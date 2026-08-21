"""Beschaffungs-Beleg: die Tabelle `purchases`

Der Beleg eines Beschaffungs-Moduls — **ohne eigene Objektnummer**: er läuft unter der
Auftragsnummer, wie jede andere Fachzeile des Prozesses.

Idempotent (``IF NOT EXISTS``), weil das Lifespan-Netz (``create_all``) fehlende
**Tabellen** ohnehin anlegt: läuft es zuerst, darf die Migration danach nicht auflaufen —
sonst stünde Alembic für immer auf 113 und jede künftige Migration wäre blockiert (die
Lehre aus Migration 090).

Revision ID: 114
Revises: 113
"""
from alembic import op

revision = "114"
down_revision = "113"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id              BIGSERIAL PRIMARY KEY,
            order_id        BIGINT        NOT NULL,
            step_id         BIGINT        NOT NULL,
            article_id      BIGINT        NOT NULL,
            quantity        NUMERIC(14,3) NOT NULL DEFAULT 1,
            stage           VARCHAR(20)   NOT NULL DEFAULT 'anfrage',
            supplier_id     BIGINT,
            amount          NUMERIC(12,2),
            currency        VARCHAR(3)    NOT NULL DEFAULT 'CHF',
            reference       VARCHAR(200),
            due_date        DATE,
            quotes          JSONB         NOT NULL DEFAULT '[]',
            ordered_for     NUMERIC(14,3),
            created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """)
    # Ein Beleg je Modul — die Regel steht in der Datenbank, nicht nur im Dienst:
    # `instantiate_for_order` ist idempotent, aber zwei gleichzeitige Freigaben sind es
    # nicht, und der Index ist die einzige Stelle, die das je Anweisung prüft.
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_purchases_step ON purchases (step_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_purchases_order ON purchases (order_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS purchases")
