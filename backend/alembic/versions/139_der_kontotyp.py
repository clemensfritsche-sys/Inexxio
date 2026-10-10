"""►►► **Der Kontotyp – und die Rechtsform am Benutzer** (Testnotiz #1042). ◄◄◄

Zwei Spalten an ``user_profiles``:

* ``account_type`` – **Privat ↔ Geschäft**, die Stammdatenfrage neben der Rolle.
  **Nullable, ohne Default** – und das ist keine Nachlässigkeit, sondern der Grund, warum
  diese Migration **keinen Backfill** braucht: ``NULL`` heisst «noch nicht entschieden»,
  und dann *ist* der Firmenname die Antwort (``domain/accounts.effective``). Ein
  ``UPDATE … SET account_type='business' WHERE company_name <> ''`` müsste im
  Lifespan-Netz stehen (die dev-Datenbank fährt kein ``alembic upgrade head``, #778) und
  liefe damit bei **jedem** Start – es flippte also jeden zurück, der bewusst auf
  «Privat» gestellt hat, ohne seinen Firmennamen zu löschen. Genau gegen die Regel, dass
  vorhandene Werte **bleiben**.
* ``legal_form`` – die Rechtsform der Firma. «Muster» ist keine Rechtsperson, «Muster AG»
  ist eine, und auf einem Beleg steht die, die haftet (MWSTG Art. 26). Zusammengesetzt
  wird sie an derselben einen Stelle wie bei unserer eigenen Seite
  (``sites.legal_name``).

**Nichts wird gedroppt.** ``company_billing_email`` und ``invoice_company`` verlieren in
diesem Deploy ihr Mapping; gedroppt werden sie im Folge-Deploy (Zwei-Deploy-Regel,
``docs/backlog.md``) – die Lehre aus Migration 090 ist teuer bezahlt.

Revision ID: 139
Revises: 138
"""

import sqlalchemy as sa
from alembic import op

revision = "139"
down_revision = "138"
branch_labels = None
depends_on = None


#: ``(Spalte, Typ)`` – je Objekt idempotent geprüft. Ein Wächter der Form «eine Spalte da
#: → fertig» wäre auf dev falsch: dort legt das Spalten-Netz die erste an, und die zweite
#: käme dann **nie** (dieselbe Lehre wie bei Index und Fremdschlüssel, #1042/Migration 129).
_COLUMNS = (
    ("account_type", sa.String(length=20)),
    ("legal_form", sa.String(length=50)),
)


def _has(name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return name in {c["name"] for c in insp.get_columns("user_profiles")}


def upgrade() -> None:
    for name, type_ in _COLUMNS:
        if not _has(name):
            op.add_column("user_profiles", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in _COLUMNS:
        if _has(name):
            op.drop_column("user_profiles", name)
