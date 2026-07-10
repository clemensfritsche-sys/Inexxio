# ADR 005 – Logistik/Versand: «Versand wird abgeleitet, nicht bestellt»

Status: umgesetzt (Slice 1+2, Sendcloud-Default + Shippo-Fallback, adress-basiert) · Datum: 2026-07-10

## Kontext

Das Bewegen-Modul besorgt jeden physischen Transport. Externe Transporte (Versand zum
Kunden, Versand zum Lieferanten/Lohnveredelung, Abholung beim Lieferanten, Kunden-Retoure)
sollen **maximal automatisiert** sein – ohne dass interne Umlagerungen oder Sonderfälle
(selbst bringen/abholen) Logistikaufträge erzeugen.

## Entscheidung

### 1. Ableitung statt Orchestrierung (eine Klassifikation)

Jeder Bewegungs-Schritt wird klassifiziert (`services/logistics.classify_movement`) –
**adress-basiert, KEIN Geofence** (bewusst einfach: «von A nach B mit anderer Adresse →
Versand, sonst innerbetrieblich»):

- **Personen nach Rolle** (`location_kind`): Kunde/Lieferant = extern, Mitarbeiter/Admin/KI
  = intern. Ziel externe Person → extern/outbound; Quelle externe Person → extern/inbound.
- **Ziel ohne Standort/Adresse → innerbetrieblich** (kein Versand). Genau die Regel des
  Nutzers: hat der Zielstandort keine Adresse, ist es interner Transport.
- **Zwei interne Orte** (Lagerplatz/Instanz/Mitarbeiter): Versand NUR, wenn **beide eine
  Adresse tragen und sich unterscheiden** (`same_place`, normalisierter Vergleich) –
  Mehr-Standort-Transport. Gleiche/keine Adresse → innerbetrieblich.
- **Instanz-Ziele** werden über die physische Standort-Kette aufgelöst
  (`resolve_physical_location`) und dann klassifiziert.
- **Richtung**: `outbound` (wir versenden) bzw. `inbound` (Abholung Lieferant /
  Kunden-Retoure) – **dieselbe Engine** für den Rückversand.

Der frühere Betriebs-Geofence (`company_settings.site_*`, Migration 071) ist damit
**entfallen** (Migration 072 droppt die Spalten). Adressen werden per Google-Places-Autofill
gepflegt (`components/erp/address-autocomplete.tsx`), was den Adressvergleich zuverlässig macht.

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

### 4. Carrier-Aggregator: **Sendcloud** (Default), Shippo als Fallback – hinter EINEM Gateway

`services/shipping/` (exakt das Payments-Muster): `base.ShippingProvider` →
**sendcloud** | **shippo** | **manual**. Auswahl über `shipping_provider` (`auto` =
Sendcloud ≻ Shippo ≻ manual): der aktive Provider ergibt sich aus den vorhandenen Secrets;
beide Adapter koexistieren im Code.

- **sendcloud** (EMPFOHLEN): europäischer Aggregator mit **nativer Herkunft Schweiz**
  (Swiss Post/DPD/DHL ab CH). Self-serve API-Keys (Public + Secret, HTTP-Basic), ohne
  eigenen Carrier-Vertrag über Sendclouds Tarife startbar, **kostenlose Test-Labels**
  («Unstamped letter»). Rate-Shopping über `GET /shipping_methods` (Preis je Zielland),
  Label über `POST /parcels`. Rechnet nativ in kg.
- **shippo** (Fallback): US-zentriert – die geteilten Gratis-Carrier können **CH-Herkunft
  NICHT** (praktisch bewiesen: alle meldeten „origin not supported"). Ab CH nur mit
  **eigenem Carrier-Konto** (DHL Express/UPS/…) + **Live-Token**. Bleibt als Adapter erhalten.
- **manual** (ohne Keys): Carrier/Tracking von Hand – nie kaputt.

**Warum Sendcloud statt Shippo für eine Schweizer AG:** Shippos Sandbox deckt CH-Herkunft
prinzipiell nicht ab; Sendcloud tut es nativ und lässt sich gratis testen. EasyPost/nShift
wären weitere Drop-in-Adapter.

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
