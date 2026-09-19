"""Ein Modul für Geld — der Vorgang und seine Zeilen

Das Prozessschrittmodul «Zahlung» bekommt seine eigenen zwei Tabellen. **Eigene**, nicht
geteilte: es soll bestehen bleiben, wenn die Module «Beschaffen» und «Verkauf» eines Tages
ersatzlos gelöscht werden – und dann darf keine Zeile davon an ``purchases``,
``invoices`` oder ``payments`` hängen.

``deals``         **was vereinbart ist**: Richtung (Geld kommt ↔ Geld geht), Stufe,
                  Gegenpartei, Betrag, Zahlungsfrist. Ein aktiver je Modul.
``deal_entries``  **die Geld-Zeilen**: ``charge`` ist die Forderung (negativ =
                  Gutschrift), ``payment`` das Geld (negativ = Erstattung). Weil die
                  beiden Achsen getrennt sind, brauchen Vorauszahlung, Anzahlung,
                  Teilzahlung, Gutschrift und Erstattung **keinen** eigenen Modus.

**Vollständiger Spaltensatz inklusive der geerbten** (``is_active``, ``created_at``,
``updated_at``) – die Lehre aus Migration 114, wo genau die fehlten und danach jeder
Lesezugriff gegen ein frisch aus den Migrationen gebautes Schema scheiterte.

Es werden **keine Daten umgeschrieben**: das Modul ist neu, es gibt nichts zu migrieren.

Revision ID: 124
Revises: 123
"""
from alembic import op

revision = "124"
down_revision = "123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id          BIGSERIAL PRIMARY KEY,
            order_id    BIGINT        NOT NULL,
            step_id     BIGINT        NOT NULL,
            -- ``in`` (Geld kommt) · ``out`` (Geld geht) – domain/deal. Eingefroren bei
            -- der Anlage: ein laufender Auftrag trägt seinen Prozess eingefroren, und
            -- dieser Vorgang soll auch dann noch sagen können, was er war.
            direction   VARCHAR(8)    NOT NULL DEFAULT 'out',
            -- ``offer`` · ``agreed`` · ``done`` · ``cancelled``
            stage       VARCHAR(16)   NOT NULL DEFAULT 'offer',
            -- Die Objektnummer der Gegenpartei. NULL, solange niemand gewählt ist.
            party_id    BIGINT,
            -- **Was vereinbart ist** – nicht was gefordert und nicht was gezahlt ist.
            amount      NUMERIC(14,2),
            due_days    INTEGER,
            reference   VARCHAR(120),
            note        VARCHAR(400),
            agreed_on   DATE,
            -- Die geerbten Spalten (``Base``/``TimestampMixin``) – siehe Migration 114.
            is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """)
    # **Ein AKTIVER Vorgang je Modul** – die Regel in der Datenbank, nicht nur im Dienst:
    # ``instantiate_for_order`` ist idempotent, zwei gleichzeitige Freigaben sind es
    # nicht, und ein Index prüft je Anweisung. Partiell, damit ein zurückgenommener
    # Vorgang als Zeile stehen bleiben darf, ohne einen neuen zu blockieren.
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_deals_step "
               "ON deals (step_id) WHERE is_active")
    op.execute("CREATE INDEX IF NOT EXISTS ix_deals_order ON deals (order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_deals_step ON deals (step_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS deal_entries (
            id          BIGSERIAL PRIMARY KEY,
            deal_id     BIGINT        NOT NULL,
            -- ``charge`` (Forderung) · ``payment`` (Geld) – domain/deal.KINDS
            kind        VARCHAR(10)   NOT NULL,
            -- **Darf negativ sein**: das ist die Gutschrift bzw. die Erstattung. Eine
            -- dritte Art dafür gäbe es sonst, und sie bräuchte eine eigene Regel.
            amount      NUMERIC(14,2) NOT NULL,
            booked_on   DATE,
            -- **Je Rechnung eine eigene** Fälligkeit: eine Anzahlung und eine
            -- Schlussrechnung sind zu zwei Zeitpunkten fällig.
            due_on      DATE,
            -- Wer die Nummer vergibt, sagt die Richtung: bei einer Einnahme wir
            -- (``<Auftragsnummer>[-n]``), bei einer Ausgabe die Gegenpartei. **Kein**
            -- Unique-Index darüber: zwei Lieferanten dürfen beide eine «2026-001»
            -- schicken, und ein Index wiese eine richtige Eingabe ab.
            reference   VARCHAR(120),
            note        VARCHAR(200),
            is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_deal_entries_deal "
               "ON deal_entries (deal_id)")


def downgrade() -> None:
    # Umgekehrte Reihenfolge: die Zeilen zeigen auf den Vorgang.
    op.execute("DROP TABLE IF EXISTS deal_entries")
    op.execute("DROP TABLE IF EXISTS deals")
