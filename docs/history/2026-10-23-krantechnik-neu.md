# 2026-10-23 – Krantechnik neu: Bereich, Krane nach Mass, Kranservice, Heukrananlagen

**Was:** Die vier Seiten haben ein eigenes Layout nach dem Muster von Fahrzeugtechnik und
Speziallösungen; dazu der Auftrag «Krane nach Mass schärfen (schwierige Gebäude) und Funk statt Kabine
ausweisen» (WEBSITE_PLAN Entscheid 125).
- `/krantechnik`: Kopf → «Alles rund um Ihren Kran» (`FieldCards`) → Weg → Garantien → Fragen (5) → Anfrage.
- `/krantechnik/krane-nach-mass`: Kopf «Ihr Gebäude ist nicht gerade …» → vier Situationen mit neuen
  Strichzeichnungen (`kran-kurve|steigung|versatz|eng.svg`) → «Für Scheune und Halle» (zwei `PhotoCard`)
  → «Was Sie vorher wissen wollen» → «So geht's» (#ablauf) → Belege (Schalter, aus) → Standardkran →
  Häfen und Hafenjahr (#hafen) → Kaufen oder ohne Kauf (`WayPair`) → «Was zu jedem Kran gehört»
  (`FactGrid`) → Fragen (5) → Anfrage mit Foto-Hilfe.
- `/krantechnik/heukrananlagen`: Kopf (Lead «… nach Mass, bedient per Funk») → «Funk statt Kabine»
  (Zeichnung `heukran-funk.svg`, bis das Foto da ist) → Saison-Check als Wandkalender → bestehende
  HS-Anlagen → Bauformen als Bühne mit Umschalter (vier Felder, je «Bedienung per Funk») → Weg → Fragen.
- `/krantechnik/kranservice`: Kopf → vier Stufen (v4, schmal zum Wischen) → zwei Wege zu INEXXIO 365 →
  was wir prüfen → Modernisierung → Prüfpflicht mit Check, Tabelle, Quellen → Fragen → Anfrage mit
  Foto-Hilfe (Typenschild).
- Bausteine allgemein gemacht statt neu: `SeasonCalendar` (vorher `fahrzeug/WinterBand`, jetzt mit Plan je
  Monat und beliebig vielen Arten), `home/SpecialStage` (bis vier Felder, kurzer Tab-Name), `PhotoCard`
  (aus dem Katalog herausgelöst), `ContactSection` (`hint`). Neu: `WayPair`, `FactGrid`, `kran/*`.
- Entfernt, weil niemand sie mehr nutzt: `layouts/AreaPage`, `layouts/SubPage`, `Glance`, `ScopeList`,
  `Steps`, `AreaCard`, `CraneForm`, `Promises`.
- Fotostellen angelegt (ohne Datei): `kran-kurve`, `kran-steigung`, `kran-versatz`, `kran-eng`, `heukran-funk`.

**Abweichungen vom Auftrag:**
- Titel «Krane für schwierige Gebäude» statt «Krane nach Mass: auch für schwierige Gebäude» – mit dem
  Zusatz «| INEXXIO (ehemals HS Steiner)» wären es 75 Zeichen, `check-site` erlaubt 60.
- Fragen höchstens 5 je Seite (Wunsch vom 22.10.): auf «Krane nach Mass» die drei neuen, dazu Kauf und
  Bootslifte; Standardkrane, Garantie, 365, Bootskran-Prüfung, Preis und Zweitmeinung stehen nicht mehr
  dort (Standardkran, Garantie und 365 haben eigene Abschnitte).
- «Werkstatt» ist ein gesperrtes Wort: «im eigenen Betrieb», «Gewerbe» statt «Werkstätten».

**Offen:** Kopfbilder (heute die Menü-Zeichnungen) und die fünf Fotos; Belege mit echten Projekten.
Die Startseite läuft bei 320 px 2 px über (Kopf, schon vorher so).
