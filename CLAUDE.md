# INEXXIO – Enterprise Central System

> **WICHTIG:** Vollständige und verbindliche Projekt-Anforderungen in `docs/Lastenheft_v1.0.md` – vor Entwicklungsarbeiten konsultieren.

## Was ist Inexxio?
Zentrales Unternehmenssystem für ein produzierendes Schweizer KMU (AG, Maschinenbau).
Kombination aus Website/Shop + ERP + Buchhaltung + HR + Qualitätsmanagement.

Rechtsform: Aktiengesellschaft (AG), Schweiz
Branche: Produzierendes Gewerbe / Maschinenbau
Mitarbeiter: ca. 10 | Artikel: ca. 1'000

## Architektur
```
Frontend:  Next.js 14, TypeScript, App Router, Tailwind CSS, PWA
Backend:   FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic v2, Alembic
DB:        PostgreSQL 15 (Cloud SQL), universeller 9-stelliger Nummernkreis
Auth:      Firebase Authentication (Magic Link + Google SSO + TOTP MFA für Admin)
Storage:   Google Cloud Storage
Search:    Typesense (Phase 2)
Email:     Gmail API (info.inexxio@gmail.com Phase 1 → @inexxio.com ab Phase 2)
Payments:  Stripe (Phase 2)
KI:        Claude API (Anthropic)
Infra:     Google Cloud Run + Firebase Hosting
Analytics: Plausible Analytics (DSGVO-konform)
```

## Monorepo-Struktur
```
inexxio/
├── CLAUDE.md              ← Haupt-Kontext (IMMER zuerst lesen)
├── frontend/              ← Next.js 14 App
│   ├── CLAUDE.md          ← Frontend-spezifischer Kontext
│   └── src/
│       ├── app/
│       │   ├── (public)/  ← Öffentliche Website-Seiten
│       │   ├── (auth)/    ← Login
│       │   └── (erp)/     ← ERP / Auth-geschützte Seiten
│       ├── components/    ← UI-Komponenten
│       └── types/         ← TypeScript Interfaces
├── backend/               ← FastAPI Python
│   ├── CLAUDE.md          ← Backend-spezifischer Kontext
│   └── app/
│       ├── routers/       ← API Endpunkte
│       ├── models/        ← SQLAlchemy Modelle
│       ├── schemas/       ← Pydantic Schemas
│       ├── services/      ← Business Logic
│       └── core/          ← Config, Auth, DB-Connection
├── shared/
│   └── types.ts           ← Geteilte TypeScript-Typen
├── .env.example           ← Vorlage für Env-Variablen
└── docs/
    └── adr/               ← Architecture Decision Records
```

