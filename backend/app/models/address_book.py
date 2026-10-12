"""►►► **Das Adressbuch einer Person** – beliebig viele Anschriften, privat wie geschäftlich.

Eine Person bestellt (eine Firma bestellt nie selbst – sie ist höchstens der
Rechnungsempfänger «im Namen von»). Die Anschriften gehören darum **der Person**: die
Wohnung, das Büro, das Lager der Firma, die Baustelle. Wohin die Ware und wohin die
Rechnung geht, entscheidet die **Bestellung** – je Beleg, vorbelegt mit den Standards hier.

**Genau eine Standard-Lieferadresse und genau eine Standard-Rechnungsadresse** – als
partieller Unique-Index in der Datenbank, nicht als Prüfung im Dienst: zwei Standards
wären zwei Antworten auf «wohin, wenn niemand etwas sagt?». Beide dürfen dieselbe Zeile
sein (der Normalfall).

**Die Rechnungs-E-Mail steht an der Anschrift**, nicht an der Person: wohin die Rechnung
per Post geht und wohin per E-Mail, ist dieselbe Entscheidung. Leer heisst «die E-Mail
der Person».

Ersetzt die Felder ``address_*``/``invoice_*`` am Benutzer (Migration ``143``) – dort
gab es genau zwei Anschriften und die Kopie der einen in der anderen.
"""

from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Address(Base, TimestampMixin):
    __tablename__ = "addresses"
    __table_args__ = (
        Index("uq_addresses_default_delivery", "owner_id", unique=True,
              postgresql_where=text("is_active AND is_default_delivery")),
        Index("uq_addresses_default_billing", "owner_id", unique=True,
              postgresql_where=text("is_active AND is_default_billing")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    #: Die Person, der die Anschrift gehört (``user_profiles.id``).
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user_profiles.id"), index=True, nullable=False)
    #: Strasse mit Hausnummer – eine Zeile, so wie die Adresssuche sie liefert.
    street1: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    #: Zusatz: c/o, Postfach, Abteilung, Gebäude.
    street2: Mapped[Optional[str]] = mapped_column(String(255))
    zip: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    region: Mapped[Optional[str]] = mapped_column(String(100))
    #: ISO-2.
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="CH")
    #: Wohin die Rechnung per E-Mail geht, wenn sie an diese Anschrift geht.
    email: Mapped[Optional[str]] = mapped_column(String(255))
    is_default_delivery: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false")
    is_default_billing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false")
