# Website INEXXIO (ehemals HS Steiner) – Plan

> Arbeitsplan zum Auftrag «Neue Website INEXXIO – ehemals HS Steiner». Jede Phase endet mit
> grünem Build, Commit und einem Haken hier. Wer nach einer Unterbrechung weitermacht,
> liest zuerst diese Datei, danach den Auftrag.

## 1. Ist-Zustand (Phase 0, gelesen am 03.10.2026)

| Frage | Befund |
|---|---|
| Stack | Monorepo: `frontend/` Next.js 14 (statischer Export, Tailwind), `backend/` FastAPI (Python 3.12) auf Cloud Run, PostgreSQL. |
| Was liegt unter «/» | Die Next-Route-Gruppe `(public)`: Startseite, Über uns, Kontakt, Impressum, AGB, Datenschutz – Inhalte des **Vorgänger-Geschäfts** («Präzisionsfertigung», Wohnraum-Design-System). Dieselbe Next-App trägt `/login`, `/konto`, `/erp`. |
| Rendering | Next-Export liefert HTML, lädt aber auf jeder Seite das React-Laufzeitpaket und den gemeinsamen Root-Layout (Einwilligungs-Banner, Plausible, Chunk-Guard). |
| Hosting | **Eine** Firebase-Hosting-Site je Umgebung (`inexxio-dev`, `inexxio-prod`), `public: frontend/out`, `cleanUrls: true`, `trailingSlash: false`, `/api/**` → Cloud Run (`inexxio-backend-dev`). Sicherheits-Header und CSP global in `firebase.json`. |
| Deploy | Push auf `develop` → `.github/workflows/deploy-dev.yml` (Quality → Backend → Frontend). `main` → `deploy-prod.yml` (Prod-Datenbank ist gestoppt). Node 20 in der CI. |
| Design-Tokens | `frontend/src/styles/design-system/colors_and_type.css` ist die eine Quelle (Rot `#E51A14`, Schwarz `#0A0A0B`, Papier `#F4F3F0`, Dunkel `#0E0E10`, Graustufen, System-Mono). Inter wird dort über Google Fonts geladen. |
| Marke | Es gibt ein bestehendes Zeichen: das rote **XX-Monogramm** (`frontend/public/brand/favicon.svg`). Das alte Wort-Logo (PNG mit Verlauf und Schwung, 365 KB) gehört zum Vorgänger-Geschäft. |
| Mailversand | **Keiner.** `backend/app/routers/contact.py` schreibt Anfragen nur ins Log (`TODO Phase 2`). Gmail-API ist geplant, nicht verdrahtet. |
| Alte Website hs-steiner.ch | Vom Netzwerk dieser Umgebung gesperrt; Fakten und ein Teil der URLs über die Suche erhoben (siehe §5). |

## 2. Entscheidungen (je ein Satz Begründung nach den drei Grundsätzen)

1. **Astro 7 als eigenständiges Teilprojekt in `website/`** – liefert reines HTML ohne
   Laufzeit-JavaScript; ein Neubau in Next hätte jede Seite um das React-Paket (≈ 90 KB gzip)
   schwerer gemacht und die Website an den ERP-Root-Layout gebunden. *Korrigiert in Phase 1*:
   geplant war Astro 5 auf dem Node 20 der CI; die aktuelle, gepflegte Fassung ist 7 und
   verlangt **Node ≥ 22.12**. Der Website-Schritt der CI läuft darum mit Node 22 – das ERP
   baut unverändert mit Node 20. Eine statische Ausgabe hat keine Server-Laufzeit, die
   Sicherheits-Updates bräuchte.
2. **Gleiche Firebase-Hosting-Site, zusammengeführte Ausgabe** – die CI baut beide Teile und
   kopiert `website/dist` in `frontend/out`; die Website besitzt «/» und ihre Pfade, das ERP
   behält `/erp`, `/konto`, `/login`, `/agb`. Null neue Infrastruktur, null Zusatzkosten; ein
   Kollisionswächter bricht ab, falls die Website je eine ERP-Seite überdecken würde.
3. **Die alten Next-Seiten `/`, `/ueber-uns`, `/kontakt`, `/impressum`, `/datenschutz`
   werden gelöscht** – sie sind durch die neue Website ersetzt; zwei Fassungen derselben
   Seite wären zwei Wahrheiten. **`/agb` bleibt** in Next: der Anmeldedialog des ERP verweist
   darauf.
4. **Formular-Backend = der bestehende, isolierte Endpunkt `POST /api/v1/contact`**, neu
   geschrieben – er ist bereits registriert (kein Eingriff in `main.py`), importiert nichts
   aus dem ERP und berührt keine Tabelle. Versand per SMTP aus der Standardbibliothek
   (`smtplib`, keine neue Abhängigkeit), Zugangsdaten nur über Umgebungsvariablen. **Ohne
   Zugangsdaten** antwortet er 503, und die Seite zeigt Telefon und einen vorausgefüllten
   `mailto:`-Link – keine Anfrage geht still verloren; zusätzlich steht die Anfrage als
   JSON-Zeile im Cloud-Run-Log.
