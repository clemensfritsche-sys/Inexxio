"""Der Beleg IST die Rechnung — acht Spalten wandern eine Ebene hoch

►►► **Die Rechnung stand zweimal da.** ◄◄◄

    vouchers        Partner · Positionen · MWST · Währung · Fristen · Incoterm
      └─ entries    «charge»: Betrag · MWST · Nummer · Datum · Fälligkeit · Leistungsdatum

Betrag, Steuer, Nummer, Datum und Fälligkeit standen auf **beiden** Ebenen: die
Forderungs-Zeile war eine Kopie des Belegs, der sie enthielt – dieselbe Fehlerform, die
der Neuaufbau bei den Positionen schon einmal beseitigt hat (dort gab es sie dreimal).

Danach **ist** der Beleg die Rechnung. Damit kann es sie nicht zweimal geben, und «eine
Rechnung je Modul» ist keine Regel mehr, die eine Funktion zählt (`live_charge`), sondern
die **Struktur**. Eine **Korrektur** ist ein eigener Beleg in einem eigenen Modul
(`corrects_id`) – und der darf über Auftragsgrenzen zeigen: die Gutschrift gehört dorthin,
wo die Ware zurückkommt.

## Was hier passiert

1. **Acht Spalten an `vouchers`** – genau die acht, die die Zeile verliert.
2. **`voucher_entries.kind` wird lösbar** (nullable + Server-Default): das Modell kennt
   sie nicht mehr, und ohne den Default liefe jedes Insert auf. Gedroppt wird im
   Folge-Deploy (Zwei-Deploy-Regel, `docs/backlog.md`).
3. **Der Backfill** – die bestehende Forderung wandert an ihren Beleg:
   * **Betrag** = Summe **aller** lebenden `charge`-Zeilen. Das ist exakt die Zahl, die
     vorher galt: ein Storno-Paar hebt sich auf, eine Gutschrift mindert. Den Betrag der
     ersten Zeile zu nehmen verfälschte jeden Beleg, an dem je korrigiert wurde.
   * **Nummer, Datum, Fälligkeit, Steuer, Leistungsdatum** von der ältesten Zeile, die
     nicht selbst Gegenbuchung ist und zu der es keine gibt – also von der, die *gilt*.
     Gibt es keine solche (alles storniert), bekommt der Beleg **keine** Rechnung und
     bleibt auf «Auftrag»: stornieren und neu stellen war der Ausweg, und «neu gestellt»
     heisst hier «noch keine Rechnung».
   * **`issued_on` = Rechnungsdatum**: was gebucht ist, gilt als hinausgegangen. Die
     vorsichtigere Annahme – sonst liesse sich eine längst versendete Rechnung
     zurücknehmen.
4. **Jede `charge`-Zeile wird inaktiv.** Das ist nicht Kosmetik, sondern zwingend: nach
   dem Umbau liest der Dienst jede aktive Zeile als **Zahlung**, und eine
   stehengebliebene Forderung zählte als Geldeingang.

## Die eine benannte Ungenauigkeit

Wo ein Beleg mehrere Forderungen trug, stimmt der **Betrag** (die Summe), die
**Steueraufteilung** aber stammt von der ersten Zeile. Ein exakter Neu-Split wäre eine
Rechnung über Zahlen, die niemand mehr prüfen kann. **Vertretbar, weil es keine
produktiven Belege gibt**: das Deployment ist `inexxio-dev`, die Daten sind Testdaten.
Gäbe es echte Rechnungen, wäre dieser Schritt eine eigene Runde mit vorheriger Sicherung.

Revision ID: 138
Revises: 137
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# **Die Ableitung steht an EINER Stelle** – die dev-Datenbank fährt kein
# ``alembic upgrade head``, also braucht sie das Lifespan-Netz ebenfalls (Testnotiz #778).
# Zweimal ausgeschrieben wären es zwei Wahrheiten; dieselbe Bauart wie der Endzustands-
# Trigger in Migration 110.
from app.domain.voucher import invoice_backfill_sql

revision = "138"
down_revision = "137"
branch_labels = None
depends_on = None


#: Die acht Angaben, die von der Zeile an den Beleg wandern.
_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("billed_on", sa.Date()),
    ("due_on", sa.Date()),
    ("number", sa.String(120)),
    ("issued_on", sa.Date()),
    ("amount", sa.Numeric(18, 4)),
    ("vat", postgresql.JSONB(astext_type=sa.Text())),
    ("service_date", sa.Date()),
    ("corrects_id", sa.BigInteger()),
)


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return any(c["name"] == name for c in sa.inspect(op.get_bind()).get_columns(table))


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return any(i["name"] == name for i in sa.inspect(op.get_bind()).get_indexes(table))


def _nullable(table: str, name: str) -> bool:
    if not _has_column(table, name):
        return True
    return next(c["nullable"] for c in sa.inspect(op.get_bind()).get_columns(table)
                if c["name"] == name)


def upgrade() -> None:
    if not _has_table("vouchers"):
        return

    # **Idempotent je Objekt, nicht je Tabelle** (die Lehre aus Migration 129): auf dev
    # legt das Spalten-Netz die Spalte an und sonst nichts – ein Wächter der Form «Tabelle
    # da → fertig» liesse Index und Fremdschlüssel dort für immer fehlen.
    for name, kind in _COLUMNS:
        if not _has_column("vouchers", name):
            op.add_column("vouchers", sa.Column(name, kind, nullable=True))

    if not _has_index("vouchers", "ix_vouchers_corrects_id"):
        op.create_index("ix_vouchers_corrects_id", "vouchers", ["corrects_id"])
    # **Der Verweis zeigt auf einen Beleg, nicht auf eine Zeile** – und er darf über
    # Auftragsgrenzen gehen. `SET NULL`: verschwindet der Originalbeleg, bleibt die
    # Gutschrift als Buchung bestehen; sie hätte nur keinen Bezug mehr.
    if not any(f["name"] == "fk_vouchers_corrects"
               for f in sa.inspect(op.get_bind()).get_foreign_keys("vouchers")):
        op.create_foreign_key("fk_vouchers_corrects", "vouchers", "vouchers",
                              ["corrects_id"], ["id"], ondelete="SET NULL")

    # ►►► **`kind` verliert seine Sperre, bevor das Modell sie vergisst.** ◄◄◄ Sie ist
    # `NOT NULL` ohne Server-Default – ohne diesen Schritt liefe jedes Insert einer Zahlung
    # auf. Dieselbe Zwei-Schritte-Regel wie bei `purchases.quantity` (Migration 115).
    if _has_column("voucher_entries", "kind"):
        if not _nullable("voucher_entries", "kind"):
            op.alter_column("voucher_entries", "kind", nullable=True,
                            server_default=sa.text("'payment'"))
        else:
            op.alter_column("voucher_entries", "kind",
                            server_default=sa.text("'payment'"))

    if not _has_column("voucher_entries", "kind"):
        return

    # ►►► **Der Backfill.** ◄◄◄ Zwei Ableitungen über dieselben Zeilen, und sie stehen in
    # ``domain/voucher.invoice_backfill_sql`` – die Migration ist die Wahrheit, das
    # Lifespan-Netz der zweite Weg, und beim Ausfall zählt nur der zweite.
    #
    # **Die Forderungs-Zeilen gehen dabei aus dem Weg** (zweite Anweisung). Das ist nicht
    # Kosmetik, sondern zwingend: nach dem Umbau liest der Dienst jede aktive Zeile als
    # **Zahlung**, und eine stehengebliebene Forderung zählte als Geldeingang.
    for stmt in invoice_backfill_sql():
        op.execute(sa.text(stmt))


def downgrade() -> None:
    # **Die Zeilen kommen nicht zurück** – sie stehen noch da (Soft-Delete), also genügt
    # es, sie wieder sichtbar zu machen und die hochgezogenen Angaben zu leeren.
    if _has_column("voucher_entries", "kind"):
        op.execute(sa.text(
            "UPDATE voucher_entries SET is_active = true WHERE kind = 'charge'"))
        op.alter_column("voucher_entries", "kind", server_default=None)
        op.alter_column("voucher_entries", "kind", nullable=False)
    if _has_table("vouchers"):
        op.execute(sa.text("UPDATE vouchers SET stage = 'agreed' WHERE stage = 'billed'"))
        if any(f["name"] == "fk_vouchers_corrects"
               for f in sa.inspect(op.get_bind()).get_foreign_keys("vouchers")):
            op.drop_constraint("fk_vouchers_corrects", "vouchers", type_="foreignkey")
        if _has_index("vouchers", "ix_vouchers_corrects_id"):
            op.drop_index("ix_vouchers_corrects_id", table_name="vouchers")
        for name, _kind in _COLUMNS:
            if _has_column("vouchers", name):
                op.drop_column("vouchers", name)
