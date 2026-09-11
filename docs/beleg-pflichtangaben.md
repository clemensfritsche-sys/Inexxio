# Was auf eine Offerte und eine Rechnung gehört — Soll/Ist

> **Zweck:** keine Rückfragen. Ein Beleg, der beim Empfänger eine Frage auslöst, kostet
> mehr Zeit als jedes Feld, das ihn verhindert hätte.
>
> **Massstab:** eine externe Checkliste «international gültig» (Offerte · Rechnung ·
> Aussenhandel), geprüft gegen unsere Logik. **Nicht** jede Zeile daraus ist für ein
> Schweizer KMU im Maschinenbau relevant, und nichts davon wird übernommen, was es bei
> uns schon in anderer Form gibt. Wo der Massstab etwas vorschlägt, das wir bereits
> anders und besser gelöst haben, gewinnt **unsere** Lösung — die Nummerierung ist der
> Musterfall.
>
> Stand: 11.09.2026, gegen `06b1506`.

---

## 1 · Was der Beleg heute trägt

Alles hier ist gebaut und läuft. Die Spalte «wo» ist die eine Stelle, an der es wohnt.

| Angabe | Wo |
|---|---|
| **Aussteller**: Name, Anschrift, UID/MWST-Nr. | `deal.document_head` → `DealSide.supplier` |
| **Empfänger**: Name, Anschrift | `document_head` → `DealSide.customer` (aus `billing_of`) |
| **Welche Seite welche Rolle hat** | `Direction.collects` — gilt für Ein- **und** Auszahlung ohne Fallunterscheidung |
| **Belegart** (Angebot ↔ Auftrag ↔ Storniert) | `DealEmbed.stage_label`, im Kopf |
| **Rechnungsnummer, fortlaufend** | `DealEntry.reference` = `<Auftragsnummer>-<n>`, vom Server vergeben |
| **Rechnungsdatum** | `DealEntry.booked_on` |
| **Leistungsdatum** (MWSTG Art. 26 Bst. c) | `DealEntry.service_date`, **abgeleitet aus dem Prozess** |
| **Fälligkeit** | `DealEntry.due_on`, aus der vereinbarten Zahlungsfrist |
| **Zahlungsfrist** mit Namen («Vorauszahlung», «30 Tage») | `deals.due_days` + `PAYMENT_TERMS` |
| **Lieferfrist und Liefertermin** | `quotes[].lead_days` → `_delivery` (Ableitung, null Spalten) |
| **Positionen**: Artikel, Objektnummer, Menge | `deal.lines` / `agreed_lines` — abgeleitet aus den Einzelinstanzen |
| **Spezifikation je Position** (Werkstoff, Grösse, Gewicht, Oberfläche, Zeichnung, Gefahrgut) | `services/article_fields.SPEC_FIELDS`, reist mit dem Beleg |
| **Einzelpreis netto** | `DealLine.price` |
| **Steuersatz je Position**, Steuerbetrag **je Satz auf der Summe** | `DealLine.vat` → `domain/deal.vat_split` |
| **Netto · Steuer · Total** | `Totals` (eine Aufstellung für Vorschau und Buchung) |
| **Währung**, mit den Nachkommastellen der Währung | `deals.currency` (ISO 4217), `domain/currency` |
| **Bankverbindung, Referenz (ISO 11649), Swiss QR-Rechnung** | `deal.transfer_info` + `services/qrbill`, auf Klick an der Rechnung |
| **Offener Betrag / überfällig** | Ableitung aus den Zeilen, im Kopf |
| **Gutschrift und Storno** | Gegenbuchung mit eigener Nummer und Verweis |
| **Was zu tun ist** (Artikelnummer, Link, Beschreibung) | `config.parties[].ref`, je Partner |

**Damit ist die Rechnung nach MWSTG Art. 26 schon heute fast vollständig.** Was fehlt,
steht unten — und es ist weniger, als die Checkliste vermuten lässt.

---

## 2 · Echte Lücken — und wie ich sie schliessen würde

Sortiert nach Nutzen je Aufwand. Jede Zeile nennt die **Stelle**, an der sie hingehört.

### 2.1 Pflicht-Lücken (eine Rechnung ist ohne sie angreifbar)

#### ① UID / MWST-Nummer des EMPFÄNGERS — *ein Feld wegwerfen ist teurer als eins bauen*

**Der Fund:** die Daten sind längst da (`UserProfile.uid_number`, `vat_number`,
`vat_registered`). `document_head` setzt sie trotzdem hart auf `None`, mit der
Begründung «eine UID der Gegenpartei führt das System nicht».

