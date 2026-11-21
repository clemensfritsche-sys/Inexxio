# Runde 06.11.2026 – Phase 2 «Fundament» (Die lernende Firma)

**Auftrag (Clemens):** Phase 2 der Projektakte vollständig umsetzen, selbst kontrollieren, ausrollen.

## Gebaut (Schritte 2.1–2.6 der Akte)
- **2.1 Feld-Baustein:** `useField` (eine Logik: Wert, weiche Prüfung, Pflicht, Enter, Hinweis;
  Ansatzpunkt für Vorschläge in 3.4) und `Field`/`SelectField` bzw. `Input`/`Select`/`TextArea`
  (gleiche Logik, eigenes Aussehen – das Zahlungsmodul). 30 Dateien umgezogen; ESLint-Wächter
  `RAW_FIELD` verbietet lose Felder in ERP, Konto, Kundenseite. 17 Ansichten vorher/nachher
  pixelgleich (Chromium), Tastatur und Auto-Save gleich.
- **2.2 Prüfsumme im Log:** ein Wert über 2'000 Zeichen steht als `{sha256, len}` (`log_shorten`).
- **2.3 Kommunikation skalierbar:** Spalte `messages.topic` (Anliegen) mit Index; «offen» als eine
  SQL-Bedingung (`communication._ANSWERED`), Regel unverändert; Verlauf in Seiten. Gemessen mit
  50'000 Nachrichten: Seite 24–44 ms, «zu tun» 155 ms. Auf Bestandsdaten: «offen»-Zahlen mit altem
  und neuem Code identisch.
- **2.4 Notiz an jedem Datensatz:** `message_parties.object_id` (Zwei-Deploy-Regel mit Brücke),
  Kanal `note` (nie offen, nie hinaus, nie Antwort), Korrektur per Vermerk (`move_note`).
- **2.5 Ein Verlauf:** `GET /erp/history/{object_id}` (Nachrichten, Dokumente, Änderungen nach
  `request_id`, Cursor über drei Quellen), eine Komponente an Person, Firma, Auftrag, Artikel,
  Instanz, Dokument; `GET /erp/messages` entfällt.
- **2.6 Der Takt:** `POST /internal/tick` (Google-Token, `core/oidc`), Aufgaben Siegel und Mails
  (`services/tick`), Deploy-Job `scheduler`, einmaliges `infra/setup-takt.sh`.

## Arbeitsweise
Drei Stränge parallel (je eigene Arbeitskopie), zusammengeführt, unabhängig gegengelesen.
Befunde des Gegenlesens behoben: Anliegen aus dem Ausroll-Fenster (Migration 169 holt nach), Takt
überschreitet seine Frist nicht mehr (Gelesen-Markieren erst danach), Verlauf gruppiert nur ein
Fenster der neuesten Zeilen, eine Notiz beantwortet nie etwas, kein Zusatzpaket für den Takt.

## Gemessen
Backend 795 Tests grün; Frontend Typen, Lint, 63 Tests, Build grün; Website-Build grün.
Migration 168 auf Bestandsdaten: Rückfüllung vollständig, Invarianten-Bericht identisch, die
alte Fassung schreibt während des Ausrollens weiter (Brücke).

## Offen / zweiter Deploy
Migration 169: `person_object_id`, Brücke und Index weg; Anliegen nachholen. Takt: einmalig
`infra/setup-takt.sh` je Projekt ausführen (siehe `infra/README.md`), sonst bleibt der Deploy-Job
«Takt» rot (Hosting geht trotzdem hinaus).
