from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/api/v1/contact", tags=["contact"])


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    subject: str
    message: str


@router.post("")
async def send_contact(data: ContactRequest):
    # TODO Phase 2: send via Gmail API (info.inexxio@gmail.com)
    print(f"[CONTACT] {data.subject} — {data.name} <{data.email}>\n{data.message}")
    return {"ok": True}
