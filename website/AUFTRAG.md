<!-- Der Auftrag, Fassung 2 (04.10.2026) – ersetzt die erste Fassung vom 03.10.2026 vollständig.
     Unverändert abgelegt, damit er nach einer Unterbrechung erneut gelesen werden kann
     (Kapitel 0). Was sich gegenüber der ersten Fassung geändert hat und wie es umgesetzt ist:
     WEBSITE_PLAN.md, Abschnitt «Umbau v2». -->

# Auftrag: Neue Website INEXXIO – ehemals HS Steiner

> **Für Claude Code.** Lies dieses Dokument vollständig, bevor du beginnst. Es liegt als Datei im Repository. Lies es jederzeit erneut, wenn du unsicher bist oder dein Kontext komprimiert wurde.

---

## 0. Arbeitsweise

- **Nimm dir ausdrücklich so viel Zeit, wie du brauchst.** Gründlichkeit vor Tempo. Der Auftrag ist erst fertig, wenn alles in diesem Dokument umgesetzt, geprüft und dokumentiert ist.
- **Keine Abkürzungen.** Keine leeren Seiten, keine TODO-Stubs, kein Lorem ipsum. Fehlt eine Information, setzt du einen markierten Platzhalter (Kapitel 5.5) und baust alles andere vollständig.
- **Arbeite in Phasen** (Kapitel 17). Nach jeder Phase: Build grün, Commit, Fortschritt in `WEBSITE_PLAN.md` abhaken. So kannst du nach einer Unterbrechung nahtlos weitermachen.
- **Selbstständig entscheiden** nach den Grundsätzen in Kapitel 1 und jede Entscheidung im Plan in einem Satz begründen. **Anhalten und fragen** nur, wenn du an eine Grenze aus Kapitel 2 stösst.
- **Weniger, aber stark.** Lieber eine Sektion weniger, dafür jede mit klarem Zweck. Die Seite muss leicht sein und man muss sich sofort zurechtfinden.

---

## 1. Drei Grundsätze – gelten immer gleichzeitig

1. **Es muss funktionieren.** Extrem stabil und robust. Keine fragilen Tricks, keine Abhängigkeit von Diensten, die ausfallen oder teuer werden können.
2. **So einfach wie möglich.** Vor jeder Lösung fragen: Was ist das eigentliche Ziel? Gibt es einen einfacheren Weg dorthin?
3. **So günstig wie möglich, so teuer wie nötig.** Laufende Kosten, Pflegeaufwand und Abhängigkeiten zählen mit.

Verletzt eine Lösung einen der drei Punkte, ist sie keine Lösung.

---

## 2. Harte Grenzen

1. **Das ERP ist der Master und seine Logik bleibt unberührt.** Fachlogik, Datenmodell, Prozesse, Module und Migrationen des ERP werden weder geändert noch refaktoriert noch «nebenbei verbessert». Die Website spiegelt nur, was das ERP vorgibt. Sie hält keine eigenen Kopien von Benutzern, Rechten oder Stammdaten.
2. **Login, Profil und ERP-Zugang bestehen bereits.** Sie werden übernommen und in das neue Design eingebettet, nicht neu gebaut (Kapitel 6).
3. **Schnittstellen zum ERP:** Kleine, rein lesende, additive Schnittstellen sind erlaubt, wenn die Website sie zwingend braucht (z. B. «Wer ist eingeloggt und darf was?»). Jede davon steht vorher im Plan und wird im Bericht dokumentiert. Alles, was darüber hinausgeht (schreibende Zugriffe, Änderungen an Auth-Logik, Rechten, Sessions, Datenbank): **anhalten, Optionen darlegen, fragen.**
4. **Nichts erfinden, was als Tatsache gilt.** Keine erfundenen Zahlen, Kunden, Zitate, Bewertungen, Zertifikate, Preise, Reaktionszeiten oder Zusagen. Fehlt etwas: Platzhalter. Fachliche und rechtliche Aussagen: als «zu prüfen» markieren.
5. **Keine vertraulichen Angaben.** Kein Kaufpreis, keine Vertragskonditionen, kein Umsatz, kein aktueller Arbeitgeber von Clemens Fritsche, keine privaten Handynummern (auch nicht die bisherige Nummer von Heiri Steiner).
6. **Kein Shop.** Der Shop kommt später als Spiegelung des ERP. Jetzt nichts davon bauen, nur die Struktur so anlegen, dass er später ohne Umbau Platz hat (Kapitel 6.4).
7. **Git:** eigener Branch `website`. Kein Force-Push, kein Merge in den Hauptbranch ohne Freigabe.

---

## 3. Ausgangslage

### 3.1 Das Unternehmen

- **HS STEINER Fahrzeug- und Kranbau GmbH**, Waldweg 1, 9546 Tuttwil (Wängi TG).
- **1982:** Heiri Steiner baut die Reparaturwerkstätte in Tuttwil-Wängi und macht sich selbstständig.
- **Seit 1985:** eigene Krananlagen für Landwirtschaft und Industrie, vermarktet in der Schweiz, in Deutschland, Österreich und im Südtirol. Vorwiegend Sonderanfertigungen.
- **GmbH seit 1993** `[[PRÜFEN: Gründungsjahr der GmbH]]`.
- Grosses Lager an Ersatz- und Kranteilen (Greifer, Ausleger, Fahrwerke, Drehtürme).
- Fahrmischer-Service für viele Marken: Intermix, Putzmeister, Cifa, Stetter, Liebherr, Belmix, Peter.
- Kundenstamm bis zurück ins Jahr 1982, darunter grössere Bau- und Kiesunternehmen `[[PLATZHALTER: Referenzkunden nur mit schriftlicher Freigabe nennen]]`.
- Bisherige Website hs-steiner.ch: veraltet, unübersichtlich, rund 15 Rubriken mit vielen Nebensparten. **Nur als Faktenquelle nutzen, nicht als Vorbild.**

### 3.2 Die Übernahme

- Heiri Steiner übergibt sein Unternehmen an **Clemens Fritsche**.
- Die Firma tritt neu als **INEXXIO AG** auf, **immer mit dem Zusatz «ehemals HS Steiner»**.
- Heiri Steiner bleibt in einer befristeten Übergangszeit beratend dabei `[[PRÜFEN]]`. Alle Elemente dazu müssen später mit einem Schalter in der Konfiguration entfernt werden können.
- **Clemens Fritsche:** Maschinenbauingenieur, Produktentwicklung bei Liebherr (Baumaschinen), Produkt- und Plattformmanagement im IoT-Umfeld, betriebswirtschaftliche Weiterbildung. `[[PLATZHALTER: genaue Titel und Abschlüsse, Porträtfoto, LinkedIn-Link]]`
- **Namensrisiko:** «INEXXIO» klingt am Telefon wie «inexio» (deutscher Telekom-/Glasfaseranbieter). Darum steht der Name auf der Website nie allein, sondern bei der ersten Nennung immer mit «ehemals HS Steiner».

### 3.3 Ausrichtung: drei Bereiche

Die Firma stellt sich **breiter** auf, damit Kunden sich schnell zuordnen können und das Unternehmen nicht eingeengt wird. Oben stehen drei Bereiche, darunter die Spezialisierungen. Jeder Bereich hat dieselben drei Ebenen: **Lösungen · Service & Reparatur · Ersatz- und Verschleissteile.**

**Gewichtung:** Krantechnik und Fahrzeugtechnik gleichwertig. Sonderlösungen etwas darunter.

**A) Krantechnik** – aktiv verkaufen, Neuanlagen und Service
1. **Heukrananlagen** (an erster Stelle): Neuanlagen nach Mass, Ausbau und Umbau bestehender Anlagen, Service, Ersatzteile. Bauformen: Einschienenkran, Brückenkran, Drehkran hydraulisch, an das Gebäude angepasste Anlagen.
2. **Industriekrane:** Brücken-, Hänge-, Schwenk- und Drehkrane für Gewerbe, Industrie und Gemeinden. Neuanlagen und Service für Krane aller Marken.
3. **Prüfung & Wartung:** jährliche Überprüfung, Wartung, Dokumentation.
4. **Modernisierung:** Funkfernsteuerung, Frequenzumrichter, Überlastsicherung, Steuerung, Greifer.

Die Bezeichnung «HS» wird nicht mehr als Produktname verwendet. Es sind schlicht Krananlagen von INEXXIO. Besitzer bestehender HS-Anlagen finden den Hinweis, dass ihre Anlage weiter betreut wird, im Fliesstext, in den FAQ und auf der Übergabe-Seite – ohne eigenen Menüpunkt.

**B) Fahrzeugtechnik** – Service, Reparatur, Teile (keine Neuaufbauten)
1. **Fahrmischer:** Service, Reparatur und Trommel-Revision aller gängigen Marken, besonders im Winter.
2. **Reparatur & Service von Aufbauten:** LKW-Aufbauten, Mulden und Kipper, Hydraulik, Baustellenfahrzeuge `[[PRÜFEN: genauer Umfang]]`.
3. **Verschleiss- & Ersatzteile:** Rinnen, Schurren, Spiralschutz und weitere Teile ab Lager `[[PRÜFEN: Teileliste, Material, passende Typen]]`.

**C) Sonderlösungen** – Maschinenbau im weiteren Sinn, Richtung Baumaschinen
1. **Konstruktion & Engineering:** Entwicklung und Konstruktion von Sonderlösungen, Berechnung, Dokumentation.
2. **Schweiss- & Stahlbau:** Stahlkonstruktionen, Schweissarbeiten, Einzelanfertigungen.
3. **Baumaschinen: Umbau & Reparatur:** Umbauten, Nachrüstungen, Anbauteile, Reparaturen.

