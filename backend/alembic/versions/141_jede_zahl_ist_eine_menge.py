"""►►► **Jede Zahl auf dem Beleg ist eine MENGE** (Testnotizen #1054–#1056). ◄◄◄

Diese Migration **legt keine Spalte an**. Sie dreht Daten, und zwar dort, wo ein
Korrekturbeleg bis hierher negativ stand:

* ``vouchers.amount`` und die gespiegelte Steuer-Aufteilung ``vouchers.vat`` – ``bill``
  machte aus der Summe der Positionen einen **negativen** Betrag, sobald ``corrects_id``
  gesetzt war;
* die **Zahlungen** darauf (``voucher_entries.amount``) – eine Erstattung an einer
  Gutschrift musste man als Minus tippen.

**Warum überhaupt:** drei Leser fragen «ist der Betrag grösser als null?», und bei einer
Gutschrift ist er das nie. ``pay_online`` fiel damit weg, ``next_payment`` blieb leer, und
``settled`` (``paid >= agreed``) war **strukturell unerreichbar** – das Modul liess sich
bei einem Saldo von 0 nicht abschliessen. Die Regel heisst jetzt: der Betrag ist eine
Menge, und *dass* der Beleg mindert, sagt ``corrects_id``.

**Die Anweisungen stehen in ``domain/voucher.magnitude_sql``**, nicht hier: die
dev-Datenbank fährt kein ``alembic upgrade head`` (Testnotiz #778), also liest sie das
Lifespan-Netz ebenfalls – zweimal ausgeschrieben wären es zwei Wahrheiten. Beide sind
**selbstbegrenzend** (sie fassen nur, was negativ ist), und damit idempotent.

Revision ID: 141
Revises: 140
"""

import sqlalchemy as sa
from alembic import op

from app.domain.voucher import magnitude_sql

revision = "141"
down_revision = "140"
branch_labels = None
depends_on = None


def _ready() -> bool:
    """Gibt es die Spalten, die hier gedreht werden?

    Gegen ein Schema, das nur aus den Migrationen kommt, ist die Antwort immer ja; auf der
    dev-Datenbank zieht das Spalten-Netz sie nach, und dort kann diese Migration vor dem
    Netz laufen. Eine Reparatur, die an einer fehlenden Spalte abbricht, nimmt jede andere
    mit in den Rollback – die Lehre aus Migration ``090``.
    """
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if not {"vouchers", "voucher_entries"} <= tables:
        return False
    cols = {c["name"] for c in insp.get_columns("vouchers")}
    return {"amount", "vat", "corrects_id"} <= cols


def upgrade() -> None:
    if not _ready():
        return
    bind = op.get_bind()
    for stmt in magnitude_sql():
        bind.execute(sa.text(stmt))


def downgrade() -> None:
    """Zurück zum Vorzeichen – dieselbe Drehung, nur in die andere Richtung.

    Sie ist **nicht** symmetrisch formuliert, sondern spiegelbildlich: gedreht wird, was
    **positiv** ist. Damit bleibt auch der Rückweg selbstbegrenzend.
    """
    if not _ready():
        return
    op.execute("""
        UPDATE vouchers v
           SET amount = -v.amount,
               vat = CASE WHEN v.vat IS NULL THEN NULL ELSE (
                   SELECT jsonb_agg(e || jsonb_build_object(
                              'net', '-' || ltrim(e->>'net', '-'),
                              'tax', '-' || ltrim(e->>'tax', '-')))
                     FROM jsonb_array_elements(v.vat) e
               ) END
         WHERE v.corrects_id IS NOT NULL AND v.amount > 0
    """)
    op.execute("""
        UPDATE voucher_entries e
           SET amount = -e.amount
         WHERE e.amount > 0
           AND e.voucher_id IN (SELECT id FROM vouchers
                                 WHERE corrects_id IS NOT NULL)
    """)
