"""Aufräumen A2: vier doppelte Indizes weg (Änderungsakte §6).

Jeder ist schon der Anfang eines anderen bzw. wird nie allein gefragt:

* ``ix_vouchers_step_id`` – ``uq_vouchers_step`` (eindeutig, ohne Bedingung seit 175).
* ``ix_time_contracts_person_object_id`` – Anfang von ``uq_time_contracts_person_from``.
* ``ix_instance_units_instance_id`` – Anfang von ``uq_instance_units_instance_suffix``.
* ``ix_log_actor_at`` – jede Frage nach dem Handelnden fragt auch das Ereignis
  (``ix_log_event_at``); am Log kostet jeder Index bei jedem Schreiben.

Die Spalten aus A1 gehen erst im Folge-Deploy (Zwei-Deploy-Regel, Migration 182).

Revision ID: 181
Revises: 180
"""

from alembic import op

revision = "181"
down_revision = "180"
branch_labels = None
depends_on = None

_GONE = {
    "ix_vouchers_step_id": "vouchers (step_id)",
    "ix_time_contracts_person_object_id": "time_contracts (person_object_id)",
    "ix_instance_units_instance_id": "instance_units (instance_id)",
    "ix_log_actor_at": "log (actor_id, at)",
}


def upgrade() -> None:
    for name in _GONE:
        op.execute(f"DROP INDEX IF EXISTS {name}")


def downgrade() -> None:
    for name, target in _GONE.items():
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {target}")
