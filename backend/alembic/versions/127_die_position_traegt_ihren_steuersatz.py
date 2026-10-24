"""Die Position trägt ihren Steuersatz — `deal_entries.vat` + `service_date`

Eine Rechnung ohne Steuersatz und Steuerbetrag ist keine (MWSTG Art. 26 Abs. 2 Bst. f),
und ohne **Leistungsdatum** (Bst. c) entscheidet bei einem Satzwechsel das falsche Datum
über den Satz.

**Warum die Aufteilung am Beleg steht und nicht gerechnet wird:** ein gebuchter Beleg
behält seine Steuerangabe. Aus den Positionen nachgerechnet änderte sich die Steuer einer
längst gestellten Rechnung, sobald jemand eine Position anfasst.

Beide Spalten sind ``NULL``-bar: eine **Zahlung** trägt keine Steuer (Geld begleicht sie,
es hat keine), und ein Leistungsdatum, das fehlt, heisst «wie gebucht».

Revision ID: 127
Revises: 126
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "127"
down_revision = "126"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in sa.inspect(bind).get_columns("deal_entries")}


def upgrade() -> None:
    # **Geprüft, nicht geglaubt**: die dev-Datenbank kennt kein `alembic upgrade`, dort
    # legt das Lifespan-Netz (`main._COLUMN_SAFETY_NET`) die Spalten an. Diese Migration
    # muss darum idempotent sein – sonst scheitert sie genau auf der Umgebung, die läuft.
    have = _columns()
    if "vat" not in have:
        op.add_column("deal_entries", sa.Column("vat", JSONB(), nullable=True))
    if "service_date" not in have:
        op.add_column("deal_entries", sa.Column("service_date", sa.Date(), nullable=True))


def downgrade() -> None:
    have = _columns()
    if "service_date" in have:
        op.drop_column("deal_entries", "service_date")
    if "vat" in have:
        op.drop_column("deal_entries", "vat")
