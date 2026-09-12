"""Gesellschaften: Betreiber-Wahl + Währung; ``is_primary`` endgültig entfernt.

Drei zusammenhängende Änderungen am ``company_settings``-Datensatztyp:

  1. **``is_primary`` weg.** Deploy A hat die Spalte aus dem Modell entfernt und den Betreiber
     abgeleitet (ältestes Unternehmen). Jetzt fällt auch die DB-Spalte samt Index – der
     2-Schritt-Drop ist damit abgeschlossen (die Vorgänger-Revision las sie schon nicht mehr).
  2. **``is_operator`` neu** – der Betreiber der Website ist jetzt **wählbar** (genau EINE
     Gesellschaft trägt den Titel, partieller Unique-Index). Default = das älteste Unternehmen,
     also exakt die Zeile, die ``is_primary`` zuletzt trug. Anders als ``is_primary`` bedeutet
     das Flag **nur** «vertritt die Website» – keine Kaste, jede Gesellschaft bleibt vollständig.
  3. **``currency`` neu** – die Funktionswährung je Gesellschaft (Default CHF; wird aus dem Land
     abgeleitet vorbelegt). Grundlage für «ein Preis, überall in Landeswährung».

**Jeder Schritt idempotent** – ``start.sh`` startet uvicorn auch bei Alembic-Fehler, das
Lifespan-Netz zieht dieselben Änderungen nach; liefe die Migration danach erneut, dürfte sie
nicht an «column already exists» scheitern (sonst blockiert sie jede künftige Migration).

Revision ID: 091
Revises: 090
"""

from alembic import op
import sqlalchemy as sa

revision = "091"
down_revision = "090"
branch_labels = None
depends_on = None


def _cols(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("company_settings")}


def upgrade() -> None:
    conn = op.get_bind()
    cols = _cols(conn)

    # 2) is_operator anlegen und aus dem bisherigen Betreiber (is_primary=true, sonst
    #    ältestes) seeden – VOR dem Drop von is_primary, damit die Markierung nicht verloren geht.
    if "is_operator" not in cols:
        op.add_column("company_settings",
                      sa.Column("is_operator", sa.Boolean(), nullable=False, server_default="false"))
    if "is_primary" in cols:
        op.execute("UPDATE company_settings SET is_operator = is_primary")
    # Fallback (frische DB ohne is_primary): das älteste Unternehmen ist der Betreiber.
    op.execute(
        "UPDATE company_settings SET is_operator = true "
        "WHERE id = (SELECT min(id) FROM company_settings) "
        "AND NOT EXISTS (SELECT 1 FROM company_settings WHERE is_operator)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_company_settings_operator "
        "ON company_settings (is_operator) WHERE is_operator"
    )

    # 3) currency (Funktionswährung je Gesellschaft).
    if "currency" not in cols:
        op.add_column("company_settings",
                      sa.Column("currency", sa.String(3), nullable=False, server_default="CHF"))

    # 1) is_primary + Index endgültig entfernen (2-Schritt-Drop abgeschlossen).
    op.execute("DROP INDEX IF EXISTS uq_company_settings_primary")
    if "is_primary" in cols:
        op.drop_column("company_settings", "is_primary")


def downgrade() -> None:
    conn = op.get_bind()
    cols = _cols(conn)
    if "is_primary" not in cols:
        op.add_column("company_settings",
                      sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"))
    op.execute("UPDATE company_settings SET is_primary = is_operator")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_company_settings_primary "
        "ON company_settings (is_primary) WHERE is_primary"
    )
    op.execute("DROP INDEX IF EXISTS uq_company_settings_operator")
    if "is_operator" in cols:
        op.drop_column("company_settings", "is_operator")
    if "currency" in cols:
        op.drop_column("company_settings", "currency")
