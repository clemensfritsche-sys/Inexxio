"""►►► **Das Postfach – Gmail ist der Speicher, das ERP der Verlauf** (CRM Schritt 3). ◄◄◄

Drei Dinge, und jedes an genau einer Stelle:

* **Verbinden** (``connect_url`` → Google → ``callback``): je Kanal ein Postfach, OAuth
  mit dauerhaftem Zugang. **Jede eigene Gesellschaft hat eines** (``c<Objektnummer>``),
  und ►►► **ihre Kontakt-E-Mail IST seine Adresse** ◄◄◄ – gesetzt allein durch das
  Verbinden, geleert allein durch das Trennen; ein Eingabefeld dafür gibt es nicht. So
  kann die Website nie eine Adresse zeigen, über die nichts hinausgeht und nichts
  hereinkommt. Verbunden wird es am **Firmen-Datensatz** (nur ein Admin). **Persönliche
  Postfächer gibt es nicht** – im Kommunikationstool ist jeder Benutzer gleich.
* **Abgleichen** (``sync_all``): neue Mails seit dem letzten Stand (Gmail ``history``)
  werden zu Nachrichten. Der Absender wird einer Person zugeordnet – **unbekannte werden
  angelegt** (ohne Anmeldekonto: meldet sie sich später mit dieser Adresse an, übernimmt
  sie den Datensatz). Was zusammengehört, sagt der **Betreff** (``domain.topic``) – wie
  bei E-Mail; ein «Antwort auf» gibt es nicht.
* **Senden** (``send``): eine Mail, die im ERP an aussen geschrieben wird, geht über das
  Postfach ihres Kanals hinaus – im Faden ihres Betreffs (``_parent``).

**Eine eigene Adresse ist nie eine Person.** Die Adressen der Postfächer und die
Kontakt-E-Mails der eigenen Gesellschaften sind «wir» (``_ours``): eine Mail von dort hat einen
Mitarbeiter als Absender, eine Mail dorthin hat sie als Kanal – und keine davon legt je
eine Person an, auch nicht, wenn ein Benutzerkonto dieselbe Adresse trägt.

**Kein Abo, kein Pub/Sub, keine Uhr**: abgeglichen wird, wenn jemand das ERP offen hat
(``POST /erp/messages/sync``, höchstens alle ``SYNC_EVERY``). Bis dahin liegen die Mails
dort, wo sie ohnehin liegen – in Gmail.
"""

import base64
import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, getaddresses, parseaddr
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..domain import communication as dc
from ..models import Mailbox, Message, MessageParty, UserProfile
from .people import by_email, normalize_email

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://gmail.googleapis.com/gmail/v1/users/me"
#: ``gmail.modify`` statt ``readonly``: erledigt im ERP heisst gelesen im Postfach
#: (``_mark_read``) – dafür muss das ERP das Label «UNREAD» entfernen dürfen.
#: ``userinfo.profile``: das Bild des Kontos – es steht neben der Unterschrift.
SCOPES = ("https://www.googleapis.com/auth/gmail.modify "
          "https://www.googleapis.com/auth/gmail.send "
          "https://www.googleapis.com/auth/userinfo.profile")
USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"
#: Nachrichten, die älter sind, markiert niemand mehr nach – sie sind längst gelesen.
MARK_WITHIN = timedelta(days=30)
CALLBACK = "/api/v1/mail/callback"
SYNC_EVERY = timedelta(seconds=30)
STATE_TTL = 600
MAX_BODY = 20_000
#: Nie abgleichen: Entwürfe, Spam, Papierkorb.
NEVER = {"DRAFT", "SPAM", "TRASH"}
#: Was Gmail selbst als Massenpost einordnet – von aussen kommend legt es keine Kontakte an.
BULK_LABELS = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_UPDATES",
               "CATEGORY_FORUMS"}
_ROBOT = re.compile(r"(no-?reply|do-?not-?reply|mailer-daemon|postmaster|bounce)", re.I)
EXPIRED = "Die Verbindung ist abgelaufen – bitte das Postfach neu verbinden."


def ready() -> bool:
    """Gibt es eine Anbindung? Ohne OAuth-Client nicht – dann wird eine Mail nur erfasst."""
    s = get_settings()
    return bool(s.google_client_id and s.google_client_secret)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Adressen: welche sind «wir»?
