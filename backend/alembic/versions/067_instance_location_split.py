"""Standort-Verteilung einer Charge (instances.locations).

Eine Charge-Instanz (z. B. 1000 Schrauben) kann physisch auf mehrere Standorte
verteilt sein, OHNE Teilung der Instanz / ohne neue Objektnummer – exakt nach dem
Vorbild von ``instances.reservations``. Map keyed by Ziel-Objektnummer:
``{"100000123": {"t": "lagerplatz", "q": "300"}, ...}`` (Summe = quantity).

GIN-Index auf ``locations`` (Default-``jsonb_ops``) macht die «wer liegt hier?»-Abfrage
(``locations ? '<objektnr>'``) indizierbar.

Revision ID: 067
Revises: 066
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '067'
down_revision = '066'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "instances" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("instances")}
        if "locations" not in cols:
            op.add_column("instances", sa.Column("locations", JSONB(), nullable=True))
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_instances_locations "
            "ON instances USING gin (locations)"
        )


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if "instances" in insp.get_table_names():
        op.execute("DROP INDEX IF EXISTS ix_instances_locations")
        cols = {c["name"] for c in insp.get_columns("instances")}
        if "locations" in cols:
            op.drop_column("instances", "locations")
