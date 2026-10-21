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
