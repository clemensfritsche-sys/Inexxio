# Website INEXXIO (ehemals HS Steiner) – Bericht Umbau v2

> Stand 4. Oktober 2026 · Auftrag: `website/AUFTRAG.md` (Fassung 2, die einzige gültige) ·
> Plan und alle Entscheidungen: `website/WEBSITE_PLAN.md` §7 · offene Punkte (generiert):
> `website/OFFENE_PUNKTE.md` · der Bericht zur ersten Fassung bleibt als
> `WEBSITE_REPORT_20261003.md` stehen.

## Kurzfassung

- **Die Website ist auf die neue Fassung des Auftrags umgebaut**: drei Bereiche
  (Krantechnik · Fahrzeugtechnik · Sonderlösungen) mit neuen Adressen, Heukrananlagen zuerst,
  Service mit Notfall-Service, zweizeiliger Kopf mit Servicezeile und Anmeldezustand.
- **Die zwei Sofortpunkte sind erledigt**: das Logo trägt «ehemals HS Steiner» (ohne die
  Unterzeile «Kran- und Fahrmischertechnik»), und das **Burger-Menü funktioniert** wieder –
  das Menü war in der 60 px hohen Kopfzeile eingesperrt (Ursache: ein Milchglas-Effekt auf
  der Kopfzeile; gemessen jetzt 844 px hoch, also bildschirmfüllend).
- **Konto, Profil und ERP sitzen im neuen Kopf und Fuss** – nur die Darstellung ist neu,
  Anmeldung, Rollen und Abmelden laufen unverändert. Die ERP-Logik ist nicht angefasst.
- **Gelöscht, was nicht mehr gebraucht wird**: Service-Abo, digitales Kranbuch, die alten
  Krane-/Fahrmischer-Seiten, die Einsatzgebiet-Seite, zwei Ratgeber, die Ankündigungsleiste,
  dazu tote Stile und das alte Logo im Frontend. Alte Adressen leiten weiter.
- **Gemessen, nicht behauptet**: 28/28 Seiten ohne JavaScript vollständig, HTML 0 Fehler,
  axe 0 Verstösse, 0 px seitliches Scrollen bei 7 Breiten, Lighthouse mobil 98–99 /
  Barrierefreiheit 100, Weiterleitungen 47/47, Konto-Anzeige 23/23, Formular 22/22 inklusive
  Störungsfall, Backend-Suite 651 grün. Was **nicht** geprüft werden konnte, steht in §4.
- **Modus bleibt «Vorschau»**: 125 offene Punkte plus 25 Fotos – ein Build im Modus «live»
  bricht ab, so wie verlangt.

## 1. Was sich gegenüber der ersten Fassung geändert hat

| Vorher (03.10.) | Jetzt (04.10.) |
|---|---|
| Zwei Säulen: Krane · Fahrmischer | **Drei Bereiche**: Krantechnik · Fahrzeugtechnik · Sonderlösungen, als Datenstruktur in `site.mjs` – Navigation, Karten, Fuss, JSON-LD und llms.txt entstehen daraus |
| `/krane/…`, `/fahrmischer/…` | `/krantechnik/…`, `/fahrzeugtechnik/…`, `/sonderloesungen/…` (Kap. 7.1); alte Adressen leiten weiter |
| «HS-Krananlagen» als eigene Seite und Produktname | **Heukrananlagen** als erste Unterseite; «HS» nur noch im Hinweis für Besitzer bestehender Anlagen |
| Service-Abo mit Stufen, digitales Kranbuch | **entfernt** (Seite, Inhalte, Komponenten, Konfiguration) |
| «Pikett» | **Notfall-Service** und **Notfallnummer** 076 563 22 47 (Servicezeile, Fuss, `/service/notfall`, Formular) |
| `/einsatzgebiet` als eigene Seite | Abschnitt auf «Über uns» (`/ueber-uns#einsatzgebiet`) |
| Einzeiliger Kopf, Milchglas, «Login» | **Zweizeilig**: dunkle Servicezeile (Notfall · Telefon · ERP · Anmelden/Profilmenü) + weisse Hauptzeile mit Dropdowns; deckend weiss, Burger-Menü wieder funktionsfähig |
| Wortmarke mit Unterzeile | **Gestapeltes Logo mit «ehemals HS Steiner»** |
| Ankündigungsleiste (schliessbar) | Ankündigung **in der Servicezeile** (Schalter in `site.mjs`) |
| Konto/ERP mit altem Kopf (falsches Logo, «Präzisionsfertigung», fremde Telefonnummer) | **Derselbe Kopf und Fuss wie die Website**, Inhalte aus derselben Quelle |
| Formular: Krane/Fahrmischer/Abo, Fotos | Bereich → Anliegen, **Teil + «Wofür?»**, **Skizzen als PDF**, Notfallnummer gross bei «Steht still», **Vorausfüllen aus dem Konto** |
| Drei Teilen-Bilder | Vier: Startseite + je Bereich; Logo-PNG für die Suchmaschinen neu |
| Firma «INEXXIO» | **INEXXIO AG** (ehemals HS Steiner Fahrzeug- und Kranbau GmbH) |
| Neu | Seiten Industriekrane, Aufbauten, Konstruktion & Engineering, Schweiss- & Stahlbau, Baumaschinen, Service, Notfall-Service, Ratgeber «Neue Heukrananlage planen»; Bausteine «Drei Ebenen», Bereichskarte, Kranbahn-Linie am Ablauf |

