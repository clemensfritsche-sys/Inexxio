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

**Dritte Runde (gleicher Tag):**
- Kopfbilder Bereich, Heukran, Kranservice: Ränder (links, rechts, oben) laufen weich aus, damit die
  Zeichnung nicht abgeschnitten wirkt; das Rote und Dunkle bleibt voll (Maske beim Freistellen).
- Situationen: alle vier auf einen Blick, gesetzt wie der Verschleissteile-Katalog (`Magazine` aus dem
  Katalog herausgelöst, `PhotoCard` mit `illo`), dazu die Karte «Ihre Situation ist nicht dabei?».
- Häfen ohne graue Fläche (Bild folgt, Prompt an den Auftraggeber).
- Funk: gesetzt wie die Garantien – das Layout ist jetzt `home/Stagger`, die Garantien nutzen es auch.
  Titel «Ohne Kabine. Mit dem besten Blick.», zwei neue Schemas (`schema/funk-sender.svg`,
  `funk-sicht.svg`), Foto `heukran-funk` (bis dahin `heukran-einsatz`). Kopf «Heukrane, gebaut für
  Ihre Scheune».

**Vierte Runde (gleicher Tag):**
- Bilder des Auftraggebers eingebaut: Kopf Krane nach Mass neu, Hafen freigestellt (`hafen-titel.webp`,
  ersetzt die Zeichnung), Foto `heukran-funk` (generiert, ohne echte Person). Ungenutzt entfernt:
  `kran-hafen.svg`, `heukran-funk.svg`.
- `Magazine` kann `square` (Zeichnungen) und eine kompakte Schlusskarte `mag__end`, die rechts die
  Lücke schliesst; `PhotoCard` mit `compact` und Glas-Etikett bei Zeichnungen. Bauformen der
  Heukrananlagen jetzt ebenso (statt Bühne mit Umschalter).
- `FieldCards`: Titel, Satz und Pfeil liegen auf einer Glasfläche über dem Fuss der Zeichnung – gilt auf
  Krantechnik, Fahrzeugtechnik und Speziallösungen (ein Baustein). Krantechnik-Texte lockerer.
- Kranservice reduziert: Stufen als Treppe (`ServiceTiers`, INEXXIO 365 oben, #inexxio-365) → Garantien →
  zwei Bildkarten «Prüfen, warten, modernisieren» → Prüfpflicht in drei Sätzen (Einzelheiten im
  Ratgeber). Entfernt: «Was ist bei Ihrem Kran fällig?» (`InspectionCheck`, `scripts/check.ts`),
  `InspectionTable`, `config/inspection.mjs`, «Zwei Wege zu INEXXIO 365» (`WayPair`), die Listen
  «Was wir prüfen» und «Modernisieren».

**Fünfte Runde (gleicher Tag):**
- «Alles rund um Ihren Kran»: Titel und Glasfläche zurückgenommen (wie vorher), die lockereren Kartentexte bleiben.
- Kranservice: drei Stufen statt vier (Auf Abruf · Service-Vertrag · INEXXIO 365; Basis und Plus sind
  zusammengelegt), je Karte eine kleine Stufen-Anzeige, schmal gleich breit untereinander. Anfrage ohne
  Foto-Hilfe (Standard).
- `Magazine` global: Versatz 160 px; bei Zeichnungen ragt das Bild oben aus der Karte (wie die Feldkarten),
  die Schlusskarte rückt an die Karte darüber.
- Funk: helle Karte mit der Hand am Sender (`funk-sender.webp`, mit der Fläche verrechnet), dunkle Karte
  mit Foto `funk-sicht`, Fotokarte neu (`heukran-funk`). `home/Stagger` nimmt dafür Bild bzw. Foto an.
  Entfernt: `schema/funk-sender.svg`, `funk-sicht.svg`.

**Sechste Runde (gleicher Tag):**
- Kopfbild Heukrananlagen neu (freigestellt, schmal gesetzt).
- Rasterkarten mit Zeichnung (`PhotoCard` `illo`) wie die Feldkarten: so hoch wie ihr Inhalt, Wort, Titel
  und Satz direkt unter der Zeichnung; das Glas-Etikett ist weg. `Magazine` heisst dafür `art` statt `square`.
- Steigung neu gerechnet: die Fahrbahn ist die um 22 px parallel versetzte Decke (auch in der Schräge).
- Saison-Check zweimal im Jahr: Frühling vor dem ersten Schnitt und Spätherbst (Oktober, November), wenn
  das Heu drin ist und das Vieh noch auf der Weide; dazu eine zweite Saison-Aktion `heukran-herbst`.

**Offen:** Foto für «Die erste Inspektion ist gratis» (Prompt gestellt); die vier Fotos (Situationen, Funk) und ein Hafen-Foto; Belege mit echten Projekten.
Die Startseite läuft bei 320 px 2 px über (Kopf, schon vorher so).
