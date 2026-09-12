"""Ein Modul hat eine ID, keinen Namen – und die Journey braucht ihren Index.

``…_steps.name``       **Entfällt.** Ein Modul heisst nach seinem **Typ**
                       (``domain/modules``), und das war es immer: das Eingabefeld hatte
                       genau eine richtige Antwort und war trotzdem Pflicht. Als
                       *Identität* taugte es ohnehin nie – ein Name lässt sich ändern,
                       doppelt vergeben oder leer lassen, und dann zeigt die Historie auf
                       etwas, das es so nie gab. Die Identität ist die ``id``: sie
                       entsteht mit der Zeile und ändert sich nie (Testnotizen #682/#687).

                       Nebenbei verschwindet damit die Meldung «String should have at
                       least 1 character» an ihrer Wurzel (#686): sie kam von genau
                       diesem Pflichtfeld.

``ix_process_events``  Neuer Index ``(instance_unit_id, id)``. Die **Journey** einer
                       Einzelinstanz wird aus dem Ereignis-Log abgeleitet – «welcher
                       Auftrag war vor bzw. nach diesem?» ist ein Sprung an die Nachbar-
                       Zeile derselben Einzelinstanz. Ein **Index** beschleunigt diese
                       Frage; er beantwortet sie nicht und ist darum kein zweiter
                       Datenbestand.

Revision ID: 108
Revises: 107
"""
import sqlalchemy as sa
from alembic import op

revision = "108"
down_revision = "107"
branch_labels = None
depends_on = None

_NAME_TABLES = ("process_steps", "article_process_steps")
_JOURNEY_INDEX = "ix_process_events_unit_timeline"


def _has_column(table: str, column: str) -> bool:
    return bool(op.get_bind().execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table, "c": column}).first())


def _has_table(table: str) -> bool:
    return bool(op.get_bind().execute(
        sa.text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar())


def upgrade() -> None:
    for table in _NAME_TABLES:
        if _has_column(table, "name"):
            op.drop_column(table, "name")

    if _has_table("process_events"):
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {_JOURNEY_INDEX} "
            f"ON process_events (instance_unit_id, id)"
        )


def downgrade() -> None:
    """Struktur zurück – **nicht** die alten Namen.

    Welchen Namen eine Zeile trug, ist nicht rekonstruierbar; ein erfundener wäre eine
    Lüge. Die Spalte kommt darum leer zurück (mit Default), damit sie nicht NULL ist.
    """
    op.execute(f"DROP INDEX IF EXISTS {_JOURNEY_INDEX}")
    for table in _NAME_TABLES:
        if _has_table(table) and not _has_column(table, "name"):
            op.add_column(table, sa.Column(
                "name", sa.String(120), nullable=False, server_default=sa.text("''")))
