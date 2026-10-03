"""Anfragen der öffentlichen Website (``/kontakt`` und die Kurzformulare der Leistungsseiten).

►►► Strikt getrennt vom ERP. ◄◄◄ Dieses Modul importiert nichts aus ``app.models``,
``app.services`` oder ``app.core`` und berührt keine Tabelle: eine Anfrage wird geprüft,
als E-Mail an uns geschickt (Fotos im Anhang), und die anfragende Person bekommt eine
Bestätigung. Das ist alles – keine Datenbank, kein Konto, keine Warteschlange.

**Die Wörter kommen von der Website.** Welche Anliegen, Themen und Dringlichkeiten es gibt,
wie die Felder heissen und welche Fehlermeldungen erscheinen, steht in
``website/src/config`` und wird mit ``npm run export:contact`` nach
``app/assets/website_contact.json`` übertragen (die CI prüft, dass die Datei aktuell ist).
Formular im Browser und Server sagen damit garantiert dasselbe.

**Ohne JavaScript** schickt der Browser das Formular klassisch (multipart). Dann antwortet
der Endpunkt mit HTML: bei Erfolg ``303`` auf ``/kontakt/danke``, sonst eine schlichte Seite
mit den fehlenden Angaben bzw. mit Telefon und einem vorausgefüllten mailto-Link. Mit
``Accept: application/json`` (das Skript der Website) antwortet er mit JSON.

**Keine Anfrage geht still verloren.** Ist kein Mailversand eingerichtet oder schlägt er
fehl, antwortet der Endpunkt mit ``503`` – das Formular zeigt dann Telefon und den
vorausgefüllten mailto-Link –, und die Anfrage steht vollständig (ohne Fotos) im Log.

**Konfiguration nur über Umgebungsvariablen** (``INQUIRY_*``, siehe ``InquirySettings``),
Zugangsdaten nie im Repository.

Schema der Anfrage (``anfrage.json`` im Anhang der E-Mail an uns; Grundlage für eine
spätere Übernahme ins ERP)::

    {
      "schema": "inexxio.website.inquiry/1",
      "id": "uuid", "received_at": "ISO-8601 UTC",
      "form": "haupt" | "kurz", "source": "/pfad/der/seite",
      "kind":    {"value": "kran", "label": "Kran"},
      "need":    {"value": "...", "label": "..."} | null,
      "urgency": {"value": "...", "label": "..."} | null,
      "asset":   {"maker": str|null, "year": str|null, "part": str|null,
                  "mixer": str|null, "cranes": int|null},
      "place": str, "message": str | null,
      "contact": {"name": str, "company": str|null, "phone": str|null,
                  "email": str|null, "preference": {"value", "label"} | null},
      "photos":  [{"filename": str, "content_type": str, "size": int}]
    }
"""
from __future__ import annotations

import json
import re
import smtplib
import ssl
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from html import escape
from pathlib import Path
from threading import Lock
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

router = APIRouter(prefix="/api/v1/contact", tags=["contact"])

#: Das Vokabular der Website (generiert, siehe Moduldoku).
VOCAB: dict = json.loads(
    (Path(__file__).resolve().parent.parent / "assets" / "website_contact.json").read_text("utf-8")
)
MSG: dict[str, str] = VOCAB["messages"]
LIMITS: dict[str, int] = VOCAB["limits"]
PHOTOS: dict = VOCAB["photos"]

SCHEMA = "inexxio.website.inquiry/1"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
PHONE_RE = re.compile(r"^[+()\d][\d\s/().-]{5,}$")
SOURCE_RE = re.compile(r"^/[a-z0-9/_-]{0,80}$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
        ".heic": "image/heic", ".heif": "image/heif"}
#: Obergrenze der ganzen Anfrage: Fotos plus grosszügig Platz für die Textfelder.
MAX_BODY = int(PHOTOS["maxTotalBytes"]) + 1024 * 1024
WINDOW_SECONDS = 3600


