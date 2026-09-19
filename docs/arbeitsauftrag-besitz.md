# Arbeitsauftrag — **Besitz: ein zweiter Zeiger, gesetzt vom Zahlungsmodul**

> **Der Auftrag in einem Satz:** Eine Einzelinstanz bekommt neben *wo sie liegt* eine
> zweite Angabe — *wem sie gehört*. Geschrieben wird sie **ausschliesslich** vom
> Zahlungsmodul, wenn die Stücke es passieren. Ein eigenständiges Modul dafür gibt es
> **nicht**.

---

## 1 · Der Befund

Ein Stück beantwortet heute **zwei** Fragen, und eine davon wird doppelt belegt:

| Frage | Antwort heute |
|---|---|
| Was passiert damit? | `instance_units.status` — die **Prozess**-Achse |
| Wo liegt es? | `place_object_id` / `place_unit_id` — ein **Zeiger** (`services/places`) |
| **Wem gehört es?** | **fehlt** |

Der Wunsch, «Verkauft» als *Status* zu führen, beisst sich genau deshalb mit dem
Prozessmodell: solange ein Auftrag läuft, steht das Stück auf `Im Prozess` — und das ist
richtig. Ein Feld mit **zwei Chefs** (der Prozess schreibt jede Sekunde, das Geschäft
einmal) verliert immer gegen den Prozess.

**Der Ort hat dieses Problem nicht**, weil er kein Zustand ist, sondern ein Zeiger, den
keine Prozessregel liest. Besitz bekommt dieselbe Bauart.

Und die beiden Achsen sind wirklich unabhängig — das ist der ganze Grund, warum es zwei
sein müssen:

| | **liegt bei uns** | **liegt beim Partner** |
|---|---|---|
| **gehört uns** | Lager | Muster · Leihgabe · Konsignation |
| **gehört ihm** | **Beistellung** | verkauft |

---

## 2 · Der Zeiger

Neue Spalte `instance_units.owner_object_id` (`BIGINT`, nullable, indiziert).

* **`NULL` = uns.** Ein regulärer Zustand, kein fehlender Wert — so wie `place_*`.
* Sonst die **Objektnummer einer Rechtsperson**: ein **Benutzer** oder ein
  **Unternehmen**. Kein Typfeld daneben — Objektnummern sind eindeutig, der Typ ist
  ableitbar (dieselbe Regel wie beim Halter).
* Zeigt sie auf **eine unserer Gesellschaften**, gehört das Stück *dieser* Gesellschaft —
  und damit weiterhin uns. Das beantwortet «womit kann ich als **jeweiliges** Unternehmen
  wirtschaften», ohne eine zweite Spalte.
* **Am Stück, nicht an der Gruppe**: zwei Schrauben derselben Charge dürfen verschiedenen
  gehören (Beistellung neben eigenem Material).
* **Keine Zyklen möglich** — ein Eigentümer ist nie wieder ein Stück. Die
  `seen`/`MAX_STATIONS`-Mechanik des Ortes entfällt hier ersatzlos.

**`services/owners.py` ist die EINE Schreibstelle** (Quelltext-Wächter), Zwilling von
`services/places.py`:

```
owner_of(unit)                → Optional[int]
ours(db) / is_ours(db, id)    → gehört das uns? (NULL oder eine unserer Gesellschaften)
assert_ownable(db, target)    → nur Benutzer | Unternehmen, sonst 400 mit Satz
transfer(db, units, to)       → die eine Schreibstelle
apply_for_step(db, step, …)   → was dieses Modul am Eigentum ändert (Payload für den Log)
```

*Wer besitzen kann, ist genau, wer eine **Anschrift** trägt* — dieselbe Menge, die
`places.ADDRESS_HOLDERS` schon führt. Die Auflösung wird **geteilt**
(`places.stations_for`), nicht nachgebaut.

---

## 3 · Wer den Wechsel auslöst: das Zahlungsmodul

