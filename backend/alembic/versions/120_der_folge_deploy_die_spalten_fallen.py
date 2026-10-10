"""Der Folge-Deploy: die toten Spalten fallen

Zweiter und letzter Schritt der **Zwei-Deploy-Regel**. Im Aufräum-Deploy (August 2026)
haben diese Spalten ihr ORM-Mapping verloren; gedroppt werden sie erst jetzt, weil
während eines Cloud-Run-Rollouts die **Vorgänger-Revision** noch läuft und eine Spalte,
die sie noch liest oder schreibt, nicht unter ihr verschwinden darf. Genau daran starb
Migration ``090`` – die Lehre ist teuer bezahlt und steht seither in ``docs/backlog.md``.

Die Vorbedingung ist **geprüft, nicht angenommen**: keine dieser Spalten steht noch in
``Base.metadata``, und der Stand, der sie zuletzt mappte, ist seit dem Aufräum-Deploy
nicht mehr in Betrieb.

Woher sie stammen – jede gehört zu einem Bereich, den es nicht mehr gibt
(``docs/attic.md``):

``articles``          Beschaffungs-/Verkaufsfelder des Vorgänger-Systems. Was beschafft
                      wird, sagt heute der **Prozess** (die Einzelinstanzen vor dem
                      Modul), nicht ein Feld am Artikel.
``company_settings``  Zahlungsanbieter, Shop-Währungen, hCaptcha, Rechtstexte,
                      Infrastruktur-Kosten, Wareneingangs-Ort – die Konfiguration der
                      entfernten Bereiche. Übrig bleibt die **Plattform**-Konfiguration
                      der einen Website (Plausible, Google-Maps-Schlüssel).
``user_profiles``     Die Stripe-Kundennummer.
``purchases``         Reste zweier Umbauten am Beschaffungs-Beleg: die Bestellmenge ist
                      **abgeleitet** (Migration 115), und **was** bestellt wird, sagen
                      die Zeilen (Migration 116) statt eines Artikelfeldes.

**Idempotent** (``IF EXISTS``): dieselbe Migration darf auf einer Datenbank laufen, in
der ein früherer Lauf schon einen Teil erledigt hat.

**Die Tabellen der entfernten Bereiche bleiben vorerst stehen** (``events``,
``document_*``, ``article_prices``, ``ai_actions`` …). Sie halten Historie, ihr Drop ist
unumkehrbar, und ``docs/backlog.md`` verlangt dafür ausdrücklich vorher eine Sicherung
(``scripts/dump-db.sh``) gegen die **produktive** Datenbank. Eine Spalte, die niemand
liest, kostet nichts; ein Tabellen-Drop ohne Sicherung kostet die Vergangenheit.

Revision ID: 120
Revises: 119
"""
from alembic import op

revision = "120"
down_revision = "119"
branch_labels = None
depends_on = None


#: Tabelle → die Spalten, die dort fallen.
_DEAD: dict[str, tuple[str, ...]] = {
    "articles": (
        "procurement_mode", "default_supplier_id", "default_webshop_url",
        "sales_published", "sales_visibility", "sales_fulfillment", "sales_content",
    ),
    "company_settings": (
        "logo_path", "stripe_publishable_key", "hcaptcha_site_key",
        "shop_currencies", "shop_country_currency", "shop_default_currency",
        "payments_provider", "pricing_zone_factors", "infra_monthly_chf",
        "legal_documents", "default_receiving_location_id",
    ),
    "user_profiles": ("stripe_customer_id",),
    "purchases": ("reference", "quantity", "article_id", "due_date", "ordered_for"),
}


def upgrade() -> None:
    for table, columns in _DEAD.items():
        for column in columns:
            op.execute(f'ALTER TABLE {table} DROP COLUMN IF EXISTS "{column}"')


def downgrade() -> None:
    # **Nicht umkehrbar, und das ist ehrlich.** Die Spalten liessen sich anlegen, ihr
    # Inhalt nicht – und eine leere Spalte zurückzugeben wäre die schlechtere Antwort:
    # sie sähe aus wie die alte und wäre es nicht. Wer den Stand davor braucht, nimmt
    # die Sicherung (``scripts/dump-db.sh``) bzw. den Tag ``attic/pre-cleanup-2026-08``.
    pass