class InquirySettings(BaseSettings):
    """Mailversand der Website-Anfragen – ausschliesslich aus der Umgebung.

    Ohne ``INQUIRY_SMTP_HOST`` ist der Versand aus: der Endpunkt antwortet dann mit 503,
    und das Formular bietet Telefon und mailto an.
    """

    model_config = SettingsConfigDict(env_prefix="INQUIRY_", extra="ignore")

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    #: True = TLS von Anfang an (Port 465); sonst STARTTLS, sobald der Server es anbietet.
    smtp_ssl: bool = False
    smtp_timeout: float = 20.0
    #: Absender; leer = ``smtp_user``.
    mail_from: str = ""
    #: Empfänger der Anfragen; leer = die E-Mail-Adresse der Website-Konfiguration.
    mail_to: str = ""
    #: Bestätigung an die anfragende Person (wenn sie eine E-Mail-Adresse angibt).
    confirm: bool = True
    #: Gesendete Anfragen je IP-Adresse und Stunde.
    rate_limit: int = 5


# ------------------------------------------------------------------ Begrenzung je IP

_hits: dict[str, deque[float]] = {}
_hits_lock = Lock()


def reset_rate_limit() -> None:
    """Für Tests: Zähler leeren."""
    with _hits_lock:
        _hits.clear()


def _allow(ip: str, limit: int) -> bool:
    """Höchstens ``limit`` Sendungen je IP und Stunde – nur im Arbeitsspeicher dieser Instanz."""
    now = time.monotonic()
    with _hits_lock:
        q = _hits.setdefault(ip, deque())
        while q and now - q[0] > WINDOW_SECONDS:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        if len(_hits) > 10_000:  # Speicher begrenzen: alte Einträge verwerfen
            for key in [k for k, v in _hits.items() if not v][:5_000]:
                _hits.pop(key, None)
        return True


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    return first or (request.client.host if request.client else "unbekannt")


# ------------------------------------------------------------------ Einlesen und Prüfen

@dataclass
class Photo:
    filename: str
    content_type: str
    data: bytes


@dataclass
class Inquiry:
    form: str
    source: str
    values: dict[str, str]
    photos: list[Photo] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _clean(raw: object, multiline: bool = False) -> str:
    """Text bereinigen: Steuerzeichen weg, Zeilenenden vereinheitlicht, einzeilige Felder
    ohne Umbruch (sie landen im Betreff einer E-Mail)."""
    text = raw if isinstance(raw, str) else ""
    text = CONTROL_RE.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    if not multiline:
        text = " ".join(text.split())
    return text.strip()


def _options(key: str) -> dict[str, str]:
    return {o["value"]: o["label"] for o in VOCAB[key]}


def _check_choices(values: dict[str, str], form: str, errors: dict[str, str]) -> None:
    kind = values["kind"]
    if kind not in _options("kinds"):
        errors["kind"] = MSG["kind"]
        return
    needs = {n["value"] for n in VOCAB["needs"].get(kind, [])}
    if not needs:
        values["need"] = ""  # ein Thema gibt es nur bei Kran und Fahrmischer
    elif values["need"] and values["need"] not in needs:
        errors["need"] = MSG["need"]
    elif form == "haupt" and not values["need"]:
        errors["need"] = MSG["need"]
    if values["urgency"] and values["urgency"] not in _options("urgencies"):
        errors["urgency"] = MSG["urgency"]
    elif form == "haupt" and not values["urgency"]:
        errors["urgency"] = MSG["urgency"]
    if values["contact_pref"] and values["contact_pref"] not in _options("contactPrefs"):
        values["contact_pref"] = ""
    if kind != "teile":
        values["part"] = values["mixer"] = ""
    elif form == "haupt" and not values["part"]:
        errors["part"] = MSG["part"]
    if kind != "abo":
        values["cranes"] = ""
    elif values["cranes"] and not re.fullmatch(r"[1-9]\d{0,2}", values["cranes"]):
        errors["cranes"] = MSG["cranes"]
    elif form == "kurz" and not values["cranes"]:
        errors["cranes"] = MSG["cranes"]


def _check_fields(values: dict[str, str], form: str, errors: dict[str, str]) -> None:
    for name, limit in LIMITS.items():
        if name in values and len(values[name]) > limit:
            errors.setdefault(name, MSG["tooLong"].replace("{max}", str(limit)))
    if values["year"] and not re.fullmatch(r"(19|20)\d{2}", values["year"]):
        errors.setdefault("year", MSG["year"])
    if not values["place"]:
        errors.setdefault("place", MSG["place"])
    if form == "kurz" and not values["message"]:
        errors.setdefault("message", MSG["message"])
    if not values["name"]:
        errors.setdefault("name", MSG["name"])
    phone, email, pref = values["phone"], values["email"], values["contact_pref"]
    if not phone and not email:
        errors.setdefault("phone", MSG["contact"])
        return
    if phone and not PHONE_RE.match(phone):
        errors.setdefault("phone", MSG["phone"])
    if email and not EMAIL_RE.match(email):
        errors.setdefault("email", MSG["email"])
    if pref == "telefon" and not phone:
        errors.setdefault("phone", MSG["prefPhone"])
    if pref == "email" and not email:
        errors.setdefault("email", MSG["prefEmail"])


