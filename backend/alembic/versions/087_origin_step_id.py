"""087 – ``orders.provisioning_step_id`` → ``origin_step_id``.

Dieselbe Frage, jetzt für JEDE Unter-Auftragsart: **aus welchem Schritt des Eltern-Auftrags
ist dieser Unter-Auftrag hervorgegangen?** Die Bereitstellung wartet für genau diesen Schritt;
eine Abweichung wurde an genau dieser Stelle gemeldet. Damit bekommt jeder Unter-Auftrag eine
Position im Ablauf und kann dort gezeigt werden, wo er entstanden ist – statt als Karte
irgendwo über dem Prozess.

Revision ID: 087
Revises: 086
Create Date: 2026-07-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '087'
down_revision = '086'
branch_labels = None
depends_on = None

OLD, NEW = "provisioning_step_id", "origin_step_id"


def _cols(insp) -> set:
    if "orders" not in set(insp.get_table_names()):
        return set()
    return {c["name"] for c in insp.get_columns("orders")}


def upgrade() -> None:
    cols = _cols(inspect(op.get_bind()))
    if OLD in cols and NEW not in cols:
        op.alter_column("orders", OLD, new_column_name=NEW)
    elif NEW not in cols and cols:
        op.add_column("orders", sa.Column(NEW, sa.BigInteger(), nullable=True))


def downgrade() -> None:
    cols = _cols(inspect(op.get_bind()))
    if NEW in cols and OLD not in cols:
        op.alter_column("orders", NEW, new_column_name=OLD)
