"""Datenreparatur: Shop-Versandschritte als gesperrten Pflicht-Versand markieren.

Der Shop-Verkaufsauftrag (``sales._create_multiline_sale_order``) legte seinen
Versand-Schritt bisher OHNE ``locked=True`` / ``mode='customer'`` an – anders als der
ERP-Verkauf (``process_steps.sync_locked_movements``). Damit galt die Locked-Ausnahme
der Fehlmengen-Prüfung (``process.step_shortfalls``) nicht: nach der Zahlung war die
Ware «verkauft» (aus dem freien Bestand weg), der Versand-Schritt dadurch dauerhaft
«blockiert» und der Shop-Auftrag konnte nie versendet/abgeschlossen werden.

Der Code-Fix erzeugt neue Schritte korrekt; diese Migration repariert die BESTEHENDEN:
alle aktiven, nicht gesperrten movement-Schritte mit Personen-Ziel an Aufträgen mit
Shop-Verkaufsbeleg werden zu ``locked=true, mode='customer'``.

Revision ID: 074
Revises: 073
Create Date: 2026-07-14
"""
from alembic import op
from sqlalchemy import inspect

revision = '074'
down_revision = '073'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    tables = insp.get_table_names()
    if "article_process_steps" not in tables or "sales" not in tables:
        return
    # ``locked`` ist eine **Altlast-Spalte**: sie wurde nie von einer Migration angelegt,
    # sondern nur vom Lifespan-``create_all`` aus dem damaligen Modell – und Migration 081
    # hat sie wieder entfernt. Auf einer **frischen** Datenbank existiert sie hier also gar
    # nicht, und diese reine Datenreparatur brach den Aufbau von Grund auf ab («column
    # s.locked does not exist»). Eine Datenreparatur muss überspringbar sein, wenn es nichts
    # zu reparieren gibt: ohne Spalte gibt es keine Altdaten. (Dieselbe Vorsichtsmassnahme
    # wie in 079, nur dort war sie von Anfang an drin.)
    cols = {c["name"] for c in insp.get_columns("article_process_steps")}
    if not {"locked", "mode", "target_location_type"} <= cols:
        return
    op.execute(
        """
        UPDATE article_process_steps s
        SET locked = true, mode = 'customer'
        FROM orders o
        WHERE s.order_id = o.id
          AND s.step_type = 'movement'
          AND s.is_active = true
          AND s.locked = false
          AND s.target_location_type = 'user'
          AND EXISTS (
            SELECT 1 FROM sales sa
            WHERE sa.order_id = o.id AND sa.mode = 'shop' AND sa.is_active = true
          )
        """
    )


def downgrade() -> None:
    # Bewusst kein Rückbau: der alte Zustand (ungesperrter Shop-Versand) war der Fehler.
    pass
