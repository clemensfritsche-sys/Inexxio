# Inexxio AG – Enterprise Central System

Zentrales Unternehmenssystem für ein produzierendes Schweizer KMU (AG, Maschinenbau):
öffentliche Website + ERP. Buchhaltung, HR und Qualitätsmanagement sind geplant, aber
nicht gebaut – was heute wirklich steht, sagt `CLAUDE.md` («Was heute steht»).

## Technologie-Stack
| Bereich | Technologie |
|---------|------------|
| Frontend | Next.js 16 / React 19 (statischer Export), TypeScript strict, Tailwind CSS |
| Website | Astro 7 (`website/`, reines HTML) – dieselbe Hosting-Site |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.1, Pydantic v2, Alembic |
| Datenbank | PostgreSQL 16 |
| Auth | Firebase Authentication (Magic Link, Google SSO, Passkeys/WebAuthn) |
| Infra | Google Cloud Run (Backend) + Firebase Hosting (Frontend) |

## Lokale Entwicklung

### Voraussetzungen
- Node.js 22 (die Website verlangt ≥ 22.12)
- Python 3.12
- PostgreSQL 16

### Setup
```bash
# 1. Env-Variablen konfigurieren
cp .env.example .env.local
# Werte in .env.local ausfüllen

# 2. Datenbank erstellen
createdb inexxio_local

# 3. Backend starten
cd backend
pip install --require-hashes -r requirements.lock   # dieselben Pakete wie CI und Docker
alembic upgrade head          # die Migration ist der einzige Weg zum Schema
uvicorn app.main:app --reload --port 8000

# 4. Website bauen (liefert Kopf und Fuss für das ERP; ohne sie sind es Platzhalter)
cd website
npm ci
npm run build

# 5. Frontend starten (neues Terminal)
cd frontend
npm ci
npm run dev
```

### Docker
```bash
docker-compose up -d
```

### Prüfen
```bash
cd backend  && INEXXIO_REQUIRE_DB=1 pytest tests/ -rs   # wie die CI: ohne PostgreSQL ein Fehler
cd backend  && ruff check .
cd frontend && npm run type-check && npm run lint && npm test && npm run build
cd website  && npm test && npx astro check && npm run build
cd backend  && python -m scripts.deadcode   # findet, was niemand mehr liest   (das ganze Gate: .github/workflows/quality.yml)
```

## Dokumentation
| Datei | Inhalt |
|---|---|
| `CLAUDE.md` | Kontext, was heute steht, verbindliche Regeln |
| `PROCESS_CORE.md` | Die Prozesslogik (vor Arbeit am Prozess lesen) |
| `SYSTEM_LOGIC.md` | Die Regeln als prüfbare Sätze (Massstab der Tests) |
| `docs/prozessbild.md` | Wie das Prozessbild gezeichnet wird |
| `docs/backlog.md` | Was offen ist (benannt, nicht gebaut) |
| `website/WEBSITE_PLAN.md` | Die geltenden Entscheide der Website |

| `docs/adr/` | Architekturentscheide, jeder mit Kopfstatus |
| `docs/attic.md` | Was entfernt wurde, wo es liegt, welche Entscheidung darin steckt |
| `docs/history/` | Archiv – beschreibt Zustände, die es nicht mehr gibt |

## Phasenplan
| Phase | Zeitraum | Inhalt |
|-------|----------|--------|
| 1 – Fundament | Mt. 1–5 | Website, ERP Kern, Auth, Admin |
| 2 – Kernprozesse | Mt. 6–10 | PO, Produktion, SO, Stripe, Shop |
| 3 – Erweiterungen | Mt. 11–16 | NCR, CAPA, Buchhaltung, HR |
| 4 – KI | Mt. 17–22 | Bestellvorschlag, Semantische Suche |
| 5 – Advanced | Mt. 23+ | Bexio, Onshape, ISO 14001 |

## Deployment
| Branch | Ziel | Auslöser |
|---|---|---|
| `develop` | https://inexxio-dev.web.app | Push (automatisch) |
| `main` | https://inexxio-prod.web.app | Push + **manuelle Freigabe** (Environment `production`) |

Backend jeweils Cloud Run (`europe-west6`), Frontend Firebase Hosting.
API-Docs lokal: http://localhost:8000/api/docs
