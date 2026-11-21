# Wiederkehrende Aufträge – Runde 1: Fundament (08.11.2026)

Projektakte `docs/konzept/wiederkehr.md` (Bauplan §8, Runde 1 = Schritte 0–2).

## Was gebaut wurde

- **Soll notiert** (Schritt 0): `SYSTEM_LOGIC.md` §5.10 (W1–W9, die Sätze der Schlaufe für
  Runde 2), T7e und U6c neu, PROCESS_CORE §12.2 neu.
- **`Verkauft` ist ein regulärer Start** (V1): `statuses.REGULAR_STARTS = {Freigegeben,
  Verkauft}`; `order_state.deviation_flags` vergleicht gegen diese Menge. Ein Service am
  Kundenstück und eine Retoure tragen kein Abweichungs-Zeichen mehr. Der Hinweis im Entwurf
  (`definition-lines.tsx`) sagt «ein regulärer Start».
- **Bewusst NICHT umgestellt:** Verbrauch (`consumption._free`) nimmt ausdrücklich nur
  `Freigegeben` (vorher über `START_BEFORE`, das jetzt nur noch den Rand-Übergang benennt); FIFO
  liest `IN_STOCK_UNIT_STATUSES` (ohne `Verkauft`). Ein Kundenstück wird nie vorgeschlagen und nie
  verbaut.
- **Preise als Vorgabe im Zahlungsmodul** (allgemein, nicht nur für die Schlaufe):
  `Beleg.PRICES` – je Artikel ein Einzelpreis, netto, in der Hauswährung, nur bei einer Einnahme,
  streng geprüft (`_clean_prices`: Liste, Artikel, einmal je Artikel, Betrag ≥ 0, höchstens 50).
  Der Beleg übernimmt ihn (`voucher_head.preset_prices` → `sync_lines`), zeigt ihn fest
  (`fixed_price`, punktiert, Grund im Hover) und weist das Verb `price` mit einem anderen Betrag
  ab; die Währung bleibt (kein Umrechnen). Kein Steuersatz in der Vorgabe – den entscheidet die
  Anschrift. Editor: «Preise» unter den Vorgaben, nur bei einer Einnahme.

- **Zwei Wächter angeschlagen und nachgezogen:** (1) «Der Editor verzweigt nicht auf die
  Richtung» (`test_source_beleg`) – der Editor fragt jetzt die Eigenschaft
  `VOUCHER_DIRECTION[…].weQuote` (gespiegelt von `Direction.quoted_by`, neu im Spiegel-Test
  `test_frontend_mirrors`), nie `direction === 'in'`. (2) «Die Abweichungsregel vergleicht mit
  dem Regelstart» (`test_source_process`) – sie prüft jetzt `REGULAR_STARTS` statt des alten
  Namens; die Regel (eine Menge, kein einzelner Status) bleibt dieselbe.

## Gemessen

- Backend: alle Tests grün (vorher 874, dazu 4 neue und 2 erweiterte).
- Gegenproben: Verbrauch auf `REGULAR_STARTS` umgestellt → `test_sold_units_are_never_offered_or_consumed`
  schlägt an; Preissperre im Verb `price` entfernt → `test_module_price_is_fixed_on_the_voucher`
  schlägt an.
- Frontend: `type-check`, `lint`, `npm test` grün; Typen und `openapi.json` neu erzeugt.

## Verworfen

- Eine Prüfung «Währung bleibt» im Test: bei einer Inlandsanschrift weist schon `can` den
  Währungswechsel ab, der Test hätte die neue Sperre gar nicht erreicht. Die Sperre bleibt als
  Absicherung für Lieferungen ins Ausland, ohne irreführenden Test.
- Den Preis an einer freien Zeile (ohne Artikel) vorzugeben: der Beleg kennt heute nur Zeilen je
  Artikel des Auftrags; eine Pauschale ist ein Artikel (z. B. «Anfahrt»).