Ton: «Sie haben ein Problem, für das es kein Produkt von der Stange gibt? Wir konstruieren und bauen die Lösung.» Grossprojekte nicht aktiv bewerben, die Werkstatt ist klein.

**Entfällt** (nicht mehr bewerben, alte URLs per Redirect auffangen, siehe Kapitel 14)
- Haus & Garten, Motorgeräte, Pflanzenschutz, Pflanzenbehälter, Transportwagen
- Reifenservice, Reparaturen von PW und Transportern
- Hebebühnen-Vermietung
- Trailer, Neuaufbauten, Fahrzeughandel
- Events & Oldtimer
- Geländer und Verglasung

**Vorerst nicht auf der Website:** Service-Abo, digitales Kranbuch, Shop.

### 3.4 Zielgruppen

| Zielgruppe | Wer entscheidet | Was sie brauchen |
|---|---|---|
| Landwirte mit Heukran oder Bedarf an einer neuen Anlage | Betriebsleiter | Anlage nach Mass, läuft in der Heusaison, Ersatzteile, persönlicher Kontakt |
| Produktions- und Gewerbe-KMU mit Hallenkranen | Instandhaltungs-/Betriebsleiter, Inhaber | Prüfpflicht erfüllen, keine Ausfälle, schnelle Reaktion, saubere Dokumentation. Grosse Hersteller sind langsam und teuer. |
| Betonwerke, Bau- und Transportunternehmen | Fuhrpark-/Werkstattleiter | Kurze Standzeiten, alle Marken an einem Ort, Teile ab Lager |
| Bau- und Industriebetriebe mit Sonderwünschen | Inhaber, Technischer Leiter | Jemand, der konstruiert, baut und dokumentiert |
| Bestandskunden von HS Steiner | – | «Was ändert sich für mich?» → Kontinuität plus mehr Möglichkeiten |
| Fachkräfte | Mechaniker, Servicetechniker | Gute Arbeit, faire Firma. Techniker sind der Engpass im Markt. |

### 3.5 Positionierung

**Kernidee:** So schnell wie der Handwerker aus der Region, so durchdacht und sauber dokumentiert wie der Hersteller.

**Claim (Vorschlag):** «Krane. Fahrzeuge. Sonderlösungen. Aus einer Werkstatt mit Ingenieurwissen.» `[[PRÜFEN]]`

**Belege, die die Seite liefern muss:**
- Ingenieur-Know-how (Liebherr-Hintergrund)
- über 40 Jahre Erfahrung am Standort
- eigene Krananlagen seit 1985
- alle Marken im Service
- Ersatzteillager vor Ort
- Notfallnummer `[[PRÜFEN]]`

---

## 4. Ziel der Website und Erfolgsmessung

**Hauptziel: Aufträge.** Jede Seite führt zu einer Anfrage oder einem Anruf.

**Nebenziele:**
- Bestandskunden halten (Vertrauen in die Übergabe)
- unter neuem **und** altem Namen gefunden werden (Google, Bing, KI-Assistenten)
- Fachkräfte gewinnen
- eingeloggte Nutzer finden mit einem Klick ihr Profil, ihre Aufträge und – mit Berechtigung – das ERP

**Regel:** Jede Seite hat genau eine Hauptaktion. Telefon und Anfrage sind von überall mit einem Klick erreichbar.

**Messpunkte** (über einen neutralen `track()`-Helper, Kapitel 15): `form_start`, `form_submit` (mit Bereich und Dringlichkeit), `tel_click`, `notfall_click`, `mailto_click`, `part_inquiry`.

---

## 5. Technik

### 5.1 Phase 0: Analyse vor dem Bauen (nur lesen)

Analysiere das Repository gründlich:
- Stack, Ordnerstruktur, Deploy-Pipeline, Hosting
- **die bestehende öffentliche Startseite, das Login, die Profileinstellungen und wie das ERP heute im Menü erscheint** (aktueller Code und, falls entfernt, die Git-Historie: `git log`, `git log -S`, alte Branches)
- das bestehende Header-Design mit Login- und Profilmenü (dient als Vorlage, siehe Kapitel 6)
- wie Sessions und Rechte funktionieren und wie die Rolle/Berechtigung «ERP» geprüft wird
- welche Routen unter der Domain belegt sind (u. a. `/erp`)
- bestehende Design-Tokens (Rot, Schwarz, Inter)
- vorhandene Möglichkeiten für Mailversand

**Ergebnis:** `WEBSITE_PLAN.md` mit Ist-Zustand, gewählter Architektur samt Begründung nach Kapitel 1, Liste aller geplanten ERP-Schnittstellen und aller Änderungen ausserhalb des Website-Bereichs, Phasen-Checkliste. Danach selbstständig weiter, ausser eine Grenze aus Kapitel 2 ist betroffen.

### 5.2 Architektur

**Rahmen:**
- Website, Login, Profil und ERP laufen **unter derselben Domain**, nur mit unterschiedlichen Pfaden (z. B. `/`, `/krantechnik/…`, `/anmelden`, `/profil`, `/erp`).
- Die öffentlichen Seiten bilden einen **klar abgegrenzten Website-Bereich** im Repo (eigener Ordner, eigene Komponenten, eigene Inhalte). Kein Website-Code mischt sich in ERP-Module.
- **Pflicht:** Jede öffentliche Seite liefert ihren vollständigen Inhalt als HTML in der Server-Antwort, ohne JavaScript. Prüfbar per `curl`. Keine Client-only-SPA für öffentliche Seiten.

**Wahl der Umsetzung (in Phase 0 entscheiden und begründen):**
- **Variante A – im bestehenden Frontend:** Die öffentlichen Seiten werden im bestehenden Web-Frontend gebaut, das schon Login, Profil und Header enthält. Nur wählen, wenn dieses Frontend vollständiges HTML serverseitig oder statisch ausliefern kann (SSR/SSG). Vorteil: ein Header, eine Session, kein Doppelaufwand.
- **Variante B – eigenes statisches Teilprojekt (z. B. Astro):** Die Website wird statisch generiert und unter derselben Domain ausgeliefert. Der Header ist für alle gleich; der Anmeldezustand wird nach dem Laden über eine kleine, rein lesende Schnittstelle abgefragt (Kapitel 6.3). Login, Profil und ERP bleiben, wo sie sind.

Wähle die Variante, die die drei Grundsätze am besten erfüllt. Im Zweifel die mit weniger beweglichen Teilen.

**Allgemein:**
- JavaScript auf öffentlichen Seiten nur für: Mobile-Menü, Header-Verhalten, Anmeldezustand, Reveal-Animationen, Formular-Komfort, Prüfpflicht-Check, Vorher/Nachher-Regler. Alles funktioniert auch ohne JS.
- Minimale Abhängigkeiten. Keine Animations-Library, kein zusätzliches UI-Kit. Eigenes schlankes CSS mit Custom Properties.
- **Kein CMS.** Inhalte liegen in Dateien im Repo.

### 5.3 Eine Quelle für alles (Single Source of Truth)

Eine Konfigurationsdatei (z. B. `site.config.ts`) im Website-Bereich enthält alles, was mehrfach vorkommt. Header, Footer, Kontaktseite, JSON-LD, `llms.txt`, Sitemap und E-Mail-Vorlagen lesen **ausschliesslich** daraus. **Ein Namenswechsel muss in dieser einen Datei in Minuten möglich sein.**

Seitentexte liegen in Markdown/MDX bzw. Content-Dateien, getrennt von den Layout-Komponenten. Auch die Bereiche und ihre Unterseiten (Kapitel 3.3) sind dort als Datenstruktur definiert, damit Navigation, Übersichten und Footer automatisch daraus entstehen.

**Startwerte:**

| Feld | Wert |
|---|---|
| Markenname | INEXXIO |
| Rechtlicher Name | INEXXIO AG `[[PRÜFEN: Eintrag im Handelsregister]]` |
| Ehemals-Zeile | «ehemals HS Steiner» |
| Frühere Namen (alternateName) | «HS Steiner», «HS Steiner Fahrzeug- und Kranbau GmbH», «HS Krananlagen» |
| Domain | `[[PLATZHALTER: Domain]]` (hs-steiner.ch wird später weitergeleitet) |
| Telefon | +41 52 378 22 47 (Anzeige: 052 378 22 47) |
| Notfallnummer | +41 76 563 22 47 `[[PRÜFEN: weiterführen? erreichbar wann?]]` |
| E-Mail | `[[PLATZHALTER: neue Adresse]]` (fahrzeug-kranbau@hs-steiner.ch bleibt als Weiterleitung) |
| Öffnungszeiten | Mo–Fr 7.00–12.00 und 13.15–17.30 Uhr `[[PRÜFEN]]` |
| Adresse | Waldweg 1, 9546 Tuttwil (Wängi TG) |
| Koordinaten | 47.4836, 8.9357 `[[PRÜFEN]]` |
| Einsatzgebiet | Ostschweiz, Raum Winterthur/Zürich, Schaffhausen `[[PRÜFEN]]`. Krananlagen auch in Deutschland, Österreich und Südtirol `[[PRÜFEN]]` |
| UID | `[[PLATZHALTER: UID]]` |

### 5.4 Begriffe

- **Nicht verwenden:** «Pikett». Stattdessen allgemein verständlich: **«Notfall-Service»** bzw. **«Notfallnummer»**.
- Bereiche immer gleich benennen: **Krantechnik · Fahrzeugtechnik · Sonderlösungen**.

### 5.5 Platzhalter-System

**Zwei Markierungen:**
- `[[PLATZHALTER: …]]` – Information fehlt.
- `[[PRÜFEN: …]]` – Text oder Fakt ist vorhanden, muss aber von Clemens freigegeben oder fachlich/rechtlich geprüft werden.

