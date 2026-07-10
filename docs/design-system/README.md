# Inexxio Design System — verbindliche Grundlage

> **Klein wohnen. Gross leben.**
> Dies ist die **eine, verbindliche** Design-Grundlage für ALLE Oberflächen von
> Inexxio (Website, Shop, ERP). Jede neue oder geänderte UI **muss** auf diesem
> System aufbauen. Es ist der in den Code übernommene Export aus **Claude Design**
> (claude.ai/design) und ersetzt die frühere, abgedriftete Ad-hoc-Palette
> (slate/blue-600).

---

## 1. Wo liegt was (Single Source of Truth)

| Pfad | Rolle |
|---|---|
| **`frontend/src/styles/design-system/colors_and_type.css`** | **DIE Quelle der Wahrheit.** Alle Design-Tokens (Farbe, Typo, Spacing, Radien, Schatten) + `.ix-*`-Helper. Wird als erstes CSS-Modul in `frontend/src/app/layout.tsx` geladen. |
| `frontend/tailwind.config.js` | Spiegelt die Tokens als Tailwind-Utilities (`bg-bg-2`, `text-fg-3`, `text-accent`, `border-border-1`, `rounded-ds-lg`, `shadow-ds-md`, `font-display`). Enthält **keine eigenen Werte** – nur `var(--…)`-Referenzen. |
| `frontend/src/app/globals.css` | Nur noch app-lokale Komponenten-Styles (Login, Public-Site, Buttons) + die Alias-Map `--ix-* → --inexxio-*`. **Definiert keine Token-Werte mehr.** |
| `docs/design-system/brand-foundations.md` | Vollständige Marken-/Content-/Visual-Doku (Stimme, Farben, Typo, Bildsprache, ERP-Muster). Zum Lesen, nicht zum Bauen. |
| **`frontend/public/brand/`** | Echte Marken-Assets für die App: `inexxio-logo.svg` (bevorzugt), `favicon.svg`, `inexxio-logo.png`. Produktiv nutzbar. |
| `docs/design-system/reference/` | Read-only Referenz: Instanz-Detail-Mockups (`mockups/*.dc.html`), Referenz-React-Komponenten (`components/`), Website-UI-Kit (`ui-kit-website/`), Design-Specimens (`preview/`), offizielle Claude-Design-Skill (`inexxio-design.SKILL.md`), Token-Manifest. Vorlage, **nicht** direkt importieren. |
| `.claude/skills/inexxio-design-system/SKILL.md` | Auto-Skill: legt jeder künftigen Claude-Session bei UI-Arbeit diese Regeln vor. |
| **`.mcp.json`** (Repo-Wurzel) | Projekt-Scope-MCP-Konfiguration: registriert den **`claude-design`**-Server (`https://api.anthropic.com/v1/design/mcp`) für **jede** Claude-Code-Session in diesem Repo. Damit zieht Claude den Claude-Design-Export direkt statt ihn manuell zu kopieren (§5). |

> **Marketing-Bildmaterial** (Interior-Renders `room1–7.png`, `hero_scan.png`,
> `city_bw.png`, `og_hero.png`, zusammen ~9 MB) ist **bewusst nicht** im Repo — es
> gehört zur Website-Arbeit und liegt im Claude-Design-Export. Beim Neubau der
> Marketing-Seiten von dort ziehen (siehe `reference/ui-kit-website/`).

**Regel:** Ein Token-Wert wird an **genau einer** Stelle definiert – in
`colors_and_type.css`. Niemals Werte in `globals.css`, `tailwind.config.js` oder in
Komponenten hart kodieren.

## 2. So nutzt du das System (drei Wege, gleiche Wahrheit)

1. **Tailwind-Utilities** (bevorzugt im JSX):
   `className="bg-bg-1 text-fg-2 border border-border-1 rounded-ds-lg shadow-ds-sm"`
2. **CSS-Variablen** (in CSS/`style=`): `color: var(--fg-2); background: var(--bg-2);`
3. **`.ix-*`-Helper** (Typo-Primitive): `.ix-h2`, `.ix-overline`, `.ix-index`, `.ix-tnum`, `.ix-rule`.

## 3. Kernregeln (aus den Foundations, verbindlich)

- **Farbe = Bedeutung.** Warme Neutraltöne (`bg-*`, `sand-*`, `fg-*`) tragen die
  Fläche. **Rot (`inexxio`) ist der EINE laute Akzent** – nur CTA, ein Headline-Wort,
  aktive Nav-Unterstreichung, echte Fehler. Nie dekorativ.
- **Slate (`accent`) ist die leise dritte Stimme** – informative/aktive Zustände,
  Links, aktive Zeilen im dichten ERP, wo Rot zu laut wäre oder als Alarm gelesen
  würde. Konkurriert **nie** mit Rot. `accent-soft` = getönte Füllung, `accent-ink`
  = Text/Icon darauf.
- **Struktur vor Fläche.** Im ERP: Haarlinien (`border-1`) + Weissraum statt
  Kartenrahmen + Schlagschatten. `shadow-ds-*` nur für echte Overlays (Modals, Menüs).
