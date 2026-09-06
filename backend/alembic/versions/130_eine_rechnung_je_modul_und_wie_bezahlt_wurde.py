"""Eine Rechnung je Modul — `deals.share` und `deal_entries.method`

Zwei Spalten aus einer Runde (Testnotizen #859–#866), und beide tragen eine Regel:

**`deals.share`** — welchen Teil der Positionen dieser Vorgang abrechnet, in Prozent.
Er ist die Voraussetzung dafür, dass «je Modul höchstens eine Rechnung» überhaupt
gangbar ist: *Vorauszahlung → Leistung → Restzahlung* sind zwei Zahlungs-Module, beide
sehen dieselben Stücke und damit dieselben Positionen — ohne Anteil hätte jedes die
**volle** Summe zugesagt, und «erst zahlen» ginge nie auf. Vorgabe 100 = der ganze
Betrag, also der Normalfall, den niemand einstellen muss.

**`deal_entries.method`** — bar · Überweisung · Karte. Kein zweites Modell: gebucht wird
in jedem Fall dieselbe Zeile; bei der einen ruft ein Mensch, bei der anderen der Webhook.
`NULL` ist regulär und heisst «nicht festgehalten» — so steht jede Zahlung da, die es vor
dieser Angabe schon gab. Nachträglich geraten wird **nichts**: eine erfundene Zahlungsart
wäre eine Behauptung über einen Kontoauszug, den niemand gelesen hat.

Revision ID: 130
Revises: 129
"""

from alembic import op
import sqlalchemy as sa

revision = "130"
down_revision = "129"
branch_labels = None
depends_on = None


def _has_column(table: str, name: str) -> bool:
    bind = op.get_bind()
    return any(c["name"] == name for c in sa.inspect(bind).get_columns(table))


def upgrade() -> None:
    # **Idempotent JE OBJEKT** – die dev-Datenbank kennt kein `alembic upgrade`, dort legt
    # das Spalten-Netz in `main.py` nach. Ein `if irgendetwas da: return` hiesse, dass die
    # zweite Spalte genau dort nie ankommt (die Lehre aus Migration 129).
    if not _has_column("deals", "share"):
        op.add_column("deals", sa.Column(
            "share", sa.Numeric(6, 3), nullable=False, server_default="100"))
    if not _has_column("deal_entries", "method"):
        op.add_column("deal_entries", sa.Column("method", sa.String(10), nullable=True))


def downgrade() -> None:
    if _has_column("deal_entries", "method"):
        op.drop_column("deal_entries", "method")
    if _has_column("deals", "share"):
        op.drop_column("deals", "share")
