"""Deactivate duplicate user account with object_id 100000003

Revision ID: 005
Revises: 004
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE user_profiles
            SET is_active = false,
                email = 'deleted_100000003@deleted.invalid',
                updated_at = NOW()
            WHERE object_id = 100000003
              AND is_active = true
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE objects
            SET is_active = false,
                updated_at = NOW()
            WHERE id = 100000003
              AND object_type = 'user'
            """
        )
    )


def downgrade() -> None:
    pass
