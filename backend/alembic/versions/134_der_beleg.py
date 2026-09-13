"""Der Beleg — die vier Tabellen des neu aufgebauten Zahlungsmoduls

``docs/neuaufbau-zahlungsmodul.md``. Fachlich dasselbe wie ``deals``/``deal_entries``;
verschieden ist die **Form**: der Angebotsspiegel und die Positionen sind Tabellen statt
JSONB an der Kopfzeile, und die Positionen gibt es in **einer** Form statt in dreien.

**Drei Spalten des Vorgängers fehlen mit Absicht** – ``party_id``, ``amount`` und
``due_days`` sind Ableitungen der **gewählten Angebotszeile** (``state = 'gewaehlt'``).
Als Spalten daneben konnten sie der Zeile widersprechen, und eine eigene Regel musste das
verhindern.

**Der vollständige Spaltensatz, inklusive der geerbten** (``is_active``, ``created_at``,
``updated_at``) – die Lehre aus ``purchases.is_active``: dort nannte die Migration eine
geerbte Spalte nicht, lokal war es grün (``create_all`` hatte die Tabelle einmal
vollständig angelegt), und gegen ein Schema nur aus den Migrationen fiel jeder Lesezugriff
aus.

**Idempotent je Objekt** (Tabelle, Index): die dev-Datenbank kennt kein ``alembic
upgrade`` – dort legen ``create_all`` und die Netze in ``main.py`` nach, und eine Migration
mit einem einzigen «gibt es die erste Tabelle? dann fertig»-Wächter hinterliesse dort die
Indizes nie (die Lehre aus Migration 129).

Revision ID: 134
Revises: 133
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "134"
down_revision = "133"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return any(i["name"] == name for i in sa.inspect(op.get_bind()).get_indexes(table))


#: Was **jede** Tabelle des Hauses erbt (``Base`` + ``TimestampMixin``). Als Funktion und
#: nicht viermal abgeschrieben: eine vergessene geerbte Spalte ist genau die Lücke, durch
#: die Migration 114 gefallen ist.
def _base() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    if not _has_table("vouchers"):
        op.create_table(
            "vouchers",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("order_id", sa.BigInteger(), nullable=False),
            sa.Column("step_id", sa.BigInteger(), nullable=False),
            sa.Column("direction", sa.String(length=8), nullable=False,
                      server_default="out"),
            sa.Column("currency", sa.String(length=3), nullable=False,
                      server_default="CHF"),
            sa.Column("issuer_company_id", sa.BigInteger(), nullable=True),
            sa.Column("stage", sa.String(length=16), nullable=False,
                      server_default="offer"),
            sa.Column("agreed_on", sa.Date(), nullable=True),
            sa.Column("cancelled_on", sa.Date(), nullable=True),
            sa.Column("incoterm", sa.String(length=3), nullable=True),
            sa.Column("incoterm_place", sa.String(length=120), nullable=True),
            *_base(),
        )
    if not _has_index("vouchers", "ix_vouchers_order_id"):
        op.create_index("ix_vouchers_order_id", "vouchers", ["order_id"])
    if not _has_index("vouchers", "ix_vouchers_step_id"):
        op.create_index("ix_vouchers_step_id", "vouchers", ["step_id"])
    # **Ein AKTIVER Beleg je Modul** – partiell, weil ein zurückgenommener als Zeile
    # stehen bleibt (Soft-Delete); ein voller Index liesse danach keinen neuen mehr zu.
    if not _has_index("vouchers", "uq_vouchers_step"):
        op.create_index("uq_vouchers_step", "vouchers", ["step_id"], unique=True,
                        postgresql_where=sa.text("is_active"))

    if not _has_table("voucher_quotes"):
        op.create_table(
            "voucher_quotes",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("voucher_id", sa.BigInteger(), nullable=False),
            sa.Column("party_id", sa.BigInteger(), nullable=False),
            sa.Column("state", sa.String(length=16), nullable=False,
                      server_default="angefragt"),
            sa.Column("amount", sa.Numeric(18, 4), nullable=True),
            sa.Column("lead_days", sa.Integer(), nullable=True),
            sa.Column("payment_days", sa.Integer(), nullable=True),
            sa.Column("sent_on", sa.Date(), nullable=True),
            *_base(),
            sa.ForeignKeyConstraint(["voucher_id"], ["vouchers.id"],
                                    ondelete="CASCADE"),
        )
    if not _has_index("voucher_quotes", "ix_voucher_quotes_voucher_id"):
        op.create_index("ix_voucher_quotes_voucher_id", "voucher_quotes",
                        ["voucher_id"])
    if not _has_index("voucher_quotes", "ix_voucher_quotes_party_id"):
        op.create_index("ix_voucher_quotes_party_id", "voucher_quotes", ["party_id"])
    if not _has_index("voucher_quotes", "uq_voucher_quotes_party"):
        op.create_index("uq_voucher_quotes_party", "voucher_quotes",
                        ["voucher_id", "party_id"], unique=True,
                        postgresql_where=sa.text("is_active"))

    if not _has_table("voucher_lines"):
        op.create_table(
            "voucher_lines",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("voucher_id", sa.BigInteger(), nullable=False),
            sa.Column("article_id", sa.BigInteger(), nullable=True),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("price", sa.Numeric(18, 4), nullable=True),
            sa.Column("vat", sa.String(length=16), nullable=False,
                      server_default="normal"),
            sa.Column("hs_code", sa.String(length=12), nullable=True),
            sa.Column("origin_country", sa.String(length=60), nullable=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            *_base(),
            sa.ForeignKeyConstraint(["voucher_id"], ["vouchers.id"],
                                    ondelete="CASCADE"),
        )
    if not _has_index("voucher_lines", "ix_voucher_lines_voucher_id"):
        op.create_index("ix_voucher_lines_voucher_id", "voucher_lines", ["voucher_id"])
    if not _has_index("voucher_lines", "ix_voucher_lines_article_id"):
        op.create_index("ix_voucher_lines_article_id", "voucher_lines", ["article_id"])
    # **Ein Artikel, eine Zeile** – ``sync_lines`` läuft bei jeder Anzeige; zwei
    # gleichzeitige Aufrufe legten sonst dieselbe Position zweimal an. ``NULL`` kollidiert
    # in PostgreSQL nicht mit sich selbst, also bleiben mehrere **freie** Zeilen erlaubt.
    if not _has_index("voucher_lines", "uq_voucher_lines_article"):
        op.create_index("uq_voucher_lines_article", "voucher_lines",
                        ["voucher_id", "article_id"], unique=True,
                        postgresql_where=sa.text("is_active"))

    if not _has_table("voucher_entries"):
        op.create_table(
            "voucher_entries",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("voucher_id", sa.BigInteger(), nullable=False),
            sa.Column("kind", sa.String(length=10), nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("booked_on", sa.Date(), nullable=True),
            sa.Column("due_on", sa.Date(), nullable=True),
            sa.Column("reference", sa.String(length=120), nullable=True),
            sa.Column("note", sa.String(length=200), nullable=True),
            sa.Column("reverses_id", sa.BigInteger(), nullable=True),
            sa.Column("charge_id", sa.BigInteger(), nullable=True),
            sa.Column("method", sa.String(length=10), nullable=True),
            sa.Column("vat", JSONB(), nullable=True),
            sa.Column("service_date", sa.Date(), nullable=True),
            *_base(),
            sa.ForeignKeyConstraint(["voucher_id"], ["vouchers.id"],
                                    ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["reverses_id"], ["voucher_entries.id"],
                                    ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["charge_id"], ["voucher_entries.id"],
                                    ondelete="SET NULL"),
        )
    for col in ("voucher_id", "reverses_id", "charge_id"):
        name = f"ix_voucher_entries_{col}"
        if not _has_index("voucher_entries", name):
            op.create_index(name, "voucher_entries", [col])


def downgrade() -> None:
    # In umgekehrter Reihenfolge – die Fremdschlüssel zeigen auf ``vouchers``.
    for name in ("voucher_entries", "voucher_lines", "voucher_quotes", "vouchers"):
        if _has_table(name):
            op.drop_table(name)
