from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class DocumentAcknowledgement(Base, TimestampMixin):
    """Bestätigung eines zu quittierenden Dokuments durch einen Nutzer (append-only).

    Ein Rechts-/Pflichtdokument (AGB, Datenschutz, Lieferantenvertrag …) ist versioniert:
    seine „Version" ist die **Objektnummer der gerade gültigen Dokument-Instanz** (aufgelöst
    über ``company_settings.legal_documents`` → ``services/legal.resolve``). Diese Zeile hält
    fest, **wer welche Version wann** akzeptiert hat – der wasserdichte Nachweis im Streitfall
    (CH DSG / DSGVO: «Zeitstempel + Version in DB»).

    Ein Nutzer gilt für eine ``kind`` als aktuell, wenn er eine Bestätigung für **genau die
    aktuell gültige** ``version_object_id`` besitzt; wird eine neue Fassung veröffentlicht
    (neue Instanz-Objektnummer), fehlt die Bestätigung wieder → das Consent-Gate greift.
    """

    __tablename__ = "document_acknowledgements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Wer hat bestätigt (UserProfile.id – interner PK, nicht die Objektnummer).
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # Welches Dokument (agb | datenschutz | … – frei, aus company_settings.legal_documents).
    kind: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    # Welche Fassung – die Objektnummer der akzeptierten Dokument-Instanz.
    version_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # created_at/updated_at/is_active kommen aus dem TimestampMixin.