> **Kein eigenes Modul.** Der Eigentumsübergang ist die **Folge** eines Geschäfts, und
> das Geschäft ist der Beleg. Ein Modul, dessen ganze Aussage eine Folge ist, beschreibt
> nichts, was nicht schon dasteht — genau daran ist «Ausliefern» gestorben (§9.13).

**Eine Deklaration am Modul** (`domain/modules.Beleg`, Schlüssel `transfer`, Vorgabe
**aus**):

* **`Eigentum bleibt`** — der Normalfall: Miete, Lohn, Gebühr, Spedition, eine Leistung
  an fremdem Material. Es passiert nichts.
* **`Eigentum wechselt`** — Verkauf, Einkauf, Retoure.

**An wen, sagt die Richtung** — kein zweites Feld: `Direction.collects` beantwortet es
längst.

| Richtung | Geld | Eigentum geht an |
|---|---|---|
| **Einnahme** (`collects = True`) | kommt herein | die **Gegenpartei** des Belegs |
| **Ausgabe** (`collects = False`) | geht hinaus | **unsere** Gesellschaft (der Aussteller) |

**Wann:** wenn die Einzelinstanzen das Modul **passieren** (`process.confirm_step`),
dieselbe Stelle und dieselbe Reihenfolge wie beim Ort — erst schreiben, dann `_pass`,
damit der Vorgang im **Log** des `step`-Ereignisses steht und nicht in einer zweiten
Tabelle daneben.

**Wo im Prozess, entscheidet der Modellierer** — das ist der Gewinn gegenüber einer
Automatik: steht die Zahlung vor dem Bewegen, wechselt das Eigentum vor der Lieferung;
steht sie danach, ist es der Eigentumsvorbehalt. **Die Reihenfolge IST der Prozess.**

**Die Retoure braucht keine Regel**: ein ganz gewöhnlicher Auftrag greift die Stücke
(*das Greifen IST die Rücknahme*) und trägt ein Zahlungsmodul in der Gegenrichtung mit
`Eigentum wechselt` — das Eigentum kommt zurück, weil die Richtung es sagt.

---

## 4 · Was NICHT geändert wird — und warum

* **`Verkauft` bleibt im Katalog und bleibt schreiberlos.** Er ist das Vokabular des
  append-only Logs; ihn zu streichen machte Vergangenes unlesbar (§9.13). Ein neues
  Modul schreibt ihn **nicht** — der Besitz sagt es jetzt genauer.
* **Der Ort wird nicht berührt.** Verkauft ≠ beim Kunden; beides bleibt getrennt
  schreibbar, und das war die ganze Bitte.
* **`places.forget` bekommt kein Gegenstück.** Wer zur Historie zählt, verliert seinen
  **Ort**; sein **Eigentum** behält er — wem ein Stück gehörte, als es verschrottet
  wurde, ist eine Tatsache und keine Behauptung über ein Regal.
* **`pick_problem` bleibt unangetastet.** Ein fremdes Stück ist greifbar: Beistellung
  wird verarbeitet, Verkauftes zurückgenommen.
* **Die FIFO-Vorauswahl bleibt unangetastet.** Eine Regel «fremdes nie vorschlagen» wäre
  bei der Lohnfertigung falsch — dort ist fremdes Material genau das Richtige. Der
  Mensch sieht den Eigentümer und entscheidet (*das System bietet an, der Mensch
  entscheidet*).

---

## 5 · Der Bestand — zwei Fragen, zwei Leisten

> *«Ich muss trotzdem den globalen Überblick behalten und zugleich wissen, mit was ich
> als jeweiliges Unternehmen wirtschaften kann.»*

Das sind **zwei** Fragen über **dieselbe** Menge Stücke, und darum stehen sie als zwei
Leisten übereinander — buchstäblich dasselbe Bauteil (`module-ui.ValueBar`), zwei
Aufteilungen:

