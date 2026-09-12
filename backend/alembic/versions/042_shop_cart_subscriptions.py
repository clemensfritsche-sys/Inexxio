"""Shop-Phase 8: Warenkorb (CheckoutIntent), zwei Abo-Typen, Verkaufs-Vereinfachung.

- ``article_prices.sub_type`` – Abo-Typ (usage = Nutzungsabo | product = Produktabo);
  nur bei ``kind='subscription'`` relevant, sonst NULL. ``tax_class`` entfällt aus dem UI/
  API (Stripe Tax übernimmt die Steuer) – die Spalte bleibt (Default 'standard') unberührt.
- ``orders.recurrence_kind`` – gespiegelter Abo-Typ am Auftrag (für die per-Zyklus-Logik
  beim ``invoice.paid``-Webhook: Produktabo erzeugt Folge-Fulfillment, Nutzungsabo nicht).
- Neue Tabelle ``checkout_intents`` – **aufgeschobene Auftragserzeugung** (Defer-Modell):
  der Warenkorb wird bis zur bestätigten Zahlung gehalten; erst der Zahlungs-Webhook
  erzeugt je Position einen Auftrag (Made-to-Order) bzw. finalisiert die schon
  reservierten (stock-) Aufträge. Eine Checkout-Session ⇒ ein Intent ⇒ N Aufträge.
- Sichtbarkeit ``unlisted`` entfällt – Altbestände werden zu ``private`` normalisiert.

Revision ID: 042
Revises: 041
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = '042'
down_revision = '041'
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not _has_col(insp, "article_prices", "sub_type"):
        op.add_column("article_prices", sa.Column("sub_type", sa.String(length=10), nullable=True))
    if not _has_col(insp, "orders", "recurrence_kind"):
        op.add_column("orders", sa.Column("recurrence_kind", sa.String(length=10), nullable=True))

    if "checkout_intents" not in insp.get_table_names():
        op.create_table(
            "checkout_intents",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("customer_id", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("provider", sa.String(length=16), nullable=True),
            sa.Column("stripe_session_id", sa.String(length=80), nullable=True),
            sa.Column("lines", postgresql.JSONB(), nullable=True),
            sa.Column("amount_chf", sa.Numeric(12, 2), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_checkout_intents_stripe_session_id", "checkout_intents", ["stripe_session_id"])
        op.create_index("ix_checkout_intents_customer_id", "checkout_intents", ["customer_id"])

    # Sichtbarkeit 'unlisted' wird nicht mehr unterstützt → auf 'private' normalisieren.
    if _has_col(insp, "articles", "sales_visibility"):
        bind.execute(sa.text(
            "UPDATE articles SET sales_visibility='private' WHERE sales_visibility='unlisted'"))


def downgrade() -> None:
    op.drop_index("ix_checkout_intents_customer_id", table_name="checkout_intents")
    op.drop_index("ix_checkout_intents_stripe_session_id", table_name="checkout_intents")
    op.drop_table("checkout_intents")
    op.drop_column("orders", "recurrence_kind")
    op.drop_column("article_prices", "sub_type")
