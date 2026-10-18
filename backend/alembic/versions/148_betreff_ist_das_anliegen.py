"""Das Anliegen ist der Betreff – «Antwort auf» entfällt.

Was über ``message_replies`` beantwortet war, bleibt beantwortet: die Anweisungen stehen in
``domain/communication.topic_repair_sql`` und laufen auch im Lifespan-Netz (#778).
Selbstbegrenzend. Die Tabelle selbst fällt erst im Folge-Deploy (``docs/backlog.md``).
"""
import sqlalchemy as sa
from alembic import op

from app.domain.communication import topic_repair_sql

revision = "148"
down_revision = "147"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT to_regclass('message_replies')")).scalar():
        for stmt in topic_repair_sql():
            op.execute(sa.text(stmt))


def downgrade() -> None:
    pass        # der nachgetragene Betreff ist richtig – zurück gibt es nichts
