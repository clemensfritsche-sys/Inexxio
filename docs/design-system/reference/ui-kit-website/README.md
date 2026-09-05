# INEXXIO — Website UI Kit

A high-fidelity, interactive recreation of the **INEXXIO marketing site**
(`https://www.inexxio.com/`) — a long single-page German microliving site. Built
with React + Babel (in-browser) against the tokens in `../../colors_and_type.css`.

## Run
Open `index.html`. No build step — React/Babel/Lucide load from CDN.

## What's interactive
- **Sticky frosted header** with desktop nav → collapses to a burger menu < 1000px.
- **"Jetzt 3D-Scan starten"** (header, hero, CTA) opens a **3-step scan modal**:
  Raum scannen (animated LiDAR scan line) → Daten verarbeiten → Konzept anfordern
  (form). Finishing fires a confirmation **toast**.
- **Inspiration masonry** — click any render to open a **lightbox**.
- **"INEXXIO in Zahlen" calculator** — drag the m² slider; lost-space, lost-value,
  solution price and amortisation KPIs recompute live (Swiss CHF formatting, e.g.
  `2'448 CHF`).
- **FAQ accordion** — single-open, animated.

## Files
| File | Contents |
|---|---|
| `index.html` | Mounts the app; loads CSS + all JSX. |
| `site.css` | All component styles (uses design-system tokens). |
| `ui.jsx` | Atoms: `Icon` (Lucide), `Button`, `Eyebrow`, `Check`, `SectionHead`. |
| `header.jsx` | `Header` (nav + mobile menu), `Hero`. |
| `sections.jsx` | `UseCases` (4 cards), `Inspiration` (masonry), `Process` (3 steps). |
| `calculator.jsx` | `Calculator` — dark savings section. |
| `story.jsx` | `Story`, `Testimonial` (We·Want·You), `FAQ`, `CTA`, `Footer`. |
| `app.jsx` | `App` shell + `ScanModal`, `Lightbox`, toast state. |

## Component vocabulary (reuse these)
- **Buttons:** `btn-primary` (red, pill, red glow), `btn-dark`, `btn-ghost`,
  `btn-ghost-light` (on dark), `btn-link`. Add `btn-lg` for hero scale.
- **Benefit list:** `<ul class="checklist">` with `<Check red>` — the signature ✓ row.
- **Cards:** `.uc` image-top card with hover-lift; `.kpi` dark stat tile.
- **Section rhythm:** `.section` (white) alternating with `.section.alt` (warm
  off-white) and one `.dark-sec` (near-black) band. `SectionHead` = eyebrow + h-sec
  + sub.
- **Headlines:** `.h-display` / `.h-sec` in Archivo 800, one red accent word via
  `.mark` (gradient) or `.accent`.

## Fidelity notes / deliberate omissions
- This recreates the **public marketing site**. The "Meine Projekte" product app and
  the scan flow are **not publicly inspectable** — the scan modal here is a *plausible*
  reconstruction of the described 3-step flow, not a copy of a real screen.
- Copy is condensed/cleaned from the live site; the **du-headline / Sie-body** voice is
  preserved. Imagery is the real downloaded renders in `../../assets/`.
- Fonts (Archivo/Manrope) and the Lucide icon set are **substitutions** — see the root
  `README.md`.
