"""Das Anliegen ist der Betreff – «Antwort auf» entfällt.

Was über ``message_replies`` beantwortet war, bleibt beantwortet. Die Anweisungen standen
bis Migration 152 in ``domain/communication.topic_repair_sql`` und liefen auch im
Lifespan-Netz; seit die Tabelle gedroppt ist (152), stehen sie nur noch hier.
Selbstbegrenzend.
"""
import sqlalchemy as sa
from alembic import op


revision = "148"
down_revision = "147"
branch_labels = None
depends_on = None

_TOPIC_REPAIR: tuple[str, ...] = (
    "UPDATE messages AS m SET subject = p.subject FROM message_replies AS r "
    "JOIN messages AS p ON p.id = r.reply_to_id WHERE r.message_id = m.id "
    "AND COALESCE(m.subject, '') = '' AND COALESCE(p.subject, '') <> ''",
    "INSERT INTO message_parties (message_id, person_object_id, role) "
    "SELECT DISTINCT r.message_id, p.sender_object_id, 'about' FROM message_replies AS r "
    "JOIN messages AS p ON p.id = r.reply_to_id JOIN messages AS m ON m.id = r.message_id "
    "WHERE p.sender_object_id <> m.sender_object_id AND NOT EXISTS (SELECT 1 FROM "
    "message_parties AS x WHERE x.message_id = r.message_id "
    "AND x.person_object_id = p.sender_object_id)",
)


def upgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT to_regclass('message_replies')")).scalar():
        for stmt in _TOPIC_REPAIR:
            op.execute(sa.text(stmt))


def downgrade() -> None:
    pass        # der nachgetragene Betreff ist richtig – zurück gibt es nichts
