# Website INEXXIO (ehemals HS Steiner) – Plan (geltende Entscheide)

> **Was hier steht, gilt heute.** Eingedampft im Cleanup Oktober 2026 (W-41) aus einer
> Folge von 124 Entscheiden, von denen viele spätere abgelöst haben. Die **Nummern** sind
> die der Chronik und bleiben als Verweis gültig («WEBSITE_PLAN Entscheid 60» im Code); der
> vollständige Wortlaut mit Begründungen, Messungen und abgelösten Fassungen liegt in
> `docs/history/2026-10-website-plan-chronik.md`.
>
> **Für Inhalte (Texte, Seiten, Versprechen, Branchen) ist der Code die Quelle**, nicht
> dieser Plan: `src/config/site.mjs` (Name, Telefon, Navigation, Schalter, SEO) und
> `src/content/*.ts`. Der Auftrag im Wortlaut steht in `AUFTRAG.md` (in zentralen Punkten
> überholt), die Start-Checkliste in `START.md`, offene Fotos in `OFFENE_PUNKTE.md`.

## 1. Architektur

- **1 · Astro 7 als eigenständiges Teilprojekt in `website/`** – reines HTML ohne
  Laufzeit-Framework, Progressive Enhancement. Node ≥ 22.12 (die CI baut die Website mit
  Node 22, das ERP mit Node 20).
- **2 · Dieselbe Firebase-Hosting-Site wie das ERP**: die CI baut beide Teile und kopiert
  `website/dist` in `frontend/out` (`scripts/merge-hosting.mjs`, bricht bei jeder Kollision
  ab). Die Website besitzt «/» und ihre Seiten; das ERP behält `/erp`, `/konto`, `/login`,
  `/abmelden`, `/agb`. `robots.txt` und `404.html` kommen von der Website.
- **3 · Die alten Next-Seiten sind gelöscht**; `/agb` bleibt im Next-Frontend (der
  Anmeldedialog verweist darauf).
- **5 · Farben aus dem Design-System, generiert** (`scripts/tokens.mjs` liest
  `frontend/src/styles/design-system/colors_and_type.css`). **34/37 · Formsprache = Design-System
  v3**: Inter Tight 700/600, Knöpfe 8 px, Karten 12 px, flach. **36/71a · Logo** = das
  gestapelte Logo mit «ehemals HS Steiner» (`public/logo/`).
- **12/40 · Weiterleitungen** der alten hs-steiner.ch-Pfade in `firebase.json`; **keine**
  Fangregel «alles andere → /» auf dieser Site (sie gehört auf die alte Domain).
  `check-site.mjs` prüft jedes Ziel.
- **13/61 · CSP** per `<meta>` (Skripte nur `'self'`); `img-src` kommt aus `firebase.json`
  (`src/lib/csp.mjs`) – eine Quelle für beide Teile.
- **17 · Eine Seitenliste** (`src/lib/pages.ts`) speist Sitemap und llms.txt; eine Seite, die
  weder dort steht noch `noindex` trägt, bricht den Build. **65 · Jede Seite der Sitemap ist
  über das Menü erreichbar** (`check-site.mjs`). **116 · Kopf und Fuss lesen EINE Liste**
  (`site.navigation`).
- **20 · Ein Stylesheet** für die ganze Website (`cssCodeSplit: false`).
- **49 · Dev wird nie indexiert** (`X-Robots-Tag` im Dev-Deploy); unabhängig davon sperrt der
  Modus `preview` per `noindex` und `robots.txt`. **86 · DEV-Eckband** nur bei `SITE_ENV=dev`.
- **48/66 · Testnotizen** auf der Website = dasselbe Werkzeug wie im ERP
  (`frontend/scripts/build-islands.mjs` → `/islands/feedback.js`), nur mit
  `SITE_FEEDBACK=on` (Dev) und nur für Angemeldete; geladen mit `?v=<Commit>`.

