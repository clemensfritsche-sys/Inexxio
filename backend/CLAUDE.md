# Inexxio Backend – FastAPI

## Stack
- Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic, asyncpg
- PostgreSQL 15 mit pgcrypto (sensititve Felder) + pgvector (Phase 1 vorbereiten)

## Struktur
```
app/
├── core/       config.py, database.py, auth.py
├── models/     SQLAlchemy ORM Models (base_object, user, item, bom, company, ...)
├── schemas/    Pydantic Request/Response Schemas
├── services/   Business Logic (item_service, object_service, ...)
└── routers/    FastAPI Router (health, auth, items, ...)
alembic/        DB Migrationen
```

## Wichtige Regeln
- Alle Timestamps: UTC in DB (`DateTime(timezone=True)`)
- Soft-Delete: Immer `is_active=false` via `object_service.soft_delete()`
- Jede neue ERP-Entität braucht zuerst `create_object()` → gibt 9-stellige ID
- Audit-Log: Jede Feldänderung in `update_*` services → `AuditLog` Eintrag
- API-Prefix: `/api/v1/{resource}`
- Fehler: `{ error: str, code: str, details?: Any }`
- Optimistic Locking: `updated_at`-Vergleich vor Update (TODO: implementieren)

## Lokaler Start
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# API Docs: http://localhost:8000/api/docs
```

## Migrationen
```bash
alembic upgrade head         # Migrationen ausführen
alembic revision -m "name"   # Neue Migration erstellen
```

## Status Phase 1
- [x] Projektstruktur
- [x] Core (config, database, auth)
- [x] Models: objects, users, items, boms, work_plans, companies, audit_log, company_settings
- [x] Services: object_service, item_service
- [x] Routers: health, auth, items
- [x] Alembic Migration 001 (Initial Schema)
- [ ] Tests für item_service
- [ ] Admin-Router (company_settings CRUD)
- [ ] SSE (Server-Sent Events) für Echtzeit-Updates
