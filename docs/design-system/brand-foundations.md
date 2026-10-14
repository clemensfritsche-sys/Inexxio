# INEXXIO — Design System

> **Klein wohnen. Gross leben.** — Maximale Wohnqualität auf kleinem Raum.

This repository is the brand & product design system for **INEXXIO AG**, a Swiss
(CHF, German-language) microliving company. Use it to generate well-branded
interfaces, marketing pages, and assets that look and feel like INEXXIO.

---

## 1. Company & product context

INEXXIO is an **interior-design / "Raumlösungen" (room-solutions) service for small
urban apartments**. The promise: turn limited square metres into full-value living
space — *"Ich will schöner wohnen – nicht größer."* (I want to live more beautifully,
not bigger.)

**How the product works (3 steps):**
1. **Raumdaten erfassen** — the customer 3D-scans their room with a smartphone
   (LiDAR), 5–10 min, ~2 mm precision. No appointment, no special hardware.
2. **Individuelles Designkonzept** — within 48–72 h INEXXIO returns a photorealistic
   3D furnishing concept that uses every square millimetre.
3. **Produktion & Lieferung** — local partner workshops CNC-cut the chosen elements;
   delivery + assembly to the door. The customer buys only the pieces they want.

**Audiences:** singles, couples and families in compact city flats; also holiday-flat
(Ferienwohnung) owners and loft dwellers. Positioning is aspirational and a little
provocative — *"the most expensive square metre in the world is the one in your own
flat that you pay for but never use."*

**Status:** early / pilot ("Pilotprojekt", "Werde einer unserer ersten Kunden").
Founded as **INEXXIO AG**, © 2024. Contact: +41 79 505 83 02 · info.inexxio@gmail.com.

**Surfaces represented:**
- **Marketing website** (the only shipped product surface) — a long single-page Wix
  site: hero with 3D-scan CTA, use-case cards, inspiration gallery, "INEXXIO in
  Zahlen" savings calculator, 3-step process, story, testimonial, about, FAQ.
- **"Meine Projekte" / scan flow** — implied product app (smartphone 3D-scan →
  project dashboard). Not publicly inspectable; the UI kit includes a *plausible*
  reconstruction clearly marked as such.

### Sources given
- **Live website:** https://www.inexxio.com/ (Wix-built; German). Sub-pages seen:
  `/meine-projekte`, `/delivery`, `/assembly`, `/impressum`, `/privacy-policy`,
  `/shipping-policy`.
- No codebase, Figma, or decks were provided. All foundations below were derived
  from the live site's **content + real downloaded image/logo assets** (in `assets/`).
  Exact production fonts and color tokens were **not** available from Wix and are
  documented as **substitutions** (see Visual Foundations).

---

## 2. CONTENT FUNDAMENTALS — how INEXXIO writes

**Language:** German (Swiss). Uses the Swiss **ß→ss** convention inconsistently —
headlines say **"Gross leben"** (ss) while body copy sometimes uses "größer/Räume"
(ß). When in doubt for headlines, prefer **ss** (Gross, grösser); body may use ß.
Currency is **CHF**, formatted Swiss-style with an apostrophe thousands separator:
**9'999 CHF**, **25 m²**.

**Voice — dual register, by design:**
- **Headlines & emotional copy = "du" (informal, intimate).**
  *"Ich will schöner wohnen – nicht größer."* · *"Hol dir den Raum zurück, den du
  längst bezahlst."* · *"Verwandle deinen Raum."*
- **Explanatory / service body = "Sie" (formal, trustworthy).**
  *"Verwandeln Sie jede kleine Wohnung…"* · *"Sie entscheiden selbst, welche Möbel…"*

  → Keep this split: hero/CTA/story speak **du**; feature explanations and process
  steps speak **Sie**. Don't mix within a single block.

**Tone:** confident, aspirational, gently provocative, optimistic. Reframes a
constraint (small flat) as an opportunity. Sells *Lebensqualität* (quality of life),
not furniture. Tech-forward words signal innovation: *3D-Scan, LiDAR, CAD,
KI-gestützt, millimetergenau, fotorealistisch, Express-Service 48–72 h.*

**Casing:** German noun capitalisation throughout. Section titles are often a
**two-part headline** — a punchy phrase + a softer subline, e.g.
*"Still und leise verlierst du Geld — INEXXIO in Zahlen"*,
*"Mehr als nur Möbel — Dein Raum, neu gedacht"*.

