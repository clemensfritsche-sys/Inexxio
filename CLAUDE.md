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
    kommt aus der **Systemkonfiguration** (`company_settings.default_receiving_location_id`); beim
    **Wareneingang («received») ist der aktuelle Lagerort Pflichteingabe** des Bestellers
    (`receiving_location_id`) – dorthin wechseln die Instanzen (`services/purchase.py`).
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
- **Standorte**: jede Instanz hat immer einen Standort. Neue Instanzen starten bei der Freigabe beim
  **Lieferanten** (Beschaffung mit Lieferant) bzw. an der **Lieferadresse** aus der Systemkonfiguration.
  Beim **Wareneingang («received»)** gibt der Besteller den **aktuellen Lagerort verpflichtend** an
  (`purchase_orders.receiving_location_id`); fehlt eine Vorgabe, wird automatisch ein Lagerplatz
  «Wareneingang» angelegt (`services/locations.py: resolve_receiving_location`). Der **Bewegungs**-Schritt
  verteilt von dort weiter. Lagerplätze werden überall über die **Objektnummer** angesprochen (kein Name);
  freigegebene Lagerplätze zeigen die Karte read-only; optionale **Bemerkung** (`note`) je Lagerplatz; Reiter
  **Verwendung** listet lagernde Instanzen + referenzierende Artikel (`/storage-locations/{id}/references`).
  Standard-Lieferadresse: Admin → Systemkonfiguration → «Lieferadresse / Wareneingang».
- **Artikelnamen**: beim Anlegen aus einem Katalog gewählt (kein Freitext); Pflege via Admin →
  Einstellungen → «Artikelnamen» (`company_settings.article_names`, auch über `settings/public`).
- **Optionale Artikel-Stammdaten** (dynamische Feldliste, nur bei Bedarf): `material`, `cad_url`
  (CAD-Link), `surface` (Oberfläche), `min_order_qty` (MOQ), `safety_stock` (Sicherheitsbestand). Im
  Stammdaten-Reiter über «+ Feld hinzufügen» einblendbar; nur befüllte Felder werden gespeichert/angezeigt.
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
  - **Aussteuerung eines reservierten Subjekts → Eltern reagiert + drei Deckungs-Wege** (`services/
    recovery.py`): Steuert eine Abweichung eine Instanz aus, die ein **anderer** Auftrag bereits reserviert
    hatte (z. B. ein für einen Verkauf reserviertes Teil), muss dessen Fehlmenge **ehrlich** wieder
    sichtbar werden. **Core-Fix:** `scrap.record_scrap` löst beim Verschrotten **ALLE** Reservierungen der
    Instanz (`reservation.release_all`), nicht nur die des eigenen (Abweichungs-)Auftrags – ein
    verschrottetes Teil verlässt den Bestand endgültig und kann keinen Auftrag mehr beliefern. Dadurch
    meldet `_subject_shortfalls` des Eltern-Auftrags nach Schliessung der Abweichung wieder eine Fehlmenge,
    sein **Subjekt-Schritt (Bewegung/Versand/Kontrolle) wird «blockiert»** – abgeleitet aus dem Bestand,
    kein stilles Unterliefern mehr (vorher blieb die tote Eltern-Reservierung stehen → Schritt lief
    scheinbar weiter, es wurde 1 Stück zu wenig geliefert). Der blockierte Schritt bietet Personal (am
    freigegebenen Auftrag) **vier Wege**, konsistent mit dem bestehenden Backorder-Verhalten und der
    „Mensch entscheidet"-Philosophie: (1) **Nachschub anlegen** (produzieren/beschaffen, `POST /supply`,
    bestehend); (2) **Aus Lager decken** – freien Bestand FIFO reservieren (`POST /cover-stock` ohne ids,
    `recovery.cover_from_stock`); (3) **Andere Instanz wählen** – gezielt eine freie, freigegebene Instanz
    reservieren (`POST /cover-stock` mit ids, inline-Picker); (4) **Menge reduzieren** – die Anforderung
    auf das Vorhandene senken (`POST /reduce`, `recovery.reduce_to_available`; Einzel-Artikel: `order.
    quantity`, Mehrpositionen: je Position, letzte darf nicht auf 0 fallen → dann «Abbrechen»). Diese Wege
    bilden genau die Fälle je Subjektwahl ab: ein **FIFO**-Auftrag nutzt anderen Lagerbestand; ein gezielt
    auf Instanzen fixierter Auftrag wählt eine **Ersatz-Instanz** oder reduziert; wo nichts am Lager liegt,
    **produziert** der Nachschub. `StepShortfall` trägt dafür die **Verfügbarkeit** (`available_quantity`/
    `available_instances`) aus freiem Lagerbestand; `BlockedStepNotice` empfiehlt „Aus Lager decken", wenn
    Bestand frei ist, sonst „Nachschub anlegen". Nur bei **Subjekt-Schritten** (movement/inspection/scrap/
    sale) – ein reiner Komponenten-Bedarf (Ressource) wird weiterhin ausschliesslich über Nachschub
    gedeckt.
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
  (Provider/Zonen) + öffentlicher Shop (`/shop`, `/shop/product`, `/shop/success`, `/shop/pay` für manual).
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
    (wiederkehrende Lieferung; Folge-Fulfillment je Zyklus via `invoice.paid`-Hook = dokumentierte
    Erweiterung). Beide ohne Enddatum, aktiv kündbar (Customer Portal).
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

