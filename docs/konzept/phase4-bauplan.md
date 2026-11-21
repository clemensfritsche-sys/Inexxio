# Phase 4 · Sprache – Bauplan (Vertrag zwischen Backend und Oberfläche)

> **Kopfstatus:** gebaut (07.11.2026) · gehört zur Projektakte
> `docs/konzept/lernende-firma.md` (§4.4 «Aufnehmen», «Abschreiben», §6 Phase 4). Baut auf
> Phase 3 (`docs/konzept/phase3-bauplan.md`): aus einer Aufnahme wird eine **Erfassung**
> (`intake`), danach ist alles wie beim Schreiben («Abgelegt», «Stimmt so»).

## Grundsätze (aus der Akte, verbindlich)

- **Ein Weg für jede Eingabe:** Gesprochenes wird Text; der Text ist die Erfassung. Vom
  Gesprochenen bleibt **nur der Text** – das Audio wird nach der Abschrift gelöscht,
  **spätestens nach einem Tag**.
- **Nichts geht verloren:** die Aufnahme geht **in Stücken** hoch (alle 30 s); bricht sie ab
  (Akku, Netz, Tab zu), ist alles bis zum letzten Stück da und wird abgeschrieben.
- **Abschreiben macht Gemini** über **Vertex AI** im eigenen Projekt (Region `VERTEX_REGION`,
  Europa; Eingaben nicht zum Training) – durch **dieselbe Tür** `services/ai.py`, derselbe
  Deckel in Franken, jeder Aufruf ein `ai.call`. **Verstehen und ablegen macht Claude** (Phase 3).
- **Im Namen der Person, die aufgenommen hat.** Nur sie (und der Admin) sieht ihre Aufnahme.
- **Ohne Netz wird nichts vorgesehen** (kein Speichern im Browser über die Sitzung hinaus).
- Gespräche aufnehmen: die Verantwortung trägt Clemens (Akte).

## Aufnahme im Browser

- `MediaRecorder` (Opus in WebM, sonst was der Browser kann – Safari: `audio/mp4`), Mono,
  24 kbit/s; **Stücke alle 30 s** (`timeslice`); **ein Abschnitt = 5 Minuten** – danach endet
  der Recorder und ein neuer beginnt am selben Mikrofon (jeder Abschnitt ist eine eigene,
  vollständige Datei → einzeln abschreibbar, klein, schnell). Höchstens 3 Stunden.
- **Bildschirm bleibt an** (Wake Lock, nach dem Zurückkehren in den Tab neu angefordert).
- Nur das Nötigste: Zeit, Pegel, Stopp (Mockup «Aufnahme»).
- **Ein Stück wird nie aufgegeben, solange die Seite lebt:** wiederholt mit wachsender Pause
  (höchstens 30 s), ohne Ende; jeder Versuch mit Zeitgrenze (30 s). Aufgegeben nur bei einer
  Abweisung 4xx (ausser 408/429), dann `tell`. Solange Stücke warten, steht ruhig «wartet auf
  Netz» (eine Meldung beim ersten Hängen, nicht je Versuch).
- **Fällt das Mikrofon aus** (Fehler des Recorders, Spur beendet, länger stumm): einmal «Mikrofon
  getrennt – Aufnahme beendet», dann sauber beenden (letztes Stück, Stopp). Beim Verlassen der
  Seite (`pagehide`, unsichtbar) geht das Letzte sofort hoch (`requestData`).
- **Kommt ein Stück zu einer fertigen Aufnahme (409)**: sofort sauber beenden und klar sagen
  «Diese Aufnahme ist schon abgeschlossen – bitte neu starten».
- Der Stopp wartet auf das `stop`-Ereignis des Recorders (davor kommt das letzte Stück), mit
  einer grosszügigen Sicherheitsgrenze.

## Ereignisse im Log (keine Insel)