## 2. Was gebaut wurde

### Seiten (28, davon 26 in der Sitemap)

| Bereich | Seiten |
|---|---|
| Start | `/` |
| Krantechnik | `/krantechnik` · `/heukrananlagen` · `/industriekrane` · `/pruefung-wartung` (mit Prüfpflicht-Check) · `/modernisierung` |
| Fahrzeugtechnik | `/fahrzeugtechnik` · `/fahrmischer` · `/aufbauten-reparatur` · `/verschleiss-ersatzteile` (Teile-Katalog) |
| Sonderlösungen | `/sonderloesungen` · `/konstruktion-engineering` · `/schweiss-stahlbau` · `/baumaschinen` |
| Service | `/service` (Einstieg nach Anliegen) · `/service/notfall` |
| Unternehmen | `/uebergabe` · `/ueber-uns` (mit Einsatzgebiet) · `/karriere` |
| Ratgeber | `/ratgeber` · `heukrananlage-planen` · `kranpruefung-schweiz` · `verschleissteile-fahrmischer` |
| Kontakt | `/kontakt` · `/kontakt/danke` (noindex) |
| Rechtliches | `/impressum` · `/datenschutz` |
| Fehler | `404` (noindex) |

Konto und ERP (Next-Frontend, unverändert in der Logik): `/login` · `/konto` · `/erp` ·
`/agb` · neu `/abmelden`.

### Bausteine

35 Komponenten, 4 Vorlagen (Bereichsseite, Unterseite, Rechtliches, Grundgerüst). Neu bzw.
umgebaut: zweizeiliger Kopf mit Dropdowns (Maus, Klick, Tastatur, Esc) und Profilmenü,
Vollbild-Menü mobil, Bereichskarte, «Drei Ebenen», Ablauf mit Kranbahn-Linie, Unterseiten-
und Bereichsvorlage («Auf einen Blick»: Für wen · Was wir tun · Was Sie erhalten),
Notfall-Kasten im Formular. Alles ohne JavaScript bedienbar; das Skript ergänzt nur Komfort
(gesamt höchstens 2.3 KB pro Seite).

## 3. Schnittstellen zum ERP und Änderungen ausserhalb von `website/`

### Schnittstellen (alle rein lesend bzw. additiv, vorher im Plan beschrieben)

| | Was | Art |
|---|---|---|
| S1 | Anzeige-Cache `inexxio_user_role`, `inexxio_user_fullname` (localStorage, gleiche Domain) | bestand schon; die Website **liest** daraus Name/Initialen und «ERP ja/nein» |
| S2 | Anzeige-Cache `inexxio_user_contact` = `{email, phone, company}` | neu: an derselben Stelle geschrieben, an der die Navigation Rolle und Name speichert; nur für das Vorausfüllen des Formulars |
| S3 | Route `/abmelden` | neu: ruft das **bestehende** `logout()` und kehrt zu «/» zurück; `logout()` räumt dabei alle drei Anzeige-Schlüssel |

