# Cleanup-Analyse Backend – INEXXIO (develop @ fbd70fc)

Umfang: `backend/app` (domain · services · routers · models · schemas · core · main.py mit
allen Netzen), `backend/scripts`, `backend/alembic` (nur Netze/Backfills/Drops). Frontend/Website
nur gelesen, um Leser festzustellen. **Nichts geändert.**

Messwerkzeuge: `python -m scripts.deadcode --backend` (lief, 44 Hinweise), ein AST-Skript für
Funktionslängen, ein Skript «Antwortfeld ohne Leser im Frontend» (alle Response-Schemas gegen
`frontend/src` ohne `types/api.ts`), ein Skript «Endpunkt ↔ Aufrufer in `lib/api.ts`», dazu je
Fundstelle `grep -rnw` (Treffer ausser Definition gezählt). «Zu prüfen» heisst: nicht gemessen,
nur gelesen.

---

## Kurzfassung – die 10 wichtigsten Befunde

1. **Doppelversand von Mails möglich** (B-30/B-31): `mailbox.send_due` holt fällige Mails **ohne
   Zeilensperre** – zwei offene ERP-Tabs (jede Minute `POST /messages/sync`) senden dieselbe
   geplante Mail zweimal. Und `send()` liest nach dem erfolgreichen Versand die Metadaten
   **ungeschützt** (`_get` ohne `try`); ein Netzfehler dort rollt die ganze Sync-Transaktion
   zurück – `outgoing` bleibt `True` für **alle** in diesem Lauf schon gesendeten Mails → beim
   nächsten Lauf erneut versendet.
2. **Der Formwächter kann Kerndaten löschen** (B-33): `_ensure_rebuilt_tables_shape` macht bei
   «fremder Pflichtspalte» `DROP TABLE … CASCADE` auf `orders`, `process_events` (append-only
   Log!), `instance_units` u. a. – bei jedem Start. Der Anlass (Basis-Neuaufbau, Aug. 2026) ist
   vorbei; heute ist das ein Datenvernichter, der durch eine einzige unvorsichtige Migration
   auslösbar ist.
3. **Plausible lädt im Frontend nie** (B-35): `GET /admin/settings/public` liefert kein
   `plausible_domain`; `components/analytics/plausible.tsx` liest genau dieses Feld → stiller
   Ausfall. Dazu trägt der Endpunkt ein **erfundenes** Fallback («Inexxio AG», info@inexxio.com)
   und Felder (Anschrift, UID …), die kein Aufrufer mehr liest (Impressum lebt in `website/`).
4. **Optimistic Locking ist tot** (B-36): `ensure_version` wird nur am Artikel gerufen, und das
   Frontend sendet `expected_updated_at` **nirgends** → prüft nie. CLAUDE.md führt es unter
   «Sicherheit – gebaut».
5. **`articles.status` wird bei jedem Start beschrieben, obwohl ungemappt** (B-20):
   `_ARTICLE_STATUS_FIXES` schreibt eine Spalte, die seit #773/Migration 121 niemand liest; der
   Drop steht in **keinem** Backlog-Eintrag (nur im `_NULLABLE_SAFETY_NET`-Kommentar).
6. **Tote Netz-Einträge für entfernte Bereiche** (B-21/B-22): Index-Reparatur
   `uq_purchases_step` auf der Tabelle eines gelöschten Moduls; `_DROP_COLUMN_SAFETY_NET` mit 19
   Spalten, die Migration 120 längst gedroppt hat; `people.move_company_texts`/`MOVED_COLUMNS`,
   `info_/personal_/contact_/topic_repair_sql`, `invoice_backfill_sql`, `magnitude_sql` – alle
   selbstbegrenzend und laufen bei jedem Start (zu prüfen: ob jede Umgebung sie gesehen hat).
7. **Tote Endpunkte/Funktionen** (B-01…B-10): `POST /auth/terms-accept`, `GET /admin/audit-log`,
   `GET /admin/users` (Client-Methode `getUsers` ohne Aufrufer), `core/auth.get_optional_user`
   (Shop-Rest), `routers/contact._summary`, `places.counts_at` (nur Test),
   `domain/voucher.BINDING/QUOTE_STATES/TASK_HINT/term_name/WITHDRAWN_NOTE`,
   `articles.landed_unit_cost` (kein Schreiber seit «Beschaffen» weg).
8. **`STAFF_ROLES` viermal definiert** (B-40): `people.STAFF_ROLES`, `voucher.STAFF_ROLES`,
   `feedback.STAFF_ROLES`, `core/auth.require_employee = require_role("admin","employee")`, dazu
   ein Literal in `sites._assert_may_leave`. Personensuche zweimal (`voucher.search_parties` ↔
   `places.search`, mit verschiedenen Suchspalten), Firmenanschrift zweimal
   (`voucher._creditor` ↔ `address.of_company`), UID einmal formatiert, einmal roh (B-42).
