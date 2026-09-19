"""Was beschafft wird, sagt der Prozess — `purchases.ordered_lines`

**Das Artikelfeld am Beschaffungs-Modul entfällt.** *Was* bestellt wird, sagen die
Einzelinstanzen, die vor dem Modul stehen: sie tragen ihren Artikel, und ihre Zahl ist die
Menge (``purchase.process_lines``). Es von Hand zu wählen war eine zweite Aussage über
dieselbe Sache – und die getippte gewinnt auch dann, wenn sie falsch ist.

Daraus fällt der Mehrartikel-Fall von selbst heraus: stehen Stücke zweier Artikel davor,
hat der Beleg **zwei Zeilen** – EINE Bestellung mit zwei Positionen, wie im echten Leben.
Darum ersetzt ``ordered_lines`` (JSONB) die einzelne Zahl ``ordered_for``.

**Warum ``article_id`` nur optional und nicht gedroppt:** während des Cloud-Run-Rollouts
läuft die Vorgänger-Revision weiter, und die schreibt die Spalte noch mit ``NOT NULL``.
Ein Drop jetzt liesse ihre Inserts auflaufen (die Ausfallklasse von Migration 090,
umgekehrt herum). Also zuerst die Sperre lösen – ab jetzt darf **beides** laufen. Der
**Drop kommt im Folge-Deploy**, zusammen mit ``quantity``, ``due_date`` und
``ordered_for``.

Revision ID: 116
Revises: 115
"""
from alembic import op

revision = "116"
down_revision = "115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: repariert das Lifespan-Netz das Schema vor Alembic, läuft die Migration
    # beim nächsten Deploy trotzdem durch (die Lehre aus 090).
    op.execute(
        "ALTER TABLE purchases ADD COLUMN IF NOT EXISTS ordered_lines JSONB"
    )
    op.execute("ALTER TABLE purchases ALTER COLUMN article_id DROP NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE purchases DROP COLUMN IF EXISTS ordered_lines")
    # Zurück geht nur mit einem Wert – NULL wäre für die alte Sperre kein gültiger Zustand.
    op.execute("DELETE FROM purchases WHERE article_id IS NULL")
    op.execute("ALTER TABLE purchases ALTER COLUMN article_id SET NOT NULL")