**Signature devices:**
- **Green check bullets ✓** for benefit lists (3–4 per block), each a short benefit
  phrase: *"✓ Millimetergenau: Präzision bis auf 2 mm Genauigkeit"*.
- **Big number stats** with a short label: *70 % mehr Stauraum*, *48–72 h*,
  *5–10 Minuten*, *2 mm*.
- **Imperative CTAs:** *Jetzt 3D-Scan starten · Projekt starten · Jetzt Scannen ·
  Konzept anfordern · Jetzt Beratung vereinbaren · Inspirieren lassen.*
- Recurring slogans: **"Klein wohnen. Gross leben."** · **"Weniger Raum bedeutet
  nicht weniger Leben – es bedeutet bewusster leben."** (INEXXIO Philosophy).

**Emoji:** none in brand voice. The only glyph used decoratively is the **✓ check**.
Keep emoji out.

---

## 3. VISUAL FOUNDATIONS

**Overall vibe:** *bold Swiss-tech meets warm Scandinavian microliving.* A
high-contrast **black + vivid red** brand mark sits on top of soft, warm,
photoreal interiors. The result is energetic and premium, never sterile.

### Color
- **Primary red `#E51A14`** (logo "XX" swoosh) — used for accents, CTAs, the accent
  word in headlines, underlines. Has a subtle vertical gradient in the logo:
  bright `#FA3030` → deep `#B3120F`. Use red **sparingly and decisively** — it is the
  single loud element against neutral surroundings.
- **Black `#0A0A0B`** — primary text, inverse sections, the other half of the logo.
- **Warm neutrals** carry everything else: off-whites `#F7F5F2 / #FBF9F6`, sand
  `#EFEBE5 / #EBE4DA`, light-oak accent `#C9A27A`, cool stone-grey `#9AA0A0` (both
  pulled from the interior renders). Backgrounds are **warm**, not blue-grey.
- Inverse "INEXXIO in Zahlen" / story sections go **near-black `#141416`** with white
  text and red highlights.
- **Cool accent `#2C6E8F` (slate teal-blue)** — a restrained *third voice*, added in
  v2.2 for the ERP. It carries **informational** accents, active-nav and links inside
  dense product UI where brand red would read as an alert or be too loud. Soft fill
  `#E7F0F4` tints active rows / info chips; `#1C4D66` is text/icons on that fill.
  It **never competes with red** on marketing surfaces — red stays the single loud
  brand accent; slate is the quiet, competent one.

### Type
- **Display = Inter Tight (800), very tight tracking (−0.035 to −0.04em).** The brand
  font is **Inter** — for headlines we use its tighter optical sibling *Inter Tight*
  at heavy weight, set large with near-solid leading. Confident, modern, Swiss.
- **Body/UI = Inter (400–700).** The workhorse: clean, neutral, highly legible.
- **Numerals are tabular** (`font-variant-numeric: tabular-nums`) wherever figures
  align — stats, the calculator, KPIs, index numbers.
- Eyebrows/overlines are **uppercase, +0.18em**, usually **red**. Section indices
  (`01 / 02 / 03`) are set in **mono** (JetBrains Mono) as a small red kicker.

### Imagery (the brand's heart)
- **Photoreal 3D interior renders** (Gemini-generated) of small studios: loft beds,
  multifunctional joinery, integrated desks/kitchens.
- **Palette of imagery: warm + bright + airy.** Light-oak floors, white/light-grey
  cabinetry, soft greys, natural daylight, green-plant accents. Calm, aspirational,
  *not* moody. One recurring exception: a **black-&-white aerial city photo** in the
  Story section (dense towers) used to dramatize urban density.
- Images are **full-bleed or large rounded cards**; an inspiration **masonry gallery**
  uses low-res blurred placeholders that resolve to sharp renders (lazy-load feel).
- Treatment: minimal filtering, true-to-life color, soft contrast. No heavy grain.

### Layout & space
- Generous whitespace, **8-pt spacing**, wide section padding (`--sp-9/10`).
- Alternating section backgrounds: white → warm off-white → occasional near-black
  inverse band. Max ~2 background tones per page plus the dark band.
- Content centered with comfortable measure; big two-part headlines anchor sections.

