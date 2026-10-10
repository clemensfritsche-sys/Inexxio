# Architektur- & Logik-Review — Juli 2026

Systematische Tiefenprüfung der Geschäftslogik auf Basis des deployten `develop`-Stands:
Zirkularitäten, Blockade-/Deadlock-Zustände, Logiklücken über die Business-Cases,
Nebenläufigkeit, tote/inkonsistente Pfade. Geprüft wurden insbesondere der
Unter-Auftrags-Graph (Abweichung/Nachschub/Retoure/Nachbestellung), der Geld-/Bestandsfluss
(Verkauf/Shop/Erstattung), die Prozess-Engine (Fehlmengen/Abschluss/Pause) und die
Gating-/Deaktivierungs-Kaskaden (Dokumente/Consent/Benutzer).

**Ergebnis: 15 Befunde sofort behoben** (dieser Branch), 263 Backend-Tests grün
(inkl. neuer Regressions-Guards in `tests/test_architecture_review.py`).
Die grossen Folgethemen stehen am Ende.

---

## 1. Sofort behobene Befunde

### Kritisch

**R1 — Shop-Versand war strukturell blockiert (jeder Shop-Kauf!).**
`sales._create_multiline_sale_order` legte den Versandschritt OHNE `locked=True` /
`mode='customer'` an – anders als der ERP-Verkauf (`sync_locked_movements`). Damit galt
die Locked-Ausnahme der Fehlmengen-Prüfung (`process.step_shortfalls`) nicht: nach der
Zahlung war die Ware «verkauft» (aus dem freien Bestand weg), der Versandschritt dadurch
dauerhaft «blockiert» (409 bei jeder Ausführung) und der Auftrag konnte NIE abgeschlossen
werden. Fix: Schritt korrekt als Pflicht-Versand anlegen + **Datenreparatur-Migration
`074`** für bestehende Shop-Aufträge. *(Warum unbemerkt: der Shop-Sandbox-Test steht in
CLAUDE.md noch als offene Aufgabe.)*

**R2 — «Verkauft durch diesen Auftrag» zählte als «verloren» statt «geliefert».**
`process._subject_shortfalls` wertete jede terminal-verkaufte Menge als Fehlmenge –
auch wenn DIESER Auftrag sie selbst verkauft hatte. Folgen: (a) Nachschub für teilweise
vorrätige make-Artikel wurde auf die VOLLE Menge statt der Fehlmenge dimensioniert
(Phantom-Produktion; zusätzlich abgesichert: `fulfill_intent` ruft `ensure_supply` jetzt
VOR dem Zahlungs-Verbuchen); (b) nicht-gesperrte Folgeschritte blockierten nach der
Zahlung dauerhaft; (c) «Nachschub anlegen» nach Lieferung hätte doppelt produziert.
Fix: `process.sold_amounts_for_order` rekonstruiert die je Auftrag verkauften Mengen aus
dem **Event-Strom** (`inventory.decreased`, `payload.order`; Verschrottung zählt nicht)
und zählt sie als *gesichert* – ausser die Instanz wurde danach verschrottet (Abweichung
zerstört Kundenware → Fehlmenge bleibt ehrlich sichtbar, Deckungs-Wege unverändert).

