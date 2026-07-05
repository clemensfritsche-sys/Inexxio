"""KI-Endpunkte (ADR 004). Die KI handelt hier IMMER als Principal mit Delegation:
Attribution = KI-User, effektive Rechte = die angemeldete Person (``get_current_user``).
Ohne konfigurierten Provider antworten alle Endpunkte 503 – das ERP läuft normal."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.ai import (
    AiChatRequest, AiChatResponse, AiConfig, AiImageEditRequest, AiImageEditResponse,
    AiProposal, AiWriteRequest, AiWriteResponse,
)
from ..services import attachments as attachments_svc
from ..services.ai import actions as actions_svc
from ..services.ai import assistant, gateway
from ..services.ai.identity import ensure_ai_user
from ..services.ai.principal import AiPrincipal

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


def _principal(db: Session, user: UserProfile) -> AiPrincipal:
    return AiPrincipal(actor=ensure_ai_user(db), on_behalf_of=user)


def _unavailable(e: gateway.AiUnavailable) -> HTTPException:
    return HTTPException(503, detail=f"KI derzeit nicht verfügbar: {e}")


@router.get("/config", response_model=AiConfig)
async def ai_config(_: UserProfile = Depends(get_current_user)):
    """Verfügbarkeit für das Frontend (Assistent/Bild-Knöpfe ein-/ausblenden)."""
    return AiConfig(enabled=gateway.is_enabled(), image_enabled=gateway.image_enabled())


@router.post("/chat", response_model=AiChatResponse)
async def ai_chat(
    data: AiChatRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Rechte-geschützter Assistent – für ALLE Rollen (Kunde, Lieferant, Personal).
    Die Rolle bestimmt die Tool-Menge; das Daten-Scoping übernimmt die Service-Authz."""
    principal = _principal(db, user)
    try:
        result = assistant.run_chat(
            db, principal,
            [m.model_dump() for m in data.messages],
            context=data.context,
        )
    except gateway.AiUnavailable as e:
        raise _unavailable(e)
    return AiChatResponse(**result)


@router.post("/write", response_model=AiWriteResponse)
async def ai_write(
    data: AiWriteRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Schreibhilfe für das Dokumente-Prozessschrittmodul (nur Personal)."""
    principal = _principal(db, user)
    try:
        content = assistant.write_document(
            db, principal, data.instruction,
            data.content.model_dump() if data.content else None,
        )
    except gateway.AiUnavailable as e:
        raise _unavailable(e)
    return AiWriteResponse(content=content)


@router.post("/image-edit", response_model=AiImageEditResponse)
async def ai_image_edit(
    data: AiImageEditRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Shop-Produktbild mit Gemini bearbeiten (nur Personal). Das Ergebnis wird als
    NEUES Attachment gespeichert (Original bleibt unangetastet – reversibel)."""
    token = data.image_url.rstrip("/").split("/")[-1]
    att = attachments_svc.get_by_token(db, token)   # 404 wenn unbekannt
    principal = _principal(db, user)
    try:
        edited, _mime = gateway.edit_image(att.data, att.mime, data.instruction)
    except gateway.AiUnavailable as e:
        raise _unavailable(e)
    # store_image normalisiert (EXIF/Grösse/JPEG) – derselbe Pfad wie ein Upload.
    new_att = attachments_svc.store_image(db, edited, f"ki-{att.filename or 'bild'}.png", principal.actor.id)
    from ..services.events import emit
    emit(db, "ai.image_edited", object_type="attachment", object_id=None,
         payload={"source": token, "result": new_att.token,
                  "on_behalf_of": user.id},
         actor_id=principal.actor.id)
    db.commit()
    return AiImageEditResponse(
        url=attachments_svc.public_url(new_att), width=new_att.width, height=new_att.height,
    )


@router.post("/actions/{action_id}/confirm", response_model=AiProposal)
async def confirm_action(
    action_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Menschliches Freigabe-Gate: KI-Vorschlag bestätigen → autorisierter Pfad, einmalig."""
    return actions_svc.confirm(db, action_id, user)


@router.post("/actions/{action_id}/reject", response_model=AiProposal)
async def reject_action(
    action_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    return actions_svc.reject(db, action_id, user)
