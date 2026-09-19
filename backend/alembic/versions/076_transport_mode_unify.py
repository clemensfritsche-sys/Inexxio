"""Transport-Modus vereinheitlichen: auto/carrier/self/none → internal/parcel/freight.

ADR 005 «Versand wird abgeleitet, nicht bestellt», UI-Vereinfachung: die frühere Doppelung
aus Transport-Modus (auto | carrier | self | none) UND Sendungsart (parcel | freight) wird
zu EINER Achse ``shipments.transport_mode`` ∈ (internal | parcel | freight) zusammengezogen.
Der abgeleitete Modus (Adress-Klassifikation + geschätzte Last) ist nur noch die vorgewählte
Empfehlung; der Nutzer wählt am Beleg IMMER frei zwischen den drei Optionen.

Bestehende Overrides migrieren (nur ``shipments`` – Datenpflege, kein Schema-Zwang):
  self / none               → internal   (kein Carrier)
  carrier  UND kind='freight' → freight
  carrier  (sonst)          → parcel
  auto                      → NULL        (kein Override → Empfehlung folgt automatisch)

Die Alt-Spalte ``article_process_steps.transport_mode`` bleibt (immer 'auto', nie befüllt) –
zur Laufzeit ignoriert (``logistics.build_embed`` leitet ab). Nichts daran zu ändern.

Revision ID: 076
Revises: 075
Create Date: 2026-07-19
"""
from alembic import op
from sqlalchemy import inspect

revision = '076'
down_revision = '075'
branch_labels = None
depends_on = None


def _has_table(insp, table: str) -> bool:
    return table in insp.get_table_names()


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if not _has_table(insp, "shipments"):
        return
    op.execute("UPDATE shipments SET transport_mode = 'internal' WHERE transport_mode IN ('self', 'none')")
    op.execute("UPDATE shipments SET transport_mode = 'freight' WHERE transport_mode = 'carrier' AND kind = 'freight'")
    op.execute("UPDATE shipments SET transport_mode = 'parcel' WHERE transport_mode = 'carrier'")
    op.execute("UPDATE shipments SET transport_mode = NULL WHERE transport_mode = 'auto'")


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if not _has_table(insp, "shipments"):
        return
    # Verlustbehaftet – die feineren Alt-Werte (self vs. none, carrier-Automatik) sind nicht
    # rekonstruierbar; bestmögliche Rückabbildung.
    op.execute("UPDATE shipments SET transport_mode = 'carrier' WHERE transport_mode IN ('parcel', 'freight')")
    op.execute("UPDATE shipments SET transport_mode = 'self' WHERE transport_mode = 'internal'")
