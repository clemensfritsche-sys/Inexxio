"""Die Forderung ist die dritte Achse — und eine Gutschrift eine negative Rechnung

Ein Geschäft hat drei **unabhängige** Achsen: Ware (die Einzelinstanzen im Prozess),
**Forderung** (die Rechnung) und Geld (die Zahlung). Zwei gab es; ``balance`` kürzte die
dritte weg, indem sie die **Zusage** (``purchases.amount``) als **Forderung** las. Solange
beides dasselbe ist, geht das gut – an Anzahlung, Teilrechnung und zwei Fälligkeiten
bricht es, und zwar still.

Vier Schritte, ein Deploy:

1. **``invoices``** – die neue Tabelle. Vollständiger Spaltensatz inklusive der geerbten
   (``is_active``, ``created_at``, ``updated_at``): die Lehre aus Migration 114, wo genau
   die fehlte und danach jeder Lesezugriff gegen ein frisches Schema scheiterte.

2. **Je Beleg ab der Zusage eine Rechnung** über die Belegsumme, mit Datum und Fälligkeit
   aus dem, was bisher gerechnet wurde (``committed_on`` + Zahlungsfrist der gewählten
   Angebotszeile). **Ohne diesen Schritt stünde jeder bestehende Beleg auf
   ``offen = −gezahlt``** – die Formel liest ab jetzt die Rechnungen.

3. **Gutschriften werden negative Rechnungen.** Eine ``payment``-Zeile der Art ``credit``
   war eine Zahlung, bei der kein Geld fliesst – mit einer eigenen Regel dafür
   («eine Gutschrift hat keinen Zahlweg»). Als negative Rechnung ist sie schlicht
   richtig, und **zwei Regeln entfallen**.

4. **``payments.kind`` verliert sein Mapping.** Gedroppt wird im **Folge-Deploy**
   (Zwei-Deploy-Regel, ``docs/backlog.md``): fiele die Spalte jetzt, liefe der noch
   laufende alte Code im Deploy-Fenster gegen eine Tabelle ohne sie.

**Die Nummer** ist ``<Auftragsnummer>-<laufend>`` – dieselbe Regel wie beim Suffix der
Einzelinstanz. Sie wird hier mitgeschrieben, damit ein bestehender Beleg nicht mit einer
nummernlosen Rechnung dasteht.

Revision ID: 123
Revises: 122
"""
from alembic import op

revision = "123"
down_revision = "122"
branch_labels = None
depends_on = None

