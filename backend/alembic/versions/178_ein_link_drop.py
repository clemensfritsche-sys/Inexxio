"""Ein Link, zweiter Deploy: die Tabelle ``voucher_documents`` fällt – Migration 177 hat ihre
Links nach ``document_links`` übernommen und das Modell entmappt (Zwei-Deploy-Regel).

Revision ID: 178
Revises: 177
"""

from alembic import op

revision = "178"
down_revision = "177"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS voucher_documents")


def downgrade() -> None:
    raise RuntimeError("178 lässt sich nicht zurückdrehen – die Links stehen in document_links.")
