# Runde 16 · Das «+» als Eingabe wie bei Claude

Datum: 09.11.2026 · Rollback-Punkt: `02fcd3c` (develop vor dieser Runde)

## Was störte (Inhaber)
- Beim Mikrofon wechselte die ganze Oberfläche (die Aufnahme-Leiste ersetzte das Feld).
- Nach einer Aufnahme stand sie unter «Offene Gespräche» und zählte am «+», obwohl ihr Text schon
  im Feld lag – es sah aus wie ein Gespräch, bevor etwas gesendet war.

## Entschieden
1. Das Feld bleibt; die Aufnahme dezent in der Leiste mit Pegel-Animation (von rechts nach links).
2. Auto-Stopp nach **30 s Stille** (Claude Code: 15 s laut Doku; im Feld denkt man länger nach).
3. Der Text kommt ins Feld, kein Eintrag, keine Zahl – ein Gespräch erst mit dem Senden.
4. Der Entwurf bleibt beim Schliessen – nur, weil es ohne Tabelle geht (`localStorage`).
5. Während die KI antwortet, ist ➤ der Stopp (kein eigener Knopf mehr).
6. Dateien mit Ctrl+V einfügen oder hineinziehen.
7. Die Antwort der KI als Markdown – ohne Regeln, die KI formatiert, wie sie will.
8. (Kopieren-Symbol) – weggelassen.

## Gebaut
- `lib/recorder.silence` (eine Zahl, getestet), angeschlossen im Pegel-Takt von `use-recorder`.
- `RecordingBar` statt `RecordingStrip`: Punkt, Zeit, Pegel (grau), ■ – in der Leiste der Eingabe.
- `lib/draft` (Text, Stecknadel, Aufnahmen im Feld); `useDictation` im «+» schreibt laufende
  Aufnahmen zu Ende (`follow`) und legt fertige Texte einmal ans Ende des Feldes.
- Backend: `TalkIn.recordings` (Liste; mehrere Diktate in einer Nachricht) im `talk`-Ereignis;
  `recordings.open_for` erkennt Gesendetes daran. Der Auftrag der KI erlaubt Markdown.
- Die Zahl am «+» und «Offene Gespräche» zeigen Aufnahmen nur noch, wenn sie scheiterten.
- `markdown.tsx`: Markdown als React-Elemente, nie HTML; Links nur http(s).

## Geprüft
- Wächter gegen ihre Bug-Form: Stille ohne Neubeginn beim Laut → rot; ein Link mit beliebigem
  Schema → rot. Frontend: Typen, Lint, 161 Tests, Build. Backend: ganze Suite auf frischer DB.

## Verworfen
- Die gesprochene Aufnahme live mitschreiben (wie ein Diktat in Echtzeit): bräuchte Streaming zu
  Gemini; heute wird je 5-Minuten-Abschnitt abgeschrieben – günstig und robust.
- Den Entwurf am Server speichern: wäre eine Tabelle für eine Bequemlichkeit.
