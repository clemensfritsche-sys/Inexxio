# Illustrationen neu: isometrisch, mittlere Distanz, mehr Detail (21.10.2026)

**Was:** Alle Kachel- und Bauform-Bilder der Website neu gezeichnet (18 Dateien in
`website/src/assets/illustrations/`), im Stil der im Design-Artefakt gewählten Variante F:
isometrisch, ein Motiv in mittlerer Distanz, in einem Bruchteil einer Sekunde erkennbar,
drei Farben (Rot als Akzent, Schwarz, kühle Grautöne).

- Krantechnik-Untermenü: `menu/krane-nach-mass.svg` (Brückenkran mit Spannweiten-Mass, auch
  Bereich Krantechnik), `menu/kranservice.svg` (Werkzeugkiste, Prüfprotokoll),
  `menu/heukrananlagen.svg` (Dachstuhl, Kranbahn, Greifer über dem Heustock). Die alten Bilder
  (Säulenkran, Brückenkran-Gerüst) sind ersetzt.
- Neu gezeichnet unter gleichem Namen: Trommeltausch (Trommel wird aufgesetzt), Service
  (Servicewagen), Über uns (Werkhalle), Verschleissteile, Ratgeber, Karriere, Kontakt,
  Anmelden, Mein Profil, Abmelden, die vier Heukran-Bauformen und die drei
  Speziallösungen-Felder.
- Unverändert: Garantien (`assets/schema/`) und die bewegte Kran-Szene der Startseite
  (`assets/crane/`).

**Wie:** Generiert (Python, isometrische Projektion, Maler-Reihenfolge), danach im Browser
auf den Inhalt zugeschnitten (viewBox). Übersicht mit Überschrift und Einsatzort je Bild im
Design System, Karte «Illustrationen».

## Runde 2 (Feedback)

- **Fahrmischer** neu: europäischer Frontlenker mit 4 Achsen, weisse Trommel mit roten
  Streifen, Proportionen wie die Szene der Startseite (`assets/crane/szene-fahrzeugtechnik.svg`).
  Darauf bauen Trommeltausch, Verschleissteile (Trichter und Rinnen rot am Fahrzeug, Ersatzteile
  davor) und «Für Fahrzeuge» (Pritsche mit Ladekran) auf.
- **Service**: Servicewagen unterwegs (Strasse, Fahrtlinien). **Karriere**: drei Personen tragen
  gemeinsam einen Träger. **Kontakt**: Handschlag. **Anmelden/Abmelden**: Telefon mit
  Fingerabdruck und Schlüssel bzw. Abmelde-Pfeil statt Tür. **Profil**: grössere Ausweiskarte.
  **Bagger** detailreicher (Laufwerk, Kabine, Zylinder, Abbruchhammer).
- Startseiten-Budget (1024 KB) war um 14 KB überschritten: Kreise mit weniger Punkten,
  Zahlen ohne «.0» – die Bilder sind rund 40 % kleiner.

## Runde 3 (Feedback)

- **Trommeltausch/Fahrzeugtechnik**: Trommel grösser, breite schräge rote Streifen (Flächen statt
  Linien), alte graue Trommel liegt davor – kein Kranhaken mehr.
- **Verschleissteile**: Fahrmischer von hinten; Einfülltrichter, Auslaufschurre, Auslaufrinne
  und Verlängerungsrinne rot, Ersatzrinne davor.
- **Karriere**: drei Personen arbeiten gemeinsam an einem Träger (halten, schweissen, Plan).
- **Bühnen-Video** neu hochgeladen (5 MB, mit Ton, Index am Dateiende): ohne Ton neu kodiert,
  `faststart` (Index vorne – sonst lädt ein Handy erst die ganze Datei), 1.4 MB. Verweigert
  ein Handy das automatische Abspielen, startet das Video bei der ersten Berührung
  (`scripts/media.ts`). Bei «Bewegung reduzieren» bleibt bewusst das Foto stehen.