5. **Farben aus dem Design-System, generiert** – `scripts/tokens.mjs` liest die DS-Datei und
   schreibt die benötigten Werte in `src/styles/tokens.css`; ein Wert existiert damit genau
   einmal. Die «Stahlgrau»-Stufen der Vorgabe sind die DS-Graustufen (`fg-2…4`,
   `border-1/2`) – das DS ist laut `CLAUDE.md` für alle Oberflächen verbindlich.
6. **Formsprache nach Vorgabe, nicht nach DS-Lifestyle** – 2 px Radius, keine Schatten,
   Inter 600–700 statt Inter Tight 800: das DS wurde für ein Wohnraum-Geschäft entworfen;
   seine «Swiss editorial»-Richtung (Haarlinien, Raster, Rot als einziger Akzent) passt, die
   weichen Radien und Pillen nicht zu Industrie.
7. **Schrift**: Inter Variable (Latin-Subset inkl. Latin-1, OFL), selbst gehostet, von Vite
   gehasht und vorab geladen (≈ 48 KB). **Mono = System-Mono-Stapel des DS** (0 Byte) statt
   einer zusätzlichen Webschrift – das DS hat das bewusst so entschieden.
8. **Logo**: Wortmarke als **Text aus der Konfiguration** (Inter 700, enge Laufweite) –
   so ist ein Namenswechsel eine Zeile; dazu Wortmarke A (schwarz) und B (rotes «XX») als
   SVG-Dateien für JSON-LD/Druck. **Favicon = das bestehende XX-Monogramm.** Alles als
   `[[PLATZHALTER: finales Logo]]` geführt.
9. **Bilder**: keine erfundenen; jede Bildstelle ist ein `ImagePlaceholder` aus einer
   zentralen Fotoliste (`src/config/photos.ts`) – dieselbe Liste ist die Fotoliste in
   `OFFENE_PUNKTE.md`. Erklärende Grafiken (Kranbuch-QR, Einsatzgebiet) als eigenes SVG.
10. **Karte**: schematische SVG-Karte aus echten Koordinaten statt eingebettetem Dienst –
    kein Cookie, keine Fremdanfrage; daneben «Route in Google Maps öffnen» als Link.
11. **Analytics**: neutraler `track()`-Helper, standardmässig aus; Anbieter ist eine offene
    Entscheidung.
12. **Redirects** der alten hs-steiner.ch-Pfade in `firebase.json` (Regex, Gross-/Klein-
    schreibung egal) – die einzige Stelle, an der Firebase sie ausführen kann; ein Wächter
    prüft, dass jedes Ziel als Seite existiert.
13. **CSP**: Die Website setzt eine strenge Richtlinie per `<meta>` (Skripte nur `'self'`);
    der Browser erzwingt sie zusätzlich zur globalen Header-CSP. Die globale bleibt, weil
    das ERP sie braucht. `frame-ancestors 'none'` wird **nicht** global gesetzt: das
    Firebase-Login-Iframe läuft auf derselben Origin; `X-Frame-Options: SAMEORIGIN` sperrt
    fremdes Einbetten bereits.
14. **Inhalte**: Astro Content Collections (Markdown + Frontmatter mit Zod-Schema) –
    Seitentexte getrennt von Layout, ein fehlendes Feld bricht den Build. Werte aus der
    Konfiguration werden in Texten über `{{schlüssel}}` eingesetzt, damit Name, Telefon und
    Adresse auch im Fliesstext nur an einer Stelle stehen.
15. **E-Mail-Vorlagen lesen dieselbe Konfiguration**: `scripts/export-contact.mjs`
    schreibt die nötigen Angaben nach `backend/app/assets/website_contact.json`; die CI
    prüft, dass die Datei aktuell ist (gleiches Muster wie `api.ts`).
16. **Kein Testnotizen-Pin auf der Website** – er hängt an der ERP-Anmeldung (React +
    Firebase) und würde jede Seite um ein Vielfaches schwerer machen.

## 3. Änderungen ausserhalb von `website/`