### Shape, border, elevation
- **Corner radii:** soft but not bubbly — cards `--r-lg (20px)`, buttons `--r-pill`
  or `--r-md`, images `--r-lg/xl`. The logo's strokes are fully rounded (pill caps),
  so **pill buttons** feel on-brand.
- **Borders:** hairline warm greys `#E7E2DA / #D8D2C8`; dark sections use translucent
  white borders.
- **Shadows:** soft, warm, low-contrast (tinted with brown, not pure black). Kept
  deliberately restrained — nothing should glow at rest. Cards = `--shadow-sm/md`,
  hovered = `--shadow-lg`. Red CTAs may carry a subtle red glow `--shadow-red` /
  `--glow-sm/md/lg`, but **only as a hover or press accent, never a resting glow**
  (tuned lighter in v2.1 — see Changelog).
- **Cards:** white surface, 20px radius, hairline border + soft shadow; image-top +
  text-body pattern with a ✓ benefit list.

### Motion & states
- **Easing:** smooth ease-out, ~180–260 ms. Gentle, premium; no bouncy/elastic.
- **Entrances:** soft fade + small upward translate (8–16px) as sections scroll in.
- **Hover:** lift (translateY −2px) + deepen shadow; red buttons darken
  bright→`--inexxio-red`; secondary/ghost buttons fill or darken border.
- **Press:** slight scale-down (0.98) and/or shift to `--inexxio-red-deep`.
- **Transparency/blur:** sparing — a frosted sticky header (white @ ~80% +
  backdrop-blur) and image protection gradients behind overlaid text. No glassmorphism
  everywhere.

### ⚠️ Substitution notes
- **Fonts: confirmed = Inter.** The brand uses **Inter** (client-confirmed). Display
  headlines use **Inter Tight** (the tighter optical cut of the same superfamily) at
  weight 800; body/UI use **Inter**. Both load from Google Fonts.
- **Color tokens** were sampled from the **real logo** (red `#FA3030`→`#B3120F`, black
  `#0A0A0B`) and eye-matched from the interior renders for neutrals. Tweak if you have
  exact brand values.

### Design direction — "Swiss editorial" (elevated)
The foundations and UI kit are tuned to a refined **International Typographic Style**
(Swiss design) — fitting for a Swiss company. Hallmarks used throughout:
- **Structural grids & hairline rules** instead of heavy shadows; sections open with a
  **2px black top rule** + a numbered index (`05 / INEXXIO IN ZAHLEN`) in the left margin.
- **Big, tight, heavy headlines** (Inter Tight) against generous negative space.
- **Red as a single sharp accent** — eyebrows, one headline word, CTAs, the slider,
  active nav underline — never decorative.
- **Cards built from borders** (1px grid lines), tabular figures, restrained motion
  (soft fades + image scale on hover). Minimal, precise, premium.

---

## 4. ICONOGRAPHY

INEXXIO's site is **icon-light**. The brand's recurring graphic devices are:
- **The ✓ check** (benefit bullets) — by far the most-used glyph. Render it in
  **brand red** or **success green** at the start of benefit lines.
- **Numbered step badges** (1 / 2 / 3) for the process section — large numerals, not
  pictographic icons.
- **The hockey-stick swoosh** from the logo (red rounded stroke sweeping above/below
  a word) — usable as a brand accent / underline motif.

There is **no custom icon font or SVG icon set** in the source. For UI chrome that
needs icons (menu, phone, mail, arrows, close, chevrons), this system standardises on
**[Lucide](https://lucide.dev)** — a clean, rounded-stroke open-source set whose 2px
rounded caps match the logo's rounded strokes. **This is a substitution** (the brand
ships no icon set); load from CDN:

```html
<script src="https://unpkg.com/lucide@latest"></script>
<script>lucide.createIcons();</script>
```

Use icons **functionally and sparingly** (nav, contact, form affordances). Do **not**
introduce decorative/colorful icon cards or emoji — they're off-brand.

Real assets copied into `assets/`: `logo.png` (3000×1500, transparent), interior
renders `room1–7.png`, `hero_scan.png` (3D-scan phone mock), `city_bw.png`
(B&W aerial), `og_hero.png` (social hero composite).

---

## 5. ERP / DENSE-UI & ICON-FIRST PATTERNS