**Darstellung im Modus `preview`:** sichtbar, gelb gestrichelt umrandet, mit kleinem Label «Platzhalter» bzw. «Prüfen». Fehlende Bilder als `<ImagePlaceholder>`: grauer Rahmen im richtigen Seitenverhältnis, darin die Bildbeschreibung. Diese Beschreibungen sind gleichzeitig die Fotoliste.

**Prüfskript `check:content`:**
- findet alle Markierungen in Quellen und Build-Ausgabe
- schreibt `OFFENE_PUNKTE.md`, gruppiert nach: Entscheidungen · Inhalte und Freigaben · Fotos · Fachlich/Rechtlich. Pro Eintrag: Seite, Stelle, was gebraucht wird.
- Ein Build im Modus `live` bricht ab, solange noch Markierungen existieren.

**Sektionen ohne echten Inhalt** (Referenzen, Vorher/Nachher, Teamfotos, Stelleninserat) sind in der Konfiguration mit `enabled: false` abgeschaltet und erscheinen in `OFFENE_PUNKTE.md`.

### 5.6 Modus (SITE_MODE)

- **`preview` (Standard):** `<meta name="robots" content="noindex, nofollow">`, `robots.txt` mit `Disallow: /`, Markierungen sichtbar, Analytics aus.
- **`live`:** indexierbar, Markierungsprüfung strikt, Analytics an (falls konfiguriert).

---

## 6. Konto, Profil und ERP-Zugang

### 6.1 Grundprinzip

- **Ein Login für alle:** Kunden, Partner und Mitarbeitende melden sich gleich an – wie auf jeder Website, auf der man bestellt oder Aufträge verfolgt.
- Nach dem Login gibt es ein **Konto** mit Profileinstellungen und (später) Bestellungen und Aufträgen.
- **Das ERP ist nur ein Bereich davon**, sichtbar ausschliesslich für Personen mit der entsprechenden Berechtigung.
- **Das ERP ist die Wahrheit.** Benutzer, Rollen, Rechte, Aufträge und Bestellungen kommen aus dem ERP. Die Website zeigt sie nur an.

### 6.2 Was übernommen wird

- **Login, Registrierung (falls vorhanden), Passwort vergessen, Profileinstellungen und der ERP-Einstieg bestehen bereits.** Übernimm sie funktional unverändert.
- Passe nur ihr **Erscheinungsbild** an, damit sie im neuen Header und Design nahtlos wirken (gleicher Header, gleiche Schriften, Farben, Abstände). Keine Änderung an Logik, Validierung oder Datenfluss.
- **Orientiere dich am bisherigen Design** von Startseite, Header und Profilmenü (aktueller Code oder Git-Historie). Es war gut. Übernimm daraus, was funktioniert hat, insbesondere die Platzierung von «ERP» in der Menüleiste und das Profilmenü.

### 6.3 Anmeldezustand im Header

- **Nicht eingeloggt:** Link «Anmelden».
- **Eingeloggt:** Name bzw. Initialen mit Dropdown: Profil · Meine Aufträge · Meine Bestellungen (beide nur, wenn im ERP schon vorhanden, sonst ausblenden) · **ERP** (nur mit Berechtigung) · Abmelden.
- **Mit ERP-Berechtigung** steht zusätzlich ein eigener Punkt **«ERP»** direkt in der Menüleiste, wie bisher.
- Der Zustand kommt immer aus der bestehenden Session des ERP. Bei Variante B (Kapitel 5.2) über eine kleine, rein lesende Schnittstelle, z. B. `GET /api/session/me` → `{ eingeloggt, name, initialen, rechte: { erp: true/false } }`. Gibt es eine solche Schnittstelle schon, nutze sie.
- **Seiten-Cache beachten:** Öffentliche Seiten bleiben für alle identisch und cachebar. Der persönliche Teil des Headers wird erst im Browser eingesetzt (kleines Script). Ohne JS oder bei Fehler der Schnittstelle zeigt der Header schlicht «Anmelden». Kein Layout-Sprung: Der Platz ist reserviert.
- Die Berechtigung wird **nur angezeigt**, nie auf der Website durchgesetzt. Der Schutz von `/erp` und `/profil` liegt weiterhin vollständig beim ERP.

### 6.4 Vorbereitung für später (jetzt nicht bauen)

- **Shop:** Unter `/shop` wird später ein Shop als Spiegelung der ERP-Artikel entstehen. Jetzt: Pfad reservieren, nichts anlegen, keine Navigation.
- **Verschleiss- und Ersatzteile:** Jetzt als Anfrage-Katalog aus einer Datei im Website-Bereich (Kapitel 7.3). Datenstruktur so wählen, dass sie später 1:1 aus dem ERP gefüllt werden kann (Artikelnummer, Bezeichnung, passend für, Material, Bild).

---

## 7. Seiten

### 7.1 Navigation und Seitenstruktur

**Header (Desktop), zweizeilig:**

- **Obere Servicezeile** (schmal, 36 px, dunkel): links «HS Steiner heisst jetzt INEXXIO → Mehr erfahren» (per Konfiguration schaltbar). Rechts: «Notfall 076 563 22 47» · «052 378 22 47» · **ERP** (nur mit Berechtigung) · **Anmelden** bzw. Profilmenü.
- **Hauptzeile** (72 px, weiss): links Logo-Lockup (Wortmarke «INEXXIO», darunter klein «ehemals HS Steiner»). Mitte/rechts: `Krantechnik ▾` · `Fahrzeugtechnik ▾` · `Sonderlösungen ▾` · `Service ▾` · `Über uns` · `Kontakt` · Button **«Anfrage stellen»**.

**Mega-Dropdowns (schlicht):** Pro Bereich ein Panel mit den Unterseiten, je eine Zeile Beschreibung, plus ein Link «Alle Leistungen Krantechnik →» und ein kleines Foto. Öffnen per Hover und Klick, voll per Tastatur bedienbar, schliessen mit Esc.

**Verhalten:** Sticky. Beim Runterscrollen klappt die Servicezeile weg und die Hauptzeile bleibt; beim Hochscrollen erscheint alles wieder. Ab 8 px Scroll 1-px-Linie unten.

**Mobil:**
- Logo, Telefon-Icon, Burger. Burger öffnet ein Vollbild-Menü: Bereiche als Akkordeons, darunter Service, Über uns, Kontakt, dann Anmelden/Profil/ERP.
- **Feste Aktionsleiste unten** (erscheint nach dem Hero): `[Anrufen]` `[Anfrage]`, 56 px hoch.

**URLs** (Deutsch, ohne Umlaute):

```
/                                         Startseite
/uebergabe                                Aus HS Steiner wird INEXXIO

/krantechnik                              Bereich Krantechnik
/krantechnik/heukrananlagen               Heukrananlagen (Neuanlagen, Umbau, Service, Teile)
/krantechnik/industriekrane               Industriekrane (Neuanlagen, Service aller Marken)
/krantechnik/pruefung-wartung             Prüfung & Wartung (inkl. Prüfpflicht-Check)
/krantechnik/modernisierung               Modernisierung

/fahrzeugtechnik                          Bereich Fahrzeugtechnik
/fahrzeugtechnik/fahrmischer              Fahrmischer: Service, Reparatur, Trommel-Revision
/fahrzeugtechnik/aufbauten-reparatur      Reparatur & Service von Aufbauten
/fahrzeugtechnik/verschleiss-ersatzteile  Verschleiss- & Ersatzteile

/sonderloesungen                          Bereich Sonderlösungen
/sonderloesungen/konstruktion-engineering Konstruktion & Engineering
/sonderloesungen/schweiss-stahlbau        Schweiss- & Stahlbau
/sonderloesungen/baumaschinen             Baumaschinen: Umbau & Reparatur

/service                                  Service-Übersicht (Einstieg nach Anliegen)
/service/notfall                          Notfall-Service

/ueber-uns                                Clemens Fritsche, Team, Geschichte, Standort, Einsatzgebiet
/karriere                                 Stellen
/ratgeber                                 Übersicht Ratgeber
/ratgeber/[slug]                          Fachartikel
/kontakt                                  Anfrage, Telefon, Notfall, Anfahrt
/impressum
/datenschutz
/404

Bestehend, nur ins Design einbetten:  /anmelden  /profil  /erp  (exakte Pfade aus Phase 0)
Reserviert, nicht bauen:               /shop
```

Breadcrumbs auf allen Unterseiten.

### 7.2 Globale Elemente

**Saison-Hinweis** (aus der Konfiguration, mit Datumsbereich, als dezente Karte auf Startseite und passenden Seiten):
- November bis Februar: «Winter-Revision für Fahrmischer: Trommel und Aufbau überholen, solange der Bau ruht.»
- Januar bis April: «Neue Heukrananlage für die nächste Saison? Jetzt planen, damit sie vor dem ersten Schnitt läuft.»

**Footer** (dunkel)
- Spalte 1: Logo-Lockup und ein Satz, der das Unternehmen eindeutig beschreibt:
  > INEXXIO AG (ehemals HS Steiner Fahrzeug- und Kranbau GmbH) – Krantechnik, Fahrzeugtechnik und Sonderlösungen aus Tuttwil-Wängi TG. Seit 1982.
- Spalten 2–4: je ein Bereich mit seinen Unterseiten.
- Spalte 5: Adresse, Telefon, Notfallnummer, E-Mail, Öffnungszeiten.
- Unterste Zeile: © Jahr · Impressum · Datenschutz · UID · Anmelden.

### 7.3 Startseite (Reihenfolge verbindlich)

