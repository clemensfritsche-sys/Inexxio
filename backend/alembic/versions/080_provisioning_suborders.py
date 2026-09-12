"""080 – Bereitstellung als Unter-Auftrag (``reason='provisioning'``).

Physisch nötige Transporte werden nicht mehr als Prozessschritt **geplant**, sondern zur
Laufzeit **abgeleitet**: Braucht ein Schritt sein Material an einem bestimmten Ort und
liegt es woanders, entsteht ein Bereitstellungs-Unter-Auftrag, der genau diese Instanzen
dorthin bringt (``services/provisioning.py``).

Diese Migration fügt nur die Bindung an den auslösenden Schritt hinzu: ein Auftrag kann
mehrere Schritte haben, die unabhängig voneinander Material an verschiedene Orte
brauchen – ohne die Spalte liessen sich ihre Bereitstellungen nicht auseinanderhalten
(der Idempotenz-Check «läuft für diesen Schritt schon eine?» wäre nicht formulierbar).

``orders.reason`` bleibt unverändert: die Spalte ist VARCHAR(20) (Migration 060),
``'provisioning'`` hat 12 Zeichen und passt.

Zusätzlich werden die zuletzt automatisch gesäten Begleit-Bewegungen aufgeräumt, die
**noch nie ausgeführt** wurden: Das System legt keine Prozessschritte mehr an, und ein
nie benutzter Zwangsschritt aus der Vorgänger-Logik wäre ab jetzt ein Schritt, den
niemand angelegt hat und den niemand braucht. Begleiter **mit** Fachzeile (bereits
gebucht) bleiben unangetastet – sie sind gelebte Historie.

Idempotent: ein erneuter Lauf ist ein No-op.

Revision ID: 080
Revises: 079
Create Date: 2026-07-26
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '080'
down_revision = '079'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    tables = set(insp.get_table_names())

    if "orders" in tables:
        cols = {c["name"] for c in insp.get_columns("orders")}
        if "provisioning_step_id" not in cols:
            op.add_column("orders", sa.Column("provisioning_step_id", sa.BigInteger(), nullable=True))
            op.create_index("ix_orders_provisioning_step_id", "orders", ["provisioning_step_id"])

    # Nie ausgeführte Begleit-Bewegungen deaktivieren (kein Movement-Beleg daran).
    if {"article_process_steps", "movements"} <= tables:
        aps = {c["name"] for c in insp.get_columns("article_process_steps")}
        if "companion" in aps:
            op.execute("""
                UPDATE article_process_steps s
                   SET is_active = false
                 WHERE s.companion = true
                   AND s.is_active = true
                   AND NOT EXISTS (SELECT 1 FROM movements m WHERE m.step_id = s.id)
            """)


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if "orders" not in set(insp.get_table_names()):
        return
    if "provisioning_step_id" in {c["name"] for c in insp.get_columns("orders")}:
        op.drop_index("ix_orders_provisioning_step_id", table_name="orders")
        op.drop_column("orders", "provisioning_step_id")
