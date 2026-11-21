"""Die Richtung einer Nachricht: kam sie von aussen zu uns? (``messages.inbound``)

Bisher galt «von uns», wenn der Absender Mitarbeiter ist. Das verwechselt die Person mit dem
Weg: schreibt ein Mitarbeiter von seiner privaten Adresse an das Postfach der Gesellschaft,
kam die Mail von aussen – und eine Mail, die die Gesellschaft selbst schickt (Bestätigung,
Beleg), hat gar keinen Menschen als Absender. Die Richtung ist darum eine Tatsache der
Nachricht, festgehalten, wenn sie entsteht.

Bestand: von aussen ist, was nicht von einem Mitarbeiter und nicht von einer eigenen
Gesellschaft kam – genau die bisherige Lesart, nur jetzt festgeschrieben.

Revision ID: 183
Revises: 182
"""

from alembic import op

revision = "183"
down_revision = "182"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE messages ADD COLUMN inbound boolean NOT NULL DEFAULT false")
    op.execute("""
UPDATE messages m SET inbound = true
 WHERE NOT EXISTS (SELECT 1 FROM user_profiles u WHERE u.object_id = m.sender_object_id
                     AND u.role IN ('admin', 'employee'))
   AND NOT EXISTS (SELECT 1 FROM company_settings c WHERE c.object_id = m.sender_object_id
                     AND c.is_own)""")


def downgrade() -> None:
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS inbound")
