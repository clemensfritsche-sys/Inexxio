"""qc_status in zwei getrennte Achsen aufteilen: quality + disposition.

Der überladene ``instances.qc_status`` (pending/passed/failed/consumed/sold/scrapped)
mischte ZWEI orthogonale Fragen: «ist es gut?» (QC-Verdikt) und «wo ist es?»
(Verbleib im Lager). Diese Migration trennt sie sauber:

    quality     ∈ pending | passed | failed
    disposition ∈ in_process | in_stock | consumed | sold | scrapped

«Verfügbar» heisst ab jetzt explizit ``quality='passed' AND disposition='in_stock'``.

Backfill-Abbildung aus dem alten qc_status:
    pending  → (pending, in_process)     passed   → (passed, in_stock)
    failed   → (failed,  in_process)     consumed → (passed, consumed)
    sold     → (passed,  sold)           scrapped → (failed, scrapped)

Revision ID: 030
Revises: 029
Create Date: 2026-06-25
"""
from alembic import op
from sqlalchemy import inspect

revision = '030'
down_revision = '029'
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if not _has_table(insp, 'instances'):
        return
    cols = {c['name'] for c in insp.get_columns('instances')}

    if 'quality' not in cols:
        op.execute("ALTER TABLE instances ADD COLUMN quality VARCHAR(20) NOT NULL DEFAULT 'pending'")
    if 'disposition' not in cols:
        op.execute("ALTER TABLE instances ADD COLUMN disposition VARCHAR(20) NOT NULL DEFAULT 'in_process'")

    if 'qc_status' in cols:
        op.execute(
            "UPDATE instances SET quality = CASE qc_status "
            "WHEN 'passed' THEN 'passed' WHEN 'failed' THEN 'failed' "
            "WHEN 'consumed' THEN 'passed' WHEN 'sold' THEN 'passed' "
            "WHEN 'scrapped' THEN 'failed' ELSE 'pending' END"
        )
        op.execute(
            "UPDATE instances SET disposition = CASE qc_status "
            "WHEN 'passed' THEN 'in_stock' WHEN 'consumed' THEN 'consumed' "
            "WHEN 'sold' THEN 'sold' WHEN 'scrapped' THEN 'scrapped' "
            "ELSE 'in_process' END"
        )
        op.execute("ALTER TABLE instances DROP COLUMN qc_status")


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if not _has_table(insp, 'instances'):
        return
    cols = {c['name'] for c in insp.get_columns('instances')}

    if 'qc_status' not in cols:
        op.execute("ALTER TABLE instances ADD COLUMN qc_status VARCHAR(20) NOT NULL DEFAULT 'pending'")
    # Zwei Achsen zurück auf das überladene qc_status falten (Verbleib dominiert).
    op.execute(
        "UPDATE instances SET qc_status = CASE "
        "WHEN disposition='scrapped' THEN 'scrapped' "
        "WHEN disposition='sold' THEN 'sold' "
        "WHEN disposition='consumed' THEN 'consumed' "
        "WHEN quality='failed' THEN 'failed' "
        "WHEN quality='passed' AND disposition='in_stock' THEN 'passed' "
        "ELSE 'pending' END"
    )
    for col in ('quality', 'disposition'):
        if col in cols:
            op.execute(f"ALTER TABLE instances DROP COLUMN {col}")
