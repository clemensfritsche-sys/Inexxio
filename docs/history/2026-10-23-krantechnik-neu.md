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

**Zweite Runde (gleicher Tag, Rückmeldung des Auftraggebers):**
- Vier Kopfbilder geliefert, freigestellt wie bei der Fahrzeugtechnik (`kran-titel`, `nachmass-titel`,
  `heukran-titel`, `kranservice-titel.webp`). Damit nutzt keine Seite mehr eine Zeichnung als Kopf –
  der SVG-Zweig in `StageHero` ist entfernt.
- Krane nach Mass neu: Situationen als Bühne mit Umschalter (`home/SpecialStage`, Kurve · Steigung ·
  Versatz · Eng) statt vier Karten; «Ihre Situation ist nicht dabei?» steht im Satz, der Knopf heisst
  «Ihre Situation schildern». Steigung neu gezeichnet: Decke mit Absatz, die Fahrbahn steigt weich mit an.
  «Was Sie vorher wissen wollen» ist in die Fragen gewandert (Tragfähigkeit, Stillstand), der
  Standardkran in einen Satz der Hallen-Karte, «Was zu jedem Kran gehört» in «So geht's» (fünf
  Stationen), «Kaufen oder ohne Kauf» ist durch die Garantien (`home/Guarantees`) ersetzt. Häfen als
  eine Karte mit Zeichnung (`kran-hafen.svg`), ohne Einschränkung auf Bodensee und Schweizer Seen; das
  Hafenjahr ist weg. Entfernt: `kran/SituationCards`, `kran/Concerns`.
- Heukrananlagen: Kopf «Heu abladen, ohne hinaufzusteigen»; Funk als Raster nach dem Muster der
  Garantien («Den Greifer im Blick, den Sender in der Hand», eine dunkle und drei helle Karten).
  Saison-Check richtig gestellt: Der Heukran läuft das ganze Jahr (Sommer einlagern, Winter
  herausholen); geprüft wird im März und April, wenn der Heustock am leersten ist. Die Marken unter dem
  Kalender sind weg, was geprüft wird, steht im Satz.

**Offen:** die fünf Fotos (Situationen, Funk) und ein Hafen-Foto; Belege mit echten Projekten.
Die Startseite läuft bei 320 px 2 px über (Kopf, schon vorher so).
