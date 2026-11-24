"""Aussortierte Anfragen der Website (``services/spam``)."""

from datetime import datetime

from pydantic import BaseModel, Field


class HeldFile(BaseModel):
    name: str
    url: str


class HeldOut(BaseModel):
    """Eine aussortierte Anfrage – was die Person ins Formular schrieb, und warum die KI sie für
    Spam hält."""
    id: int = Field(description="Nummer der aussortierten Anfrage (Zeile im Log).")
    at: datetime
    company: int = Field(description="Objektnummer der eigenen Gesellschaft, die sie bekommen hätte.")
    name: str
    email: str
    phone: str = ""
    firm: str = Field("", description="Was im Feld «Firma» stand.")
    message: str
    source: str = Field("", description="Die Seite der Website, von der sie kam.")
    reason: str = Field("", description="Warum die KI sie für Spam hält.")
    files: list[HeldFile] = []


class ReleasedOut(BaseModel):
    message: int = Field(description="Nummer der angelegten Nachricht.")
