# INEXXIO – Marke und Gestaltung (v4)

> Wofür INEXXIO steht und wie es aussieht. Zum Lesen, nicht zum Bauen: die Werte stehen in
> `frontend/src/styles/design-system/colors_and_type.css`, die Regeln in `README.md`.
> Referenz zum Anschauen: `reference/mockups/Startseite v4.dc.html` (+ `… mobil`).

## 1. Wer wir sind

**INEXXIO AG** (ehemals HS Steiner Fahrzeug- und Kranbau GmbH), Tuttwil-Wängi TG, seit 1982.
Drei Bereiche, ein Ansprechpartner:

- **Krantechnik** – Krane nach Mass, Kranservice, Heukrananlagen.
- **Fahrzeugtechnik** – Trommeltausch und Verschleissteile für Fahrmischer.
- **Speziallösungen** – Spezialmaschinen, Anbauten und Vorrichtungen für Krane, Fahrzeuge
  und Baumaschinen, als Einzelstück oder Kleinserie.

Für wen: alle mit schwerem Gerät – Landwirte mit Heukran, Bauunternehmen und
Baumaschinenbetriebe, Kranhersteller und -händler, Betonwerke, Kieswerke, Recycling.

Was eine Seite erreichen soll: eine **Anfrage** oder einen **Anruf** – und Vertrauen auf den
ersten Blick: der richtige, professionelle Partner für robuste Lösungen, die funktionieren.
Gefühl: **leicht, vertrauenswürdig, kompetent, nahbar.**

## 2. Wie wir schreiben

- Schweizer Deutsch, **ss** statt ß. Zahlen Schweizer Art (`9'999 CHF`).
- **Sie** im Text, kurze Sätze, eine Sache je Satz. Nutzen vor Aufzählung
  («Neue Trommel statt neuer Fahrmischer.»).
- Was nicht feststeht, steht nicht da – keine Platzhalter, keine erfundenen Zahlen.
- **Nicht verwenden:** «Fixpreis» (in keiner Form) und «Werkstatt» – wir sind eine saubere
  Firma, kein Werkstattbetrieb. Statt «Werkstatt» → «Standort», «Betrieb», «bei INEXXIO».
- Kein Emoji. Kein Werbe-Superlativ.

## 3. Gestaltung

### Haltung
Klar und reduziert, mit dem gewissen Etwas – Vorbild in Struktur und Ruhe ist die Website
von Porsche: grosse Bilder und Videos, wenige Worte, präzise Raster, weiche Übergänge.

### Farbe
- **Kühles, neutrales Grau** (v4) trägt die Fläche – sauber statt beige. Die Skala
  `--gray-25 … --gray-950` ist leicht kühl; v3 war warm und wirkte beliebig.
- **Rot `#E51A14`** ist der eine laute Akzent – auf der Website **nur für die Anfrage**
  (Knopf, Fehler), nie dekorativ, nie in Überschriften.
- **Schwarz `#0A0A0B`** für Text, dunkle Karten und die Fusszeile.
- **Slate** bleibt die leise Stimme im ERP (Info, aktive Zeile, Links).

### Schrift
- Überschriften **Inter Tight 600**, Laufweite −0.03 em, Website-Abschnitte 48 px
  (mobil 32 px). Fliesstext **Inter 400**, grau `--fg-3` für den einen Satz unter einer
  Überschrift. Zahlen tabellarisch.
- **Eine Überschrift-Form überall:** grosse Überschrift, darunter höchstens ein grauer Satz.
  Keine Kicker darüber, keine roten Wörter, kein Mono, keine gesperrte Schrift.

### Bilder und Zeichnungen
- **Fotos und Videos** vollflächig oder als grosse Karten (Radius 16 px). Text liegt direkt
  auf dem Bild über einem dunklen Verlauf.
- **Isometrische Zeichnungen** (schematisch, Grau-Rampe): «**Grau ist die Serie, Rot ist,
  was wir dazubauen.**» – die Regel ist auf Speziallösungen sichtbar als Legende.
- **Kran-Szenen** (Heu einlagern, Trommel tauschen, Ausleger montieren) spielen in ihrer
  Bereichskarte, wenn man darüberfährt – die Laufkatze trägt das INEXXIO-Logo.
- Kartenbilder für Garantien sind **Schemata**, keine Stockfotos (geteilte Rechnung,
  Jahresband).

### Glas
Milchiges Glas (`.ix-glass`, `.ix-glass-dark`) über Bild oder ruhiger Fläche: der offene
Kopf mit seinen Menüs, Umschalter, Text auf Fotos, Eingabefelder über der Karte.
**Nur eine Ebene** – Glas sitzt nie in einer Karte, Text und Knopf nie im selben Glaskasten.
**Nicht im ERP.**

### Bewegung
Weich und ruhig: Überblenden 0.35–0.6 s, `--ease-out`. Karten wachsen beim Darüberfahren
(Bereiche ~25 % breiter), Bilder zoomen leicht, ein Umschalter blendet über statt zu
springen. Bei «reduzierter Bewegung» steht alles still.

## 4. ERP – dichte Oberfläche

Unverändert in der Haltung: **Struktur vor Fläche** (Haarlinien und Weissraum statt Karten
mit Schatten), **Status als Punkt + Wort**, Lucide-Symbole statt Text, Infotexte im Hover,
tabellarische Zahlen, 8-px-Raster. Seit v4 im **kühlen Grau** wie die Website – ohne Glas.

## 5. Logo

Wortmarke und «ehemals HS Steiner»-Lockup aus `reference/assets/logo/` – **nie umfärben**.
In der Fusszeile oben links das Logo; ganz unten der grosse Schriftzug (Buchstaben fast
schwarz, der rote Schwung leuchtet, unten angeschnitten).

## 6. Änderungen

- **v4 (Oktober 2026):** kühles Grau statt warmem Beige (Website, Konto, ERP, E-Mail);
  Glas-Tokens und `.ix-glass*`; eine Überschrift-Form ohne Kicker und rote Wörter; Rot auf
  der Website nur für die Anfrage; Karten 16 px mit Text auf dem Bild; Wortregeln
  (kein «Fixpreis», keine «Werkstatt»). Diese Datei neu geschrieben – die frühere Fassung
  beschrieb ein Microliving-Konzept, das mit dem heutigen INEXXIO nichts zu tun hat.
- **v3:** Titel 700/600, Radien 8/12/16, flach statt Schatten, drei Token-Schichten.
- **v2.x:** Slate als dritte Stimme fürs ERP, leisere Schatten.
