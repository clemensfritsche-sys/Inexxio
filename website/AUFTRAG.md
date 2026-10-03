<!-- Der Auftrag, wie er am 03.10.2026 erteilt wurde – unverändert abgelegt, damit er nach
     einer Unterbrechung erneut gelesen werden kann (Kapitel 0). Kapitel 14 fehlte im
     Original; die Redirect-Tabelle steht in WEBSITE_PLAN.md §5. -->

Auftrag: Neue Website INEXXIO – ehemals HS Steiner
Für Claude Code. Lies dieses Dokument vollständig, bevor du beginnst. Es liegt als Datei im Repository. Lies es jederzeit erneut, wenn du unsicher bist oder dein Kontext komprimiert wurde.

0. Arbeitsweise
Nimm dir ausdrücklich so viel Zeit, wie du brauchst. Gründlichkeit vor Tempo. Der Auftrag ist erst fertig, wenn alles in diesem Dokument umgesetzt, geprüft und dokumentiert ist.
Keine Abkürzungen. Keine leeren Seiten, keine TODO-Stubs, kein Lorem ipsum. Fehlt eine Information, setzt du einen markierten Platzhalter (Kapitel 5.4) und baust alles andere vollständig.
Arbeite in Phasen (Kapitel 17). Nach jeder Phase: Build grün, Commit, Fortschritt in website/WEBSITE_PLAN.md abhaken. So kannst du nach einer Unterbrechung nahtlos weitermachen.
Selbstständig entscheiden nach den Grundsätzen in Kapitel 1 und jede Entscheidung im Plan in einem Satz begründen. Anhalten und fragen nur, wenn du an eine Grenze aus Kapitel 2 stösst.
Weniger, aber stark. Lieber eine Sektion weniger, dafür jede mit klarem Zweck. Die Seite muss leicht sein und man muss sich sofort zurechtfinden.

1. Drei Grundsätze – gelten immer gleichzeitig
Es muss funktionieren. Extrem stabil und robust. Keine fragilen Tricks, keine Abhängigkeit von Diensten, die ausfallen oder teuer werden können.
So einfach wie möglich. Vor jeder Lösung fragen: Was ist das eigentliche Ziel? Gibt es einen einfacheren Weg dorthin?
So günstig wie möglich, so teuer wie nötig. Laufende Kosten, Pflegeaufwand und Abhängigkeiten zählen mit.
Verletzt eine Lösung einen der drei Punkte, ist sie keine Lösung.

2. Harte Grenzen
Das ERP bleibt unberührt. Die bestehende INEXXIO-ERP-Logik (Backend, Datenbank, Modelle, Migrationen, ERP-Frontend, Shop, Auth, Routen, ERP-Deploy-Konfiguration) wird weder geändert noch refaktoriert noch «nebenbei verbessert». Die Website ist ein strikt getrennter Bereich. Kein Import von ERP-Code, kein Lese- oder Schreibzugriff auf ERP-Tabellen.
Änderungen ausserhalb von website/ nur, wenn für Build oder Deploy der Website zwingend nötig. Jede solche Änderung steht vorher im Plan. Berührt sie das ERP auch nur indirekt (Routing, Root-Pfad «/», Domain, gemeinsame Konfiguration, gemeinsame Dependencies): anhalten, Optionen darlegen, fragen.
Nichts erfinden, was als Tatsache gilt. Keine erfundenen Zahlen, Kunden, Zitate, Bewertungen, Zertifikate, Preise, Reaktionszeiten oder Zusagen. Fehlt etwas: Platzhalter. Fachliche und rechtliche Aussagen: als «zu prüfen» markieren.
Keine vertraulichen Angaben. Kein Kaufpreis, keine Vertragskonditionen, kein Umsatz, kein aktueller Arbeitgeber von Clemens Fritsche, keine privaten Handynummern (auch nicht die bisherige Nummer von Heiri Steiner).

3. Ausgangslage
3.1 Das Unternehmen
HS STEINER Fahrzeug- und Kranbau GmbH, Waldweg 1, 9546 Tuttwil (Wängi TG).
1982: Heiri Steiner baut die Reparaturwerkstätte in Tuttwil-Wängi und macht sich selbstständig.
Seit 1985: eigene Krananlagen («HS Krananlagen») für Industrie und Landwirtschaft, vermarktet in der Schweiz, in Deutschland, Österreich und im Südtirol. Vorwiegend Sonderanfertigungen.
GmbH seit 1993 [[PRÜFEN: Gründungsjahr der GmbH]].
Grosses Lager an Ersatz- und Kranteilen (Greifer, Ausleger, Fahrwerke, Drehtürme).
Fahrmischer-Service für viele Marken: Intermix, Putzmeister, Cifa, Stetter, Liebherr, Belmix, Peter.
Kundenstamm bis zurück ins Jahr 1982, darunter grössere Bau- und Kiesunternehmen [[PLATZHALTER: Referenzkunden nur mit schriftlicher Freigabe nennen]].
Bisherige Website hs-steiner.ch: veraltet, unübersichtlich, rund 15 Rubriken mit vielen Nebensparten. Nur als Faktenquelle nutzen, nicht als Vorbild.
3.2 Die Übernahme
Heiri Steiner übergibt sein Unternehmen an Clemens Fritsche.
Die Firma tritt neu als INEXXIO auf, immer mit dem Zusatz «ehemals HS Steiner».
Heiri Steiner bleibt in einer befristeten Übergangszeit beratend dabei [[PRÜFEN]]. Alle Elemente dazu müssen später mit einem Schalter in der Konfiguration entfernt werden können.
Clemens Fritsche: Maschinenbauingenieur, Produktentwicklung bei Liebherr (Baumaschinen), Produkt- und Plattformmanagement im IoT-Umfeld, betriebswirtschaftliche Weiterbildung. [[PLATZHALTER: genaue Titel und Abschlüsse, Porträtfoto, LinkedIn-Link]]
Namensrisiko: «INEXXIO» klingt am Telefon wie «inexio» (deutscher Telekom-/Glasfaseranbieter). Darum steht der Name nie allein, sondern immer mit beschreibendem Zusatz und «ehemals HS Steiner».
3.3 Künftige Ausrichtung
Zwei Standbeine mit klarer Priorität.
A) Krane
Neue Krananlagen: Aktiv bewerben
Service und Ersatzteile für den Bestand an HS-Krananlagen (v. a. Heukrane in der Landwirtschaft). Versprechen: Diese Anlagen werden auch in Jahrzehnten noch betreut.
Industriekran-Service für KMU (Brücken-, Hänge-, Schwenk- und Drehkrane aller Marken): Prüfung, Wartung, Reparatur, Modernisierung. Wachstumsfeld, Hauptfokus der Akquise.
Modernisierung älterer Krane: Funkfernsteuerung, Frequenzumrichter, Überlastsicherung, Steuerung.
B) Fahrzeugbau allg. bewerben
Fahrmischer (Betonfördertechnik)
Service und Reparatur aller gängigen Marken.
Trommel-Revision, besonders im Winter, wenn der Bau ruht.
Verschleissteile (Rinnen, Schurren, Spiralschutz) als eigenes Programm im Aufbau [[PRÜFEN: Teileliste, Material, passende Typen]].
Neu
Service-Abos zum Fixpreis (Prüfung und Wartung pro Kran und Jahr).
Digitales Kranbuch: QR-Code am Kran, Prüfberichte digital abrufbar, automatische Terminerinnerung [[PRÜFEN: ab Start verfügbar oder «in Vorbereitung»?]]. Nur als Leistung beschreiben. Kein Login, kein Portal bauen.
Entfällt (nicht mehr bewerben, alte URLs per Redirect auffangen, siehe Kapitel 14)
Haus & Garten, Motorgeräte, Pflanzenschutz, Pflanzenbehälter, Transportwagen
Reifenservice, Reparaturen von PW und Transportern
Hebebühnen-Vermietung
Fahrzeughandel
Events & Oldtimer
Geländer und Verglasung
[[PRÜFEN: Liste von Clemens bestätigen lassen. Offen sind Hydraulikschlauch-Service, Reparaturen an Baumaschinen und LKW-Aufbauten sowie allgemeine Schlosserarbeiten.]]
3.4 Zielgruppen (Reihenfolge = Priorität der Akquise)
#
Zielgruppe
Wer entscheidet
Was sie brauchen
1
Produktions- und Gewerbe-KMU mit Hallenkranen
Instandhaltungs- oder Betriebsleiter, Inhaber
Prüfpflicht erfüllen, keine Ausfälle, schnelle Reaktion, saubere Dokumentation. Grosse Hersteller sind langsam und teuer.
2
Betonwerke, Bau- und Transportunternehmen mit Fahrmischern
Fuhrpark- oder Werkstattleiter
Kurze Standzeiten, alle Marken an einem Ort, Teile ab Lager
3
Landwirte mit HS-Krananlagen
Betriebsleiter
Kran läuft in der Heusaison, Ersatzteile, persönlicher Kontakt
4
Bestandskunden von HS Steiner (aus allen Gruppen)
–
«Was ändert sich für mich?» → Kontinuität plus mehr Service
5
Fachkräfte
Mechaniker, Servicetechniker
Gute Arbeit, faire Firma. Techniker sind der Engpass im Markt.

