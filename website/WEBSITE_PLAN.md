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
17. **Eine Seitenliste** (`src/lib/pages.ts`) speist Sitemap, llms.txt und llms-full.txt;
    `Base.astro` bricht den Build, wenn eine Seite weder dort steht noch `noindex` trägt –
    eine neue Seite kann nicht still aus der Sitemap fallen. `lastmod` = eigenes Datum
    (Ratgeber, Rechtstexte) bzw. `site.seo.contentUpdated` – ein Datum aus Git wäre in der
    CI (flacher Checkout) für jede Seite das Datum des letzten Commits, also falsch.
18. **robots.txt als reine Funktion** (`src/lib/robots.mjs`): der Zweig «live» lässt sich
    so prüfen (`npm test`), obwohl ein echter live-Build heute an den offenen Markierungen
    abbricht.
19. **FAQ ohne Antwort fällt aus dem JSON-LD**: eine Frage, deren Antwort noch ganz offen
    ist, wäre dort eine leere Aussage.

*Entscheidungen aus Phase 6 – jede aus einer Messung, nicht aus Geschmack:*

20. **Ein Stylesheet für die ganze Website** (`cssCodeSplit: false`, rund 13 KB gzip): vorher
    lud jede Seite ein Dutzend Teil-Dateien, und jede blockiert das erste Zeichnen. Lighthouse
    mobil: LCP 2.1–2.4 s → 1.5–1.8 s; ab der zweiten Seite kommt es aus dem Cache.
21. **Was JavaScript einblendet, hat seinen Platz von Anfang an** (Schliessen-Knopf der
    Ankündigung, Schrittanzeige des Formulars: `visibility` statt `hidden`): sonst springt die
    Seite, sobald das Skript läuft – gemessen bis 0.073 CLS, danach 0 auf allen 24 Seiten.
22. **Logo-Lockup gestapelt**: nebeneinander brauchte die Kopfzeile 1254 px bei 1240 px
    Inhaltsbreite – «Über uns» und die Nummer brachen um. Gestapelt entspricht es zugleich
    der Vorgabe (Zusatz und «ehemals HS Steiner» *darunter*).
23. **`data-hero` markiert den Seitenkopf, nicht den Inhalt**: daran hängt, wann die
    Aktionsleiste unten erscheint. Stand es am ganzen Artikel (Ratgeber, Rechtstexte), kam
    sie erst nach rund 1700 px. `check-site` verlangt jetzt genau einen Seitenkopf je Seite,
    nie an `<article>`/`<main>`/`<body>`, und vor der H1.
24. **Versteckt heisst nicht fokussierbar**: die Aktionsleiste unten war nur verschoben – mit
    der Tabulatortaste blieben beide Links erreichbar, der Fokus stand unsichtbar unter dem
    Bildrand. Jetzt zusätzlich `visibility: hidden`, umgeschaltet erst nach der Bewegung.
25. **Die Prüffristen-Tabelle wird unter 768 px zu Blöcken** (Kranart, darunter beide Fristen
    mit Beschriftung): als Tabelle lag ausgerechnet die Spalte «Kontrolle durch
    Kranexperten» bei 390 px ausserhalb des Bildes. Die Beschriftung bleibt für Vorleser
    hörbar – verliert ein Browser mit `display: block` die Tabellen-Semantik, sagt sie, welche
    Frist gemeint ist. (Ausdrückliche ARIA-Rollen an `th`/`td` waren der erste Anlauf; die
    HTML-Validierung meldet sie als ungültig.) Je Altersstufe eine Zeile statt eines Satzes
    mit «·».
26. **Die Karte zeigt schmal nur die grossen Orte, dafür lesbar** (unter 600 px 3.4 statt
    2.7 Einheiten → rund 10 statt 8 px; die Liste darunter nennt alle Orte), mit
    Freistellung wie auf jeder Karte: Kreis und Rhein laufen nicht mehr durch die Buchstaben.