## Design System
Tailwind CSS, minimalistisch, dark-mode-fähig.
- Farben: Neutrale Grautöne (slate), Akzentblau (blue-600 #2563eb)
- Komponenten: Karten mit shadow-sm, runde Ecken (rounded-xl/rounded-lg)
- Density: Kompakt aber luftig – 8px Grid-System
- Font: Inter

## Konventionen
- Alle DB-Felder: snake_case, Englisch
- API-Endpunkte: /api/v1/{resource}
- Timestamps: IMMER UTC in DB, Frontend konvertiert mit Intl.DateTimeFormat
- Soft-Delete: Niemals hard delete – nur is_active=false
- Fehler: Immer strukturiert { error: string, code: string, details?: any }
- Max. Funktionslänge: 80 Zeilen
- TypeScript strict mode – kein 'any'

## Nummernkreis
Universell 9-stellig: 100'000'001–999'999'999. Gilt für ALLE Objekte.
Tabelle: objects(id, object_type, created_at, updated_at, created_by, updated_by, is_active)

## Wichtige Entscheide
- Artikel haben keine Versionierung: Änderung → neuer Artikel + replaced_by_id
- BOM hat keine eigene Versionierung: neue BOM = neuer Artikel
- Serialisierung: qty=1→Einzelteil (unit), qty>1→Batch
- QC-Checks sind Arbeitsplan-Schritte (step_type='qc_check')
- Prozessabschluss: Pflichtfeld-Check + Signatur-Check vor Status 'Completed'
- Autosave: Debounced 3s, grüner Rahmen-Flash
- MWST CH: 8.1% Standard | 2.6% Reduziert | 3.8% Beherbergung | 0% Export
- MWST EU B2B: 0% + Reverse Charge (VAT-ID auf Rechnung)

## Sicherheit
- HTTPS/TLS 1.3, HSTS, CSP, Security Headers
- 2FA für Admin (TOTP Firebase MFA, verpflichtend)
- Session-Timeout 8h | Brute-Force Sperre nach 5 Versuchen
- Google Secret Manager für alle Secrets
- Optimistic Locking: updated_at-Vergleich vor jedem Update

## DSGVO / Schweizer DSG
- CH DSG (01.09.2023) + DSGVO für EU
- Plausible Analytics: Privacy-by-Design, kein Cookie-Banner
- AGB-Akzeptanz: Zeitstempel + Version in DB
- 10-Jahres-Archivierung Buchungsbelege (unveränderlich)

## Pflichtregeln für Claude – vor jeder Änderung

> Diese Regeln sind VERBINDLICH und müssen bei jeder Arbeitssitzung eingehalten werden.

### 1. Immer zuerst mit Remote synchronisieren
Vor der ERSTEN Code-Änderung einer Sitzung zwingend ausführen:
```bash
git fetch origin develop
git pull origin develop
git log --oneline -5
git status
```
Erst danach dürfen Dateien gelesen oder editiert werden.

### 2. Dateien immer frisch lesen – niemals Zusammenfassungen vertrauen
Kontext-Komprimierungen (Context Summaries) beschreiben Dateien so, wie sie *waren*, nicht so, wie sie *aktuell* auf `develop` liegen. Vor jedem Edit die Datei mit dem Read-Tool neu laden.

### 3. Änderungen nur auf Basis des aktuellen `develop`-Stands
Niemals auf Basis von:
- gespeicherten Kontext-Beschreibungen aus einer früheren Session
- eigenen früheren Edits, die noch nicht gepusht/gemerged wurden
- Annahmen über den Dateiinhalt

### 4. Branch-Workflow
- Entwicklung auf Feature-Branch (z.B. `claude/...`)
- Merge nach `develop` erst nach expliziter Freigabe durch den User
- Direktes Pushen auf `develop` nur wenn ausdrücklich angewiesen

## Lokale Entwicklung
```bash
# Backend starten
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend starten
cd frontend && npm install
npm run dev

# Datenbank
createdb inexxio_local
cd backend && alembic upgrade head
```

## Status (aktuell halten)
Phase: 1 | Deployment: develop → https://inexxio-dev.web.app

### Tatsächlich gebaut (Stand Juni 2026)
- Monorepo-Struktur vollständig
- Backend: FastAPI mit UserProfile (Benutzer- & Profilverwaltung), Admin-Einstellungen, Audit-Log, Notifications, Kontaktformular
- Backend: Artikel-Stammdaten (`articles`, Status draft/released/inactive, gemeinsamer Nummernkreis via `services/objects.py`)
- Frontend: Öffentliche Website (Homepage, Über uns, Kontakt, Impressum, AGB, Datenschutz)
- Frontend: ERP mit Reitern Benutzer + Artikel (Master-Detail-Feed)
- Frontend: Artikel-Anlage via «+» (Pflichtfelder Name/Einheit/Serialisierung/Grösse/Gewicht), Detailfenster mit Reitern Stammdaten/Prozess/Bestand
- Frontend: Admin Einstellungen + Benutzerverwaltung
- Frontend: Profileinstellungen (Profil, Adresse, Rechnungsadresse, Sicherheit, Benachrichtigungen, Datenschutz)
- **Generische Auftrags-Prozess-Engine** (`services/process.py`): Der Auftrag führt eine geordnete
  Liste von Prozessschritten (`article_process_steps`, pro Artikel optional & frei sortierbar via
  `position`). Schritt-Status wird aus der Fachtabelle abgeleitet (keine Orchestrierungstabelle);
  Auftrag wird **automatisch `completed`**, wenn alle Schritte erledigt sind. Schritttypen:
  - **purchase** (Beschaffung): Bestellung `purchase_orders` unter dem Auftrag (keine eigene Nummer),
    Ablauf requested→quoted→ordered→received (+rejected); webshop: requested→ordered→received.
    Offerte = **eine Bestellsumme** (netto), Stück-/Einstandspreis = Summe÷Menge. Saubere
    Verantwortungstrennung (Lieferant offeriert, Besteller bestellt/nimmt an).
  - **serialization** (Serialisierung): erzeugt **Instanzen** (`instances`, eigene Objektnummer) –
    Einzelteil → N Stück-Instanzen, Batch → 1 Charge à N. Speist den **Bestand** (`services/serialization.py`).
  - **inspection** = «**Datenerfassung**»: nennt **konkret die zu prüfenden Instanzen** (Stichprobe).
    Prüfumfang % via `sample_percent`: Einzelteil → N zufällig (stabil) ausgewählte Instanzen; Charge →
    eine Instanz mit N Proben. Je Stichprobe ein Wertesatz (`inspections.samples`), konfigurierbare Maske
    (`capture_fields`: Soll-Ist mit Toleranz / Gut-Schlecht / Text; ohne Maske synthetisches Gut-Schlecht).
    Ergebnis (passed/failed) = alle Proben ok, wird auf `instances.qc_status` übertragen (`services/inspection.py`).
  - **movement** = «**Bewegung**»: bringt Instanzen an ihren Standort. Jede Instanz hat **immer** einen
    Standort (`instances.location_type` ∈ lagerplatz|user|instance + `location_id` = Objektnummer des
    Ziels). Der Lagerist setzt je Instanz das Ziel (auch unterschiedliche Ziele pro Auftrag möglich);
    optionales Vorgabe-Ziel am Schritt – **ein** kombiniertes Auswahlfeld (Lagerplatz/Person/Instanz),
    leer = Standort nicht definiert/frei wählbar. Abschluss-Marker = `movements` (analog inspection, keine
    eigene Nummer); Standorte direkt auf den Instanzen (`services/movement.py`, `services/locations.py`).
- ERP-Feed: Datensätze nach Nummer **absteigend**; **Instanzen** sind eigener Feed-Typ
  (`/api/v1/erp/instances`, read-only Detail). Prozessdefinition im BPMN-Stil (Typ-Auswahl beim
  Hinzufügen, Drag&Drop-Reihenfolge, Start/Ende-Knoten).
- Status als **Prozess** (kein Dropdown): Entwurf →[Freigeben]→ Freigegeben →[Deaktivieren]→ Inaktiv
  (→[Reaktivieren]); gilt für Artikel/Auftrag/Lagerplatz (`lib/status-flow.ts`, `StatusFlow`)
- Frontend: Artikel-«Prozess»-Reiter (Schritttypen hinzufügen/sortieren), **Bestand**-Reiter zeigt die
  Instanzen. Auftrag heisst starr «Auftrag», nur **freigegebene** Artikel referenzierbar, Menge mit
  Artikel-Einheit, Wunsch-Liefertermin optional (Default «Schnellstmöglich»), Bedarf nach Freigabe
  read-only. Auftrag-Detail: **Auftrag-Stepper** über alle Schritte + Panel des gewählten Schritts
  (Beschaffung/Serialisierung/Datenerfassung/Bewegung); Lieferant sieht nur die Beschaffung seiner Aufträge.
- **Standorte**: jede Instanz hat immer einen Standort. Bei der Serialisierung landen Instanzen im
  **Wareneingang** (Systemkonfiguration `company_settings.default_receiving_location_id`; fehlt der
  Eintrag, wird automatisch ein Lagerplatz «Wareneingang» angelegt). Admin → Einstellungen → «Lager &
  Logistik» wählt den Standard-Wareneingang. Der **Bewegungs**-Schritt verteilt von dort weiter – das
  PO-Modul bleibt standort-agnostisch (mehrere Lager = mehrere Lagerplätze als Bewegungsziele).
  Lagerplätze werden überall über die **Objektnummer** angesprochen (kein Name); freigegebene
  Lagerplätze zeigen die Karte read-only; optionale **Bemerkung** (`note`) je Lagerplatz.
- **Artikelnamen**: beim Anlegen aus einem Katalog gewählt (kein Freitext); Pflege via Admin →
  Einstellungen → «Artikelnamen» (`company_settings.article_names`, auch über `settings/public`).
- **ERP-UX-Konventionen**: Detailfenster speichern per **Auto-Save** (debounced, Enter löst sofort aus,
  grüner Rahmen-Flash; kein Speichern-Knopf – `lib/use-autosave.ts`). Referenz-Auswahlfelder sind
  durchsuchbar (`SearchSelect`, Suche auch per Objektnummer-Teilstring). Referenzierte **Objektnummern
  sind klickbar** und öffnen den Datensatz (`components/erp/obj-id.tsx` + `ErpNavContext`). Artikel ohne
  Prozessschritt sind **nicht freigebbar**. Auftrag-Stepper zeigt beim Hover Wer/Wann je erledigtem
  Schritt; Instanzen haben einen Reiter **Verwendung** (Verwendungsnachweise, neu→alt).

> **HINWEIS:** Artikel **Stammdaten** + **Prozess** + **Bestand** (Instanzen mit Standort) sind gefüllt.
> Prozess-Schritttypen: purchase, serialization, inspection, movement. E-Mail-Versand ist nur als TODO
> vermerkt (Gmail API, Phase 2). Stückliste/BOM, Arbeitspläne und Stripe sind **noch nicht** implementiert.

Nächste Aufgabe: E-Mail-Versand (Gmail API); Stückliste/BOM; Arbeitspläne; Stripe

## Deployment
- Trigger: Push auf Branch `develop`
- Workflow: .github/workflows/deploy-dev.yml
- Backend: Cloud Run (inexxio-dev, europe-west6)
- Frontend: Firebase Hosting (inexxio-dev → https://inexxio-dev.web.app)
- Nach Änderungen: git push → develop mergen → git push develop
- Erster Besuch nach Deploy: einmal Hard-Refresh (Ctrl+Shift+R) nötig

## Phasenplan
| Phase | Zeitraum | Inhalt |
|-------|----------|--------|
| 1 – Fundament | Mt. 1–5 | Google Cloud, Firebase Auth, Website DE+EN, ERP Kern |
| 2 – Kernprozesse | Mt. 6–10 | PO + Lieferantenportal, Produktion, SO + Kundenportal, Stripe |
| 3 – Erweiterungen | Mt. 11–16 | NCR/8D, CAPA, Audit, Risiko, ISO 9001, HR, Buchhaltung |
| 4 – KI & Auto | Mt. 17–22 | Bestellvorschlag KI, Semantische Suche, OCR |
| 5 – Advanced | Mt. 23+ | Bexio-Integration, Onshape API, ISO 14001 |
