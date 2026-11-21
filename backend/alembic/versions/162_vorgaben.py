"""Vorgaben der Datenbank, die es fachlich nicht mehr gibt.

* ``user_profiles.role`` stand auf ``'customer'`` – eine Rolle, die ``people.ROLES`` nicht
  kennt. Eine Zeile ohne Angabe bekäme damit einen Zugang, den es nicht gibt.
* ``company_settings.company_name`` und ``email`` trugen «Inexxio AG» bzw.
  «info@inexxio.com» – eine Firma ohne Namen hiesse sonst wie wir.

Revision ID: 162
Revises: 161
"""

from alembic import op

revision = "162"
down_revision = "161"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_profiles ALTER COLUMN role SET DEFAULT 'user'")
    op.execute("ALTER TABLE company_settings ALTER COLUMN company_name DROP DEFAULT")
    op.execute("ALTER TABLE company_settings ALTER COLUMN email SET DEFAULT ''")


def downgrade() -> None:
    op.execute("ALTER TABLE user_profiles ALTER COLUMN role SET DEFAULT 'customer'")
    op.execute("ALTER TABLE company_settings ALTER COLUMN company_name SET DEFAULT 'Inexxio AG'")
    op.execute("ALTER TABLE company_settings ALTER COLUMN email SET DEFAULT 'info@inexxio.com'")
