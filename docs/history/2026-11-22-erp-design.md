# ERP-Design neu (22.11.2026)

**Auftrag des Inhabers:** Das ERP einfacher, schlichter, nicht überladen – wie die Profilseite im
Konto. Gemeinsam definiert, erst als Mockup (Artefakt «INEXXIO ERP Mockup»), dann auf Development.

## Entschieden (Schritt für Schritt)
- Kopf: bleibt der Website-Kopf. Feed: Etiketten, Symbole, «+» bleiben – das «+» links unten.
- Datensatz-Kopf: bleibt, aber **weiss**; die Überschrift trägt die **Art-Farbe** statt Rot.
- Inhalt: **dieselben Abschnitte wie im Konto** (Titel links, Sache rechts, Haarlinie), weiss, keine
  Karten in Karten, **keine Untertitel, keine Sprungleiste**; schmal übereinander.
- Verlauf: Technisches bleibt, aber hinter **«Änderungen zeigen»** (standardmässig aus).
- Farbe: **Art-Farben, Palette «abgestimmt»** (kühl wie das Grau, Unternehmen Indigo statt Ziegel).
- Feed ohne Kästen in Kästen; die Linie unter dem Feed-Kopf trifft die unter dem Datensatz-Kopf.
- Verworfen: eigener ERP-Kopf, Rechts-Spalte «Profil», Verlauf in Worten, grösserer Umbau (zu viel),
  vier Feinschliffe (Titel kleiner, weniger Luft, Normalzustand grau, Nur-Lesen als Text).

## Getan
- Tokens `--type-*` (`colors_and_type.css`), `TYPE_META` liest sie.
- `detail-frame`: `Card` = `.kt-sec` (+ `wide`), `SectionSep` als Titel, `DetailBody` = `.erp-secs`
  (Container-Abfrage), `DETAIL_PANE` (weiss), `ERP_HEAD_H` (125 px, Feed und Kopf), `DETAIL_MAXW` 1040.
- `controls.inputClass`: die eine Feldform grau ohne Rahmen (wie `.kt-input`); Suchliste und
  Adressfeld ohne eigene Form.
- Person: Verlauf · Zeit · Zahlungen · Person · Adressen · Firma · Mitarbeit/Rolle · Newsletter ·
  Sicherheit · System – mit `KtField`/`KtDate`/neu `KtSelect`, Adressbuch/Firma/Zugang im Konto-Kleid.
- Zeit: ohne Vertrag ein Satz + «Vertrag anlegen» (Entwurf gleich offen); Kennzahlen ohne Versalien;
  Verträge und Buchungen als Teile (`Sect`), «+»-Knöpfe wie «Lieferadresse hinzufügen».
- Verlauf: `ChangesSwitch`, `HistoryCard` an Artikel, Auftrag, Instanz, Dokument; Firma ebenso.
- Gesellschaft: doppelte Überschrift «Zeiterfassung» weg, Regeln ohne Versalien.

## Geprüft
Gebaut mit Schein-Anmeldung, echte Dev-Daten (Person, Gesellschaft, Dokument) und Testdaten
(Mitarbeiterin mit Vertrag): Person ohne/mit Vertrag, Vertrag anlegen, Tag + «Erfassen», Verträge und
Buchungen, Gesellschaft, Dokument mit Schalter, 1440/1100/390 px (kein seitliches Scrollen).
Artikel, Auftrag und Instanz nur über die gemeinsamen Bausteine (in Dev gibt es keine) – nach dem
Deploy ansehen.
