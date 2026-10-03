# Website INEXXIO (ehemals HS Steiner) – Abschlussbericht

> Stand 3. Oktober 2026 · Auftrag: `website/AUFTRAG.md` · Plan und alle Entscheidungen:
> `website/WEBSITE_PLAN.md` · offene Punkte (generiert): `website/OFFENE_PUNKTE.md`

## Kurzfassung

- **Die neue Website steht vollständig** – 24 Seiten, eigenständig in `website/` (Astro,
  reines HTML, kein Laufzeit-Framework), auf derselben Firebase-Hosting-Site wie das ERP.
- **Das ERP ist unverändert.** Ausserhalb von `website/` wurde nur angefasst, was Bau,
  Formular und Auslieferung zwingend brauchen (Liste in §3).
- **Nichts ist erfunden.** Wo eine Angabe fehlt oder fachlich/rechtlich geprüft werden muss,
  steht sichtbar eine Markierung – 135 Stück, alle in `OFFENE_PUNKTE.md`. Fotos sind
  beschriebene Platzhalter (22), keine Stock- oder KI-Bilder.
- **Modus heute: «Vorschau»** – `noindex`, `robots.txt` sperrt alles, ein Banner sagt es.
  Ein Build im Modus «live» bricht ab, solange eine Markierung offen ist – so ist es
  verlangt, und so ist es geprüft.
- **Gemessen, nicht behauptet:** Lighthouse mobil 99–100, axe 0 Verstösse, HTML-Validierung
  0 Fehler, CLS 0, Formular 30/30 inklusive Störungsfall und ohne JavaScript.

## 1. Was gebaut wurde

### Seiten (24)

| Bereich | Seiten |
|---|---|
| Start | `/` |
| Krane | `/krane` · `/krane/pruefung-wartung` · `/krane/reparatur` · `/krane/modernisierung` · `/krane/hs-krananlagen` |
| Fahrmischer | `/fahrmischer` · `/fahrmischer/service-reparatur` · `/fahrmischer/verschleissteile` |
| Abo | `/service-abo` |
| Unternehmen | `/uebergabe` · `/ueber-uns` · `/einsatzgebiet` · `/karriere` |
| Kontakt | `/kontakt` · `/kontakt/danke` (noindex) |
| Ratgeber | `/ratgeber` · `/ratgeber/kranpruefung-schweiz` · `/ratgeber/kranfachmann-kranexperte` · `/ratgeber/heukran-saison-check` · `/ratgeber/verschleissteile-fahrmischer` |
| Rechtliches | `/impressum` · `/datenschutz` |
| Fehler | `404` (noindex) |

Die AGB bleiben im Next-Frontend (`/agb`) – der Anmeldedialog des ERP verweist darauf.

### Komponenten (39) und Funktionen

- **Global:** Ankündigungsleiste (schliessbar, gemerkt mit `try/catch`), Kopfzeile (sticky,
  blendet beim Runterscrollen aus), Dropdowns per Maus, Klick und Tastatur, Vollbild-Menü
  mobil mit Akkordeons, feste Aktionsleiste unten mobil, Fusszeile, Brotkrümel,
  Saison-Aktion nach Datum (Nov.–Feb. Fahrmischer, März–Mai Heukrane).
- **Inhalt:** Hero, Einstiegs-Kacheln, Vertrauensleiste, Leistungskarten, Faktenbox «Auf
  einen Blick», Leistungsumfang, Ablauf in vier Schritten mit Kranbahn-Linie, FAQ (natives
  `<details>`), Abo-Stufen, Kranbuch-Illustration, Zeitleiste, Zitat (bis zur Freigabe ein
  Platzhalter), Teilekatalog, Quellenliste, verwandte Leistungen, Ratgeber-Karten,
  schematische Einsatzkarte (eigenes SVG aus echten Koordinaten, kein Kartendienst).
