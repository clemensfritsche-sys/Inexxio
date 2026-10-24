"""Cleanup Paket F/G: die Spalten und Tabellen entfernter Bereiche fallen.

Zweiter Schritt der **Zwei-Deploy-Regel** für alles, was in ``docs/backlog.md`` als
«Folge-Deploy» stand – und für die Tabellen der Bereiche, die es nicht mehr gibt
(``docs/attic.md``). Die produktive Datenbank ist **vorher gesichert** worden
(``scripts/dump-db.sh``); erst damit war der Drop freigegeben.

Die Vorbedingung ist **geprüft, nicht angenommen**: keine dieser Spalten und keine dieser
Tabellen steht noch in ``Base.metadata`` (der Wächter
``tests/test_schema_is_built_by_the_migrations.py`` hält es seither umgekehrt fest: nach
``upgrade head`` gibt es nichts mehr, das kein Modell kennt).

**Bewusst NICHT gedroppt** (Entscheid E7): ``articles.safety_stock``, ``min_order_qty``,
``supplier_article_number``, ``user_profiles.language`` und ``notification_*`` – sie sind
gemappt und bleiben vorgemerkt. ``objects`` (die Nummern-Registry) und ``alembic_version``
fasst diese Migration nie an.

**Der Nummernraum verliert nichts**: die Objektnummern von ``document_files`` werden vor
dem Drop in die Registry übernommen (``ON CONFLICT DO NOTHING``) – ohne sie könnte
``setval`` eine Nummer ein zweites Mal vergeben, falls sie dort noch nicht stand.

**Ohne CASCADE**: die Tabellen fallen in **einer** Anweisung, also lösen sich ihre
Fremdschlüssel untereinander (``deal_entries`` → sich selbst, ``voucher_allocations`` →
``voucher_entries``, ``message_replies`` → ``messages``) von selbst. Hängt etwas
**Unbekanntes** an ihnen, scheitert die Migration laut statt es still mitzunehmen.

**Idempotent** (``IF EXISTS``). Der Rückweg legt nichts wieder an: die Daten liegen in
der Sicherung, und eine leere Spalte zurückzugeben sähe aus wie die alte und wäre es nicht.

Revision ID: 152
Revises: 151
"""
from alembic import op

revision = "152"
down_revision = "151"
branch_labels = None
depends_on = None


#: Tabelle → die Spalten, die dort fallen (alle ohne Mapping, jede mit ihrem Grund).
DEAD_COLUMNS: dict[str, tuple[str, ...]] = {
    # Einstandspreis ohne Schreiber seit «Beschaffen» (B-08) · Zustand ist die Projektion
    # von ``replaced_by_id`` (#773, B-20) · Lagerplatz-Kennzeichen des Vorgänger-Modells.
    "articles": ("landed_unit_cost", "status", "is_location"),
    # Plausible (E5) und die Felder, die ``sites.ENTITY_FIELDS`` längst gestrichen hat
    # (Handelsregister und Kapital sagt die UID, die Bank die IBAN, Buchhaltung ist Phase
    # 3, die Website-Adresse ist abgeleitet, #309).
    "company_settings": (
        "plausible_domain", "article_names", "bank", "bic_swift", "qr_iban_encrypted",
        "share_capital", "trade_register_nr", "trade_register_canton",
        "default_payment_days", "default_skonto_days", "default_skonto_pct",
        "vat_method", "vat_period", "oss_active", "oss_reg_number", "vies_active",
        "website",
    ),
    "user_profiles": (
        # Bankverbindung an der Person (CRM Schritt 1b) – es gibt sie nur an einer
        # eigenen Gesellschaft.
        "bank_account_holder", "bank_iban", "bank_bic", "bank_name",
        # Die Anschriften stehen im Adressbuch (Migration 143).
        "address_line1", "address_line2", "city", "postal_code", "state_region", "country",
        "invoice_first_name", "invoice_last_name", "invoice_address_line1",
        "invoice_address_line2", "invoice_city", "invoice_postal_code", "invoice_country",
        "invoice_email",
        # #1042/#1043: eine Angabe existiert genau einmal.
        "company_billing_email", "invoice_company", "account_type",
        "invoice_same_as_shipping",
        "ship_name", "ship_company", "ship_address_line1", "ship_address_line2",
        "ship_city", "ship_postal_code", "ship_state_region", "ship_country",
        # AGB-Akzeptanz ohne Schreiber und Leser (E2).
        "terms_accepted_at", "terms_version",
    ),
    # Seit Migration 138 ist der Beleg die Rechnung; die Zeile trägt nur Zahlungen.
    "voucher_entries": ("kind", "due_on", "vat", "service_date", "reverses_id",
                        "charge_id", "reason"),
    # «Rechnung ist versendet» (#1047) – gestellt ist draussen.
    "vouchers": ("issued_on",),
}

#: Die Tabellen der entfernten Bereiche – kein Modell kennt sie.
DEAD_TABLES: tuple[str, ...] = (
    # Ereignis-Strom, Preise/Shop, KI, Dokumente (Aufräumrunde August 2026)
    "events", "article_prices", "article_sales_audience", "fx_rates", "ai_actions",
    "document_files", "document_links", "document_blobs", "document_signoffs",
    "document_acknowledgements",
    # Die Handels-Module «Beschaffen» und «Verkauf» (§9.9a)
    "purchases", "invoices", "payments",
    # Das Vorgänger-Zahlungsmodul (#960)
    "deals", "deal_entries",
    # «Antwort auf» (Migration 148) und die modulinterne Sammelzahlung (Migration 138)
    "message_replies", "voucher_allocations",
)

# Die Fassung des Standard-Index ohne Konto (vor Migration 143).
_OLD_INDEXES = ("uq_addresses_default_delivery", "uq_addresses_default_billing")


def upgrade() -> None:
    # Der Nummernraum zuerst: was ``document_files`` an Nummern vergeben hat, bleibt
    # vergeben.
    op.execute(
        "DO $$ BEGIN "
        "IF to_regclass('public.objects') IS NOT NULL "
        "AND to_regclass('public.document_files') IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'document_files' AND column_name = 'object_id') THEN "
        "INSERT INTO objects (object_id, object_type, created_at) "
        "SELECT object_id, 'document', now() FROM document_files "
        "WHERE object_id IS NOT NULL ON CONFLICT (object_id) DO NOTHING; "
        "END IF; END $$;"
    )
    op.execute("DROP TABLE IF EXISTS " + ", ".join(DEAD_TABLES))
    for table, columns in DEAD_COLUMNS.items():
        op.execute(f"ALTER TABLE IF EXISTS {table} "
                   + ", ".join(f'DROP COLUMN IF EXISTS "{c}"' for c in columns))
    for name in _OLD_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")


def downgrade() -> None:
    # **Unumkehrbar, und das ist ehrlich.** Spalten und Tabellen liessen sich anlegen, ihr
    # Inhalt nicht – die Daten liegen in der Sicherung der produktiven Datenbank. Ein
    # leerer Rückweg hält ``downgrade -1 && upgrade head`` lauffähig (die Drops sind
    # ``IF EXISTS``).
    pass