**1. Hero**
- Layout asymmetrisch: links Text (5–6 Spalten), rechts grosses echtes Foto. Kein Video, kein Slider.
- Eyebrow: «Tuttwil-Wängi TG · seit 1982»
- **H1:** «Krantechnik, Fahrzeugtechnik und Sonderlösungen aus der Ostschweiz»
- Lead: «Wir planen und bauen Krananlagen, warten und reparieren Fahrmischer und Aufbauten aller Marken und konstruieren Lösungen, die es nicht von der Stange gibt. Mit Ingenieurwissen und kurzen Wegen.»
- Buttons: **«Anfrage stellen»** (primär) · «052 378 22 47» (sekundär, `tel:`)
- Vertrauensleiste: «Seit 1982 · Eigene Krananlagen seit 1985 · Alle Marken im Service · Ersatzteillager vor Ort»

**2. Die drei Bereiche** (direkt unter dem Hero)
- Drei grosse Karten mit Foto. Krantechnik und Fahrzeugtechnik gleich gross nebeneinander, Sonderlösungen darunter als breite, flachere Karte (zeigt die Gewichtung).
- Jede Karte: Titel, ein Satz, die Unterseiten als Links, Pfeil «Zum Bereich».
  - **Krantechnik** – «Heukrananlagen und Industriekrane: neue Anlagen nach Mass, Prüfung, Wartung und Modernisierung.»
  - **Fahrzeugtechnik** – «Fahrmischer und Aufbauten aller Marken: Service, Reparatur, Trommel-Revision und Verschleissteile ab Lager.»
  - **Sonderlösungen** – «Konstruktion, Schweiss- und Stahlbau, Umbauten an Baumaschinen. Wenn es die Lösung nicht zu kaufen gibt.»

**3. Übergabe (prominent, dunkle Sektion)**
- Eyebrow: «Nachfolge geregelt»
- **H2:** «Aus HS Steiner wird INEXXIO.»
- Lead: «Nach über 40 Jahren übergibt Heiri Steiner sein Unternehmen an Clemens Fritsche. Gleiches Team, gleiche Telefonnummer, gleicher Standort – und neue Möglichkeiten.» `[[PRÜFEN]]`
- Grosses Foto: Clemens und Heiri gemeinsam vor der Werkstatt `[[PLATZHALTER: Foto]]`
- Zitat von Heiri Steiner `[[PLATZHALTER: mit Heiri formulieren und von ihm freigeben lassen. Kein erfundenes Zitat veröffentlichen.]]`
- Zwei Spalten:
  - **Was bleibt:** Standort Tuttwil-Wängi · Telefonnummer 052 378 22 47 · bekannte Ansprechpartner `[[PLATZHALTER: Namen nur mit Einverständnis]]` · Service und Ersatzteile für alle bestehenden HS-Krananlagen · laufende Verträge `[[PRÜFEN: rechtlich]]`
  - **Was neu ist:** der Name INEXXIO · Ingenieurwissen für Konstruktion und Modernisierung · Sonderlösungen · ein Konto für Kunden (später mit Aufträgen und Bestellungen)
- Links: «Die ganze Geschichte →» · «Fragen zur Übergabe →»

**4. Warum INEXXIO** (vier konkrete Belege, keine Icon-Kreise)
1. **Ingenieurwissen statt Rätselraten.** «Clemens Fritsche hat bei Liebherr Baumaschinen entwickelt. Wir verstehen, wie eine Maschine gebaut ist – nicht nur, wo sie klemmt.»
2. **Eigene Krananlagen seit 1985.** «Wir planen, bauen und montieren Krananlagen selbst. Dieses Wissen steckt auch in jedem Service.»
3. **Alle Marken, kurze Wege.** «Ein Ansprechpartner für Krane, Fahrmischer und Aufbauten. Ersatzteillager vor Ort, Notfallnummer für Stillstände.»
4. **Sauber dokumentiert.** «Jede Arbeit mit Bericht. Das zählt bei Versicherung und Suva – und ab 2027 auch bei Umbauten.» `[[PRÜFEN: fachlich]]`

Dazu ein kleines Porträt von Clemens mit einem Satz und Link auf `/ueber-uns`.

**5. Ausgewählte Arbeiten** (`enabled: false`, bis echte Projekte mit Fotos vorliegen)
- 3 Projekte, je Foto, Bereich, Titel, ein Satz Ergebnis. Kein Karussell.

**6. Einsatzgebiet (kompakt)**
- Statische SVG-Karte der Ostschweiz mit Standort und Gebiet. Kein Google-Maps-Embed.
- Ein Satz zu Regionen, Hinweis «Krananlagen auch in Deutschland, Österreich und Südtirol» `[[PRÜFEN]]`.

**7. Ratgeber**
- Drei Artikel-Teaser.

**8. Häufige Fragen** (native `<details>`/`<summary>`)
- «Wer betreut meine HS-Krananlage in Zukunft?» – «Wir. Service und Ersatzteile führen wir weiter, mit demselben Wissen und denselben Teilen ab Lager.»
- «Bauen Sie weiterhin neue Krananlagen?» – «Ja. Heukrananlagen und Industriekrane planen und bauen wir nach Mass.»
- «Bleibt die Telefonnummer gleich?» – «Ja, 052 378 22 47. Auch die bisherigen E-Mail-Adressen erreichen uns weiterhin.» `[[PRÜFEN]]`
- «Gelten bestehende Verträge weiter?» – «Ja. Das Unternehmen bleibt dasselbe, nur der Name ändert sich.» `[[PRÜFEN: rechtlich]]`
- «Welche Marken betreuen Sie?» – Krane aller Hersteller, Fahrmischer der genannten Marken.
- «Wie schnell sind Sie bei einem Stillstand vor Ort?» `[[PLATZHALTER: realistische Reaktionszeit]]`
- «Führen Sie noch Garten- und Motorgeräte oder Reifen?» – «Nein. Wir konzentrieren uns auf Krantechnik, Fahrzeugtechnik und Sonderlösungen.»

**9. Abschluss-CTA**
- **H2:** «Was steht bei Ihnen an?»
- Lead: «Beschreiben Sie Ihr Anliegen in zwei Minuten. Wir melden uns innert `[[PLATZHALTER: Antwortzeit]]`.»
- Kurzformular (Kapitel 11) plus Telefon und Notfallnummer daneben.

### 7.4 Bereichsseiten (`/krantechnik`, `/fahrzeugtechnik`, `/sonderloesungen`)

Alle drei mit derselben Struktur:

1. **Hero:** H1 (z. B. «Krantechnik: Heukrananlagen und Industriekrane»), Lead, Hauptaktion, Foto
2. **«Auf einen Blick»:** 2–3 sachliche Sätze: was, für wen, wo
3. **Die drei Ebenen** als klar getrennte Blöcke, jeweils mit Links auf die Unterseiten:
   - **Lösungen** (bei Fahrzeugtechnik entfällt Neubau; dort heisst die Ebene «Reparatur & Instandsetzung»)
   - **Service & Reparatur**
   - **Ersatz- und Verschleissteile**
4. **Unterseiten** als grosse Karten mit Foto
5. **Ablauf in vier Schritten** (Anfrage → Abklärung → Umsetzung → Bericht), verbunden durch die Kranbahn-Linie (Kapitel 9.6)
6. **FAQ** des Bereichs
7. **CTA-Block:** Kurzformular mit vorausgewähltem Bereich

### 7.5 Unterseiten (Vorlage)

1. **Hero:** H1 mit Suchbegriff, Lead mit Nutzen, Hauptaktion, Foto
2. **«Auf einen Blick»:** Faktenbox mit Für wen · Was wir tun · Was Sie erhalten
3. **Leistungsumfang:** klare Liste, technisch präzise
4. **Seiten-spezifisches Modul** (siehe unten)
5. **FAQ:** 4–6 echte Fragen der Zielgruppe
6. **CTA-Block:** Kurzformular, Bereich und Thema vorausgewählt
7. **Verwandte Leistungen:** 2–3 Links, auch bereichsübergreifend

**Seiten-spezifische Inhalte:**

- **`/krantechnik/heukrananlagen`:**
  - Neuanlagen nach Mass: Bauformen (Einschienenkran, Brückenkran, Drehkran hydraulisch, gebäudeangepasste Anlagen) mit je kurzer Beschreibung und Einsatzfall. Komponenten: Greifer, Ausleger, Fahrwerke, Drehtürme.
  - **Ablauf Neuanlage:** Besichtigung → Konzept und Offerte → Fertigung → Montage und Inbetriebnahme → Service.
  - Umbau und Erweiterung bestehender Anlagen, Service, Ersatzteile ab Lager, Saison-Check.
  - Absatz für Besitzer bestehender HS-Krananlagen: «Ihre Anlage wird weiter betreut.» Kleine Hilfe «So finden Sie Typ und Baujahr» `[[PLATZHALTER: Foto Typenschild]]`.
  - Hauptaktion: «Anlage anfragen» (Formular mit Bereich Krantechnik, Thema Heukrananlage).