INEXXIO's second surface is an **internal ERP / project-management app** (projects,
team, finances, reports) alongside the marketing site. Dense, data-heavy screens need
the same Swiss-editorial restraint as the website, just compressed. Rules:

- **Icons carry meaning, not decoration.** Lead list rows, nav items and stat tiles
  with a single **Lucide** glyph instead of a repeated text label — e.g. a nav rail is
  icon + 10px micro-label, never icon *and* a full sentence. Icons are neutral
  `--fg-3`/`--fg-2` by default; **red is reserved for the active/selected state only**,
  exactly like the website's nav-underline convention.
- **Structure over surface.** Prefer hairline dividers (`--border-1`) and whitespace
  over card borders + drop shadows to separate dense content. A table row, a KPI tile,
  a nav item should sit flat against the page; reach for `--shadow-sm/md` only for
  true overlays (modals, menus), never for routine rows or tiles.
- **Status dots, not badges.** A 6px colored dot (`--success` / `--warning` /
  `--inexxio-red`) + one short word reads faster than a filled pill badge and keeps
  rows light — use pill badges sparingly, for the one or two states that need real
  emphasis.
- **Compact nav rail, not a wordy sidebar.** A 76–80px icon rail (see
  `preview/erp-nav-rail.html`) with a 2px red left-accent on the active item scales
  better across dashboard/detail/settings screens than a full-width labelled sidebar
  — reserve a wider labelled sidebar for shallow apps with 4 destinations or fewer.
- **Tabular numbers everywhere figures appear** — KPI tiles, table values, deltas —
  exactly as on the marketing site's calculator and stats.

See the **ERP / App** group in the Design System tab for reference specimens: icon
nav rail, KPI tiles, icon-led data list, and a minimal icon-only top bar.

---

## 6. Index — what's in this system

| Path | What it is |
|---|---|
| `README.md` | This file — context, content, visual foundations, iconography. |
| `colors_and_type.css` | All design tokens: color, type scale, spacing, radii, shadows, semantic classes. |
| `assets/` | Real brand assets — logo, interior renders, scan mock, city photo. |
| `preview/` | Small specimen cards that populate the Design System tab. |
| `ui_kits/website/` | High-fidelity recreation of the INEXXIO marketing site (React/JSX + `index.html`). |
| `SKILL.md` | Agent-Skill manifest so this system works in Claude Code. |

**Quick start:** link `colors_and_type.css`, pull imagery from `assets/`, set
headlines in `var(--font-display)` weight 800 with a single red accent word, keep
backgrounds warm-neutral, and write copy in the **du-headline / Sie-body** voice.

---

## 7. Changelog

- **v2.2 (current):** Made `--shadow-red` **dezenter still** (0.14 alpha / 8px blur /
  2px offset, tinted toward deep-red ink) and lightened `--glow-sm/md/lg` ~40% so red
  CTAs lift rather than glow. Added a **cool slate accent** (`--accent #2C6E8F`,
  `--accent-soft`, `--accent-ink`) as a restrained third colour for ERP information /
  active states, plus matching `*-bg` tint tokens for every semantic colour
  (`--success-bg/--warning-bg/--info-bg/--danger-bg`). Updated `--info` to the slate
  accent. New ERP specimen `preview/erp-status-tooltips.html`: icon+colour+text status
  badges and icon-only actions with hover tooltips ("Symbole vor Text").
- **v2.1:** Lightened the entire shadow scale ~35–45% for a calmer, less
  "heavy" feel — `--shadow-red` in particular was a loud resting glow (0.26 alpha /
  24px blur) and is now a dezent hover/press accent (0.16 alpha / 14px blur). Added
  `--glow-sm/md/lg` and `--shadow-xl` tokens. Removed an unmaintained parallel "v2"
  token/component fork (`colors_and_type_v2.css`, `site_v2.css`, `index_v2.html`) that
  had drifted from `colors_and_type.css` — **`colors_and_type.css` is the single
  source of truth**; `styles.css` at the project root imports only that file. Added
  an **ERP / App** card group (icon nav rail, KPI tiles, icon-led data list, top bar)
  for the upcoming internal tool, built icon-first per §5 above.
- **v2.0:** Initial Swiss-editorial foundations, website UI kit, brand colors/type/
  spacing tokens derived from the live site and real assets.
