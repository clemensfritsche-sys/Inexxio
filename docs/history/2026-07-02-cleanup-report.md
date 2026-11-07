# CLEANUP REPORT – 2026-07-02

Autonomer Cleanup-/Bugfix-/Optimierungs-Durchgang über die gesamte Inexxio-Codebase
(Backend ~13'100 LOC Python, Frontend ~23'500 LOC TS/TSX). Keine Schema-Änderungen.
Verifiziert: **161/161 Backend-Tests grün**, `tsc --noEmit` grün, ESLint grün,
Production-Build grün, OpenAPI/Typen ohne Drift, Batch-Helfer per Äquivalenz-Skript
gegen die Einzel-Helfer geprüft.

## Architektur-Befund (Kurzfassung)

Die 5 Primitive sind konsistent umgesetzt:
- **Entity** = universelle 9-stellige Objektnummer (`object_id_seq`) über alle Objekttabellen.
- **Event** = `events`-Outbox (`services/events.emit`) mit **deklarierter** Bestands-Polarität
  aus der REA-Registry (`domain/event_types.py`) – eine Quelle der Wahrheit je Schritttyp.
- **Relation** = `instance_order_links` (Historie), `parent_order_id`+`reason` (Unter-Aufträge),
  `replaced_by_id` (Nachfolge), `reservations` (mengengenau), `subject_of_order_id`.
- **Projection** = Schritt-/Auftragsstatus wird IMMER abgeleitet, nie gespeichert
  (`process.build_order_steps`, `blocked` aus Bestand, Badge = Projektion quality×disposition).
- **Process Definition** = `article_process_steps` inline am Artikel/Auftrag (kein Prozess-Objekt).

«One ledger, N lenses» wird eingehalten; nennenswerte Drift wurde nicht gefunden. Die
Schrittstatus werden aus Fachtabellen (nicht aus Events) projiziert – bewusst (Outbox-Muster).

## 1. SUMMARY

**Backend**
- 14 tote Imports entfernt (ruff, u. a. `auth.py`, `orders.py`, `shop.py`, `resource.py`);
  `shop.py`: doppelter lokaler `Order`-Import (F811) aufgelöst.
- `schemas/common.py` gelöscht (PaginatedResponse/ErrorResponse – nirgends referenziert).
- `services/reservation.py`: das 4-fach duplizierte Zurückschreiben der Reservierungs-Map
  (Map + Summe + Einzel-Zeiger) in EINEN Helfer `_write()` konsolidiert (verhaltensidentisch).
- **N+1 behoben (grösster Performance-Gewinn):** neue Batch-Helfer
  `locations.location_labels()` / `physical_location_labels()` (1 Query je Standort-Typ bzw.
  je Kettentiefe statt 1–2 Queries **je Zeile**). Eingesetzt im Instanz-Feed
  (`routers/instances._denorm`: vorher ~100–200 Queries pro Feed-Seite à 100 Instanzen),
  im Artikel-Bestand (`routers/articles.list_article_instances`) und im Auftrags-Detail
  (`services/orders.to_order_response`).
- **N+1 behoben:** `sales.list_customer_orders` lädt Auftrag+Artikel jetzt batch
  (vorher 2 Queries je Verkaufsbeleg – betrifft «Meine Bestellungen» + ERP-Reiter «Bestellungen»).

