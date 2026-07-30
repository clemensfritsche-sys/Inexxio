"""Gebiets-/Multi-Gesellschaften-Aufteilung: Tabelle ``company_territories`` (ADR 006).

Eine **Region → Gesellschaft**-Zuweisung. Die Welt ist in feste Regionen partitioniert
(``services/geography.REGIONS``); jede Region gehört genau EINER Gesellschaft. Diese Tabelle
hält NUR die Abweichungen vom Default – eine Region ohne Zeile gehört dem **Betreiber**. So
gehört jeder Fleck der Erde jemandem (Totalität), ohne alle Länder pflegen zu müssen.

``region`` ist unique (ein Besitzer je Region), ``company_id`` → ``company_settings.id``.

**Neue Tabelle** – ``create_all()`` im Lifespan legt sie ohnehin an, falls diese Migration
nicht läuft; die Migration ist die SSOT. **Idempotent** (``IF NOT EXISTS``), damit ein erneuter
Lauf nach dem Lifespan-Netz nicht an «table already exists» scheitert und künftige Migrationen
blockiert.

Revision ID: 092
Revises: 091
"""

from alembic import op
import sqlalchemy as sa

revision = "092"
down_revision = "091"
branch_labels = None
depends_on = None


def _has_table(conn, name: str) -> bool:
    return sa.inspect(conn).has_table(name)


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_table(conn, "company_territories"):
        op.create_table(
            "company_territories",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("region", sa.String(length=10), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
        )
    # Unique je Region (ein Besitzer) + Index auf company_id – idempotent.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_company_territories_region "
        "ON company_territories (region)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_company_territories_company_id "
        "ON company_territories (company_id)"
    )


def downgrade() -> None:
    conn = op.get_bind()
    if _has_table(conn, "company_territories"):
        op.drop_table("company_territories")