- **`/krantechnik/industriekrane`:** Neuanlagen (Brücken-, Hänge-, Schwenk-, Drehkrane) nach Mass `[[PRÜFEN: Umfang Neuanlagen]]`, Service und Reparatur aller Marken, Notfall-Service. Hinweis «Foto vom Typenschild oder Schaden mitschicken».
- **`/krantechnik/pruefung-wartung`:**
  - Prüfpflicht einfach erklärt, mit Tabelle und Quellenlinks (Suva, Kranverordnung SR 832.312.15, EKAS-Richtlinie 6511) `[[PRÜFEN: fachlich]]`. Grundlage:
    - Alle Krane: regelmässige Überprüfung nach Herstellerangaben durch ausgebildete Kranfachleute.
    - Fahrzeug- und Turmdrehkrane: jährliche Überprüfung durch Kranfachleute, zusätzlich periodische Kontrolle durch einen von der Suva anerkannten Kranexperten (bis 20 Jahre alle 4 Jahre, 21–30 Jahre alle 2 Jahre, ab 31 Jahren jährlich).
    - Die Form des Kranbuchs ist frei, also auch digital möglich.
  - **Prüfpflicht-Check:** zwei Fragen (Kranart, Alter) → Ergebnis und Button «Prüfung anfragen». Daten aus der Konfiguration. Ohne JS als statische Tabelle sichtbar. Hinweis: «Unverbindliche Orientierung, massgebend sind Herstellerangaben und Suva.»
  - **Wichtig:** Nicht behaupten, dass INEXXIO Kranexperten-Kontrollen durchführt oder von der Suva anerkannt ist. `[[PRÜFEN: Qualifikation Kranfachleute im Team]]`
- **`/krantechnik/modernisierung`:** Funkfernsteuerung, Frequenzumrichter (sanftes Anfahren, weniger Verschleiss), Überlastsicherung, Steuerung, Endschalter, Greifer. Nutzen in einem Satz pro Punkt. Hinweis zur neuen EU-Maschinenverordnung (gilt ab 20. Januar 2027): Wesentliche Umbauten brauchen saubere Dokumentation `[[PRÜFEN: fachlich, Übernahme durch die Schweiz]]`. Vorher/Nachher-Regler (`enabled: false` bis echte Fotos vorhanden).
- **`/fahrzeugtechnik/fahrmischer`:** Trommel, Antrieb, Hydraulik, Rinnen, Aufbau; Winter-Revision. Markenliste als Text (keine fremden Logos) mit Hinweis: «Markennamen gehören ihren Inhabern. Wir sind unabhängig und kein Vertragshändler.» `[[PRÜFEN: bestehende Partnerschaften, z. B. Cifa?]]`
- **`/fahrzeugtechnik/aufbauten-reparatur`:** LKW-Aufbauten, Mulden und Kipper, Hydraulik, Baustellenfahrzeuge `[[PRÜFEN: Umfang]]`. Klar: «Reparatur und Instandsetzung, keine Neuaufbauten.»
- **`/fahrzeugtechnik/verschleiss-ersatzteile`:** Katalog aus einer Datei, **gruppiert** nach Teileart und «passend für»-Marke. **Keine Filter-UI** – die Gruppierung muss so klar sein, dass niemand filtern muss. Pro Teil: Foto-Platzhalter, Kurzbeschreibung, Material `[[PRÜFEN]]`, Button «Teil anfragen» (öffnet das Formular mit vorausgefülltem Teil). Keine Preise, kein Warenkorb (Shop kommt später, Kapitel 6.4).
- **`/sonderloesungen/konstruktion-engineering`:** Von der Idee bis zur Zeichnung: Konzept, Konstruktion, Berechnung, Dokumentation, Fertigung in der eigenen Werkstatt oder mit Partnern aus der Region `[[PRÜFEN]]`. Ablauf: Anliegen → Machbarkeit und Richtofferte → Konstruktion → Fertigung → Übergabe mit Dokumentation.
- **`/sonderloesungen/schweiss-stahlbau`:** Stahlkonstruktionen, Schweissarbeiten, Einzelstücke und Kleinserien, Materialien `[[PRÜFEN: Stahl, Inox, Alu?]]`.
- **`/sonderloesungen/baumaschinen`:** Umbauten, Nachrüstungen, Anbauteile, Reparaturen an Baumaschinen `[[PRÜFEN: Umfang]]`. Bezug zum Liebherr-Hintergrund.

### 7.6 Service

- **`/service`** – Einstieg nach Anliegen, nicht nach Bereich. Vier grosse Kacheln:
  - «Etwas steht still» → `/service/notfall`
  - «Kran prüfen oder warten lassen» → `/krantechnik/pruefung-wartung`
  - «Fahrmischer oder Aufbau reparieren» → `/fahrzeugtechnik/fahrmischer` bzw. `/fahrzeugtechnik/aufbauten-reparatur`
  - «Ersatz- oder Verschleissteil gesucht» → `/fahrzeugtechnik/verschleiss-ersatzteile` bzw. Formular «Teil anfragen»
  - Darunter: wie wir arbeiten (Offerte vor Arbeitsbeginn, Bericht nach jeder Arbeit `[[PRÜFEN]]`), Einsatzgebiet, Kontakt.
- **`/service/notfall`** – Notfallnummer gross, wann erreichbar `[[PRÜFEN]]`, was man bereithalten sollte (Standort, Maschine, Typenschild, Foto), Kurzformular mit Dringlichkeit «Steht still».

Der Service ist inhaltlich in jedem Bereich beschrieben. `/service` ist nur der schnelle Einstieg für Kunden mit einem akuten Anliegen.

### 7.7 Weitere Seiten

- **`/uebergabe`:** Zeitstrahl (1982 Werkstatt · 1985 erste eigene Krananlage · 1993 GmbH `[[PRÜFEN]]` · `[[PLATZHALTER: Übergabedatum]]` INEXXIO AG), Zitat Heiri `[[PLATZHALTER]]`, persönliche Botschaft von Clemens (Kapitel 7.8), Was bleibt / was neu ist, Abschnitt «Nicht mehr in unserem Angebot» mit Anker `#nicht-mehr-im-angebot`, FAQ für Bestandskunden mit Anker `#fragen`, Kontakt-CTA. Soll bei Suchen nach «HS Steiner Tuttwil», «HS Steiner Nachfolge» und «HS Krananlagen» gefunden werden.
- **`/ueber-uns`:** Clemens (Porträt, Werdegang, Botschaft) · Team (`enabled: false` bis Einverständnis) · Geschichte (kurz, Link auf `/uebergabe`) · **«Worauf Sie sich verlassen können»:** konkrete Zusagen statt Werte-Floskeln `[[PLATZHALTER: Zusagen definieren]]` · Werkstatt und Standort mit Foto · **Einsatzgebiet** mit SVG-Karte und Regionen als Fliesstext (keine eigenen Seiten pro Ort) · Ausbildungsbetrieb `[[PRÜFEN]]`.
- **`/ratgeber`:** drei Startartikel, je mit Autor (Clemens Fritsche), Datum, Quellenlinks und einer Box «Kurz gesagt» am Anfang. Alle `[[PRÜFEN: fachlich]]`.
  1. «Kranprüfung in der Schweiz: Wer muss wann was prüfen?»
  2. «Neue Heukrananlage planen: Bauformen, Platzbedarf, Ablauf»
  3. «Verschleissteile am Fahrmischer: Wann Rinne, Schurre und Spiralschutz ersetzen?»
- **`/karriere`:** Warum hier arbeiten (konkret: abwechslungsreich, Krane, Fahrzeuge, Sonderbau, kleines Team, Chef arbeitet mit). Stelleninserat «Servicetechniker/in» `[[PLATZHALTER]]` (`enabled: false`). Bewerbung per E-Mail.
- **`/kontakt`:** Hauptformular, direkte Kontakte, Notfallnummer, Öffnungszeiten, Anfahrt (statische Karte plus Link «Route in Google Maps öffnen»), Adresse.
- **`/impressum`, `/datenschutz`:** nach Schweizer Recht (revDSG). Formular, Hosting, Mailversand, Server-Logs, Konto/Login (Session-Cookie), Analytics. Komplett `[[PRÜFEN: rechtlich]]`.
- **`/404`:** kurze Entschuldigung, Links auf die drei Bereiche und den Service, Telefonnummer.

### 7.8 Persönliche Botschaft von Clemens (Entwurf)

`[[PRÜFEN: von Clemens anpassen und freigeben]]`

> Ich bin Maschinenbauingenieur und habe bei Liebherr Baumaschinen entwickelt. Krane und schwere Maschinen begleiten mich mein ganzes Berufsleben. Als ich Heiri Steiner kennengelernt habe, war schnell klar: Hier stimmt die Basis – treue Kunden, solide Anlagen, ehrliches Handwerk.
>
> Was Heiri in über 40 Jahren aufgebaut hat, führe ich mit derselben Sorgfalt weiter. Und ich ergänze es dort, wo es Ihnen nützt: mit Ingenieurwissen, sauberer Dokumentation und Lösungen, die es nicht von der Stange gibt.
>
> Clemens Fritsche, Geschäftsführer

---

## 8. Texte

### 8.1 Ton und Regeln

- **Sie-Form.** Firma spricht als «wir», Clemens persönlich als «ich».
- **Schweizer Rechtschreibung:** ss statt Eszett, Anführungszeichen «», Beträge «CHF 1'200.–», Uhrzeiten «7.00 Uhr».
- **Kurze Sätze, aktive Verben, konkrete Fakten.** Technisch präzise, aber für einen Landwirt genauso klar wie für einen Instandhaltungsleiter.
- Jede Sektion beantwortet: Was? Für wen? Warum wir? Was ist der nächste Schritt?
- **Erste Nennung auf jeder Seite:** «INEXXIO (ehemals HS Steiner)». Danach «INEXXIO» oder «wir».

### 8.2 Verbotene Wörter und Muster

innovativ · ganzheitlich · massgeschneidert · «Ihr zuverlässiger Partner» · «Lösungen aus einer Hand» · höchste Qualität · Leidenschaft · Mehrwert · State of the Art · Synergien · Exzellenz · revolutionär · nahtlos · «im Herzen von» · «Herzlich willkommen auf unserer Website» · Pikett · Superlative ohne Beleg · Ausrufezeichen · Emojis

---

## 9. Design

### 9.1 Charakter