9. **`open_counts` lädt den ganzen Nachrichtenbestand** (B-50): für das Feed-Zeichen wird jede
   aktive Nachricht (inkl. `body`/`html`) über `load()` voll gebaut, und `answered` lädt alle
   Staff-Nachrichten seit der ältesten – O(Bestand) bei jedem Feed-Aufruf. Heute klein, wächst
   aber linear mit jeder Mail.
10. **Prosa widerspricht Code** (B-60…B-70): `backend/CLAUDE.md` führt die gelöschten
    `…/deal*`-Endpunkte, `deal-parties` und `PATCH /auth/me/company` als «tatsächlich vorhanden»;
    `docs/attic.md` beschreibt `domain/deal` als lebend; `domain/voucher.py`-Modul-Docstring
    spricht von «Chronik», «Rückläufe» und einer «befristeten Doppelung mit `domain/deal.py`»;
    vier Verweise auf ein `Module.buys`, das es nicht gibt; CLAUDE.md sagt «der Deploy fährt kein
    `alembic upgrade head`», `start.sh` tut genau das (zu prüfen, ob es auf dev scheitert).

---

## Befundtabelle

Legende Vorschlag: E = entfernen · U = umbenennen · V = vereinfachen · H = härten · B = bleibt.
«DB» = Verhaltens- oder DB-Änderung.

### Achse 1 – Tot

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | DB | wie geprüft |
|---|---|---|---|---|---|---|---|
| B-01 | Tot | routers/auth.py:74 | `POST /auth/terms-accept` hat keinen Aufrufer (Frontend, Website, Tests). Die AGB-Akzeptanz (CLAUDE.md DSG-Abschnitt) ist damit nicht verdrahtet; `terms_version="1.0"` hart. | zu prüfen: verdrahten (Fachfrage) **oder** entfernen | niedrig | nein | `grep -rn "terms-accept\|terms_accept" frontend/src website/src backend/tests` = 0 |
| B-02 | Tot | routers/admin.py:315 | `GET /admin/audit-log` ohne Aufrufer. | B (Admin-Werkzeug) oder E; Entscheidung | niedrig | nein | `grep -rn "audit-log" frontend/src` = 0 |
| B-03 | Tot | routers/admin.py:288 | `GET /admin/users`: einzige Client-Methode `getUsers()` (api.ts:343) hat **keinen** Aufrufer. Lädt zudem alle Benutzer ungepagt. | E (Endpunkt + Client-Methode) | niedrig | nein | `grep -rn "\.getUsers(" frontend/src` = 0 |
| B-04 | Tot | core/auth.py:190 | `get_optional_user` – Docstring «z. B. der Shop»; kein `Depends` darauf. | E | niedrig | nein | `grep -rn get_optional_user backend` = nur Definition |
| B-05 | Tot | routers/contact.py:206 | `_summary()` ohne Aufrufer (Rest aus der Mailversand-Fassung). | E | niedrig | nein | Skript «private Fkt. mit 1 Treffer» + grep |
| B-06 | Tot | services/places.py:596 | `counts_at` nur in `tests/test_move_module.py:161`. | E (Test auf `at_holder` o. Ä. umstellen) | niedrig | nein | grep = Definition + 1 Test |
| B-07 | Tot | domain/voucher.py:95, 110, 382, 461, 553 | `BINDING`, `QUOTE_STATES`, `TASK_HINT`, `term_name`, `WITHDRAWN_NOTE` – null Leser. `WITHDRAWN_NOTE` beschreibt zudem eine «zurückgenommene Zeile», die es seit Migration 138 nicht mehr gibt. | E | niedrig | nein | deadcode + `grep -rnw` (je 1 Treffer); `QUOTE_STATES` nur in einem Kommentar in `frontend/src/lib/modules.ts:203`, der auf `domain/deal` zeigt |
| B-08 | Tot | models/article.py:96, schemas/article.py:354, main.py:76 | `landed_unit_cost`: Schreiber war `services/purchase` (gelöscht); heute nur Mapping + Response-Feld + Netz, Frontend liest es nicht. | E (Mapping, Schema-Feld, Netz-Eintrag); Drop im Folge-Deploy **nach DB-Sicherung** | niedrig | ja (Drop) | `grep -rn landed` app/tests = Modell, Schema, Netz; Frontend nur `types/api.ts` |
| B-09 | Tot | models/user.py:94-96, schemas/admin.py | `language` (nur geschrieben in `core/auth._create_user`), `notification_email`, `notification_inapp` – kein Leser im Backend, keiner im Frontend. | zu prüfen (vorgemerkte Funktion?) → sonst E aus Schema, Drop später | niedrig | ja (Drop) | Spalten-Skript + `grep -rln notification_email frontend/src` = 0 |
| B-10 | Tot | schemas/voucher.py (VoucherEmbed) | Antwortfelder ohne Leser im Frontend: `incoterm_place_hint`, `agreed_on`, `late`, `charged`, `uncharged`; `VoucherQuoteOut.sent_on`; weiter `ArticleValidation.saveable`, `OrderValidation.saveable`, `OrderResponse.waiting_for_return`, `ProcessStepResponse.source_article_id/source_version`. | zu prüfen je Feld (einige lesen Tests) → E, wo auch kein Test es braucht | niedrig | nein | Skript «Response-Feld ∉ frontend/src (ohne types/api.ts)» |
| B-11 | Tot | domain/modules.py:65 | `Module.units_may_leave` ist bei **jedem** Modul `True`; `process._assert_may_leave` kehrt damit immer sofort zurück. Docstring begründet es mit «künftigem Einkauf/Verkauf» – gelöscht. | V/zu prüfen: entfernen oder als bewusster Haken (R7) mit aktuellem Docstring | niedrig | nein | `grep -rn units_may_leave` = Definition + 1 Leser, kein Override |
| B-12 | Tot | services/stripe_pay.py:95 | `MONEY` ist eine Registry mit genau einem Eintrag (`voucher`) plus `key_of`, `svc: Any`-Parameter – Indirektion für einen Fall, der seit #960 nicht mehr existiert. | V (direkt `voucher_svc`), **Metadaten-Schlüssel `voucher_id` beibehalten** | niedrig | nein | Lesen; deadcode «nur modulintern» |
| B-13 | Tot | domain/modules.py:435 | `Move` ist eine Dataclass mit einem Feld `target`; einziger Leser `places.py:535`. | V (int zurückgeben) | niedrig | nein | grep `Move(`/`.target` |
| B-14 | Tot | routers/website.py:76 | `if line.strip("— ")` filtert, was `address.lines` schon herausnimmt (`DASH`). | V | niedrig | nein | Lesen `services/address.py:101-121` |
| B-15 | Tot | routers/health.py:14 | `"version": "1.0.0"` hart, daneben `settings.app_version`. | V | niedrig | nein | Lesen |

