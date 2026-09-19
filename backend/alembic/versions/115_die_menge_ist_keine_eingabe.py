"""Die Bestellmenge ist keine Eingabe — `purchases.quantity` wird optional

Ein Beschaffungs-Modul sitzt in einem Prozess: **wie viel bestellt wird, sagen die
Einzelinstanzen, die davorstehen**. Eine getippte Menge daneben war eine zweite Aussage
über dieselbe Sache. Geblieben ist ``ordered_for`` – die Menge, die mit der Bestellung
eingefroren wird; davor wird gerechnet (``purchase.quantity_of``).

**Warum optional und nicht gedroppt:** während des Cloud-Run-Rollouts läuft die
Vorgänger-Revision weiter, und die schreibt ``quantity`` noch mit. Ein Drop jetzt liesse
ihre Inserts auflaufen (die Ausfallklasse von Migration 090, umgekehrt herum). Also
zuerst die ``NOT NULL``-Sperre lösen – ab jetzt darf **beides** laufen: wer die Spalte
noch füllt, darf; wer sie weglässt, auch. Der **Drop kommt im Folge-Deploy**, zusammen
mit ``due_date``.

``due_date`` (zugesagter Liefertermin) war ein Eingabefeld, das niemand pflegen will: er
ist aus Bestelldatum + Lieferfrist ableitbar, sobald man ihn braucht. Die Spalte ist
bereits nullable und wird nur noch nicht mehr geschrieben.

Revision ID: 115
Revises: 114
"""
from alembic import op

revision = "115"
down_revision = "114"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE purchases ALTER COLUMN quantity DROP NOT NULL")


def downgrade() -> None:
    # Zurück geht nur mit einem Wert – NULL wäre für die alte Sperre kein gültiger Zustand.
    op.execute("UPDATE purchases SET quantity = 1 WHERE quantity IS NULL")
    op.execute("ALTER TABLE purchases ALTER COLUMN quantity SET NOT NULL")
