from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..domain import statuses as st
from .base import TimestampMixin


class Article(Base, TimestampMixin):
    """Stammdaten-Datensatz für einen Artikel (Phase 2 – Produktion).

    **«Ausser Betrieb» ist keine eigene Angabe** (Testnotiz #773). Ein Artikel wird nicht
    versioniert, er wird **ersetzt** – und wer abgelöst ist, erzeugt nichts Neues mehr.
    Das ist keine zweite Wirkung des Ersetzens, sondern seine Bedeutung; also gibt es
    dafür auch keine zweite Spalte, keinen Schalter und keinen Endpunkt. Der Zustand ist
    die **Projektion** von ``replaced_by_id`` (siehe ``status``).

    *Vorher stand er als Spalte daneben, und das war genau die Falle, aus der schon
    einmal ein Fehler kam:* zwei Angaben über dieselbe Sache, von denen die eine gesetzt
    wurde und die andere gelesen – und sie konnten auseinanderlaufen, ohne dass es jemand
    merkte (ein von Hand inaktiv gesetzter Artikel ohne Nachfolger war für immer
    stillgelegt, denn den Weg zurück gab es nur über denselben Schalter).

    **``is_active`` ist etwas anderes** und bleibt: der **Soft-Delete** («den Datensatz
    gibt es nicht»). Er wird im Prozessbereich nirgends gesetzt und ist von aussen nicht
    setzbar – zwei Achsen, die beide «aktiv» heissen, waren einmal die Ursache dafür,
    dass eine Freigabe-Prüfung gar nichts abweisen konnte.
    """

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )

    # **Die Spalte ``status`` ist entfallen** (Testnotiz #773, Migration ``121``). Sie war
    # die zweite Aussage über dieselbe Sache; jetzt gibt es nur noch ``replaced_by_id``,
    # und der Zustand fällt daraus heraus – siehe die Eigenschaft ``status`` unten. Nach
    # der Zwei-Deploy-Regel verliert sie in ``121`` erst ihre ``NOT NULL``-Sperre und
    # fällt im Folge-Deploy (die Vorgänger-Revision schreibt sie währenddessen noch).

    # Versionsstempel des **Erzeugungsprozesses** (``article_process_steps``). Er zählt
    # bei jeder Änderung der Vorlage hoch und wird auf die Kopie im Auftrag geschrieben.
    # Damit ist an einem laufenden Auftrag ablesbar, welchen Stand er fährt – und eine
    # spätere Artikeländerung kann ihn nicht rückwirkend umschreiben (PROCESS_CORE.md §6.4).
    process_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )

    # Stammdaten. Pflicht ist einzig der **Name**; Einheit/Serialisierung tragen einen
    # Default (Stk / unit), Grösse & Gewicht sind optional (physische Attribute, die z. B.
    # ein Dokument-Artikel nicht braucht). Es gibt KEINE Typ-Unterscheidung physisch/nicht-
    # physisch mehr: ob ein Dokument entsteht, entscheidet allein der Prozessschritt «document».
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), default="Stk", server_default="Stk", nullable=False)  # Stk | m | kg | l
    serialization: Mapped[str] = mapped_column(String(20), default="unit", server_default="unit", nullable=False)  # unit | batch
    size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # z. B. 3x40x600 (optional)
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)  # optional

    # Optionale Stammdaten – nur bei Bedarf gepflegt (dynamische Feldliste im UI).
    material: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cad_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # CAD-Link
    surface: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Oberfläche
    min_order_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)  # MOQ
    safety_stock: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)  # Sicherheitsbestand
    supplier_article_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Lieferanten-Artikelnummer
    # Gefahrgut: ein Spezifikationsfeld wie jedes andere – es reist mit dem
    # Beschaffungs-Beleg zum Lieferanten (``services/article_fields``), damit er weiss,
    # was er in die Hand nimmt.
    is_hazmat: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # Die frühere Erfassungsmaske am Artikel (``capture_fields``) ist entfallen: was
    # erfasst wird, sagt das **Modul** im Prozess (``process_steps.config``). Am Artikel
    # war sie eine zweite Stelle für dieselbe Frage – und sie hing an keinem Prozess, man
    # konnte also an einem Stück erfassen, ohne dass es irgendwo davorstand.

    # Einstandspreis netto/Stück – read-only, aus dem zuletzt bestellten
    # Beschaffungs-Beleg automatisch zurückgeschrieben (``services/purchase``).
    landed_unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)

    # Ersetzen statt Versionierung: Objektnummer des Nachfolge-Artikels (alt → neu).
    replaced_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    @property
    def status(self) -> str:
        """►►► **Der fachliche Zustand — ABGELEITET, nicht gespeichert.** ◄◄◄

        ``Freigegeben``, solange dieser Artikel die neueste Fassung ist; ``Inaktiv``,
        sobald ein Nachfolger ihn abgelöst hat. Das ist die **ganze** Regel: ausser
        Betrieb geht ein Artikel dadurch, dass ein anderer seinen Platz einnimmt.

        Als Spalte war es die zweite Wahrheit neben ``replaced_by_id`` – und die zweite
        ist die, die man beim nächsten Schreibpfad vergisst. Als Eigenschaft kann sie
        gar nicht abweichen; ``articles.may_create`` liest darum die **Tatsache**
        (``replaced_by_id``) und nicht dieses Wort.
        """
        return st.INAKTIV if self.replaced_by_id else st.FREIGEGEBEN