### Achse 2 – Reste entfernter Bereiche (Netze, Backfills, Daten)

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | DB | wie geprüft |
|---|---|---|---|---|---|---|---|
| B-20 | Rest | main.py:434-440, 537-545 | `_ARTICLE_STATUS_FIXES` schreibt bei jedem Start `articles.status` (ungemappt seit 121) – mit einer Sonderbedingung `… or table != "articles"`, weil die dritte Anweisung `orders.name` betrifft. Drop von `articles.status` steht in keinem Backlog-Eintrag. | Paket A: die zwei `articles`-Zeilen entfernen, `orders.name`-Fix eigenständig; Backlog-Eintrag für den Drop (**DB-Sicherung**) | niedrig | ja | `grep -n "articles.status" docs/backlog.md` = 0; `models/article.py:41` |
| B-21 | Rest | main.py:384-413 | `_RAW_INDEX_SAFETY_NET`: `uq_purchases_step`-Reparatur für die Tabelle des gelöschten Beschaffen-Moduls. | E (Lehre im Kommentar an anderer Stelle belassen) | niedrig | nein | `models/` kennt `purchases` nicht (`grep -rn "purchases" app/models` = 0) |
| B-22 | Rest | main.py:250-305 | `_DROP_COLUMN_SAFETY_NET`: 19 Einträge (Block «Migration 120») + 9 ältere – alle längst gedroppt; laufen als `DROP COLUMN IF EXISTS` jeden Start (ACCESS-EXCLUSIVE-Lock je Tabelle). | zu prüfen (alle Umgebungen auf ≥120?) → E der Einträge, Netz als leere Struktur behalten | niedrig | nein | Migration `120_*` + backlog «Erledigt: … gedroppt (Migration 120)» |
| B-23 | Rest | main.py:497-501, services/people.py:283-330 | `move_company_texts` + `MOVED_COLUMNS` (CRM Schritt 1) – selbstbegrenzend, fragt `information_schema` jeden Start. | zu prüfen → E (Migration 142 behält ihre Kopie) | niedrig | nein | Lesen; Spalten in Modell nicht mehr vorhanden |
| B-24 | Rest | domain/communication.py:101-172, main.py:645-660 | `info_repair_sql` (146), `personal_repair_sql` (149), `contact_repair_sql` (147), `topic_repair_sql` (148, liest `message_replies`). Alle selbstbegrenzend, laufen jeden Start; die SQL-Teilabfrage «Betreiber-Kanal» steht zweimal wörtlich (Z. 105 und 115). | Paket C: `topic_repair_sql` mit Drop von `message_replies` (Backlog) entfernen; die anderen nach Prüfung; Teilabfrage einmal | niedrig | ja (Drop `message_replies`, **DB-Sicherung**) | Lesen + backlog «message_replies droppen» |
| B-25 | Rest | domain/voucher.py:1074-1145, main.py:575-604 | `invoice_backfill_sql` (138) und `magnitude_sql` (141) – selbstbegrenzend; hängen an `voucher_entries.kind`. | mit Drop von `kind`/`due_on`/`vat`/`service_date`/`reverses_id`/`charge_id`/`reason` + Tabelle `voucher_allocations` entfernen (Backlog «Folge-Deploy Geld-Zeile») | mittel | ja (**DB-Sicherung**) | backlog + Lesen |
| B-26 | Rest | services/address_book.py:234-300, main.py:622-633 | `migrate_sql`/`business_sql`/`OLD_COLUMNS` (143) und `ADDRESS_INDEXES` (DROP+CREATE INDEX jeden Start). | mit Drop der Benutzer-Anschriftsspalten entfernen; `ADDRESS_INDEXES` nur `CREATE IF NOT EXISTS` behalten | niedrig | ja (**DB-Sicherung**) | backlog «Anschriften am Benutzer droppen» |
| B-27 | Rest | main.py:223-248 | `_NULLABLE_SAFETY_NET`: 4 Einträge, deren Drop seit 1–4 Deploys aussteht (`articles.status`, `voucher_entries.kind`, `user_profiles.invoice_same_as_shipping`, `.country`). | Paket F (Drops) – Einträge gehen mit | mittel | ja (**DB-Sicherung**) | Lesen + backlog |
| B-28 | Rest | backlog (Sammlung) | Ausstehende Spalten-Drops: `vouchers.issued_on`; Benutzer: 4× `bank_*`, 6 Anschrift, 7 `invoice_*`, `invoice_email`, 12 aus #1042/#1043; `articles.status` (B-20), `articles.landed_unit_cost` (B-08); `voucher_entries` 7 Spalten. Tabellen: `message_replies`, `voucher_allocations`, `purchases`, `invoices`, `payments`, `deals`, `deal_entries`, `events`, `document_*`, `article_prices`, `article_sales_audience`, `fx_rates`, `ai_actions`. | Paket F (Spalten) und G (Tabellen) – **immer erst Sicherung der produktiven DB** (`scripts/dump-db.sh`), lesbar prüfen, dann droppen | hoch (Daten) | ja | docs/backlog.md |
| B-29 | Rest | Kommentare/Namen | «Lieferant» als Rollenwort in `routers/orders.py:155,214,737`, `people.py:116` (`supplier_id, customer_id` – gibt es nicht), `models/attachment.py:15` («Verkauf/Shop»), `core/database.py:28` (`reservation`, `selling._resolve_line`), `models/admin.py:16` (`instances.location_type`). | E/U (Kommentare auf «Gegenpartei»/heutige Namen) | niedrig | nein | grep-Liste Achse 2 |

