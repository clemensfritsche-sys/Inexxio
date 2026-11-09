# Runde 15 · Der Assistent: Vorschlag statt Ausführen, Tempo, Eingabe wie bei Claude

Datum: 09.11.2026 · Grundlage: Mockup und Konzept «Lernschlaufe Inexxio», Runde 15
(https://claude.ai/artifact/8jAy56JQ1jEESPwgRHPSSK, Abschnitte 1–9) · Rollback-Punkt: `bfc0cd5`

## Was entschieden war
- **A · Namen:** Assistent · Gespräch · Vorschlag · Wissen; «Auf einen Blick» ersetzt «Angeheftet».
- **B · Die KI führt nie aus.** Im Gespräch je Vorschlag nur «Öffnen» und «✕». Was sich ändert,
  steht am Datensatz (alt → neu) mit «Übernehmen»; Neues geht in den Entwurf. «Ändern» weg,
  «Ausführen über MCP» weg.
- **C · Tempo:** die Handlungen als Katalog im zwischengespeicherten Auftrag (aus den Routen
  erzeugt, nie gepflegt), der offene Datensatz gleich mit der Nachricht, die Antwort Wort für
  Wort, «Auf einen Blick» im Takt mit dem schnellen Modell vorbereitet.
- **9 · Eingabe wie bei Claude:** der Text einer Aufnahme kommt in die Eingabe (ergänzen, dann
  selbst senden), die Stecknadel als Chip, «←» zurück zur Übersicht.

## Was gebaut ist
- **Backend:** `handgriff.run` = Übernehmen (ohne geänderte Werte), `changes_of` (alt → neu aus
  der lesenden Route desselben Pfads, wie es *jetzt* ist – darum braucht es kein «inzwischen
  geändert» mehr); `probe`, `operation`, `missing`, `hand`, `seen` entfernt. `talk.answer` ohne
  Ausführen-Werkzeug, Antwort als Text (`ai.converse` ohne Schema streamt, `on_text`), dazu
  `ai_tools.catalog()` und der offene Datensatz im Auftrag. `pins.ahead` im Takt (Haiku, höchstens
  10 je Lauf, zuletzt geöffnet in 30 Tagen). Aufnahme: `recording.done` trägt den Text; die Person
  schickt ihn (`TalkIn.recording`, geprüft: nur die eigene).
- **Frontend:** `handgriff-card` neu (Gespräch: Öffnen/✕; am Datensatz: alt → neu, Übernehmen
  bzw. Entwurf öffnen), `pinned` = «Auf einen Blick», `capture-sheet` mit Live-Text, Aufnahme ins
  Feld (auch aus «Offene Gespräche», mit Verwerfen), Stecknadel-Chip, «←».
- Zwei Routen weniger (157).

## Geprüft
- Backend: ganze Suite auf frischer DB (Schema aus den Migrationen). Die neuen Wächter gegen ihre
  Bug-Form gegengeprüft: ohne Katalog im Auftrag, `ahead` als No-op, «alt» eingefroren statt
  jetzt – jeder schlägt an.
- Frontend: `tsc`, ESLint, `npm test` (157), Build.

## Verworfen
- «Ändern» mit Formular aus dem JSON-Schema der Route: viel Code für einen seltenen Fall; der
  Entwurf bzw. der Datensatz selbst ist der Ort zum Ändern.
- Ausführen auf ein Wort im Gespräch: bequem, aber die Person sieht dann nicht, was sich ändert.
