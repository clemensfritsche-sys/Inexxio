# Runde «Dokumente – eine Ablage» (28.10.2026)

Ausgangslage: Konzept und Mockup (Artifacts «Dokumente» und «Mockup», vom Auftraggeber in neun
Runden abgenommen). Auftrag: alles vollständig umsetzen, auf Basis von `develop` (Stand
`104f63e`), in einem Zug, danach Deploy. Das Ergebnis beschreibt `docs/dokumente.md`.

## Was gemacht wurde – in vier Stufen

1. **Kern**: Tabellen `documents`, `document_refs`, `document_signatures`, `document_links`
   (Migration `157`), Objekttyp `document`, Anlage nur über `documents.file`, dieselbe Datei =
   dasselbe Dokument (partieller Unique-Index auf SHA-256), Referenzen und Pflichtfelder,
   Löschen nur ohne Referenz, Zugriff über die Referenz (`services/access`, Teil `time:` nur
   Person + Admin), Suche ohne KI. Feed «Dokument», Dokumentseite, der Entwurf, Kacheln unten
   an jedem Datensatz. **Jede schreibende Anfrage** steht jetzt im `audit_log`
   (`main.audit_writes`, Spalte `on_behalf`).
2. **KI-Tor** (`services/ai`): eine Tür, Aufgaben/Modelle in `TASKS`, structured outputs,
   Tagesdeckel 300, jeder Aufruf im Log. Lesen + Prüfen in EINEM Aufruf (`services/reading`):
   Art, Name, Text, Stichworte DE/EN, Nummern, Werte der Anforderung; zugeordnet wird im Code
   (wartendes Modul ≻ unsere Nummer ≻ Absender, Betrag ±5 %). Ohne Schlüssel: nichts davon,
   alles andere geht.
3. **Eine Ablage**: Belege (Papier als Dokument, Feld `voucher.doc`; `voucher_documents` hält
   nur noch Link, Partei, Mail – Migration `158`), Lieferantenrechnung und Ausfuhrnachweis
   (Felder statt `attachments.id`), Nachweis einer Absenz, Bild der Datenerfassung, Anhänge
   aus Gmail und Fotos des Kontaktformulars (öffnen den Entwurf), AGB und Datenschutz als
   Pflichtfelder der Gesellschaft (Website: AGB nach Land, Datenschutz/Impressum des
   Betreibers). **Vorschau → Freigeben** für jedes Papier; **AB und Quittung gehen nicht mehr
   von selbst** (`papers_due`, «zu tun», Verb `release`). Übernahme der Altdaten beim Start
   (`services/adopt`).
4. **Erstellen**: Scanner (OpenCV.js: Blatt finden, ruhig → Aufnahme, Ecken ziehen, mehrere
   Seiten → PDF), Verfassen im Chat (`services/composing`, Vorlage `document.written`,
   Unterzeichner-Linien), Senden (Link je Empfänger ohne Ablauf + Mail), Unterschreiben auf
   `/dokument` (Unterschrift auf dem Papier, «Abgelehnt» endgültig, gelöscht → 410).

## Unterwegs entschieden (Spielraum des Auftrags)

- **Kein jscanify-Paket**: es zieht `canvas` (native Abhängigkeit, Cairo) und `jsdom` – ein
  Risiko für jeden Build. Dieselbe Methode in 120 Zeilen (`lib/doc-scan.ts`) auf
  `@techstark/opencv-js`; Datei mit Version im Namen (`*.js` bleibt ein Jahr im Cache).
- **Verfassen mit Sonnet 5.5** statt Opus: ein Papier von ein paar Seiten braucht nicht das
  teuerste Modell. Lesen mit Haiku 5.5 wie vereinbart. Ohne Streaming: 8000 Tokens, 240 s.
- **Rechtstexte**: die Dateien unter `app/assets/legal/` bleiben – als **Vorlage**
  («Aus Vorlage übernehmen», ein Mensch entscheidet). Ein AGB-Dokument aus der Vorlage wird
  auf jedem Papier gesetzt; ein PDF wird nur genannt (sich nicht in HTML einbetten).
- **`voucher_documents` bleibt** als Versandzeile (Link `/beleg`, Partei, Mail): die Seite der
  Partei hat andere Verben (annehmen, bezahlen) als die eines Dokuments (unterschreiben). Das
  Papier selbst steht nur noch im Dokument; `html` fällt im Folge-Deploy weg.
- **Die Übernahme läuft beim Start, nicht in der Migration**: sie braucht Nummernkreis und
  Korb (Fachschicht). Selbstbegrenzend; die Rechtstexte nur, solange es noch gar keines gibt.
- **Ein Anhang aus Gmail wird erst beim Öffnen geholt** – gespeichert wird er erst mit der
  Freigabe (vorher gäbe es eine zweite Ablage).
- Ein Wächter (`test_the_object_registry_claims_only_what_it_can_serve`) verbot den Typ
  `document` (vom alten Modul); er prüft jetzt, dass es einen Endpunkt dafür gibt.