# ---------------------------------------------------------------------------

def company(db: Session, channel: str):
    """Die **eigene** Gesellschaft hinter einem Unternehmens-Postfach – sonst ``None``."""
    from .sites import by_object_id
    oid = dc.company_of(channel)
    c = by_object_id(db, oid) if oid else None
    return c if c is not None and c.is_own else None


def company_address(db: Session, channel: str) -> str:
    """Die Adresse eines Unternehmens-Postfachs = die Kontakt-E-Mail seiner Gesellschaft."""
    c = company(db, channel)
    return normalize_email(c.email if c else "")


def _company_addresses(db: Session) -> set[str]:
    from .sites import selectable_companies
    return {a for a in (normalize_email(c.email) for c in selectable_companies(db)) if a}


def active(db: Session, channel: str) -> Optional[Mailbox]:
    return db.query(Mailbox).filter(Mailbox.channel == channel,
                                    Mailbox.is_active.is_(True)).first()


def address_of(db: Session, channel: str) -> str:
    """Die Adresse hinter einem Mail-Kanal – angezeigt als sein Name."""
    if dc.company_of(channel) is not None:
        return company_address(db, channel)     # leer = (noch) kein Postfach verbunden
    mb = active(db, channel)
    return mb.address if mb is not None else channel


def _ours(db: Session) -> dict[str, Optional[int]]:
    """Adresse → wer dahinter schreibt (Objektnummer, ``None`` = unbekannt)."""
    out: dict[str, Optional[int]] = {a: None for a in _company_addresses(db)}
    for mb in db.query(Mailbox).filter(Mailbox.is_active.is_(True)).all():
        out[mb.address] = mb.owner_object_id
    return out


# ---------------------------------------------------------------------------
# Verbinden
# ---------------------------------------------------------------------------

def may_connect(actor: UserProfile, channel: str) -> bool:
    """Ein Postfach gibt es nur je eigener Gesellschaft – und verbinden darf es ein Admin."""
    return dc.company_of(channel) is not None and actor.role == "admin"


def _assert_may(db: Session, actor: UserProfile, channel: str) -> None:
    if not dc.is_mail(channel):
        raise HTTPException(400, detail=f"«{channel}» ist kein Postfach.")
    if dc.company_of(channel) is not None and company(db, channel) is None:
        raise HTTPException(404, detail=f"«{dc.company_of(channel)}» ist keine eigene "
                                        f"Gesellschaft – nur sie hat ein Postfach.")
    if not may_connect(actor, channel):
        raise HTTPException(403, detail="Das Postfach einer Gesellschaft verbindet ein Admin.")


def _redirect_uri() -> str:
    return get_settings().frontend_base_url.rstrip("/") + CALLBACK


def _sign(payload: dict[str, Any]) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    key = get_settings().google_client_secret.encode()
    sig = hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def _unsign(state: str) -> dict[str, Any]:
    raw, _, sig = (state or "").partition(".")
    key = get_settings().google_client_secret.encode()
    good = hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()
    if not raw or not hmac.compare_digest(sig, good):
        raise ValueError("Die Anfrage ist ungültig – bitte erneut verbinden.")
    data = json.loads(base64.urlsafe_b64decode(raw.encode()))
    if data.get("exp", 0) < time.time():
        raise ValueError("Die Anfrage ist abgelaufen – bitte erneut verbinden.")
    return data


def connect_url(db: Session, channel: str, actor: UserProfile) -> str:
    if not ready():
        raise HTTPException(404, detail="Es ist keine Postfach-Anbindung eingerichtet.")
    _assert_may(db, actor, channel)
    hint = company_address(db, channel)
    state = _sign({"c": channel, "u": actor.object_id, "exp": time.time() + STATE_TTL})
    return AUTH_URL + "?" + urlencode({
        "client_id": get_settings().google_client_id, "redirect_uri": _redirect_uri(),
        "response_type": "code", "scope": SCOPES, "access_type": "offline",
        "prompt": "consent", "include_granted_scopes": "true",
        "login_hint": hint, "state": state,
    })


def _fernet() -> Fernet:
    digest = hashlib.sha256(b"inexxio-mailbox:" + get_settings().google_client_secret.encode())
    return Fernet(base64.urlsafe_b64encode(digest.digest()))


