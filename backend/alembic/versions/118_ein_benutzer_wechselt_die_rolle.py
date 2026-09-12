"""Ein Benutzer wird nicht deaktiviert — er wechselt die Rolle

«man deaktiviert/löscht nicht user. man wechselt höchstens die nutzerrolle. wenn jemand
das unternehmen verlässt, dann wird er zum normalen user statt als mitarbeiter. er soll ja
trotzdem weiterhin bei uns einkaufen dürfen gehen» (Testnotiz #755).

Beide Endpunkte (``DELETE /admin/users/{id}`` und ``POST …/reactivate``) sind ersatzlos
entfallen. **Damit könnte niemand mehr aufheben, was heute gesetzt ist** – ein
deaktivierter Benutzer wäre für immer ausgesperrt. Diese Migration hebt darum jede
bestehende Deaktivierung auf; setzen kann den Zustand danach nichts mehr.

Die Abweisung beim Login (``core/auth``) bleibt trotzdem stehen: sie verhindert, dass eine
deaktivierte Zeile still als **neuer** Benutzer mit neuer Objektnummer wiederaufersteht –
das ist ihr eigentlicher Zweck, und sie kostet eine Zeile.

Revision ID: 118
Revises: 117
"""
from alembic import op

revision = "118"
down_revision = "117"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE user_profiles SET is_active = true WHERE is_active = false")


def downgrade() -> None:
    # **Nicht umkehrbar, und das ist ehrlich:** welche Personen einmal deaktiviert waren,
    # steht im Audit-Log, nicht in dieser Spalte. Sie hier zu raten wäre schlimmer als
    # nichts zu tun.
    pass
