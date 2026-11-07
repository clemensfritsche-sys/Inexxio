"""Erfassen neu: die Testnotizen sind weg (``feedback_notes``).

Rückmeldungen zur Software sind seither gewöhnliche Erfassungen mit der Stecknadel: eine Notiz am
Artikel «ERP» bzw. «Website» (``frontend/src/lib/pin-point.ts``). Die eigene Tabelle der
Testnotizen, ihr Werkzeug und ihr Endpunkt sind entfernt – ohne Übernahme (es gab sie nur in der
Testumgebung). Was das Log über sie festhielt, bleibt dort (unveränderlich).

Mapping und Tabelle gehen in einem Deploy: ausser dem entfernten Endpunkt las niemand die Tabelle.

Revision ID: 172
Revises: 171
"""

from alembic import op

revision = "172"
down_revision = "171"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS feedback_notes")


def downgrade() -> None:
    raise NotImplementedError("Die Testnotizen kommen nicht zurück.")
