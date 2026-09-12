# Code-Cleanup & Architektur-Härtung — Analyse- und Befund-Bericht (Juli 2026)

Grundlage: `origin/develop` Stand 2026-07-07 (`78d5ec3`). Analysiert wurden Backend
(FastAPI/SQLAlchemy, 136 Dateien), Frontend (Next.js 14), Alembic-Migrationen (59,
lineare Kette, ein Head) und Doku. Backend-Testsuite grün (180 Tests), Frontend-
Typecheck sauber. Dieser Bericht ist das Phase-1-Deliverable des Cleanup-Auftrags;
die Umsetzung (Phase 2/3) referenziert die Befund-Nummern.

---

## 1. Architektur-Verständnis (Kurzfassung je Modul)

- **Kernmodell Auftrag → Prozess → Instanz.** Ein Artikel trägt Spezifikation + genau
  einen Prozess (geordnete `article_process_steps`, kein Prozess-Objekt). Ein Auftrag
  fährt entweder den Artikel-Prozess (produce, erzeugt Instanzen bei Freigabe) oder
  eigene Schritte (stock/instance, wirkt auf Bestand). Der Schritt-Status wird aus der
  jeweiligen **Fachtabelle abgeleitet** (`process._FACT_MODEL`), keine
  Orchestrierungstabelle; `recompute_completion` schliesst automatisch ab.
- **Event-Registry (`domain/event_types.py`).** Deklarative Quelle der Wahrheit je
  Schritttyp: Label, Bestands-Polarität (increase/decrease/move/neutral), Subjekt-Rolle
  (produce/stock/instance), Fachtabelle. `derive_subject_mode` +
  `aggregate_stock_effect` leiten Subjektart/Lagerwirkung ab statt sie zu raten.
- **Zwei Instanz-Achsen.** `quality` (pending/passed/failed) × `disposition`
  (in_process/in_stock/consumed/sold/scrapped). Verbrauchbar = passed ∧ in_stock
  (`inventory.in_stock_clauses`, die EINE Helper-Stelle). Mengengenaue Reservierung
  ohne Instanz-Teilung (`instances.reservations` JSONB-Map, denormalisierte Summe).
- **Unter-Aufträge** (`parent_order_id` + `reason`): deviation (pausiert Eltern),
  supply (blockiert nur Schritt, Pegging bei Abschluss), return (festes Subjekt,
  Gutschrift), replenishment (eigenständig, Meldebestand). Ein Mechanismus, vier Gründe.
- **Unterdeckung**: EINE Formel `Soll − Gesichert` (`process._subject_shortfalls`),
  Schritt wird abgeleitet `blocked`; Deckung über Nachschub (`supply.ensure_supply`,
  rekursiv/idempotent/zyklensicher) oder Lager (`recovery.cover_from_stock`).
- **Verkauf/Shop**: Verkaufs-Ebene lebt am Artikel (Preise 1:n, Pipeline
  `pricing.py` Basis-CHF → Zone → Rabatt → gepinnte Fremdwährung → MWST). Kauf =
  stock/FIFO-Auftrag mit `sale`+`movement`; `CheckoutIntent` erzeugt Aufträge erst
  bei bestätigter Zahlung; Stripe (embedded) ist Quelle der Wahrheit, Webhook spiegelt.
  Retoure = normaler Auftrag mit verkauften Instanzen als Subjekt, `sale` im
  Kredit-Modus (`kind='credit'`) + Stripe-Refund.
- **KI-Layer (ADR 004)**: Gateway (Vertex/Anthropic, ohne Config inaktiv statt kaputt),
  KI-Identität als echter Principal, rechte-gescopte Tools (Scoping = Authz),
  `AiAction`-Vorschläge für Kritisches. Dokument-Modul: Upload → KI-Extraktion →
  Vorschlag → menschliche Bestätigung materialisiert `DocumentFile` + n:m-Links.
