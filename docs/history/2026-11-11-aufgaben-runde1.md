# Rundenbericht: Aufgaben, Runde 1 «Dran» (11.11.2026)

Projektakte: `docs/konzept/aufgaben.md` (Fassung 13). Branch `claude/aufgaben`.

## Was gebaut ist

- **Kompetenzen** (`domain/competences.py`): acht, eine Liste. Jedes Modul nennt seine Vorgabe
  (`Module.competence`); am Schritt tauschbar über `Module.clean_step` (die eine Stelle, durch die
  jeder Schritt geht: Freigabe, Artikel-Vorlage, Prüfung des Artikel-Entwurfs). Im JSON-Schema der
  Routen, die Schritte nehmen (`config_schemas` → `competence`), also auch für die KI.
- **Wer was kann**: `user_profiles.competences` (Migration 188), gesetzt über das bestehende PATCH
  der Person (`people.apply_profile_update` → `tasks.set_competences`); nur Personal, nur der Admin
  (Angaben von Mitarbeitenden, `person.staff`); die letzte Person einer Kompetenz kann sie nicht
  verlieren.
- **Wer woran ist**: `task_focus` (Migration 188), eine Zeile je Person, `task_key` eindeutig wo
  gesetzt. Das Log schreibt der Trigger; im Verlauf versteckt (`history.HIDDEN`).
- **`services/tasks.py`**: `collect` (alle Quellen), `dispatch` (Arztpraxis-Modell, unter
  `locks.TASKS`), `presence` (drei Sätze), `hand`, `view`, `set_competences`.
- **Zahlung**: `voucher_view.situation` sagt strukturiert `ours` – eine Quelle statt vier
  (Papiere, erwartete Dokumente, überfällige Rechnungen, Bezahlen/Erstatten).
- **Nachrichten**: `communication.open_threads` – dieselbe Regel wie Verlauf und Zeichen (`_state`).
- **Routen**: `GET /erp/tasks`, `POST /erp/tasks/{key}/hand`; `GET /erp/todo` und
  `services/todo.py` sind weg.
- **Takt**: Aufgabe `tasks` nach den Mails.
- **Oberfläche**: Zeile zuoberst im Feed (`FeedPanel.mine`), rotes Zeichen am Symbol (`RecordIcon`,
  «!» für verwaiste), an der Stelle (`TodoChip`, `TodoAt`, am Schritt `useTodoAt` über
  `TodoContext`), «Abgeben» beim Darüberfahren meiner Aufgabe; Feld «Kompetenzen» in der
  Personen-Karte (`components/erp/competences.tsx`); «Wer kann das?» im Prozess-Editor.

## Entscheide in der Umsetzung

- **Angaben eines Kunden** (fehlende Telefonnummer, Adresse) sind **keine** Aufgabe: jede
  unbekannte Absenderin einer Mail würde sonst eine. Sie fehlen dort, wo etwas sie braucht (die
  Zahlung sagt es). Eigene Pflichtangaben des Personals bleiben eine Aufgabe (nur die Person).
- **Zahlung vorgefiltert** in SQL (`_PAYMENT_CANDIDATES`): Offerte und Zusage immer; gestellt, wenn
  Geld offen scheint oder etwas in den letzten 120 Tagen geschah; storniert mit Geld. Entscheiden tut
  `situation`. Grenze: eine Rechnung, die seit über 120 Tagen ausgeglichen ist und erst danach einen
  fehlenden Ausfuhrnachweis bemerkt, fällt aus dem Vorfilter.
- **Hinweis KI-Deckel**: bleibt ein Zeichen für den Admin (am Betreiber), nie zugeteilt.
- **Dokument unterschreiben** (an mich gesendet) ist noch keine Quelle – es war auch kein «zu tun».

## Geprüft

- Backend: 863 Tests grün (vorher 856), neu `tests/test_tasks.py` (7 Wächter, je mit Bug-Form:
  Doppelvergabe per eindeutigem Schlüssel, frühestes Datum zuerst, ohne Kompetenz nichts, Abgeben
  nicht sofort zurück, verwaist sichtbar, Anwesenheit, letzte Kompetenz); `ruff` sauber.
- Frontend: `type-check`, `lint`, `npm test` (165), `build` grün. Ein Test der Aufnahme
  («Netz weg») schlug einmal zeitabhängig fehl und lief danach zweimal grün – unabhängig von dieser
  Runde.
- Generierte Dateien (`openapi.json`, `api.ts`, `vocab.ts`) neu erzeugt.
- **Nicht** im laufenden ERP angesehen (die Anmeldung braucht Firebase) – das ist der nächste
  Schritt auf inexxio-dev nach dem Merge.

## Offen

- Runde 2: ein Datum am Auftrag («bis» oder «ab»).
- Dokument zum Unterschreiben als Aufgabe (nur die Person).
