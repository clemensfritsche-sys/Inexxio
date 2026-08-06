import re
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from .core.config import get_settings
from .core.database import Base, SessionLocal, engine
from .models import UserProfile
from .core import features
from .routers import (
    admin, articles, attachments, auth, captures, contact, erp, events, feedback, health,
    instances, object_refs, orders, passkey,
)
# Nicht importiert, weil abgeschaltet (siehe core/features.py): ai, consent, documents,
# document_files, legal, sales, shop. Ihre Module hängen an der entfernten Prozesslogik
# und sind derzeit nicht importierbar – ihre Prefixe beantwortet ein Stub mit 503.

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
    # ``company_settings`` wird von JEDER Standort-Anzeige und von den öffentlichen
    # Endpunkten (Impressum, Shop-Konfiguration) gelesen. Fehlt hier eine Spalte, die das
    # Modell kennt, endet jede dieser Abfragen in einem 500 – das nimmt ERP **und** Website
    # mit. Genau das ist mit ``is_primary`` passiert (Migration 090), als sie hier fehlte.
    ("company_settings", "google_maps_api_key", "VARCHAR(255)"),
    ("company_settings", "is_operator", "BOOLEAN NOT NULL DEFAULT false"),
    ("company_settings", "currency", "VARCHAR(3) NOT NULL DEFAULT 'CHF'"),
    ("company_settings", "legal_documents", "JSONB"),
    ("company_settings", "is_active", "BOOLEAN NOT NULL DEFAULT true"),
    ("company_settings", "object_id", "BIGINT"),
    # Artikel-Spezifikation (optionale Felder, nachträglich ergänzt).
    ("articles", "landed_unit_cost", "NUMERIC(12,4)"),
    ("articles", "material", "VARCHAR(255)"),
    ("articles", "cad_url", "VARCHAR(500)"),
    ("articles", "surface", "VARCHAR(255)"),
    ("articles", "supplier_article_number", "VARCHAR(255)"),
    ("articles", "min_order_qty", "NUMERIC(12,3)"),
    ("articles", "safety_stock", "NUMERIC(12,3)"),
    ("articles", "replaced_by_id", "BIGINT"),
    ("articles", "is_hazmat", "BOOLEAN DEFAULT FALSE NOT NULL"),
    # Die Erfassungsmaske der Datenerfassung (Migration 102) – eine NEUE Spalte auf einer
    # BESTEHENDEN Tabelle, also gehört sie ins Netz. Das ist die Lehre aus 090: die
    # Migration ist die Wahrheit, das Netz der zweite Weg, und beim Ausfall zählt nur der.
    ("articles", "capture_fields", "JSONB"),
)
# Für ``instances`` steht hier bewusst NICHTS mehr: die Tabelle wird von Migration 102
# neu aufgebaut. Ein Netz-Eintrag würde eine gerade entfernte Spalte wieder anlegen –
# das Netz darf reparieren, aber nicht auferstehen lassen. Die Einträge für orders /
# order_lines / purchase_orders / sales / shipments / movements / disposals /
# resource_usages / documents / inspections / article_process_steps / material_moves /
# instance_order_links sind mit ihren Tabellen entfallen.

_NUMERIC_QTY_COLUMNS: tuple[tuple[str, str], ...] = ()
# Leer, seit es keine gespeicherten Mengen mehr gibt: die Menge einer Instanz ist die
# Anzahl ihrer Einzelinstanzen und wird gezählt. Die Schleife bleibt stehen, weil die
# nächste Bruchmengen-Spalte hier hinein gehört – nicht in einen neuen Mechanismus.

# VARCHAR-Spalten, die nachträglich verbreitert wurden (Migration 060): idempotentes
# ALTER, falls Alembic übersprungen wurde. 'replenishment' (13 Zeichen) scheiterte an
# der ursprünglichen Breite 12 – jede Auto-Nachbestellung endete im Truncation-Fehler.
_VARCHAR_WIDEN_COLUMNS: tuple[tuple[str, str, int], ...] = ()

# Obsolete Spalten, die aus dem Modell entfernt wurden. In Prod wird das Schema
# via create_all() (nicht Alembic) erzeugt – diese NOT-NULL/Alt-Spalten würden
# sonst INSERTs brechen (z. B. purchase_orders.transport_included). Idempotent.
_DROP_COLUMN_SAFETY_NET = (
    # Gesellschaften (Migration 091): der «Betreiber» ist WÄHLBAR (``is_operator`` mit eigenem
    # Unique-Index) statt das starre «Hauptsitz»-Flag. ``is_primary`` ist tot – auch im Netz
    # gedroppt, falls Alembic 091 nicht durchlief (belt-and-suspenders).
    ("company_settings", "is_primary"),
    # Reste des per Notfall-Revert (#85) zurückgenommenen Konzepts «Standort als Instanz».
    ("articles", "is_location"),
    ("articles", "max_load_kg"),
    # Dokument-Redesign: das Dokument wurde im Auftrag verfasst (Nummer = Instanz).
    ("articles", "physical"),
)
# Die Einträge für orders / order_lines / purchase_orders / sales / shipments / documents /
# inspections / article_process_steps sind mit ihren Tabellen entfallen (Migration 102).

