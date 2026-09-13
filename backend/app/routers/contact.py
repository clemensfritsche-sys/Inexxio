from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/api/v1/contact", tags=["contact"])


# FIX: Der öffentliche Endpoint nahm unbegrenzt lange Strings an (Log-/Memory-Spam per
# Multi-MB-POST). Grosszügige, aber harte Obergrenzen je Feld.
class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    subject: str = Field(min_length=1, max_length=300)
    message: str = Field(min_length=1, max_length=5000)


@router.post("")
async def send_contact(data: ContactRequest):
    # TODO Phase 2: send via Gmail API (info.inexxio@gmail.com)
    print(f"[CONTACT] {data.subject} — {data.name} <{data.email}>\n{data.message}", flush=True)
    return {"ok": True}
