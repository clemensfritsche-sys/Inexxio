# Runde zur Änderungsakte (09.11.2026)

Grundlage: die Gesamtprüfung (`2026-11-09-gesamtpruefung.md`) und die Entscheide des Inhabers
in `docs/aenderungsakte.md`. Umgesetzt wurden die Freigaben U1, U3–U10; U2 ist zurückgestellt.

## Was jetzt gilt

- **Rechte an einer Stelle** (`domain/policy.py`): eine Regeltabelle `RULES` (staff · admin ·
  self) mit dem Satz, warum nicht; `may` (Auskunft) ↔ `require` (Tor). Rund 70 verstreute
  Rollenprüfungen in 25 Dateien zeigen jetzt dorthin. Wächter `test_policy`: kein
  Rollenvergleich daneben (gegen die Bug-Form geprüft). Im Frontend `isStaff` · `isAdmin` an
  einer Stelle (ESLint), ob man darf, sagt der Server (`may_edit`).
- **Kundendaten ändert jedes Personal**; Rollen und Mitarbeitende nur der Admin.
- **Ein Fehlermodell** (`domain/errors.py`): `Invalid` · `Forbidden` · `NotFound` · `Conflict` ·
  `Gone` · …; 365 Fehlerstellen per Syntaxbaum umgestellt; EIN Übersetzer, überall
  `{detail, code, field?}` (auch für Pfade, die es nicht gibt, und Eingabefehler). Die
  Fachschicht kennt kein HTTP mehr. Wächter `test_errors` (gegen die Bug-Form geprüft).
  Englische Restmeldungen sind deutsch.
- **MCP gehärtet**: Rückkehr nur zu Claude (claude.ai, claude.com) oder auf den eigenen Rechner;
  die Erneuerung gilt genau einmal und nur für ihren Client (Migration 180; wird eine gebrauchte
  wieder vorgelegt, ist die Verbindung getrennt), 30 statt 90 Tage; jeder Zugang nennt sein ERP
  (dev gilt nicht in prod); die volle Rückkehr-Adresse steht auf «Claude verbinden».
- **Ein Zahlen-Leser** (`domain/number.py`): «1'234.50», «1’234.50», «1 234,50», «1.234,50».
- **Frontend liest über Queries**: Zeiterfassung, Feiertage, Modul-Katalog, Zielort, Protokoll,
  Überweisung, korrigierbare Rechnungen, Artikel-Vorbelegung, Konto (Passkeys, Newsletter,
  Claude). Das Konto hat dieselbe Query-Client-Bauart wie das ERP (Fehler melden sich jetzt
  auch dort). Wächter `scripts/queries.test.mjs` mit einer begründeten Ausnahmeliste
  (Handlungen, öffentliche Seiten, Anmeldung).
- **Ein Dialog-Verhalten** (`lib/use-dialog.ts`) für alle sechs Dialoge: Fokus hinein und
  zurück, Escape, Tab im Kreis. Wächter `scripts/dialog.test.mjs`.
- **Grosse Dateien geteilt**, ohne Verhaltensänderung (Werkzeug verschiebt ganze Definitionen,
  die Tests beweisen es): der Beleg in `voucher_rules` · `voucher_input` · `voucher_offer` ·
  `voucher_billing` · `voucher_actions` (1'339 → 290 Zeilen im Kern, ohne Kreisbezug – dafür
  steht «welche Stufen ein Verb braucht» jetzt als `NEEDS` bei den Regeln); die Auftragsansicht
  in `services/order_view.py` (Router 962 → 581); das Lesen einer Gmail-Nachricht in
  `mail_parse.py`.
- **CSP**: Google nur mit den genauen Adressen; der Deploy setzt den eigenen Dienst statt
  `*.a.run.app` ein (und prüft es).
- Ein Test, der im Gesamtlauf wackelte (`test_memory`), ist stabil.

## Bewusst nicht gemacht

- **U2 (KI-Kosten auch bei Abbruch zählen)**: ginge nur, wenn das unveränderliche Log
  ausserhalb der laufenden Antwort geschrieben wird – nicht einfach und elegant, Risiko klein.
- **CSP ohne `unsafe-inline`/`unsafe-eval`**: Next-Export, Google Maps und der Scanner brauchen
  sie möglicherweise; ohne Test im echten Browser nicht verantwortbar.
- **`mailbox.py` weiter teilen** (Senden für sich): Abgleich und Senden rufen einander – eine
  Teilung erzeugte einen Kreisbezug; geteilt wurde nur, was rein ist (`mail_parse`).

## Gemessen

- Backend 905 Tests grün (neu: `test_policy`, `test_errors`, `test_number`, MCP erweitert),
  `ruff` sauber, OpenAPI und Typen neu erzeugt.
- Frontend: Typen, Lint, 83 Tests, Build grün.
