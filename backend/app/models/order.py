from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Order(Base, TimestampMixin):
    """Auftrag – ein ERP-Datensatz mit eigener Objektnummer.

    **Bewusst leer.** Der Auftrag trägt heute nichts ausser seiner Identität: welche
    Angaben er führt, hängt an der Prozesslogik, und die wird als Nächstes entworfen.
    Felder auf Vorrat anzulegen hiesse, sie jetzt zu erfinden – und eine erfundene Spalte
    ist schwerer wieder loszuwerden als eine fehlende hinzuzufügen.

    Was er hat, hat er aus der bestehenden Datensatz-Systematik (wie Instanz und Artikel):
    eine 9-stellige Objektnummer aus dem gemeinsamen Kreis, Zeitstempel und ``is_active``
    für den Soft-Delete. Der Zustand im Feed wird daraus **abgeleitet** (aktiv/inaktiv) –
    es gibt kein Status-Feld, weil es keinen Lebenszyklus gibt, den es beschreiben könnte.

    **Die Objektnummer entsteht erst beim Speichern** (``services/orders.create_order``).
    Ein Auftragsentwurf lebt ausschliesslich im Browser: keine Entwurfs-Zeile, keine
    vorreservierte Nummer, kein Autosave. Wer den Entwurf verwirft, lässt keine Spur.
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
