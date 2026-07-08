from typing import Optional

from sqlalchemy import BigInteger, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Document(Base, TimestampMixin):
    """Ausführung des Prozessschritts «Dokument» – eine Fachzeile unter dem Auftrag.

    Das Dokument trägt **keine eigene Objektnummer**. Sein Liefergegenstand ist die
    **Instanz**, die der Auftrag erzeugt (wie bei jedem Erzeugungsauftrag): die
    **Instanz-Objektnummer IST die Dokumentennummer**, und das **Freigabedatum der Instanz**
    (``instances.released_at``) IST das Dokumentdatum. Verschiedene Ausfertigungen = verschiedene
    Aufträge/Instanzen mit eigenen Nummern (statt einer Revisions-/Versionsnummer).

    Der Inhalt (``content``) wird – anders als früher – **während der Auftragsausführung**
    an diesem Schritt verfasst (nicht am Artikel vorlagt) und mit «Ausstellen» (``done``)
    festgeschrieben. Analog zur Datenerfassung (``Inspection``): erst mit dem Abschluss ist
    der Schritt erledigt.

    ``content``-Struktur (bewusst schlank, „Word"-artige Textdokumente):
        {"title": str, "subtitle": str|None, "sections": [{"heading": str, "body": str}]}
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Herkunft: unter welchem Auftrag / aus welcher Schritt-Definition (bei Mehrpositionen: Artikel).
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    step_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    article_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    # Verfasster Inhalt (während der Ausführung) – Snapshot beim Ausstellen unveränderlich.
    content: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ZWEI Achsen (DocuSign-Prinzip): «ausgestellt» friert den Inhalt ein, «freigegeben»
    # setzt zusätzlich alle Freigabe-Parteien voraus.
    #  • ``issued`` – der Inhalt ist mit «Ausstellen» festgeschrieben (unveränderliche Basis).
    #    Ab hier laufen die Unterschriften/Bestätigungen (``document_signoffs``).
    #  • ``done`` – **vollständig freigegeben**: ausgestellt UND von ALLEN Freigabe-Parteien
    #    signiert (ohne Parteien fällt beides bei «Ausstellen» zusammen – rückwärtskompatibel).
    #    Erst ``done`` schliesst den Prozessschritt ab (``process._fact_status`` liest ``done``).
    issued: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # created_at/updated_at/is_active kommen aus dem TimestampMixin.