### Achse 6 – Robustheit

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | DB | wie geprüft |
|---|---|---|---|---|---|---|---|
| B-30 | Robust | services/mailbox.py:596-601 | `send_due` ohne `with_for_update(skip_locked=True)`; die Sperre in `sync_all` gilt nur den Postfach-Zeilen. Zwei gleichzeitige `POST /messages/sync` (ein Tab je Mitarbeiter, 60 s) → dieselbe geplante/gescheiterte Mail zweimal gesendet. | H: Zeilensperre `SKIP LOCKED` in `send_due` | mittel | ja (Verhalten) | Lesen; Poll in `app/(erp)/erp/page.tsx:230-241` |
| B-31 | Robust | services/mailbox.py:604-638, 325-342 | Nach erfolgreichem `messages/send` folgt `_get(... metadata)` **ohne** `try`; `sync_all` committet erst am Ende. Ein `httpx.HTTPError` (oder `r.json()`-Fehler) dort rollt alles zurück → `outgoing=True` für jede in diesem Lauf bereits versendete Mail → Wiederholversand. Auch `_new_ids` 404-Zweig ruft `.json()` ungeprüft. | H: Ergebnis des Versands sofort festschreiben (commit/savepoint je Mail), Metadaten-Abruf in `try`; Fehlerstatus loggen | **hoch** | ja | Lesen |
| B-32 | Robust | services/mailbox.py:626-627 | `send()` gibt bei `status != 200` still `False` zurück, ohne Status zu loggen (anders als `_mark_read`). Ein dauerhaft abgelehnter Versand wird jede Minute neu versucht, unsichtbar. | H: loggen; nach n Fehlversuchen `problem` setzen | niedrig | ja | Lesen |
| B-33 | Robust | main.py:807-858 | `_ensure_rebuilt_tables_shape` droppt bei «fremder Pflichtspalte»/«fehlender Spalte» `orders`, `order_units`, `process_events`, `instance_units`, `instances`, `captures`, `attachments` … mit `CASCADE`. Eine Migration, die eine `NOT NULL`-Spalte hinzufügt, bevor das Modell sie kennt (oder ein ungemapptes `NOT NULL` ohne Netz-Eintrag), vernichtet den Prozess-Log. | H: DROP-Zweig entfernen → nur melden (WARNING), Neuaufbau nur für leere Tabellen | **hoch** | ja | Lesen; Docstring selbst nennt den Anlass «Basis-Neuaufbau» |
| B-34 | Robust | main.py:452-673 | `_ensure_columns` ist **ein** `try`; nach dem ersten Commit laufen ~10 unabhängige Daten-Reparaturen hintereinander – scheitert eine, entfallen alle folgenden still (nur `print`). Ebenso `_COMPANY_DATA_FIXES` setzt bei jedem Start `ALTER … SET DEFAULT false` (Lock). | H: je Reparatur eigener `try`/Savepoint + `logging.warning`; DDL nur bei Bedarf | mittel | ja | Lesen |
| B-35 | Robust | routers/admin.py:92-120 | `/admin/settings/public` liefert kein `plausible_domain` → `plausible.tsx:27` bekommt nie eine Domain (stiller Ausfall). Fallback erfindet «Inexxio AG»/info@inexxio.com. Übrige Felder (Anschrift, UID, MWST …) hat kein Leser mehr (nur `plausible.tsx`, `use-maps-key.ts`). | H/V: Endpunkt auf `{plausible_domain, google_maps_api_key}` reduzieren, kein erfundener Fallback | niedrig | ja (Plausible lädt dann) | `grep -rn getPublicSettings frontend/src` = 2 Aufrufer; Lesen der Antwort |
| B-36 | Robust | services/lifecycle.py, routers/articles.py:187 | `ensure_version` prüft nur, wenn `expected_updated_at` kommt; Frontend sendet es nie. Docstring behauptet zudem, kein Endpunkt ändere die Spezifikation eines angelegten Artikels – `PATCH /articles/{id}` tut genau das. | H (Frontend sendet Stand) **oder** E + CLAUDE.md korrigieren | niedrig | ja | `grep -rn expected_updated_at frontend/src` (ohne types) = 0 |
| B-37 | Robust | services/voucher.py:392-435, routers/orders.py:126-150 | `sync_lines` legt Zeilen auf einem **GET** an und `_keep` committet. Zwei gleichzeitige GETs desselben Auftrags (neue Position) → der zweite läuft in `uq_voucher_lines_article` → `IntegrityError` im Lesepfad (globaler Handler → 409/500 auf einem GET). | H: Insert mit `ON CONFLICT DO NOTHING` bzw. Savepoint + Retry | niedrig | ja | Lesen; kein `IntegrityError`-Fang in `sync_lines` |
| B-38 | Robust | routers/orders.py:78-127 | `_steps` je Schritt: `step_work`, `consumption.needs` (+ `places.describe` je Bedarf **und** je Quelle), `_place_ref`, `embed_data` (297 Zeilen, viele Abfragen), `completion_problem` → N+1 über Schritte × Bedarfe. | zu prüfen: Abfragen je Auftragsantwort zählen (wie bei Bestand/Halter-Kette) | mittel | nein | Lesen |
| B-39 | Robust | main.py:29-60, core/auth.py:41-56,131 | Admin-Bootstrap zweimal (Start + Login): «kein Admin vorhanden → erster/jeder neue Benutzer wird Admin». Auf einer leeren/zurückgesetzten DB wird der erste Login Admin. `_bootstrap_admin` vergleicht `email ==` case-sensitiv, obwohl E-Mails inzwischen klein gespeichert werden. | H: nur `initial_admin_email` promoten (lower), Rückfall «erster Benutzer» streichen oder nur bei `app_env != production` | mittel | ja | Lesen |
| B-50 | Robust (N+1/Last) | services/communication.py:368-387, 252-307 | `open_counts`: alle aktiven Nachrichten (inkl. `body`, `html`) über `load()` → volle `MessageOut`; `answered` lädt alle Staff-Nachrichten seit der ältesten Kandidatin. Linear im Gesamtbestand, bei jedem Feed-Aufruf. `_mark_read` ruft `answered` je Postfach jede 30 s über 30 Tage. | V/H: Kandidaten vorfiltern (nur `to_us`, noch nicht beantwortet), `load_only`/kein `html`; Messen | mittel | nein | Lesen |
| B-51 | Robust | services/communication.py:164-166 | `_assert_mail` (E-Mail braucht «An») greift nur bei `body` – eine Mail mit leerem Text und leerem «An» wird angelegt (CLAUDE.md: «400 im Dienst»). | zu prüfen | niedrig | ja | Lesen |
| B-52 | Robust | models/voucher.py:233 / main.py:150 | `vouchers.corrects_id` kam über das Spalten-Netz als blankes `BIGINT` – Index `ix_vouchers_corrects_id` und FK (Migration 138) erreichen eine Datenbank ohne Alembic nie (`create_all` legt Indizes nur für neue Tabellen an). Gleiches Muster wie #778. | zu prüfen (Index/FK auf dev vorhanden?) → Eintrag in `_RAW_INDEX_SAFETY_NET` | niedrig | ja | Migration 138:116 vs. Netz |

