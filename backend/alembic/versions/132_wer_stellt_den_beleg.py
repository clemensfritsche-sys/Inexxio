"""Wer stellt den Beleg — `user_profiles.company_object_id`, `deals.issuer_company_id`

Zwei Spalten, eine Frage: **welche unserer Gesellschaften stellt diesen Beleg?**

Bis hierher war die Antwort immer der **Betreiber** (`sites.find_operator`) – also die
Gesellschaft, die die eine Website vertritt. Bei mehreren gleichrangigen Gesellschaften
ist das eine Vermutung, und sie steht auf einem Beleg.

**`user_profiles.company_object_id`** — für welche Gesellschaft eine Person arbeitet.
Die Angabe fehlte im Datenmodell ganz; ohne sie lässt sich nichts vorwählen. Objektnummer
statt Fremdschlüssel, wie überall im Haus, wo auf einen Datensatz gezeigt wird.
`NULL` ist regulär für jeden, der nicht bei uns arbeitet.

**`deals.issuer_company_id`** — wer den Beleg stellt, **eingefroren bei der Anlage** aus
der Gesellschaft des freigebenden Mitarbeiters. Bei jeder Anzeige neu gelesen änderte ein
Wechsel rückwirkend, wer einen alten Beleg gestellt hat. `NULL` heisst weiterhin «der
Betreiber» – der Rückfall bleibt, er ist nur nicht mehr die Regel.

Revision ID: 132
Revises: 131
"""

from alembic import op
import sqlalchemy as sa

revision = "132"
down_revision = "131"
branch_labels = None
depends_on = None


def _has_column(table: str, name: str) -> bool:
    bind = op.get_bind()
    return any(c["name"] == name for c in sa.inspect(bind).get_columns(table))


def upgrade() -> None:
    # **Idempotent je Spalte** – die dev-Datenbank kennt kein `alembic upgrade`, dort legt
    # das Spalten-Netz in `main.py` nach (die Lehre aus Migration 129).
    if not _has_column("user_profiles", "company_object_id"):
        op.add_column("user_profiles",
                      sa.Column("company_object_id", sa.BigInteger(), nullable=True))
    if not _has_column("deals", "issuer_company_id"):
        op.add_column("deals",
                      sa.Column("issuer_company_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    for table, name in (("deals", "issuer_company_id"),
                        ("user_profiles", "company_object_id")):
        if _has_column(table, name):
            op.drop_column(table, name)