#: Die Stufe, ab der es etwas zu fordern gibt. Ausgeschrieben, weil eine Migration keinen
#: Anwendungscode importieren darf – sie muss auch dann noch laufen, wenn das Modul längst
#: anders aussieht. Die alten Werte stehen daneben: Migration 122 schreibt sie um, aber
#: eine Datenbank, die sie nicht gesehen hat, trägt sie noch (Lifespan-Netz).
_COMMITTED = ("commitment", "fulfilment", "cancelled",
              "bestellung", "wareneingang", "storniert")


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id           BIGSERIAL PRIMARY KEY,
            purchase_id  BIGINT        NOT NULL,
            -- ``<Auftragsnummer>-<laufend>`` bei uns, die Nummer der Gegenpartei beim
            -- Einkauf. Nullable: eine Lieferantenrechnung ohne Nummer ist möglich.
            number       VARCHAR(60),
            -- **Darf negativ sein**: das ist die Gutschrift.
            amount       NUMERIC(12,2) NOT NULL,
            currency     VARCHAR(3)    NOT NULL DEFAULT 'CHF',
            issued_on    DATE,
            -- **Ihre eigene** Fälligkeit. Sie stand vorher am Beleg (abgeleitet aus
            -- Zusagedatum + Frist) und konnte damit nur den Fall «eine Rechnung».
            due_on       DATE,
            note         VARCHAR(400),
            -- Die geerbten Spalten (``Base``/``TimestampMixin``) – siehe Migration 114.
            is_active    BOOLEAN       NOT NULL DEFAULT TRUE,
            created_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """)
    # **Eine Nummer gehört zu genau einer Rechnung im Haus** – in der Datenbank, nicht nur
    # im Dienst: ``record`` prüft je Aufruf, zwei gleichzeitige Aufrufe sind nicht einer.
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_invoices_number "
               "ON invoices (number) WHERE number IS NOT NULL AND is_active")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoices_purchase ON invoices (purchase_id)")

    stages = ", ".join(f"'{s}'" for s in _COMMITTED)
    # ►► **Je zugesagtem Beleg eine Rechnung** – mit genau den Werten, die die alte
    #    Ableitung ergeben hätte. Idempotent über ``NOT EXISTS``: ein zweiter Lauf findet
    #    nichts mehr. Die Zahlungsfrist steht in der **gewählten** Angebotszeile des
    #    JSONB; ist keine da, bleibt die Fälligkeit leer – genau wie vorher.
    op.execute(f"""
        INSERT INTO invoices (purchase_id, number, amount, currency, issued_on, due_on,
                              note, is_active, created_at, updated_at)
        SELECT p.id,
               o.object_id || '-1',
               p.amount,
               COALESCE(p.currency, 'CHF'),
               p.committed_on,
               CASE WHEN p.committed_on IS NOT NULL AND q.days IS NOT NULL
                    THEN p.committed_on + (q.days || ' days')::interval
                    END,
               NULL, TRUE, now(), now()
        FROM purchases p
        JOIN orders o ON o.id = p.order_id
        LEFT JOIN LATERAL (
            SELECT (elem->>'payment_days')::int AS days
            FROM jsonb_array_elements(COALESCE(p.quotes, '[]'::jsonb)) elem
            WHERE elem->>'state' = 'gewaehlt'
              AND elem->>'payment_days' IS NOT NULL
              AND elem->>'payment_days' <> ''
            LIMIT 1
        ) q ON TRUE
        WHERE p.amount IS NOT NULL
          AND p.stage IN ({stages})
          AND NOT EXISTS (SELECT 1 FROM invoices i WHERE i.purchase_id = p.id)
    """)

    # ►► **Gutschriften werden negative Rechnungen.** Der Betrag kehrt sein Vorzeichen um:
    #    vorher zog ``credit`` von der Forderung ab, jetzt **ist** er die (negative)
    #    Forderung. Die alte Zeile bleibt als Historie stehen, nur nicht mehr aktiv –
    #    gelöscht wird nichts (Soft-Delete, ``CLAUDE.md``).
    op.execute("""
        INSERT INTO invoices (purchase_id, number, amount, currency, issued_on, due_on,
                              note, is_active, created_at, updated_at)
        SELECT pay.purchase_id, NULL, -pay.amount, COALESCE(pay.currency, 'CHF'),
               pay.paid_at, NULL,
               COALESCE(pay.note, 'Gutschrift'), TRUE, pay.created_at, now()
        FROM payments pay
        WHERE pay.kind = 'credit' AND pay.is_active
    """)
    op.execute("UPDATE payments SET is_active = FALSE WHERE kind = 'credit' AND is_active")
    # Der Default fällt, damit ein Insert ohne die Spalte durchgeht. Gedroppt wird sie im
    # Folge-Deploy – jetzt liefe der alte Code im Fenster gegen eine Tabelle ohne sie.
    op.execute("ALTER TABLE payments ALTER COLUMN kind DROP NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE payments ALTER COLUMN kind SET DEFAULT 'payment'")
    op.execute("UPDATE payments SET kind = 'payment' WHERE kind IS NULL")
    op.execute("ALTER TABLE payments ALTER COLUMN kind SET NOT NULL")
    # Die zurückgestellten Gutschriften wieder aktivieren – erkennbar daran, dass es zu
    # ihnen eine negative Rechnung gibt. Die Rechnungen fallen mit der Tabelle.
    op.execute("UPDATE payments SET is_active = TRUE WHERE kind = 'credit'")
    op.execute("DROP TABLE IF EXISTS invoices")
