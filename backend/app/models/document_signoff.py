from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class DocumentSignoff(Base, TimestampMixin):
    """Eine **Freigabe-Partei** eines Dokuments (append-only Unterschriften-/Bestätigungs-Layer).

    Prinzip (wie DocuSign): der Dokument-Inhalt wird bei «Ausstellen» **eingefroren**
    (unveränderliche Basis), die Zustimmungen liegen als **separater Layer** darüber. Genau
    EINE Tabelle für beide Aktionen: ``confirm`` (bestätigen, ohne Bild) und ``sign``
    (unterschreiben, mit Unterschrift-Bild). Erst wenn **alle** Freigabe-Parteien signiert
    haben, wird das Dokument (die Instanz) freigegeben und der Auftrag abgeschlossen.

    Abgrenzung: das ist die **endliche** Partei-Liste (namentlich, terminiert – gated den
    Auftragsabschluss). Das offene **Anerkennungs-Publikum** (alle/Rolle) ist dagegen ein
    rollierendes, aktions-getriggertes Gate auf dem BEREITS freigegebenen Dokument
    (``document_acknowledgements``) und blockiert den Auftrag NIE.

    Ein Signoff wird bei «Ausstellen» aus der Schritt-Deklaration (``doc_signers``) erzeugt;
    die zu unterschreibende Person wird über ihre **Objektnummer** (``signer_object_id``)
    referenziert (universeller Schlüssel, konsistent zu ``inspection.signer_ids``).
    """

    __tablename__ = "document_signoffs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Fachzeile (Dokument) + Auftrag (denormalisiert für Abfragen).
    document_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    # Wer unterschreiben/bestätigen muss – Objektnummer der Person (universeller Schlüssel).
    signer_object_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    # Verlangte Aktion: 'confirm' (bestätigen, ohne Bild) | 'sign' (unterschreiben, mit Bild).
    action: Mapped[str] = mapped_column(String(10), default="sign", nullable=False)
    # Reihenfolge (sequenzielles Signieren, Drag&Drop-Liste am Schritt).
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    # Zustand dieser Partei: pending → signed | rejected. Zurücknehmen (withdraw) setzt → pending.
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending", nullable=False)
    signature_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)  # Bild (action=sign)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)          # Ablehnungsgrund
    acted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    acted_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)         # UserProfile.id

    # created_at/updated_at/is_active kommen aus dem TimestampMixin.