| Ereignis | `object_id` | `payload` |
|---|---|---|
| `recording.start` | der offene Datensatz (Hinweis), sonst die Person | `{hint, mime}` |
| `recording.stop` | wie oben | `{recording, segments}` |
| `recording.segment` | wie oben | `{recording, segment, text, seconds}` – die Abschrift eines Abschnitts |
| `recording.done` | wie oben | `{recording, intake}` – fertig, Audio gelöscht |
| `recording.failed` | wie oben | `{recording, problem}` – aufgegeben (z. B. nach einem Tag ohne Abschrift) |

Die Nummer einer Aufnahme ist die Log-Id von `recording.start`. **Die Stücke** liegen als Dateien
in einem **eigenen Bucket ohne Soft Delete** (`RECORDINGS_BUCKET` = `<projekt>-recordings`,
`recordings/<Aufnahme>/<Abschnitt>-<Stück>`; ohne ihn oder wenn er hakt in der Datenbank – nie im
Datei-Bucket, dessen Soft Delete gelöschtes Audio eine Woche hielte) und
sind in **`recording_chunks`** verzeichnet (Aufnahme, Abschnitt, Stück, Grösse; eindeutig je
Aufnahme+Abschnitt+Stück – ein zweites Hochladen desselben Stücks ersetzt es). Die Tabelle steht
**nicht** im Log (`EXEMPT`: technische Stücke, gelöscht nach der Abschrift). Die Ereignisse der
Aufnahme stehen nicht im Verlauf (`history.HIDDEN_EVENTS`).

## Ablauf

1. **Start** → `recording.start`. **Stücke** gehen hoch (in Reihenfolge, wiederholbar).
2. **Stopp** → `recording.stop`. Eine Aufnahme ohne Stopp, deren letztes Stück **30 Minuten**
   alt ist, gilt als abgebrochen und wird **wie gestoppt** behandelt (Akte: «Abbruch → was bis
   dahin aufgenommen ist, ist da»). 30 statt 10 Minuten: ein Netzloch schliesst die Aufnahme
   nicht, während der Browser noch aufnimmt.
3. **Abschreiben** je Abschnitt (`ai.transcribe`, Gemini) → `recording.segment` – begonnen nur,
   wenn noch 40 s bleiben. **Mit Vermerk übersprungen** (ohne Gemini zu fragen): kein Stück, kein
   Stück 0 (ohne Kopf nicht lesbar), über 15 MB; nach zwei Ablehnungen; nach sechs Fehlversuchen
   ohne Ablehnung (Zeit, 5xx, 429, `MAX_TOKENS`). Im Text steht jede Lücke als «[Abschnitt n:
   Grund]». Im Takt kommt die Aufnahme mit dem jüngsten Fehlschlag zuletzt. Dann der ganze
   Text → **eine Erfassung** (`intake.capture`, Hinweis = der der Aufnahme) → die KI legt ab wie
   bei «Schreiben» → `recording.done` → **Stücke gelöscht** (Bucket + Zeilen).
4. Das alles macht **eine** Funktion `recordings.advance(db, id)` – so weit, wie die Zeit reicht
   (`ai.until`). Sie läuft **in der Anfrage** (`POST …/advance`, die Oberfläche fragt nach,
   bis es fertig ist – kurz für kurze Aufnahmen) **und im Takt** (lange Aufnahmen, Tab zu).
5. **Aufräumen im Takt:** ein Stück, das älter als **24 Stunden** ist, wird gelöscht – was bis
   dann nicht abgeschrieben ist, wird `recording.failed` mit Grund. Zusätzlich hält der Bucket
   eine Regel: jedes Objekt nach einem Tag weg (`infra/setup-sprache.sh`). Gelöscht wird
   gebündelt (je 100 eine Anfrage).
6. **Ablegen einer Aufnahme:** der Text geht in **nummerierten Absätzen** (Zeilen, lange Zeilen
   an Satzenden) an die KI; sie nennt je Teil nur `object_id`, `subject`, `from`, `to`. Der Code
   baut den Text wörtlich (`intake.spoken_parts`): jeder Absatz genau einmal, nichts gekürzt;
   was keinem Teil gehört, geht an den Datensatz der Erfassung. Getippte Erfassungen wie bisher.

