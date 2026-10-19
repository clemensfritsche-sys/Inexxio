"""Newsletter: Einwilligung als Nachweis, Versandart an der Nachricht.

* ``newsletter_consents`` – je An-/Abmeldung eine Zeile (Quelle, Wortlaut, Zeitpunkt).
* ``messages.group_id`` – Rundschreiben und Newsletter: je Empfänger eine Nachricht,
  alle zeigen auf die erste. ``messages.newsletter`` – Werbung mit Abmeldelink.
* Das frühere Häkchen ``user_profiles.newsletter_opt_in`` wird ein Nachweis
  (``domain/newsletter.legacy_repair_sql``); die Spalte fällt im Folge-Deploy.

Revision ID: 153
Revises: 152
"""

from alembic import op

from app.domain.newsletter import legacy_repair_sql

revision = "153"
down_revision = "152"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS newsletter_consents (
            id BIGSERIAL PRIMARY KEY,
            person_object_id BIGINT NOT NULL,
            subscribed BOOLEAN NOT NULL,
            source VARCHAR(20) NOT NULL,
            wording TEXT,
            at TIMESTAMPTZ NOT NULL,
            created_by BIGINT,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            is_active BOOLEAN NOT NULL
        )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_newsletter_consents_person_object_id "
               "ON newsletter_consents (person_object_id)")
    op.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS group_id BIGINT")
    op.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS newsletter BOOLEAN "
               "NOT NULL DEFAULT false")
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_group_id ON messages (group_id)")
    for stmt in legacy_repair_sql():
        op.execute(stmt)


def downgrade() -> None:
    pass