def _mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB".replace(".", ",")


async def _read_photos(uploads: list, errors: dict[str, str]) -> list[Photo]:
    files = [u for u in uploads if isinstance(u, UploadFile) and (u.filename or "").strip()]
    if not files:
        return []
    if len(files) > int(PHOTOS["max"]):
        errors["photos"] = MSG["photosCount"].replace("{max}", str(PHOTOS["max"])).replace("{count}", str(len(files)))
        return []
    photos: list[Photo] = []
    total = 0
    for upload in files:
        name = Path(upload.filename or "foto").name
        ext = Path(name).suffix.lower()
        if ext not in PHOTOS["extensions"]:
            errors["photos"] = MSG["photosType"].replace("{name}", name[:80])
            return []
        data = await upload.read()
        total += len(data)
        safe = re.sub(r"[^\w.\-]+", "_", name)[-80:] or f"foto{ext}"
        photos.append(Photo(filename=safe, content_type=MIME.get(ext, "application/octet-stream"), data=data))
    if total > int(PHOTOS["maxTotalBytes"]):
        errors["photos"] = MSG["photosSize"].replace("{size}", _mb(total)).replace("{max}", _mb(int(PHOTOS["maxTotalBytes"])))
        return []
    return photos


FIELDS = ("kind", "need", "urgency", "part", "mixer", "cranes", "maker", "year", "place",
          "message", "name", "company", "phone", "email", "contact_pref")


async def _parse(form_data, errors: dict[str, str]) -> Inquiry:
    form = "kurz" if _clean(form_data.get("form")) == "kurz" else "haupt"
    source = _clean(form_data.get("source")).lower()
    values = {name: _clean(form_data.get(name), multiline=(name == "message")) for name in FIELDS}
    _check_choices(values, form, errors)
    _check_fields(values, form, errors)
    photos = await _read_photos(form_data.getlist("photos"), errors)
    return Inquiry(form=form, source=source if SOURCE_RE.match(source) else "/kontakt",
                   values=values, photos=photos)


# ------------------------------------------------------------------ Darstellung

def _shown(inq: Inquiry) -> list[tuple[str, str, str]]:
    """(Feld, Beschriftung, angezeigter Wert) in der Reihenfolge der Website, ohne Leeres."""
    v = inq.values
    display = {
        "kind": _options("kinds").get(v["kind"], v["kind"]),
        "need": {n["value"]: n["label"] for ns in VOCAB["needs"].values() for n in ns}.get(v["need"], ""),
        "urgency": _options("urgencies").get(v["urgency"], ""),
        "contact_pref": _options("contactPrefs").get(v["contact_pref"], ""),
    }
    rows = []
    for name, label in VOCAB["labels"]:
        value = display.get(name, v.get(name, ""))
        if value:
            rows.append((name, label, value))
    return rows


def _subject(inq: Inquiry) -> str:
    v = inq.values
    kinds = {k["value"]: k["subject"] for k in VOCAB["kinds"]}
    urgencies = {u["value"]: u["subject"] for u in VOCAB["urgencies"]}
    tags = ["Anfrage", kinds.get(v["kind"], v["kind"]), urgencies.get(v["urgency"], "")]
    who = v["company"] or v["name"]
    place = f" – {v['place']}" if v["place"] else ""
    return f"{''.join(f'[{t}]' for t in tags if t)} {who}{place}".strip()


def _summary(inq: Inquiry, *, include_message_block: bool) -> str:
    lines = []
    for name, label, value in _shown(inq):
        if name == "message" and include_message_block:
            continue
        lines.append(f"{label}: {value}")
    if include_message_block and inq.values["message"]:
        lines += ["", "Beschreibung:", inq.values["message"]]
    return "\n".join(lines)