def _seal(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def _open(sealed: str) -> Optional[str]:
    try:
        return _fernet().decrypt(sealed.encode()).decode()
    except InvalidToken:
        return None


def callback(db: Session, code: str, state: str) -> str:
    """Google kommt zurück. Gibt den Satz zurück, den die Oberfläche zeigt (leer = gut)."""
    try:
        data = _unsign(state)
    except (ValueError, json.JSONDecodeError) as exc:
        return str(exc)
    channel = data["c"]
    actor = db.query(UserProfile).filter(UserProfile.object_id == data["u"]).first()
    if actor is None or not may_connect(actor, channel):
        return "Dieses Postfach darfst du nicht verbinden."
    with httpx.Client(timeout=20) as http:
        r = http.post(TOKEN_URL, data={
            "code": code, "client_id": get_settings().google_client_id,
            "client_secret": get_settings().google_client_secret,
            "redirect_uri": _redirect_uri(), "grant_type": "authorization_code"})
        if r.status_code != 200:
            return "Google hat den Zugang nicht erteilt – bitte erneut verbinden."
        tokens = r.json()
        refresh = tokens.get("refresh_token")
        if not refresh:
            return "Google hat keinen dauerhaften Zugang erteilt – bitte erneut verbinden."
        auth = {"Authorization": f"Bearer {tokens['access_token']}"}
        prof = http.get(f"{API}/profile", headers=auth).json()
        who = http.get(USERINFO, headers=auth)
        picture = (who.json().get("picture") or "") if who.status_code == 200 else ""
    return _store(db, channel, actor, normalize_email(prof.get("emailAddress")),
                  refresh, str(prof.get("historyId") or ""), picture)


def _store(db: Session, channel: str, actor: UserProfile, address: str, refresh: str,
           history: str, picture: str = "") -> str:
    """Das Postfach festhalten. **Eine Adresse gehört genau einem Postfach** – auch nicht
    der Kontakt-E-Mail einer anderen Gesellschaft. Am Unternehmens-Postfach wird sie
    zugleich **die Kontakt-E-Mail der Gesellschaft** (die eine Schreibstelle dafür)."""
    if not address:
        return "Google hat keine Adresse genannt – bitte erneut verbinden."
    other = db.query(Mailbox).filter(Mailbox.address == address, Mailbox.channel != channel,
                                     Mailbox.is_active.is_(True)).first()
    firm = company(db, channel)
    taken = _company_addresses(db) - ({normalize_email(firm.email)} if firm else set())
    if other is not None or address in taken:
        return f"«{address}» ist bereits als anderes Postfach verbunden."
    old = active(db, channel)
    if old is not None:
        old.is_active = False
        db.flush()
    db.add(Mailbox(channel=channel, address=address, owner_object_id=actor.object_id,
                   token=_seal(refresh), history_id=history or None,
                   picture=picture[:1000] or None))
    if firm is not None:
        _contact(db, firm, address, actor)
    db.commit()
    return ""


def _contact(db: Session, firm: Any, address: str, actor: UserProfile) -> None:
    """Die Kontakt-E-Mail einer eigenen Gesellschaft – geschrieben NUR von hier."""
    from .admin import log_audit
    if normalize_email(firm.email) != address:
        firm.email = address
        log_audit(db, "company_settings", "email", address or "[entfernt]", actor.id,
                  object_id=firm.object_id)


def disconnect(db: Session, channel: str, actor: UserProfile) -> None:
    """Trennen – und am Unternehmens-Postfach verschwindet damit seine Kontakt-E-Mail:
    eine Adresse, über die nichts mehr hereinkommt, zeigt die Website nicht."""
    _assert_may(db, actor, channel)
    mb = active(db, channel)
    firm = company(db, channel)
    if firm is not None:
        _contact(db, firm, "", actor)
    if mb is None:
        db.commit()
        return
    mb.is_active = False
    token = _open(mb.token)
    db.commit()
    if token:
        try:
            httpx.post(REVOKE_URL, data={"token": token}, timeout=10)
        except httpx.HTTPError:
            pass        # zurückgezogen ist es bei uns; Google räumt abgelaufene selbst


# ---------------------------------------------------------------------------
# Zugriff
# ---------------------------------------------------------------------------

def _access(mb: Mailbox) -> Optional[str]:
    """Ein frisches Zugangs-Token – oder ``None``, und dann steht der Grund am Postfach."""
    refresh = _open(mb.token)
    if refresh is None:
        mb.problem = EXPIRED
        return None
    try:
        r = httpx.post(TOKEN_URL, timeout=20, data={
            "client_id": get_settings().google_client_id,
            "client_secret": get_settings().google_client_secret,
            "refresh_token": refresh, "grant_type": "refresh_token"})
    except httpx.HTTPError:
        return None     # Netz weg – beim nächsten Mal; kein Grund, die Verbindung zu kappen
    if r.status_code == 200:
        return r.json().get("access_token")
    if r.status_code in (400, 401) and "invalid_grant" in r.text:
        mb.problem = EXPIRED
    return None


def _get(token: str, path: str, **params: Any) -> httpx.Response:
    return httpx.get(f"{API}/{path}", params=params, timeout=20,
                     headers={"Authorization": f"Bearer {token}"})


# ---------------------------------------------------------------------------
# Abgleichen
# ---------------------------------------------------------------------------

def sync_all(db: Session, *, force: bool = False) -> int:
    """Alle verbundenen Postfächer abgleichen und Fälliges senden. Gibt die Zahl neuer
    Nachrichten zurück. Ein Postfach, das gerade ein anderer abgleicht, wird übersprungen
    (``SKIP LOCKED``) – zwei Instanzen holen dieselbe Mail nie gleichzeitig."""
    if not ready():
        return 0
    due = _now() - SYNC_EVERY
    boxes = (db.query(Mailbox)
             .filter(Mailbox.is_active.is_(True), Mailbox.problem.is_(None))
             .with_for_update(skip_locked=True).all())
    new = 0
    for mb in boxes:
        if force or mb.synced_at is None or mb.synced_at < due:
            try:        # ein gestörtes Postfach hält die übrigen und den Versand nicht auf
                with db.begin_nested():
                    new += _sync_one(db, mb)
                    _mark_read(db, mb)
            except Exception as exc:
                print(f"WARNING: MAILBOX sync {mb.channel} failed: {exc!r}", flush=True)
    send_due(db)
    db.commit()
    return new


def _sync_one(db: Session, mb: Mailbox) -> int:
    token = _access(mb)
    if not token:
        return 0
    ids, latest = _new_ids(token, mb.history_id)
    count = 0
    for gid in ids:
        if db.query(Message.id).filter(Message.channel == mb.channel,
                                       Message.gmail_id == gid).first():
            continue
        r = _get(token, f"messages/{gid}", format="full")
        if r.status_code == 200 and ingest(db, mb, r.json()):
            count += 1
    if latest:
        mb.history_id = latest
    mb.synced_at = _now()
    return count


def _mark_read(db: Session, mb: Mailbox) -> None:
    """►►► **Erledigt im ERP = gelesen in Gmail** – in diese eine Richtung. ◄◄◄

    Was hier beantwortet ist (dieselbe Ableitung wie im Verlauf, ``communication.answered``),
    verliert in Gmail sein «UNREAD», genau einmal (``read_marked``). Umgekehrt nicht:
    gelesen heisst nicht erledigt. Fehlt dem Postfach die Freigabe (vor dem Umstellen
    verbunden), bleibt alles, wie es ist – bis es neu verbunden wird."""
    from collections import defaultdict
    from .communication import answered
    since = _now() - MARK_WITHIN
    msgs = db.query(Message).filter(
        Message.channel == mb.channel, Message.gmail_id.isnot(None),
        Message.read_marked.is_(False), Message.is_active.is_(True),
        Message.at >= since).all()
    if not msgs:
        return
    roles: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for p in db.query(MessageParty).filter(
            MessageParty.message_id.in_([m.id for m in msgs])).all():
        roles[p.message_id][p.role].append(p.person_object_id)
    # **Einmal gefragt, nicht je Nachricht** (Cleanup B-50): als Bedingung im
    # Ausdruck lief ``answered`` für jede Mail erneut über alle – quadratisch, und das
    # alle 30 Sekunden je Postfach.
    replied = answered(db, msgs, roles)
    done = [m for m in msgs if m.id in replied]
    token = _access(mb) if done else None
    if not token:
        return
    try:
        r = httpx.post(f"{API}/messages/batchModify", timeout=20,
                       headers={"Authorization": f"Bearer {token}"},
                       json={"ids": [m.gmail_id for m in done], "removeLabelIds": ["UNREAD"]})
    except httpx.HTTPError:
        return
    if r.status_code in (200, 204):
        for m in done:
            m.read_marked = True
        db.flush()
    else:
        print(f"WARNING: MAILBOX mark-read {mb.channel} failed: {r.status_code}", flush=True)


def _new_ids(token: str, start: Optional[str]) -> tuple[list[str], Optional[str]]:
    """Die neuen Mail-Ids seit ``start`` – beim ersten Mal keine (es zählt ab Verbinden)."""
    if not start:
        prof = _get(token, "profile")
        return [], str(prof.json().get("historyId")) if prof.status_code == 200 else None
    ids: list[str] = []
    page: Optional[str] = None
    latest = start
    while True:
        params: dict[str, Any] = {"startHistoryId": start, "historyTypes": "messageAdded"}
        if page:
            params["pageToken"] = page
        r = _get(token, "history", **params)
        if r.status_code == 404:        # Stand zu alt: die letzten zwei Tage nachholen
            listed = _get(token, "messages", q="newer_than:2d", maxResults=200).json()
            prof = _get(token, "profile").json()
            return [m["id"] for m in listed.get("messages", [])], str(prof.get("historyId"))
        if r.status_code != 200:
            return [], None
        data = r.json()
        latest = str(data.get("historyId") or latest)
        for h in data.get("history", []):
            ids += [a["message"]["id"] for a in h.get("messagesAdded", [])]
        page = data.get("nextPageToken")
        if not page:
            return list(dict.fromkeys(ids)), latest


def ingest(db: Session, mb: Mailbox, raw: dict[str, Any]) -> bool:
    """**Eine Gmail-Nachricht wird eine Nachricht.** ``False`` = übersprungen."""
    from .communication import write
    labels = set(raw.get("labelIds") or [])
    payload = raw.get("payload") or {}
    head = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    ours = _ours(db)
    name, sender_addr = parseaddr(head.get("from", ""))
    sender_addr = normalize_email(sender_addr)
    inbound = sender_addr not in ours
    if labels & NEVER or not sender_addr or (inbound and _bulk(labels, head, sender_addr)):
        return False
    rfc = (head.get("message-id") or "").strip()[:255] or None
    if rfc and db.query(Message.id).filter(Message.rfc_id == rfc).first():
        return False
    sender = (person_for(db, name, sender_addr) if inbound
              else ours.get(sender_addr) or mb.owner_object_id)
    roles: dict[str, list[int]] = {"to": [], "cc": [], "bcc": [], "about": []}
    for role in ("to", "cc"):
        for n, addr in getaddresses([head.get(role, "")]):
            addr = normalize_email(addr)
            if addr and "@" in addr and addr not in ours:
                roles[role].append(person_for(db, n, addr))
    msg = Message(
        sender_object_id=sender, channel=mb.channel,
        subject=(head.get("subject") or "").strip()[:255] or None,
        body=_strip_quote(_text(payload))[:MAX_BODY],
        at=datetime.fromtimestamp(int(raw.get("internalDate", 0)) / 1000, timezone.utc),
        created_by=None, gmail_id=raw.get("id"), thread_id=raw.get("threadId"),
        rfc_id=rfc, attachments=_attachments(payload) or None)
    try:
        with db.begin_nested():
            write(db, msg, roles)
    except IntegrityError:
        return False        # ein paralleler Abgleich war schneller – dieselbe Mail
    return True


def _bulk(labels: set[str], head: dict[str, str], addr: str) -> bool:
    """Massenpost legt keine Kontakte an: Gmails eigene Einordnung, die üblichen Köpfe
    automatischer Mails, und Absender, die niemand liest."""
    auto = head.get("auto-submitted", "no").lower()
    return bool(labels & BULK_LABELS or "list-unsubscribe" in head
                or head.get("precedence", "").lower() in {"bulk", "list", "junk"}
                or auto != "no" or _ROBOT.search(addr.split("@")[0]))


def person_for(db: Session, name: str, addr: str, phone: str = "") -> int:
    """Die Person zu dieser Adresse – **angelegt, wenn es sie nicht gibt**.

    Ohne Anmeldekonto: der Platzhalter ``mail:<adresse>`` ist eindeutig, und meldet sie
    sich später mit dieser (bestätigten) Adresse an, übernimmt sie genau diesen Datensatz
    (``core/auth._resolve_user``)."""
    from .admin import log_audit
    from .objects import next_object_id
    found = by_email(db, addr)
    if found is not None and found.object_id:
        if phone and not found.phone:
            found.phone = phone[:50]
        return found.object_id
    first, last = split_name(name) or (addr.split("@")[0], "")
    user = UserProfile(firebase_uid=f"mail:{addr}"[:128], email=addr, role="user",
                       first_name=first[:100], last_name=last[:100],
                       phone=phone[:50] or None, object_id=next_object_id(db, "user"))
    db.add(user)
    db.flush()
    log_audit(db, "user_profiles", None, f"Kontakt «{user.display_name}» angelegt",
              None, object_id=user.object_id)
    return user.object_id


def split_name(name: str) -> Optional[tuple[str, str]]:
    """Vor- und Nachname aus dem Namen im Mail-Kopf. «Fritsche, Clemens» ist die
    Schreibweise «Nachname, Vorname» – das Komma sagt es, also wird gedreht und das Komma
    fällt weg. Sonst: das erste Wort ist der Vorname. ``None`` = kein Name."""
    raw = re.sub(r"\s+", " ", (name or "").replace('"', "")).strip()
    if "," in raw:
        last, _, first = raw.partition(",")
        raw = f"{first.strip()} {last.strip()}".strip()
    parts = raw.split(" ") if raw else []
    return (parts[0][:100], " ".join(parts[1:])[:100]) if parts else None


class _Html(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("style", "script"):
            self.skip += 1
        if tag in ("br", "p", "div", "tr", "li"):
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script") and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.out.append(data)


def _decode(part: dict[str, Any]) -> str:
    data = (part.get("body") or {}).get("data")
    if not data:
        return ""
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    return raw.decode("utf-8", errors="replace")


def _parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out = [payload]
    for p in payload.get("parts") or []:
        out += _parts(p)
    return out


def _text(payload: dict[str, Any]) -> str:
    """Der lesbare Text: ``text/plain`` zuerst, sonst ``text/html`` ohne Auszeichnung."""
    parts = [p for p in _parts(payload) if not p.get("filename")]
    for mime in ("text/plain", "text/html"):
        for p in parts:
            if p.get("mimeType") == mime and (text := _decode(p)):
                if mime == "text/html":
                    h = _Html()
                    h.feed(text)
                    text = "".join(h.out)
                return re.sub(r"\n{3,}", "\n\n", text.replace("\r", "")).strip()
    return ""


_QUOTE = re.compile(
    r"\n[ \t]*(?:(?:Am|On)\b[^\n]*(?:\n[^\n]*)?(?:schrieb|wrote)[^\n]*:[ \t]*\n"
    r"|-{2,}[ \t]*(?:Original Message|Ursprüngliche Nachricht)[ \t]*-{2,})", re.I)


def _strip_quote(text: str) -> str:
    """Ohne den zitierten Verlauf – der steht schon als eigene Nachricht im Verlauf."""
    m = _QUOTE.search("\n" + text + "\n")
    if m and m.start() > 0:
        text = text[: m.start() - 1]
    lines = text.rstrip().split("\n")
    while lines and lines[-1].lstrip().startswith(">"):
        lines.pop()
    return "\n".join(lines).strip()


def _attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"name": p["filename"], "size": (p.get("body") or {}).get("size", 0)}
            for p in _parts(payload) if p.get("filename")]


