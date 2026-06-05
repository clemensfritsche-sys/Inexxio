# Backend – FastAPI (Python 3.12)

## Technologie
Python 3.12, FastAPI 0.109, SQLAlchemy 2.0, Pydantic v2, Alembic, PostgreSQL 15

## Starten
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Alembic
```bash
alembic upgrade head          # Migrationen anwenden
alembic revision --autogenerate -m "description"  # Neue Migration erstellen
```

## Struktur
```
app/
├── main.py           ← FastAPI App, Router-Registrierung, CORS
├── core/
│   ├── config.py     ← Pydantic Settings (env vars)
│   ├── database.py   ← SQLAlchemy Engine + Session
│   └── auth.py       ← Firebase JWT-Verifikation, require_admin/require_staff
├── models/           ← SQLAlchemy 2.0 Mapped-Column Modelle
├── schemas/          ← Pydantic v2 Request/Response Schemas
├── routers/          ← FastAPI Router (je ein File pro Ressource)
└── services/         ← Business Logic (DB-unabhängig testbar)
```

## API-Endpunkte Phase 1
| Method | Path | Auth | Beschreibung |
|--------|------|------|--------------|
| GET | /health | – | Health Check |
| GET | /api/v1/auth/me | user | Eigenes Profil |
| POST | /api/v1/auth/terms-accept | user | AGB akzeptieren |
| GET | /api/v1/objects | staff | Universal Feed |
| CRUD | /api/v1/items | staff | Artikel |
| POST | /api/v1/items/{id}/approve | staff | Artikel freigeben |
| CRUD | /api/v1/boms | staff | Stücklisten |
| CRUD | /api/v1/work-plans | staff | Arbeitspläne |
| CRUD | /api/v1/companies | staff | Firmen (Kunden + Lieferanten) |
| CRUD | /api/v1/companies/{id}/contacts | staff | Kontakte |
| GET/PATCH | /api/v1/admin/settings | admin | Firmeneinstellungen |
| GET | /api/v1/admin/settings/public | – | Öffentliche Firma-Infos |
| CRUD | /api/v1/admin/users | admin | Benutzerverwaltung |
| GET | /api/v1/admin/audit-log | admin | Audit Log |

## Konventionen
- Soft-Delete überall: is_active=false, KEIN hard delete
- UTC Timestamps überall
- Pydantic v2: `model_validate()`, `model_dump()`, `ConfigDict(from_attributes=True)`
- SQLAlchemy 2.0: `Mapped[T]`, `mapped_column()`
- Fehler: `raise HTTPException(status_code=..., detail="...")`
- Audit-Log bei jedem Update schreiben

## Env-Variablen
Siehe /.env.example für vollständige Liste.
Pflicht lokal: DATABASE_URL, FIREBASE_PROJECT_ID
