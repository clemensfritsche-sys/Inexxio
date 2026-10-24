"""085 – «Gesperrt» ist EIN Zustand; ein fehlgeschlagener Befund ist nicht terminal.

**(1) Zwei Werte, eine Bedeutung.** Eine Instanz, die eine Datenerfassung nicht bestand,
trug ``quality='failed'``; eine bewusst ausgesetzte trug seit Migration 084
``quality='blocked'``. Beides heisst «vorhanden, aber nicht verwendbar», beides fällt über
dieselbe Bedingung aus FIFO/Bestand, beides wird auf demselben Weg wieder aufgehoben – nur
die Namen waren verschieden. Ab hier gibt es **einen** Wert (``blocked``) und **ein** Wort
(«Gesperrt»); ``failed`` wird nur noch tolerant gelesen (``inventory.is_blocked``).

**(2) Fehlgeschlagen war terminal.** Ein Schritt mit ``inspections.result='failed'`` blieb
für immer ``failed``; damit war ``all_steps_done`` nie wahr, der Auftrag schloss nie ab und
seine Instanzen wurden nie freigegeben – sie hingen dauerhaft in «In Arbeit», auch wenn eine
Abweichung den Fall längst geklärt hatte. ``resolved_by_order_id`` hält jetzt fest, welcher
**Folgeauftrag** den Befund geklärt hat. Der Befund selbst bleibt ``failed``: was gemessen
wurde, wird nicht nachträglich schöngeschrieben.

Revision ID: 085
Revises: 084
Create Date: 2026-07-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '085'
down_revision = '084'
branch_labels = None
depends_on = None


def _has(insp, table: str, column: str) -> bool:
    if table not in set(insp.get_table_names()):
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "inspections" in set(insp.get_table_names()) and not _has(insp, "inspections", "resolved_by_order_id"):
        op.add_column("inspections", sa.Column("resolved_by_order_id", sa.BigInteger(), nullable=True))
    # Altbestand auf den einen Wert ziehen (gelesen wird beides, geschrieben nur 'blocked').
    if "instances" in set(insp.get_table_names()):
        bind.execute(sa.text("UPDATE instances SET quality = 'blocked' WHERE quality = 'failed'"))


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if _has(insp, "inspections", "resolved_by_order_id"):
        op.drop_column("inspections", "resolved_by_order_id")
