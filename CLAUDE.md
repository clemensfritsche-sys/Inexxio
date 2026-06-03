# INEXXIO – Enterprise Central System

## Was ist Inexxio?
Zentrales Unternehmenssystem für ein produzierendes KMU (Schweizer AG, Maschinenbau).
Kombination aus Website/Shop + ERP + Buchhaltung + HR + Qualitätsmanagement.

## Architektur
- **Frontend**: Next.js 14, TypeScript, App Router, Tailwind CSS, PWA
- **Backend**: FastAPI (Python 3.12), SQLAlchemy, Pydantic, Alembic
- **DB**: PostgreSQL 15 (Cloud SQL), eine Instanz, universeller Nummernkreis
- **Auth**: Firebase Authentication (Magic Link + Google SSO + TOTP MFA für Admin)
- **Storage**: Google Cloud Storage
- **Search**: Typesense (Phase 2)
- **Email**: Gmail API
- **Payments**: Stripe (Phase 2)
- **KI**: Claude API
- **Infra**: Google Cloud Run + Firebase Hosting
- **Analytics**: Plausible Analytics (DSGVO-konform, kein Cookie-Banner)

## Repository-Struktur (Monorepo)
```
inexxio/
├── CLAUDE.md                  ← Haupt-Kontext (IMMER zuerst lesen)
├── frontend/                  ← Next.js 14 App
│   ├── CLAUDE.md
│   ├── app/
│   │   ├── (public)/          ← Öffentliche Website-Seiten
│   │   ├── (app)/             ← ERP / Auth-geschützte Seiten
│   │   └── (shop)/            ← Online Shop
│   ├── components/
│   └── types/
├── backend/                   ← FastAPI Python
│   ├── CLAUDE.md
│   ├── app/
│   │   ├── routers/           ← API Endpunkte
│   │   ├── models/            ← SQLAlchemy Modelle
│   │   ├── schemas/           ← Pydantic Schemas
│   │   ├── services/          ← Business Logic
│   │   └── core/              ← Config, Auth, DB-Connection
│   ├── alembic/               ← Datenbank-Migrationen
│   └── tests/
├── shared/
│   └── types.ts               ← Geteilte TypeScript-Typen
├── .env.example
└── docs/adr/                  ← Architecture Decision Records
```

## Konventionen
- Alle DB-Felder: `snake_case`, Englisch
- API-Endpunkte: `/api/v1/{resource}`
- Timestamps: IMMER UTC in DB, Frontend konvertiert mit `Intl.DateTimeFormat`
- Soft-Delete: Niemals hard delete – nur `is_active=false`
- Fehler: Immer strukturiert `{ error: string, code: string, details?: any }`
- Max. Funktionslänge: 80 Zeilen
- TypeScript strict mode – kein `any`
- Autosave: Debounced 3s, Rahmen leuchtet grün, 'Gespeichert um HH:MM'

## Nummernkreis
Universell 9-stellig: **100000001–999999999**. Gilt für ALLE Objekte.
Tabelle: `objects(id, object_type, created_at, created_by, is_active)`

## Wichtige Entscheide
- Artikel ohne Versionierung: Änderung → neuer Artikel + `replaced_by_id`
- BOM ohne eigene Versionierung: neue BOM = neuer Artikel
- Serialisierung: `qty=1` → Einzelteil, `qty>1` → Batch
- QC-Checks sind Arbeitsplan-Schritte (`step_type='qc_check'`)
- Prozessabschluss: Immer Pflichtfeld-Check + Signatur-Check vor Status 'Completed'
- Soft-Delete überall: `is_active=false`
- MWST: Effektive Methode, Quartal, CH 8.1% | EU B2B 0%+RC | Export 0%

## MWST-Sätze (Schweiz)
- 8.1% Standard (Inland)
- 2.6% Reduziert (Lebensmittel, Bücher)
- 3.8% Beherbergung
- 0% Export / EU B2B (Reverse Charge)

## Sicherheit
- HTTPS/TLS 1.3, HSTS, OWASP Top 10, CSP
- 2FA für Admin (TOTP Firebase MFA) – verpflichtend
- Session: JWT 24h + Refresh-Token 30 Tage
- Inaktivitäts-Timeout: 8h
- Brute-Force: 5 Fehlversuche → 15 Min. Sperre
- Google Secret Manager für alle Secrets
- Optimistic Locking: `updated_at`-Vergleich vor jedem Update

## Git-Workflow
- `main` → Production (inexxio.com) – nur via PR
- `develop` → Dev (inexxio.web.app) – auto-deployed
- `feature/xxx` → Lokale Entwicklung → PR auf develop
- Commit-Konvention: `feat:` / `fix:` / `refactor:` / `docs:` / `test:`

## Status (aktuell halten!)
**Phase**: 1 – Fundament
**Aktuell gebaut**: Projektstruktur, CLAUDE.md, .env.example, Backend-Grundgerüst, Frontend-Grundgerüst
**Nächste Aufgabe**: Backend DB-Modelle + Alembic Migrationen + API-Endpunkte für Artikel

## Phasenplan
| Phase | Zeitraum | Inhalt |
|-------|----------|--------|
| 1 – Fundament | Mt. 1–5 | Cloud, Auth, Website DE+EN, ERP Kern (Artikel, BOM, Arbeitsplan, Serialisierung, Admin) |
| 2 – Kernprozesse | Mt. 6–10 | PO, Produktion, SO, Stripe, Lager, Domain, E-Mail |
| 3 – Erweiterungen | Mt. 11–16 | NCR/8D, CAPA, Audit, Risiko, ISO 9001, Zeiterfassung, Buchhaltung |
| 4 – KI & Auto | Mt. 17–22 | Bestellvorschlag, Semantische Suche, OCR |
| 5 – Advanced | Mt. 23+ | Bexio, Onshape API, ISO 14001, FR+IT |
