# Retoure, Gutschrift und Teilkorrektur — Logikanalyse

**Stand:** 17.09.2026 · **Geltungsbereich:** Zahlungsmodul (`beleg`) · **Keine Code-Änderung.**

> ## ⚠ ÜBERHOLT durch «Der Beleg IST die Rechnung» (19.09.2026)
>
> Diese Analyse beschreibt das Modell, in dem ein Beleg **mehrere** Forderungszeilen
> tragen konnte. Seit Migration `138` ist der Beleg **die** Rechnung
> (`docs/konzept-eine-rechnung-je-modul.md`, PROCESS_CORE §9.15q), und eine Korrektur ist
> ein **eigener Beleg in einem eigenen Modul** – dort, wo die Ware zurückkommt.
>
> **Drei der hier geplanten Arbeiten entfallen damit ersatzlos**, weil die Positionen der
> Gutschrift aus den zurückkommenden Stücken entstehen (*die Warenlogik ist die
> Mengenkontrolle des Geldes*):
>
> | Hier geplant | Entfällt, weil … |
> |---|---|
> | §1 Teilkorrektur mit Positionsauswahl `[{line_id, quantity}]` | die Teilmenge **ist** die zurückgenommene Ware |
> | §2 Gutschrift ohne Positionsbezug (`split_at` mit freiem Betrag) | es gibt immer Positionen – die der zurückkommenden Stücke |
> | §6 Summenregel «Σ Gegenbuchungen ≤ Betrag» | man kann nicht mehr zurücknehmen, als geliefert wurde |
>
> **Was weiter gilt:** die Referenzpflicht aus MWSTG Art. 26 (sie steht jetzt als
> `corrects_id` und als Satz «Korrektur zu …» auf dem Papier), die Stripe-Grenze und die
> Trennung *Ware · Forderung · Geld*. **Nicht als Vorlage verwenden**, ohne §9.15q daneben
> zu lesen.

