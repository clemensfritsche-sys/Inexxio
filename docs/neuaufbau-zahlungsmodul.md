# Neuaufbau des Zahlungsmoduls — Plan

> **Auftrag:** *«Wir haben jetzt schon so viel hin und her geflickt … es wird Zeit für einen
> Neustart. Bau das Modul von Grund auf neu, in deinem eigenen Ermessen. Es gibt dann einfach
> ein neues Modul, heisst auch «Zahlung», bekommt eine leicht andere Farbe. Irgendwann soll
> das erste vollständig gelöscht werden können.»*

Dazu die sechs offenen Testnotizen **#921–#926**.

---

## 1 Der Befund — gemessen, nicht erinnert

| Datei | Zeilen |
|---|---:|
| `backend/app/domain/deal.py` | 1054 |
| `backend/app/services/deal.py` | 2496 |
| `backend/app/schemas/deal.py` | 753 |
| `backend/app/models/deal.py` | 296 |
| `frontend/src/components/erp/deal-work.tsx` | 3026 |
| **Summe** | **7625** |

Die **Logik** ist richtig geworden. Die **Datenform** ist an drei Stellen noch die des
ersten Entwurfs, und dort liegt die Hälfte der Zeilen:

1. **Der Angebotsspiegel ist JSONB** (`deals.quotes`). Ein Angebot *ist* eine Entität –
   Partner, Betrag, zwei Fristen, Zustand, Datum, Positionen. Als JSONB muss die ganze
   Liste bei jeder Änderung neu gebaut werden (`_write_quotes`, weil ein mutierter Wert
   still aus dem `UPDATE` fällt), und `sent_on` musste nachträglich hineingeflickt werden.
2. **Die Position gibt es in DREI Formen** – `process_lines` (abgeleitet) →
   `quotes[].lines` (je Angebot kopiert) → `agreed_lines` (eingefroren) –, angefasst an
   **21 Stellen**.
3. **Ein Verb wird an VIER Stellen deklariert**: `ACTIONS` (welche Stufe), `REQUIRED_FOR`
   + `_UP_TO` (welche Stammdaten), `HANDLERS` (welche Funktion), `Direction.party_actions`
   (wer darf). Das widerspricht der eigenen Hausregel.

Dazu die UI: sie **entstand als Modulkarte** und wurde über #847 · #899 · #913 schrittweise
zu einem Beleg umgeformt. Drei Runden für eine Einsicht.

---

## 2 Was bleibt — es war richtig

Nichts davon wird angerührt, es wird **übernommen**:

* **Die Eigenständigkeit.** Kein Import aus einem anderen Prozessmodul. Genau deshalb
  kostete die Löschung von «Beschaffen» und «Verkauf» hier null Zeilen – und genau
  deshalb wird die Löschung des alten Zahlungsmoduls hier ebenfalls null Zeilen kosten.
* **Es bewegt keine Stücke** (`Im Prozess` → `Im Prozess`, `terminal = False`,
  `moves = False`). Robustheit konstruktiv statt geprüft.
* **Ableitungen statt Spalten**: *berechnet · bezahlt · offen · uncharged · fällig ·
  überfällig · Liefertermin · Netto · Steuer* – null Spalten.
* **`can` ist Auskunft UND Tor.** Dieselbe Liste rendert die Knöpfe und weist ab.
* **Die Richtung ist DATEN, kein `if`.** Einnahme ↔ Ausgabe unterscheiden sich in Wörtern
  und in `quoted_by`/`collects`, sonst in nichts.
* **Zwei Stufen** (`offer` · `agreed`) + zwei Ausgänge (`done` · `cancelled`). Das Geld ist
  eine **Zeile**, keine Stufe.