Die Berechtigung wird auf der Website **nur angezeigt**, nie durchgesetzt – den Schutz von
`/konto` und `/erp` hat das ERP (gemessen: `/konto` ohne Sitzung → `/login?from=/konto`).
Ein Wächter (`website/scripts/account.test.mjs`) hält Schlüssel und Personal-Rollen beider
Seiten gleich.

### Dateien ausserhalb von `website/`

| Datei | Änderung | Warum |
|---|---|---|
| `backend/app/routers/contact.py`, `tests/test_contact.py` | Abo-Zweig raus, Teil + Verwendung, PDF als Anhang, Notfall- statt Pikett-Satz, alte Arten werden abgewiesen | Formular nach Kap. 11; isolierter Endpunkt, keine ERP-Logik |
| `backend/app/assets/website_contact.json` | regeneriert | Vokabular der Website |
| `frontend/src/lib/site-shell.json`, `frontend/public/brand/inexxio-ehemals-hs-steiner*.svg` | neu, **generiert** aus `website/` (CI prüft) | Kopf, Fuss und Logo für Konto/ERP aus einer Quelle |
| `frontend/src/components/layout/navbar.tsx`, `footer.tsx` | neu gezeichnet, Anmelde-Logik unverändert | gleicher Kopf und Fuss wie die Website (Kap. 6.2) |
| `frontend/src/lib/account-cache.ts` (neu), `lib/firebase.ts` (`logout`) | S2 schreiben, Cache beim Abmelden räumen | S2/S3 |
| `frontend/src/app/(auth)/abmelden/page.tsx` | neu | S3 |
| `frontend/src/app/globals.css` | Stile für Kopf/Fuss; Anmeldedialog flach mit 8 px statt Pille, ohne schwebendes Logo; tote Klassen der alten öffentlichen Seiten entfernt | Design-System v3, nur Darstellung |
| `frontend/src/app/(erp)/layout.tsx`, `(account)/layout.tsx`, `(erp)/erp/page.tsx` | `72px` → `var(--site-header-h)` | der Kopf ist zweizeilig |
| `frontend/src/app/layout.tsx`, `(auth)/layout.tsx`, Anmeldedialog, `/login/verify` | Titel/Beschreibung aus der Website-Quelle, neues Logo, Hintergrund als Token | falsche Fremdtexte, altes Logo |
| `frontend/src/components/consent/cookie-consent.tsx`, `lib/consent.ts` | «Warenkorb» gestrichen | es gibt keinen Shop |
| `frontend/src/app/(public)/agb/page.tsx` | Titel bricht auf dem Telefon um | lief bei 320–375 px seitwärts über |
| `frontend/public/logo.png` | gelöscht | altes Logo, kein Leser mehr |
| `firebase.json` | 14 Weiterleitungen alter hs-steiner.ch-Pfade | Kap. 14 |
| `CLAUDE.md`, `frontend/CLAUDE.md` | Website- und Kopf-Abschnitt nachgezogen | jede Sitzung liest sie zuerst |

**Nicht angefasst:** ERP-Backend (ausser dem Kontakt-Router der Website), Datenbank, Modelle,
Migrationen, Anmelde-Logik, Rechte, Sitzungen, Prozesse, Module.

## 4. Testergebnisse (Kap. 17.1)

Gemessen am Endstand, lokal: die **zusammengeführte Hosting-Ausgabe** (ERP-Build + Website,
wie in der CI) ausgeliefert mit **superstatic** – der Engine des Firebase-Emulators, mit den
Weiterleitungen und Headern (inkl. CSP) aus `firebase.json`.

