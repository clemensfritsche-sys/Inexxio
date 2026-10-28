import re
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from .core.config import get_settings
from .core.database import SessionLocal
from .domain import statuses as st
from .domain import timekeeping as timekeeping_domain
from .routers import (
    admin, articles, attachments, auth, beleg, communication, contact, documents, erp, feedback,
    health, website,
    instances, newsletter, orders, passkey, payments, payments_list, places, public_documents,
    timekeeping,
)

settings = get_settings()


#: Der Start läuft je Datenbank einmal zur Zeit – mehrere Worker und Instanzen warten
#: aufeinander, statt dieselben Trigger gleichzeitig neu zu schreiben.
_STARTUP_LOCK_KEY = 778_899_001


def _sync_database_rules(db) -> None:
    """**Endzustände sind terminal, Zeiteinträge append-only – und das steht in der
    Datenbank.** Beide Trigger werden bei jedem Start aus der Fachschicht neu geschrieben
    (``statuses.terminal_guard_sql`` · ``timekeeping.append_only_sql``): kommt ein zweiter
    Endzustand in den Katalog, gilt er ab dem nächsten Start auch unten, ohne dass jemand
    an eine Migration denken muss. Scheitert das, startet der Dienst nicht."""
    db.execute(text(st.terminal_guard_sql()))
    db.execute(text(timekeeping_domain.append_only_sql()))


def _seed(name: str, fn) -> None:
    """Ein Start-Schritt mit Daten (nicht Schema) in eigener Sitzung: scheitert er, steht
    es im Log, und der Dienst läuft – die Daten fehlen dann, sichtbar, statt alles
    anzuhalten."""
    db = SessionLocal()
    try:
        fn(db)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"WARNING: Start-Schritt «{name}» fehlgeschlagen: {e!r}", flush=True)
    finally:
        db.close()


def _adopt_documents(db) -> None:
    """Die Rechtstexte werden einmal Dokumente (``legal.adopt_templates``) – selbstbegrenzend."""
    from .services import legal
    done = legal.adopt_templates(db)
    if done:
        print(f"INFO: Rechtstexte als Dokumente übernommen: {done}", flush=True)


def _ensure_operator(db) -> None:
    """Der Betreiber (``sites.operator``) ist ein nummerierter Datensatz – beim Start
    einmal angelegt, unabhängig davon, ob jemand die Einstellungen öffnet."""
    from .services.sites import operator
    operator(db)


def _startup() -> None:
    """Was aus dem Code folgt – das Schema baut allein die Migration (``start.sh``)."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _STARTUP_LOCK_KEY})
        _sync_database_rules(db)
        db.commit()
    finally:
        db.close()
    _seed("Betreiber", _ensure_operator)
    _seed("Rechtstexte", _adopt_documents)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _startup()      # vor der ersten Anfrage: blockieren darf es hier
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


#: Was keine Spur im Log hinterlassen muss: reine Lese-Anfragen.
_READS = ("GET", "HEAD", "OPTIONS")


def _log_write(method: str, path: str, user_id: int) -> None:
    """Eine Zeile im ``audit_log`` – in eigener Sitzung; scheitert sie, bleibt die Antwort."""
    from .services.admin import log_audit
    db = SessionLocal()
    try:
        log_audit(db, "request", method, path[:500], user_id)
        db.commit()
    except Exception as exc:                                   # noqa: BLE001
        print(f"WARNING: audit_writes failed: {exc!r}", flush=True)
        db.rollback()
    finally:
        db.close()


@app.middleware("http")
async def audit_writes(request: Request, call_next):
    """►►► **Jede schreibende Anfrage ans ERP steht im Log** (``audit_log``, ``services/admin``). ◄◄◄

    Eine Zeile je erfolgreichem Schreiben: wer, welche Handlung (Methode + Pfad), wann. Was
    eine Stelle genauer protokolliert (vorher/nachher, «im Namen von»), steht daneben. Die
    Datenbank-Arbeit läuft im Threadpool, nie in der Event-Loop."""
    response = await call_next(request)
    user_id = getattr(request.state, "user_id", None)
    if (request.method in _READS or response.status_code >= 400 or user_id is None
            or not request.url.path.startswith("/api/v1/")):
        return response
    await run_in_threadpool(_log_write, request.method, request.url.path, user_id)
    return response


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Ein verletzter DB-Constraint ist ein **Eingabe**-Fehler: 400 mit einem Satz, der die
    betroffene **Spalte** nennt – der Zeileninhalt gehört ins Log, nie in die Oberfläche."""
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


