# Eine Rechnung je Zahlungsmodul — der Beleg IST die Rechnung

**Status:** Konzept, freigegeben zur Umsetzung · **Stand:** 19.09.2026
**Geltungsbereich:** Zahlungsmodul (`beleg`) — `domain/voucher` · `services/voucher` ·
`schemas/voucher` · `models/voucher` · `beleg-work.tsx`
**Ersetzt:** #866 (die Regel als Zählung), #823/#824/#841/#842 (`reverse` am Modul),
#1010–#1017 teilweise (die Aufteilung *innerhalb* eines Moduls)

---

## 0 · In vier Sätzen

1. **Ein Zahlungsmodul trägt genau eine Rechnung** — nicht als Regel, die jemand
   durchsetzt, sondern weil der Beleg selbst die Rechnung **ist**.
2. **Vor dem Versenden zurücknehmbar, danach unveränderlich.**
3. **Jede Minderung ist ein eigener Beleg in einem eigenen Zahlungsmodul**, mit Verweis
   auf die Rechnung, die sie mindert — und sie steht in dem Auftrag, in dem der Vorfall
   passiert (Retoure → Retourenauftrag).
4. **Zahlungen bleiben, wie sie sind**: beliebig viele, alle auf die eine Rechnung
   ihres Moduls.

> **Der Kern in einem Satz:** heute ist ein Beleg ein *Behälter* für Rechnungen; danach
> **ist** er eine.

---

## 1 · Der Befund — die Rechnung steht heute zweimal da

```
Modul → Beleg (Partner · Positionen · MWST · Währung · Fristen · Incoterm · Aussteller)
           └─ Zeile «Rechnung»  (Betrag · MWST · Nummer · Datum · Fälligkeit · Leistungsdatum)
           └─ Zeile «Storno»    (negativ, reverses_id)
           └─ Zeile «Gutschrift»(negativ)
           └─ Zeile «Zahlung»   …
```

Betrag, MWST, Nummer, Datum und Fälligkeit stehen **auf beiden Ebenen**. Die
Rechnungszeile (`voucher_entries.kind = 'charge'`) ist eine Kopie des Belegs, der sie
enthält — genau die Fehlerform, die der Neuaufbau bei den Positionen schon einmal
beseitigt hat (dort gab es sie dreimal). Bei der Forderung ist sie stehengeblieben.

Daraus folgt die gefühlte Unordnung, und sie ist zählbar:

| Heute | Danach |
|---|---|
| `live_charge` muss *zählen*, was eine «Forderung nach aussen» ist (nicht die Gegenbuchung, nicht die stornierte, nicht die negative) | es gibt genau eine, strukturell |
| `_charge` weist die zweite positive Forderung mit einem sechszeiligen Satz ab | der Knopf existiert nach der Rechnung nicht mehr |
| `_charge_for_payment` · `_split` · `allocate` · `paid_map` beantworten «welche Rechnung meint diese Zahlung» | die Frage hat genau eine Antwort und wird nicht gestellt |
| `reverse` heisst je nach Bezahlstatus «Stornieren» oder «Gutschrift» | zwei verschiedene Sachverhalte, zwei verschiedene Wege |

**Und ein Verb macht zwei Dinge.** Das ist der zweite Teil des Befunds:

* **Storno** = *diese Rechnung war falsch, sie gilt nicht.* Derselbe Vorgang, kein neues
  Geschäft, meist vor jeder Zahlung.
* **Gutschrift** = *die Rechnung war richtig, die Leistung wurde gemindert.* Ein **neuer**
  Geschäftsvorfall — eigenes Datum, eigene Ware, eigene Steuerperiode.

`reverse_word` hält die beiden heute mit **einer** Zahl auseinander (`paid > 0`). Das ist
die Stelle, an der zwei Sachverhalte so tun, als wären sie einer.

---

## 2 · Das Modell danach

### 2.1 Der Beleg ist die Rechnung

`vouchers` trägt bereits Partner, Positionen, Währung, Fristen, Incoterm und Aussteller.
Neu trägt er auch, was die Rechnungszeile trug:

