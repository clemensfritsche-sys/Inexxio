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

from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from ..core.actor import public
from ..core.database import DB
from ..services import inquiry as svc, visitor
from ..domain.errors import Rejected
from ..core import report

router = APIRouter(prefix="/api/v1/contact", tags=["contact"])

#: Das Vokabular der Website (generiert, ``services/inquiry``) – gelesen an EINER Stelle.
VOCAB: dict = svc.VOCAB
MSG, PHOTOS = svc.MSG, svc.PHOTOS
Inquiry = svc.Inquiry
#: Obergrenze der ganzen Anfrage: Fotos plus grosszügig Platz für die Textfelder.
MAX_BODY = int(PHOTOS["maxTotalBytes"]) + 1024 * 1024
#: Gesendete Anfragen je Absender und Stunde (``services/visitor``).
RATE_LIMIT = 5


async def _files(uploads: list) -> list[tuple[str, bytes]]:
    """Die hochgeladenen Fotos als (Name, Bytes) – leere Felder zählen nicht."""
    found = [u for u in uploads if isinstance(u, UploadFile) and (u.filename or "").strip()]
    if len(found) > int(PHOTOS["max"]):      # nicht alle lesen – die Zahl allein ist der Fehler
        return [(u.filename, b"") for u in found]
    return [(u.filename, await u.read()) for u in found]


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


def page(title: str, body: str, status: int, lang: str = "de") -> HTMLResponse:
    """Die Antwortseite ohne JavaScript – in der Sprache der Seite, von der es kam."""
    phone = VOCAB["phone"]
    said = svc.words(lang)["server"]
    html = (
        f'<!doctype html><html lang="{escape(svc.lang_of(lang))}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        f"<title>{escape(title)} | {escape(VOCAB['brand']['full'])}</title><style>{_PAGE_CSS}</style></head>"
        f'<body><main><p class="brand">{escape(VOCAB["brand"]["name"])}<span>{escape(VOCAB["brand"]["formerly"])}</span></p>'
        f"<h1>{escape(title)}</h1>{body}"
        f'<p>{escape(said["phone"])} <a href="tel:{phone["e164"]}"><strong>{escape(phone["display"])}</strong></a></p>'
        "</main></body></html>"
    )
    return HTMLResponse(html, status_code=status)


def _invalid(errors: dict[str, str], inq: Inquiry | None, wants_json: bool, lang: str) -> Response:
    said = svc.words(lang)["server"]
    if wants_json:
        return JSONResponse({"ok": False, "message": said["check"], "fields": errors}, status_code=422)
    items = "".join(f"<li>{escape(text)}</li>" for text in dict.fromkeys(errors.values()))
    back = escape(inq.source if inq else svc.words(lang)["pages"]["thanks"].rsplit("/", 1)[0])
    body = (
        f'<div class="box"><p>{escape(said["missingLead"])}</p><ul>{items}</ul></div>'
        f'<p>{escape(said["back"])}</p>'
        f'<p><a class="btn" href="{back}">{escape(said["backButton"])}</a></p>'
    )
    return page(said["missingTitle"], body, 422, lang)


def _failed(inq: Inquiry | None, status: int, message: str, wants_json: bool, lang: str) -> Response:
    if wants_json:
        return JSONResponse({"ok": False, "message": message}, status_code=status)
    said = svc.words(lang)["server"]
    mailto = _mailto(inq) if inq else f"mailto:{VOCAB['email']}"
    body = (
        f'<div class="box"><p>{escape(message)}</p><p>{escape(said["failedText"])}</p></div>'
        f'<p><a class="btn btn--red" href="tel:{VOCAB["phone"]["e164"]}">{escape(said["call"])}</a>'
        f'<a class="btn" href="{escape(mailto)}">{escape(said["mail"])}</a></p>'
    )
    return page(said["failedTitle"], body, status, lang)


def _done(inq: Inquiry, wants_json: bool) -> Response:
    if wants_json:
        return JSONResponse({"ok": True, "id": inq.id})
    return RedirectResponse(svc.words(inq.lang)["pages"]["thanks"], status_code=303)


# ------------------------------------------------------------------ Endpunkt

