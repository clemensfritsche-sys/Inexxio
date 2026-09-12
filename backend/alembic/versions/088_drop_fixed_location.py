"""Fixierter Standort am Artikel ersatzlos entfernt.

Sechs Spalten (`articles.fixed_location_*`) trugen einen GPS-Punkt plus die dazu
reverse-geocodierte Adresse. Sie waren **rein deskriptiv**: kein Bestands-Standort,
keine Logik – nichts las sie ausserhalb von Formular, Lese-Ansicht und der
Kopierfunktion des «Ersetzen». Ein Artikel ist eine Gattung; einen Ort hat immer nur
die **Instanz** (`instances.location_*` + `locations.location_chain`). Die Angabe war
damit eine zweite, konkurrierende Antwort auf «wo ist das?» – und die schwächere.

Revision ID: 088
Revises: 087
"""

from alembic import op
import sqlalchemy as sa

revision = "088"
down_revision = "087"
branch_labels = None
depends_on = None

_COLS = (
    ("fixed_location_lat", sa.Numeric(9, 6)),
    ("fixed_location_lng", sa.Numeric(9, 6)),
    ("fixed_location_street", sa.String(255)),
    ("fixed_location_zip", sa.String(20)),
    ("fixed_location_city", sa.String(100)),
    ("fixed_location_country", sa.String(100)),
)


def upgrade() -> None:
    for name, _type in _COLS:
        op.drop_column("articles", name)


def downgrade() -> None:
    for name, type_ in _COLS:
        op.add_column("articles", sa.Column(name, type_, nullable=True))