| Prüfung | Werkzeug | Ergebnis |
|---|---|---|
| Build in beiden Modi | `npm run build` | «preview» grün; «live» bricht ab – an der Domain (Platzhalter) und an 157 offenen Markierungen ✔ |
| Jede Seite ohne JavaScript | curl: Status, H1, Wortzahl | 28/28 vollständig (470–1738 Wörter), 404 korrekt ✔ |
| HTML-Validierung | Nu Html Checker (vnu) | 0 Fehler auf 28 Seiten ✔ |
| Links, JSON-LD, Sitemap, robots, llms, Bilder | `check-site.mjs` (neu: jedes Bild in Meta/JSON-LD muss existieren – gegengeprüft) | in Ordnung ✔ |
| Barrierefreiheit | axe-core 4 (WCAG 2.0–2.2 A/AA + Best Practice), jede Seite mobil und Desktop | **0** Verstösse ✔ – vorher 4: Ablauf-Text auf dunklem Grund (2:1), Nummer auf Bereichskarte (1.5:1); behoben |
| Breiten | 360 · 390 · 768 · 1024 · 1280 · 1440 · 2560 px, jede Seite | **0 px** seitliches Scrollen ✔ – vorher 2 Seiten bei 360 px (Dachzeile brach nicht um); behoben |
| Klickflächen | Knöpfe, Navigation, Felder, Telefon-/E-Mail-Links | 0 unter 24 × 24 px (WCAG 2.5.8) ✔ |
| CSP und Skriptfehler | Chromium, jede Seite × 7 Breiten | 0 Verstösse, 0 Fehler ✔ |
| Lighthouse mobil | 8 Kernseiten | Leistung 98–99 · Barrierefreiheit 100 · Best Practices 100 · LCP 1.8–2.2 s · CLS 0 · SEO 66–69 – **allein** wegen des gewollten `noindex` der Vorschau (einziger Fehlbefund: `is-crawlable`) |
| Konto-Ablauf | Playwright, Anzeige-Cache in allen Zuständen | 23/23 ✔: nicht angemeldet → «Anmelden» · angemeldet ohne Recht → Profilmenü ohne ERP · mit Recht (Mitarbeiter, Admin) → «ERP» in Servicezeile und Menü, Klick öffnet `/erp` · mobil · Abmelden räumt den Cache und zeigt wieder «Anmelden» · Speicher gesperrt bzw. unlesbar → «Anmelden», nichts bricht |
| Konto/ERP im neuen Kopf | Chromium am echten Next-Build | Kopf 108 px (36 + 72), Dropdowns, Anmelde-Pop-up öffnet, Vollbild-Menü mobil, `/abmelden` räumt und geht zu «/», 0 px Überlauf bei 320–2560 px ✔ |
| Formular | Playwright gegen den echten Endpunkt + lokalen SMTP-Briefkasten | 22/22 ✔: Pflichtfeld- und Baujahr-Fehler am Feld · Notfallnummer bei «Steht still» · Erfolg mit Anfrage **und** Bestätigung · Betreff mit Bereich · PDF-Skizze und `anfrage.json` im Anhang · Reply-To · keine Markierung in Mails · Teil + «Wofür?» · `?typ=teile` · Kurzformular · **Störung** (Versand aus → 503 → Telefon und vorausgefüllter `mailto:`, Eingaben bleiben, `INQUIRY_UNSENT` im Log) · **ohne JavaScript** → Danke-Seite |
| Vorausfüllen bei Login | Playwright | Name, Firma, Telefon, E-Mail aus dem Konto ✔ |
| Weiterleitungen | fetch gegen superstatic | 37 alte Pfade → 301 → Seite 200; `/kontakt` bleibt; 9 neue Seiten und ERP-Pfade werden von keiner Regel gefangen – 47/47 ✔ |
| ERP-Regression | Backend-Suite gegen PostgreSQL 16 (Schema aus den Migrationen); Frontend: TypeScript, ESLint, Unit-Tests, Build; generierte Typen | **651 bestanden, 2 übersprungen** · alles grün · Typen aktuell ✔ |
| Website-Tests | `npm test` | 9/9 (inkl. Spiegel Anzeige-Cache) ✔ |
| Texte | Suche in allen Seiten | 0 × ß, Ausrufezeichen, Emojis, «Pikett», Du-Form, Service-Abo/Kranbuch; verbotene Wörter (8.2) prüft `check-site` bei jedem Build ✔ |
| Anti-KI-Look (9.7) | CSS-Prüfung + Sichtung | kein Verlauf mehr (der Logo-Schwung unter dem Titelwort war einer – jetzt einfarbig wie im Logo), kein Glas, keine Unschärfe, keine Icon-Kreise, keine Zähler, keine Karussells; Bewegung nur Einblenden und Kranbahn-Linie, bei `prefers-reduced-motion` aus ✔ |