- **Interaktiv, alles mit Rückfall ohne JavaScript:** Prüfpflicht-Check (die Tabelle steht
  immer da), Vorher/Nachher-Regler (abgeschaltet, bis echte Fotopaare da sind), Formular.
- **Formular:** vier Schritte (Anliegen · Bedarf · Details · Kontakt) bzw. Kurzformular auf
  jeder Leistungsseite mit Vorbelegung; Foto-Anhang; Prüfung am Feld; Honeypot, Mindestzeit
  und Begrenzung je IP; E-Mail an uns (mit `anfrage.json` für eine spätere Übernahme ins
  ERP) plus Bestätigung an die anfragende Person. **Ohne Mailversand oder bei einer Störung
  geht keine Anfrage verloren:** Telefon und ein vorausgefüllter `mailto:`-Link erscheinen,
  die Eingaben bleiben stehen, die Anfrage steht vollständig im Log (`INQUIRY_UNSENT`).
- **Tracking:** neutraler Helfer, Ereignisse definiert (Formular, Telefon, E-Mail, Abo),
  standardmässig aus – der Anbieter ist eine offene Entscheidung.
- **Platzhalter-System:** `[[PLATZHALTER: …]]` / `[[PRÜFEN: …]]` in Texten und
  Konfiguration, im Modus «preview» gelb sichtbar, im Modus «live» ein Build-Abbruch;
  `OFFENE_PUNKTE.md` wird bei jedem Build neu geschrieben.

### SEO und KI

Titel und Beschreibung je Seite, Canonical, Open-Graph-Bilder (3), JSON-LD
(Organization + LocalBusiness, WebSite, Service mit Angebotskatalog, FAQPage,
BreadcrumbList, Article), `sitemap.xml` (22 Seiten), `robots.txt` je Modus, `llms.txt` und
`llms-full.txt`, Weiterleitungen der alten hs-steiner.ch-Pfade (12 Regeln in
`firebase.json`, unabhängig von Gross-/Kleinschreibung). Jede Seite steht in **einer**
Seitenliste (`src/lib/pages.ts`) oder trägt `noindex` – sonst bricht der Build.

### Werkzeuge

| Skript | Aufgabe |
|---|---|
| `scripts/check-content.mjs` | offene Punkte finden, `OFFENE_PUNKTE.md` schreiben, im Modus «live» abbrechen |
| `scripts/check-site.mjs` | nach jedem Build: interne Links, JSON-LD, Titel, eine H1, ein Seitenkopf, Sitemap/robots/llms, Weiterleitungsziele, verbotene Wörter, Leistungsbudget |
| `scripts/tokens.mjs` | Farben aus dem Design-System übernehmen (ein Wert, eine Stelle) |
| `scripts/export-contact.mjs` | Formular-Vokabular für die E-Mails ans Backend (CI prüft Aktualität) |
| `scripts/merge-hosting.mjs` | Website in die Hosting-Ausgabe des ERP übernehmen, bricht bei jeder Kollision ab |

## 2. Entscheidungen

Alle 29 stehen mit Begründung in `WEBSITE_PLAN.md` §2. Die tragenden:

1. **Astro in `website/` statt einer Erweiterung des Next-Frontends** – reines HTML,
   ≈ 2 KB JavaScript statt eines React-Pakets auf jeder Seite, keine Bindung an den
   ERP-Root-Layout. Astro 7 verlangt Node ≥ 22.12; die CI baut die Website darum mit
   Node 22, das ERP unverändert mit Node 20.
2. **Dieselbe Hosting-Site, zusammengeführte Ausgabe** – null neue Infrastruktur, null
   Zusatzkosten; ein Kollisionswächter schützt die ERP-Pfade.
3. **Formular über den bestehenden, isolierten Endpunkt** `POST /api/v1/contact` – kein
   ERP-Import, keine Tabelle, SMTP aus der Standardbibliothek, Zugangsdaten nur aus der
   Umgebung. Ohne sie: 503 und der sichere Rückfall.
