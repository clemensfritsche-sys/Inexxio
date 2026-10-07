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
34. **Design-System v3 übernommen** (Auftrag 03.10.: «die ganze Webseite gemäss neuem
    Design-System»). Der neue Claude-Design-Export (v3, Logo-System v3.1) ist ruhiger und
    leichter, und die Website folgt ihm jetzt ohne eigene Abweichung: Titel Inter Tight
    **700/600 statt 800** (Schrift neu auf 600–700 beschnitten, wieder 32 KB), kleinere
    Titelstufen (bis 64 px), Knöpfe und Felder **8 px statt Pille**, Karten 12 px, flach
    (Schatten nur an Kopfzeile und Dropdown), **kein Glow** mehr – der rote Schein im dunklen
    Band entfällt ersatzlos, der rote Knopf bekommt nur beim Zeigen den sehr dezenten
    `--elev-primary`. Fokus in Feldern = schwarzer Ring (Rot bleibt dem Fehler). Die zwei
    Signaturen des Systems stehen je **einmal**: der **Logo-Schwung** unter dem markierten
    Titelwort der Startseite («Ostschweiz») und das **Punktraster** hinter der Textspalte
    des Seitenkopfs. **Logo:** die offizielle Wortmarke ersetzt die selbst gesetzte
    Text-Wortmarke (Platzhalter «finales Logo» erledigt); Zusatz und «ehemals HS Steiner»
    bleiben darunter als Text – im gestapelten Logo wären sie in Kopfzeilenhöhe unlesbar.
    Favicons, Logo-PNG und OG-Bilder neu erzeugt (`scripts/make-assets.mjs`, jetzt mit
    Punktraster statt Kranbahn-Linie). `tokens.mjs` löst die mehrstufigen v3-Verweise auf.

## 3. Änderungen ausserhalb von `website/`

| Datei | Änderung | Warum zwingend |
|---|---|---|
| `frontend/src/styles/design-system/colors_and_type.css`, `docs/design-system/` | Design-System v3 eingespielt (Re-Sync nach `docs/design-system/README.md` §5); alle v2-Namen lösen weiter auf, ERP-Build geprüft | Die Website liest ihre Tokens aus dieser einen Quelle (Entscheid 34) |
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

---

## 7. Umbau v2 (Auftrag Fassung 2 vom 04.10.2026)

> Die Website wurde nach der ersten Fassung des Auftrags gebaut (Abschnitte 1–6 oben). Die
> zweite Fassung (`AUFTRAG.md`) ist ab 04.10.2026 die **einzige** gültige Vorgabe. Dieser
> Abschnitt ist der Abgleich (Phase 0, nur gelesen), die Architekturentscheidung und die
> Checkliste des Umbaus. Arbeitsbranch: `website` (Kap. 2.7) – kein Merge ohne Freigabe.

### 7.1 Was sich am Auftrag geändert hat (Kurzfassung)