### Achse 3 – Doppelungen

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | DB | wie geprüft |
|---|---|---|---|---|---|---|---|
| B-40 | Doppelt | services/people.py:34, services/voucher.py:53, services/feedback.py:27, services/sites.py:831, core/auth.py:220 | Staff-Rollen fünfmal (3× Konstante, 1× Literal, 1× `require_role(...)`). `people.STAFF_ROLES` nennt sich «die EINE Frage». | V: überall `people.STAFF_ROLES` (auth: `require_role(*STAFF_ROLES)`) | niedrig | nein | `grep -rn 'STAFF_ROLES\s*=\|("admin", "employee")'` |
| B-41 | Doppelt | services/voucher.py:2171, services/places.py:225-238 | Personensuche zweimal: `voucher.search_parties` (Firma, Vorname, Nachname, E-Mail) und `places.search` (ohne Firma). Wer «Muster» tippt, findet in einem Feld Personen der Muster AG, im anderen nicht. | V: `people.search(db, q, staff=…, limit=…)`, beide lesen sie | niedrig | ja (Suchergebnis) | Lesen |
| B-42 | Doppelt | services/voucher.py:1894 vs. 1923 | Partner-Seite: `uid_fmt.display(vat or uid)`; unsere Seite: roh `vat or uid` – dieselbe Angabe auf demselben Beleg verschieden formatiert. | V: eine Funktion `_uid(company)` | niedrig | ja (Anzeige) | Lesen |
| B-43 | Doppelt | services/voucher.py:1930-1940 vs. services/address.py:82 | `_creditor` baut die Firmenanschrift Feld für Feld nach, die `address.of_company` schon kennt (mit 7× defensivem `getattr`). | V | niedrig | nein | Lesen |
| B-44 | Doppelt | services/address.py:87, services/sites.py:183-184, routers/admin.py:102-105 | Drei erfundene Firmen-Defaults («Inexxio», «Inexxio AG», info@inexxio.com) – widerspricht «was fehlt, wird gesagt statt erfunden». | zu prüfen: `operator()`-Anlage braucht einen Namen; die beiden anderen entfernen | niedrig | ja | grep "Inexxio" app |
| B-45 | Doppelt | services/feedback.py:27, people.py | siehe B-40 (eigene `_is_staff`). | V | niedrig | nein | Lesen |
| B-46 | Doppelt | routers/contact.py:200 vs. services/inquiry.py:66 | Zwei Betreff-Regeln für die Anfrage: `_subject` («[Anfrage] Firma», nur im mailto-Fallback) und `subject_of` («Anfrage: erster Satz»). | zu prüfen: Fallback auf `inquiry.subject_of` | niedrig | ja (mailto) | Lesen |

