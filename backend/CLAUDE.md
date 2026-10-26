# Backend – FastAPI (Python 3.12)

> **Ist-Stand.** Wie das Backend so geworden ist (Rundenberichte, Testnotizen), steht in
> `docs/history/2026-10-backend-claude-md-chronik.md`. Die Prozesslogik steht in
> `PROCESS_CORE.md`, die Regeln als prüfbare Sätze in `SYSTEM_LOGIC.md`. Im Zweifel gilt der
> Code.

## Technologie
Python 3.12, FastAPI 0.115, SQLAlchemy 2.0, Pydantic v2, Alembic, PostgreSQL 16. Die
Versionen stehen gepinnt in `requirements.txt` – **mit diesen** generieren (siehe unten),
sonst produziert eine neuere Umgebung einen Diff, der lokal unsichtbar ist und erst die CI
rot macht.

## Pflichtregeln – vor jeder Änderung
```bash
git fetch origin develop && git pull origin develop
git log --oneline -5 && git status
```
Dann die betroffene Datei frisch lesen – nie eine Kontext-Zusammenfassung als Dateiinhalt
behandeln.

## Starten
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Alembic und der Start
```bash
alembic upgrade head                                 # Migrationen anwenden
alembic revision --autogenerate -m "description"     # neue Migration
```
- **`start.sh` fährt `alembic upgrade head` bei JEDEM Start – auf jeder Umgebung, auch auf
  dev.** Scheitert der Lauf (z. B. «Can't locate revision» nach einem Revert), startet
  uvicorn trotzdem, und dann tragen die **Lifespan-Netze** in `main._ensure_columns` – der
  **zweite Weg**, kein Ersatz.
- Die Netze: `_COLUMN_SAFETY_NET` (fehlende Spalten) · `_NUMERIC_SAFETY_NET` (Skala) ·
  `_NULLABLE_SAFETY_NET` (gelöste `NOT NULL`) · `_INDEX_SAFETY_NET` ·
  `_RAW_INDEX_SAFETY_NET` (Indizes, CHECKs, Fremdschlüssel, partielle Unique-Indizes).
  `create_all` legt nur fehlende **Tabellen** an.
- **Daten-Reparaturen** stehen je als Funktion mit eigenem Savepoint in `main._DATA_REPAIRS`
  (heute: `orders.name` · `instance_units.status` · `user_profiles` ·
  `company_settings` · `newsletter_consents`); ihre SQL kommt aus der Fachschicht (`statuses.terminal_guard_sql`,
  `people.repair_sql`, `address_book.ADDRESS_INDEXES`,
  `communication.*_repair_sql`, `sites.backfill_keys`). Scheitert eine, laufen die übrigen.
- **Zwei Trigger entstehen bei jedem Start neu** (und in ihrer Migration): `statuses.terminal_guard_sql`
  (Endzustand) und `timekeeping.append_only_sql` (Zeiterfassung: `time_entries` und
  `time_contracts` sind append-only – kein UPDATE, kein DELETE).
- **Der Start löscht nichts und ernennt niemanden**: kein `DROP TABLE` (ein Wächter
  verbietet es), der Formwächter `_check_core_tables_shape` legt eine fehlende
  Prozess-Tabelle an und **meldet** eine fremde Form; Admin wird nur `initial_admin_email`
  (`main._bootstrap_admin`, `core/auth`).

### Eine Änderung am Schema ist erst fertig, wenn …
- **neue Tabelle**: die Migration legt den **vollständigen** Spaltensatz des Modells an,
  inklusive geerbter (`is_active`, `created_at`, `updated_at`);
- **neue Spalte** auf bestehender Tabelle: Migration **und** `_COLUMN_SAFETY_NET`;
- **neuer Index/CHECK/Fremdschlüssel**: Migration **und** `_RAW_INDEX_SAFETY_NET` – und die
  Migration ist **je Objekt** idempotent (nicht «Spalte da → fertig»);
- **Datenänderung**: Migration **und** ein Eintrag in `_DATA_REPAIRS`, der sich selbst
  begrenzt (zweiter Lauf ändert nichts);
- **Drop**: Zwei-Deploy-Regel – erst das Mapping weg (Nullable-Netz), im Folge-Deploy die
  Spalte; die offene Liste steht in `docs/backlog.md`.
- Geprüft wird das, nicht geglaubt: `tests/test_schema_is_built_by_the_migrations.py` baut
  eine Wegwerf-DB per `alembic upgrade head` und vergleicht Modell ↔ Schema. **Lokal testen
  wie die CI** – gegen ein Schema, das nur aus den Migrationen kommt.

## Struktur
```
app/
├── main.py           ← App, Router-Registrierung, CORS, Lifespan-Netze, Daten-Reparaturen
├── core/             ← config.py (Settings – nur, was der Code liest) · database.py ·
│                       auth.py (Firebase-JWT, get_current_user, require_employee, require_admin)
├── domain/           ← der fachliche Kern: KEINE DB, KEINE Services
│   ├── statuses.py   ← jeder Zustand: Beschriftung, Ampelton, Achsen, stock, terminal
│   ├── modules.py    ← die Prozessschrittmodule (MODULES) und was jedes deklariert
│   ├── capture_types/← Erfassungspunkt-Typen (text · yes_no · photo · signature · measure)
│   ├── sampling.py   ← die Stichprobe als EINE Zahl
│   ├── chain.py      ← die Kettenregel (an Artikel-Vorlage UND Auftrag)
│   ├── voucher.py    ← der Beleg: Direction, Stufen, Steuer (VAT_RATES, vat_split,
│   │                   vat_choices nach Anschrift), Saldo (balance), Mahnstufen, Wörter
│   ├── currency.py   ← Währungen (ISO 4217) mit ihren Nachkommastellen
│   ├── incoterms.py  ← die elf Klauseln der Incoterms 2020 mit Erklärung
│   ├── communication.py ← Kanäle, Rollen, Versandarten, Betreff/Anliegen, overdue (2 h), Signatur
│   ├── newsletter.py ← Quellen der Einwilligung, Gültigkeit der Bestätigung
│   ├── timekeeping.py← Zeiterfassung: Absenzarten (je EINE Wirkung), Regeln CH (ArG/OR),
│   │                   Hinweise, Reglement-Texte (ⓘ), append-only-Trigger
│   └── uid.py        ← UID-Normalform und Prüfziffer (eCH-0097)
├── models/           ← SQLAlchemy 2.0 (je Entität eine Datei; Import über models/__init__)
├── schemas/          ← Pydantic v2 Request/Response
├── routers/          ← dünn; je Ressource eine Datei
├── services/         ← Fachlogik (siehe «Wo was steht»)
└── assets/           ← website_contact.json (generiert von website/scripts/export-erp.mjs)

scripts/
├── dump_openapi.py   ← OpenAPI → backend/openapi.json (Quelle der Frontend-Typen)
├── dump_statuses.py  ← domain/statuses.py → frontend/src/lib/status-catalog.ts
├── deadcode.py       ← «was liest eigentlich niemand mehr?» (beide Seiten)
├── build_geoip.py    ← DB-IP Lite → IP→Land (im Docker-Build)
├── invariant_report.py · scenario_report.py
```

### Wo was steht (`services/`)
| Bereich | Datei(en) |
|---|---|
| Prozess-Engine (Freigabe, Bestätigen, Halt, Auswahl) | `process.py`, `orders.py`, `materialize.py` |
| Prozessbild, Protokoll, Journey, Genealogie | `flow.py`, `record.py`, `journey.py`, `genealogy.py` |
| Module | `capture.py`, `sampling.py`, `consumption.py`, `places.py`, `voucher.py` (+ `voucher_docs.py`, `document.py`, `legal.py`, `payment_list.py`, `stripe_pay.py`, `qrbill.py`) |
| Artikel, Instanzen, Bestand, Stückliste | `articles.py`, `article_process.py`, `article_names.py`, `instances.py`, `bom.py` |
| Personen, Adressen, Firmen | `people.py`, `address.py`, `address_book.py`, `sites.py`, `geography.py`, `geoip.py`, `phone.py` |
| Kommunikation | `communication.py`, `mailbox.py`, `mail_layout.py`, `inquiry.py`, `newsletter.py` |
| Zeiterfassung | `timekeeping.py` (rechnen + die EINE Schreibstelle `record`), `time_view.py` (Antwort der Karte), `holidays.py` (Feiertage, Regeln der Gesellschaft), `todo.py` (die Zahl am Symbol) |
| Querschnitt | `objects.py` (Nummernkreis), `lookup.py` (Nummer ODER Name), `attachments.py`, `passkey.py`, `feedback.py`, `admin.py`, `invariants.py` |

## OpenAPI → Frontend-Typen (Single Source of Truth)
Nach jeder Änderung an einem Request/Response-Schema oder am Statuskatalog:
```bash
cd backend && python -m scripts.dump_openapi     # → backend/openapi.json
cd backend && python -m scripts.dump_statuses    # → frontend/src/lib/status-catalog.ts
cd ../frontend && npm run generate:types          # → src/types/api.ts
```
Die CI generiert alle drei neu und bricht bei jedem Unterschied ab. Das Ergebnis hängt an
der FastAPI-/Pydantic-Version – vorher prüfen:
```bash
python -c "import fastapi,pydantic;print(fastapi.__version__, pydantic.VERSION)"
# muss zu requirements.txt passen (fastapi==0.115.5, pydantic==2.10.2)
```
Ein neuer Status ist **eine Zeile in `CATALOG`**; fehlt einem Stück-Zustand `stock`, startet
die App nicht.

## API-Endpunkte (aus dem Code)
Quelle: `@router.<methode>(…)` in `app/routers/*.py` mit dem Präfix aus `APIRouter(prefix=…)`,
registriert in `main.py`. **109 Routen**. Auth: `admin` = `require_admin`,
`staff` = `require_employee` (admin oder employee), `user` = angemeldet, `–` = ohne
Anmeldung. Einige Routen prüfen zusätzlich im Rumpf (vermerkt).

| Methode | Pfad | Auth | Zweck |
|---|---|---|---|
| GET | `/health` | – | Health Check |
| GET · PATCH | `/api/v1/auth/me` | user | Eigenes Profil lesen / ändern (Selbstbedienung, `people.apply_profile_update`) |
| POST | `/api/v1/auth/me/email-check` | user | Ist die neue Anmelde-E-Mail frei? (`people.email_problem`, vor dem Firebase-Bestätigungslink) |
| POST · PATCH · DELETE | `/api/v1/auth/me/addresses` · `/{address_id}` | user | Eigenes Adressbuch |
| POST | `/api/v1/auth/passkeys/register/options` · `/register/verify` | user | Passkey registrieren |
| GET · DELETE | `/api/v1/auth/passkeys` · `/{passkey_id}` | user | Eigene Passkeys verwalten |
| POST | `/api/v1/auth/passkeys/login/options` · `/login/verify` | – | Anmelden mit Passkey → Firebase Custom Token |
| POST | `/api/v1/contact` | – | Anfrage der Website → Nachricht im ERP (`services/inquiry`); Honigtopf, Mindestzeit, 5/h je IP; 503 mit Ausweg, wenn nicht speicherbar |
| GET | `/api/v1/public/contact` | – | Telefon, E-Mail, Anschrift der Gesellschaft zum Land des Besuchers |
| GET · PATCH | `/api/v1/admin/settings` | admin | Plattform-Konfiguration des Betreibers (Maps-Schlüssel) |
| GET | `/api/v1/admin/settings/public` | – | Nur der Google-Maps-Schlüssel |
| GET · POST | `/api/v1/admin/companies` | staff | Firmen lesen / anlegen (eigene nur Admin) |
| GET · PATCH · DELETE | `/api/v1/admin/companies/{object_id}` | staff | Firma lesen / ändern / schliessen (eigene nur Admin; Betreiber und letzte eigene nicht schliessbar) |
| POST | `/api/v1/admin/companies/{object_id}/reopen` | staff | Geschlossene Firma wieder öffnen |
| POST | `/api/v1/admin/companies/{object_id}/operator` | admin | Zum Betreiber der Website machen |
| GET · PUT | `/api/v1/admin/territories` · `/{area}` | admin | Gebietskarte lesen / ein Gebiet zuweisen |
| GET | `/api/v1/erp/objects/{object_id}` | staff | Was ist diese Objektnummer? (QR-Scan) |
| GET · POST | `/api/v1/erp/records` | staff | Benutzer-Feed / Person anlegen (Personal-Rollen nur Admin) |
| GET · PATCH | `/api/v1/erp/records/{object_id}` | staff · admin | Benutzer lesen (staff) / ändern (admin) |
| POST · PATCH · DELETE | `/api/v1/erp/records/{object_id}/addresses` · `/{address_id}` | admin | Adressbuch einer Person |
| GET | `/api/v1/erp/people` | staff | **Personensuche** (`people.search`: Nummer, Firma, Name, E-Mail; `staff=true` nur Personal) |
| GET | `/api/v1/erp/companies` | staff | Firmen-Vorschläge (Nummer, Name, UID) |
| GET · POST | `/api/v1/erp/articles` | staff | Artikel-Feed / anlegen = freigeben (`replaces_object_id` löst einen Vorgänger ab) |
| GET | `/api/v1/erp/articles/name-suggestions` | staff | Ähnliche Namen, lexikalisch, ohne KI |
| POST | `/api/v1/erp/articles/validate` | staff | Entwurf prüfen, ohne ihn anzulegen |
| GET | `/api/v1/erp/articles/{object_id}` | staff | Artikel lesen (es gibt kein Ändern) |
| GET | `/api/v1/erp/articles/{object_id}/stock` | staff | Bestand in drei Ebenen, seitenweise |
| GET | `/api/v1/erp/articles/{object_id}/process` | staff | Eingefrorener Erzeugungsprozess (nur lesen) |
| GET | `/api/v1/erp/instances` · `/{object_id}` | staff | Instanz-Feed / eine Instanz |
| GET | `/api/v1/erp/instances/{object_id}/units` | staff | Nummern der Einzelinstanzen, seitenweise |
| GET | `/api/v1/erp/instances/{object_id}/units/{suffix}/genealogy` | staff | Woraus besteht das Stück, worin steckt es (Ableitung aus dem Log) |
| GET | `/api/v1/erp/places` · `/{object_id}` | staff | Halter suchen / Kann diese Nummer etwas halten? (404 ist eine Antwort) |
| GET · POST | `/api/v1/erp/orders` | user · staff | Auftrag-Feed (Partner: nur die eigenen) / Auftrag erteilen = freigeben (staff) |
| GET | `/api/v1/erp/orders/article-options` · `/unit-options` · `/module-catalog` | staff | Auswahl für den Entwurf (FIFO-Vorauswahl vom Server, `preselect=N`) |
| POST | `/api/v1/erp/orders/validate` | staff | Entwurf prüfen inkl. Vorschau des Prozessbildes |
| GET | `/api/v1/erp/orders/{object_id}` | user | Auftrag lesen; ein Partner sieht nur sein Modul, ein Unbeteiligter 404 |
| GET | `/api/v1/erp/orders/{object_id}/units?edge=` | staff | Stücke einer Kante des Prozessbildes |
| POST | `/api/v1/erp/orders/{object_id}/steps/{step_id}/confirm` | staff | **Ein Modul bestätigen** – für EINE Instanz (`instance_object_id`, `verification`) |
| GET | `…/steps/{step_id}/hold?instance=&group=` | staff | Nummern einer Gruppe (`sample` · `failed` · `rest`), erst auf Klick |
| GET | `…/steps/{step_id}/record` | staff | Modul-Protokoll, seitenweise |
| POST | `…/steps/{step_id}/voucher` | user | **Eine Handlung am Beleg** (`voucher.VERBS`, `can` ist das Tor) |
| POST | `…/steps/{step_id}/voucher/payment` | user | Zahlungsabsicht für die Bezahlkarte vorbereiten |
| POST | `…/steps/{step_id}/voucher/refund` | staff | Kartenzahlung über den Dienst erstatten |
| GET | `…/steps/{step_id}/voucher/transfer` | user | Überweisungsangaben + Swiss QR-Rechnung |
| GET | `…/steps/{step_id}/voucher/correctable` | staff | Welche Rechnung mindert dieser Beleg? (Suche, auch über Auftragsgrenzen) |
| POST | `/api/v1/erp/attachments` | staff | Bild aus der Kamera hochladen – oder PDF/Bild als Datei, **nur** für den Ausfuhrnachweis (`attachments.store_file`) |
| GET | `/api/v1/public/beleg/{token}` | – (Token) | **Kundenseite** eines Dokuments: eingefrorenes A4-HTML, Hinweis (überholt/abgelaufen/storniert), Handlungen aus `can` der Partei |
| POST | `/api/v1/public/beleg/{token}/accept` · `/decline` · `/payment` | – (Token) | Offerte annehmen / ablehnen / Kartenzahlung vorbereiten (`voucher_docs.public_act`) |
| GET | `/api/v1/public/legal/{kind}` | – | AGB · Datenschutz · Impressum, wie sie heute gelten, als A4-Dokument (`services/legal`, `document.standalone`) |
| GET | `/api/v1/erp/payments?person=\|company=` | staff | **Zahlungen** einer Person oder eigenen Gesellschaft (Ableitung, `services/payment_list`) |
| GET | `/api/v1/attachments/{token}` | – | Bild ausliefern (unerratbarer Token) |
| POST | `/api/v1/payments/webhook` | – (Signatur) | Rückmeldung des Zahlungsdienstes – bucht eine Geld-Zeile am Beleg, sonst nichts |
| GET | `/api/v1/erp/messages` | staff | Verlauf einer Person (`person=`) oder Firma (`company=`) |
| POST | `/api/v1/erp/messages` | staff | Nachricht anlegen (jede Art dieselbe Form) |
| GET | `/api/v1/erp/messages/channels` | staff | Kanäle, aus denen man schreiben kann |
| GET | `/api/v1/erp/messages/mailboxes?company=` | staff | Postfach einer eigenen Gesellschaft |
| POST · DELETE | `/api/v1/erp/messages/mailboxes/{channel}/connect` · `/{channel}` | staff | Verbinden (Google-Zustimmung) / trennen – nur Admin (im Dienst geprüft) |
| POST | `/api/v1/erp/messages/sync` | staff | Abgleichen und Fälliges senden (30 s je Postfach) |
| GET | `/api/v1/mail/callback` | – (signierter `state`) | Rückkehr von Google → `/erp?mail=…` |
| POST | `/api/v1/newsletter` | – | Anmeldung von der Website (E-Mail → Bitte um Bestätigung); Honigtopf, 5/h je IP |
| GET · POST | `/api/v1/newsletter/confirm?t=` | – (signierter Link) | Bestätigen → angemeldet (Quelle aus dem Link) → `/newsletter/bestaetigt` |
| GET · POST | `/api/v1/newsletter/unsubscribe?t=` | – (signierter Link) | GET zeigt einen Knopf, POST meldet ab; One-Click (RFC 8058) direkt |
| GET · PUT | `/api/v1/auth/me/newsletter` | user | Mein Newsletter (Konto) – direkt an/ab, die Adresse ist bestätigt |
| GET | `/api/v1/erp/newsletter/{object_id}` | staff | Zustand und Nachweis einer Person |
| POST | `/api/v1/erp/newsletter/{object_id}/invite` · `/unsubscribe` | staff | Bitte um Bestätigung schicken / abmelden (anmelden kann das ERP niemanden) |
| GET | `/api/v1/erp/todo` | staff | **Was zu tun ist** je Datensatz – die Zahl am Symbol (offene Nachrichten, Zeiterfassung nur eigene/Admin, Pflichtangaben, Feiertage nur Admin; `services/todo`) |
| GET | `/api/v1/erp/time/{object_id}?month=` | staff (selbst · Admin) | **Zeiterfassung** einer Person: Konto, Ferien, Verträge, Buchungen, ein Monat (`services/time_view`) |
| POST | `/api/v1/erp/time/{object_id}/swipe` | staff (selbst · Admin) | Kommen ↔ Gehen, Serverzeit, ein Schlüssel je Wisch (idempotent, 60-s-Sperre) |
| POST | `/api/v1/erp/time/{object_id}/entries` · `/entries/preview` | staff (selbst · Admin) | **Ein Eintrag** (Stempel nachtragen/korrigieren, Absenz, Nachweis, Buchung = Admin, Rücknahme) / dieselbe Regel als Vorschau, ohne zu schreiben (`timekeeping.record` · `preview`) |
| POST | `/api/v1/erp/time/{object_id}/contracts` | admin (im Dienst) | Neuer Vertrag ab Stichtag; 0 h = Austritt |
| GET · PUT | `/api/v1/erp/time/companies/{object_id}` · `/rules` | staff · admin | Feiertage, Nachweis-Regeln, Regeln des Landes einer eigenen Gesellschaft / Kanton und Nachweis setzen |
| GET | `/api/v1/erp/time/companies/{object_id}/proposal?year=` | admin | Vorschlag der Feiertage (OpenHolidays) – geholt, nicht gespeichert |
| POST · DELETE | `/api/v1/erp/time/companies/{object_id}/holidays` · `/{holiday_id}` | admin | Feiertage übernehmen / einen entfernen (Soft-Delete) |
| GET · POST · DELETE | `/api/v1/feedback` | user | Testnotizen (nur Testumgebung); `DELETE ?scope=done\|all` räumt die eigenen |
| PATCH · DELETE | `/api/v1/feedback/{note_id}` | user | Notiz erledigt/verworfen setzen / löschen |

## Befehle statt Feld-Updates
- **Ein Auftrag entsteht als GANZES** (ein `POST`); es gibt kein `PATCH /orders/{id}`.
- **Bewegt wird er über zwei Befehle**: `confirm` (ein Modul bestätigen) und `voucher` (eine
  Handlung am Beleg). Beide sind POST; ein Wächter verbietet `PATCH` und `DELETE` im
  Auftrags-Router (`test_source_process.test_a_status_change_always_writes_the_log`),
  damit jede Zustandsänderung durch die Stelle geht, die den Log schreibt.
- **Der Beleg** (`services/voucher.py`): jedes Verb steht EINMAL in `VERBS` – Stufen
  (`offer` · `agreed` · `billed`), nötige Stammdaten (`needs` → `DataGap`), wer darf
  (`party`: `ALWAYS` · `IF_WE_PRICE` · `IF_THEY_PRICE`) und die Funktion. `can` liest
  dieselbe Tabelle für die Knöpfe und `assert_allowed` weist an ihr ab (fehlende Angabe →
  400 mit Feldname, falsche Stufe → 409). `pay_online`/`refund_online` ändern den Beleg
  nicht – gebucht wird nur vom Webhook (`record_payment`). Nach jeder Handlung (`_after`)
  entsteht, was dazugehört (Quittung), und die Stücke ziehen weiter
  (`process.advance_payments` → `confirm_step(auto=True)`). Ein Dokument entsteht nur über
  `voucher_docs.issue` (eingefroren in `voucher_documents`, Mail im Postfach der
  Gesellschaft, gesendet nach dem Commit über `send_pending`).
- **Ein Lesepfad, der schreibt, behält**: die Positionen werden beim Anzeigen aus dem
  Prozess nachgezogen (`voucher.sync_lines`); committet wird an der Transaktionsgrenze
  (`routers/orders._steps`), nicht im Dienst.

## Unternehmen (`services/sites.py`)
`company_settings` trägt **mehrere** Firmen: eigene Gesellschaften (`is_own`) mit voller
Rechtsidentität und fremde (nur `EXTERNAL_FIELDS`: Name, Rechtsform, UID). Genau eine eigene
ist **Betreiber** (`is_operator`, partieller Unique-Index; ohne Markierung tolerant die
älteste). Die EINE Auflösung: `find_operator()` (rein lesend), `by_object_id()`,
`require_own()`, `company_for_country()`, `resolve()` (erkennen über `uid_key`/`name_key`
oder anlegen), `legal_name()` (Name + Rechtsform, ohne «AG AG»). **Nie**
`CompanySettings.id == 1` oder ein blosses `.first()` (`tests/test_sites.py`).
`ENTITY_FIELDS` (je Gesellschaft) ↔ `PLATFORM_FIELDS` (die eine Website). Die
Kontakt-E-Mail einer eigenen Gesellschaft schreibt allein das Postfach (`mailbox._contact`).

## Konventionen
- Soft-Delete überall (`is_active=false`), kein hard delete. `is_active` (Soft-Delete) und
  `status` (fachlich) sind zwei Achsen.
- UTC-Timestamps; Pydantic v2 (`model_validate`, `model_dump`,
  `ConfigDict(from_attributes=True)`); SQLAlchemy 2.0 (`Mapped[T]`, `mapped_column`).
- Fehler: `HTTPException(status_code=…, detail="…")` mit einem Satz, der die Sache nennt.
- Audit-Log bei jedem Update (`people.apply_profile_update` ist der eine Pfad für den
  Benutzer).
- **Pydantic verwirft unbekannte Felder still** – ein neues Feld gehört in Request-Schema
  **und** Dienst; ein Feld, das die Oberfläche nicht anbietet, verwirft der Dienst
  ausdrücklich.
- Personal-Prüfung nur über `people.STAFF_ROLES` (auch in `require_employee`).

## Env-Variablen
`/.env.example` nennt **nur, was der Code auch liest**. Pflicht lokal: `DATABASE_URL`,
`FIREBASE_PROJECT_ID`. Optional: `INITIAL_ADMIN_EMAIL`, `GOOGLE_CLIENT_ID`/`_SECRET`
(Gmail), Stripe-Schlüssel (`docs/stripe-setup.md`). Secrets nie im Repo.

## Tote Stellen finden
```bash
cd backend && python -m scripts.deadcode              # beide Seiten
cd backend && python -m scripts.deadcode --backend    # nur das Backend
```
Jede Fundstelle ist ein **Hinweis**, kein Urteil: ein Endpunkt wird über den Router
aufgerufen, ein Wächter über den Test.
