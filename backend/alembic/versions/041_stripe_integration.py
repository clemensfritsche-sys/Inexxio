"""Stripe-Vollintegration: Customer-/Session-/Subscription-/PaymentIntent-Bezüge + Snapshot.

- ``user_profiles.stripe_customer_id`` – Mapping UserProfile ↔ Stripe Customer.
- ``orders.stripe_checkout_session_id`` / ``stripe_subscription_id`` – Zahlung/Abo (Stripe = Quelle der Wahrheit).
- ``sales.stripe_payment_intent_id`` / ``stripe_snapshot`` – Beleg-Snapshot (Settlement CHF + Adaptive-Pricing-Lokalwährung + Steuer).

Revision ID: 041
Revises: 040
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = '041'
down_revision = '040'
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if not _has_col(insp, "user_profiles", "stripe_customer_id"):
        op.add_column("user_profiles", sa.Column("stripe_customer_id", sa.String(length=64), nullable=True))
        op.create_index("ix_user_profiles_stripe_customer_id", "user_profiles", ["stripe_customer_id"])
    if not _has_col(insp, "orders", "stripe_checkout_session_id"):
        op.add_column("orders", sa.Column("stripe_checkout_session_id", sa.String(length=80), nullable=True))
        op.create_index("ix_orders_stripe_checkout_session_id", "orders", ["stripe_checkout_session_id"])
    if not _has_col(insp, "orders", "stripe_subscription_id"):
        op.add_column("orders", sa.Column("stripe_subscription_id", sa.String(length=80), nullable=True))
        op.create_index("ix_orders_stripe_subscription_id", "orders", ["stripe_subscription_id"])
    if not _has_col(insp, "sales", "stripe_payment_intent_id"):
        op.add_column("sales", sa.Column("stripe_payment_intent_id", sa.String(length=80), nullable=True))
        op.create_index("ix_sales_stripe_payment_intent_id", "sales", ["stripe_payment_intent_id"])
    if not _has_col(insp, "sales", "stripe_snapshot"):
        op.add_column("sales", sa.Column("stripe_snapshot", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("sales", "stripe_snapshot")
    op.drop_index("ix_sales_stripe_payment_intent_id", table_name="sales")
    op.drop_column("sales", "stripe_payment_intent_id")
    op.drop_index("ix_orders_stripe_subscription_id", table_name="orders")
    op.drop_column("orders", "stripe_subscription_id")
    op.drop_index("ix_orders_stripe_checkout_session_id", table_name="orders")
    op.drop_column("orders", "stripe_checkout_session_id")
    op.drop_index("ix_user_profiles_stripe_customer_id", table_name="user_profiles")
    op.drop_column("user_profiles", "stripe_customer_id")
