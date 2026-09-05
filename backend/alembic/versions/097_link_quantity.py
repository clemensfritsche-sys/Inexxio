"""Materialfluss: wie viel eine Instanz an einen Auftrag ging (Notiz #413).

Die Reservierung wird bei Abschluss gelöst – danach war «wie viel ging da hinein?» nicht
mehr beantwortbar. Der Fluss braucht die Zahl aber genau dann noch: an seinen Kanten steht
«2 × 100000590», und der Abzweig zeigt, wie viel zurückkam (0, wenn verschrottet).

**Nullable, kein Backfill**: für Altbestand ist die Menge nicht rekonstruierbar; dort fällt
die Anzeige auf die abgeleitete Menge zurück (tolerant lesen, streng schreiben).

Revision ID: 097
Revises: 096
"""
import sqlalchemy as sa
from alembic import op

revision = "097"
down_revision = "096"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    # Idempotent: das Lifespan-Sicherheitsnetz legt die Spalte notfalls schon an (Lehre aus
    # Migration 090) – dann darf diese Revision nicht an «column already exists» scheitern.
    if not _has_column("instance_order_links", "quantity"):
        op.add_column("instance_order_links",
                      sa.Column("quantity", sa.Numeric(14, 3), nullable=True))


def downgrade() -> None:
    if _has_column("instance_order_links", "quantity"):
        op.drop_column("instance_order_links", "quantity")
