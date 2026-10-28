"""Kommunikation – Verlauf lesen, Nachricht anlegen, offene zählen (nur Personal)."""

from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.config import get_settings
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.communication import (ChannelOut, MailboxOut, MessageIn, MessageOut,
                                     SyncOut)
from ..services import communication as svc
from ..services import mailbox

router = APIRouter(prefix="/api/v1/erp/messages", tags=["communication"])
#: Die Rückkehr von Google – ohne Anmeldung (der Browser kommt von accounts.google.com);
#: wer da zurückkommt, sagt der signierte ``state``.
callback_router = APIRouter(prefix="/api/v1/mail", tags=["communication"])


@router.get("/channels", response_model=list[ChannelOut])
def list_channels(db: Session = Depends(get_db),
                  _: UserProfile = Depends(require_employee)):
    return svc.channels(db)


@router.get("/mailboxes", response_model=list[MailboxOut])
def mailboxes(company: Optional[int] = Query(None), db: Session = Depends(get_db),
              user: UserProfile = Depends(require_employee)):
    """Das Postfach dieser (eigenen) Gesellschaft – Adresse, Zustand, darf ich verbinden?
    Persönliche Postfächer gibt es nicht; ohne ``company`` ist die Liste leer."""
    return mailbox.status(db, user, company)


@router.post("/mailboxes/{channel}/connect")
def connect(channel: str, db: Session = Depends(get_db),
            user: UserProfile = Depends(require_employee)) -> dict[str, str]:
    """Die Adresse bei Google, an der die Zustimmung erteilt wird."""
    return {"url": mailbox.connect_url(db, channel, user)}


@router.delete("/mailboxes/{channel}", status_code=204)
def disconnect(channel: str, db: Session = Depends(get_db),
               user: UserProfile = Depends(require_employee)) -> None:
    mailbox.disconnect(db, channel, user)


@router.post("/sync", response_model=SyncOut)
def sync(db: Session = Depends(get_db), _: UserProfile = Depends(require_employee)):
    """Die Postfächer abgleichen und Fälliges senden (je Lauf höchstens 20 – so geht ein
    Rundschreiben nach und nach hinaus) – abgeglichen höchstens alle 30 Sekunden je
    Postfach. Ruft das ERP, solange es offen ist; ohne Anbindung ein No-op."""
    new, sent = mailbox.sync_all(db)
    return SyncOut(new=new, sent=sent)


@callback_router.get("/callback", include_in_schema=False)
def callback(code: str = "", state: str = "", error: str = "",
             db: Session = Depends(get_db)) -> RedirectResponse:
    problem = ("Die Verbindung wurde bei Google abgebrochen." if error or not code
               else mailbox.callback(db, code, state))
    query = urlencode({"mail": problem or "ok"})
    return RedirectResponse(f"{get_settings().frontend_base_url.rstrip('/')}/erp?{query}",
                            status_code=303)


# Die offenen Nachrichten je Person zählt ``GET /erp/todo`` mit (``services/todo``) – EINE
# Zahl am Symbol für alles, was zu tun ist.


@router.get("/{message_id}/attachments/{index}")
def attachment(message_id: int, index: int, db: Session = Depends(get_db),
               _: UserProfile = Depends(require_employee)) -> Response:
    """**Ein Anhang zum Öffnen im Entwurf** – die Datei, wie sie kam (``mailbox.attachment``).
    Ausgeliefert als Download in einem Sandkasten: angezeigt wird sie im Entwurf."""
    from urllib.parse import quote
    from ..models import Message
    msg = db.query(Message).filter(Message.id == message_id, Message.is_active.is_(True)).first()
    if msg is None:
        raise HTTPException(404, detail="Diese Nachricht gibt es nicht.")
    raw, mime, name = mailbox.attachment(db, msg, index)
    db.commit()     # ein erneuertes Zugangs-Token bleibt stehen
    return Response(content=raw, media_type=mime, headers={
        "Content-Security-Policy": "sandbox", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("", response_model=list[MessageOut])
def history(
    person: Optional[int] = Query(None),
    company: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Der Verlauf einer Person oder aller Personen einer Firma – chronologisch."""
    if not person and not company:
        raise HTTPException(400, detail="Person oder Firma angeben.")
    return svc.history(db, person=person, company=company)


@router.post("", response_model=MessageOut)
def create(
    data: MessageIn,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    msg = svc.create(db, data, user)
    db.commit()
    return next(m for m in svc.load(db, [msg.id]))
