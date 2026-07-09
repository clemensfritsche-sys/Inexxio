# ADR 005 – Logistik/Versand: «Versand wird abgeleitet, nicht bestellt»

Status: umgesetzt (Slice 1+2) · Datum: 2026-07-09

## Kontext

Das Bewegen-Modul besorgt jeden physischen Transport. Externe Transporte (Versand zum
Kunden, Versand zum Lieferanten/Lohnveredelung, Abholung beim Lieferanten, Kunden-Retoure)
sollen **maximal automatisiert** sein – ohne dass interne Umlagerungen oder Sonderfälle
(selbst bringen/abholen) Logistikaufträge erzeugen.

## Entscheidung

### 1. Ableitung statt Orchestrierung (eine Klassifikation)

Jeder Bewegungs-Schritt wird klassifiziert (`services/logistics.classify_movement`):

- **Personen nach Rolle**: Kunde/Lieferant = aussen, Mitarbeiter/Admin/KI = innen.
  Funktioniert OHNE Geofence – deckt die Versand-Hauptfälle ab Tag 1 ab.
- **Lagerplätze nach GPS** gegen den **Betriebs-Geofence** (Mittelpunkt + Radius am
  Unternehmens-Datensatz, `company_settings.site_latitude/longitude/radius_m`,
  Default-Radius 300 m). Ohne Geofence/GPS gilt der Firmen-Lagerplatz als «innen».
- **Instanz-Ziele** werden über die physische Standort-Kette aufgelöst
  (`resolve_physical_location`) und dann klassifiziert.
- **Richtung**: Ziel aussen → `outbound` (wir versenden); Quelle aussen, Ziel innen →
  `inbound` (Abholung beim Lieferanten / Kunden-Retoure) – **dieselbe Engine** für den
  Rückversand.

Klassifizierbar ist ein Schritt mit bekanntem Ziel (Pflicht-Versand zum Kunden,
Vorgabe-Ziel am Schritt). Frei wählbare Ziele bleiben ohne Versand-Box (interner Alltag).

### 2. Long-Tail über EIN Feld: `transport_mode`

`auto` (Default, abgeleitet) | `carrier` (immer Versand) | `self` (Selbsttransport:
bringen/abholen, protokolliert ohne Carrier) | `none` (nie Versand). Deklariert am
Bewegungs-Schritt (`article_process_steps.transport_mode`), **je Auftrag übersteuerbar**
am Versand-Beleg (`shipments.transport_mode`) – ein Auftrag mutiert nie den Artikel-Prozess.
Digitale Payloads sind bewusst KEIN Fall (Dokumente werden nicht extern bewegt).

### 3. Versand-Beleg (`shipments`) – Fachzeile ohne eigene Nummer

Analog `purchase_orders`/`movements`: je Bewegungs-Schritt (`step_id`) ein Beleg unter
dem Auftrag. Trägt Adress-Snapshots, Paket-Schätzung, Rate-Snapshot, Label, Tracking,
Kosten. Status: `draft → quoted → purchased → done` (done = Bewegung scan-quittiert).
Pakete werden **aus den Artikel-Daten geschätzt** (Gewicht × Menge, Grösse-String
mm→cm; Fallback Standardkarton) – kaum manueller Input. **Gefahrgut** ist ein optionales
Artikel-Spezifikationsfeld (`articles.is_hazmat`) und erscheint als Warnung am Versand.

### 4. Carrier-Aggregator: **EasyPost**, hinter einem Gateway

`services/shipping/` (exakt das Payments-Muster): `base.ShippingProvider` →
**easypost** (Rate-Shopping + Label-Kauf, aktiviert sich selbst über `EASYPOST_API_KEY`)
| **manual** (ohne Key: Carrier/Tracking von Hand – nie kaputt). EasyPost-Wahl:
Self-Serve wie Stripe (Test-Key sofort, Pay-per-Label, keine Vertrags-Eintrittsbarriere),
sauberstes REST-API, 100+ Carrier international. Adapter rechnet cm/kg → inch/oz;
Kauf über `POST /v2/shipments/{id}/buy`. Sendcloud/Shippo wären Drop-in-Adapter.

### 5. Best-Offer-Policy: günstigster Default, Schnellster als Hinweis

`logistics.quote` sortiert aufsteigend nach Preis, markiert `cheapest` (Default-Auswahl)
und `fastest` (Hinweis-Badge + Alternative-Zeile im Panel). Der Mensch bestätigt den
**Kauf** mit einem Klick (Geld = Gate, wie überall); no-ops laufen still.

### 6. Vollzug bleibt scan-quittiert

Das Label ist die vorbereitende Carrier-/Geld-Seite; die **Bewegung** bleibt der
physische Vollzug (Scan). `record_movement` schliesst den Beleg (purchased → done) und
übernimmt Tracking/Carrier in die Bewegung, wenn nichts Eigenes erfasst wurde.

## Bewusst NICHT gebaut (dokumentierte Erweiterungen)

Tracking-Webhooks (Status-Events vom Carrier), Pickup-Orders (Abholauftrag beim Carrier
– heute: inbound-Label/manuelle Organisation), Multi-Parcel-Splits, Versandkosten-
Verrechnung an den Kunden, Zoll-Dokumente (customs_info) für Übersee.
