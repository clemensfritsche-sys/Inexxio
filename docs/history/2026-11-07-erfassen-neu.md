# Erfassen neu – das «+» als eine Eingabe, Testnotizen weg (07.11.2026)

## Auftrag (Clemens, nach dem Test von Phase 4)

- Das «+» soll aussehen und sich verhalten wie das Eingabefeld bei Claude: **eine Ansicht**,
  Aufnahme, Warten und Ergebnis passieren darin; kein Titel, kein X.
- Foto und Datei springen direkt in den Dokument-Entwurf («wie Hyperlinks»); «Neu anlegen» bleibt
  wie gehabt, auch «Dokument».
- Nach dem Stopp nur ein Skeleton, keine Schritte, kein «du kannst schliessen».
- In «Abgelegt» kein «Weiterer Teil», kein «Später», kein «Übernehmen»: **«Verwerfen» oder «Stimmt
  so»**; ein Vorschlag führt zum Feld.
- Das rätselhafte «Ablegen» im Angehefteten: was nicht abgelegt ist, gehört **an das «+»** (die
  Zahl dort), nicht an die Person.
- Die Testnotizen **ganz weg** – ohne Rückwärtskompatibilität. Rückmeldungen zur Software sind
  Teil der lernenden Firma: **Stecknadel** im «+», Notiz am Artikel «ERP» bzw. «Website».
- Das «+» auch auf der Website, für Mitarbeiter und Admin.
- Enter während der Aufnahme: bleibt, wie es ist.

## Was gebaut ist

- **Backend**: `intake.discard` (+ Route; ohne KI wird der `file`-Vorschlag roh angelegt und gleich
  verworfen, damit der Takt nicht nachholt; offene `change`/`create` aus der Erfassung gehen mit),
  `recordings.dismiss` (`recording.dismissed`), `context` an der Aufnahme (die Stecknadel steht
  vor dem Text), `intake.clean` (Steuerzeichen), «zu tun» ohne Erfassungen/Aufnahmen
  (`failed_count` entfernt), das Angeheftete ohne `file`. Migration **172** löscht
  `feedback_notes`; Modell, Schema, Dienst, Router, Test und Log-Zuordnung sind weg.
- **Frontend**: `capture-sheet` neu (Composer, Aufnahme im Feld `RecordingStrip`, Skeleton,
  `FiledBody`, «Nicht abgelegt» als Knöpfe), `lib/pin-point.ts` (zeigen, beschreiben; mit eigener
  Leiste «Auf die Stelle tippen · Abbrechen»), `lib/transcribe.ts` (eine Schleife je Aufnahme,
  läuft weiter, wenn das «+» zu ist, und meldet sich), Zahl am «+» (`useUnfiled`), `?neu=` in
  `useUrlParams`, Entwurf mit `start: 'scan'`, `/erp/erfassen` zum Einbetten. Die Marken
  `data-fb-*` heissen jetzt `data-where-*`. Weg: `components/feedback`, `lib/feedback.ts`,
  `src/islands`, `scripts/build-islands.mjs`, `sheet-head`, die Aufrufe in `lib/api.ts`.
- **Website**: `scripts/capture.ts` (das «+» für Personal, Rahmen mit `/erp/erfassen`, sichtbar
  erst bei `ready`, nach 12 s ohne Antwort ins ERP), CSP ohne Google-Dienste, `frame-src 'self'`;
  `scripts/feedback.ts` und `SITE_FEEDBACK` weg (auch im Deploy-Ablauf).
- Skill `feedback` und `docs/feedback.md` entfernt.

## Entscheide

- **Website: Rahmen statt Insel.** Eine Insel hätte das «+» samt Stilen, Portalen (Listen,
  Tooltips), Anmeldung und Abfragen nachbauen müssen – eine zweite Fassung. Der Rahmen zeigt
  dieselbe Seite; die Stecknadel greift über den gleichen Ursprung auf die Website zu. Was der
  Rahmen nicht kann (eine Datei ins ERP mitnehmen), springt ins ERP.
- **Daneben tippen lässt eine Erfassung offen** (nichts geht aus Versehen verloren); verworfen wird
  nur mit «Verwerfen».
- **Die Stecknadel findet den Artikel über die Suche** («ERP», «Website», genauer Name). Fehlt er,
  sagt das «+» es leise, und die KI legt ab, wo es passt.
- **Alte Log-Zeilen der Testnotizen bleiben** (das Log ist unveränderlich und versiegelt); sie
  hingen nur in der Testumgebung an Datensätzen.

## Geprüft

Backend 873 Tests, Frontend Typen/Lint/81 Tests, Website Tests/`astro check`/Build mit
`check-site`. Das «+» in Chromium angesehen (Schreibtisch und Handy): bereit, Stecknadel, Skeleton,
«Abgelegt», Aufnahme im Feld.
