# Rundenbericht 24.10.2026 – Zeiterfassung

## Was

Die Zeiterfassung nach `docs/zeiterfassung-spezifikation.md` (nachgeführt mit allen Entscheiden
aus 15 Mockup-Runden) – Backend, Frontend, Tests, Doku.

- **Backend**: Migration `154` (`time_contracts`, `time_entries`, `holidays`,
  `company_settings.time_rules`, append-only-Trigger); `domain/timekeeping` (Absenzarten,
  Regeln CH, Hinweise, Reglement-Texte); `services/timekeeping` (Konto, Ferien, Hinweise,
  Aufgaben, die eine Schreibstelle `record`, Wisch, Vorschau, Vertrag), `time_view`,
  `holidays` (inkl. Vorschlag OpenHolidays), `todo`; Router `routers/timekeeping`.
- **Pflichtangaben im Backend**: `people.required_fields`/`missing_fields`, ausgeliefert am
  Profil (`required_fields`, `missing_fields`). Das Konto rechnet den Fortschritt daraus statt
  aus einer eigenen Liste (`hooks/useProfileCompletion`).
- **«Zu tun»**: `GET /erp/todo` ersetzt `GET /erp/messages/open` – eine Zahl am Symbol für
  Nachrichten, Zeiterfassung, Pflichtangaben und Feiertage (`lib/todo`, `RecordIcon.todo`).
- **Frontend**: `components/erp/time/*`, Abschnitt im Personendatensatz, Karte an der eigenen
  Gesellschaft; `StageAction` nach `module-ui` (geteilt mit dem Beleg); `Card` mit `info`,
  `extra`, `unclipped`, `anchor`; `SectionSep`, `TodoChip`; Datumshilfen in `lib/when`.
- **Weg**: «Eintrittsdatum» und «Pensum» am Profil (ERP und Konto) – Mapping entfernt, Spalten
  fallen im Folge-Deploy (`docs/backlog.md`, `PENDING_DROP`).

## Warum so

- **Eine Tabelle für Einträge, Änderung = Ersatz** (`replaces_id`, Unique-Index): kein Löschen,
  das Korrekturprotokoll ist die Kette selbst; ein Trigger verbietet UPDATE/DELETE auch von Hand.
- **Keine Summe gespeichert**: Konto, Ferien, Hinweise und Aufgaben werden je Anfrage Tag für Tag
  gerechnet (einige Jahre × 365 Tage – Millisekunden). Keine zweite Wahrheit, die veraltet.
- **Robust gegen Netz und Doppelklick**: Idempotenz-Schlüssel je Wisch (der Client wiederholt
  einen POST ohne Antwort mit demselben Schlüssel), 60-s-Sperre, Sperre je Person
  (`FOR UPDATE`), Serverzeit.
- **14 h Laufzeit eines Kommens** (ArG Art. 10 Abs. 3): beantwortet ohne Sonderfall, wann ein
  vergessenes «Gehen» zum offenen Tag wird und dass der nächste Wisch wieder «Kommen» ist –
  und lässt Nachtschichten über Mitternacht zu.
- **Vorschau vom Server** statt Rechnen im Browser: dieselbe Regel sagt vor dem Speichern, ob
  es geht und was es bewirkt (Ersetzt, Ferien danach) – die Oberfläche kann nicht abweichen.
- **«Ferien danach»** = Guthaben heute minus alle geplanten Ferien, mit dieser Absenz (der
  erste Ansatz – «heute plus Rückgabe» – zählte eine noch nicht bezogene Ferienwoche als
  zurückgegeben; der Test hat es gefunden).
- **Abgeschlossene Tage blass statt Schloss** (Wunsch): antippen geht, der Tag sagt warum.

## Gemessen / geprüft

- Backend: `pytest tests/` 776 grün (neu: `test_timekeeping.py` 25 Prüfungen – Teilzeit Mo–Mi,
  Feiertag in Ferien, krank in den Ferien, Vertragswechsel mitten in der Absenz, Austritt mit
  Schlussstand, Jahreswechsel, Zeitumstellung, Mitternacht, unter 18, Sonntag, Idempotenz,
  7-Tage-Regel, append-only gegen die Bug-Form ohne Trigger, Vorschau, «zu tun»), `ruff`,
  Schema nur aus den Migrationen.
- Frontend: `type-check`, `lint`, `npm test`.
- Im Browser (lokal, echte Komponenten): Wischen (Maus), Doppelwisch innert 60 s ohne Wirkung,
  «Gehen» nachtragen, Krankheit in den Ferien mit Vorschau, Vertrag/Buchungen, Gesellschaft,
  Handy-Breite (390 px), Sichtbarkeit (Mitarbeiterin sieht die Zeit anderer nicht), Konto 80 %.

## Offen / verworfen

- **OpenHolidays** war aus der Testumgebung nicht erreichbar (Netz); der Vorschlag ist
  robust gebaut (Fehlersatz, Feiertage von Hand) – auf dev prüfen.
- Nachweise sind **Bilder** (Foto/Scan, `attachments.store_image`); PDF bewusst nicht.
- Verworfen: halbe Tage, Offline-Stempeln, Export, Team-Seite, Obergrenzen (Spezifikation §11).
