from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Instance(Base, TimestampMixin):
    """Bestandsobjekt – entsteht bei der **Auftragsfreigabe**.

    **Eine Instanz ist eine MENGE, kein Ding.** Sie trägt eine Objektnummer und eine
    ``quantity``; wie viel das ist, sagt allein diese Zahl. Aus der Artikel-Einstellung
    ``serialization`` folgt nur, wie die Menge bei der Entstehung aufgeteilt wird
    (``services/serialization.py`` – die EINZIGE Stelle, die den Unterschied kennt):

        unit  → je Stück eine eigene Instanz (quantity = 1, eigene Nummer)
        batch → eine Charge-Instanz mit quantity = Bestellmenge

    ``kind`` ist danach nur noch ein **Etikett** für die Anzeige, keine Regel: kein
    Fachmodul verzweigt darauf. Wer wissen will «wie viel», liest ``quantity`` – auch die
    Stichprobe (``inspection.sample_capacity``), der Bestand und die Reservierung.

    **Warum nicht N Zeilen à 1 Stück?** Die Frage kommt wieder, darum hier die Antwort:
      * Eine Charge darf **gebrochen** sein (2.5 kg, 0.75 m²) – «2.5 Zeilen» gibt es nicht.
        Genau dafür existiert ``batch``; ``unit`` erzwingt ganze Stück.
      * Die **Objektnummer ist systemweit eindeutig** (Unique-Index) und der Schlüssel für
        QR-Scan, ``references.object_references`` und ``locations.location_chain``. N Zeilen
        mit derselben Nummer bräuchten überall eine neue Antwort auf «welche davon?».
      * Eine 1000er-Charge wären 1000 Zeilen je Reservierung, FIFO-Zugriff und Umlagerung.
    Der Preis dafür ist die Teilmengen-Logik – und die steht an genau zwei Stellen
    (``services/reservation.py`` für «wer beansprucht wie viel», ``services/location_split.py``
    für «wo liegt wie viel»). Die daraus entstandene Fehlerklasse («Zeilen zählen statt
    Mengen summieren») bewacht ``tests/test_quantity_rules.py``.

    Trägt eine eigene 9-stellige Objektnummer (etikettier-/QR-fähig) und ist die
    Grundlage des Bestands. Entsteht unter einem Auftrag (``order_id``).
    """

    __tablename__ = "instances"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)

    article_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    kind: Mapped[str] = mapped_column(String(10), default="unit", nullable=False)   # unit | batch
    # Menge als Dezimalzahl (NUMERIC(14,3)): ein Einzelteil trägt 1, eine Charge die
    # Bestellmenge – für kg/m²/m³/l auch als **Bruchmenge** (2.5 kg, 0.75 m²), nicht nur
    # ganze Stück. Arithmetik ausschliesslich über ``services/quantity.py`` (exakt, kein float).
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=1, nullable=False)
    serial_number: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # ZWEI getrennte Achsen statt eines überladenen qc_status:
    #   quality     = QC-Verdikt:  pending | passed | blocked  («darf man es verwenden?»)
    #   disposition = Verbleib:     in_process | in_stock | consumed | sold | scrapped  («wo ist es?»)
    # Verbrauchbar/zählbar ist eine Instanz nur, wenn quality=passed UND disposition=in_stock.
    quality: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    disposition: Mapped[str] = mapped_column(String(20), default="in_process", nullable=False)
    # Zeitpunkt der Freigabe (disposition → in_stock). Basis für FIFO beim Verbrauch
    # (Ressource-Schritt): ältester Freigabe-Zeitpunkt zuerst.
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Standort – eine Instanz hat IMMER einen Standort (ab Freigabe: Lieferant bzw. Wareneingang).
    # Der Standort ist stets ein Datensatzobjekt mit Nummer:
    #   user → UserProfile | instance → andere Instanz (Behälter) | company → Unternehmen
    location_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    location_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    # **Standort-Verteilung** – exakt nach dem Vorbild von ``reservations`` (mengengenau,
    # OHNE Teilung der Instanz / ohne neue Objektnummer). Eine Charge von 1000 Schrauben
    # kann physisch auf mehrere Standorte verteilt sein (300 @ Band A, 700 @ Band B) und
    # trägt trotzdem EINE Objektnummer (die Teile sind alle mit ihr beschriftet). Die Map
    # ist nach **Objektnummer** des Ziels geschlüsselt (global eindeutig → «wer liegt hier?»
    # per has_key), Wert = {"t": <user|instance|company>, "q": <menge-string>}:
    #   locations = {"100000123": {"t": "instance", "q": "300"}, ...}   Summe = quantity.
    # Ist die Charge an EINEM Ort (Normalfall) → Map NULL, der Skalar ``location_*`` ist die
    # Wahrheit. Verteilt → die Map ist die Wahrheit, der Skalar spiegelt die grösste Teilmenge
    # (denormalisiert, wie ``reserved_for_order_id`` die Einzel-Reservierung spiegelt).
    # Einzige Schreibstelle: ``services/location_split.py``.
    locations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Reservierung – **mengengenau, ohne Teilung der Instanz** (die Objektnummer bleibt
    # IMMER erhalten – physisch sind die Teile mit dieser Nummer beschriftet):
    #   reservations      = {auftrag_db_id: menge}  – wer wie viel dieser Instanz beansprucht
    #   reserved_quantity = Summe der Reservierungen (denormalisiert, für SQL-Verfügbarkeit)
    # Frei verfügbar (für andere Aufträge) = quantity − reserved_quantity. Eine Charge von
    # 1000 Schrauben, von der 30 reserviert sind, bleibt also mit 970 frei verfügbar –
    # **ohne** dass eine zweite Instanz mit eigener Nummer entsteht.
    reservations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    reserved_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=0, server_default="0", nullable=False)

    # Einzel-Reservierungs-Zeiger (Altfeld / Schnellprüfung): gesetzt, solange genau EIN
    # Auftrag die Instanz (teil-)reserviert. Massgeblich ist die ``reservations``-Map.
    reserved_for_order_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)

    # **Subjekt** eines Bestands-Auftrags (Prozess-Quelle ``stock``: Verkauf/Entnahme):
    # die FIFO-ausgewählten Instanzen, auf die der Auftrag wirkt (≠ Komponenten-
    # Reservierung). Bei Abschluss verlassen sie den Bestand (sold/consumed).
    subject_of_order_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