def _mailto(inq: Inquiry) -> str:
    """Dieselbe Form wie der mailto-Link im Browser (scripts/form.ts)."""
    lines = [f"{label}: {value[:1200] if name == 'message' else value}" for name, label, value in _shown(inq)]
    body = "\n".join(lines)
    if inq.photos:
        n = len(inq.photos)
        body += f"\n\nFotos: bitte {'das Foto' if n == 1 else f'die {n} Fotos'} an diese E-Mail anhängen."
    return f"mailto:{VOCAB['email']}?subject={quote(_subject(inq))}&body={quote(body)}"


def as_record(inq: Inquiry) -> dict:
    """Die Anfrage als JSON-Objekt (Schema siehe Moduldoku) – ohne Fotodaten."""
    v = inq.values
    opt = lambda key, value: ({"value": value, "label": _options(key)[value]} if value else None)  # noqa: E731
    needs = {n["value"]: n["label"] for ns in VOCAB["needs"].values() for n in ns}
    return {
        "schema": SCHEMA,
        "id": inq.id,
        "received_at": inq.received_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "form": inq.form,
        "source": inq.source,
        "kind": opt("kinds", v["kind"]),
        "need": {"value": v["need"], "label": needs[v["need"]]} if v["need"] else None,
        "urgency": opt("urgencies", v["urgency"]),
        "asset": {"maker": v["maker"] or None, "year": v["year"] or None, "part": v["part"] or None,
                  "mixer": v["mixer"] or None, "cranes": int(v["cranes"]) if v["cranes"] else None},
        "place": v["place"],
        "message": v["message"] or None,
        "contact": {"name": v["name"], "company": v["company"] or None, "phone": v["phone"] or None,
                    "email": v["email"] or None, "preference": opt("contactPrefs", v["contact_pref"])},
        "photos": [{"filename": p.filename, "content_type": p.content_type, "size": len(p.data)}
                   for p in inq.photos],
    }


# ------------------------------------------------------------------ E-Mails

def _local_time(dt: datetime) -> str:
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("Europe/Zurich")).strftime("%d.%m.%Y %H.%M Uhr")
    except Exception:  # keine Zeitzonen-Daten im Image: dann UTC, ausdrücklich so benannt
        return dt.strftime("%d.%m.%Y %H.%M Uhr (UTC)")


def _sender(s: InquirySettings) -> str:
    return formataddr((VOCAB["brand"]["full"], s.mail_from or s.smtp_user))


def _internal_mail(inq: Inquiry, s: InquirySettings) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = _subject(inq)
    msg["From"] = _sender(s)
    msg["To"] = s.mail_to or VOCAB["email"]
    if inq.values["email"]:
        msg["Reply-To"] = formataddr((inq.values["name"], inq.values["email"]))
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain=(s.mail_from or s.smtp_user or "website").split("@")[-1])
    photos = f"Fotos: {len(inq.photos)} (im Anhang)" if inq.photos else "Fotos: keine"
    msg.set_content("\n".join([
        f"Neue Anfrage über die Website – Seite {inq.source}, Formular «{inq.form}».",
        "",
        _summary(inq, include_message_block=True),
        "",
        photos,
        f"Eingang: {_local_time(inq.received_at)}",
        f"Anfrage-Nr.: {inq.id}",
    ]))
    for p in inq.photos:
        maintype, subtype = p.content_type.split("/", 1)
        msg.add_attachment(p.data, maintype=maintype, subtype=subtype, filename=p.filename)
    record = json.dumps(as_record(inq), ensure_ascii=False, indent=2).encode("utf-8")
    msg.add_attachment(record, maintype="application", subtype="json", filename="anfrage.json")
    return msg


def _confirmation(inq: Inquiry, s: InquirySettings) -> EmailMessage:
    m = VOCAB["mail"]
    msg = EmailMessage()
    msg["Subject"] = m["confirmSubject"]
    msg["From"] = _sender(s)
    msg["To"] = formataddr((inq.values["name"], inq.values["email"]))
    msg["Reply-To"] = s.mail_to or VOCAB["email"]
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain=(s.mail_from or s.smtp_user or "website").split("@")[-1])
    urgent = inq.values["urgency"] == "dringend"
    body = [f"Guten Tag {inq.values['name']}", "", m["confirmIntro"], "", _summary(inq, include_message_block=True)]
    if inq.photos:
        body += ["", f"Fotos: {len(inq.photos)} übermittelt"]
    body += ["", m["confirmNext"]]
    if urgent and m.get("urgent"):
        body.append(m["urgent"])
    if urgent and m.get("urgentPikett"):
        body.append(m["urgentPikett"])
    body += ["", m["closing"], VOCAB["brand"]["full"], *VOCAB["address"],
             f"Telefon {VOCAB['phone']['display']}", VOCAB["email"]]
    msg.set_content("\n".join(body))
    return msg


