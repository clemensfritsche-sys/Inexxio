"""Persönliche Postfächer gibt es nicht mehr – im Kommunikationstool ist jeder gleich.

Ein früher verbundenes persönliches Postfach (``u<Objektnummer>``) wird getrennt, und was
über es lief, steht danach im Postfach des Betreibers. Die Anweisungen stehen in
``domain/communication.personal_repair_sql`` und laufen auch im Lifespan-Netz (#778).
Selbstbegrenzend.
"""
import sqlalchemy as sa
from alembic import op

from app.domain.communication import personal_repair_sql

revision = "149"
down_revision = "148"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT to_regclass('mailboxes')")).scalar():
        for stmt in personal_repair_sql():
            op.execute(sa.text(stmt))


def downgrade() -> None:
    pass        # ein getrenntes Postfach verbindet man neu – zurück gibt es nichts
