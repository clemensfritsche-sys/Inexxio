"""Add invoice_same_as_shipping flag to user_profiles

Revision ID: 006
Revises: 005
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "invoice_same_as_shipping",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "invoice_same_as_shipping")
