# Backend – FastAPI (Python 3.12)

## Technologie
Python 3.12, FastAPI 0.109, SQLAlchemy 2.0, Pydantic v2, Alembic, PostgreSQL 15

## Pflichtregeln – vor jeder Änderung

Vor der ersten Änderung in einer Sitzung:
```bash
git fetch origin develop && git pull origin develop
git log --oneline -5 && git status
```
Dann: Betroffene Datei mit Read-Tool frisch laden – niemals Kontext-Zusammenfassungen als Dateiinhalt behandeln.

## Starten
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Alembic
```bash
alembic upgrade head          # Migrationen anwenden
alembic revision --autogenerate -m "description"  # Neue Migration erstellen
```

## Struktur
```
app/
├── main.py           ← FastAPI App, Router-Registrierung, CORS
├── core/
│   ├── config.py     ← Pydantic Settings (env vars)
│   ├── database.py   ← SQLAlchemy Engine + Session
│   └── auth.py       ← Firebase JWT-Verifikation, require_admin/require_staff
├── models/           ← SQLAlchemy 2.0 Modelle (je ein File pro Entität)
│   ├── user.py       ← UserProfile
│   ├── audit.py      ← AuditLog
│   ├── notification.py ← Notification
│   ├── admin.py      ← CompanySettings
│   └── __init__.py   ← Re-Export aller Modelle (immer von hier importieren)
├── schemas/          ← Pydantic v2 Request/Response Schemas
├── routers/          ← FastAPI Router (je ein File pro Ressource)
├── services/         ← Business Logic (DB-unabhängig testbar)
└── scripts/
    └── dump_openapi.py ← OpenAPI-Schema → backend/openapi.json (SSOT für FE-Typen)
```

## OpenAPI → Frontend-Typen (Single Source of Truth)
Die TypeScript-Typen des Frontends werden aus den Pydantic-Schemas generiert.
Nach jeder Änderung an einem Request/Response-Schema:
```bash
cd backend && python -m scripts.dump_openapi     # → backend/openapi.json
cd backend && python -m scripts.dump_statuses    # → frontend/src/lib/status-catalog.ts
cd ../frontend && npm run generate:types          # → src/types/api.ts
```

> **Die Statusliste gehört dazu.** `app/domain/statuses.py` ist die eine Quelle; das
> Frontend spiegelt sie nicht, es **bekommt** sie (`scripts/dump_statuses.py`). Ein neuer
> Status ist **eine Zeile in `CATALOG`** – mit Beschriftung, Ampelton, Achsen und (für
> Stücke) Bestands-Zugehörigkeit. Fehlt Letztere, **startet die App nicht** (`_check`):
> ein Stück-Zustand, der nicht sagt, ob er zum Bestand zählt, landete sonst
> stillschweigend irgendwo, und die Bestandsleiste zeigte eine Zahl, die niemand
> nachrechnet.

> **ACHTUNG – mit den GEPINNTEN Versionen generieren.** Die CI (`deploy-dev.yml`,
> Job «Quality gates») generiert beides neu und bricht bei jedem Unterschied ab
> («Generierte Typen sind veraltet»). Das Ergebnis hängt an der **FastAPI-/Pydantic-
> Version**: eine neuere Umgebung schreibt z. B. `additionalProperties: true` dort,
> wo die gepinnte es weglässt (`Record<string, never>` statt `{[key: string]: unknown}`
> in der `api.ts`). Wer mit global installierten, neueren Paketen generiert, produziert
> deshalb einen Diff, der lokal unsichtbar ist und erst die CI rot macht.
>
> Vor dem Generieren prüfen, dass die aktive Umgebung `requirements.txt` entspricht:
> ```bash
> python -c "import fastapi,pydantic;print(fastapi.__version__, pydantic.VERSION)"
> # muss zu requirements.txt passen (fastapi==0.115.5, pydantic==2.10.2)
> ```
> Passt es nicht, in einem venv mit `pip install -r requirements.txt` generieren.