## 2. Kopf, Fuss und Konto (die Naht zum ERP)

- **60 · EIN Kopf und EIN Fuss für Website UND Konto/ERP – kein Nachbau.** Der Website-Build
  schreibt Kopf-/Fuss-HTML, Skript und ein auf `.ix-shell` beschränktes Stylesheet nach
  `dist/_shell/` (`scripts/export-shell.mjs`); das Frontend übernimmt es beim Bauen
  (`frontend/scripts/site-shell.mjs`, im Deploy Pflicht über `SHELL_REQUIRED=1`) und setzt es
  im Wurzel-Layout ein (`components/layout/site-shell.tsx`). Dasselbe Skript
  (`window.inexxioShell`) bedient beide Seiten. Anmelden ist überall der Link
  `/login?from=…`. Wer Kopf oder Fuss ändert, ändert `src/components/Header.astro` bzw.
  `Footer.astro`.
- **50/59 · Der Kopf ist EINE Zeile**: Telefon, Anmelden/Profilmenü, «Anfrage stellen»; ERP
  ist für Personal ein gewöhnlicher Menüpunkt. Servicezeile, Vorschau-Banner und
  Arbeitsleiste gibt es nicht mehr.

### 7.5 Anzeige-Cache und Abmelden (Schnittstellen S1–S3)

Eine statische Seite hat kein Token. Der Anmeldezustand im Kopf ist darum **nur Anzeige**:

| # | Schnittstelle | Was |
|---|---|---|
| S1 | `localStorage['inexxio_user_role']`, `['inexxio_user_fullname']`, `['inexxio_user_photo']` | Name/Initialen, Profilbild und «ERP ja/nein» (`isStaff` = `admin`/`employee`, Spiegel von `people.STAFF_ROLES`). Geschrieben vom ERP-Frontend nach jeder Anmeldung und beim Laden von Konto/ERP (`components/layout/account-sync.tsx`), gelöscht beim Abmelden. |
| S2 | `localStorage['inexxio_user_contact']` = `{ email, phone, company }` | Vorausfüllen des Formulars. |
| S3 | Route `/abmelden` (Next) | Die Website kann ohne Firebase-SDK nicht abmelden; die Seite ruft das bestehende `logout()`, das den Cache räumt. |

Die vier Schlüssel stehen an einer Stelle (`frontend/src/lib/account-cache.ts`); der Spiegel
ist getestet (`scripts/account.test.mjs`). Wer den Cache fälscht, sieht einen Menüpunkt
«ERP», den `/erp` und das Backend trotzdem abweisen.

## 3. Kontaktdaten und Formular (die Naht zum Backend)

- **51 · Eine Telefonnummer für alles**; keine Öffnungszeiten. **52 · Kein Einsatzgebiet**,
  das uns begrenzt (zuhause in Tuttwil-Wängi, im Einsatz in der ganzen Schweiz und weltweit).
- **56/64 · Kontaktdaten aus dem ERP**: `GET /api/v1/public/contact` liefert Telefon, E-Mail
  und Anschrift der Gesellschaft zum Land des Besuchers (IP → Land über DB-IP Lite im
  Docker-Build → `sites.company_for_country`, sonst der Betreiber). Beim Build holt
  `scripts/erp-contact.mjs` (mit `SITE_API`) die Angaben des Betreibers als Vorgabe ins HTML
  (Telefon, E-Mail – die Anschrift kommt aus `site.mjs`); zur Laufzeit tauscht
  `src/scripts/contact.ts` sie aus, auch `{{erp.city}}`. Impressum und Datenschutz sind
  ausgenommen. Die IP-Adresse wird nicht gespeichert.