4. **Eine Konfigurationsdatei** (`src/config/site.mjs`) für Name, Telefon, Adresse,
   Schalter, SEO – Texte setzen Werte mit `{{schlüssel}}` ein.
5. **Keine Fremddienste im Browser:** Schrift selbst gehostet, Karte als eigenes SVG,
   strenge Content-Security-Policy (Skripte nur von der eigenen Domain), Analytics aus.
6. **Phase 6 hat sieben Befunde behoben**, jeden aus einer Messung (Entscheidungen 20–28):
   ein Stylesheet statt vieler (LCP −0.6 s), Platz für alles, was JavaScript einblendet
   (CLS 0.073 → 0), gestapeltes Logo (die Kopfzeile passte nebeneinander in keine Breite),
   Seitenkopf-Regel für die Aktionsleiste, versteckt = nicht fokussierbar, Prüffristen als
   Blöcke auf dem Handy, lesbare Karte, Telefon-Symbol auf dem Tablet.

**Abweichungen vom Wortlaut des Auftrags, bewusst:**

- Der Claim «Schnell vor Ort. Sauber dokumentiert.» im Hero ist ersetzt durch «Aus der
  Region, mit Bericht zu jeder Arbeit.» und als `[[PRÜFEN]]` markiert: «schnell» ist eine
  Zusage über die Reaktionszeit, und die ist selbst noch ein Platzhalter.
- Mono-Schrift = der System-Mono-Stapel des Design-Systems (0 Byte) statt einer zusätzlichen
  Webschrift – der Auftrag erlaubt das ausdrücklich, das Design-System hat es so entschieden.
- Favicon = das bestehende rote XX-Monogramm; die Wortmarke ist Text aus der Konfiguration
  (ein Namenswechsel ist eine Zeile). Beides als `[[PLATZHALTER: finales Logo]]` geführt.

## 3. Änderungen ausserhalb von `website/`

| Datei | Änderung | Warum zwingend |
|---|---|---|
| `backend/app/routers/contact.py` | neu geschrieben: Anfrage-Endpunkt | das Formular braucht eine Verarbeitung; die Datei war schon der isolierte Endpunkt der öffentlichen Website, registriert in `main.py` (dort keine Änderung) |
| `backend/app/assets/website_contact.json` | neu, generiert | die E-Mails sprechen die Wörter der Website |
| `backend/tests/test_contact.py` | neu, 19 Wächter | Prüfung des Endpunkts in der CI |
| `backend/openapi.json`, `frontend/src/types/api.ts` | regeneriert | die CI verlangt, dass sie zum Backend passen |
| `frontend/src/app/(public)/` – Start, Über uns, Kontakt, Impressum, Datenschutz | gelöscht | durch die Website ersetzt; zwei Fassungen derselben Seite wären zwei Wahrheiten |
| `frontend/src/app/robots.ts`, `frontend/public/robots.txt` | gelöscht | die Website liefert die eine `robots.txt` |
| `frontend/src/lib/api.ts`, 4 UI-Bausteine, `cookie-settings-link.tsx`, 3 Pakete | entfernt | hatten nur die gelöschten Seiten als Leser |
| `firebase.json` | 12 Weiterleitungen alter hs-steiner.ch-Pfade | nur Firebase kann sie ausführen |
| `.github/workflows/deploy-dev.yml`, `deploy-prod.yml` | Website-Prüfjob (dev); im Frontend-Job Website zuerst bauen (Node 22), nach dem ERP-Build zusammenführen | ohne diesen Schritt hätte die Domain keine Startseite mehr |
| `CLAUDE.md`, `backend/CLAUDE.md`, `frontend/CLAUDE.md` | Abschnitt «Website», Endpunkt, entfernte Seiten | jede Sitzung liest sie zuerst |

