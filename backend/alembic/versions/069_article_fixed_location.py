"""Fixierter Standort am Artikel (optionales Spezifikationsfeld).

GPS-Koordinaten + per Reverse-Geocoding gefüllte Adresse – exakt wie die Standort-
Definition am Lagerplatz-Datensatz. Rein deskriptiv am Artikel hinterlegt.

Revision ID: 069
Revises: 068
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '069'
down_revision = '068'
branch_labels = None
depends_on = None

_COLUMNS = (
    ("fixed_location_lat", sa.Numeric(9, 6)),
    ("fixed_location_lng", sa.Numeric(9, 6)),
    ("fixed_location_street", sa.String(255)),
    ("fixed_location_zip", sa.String(20)),
    ("fixed_location_city", sa.String(100)),
    ("fixed_location_country", sa.String(100)),
)


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "articles" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("articles")}
    for name, coltype in _COLUMNS:
        if name not in cols:
            op.add_column("articles", sa.Column(name, coltype, nullable=True))


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if "articles" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("articles")}
    for name, _ in _COLUMNS:
        if name in cols:
            op.drop_column("articles", name)
