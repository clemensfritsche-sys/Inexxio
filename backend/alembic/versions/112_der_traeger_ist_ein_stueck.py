"""Der Träger ist ein Stück — die zweite Art, einen Halter zu nennen.

Bis hierher konnte ein Ort nur eine **Objektnummer** sein (Instanz · Benutzer ·
Unternehmen). Für ein **verbautes** Stück gibt es die nicht: sein Halter ist eine
Einzelinstanz, und die zieht bewusst keine Objektnummer (PROCESS_CORE §2.2) — es kann
für sie gar kein Etikett geben. Die Instanz-Nummer stattdessen wäre eine **Gruppe**,
kein Ort: bei einer Charge über 600 Getriebe sagte sie nicht, in welchem.

**Zwei Spalten, weil es zwei Arten von Halter gibt — nicht zwei Antworten auf eine
Frage.** Die Genauigkeit des Ortes ist die Genauigkeit seiner Quelle:

* **gescannt** ⇒ ``place_object_id``. Was man scannt, ist ein Etikett, und ein Etikett
  hat die Instanz. Feiner geht es nicht, ohne zu raten.
* **verbaut** ⇒ ``place_unit_id``. Hier weiss das Modul das Stück genau — die Zuteilung
  nennt es (``consumption.plan``). Gröber wäre es, die Genauigkeit wegzuwerfen.

Ein ``CHECK`` erzwingt, dass höchstens eines gesetzt ist: der Ort bleibt **eine**
Aussage, sie hat nur zwei mögliche Formen.

**Das ist nicht die Genealogie.** Der Log hält fest, **worin** ein Stück verbaut wurde
(``payload.into``) — unveränderlich, und er überlebt die Demontage. Diese Spalte sagt,
**wo es jetzt liegt** — und wird beim Ausbau geräumt. Dass die beiden Werte auseinander
laufen können, ist der Beweis, dass es zwei Fragen sind (§9.6).

**Idempotent** und zusätzlich im Lifespan-Sicherheitsnetz (``main._COLUMN_SAFETY_NET``) —
die Lehre aus Migration 090: eine neue Spalte auf einer bestehenden Tabelle ist erst
fertig, wenn sie an beiden Stellen steht.

Revision ID: 112
Revises: 111
"""
from alembic import op

revision = "112"
down_revision = "111"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE instance_units ADD COLUMN IF NOT EXISTS place_unit_id BIGINT"
    )
    # Die Gegenrichtung «was steckt in diesem Stück» – dieselbe Frage wie
    # ``ix_instance_units_place``, nur für den Träger.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_instance_units_place_unit "
        "ON instance_units (place_unit_id)"
    )
    # **Der Ort ist EINE Aussage.** Ohne diesen Riegel könnte ein Stück gleichzeitig im
    # Regal und in einem Getriebe liegen – und welche der beiden Angaben gilt, entschiede
    # die Lesestelle. Genau die Sorte Zweideutigkeit, die eine Ansicht später zerlegt.
    op.execute(
        "ALTER TABLE instance_units DROP CONSTRAINT IF EXISTS ck_instance_units_one_place"
    )
    op.execute(
        "ALTER TABLE instance_units ADD CONSTRAINT ck_instance_units_one_place "
        "CHECK (place_object_id IS NULL OR place_unit_id IS NULL)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE instance_units DROP CONSTRAINT IF EXISTS ck_instance_units_one_place"
    )
    op.execute("DROP INDEX IF EXISTS ix_instance_units_place_unit")
    op.execute("ALTER TABLE instance_units DROP COLUMN IF EXISTS place_unit_id")
