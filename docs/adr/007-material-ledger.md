# ADR 007 – Das Material-Journal: drei Fragen, ein Modell

> ## Kopfstatus (August 2026): **historisch – das Modell existiert nicht mehr**
> Das Material-Journal (`material_moves`, `services/ledger.py`) ist mit dem
> Basis-Neuaufbau entfallen. Seine Rolle – **die Vergangenheit ist eine Buchung, keine
> Ableitung aus dem heutigen Zustand** – trägt heute der Ereignis-Log
> (`process_events`, PROCESS_CORE.md §8.1a).
> **Der Grund, warum dieses Dokument bleibt**, ist seine Analyse: fast alle Mengen-Fehler
> des Vorgängers kamen aus drei Wurzeln (Zustand als Skalar an einer Menge · «wer hält wie
> viel» an vier Stellen · Vergangenheit aus der Gegenwart rekonstruiert). Wer eine
> Mengen-Frage neu beantwortet, liest sie vorher.


Status: **angenommen** (August 2026) · Vorleistung: Migration `097` (`instance_order_links.quantity`)

## Die drei Fragen (das SOLL)

Der Nutzer hat das Ziel in einem Absatz formuliert, und er ist der Massstab für alles:

> Im Grunde ist es ganz einfach. Ich muss 3 Sachen wissen:
> **was muss ich mit was im Moment machen** ·
> **was muss ich voraussichtlich als Nächstes machen** (kann sich noch ändern, z. B. durch
> Unteraufträge) · **was ist passiert** – und das, was passiert ist, ist passiert und kann
> unter keinen Umständen mehr geändert werden.

Daraus folgen drei Antworten, jede mit genau EINER Quelle:

| Frage | Antwort | Quelle |
|---|---|---|
| **Jetzt** | aktiver Schritt + das Material, das dieser Auftrag gerade hält (je Menge · je Zustand) | Kontostand = Summe der Journalzeilen (`ledger.lots`) |
| **Als Nächstes** | die noch offenen Schritte (Plan – änderbar, solange nichts passiert ist) | Schritt-Ableitung (`process.build_order_steps`, unverändert) |
| **Passiert** | die Journalzeilen selbst – append-only, nie editiert, nie gelöscht | `material_moves` |

## Der Konstruktionsfehler (das IST, und warum es scheitern musste)

Die Bug-Runden #341–#499 kreisen fast alle um denselben Kern, in drei Ausprägungen:

