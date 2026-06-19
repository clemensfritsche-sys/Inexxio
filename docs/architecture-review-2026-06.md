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

## Empfehlungen für später (größere Eingriffe — bitte Rücksprache)

1. **Schema-Management vereinheitlichen.** Prod erzeugt das Schema via
   `create_all()` + handgepflegte Safety-Nets (`_COLUMN_SAFETY_NET`,
   `_DROP_COLUMN_SAFETY_NET`, `_INDEX_SAFETY_NET`, `_DATA_FIXES`). Das dupliziert die
   Alembic-Migrationen und driftet leicht. Empfehlung: beim Deploy `alembic upgrade
   head` ausführen und die Safety-Nets auf ein minimales Notfall-Fallback reduzieren.

2. **Objektnummern über eine DB-Sequence.** `max(object_id)+1` ist unter Last
   **nicht race-sicher** (zwei gleichzeitige Anlagen → gleiche Nummer → Unique-
   Verletzung). Empfehlung: eine Postgres-`SEQUENCE` (Start 100'000'001), die alle
   Objekttypen teilen – atomar und ohne Scan. (Der Query-Aufwand ist bereits reduziert.)

3. **Feed-Strategie / Over-Fetching.** `GET /orders` liefert für **jeden** Auftrag den
   vollen Prozess-Embed (FIFO-Vorschau, Stichproben, Historie). Der ERP-Feed lädt
   zudem alle Objekttypen gleichzeitig und ungepaged. Empfehlung: schlanke Listen-
   Responses + Detail-on-Demand (`GET /{id}`) + Pagination/Server-Filter.

4. **KI-Readiness ausbauen.** Datenmodell (universelle Objektnummern,
   Instanz-Genealogie, Audit-Log, JSONB-Flexfelder) ist analyse-/agentenfreundlich.
   Für native Automatisierung empfohlen: (a) ein **Domain-Event-/Outbox-Strom**
   (sauberer als das Audit-Log) für Push an KI-Agenten/Webhooks, (b) Read-Replica
   bzw. materialisierte Sichten für Analytik, (c) die bestehende REST-API bleibt
   direkt agenten-konsumierbar.

## Kleinere offene Punkte (geringe Priorität)
- `orders.title` wird nie gesetzt (Auftrag heißt starr «Auftrag») – Kandidat zum
  Entfernen, betrifft aber die API-Oberfläche → in einem Schema-Review bündeln.
- Rest-N+1 in `to_order_response` (Standort-Label je Instanz, Namen je Schritt) –
  klein; bei Bedarf per Batch-Lookup auflösbar.
- `GET /erp/records` vergibt fehlende Objektnummern (Schreib-Seiteneffekt auf GET).