**Nicht angefasst:** ERP-Backend ausser dem Kontakt-Router, Datenbank, Modelle,
Migrationen, ERP-Frontend-Logik, Anmeldung, die globalen Header in `firebase.json`.
Die Seiten im ERP (`/login`, `/konto`, `/erp`, `/agb`) zeigen weiterhin ihre bisherigen
Texte – bewusst, sie gehören nicht zum Auftrag.

## 4. Testergebnisse

Alle Messungen am Endstand dieses Berichts, lokal gegen den echten Build. Ausgeliefert mit
**superstatic** – der Engine, die auch der Firebase-Emulator benutzt (gleiche `cleanUrls`,
Weiterleitungen und Header wie `firebase.json`), mit Kompression.

| Prüfung (Auftrag 17.1) | Werkzeug | Ergebnis |
|---|---|---|
| Build in beiden Modi | `npm run build` | «preview» grün; «live» bricht an den 135 offenen Markierungen ab, `dist` bleibt unberührt ✔ |
| Inhalt ohne JavaScript | curl, je Seite Status, H1, Wortzahl, seitentypische Inhalte | 24/24 vollständig ✔ |
| HTML-Validierung | Nu Html Checker (vnu) | 0 Fehler auf 24 Seiten ✔ |
| Interne Links, JSON-LD, Sitemap, robots, llms | `check-site.mjs` (18 Fehlerformen gegengeprüft, jede meldet) | in Ordnung ✔ |
| Barrierefreiheit | axe-core 4 (WCAG 2.0/2.1/2.2 A+AA + Best Practice), je Seite mobil und Desktop | 0 Verstösse ✔ |
| Klickflächen, Überlauf | eigene Messung bei 360 · 390 · 768 · 1024 · 1280 · 1440 · 2560 px | 0 Bedienelemente unter 44 × 44 px (Knöpfe, Navigation, Auswahl, Telefon- und E-Mail-Links; Textlinks im Fliesstext ausgenommen, WCAG 2.5.8) · 0 px waagrechter Überlauf ✔ |
| Layout-Verschiebung | Chromium, CPU ×4, langsames Netz, schlimmster Fall | CLS 0 auf allen 24 Seiten, mobil und Desktop ✔ |
| Lighthouse mobil (Vorschau) | Lighthouse, Standard-Drosselung, 8 Seiten | Leistung 99–100 · Barrierefreiheit 100 · Best Practices 100 · LCP 1.5–1.8 s · TBT 0 ms · CLS 0. SEO 66 – allein wegen des gewollten `noindex` der Vorschau |
| Lighthouse mobil (Live-Simulation) | wie oben, Build mit `index, follow` und Live-`robots.txt` | Leistung 99–100 · SEO 100 · alles andere 100 ✔ |
| Content-Security-Policy | Chromium, jede Seite | 0 Verstösse ✔ |
| Formular | Playwright gegen den echten Endpunkt und einen lokalen SMTP-Briefkasten | 25/25 (Erfolg, Pflichtfelder, Vorbelegung, Foto, Bestätigung, Betreff, Reply-To, zu schnell, ohne JS) + 5/5 Störungsfall (Mailserver aus: Rückfall erscheint, Eingaben bleiben, `mailto:` vorausgefüllt, `INQUIRY_UNSENT` im Log) ✔ |
| Endpunkt | pytest, 19 Wächter (jeder gegen seine Fehlerform gegengeprüft) | 19/19 ✔ |
| ERP unberührt | ganze Backend-Suite gegen PostgreSQL 16; Frontend: TypeScript, ESLint, Unit-Tests, Build; generierte Typen | 648 bestanden (2 übersprungen) · alles grün · Typen aktuell ✔ |
| Weiterleitungen | curl gegen superstatic | 16/16 alte Pfade → 301 → Seite mit 200 ✔ |
| Ansichten | Ganzseiten-Aufnahmen, gesichtet | alle 24 Seiten bei 390 px, Kernseiten bei 360 · 768 · 1024 · 1280 · 1440 · 2560 px; 7 Befunde behoben |
| Texte | Suche nach den verbotenen Wörtern (8.2), Ausrufezeichen, Emojis, ß, «»-Regel, Uhrzeit-/Betragsform, Du-Form; Lektüre | keine Fundstelle; jede Tatsachenbehauptung ohne Beleg im Auftrag trägt eine Markierung |
| Anti-KI-Look (9.7) | CSS-Prüfung + Sichtung | keine Verläufe, keine Unschärfe, kein Glas, keine Icon-Kreise, keine hochzählenden Zahlen, keine Karussells; Bewegung nur Einblenden und Kranbahn-Linie, bei `prefers-reduced-motion` aus |
| Deploy-Ablauf | lokal nachgestellt: frischer ERP-Build → Website zusammenführen | 49 Dateien übernommen, ERP-Seiten unberührt, 404 und robots.txt bewusst von der Website ✔ |

