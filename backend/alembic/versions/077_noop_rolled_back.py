"""077 – **zurückgenommen** (No-op-Platzhalter).

Diese Revision trug ursprünglich den Standort-Umbau «Ort statt Lagerplatz» (Drop von
``storage_locations``, ``instances.place`` …). Der Umbau wurde zurückgerollt, weil der
Lagerplatz-Datensatztyp vorerst **bestehen bleiben soll**.

Die Revisionsnummer bleibt als **No-op** erhalten, damit die Alembic-Kette in JEDEM Fall
konsistent ist:

* DB steht auf 076 → dieser No-op hebt sie auf 077, ohne etwas zu ändern (das Schema
  entspricht dem zurückgerollten Code).
* DB steht bereits auf 077 (Migration war doch durchgelaufen) → Alembic findet die
  Revision und bricht NICHT mit «Can't locate revision 077» ab. Etwaige damals
  angelegte Spalten (``instances.place``) bleiben ungenutzt liegen; die Tabelle
  ``storage_locations`` legt ``create_all()` beim Start wieder an.

Ein erneuter Anlauf des Standort-Umbaus bekommt eine **neue** Revisionsnummer.

Revision ID: 077
Revises: 076
Create Date: 2026-07-25
"""

revision = '077'
down_revision = '076'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Bewusst leer – siehe Modul-Docstring."""


def downgrade() -> None:
    """Bewusst leer – siehe Modul-Docstring."""