- Der alte Upload für PDF (`attachments.store_file`, `file-upload.tsx`) ist weg: der
  Upload-Endpunkt nimmt nur noch ein Bild, das kein Dokument ist (die Unterschrift).

## Barrieren

- **Kein `ANTHROPIC_API_KEY`** im Projekt: Lesen und Verfassen sind gebaut und gegen eine
  nachgebildete Schnittstelle geprüft, laufen aber erst mit Schlüssel (Secret Manager; der
  Dev-Deploy verdrahtet ihn, sobald es ihn gibt). Der Prod-Deploy hat keine optionalen Secrets.
- **Kein Cloud-Storage-Bucket** (keine Zugangsdaten): die Bytes liegen im Korb in der DB.
- **Alte Fotos der Datenerfassung** und alte Nachweise bleiben Bilder im Korb: sie stehen als
  URL im append-only Log bzw. in append-only Einträgen und werden nicht umgeschrieben.

## Gemessen

- Backend: 858 Tests grün gegen ein Schema nur aus den Migrationen (vorher 827), `ruff` sauber.
- Frontend: Typprüfung, Lint, Tests, Build; Website: Tests, `astro check`, Build, `export-erp`.
- Blatterkennung in Chromium: ein schräges Blatt auf dunklem Grund – Ecken auf ±1 px, gerade
  gezogen.
- Lokal mit Playwright (Beispieldaten, KI nachgebildet): Freigeben einer Datei, Senden mit
  Unterschrift, Unterschreiben auf `/dokument` (Zustand Freigegeben), Verfassen im Chat,
  zweite gleiche Datei → «gibt es schon», Scanner mit Kamera-Attrappe (zwei Seiten in den
  Entwurf), Vorschau einer Offerte (nichts gespeichert). Gefunden und behoben: kaputte
  Vorschaubilder im Entwurf (Bildadressen zu früh freigegeben), ein voller Name wurde keine
  Person, «Auftrag · Auftrag …» doppelt.

Rollback-Punkt: `104f63e` (develop vor dieser Runde).

## Nachtrag – Altlasten weg, Cloud Storage an (28.10.2026)

Auftrag: die zwei offenen Punkte löschen, Cloud Storage aktiv (dev und prod getrennt), alte
Fotos und Nachweise müssen nicht mitkommen.

- **Übernahme alter Daten entfernt** (`services/adopt` hält nur noch die Rechtstexte):
  Rückwärtskompatibilität ist nicht verlangt. `voucher_documents.html` hat sein Mapping
  verloren und fällt im Folge-Deploy (Migration `160`, Zwei-Deploy-Regel).
- **Cloud Storage**: je Umgebung ein Bucket `<Projekt>-files` mit Zugriff für
  `cloudrun-backend@…`. Der Deploy durfte ihn nicht anlegen (`deploy-sa` ohne
  `storage.buckets.create`) – angelegt hat ihn der Auftraggeber einmal in der Cloud Shell; der
  Deploy setzt `FILES_BUCKET` jetzt fest, ohne nachzusehen. Die Bytes gehen in den
  Bucket, `attachments.data` ist leer (Migration `159`). **Ohne Bucket oder bei einem Fehler
  bleiben sie in der Zeile** – eine Datei geht nie verloren, weil der Speicher hakt. Die
  Vorschau eines Belegs (zurückgerollt) schreibt nie in den Bucket (`in_database`); gelöscht
  wird ein Objekt erst nach dem Commit.
- **KI-Schlüssel**: auf dev lag er schon im Secret Manager und war eingebunden; der
  Prod-Deploy bindet `ANTHROPIC_API_KEY` (und Gmail) jetzt ebenso optional ein.
- Das Design-Canvas «INEXXIO Dokumente» ist gelöscht.
- **Scanner fand kein gewöhnliches Blatt**: eine Karte (Canny 50/150) und «die grösste
  Kontur» scheiterten an weissem Tisch, Daumen am Rand, Gegenstand daneben, Blatt weiter weg
  (nachgestellt: 6 von 10; zufällig 20 von 120). Jetzt drei Karten (hell · Kanten · Kanten
  fein), konvexe Hülle, und ein Viereck zählt nur, wenn sein Rand trägt (innen heller als
  aussen, an allen vier Seiten): 10 von 10, zufällig 116 von 120, kein Schein-Blatt auf leerem
  Tisch. Wächter `frontend/scripts/doc-scan.test.mjs` (die alte Fassung fällt durch).
- **KI las nichts, und niemand erfuhr es**: der Entwurf verschluckte einen Fehler der Anfrage
  still, und jede Anfrage läuft über Firebase Hosting, das nach 60 s abbricht (Lesen wartete bis
  90 s mit Wiederholung, Verfassen bis 240 s). Jetzt: Lesen höchstens 50 s, Verfassen 55 s, kein
  zweiter Versuch, kürzere Antworten; `ai.problem()` nennt den Grund eines Ausfalls, und der
  Entwurf zeigt oben über «Art», dass die KI liest – oder warum nicht.
