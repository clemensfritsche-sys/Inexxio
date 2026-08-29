# CLEANUP REPORT – 2026-07-03

Zweiter autonomer Cleanup-/Bugfix-/Optimierungs-Durchgang (Folge zu `CLEANUP_REPORT_20260702.md`).
Keine Schema-Änderungen. Verifiziert: **161/161 Backend-Tests grün**, `ruff` (F) grün,
`tsc --noEmit` grün (auch mit `noUnusedLocals`), ESLint grün, `next build` grün,
OpenAPI→TS-Typen neu generiert und synchron.

Die 5-Primitive-Architektur (Entity = Objektnummer, Event = Outbox mit deklarierter Polarität,
Relation = Links/Unter-Aufträge/Reservierungen, Projection = abgeleitete Schritt-/Auftragsstatus,
Prozessdefinition = Schritte inline am Artikel/Auftrag) ist weiterhin konsistent; die Bugs unten
sind Lücken in einzelnen Ableitungen, kein Architektur-Drift.

## 1. SUMMARY

**Backend – Sicherheit**
- **Unauthentifizierter Debug-Endpoint `GET /api/v1/debug` entfernt** (`routers/health.py`): gab
  Admin-E-Mails, Nutzerzahlen und die `initial_admin_email`-Konfiguration anonym preis (Phishing-Ziel-Liste).
- `GET /health` gibt DB-Fehlertexte (können Host/User der DATABASE_URL enthalten) nur noch ins Log.
- **Manueller Zahlungsmodus: öffentlicher Webhook geschlossen** – jeder konnte fremde Checkouts
  unauthentifiziert als «bezahlt» markieren (Erfüllung ohne Zahlung) oder stornieren. Manuelle
  Zahlung läuft nur noch über den eingeloggten, ownership-geprüften `/shop/payments/simulate`.
- **Stripe-Webhook ohne `STRIPE_WEBHOOK_SECRET` schlägt hart fehl** (503) statt Events unverifiziert
  zu verarbeiten (gefälschtes `checkout.session.completed` = Gratis-Erfüllung).
- 401-Antworten echoen keine rohen Firebase-Exceptions mehr; Kontaktformular mit Feld-Obergrenzen;
  `quantity` mit Obergrenze 100'000 (vorher hätte 2e9 ebenso viele Instanzen erzeugt); Verkaufs-
  `currency`/`vat_rate` validiert; Rollen-Whitelist als `Literal` an BEIDEN Rollen-Endpunkten.

**Backend – Cleanup**
- Tote Funktionen entfernt (je grep-verifiziert): `admin.create_notification`/`get_user_by_firebase_uid`,
  `inventory.on_hand`, `lifecycle.ensure_article_draft`, `process.active_step_of_type`,
  `locations.ensure_receiving_location`/`resolve_receiving_location`/`physical_location_label`
  (Relikte des alten Wareneingang-Modells – Beschaffung ist heute rein kaufmännisch),
  `sale.unit_price`/`mark_paid`, `tax.TAX_CLASSES`, `stripe_provider._ship_countries`/`_dig`,
  Config `shop_ship_countries`.
- **Notifications-Endpunkte entfernt** (`GET/POST /admin/notifications…`): nichts schreibt je eine
  Notification, das Frontend ruft sie nie – die Liste konnte nur leer sein (Modell bleibt, Schema eingefroren).
- Duplikate konsolidiert: Anzeigename (Firma→Name→E-Mail) 5× → `UserProfile.display_name`;
  Preis-Sortierung 3× → `pricing.sort_key`/`sales.sort_prices`.

