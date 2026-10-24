"""Adress-basierte Versand-Ableitung (Geofence entfernt) + Ausschuss-Standort bereinigen.

- Der Betriebs-Geofence (``company_settings.site_latitude/longitude/radius_m``, Migration
  071) wird verworfen: der Versand wird jetzt rein **adress-basiert** abgeleitet
  (Rolle Kunde/Lieferant ODER unterschiedliche Adresse A→B; Ziel ohne Adresse = intern).
- **Verschrottete Instanzen sind standortlos**: ein bereits verschrottetes Teil, das noch
  einen Alt-Standort trägt, wird bereinigt (kein «liegt hier» mehr auf einem Lagerplatz).

Revision ID: 072
Revises: 071
Create Date: 2026-07-09
"""
from alembic import op
from sqlalchemy import inspect

revision = '072'
down_revision = '071'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    tables = insp.get_table_names()

    if "company_settings" in tables:
        cols = {c["name"] for c in insp.get_columns("company_settings")}
        for name in ("site_latitude", "site_longitude", "site_radius_m"):
            if name in cols:
                op.drop_column("company_settings", name)

    # Verschrottete Instanzen standortlos machen (Alt-Datensätze bereinigen).
    if "instances" in tables:
        cols = {c["name"] for c in insp.get_columns("instances")}
        sets = ["location_type = NULL", "location_id = NULL"]
        if "locations" in cols:
            sets.append("locations = NULL")
        op.execute(
            "UPDATE instances SET " + ", ".join(sets)
            + " WHERE disposition = 'scrapped'"
              " AND (location_type IS NOT NULL OR location_id IS NOT NULL"
            + (" OR locations IS NOT NULL" if "locations" in cols else "") + ")"
        )


def downgrade() -> None:
    # Geofence-Spalten werden bewusst nicht wiederhergestellt (Feature entfernt).
    pass