def _smtp(s: InquirySettings) -> smtplib.SMTP:
    context = ssl.create_default_context()
    if s.smtp_ssl:
        return smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout, context=context)
    server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout)
    server.ehlo()
    if server.has_extn("starttls"):
        server.starttls(context=context)
        server.ehlo()
    return server


def _deliver(inq: Inquiry, s: InquirySettings) -> bool:
    """Schickt die Anfrage an uns (Pflicht) und die Bestätigung (Kür). Gibt zurück, ob die
    Bestätigung verschickt wurde. Scheitert die E-Mail an uns, fliegt die Ausnahme weiter."""
    with _smtp(s) as server:
        if s.smtp_user:
            server.login(s.smtp_user, s.smtp_password)
        server.send_message(_internal_mail(inq, s))
        if not (s.confirm and inq.values["email"]):
            return False
        try:
            server.send_message(_confirmation(inq, s))
            return True
        except (smtplib.SMTPException, OSError) as exc:
            print(f"WARNING: INQUIRY confirmation not sent id={inq.id}: {type(exc).__name__}: {exc}", flush=True)
            return False


# ------------------------------------------------------------------ Antworten

_PAGE_CSS = (
    "body{margin:0;font:17px/1.6 system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;color:#3A3A3D;"
    "background:#F4F3F0}main{max-width:640px;margin:0 auto;padding:48px 20px}"
    ".brand{font-weight:700;color:#0A0A0B;letter-spacing:-.02em;margin:0 0 32px}.brand span{font-weight:400;"
    "color:#6E6E73;margin-left:8px;font-size:.9em}h1{color:#0A0A0B;font-size:32px;line-height:1.15;"
    "letter-spacing:-.02em;margin:0 0 16px}ul{padding-left:1.2em}a{color:#0A0A0B}"
    ".btn{display:inline-block;margin:8px 12px 8px 0;padding:12px 20px;border:1px solid #0A0A0B;"
    "border-radius:2px;font-weight:600;text-decoration:none}.btn--red{background:#E51A14;border-color:#E51A14;"
    "color:#fff}.box{background:#fff;border:1px solid #D7D4CC;border-left:3px solid #E51A14;padding:20px 24px}"
)


def _page(title: str, body: str, status: int) -> HTMLResponse:
    phone = VOCAB["phone"]
    html = (
        '<!doctype html><html lang="de-CH"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        f"<title>{escape(title)} | {escape(VOCAB['brand']['full'])}</title><style>{_PAGE_CSS}</style></head>"
        f'<body><main><p class="brand">{escape(VOCAB["brand"]["name"])}<span>ehemals HS Steiner</span></p>'
        f"<h1>{escape(title)}</h1>{body}"
        f'<p>Telefon <a href="tel:{phone["e164"]}"><strong>{escape(phone["display"])}</strong></a></p>'
        "</main></body></html>"
    )
    return HTMLResponse(html, status_code=status)


def _invalid(errors: dict[str, str], inq: Inquiry | None, wants_json: bool) -> Response:
    message = "Bitte prüfen Sie die markierten Angaben."
    if wants_json:
        return JSONResponse({"ok": False, "message": message, "fields": errors}, status_code=422)
    items = "".join(f"<li>{escape(text)}</li>" for text in dict.fromkeys(errors.values()))
    back = escape(inq.source if inq else "/kontakt")
    body = (
        f'<div class="box"><p>Es fehlen noch Angaben:</p><ul>{items}</ul></div>'
        "<p>Mit der Zurück-Taste Ihres Browsers kommen Sie zum Formular – Ihre Eingaben sind noch da.</p>"
        f'<p><a class="btn" href="{back}">Zurück zum Formular</a></p>'
    )
    return _page("Es fehlen noch Angaben", body, 422)


