---
name: inexxio-design-system
description: >-
  VERBINDLICH bei JEDER UI-/Design-Arbeit an Inexxio (Website, Shop, ERP) — vor dem
  Schreiben von JSX/TSX/CSS lesen. Nutze diese Skill immer wenn du Oberflächen,
  Komponenten, Seiten, Styles, Farben, Layout, Buttons, Badges, Karten, Icons oder
  Tailwind-Klassen erstellst oder änderst. Liefert die Design-Tokens (Single Source of
  Truth), Tailwind-Utilities, Farb-/Typo-/ERP-Regeln und den Migrationspfad weg von
  der alten slate/blue-Palette. Trigger: "design", "UI", "Komponente", "Seite",
  "styling", "Farbe", "Layout", "Tailwind", "Badge", "Button", "Karte", "Redesign".
---

# Inexxio Design System — Pflicht-Skill für UI-Arbeit

Alle Oberflächen von Inexxio bauen auf **einem** Design-System auf (Export aus Claude
Design, in den Code übernommen). **Bevor** du UI schreibst oder änderst:

1. **Lies `docs/design-system/README.md`** (Governance, Nutzung, Migration §4).
   Bei Marken-/Visual-Fragen zusätzlich `docs/design-system/brand-foundations.md`.
2. **Token-Quelle der Wahrheit:** `frontend/src/styles/design-system/colors_and_type.css`
   — geladen als erstes CSS-Modul in `frontend/src/app/layout.tsx`. Werte werden **nur
   dort** definiert. Niemals Farb-/Radien-/Schatten-Werte in `globals.css`,
   `tailwind.config.js` oder Komponenten hart kodieren.

## Nutzung (drei Wege, gleiche Wahrheit)
- **Tailwind-Utilities (bevorzugt):** `bg-bg-1/2/3/4`, `text-fg-1/2/3/4`,
  `text-accent` / `bg-accent-soft` / `text-accent-ink`, `text-inexxio` (Marke-Rot),
  `border-border-1/2`, `rounded-ds-xs/sm/md/lg/xl/ds-pill`, `shadow-ds-xs/sm/md/lg`,
  `shadow-ds-red` (nur Hover; Glow = none in v3), `font-display` / `font-body` /
  `font-mono`, semantisch `text-success/warning/info/danger` + `bg-*-bg`.
- **CSS-Variablen:** `var(--fg-2)`, `var(--bg-2)`, `var(--accent)`, `var(--r-lg)` …
- **`.ix-*`-Typo-Helper:** `.ix-h1/h2/h3`, `.ix-overline`, `.ix-index`, `.ix-tnum`
  (tabellarische Zahlen), `.ix-rule` / `.ix-rule-strong`.

## Kernregeln (nicht verhandelbar)
- **Farbe = Bedeutung.** Kühle, neutrale Grautöne (v4) tragen die Fläche – Website,
  Konto, ERP und E-Mail gleich. **Rot (`inexxio`) = der EINE laute Akzent** — CTA,
  aktiver Zustand, echter Fehler; nie dekorativ, nie flächig, **nie in Überschriften**. **Slate (`accent`) = die leise Stimme** für Info,
  aktive Zeilen/Nav, Links im dichten ERP. Slate konkurriert nie mit Rot.
- **ERP: Struktur vor Fläche** — Haarlinien (`border-border-1`) + Weissraum statt
  Kartenrahmen+Schatten. `shadow-ds-*` nur für echte Overlays (Modal/Menü).
- **Status: Punkt + Wort** wo möglich (6px Dot in Semantik-Farbe); gefüllte Badges
  sparsam. Symbol + Farbe + Label; Infotexte gehören in den **Hover** (ⓘ), nicht in
  die Fläche.
- **Icons: nur Lucide** (`lucide-react`), funktional & sparsam, neutral `fg-3`/`fg-2`;
  Rot nur aktiv/selektiert. **Keine Emoji**, kein Deko-Icon-Set.
- **Typo:** Headlines `font-display` (Inter Tight 700, Zwischentitel 600, kein 800+), Body
  `font-body` (Inter). **Zahlen immer tabellarisch** (`.ix-tnum`), wo sie ausrichten.
- **Schweiz:** CHF mit `'`-Trennung (`9'999 CHF`), `25 m²`, **ss** statt ß; Anrede **Sie**.
- **Wörter:** nie «Fixpreis», nie «Werkstatt» (→ «Standort», «Betrieb», «bei INEXXIO»).

## Website (v4) – vor jeder Website-Arbeit README §3a lesen
- **Überschrift:** eine Form – H2 Inter Tight 600, 48/32 px, darunter höchstens ein grauer
  Satz. Keine Kicker, keine roten Wörter, kein Mono.
- **Knöpfe:** Rot nur für die Anfrage; Abschnitts-Links hellgrau (`bg-3`); auf Bildkarten
  ein runder Glas-Pfeil; Radius 8 px.
- **Karten:** 16 px, Text direkt auf dem Bild mit Verlauf; **kein Kasten im Kasten**.
- **Glas:** `.ix-glass` / `.ix-glass-dark` (`--glass-*`) – Kopf, Menüs, Umschalter, Text auf
  Fotos, Felder über der Karte. Eine Ebene. **Nie im ERP.**
- **Vorlage:** `docs/design-system/reference/mockups/Startseite v4.dc.html` (+ mobil) –
  daran messen, nicht neu erfinden.

## Die Alt-Palette ist weg
`slate-*`, `blue-*`, `gray-*`, `#2563eb` und der `brand-*`-Vorrat sind aus dem Code
entfernt – **0 Vorkommen**, auch als Hex (einzige Ausnahme: die Gebietskarte). Wer sie
wieder einführt, führt eine zweite Farbsprache ein; die Zuordnung steht als Lesehilfe in
`docs/design-system/README.md §4`.

## Bestehendes UI-Vokabular wiederverwenden
Nicht neu erfinden:
- `frontend/src/components/erp/detail-frame.tsx` – Detail-Anatomie (`SPEC`, `SpecHead`,
  `SpecSection`, `ReadField`, `DetailBody`/`DETAIL_MAXW`, `Card`, `RecordIcon`,
  `DetailHeader`).
- `frontend/src/components/erp/controls.tsx` – `inputClass`/`inputCls` (die EINE Feldform),
  `Label`, `Segmented`, `IconSwitch`, `Dialog`, `Palette`, `FieldAction`.
- `search-select.tsx` (`SearchSelect`/`OptionRow`) · `hints.tsx` (`Tooltip`/`InfoHint`,
  `ErrorText`) · `fields.tsx` (`StatusDot` – der eine Status-Punkt –, `StatusBadge`, `Row`).
- `frontend/src/components/erp/module-ui.tsx` – die Bauteile eines Prozessschrittmoduls
  (`MODULE_CARD`, `ActionButton`/`Actions`, `LedgerRow`/`RowActions`,
  `Amount`, `ValueBar`, `ACT_H`, `FIELD_GAP`).
- `frontend/src/components/erp/object-select.tsx` – jedes Referenzfeld («welchen Datensatz
  meinst du?»), Kamera im Feld.
- `frontend/src/lib/when.ts` – die einzige Datums-Ausgabe.
Diese Bausteine nutzen, statt Eigenbau.

## Neuen Claude-Design-Export übernehmen
`colors_and_type.css` ersetzen → Referenz/Doku in `docs/design-system/` aktualisieren
→ `cd frontend && npm run build` (Build = Wächter). Tokens sind nach Namen stabil.