**R3 — Kunden-Versand verschob unverkauften Bestand zum Kunden.**
Nach einem Chargen-Teilverkauf (Verkauf konsumiert die reservierte Teilmenge, Rest bleibt
`in_stock`) bewegte der Pflicht-Versand die GANZE Rest-Charge per `set_single` zum Kunden –
der unverkaufte Rest stand danach als freier Bestand «beim Kunden». Fix:
`movement.movable_instances` als EINE Auswahlregel (Ausführung + Embed + Versand-Beleg):
Kunden-Versand nimmt nur `sold`/`in_process`/*ganz für den Auftrag reservierte* Instanzen
mit; eine reine Teilmengen-Sendung (der verkaufte Anteil hat keine eigene Instanz) wird als
Quittierung ohne Umlagerung abgeschlossen statt mit 409 zu blockieren.

**R4 — Chargen-Retoure stellte 1 statt der verkauften Menge zurück.**
`return_subjects_to_stock` setzte eine voll konsumierte Chargen-Instanz (Menge 0, `sold`)
pauschal auf Menge 1 zurück – eine 5-kg-Charge kam als 1 kg zurück (stiller
Bestandsverlust). Fix: Rückstell-Menge aus `sold_amounts_for_order(parent)` (Event-Strom),
Fallback 1 nur noch für Einzelteile/Altdaten.

### Blockaden / Deadlocks

**R5 — Unterschriften-Deadlock durch deaktivierte Partei.** Nur die benannte Person darf
signieren; eine deaktivierte kann sich nie mehr anmelden, und die Schritt-Definition ist
nach Freigabe eingefroren («Zurücknehmen + neu ausstellen» reproduziert dieselben
Parteien). Fixes: (a) «Ausstellen» prüft, dass jede deklarierte Partei ein aktiver Benutzer
ist (klare 409 statt unerfüllbarem Signoff); (b) Admin-Benutzer-Deaktivierung wird bei
offenen Signoffs (pending/rejected auf ausgestellten Dokumenten) mit 409 blockiert.

**R6 — Reject-Sackgasse beim sequenziellen Signieren.** Nach «Ablehnen» war die Partei
selbst nicht mehr handlungsfähig (nur `pending` zählte) UND die nächste Partei konnte an
der ungeklärten Ablehnung vorbeiziehen (Reihenfolge-Verletzung). Fix: `pending` UND
`rejected` gelten als unerledigt – die Ablehnung hält ihre Position, die ablehnende Partei
bleibt re-aktionabel (`_assert_actionable` + «Meine Dokumente»-Spiegel).

**R7 — Steckengebliebene Nachbestellung unterdrückte alle künftigen.** Ein fehlgeschlagener
Schritt (abgelehnte Beschaffung, endgültig durchgefallene Prüfung) ist nicht erneut
ausführbar → der Auftrag bleibt für immer `released` und galt als «offen» → keine
Auto-Nachbestellung mehr für den Artikel (schleichender Stockout ohne Fehler). Fix:
`_open_replenishment` ignoriert Aufträge mit fehlgeschlagenem Schritt (Klärung = Abbruch,
Bestand wird derweil regulär nachbestellt).

**R8 — Auto-Abweichung von Nachschub-Kindern unterdrückt.** `open_deviations` filterte
nicht auf `reason='deviation'` – ein offener Nachschub-/Retoure-Unterauftrag zählte als
«offene Abweichung» und die dokumentierte Auto-Abweichung nach fehlgeschlagener
Datenerfassung wurde still übersprungen (Durchfaller ohne Auflösungs-Workflow).

**R9 — Consent-Lücke beim Ersetzen einer Dokument-Fassung.** Der Supersede-Skip der
Publikums-Anerkennungen feuerte schon bei gesetztem `replaced_by_id` – also ab dem Klick
auf «Ersetzen», obwohl der Nachfolger nur Entwurf ohne ausgestelltes Dokument war. Die
gültige Fassung verlor ihre Anerkennungspflicht. Fix: `_superseded_by_released_doc`
(Kette zyklensicher; Skip erst, wenn ein Nachfolger ein freigegebenes Dokument trägt) –
analog `legal.resolve`. Zusätzlich: inaktive Schritte erzeugen keine Obligationen mehr.

### Stille Daten-/Konfigurationsverluste

**R10 — `_copy_steps` (Ersetzen/Wiederkehr) verlor Konfiguration.** `doc_signers`,
`sign_sequential`, `doc_audience(_roles/_person_ids)`, `doc_visibility` und
`transport_mode` wurden nicht mitkopiert: die neue Fassung eines Rechts-/Publikums-
Dokuments hätte NIE mehr gated, der nächste Wartungszyklus verlor die
Unterschriften-Pflichten.

**R11 — `duplicate_article` verlor Spezifikations-/Steuerfelder.** `is_hazmat`,
`reorder_target`, `fixed_location_*`, `procurement_mode`, `default_supplier_id`,
`default_webshop_url` fehlten – der Nachfolger eines Beschaffungs-Artikels liess sich
ohne Neueingabe der Bezugsquelle nicht freigeben (`has_source`-Gate).

### Nebenläufigkeit (Race-Conditions)

**R12 — Doppel-Freigabe erzeugte doppelte Instanzen.** `release_order` prüfte den Status
ohne Row-Lock (Doppelklick/Retry): zwei gleichzeitige Freigaben eines produce-Auftrags
erzeugten 2× die Instanzen. Fix: Lock + Status-Frischlesen (nur die Spalte – kein
`refresh`, das bei `autoflush=False` ungeflushte Änderungen verwerfen würde).

**R13 — «Bestimmte Instanz wählen» (Deckung) reservierte ohne Lock.** Zwei gleichzeitige
Deckungen derselben freien Instanz reservierten doppelt (Überverkauf). Fix:
`with_for_update` wie in jedem anderen Allokations-Schreibpfad.

**R14 — Doppel-Refund + Provider-Wechsel.** Zwei gleichzeitige «Erstatten»-Requests
konnten ZWEI Stripe-Refunds auslösen (kein Lock, kein Idempotency-Key). Fix: Row-Lock +
Frischlesen der `stripe_refund_id`. Zusätzlich: lief der Original-Verkauf über Stripe,
verlangt die Erstattung den Stripe-Provider (vorher: stilles «erstattet» ohne Geldfluss
bei zwischenzeitlich gewechseltem Provider). Kunden-Retoure-Anfrage jetzt ebenfalls mit
Lock (Doppelklick → zwei Retoure-Unteraufträge).

**R15 — Nachbestell-Kette bei Scrap-Abschluss.** `record_scrap` prüfte den Meldebestand
NACH `recompute_completion`: schliesst der Scrap die eigene Nachbestellung ab, sah der
Idempotenz-Check sie nicht mehr und legte sofort die nächste an. Fix: Reihenfolge
getauscht. Ausserdem: `deviation.revoke` gibt die Subjekt-Bindung ans Original zurück
(statt `None`), wenn der Eltern die Instanz noch reserviert hält; `_can_supply` existiert
nur noch einmal (`supply`, von `replenishment` importiert).

---

## 2. Geprüft und in Ordnung (Auszug)

- **`ensure_supply`**: rekursiv/idempotent/zyklensicher bestätigt (Kette `chain | {art_id}`,
  Eltern-Lock, `_existing_open_supply` je Eltern+Artikel; A→B→A wird auditiert übersprungen).
- **Reservierungs-Lebenszyklus**: jeder Erzeuger hat einen Löser an allen Terminalzuständen
  (Abschluss, Abbruch/Ersetzen/Deaktivierung, Scrap `release_all`, Verkauf `consume`);
  kein struktureller Leak gefunden (nur die o. g. Race-Lücken).
- **Abbruch-Mechanik**: Antrag→Folgeauftrag→Freigabe-Vollzug inkl. `revoke` nur im Entwurf;
  `apply_abort_on_release` self-guarded; Nachschub-Kinder laufen bewusst weiter (Output →
  freier Bestand). Eltern-Pause blockiert alle sechs Schritt-Endpunkte (`_assert_not_paused`).
- **Stripe-Webhook**: `fulfill_intent` mit `with_for_update` + Status-Guards (Doppel-
  Zustellung sicher); Signaturprüfung hart; FIFO-Allokation überall mit Row-Lock.
- **Abo-Kündigung**: Stripe-first, lokal erst nach Erfolg; Kette wird deaktiviert.
- **`legal.resolve`/`sales._canonical`**: Ersetzungs-Ketten zyklensicher, Entwurf-Nachfolger
  korrekt übersprungen. Fehlende AGB-Auflösung sperrt niemanden aus (kein Admin-Lockout).
- **Teil-Erstattung**: `frac`-Mathematik je Position konsistent (gleiche Währungsbasis).

---

## 3. Grosse Folgethemen — Stand der Umsetzung (Nachtrag 2026-07-14)

**Alle Punkte ausser Nr. 2 sind umgesetzt** (gleicher Branch, Regressions-Guards in
`tests/test_review_followups.py`):

1. **Teilverkaufte Charge → Slice-Retouren umgesetzt.** Der Event-Strom IST das
   Slice-Ledger (`process.sold_amounts_for_order`): eine Bestellung über eine Chargen-
   Teilmenge ist jetzt retournierbar (`customer_returns._return_subjects` nimmt neben
   `sold`-Instanzen auch die Slice-Quellen auf); die Rückgabe bucht die verkaufte Menge
   **mengengenau in die Original-Charge zurück** (`return_subjects_to_stock`, event-
   idempotent, erst nach quittierter Rückgabe-Bewegung); die Rest-Charge wird bei der
   Retoure-Bewegung nicht umgelagert (`movable_instances`: nur `sold` wird bewegt).
   *Weiterhin offen (bewusst): eine eigene physische Repräsentation der ausgelieferten
   Teilmenge (Kind-Slices) – der Event-Strom deckt Retoure + Rückverfolgung ab.*
2. **Fehlgeschlagener Schritt ist terminal — BEWUSST ZURÜCKGESTELLT** (einziger offener
   Punkt): braucht ein «Schritt wiederholen»-Design (neue Fachzeile, alte bleibt Historie).
3. **Consent-Gate serverseitig erzwungen:** `consent.assert_acknowledged` (403) am
   Shop-Checkout, an der Retoure-Anfrage und an der Lieferanten-Offerte
   (`PATCH …/purchase`, nur Rolle supplier – Personal bleibt arbeitsfähig).
4. **`doc_visibility` als Lese-Zugriffsfilter:** `orders._doc_content_visible` filtert den
   Dokument-Inhalt im Auftrags-Embed für Nicht-Personal (public/parties/internal); eine
   benannte Partei liest immer.
5. **Benutzer-Identität:** deaktiviert = **403 beim Login** statt stiller Neuanlage
   (keine verwaisten Objektnummern-Referenzen mehr); Reaktivierung als bewusste
   Admin-Aktion (`POST /admin/users/{id}/reactivate` + Knopf in der Benutzerverwaltung).
6. **Produktabo-Auto-Fulfillment:** `invoice.paid` gibt den von `_spawn_recurrence`
   angelegten Entwurfs-Nachfolger frei und verbucht seinen Verkauf als bezahlt
   (idempotent; Zyklus-1-Rechnung/Retries treffen den bereits bezahlten Auftrag;
   `ensure_supply` für make-Artikel). Grenzfall dokumentiert: ist der Vorzyklus bei
   Rechnungseingang noch nicht abgeschlossen, zieht dessen Abschluss den Folgeauftrag nach.
7. **CheckoutIntent-Reaper:** `sales.reap_stale_intents` (24 h) im Wartungs-Sweep
   (`POST /erp/maintenance/sweep`, `SweepResult.reaped_intents`) – verlassene Warenkörbe
   geben ihre stock-Reservierungen frei (manual-Provider/verlorene expired-Webhooks).
8. **Parteien-Substitution:** `POST …/document/substitute-signer` (Personal, auditiert) –
   das offene (pending/abgelehnte) Signoff wandert auf eine neue aktive Person; Position/
   Aktion bleiben, geleistete Unterschriften nie; wirkt auf den materialisierten Layer,
   nicht auf die eingefrorene Schritt-Deklaration.
9. **`legal_ack_config` entfernt** (Modell/Schemas/FE + Migration 075) – die Pflicht ist
   hart verdrahtet, Rollen-Publikum läuft über `doc_audience`.
10. **Kleineres erledigt:** Preis-Pin committet keine fremden Session-Änderungen mehr
    (flush, wenn anderes im Puffer); `_audience_obligations` lädt Versions-Instanzen
    batch (kein N+1 je `/consent/pending`-Poll); Settlement-Kommentar korrigiert
    (Session-Währung, nicht zwingend CHF); Alt-Beleg-Refund ohne Snapshot wird bei
    Mehrpositionen-Kauf mit 409 abgelehnt statt den ganzen PaymentIntent zu erstatten.