3.5 Positionierung
Kernidee: So schnell wie der Handwerker aus der Region, so sauber dokumentiert wie der Hersteller. Alle Marken
Claim (Vorschlag): «Schnell vor Ort. Sauber dokumentiert (Anmerkung von Clemens: Claim gefällt mir nicht).»
Belege, die die Seite liefern muss:
Ingenieur-Know-how (Liebherr-Hintergrund)
über 40 Jahre Erfahrung am Standort
alle Marken
Ersatzteillager vor Ort
Pikett [[PRÜFEN]]
digitale Dokumentation

4. Ziel der Website und Erfolgsmessung
Hauptziel: Aufträge. Jede Seite führt zu einer Anfrage, einem Anruf oder einem Pikett-Kontakt.
Nebenziele:
Bestandskunden halten (Vertrauen in die Übergabe)
unter neuem und altem Namen gefunden werden (Google, Bing, KI-Assistenten)
Fachkräfte gewinnen
Regel: Jede Seite hat genau eine Hauptaktion. Telefon und Anfrage sind von überall mit einem Klick erreichbar.
Messpunkte (über einen neutralen track()-Helper, Kapitel 15): form_start, form_submit (mit Typ und Dringlichkeit), tel_click, pikett_click, mailto_click, abo_interest, part_inquiry.

5. Technik
5.1 Phase 0: Analyse vor dem Bauen (nur lesen)
Analysiere das Repository:
Stack und Ordnerstruktur
wie das bestehende Frontend rendert
vorhandene öffentliche Routen und der Shop
was heute unter «/» ausgeliefert wird
Deploy-Pipeline und Hosting
bestehende Design-Tokens (Rot, Schwarz, Inter)
vorhandene Möglichkeiten für Mailversand
Ergebnis: website/WEBSITE_PLAN.md mit Ist-Zustand, Entscheidungen samt Begründung nach Kapitel 1, Liste aller Änderungen ausserhalb website/ und Phasen-Checkliste. Danach selbstständig weiter, ausser eine Grenze aus Kapitel 2 ist betroffen.
5.2 Architekturvorgabe
Standard: eigenständiges, statisch generiertes Teilprojekt in website/ mit eigenem Build.
Empfehlung: Astro. Reines HTML als Ausgabe, standardmässig kein JavaScript, Content Collections, Bildoptimierung, Sitemap. Weiche nur ab, wenn das Repo einen gleich einfachen und robusten Weg bereits bietet, und begründe das.
Pflicht: Jede Seite liefert ihren vollständigen Inhalt als HTML in der Server-Antwort, ohne JavaScript. Prüfbar per curl. Keine Client-only-SPA.
JavaScript nur für: Mobile-Menü, Header-Verhalten, Reveal-Animationen, Formular-Komfort, Prüfpflicht-Check, Vorher/Nachher-Regler, Ankündigungsleiste. Alles Vanilla, je ein kleines Modul. Alles funktioniert auch ohne JS (Progressive Enhancement).
Minimale Abhängigkeiten. Kein React/Vue für die Website, keine Animations-Library, kein UI-Kit. Eigenes schlankes CSS mit Custom Properties. Tailwind nur, wenn es im Repo bereits Standard ist.
Kein CMS. Inhalte liegen in Dateien im Repo.
Hosting: wie im Repo üblich, falls einfach möglich. Sonst die günstigste robuste Lösung für statische Seiten. Laufende Kosten im Plan ausweisen.
5.3 Eine Quelle für alles (Single Source of Truth)
Eine Konfigurationsdatei (z. B. website/src/config/site.ts) enthält alles, was mehrfach vorkommt. Header, Footer, Kontaktseite, JSON-LD, llms.txt, Sitemap und E-Mail-Vorlagen lesen ausschliesslich daraus.
Ein Namenswechsel muss in dieser einen Datei in Minuten möglich sein, z. B. falls zum Start doch «HS Steiner – Teil von INEXXIO» gewählt wird.
Seitentexte liegen in Markdown/MDX bzw. Content-Dateien, getrennt von den Layout-Komponenten.
Startwerte:
Feld
Wert
Markenname
INEXXIO
Zusatz
«Kran- und Fahrmischertechnik» [[PRÜFEN: Alternativen «Krantechnik» oder «Kran- und Fahrzeugtechnik»]]
Ehemals-Zeile
«ehemals HS Steiner»
Rechtlicher Name
[[PLATZHALTER: künftiger Name im Handelsregister]]
Frühere Namen (alternateName)
«HS Steiner», «HS Steiner Fahrzeug- und Kranbau GmbH», «HS Krananlagen»
Domain
[[PLATZHALTER: Domain]] (hs-steiner.ch wird später weitergeleitet)
Telefon
+41 52 378 22 47 (Anzeige: 052 378 22 47)
Pikett
+41 76 563 22 47 [[PRÜFEN: Pikett weiterführen? Zeiten?]]
E-Mail
[[PLATZHALTER: neue Adresse]] (fahrzeug-kranbau@hs-steiner.ch bleibt als Weiterleitung)
Öffnungszeiten
Mo–Fr 7.00–12.00 und 13.15–17.30 Uhr [[PRÜFEN]]
Adresse
Waldweg 1, 9546 Tuttwil (Wängi TG)
Koordinaten
47.4836, 8.9357 [[PRÜFEN]]
Einsatzgebiet
rund 1 Stunde ab Tuttwil: Thurgau, St. Gallen, Raum Winterthur/Zürich, Schaffhausen [[PRÜFEN]]. Service für HS-Krananlagen in Deutschland, Österreich und Südtirol auf Anfrage [[PRÜFEN]]
Fax
entfällt
UID
[[PLATZHALTER: UID]]