| Spalte | Bedeutung |
|---|---|
| `billed_on` | Rechnungsdatum. `NULL` = noch keine Rechnung gestellt |
| `due_on` | Fälligkeit = `billed_on` + vereinbarte Zahlungsfrist |
| `number` | Belegnummer (`<Auftragsnummer>-<laufend>`, wo **wir** nummerieren; sonst die erfasste des Partners) |
| `issued_on` | wann sie hinausging. `NULL` = noch im Haus |
| `amount` | Rechnungsbetrag **brutto**, eingefroren |
| `vat` | Steueraufteilung, eingefroren (JSONB, wie heute an der Zeile) |
| `service_date` | Leistungsdatum (MWSTG Art. 26 Bst. c), aus dem Prozess abgeleitet |
| `corrects_id` | FK → `vouchers.id`: **welchen Beleg dieser mindert** |

Das sind exakt die acht Angaben, die heute an `voucher_entries` hängen — eine Ebene
höher, und damit **ohne Möglichkeit, zweimal vorzukommen**.

> **Warum eingefroren und nicht gerechnet?** Die Positionen stehen ab der Zusage fest
> (`sync_lines` läuft nur in `offer`, `price` ist ein Verb der Stufe `offer`) — die Summe
> wäre also stabil. Die **Steueraufteilung** ist es nicht: eine künftige Änderung an
> `vat_split` oder am Katalog änderte rückwirkend die Steuer einer längst gestellten
> Rechnung. Ein Beleg behält, was auf ihm stand.

### 2.2 `voucher_entries` trägt nur noch Zahlungen

`kind` entfällt aus dem Modell (die Spalte bleibt, Zwei-Deploy-Regel). Jede Zeile ist eine
**Zahlung**: Betrag (negativ = Erstattung), Buchungsdatum, Referenz, Zahlungsart.

Damit entfallen ersatzlos: `charge_id` · `voucher_allocations` · `allocate` · `paid_map` ·
`_split` · `_charge_for_payment` · `open_charges` · `live_charge` · `charge_state`
(aufgegangen in `balance_state`) · `reverse_word` · `settle_charge`.

### 2.3 Drei Stufen statt zwei

```
offer     Angebot        schreiben · anfragen · zusagen
agreed    Auftrag        → Rechnung stellen
billed    Rechnung       → versenden · Zahlungen erfassen
done / cancelled         Ausgänge (unverändert)
```

**Die dritte Stufe ist keine Wiederholung des Fehlers von damals.** «Abgeschlossen» war
ein *Zustand* in einer Reihe von *Schritten* — man tat nichts, um ihn zu erreichen. Eine
Rechnung zu stellen ist eine **Handlung mit einem unumkehrbaren Ergebnis**: eine Nummer
ist vergeben, die Steuer steht fest, ein Papier existiert. Das ist dieselbe Art Schwelle
wie `agreed`.

### 2.4 Die beiden neuen Verben

| Verb | Stufe | Wirkung |
|---|---|---|
| `bill` | `agreed` | Nummer vergeben, Betrag und Steuer einfrieren, Datum und Fälligkeit setzen → `billed` |
| `issue` | `billed` | `issued_on` setzen — *«Rechnung ist versendet»*. Danach unveränderlich |
| `unbill` | `billed`, solange `issued_on IS NULL` **und** keine Zahlung eingegangen | die Rechnung zurücknehmen → zurück auf `agreed` |

`unbill` ist die Gegenhandlung zu `bill` und folgt derselben Anatomie wie `unask` — *jede
Zusage nach aussen hat ihre Gegenhandlung an derselben Stelle*. Sie ist ein **Soft-Delete
mit Protokoll**, kein Löschen: die zurückgenommene Rechnung bleibt als inaktive Zeile
stehen und **verbraucht ihre Nummer**.

> **Warum die Nummer verbraucht ist.** Eine Rechnungsserie muss lückenlos *belegbar* sein,
> nicht lückenlos *durchgezählt*: zu jeder vergebenen Nummer muss ein Datensatz
> existieren. Eine zurückgenommene, nie versendete Rechnung ist genau das — ein Datensatz
> mit Vermerk «zurückgenommen am …». Die Nummer beim Versenden statt beim Stellen zu
> vergeben wäre die Alternative und ist falsch: man druckt und prüft ein Papier, auf dem
> die Nummer schon steht.

