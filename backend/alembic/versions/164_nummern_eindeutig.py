"""Nummern, die eindeutig sein müssen, sind es in der Datenbank.

* **Unsere Rechnungs- und Gutschriftnummern** (``<Auftragsnummer>-<laufend>``): je eine
  Nummer genau einmal. Vergeben werden beide aus einer Zählung je Auftrag unter Sperre
  (``voucher._our_number``); der Index ist der Riegel darunter. Eine Lieferantenrechnung
  (Ausgabe) trägt die Nummer der Gegenpartei – zwei Lieferanten dürfen dieselbe schicken,
  darum gilt der Index nur für Einnahmen.
* **Jede Person und jede Firma hat ihre Objektnummer** (``object_id NOT NULL``).

Steht schon eine Dublette oder eine Zeile ohne Nummer da, bricht die Migration mit dem
Grund ab – der Dienst bleibt dann auf der alten Revision.

Revision ID: 164
Revises: 163
"""

from alembic import op

revision = "164"
down_revision = "163"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT n FROM (
              SELECT number AS n FROM vouchers WHERE direction = 'in' AND number IS NOT NULL
              UNION ALL
              SELECT credit_number FROM vouchers WHERE credit_number IS NOT NULL) x
            GROUP BY n HAVING count(*) > 1) THEN
            RAISE EXCEPTION 'Doppelte Rechnungs-/Gutschriftnummer in vouchers – zuerst bereinigen.';
          END IF;
          IF EXISTS (SELECT 1 FROM user_profiles WHERE object_id IS NULL)
             OR EXISTS (SELECT 1 FROM company_settings WHERE object_id IS NULL) THEN
            RAISE EXCEPTION 'Person oder Firma ohne Objektnummer – zuerst vergeben.';
          END IF;
        END $$;
    """)
    op.execute("CREATE UNIQUE INDEX uq_vouchers_our_number ON vouchers (number) "
               "WHERE direction = 'in' AND number IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX uq_vouchers_credit_number ON vouchers (credit_number) "
               "WHERE credit_number IS NOT NULL")
    op.execute("ALTER TABLE user_profiles ALTER COLUMN object_id SET NOT NULL")
    op.execute("ALTER TABLE company_settings ALTER COLUMN object_id SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE company_settings ALTER COLUMN object_id DROP NOT NULL")
    op.execute("ALTER TABLE user_profiles ALTER COLUMN object_id DROP NOT NULL")
    op.execute("DROP INDEX IF EXISTS uq_vouchers_credit_number")
    op.execute("DROP INDEX IF EXISTS uq_vouchers_our_number")