```
Zustand    ▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉    ← der globale Überblick (unverändert)
           Freigegeben 12 · Im Prozess 3 · Verkauft 5

Eigentum   ▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉▉    ← womit kann ich wirtschaften
           Uns 15 · Muster AG 5
```

* **Beide Leisten summieren sich auf dieselbe Gesamtzahl** — sonst wären es zwei
  Auskünfte über zwei Dinge.
* **Die zweite ist eine Auskunft, kein Bedienelement** (`ValueBar` ohne Handler — dieselbe
  Bauart, die `ModuleSteps` seit #868 hat). Der Durchgriff auf die Nummern bleibt, wo er
  ist: Zustand anklicken → Instanz aufklappen → **jede Nummer nennt ihren Eigentümer**.
* **Sie erscheint nur, wenn es etwas zu sagen gibt** — gehört alles uns, wäre ein
  einziges Segment «Uns 20» eine Zeile ohne Aussage. Dieselbe Regel wie bei den
  Zuständen: was es nicht gibt, steht nicht da.

Dazu: die **Auswahl-Liste** (`unit-options`) nennt je Stück seinen Eigentümer, wo er
nicht uns ist — dort entscheidet sich, womit gearbeitet wird.

---

## 6 · Berührungspunkte (vollständig)

**Backend**

| Stelle | Was |
|---|---|
| `models/instance_unit.py` | die Spalte |
| `alembic/versions/138_*` | Spalte + Index, von null · idempotent · downgrade |
| `main._COLUMN_SAFETY_NET` / `_RAW_INDEX_SAFETY_NET` | das Netz (dev fährt kein `upgrade head`) |
| `services/owners.py` | **neu** — die eine Schreibstelle |
| `domain/voucher.py` | die Wörter (`TRANSFER_*`) |
| `domain/modules.py` | `Module.transfers_ownership` (Vorgabe *nein*) + `Beleg.TRANSFER` |
| `services/voucher.py` | `transfer_for(db, step)` → an wen · `VoucherEmbed.transfer_note` |
| `services/process.confirm_step` | **eine** Zeile Verdrahtung, Payload in den Log |
| `services/instances.py` | `owner_states(db, article_id)` · `owners_of(db, instance_ids)` |
| `schemas/instance.py` | `OwnerShare` · `UnitOut.owner` |
| `routers/articles.py` · `routers/instances.py` · `routers/orders.py` | Aggregation durchreichen |
| `services/invariants.py` | «ein Eigentümer ist eine Rechtsperson» |

**Frontend**

| Stelle | Was |
|---|---|
| `lib/modules.ts` | `MONEY_FORM` ± `transfer`, `ModuleDraft.transfer`, die Wörter |
| `components/erp/process-designer.tsx` | der Schieber im Editor |
| `components/erp/stock-view.tsx` | die zweite Leiste |
| `components/erp/unit-numbers.tsx` | der Eigentümer je Nummer |
| `components/erp/unit-choices.tsx` | der Eigentümer in der Auswahl |
| `components/erp/beleg-work.tsx` | die Auskunft am Beleg |

**Wächter:** `backend/tests/test_ownership.py` (jede Prüfung gegen ihre Bug-Form
gegengeprüft) + `test_frontend_mirrors.py`.

---

## 7 · Bewusst offen (benannt, nicht vergessen)

* **Eine Beistellung, die in unser Produkt verbaut wird**, macht das Produkt anteilig
  fremd. Das ist eine Frage der Bewertung, nicht der Zuordnung — hier wird nichts
  geraten: das verbaute Stück behält seinen Eigentümer, das Produkt den seinen.
* **Die Bestandsbewertung** (wie viel Geld liegt im Regal) folgt später; der Zeiger ist
  die Voraussetzung dafür, nicht die Antwort.
* **Eine Mengenaussage «fremdes Material am Standort»** über alle Artikel hinweg gibt es
  noch nicht — die Frage stellt heute niemand, und eine Ansicht auf Verdacht wäre die
  zweite, die man pflegen müsste.
