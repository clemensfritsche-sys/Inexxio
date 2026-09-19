"""Eine Statusliste für alle, ein Auftragsname, kein Pflicht-Schalter.

Drei Eingriffe, alle aus demselben Grundsatz — *so wenige Status wie möglich, so viele
gemeinsame wie möglich; und was abgeleitet werden kann, wird nicht gespeichert.*

``orders.status``       **Entfällt.** Der Auftragsstatus ergibt sich aus dem Zustand
                        seiner Einzelinstanzen (``process.order_status``). Eine Spalte
                        daneben ist der zweite Ort, an dem er gesetzt wird – und der lief
                        prompt weg: sie stand auf ``released``, also zeigte der Kopf
                        «Freigegeben». Das ist kein Zustand, sondern die Aktion, mit der
                        der Auftrag entstanden ist.
``orders.name``         Neu, Pflicht: «Auftrag <Objektnummer>». Er entsteht im selben Zug
                        wie die Nummer; vorher gibt es keine.
``instances.status``    **Entfällt** aus demselben Grund, nur eine Ebene tiefer: eine
                        Instanz ist eine Gruppe. Sie hat so wenig einen eigenen Zustand
                        wie eine eigene Menge – beides ergibt sich aus ihren
                        Einzelinstanzen. Die Spalte stand auf ``new`` und wurde **nie**
                        geschrieben; ``new`` war damit ein sechstes Wort, das keine der
                        drei Achsen kennt.
``articles.status``     ``released``/``inactive`` → ``freigegeben``/``inaktiv``. Dieselben
                        zwei Zustände, jetzt aus der EINEN Liste (``domain/statuses``) –
                        mit derselben Beschriftung und derselben Farbe wie überall sonst.
``…config.points[]``    Der Schlüssel ``required`` fällt aus jedem Erfassungspunkt.
                        **Alles, was angelegt ist, ist Pflicht** – ein Schalter dafür wäre
                        die Frage, warum man einen Punkt anlegt, den niemand ausfüllen muss.

Revision ID: 107
Revises: 106
"""
import sqlalchemy as sa
from alembic import op

revision = "107"
down_revision = "106"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    return bool(op.get_bind().execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table, "c": column}).first())


def _has_table(table: str) -> bool:
    return bool(op.get_bind().execute(
        sa.text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar())


#: Die beiden Tabellen, deren ``config`` Erfassungspunkte trägt.
_CONFIG_TABLES = ("process_steps", "article_process_steps")


def upgrade() -> None:
    # ── 1. Der Auftrag bekommt seinen Namen ──────────────────────────────────
    if _has_table("orders") and not _has_column("orders", "name"):
        op.add_column("orders", sa.Column("name", sa.String(120), nullable=True))
        # Bestehende Aufträge tragen genau den Namen, den sie bei der Freigabe bekommen
        # hätten – abgeleitet aus ihrer Nummer, nicht erfunden.
        op.execute("UPDATE orders SET name = 'Auftrag ' || object_id WHERE name IS NULL")
        op.alter_column("orders", "name", nullable=False)

    # ── 2. Der Auftragsstatus wird abgeleitet – die Spalte entfällt ──────────
    if _has_column("orders", "status"):
        op.drop_column("orders", "status")

    # ── 3. Die Instanz-Gruppe leitet ihren Zustand ab – die Spalte entfällt ──
    if _has_column("instances", "status"):
        op.drop_column("instances", "status")

    # ── 4. Artikel-Status aus der EINEN Liste ────────────────────────────────
    if _has_column("articles", "status"):
        op.execute("UPDATE articles SET status = 'freigegeben' WHERE status = 'released'")
        op.execute("UPDATE articles SET status = 'inaktiv' WHERE status = 'inactive'")
        op.execute("ALTER TABLE articles ALTER COLUMN status SET DEFAULT 'freigegeben'")

    # ── 5. «Pflicht ja/nein» aus jedem Erfassungspunkt streichen ─────────────
    # Der Schlüssel wird entfernt, nicht auf ``true`` gesetzt: was es nicht gibt, kann
    # niemand lesen – und eine zurückgelassene Spur wäre die Einladung, sie wieder
    # auszuwerten.
    for table in _CONFIG_TABLES:
        if not _has_table(table):
            continue
        op.execute(f"""
            UPDATE {table} SET config = jsonb_set(
                config, '{{points}}',
                (SELECT coalesce(jsonb_agg(p - 'required'), '[]'::jsonb)
                   FROM jsonb_array_elements(config->'points') AS p))
            WHERE config ? 'points'
              AND EXISTS (SELECT 1 FROM jsonb_array_elements(config->'points') AS p
                          WHERE p ? 'required')
        """)


def downgrade() -> None:
    """Struktur zurück – **nicht** die alte Welt.

    Der abgeleitete Auftragsstatus wird als ``im_prozess`` zurückgeschrieben: welchen
    Wert eine Zeile vorher trug, ist nicht rekonstruierbar, und ein erfundener wäre eine
    Lüge. Der gestrichene ``required``-Schlüssel kommt nicht wieder – alles ist Pflicht.
    """
    if _has_column("articles", "status"):
        op.execute("UPDATE articles SET status = 'released' WHERE status = 'freigegeben'")
        op.execute("UPDATE articles SET status = 'inactive' WHERE status = 'inaktiv'")
        op.execute("ALTER TABLE articles ALTER COLUMN status SET DEFAULT 'released'")
    if _has_table("orders") and not _has_column("orders", "status"):
        op.add_column("orders", sa.Column(
            "status", sa.String(20), nullable=False, server_default=sa.text("'im_prozess'")))
    if _has_table("instances") and not _has_column("instances", "status"):
        op.add_column("instances", sa.Column(
            "status", sa.String(30), nullable=False, server_default=sa.text("'new'")))
    if _has_column("orders", "name"):
        op.drop_column("orders", "name")
