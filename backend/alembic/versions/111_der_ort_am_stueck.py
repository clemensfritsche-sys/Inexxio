"""Der Ort — eine Spalte am Stück, kein Zustand.

Jede Einzelinstanz bekommt die Objektnummer ihres **Halters**. Kein Typfeld daneben:
Objektnummern sind systemweit eindeutig, der Typ ist ableitbar. Kein ``NOT NULL``:
standortlos ist ein regulärer Zustand — ein frisch erzeugtes Stück liegt nirgends, bis
ein Modul es irgendwohin bringt.

**Warum eine Spalte und keine append-only Tabelle.** Der Ort ist die Gegenwart, und die
Vergangenheit steht ohnehin schon woanders: jede Bewegung läuft über
``process.confirm_step`` und schreibt dort ihren Eintrag in ``process_events`` — mit
Herkunft und Ziel. Eine zweite Tabelle daneben wäre eine zweite Wahrheit über denselben
Vorgang. (Die Grenze ist benannt: käme später ein Ablegen **ausserhalb** eines Auftrags
dazu, hätte genau dieser Weg keine Historie. Dann kommt sie dort dazu, und diese Spalte
bleibt richtig.)

**Idempotent.** Die Spalte wird nur angelegt, wenn sie fehlt — und sie steht zusätzlich
im Lifespan-Sicherheitsnetz (``main._COLUMN_SAFETY_NET``), damit die App sie auch dann
bekommt, wenn Alembic auf einer unbekannten Revision hängt. Das ist die Lehre aus
Migration 090: eine neue Spalte auf einer bestehenden Tabelle ist erst fertig, wenn sie
an beiden Stellen steht.

**Aufräumen des zurückgerollten Versuchs.** ``unit_places``, ``awards`` und
``award_offers`` stammen aus PR #220 (Migrationen 111–113), der als Ganzes zurückgerollt
wurde. Stand die Datenbank beim Revert noch auf 113 und wurde nicht zurückgefahren,
liegen sie als Leichen herum — ohne Modell, ohne Leser, ohne Weg sie loszuwerden.
``IF EXISTS`` macht das zum No-op, wo sie längst weg sind.

Revision ID: 111
Revises: 110
"""
from alembic import op

revision = "111"
down_revision = "110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE instance_units ADD COLUMN IF NOT EXISTS place_object_id BIGINT"
    )
    # Die Gegenrichtung «was liegt hier» ist eine Frage, die eine Bestandsansicht je
    # Kettenstufe stellt – ohne Index ein Full Scan über alle Stücke.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_instance_units_place "
        "ON instance_units (place_object_id)"
    )
    for table in ("award_offers", "awards", "unit_places"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_instance_units_place")
    op.execute("ALTER TABLE instance_units DROP COLUMN IF EXISTS place_object_id")
