"""Welche Stücke eine Buchung bewegt hat: ``material_moves.units``.

Die Nummern wurden bisher aus dem **heutigen** Halter abgeleitet. Schloss ein Abzweig ab
und gab seine Stücke zurück, hielt er nichts mehr – und die Vergangenheit zeigte plötzlich
ALLE Nummern statt der richtigen (Testnotizen #543/#544). Eine abgeleitete Antwort kann
keine Vergangenheit sein; die Nummern gehören zur **Buchung** (ADR 007: was passiert ist,
ändert sich nicht mehr).

**Kein Backfill**: ``NULL`` heisst «diese Buchung stammt aus der Zeit davor» – dort bleibt
es bei der Ableitung (tolerant lesen, streng schreiben).

Revision ID: 100
Revises: 099
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "100"
down_revision = "099"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    # Idempotent (Lehre aus Migration 090): das Lifespan-Netz legt sie notfalls schon an.
    if not _has_column("material_moves", "units"):
        op.add_column("material_moves",
                      sa.Column("units", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    if _has_column("material_moves", "units"):
        op.drop_column("material_moves", "units")
