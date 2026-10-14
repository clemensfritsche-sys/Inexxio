"""Die Firma ist ein Datensatz – für jede Firma, nicht nur für unsere (CRM Schritt 1).

* ``company_settings.is_own`` – «eine unserer Gesellschaften». Jede bestehende Zeile ist
  eine, darum kommt die Spalte mit ``DEFAULT true`` und bekommt danach ``false`` als
  Vorgabe: jede neue Firma ist zuerst fremd.
* Die Firmentexte an der Person (Name, Rechtsform, UID, MWST, Handelsregister, Website)
  werden zu Firmen-Datensätzen (``people.move_company_texts`` – nur bei eindeutiger
  Gleichheit zusammengelegt) und fallen danach.
* E-Mail klein und Objektnummer für jede Person (``people.repair_sql``).

Dieselben Schritte stehen im Lifespan-Netz (``main._ensure_columns``) – die dev-Datenbank
fährt kein ``alembic upgrade head`` (#778).
"""
import sqlalchemy as sa
from alembic import op

from app.services.people import MOVED_COLUMNS, move_company_texts, repair_sql

revision = "142"
down_revision = "141"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "is_own" not in _columns("company_settings"):
        op.add_column("company_settings", sa.Column(
            "is_own", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.alter_column("company_settings", "is_own", server_default=sa.text("false"))
    bind = op.get_bind()
    move_company_texts(bind)
    have = _columns("user_profiles")
    for col in MOVED_COLUMNS:
        if col in have:
            op.drop_column("user_profiles", col)
    for stmt in repair_sql():
        bind.execute(sa.text(stmt))


def downgrade() -> None:
    have = _columns("user_profiles")
    for col in ("company_name", "company_website", "trade_register_nr",
                "trade_register_canton"):
        if col not in have:
            op.add_column("user_profiles", sa.Column(col, sa.String(255)))
    for col in ("legal_form", "uid_number", "vat_number"):
        if col not in have:
            op.add_column("user_profiles", sa.Column(col, sa.String(50)))
    if "vat_registered" not in have:
        op.add_column("user_profiles", sa.Column(
            "vat_registered", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    if "is_own" in _columns("company_settings"):
        op.drop_column("company_settings", "is_own")