**Das ist schlicht falsch, und es ist mein Fehler aus der letzten Runde.** Die Spalten
stehen seit dem Fundament im Benutzer-Datensatz.

Relevant ist es genau dort, wo die Checkliste recht hat: bei **EU-B2B** muss die USt-IdNr.
des Empfängers auf der Rechnung stehen, sonst trägt das Reverse-Charge-Verfahren nicht.

**Umsetzung:** eine Zeile in `document_head` — dieselbe Regel wie bei uns
(MWST-Nummer vor blosser UID). Kein neues Feld, keine Migration.
**Aufwand: Minuten.**

#### ② Der Empfänger ist eine RECHTSPERSON, nicht die Person, die sie vertritt

**Der Fund:** `billing_of` fällt auf `people.display_name` zurück, und das ist
**person-first** («Vorname Nachname → Firma → E-Mail», Notiz #291). Im ERP ist das
richtig — man arbeitet mit Menschen. Auf einer **Rechnung** ist es falsch: Schuldner ist
die *Muster AG*, nicht *Clemens Fritsche*. Heute stimmt es nur, wenn jemand eine
Rechnungsadresse mit Firmenfeld gepflegt hat.

**Umsetzung:** eine eigene Regel **für den Beleg** (`billing_of` bekommt sie, nicht
`display_name` — die ERP-Anzeige bleibt, wie sie ist): *Firma zuerst, Person als Zeile
darunter («z. H. …»)*. Fällt die Firma weg, bleibt die Person — das ist der B2C-Fall und
korrekt.
**Aufwand: klein.** *Zwei Formen einer Regel sind in Ordnung; zwei Regeln nicht — darum
steht sie in `services/people` neben `display_name`, nicht daneben im Deal-Dienst.*

#### ③ Der Steuerhinweis bei 0 % — und warum «0 %» heute zu wenig ist

**Der Fund:** der Katalog führt **einen** Nullsatz: `("0.00", "Ohne (Export · Reverse
Charge)")`. Das sind aber **zwei verschiedene Tatbestände mit zwei verschiedenen
Pflichtsätzen** auf dem Beleg:

* Ausfuhr → «Steuerfreie Ausfuhrlieferung»
* EU-B2B-Dienstleistung → «Steuerschuldnerschaft des Leistungsempfängers» (Reverse Charge)

Ein Beleg, der nur «0 %» sagt, nennt den **Grund** nicht — und genau den verlangt der
Empfänger für seine eigene Abrechnung. Das ist eine Rückfrage, die garantiert kommt.

**Umsetzung — und sie ist die eleganteste im ganzen Papier:** der Pflichtsatz ist eine
Eigenschaft **des Steuersatzes**, nicht des Belegs. Also wird aus einer Katalogzeile
mit zwei Bedeutungen **zwei Katalogzeilen mit je ihrem Satz**:

```python
VAT_RATES = (
    ("8.10", "Normalsatz",   None),
    ("2.60", "Reduziert",    None),
    ("3.80", "Beherbergung", None),
    ("0.00", "Export",         "Steuerfreie Ausfuhrlieferung"),
    ("0.00", "Reverse Charge", "Steuerschuldnerschaft des Leistungsempfängers"),
)
```

Der Hinweis erscheint damit **automatisch**, sobald ein solcher Satz auf dem Beleg
vorkommt — kein `if`, kein Feld, keine zweite Stelle, die jemand vergisst. `vat_split`
gruppiert weiterhin nach Satz; hier muss es nach **Katalogzeile** gruppieren, weil zwei
Zeilen denselben Satz tragen.
*Der einzige Haken, benannt statt versteckt: `assert_vat` vergleicht heute auf den
Zahlenwert — der Schlüssel wird die Katalogzeile, nicht die Zahl.*
**Aufwand: klein bis mittel.**

#### ④ Rechtsform und Kontaktweg des Ausstellers

**Der Fund:** `legal_form`, `email` und `phone` stehen am Unternehmen und **nicht** im
Belegkopf. «Inexxio» statt «Inexxio AG» ist bei einer Rechnung eine unvollständige
Bezeichnung der Rechtsperson; und ein Beleg ohne Kontaktweg ist genau das Dokument, das
eine Rückfrage per Telefonbuch auslöst.

**Umsetzung:** zwei Zeilen in `document_head.supplier` (`legal_form` an den Namen,
`email`/`phone` unter die Anschrift). Daten sind da.
**Aufwand: Minuten.**

### 2.2 Die Offerte — hier fehlt am meisten

Die Karte ist als **Rechnung** weit, als **Angebot** noch nicht. Drei Dinge fehlen, und
zwei davon haben bei uns schon eine fertige Form.

#### ⑤ Gültigkeitsdauer des Angebots

**Der Fund:** fehlt vollständig. Ein Angebot ohne Befristung bindet **unbefristet** —
das ist das einzige Thema dieser Liste mit echtem kaufmännischem Risiko: ein Preis von
vor achtzehn Monaten ist heute einklagbar.

**Umsetzung — kein neuer Mechanismus:** wir haben die Form längst zweimal. Eine Frist ist
bei uns **eine Zahl in Tagen mit Namen** (`TermField`, `PAYMENT_TERMS`/`LEAD_TERMS`), und
das Datum ist die **Ableitung**. Also:

* `quotes[].valid_days` neben `lead_days` und `payment_days` (JSONB — keine Migration)
* `VALID_TERMS = ((30, "30 Tage"), (14, "14 Tage"), (90, "3 Monate"), …)`
* «gültig bis» = Angebotsdatum + Frist, gerechnet wie `_delivery`

Das ist die dritte Frist in einer Reihe, die schon zwei trägt — sie erbt Feld,
Darstellung und Vorgabewerte, ohne eine eigene Zeile Oberfläche.
**Aufwand: klein.**

#### ⑥ Angebotsdatum

**Der Fund:** eine Angebotszeile trägt **kein Datum**. Ohne es lässt sich ⑤ nicht
rechnen, und der Empfänger kann nicht sagen, worauf er antwortet.

**Umsetzung:** `quotes[].quoted_on`, gesetzt beim Offerieren. Dieselbe Stelle wie
`agreed_on` beim Zuschlag.
**Aufwand: Minuten.**

#### ⑦ Angebotsnummer — **bewusst KEINE neue Serie**

Die Checkliste verlangt eine eigene Offertnummer (`OFF-2026-001`). **Wir erfinden keine.**

Der Auftrag hat eine **Objektnummer**, das Modul ist ein Schritt darin, und die
Rechnungsnummer leitet sich bereits daraus ab (`<Auftragsnummer>-<n>`). Eine zweite
Serie daneben wäre ein zweiter Nummernraum für dieselbe Sache — genau das, was der
universelle 9-stellige Nummernkreis abschafft.

**Die Objektnummer des Auftrags IST die Angebotsreferenz.** Sie steht schon im Kopf.
Dass mehrere Partner angefragt sein können, macht sie nicht mehrdeutig: jede Gegenpartei
sieht ausschliesslich ihre eigene Zeile.
**Aufwand: null — nur als Entscheidung festhalten.**

### 2.3 Was der Kunde von uns verlangt, damit er zahlt

#### ⑧ «Ihre Bestellnummer» — die Referenz des Empfängers

**Der Fund:** es gibt keinen Ort dafür. `config.parties[].ref` beantwortet die
**Gegenrichtung** («wie bestelle ich bei ihm»), `DealEntry.reference` ist die
Belegnummer.

Und es ist der praktisch häufigste Grund für eine unbezahlte Rechnung: viele Kunden —
und **jede** öffentliche Stelle — zahlen nicht ohne ihre eigene Bestellnummer auf dem
Papier. Das trifft das Ziel dieser Runde direkter als alles andere in der Liste.

**Umsetzung:** eine Spalte `deals.party_order_ref`, erfasst beim Zuschlag (dort nennt der
Kunde sie), eine Zeile im Belegkopf. Sie gehört zum **Vorgang**, nicht zur Zeile: eine
Bestellnummer gilt für das ganze Geschäft.
**Aufwand: klein + eine Migration.**

### 2.4 Aussenhandel — nur, wenn wirklich exportiert wird

#### ⑨ HS-Code (Zolltarifnummer) und Ursprungsland

**Beurteilung:** relevant, sobald eine Sendung die Grenze passiert — dann ist es
zwingend. Für rein inländische Geschäfte irrelevant.

**Umsetzung — und auch hier null neue Mechanik:** beides ist eine Eigenschaft der
**Sache**, nicht des Belegs. Zwei Spalten an `articles` (`hs_code`, `origin_country`) und
zwei Zeilen in `SPEC_FIELDS` — die Spezifikation **reist bereits mit dem Beleg**. Damit
steht es auf Offerte und Rechnung, ohne dass der Geldvorgang davon weiss.
**Aufwand: klein + eine Migration.**

#### ⑩ Incoterms 2020 (Lieferbedingung)

**Beurteilung:** relevant im Export, und die Checkliste hat recht, dass es auf **beiden**
Dokumenten stehen muss.

**Die Modellfrage, ehrlich:** eine Lieferbedingung klingt nach dem **Bewegen**-Modul —
dort geschieht der Transport. Sie ist aber eine **Vereinbarung** zwischen zwei Parteien
über Kosten und Risiko, kein physischer Vorgang; sie steht auf dem Beleg, und sie gehört
zur Zusage. Also: `deals.incoterm` + `incoterm_place`, aus einem **Katalog**
(elf Klauseln, kein Freitext — dieselbe Begründung wie bei Währung und Steuersatz).

**Priorität: mittel.** Erst umsetzen, wenn ⑨ gebraucht wird — die beiden gehören
zusammen.
**Aufwand: mittel + eine Migration.**

#### ⑪ AGB-Verweis

**Beurteilung:** billig und wirksam — ohne Verweis gelten die AGB nicht als einbezogen.

**Umsetzung:** eine Fusszeile mit Link auf die Website-AGB, gepflegt am **Betreiber**.
Kein Dokumentmodul nötig (das ist entfernt), ein Satz genügt.
**Aufwand: Minuten.**

---

## 3 · Bewusst NICHT — mit Grund

| Vorschlag | Warum nicht |
|---|---|
| **Eigene Offertnummern-Serie** | Der Nummernkreis ist universell und 9-stellig. Eine zweite Serie ist ein zweiter Nummernraum für dieselbe Sache (siehe ⑦). |
| **Handelsregisternummer separat** | In der Schweiz **ist** sie die UID — steht so seit Notiz #307 im Code. Eine zweite Spalte schriebe dieselbe Zahl ab. |
| **Steuernummer neben der USt-IdNr.** | Ebenso: in der Schweiz dieselbe Nummer. |
| **Skonto** | Ein zweites Zahlungsziel mit Bedingung — also eine **dritte Wahrheit** neben `open` und `due_on`, und sie müsste beim Zahlungseingang nachgerechnet werden. Im CH-B2B-Maschinenbau selten. Erst bauen, wenn jemand ihn wirklich gewährt. |
| **Proforma-Rechnung** | «Nicht zahlungsbegründend» heisst: eine Forderung, die **nicht zählt**. Im Modell wäre das eine Zeile, die `balance` überspringt — genau die Ausnahme, die dieses Modul nirgends hat. Später als eigener `kind`, nicht als Flag an einer Rechnung. |
| **VIES-Validierung der Kunden-USt-IdNr.** | Externer Dienst. Sinnvoll — aber erst, wenn EU-B2B real vorkommt; heute wäre es eine Anbindung ohne Anwender. |
| **Brutto-/Nettogewicht, Packstücke, Packliste** | Eigenschaften einer **Sendung**, nicht eines Geldvorgangs. Sie gehören zum Bewegen-Modul, und dort gibt es sie noch nicht. |
| **Englische Belege** | Kein Beleg-Thema, sondern die Übersetzung der ganzen Oberfläche. Eigenes Vorhaben. |
| **«Freibleibend»-Formel** | Eine Gültigkeitsfrist (⑤) sagt dasselbe **präziser**. Zwei Aussagen über dieselbe Sache geraten in Widerspruch. |

---

## 4 · Reihenfolge

**Runde 1 — der Beleg wird rechtssicher** (klein, kein Risiko)
① UID des Empfängers · ② Firma als Empfänger · ④ Rechtsform + Kontakt · ③ Steuerhinweis
bei 0 %

**Runde 2 — das Angebot wird ein Angebot**
⑤ Gültigkeitsfrist · ⑥ Angebotsdatum · ⑪ AGB-Verweis
*(⑦ ist eine Entscheidung, kein Code.)*

**Runde 3 — der Kunde zahlt ohne Rückfrage**
⑧ «Ihre Bestellnummer»

**Runde 4 — erst wenn exportiert wird**
⑨ HS-Code + Ursprungsland · ⑩ Incoterms

---

## 5 · Der rote Faden

Bemerkenswert an dieser Prüfung ist, **wie wenig neue Mechanik** herauskommt:

* Drei Lücken sind **Daten, die wir haben und wegwerfen** (①, ②, ④).
* Zwei erben eine Form, die schon zweimal dasteht (⑤ = die dritte Frist, ⑨ = zwei weitere
  Spezifikationsfelder).
* Eine wird **kleiner**, indem eine Katalogzeile mit zwei Bedeutungen zu zwei Zeilen mit
  je einer wird (③).
* Genau **drei** Spalten kommen dazu (⑧, ⑨, ⑩) — und keine davon ist eine Ableitung, die
  man auch rechnen könnte.
* Eine Anforderung wird **abgelehnt, weil wir sie besser gelöst haben** (⑦).

Das ist der Beleg dafür, dass das Modell trägt: eine vollständige externe Checkliste
findet daran im Wesentlichen vergessene **Anzeigen**, keine fehlenden **Begriffe**.
