# Backend – FastAPI (Python 3.12)

## Technologie
Python 3.12, FastAPI 0.109, SQLAlchemy 2.0, Pydantic v2, Alembic, PostgreSQL 15

## Pflichtregeln – vor jeder Änderung

Vor der ersten Änderung in einer Sitzung:
```bash
git fetch origin develop && git pull origin develop
git log --oneline -5 && git status
```
Dann: Betroffene Datei mit Read-Tool frisch laden – niemals Kontext-Zusammenfassungen als Dateiinhalt behandeln.

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
├── models/           ← SQLAlchemy 2.0 Modelle (je ein File pro Entität)
│   ├── user.py       ← UserProfile
│   ├── audit.py      ← AuditLog
│   ├── notification.py ← Notification
│   ├── admin.py      ← CompanySettings
│   └── __init__.py   ← Re-Export aller Modelle (immer von hier importieren)
├── schemas/          ← Pydantic v2 Request/Response Schemas
├── routers/          ← FastAPI Router (je ein File pro Ressource)
├── services/         ← Business Logic (DB-unabhängig testbar)
└── scripts/
    └── dump_openapi.py ← OpenAPI-Schema → backend/openapi.json (SSOT für FE-Typen)
```

## OpenAPI → Frontend-Typen (Single Source of Truth)
Die TypeScript-Typen des Frontends werden aus den Pydantic-Schemas generiert.
Nach jeder Änderung an einem Request/Response-Schema:
```bash
cd backend && python -m scripts.dump_openapi     # → backend/openapi.json
cd ../frontend && npm run generate:types          # → src/types/api.ts
```

## API-Endpunkte (tatsächlich vorhanden, Phase 1)
| Method | Path | Auth | Beschreibung |
|--------|------|------|--------------|
| GET | /health | – | Health Check |
| GET | /api/v1/auth/me | user | Eigenes Profil |
| PATCH | /api/v1/auth/me | user | Eigenes Profil bearbeiten (Self-Service) |
| POST | /api/v1/auth/terms-accept | user | AGB akzeptieren |
| GET | /api/v1/erp/records | staff | Benutzer-Feed (Master-Detail) |
| GET/PATCH | /api/v1/erp/records/{object_id} | staff/admin | Datensatz lesen/ändern |
| GET/PATCH | /api/v1/admin/settings | admin | Firmeneinstellungen |
| GET | /api/v1/admin/settings/public | – | Öffentliche Firma-Infos |
| GET | /api/v1/admin/users | staff | Benutzerliste |
| PATCH | /api/v1/admin/users/{id}/role | admin | Rolle ändern |
| DELETE | /api/v1/admin/users/{id} | admin | Benutzer deaktivieren |
| GET | /api/v1/admin/audit-log | admin | Audit Log |
| GET | /api/v1/admin/notifications | user | Eigene Benachrichtigungen |
| POST | /api/v1/contact | – | Kontaktformular |

> Artikel/BOM/Arbeitspläne/Companies sind Phase 2+ und **noch nicht** implementiert.

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