* **Eine Rechnung je Modul** (#866), **kein Anteil** (#867), **eine Zahlung je Rechnung**
  (#858), **Storno = Gegenbuchung** (#823/#824), **eine Währung je Vorgang** mit ihren
  Nachkommastellen, **Steuer je Position** mit Rundung je Satz auf der Summe,
  **`DataGap`** (fehlende Stammdaten sind eine Zeile, kein Zustand).

**Ausdrücklich NICHT geändert:** der Vorgang bleibt am **Schritt**, nicht am Auftrag. Ein
Auftrag kann eine Einnahme *und* eine Ausgabe tragen (wir kaufen Material, wir verkaufen
das Produkt) – «ein Vorgang je Auftrag» bräuchte sofort die Regel «je Richtung», und
Regeln sind das, was hier abgebaut wird. Dass eine Anzahlung ein zweites Modul ist, hat
der Nutzer in #866 entschieden, und die Begründung trägt: drei Zeitpunkte sind drei
Punkte im Prozess.

---

## 3 Was neu wird

### 3.1 Identität

| | alt | neu |
|---|---|---|
| Schlüssel | `zahlung` | **`beleg`** |
| Beschriftung | «Zahlung **(alt)**» | «Zahlung» |
| Farbfamilie | `rose` (Altrosa) | **`plum`** (gedämpftes Violett) |

`plum` steht bereits im Katalog und hat seit der Löschung von «Beschaffen» keinen
Besitzer – die Farbe kostet **null neue Zeilen**, ist die Nachbarfamilie von `rose` über
die kalte Seite (verwandt, wie es sich für zwei Fassungen desselben Moduls gehört) und
trotzdem unterscheidbar.

*Zum Schlüssel:* er kann nicht `zahlung` heissen, solange das alte Modul existiert – er
steht in eingefrorenen Prozessen laufender Aufträge. Er heisst darum nach der **Sache**
(ein Beleg), die Beschriftung nach der **Handlung**. Ein Schlüssel ist eine Adresse, kein
Name; umbenennen wäre eine Datenmigration eingefrorener Vorlagen.

### 3.2 Vier Tabellen statt zwei Tabellen und drei JSONB-Formen

```
vouchers            der Vorgang        (1 je Modul, aktiv)
├─ voucher_quotes   der Angebotsspiegel (n je Vorgang — je Partner eine Zeile)
├─ voucher_lines    die Positionen      (n je Vorgang — EINE Form)
└─ voucher_entries  Forderungen + Zahlungen
```

**Der Angebotsspiegel wird eine Tabelle.** Ein Angebot hat einen Zustand, ein Datum, einen
Betrag und zwei Fristen – das ist eine Entität, keine Liste an einem Feld. Damit entfallen
`_write_quotes`, `_quote_of`, `_patch_quote` und die Regel «nie an Ort ändern».

**Die Position gibt es EINMAL.** `voucher_lines` trägt Artikel, Menge, Preis, Satz und die
beiden Zoll-Angaben. Eingefroren wird sie **nicht durch eine Kopie**, sondern durch die
Stufe: solange `stage = offer`, zieht `sync_lines` die Mengen aus dem Prozess nach; ab der
Zusage nie wieder. Null zusätzliche Spalten, null Kopien.

*Die eine bewusste Vereinfachung:* die Positionen gehören dem **Vorgang**, nicht der
Angebotszeile. Ein Beleg hat **einen** Satz Positionen mit **einem** Satz Preise – zwei
Kunden zwei verschiedene Preise anzubieten sind zwei Angebote, also zwei Vorgänge. Beim
Vergleich mehrerer Lieferanten (der eigentliche Zweck des Spiegels) nennt ohnehin jeder
eine **Summe**, und die steht an seiner Zeile.

### 3.3 Ein Verb hat EINE Deklaration

```python
VERBS = {
  "ask": Verb(stages=(OFFER,), run=_ask, needs=("ask",), party=NEVER),
  "quote": Verb(stages=(OFFER,), run=_quote, needs=("ask",), party=IF_THEY_PRICE),
  ...
}
```

Vier Fragen über ein Verb – *in welcher Stufe · welche Stammdaten · welche Funktion · darf
die Gegenpartei* – stehen in **einer Zeile**. `ACTIONS`, `_UP_TO`, `HANDLERS` und
`party_actions` sind darin aufgegangen.

### 3.4 Die Oberfläche ist von der ersten Zeile an ein Beleg

```
Belegkopf      Belegart · Nr. · beide Parteien auf EINEM Raster
Positionen     Zeile · Preis · MWST · Zoll  →  Netto · Steuer je Satz · Total
Konditionen    Zahlungsfrist · Lieferfrist · Lieferbedingung   (ohne Überschrift, #926)
Rückläufe      der Angebotsspiegel — nach dem Zuschlag auf eine Zeile
Rechnung & Zahlung
Chronik        wann offeriert · wann zugesagt · wann storniert
Handlungen     unter dem Strich, wie die Unterschrift
```

---

## 4 Die sechs Testnotizen

**#922 — «man muss erkennen, dass es veränderbar ist»** (der Kern).
Eine **Klasse**, `.ix-editable`, und sie gilt für **jeden** änderbaren Wert auf dem Beleg
(Währung · Zahlungsfrist · Lieferfrist · Lieferbedingung · Preis · MWST · Zolltarifnummer ·
Ursprungsland · Leistungserbringer/-empfänger):

* Ruhezustand: eine **Haarlinie unter dem Wert** in der leisen Stimme des Hauses
  (`--accent`, gedämpft) – als `inset box-shadow`, also **ohne Layoutwirkung**.
* Beim Zeigen: volle Akzentlinie + `--accent-soft` als Fläche.
* **Keine** Änderung von Grösse, Form, Schriftart oder Gewicht – der Beleg sieht aus wie
  der Beleg, nur gehighlighted.

Genau eine Regel, an einer Stelle, geerbt von allem: die Antwort auf «ACHTUNG. Ich will
das auch für alle andere Angaben auf dem Beleg.»

**#921 — die Währung steht neben den Beträgen.** Regel: *jede Zahl, die man abschreibt
oder überweist, nennt ihre Währung* – Netto, Steuer je Satz, Total, offener Betrag, jede
Geld-Zeile. **Nicht** an jedem Einzelpreis: dort stünde dasselbe Wort zwanzigmal.

**#923 — die Handlung, die den Beleg weiterbringt, sieht überall gleich aus.** Ein
Bauteil (`StageAction`): volle Breite, Akzentfläche, gleiche Höhe – für «Anbieten /
Anfragen», «Angebot annehmen» und «Vorgang abschliessen». Das ist die verlangte UI-Logik,
kein Sonderfall für einen Knopf.

**#924 / #925 — «Erst zahlen» entfällt im Kopf** (beide Vorkommen). Ob vorausbezahlt wird,
sagt die **Zahlungsfrist** in den Konditionen – eine Zeile tiefer, wo man sie ändert.

**#926 — keine Überschrift «Konditionen».** Die Fristen stehen direkt unter den Positionen
und Beträgen; sie erklären sich selbst.

---

## 5 Nebeneinander, und dann weg

Beide Module laufen parallel. Das neue fasst das alte **an keiner Stelle an**:

* eigene Vokabel (`domain/voucher.py`), eigener Dienst, eigene Tabellen, eigene Endpunkte
  (`…/steps/{id}/voucher…`), eigene Komponente – **kein Import** aus `deal`/`purchase`.
* der Rahmen bekommt **je eine Zeile** an denselben drei Berührungspunkten
  (`instantiate_for_order` · `assert_completable` · `finish`), no-op ohne das Modul.

Der Preis dafür ist **eine bewusste, befristete Doppelung**: der Steuerkatalog und die
Betrags-Mathematik stehen in beiden Fachkernen. Ein gemeinsames drittes Modul wäre ein
Umbau an Code, der gelöscht werden soll, und würde die beiden genau dann koppeln, wenn sie
unabhängig sein müssen. **Ein Wächter vergleicht die beiden Kataloge**, solange es beide
gibt – er stirbt mit dem alten Modul.

**Die Löschung später** ist dann: `domain/deal.py` · `services/deal.py` · `schemas/deal.py`
· `models/deal.py` · `deal-work.tsx` · der Modul-Eintrag · vier Endpunkte · die Wächter –
und **keine** Zeile im neuen Modul.

---

## 6 Migration und Netze

Migration **`134`**: vier Tabellen, **vollständiger** Spaltensatz inklusive der geerbten
(`is_active`, `created_at`, `updated_at`) – die Lehre aus `purchases.is_active`. Idempotent
je Objekt (Tabelle, Index, Fremdschlüssel), weil die dev-Datenbank kein `alembic upgrade`
fährt. Netz-Einträge in `main.py` für jede Spalte, die später dazukommt.

Verifiziert: von null · idempotent · downgrade · re-upgrade · über das Lifespan-Netz.
Suite grün gegen die gewachsene Datenbank **und** gegen ein Schema, das nur aus den
Migrationen kommt.
