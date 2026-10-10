"""Ein AKTIVER Beleg je Modul — der Unique-Index wird partiell

Seit das **Bewegen**-Modul einen Einkaufs-Beleg tragen kann (``Module.buys``), ist
«eingekauft» die Antwort auf «gibt es einen Beleg?». Wer die Wahl zurücknimmt
(``revoke`` an der ersten Stufe), muss sie darum wirklich los werden – der Beleg geht
per Soft-Delete (``is_active = false``), wie jeder Datensatz im Haus.

**Und genau daran hing der volle Unique-Index**: ein zurückgenommener Beleg blockierte
jeden neuen am selben Modul, und «eingekauft ↔ doch selbst ↔ dann doch eingekauft» wäre
eine Sackgasse gewesen. Partiell gilt die Regel weiter, nur präziser formuliert: **ein
AKTIVER Beleg je Modul**.

Revision ID: 119
Revises: 118
"""
from alembic import op

revision = "119"
down_revision = "118"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: das Netz (``create_all``) legt den Index auf einer frischen Datenbank
    # bereits in seiner neuen Form an – dann gibt es hier nichts zu tun.
    op.execute("DROP INDEX IF EXISTS uq_purchases_step")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_purchases_step "
               "ON purchases (step_id) WHERE is_active")


def downgrade() -> None:
    # **Zurück kann scheitern, und das ist ehrlich:** gibt es zu einem Modul einen
    # zurückgenommenen UND einen neuen Beleg, lässt sich der volle Index nicht mehr
    # anlegen. Die zurückgenommenen zu löschen wäre Datenverlust ohne Auftrag.
    op.execute("DROP INDEX IF EXISTS uq_purchases_step")
    op.execute("CREATE UNIQUE INDEX uq_purchases_step ON purchases (step_id)")
