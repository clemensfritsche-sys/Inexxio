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
- Frontend: Profileinstellungen (Profil, Adresse, Rechnungsadresse, Sicherheit, Benachrichtigungen, Datenschutz)
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
  kanonisch (Spezifikation/Charge/Instanz/Lagerplatz). Responsive: Inline-Grids kollabieren
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
  target`/`fixed_location_*`/Beschaffungsquelle (vorher: Consent-Lücke + Freigabe-Gate-Bruch beim
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
  `quality` ∈ pending|passed|failed («ist es gut?») und `disposition` ∈ in_process|in_stock|consumed|
  sold|scrapped («wo ist es?»). Neue Instanzen starten `(pending, in_process)`; bei Auftrags-Abschluss
  → `(passed, in_stock)` («Freigegeben, ab Lager verbrauchbar») via `process.recompute_completion` →
  `release_instances` (`released_at` = FIFO-Basis). Datenerfassung gibt NICHT vorzeitig frei (nur
  Durchfaller → `quality=failed`). Verbaut → `disposition=consumed`, verkauft → `sold`, verschrottet →
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
    kommt aus der **Systemkonfiguration** (`company_settings.default_receiving_location_id`); den
    realen Wareneingangs-Ort setzt die **gesperrte Pflicht-Bewegung «Wareneingang»** nach der
    Beschaffung (`process_steps.sync_locked_movements`) – NICHT mehr die Bestellung selbst
    (`purchase_orders.receiving_location_id` ist Alt-Spalte, `apply_update` ignoriert das Feld).
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
    als Ganzes). Durchfaller → `instances.quality='failed'` (`services/inspection.py`).
  - **movement** = «**Bewegung**»: bringt Instanzen an ihren Standort. Jede Instanz hat **immer** einen
    Standort (`instances.location_type` ∈ lagerplatz|user|instance + `location_id` = Objektnummer des
    Ziels). Der Lagerist setzt je Instanz das Ziel (auch unterschiedliche Ziele pro Auftrag möglich);
    optionales Vorgabe-Ziel am Schritt – **ein** kombiniertes Auswahlfeld (Lagerplatz/Person/Instanz),
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
  (→[Reaktivieren]); gilt für Artikel/Auftrag/Lagerplatz (`lib/status-flow.ts`, `StatusFlow`)
- Frontend: Artikel-«Prozess»-Reiter (Schritttypen hinzufügen/sortieren), **Bestand**-Reiter zeigt die
  Instanzen. Auftrag heisst starr «Auftrag», nur **freigegebene** Artikel referenzierbar, Menge mit
  Artikel-Einheit, Wunsch-Liefertermin optional (Default «Schnellstmöglich»), Bedarf nach Freigabe
  read-only. Auftrag-Detail: Sektion **Instanzen** (bei Freigabe erzeugt, mit Standort/QC) +
  **Auftrag-Stepper** über alle Schritte (Schlüssel = Schritt-id, mehrere gleichartige möglich) + Panel
  des gewählten Schritts (Beschaffung/Datenerfassung/Bewegung/Ressource); Lieferant sieht nur die
  Beschaffung seiner Aufträge.
- **Standorte**: eine Instanz **kann** einen Standort haben – **standortlos ist erlaubt** (kein
  erzwungener Firmen-Default mehr; `serialization._initial_location` gibt `NULL` zurück, ausser die
  Lieferanten-Beschaffung ist der erste Schritt → Start beim **Lieferanten**). Den realen Ort setzt der
  erste Bewegungs-Schritt. `LOCATION_TYPES` = lagerplatz/user/instance (Anzeige via
  `locations.location_labels`, NULL toleriert). Mengeneinheiten: Stk/mm/m²/**m³**/kg/l (Mengen sind aktuell
  ganzzahlig – Bruchmengen für kg/m²/l/m³ wären ein separater Decimal-Umbau der Bestands-Engine).
  Den **Wareneingangs-Ort** setzt die gesperrte Pflicht-Bewegung «Wareneingang» nach der Beschaffung
  (nicht mehr die Bestellung; `purchase_orders.receiving_location_id` ist Alt-Spalte); fehlt eine
  Vorgabe, wird automatisch ein Lagerplatz «Wareneingang» angelegt
  (`services/locations.py: resolve_receiving_location`). Der **Bewegungs**-Schritt
  verteilt von dort weiter. Lagerplätze werden überall über die **Objektnummer** angesprochen (kein Name);
  freigegebene Lagerplätze zeigen die Karte read-only; optionale **Bemerkung** (`note`) je Lagerplatz; Reiter
  **Verwendung** listet lagernde Instanzen + referenzierende Artikel (`/storage-locations/{id}/references`).
  Standard-Lieferadresse: Admin → Systemkonfiguration → «Lieferadresse / Wareneingang».
- **Adressen: EINE Darstellung** (`services/address.py`): Person, Unternehmen und Lagerplatz
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
- **Standort-Kette «wo genau?»** (`locations.location_chain`, `InstanceResponse.location_path`):
  liefert den vollen Pfad von innen nach aussen – Instanz → Behälter → Lagerplatz → **Anschrift**
  (`location_type='address'`, ohne Objektnummer). Zyklensicher, auf 10 Stationen begrenzt, und
  bewusst **nur im Instanz-Detail** gefüllt (ein Datensatz, ≤10 Auflösungen) – Feeds bleiben bei
  den Batch-Labels. Frontend: `components/erp/location-path.tsx` rendert sie als eingerückte
  Kette im bestehenden Karten-Design (Stationen klickbar, die Anschrift nicht – sie ist kein
  Datensatz); erscheint erst ab echter Verschachtelung, sonst genügt die Standort-Kachel.
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
  die Python-Entsprechung zu ESLint, die im Backend gefehlt hat.
- **Verbauen setzt den Standort über die EINE Schreibstelle** (`resource._relocate` →
  `location_split.set_single`): eine Komponente wandert beim Einbau auf die Produkt-Instanz
  (und damit über die Kette physisch mit ihr mit). Vorher wurde `location_type`/`location_id`
  direkt zugewiesen – eine zuvor auf mehrere Standorte **verteilte Charge behielt dabei ihre
  veraltete `locations`-Map** und galt gleichzeitig als verbaut UND anteilig woanders liegend.
- **Generischer Rückverweis «wer zeigt auf mich» je Objektnummer** (`services/references.object_references`,
  `GET /erp/objects/{id}/references`): was aktuell an einer Objektnummer **verortet** ist (`instances.
  location_id == id`, ohne Typ-Filter – Objektnummern sind global eindeutig) + referenzierende
  Prozessschritte. Reiter **«Verwendung»** generisch an Benutzer/Instanz/Lagerplatz (Frontend
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
  (CAD-Link), `surface` (Oberfläche), `min_order_qty` (MOQ), `safety_stock` (Sicherheitsbestand) sowie
  **Fixierter Standort** (`fixed_location_*`, Migration 069): GPS-Koordinaten + reverse-geocodierte
  Adresse – **exakt die Standort-Definition des Lagerplatz-Datensatzes** (`MapPicker` + Adressblock,
  `google_maps_api_key`). Rein deskriptiv am Artikel; friert wie die übrige Spezifikation bei der
  Freigabe ein. Im Spezifikation-Reiter über «+ Feld hinzufügen» einblendbar; nur befüllte Felder werden
  gespeichert/angezeigt.
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
    ein realer **Halter** (Lagerplatz/Person/Instanz), den Ausschuss nicht mehr hat; der Endzustand
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
  Bewegungs-Schritt (`location_split.move`). Wareneingang/Versand/Kunde laufen wie gehabt über die
  gesperrten Pflicht-Bewegungen (`services/process_steps.py`), Verbrauch/Betriebsmittel über den
  Ressourcen-Schritt (Komponente → Produkt-Instanz via `_relocate`; Werkzeug → Arbeitsplatz via `_use_tool`,
  jetzt über denselben Reconciler, no-op wenn schon da). **Verschrotten** hat KEINEN Bereitstellungsort
  (`PROV_NOWHERE`): die Instanz wird standortlos (`location_split.clear`), kein Schrottplatz-Reconcile mehr.
  Automatik ist **standardmässig an** (der physische Vollzug bleibt beim Bewegungs-Schritt scan-quittiert;
  no-ops laufen still durch). *Rückführung/WIP-Puffer/Werkzeug-Rückgabe/mehrstufige Montage sind über
  denselben Bewegungs-Schritt + die Primitive abbildbar; scan-Quittierung im Verschrotten bleibt Backlog.*
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
  spiegelt nur noch den Modus (freight ⟺ 'freight'). Der Artikel-Prozess wird nie mutiert (die Alt-Spalte
  `article_process_steps.transport_mode` bleibt, wird zur Laufzeit ignoriert); digitale Payloads = KEIN Fall.
  **Versand-Beleg `shipments`** (Fachzeile je Bewegungs-Schritt, KEINE eigene Nummer): Adress-Snapshots
  (Firma ↔ Ziel-Person/-Lagerplatz, Länder → ISO-2), **Paket-Schätzung aus Artikel-Daten** (Gewicht×Menge,
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
  automatisch. Verdrahtet in Profil-Adresse/Rechnungsadresse, Unternehmens-Stammdaten und als Suchfeld im
  `MapPicker` (Lagerplatz/Artikel-Fixstandort). **Bugfix:** eine **verschrottete** Instanz zählt NIE mehr als
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
  Configs; `StatusBadge` rendert sie als Pille – Feed & Detail-Köpfe). Semantik: Amber = offen/Entwurf,
  Blau = aktiv/Aktion, Grün = erledigt/ok, Rot = Fehler/gesperrt, Slate = inaktiv. Der Prozess-Stepper
  zeigt **Schritt-Symbole** statt Zahlen. Aktive Prozessschritte haben **eine** grosse, touch-taugliche
  Hauptaktion (`PrimaryButton`, ≥44 px, volle Breite) – «Was muss ich jetzt tun?» auf einen Blick.
  **Gemeinsames UI-Vokabular (`components/erp/fields.tsx`) – konsequent verwenden statt Eigenbau:**
  `Tooltip`/`InfoHint` (Erklärungen/Infotexte gehören in den **Hover**, ⓘ-Symbol – nicht in die
  Fläche), `SectionTitle` (Symbol + Versalien-Label + optional ⓘ + rechter Slot), `PanelHeader`
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
  Etikettendruck via `ObjectLabel` (`qrcode.react`) an Instanz & Lagerplatz; Feed-Button «Scannen»
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
  Umsetzung). Der automatische Pflicht-Versand (`_Owner.sync`/`sync_locked_movements`) funktioniert daher
  unverändert – EIN Sale-Schritt ⇒ EIN Versand, kein Vervielfachungsrisiko.
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
      make-to-order zieht beim Abschluss nach. Die **gesperrten Pflicht-Bewegungen** (u. a. der Versand zum
      Kunden) sind von der Subjekt-Fehlmengen-Prüfung **ausgenommen** (`step_shortfalls`, `not step.locked`),
      sonst würde der Versand blockiert, sobald die Ware «verkauft» (aus dem freien Bestand «weg») ist.
    - **Rückgabe-Bewegung durch → «freigegeben»**: `process.return_subjects_to_stock` (sold→in_stock, Menge
      auf ≥1) wird bei der **Bewegung** an einen Lagerplatz aufgerufen (`movement.record_movement`), nicht
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
- **Pflicht-Versand zum Kunden geht IMMER an den Kunden** (Fix): die auf einen `sale`-Schritt folgende
  Pflicht-Bewegung (`mode='customer'`) hat als Ziel **fix den Kunden des Verkaufs** (`sale.customer_for_order`).
  Serverseitig erzwungen (`movement.record_movement` überschreibt die Ziel-Eingaben) UND im Embed als festes
  Ziel gezeigt (`orders._movement_embed`) – der Lagerist kann kein falsches Ziel wählen. Weil das Ziel fest
  ist, lädt das Movement-Panel **keine** Lagerplatz-/Personen-/Instanz-Listen mehr (`movement-panel.tsx:
  hasFixedTarget` → spürbar schneller, gerade direkt nach dem Verkauf).
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
  in ALLE Detailansichten (Artikel/Auftrag/Instanz/Benutzer/Lagerplatz/Unternehmen). **RAG (semantische
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
> einen Lagerplatz → in_stock; Kulanz (nicht bewegt) → bleibt sold. **Bedarf→Nachschub (ADR 003):** ein ungedeckter Bedarf
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
- **Meldebestand + Auto-Nachbestellung (E, «Nicht die Zeit soll bestellen, sondern der Bestand»)**:
  **Meldebestand** = `articles.safety_stock`; fällt der **freie** Bestand darunter, legt
  `services/replenishment.check_article` einen eigenständigen Nachschub-Auftrag (`orders.reason=
  'replenishment'`, ohne Eltern) an und gibt ihn frei – füllt bis `articles.reorder_target` (bzw.
  Meldebestand) auf (MOQ-gerundet), fährt den Artikel-Prozess (produzieren/beschaffen). Reuse von
  `orders.release_order` (wie ADR-003-Nachschub, nur ohne Pegging), idempotent (ein offener Nachschub je
  Artikel). **Auslöser** reaktiv (nach Bestandsabgang – `scrap.record_scrap` ruft `check_article`) +
  periodisch über `POST /api/v1/erp/maintenance/sweep` (`replenishment.evaluate_all`, Personal-Knopf
  «Lagerwartung», künftig Cloud Scheduler). Logistik-Felder (safety_stock/reorder_target) sind **auch am
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
  (`registry.PROMPT_VERSION`) präzisiert. (2) **Status-Töne vereinheitlicht** über `lib/status-flow.TONE`
  (pending=amber/warning, info=slate/accent, done=grün/success, danger=rot, inactive=grau): **Auftrag «In
  Bearbeitung» ist jetzt amber** – exakt der Ton der Instanz «Im Prozess»; Artikel/Prozess/Lagerplatz/
  Beschaffung/Verkauf ziehen dieselbe Palette (nur terminal Verbraucht/Verkauft behalten violett/petrol,
  kein Semantik-Token). (3) **Datenerfassung**: der Bug «Unterschrift konfiguriert, trotzdem Foto-Aufnahme
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
