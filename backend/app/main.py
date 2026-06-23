from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import inspect, text

from .core.config import get_settings
from .core.database import Base, SessionLocal, engine
from .models import UserProfile
from .routers import (
    admin, article_process, articles, auth, claims, contact, erp, events, health,
    instances, orders, processes, recurring, storage_locations,
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
    ("company_settings", "default_receiving_location_id", "BIGINT"),
    ("articles", "landed_unit_cost", "NUMERIC(12,4)"),
    ("orders", "article_id", "BIGINT"),
    ("orders", "quantity", "INTEGER"),
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
    ("storage_locations", "note", "VARCHAR(500)"),
    ("company_settings", "article_names", "JSONB"),
    ("inspections", "escalated", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ("purchase_orders", "receiving_location_id", "BIGINT"),
    ("instances", "released_at", "TIMESTAMP WITH TIME ZONE"),
    ("article_process_steps", "resource_lines", "JSONB"),
    # Optionale Artikel-Stammdaten (dynamische Feldliste)
    ("articles", "material", "VARCHAR(255)"),
    ("articles", "cad_url", "VARCHAR(500)"),
    ("articles", "surface", "VARCHAR(255)"),
    ("articles", "supplier_article_number", "VARCHAR(255)"),
    ("articles", "min_order_qty", "NUMERIC(12,3)"),
    ("articles", "safety_stock", "NUMERIC(12,3)"),
    # Durchlaufzeit (Freigabe → Abschluss)
    ("orders", "released_at", "TIMESTAMP WITH TIME ZONE"),
    ("orders", "completed_at", "TIMESTAMP WITH TIME ZONE"),
    # Mehr-Operationen-Routing: Fachzeilen an ihre Schritt-Definition binden
    ("purchase_orders", "step_id", "BIGINT"),
    ("inspections", "step_id", "BIGINT"),
    ("movements", "step_id", "BIGINT"),
    ("resource_usages", "step_id", "BIGINT"),
    # Pflicht-Bewegung rund um Beschaffung (System, nicht löschbar)
    ("article_process_steps", "locked", "BOOLEAN DEFAULT FALSE NOT NULL"),
    # Ersetzen statt Versionierung: Nachfolger-Objektnummer (alt → neu)
    ("articles", "replaced_by_id", "BIGINT"),
    ("orders", "replaced_by_id", "BIGINT"),
    ("storage_locations", "replaced_by_id", "BIGINT"),
    # Mehrere Prozesse je Artikel + Auftrags-Subjekt/Prozesswahl + Sales-Tracking
    ("article_process_steps", "process_id", "BIGINT"),
    ("orders", "process_id", "BIGINT"),
    ("orders", "subject_instance_id", "BIGINT"),
    ("instances", "subject_of_order_id", "BIGINT"),
    ("movements", "tracking_number", "VARCHAR(100)"),
    ("movements", "carrier", "VARCHAR(60)"),
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
)

# Indizes, die nach dem Initial-Schema ergänzt wurden. create_all() legt Indizes
# nur für NEUE Tabellen an – auf bestehenden Tabellen müssen sie idempotent
# nachgezogen werden (sonst Seq-Scans, z. B. auf dem wachsenden Audit-Log).
_INDEX_SAFETY_NET = (
    ("ix_audit_log_object_id", "audit_log", "object_id"),
    ("ix_audit_log_table_name", "audit_log", "table_name"),
    ("ix_claims_order_object_id", "claims", "order_object_id"),
    ("ix_instances_location_id", "instances", "location_id"),
    # Bestands-Aggregate (Verfügbarkeit/FIFO je Artikel) + Ressourcen-Schritt-Scans
    ("ix_instances_article_id", "instances", "article_id"),
    ("ix_aps_step_type", "article_process_steps", "step_type"),
    # Mehr-Prozess-Modell: Schritte je Prozess, Bestands-Subjekte je Auftrag
    ("ix_aps_process_id", "article_process_steps", "process_id"),
    ("ix_instances_subject_of_order", "instances", "subject_of_order_id"),
)

# Daten-Normalisierungen (idempotent), wenn keine Alembic-Migration lief.
_DATA_FIXES = (
    "UPDATE purchase_orders SET status='ordered' WHERE status IN ('approved','confirmed')",
)

# «serialization» ist kein eigener Prozessschritt mehr – die Bestands-Instanzen
# entstehen bei der Auftragsfreigabe. Bestehende Definitionen soft-löschen.
_STEP_DATA_FIXES = (
    "UPDATE article_process_steps SET is_active=false WHERE step_type='serialization'",
)

# Instanz-Normalisierung (idempotent): «Freigegeben» (passed) darf es nur geben,
# wenn der zugehörige Auftrag abgeschlossen ist. Altbestände, die bei der Anlage
# vorzeitig auf passed gesetzt wurden, auf «Im Prozess» (pending) zurücksetzen.
_INSTANCE_DATA_FIXES = (
    "UPDATE instances SET qc_status='pending', released_at=NULL "
    "WHERE qc_status='passed' AND is_active=true "
    "AND order_id IN (SELECT id FROM orders WHERE status <> 'completed')",
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
            for table, col in _DROP_COLUMN_SAFETY_NET:
                if table in tables:
                    conn.execute(text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {col}"))
            for index_name, table, col in _INDEX_SAFETY_NET:
                if table in tables and col in {c["name"] for c in insp.get_columns(table)}:
                    conn.execute(text(
                        f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({col})"
                    ))
            if "purchase_orders" in tables:
                for stmt in _DATA_FIXES:
                    conn.execute(text(stmt))
            if "article_process_steps" in tables:
                for stmt in _STEP_DATA_FIXES:
                    conn.execute(text(stmt))
            if "instances" in tables and "orders" in tables:
                for stmt in _INSTANCE_DATA_FIXES:
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


def _backfill_processes() -> None:
    """Auf das Mehr-Prozess-Modell migrieren (idempotent).

    Bisher hingen die Schritte direkt am Artikel (ein impliziter Prozess). Hier wird
    je Artikel mit «losen» Schritten ein Default-Prozess «Entstehung» (Quelle
    ``produce``) angelegt, die Schritte werden ihm zugeordnet und die bestehenden
    Aufträge des Artikels darauf gesetzt. ``article_id`` der Schritte wird nullable
    (Standardprozess-Schritte haben keinen Artikel)."""
    from .models import Process
    db = SessionLocal()
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        if "article_process_steps" not in tables or "processes" not in tables:
            return
        # Standardprozess-Schritte haben keinen Artikel → NOT NULL lösen (idempotent).
        try:
            db.execute(text("ALTER TABLE article_process_steps ALTER COLUMN article_id DROP NOT NULL"))
            db.commit()
        except Exception:
            db.rollback()
        rows = db.execute(text(
            "SELECT DISTINCT article_id FROM article_process_steps "
            "WHERE process_id IS NULL AND article_id IS NOT NULL AND is_active = true"
        )).fetchall()
        for (aid,) in rows:
            proc = Process(article_id=aid, name="Entstehung", source="produce",
                           is_standard=False, status="released", position=1)
            db.add(proc)
            db.flush()
            db.execute(text(
                "UPDATE article_process_steps SET process_id = :pid "
                "WHERE article_id = :aid AND process_id IS NULL"
            ), {"pid": proc.id, "aid": aid})
            db.execute(text(
                "UPDATE orders SET process_id = :pid WHERE article_id = :aid AND process_id IS NULL"
            ), {"pid": proc.id, "aid": aid})
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"WARNING: _backfill_processes() failed: {e}", flush=True)
    finally:
        db.close()


def _sync_locked_movements_bootstrap() -> None:
    """Pflicht-Bewegungen rund um Beschaffungsschritte herstellen – jetzt **je
    Prozess** (Idempotent; nur über Prozesse mit Beschaffungs-/Bewegungsschritten)."""
    from .models import ArticleProcessStep, Process
    from .services.process_steps import sync_locked_movements
    db = SessionLocal()
    try:
        rows = (
            db.query(ArticleProcessStep.process_id)
            .filter(ArticleProcessStep.is_active == True,
                    ArticleProcessStep.process_id.isnot(None),
                    ArticleProcessStep.step_type.in_(("purchase", "movement")))
            .distinct()
            .all()
        )
        active = {pid for (pid,) in db.query(Process.id).filter(Process.is_active == True).all()}
        for (pid,) in rows:
            if pid in active:
                sync_locked_movements(db, pid)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"WARNING: _sync_locked_movements_bootstrap() failed: {e}", flush=True)
    finally:
        db.close()


def _spawn_recurring_bootstrap() -> None:
    """Fällige wiederkehrende Vorgänge beim Start zu Aufträgen machen (best-effort)."""
    from .services.recurring import spawn_due
    db = SessionLocal()
    try:
        spawn_due(db)
    except Exception as e:
        db.rollback()
        print(f"WARNING: _spawn_recurring_bootstrap() failed: {e}", flush=True)
    finally:
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
    _ensure_columns()
    _ensure_object_id_sequence()
    _backfill_object_registry()
    _backfill_processes()              # Mehr-Prozess-Modell: Default-«Entstehung» je Artikel
    _sync_locked_movements_bootstrap()
    _spawn_recurring_bootstrap()
    try:
        _bootstrap_admin()
    except Exception as e:
        print(f"WARNING: _bootstrap_admin() failed: {e}", flush=True)
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

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(contact.router)
app.include_router(admin.router)
app.include_router(erp.router)
app.include_router(articles.router)
app.include_router(processes.router)
app.include_router(article_process.router)
app.include_router(orders.router)
app.include_router(instances.router)
app.include_router(storage_locations.router)
app.include_router(claims.router)
app.include_router(events.router)
app.include_router(recurring.router)


@app.get("/")
async def root():
    return {
        "name": "Inexxio ECS API",
        "version": settings.app_version,
        "docs": "/api/docs",
    }
