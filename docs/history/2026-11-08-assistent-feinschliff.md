# 08.11.2026 · Der Assistent – Feinschliff nach dem ersten Test

Auslöser: Clemens' erster Test auf dev («Artikel ERP und Website anlegen», gesprochen).

## Gefunden

1. **«Die KI hat noch nicht geantwortet – der Takt holt es nach»** nach einer Aufnahme: Abschreiben
   und Antworten teilten sich die 60 s des Hostings; die KI bereitete die Notiz vor, für ihren Satz
   blieb keine Zeit.
2. **Kein Artikel-Entwurf:** der Probelauf wies ab (Abmessungen, Gewicht, Prozessschritt fehlen) –
   «was nicht geht, wird keine Karte»; «Entwurf öffnen» gab es nur für Person, Firma, Dokument.
3. **Schwache Antwort:** die KI konnte nur vier Dinge lesen (die Module des ERP nicht), fragte statt
   zu probieren, und meine Formatvorgabe verleitete zu «Ich habe noch nichts vorbereitet».
4. **Verschwundene Nachrichten:** eine Aufnahme begann immer ein neues Gespräch – im offenen
   gesprochen, landete die Frage in einem zweiten, das nach der Antwort verschwand.

## Gebaut

- **Live wie bei Claude** (`talk.stream`, `POST …/assistant/talks` als NDJSON): Nachricht sofort,
  jeder Schritt der KI, am Ende das Gespräch; «Stopp» (`talk.stop`, ein Ereignis – gilt über alle
  Instanzen). Direkt am Dienst (`BACKEND_URL`, vom Deploy), nicht über das Hosting; Cloud Run 300 s,
  die KI 240 s als Netz, sonst Schritte und Deckel. Die KI arbeitet in eigenem Faden und eigener
  Sitzung; reisst die Leitung, arbeitet sie zu Ende. Eine Sperre je Gespräch (Stream ↔ Takt).
  Verworfen: «Wird die Zeit knapp, antwortet die KI sofort» (Clemens: Qualität vor Zeit) und
  «weiter»-Runden über mehrere Anfragen.
- **Unvollständig ist eine Karte** (`handgriff.incomplete`, 400/422): «Fehlt noch: …», Ausführen
  gesperrt (Tor im Dienst), «Entwurf öffnen» für Person, Firma, Artikel, Auftrag, Dokument.
- **`abrufen`**: jede lesende Route des Personals (`handgriff.reads`, `look`) – durch die echte
  Route als `ai_tools.reader`, verworfen, ohne Weg nach aussen.
- **Antwortformat**: direkt, kurz, reiner Text; vorbereiten statt fragen.
- **Aufnahme im Gespräch** (`recording.start.talk`); die Aufnahme antwortet nicht mehr selbst –
  das «+» lässt die KI live antworten, ohne «+» der Takt.
- **Tür zur KI**: Zwischenspeicher (`cache_control` auf der Anleitung; Lesen kostet 0.1, Schreiben
  1.25 des vollen Preises) und `ms` je `ai.call` (auch beim Abschreiben).

- **Nur das Ergebnis**: Karten, die die KI selbst weglegt (ersetzt), stehen nicht im Gespräch
  (Clemens' zweiter Test: zwei durchgestrichene Karten mit «Einzelteil» statt `unit`).

## Geprüft

- Backend 879 Tests (frische DB), neu: unvollständige Karte, abrufen (nicht Admin, nicht schreibend),
  Stream mit Schritten und `ms`, Stopp, Aufnahme im offenen Gespräch; Gegenprobe je Wächter (ohne
  `incomplete`, ohne Gespräch an der Aufnahme, ohne Stopp-Prüfung → rot).
- Echter Server mit nachgebildeter KI: Stream Zeile für Zeile, Zwischenspeicher gelesen, CORS der
  direkten Adresse für `inexxio-dev.web.app`.
- CSP: `connect-src` erlaubt `https://*.a.run.app` (Clemens: Weg 1 – eine Zeile statt einer Adresse je Umgebung).
- Browser: Schritte live mit «Stopp», Karte «Fehlt noch», Ausführen gesperrt, «Entwurf öffnen» →
  Artikel-Entwurf mit «ERP».
- Frontend: Typen, Lint, 79 Tests.
