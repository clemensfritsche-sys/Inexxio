# Inexxio AG – Enterprise Central System

Zentrales Unternehmenssystem für ein produzierendes Schweizer KMU.
Kombination aus Website/Shop + ERP + Buchhaltung + HR + Qualitätsmanagement.

## Technologie-Stack
| Bereich | Technologie |
|---------|------------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, PWA |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic |
| Datenbank | PostgreSQL 15 |
| Auth | Firebase Authentication (Magic Link, Google SSO) |
| Infra | Google Cloud Run + Firebase Hosting |

## Lokale Entwicklung

### Voraussetzungen
- Node.js 20+
- Python 3.12
- PostgreSQL 15

### Setup
```bash
# 1. Env-Variablen konfigurieren
cp .env.example .env.local
# Werte in .env.local ausfüllen

# 2. Datenbank erstellen
createdb inexxio_local

# 3. Backend starten
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 4. Frontend starten (neues Terminal)
cd frontend
npm install
npm run dev
```

### Docker
```bash
docker-compose up -d
```

## Phasenplan
| Phase | Zeitraum | Inhalt |
|-------|----------|--------|
| 1 – Fundament | Mt. 1–5 | Website, ERP Kern, Auth, Admin |
| 2 – Kernprozesse | Mt. 6–10 | PO, Produktion, SO, Stripe, Shop |
| 3 – Erweiterungen | Mt. 11–16 | NCR, CAPA, Buchhaltung, HR |
| 4 – KI | Mt. 17–22 | Bestellvorschlag, Semantische Suche |
| 5 – Advanced | Mt. 23+ | Bexio, Onshape, ISO 14001 |

## Links
- Production: https://inexxio.com
- Dev: https://inexxio.web.app
- API Docs (Dev): http://localhost:8000/api/docs
