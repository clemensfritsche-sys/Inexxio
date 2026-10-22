# 2026-10-22 – Fahrzeugtechnik, Trommeltausch und Verschleissteile neu

**Was:** Die drei Seiten haben ein eigenes Layout nach dem Muster von Speziallösungen und Über uns
(vorher `AreaPage`/`SubPage` mit Foto-Kopf, «Auf einen Blick», Leistungsumfang, Verwandte Leistungen).
- `/fahrzeugtechnik`: `StageHero` (Zeichnung `fahrzeug-titel.svg` = die zwei Menü-Zeichnungen der
  Unterseiten) → «Alles für Ihren Fahrmischer» (`FieldCards`: Trommeltausch · Verschleissteile · Reparatur,
  Anker `#reparatur` bleibt) → «So läuft es ab» (`SolutionPath`) → Marken → Garantien → Fragen → Anfrage.
- `/fahrzeugtechnik/trommeltausch`: Kopf → «Tauschen, überholen – oder neu?» (`fahrzeug/DrumChoice`,
  die eine dunkle Karte) → «Was zum Tausch gehört» (`SolutionPath`) → «Im Winter» (`fahrzeug/WinterBand`,
  Jahresband ab September, Anker `#winter`) → Marken → Garantien → Fragen → Anfrage.
- `/fahrzeugtechnik/verschleissteile`: Kopf → Katalog (v4, je Teileart Titel links, Teile rechts;
  «Passend für» einmal oben) → «Bestellt in drei Schritten» → Fragen → Anfrage. Ohne Garantien.
- Wiederverwendet statt neu: `StageHero` (kann jetzt eine SVG-Zeichnung tragen), `FieldCards` (Zeichnung
  per Schlüssel, eigener Anker, Startkarte), `SolutionPath`, `Guarantees`, `FaqStage`, `ContactSection`.
  Die Zeichnungs-Suche steht einmal in `lib/illustrations.ts` (vorher in `FaqStage`).
- Eine Quelle: Ablauf (`steps`) und Leistungsumfang (`scope`) für llms.txt werden aus den Wegen auf der
  Seite abgeleitet. `BrandBand` steht auf Bereich und Trommeltausch.
- Saison-Aktion «Winter» nicht mehr auf dem Trommeltausch selbst (dort steht der Winter als Abschnitt).
- Design-Artefakt «Fahrzeugtechnik – Vorschlag» mit Desktop und Handy.

**Nach Feedback:** Kopf «Länger fahren statt neu kaufen»; Karten «Alles für Ihren Fahrmischer»,
schmal beginnt das Karussell in der Mitte; letzter Schritt «Übergabe» statt «Protokoll»; Markenhinweis
«Wir sind unabhängig von jedem Hersteller und kein Vertragshändler.» (statt «Markennamen gehören …»);
Fragen höchstens 5 je Seite (Bereich ohne «Aufbauten», Trommeltausch ohne «Wie schnell» und «Zweitmeinung»);
Marken-Band zeigt ein Logo, sobald `src/assets/marken/<marke>.svg` liegt (grau, beim Zeigen in Farbe) –
die Logos selbst liessen sich aus der Cloud-Umgebung nicht laden (Wikimedia gesperrt).

**Offen:** eigene Kopfbilder (wie die Zeichnung mit echtem rotem Teil auf Speziallösungen) – heute
stehen die Menü-Zeichnungen dort; Produktfotos der Teile sind weiter Beispielbilder.