**«Industrielle Präzision».** Ruhig, klar, technisch, hochwertig. Gefühl wie ein gutes technisches Datenblatt und Schweizer Typografie. Seriös, modern, aber nicht verspielt.

**Nicht:** Startup, SaaS-Landingpage, Agentur-Portfolio, Baumarkt.

Login, Profil und ERP-Einstieg folgen demselben Design-System, damit Website und Konto wie aus einem Guss wirken.

### 9.2 Farben

- **Rot:** exakt das Rot aus dem bestehenden INEXXIO-Design-System (aus dem Repo übernehmen). Nur für primäre Buttons, aktive Zustände und kleine Akzente, höchstens rund 5 % der Fläche. Text in Rot nur mit Kontrast ≥ 4.5:1.
- **Schwarz/Anthrazit:** dunkle Sektionen ca. `#0E0F10`, Text ca. `#16181A`.
- **Stahlgrau:** 5–6 kühle Graustufen für Linien, Sekundärtext und Flächen.
- **Papier:** Off-White ca. `#F4F4F1` für abwechselnde Sektionen, dazu Weiss.
- **Amber:** nur für Platzhalter im Modus `preview`.
- **Keine Verläufe**, ausser einer dezenten Abdunklung auf Fotos für Lesbarkeit.
- Rhythmus: Weiss → Off-White → Dunkel, damit lange Seiten gegliedert wirken.

### 9.3 Typografie

- **Inter** (Teil des INEXXIO-Design-Systems), selbst gehostet als Variable-Font im woff2-Format, Subset Latin + Latin-1, `font-display: swap`, Preload.
- Überschriften: Gewicht 600–700, Laufweite −0.02 bis −0.03 em, Zeilenhöhe 1.05–1.15.
- Fluid mit `clamp()`: H1 ca. 2.5 → 4.25 rem · H2 1.875 → 3 rem · H3 1.25 → 1.5 rem.
- Fliesstext 17 px, Zeilenhöhe 1.6, Zeilenlänge maximal ca. 68 Zeichen.
- **Technische Labels** (Eyebrows, Schrittnummern «01 — Anfrage», Spezifikationstabellen): eine Monospace-Schrift in einem einzigen Schnitt (z. B. JetBrains Mono oder IBM Plex Mono), Grossbuchstaben, Laufweite 0.08 em, 12–13 px. Sparsam einsetzen. Nur verwenden, wenn die Datei unter 25 KB bleibt; sonst Inter mit Tabellenziffern.

### 9.4 Raster und Formen

- 12-Spalten-Raster, maximale Inhaltsbreite ca. 1240 px, Rand 24 px Desktop und 16 px mobil.
- Abstände in einer festen Skala (4/8/12/16/24/32/48/64/96/128). Sektionen 96–128 px Abstand Desktop, 64 px mobil.
- **Linksbündiges, redaktionelles Layout** mit asymmetrischen Aufteilungen (5/7, 7/5). Nicht alles zentrieren.
- Feine 1-px-Trennlinien statt Kästen.
- Eckenradius 2 px bei Buttons und Feldern, 0 bei Bildern. Schatten nur für Dropdowns und den Sticky-Header, sehr dezent.
- **Buttons:** Primär rot, weisse Schrift, 48 px hoch, Gewicht 600, Pfeil-Icon, das beim Hover 2 px nach rechts wandert. Sekundär mit 1-px-Rahmen. Textlinks mit Unterstreichung beim Hover.

### 9.5 Bilder, Icons, Logo

- **Nur echte Fotos:** Werkstatt, Team bei der Arbeit, Krananlagen im Einsatz, Fahrmischer in der Werkstatt, Schweiss- und Stahlbauarbeiten, Details, Clemens und Heiri. Natürliches Licht, ehrlich, einheitliche, leicht kühle Farbstimmung.
- **Verboten:** Stockfotos mit Menschen, KI-generierte Bilder.
- Technik: AVIF/WebP mit Fallback, `srcset`, feste `width`/`height`, Lazy Loading unterhalb der ersten Ansicht, Hero-Bild mit `fetchpriority="high"`. Sprechende Dateinamen (z. B. `heukrananlage-brueckenkran-thurgau.avif`).
- Bis echte Fotos vorliegen: `<ImagePlaceholder>` mit genauer Bildbeschreibung.
- **Icons:** ein einziges Linien-Set (z. B. Lucide), Strichstärke 1.5, inline als SVG. Nur wo sie Bedeutung tragen. **Keine Icon-in-Kreis-Raster.**
- **Logo:** Falls im Repo schon ein INEXXIO-Logo existiert, dieses verwenden. Sonst eine schlichte typografische Wortmarke «INEXXIO» als SVG (Inter 700, enge Laufweite) plus Lockup mit «ehemals HS Steiner». Favicon als einfaches Monogramm. `[[PLATZHALTER: finales Logo]]`.

### 9.6 Erkennungsmerkmal: die Kranbahn-Linie

Eine feine 1-px-Linie mit einem kleinen roten Quadrat (wie eine Laufkatze auf der Kranbahn).
- Einsatz: als Trenner zwischen ausgewählten Sektionen und als Verbindung der Ablauf-Schritte.
- Zeichnet sich beim Hineinscrollen einmal ein (siehe Kapitel 10).
- **Höchstens dreimal pro Seite.** Das ist das einzige Element mit «Persönlichkeit» – es soll auffallen, weil es selten ist.

### 9.7 Anti-KI-Look (verbindliche Prüfliste)

Die Seite darf nicht nach Baukasten oder KI aussehen. **Verboten:**
- Farbverläufe, Unschärfe-Blobs, Glas-Effekte, Neon, Lila/Blau-Tech-Look
- zentrierter Hero mit Riesen-Headline über abstraktem Hintergrund
- Reihen aus drei gleichen Karten mit Icon im Kreis
- Stockfotos, KI-Bilder, Händeschütteln, Anzugträger
- hochzählende Zahlen, Fake-Bewertungen, Fake-Kundenlogos
- Floskeln aus Kapitel 8.2
- verspielte Effekte (Partikel, Tippanimation, Parallax, Scroll-Jacking, automatische Karussells)

**Stattdessen:** echte Fotos, konkrete Fakten, technische Details, redaktionelle Raster, viel Weissraum, präzise Typografie.

---

## 10. Animationen und Interaktionen

**Grundsatz:** Bewegung erklärt oder führt. Sie schmückt nicht.

- **Zeiten:** Mikro-Interaktionen 150–250 ms, Einblendungen 400–600 ms. Easing `cubic-bezier(0.2, 0.7, 0.2, 1)`. Kein Federn oder Wackeln.
- **`prefers-reduced-motion`:** alle Animationen aus.
- **Nur `transform` und `opacity` animieren.** Auslösen per IntersectionObserver, jeweils nur einmal.

**Liste:**
- Header: Servicezeile beim Scrollen weg- und wieder einklappen
- Mega-Dropdowns blenden in 150 ms ein
- Profilmenü öffnet in 150 ms
- Einblenden von Inhalten: Deckkraft 0 → 1, Versatz 12 px → 0, gestaffelt um 60 ms, maximal vier Elemente
- Kranbahn-Linie zeichnet sich ein (`stroke-dashoffset`, ca. 800 ms)
- Bilder in Karten beim Hover leicht vergrössern (1.03, 600 ms)
- Pfeil im Button wandert 2 px
- FAQ mit `<details>`
- Vorher/Nachher-Regler: basiert auf `<input type="range">`, voll per Tastatur bedienbar
- Ergebnis des Prüfpflicht-Checks blendet ein
- Formular: Schritte wechseln ohne Effekthascherei, Fehler erscheinen direkt am Feld

---

## 11. Formulare und Anfragen

### 11.1 Hauptformular (`/kontakt`)

Vier kurze Schritte mit Fortschrittsanzeige. **Ohne JavaScript** ist es ein einziges langes Formular mit Fieldsets und Validierung auf dem Server.

1. **Bereich:** Krantechnik · Fahrzeugtechnik · Sonderlösungen · Ersatz-/Verschleissteile · Anderes
2. **Anliegen** (abhängig von Schritt 1):
   - Krantechnik: Neue Heukrananlage · Neuer Industriekran · Prüfung · Wartung · Störung/Reparatur · Modernisierung
   - Fahrzeugtechnik: Fahrmischer-Service · Reparatur · Trommel-Revision · Aufbau-Reparatur
   - Sonderlösungen: Konstruktion · Schweiss-/Stahlbau · Baumaschine Umbau/Reparatur
   - Teile: welches Teil, wofür
   - **Dringlichkeit:** «Steht still – dringend» · «In den nächsten Wochen» · «Planung». Bei «Steht still» erscheint sofort die Notfallnummer gross.
3. **Details** (freiwillig ausser Ort): Hersteller/Typ, Baujahr, Standort (PLZ/Ort, Pflicht), Beschreibung, bis zu 3 Fotos oder Skizzen (JPG/PNG/WEBP/HEIC/PDF; zusammen max. 10 MB).
4. **Kontakt:** Firma (freiwillig, Landwirte haben oft keine), Name, Telefon, E-Mail, bevorzugter Kontaktweg. Datenschutzhinweis mit Link.

**Ist der Nutzer eingeloggt**, werden Name, Firma, Telefon und E-Mail aus dem Konto vorausgefüllt (nur lesend aus der Session-Schnittstelle).

**Kurzformular** auf Bereichs- und Unterseiten und der Startseite: Bereich und Thema vorausgewählt, nur Anliegen, PLZ/Ort, Name, Telefon, E-Mail.

**Erfolgsmeldung:** «Danke. Wir melden uns innert `[[PLATZHALTER]]`.» Dazu, was als Nächstes passiert, und die Telefonnummer.

