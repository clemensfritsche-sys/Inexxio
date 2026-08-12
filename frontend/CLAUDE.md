# Frontend – Next.js 14 (TypeScript)

## Technologie
Next.js 14, TypeScript, Tailwind CSS, App Router, React Query (punktuell), react-hook-form + zod

## Starten
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # Production Build
```

## Struktur
```
src/app/
├── (public)/       ← Öffentliche Website (kein Auth)
│   ├── layout.tsx  ← Navbar + Footer
│   ├── page.tsx    ← Homepage
│   ├── ueber-uns/  ← Über uns
│   ├── kontakt/    ← Kontaktformular
│   ├── impressum/  ← Impressum (dynamisch aus API)
│   ├── agb/        ← AGB (B2B + B2C Tabs)
│   └── datenschutz/← Datenschutzerklärung
├── (auth)/
│   └── login/      ← Magic Link + Google Sign-In
└── (erp)/          ← Auth-geschützte ERP-Seiten
    └── erp/        ← Universal Feed (Master-Detail) – EINZIGE ERP-Oberfläche.
                    #   Benutzer, Artikel, Aufträge, Instanzen und Unternehmen werden
                    #   ausschliesslich hier gepflegt (Detailfenster je Datensatz).
                    #   Die früheren Admin-Seiten (`einstellungen`, `benutzer`) waren
                    #   nicht verlinkte Zweitoberflächen und sind aufgelöst.