> **Warum `issued_on` eine Spalte braucht.** Die Hausregel lautet «der Moment braucht
> keine Spalte» — hier gibt ihn nichts anderes her: eine Zustellung (PDF, E-Mail) ist
> nicht gebaut. Sobald sie es ist, setzt **sie** das Datum, und der Knopf verschwindet.
> Eine Frist («innerhalb fünf Minuten») wäre eine erfundene Regel mit einer Uhr darin.

### 2.5 Der Korrekturbeleg

Ein Beleg mit gesetztem `corrects_id` **mindert** den genannten Beleg.

* **Die Positionen tragen positive Preise** — niemand tippt ein Minus. «3 × Getriebe à
  200» ist die Aussage, und sie ist MWST-korrekt (Positionen, Satz, Steuerbetrag).
* **`bill` dreht das Vorzeichen**: wo `corrects_id` gesetzt ist, wird `amount` negativ
  gespeichert und die Steueraufteilung gespiegelt. Danach rechnet **jede** Zahl
  vorzeichenrichtig, ohne eine einzige Fallunterscheidung beim Lesen.
* **Der Verweis steht auf dem Papier**: «Korrektur zu `<Nummer des Originals>`» — eine
  **Ableitung** über `corrects_id`, kein zweites Feld. MWSTG Art. 26 verlangt die
  eindeutige Identifikation der Leistung und des Entgelts; ohne Verweis wäre es eine
  zweite Rechnung mit negativem Vorzeichen.
* **`corrects_id` darf über Auftragsgrenzen zeigen** — das ist der Kern dieser Runde.

---

## 3 · Die Retoure — warum das Modell dadurch *kleiner* wird

> *«Gerade bei Retouren wäre der Warenverkehr getrennt von der monetären Abwicklung. Ich
> müsste im originalen Zahlungsmodul stornieren — aber dort, wo das Geschehen ist, soll
> ich es auch abwickeln können.»*

Steht der Gutschriftsbeleg im **Retourenauftrag**, entstehen seine Positionen **von
selbst** aus den Stücken, die zurückkommen (`sync_lines` liest die Einzelinstanzen vor dem
Modul). Der Auftrag greift drei Getriebe → der Beleg hat drei Getriebe. Und er kann keine
fünf greifen, wenn nur drei existieren.

> **Die Warenlogik ist die Mengenkontrolle des Geldes.**

Damit fällt ersatzlos weg, was `ANALYSE_RETOURE_20260917.md` als Arbeit auflistet:

| Dort geplant | Entfällt, weil … |
|---|---|
| §1 Teilkorrektur mit Positionsauswahl `[{line_id, quantity}]` | die Teilmenge **ist** die zurückgenommene Ware |
| §2 Gutschrift ohne Positionsbezug (`split_at` mit freiem Betrag) | es gibt immer Positionen — die der zurückkommenden Stücke |
| §6 Summenregel «Σ Gegenbuchungen ≤ Betrag» | man kann nicht mehr zurücknehmen, als geliefert wurde |
| `reversible` je Zeile, `reversed_on` als Ableitung | es gibt keine Gegenbuchung *an* einer Zeile mehr |

**Physische und monetäre Abwicklung stehen danach am selben Ort.** Genau das war die
Anforderung.

---

## 4 · Die drei Korrekturfälle — und wie jeder läuft

| Fall | Weg | Bemerkung |
|---|---|---|
| **Retoure** (Ware kommt zurück) | Abweichungsauftrag greift die Stücke → Zahlungsmodul mit `corrects_id` → Positionen entstehen aus der Ware | der Musterfall |
| **Kulanz / Mangel** (Ware bleibt beim Kunden) | derselbe Auftrag, er greift dieselben Stücke; sie laufen durch, ohne bewegt zu werden | **Gewinn**: im Log steht danach, *welche* Stücke betroffen waren — das steht heute nirgends |
| **Rechnungsfehler, noch nicht versendet** | `unbill` → korrigieren → `bill` | spurlos, kein Beleg nach aussen |
| **Rechnungsfehler, bereits versendet** | wie Kulanz: Korrekturauftrag über die betroffenen Stücke | die eine Reibung, siehe §7 |