**Frontend**
- Tote Datei `src/store/auth.ts` gelöscht → Dependency **`zustand` komplett entfernt**.
- Tote Utils entfernt (`formatDateTime`, `formatCurrency`, `formatObjectId`, `relativeTime`,
  `getInitials` in `lib/utils.ts`), tote Exporte (`useRequireAuth`, `stepLabel`,
  `storageTypeLabel`, vier `*_STATUS_ORDER`-Konstanten), tote API-Methoden
  (`acceptTerms`, `getErpRecord`, `replaceOrder` – vgl. Deferred #2/#3).
- Bewusst NICHT konsolidiert: die zwei `useAutosave`-Hooks (Konto vs. ERP) haben absichtlich
  unterschiedliche Semantik (Wert+Status-Pille vs. Signatur+Flush+Rahmen-Flash) – eine
  erzwungene Abstraktion wäre «clever statt einfach».

## 2. BUGS FIXED

1. **`frontend/src/lib/cart-context.tsx` – Warenkorb-`add()` konnte die Abo-Ablehnung verlieren.**
   Das Resultat wurde INNERHALB des `setItems`-Updaters gesetzt und danach zurückgegeben; React
   garantiert die synchrone Ausführung des Updaters nicht (nur die Eager-Evaluation-Optimierung
   liess es meist funktionieren). Bei ausstehenden Updates hätte «Abos werden einzeln gekauft»
   still gefehlt und ein Abo wäre kommentarlos nicht im Korb gelandet. → Prüfung läuft jetzt vor
   `setItems` gegen den aktuellen State (`// FIX:`-Kommentar an Ort).
2. **`frontend/src/app/(erp)/erp/page.tsx` – NaN-Sortierkomparator im Feed.** Fallback
   `-Infinity` ergab `NaN`, sobald zwei Zeilen ohne Objektnummer verglichen wurden
   (−∞ − −∞ = NaN) – ein NaN-Komparator verletzt die Sortier-Ordnung (undefinierte
   Reihenfolge). → Fallback `0` (`// FIX:`-Kommentar an Ort).

Weitere echte Laufzeit-Bugs wurden trotz gezielter Suche (Kern-Services, Retouren-Pfad,
Reservierung, Deaktivierungs-Kaskade, Auth-Guards aller Router) nicht gefunden – die Codebase
ist durch die jüngsten e2e-getesteten Umbauten in gutem Zustand.

## 3. DEFERRED ITEMS (bewusst nicht angefasst)

1. **DB-Indizes** (Regel «kein Schema anfassen»): lohnend wären Indizes auf
   `instances(article_id, is_active, quality, disposition)` (FIFO/Bestand),
   `instances(subject_of_order_id)`, `instance_order_links(order_id)`,
   `orders(parent_order_id, reason, status)`, `article_process_steps(order_id/article_id, is_active)`,
   `audit_log(object_id, table_name)`. Bei ~10 Nutzern/1'000 Artikeln unkritisch, vor
   Phase-2-Wachstum per Alembic-Migration nachziehen.
2. **AGB-Akzeptanz ist im Frontend nicht verdrahtet**: Backend-Endpoint
   `POST /auth/terms-accept` existiert (DSGVO/OR-relevant: Zeitstempel+Version), aber kein
   Frontend-Aufruf (die tote Methode `acceptTerms` wurde entfernt). Entscheidung nötig, WO die
   Akzeptanz erzwungen wird (Login? Checkout?) – rechtlich relevant, gehört vor den Live-Shop.
3. **`POST /orders/{id}/replace` (Auftrag ersetzen) ist im UI nicht erreichbar** (tote
   FE-Methode entfernt, Backend-Endpoint + Logik vorhanden). Entweder UI-Knopf nachrüsten
   oder Endpoint entfernen.
4. **Bestell-Verlauf bei Mehrpositionen-Beschaffung vermischt**: `_purchase_history` filtert
   das Audit-Log nur nach `object_id` (=Auftragsnummer) + Tabelle – bei MEHREREN Bestellungen
   unter einem Auftrag zeigt jeder Stepper die Statuswechsel ALLER Positionen. Fix braucht
   eine PO-Kennung im Audit-Log (Datenmodell-Entscheid).
5. **`google_maps_api_key` in `GET /admin/settings/public`**: für Maps-JS nötig und als
   Client-Key konzipiert – im GCP-Console per HTTP-Referrer auf die eigenen Domains
   einschränken (Konfiguration, kein Code).
6. **`GET /orders` & `GET /instances` erlauben `limit=0` = unbegrenzt** (bewusste
   Escape-Hatch; das Frontend paginiert Instanzen mit 100). Bei Wachstum serverseitig ein
   Default-Limit erzwingen.
7. **B904/B905 (ruff)**: Exception-Chaining (`raise … from e`) und `zip(strict=)` – reine
   Hygiene, teils verhaltensändernd (strict wirft bei Längen-Mismatch); nicht ohne
   Einzelabwägung ändern.

## 4. RECOMMENDATIONS (priorisiert)

1. Indizes aus Deferred #1 als eigene Alembic-Migration (15 Min Aufwand, grösster Zukunfts-Hebel).
2. AGB-Akzeptanz-Flow entscheiden + verdrahten (rechtlich, vor Live-Gang des Shops).
3. `ruff` (F-Regeln) als CI-Gate neben ESLint/pytest aufnehmen – hält tote Imports dauerhaft draussen.
4. Rate-Limiting/Brute-Force-Schutz liegt derzeit allein bei Firebase Auth – für öffentliche
   Endpoints (`/contact`, `/shop/checkout`) ein einfaches Limit (z. B. slowapi) erwägen.
5. `fifo_candidates` lädt alle passenden Instanzen und sortiert in Python – bei grossen
   Chargenbeständen auf SQL-Sortierung + Limit umstellen (zusammen mit Indizes aus #1).

## Verifikation (Phase 5)

Automatisiert: `pytest` 161/161 grün · `tsc --noEmit` grün · ESLint grün · `next build` grün ·
OpenAPI→TS-Typen ohne Drift · Äquivalenz-Skript Batch- vs. Einzel-Label-Helfer grün.

Manuell nachgezeichnete kritische Workflows (alle intakt):
1. **Artikel anlegen → Prozess definieren → freigeben** – Freigabe-Gate (Prozess-Pflicht) unberührt.
2. **Produktionsauftrag**: anlegen → freigeben (Instanzen entstehen) → Schritte → auto-completed –
   Reservierungs-Refactor verhaltensidentisch (`_write`), Abschluss-Pfad unberührt.
3. **Shop-Kauf**: Warenkorb → eingebettete Kasse → Webhook → Auftrag – `add()`-Fix ändert den
   Happy Path nicht; `list_customer_orders`-Batching liefert identische Zeilen.
4. **Verkauf ab Lager + Pflicht-Versand** – Allokation/`sell_order_subjects`/Movement unberührt.
5. **Retoure/Erstattung (ERP + Kundenportal)** – Erkennung verkaufter Instanzen, Gutschrift,
   Stripe-Refund, Rückgabe-Bewegung unberührt.