### 5-Sekunden-Test (Startseite und Kopf, 1440 × 900 und 390 × 844)

| Zielgruppe | Findet sie … | Ergebnis |
|---|---|---|
| Landwirt | neue Heukrananlage, alte wird weiter betreut? | ✔ Menü «Krantechnik» → Heukrananlagen an erster Stelle; Bereichskarte «Heukrananlagen und Industriekrane: neue Anlagen nach Mass» direkt unter dem Hero; Frage «Wer betreut meine HS-Krananlage?» auf Start, Krantechnik und Übergabe. *Einschränkung:* das Wort «Heukrananlage» steht nicht in der ersten Ansicht der Startseite (H1 nennt «Krantechnik») |
| Instandhaltungsleiter | Prüfpflicht und Prüfung buchen? | ✔ Menü «Krantechnik» → Prüfung & Wartung; Service-Kachel «Kran prüfen oder warten lassen»; dort Prüfpflicht-Tabelle, Check und Formular |
| Fuhrparkleiter | Fahrmischer-Service und Telefon? | ✔ «Fahrzeugtechnik» in H1 und Menü → Fahrmischer; Telefon und Notfallnummer in der Servicezeile und im Hero |
| Betrieb mit Sonderwunsch | wird hier konstruiert und gebaut? | ✔ H1 «… und Sonderlösungen», Lead «konstruieren Lösungen, die es nicht von der Stange gibt» |
| Bestandskunde | was ändert sich durch die Übergabe? | ✔ «HS Steiner heisst jetzt INEXXIO → Mehr erfahren» in der Servicezeile (ab 900 px); auf dem Handy sagt es das Logo («ehemals HS Steiner»), der Weg zur Übergabe steht im Menü und als zweiter Abschnitt der Startseite |
| Mitarbeiter | mit einem Klick ins ERP? | ✔ «ERP» in der Servicezeile (Desktop, ein Klick); mobil Menü → ERP (zwei) |

### Nicht geprüft – und warum

- **Echte Anmeldung mit einem ERP-Konto**: hier gibt es keine Zugangsdaten. Geprüft sind
  der Kopf im abgemeldeten Zustand, das Anmelde-Pop-up, `/abmelden`, die Umleitung
  geschützter Seiten und die ganze Anzeige auf der Website; die Anmelde-Logik selbst ist
  unverändert und durch die Backend-Suite und den Build gedeckt. **Ein manueller Kurztest
  mit echtem Konto (Profil, ERP, Abmelden) steht aus** – siehe Start-Checkliste.
- **Echte Geräte und andere Browser**: gemessen mit Chromium (Desktop und Mobil-Emulation);
  Safari/iOS und Firefox nicht.
- **Echter Mailversand**: gegen einen lokalen SMTP-Briefkasten, nicht gegen den künftigen
  Anbieter (noch keine Zugangsdaten).
- **Externe Links** (Fedlex, Suva, SECO, EUR-Lex, Google Maps): die Netzwerkrichtlinie dieser
  Umgebung sperrt sie.
- **Bildschirmleser von Hand**: geprüft sind Struktur und ARIA mit axe; ein Durchgang mit
  VoiceOver/NVDA steht aus.
- **Echte Fotos**: es stehen gekennzeichnete Beispielbilder bzw. beschriebene Platzhalter.
  Das Beispielbild «Servicefahrzeug» (ein Kleinbus im Stadtverkehr) passt inhaltlich
  schlecht – es fällt mit dem Fototag weg.

## 5. Offene Punkte (Zusammenfassung)

Vollständig mit Fundstelle in `OFFENE_PUNKTE.md` (bei jedem Build neu geschrieben):

