"""Newsletter: Einwilligung als Nachweis, Versandart an der Nachricht.

* ``newsletter_consents`` – je An-/Abmeldung eine Zeile (Quelle, Wortlaut, Zeitpunkt).
* ``messages.group_id`` – Rundschreiben und Newsletter: je Empfänger eine Nachricht,
  alle zeigen auf die erste. ``messages.newsletter`` – Werbung mit Abmeldelink.
* Das frühere Häkchen ``user_profiles.newsletter_opt_in`` wird ein Nachweis (Quelle
  «legacy»); die Spalte fiel in ``161``. Die SQL steht hier wörtlich (wie bei ``152``) –
  die Fachschicht kennt die Spalte nicht mehr.

Revision ID: 153
Revises: 152
"""

from alembic import op

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
    op.execute("INSERT INTO newsletter_consents (person_object_id, subscribed, source, wording, "
               "at, created_at, updated_at, is_active) "
               "SELECT u.object_id, true, 'legacy', NULL, now(), now(), now(), true "
               "FROM user_profiles u WHERE u.newsletter_opt_in AND u.object_id IS NOT NULL "
               "AND NOT EXISTS (SELECT 1 FROM newsletter_consents c "
               "WHERE c.person_object_id = u.object_id)")


def downgrade() -> None:
    pass
