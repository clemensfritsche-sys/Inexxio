"""078 – Lagerplatz-Datensatztyp aufräumen (Daten + Schema).

Der Code kennt den Typ ``lagerplatz`` seit dem vorangegangenen Deploy **nicht mehr**
(``LOCATION_TYPES`` = user | instance | company). Diese Migration räumt nur noch auf,
was dadurch verwaist ist:

* Instanzen, die noch auf einen Lagerplatz zeigen → **standortlos** (NULL/NULL). Das ist
  im System ein regulärer Zustand, kein Sonderfall.
* Lagerplatz-Anteile in der Chargen-Verteilungsmap (``instances.locations``) → Map löschen;
  der (nun leere) Skalar ist die Wahrheit.
* Vorgabe-Ziele an Prozessschritten (``article_process_steps.target_location_*``) → NULL.
* Tote Spalten ``company_settings.default_receiving_location_id`` und
  ``purchase_orders.receiving_location_id`` → weg (die Lieferadresse ist die Firmenadresse).
* Registry-Einträge (``objects``) mit Typ ``storage_location`` → weg.
* Tabelle ``storage_locations`` → weg.

**Bewusst als eigener Deploy** nach dem Code: während eines Cloud-Run-Rollouts serviert die
alte Revision noch. Liefe die Migration zusammen mit dem Code, träfe die alte Revision auf
gedroppte Spalten. Getrennt gibt es dieses Fenster nicht – nach dem Code-Deploy rührt kein
Code diese Spalten mehr an.

**Idempotent und defensiv**: jeder Schritt prüft erst, ob es etwas zu tun gibt. Ein erneuter
Lauf (oder ein Lauf gegen eine DB, in der die Migration teilweise schon wirkte) ist ein No-op.
Reihenfolge ist wichtig: erst die Verweise lösen, dann die Registry-Zeilen, dann die Tabelle –
sonst schlägt der FK ``instances.location_id → objects.object_id`` zu.

Revision ID: 078
Revises: 077
Create Date: 2026-07-25
"""
from alembic import op
from sqlalchemy import inspect

revision = '078'
down_revision = '077'
branch_labels = None
depends_on = None


def _cols(insp, table: str) -> set[str]:
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    insp = inspect(op.get_bind())
    tables = set(insp.get_table_names())

    # ── 1) Verweise auf Lagerplätze lösen → standortlos ──────────────────────────
    if "instances" in tables:
        op.execute("""
            UPDATE instances
               SET location_type = NULL, location_id = NULL
             WHERE location_type = 'lagerplatz'
        """)
        # Verteilte Charge mit Lagerplatz-Anteilen: die Map ist wertlos geworden.
        if "locations" in _cols(insp, "instances"):
            op.execute("""
                UPDATE instances
                   SET locations = NULL
                 WHERE locations IS NOT NULL
                   AND EXISTS (SELECT 1 FROM jsonb_each(locations) AS e(k, v)
                                WHERE v ->> 't' = 'lagerplatz')
            """)

    if "article_process_steps" in tables:
        op.execute("""
            UPDATE article_process_steps
               SET target_location_type = NULL, target_location_id = NULL
             WHERE target_location_type = 'lagerplatz'
        """)

    # ── 2) Tote Spalten ─────────────────────────────────────────────────────────
    if "company_settings" in tables and "default_receiving_location_id" in _cols(insp, "company_settings"):
        op.drop_column("company_settings", "default_receiving_location_id")
    if "purchase_orders" in tables and "receiving_location_id" in _cols(insp, "purchase_orders"):
        op.drop_column("purchase_orders", "receiving_location_id")

    # ── 3) Registry + Tabelle (NACH dem Lösen der Verweise – FK-Reihenfolge) ─────
    if "objects" in tables:
        op.execute("DELETE FROM objects WHERE object_type = 'storage_location'")
    if "storage_locations" in tables:
        op.drop_table("storage_locations")


def downgrade() -> None:
    """Nur strukturell – die aufgelösten Lagerplätze sind nicht rekonstruierbar.

    Bewusst KEIN Wiederanlegen der Tabelle: der Datensatztyp ist endgültig entfallen,
    und eine leere Hülle würde nur den Eindruck erwecken, er sei zurück. Die beiden
    Spalten kommen zurück, damit eine ältere Code-Revision wieder lauffähig wäre."""
    import sqlalchemy as sa

    insp = inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if "company_settings" in tables and "default_receiving_location_id" not in _cols(insp, "company_settings"):
        op.add_column("company_settings", sa.Column("default_receiving_location_id", sa.BigInteger))
    if "purchase_orders" in tables and "receiving_location_id" not in _cols(insp, "purchase_orders"):
        op.add_column("purchase_orders", sa.Column("receiving_location_id", sa.BigInteger))
