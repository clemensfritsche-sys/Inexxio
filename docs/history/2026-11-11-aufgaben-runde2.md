# Rundenbericht: Aufgaben, Runde 2 «Datum» (11.11.2026)

Projektakte: `docs/konzept/aufgaben.md` §5, §12.1 (Punkte 11–16). Branch `claude/aufgaben-datum`.

## Was gebaut ist

- **Das eine Datum** (`domain/order_date.py`): «bis» (`until`) oder «ab» (`from`), nie beide, nie in
  der Vergangenheit; `problem` ↔ `clean`. Spalten `orders.date_kind` · `date_on` mit Prüfung in der
  Datenbank (Migration 189, `ck_orders_date`).
- **Setzen und verschieben**: im Entwurf (`OrderCreate.date`, geprüft wie alles andere in
  `validate_draft`), danach `POST /erp/orders/{nr}/date` (`orders.set_date`, nur im Prozess). Das Log
  schreibt der Trigger an `orders` – kein eigenes Ereignis.
- **Aufgaben** (`tasks._dated`): eine Aufgabe am Auftrag (Schritt, Zahlung) hat als Datum X; bei
  «ab» X gibt es sie vor X nicht. Alles andere unverändert («seit wann»).
- **Zahlung**: Offerte und AB nennen «Liefertermin» bzw. «Ausführung ab» (`voucher_docs._terms`);
  gespeichert ist es nur am Auftrag. Ein verschobenes Datum macht eine gesendete Offerte überholt
  (`voucher.fingerprint` – nur wenn gesetzt, damit bestehende Offerten ohne Datum gültig bleiben).
- **Wiederholung** (`loop._next_date`): der Nachfolger bekommt dasselbe Wort und denselben Abstand
  zwischen Termin und Datum wie der Vorgänger; wartete er, nie vor heute (sonst wiese ihn die
  Freigabe ab und die Kette stünde still).
- **Beschaffen**: «Nachschub» und «Holen lassen» am Verbrauch öffnen den Entwurf mit «bis» = Datum
  des Auftrags (`CaptureWork.due` → `OrderSeed.date`). Keine Verknüpfung.
- **Oberfläche**: neben dem Start-Kreis «ab», neben dem Ende-Kreis «bis» (`order-date.tsx`,
  `FlowColumn.dates`, ausserhalb des Flusses – die Linien messen nur den Kreis); dieselben Felder im
  Entwurf und am laufenden Auftrag, danach nur gelesen. Ein Vorschlag der KI bringt das Datum mit
  (`proposal-draft.dateOf`).

## Entscheide in der Umsetzung

- **Abstand statt Kalender** für den Nachfolger: ein eigener Anker je Datum wäre ein zweiter
  Kalender; der Abstand zum Termin folgt dem Kalender der Wiederholung von selbst und übernimmt ein
  verschobenes Datum.
- **«ab» gilt für jede Aufgabe am Auftrag**, auch für die Offerte (wie in §5 entschieden). Braucht
  ein Service vorher eine Offerte, ist «bis» oder kein Datum die Wahl.
- Die Feed-Zeile (`OrderSummary`) trägt das Datum nicht – niemand liest es dort.

## Geprüft

- Backend: 868 Tests grün, neu `tests/test_auftrag_datum.py` (5 Wächter; gegen die Bug-Formen
  gegengeprüft: «ab» ohne Wirkung und ein Nachfolger in der Vergangenheit schlagen an); `ruff` sauber.
- Frontend: `type-check`, `lint`, `npm test` grün (der Test «Netz weg» der Aufnahme schlug wie in
  Runde 1 einmal zeitabhängig fehl und lief einzeln zweimal grün); `proposal-draft` mit Datum.
- Generierte Dateien neu (`openapi.json`, `api.ts`, `vocab.ts`).
- **Nicht** im laufenden ERP angesehen (Anmeldung über Firebase) – nach dem Merge auf inexxio-dev.

## Offen

- Dauer selbst abziehen («bis minus Dauer», aus dem Log) – vorerst setzt der Mensch «bis» früher.
- Dokument zum Unterschreiben als Aufgabe (aus Runde 1).