## API-Endpunkte (tatsächlich vorhanden, Phase 1)
| Method | Path | Auth | Beschreibung |
|--------|------|------|--------------|
| GET | /health | – | Health Check |
| GET | /api/v1/auth/me | user | Eigenes Profil |
| PATCH | /api/v1/auth/me | user | Eigenes Profil bearbeiten (Self-Service) |
| POST | /api/v1/auth/terms-accept | user | AGB akzeptieren |
| GET | /api/v1/erp/records | staff | Benutzer-Feed (Master-Detail) – **auch deaktivierte**: «inaktiv» ist ein Zustand, kein Verschwinden |
| GET/PATCH | /api/v1/erp/records/{object_id} | staff/admin | Datensatz lesen/ändern |
| GET/POST | /api/v1/erp/articles | staff | Artikel-Feed (`search`/`limit`) / Artikel anlegen – Anlegen **ist** Freigeben; `replaces_object_id` löst dabei einen Vorgänger ab (er geht im selben Zug ausser Betrieb) |
| GET | /api/v1/erp/articles/name-suggestions | staff | Intelligente Namensvorschläge (frei + Fuzzy, ohne KI) |
| GET/PATCH | /api/v1/erp/articles/{object_id} | staff | Artikel lesen/ändern. **Ausser Betrieb nehmen ist ein Statuswechsel** (`status`), in beide Richtungen – kein eigener Endpunkt, kein Dialog. Das **Detail** trägt zusätzlich die Reihe (`replaces`/`replaced_by`) und die geplante Stückliste (`bom`: wer verbaut mich · was in mir ist ausser Betrieb, transitiv); im Feed bleibt `bom` `null` = «nicht geladen» |
| GET/POST | /api/v1/erp/articles/{object_id}/process-steps | staff | Prozessschritte (Purchase) lesen/anlegen |
| PATCH/DELETE | /api/v1/erp/articles/{object_id}/process-steps/{step_id} | staff | Prozessschritt ändern/entfernen |
| GET | /api/v1/erp/articles/{object_id}/stock | staff | **Bestand** – Aufstellung (Zustand → Menge → **Block**) über ALLE Stücke + eine Seite Instanzen mit je eigener Aufstellung (PROCESS_CORE §10.3) |
| GET | /api/v1/erp/orders/unit-options | staff | **Wählbare Einzelinstanzen – eine SEITE, nicht die Liste.** `search` (die Stücknummer, wie sie gebaut ist: «-7» = Suffix, «00123» = Instanz, «100000123-7» = beides) · `status` · `limit`/`offset` · `preselect=N` für die **FIFO-Vorauswahl vom Server**. Die Antwort trägt daneben die Aufstellung je Zustand über den **ganzen** Artikel und die Gesamtzahl – eine aus der Seite gezählte Zahl zeigte «60», wo fünfzigtausend liegen. Zwei Eigenschaften je Stück: `available` («lässt sich nehmen», aus `Status.terminal`) und `in_stock` («liegt im Regal», aus `Status.stock`) – FIFO fragt die zweite. |
| GET | /api/v1/erp/instances/{object_id}/units | staff | Die **Nummern** der Einzelinstanzen – seitenweise, optional auf Zustände gefiltert (`status` mehrfach) |
| GET | /api/v1/erp/orders | user | Auftrag-Feed (Lieferant: nur eigene, mit eingebettetem Prozess) |
| POST | /api/v1/erp/orders | staff | **Auftrag erteilen** – Bedarf + Positionen + Ablauf + Instanz-Auswahl in EINEM Aufruf, anlegen **und** freigeben; erst dabei entsteht die Objektnummer (ein Entwurf existiert nie in der DB) |
| GET | /api/v1/erp/orders/{object_id} | user | Auftrag lesen (inkl. Beschaffungs-Embed) |
| GET | /api/v1/erp/orders/{object_id}/diagnostics | staff | **Systemprotokoll** (Fehlersuche): Befund (abgeleiteter Zustand + Drift-Prüfung) + Chronologie aus Audit · Ereignissen · Material-Journal – on demand, keine eigene Wahrheit |
| PATCH | /api/v1/erp/orders/{object_id} | staff | Auftrag ändern (Freigabe stösst Prozess an); `picks` = gewählte **Anteile** (Instanz · Menge · Halter) |
| GET | /api/v1/erp/orders/supplier-options | staff | Zugelassene Lieferanten suchen (Nummer **oder** Name, dieselbe Bedingung wie überall: `services/lookup`) |
| POST | /api/v1/erp/orders/{object_id}/steps/{step_id}/confirm | staff | **Ein Modul bestätigen – für EINE Instanz.** `instance_object_id` + `verification` (`scan`\|`manual`) sind Pflicht (§4.4); ohne sie 400. `values` ist **zweistufig** – Nummer der Einzelinstanz → (Punkt → Wert), je gezogenem Stück ein Satz (§9.5). Die Art kommt aus dem **Scan-Dialog** (Kamera ↔ Tastatur), nicht von einem zweiten Knopf daneben. Bestanden → die Stücke rücken vor, nicht bestanden → sie bleiben stehen (§4.5). Antwort: der Auftrag; die Wirkung steht im Audit. |
| POST | /api/v1/erp/orders/{object_id}/steps/{step_id}/purchase | staff | **Den Beschaffungs-Beleg bewegen** – `action` ∈ `ask`·`quote`·`decline`·`order`·`note`·`revoke`·`clarified`. Ein **Befehl**, kein Feld-Update, darum POST wie `confirm` (der Wächter `test_a_status_change_always_writes_the_log` verbietet `PATCH` in diesem Router). Die Regel «ein **Lieferant** darf nur `quote`/`decline`, und nur auf **seiner** Zeile» steht im Dienst – die Tür ist heute Personal-only, weil ein Lieferant im Neuaufbau (noch) keine Sicht auf einen Auftrag hat; wer sie öffnet, baut zuerst den Sichtbarkeitsfilter auf der Antwort. |
| GET | /api/v1/erp/orders/{object_id}/steps/{step_id}/record | staff | **Was ist an diesem Modul passiert?** Je Vorgang (= eine Einzelinstanz, ein Durchgang): Nummer · wer · wann · wie bestätigt · Nachher-Zustand · Urteil · gezogen? · verbaut in? · **jeder erfasste Wert mit seiner Frage**. Eine Ableitung über den Ereignis-Log (`services/record.py`) – **zentral, kein Protokoll je Modultyp**; ein neuer Modultyp erbt es ohne eine Zeile. Seitenweise (`limit`/`offset`, Gesamtzahl daneben) und **erst auf Klick**: bei einer 6000er-Charge wären es tausende Zeilen in jeder Auftrags-Antwort. |
| GET | /api/v1/erp/orders/{object_id}/steps/{step_id}/hold?instance=&group= | staff | Die **Nummern** einer Gruppe dieser Instanz an diesem Modul: `sample` (die gezogenen – für jede ist ein Wertesatz zu erfassen, §9.5) \| `failed` \| `rest` (Vorauswahl der Entscheidung). **Erst auf Klick**: der «Rest» einer 6000er-Charge wären sechstausend Nummern in jeder Auftrags-Antwort. |
| GET/PATCH | /api/v1/erp/articles/{object_id}/sales | staff | Verkaufs-Profil (publiziert/Sichtbarkeit/Inhalt) – immer editierbar |
| GET/POST | /api/v1/erp/articles/{object_id}/sales/prices | staff | Verkaufspreise (1:n) lesen/anlegen |
| PATCH/DELETE | /api/v1/erp/articles/{object_id}/sales/prices/{price_id} | staff | Preis ändern/entfernen |
| POST | /api/v1/erp/articles/{object_id}/sales/audience | staff | Zielgruppe (private) zuweisen (Lesen: eingebettet im Sales-Profil) |
| DELETE | /api/v1/erp/articles/{object_id}/sales/audience/{row_id} | staff | Kunden-Zuweisung entfernen |
| GET | /api/v1/shop/config | – | Shop-Währungen + Default + Provider + **Publishable Key** (eingebettete Kasse) |
| GET | /api/v1/shop/products | optional | Publizierte Produkte (public + private des Kunden), inkl. Preis-Optionen |
| GET | /api/v1/shop/products/{object_id} | optional | Produktdetail (kanonisch über replaced_by_id) inkl. `prices[]` |
| POST | /api/v1/shop/checkout | user | **Warenkorb** (`items[]`) → CheckoutIntent → Stripe-Embedded (`client_secret`) / manual; Auftrag entsteht aufgeschoben bei Zahlung |
| POST | /api/v1/shop/portal | user | Stripe Customer Portal (Abo/Zahlungsmittel verwalten) → URL |
| POST | /api/v1/shop/payments/webhook | – | Stripe-Webhook (signaturgeprüft): Zahlung/Abo spiegeln |
| GET | /api/v1/shop/payment/{token} | user | Zahlungsstatus (manueller Fallback-Provider) |
| POST | /api/v1/shop/payments/simulate | user | Manueller Provider: Zahlung simulieren (nur ohne Stripe) |
| GET/PATCH | /api/v1/admin/settings | admin | Firmeneinstellungen des **Hauptsitzes** (Rechtsidentität + Systemkonfiguration, inkl. Shop-Währungen/Provider) |
| GET | /api/v1/admin/settings/public | – | Öffentliche Firma-Infos (immer der Hauptsitz – das Impressum nennt die Rechtsperson) |
| GET/POST | /api/v1/admin/companies | admin | **Unternehmen** (Gesellschaften): alle lesen (Betreiber/ältestes zuerst) / neues anlegen |
| GET/PATCH | /api/v1/admin/companies/{object_id} | admin | Ein Unternehmen lesen / Entitäts-Felder ändern (voller Feldsatz inkl. Rechtsidentität + Währung – **derselbe Pfad für jede** Gesellschaft; Plattform-Config bleibt bei `/admin/settings`) |
| POST | /api/v1/admin/companies/{object_id}/operator | admin | Diese Gesellschaft zum **Betreiber der Website** machen (genau EINE trägt den Titel) |
| GET | /api/v1/admin/users | staff | Benutzerliste |
| DELETE · POST …/reactivate | /api/v1/admin/users/{id} | admin | Benutzer deaktivieren / reaktivieren (Aktionen am **ERP-Benutzer-Datensatz**; die Rolle wird über `PATCH /erp/records/{object_id}` gepflegt – EIN Schreibpfad) |
| GET | /api/v1/admin/audit-log | admin | Audit Log |
| POST | /api/v1/contact | – | Kontaktformular |
| GET | /api/v1/ai/config | user | KI-Verfügbarkeit (Text/Bild) fürs Frontend |
| POST | /api/v1/ai/chat | user | Rechte-geschützter Assistent (Tools rollen-gescopt, ADR 004) |
| POST | /api/v1/ai/write | staff | KI-Schreibhilfe (Dokumente-Modul, Structured Output) |
| POST | /api/v1/ai/image-edit | staff | Shop-Bild mit Gemini bearbeiten → neues Attachment |
| POST | /api/v1/ai/actions/{id}/confirm · /reject | staff | KI-Vorschlag bestätigen/ablehnen (kritische Aktionen) |
| GET/POST | /api/v1/feedback | user | Testnotizen der Oberfläche (JEDE Rolle; eigene bzw. alle für Personal) – nur Testumgebung, sonst 404 |
| PATCH | /api/v1/feedback/{id} | user | Notiz erledigt/verworfen setzen bzw. wieder öffnen |
| DELETE | /api/v1/feedback/{id} · ?scope=done\|all | user | Notiz löschen bzw. aufräumen/zurücksetzen (weich, nur eigene sichtbare) |

