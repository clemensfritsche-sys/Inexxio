import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

from .core.config import get_settings
from .core.database import Base, SessionLocal, engine
from .models import UserProfile
from .routers import (
    admin, ai, article_process, articles, attachments, auth, consent, contact, documents,
    document_files, erp, events, feedback, health, instances, legal, maintenance, object_refs,
    orders, passkey, sales, shop,
)

settings = get_settings()


def _bootstrap_admin() -> None:
    """Ensure initial_admin_email always has admin role; fall back to first user."""
    db = SessionLocal()
    try:
        if settings.initial_admin_email:
            candidate = db.query(UserProfile).filter(
                UserProfile.email == settings.initial_admin_email,
                UserProfile.is_active == True,
            ).first()
            if candidate:
                if candidate.role != "admin":
                    candidate.role = "admin"
                    db.commit()
                    print(f"INFO: Promoted {settings.initial_admin_email} to admin.", flush=True)
                return

        has_admin = db.query(UserProfile).filter(
            UserProfile.role == "admin", UserProfile.is_active == True
        ).first()
        if has_admin:
            return
        candidate = (
            db.query(UserProfile)
            .filter(UserProfile.is_active == True)
            .order_by(UserProfile.id)
            .first()
        )
        if candidate:
            candidate.role = "admin"
            db.commit()
    finally:
        db.close()