5.4 Platzhalter-System
Zwei Markierungen:
[[PLATZHALTER: …]] – Information fehlt.
[[PRÜFEN: …]] – Text oder Fakt ist vorhanden, muss aber von Clemens freigegeben oder fachlich/rechtlich geprüft werden.
Darstellung im Modus preview: sichtbar, gelb gestrichelt umrandet, mit kleinem Label «Platzhalter» bzw. «Prüfen». Fehlende Bilder als <ImagePlaceholder>: grauer Rahmen im richtigen Seitenverhältnis, darin die Bildbeschreibung. Diese Beschreibungen sind gleichzeitig die Fotoliste.
Prüfskript npm run check:content:
findet alle Markierungen in Quellen und Build-Ausgabe
schreibt website/OFFENE_PUNKTE.md, gruppiert nach: Entscheidungen · Inhalte und Freigaben · Fotos · Fachlich/Rechtlich. Pro Eintrag: Seite, Stelle, was gebraucht wird.
Ein Build im Modus live bricht ab, solange noch Markierungen existieren.
Sektionen ohne echten Inhalt (Referenzen, Vorher/Nachher, Teamfotos, Stelleninserat) sind in der Konfiguration mit enabled: false abgeschaltet und erscheinen in OFFENE_PUNKTE.md.
5.5 Modus (SITE_MODE)
preview (Standard): <meta name="robots" content="noindex, nofollow">, robots.txt mit Disallow: /, Markierungen sichtbar, Analytics aus.
live: indexierbar, Markierungsprüfung strikt, Analytics an (falls konfiguriert).

6. Informationsarchitektur
6.1 Hauptnavigation
Desktop: Krane ▾ · Fahrmischer ▾ · Service · Ratgeber · Über uns · rechts: Telefonnummer als Link · Button «Service anfragen»
Kontakt erreicht man über den Button, das Telefon und den Footer.
6.2 Seitenstruktur und URLs
Slugs auf Deutsch, ohne Umlaute.
/                                Startseite
/uebergabe                       Aus HS Steiner wird INEXXIO
/krane                           Übersicht Krane
/krane/pruefung-wartung          Kranprüfung und Wartung (inkl. Prüfpflicht-Check)
/krane/reparatur                 Reparatur und Pikett
/krane/modernisierung            Modernisierung älterer Krane
/krane/hs-krananlagen            HS-Krananlagen: Bestand, Ersatzteile, Neuanlagen auf Anfrage
/fahrmischer                     Übersicht Fahrmischer
/fahrmischer/service-reparatur   Service, Reparatur, Trommel-Revision
/fahrmischer/verschleissteile    Verschleissteile
/service-abo                     Abo-Stufen und digitales Kranbuch
/ueber-uns                       Clemens Fritsche, Team, Geschichte, Standort
/einsatzgebiet                   Einsatzgebiet
/ratgeber                        Übersicht Ratgeber
/ratgeber/[slug]                 Fachartikel
/karriere                        Stellen
/kontakt                         Anfrage, Telefon, Pikett, Anfahrt
/impressum
/datenschutz
/404

Breadcrumbs auf allen Unterseiten.

7. Seiten im Detail
7.1 Globale Elemente
Ankündigungsleiste (über dem Header, per Konfiguration schaltbar, schliessbar; das Schliessen wird in localStorage gemerkt, immer mit try/catch):
HS Steiner heisst jetzt INEXXIO. Gleiches Team, gleiche Nummer. Mehr erfahren → (Link auf /uebergabe)
Header
Links das Logo-Lockup: Wortmarke «INEXXIO», darunter klein der Zusatz und «ehemals HS Steiner».
Navigation, rechts Telefonnummer (Desktop sichtbar) und Button «Service anfragen».
Sticky. Beim Runterscrollen ausblenden, beim Hochscrollen einblenden. Ab 8 px Scroll weisser Hintergrund mit 1-px-Linie.
Höhe 72 px Desktop, 60 px mobil.
Dropdowns: schlichtes Panel mit 3–4 Links, je eine Zeile Beschreibung. Öffnen per Hover und Klick, voll per Tastatur bedienbar.
Mobil
Burger-Menü öffnet ein Vollbild-Overlay mit Akkordeons; unten fix Telefon und Anfrage.
Feste Aktionsleiste unten (nur mobil, erscheint nach dem Hero): [Anrufen] [Anfrage], 56 px hoch.
Saison-Aktion (aus der Konfiguration, mit Datumsbereich, als dezente Leiste oder Karte auf der Startseite und den passenden Seiten):
November bis Februar: «Winter-Revision für Fahrmischer: Trommel und Aufbau überholen, solange der Bau ruht.»
März bis Mai: «Saison-Check für Heukrane – vor dem ersten Schnitt.»
Footer (dunkel)
Spalte 1: Logo-Lockup und ein Satz, der das Unternehmen eindeutig beschreibt:

 INEXXIO (ehemals HS Steiner Fahrzeug- und Kranbau GmbH) – Prüfung, Service und Reparatur von Krananlagen und Fahrmischern in der Ostschweiz. Seit 1982 in Tuttwil-Wängi TG.