**5-Sekunden-Test** (Startseite, erste Ansicht 390 × 844 und 1440 × 900):

| Zielgruppe | Findet sie … | Ergebnis |
|---|---|---|
| Fuhrparkleiter | Fahrmischer-Service und Telefon? | ✔ H1 nennt «Fahrmischer-Reparatur», Kachel «Fahrmischer-Service», Telefon im Hero und in der Kopfzeile |
| Landwirt | dass sein HS-Kran weiter betreut wird? | ✔ mit einer Einschränkung: die Ankündigung «HS Steiner heisst jetzt INEXXIO. Gleiches Team, gleiche Nummer.» steht ganz oben; der Satz «Service und Ersatzteile für alle HS-Krananlagen» folgt in der Übergabe-Sektion direkt unter dem Hero – auf dem Handy nach einmal Scrollen. Von März bis Mai kommt die Saison-Aktion «Heukrane» dazu |
| Instandhaltungsleiter | was die Prüfpflicht verlangt und wie man bucht? | ✔ Kachel «Kran prüfen lassen» in der ersten Ansicht → Tabelle, Prüfpflicht-Check und Formular auf einer Seite |
| Bestandskunde | was sich durch die Übergabe ändert? | ✔ Ankündigung «Mehr erfahren» → `/uebergabe` mit «Was bleibt / Was neu ist» und Fragen |

### Nicht geprüft – und warum

- **Externe Links** (Fedlex, Suva, SECO, EUR-Lex, BUL, Google Maps): die Netzwerkrichtlinie
  dieser Umgebung sperrt diese Adressen. Sie stehen in der Start-Checkliste.
- **Echte Geräte und andere Browser-Engines:** gemessen wurde mit Chromium (Desktop- und
  Mobil-Emulation). Safari/iOS und Firefox sind nicht geprüft.
- **Echter Mailversand:** geprüft gegen einen lokalen SMTP-Briefkasten, nicht gegen den
  künftigen Anbieter – es gibt noch keine Zugangsdaten.
- **Firebase in Produktion:** lokal mit der Engine des Emulators nachgestellt, nicht auf
  der echten Domain.
- **Bildschirmleser von Hand:** geprüft sind Struktur und ARIA mit axe; ein Durchgang mit
  VoiceOver/NVDA steht aus.
- **Fotos:** es gibt noch keine – Bildgrössen, Zuschnitte und die Leistung mit echten
  Bildern sind darum nicht gemessen (das Gerüst – feste Masse, `srcset`, Lazy Loading,
  `fetchpriority` – steht und ist im Platzhalter-Fall geprüft).

## 5. Offene Punkte (Zusammenfassung)

Vollständig und mit Fundstelle in `OFFENE_PUNKTE.md` (wird bei jedem Build neu geschrieben):

