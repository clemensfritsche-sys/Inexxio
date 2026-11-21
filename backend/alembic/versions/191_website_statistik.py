"""Die Website-Statistik: ``site_hits`` (Aufrufe, Klicks, Anfragen – ohne IP) und
``site_salts`` (der Schlüssel eines Tages, danach gelöscht).

Revision ID: 191
Revises: 190
"""

from alembic import op

revision = "191"
down_revision = "190"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE site_hits (
            id BIGSERIAL PRIMARY KEY,
            day DATE NOT NULL,
            kind VARCHAR(16) NOT NULL,
            visitor VARCHAR(16),
            path VARCHAR(300) NOT NULL,
            lang VARCHAR(2) NOT NULL,
            entry BOOLEAN NOT NULL,
            ref_host VARCHAR(120),
            utm_source VARCHAR(80),
            utm_campaign VARCHAR(80),
            entry_path VARCHAR(300),
            country VARCHAR(2),
            device VARCHAR(8) NOT NULL,
            value INTEGER,
            message_id BIGINT,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )""")
    op.execute("CREATE INDEX ix_site_hits_day_kind ON site_hits (day, kind)")
    op.execute("CREATE INDEX ix_site_hits_day_visitor ON site_hits (day, visitor)")
    op.execute("""
        CREATE TABLE site_salts (
            day DATE PRIMARY KEY,
            salt BYTEA NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS site_salts")
    op.execute("DROP TABLE IF EXISTS site_hits")
