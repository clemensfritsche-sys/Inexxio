"""Das erste echte Prozessschrittmodul: **Datenerfassung**. Das Testmodul entfällt.

Vier Eingriffe, alle aus derselben Regel — *eine Sache, eine Stelle*:

``captures.order_id/step_id``   Eine Erfassung entsteht ausschliesslich, wenn ein Stück vor
                                einem Modul steht. Beide Spalten sind Pflicht; die Tabelle
                                wird darum neu aufgebaut statt migriert (ihre Zeilen
                                stammen aus dem Pfad, den es nicht mehr gibt).
``articles.capture_fields``     Entfällt. Was erfasst wird, sagt das **Modul**; am Artikel
                                war es eine zweite Stelle für dieselbe Frage – und sie hing
                                an keinem Prozess.
``articles.status='draft'``     Gibt es nicht mehr: ein Artikel entsteht erst mit seiner
                                Freigabe. Vorgefundene Entwürfe sind das Ergebnis des
                                behobenen Fehlers (Autosave legte sie ohne Prozess an) –
                                sie können nichts erzeugen und werden **inaktiv** gesetzt.
                                Nicht gelöscht: ihre Objektnummer ist vergeben, und
                                «inaktiv» ist ein Zustand, kein Verschwinden.
Testmodul-Aufträge              Werden entfernt. Ihr Modul existiert nicht mehr, also käme
                                ihr Prozess nie ans Ende – und ihre Einzelinstanzen blieben
                                über den Exklusivitäts-Index **für immer gebunden**. Das
                                wäre kein Altbestand, sondern gesperrter Bestand.

Revision ID: 106
Revises: 105
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "106"
down_revision = "105"
branch_labels = None
depends_on = None

#: Die Modultypen, die es noch gibt. Bewusst hier ausgeschrieben statt importiert: eine
#: Migration beschreibt einen Zeitpunkt, und der ändert sich nicht mit dem Code.
_KNOWN_MODULES = ("datenerfassung",)


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


def _has_table(table: str) -> bool:
    return bool(op.get_bind().execute(sa.text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar())


def upgrade() -> None:
    # ── 1. Aufträge des entfallenen Testmoduls samt ihrer Spuren entfernen ────
    # Reihenfolge: erst die abhängigen Zeilen, dann der Auftrag. Die Einzelinstanzen
    # bleiben bestehen – sie sind Bestand; nur ihre Bindung an einen toten Auftrag geht.
    if _has_table("process_steps") and _has_table("orders"):
        known = ", ".join(f"'{m}'" for m in _KNOWN_MODULES)
        # Die Liste wird **zuerst gelesen**: als Unterabfrage wäre sie leer, sobald
        # ``process_steps`` gelöscht ist – und der Auftrag selbst bliebe stehen.
        dead = [
            int(i) for (i,) in op.get_bind().execute(sa.text(
                f"SELECT DISTINCT order_id FROM process_steps "
                f"WHERE module_type NOT IN ({known})"
            )).all()
        ]
        if dead:
            ids = ", ".join(str(i) for i in dead)
            for table in ("process_events", "order_units", "process_steps", "order_lines"):
                if _has_table(table):
                    op.execute(f"DELETE FROM {table} WHERE order_id IN ({ids})")
            op.execute(f"DELETE FROM orders WHERE id IN ({ids})")

    # Stücke, die dadurch aus einem Prozess fallen, sind wieder einsatzbereit. Genau das
    # heisst «freigegeben» – ein Stück, das in keinem Auftrag steckt (PROCESS_CORE §5.2).
    if _has_table("instance_units") and _has_table("order_units"):
        op.execute(
            "UPDATE instance_units SET status = 'freigegeben' "
            "WHERE status <> 'freigegeben' AND id NOT IN ("
            "  SELECT instance_unit_id FROM order_units WHERE released_at IS NULL)"
        )

    # ── 2. captures neu aufbauen ──────────────────────────────────────────────
    op.execute("DROP TABLE IF EXISTS captures CASCADE")
    op.create_table(
        "captures",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instance_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("step_id", sa.BigInteger(), nullable=False),
        sa.Column("values", postgresql.JSONB(), nullable=False),
        sa.Column("result", sa.String(10), nullable=True),
        sa.Column("captured_by", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_captures_instance_unit_id", "captures", ["instance_unit_id"])
    op.create_index("ix_captures_order_id", "captures", ["order_id"])
    op.create_index("ix_captures_step_id", "captures", ["step_id"])

    # ── 3. Die Maske am Artikel entfällt ──────────────────────────────────────
    if _has_column("articles", "capture_fields"):
        op.drop_column("articles", "capture_fields")

    # ── 4. «Entwurf» gibt es nicht mehr ───────────────────────────────────────
    if _has_column("articles", "status"):
        op.execute("UPDATE articles SET status = 'inactive' WHERE status = 'draft'")
        op.execute("ALTER TABLE articles ALTER COLUMN status SET DEFAULT 'released'")


def downgrade() -> None:
    """Struktur zurück – **nicht** die alte Welt.

    Die gelöschten Testmodul-Aufträge kommen nicht wieder, und die auf ``inactive``
    gesetzten Entwürfe bleiben inaktiv: ein Downgrade, das Daten erfindet, wäre eine Lüge.
    """
    if not _has_column("articles", "capture_fields"):
        op.add_column("articles", sa.Column("capture_fields", postgresql.JSONB(), nullable=True))
    if _has_column("articles", "status"):
        op.execute("ALTER TABLE articles ALTER COLUMN status SET DEFAULT 'draft'")
    op.execute("DROP TABLE IF EXISTS captures CASCADE")
    op.create_table(
        "captures",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instance_unit_id", sa.BigInteger(), nullable=False),
        sa.Column("values", postgresql.JSONB(), nullable=False),
        sa.Column("result", sa.String(10), nullable=True),
        sa.Column("captured_by", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_captures_instance_unit_id", "captures", ["instance_unit_id"])