### Achse 4 – Benennung

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | DB | wie geprüft |
|---|---|---|---|---|---|---|---|
| B-47 | Name | models/admin.py:124 (+7 Leser) | `iban_encrypted` – es wird nichts verschlüsselt. | U ohne Migration: `iban: Mapped[...] = mapped_column("iban_encrypted", Text)`; `getattr(..., "iban_encrypted")` (voucher.py:652, 2132) wird `company.iban` | niedrig | nein | `grep -rn iban_encrypted app` = 7 |
| B-48 | Name | routers/orders.py:450, services/voucher.py:2171 | `GET /erp/orders/voucher-parties` (+ `searchVoucherParties`) ist die allgemeine Personensuche – auch für Mitarbeiter-Empfänger in der Kommunikation (`staff=true`, communication.tsx:443). Liegt im Auftrags-Router. | U: `GET /erp/people?search=&staff=` in `routers/erp.py`, Dienst `people.search` (mit B-41); Frontend-Methode umbenennen | niedrig | nein (API-Pfad ja) | grep Aufrufer: communication.tsx, process-designer.tsx, beleg-work.tsx |
| B-49 | Name | routers/payments.py:4, core/config.py:99, domain/__init__.py:12 | Docstrings nennen `services/payments.record`, `services/deal.can`, `procurement` als heutige Bauteile. | E/U (Text) | niedrig | nein | grep Achse 2 |

### Achse 5 – Vereinfachung

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | DB | wie geprüft |
|---|---|---|---|---|---|---|---|
| B-53 | Länge | siehe Liste unten | 6 Funktionen > 80 Zeilen (Regel CLAUDE.md «max. 80»). | V schrittweise, nur mit Wächtern | mittel | nein | AST-Skript |
| B-54 | Kommentare | ganze App | 113 «Hier stand …»/«mitgegangen»/«ersatzlos entfallen»/«Vorgänger»-Grabsteine in Code-Kommentaren (voucher.py 23, domain/voucher.py 15, models/voucher.py 9, articles.py 8, main.py 8 …). Sie beschreiben Vergangenes am Ort des Heutigen; die Historie liegt ohnehin in `docs/history`, CLAUDE.md und Git. | V: Grabsteine entfernen, wo kein Wächter/keine Regel davon abhängt (Tests lesen teils Kommentare – `_code()`-Wächter prüfen) | niedrig | nein | `grep -rcE "Hier stand|mitgegangen|ersatzlos entfallen|Vorgänger"` |
| B-55 | Defensiv | services/voucher.py (15× `getattr`) | `getattr(company, "street", None)` usw. auf einem typisierten Modell – verdeckt Tippfehler. | V | niedrig | nein | `grep -c getattr services/voucher.py` |

