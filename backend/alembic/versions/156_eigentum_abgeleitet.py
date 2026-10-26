"""Eigentum wird abgeleitet – die Spalte am Stück entfällt (Oktober 2026).

Wem ein Stück gehört, sagt das jüngste nicht stornierte Zahlungsmodul, das es passiert hat
(``services/voucher.sold_units``); gelesen wird es am Ziel des Auftrags («Verkauft» statt
«Freigegeben»). Die gespeicherte Kopie ``instance_units.owner_object_id`` war eine zweite
Wahrheit und fällt weg. **Ein Deploy statt zwei**: ausdrücklich freigegeben, Rückwärts-
kompatibilität ist in dieser Phase nicht nötig.

Eine Wahl «bleibt» gibt es nicht mehr – solche Belege gelten als ungewählt und müssen neu
wählen (``services/voucher.ownership_of`` liest tolerant, darum keine Datenänderung).
"""

from alembic import op

revision = "156"
down_revision = "155"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE instance_units DROP COLUMN IF EXISTS owner_object_id")


def downgrade() -> None:
    op.execute("ALTER TABLE instance_units ADD COLUMN IF NOT EXISTS owner_object_id BIGINT")
