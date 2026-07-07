"""Rollback-Cleanup: verwaiste Lagerplatz-Instanzen deaktivieren.

Der Roll-back auf den Stand VOR «Lagerplatz-als-Instanz» stellt Code her, der
``instances.order_id`` wieder als PFLICHT (nicht-nullable) behandelt und ``InstanceResponse``
mit ``order_id: int`` serialisiert. Eine bereits angelegte Lagerplatz-Instanz hat aber
``order_id IS NULL`` (disposition='location') – sie würde den Instanz-Feed beim Serialisieren
brechen («keine Instanzen mehr angezeigt»).

Diese Instanzen werden hier **soft-deaktiviert** (``is_active=false``) und verschwinden damit
aus allen Feed-Abfragen (die alle ``is_active == True`` filtern). Die von 062 angelegten
Spalten (``articles.is_location``, ``instances.order_id`` nullable) bleiben bestehen – sie sind
für den zurückgerollten Code harmlos (nicht gemappte Extra-Spalte bzw. weichere DB-Constraint);
ein Drop wäre unnötig riskant.

Revision ID: 063
Revises: 062
Create Date: 2026-07-07
"""
from alembic import op
from sqlalchemy import inspect, text

revision = '063'
down_revision = '062'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "instances" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("instances")}
    if "order_id" not in cols or "is_active" not in cols:
        return
    # Vor 062 hatte KEINE Instanz order_id IS NULL (Spalte war nicht-nullable) – die Menge ist
    # also exakt die neu angelegten Lagerplatz-Instanzen.
    op.execute(text("UPDATE instances SET is_active = false WHERE order_id IS NULL"))


def downgrade() -> None:
    # Kein automatisches Reaktivieren (die Instanzen sind bewusst ausgeblendet).
    pass
