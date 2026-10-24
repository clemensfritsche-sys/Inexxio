"""Phase-0-Fracht: Sendungsart + Last am Versand-Beleg (ADR 005).

Der Bewegungs-/Versand-Beleg unterscheidet jetzt **Paket** (Aggregator/Rate-Shopping)
und **Fracht** (Stückgut/Palette – manuell/Spediteur, RFQ offline). Die Sendungsart wird
bei der Anlage aus der Last (Gewicht/Volumen) abgeleitet und ist am Beleg übersteuerbar.

shipments:
  + kind        VARCHAR(12)  DEFAULT 'parcel' NOT NULL  (parcel | freight)
  + load        JSONB                                    (pallets/loading_meters/volume_m3/…)
  + incoterm    VARCHAR(8)                               (EXW … DDP, international)
  + pickup_date VARCHAR(10)                              (ISO YYYY-MM-DD, Fracht-Abholung)

Revision ID: 073
Revises: 072
Create Date: 2026-07-10
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '073'
down_revision = '072'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "shipments" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("shipments")}
    if "kind" not in cols:
        op.add_column("shipments", sa.Column("kind", sa.String(12), nullable=False,
                                             server_default="parcel"))
    if "load" not in cols:
        op.add_column("shipments", sa.Column("load", JSONB, nullable=True))
    if "incoterm" not in cols:
        op.add_column("shipments", sa.Column("incoterm", sa.String(8), nullable=True))
    if "pickup_date" not in cols:
        op.add_column("shipments", sa.Column("pickup_date", sa.String(10), nullable=True))


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if "shipments" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("shipments")}
    for name in ("kind", "load", "incoterm", "pickup_date"):
        if name in cols:
            op.drop_column("shipments", name)
