"""083 – Anmeldeweg am Benutzer festhalten.

Das Firebase-ID-Token nennt bei jeder Anfrage, **wie** sich die Person angemeldet hat
(``firebase.sign_in_provider``: google.com | password | emailLink | custom = Passkey).
Bisher wurde das verworfen – am ERP-Benutzer-Datensatz war damit nicht beantwortbar,
worüber jemand überhaupt hereinkommt. Die Spalte ist rein deskriptiv (kein Gate) und
wird bei jedem Login mitgeschrieben.

Revision ID: 083
Revises: 082
Create Date: 2026-07-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '083'
down_revision = '082'
branch_labels = None
depends_on = None

TABLE = "user_profiles"
COLUMN = "last_sign_in_provider"


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if TABLE not in set(insp.get_table_names()):
        return
    if COLUMN not in {c["name"] for c in insp.get_columns(TABLE)}:
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(length=40), nullable=True))


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if TABLE in set(insp.get_table_names()):
        if COLUMN in {c["name"] for c in insp.get_columns(TABLE)}:
            op.drop_column(TABLE, COLUMN)