# ---------------------------------------------------------------------------
# Senden
# ---------------------------------------------------------------------------

def assert_may_send(db: Session, channel: str, sender: UserProfile) -> None:
    """Hinaus geht nur, was ein verbundenes Postfach hat."""
    mb = active(db, channel)
    if mb is None or mb.problem:
        raise HTTPException(400, detail=f"Das Postfach «{address_of(db, channel)}» ist nicht "
                                        f"verbunden – erst verbinden, dann senden.")


def send_due(db: Session) -> None:
    """Was hinaus muss und dessen Zeitpunkt da ist (auch ein früher gescheiterter Versand).

    **Jede Mail geht genau einmal hinaus.** Sie wird einzeln gesperrt (``SKIP LOCKED`` –
    ein zweiter Abgleich aus einem anderen Tab überspringt sie), gesendet und **sofort**
    festgeschrieben. Ein Fehler bei einer späteren Mail kann eine bereits versendete damit
    nicht mehr zurückrollen und erneut hinausschicken."""
    db.commit()     # was der Abgleich bis hier geschrieben hat, steht – unabhängig vom Versand
    ids = [i for (i,) in db.query(Message.id).filter(
        Message.outgoing.is_(True), Message.is_active.is_(True),
        Message.at <= _now()).order_by(Message.at).limit(20)]
    for mid in ids:
        msg = (db.query(Message).filter(Message.id == mid, Message.outgoing.is_(True))
               .with_for_update(skip_locked=True).first())
        if msg is None:
            continue    # versendet oder gerade in Arbeit bei einem anderen Abgleich
        try:
            send(db, msg)
            db.commit()
        except Exception as exc:    # eine kaputte Mail hält die übrigen nicht auf
            db.rollback()
            print(f"WARNING: MAILBOX send {mid} failed: {exc!r}", flush=True)