# Spalten, die nach dem Initial-Schema ergänzt wurden (Tabelle, Spalte, DDL-Typ).
# create_all() legt nur fehlende TABELLEN an – KEINE neuen Spalten auf bestehenden.
_COLUMN_SAFETY_NET = (
    ("company_settings", "google_maps_api_key", "VARCHAR(255)"),
    ("articles", "landed_unit_cost", "NUMERIC(12,4)"),
    ("orders", "article_id", "BIGINT"),
    ("orders", "quantity", "NUMERIC(14,3)"),
    ("orders", "desired_delivery_date", "DATE"),
    ("purchase_orders", "order_total", "NUMERIC(12,2)"),
    ("purchase_orders", "ordered_at", "TIMESTAMP WITH TIME ZONE"),
    ("article_process_steps", "shared_fields", "JSONB"),
    ("article_process_steps", "position", "INTEGER DEFAULT 1"),
    ("article_process_steps", "sample_percent", "INTEGER"),
    ("article_process_steps", "capture_fields", "JSONB"),
    ("article_process_steps", "target_location_type", "VARCHAR(20)"),
    ("article_process_steps", "target_location_id", "BIGINT"),
    ("inspections", "samples", "JSONB"),
    ("instances", "location_type", "VARCHAR(20)"),
    ("instances", "location_id", "BIGINT"),
    ("instances", "reserved_for_order_id", "BIGINT"),
    # Mengengenaue Reservierung ohne Instanz-Teilung
    ("instances", "reservations", "JSONB"),
    ("instances", "reserved_quantity", "NUMERIC(14,3) DEFAULT 0 NOT NULL"),
    # Standort-Verteilung einer Charge ohne Instanz-Teilung (analog reservations)
    ("instances", "locations", "JSONB"),
    # Unternehmen als nummerierter ERP-Datensatz (universelle Objektnummer)
    ("company_settings", "object_id", "BIGINT"),
    ("inspections", "escalated", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ("instances", "released_at", "TIMESTAMP WITH TIME ZONE"),
    ("article_process_steps", "resource_lines", "JSONB"),
    # Optionale Artikel-Stammdaten (dynamische Feldliste)
    ("articles", "material", "VARCHAR(255)"),
    ("articles", "cad_url", "VARCHAR(500)"),
    ("articles", "surface", "VARCHAR(255)"),
    ("articles", "supplier_article_number", "VARCHAR(255)"),
    ("articles", "min_order_qty", "NUMERIC(12,3)"),
    ("articles", "safety_stock", "NUMERIC(12,3)"),
    # Beschaffungsquelle an der Artikel-Spezifikation (vom purchase-Schritt geerbt)
    ("articles", "procurement_mode", "VARCHAR(20) DEFAULT 'supplier' NOT NULL"),
    ("articles", "default_supplier_id", "BIGINT"),
    ("articles", "default_webshop_url", "VARCHAR(500)"),
    # Durchlaufzeit (Freigabe → Abschluss)
    ("orders", "released_at", "TIMESTAMP WITH TIME ZONE"),
    ("orders", "completed_at", "TIMESTAMP WITH TIME ZONE"),
    # Mehr-Operationen-Routing: Fachzeilen an ihre Schritt-Definition binden
    ("purchase_orders", "step_id", "BIGINT"),
    ("inspections", "step_id", "BIGINT"),
    ("movements", "step_id", "BIGINT"),
    ("resource_usages", "step_id", "BIGINT"),
    # Alt-Bestand: früher automatisch gesäte Begleit-Bewegung (Rolle, keine Sperre).
    # Neue entstehen nicht mehr – physische Transporte sind Bereitstellungs-Unter-Aufträge
    # (Migration 080). ``locked`` ist die abgelöste Sperr-Spalte aus der Zeit davor.
    ("article_process_steps", "companion", "BOOLEAN DEFAULT FALSE NOT NULL"),
    # Bereitstellung (Unter-Auftrag) → welcher Schritt des Eltern auf sie wartet
    ("orders", "provisioning_step_id", "BIGINT"),
    # Ersetzen statt Versionierung: Nachfolger-Objektnummer (alt → neu)
    ("articles", "replaced_by_id", "BIGINT"),
    ("orders", "replaced_by_id", "BIGINT"),
    # Prozess am Artikel ODER am Auftrag (kein Prozess-Objekt mehr)
    ("article_process_steps", "order_id", "BIGINT"),
    ("instances", "subject_of_order_id", "BIGINT"),
    # qc_status in zwei Achsen aufgeteilt: quality (QC-Verdikt) + disposition (Verbleib)
    ("instances", "quality", "VARCHAR(20) DEFAULT 'pending' NOT NULL"),
    ("instances", "disposition", "VARCHAR(20) DEFAULT 'in_process' NOT NULL"),
    ("movements", "tracking_number", "VARCHAR(100)"),
    ("movements", "carrier", "VARCHAR(60)"),
    # Wiederkehrende Aufträge: Konfiguration direkt am Auftrag (kein eigenes Objekt mehr)
    ("orders", "recurrence_active", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ("orders", "recurrence_interval_days", "INTEGER"),
    ("orders", "recurrence_lead_time_days", "INTEGER DEFAULT 0 NOT NULL"),
    ("orders", "recurrence_anchor", "DATE"),
    ("orders", "recurring_parent_id", "BIGINT"),
    # Abweichung als Auftrag (Unter-Auftrag) + Abbruch-Folgeauftrag
    ("orders", "parent_order_id", "BIGINT"),
    ("orders", "abort_into_id", "BIGINT"),
    # Verkauf/Shop: Verkaufs-Ebene am Artikel (NICHT von der Freigabe eingefroren)
    ("articles", "sales_published", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ("articles", "sales_visibility", "VARCHAR(10) DEFAULT 'public' NOT NULL"),
    ("articles", "sales_content", "JSONB"),
    # Preis-Snapshot beim Kauf (Beleg unveränderlich)
    ("sales", "base_amount_chf", "NUMERIC(12,2)"),
    ("sales", "fx_rate", "NUMERIC(18,8)"),
    ("sales", "fx_date", "DATE"),
    ("sales", "tax_class", "VARCHAR(16)"),
    # Shop-Konfiguration
    ("company_settings", "shop_currencies", "JSONB"),
    ("company_settings", "shop_country_currency", "JSONB"),
    ("company_settings", "shop_default_currency", "VARCHAR(3) DEFAULT 'CHF' NOT NULL"),
    ("company_settings", "payments_provider", "VARCHAR(16)"),
    # Shop-Optimierung: Verfügbarkeits-Achse (Backorder-Policy), Pinning, Zonen-Faktoren
    ("articles", "sales_fulfillment", "VARCHAR(10) DEFAULT 'make' NOT NULL"),
    ("article_prices", "pinned", "JSONB"),
    ("company_settings", "pricing_zone_factors", "JSONB"),
    # Stripe-Integration: Customer-/Subscription-/PaymentIntent-Bezüge + Snapshot
    ("user_profiles", "stripe_customer_id", "VARCHAR(64)"),
    ("user_profiles", "last_sign_in_provider", "VARCHAR(40)"),
    ("disposals", "mode", "VARCHAR(10) DEFAULT 'scrap' NOT NULL"),
    ("orders", "stripe_subscription_id", "VARCHAR(80)"),
    ("sales", "stripe_payment_intent_id", "VARCHAR(80)"),
    ("sales", "stripe_snapshot", "JSONB"),
    # Shop-Phase 8: zwei Abo-Typen (Nutzungs-/Produktabo) + Warenkorb-Defer (CheckoutIntent)
    ("article_prices", "sub_type", "VARCHAR(10)"),
    ("orders", "recurrence_kind", "VARCHAR(10)"),
    # Unter-Auftrag-Grund: deviation | supply | return | replenishment – EIN Mechanismus.
    # VARCHAR(20): 'replenishment' (13 Zeichen) passte nicht in die frühere Breite 12.
    ("orders", "reason", "VARCHAR(20)"),
    # Dokument-Modul: der Schritt wird WÄHREND der Ausführung ausgestellt (done-Flag).
    ("documents", "done", "BOOLEAN DEFAULT FALSE NOT NULL"),
    # Dokument-Freigabe: 'issued' (Inhalt eingefroren) getrennt von 'done' (alle Parteien signiert).
    ("documents", "issued", "BOOLEAN DEFAULT FALSE NOT NULL"),
    # Dokument-Deklaration am Schritt: Freigabe-Parteien + Anerkennungs-Publikum + Sichtbarkeit.
    ("article_process_steps", "doc_signers", "JSONB"),
    ("article_process_steps", "sign_sequential", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ("article_process_steps", "doc_audience", "VARCHAR(16)"),
    ("article_process_steps", "doc_audience_roles", "JSONB"),
    ("article_process_steps", "doc_audience_person_ids", "JSONB"),
    ("article_process_steps", "doc_visibility", "VARCHAR(16) DEFAULT 'internal' NOT NULL"),
    # Datenerfassung: Freigabe/Unterschrift + Bilderfassung (Konfiguration am Schritt, Werte an der Erfassung).
    # Logistik/Versand (ADR 005): Gefahrgut-Flag, Betriebs-Geofence, Transport-Modus.
    # Die shipments-TABELLE legt create_all() an; hier nur nachgezogene Spalten.
    ("articles", "is_hazmat", "BOOLEAN DEFAULT FALSE NOT NULL"),
    # Phase-0-Fracht: Sendungsart + Last am Versand-Beleg (parcel|freight).
    ("shipments", "kind", "VARCHAR(12) DEFAULT 'parcel' NOT NULL"),
    ("shipments", "load", "JSONB"),
    ("shipments", "incoterm", "VARCHAR(8)"),
    ("shipments", "pickup_date", "VARCHAR(10)"),
)

# Bruchmengen (Migration 055): Mengen-Spalten müssen NUMERIC(14,3) sein, nicht INTEGER –
# sonst würde eine Bruchmenge (2.5 kg) beim Speichern abgeschnitten. ``create_all()`` ändert
# bestehende Spalten NICHT und die ADD-Safety-Net ergänzt nur fehlende – darum hier explizit
# per ALTER (idempotent: nur, wenn die Spalte noch ganzzahlig ist). Belt-and-suspenders zur
# Migration, falls Alembic übersprungen wurde/fehlschlug.
_NUMERIC_QTY_COLUMNS = (
    ("instances", "quantity"),
    ("instances", "reserved_quantity"),
    ("orders", "quantity"),
    ("order_lines", "quantity"),
    ("purchase_orders", "quantity"),
    ("sales", "quantity"),
)

# VARCHAR-Spalten, die nachträglich verbreitert wurden (Migration 060): idempotentes
# ALTER, falls Alembic übersprungen wurde. 'replenishment' (13 Zeichen) scheiterte an
# der ursprünglichen Breite 12 – jede Auto-Nachbestellung endete im Truncation-Fehler.
_VARCHAR_WIDEN_COLUMNS = (
    ("orders", "reason", 20),
)

# Obsolete Spalten, die aus dem Modell entfernt wurden. In Prod wird das Schema
# via create_all() (nicht Alembic) erzeugt – diese NOT-NULL/Alt-Spalten würden
# sonst INSERTs brechen (z. B. purchase_orders.transport_included). Idempotent.
_DROP_COLUMN_SAFETY_NET = (
    ("purchase_orders", "transport_cost"),
    ("purchase_orders", "transport_included"),
    ("purchase_orders", "other_costs"),
    ("purchase_orders", "rejection_reason"),
    ("purchase_orders", "object_id"),
    ("purchase_orders", "unit_price"),
    ("purchase_orders", "desired_delivery_date"),
    # Datenerfassung: Altformat `values` durch `samples` (je Stichprobe) ersetzt.
    ("inspections", "values"),
    # Vereinheitlichtes Bedarf-/Nachschub-Modell: Make-to-Order ist kein Sonderfall mehr.
    # WOHER die Stück kommen, leitet sich aus der Auftragsgestalt ab (kein Quellen-Override);
    # Nachschub ist ein Unter-Auftrag (reason='supply'), kein verketteter Produktionsauftrag.
    ("orders", "subject_source"),
    ("orders", "fulfilled_by_order_id"),
    # Dokument-Redesign: keine Typ-Trennung physisch/nicht-physisch mehr; das Dokument
    # wird im Auftrag verfasst (keine eigene Nummer/Version/Vorlage – Nummer = Instanz).
    ("articles", "physical"),
    ("article_process_steps", "document_content"),
    ("documents", "object_id"),
    ("documents", "version"),
    ("documents", "issued_at"),
    ("documents", "title"),
    ("documents", "replaced_by_id"),
    # Nie befüllte Stripe-/FX-Spalten (Cleanup 2026-07): der Checkout läuft über
    # CheckoutIntent.stripe_session_id; der Beleg-Snapshot nutzt base_amount_chf + fx_date.
    ("orders", "stripe_checkout_session_id"),
    ("sales", "fx_rate"),
    # Reste des per Notfall-Revert (#85) zurückgenommenen Konzepts «Standort als
    # Instanz» (F): die Migration 059_location_as_instance lief auf der Dev-DB, ihr
    # Rückbau nie.
    ("articles", "is_location"),
    ("articles", "max_load_kg"),
    ("instances", "is_location"),
    ("instances", "note"),
    ("instances", "latitude"),
    ("instances", "longitude"),
    ("instances", "address_street"),
    ("instances", "address_zip"),
    ("instances", "address_city"),
    ("instances", "address_country"),
)

# Indizes, die nach dem Initial-Schema ergänzt wurden. create_all() legt Indizes
# nur für NEUE Tabellen an – auf bestehenden Tabellen müssen sie idempotent
# nachgezogen werden (sonst Seq-Scans, z. B. auf dem wachsenden Audit-Log).
_INDEX_SAFETY_NET = (
    ("ix_audit_log_object_id", "audit_log", "object_id"),
    ("ix_audit_log_table_name", "audit_log", "table_name"),
    ("ix_instances_location_id", "instances", "location_id"),
    # Bestands-Aggregate (Verfügbarkeit/FIFO je Artikel) + Ressourcen-Schritt-Scans
    ("ix_instances_article_id", "instances", "article_id"),
    ("ix_aps_step_type", "article_process_steps", "step_type"),
    # Schritte am Artikel/Auftrag, Bestands-Subjekte je Auftrag
    ("ix_aps_order_id", "article_process_steps", "order_id"),
    ("ix_instances_subject_of_order", "instances", "subject_of_order_id"),
    ("ix_company_settings_object_id", "company_settings", "object_id"),
    # Heisse Filterspalten (Cleanup 2026-07): «Meine Bestellungen», Abo-Ketten,
    # Lieferanten-Feed – ohne Index Seq-Scans auf wachsenden Tabellen.
    ("ix_sales_customer_id", "sales", "customer_id"),
    ("ix_orders_recurring_parent_id", "orders", "recurring_parent_id"),
    ("ix_purchase_orders_supplier_id", "purchase_orders", "supplier_id"),
)

# Roh-Indizes mit speziellem Typ: GIN auf der Reservierungs-Map – die Hot-Path-Abfragen
# ``Instance.reservations.has_key(...)`` (Unterdeckung, Verkaufs-Abgang, Abschluss)
# wären sonst Full-Table-Scans über den gesamten Bestand.
_RAW_INDEX_SAFETY_NET = (
    "CREATE INDEX IF NOT EXISTS ix_instances_reservations "
    "ON instances USING gin (reservations jsonb_path_ops)",
    # Standort-Verteilung: «wer liegt hier?» (locations ? '<objektnr>') – Default-jsonb_ops
    # (nicht jsonb_path_ops), damit der has_key-Operator (?) den Index nutzt.
    "CREATE INDEX IF NOT EXISTS ix_instances_locations "
    "ON instances USING gin (locations)",
)

# Daten-Normalisierungen (idempotent), wenn keine Alembic-Migration lief.
_DATA_FIXES = (
    "UPDATE purchase_orders SET status='ordered' WHERE status IN ('approved','confirmed')",
)

# Dokument-Freigabe (Migration 066): ein bereits ausgestelltes Alt-Dokument (done) war
# ohne Freigabe-Parteien sofort freigegeben → issued nachziehen (idempotent).
_DOCUMENT_DATA_FIXES = (
    "UPDATE documents SET issued=true WHERE done=true AND issued=false",
)

# «serialization» ist kein eigener Prozessschritt mehr – die Bestands-Instanzen
# entstehen bei der Auftragsfreigabe. Bestehende Definitionen soft-löschen.
_STEP_DATA_FIXES = (
    "UPDATE article_process_steps SET is_active=false WHERE step_type='serialization'",
)

# Instanz-Normalisierung (idempotent): «am Lager» (in_stock) darf es nur geben, wenn
# der zugehörige Auftrag abgeschlossen ist. Altbestände, die bei der Anlage vorzeitig
# auf in_stock gesetzt wurden, auf «Im Prozess» (in_process/pending) zurücksetzen.
_INSTANCE_DATA_FIXES = (
    "UPDATE instances SET quality='pending', disposition='in_process', released_at=NULL "
    "WHERE quality='passed' AND disposition='in_stock' AND is_active=true "
    "AND order_id IN (SELECT id FROM orders WHERE status <> 'completed')",
)

# Verkaufs-Sichtbarkeit 'unlisted' wird nicht mehr unterstützt → auf 'private' normalisieren.
_ARTICLE_DATA_FIXES = (
    "UPDATE articles SET sales_visibility='private' WHERE sales_visibility='unlisted'",
)


def _ensure_columns() -> None:
    """Fehlende Spalten idempotent ergänzen, obsolete entfernen und Altdaten
    normalisieren, falls eine Migration nicht lief. create_all() ändert
    bestehende Tabellen NICHT."""
    try:
        with engine.connect() as conn:
            insp = inspect(engine)
            tables = set(insp.get_table_names())
            for table, col, ddl in _COLUMN_SAFETY_NET:
                if table not in tables:
                    continue
                if col not in {c["name"] for c in insp.get_columns(table)}:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {ddl}"
                    ))
            # Bruchmengen: ganzzahlige Mengen-Spalten auf NUMERIC(14,3) heben (idempotent).
            for table, col in _NUMERIC_QTY_COLUMNS:
                if table not in tables or col not in {c["name"] for c in insp.get_columns(table)}:
                    continue
                dtype = conn.execute(text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = :c"
                ), {"t": table, "c": col}).scalar()
                if dtype and dtype.lower() != "numeric":
                    conn.execute(text(
                        f"ALTER TABLE {table} ALTER COLUMN {col} "
                        f"TYPE NUMERIC(14,3) USING {col}::numeric(14,3)"
                    ))
            # Zu schmale VARCHAR-Spalten idempotent verbreitern (nur vergrössern).
            for table, col, width in _VARCHAR_WIDEN_COLUMNS:
                if table not in tables or col not in {c["name"] for c in insp.get_columns(table)}:
                    continue
                current = conn.execute(text(
                    "SELECT character_maximum_length FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = :c"
                ), {"t": table, "c": col}).scalar()
                if current is not None and current < width:
                    conn.execute(text(
                        f"ALTER TABLE {table} ALTER COLUMN {col} TYPE VARCHAR({width})"
                    ))
            for table, col in _DROP_COLUMN_SAFETY_NET:
                if table in tables:
                    conn.execute(text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {col}"))
            for index_name, table, col in _INDEX_SAFETY_NET:
                if table in tables and col in {c["name"] for c in insp.get_columns(table)}:
                    conn.execute(text(
                        f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({col})"
                    ))
            if "instances" in tables:
                for stmt in _RAW_INDEX_SAFETY_NET:
                    conn.execute(text(stmt))
            if "purchase_orders" in tables:
                for stmt in _DATA_FIXES:
                    conn.execute(text(stmt))
            if "documents" in tables:
                # Über information_schema auf DERSELBEN Verbindung prüfen (sieht die eben in
                # dieser Transaktion via ADD COLUMN ergänzte Spalte – anders als der Vor-Loop-``insp``).
                doc_cols = {r[0] for r in conn.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='documents'"))}
                if {"issued", "done"}.issubset(doc_cols):
                    for stmt in _DOCUMENT_DATA_FIXES:
                        conn.execute(text(stmt))
            if "article_process_steps" in tables:
                for stmt in _STEP_DATA_FIXES:
                    conn.execute(text(stmt))
            if "instances" in tables and "orders" in tables:
                for stmt in _INSTANCE_DATA_FIXES:
                    conn.execute(text(stmt))
            if "articles" in tables:
                for stmt in _ARTICLE_DATA_FIXES:
                    conn.execute(text(stmt))
            conn.commit()
    except Exception as e:
        print(f"WARNING: _ensure_columns() failed: {e}", flush=True)


def _ensure_object_id_sequence() -> None:
    """Objektnummern-Sequence anlegen und (einmalig) an Altdaten ausrichten.

    Idempotent und rewind-sicher: hebt die Sequence höchstens auf den höchsten
    bereits vergebenen Stand – nie darunter. Auf einer leeren DB bleibt der Start
    bei OBJ_ID_START. Migration ``021`` macht dasselbe; diese Funktion ist das
    Fallback, falls die Migration übersprungen wurde/fehlschlug."""
    from .services.objects import OBJ_ID_START, OBJECT_ID_SEQUENCE, current_max_object_id
    db = SessionLocal()
    try:
        db.execute(text(
            f"CREATE SEQUENCE IF NOT EXISTS {OBJECT_ID_SEQUENCE} AS BIGINT "
            f"START WITH {OBJ_ID_START} MINVALUE {OBJ_ID_START}"
        ))
        db.commit()
        max_id = current_max_object_id(db)
        if max_id >= OBJ_ID_START:
            db.execute(text(
                f"SELECT setval('{OBJECT_ID_SEQUENCE}', "
                f"GREATEST((SELECT last_value FROM {OBJECT_ID_SEQUENCE}), :m), true)"
            ), {"m": max_id})
            db.commit()
    except Exception as e:
        print(f"WARNING: _ensure_object_id_sequence() failed: {e}", flush=True)
    finally:
        db.close()


# Eigener Advisory-Lock für die (potenziell destruktive) Registry-Reparatur,
# damit parallele Worker/Instanzen sie serialisieren (kein Drop-Recreate-Race).
_REGISTRY_LOCK_KEY = 778_899_002


def _ensure_object_registry_shape() -> None:
    """Die Objekt-Registry ``objects`` muss dem aktuellen ``ObjectRef``-Modell
    entsprechen (``object_id`` als Schlüssel, ``object_type``, ``created_at``).

    Auf gewachsenen Datenbanken existiert evtl. noch eine **veraltete** ``objects``-
    Tabelle aus einem früheren Modell (Spalte ``id`` statt ``object_id``).
    ``create_all()`` ändert bestehende Tabellen nicht, daher schlägt JEDE
    Objektanlage mit «column object_id … does not exist» fehl. Hier wird die
    veraltete Tabelle verworfen und korrekt neu angelegt – die Registry ist eine
    reine Ableitung der Fachtabellen (``_backfill_object_registry`` füllt sie neu).
    Idempotent und über einen Advisory-Lock gegen Nebenläufigkeit abgesichert."""
    db = SessionLocal()
    try:
        # Serialisiert diese Reparatur über alle Worker/Instanzen (eine Transaktion).
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _REGISTRY_LOCK_KEY})
        exists = db.execute(text("SELECT to_regclass('public.objects')")).scalar() is not None
        if exists:
            has_object_id = db.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'objects' AND column_name = 'object_id'"
            )).first() is not None
            if not has_object_id:
                db.execute(text("DROP TABLE objects CASCADE"))
        db.execute(text(
            "CREATE TABLE IF NOT EXISTS objects ("
            "object_id BIGINT PRIMARY KEY, "
            "object_type VARCHAR(30) NOT NULL, "
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now())"
        ))
        db.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_objects_object_type ON objects (object_type)"
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"WARNING: _ensure_object_registry_shape() failed: {e}", flush=True)
    finally:
        db.close()


