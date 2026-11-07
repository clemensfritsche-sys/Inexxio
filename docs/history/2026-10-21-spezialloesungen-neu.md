# Speziallösungen neu (21.10.2026)

Umsetzung des Entwurfs «Speziallösungen – Ist und Vorschlag» (Design-Canvas-Artefakt,
Boards «Vorschlag · Desktop» und «Vorschlag · Handy»).

## Was
- **Kopf wie Porsche** (`components/StageHero.astro`, wiederverwendbar): heller Verlauf, grosses
  graues Wort, freigestelltes Titelbild (Lastwagen als Zeichnung, nur der Greifer echt und rot),
  H1, ein Satz, rote Anfrage + Glas-Knopf «So läuft es ab». Neuer Knopf `.btn--glass`.
- **Drei Felder** (`components/spezial/FieldCards.astro`): Text in grauer Karte, Zeichnung darüber;
  Baumaschinen · Fahrzeuge · Krane; schmal ein Karussell, das bei «Für Fahrzeuge» beginnt.
- **Serienmaschinen …** (`SeriesGap.astro`): Bild ohne Fläche (Reihe gleicher Bagger als Zeichnung,
  einer echt mit rotem Anbau), drei Gewinne kompakt.
- **Vom Problem zur Lösung** (`SolutionPath.astro`): senkrechter Weg, fünf Stationen mit «wer»;
  neue Texte ohne Offerte und ohne Zahlen.
- **Garantien**: der Baustein der Startseite (`Guarantees.astro`) statt `Promises`.
- **Fragen (global)**: Grundbild `assets/schema/fragen.svg`, Bild je Frage (`illo`), schmal rückt
  das Bild über die offene Frage. Frage «Co-Entwicklung» entfernt – nicht mehr im Konzept.
- Entfernt: Fakten-Zeile, Prinzip-Liste, alte Feld-Spalten, Schrittliste, `specialFacts`.

## Gemessen
Startseite 1023.8 KB (Budget 1024 KB) – das Grundbild kostete ~1 KB; ausgeglichen durch
Entfernen von Leerraum zwischen Tags in `assets/crane/szene-*.svg` (ohne `<text>`, unverändert
im Bild).

## Bewusst
Die beiden freigestellten Bilder sind KI-Bilder im Zeichnungsstil. Sie liegen bei den
Illustrationen, nicht in der Fotoliste (`photos.mjs` bleibt «nur echte Fotos»).
