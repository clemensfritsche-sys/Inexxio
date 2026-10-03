from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class WebAuthnCredential(Base, TimestampMixin):
    """Ein registrierter Passkey (FIDO2/WebAuthn-Credential) eines Benutzers.

    Die Anmeldung läuft passwortlos über den Authenticator des Geräts (Face/Touch ID,
    Windows Hello, Security-Key). Firebase kennt keinen nativen Passkey-Provider – die
    Zeremonie läuft hier im Backend, bei Erfolg wird ein Firebase **Custom Token**
    ausgestellt (``signInWithCustomToken``). So bleibt der bestehende Firebase-Session-
    Fluss (ID-Token → ``get_current_user``) unverändert.

    Ein Passkey ist an eine **RP-ID** (Domain) gebunden; sie wird beim Registrieren aus
    der Origin abgeleitet und hier festgehalten, damit die Anmeldung sie gegenprüfen kann.
    """

    __tablename__ = "webauthn_credentials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Wem gehört der Passkey (UserProfile.id – interner PK, nicht die Objektnummer).
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # Credential-ID (base64url) – vom Authenticator vergeben, global eindeutig.
    credential_id: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    # Öffentlicher Schlüssel (COSE-kodiert) – gegen ihn wird die Signatur geprüft.
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Signatur-Zähler (Klon-Erkennung): steigt bei jeder Anmeldung.
    sign_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    # An welche Domain der Passkey gebunden ist (aus der Origin beim Registrieren).
    rp_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # Transport-Hinweise (['internal','hybrid',…]) für schnellere Auswahl beim Login.
    transports: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    # Vom Nutzer vergebener Anzeigename ("iPhone", "Laptop").
    device_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    # 'singleDevice' | 'multiDevice' (synchronisierter Passkey) – informativ.
    device_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    backed_up: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # created_at/updated_at/is_active kommen aus dem TimestampMixin.


class WebAuthnChallenge(Base, TimestampMixin):
    """Kurzlebige Challenge einer laufenden WebAuthn-Zeremonie (Register/Login).

    WebAuthn ist ein Challenge-Response-Verfahren: der Server stellt eine zufällige
    Challenge aus, der Authenticator signiert sie. Die Challenge muss serverseitig
    gemerkt werden, um Replay zu verhindern – auf Cloud Run (mehrere Instanzen) darf
    das nicht im Prozessspeicher liegen, daher hier in der DB (Einmalgebrauch, mit
    Ablauf). Beim Verifizieren wird die aus der signierten ``clientDataJSON`` gelesene
    Challenge hier nachgeschlagen, geprüft und gelöscht.
    """

    __tablename__ = "webauthn_challenges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Die Challenge selbst (base64url) – Schlüssel für den Nachschlag beim Verifizieren.
    challenge: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # 'register' | 'authenticate'.
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    # Bei 'register' der Benutzer, für den registriert wird (bei 'authenticate' NULL –
    # Login ist usernamelos, der Benutzer ergibt sich aus dem verwendeten Credential).
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # created_at/updated_at/is_active kommen aus dem TimestampMixin.