def _backfill_object_registry() -> None:
    """Zentrale Objekt-Registry mit allen vorhandenen Objektnummern auffüllen
    (Altdaten + ohne Typ vergebene). Idempotent."""
    from .services.objects import backfill_registry, ensure_foreign_keys
    db = SessionLocal()
    try:
        backfill_registry(db)
        db.commit()
        ensure_foreign_keys(db)   # FK-Integrität der Quer-Referenzen (best-effort)
    except Exception as e:
        db.rollback()
        print(f"WARNING: _backfill_object_registry() failed: {e}", flush=True)
    finally:
        db.close()


def _ensure_company_object_id() -> None:
    """Das Unternehmen (Singleton) als nummerierten ERP-Datensatz sicherstellen:
    fehlt die Objektnummer, wird sie hier EINMALIG beim Start vergeben – deploy-
    deterministisch und unabhängig davon, ob jemand die Admin-Einstellungen öffnet
    (der öffentliche Settings-Endpoint vergibt bewusst keine Nummern)."""
    from .services.admin import get_or_create_settings
    db = SessionLocal()
    try:
        get_or_create_settings(db)   # legt Settings an + vergibt object_id (committet)
    except Exception as e:
        db.rollback()
        print(f"WARNING: _ensure_company_object_id() failed: {e}", flush=True)
    finally:
        db.close()


