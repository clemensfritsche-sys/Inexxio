"""Die Verbindung zwischen zwei Aufträgen: kehrt ein Stück zurück?

``order_units.return_to_order_id``  Ein **Abweichungsauftrag** nimmt einem laufenden
                                   Auftrag ein Stück mitten im Ablauf ab. Diese Spalte
                                   sagt, ob es dorthin zurückkehrt, wenn es hier durch
                                   ist – ``NULL`` heisst «nirgendwohin» (das Stück war
                                   frei, oder die Rückführung wurde gekappt).

                                   Sie hängt an der **Verbindung**, nicht am Auftrag.
                                   Genau dadurch funktionieren Schachtelung (eine
                                   Abweichung hat ihre eigene Abweichung) und
                                   Parallelität (mehrere gleichzeitig) ohne eine einzige
                                   zusätzliche Regel – und «wartet auf Rückführung»
                                   bleibt **abgeleitet**: es wartet, wer noch eine
                                   offene rückführende Verbindung hat.

Der **Auftragstyp «Abweichung» entsteht dabei nicht** – es gibt keinen. Dass ein Auftrag
eine Abweichung ist, steht im Ereignis-Log: sein Start-Eintrag trägt
``status_before = im_prozess``.

Revision ID: 109
Revises: 108
"""
import sqlalchemy as sa
from alembic import op

revision = "109"
down_revision = "108"
branch_labels = None
depends_on = None

_TABLE = "order_units"
_COLUMN = "return_to_order_id"
_INDEX = "ix_order_units_return_to_order_id"


def _has_table(table: str) -> bool:
    return bool(op.get_bind().execute(
        sa.text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar())


def _has_column(table: str, column: str) -> bool:
    return bool(op.get_bind().execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table, "c": column}).first())


def upgrade() -> None:
    if not _has_table(_TABLE):
        return
    if not _has_column(_TABLE, _COLUMN):
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.BigInteger(), nullable=True))
    op.execute(f"CREATE INDEX IF NOT EXISTS {_INDEX} ON {_TABLE} ({_COLUMN})")


def downgrade() -> None:
    """Struktur zurück – die Verbindungen selbst sind damit weg.

    Das ist ehrlich und nicht rekonstruierbar: welches Stück in welchen Auftrag
    zurückgekehrt wäre, steht sonst nirgends als Absicht. Der Ereignis-Log behält, was
    **passiert** ist; was geplant war, ist eine Aussage der Gegenwart.
    """
    op.execute(f"DROP INDEX IF EXISTS {_INDEX}")
    if _has_table(_TABLE) and _has_column(_TABLE, _COLUMN):
        op.drop_column(_TABLE, _COLUMN)
