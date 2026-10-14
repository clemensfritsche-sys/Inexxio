"""Eine Zahlung gehört zu genau EINER Rechnung — `deal_entries.charge_id`

«Wenn ich eine Rechnung ausstelle, dann wird eine Zahlung auf genau diese Rechnung
referenziert. Ich soll nicht eine Zahlung für zwei verschiedene Rechnungen erfassen
können – dann lieber die 2 Rechnungen stornieren und eine daraus machen und die wird dann
bezahlt. Ansonsten ist es glaube ich nicht sauber.» (Testnotiz #858)

**Das ist die einfachere Regel und nicht die ärmere.** Der Weg für «eine Überweisung über
zwei Rechnungen» ist eine Stornorechnung und eine gemeinsame neue – ein Vorgang, den es
längst gibt, mit einem Beleg, den man vorzeigen kann. Die Alternative wäre eine
Aufteilungstabelle (das *Ausziffern* offener Posten) für eine Zahl, die daneben ohnehin
als Summe steht.

**Der Saldo bleibt unberührt.** ``domain/deal.balance`` rechnet weiter über die Summen
aller Zeilen; diese Spalte beantwortet «worauf», nicht «wie viel». Zwei Fragen, ein Feld
je Frage – und deshalb ändert sich an keiner bestehenden Zahl etwas.

``NULL`` ist regulär und heisst «nicht zugeordnet»: so stehen die Zahlungen da, die es vor
dieser Regel schon gab. Sie werden **nicht** nachträglich zugeordnet – eine geratene
Zuordnung wäre eine Behauptung über einen Beleg, und genau das soll die Spalte verhindern.

Revision ID: 129
Revises: 128
"""

from alembic import op
import sqlalchemy as sa

revision = "129"
down_revision = "128"
branch_labels = None
depends_on = None


def _has_column(table: str, name: str) -> bool:
    bind = op.get_bind()
    return any(c["name"] == name for c in sa.inspect(bind).get_columns(table))


def _has_index(table: str, name: str) -> bool:
    bind = op.get_bind()
    return any(i["name"] == name for i in sa.inspect(bind).get_indexes(table))


def _has_fk(table: str, name: str) -> bool:
    bind = op.get_bind()
    return any(f["name"] == name for f in sa.inspect(bind).get_foreign_keys(table))


def upgrade() -> None:
    # ►►► **Idempotent JE OBJEKT, nicht als Ganzes.** ◄◄◄
    #
    # Die dev-Datenbank kennt kein `alembic upgrade` – dort legt das **Spalten**-Netz in
    # `main.py` nach, und zwar nur die Spalte. Ein `if Spalte da: return` hiesse damit,
    # dass Index und Fremdschlüssel **genau dort nie ankommen**, wo das System läuft
    # (dieselbe Lehre wie Testnotiz #778: eine Index-Änderung, die nur in einer Migration
    # steht, erreicht dev nie). Gemessen: nach einem von Hand angelegten `charge_id` lief
    # die Migration «erfolgreich» durch und hinterliess die Tabelle ohne Index.
    if not _has_column("deal_entries", "charge_id"):
        op.add_column("deal_entries",
                      sa.Column("charge_id", sa.BigInteger(), nullable=True))
    if not _has_index("deal_entries", "ix_deal_entries_charge_id"):
        op.create_index("ix_deal_entries_charge_id", "deal_entries", ["charge_id"])
    # **`SET NULL` und nicht `CASCADE`**: eine Zahlung ist ein Ereignis der Aussenwelt und
    # verschwindet nicht, weil ein Beleg verschwindet. (Gelöscht wird hier ohnehin nichts –
    # storniert wird durch eine Gegenbuchung; der Fremdschlüssel ist das Netz darunter.)
    if not _has_fk("deal_entries", "fk_deal_entries_charge"):
        op.create_foreign_key("fk_deal_entries_charge", "deal_entries", "deal_entries",
                              ["charge_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    if _has_fk("deal_entries", "fk_deal_entries_charge"):
        op.drop_constraint("fk_deal_entries_charge", "deal_entries", type_="foreignkey")
    if _has_index("deal_entries", "ix_deal_entries_charge_id"):
        op.drop_index("ix_deal_entries_charge_id", table_name="deal_entries")
    if _has_column("deal_entries", "charge_id"):
        op.drop_column("deal_entries", "charge_id")
