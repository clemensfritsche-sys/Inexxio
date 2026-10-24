"""Basis-Neuaufbau: Artikel → Instanz → Einzelinstanz.

Die Prozesslogik ist ersatzlos entfallen; mit ihr jede Tabelle, die einen Auftrag oder
einen Prozessschritt voraussetzt. Die Instanz wird neu aufgebaut: sie ist ab jetzt eine
**Gruppe**, kein Bestandsposten – ohne Menge, ohne Zustandsachsen, ohne Standort, ohne
Reservierung. Gearbeitet wird an der **Einzelinstanz** (``instance_units``), und die
Menge einer Instanz ist die Anzahl ihrer Einzelinstanzen.

**Destruktiv und ohne Rückwärtskompatibilität** – so beauftragt: Altdaten sind
irrelevant, die Tabellen werden nicht migriert, sondern verworfen. Der Rollback-Punkt
ist der Git-Tag ``rollback/basis-20260806`` plus ein DB-Dump (``scripts/dump-db.sh``).

``downgrade`` stellt die Struktur der neuen Tabellen zurück, aber **nicht die alte
Welt**: was gedroppt wurde, ist weg. Ein ehrliches Downgrade wäre eine Lüge – die
Wiederherstellung läuft über den Dump.

Revision ID: 102
Revises: 101
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "102"
down_revision = "101"
branch_labels = None
depends_on = None


# Tabellen der entfernten Prozesslogik. Jede von ihnen setzt einen Auftrag oder einen
# Prozessschritt voraus; ohne den ist sie sinnlos, nicht bloss ungenutzt.
_DROP = (
    "material_moves",          # Material-Journal (ADR 007)
    "instance_order_links",    # Verarbeitungs-Historie Instanz ↔ Auftrag
    "inspections",             # Datenerfassung am Schritt → ersetzt durch captures
    "movements",               # Bewegung
    "disposals",               # Aussondern (verschrotten/sperren)
    "resource_usages",         # Verbrauch / Betriebsmittel
    "shipments",               # Versandbeleg
    "purchase_orders",         # Beschaffung
    "sales",                   # Verkaufs-/Gutschriftsbeleg
    "documents",               # Prozessschritt-Dokument (order_id NOT NULL)
    "checkout_intents",        # Warenkorb → Auftrag (aufgeschoben)
    "order_lines",             # Positionen
    "article_process_steps",   # die Prozessdefinition selbst
    "orders",                  # der Auftrag
)


def upgrade() -> None:
    for table in _DROP:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    # Die Instanz wird neu aufgebaut statt umgebaut: von ihren 19 Spalten überlebt keine
    # einzige Fachaussage (Menge, Qualität, Verbleib, Standort, Reservierung, Stücke-Map).
    # Ein ALTER mit 15 DROP COLUMN wäre derselbe Vorgang, nur unleserlich.
    op.execute("DROP TABLE IF EXISTS instances CASCADE")

    op.create_table(
        "instances",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("object_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("article_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="new"),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_instances_object_id", "instances", ["object_id"])
    op.create_index("ix_instances_article_id", "instances", ["article_id"])

    op.create_table(
        "instance_units",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instance_id", sa.BigInteger(), nullable=False),
        # Kumulierend: MAX(suffix)+1 unter Zeilensperre. Der Unique-Index ist der zweite
        # Riegel – ohne ihn könnte eine Nebenläufigkeit dieselbe Nummer zweimal vergeben,
        # und eine doppelte Nummer wäre schlimmer als ein Fehlschlag.
        sa.Column("suffix", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("instance_id", "suffix", name="uq_instance_units_instance_suffix"),
    )
    op.create_index("ix_instance_units_instance_id", "instance_units", ["instance_id"])

    op.create_table(
        "captures",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instance_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("values", JSONB(), nullable=False),
        # NULL heisst «nichts Bewertbares erfasst» – kein erfundenes «bestanden».
        sa.Column("result", sa.String(length=10), nullable=True),
        sa.Column("captured_by", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_captures_instance_unit_id", "captures", ["instance_unit_id"])

    # Die Erfassungsmaske zieht vom Prozessschritt an den Artikel um. Neue Spalte auf einer
    # BESTEHENDEN Tabelle – sie steht zusätzlich im Lifespan-Sicherheitsnetz (Lehre aus 090).
    op.execute("ALTER TABLE articles ADD COLUMN IF NOT EXISTS capture_fields JSONB")

    # Der Objektnummern-Kreis kennt keinen Auftrag mehr; die Registry-Zeilen der
    # verschwundenen Aufträge zeigen ins Leere. Die Registry selbst wird nicht von
    # Alembic angelegt, sondern beim Start (``main._ensure_object_registry_shape``) –
    # auf einer frischen Datenbank gibt es sie hier also noch nicht.
    op.execute(
        "DO $$ BEGIN IF to_regclass('public.objects') IS NOT NULL THEN "
        "DELETE FROM objects WHERE object_type = 'order'; END IF; END $$"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE articles DROP COLUMN IF EXISTS capture_fields")
    op.execute("DROP TABLE IF EXISTS captures CASCADE")
    op.execute("DROP TABLE IF EXISTS instance_units CASCADE")
    op.execute("DROP TABLE IF EXISTS instances CASCADE")
    # Die Tabellen der Prozesslogik kommen hier NICHT zurück. Sie stehen im Dump; ein
    # leeres Gerüst ohne Inhalt wäre schlimmer als ihre Abwesenheit, weil es Betrieb
    # vortäuscht, den es nicht gibt.