## API (`/api/v1/erp`, Personal)

```
POST /recordings                         {hint_object_id?, mime, context?} → Recording  (context: die Stecknadel)
POST /recordings/{id}/chunks             multipart: segment, seq, file     → Recording
POST /recordings/{id}/stop               {segments}                        → Recording
POST /recordings/{id}/advance                                              → Recording
GET  /recordings/open                                                      → Recording[]  (meine, nicht fertig; gescheiterte 7 Tage, «Nichts zu hören» und verworfene nie)
POST /recordings/{id}/dismiss                                              → Recording  (eine gescheiterte verwerfen: `recording.dismissed`)
```

```ts
Recording = { id: number, at: string, hint_object_id: number|null, mime: string,
              state: 'recording'|'transcribing'|'filing'|'done'|'failed',
              segments: number /* bekannt */, transcribed: number, seconds: number,
              intake: Intake|null /* wenn abgelegt bereit */, problem: string|null }
```

- `state`: `recording` (kein Stopp, nicht abgebrochen) · `transcribing` (gestoppt, Abschnitte
  fehlen) · `filing` (Text da, Erfassung entsteht/KI legt ab) · `done` (es gibt die Erfassung;
  `intake` gesetzt – die Oberfläche öffnet «Abgelegt») · `failed` (`problem`).
- Ein Stück: höchstens 4 MB; nur die Person, die aufnimmt; nach `done`/`failed` 409.
- **Die Zahl am «+»** (nicht «zu tun» an der Person): Aufnahmen, die fertig abgeschrieben, aber
  nicht abgelegt sind, zählen als offene Erfassung (Phase 3); unfertige und fehlgeschlagene als
  Aufnahme (nicht: «Nichts zu hören», `silent`; nicht: verworfene).
- **Die Oberfläche** (Erfassen neu, November 2026): die Aufnahme läuft *im* Eingabefeld des «+»
  (Punkt, Zeit, Pegel, Stopp); nach dem Stopp steht dort das Skeleton, bis «Abgelegt» kommt. Die
  Schleife «weiter abschreiben» gehört nicht dem Fenster (`lib/transcribe.ts`): schliesst man,
  läuft sie weiter und meldet sich.

## Die KI

- `ai.transcribe(db, raw, mime, *, actor, seconds)` → Text oder `None` (`ai.problem()` sagt
  warum, `refused()` / `faulted()` was es war): Vertex AI `generateContent` in der Region
  `VERTEX_GEMINI_REGION` (leer = `VERTEX_REGION`; ein 404 nennt Modell und Region), Modell
  `TRANSCRIBE_MODEL = "gemini-3.5-flash"` (an EINER Stelle; Gemini 2.5 ist auf Vertex seit
  Oktober 2026 abgeschaltet), Audio als `inlineData` (ein Abschnitt ≤ 15 MB, meist < 1 MB).
  Kam keine Antwort in der Zeit, stehen **geschätzte Kosten** im `ai.call` (Audio-Sekunden × 32
  Tokens/s), damit der Deckel greift. Auftrag: wörtlich abschreiben, **auf Hochdeutsch in Schweizer
  Schreibweise (ss)**, auch wenn Mundart gesprochen wird; Namen, Zahlen, Masse genau; bei
  Sprecherwechsel neue Zeile; nichts hinzufügen, nichts zusammenfassen. Kosten aus
  `usageMetadata` in `ai.PRICES`; Deckel und `ai.until` wie jeder Aufruf; keine
  Wiederholung unter `until`; nach Abweisung (401/403/404) eine Stunde Pause wie `embed`.

## Fertig, wenn … (Akte)

- Abbruch → was bis dahin aufgenommen ist, ist da (Test: Stücke ohne Stopp → nach 30 Min. Ruhe
  abgeschrieben; nach 15 Min. noch offen).
- Eigene Testaufnahmen in Mundart: Namen und Zahlen stimmen (Clemens, auf dev).
- Eine Aufnahme von 1 Stunde läuft auf dev durch · Audio danach gelöscht.