| Gruppe | Anzahl | Beispiele |
|---|---|---|
| Entscheidungen | 41 | Domain, neue E-Mail-Adresse, Notfallnummer weiterführen und Erreichbarkeit, Antwort- und Reaktionszeit, Einsätze vor Ort (Aufbauten, Baumaschinen, Fahrmischer), Materialien im Stahlbau, Preisrahmen, Analytics |
| Inhalte und Freigaben | 63 | Zitat und Rolle von Heiri Steiner, Botschaft von Clemens, Zusagen (Offerte, Bericht), Teamnamen, Übergabedatum, Handelsregister |
| Fachlich/rechtlich | 21 | Prüfpflicht-Tabelle und -Check, Ratgeber, Verhalten bei Störung, Impressum, Datenschutz |
| Fotos | 25 | Fotoliste aus Kap. 16 – Empfehlung: ein professioneller Fototag |
| Abgeschaltete Sektionen | 4 | Referenzen/Arbeiten, Vorher/Nachher, Team, Stelleninserat |

**Ausserhalb der generierten Liste** (sie betrifft nur die Website): die **AGB** im
Frontend sprechen von einem Online-Shop, einem Warenkorb und der Adresse
`info@inexxio.com` – das ist Rechtstext, ich habe ihn nicht verändert. Er gehört vor dem
Start rechtlich geprüft und an die heutige Firma angepasst.

## 6. Start-Checkliste

**Vor dem Umschalten**

- [ ] Freigabe von Heiri Steiner: Texte, Zitat, Fotos, Namenswechsel
- [ ] Fototag; Fotos in `src/config/photos.mjs` eintragen (jedes ersetzt ein Beispielbild)
- [ ] alle Markierungen erledigt (`OFFENE_PUNKTE.md` leer), dann `SITE_MODE=live` und
      `SITE_URL=https://<Domain>` im Produktions-Workflow
- [ ] Mailversand einrichten (`INQUIRY_SMTP_HOST`, `_PORT`, `_USER`, `_PASSWORD` im Secret
      Manager, optional `INQUIRY_MAIL_TO`, `INQUIRY_MAIL_FROM`) – ohne sie zeigt das
      Formular Telefon und `mailto:`
- [ ] `firebase.json`: der `/api/**`-Rewrite zeigt für beide Umgebungen auf das
      Dev-Backend – für die Produktion den Produktionsdienst eintragen
- [ ] AGB rechtlich prüfen und anpassen (siehe §5)
- [ ] **Login, Profil und ERP einmal mit einem echten Konto durchklicken** (Mitarbeiter und
      Kunde): Profilmenü, «ERP» in der Servicezeile, Abmelden – auf Website **und** im ERP
- [ ] Test auf iPhone (Safari) und Android (Chrome); externe Links einmal öffnen

**Beim Umschalten**

- [ ] Domain mit Firebase Hosting verbinden; hs-steiner.ch per 301 weiterleiten – dafür eine
      eigene Hosting-Site mit derselben Tabelle plus Fangregel «alles andere → Startseite»
      (auf der neuen Site wäre diese Regel ein Fehler, Entscheid 40)
- [ ] Formular und Login in Produktion einmal testen (Anfrage und Bestätigung kommen an)
- [ ] Google Search Console und Bing Webmaster Tools: Domain bestätigen, Sitemap einreichen,
      Adressänderung melden

**Ausserhalb der Website**

- [ ] Google-Unternehmensprofil umbenennen («INEXXIO – ehemals HS Steiner»), Bing Places,
      Apple Business Connect, local.ch/search.ch – überall derselbe Name
- [ ] E-Mail-Weiterleitungen der bisherigen Adressen und neue Signaturen
- [ ] Analytics-Anbieter wählen (cookielos), dann Datenschutzerklärung anpassen

## 7. Laufende Kosten

Unverändert **0 CHF zusätzlich**: Hosting, Formular-Endpunkt, Schrift, Logo und Bilder liegen
bei uns. Offen bleiben nur das Mail-Postfach für den Versand und – falls gewählt – ein
Analytics-Anbieter.