> Artikel: **Stammdaten**, **Prozess** (Purchase-Schritt) und **Bestand** implementiert. Der
> Bestand ist reine Summierung über Einzelinstanzen, in drei Ebenen und **ohne Filter** (die
> Aufteilung selbst ist das Bedienelement) – PROCESS_CORE §10.3.
> Prozessschritt-Modul «Purchase»: Auftrag (Artikel+Menge) → Freigabe instanziiert
> die Bestellung. Diese läuft **unter der Auftragsnummer** (Tabelle `purchase_orders` OHNE eigene
> Objektnummer, eingebettet als `purchase` in der OrderResponse). Status requested→quoted→
> approved/rejected→confirmed→received; Einstandspreis netto/Stück wird auf den Artikel zurück-
> geschrieben; der Auftrag wird automatisch `completed`, wenn alle Schritte erledigt sind
> (`services/purchase.py`, `services/orders.py`). E-Mail-Versand ist nur als TODO vermerkt.
> Seriennummern/Eingangskontrolle, BOM/Arbeitspläne, Stripe sind Phase 2+ und **noch nicht** implementiert.
>
> Objektnummern (9-stellig) werden objekttyp-übergreifend in `app/services/objects.py`
> vergeben (Maximum über alle Objekttabellen + 1).
>
> **Unternehmen (Gesellschaften):** `company_settings` trägt **mehrere** gleichrangige
> Zeilen (je eine vollständige juristische Einheit, Typ `organization`, eigene Objektnummer,
> **eigene** Rechtsidentität). Der **Betreiber** (vertritt die eine Website, trägt die
> Plattform-Config) = das **älteste** Unternehmen, **abgeleitet** (kein `is_primary` mehr).
> Die EINE Auflösung ist `services/sites.py`: `operator()`/`primary()` schreibend,
> `find_operator()`/`find_primary()` rein lesend (in fremden Transaktionen Pflicht),
> `by_object_id()` für «genau diese Gesellschaft», `all_companies()` für den Feed. **Nie**
> `CompanySettings.id == 1` oder ein blosses `.first()` – das wählt ab der zweiten Zeile
> willkürlich; `tests/test_sites.py` erzwingt es. `ENTITY_FIELDS` (je Gesellschaft) vs.
> `PLATFORM_FIELDS` (die eine Website, nur über `/admin/settings`).