> **HINWEIS (aktuelles Kernmodell):** **Auftrag → Prozess → Instanz.** Der **Artikel** trägt seine
> **Spezifikation** (vormals «Stammdaten») + **einen** Prozess (Schritte inline, kein Prozess-Objekt, keine
> Objektnummer, keine n:m-Verknüpfung). **Freigabe auf Artikel-Ebene** friert Spezifikation + Prozess.
> Ein **Auftrag** ist der Trigger in zwei **Modi**: **make** (Artikel + Menge → fährt den Artikel-Prozess,
> ERZEUGT Instanzen) oder **custom** (ausgewählte vorhandene Instanzen + individueller Prozess am Auftrag).
> **Instanzschritte verarbeiten nur Instanzen**; Artikel dienen v. a. als FIFO-Bezug. Schritttypen: purchase,
> inspection, movement, **resource** (Verbrauch + Betriebsmittel, Modus je Zeile), **scrap** (Verschrotten),
> sale. `quality`+`disposition` als zwei Instanz-Achsen; `event_types`-Registry deklariert die Bestands-
> Polarität. **Unter-Auftrag** (`parent_order_id` + `reason`) – EIN Mechanismus, zwei Gründe:
> **Abweichung** (`reason='deviation'`: Abbruch-Folgeauftrag / Fehler / Reklamation / Nacharbeit,
> pausiert den Eltern; `Claim`-Typ entfernt) und **Nachschub** (`reason='supply'`: deckt einen nicht
> vorrätigen Bedarf, blockiert nur den Schritt). **Bedarf→Nachschub (ADR 003):** ein ungedeckter Bedarf
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

Nächste Aufgabe: Publishable Key (`pk_test_…`) in Admin → Systemkonfiguration hinterlegen + die
eingebettete Kasse/Warenkorb inkl. Mehrpositionen-Verkauf (Fehlbestand + Nachschub, Zahlungsart) in der
Sandbox testen (`docs/stripe-setup.md`); Abo-Mindestlaufzeit/Kündigungs-Cooldown in der Praxis prüfen;
Auto-Fulfillment je Produktabo-Zyklus (`invoice.paid`-Hook); Custom-Auftrag-UX verfeinern; Instanz =
vollständige Ereignis-Historie; Scan-Quittierung im Wareneingang & beim Verschrotten; E-Mail (Gmail API);
Stripe Terminal für Vor-Ort-Zahlung (payment_method='terminal', Phase 2+, aktuell nur vorgemerkt).

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
