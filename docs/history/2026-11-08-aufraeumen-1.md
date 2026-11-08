# Aufräumen 1 (08.11.2026)

Auslöser: eine Durchsicht des ganzen ERP mit drei unabhängigen Prüfern (Backend-Architektur,
Frontend, Datenmodell) und eigenen Messungen. Ergebnis der Durchsicht: das Fundament trägt
(ein Log, Ableitungen statt Kopien, 38 Tabellen, keine verwaisten Spalten) – kein Neubau,
sondern Entrümpeln. Umgesetzt wurden Stufe 1 (Fehler), Stufe 2 (Altlasten) und ein Teil von
Stufe 3 (Code straffen).

## Stufe 1 – echte Fehler

- **Gelöschte Dokumente flossen weiter ins Gedächtnis der KI.** `services/memory` las
  `documents.is_active`, gelöscht wird aber über `deleted_at`. Jetzt bekommt ein gelöschtes
  Dokument keine Zahlen mehr, und schon vorhandene finden nichts mehr (`_where`).
  Test `test_memory.test_a_deleted_document_is_no_case_anymore`, gegen die Bug-Form geprüft.
- **Ein Pflichtfeld konnte zwei Dokumente tragen** (zwei gleichzeitige «In das Feld»).
  Eindeutiger Index `uq_document_refs_field` (Migration 175, ältere Doppel vorher abgelöst);
  `voucher.doc` sammelt ausdrücklich alle Papiere eines Moduls. Test
  `test_eine_ablage.test_a_mandatory_field_holds_exactly_one_document`, gegen die Bug-Form
  geprüft (ohne Index schlägt er an).
- **Falscher Satz am Artikel**: «lässt sich jederzeit wieder aktiv setzen» – das gibt es nicht
  («inaktiv» folgt aus `replaced_by_id`). Jetzt: Stücke laufen weiter und lassen sich ab Lager
  verwenden.
- Der KI-Abschnitt der CLAUDE.md war schon von der Assistent-Runde nachgezogen.

## Stufe 2 – Altlasten

- **Tote Spalten** (Zwei-Deploy-Regel: Migration 175 entmappt und macht sie optional, 176
  droppt): `is_active` an 23 Tabellen, an denen nie gelöscht wird (Mixin `SoftDeleteMixin`
  nur noch an den 9 Tabellen mit echtem Löschen; jede Abfrage `is_active = true` auf den
  übrigen war eine Prüfung, die nichts prüfte – auch die Sperre «deaktiviertes Konto», die
  nie eintreten konnte); `created_by` an `attachments`, `document_refs`, `document_links`,
  `holidays` und `captures.captured_by` (das Log hält fest, wer handelte);
  `articles.process_version` / `process_steps.source_version` (ein Artikel ändert sich nie);
  `orders.name` (immer «Auftrag <Nummer>», jetzt abgeleitet); `instances.label` (nie
  gesetzt); `vouchers.original_id` / `export_photo_id` (stehen im Pflichtfeld – die zweite
  Wahrheit daneben ist weg). Zwei eindeutige Indizes hingen an `is_active` und gelten jetzt
  ohne; acht doppelte Indizes fielen. `company_settings.iban_encrypted` heisst jetzt `iban`
  (verschlüsselt war nie etwas). **Bewusst geblieben**: Sprache und Benachrichtigungen der
  Person (Entscheid), die Lagerangaben am Artikel (E7), `newsletter_consents.created_by`
  (Nachweis).
- **Toter Code**: Exporte ohne Leser (8 entexportiert, `SectionTitle`, `PanelHeader`,
  `formatNumber` gelöscht), ungenutzte Parameter (`flow.build(steps)`, `mailbox.sync_all(force)`,
  `documents.file(stored)`, `attachments.store_*(actor_id)`, `instances.create_instances(label)`),
  Konstanten ohne Leser, die Abhängigkeit `esbuild`.
