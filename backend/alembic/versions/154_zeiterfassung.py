"""Zeiterfassung: Vertrag, Einträge, Feiertage, Regeln der Gesellschaft.

* ``time_contracts`` – Vertrag ab Stichtag (Wochenstunden, Arbeitstage, Ferien, Gesellschaft).
* ``time_entries`` – Stempel, Absenzen, Buchungen, Rücknahmen; eine Änderung ersetzt.
* ``holidays`` – bestätigte Feiertage je Gesellschaft.
* ``company_settings.time_rules`` – Kanton und Nachweis-Regeln.
* Verträge und Einträge sind append-only (Trigger, ``domain/timekeeping.append_only_sql``).
* ``user_profiles.employment_start_date``/``weekly_hours`` verlieren ihr Mapping; sie fallen
  im Folge-Deploy (Zwei-Deploy-Regel, ``docs/backlog.md``).

Revision ID: 154
Revises: 153
"""

from alembic import op

from app.domain.timekeeping import append_only_sql

revision = "154"
down_revision = "153"
branch_labels = None
depends_on = None

_STAMPS = "created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, " \
          "is_active BOOLEAN NOT NULL"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS time_contracts (
            id BIGSERIAL PRIMARY KEY,
            person_object_id BIGINT NOT NULL,
            valid_from DATE NOT NULL,
            weekly_minutes INTEGER NOT NULL,
            workdays SMALLINT NOT NULL,
            vacation_weeks NUMERIC(4, 1) NOT NULL,
            company_object_id BIGINT,
            created_by BIGINT,
            {_STAMPS}
        )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_time_contracts_person_object_id "
               "ON time_contracts (person_object_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_time_contracts_person_from "
               "ON time_contracts (person_object_id, valid_from)")
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS time_entries (
            id BIGSERIAL PRIMARY KEY,
            person_object_id BIGINT NOT NULL,
            kind VARCHAR(10) NOT NULL,
            day DATE NOT NULL,
            at TIMESTAMPTZ,
            until DATE,
            art VARCHAR(20),
            minutes INTEGER,
            vacation_minutes INTEGER,
            note TEXT,
            proof_url VARCHAR(200),
            source VARCHAR(10),
            replaces_id BIGINT REFERENCES time_entries (id) ON DELETE RESTRICT,
            idem_key VARCHAR(64),
            created_by BIGINT,
            {_STAMPS}
        )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_time_entries_person_day "
               "ON time_entries (person_object_id, day)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_time_entries_replaces "
               "ON time_entries (replaces_id) WHERE replaces_id IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_time_entries_key "
               "ON time_entries (idem_key) WHERE idem_key IS NOT NULL")
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS holidays (
            id BIGSERIAL PRIMARY KEY,
            company_object_id BIGINT NOT NULL,
            day DATE NOT NULL,
            name VARCHAR(120) NOT NULL,
            created_by BIGINT,
            {_STAMPS}
        )""")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_holidays_company_day "
               "ON holidays (company_object_id, day) WHERE is_active")
    op.execute("ALTER TABLE company_settings ADD COLUMN IF NOT EXISTS time_rules JSON")
    op.execute(append_only_sql())


def downgrade() -> None:
    pass
