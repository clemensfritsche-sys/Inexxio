# Inexxio Design System — verbindliche Grundlage

> **Krane · Fahrmischer · Spezialmaschinen.** – Stand v4, Oktober 2026.
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
| **`frontend/public/brand/`** | Was die App selbst zeigt: `inexxio-ehemals-hs-steiner.svg` (Kopie von `website/scripts/export-erp.mjs`, auf `/login/verify`) und `anmelden.svg` (Zeichnung im Anmeldedialog). Das Favicon der App ist `frontend/src/app/icon.svg`; die Wortmarke steht in `reference/assets/logo/`. |
| `docs/design-system/reference/assets/logo/` | **Logo-System v5 «F1»** (Oktober 2026, vektoriell, nie umfärben): Wortmarke `inexxio-horizontal-light|dark|red|mono.svg`, mit «ehemals HS Steiner» `inexxio-stacked-*.svg` (60 % INEXXIO : 40 % HS Steiner), Favicon `inexxio-symbol-red.svg` (ganz rot), Symbol `inexxio-symbol.svg` (passt sich an), feste Symbole `inexxio-symbol-light|dark|red|on-red|mono.svg`, `inexxio-app-icon.svg`. Erzeugt von `generator/make_logos.py` – nie von Hand ändern. Regeln: `brand-foundations.md` §5. |
| `docs/design-system/reference/mockups/` | Die Vorlage der Website v4: `Startseite v4.dc.html` und `Startseite v4 mobil.dc.html` (Design-Artefakt «Website Startseite»). Zum Anschauen, **nicht** importieren. |
| `.claude/skills/inexxio-design-system/SKILL.md` | Auto-Skill: legt jeder künftigen Claude-Session bei UI-Arbeit diese Regeln vor. |


**Regel:** Ein Token-Wert wird an **genau einer** Stelle definiert – in
`colors_and_type.css`. Niemals Werte in `globals.css`, `tailwind.config.js` oder in
Komponenten hart kodieren.

## 2. So nutzt du das System (drei Wege, gleiche Wahrheit)

1. **Tailwind-Utilities** (bevorzugt im JSX):
   `className="bg-bg-1 text-fg-2 border border-border-1 rounded-ds-lg shadow-ds-sm"`
2. **CSS-Variablen** (in CSS/`style=`): `color: var(--fg-2); background: var(--bg-2);`
3. **`.ix-*`-Helper** (Typo-Primitive): `.ix-h2`, `.ix-overline`, `.ix-index`, `.ix-tnum`, `.ix-rule`.

## 3. Kernregeln (aus den Foundations, verbindlich)

- **Farbe = Bedeutung.** Kühle, neutrale Grautöne (v4, `bg-*`, `fg-*`) tragen die
  Fläche – überall gleich: Website, Konto, ERP, E-Mail. **Rot (`inexxio`) ist der EINE
  laute Akzent** – CTA, aktiver Zustand, echte Fehler. Nie dekorativ, **nie in einer
  Überschrift** (seit v4).
- **Slate (`accent`) ist die leise dritte Stimme** – informative/aktive Zustände,
  Links, aktive Zeilen im dichten ERP, wo Rot zu laut wäre oder als Alarm gelesen
  würde. Konkurriert **nie** mit Rot. `accent-soft` = getönte Füllung, `accent-ink`
  = Text/Icon darauf.
- **Struktur vor Fläche.** Im ERP: Haarlinien (`border-1`) + Weissraum statt
  Kartenrahmen + Schlagschatten. `shadow-ds-*` nur für echte Overlays (Modals, Menüs).
- **Status: Punkt statt Badge**, wo möglich (6px farbiger Dot + ein Wort). Gefüllte
  Pillen sparsam. Symbol + Farbe + Label (semantische Config), Infotexte in den Hover.
- **Typo (v3):** Titel in `font-display` (Inter Tight **700**, Zwischentitel **600**,
  Laufweite −0.03 em), Body in `font-body` (Inter 400, Labels 500). **Kein Gewicht 800+.**
  Leiter 12·14·16·18·24·32·48·64. Zahlen **immer tabellarisch** (`.ix-tnum` /
  `font-variant-numeric: tabular-nums`), wo Werte ausgerichtet sind.
- **Icons:** ausschliesslich **Lucide** (`lucide-react`), funktional & sparsam,
  neutral `fg-3`/`fg-2`; Rot nur für aktiv/selektiert. Keine Emoji, kein Deko-Icon-Set.
- **Schweizer Konventionen:** CHF mit `'`-Tausendertrennung (`9'999 CHF`), `25 m²`,
  **ss** statt ß; angesprochen wird mit **Sie**.
- **Wörter (v4):** kein «Fixpreis» (in keiner Form), keine «Werkstatt» – stattdessen
  «Standort», «Betrieb», «bei INEXXIO».
- **Radien/Schatten (v3):** Bedienelemente 8 px (`rounded-ds-md`), Karten 12 px
  (`rounded-ds-lg`), Dialoge 16 px. **Keine Pillen-Knöpfe.** Flach als Standard – Linien
  trennen, Schatten nur für schwebende Ebenen (Menü, Dialog, Toast). Glow-Tokens sind
  `none`. Der rote Knopf bekommt `shadow-ds-red` (= `--elev-primary`, sehr dezent)
  nur als Hover/Press-Akzent, **nie** als Ruhezustand.

## 3a. Website-Sprache (v4, verbindlich für Website und Konto-Kopf)

Referenz zum Anschauen: `reference/mockups/Startseite v4.dc.html` und
`Startseite v4 mobil.dc.html` (Design-Artefakt «Website Startseite»).