Randbedingungen, die für jede Antwort unten gelten: genau **zwei gespeicherte Entitäten**
(Beleg = `voucher_entries.kind = charge`, Zahlung = `kind = payment`), **kein Belegtyp**,
das **Vorzeichen** entscheidet, der **Saldo ist immer abgeleitet**, **kein Grund-Feld**
(#1021), und kein Sonderweg je Fall — Retoure, Reklamation, Storno und Gutschrift
durchlaufen denselben Mechanismus. Physische Vorgänge gehören in die bestehende
Auftrags-/Einzelinstanzlogik, nie hierher.

---

## 1 · Teilkorrektur ohne Handrechnen

Heute nimmt `reverse` immer den **vollen** Betrag (`amount=-entry.amount`, `vat` gespiegelt).
Empfehlung: `reverse` bekommt eine **optionale Positionsauswahl** `[{line_id, quantity}]`;
daraus rechnet `vo.split_for` die Steuer je Satz wie beim Stellen der Rechnung.
Ohne Auswahl bleibt es die volle Gegenbuchung — der heutige Weg, unverändert.
Ein **freier Teilbetrag ohne Positionsbezug** bleibt möglich (`amount`), dann gilt §2.
Gerechnet wird nie im Browser: derselbe Dienst, dieselbe Rundung je Satz auf der Summe.

## 2 · Gutschrift ohne Positionsbezug

Ja, sie muss es geben — «eines von zehn, unklar welches» ist der Normalfall.
Empfehlung: **Betrag + Steuersatz genügen** (`split_at`, existiert bereits für die
Ausgabe-Richtung). Es entsteht dieselbe Zeile wie in §1, nur ohne `line_id`.
Ein erzwungener Positionsbezug wäre eine erfundene Genauigkeit: welches Stück
zurückkommt, sagt der **Auftrag** (Einzelinstanz), nicht der Beleg.
Fehlt der Satz und gibt es genau einen auf dem Originalbeleg, wird dieser vorbelegt.

## 3 · Retoure als Prozess — welche der drei Varianten

**Empfehlung: (b) — physischer Retourenauftrag, Korrekturbeleg im Originalauftrag.**
Der Rückfluss der Ware ist ein ganz gewöhnlicher Auftrag, der die Stücke greift (*das
Greifen IST die Rücknahme*, und weil sein Start vom Regelstart abweicht, ist er
automatisch eine dokumentierte Abweichung). Das Geld bleibt, wo die Forderung steht.
(a) scheidet aus: ein abgeschlossener Auftrag müsste wieder laufen — er ist Vergangenheit.
(c) scheidet aus: ein zweites Zahlungsmodul in einem anderen Auftrag führte zu **zwei**
Saldi über dieselbe Forderung, und `reverses_id` zeigte über eine Auftragsgrenze.

## 4 · Referenzpflicht auf den Originalbeleg

**Ja, zwingend** — `reverses_id` ist bereits `NOT NULL`-Pflicht bei `reverse` und bleibt es.
MWSTG Art. 26 verlangt die eindeutige Identifikation des Leistungserbringers, des
Empfängers, der Leistung und des Entgelts; eine Korrektur, die nicht sagt, **welches**
Entgelt sie mindert, ist keine Rechnungskorrektur, sondern eine zweite Rechnung mit
negativem Vorzeichen. Zudem lebt je Modul genau **eine** Forderung (#866) — ohne Referenz
liesse sich §6 gar nicht durchsetzen.
Die Referenz ist zugleich der Ersatz des gestrichenen Grund-Felds.

## 5 · Stripe — Grenze und Konsequenz

Eine Rückerstattung referenziert immer die ursprüngliche Zahlung und kann sie nie
übersteigen; das ist seit #1018 durchgesetzt (`refundable_amount` je Zahlung).
**Konsequenz für einen anderen Auftrag: keine.** Erstattet wird die **Zahlung**, nicht der
Beleg — `refund_online` steht an der Zahlungszeile, und die liegt im Originalauftrag.
Ein Retourenauftrag (§3b) erstattet darum nie selbst; er bewegt Ware.
**Korrekturbetrag > Kartenzahlung** (teils bar, teils Karte): die Karte gibt höchstens
ihren Rest zurück, der Überhang ist eine **gewöhnliche negative Zahlung** (bar/Überweisung).
Zwei Zeilen, ein Saldo — kein Sonderfall, weil Forderung und Geld getrennte Achsen sind.

## 6 · Mehrere Korrekturen nacheinander

Regel: **Σ aller Gegenbuchungen zu einem Beleg ≤ dessen Betrag.**
Durchgesetzt in `_reverse` (die Tür) und gespiegelt in `can` (der Knopf) — dieselbe Zahl,
zwei Formen. Die heutige Sperre «diese Zeile ist bereits storniert» wird dadurch **ersetzt**,
nicht ergänzt: sie ist der Sonderfall «Rest = 0».
Gerechnet als `entry.amount − Σ |amount| der Zeilen mit reverses_id = entry.id` — eine
Ableitung, keine Spalte. Ist der Rest null, fehlt der Knopf und die Tür weist mit der
Restzahl ab.

---

## Wenn das, dann das

1. Ware kommt zurück → **neuer Auftrag**, greift die Stücke (Abweichung entsteht von selbst).
2. Ware kommt **nicht** zurück (Kulanz) → Schritt 1 entfällt, sonst identisch.
3. Beleg mindern → `reverse` am Originalbeleg, mit Positionen **oder** mit Betrag + Satz.
4. Rest = 0 → kein Knopf, Tür weist ab. Rest > 0 → Gegenbuchung mit eigener Nummer.
5. Beleg war **unbezahlt** → fertig; der offene Betrag sinkt.
6. Beleg war **bezahlt** → offener Betrag wird negativ = Guthaben.
7. Guthaben, per Karte gezahlt → `refund_online` an **der** Zahlung, höchstens ihr Rest.
8. Guthaben, bar/Überweisung oder Überhang → **negative Zahlung** erfassen.
9. Guthaben bleibt stehen → nichts tun; verrechnet wird nie automatisch.
10. Zweite Korrektur nötig → zurück zu 3; die Summenregel §6 ist die einzige Grenze.

## Nötige Modelländerungen (Stichworte)

- `VoucherUpdate`: `lines` (`[{line_id, quantity}]`) und `vat` auch für `reverse` zulassen.
- `_reverse`: Betrag aus Positionen **oder** aus `amount`; Steuer über `split_for`/`split_at`.
- `_reverse`: Summenregel (`reversed_on(entry)` als Ableitung) statt «bereits storniert».
- `can`: `reverse` nur, solange ein Beleg mit Rest > 0 dasteht (Auskunft **und** Tor).
- `VoucherEntryOut`: `reversible` (Restbetrag) je Beleg-Zeile — wie `refundable` je Zahlung.
- **Keine neue Tabelle, keine neue Spalte, kein neuer Status.**

## Benannt statt stillschweigend

Ohne Grund-Feld lässt sich **nicht** maschinell unterscheiden, ob eine Gutschrift aus
Retoure, Mangel oder Kulanz entsteht. Das ist Absicht (#1021) und für die Buchhaltung
ohne Folge: der Unterschied steht in der **Ware** (kam sie zurück? → Auftrag ja/nein),
nicht im Geld. Braucht die Auswertung ihn später doch, ist die Antwort ein **Bericht über
die beiden Achsen**, kein Feld am Beleg.