def _ensure_documents_shape() -> None:
    """Die ``documents``-Tabelle exakt an das aktuelle Modell angleichen – UNABHÄNGIG von
    Alembic. ``create_all()`` legt nur fehlende TABELLEN an, nicht fehlende Spalten; ein
    inkonsistenter Alt-Stand (z. B. ohne ``order_id``) liesse die Tabelle sonst kaputt.
    Fehlt eine erwartete Spalte, wird die Tabelle idempotent neu aufgebaut (Inhalt =
    Wegwerf-Testdaten des frisch eingeführten Moduls). Greift auch, wenn eine Migration
    nicht durchlief (start.sh startet uvicorn dann trotzdem)."""
    from sqlalchemy import inspect
    from .models import Document
    try:
        insp = inspect(engine)
        if "documents" not in insp.get_table_names():
            Document.__table__.create(bind=engine, checkfirst=True)
            return
        have = {c["name"] for c in insp.get_columns("documents")}
        # NUR ein fehlender STRUKTUR-Kern rechtfertigt den (destruktiven) Neuaufbau – rein
        # additive Flags (``done``/``issued``) ergänzt danach ``_ensure_columns`` non-destruktiv.
        # Wichtig: ``documents`` trägt die ausgestellten **Rechtsdokumente** (AGB/Datenschutz),
        # die ``legal.resolve`` referenziert – ein Neuaufbau wegen einer neuen additiven Spalte
        # (nach einem Modell-Zuwachs, bevor Alembic lief) würde sie unwiederbringlich löschen.
        structural = {"id", "order_id", "step_id", "article_id", "content",
                      "created_by", "created_at", "updated_at", "is_active"}
        if structural.issubset(have):
            return  # Struktur passt – additive Spalten übernimmt _ensure_columns
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS documents CASCADE"))
        Document.__table__.create(bind=engine, checkfirst=True)
        print("INFO: documents-Tabelle neu aufgebaut (Schema an das Modell angeglichen).", flush=True)
    except Exception as e:
        print(f"WARNING: _ensure_documents_shape() failed: {e}", flush=True)