| Datei | Änderung | Warum zwingend |
|---|---|---|
| `backend/app/routers/contact.py` | neu geschrieben: Anfrage-Endpunkt (Validierung, Honeypot, Mindestzeit, Rate-Limit, SMTP, Bestätigung, No-JS-Antworten) | Formular braucht eine Verarbeitung; die Datei ist bereits der isolierte Endpunkt der öffentlichen Website |
| `backend/app/assets/website_contact.json` | neu, generiert | E-Mail-Vorlagen lesen die Website-Konfiguration |
| `backend/tests/test_contact.py` | neu | Wächter für den Endpunkt |
| `backend/openapi.json`, `frontend/src/types/api.ts` | regeneriert | CI prüft, dass sie zum Backend passen |
| `frontend/src/app/(public)/{page.tsx,ueber-uns,kontakt,impressum,datenschutz}` | gelöscht | durch die Website ersetzt |
| `frontend/src/app/robots.ts`, `frontend/public/robots.txt` | gelöscht | die Website liefert die eine `robots.txt` |
| `frontend/src/lib/api.ts` | `sendContactForm` entfernt | hatte nur die gelöschte Kontaktseite als Aufrufer |
| `frontend/src/components/ui/{button,input,select,textarea}.tsx`, `CookieSettingsButton` | entfernt | nur von gelöschten Seiten benutzt |
| `frontend/package.json` (+ Lock) | `react-hook-form`, `zod`, `@hookform/resolvers` entfernt | nur vom gelöschten Kontaktformular benutzt |
| `firebase.json` | `redirects` der alten hs-steiner.ch-Pfade | alte URLs auffangen (Auftrag Kap. 3.3) |
| `.github/workflows/deploy-dev.yml`, `deploy-prod.yml` | Website prüfen, bauen, zusammenführen | ohne diesen Schritt hätte die Domain keine Startseite mehr |
| `.gitignore` | `website/dist`, `website/.astro`, generierte Tokens | Build-Ausgaben gehören nicht ins Repo |
| `CLAUDE.md`, `backend/CLAUDE.md`, `frontend/CLAUDE.md` | Abschnitt «Website», Endpunkt-Zeile, entfernte Seiten | jede Sitzung liest sie zuerst |

Nicht angefasst: ERP-Backend (ausser dem Kontakt-Router), Datenbank, Modelle, Migrationen,
ERP-Frontend-Logik, Auth, die globalen Header in `firebase.json`.

## 4. Laufende Kosten

| Posten | Kosten |
|---|---|
| Hosting (Firebase Hosting, bereits vorhanden) | 0 CHF zusätzlich – statische Dateien, wenige MB |
| Formular (bestehender Cloud-Run-Dienst) | 0 CHF zusätzlich |
| Mailversand | abhängig vom Postfach-Anbieter; SMTP des bestehenden Mail-Hostings oder ein Gratis-Kontingent reicht (Anfragen im ein- bis zweistelligen Bereich pro Tag) |
| Schriften, Karten, Icons | 0 CHF – alles selbst gehostet bzw. eigenes SVG |
| Analytics | 0 CHF, solange aus |

## 5. Alte URLs (für die Redirect-Tabelle)

Erhoben über die Websuche (hs-steiner.ch selbst ist von hier aus gesperrt). Vollständigkeit
`[[PRÜFEN]]` – beim Start mit dem Abdeckungsbericht der Google Search Console abgleichen.

`/kontakt` · `/heuentnahmekran` (+ `/drehkran-hydraulisch`, `/bruecken-kran`, `/Einschienen-Kran`) ·
`/betonfordertechnik/Betonfahrmischer` · `/betonfordertechnik/verschleissteile` ·
`/antrieb-und-steuerung/elektrosteuerung` · `/antrieb-und-steuerung/Getriebe-und-Antrieb` ·
`/unsere-einsatzorte/ch-schweiz` · `/wahrschaftes/stahlbau` · `/sachtransporter-anhanger/aufbau` ·
`/hebebuhnen` · `/kleintransporter-pw/reifenservice`

## 6. Phasen-Checkliste

- [x] **0 – Analyse** und dieser Plan
- [x] **1 – Fundament**: Projekt, Konfiguration, Tokens, Schrift, Layout, Header, Footer,
      Navigation, Platzhalter-System, `SITE_MODE`
- [x] **2 – Komponenten**: Buttons, Karten, Sektionen, FAQ, ImagePlaceholder,
      Kranbahn-Linie, Formular-UI, Prüfpflicht-Check, Vorher/Nachher
- [x] **3 – Seiten**: Start → Übergabe → Krane (5) → Fahrmischer (3) → Service-Abo →
      Über uns → Einsatzgebiet → Kontakt → Karriere → Ratgeber (4) → Rechtliches → 404
      (24 Seiten inkl. `/kontakt/danke`; Feinschliff der Darstellung in Phase 6)
- [x] **4 – Formular-Backend und Tracking**: Endpunkt neu (19 Wächter, jeder gegen seine
      Fehlerform gegengeprüft), Vokabular-Export, alte Next-Seiten entfernt; Ende-zu-Ende in
      Chromium gegen einen echten SMTP-Briefkasten (30/30 inkl. Störungsfall und ohne JS)
- [ ] **5 – SEO und KI**: Meta, JSON-LD, Sitemap, robots.txt, llms.txt, Redirects, OG-Bilder
- [ ] **6 – Prüfung und Feinschliff**
- [ ] **7 – Abschlussbericht** und Deploy