### 11.2 Verarbeitung

- Eigener, klar abgegrenzter Endpunkt für Anfragen. Keine Änderung an ERP-Logik.
- Validierung auf dem Server, Honeypot-Feld, Mindestausfüllzeit 3 Sekunden, Rate Limit pro IP (z. B. 5 pro Stunde), Grössenlimits, Bereinigung aller Eingaben.
- **Kein CAPTCHA.** Nur wenn später Spam auftritt, Cloudflare Turnstile ergänzen (kostenlos).
- E-Mail an die Firmenadresse mit klarem Betreff, z. B. `[Anfrage][Krantechnik][DRINGEND] Firma – Ort`, Dateien als Anhang.
- Automatische Bestätigung an den Kunden mit Zusammenfassung und Telefonnummer.
- **Fehlerfall:** freundliche Meldung mit Telefonnummer und einem `mailto:`-Link, dessen Text die Eingaben bereits enthält. Keine Anfrage darf stillschweigend verloren gehen.
- Zugangsdaten nur über Umgebungsvariablen, nie im Repo.
- Die Anfrage intern als sauberes JSON-Objekt aufbauen (dokumentiertes Schema), damit eine spätere Übernahme ins ERP einfach ist. **Die Übernahme ins ERP selbst gehört nicht zu diesem Auftrag.**

---

## 12. Suchmaschinen (SEO)

### 12.1 Pro Seite

- Eindeutiger Title (≤ 60 Zeichen), Muster: «Heukrananlagen nach Mass | INEXXIO (ehemals HS Steiner)»
- Meta-Description 140–155 Zeichen mit Nutzen und Aufforderung
- Canonical, Open-Graph- und Twitter-Tags, OG-Bild (eine Standardgrafik plus je eine pro Bereich, statisch)
- Genau eine H1, saubere H2/H3-Hierarchie, beschreibende Alt-Texte
- `lang="de-CH"`
- Startseiten-Title enthält «ehemals HS Steiner»
- `/anmelden`, `/profil`, `/erp` und alles hinter dem Login: `noindex` und nicht in der Sitemap

### 12.2 Suchbegriffe pro Seite (Startpunkt, nach dem Launch mit der Search Console prüfen)

| Seite | Begriffe |
|---|---|
| Startseite | Krantechnik Ostschweiz, Fahrmischer Reparatur, HS Steiner Tuttwil |
| Krantechnik | Krananlagen, Kranbau Thurgau, Kranservice Ostschweiz |
| Heukrananlagen | Heukran, Heukrananlage, Heukran kaufen, Heukran Service, Heukran Ersatzteile, Heudrehkran |
| Industriekrane | Brückenkran, Hallenkran, Schwenkkran, Kranreparatur |
| Prüfung/Wartung | Kranprüfung, Krankontrolle, Kranwartung |
| Modernisierung | Kran modernisieren, Funkfernsteuerung Kran nachrüsten, Frequenzumrichter Kran |
| Fahrzeugtechnik / Fahrmischer | Fahrmischer Service, Fahrmischer Reparatur, Trommel Revision |
| Aufbauten | LKW Aufbau Reparatur, Mulde Kipper Reparatur |
| Verschleissteile | Fahrmischer Verschleissteile, Fahrmischer Rinne, Schurre |
| Sonderlösungen | Sondermaschinenbau Thurgau, Stahlbau, Schweissarbeiten, Baumaschinen Umbau |
| Übergabe | HS Steiner Nachfolge, HS Steiner Fahrzeug- und Kranbau, HS Krananlagen |
| Über uns (Einsatzgebiet) | Thurgau, St. Gallen, Winterthur, Frauenfeld, Wil |

Natürlich einbauen, nie stopfen.

### 12.3 Interne Verlinkung

Jede Unterseite verlinkt ihren Bereich, 2–3 verwandte Leistungen (auch bereichsübergreifend) und mindestens einen Ratgeber-Artikel, mit beschreibenden Linktexten.

### 12.4 Strukturierte Daten (JSON-LD, generiert aus der Konfiguration)

- **Global (@graph):** `Organization` + `LocalBusiness` mit name, **alternateName (alte Namen!)**, legalName, url, logo, image, telephone, email, address, geo, openingHoursSpecification, areaServed, foundingDate 1982, founder (Heiri Steiner), knowsAbout, hasOfferCatalog (die drei Bereiche mit Unterleistungen), sameAs `[[PLATZHALTER: Google-Unternehmensprofil, LinkedIn]]`. Dazu `WebSite`.
- **Bereichs- und Unterseiten:** `Service` (serviceType, provider, areaServed)
- **Heukrananlagen:** zusätzlich `Product` nur mit belegbaren Angaben (Name, Beschreibung, Hersteller, Bild), ohne Preise und Bewertungen
- **Unterseiten:** `BreadcrumbList`
- **FAQ-Blöcke:** `FAQPage` (Inhalt muss sichtbar auf der Seite stehen)
- **Ratgeber:** `Article` mit Autor als `Person`, datePublished, dateModified
- **Über uns:** `Person` für Clemens Fritsche
- **Karriere:** `JobPosting` nur für ein echtes, aktiviertes Inserat
- **Keine** `Review` oder `AggregateRating`.
- Prüfskript im Build: JSON-LD parsebar und Pflichtfelder vorhanden.

### 12.5 Dateien

- `sitemap.xml` (nur öffentliche, indexierbare Seiten, mit lastmod)
- `robots.txt` (je nach Modus; Konto- und ERP-Pfade immer `Disallow`)

### 12.6 Lokale Sichtbarkeit

Name, Adresse und Telefon überall exakt gleich (aus der Konfiguration). Einsatzgebiet als starker Abschnitt auf «Über uns» statt vieler dünner Ortsseiten.

---

## 13. Sichtbarkeit in KI-Assistenten (ChatGPT, Claude, Perplexity, Gemini, Copilot)

- **`robots.txt` im Modus `live`** erlaubt für öffentliche Seiten ausdrücklich: Googlebot, Bingbot, Google-Extended, GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-User, Claude-SearchBot, PerplexityBot, Perplexity-User, Applebot, Applebot-Extended, CCBot. Liste in der Konfiguration.
- **`/llms.txt`** (und `/llms-full.txt`), generiert aus der Konfiguration: wer wir sind, ehemals HS Steiner, die drei Bereiche mit Leistungen, Einsatzgebiet, Kontakt, wichtigste Seiten mit Links. Mit Abgrenzung: «Nicht zu verwechseln mit inexio (Telekommunikation, Deutschland).»
- **Inhalte so schreiben, dass KI sie zitieren kann:**
  - Jede Seite beginnt mit 2–3 sachlichen Sätzen: wer, was, wo («Auf einen Blick»).
  - FAQ-Überschriften als echte Fragen.
  - Klare Definitionen (z. B. Kranfachmann vs. Kranexperte), Tabellen für Fristen.
  - Einheitliche Bezeichnung «INEXXIO (ehemals HS Steiner)».
  - Ratgeber mit Autor, Datum und Quellen (Suva, Fedlex, EKAS).
- **Ausserhalb der Website** (nur in die Launch-Checkliste): Google-Unternehmensprofil, Bing Places, Apple Business Connect, local.ch/search.ch, LinkedIn-Seite. Überall derselbe Name mit «ehemals HS Steiner».

---

## 14. Umzug von hs-steiner.ch

Erstelle eine **301-Weiterleitungstabelle** im Format des gewählten Hostings und teste sie lokal. **Aktiviert wird sie erst beim Domainwechsel** (nicht Teil dieses Auftrags).

| Alt (Pfad inkl. Unterseiten) | Neu |
|---|---|
| `/heuentnahmekran` und Unterseiten (Einschienen-Kran, drehkran-hydraulisch, bruecken-kran, bilder-gallerie, pdf-prospekte) | `/krantechnik/heukrananlagen` |
| `/heuentnahmekran/Kran-dem-Gebäude-Angepasst` | `/krantechnik/industriekrane` |
| `/heuentnahmekran/matagematerial` | `/krantechnik/pruefung-wartung` |
| `/betonfordertechnik` und Unterseiten (Betonfahrmischer, fahrmischerpumpen, service-und-reparaturen, bilder) | `/fahrzeugtechnik/fahrmischer` |
| `/betonfordertechnik/Euro-Kpper` | `/fahrzeugtechnik/aufbauten-reparatur` |
| `/betonfordertechnik/verschleissteile` | `/fahrzeugtechnik/verschleiss-ersatzteile` |
| `/antrieb-und-steuerung` und Unterseiten | `/krantechnik/modernisierung` |
| `/baumaschinen` und Unterseiten | `/sonderloesungen/baumaschinen` |
| `/wahrschaftes`, `/wahrschaftes/stahlbau` | `/sonderloesungen/schweiss-stahlbau` |
| `/sachtransporter-anhanger/Reparaturen` | `/fahrzeugtechnik/aufbauten-reparatur` |
| `/forst-und-landwirtschaft` und Unterseiten | `/krantechnik/heukrananlagen` |
| `/haus-und-garten`, `/kleintransporter-pw`, `/hebebuhnen`, `/sachtransporter-anhanger` (Rest), `/Camping`, `/wahrschaftes/Gelaender-und-Verglasung` und Unterseiten | `/uebergabe#nicht-mehr-im-angebot` |
| `/unsere-einsatzorte` und Unterseiten | `/ueber-uns` |
| `/kontakt` und Unterseiten | `/kontakt` |
| `/application/files/*` (alte PDFs) | `/krantechnik/heukrananlagen` |
| alles andere | `/` |

Gross-/Kleinschreibung und Sonderzeichen der alten Pfade beachten.

---