27. ~~Das rote Quadrat gehört der Kranbahn-Linie~~ – mit Entscheid 30 entfallen: die
    Kranbahn-Linie war eine eigene Formsprache neben dem Design-System. Geblieben ist der
    runde Auswahlpunkt der Formular-Kacheln (ein Quadrat las sich als Mehrfachauswahl).
28. **Telefon-Symbol auch auf dem Tablet** (600–899 px): dort hatte weder die ausgeschriebene
    Nummer noch die Aktionsleiste unten Platz – die Kopfzeile bot keinen Weg zum Telefon. Der
    Link heisst für Vorleser immer «052 378 22 47 anrufen».
29. **Externe Links sind von hier aus nicht prüfbar**: die Netzwerkrichtlinie dieser Umgebung
    sperrt fedlex.admin.ch, suva.ch, seco.admin.ch, eur-lex.europa.eu, bul.ch und google.com.
    Die Prüfung steht in der Start-Checkliste des Berichts, statt dass sie als «geprüft» gilt.
30. **Die Formsprache ist die des Design-Systems, nicht eine eigene** (Rückmeldung 03.10.:
    «entspricht nicht dem Inexxio Design System», «etwas langweilig»). Das Claude-Design-
    Projekt selbst ist von hier aus nicht lesbar (Anmeldung nötig); sein Export liegt aber im
    Repo – samt **Website-Kit** (`docs/design-system/reference/ui-kit-website/`). Danach
    richtet sich jetzt alles: Inter Tight 800 für Titel (selbst gehostet, auf 700–800
    beschnitten, 32 KB), rote Overlines, Abschnittsköpfe mit 2 px schwarzer Linie und Index
    («01»), Pillen-Knöpfe mit rotem Schein nur beim Zeigen, Karten aus 1-px-Linien, grosse
    rote Schrittziffern, Milchglas-Kopfzeile, ein dunkles Band mit rotem Schein, ein rotes
    Wort je Seitentitel (`==Wort==`). Die frühere «Industrielle Präzision» (2 px Radius,
    Mono-Etiketten, Kranbahn-Linie mit rotem Quadrat) ist entfallen. Overlines auf getöntem
    Grund stehen in der tiefen Rotstufe – das hellere Rot hätte dort 4.2:1 statt 4.5:1.
31. **Der Seitenkopf trägt eine Zahlenreihe – nur aus belegten Fakten** (1982 · alle Marken ·
    rund 1 h Einsatzradius, letzteres weiterhin `[[PRÜFEN]]`). Die Vertrauensleiste darunter
    ist entfallen: sie sagte dasselbe ein zweites Mal.
32. **Beispielbilder statt grauer Rahmen** (Rückmeldung 03.10.). Die Arbeitsumgebung hat
    keinen Zugang zu Bildquellen; ein einmaliger Actions-Job (`.github/workflows/
    sample-photos.yml`) sucht auf Wikimedia Commons nur frei lizenzierte Fotos (CC0,
    gemeinfrei, CC BY, CC BY-SA), schreibt Kontaktbögen zurück, und nach der Auswahl die
    Bilder samt Urheber und Lizenz. 22 Stellen, jede **sichtbar «Beispielbild»**, Alt-Text =
    was wirklich zu sehen ist, Bildnachweis im Impressum (Link im Fuss). Wo eine Person
    gemeint ist (Porträt, Übergabe, Team), zeigt das Beispiel bewusst eine Sache – ein
    fremdes Gesicht unter «Clemens Fritsche» wäre eine erfundene Tatsache. Im Modus `live`
    bricht der Build ab, solange ein Beispielbild steht – genau wie bei einem fehlenden Foto.