> **Datenerfassung – drei Regeln, die keine Modulregeln sind** (PROCESS_CORE §4.4/§4.5/§9.3):
> (1) **Ein Vorgang ist EINE Instanz**, denn der Scan verifiziert das physische Ding – eine
> Einzelinstanz zieht bewusst keine Objektnummer. Charge = 1 Scan, Einzelserialisierung =
> n Scans, **ohne** Abfrage nach der Serialisierung. Ohne Verifikation lehnt
> `process.confirm_step` ab (400) – ein ausgegrautes Feld ist keine Sperre.
> (2) **«Nicht bestanden» rückt nicht vor** und legt **nichts** an: angehalten wird die
> ganze Instanz (eine durchgefallene Stichprobe ist nicht mehr repräsentativ), angeboten
> wird ein ganz gewöhnlicher Auftrag mit vorgewählten Stücken.
> **Der Haltezustand ist dabei eine AUSKUNFT, keine Sperre**: `process.held_units` sagt,
> welche Stücke zuletzt durchgefallen sind – `confirm_step` lehnt eine erneute Erfassung
> **nie** ab, und genau das ist der Ausweg (das nächste Urteil ersetzt das letzte). Eine
> Sperre bräuchte einen Schlüssel, der Schlüssel wäre ein zweiter Weg neben der Erfassung,
> und er müsste entscheiden, wer ihn drehen darf. **Und das Urteil hängt am Stück**: das
> `capture`-Ereignis trägt je Einzelinstanz ihr **eigenes** Ergebnis, nicht das der
> Bestätigung – sonst stünden bei «4 von 5 gut» vier falsche Zeilen im Nachweis.
> (3) **Die Stichprobe** (`domain/sampling.py` = die Regel, `services/sampling.py` = die
> Ziehung) ist **EINE Zahl: der Anteil an der Gesamtmenge** – alle (100 %) · Hälfte ·
> Viertel · frei. Nicht je Instanz: ein Modul sieht die Summe dessen, was davorsteht, und
> «10 % von drei Chargen» ergäbe sonst drei Ziehungen, von denen keine der angezeigten
> Zahl entspricht. Gezogen wird **einmal je Modul**, wenn es erreicht wird (vorher steht
> die Menge nicht fest; und je *Welle* gezogen wäre wieder «je Instanz»), zufällig, über
> den vollen Bestand des Auftrags, und steht als `sample`-Ereignis **eingefroren** im Log.
> Aufgerundet, mindestens eines, höchstens alle. Der ungezogene Rest läuft ohne Erfassung
> durch – sichtbar.
> Alle drei stehen an der EINEN Ausführungsstelle; jedes künftige Modul erbt sie.