@router.post("", summary="Anfrage der Website (Formular, multipart)", dependencies=[public("web")])
async def submit_inquiry(request: Request, db: Session = DB) -> Response:
    """Eine Anfrage von der Website – sie wird eine offene Nachricht im Postfach der Gesellschaft zum Land des Besuchers."""
    wants_json = "application/json" in request.headers.get("accept", "")
    # Die Sprache der Seite steht in der Adresse (`?lang=`) – so ist sie bekannt, bevor der Rumpf gelesen ist.
    lang = svc.lang_of(request.query_params.get("lang"))
    said = svc.words(lang)["server"]
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > MAX_BODY:
        limit = svc.mb(int(PHOTOS["maxTotalBytes"]))
        return _failed(None, 413, said["tooBig"].replace("{max}", limit), wants_json, lang)
    try:
        form_data = await request.form(max_files=int(PHOTOS["max"]) + 5, max_fields=60)
    except Exception as exc:  # zu viele Teile, kaputtes multipart
        report.warn(f"INQUIRY unreadable form: {type(exc).__name__}: {exc}")
        return _failed(None, 400, said["unreadable"], wants_json, lang)

    # Spam erzeugt nichts: alles hier steht VOR dem ersten Zugriff auf die Datenbank.
    ip = visitor.sender_key(request)
    if svc.clean(form_data.get("hp")):  # Honigtopf: Menschen sehen das Feld nicht
        report.info(f"INQUIRY spam (honeypot) ip={ip}")
        return JSONResponse({"ok": True}) if wants_json else RedirectResponse(svc.words(lang)["pages"]["thanks"], 303)
    elapsed = svc.clean(form_data.get("t"))
    if elapsed.isdigit() and int(elapsed) < int(VOCAB["minSeconds"]) * 1000:
        report.info(f"INQUIRY too fast ({elapsed} ms) ip={ip}")
        return _failed(None, 400, svc.words(lang)["messages"]["tooFast"], wants_json, lang)

    inq, errors = svc.read(form_data, await _files(form_data.getlist("photos")), lang)
    if errors:
        return _invalid(errors, inq, wants_json, lang)
    if not visitor.allow_send("contact", request, RATE_LIMIT):
        report.info(f"INQUIRY rate limited ip={ip}")
        return _failed(inq, 429, said["tooMany"].replace("{phone}", VOCAB["phone"]["display"]), wants_json, lang)
    return await run_in_threadpool(_store, db, inq, visitor.country(request), wants_json)


def _store(db: Session, inq: Inquiry, country: str | None, wants_json: bool) -> Response:
    """Ins ERP – und erst wenn das steht, «Danke». Scheitert es, sagt die Seite es mit
    Telefon und mailto; die Anfrage steht dann im Log."""
    try:
        msg = svc.record(db, inq, country)
        db.flush()      # was beim Speichern scheitern kann, scheitert hier – vor dem «Danke»
    except Rejected as exc:  # ein Bild, das sich nicht lesen lässt
        db.rollback()
        name = inq.photos[0].filename if len(inq.photos) == 1 else "Eine der Dateien"
        return _invalid({"photos": svc.words(inq.lang)["messages"]["photosType"].replace("{name}", name)}, inq, wants_json, inq.lang) \
            if exc.status in (400, 413) else _unsent(db, inq, exc, wants_json)
    except Exception as exc:
        return _unsent(db, inq, exc, wants_json)
    confirmed = _confirm(db, msg, inq)
    report.info(f"INQUIRY stored id={inq.id} message={msg.id} channel={msg.channel} "
          f"photos={len(inq.photos)} confirmation={'ja' if confirmed else 'nein'}")
    return _done(inq, wants_json)


def _confirm(db: Session, msg, inq: Inquiry) -> bool:
    """Die Bestätigung ist Kür: gespeichert ist die Anfrage schon. Was hier scheitert,
    steht im Log – und eine angelegte Bestätigung holt der nächste Abgleich nach."""
    m = svc.words(inq.lang)["mail"]
    try:
        with db.begin_nested():     # scheitert sie, bleibt die Anfrage stehen
            return svc.confirm(db, msg, inq, m)
    except Exception as exc:
        report.warn(f"INQUIRY confirmation not sent message={msg.id}: {type(exc).__name__}: {exc}")
        return False


def _unsent(db: Session, inq: Inquiry, exc: Exception, wants_json: bool) -> Response:
    db.rollback()
    report.error(f"INQUIRY not stored id={inq.id}: {type(exc).__name__}: {exc}")
    # Die eine bewusste Ausnahme von «keine Personendaten in Meldungen»: die Anfrage steht sonst
    # nirgends – so lässt sie sich aus dem Log nachtragen.
    report.error("INQUIRY_UNSENT", inquiry=as_record(inq))
    return _failed(inq, 503, svc.words(inq.lang)["server"]["unavailable"], wants_json, inq.lang)
