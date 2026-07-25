"""Standort-Modell: **Lagerplatz entfällt**, der «Ort» (place) kommt an die Instanz.

Ein Standort ist ein **Halter**. Vier Arten – drei mit Objektnummer, eine ohne:

    place    → Adresse/GPS INLINE (``instances.place``, keine Objektnummer)  ← neu
    user     → UserProfile
    instance → andere Instanz (Behälter/Palette/Maschine/LKW)  ← ersetzt den Lagerplatz
    company  → das Unternehmen selbst (Betriebsadresse)        ← neu als Bewegungsziel

Ein **benannter Platz** (Regal A, Wareneingang, LKW 1) ist damit eine ganz normale Instanz,
die andere Instanzen hält – kein eigener Datensatztyp mehr. Der frühere `lagerplatz` wird
vollständig aufgelöst: jede Referenz wird in einen **Ort** überführt (Adresse + GPS des
Lagerplatzes werden inline übernommen), danach fällt die Tabelle weg.

**Bewusst NICHT rückwärtskompatibel** (Vorgabe): es bleibt keine Altlast stehen.

Weitere Aufräumarbeiten in einem Zug:
* ``articles.fixed_location_*`` (der Karten-Picker am Artikel) wird **endgültig** entfernt –
  ein Artikel ist eine Spezifikation, kein Ort. Standorte hängen an Instanzen.
* ``company_settings.default_receiving_location_id`` entfällt – der Wareneingang ist ab jetzt
  das **Unternehmen selbst** (dessen Adresse in den Firmen-Stammdaten steht).
* ``purchase_orders.receiving_location_id`` (tote Alt-Spalte) entfällt.

Chargen-Verteilung: ``instances.locations`` ist nach **Objektnummer** geschlüsselt. Ein Ort
hat keine – eine über mehrere Lagerplätze verteilte Charge wird darum auf ihren grössten
Teilstandort zusammengeführt (der Skalar, der zuvor in einen Ort überführt wurde).

Revision ID: 077
Revises: 076
Create Date: 2026-07-19
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '077'
down_revision = '076'
branch_labels = None
depends_on = None


def _tables(insp) -> set[str]:
    return set(insp.get_table_names())


def _cols(insp, table: str) -> set[str]:
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    insp = inspect(op.get_bind())
    tables = _tables(insp)

    # ── 1) Neue Standort-Träger ───────────────────────────────────────────────────
    if "instances" in tables and "place" not in _cols(insp, "instances"):
        op.add_column("instances", sa.Column("place", JSONB, nullable=True))
    if "article_process_steps" in tables and "target_place" not in _cols(insp, "article_process_steps"):
        op.add_column("article_process_steps", sa.Column("target_place", JSONB, nullable=True))

    # ── 2) Lagerplatz-Referenzen in Orte überführen ───────────────────────────────
    if "instances" in tables and "storage_locations" in tables:
        # Adresse + GPS des Lagerplatzes inline auf die Instanz übernehmen.
        op.execute("""
            UPDATE instances i
               SET location_type = 'place',
                   location_id   = NULL,
                   place = jsonb_strip_nulls(jsonb_build_object(
                       'name',    NULLIF(sl.name, ''),
                       'street1', NULLIF(sl.address_street, ''),
                       'zip',     NULLIF(sl.address_zip, ''),
                       'city',    NULLIF(sl.address_city, ''),
                       'country', COALESCE(NULLIF(sl.address_country, ''), 'CH'),
                       'lat',     sl.latitude,
                       'lng',     sl.longitude))
              FROM storage_locations sl
             WHERE i.location_type = 'lagerplatz'
               AND sl.object_id = i.location_id
        """)
        # Verwaiste Zeiger (Lagerplatz existiert nicht mehr) → standortlos.
        op.execute("""
            UPDATE instances
               SET location_type = NULL, location_id = NULL
             WHERE location_type = 'lagerplatz'
        """)
        # Verteilte Chargen mit Lagerplatz-Anteilen auf den (nun als Ort geführten)
        # Hauptstandort zusammenführen – ein Ort hält immer die ganze Menge.
        op.execute("""
            UPDATE instances
               SET locations = NULL
             WHERE locations IS NOT NULL
               AND EXISTS (SELECT 1 FROM jsonb_each(locations) AS e(k, v)
                            WHERE v ->> 't' = 'lagerplatz')
        """)

    # Vorgabe-Ziel am Bewegungs-Schritt ebenso überführen.
    if "article_process_steps" in tables and "storage_locations" in tables:
        op.execute("""
            UPDATE article_process_steps s
               SET target_location_type = 'place',
                   target_location_id   = NULL,
                   target_place = jsonb_strip_nulls(jsonb_build_object(
                       'name',    NULLIF(sl.name, ''),
                       'street1', NULLIF(sl.address_street, ''),
                       'zip',     NULLIF(sl.address_zip, ''),
                       'city',    NULLIF(sl.address_city, ''),
                       'country', COALESCE(NULLIF(sl.address_country, ''), 'CH'),
                       'lat',     sl.latitude,
                       'lng',     sl.longitude))
              FROM storage_locations sl
             WHERE s.target_location_type = 'lagerplatz'
               AND sl.object_id = s.target_location_id
        """)
        op.execute("""
            UPDATE article_process_steps
               SET target_location_type = NULL, target_location_id = NULL
             WHERE target_location_type = 'lagerplatz'
        """)

    # ── 3) Karten-Picker am Artikel endgültig entfernen ───────────────────────────
    if "articles" in tables:
        have = _cols(insp, "articles")
        for col in ("fixed_location_lat", "fixed_location_lng", "fixed_location_street",
                    "fixed_location_zip", "fixed_location_city", "fixed_location_country"):
            if col in have:
                op.drop_column("articles", col)

    # ── 4) Wareneingang = das Unternehmen selbst ──────────────────────────────────
    if "company_settings" in tables and "default_receiving_location_id" in _cols(insp, "company_settings"):
        op.drop_column("company_settings", "default_receiving_location_id")
    if "purchase_orders" in tables and "receiving_location_id" in _cols(insp, "purchase_orders"):
        op.drop_column("purchase_orders", "receiving_location_id")

    # ── 5) Lagerplatz-Datensatztyp fällt weg ──────────────────────────────────────
    if "storage_locations" in tables:
        op.drop_table("storage_locations")


def downgrade() -> None:
    """Nur strukturell (die aufgelösten Lagerplätze sind nicht rekonstruierbar)."""
    insp = inspect(op.get_bind())
    tables = _tables(insp)

    if "storage_locations" not in tables:
        op.create_table(
            "storage_locations",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("object_id", sa.BigInteger, unique=True, index=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("code", sa.String(100)),
            sa.Column("location_type", sa.String(30)),
            sa.Column("note", sa.String(500)),
            sa.Column("max_load_kg", sa.Numeric(12, 3)),
            sa.Column("width_mm", sa.Integer), sa.Column("depth_mm", sa.Integer),
            sa.Column("height_mm", sa.Integer),
            sa.Column("is_dry", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("is_tempered", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("is_hazmat", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("is_blocked", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("latitude", sa.Numeric(9, 6)), sa.Column("longitude", sa.Numeric(9, 6)),
            sa.Column("address_street", sa.String(255)), sa.Column("address_zip", sa.String(20)),
            sa.Column("address_city", sa.String(100)), sa.Column("address_country", sa.String(100)),
            sa.Column("replaced_by_id", sa.BigInteger, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        )
    if "purchase_orders" in tables and "receiving_location_id" not in _cols(insp, "purchase_orders"):
        op.add_column("purchase_orders", sa.Column("receiving_location_id", sa.BigInteger))
    if "company_settings" in tables and "default_receiving_location_id" not in _cols(insp, "company_settings"):
        op.add_column("company_settings", sa.Column("default_receiving_location_id", sa.BigInteger))
    if "articles" in tables:
        have = _cols(insp, "articles")
        for col, typ in (("fixed_location_lat", sa.Numeric(9, 6)), ("fixed_location_lng", sa.Numeric(9, 6)),
                         ("fixed_location_street", sa.String(255)), ("fixed_location_zip", sa.String(20)),
                         ("fixed_location_city", sa.String(100)), ("fixed_location_country", sa.String(100))):
            if col not in have:
                op.add_column("articles", sa.Column(col, typ, nullable=True))
    if "article_process_steps" in tables and "target_place" in _cols(insp, "article_process_steps"):
        op.drop_column("article_process_steps", "target_place")
    if "instances" in tables and "place" in _cols(insp, "instances"):
        op.drop_column("instances", "place")
