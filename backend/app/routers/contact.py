"""Anfragen der öffentlichen Website (das EINE Anfrage-Formular auf /kontakt und am Ende jeder Seite).

►►► **Eine Anfrage ist eine Nachricht im ERP** (``services/inquiry``). ◄◄◄ Kein
Mailversand mehr, keine zweite Inbox: die Anfrage steht im Verlauf der anfragenden Person
(angelegt, wenn es sie nicht gibt), **offen**, im Postfach der Gesellschaft, die die
Website diesem Besucher zeigt (Land → Gesellschaft, sonst der Betreiber). Die Bestätigung
geht über dasselbe Postfach hinaus und beantwortet die Anfrage **nicht** – sie bleibt
offen, bis ein Mensch antwortet.

**Die Wörter kommen von der Website.** Welche Felder es gibt, wie sie heissen und welche
Fehlermeldungen erscheinen, steht in ``website/src/config`` und wird mit
``npm run export:erp`` nach ``app/assets/website_contact.json`` übertragen (die CI
prüft, dass die Datei aktuell ist). Formular im Browser und Server sagen damit garantiert
dasselbe. Telefon und E-Mail darin sind die **Vorgaben** der Website, nicht die des ERP:
sie tragen den Ausweg, der ohne Datenbank funktionieren muss (503-/429-Seite, mailto).

**Ohne JavaScript** schickt der Browser das Formular klassisch (multipart). Dann antwortet
der Endpunkt mit HTML: bei Erfolg ``303`` auf ``/kontakt/danke``, sonst eine schlichte Seite
mit den fehlenden Angaben bzw. mit Telefon und einem vorausgefüllten mailto-Link. Mit
``Accept: application/json`` (das Skript der Website) antwortet er mit JSON.

**Keine Anfrage geht still verloren.** Lässt sie sich nicht speichern, antwortet der
Endpunkt mit ``503`` – das Formular zeigt dann Telefon und den vorausgefüllten
mailto-Link –, und die Anfrage steht vollständig (ohne Fotos) im Log (``INQUIRY_UNSENT``).
Nie ein stilles «Danke».

**Spam erzeugt nichts**: Honigtopf, Mindestausfüllzeit und die Begrenzung je IP stehen
**vor** dem ersten Zugriff auf die Datenbank – keine Person, keine Nachricht.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from threading import Lock
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from ..core.database import get_db
from ..services import geoip, inquiry as svc

router = APIRouter(prefix="/api/v1/contact", tags=["contact"])

#: Das Vokabular der Website (generiert, siehe Moduldoku) – gelesen an EINER Stelle.
VOCAB: dict = svc.VOCAB
MSG: dict[str, str] = VOCAB["messages"]
LIMITS: dict[str, int] = VOCAB["limits"]
PHOTOS: dict = VOCAB["photos"]

#: Dieselben Ausdrücke wie im Browser (``website/src/config/inquiry.mjs`` → ``patterns``).
EMAIL_RE = re.compile(VOCAB["patterns"]["email"])
PHONE_RE = re.compile(VOCAB["patterns"]["phone"])
SOURCE_RE = re.compile(r"^/[a-z0-9/_-]{0,80}$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
#: Obergrenze der ganzen Anfrage: Fotos plus grosszügig Platz für die Textfelder.
MAX_BODY = int(PHOTOS["maxTotalBytes"]) + 1024 * 1024
WINDOW_SECONDS = 3600
#: Gesendete Anfragen je IP-Adresse und Stunde.
RATE_LIMIT = 5


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
    data: bytes


@dataclass
class Inquiry:
    source: str
    values: dict[str, str]
    photos: list[Photo] = field(default_factory=list)
    newsletter: bool = False
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


def _check_fields(values: dict[str, str], errors: dict[str, str]) -> None:
    for name, limit in LIMITS.items():
        if name in values and len(values[name]) > limit:
            errors.setdefault(name, MSG["tooLong"].replace("{max}", str(limit)))
    if not values["message"]:
        errors.setdefault("message", MSG["message"])
    if not values["name"]:
        errors.setdefault("name", MSG["name"])
    phone, email = values["phone"], values["email"]
    # Die E-Mail ist Pflicht: über sie wird die Person gefunden (oder angelegt), und
    # dorthin gehen Bestätigung und Antwort. Das Telefon ist freiwillig.
    if not email:
        errors.setdefault("email", MSG["emailMissing"])
    if phone and not PHONE_RE.match(phone):
        errors.setdefault("phone", MSG["phone"])
    if email and not EMAIL_RE.match(email):
        errors.setdefault("email", MSG["email"])


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
        photos.append(Photo(filename=safe, data=data))
    if total > int(PHOTOS["maxTotalBytes"]):
        errors["photos"] = MSG["photosSize"].replace("{size}", _mb(total)).replace("{max}", _mb(int(PHOTOS["maxTotalBytes"])))
        return []
    return photos


FIELDS = ("message", "name", "company", "phone", "email")


async def _parse(form_data, errors: dict[str, str]) -> Inquiry:
    source = _clean(form_data.get("source")).lower()
    values = {name: _clean(form_data.get(name), multiline=(name == "message")) for name in FIELDS}
    _check_fields(values, errors)
    photos = await _read_photos(form_data.getlist("photos"), errors)
    return Inquiry(source=source if SOURCE_RE.match(source) else "/kontakt",
                   values=values, photos=photos, newsletter=bool(_clean(form_data.get("newsletter"))))


# ------------------------------------------------------------------ Darstellung

def _shown(inq: Inquiry) -> list[tuple[str, str, str]]:
    """(Feld, Beschriftung, Wert) in der Reihenfolge der Website, ohne Leeres."""
    return [(name, label, inq.values[name]) for name, label in VOCAB["labels"] if inq.values.get(name)]


def _mailto(inq: Inquiry) -> str:
    """Dieselbe Form wie der mailto-Link im Browser (scripts/form.ts) – und derselbe Betreff
    wie die Nachricht im ERP (``inquiry.subject_of``): die E-Mail landet im Postfach derselben
    Gesellschaft und soll dort unter demselben Anliegen stehen."""
    lines = [f"{label}: {value[:1200] if name == 'message' else value}" for name, label, value in _shown(inq)]
    body = "\n".join(lines)
    if inq.photos:
        n = len(inq.photos)
        body += f"\n\nDateien: bitte {'die Datei' if n == 1 else f'die {n} Dateien'} an diese E-Mail anhängen."
    subject = svc.subject_of(inq.values["message"])
    return f"mailto:{VOCAB['email']}?subject={quote(subject)}&body={quote(body)}"


def as_record(inq: Inquiry) -> dict:
    """Die Anfrage als JSON-Objekt (Schema siehe Moduldoku) – ohne Fotodaten."""
    v = inq.values
    return {
        "schema": "inexxio.website.inquiry/3",
        "id": inq.id,
        "received_at": inq.received_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": inq.source,
        "message": v["message"],
        "contact": {"name": v["name"], "company": v["company"] or None, "phone": v["phone"] or None,
                    "email": v["email"] or None},
        "photos": [{"filename": p.filename, "size": len(p.data)} for p in inq.photos],
    }


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
        f'<body><main><p class="brand">{escape(VOCAB["brand"]["name"])}<span>{escape(VOCAB["brand"]["formerly"])}</span></p>'
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
async def submit_inquiry(request: Request, db: Session = Depends(get_db)) -> Response:
    wants_json = "application/json" in request.headers.get("accept", "")
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_BODY:
        limit = _mb(int(PHOTOS["maxTotalBytes"]))
        return _failed(None, 413, f"Die Anfrage ist zu gross – Dateien zusammen höchstens {limit}.", wants_json)
    try:
        form_data = await request.form(max_files=int(PHOTOS["max"]) + 5, max_fields=60)
    except Exception as exc:  # zu viele Teile, kaputtes multipart
        print(f"WARNING: INQUIRY unreadable form: {type(exc).__name__}: {exc}", flush=True)
        return _failed(None, 400, "Die Anfrage konnte nicht gelesen werden.", wants_json)

    # Spam erzeugt nichts: alles hier steht VOR dem ersten Zugriff auf die Datenbank.
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
    if not _allow(ip, RATE_LIMIT):
        print(f"INFO: INQUIRY rate limited ip={ip}", flush=True)
        msg = f"Zu viele Anfragen in kurzer Zeit. Bitte rufen Sie uns an: {VOCAB['phone']['display']}."
        return _failed(inq, 429, msg, wants_json)
    country = geoip.country_of(geoip.client_ip(request.headers, request.client.host if request.client else None))
    return await run_in_threadpool(_store, db, inq, country, wants_json)


def _store(db: Session, inq: Inquiry, country: str | None, wants_json: bool) -> Response:
    """Ins ERP – und erst wenn das steht, «Danke». Scheitert es, sagt die Seite es mit
    Telefon und mailto; die Anfrage steht dann im Log."""
    v = inq.values
    data = svc.Inquiry(name=v["name"], email=v["email"].lower(), message=v["message"],
                       phone=v["phone"], company=v["company"], source=inq.source,
                       photos=[svc.Photo(p.filename, p.data) for p in inq.photos],
                       newsletter=inq.newsletter)
    try:
        msg = svc.record(db, data, country)
    except HTTPException as exc:  # ein Bild, das sich nicht lesen lässt
        db.rollback()
        name = inq.photos[0].filename if len(inq.photos) == 1 else "Eine der Dateien"
        return _invalid({"photos": MSG["photosType"].replace("{name}", name)}, inq, wants_json) \
            if exc.status_code in (400, 413) else _unsent(db, inq, exc, wants_json)
    except Exception as exc:
        return _unsent(db, inq, exc, wants_json)
    confirmed = _confirm(db, msg, data)
    print(f"INFO: INQUIRY stored id={inq.id} message={msg.id} channel={msg.channel} "
          f"photos={len(inq.photos)} confirmation={'ja' if confirmed else 'nein'}", flush=True)
    return _done(inq, wants_json)


def _confirm(db: Session, msg, inq: svc.Inquiry) -> bool:
    """Die Bestätigung ist Kür: gespeichert ist die Anfrage schon. Was hier scheitert,
    steht im Log – und eine angelegte Bestätigung holt der nächste Abgleich nach."""
    m = VOCAB["mail"]
    try:
        return svc.confirm(db, msg, inq, m)
    except Exception as exc:
        db.rollback()
        print(f"WARNING: INQUIRY confirmation not sent message={msg.id}: {type(exc).__name__}: {exc}", flush=True)
        return False


def _unsent(db: Session, inq: Inquiry, exc: Exception, wants_json: bool) -> Response:
    db.rollback()
    print(f"ERROR: INQUIRY not stored id={inq.id}: {type(exc).__name__}: {exc}", flush=True)
    print(f"INQUIRY_UNSENT {json.dumps(as_record(inq), ensure_ascii=False)}", flush=True)
    return _failed(inq, 503, "Das Senden ist gerade nicht möglich.", wants_json)