# Indizes, die nach dem Initial-Schema ergänzt wurden. create_all() legt Indizes
# nur für NEUE Tabellen an – auf bestehenden Tabellen müssen sie idempotent
# nachgezogen werden (sonst Seq-Scans, z. B. auf dem wachsenden Audit-Log).
_INDEX_SAFETY_NET = (
    ("ix_audit_log_object_id", "audit_log", "object_id"),
    ("ix_audit_log_table_name", "audit_log", "table_name"),
    ("ix_company_settings_object_id", "company_settings", "object_id"),
    # Neues Datenmodell: der Feed filtert Instanzen je Artikel, das Detail zählt die
    # Einzelinstanzen einer Instanz. Beides ohne Index ein Seq-Scan über den Bestand.
    ("ix_instances_article_id", "instances", "article_id"),
    ("ix_instance_units_instance_id", "instance_units", "instance_id"),
    ("ix_captures_instance_unit_id", "captures", "instance_unit_id"),
)

# Roh-Indizes mit speziellem Typ: GIN auf der Reservierungs-Map – die Hot-Path-Abfragen
# ``Instance.reservations.has_key(...)`` (Unterdeckung, Verkaufs-Abgang, Abschluss)
# wären sonst Full-Table-Scans über den gesamten Bestand.
_RAW_INDEX_SAFETY_NET: tuple[str, ...] = ()
# Die GIN-Indizes auf ``instances.reservations``/``locations`` sind mit den Spalten entfallen.

# Daten-Normalisierungen (idempotent), wenn keine Alembic-Migration lief.
# Die Fixes für purchase_orders / documents / article_process_steps / instances sind mit
# ihren Tabellen bzw. Spalten entfallen (Migration 102).

# Verkaufs-Sichtbarkeit 'unlisted' wird nicht mehr unterstützt → auf 'private' normalisieren.
_ARTICLE_DATA_FIXES = (
    "UPDATE articles SET sales_visibility='private' WHERE sales_visibility='unlisted'",
)

# Gesellschaften (Migration 091): genau EIN Betreiber. Wurde die Spalte gerade erst vom
# Sicherheitsnetz ergänzt (Default ``false``), trüge sonst KEINE Zeile die Markierung –
# lesend fiele ``sites.find_operator`` zwar auf die kleinste ``id`` zurück, aber der
# gewählte Betreiber wäre nicht persistent. Wiederholbar; ein bereits gewählter Betreiber
# bleibt unberührt. Der partielle Unique-Index erzwingt «höchstens einer».
_COMPANY_DATA_FIXES = (
    "UPDATE company_settings SET is_operator = true "
    "WHERE id = (SELECT min(id) FROM company_settings) "
    "AND NOT EXISTS (SELECT 1 FROM company_settings WHERE is_operator)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_company_settings_operator "
    "ON company_settings (is_operator) WHERE is_operator",
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
            for stmt in _RAW_INDEX_SAFETY_NET:
                conn.execute(text(stmt))
            if "articles" in tables:
                for stmt in _ARTICLE_DATA_FIXES:
                    conn.execute(text(stmt))
            if "company_settings" in tables:
                # Über information_schema auf DERSELBEN Verbindung prüfen – ``insp`` stammt
                # von VOR dem ADD-COLUMN-Lauf und sähe die eben ergänzte Spalte nicht
                # (gleiche Begründung wie beim ``documents``-Block oben).
                cs_cols = {r[0] for r in conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='company_settings'"))}
                if "is_operator" in cs_cols:
                    for stmt in _COMPANY_DATA_FIXES:
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
    # Die KI-Identität wird NICHT mehr geseedet: das Modul ``ai`` ist abgeschaltet
    # (core/features.py) und hängt an der entfernten Prozesslogik.
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


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Ein verletzter DB-Constraint ist ein **Eingabe**-Fehler, kein Serverabsturz.

    Vorher fiel er in die letzte Auffanglinie unten und erschien im Formular als roher
    psycopg2-Dump («NotNullViolation … Failing row contains (2, Inexxio LLC, null, Dah…»,
    Testnotiz #338): unlesbar, und er verriet nebenbei den Zeileninhalt. Hier wird daraus
    ein 400 mit einem Satz, der die betroffene **Spalte** nennt – die eigentliche Ursache
    gehört ins Log, nicht in die Oberfläche."""
    tb = traceback.format_exc()
    print(f"ERROR: IntegrityError on {request.method} {request.url.path}\n{tb}", flush=True)
    raw = str(getattr(exc, "orig", exc))
    column = None
    match = re.search(r'column "([^"]+)"', raw)
    if match:
        column = match.group(1)
    if "not-null" in raw or "NotNullViolation" in raw:
        detail = (f"Pflichtangabe «{column}» fehlt." if column
                  else "Eine Pflichtangabe fehlt.")
    elif "unique" in raw.lower():
        detail = (f"«{column}» ist bereits vergeben." if column
                  else "Dieser Wert ist bereits vergeben.")
    else:
        detail = "Die Angaben verletzen eine Datenbank-Regel und wurden nicht gespeichert."
    return JSONResponse(status_code=400, content={"detail": detail, "code": "INTEGRITY_ERROR"})


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
app.include_router(contact.router)
app.include_router(admin.router)
app.include_router(erp.router)
app.include_router(articles.router)
app.include_router(orders.router)
app.include_router(instances.router)
app.include_router(captures.router)
app.include_router(object_refs.router)
app.include_router(events.router)
app.include_router(attachments.router)
app.include_router(feedback.router)

# Abgeschaltete Module antworten unter ihren eigenen Prefixen mit 503 und Grund –
# «nicht da» und «abgeschaltet» sind verschiedene Aussagen. ZULETZT registriert, damit
# kein Stub einen aktiven Nachbarn verdeckt.
for _stub in features.stub_routers():
    app.include_router(_stub)


@app.get("/")
async def root():
    return {
        "name": "Inexxio ECS API",
        "version": settings.app_version,
        "docs": "/api/docs",
    }