def _ensure_attachments_shape() -> None:
    """Die ``attachments``-Tabelle exakt ans Modell angleichen (analog documents). Eine früher
    per ``create_all()`` – oder mit übersprungener Migration – angelegte Alt-Tabelle konnte ohne
    ``token`` entstehen; jeder Bild-Upload (Verkauf/Datenerfassung) scheiterte dann mit
    «column token does not exist». Fehlt eine erwartete Spalte, wird die Tabelle idempotent neu
    aufgebaut (Inhalt = verworfene Bild-Uploads, keine Rückwärtskompatibilität nötig)."""
    from sqlalchemy import inspect
    from .models import Attachment
    try:
        insp = inspect(engine)
        if "attachments" not in insp.get_table_names():
            Attachment.__table__.create(bind=engine, checkfirst=True)
            return
        have = {c["name"] for c in insp.get_columns("attachments")}
        expected = set(Attachment.__table__.columns.keys())
        if expected.issubset(have):
            return  # Schema passt – nichts zu tun
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS attachments CASCADE"))
        Attachment.__table__.create(bind=engine, checkfirst=True)
        print("INFO: attachments-Tabelle neu aufgebaut (Schema an das Modell angeglichen).", flush=True)
    except Exception as e:
        print(f"WARNING: _ensure_attachments_shape() failed: {e}", flush=True)




