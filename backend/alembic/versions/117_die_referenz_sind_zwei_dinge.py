"""Die Referenz sind zwei Dinge — `purchases.tracking`

Ein Feld «Bestellnummer, Link, Sendungsnummer» beantwortete **zwei Fragen zu zwei
Zeitpunkten**:

* *Wie bestelle ich bei ihm?* — seine Artikelnummer, der Shop-Link. Das ist eine
  Eigenschaft der **Paarung** Modul × Lieferant und bekannt, wenn man festlegt, wer in
  Frage kommt. Sie steht seither in der Definition (``config.suppliers[].ref``, JSONB —
  darum ohne Migration).
* *Wo ist die Sendung?* — entsteht erst **nach** der Bestellung und kommt vom
  Lieferanten. Das ist ``tracking``.

**Warum ein neuer Name statt ``reference``:** daneben steht künftig ``suppliers[].ref``.
Zwei Dinge, die «ref» heissen und Verschiedenes meinen, sind genau die Verwechslung, aus
der dieser Umbau entstanden ist.

``reference`` bleibt vorerst stehen (nullable, wird nicht mehr geschrieben, tolerant
gelesen) und wird im **Folge-Deploy** gedroppt — zusammen mit ``quantity``, ``due_date``,
``ordered_for`` und ``article_id``. Ein Drop jetzt träfe die während des Rollouts noch
laufende Vorgänger-Revision (die Ausfallklasse von Migration 090).

Revision ID: 117
Revises: 116
"""
from alembic import op

revision = "117"
down_revision = "116"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: repariert das Lifespan-Netz das Schema vor Alembic, läuft die Migration
    # beim nächsten Deploy trotzdem durch (die Lehre aus 090).
    op.execute("ALTER TABLE purchases ADD COLUMN IF NOT EXISTS tracking VARCHAR(200)")
    # Was schon dasteht, ist in aller Regel eine Sendungsnummer – sie wandert mit, statt
    # verloren zu gehen. Ein Shop-Link gehört zwar nicht mehr hierher, aber ihn
    # wegzuwerfen wäre schlimmer als ihn einmal an der falschen Stelle zu sehen.
    op.execute("UPDATE purchases SET tracking = reference WHERE tracking IS NULL")


def downgrade() -> None:
    op.execute("UPDATE purchases SET reference = tracking WHERE reference IS NULL")
    op.execute("ALTER TABLE purchases DROP COLUMN IF EXISTS tracking")