**Die Entscheidung «Storno oder Gutschrift» trifft damit niemand mehr** — sie fällt aus
dem Zeitpunkt heraus: vor dem Versenden gibt es nur `unbill`, danach nur den
Korrekturbeleg.

---

## 5 · Was das mit den Zahlungen macht

**Nichts.** Eine Zahlung gehört zu ihrem Modul, und dort gibt es genau eine Rechnung — die
Zuordnung ist trivial statt eine Rechenaufgabe.

* `balance_of(voucher)` = `amount` (bzw. `None`, solange nicht gestellt) − Σ Zahlungen.
* *offen · fällig · überfällig · Guthaben* bleiben Ableitungen, null neue Spalten.
* `refund_online` · `refundable_amount` · `refunded_on` · der Webhook: **unverändert** —
  eine Erstattung war schon immer eine negative **Zahlung**, kein Beleg.
* `pay_online` · `transfer_info` · die Swiss QR-Rechnung: unverändert, nur fragen sie
  künftig den **Beleg** statt `settle_charge`.

### ⚠ Die eine Funktion, die dabei zurückgenommen wird

**Die Sammelzahlung innerhalb eines Moduls** (`voucher_allocations`, #1010–#1017) wird
gegenstandslos: sie teilt eine Zahlung auf mehrere Rechnungen **desselben Belegs** auf,
und davon gibt es künftig genau eine. Die Tabelle prüft heute ausdrücklich, dass jeder
genannte Beleg zum selben Voucher gehört — der Fall, den sie beantwortet, entsteht nicht
mehr.

**Der Fall selbst bleibt real**: eine Überweisung über 1'500 begleicht eine Rechnung über
1'000 und eine über 500. Nach diesem Umbau liegen die beiden zwingend in **verschiedenen
Modulen**, also ist es eine Zuordnung über Modulgrenzen — das ist die **offene-Posten-
Liste** je Partner, und die ist Buchhaltung (§7).

**Empfehlung:** die Tabelle jetzt **nicht** umbauen, sondern stilllegen (Mapping
entfernen, Spalten nach der Zwei-Deploy-Regel fallen lassen) und den Fall als benannten
offenen Punkt führen. Zwei Zahlungen zu erfassen, wo im Kontoauszug eine steht, ist bis
dahin eine Zeile mehr auf dem Bildschirm — keine falsche Zahl.

*Diese Konsequenz stand nicht in der Vorbesprechung; sie fällt aus dem Modell heraus und
gehört darum ausdrücklich in die Freigabe.*

---

## 6 · Die Bilanz

**Fällt weg** (Backend): `live_charge` · `open_charges` · `charge_state` ·
`_charge_for_payment` · `_split` · `allocate` · `paid_map` · `_paid_on` · `_open_of` ·
`_reversal_of` · `reverse_word` · `settle_charge` · `credit_only` · das Verb `reverse` ·
`VoucherAllocation` · `VoucherEntry.kind` / `charge_id` / `due_on` / `vat` /
`service_date` / `reverses_id` (Mapping) · `VoucherAllocationOut` ·
`VoucherEntryOut.reverse_word` / `allocations` / `open` / `state*` / `refundable`-Logik
an der Zeile.

**Fällt weg** (Frontend): die Unterscheidung `charge`/`payment` in der Geld-Zeile · der
Zustandspunkt je Rechnung (er wandert an den Beleg) · der «Korrigieren»-Knopf an der
Rechnung · die Aufteilungs-Eingabe · `negate()`.

**Kommt dazu:** acht Spalten an `vouchers` (die acht, die die Zeile verliert) · drei
Verben (`bill` · `issue` · `unbill`) · eine Stufe (`billed`) · ein Endpunkt, um den zu
korrigierenden Beleg zu finden · ein Abschnitt im Beleg, der die Korrektur ausweist.

**Netto:** deutlich weniger Code, eine Regel weniger (die Zählung), eine Entität weniger
(die Forderungs-Zeile), eine Fallunterscheidung weniger (Storno ↔ Gutschrift).

---

## 7 · Was offen bleibt — benannt, nicht versteckt

1. **Die offene-Posten-Liste je Partner.** «Was schuldet mir dieser Kunde insgesamt» hat
   nach diesem Umbau keinen Ort mehr an *einem* Modul: Rechnung 10'000 (bezahlt) steht in
   Modul A, Gutschrift 600 (offen) in Modul B. Beide für sich sind korrekt; die Summe ist
   Debitorenbuchhaltung. Sie wäre spätestens beim zweiten Auftrag je Kunde ohnehin fällig
   — der Umbau verursacht sie nicht, er macht sie sichtbar nötig. **Mit ihr kommt die
   modulübergreifende Sammelzahlung zurück** (§5).
2. **Der reine Rechnungsfehler nach dem Versand** braucht einen Auftrag über die
   betroffenen Stücke. Das funktioniert, fühlt sich aber schief an — und ist derselbe
   offene Punkt wie «ein Beleg ganz ohne Ware» (Miete, Lohn, Gebühr): `assert_releasable`
   verlangt *mindestens eine Einzelinstanz*, also kann das System das heute auch ohne
   diesen Umbau nicht. Fällt die Regel eines Tages, fällt sie für beide.
3. **Abschliessbar ohne Rechnung?** Bleibt wie heute: `completion_problem` fragt die
   vereinbarte **Zahlungsfrist** (`prepaid`), nicht die Existenz einer Rechnung. Ware ohne
   Rechnung ist der Lieferschein-Fall und ein gültiger Ablauf.
4. **Mahnwesen, camt.053, PDF-Zustellung** — unverändert nicht in dieser Runde.

---

## 8 · Ausdrücklich verworfen

**«Nur die Regel verschärfen»** — `_charge` verbietet jede zweite Forderung, `reverse`
fliegt raus, der Rest bleibt wie er ist.

Das hätte den Wunsch mit weniger Aufwand erfüllt und wird **vollständig verworfen**: die
Doppelung aus §1 bliebe stehen, die Regel müsste weiterhin von Hand durchgesetzt werden
(und kann vergessen werden), und derselbe Umbau stünde in einem Jahr ein zweites Mal an.

---

## 9 · Die Umsetzung

### 9.1 Reihenfolge

| # | Schritt | Datei(en) |
|---|---|---|
| 1 | **Migration `138`** — acht Spalten an `vouchers`, Stufe `billed` erlaubt, Bestandsdaten hochziehen, `_COLUMN_SAFETY_NET` + `_NUMERIC_SAFETY_NET` ergänzen | `alembic/versions/138_der_beleg_ist_die_rechnung.py`, `main.py` |
| 2 | **Vokabel** — `STAGES` um `BILLED`, `stage_labels` je Richtung, Verben-Wörter, `balance_state` als einzige Zustands-Ableitung; `charge_state` entfällt | `domain/voucher.py` |
| 3 | **Modell** — acht Spalten an `Voucher`; `VoucherEntry` verliert sein Charge-Mapping; `VoucherAllocation` entfällt | `models/voucher.py` |
| 4 | **Dienst** — `bill` · `issue` · `unbill` in `VERBS`; `_charge`/`_reverse`/`_pay`-Umbau; `balance_of` liest den Beleg; `REQUIRED_FOR['charge']` → `REQUIRED_FOR['bill']` | `services/voucher.py` |
| 5 | **Schnittstelle** — `VoucherEmbed` (Rechnungsfelder am Beleg statt an der Zeile), `VoucherEntryOut` schrumpft; `stripe_pay.MONEY` folgt | `schemas/voucher.py`, `services/stripe_pay.py` |
| 6 | **Korrektur-Auswahl** — Endpunkt «welche Belege dieses Partners lassen sich korrigieren» | `routers/orders.py`, `services/voucher.py` |
| 7 | **Oberfläche** — Abschnitt «Rechnung» statt Geld-Zeilen-Liste; der Korrektur-Verweis im Belegkopf; `Fordern`/`Begleichen` bleiben als Fächer | `beleg-work.tsx` |
| 8 | **Generierte Typen** — `dump_openapi` → `generate:types` (mit den **gepinnten** Versionen) | — |

### 9.2 Die Migration im Einzelnen

**Bestandsdaten.** Für jeden Beleg mit **genau einer** lebenden positiven Forderung ohne
Gegenbuchung werden Betrag, Nummer, Datum, Fälligkeit, Steuer und Leistungsdatum an den
Beleg hochgezogen und `stage = 'billed'` gesetzt; `issued_on` bekommt `billed_on` (was
gebucht ist, gilt als hinausgegangen — die vorsichtigere Annahme).

**Alles andere** (Storno-Ketten, mehrere Forderungen) fällt auf `agreed` zurück; die
Zeilen bleiben inaktiv als Historie stehen.

> **Das ist vertretbar, weil es keine produktiven Belege gibt** — das Deployment ist
> `inexxio-dev`, die Daten sind Testdaten. Gäbe es produktive Rechnungen, wäre dieser
> Schritt eine eigene Runde mit vorheriger Sicherung.

**Verifiziert wie immer:** von null · idempotent · downgrade · re-upgrade · über das
Lifespan-Netz. Und die Suite läuft gegen die gewachsene Datenbank **und** gegen ein Schema
nur aus den Migrationen.

### 9.3 Wächter (mit ihrer Bug-Form)

| Wächter | Bug-Form, die er melden muss |
|---|---|
| `test_a_module_carries_exactly_one_invoice` | ein zweites `bill` am selben Beleg geht durch |
| `test_an_issued_invoice_cannot_be_taken_back` | `unbill` nach `issue` geht durch |
| `test_an_invoice_with_a_payment_cannot_be_taken_back` | `unbill` bei eingegangener Zahlung geht durch |
| `test_a_withdrawn_invoice_keeps_its_number` | die Nummer wird wiederverwendet |
| `test_a_correction_carries_the_reference_to_what_it_corrects` | `corrects_id` fehlt oder der Verweis steht nicht auf dem Beleg |
| `test_a_correction_may_live_in_another_order` | der Dienst weist einen Beleg aus einem fremden Auftrag ab |
| `test_a_correction_is_stored_with_a_negative_amount` | `amount` bleibt positiv, der Saldo addiert statt zu mindern |
| `test_a_correction_mirrors_the_tax_split` | die Steuer wird nicht gespiegelt |
| `test_the_frozen_tax_survives_a_price_change` | die Steuer wird beim Lesen nachgerechnet |
| `test_there_is_no_reverse_verb_at_the_module` | `reverse` steht wieder in `VERBS` |
| `test_a_payment_needs_no_allocation` | eine Zuordnungs-Tabelle wird wieder gelesen |
| `test_frontend_mirrors: …_the_invoice_lives_on_the_voucher` | die Karte baut die Rechnung wieder aus einer Geld-Zeile |

**Jeder gegen seine Bug-Form gegengeprüft** — ein Wächter, der nie anschlägt, ist von
einem kaputten nicht zu unterscheiden.

### 9.4 Messung

Wie in jeder Runde: die echte Komponente im `ModuleShell`, Chromium, 1440 · 1280 · 1024 ·
834 · 375 · 320 px, **0 px** waagrechter Überlauf über alle Beleg-Zustände (neu: *Auftrag
ohne Rechnung* · *Rechnung im Haus* · *Rechnung versendet* · *Korrekturbeleg* · *Sicht der
Gegenpartei*), und die Messung gegen ihre eigene Bug-Form gegengeprüft.

---

## 10 · Zwei Entscheidungen, die getroffen sind

1. **Woran erkennt das System, dass eine Rechnung «raus» ist?**
   → Ein Knopf **«Rechnung ist versendet»** (`issue`). Später setzt ihn die Zustellung
   selbst. Keine Zeitfrist.
2. **Wie entsteht eine Korrektur ohne Warenrückfluss?**
   → Über einen ganz gewöhnlichen Auftrag, der die **betroffenen Stücke** greift. Er
   dokumentiert damit zugleich, worauf sich die Korrektur bezieht.

**Offen zur Freigabe:** die Rücknahme der modulinternen Sammelzahlung (§5).
