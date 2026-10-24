"""Eine Stornierung ist eine Gegenbuchung — `deal_entries.reverses_id`

Gelöscht wird nichts mehr (Testnotizen #823/#824): eine Rechnungsnummer ist vergeben, ein
Beleg ist draussen. Storniert wird durch eine **Gegenzeile** – dieselbe Art, der negative
Betrag, und diese Spalte als Verweis auf die stornierte.

Die Summe stimmt damit von selbst (``balance`` rechnet beide) und braucht keinen
Sonderfall; das ist dieselbe Mechanik, mit der eine Gutschrift schon immer eine negative
Rechnung war (§9.11).

**Bestehende Daten bleiben unangetastet.** Zeilen, die früher über den Papierkorb weich
gelöscht wurden (``is_active = False``), bleiben genau das: sie nachträglich in
Gegenbuchungen zu verwandeln hiesse, eine Buchung zu erfinden, die niemand vorgenommen hat.

Revision ID: 126
Revises: 125
"""

from alembic import op
import sqlalchemy as sa

revision = "126"
down_revision = "125"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("deal_entries")}
    if "reverses_id" not in cols:
        op.add_column(
            "deal_entries",
            sa.Column("reverses_id", sa.BigInteger(), nullable=True),
        )
        op.create_foreign_key(
            "fk_deal_entries_reverses", "deal_entries", "deal_entries",
            ["reverses_id"], ["id"], ondelete="SET NULL",
        )
        op.create_index(
            "ix_deal_entries_reverses_id", "deal_entries", ["reverses_id"],
        )


def downgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("deal_entries")}
    if "reverses_id" in cols:
        op.drop_index("ix_deal_entries_reverses_id", table_name="deal_entries")
        op.drop_constraint("fk_deal_entries_reverses", "deal_entries",
                           type_="foreignkey")
        op.drop_column("deal_entries", "reverses_id")
