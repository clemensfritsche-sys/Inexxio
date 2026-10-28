# Logo-Generator

Erzeugt alle Logo-Dateien in `../` aus einer Konstruktion (Logo v5 «F1», Oktober 2026).
Nie eine Logo-Datei von Hand ändern – Parameter hier anpassen und neu erzeugen.

```bash
pip install shapely svgelements
python3 make_logos.py          # schreibt ../inexxio-*.svg
```

- `logo.py` – die Konstruktion: Pfeil-E, Chevron-X, verschachteltes zweites X, roter Schwung,
  überall derselbe Abstand zwischen parallelen Strichen. Einheit: Versalhöhe = 100.
- `make_logos.py` – Proportionen von F1 (`F`), Symbol (kräftiger, bündig), Lockup
  «ehemals HS Steiner» (60 : 40), alle Farbvarianten.
- `hs-steiner-quelle.svg` – Quelle für «ehemals» und das HS-Steiner-Zeichen (unverändert
  übernommen, nur skaliert).

**Kopien** (nach dem Erzeugen nachziehen, dann `website/`: `node scripts/export-erp.mjs` und
`node scripts/make-assets.mjs` für die PNG):

| Kopie | Quelle |
|---|---|
| `website/public/logo/inexxio-ehemals-hs-steiner.svg` · `-weiss.svg` | `inexxio-stacked-light.svg` · `-dark.svg` |
| `website/public/logo/inexxio-wortmarke-weiss.svg` | `inexxio-horizontal-dark.svg` |
| `website/public/favicon.svg`, `frontend/src/app/icon.svg`, `../favicon.svg` | `inexxio-symbol-red.svg` |
| `website/src/assets/brand/schriftzug-fuss.svg` | `inexxio-horizontal-light.svg`, Ink → `#1E1F21`, ohne Titel und Masse |
| `frontend/public/mail/logo.png` · `logo-dark.png` (291 × 78) | Wortmarke hell · dunkel |
| `backend/app/assets/img/inexxio-logo.png` (900 breit) | Wortmarke hell |

Ändert sich das Seitenverhältnis: `Lockup.astro` (`aspect-ratio`), `Footer.astro`
(Masse und Anschnitt des Schriftzugs), `mail_layout.LOGO_W/LOGO_H`.