def send(db: Session, msg: Message) -> bool:
    """Eine Mail über das Postfach ihres Kanals hinausschicken – im Faden, auf den sie
    antwortet. Scheitert es, bleibt ``outgoing`` stehen, und der nächste Abgleich versucht
    es wieder; nichts geht still verloren."""
    mb = active(db, msg.channel)
    token = _access(mb) if mb is not None and not mb.problem else None
    if not token:
        return False
    parent = _parent(db, msg)
    mime = _mime(db, mb, msg, parent)
    body: dict[str, Any] = {"raw": base64.urlsafe_b64encode(mime.as_bytes()).decode()}
    if parent is not None and parent.channel == msg.channel and parent.thread_id:
        body["threadId"] = parent.thread_id
    try:
        r = httpx.post(f"{API}/messages/send", json=body, timeout=30,
                       headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        print(f"WARNING: MAILBOX send {msg.id} failed: {exc!r}", flush=True)
        return False
    if r.status_code != 200:
        print(f"WARNING: MAILBOX send {msg.id} failed: {r.status_code} {r.text[:200]}",
              flush=True)
        return False
    # Ab hier IST die Mail draussen: nichts darf mehr werfen, sonst bliebe ``outgoing``
    # stehen und der nächste Abgleich schickte sie ein zweites Mal.
    msg.outgoing = False
    try:
        sent = r.json()
    except ValueError:
        sent = {}
    msg.gmail_id, msg.thread_id = sent.get("id"), sent.get("threadId")
    msg.rfc_id = _rfc_id(token, msg.gmail_id)
    msg.subject = msg.subject or mime["Subject"] or None
    html_part = mime.get_body(("html",))
    msg.html = msg.html or (html_part.get_content() if html_part is not None else None)
    db.flush()
    return True


def _rfc_id(token: str, gmail_id: Optional[str]) -> Optional[str]:
    """Die ``Message-ID`` einer eben gesendeten Mail (für den Faden der Antworten) – oder
    ``None``. Fehlt sie, ist das ein Schönheitsfehler; ein Fehler hier darf den Versand
    nicht ungeschehen machen."""
    if not gmail_id:
        return None
    try:
        meta = _get(token, f"messages/{gmail_id}", format="metadata",
                    metadataHeaders="Message-ID")
        if meta.status_code != 200:
            return None
        head = {h["name"].lower(): h["value"]
                for h in (meta.json().get("payload") or {}).get("headers", [])}
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    return (head.get("message-id") or "")[:255] or None


def _parent(db: Session, msg: Message) -> Optional[Message]:
    """**Der Faden, in dem eine Mail hinausgeht** – wie bei Gmail über den Betreff: die
    jüngste frühere Mail mit **demselben Anliegen** (``domain.topic``), die eine
    ``Message-ID`` trägt und an der einer der Empfänger beteiligt ist. Ohne Betreff gibt
    es keinen Faden – eine neue Mail beginnt einen."""
    key = dc.topic(msg.subject)
    if not key:
        return None
    people = {p.person_object_id for p in db.query(MessageParty).filter(
        MessageParty.message_id == msg.id, MessageParty.role.in_(("to", "cc"))).all()}
    if not people:
        return None
    involved = select(MessageParty.message_id).where(MessageParty.person_object_id.in_(people))
    rows = (db.query(Message).filter(
        Message.id != msg.id, Message.is_active.is_(True), Message.rfc_id.isnot(None),
        Message.at <= msg.at,
        or_(Message.sender_object_id.in_(people), Message.id.in_(involved)))
        .order_by(Message.at.desc()).limit(200).all())
    return next((m for m in rows if dc.topic(m.subject) == key), None)


def signer_of(sender: Optional[UserProfile], msg: Message):
    """Wer unterschreibt: der Mensch, der die Mail **geschrieben** hat (``created_by``),
    sofort erkennbar als Mitarbeiter – mit seinem Profilbild. Eine automatische Mail
    unterschreibt das Unternehmen (``None``)."""
    from . import mail_layout as layout
    from .people import STAFF_ROLES
    if msg.created_by is None or sender is None or sender.role not in STAFF_ROLES:
        return None
    return layout.Signer(name=sender.display_name, photo=sender.photo_url or "")


def _mime(db: Session, mb: Mailbox, msg: Message, parent: Optional[Message]) -> EmailMessage:
    """Die Mail – **in der einen Vorlage des Hauses** (``mail_layout``): als Text und als
    HTML, unterschrieben mit dem Menschen im Namen der Gesellschaft."""
    from . import mail_layout as layout
    parties = db.query(MessageParty).filter(MessageParty.message_id == msg.id).all()
    ids = {p.person_object_id for p in parties} | {msg.sender_object_id}
    people = {u.object_id: u for u in
              db.query(UserProfile).filter(UserProfile.object_id.in_(ids)).all()}
    signer = signer_of(people.get(msg.sender_object_id), msg)
    firm = layout.firm_of(company(db, msg.channel), mb.address, mb.picture or "")
    mime = EmailMessage()
    mime["From"] = formataddr((layout.sender_name(signer), mb.address))
    for role, header in (("to", "To"), ("cc", "Cc"), ("bcc", "Bcc")):
        addrs = [formataddr((people[p.person_object_id].display_name,
                             people[p.person_object_id].email))
                 for p in parties if p.role == role and p.person_object_id in people]
        if addrs:
            mime[header] = ", ".join(addrs)
    mime["Subject"] = msg.subject or ""
    if parent is not None:
        mime["In-Reply-To"] = parent.rfc_id
        mime["References"] = parent.rfc_id
    if msg.html:
        # Schon gebaut (die Eingangsbestätigung): ``body`` IST ihr Inhalt (``compose``).
        text, html = layout.text(msg.subject or "", msg.body or "", firm, signer), msg.html
    else:
        mail = layout.compose(msg.subject or "", msg.body or "", firm, signer)
        msg.body = mail.body        # der Verlauf ist, was hinausgeht – Wort für Wort
        text, html = mail.text, mail.html
    mime.set_content(text)
    mime.add_alternative(html, subtype="html")
    return mime


# ---------------------------------------------------------------------------
# Auskunft
# ---------------------------------------------------------------------------

def status(db: Session, actor: UserProfile, company_id: Optional[int] = None
           ) -> list[dict[str, Any]]:
    """Das Postfach einer Gesellschaft (nur eine eigene hat eines) – mit Adresse, Zustand
    und ob dieser Betrachter verbinden darf. Ohne Gesellschaft: keines."""
    keys = [dc.company(company_id)] if (
        company_id is not None and company(db, dc.company(company_id))) else []
    out = []
    for key in keys:
        mb = active(db, key)
        out.append({"channel": key, "address": address_of(db, key),
                    "connected": mb is not None and not mb.problem,
                    "problem": mb.problem if mb is not None else None,
                    "may_connect": ready() and may_connect(actor, key)})
    return out


def gmail_url(address: str, msg: Message) -> Optional[str]:
    ref = msg.thread_id or msg.gmail_id
    if not ref:
        return None
    return f"https://mail.google.com/mail/?authuser={address}#all/{ref}"