- **62/63/69 · EIN Kontaktbereich, EIN Formular** (`ContactSection`): «Ihr Anliegen», Anhänge
  (nur Bilder) und «wer fragt an»; Karte und Anschrift daneben, Route als Link auf Google
  Maps. Das Formular geht an `POST /api/v1/contact` und wird eine **Nachricht im ERP**
  (`backend/app/services/inquiry.py`) – E-Mail Pflicht, Telefon freiwillig. Lässt sich die
  Anfrage nicht speichern: 503, die Seite zeigt Telefon und `mailto:`. Nach 60 s bricht das
  Formular ab und zeigt denselben Ausweg.
- **15 · Das Vokabular des Formulars ist generiert** (`scripts/export-erp.mjs` →
  `backend/app/assets/website_contact.json` und `frontend/src/lib/site-meta.json`); die CI
  prüft mit `--check`, dass es aktuell ist. Gebaut wird es aus den **Vorgaben** in
  `site.mjs` (`SITE_ERP=0`) – es ist der DB-freie Ausweg des Backends.

## 4. Inhalt und Bilder

- **119–122 · Drei gleichwertige Bereiche**: **Krantechnik** (`/krantechnik`: Krane nach
  Mass · Kranservice · Heukrananlagen) · **Fahrzeugtechnik** (`/fahrzeugtechnik`:
  Trommeltausch · Verschleissteile) · **Speziallösungen** (`/spezialloesungen`). Dazu
  `/service` (mit Notfall), `/ueber-uns` (mit Übergabe), `/karriere`, `/ratgeber`, `/kontakt`,
  Rechtliches.
- **61 · Garantien** (`src/content/promises.ts`, die eine Quelle): INEXXIO
  Zufriedenheitsgarantie und INEXXIO 365 für alle drei Bereiche, die Gratis-Inspektion als
  leiser Einstieg. **101 · Verbotene Wörter** (Preise, «Abo», «aller Marken» …) prüft
  `check-site.mjs` (FORBIDDEN).
- **58/76 · Kranservice defensiv**: keine Aussage «aller Marken/Hersteller» bei Kranen.
- **67 · Keine gelben Vermerke**: was nicht feststeht, steht nicht da. Offen ist allein die
  Fotoliste (`OFFENE_PUNKTE.md`, generiert).
- **32/108 · Keine Beispielbilder mehr** (Weisung 25.10.2026): bis zum Fototag steht der graue
  Rahmen «Foto fehlt»; ein Bildnachweis entfällt. Im Modus `live` ist er ein Build-Fehler.
- **Rechtstexte gehören dem ERP** (Weisung 25.10.2026): `/datenschutz` und `/impressum` sind wie
  `/agb` A4-Dokumente des ERP (`site.erpPaths`); die Website verlinkt sie nur.
- **53 · Keine laufenden Nummern** an Abschnitten ohne Reihenfolge. **54 · FAQ**: höchstens
  eine Antwort offen; ist keine offen, steht das Grundbild (Frage grau, Antwort rot). Schmal
  steht das Bild immer direkt über der offenen Frage.
- **125 · Krane nach Mass = schwierige Gebäude, Heukran = Funk statt Kabine** (Entscheid
  23.10.2026, aus Kundenbesuchen): «Krane nach Mass» (URL bleibt) ist die Seite für Gebäude, in
  die kein Katalogkran passt – um Ecken, über Steigungen, Deckenversätze, enge Stellen; Scheune und
  Halle gleich stark. Häfen (Boots- und Mastkrane, Bootslifte, ohne Gebietsgrenze) bleiben darunter. Heukrane haben keine Kabine und
  werden per Funk bedient – ein eigener Abschnitt auf den Heukrananlagen. Umrüsten auf Funk wird
  nicht beworben (nur in «Modernisierung»). Der Menüname steht als ein Wert in `site.labels`.
  Belege (Projekte) erst mit echten Fotos (`features.craneReferences`).
- **126 · Menü-Kacheln mit Titelbild** (Entscheid 23.10.2026): jede Kachel im Kopf- und Mobil-Menü
  zeigt das Titelbild ihrer Seite; hat eine Seite (noch) keines, steht ihre Zeichnung. Eine Liste
  `src/lib/titles.ts` für Seitenkopf und Menü. Menübilder laden erst beim Berühren des Kopfs.
