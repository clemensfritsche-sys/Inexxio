"""Ein Postfach je eigener Gesellschaft.

Der frühere eine Unternehmens-Kanal ``info`` wird ``c<Objektnummer>`` des Betreibers –
die Anweisungen stehen in ``domain/communication.info_repair_sql`` und laufen auch im
Lifespan-Netz (die dev-Datenbank fährt keine Migration, #778). Selbstbegrenzend.
"""
import sqlalchemy as sa
from alembic import op

from app.domain.communication import info_repair_sql

revision = "146"
down_revision = "145"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for stmt in info_repair_sql():
        op.execute(sa.text(stmt))


def downgrade() -> None:
    pass        # die Zuordnung zum Betreiber ist die richtige – zurück gibt es nichts
