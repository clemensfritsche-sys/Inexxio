"""Die Sammelzahlung und der Grund — `voucher_allocations` + `voucher_entries.reason`

►►► **Zwei Entitäten, und sonst nichts.** ◄◄◄

    Beleg    (Betrag ±, MWST, Belegnummer, Fälligkeit, Grund, Referenz-Beleg)
    Zahlung  (Betrag ±, Zuordnung zu Beleg(en), Zahlungsart)
    Saldo  = Σ Beleg − Σ Zahlung   → immer gerechnet, NIE gespeichert

**Einen Belegtyp gibt es im Code nicht** – und es gab ihn hier auch nie: `voucher_entries`
trägt `kind ∈ {charge, payment}`, also genau die beiden Entitäten oben, und **das
Vorzeichen** sagt, ob gefordert oder korrigiert wird. Es ist darum nichts zu migrieren:
keine Enum-Werte *Rechnung · Storno · Gutschrift · Ausbuchung*, keine Verzweigung darauf,
keine Belegnummer, die sich ändert.

Was fehlte, sind zwei Dinge:

**(1) `voucher_entries.reason`** – *warum* korrigiert wird (Retoure · Mangel · Kulanz ·
Rechnungsfehler · uneinbringlich · Rundungsdifferenz). **Freitext ohne Logik dahinter**:
nichts im System verzweigt darauf, der Katalog ist ein Vorschlag. Das ist die Stelle, an
der ein Belegtyp stünde, wenn es einen gäbe – und der Unterschied ist, dass ein Grund
nichts *tut*.

**(2) `voucher_allocations`** – eine Zahlung darf auf **mehrere** Belege gehen. Eine
Überweisung über 1'500 begleicht eine Rechnung über 1'000 und eine über 500: auf dem
Kontoauszug steht **eine** Zeile, und eine zweite zu erfinden hiesse, die Wirklichkeit dem
Datenmodell anzupassen. Bisher trug `voucher_entries.charge_id` genau eine Zuordnung.

**Die Spalte bleibt** – als Abkürzung für den einfachen Fall, geschrieben von derselben
einen Stelle (`voucher.allocate`). **Gelesen wird nur die Tabelle** (`voucher.paid_map`);
zwei Lesestellen wären genau der Ort, an dem eine Sammelzahlung halb ankommt. Die
bestehenden Zuordnungen werden darum **übernommen**, sonst verlöre jede bezahlte Rechnung
ihren Stand – ein Backfill, kein Neuaufbau.

`balance` bleibt unangetastet: es rechnet über die **Summen** aller Zeilen. Diese Tabelle
beantwortet allein «was ist auf *dieser* Rechnung noch offen».

Revision ID: 137
Revises: 136
"""

from alembic import op
import sqlalchemy as sa

revision = "137"
down_revision = "136"
branch_labels = None
depends_on = None


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


def upgrade() -> None:
    # **Idempotent je Objekt, nicht je Tabelle** (die Lehre aus Migration 129): auf dev
    # legt das Spalten-Netz die Spalte an und sonst nichts – ein Wächter der Form «Tabelle
    # da → fertig» liesse Index und Fremdschlüssel dort für immer fehlen.
    if not _has_column("voucher_entries", "reason"):
        op.add_column("voucher_entries", sa.Column("reason", sa.String(120), nullable=True))

    if not _has_table("voucher_allocations"):
        op.create_table(
            "voucher_allocations",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("payment_id", sa.BigInteger(), nullable=False),
            sa.Column("charge_id", sa.BigInteger(), nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False),
            # **Der vollständige Spaltensatz des Modells** – inklusive der geerbten.
            # Genau hier ist `purchases.is_active` einmal gelandet (Migration 114):
            # lokal grün, weil `create_all` die Tabelle angelegt hatte, und gegen ein
            # Schema nur aus den Migrationen fiel jeder Lesezugriff aus.
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["payment_id"], ["voucher_entries.id"],
                                    ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["charge_id"], ["voucher_entries.id"],
                                    ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if _has_table("voucher_allocations"):
        if not _has_index("voucher_allocations", "ix_voucher_allocations_payment_id"):
            op.create_index("ix_voucher_allocations_payment_id",
                            "voucher_allocations", ["payment_id"])
        if not _has_index("voucher_allocations", "ix_voucher_allocations_charge_id"):
            op.create_index("ix_voucher_allocations_charge_id",
                            "voucher_allocations", ["charge_id"])
        # **Eine Zeile je Paar**: zweimal dieselbe Rechnung aus derselben Zahlung zu
        # bedienen ist keine zweite Zuordnung, sondern ein höherer Betrag. Partiell,
        # weil eine zurückgenommene Zeile als Soft-Delete stehenbleibt.
        if not _has_index("voucher_allocations", "uq_voucher_allocations"):
            op.create_index("uq_voucher_allocations", "voucher_allocations",
                            ["payment_id", "charge_id"], unique=True,
                            postgresql_where=sa.text("is_active"))

        # ►►► **Der Backfill** – die bestehende Zuordnung wird übernommen, nicht
        # neu gedacht: jede Zahlung mit `charge_id` bekommt ihre eine Zeile über ihren
        # vollen Betrag. Ohne ihn stünde jede bezahlte Rechnung wieder auf «offen».
        op.execute(sa.text("""
            INSERT INTO voucher_allocations
                (payment_id, charge_id, amount, is_active, created_at, updated_at)
            SELECT p.id, p.charge_id, p.amount, true, now(), now()
              FROM voucher_entries p
             WHERE p.kind = 'payment'
               AND p.charge_id IS NOT NULL
               AND p.is_active
               AND NOT EXISTS (
                     SELECT 1 FROM voucher_allocations a
                      WHERE a.payment_id = p.id AND a.charge_id = p.charge_id)
        """))


def downgrade() -> None:
    if _has_table("voucher_allocations"):
        op.drop_table("voucher_allocations")
    if _has_column("voucher_entries", "reason"):
        op.drop_column("voucher_entries", "reason")