def _failed(inq: Inquiry | None, status: int, message: str, wants_json: bool) -> Response:
    if wants_json:
        return JSONResponse({"ok": False, "message": message}, status_code=status)
    mailto = _mailto(inq) if inq else f"mailto:{VOCAB['email']}"
    body = (
        f'<div class="box"><p>{escape(message)}</p><p>Ihre Angaben sind nicht verloren: Rufen Sie uns an '
        "oder schicken Sie sie per E-Mail – der Text ist bereits vorbereitet.</p></div>"
        f'<p><a class="btn btn--red" href="tel:{VOCAB["phone"]["e164"]}">Anrufen</a>'
        f'<a class="btn" href="{escape(mailto)}">Per E-Mail senden</a></p>'
    )
    return _page("Das Senden hat nicht geklappt", body, status)


def _done(inq: Inquiry, wants_json: bool) -> Response:
    if wants_json:
        return JSONResponse({"ok": True, "id": inq.id})
    return RedirectResponse(VOCAB["pages"]["thanks"], status_code=303)


# ------------------------------------------------------------------ Endpunkt

@router.post("", summary="Anfrage der Website (Formular, multipart)")
async def submit_inquiry(request: Request) -> Response:
    wants_json = "application/json" in request.headers.get("accept", "")
    settings = InquirySettings()
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_BODY:
        limit = _mb(int(PHOTOS["maxTotalBytes"]))
        return _failed(None, 413, f"Die Anfrage ist zu gross – Fotos zusammen höchstens {limit}.", wants_json)
    try:
        form_data = await request.form(max_files=int(PHOTOS["max"]) + 5, max_fields=60)
    except Exception as exc:  # zu viele Teile, kaputtes multipart
        print(f"WARNING: INQUIRY unreadable form: {type(exc).__name__}: {exc}", flush=True)
        return _failed(None, 400, "Die Anfrage konnte nicht gelesen werden.", wants_json)

    ip = _client_ip(request)
    if _clean(form_data.get("hp")):  # Honigtopf: Menschen sehen das Feld nicht
        print(f"INFO: INQUIRY spam (honeypot) ip={ip}", flush=True)
        return JSONResponse({"ok": True}) if wants_json else RedirectResponse(VOCAB["pages"]["thanks"], 303)
    elapsed = _clean(form_data.get("t"))
    if elapsed.isdigit() and int(elapsed) < int(VOCAB["minSeconds"]) * 1000:
        print(f"INFO: INQUIRY too fast ({elapsed} ms) ip={ip}", flush=True)
        return _failed(None, 400, MSG["tooFast"], wants_json)

    errors: dict[str, str] = {}
    inq = await _parse(form_data, errors)
    if errors:
        return _invalid(errors, inq, wants_json)
    if not _allow(ip, settings.rate_limit):
        print(f"INFO: INQUIRY rate limited ip={ip}", flush=True)
        msg = f"Zu viele Anfragen in kurzer Zeit. Bitte rufen Sie uns an: {VOCAB['phone']['display']}."
        return _failed(inq, 429, msg, wants_json)
    return await _send(inq, settings, wants_json)


async def _send(inq: Inquiry, settings: InquirySettings, wants_json: bool) -> Response:
    record = as_record(inq)
    if not settings.smtp_host:
        print(f"ERROR: INQUIRY not sent (INQUIRY_SMTP_HOST fehlt) id={inq.id}", flush=True)
        print(f"INQUIRY_UNSENT {json.dumps(record, ensure_ascii=False)}", flush=True)
        return _failed(inq, 503, "Das Senden ist gerade nicht möglich.", wants_json)
    try:
        confirmed = await run_in_threadpool(_deliver, inq, settings)
    except (smtplib.SMTPException, OSError) as exc:
        print(f"ERROR: INQUIRY not sent id={inq.id}: {type(exc).__name__}: {exc}", flush=True)
        print(f"INQUIRY_UNSENT {json.dumps(record, ensure_ascii=False)}", flush=True)
        return _failed(inq, 503, "Das Senden ist gerade nicht möglich.", wants_json)
    print(
        f"INFO: INQUIRY sent id={inq.id} form={inq.form} kind={inq.values['kind']} "
        f"urgency={inq.values['urgency'] or '-'} photos={len(inq.photos)} confirmation={'ja' if confirmed else 'nein'}",
        flush=True,
    )
    return _done(inq, wants_json)