33. **«Login» steht in der Kopfzeile** (ab 768 px, schmaler im Menü). Seit die Website «/»
    besitzt, fand man den Weg ins Konto bzw. ERP nur noch im Fuss – und nach der Anmeldung
    landete man wieder auf der Website, ohne jedes Zeichen, angemeldet zu sein (behoben im
    Frontend, `lib/login-target.ts`).

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
| `firebase.json` | `redirects` der alten hs-steiner.ch-Pfade (12 Regeln, Regex, Gross-/Kleinschreibung egal) | alte URLs auffangen (Auftrag Kap. 3.3); Firebase ist die einzige Stelle, die sie ausführen kann |
| `.github/workflows/deploy-dev.yml` | Job «Quality gates (Website)» (Node 22: Tests, astro check, Vokabular, Build mit Prüfungen); der Backend-Deploy wartet darauf | ein Fehler der Website hält den Deploy an, statt live zu gehen |
| `.github/workflows/deploy-dev.yml`, `deploy-prod.yml` | im Frontend-Job: Website **zuerst** bauen (Node 22), danach alles Bisherige unverändert mit Node 20 (auch die Firebase-CLI); nach dem ERP-Build mit `website/scripts/merge-hosting.mjs` in `frontend/out` übernehmen | ohne diesen Schritt hätte die Domain keine Startseite mehr; die Reihenfolge lässt jeden bestehenden Schritt auf seiner Node-Version |
| `CLAUDE.md`, `backend/CLAUDE.md`, `frontend/CLAUDE.md` | Abschnitt «Website», Endpunkt-Zeile, entfernte Seiten | jede Sitzung liest sie zuerst |
| `frontend/src/lib/login-target.ts` (neu), Login-Dialog, `/login`, `/login/verify`, ERP-Layout, Navbar, Footer, Cookie-Hinweis, 404 | Ziel nach der Anmeldung = Startplatz der Rolle (ERP bzw. Konto) statt «/»; harte Navigation; Links auf Website-Seiten als `<a>` | «/» ist seit der Website keine Next-Seite mehr – die Anmeldung endete dort, ohne Weg ins ERP |
| `frontend/scripts/login-target.test.mjs` | neu | Wächter: nie wieder «/» als Ziel, keine fremde Adresse |
| `.github/workflows/sample-photos.yml` | neu: holt Beispielbilder (nur bei Änderung der Anfrage-Datei, schreibt per Commit zurück, löst keinen Deploy aus) | die Arbeitsumgebung erreicht keine Bildquelle |

Nicht angefasst: ERP-Backend (ausser dem Kontakt-Router), Datenbank, Modelle, Migrationen,
ERP-Fachlogik, die globalen Header in `firebase.json`.

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
- [x] **5 – SEO und KI**: Meta, JSON-LD, Sitemap, robots.txt, llms.txt + llms-full.txt, Redirects
      (lokal mit superstatic, der Engine des Firebase-Emulators: 22/22), OG-Bilder, `check-site.mjs`
      (16 Fehlerformen gegengeprüft, jede meldet), Seitenliste `src/lib/pages.ts`
- [x] **6 – Prüfung und Feinschliff** (Ergebnisse im Bericht): Build in beiden Modi – «live»
      bricht an den offenen Markierungen ab, wie verlangt; 24/24 Seiten vollständig ohne JS;
      HTML-Validierung 0 Fehler; axe 0 Verstösse; 0 px Überlauf und 0 zu kleine Klickflächen
      bei 360–2560 px; CLS 0 auf allen Seiten (gedrosselt, schlimmster Fall); Lighthouse mobil
      Leistung 99–100, Barrierefreiheit/Best Practices 100, SEO 100 in der Live-Simulation;
      Formular 30/30 inkl. Störung und ohne JS; Weiterleitungen 16/16; CSP 0 Verstösse;
      Sichtprüfung aller Seiten – 7 Befunde behoben (Entscheidungen 22–28).
      *Nicht prüfbar von hier:* externe Links (Netzwerkrichtlinie), echte Geräte und andere
      Browser-Engines als Chromium.
- [x] **7 – Abschlussbericht** (`WEBSITE_REPORT_20261003.md`) und Deploy (Push auf `develop`)