# Advisory-Lock-Schlüssel: Schema-/Daten-Fixups laufen genau EINMAL – auch bei
# mehreren uvicorn-Workern oder mehreren Cloud-Run-Instanzen (Lock liegt in der DB).
_STARTUP_LOCK_KEY = 778_899_001


def _run_startup_fixups_once() -> None:
    """Alle Startup-Mutationen (Schema-Nachzug, Registry, Prozess-Backfill, Pflicht-
    Bewegungen, Wiederkehr) unter einem DB-Advisory-Lock ausführen, damit sie sich
    bei parallelem Start nicht in die Quere kommen (verhindert doppelte Prozesse/
    Bewegungen und Lock-Konflikte → keine sporadischen 5xx kurz nach dem Deploy)."""
    db = SessionLocal()
    acquired = False
    try:
        acquired = bool(db.execute(text("SELECT pg_try_advisory_lock(:k)"),
                                   {"k": _STARTUP_LOCK_KEY}).scalar())
        if not acquired:
            print("INFO: Startup-Fixups laufen bereits (anderer Worker/Instanz) – übersprungen.", flush=True)
            return
        _ensure_documents_shape()     # documents-Tabelle exakt ans Modell angleichen (Reparatur)
        _ensure_attachments_shape()   # attachments-Tabelle reparieren (fehlendes 'token' → Upload-Fehler)
        _ensure_columns()
        _ensure_object_id_sequence()
        _backfill_object_registry()
        _ensure_company_object_id()   # Firma = nummerierter ERP-Datensatz
    except Exception as e:
        print(f"WARNING: _run_startup_fixups_once() failed: {e}", flush=True)
    finally:
        if acquired:
            try:
                db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _STARTUP_LOCK_KEY})
                db.commit()
            except Exception:
                pass
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Safety-Net: fehlende Tabellen idempotent anlegen, falls eine Migration
        # übersprungen wurde oder fehlschlug. create_all() ändert bestehende
        # Tabellen NICHT – Schema-Änderungen bleiben Sache von Alembic.
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"WARNING: create_all() failed: {e}", flush=True)
    # Den universellen Nummernkreis-Generator IMMER sicherstellen – NICHT hinter
    # dem Advisory-Lock. Sonst startet ein Worker, der den Lock nicht erhält, ohne
    # ``object_id_seq`` und JEDE Objektanlage (Artikel/Auftrag/…) endet in einem
    # 500 (``nextval`` auf fehlende Sequence). Idempotent & nebenläufigkeitssicher.
    _ensure_object_id_sequence()
    # Objekt-Registry auf die aktuelle Form bringen (veraltete `objects`-Tabelle
    # ohne `object_id` → Neuanlage). Ebenfalls IMMER, race-sicher per Advisory-Lock.
    _ensure_object_registry_shape()
    # Übrige Schema-/Daten-Fixups genau einmal (Advisory-Lock, cross-worker/-instanz).
    _run_startup_fixups_once()
    try:
        _bootstrap_admin()
    except Exception as e:
        print(f"WARNING: _bootstrap_admin() failed: {e}", flush=True)
    # KI-Identität seeden (ADR 004): die KI ist ein echter Principal (role='ai') mit
    # eigener Objektnummer – Audit/Events zeigen «angelegt von User KI». Idempotent.
    try:
        from .services.ai.identity import ensure_ai_user
        db = SessionLocal()
        try:
            ensure_ai_user(db)
        finally:
            db.close()
    except Exception as e:
        print(f"WARNING: ensure_ai_user() failed: {e}", flush=True)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Letzte Auffanglinie für unbehandelte Fehler.

    Ohne diesen Handler liefert Starlette einen **text/plain** «Internal Server
    Error» ohne jede Diagnose – der Client kann ihn nicht als JSON lesen und zeigt
    nur «Server nicht erreichbar». Hier wird der vollständige Traceback in die
    Logs geschrieben (Cloud Run) und eine **strukturierte JSON-Antwort** geliefert.
    Ausserhalb der Produktion enthält ``detail`` die echte Ursache (Diagnose);
    HTTPException wird davon nicht erfasst (eigener Handler)."""
    tb = traceback.format_exc()
    print(f"ERROR: Unhandled exception on {request.method} {request.url.path}\n{tb}", flush=True)
    expose = settings.debug or settings.app_env.lower() != "production"
    detail = f"{type(exc).__name__}: {exc}" if expose else "Interner Serverfehler"
    return JSONResponse(status_code=500, content={"detail": detail, "code": "INTERNAL_ERROR"})

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(passkey.router)
app.include_router(consent.router)
app.include_router(contact.router)
app.include_router(admin.router)
app.include_router(erp.router)
app.include_router(articles.router)
app.include_router(article_process.router)
app.include_router(orders.router)
app.include_router(instances.router)
app.include_router(object_refs.router)
app.include_router(sales.router)
app.include_router(shop.router)
app.include_router(events.router)
app.include_router(documents.router)
app.include_router(document_files.router)
app.include_router(attachments.router)
app.include_router(legal.router)
app.include_router(maintenance.router)
app.include_router(ai.router)
app.include_router(feedback.router)


@app.get("/")
async def root():
    return {
        "name": "Inexxio ECS API",
        "version": settings.app_version,
        "docs": "/api/docs",
    }
