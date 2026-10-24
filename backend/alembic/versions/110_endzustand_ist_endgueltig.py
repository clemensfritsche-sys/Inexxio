"""Ein Endzustand ist endgültig – und das steht in der DATENBANK.

Ein Statuswechsel aus einem terminalen Zustand heraus wird von einem Trigger abgewiesen,
nicht von der Anwendungslogik. Der Unterschied ist der zwischen einer Zusage und einer
Gewohnheit: eine Prüfung im Dienst kennt nur die Wege, die man beim Schreiben im Kopf
hatte – ein neues Modul, ein Reparaturskript, eine Migration oder ein ``UPDATE`` von Hand
gehen daran vorbei. Der Trigger sitzt darunter und kennt sie alle.

**Keine Umgehung.** Es gibt keinen Parameter und kein Force-Flag. Wer eine Ausnahme
bräuchte, hat kein Sonderrecht, sondern ein Modellproblem: ein Zustand, den man doch
verlassen können muss, ist nicht terminal – und das ist eine Zeile in
``domain/statuses.CATALOG``.

Die Liste der Endzustände kommt aus genau diesem Katalog. Diese Migration ist ihre
Momentaufnahme; **nachgezogen wird sie bei jedem Start** (``main._ensure_columns``), damit
die Datenbank von der einen Liste nicht abweichen kann.

Revision ID: 110
Revises: 109
"""
from alembic import op

from app.domain import statuses as st

revision = "110"
down_revision = "109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(st.terminal_guard_sql())


def downgrade() -> None:
    op.execute(
        f"DROP TRIGGER IF EXISTS {st.TERMINAL_GUARD_TRIGGER} ON instance_units"
    )
    op.execute(f"DROP FUNCTION IF EXISTS {st.TERMINAL_GUARD_FN}()")
