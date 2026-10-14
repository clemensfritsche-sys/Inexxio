"""Die Kontakt-E-Mail einer eigenen Gesellschaft ist die Adresse ihres Postfachs.

Wo ein verbundenes Postfach und die Kontakt-E-Mail auseinanderliegen, gewinnt das
Postfach – die Anweisung steht in ``domain/communication.contact_repair_sql`` und läuft
auch im Lifespan-Netz (#778). Selbstbegrenzend.
"""
import sqlalchemy as sa
from alembic import op

from app.domain.communication import contact_repair_sql

revision = "147"
down_revision = "146"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for stmt in contact_repair_sql():
        op.execute(sa.text(stmt))


def downgrade() -> None:
    pass        # die Adresse des Postfachs ist die richtige – zurück gibt es nichts
