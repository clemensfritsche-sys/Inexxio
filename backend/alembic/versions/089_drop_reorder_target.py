"""«Zielbestand» am Artikel ersatzlos entfernt.

Zwei Zahlen beantworteten dieselbe Frage: `safety_stock` («ab wann nachbestellen?») und
`reorder_target` («bis wohin auffüllen?»). Die zweite blieb in der Praxis fast immer leer –
und dann füllte die Nachbestellung ohnehin auf den Sicherheitsbestand auf. Genau das ist
jetzt die einzige Regel: **es wird auf den Sicherheitsbestand aufgefüllt.**

Revision ID: 089
Revises: 088
"""

from alembic import op
import sqlalchemy as sa

revision = "089"
down_revision = "088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("articles", "reorder_target")


def downgrade() -> None:
    op.add_column("articles", sa.Column("reorder_target", sa.Numeric(12, 3), nullable=True))
