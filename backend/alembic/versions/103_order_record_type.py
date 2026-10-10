"""Der Datensatztyp «Auftrag» – neu, leer, mit eigener Objektnummer.

Migration 102 hatte ``orders`` samt der ganzen Prozesslogik gedroppt. Diese Tabelle ist
**nicht** deren Rückkehr: sie trägt genau zwei Spalten plus die Systematik-Felder. Welche
Angaben ein Auftrag führt, entscheidet sich mit der neuen Prozesslogik – Spalten auf
Vorrat wären erfundene Anforderungen.

Der Zustand im Feed wird aus ``is_active`` abgeleitet; ein Status-Feld gibt es bewusst
nicht, weil es keinen Lebenszyklus gibt, den es beschreiben könnte.

Revision ID: 103
Revises: 102
"""
import sqlalchemy as sa
from alembic import op

revision = "103"
down_revision = "102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: 102 hat die alte Tabelle gedroppt, aber das Lifespan-``create_all``
    # könnte sie zwischen zwei Deploys bereits aus dem Modell angelegt haben.
    op.execute("DROP TABLE IF EXISTS orders CASCADE")
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("object_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_orders_object_id", "orders", ["object_id"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS orders CASCADE")