#: Rohe Pydantic-Meldungen → Klartext. Was hier nicht steht, wird als Regel-Satz
#: durchgereicht, mit dem Feldnamen davor.
_VALIDATION_TEXTS: tuple[tuple[str, str], ...] = (
    ("Field required", "fehlt"),
    ("at least 1 character", "darf nicht leer sein"),
    ("at least", "ist zu kurz"),
    ("at most", "ist zu lang"),
    ("valid integer", "muss eine ganze Zahl sein"),
    ("valid number", "muss eine Zahl sein"),
    ("valid boolean", "muss ja oder nein sein"),
    ("greater than or equal", "ist zu klein"),
    ("less than or equal", "ist zu gross"),
    ("valid list", "muss eine Liste sein"),
    ("valid dictionary", "hat die falsche Form"),
)

#: Feldnamen → das Wort, das der Mensch auf dem Bildschirm sieht. Ein Feld, das hier
#: fehlt, erscheint mit seinem technischen Namen – unschön, aber ehrlich, und es fällt
#: auf. Eine erfundene Übersetzung wäre schlimmer.
_FIELD_LABELS: dict[str, str] = {
    "name": "Name",
    "quantity": "Menge",
    "size": "Abmessungen",
    "weight_kg": "Gewicht",
    "unit": "Mengeneinheit",
    "serialization": "Serialisierung",
    "module_type": "Modultyp",
    "label": "Bezeichnung",
    "type": "Typ",
    "target": "Sollwert",
    "tolerance": "Toleranz",
    "points": "Erfassungspunkte",
    "steps": "Prozessschrittmodule",
    "lines": "Definitionszeilen",
    "article_object_id": "Artikel",
    "origin": "Herkunft",
    "values": "Erfassung",
    "config": "Konfiguration",
}


def _field_path(loc: tuple) -> str:
    """``('body', 'steps', 0, 'name')`` → «Prozessschrittmodule → 1 → Name» – **wo** der
    Fehler steckt; Listen-Indizes ab 1."""
    parts: list[str] = []
    for item in loc:
        if item in ("body", "query", "path"):
            continue
        if isinstance(item, int):
            parts.append(str(item + 1))
        else:
            parts.append(_FIELD_LABELS.get(str(item), str(item)))
    return " → ".join(parts)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Eingabefehler in **Klartext**: was fehlt, und wo – an einer Stelle für jeden
    Endpunkt. Ins Log kommen nur Ort und Art der Fehler, nie die Eingabe selbst (sie kann
    Personendaten tragen)."""
    seen: list[str] = []
    for err in exc.errors():
        where = _field_path(tuple(err.get("loc") or ()))
        # ``Value error, …`` ist Pydantic-Rahmen um eine **selbst geschriebene** Meldung
        # aus einem Feld-Validator. Die ist bereits Klartext – sie braucht die Übersetzung
        # nicht, nur den Rahmen weg.
        raw = str(err.get("msg") or "").removeprefix("Value error, ")
        what = next((text for needle, text in _VALIDATION_TEXTS if needle in raw), raw)
        # Nennt die Meldung ihr Feld schon selbst, wäre der Pfad davor ein Stottern
        # («Name: Name ist ein Pflichtfeld»).
        head = where.split(" → ")[-1] if where else ""
        line = what if (head and head.lower() in what.lower()) else (
            f"{where}: {what}" if where else what)
        if line not in seen:
            seen.append(line)
    shape = [(list(e.get("loc") or ()), e.get("type")) for e in exc.errors()]
    print(f"WARNING: 422 on {request.method} {request.url.path} – {shape}", flush=True)
    return JSONResponse(
        status_code=422,
        content={"detail": " · ".join(seen) or "Die Eingaben sind unvollständig.",
                 "code": "VALIDATION_ERROR"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Letzte Auffanglinie: Traceback ins Log, eine **JSON-Antwort** an den Client
    (ausserhalb der Produktion mit der Ursache in ``detail``)."""
    tb = traceback.format_exc()
    print(f"ERROR: Unhandled exception on {request.method} {request.url.path}\n{tb}", flush=True)
    expose = settings.debug or settings.app_env.lower() != "production"
    detail = f"{type(exc).__name__}: {exc}" if expose else "Interner Serverfehler"
    return JSONResponse(status_code=500, content={"detail": detail, "code": "INTERNAL_ERROR"})

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(passkey.router)
app.include_router(contact.router)
app.include_router(website.router)
app.include_router(admin.router)
app.include_router(erp.router)
app.include_router(articles.router)
app.include_router(orders.router)
app.include_router(instances.router)
app.include_router(places.router)
app.include_router(attachments.router)
app.include_router(documents.router)
app.include_router(public_documents.router)
app.include_router(payments.router)
app.include_router(beleg.router)
app.include_router(payments_list.router)
app.include_router(feedback.router)
app.include_router(communication.router)
app.include_router(communication.callback_router)
app.include_router(newsletter.router)
app.include_router(newsletter.me_router)
app.include_router(newsletter.erp_router)
app.include_router(timekeeping.router)


@app.get("/")
def root():
    """Name und Version – ``docs`` nur, wenn die Dokumentation eingeschaltet ist."""
    out = {"name": settings.app_name, "version": settings.app_version}
    if app.docs_url:
        out["docs"] = app.docs_url
    return out