| Thema | Fassung 1 | Fassung 2 |
|---|---|---|
| Ausrichtung | zwei Standbeine: Krane · Fahrmischer | **drei Bereiche**: Krantechnik · Fahrzeugtechnik · Sonderlösungen, je mit Lösungen · Service & Reparatur · Ersatz-/Verschleissteile |
| Krane | «HS-Krananlagen» als eigene Seite, Service-Fokus | **Heukrananlagen an erster Stelle**, Neuanlagen aktiv verkaufen, «HS» kein Produktname mehr |
| Abo, Kranbuch | Service-Abo mit drei Stufen, digitales Kranbuch | **entfällt vollständig** |
| Notdienst | «Pikett» | **«Notfall-Service» / «Notfallnummer»**, «Pikett» verboten |
| Name | INEXXIO, Zusatz «Kran- und Fahrmischertechnik» | **INEXXIO AG**, immer «ehemals HS Steiner»; Zusatz entfällt (Weisung 04.10.: Logo mit «ehemals HS Steiner») |
| Header | einzeilig, Ankündigungsleiste darüber | **zweizeilig**: dunkle Servicezeile (36 px) + Hauptzeile (72 px), Mega-Dropdowns mit Foto |
| Konto | nur ein Link «Login» | **Anmeldezustand im Header**, Profilmenü, «ERP» in der Menüleiste; Login/Profil/ERP im selben Design (Kap. 6) |
| Seiten | /krane/*, /fahrmischer/*, /service-abo, /einsatzgebiet | neue URL-Struktur (Kap. 7.1), /service + /service/notfall, Einsatzgebiet auf «Über uns» |
| Ratgeber | 4 Artikel | **3 Artikel** (neu: «Neue Heukrananlage planen») |
| Formular | Kran · Fahrmischer · Teile · Abo · Anderes | **Bereich**: Krantechnik · Fahrzeugtechnik · Sonderlösungen · Teile · Anderes; Skizzen als PDF; Vorausfüllen bei Login |
| Redirects | 12 Regeln auf /krane, /fahrmischer | neue Tabelle (Kap. 14) auf die neuen URLs |

### 7.2 Abgleich – bleibt unverändert

- **Architektur**: Astro 7 als statisches Teilprojekt in `website/`, gleiche Firebase-Site,
  `merge-hosting.mjs` mit Kollisionswächter (Entscheide 1, 2). Kap. 5.2 Variante B.
- **Fundament**: Tokens aus dem Design-System (`tokens.mjs`), selbst gehostete Schriften,
  strenge CSP per `<meta>`, `SITE_MODE`, Platzhalter-System mit `check-content.mjs` →
  `OFFENE_PUNKTE.md`, Seitenliste `lib/pages.ts` mit Build-Wächter, Werte im Fliesstext über
  `{{…}}` (`lib/text.mjs`), `check-site.mjs` (Links, JSON-LD, Titel, H1, Budget …).
- **Komponenten**: Photo (inkl. Bildplatzhalter, Beispielbilder, Bildnachweis), Breadcrumbs,
  Faq (`<details>`), Glance, ScopeList, RelatedLinks, ArticleCard, Sources, Quote, Timeline,
  AreaMap (eigenes SVG), InspectionCheck + InspectionTable (Prüfpflicht-Check), BeforeAfter
  (abgeschaltet), PartCatalog, SeasonNotice, Hero, SectionHead, MobileBar, Reveal, Tracking.
- **Formular-Mechanik**: Haupt- (4 Schritte, ohne JS ein langes Formular) und Kurzformular,
  Validierung im Browser und auf dem Server mit denselben Sätzen, Honeypot, Mindestzeit,
  Rate-Limit, SMTP, Bestätigung, `mailto:`-Rückfall, JSON-Datensatz im Log
  (`backend/app/routers/contact.py`, isoliert, kein ERP-Import).
- **Inhalte, die passen** (übernommen, nur verschoben bzw. sprachlich angepasst):
  Prüfpflicht und Prüffristen, Modernisierung inkl. EU-Maschinenverordnung, Fahrmischer-
  Service und Winter-Revision, Teilekatalog (Datenstruktur schon «ERP-tauglich»), Übergabe
  (Zeitstrahl, Zitat-Platzhalter, Botschaft), Ratgeber «Kranprüfung» und «Verschleissteile»,
  Impressum, Datenschutz, Karriere, Einsatzgebiet-Karte.

### 7.3 Abgleich – wird angepasst

- **`config/site.mjs`**: `brand.legalName` = «INEXXIO AG `[[PRÜFEN: Eintrag im
  Handelsregister]]`», `descriptor` entfällt; `pikett` → `notfall` (gleiche Nummer, neue
  Wörter); `nav` → **`areas`** (drei Bereiche mit Unterseiten, Ebene, Foto, Kurztext) +
  `service`, `ueberUns`, `kontakt` – Navigation, Übersichten, Footer, JSON-LD und llms.txt
  entstehen daraus (Kap. 5.3); `cta` = «Anfrage stellen»; Saison-Hinweise (Jan.–Apr. neu:
  Heukrananlage planen); Footer-Satz; `account` (Pfade `/login`, `/konto`, `/erp`,
  `/abmelden`); `/shop` reserviert (nur in `privatePaths`, keine Seite, kein Link).
- **Header**: zweizeilig (Kap. 7.1): dunkle **Servicezeile** (Ankündigung links per Schalter;
  rechts Notfall · Telefon · ERP · Anmelden/Profilmenü) und weisse **Hauptzeile** mit
  Mega-Dropdowns (Unterseiten, je eine Zeile, «Alle Leistungen …», kleines Foto). Die
  Servicezeile klappt beim Runterscrollen weg. **Deckend weiss statt Milchglas** (Kap. 9.7
  verbietet Glas-Effekte) – das behebt zugleich den gemeldeten Fehler des Mobil-Menüs
  (§7.6, Entscheid 35).
- **Logo** (Weisung 04.10.): das **gestapelte Logo mit «ehemals HS Steiner»**, ohne den
  Zusatz «Kran- und Fahrmischertechnik» (Entscheid 36).
- **Footer**: fünf Spalten (Lockup + Satz · drei Bereiche · Kontakt mit Notfallnummer),
  unterste Zeile © · Impressum · Datenschutz · UID · Anmelden.
- **`layouts/Service.astro`** → Unterseiten-Vorlage nach Kap. 7.5 («Auf einen Blick» mit
  drei Zeilen: Für wen · Was wir tun · Was Sie erhalten; der Ablauf ist kein Pflichtteil
  mehr, sondern seitenspezifisches Modul, wo der Auftrag ihn verlangt).
- **Steps**: wieder mit der **Kranbahn-Linie** (Kap. 9.6), nur als Verbindung von
  Ablauf-Schritten (Entscheid 38).
- **Startseite** (Reihenfolge Kap. 7.3): Hero mit Vertrauensleiste → drei Bereichskarten →
  Übergabe → Warum (4 Belege + Porträt) → Ausgewählte Arbeiten (`enabled: false`) →
  Einsatzgebiet kompakt (Karte) → Ratgeber → Fragen → Abschluss-CTA.
- **Übergabe, Über uns** (nimmt das Einsatzgebiet auf), **Karriere, Kontakt, 404,
  Impressum, Datenschutz** (Konto/Session-Cookie, INEXXIO AG) nach Kap. 7.7.
- **Formular**: Vokabular nach Kap. 11.1 (Bereich → Anliegen, Teile «welches/wofür»),
  Notfallnummer gross bei «Steht still», PDF für Skizzen, Vorausfüllen aus dem Konto,
  Messpunkte `notfall_click` statt `pikett_click`, `abo_interest` entfällt, `form_submit`
  mit Bereich. Backend: Abo-Zweig raus, PDF erlaubt, Notfall-Satz statt Pikett-Satz.
- **SEO/KI**: Titel, Beschreibungen, Suchbegriffe je neue Seite (Kap. 12.2), OG-Bild je
  Bereich, `hasOfferCatalog` aus den drei Bereichen, `Product` für Heukrananlagen,
  `robots.txt` sperrt Konto- und ERP-Pfade in **beiden** Modi, llms.txt mit drei Bereichen.
- **Weiterleitungen** (`firebase.json`): Tabelle aus Kap. 14 (Entscheid 40).
- **Prüfskripte**: «Pikett» in die Liste verbotener Wörter, neue ERP-/Konto-Pfade, alte
  Seiten-URLs als «darf nicht mehr existieren», höchstens drei Kranbahn-Linien je Seite.
- **Konto, Profil, ERP im Next-Frontend – nur Darstellung** (Kap. 6.2, Phase 3): Kopf und
  Fuss (`components/layout/navbar.tsx`, `footer.tsx`) bekommen dieselbe Struktur und
  dieselben Inhalte wie die Website (heute: altes Logo, «Präzisionsfertigung», falsche
  Telefonnummer); Anmeldedialog mit dem neuen Logo. Logik, Validierung und Datenfluss
  bleiben unverändert (Entscheid 39).

### 7.4 Abgleich – wird neu gebaut oder entfernt

**Neu**

| Was | Wo |
|---|---|
| Bereichsseiten mit gleicher Struktur (Kap. 7.4) | `/krantechnik`, `/fahrzeugtechnik`, `/sonderloesungen` |
| Unterseiten | `/krantechnik/heukrananlagen`, `/krantechnik/industriekrane`, `/fahrzeugtechnik/aufbauten-reparatur`, `/sonderloesungen/konstruktion-engineering`, `/sonderloesungen/schweiss-stahlbau`, `/sonderloesungen/baumaschinen` |
| Verschoben (Inhalt übernommen) | `/krane/pruefung-wartung` → `/krantechnik/pruefung-wartung`, `/krane/modernisierung` → `/krantechnik/modernisierung`, `/fahrmischer/service-reparatur` → `/fahrzeugtechnik/fahrmischer`, `/fahrmischer/verschleissteile` → `/fahrzeugtechnik/verschleiss-ersatzteile` |
| Service | `/service` (vier Kacheln nach Anliegen), `/service/notfall` |
| Ratgeber | «Neue Heukrananlage planen: Bauformen, Platzbedarf, Ablauf» |
| Komponenten | Servicezeile mit Anmeldezustand und Profilmenü, Mega-Dropdown, Bereichskarte, «Drei Ebenen», Kranbahn-Linie |
| Skript | `scripts/account.ts` – liest den Anzeige-Cache (Schnittstelle S1/S2), setzt Profilmenü und ERP-Punkt, sonst bleibt «Anmelden» |
| Next-Frontend | Route `/abmelden` (Schnittstelle S3) |

**Entfernt** (vollständig – Seite, Inhalt, Komponente, Konfiguration, Links)

`/krane`, `/krane/reparatur` (Inhalt geht in Industriekrane und Notfall-Service),
`/krane/hs-krananlagen` (→ Heukrananlagen), `/fahrmischer`, `/service-abo` samt
`config/abo.mjs`, `content/service-abo.ts`, `TierCards`, `KranbuchIllustration` und allen
Abo-/Kranbuch-Texten, `/einsatzgebiet` (→ «Über uns»), Ratgeber «Kranfachmann oder
Kranexperte» (die Definition wandert in den Prüf-Artikel) und «Heukran-Saison-Check» (der
Saison-Check bleibt als Abschnitt auf «Heukrananlagen»), `Announcement` + `announce.ts`
(→ Servicezeile), `EntryTiles` auf der Startseite (die vier Anliegen-Kacheln stehen jetzt auf
`/service`), die Zahlenreihe im Hero (Kap. 7.3 verlangt die Vertrauensleiste), der
Formular-Typ «Abo» mit dem Feld «Anzahl Krane», alle Wörter «Pikett».

### 7.5 Architektur und Schnittstellen zum ERP

**Variante B bleibt** (Kap. 5.2). Variante A schied schon in Fassung 1 aus: das Next-Frontend
liefert zwar statisches HTML, lädt aber auf jeder Seite das React-Laufzeitpaket (≈ 90 KB
gzip, Budget 30 KB). Für die Einbettung von Login, Profil und ERP muss **nichts** an der
Architektur geändert werden – darum kein Halt nach Kap. 2.

**Wie das Konto heute funktioniert** (gelesen): Anmeldung über Firebase (Magic Link, Google,
Passkey), Persistenz `browserLocalPersistence` – der Anmeldezustand liegt **im Browser**, eine
Server-Session gibt es nicht. Das Backend prüft je Anfrage ein Firebase-ID-Token
(`Authorization: Bearer`). Die Rolle kommt aus `GET /api/v1/auth/me`; «ERP» heisst
`isStaff(role)` = `admin` oder `employee` (`frontend/src/lib/record-status.ts`, Spiegel von
`people.STAFF_ROLES`). Routen: `/login` (+ `/login/verify`), `/konto`, `/erp`; der Schutz von
`/konto` und `/erp` liegt in deren Layouts (Redirect auf `/login`) und im Backend.

**Warum keine Server-Schnittstelle `GET /api/session/me`** (Kap. 6.3 nennt sie als Beispiel):
eine statische Seite hat kein Token. Sie müsste entweder das Firebase-SDK laden (≈ 60 KB gzip
auf **jeder** öffentlichen Seite – doppeltes Budget) oder das Backend müsste ein
Session-Cookie ausstellen (eine Änderung an Auth-Logik und Sessions – Kap. 2.3). Beides
verletzt einen Grundsatz. Es gibt aber **schon** eine Schnittstelle, die genau die Frage
beantwortet («wer ist angemeldet, darf er ins ERP?»):

| # | Schnittstelle | Art | Was | Änderung am ERP |
|---|---|---|---|---|
| S1 | Anzeige-Cache `localStorage['inexxio_user_role']` und `['inexxio_user_fullname']` (gleiche Domain) | **besteht**, rein lesend | Das ERP-Frontend schreibt ihn nach jeder Anmeldung und bei jedem Laden von Konto/ERP (Anmeldedialog, `/login/verify`, Navigation, ERP-Layout, Konto) und löscht ihn beim Abmelden. Die Website liest daraus Name/Initialen und «ERP ja/nein» – nichts anderes. | keine |
| S2 | Anzeige-Cache `localStorage['inexxio_user_contact']` = `{ email, phone, company }` | **neu, additiv** | Für das Vorausfüllen des Formulars (Kap. 11.1). Geschrieben an **derselben** Stelle, an der die Navigation schon Rolle und Name aus `/auth/me` speichert; gelöscht mit ihnen. | eine Zeile schreiben, eine löschen |
| S3 | Route `/abmelden` (Next) | **neu, additiv** | Die Website kann ohne Firebase-SDK nicht abmelden; der Menüpunkt «Abmelden» führt dorthin, die Seite ruft das **bestehende** `logout()` und kehrt zu «/» zurück. `logout()` räumt dabei den Anzeige-Cache (bisher tat das nur der Listener der Navigation). | neue Seite; `logout()` löscht drei Anzeige-Schlüssel |

Die Website **zeigt** die Berechtigung nur an (Kap. 6.3): Wer den Cache von Hand fälscht, sieht
einen Menüpunkt «ERP», den `/erp` und das Backend trotzdem abweisen. Fehlt der Cache, ist er
unlesbar oder ist JavaScript aus, steht «Anmelden» da – der Platz ist reserviert, nichts
springt. Kein Token, keine ID verlässt das ERP-Frontend. Der Spiegel (Schlüsselnamen,
Staff-Rollen) ist getestet (`scripts/account.test.mjs` gegen die Frontend-Quellen).

### 7.6 Sofortpunkte (Rückmeldung 04.10.)

1. **Logo mit «ehemals HS Steiner»** – siehe Entscheid 36.
2. **Burger-Menü mobil funktionierte nicht** – gemessen: das Menü öffnete, war aber nur
   **60 px** hoch (so hoch wie die Kopfzeile). Ursache: `backdrop-filter` (Milchglas) macht
   die Kopfzeile zum Bezugsrahmen für `position: fixed` darin; das Vollbild-Menü war damit in
   ihr eingesperrt. Entscheid 35.

### 7.7 Entscheidungen des Umbaus

35. **Kopfzeile deckend weiss, Einklappen ohne `transform`**: Glas-Effekte verbietet Kap. 9.7,
    und `backdrop-filter` wie `transform` sperren jedes `position: fixed` darin ein (der
    gemeldete Fehler). Die Servicezeile klappt über den Sticky-Versatz (`top`) weg, nicht über
    eine Verschiebung – so kann das Vollbild-Menü nie wieder in der Kopfzeile landen. Ein
    Wächter in `check-site` misst die Menühöhe nicht, darum steht die Regel als Kommentar am
    Ort und im Browser-Test des Berichts.
36. **Logo = das gestapelte Logo mit «ehemals HS Steiner»** (Weisung 04.10.: «dann lieber
    das ‹Kran- und Fahrmischertechnik› weglassen, damit genügend Platz ist»). Der Zusatz
    entfällt überall (Kopf, Fuss, OG-Bild); «ehemals HS Steiner» steht damit im Zeichen
    selbst und im zugänglichen Namen des Logos.
37. **Formsprache bleibt die des Design-Systems v3** (8 px Radien, Karten 12 px, flach):
    Kap. 9.4 nennt 2 px, Kap. 9.1/9.2 verlangen zugleich das bestehende Design-System und
    dass Website und Konto «wie aus einem Guss» wirken – und Konto und ERP stehen im
    Design-System. Zwei Radien für dieselbe Marke wären zwei Formsprachen (Entscheid 30, 34).
38. **Die Kranbahn-Linie kommt zurück – nur als Verbindung der Ablauf-Schritte** (Kap. 9.6
    und 7.4 verlangen sie dort ausdrücklich). Als Sektionstrenner nicht: das Design-System
    erlaubt als Zierde nur Logo-Schwung und Punktraster, und drei Signaturen wären keine mehr.
    Höchstens eine je Seite; `check-site` erlaubt drei.
39. **Kopf und Fuss des Konto-/ERP-Bereichs werden nachgebaut, nicht geteilt**: Astro und
    React können keine Komponente teilen. Damit sie nicht auseinanderlaufen, kommen **alle
    Inhalte** (Bereiche, Unterseiten, Telefon, Notfallnummer, Adresse, Öffnungszeiten,
    Footer-Satz, Pfade) aus einer generierten Datei (`scripts/export-contact.mjs` →
    `frontend/src/lib/site-shell.json`), die die CI schon heute auf Aktualität prüft
    (derselbe Schritt wie das Formular-Vokabular). Nur Darstellung – kein Zustand, keine
    Logik der Navigation wird geändert.
40. **Weiterleitungen: Tabelle aus Kap. 14, ohne «alles andere → /»**: Firebase führt
    Weiterleitungen **vor** den statischen Dateien aus – eine Regel für «alles andere» auf
    derselben Site würde jede Seite der neuen Website auf die Startseite umleiten. Sie gehört
    auf die **alte** Domain: beim Domainwechsel bekommt hs-steiner.ch eine eigene, kostenlose
    Hosting-Site mit derselben Tabelle plus Fangregel (Launch-Checkliste). `/kontakt` wird
    nicht umgeleitet: der Pfad ist alt wie neu derselbe (eine Regel darauf wäre eine
    Schleife).
41. **Neue Bildstellen ohne Beispielbild** (Industriekran, Aufbau, Schweissarbeit,
    Konstruktion): bis echte Fotos vorliegen, zeigt der Bildplatzhalter die Beschreibung –
    so wie Kap. 9.5 es vorsieht. Neue Beispielbilder müsste der Actions-Job holen; das wäre
    ein zusätzlicher Zwischenstand, den der Fototag ohnehin ersetzt.
42. **Die Dropdowns im Konto-/ERP-Kopf tragen kein Foto.** Die Fotos der Website sind
    von Astro optimierte Dateien mit wechselnden Namen; das Next-Frontend kennt sie nicht.
    Eine Kopie nur für ein 220-px-Vorschaubild wäre eine zweite Bildverwaltung. Die Listen
    (Unterseite + eine Zeile Beschreibung + «Alle Leistungen …») sind dieselben.
43. **Das Logo des Konto-/ERP-Bereichs ist ein Abdruck, kein zweites Original**:
    `export-contact.mjs` kopiert die beiden SVG aus `public/logo/` nach
    `frontend/public/brand/`, die CI prüft wie beim Vokabular, dass sie gleich sind. So ist
    das Logo auch beim lokalen Arbeiten am Frontend da, und ändern kann man es nur an
    einer Stelle. Das alte `frontend/public/logo.png` ist gelöscht.
44. **Der Logo-Schwung unter dem Titelwort ist einfarbig** – der Design-System-Export
    hatte dort einen Verlauf in Rot, Kap. 9.7 verbietet Farbverläufe, und im Logo selbst
    ist der Schwung einfarbig.
45. **Drei Befunde der Prüfung (Phase 7) behoben**, je eine Zeile: Ablauf-Text auf dunklem
    Grund war dunkelgrau (Kontrast 2:1), die Nummer auf der Bereichskarte stand weiss auf
    hellem Bild (1.5:1, jetzt eigener dunkler Grund), und die Dachzeile im Seitenkopf
    durfte nicht umbrechen (+25/+30 px bei 360 px). Im Frontend: der AGB-Titel lief bei
    320–375 px seitwärts über, der Cookie-Hinweis nannte einen «Warenkorb», den es nicht
    gibt. Den AGB-Text selbst (Shop, `info@inexxio.com`) fasse ich nicht an – das ist
    Rechtstext und steht als offener Punkt im Bericht.
46. **Ein Teilen-Bild je Bereich** (`og/krantechnik.png` usw.), Titel als `ogTitle` an
    den Bereichen in `site.mjs`; das ungenutzte Feld `og` (= die ID) ist dafür entfallen.
    `check-site` prüft jetzt, dass jedes Bild, auf das Meta-Angaben oder JSON-LD zeigen,
    im Build liegt – ein fehlendes fiele sonst erst beim Teilen auf.
47. **Arbeitsleiste statt ERP-Knopf** (Rückmeldung 04.10.2026): eine schmale Leiste über
    dem Kopf, nur für Personal – «ERP» und die fünf Datensatztypen (`/erp?typ=…` stellt im
    Feed den Filter vor). Servicezeile, Profilmenü und Mobil-Menü tragen kein ERP mehr.
    Inhalt in `site.mjs` (`account.workbar`), Website und Konto lesen dieselbe Liste. Sie
    scrollt weg, sticky bleibt der Kopf – darum ändert sich keine Kopfhöhe.
48. **Testnotizen auf der Website = dasselbe Werkzeug wie im ERP**, kein Nachbau:
    `frontend/scripts/build-islands.mjs` bündelt `FeedbackPin` zu `/islands/feedback.js`
    (nur in der Testumgebung gebaut, Stile auf `#ix-feedback` begrenzt). Die Website lädt es
    nur mit `SITE_FEEDBACK=on` (allein im Dev-Deploy) und nur für Angemeldete; nur dann
    erlaubt ihre CSP zusätzlich die Google-Dienste der Anmeldung. ~95 KB gzip, die kein
    Besucher je lädt.
49. **Dev wird nie indexiert**: der Dev-Deploy hängt an jede Antwort `X-Robots-Tag: noindex,
    nofollow, noarchive` (Website, Konto, ERP, Bilder, PDFs) und bricht ab, falls die Zeile
    fehlt. Prod liest dieselbe `firebase.json` ohne sie. Unabhängig davon bleibt der
    Vorschau-Modus (`noindex`-Meta, gesperrte `robots.txt`).
50. **Testnotizen #1060–#1094 (04.10.2026) – der Kopf ist EINE Zeile.** Vorschau-Banner,
    Servicezeile und Arbeitsleiste sind **aus dem Code gelöscht**. ERP ist für Personal ein
    gewöhnlicher Hauptmenüpunkt (Dropdown neben «Kontakt», `account.erp`); Telefon,
    Anmelden/Profilmenü und «Anfrage stellen» stehen in der Hauptzeile. *Entscheid 47
    (eigene Arbeitsleiste) ist damit abgelöst.* Die Ankündigung «HS Steiner heisst jetzt
    INEXXIO» ging mit der Servicezeile.
51. **Eine Telefonnummer für alles.** `site.notfall` und `features.notfall` sind entfallen;
    der Notfall-Service bleibt als Seite und nennt die eine Nummer. **Öffnungszeiten**
    stehen nirgends mehr (auch nicht in JSON-LD).
52. **Kein Einsatzgebiet mehr, das uns begrenzt.** «Wo wir arbeiten»: zuhause in
    Tuttwil-Wängi, im Einsatz in der ganzen Schweiz und weltweit (`site.area`). Die
    Regionenliste, der 1-Stunden-Kreis und `areaServed` sind entfallen; die Karte heisst
    jetzt `LocationMap` und zeigt nur noch den Standort (Kontaktseite, Über uns).
53. **Keine laufenden Nummern «01/02»** an Abschnitten, Karten, Hero und Aufzählungen ohne
    Reihenfolge. Geblieben sind sie dort, wo sie eine Reihenfolge sagen (Formular-Schritte,
    Ablauf, nächste Schritte).
54. **FAQ: immer nur eine Antwort offen** – `<details name>` je FAQ-Block, mit kleinem
    Rückfall-Skript für ältere Browser.
55. **Die Startseite spiegelt die Unterseiten – eine Antwort an einer Stelle.**
    `uebergabe.ts` hält `handoverLead`, `heiriQuote` (Entwurf, markiert bis zur Freigabe
    durch Heiri) und `sharedFaq`; Startseite und Übergabe-Seite lesen sie. «Nicht mehr im
    Angebot» ist entfallen; die alten Garten-/Reifen-Pfade leiten still auf `/uebergabe`.
56. **Kontaktdaten aus dem ERP** (Testnotiz #1094): `GET /api/v1/public/contact` (Backend,
    rein lesend, ohne Anmeldung) liefert Telefon, E-Mail und Anschrift der Gesellschaft zum
    Land des Besuchers (IP → Land über DB-IP Lite im Docker-Build, dann
    `sites.company_for_country`; ohne Treffer der Betreiber). **Beim Build** holt
    `scripts/erp-contact.mjs` (mit `SITE_API`) die Angaben des Betreibers als Vorgabe ins
    HTML; **zur Laufzeit** tauscht `src/scripts/contact.ts` sie nach Wert aus –
    Impressum und Datenschutz ausgenommen. Konto/ERP-Fuss liest dieselbe Antwort. Die
    IP-Adresse wird nicht gespeichert; Datenschutz und DB-IP-Nachweis stehen in
    `datenschutz.md`.
57. **EIN Kontaktbereich, EIN Formular** (Testnotizen #1102/#1107/#1129): `ContactSection`
    steht auf /kontakt (mit der H1) und am Ende jeder Seite – dieselbe Überschrift, derselbe
    Satz, dasselbe Formular in drei Schritten. Das Kurzformular ist entfallen, und einen
    Schritt «Bereich» gibt es nicht mehr: das **Anliegen** sagt, worum es geht
    (`inquiry.kindOf`), der Server leitet den Bereich daraus ab und glaubt keinen
    mitgeschickten. Je Seite ist höchstens das passende Anliegen vorgewählt.
58. **Kranservice defensiv** (Rückmeldung 04.10.2026: «ich möchte nicht lügen»): Schwerpunkt
    sind die HS- und die eigenen Krananlagen, Krane anderer Hersteller «auf Anfrage». Keine
    Aussage «aller Marken/Hersteller» bei Kranen und kein Ersatzteillager für fremde Krane;
    Ersatzteile nur für HS-Anlagen («an Lager oder neu gefertigt»). Bei Fahrmischern bleibt
    «alle gängigen Marken».
59. **ERP ist ein Link, kein Menü** (#1106); das Profilbild aus dem ERP steht im Profilknopf
    (#1105, vierter Schlüssel `inexxio_user_photo` im Anzeige-Cache); die UID steht nur noch
    im Impressum (#1103); ein Bild je Unterpunkt im Mega-Dropdown, so hoch wie das Panel
    (#1111, reines CSS über `:has`).

60. **EIN Kopf und EIN Fuss für Website UND Konto/ERP** (Rückmeldung 04.10.2026: «Ein
    Header für beides. Eine globale Funktion, Logik, Design.»). Der React-Nachbau
    (`navbar.tsx`, `footer.tsx`) ist **gelöscht**. Der Website-Build schreibt Kopf- und
    Fuss-HTML, Skripte und sein Stylesheet (auf `.ix-shell` beschränkt, damit es im ERP
    nur Kopf und Fuss trifft) nach `dist/_shell/` (`scripts/export-shell.mjs`); das
    Frontend übernimmt es beim Bauen (`frontend/scripts/site-shell.mjs`, im Deploy Pflicht
    über `SHELL_REQUIRED=1`) und setzt es im Wurzel-Layout ein. Dasselbe Skript
    (`window.inexxioShell`) bedient beide Seiten; das Frontend schreibt nur den
    Anzeige-Cache (`account-sync.tsx`). **Anmelden ist damit überall der Link auf
    `/login?from=…`** – nach der Anmeldung und beim Danebenklicken geht es dorthin
    zurück. AGB und Cookie-Einstellungen stehen im gemeinsamen Fuss.
61. **Das Profilbild fehlte auf der Website, weil die CSP es blockierte** (#1139): das
    `<meta>`-CSP der Website erlaubte für Bilder nur `'self' data:`. Es liest `img-src`
    jetzt aus `firebase.json` (`src/lib/csp.mjs`) – EINE Quelle für beide Teile.
62. **Das Anfrage-Formular ist ein Feld** (Rückmeldung 04.10.2026): «Ihr Anliegen»,
    Anhänge (freiwillig) und «wer fragt an» (für Angemeldete vorbelegt). Bereich, Anliegen,
    Dringlichkeit, Kontaktweg, Schritte und Fortschritt sind **aus Code und Logik
    entfernt** – auch im Endpunkt (`inquiry/3`): ein mitgeschicktes Altfeld wird ignoriert.
    Die Auswertung der Anfrage soll später eine KI übernehmen; dafür genügt der Text.
    *Entscheid 57 ist damit abgelöst.*
63. **/kontakt ist ein Abschnitt** (#1142–#1145): «Wie finden Sie uns» ist im Kontaktbereich
    aufgegangen – Karte (nur grössere Städte) und Anschrift stehen neben dem Formular, die
    Route öffnet **Google Maps in einem neuen Tab** (Ziel = Anschrift aus dem ERP). Kein
    eingebettetes Google-Maps-Fenster: kostet API und Einwilligung und bricht bei Ausfall.
64. **Der Ort kommt aus dem ERP** (#1146/#1153): `{{erp.city}}` setzt den Ort der Anschrift
    beim Build ein und lässt `contact.ts` ihn zur Laufzeit ersetzen – wie Telefon und
    E-Mail. «Über uns» spricht als **Wir**, nicht über eine Person.
65. **Jede Seite der Sitemap ist über das Menü erreichbar** (#1154): `check-site.mjs`
    bricht ab, wenn eine indexierte Seite nicht im Kopf verlinkt ist (ausgenommen Start,
    Impressum, Datenschutz und einzelne Ratgeber-Artikel, die über die Übersicht laufen).
    «Über uns» ist dafür ein Dropdown mit Übergabe, Ratgeber und Karriere.
66. **Testnotizen gehen beim Seitenwechsel mit** (Rückmeldung 04.10.2026): die Insel
    `/islands/feedback.js` hat keinen Hash im Namen, und `firebase.json` cacht `.js` ein
    Jahr – der Browser hielt eine alte Fassung. Sie wird jetzt mit dem Stand geladen
    (`?v=<Commit>`, `body[data-feedback]`).

67. **Keine gelben Vermerke mehr** (Rückmeldung 04.10.2026: «vollständig eliminieren»):
    `[[PRÜFEN: …]]`/`[[PLATZHALTER: …]]` sind samt Mechanik entfernt (`text.mjs`, `.mk`,
    Quellen-Prüfung in `check-content.mjs`). Was nicht feststeht, steht nicht da – leere
    Werte (UID, LinkedIn, Stellenanzeige, Projekte, Preisrahmen) sind gestrichen, nicht
    ersetzt. Offen bleibt allein die Fotoliste (`OFFENE_PUNKTE.md`).
68. **Bauformen der Heukrane als Illustration** (Claude-Design-Export «Krantypen»): vier
    statische SVGs (`src/assets/illustrations/heukran-*.svg`, `CraneForm.astro`), inline –
    kein Bild-Request, kein JavaScript. Je Bauform eine Zeile: Bild gross links, rechts
    «So arbeitet sie», darunter «Passt, wenn …» (#1186). Die vier Fotowünsche dafür sind
    entfallen.
69. **Die Standortkarte steht in JEDEM Kontaktbereich** (#1162/#1181), nicht nur auf
    `/kontakt`. Ohne `id` im SVG (Name über `aria-label`), weil sie auf einer Seite zweimal
    vorkommen kann.
71a. **Logo aus dem Logo-System v3.2** (#1184, Claude-Design-Export 04.10.): gestapelte Fassung mit «ehemals HS Steiner» in hell/dunkel/rot ersetzt die bisherige (Seitenverhältnis 4618 : 2256); Herkunftsdaten (C2PA) entfernt, PNG und OG-Bilder neu erzeugt.
70. **Marken als Referenz-Band** (#1185): je Marke eine Kachel. Liegt ein Logo in
    `src/assets/marken/<name>.svg`, erscheint es, sonst der Schriftzug – Logo-Dateien
    müssen geliefert werden (Markenrecht, keine Quelle im Repo).
71. **Werte auf /ueber-uns** (#1182): Qualität · Verlässlichkeit · Ehrlichkeit ·
    Verantwortung – vor den Zusagen, die sie prüfbar machen.

### 7.7a Strategie-Umbau (06.10.2026)

72. **Der Strategiekern** (vorher kurzzeitig `STRATEGIE.md`, am 07.10.2026 gelöscht – dieser
    Plan ist die eine Quelle): Servicebetrieb mit eigenen Produkten. **Krantechnik** –
    Fokus Industrie-/Gewerbe-KMU der Ostschweiz sowie Häfen, Segelclubs, Gemeindehäfen und
    Werften; Kernangebot ist der Kranservice (Entscheid 83); bestehende Heukrane betreuen,
    Neuanlagen wie bisher. **Fahrzeugtechnik** – Fahrmischer-Service für alle gängigen
    Marken, Verschleissteile ohne «ab Lager», Trommeltausch als erstes eigenes Produkt.
    **Sonderlösungen** bleiben als dritter Bereich. Werte: Handschlagqualität, Qualität,
    Zuverlässigkeit, Innovation, Design. Markt: zuerst D-A-CH. **Bewusst nicht:** kein
    Preiskampf mit Katalog-Kranen; Hafenkrane über 15 t sind intern nicht im Fokus (steht
    nicht auf der Website); keine Beträge, solange die Jahrespreise nicht kalkuliert sind;
    keine erfundenen Referenzen.
73. **Service-Vertrag statt «Abo/Kranbuch entfällt»** (löst AUFTRAG v2 an dieser Stelle ab):
    neue Seite `/krantechnik/service-vertrag`, drei Stufen Basis · Plus · Voll
    (`ContractTiers.astro`, auch auf der Startseite). **Kein Betrag** – die Fixpreise sind
    noch nicht kalkuliert.
74. **Häfen & Werften** als neue Seite `/krantechnik/haefen-werften` (Boots- und Mastkrane,
    Bootslifte, «Das Hafenjahr»). Die interne Grenze «über 15 t nicht im Fokus» steht nicht
    auf der Website.
75. **Trommeltausch ist das erste eigene Produkt**: `/fahrzeugtechnik/trommeltausch`, erste
    Unterseite und Titel der Fahrzeugtechnik. **«Ab Lager» ist überall entfernt** – es gibt
    kein Lager.
76. **Entscheid 58 gelockert**: Kranservice herstellerunabhängig; kein «alle Hersteller»,
    jeder Kran wird zuerst angeschaut, Teile werden im Einzelfall geklärt.
77. **«Neu» markiert ein Angebot, nie eine Kompetenz** (Rückfrage beantwortet):
    `badge` an der Unterseite in `site.mjs` → Menü, Fuss, Karten. Heute nur Service-Vertrag
    und Häfen & Werften; Industriekrane nicht. Keine erfundenen Referenzen.
78. **Claim, Pfeiler, Werte** aus `STRATEGIE.md`: «Hebetechnik mit Handschlagqualität.»,
    Pfeiler Passt · Läuft · Ohne Investition (Startseite), Werte Handschlagqualität ·
    Qualität · Zuverlässigkeit · Innovation · Design (löst Entscheid 71 ab), Markt D-A-CH.
79. **DEV-Marke im Kopf** nur bei `SITE_ENV=dev` (gesetzt allein in `deploy-dev.yml`); über
    den gemeinsamen Kopf gilt sie auch für Konto und ERP. Prod bleibt ohne.
80. **#1191**: der rot-graue Aktivierungspunkt an den Karten der Startseite ist samt CSS
    entfernt.

### 7.7b Rückmeldung zum Strategie-Umbau (07.10.2026)

81. **Claim zurück** auf «Krantechnik, Fahrzeugtechnik und Sonderlösungen aus der Schweiz»
    (H1, `brand.claim`, Fuss, OG) – «Hebetechnik» ist zu eng. `brand.promise` entfällt.
82. **Pfeiler-Abschnitt entfernt** – er überschnitt sich mit «Warum INEXXIO».
83. **Kranservice statt Service-Vertrag** (löst 73 ab): `/krantechnik/service-vertrag` und
    `/krantechnik/pruefung-wartung` sind EINE Seite `/krantechnik/kranservice` – Name und
    Adresse sagen dasselbe (Entscheid 89).
    Auf Abruf · Pflicht · Pflege · Rundum, dargestellt als Tabelle «was kann was»
    (`ServicePlans.astro`, `content/krantechnik.ts → servicePlans`; `from` = ab welchem
    Paket eine Leistung gilt). Die Startseite zeigt nur die Kurzform.
84. **Trommeltausch ohne eigene Seite** (löst 75 ab): `/fahrzeugtechnik/trommeltausch` ist in
    `/fahrzeugtechnik/fahrmischer` aufgegangen – Vergleich Revision · Tausch · Neukauf
    (`#trommel`), Product-JSON-LD dort.
85. **«Erweitert» statt «Neu»** (löst 77 ab), Klasse `.badge-ext`.
86. **DEV als Eckband** (löst 79 ab): 45° oben rechts, `position: fixed`, Klicks gehen
    hindurch; auf dem Telefon kleiner.
87. **Doppelspurigkeiten bereinigt**: «Wo wir arbeiten» stand auf Start und /service neben
    dem Kontaktbereich, der die Karte schon trägt – entfernt (bleibt auf «Über uns», dort
    ohne den doppelten Satz «Werkstatt steht in …»). «So arbeiten wir» (/service) und
    «Zusagen» (Über uns) sind EINE Liste. Die Antworten «Krane anderer Hersteller» (vorher
    widersprüchlich: «nur auf Anfrage» ↔ «unabhängig vom Hersteller») und «Wie schnell bei
    einem Stillstand» stehen einmal in `sharedFaq`. Doppelte FAQ zwischen Bereichs- und
    Unterseiten sind entfernt.
88. **Aufräumen**: `Btn.astro` (ohne Aufrufer), CSS ohne Verwendung (`.btn--dark`,
    `.btn--block`, `.cols-4`, `.link-quiet`, `.stack*`, `.start-7/8`, `.swoosh`, `.select`,
    `.no-print`, `.field--narrow`, `.mnav__more`), Exporte ohne fremden Leser, das Foto
    `trommeltausch`. OG-Bilder mit den neuen Bereichstiteln neu erzeugt.

### 7.7c Konsolidierung (07.10.2026)

Rückmeldung: «relativ viele Seiten» – zusammengelegt wurde nur, wo zwei Seiten dieselbe
Geschichte erzählten oder eine Seite keinen eigenen Inhalt hatte. **29 → 24 Seiten.** Auf
alte Adressen wird keine Rücksicht genommen (Dev-Umgebung); die Weiterleitungen der alten
hs-steiner.ch-Pfade zeigen auf die neuen Ziele.

89. **Name = Adresse**: «Kranservice» liegt unter `/krantechnik/kranservice`.
90. **Sonderlösungen ist EINE Seite** (`/sonderloesungen`, Vorlage der Unterseiten): die
    drei Unterseiten Konstruktion · Schweiss-/Stahlbau · Baumaschinen waren dünn und
    stellten dieselben Fragen. Im Menü ist Sonderlösungen ein einfacher Link; ein Bereich
    ohne Unterseiten wird überall so behandelt (Kopf, Fuss, Startseite, JSON-LD, llms.txt).
91. **Service und Notfall sind EINE Seite** (`/service`, Notfall unter `#notfall`): die
    Übersicht hatte ausser Kacheln keinen eigenen Inhalt. Im Menü ein einfacher Link – das
    frühere Untermenü wiederholte nur Links der Bereiche.
92. **Die Übergabe steht auf «Über uns»** (`/ueber-uns#uebergabe`): dort stand dieselbe
    Geschichte schon als Kurzfassung. Die Startseite zeigt Satz, Zitat und den Link, die
    Listen «Was bleibt / was neu ist» stehen nur noch auf «Über uns».
93. **Bereichsseiten ohne «Drei Ebenen»**: sie verlinkten dieselben Unterseiten wie die
    Karten darunter (`Levels.astro` entfernt).
94. **Bewusst NICHT zusammengelegt**: die Krantechnik-Unterseiten (je eigene Zielgruppe und
    Suchanfrage), Fahrmischer · Aufbauten · Verschleissteile (verschiedene Kunden, der
    Teilekatalog braucht eine eigene Seite), Ratgeber (Suche), Karriere (eigene Absicht),
    Kontakt und Rechtliches.

**Seitenplan (Stand 07.10.2026, mit §7.7d/e: 24 Seiten)**

| Bereich | Seiten |
|---|---|
| Start | `/` |
| Krantechnik | `/krantechnik` · `/kranservice` · `/industriekrane` · `/haefen-werften` · `/heukrananlagen` · `/anschlagmittel` |
| Fahrzeugtechnik | `/fahrzeugtechnik` · `/fahrmischer` · `/aufbauten-reparatur` · `/verschleiss-ersatzteile` |
| Sonderlösungen | `/sonderloesungen` |
| Service | `/service` |
| Unternehmen | `/ueber-uns` · `/karriere` · `/kontakt` (+ `/kontakt/danke`, noindex) |
| Ratgeber | `/ratgeber` + drei Artikel |
| Rechtliches | `/impressum` · `/datenschutz` (+ `/agb` im ERP-Frontend, `/404`) |

### 7.7d Drei Versprechen und INEXXIO 365 (07.10.2026)

Strategie: INEXXIO verkauft Mehrwert – Lösung nach Mass, zuverlässiger Betrieb, planbare
Kosten – bei kleinem Risiko für den Kunden. Krantechnik ist das Wachstumsfeld, die
Fahrzeugtechnik (Trommeltausch, Fahrmischer) die Cash-Quelle und tritt nicht zurück.

95. **Drei Versprechen, nie vermischt** (`content/promises.ts`, die EINE Quelle):
    ① *Service testen* – «Der erste Kranservice ist gratis.» (einmal pro Kunde, Material
    wird verrechnet, nur Service/Wartung, keine Prüfung, nur Krane aller Marken) ·
    ② *Kaufen mit Garantie* – «Nicht zufrieden? Sie zahlen nur die Hälfte.» (ganzer Preis,
    ohne Einschränkung, auf alles, was man kauft) · ③ *INEXXIO 365* – «Ihr Kran läuft –
    oder Sie zahlen nicht.» Für alles: Fixpreis vor jeder Arbeit, keine Mindestlaufzeit,
    Zweitmeinung gratis. Keine Preise, keine Kranklassen, keine erfundenen Bedingungen.
96. **EIN Bauteil** (`Promises.astro`): Startseite alle drei, direkt nach dem Hero; jede
    Seite nennt in `promises` die, die für sie gelten (Vorlage der Unter- und
    Bereichsseiten). Grosse Zahl als Anker (0.– · 50 % · 365), Rot nur als Linie darüber.
    Ein einzelnes Versprechen steht als Zahl links, Worte rechts.
97. **Kranservice in vier Stufen** (löst 83 ab): Auf Abruf · Service-Vertrag Basis ·
    Service-Vertrag Plus · INEXXIO 365 (`ServiceTiers.astro`). Die Pakete Pflicht · Pflege ·
    Rundum und jeder «Jahrespreis» sind entfernt (`ServicePlans.astro` gelöscht).
    INEXXIO 365 hat zwei Wege: bestehender Kran (auch fremde Marken) · neuer Kran ohne
    Kauf, zur Monatsrate (`#inexxio-365`).
98. **Zuordnung**: Kranservice ①③ · Häfen & Werften ①②③ (Bootslifte gleichwertig, neu und
    Service) · Industriekrane ①② + Branchenzeile und Hinweis auf 365 · Heukrananlagen ①②
    (kein 365) · Modernisierung ①② · Fahrzeugtechnik und Fahrmischer ② (Trommeltausch
    zuerst, kein Gratis-Erstservice) · Sonderlösungen ② + Zweitmeinung.
99. **Startseite**: H1 «Krane und Fahrmischer mit Handschlagqualität.», zwei gleichwertige
    Einstiege (Krantechnik · Fahrzeugtechnik), Sonderlösungen als kleiner Link darunter
    (der Kran spielt nur noch zwei Szenen – Ausleger-Szene entfernt), Vertrauensleiste
    1982 · Alle Marken · Fixpreis · 50 %, dann die Versprechen und die Branchenzeile
    (Recycling und Entsorgung, Sägewerke und Holzhandel, Stahlhandel und Metallbau,
    Betonwerke). Claim in `brand.claim` (löst 81 ab).
100. **Neue Seite `/krantechnik/anschlagmittel`**: Ketten, Hebebänder, Haken als Set, das
     immer geprüft ist – jährlicher Tausch, Prüfung in der eigenen Werkstatt, jedes Teil
     gekennzeichnet. Zur Prüfpflicht nur «regelmässig geprüft». Bild vorerst das des
     Kranservice.
101. **Verbotene Wörter erweitert** (`check-site.mjs`): «Jahrespreis», «Jahrespaket» und
     das ganze Wort «Abo» brechen den Build. «INEXXIO 365» zählt nicht als erste Nennung
     der Firma.
102. **Über uns / Service**: die Zusagen beginnen mit «Fixpreis vor jeder Arbeit» und
     «Keine Mindestlaufzeit»; die Kran-Kachel auf /service nennt Gratis-Erstservice und
     INEXXIO 365. Das Anfrage-Formular hat keine Themenliste – unverändert.

### 7.7e Marketing-Durchgang und Testnotizen #1192–#1198 (07.10.2026)

103. **Startseite aus Sicht des Marketings** (`content/start.ts`): der Lead sagt jetzt, *was*
     wir tun und *warum ohne Risiko* («… Fixpreis vor jeder Arbeit – und einen
     Ansprechpartner, der erreichbar ist, wenn etwas stillsteht») statt einer Floskel. Die
     Vertrauensleiste trägt nur **belegbare Tatsachen** (1982 · 1985 · Alle Marken · Eine
     Nummer); «50 %» und «Fixpreis» stehen direkt darunter im Versprechens-Block, doppelt
     wären sie schwächer. **Belege vor Übergabe**: «Warum wir» steht vor «Aus HS Steiner
     wird INEXXIO» – erst überzeugen, dann beruhigen. Löst 99 teilweise ab (Lead, Leiste).
104. **Drei gleichwertige Karten** (#1193, löst 99 ab): Sonderlösungen wieder mit Bild und
     Szene; jede Karte trägt ihr Versprechen in einem Satz («Was es nicht zu kaufen gibt,
     bauen wir.»).
105. **Kranservice in drei Stufen** (#1197, löst 97 ab): Auf Abruf · Service-Vertrag Basis ·
     INEXXIO 365; was «Plus» trug, steckt in Basis (Kranbuch, Fristen) bzw. 365
     (Verschleissteile). Kein Satz «Sie erhalten eine Offerte» (#1192).
106. **«INEXXIO Zufriedenheitsgarantie»** heisst das zweite Versprechen (#1196).
107. **Modernisierung als Seite entfällt** (#1198): Seite, Inhalt, Vorher/Nachher-Bauteil und
     Fotos gelöscht; `/antrieb-und-steuerung` leitet auf den Kranservice. Das Foto
     `steuerung-funk` ist jetzt `anschlagmittel`.
108. **Kein «Erweitert»** (#1195) und **kein «Beispielbild»-Etikett** (#1194) mehr – beide
     samt CSS entfernt; der Bildnachweis bleibt im Impressum.
109. **Versprechen = «Zahlen als Anker»** (Claude Design, V1): Titel «Unser Wort hat einen
     Preis.» links, Satz und die drei Zusagen als ruhige Zeile rechts (kein Kasten, keine
     Häkchen); drei Spalten an einer schwarzen Linie; «365 Tage» – ohne Einheit war offen,
     was die Zahl zählt. Titel in der normalen h2 des Hauses.
110. **Branchen als Liste mit Bild** (Claude Design, B): links «Für alle, deren Kran laufen
     muss.» mit Satz und Knopf zu INEXXIO 365, rechts die vier Branchen, je mit einem
     isometrischen Bild im Stil der Heukran-Bauformen (grau der Bestand, rot die Last am
     Haken; `src/assets/illustrations/branche-*.svg`, inline, kein Request).

### 7.8 Änderungen ausserhalb von `website/` (Umbau v2)

| Datei | Änderung | Warum |
|---|---|---|
| `backend/app/routers/contact.py`, `backend/tests/test_contact.py` | Abo-Zweig und «Anzahl Krane» raus, PDF als Anhang, Notfall- statt Pikett-Satz | Formular nach Kap. 11 (eigener, isolierter Endpunkt – keine ERP-Logik) |
| `backend/app/assets/website_contact.json` | regeneriert | Vokabular aus der Website-Konfiguration |
| `frontend/src/lib/site-shell.json` | neu, generiert | Inhalte für Kopf und Fuss des Konto-/ERP-Bereichs (Entscheid 39) |
| `frontend/src/components/layout/navbar.tsx`, `footer.tsx`, Anmeldedialog, Auth-Layout | nur Darstellung (Kap. 6.2) | gleicher Kopf und Fuss wie die Website |
| `frontend/src/lib/firebase.ts` (`logout`), Navigation | S2 schreiben, Anzeige-Cache beim Abmelden räumen | Schnittstellen S2/S3 |
| `frontend/src/app/(auth)/abmelden/page.tsx` | neu | Schnittstelle S3 |
| `frontend/src/lib/account-cache.ts` | neu: die drei Schlüssel des Anzeige-Caches, Schreiben (S2) und Räumen | eine Stelle statt verstreuter Literale; `website/scripts/account.test.mjs` prüft beide Seiten |
| `frontend/public/brand/` | gestapeltes Logo (Abdruck aus `website/public/logo`), `logo.png` gelöscht | Entscheid 43 |
| `frontend/src/app/globals.css` | Stile für Kopf und Fuss, `--site-header-h`; tote Klassen der alten öffentlichen Seiten (`ix-wrap`, `ix-btn*`, `ix-section*`, `ix-card`, `ix-cta-band`, `ix-reveal`) entfernt | nur Darstellung |
| `frontend/src/app/(erp)/layout.tsx`, `(account)/layout.tsx`, `(erp)/erp/page.tsx` | feste `72px` → `var(--site-header-h)` | der Kopf ist jetzt zweizeilig (108 px ab 768 px) |
| `frontend/src/app/layout.tsx` | Titel/Beschreibung aus `site-shell.json` statt «Präzisionsfertigung» | falscher Fremdtext |
| `frontend/src/components/consent/cookie-consent.tsx`, `lib/consent.ts` | «Warenkorb» gestrichen | es gibt keinen Shop |
| `frontend/src/app/(public)/agb/page.tsx` | Titel bricht auf dem Telefon nicht mehr seitwärts aus | 0 px Überlauf (Kap. 15) |
| `firebase.json` | Weiterleitungen nach Kap. 14 | Entscheid 40 |
| `frontend/src/components/layout/navbar.tsx`, `globals.css` | ERP-Knöpfe raus, Arbeitsleiste rein | Entscheid 47 |
| `frontend/src/app/(erp)/erp/page.tsx` | `?typ=` stellt den Feed-Filter vor (wie ein Klick auf den Chip) | Entscheid 47 |
| `frontend/src/islands/`, `frontend/scripts/build-islands.mjs`, `package.json` (esbuild) | Testnotizen als Insel für die Website | Entscheid 48 |
| `.github/workflows/deploy-dev.yml` | `SITE_FEEDBACK=on`, `X-Robots-Tag` nur auf Dev | Entscheide 48/49 |
| `backend/app/routers/website.py`, `services/geoip.py`, `scripts/build_geoip.py`, `Dockerfile`, `main.py` | öffentlicher, rein lesender Endpunkt für Kontaktdaten; IP→Land im Docker-Build | Entscheid 56 |
| `frontend/src/components/layout/navbar.tsx`, `footer.tsx`, `globals.css`, `lib/api.ts`, `types/index.ts` | Kopf eine Zeile, ERP im Menü, Fuss mit Unternehmen-Spalte und Kontaktdaten aus dem ERP | Entscheide 50/56 |
| `firebase.json` | Garten-/Reifen-Weiterleitungen auf `/ueber-uns` (vorher `/uebergabe`) | Entscheid 55/92 |
| `.github/workflows/deploy-*.yml` | `SITE_API` für den Build | Entscheid 56 |
| `frontend/scripts/site-shell.mjs`, `src/components/layout/site-shell.tsx`, `account-sync.tsx`, `app/layout.tsx`, Layouts | Kopf/Fuss aus dem Website-Build einsetzen; `navbar.tsx`, `footer.tsx`, `cookie-settings-link.tsx` und das weisse Logo gelöscht; `lib/site-shell.json` → `lib/site-meta.json` | Entscheid 60 |
| `frontend/src/app/globals.css`, `cookie-consent.tsx`, `(auth)/login/page.tsx` | Kopf-/Fuss-Stile entfernt; Cookie-Einstellungen im gemeinsamen Fuss; Danebenklicken führt zu `?from=` zurück | Entscheid 60 |
| `backend/app/routers/contact.py`, `tests/test_contact.py`, `app/assets/website_contact.json` | Formular auf ein Feld reduziert (`inquiry/3`) | Entscheid 62 |
| `backend/tests/test_frontend_mirrors.py` | drei Wächter auf den gemeinsamen Kopf gezogen | Entscheid 60 |
| `.github/workflows/deploy-*.yml` | `SHELL_REQUIRED=1` | Entscheid 60 |
| `.github/workflows/deploy-dev.yml` | `SITE_ENV=dev` (DEV-Eckband im Kopf) | Entscheid 79/86 |

Nicht angefasst: ERP-Backend (ausser dem Kontakt-Router der Website), Datenbank, Modelle,
Migrationen, Auth-Logik, Rechte, Prozesse, Module.

### 7.9 Phasen-Checkliste (Kap. 17)

- [x] **0 – Analyse** und dieser Abschnitt
- [x] **1 – Fundament**: Konfiguration (Bereiche als Datenstruktur), Header zweizeilig mit
      Servicezeile und Anmeldezustand, Footer, Navigation, Logo, Begriffe, SITE_MODE
- [x] **2 – Komponenten**: Mega-Dropdown, Profilmenü, Bereichskarte, Drei Ebenen,
      Kranbahn-Linie, Unterseiten-Vorlage, Bereichs-Vorlage
- [x] **3 – Konto, Profil, ERP** im neuen Design (nur Darstellung) + S2/S3
- [x] **4 – Seiten** in der Reihenfolge von Kap. 17
- [x] **5 – Formular und Tracking**
- [x] **6 – SEO und KI** (Meta, JSON-LD, Sitemap, robots, llms, Redirects, OG-Bilder)
- [x] **7 – Prüfung** nach Kap. 17.1
- [x] **8 – Bericht** `WEBSITE_REPORT_20261004.md`
