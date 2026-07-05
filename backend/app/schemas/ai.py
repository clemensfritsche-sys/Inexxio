from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Chat (Assistent) ──────────────────────────────────────────────────────────────

class AiChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class AiChatRequest(BaseModel):
    messages: list[AiChatMessage] = Field(max_length=40)
    # Optionaler UI-Kontext (Seitenname/Objektnummer aus UNSEREM Frontend).
    context: Optional[str] = Field(default=None, max_length=300)


class AiProposal(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action_type: str
    summary: str
    status: str
    target_object_id: Optional[int] = None
    decided_at: Optional[datetime] = None


class AiChatResponse(BaseModel):
    reply: str
    proposals: list[AiProposal] = []
    model: str


# ── Konfiguration (Frontend blendet den Assistenten danach ein/aus) ───────────────

class AiConfig(BaseModel):
    enabled: bool
    image_enabled: bool
    assistant_name: str = "Inexxio KI"


# ── Schreibhilfe (Dokumente-Prozessschrittmodul) ──────────────────────────────────

class AiDocSection(BaseModel):
    heading: str = ""
    body: str = ""


class AiDocContent(BaseModel):
    title: str = ""
    subtitle: Optional[str] = None
    sections: list[AiDocSection] = []


class AiWriteRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)
    content: Optional[AiDocContent] = None    # vorhandener Entwurf (wird weiterentwickelt)


class AiWriteResponse(BaseModel):
    content: AiDocContent


# ── Bildbearbeitung (Shop-Produktbilder, Gemini) ──────────────────────────────────

class AiImageEditRequest(BaseModel):
    # URL eines bestehenden Attachments (``/api/v1/attachments/{token}``).
    image_url: str = Field(min_length=1, max_length=500)
    instruction: str = Field(min_length=1, max_length=1000)


class AiImageEditResponse(BaseModel):
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
