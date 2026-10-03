"""Die gekappte Rückführung: ``orders.returns_nothing``.

**Testnotiz #563.** Nimmt ein Unter-Auftrag ALLE Instanzen seines Verleihers und ist klar,
dass nichts zurückkommt, endet der Verleiher an dieser Stelle – er ist abgebrochen,
fortgeführt in diesem Auftrag. Das ist eine **Aussage über die Zukunft**, die das System
nicht selbst treffen kann: solange der Abzweig läuft, könnte das Material zurückkommen.

Die Kaskade nach oben braucht dafür keine zweite Regel: ein gekappter Auftrag deckt
niemanden mehr, also entscheidet die automatische Auflösung beim Verleiher sofort – und geht
eine Ebene höher, wenn der dadurch abgebrochen wird.

Revision ID: 101
Revises: 100
"""
import sqlalchemy as sa
from alembic import op

revision = "101"
down_revision = "100"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    # Idempotent (Lehre aus Migration 090): das Lifespan-Netz legt sie notfalls schon an.
    if not _has_column("orders", "returns_nothing"):
        op.add_column("orders", sa.Column("returns_nothing", sa.Boolean(), nullable=False,
                                          server_default=sa.text("false")))


def downgrade() -> None:
    if _has_column("orders", "returns_nothing"):
        op.drop_column("orders", "returns_nothing")
