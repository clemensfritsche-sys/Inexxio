# Architektur- & Code-Review — Juni 2026

Ganzheitliches Review der ERP-Software (Geschäftslogik, Datenbank, Codebase) vor
dem Bau weiterer Features. Bewertung nach Architektur, Skalierbarkeit, Performance
und KI-Readiness, plus Bereinigung technischer Altlasten.

## Gesamteinschätzung
Solides, pragmatisch geschnittenes Fundament: saubere Schichtung
(Router → Service → Model/Schema), konsequente Soft-Deletes, UTC, Audit-Log,
universeller Nummernkreis und eine generische, datengetriebene Prozess-Engine.
Kein zyklischer Import, keine offensichtlichen Anti-Patterns in der Schichtung.
Die größten Hebel liegen in **DB-Indizierung**, **Objektnummern-Vergabe** und der
**Antwort-/Feed-Strategie** (Over-Fetching).

## In diesem Durchgang behoben (sicher, ohne API-Änderung)

### Performance
- **Objektnummern in EINER Query**: `current_max_object_id` ermittelte das Maximum
  bisher mit **6 Einzel-Queries** (eine je Objekttabelle) – jetzt EIN `UNION ALL`.
- **Block-Vergabe bei Massenanlage**: Bei der Auftragsfreigabe wurde
  `next_object_id` **in der Schleife** je Instanz aufgerufen (6 Queries × N Stück).
  Neu vergibt `next_object_ids(n)` einen ganzen Block in einer Query → eine
  Freigabe über 100 Einzelteile geht von ~600 auf 1 Nummern-Query zurück.
- **Prozess-Engine ohne O(K²)**: `order_step_infos`/`to_order_response` lösten die
  Fachzeilen **je Schritt erneut** auf (Definitionen + Fachzeilen mehrfach geladen).
  Neu lädt `build_order_steps` Definitionen und Fachzeilen **je einmal** und gibt die
  aufgelöste Fachzeile gleich mit – der Embed-Aufbau lädt nichts nach.

### Fehlende Indizes (auf wachsenden, häufig gefilterten Spalten)
- `audit_log.object_id` + `audit_log.table_name` — wird je Auftrag im Feed gelesen
  (`_purchase_history`) und im Verwendungsnachweis; ohne Index Seq-Scan auf der am
  schnellsten wachsenden Tabelle.
- `claims.order_object_id` — Idempotenz-Prüfung der Auto-Reklamation.
- `instances.location_id` — Standort-/Genealogie-Abfragen (Verwendungsnachweis).

Indizes greifen für neue DBs über die Modelle (`index=True`) und für bestehende DBs
idempotent über das Safety-Net (`_INDEX_SAFETY_NET` in `main.py`) sowie Migration `020`.

### Toter Code / obsolete Felder entfernt
- `process.is_step_active()` — durch `resolve_exec_step` ersetzt, nirgends mehr genutzt.
- DB-Spalte `inspections.values` — Altformat, durch `inspections.samples` (je
  Stichprobe) abgelöst; wurde nirgends mehr gelesen/geschrieben. Entfernt aus Modell,
  Migration `020` und Drop-Safety-Net.

## Die vier größeren Maßnahmen — Status

1. **Objektnummern über eine DB-Sequence — ✅ UMGESETZT.** `max(object_id)+1` war
   unter Last nicht race-sicher. Neu: gemeinsame Postgres-`SEQUENCE` `object_id_seq`
   (atomar, ohne Scan), beim Start rewind-sicher ausgerichtet + Migration `021`.

2. **Schema via Alembic in Prod — ✅ IM KERN BEREITS VORHANDEN.** `start.sh` führt
   `alembic upgrade head` vor uvicorn aus; die Lifespan-Safety-Nets sind das
   *Fallback* bei Migrationsfehlern. Migrationen sind damit autoritativ. Empfehlung:
   die Safety-Nets bewusst als Resilienz-Schicht behalten (nicht entfernen).

3. **Feed-Strategie / Over-Fetching — ✅ UMGESETZT (Kern).** `GET /orders` liefert
   jetzt eine schlanke `OrderSummary` (ohne Embeds; Artikel-Infos + Beschaffungs-
   status **batch**-geladen) und ist server-seitig paginierbar (`limit`/`offset`).
   Das Frontend lädt den vollen Auftrag **erst bei Auswahl** (`getOrder(id)`,
   Detail-on-Demand) – der Feed baut keine Prozess-Embeds mehr. Offen/empfohlen als
   Folgeschritt: Infinite-Scroll/serverseitige Paginierung auch im gemischten
   Frontend-Feed (derzeit lädt er die schlanken Listen vollständig).

4. **KI-Event-/Outbox-Strom — ✅ UMGESETZT (Basis).** Neue append-only Tabelle
   `events` (transaktionaler Outbox), Emit an den Lebenszyklus-Punkten
   (order.released/completed, purchase.*, inspection.*, movement/resource.recorded,
   claim.opened, instances.created) und Konsum-API `GET /api/v1/events?after_id=…`
   (lückenloser Vorwärts-Cursor für Agenten). Offen/empfohlen: aktiver Relay/Webhook-
   Push + Read-Replica/materialisierte Sichten für Analytik.

## Kleinere offene Punkte (geringe Priorität)
- `orders.title` wird nie gesetzt (Auftrag heißt starr «Auftrag») – Kandidat zum
  Entfernen, betrifft aber die API-Oberfläche → in einem Schema-Review bündeln.
- Rest-N+1 in `to_order_response` (Standort-Label je Instanz, Namen je Schritt) –
  klein; bei Bedarf per Batch-Lookup auflösbar.
- `GET /erp/records` vergibt fehlende Objektnummern (Schreib-Seiteneffekt auf GET).