- **Überschrift – eine Form:** H2 in `font-display` 600, 48 px (mobil 32 px),
  −0.03 em; darunter **höchstens ein** grauer Satz (`fg-3`, 17/16 px). Keine Kicker
  darüber, keine roten Wörter, kein Mono, keine gesperrte Schrift. Zentriert nur bei
  «Häufige Fragen».
- **Knöpfe:** Rot **nur für die Anfrage** («Anfrage stellen», «Weiter», «Anfrage
  senden», «Aufgabe schildern»). Abschnitts-Links («Mehr über uns», «Alle
  Ratgeber-Artikel») hellgrau (`bg-3`). Auf Bildkarten ein **runder Pfeil** (44 px, Glas).
  Radius 8 px, Höhen 52 (gross) · 48 · 44.
- **Karten:** Radius 16 px, Bild vollflächig, Text **direkt auf dem Bild** über einem
  dunklen Verlauf. **Kein Kasten im Kasten:** Text und Knopf nie gemeinsam in einem
  Glas- oder Rahmenkasten.
- **Glas** (`.ix-glass` hell, `.ix-glass-dark` auf Fotos; Tokens `--glass-*`): offener
  Kopf und Menüs, Umschalter, Text auf Fotos, Eingabefelder über der Karte. Eine Ebene,
  nie verschachtelt. **Nie im ERP.**
- **Abschnitts-Muster:** Bühne mit Video · Bereichskarten, die beim Darüberfahren ~25 %
  breiter werden und ihre Kran-Szene spielen · Umschalter mit Überblendung · versetzte
  Karten (Garantien) · grosse Zahlen neben Porträt · Bild-Collage · Karussell mit
  angeschnittenen Nachbarn · Akkordeon in Glas über wechselndem Bild · Anfrage auf der
  Skizzenkarte (erst ein Feld, dann Kontakt).
- **Zeichnungen:** isometrisch, Grau-Rampe; **Grau ist die Serie, Rot ist, was wir
  dazubauen.**
- **Bewegung:** Überblenden 0.35–0.6 s mit `--ease-out`; bei `prefers-reduced-motion`
  steht alles.

## 3b. Version

**v4 (Oktober 2026)** – kühles, neutrales Grau statt warmem Beige (gleiche Token-Namen,
neue Werte: `--gray-*`, Elevation, Dark-Theme, `--fg-on-dark`, `sand-*` zeigt auf die
Grauskala), Glas-Tokens `--glass-*` und `.ix-glass*`, die Website-Sprache §3b. ERP und
Konto übernehmen das Grau automatisch über die Tokens; Glas bleibt der Website vorbehalten.
Die E-Mail-Vorlage (`backend/app/services/mail_layout.py`) und die Website-Zeichnungen sind
mitgezogen.

v4 baut auf v3 auf (Titel 700/600, Radien 8/12/16, flach, Rot-Rampe `--red-50…900`, drei
Token-Schichten Primitive → semantisch `--color-*` → v2-Aliase); **alle v2-Namen lösen
weiter auf**.

## 4. Migration der Bestands-Komponenten — **abgeschlossen** (August 2026)

Die Alt-Palette ist aus dem Code verschwunden: `slate-*`, `blue-*`, `gray-*`, das
hartkodierte `#2563eb` und der `brand-*`-Vorrat in `tailwind.config.js` sind entfernt
(**0 Vorkommen**, geprüft). Was hier stand, war der Migrationspfad; er ist gegangen.

Die Zuordnung bleibt als **Lesehilfe** für alten Code aus der Historie:

| alt (deprecated) | neu (Design System) |
|---|---|
| `bg-slate-50` / `bg-white` | `bg-bg-2` / `bg-bg-1` |
| `bg-slate-900` (Inverse-Sektion) | `bg-bg-dark` (Achtung: Farbgruppe **und** Wert heissen `bg`) |
| `text-slate-900` / `-700` / `-600` / `-400` | `text-fg-1` / `-2` / `-3` / `-4` |
| `border-slate-200` | `border-border-1` |
| `blue-600` (Info/aktiv/Link) | `accent` (Slate) |
| `bg-blue-50/100` (Info-Fläche, Symbol-Chip) | `bg-accent-soft` + `text-accent-ink` |
| `bg-blue-600` als **CTA-Fläche** | `bg-inexxio` (Rot = der EINE laute Akzent) |
| `focus:ring-blue-500` | `focus:ring-accent` |
| `rounded-xl` (Karte) | `rounded-ds-lg` |

> **Gemessen, nicht geglaubt.** Die Umstellung der öffentlichen Seiten wurde in Chromium
> geprüft (Screenshot + eine Suche nach Text, dessen Farbe der Hintergrundfarbe
> entspricht). Genau das hat den einen echten Fehler gefunden: `bg-dark` gibt es nicht –
> die Farbgruppe heisst `bg`, die Klasse also `bg-bg-dark`. Ohne die Prüfung wären fünf
> dunkle Hero-Sektionen weiss auf weiss gewesen, und der Build hätte nichts gemeldet:
> eine unbekannte Tailwind-Klasse ist kein Fehler, sie erzeugt schlicht kein CSS.

## 5. Neuen Claude-Design-Export übernehmen (Re-Sync)

Wenn du in Claude Design weiterarbeitest und neu exportierst:

1. Die kanonische Token-Datei ersetzen:
   `cp <export>/…/colors_and_type.css frontend/src/styles/design-system/colors_and_type.css`
2. Doku in `docs/design-system/` aktualisieren (`brand-foundations.md`, die Vorlage in
   `reference/mockups/`).

3. `cd frontend && npm run build` – der Build ist der Wächter (fehlende Tokens fallen
   sofort auf). Tokens sind nach **Name** stabil; nur Werte ändern sich → kein
   Komponenten-Refactor nötig.