- **Kommentare: Regel statt Geschichte.** Rund ein Drittel des Codes war Text, darin rund 400
  Verweise auf Testnotizen. In 82 Dateien ist die Geschichte weg und die Regel geblieben –
  netto rund 4'550 Zeilen weniger. Abgesichert mit dem neuen Werkzeug
  `scripts/same-code.mjs` (TypeScript ohne Kommentare übersetzt, Python als Syntaxbaum ohne
  Docstrings – gleich vorher und nachher): 0 Dateien mit Code-Änderung. Dabei fielen vier
  Kommentare auf, die dem Code widersprachen, und zwei Doc-Kommentare, die an der falschen
  Funktion standen – berichtigt. Nicht angefasst: Docstrings der Routen und Schemas (sie sind
  die OpenAPI-Beschreibung und die Liste, aus der die KI ihre Handlungen kennt).

## Stufe 3 – Code straffen (Auswahl)

- **Laden = Skeleton, überall** (`components/erp/skeleton.tsx`: `Skeleton` mit `lines` ·
  `rows` · `block`, `DetailSkeleton`): Feed, Detailfenster (Auftrag, Instanz, Dokument),
  Verlauf, Protokoll, Bestand, Nummern, Zeiterfassung, Feiertage, Gebietskarte, Konto,
  Anmeldung. Kein «Lädt …» und kein Kreisel mehr beim ersten Laden.
- **Ein Baustein für Handlungen** (`lib/use-action.ts`: `useAction` → `run(fn, onError?)`,
  `busy`, `error`) und **eine Stelle für den Fehlertext** (`errorText`, vorher 44-mal von
  Hand). Der Auftrag nutzt ihn für Freigeben, Bestätigen, Beleg, Wiederholung beenden.
- **Auftragsbild: Nachbarn werden gezeichnet, nicht bedient** (`_steps(drawn=True)`): ein
  Nachbar kostete so viel wie ein ganzer Auftrag und zog dabei seine Belegpositionen nach.
  Gemessen (`test_order_view_queries`): 35 → 18 Abfragen je Nachbar mit drei Modulen, und es
  wächst nicht mehr mit der Zahl der Module. Dasselbe in der Vorschau des Entwurfs.
- **Eine Fristen-Regel** (`domain/voucher.assert_days`) statt zweier gleicher Prüfungen in
  Modul und Beleg; **eine Sperre über Commits** (`core/locks`) statt zweier fast gleicher
  Helfer in Takt und Aufnahmen (die strengere Fehlerbehandlung gilt jetzt für beide).

## Bewusst nicht gemacht (Stufe 4 und Rest von Stufe 3)

- **Stufe 4** – der Assistent ruft Routen intern auf, zwei Linkarten (Beleg ↔ Dokument), die
  Gutschrift auf zwei Arten: hohes Risiko (gesendete Links müssen weiter gehen, die
  Nummernserie ist rechtlich relevant), kein Nutzen heute. Erst, wenn dort ohnehin gearbeitet
  wird.
- **API-Aufrufe generieren** (`openapi-fetch` statt 1'200 Zeilen `lib/api.ts`), **grosse
  Dateien teilen**, **eine Fehlerart im Backend**: brauchen zuerst den Umbau der
  Quelltext-Tests (`test_source_*`), die Frontend-Text abgleichen und jedes Teilen blockieren.
  Eine eigene Runde.
- **Lesen, das schreibt** (`voucher.sync_lines` beim Anzeigen): für den eigenen Auftrag
  bleibt es (Absicht, dokumentiert); für Nachbarn fällt es jetzt weg.

## Gemessen

- Backend: 883 Tests grün (vorher 881; neu die zwei Fehler-Tests und die Abfrage-Messung),
  auf einem Schema frisch aus allen Migrationen bis 176; `ruff` sauber.
- Frontend: Typen, Lint, 79 Tests, Build grün.
- Deploy 1 (Migration 175) grün auf dev, danach Deploy 2 (176).
