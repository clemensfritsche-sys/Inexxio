"""Das Material-Journal (ADR 007): append-only Buchungen statt rekonstruierter Vergangenheit.

Die drei Fragen des Nutzers – was muss ich JETZT mit was machen, was kommt als NÄCHSTES,
was ist PASSIERT – bekommen je eine Quelle. «Passiert» sind diese Zeilen: Menge X der
Instanz I wechselte von Topf (Halter·Qualität·Verbleib) A nach Topf B. Kein Update-Pfad,
kein Delete-Pfad – die Vergangenheit kann sich nicht mehr ändern.

Neue Tabelle → das Lifespan-``create_all`` deckt sie ab (ausserhalb der 090-Ausfallklasse);
diese Revision ist die Schema-SSOT.

Revision ID: 098
Revises: 097
"""
import sqlalchemy as sa
from alembic import op

revision = "098"
down_revision = "097"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    # Idempotent: das Lifespan-create_all kann die Tabelle schon angelegt haben.
    if _has_table("material_moves"):
        return
    op.create_table(
        "material_moves",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("instance_object_id", sa.BigInteger(), nullable=False),
        sa.Column("article_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("src_order_id", sa.BigInteger(), nullable=True),
        sa.Column("src_quality", sa.String(10), nullable=True),
        sa.Column("src_disposition", sa.String(12), nullable=True),
        sa.Column("dst_order_id", sa.BigInteger(), nullable=True),
        sa.Column("dst_quality", sa.String(10), nullable=True),
        sa.Column("dst_disposition", sa.String(12), nullable=True),
        sa.Column("note", sa.String(40), nullable=True),
    )
    op.create_index("ix_material_moves_instance_object_id", "material_moves", ["instance_object_id"])
    op.create_index("ix_material_moves_src_order_id", "material_moves", ["src_order_id"])
    op.create_index("ix_material_moves_dst_order_id", "material_moves", ["dst_order_id"])


def downgrade() -> None:
    if _has_table("material_moves"):
        op.drop_table("material_moves")