| Gruppe | Anzahl | Beispiele |
|---|---|---|
| Entscheidungen | 26 | Domain, Antwortzeit, Reaktionszeit, Pikett weiterführen und Zeiten, Preise (Abo, Prüfung, Teile), neue E-Mail-Adresse, UID, Analytics-Anbieter, WhatsApp, finales Logo |
| Inhalte und Freigaben | 64 | Zitat und Rolle von Heiri Steiner, «gleiches Team», Namen der Ansprechpartner, Zusagen, Abo-Bedingungen, Lager für ältere Typen |
| Fachlich/rechtlich | 19 | Prüfpflicht-Tabelle und -Check, Ratgeber-Artikel, Maschinenverordnung, laufende Verträge, Impressum, Datenschutz |
| Fotos | 22 | mit Bildbeschreibung je Stelle – Empfehlung: ein professioneller Fototag |
| Abgeschaltete Sektionen | 5 | Referenzen, Vorher/Nachher, Team, Stelleninserat, WhatsApp |

## 6. Start-Checkliste

**Vor dem Umschalten**

- [ ] Freigabe von Heiri Steiner: Texte, Zitat, Fotos, Namenswechsel
- [ ] Fototag; Fotos in `src/config/photos.mjs` eintragen
- [ ] alle Markierungen erledigt (`OFFENE_PUNKTE.md` leer), dann `SITE_MODE=live` und
      `SITE_URL=https://<Domain>` im Produktions-Workflow (`deploy-prod.yml`)
- [ ] Mailversand einrichten: `INQUIRY_SMTP_HOST`, `INQUIRY_SMTP_PORT`, `INQUIRY_SMTP_USER`,
      `INQUIRY_SMTP_PASSWORD` (Secret Manager), optional `INQUIRY_MAIL_TO`, `INQUIRY_MAIL_FROM`,
      `INQUIRY_SMTP_SSL` – als Umgebung des Cloud-Run-Dienstes; ohne sie zeigt das Formular
      Telefon und `mailto:`
- [ ] `firebase.json`: der `/api/**`-Rewrite zeigt heute für **beide** Umgebungen auf
      `inexxio-backend-dev` – für die Produktion den Produktionsdienst eintragen (betrifft
      ERP und Formular gleichermassen)
- [ ] Externe Links einmal von Hand öffnen (Quellen in Prüfpflicht, Ratgeber, Modernisierung)
- [ ] Test auf iPhone (Safari) und Android (Chrome)

**Beim Umschalten**

- [ ] Domain mit Firebase Hosting verbinden; hs-steiner.ch per 301 auf die neue Domain
      weiterleiten; die 12 Pfad-Weiterleitungen sind aktiv, sobald die Domain auf die Site zeigt
- [ ] Formular in Produktion einmal ausfüllen (Anfrage und Bestätigung kommen an)
- [ ] Google Search Console und Bing Webmaster Tools: Domain bestätigen, `sitemap.xml`
      einreichen, bei Domainwechsel die Adressänderung melden; Alt-URLs mit dem
      Abdeckungsbericht abgleichen (die Liste in `WEBSITE_PLAN.md` §5 stammt aus der Suche)

**Ausserhalb der Website**

- [ ] Google-Unternehmensprofil umbenennen («INEXXIO – ehemals HS Steiner»), Bing Places,
      Apple Business Connect, local.ch/search.ch, LinkedIn – überall derselbe Name
- [ ] E-Mail-Weiterleitungen der bisherigen Adressen und neue Signaturen
- [ ] Analytics-Anbieter wählen (cookielos), dann Datenschutzerklärung anpassen

## 7. Laufende Kosten

0 CHF zusätzlich für Hosting, Formular-Endpunkt, Schrift, Karte und Icons (alles vorhanden
bzw. selbst gehostet). Offen sind nur die Kosten des Mail-Postfachs für den Versand
(bestehendes Hosting oder ein Gratis-Kontingent reicht) und – falls gewählt – der
Analytics-Anbieter.