- **127 · Kopf mit Platz** (Entscheid 23.10.2026): Hauptzeile = was man bei uns bekommt
  (Speziallösungen · Krantechnik · Fahrzeugtechnik · Service) plus **Unternehmen** (Über uns ·
  Ratgeber · Kontakt · Karriere). «Kontakt» ist kein eigener Punkt mehr – Telefon und «Anfrage
  stellen» stehen rechts. Service bleibt allein (wer einen Ausfall hat, sucht dieses Wort). Die
  Sprachwahl bleibt im Kopf. Ein späterer Shop kommt rechts als Symbol, «Meine Produkte» ins Konto.
- **128 · Reihenfolge unter «Unternehmen»** (Entscheid 24.10.2026): Über uns · Ratgeber · Kontakt ·
  Karriere – erst Vertrauen (wer wir sind, was wir wissen), dann der Weg zu uns; Karriere spricht
  Bewerbende an, nicht Kunden, und steht zuletzt.
- **129 · Service, Karriere, Ratgeber im Layout v4** (Entscheid 24.10.2026): Kopf wie Porsche mit
  Titelbild; Service: Notfall als dunkle Karte mit der Nummer gross, dann drei Anliegen-Karten,
  Garantien, Fragen; Karriere: Warum hier arbeiten, Wer zu uns passt (keine ausgeschriebenen Stellen),
  Weg der Bewerbung, Bewerbungskarte – kein Anfrage-Formular; Ratgeber: Artikel als Karten mit Zeichnung,
  im Artikel «Kurz gesagt» als Karte, «Weiterlesen» als Karten. Artikeltexte unverändert.
- **130 · Der frühere Name nur im Fliesstext** (Weisung 24.10.2026): Seitentitel, Meta-Description,
  `og:*`, der Name der Website im JSON-LD und der Kopf von llms.txt nennen nur «INEXXIO».
  «ehemals HS Steiner» steht im Fliesstext, im Logo und als `alternateName` im JSON-LD (so bleibt
  der alte Name für Suchmaschinen auffindbar). `check-site` bricht ab, wenn Titel oder
  Beschreibung ihn nennen. Die Kontakt-E-Mail kommt aus dem ERP (Postfach der Betreiber-Gesellschaft);
  ohne Angabe dort steht die bisherige Adresse.
- **131 · Eine Regel für Überschriften** (Entscheid 24.10.2026): Das grosse Wort im Kopf nennt den
  Bereich; die H1 ist ein Nutzen-Satz und wiederholt es nie. Aussagen enden mit Punkt (oder
  Fragezeichen), reine Rubriken nicht («Häufige Fragen», «Katalog», «Bauformen», «Artikel», «Mehr
  von uns»). Jeder Ablauf heisst «So läuft es ab.» (Karriere: «So bewerben Sie sich.»). Auf einer
  Seite stehen nie zwei fast gleiche Überschriften. Rechtstexte und Ratgeber-Artikel behalten ihre
  Kapitel.
- **132 · Bühne der Startseite mit KI-Bildern** (Entscheid 24.10.2026): «Ihre Aufgabe. Unsere Lösung.»
  zeigt statt der Symbolbilder drei KI-Bilder nach der Bildregel der Legende – die Serie als graue
  Zeichnung, rot und echt, was wir dazubauen: Säulenschwenkkran mit Rohrgreifer, Lastwagen mit
  Kippbrücke, Minibagger mit Anbau-Rüttelplatte (`src/assets/illustrations/spezial-*-bild.jpg`). Auf
  Weiss statt freigestellt: die Bühne steht auf Weiss, und so bleibt die Startseite im Budget.
  Die Karten der Speziallösungen tragen weiter die Zeichnungen.
