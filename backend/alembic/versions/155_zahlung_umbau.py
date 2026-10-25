"""Zahlungsmodul – Umbau (Oktober 2026).

* ``vouchers``: Gültigkeit, Eigentum, eingefrorene Stücke, Storno-Grund, Gutschrift-Nummer,
  Lieferantenrechnung (MWST-Nr., Foto, Abweichung), Ausfuhrnachweis.
* ``voucher_quotes``: Referenz und Link der Gegenpartei.
* ``voucher_lines``: Leistung (Untertitel), Teilbetrag, Gewicht.
* ``voucher_entries``: Art (Zahlung · Ausbuchung · Trinkgeld), Grund, Gegenbuchung, IBAN;
  **eine Referenz gehört zu genau einer Zahlung** (partieller Unique-Index).
* ``voucher_documents``: jedes Dokument, so wie es hinausging.
* ``instance_units.owner_object_id``: das Eigentum als dritte Angabe am Stück.
* ``articles.is_service``: Ware oder Dienstleistung.
* «Erledigt» ist keine gespeicherte Stufe mehr: ``done`` → ``billed`` bzw. ``agreed``.
  Keine Rückwärtskompatibilität (ausdrücklich so entschieden): alte Belege bleiben lesbar,
  werden aber nicht nachgebessert.

Revision ID: 155
Revises: 154
"""

from alembic import op

revision = "155"
down_revision = "154"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for stmt in (
        "ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS valid_days INTEGER",
        "ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS ownership VARCHAR(8)",
        "ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS unit_ids JSONB",
        "ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS offered_hash VARCHAR(64)",
        "ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS cancel_note VARCHAR(200)",
        "ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS credit_number VARCHAR(120)",
        "ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS party_uid VARCHAR(40)",
        "ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS original_id BIGINT",
        "ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS deviation_note VARCHAR(200)",
        "ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS export_number VARCHAR(60)",
        "ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS export_photo_id BIGINT",
        "ALTER TABLE voucher_quotes ADD COLUMN IF NOT EXISTS reference VARCHAR(120)",
        "ALTER TABLE voucher_quotes ADD COLUMN IF NOT EXISTS link VARCHAR(500)",
        "ALTER TABLE voucher_lines ADD COLUMN IF NOT EXISTS text VARCHAR(300)",
        "ALTER TABLE voucher_lines ADD COLUMN IF NOT EXISTS part NUMERIC(18, 4)",
        "ALTER TABLE voucher_lines ADD COLUMN IF NOT EXISTS weight_kg NUMERIC(12, 3)",
        "ALTER TABLE voucher_entries ADD COLUMN IF NOT EXISTS kind VARCHAR(10) "
        "NOT NULL DEFAULT 'payment'",
        "ALTER TABLE voucher_entries ADD COLUMN IF NOT EXISTS reason VARCHAR(20)",
        "ALTER TABLE voucher_entries ADD COLUMN IF NOT EXISTS reverses_id BIGINT "
        "REFERENCES voucher_entries (id) ON DELETE SET NULL",
        "ALTER TABLE voucher_entries ADD COLUMN IF NOT EXISTS iban VARCHAR(34)",
        "ALTER TABLE instance_units ADD COLUMN IF NOT EXISTS owner_object_id BIGINT",
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_service BOOLEAN "
        "NOT NULL DEFAULT false",
        """CREATE TABLE IF NOT EXISTS voucher_documents (
            id BIGSERIAL PRIMARY KEY,
            voucher_id BIGINT NOT NULL REFERENCES vouchers (id) ON DELETE CASCADE,
            kind VARCHAR(16) NOT NULL,
            level INTEGER,
            number VARCHAR(120),
            party_id BIGINT,
            token VARCHAR(64) NOT NULL UNIQUE,
            html TEXT NOT NULL,
            agb VARCHAR(10),
            message_id BIGINT,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            is_active BOOLEAN NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS ix_voucher_documents_voucher_id "
        "ON voucher_documents (voucher_id)",
        "CREATE INDEX IF NOT EXISTS ix_voucher_documents_party_id "
        "ON voucher_documents (party_id)",
        # Zwei Zeilen mit derselben Referenz gab es bisher nur als Fehler – vor dem Riegel
        # bleibt die älteste stehen, die übrigen werden inaktiv (Soft-Delete).
        "UPDATE voucher_entries e SET is_active = false WHERE e.is_active "
        "AND e.reference IS NOT NULL AND EXISTS (SELECT 1 FROM voucher_entries o "
        "WHERE o.is_active AND o.reference = e.reference AND o.id < e.id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_voucher_entries_reference "
        "ON voucher_entries (reference) WHERE is_active AND reference IS NOT NULL",
        "UPDATE vouchers SET stage = CASE WHEN billed_on IS NOT NULL THEN 'billed' "
        "ELSE 'agreed' END WHERE stage = 'done'",
    ):
        op.execute(stmt)


def downgrade() -> None:
    pass
