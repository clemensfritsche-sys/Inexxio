"""Der Beleg bekommt eine Richtung — und das Geld eine Zeile

Drei Dinge, ein Deploy:

1. **``purchases.direction``** (``buy`` · ``sell``). Einkauf und Verkauf sind dasselbe
   Geschäft aus zwei Blickwinkeln; was sie unterscheidet, steht als Daten im ``Flow``
   (``domain/procurement``). Jeder bestehende Beleg ist ein Einkauf – das ist der
   Default, und damit ändert die Spalte an keinem von ihnen etwas.

2. **Die Stufen werden neutral** (``anfrage``/``bestellung``/``wareneingang`` →
   ``offer``/``commitment``/``fulfilment``, ``storniert`` → ``cancelled``). Die alten
   Namen beschrieben den Einkauf und wären an einem Verkaufs-Beleg schlicht falsch: ein
   «Wareneingang», bei dem Ware das Haus verlässt, ist kein Name, sondern ein Irrtum mit
   Bestand.

   **Beide Revisionen bleiben lauffähig.** Der neue Code liest die alten Werte weiterhin
   (``procurement.normalize``) – er braucht diese Migration nicht, sie räumt nur auf. Und
   der alte Code läuft im Deploy-Fenster gegen die neuen Werte; das ist die eine bewusst
   in Kauf genommene Sekunde, und sie betrifft nur die Beschriftung einer Stufe, nicht
   die Daten.

3. **``payments``** – die eine neue Tabelle. Es gibt **keine Forderungs-Tabelle**: offen
   ist eine Subtraktion (``services/payments.balance``). Vollständiger Spaltensatz
   inklusive der geerbten (``is_active``, ``created_at``, ``updated_at``) – die Lehre aus
   Migration 114, wo genau die fehlte und jeder Lesezugriff gegen ein frisches Schema
   scheiterte.

Dazu ``purchases.committed_on``: der Tag der Zusage. Ab ihm läuft die Zahlungsfrist, und
er steht sonst nirgends – ``created_at`` ist die Anlage, ``updated_at`` bewegt sich.

Revision ID: 122
Revises: 121
"""
from alembic import op

revision = "122"
down_revision = "121"
branch_labels = None
depends_on = None

#: Alt → neu. Dieselbe Zuordnung liest ``procurement._ALIASES`` zur Laufzeit; hier steht
#: sie ausgeschrieben, weil eine Migration keinen Anwendungscode importieren darf – sie
#: muss auch dann noch laufen, wenn das Modul längst anders aussieht.
_STAGES = (
    ("anfrage", "offer"),
    ("bestellung", "commitment"),
    ("wareneingang", "fulfilment"),
    ("storniert", "cancelled"),
)


def upgrade() -> None:
    op.execute("ALTER TABLE purchases ADD COLUMN IF NOT EXISTS "
               "direction VARCHAR(10) NOT NULL DEFAULT 'buy'")
    op.execute("ALTER TABLE purchases ADD COLUMN IF NOT EXISTS committed_on DATE")

    # Idempotent: läuft die Migration zweimal, findet die zweite Runde nichts mehr.
    for old, new in _STAGES:
        op.execute(f"UPDATE purchases SET stage = '{new}' WHERE stage = '{old}'")
    op.execute("ALTER TABLE purchases ALTER COLUMN stage SET DEFAULT 'offer'")

    op.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id           BIGSERIAL PRIMARY KEY,
            purchase_id  BIGINT        NOT NULL,
            kind         VARCHAR(10)   NOT NULL DEFAULT 'payment',
            -- **Darf negativ sein**: eine Erstattung ist eine Zahlung rückwärts.
            amount       NUMERIC(12,2) NOT NULL,
            currency     VARCHAR(3)    NOT NULL DEFAULT 'CHF',
            paid_at      DATE,
            method       VARCHAR(20),
            reference    VARCHAR(200),
            note         VARCHAR(400),
            -- Die geerbten Spalten (``Base``/``TimestampMixin``). Sie hier zu vergessen
            -- fällt lokal nicht auf – dort legt das Lifespan-``create_all`` die Tabelle
            -- aus dem Modell an; gegen ein Schema, das nur aus den Migrationen kommt,
            -- scheitert danach jeder Lesezugriff (Migration 114).
            is_active    BOOLEAN       NOT NULL DEFAULT TRUE,
            created_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """)
    # **Dieselbe Referenz ist dieselbe Zahlung.** Der Schutz gegen die doppelt zugestellte
    # Webhook-Meldung – in der Datenbank, nicht nur im Dienst: ``record`` prüft je Aufruf,
    # zwei gleichzeitige Zustellungen sind nicht ein Aufruf.
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_reference "
               "ON payments (reference) WHERE reference IS NOT NULL AND is_active")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_purchase ON payments (purchase_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS payments")
    for old, new in _STAGES:
        op.execute(f"UPDATE purchases SET stage = '{old}' WHERE stage = '{new}'")
    op.execute("ALTER TABLE purchases ALTER COLUMN stage SET DEFAULT 'anfrage'")
    op.execute("ALTER TABLE purchases DROP COLUMN IF EXISTS committed_on")
    op.execute("ALTER TABLE purchases DROP COLUMN IF EXISTS direction")
