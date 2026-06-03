from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/contact", tags=["contact"])


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    message: str


@router.post("/")
async def send_contact(data: ContactRequest):
    # Phase 1: Log to stdout; Phase 2: send via Gmail API
    print(f"[CONTACT] From: {data.name} <{data.email}>\n{data.message}")
    return {"ok": True}
