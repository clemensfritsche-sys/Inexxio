"""Mehrstandort (Variante A): ``company_settings`` darf mehrere Zeilen tragen.

**Eine Spalte, keine neue Tabelle.** Ein Standort ist bereits ein vollwertiger ERP-
Datensatz vom Typ ``organization`` – mit Objektnummer, im Feed, und als **Halter**
verwendbar (``instances.location_type='company'``). Er braucht genau die Felder, die
``company_settings`` schon hat: Name, Anschrift, Kontakt. Eine zweite Tabelle wäre eine
zweite Wahrheit für dieselbe Sache.

Was einmal gilt und was je Standort gilt, ist deshalb **keine Frage der Tabelle, sondern
der Schreibstelle**:

  * **Hauptsitz** (``is_primary``) trägt die **Rechtsidentität** (UID, MWST, HR,
    Aktienkapital, IBAN, Rechtsform, Website) und die **Systemkonfiguration** (Stripe,
    Shop-Währungen, Rechtstexte, Plausible, Maps). Nur dort editierbar, nur von dort
    gelesen (``services/sites.primary``).
  * **Jeder Standort** trägt Name, Anschrift und Kontakt – mehr nicht.

Genau ein Hauptsitz ist über einen partiellen Unique-Index erzwungen; ohne ihn könnte
«die Firma» zwei Antworten haben.

Bestandsdaten: **keine Zeile wird umgeschrieben.** Die vorhandene Zeile wird zum
Hauptsitz, ihre Objektnummer bleibt gültig – alle Instanzen, die dort verortet sind,
zeigen weiterhin korrekt darauf.

Revision ID: 090
Revises: 089
"""

from alembic import op
import sqlalchemy as sa

revision = "090"
down_revision = "089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_settings",
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Die bestehende Zeile IST der Hauptsitz. Bewusst über die kleinste ``id`` statt hart
    # ``id = 1``: der Singleton wurde immer als ``id=1`` angelegt, aber eine Datenbank, in
    # der das je anders lief, soll hier nicht ohne Hauptsitz zurückbleiben.
    op.execute(
        "UPDATE company_settings SET is_primary = true "
        "WHERE id = (SELECT min(id) FROM company_settings)"
    )
    # Genau EIN Hauptsitz – sonst hätte «die Firma» zwei Antworten.
    op.execute(
        "CREATE UNIQUE INDEX uq_company_settings_primary "
        "ON company_settings (is_primary) WHERE is_primary"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_company_settings_primary")
    op.drop_column("company_settings", "is_primary")
