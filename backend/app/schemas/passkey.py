from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class PasskeyRegisterVerify(BaseModel):
    """Abschluss der Passkey-Registrierung – das vom Browser erzeugte Credential."""

    credential: dict[str, Any] = Field(..., description="PublicKeyCredential (attestation) aus dem Browser")
    device_name: Optional[str] = Field(None, max_length=80, description="Anzeigename ('iPhone', 'Laptop')")


class PasskeyLoginVerify(BaseModel):
    """Abschluss der passwortlosen Anmeldung – die vom Browser erzeugte Assertion."""

    credential: dict[str, Any] = Field(..., description="PublicKeyCredential (assertion) aus dem Browser")


class PasskeyLoginResult(BaseModel):
    """Erfolgreiche Passkey-Anmeldung → Firebase Custom Token für signInWithCustomToken."""

    firebase_token: str


class PasskeyResponse(BaseModel):
    """Ein registrierter Passkey (Auflistung/Verwaltung im Konto). Ohne Krypto-Material."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    backed_up: bool = False
    created_at: datetime
    last_used_at: Optional[datetime] = None
