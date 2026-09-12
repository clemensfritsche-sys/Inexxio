"""086 – «Abbruch ausstehend» gibt es nicht mehr: der Abbruch ist sofort vollzogen.

Bisher blieb ein abgebrochener Auftrag ``released`` und wurde erst inaktiv, wenn sein
Folgeauftrag freigegeben war (bis dahin rücknehmbar). Ein Auftrag, den man abbrechen kann
und der danach weiterläuft, ist aber nicht abgebrochen. Ab jetzt ist er im selben Moment
inaktiv; ``orders.abort_into_id`` ist nur noch der Zeiger «fortgeführt in …».

Altbestand: jeder noch laufende Auftrag mit gesetztem ``abort_into_id`` hatte genau diesen
schwebenden Zustand – er wird hier nachgezogen (ein zurückgenommener Abbruch hat
``abort_into_id`` bereits auf NULL gesetzt, ist also nicht betroffen).

Revision ID: 086
Revises: 085
Create Date: 2026-07-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '086'
down_revision = '085'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "orders" not in set(inspect(bind).get_table_names()):
        return
    bind.execute(sa.text(
        "UPDATE orders SET status = 'inactive' "
        "WHERE abort_into_id IS NOT NULL AND status = 'released'"
    ))


def downgrade() -> None:
    # Der schwebende Zustand lässt sich nicht rekonstruieren (und soll es auch nicht).
    pass
