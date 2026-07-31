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
Auth:      Firebase Authentication (Magic Link + Google SSO + Passkeys/WebAuthn + TOTP MFA für Admin)
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

## Design System (VERBINDLICH)

> **Inexxio Design System** ist die EINE, verbindliche Grundlage für ALLE
> Oberflächen (Website, Shop, ERP). Jede neue oder geänderte UI **MUSS** darauf
> aufbauen. Es ist der in den Code übernommene Export aus **Claude Design**.
> Vollständige Regeln & Nutzung: **`docs/design-system/README.md`** (vor UI-Arbeit
> lesen), Marken-/Visual-Doku: `docs/design-system/brand-foundations.md`.

- **Quelle der Wahrheit für Tokens:** `frontend/src/styles/design-system/colors_and_type.css`
  (geladen als erstes CSS-Modul in `app/layout.tsx`). Token-Werte werden NUR dort
  definiert – niemals in `globals.css`, `tailwind.config.js` oder Komponenten hart
  kodieren.
- **Nutzung:** Tailwind-Utilities aus den Tokens (`bg-bg-2`, `text-fg-3`,
  `text-accent`, `border-border-1`, `rounded-ds-lg`, `shadow-ds-md`, `font-display`),
  CSS-Vars (`var(--fg-2)`) oder `.ix-*`-Typo-Helper.
- **Farbe = Bedeutung:** warme Neutraltöne tragen die Fläche; **Rot (`inexxio`) ist
  der EINE laute Akzent** (CTA / ein Headline-Wort / aktiv / Fehler, nie dekorativ);
  **Slate (`accent`) ist die leise Stimme** für Info/aktiv/Links im dichten ERP.
- **ERP:** Struktur vor Fläche (Haarlinien + Weissraum statt Schatten), Status als
  Punkt+Wort, Symbole (Lucide) statt Text, tabellarische Zahlen, Infotexte im Hover.
- **Alt = deprecated:** `slate-*` / `blue-600` / `brand-*` (blaue Alt-Marke) sind
  Altlast; beim Anfassen einer Komponente auf die Tokens migrieren (Tabelle in
  `docs/design-system/README.md §4`). Kein Big-Bang – inkrementell mitziehen.
- Density: kompakt aber luftig – 8px-Grid. Font: Inter (Body) / Inter Tight (Display).

## Leitbild (VERBINDLICH)

### ERP ist Master – alles andere ist Spiegelbild
Jeder Datensatz hat **genau EINEN Ort, an dem er gepflegt wird: das ERP.** Oberflächen
ausserhalb des ERP (Konto/Profil, Admin-Seiten, Shop) sind **Spiegel** – sie zeigen an,
sie besitzen nicht. Konkret:

- Dieselbe fachliche Angabe darf **nie an zwei Stellen editierbar** sein. Existiert ein
  ERP-Datensatz dafür, ist die andere Stelle read-only mit Verweis («wird am ERP-Datensatz
  … gepflegt»).
- Ein Formular ausserhalb des ERP darf schreiben, wenn es der **Selbstbedienungs-Pfad** einer
  Person auf ihre EIGENEN Daten ist (Profil, Rechnungsadresse) – dann ist es derselbe
  Datensatz über denselben Endpunkt, nicht eine zweite Wahrheit.
- Beim Anfassen einer Oberfläche prüfen: *Gibt es diese Eingabe schon woanders?* Wenn ja,
  die schwächere Stelle zum Spiegel machen, statt die Logik zu duplizieren.
- **Das ERP muss ALLES können**, was aussenrum geht – nicht nur anzeigen. Konkret am
  Benutzer: `ErpAdminUpdate` **erbt** von `UserProfileUpdate` (alles, was die Person selbst
  pflegt) und ergänzt die Anstellungsdaten. Geprüft in `tests/test_frontend_mirrors.py`.
- Schreiben beide Oberflächen denselben Datensatz, tun sie es über **denselben Pfad**
  (`people.apply_profile_update` – gleiche Zuweisung, gleiches Audit-Log). Sonst ist eine
  Änderung je nach Herkunft nachvollziehbar oder eben nicht.

### Eine Sache, eine Stelle
Gleiches gleich behandeln: gleiche Bedeutung → gleicher Name, gleiche Datenform, **eine**
Implementierung (z. B. `services/address.py` für Adressen, `services/people.py` für
Personennamen, `services/locations.py` für Standorte, `objects.obj_nr` für die
Objektnummer, `components/erp/address-field.tsx` für jede Adress-Eingabe). Zwei Wege für
dieselbe Sache sind ein Bug, auch wenn beide funktionieren.

Braucht eine Regel zwei **Formen** (SQL-Bedingung *und* Prüfung auf einem geladenen
Objekt), stehen beide nebeneinander in EINEM Modul und tragen denselben Namensstamm –
`inventory.in_stock_clauses()` / `inventory.is_in_stock()`. Zwei Formen einer Regel sind
in Ordnung; zwei Regeln sind es nicht.

**Spiegel über die API-Grenze** (Frontend braucht Symbol/Label zu Backend-Aufzählungen)
sind erlaubt, aber getestet: `backend/tests/test_frontend_mirrors.py` vergleicht die
handgepflegten TS-Unions (`StepType`, `LocationType`, `ArticleUnit`) und die Labels gegen
die Backend-Quellen. So bleibt der Spiegel schnell und kann trotzdem nicht auseinanderlaufen.

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
- Backend: FastAPI mit UserProfile (Benutzer- & Profilverwaltung), Admin-Einstellungen, Audit-Log, Kontaktformular
- Backend: Artikel-Stammdaten (`articles`, Status draft/released/inactive, gemeinsamer Nummernkreis via `services/objects.py`)
- Frontend: Öffentliche Website (Homepage, Über uns, Kontakt, Impressum, AGB, Datenschutz)
- Frontend: ERP mit Reitern Benutzer + Artikel (Master-Detail-Feed)
- Frontend: Artikel-Anlage via «+» (Pflichtfelder Name/Einheit/Serialisierung/Grösse/Gewicht), Detailfenster mit Reitern Stammdaten/Prozess/Bestand
- Frontend: Admin Einstellungen + Benutzerverwaltung
- **Betriebskosten Monat-bis-heute** (`GET /admin/operating-costs`, `services/operating_costs.py`): am
  Unternehmens-Datensatz eine kompakte Übersicht der **tatsächlichen** laufenden Kosten – KI aus dem
  Event-Strom (verbrauchte Tokens × Modell-Tarif), Zahlungen aus Stripe-Gebühren der bezahlten Verkäufe,
  Infrastruktur als anteilige Google-Cloud-Schätzung; grosse Ist-Summe + Monats-Hochrechnung.
- Frontend: Profileinstellungen – **auf 4 Reiter konsolidiert**: «Mein Profil» (Person + Adresse +
  Rechnungsadresse + Newsletter/AGB-Nachweis, gestapelt), «Bestellungen & Abos», «Meine Dokumente»,
  «Sicherheit». Der frühere «Benachrichtigungen»-Reiter ist entfernt (die Toggles `notification_email`/
  `notification_inapp` hatten KEINE Backend-Wirkung – kein E-Mail-/In-App-System; Spalten bleiben für die
  spätere Gmail-Anbindung). Vollständigkeits-Badge (`useProfileCompletion`) rechnet Adresse/Rechnung neu
  dem Profil-Reiter zu. **Runde 2:** «Mein Profil» ist jetzt EINE Komponente (`profile-section.tsx`) mit
  **einem** Formular/Auto-Save und **drei** Containern – Persönliche Angaben (inkl. **Telefon**),
  **Adressen** (Liefer- + Rechnungsadresse über EINEN «Rechnungsadresse = Lieferadresse»-Schalter im
  gleichen Container), Kommunikation (Newsletter + AGB-Nachweis als **Tatsache**, nicht als Fake-Toggle).
  `contact-section.tsx`/`invoice-section.tsx`/`privacy-section.tsx` sind entfallen. Toggle-Optik ist
  einheitlich (`ToggleField`, rot = an). **Rechnungs-E-Mail** zeigt die Konto-Adresse als Platzhalter
  (leer = dorthin). **Adresszusatz** bleibt (Shippo-Etiketten brauchen c/o · Postfach · Stockwerk), wird
  aber erst auf «+ Adresszusatz» eingeblendet statt als leeres Dauerfeld.
- **Frische Daten nach einer Pause – ohne Polling** (`erp/page.tsx`, `lib/api.ts`, `lib/firebase.ts`):
  Der ERP-Feed war ein **Schnappschuss vom Seitenaufbau** (ein `useEffect([])`, sonst nichts) – wer ein
  paar Minuten weg war, sah alte Daten und musste F5 drücken. Verschärfend: der Bearer-Token ist ein
  In-Memory-Schnappschuss (Firebases proaktive Erneuerung ist ein Timer, der im Hintergrund-Tab
  gedrosselt wird), und **jeder 401 wurde still verschluckt** → der Feed rendete «Keine Datensätze»
  statt eines Fehlers. Zwei Eingriffe, beide kostenneutral: (1) `api.setTokenProvider` – bei einem 401
  wird **einmal** ein frischer Token geholt (`getIdToken(true)`) und dieselbe Anfrage wiederholt
  (registriert in `firebase.ts`, kein Import-Zyklus); (2) Rückkehr-Refresh: bei `visibilitychange`/
  `focus` lädt der Feed **einmal** nach – aber nur, wenn er älter als `STALE_AFTER_MS` (60 s) ist.
  Kein Intervall, kein Polling: ein Nachladen je Rückkehr, nichts beim kurzen Tab-Wechsel.
