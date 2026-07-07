"""Cleanup & Härtung (Juli 2026) – siehe docs/cleanup-2026-07.md.

1. **Bugfix Meldebestand (B1)**: ``orders.reason`` von VARCHAR(12) auf VARCHAR(20) –
   ``reason='replenishment'`` hat 13 Zeichen; jede Auto-Nachbestellung scheiterte mit
   einem Truncation-Fehler (Feature E war damit wirkungslos).
2. **Fehlende Indizes (B7)**: GIN auf ``instances.reservations`` (``has_key``-Hot-Paths:
   Unterdeckung/Verkaufs-Abgang/Abschluss) + B-Tree auf ``sales.customer_id``,
   ``orders.recurring_parent_id``, ``purchase_orders.supplier_id``.
3. **Alembic wieder Schema-SSOT (A12)**: die PR-#90-Spalten (Datenerfassung: Freigabe/
   Unterschrift + Bilderfassung) existierten nur im Runtime-Safety-Net – hier nachgezogen.
4. **Tote Spalten (A5/A6)**: ``orders.stripe_checkout_session_id`` und ``sales.fx_rate``
   wurden nie befüllt/gelesen (Checkout läuft über ``checkout_intents.stripe_session_id``;
   der Beleg-Snapshot nutzt ``base_amount_chf`` + ``fx_date``).
5. **Totes Notification-Modell (A7)**: Tabelle ``notifications`` wurde von keinem
   Router/Service je beschrieben oder gelesen (die Benachrichtigungs-Präferenzen am
   ``user_profiles`` sind davon unabhängig).
6. **F-Rollback-Reste (A3)**: Die per Notfall-Revert (#85) zurückgenommene Migration
   ``059_location_as_instance`` lief auf der Dev-DB; ihr Rückbau nie (die Revisions-ID
   059 wurde danach neu vergeben). Ihre Spalten auf ``articles``/``instances`` werden
   entfernt; F-Artefakt-Instanzen ohne Auftrag (``order_id IS NULL``) soft-deaktiviert.
   ``storage_locations`` behält seine eigenen (gleichnamigen) Spalten.

Alles idempotent (inspect-basiert) – ``create_all()``/Safety-Net bleiben das Fallback.

Revision ID: 060
Revises: 059
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '060'
down_revision = '059'
branch_labels = None
depends_on = None


def _insp():
    return inspect(op.get_bind())


def _cols(table: str) -> set[str]:
    return {c["name"] for c in _insp().get_columns(table)}


def _has_table(table: str) -> bool:
    return table in _insp().get_table_names()


# Datenerfassung (PR #90): Konfiguration am Schritt, Werte an der Erfassung.
_STEP_COLS = (
    ("require_signature", sa.Column("require_signature", sa.Boolean(), nullable=False, server_default="false")),
    ("signer_ids", sa.Column("signer_ids", JSONB(), nullable=True)),
    ("require_photo", sa.Column("require_photo", sa.Boolean(), nullable=False, server_default="false")),
    ("photo_instruction", sa.Column("photo_instruction", sa.String(300), nullable=True)),
)
_INSPECTION_COLS = (
    ("signature_url", sa.Column("signature_url", sa.String(300), nullable=True)),
    ("signed_by", sa.Column("signed_by", sa.BigInteger(), nullable=True)),
    ("signed_at", sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True)),
    ("photo_url", sa.Column("photo_url", sa.String(300), nullable=True)),
)

# F-Rollback-Reste (nur articles/instances – storage_locations bleibt unberührt).
_F_LEFTOVERS = {
    "articles": ("is_location", "max_load_kg"),
    "instances": ("is_location", "note", "latitude", "longitude",
                  "address_street", "address_zip", "address_city", "address_country"),
}


def upgrade() -> None:
    bind = op.get_bind()

    # 1) orders.reason verbreitern (12 → 20)
    if _has_table("orders") and "reason" in _cols("orders"):
        op.alter_column("orders", "reason", type_=sa.String(20), existing_type=sa.String(12))

    # 2) Indizes (idempotent)
    if _has_table("instances") and "reservations" in _cols("instances"):
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_instances_reservations "
            "ON instances USING gin (reservations jsonb_path_ops)"))
    for name, table, col in (
        ("ix_sales_customer_id", "sales", "customer_id"),
        ("ix_orders_recurring_parent_id", "orders", "recurring_parent_id"),
        ("ix_purchase_orders_supplier_id", "purchase_orders", "supplier_id"),
    ):
        if _has_table(table) and col in _cols(table):
            bind.execute(sa.text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({col})"))

    # 3) PR-#90-Spalten nachziehen (Alembic = SSOT)
    if _has_table("article_process_steps"):
        have = _cols("article_process_steps")
        for name, col in _STEP_COLS:
            if name not in have:
                op.add_column("article_process_steps", col)
    if _has_table("inspections"):
        have = _cols("inspections")
        for name, col in _INSPECTION_COLS:
            if name not in have:
                op.add_column("inspections", col)

    # 4) Tote Spalten entfernen
    if _has_table("orders") and "stripe_checkout_session_id" in _cols("orders"):
        op.drop_column("orders", "stripe_checkout_session_id")
    if _has_table("sales") and "fx_rate" in _cols("sales"):
        op.drop_column("sales", "fx_rate")

    # 5) Totes Notification-Modell
    if _has_table("notifications"):
        op.drop_table("notifications")

    # 6) F-Rollback-Reste: Artefakt-Instanzen deaktivieren, Spalten entfernen
    if _has_table("instances") and "order_id" in _cols("instances"):
        bind.execute(sa.text(
            "UPDATE instances SET is_active = false WHERE order_id IS NULL"))
    for table, cols in _F_LEFTOVERS.items():
        if not _has_table(table):
            continue
        have = _cols(table)
        for col in cols:
            if col in have:
                op.drop_column(table, col)


def downgrade() -> None:
    # Bereinigende Migration – die entfernten Spalten/Tabellen waren nie befüllt bzw.
    # gehörten zu einem zurückgenommenen Konzept. Kein sinnvoller Rückweg. No-op.
    pass