## 15. Leistung, Barrierefreiheit, Datenschutz, Sicherheit

**Leistungsbudget (mobil, 4G), öffentliche Seiten:**
- LCP < 2.0 s · CLS < 0.05 · INP < 200 ms
- Lighthouse ≥ 95 in allen vier Kategorien
- JavaScript ≤ 30 KB (gzip) pro Seite · CSS ≤ 40 KB · Schriften ≤ 120 KB gesamt
- Startseite inkl. Bilder ≤ 1 MB

**Barrierefreiheit (WCAG 2.2 AA):** Kontraste, sichtbarer Fokus (2-px-Rahmen mit Abstand), Skip-Link, Landmarks, Formularlabels und Fehlermeldungen mit `aria-describedby`, Tastaturbedienung für Menü, Mega-Dropdowns, Profilmenü und Regler, Klickflächen ≥ 44 px, nie Information nur über Farbe.

**Datenschutz (revDSG), damit kein Cookie-Banner nötig ist:**
- auf öffentlichen Seiten keine Cookies ausser dem technisch nötigen Session-Cookie des Logins (nur für Eingeloggte)
- keine fremden Einbettungen (kein Google-Maps-iframe, kein YouTube-iframe)
- Schriften selbst gehostet
- Analytics nur cookielos und optional: ein neutraler `track()`-Helper, standardmässig aus. Anbieter `[[PRÜFEN: kostenlose oder günstige cookielose Lösung]]`

**Sicherheit:** HTTPS, HSTS, Content-Security-Policy (nur eigene Quellen plus zwingend Nötiges), `X-Content-Type-Options`, `Referrer-Policy: strict-origin-when-cross-origin`, schlanke `Permissions-Policy`, `frame-ancestors 'none'`. Die Session-Schnittstelle gibt nur das Nötigste zurück (keine IDs, Tokens oder Rechte-Details über «ERP ja/nein» hinaus) und ist nicht cachebar.

---

## 16. Bekannte offene Punkte (Startliste für `OFFENE_PUNKTE.md`)

**Entscheidungen**
- finales Logo · Domain · neue E-Mail-Adresse · Claim
- Notfallnummer ja/nein und Erreichbarkeit · Antwortzeit-Versprechen · konkrete Zusagen auf «Über uns»
- Umfang Neuanlagen Industriekrane
- Umfang Aufbauten-Reparatur und Baumaschinen
- Verschleissteil-Programm: Teile, Material, passende Typen
- Materialien im Schweiss- und Stahlbau
- Grenzen des Einsatzgebiets, Krananlagen im Ausland
- Analytics-Anbieter

**Inhalte und Freigaben**
- Zitat und Foto von Heiri Steiner, von ihm freigegeben
- Botschaft von Clemens
- Teamnamen und -fotos nur mit Einverständnis
- Referenzkunden und Projekte nur mit schriftlicher Freigabe
- Übergabedatum, Handelsregistereintrag INEXXIO AG, UID
- Qualifikationen im Team (Kranfachleute)

**Fachlich/Rechtlich**
- Ratgeber-Artikel, Prüfpflicht-Check, Hinweis EU-Maschinenverordnung
- Aussagen zu laufenden Verträgen
- Impressum und Datenschutzerklärung

**Fotoliste** (Empfehlung: ein professioneller Fototag – grösster Hebel für die Qualität)
1. Clemens und Heiri vor der Werkstatt (quer und hoch)
2. Werkstatt von aussen
3. Heukrananlage im Einsatz (Scheune, Greifer voll)
4. Industriekran in einer Halle
5. Techniker bei einer Kranprüfung
6. Fahrmischer in der Werkstatt, Trommel offen
7. LKW-Aufbau oder Mulde in Reparatur
8. Schweissarbeit / Stahlkonstruktion
9. Konstruktion am Bildschirm mit Werkstück daneben
10. Detail Verschleissteile
11. Ersatzteillager
12. Servicefahrzeug
13. Porträt Clemens (hoch, neutraler Hintergrund)
14. Teamfoto
15. Typenschild einer HS-Krananlage
16. Vorher/Nachher-Paare

---

## 17. Phasen und Abnahme

| Phase | Inhalt |
|---|---|
| 0 | Analyse (inkl. bestehendem Login, Profil, ERP-Einstieg, altem Design) und `WEBSITE_PLAN.md` |
| 1 | Fundament: Struktur, Konfiguration, Design-Tokens, Schriften, Layout, Header mit Servicezeile und Anmeldezustand, Footer, Navigation, Platzhalter-System, SITE_MODE |
| 2 | Komponenten: Buttons, Karten, Sektionstypen, Mega-Dropdown, Profilmenü, FAQ, ImagePlaceholder, Kranbahn-Linie, Formular-UI, Prüfpflicht-Check, Vorher/Nachher |
| 3 | Einbettung von Login, Profil und ERP-Einstieg ins neue Design (nur Darstellung) |
| 4 | Seiten in dieser Reihenfolge: Startseite → Übergabe → Krantechnik (Bereich + 4) → Fahrzeugtechnik (Bereich + 3) → Sonderlösungen (Bereich + 3) → Service (2) → Über uns → Kontakt → Karriere → Ratgeber (3) → Rechtliches → 404 |
| 5 | Formular-Endpunkt und Tracking |
| 6 | SEO und KI: Meta, JSON-LD, Sitemap, robots.txt, llms.txt, Redirects, OG-Bilder |
| 7 | Prüfung und Feinschliff (siehe unten) |
| 8 | Abschlussbericht |

### 17.1 Prüfungen in Phase 7

- Build in beiden Modi; der `live`-Build bricht wegen offener Markierungen korrekt ab
- **Jede öffentliche Seite per `curl`:** vollständiger Inhalt ohne JavaScript
- **Konto-Ablauf durchgespielt:** nicht eingeloggt → «Anmelden» · eingeloggt ohne ERP-Recht → Profilmenü ohne ERP · eingeloggt mit ERP-Recht → «ERP» in Servicezeile und Profilmenü, Klick öffnet das ERP · Abmelden · Schnittstelle nicht erreichbar → Header zeigt «Anmelden», nichts bricht
- **ERP-Regression:** Login, Profil und ERP funktionieren exakt wie vorher (bestehende Tests grün, manueller Kurztest)
- HTML-Validierung, interne Links ohne Fehler, JSON-LD-Prüfung
- Barrierefreiheit (z. B. axe), Lighthouse mobil
- Ansichten bei 360, 390, 768, 1024, 1280, 1440 und 2560 px Breite
- Formular durchgespielt (mindestens lokal mit Test-Mailserver), inklusive Fehlerfall und Vorausfüllen bei Login
- Redirect-Tabelle lokal getestet
- Texte korrekturgelesen: Schweizer Rechtschreibung, verbotene Wörter (Kapitel 8.2), keine erfundenen Fakten
- **Anti-KI-Look-Prüfung** nach Kapitel 9.7
- **5-Sekunden-Test pro Zielgruppe** – findet man in wenigen Sekunden …
  - als Landwirt: dass man hier eine neue Heukrananlage bekommt und seine alte weiter betreut wird?
  - als Instandhaltungsleiter: was die Prüfpflicht verlangt und wie man eine Prüfung bucht?
  - als Fuhrparkleiter: Fahrmischer-Service und Telefon?
  - als Betrieb mit Sonderwunsch: dass hier konstruiert und gebaut wird?
  - als Bestandskunde: was sich durch die Übergabe ändert?
  - als Mitarbeiter: mit einem Klick ins ERP?
- `OFFENE_PUNKTE.md` vollständig

**Ehrlichkeit:** Ist ein Prüfwerkzeug nicht verfügbar (z. B. kein Browser für Lighthouse), schreibe klar in den Bericht, was nicht geprüft werden konnte. Nichts als geprüft ausweisen, was nicht geprüft wurde.

### 17.2 Abschlussbericht `WEBSITE_REPORT_JJJJMMTT.md`

- Was gebaut wurde (Seiten, Komponenten, Funktionen)
- Gewählte Architektur (Variante A oder B) und Entscheidungen mit Begründung
- **Alle ERP-Schnittstellen und alle Änderungen ausserhalb des Website-Bereichs** (Ziel: nur die nötigsten, rein lesend)
- Testergebnisse inkl. dem, was nicht getestet werden konnte
- Zusammenfassung der offenen Punkte
- **Launch-Checkliste:**
  - Freigabe von Heiri Steiner (Texte, Zitat, Fotos, Namenswechsel)
  - alle Markierungen erledigt, `SITE_MODE=live`
  - Domain verbinden, hs-steiner.ch weiterleiten, Redirects aktivieren
  - Google Search Console und Bing Webmaster Tools: Domain bestätigen, Sitemap einreichen, bei Domainwechsel Adressänderung melden
  - Google-Unternehmensprofil umbenennen («INEXXIO – ehemals HS Steiner»), Bing Places, Apple Business Connect, local.ch/search.ch
  - E-Mail-Weiterleitungen und Signaturen
  - Formular und Login in Produktion einmal testen

### 17.3 Definition of Done

- Alle öffentlichen Seiten existieren mit vollständigem Inhalt (ausser markierten Platzhaltern).
- Login, Profil und ERP funktionieren unverändert und sitzen sichtbar im neuen Design.
- Die ERP-Logik ist unverändert; jede Schnittstelle und jede Änderung ausserhalb des Website-Bereichs ist dokumentiert und begründet.
- Leistungs- und Qualitätsziele sind erreicht oder Abweichungen sind erklärt.
- Formular funktioniert inklusive Fehlerfall.
- `WEBSITE_PLAN.md`, `OFFENE_PUNKTE.md` und `WEBSITE_REPORT_JJJJMMTT.md` liegen vor.