```

## Design System (VERBINDLICH — Inexxio Design System)
> Alle UI baut auf dem **Inexxio Design System** auf. Regeln & Nutzung:
> **`../docs/design-system/README.md`**. Vor UI-Arbeit lesen.
- **Tokens (Single Source of Truth):** `src/styles/design-system/colors_and_type.css`
  (erstes CSS-Modul in `src/app/layout.tsx`). Werte nur dort definieren.
- **Tailwind-Utilities daraus:** `bg-bg-1/2/3`, `text-fg-1/2/3/4`, `text-accent`,
  `text-inexxio`, `border-border-1/2`, `rounded-ds-lg`, `shadow-ds-sm/md`,
  `font-display` (Inter Tight) / `font-body` (Inter). Zahlen `.ix-tnum`.
- **Farb-Semantik:** warme Neutraltöne = Fläche · **Rot (`inexxio`) = der eine laute
  Akzent** (CTA/aktiv/Fehler) · **Slate (`accent`) = Info/aktiv/Links** im ERP.
- **ERP:** Haarlinien + Weissraum statt Schatten; Status = Punkt+Wort; Lucide-Icons
  funktional/sparsam; Karten `rounded-ds-lg`, 8px-Grid, `max-w-7xl mx-auto`.
- **Deprecated (Altlast, nicht neu verwenden):** `slate-*`, `blue-600`, `brand-*`
  (blau). Beim Editieren einer Datei auf Tokens migrieren (`docs/design-system/README.md §4`).

## i18n
Aktuell **einsprachig Deutsch**. Das frühere next-intl-Konzept (inkl. `/messages/*.json`)
war nie verdrahtet und ist entfernt (Cleanup 2026-07); EN kommt später (KI-Übersetzung geplant).

## Auth Guard
ERP-Seiten prüfen Firebase Auth. Nicht eingeloggt → Redirect zu /login.

## API-Integration
- Client: src/lib/api.ts (fetch wrapper mit Bearer Token)
- Firebase: src/lib/firebase.ts (Magic Link, Google Sign-In)
- React Query für Serverdaten-Caching

## Typen (Single Source of Truth)
- `src/types/api.ts` wird aus dem Backend-OpenAPI-Schema generiert – NICHT editieren.
- `src/types/index.ts` leitet `UserProfile` daraus ab (nur `role` wird auf die Union verengt).
- **`src/lib/status-catalog.ts` ebenso** – aus `backend/app/domain/statuses.py`. Die
  Statusliste ist eine **Quelle, kein Spiegel**: ein neuer Status ist EINE Zeile im
  Backend, und Beschriftung/Ampelton/Achsen/Bestands-Zugehörigkeit kommen von selbst
  hier an. `lib/process-status.ts` liegt daneben und trägt nur das **Symbol** – eine
  Gestaltungsfrage, die aus dem Fachmodell nicht kommen kann.
- Neu generieren nach Backend-Schema-Änderung:
  ```bash
  cd backend && python -m scripts.dump_openapi   # → backend/openapi.json
  cd backend && python -m scripts.dump_statuses  # → frontend/src/lib/status-catalog.ts
  cd frontend && npm run generate:types          # → src/types/api.ts
  ```

## Bestand (`components/erp/stock-view.tsx`)
EIN Modul, zwei Umfänge – am **Artikel** (Zeilen = seine Instanzen) und an der **Instanz**
(Zeilen = ihre Einzelinstanzen). Der Unterschied ist der Umfang der Daten, nie die
Darstellung; eine zweite Fassung liefe beim ersten neuen Zustand auseinander.
Bestand ↔ Historie entscheidet **der Server** (`StockState.stock`) – die Ansicht führt
keine Liste und meldet einen Zustand ohne Zuordnung, statt ihn zu raten.
Karte + Kopf + Werteraster kommen aus `fields.tsx` (`SPEC`, `SpecHead`, `SpecSection`,
`ReadField`) – die Anatomie **jeder** Detail-Ansicht.

## Datenerfassung (`components/erp/capture-work.tsx`)
Eine Zeile **je Instanz**, denn ein Vorgang ist eine Instanz (PROCESS_CORE §4.4): das
Etikett klebt am physischen Ding, und eine Einzelinstanz zieht keine Objektnummer. Charge
= ein Scan, Einzelserialisierung = n Scans – **ohne** Abfrage nach der Serialisierung.

- **Ohne Bestätigung kein Formular – und genau EIN Weg dorthin.** Der Scan ist der
  Regelweg (`useScan` mit `expected` = der Objektnummer, kein eigener Dialog), die
  Tastatur die Alternative **im selben Dialog** (die Leiste im Bild). Ein zweiter Knopf
  «Von Hand bestätigen» daneben ist entfallen: er war ein zweiter Weg zum selben Ziel und
  bestätigte gar nichts. **Wie** bestätigt wurde, sagt der Dialog selbst
  (`onComplete(ids, via)` – `scan` ↔ `manual`, vorsichtig gerechnet: eine getippte oder
  gewählte Nummer macht den ganzen Vorgang `manual`). Die **Regel** ist die Ablehnung im
  Backend (`process.confirm_step`), nicht das ausgegraute Feld.
- **«Nicht bestanden» hält an.** Das Modul legt **nichts** an: es zeigt den Haltezustand
  und öffnet auf Klick einen ganz gewöhnlichen Auftragsentwurf mit vorgewählten Stücken
  (Nummern erst auf Klick: `api.stepHold`).
- **Die Stichprobe kommt vom Server** – die Zeile nennt die Ziehung («3 von 10 …»), die
  Definition den Satz (`ProcessStepResponse.sample`). Die Oberfläche formuliert ihn nicht
  selbst; `sampling.describe` ist die eine Quelle. Sie ist **EINE Zahl: der Anteil an der
  Gesamtmenge** (alle · Hälfte · Viertel · frei, `SAMPLE_PRESETS`) – die Kurzwege sind
  Werte derselben Zahl, keine eigenen Modi.

## Prozessschrittmodule im Entwurf (`lib/modules.ts`)
**Was ein Modultyp mitbringt, steht als Zuordnung, nicht als `if`-Kette**: `MODULE_FORM`
(Nutzlast + Vollständigkeit) und `MODULE_FIELDS` im Designer (der Feldsatz). Ein neuer
Typ ist je ein Eintrag; `test_frontend_mirrors` hält die Schlüssel mit `domain/modules.py`
deckungsgleich. Ein Modul-Entwurf entsteht an **einer** Stelle (`blankModule`).

- **Aussondern** hat zwei Angaben, beide Pflicht: Verschrotten ↔ Sperren
  (`DISPOSAL_MODES`, Liste im Backend) und der **Grund**. Keine Erfassungspunkte, keine
  Stichprobe: der Grund gehört zur Definition, nicht ans Band – dort lautete er bei jedem
  Stück gleich. Zur Laufzeit steht er als Auskunft da (`ProcessStepResponse.reason`).
- **Farbe und «Ausgang?» reisen mit dem Schritt** (`DiagramStep.tone`/`.terminal`, gefüllt
  aus `ModuleFacts`). Sie waren einmal ein Rückruf des Rahmens, gefüttert aus dem
  Modul-Katalog – und den lädt nur der Editor: im freigegebenen Auftrag kam nichts an, und
  ein stiller Rückfall gab jedem Modul die Farbe der Datenerfassung. `moduleTone` hat
  darum **keinen** Rückfall auf eine echte Modulfarbe mehr; Unbekanntes sieht kaputt aus.
- **Hinter einem terminalen Modul bietet der Editor nichts an** – dieselbe Eigenschaft,
  aus der die Freigabe ihren Fehler zieht und das Bild sein Ende (`chainProblems` meldet
  ein Modul, das durch Umsortieren dahinter geraten ist).
- **Das Verb auf dem Knopf kommt vom Server** (`ProcessStepResponse.action`):
  «Erfassen & bestätigen» · «Verschrotten» · «Sperren». Es hängt beim Aussondern an der
  Ausprägung – ein fester Text in der Oberfläche wäre eine zweite Aussage darüber.
- Die Laufzeit ist **dieselbe Komponente** (`CaptureWork`): Zeile je Instanz, Scan-Gate,
  dann das Formular – bei 0 Erfassungspunkten nur der Knopf.

## Kamera-Scan (`lib/scan.ts` + `components/scan/`)
Der QR trägt **nur die 9-stellige Objektnummer**; den Typ löst der Server auf
(`GET /erp/objects/{id}`). Drei Schichten, strikt getrennt:

| Schicht | Datei | weiss nichts von |
|---|---|---|
| Logik + **Deutung** | `lib/scan.ts` (`ScanReading`, `objectCodes`) | React, API |
| Kamera + Decoder | `components/scan/use-barcode-scanner.ts` | dem ERP |
| Dialog | `components/scan/scan-dialog.tsx` | Decoder, Objektnummern |

Aufruf über `useScan()` (eine Instanz am ERP-Layout, lazy). Ein Vorgang ist eine
**Sequenz**: `steps: [{label, expected?, candidates?, restrict?, exists?, suggest?}]`.
`expected` = Verifikation · `restrict`+`candidates` = eingeschränkte Wahl · sonst freier
Lookup – dann **`exists` mitgeben**, sonst gilt jede 9-stellige Zahl.

- **Vorschläge: der Scanner bietet an, was er ANNIMMT** (`offersFor`). Ein
  Verifikationsschritt braucht dafür keine Suche – seine Vorschlagsmenge *ist* `expected`,
  also genügt eine Teileingabe («00787»). Das war der strukturelle Bruch: die
  Vorschlagsquelle war eine Angabe **je Aufrufer**, der Feed brachte eine mit, ein
  Prozessschrittmodul nicht – dort blieb die Liste für immer leer, und nur die volle
  neunstellige Nummer ging durch. Wo die Menge das halbe ERP wäre (freier Lookup), gibt
  der Aufrufer weiterhin `suggest` mit – **seine eigene Suche**, nicht eine zweite (der
  Feed reicht `feedMatch` + `api.getInstances` herein).
  **Die Vorschlagsmenge ist die Gültigkeitsmenge**: ein `restrict`- oder `expected`-Schritt
  fragt `suggest` gar nicht erst.
- **Kein Zwischenschritt.** Enter bzw. ein Klick auf einen Vorschlag geht direkt durch;
  passt die Nummer nicht, steht der **Grund im Zielrahmen** (dort ist der Blick, und dort
  meldet die Farbe den Zustand). Der frühere «Übernehmen»-Knopf war ein zweiter Klick für
  eine getroffene Entscheidung – und ausgerechnet gesperrt, wenn die Eingabe nicht passte,
  also genau dann, wenn der Mensch den Grund gebraucht hätte.

- **Deutung tauschen** heisst `reading` mitgeben, nicht den Dialog anfassen.
- **ZXing nur als Rückfall** und nur `await import(…)` – der native `BarcodeDetector`
  kommt zuerst (5 kB statt 112 kB gzip beim Öffnen).
- **Der Stream gehört dem Hook.** Tracks im Cleanup explizit stoppen – ZXings `stop()`
  beendet nur die Decode-Schleife, sonst wächst der Video-Puffer über jeden Scan.
- Etikett drucken: `<LabelButton objectId title kind />` im `DetailHeader`.

## Wichtige Konventionen
- 'use client' nur wenn nötig (Interaktivität, Hooks)
- **`no-unused-vars` ist scharf** (`.eslintrc.json`, läuft in der CI): eine ungenutzte
  `useState`-Destrukturierung ist die Form, in der ein Knopf ohne Wirkung auftritt.
- Server Components für statische Seiten
- react-hook-form + zod für alle Formulare
- Lucide React für alle Icons
- TypeScript strict: kein 'any'

## Rechtliche Seiten
- Impressum: Daten dynamisch von /api/v1/admin/settings/public
- AGB: Vollständiger Schweizer Rechtstext (B2B + B2C)
- Datenschutz: Vollständig DSGVO + CH DSG konform
