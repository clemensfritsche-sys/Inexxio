# 08.11.2026 · Phase 5 «Der Assistent» – Rundenbericht

Bauplan: `docs/konzept/phase5-bauplan.md` (Abweichungen dort in §11). Auftrag von Clemens: das
neue Konzept vollständig umsetzen, nicht rückwärtskompatibel, sauber, schlicht; prüfen, deployen.

## Was gebaut ist

1. **Speichern an einer Stelle.** `get_db` speichert am Ende jeder Anfrage (`scope="function"` –
   gemessen: so läuft das Speichern vor der Antwort; ohne den Geltungsbereich bekam der Client ein
   «200», obwohl das Speichern scheiterte). Rund 90 `commit` in Routern und Anfrage-Diensten sind
   `flush` oder weg. Hintergrundarbeit (Takt, Abgleich, Abschreiben) speichert je Einheit.
2. **Die Tür nach aussen** (`core/outside`): `after` (nach dem Speichern – Mails über
   `mailbox.send_after`, Löschen im Speicher, Zurückziehen eines Gmail-Tokens) und `now` (KI,
   Stripe, Gmail; im Probelauf `NeedsHand`). Eine Person anlegen erzeugt kein Anmeldekonto mehr.
3. **Der Handgriff** (`services/handgriff`): Handlungen aus den Routen (54 heute), Aufruf über
   ASGI mit den Rechten der Person, Probelauf in eigener Sitzung, Ausführen genau einmal
   (eindeutiger Index), Platzhalter `{"$handgriff": n}`, «inzwischen geändert», «nur von Hand».
4. **Das Gespräch** (`services/talk`, `routers/assistant`): Nachrichten im Log, die KI mit
   Werkzeugen (lesen, nachschlagen, vorbereiten, weglegen, ausführen auf ein Wort), Takt holt nach.
   Aufnahmen werden eine Nachricht im Gespräch. Handgriffe aus Mails (`follow`).
5. **Wissen**: das Angeheftete (offene Handgriffe + Wissen, neu gewählt nur bei Änderung im
   Umfeld), das Umfeld aus dem Log (`surroundings`), «im Wissen suchen» (Notizen, Dokumente,
   entschiedene Handgriffe; Migration 174).
6. **Oberfläche**: das «+» als Gespräch mit Handgriff-Karten (Ausführen/Ablegen, Entwurf öffnen,
   Ändern mit Feldern aus dem Schema der Route, Weg, Öffnen), Foto/Datei ins Gespräch, «Offene
   Gespräche»; das Angeheftete neu; das Zeichen am Feld ist weg.
7. **Jede Route beschreibt sich** (33 Docstrings ergänzt, Wächter).

## Entfernt

`services/intake.py`, `services/proposals.py`, `routers/proposals.py`, `schemas/proposals.py`, die
Ereignisse `intake`/`proposal`/`proposal.decided`/`pin.solved` (bleiben im Log, werden nicht mehr
gelesen), `ix_log_decided`, das Festschreiben im Takt; im Frontend `lib/proposals.ts`,
`lib/settled.ts`, `form/proposal-mark.tsx`, `capture/filed.tsx`, `capture/proposal-card.tsx`, der
Vorschlag in `useField` und `objectId` an jedem Feld.

## Geprüft

- Backend 870 Tests grün (vor dem Gegenlesen) (gegen ein Schema nur aus den Migrationen), darunter neu
  `test_handgriff.py` (Probelauf hinterlässt nichts und geht nie hinaus – Netz gesperrt; Rechte;
  halbe Anfrage hinterlässt nichts; jede Route beschreibt sich; kein `commit` in Routern) und
  `test_assistant.py` (vorbereiten ≠ ausführen, genau einmal, aufeinander aufbauen, inzwischen
  geändert, Rechte, privat, KI aus, Mails in «zu tun», Angeheftetes fragt nur nach einer
  Änderung, nur von Hand). Gegenprobe: ohne Verwerfen im Probelauf, mit Admin-Rechten für den
  Handgriff, mit `commit` statt `rollback` bei Fehler – je der passende Wächter rot.
- Rauchtest mit dem echten Server (uvicorn) und nachgebildeter KI: Gespräch → Werkzeug →
  Probelauf über ASGI → Karte → Ausführen → zweites Ausführen 409 → «inzwischen geändert» 409.
  Dabei gefunden und behoben: doppelte Nummer im Namen der Karte; eine neue Nachricht der Person
  galt als «Änderung an ihr».
- Im Browser (Playwright): Gespräch, Karte, Ablegen, Angeheftetes; dabei behoben: der Hinweis
  «sieht nach …» blieb nach einem Fehlschlag stehen, das Angeheftete fragte nach jedem Nachladen
  neu (jetzt je Stand des Umfelds höchstens einmal, `mark`).
- Frontend: Typen, Lint, 79 Tests, Build.

## Gegengelesen (unabhängig) – gefunden und behoben

1. **Hoch:** die KI hätte über «ausführen» jeden sichtbaren Handgriff ausführen können (auch aus
   einer Mail, im selben Zug, im Takt). Jetzt im Code: nur im Gespräch, das die Person gerade
   führt, nur ein Handgriff **dieses** Gesprächs, den sie vor ihrer letzten Nachricht sah; im Takt
   und aus Mails gibt es das Werkzeug nicht.
2. Ein verworfener Sicherungspunkt verwarf alle Haken «nach dem Speichern» der Anfrage – jetzt je
   Transaktion (`outside._within`).
3. Anfrage und Handgriff hätten aufeinander warten können (die Anmeldung schreibt die Person, der
   Handgriff sperrt sie) – `handgriff.release` speichert vorher, dazu `lock_timeout` als Netz.
4. Zwei Klicks: die Route lief zweimal (der zweite scheiterte erst am Ende) – jetzt eine Sperre je
   Handgriff vor dem ersten Schritt.
5. Jede Änderung (Auto-Save) hätte die KI das Wissen neu wählen lassen – höchstens einmal je 15
   Minuten (`pins.QUIET`).
6. «Entwurf öffnen» und dann weg: eine spätere Anlage hätte den Handgriff erledigt – die Verbindung
   fällt beim Wegnavigieren.
7. Ein Probelauf, der nach aussen ging, machte den Handgriff zu «nur von Hand» – nur eine Datei
   braucht die Hand.
8. Abhängigkeiten werden gegen die Rechte der Person geprüft.
9. Pfade mit Punkt-Teilen, Abfrage oder Kodierung sind keine Handlung.

Danach 874 Backend-Tests grün; die neuen Wächter gegen ihre Fehlerform gegengeprüft.

## Bewusst nicht

Massenänderungen als eigener Mechanismus, Schwärzen der Bedeutungs-Zahlen, gemeinsame Gespräche,
bedingte Erinnerungen, die KI beginnt kein Gespräch, MCP (später).
