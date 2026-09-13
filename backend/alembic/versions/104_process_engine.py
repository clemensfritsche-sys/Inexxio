"""Die Prozesslogik: Definition, Zugehörigkeit, Ereignis-Log.

Drei neue Tabellen (die drei Ebenen aus PROCESS_CORE.md §10) und zwei neue Spalten am
Auftrag.

Das Herzstück ist der **partielle Unique-Index** ``uq_order_units_active``: er ist die
Exklusivitätsregel (§3) und die einzige Stelle, an der sie nicht umgangen werden kann.
In der Anwendungslogik geprüft, lesen zwei gleichzeitige Freigaben beide «ist frei» und
schreiben beide.

``instance_units.status`` trug bisher den Platzhalter ``new`` aus dem Basis-Neuaufbau –
ein Feld ohne Logik. Mit der geschlossenen Statusliste (§5) gibt es diesen Wert nicht
mehr; er wird auf ``freigegeben`` gezogen: ein Stück, das in keinem Auftrag steckt, ist
einsatzbereit, und genau das heisst das Wort.

Revision ID: 104
Revises: 103
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "104"
down_revision = "103"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return bool(
        bind.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).first()
    )


def upgrade() -> None:
    # ── Auftrag: Lebenszyklus + der EINE Ort des Endzustands ──────────────────
    # Idempotent, weil das Lifespan-Sicherheitsnetz dieselben Spalten anlegt, falls
    # Alembic bei einem Deploy scheitert (Lehre aus Migration 090).
    if not _has_column("orders", "status"):
        op.add_column(
            "orders",
            sa.Column("status", sa.String(20), nullable=False,
                      server_default=sa.text("'released'")),
        )
    if not _has_column("orders", "end_status"):
        op.add_column(
            "orders",
            sa.Column("end_status", sa.String(30), nullable=False,
                      server_default=sa.text("'freigegeben'")),
        )

    # ── Ebene 1: die Prozessdefinition ────────────────────────────────────────
    op.execute("DROP TABLE IF EXISTS process_steps CASCADE")
    op.create_table(
        "process_steps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("module_type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status_before", sa.String(30), nullable=False),
        sa.Column("status_after", sa.String(30), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_process_steps_order_id", "process_steps", ["order_id"])

    # ── Zugehörigkeit + Exklusivität ──────────────────────────────────────────
    op.execute("DROP TABLE IF EXISTS order_units CASCADE")
    op.create_table(
        "order_units",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("instance_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("current_step_id", sa.BigInteger(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_order_units_order_id", "order_units", ["order_id"])
    op.create_index("ix_order_units_instance_unit_id", "order_units", ["instance_unit_id"])
    # ►► DIE Exklusivitätsregel. Eine Einzelinstanz kann höchstens eine Zeile ohne
    #    ``released_at`` haben – «aktiv in zwei Aufträgen» ist damit nicht speicherbar.
    op.execute(
        "CREATE UNIQUE INDEX uq_order_units_active ON order_units (instance_unit_id) "
        "WHERE released_at IS NULL"
    )

    # ── Ebene 3: der Ereignis-Log ─────────────────────────────────────────────
    op.execute("DROP TABLE IF EXISTS process_events CASCADE")
    op.create_table(
        "process_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("step_id", sa.BigInteger(), nullable=True),
        sa.Column("instance_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("status_before", sa.String(30), nullable=False),
        sa.Column("status_after", sa.String(30), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_process_events_order_id", "process_events", ["order_id"])
    op.create_index("ix_process_events_unit", "process_events", ["instance_unit_id"])

    # ── Der Platzhalter-Status weicht der geschlossenen Liste ─────────────────
    op.execute(
        "UPDATE instance_units SET status = 'freigegeben' "
        "WHERE status IS NULL OR status NOT IN ('freigegeben', 'im_prozess')"
    )
    op.execute("ALTER TABLE instance_units ALTER COLUMN status SET DEFAULT 'freigegeben'")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS process_events CASCADE")
    op.execute("DROP TABLE IF EXISTS order_units CASCADE")
    op.execute("DROP TABLE IF EXISTS process_steps CASCADE")
    if _has_column("orders", "end_status"):
        op.drop_column("orders", "end_status")
    if _has_column("orders", "status"):
        op.drop_column("orders", "status")
    op.execute("ALTER TABLE instance_units ALTER COLUMN status SET DEFAULT 'new'")