- **Code-Cleanup & Härtung (Juli 2026, `docs/cleanup-2026-07.md`)**: Migration `060` –
  **Meldebestand-Bug behoben** (`orders.reason` VARCHAR(12)→(20): `replenishment` hat 13
  Zeichen, JEDE Auto-Nachbestellung scheiterte vorher am Truncation-Fehler); GIN-Index auf
  `instances.reservations` + Indizes `sales.customer_id`/`orders.recurring_parent_id`/
  `purchase_orders.supplier_id`; PR-#90-Spalten in Alembic nachgezogen (Alembic = Schema-SSOT);
  tote Spalten (`orders.stripe_checkout_session_id`, `sales.fx_rate`), das nie verdrahtete
  `Notification`-Modell und die F-Rollback-Reste (#85) entfernt. **Race-Conditions gehärtet**
  (Row-Locks): Stripe-Webhook-Doppelzustellung (CheckoutIntent), FIFO-Allokation in allen
  Schreibpfaden (kein Überverkauf), `ensure_supply`/`check_article` (kein Doppel-Nachschub);
  Shop-Handler mit FX-/Stripe-Calls als `def` (kein Event-Loop-Blocking). Tote Endpunkte
  (`GET /shop/session/{id}`, `GET …/sales/audience`, `GET /erp/instances/{id}/documents`)
  + totes i18n (`frontend/messages/`, next-intl war nie installiert) entfernt. Wording
  kanonisch (Spezifikation/Charge/Instanz/Standort). Responsive: Inline-Grids kollabieren
  auf Mobile, Warenkorb auf Tokens + umbrechend, Touch-Ziele ≥40px, Freiraum fürs KI-Widget.
- **Architektur-/Logik-Review (Juli 2026, `docs/review-2026-07.md`)**: systematische Prüfung auf
  Zirkularitäten/Blockaden/Logiklücken; 15 Befunde sofort behoben. Kernpunkte: (1) **Shop-Versand
  repariert** – der Shop-Verkaufsauftrag legte seinen Versandschritt OHNE `locked`/`mode='customer'`
  an → nach Zahlung dauerhaft «blockiert», kein Shop-Auftrag konnte je versendet werden (Fix +
  Datenreparatur Migration `074`); (2) **«verkauft durch DIESEN Auftrag» zählt als GELIEFERT**
  (`process.sold_amounts_for_order` aus dem Event-Strom) statt als «verloren» – vorher Phantom-
  Fehlmengen nach Zahlung (Nachschub auf volle Menge dimensioniert, Chargen-Retoure kam mit Menge 1
  statt der verkauften Menge zurück; NACH Verkauf verschrottete Instanzen bleiben ehrlich fehlend);
  (3) **Kunden-Versand bewegt nur Verkauftes/Eigenes** (`movement.movable_instances`, EINE Auswahl-
  regel für Ausführung/Embed/Versand-Beleg) – vorher wanderte der unverkaufte Rest einer teilverkauf-
  ten Charge zum Kunden; reine Teilmengen-Sendung quittiert ohne Umlagerung statt 409; (4) **Kopier-
  Vollständigkeit**: `_copy_steps` (Ersetzen/Wiederkehr) kopiert jetzt `doc_signers`/`sign_sequential`/
  `doc_audience*`/`doc_visibility`/`transport_mode`, `duplicate_article` auch `is_hazmat`/`reorder_
  target`/Beschaffungsquelle (vorher: Consent-Lücke + Freigabe-Gate-Bruch beim
  Nachfolger); (5) **Unterschriften-Deadlocks**: Ausstellen prüft aktive Parteien, Admin-Deaktivierung
  blockiert bei offenen Signoffs, abgelehntes Signoff bleibt für den Eigentümer re-aktionabel und hält
  die sequenzielle Position; (6) **Consent-Supersede erst bei in Kraft getretener Nachfolge**
  (freigegebenes Dokument, nicht schon beim Entwurf-Nachfolger); (7) **Auto-Abweichung** wird nicht
  mehr von offenen Nachschub-Kindern unterdrückt (`open_deviations` filtert `reason='deviation'`);
  (8) **steckengebliebene Nachbestellung** (fehlgeschlagener Schritt) unterdrückt Auto-Nachbestellung
  nicht mehr (Stockout-Schutz); (9) **Race-Fixes**: Row-Locks in `release_order` (Doppel-Freigabe →
  doppelte Instanzen), `recovery.cover_from_stock` (Instanz-Wahl), `_issue_refund` (Doppel-Refund;
  zudem: Stripe-bezahlter Verkauf verlangt Stripe-Provider für die Erstattung), Kunden-Retoure
  (Doppelklick); Scrap prüft Meldebestand VOR dem Abschluss (keine Nachbestell-Kette).
  **Folgethemen-Umsetzung (gleicher Monat, `docs/review-2026-07.md §3`)**: Slice-Retouren
  (Teilmengen-Verkauf einer Charge ist retournierbar – Subjekte aus `process.sold_amounts_for_order`,
  Rückfluss mengengenau in die Original-Charge, event-idempotent, erst nach quittierter Rückgabe-
  Bewegung); Consent-Gate serverseitig (`consent.assert_acknowledged` an Checkout/Retoure/Lieferanten-
  Offerte); `doc_visibility` als Lese-Zugriffsfilter + **Parteien-Substitution** am laufenden Auftrag
  (`POST …/document/substitute-signer`); Benutzer-Identität (deaktiviert = 403 beim Login statt
  stiller Neuanlage; `POST /admin/users/{id}/reactivate` + FE-Knopf); **CheckoutIntent-Reaper** im
  Wartungs-Sweep (verlassene Warenkörbe geben Reservierungen nach 24 h frei); **Produktabo-Auto-
  Fulfillment** (`invoice.paid` released den Wiederkehr-Entwurf und verbucht die Zahlung);
  `legal_ack_config` entfernt (Migration 075); Kleinigkeiten (Preis-Pin committet keine fremden
  Änderungen mehr, Publikums-Obligationen ohne N+1, Refund-Ablehnung bei Alt-Beleg ohne Snapshot im
  Mehrpositionen-Fall). **Einzig offen aus dem Review: «fehlgeschlagener Schritt ist terminal»**
  (bewusst zurückgestellt – braucht ein «Schritt wiederholen»-Design).
- **Generische Auftrags-Prozess-Engine** (`services/process.py`): Der Auftrag führt eine geordnete
  Liste von Prozessschritten (`article_process_steps`, pro Artikel optional & frei sortierbar via
  `position`). Schritt-Status wird aus der Fachtabelle abgeleitet (keine Orchestrierungstabelle);
  Auftrag wird **automatisch `completed`**, wenn alle Schritte erledigt sind.
  **Bestands-Instanzen entstehen direkt bei der Auftragsfreigabe** (kein eigener Schritt mehr,
  `services/serialization.py`): Einzelteil → N Stück-Instanzen, Batch → 1 Charge à N (`instances`,
  eigene Objektnummer). Startstandort = **Lieferant** (Beschaffung mit Lieferant) sonst Wareneingang –
  volle Rückverfolgbarkeit/Aktionen ab Tag 1 (Standort, Seriennummer, Reklamation).
  **Instanz-Lebenszyklus – ZWEI getrennte Achsen** (Migration `030`, statt überladenem `qc_status`):
  `quality` ∈ pending|passed|**blocked** («darf man es verwenden?») und `disposition` ∈ in_process|in_stock|consumed|
  sold|scrapped («wo ist es?»). Neue Instanzen starten `(pending, in_process)`; bei Auftrags-Abschluss
  → `(passed, in_stock)` («Freigegeben, ab Lager verbrauchbar») via `process.recompute_completion` →
  `release_instances` (`released_at` = FIFO-Basis). Datenerfassung gibt NICHT vorzeitig frei (nur
  Durchfaller → `quality=blocked` = «Gesperrt», Migration `085`). Verbaut → `disposition=consumed`, verkauft → `sold`, verschrottet →
  `scrapped`. **Verbrauchbar/zählbar = `quality=passed` UND `disposition=in_stock`** – die EINE Helper-
  Stelle `inventory.in_stock_clauses()` (von Bestand/FIFO/Betriebsmittel geteilt). Anzeige: eine Badge
  als Projektion beider Achsen (`lib/process.ts: instanceStatusConfig`).
  **Reservierung:** bei der Auftragsfreigabe werden die zu verbrauchenden Komponenten für genau diesen
  Auftrag reserviert (`instances.reserved_for_order_id`); reservierte Instanzen sind für andere Aufträge
  nicht verbrauchbar (FIFO blendet sie aus). Auflösung bei Abschluss/Deaktivierung des Auftrags.
  **Mehr-Operationen-Routing:** mehrere gleichartige Schritte (z. B. mehrere `resource`-Operationen)
  sind hintereinander möglich – jede Fachzeile trägt die `step_id` ihrer Schritt-Definition, der
  Status wird **pro Schritt** abgeleitet (`process.fact_for_step`/`resolve_exec_step`). Schritttypen:
  - **purchase** (Beschaffung): Bestellung `purchase_orders` unter dem Auftrag (keine eigene Nummer),
    Ablauf requested→quoted→ordered→received (+rejected); webshop: requested→ordered→received.
    Offerte = **eine Bestellsumme** (netto), Stück-/Einstandspreis = Summe÷Menge. Saubere
    Verantwortungstrennung (Lieferant offeriert, Besteller bestellt/nimmt an). Die **Lieferadresse**
    ist die **Firmenadresse**; den realen Wareneingangs-Ort setzt die **Bereitstellung** nach der
    abgeschlossenen Beschaffung (`provisioning.ensure_provisioning`) – NICHT mehr die Bestellung selbst.
    **Bezugsquelle wird IM PROZESSSCHRITT definiert** (max. Flexibilität – ein Prozess darf mehrere
    `purchase`-Schritte mit UNTERSCHIEDLICHEN Lieferanten/Quellen haben, was ein reines Artikel-Feld
    nicht abbilden kann): am Schritt `article_process_steps.mode` (supplier|webshop) +
    `supplier_id`/`webshop_url`. Der **Artikel-Standard** (`articles.procurement_mode` +
    `default_supplier_id`/`default_webshop_url`, Reiter «Spezifikation» → Beschaffung) dient als
    **Vorbelegung/Fallback**: das Schritt-Formular ist damit vorbelegt und leer gelassene Schritte erben
    ihn. `purchase.resolve_source(step, article)` ist die EINE Auflösung (Schritt ≻ Artikel-Default),
    ihr Ergebnis wird als Snapshot auf die Bestellung geschrieben; `serialization._initial_location`
    erbt den Lieferanten-Startort ebenso. **Freigabe-Gate** (`purchase.has_source(step, article)`): ein
    Artikel/Auftrag mit `purchase`-Schritt lässt sich nur freigeben, wenn die Bezugsquelle **am Schritt
    ODER als Artikel-Default** auflösbar ist (Router-Check in `articles.py`/`orders.py`; das Frontend
    warnt proaktiv am Schritt, `procurementReady`).
  - **inspection** = «**Datenerfassung**»: allgemeine Werterfassung (nicht nur QC) – nennt **konkret die
    zu prüfenden Instanzen** (Stichprobe). Prüfumfang % via `sample_percent`: Einzelteil → N zufällig
    (stabil) ausgewählte Instanzen; Charge → eine Instanz mit N Proben. Je Stichprobe ein Wertesatz
    (`inspections.samples`), konfigurierbare Maske (`capture_fields`: Soll-Ist mit Toleranz / Gut-Schlecht /
    Text; ohne Maske synthetisches Gut-Schlecht). **Ungenügende Teil-Stichprobe → Hochstufung auf 100 %**
    (`inspections.escalated`); erst bei vollem Umfang endgültig `failed`, dann je Instanz bewertet (Charge
    als Ganzes). Durchfaller werden **gesperrt** (`instances.quality='blocked'`, `services/inspection.py`) –
    derselbe Zustand wie beim Schritt «Sperren»; **geklärt wird nur über den Folgeauftrag**
    (`inspections.resolved_by_order_id`, siehe Testnotizen-Runde 6).
  - **movement** = «**Bewegung**»: bringt Instanzen an ihren Standort. Jede Instanz hat **immer** einen
    Standort (`instances.location_type` ∈ user|instance|company + `location_id` = Objektnummer des
    Ziels). Der Lagerist setzt je Instanz das Ziel (auch unterschiedliche Ziele pro Auftrag möglich);
    optionales Vorgabe-Ziel am Schritt – **ein** kombiniertes Auswahlfeld (Person/Instanz/Unternehmen),
    leer = Standort nicht definiert/frei wählbar. Abschluss-Marker = `movements` (analog inspection, keine
    eigene Nummer); Standorte direkt auf den Instanzen (`services/movement.py`, `services/locations.py`).
    **Charge auf mehrere Standorte verteilen – AUFTRAGSGETRIEBEN (`services/location_split.py`, Migration
    `067`)**: Eine Charge (z. B. 1000 Schrauben unter EINER Objektnummer) kann physisch auf mehrere
    Standorte verteilt sein (990 @ Eingang, 10 @ Band A) – **ohne Teilung der Instanz / ohne neue
    Objektnummer**, exakt nach dem Vorbild von `reservations`: `instances.locations` = Map
    `{ziel_objektnr: {"t":typ,"q":menge}}` (Summe = quantity). Ein Ort → Map `NULL`, der Skalar
    `location_*` ist die Wahrheit; verteilt → die Map ist die Wahrheit, der Skalar spiegelt die **grösste**
    Teilmenge (denormalisiert, wie `reserved_for_order_id`). **Das Verteilen geschieht AUSSCHLIESSLICH über
    einen regulären Auftrag + Bewegungsschritt, NICHT als Aktion an der Instanz:** ein Bestands-Auftrag über
    z. B. 10 Stück reserviert mengengenau 10 der 1000er-Charge (FIFO, `subject._allocate_stock_for`); der
    Bewegungsschritt verlagert **genau diese vom Auftrag reservierte Teilmenge** ans Ziel
    (`movement.record_movement`: `share = reserved_for(inst, order)`, dann `location_split.move`), der Rest
    bleibt liegen. GANZE Instanz / Erzeugung / Kunden-Versand / Retoure (keine Teil-Reservierung) →
    `location_split.set_single` (führt eine verteilte Charge wieder zusammen). Das Panel zeigt die bewegte
    Teilmenge (`InstanceEmbed.move_quantity`). Am **Instanz-Detail** ist die Verteilung nur **read-only**
    sichtbar (`components/erp/instance-locations.tsx`) – kein Verlagern dort. FIFO/Verbrauch/Reservierung
    sind **standortunabhängig** und unberührt; Teil-Verschrottung/-Verbrauch ziehen die Verteilung per
    `location_split.reconcile` nach. «Wer liegt hier?» (`references.object_references`) findet eine Charge
    auch über ihre Teil-Slices (`locations ? '<objektnr>'`, GIN-Index).
  - **consume** = «**Verbrauch**» / **tool** = «**Betriebsmittel**»: zwei Schritttypen – der
    **Modus ist der Schritttyp** (NICHT Artikel-Eigenschaft, NICHT pro Zeile; `article.kind` gibt es
    nicht mehr). Je Schritt eine Liste von Zeilen (`resource_lines` = [{article_id, quantity **pro
    Stück**}]). **consume**: Bauteil wird in die **Produkt-Instanz eingebaut** (Standort → `instance`)
    = Lagerabgang; Auswahl strikt **FIFO nach Freigabe** (`instances.released_at`),
    Chargen-**Teilentnahme**. **tool**: Werkzeug/Maschine wird nur **genutzt** (kein Lagerabgang, kein
    FIFO, freie Wahl). Nur **freigegebene** (qc passed) Instanzen verbrauchbar/nutzbar; Verfügbarkeit
    wird geprüft. Beide buchen in `resource_usages` (keine eigene Nummer); Genealogie via Instanz-
    «Verwendung» (Eingebaut in/Enthält, Betriebsmittel-Nutzung) – `services/resource.py`. Das Panel
    zeigt den Verbrauch **je Produkt-Instanz** (welche Komponenten-Instanz in welche Produkt-Instanz
    verbaut wird; Vorschau = FIFO-Plan, danach das Protokoll) – `ResourceEmbed.products`.
- **KEIN Prozess-Objekt mehr** (Migration `031`): Ein Prozess ist nur noch die geordnete Schrittliste,
  die ENTWEDER am **Artikel** (`article_process_steps.article_id`, «wie etwas entsteht», EIN Prozess je
  Artikel) ODER am **Auftrag** (`order_id`, individueller Ablauf) hängt. Keine Objektnummer, kein eigener
  Lebenszyklus, keine n:m-Verknüpfung, kein `is_standard`, keine `source`. Tabellen `processes` +
  `article_process_links` sind entfernt; Feed-Typ «Prozesse» weg. `services/processes.py` liefert nur noch
  `article_steps`/`order_custom_steps`/`has_custom_steps`. Schritt-CRUD generisch über
  `routers/article_process.py` (`/articles/{id}/steps` und `/orders/{id}/steps`).
- **Auftrags-Subjektart – ABGELEITET aus der DEKLARIERTEN Schritt-Rolle** (kein Modus-Flag): **produce**
  (Artikel + Menge → fährt den Artikel-Prozess, ERZEUGT Instanzen) | **stock** (wirkt auf vorhandenen
  Bestand: FIFO ab Lager bzw. via `instances.subject_of_order_id` fixierte Instanzen). `subject.subject_kind`
  leitet die Art über `event_types.derive_subject_mode`/`SUBJECT_PRECEDENCE` ab: **KEINE eigenen Schritte →
  produce**, und **eigene Schritte, die Bestand HEREINBRINGEN** (Beschaffung/Ressource haben Subjekt-Rolle
  `PRODUCE`) → **ebenfalls produce** (erzeugt Instanzen!); nur ein Zugriff auf vorhandenen Bestand
  (Verkauf → `STOCK`) bzw. eine Bearbeitung bestehender Instanzen (Bewegung/Prüfung/Verschrottung →
  `INSTANCE`) ergibt **stock**. **Wichtig (Regression-Fix):** früher galt „jeder eigene Schritt = stock" –
  dadurch wurde ein Auftrag mit einem **order-level `purchase`-Schritt** fälschlich als Bestands-Operation
  behandelt und band bei leerem Lager still 0 Instanzen (keine Objektnummer, keine Fehlermeldung). Jetzt ist
  er korrekt `produce`. Frontend spiegelt dieselbe Regel (`lib/process.ts: isStockOperation`,
  `ProcessSteps.onStepsCount(n, isStockOp)`). `subject_instance_id`/`process_id`/`orders.mode` sind entfernt.
- **Freigabe auf Artikel-Ebene**: Die Artikel-Freigabe (Reiter «Spezifikation») friert Spezifikation **und**
  Prozess gemeinsam ein – Schritte sind nur im Artikel-Entwurf editierbar. Ein **make-Auftrag startet nur**,
  wenn der **Artikel freigegeben** ist (einzige Vorbedingung, `routers/orders.py`). Bei der Artikelanlage
  entsteht KEIN Auto-Prozess mehr; Schritte werden im Reiter «Prozess» direkt am Artikel gepflegt.
- **Deklarative Ereignis-Registry (REA-Kern, `app/domain/event_types.py`)**: EINE Quelle der Wahrheit
  für jeden Schritt-/Ereignistyp – Label, **Bestands-Polarität** (increase/decrease/move/neutral),
  **Subjekt-Rolle** (produce/stock/instance) und Fachtabelle. Die Polarität ist **deklariert**, nicht
  aus der Prozessform erraten. `process.STEP_LABELS`/`_FACT_MODEL`/`RESOURCE_STEP_TYPES`,
  `processes.derive_source`/`stock_effect` und die Schema-Whitelist `ALLOWED_STEP_TYPES` lesen alle
  aus dieser Registry. Die **`consume`/`tool`-Alt-Schritttypen sind entfernt** (nur noch `resource`,
  Modus je Zeile). Bestandswirksame Vorgänge schreiben ihre Polarität in den Event-Strom
  (`inventory.increased`, `resource.recorded` mit `polarity`/`delta`) → Event-Log als ökonomische Wahrheit.
- **Quelle & Lager-Richtung werden ABGELEITET, nicht gewählt** (Frage 2): KEIN Quellen-/Richtungs-
  Dropdown mehr. `processes.recompute_source` leitet `source` über die **deklarierte Vorrangordnung**
  (`stock ≻ produce ≻ instance`, `event_types.SUBJECT_PRECEDENCE`) ab und speichert sie. `stock_effect`
  ist das **Aggregat der Schritt-Polaritäten**: increase | decrease | **mixed** (Zu- UND Abgang) |
  neutral – ehrlich auch bei gemischten Prozessen statt 1:1-Spiegel der Subjektart. Anzeige als Badge
  (`ProcessResponse.stock_effect`, `OrderResponse.process_stock_effect`).
- ERP-Feed: Datensätze nach Nummer **absteigend**; **Instanzen** sind eigener Feed-Typ
  (`/api/v1/erp/instances`, read-only Detail). Prozessdefinition im BPMN-Stil (Typ-Auswahl beim
  Hinzufügen, Drag&Drop-Reihenfolge, Start/Ende-Knoten).
- Status als **Prozess** (kein Dropdown): Entwurf →[Freigeben]→ Freigegeben →[Deaktivieren]→ Inaktiv
  (→[Reaktivieren]); gilt für Artikel/Auftrag (`lib/status-flow.ts`, `StatusFlow`)
- Frontend: Artikel-«Prozess»-Reiter (Schritttypen hinzufügen/sortieren), **Bestand**-Reiter zeigt die
  Instanzen. Auftrag heisst starr «Auftrag», nur **freigegebene** Artikel referenzierbar, Menge mit
  Artikel-Einheit, Wunsch-Liefertermin optional (Default «Schnellstmöglich»), Bedarf nach Freigabe
  read-only. Auftrag-Detail: Sektion **Instanzen** (bei Freigabe erzeugt, mit Standort/QC) +
  **Auftrag-Stepper** über alle Schritte (Schlüssel = Schritt-id, mehrere gleichartige möglich) + Panel
  des gewählten Schritts (Beschaffung/Datenerfassung/Bewegung/Ressource); Lieferant sieht nur die
  Beschaffung seiner Aufträge.
- **Standorte – der Datensatztyp «Lagerplatz» ist ERSATZLOS entfallen** (Juli 2026): ein Lagerplatz
  war ein eigener Datensatz mit Feed, Detailfenster, Status-Fluss, Adresse, Massen, Traglast und
  Flags – und **kein einziges** dieser Felder trug Logik (Nachweis: ausserhalb von Modell/Schema
  tauchten sie nur in der Kopierfunktion des «Ersetzen» auf). Faktisch war er eine **Objektnummer
  mit Namen**. Entfernt sind: Modell/Schema/Router `storage_locations`, Feed-Typ + Detailfenster,
  `storage_location_in_use`/`duplicate_storage_location`, `storage_location_references`,
  `address.of_storage`, das KI-Tool `storage_locations`, `company_settings.default_receiving_
  location_id` und `purchase_orders.receiving_location_id`.
  **Ein Standort ist nur noch ein Halter:** `LOCATION_TYPES` = **user | instance | company**
  (`company` = «im Betrieb», Adresse aus den Firmen-Stammdaten – der Ersatz für den internen
  Lagerort; ein benannter Platz/Behälter ist eine ganz normale **Instanz**). **Standortlos bleibt
  ein regulärer Zustand** (`serialization._initial_location` gibt `NULL` zurück, ausser die
  Lieferanten-Beschaffung ist der erste Schritt → Start beim **Lieferanten**).
  **Gelesen wird tolerant, geprüft nur beim Schreiben:** `location_label`/`location_labels` lösen
  einen unbekannten/veralteten Typ (Altbestand `'lagerplatz'`) zu `None` = «kein Standort» auf –
  nur `validate_location` und die Pydantic-Validatoren weisen ihn ab. Darum kann Altbestand keine
  Ansicht zerlegen (auf echtem PostgreSQL über alle Detail-/Feed-Endpunkte verifiziert).
  Zwei Stellen trugen echte Bedeutung und wurden dabei **besser**: die **Lieferadresse** für den
  Lieferanten ist jetzt die **Firmenadresse** statt einer Lagerplatz-Objektnummer (`orders._receiving_
  label`), und `logistics.target_address` hat endlich einen `company`-Zweig (vorher hätte ein
  Firmen-Ziel «Empfänger-Adresse unvollständig» ergeben). **Kern-Fix im gleichen Zug:**
  `process.return_subjects_to_stock` erkannte die Rückkehr einer Retoure an `location_type ==
  'lagerplatz'` – mit dem Wegfall des Typs hätte das **nie mehr** zugetroffen und keine Retoure
  wäre je wieder eingebucht worden; jetzt gilt «die Instanz liegt **nicht mehr beim Kunden**»
  (Kunde vom **Original-Verkauf**, da die Retoure selbst nur `kind='credit'`-Belege trägt).
  Mengeneinheiten: Stk/mm/m²/**m³**/kg/l. Den **Wareneingangs-Ort** setzt die **Bereitstellung**
  nach der abgeschlossenen Beschaffung (Ziel: die Firmenadresse, `locations.company_location`);
  der **Bewegungs**-Schritt verteilt von dort weiter.
- **Adressen: EINE Darstellung** (`services/address.py`): Person und Unternehmen
  tragen historisch **verschiedene Spaltennamen** (`address_line1`/`postal_code` an der Person
  vs. `street`+`street_nr`/`zip_code` am Unternehmen). Dieses Modul ist die eine Stelle, die
  das übersetzt – kanonische Form `{name,street1,street2,zip,city,state,country,email,phone}`
  (identisch mit dem Versand-Adress-Snapshot). `of_user(u, ship|invoice|home)` kapselt den
  **Rückfall auf die Wohnadresse** (stand vorher an jeder Aufrufstelle einzeln ausgeschrieben),
  `of_company`/`of_storage` die jeweilige Herkunft; dazu `one_line` (Anzeige), `lines`
  (Briefkopf/Etikett), `same` (normalisierter Ortsvergleich) und `iso2`. Es delegieren:
  `logistics` (`_addr_user`/`_addr_company`/`_addr_storage`/`same_place`/`iso2`),
  `document_render` (Briefkopf), `payments/stripe_provider` (Liefer-/Rechnungsadresse; die
  Stripe-Feldnamen bleiben, nur die Fallback-Logik ist zentral) und `ai/tools` (Firmen-Info).
- **Auftrag-Anlage: EINE Zeile je Position (UI-Refresh Runde 2, `order-detail.tsx`)**. Vorher zerfiel die
  Anlage in ~8 Container (Bedarf-Karte, 3 grosse Ziel-Karten, Ergebnis-Banner, Instanz-Picker-Karten,
  Ablauf) – und der **Mehrpositionen-Fall sah völlig anders aus** als der Einzel-Artikel-Fall (Ziel-Karten
  vs. Segment-Umschalter), sodass das Hinzufügen einer Position das Fenster umbaute. Jetzt: **eine Position
  = eine Zeile** (`PositionRow`) mit Artikel · Menge · **Quellen-Umschalter** und – nur bei Bedarf – der
  Instanz-Auswahl darunter; **dieselbe Zeile** für einen wie für viele Artikel (`lineSource`/`setLineSource`
  vereinheitlichen `goal` und `lineMode`). Statt Banner steht **eine Ergebniszeile** je Position («5 Stk ab
  Lager, älteste zuerst · nur 3 da – Rest per Nachschub»). Gesperrte Optionen nennen den Grund im **Hover**
  statt in der Fläche. **Wortwahl allgemein statt spezifisch:** «Herstellen / Beschaffen» → **Erzeugen**,
  «Aus dem Lager» → **Ab Lager**, «Instanz wählen» → **Auswählen**. Der Termin ist eine Zeile, kein
  Feld-Raster. `GoalCard`/`OutcomeBanner` sind entfallen. **Die Backend-Logik ist unverändert** – rein
  Präsentation (Subjektart wird weiterhin abgeleitet, nicht gewählt).
- **Code-Cleanup ERP (Juli 2026, Migration `081`)** – drei Runden, alles ohne Verhaltensänderung:
  **(1) Tote Achse Unterschrift/Foto (8 Spalten).** Beim Umbau der Datenerfassung auf frei
  konfigurierbare `capture_fields` wurden `photo`/`signature` normale **Feldtypen**; die alte
  Parallel-Mechanik blieb tot stehen: Definition (`article_process_steps.require_signature/
  signer_ids/require_photo/photo_instruction` – das Frontend setzte sie beim Anlegen hart auf
  `false` und las sie nie) und Ergebnis (`inspections.signature_url/signed_by/signed_at/photo_url`
  – **nirgends geschrieben**; gelesen wurde nur `signed_by`, das damit immer NULL war, der
  Auftrags-Embed zeigte also nie einen Unterzeichner). Dazu `article_process_steps.transport_mode`
  (trug die von `076` abgeschafften Werte + eine **zweite, veraltete** `ALLOWED_TRANSPORT_MODES` –
  zwei Wahrheiten für dieselbe Sache; ein Test prüfte ausgerechnet die veraltete) und
  `article_process_steps.locked` (Migration `079` hatte den Drop auf den Folge-Deploy vertagt).
  **(2) Überlange ERP-Kernfunktionen** auf die 80-Zeilen-Regel gebracht, entlang **fachlicher**
  Nähte statt nach Zeilenzahl: `to_order_response` 155→53 (`_fill_demand`/`_instance_embeds`/
  `_attach_step_embed`), `update_order` 123→62 (`_assert_status_transition` = die vollständige
  Zustandsmaschine, `_assert_releasable` = die drei Freigabe-Gates an EINER Stelle),
  `record_movement` 91→66, `record_scrap` 91→49 (`_scrap_one` kapselt «ganz oder Teilmenge»),
  `build_resource_embed` 86→58. *Bewusst gelassen: `render_pdf`/`run_chat`/`fulfill_intent` –
  ausserhalb des ERP-Kerns.*
  **(3) Quelltext-Guards robuster:** Tests, die eine Einzelfunktion zeilengenau prüften, prüfen
  jetzt das **Modul** – dieselbe Fachaussage, aber sie brechen nicht mehr bei jeder internen
  Umstrukturierung. Dazu drei ungenutzte Imports.
- **Bereitstellung: physische Bewegungen werden ABGELEITET, nicht geplant** (Juli 2026,
  `services/provisioning.py`, Migration `080`): Das System legt **KEINEN** Prozessschritt mehr
  an. Der Nutzer modelliert nur die **fachlichen** Schritte (kaufen, verbauen, verkaufen);
  jeder physische Transport, der daraus zwingend folgt, entsteht **zur Laufzeit**.
  **Warum die Vorgänger-Lösung falsch sein musste:** Beim Modellieren ist gar nicht
  entscheidbar, ob eine Bewegung nötig sein wird – ob die Schraube schon am Band liegt oder
  in Halle B, zeigt sich erst zur Laufzeit. Jedes vorgeplante Bewegungs-Modul rät deshalb:
  mal überflüssig (Teil liegt längst richtig), mal fehlend (Teil liegt woanders, aber niemand
  hat den Schritt eingeplant). Die gesperrten Pflicht-Bewegungen (`locked`, selbstheilend
  neu positioniert) und danach das einmalige Säen (`seed_companion_movements`) sind beide
  ersatzlos entfernt – `services/process_steps.py` gibt es nicht mehr, ebenso wenig den fest
  eingebauten Shop-Versandschritt.
  **Die vier Regeln:** (1) jeder Schritttyp deklariert in `domain/event_types.py`, **wo sein
  Material sein muss** (`provisioning`); (2) ist ein Schritt dran (oder gerade erledigt), wird
  **Ist ↔ Soll** verglichen; (3) stimmt es → **nichts passiert** (der häufigste Fall, komplett
  unsichtbar); (4) stimmt es nicht → ein **Bereitstellungs-Unter-Auftrag**
  (`orders.reason='provisioning'` + `orders.provisioning_step_id`) holt genau diese Instanzen
  an ihren Soll-Ort.
  **Warum Unter-Auftrag und nicht Schritt im Auftrag:** Ein Bewegungs-Schritt bewegt immer die
  Instanzen **seines** Auftrags (`movement.movable_instances`). Die Komponente aus Halle B
  gehört aber nicht zum Subjekt – sie ist eine Ressourcen-Zeile; der Schritt könnte sie gar
  nicht greifen. Ein Unter-Auftrag kann es, weil er ein **eigenes fixiertes Subjekt** trägt –
  exakt wie Abweichung und Retoure. Damit ist die Systematik symmetrisch: **nichts da** →
  `supply` (blockiert den Schritt) · **falscher Ort** → `provisioning` (blockiert den Schritt) ·
  **kaputt** → `deviation` (pausiert den ganzen Auftrag).
  **Der Zeitpunkt ist je Schritttyp verschieden – und muss es sein** (`_STAGE_BEFORE`):
  Ressource stellt **vor** der Ausführung bereit (die Komponente muss da sein, bevor verbaut
  wird), Beschaffung/Verkauf **danach** (die Ware kommt an bzw. geht hinaus, nachdem der
  kaufmännische Vorgang durch ist). Ohne die Trennung würde erst BESTELLTE Ware sofort in den
  Betrieb gebucht – buchhalterisch da, bevor sie geliefert ist.
  **Abstufung nach Distanz** (dieselbe Mechanik, andere Konsequenz – über die bestehende
  Adress-Klassifikation aus ADR 005, kein zweites Regelwerk): **innerhalb derselben Adresse**
  bucht der Unter-Auftrag sich sofort selbst ab (zwanzig Meter durch die Halle brauchen kein
  Formular); **über Adressgrenzen** bleibt er offen für Tarifwahl, Label und Quittierung.
  Die automatische Buchung ist eine **Behauptung**, keine Beobachtung – das Audit-Log hält sie
  ausdrücklich als «systemseitig zugewiesen, nicht quittiert» fest.
  **Zwei Fallstricke, beide getestet:** (a) Die Bereitstellung hängt `subject_of_order_id`
  **nicht** um (nur `record_link`) – sonst verlöre der Eltern-Auftrag sein Subjekt; (b) zum
  Kunden gehen **nur `sold`-Instanzen** über die VOLLE Instanzliste (`order_instances`), denn
  `sold` ist terminal und `order_active_instances` blendet es aus – über die aktive Liste
  hätte der Kundenversand nie ausgelöst, und eine teilverkaufte Charge wäre als Ganzes zum
  Kunden gewandert. Wächter: `test_smoke.py: test_system_never_plans_process_steps`,
  `…_keeps_parent_subject_binding`, `…_timing_differs_by_step_type`,
  `…_to_customer_only_moves_sold_units`, `…_sub_order_buckets_are_explicit_per_reason`.
  *Alt-Bestand:* früher gesäte Begleit-Bewegungen (`article_process_steps.companion`) bleiben
  gültige Schritte und behalten ihre Fachwirkung (`provisioning.is_companion`: festes Ziel
  «Kunde», Ausnahme von der Fehlmengen-Prüfung); nie ausgeführte werden von Migration `080`
  deaktiviert.
- **Standort-Kette «wo genau?»** (`locations.location_chain`, `InstanceResponse.location_path`):
  liefert den vollen Pfad von innen nach aussen – Instanz → Behälter → Unternehmen → **Anschrift**
  (`location_type='address'`, ohne Objektnummer). Zyklensicher, auf 10 Stationen begrenzt, und
  bewusst **nur im Instanz-Detail** gefüllt (ein Datensatz, ≤10 Auflösungen) – Feeds bleiben bei
  den Batch-Labels. Frontend: `components/erp/location-path.tsx` rendert sie als eingerückte
  Kette im bestehenden Karten-Design (Stationen klickbar, die Anschrift nicht – sie ist kein
  Datensatz). **Die Kette startet beim unmittelbaren Halter, NICHT bei der Instanz selbst** (die
  ist ja schon geöffnet – die frühere «Diese Instanz»-Zeile ist entfernt) und ist die **einzige**
  Standort-Anzeige im Instanz-Detail: die frühere zusätzliche «Standort»-Kachel im Glance-Grid ist
  entfallen. Sie rendert jetzt auch bei nur EINEM Halter bzw. «Nicht festgelegt» (kein
  Verschachtelungs-Schwellenwert mehr); bei einer verteilten Charge weist sie auf die
  Aufteilung darunter (`InstanceLocationsCard`) hin.
  **Die Kette ist Dekoration, nie der Datensatz** (`routers/instances.safe_location_path`):
  scheitert ihre Auflösung (Altdaten, gelöschter Halter), kostet das die Kette – die Instanz
  bleibt lesbar, der echte Fehler geht mit Objektnummer ins Log; das Frontend verwirft
  unbrauchbare Stationen still.
- **Wächter gegen `NameError` im Backend** (`tests/test_no_undefined_names.py`): ein im
  Funktionsrumpf benutzter, aber nie importierter Name ist in Python **kein** Import- oder
  Syntaxfehler – er fliegt erst, wenn genau dieser Pfad läuft. Genau so kam `LocationHop` in
  `routers/instances.py` durch alle Netze (Tests, `dump_openapi`, Deploy, App-Start alle grün)
  und liess trotzdem **jeden** Aufruf von `GET /erp/instances/{id}` mit 500 auflaufen. Der Test
  prüft über `symtable` (stdlib) je Modul, dass jeder als **global** aufgelöste Name nach dem
  Import wirklich existiert – und dass **jedes** Modul unter `app/` importierbar ist. Das ist
  die Python-Entsprechung zu ESLint, die im Backend gefehlt hat. Gemeldet wird nur, was
  **gelesen und nirgends gebunden** ist: Python 3.12 inlinet Comprehensions (PEP 709), womit
  `[k for k, m in KATALOG]` auf Modulebene `k`/`m` in die Symboltabelle legt, obwohl sie nie
  Modul-Attribut werden – gebunden und darum harmlos (CI läuft 3.12, lokal 3.11; die Regel ist
  über 3.11/3.12/3.13 gegengeprüft). Ein **Selbsttest** hält den Wächter scharf: er muss die
  Bug-Form melden und die Comprehension-Form durchlassen – ein Wächter, der nie anschlägt, ist
  von einem kaputten nicht zu unterscheiden.
- **Verbauen setzt den Standort über die EINE Schreibstelle** (`resource._relocate` →
  `location_split.set_single`): eine Komponente wandert beim Einbau auf die Produkt-Instanz
  (und damit über die Kette physisch mit ihr mit). Vorher wurde `location_type`/`location_id`
  direkt zugewiesen – eine zuvor auf mehrere Standorte **verteilte Charge behielt dabei ihre
  veraltete `locations`-Map** und galt gleichzeitig als verbaut UND anteilig woanders liegend.
- **Generischer Rückverweis «wer zeigt auf mich» je Objektnummer** (`services/references.object_references`,
  `GET /erp/objects/{id}/references`): was aktuell an einer Objektnummer **verortet** ist (`instances.
  location_id == id`, ohne Typ-Filter – Objektnummern sind global eindeutig) + referenzierende
  Prozessschritte. Reiter **«Verwendung»** generisch an Benutzer/Instanz (Frontend
  `components/erp/object-references.tsx`); `storage_location_references` delegiert darauf. AGB/Datenschutz-
  Artikelnummer wird auch **am ERP-Unternehmens-Datensatz** gepflegt (`organization-detail`, Sektion
  «AGB & Datenschutz»), nicht nur Admin → Einstellungen.
- **Consent-Gate: versionierte Bestätigung von Pflichtdokumenten** (`services/consent.py`,
  `routers/consent.py`, `models/document_acknowledgement.py`, Migration 064): Bestätigungspflichtige
  Dokumente sind **hart verdrahtet** (`consent.MUST_ACKNOWLEDGE_KINDS = ("agb",)`) – **kein Admin-Häkchen**,
  gilt für **jede** angemeldete Rolle (Mitarbeiter, **Lieferant**, Kunde, Admin; Endpunkte an
  `get_current_user`). Verlangt wird eine Art nur, wenn tatsächlich ein Dokument auflösbar ist. Die
  **Version** ist die Objektnummer der gültigen Dokument-Instanz (`legal.resolve` folgt der Artikel-/
  `replaced_by_id`-Kette). Wer welche Version wann bestätigt hat, liegt append-only in
  `document_acknowledgements` (Nachweis CH DSG/DSGVO; AGB spiegelt weiterhin `terms_accepted_at`). Am
  **Benutzer-ERP-Datensatz** wird der Nachweis gezeigt («AGB akzeptiert am … · Stand <Objektnr>»,
  `GET /consent/acknowledgements/{user_object_id}`). `GET /consent/pending` liefert offene Bestätigungen,
  `POST /consent/acknowledge` quittiert. Frontend: **blockierendes Modal** `components/consent/consent-
  gate.tsx` (in ERP-, Konto- und Public/Shop-Layout gemountet, self-contained via `onAuthChange`) – zeigt
  je ein Dokument mit «gelesen + akzeptieren», bis nichts mehr offen ist. **Serverseitig erzwungen**
  (`consent.assert_acknowledged`, 403) an den kritischen Aktionen: Shop-Checkout, Retoure-Anfrage,
  Lieferanten-Offerte (`PATCH …/purchase`, nur Rolle supplier) – das Modal ist kein reines UI-Gate mehr.
  *(Die nie ausgewertete Spalte `legal_ack_config` ist entfernt (Migration 075); Rollen-Feinsteuerung
  läuft über das Dokument-Publikum `doc_audience`.)*
- **Artikelnamen (frei + intelligente Vorschläge, KI-unabhängig)**: Namen sind **frei wählbar**
  (kein Katalog-Zwang mehr), aber auf **`NAME_MAX_LENGTH=32` Zeichen** gekappt (zentral in
  `schemas/article.py: clean_article_name`, Frontend `maxLength`). Beim Tippen schlägt das System
  **bereits verwendete oder ähnliche** Namen vor, um Dubletten zu vermeiden – **ohne KI/Kosten**,
  rein lexikalisch (Trigramm-Jaccard + Substring-/Wortstamm-Bonus, `services/article_names.py`,
  erkennt gemeinsame Stämme wie «schraub» → «Akkuschrauber»/«Schraubendreher»). Endpoint
  `GET /erp/articles/name-suggestions?q=…` (`ArticleNameSuggestion{name,count,score}`); Frontend
  `NameField` (Freitext + Vorschlags-Dropdown, Dubletten-Hinweis). Der frühere Admin-Katalog
  `company_settings.article_names` ist **vollständig entfernt** (Modell/Schema/API + Admin-UI) –
  Vorschläge stammen ausschliesslich aus echten Artikelnamen.
- **Optionale Artikel-Stammdaten** (dynamische Feldliste, nur bei Bedarf): `material`, `cad_url`
  (CAD-Link), `surface` (Oberfläche), `min_order_qty` (MOQ), `safety_stock` (Sicherheitsbestand).
  Im Spezifikation-Reiter über «+ Feld hinzufügen» einblendbar; nur befüllte Felder werden
  gespeichert/angezeigt. *Der frühere **«Fixierte Standort»** (`fixed_location_*` + `MapPicker`,
  Migration 069) ist mit Migration `088` **ersatzlos entfallen** (Notiz #168): er trug einen
  GPS-Punkt samt reverse-geocodierter Adresse, war aber rein deskriptiv – kein Bestands-Standort,
  keine Logik. Ein Artikel ist eine **Gattung**; einen Ort hat immer nur die **Instanz**
  (`instances.location_*` + `locations.location_chain`). Die Angabe war damit eine zweite,
  konkurrierende Antwort auf «wo ist das?» – und die schwächere.*
- **Durchlaufzeit** je Artikel (read-only, analog Preisspanne): kürzeste–längste Zeit zwischen Freigabe
  (`orders.released_at`) und Abschluss (`orders.completed_at`) über erledigte Aufträge
  (`ArticleResponse.lead_time_days_low/high`, berechnet in `routers/articles.py`).
- **Abweichung (vereinheitlicht Abbruch-Folgeauftrag / Fehler / Reklamation / Nacharbeit)**: KEIN eigener
  Datentyp – eine Abweichung ist ein **Unter-Auftrag** (`orders.parent_order_id`), der aus einem laufenden
  Eltern-Auftrag heraus entsteht und auf dessen Instanzen wirkt – OHNE Lager-FIFO/-Reservierung (die
  Instanzen sind bereits in Arbeit/im Besitz). Der Eltern-Auftrag **pausiert** (`process._is_paused_by_
  deviation`), solange eine Abweichung offen ist. `services/deviation.py`; Endpoint `POST /orders/{id}/
  deviation` («Abweichung melden», am Auftrag- und Instanz-Detail). **Auto-Trigger**: fehlgeschlagene
  Datenerfassung legt automatisch eine Abweichung auf die Durchfaller-Instanzen an (idempotent,
  `auto_deviation_from_inspection`). Der frühere eigenständige `Claim`-Typ ist **vollständig entfernt**
  (Migration 037 droppt `claims`).
  - **Abbruch ist ein Antrag, kein Vollzug (reversibel)**: «Abbrechen» (`POST /orders/{id}/abort`) setzt
    einen freigegebenen Auftrag NICHT direkt inaktiv, sondern erzeugt einen Folgeauftrag (Entwurf,
    `abort_into_id`) und **pausiert** das Original. Erst die **Freigabe** des Folgeauftrags vollzieht den
    Abbruch (`apply_abort_on_release`, `keep_instances=True`) – keine herrenlosen Teile. Bis dahin zwei Wege
    über DENSELBEN Mechanismus: Folgeauftrag **freigeben** (Schritt einlagern/verschrotten/nacharbeiten =
    Auflösung) ODER **«Abbruch zurücknehmen»** (`deviation.revoke`, `POST /orders/{id}/revoke`) → Original
    läuft **unverändert** weiter (ein Entwurf hat die Reservierungen nie gelöst). „Weitermachen" ist KEIN
    eigener Schritttyp, sondern das Zurücknehmen des Abbruchs. Ein Entwurf ohne Instanzen wird direkt inaktiv.
  - **Verschrotten** (`scrap`, Schritttyp, Migration 038, `services/scrap.py`): die definierte Auflösung
    einer Abweichung – gewählte Instanzen → `disposition='scrapped'` (Bestandsabgang, DECREASE/INSTANCE in
    der Registry); Abschluss-Marker `disposals` (keine eigene Nummer). Nur im **Auftrags-Ablauf** zulässig
    (nicht im Artikel-Prozess). Durchfaller sind im Panel vorausgewählt. **«Ersatz»** = Komposition aus
    `scrap` (defektes Teil raus) + Beschaffung/Bestand (neues herein) – kein monolithischer Schritt.
    **Ausschuss ist STANDORTLOS (Migration 070, kehrt 068 um):** die GANZ verschrottete Instanz verliert
    beim Verschrotten ihren Standort (`location_split.clear` in `services/scrap.py`) – ein Standort ist immer
    ein realer **Halter** (Person/Instanz/Unternehmen), den Ausschuss nicht mehr hat; der Endzustand
    `disposition='scrapped'` IST die «Wo»-Aussage. So findet «wer liegt hier» (`references`) ein
    verschrottetes Teil korrekt nicht mehr. **Kein Schrottplatz-Lagerort mehr** (`provisioning.
    send_to_scrapyard`/`resolve_scrap_location` + `company_settings.default_scrap_location_id` entfernt).
    Teil-Verschrottung lässt die gute Restmenge am Lager (Standort bleibt).
- **Bereitstellungsort — «Bewegung wird ABGELEITET, nicht orchestriert»** (`domain/event_types.py`
  `provisioning`, `services/provisioning.py`): jeder Schritttyp DEKLARIERT seinen Bereitstellungsort (wohin
  sein Subjekt/seine Inputs physisch müssen) — Beschaffung→Wareneingang, Verkauf→Kunde, Ressource→Produkt-
  Instanz/Arbeitsplatz, **Verschrotten→standortlos** (`PROV_NOWHERE`, kein Halter mehr),
  Datenerfassung/Bewegung/Dokument→kein fester Ort. Der
  EINE Reconciler `provisioning.reconcile_to(inst, typ, id)` vergleicht Ist↔Soll und bringt die **ganze**
  Instanz ans Ziel — **no-op, wenn schon da**; Teilmengen/Chargen laufen weiter auftragsgetrieben über den
  Bewegungs-Schritt (`location_split.move`). **Verschrotten** hat KEINEN Bereitstellungsort
  (`PROV_NOWHERE`): die Instanz wird standortlos (`location_split.clear`), kein Schrottplatz-Reconcile mehr.
  **Die Deklaration ist jetzt wirksam** (Juli 2026): `provisioning.target_for` löst sie in eine konkrete
  Objektnummer auf, und `ensure_provisioning` (aufgerufen aus `process.recompute_completion`, also nach
  JEDEM Schritt-Abschluss) legt bei Abweichung Ist↔Soll einen **Bereitstellungs-Unter-Auftrag** an – siehe
  «Bereitstellung» oben. Zuvor war der Eintrag reine Beschriftung: `reconcile_to` hatte genau EINEN
  Aufrufer (`resource._use_tool`). *Rückführung/WIP-Puffer/Werkzeug-Rückgabe/mehrstufige Montage sind über
  denselben Mechanismus abbildbar; scan-Quittierung im Verschrotten bleibt Backlog. Ortsfeste
  Betriebsmittel (das Produkt muss zur Maschine, nicht umgekehrt) sind bewusst NOCH NICHT gebaut.*
- **Logistik/Versand — «Versand wird ABGELEITET, nicht bestellt» (ADR 005, `docs/adr/005-logistik.md`,
  Migrationen `071`+`072`)**: der Bewegungs-Schritt kennt Quelle+Ziel → EINE Klassifikation
  (`services/logistics.classify_movement`) leitet die Transportklasse **adress-basiert, OHNE Geofence** ab
  (bewusst einfach: «von A nach B mit anderer Adresse → Versand, sonst intern»): **externe Person**
  (Kunde/Lieferant per Rolle) als Ziel → extern/outbound bzw. als Quelle → extern/inbound (**Abholung
  Lieferant / Kunden-Retoure = DIESELBE Engine**); **Ziel ohne Standort/Adresse → innerbetrieblich**; zwei
  **interne** Orte → Versand NUR bei belegten, **unterschiedlichen** Adressen (Mehr-Standort). Instanz-Ziele
  über die physische Kette (`resolve_physical_location`); `location_kind` (Ownership) + `same_place`
  (normalisierter Adressvergleich) sind die Bausteine. **Transport = EINE Wahl mit drei Optionen**
  `transport_mode` ∈ **internal** (innerbetrieblich, kein Carrier – Vollzug per Scan) | **parcel** (Paket) |
  **freight** (Stückgut/Palette): `logistics.recommend_mode` leitet aus Transportklasse + geschätzter Last
  die **Empfehlung** ab (vorgewählte Default-Auswahl, IMMER frei übersteuerbar am Beleg
  `shipments.transport_mode`). Die frühere **Doppelung Modus×Sendungsart** und die Werte
  `auto/carrier/self/none` sind **entfernt** (Migration `076`); die interne `kind`-Spalte (parcel|freight)
  spiegelt nur noch den Modus (freight ⟺ 'freight'). Der Artikel-Prozess wird nie mutiert; die Alt-Spalte
  `article_process_steps.transport_mode` ist **entfernt** (Migration `081`) – sie trug noch die von `076`
  abgeschafften Werte und eine zweite, veraltete Whitelist. Digitale Payloads = KEIN Fall.
  **Versand-Beleg `shipments`** (Fachzeile je Bewegungs-Schritt, KEINE eigene Nummer): Adress-Snapshots
  (Firma ↔ Ziel-Person/-Halter, Länder → ISO-2), **Paket-Schätzung aus Artikel-Daten** (Gewicht×Menge,
  Grösse mm→cm, Fallback-Karton), Gefahrgut-Warnung (`articles.is_hazmat`, optionales Spez-Feld «Gefahrgut»),
  Rate-Snapshot, Label, Tracking, Kosten; Status draft→quoted→purchased→done. **Carrier-Aggregator = Shippo**
  hinter dem Gateway-Muster (`services/shipping/`: base/shippo/manual, exakt wie payments): aktiviert sich
  selbst über `SHIPPO_API_KEY` (Self-Serve wie Stripe, Pay-per-Label; rechnet nativ cm/kg, Rates inline am
  Shipment, Kauf via `/transactions/`); ohne Key läuft `manual` (Carrier/Tracking von Hand – nie kaputt).
  Anbieter jederzeit austauschbar (EasyPost/Sendcloud = Drop-in-Adapter). **Best-Offer: günstigster =
  Default-Auswahl, Schnellster als Hinweis** (`logistics.quote` markiert cheapest/fastest). Endpunkte am
  Auftrag: `POST …/shipment/quote|buy`, `PATCH …/shipment`; Embed fährt im Bewegungs-Embed mit
  (`MovementEmbed.shipment`, Versand-Box im `movement-panel.tsx`: **3-Wege-Umschalter Im Betrieb | Paket |
  Fracht** mit markierter Empfehlung, Extern-/Gefahrgut-Chip, Tarifliste, Label-PDF, manuelle Erfassung;
  bei «Im Betrieb» keine Carrier-Maschinerie – nur Scan-Hinweis). `record_movement` schliesst den Beleg
  (purchased→done) und übernimmt
  Tracking – **der physische Vollzug bleibt scan-quittiert**. *Bewusst NICHT gebaut: Tracking-Webhooks,
  Carrier-Pickup-Orders, Multi-Parcel, Zoll-Dokumente, Versandkosten-Weiterverrechnung.*
- **Adress-Autofill (Google Places) + verschrottet = standortlos**: alle editierbaren Adressfelder nutzen
  Google-Places-Autovervollständigung (`components/erp/address-autocomplete.tsx` + `use-maps-key.ts`;
  Loader mit `libraries=places`) – Strasse tippen, Vorschlag wählen → Strasse/PLZ/Ort/Land (+Koordinaten)
  automatisch. Verdrahtet in Profil-Adresse/Rechnungsadresse und Unternehmens-Stammdaten. **Bugfix:** eine **verschrottete** Instanz zählt NIE mehr als
  «liegt hier» (`references.object_references` filtert `disposition != 'scrapped'`; Migration `072` nullt den
  Alt-Standort bereits verschrotteter Instanzen).
  - **Unterdeckung → EINE Formel & zwei Deckungs-Wege für ALLE Auftragsarten** (`services/recovery.py`,
    `process._subject_shortfalls`): Kann ein Auftrag sein Soll nicht (mehr) erfüllen – weil eine reservierte
    Instanz **ausgesteuert** wurde (Abweichung verschrottet ein verkauftes/reserviertes Teil) ODER weil ein
    **Erzeugungsauftrag Ausschuss** hatte –, wird die Fehlmenge **ehrlich** sichtbar. **Kein `subject_kind`-
    Sonderpfad mehr:** `_subject_shortfalls` = **Soll − Gesichert** über ALLE Arten. *Gesichert* = für den
    Auftrag **reservierte** Bestands-Instanzen (FIFO/gepinnt/gepeggter Nachschub) **plus selbst erzeugte
    gute** Instanzen; terminal verlorene (verschrottet/verkauft/verbaut) oder durchgefallene zählen nicht.
    So reagiert ein **Erzeugungsauftrag auf Ausschuss identisch** wie ein Bestands-Auftrag auf eine
    ausgesteuerte Reservierung (nur die **Abweichung** ist ausgenommen – ihr Subjekt sind fixierte
    Instanzen). **Core-Fix dazu:** `scrap.record_scrap` löst beim Verschrotten **ALLE** Reservierungen der
    Instanz (`reservation.release_all`) – ein verschrottetes Teil verlässt den Bestand endgültig und kann
    keinen Auftrag mehr beliefern. Der betroffene **Subjekt-Schritt wird «blockiert»** (abgeleitet, kein
    stilles Unterliefern). Personal hat am freigegebenen Auftrag **zwei Wege** (statt vier – „Mensch
    entscheidet"): (1) **Nachschub anlegen** – produzieren/beschaffen (`POST /supply`, ein Unter-Auftrag);
    (2) **Aus Lager decken** – freien Bestand **FIFO** reservieren (`POST /cover-stock` ohne ids), mit
    **Unterkategorie «bestimmte Instanz wählen»** (`POST /cover-stock` mit ids, inline-Picker) –
    `recovery.cover_from_stock`. `StepShortfall` trägt dafür die **Verfügbarkeit** (`available_quantity`/
    `available_instances`) aus freiem Lagerbestand; `_peg_supply_to_parent` erkennt das Subjekt eines
    Erzeugungsauftrags EBENSO wie eines Bestands-Verkaufs (kein Stock-Gate). Nur bei **Subjekt-Schritten**
    (movement/inspection/scrap/sale) – ein reiner Komponenten-Bedarf (Ressource) wird weiterhin über
    Nachschub gedeckt. **«Menge reduzieren» ist bewusst NICHT gebaut:** eine bezahlte Position wird erst
    reduziert, wenn sie zugleich sauber (Stripe) **gutgeschrieben** wird – kommt gebündelt mit der
    Gutschrift-Funktion (TODO), nicht als isolierte Mengen-Kürzung.
  - **EINE On-Hold-Sprache «Prozess angehalten»** (`order-detail.tsx: ProcessHoldNotice`, ersetzt
    `BlockedStepNotice`): Beide Gründe, warum ein Auftrag nicht weiterläuft, teilen sich EIN Muster (gleiche
    Optik wie die Pause-Leiste, `PauseCircle`/amber): (a) **Angehalten – Abweichung offen**
    (`record.paused`): der GANZE Auftrag ruht, solange eine Abweichung offen ist; die Notiz verlinkt die zu
    klärende Abweichung, KEIN interaktives Panel; (b) **Angehalten – Unterdeckung** (`step.state ===
    'blocked'`): nur der betroffene Schritt ruht, mit den zwei Deckungs-Wegen. **Pause blockiert die
    Schritt-Ausführung jetzt auch im UI:** bei `record.paused` wird kein interaktives Panel gerendert (das
    Backend lehnte die Ausführung schon immer via `_assert_not_paused` an ALLEN sechs Schritt-Endpunkten
    mit 409 ab – die Lücke war rein visuell). Ganz-Auftrag-Pause ist fachlich korrekt: eine Sendung mit
    offener Abweichung darf nicht teil-versendet werden, bevor klar ist, ob ein Stück ausgesteuert wird.
  - **Praxistest-Nachbesserungen (Runde 2)**: (1) **«Verkauf» ist ein Subjekt-Schritt**
    (`process.SUBJECT_STEP_TYPES`) – ein Verkaufsauftrag blockiert jetzt bei Unterdeckung (vorher traf
    `sale` weder Subjekt- noch Komponenten-Zweig → reagierte NICHT, wenn sein Bestand per Abweichung
    ausgesteuert wurde). (2) **Verkaufspreis zieht nachträglich nach**: wird der (Einmalkauf-)Preis erst
    NACH der Freigabe am Artikel hinterlegt, zeigt das Sale-Embed den ableitbaren Betrag (Panel nicht mehr
    blockiert) und die Bestätigung holt ihn frisch (`sale._apply_transition` → `_prefill_price`) – sonst
    blieb ein Mehrpositionen-Verkauf ohne editierbaren Betrag stecken. (3) **Charge teilverschrotten**
    (`ScrapUpdate.items` mit `quantity`, `reservation.reduce_quantity`): analog zur Ressourcen-Teilentnahme
    sinkt nur die Menge (keine Teilung/neue Nummer); überschüssige Reservierungen werden getrimmt (Recovery).
    (4) **Mehrpositionen-Auftrag: je Position FIFO ODER Instanz wählen** (nicht mehr global) – segmentierter
    Umschalter je Position (`order-detail.tsx: lineMode`/`PinPicker`/`SegBtn`); ein Auftrag mischt Positionen
    frei. (5) **Position löschen faltet auf Einzel-Artikel zurück**: sinkt ein Mehrpositionen-Auftrag auf
    EINE Position, wird `article_id`/`quantity` zurückgesetzt (`orders.remove_order_line`) – die Ziel-Karten
    aktualisieren sich (Herstellen wieder möglich). (6) **Bewegen-Scan wartet auf die Zielort-Listen**: der
    freie Zielort-Scan wird erst freigegeben, wenn Lagerplätze/Personen/Instanzen geladen sind
    (`movement-panel.tsx: scanReady`) – vorher konnte der letzte Scan-Schritt ohne Kandidaten „nichts
    anzeigen", bis man ihn per Einzel-Scan erneut auslöste.
- **ERP-UX-Konventionen**: Detailfenster speichern per **Auto-Save** (debounced, Enter löst sofort aus,
  grüner Rahmen-Flash; kein Speichern-Knopf – `lib/use-autosave.ts`). Referenz-Auswahlfelder sind
  durchsuchbar (`SearchSelect`, Suche auch per Objektnummer-Teilstring). Referenzierte **Objektnummern
  sind klickbar** und öffnen den Datensatz (`components/erp/obj-id.tsx` + `ErpNavContext`). Artikel ohne
  Prozessschritt sind **nicht freigebbar**. Auftrag-Stepper zeigt beim Hover Wer/Wann je erledigtem
  Schritt; Instanzen haben einen Reiter **Verwendung** (Verwendungsnachweise, neu→alt).
- **Design-Sprache (DAU-tauglich, «Symbole statt Text, Farbe = Bedeutung»)**: Status-Badges sind
  einheitlich **Symbol + semantische Farbe + Label** (`StatusCfg` mit `icon` in den `lib/*`-Status-
  Configs; `StatusBadge` rendert sie als Pille – Feed & Detail-Köpfe). **Ampel-Semantik (nur
  grün/gelb/rot, kein Blau/Petrol/Violett/Slate mehr):** GELB (`--warning`) = offen/in Arbeit/wartend
  (Entwurf, **In Arbeit**, Angefragt/Offeriert/Bestellt, Bestätigt/Verrechnet, Reserviert);
  GRÜN (`--success`) = gut/erledigt/frei (Freigegeben, Abgeschlossen, Geliefert, Bezahlt, am Lager,
  Verkauft, Verbaut); ROT (`--danger`) = Problem/Stopp/tot (Fehler, Abgelehnt, Storniert, **Inaktiv,
  Verschrottet**). Alles läuft über die drei `TONE`-Töne (`lib/status-flow.ts`); Rollen-Badges sind
  bewusst **neutral** (Identität, keine Ampelfarbe). Der Prozess-Stepper
  zeigt **Schritt-Symbole** statt Zahlen. Aktive Prozessschritte haben **eine** grosse, touch-taugliche
  Hauptaktion (`PrimaryButton`, ≥44 px, volle Breite) – «Was muss ich jetzt tun?» auf einen Blick.
  **Gemeinsames UI-Vokabular (`components/erp/fields.tsx`) – konsequent verwenden statt Eigenbau:**
  `Tooltip`/`InfoHint` (Erklärungen/Infotexte gehören in den **Hover**, ⓘ-Symbol – nicht in die
  Fläche), `TileShell`/`TILE` (Kachel-Grundform der Detail-Ansichten: Symbol-Kasten + Versalien-
  Label + Inhalt; jede Kachel trägt ihre eigene Haarlinie und steht in Weissraum – **kein**
  durchgefärbtes Raster, sonst erscheint eine unvollständige letzte Reihe als grauer Block),
  `SectionTitle` (Symbol + Versalien-Label + optional ⓘ + rechter Slot), `PanelHeader`
  (einheitlicher Prozessschritt-Kopf: getöntes Symbol + Titel + ⓘ + rechter Slot/Status – EIN Look
  über ALLE Schritt-Panels), `StatusBadge`, `PrimaryButton`. Leitsatz: «weniger ist mehr» – Symbole
  statt Text, Infotexte in den Hover, sofort erkennbar was Sache ist / was zu tun ist.
- **Bruchmengen (kg · m² · m³ · l, nicht nur ganze Stück)**: alle Mengen sind `Decimal`
  (DB `NUMERIC(14,3)`, Migration `055`): `instances.quantity/reserved_quantity`,
  `orders.quantity`, `order_lines.quantity`, `purchase_orders.quantity`, `sales.quantity`. Die
  **EINE** Mengen-Stelle `services/quantity.py` (`to_qty`/`qty_sum`/`is_whole`) kapselt
  Umwandlung/Rundung – Bestand/FIFO/Reservierung (`inventory`/`reservation`/`subject`/`process`/
  `resource`/`recovery`/`scrap`) rechnen exakt (kein `float`). Die Reservierungs-Map
  (`instances.reservations`) speichert Mengen als **String** (JSON-sicher); `events.emit`
  serialisiert `Decimal`→`float` für den Event-Strom. Am API-Rand sind Mengen `float` (TS
  `number` – Frontend unverändert). **Einzelteil-Artikel (`serialization='unit'`) dürfen nur
  GANZE Stück** (2.5 Schrauben gibt es nicht – Router-Check gegen die Serialisierung); **Chargen
  (`batch`) tragen Bruchmengen** (2.5 kg). Stichprobe: `required_sample` liefert ganze Proben
  (`ceil`, auch für 2.5 kg). Frontend-Inputs (Menge/Ressourcen-Zeile/Teil-Verschrottung)
  akzeptieren Nachkommastellen (kein `Math.trunc` mehr). *Shop-Kauf bleibt ganzzahlig (Stückzahl).*
- **Performance/Infra** (siehe `docs/architecture-review-2026-06.md`): Objektnummern über die
  Postgres-Sequence `object_id_seq` (race-sicher, `services/objects.py`). Auftrags-Feed `GET /orders`
  liefert schlanke `OrderSummary` (ohne Embeds); das Detail kommt **on-demand** via `getOrder(id)`.
  **Domain-Event-Strom** (Outbox) `events` + `GET /api/v1/events?after_id=…` für KI/Automatisierung
  (`services/events.py`). Schema-Management via Alembic (`start.sh`), Lifespan-Safety-Nets als Fallback.
- **QR-Code / Kamera-Scan (zentral, Frontend-only)**: die universelle Objektnummer ist der einzige
  Code-Inhalt. `lib/scan.ts` (`encodeObjectCode`/`parseScannedCode` – tolerant ggü. nackter Nummer &
  URL/Deep-Link; `validateForStep`). Zentraler Scanner: `ScanProvider` + `useScan({ title, steps,
  onComplete })` mountet EINE Dialog-Instanz am ERP-Layout. `ScanDialog` ist **Kamera-first**
  (ZXing `BrowserMultiFormatReader` – **alle** Code-Arten, lazy geladen) mit **sofort sichtbarer**
  manueller **semantischer Suche** (z. B. «003» → 100000003). Ein Scan-Vorgang ist eine **Sequenz**
  von Schritten (`steps`): je Schritt `expected` (Verifikation, grün/rot, Kamera läuft weiter) oder
  `restrict`+`candidates` (Lookup; Code ausserhalb des ERP → Fehlermeldung). **Prozess-Quittierung
  per Scan ist verbindlich:** Bewegung (aktueller Standort → Instanz → Zielstandort), Ressource
  (Produkt-Instanz → Komponente; Betriebsmittel), Datenerfassung (Instanz vor Erfassung).
  Etikettendruck via `ObjectLabel` (`qrcode.react`) an der Instanz; Feed-Button «Scannen»
  öffnet den Datensatz. Kein Backend nötig (Objektnummer = Schlüssel, Feed kennt alle IDs).
- **Verkauf / Shop (MVP, am Artikel – kein eigenes «Angebot»-Objekt)**: Der Verkauf ist eine dritte,
  bewusst **lebende** Ebene am Artikel (analog `landed_unit_cost`): `articles.sales_published/
  sales_visibility/sales_content` + 1:n `article_prices` (mutabel, Soft-Delete) + `article_sales_audience`
  (private/unlisted). Die **Freigabe friert NUR Spezifikation + Prozess** ein – die Verkaufs-Ebene bleibt
  in jedem Status editierbar (eigene Endpunkte `…/articles/{id}/sales[/prices|/audience]`, alles geloggt).
  **Du pflegst NUR den Basispreis in CHF** (genau eine Zahl je Preis); alles andere wird abgeleitet.
  **Zwei unabhängige Achsen:** *Preismodell* (`article_prices.kind` = Einmalkauf | Abo → `orders.recurrence_*`)
  und *Verfügbarkeit* (`articles.sales_fulfillment`, jetzt **1-Bit-Backorder-Policy**): **make** = bei
  Mangel **Nachschub** (Made-to-Order) | **stock** = nur ab Lager FIFO (limitierte Auflage, kein
  Überverkauf). Der Verkauf ist IMMER ein stock/FIFO-Auftrag; was an Bestand fehlt, deckt ein
  **Nachschub-Unter-Auftrag** (ADR 003, siehe unten) – KEIN `subject_source` mehr.
  **Preis-Pipeline** (`services/pricing.py`, gestaffelt, jede Stufe optional): Basis-CHF → ① Kunden-/
  Gruppenpreis (Hook) → ② Zonen-/Kaufkraft-Faktor (PPP, `company_settings.pricing_zone_factors`, Default aus)
  → ③ Rabatt (Vergleichspreis visuell; Coupons = Erweiterung) → **Netto-CHF** → ④ Währung: **gepinnter** Kurs
  (`article_prices.pinned`, `charm_round`, **stabil bis Basis-Änderung oder >3 % Kurs-Drift** – KEINE
  Live-Umrechnung) → ⑤ MWST (`services/tax.py`, CH 8.1/2.6/3.8, Ausland 0 %). Tageskurse unveränderlich in
  `fx_rates` (Env `FX_SOURCE_URL`). **Kauf = ganz normaler Auftrag** mit `sale`-Schritt + `movement`
  (Versand); **Defer-Modell**: der Auftrag wird **erst bei bestätigter Zahlung freigegeben** (make erzeugt
  dann die Instanzen; stock reserviert schon bei Bestellung). Preis/Währung/Steuer werden auf den
  `sale`-Beleg **eingefroren** (Snapshot).
  **Zahlung – Stripe (Vollintegration, `services/payments/`)**: hosted **Checkout Session** (Redirect) für
  Einmalkauf (`mode=payment`) und Abo (`mode=subscription`). **Adaptive Pricing** (kein Währungsumschalter –
  Stripe zeigt die Lokalwährung an der Kasse; Website zeigt CHF) + **Stripe Tax** (`automatic_tax`,
  `tax_behavior=inclusive`). Stripe ist **Quelle der Wahrheit**: Webhook (signaturgeprüft) `checkout.session.
  completed` → Verkauf `paid`, Auftrag freigegeben, **realer Betrag/Lokalwährung/Steuer** als Snapshot
  (`sales.stripe_snapshot/stripe_payment_intent_id`, `orders.stripe_subscription_id`, `user_profiles.
  stripe_customer_id`). **Customer Portal** (Abo/Zahlungsmittel selbst verwalten) via `POST /shop/portal`.
  Provider-Auswahl automatisch `stripe`, sobald `STRIPE_SECRET_KEY` gesetzt ist; sonst `manual` (Fallback,
  `/shop/pay?token=…` + `/shop/payments/simulate`). Setup: `docs/stripe-setup.md`. **Shop** (öffentlich):
  `GET /shop/products|products/{id}` (public für alle, private nur zugewiesene Kunden, unlisted nur per Link;
  **kanonisiert über `replaced_by_id`** – ein ersetzter Artikel zeigt nahtlos auf den Nachfolger, URL/Listing
  brechen nicht), `POST /shop/checkout` (Login-Pflicht, kein Gast-Checkout). Frontend: ERP-Reiter **Verkauf**
  am Artikel (Autosave, Preise/Inhalt de+en/Zielgruppe/Verfügbarkeit/CHF-Vorschau) + Admin-Shop-Konfig
  (Provider/Zonen) + öffentlicher Shop (`/shop`, `/shop/product`, `/shop/cart`, `/shop/checkout`, `/shop/pay` für manual).
  **Ersetzen** kopiert das Verkaufs-Profil auf den Nachfolger. *Bewusst NICHT gebaut: Coupon-Engine,
  Bundles, Gast-Checkout, metered-Abos, kunden-/gruppenspezifische Preislisten, Auto-Fulfillment je
  Abo-Zyklus (TODO-/Extension-Hooks an Ort).*
- **Shop-Phase 8 (Warenkorb · eingebettete Kasse · zwei Abo-Typen · Vereinfachung)**:
  - **Warenkorb** (`lib/cart-context.tsx`, localStorage; `/shop/cart`): mehrere Artikel/Optionen ⇒
    **EINE** Checkout-Session. **Abos werden einzeln** gekauft (Store erzwingt das). **Mehrere
    Preis-Optionen je Produkt** (`ShopProduct.prices`) – der Kunde wählt am Produkt (Einmalkauf /
    Nutzungsabo / Produktabo) und legt in den Warenkorb.
  - **Aufgeschobene Auftragserzeugung** (`CheckoutIntent`, Migration `042`): der Auftrag entsteht
    **erst bei bestätigter Zahlung** (`sales.fulfill_intent`) – Made-to-Order erzeugt dann je
    Position einen Auftrag; **stock** wird schon bei der Bestellung als reservierter Auftrag angelegt
    (kein Überverkauf). Abbruch/Ablauf → `sales.cancel_intent`. Token = Intent-id.
  - **Eingebettete Stripe-Kasse** (`ui_mode='embedded'`, `/shop/checkout` mit
    `@stripe/react-stripe-js`): kein Redirect mehr. Der **Publishable Key** ist öffentlich und kommt
    aus `company_settings.stripe_publishable_key` über `GET /shop/config` (Admin → Systemkonfiguration).
  - **Lieferadresse aus dem Profil** wird auf den Stripe-Customer gespiegelt (Vorbefüllung der Kasse,
    keine Doppeleingabe) – `stripe_provider._profile_shipping`.
  - **Zwei Abo-Typen** (`article_prices.sub_type`, gespiegelt nach `orders.recurrence_kind`):
    **usage** = Nutzungsabo (Zugang/Miete, einmalige Erfüllung) | **product** = Produktabo
    (wiederkehrende Lieferung; **Auto-Fulfillment je Zyklus umgesetzt**: `invoice.paid` gibt den von
    `_spawn_recurrence` angelegten Entwurfs-Nachfolger frei und verbucht seinen Verkauf als bezahlt –
    idempotent, Zyklus 1/Retries treffen den bereits bezahlten Auftrag; `ensure_supply` deckt
    make-Artikel). Beide ohne Enddatum, aktiv kündbar (Customer Portal).
  - **Vereinfachung**: Steuerklasse (Stripe Tax übernimmt), Sichtbarkeit «Verborgen»/unlisted und
    DE/EN-Umschalter im Verkauf-Reiter **entfernt** (einsprachig, KI-Übersetzung später).
  - **Bedarf → Nachschub: EIN Unter-Auftrag-Mechanismus** (ADR 003, Migration `044`, ersetzt die
    frühere Make-Verkettung). Der Shop-Verkaufsauftrag ist IMMER ein **stock/FIFO**-Auftrag – er
    SELEKTIERT vorhandene, freigegebene Instanzen (erzeugt NIE selbst welche). Reicht der Bestand
    nicht, ist der betroffene Schritt **`blocked`** (abgeleitet aus dem Bestand, kein Auto-Trigger,
    `process.step_shortfalls`/`build_order_steps`); die Fehlmenge deckt ein **Nachschub-Unter-Auftrag**
    (`orders.parent_order_id` + `orders.reason='supply'`, `services/supply.ensure_supply`), der den
    **Artikel-Prozess** fährt (produziert/beschafft) und seine Stück bei Abschluss an den Eltern
    **pinnt** (`process._peg_supply_to_parent`) → der Schritt wird von selbst wieder aktiv.
    **Rekursiv** (mehrstufige Stückliste), **idempotent**, **zyklensicher**. Auslöser ist EINER:
    ERP-Knopf «Nachschub anlegen» (`POST /orders/{id}/supply`) bzw. Shop-Zahlung bei «auf Bestellung»
    rufen **dieselbe** `ensure_supply`. Freigabe = EIN Pfad (`services/orders.release_order`) für
    ERP/Shop/Nachschub; Unterdeckung ist KEIN Freigabe-Fehler mehr (Teil-Reservierung).
    `orders.subject_source` und `orders.fulfilled_by_order_id` sind **entfernt**;
    `process._release_dependent_sales` und `sales._create_production_order` ebenfalls.
  - **Eingebettete Kasse: Inline-Abschluss** (`redirect_on_completion='never'` + `onComplete`) – kein
    separates Erfolgs-Fenster, kein Abbruch-Hänger. **Adressen = Single Source of Truth «Profil»**:
    Liefer-/Rechnungsadresse werden auf den Stripe-Customer gespiegelt, KEINE Adress-Erfassung an der
    Kasse. **Bestellungen + Abos**: Kunde unter **Konto → «Bestellungen & Abos»** (+ Stripe-Portal),
    ERP am Benutzer-Datensatz als Karte **«Bestellungen»** (`GET /shop/orders`, `GET /erp/records/{id}/orders`).
  - **EIN Auftrag je Einkauf** (Mehrpositionen): die stock-Positionen eines Warenkorbs bilden **einen**
    Verkaufsauftrag (Instanz X + Y zusammen verkaufen & versenden) – je Position ein `sale`-Schritt +
    Beleg, EIN gemeinsamer `movement`-Schritt; `order.article_id=NULL` bei >1 Position; Subjekt = FIFO je
    Position (`_create_multiline_sale_order`/`_materialize_multiline`, `_finalize_subjects` ohne Artikel-
    Filter). make-Positionen (Produktion nötig) bleiben je ein eigener Auftrag (eigene Fertigungs-Timeline).
  - **Abo on-site kündigen** (`POST /shop/orders/{id}/cancel-subscription`): kündigt **zuerst bei Stripe**,
    spiegelt erst danach lokal (`provider.cancel_subscription`) – scheitert der Stripe-Call, bleibt das Abo
    aktiv (sauberer Fehler, kein stilles Weiterlaufen). Button im Konto-Reiter; Stripe-Portal bleibt für
    Zahlungsmittel.
- **ERP-Mehrpositionen-Aufträge + Direktverkauf (Herkunft/Zahlungsart)**: die Auftragsanlage bleibt
  **unverändert Einzel-Artikel** (Artikel + Menge, wie gewohnt per Auto-Save). Weitere Artikel lassen
  sich **jederzeit danach** ergänzen – auch nachdem der Auftrag schon gespeichert wurde, nicht nur bei
  der Anlage (`POST /orders/{id}/lines`, `services/order_lines.py`; wandelt beim ersten Aufruf den
  bisherigen Anker in Position 0 um, `order.article_id` wird `NULL`). `DELETE .../lines/{id}` entfernt
  eine Position (die letzte ist geschützt – ein Auftrag ohne jedes Subjekt wäre inkonsistent);
  `PATCH .../lines/{id}` fixiert Instanzen EINER Position statt FIFO (analog `instance_object_ids` am
  Einzel-Artikel-Auftrag). Ein Abo lässt sich – wie im Shop-Warenkorb – nicht mit weiteren Positionen
  mischen; der Check sitzt aber bewusst **am Hinzufügen des `sale`-Prozessschritts**
  (`sale.assert_sale_compatible`, aufgerufen aus `article_process.py: _create`), NICHT am Hinzufügen
  einer Position – eine weitere Position anzulegen, ohne dass überhaupt ein Verkauf beabsichtigt ist
  (z. B. nur Bewegen/Prüfen), darf nicht blockiert werden. `add_order_line` prüft nur die Rückrichtung
  (existiert bereits ein `sale`-Schritt, verhindert es eine nachträglich inkompatible Position). Ob ein
  Artikel „exklusiv" ein Abo ist, entscheidet `pricing.is_subscription_exclusive`/`resolve_one_time_price`
  über ALLE aktiven Preise (nicht nur die „primäre" Option) – ein Artikel mit Abo- UND Einmalkauf-Preis
  gilt nicht als exklusiv und lässt sich mischen (`sale.price_from_article` nutzt dann automatisch den
  Einmalkauf-Preis). `subject.subject_kind` erzwingt für einen Mehrpositionen-Auftrag **immer** `stock` (auch OHNE
  jeden Schritt) – schliesst die stille „0 Instanzen, keine Fehlermeldung"-Lücke, die entstünde, würde er
  fälschlich als `produce` behandelt.
  **Der Ablauf bleibt der GENERISCHE Step-Editor, unverändert** (`ProcessSteps`/`article_process.py`) –
  KEIN eigener Bypass, KEINE Sonderbehandlung: **jedes Prozessschrittmodul ist universell einsetzbar**,
  auch bei einem Mehrpositionen-Auftrag (keine Schritttyp-Whitelist mehr – Nutzer-Feedback: „Prozess-
  schrittmodule sollten, wenn auch immer möglich, universell einsetzbar sein"). `purchase` legt dafür
  wie `sale` je Position eine eigene Fachzeile an (`purchase.instantiate_for_order`, mehrere
  `PurchaseOrder` teilen sich den `step_id`; anders als beim Verkauf ist jede Bestellung eine EIGENE,
  unabhängig fortschreitende Beschaffung – `purchase.apply_update_bulk` verlangt bei >1 Position die
  betroffene `article_id`, statt eine gemeinsame Aktion zu erzwingen). `resource`/`inspection` skalieren
  jetzt über `order_lines.effective_quantity` (Summe der Positionsmengen) statt über das bei
  Mehrpositionen NULL-wertige `order.quantity`; eine Datenerfassung bleibt EINE Fachzeile über alle
  Instanzen des Auftrags hinweg (`inspections.article_id` jetzt nullable). `movement`/`scrap` waren
  bereits artikel-unabhängig und brauchten keine Änderung. Aber **genau EIN** `sale`-Schritt bedient
  **alle** Positionen (`sale.instantiate_for_order`
  legt bei Freigabe pro Position einen `Sale`-Beleg an, alle mit demselben `step_id`;
  `process.facts_for_step`/`_resolve_facts_multi` lösen die Liste auf) – **NIE mehrere sequentielle
  Sale-Schritte** («2-fache Prozessschrittmodule» war der zentrale Kritikpunkt der ersten, verworfenen
  Umsetzung). Die abgeleitete Bereitstellung zum Kunden funktioniert daher unverändert –
  EIN Sale-Schritt ⇒ EINE Sendung, kein Vervielfachungsrisiko.
  **Preis = Single Source of Truth vom Artikel** (`sale.price_from_article`, dieselbe Preis-Pipeline wie
  der Shop `services/pricing.py`): bei genau EINER Position bleibt der Betrag wie gewohnt frei editierbar
  (z. B. Artikel ohne hinterlegten Verkaufspreis); bei mehreren Positionen ist der Betrag **pro Position
  vom Artikel abgeleitet** und NICHT mehr frei eintippbar (`sale.apply_update_bulk` lehnt eine manuelle
  Betrags-Änderung dann ab) – kein einzelner Betrag mehr über unterschiedliche Artikel/Preismodelle
  gestülpt. Eine kombinierte Aktion (Bestätigen/Rechnung/Zahlung, EIN Kunde) wirkt auf **alle** Positionen
  gleichzeitig. Kernstellen generalisiert, Einzel-Artikel-Pfad unverändert: `subject._allocate_stock_for`
  (Kern aus `_allocate_stock_subject`), `process._subject_shortfalls` (dict über alle Positionen),
  `process._peg_supply_to_parent` (Nachschub-Pegging erkennt Mehrpositionen-Aufträge als Subjekt),
  `deactivation._order_article_filter` (Artikel-Deaktivierung findet Aufträge auch über `order_lines`).
  Frontend: die gewohnten 3 Ziel-Karten «Was möchten Sie tun?» bleiben unverändert – bei mehreren
  Positionen ist **«Herstellen» ausgegraut** (kein EINER Artikel-Prozess, den ein Mehrpositionen-Auftrag
  fahren könnte), nur FIFO/«Instanz wählen» bleiben (`order-detail.tsx: canProduce`); «Instanz wählen»
  zeigt dann **einen Picker je Position** (`PinLine`/`pinLines`). Eine dezente «+ Position hinzufügen»-
  Zeile im Bedarf-Feld ist **jederzeit im Entwurf** aktiv, nicht nur bei der Anlage
  (`AddPositionRow`/`api.addOrderLine`). `SalePanel` rendert die volle Belegliste (`OrderStepInfo.sales`)
  statt eines einzelnen Verkaufs. Zusätzlich `sales.mode` (shop/direct) + `payment_method`/
  `payment_reference` am Verkauf: ein personal-erfasster Verkauf braucht **kein Kartenterminal** –
  Rechnung ist der übliche B2B-Weg (wählbar: invoice/cash/twint/other; `payment_method='terminal'` für
  Stripe Terminal ist im Datenmodell vorgemerkt, aber **noch nicht** wählbar). **Regressions-Fix im
  gleichen Zug:** `PATCH /orders/{id}/sale` nahm bisher blind die erste Sale-Zeile eines Auftrags
  (`.first()`) – bei mehreren Verkaufs-Belegen hätte jede Aktualisierung dieselbe (falsche) Position
  getroffen; jetzt wie movement/resource/inspection über `resolve_exec_step`/`facts_for_step` (`step_id`)
  aufgelöst.
- **Nachbesserungen Mehrpositionen/Abo (Praxistest-Fixes)**:
  - **Freigabe-Ausnahme für Abweichungen**: eine Abweichung (Unter-Auftrag, `reason='deviation'`) hat ihr
    Subjekt bereits über fixierte Instanzen (`Instance.subject_of_order_id`), OHNE eigene `order_lines` –
    erbt bei einem Mehrpositionen-Eltern aber dessen `article_id=NULL`. Die Freigabe-Prüfung verlangte
    fälschlich trotzdem Artikel+Menge (`orders.py`: `wants_release`-Block prüft jetzt zusätzlich
    `subject.is_deviation(order)` und lässt Abweichungen ohne `order_lines` durch); Frontend-Pendant
    `order-detail.tsx: hasDemand` berücksichtigt `isSubOrder` ebenso.
  - **Alle Prozessschritt-Module sind jetzt universell einsetzbar** (Task 3): die künstliche
    «nur sale+movement»-Sperre in `article_process.py: _create` ist entfernt. `purchase` legt bei
    Mehrpositionen **eine unabhängige Bestellung je Position** an, alle mit gemeinsamem `step_id`
    (`purchase.instantiate_for_order`); jede Position schreitet **eigenständig** fort (eigener
    Lieferant/Zeitplan) – `purchase.apply_update_bulk` verlangt ab der zweiten Position die
    betroffene `article_id` zur Disambiguierung (auch für Status, keine erzwungene Sammelaktion wie
    beim Verkauf). `resource`/`inspection` nutzen jetzt `order_lines.effective_quantity` (Summe der
    Positionsmengen) statt des bei Mehrpositionen NULL-wertigen `order.quantity`
    (`inspections.article_id` dafür nullable, Migration `047`); eine Datenerfassung bleibt EINE
    Fachzeile über alle Instanzen. Frontend: `PurchaseStepPanel` rendert eine Zeile je `OrderPurchase`
    (`OrderStepInfo.purchases`), mit Artikel-Header sobald >1 Position.
  - **Abo-Mischungs-Prüfung verschoben + präzisiert** (Task 2): die Prüfung «Abo lässt sich nicht mit
    weiteren Positionen kombinieren» blockierte bisher schon beim reinen Hinzufügen einer Position
    (`add_order_line`), bevor überhaupt klar war, ob der Auftrag einen Verkauf durchläuft, UND erkannte
    Artikel mit **zusätzlichem** Einmalpreis fälschlich als Abo-exklusiv. Neu: `pricing.
    is_subscription_exclusive`/`resolve_one_time_price` prüfen korrekt über ALLE Preise eines Artikels
    (exklusiv nur, wenn GAR kein Einmalpreis existiert); die Prüfung (`sale.assert_sale_compatible`)
    greift jetzt am **`sale`-Schritt selbst** – sowohl beim Hinzufügen des `sale`-Moduls zu einem
    Mehrpositionen-Auftrag (`article_process.py: _create`) als auch umgekehrt beim Hinzufügen einer
    weiteren Position, wenn bereits ein `sale`-Schritt existiert (`orders.py: add_order_line`) – mit
    konkreter Fehlermeldung, die den betroffenen Artikel nennt.
  - **Abo-Mindestlaufzeit / Kündigungs-Cooldown** (Task 1, State-of-the-Art analog SaaS-Branche): ein
    **Produktabo** (`sub_type='product'`, wiederkehrende Lieferung) ist erst nach **einem vollen
    Abrechnungszyklus** ab Freigabe kündbar (`sales.earliest_cancellation_date`,
    `PRODUCT_MINIMUM_TERM_CYCLES=1`); ein **Nutzungsabo** (`sub_type='usage'`) hat keine Mindestlaufzeit.
    Personal/Admin kann jederzeit kündigen (Bypass). `routers/shop.py: cancel_subscription` weist eine
    verfrühte Kündigung mit 403 + Datum ab; `CustomerOrder.cancellable_from` liefert das Datum an den
    Kunden, `orders-list.tsx` deaktiviert den Kündigen-Knopf bis dahin mit Beschriftung «Kündbar ab …».
  - **UX: Hover-Begründung bei gesperrten Aktionen**: der Auftrag-Freigabe-Knopf zeigt per `title`-
    Tooltip den konkreten Grund, warum er (noch) ausgegraut ist, statt stillschweigend deaktiviert zu
    bleiben.
- **Retoure/Erstattung = ganz normaler Auftrag über das VEREINHEITLICHTE `sale`-Modul** (Migrationen
  `048`+`049`; der frühere separate `refund`-Schritt ist wieder entfernt): Eine Retoure wird angelegt **wie
  jeder andere Auftrag** – Artikel wählen, dann bei **«Instanz wählen»** statt Lager-Instanzen die
  **verkauften** Instanzen wählen (KEINE eigene Ziel-Karte mehr; `routers/orders._set_chosen_instances` +
  `_validate_pins` akzeptieren `sold`). Das Backend erkennt verkaufte Instanzen und macht den Auftrag zur
  Retoure: `orders.reason='return'` (festes Subjekt via `Instance.subject_of_order_id`, wie eine Abweichung –
  kein FIFO/keine Reservierung, **ohne** Eltern-Pause) + `parent_order_id` = der **Original-Verkauf**
  (`services/refund.original_sale_order`, Grundlage für Betrag/MWST/Kunde/Stripe-PaymentIntent). Lager- und
  verkaufte Instanzen lassen sich nicht mischen (gegensätzliche Geldrichtungen).
  - **EIN `sale`-Schritt, ZWEI Modi – aus dem Subjekt ABGELEITET** (kein eigener Schritttyp): normaler
    Auftrag → **Verkauf** (`kind='sale'`, Geld rein, Bestands-Abgang) | Retoure (Subjekt verkauft) →
    **Gutschrift/Erstattung** (`kind='credit'`, Geld raus, `sale.instantiate_for_order` über `is_return`).
    Betrag/Kunde aus dem Original abgeleitet (`_prefill_credit`), bei EINER Position **abweichend erfassbar**
    (Teil-Erstattung/**Kulanz**). Ablauf Bestätigen→Ausstellen→**Erstatten**: die «Zahlung» (`paid`) löst den
    **Stripe-Refund** aus, wenn der Verkauf via Stripe lief (`_issue_refund`/`provider.refund`, voll/anteilig,
    idempotent), sonst dokumentierte manuelle Gutschrift; Nummer `GS-{id}`, Event `sale.refunded`. Dasselbe
    Panel (`sale-panel.tsx`) rendert Verkauf ODER Gutschrift (Dual-Mode über `first.kind`); EIN Endpoint
    `PATCH /orders/{id}/sale`.
  - **Label-Wechsel dann, WANN es wirklich passiert (step-basiert, idempotent):**
    - **Verkauf bezahlt → «verkauft»**: `process.sell_order_subjects` (in_stock→sold, mengengenau) wird bei
      **sale-`paid`** aufgerufen (`sale._apply_transition`/`finalize_paid`) – nicht erst am Auftragsende;
      make-to-order zieht beim Abschluss nach. Die **Begleit-Bewegungen** (u. a. der Versand zum
      Kunden) sind von der Subjekt-Fehlmengen-Prüfung **ausgenommen** (`step_shortfalls`, `not
      is_companion(step)`), sonst würde der Versand blockiert, sobald die Ware «verkauft» (aus dem freien
      Bestand «weg») ist.
    - **Rückgabe-Bewegung durch → «freigegeben»**: `process.return_subjects_to_stock` (sold→in_stock, Menge
      auf ≥1) wird bei der **Bewegung** weg vom Kunden aufgerufen (`movement.record_movement`), nicht
      erst am Auftragsende. Movement/Scrap nehmen bei einer Retoure (bzw. Versand: Ziel=Person) auch
      **verkaufte** Instanzen auf. **Kulanz** (Ware NICHT bewegt) → bleibt `sold`, nur Geld zurück.
    - `_finalize_subjects` beim Abschluss ist nur noch das **Sicherheitsnetz** (ruft beide Helfer idempotent).
  - Geld (`sale`/Gutschrift) und Ware (`movement`) sind **frei kombinierbar** – Retoure mit Rücknahme,
    reine Kulanz-Gutschrift (Reklamation ohne Rückgabe), defekt→verschrotten+gutschreiben. **Löst nebenbei
    das «Menge reduzieren»-TODO** (Teil-Erstattung statt stiller Mengen-Kürzung). Original-Verkauf zeigt die
    Retoure als Unter-Auftrag (`OrderResponse.returns`). *Bewusst NICHT gebaut: Store-Credit/Guthaben.*
  - **Kunden-Retoure aus «Meine Bestellungen» (Online-Shop-Logik, `services/customer_returns.py`)**: der
    Kunde stösst zu einer **abgeschlossenen** Bestellung im **Rückgabefenster** (`RETURN_WINDOW_DAYS=30`)
    eine Rückgabe an (`POST /shop/orders/{id}/return`, optionaler Grund). Das legt – wie eine ERP-Retoure –
    einen Retoure-Unter-Auftrag an (verkaufte Instanzen als Subjekt, `parent`=Original-Verkauf) und gleich
    den üblichen **Ablauf** (Bewegung = Wareneingang + `sale` im Kredit-Modus = Gutschrift); das Personal
    verarbeitet ihn im ERP (Wareneingang buchen → Gutschrift bestätigen → Stripe-Refund). `CustomerOrder`
    trägt `returnable`/`return_requested`/`return_deadline`; `orders-list.tsx` zeigt «Retoure anfragen»
    (mit Frist) bzw. «Retoure angefragt». *Bewusst NICHT gebaut: Rücksende-Label/RMA-Tracking, Teil-
    Mengen-Auswahl durch den Kunden (Personal passt die Menge im ERP an).*
- **Versand zum Kunden geht IMMER an den Kunden** (Fix): die zu einem `sale`-Schritt gehörende
  Bewegung (Bereitstellung bzw. Alt-Bestand `mode='customer'`) hat als Ziel **fix den Kunden des Verkaufs** (`sale.customer_for_order`).
  Serverseitig erzwungen (`movement.record_movement` überschreibt die Ziel-Eingaben) UND im Embed als festes
  Ziel gezeigt (`orders._movement_embed`) – der Lagerist kann kein falsches Ziel wählen. Weil das Ziel fest
  ist, lädt das Movement-Panel **keine** Personen-/Instanz-Listen mehr (`movement-panel.tsx:
  hasFixedTarget` → spürbar schneller, gerade direkt nach dem Verkauf). **Das Ziel ist fest, der Schritt
  ist es nicht:** wer nicht versendet (Abholung, Streckengeschäft), löscht die Bewegung – sie ist seit
  Juli 2026 ein normaler Schritt (siehe «Zwangs-Prozessschrittmodule sind aufgelöst»).
- **KI-Layer (ADR 004, `docs/adr/004-ki-layer.md` – VOR KI-Arbeit lesen)**: vier dünne Schichten in
  `backend/app/services/ai/`. (1) **Gateway** (`gateway.py`): provider-agnostisch – **Vertex-EU Default**
  (`AI_PROVIDER=vertex` + `VERTEX_PROJECT_ID`, ADC-Auth), Anthropic-direkt swap-bar, Gemini-Bild
  («Nano Banana») via Vertex-REST; ohne Konfiguration **inaktiv statt kaputt** (503, ERP läuft normal).
  Modelle/Prompts versioniert in `registry.py` (`PROMPT_VERSION`), NIE in der Fachlogik. (2) **KI-Identität**
  (`identity.py`): System-`UserProfile` `role='ai'` mit Objektnummer, beim Start geseedet; Audit/Events
  zeigen «User KI»; Admin kann sie weder umrollen noch deaktivieren. **Delegation** (`principal.py`):
  Attribution = KI, **effektive Rechte = delegierender Mensch**. (3) **Rechte-gescopte Tools** (`tools.py`):
  rollen-gefilterte Whitelist (Kunde: shop/my_orders; Lieferant: nur eigene Aufträge; Staff: alles; autonom:
  read-only) – jedes Tool wrappt die BESTEHENDE Authz (`visible_orders`, `can_view`, `in_stock_clauses`);
  **Scoping = Authz, nicht Prompt**. **Zielbild: permission-scoped Vollparität** – die KI soll grundsätzlich
  ALLES einsehen/tun können, was der jeweilige Nutzer auch darf (Lesen breit, kritisches Schreiben hinter
  Bestätigung). Werkzeug-Set wächst entsprechend (Staff aktuell u. a. Artikel/Auftrag/Instanz/Benutzer/
  Standort/Firmen-Info/Audit-Log lesen, Artikel/Auftrag-Entwürfe + Prozessschritte + Instanz-Fixierung
  schreiben, `resolve_object` für jede Objektnummer). Kritisches (Freigabe/Geld/Löschen/Rolle) bleibt Gate. **Autonomie-Policy**: Entwürfe (Artikel/Auftrag, draft) legt die KI
  direkt an (reversibel); **Kritisches** (Auftrag freigeben) nur als `AiAction`-Vorschlag (Migration `054`)
  → menschliche Bestätigung im Chat → autorisierter Pfad (`actions.py`, idempotent). (4) **Endpunkte**
  `routers/ai.py`: `/api/v1/ai/{config,chat,write,image-edit,actions/{id}/confirm|reject}`; Events `ai.*`
  (Modell/Prompt-Version/Token je Lauf). **Frontend**: schwebendes Chat-Widget `components/ai/assistant.tsx`
  (ERP-, Konto-, Shop-Layout; Vorschlagskarten mit Bestätigen/Ablehnen), **KI-Schreibhilfe** im
  Dokument-Panel (`ai/write-assist.tsx`), **Shop-Bild-Bearbeitung** im Verkauf-Panel (`ai/image-assist.tsx`,
  Ergebnis = neues Attachment, Original bleibt). Untrusted-Text (Dokumente/Fremdtexte) ist DATEN, nie
  Instruktion. *Bewusst NICHT gebaut: autonome Freigaben/Geld/E-Mail, MCP-Server nach aussen, RAG/Vektor.*
  - **KI-Optimierungen (Kosten/Latenz/UX)**: (1) **Dynamische Modellwahl** (`registry.route`): einfache
    Lese-/Zählfragen laufen auf dem **leichten** Modell (`ai_chat_model_light`, Haiku) OHNE Reasoning
    (günstig/schnell), nur mehrstufige/schreibende Aufgaben (anlegen/bestellen/freigeben/Link) nutzen das
    **starke** Modell (`ai_chat_model`, Opus) mit adaptivem Reasoning – reine Heuristik (kein Vorab-Call),
    im Zweifel aufwärts. (2) **Knappe Antworten** (Prompt) + **Markdown-Rendering** im Chat (react-markdown +
    remark-gfm, Design-Tokens; **fett**/Listen/Tabellen). (3) **KI überall**: das Widget hängt im
    `(public)/layout` (Website+Shop), ERP-, Konto-Layout – rechte-gescopt, rendert nur für angemeldete
    Nutzer. (4) **Live-Refresh**: verändert die KI ERP-Daten (`AiChatResponse.changed=true` via
    `tools.is_write_tool`), feuert das Widget `inexxio:data-changed` → der Feed lädt sofort nach. Der
    Verlauf lädt beim Mounten (überlebt Seiten-Refresh); der Chat scrollt beim Öffnen ans Ende.
    (5) **Navigation/Hinführen** (`open_page`-Tool → `AiChatResponse.navigate`): die KI kann den Nutzer
    an die passende Stelle führen (Shop-Produkt/Warenkorb/«Meine Bestellungen»/ERP-Datensatz via
    `/erp?open=<Objektnr>`) – das Widget rendert dazu einen Knopf. Ein Kaufwunsch «leg es in den
    Warenkorb» wird NICHT abgewimmelt, sondern zum Produkt geführt. (6) **Rückfragen erlaubt**: bei
    echter Unklarheit fragt die KI kurz nach statt zu raten. (7) **Schreibhilfe** liefert ein
    vollständiges Dokument (mehrere ausformulierte Abschnitte), nie nur eine Überschrift.
- **Beleg-/Dokument-Modul (hochgeladene Fremd-Dokumente, KI-Aufnahme, Reiter «Dokumente»)**: Für
  unvermeidbare Fremd-Dokumente (Rechnungen, Lieferscheine, Anleitungen, Datenblätter, Zertifikate,
  Verträge), die MIT Lieferungen ins Unternehmen kommen – NICHT von Inexxio verfasst. **Abgrenzung:**
  das Prozessschritt-`Document` (`models/document.py`) sind Inexxio-EIGENE, verfasste Textdokumente
  (Nummer = Instanz); das neue `DocumentFile` (`models/document_file.py`) ist eine **hochgeladene
  Datei** mit **eigener Objektnummer** (Typ `document`). **Ablauf (ADR-004-Muster «Vorschlagen ≠
  Ausführen»):** Datei hochladen/fotografieren (`POST /ai/documents/analyze`, multipart) → die KI liest
  das PDF/Bild direkt (Vision/Document-Block, kein separates OCR; PDF-Textlayer wird zusätzlich per
  `pypdf` gratis extrahiert und als `extracted_text` gespeichert = spätere RAG-Basis) und erfasst über
  ein **erzwungenes Tool** `extract_document` strukturiert **Name, Typ, Zusammenfassung, Bezugsgrössen**
  (`services/ai/documents.py`). Aus den Bezugsgrössen matcht der Server **passende ERP-Objekte**
  (`match_candidates`: Artikel-Fuzzy via `article_names._similarity`, Lieferant/Firma, im Text genannte
  Objektnummern, plus das Kontext-Objekt) und legt einen **`AiAction`-Vorschlag** (`action_type=
  'link_document'`) an – NICHTS ist damit gespeichert. Der Mensch prüft/ändert **Name + Objektzuordnung**
  und **bestätigt** (`POST /ai/documents/{id}/confirm`) → erst dann materialisiert `documents.materialize`
  das `DocumentFile` + die **n:m-Verknüpfungen** (`document_links`). **Ein Dokument entsteht NIE
  objektlos** (Freigabe-Gate: min. 1 Verknüpfung; manuelle Objektnummer-Eingabe möglich). Ablehnen
  (`reject`) entfernt die Datei aus der Ablage. **Zuordnung ist n:m** (eine Rechnung betrifft Lieferant
  + mehrere Artikel + Auftrag). **Dublette** über `sha256` erkannt. **Speicher:** `services/storage.py` –
  **GCS**, wenn `settings.gcs_bucket` gesetzt (Cloud-Run-ADC, kein Key), sonst DB-Fallback
  (`document_blobs`); PDFs werden **byte-genau** abgelegt (kein JPEG-Re-Encode wie bei `attachments`).
  **Auslieferung authentifiziert** (`GET /erp/document-files/{id}/download`, `require_employee` – Rechnungen
  sind sensibel, NICHT der öffentliche Foto-Token-Weg). **Reiter «Dokumente» je ERP-Objekt**
  (`GET /erp/objects/{id}/documents`, generisch über die Objektnummer): vereint hochgeladene Dateien
  (via Links) UND die im Schritt «Dokument» erzeugten Dokumente. Frontend: `components/erp/object-
  documents.tsx` (`ObjectDocuments` + Upload-/Analyse-/Bestätigungs-Dialog, Kamera-Aufnahme), eingebunden
  in ALLE Detailansichten (Artikel/Auftrag/Instanz/Benutzer/Unternehmen). **RAG (semantische
  Suche über den `extracted_text`) ist bewusst im Backlog** – der weiche Start deckt «Objekt bekannt →
  Text am Objekt» ab; korpusweite Suche kommt später über das geplante Typesense. Ohne konfigurierte KI
  läuft das Modul weiter (Titel = Dateiname, manuelle Zuordnung). Migration `059`.

> **HINWEIS (aktuelles Kernmodell):** **Auftrag → Prozess → Instanz.** Der **Artikel** trägt seine
> **Spezifikation** (vormals «Stammdaten») + **einen** Prozess (Schritte inline, kein Prozess-Objekt, keine
> Objektnummer, keine n:m-Verknüpfung). **Freigabe auf Artikel-Ebene** friert Spezifikation + Prozess.
> Ein **Auftrag** ist der Trigger in zwei **Modi**: **make** (Artikel + Menge → fährt den Artikel-Prozess,
> ERZEUGT Instanzen) oder **custom** (ausgewählte vorhandene Instanzen + individueller Prozess am Auftrag).
> **Instanzschritte verarbeiten nur Instanzen**; Artikel dienen v. a. als FIFO-Bezug. Schritttypen: purchase,
> inspection, movement, **resource** (Verbrauch + Betriebsmittel, Modus je Zeile), **scrap** (Verschrotten),
> sale. `quality`+`disposition` als zwei Instanz-Achsen; `event_types`-Registry deklariert die Bestands-
> Polarität. **Unter-Auftrag** (`parent_order_id` + `reason`) – EIN Mechanismus, DREI Gründe:
> **Abweichung** (`reason='deviation'`: Abbruch-Folgeauftrag / Fehler / Reklamation / Nacharbeit,
> pausiert den Eltern; `Claim`-Typ entfernt), **Nachschub** (`reason='supply'`: deckt einen nicht
> vorrätigen Bedarf, blockiert nur den Schritt) und **Retoure/Erstattung** (`reason='return'`, Migrationen
> `048`+`049`: als **ganz normaler Auftrag** angelegt – bei «Instanz wählen» **verkaufte** Instanzen wählen
> → Backend leitet Retoure + `parent`=Original-Verkauf ab; Geld über das **vereinheitlichte `sale`-Modul im
> Kredit-Modus** (`kind='credit'` aus dem Subjekt abgeleitet + Stripe-Refund), Ware über die **Bewegung**.
> Festes Subjekt wie eine Abweichung, aber OHNE Eltern-Pause. Kein separater `refund`-Schritt mehr).
> **Label-Wechsel step-basiert** (wann es wirklich passiert): Verkauf bezahlt → sold; Rückgabe-Bewegung an
> weg vom Kunden → in_stock; Kulanz (nicht bewegt) → bleibt sold. **Bedarf→Nachschub (ADR 003):** ein ungedeckter Bedarf
> macht den Schritt `blocked` (abgeleitet); `supply.ensure_supply` legt rekursiv/idempotent/zyklensicher
> Nachschub-Unteraufträge an (Artikel-Prozess), die bei Abschluss an den Eltern **gepinnt** werden.
> **Verkauf/Shop** (MVP) lebt am Artikel (Profil + `article_prices` + Audience); **nur Basispreis CHF**
> gepflegt, Rest abgeleitet (gestaffelte Pipeline, gepinnte Fremdwährung). Zwei Achsen: Preismodell
> (Einmalkauf/Abo) + Verfügbarkeit (`sales_fulfillment` = 1-Bit-Backorder-Policy: make=Nachschub |
> stock=nur ab Lager). Kauf = stock/FIFO-Auftrag mit `sale`+`movement`-Schritt + Preis-Snapshot;
> Fehlmenge → Nachschub (kein `subject_source`/`fulfilled_by_order_id` mehr). **Warenkorb**
> (mehrere Positionen ⇒ ein Checkout; Auftrag entsteht aufgeschoben erst bei Zahlung via `CheckoutIntent`).
> **Zahlung = Stripe** (eingebettete Kasse `ui_mode='embedded'` + Adaptive Pricing + Stripe Tax,
> Webhook-gespiegelt; `manual` als Fallback ohne Keys). Zwei Abo-Typen (`sub_type` usage/product).
> **Inaktive Artikel sind endgültig** (kein Reaktivieren). Setup/Keys: `docs/stripe-setup.md`.
> E-Mail (Gmail API) ist **noch nicht** umgesetzt.

- **Öffentliche Rechtsdokumente (D, Zeiger auf einen Artikel)**: AGB/Datenschutz kommen aus dem
  **Dokument-Modul** statt aus hartkodiertem Seitentext. Am Unternehmen wird je Typ die **Objektnummer
  eines Artikels** hinterlegt (`company_settings.legal_documents` JSONB, `{"agb": <Artikel-Objektnr>,
  "datenschutz": …}`); die Website zieht dessen **erste Instanz mit ausgestelltem Dokument-Beleg**
  (`Document.done=True`) – massgeblich ist die **Ausstellung**, NICHT der Lagerstatus (`in_stock`) der
  Instanz; nur verschrottete Instanzen werden übersprungen. **Neue Fassung = neuer Artikel + «Ersetzen»**
  (`replaced_by_id`): die Auflösung folgt der Ersetzungs-Kette automatisch auf die **neueste Fassung mit
  ausgestelltem Beleg** (wie der Shop kanonisiert) – der Zeiger muss nicht angefasst werden; ein noch
  belegloser Nachfolger (Entwurf) wird übersprungen, die alte Fassung bleibt gültig, bis die neue
  tatsächlich einen ausgestellten Beleg hat. Alte Instanzen bleiben über ihre Objektnummer archiviert
  (Nachweis im Streitfall). Auflösung `services/legal.resolve` (Artikel→`replaced_by_id`-Kette→erste
  Instanz mit ausgestelltem `instance_document_embeds`); Public-Endpoint `GET /api/v1/legal/{kind}`
  (404 → Website-Fallback auf eingebauten Text). **Voraussetzung:** das Dokument muss in einem Auftrag
  auf den Artikel **ausgestellt** worden sein (Prozessschritt «Dokument» → «Ausstellen»).
  Frontend: `/agb` + `/datenschutz` rendern `<LegalDocument kind=… fallback={…}>` (DocumentView inkl.
  Briefkopf), Admin → Systemkonfiguration → «Rechtstexte» (Artikelnummer je Typ). Erfüllt die
  AGB-Akzeptanz-Version geschenkt.
- **Dokument-Freigabe & Pflichten (Unterschriften/Anerkennungen, DocuSign-Prinzip)**: Ein Dokument ist
  eine **ganz normale Instanz** (unveränderte Statuse `quality`/`disposition`); der Prozessschritt
  «Dokument» ist ein **Sub-Prozess** (wie `purchase`): **Entwurf → Ausgestellt (`documents.issued`, Inhalt
  eingefroren, unveränderliche Basis) → Freigaben laufen → Vollständig freigegeben (`documents.done`) →
  Instanz freigegeben, Auftrag abgeschlossen**. `done` wird NICHT im `_fact_status` erraten, sondern vom
  Service gesetzt, sobald alle Parteien signiert haben (`document._maybe_complete`; ohne Parteien fällt es
  bei «Ausstellen» zusammen → rückwärtskompatibel). **ZWEI Partei-Typen, am Schritt deklariert**
  (`article_process_steps`, Migration 066): (1) **Freigabe-Parteien** – endliche, geordnete Liste
  (`doc_signers` = [{signer_object_id, action `confirm`|`sign`}], `sign_sequential`), materialisiert bei
  «Ausstellen» als **append-only Layer** `document_signoffs` (EINE Tabelle für bestätigen OHNE Bild +
  unterschreiben MIT Bild). Erst wenn ALLE signiert haben, ist das Dokument freigegeben → **gated den
  Auftragsabschluss** (terminiert immer, weil endlich). Nur die **benannte Person** (Objektnummer-Abgleich)
  handelt; **sequenziell** = nur die kleinste offene `order_index` ist dran. Aktionen: sign/confirm/reject
  (mit Grund)/withdraw (eigene Unterschrift zurückziehen); Personal kann die **Ausstellung zurücknehmen**
  (`document.withdraw_issuance`, solange nicht `done`) → Inhalt wieder editierbar. (2) **Anerkennungs-
  Publikum** – offen (`doc_audience` = all|roles|persons + `doc_audience_roles`/`_person_ids`), ein
  **rollierendes, aktions-getriggertes Gate auf dem BEREITS freigegebenen Dokument** (`services/consent.
  _audience_obligations` → `document_acknowledgements`, kind='document', Version = Instanz-Objektnummer) –
  **blockiert den Auftrag NIE**, erscheint aber im **Consent-Gate-Modal** (jede Rolle). Kanonisch: ein
  Dokument, dessen Artikel **ersetzt** wurde, ist superseded → der Nachfolger fordert die neue Anerkennung
  (Q «neue Version = sofort neu bestätigen»). **Aufteilung Schritt↔Auftrag:** der Schritt deklariert die
  STRUKTUR (Parteien-Slots, Reihenfolge, Publikum, `doc_visibility`); der Auftrag füllt INHALT + sammelt
  die konkreten Unterschriften. **Lieferanten-Fähigkeits-Gate** (Offerte erst nach Bestätigung): über ein
  `supplier_terms`-Dokument mit `doc_audience=roles=[supplier]` – das Consent-Gate blockiert den Lieferanten,
  bis er anerkannt hat (kein Sonder-Check im Beschaffungs-Pfad). **Surfaces:** Prozess-Editor
  (`process-steps.tsx: DocConfigEditor` – Parteien per SearchSelect + Drag&Drop + `confirm`/`sign` je Zeile,
  sequenziell-Toggle, Publikum, Sichtbarkeit); Auftrags-Panel (`document-panel.tsx` – Ausstellen →
  Parteien-Liste mit Inline-Signatur `SignaturePad`/Bestätigen/Ablehnen + Zurücknehmen); **«Meine Dokumente»**
  (`account/sections/documents-section.tsx` – externe Parteien signieren im Konto, `GET/POST /consent/
  {my-documents,signoffs/{id}}`); der **Freigabe-Layer wird auf das Dokument gerendert** (Web `DocumentView`
  + PDF `document_render._signoffs_html`, Unterschrift-Bild als data-URI). Endpunkte am Auftrag
  (`POST …/document/signoff/{id}`, `…/document/withdraw`). **Sichtbarkeit ist als Lese-Zugriffsfilter
  erzwungen** (`orders._doc_content_visible`): Nicht-Personal sieht den Dokument-Inhalt im Auftrags-Embed
  nur nach `doc_visibility` (public → jeder | parties → Parteien/Publikum | internal → nur Personal);
  eine benannte Partei liest IMMER (man kann nicht unterschreiben, was man nicht sieht).
  **Parteien-Substitution am laufenden Auftrag** (`POST …/document/substitute-signer`, Personal,
  auditiert): das offene (pending/abgelehnte) Signoff wandert auf eine neue aktive Person – Position/
  Aktion bleiben, geleistete Unterschriften nie; fällt eine Partei aus, braucht der Auftrag keinen
  Abbruch mehr.
  - **Ausstehende Pflicht-Unterschriften senken die Profil-Vollständigkeit**: `useProfileCompletion`
    nimmt jetzt die Zahl **offener** Dokument-Pflichten (ausstehende Unterschriften/Bestätigungen +
    Anerkennungen, aus `/consent/my-documents` + `/consent/pending`) und zählt sie wie fehlende
    Pflichtfelder → das Profil zeigt **nicht «vollständig»**, solange etwas aussteht (Badge am Reiter
    «Meine Dokumente»). `account-shell` lädt die Zahl und aktualisiert live über das Fenster-Event
    `inexxio:documents-changed` (von `documents-section` nach jeder Aktion gefeuert).
  - **Dokument-Vorschau ist auf A4 begrenzt & überlaufsicher**: `DocumentView` rendert ein Blatt mit
    fester A4-Breite (`A4_WIDTH=794px`, zentriert, WYSIWYG mit dem PDF); Tabellen nutzen
    `table-layout:fixed` + Wortumbruch (Web **und** PDF `document_render`), lange Wörter/URLs/Code
    brechen um – **nichts kann breiter als der Satzspiegel werden** (kein horizontaler Überlauf/
    Beschnitt, auch bei KI-generierten breiten Tabellen).
- **Sicherheitsbestand + Auto-Nachbestellung (E, «Nicht die Zeit soll bestellen, sondern der Bestand»)**:
  **Sicherheitsbestand** = `articles.safety_stock`; fällt der **freie** Bestand darunter, legt
  `services/replenishment.check_article` einen eigenständigen Nachschub-Auftrag (`orders.reason=
  'replenishment'`, ohne Eltern) an und gibt ihn frei – füllt **auf den Sicherheitsbestand** auf
  (MOQ-gerundet), fährt den Artikel-Prozess (produzieren/beschaffen). *Der frühere separate
  «Zielbestand» (`reorder_target`) ist mit Migration `089` entfallen (Notiz #221): zwei Zahlen
  für dieselbe Frage, von denen die zweite fast immer leer blieb.* Reuse von
  `orders.release_order` (wie ADR-003-Nachschub, nur ohne Pegging), idempotent (ein offener Nachschub je
  Artikel). **Auslöser** reaktiv (nach Bestandsabgang – `scrap.record_scrap` ruft `check_article`) +
  periodisch über `POST /api/v1/erp/maintenance/sweep` (`replenishment.evaluate_all`, Personal-Knopf
  «Lagerwartung», künftig Cloud Scheduler). Der Sicherheitsbestand ist **auch am
  freigegebenen Artikel tunebar** (operative Steuergrössen, nicht eingefrorene Spezifikation).
  *Die frühere MHD-/Haltbarkeits-Achse (`instances.expires_at`, `articles.shelf_life_days`,
  `services/expiry.py`) ist bewusst entfernt (Migration 061) – eine Instanz „läuft" nicht mehr ab.*
- **Wiederkehrende Aufträge klonen Prozess + Subjekt (Wartung)**: `process._spawn_recurrence` zieht beim
  Abschluss den nächsten Auftrag (Entwurf) nach und erbt jetzt zusätzlich (a) die **auftrags-eigenen
  Prozessschritte** (via `deactivation._copy_steps`, `src_order_id`→`dst_order_id`) und (b) **dieselben
  gewählten Subjekt-Instanzen** (z. B. die zu wartende Maschine – in `recompute_completion` vor dem Lösen
  der Bindung erfasst, auf den Kind-Auftrag `subject_of_order_id` gepinnt, bei dessen Freigabe erneut
  reserviert). So läuft eine **wiederkehrende Wartung mit Prozess-im-Auftrag** vollständig weiter statt
  leer; ein reiner Erzeugungs-/Abo-Auftrag verhält sich unverändert (kein eigener Schritt → Artikel-Prozess).
- **Passkeys / passwortlose Anmeldung (WebAuthn/FIDO2, `docs/passkeys.md`)**: Firebase hat keinen nativen
  Passkey-Provider – die WebAuthn-Zeremonie läuft im Backend (`services/passkey.py`, `py_webauthn`), bei
  Erfolg wird ein Firebase **Custom Token** ausgestellt (`signInWithCustomToken`) → ab da normale Firebase-
  Session, restlicher Auth-Fluss unverändert. Modelle `webauthn_credentials`/`webauthn_challenges` (Migration
  `065`), Endpunkte unter `/api/v1/auth/passkeys` (register/login options+verify, list, delete). **RP-ID +
  Origin werden pro Request aus dem `Origin`-Header abgeleitet** und gegen `cors_origins` geprüft (multi-
  domain: localhost/dev/prod ohne feste Verdrahtung); Challenges sind DB-basiert (Cloud-Run-sicher, einmalig,
  5 min). Frontend: `lib/passkey.ts` + `@simplewebauthn/browser`, Login-Button «Mit Passkey anmelden»,
  Konto → Sicherheit «Passkeys» (hinzufügen/entfernen). **Deployment-Hinweis:** der Cloud-Run-SA
  braucht `roles/iam.serviceAccountTokenCreator` (Custom-Token-Signierung, siehe Doc).
- **Login-UX «state of the art, schlank & reibungslos» (Juli 2026)**: Der Anmelde-Flow ist auf Passkey-
  first getrimmt (Vorbild: SBB). (1) **Passkey-Autofill / Conditional UI** (`lib/passkey.
  loginWithPasskeyAutofill`, `passkeyAutofillSupported`, `cancelPasskeyAutofill`): das E-Mail-Feld trägt
  `autocomplete="email webauthn"`, beim Laden startet **still** eine `mediation:'conditional'`-Zeremonie
  (`useBrowserAutofill:true`) → der Passkey erscheint DIREKT im Autofill-Dropdown, ein Tap + Face/Touch ID
  meldet an, ganz ohne Knopf (Backend war schon usernameless: `login_options` ohne `allowCredentials`,
  `resident_key=REQUIRED`). Abbruch beim Verlassen via `WebAuthnAbortService`. (2) **Login-Seite reduziert**:
  zufällige `ix-var`-Optikvarianten entfernt, `Fingerprint`-Symbol statt `KeyRound`, Passkey-Knopf **über**
  Google (der schnelle Weg), dezenter Hinweis unter dem Feld; `Magic Link`→«Anmeldelink senden».
  (3) **Post-Login-Nudge** (`components/auth/passkey-nudge.tsx`, in ERP-/Konto-/Public-Layout gemountet wie
  das ConsentGate, aber **nicht** blockierend): direkt nach einem Login OHNE Passkey ein dezenter,
  wegklickbarer Anstoss «In Sekunden anmelden – Passkey einrichten» (nutzen-, nicht angst-orientiert; der
  stärkste Adoptions-Hebel). Erscheint NUR, wenn Plattform-Authenticator vorhanden **und** 0 Passkeys
  **und** kein Cooldown (localStorage `inexxio_passkey_nudge`: 30 Tage Ruhe nach «Später», max. 3×, dann
  nie mehr). (4) **Freundlicher Gerätename** aus dem User-Agent (iPhone/Mac/Windows-PC …) statt «Passkey 1»
  (`friendlyDeviceName`). (5) **Verify-Seite + Konto-Sicherheit** auf Design-Tokens + einheitlichen
  Karten-Look migriert; erster Passkey = roter CTA «Passkey einrichten», weitere dezent.
- **Cookie-/Einwilligungs-Layer (schlank, professionell, `docs/passkeys.md §2`)**: Erstanbieter-Consent
  ohne Fremd-CMP. `lib/consent.ts` (eine Wahrheit, Cookie `inexxio_consent` + localStorage, versioniert,
  6 Monate, Event-basiert); `components/consent/cookie-consent.tsx` (nicht blockierendes Banner +
  Einstellungs-Dialog, ZWEI ehrliche Kategorien: **Notwendig** immer aktiv + **Statistik** optional,
  «Ablehnen» = «Akzeptieren», keine Dark Patterns). **Plausible lädt erst mit Statistik-Einwilligung**
  (`components/analytics/plausible.tsx`, Domain aus `plausible_domain`; CSP in `firebase.json` um
  `plausible.io` erweitert). Footer-Link + Datenschutz-Button «Cookie-Einstellungen» (jederzeit
  widerrufbar). Datenschutz-Seite (Ziffer 3) auf den realen, cookie-armen Footprint aktualisiert.
- **UX-/Konsistenz-Runde (Juli 2026, deployt)**: (1) **KI-Artikelanlage validiert wie das Formular** –
  `ai/tools._clean_article_fields` schickt jede von der KI angelegte/aktualisierte Artikel-Spez durch die
  **echten** Pydantic-Validatoren (`schemas/article`: `clean_article_name`/`normalize_size`/`validate_weight`,
  Einheiten/Serialisierung-Whitelist); Fehler kommen als `{error,hint}` zurück → die KI korrigiert sich
  selbst (kein «15cm» mehr, Grösse mm/aufsteigend/×-getrennt, Gewicht in kg). Neues rechte-gescoptes
  Read-Tool `article_name_suggestions` (Dubletten vermeiden statt neu erfinden); Tool-Schemas + Prompt
  (`registry.PROMPT_VERSION`) präzisiert. (2) **Status auf reine Ampel konsolidiert** (`lib/status-flow.TONE`
  = nur noch pending=GELB/warning, done=GRÜN/success, danger=ROT/danger – die früheren Töne `info` (Slate)
  und `inactive` (Grau) sind entfallen): **In Bearbeitung/Reserviert/Offeriert/Bestellt/Bestätigt/Verrechnet
  = GELB**, **Inaktiv/Verschrottet = ROT** («Stopp/nicht verwendbar»), **Verkauft/Verbaut = GRÜN**. Die
  hartkodierten Blau/Petrol/Violett-Ausreisser (Instanz consumed/sold, Prozess-Stepper, PurchaseProgress,
  Dokument-Stufen, Rollen-Badges, Primär-Buttons) sind alle auf Tokens gezogen; Rollen-Badges sind neutral
  (Identität, keine Ampel), Primär-CTA = Rot (Design-System).
- **Status-NAMEN konsolidiert (Runde 2)**: gleiche Lebensphase → **dasselbe Wort**, überall.
  Auftrag «In Bearbeitung» **und** Instanz «Im Prozess» heissen beide **«In Arbeit»** (zwei Namen → einer;
  auch in der Kunden-Bestellliste `orders-list.tsx`); Instanz «Verbraucht» → **«Verbaut»** (passt zu
  «Verkauft»); Dokument «Freigaben laufen» → **«In Freigabe»**. Rollen-Badges + Unternehmens-Badge sind
  **grün** statt grau (ein aktiver Datensatz ist gültig; Grau läse sich als «aus»). (3) **Datenerfassung**: der Bug «Unterschrift konfiguriert, trotzdem Foto-Aufnahme
  angeboten» ist weg – Foto/Unterschrift sind reine `capture_fields`-Typen, der unbedingte `PhotoCapture`-
  Block je Probe ist entfernt. (4) **Auftrag-Shortcut**: kleiner Kopf-Knopf «Auftrag anlegen» am
  freigegebenen **Artikel** (neben Deaktivieren/Ersetzen) und an der **Instanz** (neben Abweichung) – legt
  den Auftrag an, fixiert bei der Instanz gleich diese als Subjekt, und springt hin (`ClipboardPlus`,
  `erp-idbtn`). (5) **Auftrag-Detail entschlackt**: die Subjektart-Zeile («Herstellung – erzeugt Instanzen»)
  und der Abschluss-Text sind entfernt; die **Abweichung** ist jetzt – wie an der Instanz – ein kleiner
  Flag-Knopf im Detail-Kopf (`erp-idbtn-flag`) statt einer Karte mitten im Feld. (6) **Bewegung/Versand**:
  siehe ADR-005-Bullet – der frühere «komisch differenzierte» Split (Klasse-Chip + auto/carrier/self/none-
  Select + Paket/Fracht-Toggle) ist EIN **3-Wege-Umschalter Im Betrieb | Paket | Fracht** mit markierter,
  abgeleiteter Empfehlung.
- **Testnotizen – «Pin setzen» statt Befunde dokumentieren** (Juli 2026, `docs/feedback.md`,
  Migration `082`): Beim Testen fallen laufend Dinge auf; teuer ist nicht das Erkennen, sondern das
  **Rekonstruieren des Kontexts** (wo war ich, welcher Datensatz, welche Rolle, was hat der Browser
  gemeldet). Ein Launcher unten **links** (die KI sitzt rechts) öffnet die Notizen der Seite;
  «Notiz anheften» schaltet in einen **Zeigemodus** (Element unter dem Cursor wird umrandet, Klick
  heftet die Notiz daran, `Esc` bricht ab), Kommentar tippen, Enter. **Sichtbar nur in der
  Testumgebung** (`NEXT_PUBLIC_ENVIRONMENT`/`APP_ENV`; die Produktion antwortet 404) und bewusst für
  **JEDE angemeldete Rolle** – auch aus Kunden-/Lieferantensicht muss gemeldet werden können.
  **Die Brücke vom Pixel zum Code sind nicht Koordinaten/Screenshots, sondern Text + DOM-Signatur:**
  die Oberfläche ist deutschsprachig, ihre Beschriftungen stehen im Repo meist genau einmal – der
  sichtbare Text des geklickten Elements (`anchor.label`) ist damit der beste greppbare Anker
  (dazu Selektor-Kette ohne Klassennamen, gekapptes `outerHTML`, relative Position `rx`/`ry`).
  Automatisch mitgeschnitten ausserdem: Route, **Objektnummer des offenen Datensatzes**, Rolle,
  Viewport, **Build-Commit** (`NEXT_PUBLIC_COMMIT_SHA`) und die letzten 5 Laufzeitfehler (Ringpuffer
  aus `error`/`unhandledrejection` – **kein** Monkey-Patching von `console.*`). Pins sitzen an ihren
  Elementen, solange die Liste offen ist (Ampel: offen gelb · erledigt grün · verworfen grau) –
  damit wird ein Fix **am Ort des Befunds** verifiziert statt aus einer Liste heraus.
  **Kein Geschäftsobjekt:** `feedback_notes` hat **keine Objektnummer**, keinen Feed, keinen
  Event-Strom und kein Audit-Log (Einordnung wie `ai_actions`/`attachments`); die Referenz auf den
  offenen Datensatz heisst darum `target_object_id` wie bei `AiAction` – `object_id` ist im System
  immer die EIGENE Nummer eines Datensatzes. Sichtbarkeit: Personal sieht alles, jede andere Rolle
  nur die eigenen Notizen. Weiterverarbeitung über **«Alle offenen Notizen als Markdown kopieren»**
  → Einfügen in eine Entwicklungs-Sitzung (Skill `.claude/skills/feedback/`); Wächter
  `tests/test_feedback.py`. *Bewusst NICHT gebaut: GitHub-Issue-Sync (Token im Backend = zweite
  Wahrheit), `html2canvas`-Screenshot, flächendeckende `data-*`-Anker, Voting/Threads/Kanban.*
  **Runde 2 (Präzision + Aufräumen):** (1) **Der Feed ist ein Master-Detail auf EINER Route** –
  `/erp` bleibt `/erp`, egal welcher Datensatz offen ist (`?open=` ist nur der Deep-Link von
  aussen). Notizen aus dem Detailfenster trugen darum **keine Objektnummer**; jetzt meldet die
  ERP-Seite ihre Auswahl an `feedback.setOpenRecord` (EINE Stelle: der `sel`-Effekt in
  `erp/page.tsx`), und `currentObjectId` zieht sie der URL vor. (2) **Dynamische Listen**
  (Prozess-Editor: sortierbare Schritte) machen eine `nth-of-type`-Kette wertlos – sie sagt nur
  «der dritte Block». Deshalb markieren sich `PanelHeader`/`SectionTitle` mit `data-fb-section`
  und der aktive Reiter (`DetailTabs`) mit `data-fb-tab`; die Notiz trägt jetzt
  **`context.view`** («Auftrag · Ablauf») und **`anchor.section`** («Bewegung») – beides
  positions**un**abhängig. (3) **Löschen/Zurücksetzen** (vorher gar nicht möglich):
  Papierkorb je Notiz, «Erledigte aufräumen» und «Alles zurücksetzen» (zweiter Klick bestätigt)
  – `DELETE /api/v1/feedback/{id}` bzw. `?scope=done|all`, **weich** (`is_active=false`) und
  über `visible_query` gescopt, damit niemand fremde Notizen wegräumt.

- **Testnotizen-Runde 1 (Instanz-Detail entdoppelt, Notizen #1–#6)**: erste über das Notiz-Widget
  gemeldete Befunde, alle Frontend. Kern war **Doppelung des Zustands**: die Statusbadge im Kopf
  einer Instanz ist bereits die Projektion beider Achsen (`quality`+`disposition`) – die Kachel
  «Letzte Bewegung» zeigte exakt dieselbe Beschriftung noch einmal (entfernt), und die Unterzeile
  der Bestands-Kachel schrieb sie ein drittes Mal aus («Qualität: durchgefallen», «Verkauft», …).
  Sie erklärt jetzt nur noch die **Zahl** (`Nicht am Lager` · `Am Lager` · `N reserviert` – die
  reservierte Menge steht nirgends sonst). Gleiches Muster im Bewegungs-Panel: das grüne Banner
  «Bewegung abgeschlossen» ist weg – dass der Schritt erledigt ist, sagt der Auftrags-Stepper
  (Symbol + Wer/Wann im Hover), im Panel zählt das Ergebnis. **Kachel-Raster:** das Raster war
  durchgehend in der Linienfarbe eingefärbt (Haarlinien über `gap: 1`), wodurch eine
  unvollständige letzte Reihe als **grauer Block** erschien; jetzt trägt jede Kachel ihre eigene
  Haarlinie und steht in Weissraum (Mindestspalte 160→260 px, damit auf breiten Schirmen keine
  schmalen Streifen entstehen). Die **Standort**-Karten sitzen im selben Raster (volle Breite)
  statt als eigene Karten darunter – möglich geworden durch `TileShell` in `fields.tsx`, das die
  dreifach kopierte Kachel-Anatomie zusammenführt. Homepage-Headline: «Industrie 4.0».

- **Testnotizen-Runde 2 (Artikel/Verkauf/Benutzer, Notizen #7–#22)**: (1) **Kennzahlen zeigen
  den Median** (`services/metrics.py: spread` → `(median, low, high)`, EINE Stelle für Lieferzeit
  UND Einstandspreis): ein einzelner Eil-Auftrag oder eine Kleinstmenge zu Apothekerpreisen zieht
  einen Mittelwert weg – der Median bleibt bei dem, was üblich ist. Die Spanne steht untergeordnet
  darunter («kürzeste … · längste …») und nur, wenn sie etwas Neues sagt.
  (2) **Kein Abschnitt «Beschaffung» in der Artikel-Spezifikation** mehr: WIE beschafft wird, steht
  ausschliesslich am Beschaffungs-Schritt im Reiter «Prozess»; geblieben sind ein Abschnitt
  **«Kennzahlen»** (abgeleitet) und die optionalen Angaben in der Basis-Gruppe.
  (3) **Verkauf-Reiter Symbol-first**: alle Wahlmöglichkeiten (Status · Sichtbarkeit · Verfügbarkeit ·
  Preisart · Intervall · Abo-Typ) sind EINE Zeile Symbol-Chips (`IconChoice`) statt Dropdown/Segment,
  jede Erklärung sitzt im **Hover** statt als Absatz in der Fläche; der **Vergleichspreis** ist
  entfallen (soll später automatisiert kommen), das Anlegen eines Preises läuft über **Auto-Save**
  statt Speichern/Abbrechen (bewusst längere Denkpause von 2,5 s, damit keine halb getippte Zahl
  committet wird). Die Datei ist dabei von der Alt-Palette (`#2563eb`/slate) auf Tokens migriert.
  (4) **Benutzer-Datensatz**: «Bestätigungen»-Karte und die AGB-Felder im System-Block entfernt –
  der Reiter **Dokumente** führt das vollständig (der nur dafür gebaute Endpunkt
  `GET /consent/acknowledgements/{id}` ist mit entfallen); neu **«Anmeldung»** (Google SSO ·
  Passkey · Anmeldelink · Passwort, aus `firebase.sign_in_provider`, Migration `083`) und
  **«Passkeys»** (Anzahl Geräte, eine gruppierte Abfrage). **Spiegel-Abgleich mit den
  Profileinstellungen** (Notiz #20): die Benachrichtigungs-Schalter sind auch im ERP entfernt (sie
  hatten nie Backend-Wirkung und fehlen im Profil längst), und die **Rechnungsadresse** erscheint
  jetzt für JEDE Rolle statt nur für Kunde/Lieferant – bei einer Mitarbeiterin sah das Personal
  ihre eigenen Eingaben sonst nicht.
  (5) Kleineres: Bestandsliste ohne Summenzeile + zentriert, Instanz-Detail auf allen Reitern
  zentriert, Auftrag-Shortcut getönt wie der Abweichung-Knopf (`.erp-idbtn-act`), Prozess-Schritt
  nennt nur noch den Prüfumfang (nicht die Zahl der Erfassungsfelder), Homepage-Headline.

- **Testnotizen-Runde 3 (Auftrag-Bedarf & Ablauf, Notizen #23–#31)**: (1) **Quelle als Schieber**
  (`SourceSwitch`): EIN Gleis mit gleitendem Reiter statt drei gleich aussehender Knöpfe – dass die
  Optionen einander ausschliessen, zeigt jetzt die Bewegung statt ein Erklärsatz; gesperrte Felder
  bleiben sichtbar und nennen den Grund im Hover. (2) **«Erzeugen» zeigt den Artikel-Prozess**
  (`ProcessSteps owner="articles" readOnly`) – **1:1-Spiegelung, keine Kopie**: dieselbe Komponente,
  dieselben Daten, nur lesend; geändert wird am Artikel. Vorher wurde die Aussage «der Artikel-Prozess
  läuft» nur behauptet. (3) **Ablauf sieht aus wie der Prozess-Reiter am Artikel** – die zusätzliche
  Karte um `ProcessSteps` ist weg (gleicher Editor ⇒ gleiche Optik), an allen drei Stellen
  (Ablauf, Unter-Auftrag, Spiegel). (4) **Instanz-Auswahl ist durchsuchbar** (ab 8 Instanzen
  Suchfeld nach Objektnummer + scrollende Liste) – bei dreistelligen Beständen war die Chip-Wolke
  nicht mehr bedienbar. (5) **«Wiederkehrend» ohne Häkchen und ohne Speichern-Knopf**: die Periode
  IST der Schalter (leer = einmalig), Auto-Save wie überall, und der Zustand steht als **Satz**
  darunter statt als Schalterstellung. Der widersprüchliche Zustand «angehakt, aber keine Periode»
  existiert damit nicht mehr. (6) **Zahlenfelder lassen nur Zahlen zu** (`fields.numericOnly` +
  `numericInputProps`, die EINE Regel): Komma→Punkt, höchstens ein Trenner, bewusst KEIN
  `input type="number"` (dessen Spinner/Scrollrad stören, und bei ungültiger Eingabe liefert es
  einen leeren Wert – getippte Zeichen verschwinden spurlos). Verdrahtet an Auftrags-Menge,
  Ressourcen-Zeile, Prüfumfang, Messwert, Wiederkehr-Perioden. (7) **Datensatz-Auswahlen zeigen die
  grösste Nummer zuerst** (`SearchSelect: newestFirst`) – Objektnummern werden aufsteigend vergeben,
  gemeint ist fast immer ein zuletzt angelegter Datensatz; greift nur, wenn alle Werte Zahlen sind.
  *Bewusst NICHT geändert: der «Freigeben»-Knopf bleibt **rot**. Rot ist im Design-System der EINE
  laute CTA-Akzent; Grün ist die Farbe des ZUSTANDS «freigegeben/erledigt». Wäre die Aktion grün,
  hiesse dieselbe Farbe gleichzeitig «tu es» und «ist getan» – die Badge daneben wird nach der
  Freigabe grün, das ist die Rückmeldung.*

- **Testnotizen-Runde 4 (Prozess-Editor & Datenerfassung, Notizen #32–#51)**: (1) **Eine
  durchgefallene Datenerfassung ist nicht mehr terminal** (#51, der einzige offene Punkt aus
  `docs/review-2026-07.md`): `all_steps_done` verlangt je Schritt `done` – ein Schritt auf
  «fehlgeschlagen» verhinderte den Abschluss **für immer**. Der Weg nach vorn ist jetzt gebaut:
  Abweichung klärt den Fall (nacharbeiten/verschrotten/ersetzen) → **«Erneut erfassen»** im Panel →
  neue Bewertung. Damit das etwas ändern kann, läuft `_apply_per_instance_qc` bei **jedem** Ergebnis
  (nicht nur beim Nichtbestehen) und **löst eine frühere Sperre** (`failed` → `pending`, nie direkt
  `passed` – freigegeben wird weiterhin erst beim Auftrags-Abschluss). Wächter
  `test_smoke.py: test_failed_inspection_is_not_terminal`. (2) **Datenerfassung ohne Erfassungsfeld
  ist keine mehr** (#41): Schema-Prüfung analog zur Ressource-Zeile (nicht nur im Formular) – ein
  solcher Schritt böte im Auftrag nichts zu erfassen. (3) **Prüfumfang als Voreinstellungen** (#36,
  #37): Chips «Alle · Jedes 2. · Jedes 4. · Stichprobe» statt Prozentfeld mit Erklärsatz; «…» blendet
  ein Zahlenfeld für Sonderwerte ein (ein gespeicherter Sonderwert geht nie verloren). (4) **Gut/
  Schlecht als Daumen** (#42), **eigene Farbfamilie für die Datenerfassung** (#44 – sie trug exakt
  die Tönung der Bewegung). (5) **Weniger Text, mehr Hover**: Bezugsquelle als **symbol-only
  Schieber** (#47, generischer `fields.IconSwitch` – dieselbe Mechanik wie der Bedarf-Schieber),
  Ressourcen-Legende (#45), Beschaffungs-Infotext (#48), Lieferanten-Hinweis (#49) und der
  Bild/Unterschrift-Kasten (#38) entfallen; «+ Ressource/Erfassungsfeld» wird zum blossen **«+»**,
  sobald die Liste nicht leer ist (#46); Headline «Für Lieferant sichtbar» (#50). (6) **Auswahl
  neueste zuerst repariert** (#34): `newestFirst` verlangte, dass ALLE Werte Zahlen sind – der
  Platzhalter «— wählen —» hat die Sortierung damit überall stillgelegt. Platzhalter bleiben jetzt
  vorn, der Rest wird sortiert. (7) **Namensgebung vereinheitlicht**: «Adresszeile 1/2» → **«Strasse
  und Hausnummer» / «Adresszusatz»** wie in den Profileinstellungen (#33); Verkauf «Publiziert/
  Entwurf» → **«Nicht sichtbar / Sichtbar»**, Ausgangszustand links (#32). (8) Ziel-Angabe am
  Bewegungsschritt: **Objektnummer zuerst**, dann die Bezeichnung (#43); Wiederkehr zeigt nur noch
  «Aktiv · alle N Tage» statt eines Erklärsatzes (#35).
  *Bewusst NICHT geändert: der «Hinzufügen»-Knopf im Schritt-Editor bleibt (#40) – Auto-Save würde
  einen halb konfigurierten Schritt anlegen, und genau das verbietet #41.*

- **Testnotizen-Runde 5 (Sperren-Modul, Notizen #52–#68)**: Kern ist ein **neuer Schritttyp
  `block` = «Sperren»** (#59) – das **reversible Gegenstück zum Verschrotten**: nicht alles, was
  aus dem Verkehr muss, ist Ausschuss (die defekte Maschine wartet auf ihre Wartung, das
  fragliche Los auf ein Laborergebnis). **Modelliert auf der Qualitäts-Achse**
  (`instances.quality='blocked'`), NICHT auf der Verbleibs-Achse: eine Sperre ändert nicht,
  *wo* etwas ist, sondern ob man es *verwenden darf*. Das ist der ganze Trick – weil
  `inventory.in_stock_clauses()` ohnehin `passed` UND `in_stock` verlangt, fällt eine gesperrte
  Instanz **ohne eine einzige zusätzliche Abfrage** aus FIFO, Verfügbarkeit, Bestandszählung und
  Reservierbarkeit; und weil `quality` von Natur aus veränderlich ist, ist die Rücknahme
  eingebaut statt nachgerüstet. Verschrotten dagegen ist `DECREASE`/terminal, standortlos und
  löst alle Reservierungen – Sperren ist `NEUTRAL`, lässt Standort, Menge und Reservierungen
  **unangetastet** (das Teil gehört weiterhin seinem Auftrag, es ist nur gerade nicht benutzbar).
  Schema-seitig kostet das **eine** Spalte: `disposals.mode` ∈ scrap|block (Migration `084`,
  `quality` ist ein freies VARCHAR). **Ein Panel, zwei Wirkungen** (`scrap-panel.tsx` mit
  `mode`-Prop) – die Instanz-Auswahl ist identisch, nur das Ergebnis nicht; Teilmengen gibt es
  nur beim Verschrotten (eine halbe Charge sperren hiesse, sie zu teilen). **Aufgehoben wird an
  der Instanz, nicht im Prozess** (`POST /erp/instances/{id}/unblock`, Knopf nur bei
  `quality='blocked'`): eine Maschine kommt aus der Wartung zurück, ohne dass jemand dafür einen
  Auftrag anlegen will. Der Zustand danach wird **abgeleitet statt gemerkt**
  (`scrap._restore_quality`: `released_at` gesetzt → `passed`, sonst `pending`) – kein
  verstecktes «vorherige Qualität»-Feld, das auseinanderlaufen könnte. Nur im **Auftrags**-Ablauf
  zulässig (wie `scrap`), Wächter `test_smoke.py: test_block_is_reversible_scrap_is_not`.
  **Wortschärfe im gleichen Zug:** `quality='failed'` hiess bisher ebenfalls «Gesperrt» – kurzzeitig
  hiess es dann «Durchgefallen» und stand neben «Gesperrt». *Runde 6 hat die beiden zu EINEM Zustand
  zusammengeführt (Migration `085`) – siehe unten.* Daneben: (2) **Ein Prozessschritt wird nicht mehr nachträglich umkonfiguriert** –
  die Sonderfälle «Sichtbare Felder» und «Dokument-Deklaration» hielten als einzige Module einen
  Bearbeiten-Zustand am Leben; wie überall sonst gilt jetzt löschen + neu anlegen. (3)
  **Lieferant am Beschaffungs-Schritt ist klickbar** (`ArticleProcessStepResponse.
  supplier_object_id` – `supplier_id` ist der INTERNE Schlüssel und darf nie als Objektnummer
  erscheinen), Symbol statt Wort. (4) **Dokument-Deklaration symbol-first**: Sichtbarkeit
  (Alle · Intern · Vertraulich) und Anerkennungs-Publikum (Niemand · Alle · Rollen · Personen)
  als `IconSwitch` mit Hover-Erklärung statt Segmented+Erklärsatz. (5) **Benutzernummer ist kein
  Formularfeld** – sie ist vergeben und unveränderlich, steht also als Versalien-Label +
  monospaced Nummer da statt in einem Eingabefeld, das zum Hineinklicken einlädt; dazu zwei
  Erklärkästen im Konto entfernt bzw. auf eine Zeile eingedampft.
  *Bewusst NICHT geändert (#68, wie #40): der «Hinzufügen»-Knopf bleibt – Auto-Save legte einen
  halb konfigurierten Schritt an, was #41 gerade verbietet.*

- **Testnotizen-Runde 6 (Sackgassen im Auftrag, Notizen #70–#75, Migration `085`)**: Fünf der
  sechs Befunde waren **derselbe Bug in verschiedenen Ausprägungen** – ein Auftrag, der nach
  einer fehlgeschlagenen Datenerfassung nicht mehr weiterkam.
  (1) **«Gesperrt» ist EIN Zustand mit EINEM Wort** (#73): eine durchgefallene Instanz trug
  `quality='failed'`, eine bewusst ausgesetzte `quality='blocked'`. Beides heisst «vorhanden,
  aber nicht verwendbar», beides fällt über dieselbe Bedingung aus FIFO/Bestand, beides ist
  aufhebbar – nur die Namen waren verschieden. Geschrieben wird jetzt **nur noch `blocked`**,
  `failed` wird tolerant GELESEN (Altbestand; Migration `085` zieht ihn nach). Damit es EINE
  Stelle bleibt, geht jeder Lesezugriff über `inventory.is_blocked()`/`unblocked_clauses()`
  statt über einen handgeschriebenen Vergleich (dieselbe Zwei-Formen-Regel wie
  `in_stock_clauses`/`is_in_stock`).
  (2) **Ein fehlgeschlagener Befund wird vom Folgeauftrag geklärt – von sonst nichts** (#70,
  #71). `all_steps_done` verlangt je Schritt `done`; ein Schritt auf «fehlgeschlagen» blieb es
  für immer → der Auftrag schloss **nie** ab und seine Instanzen wurden **nie** freigegeben
  (genau #71: die Abweichung lief korrekt durch, die Charge hing trotzdem in «In Arbeit»).
  Runde 4 hatte dafür einen Knopf «Erneut erfassen» ins Panel gesetzt – der ist **entfernt**
  (#70: «nur ein Folgeauftrag darf das») und war ohnehin eine Sackgasse, weil
  `resolve_exec_step` nur **aktive** Schritte ausführt und ein fehlgeschlagener das nicht ist
  (409). Stattdessen: schliesst die **Abweichung** ab, vermerkt `inspection.resolve_failed_by`
  den Klärer auf dem Befund (`inspections.resolved_by_order_id`), und `_fact_status` liest den
  Schritt als `done`. **Der Befund selbst bleibt `failed`** – was gemessen wurde, wird nicht
  nachträglich schöngeschrieben; die Klärung steht als eigener, nachvollziehbarer Vorgang
  daneben (Panel: «Geklärt durch <Objektnr>»).
  (3) **Der Prüfumfang bemisst sich an der geprüften MENGE, nicht an der Zahl der Subjekte**
  (#72): `required_count` rechnete mit `order.quantity`. Eine Abweichung auf EINE Charge à
  5 Stk trägt aber `quantity=1` (ein Subjekt) – bei «jede» kam so statt fünf Proben nur eine.
  Stichprobenzahl und Stichprobenziele stammen jetzt aus **derselben** Quelle
  (`inspection.inspected_quantity` → `order_active_instances`) und können nicht mehr
  auseinanderlaufen; `create_deviation` deklariert die Menge ebenfalls als Summe der
  Instanz-Mengen statt als deren Anzahl.
  (4) **Eine Bereitstellung ist keine Abweichung** (#75): `instance_open_deviation` filterte
  nicht auf `reason` – damit galt **jeder** Unter-Auftrag als «offene Abweichung», auch die
  automatisch abgeleitete **Bereitstellung** (`reason='provisioning'`, ein Unter-Auftrag mit
  genau einem Bewegungs-Schritt: exakt das «Folgeauftrag …475 mit aktivem Bewegen-Modul», das
  niemand angelegt hatte). Ein Abbruch scheiterte an dieser falschen Meldung. Jetzt zählt nur
  `reason='deviation'` – derselbe Filter, den `open_deviations` längst hatte.
  (5) **Der Feed zeigt den Status des Auftrags, nicht den seiner Bestellung** (#74): bei einem
  freigegebenen Auftrag schlug der **Beschaffungs**-Status durch – ein Auftrag, dessen
  Bestellung geliefert war, stand auf «Geliefert», obwohl Prüfung, Bewegung und Verkauf noch
  offen waren. Der Stand eines einzelnen Schritts ist nicht der Stand des Auftrags; er steht
  im Detail am Ablauf.
  Wächter: `test_smoke.py: test_failed_inspection_is_not_terminal` (erweitert),
  `test_blocked_is_one_state_with_one_word`, `test_only_a_deviation_counts_as_an_open_deviation`,
  `test_sample_size_comes_from_the_inspected_instances`.

- **Unter-Aufträge: sichtbar, abbrechbar, sauber gelöst** (Juli 2026, Folge-Analyse zu Runde 6):
  Drei Lücken desselben Themas – *was das System selbst anlegt, muss der Mensch sehen und wieder
  loswerden können*.
  (1) **Bereitstellungen waren unsichtbar**: `OrderResponse.provisionings` wurde geliefert, aber
  nirgends gerendert – Abweichung/Nachschub/Retoure hatten je eine Karte, die Bereitstellung
  nicht. Sie ist die **einzige automatisch entstehende** Unter-Auftragsart; genau darum muss sie
  sichtbar sein (sonst taucht wie in Notiz #75 ein fremder «Folgeauftrag mit aktivem Bewegen-Modul»
  auf, den niemand angelegt hat). Jetzt eigene Karte im Auftrag-Detail, Erklärung im Hover.
  (2) **Eine steckengebliebene Bereitstellung hat einen Ausweg**: sie blockiert den Schritt UND
  den Abschluss – lief sie nicht durch, war der Auftrag ohne Ausstieg tot. «Abbrechen» am
  Bereitstellungs-Datensatz ist die Aussage «das mache ich von Hand»; damit das hält, legt
  `provisioning.cancelled_for_step` sie **nicht neu an**. Marker ist der **abgebrochene
  Unter-Auftrag selbst** (`status='inactive'` zu diesem Schritt) – kein zusätzliches Feld, keine
  zweite Wahrheit, und das Audit-Log zeigt, wer die Bereitstellung wann übersprungen hat.
  (3) **EINE Aufräum-Stelle für Unter-Aufträge** (`deviation.detach_sub_order`): ein Unter-Auftrag
  hält drei Fäden zum Eltern – Subjekt-Bindung der Instanzen, Verarbeitungs-Links und (beim
  Abbruch-Folgeauftrag) `abort_into_id`. Wer nur den Status auf «inaktiv» setzte, liess alle drei
  stehen: der Eltern blieb **für immer pausiert** (`abort_into_id` nie NULL → auch kein neuer
  Abbruch mehr möglich) und seine Instanzen zeigten auf einen toten Auftrag. Beide Türen –
  «Zurücknehmen» (Entwurf) und «Abbrechen» (freigegeben) – gehen jetzt durch dieselbe Stelle, und
  ein Unter-Auftrag bekommt **nie** einen eigenen Folgeauftrag (sein Subjekt gehört ohnehin dem
  Eltern bzw. er transportiert nur); danach läuft der Eltern automatisch weiter.
  (4) Dazu: **«Abbruch ausstehend» ist im Feed ein eigener Zustand** statt «In Arbeit» – ein
  beantragter Abbruch sah sonst aus, als hätte er nichts bewirkt.
  Wächter: `test_smoke.py: test_sub_order_deactivation_goes_through_one_cleanup`,
  `test_cancelled_provisioning_is_not_recreated`.

- **Abbrechen ist ein Vollzug, kein Antrag – und kein zweiter Knopf** (Juli 2026, Migration
  `086`): Drei zusammenhängende Korrekturen am Abweichungs-Modell.
  (1) **Der Abbruch wirkt sofort.** Bisher blieb das Original `released` («Abbruch ausstehend»)
  und wurde erst inaktiv, wenn der Folgeauftrag freigegeben war; bis dahin liess er sich
  zurücknehmen. Das war als Sicherheitsnetz gedacht, aber falsch herum: *ein Auftrag, den man
  abbrechen kann und der danach weiterläuft, ist nicht abgebrochen.* Jetzt setzt
  `deviation.abort_parent` ihn im selben Moment auf inaktiv – endgültig, keine Reaktivierung;
  nur der Abweichungsauftrag lebt weiter und hält die Instanzen (`keep_instances`).
  `abort_into_id` ist nur noch der Zeiger «fortgeführt in …»; `apply_abort_on_release` und
  `create_abort_followup` sind entfallen, `_is_paused_by_deviation` hängt nur noch an offenen
  Abweichungen. Anzeige: **«Abgebrochen» (rot)** als Projektion über `orderStatusConfig(status,
  aborted)` – «Inaktiv» heisst verworfen, «Abgebrochen» heisst fortgeführt.
  (2) **EIN Vorgang, EIN Wort, EIN Symbol.** «Abbrechen» war ein zweiter Name und ein zweites
  UI für dieselbe Sache (es legte ja einen Abweichungsauftrag an). Die Status-Aktion ist weg;
  es gibt nur noch den Flag-Knopf **«Abweichungsauftrag»**, und der Unterschied ist eine
  **Eigenschaft des Vorgangs** statt eines zweiten Wegs: `OrderDeviationCreate.abort_parent`
  (Dialog: «Auftrag läuft weiter» ↔ «Auftrag abbrechen»). `POST /orders/{id}/abort` bedient nur
  noch das **Verwerfen** eines Unter-Auftrags bzw. eines Auftrags ohne Instanzen – ein anderer
  Vorgang, darum ein anderes Wort.
  (3) **Eine Abweichung darf ihre eigene Abweichung haben.** Die Regel «höchstens EINE aktive
  Abweichung je Instanz» traf auch die Instanzen, die schon in einer Abweichung steckten –
  misslang die Nacharbeit, liess sich das nicht melden. Jetzt gilt sie nur noch für das
  **gleichzeitige** Greifen zweier Vorgänge (`existing.id != parent.id`); die **Kette**
  Abweichung → Abweichung ist erlaubt und bildet die Realität ab.
  Wächter: `test_abort_is_a_deed_not_a_request`, `test_a_deviation_can_have_its_own_deviation`.

- **Eine offene Bereitstellung hält den ganzen Auftrag an – und steht im Ablauf** (Juli 2026):
  Gemeldeter Fall: Erzeugungsauftrag mit Beschaffung + Datenerfassung; die Bereitstellung
  schien erst NACH der Datenerfassung zu entstehen, obwohl sie zwischen die beiden gehört.
  **Der Zeitpunkt war schon richtig** (`purchase` deklariert `PROV_RECEIVING` + Stufe
  «danach» → sie entsteht, sobald die Bestellung geliefert ist). Falsch war die **Reichweite
  der Blockade**: `_step_blocked` fragte `open_provisioning(order, step.id)` – die
  Bereitstellung gehört aber zum **Beschaffungs**-Schritt, nicht zur Datenerfassung, also war
  die Datenerfassung ausführbar, während die Ware buchhalterisch noch beim Lieferanten lag
  (nur der Auftrags-*Abschluss* lief auf sie auf – von aussen sieht das aus wie «zu spät
  ausgelöst»). Jetzt gilt **eine Regel statt einer Fallunterscheidung**: *solange eine
  Bereitstellung offen ist, geht der Auftrag nicht weiter* (`open_provisioning(db, order)`).
  Damit braucht es keine fest verdrahtete Bewegung nach jedem Beschaffungs-Schritt.
  **Darstellung:** die Bereitstellung erscheint als **Knoten im Auftrags-Stepper** an ihrer
  Position – `OrderStepInfo.provisionings` (alle Bereitstellungen des Schritts) +
  `provisioning_stage` ∈ before|after, abgeleitet aus der bereits deklarierten Zeitpunkt-Regel
  (`provisioning._STAGE_BEFORE`). Sie bleibt ein **Unter-Auftrag**, der Knoten ist reine
  Projektion (Klick öffnet den Datensatz, kein Schritt-Panel); das Frontend platziert nur,
  es entscheidet nicht. Wächter: `test_smoke.py: test_open_provisioning_holds_the_whole_order`.

- **Testnotizen-Runde 7 (Auftrag sieht aus wie der Prozess, Notizen #79–#82)**: (1) **Der
  laufende Auftrag zeigt denselben Fluss wie die Definition** (#82, `components/erp/order-
  flow.tsx`): senkrechter BPMN-Fluss mit Start-/Endknoten und einer Karte je Modul – exakt
  die Bildsprache, in der man den Prozess am Artikel definiert hat. Vorher war es ein
  waagrechter Punkte-Stepper: dieselbe Sache in einer **zweiten** Bildsprache, und man musste
  erst übersetzen, welcher Punkt welches Modul ist. Geteilt werden die Fluss-Bausteine
  (`FlowTerm`/`Connector`/`kindColor`/`STEP_MAXW` aus `process-steps.tsx`) – EINE Quelle für
  die Optik. Der einzige Unterschied ist, was eine Karte **zeigt**: dort die Konfiguration,
  hier der Zustand (Erledigt · In Arbeit · Angehalten · Wartet · Fehler) und im Hover Wer/Wann.
  Die abgeleiteten **Bereitstellungen** sind Karten an ihrer Position im Fluss und öffnen ihren
  Datensatz (sie sind Unter-Aufträge, kein Modul). `process-stepper.tsx` + `toStepperState`
  sind damit ersatzlos entfallen. (2) **Der Auftrags-Kopf hat dieselbe Anatomie wie Artikel und
  Instanz** (#79): Symbol · Eyebrow · Titel · Objektnummer + Symbol-Aktionen in EINER Zeile,
  rechts Speicher-Anzeige und Status. Die Objektnummer stand vorher als eigener Kasten ganz
  rechts – ein drittes Layout für dieselbe Sache. (3) **Kein «Verwerfen»** (#81): ein
  Unter-Auftrag ist eine bewusste Entscheidung und wird durchgezogen, nicht weggeworfen. Die
  **einzige** Ausnahme ist die **Bereitstellung** – sie legt das System selbst an, also braucht
  sie einen Ausstieg; er heisst jetzt **«Bereitstellung übergehen»** (Symbol im Kopf) und sagt
  damit, was man entscheidet, statt generisch «verwerfen» zu heissen.

- **Testnotizen-Runde 8 (der Auftrag ist der Prozess, Notizen #83–#90, Migration `087`)**:
  (1) **Der Schritt wird dort bearbeitet, wo er im Fluss steht** (#84): die gewählte Modul-Karte
  klappt ihr Panel **in sich selbst** auf – dieselbe Anatomie wie die Konfiguration in der
  Definition. Der abgespaltene Container darunter ist weg, ebenso der Karten-Hintergrund um den
  Fluss (#83): ein Fluss aus Karten braucht keine Karte drumherum.
  (2) **Zustand ohne Wort** (#88): erledigte und noch nicht erreichte Schritte treten zurück
  (weisse Fläche, gedämpft), nur was JETZT dran ist, trägt seine Modulfarbe. Dazu ein Symbol
  statt eines Status-Textes – Haken (erledigt), Pause (angehalten), Kreuz (Fehler); Wer/Wann
  bleibt im Hover.
  (3) **Abweichungen stehen an ihrer Stelle im Ablauf** (#85): `orders.origin_step_id`
  (vormals `provisioning_step_id`, Migration `087`) beantwortet für **jede** Unter-Auftragsart
  dieselbe Frage – aus welchem Schritt ist er hervorgegangen? `create_deviation` schreibt den
  gerade aktiven Schritt hinein; der Fluss rendert die Abweichung als **dezenten Abzweig**
  (schmale Pille mit Aststück) statt als Karte über dem Prozess.
  (4) **«Auftragsspezifikation» statt «Bedarf», immer zuoberst** (#87) – und die bei der
  Freigabe entstandenen **Instanzen stehen in derselben Karte** (#86, `OrderInstances
  embedded`) statt in einer zweiten darunter: sie sind das Ergebnis derselben Aussage
  (Artikel + Menge), kein neues Thema.
  (5) **«In Arbeit» gibt es nicht mehr** (#89/#90): der EINE Name für «läuft gerade» ist
  **«Im Prozess»** – beim Auftrag, bei der Instanz, im Prozessschritt und in der
  Kunden-Bestellliste.
  (6) **Das Notiz-Werkzeug liegt über allem** (`z-[2000]`+): Dialoge/Lightboxen (bis `zIndex 70`)
  verdeckten den Launcher – ausgerechnet dort, wo man beim Testen gerade steht, liess sich
  nichts melden. Der Zeigemodus funktionierte schon immer über Overlays hinweg (Handler in der
  **Capture**-Phase am `document`), nur sichtbar war er nicht.

- **Testnotizen-Runde 9 (Kamera-first scannen, Panel entschlackt, Notizen #91–#104)**:
  (1) **Der Scan-Dialog IST die Kamera** (#94–#99, `components/scan/scan-dialog.tsx`): kein
  Kopf, kein Titel, kein Erklärtext, kein zweiter Kasten – die Sheet-Fläche ist der
  Kamerastrom, alles Weitere liegt darüber. Im Zielrahmen tastet ein **Suchstrahl**
  (`.ix-scanbeam`, `prefers-reduced-motion`-fest) das Bild ab, darunter steht die EINE
  Angabe, die zählt: **was** zu scannen ist («Instanz 100000479»). Die Suche ist eine
  milchige Leiste **im Bild** statt eines Blocks darunter; Klick daneben schliesst wie das ×.
  `ScanRequest.title` und `ScanStep.hint` sind ersatzlos entfallen (sie wurden nirgends mehr
  gerendert) – `label` ist der einzige Text.
  (2) **Panels ohne zweiten Rahmen und ohne zweiten Titel** (#100, #104): sie sitzen seit
  Runde 8 IN der Modul-Karte des Ablaufs; ihr eigener `cardStyle` (Rahmen, Fläche, Polsterung)
  und ihr `PanelHeader` waren damit Container-in-Container bzw. eine Titel-Dopplung – beides
  entfernt (Datenerfassung/Bewegung/Ressource/Verschrotten; Beschaffung/Verkauf/Dokument
  behalten ihren Kopf, weil er Status bzw. einen anderen Namen trägt). Der aufgeklappte
  Panel-Bereich trägt jetzt die **Modulfarbe** der Karte statt Weiss.
  (3) **Datenerfassung**: «Vorschau: Bestanden/Durchgefallen» entfällt (#103 – das Ergebnis
  steht nach dem Abschluss da), «Erfassung abschliessen» ist **gesperrt, solange nichts
  erfasst ist** (#101 – ein Klick auf einen leeren Satz hätte die Prüfung mit lauter
  Nichtwerten durchfallen lassen), der Prüfumfang ist eine Zeile statt eines grauen Kastens
  (#100). Der ⓘ-Text ist mit dem Kopf entfallen (#93). **Die Hochstufung auf 100 % bleibt**
  (#102 revidiert #93 ausdrücklich: «diese Funktion doch beibehalten»).
  (4) **Auftragsspezifikation im Kachel-Design** (#92, `SpecTile`/`TileShell`): dieselbe
  Sprache wie Artikel-Spezifikation und Instanz-Merkmale – Symbol-Kasten, Versalien-Label,
  Wert; responsiv über `auto-fit, minmax(min(100%, 260px), 1fr)`. Die Instanzen sind eine
  Kachel über die volle Breite im selben Raster.
  (5) **«Prozess» statt «Ablauf»** (#91) – auch bei Nachschub/Retoure/Abweichung.

- **Testnotizen-Runde 10 (Kamera-Sprache überall, Kopf aufgeräumt, Notizen #105–#122)**:
  (1) **Der Dokument-Dialog spricht die Scanner-Sprache** (#119): die Kamera-Phase ist jetzt
  dieselbe Fläche wie beim Objekt-Scanner – ganz Kamera, Zielrahmen mit Suchstrahl, alle
  Bedienelemente als milchige Chips **im Bild** (Auslöser · Datei hochladen · Objektnummer
  öffnen). Erst ab «Analyse» wird es ein normales Formular-Fenster: dort geht es um Text,
  nicht um Bild. `DocumentCamera` hat dafür einen `extra`-Slot für die Zusatzfunktion.
  Im Scanner selbst entfällt das × (#108 – Klick daneben und Esc schliessen ohnehin), und der
  Such-Platzhalter nennt das Ziel (#109: «Instanz 100000479 suchen»).
  (2) **Kein Footer mehr** (#105): der Streifen «Erstellt … Zuletzt geändert» am Fensterrand
  ist weg; die Angabe steht als Kachel in der Auftragsspezifikation, wo die übrigen Angaben
  stehen.
  (3) **Die Status-Aktion sitzt bei den Aktionen** (#117): «Freigeben» steht neben QR-Druck
  und Abweichung unter dem Titel; rechts bleibt nur der **Zustand**. Eine Aktion gehört zu den
  Aktionen, der Status zeigt an.
  (4) **Titel eines Mehrpositionen-Auftrags** (#107): es gibt keinen EINEN Artikel – der Titel
  nennt den ersten und wie viele noch dazugehören («Schraubendreher +2»), ohne Artikel bleibt
  es beim schlichten «Auftrag».
  (5) **Alle Symbol-Aktionen sind getönt** (#113/#115): ein Knopf ohne Fläche sah neben den
  getönten Nachbarn aus wie deaktiviert. `.erp-idbtn` trägt jetzt grundsätzlich eine dezente
  Tönung, Deaktivieren/Ersetzen eine rote (`.erp-idbtn-danger`).
  (6) **Bestand am Artikel**: neueste Instanz zuerst + Suchfeld (#111), ohne Auftragsnummer
  (#112 – am Artikel zählt die Instanz) und ohne die Überschrift «Bestand» (#114 – der Reiter
  sagt es bereits).
  (7) **Inhalte zentriert und responsiv** (#120/#121): Spezifikation und Dokumente stehen
  mittig statt links geklebt; die Spezifikations-Karte wächst mit (`clamp`-Polsterung, keine
  feste 720-px-Breite mehr).
  (8) **Herkunft einer Zahl gehört ans Label** (#122): «Median aus erledigten Aufträgen» ist
  ein ⓘ neben «Lieferzeit»/«Einstandspreis» statt einer eigenen Zeile darunter.
  (9) Datenerfassung: kein Live-Häkchen je Stichprobe mehr (#110) – es bewertete, während man
  noch tippt; das Ergebnis steht nach dem Abschluss da. Die Panels mit eigenem Kopf
  (Beschaffung/Verkauf/Dokument) haben ihren weissen Kasten verloren (#118) und tragen jetzt
  ebenfalls die Modulfarbe der Karte.
  (10) Die Prozess-Überschriften im **Entwurf** entfallen (#106/#116) – der Fluss mit
  Start-/Endknoten sagt selbst, was er ist; am laufenden Auftrag bleibt «Prozess».

- **Testnotizen-Runde 11 (gebundener Bestand, ruhige Aktionen, Notizen #123–#137)**:
  (1) **Ein freigegebener Unter-Auftrag reserviert seinen Bestand** (#131, `subject._bind_
  deviation_subjects`): eine Abweichung band ihre Instanzen bisher nur über
  `subject_of_order_id` + Verarbeitungs-Link – **FIFO sah sie weiterhin als frei**, ein
  beliebiger anderer Auftrag konnte sie wegnehmen, und die Badge zeigte «Freigegeben», obwohl
  sie längst gebunden waren. Jetzt wird reserviert, was am Lager liegt (in Arbeit/verkauft/
  gesperrt braucht es nicht – dort greift ohnehin kein FIFO); Abschluss und Verwerfen lösen
  die Reservierung über die bestehende `release`-Mechanik. Wächter
  `test_fixed_subject_sub_order_reserves_its_stock`.
  (2) **Die Schritt-Palette spricht die Sprache des Flusses** (#123/#124): Symbol in der
  **Modulfarbe** statt neutraler Kachel mit Text; der Name klappt beim Hover auf
  (`.erp-palette`, `prefers-reduced-motion`-fest), die Rolle steht im Tooltip.
  (3) **Ruhige Hauptaktion** (#125): `PrimaryButton` ist **schwarz** statt rot. Rot ist der
  EINE laute Akzent für die Entscheidung über den Datensatz («Freigeben»), nicht für die
  alltägliche Arbeit im Schritt – «Scannen & bewegen» in Rot las sich wie ein Fehler. Grün
  bleibt der Abschluss. Ebenso der Foto-Auslöser im Dokument-Dialog (#135); «Datei hochladen»
  ist dort nur noch ein Symbol (#136).
  (4) **Weniger Text im Bewegungs-Panel**: die Empfehlung markiert die Option selbst (Punkt +
  Hover) statt eines Erklärsatzes (#132); der Hinweis «Innerbetriebliche Bewegung – kein
  Versand» entfällt (#133 – der Umschalter sagt es bereits).
  (5) **Eine Aussage, eine Stelle** (#126): die Zielangabe im Scanner steht nur noch als
  **Platzhalter** im Suchfeld («Aktueller Standort suchen») statt zusätzlich als Chip im Bild.
  Im Dokument-Dialog entfällt die Objektnummer-Eingabe ganz (#134) – dafür gibt es die
  Feed-Suche.
  (6) **Abweichungs-Dialog** (#128–#130): kein Erklärtext, kein ×, und **nichts ist
  vorausgewählt oder hervorgehoben** – zwei gleichwertige Wege, die Entscheidung trifft der
  Mensch und nicht die Gestaltung.
  (7) **Feed ohne Scrollbalken** (#137, `.ix-noscrollbar`): gescrollt wird weiterhin (Rad,
  Trackpad, Touch, Tastatur), nur der Balken verschwindet.

- **Testnotizen-Runde 12 (eine Frage – eine Antwort, Notizen #138–#147)**: Der rote Faden
  dieser Runde ist Entdopplung: dieselbe Aussage stand jeweils an zwei Stellen oder in zwei
  Formen.
  (1) **Positionen tragen ihre Instanzen** (#141, `components/erp/order-positions.tsx`,
  ersetzt `order-instances.tsx` + `PositionsList`): Die Auftragsspezifikation zeigte oben die
  Positionen (Artikel → Menge) und darunter **alle** Instanzen des Auftrags als zweite flache
  Liste – bei mehreren Positionen war damit ausgerechnet die entscheidende Zuordnung
  unsichtbar: welche Instanz gehört zu welchem Artikel? Jetzt hängen die Instanzen eingerückt
  an einer Haarlinie unter **ihrer** Position (`InstanceEmbed.article_id` liefert die
  Zuordnung, sie war längst da). Der Einzel-Artikel-Auftrag ist dabei kein Sonderfall mehr,
  sondern ein Auftrag mit EINER Position – die getrennten Kacheln «Artikel»/«Menge» sind
  entfallen; ein Unter-Auftrag ohne Artikel zeigt titellos nur seine Instanzen. Eine Form für
  alle drei Fälle, umbrechend statt überlaufend (Mobile).
  (2) **Die verteilte Charge steht IM Standort-Container** (#147): «Standort» (Kette) und
  «Standort · verteilt» (Teilmengen) waren zwei Karten für dieselbe Frage – und die Kette
  darüber galt ohnehin nur für die **grösste** Teilmenge, war also bei einer verteilten Charge
  die halbe Wahrheit. Ab zwei Standorten ersetzen die Teilmengen die Kette an Ort und Stelle
  (Symbol · Halter · Objektnummer · Menge, Pille «verteilt · N Standorte» im Kachel-Kopf);
  `instance-locations.tsx` ist entfallen.
  (3) **Kein Footer mehr am Auftrag** (#140): Die Fussleiste trug drei Dinge, jedes hat einen
  besseren Ort – der **Fehler** steht zuoberst im Inhalt, direkt unter der Aktion, die ihn
  ausgelöst hat («Freigeben» sitzt im Kopf); der **Auto-Save-Status** war ohnehin schon als
  grüner Flash im Kopf; **«Abbrechen»** der Anlage steht bei den übrigen Aktionen. Der
  Anlage-Hinweis ist eine leise Zeile in der Karte, auf die er sich bezieht.
  (4) **Der Platzhalter sagt, was zu TUN ist** (#145): «Standort 100000292 scannen» statt
  «Aktueller Standort suchen» – die Zielnummer hängt der Scanner selbst an (`ScanStep.expected`),
  die Aufrufstellen nennen nur noch, WAS gescannt wird. Das Eingabefeld bleibt daneben
  unverändert benutzbar; die Platzhalter-Fläche wird lediglich zweckentfremdet.
  (5) **Die abgeleitete Klasse ist eine Empfehlung, die Wahl ist die Wahrheit** (#138): der
  Chip «Extern · Versand» beschrieb weiter die Ableitung, nachdem der Nutzer «Im Betrieb»
  gewählt hatte – jetzt richtet er sich nach der getroffenen Wahl.
  (6) Kleineres: ausgegraute Schritte behalten die **Farbe ihres Moduls** statt weiss zu
  werden (#139); der Einzel-Instanz-Scan-Knopf trägt dieselbe Stimme wie der grosse Knopf
  darunter (#144, schwarz statt blau); Vorschlagsliste im Scanner ohne Scrollbalken (#146);
  «Dokument in den Rahmen halten» (#143) und «geändert …» in der Angelegt-Kachel (#142)
  entfallen.
  *Zur Suchleistung (Frage in #146): das Filtern im Scanner ist eine lineare Suche über die
  Kandidaten mit Abbruch bei 6 Treffern – auch bei fünfstelligen Beständen unter einer
  Millisekunde je Tastendruck. Die Grenze liegt nicht dort, sondern im **Vorladen**: das
  Bewegungs-Panel holt für die freie Zielwahl einmal alle Personen + alle Instanzen
  (`api.getInstances()` ohne Begrenzung). Der Endpunkt kann bereits serverseitig suchen und
  paginieren (`search`/`limit`/`offset`), die Umstellung ist also eine Ein-Stellen-Änderung,
  sobald die Instanzzahl das rechtfertigt.*

- **Testnotizen-Runde 13 (weniger Wege, weniger Text, Notizen #148–#175, Migration `088`)**:
  (1) **Der Klick auf den Weg IST die Ausführung** (#152–#155, `deactivate-dialog.tsx`): Der
  Deaktivieren-Dialog liess erst eine Option wählen und darunter noch einmal bestätigen –
  zwei Schritte für EINE Entscheidung, dazu ein ×, ein «Abbrechen» und eine hervorgehobene
  Vorauswahl. Jetzt führen zwei gleichwertige Wege selbst aus («Deaktivieren» ↔ «Ersetzen»,
  #151 – derselbe prägnante Name, den der Artikel-Kopf ohnehin verwendet); geschlossen wird
  per Klick daneben oder `Esc`. Die **Wirkungsanalyse** bleibt (sie ist die Tatsachengrundlage,
  nicht die Erklärung), ihre Unterzeilen sind entfallen (#148–#150). Dialog-Rahmen und
  Wege-Knopf sind dabei zu `fields.tsx` gewandert (`Dialog`/`ChoiceButton`) – der
  Abweichungs-Dialog nutzte dieselbe Form schon, jetzt aus EINER Quelle.
  (2) **«Fixierter Standort» am Artikel ersatzlos entfernt** (#168, Migration `088`): sechs
  Spalten für GPS + reverse-geocodierte Adresse, rein deskriptiv – kein Bestands-Standort,
  keine Logik, gelesen nur von Formular, Lese-Ansicht und Kopierfunktion. Ein Artikel ist eine
  **Gattung**; einen Ort hat immer nur die **Instanz**. Damit ist auch `MapPicker` entfallen
  (Google Places bleibt für die Adressfelder).
  (3) **Die Bezugsquelle steht am Schritt. Punkt.** (#166): «Leer lassen, um den
  Artikel-Standard zu erben» zeigte auf einen Wert, den **niemand mehr setzen kann** – der
  Abschnitt «Beschaffung» in der Artikel-Spezifikation ist seit Runde 2 weg. Eine Option, deren
  Gegenstück unerreichbar ist, ist keine Option. Lieferant bzw. Webshop-Link sind jetzt
  Pflicht am Beschaffungs-Schritt; der Backend-Fallback auf den Artikel-Standard bleibt als
  **Lesepfad für Altbestand** (tolerant lesen, streng schreiben – wie bei den Standort-Typen).
  Dazu: der Hinweis in der Spezifikation entfällt (#169), das Lieferanten-Symbol ist ein
  **Gebäude** statt eines Lastwagens (#164 – gemeint ist die Firma, nicht der Transport), und
  der Chip-Hinweis unter «Für Lieferant sichtbar» ist weg (#165).
  (4) **Erfassungsfelder wählt man wie ein Prozessschrittmodul** (#172): eine Palette aus
  Symbolen, deren Name beim Hover aufklappt (`.erp-palette`) – erst WAS für ein Feld, dann die
  Konfiguration. Vorher: «Feld hinzufügen» → leere Zeile → Dropdown, also drei Handgriffe für
  eine Entscheidung, und eine Zeile, die vor der Wahl bereits «Soll-Ist» behauptete. Die Art ist
  danach das Symbol der Zeile, kein Feld mehr (umentscheiden = löschen + neu, wie beim Schritt).
  (5) **Die Abweichung gehört an den Schritt, den sie unterbrochen hat** (#175): Sie stand als
  Abzweig **unter** der Karte – was suggerierte, sie käme NACH dem Schritt, obwohl sie während
  seiner Ausführung gemeldet wurde. Eine Abweichung ist aber kein Knoten in der Reihenfolge,
  sondern die Aussage «hier ist etwas schiefgegangen» – und «hier» ist genau eine Karte. Sie
  steht jetzt **in** der Karte ihres Schritts (`origin_step_id`), als schmale Zeile unter dem
  Kopf. Eine Abweichung **ohne** Ursprungsschritt (an der Instanz gemeldet, oder bevor ein
  Schritt aktiv war) gehört keinem Schritt, sondern dem Auftrag – sie bleibt ein Abzweig, aber
  **vor** dem ersten Schritt. Damit ist die Liste in der Angehalten-Notiz überflüssig (#174),
  und deren Erklärabsatz ebenso (#173): «angehalten» sagt bereits, dass nichts geht.
  (6) **Schieberegler im Verkauf** (#159–#161): Status · Sichtbarkeit · Verfügbarkeit (und im
  gleichen Zug Art · Intervall · Abo-Typ) laufen über denselben `IconSwitch` wie am Bedarf und
  am Beschaffungs-Schritt – dass die Optionen einander ausschliessen, zeigt die Bewegung des
  Reiters statt ein zweiter Rahmen.
  (7) **Positionen dezenter** (#171): kein Zähler im Kopf (die Instanzen stehen darunter), das
  Wort «Instanz» nicht mehr in jeder Zeile (unter einer Position IST jede Zeile eine), und die
  Menge trägt kein zweites Fettgewicht neben dem Artikelnamen – in einer Zeile darf genau EINE
  Angabe laut sein.
  (8) **Freigeben steht bei den Aktionen** (#167): am Artikel wie am Auftrag unter dem Titel
  neben QR-Druck/Deaktivieren – rechts bleibt nur der Zustand. Nebeneffekt: die Aktion ist jetzt
  auf **jedem** Reiter erreichbar, nicht nur auf «Spezifikation».
  (9) Entfallen: Suchfeld im Artikel-Bestand (#157 – der Bestand EINES Artikels ist die kurze
  Liste; gesucht wird im Feed; revidiert #111), ⓘ bei «Inhalt»/«Preise» (#162/#163), «Noch kein
  Preis …» (#158), «verteilt · N Standorte» (#170 – die Zeilen sind die Aussage), «Nachfolger:»
  (#156).

- **Testnotizen-Runde 14 (ein Name, eine Bildsprache, Notizen #176–#193)**:
  (1) **Ein Datensatz zeigt Name · Objektnummer · Status – der TYP steht im Symbol** (#177,
  `services/orders.order_display_name` + `lib/record-name.ts`): Im Feed trug ein Auftrag als
  «Namen» das Wort **«Auftrag»** und eine Instanz das Wort **«Instanz»** – der Typ war in die
  Namensspalte gerutscht, und zwei Datensätze desselben Typs sahen identisch aus. Der Name
  wird jetzt **einmal im Backend** abgeleitet und als `OrderSummary.name`/`OrderResponse.name`
  geliefert (Feed und Detail lesen dasselbe Feld, können also nicht auseinanderlaufen):
  bewusst vergebener `title` ≻ Artikel ≻ erster Positions-Artikel «+N» ≻ «Auftrag» nur, wenn
  es wirklich nichts zu benennen gibt. Die Positions-Namen kommen über **eine** Batch-Abfrage
  (kein N+1). Frontend: `lib/record-name.ts` ist die EINE Ableitung für alle Typen und gibt
  `null` zurück, wenn ein Datensatz (noch) keinen Namen hat – den Platzhalter setzt die
  Oberfläche. Instanz-Detail und Auftrag-Detail lesen dieselbe Funktion; `orderTitle` in
  `order-detail.tsx` ist entfallen. Wächter `test_smoke.py:
  test_order_name_never_falls_back_to_the_type_word_when_there_is_a_name`.
  (2) **Gleiches Wort → gleiches Symbol** (#191): «Im Prozess» hiess am Auftrag `Hammer`
  (behauptete Fertigung – falsch für Beschaffung/Verkauf) und an der Instanz `Clock`
  (behauptete Warten – falsch für etwas, das läuft). Beide tragen jetzt `Loader`. Die Uhr
  bleibt, wo Warten die Aussage IST: «Angefragt».
  (3) **Der Beschaffungs-Ablauf spricht die Fluss-Sprache** (#182, `purchase-progress.tsx`):
  senkrecht, ein Knoten je Stufe an einer dünnen Linie – wie der Auftrags-Prozess. Der
  waagrechte Punkte-Stepper mit animiertem Lieferwagen ist weg (er brachte `@keyframes` in
  die Fläche); die **Lieferfrist ist keine Stufe, sondern eine Eigenschaft der Stufe
  «Bestellt»** und steht als schmaler Balken an ihrer Zeile.
  (4) **Beschaffungs-Panel entrümpelt**: ⓘ am Kopf (#192) und Statuswort in der Aktionszeile
  (#188 – der Zustand steht als Badge oben rechts) entfallen; Knöpfe in der Design-Sprache
  statt Blau (#187); «Webshop öffnen» ist ein Knopf mit Symbol statt blauer Fliesstext (#193);
  Beschriftungen nennen die Sache, der **Platzhalter** erklärt sie («Bestellsumme» +
  «ganze Menge, netto in CHF – z. B. 1250», #183–#186); «Artikel-Spezifikation (für Lieferant
  sichtbar)» → **«Spezifikation»** (#189).
  (5) **Die Abweichung hängt SEITLICH an ihrer Karte** (#178, `.erp-devbranch`): Runde 13
  hatte sie in die Karte gelegt – sie gehört aber zum Schritt, ist aber nicht Teil des Moduls
  (sie ist das, was es unterbrochen hat). Jetzt sitzt sie auf der **Höhe** der Karte, an einem
  kurzen Ast rechts daneben; unter 1180 px rutscht sie darunter.
  (6) **Versand ohne eigenen Kasten** (#179): die Transport-Wahl ist derselbe `IconSwitch` wie
  überall (die abgeleitete Empfehlung markiert sich mit einem Punkt – neues, generisches
  `mark`-Flag); der umgebende Rahmen ist entfallen (Panel im Modul im Fluss = drei Rahmen um
  dieselbe Sache).
  (7) **Positionen: Ausrichtung statt Schriftgrösse** (#176): EIN Raster über Positions- und
  Instanz-Zeilen (Nummer · Bezeichnung · Zahl/Zustand), Positionen durch Haarlinien getrennt,
  keine 18-px-Werte mehr (die Kachel erbt `TILE.v` bewusst nicht).
  (8) **Deaktivieren-Dialog: Folgen als Liste, Entscheidung an ihrer Zeile** (#180): die
  betroffenen Objektnummern sind **klickbar** (es sind Datensätze), «keine/keiner» steht leise
  da (dass nichts passiert, ist auch eine Antwort), und die einzige Zusatz-Entscheidung
  (Auslaufen lassen ↔ Abbrechen) sitzt als Schieberegler **direkt an der Zeile «Laufende
  Aufträge»** statt in einer zweiten Gruppe mit demselben Titel.
  (9) **Responsive** (#181): die Artikel-Spezifikation polstert mit `clamp` statt fixer 30 px
  (auf einem 360-px-Telefon frassen sie ein Sechstel der Breite), lange Werte brechen um.
  (10) **Multi-Site (#190) – Analyse, noch nicht gebaut.** Die Bewegungs-Logik ist bereits
  standort-agnostisch: ein Standort ist ein **Halter** (`user|instance|company`), und
  `logistics.classify_movement` entscheidet **adress-basiert** – «zwei interne Orte mit
  unterschiedlicher Adresse → Versand» ist heute schon der Mehr-Standort-Fall. Was fehlt, ist
  nur, dass `company` ein **Singleton** ist: `locations.company_location` liefert die eine
  Firma, `provisioning.target_for` löst `PROV_RECEIVING` darauf auf. Der Weg ist deshalb
  **kein Umbau, sondern eine Auflösung**: (a) `company_settings` von 1 auf n Zeilen (je
  Standort eine Objektnummer + Adresse, eine davon «Hauptsitz» für Rechnungen/Impressum);
  (b) der **Bedarf** bekommt einen Standort – am ehesten am Prozessschritt (`site_id`, leer =
  Standort des Auftrags), analog zur Bezugsquelle; (c) `target_for` löst `PROV_RECEIVING` auf
  **den Standort des Schritts** statt auf «die Firma» auf – ab da funktioniert die
  Bereitstellung unverändert weiter und erzeugt zwischen zwei Werken automatisch einen
  **Versand** statt einer innerbetrieblichen Bewegung, weil die Adressen sich unterscheiden.
  Genau das ist der Beweis, dass die Ableitung richtig gebaut ist: Multi-Site fällt aus der
  bestehenden Regel heraus, statt eine zweite zu brauchen.

- **Testnotizen-Runde 15 (der Name benennt die Sache, Notizen #194–#222, Migration `089`)**:
  (1) **Die abgeleitete Bereitstellung ist VORÜBERGEHEND ABGESCHALTET** (#204,
  `provisioning.AUTO_PROVISIONING = False`): Im Praxistest war der Bereitstellungs-Unter-Auftrag
  (a) im Ablauf nicht als Unter-Auftrag erkennbar – er sah aus wie ein regulärer Schritt des
  Hauptprozesses – und (b) seine Blockade traf nicht das Gewollte. Statt an der Oberfläche zu
  flicken, ist der **Auslöser** stillgelegt: es entsteht keine neue Bereitstellung, und eine
  vorhandene hält keinen Auftrag mehr an (sonst hinge ein Auftrag an einem Mechanismus fest,
  den es gerade nicht gibt). Bestehende Datensätze bleiben als Historie und lassen sich normal
  abschliessen/verwerfen. **EINE Konstante**, die ganze Ableitung (`target_for`, `misplaced`,
  `reconcile_to`, alle Tests) bleibt intakt – Wiedereinschalten ist ein Ein-Zeilen-Wechsel.
  Wächter `test_auto_provisioning_is_switched_off_at_exactly_one_place`.
  (2) **Der Name benennt die SACHE, nicht die Herkunft** (#205): ein Unter-Auftrag hiess
  «Bereitstellung für Beschaffung · Auftrag 100000500» – das beschreibt seine Entstehung, es
  ist kein Name. `order_display_name` bevorzugt jetzt Artikel ≻ Positionen ≻ **Artikel der
  fixierten Subjekt-Instanzen** ≻ `title` ≻ «Auftrag». Der Subjekt-Artikel kommt über EINE
  zusätzliche Batch-Abfrage im Feed bzw. aus dem bereits geladenen Instanz-Embed im Detail.
  (3) **«Zielbestand» ersatzlos entfernt** (#221, Migration `089`): zwei Zahlen für dieselbe
  Frage – `safety_stock` («ab wann nachbestellen?») und `reorder_target` («bis wohin?»), wobei
  die zweite fast immer leer blieb und die Nachbestellung dann ohnehin auf den
  Sicherheitsbestand auffüllte. Genau das ist jetzt die einzige Regel.
  (4) **Der Beschaffungs-Ablauf ist ein Prozess IM Prozess** (#194, `purchase-progress.tsx`):
  senkrechte Karten in der Modulfarbe, durch `Connector` verbunden – dieselben Bausteine wie
  der Auftrags-Fluss, nur eine Nummer kleiner; Start-/Endknoten entfallen (die Modul-Karte IST
  der Rahmen). Zustand ohne Wort, Lieferfrist als Balken **in** der Karte «Bestellt».
  (5) **Schieberegler, der nur die aktive Option ausschreibt** (#219/#220, `IconSwitch
  labelActiveOnly`): bei sechs Mengeneinheiten ringen sonst sechs Wörter nebeneinander um
  Aufmerksamkeit, obwohl nur eines gilt. Dafür wird der gleitende Reiter jetzt **gemessen**
  (ResizeObserver) statt als `100/N %` gerechnet – sonst stimmt er nicht mehr, sobald die
  Optionen unterschiedlich breit sind.
  (6) **Beschriftung nennt die Sache, der Platzhalter erklärt sie** (#207–#209, #211–#214,
  #216, #217): alle erklärenden Zeilen unter den Spezifikations-Feldern sind entfallen und in
  den Platzhalter gewandert («aufsteigend, mit «x» getrennt – z. B. 3x40x600»); «MOQ
  (Mindestbestellmenge)» → **Mindestbestellmenge**, «Meldebestand (Sicherheitsbestand)» →
  **Sicherheitsbestand**.
  (7) **Beschaffungs-Panel**: kein eigener Kopf mehr (#201 – die Modul-Karte heisst bereits
  «Beschaffung»), Lieferzeit ist **Pflicht** (#195 – ohne sie gibt es keinen Termin und keine
  Überfälligkeit), Tracking mit **Auto-Save** statt Speichern-Knopf und ohne «(optional)»
  (#198–#200), Rechenweg unter dem Stückpreis (#196) und der Kaufmännisch-Hinweis (#197)
  entfallen.
  (8) **Bewegen**: weder Überschrift «Versand» (#202 – die Karte heisst «Bewegen») noch der
  abgeleitete «Extern»-Chip (#203 – die getroffene Wahl steht direkt darunter; zwei
  gleichzeitig gültige Aussagen nebeneinander verwirren). Übrig bleibt die einzige Warnung mit
  Konsequenz: Gefahrgut.
  (9) **Der Schritt-Editor trägt die Farbe seines Moduls** (#222): man konfiguriert die Karte,
  die gleich im Fluss stehen wird – also sieht sie schon so aus (getöntes Symbol + Name als
  Kopf). (10) Feed etwas leichter (#206: 32-px-Symbol, halbfetter statt fetter Titel).

- **Testnotizen-Runde 16 (weniger Klicks, ein Kopf für alle, Notizen #223–#243)**:
  (1) **Die Paletten stehen offen** (#223, #229, #231 – «jeder Klick ist ein Klick zu viel»):
  die Prozessschritt-Module liegen sichtbar am Ende des Flusses (der Zwischenschritt
  «Prozessschritt hinzufügen» ist weg), die Erfassungsfeld-Palette ebenso, und die
  Ressourcen-Liste hält **immer eine leere Schlusszeile** bereit, die nachwächst, sobald sie
  einen Artikel bekommt. Leere Zeilen werden beim Speichern ohnehin verworfen.
  (2) **EIN Kopf für alle Datensatz-Fenster** (#242, `fields.DetailHeader`): Alle fünf
  Detail-Ansichten sahen sich ähnlich, aber keine zwei gleich – mal 26-px-Titel, mal 28,
  mal klebend, mal nicht; der **Benutzer** hatte sogar ein ganz eigenes Layout (44-px-Avatar,
  «Obj.-Nr.»-Block rechts). Die Anatomie ist jetzt verbindlich und spiegelt den Feed:
  Symbol · TYP (Eyebrow) · **Name** · Objektnummer mit den Aktionen · rechts der Zustand.
  Artikel/Auftrag/Instanz/Benutzer/Unternehmen teilen sie sich; die lokalen `H`/`S`-Kopfstile
  sind entfallen. Ein rundes Foto bleibt möglich (`avatar`-Slot).
  (3) **Der Anzeigename einer Person folgt EINER Regel** (#227): Firma → «Vorname Nachname»
  → E-Mail – genau wie `UserProfile.display_name` im Backend. Das Frontend wich hier ab und
  zeigte die Person, wo das Backend die Firma zeigte; beim Lieferanten ist die Firma der Name,
  unter dem man bestellt.
  (4) **Der Abweichungsauftrag ist überall als solcher gekennzeichnet** (#243): die
  Auftragsliste der Instanz zeigt jetzt Name · Objektnummer · Status **und** das gelbe
  Warnzeichen am Symbol – `InstanceOrderRef` trägt dafür `name`/`reason` (dieselbe
  Namens-Ableitung wie im Feed).
  (5) **Dokument-Modul lesbar** (#236, #241): eigene, kühl-graublaue Farbfamilie (die alte
  war exakt die Flächenfarbe des Fensters – die Karte verschwand darin), und die fertige
  Deklaration ist EINE Liste (Nr · Name · Aktion · Objektnummer) plus zwei
  Schlüssel-Wert-Zeilen statt fünf gestapelter Blöcke mit je eigener Überschrift.
  (6) **Die Sache beim Namen** (#228, #237, #238): «Erfassungsfelder», «Dokumentenfreigabe»,
  «Leseberechtigung», «Anerkennung» statt Fragen; die zugehörigen ⓘ entfallen (#235, #239).
  (7) **Ressource** trägt `Blocks` statt `Wrench` (#234): der Schritt setzt BEIDES ein –
  Material, das verbraucht wird, und Werkzeug, das genutzt wird; der Schraubenschlüssel ist
  innerhalb der Zeilen genau für den Werkzeug-Modus reserviert. Das Wort «Werkzeug» in der
  Zeile entfällt (#233 – das Symbol sagt es).
  (8) **Knöpfe in der Design-Sprache** (#230, #240): `erp-actbtn`/`erp-actbtn-primary` statt
  lokaler Stile; der Zurück-Kopf im Schritt-Editor ist entfallen (#226, #232 – «Abbrechen»
  ist der Weg heraus).
  (9) **Schieberegler hugged seinen Inhalt** (#224/#225): `labelActiveOnly` hat naturgemäss
  ungleich breite Optionen – der Regler ist darum `inline-flex` und füllt nicht mehr die
  ganze Spalte.

- **Testnotizen-Runde 17 (der Auftrag, der zuletzt arbeitet, gibt frei; Notizen #244–#262)**:
  (1) **Wer zuletzt an einer Instanz gearbeitet hat, gibt sie frei** (#262, `process.release_
  instances`): Freigegeben wurde bislang nur, was der **erzeugende** Auftrag hervorgebracht
  hat (`Instance.order_id`). Wird ein Auftrag abgebrochen und ein **Abweichungsauftrag** führt
  seine Instanzen fort, bleibt deren `order_id` beim abgebrochenen Original – sie wurden
  damit **nie** freigegeben: für immer «Im Prozess», unsichtbar für FIFO und Bestandszählung.
  Jetzt zählt beides: erzeugt-von **oder** Subjekt-von. Terminale/bewertete Teile bleiben wie
  bisher ausgenommen. Wächter `test_the_order_that_finishes_an_instance_releases_it`.
  (2) **Jedes Prozessschrittmodul ist universell einsetzbar** (#246): Verkauf/Verschrotten
  waren im Artikel-Prozess gesperrt, **«Sperren» stand in gar keiner Liste** und war damit
  nirgends wählbar. `STEP_TYPES_BY_OWNER` ist jetzt EINE Liste für Artikel und Auftrag – eine
  Sperre gegen selten sinnvolle Kombinationen kostet mehr, als sie nützt.
  (3) **Unter-Aufträge stehen an ihrem Schritt** (#259/#260): Nicht nur die Abweichung, auch
  der **Nachschub** merkt sich jetzt, aus welchem Schritt sein Bedarf stammt
  (`supply._blocked_step_id` → `orders.origin_step_id`) und erscheint als Pille am Ast neben
  der Modul-Karte. Die separate «Nachschub»-Liste im Auftrag ist entfallen – sie sagte
  dasselbe noch einmal und verschwieg, WO der Bedarf entstand.
  (4) **Der Beschaffungs-Ablauf trägt seine Eingaben in der aktiven Stufe** (#248,
  `PurchaseProgress renderActive`): Bestellsumme, Lieferzeit, Zahlungsziel und die Aktion
  sitzen in der Karte der Stufe, die gerade dran ist – genau wie ein Schritt-Panel in seiner
  Modul-Karte. Der fachliche Zustand («Angefragt») wanderte in den **Modul-Kopf** des Flusses
  (#247, `FlowCard badge`), wo man ihn ohne Öffnen sieht.
  (5) **Zahlenfelder ohne Minus** (#249/#250): Bestellsumme/Lieferzeit/Zahlungsziel laufen
  über `numericOnly` – eine negative Bestellsumme gibt es nicht.
  (6) **Der Lastwagen fährt wieder** (#251, `.ix-truck`/`.ix-road` in `globals.css`): er steht
  auf dem **echten** Fortschritt und wippt, die gestrichelte Strasse läuft ihm entgegen;
  `prefers-reduced-motion` stellt beides still. Die `@keyframes` liegen im Stylesheet, nicht
  als `<style>` in der Fläche (das war die Kritik aus #182).
  (7) **Ein Erfolg, eine Meldung** (#253): der Scanner meldete den Treffer doppelt – grüner
  Rahmen UND grüne Textpille. Geblieben ist der Rahmen; Text gibt es nur beim Fehlschlag,
  wo der GRUND zählt.
  (8) **Verschrotten/Sperren verlangen einen Grund** (#255): warum etwas ausgeschleust wurde,
  ist die eigentliche Information des Schritts – ohne sie bleibt im Nachhinein nur «weg». Der
  Schritt **deklariert** die Pflicht (wie die Datenerfassung ihre Felder); das Scannen ist die
  ruhige schwarze Hauptaktion (#256), rot bleibt dem Vollzug vorbehalten.
  (9) **«Es fehlt» statt eines Absatzes** (#257/#258): die Unterdeckungs-Notiz nennt Menge,
  Artikel und Objektnummer – der Erklärtext wiederholte nur, was Titel und Zeile ohnehin
  sagen; der Kasten ist zur Haarlinie geworden (sie sitzt IM Modul).
  (10) Kleineres: Tracking-Platzhalter «Tracking-Nummer» (#252). *#244/#245 (Unternehmens-Kopf
  und Status-Farbe) waren mit dem gemeinsamen `DetailHeader` aus Runde 16 bereits erledigt.*

- **Testnotizen-Runde 18 (Ausschleusen, eine Spezifikations-Karte, Notizen #263–#277)**:
  (1) **«Verschrotten» und «Sperren» sind EIN Modul «Ausschleusen»** (#277): Beide beantworten
  dieselbe Frage – *dieses Teil darf so nicht weiter* – und unterscheiden sich nur in der
  **Endgültigkeit**. Zwei Paletten-Einträge zwangen zu dieser Entscheidung, bevor man den
  Fall überhaupt beschrieben hatte. Jetzt gibt es einen roten Eintrag (`PackageX`); die
  Wirkung wählt ein `IconSwitch` **im Editor** (Verschrotten = endgültig, standortlos ↔
  Sperren = aufhebbar, bleibt liegen), und der **Grund ist bei beiden Pflicht** (#255) –
  warum etwas ausgeschleust wurde, ist die eigentliche Information des Schritts. Datenmodell
  unverändert: es bleiben zwei Schritttypen mit zwei Polaritäten (`DECREASE` ↔ `NEUTRAL`),
  nur die Oberfläche fasst sie zusammen. **Die Labels stehen dabei weiter in der Registry**
  (`domain/event_types.py`) – der Mirror-Test hat den Alleingang im Frontend prompt gemeldet,
  also sind auch «Beschaffen» (#274) und «Ausschleusen» dort umbenannt.
  (2) **Die Auftragsspezifikation ist EINE Karte** (#267, `fields.SPEC` + `fields.ReadField`):
  Sie stand als drei lose Kacheln nebeneinander, während der Artikel seine Angaben auf EINEM
  Blatt zeigt – zwei Formensprachen für dieselbe Sache. Karte, Werteraster und Lesefeld sind
  aus `article-detail.tsx` ins gemeinsame Vokabular gewandert; `OrderPositions` rendert
  seitdem als Lesefeld (volle Breite) statt als eigene Kachel, sonst wäre es eine Karte in
  der Karte. `specGrid`/`SpecTile` sind entfallen.
  (3) **Objektnummern ohne Tausender-Trennung** (#263, `lib/utils.formatObjectId`): eine
  Objektnummer ist eine **Kennung**, keine Menge – `100'000'451` liest sich als Betrag. EINE
  Formatierung (9-stellig, führende Nullen), die alle Ansichten teilen.
  (4) **Der Kopf ist überall derselbe – auch im Detail** (#264/#268): `DetailHeader` rendert
  die Status-Badge jetzt **selbst** (`status`-Prop), statt sie den Aufrufern zu überlassen;
  damit kann keine Ansicht mehr eine eigene Grösse wählen (die Instanz hatte eine grössere
  Pille). Der `right`-Slot trägt nur noch Zusätze (Speicher-Anzeige, «Abbrechen»).
  (5) **Der Beschaffungs-Ablauf benennt Tun und Zustand getrennt** (#271/#272/#275): der
  **aktive** Knoten trägt das Verb («Bestellen»), die erreichten Stufen den Zustand
  («Bestellt») – vorher hiess dieselbe Stufe beides. Wer/Wann steht im Hover (#276), der
  Arbeitsbereich der aktiven Stufe ist eine weisse Fläche im Modulrahmen (#273).
  (6) **Erfolgsmeldungen entfallen** (#266): dass ein Schritt erledigt ist, sagt seine Karte
  im Fluss (Symbol + Wer/Wann im Hover) – ein grünes Banner im Panel sagte es ein zweites Mal.
  (7) Kleineres: Menge bei **jeder** Instanz (#265 – Einheitlichkeit statt «mal hier, mal
  dort»), Startknoten auch beim leeren Prozess (#269), «Prozess des Artikels» entfällt (#270).

- **Unterdeckung: EINE Frage, DREI Antworten – und die Abweichung hält nichts mehr an**
  (Juli 2026, `services/recovery.py`, `process.deviated_instance_ids`): Praxistest an einem
  Erzeugungsauftrag (Beschaffung → interne Bewegung → Abweichung an EINER Instanz) zeigte,
  dass beide bisherigen Wege am Fall vorbeigingen: *Aus Lager decken* schickt ein fertiges
  Teil noch einmal durch den Prozess, und *Nachschub* lässt vier Instanzen warten, bis ein
  kompletter Unter-Auftrag durchgelaufen ist. Es fehlte die ehrlichste Antwort: **der
  Auftrag wird mit weniger fertig.**
  **(1) Eine Abweichung nimmt ihr Stück HERAUS, statt den Auftrag anzuhalten.** Früher
  pausierte JEDE offene Abweichung den GANZEN Eltern (`_is_paused_by_deviation`, dazu ein
  `_assert_not_paused`-Wächter an allen zwölf Ausführungs-Endpunkten) – unabhängig davon,
  wie viele Instanzen betroffen waren: ein schlechtes von fünf Stück legte die anderen vier
  still. Das war ein **zweiter** Mechanismus für etwas, wofür es längst eine präzise Sprache
  gibt – die **Unterdeckung**. Ein Stück in Klärung ist weder verloren noch gesichert, es ist
  **fehlend**: `deviated_instance_ids` nimmt es aus «Gesichert» heraus, der Schritt meldet
  «Es fehlt 1 Stk», der Rest läuft weiter. Der Schutz, für den die Pause gedacht war – *eine
  Sendung darf nicht teil-versendet werden* –, bleibt **abgeleitet statt deklariert**:
  Verkauf und Versand sind Subjekt-Schritte und blockieren bei einer Fehlmenge ohnehin. Damit
  ist es **eine Regel weniger**, nicht eine mehr: `_is_paused_by_deviation`, `_assert_not_paused`
  und `OrderResponse.paused` sind ersatzlos entfallen. Gegenstück: `release_instances` gibt
  nicht frei, was in einer offenen Abweichung steckt (der Eltern darf jetzt abschliessen,
  während die Klärung läuft – freigegeben wird vom Auftrag, der zuletzt daran arbeitet).
  **(2) Die Unterdeckung stellt genau EINE Frage** – *was soll mit der Fehlmenge geschehen?* –
  mit drei Antworten: **Wartet** = kein Knopf, sondern ein **Zustand** (`OrderStepInfo.
  waiting_for` – ist die Menge in einer offenen Abweichung oder einem laufenden Nachschub
  gebunden, ist die Entscheidung getroffen; die frühere Trennung «Nachschub läuft» ↔
  «Abweichung offen» ist EIN Feld geworden); **Ersetzen** = EIN Weg statt zweier Knöpfe
  (`POST /orders/{id}/cover` → erst freier Lagerbestand FIFO bzw. gezielt gewählte Instanzen,
  Rest per Nachschub – woher der Ersatz kommt, ist eine Verfügbarkeitsfrage, keine zweite
  Entscheidung; `/supply` + `/cover-stock` sind darin aufgegangen); **Menge bestätigen** =
  neu (`POST /orders/{id}/confirm-quantity`, `recovery.confirm_quantity`): das Soll sinkt auf
  das Gesicherte (5 bestellt, 1 in Klärung → 4 bestellt), der Schritt ist frei, der Auftrag
  läuft normal zu Ende. **Geld bleibt ehrlich:** eine bereits **bezahlte** Verkaufsposition
  lässt sich so NICHT kürzen (409) – dafür ist die Retoure/Gutschrift da (`sale`-Kredit-Modus
  + Stripe-Refund). Damit ist auch das alte «Menge reduzieren»-TODO sauber geschlossen.
  Wächter: `test_a_deviation_takes_its_instances_out_instead_of_pausing_the_order`,
  `test_shortfall_is_one_question_with_three_answers`, `test_waiting_is_a_state_not_a_button`,
  `test_a_shortfall_blocks_only_the_step_that_needs_it`.
  *Bewusst NICHT gebaut: die **Lieferanten-Reklamation** (`purchase` im Kredit-Modus, analog
  zum `sale`-Modul) – die Gegenrichtung des Einkaufs bleibt offen; und «ab Lager gedeckte
  Teile überspringen erledigte Schritte» (ausdrücklich verworfen: ein Schritt wirkt auf die
  Instanzen seines Auftrags, eine Ausnahme je Herkunft wäre eine zweite Regel).*

- **Testnotizen-Runde 19 (die Entscheidung bleibt am Schritt, Notizen #279–#286)**:
  (1) **Was entschieden wurde, steht im Ablauf** (#281, `OrderStepInfo.resolutions`): Dass
  eine Fehlmenge **ersetzt** oder die **Menge angepasst** wurde, ist die eigentliche
  Geschichte des Auftrags – ohne Spur sah man später nur noch das Ergebnis («läuft») und
  nicht, wie es dazu kam. Die Spur ist **kein neues Feld**, sondern der **Event-Strom**:
  `recovery._record_at_step` hängt jeder Entscheidung die Schritt-id an, `orders.
  _fill_step_resolutions` liest sie je Schritt zurück, der Fluss zeigt eine Zeile
  («Menge angepasst 5 → 4», «1 ab Lager ersetzt», Wer/Wann im Hover) – auch dann noch, wenn
  der Schritt längst wieder läuft. Die Frage «welcher Schritt vermisst diesen Artikel?» hat
  damit zwei Nutzer (Nachschub-Ursprung + Deckungs-Spur) und liegt an EINER Stelle
  (`process.blocked_step_for_article`, aus `supply.py` herausgezogen).
  (2) **«Ohne Ersatz weiter» statt «Menge bestätigen»** (#280): der alte Name sagte, was das
  System tut, nicht was der Mensch entscheidet – und der Gegensatz zu «Ersetzen» ist eben:
  gar nicht ersetzen.
  (3) **Eine Objektnummer sieht überall gleich aus** (#282, `ObjId`): sie erbte die
  Schriftgrösse ihrer Umgebung und wurde im 15,5-px-Lesefeld der Auftragsspezifikation zur
  lautesten Angabe der Zeile – obwohl sie eine **Kennung** ist, keine Aussage. Jetzt feste
  12,5 px/600, tabellarisch (Fortsetzung von #263); die Positions-Aufstellung beginnt
  wieder bei der normalen Lesegrösse.
  (4) **Zustand nur, solange er etwas sagt** (#279): der fachliche Zwischenstand im
  Modul-Kopf (Beschaffung/Verkauf) entfällt, sobald der Schritt erledigt ist – dass er durch
  ist, sagt der Haken daneben, «Geliefert» stünde als zweites Wort für dieselbe Aussage.
  (5) **Abweichungs-Dialog kurz und prägnant** (#284, `ChoiceButton` mit Symbol):
  «Läuft weiter – nur das betroffene Stück wird herausgenommen» ↔ «Abbrechen – endgültig,
  nur die Abweichung läuft weiter». Der alte Untertitel behauptete noch die Pause, die es
  seit der Unterdeckungs-Runde nicht mehr gibt. Die lokale Dublette von `ChoiceButton` in
  `order-detail.tsx` ist im gemeinsamen Vokabular aufgegangen.
  (6) **Der Kopf skaliert nicht mehr** (#286, `fields.HeaderAction`): die Status-Aktion war
  32 px hoch neben 28-px-Symbolknöpfen – die Zeile wuchs in dem Moment, in dem «Freigeben»
  erschien, und schrumpfte wieder, sobald es wegfiel. Artikel und Auftrag hatten dieselbe
  Zeile zweimal ausgeschrieben; jetzt eine Stelle, exakt 28 px.
  (7) Kleineres: Menge bei **jeder** Instanz auch im Artikel-Bestand (#285, `instanceLabel`
  – Einheitlichkeit statt «bei Chargen ja, bei Einzelteilen nein»); Label «Wirkung» im
  Ausschleusen-Editor entfällt (#283 – die beiden Optionen sagen es selbst).
- **Mehrstandort – Schritt 1: «das Unternehmen» wird zu «die Standorte»** (Juli 2026,
  Migration `090`, Variante A): Ein Betrieb kann Aussenstellen haben. Umgesetzt ist bewusst
  nur das **Fundament**; Bestand, Rechte und Bedarf bleiben unverändert (siehe unten).
  **Eine Spalte, keine neue Tabelle.** `company_settings` war ein Singleton (`id == 1`) und
  trägt jetzt n Zeilen – eine je Standort. Das ist deshalb so billig, weil ein Standort im
  Modell längst existierte: `instances.location_type='company'` zeigt auf eine **Objektnummer**,
  und `locations.location_label`/`location_chain` lösen sie darüber auf. Es gab bloss immer
  nur eine davon.
  **Was einmal gilt und was je Standort gilt, ist eine Frage der Schreibstelle, nicht der
  Tabelle:** der **Hauptsitz** (`is_primary`, partieller Unique-Index = genau EINER) trägt die
  **Rechtsidentität** (UID/MWST/HR/Aktienkapital/IBAN/Rechtsform) und die **Systemkonfiguration**
  (Stripe, Shop-Währungen, Rechtstexte, Plausible, Maps); **jeder** Standort trägt Name,
  Anschrift, Kontakt (`sites.SITE_FIELDS`, gespiegelt von `schemas/admin.SiteBase` – der
  Abgleich ist getestet). Ein Nebenstandort kann eine UID gar nicht erst annehmen; sonst
  stünde dieselbe Angabe an n Stellen.
  **Die eine Auflösung ist `services/sites.py`** – in zwei Formen derselben Regel (wie
  `inventory.is_in_stock` neben `in_stock_clauses`): `primary()` schreibend (legt an, vergibt
  die Objektnummer), `find_primary()` **rein lesend** – Pflicht in fremden Transaktionen
  (Preis-Pipeline, Shop-Konfig, Provider-Wahl, PDF-Briefkopf), wo ein `commit` die halbfertige
  Arbeit des Aufrufers festschreiben würde. `admin.get_or_create_settings` delegiert nur noch
  dorthin, **keine Aufrufstelle ändert sich**.
  **Der eigentliche Bug, den das behebt:** zehn Stellen holten sich «die Firma» selbst – mal
  `id == 1`, mal ein blosses `.first()`. Bei einer Zeile war beides dasselbe; ab der zweiten
  ist `.first()` eine **willkürliche Wahl**. Am schwersten wog `logistics.target_address`: sie
  hätte JEDEM Standort-Ziel die Adresse des Hauptsitzes gegeben – Quelle und Ziel sähen für
  `classify_movement` gleich aus, und ein Transport Werk A → Werk B ginge still als
  «innerbetrieblich» durch statt als Versand mit Tarif und Label. Sie löst jetzt über die
  **Objektnummer** auf; ein Wächter hält das fest (`tests/test_sites.py`).
  **Damit fällt Mehrstandort aus der bestehenden Regel heraus, statt eine zweite zu brauchen:**
  der Zweig «zwei interne Orte mit **unterschiedlicher** Adresse → Versand» (ADR 005) war
  gebaut und toter Code – er ist jetzt lebendig. Gegen echtes Postgres verifiziert: Hauptsitz →
  Werk Nord = `outside` (Empfehlung Paket), Hauptsitz → Hauptsitz = `inside`. Ein Standort
  **ohne** Anschrift ist gültig, aber logistisch stumm (bleibt innerbetrieblich) – das Detail
  sagt es (`SiteResponse.has_address`), statt es raten zu lassen.
  **Nummernkreis unverändert global** – die Objektnummer ist eine *Identität*, kein
  Belegnummernkreis; je-Standort-Kreise würden `resolve_object_type`, den QR-Scan und
  `references.object_references` (globale Eindeutigkeit) zerlegen. Ein neuer Standort bekommt
  eine ganz normale Nummer aus `object_id_seq` und ist damit sofort **Halter**.
  **Migration ohne Datenumzug:** die vorhandene Zeile *wird* der Hauptsitz, ihre Objektnummer
  bleibt gültig – keine Zeile in `instances`/`orders`/`shipments` wird angefasst.
  **Oberfläche:** je Standort eine Feed-Zeile (Typ `organization`, admin-only wie bisher),
  «+ Standort» im FAB (nur Admin), und EIN Detailfenster in zwei Ausprägungen – Hauptsitz mit
  Rechtsidentität/Bank/MWST/Integrationen, Nebenstandort mit Name/Anschrift/Kontakt.
  Endpunkte `GET/POST /admin/sites`, `PATCH /admin/sites/{object_id}` (alle **Admin**).
  *Bewusst NICHT gebaut (kommt in späteren Schritten):* **standort-getrennter Bestand** – FIFO
  bleibt EIN Topf über alle Standorte (liegt das Teil falsch, ist das ein Transport, kein
  Fehlbestand); **Standort-Rechte** – Personal sieht weiterhin alles, der Standort ist
  Anzeige, keine Berechtigungsgrenze; **`site_id` am Prozessschritt/Auftrag** (der Bedarf
  kennt seinen Standort noch nicht, Wareneingang und Lieferadresse sind fest der Hauptsitz);
  **Absender je Standort** auf Versandbeleg und Briefkopf (die *Klassifikation* liest den
  echten Standort, der *Beleg* nennt die Firma); **Standort löschen** (bearbeiten genügt
  vorerst – ein Standort mit Bestand bräuchte sonst eine eigene Wirkungsanalyse).
  - **⚠ Vorfall beim ersten Deploy (und die Lehre daraus).** Der Mehrstandort-Deploy hat
    das ERP und die öffentliche Website lahmgelegt: der Unternehmens-Datensatz war weg,
    **kein einziger Instanz-Datensatz** liess sich laden, dazu Impressum, Shop-Konfiguration
    und Shop-Produkte. Ursache war **nicht** die Fachlogik, sondern eine Deploy-Mechanik,
    die dieses Projekt längst kennt und für die es eine benannte Vorrichtung gibt:
    **`start.sh` startet uvicorn ausdrücklich auch dann, wenn Alembic scheitert**
    («schema fix will run in lifespan»). Das Lifespan-Sicherheitsnetz
    (`main._COLUMN_SAFETY_NET`) ist dafür der vorgesehene zweite Weg – und dort fehlte
    `company_settings.is_primary`. Migration 090 lief nicht, das Modell kannte die Spalte
    trotzdem, und damit endete **jede** Abfrage auf `company_settings` in einem 500.
    Dass das so weit trägt, liegt an der Rolle der Tabelle: sie wird nicht nur im Admin
    gelesen, sondern über `locations.location_label` von **jedem Standort-Label** (also
    dem ganzen Instanz-Feed) und von **unauthentifizierten** Endpunkten (Impressum,
    Shop). Eine fehlende Spalte hier ist kein ERP-Schluckauf, sondern ein Komplettausfall.
    **Drei Korrekturen, alle strukturell:** (1) `is_primary` **und** das ebenso fehlende
    `legal_documents` (Migration 057 – dieselbe Bombe, nur noch nicht gezündet) stehen im
    Sicherheitsnetz; ein Daten-Fix (`_COMPANY_DATA_FIXES`) setzt danach genau **einen**
    Hauptsitz und legt den partiellen Unique-Index an – ohne ihn trüge nach dem
    `ADD COLUMN DEFAULT false` **keine** Zeile die Markierung und die Firma erschiene als
    blosser «Standort» ohne Rechtsidentität (genau das zweite gemeldete Symptom).
    (2) **Migration 090 ist idempotent** – repariert das Netz das Schema, versucht Alembic
    090 beim nächsten Deploy erneut; ohne Wiederholbarkeit liefe sie auf «column already
    exists» auf, bliebe für immer auf 089 stehen und würde **jede künftige Migration**
    blockieren. (3) Der Wächter `test_every_company_settings_column_is_in_the_lifespan_
    safety_net` leitet die Erwartung aus dem **Modell** ab statt aus einer gepflegten
    Liste: was nicht im Initial-Schema steht, muss im Netz stehen. Er hat `legal_documents`
    sofort mitgefunden.
    **Verifiziert, nicht vermutet:** der Vorfall ist gegen echtes PostgreSQL reproduziert
    (Spalte gezogen → dieselben 500er) und die Heilung bewiesen (echter Lifespan über die
    kaputte Datenbank → alle zehn Endpunkte wieder 200, Hauptsitz markiert,
    Rechtsidentität sichtbar, zweiter Hauptsitz von der DB abgewiesen); dazu
    `alembic stamp 089 && upgrade head` auf dem bereits reparierten Schema plus ein
    downgrade/upgrade-Zyklus.
    **Regel für künftige Spalten:** eine neue Spalte auf einer **bestehenden** Tabelle ist
    erst fertig, wenn sie in der Migration UND im Lifespan-Sicherheitsnetz steht. Die
    Migration ist die Wahrheit, das Netz der zweite Weg – und beim Ausfall zählt nur der
    zweite Weg.

- **Mehrstandort → Mehr-Gesellschaften: EIN gleichrangiger Datensatztyp «Unternehmen»**
  (Juli 2026): Die kurzlebige «Hauptsitz + kastrierte Standorte»-Zwischenstufe ist
  aufgelöst. Jetzt gibt es genau **einen** Datensatztyp (`company_settings`, Feed
  `organization`); **jede Zeile ist eine vollständige juristische Einheit** – eigene
  Objektnummer, eigene Rechtsidentität (die US-Gesellschaft hat ihre **eigene** EIN/
  Steuer/Bank). Keine Zeile ist einer anderen untergeordnet.
  **Warum die Kehrtwende:** Aussenstellen in anderen Ländern sind keine blossen Adressen –
  andere Rechtsform, Steuer, Währung, eigener Rechnungs-Aussteller. «Nur der Hauptsitz
  trägt Identität» war damit genau verkehrt; jede Gesellschaft trägt ihre eigene. Das ist
  zugleich **flacher** (eine Klasse statt Kaste) – exakt die Komplexitätsreduktion, die
  gefordert war. **Hartes No-Go bleibt gewahrt:** ein ERP, eine Website, ein Produktkatalog,
  ein Login – mehrere Gesellschaften sind **Daten in diesem einen System**, nie ein zweites
  von irgendwas.
  **Der «Betreiber» ist abgeleitet, kein Flag** (`sites.operator`/`find_operator` = das
  **älteste** Unternehmen, kleinste `id`). Er vertritt die eine Website nach aussen
  (Impressum, Rechtstexte, Fallback) und trägt die **Plattform-/Systemkonfiguration**
  (`sites.PLATFORM_FIELDS`: Stripe, Shop-Währungen, `legal_documents`, Plausible, Maps) –
  die gibt es genau EINMAL. Das frühere `is_primary` ist **aus dem Modell entfernt** (es
  stellte eine Zeile über die anderen und war die Ursache des Deploy-Ausfalls); die
  DB-Spalte bleibt vorübergehend (Migration 091 dropt sie im Folge-Deploy), SQLAlchemy
  ignoriert die nicht gemappte Spalte, das Lifespan-Netz hält sie für die während des
  Cloud-Run-Rollouts noch laufende Vorgänger-Revision intakt – **gegen echtes Postgres
  verifiziert** (neue Revision fehlerfrei auf DB MIT `is_primary`; neue Zeilen bekommen
  den DB-Default `false`, die Alt-Revision bleibt konsistent).
  **Reichweite je Feld, nicht je Rang** (`services/sites.py`): `ENTITY_FIELDS` (Name,
  Anschrift, **Rechtsidentität**, Bank, MWST) sind an JEDEM Datensatz editierbar (`PATCH
  /admin/companies/{object_id}`); `PLATFORM_FIELDS` ignoriert `apply_update` bewusst – sie
  laufen nur über die Systemkonfiguration (`PATCH /admin/settings`, trifft den Betreiber),
  damit dieselbe Angabe nicht an zwei Stellen editierbar ist. Endpunkte: `GET/POST
  /admin/companies`, `GET/PATCH /admin/companies/{object_id}` (Admin). Der frühere
  `/admin/sites` + die `Site`-Schemas/-Typen sind entfallen; `SiteResponse.is_primary` →
  `CompanySettingsResponse.is_operator`/`has_address` (beide **abgeleitet**, kein Rang).
  **Impressum: global, wechselt NICHT nach Land** – der Betreiber der EINEN Website ist die
  ausweisende Rechtsperson (`/admin/settings/public` = ältestes Unternehmen); nur die
  **Rechnung** hat je nach Warenherkunft einen anderen Aussteller (kommt als Folgeschritt).
  **Oberfläche:** `organization-detail.tsx` rendert für JEDE Gesellschaft denselben vollen
  Feldsatz (kein `isPrimary`-Zweig mehr); `/admin/einstellungen` ist auf **reine
  Plattform-Konfiguration** eingedampft (Entitäts-Felder werden am Datensatz gepflegt,
  nicht doppelt); FAB «+ Unternehmen» (Admin). Am Betreiber ein **dezenter Hinweis**
  «Betreiber der Website» + die Konzern-Kosten (Gruppen-Kennzahl) – Fakt, kein Rang.
  Wächter `tests/test_sites.py` (u. a. `test_every_company_carries_its_own_legal_identity`,
  `test_platform_config_is_never_editable_per_company`,
  `test_operator_is_derived_from_age_not_from_a_flag`).
- **Gesellschaften – vollständig im ERP, Betreiber wählbar, Währung je Gesellschaft**
  (Juli 2026, Migration `091`): Drei Ausbauten am gleichrangigen Unternehmens-Datensatz.
  **(1) Der «Betreiber» ist WÄHLBAR** (`is_operator`, partieller Unique-Index = genau EINE
  Gesellschaft trägt den Titel; `sites.set_operator` nimmt ihn allen anderen ab). Vorher
  abgeleitet (ältestes) – der Nutzer wollte ihn setzen können. `find_operator` liest die
  gewählte Zeile, **tolerant mit Alters-Fallback** (keine Markierung → ältestes; so nie «kein
  Betreiber»). `is_primary` ist damit endgültig weg – Migration 091 seedet `is_operator` aus
  ihm (der bisherige Betreiber bleibt), dann Drop von Spalte+Index; das Lifespan-Netz führt
  `is_primary` im **Drop**-Netz und `is_operator`/`currency` im **Add**-Netz (belt-and-
  suspenders, falls Alembic scheitert). **Endpoint** `POST /admin/companies/{object_id}/operator`.
  Der Betreiber trägt Impressum + Systemkonfiguration; ein Wechsel zieht sie mit (die eine
  Website hat einen Absender).
  **(2) Systemkonfiguration ins ERP geholt, `/admin/einstellungen` GELÖSCHT.** Die Seite war
  nicht verlinkt (nur per URL erreichbar) – das Unternehmen wird ausschliesslich im ERP
  gepflegt. Die Plattform-Konfiguration (Stripe/Shop/Rechtstexte/Plausible/Maps) sitzt jetzt
  als Reiter **«System»** am **Betreiber**-Datensatz (nur dort – es gibt sie genau einmal;
  `SystemConfigSection` wiederverwendet, in einen `QueryClientProvider` gehängt). Route +
  Impressum-Fallback-Link entfernt.
  **(3) Währung je Gesellschaft** (`company_settings.currency`, ISO-3, Entitäts-Feld): **auto
  aus dem Land** vorbelegt (`sites.currency_for_country`: US→USD, DE→EUR, CH→CHF; unbekannt→
  CHF). Beim Anlegen gesetzt; im Formular beim Länderwechsel **vorgeschlagen** (nicht erzwungen,
  kein Überschreiben). Das ist die **Grundlage** für «ein Preis, überall in Landeswährung» –
  die Preis-Eingabe/-Anzeige-Mechanik (Katalogpreis bleibt EIN kanonischer CHF-Betrag, Ein-/
  Ausgabe über den FX-Anker `services/fx.get_rate`) ist der **nächste** Deploy (Geldpfad
  bewusst isoliert).
  **Verifiziert gegen echtes Postgres:** Migration 091 vom echten 090-Zustand (is_operator vom
  bisherigen Betreiber übernommen, currency default, is_primary weg, zweiter Betreiber vom
  Unique-Index abgewiesen) + idempotent; Betreiber-Wechsel (US wird Betreiber, Impressum folgt,
  CH verliert Titel, DB weist zwei Betreiber ab); Währung auto (US→USD); **Rollout über das
  Lifespan-Netz** (DB im 090-Zustand → Netz ergänzt is_operator/currency, dropt is_primary,
  seedet Betreiber → alle Endpunkte 200). Wächter `tests/test_sites.py`
  (`test_operator_is_chosen_with_an_age_fallback`, `test_operator_is_editable_and_exactly_one`,
  `test_currency_is_a_per_company_field_derived_from_country`,
  `test_is_primary_is_dropped_everywhere_not_re_added`).
  **Nächste Schritte (definiert):** (4) **Anzeige in Landeswährung + EINE Kursquelle → UMGESETZT**
  (siehe eigener Bullet «Währung: EINE Kursquelle» unten). (5) **Fakturierende
  Gesellschaft aus dem Warenort ableiten** (wie ADR-005-Versand) → Beleg zeigt ihre Identität;
  **Belegnummer bleibt global** (rechtlich zulässig); Zahlungskonto je Gesellschaft mit Rückfall
  auf EIN geteiltes Stripe-Konto (US-Konto erst bei echter US-Gründung – dann nur ein Key am
  Datensatz). (6+) Steuerregime je Gesellschaft (CH live, US-Stub), Intercompany-Verkauf
  (= `sale` mit interner Partei), Konsolidierung.
- **Währung: EINE Kursquelle (unser `fx`-Anker), Adaptive Pricing AUS** (Juli 2026, Geldpfad,
  kein Schema-Migrations-Bedarf – JSONB-Zeile): Der Kunde sah im Shop z. B. € 11.80 (unser
  Tageskurs), Stripe belastete aber € 11.82 – denn der Checkout schickte **CHF** und liess
  **Stripe Adaptive Pricing** mit STRIPES Kurs in die Lokalwährung umrechnen. Das waren **zwei
  Kursquellen**. Jetzt berechnet `selling._resolve_line` je Position den Betrag in der
  **Präsentationswährung** über dieselbe Pipeline `pricing.price_view_for` (unser `fx`-Anker,
  gepinnt + „schön" gerundet) und legt ihn als `presentment_currency`/`presentment_amount` auf
  die `CheckoutIntent`-Zeile; `stripe_provider._line_item` übergibt **genau diese Währung + diesen
  Betrag** an Stripe (Adaptive Pricing bewusst **AUS**, `docs/stripe-setup.md`). Damit ist
  **Anzeige == Belastung** per Konstruktion. `base_amount_chf` bleibt die **kanonische** CHF-Grösse
  (Reservierung/Report/anteilige Erstattung – währungsunabhängige Verhältnisse); die Kasse belastet
  die Präsentationswährung, das reale Settlement kommt über `_apply_stripe_snapshot` (liest
  `settlement.currency` schon immer dynamisch) auf `sales.currency` zurück → «Meine Bestellungen»/
  Refund folgen **automatisch** (Refund proportional über den Snapshot, währungsunabhängig).
  Der Client kann **keinen Betrag vorgeben**: `checkout(currency, country)` validiert die Währung
  gegen `shop_currencies` (`resolve_currency`), der Betrag wird immer neu gerechnet. **CHF-Shops
  unverändert** (Präsentation = CHF = Basis). Welche Währung der Shop zeigt, steuert die Shop-Konfig
  (Standard/Land); der Kurs kommt aus `fx_rates`. **ERP sichtbar:** der tote Feld-Rückgabewert
  `previews` ist wiederbelebt – Reiter «Verkauf» → «Kundenpreis» zeigt den Hauptpreis in JEDER
  Shop-Währung (dieselbe Pipeline, die belastet), live beim Ändern des CHF-Basispreises. Wächter
  `tests/test_sales.py` (`test_stripe_line_item_charges_presentment_currency`,
  `…_falls_back_to_chf_for_old_intents`, `…_subscription_keeps_presentment_currency`,
  `test_checkout_threads_presentment_currency_and_recomputes_amount`,
  `test_stripe_provider_does_not_rely_on_adaptive_pricing`). *Bewusst NOCH offen: Preis-**Eingabe**
  in Landeswährung (heute EINE CHF-Zahl gepflegt, Fremdwährung nur Anzeige – ein lossy Rück-
  Umrechnen wäre die Alternative), per-Gesellschaft-Produktwährung (Intercompany), Shop-Währungs-
  umschalter für den Kunden (Backend `resolve_currency`/Produkt-Endpunkte tragen `currency` bereits).*
- **Mehr-Gesellschaften & Weltmärkte – Gebietskarte (ADR 006, `docs/adr/006-mehr-gesellschaften-
  maerkte.md`, Migration 092, Slice 1)**: Die Welt ist in feste **Regionen** partitioniert
  (`services/geography.REGIONS`: NAM/EUR/ASIA/LATAM/AFR/MEA/OCE) + umfassende ISO-2-Land→Region-Map
  (unbekannt → Betreiber). **Jede Region gehört genau EINER Gesellschaft**; der **Betreiber** besitzt
  per Default die ganze Welt, andere Gesellschaften «beissen sich» Regionen ab
  (`company_territories`, Region unique – hält NUR Abweichungen). So gehört **jeder Fleck der Erde
  jemandem** (Totalität, «es kann nie kein Land ausgewählt werden»). Die EINE Auflösung ist
  `sites.company_for_country(country)` = **Land → Region → Territorium-Besitzer → Betreiber-Fallback**
  (rein lesend). Die **fakturierende Gesellschaft** (Seller of Record) wird daraus **abgeleitet**
  (kein Dropdown): ausschlaggebend ist die **Rechnungsadresse** (Kundensitz), die **Steuer** folgt
  getrennt der **Lieferadresse** (Stripe Tax), der **Warenort** ist der Versand-Absender (ADR 005).
  Sie friert – wie Preis/Währung – bei Freigabe/Zahlung ein (Slice 2). Endpunkte `GET/PUT
  /admin/territories`; Frontend **abstrakte Weltkarte** (`components/erp/territory-map.tsx`, Region-
  Kacheln geografisch angeordnet, Klick-Zuweisung, Betreiber-Default) im Unternehmens-Reiter
  **«Gebiete»** (an jeder Gesellschaft, hebt deren Regionen hervor). **Neue Tabelle** → `create_all`
  deckt sie im Lifespan (kein Spalten-Safety-Net nötig – ausserhalb der 090-Ausfallklasse); gegen
  echtes PG16 verifiziert (create_all-Pfad, Auflösung, Totalität, Idempotenz, Downgrade,
  Lifespan-Neuschöpfung). Wächter `tests/test_geography.py`. **Slice 2 (UMGESETZT, Migration 093):**
  `sales.seller_company_object_id` – die fakturierende Gesellschaft je Verkauf, aus der
  **Rechnungsadresse** des Kunden abgeleitet (`sale._seller_object_id_for_customer` →
  `company_for_country`) und – wie Preis/Währung – **bei Bestätigung/Zahlung eingefroren**
  (`sale._freeze_seller`, idempotent; in `_apply_transition` UND `finalize_paid`). Die EINE
  Auflösung `sale.seller_company_for_order` (Snapshot ≻ live aus Kundenland ≻ Betreiber, rein
  lesend) speist **Beleg-Briefkopf** (`documents.py:_company(db, order)`) UND **Versand-Absender**
  (`logistics._sender_company` ersetzt `_settings`). Ein Nicht-Verkaufs-Auftrag (kein Kunde) →
  Betreiber wie bisher. Neue Spalte auf bestehender `sales`-Tabelle → **im Lifespan-Safety-Net**
  (090-Lehre); gegen echtes PG16 verifiziert (Freeze idempotent trotz geänderter Karte = Beleg-
  Unveränderlichkeit, Migration idempotent/downgrade, `_ensure_columns`-Netz).
  **Slice 3 (UMGESETZT, ohne Migration):** zwei Verfeinerungen, beide ohne Schema-Änderung.
  (a) **«Fakturiert durch» am Auftrag** (`OrderResponse.seller_company_object_id/_name`, gefüllt in
  `orders.to_order_response`): wer fakturiert, war bis dahin erst im fertigen PDF sichtbar – jetzt
  steht es in der Auftragsspezifikation, **bevor** der Beleg entsteht (Objektnummer klickbar).
  Gesetzt **nur bei einem Verkauf/einer Retoure** (ein Produktions-/Beschaffungsauftrag hat keinen
  Kunden, also keinen Fakturierenden) und nur fürs **Personal** sichtbar – eine interne
  Buchungs-Angabe.
  (b) **Ausnahmen je Land** (`geography.is_country_code`/`normalize_area`, `sites.country_map`/
  `_default_owner_id`/`_claim_owner`): ein einzelnes Land kann von seiner Region abweichen («Europa
  gehört der GmbH, Liechtenstein aber der Schweizer AG»). Das ist **kein zweiter Mechanismus**,
  sondern derselbe Anspruch feiner geschnitten: Region **und** Land stehen als Gebiets-Code in
  derselben Spalte (`company_territories.region`), der Unterschied ist aus der **Form abgeleitet,
  nicht gespeichert** – ISO-2 hat 2 Zeichen, jeder Regions-Code ≥ 3, eine Kollision ist per
  Konstruktion unmöglich (Wächter). Vorrang: **Land ≻ Region ≻ Betreiber**. Gespeichert wird nur,
  was **abweicht**: eine Zuweisung an die ohnehin zuständige Gesellschaft LÖSCHT die Zeile (ein
  Land fällt dann auf den Besitzer seiner Region zurück, nicht auf den Betreiber). Die Oberfläche
  leitet «ist Ausnahme» daraus ab, dass der Besitzer eines Landes von dem seiner Region abweicht –
  **kein zweites Flag**; Ländernamen kommen aus `Intl.DisplayNames` (keine zweite Länderliste im
  Repository). EIN Panel für Region wie Land, Ausnahmen als Liste unter der Karte, die Region-Kachel
  nennt die Zahl ihrer Ausnahmen. Gegen echtes PG16 verifiziert (27 Prüfungen: Totalität ohne jeden
  Anspruch, Land schlägt Region, Zurücksetzen entfernt die Zeile, `country_map` == Einzelauflösung
  über alle 225 Länder, unbekanntes Gebiet → 400, ein Gebiet = ein Besitzer, Seller folgt der
  Ausnahme; dazu 8 Prüfungen am Auftrags-Embed inkl. Snapshot schlägt Live-Ableitung).
  *Bewusst später: Steuer-Origin je
  Gesellschaft (heute hart CH; Stripe Tax rechnet destinationsbasiert real), Intercompany
  (CH→US Transferpreis), eigenes Stripe-Konto je Gesellschaft, Sub-Land-Gebiete (US-Bundesstaat).
  **Impressum bleibt global** (Betreiber); **Belegnummer bleibt global** (ein Nummernkreis).*

- **Testnotizen-Runde 20 (der ERP-Benutzer ist der Master, das Profil der Spiegel, Notizen
  #294 #295)**: Der Benutzer-Datensatz im ERP und die Profileinstellungen zeigen **dieselben
  Daten** – aber sie sahen und funktionierten völlig verschieden: hier ein Raster aus neun
  Abschnitten mit eigener `Field`-Optik (Alt-Palette `#2563eb`/slate), Speichern über einen
  Knopf und eine Rechnungsadresse mit einem wirkungslosen Häkchen «Gleich wie Adresse»; dort
  drei Container, EIN Auto-Save, Google-Adress-Suche und ein Schalter, der die Rechnungsfelder
  tatsächlich **spiegelt**. Der Nutzer hat die bessere Seite benannt (#294: «in diesem
  speziellen fall möchte ich, dass dies von den Profileinstellungen übernommen wird») – also
  **übernimmt der Master die Struktur des Spiegels**, nicht umgekehrt: Der Profil-Reiter ist
  jetzt dieselbe Anatomie (Persönliche Angaben · Adressen · Kommunikation) aus **denselben
  Bausteinen** (`account/field.tsx`, `erp/address-field.tsx`, `account/use-autosave.ts`) – kein
  Nachbau, sondern Wiederverwendung, damit die beiden nicht wieder auseinanderlaufen können.
  **Die Spiegelung ist damit auch fachlich echt:** «Rechnungsadresse = Lieferadresse» kopiert
  im ERP jetzt dieselben Felder wie im Konto (vorher ein Häkchen, das nichts kopierte – zwei
  Wahrheiten, je nachdem wo man es setzte). **Was das ERP MEHR zeigt, bleibt** (#295, «das ERP
  muss ALLES können»): Rolle, Bankverbindung, die **admin-pflegbare** Anstellung (im Konto
  read-only) und der Block **System** (E-Mail · Anmeldung · Passkeys · Login/Erstellt/Geändert ·
  Firebase-UID). Nicht-Admins sehen dieselbe Struktur read-only (die Adresse als kompakte
  Zusammenfassung statt als Sucheingabe). Der Speichern/Verwerfen-Streifen am Fensterrand ist
  entfallen – Auto-Save wie überall, Rückmeldung im Karten-Kopf.

- **Testnotizen-Runde 21 (weniger Felder, dafür Pflicht; die Welt wird gemalt; Notizen
  #300–#323)**: Der Unternehmens-Datensatz hatte **24 Eingabefelder** – und die Frage des
  Nutzers war für fast jede Gruppe dieselbe: *brauche ich das überhaupt, jetzt oder in
  Zukunft?* Der Massstab war darum nicht «könnte man mal brauchen», sondern: **nennt es
  jemand auf einem Beleg, im Impressum oder in einer Regel?** Übrig bleiben **neun** – und
  genau deshalb dürfen sie **Pflicht** sein (#323: ein Formular, in dem alles optional ist,
  sagt nichts; eines mit neun Pflichtfeldern ist in zwei Minuten vollständig).
  (1) **Gestrichen, mit Begründung** (Modell, Schema, `ENTITY_FIELDS`, Frontend-Typ, API-
  Mapping): **Handelsregister-Nr., HR-Kanton, Aktienkapital** (#307) – in der Schweiz IST die
  HR-Nummer seit 2016 die UID, der Kanton steht im Register, Kapital muss ein Impressum nicht
  nennen; drei Zeilen, die abschrieben, was die UID schon sagt. **QR-IBAN, Bankname, BIC**
  (#313) – die IBAN trägt Land, Bank und Konto; die QR-Rechnung ist nicht gebaut, und für
  SEPA braucht es keinen BIC. **MWST-Methode/-Periode** (#314/#319/#321) – reine
  Buchhaltungs-Parameter (Phase 3), die nichts im System auswertete. **Zahlungsfrist und
  Skonto** (#316/#317/#318) – die gehören in die **Offerte**, wo sie je Geschäft verhandelt
  werden, nicht als stiller Firmen-Default. **OSS/VIES** (#320) – nie ausgewertet; die
  destinationsbasierte EU-Steuer rechnet Stripe Tax. Nachweis für alle: ausserhalb von
  Modell/Schema/Formular tauchte keines davon in einer Regel auf.
  (2) **Zwei Angaben füllt jetzt das System selbst.** Die **Währung** folgt dem Land (#304,
  `sites.currency_for_country`) und steht als Wert da, nicht als Auswahl – ändern geht über
  «Ändern», also bewusst, nicht im Vorbeitippen («auch wenn nicht gerade super einfach»). Die
  **Website-Adresse** ist die des Deployments (#309, `sites.website_url` ← `FRONTEND_BASE_URL`):
  read-only angezeigt, weil sie im Impressum und auf dem Briefkopf steht – ein Eingabefeld
  daneben wäre eine zweite Wahrheit, die beim ersten Domain-Wechsel still falsch wird.
  (3) **Der Name ist hart Pflicht** (#301/#302, jetzt «Unternehmensname»): er ist zugleich das
  **Halter-Label** (`locations.location_label`), eine namenlose Gesellschaft liesse jede
  Standort-Anzeige leer, die auf sie zeigt. `sites.apply_update` weist ihn leer ab (Anlegen tat
  das immer schon). Anschrift, UID, MWST-Nr., E-Mail, Telefon, Rechtsform und IBAN sind
  markierte Pflichtfelder (#305/#307/#310/#313) – gelbes Sternchen wie im Konto, kein Blocker.
  (4) **Dieselbe Anatomie wie Benutzer und Profil** (#308/#311/#312): EIN Formular, EIN
  **Auto-Save** (Speicher-Streifen weg), Karten statt Sektionsraster, **keine Symbole** in den
  Überschriften. Die Alt-Bausteine `Field`/`Sec` (slate/blue-Altpalette) wurden nur noch hier
  genutzt und sind entfallen; die `Card` wohnt jetzt im gemeinsamen Vokabular (`fields.tsx`).
  (5) **Rechtsform schlägt sich selbst vor** (#303): Freitext mit `datalist` je Land (CH → AG ·
  GmbH · Einzelunternehmen …, US → Inc. · LLC …). Eine API dafür gibt es nicht – die einzige
  verbindliche Quelle ist die ISO-20275-Liste der GLEIF, ein Download mit ~2600 Einträgen ohne
  Abfrage-Endpunkt; für acht Vorschläge der falsche Preis, und Rechtsformen ändern sich in
  Jahrzehnten. Also dieselbe Bauart wie die Land→Währung-Zuordnung: eine kleine, dokumentierte
  Tabelle im Frontend.
  (6) **GPS → Adresse** (#306, `AddressField`): «Aktuellen Standort verwenden» holt die
  Koordinaten vom Browser und lässt Googles Geocoder daraus einen Treffer machen – der durch
  **denselben** Zweig ins Formular läuft wie ein gewählter Vorschlag (`applyPlace`), statt
  einen zweiten Weg aufzumachen. Gilt für jede Adress-Eingabe, nicht nur die Firma.
  (7) **Die Weltkarte ist jetzt eine Karte** (#322, `components/erp/world-map.tsx`): 5°-Raster,
  72×25 Zellen, **nur Linien und Ecken** – jede Zelle ist ein echtes geografisches Feld, die
  Form entsteht aus der Menge. Umriss-Polygone wären bei zehn Stützpunkten Flecken geblieben;
  erkennbar wird eine Weltkarte über die *Verhältnisse*, und die liefert ein Raster geschenkt.
  Grönland und die Antarktis fehlen **bewusst**: sie liegen in keiner Region, und eine Fläche
  einzufärben, die keiner Region gehört, wäre eine gemalte Behauptung. Russland ist bis in den
  Osten europäisch eingefärbt – so steht es in `geography.py`, und die Karte darf nicht anders
  behaupten als die Auflösung entscheidet. Darunter dieselbe Aussage als Liste (die Karte kann
  nicht sagen, wie eine Gesellschaft heisst; die Liste nicht zeigen, wo Ozeanien liegt).
  (8) **Der Feed atmet** (#300): mehr Polsterung, kleineres Symbol – und der Zustand ist ein
  **Punkt mit Wort** statt einer gefüllten Pille (`StatusBadge plain`). Vierzig Pillen
  untereinander waren das, was die Liste schwer machte; das Design-System nennt Punkt+Wort
  ohnehin als Regelform und die gefüllte Badge als Ausnahme für Detail-Köpfe.
  > **Folge-Deploy:** die 14 DB-Spalten bleiben vorerst stehen (SQLAlchemy ignoriert sie) und
  > werden erst im **nächsten** Deploy per Migration gedroppt – exakt wie `is_primary` in 090→091.
  > Ein Drop im selben Deploy trifft die während des Cloud-Run-Rollouts noch laufende
  > Vorgänger-Revision, die sie noch mappt: das ist die Ausfallklasse von Migration 090.

- **Eine Instanz ist eine MENGE, kein Ding** (Juli 2026, `tests/test_quantity_rules.py`):
  Auf die Frage, ob eine Charge à N intern nicht besser **N Zeilen à 1 Stück** wäre (damit
  überall dieselbe Logik gilt wie beim Einzelteil), lautet die Antwort **nein** – und die
  Begründung steht jetzt am Modell (`models/instance.py`), damit sie nicht erneut erarbeitet
  werden muss: (a) eine Charge darf **gebrochen** sein (2.5 kg, 0.75 m²) – «2.5 Zeilen» gibt
  es nicht, und genau dafür existiert `batch`; (b) die **Objektnummer ist systemweit
  eindeutig** und der Schlüssel für QR-Scan, `references.object_references` und
  `locations.location_chain` – N Zeilen mit derselben Nummer bräuchten überall eine neue
  Antwort auf «welche davon?»; (c) eine 1000er-Charge wären 1000 Zeilen je Reservierung,
  FIFO-Zugriff und Umlagerung. Der Preis ist die Teilmengen-Logik, und die steht an genau
  zwei Stellen (`reservation.py` = wer beansprucht wie viel, `location_split.py` = wo liegt
  wie viel).
  **Die Beobachtung dahinter war trotzdem richtig** – es gibt eine wiederkehrende
  Fehlerklasse, sie heisst nur anders: **«Zeilen zählen statt Mengen summieren»**. Eine
  Charge à 500 ist EINE Zeile und FÜNFHUNDERT Stück, also liefert `len(insts)` die Zahl 1,
  wo 500 gemeint sind (Testnotiz #72: Prüfumfang; #333: Bestands-Filter). Statt weiterer
  Einzelfixes hält ein **AST-Wächter** die Regel: kein Mengen-Feld darf aus einer Anzahl
  befüllt werden. Er fand auf Anhieb **drei** Stellen – `provisioning._sub_order`
  (`quantity=len(insts)`), `customer_returns.request_return` und `routers/orders.py` (beide
  Retoure: eine zurückgegebene Charge à 5 Stk wurde als «1 Stk» gutgeschrieben; im selben
  `orders.py`-Zweig summierte die Nachbarzeile korrekt). Frontend-Pendant: `lib/process.ts`
  liefert `sumQuantity`/`formatQty` als die EINE Mengen-Stelle.
  **Und die Unterscheidung selbst ist geschrumpft:** `Instance.kind` ist jetzt ein
  **Etikett**, keine Regel – kein Fachmodul verzweigt mehr darauf (Wächter
  `test_the_batch_unit_difference_lives_in_exactly_one_module`). Möglich wurde das durch
  zwei Umbauten in der Datenerfassung:
  (1) **Die Stichprobe wird nach MENGE gezogen** (`inspection.sample_capacity`): jede Instanz
  liefert so viele Proben, wie ihre Menge hergibt, verteilt reihum. Daraus fällt beides
  heraus, was vorher zwei Zweige waren (Einzelteil: N Instanzen à eine Probe; Charge: eine
  Instanz mit N Proben) – **und der Fall «mehrere Chargen» wird zum ersten Mal richtig
  bedient**: die alte Bedingung `len(insts) == 1 and kind == 'batch'` griff nur bei *einer*
  Instanz, zwei Chargen à 100 ergaben darum **2** Proben statt 10.
  (2) **Was nicht beprobt wurde, wird nicht beurteilt** (`inspection.sample_verdicts`) – ein
  **ernster Fehler**: `_apply_per_instance_qc` gab JEDER Instanz des Auftrags ein Urteil, und
  wer nicht in der Stichprobe war, fiel über den Default `False` durch. Eine **bestandene**
  20 %-Stichprobe sperrte damit die übrigen 80 % (`quality='blocked'`) – sie verschwanden aus
  FIFO, Bestand und Verfügbarkeit, obwohl die Prüfung bestanden war. Eine Stichprobe sagt
  etwas über die gezogenen Stück; reicht das nicht, stuft `escalate_decision` auf 100 % hoch,
  und dann ist jede Instanz beprobt. Gegen echtes PostgreSQL nachgewiesen (vorher 4 von 5
  gesperrt, jetzt 0; Durchfaller werden weiterhin gesperrt).

- **Testnotizen-Runde 22 (wer arbeitet noch daran?, Notizen #324–#340)**: Zwei echte Fehler
  und eine Reihe Farb-/Wortkorrekturen.
  (1) **Freigegeben wird erst, wenn KEIN Auftrag mehr an der Instanz arbeitet** (#332,
  `process._worked_on_by_a_running_order`). Gemeldeter Fall: eine **Abweichung** auf eine
  Instanz eines noch **laufenden** Erzeugungsauftrags wurde abgeschlossen – und gab die
  Instanz frei. Sie stand damit «Freigegeben» am Lager (FIFO-verfügbar), während sie
  tatsächlich noch in Produktion war. Die Regel aus Notiz #262 («freigegeben wird von dem
  Auftrag, der zuletzt daran gearbeitet hat») war richtig gemeint, aber nur in EINE Richtung
  gebaut: sie prüfte, was in einer offenen Abweichung steckt, nicht, ob der **Erzeuger** noch
  läuft. Jetzt zählt der Status der höchstens zwei beteiligten Aufträge (Erzeuger
  `order_id`, festes Subjekt `subject_of_order_id`): ist einer noch `released`, wird nicht
  freigegeben. Der #262-Fix bleibt gültig, weil ein **abgebrochener** Auftrag nicht
  `released` ist – er hält nichts fest. Wächter
  `test_an_instance_is_not_released_while_another_order_still_works_on_it`.
  (2) **Ein leeres Pflichtfeld ist keine Datenbank-Verletzung** (#338): eine geleerte
  Rechtsform schickte `null` in eine NOT-NULL-Spalte, und der rohe psycopg2-Dump
  («NotNullViolation … Failing row contains (2, Inexxio LLC, null, Dah…») landete im
  Formular. Zwei Korrekturen: `sites._NOT_NULL_TEXT` schreibt für diese Spalten `""` statt
  `NULL` (leer heisst «noch nicht ausgefüllt», nicht «kein Wert erlaubt»), und ein eigener
  `IntegrityError`-Handler macht aus einem verletzten Constraint einen **400 mit einem
  Satz**, der die Spalte nennt – die Ursache gehört ins Log, nicht in die Oberfläche.
  (3) **Die Weltkarte, einen Tick kräftiger und mit runden Ecken** (#340/#336): jeder
  Gesellschafts-Ton hat jetzt **drei** Stärken – `dot` (Punkt/Kontur), `land` (die Fläche)
  und `bg` (Chips/Zeilen); die Karte nutzte bisher `bg` und verschwand darin. Die Ecken
  rundet ein SVG-Filter (weichzeichnen → Alpha hart zurückschneiden) je Region: er
  verschmilzt die Zellen einer Region zu EINER Fläche mit runder Aussenkante und lässt
  zwischen zwei Regionen genau die Naht stehen, die vorher fehlte.
  (4) **Der Beschaffungs-Ablauf trägt EINE Tönung** (#329): vorher lagen drei Flächen
  ineinander, von denen zwei identisch waren (Modul-Karte getönt → Stufen im *gleichen* Ton →
  weisser Eingabe-Block). Jetzt tönt nur die Modul-Karte; die Stufen sind **weisse Karten**
  darauf, und die aktive hebt sich über ihren **Rand** in Modulfarbe ab, mit nahtlos
  anhängendem Arbeitsbereich. Struktur vor Fläche.
  (5) **«Ausschleusen» heisst «Aussondern»** (#328) – der Begriff aus der Qualitätssicherung
  («Aussonderung fehlerhafter Teile»); «Ausschleusen» klang nach Logistik und sagte nicht,
  was mit dem Teil geschieht. Umbenannt in der Registry (`domain/event_types.py`), das
  Frontend spiegelt sie (Mirror-Test).
  (6) **Der Bestand zählt Stück, nicht Instanzen** (#333): eine Charge ist EINE Instanz über
  500 Schrauben – «2» als Bestand war schlicht falsch. Die Filter-Chips summieren jetzt die
  Menge und nennen die Einheit.
  (7) **Status ist EINE Form** (#334): die zwischenzeitliche «Punkt + Wort»-Variante im Feed
  ist wieder entfallen – derselbe Zustand darf nicht je nach Ort anders aussehen. Die Luft
  im Feed (#300) kommt aus Polsterung und Zeilenabstand, nicht aus einer zweiten Form.
  (8) **Betreiber-Stern in der Kopfzeile** (#339): «Als Betreiber der Website festlegen» war
  ein Knopf mitten in den Stammdaten – dabei ist das eine Rolle **über** dem Datensatz. Jetzt
  ein Stern bei den übrigen Kopf-Aktionen (gesetzt: leuchtend als Tatsache; nicht gesetzt:
  leiser Knopf, Erklärung im Hover).
  (9) **Weiche Format-Prüfung für Telefon/E-Mail** (#326, `account/field.fieldFormatIssue`):
  melden statt blockieren. Eine strenge Telefon-Regex sperrt irgendwann eine echte Nummer
  aus, und libphonenumber wären ~150 kB für ein Feld, das niemand automatisiert wählt –
  also ein Hinweis bei offensichtlichem Unsinn (zu wenige Ziffern, fremde Zeichen),
  gespeichert wird trotzdem.
  (10) Kleineres: Auftrags-Inhalt auf **880 px zentriert** wie die übrigen Detailfenster
  (#327 – vorher lief die Spezifikation über die volle Breite, während der Fluss darunter
  bei 600 px zentriert blieb); Scan-Knopf der Datenerfassung in der ruhigen schwarzen
  Hauptaktion statt blau-auf-gestrichelt (#330, letzte Stelle der Alt-Palette in der Datei);
  Website-Hinweis (#337) und Gebiets-Erklärabsatz (#335) entfallen; der AGB-Nachweis im
  Konto entfällt (#325 – Version und Datum gehören ins Dokumentenmanagement, sonst zwei
  Anzeigen derselben Tatsache).
  *#324 (GPS für die Lieferadresse im Konto) war bereits erfüllt: die GPS-Übernahme sitzt in
  `AddressField` und gilt damit für **jede** Adress-Eingabe – im Konto über «Ändern».*
  *#331 (fehlende Unterdeckungs-Info) ist keine Lücke: die Fehlmenge wird an dem **Schritt**
  gemeldet, der das Subjekt braucht – das ist die «Es fehlt»-Zeile, die angeheftet wurde. Ein
  Auftrag ohne Subjekt-Schritt (nur Beschaffung/Ressource) meldet weiterhin nichts; das ist
  bewusst so, weil ihm nichts fehlt, was er selbst bräuchte.*

- **Szenario-Durchlauf: alle implementierten Abläufe end-to-end nachgespielt (Juli 2026)**:
  **34 Szenarien / 100 Prüfungen** über die **echten** Service-Pfade gegen echtes
  PostgreSQL 16 – Erzeugung (Einzelteil/Charge/Bruchmenge), Datenerfassung (100 %,
  Teil-Stichprobe, Hochstufung, Durchfaller → Abweichung → Klärung), Abweichung/Abbruch/
  Zurücknehmen/Kette, Bestand/FIFO, Unterdeckung/Nachschub/«ohne Ersatz weiter»/gezielte
  Deckung, Aussondern (ganz · Teilmenge · Sperren/Entsperren), Verkauf + Retoure (Slice,
  ganze Instanz, Kulanz), Made-to-Order über den Nachschub, Ressource (Verbrauch ·
  Betriebsmittel · Fehlmenge), Bewegung/Standort-Verteilung, Sicherheitsbestand,
  Beschaffung (einzeln und mehrpositionig), Dokument-Schritt, Artikel-Deaktivierung,
  Wiederkehr, Mehrpositionen-Verkauf. **Vier echte Fehler**, alle aus derselben Wurzel:
  *seit den Bruchmengen (Migration `055`) ist jede Menge ein `Decimal`* – und an vier
  Stellen war das noch nicht angekommen.
  (1) **Der Prozessschritt «Ressource» war komplett unbenutzbar.** `resource_usages.details`
  bekam die entnommene Menge als `Decimal`; `json.dumps` kann das nicht, also brach **jede**
  Verbuchung eines Verbrauchs mit einem 500 ab – nicht beim Setzen des Feldes, sondern erst
  beim `flush`, mitten in der Transaktion. Der Event-Strom hatte seine eigene Normalisierung
  (`events._json_safe`), die elf **anderen** JSONB-Spalten nicht. Die Normalisierung sitzt
  jetzt an der **Grenze zur Datenbank** (`core.database.json_safe` als `json_serializer` der
  Engine): eine Stelle, und jede neue JSONB-Spalte erbt den Schutz. Sie ist ein **Netz, kein
  Vertrag** – wo es auf den Rappen ankommt (Geld, Reservierungen, Standort-Teilmengen),
  schreibt der Fachcode weiterhin bewusst **Strings**.
  (2) **Eine Retoure blähte den Bestand auf.** Die Rückgabe einer ganz verkauften Instanz
  buchte `max(Menge, verkauft, 1)` zurück – der feste Boden machte aus einer verkauften
  0.5-kg-Charge **1 kg**. «Mindestens eins» ist eine Aussage über *Stück*, nicht über
  *Mengen*. Jetzt gilt: zurück kommt, was hinausging (Event-Strom); Instanz-Menge und die 1
  sind nur noch Rückfälle für Altdaten.
  (3) **Nach einer Teil-Verschrottung war der Rest scheinbar belegt.** Es gab zwei fast
  gleiche Entnahme-Funktionen, die je EINEN halben Job machten: `consume` löste den Anspruch
  des Entnehmers, `reduce_quantity` deckelte fremde Ansprüche – und das Verschrotten griff
  zur falschen. Eine Charge à 10 mit 5 reservierten Stück behielt nach dem Verschrotten
  dieser 5 ihre Reservierung über 5 auf einer nur noch 5 Stück grossen Instanz: frei = 0.
  FIFO übersah den Rest, andere Aufträge meldeten eine Fehlmenge, die es nicht gab, und die
  **Auto-Nachbestellung bestellte den Sicherheitsbestand ein zweites Mal** (im Test: 8 statt
  3). Jetzt gibt es **eine** Regel – `reservation.take(inst, qty, by_order_id=…)` – und sie
  tut beides; die drei Aufrufer (Verbrauch, Verkauf, Verschrottung) teilen sie sich.
  (4) **Das Schema liess sich nicht aus den Migrationen aufbauen.** Eine Datenreparatur
  (`074`) griff auf `article_process_steps.locked` zu – eine Spalte, die **nie eine
  Migration angelegt** hatte (sie stammte aus dem Lifespan-`create_all` und wurde von `081`
  wieder entfernt). Auf einer frischen Datenbank brach `alembic upgrade head` genau dort ab;
  die laufende Umgebung merkt davon nichts, ein neues Projekt oder eine Wiederherstellung
  scheitert – dieselbe Ausfallklasse wie beim Deploy von Migration `090`: es zeigt sich erst,
  wenn es zählt. Die Reparatur überspringt jetzt, was es nicht gibt (wie `079` es immer
  schon tat), und die **CI baut das Schema bei jedem Push von null auf** (Postgres-16-Service
  + `alembic upgrade head` in den Quality gates) – die Behauptung «Alembic ist die
  Schema-Wahrheit» ist damit nachgewiesen statt geglaubt.
  **Kein Fehler, aber eine Sackgasse mit Weg nach vorn:** eine Charge **ohne** Standort lässt
  sich nicht teilverlagern – nach «10 von 1000 ans Band» lägen 990 weiterhin nirgends, und
  genau das kann die Verteilungs-Map nicht sagen (bei einem einzigen Slice ist der Skalar die
  Wahrheit und würde behaupten, die GANZE Charge sei am Band). Die Ablehnung bleibt, sie
  nennt jetzt aber den Weg: erst den gesamten Bestand einlagern, danach Teilmengen verlagern.
  **Bestätigt richtig** (Szenarien ohne Befund): Auto-Abschluss und Freigabe erst, wenn kein
  Auftrag mehr an der Instanz arbeitet; bestandene Teil-Stichprobe sperrt nichts, eine
  **durchgefallene** stuft erst auf 100 % hoch und schliesst erst dann endgültig ab;
  Abweichung nimmt ihr Stück heraus statt den Auftrag anzuhalten, darf ihre **eigene**
  Abweichung haben, und «Zurücknehmen» gibt die Bindung über die EINE Aufräum-Stelle
  zurück; Verschrotten löst **alle** Reservierungen, sodass die Fehlmenge eines fremden
  Auftrags ehrlich sichtbar wird; Ausschuss ist terminal **und** standortlos, Sperren
  reversibel unter Erhalt von Standort/Menge/Reservierungen; ein Komponenten-Bedarf
  blockiert den Schritt statt still unterzuliefern; Betriebsmittel werden genutzt, nicht
  verbraucht; ein Mehrpositionen-Verkauf hat **einen** `sale`-Schritt mit einem Beleg je
  Position, eine Mehrpositionen-**Beschaffung** dagegen je Position eine eigenständig
  fortschreitende Bestellung; Kulanz (keine Rückgabe-Bewegung) lässt die Ware beim Kunden;
  eine bezahlte Position lässt sich nicht still kürzen; ein Dokument ohne Parteien ist mit
  dem Ausstellen freigegeben; das Deaktivieren eines Artikels übergibt laufende Instanzen
  an einen Abweichungsauftrag statt sie herrenlos zu lassen. **Kein Überverkauf, bewiesen
  statt begründet:** ein Verkauf ohne Bestand bindet nichts, sein Schritt ist `blocked`,
  und JEDER Ausführungs-Endpunkt löst über `process.resolve_exec_step` auf, das «aktiv»
  verlangt – gedeckt wird über den Nachschub, dessen Stück beim Abschluss an den Eltern
  gepinnt werden. Wächter: `tests/test_quantity_rules.py`
  (`test_every_json_column_survives_a_decimal`, `test_a_returned_quantity_has_no_floor_of_one`)
  und `tests/test_fractional_quantities.py: test_take_releases_the_own_claim_and_trims_the_others`.

- **Vereinfachung: zwei if/else-Ketten sind Tabellen geworden (Juli 2026)** – beide ohne
  Verhaltensänderung, beide nach demselben Muster: *per-Typ-Wissen gehört in die Registry,
  nicht in eine Kette.*
  (1) **«Woran sieht man einem Schritt an, dass er durch ist?»** stand als if/elif über die
  Schritttypen in `process._fact_status` – dieselbe Aussage wie `domain/event_types.py`, nur
  an einer zweiten Stelle: ein neuer Typ musste in beiden gepflegt werden, und sie konnten
  still auseinanderlaufen. Jetzt deklariert jeder Eintrag `status_field` / `done` / `failed`
  (`None` = die blosse **Existenz** der Fachzeile ist die Erledigung – Bewegung, Ressource,
  Aussondern), und die Ableitung ist EINE Regel: **19 Zweige → 6**. Die eine Ausnahme ist
  bewusst generisch formuliert: ein Fehlschlag, den ein Folgeauftrag geklärt hat
  (`resolved_by_order_id`), gilt als erledigt – heute trägt nur die Datenerfassung dieses
  Feld, die Regel «geklärt ist erledigt» gilt aber für jeden Typ, der es bekommt.
  (2) **«Welche Felder trägt ein Schritt-Typ?»** entschied der Konstruktor in
  `routers/article_process._create` über ~14 einzelne `x if is_document else None` plus drei
  Flag-Variablen davor. Die Frage war nur durch Absuchen aller Zeilen zu beantworten, und ein
  neuer Typ hiess «überall eine Bedingung ergänzen». Jetzt liefert je Typ EINE Funktion genau
  seine Spalten (und prüft, was zu prüfen ist); alles andere bleibt leer (Modell-Default):
  **30 Zweige → 5, 65 → 34 Zeilen**. Wächter `test_a_step_type_only_fills_its_own_columns`
  (jeder Typ füllt nur seine eigenen Spalten, Beschaffung nie Lieferant UND Webshop) und
  `test_step_status_semantics_live_in_the_registry` (kein Statuswert mehr in der Ableitung).
  Gegen echtes PostgreSQL für **jeden** Schritttyp gegengeprüft: die geschriebene Zeile ist
  spaltenweise identisch zur vorherigen Fassung.
  *Bewusst NICHT angefasst:* `main._ensure_columns` – der Lifespan-Schutz ist bereits
  tabellengetrieben (je Schleife eine Art Schema-Reparatur); seine Zweige sind der Sache
  geschuldet, und ausgerechnet dieses Netz für Kosmetik anzufassen wäre nach der
  Migration-090-Geschichte das falsche Risiko.

- **Unterdeckung ist EINE Regel für alles (Juli 2026)** – tiefe Prüfung der Auftrags-/
  Unter-Auftrags-/Abweichungs-Logik über ~30 betriebliche Situationen gegen echtes
  PostgreSQL. Die Zustandsmaschine selbst hielt dicht; die **Wirkung** der Fehlmenge nicht.
  **Der Konstruktionsfehler:** die Fehlmenge blockierte eine hand-gepflegte Liste von fünf
  Schritttypen (`SUBJECT_STEP_TYPES`). Damit wirkte sie **zu hart oder gar nicht** – je
  nachdem, welche Schritte zufällig im Prozess standen: (a) hatte der Prozess einen
  Subjekt-Schritt, legte eine Abweichung an EINEM von fünf Teilen auch die **Prüfung der
  anderen vier** still (409 «Datenerfassung ist nicht an der Reihe») – exakt die Pause, die
  abgeschafft werden sollte, nur unter anderem Namen; (b) hatte er keinen (reine
  Beschaffung), schloss der Auftrag **still mit 3 von 4** ab, ohne Hinweis und ohne
  Entscheidung. Die Konsequenz hing an der Prozessform statt an der Sache.
  **Die eine Regel, zwei Hälften** – beide *deklariert*, keine Liste:
  1. **Blockieren tut sie nur, wer die Menge WEITERGIBT** – hinaus zum Kunden (`sale`) oder
     hinein ins Produkt (`resource`). Deklariert als `EventType.hands_over`. Erfassen,
     Aussondern und Bewegen laufen **immer** – sie arbeiten an dem, was da ist, und gerade
     wenn etwas fehlt, will man sie tun.
  2. **Fertig wird kein Auftrag, solange ihm etwas fehlt** (`recompute_completion`). Das ist
     der eigentliche Schutz gegen stilles Unterliefern – jetzt an EINER Stelle statt als
     Nebenwirkung eines blockierten Schritts. Der Mensch entscheidet über die drei Wege
     (Ersetzen · gezielt decken · ohne Ersatz weiter), dann ist der Auftrag durch. *Die
     guten Stück bleiben bis dahin `in_process` – richtig so: sie sind diesem Auftrag
     zugesagt und dürfen nicht per FIFO abwandern.*
  **Die Fehlmenge gehört dem AUFTRAG, nicht einem Schritt** (`OrderResponse.shortfall` +
  `waiting_for`, aus `OrderStepInfo` entfernt): sie ist «Soll − Gesichert» und dieselbe
  Zahl, egal welcher Schritt dran ist. Vorher hing sie an jedem Subjekt-Schritt – dieselbe
  Zahl mehrfach berechnet (samt FIFO-Abfrage **je Schritt**) und in einem Prozess ohne
  Subjekt-Schritt gar nicht sichtbar. `StepShortfall.kind` (subject|component) ersetzt die
  hand-gepflegte `SUBJECT_STEP_TYPES`-**Spiegelkonstante im Frontend**; die Notiz mit den
  drei Wegen steht jetzt **einmal** unter dem Fluss statt je Schritt.
  **Steckengeblieben ≠ unterwegs** (`process.is_stalled` + `supply.covering_sub_orders`):
  Ein Nachschub mit fehlgeschlagenem Schritt liefert nie mehr etwas. Er galt trotzdem als
  «läuft» – der Eltern zeigte für immer «wartet auf …», blendete darum die Deckungs-Wege
  aus, «Ersetzen» antwortete «der Bedarf ist bereits gedeckt» und ein zweiter Nachschub
  wurde als überflüssig verworfen: **kein Weg nach vorn**. Die Regel gab es bereits einmal
  (Auto-Nachbestellung) und fehlte an den zwei Stellen, an denen sie genauso zählt; jetzt
  liegt sie an EINER und alle drei lesen sie.
  **Der Verdacht hält das Teil ab der Meldung** (`create_deviation` reserviert sofort,
  `detach_sub_order` gibt frei): zwischen «Abweichung gemeldet» (Entwurf) und «Auflösung
  freigegeben» war das verdächtige Teil per FIFO für jeden anderen Auftrag greifbar.
  Dazu: bei Totalausschuss nennt «ohne Ersatz weiter» jetzt den echten Weg («Ersetzen» oder
  «Abbrechen») statt auf einen längst erledigten Abweichungsauftrag zu zeigen; drei
  Docstrings beschrieben noch die vor Migration `086` abgeschaffte «Abbruch ausstehend»-
  Semantik. Wächter: `test_a_shortfall_stops_handover_not_work`,
  `test_no_order_completes_while_something_is_missing`,
  `test_the_shortfall_belongs_to_the_order`,
  `test_a_reported_deviation_holds_its_instance_immediately`.

- **Testnotizen-Runde 23 (die Klammer ist die Instanz, Notizen #341–#351)**: Vier der zehn
  Notizen betrafen dieselbe Wurzel – **woran ein Auftrag und eine Abweichung einander
  erkennen**.
  (1) **«Es fehlt» stand an einem abgeschlossenen Auftrag** (#347, Regression aus der
  Unterdeckungs-Runde): die Fehlmenge wurde für JEDEN Auftrag gerechnet. Bei einem fertigen
  sind Reservierung und Subjekt-Bindung längst gelöst – «Soll − Gesichert» ergab die volle
  Menge als Phantom. Jetzt: **nur ein laufender Auftrag kann etwas schulden**
  (`order.status != "released"` → keine Fehlmenge). Ein Entwurf hat noch nichts zugesagt,
  ein abgeschlossener hat abgerechnet.
  (2) **Die Klammer zwischen Auftrag und Abweichung ist die INSTANZ, nicht der
  Eltern-Zeiger** (#348/#350). Ein Auftrag referenziert Instanzen; eine Abweichung tut
  dasselbe. Das Instanz-Detail meldet eine Abweichung am **Herkunfts**-Auftrag – ein
  anderer Auftrag, der auf dasselbe Stück zählt, lief darum ungerührt weiter und zeigte die
  Abweichung nie. `deviated_instance_ids` fragt jetzt «steckt eines MEINER Stücke in einer
  offenen Abweichung?» (über `order_instances`, ohne `parent_order_id`), und
  `deviation.deviations_touching` bringt jede Abweichung an einer eigenen Instanz in den
  Prozess – über die **dauerhafte** Verarbeitungs-Historie (`instance_order_links`), damit
  auch eine **geklärte** dokumentiert bleibt. *Fallstrick, getestet: eine Abweichung darf
  sich dabei nie selbst zählen – sonst gäbe sie beim Abschluss nichts frei (ihre eigene
  Statusänderung ist zum Abfragezeitpunkt noch nicht geflusht).*
  (3) **Am Auftrag gibt es nur den Abbruch** (#351): die Option «Läuft weiter» war lediglich
  eine Vorauswahl «alle Instanzen» – und WO ein Fehler auftritt, sagt man an der **Instanz**.
  Ein Weg weniger, dieselbe Fähigkeit; Server (`routers/orders.open_deviation`) und Dialog
  sagen dasselbe.
  (4) **Gebietskarte flächig, Zuweisung am Ort** (#342/#343/#344): die Karte füllt den
  Container, jede Fläche trägt **Gebiet + fakturierende Gesellschaft** als Beschriftung
  (`WorldMap.label`, Schwerpunkt über `regionAnchor` als Median – bei Europa bis Ostrussland
  zöge der Mittelwert ins Meer), und ein Klick öffnet die Zuweisung als Kärtchen **über der
  Fläche**. Die Liste unter der Karte sagte dasselbe ein zweites Mal und ist entfallen,
  ebenso die eigene Ausnahmen-Sektion – die Ausnahmen eines Gebiets stehen im selben
  Kärtchen (samt «+ Land»), und steht keine da, steht auch nichts da. Ist eine Gesellschaft
  geöffnet, treten die Gebiete der anderen zurück (`highlight`).
  (5) **Steuerliche Kennungen je Land** (#346, `TAX_IDS_BY_ISO2` neben `LEGAL_FORMS_BY_ISO2`):
  gefragt wird, was es dort gibt. Der Gewinn ist das **Weglassen** – die USA kennen keine
  Mehrwertsteuer, dort erscheint die «MWST-Nummer» gar nicht (statt als leeres Pflichtfeld).
  Dieselbe Bauart und derselbe Grund wie bei den Rechtsformen: eine Abfrage-API dafür gibt
  es nicht (VIES *prüft* bestehende USt-IdNrn, es sagt nicht, welche Kennungen ein Land
  kennt), und die Angaben sind träge. (6) IBAN-Hinweis entfällt (#345 – der maskierte Wert
  steht bereits als Platzhalter).
  *#341 (jede Instanz einzeln statt «2 Stk.») ist bewusst NICHT umgesetzt: eine Instanz ist
  eine **Menge**, kein Ding – eine Charge darf gebrochen sein (2.5 kg), die Objektnummer ist
  systemweit eindeutig (QR/Referenzen/Standort-Kette), und N Zeilen mit derselben Nummer
  bräuchten überall eine neue Antwort auf «welche davon?». Ausführlich am Modell
  (`models/instance.py`) und in `tests/test_quantity_rules.py`.*

- **Ein Auftrag und ein Abweichungsauftrag sind DASSELBE – der Unterschied ist ein Tag**
  (Juli 2026): Es gibt EINEN Weg, einen Auftrag anzulegen, EINE Tabelle, EIN Schema, EINEN
  Freigabe-Pfad. Der frühere Sonder-Endpunkt `POST /orders/{id}/deviation` bleibt als
  **Abkürzung**, ist aber kein zweiter Weg mehr – er teilt sich jede Regel mit der normalen
  Instanz-Auswahl.
  **Das Tag wird ABGELEITET, nicht angeklickt** (`subject.classify_pick`) – exakt so, wie
  die Retoure sich seit jeher ableitet: *die Auswahl bestimmt die Art des Auftrags.*
      alle frei am Lager           → gewöhnlicher Auftrag (kein Tag)
      alle verkauft                → Retoure      (Geld zurück, Original = Eltern)
      mindestens eine **gebunden** → Abweichung   (in Arbeit · reserviert · gesperrt)
  «Gebunden» heisst: die Instanz existiert, ist aber nicht frei verfügbar. Auf so etwas
  zuzugreifen KANN nur eine Abweichung sein – darum ist das Tag die **Folge** der Auswahl,
  nicht ihre Voraussetzung. `_validate_pins` kennt kein Vorab-Flag mehr und lässt **jede
  aktive Instanz** zu (nur Verschrottetes ist raus); der Picker zeigt gebundene Stück mit
  einem gelben Punkt und erklärt sie im Hover.
  **Der Eltern-Auftrag wird ebenfalls abgeleitet** (`subject.holding_order`): es ist der
  laufende Auftrag, der das Stück gerade in der Hand hat. Läuft keiner mehr (späte
  Reklamation an fertiger Ware), steht die Abweichung allein – das ist erlaubt.
  **Und die Unterdeckung wird SOFORT entschieden.** Nimmt die Auswahl einem laufenden
  Auftrag sein Stück weg, entsteht dort im selben Moment eine Fehlmenge; sie stillschweigend
  offen zu lassen hiesse, den Eltern ohne Entscheidung hängen zu lassen. Darum antwortet der
  Server mit **409 und nennt die betroffenen Aufträge**, bis eine der drei bekannten
  Antworten mitkommt (`OrderUpdate.shortfall_response` bzw. `OrderDeviationCreate`):
  **warten** (Fehlmenge bleibt offen – der Eltern wird nicht fertig) · **ersetzen**
  (`recovery.cover_shortfall`) · **ohne Ersatz weiter** (`recovery.confirm_quantity`).
  Die «Pause» des Eltern dauert damit genau so lange wie die Eingabe – es braucht keinen
  eigenen Pause-Mechanismus. Beide menschlichen Einstiege (Auswahl im Auftrag,
  Abkürzungs-Knopf an der Instanz) teilen sich `_assert_answered`/`_apply_shortfall_answer`;
  **systemseitig** angelegte Abweichungen (Auto-Abweichung nach Datenerfassung,
  Artikel-Deaktivierung) gehen direkt über den Service und lassen die Fehlmenge offen –
  dort entscheidet später ein Mensch am Auftrag.
  **Der eine verbleibende Unterschied ist keiner der Abweichung, sondern des Subjekts:** ein
  Auftrag auf **fixierte** Instanzen (Abweichung, Retoure, Bereitstellung) fährt NICHT den
  Artikel-Prozess (`order_step_defs`) – der beschreibt, wie etwas ENTSTEHT, und die Teile
  gibt es schon. Er braucht seinen eigenen Ablauf; alles andere (Modell, Felder, Status-Fluss,
  Freigabe, Prozessschritt-Module, Unter-Aufträge) ist identisch.
  Wächter: `test_an_order_and_a_deviation_order_are_the_same_thing`,
  `test_taking_a_busy_instance_forces_the_shortfall_decision`.

- **Testnotizen-Runde 24 (die EINE Pause-Regel, Notizen #352–#359)**: Der rote Faden ist,
  dass ein Auftrag genau EINEN Grund kennt, stillzustehen – und dass dieser Grund eine
  **Entscheidung** ist, kein Nebeneffekt.
  (1) **Ein Auftrag mit offener Fehlmenge ruht – ganz** (#354, `process.is_paused`). Die
  Zwischenstufe «eine Fehlmenge hält nur auf, wer die Menge weitergibt» (Registry-Flag
  `EventType.hands_over`, nur Verkauf und Ressource) ist zurückgenommen: solange eine
  Abweichung offen ist, darf der Eltern-Prozess nicht weiterlaufen. Der Grund ist nicht
  Vorsicht, sondern Reihenfolge – wer weiterarbeitet, während noch offen ist, ob ein Stück
  ausgesteuert wird, arbeitet womöglich am falschen Bestand. **Trotzdem gibt es dafür
  keinen eigenen Mechanismus:** die Abweichung nimmt ihr Stück heraus
  (`deviated_instance_ids`), daraus wird eine Unterdeckung, und eine Unterdeckung hält den
  Auftrag an. Ausschuss und weggenommene Reservierung erzeugen denselben Zustand über
  denselben Weg – es gibt kein «pausiert wegen Abweichung» neben «es fehlt etwas».
  Das ist unter dem Strich **eine Regel weniger**: `hands_over` und `SUBJECT_STEP_TYPES`
  sind beide entfallen, und `step_shortfalls` fragt für JEDEN Schritttyp dasselbe –
  die Fehlmenge des **Auftrags** plus den **eigenen** Material-Bedarf des Schritts
  (`_component_shortfall`, nur die Ressource hat einen). Die Pause ist heute kein stiller
  Nebeneffekt mehr, sondern die gewählte Antwort «Auftrag pausieren»; wer nicht warten
  will, ersetzt oder reduziert und läuft im selben Moment weiter. Neu ist auch, dass ein
  abgewiesener Schritt den **echten** Grund nennt (`process._not_now`): «Der Prozess ruht …
  bitte zuerst entscheiden» statt «ist (noch) nicht an der Reihe».
  (2) **Eine Frage, ein Fenster** (#352, `components/erp/shortfall-dialog.tsx`): Die drei
  Antworten heissen jetzt, wie sie sich auswirken – **Auftrag pausieren · Instanz ersetzen ·
  Auftragsmenge reduzieren** – und stehen in EINER kleinen Lightbox, die von beiden
  Einstiegen benutzt wird (Auswahl gebundener Instanzen im Auftrag/an der Instanz sowie die
  Unterdeckung am laufenden Auftrag). «Ersetzen» führt dort eine Ebene tiefer auf die
  gewohnten zwei Wege der Herkunft (älteste zuerst ↔ bestimmte Instanzen) – keine zweite
  Entscheidung, nur die Ausführung der ersten. Die drei früheren Eigenbau-Leisten
  (`ProcessHoldNotice`, `PositionRow`, `instance-detail`) sind darin aufgegangen.
  (3) **Unter-Aufträge stehen ZWISCHEN den Modulen** (#353, `SubOrderCard`): Abweichung,
  Nachschub und Bereitstellung sind dasselbe Muster – ein eigener Auftrag, hervorgegangen
  aus einem Schritt (`origin_step_id`) – und sehen darum gleich aus: ein eingerückter
  Knoten an seiner Stelle im Fluss. Vorher waren es drei Darstellungen (Bereitstellung als
  vollwertige Karte, Abweichung als Pille **seitlich** neben der Karte via `.erp-devbranch`,
  Abweichung ohne Ursprungsschritt als Abzweig davor). Eine Pille am Rand liest sich als
  Randnotiz – dabei ist eine offene Abweichung der Grund, warum alles ruht. Genau dort
  steht jetzt auch das «Es fehlt …» (#354): bei dem Unter-Auftrag, der die Menge bindet,
  statt zusätzlich als Kasten unter dem Fluss. Und: **ein blockierter Schritt zeigt sein
  Panel weiterhin** – was darin schon erledigt wurde (eine eingeholte Offerte, erfasste
  Werte), darf nicht verschwinden, nur weil der Prozess ruht.
  (4) **Der Bedarf eines ENTWURFS ist bearbeitbar – bei jedem Auftrag** (#355): Der
  Abkürzungs-Knopf an der Instanz nimmt einem die erste Auswahl ab, er soll sie nicht
  festnageln; weitere Instanzen oder Positionen ergänzt man wie überall. Dazu **kein
  Mischmasch**: freie und gebundene Stücke gehören nicht in denselben Auftrag (der freie
  Teil wäre ein gewöhnlicher Bedarf, der gebundene nimmt einem laufenden Auftrag etwas
  weg) – dieselbe Regel und dieselbe Form wie beim Verkauft/Lager-Mix. Beide Seiten lesen
  dieselbe Definition (`subject.is_bound`, aus `classify_pick` herausgezogen): der Server
  weist ab, die Oberfläche sperrt die jeweils andere Sorte, sobald die erste gewählt ist.
  (5) **«Auswählen» braucht genug wählbaren Bestand** (#356): gemessen am GANZEN Pool
  (frei + gebunden), nicht nur am freien – sonst wäre die Option eine Sackgasse, deren
  Auswahl sich nie vervollständigen liesse. Gesperrt mit dem Grund im Hover.
  (6) **Weltkarte** (#357): der Ausschnitt ist die **Bounding-Box der Landzellen** statt des
  vollen 72×25-Rasters (links standen drei reine Wasser-Spalten) – abgeleitet, damit er bei
  jeder Masken-Änderung stimmt; `regionAnchor` rechnet in denselben Koordinaten. Und die
  Beschriftung überlebt den Hover: unter dem Cursor wird die Fläche mit dem **kräftigen**
  Ton nachgezeichnet – genau der Ton, der auch die Schriftfarbe war –, also schreibt sie
  dort weiss. (7) Betriebskosten ohne Erklärabsatz (#358 – die Badge «gemessen · fix ·
  geschätzt» steht bereits an jeder Zeile); Status-Badge im gemeinsamen `DetailHeader` eine
  Spur grösser (#359, 11.5 px) – weil nur diese eine Stelle sie rendert, gilt das für jeden
  Datensatztyp gleich.
  Wächter: `test_a_shortfall_pauses_the_whole_order`,
  `test_the_pause_has_no_mechanism_of_its_own`,
  `test_a_deviation_pauses_the_order_through_the_shortfall_not_a_second_rule`,
  `test_the_subject_shortfall_is_type_agnostic`,
  `test_a_pick_never_mixes_free_and_bound_instances`,
  `test_a_refused_step_names_the_real_reason`.

Nächste Aufgabe: **KI aktivieren** – `VERTEX_PROJECT_ID` (+ `roles/aiplatform.user` für den Cloud-Run-
Service-Account) setzen und Assistent/Schreibhilfe/Bild-KI in der Sandbox durchtesten (ADR 004);
Publishable Key (`pk_test_…`) in Admin → Systemkonfiguration hinterlegen + die
eingebettete Kasse/Warenkorb inkl. Mehrpositionen-Verkauf (Fehlbestand + Nachschub, Zahlungsart) in der
Sandbox testen (`docs/stripe-setup.md`); Retoure/Erstattung als Normalauftrag (verkaufte Instanzen unter
«Instanz wählen» → Bewegung zurück + Gutschrift im `sale`-Modul inkl. Stripe-Refund; Kulanz ohne Rücknahme)
in der Sandbox end-to-end prüfen; Abo-Mindestlaufzeit/
Kündigungs-Cooldown + Produktabo-Auto-Fulfillment (`invoice.paid`) in der Praxis prüfen;
Custom-Auftrag-UX verfeinern; Instanz = vollständige Ereignis-Historie; Scan-Quittierung im Wareneingang &
beim Verschrotten; E-Mail (Gmail API); Stripe Terminal für Vor-Ort-Zahlung (payment_method='terminal',
Phase 2+, aktuell nur vorgemerkt).

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
