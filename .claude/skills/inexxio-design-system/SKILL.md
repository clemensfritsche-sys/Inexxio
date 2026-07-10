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
  `shadow-ds-red` / `shadow-glow-*` (nur Hover/Press), `font-display` / `font-body` /
  `font-mono`, semantisch `text-success/warning/info/danger` + `bg-*-bg`.
- **CSS-Variablen:** `var(--fg-2)`, `var(--bg-2)`, `var(--accent)`, `var(--r-lg)` …
- **`.ix-*`-Typo-Helper:** `.ix-h1/h2/h3`, `.ix-overline`, `.ix-index`, `.ix-tnum`
  (tabellarische Zahlen), `.ix-rule` / `.ix-rule-strong`.

## Kernregeln (nicht verhandelbar)
- **Farbe = Bedeutung.** Warme Neutraltöne tragen die Fläche. **Rot (`inexxio`) =
  der EINE laute Akzent** — CTA, ein Headline-Wort, aktiver Zustand, echter Fehler;
  nie dekorativ, nie flächig. **Slate (`accent`) = die leise Stimme** für Info,
  aktive Zeilen/Nav, Links im dichten ERP. Slate konkurriert nie mit Rot.
- **ERP: Struktur vor Fläche** — Haarlinien (`border-border-1`) + Weissraum statt
  Kartenrahmen+Schatten. `shadow-ds-*` nur für echte Overlays (Modal/Menü).
- **Status: Punkt + Wort** wo möglich (6px Dot in Semantik-Farbe); gefüllte Badges
  sparsam. Symbol + Farbe + Label; Infotexte gehören in den **Hover** (ⓘ), nicht in
  die Fläche.
- **Icons: nur Lucide** (`lucide-react`), funktional & sparsam, neutral `fg-3`/`fg-2`;
  Rot nur aktiv/selektiert. **Keine Emoji**, kein Deko-Icon-Set.
- **Typo:** Headlines `font-display` (Inter Tight, 800, enges Tracking), Body
  `font-body` (Inter). **Zahlen immer tabellarisch** (`.ix-tnum`), wo sie ausrichten.
- **Schweiz:** CHF mit `'`-Trennung (`9'999 CHF`), `25 m²`; **du** in Headlines/CTA,
  **Sie** im erklärenden Service-Text — nicht mischen.

## Alt = deprecated (Migrationspfad)
`slate-*`, `blue-600`, `brand-*` (blaue Alt-Marke), `fields.tsx tone='#2563eb'` sind
Altlast (kompiliert noch, ist aber nicht Zielbild). **Beim Anfassen einer Komponente**
auf Tokens migrieren — Mapping-Tabelle in `docs/design-system/README.md §4`. Kein
Big-Bang; inkrementell mitziehen.

## Bestehendes UI-Vokabular wiederverwenden
Nicht neu erfinden: `frontend/src/components/erp/fields.tsx` liefert `StatusBadge`,
`PanelHeader`, `SectionTitle`, `PrimaryButton`, `Tooltip`/`InfoHint`, `SearchSelect`
u. a. Diese Bausteine nutzen (und schrittweise auf die Tokens ziehen), statt Eigenbau.

## Neuen Claude-Design-Export übernehmen
Der **`claude-design`**-MCP-Server (registriert in `.mcp.json`, Repo-Wurzel) zieht den
Export aus Claude Design direkt – inkrementell abgleichen (Details: README §5). Danach:
`colors_and_type.css` ersetzen → Referenz/Doku in `docs/design-system/` aktualisieren
→ `cd frontend && npm run build` (Build = Wächter). Tokens sind nach Namen stabil.