- **Infra**: Objektnummern über Postgres-Sequence (race-sicher), Alembic autoritativ
  (`start.sh`), Lifespan-Safety-Nets als Fallback (Spalten/Indizes/Datenfixes),
  Domain-Event-Outbox (`events`) mit Cursor-API.

Gesamteinschätzung: Das Fundament ist konsequent und für die Grösse bemerkenswert
konsistent — abgeleitete Zustände statt Flags, eine Formel statt Sonderpfaden,
deklarierte Semantik statt if-Ketten. Die Schwachstellen liegen bei **Nebenläufigkeit**
(Check-then-Act ohne Locks), einem **echten Show-Stopper im Meldebestand-Feature**,
einigen fehlenden **Indizes** und der noch unvollständigen **Design-System-Migration**.

---

## 2. Altlasten-Inventar

### 2.1 Bestätigt tot (wird entfernt)

| # | Fundstelle | Befund |
|---|---|---|
| A1 | `frontend/messages/de.json` + `en.json` | **Komplett totes i18n**: `next-intl` ist NICHT installiert (kein Eintrag in `package.json`, kein `useTranslations` im Code). Das Glossar enthält zudem Altbegriffe entfernter Konzepte (`complaint`, `production_order`, `work_plan`, `bom`, `capa`). `frontend/CLAUDE.md` behauptet ausserdem next-intl + Zustand als Tech-Stack — beides nicht installiert. |
| A2 | `frontend/src/lib/api.ts:463` | `getInstanceDocuments()` wird nirgends aufgerufen (toter Wrapper). |
| A3 | Dev-DB (kein Code) | **F-Rollback-Reste**: Die per Notfall-Revert (#85) entfernte Migration `059_location_as_instance` lief auf der Dev-DB vermutlich bereits — ihre Spalten (`articles.is_location/max_load_kg`, `instances.is_location/note/latitude/longitude/address_*`) liegen dort verwaist. Zusätzlich wurde die Revisions-ID `059` danach für `059_document_files` **wiederverwendet** → auf der Dev-DB gilt 059 als „applied", die Dokument-Tabellen kamen nur über das `create_all()`-Safety-Net. Aufräumen: idempotente Drop-Migration `060` + Eintrag im Drop-Safety-Net. |
| A4 | `backend/app/models/order.py:82` | Kommentar `reason: deviation \| supply` unterschlägt `return`/`replenishment` (Doku-Drift, siehe auch Bug B1). |

### 2.2 Backend-Inventar (Detail, alle grep-verifiziert)

| # | Fundstelle | Befund | Entscheid |
|---|---|---|---|
| A5 | `models/order.py:46` | `Order.stripe_checkout_session_id`: 0 Referenzen (nur Modell + Safety-Net). Der Checkout läuft über `CheckoutIntent.stripe_session_id`; die Spalte wurde nie befüllt. | Spalte entfernen ✅ |
| A6 | `models/sale.py:80` | `Sale.fx_rate`: 0 Referenzen — der Preis-Snapshot setzt `base_amount_chf` + `fx_date`, nie `fx_rate`. | Spalte entfernen ✅ |
| A7 | `models/notification.py` | **`Notification`-Modell/Tabelle komplett tot**: kein Router/Service/Schema erzeugt oder liest je eine Notification (nur Re-Export + Smoke-Assertion). Die Benachrichtigungs-*Präferenzen* am `UserProfile` sind davon unabhängig und bleiben. | Modell + Tabelle entfernen ✅ |
| A8 | `services/ai/identity.py:62` | `is_ai_user()` wird nirgends aufgerufen. | entfernen ✅ |
| A9 | `routers/sales.py:94` | `GET …/sales/audience` redundant — die Zielgruppe kommt eingebettet im Sales-Profil; FE nutzt nur POST/DELETE. | entfernen ✅ |
| A10 | `routers/shop.py:149` | `GET /shop/session/{session_id}` ohne jeden Aufrufer — die eingebettete Kasse schliesst inline ab (`redirect_on_completion='never'`), eine `/shop/success`-Seite existiert nicht (CLAUDE.md-Doku veraltet). | entfernen ✅ |
| A11 | `services/sales.py:371` | Unerreichbarer `unlisted`-Fallback (Sichtbarkeit ist per Schema auf public/private beschränkt); Docstring `models/article.py:87` nennt `unlisted` noch. | Zweig + Doku bereinigen ✅ |
| A12 | Migrationen | **PR-#90-Spalten fehlen in Alembic**: `article_process_steps.require_signature/signer_ids/require_photo/photo_instruction` + `inspections.signature_url/signed_by/signed_at/photo_url` existieren nur im Runtime-Safety-Net — Alembic ist nicht mehr Schema-SSOT. | in Migration 060 nachziehen ✅ |
| A13 | `routers/orders.py:520` | `POST /orders/{id}/replace` hat keinen FE-Aufrufer, ist aber **bewusste, getestete** Ersetzen-Trias (Artikel/Auftrag/Lagerplatz, `test_deactivation_replace_wired`). | **belassen** (fehlender FE-Knopf, kein Alt-Konzept) |
| A14 | `models/fx_rate.py:27` | `FxRate.fetched_at` write-only. | belassen (Audit-Spalte auf unveränderlicher Kurstabelle) |
| A15 | `routers/events.py` | `GET /api/v1/events` ohne FE-Aufruf — by design (externer KI-/Automatisierungs-Konsument). | belassen |

### 2.3 Explizit geprüft und SAUBER (keine Reste)

- `Claim`-Typ: 0 Treffer im aktiven Code (nur historische Migrationen).
- Prozess-Objekt (`processes`, `article_process_links`, `process_id`,
  `subject_instance_id`, `orders.mode`): 0 Treffer im aktiven Code.
- `consume`/`tool` als Schritttyp: nur noch als Zeilen-`mode` (legitim).
- `orders.subject_source` / `fulfilled_by_order_id`: entfernt, Drop-Safety-Net vorhanden.
- Frontend: keine ungenutzten Komponenten, kein auskommentierter Code, **0 `any`**.

---

## 3. Wording-Drift-Register

Kanonische Begriffe und abweichende Fundstellen. Legende: [UI] = sichtbarer String
(gefahrlos), [K] = Kommentar (gefahrlos), [ID] = Code-Identifier (API-Vertrag, nur
mit Freigabe umbenennen).

| Kanonisch | Drift | Fundstellen | Massnahme |
|---|---|---|---|
| **Spezifikation** (Artikel-Reiter, früher «Stammdaten») | Sektions-Titel «Stammdaten» im Spezifikation-Reiter | `article-detail.tsx:367,772` [UI]; KI-Strings `ai/registry.py:68`, `ai/tools.py:820` [UI] | umbenennen ✅ |
| **Instanz** (quality+disposition) | Kommentar «QC-Status» (Feld existiert seit Migr. 030 nicht mehr) | `order-instances.tsx:10` [K] | korrigieren ✅ |
| **Charge** (Anzeige für batch) | englisches Label «Batch» | `lib/article.ts:24`, `article-detail.tsx:575` [UI] | «Charge» ✅ |
| **Instanz/Einzelteil** | englisches «Unit …» als Instanz-Label | `inspection-panel.tsx:107` [UI] | eindeutschen ✅ |
| **Lagerplatz/Standort** | drittes Synonym «Lagerort» | `process-steps.tsx:485`, `purchase-step-panel.tsx:300` [UI] | vereinheitlichen ✅ |
| **Abweichung** (Claim entfernt) | totes Glossar mit `complaint` u. a. | `messages/de.json:184` | fällt mit A1 weg ✅ |
| **resource** (Schritttyp) | — | sauber (consume/tool nur als Zeilen-Modus) | — |
| **Prozess** (kein Objekt) | — | sauber | — |
| «Bestellung» | Doppelbelegung: purchase_order UND Kunden-Shop-Bestellung («Meine Bestellungen») | shop/checkout, api.ts [UI/K] | **bewusst belassen** — Standard-Shop-Wording für Kunden; im ERP heisst das Objekt konsequent «Auftrag» |
| Marken-Doku | `docs/design-system/reference/inexxio-design.SKILL.md` beschreibt eine «microliving brand» (Template-Rest des Design-Exports) | Referenz-Doku | Hinweis ergänzt, Referenz bleibt read-only |

Backend-Kommentare mit «Stammdaten» (models/schemas) bleiben unangetastet — CLAUDE.md
verwendet «Artikel-Stammdaten» teils selbst; nur die nutzer-sichtbaren Stellen und der
Artikel-Reiter werden kanonisiert (keine halben Identifier-Umbenennungen).

---

## 4. Bug-Liste (priorisiert)

| # | Schwere | Befund | Repro/Auswirkung | Fix |
|---|---|---|---|---|
| B1 | **kritisch** | `orders.reason` ist `VARCHAR(12)` (Modell + Migration 044 + Safety-Net), aber die Auto-Nachbestellung schreibt `reason='replenishment'` (**13 Zeichen**) → `StringDataRightTruncation` bei JEDER Meldebestand-Nachbestellung. Feature E (Meldebestand) ist auf develop faktisch kaputt; Tests (SQLite, keine Längen-Prüfung) sahen es nicht. | Artikel mit `safety_stock` unterschreiten → Sweep/Verschrottung → 500 | Spalte auf `VARCHAR(20)` (Migration 060 + Modell + Safety-Net) ✅ |
| B2 | **kritisch** | Webhook-Doppelverarbeitung: `sales.fulfill_intent` prüft `intent.status=='completed'` ohne Row-Lock. Stripe liefert `checkout.session.completed` UND `async_payment_succeeded`, plus Retries → zwei parallele Zustellungen erzeugen **doppelte Aufträge + doppelt bezahlte Belege** (make-Positionen). | Zwei gleichzeitige Webhook-Zustellungen derselben Zahlung | `with_for_update` auf den CheckoutIntent beim Auflösen ✅ |
| B3 | **kritisch** | Überverkauf-Race: FIFO-Zuteilung (`inventory.fifo_candidates` → reserve) ist Check-then-Act ohne Lock. Zwei gleichzeitige Checkouts auf das letzte Stück reservieren beide → `reserved_quantity > quantity`, dieselbe Ware doppelt verkauft. Gleiches Muster bei ERP-Freigabe/`recovery`. | 2× `POST /shop/checkout` auf letztes Stück | `with_for_update` auf die Kandidaten-Query ✅ |
| B4 | hoch | `supply.ensure_supply` + `replenishment.check_article`: Existenz-Check („läuft schon ein Nachschub?") ohne Lock/Unique-Constraint → paralleler Webhook + ERP-Klick bzw. Doppel-Sweep erzeugen **doppelten Nachschub**. | parallele Requests | Eltern-Auftrag bzw. Artikel-Zeile `with_for_update` sperren ✅ |
| B5 | hoch | Blockierender synchroner FX-HTTP-Abruf (`fx.py`, timeout 8 s) im `async`-Handler der **öffentlichen** Shop-Endpunkte → blockiert den ganzen Event-Loop (DoS-Fläche ohne Auth). | Erster Fremdwährungs-Abruf des Tages bei langsamer FX-Quelle | Shop-Read-Endpunkte auf `def` (Threadpool) ✅ |
| B6 | hoch | Versteckte `db.commit()` mitten in Leseoperationen: `pricing._pinned_net` und `fx._persist` committen während `price_view_for` — innerhalb einer mehrschrittigen Schreiboperation committet das halbfertige Zustände vorzeitig. | Fremdwährungspreis während `release_order` | **Vorschlag** (Geld-Pfad, braucht Freigabe): Persistenz in eigener Session |
| B7 | mittel | Fehlende Indizes: `instances.reservations` (JSONB, `has_key` in 3 Hot-Paths → Full-Scan), `sales.customer_id`, `orders.recurring_parent_id`, `purchase_orders.supplier_id` | wachsender Bestand → Seq-Scans | GIN- + B-Tree-Indizes (Migration 060 + Safety-Net) ✅ |
| B8 | mittel | Optimistic Locking (`lifecycle.ensure_version`) nur an 2 Endpunkten und nur opt-in — CLAUDE.md verlangt es «vor jedem Update». | Lost Update bei parallelem Editieren | **Vorschlag** (breite API-Änderung, braucht Freigabe) |
| B9 | mittel | `HTTPException(detail="Freitext")` durchgängig statt `{error, code, details}`-Konvention. | Frontend/KI können Fehler nicht typisiert behandeln | **Vorschlag** (API-Vertrag, braucht Freigabe) |
| B10 | mittel | N+1: `list_customer_orders` → `return_status` feuert 2 Queries je Bestellung im Rückgabefenster. | «Meine Bestellungen» bei vielen Bestellungen | begrenzt; Batch-Lookup als Folgeschritt |
| B11 | niedrig | `GET /erp/articles`, `/erp/records`, `/admin/users` ohne Pagination; GET-Handler mit Schreib-Seiteneffekt (`_assign_object_ids`, `_ensure_step_facts`). | bei 1'000 Artikeln ok, wächst | dokumentiert, Folgeschritt |
| B12 | niedrig | Funktionen > 80 Zeilen: `to_order_response` (~143), `update_order` (~124) u. a. | Wartbarkeit | beim nächsten fachlichen Umbau aufteilen |

Explizit geprüft, KEIN Befund: Objektnummern-Sequence (race-sicher), Stripe-Webhook-
Signaturprüfung (scheitert hart ohne Secret), Decimal-Durchgängigkeit der Preis-/
MWST-/Mengen-Pipeline, Shop-IDOR/Ownership-Checks.

---

## 5. Mobile/Responsive-Befunde

| # | Befund | Fundstelle | Massnahme |
|---|---|---|---|
| R0 | **Master-Detail hat einen sauberen Mobile-Pfad** (`mobileView`-State, Detail als Vollbild, Zurück-Buttons) — kein Bruch. | `erp/page.tsx` | — (grün) |
| R1 | Inline-`gridTemplateColumns: '1fr 1fr'` kollabieren auf 360 px nicht → gequetschte Formulare. Auffälligster Fall: Spezifikations-Formular. | `article-detail.tsx:579`, `process-steps.tsx:658`, `order-detail.tsx:654/1460/1543`, `instance-detail.tsx:306`, `user-detail.tsx:112`, `sales-panel.tsx`, `purchase-step-panel.tsx:258`, `storage-location-detail.tsx:306`, `account/contact-section.tsx:84` | `repeat(auto-fit, minmax(min(100%,240px),1fr))` ✅ |
| R2 | Warenkorb-Zeile ohne `flex-wrap`: Bild 64 + Menge 64 + Preis 96 + Trash lassen dem Titel auf 360 px keine Breite. | `shop/cart/page.tsx:42` | Zeile umbaubar + Token-Migration ✅ |
| R3 | Touch-Ziele < 44 px: Warenkorb-Löschen (16 px!), Scan-Dialog-Schliessen (~22 px), Suche-Löschen (24 px), Scan-Button (32 px), Foto-Entfernen (20 px). | `cart/page.tsx:60`, `scan-dialog.tsx`, `erp/page.tsx:437/447`, `photo-capture.tsx:54` | auf ≥40–44 px anheben ✅ |
| R4 | KI-Widget (fixed bottom-right, 52 px) überdeckt auf Mobile Checkout-CTA/Panel-Footer; nur der Feed reserviert `pb-24`. | `assistant.tsx:148` + Shop-/Detail-Container | Bottom-Padding auf Scroll-Containern ✅ |
| R5 | Rechtsseiten-Tabellen ohne `overflow-x-auto`-Wrapper. | `datenschutz/page.tsx:181`, `impressum/page.tsx:94,130` | wrappen ✅ |

## 6. Skalierbarkeits-Befunde

- **Indizes** (B7) — grösster Hebel, Migration 060. GIN auf `instances.reservations`
  entschärft die `has_key`-Full-Scans in `_subject_shortfalls`/`sell_order_subjects`/
  `recompute_completion`.
- **Locking** (B2–B4) — macht die versprochenen Garantien (kein Überverkauf, kein
  Doppel-Nachschub, idempotenter Webhook) unter Nebenläufigkeit real.
- **Event-Loop** (B5) — synchroner HTTP-Call in async-Route entfernt. Grundsatzthema
  (alle Handler `async def` mit synchroner DB) dokumentiert als Folgearbeit: entweder
  flächig `def`-Handler (Threadpool) oder async-Session — nicht Teil dieses Cleanups.
- **Feeds**: orders/instances server-paginiert (gut); articles/records unlimitiert
  (B11, bei aktueller Kardinalität ~1'000 unkritisch, beobachten).
- **Frontend**: react-query nur punktuell; Feed lädt schlanke Listen vollständig —
  bei aktueller Datenmenge ok (dokumentiert, kein Umbau).

## 7. Design-System-Altlasten (Zählung, «beim Anfassen migrieren»)

- **761 hartkodierte Hex-Farben in 52 TSX-Dateien** (Top: `order-detail.tsx` 122,
  `inspection-panel.tsx` 33, `resource-panel.tsx` 32, …) — Inline-Styles mit
  1:1-Token-Mapping (`#0f172a`→`--fg-1`, `#64748b`→`--fg-3`, `#2563eb`→`--accent`, …).
- **326 deprecated Tailwind-Klassen (`slate-*`/`blue-*`) in 27 Dateien** — v. a.
  öffentliche Seiten/Shop/Admin (Top: `ueber-uns` 34, `system-config-section` 33,
  `datenschutz` 33, `kontakt` 31, `shop/product` 26, `admin/benutzer` 24, `cart` 21).
- In dieser Runde migriert: die Basisbausteine `ui/input.tsx`/`ui/textarea.tsx`
  (`focus:ring-blue-500`→`focus:ring-accent`, app-weit sichtbar) und alle Dateien, die
  für Responsive-/Bug-Fixes ohnehin angefasst werden (u. a. Warenkorb komplett).
  Der Rest konvergiert per «beim Anfassen mitziehen» (README §4) — bewusst kein Big-Bang.

## 8. Autonom umgesetzt vs. Freigabe nötig

**Autonom umgesetzt (Phase 2/3, verhaltensgleich bzw. klarer Bugfix):**
B1 (reason-Spalte), B2–B4 (Row-Locks — härten bestehende Garantien, keine
Logik-Änderung), B5 (def-Handler), B7 (Indizes), A1–A4 (tote Dateien/Wrapper,
Doku-Fixes, Drop-Migration für F-Reste), Wording-Register ✅-Zeilen, R1–R5
(Responsive), Design-Token-Migration in angefassten Dateien.

**Braucht Freigabe (Entscheidungs-Vorschläge, NICHT umgesetzt):**
1. **B6/Commit-Granularität im Zahlungspfad**: `fulfill_intent` committet je Position
   (via `finalize_paid`) statt einmal je Webhook; `pricing`/`fx` committen versteckt.
   Vorschlag: Commit-Hoheit an den Webhook-Handler ziehen, FX-Persistenz in eigene
   Session. Berührt Geld-Pfad → nur mit Freigabe + Sandbox-Test.
2. **B8/Optimistic Locking flächig**: `expected_updated_at` in allen Schreib-Schemas
   + Pflicht statt opt-in. API-Vertrag ändert sich (Frontend muss mitziehen).
3. **B9/Strukturierte Fehler**: zentraler `HTTPException`-Handler, der String-Details
   in `{error, code}` normalisiert + schrittweise Fehler-Codes. API-Vertrag.
4. **Async-Grundsatzfrage**: Handler flächig auf `def` (Threadpool) umstellen.
5. **`update_order`/`to_order_response` aufteilen** (>80-Zeilen-Konvention) — reines
   Refactoring, aber gross; besser gebündelt mit dem nächsten fachlichen Umbau.