### Achse 7 – Docstrings/Prosa, die Vergangenes als aktuell beschreiben

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | DB | wie geprüft |
|---|---|---|---|---|---|---|---|
| B-60 | Prosa | domain/voucher.py:1-45 | Modul-Docstring: «kein Import aus `domain/deal`», «wird das alte Zahlungsmodul gelöscht», Ordnung «… Rückläufe → … → Chronik», «befristete Doppelung … `domain/deal.py` … ein Wächter vergleicht». Alles seit #960/#946/#970 vorbei. | U (Docstring auf heutigen Stand) | niedrig | nein | Lesen |
| B-61 | Prosa | services/voucher.py:1-25, schemas/voucher.py:3-10, models/voucher.py:24, 304, services/voucher.py:1068 | «Neuaufbau … wie sein Vorgänger `services/deal`»; «die Chronik fragt danach». | U | niedrig | nein | grep «Chronik» |
| B-62 | Prosa | domain/modules.py:113, 169, 439; schemas/process.py:288 | Vier Verweise auf `Module.buys` – existiert nicht (Beschaffen gelöscht). | U | niedrig | nein | `grep -rn buys app` = nur diese 4 Kommentare |
| B-63 | Prosa | domain/modules.py:55-64, 540 | `units_may_leave`-Begründung «künftiger Einkauf/Verkauf»; Beleg-Docstring verweist auf `domain/deal`. | U | niedrig | nein | Lesen |
| B-64 | Prosa | main.py:321-323, 638, 866-870, 766 | «GIN auf der Reservierungs-Map», «wie beim `documents`-Block oben» (gibt es nicht), Startup-Docstring «Prozess-Backfill, Pflicht-Bewegungen, Wiederkehr», «Das Unternehmen (Singleton)». | U | niedrig | nein | Lesen |
| B-65 | Prosa | models/article.py:94-95, schemas/article.py:130/222/346 | «aus dem Beschaffungs-Beleg zurückgeschrieben (`services/purchase`)», «Gefahrgut (reist mit dem Beschaffungs-Beleg)». | U | niedrig | nein | grep |
| B-66 | Prosa | services/people.py:5-7, 116 | Liste alter Funktionen (`sales._user_name`, `resource._user_name` …), FK-Beispiele `supplier_id`, `customer_id`, `inspector_id`. | U | niedrig | nein | Lesen |
| B-67 | Prosa | backend/CLAUDE.md, Tabelle «API-Endpunkte (tatsächlich vorhanden)» | Führt `GET /orders/deal-parties`, `POST …/deal`, `…/deal/payment`, `…/deal/refund`, `…/deal/transfer` (alle gelöscht), `PATCH /auth/me/company` (existiert nicht), «Lieferant: nur eigene»; nennt `name-suggestions` und `/stock` doppelt; fehlt: `/voucher*`, `/voucher-parties`, `/correctable`. Grosse Abschnitte zu `domain/deal` lesen sich als aktuell. | U (Tabelle aus Routern neu; deal-Prosa nach `docs/history`) | niedrig | nein | Routen-Liste (85 Endpunkte) vs. Tabelle |
| B-68 | Prosa | docs/attic.md:24-55 | «Genau das ist der Geldvorgang (`domain/deal`)», «Die Anbindung hängt jetzt am Geldvorgang (`deal.record_payment`)». | U | niedrig | nein | Lesen |
| B-69 | Prosa | docs/backlog.md §1/§2 | Beschreibt `location_type`, `instances.locations`-Map, GIN-Index – heute `instance_units.place_object_id/place_unit_id`. | U oder nach history | niedrig | nein | Lesen |
| B-70 | Prosa vs. Code | CLAUDE.md (mehrfach, z. B. #778) ↔ backend/start.sh:7-9 | «Der Deploy fährt kein `alembic upgrade head` gegen die dev-Datenbank» – `start.sh` (CMD im Dockerfile) führt es bei **jedem** Start aus. Entweder scheitert es auf dev dauerhaft (dann ist die Ursache ein blockierter Migrationspfad, z. B. «Can't locate revision», und gehört repariert), oder die Aussage ist falsch und viele Netze sind Doppelpfade. | **zu prüfen** (Cloud-Run-Log `migration.log` / `alembic current` auf dev) | mittel | nein | Lesen Dockerfile + start.sh |
| B-71 | Prosa (Frontend, nur Hinweis) | frontend/src/lib/modules.ts:203; components/erp/article-detail.tsx:72 | Kommentar «gespiegelt von `domain/deal.QUOTE_STATES`»; Platzhalter «darunter wird automatisch nachbestellt» (es gibt keinen Nachschub). | an Frontend-Agenten | niedrig | nein | grep |

---

## Funktionen > 80 Zeilen

Gemessen mit AST (`end_lineno − lineno + 1`; in Klammern ohne Docstring).

| Länge | Datei:Zeile | Funktion |
|---|---|---|
| 297 (279) | app/services/voucher.py:2437 | `embed_data` |
| 254 (220) | app/services/process.py:927 | `confirm_step` |
| 222 (218) | app/main.py:452 | `_ensure_columns` |
| 165 (151) | app/services/process.py:590 | `release` |
| 121 (111) | app/services/flow.py:506 | `build` |
| 83 | app/services/process.py:93 | `_pass` |

`backend/scripts`: keine. Grösste Dateien: services/voucher.py 2883, services/process.py 2090,
domain/voucher.py 1280, routers/orders.py 1055 Zeilen.

Ansatzpunkte: `_ensure_columns` zerfällt natürlich in «Schema-Netze» + «Daten-Reparaturen» (je
eigener `try`, B-34); `embed_data` in Kopf/Positionen/Angebote/Geld/Rechte (je Abschnitt ein
Helfer, der dieselbe `won`/`internal`-Sicht bekommt); `confirm_step` in Prüfen → Ziehung/Erfassung
→ Übergang → Nachlauf.

---

## Paketierung (klein, einzeln deploybar)

Reihenfolge nach Nutzen/Risiko. Jedes Paket mit eigenem Wächter gegen seine Bug-Form.

**Paket 1 – Mail-Versand härten** (B-30, B-31, B-32) · Verhalten ja, keine Migration.
`send_due` mit `SKIP LOCKED`; Versandergebnis je Mail sofort festschreiben (Savepoint/commit),
Metadaten-Abruf in `try`, Fehlstatus loggen. *Höchste Priorität: ein Doppelversand an Kunden ist
nicht zurückholbar.*

**Paket 2 – Startup entschärfen** (B-33, B-34) · keine Migration.
DROP-Zweig des Formwächters durch Meldung ersetzen; Daten-Reparaturen je eigener `try` + Logging;
`SET DEFAULT` nur bei Bedarf.

**Paket 3 – Tote Endpunkte & Funktionen** (B-03, B-04, B-05, B-06, B-07, B-13, B-14, B-15) ·
OpenAPI ändert sich → `dump_openapi` + `generate:types`. Kein DB-Effekt. B-01/B-02 erst nach
fachlicher Entscheidung (AGB-Akzeptanz ist ein DSG-Thema).

**Paket 4 – Öffentliche Einstellungen** (B-35, B-44) · Verhalten ja (Plausible lädt).
`/admin/settings/public` auf `plausible_domain` + `google_maps_api_key`, kein erfundener Fallback.

**Paket 5 – Eine Regel, eine Stelle** (B-40, B-41, B-42, B-43, B-48) · Suchverhalten ändert sich
leicht (Firma wird überall gefunden). Personensuche nach `people.search`, Endpunkt `GET /erp/people`
(alter Pfad einen Deploy lang als Alias), `STAFF_ROLES` einmal, UID einmal formatiert.

**Paket 6 – Umbenennungen ohne Migration** (B-47, B-55) · `iban` als Attribut über Spalte
`iban_encrypted`, defensive `getattr` raus.

**Paket 7 – Netze aufräumen, ohne Drop** (B-20 Teil Fix, B-21, B-22, B-23, B-24 Teilabfrage) ·
nach Bestätigung, dass jede Umgebung (dev, ggf. lokal/prod) die betreffenden Migrationen bzw.
Netze einmal gesehen hat (B-70 vorher klären).

**Paket 8 – Prosa** (B-49, B-54, B-60…B-69, B-29) · reine Text-Änderung; Achtung: einige
Wächter in `test_frontend_mirrors.py` lesen Quelltext – vorher prüfen, dass keiner an einem
Kommentar hängt. `backend/CLAUDE.md`-Endpunkttabelle aus den Routern neu erzeugen.

**Paket 9 – Messen** (B-38, B-50, B-52, B-37) · erst Abfragen zählen (Wächter wie bei der
Halter-Kette), dann `open_counts`/`answered` vorfiltern, `load_only` ohne `html`; Index/FK
`corrects_id` ins Raw-Netz; `sync_lines` konfliktfest.

**Paket F – Spalten-Drops** (B-08, B-09, B-20, B-25, B-26, B-27, B-28 Spalten) ·
**nur nach Sicherung der produktiven DB** (`scripts/dump-db.sh`, Lesbarkeit prüfen). Mit den
Drops fallen die zugehörigen Backfills/Netz-Einträge (`invoice_backfill_sql`, `magnitude_sql`,
`migrate_sql`, `business_sql`, `_NULLABLE_SAFETY_NET`-Einträge). Zwei-Deploy-Regel ist bei allen
bereits erfüllt (Mapping seit ≥1 Deploy weg) – ausser B-08/B-09: dort erst Mapping entfernen,
Drop im Folge-Deploy.

**Paket G – Tabellen-Drops** (B-28 Tabellen, `message_replies` mit B-24) · unumkehrbar,
**Sicherung der produktiven DB zwingend**, Entscheidung durch einen Menschen.

---

## Offen / nicht gemessen

- Ob `alembic upgrade head` auf dev durchläuft (B-70) – entscheidet, wie viele Netze Doppelpfade sind.
- Abfragezahl einer Auftragsantwort mit mehreren Modulen (B-38) und Laufzeit von `open_counts` (B-50).
- Ob Index/FK zu `vouchers.corrects_id` auf dev existieren (B-52).
- Ob Tests die als tot gemeldeten Response-Felder (B-10) prüfen – vor dem Entfernen je Feld grep in `backend/tests`.
