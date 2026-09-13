"""Der Geldvorgang hat zwei Parteien — und was gehandelt wird, sagt der Prozess

Zwei Spalten an ``deals``:

``quotes``        der **Angebotsspiegel** – je angefragter Gegenpartei eine Zeile
                  ``{party, amount, lead_days, payment_days, state}``. Er ist zugleich
                  die Antwort auf «woran ist dieser Betrachter beteiligt?»
                  (``deal.mine``, JSONB-Containment) und damit die Grundlage des sehr
                  engen Zugangs, den eine Gegenpartei bekommt.

``agreed_lines``  **was gehandelt wird**, abgeleitet aus dem Prozess und mit der Zusage
                  eingefroren: ``{article, quantity}``. Davor gibt es die Zeilen gar
                  nicht – sie SIND der Prozess und ziehen von selbst nach. Ab der Zusage
                  ist eine zweite Partei gebunden, und was zugesagt wurde, ändert sich
                  nicht mehr dadurch, dass der Auftrag später Stücke verliert.

``quotes`` ist ``NOT NULL DEFAULT '[]'`` – eine Liste, die es nicht gibt, wäre ein
zweiter Fall neben der leeren, und jede Lesestelle müsste ihn kennen.

**Beide gehören zusätzlich ins ``_COLUMN_SAFETY_NET``** (die Lehre aus Migration 090):
der Deploy fährt gegen dev kein ``alembic upgrade``, und ``create_all`` legt zwar eine
fehlende Tabelle an, aber **nie** eine fehlende Spalte.

Revision ID: 125
Revises: 124
"""
from alembic import op

revision = "125"
down_revision = "124"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE deals ADD COLUMN IF NOT EXISTS quotes JSONB "
               "NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE deals ADD COLUMN IF NOT EXISTS agreed_lines JSONB")

    # ►► **Bestehende Vorgänge bekommen ihre Angebotszeile.** ◄◄
    #
    # Ein Vorgang, der bereits zugesagt ist, hat eine Gegenpartei – ohne diese Zeile wäre
    # sie ab jetzt an ihrem eigenen Vorgang nicht mehr beteiligt (``mine`` liest
    # ``quotes``), und der Angebotsspiegel stünde leer, obwohl der Zuschlag längst
    # gefallen ist.
    op.execute("""
        UPDATE deals
           SET quotes = jsonb_build_array(jsonb_build_object(
                 'party', party_id,
                 'amount', CASE WHEN amount IS NULL THEN NULL
                                ELSE to_jsonb(to_char(amount, 'FM9999999990.00')) END,
                 'lead_days', NULL,
                 'payment_days', to_jsonb(due_days),
                 'state', CASE WHEN stage = 'offer' THEN 'angefragt' ELSE 'gewaehlt' END))
         WHERE party_id IS NOT NULL AND quotes = '[]'::jsonb
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE deals DROP COLUMN IF EXISTS agreed_lines")
    op.execute("ALTER TABLE deals DROP COLUMN IF EXISTS quotes")