> **Beschaffen – das Tor nach draussen** (PROCESS_CORE §9.9, `services/purchase.py`,
> Tabelle `purchases`): drei Stufen (`Anfrage → Bestellung → Wareneingang`), **eine
> Fachzeile je Modul** (partieller Unique-Index auf `step_id` – `instantiate_for_order`
> ist idempotent, zwei gleichzeitige Freigaben sind es nicht).
> **Es erzeugt nichts.** Einzelinstanzen entstehen bei der Freigabe eines
> Erzeugungsauftrags; hier passieren sie nur. Daraus fällt heraus, dass eine **Leistung**
> nie im Bestand steht – ohne ein Feld, das sie ausschliesst.
> **Die Stufen gehören dem Beleg, das Stück bleibt `Im Prozess`.** Ein Bestellzustand an
> der Einzelinstanz wäre ein Zustand, der nichts über das Material aussagt – und den
> Statusliste, FIFO und Bestand beantworten müssten.
> **Eine Handlung ist ein Befehl, kein Feld-Update** (`purchase.apply`, sieben Aktionen –
> `ask`·`quote`·`decline`·`order`·`note`·`revoke`·`clarified`). Ein **Lieferant** trifft
> nur seine eigene Zeile (`_target` liest `actor.object_id`, nicht die Nutzlast), und
> fremde Preise fallen beim **Aufbau der Antwort** weg, nicht in der Oberfläche.
> **Eine Angebotszeile wird durch NEUBAU geändert, nie an Ort** (`_write`): der geladene
> JSONB-Wert darf nicht mutiert werden – sonst sind geladener und aktueller Wert gleich,
> die Spalte fällt aus dem `UPDATE`, und die Offerte ist stillschweigend weg (dieselbe
> Falle wie `units._runs`, Testnotizen #560–#562).
> **Eine Gegenhandlung, die Stufe sagt was sie tut** (`revoke`): vor der Bestellung
> zurückziehen, ab ihr stornieren. Was **Stücke** betrifft, entscheidet ein Mensch – das
> Modul schlägt vor, es legt keinen Auftrag an.
> **Was und wie viel sind keine Eingaben** (`process_lines`/`lines_of`): die Zeilen des
> Belegs sind die Artikel der Einzelinstanzen, die vor dem Modul stehen, und ihre Zahl –
> gruppiert je Artikel, also sind **zwei Artikel zwei Zeilen auf EINEM Beleg**. Mit der
> Bestellung frieren sie in ``ordered_lines`` ein; davor gibt es sie gar nicht. Eine
> getippte Menge oder ein Artikelfeld daneben wären zweite Aussagen über dieselbe Sache.
> **Ohne Lieferfrist keine Offerte**: aus ihr kommt der Liefertermin.
> **Drei Schichten, jede an ihrem Ort**: die **Sache** aus der Artikel-Spezifikation (sie
> reist mit dem Beleg, `services/article_fields` – sie wird nicht ausgewählt), der
> **Auftrag** aus `config.instruction` (Pflicht – «Härten auf 58 HRC» gehört dem Schritt,
> nicht dem Artikel), die **Nummer** an der Angebotszeile bzw. `reference`. Die
> Lieferanten-Artikelnummer reist bewusst **nicht** mit: sie gehört genau einem.
> **Der Einstandspreis braucht genau EINE Zeile** (`_write_landed_cost`) – bei zwei
> Artikeln ist die Bestellsumme eine gemeinsame, und ihre Aufteilung ist eine menschliche
> Entscheidung.
> **Die Lieferanten-Sicht ist EINE Frage** (`purchase.mine`, ``None`` = Personal): woran
> ist dieser Betrachter beteiligt? Feed und Detail lesen dieselbe Antwort; verengt wird
> **in** `orders._to_response` (`_mine_only` blankt `_INTERNAL_FIELDS`), damit kein
> Aufrufer es vergessen kann. Nicht beteiligt → **404**, nicht 403. **Wer nicht den
> Zuschlag hat, sieht ihn auch nicht**: Name, Summe und Sendungsnummer des Gewählten
> fallen für die übrigen Angefragten beim Aufbau der Antwort weg.
> **Was man DARF, sagt der Beleg – nicht die Rolle** (`_can` → `PurchaseEmbed.can`,
> Stufe × Rolle): die Oberfläche rendert eine Aktion genau dann, wenn ihr Verb dort steht,
> und **dieselbe Tabelle weist in `apply` ab** – wäre `can` nur ein Anzeige-Hinweis,
> liefen Knopf und Tür beim nächsten Verb auseinander. Der `receive`-Eintrag (Wareneingang
> über `confirm_step`) steht mit drin: zwei Listen wären zwei Massstäbe. `_only_in` ist
> darin aufgegangen.
> **`_stages` liest die ZEILE, nicht nur ihren Stand**: ein stornierter Beleg behält
> seinen gegangenen Weg (angefragt und bestellt WURDE), keine Stufe ist aktiv, kein Verb
> wird angeboten. Wächter: `tests/test_purchase_module.py`.

> **Aussondern – ein Modul, zwei Ausprägungen** (PROCESS_CORE §9.4/§4.6/§5.2):
> **Verschrotten** (`Verschrottet`, rot, endgültig) und **Sperren** (`Gesperrt`, gelb,
> physisch noch da) tun dasselbe – das Stück verlässt den Auftrag; der Unterschied ist
> ein **Parameter** (`config.mode`), kein zweites Modul. Den Zustand leitet das Modul ab
> (`Module.status_after_for`) – es gibt kein Status-Dropdown.
> **Terminal heisst UNERREICHBAR – überall** (§5.3): ``process.pick_problem`` ist die eine
> Frage «darf ein Auftrag dieses Stück greifen?», und sie steht **vor** der Frage, woher es
> kommt (sie sass einmal nur im ``source is None``-Zweig – eine Regel aus Versehen). Zwei
> Formen derselben Regel: ``pick_problem`` wirft bei der Freigabe, ``unpickable`` sammelt
> für den Entwurf (``orders.validate_draft``) – ein zweiter, milderer Massstab wäre ein
> Knopf, der bereitsteht und dann scheitert. Im Frontend fragt ``isPickable`` dieselbe
> Eigenschaft aus dem **generierten** Katalog; der Abweichungstrigger erscheint dort gar
> nicht erst.
> **«Gibt es einen Weg zurück?» ist eine Eigenschaft des Status** (`Status.terminal`),
> keine Farbfrage: Farbe, Freigabe-Prüfung (`is_selectable`) und Auswahl-Liste folgen
> daraus – und der **Schutz in der Datenbank** (PROCESS_CORE §5.3). Ein
> gesperrtes Stück nimmt ein ganz gewöhnlicher Auftrag auf – **das Greifen IST das
> Aufheben**, es gibt keinen «entsperren»-Endpunkt.
> **Der Grund ist Pflicht – beim MODELLIEREN**, für beide Ausprägungen (`config.reason`).
> Warum ausgesondert wird, ist eine Eigenschaft des Ablaufs und lautet bei jedem Stück
> gleich; am Band wäre es ein Feld, das immer dasselbe aufnimmt. Ohne Grund ist das Modul
> nicht anlegbar – zur Laufzeit erfasst es **nichts** (der Scan ist die Bestätigung), und
> der Grund reist als `ProcessStepResponse.reason` an die Ausführungsstelle.
> **Ein terminales Modul ist ein Ausgang** (`Module.terminal`) – **EINE Eigenschaft, DREI
> Wirkungen**: der Editor bietet dahinter nichts an, die Freigabe weist ein Modul dahinter
> ab (das Netz), und das **Bild endet dort** (`flow.build` hängt kein `end` an; die
> ausgesonderten Stücke stehen auf `edge:exit:done`). Die dritte fehlte – dadurch standen
> Stücke auf einer Kante, die niemand gegangen war, und die Invariantenprüfung meldete es
> zu Recht. Es passiert das Ende-Objekt nicht.
> Damit endet auch eine geplante **Rückführung** – ohne eine Zeile Wartelogik, weil über
> die **offene** Zugehörigkeit gezählt wird. `return_to_order_id` bleibt unangetastet.
> **Kein neuer Auftragsstatus:** wer aussondert, ist seinen **definierten Weg zu Ende
> gegangen** (`Abgeschlossen` – nicht «hat das Ende-Objekt passiert»; ein Ausgang IST ein
> Ende); wem die Stücke dadurch fehlen, dessen Ziel ist unerreichbar (`Abgebrochen`).
> Wächter: `tests/test_disposal_module.py`.
> Die Kettenregel steht in `domain/chain.py` und gilt an **beiden** Definitionsorten
> (Artikel-Vorlage und Auftrag) – vorher nur beim Auftrag, und ein Artikel ist danach
> eingefroren.

> **Das Bild ist eine Ansicht der VERGANGENHEIT – also darf es keine bewegliche Grösse
> lesen** (`services/flow.py`, PROCESS_CORE §8.1a). Eine geschlossene Zeile auf der
> **Achse** (`at is None`) heisst «hier hat *dieser* Auftrag das Stück abgegeben»; was ein
> anderer danach damit tat, ist nicht seine Geschichte. Die Pille liest dort darum
> `_left_with` (den letzten `status_after` aus **seinem** Log) statt `InstanceUnit.status`.
> Auf einer **Ausscherung** (`at` gesetzt) bleibt der heutige Zustand richtig – dort IST
> der Verbleib die Aussage. Vier Fälle (offen/geschlossen × Achse/Ausscherung), eine
> Tabelle in `_rows`, keine Sonderregel.
> Ohne das zeigte ein längst abgeschlossener Auftrag Ereignisse, die nie zu ihm gehörten
> («eines im Prozess, eines verschrottet», wo nichts ausgesondert wurde) – und der Fehler
> sah aus, als käme er aus dem Nichts.
> **Die Invariantenprüfung fragt darum nach dem WIDERSPRUCH**, nicht nach dem Log allein
> (`_verify_history`): ein Schreiber ausserhalb der Prozesslogik hinterlässt gar keinen
> Eintrag – gefunden wird er nur, wenn Log und Zeile verglichen werden (§5.3).

## Eine neue Tabelle ist erst fertig, wenn sie ALLE Spalten des Modells anlegt

Drei Netze, drei verschiedene Fänge: die **Migration** ist die Wahrheit · `create_all` im
Lifespan legt eine fehlende **Tabelle** an, **nie** eine fehlende Spalte · `main.
_COLUMN_SAFETY_NET` zieht fehlende **Spalten** nach. Dazwischen bleibt genau eine Lücke –
eine Tabelle, die es gibt, der aber eine Spalte des Modells fehlt.

Genau dort ist `purchases.is_active` gelandet (Migration 114): das Modell erbt sie von
`Base`, die Migration nannte sie nicht. **Lokal grün**, weil `create_all` die Tabelle dort
einmal vollständig angelegt hatte; gegen ein Schema, das nur aus den Migrationen kommt,
scheiterte danach **jeder** Lesezugriff auf den Beleg (140 Prüfungen).

- **Neue Tabelle:** die Migration muss den **vollständigen** Spaltensatz des Modells
  anlegen – inklusive der geerbten (`is_active`, `created_at`, `updated_at`).
- **Neue Spalte auf bestehender Tabelle:** Migration **und** `_COLUMN_SAFETY_NET`
  (die Lehre aus 090 – beim Ausfall zählt nur der zweite Weg).
- **Geprüft, nicht geglaubt:** `tests/test_schema_is_built_by_the_migrations.py` baut eine
  Wegwerf-Datenbank, fährt `alembic upgrade head` und vergleicht Modell ↔ Schema für jede
  Tabelle.
- **Und lokal testen wie die CI:** einmal gegen die gewachsene Datenbank, einmal gegen ein
  frisch aus den Migrationen gebautes Schema. Nur die zweite ist die, die deployt wird.

## Konventionen
- Soft-Delete überall: is_active=false, KEIN hard delete
- UTC Timestamps überall
- Pydantic v2: `model_validate()`, `model_dump()`, `ConfigDict(from_attributes=True)`
- SQLAlchemy 2.0: `Mapped[T]`, `mapped_column()`
- Fehler: `raise HTTPException(status_code=..., detail="...")`
- Audit-Log bei jedem Update schreiben

## Env-Variablen
Siehe /.env.example für vollständige Liste.
Pflicht lokal: DATABASE_URL, FIREBASE_PROJECT_ID
