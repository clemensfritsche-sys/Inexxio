from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class ArticleProcessStep(Base, TimestampMixin):
    """Definition eines Prozessschritts am Artikel (Reiter «Prozess»).

    Unterstützte Typen (``step_type``): ``purchase`` (Beschaffung),
    ``inspection`` (Datenerfassung), ``movement`` (Bewegung). Die Reihenfolge
    bestimmt ``position`` (pro Artikel frei sortierbar); welche Schritte
    vorhanden sind, ist pro Artikel optional. Die Bestands-Instanzen entstehen
    bereits bei der Auftragsfreigabe (kein eigener Serialisierungs-Schritt).
    Kind-Objekt des Artikels – KEINE eigene Objektnummer.

    Wird ein Auftrag freigegeben, instanziiert das System aus diesen Schritten
    den Prozess (siehe ``services/process.py``).
    """

    __tablename__ = "article_process_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Ein Schritt gehört ENTWEDER zum Prozess eines Artikels (``article_id``, das
    # «wie es entsteht») ODER zum individuellen Prozess eines Auftrags (``order_id``,
    # auf bereits vorhandene Instanzen). Genau eines der beiden ist gesetzt – es gibt
    # kein eigenständiges Prozess-Objekt mehr.
    article_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    order_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    step_type: Mapped[str] = mapped_column(String(30), default="purchase", nullable=False)

    # Alt-Bestand: früher automatisch gesäte Begleit-Bewegung (Wareneingang / Versand zum
    # Kunden). Das System legt **keine** Prozessschritte mehr an – physisch nötige Transporte
    # entstehen zur Laufzeit als Bereitstellungs-Unter-Auftrag (services/provisioning.py).
    # Bestehende Begleiter behalten ihre Fachwirkung: festes Versand-Ziel und Ausnahme von
    # der Fehlmengen-Prüfung (``provisioning.is_companion``).
    companion: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # Konfiguration «purchase»
    mode: Mapped[str] = mapped_column(String(20), default="supplier", nullable=False)  # supplier | webshop
    supplier_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    webshop_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Welche Artikel-Stammdaten der Lieferant sehen darf (Pflichtfelder immer).
    shared_fields: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Konfiguration «inspection» (Datenerfassung): Stichproben-Prüfumfang in % der
    # Menge + Erfassungsfelder (Soll-Ist mit Toleranz, Gut/Schlecht, Text).
    sample_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capture_fields: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    # «Freigabe/Unterschrift»: eine Person quittiert die Datenerfassung mit digitaler
    # Unterschrift (als Bild). Optional auf bestimmte Personen (Objektnummern) beschränkt –
    # leer/NULL = jede eingeloggte Person darf unterschreiben (wird protokolliert).
    require_signature: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False)
    signer_ids: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    # «Bilderfassung»: genau EIN Foto je Schritt; die Anweisung beschreibt, was zu fotografieren ist.
    require_photo: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False)
    photo_instruction: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    # Konfiguration «movement» (Bewegung): optionales Vorgabe-Ziel. Beides NULL =
    # der Lagerist entscheidet beim Ausführen frei je Instanz.
    target_location_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    target_location_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # Transport-Modus der Bewegung (ADR 005, deklarierter Default; per Auftrag über
    # ``shipments.transport_mode`` übersteuerbar): 'auto' (abgeleitet: extern → Versand) |
    # 'carrier' (immer Versand) | 'self' (Selbsttransport, kein Carrier) | 'none' (nie Versand).
    transport_mode: Mapped[str] = mapped_column(
        String(10), default="auto", server_default="auto", nullable=False)

    # Konfiguration «resource» (Ressource): Liste der benötigten Ressourcen je
    # Operation – [{article_id, quantity, mode}], mode ∈ consume | tool.
    resource_lines: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Konfiguration «document» (Dokument). Der INHALT wird erst im Auftrag verfasst; am
    # Schritt wird die **Freigabe-/Anerkennungs-Struktur** deklariert (was für ALLE
    # Ausfertigungen dieses Dokuments gilt):
    #  • ``doc_signers`` – die endliche, geordnete Liste der **Freigabe-Parteien**
    #    ([{"signer_object_id": Objektnr, "action": "confirm"|"sign"}]). Erst wenn ALLE
    #    signiert haben, ist das Dokument freigegeben (Auftrag abgeschlossen).
    #  • ``sign_sequential`` – müssen die Parteien der Reihe nach signieren (Drag&Drop-Ordnung)?
    #  • ``doc_audience`` – das offene **Anerkennungs-Publikum** des freigegebenen Dokuments
    #    (None | 'all' | 'roles' | 'persons'); blockiert den Auftrag NIE (rollierendes Gate).
    #  • ``doc_audience_roles`` / ``doc_audience_person_ids`` – Zielgruppe zum Publikum.
    #  • ``doc_visibility`` – Sichtbarkeit ('public' | 'internal' | 'confidential').
    doc_signers: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    sign_sequential: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False)
    doc_audience: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    doc_audience_roles: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    doc_audience_person_ids: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    doc_visibility: Mapped[str] = mapped_column(
        String(16), default="internal", server_default="internal", nullable=False)

