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
- Neu generieren nach Backend-Schema-Änderung:
  ```bash
  cd backend && python -m scripts.dump_openapi   # → backend/openapi.json
  cd frontend && npm run generate:types          # → src/types/api.ts
  ```

## Kamera-Scan (`lib/scan.ts` + `components/scan/`)
Der QR trägt **nur die 9-stellige Objektnummer**; den Typ löst der Server auf
(`GET /erp/objects/{id}`). Drei Schichten, strikt getrennt:

| Schicht | Datei | weiss nichts von |
|---|---|---|
| Logik + **Deutung** | `lib/scan.ts` (`ScanReading`, `objectCodes`) | React, API |
| Kamera + Decoder | `components/scan/use-barcode-scanner.ts` | dem ERP |
| Dialog | `components/scan/scan-dialog.tsx` | Decoder, Objektnummern |

Aufruf über `useScan()` (eine Instanz am ERP-Layout, lazy). Ein Vorgang ist eine
**Sequenz**: `steps: [{label, expected?, candidates?, restrict?, exists?}]`.
`expected` = Verifikation · `restrict`+`candidates` = eingeschränkte Wahl · sonst freier
Lookup – dann **`exists` mitgeben**, sonst gilt jede 9-stellige Zahl.

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
