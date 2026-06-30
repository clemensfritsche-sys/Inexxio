from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class CheckoutIntent(Base, TimestampMixin):
    """**Aufgeschobene Auftragserzeugung** (Defer-Modell) für den Warenkorb-Checkout.

    Der Warenkorb wird – bis zur **bestätigten Zahlung** – als Intent gehalten, NICHT als
    Auftrag (Made-to-Order: kein Auftrag/keine Produktion ohne Zahlung). Eine Zahlung
    (eine Stripe-Checkout-Session bzw. ein manuelles Token) ⇒ EIN Intent ⇒ je Position
    EIN Auftrag, der erst der Zahlungs-Webhook erzeugt/finalisiert.

    ``lines`` (JSONB) hält die aufgelösten Positionen, z. B.::

        [{"article_id": 12, "article_object_id": 100000123, "price_id": 7,
          "quantity": 2, "fulfillment": "make", "kind": "subscription",
          "interval": "month", "sub_type": "product", "base_amount_chf": "199.00",
          "order_id": null}]

    ``order_id`` ist bei **stock**-Positionen schon bei der Bestellung gesetzt (dort wird
    reserviert, um Überverkauf zu vermeiden); **make**-Positionen erhalten ihren Auftrag
    erst bei der Zahlung. KEINE eigene Objektnummer (rein technischer Beleg, wie ``sales``).
    """

    __tablename__ = "checkout_intents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    # pending → wartet auf Zahlung | completed → Aufträge erzeugt/bezahlt | cancelled → storniert
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    stripe_session_id: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)

    lines: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    amount_chf: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