Spalte 2: Links Krane. Spalte 3: Links Fahrmischer. Spalte 4: Adresse, Telefon, Pikett, E-Mail, Öffnungszeiten.
Unterste Zeile: © Jahr · Impressum · Datenschutz · UID.
7.2 Startseite (Reihenfolge verbindlich)
1. Hero
Layout asymmetrisch: links Text (5–6 Spalten), rechts grosses echtes Foto. Kein Video, kein Slider.
Eyebrow: «Tuttwil-Wängi TG · seit 1982»
H1: «Kranservice und Fahrmischer-Reparatur für die Ostschweiz»
Lead: «Prüfung, Wartung, Reparatur und Modernisierung für Krananlagen und Fahrmischer aller Marken. Schnell vor Ort. Sauber dokumentiert.»
Buttons: «Service anfragen» (primär) · «052 378 22 47» (sekundär, tel:)
Darunter klein: «Notfall? Pikett: 076 563 22 47» [[PRÜFEN]]
Vier Einstiegs-Kacheln nach Anliegen (direkt unter dem Hero, unmittelbar sichtbar):
«Kran prüfen lassen» – Jährliche Kontrolle mit Prüfbericht → /krane/pruefung-wartung
«Kran steht still» – Reparatur und Pikett → /krane/reparatur
«Fahrmischer-Service» – Alle Marken, Teile ab Lager → /fahrmischer/service-reparatur
«Verschleissteile» – Rinnen, Schurren, Spiralschutz → /fahrmischer/verschleissteile
Vertrauensleiste: «Seit 1982 · Alle Marken · Ersatzteillager vor Ort · Pikett-Service · rund 1 Stunde Einsatzradius»
2. Übergabe (prominent, dunkle Sektion)
Eyebrow: «Nachfolge geregelt»
H2: «Aus HS Steiner wird INEXXIO.»
Lead: «Nach über 40 Jahren übergibt Heiri Steiner sein Unternehmen an Clemens Fritsche. Gleiches Team, gleiche Telefonnummer, gleicher Standort – und mehr Service.» [[PRÜFEN]]
Grosses Foto: Clemens und Heiri gemeinsam vor der Werkstatt [[PLATZHALTER: Foto]]
Zitat von Heiri Steiner [[PLATZHALTER: Zitat mit Heiri Steiner formulieren und von ihm freigeben lassen. Kein erfundenes Zitat veröffentlichen.]]
Zwei Spalten:
Was bleibt: Standort Tuttwil-Wängi · Telefonnummer 052 378 22 47 · bekannte Ansprechpartner [[PLATZHALTER: Namen nur mit Einverständnis]] · Service und Ersatzteile für alle HS-Krananlagen · laufende Verträge [[PRÜFEN: rechtlich]]
Was neu ist: Service-Abos zum Fixpreis · digitales Kranbuch · Modernisierung älterer Krane · Verschleissteile für Fahrmischer · der Name INEXXIO
Links: «Die ganze Geschichte →» (/uebergabe) · «Fragen zur Übergabe →» (/uebergabe#fragen)
3. Leistungen: zwei Standbeine
H2: «Zwei Bereiche. Volle Konzentration.»
Zwei grosse, gleichwertige Karten nebeneinander, mit Foto und Unterlinks:
Krane – «Brücken-, Hänge- und Drehkrane aller Marken sowie HS-Krananlagen: Prüfung, Wartung, Reparatur und Modernisierung.»
Fahrmischer – «Service, Reparatur und Trommel-Revision für Intermix, Putzmeister, Cifa, Stetter, Liebherr und weitere Marken. Verschleissteile ab Lager.»
4. Service-Abo und digitales Kranbuch
H2: «Ein Abo. Ein Preis. Kein Termin vergessen.»
Lead: «Wir übernehmen Prüfung und Wartung Ihrer Krane zum Fixpreis pro Jahr. Jede Kontrolle landet im digitalen Kranbuch – abrufbar per QR-Code direkt am Kran.» [[PRÜFEN]]
Kompakte Vorschau der drei Stufen (Kapitel 7.3) und eine schlichte SVG-Illustration: QR-Code am Kran → Prüfbericht auf dem Handy.
Button «Abo-Stufen ansehen»
5. Warum INEXXIO (vier konkrete Belege, keine Icon-Kreise)
Ingenieurwissen statt Rätselraten. «Clemens Fritsche hat bei Liebherr Baumaschinen entwickelt. Wir verstehen, wie ein Kran oder Fahrmischer gebaut ist – nicht nur, wo er klemmt.»
Alle Marken. «HS-Kran, Hallenkran eines anderen Herstellers oder Fahrmischer: ein Ansprechpartner für Ihren ganzen Bestand.»
Kurze Wege. «Rund eine Stunde Einsatzradius ab Tuttwil-Wängi, Ersatzteillager vor Ort, Pikett für Notfälle.»
Sauber dokumentiert. «Jede Arbeit mit Bericht, jede Prüfung im Kranbuch. Das zählt bei Versicherung und Suva – und ab 2027 auch bei Umbauten.» [[PRÜFEN: fachlich]]
Dazu ein kleines Porträt von Clemens mit einem Satz und Link auf /ueber-uns.
7. Ratgeber
Drei Artikel-Teaser (Kapitel 7.4).
8. Häufige Fragen (native <details>/<summary>)
«Wer betreut meinen HS-Kran in Zukunft?» – «Wir. Service und Ersatzteile für HS-Krananlagen führen wir weiter, mit demselben Wissen und denselben Teilen ab Lager.»
«Bleibt die Telefonnummer gleich?» – «Ja, 052 378 22 47. Auch die bisherigen E-Mail-Adressen erreichen uns weiterhin.» [[PRÜFEN]]
«Gelten bestehende Verträge weiter?» – «Ja. Das Unternehmen bleibt dasselbe, nur der Name ändert sich.» [[PRÜFEN: rechtlich]]
«Welche Marken betreuen Sie?» – Krane aller Hersteller, Fahrmischer der genannten Marken.
«Wie schnell sind Sie vor Ort?» [[PLATZHALTER: realistische Reaktionszeit]]
9. Abschluss-CTA
H2: «Was steht bei Ihnen an?»
Lead: «Beschreiben Sie Ihr Anliegen in zwei Minuten. Wir melden uns innert [[PLATZHALTER: Antwortzeit, z. B. einem Arbeitstag]].»
Kurzes Formular (Kapitel 11) plus Telefon und Pikett daneben.
7.3 Vorlage für Leistungsseiten
Alle Leistungsseiten folgen derselben Struktur:
Hero: H1 mit Suchbegriff, Lead mit Nutzen, Hauptaktion, Foto
«Auf einen Blick»: Faktenbox mit Für wen · Was wir tun · Wie schnell · Was Sie erhalten (Bericht, Kranbuch)
Leistungsumfang: klare Liste, technisch präzise
Ablauf in vier Schritten: Anfrage → Termin → Arbeit vor Ort → Bericht. Verbunden durch die Kranbahn-Linie (Kapitel 9.6).
Seiten-spezifisches Modul (siehe unten)
FAQ: 4–6 echte Fragen der Zielgruppe
CTA-Block: Kurzformular, Typ und Thema vorausgewählt
Verwandte Leistungen: 2–3 Links
Seiten-spezifische Inhalte:
/krane: Übersicht der vier Leistungen, Hinweis «alle Marken», Einstieg für Bestandskunden mit HS-Kran.
/krane/pruefung-wartung:
Prüfpflicht einfach erklärt, mit Tabelle und Quellenlinks (Suva, Kranverordnung SR 832.312.15, EKAS-Richtlinie 6511) [[PRÜFEN: fachlich]]. Grundlage:
Alle Krane: regelmässige Überprüfung nach Herstellerangaben durch ausgebildete Kranfachleute.
Fahrzeug- und Turmdrehkrane: jährliche Überprüfung durch Kranfachleute, zusätzlich periodische Kontrolle durch einen von der Suva anerkannten Kranexperten (bis 20 Jahre alle 4 Jahre, 21–30 Jahre alle 2 Jahre, ab 31 Jahren jährlich).
Die Form des Kranbuchs ist frei, also auch digital möglich.
Prüfpflicht-Check: kleines Werkzeug mit zwei Fragen (Kranart, Alter) → Ergebnis (was ist wann fällig) und Button «Prüfung anfragen». Daten aus der Konfiguration. Ohne JS als statische Tabelle sichtbar. Hinweis: «Unverbindliche Orientierung, massgebend sind Herstellerangaben und Suva.»
Wichtig: Behaupte nicht, dass INEXXIO Kranexperten-Kontrollen durchführt oder von der Suva anerkannt ist. [[PRÜFEN: Qualifikation Kranfachleute im Team bestätigen]]
Link zum Service-Abo.
/krane/reparatur: Störung und Stillstand, Pikett gross, Ersatzteile ab Lager, «Foto vom Typenschild oder Schaden mitschicken». Reaktionszeit als Platzhalter.
/krane/modernisierung: Funkfernsteuerung, Frequenzumrichter (sanftes Anfahren, weniger Verschleiss), Überlastsicherung, Steuerung, Endschalter, Greifer. Nutzen in einem Satz pro Punkt. Hinweis zur neuen EU-Maschinenverordnung (gilt ab 20. Januar 2027): Wesentliche Umbauten brauchen saubere Dokumentation [[PRÜFEN: fachlich, Übernahme durch die Schweiz]]. Vorher/Nachher-Regler (enabled: false bis echte Fotos vorhanden).
/krane/hs-krananlagen: für Besitzer von HS-Krananlagen. Typen: Einschienenkran, Drehkran hydraulisch, Brückenkran, gebäudeangepasste Anlagen für Industrie und Gemeinden, Heukrane. Ersatzteile ab Lager (Greifer, Ausleger, Fahrwerke, Drehtürme). Saison-Check. «Neuanlagen auf Anfrage.» Kleine Hilfe «So finden Sie Typ und Baujahr» [[PLATZHALTER: Foto Typenschild]]. Ziel: Suchanfragen wie «HS Kran Ersatzteile», «Heukran Service» abholen.
/fahrmischer: Übersicht Service, Reparatur, Trommel-Revision, Verschleissteile, Markenliste.
/fahrmischer/service-reparatur: Trommel, Antrieb, Hydraulik, Rinnen, Aufbau; Winter-Revision. Markenliste als Text (keine fremden Logos) mit Hinweis: «Markennamen gehören ihren Inhabern. Wir sind unabhängig und kein Vertragshändler.» [[PRÜFEN: bestehende Partnerschaften, z. B. Cifa?]]
/fahrmischer/verschleissteile: Katalog aus der Konfiguration, gruppiert nach Teileart und «passend für»-Marke. Keine Filter-UI – die Gruppierung muss so klar sein, dass niemand filtern muss. Pro Teil: Foto-Platzhalter, Kurzbeschreibung, Material [[PRÜFEN]], Button «Teil anfragen» (öffnet das Formular mit vorausgefülltem Teil). Keine Preise [[PLATZHALTER]], kein Warenkorb, kein Shop.
/service-abo:
Drei Stufen als Karten (Desktop nebeneinander, mobil gestapelt), mittlere Stufe hervorgehoben:
Prüfung: jährliche Überprüfung durch Kranfachleute, Prüfbericht, Eintrag ins digitale Kranbuch, Terminerinnerung.
Service: alles aus «Prüfung» plus Wartung nach Herstellervorgabe, Verschleiss-Check, Schmierung, Anfahrt zum Fixpreis.
Komplett: alles aus «Service» plus bevorzugte Reaktion bei Störungen, Rabatt auf Ersatzteile, jährlicher Modernisierungs-Check.
Preise: «ab CHF [[PLATZHALTER]] pro Kran und Jahr». Stufennamen und Inhalte [[PRÜFEN]].
Kranbuch-Erklärung mit SVG-Illustration. FAQ. Hauptaktion: «Abo-Offerte anfragen» (Formular mit Anzahl Krane).
7.4 Weitere Seiten
/uebergabe – die Geschichte der Übergabe:
Zeitstrahl: 1982 Werkstatt · 1985 erste HS-Krananlage · 1993 GmbH [[PRÜFEN]] · [[PLATZHALTER: Übergabedatum]] INEXXIO
Zitat Heiri [[PLATZHALTER]]
Persönliche Botschaft von Clemens (Entwurf unten)
Was bleibt / was neu ist
Abschnitt «Nicht mehr in unserem Angebot» mit Anker #nicht-mehr-im-angebot (kurz, freundlich, ohne Werbung für andere)
FAQ für Bestandskunden mit Anker #fragen
Kontakt-CTA
Diese Seite soll bei Suchen nach «HS Steiner Tuttwil», «HS Steiner Nachfolge» und «HS Krananlagen» gefunden werden.
/ueber-uns:
Clemens: Porträt, kurzer Werdegang, Botschaft
Team (enabled: false bis Einverständnis vorliegt)
Geschichte (kurz, Link auf /uebergabe)
«Worauf Sie sich verlassen können»: konkrete, messbare Zusagen statt Werte-Floskeln, z. B. Rückruf innert …, jede Arbeit mit Bericht, Offerte vor Arbeitsbeginn [[PLATZHALTER: Zusagen definieren]]
Werkstatt und Standort mit Foto
Ausbildungsbetrieb [[PRÜFEN]]
/ratgeber: vier Startartikel. Jeder mit Autor (Clemens Fritsche), Datum, Quellenlinks zu offiziellen Stellen und einer Box «Kurz gesagt» am Anfang. Alle Artikel komplett als [[PRÜFEN: fachlich]] markiert.
«Kranprüfung in der Schweiz: Wer muss wann was prüfen?»
«Kranfachmann oder Kranexperte – was ist der Unterschied?»
«Heukran-Saison-Check: Worauf es vor dem ersten Schnitt ankommt»
«Verschleissteile am Fahrmischer: Wann Rinne, Schurre und Spiralschutz ersetzen?»
/karriere: Warum hier arbeiten (konkret: abwechslungsreich, Krane und Fahrmischer, kleines Team, Chef arbeitet mit). Ein Stelleninserat «Servicetechniker/in Krane und Fahrmischer» [[PLATZHALTER]] (enabled: false). Bewerbung per E-Mail.
/kontakt: Hauptformular, direkte Kontakte, Pikett gross, Öffnungszeiten, Anfahrt (statische Karte plus Link «Route in Google Maps öffnen»), Adresse.
/impressum, /datenschutz: nach Schweizer Recht (revDSG). Formularverarbeitung, Hosting, Mailversand, Server-Logs, Analytics. Komplett [[PRÜFEN: rechtlich]].
/404: hilfreich: kurze Entschuldigung, Links auf die vier Einstiege, Telefonnummer.
7.5 Persönliche Botschaft von Clemens (Entwurf)
[[PRÜFEN: von Clemens anpassen und freigeben]]
Ich bin Maschinenbauingenieur und habe bei Liebherr Baumaschinen entwickelt. Krane und schwere Maschinen begleiten mich mein ganzes Berufsleben. Als ich Heiri Steiner kennengelernt habe, war schnell klar: Hier stimmt die Basis – treue Kunden, solide Anlagen, ehrliches Handwerk.
Was Heiri in über 40 Jahren aufgebaut hat, führe ich mit derselben Sorgfalt weiter. Und ich ergänze es dort, wo es Ihnen nützt.
Clemens Fritsche, Geschäftsführer

8. Texte
8.1 Ton und Regeln
Sie-Form. Firma spricht als «wir», Clemens persönlich als «ich».
Schweizer Rechtschreibung: ss statt ß, Anführungszeichen «», Beträge «CHF 1'200.–», Uhrzeiten «7.00 Uhr».
Kurze Sätze, aktive Verben, konkrete Fakten. Technisch präzise, aber für einen Landwirt genauso klar wie für einen Instandhaltungsleiter.
Jede Sektion beantwortet: Was? Für wen? Warum wir? Was ist der nächste Schritt?
Erste Nennung auf jeder Seite: «INEXXIO (ehemals HS Steiner)». Danach «INEXXIO» oder «wir».
8.2 Verbotene Wörter und Muster
innovativ · ganzheitlich · massgeschneidert · «Ihr zuverlässiger Partner» · «Lösungen aus einer Hand» · höchste Qualität · Leidenschaft · Mehrwert · State of the Art · Synergien · Exzellenz · revolutionär · nahtlos · «im Herzen von» · «Herzlich willkommen auf unserer Website» · Superlative ohne Beleg · Ausrufezeichen · Emojis

9. Design
9.1 Charakter
«Industrielle Präzision». Ruhig, klar, technisch, hochwertig. Gefühl wie ein gutes technisches Datenblatt und Schweizer Typografie. Seriös, modern, aber nicht verspielt.
Nicht: Startup, SaaS-Landingpage, Agentur-Portfolio, Baumarkt.
9.2 Farben
Rot: exakt das Rot aus dem bestehenden INEXXIO-Design-System (aus dem Repo übernehmen). Nur für primäre Buttons, aktive Zustände und kleine Akzente, höchstens rund 5 % der Fläche. Text in Rot nur mit Kontrast ≥ 4.5:1.
Schwarz/Anthrazit: dunkle Sektionen ca. #0E0F10, Text ca. #16181A.
Stahlgrau: 5–6 kühle Graustufen für Linien, Sekundärtext und Flächen.
Papier: Off-White ca. #F4F4F1 für abwechselnde Sektionen, dazu Weiss.
Amber: nur für Platzhalter im Modus preview.
Keine Verläufe, ausser einer dezenten Abdunklung auf Fotos für Lesbarkeit.
Rhythmus: Weiss → Off-White → Dunkel, damit lange Seiten gegliedert wirken.
9.3 Typografie
Inter (Teil des INEXXIO-Design-Systems), selbst gehostet als Variable-Font im woff2-Format, Subset Latin + Latin-1 (Umlaute, «»), font-display: swap, Preload.
Überschriften: Gewicht 600–700, Laufweite −0.02 bis −0.03 em, Zeilenhöhe 1.05–1.15.
Fluid mit clamp(): H1 ca. 2.5 → 4.25 rem · H2 1.875 → 3 rem · H3 1.25 → 1.5 rem.
Fliesstext 17 px, Zeilenhöhe 1.6, Zeilenlänge maximal ca. 68 Zeichen.
Technische Labels (Eyebrows, Schrittnummern «01 — Anfrage», Spezifikationstabellen): eine Monospace-Schrift in einem einzigen Schnitt (z. B. JetBrains Mono oder IBM Plex Mono), Grossbuchstaben, Laufweite 0.08 em, 12–13 px. Sparsam einsetzen. Nur verwenden, wenn die Datei unter 25 KB bleibt; sonst Inter mit Tabellenziffern.
9.4 Raster und Formen
12-Spalten-Raster, maximale Inhaltsbreite ca. 1240 px, Rand 24 px Desktop und 16 px mobil.
Abstände in einer festen Skala (4/8/12/16/24/32/48/64/96/128). Sektionen 96–128 px Abstand Desktop, 64 px mobil.
Linksbündiges, redaktionelles Layout mit asymmetrischen Aufteilungen (5/7, 7/5). Nicht alles zentrieren.
Feine 1-px-Trennlinien statt Kästen.
Eckenradius 2 px bei Buttons und Feldern, 0 bei Bildern. Schatten nur für Dropdowns und den Sticky-Header, sehr dezent.
Buttons: Primär rot, weisse Schrift, 48 px hoch, Gewicht 600, Pfeil-Icon, das beim Hover 2 px nach rechts wandert. Sekundär mit 1-px-Rahmen. Textlinks mit Unterstreichung beim Hover.
9.5 Bilder, Icons, Logo
Nur echte Fotos: Werkstatt, Team bei der Arbeit, Krane im Einsatz, Fahrmischer in der Werkstatt, Details (Greifer, Schweissnaht, Steuerung), Clemens und Heiri. Natürliches Licht, ehrlich, einheitliche, leicht kühle Farbstimmung.
Verboten: Stockfotos mit Menschen, KI-generierte Bilder.
Technik: AVIF/WebP mit Fallback, srcset, feste width/height, Lazy Loading unterhalb der ersten Ansicht, Hero-Bild mit fetchpriority="high". Sprechende Dateinamen (z. B. kranpruefung-brueckenkran-tuttwil.avif).
Bis echte Fotos vorliegen: <ImagePlaceholder> mit genauer Bildbeschreibung.
Icons: ein einziges Linien-Set (z. B. Lucide), Strichstärke 1.5, inline als SVG. Nur wo sie Bedeutung tragen (Telefon, Pfeil, Haken, Warnung). Keine Icon-in-Kreis-Raster.
Logo: Es gibt noch keins. Erstelle eine schlichte typografische Wortmarke «INEXXIO» als SVG (Inter 700, enge Laufweite, schwarz bzw. weiss auf dunkel) plus Lockup mit Zusatz und «ehemals HS Steiner». Variante B mit rotem «XX» als Alternative ablegen. Favicon als einfaches Monogramm. Alles [[PLATZHALTER: finales Logo]].
9.6 Erkennungsmerkmal: die Kranbahn-Linie
Eine feine 1-px-Linie mit einem kleinen roten Quadrat (wie eine Laufkatze auf der Kranbahn).
Einsatz: als Trenner zwischen ausgewählten Sektionen und als Verbindung der Ablauf-Schritte.
Zeichnet sich beim Hineinscrollen einmal ein (siehe 10).
Höchstens dreimal pro Seite. Das ist das einzige Element mit «Persönlichkeit» – es soll auffallen, weil es selten ist.
9.7 Anti-KI-Look (verbindliche Prüfliste)
Die Seite darf nicht nach Baukasten oder KI aussehen. Verboten:
Farbverläufe, Unschärfe-Blobs, Glas-Effekte, Neon, Lila/Blau-Tech-Look
zentrierter Hero mit Riesen-Headline über abstraktem Hintergrund
Reihen aus drei gleichen Karten mit Icon im Kreis
Stockfotos, KI-Bilder, Händeschütteln, Anzugträger
hochzählende Zahlen, Fake-Bewertungen, Fake-Kundenlogos
Floskeln aus Kapitel 8.2
verspielte Effekte (Partikel, Tippanimation, Parallax, Scroll-Jacking, automatische Karussells)
Stattdessen: echte Fotos, konkrete Fakten, technische Details, redaktionelle Raster, viel Weissraum, präzise Typografie.

10. Animationen und Interaktionen
Grundsatz: Bewegung erklärt oder führt. Sie schmückt nicht.
Zeiten: Mikro-Interaktionen 150–250 ms, Einblendungen 400–600 ms. Easing cubic-bezier(0.2, 0.7, 0.2, 1). Kein Federn oder Wackeln.
prefers-reduced-motion: alle Animationen aus.
Nur transform und opacity animieren. Auslösen per IntersectionObserver, jeweils nur einmal.
Liste:
Header ein- und ausblenden beim Scrollen
Einblenden von Inhalten: Deckkraft 0 → 1, Versatz 12 px → 0, gestaffelt um 60 ms, maximal vier Elemente
Kranbahn-Linie zeichnet sich ein (stroke-dashoffset, ca. 800 ms)
Bilder in Karten beim Hover leicht vergrössern (1.03, 600 ms)
Pfeil im Button wandert 2 px
Dropdowns blenden in 150 ms ein
FAQ mit <details>; weiche Höhenänderung nur, wo der Browser es per CSS kann, sonst sofort
Vorher/Nachher-Regler: basiert auf <input type="range">, voll per Tastatur bedienbar
Ergebnis des Prüfpflicht-Checks blendet ein
Formular: Schritte wechseln ohne Effekthascherei, Fehler erscheinen direkt am Feld

11. Formulare und Anfragen
11.1 Hauptformular (/kontakt)
Vier kurze Schritte mit Fortschrittsanzeige. Ohne JavaScript ist es ein einziges langes Formular mit Fieldsets und Validierung auf dem Server.
Worum geht es? Grosse Auswahlkacheln: Kran · Fahrmischer · Verschleiss- oder Ersatzteile · Service-Abo · Anderes
Was brauchen Sie? Abhängig von Schritt 1:
Kran: Prüfung · Wartung · Störung/Reparatur · Modernisierung · Neuanlage
Fahrmischer: Service · Reparatur · Trommel-Revision
Teile: welches Teil, für welchen Fahrmischer
Abo: Anzahl Krane
Dringlichkeit: «Steht still – dringend» · «In den nächsten Wochen» · «Planung». Bei «Steht still» erscheint sofort die Pikett-Nummer gross.
Details (freiwillig ausser Ort): Hersteller/Typ, Baujahr, Standort (PLZ/Ort, Pflicht), Beschreibung, bis zu 3 Fotos (Typenschild, Schaden; JPG/PNG/WEBP/HEIC; zusammen max. 10 MB).
Kontakt: Firma (freiwillig, Landwirte haben oft keine), Name, Telefon, E-Mail, bevorzugter Kontaktweg. Datenschutzhinweis mit Link (keine Pflicht-Checkbox).
Kurzformular auf Leistungsseiten und der Startseite: Typ und Thema vorausgewählt, nur Anliegen, PLZ/Ort, Name, Telefon, E-Mail.
Erfolgsmeldung: «Danke. Wir melden uns innert [[PLATZHALTER]].» Dazu, was als Nächstes passiert, und die Telefonnummer.
11.2 Verarbeitung (Backend)
Getrennt vom ERP. Entweder ein isolierter, kleiner Endpunkt (eigene Datei/Route, keine ERP-Imports, keine ERP-Tabellen) oder eine Serverless-Funktion des Hosters. Die einfachere, kostenlose und robuste Variante wählen und begründen.
Validierung auf dem Server, Honeypot-Feld, Mindestausfüllzeit 3 Sekunden, Rate Limit pro IP (z. B. 5 pro Stunde), Grössenlimits, Bereinigung aller Eingaben.
Kein CAPTCHA. Nur wenn später Spam auftritt, Cloudflare Turnstile ergänzen (kostenlos).
E-Mail an die Firmenadresse mit klarem Betreff, z. B. [Anfrage][Kran][DRINGEND] Firma – Ort, Fotos als Anhang.
Automatische Bestätigung an den Kunden mit Zusammenfassung und Telefonnummer.
Fehlerfall: freundliche Meldung mit Telefonnummer und einem mailto:-Link, dessen Text die Eingaben bereits enthält. Keine Anfrage darf stillschweigend verloren gehen.
Zugangsdaten nur über Umgebungsvariablen, nie im Repo.
Die Anfrage intern als sauberes JSON-Objekt aufbauen (dokumentiertes Schema), damit eine spätere Übernahme ins ERP einfach ist. Die ERP-Anbindung selbst gehört nicht zu diesem Auftrag.

12. Suchmaschinen (SEO)
12.1 Pro Seite
Eindeutiger Title (≤ 60 Zeichen), Muster: «Kranprüfung Ostschweiz | INEXXIO (ehemals HS Steiner)»
Meta-Description 140–155 Zeichen mit Nutzen und Aufforderung
Canonical, Open-Graph- und Twitter-Tags, OG-Bild (eine Standardgrafik plus je eine für Krane und Fahrmischer, statisch)
Genau eine H1, saubere H2/H3-Hierarchie, beschreibende Alt-Texte
lang="de-CH"
Startseiten-Title enthält «ehemals HS Steiner»
12.2 Suchbegriffe pro Seite (Startpunkt, nach dem Launch mit der Search Console prüfen)
Seite
Begriffe
Startseite
Kranservice Ostschweiz, Fahrmischer Reparatur, HS Steiner Tuttwil
Prüfung/Wartung
Kranprüfung, Krankontrolle, Kranwartung Thurgau, Brückenkran Service
Reparatur
Kranreparatur, Kran Störung, Kran Pikett
Modernisierung
Kran modernisieren, Funkfernsteuerung Kran nachrüsten, Frequenzumrichter Kran
HS-Krananlagen
HS Krananlagen, Heukran Service, Heukran Ersatzteile, Drehkran hydraulisch
Fahrmischer
Fahrmischer Service, Fahrmischer Reparatur, Trommel Revision
Verschleissteile
Fahrmischer Verschleissteile, Fahrmischer Rinne, Schurre Fahrmischer
Übergabe
HS Steiner Nachfolge, HS Steiner Fahrzeug- und Kranbau
Einsatzgebiet
Kranservice Thurgau, St. Gallen, Winterthur, Frauenfeld, Wil

Natürlich einbauen, nie stopfen.
12.3 Interne Verlinkung
Jede Leistungsseite verlinkt 2–3 verwandte Leistungen und mindestens einen Ratgeber-Artikel, mit beschreibenden Linktexten (nicht «hier klicken»).
12.4 Strukturierte Daten (JSON-LD, generiert aus der Konfiguration)
Global (@graph): Organization + LocalBusiness mit name, alternateName (alte Namen!), legalName, url, logo, image, telephone, email, address, geo, openingHoursSpecification, areaServed, foundingDate 1982, founder (Heiri Steiner), knowsAbout, hasOfferCatalog, sameAs [[PLATZHALTER: Google-Unternehmensprofil, LinkedIn]]. Dazu WebSite.
Leistungsseiten: Service (serviceType, provider, areaServed)
Unterseiten: BreadcrumbList
FAQ-Blöcke: FAQPage (Inhalt muss sichtbar auf der Seite stehen)
Ratgeber: Article mit Autor als Person, datePublished, dateModified
Über uns: Person für Clemens Fritsche
Karriere: JobPosting nur für ein echtes, aktiviertes Inserat
Keine Review oder AggregateRating.
Prüfskript im Build: JSON-LD parsebar und Pflichtfelder vorhanden.
12.5 Dateien
sitemap.xml (nur indexierbare Seiten, mit lastmod)
robots.txt (je nach Modus, Kapitel 5.5 und 13)
12.6 Lokale Sichtbarkeit
Name, Adresse und Telefon überall exakt gleich (aus der Konfiguration). Eine starke Einsatzgebiets-Seite statt vieler dünner Ortsseiten.

13. Sichtbarkeit in KI-Assistenten (ChatGPT, Claude, Perplexity, Gemini, Copilot)
robots.txt im Modus live erlaubt ausdrücklich: Googlebot, Bingbot, Google-Extended, GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-User, Claude-SearchBot, PerplexityBot, Perplexity-User, Applebot, Applebot-Extended, CCBot. Liste in der Konfiguration.
/llms.txt (und /llms-full.txt), generiert aus der Konfiguration: wer wir sind, ehemals HS Steiner, Leistungen, Einsatzgebiet, Kontakt, wichtigste Seiten mit Links. Mit Abgrenzung: «Nicht zu verwechseln mit inexio (Telekommunikation, Deutschland).»
Inhalte so schreiben, dass KI sie zitieren kann:
Jede Seite beginnt mit 2–3 sachlichen Sätzen: wer, was, wo («Auf einen Blick»).
FAQ-Überschriften als echte Fragen.
Klare Definitionen (z. B. Kranfachmann vs. Kranexperte), Tabellen für Fristen.
Einheitliche Bezeichnung «INEXXIO (ehemals HS Steiner)».
Ratgeber mit Autor, Datum und Quellen (Suva, Fedlex, EKAS).
Ausserhalb der Website (nur in die Launch-Checkliste): Google-Unternehmensprofil, Bing Places, Apple Business Connect, local.ch/search.ch, LinkedIn-Seite. Überall derselbe Name mit «ehemals HS Steiner». Diese Quellen nutzen KI-Assistenten stark.

15. Leistung, Barrierefreiheit, Datenschutz, Sicherheit
Leistungsbudget (mobil, 4G):
LCP < 2.0 s · CLS < 0.05 · INP < 200 ms
Lighthouse ≥ 95 in allen vier Kategorien
JavaScript ≤ 30 KB (gzip) pro Seite · CSS ≤ 40 KB · Schriften ≤ 120 KB gesamt
Startseite inkl. Bilder ≤ 1 MB
Barrierefreiheit (WCAG 2.2 AA): Kontraste, sichtbarer Fokus (2-px-Rahmen mit Abstand), Skip-Link, Landmarks, Formularlabels und Fehlermeldungen mit aria-describedby, Tastaturbedienung für Menü, Dropdowns und Regler, Klickflächen ≥ 44 px, nie Information nur über Farbe.
Datenschutz (revDSG), damit kein Cookie-Banner nötig ist:
keine Cookies
keine fremden Einbettungen (kein Google-Maps-iframe, kein YouTube-iframe)
Schriften selbst gehostet
Analytics nur cookielos und optional: ein neutraler track()-Helper, standardmässig aus. Anbieter [[PRÜFEN: kostenlose oder günstige cookielose Lösung wählen]]
Sicherheit: HTTPS, HSTS, Content-Security-Policy (nur eigene Quellen plus zwingend Nötiges), X-Content-Type-Options, Referrer-Policy: strict-origin-when-cross-origin, schlanke Permissions-Policy, frame-ancestors 'none'.

16. Bekannte offene Punkte (Startliste für OFFENE_PUNKTE.md)
Entscheidungen
Zusatz zum Markennamen · finales Logo · Domain · neue E-Mail-Adresse
Pikett ja/nein und Zeiten · Antwortzeit-Versprechen · konkrete Zusagen auf «Über uns»
Abo-Stufen: Namen, Inhalte, Preise
Verschleissteil-Programm: Teile, Material, passende Typen
Analytics-Anbieter · WhatsApp-Kontakt ja
Inhalte und Freigaben
Zitat und Foto von Heiri Steiner, von ihm freigegeben
Botschaft von Clemens
Teamnamen und -fotos nur mit Einverständnis
Referenzkunden nur mit schriftlicher Freigabe
Übergabedatum, Handelsregistername, UID
Qualifikationen im Team (Kranfachleute)
Fachlich/Rechtlich
Ratgeber-Artikel, Prüfpflicht-Check, Hinweis EU-Maschinenverordnung
Aussagen zu laufenden Verträgen
Impressum und Datenschutzerklärung
Fotoliste (Empfehlung: ein professioneller Fototag – grösster Hebel für die Qualität)
Clemens und Heiri vor der Werkstatt (quer und hoch)
Werkstatt von aussen
Techniker bei der Prüfung eines Hallenkrans
Heukran im Einsatz
Fahrmischer in der Werkstatt, Trommel offen
Detail Verschleissteile
Detail Steuerung / Funkfernsteuerung
Ersatzteillager
Servicefahrzeug
Porträt Clemens (hoch, neutraler Hintergrund)
Teamfoto
Typenschild eines HS-Krans
Vorher/Nachher-Paare

17. Phasen und Abnahme
Phase
Inhalt
0
Analyse und WEBSITE_PLAN.md
1
Fundament: Projekt, Konfiguration, Design-Tokens, Schriften, Layout, Header, Footer, Navigation, Platzhalter-System, SITE_MODE
2
Komponenten: Buttons, Karten, Sektionstypen, FAQ, ImagePlaceholder, Kranbahn-Linie, Formular-UI, Prüfpflicht-Check, Vorher/Nachher
3
Seiten in dieser Reihenfolge: Startseite → Übergabe → Krane (5) → Fahrmischer (3) → Service-Abo → Über uns → Einsatzgebiet → Kontakt → Karriere → Ratgeber (4 Artikel) → Rechtliches → 404
4
Formular-Backend und Tracking
5
SEO und KI: Meta, JSON-LD, Sitemap, robots.txt, llms.txt, Redirects, OG-Bilder
6
Prüfung und Feinschliff (siehe unten)
7
Abschlussbericht

17.1 Prüfungen in Phase 6
Build in beiden Modi; der live-Build bricht wegen offener Markierungen korrekt ab
Jede Seite per curl: vollständiger Inhalt ohne JavaScript
HTML-Validierung, interne Links ohne Fehler, JSON-LD-Prüfung
Barrierefreiheit (z. B. axe), Lighthouse mobil
Ansichten bei 360, 390, 768, 1024, 1280, 1440 und 2560 px Breite
Formular durchgespielt (mindestens lokal mit Test-Mailserver), inklusive Fehlerfall
Redirect-Tabelle lokal getestet
Texte korrekturgelesen: Schweizer Rechtschreibung, verbotene Wörter (Kapitel 8.2), keine erfundenen Fakten
Anti-KI-Look-Prüfung nach Kapitel 9.7
5-Sekunden-Test pro Zielgruppe – findet man in wenigen Sekunden …
als Fuhrparkleiter: Fahrmischer-Service und Telefon?
als Landwirt: dass sein HS-Kran weiter betreut wird?
als Instandhaltungsleiter: was die Prüfpflicht verlangt und wie man eine Prüfung bucht?
als Bestandskunde: was sich durch die Übergabe ändert?
OFFENE_PUNKTE.md vollständig
Ehrlichkeit: Ist ein Prüfwerkzeug nicht verfügbar (z. B. kein Browser für Lighthouse), schreibe klar in den Bericht, was nicht geprüft werden konnte. Nichts als geprüft ausweisen, was nicht geprüft wurde.
17.2 Abschlussbericht website/WEBSITE_REPORT_JJJJMMTT.md
Was gebaut wurde (Seiten, Komponenten, Funktionen)
Entscheidungen mit Begründung
Alle Änderungen ausserhalb von website/ (Ziel: keine oder nur zwingend nötige)
Testergebnisse inkl. dem, was nicht getestet werden konnte
Zusammenfassung der offenen Punkte
Launch-Checkliste:
Freigabe von Heiri Steiner (Texte, Zitat, Fotos, Namenswechsel)
alle Markierungen erledigt, SITE_MODE=live
Domain verbinden, hs-steiner.ch weiterleiten, Redirects aktivieren
Google Search Console und Bing Webmaster Tools: Domain bestätigen, Sitemap einreichen, bei Domainwechsel Adressänderung melden
Google-Unternehmensprofil umbenennen («INEXXIO – ehemals HS Steiner»), Bing Places, Apple Business Connect, local.ch/search.ch
E-Mail-Weiterleitungen und Signaturen
Formular in Produktion einmal testen
17.3 Definition of Done
Alle Seiten existieren mit vollständigem Inhalt (ausser markierten Platzhaltern).
Das ERP ist unverändert; jede Änderung ausserhalb website/ ist dokumentiert und begründet.
Leistungs- und Qualitätsziele sind erreicht oder Abweichungen sind erklärt.
Formular funktioniert inklusive Fehlerfall.
WEBSITE_PLAN.md, OFFENE_PUNKTE.md und WEBSITE_REPORT_JJJJMMTT.md liegen vor.
