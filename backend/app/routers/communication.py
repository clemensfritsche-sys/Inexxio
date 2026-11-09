"""Kommunikation – Nachricht anlegen, Postfächer, Abgleich (nur Personal)."""

from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.config import get_settings
from ..core.actor import public
from ..core.database import DB
from ..models import UserProfile
from ..schemas.communication import (ChannelOut, MailboxOut, MessageIn, MessageOut,
                                     SyncOut)
from ..services import communication as svc
from ..services import mailbox
from ..domain.errors import NotFound

router = APIRouter(prefix="/api/v1/erp/messages", tags=["communication"])
#: Die Rückkehr von Google – ohne Anmeldung (der Browser kommt von accounts.google.com);
#: wer da zurückkommt, sagt der signierte ``state``.
callback_router = APIRouter(prefix="/api/v1/mail", tags=["communication"])


@router.get("/channels", response_model=list[ChannelOut])
def list_channels(db: Session = DB,
                  _: UserProfile = Depends(require_employee)):
    """Die Kanäle, aus denen ich schreiben kann (Postfächer, Anruf, intern, Notiz)."""
    return svc.channels(db)


@router.get("/mailboxes", response_model=list[MailboxOut])
def mailboxes(company: Optional[int] = Query(None), db: Session = DB,
              user: UserProfile = Depends(require_employee)):
    """Das Postfach dieser (eigenen) Gesellschaft – Adresse, Zustand, darf ich verbinden?
    Persönliche Postfächer gibt es nicht; ohne ``company`` ist die Liste leer."""
    return mailbox.status(db, user, company)


@router.post("/mailboxes/{channel}/connect")
def connect(channel: str, db: Session = DB,
            user: UserProfile = Depends(require_employee)) -> dict[str, str]:
    """Die Adresse bei Google, an der die Zustimmung erteilt wird."""
    return {"url": mailbox.connect_url(db, channel, user)}


@router.delete("/mailboxes/{channel}", status_code=204)
def disconnect(channel: str, db: Session = DB,
               user: UserProfile = Depends(require_employee)) -> None:
    """Ein Postfach trennen – nur ein Admin; die Kontakt-E-Mail der Gesellschaft verschwindet mit."""
    mailbox.disconnect(db, channel, user)


@router.post("/sync", response_model=SyncOut)
def sync(db: Session = DB, _: UserProfile = Depends(require_employee)):
    """Die Postfächer abgleichen und Fälliges senden (je Lauf höchstens 20 – so geht ein
    Rundschreiben nach und nach hinaus) – abgeglichen höchstens alle 30 Sekunden je
    Postfach. Ruft das ERP, solange es offen ist; ohne Anbindung ein No-op. Ohne offenen
    Browser tut dasselbe der Takt (``services/tick``)."""
    new, sent = mailbox.sync_all(db)
    return SyncOut(new=new, sent=sent)


@callback_router.get("/callback", include_in_schema=False, dependencies=[public("link")])
def callback(code: str = "", state: str = "", error: str = "",
             db: Session = DB) -> RedirectResponse:
    """Rückkehr von Google nach der Zustimmung – verbindet das Postfach und führt zurück ins ERP."""
    problem = ("Die Verbindung wurde bei Google abgebrochen." if error or not code
               else mailbox.callback(db, code, state))
    query = urlencode({"mail": problem or "ok"})
    return RedirectResponse(f"{get_settings().frontend_base_url.rstrip('/')}/erp?{query}",
                            status_code=303)


# Die offenen Nachrichten je Person zählt ``GET /erp/todo`` mit (``services/todo``) – EINE
# Zahl am Symbol für alles, was zu tun ist.


@router.get("/{message_id}/attachments/{index}")
def attachment(message_id: int, index: int, db: Session = DB,
               _: UserProfile = Depends(require_employee)) -> Response:
    """**Ein Anhang zum Öffnen im Entwurf** – die Datei, wie sie kam (``mailbox.attachment``).
    Ausgeliefert als Download in einem Sandkasten: angezeigt wird sie im Entwurf."""
    from urllib.parse import quote
    from ..models import Message
    msg = db.query(Message).filter(Message.id == message_id, Message.is_active.is_(True)).first()
    if msg is None:
        raise NotFound("Diese Nachricht gibt es nicht.")
    raw, mime, name = mailbox.attachment(db, msg, index)
    db.flush()
    return Response(content=raw, media_type=mime, headers={
        "Content-Security-Policy": "sandbox", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


# Den Verlauf liest ``GET /erp/history/{object_id}`` (``services/history``) – EIN Verlauf
# für jeden Datensatz, in Seiten; Nachrichten sind ein Teil davon.


@router.post("", response_model=MessageOut)
def create(
    data: MessageIn,
    db: Session = DB,
    user: UserProfile = Depends(require_employee),
):
    """Eine Nachricht anlegen – Mail, Rundschreiben, Newsletter, Anruf, intern, Notiz oder Erinnerung; eine Mail geht nach dem Speichern hinaus."""
    msg = svc.create(db, data, user)
    db.flush()
    return next(m for m in svc.load(db, [msg.id]))