- **Status: Punkt statt Badge**, wo möglich (6px farbiger Dot + ein Wort). Gefüllte
  Pillen sparsam. Symbol + Farbe + Label (semantische Config), Infotexte in den Hover.
- **Typo:** Headlines in `font-display` (Inter Tight, 800, enges Tracking), Body in
  `font-body` (Inter). Zahlen **immer tabellarisch** (`.ix-tnum` /
  `font-variant-numeric: tabular-nums`), wo Werte ausgerichtet sind.
- **Icons:** ausschliesslich **Lucide** (`lucide-react`), funktional & sparsam,
  neutral `fg-3`/`fg-2`; Rot nur für aktiv/selektiert. Keine Emoji, kein Deko-Icon-Set.
- **Schweizer Konventionen:** CHF mit `'`-Tausendertrennung (`9'999 CHF`), `25 m²`;
  Headlines/CTA in **du**, erklärender Service-Text in **Sie** (nicht mischen).
- **Radien/Schatten:** Karten `rounded-ds-lg` (20px), Buttons `rounded-ds-md`/Pille;
  Schatten weich, warm, zurückhaltend. Roter Glow (`shadow-ds-red`/`shadow-glow-*`)
  nur als Hover/Press-Akzent, **nie** als Ruhezustand.

## 4. Migration der Bestands-Komponenten (inkrementell)

Viele bestehende ERP-Komponenten nutzen noch `slate-*` / `blue-600` (Alt-Marke) und
`fields.tsx: tone='#2563eb'`. Das bleibt **kompilierbar** (deprecated `brand-*` in
Tailwind), ist aber **nicht mehr Zielbild**. Beim Anfassen einer Komponente:

| alt (deprecated) | neu (Design System) |
|---|---|
| `bg-slate-50` / `bg-white` | `bg-bg-2` / `bg-bg-1` |
| `text-slate-900` / `-600` / `-400` | `text-fg-1` / `text-fg-3` / `text-fg-4` |
| `border-slate-200` | `border-border-1` |
| `blue-600` (info/aktiv) | `accent` (Slate) |
| `text-blue-600` als Marke | `text-inexxio` (Rot, nur echter Akzent) |
| `focus:ring-blue-500` | `focus:ring-accent` |
| `rounded-xl` (Karte) | `rounded-ds-lg` |

Keine Big-Bang-Umfärbung – **beim nächsten Edit einer Datei mitziehen**, so
konvergiert die App verlustfrei aufs System.

## 5. Neuen Claude-Design-Export übernehmen (Re-Sync)

Das Design-System ist der in den Code übernommene Export aus **Claude Design**
(claude.ai/design). Für den Re-Sync ist der **`claude-design`**-MCP-Server in
`.mcp.json` (Repo-Wurzel) registriert – **jede** Claude-Code-Session in diesem Repo
bekommt ihn automatisch (einmalige Bestätigung «MCP-Server dieses Projekts vertrauen»).

### 5.1 Über den `claude-design`-MCP (bevorzugt)

Der Server bildet die Claude-Design-Projekte auf Lese-/Schreib-Operationen ab
(`list_projects`, `list_files`, `get_file`, `write_files` …), gebunden an deinen
**claude.ai-Login**; der erste Zugriff fragt einmalig nach der Freigabe von
Design-System-Zugriff für den Login (OAuth). Abgleich **inkrementell, eine Komponente
nach der anderen** – nie als Voll-Ersatz. Konkret für Inexxio: die kanonische
Token-Datei und die Referenz-/Doku-Dateien unter `docs/design-system/` aus dem Projekt
ziehen, dann §5.3.

Ausserhalb dieses Repos (persönlicher Scope) lässt sich derselbe Server per CLI
hinzufügen:
`claude mcp add --transport http claude-design https://api.anthropic.com/v1/design/mcp`

### 5.2 Manuell (Fallback / was dabei passiert)

1. Die kanonische Token-Datei ersetzen:
   `cp <export>/…/colors_and_type.css frontend/src/styles/design-system/colors_and_type.css`
2. Referenz-/Doku-Dateien in `docs/design-system/` aktualisieren (Foundations,
   Mockups, Manifest).

### 5.3 Danach immer

`cd frontend && npm run build` – der Build ist der Wächter (fehlende Tokens fallen
sofort auf). Tokens sind nach **Name** stabil; nur Werte ändern sich → kein
Komponenten-Refactor nötig.

## 6. „Instanz Detail"-Redesign (nächster konkreter Schritt)

Das ursprünglich gelieferte Mockup liegt unter
`docs/design-system/reference/mockups/Instanz Detail.dc.html` (+ Mobile). Es ist die
erste Fläche, die **auf diesem System** umgesetzt werden soll – als Redesign von
`frontend/src/components/erp/instance-detail.tsx`, pixelgenau am Mockup, aber mit den
Tokens/Utilities oben statt inline-HTML.
