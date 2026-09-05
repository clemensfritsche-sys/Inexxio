"""Unternehmen deaktivierbar: ``company_settings.is_active`` (Testnotiz #365).

Ein Standort/eine Gesellschaft kann geschlossen werden. Soft-Delete wie überall – die
Objektnummer bleibt auflösbar (sie hält historische Instanzen und steht auf alten Belegen).
**Ohne Reaktivierung**: eine wiedereröffnete Gesellschaft ist rechtlich eine andere (neue
UID/EIN, neues HR-Datum) und wird darum neu angelegt.

Neue **Spalte auf bestehender Tabelle** → steht auch im Lifespan-Safety-Net
(``main._COLUMN_SAFETY_NET``, 090-Lehre): ``company_settings`` wird von jedem Standort-Label
und von den öffentlichen Endpunkten gelesen; fehlt eine Spalte, die das Modell kennt, endet
JEDE dieser Abfragen in einem 500. **Idempotent**.

Revision ID: 095
Revises: 094
"""

from alembic import op
import sqlalchemy as sa

revision = "095"
down_revision = "094"
branch_labels = None
depends_on = None


def _cols(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("company_settings")}


def upgrade() -> None:
    conn = op.get_bind()
    if "is_active" not in _cols(conn):
        op.add_column(
            "company_settings",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if "is_active" in _cols(conn):
        op.drop_column("company_settings", "is_active")
