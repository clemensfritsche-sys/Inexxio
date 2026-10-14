"""►►► **Die Rolle ist der Zugang – und der Firmenname die Erklärung** (#1043). ◄◄◄

Diese Migration **legt keine Spalte an**. Sie zieht Daten nach, und zwar zweimal, weil
zwei Angaben ihre Bedeutung verlieren:

* **``role``** kennt nur noch ``admin`` · ``employee`` · ``user``. «Lieferant» und «Kunde»
  waren eine Aussage über **Vorgänge**, nicht über die Person – wer Partner einer Ausgabe
  ist, ist dort Lieferant, bei einer Einnahme Kunde, und dieselbe Person kann beides sein.
  Jede Zeile mit einem Altwert wird ``user``; ohne das liefe **jedes** Speichern an so
  einem Datensatz in ein 422 an einer Angabe, die niemand angefasst hat (``Role`` an der
  Tür kennt die Altwerte nicht mehr).
* **``invoice_*``** ist seit #1043 freiwillig: *leer gilt die Lieferadresse.* Der frühere
  Schalter ``invoice_same_as_shipping`` liess die Oberfläche die Hauptadresse **hineinkopieren**,
  und ``voucher.billing_of`` liest sie seither als *eigene* Rechnungsadresse – der Beleg
  zeigt dieselbe Anschrift zweimal. Geräumt wird **nur die exakte Kopie** (alle sieben
  Felder gleich), also geht keine Angabe verloren.

**Die Anweisungen stehen in ``services/people.repair_sql``**, nicht hier: die dev-Datenbank
fährt kein ``alembic upgrade head`` (#778), also liest sie das Lifespan-Netz ebenfalls –
zweimal ausgeschrieben wären es zwei Wahrheiten.

Dazu fällt eine Sperre: ``invoice_same_as_shipping`` ist ``NOT NULL`` **ohne**
Server-Default, und sein Mapping ist weg – ohne dieses ``ALTER`` liefe jedes Insert eines
neuen Benutzers auf. Dieselbe Zwei-Schritte-Regel wie bei ``purchases.quantity``:
**gedroppt** wird die Spalte im Folge-Deploy, zusammen mit ``account_type``, den acht
``ship_*`` und den beiden aus #1042 (``docs/backlog.md``).

Revision ID: 140
Revises: 139
"""

import sqlalchemy as sa
from alembic import op

from app.services.people import repair_sql

revision = "140"
down_revision = "139"
branch_labels = None
depends_on = None

_LOOSEN = "invoice_same_as_shipping"


def _column(name: str) -> dict | None:
    insp = sa.inspect(op.get_bind())
    for col in insp.get_columns("user_profiles"):
        if col["name"] == name:
            return col
    return None


def upgrade() -> None:
    col = _column(_LOOSEN)
    if col is not None and not col["nullable"]:
        op.alter_column("user_profiles", _LOOSEN,
                        existing_type=sa.Boolean(), nullable=True)
    bind = op.get_bind()
    for stmt in repair_sql():
        bind.execute(sa.text(stmt))


def downgrade() -> None:
    """Die Sperre kommt zurück; die Daten nicht.

    Eine Rolle, die ``user`` heisst, war vorher ``customer`` **oder** ``supplier`` – welche,
    steht nirgends mehr. Und eine geräumte Rechnungsadresse war eine Kopie der
    Hauptadresse, also ist sie durch die Regel «leer gilt die Lieferadresse» ersetzt und
    nicht verloren. Ein Downgrade, der beides erfände, wäre schlimmer als keines.
    """
    col = _column(_LOOSEN)
    if col is not None and col["nullable"]:
        op.execute("UPDATE user_profiles SET invoice_same_as_shipping = false "
                   "WHERE invoice_same_as_shipping IS NULL")
        op.alter_column("user_profiles", _LOOSEN,
                        existing_type=sa.Boolean(), nullable=False)
