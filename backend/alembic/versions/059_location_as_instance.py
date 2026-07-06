"""Lagerplatz als Artikel + Instanz (F) – Vereinheitlichung.

Ein Lagerplatz IST eine **Instanz** eines ``is_location``-Artikels. Der Artikel trägt die
geteilten Typ-Eigenschaften (Bezeichnung, Abmessung = ``size``, Traglast = ``max_load_kg``),
die Instanz den konkreten Standort: Geo/Adresse (der Karten-Standort – per Instanz, NICHT
am Typ), Bemerkung und die Kapazität (= ``quantity``). ``is_location``-Instanzen zählen NIE
als Bestand (Ausschluss in ``inventory.in_stock_clauses``) und entstehen ohne Auftrag
(``instances.order_id`` wird nullable).

Neue Spalten:
    articles.is_location    BOOL (default false)
    articles.max_load_kg    NUMERIC(12,3)         – Traglast
    instances.is_location   BOOL (default false)
    instances.note          VARCHAR(500)
    instances.latitude      NUMERIC(9,6)
    instances.longitude     NUMERIC(9,6)
    instances.address_*     VARCHAR
    instances.order_id      → nullable

Die alte Tabelle ``storage_locations`` wird entfernt (kein Backward-Compat nötig).

Revision ID: 059
Revises: 058
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '059'
down_revision = '058'
branch_labels = None
depends_on = None

_ARTICLE_COLS = (
    ("is_location", sa.Column("is_location", sa.Boolean(), nullable=False, server_default="false")),
    ("max_load_kg", sa.Column("max_load_kg", sa.Numeric(12, 3), nullable=True)),
)
_INSTANCE_COLS = (
    ("is_location", sa.Column("is_location", sa.Boolean(), nullable=False, server_default="false")),
    ("note", sa.Column("note", sa.String(500), nullable=True)),
    ("latitude", sa.Column("latitude", sa.Numeric(9, 6), nullable=True)),
    ("longitude", sa.Column("longitude", sa.Numeric(9, 6), nullable=True)),
    ("address_street", sa.Column("address_street", sa.String(255), nullable=True)),
    ("address_zip", sa.Column("address_zip", sa.String(20), nullable=True)),
    ("address_city", sa.Column("address_city", sa.String(100), nullable=True)),
    ("address_country", sa.Column("address_country", sa.String(100), nullable=True)),
)


def _add(table: str, cols) -> None:
    insp = inspect(op.get_bind())
    if table not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns(table)}
    for name, col in cols:
        if name not in have:
            op.add_column(table, col)


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    _add("articles", _ARTICLE_COLS)
    _add("instances", _INSTANCE_COLS)
    if "instances" in insp.get_table_names():
        cols = {c["name"]: c for c in insp.get_columns("instances")}
        if "order_id" in cols and not cols["order_id"]["nullable"]:
            op.alter_column("instances", "order_id", existing_type=sa.BigInteger(), nullable=True)
    if "storage_locations" in insp.get_table_names():
        op.drop_table("storage_locations")


def downgrade() -> None:
    # Additiv/aufräumend – kein sinnvoller Rückweg (kein Backward-Compat). No-op.
    pass
