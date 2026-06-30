# ADR 003: Bedarf → Nachschub als EIN Unter-Auftrag-Mechanismus (MRP-light)

**Status:** Accepted
**Date:** 2026-06-30
**Deciders:** Inexxio AG
**Ersetzt:** ADR 002 (Make-to-Order als ein verketteter Auftrag) – siehe „Verhältnis zu ADR 002".

## Kontext

Ein Verkauf «auf Bestellung» (`articles.sales_fulfillment='make'`) und – allgemeiner –
jede Produktion mit fehlendem Material brauchen eine Antwort auf: *Was, wenn der Bestand
für einen Bedarf nicht reicht?* Die bisherigen Lösungen waren Sonderfälle:

- Make-to-Order erzeugte einen **separaten Produktionsauftrag** + Verkaufsauftrag, verkettet
  über `fulfilled_by_order_id` (Shop-Sonderlogik, „komische" Wartezustände).
- Eine Produktion liess sich nur freigeben, wenn **alle** Komponenten am Lager waren (harter
  Freigabe-Fehler), sonst Stillstand.

Leitprinzip des Auftraggebers: **Was die Automatik (Shop) tut, muss identisch sein zu dem,
was ein Mensch im ERP von Hand modelliert.** Kein Sondercode, ein Mechanismus.

## Entscheidung

**Trenne „WOHER kommen die Stück" (Quelle, abgeleitet) von „WAS fehlt" (Bedarf → Nachschub).**

### 1. Bedarf ist abgeleitet, nicht konfiguriert
Ein Auftrag hat **Bedarfe**: ein stock-Auftrag braucht sein **Subjekt** (Fertigware ab Lager),
ein produce-Auftrag **Komponenten** (consume-Zeilen). `subject_kind` wird **allein** aus der
Auftragsgestalt abgeleitet (`has_custom_steps`); die frühere `subject_source`-Übersteuerung ist
entfernt.

### 2. „Blockiert" ist ein abgeleiteter Schritt-Zustand (kein Auto-Trigger)
Ein Schritt, der an der Reihe wäre, dessen Bedarf aber nicht gedeckt ist, ist **`blocked`** –
berechnet live aus dem Bestand (`process.step_shortfalls`), nicht gesetzt. Damit löst sich das
Dilemma „Prozess starten und steckenbleiben" vs. „Auto-Freigabe-Trigger": Der Auftrag wird
freigegeben (Fehlmenge ist **kein** Fehler mehr – Teil-Reservierung), aber der **verbrauchende
Schritt** ist das Tor. Liefert der Nachschub, wird der Schritt bei der nächsten Auswertung von
selbst `active` – ohne Hook.

### 3. Nachschub ist ein Unter-Auftrag (derselbe wie die Abweichung)
Der Unter-Auftrag-Mechanismus (`orders.parent_order_id`) bekommt einen **Grund** (`orders.reason`):
- `deviation` – Reklamation/Fehler/Nacharbeit/Abbruch-Folgeauftrag (pausiert den Eltern).
- `supply` – **Nachschub**: produziert/beschafft die Fehlmenge (der ganz normale Artikel-Prozess)
  und **pinnt** sie bei Abschluss an den Eltern (`process._peg_supply_to_parent`: Reservierung;
  beim Subjekt zusätzlich `subject_of_order_id` + Historie). Der Eltern **pausiert nicht** – nur
  der betroffene Schritt ist blockiert.

`services/supply.ensure_supply` legt für jeden offenen Bedarf einen Nachschub an und gibt ihn
frei – **rekursiv** (mehrstufige Stückliste: fehlt dem Nachschub Material, deckt es ein weiterer),
**idempotent** (kein Doppel-Nachschub) und **zyklensicher** (Artikel-Kette gegen zirkuläre BOM).

### 4. EIN Auslöser, ein Pfad
- **ERP**: Knopf «Nachschub anlegen» (`POST /orders/{id}/supply`) → `ensure_supply`.
- **Shop** («auf Bestellung», make): die Zahlung ruft **dieselbe** `ensure_supply`.
- Die Freigabe selbst ist **ein** Pfad (`services/orders.release_order`), genutzt von ERP-Router,
  Shop-Zahlung (`sale._release_on_payment`) und Nachschub.

`sales_fulfillment` schrumpft auf eine **1-Bit-Policy**: `make` = bei Mangel Nachschub
(Backorder) | `stock` = nur ab Lager (limitierte Auflage, kein Überverkauf beim Checkout).

## Konsequenzen

- **Positiv:** Make-to-Order, Produktion-mit-Materialmangel und Reklamation laufen über **einen**
  Mechanismus. Kein `fulfilled_by_order_id`, kein `subject_source`, keine Make-Verkettung. „3 ab
  Lager + 7 produzieren" und mehrstufige Stücklisten fallen gratis heraus. Manuell == automatisch.
- **Pegging** verhindert, dass FIFO den Nachschub eines Auftrags „klaut" (deterministisch).
- **Abbruch ist ein Antrag, kein Vollzug (reversibel):** «Abbrechen» legt einen Folgeauftrag
  (Entwurf) an und pausiert das Original; erst die **Freigabe** des Folgeauftrags vollzieht den
  Abbruch. Bis dahin **zwei** Wege über DENSELBEN Mechanismus: Folgeauftrag **freigeben** (mit
  Schritt einlagern/verschrotten/nacharbeiten = Auflösung) **oder** **verwerfen** = «Abbruch
  zurücknehmen» (`deviation.revoke`, `POST /orders/{id}/revoke`) → Original läuft **unverändert**
  weiter (ein Entwurf hat die Reservierungen nie gelöst). „Weitermachen" ist damit KEIN eigener
  Schritttyp, sondern das Zurücknehmen des Abbruchs.
- **Nachschub-Kinder sind keine Ausnahme:** sie werden beim Eltern-Abbruch NICHT gesondert
  aufgelöst. Fällt der Bedarf weg, ist `_peg_supply_to_parent` ein No-op (toter Eltern) → der
  Output fliesst in den **freien Bestand** (kein vernichtetes WIP). Wer einen laufenden Nachschub
  stoppen will, bricht ihn mit demselben Mechanismus ab. Kann ein Bedarf nicht gedeckt werden
  (Artikel ohne Prozess), bleibt der Schritt sichtbar blockiert (manuelle Klärung).
- **Bewusst (noch) NICHT:** Netting gegen frei werdenden Bestand, Konsolidierung mehrerer Eltern
  auf einen Nachschub, Termin-Hochrollen über die Nachschub-Kette. Hooks/Notizen sind gesetzt.
- **Migration `044`:** `orders.reason` neu; `orders.subject_source` + `orders.fulfilled_by_order_id`
  entfernt. Keine Rückwärtskompatibilität für Altdaten nötig (bewusst).

## Verhältnis zu ADR 002

ADR 002 machte Make-to-Order zu **einem verketteten** Auftrag (Artikel-Prozess + Verkaufs-Schwanz).
Das zementierte die starre „make XOR stock"-Quelle und löste weder Teil-Lager noch mehrstufige
Materialknappheit. ADR 003 ist allgemeiner und **ersetzt** ADR 002: Verkauf = reiner Bedarf
(stock/FIFO); Produktion = Nachschub-Unter-Auftrag (transparent „wartet auf #123" statt
verstecktem Hänger). Der frühere Code aus ADR 002 (Schritt-Verkettung, `_create_make_sale_order`)
ist nicht Teil von `develop` und entfällt damit.