1. **Der Zustand ist ein Skalar an der Instanz, die Realität ist eine Menge.**
   `instances.quality`/`disposition` behaupten EINEN Zustand für die ganze Instanz. Bei
   Einzelserialisierung stimmt das (1 Instanz = 1 Stück). Bei einer **Charge** nicht: von
   4 Stück können 3 in Arbeit und 1 verschrottet sein. Jede Anzeige, die den Skalar liest,
   ist für Chargen potenziell falsch – und wurde einzeln geflickt (#483/#485/#495 …).

2. **«Wer hält wie viel» steht an vier Stellen.**
   `reservations` (Map), `subject_of_order_id` (wandernder Zeiger), `reserved_for_order_id`
   (Denormalisierung), `Instance.order_id` (Erzeuger) – plus `orders.pick_sources`. Vier
   Mechanismen, die Regeln wie `held_quantity`, `shares.losers`, `holding_orders` immer
   wieder zusammenraten mussten. Jede Kante, an der zwei davon auseinanderliefen, war ein
   gemeldeter Bug.

3. **Die Vergangenheit wurde aus der Gegenwart rekonstruiert.**
   «Was ist durch diesen Auftrag geflossen?» wurde aus *heutigen* Reservierungen, *heutigen*
   Zuständen und *heutigen* Zeigern zurückgerechnet – alles bewegliche Ziele. Nach jeder
   Zustandsänderung erzählte der Fluss eine andere Geschichte über dieselbe Vergangenheit.
   Die `asOf`-/Stichtags-Mechanik der Oberfläche war Kompensation dafür, dass die Daten
   selbst keine Geschichte haben.

Serialisierung (Batch/Einzelteil) ist dabei **kein eigenes Problem**, sondern der
Verstärker: beim Einzelteil fallen Menge, Zustand und Instanz zusammen, darum fällt der
Fehler dort nicht auf. Die Charge deckt ihn auf.

## Das Modell (was mit dem Wissen von heute anders gebaut wird)

**Bestand ist ein Konto. Jede Veränderung ist eine Buchung. Buchungen sind unveränderlich.**

Eine Menge einer Instanz ist zu jedem Zeitpunkt in genau **einem Topf**:

    (Halter · Qualität · Verbleib)
    Halter   = ein Auftrag oder niemand (frei)
    Qualität = pending | passed | blocked
    Verbleib = in_process | in_stock | consumed | sold | scrapped

Jedes fachliche Ereignis ist eine **Journalzeile** (`material_moves`): Menge X der Instanz I
wechselte von Topf A nach Topf B – wer, wann, warum (`kind`). Entstehen hat keinen
Quell-Topf; Verschrotten/Verkaufen/Verbauen führen in terminale Töpfe, aus denen nichts
mehr herauskommt.

    kind ∈ created | opening | taken | returned | released |
           sold | consumed | scrapped | blocked | unblocked

Daraus folgen die drei Antworten **ohne weitere Regeln**:

* **Passiert** = die Zeilen, chronologisch. Append-only: kein UPDATE, kein DELETE –
  die Vergangenheit KANN sich nicht mehr ändern, weil es keinen Schreibweg gibt.
* **Jetzt** = der Kontostand (Summe der Zeilen je Topf). «Was hält Auftrag X?» ist eine
  Abfrage, keine Rekonstruktion. Der Zustand hängt an der **Menge im Topf**, nicht an der
  Instanz – das Chargen-Problem löst sich im Modell statt in der Anzeige.
* **Als Nächstes** = der Plan (Schritte), unverändert – er darf sich ändern, denn er ist
  noch nicht passiert.

### Ein Schreibweg

`services/ledger.py` ist die **einzige** Stelle, die Journalzeilen schreibt. Die
fachlichen Dienste rufen sie an ihren semantischen Punkten:

| Ereignis | Dienststelle | kind |
|---|---|---|
| Instanzen entstehen bei Freigabe | `serialization` | `created` |
| Auftrag übernimmt eine Menge | `subject.record_link` | `taken` |
| Abschluss gibt ans Lager frei | `process.release_instances` | `released` |
| Ausleihe geht an den Verleiher zurück | `subject.return_borrowed` | `returned` |
| Verkauf bezahlt | `process.sell_order_subjects` | `sold` |
| Retoure zurück im Bestand | `process.return_subjects_to_stock` | `returned` |
| Komponente verbaut | `resource` | `consumed` |
| Aussondern | `scrap` | `scrapped` / `blocked` |
| Entsperren | `scrap.unblock` | `unblocked` |
| Sperre aus Datenerfassung | `inspection` | `blocked` |

**Buchhaltung ist streng, Zuordnung ist tolerant:** eine Buchung entnimmt ihrem Quell-Topf
nie mehr, als er hält – reicht er nicht, wird aus den übrigen lebenden Töpfen der Instanz
gedeckt (bevorzugt derselbe Halter), und was dann noch fehlt, wird als sichtbar markierte
Korrektur gebucht (`note='!unbalanced'`) statt still zu verschwinden. `ledger.verify`
findet solche Stellen; sie sind Bugs im Aufrufer, keine Kontokorruption.

### Die alten Spalten werden Projektionen

`instances.quality`/`disposition`/`reservations`/`reserved_quantity`/… bleiben vorerst –
als **Lesehilfen** (Feed-Badges, FIFO-SQL), nicht als Wahrheit. Die Reservierungs-Map
bleibt ausserdem das **Planungs**-Instrument (Ansprüche/Vormerkungen sind Absichten,
keine physischen Ereignisse – sie gehören nicht ins Journal). Wo eine Anzeige den Zustand
**je Menge** braucht (Fluss, «Menge & Zustand», Verlauf), liest sie das Journal.

### Eröffnungsbilanz statt Migration

Bestehende Instanzen bekommen keine nachgerechnete Historie (die wäre gelogen). Vor der
**ersten** Buchung einer Instanz schreibt das Journal eine **Eröffnung** (`opening`) mit
ihrem aktuellen Stand – ab dort ist die Geschichte vollständig. Aufträge ohne Journal
werden weiter aus Links + Event-Strom gelesen (tolerant lesen, streng schreiben).

## Ausbaustufen

1. **UMGESETZT:** Journal + ein Schreibweg + Eröffnung + `verify` + der
   **Instanz-Verlauf** («was ist mit diesem Stück passiert», Big-Picture-Stufe 3) +
   `flow_back` aus echten Rückgabe-Buchungen.
2. **UMGESETZT:** die Fluss-Achse (`order_material`) liest das Journal
   (`ledger.order_view` – die eine Regel: alles je Hineingebuchte ist genau einmal da,
   als gehaltener Topf, terminaler Topf mit Zeitpunkt oder abgegebene Menge im Zustand
   des Abgangs; eine **Rückkehr verzehrt ihre Abgabe-Zeile**). Dazu der
   **Auftrags-Verlauf** (`OrderResponse.history`) – die dritte Frage direkt am Auftrag,
   dieselben Zeilen wie am Instanz-Detail, aus der anderen Richtung gelesen.
   Alt-Aufträge ohne Buchungen fallen auf die Legacy-Ableitung zurück.
3. **UMGESETZT – die Visualisierungs-Stufe: das Frontend zeichnet, der Server weiss.**
   Die Fluss-Achse kommt fertig gerechnet aus dem Backend
   (`OrderResponse.flow_nodes`/`flow_edges`, `orders._fill_flow_view`): Knotenliste
   (Schritt oder Teilung, Reihenfolge = Entstehung), Fortschritt (`reached`/`passed`),
   der EINE Prozess-Punkt (`live` – Kante oder Bypass, keiner an einem nicht laufenden
   Auftrag), das Material jeder Kante **im Zustand von damals** (`_as_of`, Stichtag =
   Abschluss des Schritts darüber; die letzte Kante zeigt das ERGEBNIS – ein Stichtag
   würde dort die Abschluss-Freigabe zurückdrehen) und der **Bypass** einer Teilung
   (live = Custody `held+terminal`, Vergangenheit = Stand von damals minus Abzweig).
   **Was in einen Abzweig ging, liegt unterhalb seiner Teilung nicht mehr auf der
   Achse**: die Journal-Zeile weiss, wohin sie ging (`ViewRow.to_order`) – je Kante wird
   **gefiltert, nicht subtrahiert**; was zurückkam, ist wieder gehalten (die Rückkehr hat
   ihre Abgabe-Zeile verzehrt). Die frühere Client-Arithmetik (minus/plus/Stichtags-
   Zeitmaschine als React-Code) ist ersatzlos entfallen – jede Abweichung zwischen ihr
   und der Server-Wahrheit war eine Testnotiz. Zweite Hälfte derselben Aufräumung: die
   **Prozesslinien wohnen in EINEM Modul** (`frontend/src/components/erp/flow-line.tsx` –
   Spurbreiten, Achse, Ecken-Pfade, Drei-Spuren-Zeile, Zurücktreten); `order-flow.tsx`
   setzt nur noch zusammen. Wächter:
   `test_frontend_mirrors.test_the_frontend_draws_and_the_server_knows`;
   PG16-Harness `flowview.py` (19 Prüfungen über die echten Service-/Router-Pfade).
4. **Danach:** die Skalar-Spalten schrittweise stilllegen (Folge-Deploy-Muster wie
   `is_primary`), FIFO auf Journal-Töpfe, `shares` als reine Journal-Sicht.

## Was dadurch strukturell unmöglich wird

* Eine Vergangenheit, die sich ändert (kein UPDATE-Pfad existiert).
* Zwei Antworten auf «wer hält wie viel» (eine Quelle, eine Fold-Funktion).
* Ein Chargen-Zustand, der für die ganze Menge gilt (der Topf trägt ihn je Menge).
* Stiller Mengenschwund (Konservierung wird beim Buchen geprüft, Verstösse sind markiert
  und auffindbar statt unsichtbar).
