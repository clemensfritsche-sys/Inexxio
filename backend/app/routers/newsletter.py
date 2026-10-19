"""Newsletter – anmelden, bestätigen, abmelden (``services/newsletter``).

Drei Türen, ein Dienst:

* **Öffentlich** (``/api/v1/newsletter``): die Anmeldung von der Website (E-Mail → Bitte um
  Bestätigung), der Bestätigungslink und der Abmeldelink. Ohne JavaScript: Formular und
  Weiterleitung auf eine Seite der Website.
* **Selbst** (``/api/v1/auth/me/newsletter``): der Schalter im Konto – die Adresse ist dort
  bestätigt, ein zweiter Klick wäre keiner mehr.
* **ERP** (``/api/v1/erp/newsletter``): Zustand und Nachweis einer Person, Einladung
  verschicken, abmelden. **Anmelden kann das ERP niemanden** – zustimmen muss die Person
  selbst; das ERP schickt ihr die Bitte.

Der Abmeldelink in der Mail zeigt einen Knopf, statt sofort abzumelden: Link-Scanner der
Mailprogramme rufen Links auf, ohne dass jemand klickt. Die Abmeldung mit einem Klick im
Mailprogramm selbst (``List-Unsubscribe-Post``, RFC 8058) geht direkt.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from html import escape
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, require_employee
from ..core.database import get_db
from ..domain import newsletter as dn
from ..models import UserProfile
from ..schemas.communication import PersonRef
from ..schemas.newsletter import ConsentRow, NewsletterIn, NewsletterState
from ..services import geoip, mailbox, newsletter as svc
from ..services.people import normalize_email
from .contact import EMAIL_RE, VOCAB, _allow, _clean, _client_ip, _page

router = APIRouter(prefix=svc.API, tags=["newsletter"])
me_router = APIRouter(prefix="/api/v1/auth/me/newsletter", tags=["newsletter"])
erp_router = APIRouter(prefix="/api/v1/erp/newsletter", tags=["newsletter"])

W = svc.WORDS
#: Die Seiten der Website nach einem Schritt (``website/src/pages/newsletter``).
PAGES = {"pending": "/newsletter/danke", "confirmed": "/newsletter/bestaetigt",
         "unsubscribed": "/newsletter/abgemeldet"}
RATE_LIMIT = 5


def _state(db: Session, oid: int, *, full: bool = False) -> NewsletterState:
    rows = svc.history(db, oid)
    now = rows[0] if rows else None
    return NewsletterState(
        subscribed=bool(now and now.subscribed), since=now.at if now else None,
        source=dn.SOURCES.get(now.source, now.source) if now else None, wording=svc.WORDING,
        history=[ConsentRow(subscribed=r.subscribed, source=dn.SOURCES.get(r.source, r.source),
                            at=r.at, wording=r.wording) for r in rows] if full else [])


def _invalid(message: str, status: int = 400) -> Response:
    return _page(message, '<p><a class="btn" href="/newsletter">Neu anmelden</a></p>', status)


# ── Öffentlich ──────────────────────────────────────────────────────────────

@router.post("", summary="Anmeldung von der Website (E-Mail → Bitte um Bestätigung)")
async def subscribe(request: Request, db: Session = Depends(get_db)) -> Response:
    """Wie das Anfrage-Formular: Honigtopf und Begrenzung je IP vor der Datenbank. Dann die
    Person zur Adresse (angelegt, wenn es sie nicht gibt) und die Bitte um Bestätigung –
    angemeldet ist erst, wer darin klickt."""
    wants_json = "application/json" in request.headers.get("accept", "")
    form = await request.form(max_fields=10)
    done = (JSONResponse({"ok": True}) if wants_json
            else RedirectResponse(PAGES["pending"], status_code=303))
    if _clean(form.get("hp")):
        return done
    email = normalize_email(_clean(form.get("email")))
    if not email or not EMAIL_RE.match(email) or len(email) > 160:
        msg = VOCAB["messages"]["email"]
        return (JSONResponse({"ok": False, "message": msg}, status_code=422) if wants_json
                else _page(msg, "<p>Mit der Zurück-Taste kommen Sie zum Formular.</p>", 422))
    if not _allow(f"newsletter:{_client_ip(request)}", RATE_LIMIT):
        msg = "Zu viele Anmeldungen in kurzer Zeit – bitte später noch einmal."
        return JSONResponse({"ok": False, "message": msg}, 429) if wants_json else _page(msg, "", 429)
    country = geoip.country_of(geoip.client_ip(request.headers,
                                               request.client.host if request.client else None))
    oid = mailbox.person_for(db, "", email)
    db.commit()
    if oid in svc.subscribed(db, [oid]):
        return done
    try:
        svc.invite(db, oid, "website", svc.sending_channel(db, country))
    except HTTPException as exc:
        db.rollback()
        print(f"WARNING: NEWSLETTER invite failed person={oid}: {exc.detail}", flush=True)
        msg = "Die Anmeldung ist gerade nicht möglich – bitte später noch einmal."
        return JSONResponse({"ok": False, "message": msg}, 503) if wants_json else _page(msg, "", 503)
    return done


@router.api_route("/confirm", methods=["GET", "POST"], include_in_schema=False)
def confirm(t: str = "", db: Session = Depends(get_db)) -> Response:
    """Der Klick in der Bitte um Bestätigung – angemeldet, mit Quelle und Wortlaut."""
    try:
        oid, source = svc.read(t, "confirm")
    except ValueError as exc:
        return _invalid(str(exc))
    svc.set_state(db, oid, True, source if source in dn.SOURCES else "website")
    db.commit()
    return RedirectResponse(PAGES["confirmed"], status_code=303)


@router.get("/unsubscribe", include_in_schema=False)
def unsubscribe_page(t: str = "") -> Response:
    """Ein Knopf statt sofortiger Abmeldung – ein Link-Scanner drückt keinen Knopf."""
    try:
        svc.read(t, "unsubscribe")
    except ValueError as exc:
        return _invalid(str(exc))
    body = (f'<p>{escape(W["unsubscribeLead"])}</p><form method="post" '
            f'action="{svc.API}/unsubscribe?t={escape(t)}"><button class="btn btn--red" '
            f'type="submit">{escape(W["unsubscribeButton"])}</button></form>')
    return _page(W["unsubscribeTitle"], body, 200)


@router.post("/unsubscribe", include_in_schema=False)
async def unsubscribe(request: Request, t: str = "", db: Session = Depends(get_db)) -> Response:
    """Abmelden – vom Knopf der Seite oder mit einem Klick im Mailprogramm (RFC 8058)."""
    try:
        oid, _ = svc.read(t, "unsubscribe")
    except ValueError as exc:
        return _invalid(str(exc))
    one_click = "List-Unsubscribe=One-Click" in (await request.body()).decode("utf-8", "ignore")
    svc.set_state(db, oid, False, "one_click" if one_click else "link")
    db.commit()
    return Response(status_code=200) if one_click else RedirectResponse(
        PAGES["unsubscribed"], status_code=303)


# ── Selbst ──────────────────────────────────────────────────────────────────

@me_router.get("", response_model=NewsletterState)
def my_state(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return _state(db, user.object_id) if user.object_id else NewsletterState(
        subscribed=False, wording=svc.WORDING)


@me_router.put("", response_model=NewsletterState)
def set_mine(data: NewsletterIn, db: Session = Depends(get_db),
             user: UserProfile = Depends(get_current_user)):
    if not user.object_id:
        raise HTTPException(400, detail="Ohne Objektnummer gibt es keinen Newsletter.")
    svc.set_state(db, user.object_id, data.subscribed, "account", user.id)
    db.commit()
    return _state(db, user.object_id)


# ── ERP ─────────────────────────────────────────────────────────────────────

@erp_router.get("/subscribers", response_model=list[PersonRef])
def subscribers(db: Session = Depends(get_db), _: UserProfile = Depends(require_employee)):
    """Alle Angemeldeten – die Empfänger eines Newsletters."""
    return [PersonRef(object_id=u.object_id, name=u.display_name, email=u.email)
            for u in svc.subscribers(db)]


@erp_router.get("/{object_id}", response_model=NewsletterState)
def person_state(object_id: int, db: Session = Depends(get_db),
                 _: UserProfile = Depends(require_employee)):
    return _state(db, object_id, full=True)


@erp_router.post("/{object_id}/invite", response_model=NewsletterState)
def invite(object_id: int, db: Session = Depends(get_db),
           _: UserProfile = Depends(require_employee)):
    """Die Bitte um Bestätigung schicken – angemeldet ist die Person erst mit ihrem Klick."""
    svc.invite(db, object_id, "invitation")
    return _state(db, object_id, full=True)


@erp_router.post("/{object_id}/unsubscribe", response_model=NewsletterState)
def unsubscribe_person(object_id: int, db: Session = Depends(get_db),
                       user: UserProfile = Depends(require_employee)):
    """Abmelden im Namen der Person (sie hat es am Telefon gesagt) – mit Quelle «ERP»."""
    svc.set_state(db, object_id, False, "erp", user.id)
    db.commit()
    return _state(db, object_id, full=True)
