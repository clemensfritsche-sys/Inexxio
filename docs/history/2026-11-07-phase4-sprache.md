# Phase 4 · Sprache (07.11.2026)

Auftrag: Schritt 4 der Projektakte «Die lernende Firma» vollständig umsetzen, am Schluss prüfen
und deployen; dazu die kleine Verbesserung am Hinweis zum Deckel der KI (Betrag statt fester
80 %). Ausgangspunkt: develop `d4594ee` (Phase 3 auf dev).

## Vorgehen

1. **Bauplan** als Vertrag (`docs/konzept/phase4-bauplan.md`).
2. **Zwei Helfer parallel:** Backend (Stücke, `recording_chunks`, Migration 171, `ai.transcribe`
   über dieselbe Vertex-Stelle wie `embed`, `recordings.advance` in Anfrage und Takt, Aufgabe
   `voice`, Aufräumen nach 24 h) und Oberfläche («Aufnehmen» im «+», Zeit, Pegel, Stopp,
   Wake Lock, Warteschlange, «schreibt ab …» → «Abgelegt»).
3. **Zusammengeführt** und selbst ergänzt: lange Teile werden mehrere Notizen
   (`intake.pieces`); was nach einem Tag schon abgeschrieben ist, bleibt als Erfassung.
4. **Unabhängige Prüfung** mit echten `MediaRecorder`-Stücken (Chromium + ffmpeg): WebM und
   fragmentiertes MP4 lassen sich aneinanderhängen – solange Stück 0 eines Abschnitts da ist.
5. **16 Befunde behoben** (unten), dann Volltest und Deploy.

## Befunde und Lösungen

| Bereich | Befund | Lösung |
|---|---|---|
| Verlust | Ein Stück wurde nach ~25 s Netzloch aufgegeben; ohne Stück 0 ist ein Abschnitt verloren | nie aufgeben, solange die Seite lebt (Pausen bis 30 s, Zeitgrenze je Versuch); Abschnitt ohne Stück 0 mit Vermerk, ohne Gemini zu bezahlen |
| Verlust | Nach 10 Min. ohne Stück galt eine laufende Aufnahme als beendet | abgebrochen erst nach 30 Min. Ruhe; 409 beendet den Recorder mit klarer Meldung |
| Verlust | Mikrofon fällt aus (Anruf, Headset) – unbemerkt | `onerror`, `ended`, `mute` → Meldung und sauberer Stopp; `requestData` bei `pagehide` |
| Verlust | Stopp wartete 5 s auf das letzte Stück | wartet auf das `stop`-Ereignis |
| Zeit/Kosten | ein Abschnitt, der nie in die Zeit passt, kostete ohne Ende | Abschnitt 5 Min., mindestens 40 s Rest, höchstens 6 Fehlversuche, geschätzte Kosten bei Zeitüberschreitung, `MAX_TOKENS` nie übernommen, über 15 MB übersprungen |
| Zeit | Löschen vieler Stücke in der Anfrage | gebündelt |
| Datenschutz | gelöschtes Audio 7 Tage wiederherstellbar (Soft Delete) | eigener Bucket `<projekt>-recordings` ohne Soft Delete, Regel 1 Tag (`infra/setup-sprache.sh`); ohne ihn die Stücke in der DB, nie im Datei-Bucket |
| Lange Meetings | die KI hätte beim Ablegen kürzen können | aus einer Aufnahme legt die KI in **Bereichen nummerierter Absätze** ab; den Text baut der Code wörtlich |
| Sichtbarkeit | gescheiterte Aufnahmen nirgends zu sehen | im «+» unter «Nicht abgelegt» mit Grund; «Nichts zu hören» zählt nicht |
| Robustheit | Sperre vor dem Commit freigegeben, Verbindung konnte lecken | je Aufnahme committen, Verbindung immer zu |
| Region | Gemini 3.x steht womöglich nicht in `europe-west3` | eigene Einstellung `VERTEX_GEMINI_REGION`; ein 404 nennt Modell und Region |

Jeder Wächter gegen seine Fehlerform gegengeprüft.

## Gemessen

Backend 876 Tests grün (1 bekannter Skip), Frontend 81, Type-Check, Lint, Build.

## Offen – auf dev mit Clemens zu prüfen

- Eigene Testaufnahmen in Mundart: stimmen Namen und Zahlen? Steht `gemini-3.5-flash` in der
  Region (sonst `VERTEX_GEMINI_REGION` setzen)?
- Eine Aufnahme von einer Stunde auf dev, Audio danach weg.
- iPhone (Safari): `audio/mp4`, Bildschirmsperre – auf echtem Gerät nicht geprüft.
- Modell: Gemini 2.5 ist auf Vertex seit Oktober 2026 abgeschaltet; `gemini-3.5-flash` läuft
  laut Google bis mindestens Mai 2027 (EINE Stelle: `ai.TRANSCRIBE_MODEL`).