**Backend – Performance**
- `GET /shop/products`: Preise + Kunden-Zuweisungen **batch** (vorher 2–3 Queries **je Artikel**
  auf einem öffentlichen Endpoint – bei ~1'000 Artikeln Tausende Queries je Listing) + In-Prozess-Memo
  für Tageskurse (`fx.get_rate`).
- «Meine Bestellungen»/ERP-Reiter: Retoure-Status-Probe batch (vorher 1 Query je Beleg).
- Auftrags-Detail: Bestell-Verlauf 1× je Auftrag statt je Position; Ressource-Zeilen-Artikel batch
  (50-teilige BOM = 50→1 Query je Schrittliste); Lagerplatz-Verwendung batch.
- Instanz-Detail «Aufträge»: ResourceUsage-Scan von «ALLE Zeilen laden + Python-Scan» auf
  JSONB-Containment in SQL umgestellt (unbegrenzt wachsende Tabelle).

**Frontend**
- Tote Route `/shop/success` + `api.getCheckoutSession` entfernt (eingebettete Kasse redirectet nie);
  tote Utils/Typen/Props/State entfernt (`formatDate`, `truncate`, `STORAGE_TYPES`, 14 tote Typ-Exporte,
  `showArticle`-Prop, `roleFetched`-State, `fmtObjId`-Kopie, `'consume'/'tool'`-Altzweig).
- Konsolidiert: CHF-/Geld-Formatierung (7 Kopien) + `localDate` (5 Kopien) → `lib/utils.ts`
  (`formatAmount`/`formatMoney`/`localDate`); `SaveIndicator` (3 Kopien) → `fields.tsx`;
  `OrderInstance`-Typ statt 2 lokaler Re-Deklarationen.

## 2. BUGS FIXED (je mit `// FIX:`-Kommentar an Ort)

**Geld/Shop**
1. `services/payments/stripe_provider.py: refund` – Rückgabe EINER Position eines Mehrpositionen-
   Kaufs erstattete den **gesamten** PaymentIntent (voller Warenkorb-Betrag). Jetzt anteilig auf
   Basis des eingefrorenen **Positions**-Brutto.
2. Abo-Kündigung nach Auftrags-Abschluss war wirkungslos: «Kündigen» meldete Erfolg **ohne Stripe zu
   kündigen** (Kunde wäre unbegrenzt weiter belastet worden), und der Stripe-Webhook konnte die
   lokale Wiederkehr-Kette nicht mehr stoppen. Fix über die ganze Kette (`sales.recurrence_chain`/
   `deactivate_recurrence_chain`; `routers/shop.py`, `payments/base.py`, `stripe_provider.py`).
3. `sales.checkout` – schlug die Stripe-Session fehl, blieben stock-Reservierungen dauerhaft bestehen
   (kein `expired`-Event ohne Session, kein Aufräumer). Intent wird jetzt sauber aufgelöst.
4. `sales.fulfill_intent` – (a) Webhook-Retry nach Teilfehler hätte **Dubletten** erzeugt (Auftrag+
   bezahlter Beleg): Position→Auftrag-Zuordnung wird jetzt sofort persistiert; (b) ein stornierter
   Intent wird durch eine verspätete Zahlung nicht mehr «wiederbelebt» (inaktiver Auftrag mit
   bezahlten Belegen ohne Ware).
5. `sales._resolve_line` – **angezeigter ≠ verrechneter Preis**: Anzeige charm-gerundet (CHF 100.00),
   Stripe-Belastung roh (99.99). Der Kunde zahlt jetzt exakt den angezeigten Preis.
6. `services/refund.py` – eine wieder eingelagerte und **erneut verkaufte** Instanz war nie mehr
   retournierbar (400). Massgeblich ist jetzt je Instanz der jüngste bezahlte Verkauf.

**Kernprozess**
7. `subject.order_instances` – sobald ein Nachschub/Cover-Link auf einen **Erzeugungsauftrag** kam,
   kollabierte dessen Instanzmenge auf NUR die gepinnten Stücke: die selbst produzierten verschwanden
   aus Bewegung/Prüfung/Verschrottung und wären beim Abschluss unbewegt «am Lager» freigegeben worden.
   Jetzt Vereinigung statt entweder/oder (wirkt auch auf Bestandsdaten).
8. `routers/orders.py` – Status-Zustandsmaschine: ein Entwurf liess sich per PATCH direkt auf
   `completed` setzen, ein abgeschlossener/inaktiver Auftrag auf `draft` zurückholen (Umgehung von
   «kein Reaktivieren»), und `is_active=false` auf einem freigegebenen Auftrag hätte seine
   Reservierungen dauerhaft stranden lassen (`is_active` aus `OrderUpdate` entfernt).
9. `routers/orders.py: add_order_line` – **doppelte Positionen desselben Artikels** werden abgewiesen:
   sie zerlegten die FIFO-Allokation (Unter-Reservierung) und liessen die zweite Position still
   unbestellt/unverrechnet (Beschaffung/Verkauf schlüsseln je Artikel).
10. `deviation.auto_deviation_from_inspection` – die dokumentierte Auto-Abweichung bei fehlgeschlagener
    Datenerfassung feuerte NUR bei Erzeugungsaufträgen (Suche über `Instance.order_id`); bei Bestands-/
    Pin-/Retoure-Aufträgen wurde sie still übersprungen. Jetzt über das Subjekt des Auftrags.
11. `process._subject_shortfalls` – reservierte, aber **durchgefallene** Instanzen zählten als
    «gesichert» (gegen den eigenen Kontrakt): der Schritt blockierte nie und der Verkauf hätte still
    unterliefert. `quality='failed'` zählt nicht mehr.
12. `routers/article_process.py: _update` – Lieferanten-/Modus-Wechsel am Beschaffungs-Schritt zog die
    gesperrte Pflicht-Bewegung nicht nach (Versand zeigte auf den ALTEN Lieferanten).
13. `sale.apply_update_bulk` – die «eine gemeinsame Aktion» über mehrere Positionen war nicht atomar
    (Commit je Beleg): jetzt EINE Transaktion; nur das Erstatten von Gutschriften committet bewusst je
    Beleg (kein Rollback nach externem Stripe-Refund).
14. Klein: `supply.pegged`-Event nur noch bei tatsächlichem Pegging; Feed-Beschaffungsbadge
    deterministisch; `PurchaseEmbed` trägt jetzt die Stammdaten **je Position** (Lieferanten-Karte war
    bei Mehrpositionen leer, «—»).

**Frontend**
15. `lib/firebase.ts` – Firebase-Token wurde **nie erneuert** (`onAuthStateChanged` feuert nicht bei
    der stündlichen Rotation): nach ~1 h scheiterte jeder API-Call mit 401 bis zum Hard-Reload.
    Jetzt `onIdTokenChanged` (alle Abonnenten erneuern den Token automatisch).
16. `shop/checkout/page.tsx` – die Danke-Ansicht nach Zahlung wurde sofort vom Leerer-Warenkorb-
    Redirect zerstört («Dein Warenkorb ist leer» statt Bestätigung).
17. Container-`onKeyDown` (Artikel/Auftrag/Lagerplatz-Detail) verschluckte **Zeilenumbrüche in
    Textareas** (mehrzeilige Beschreibungen/Bild-URLs waren nicht eintippbar).
18. `RecurrenceCard` lief am Optimistic Locking vorbei → der nächste Autosave scheiterte mit einem
    unerklärlichen 409.
19. ERP-Instanz-Suche: veraltete Antworten konnten neuere überschreiben (Liste/Zähler inkonsistent).
20. Beschaffungs-Schritt am **Auftrag** konnte nie einen Lieferanten wählen (`suppliers={[]}`
    hartkodiert, 3 Stellen).
21. `sales-panel.tsx` – Preis anlegen/löschen/Zuweisung schluckten Fehler still (kein catch);
    Fehler werden jetzt angezeigt.

## 3. DEFERRED ITEMS (bewusst nicht angefasst)

1. **Charge-Retoure stellt Menge 1 wieder her** (`process.return_subjects_to_stock`): die verkaufte
   Stückzahl einer Charge wird nirgends persistiert (Instanz-Menge wird beim Verkauf mutiert) – auch
   die Gutschrift zählt Chargen als 1 Stück (`sale._credit_targets`). Sauberer Fix braucht eine
   Mengen-Angabe am `instance_order_link` oder Beleg → Datenmodell-Entscheid.
2. **Rappen-Abgleich `_split_snapshot`**: die Positions-Anteile eines Warenkorbs werden einzeln
   quantisiert; die Summe kann um ±N Rappen vom Stripe-Settlement abweichen (10-Jahres-Archiv!).
   Braucht eine definierte Allokations-Policy (largest remainder) inkl. Zuordnung Sale↔Line.
3. **Wiederkehr-Folgeauftrag kopiert keine eigenen Schritte** (`process._spawn_recurrence`): ein
   wiederkehrender Auftrag mit individuellem Ablauf (z. B. Produktabo: sale+movement) spawnt einen
   Entwurf OHNE Schritte → der würde bei Freigabe den Artikel-Prozess fahren (produzieren). Hängt am
   offenen Design «Auto-Fulfillment je Abo-Zyklus» (invoice.paid-Hook, TODO laut CLAUDE.md).
4. **Ziel-Karten vs. vorhandene Auftrags-Schritte** (`order-detail.tsx`): ein Entwurf mit
   purchase-/resource-Schritten gilt als «Herstellen» und blendet den Schritt-Editor aus – vorhandene
   Schritte sind dann unsichtbar/unlöschbar. UX-Design-Entscheid (Karten-Logik), kein reiner Bugfix.
5. **Lieferanten-Sicht bei Mehr-Lieferanten-Aufträgen**: `record.purchase` ist das ERSTE Embed ohne
   Betrachter-Filter – Lieferant A kann Bestelldaten von Lieferant B sehen (Payload). Braucht eine
   Sichtbarkeits-Regel im Response-Aufbau (`services/orders.py`).
6. **Unbegrenzte Kandidaten-Listen für Scan/Bewegen** (`movement-panel`, `process-steps`:
   `getInstances(0)` = alle): der Scan braucht heute die VOLLE Liste zur Validierung – Begrenzung
   erfordert eine serverseitige Kandidaten-Suche. Ebenso der 6-fache Refetch je Auftrags-Save
   (`erp/page.tsx: handleOrderSaved`) – Daten-Frische vs. Last, gehört zu einem React-Query-Umbau.
7. Aus dem Vorbericht weiterhin offen: DB-Indizes (Schema), AGB-Akzeptanz-Verdrahtung,
   `POST /orders/{id}/replace` ohne UI, Bestell-Verlauf-Vermischung bei Mehrpositionen-Beschaffung
   (Audit braucht PO-Kennung), Rate-Limiting öffentlicher Endpoints, Reservierung ohne Row-Locking
   (Race bei Parallelzugriff – bei 10 Nutzern akzeptiert).

## 4. RECOMMENDATIONS (priorisiert)

1. **Vor dem Stripe-Sandbox-E2E**: `STRIPE_WEBHOOK_SECRET` setzen (Webhook verweigert jetzt ohne
   Secret – gewollt) und den Mehrpositionen-Kauf inkl. Teil-Retoure durchspielen (Fixes 1–5).
2. Deferred #1 (Chargen-Mengen bei Verkauf/Retoure) als nächsten Datenmodell-Schritt einplanen –
   betrifft Geld UND Bestand.
3. Deferred #5 (Lieferanten-Sicht) vor dem Lieferantenportal-Rollout klären.
4. Abo-Lebenszyklus konsolidieren (Deferred #3 + Mindestlaufzeit nach Abschluss): die Wiederkehr-Kette
   ist jetzt kündbar, aber Folge-Fulfillment je Zyklus bleibt unimplementiert.
5. `ruff --select F` und `tsc --noUnusedLocals` als CI-Gates – beide sind jetzt sauber und halten
   tote Importe/Locals dauerhaft draussen.

## Verifikation (Phase 5)

`pytest` 161/161 grün · `ruff` (F) grün · `tsc --noEmit` grün (inkl. `noUnusedLocals`) · ESLint grün ·
`next build` grün · OpenAPI/TS-Typen regeneriert & synchron.

Manuell nachgezeichnete kritische Workflows (alle intakt):
1. **Artikel anlegen → Prozess definieren → freigeben** – Freigabe-Gate unberührt; `_update` synct
   jetzt zusätzlich die Pflicht-Bewegungen (additiv).
2. **Produktionsauftrag bis auto-completed** – Freigabe-/Abschluss-Pfad unverändert; die
   `order_instances`-Vereinigung ist für Aufträge ohne Fremd-Links verhaltensidentisch.
3. **Shop-Kauf (Warenkorb → eingebettete Kasse → Webhook → Auftrag)** – Happy Path unverändert;
   manueller Modus läuft wie bisher über `/payments/simulate` (Pay-Seite geprüft).
4. **Verkauf ab Lager + Pflicht-Versand zum Kunden** – Allokation, `sell_order_subjects`, gesperrte
   Bewegungen unberührt.
5. **Retoure/Erstattung (ERP + Kundenportal)** – Einzelpositions-Refund byte-identisch zum alten
   Verhalten (Snapshot deckt den ganzen PI); Rückgabe-Bewegung und Gutschrift-Ablauf unverändert.
