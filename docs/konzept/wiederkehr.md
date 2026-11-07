# Projektakte «Wiederkehrende Aufträge»

> **Kopfstatus:** in Klärung · **nichts gebaut** · Lead: Claude · Entscheid: Clemens Fritsche ·
> seit 06.11.2026 · zuletzt 07.11.2026 (zweite Runde)
> Bild (Ist-Stand 1:1, Schlaufe, Abo): https://claude.ai/artifact/Lk5AKy8G1CTWi68ZxA57uj
> Diese Akte ist die **eine** Quelle für Ziel, Grundsätze, Vorschläge und Entscheide. Das Bild
> zeigt, die Akte hält fest. Was hier nicht als entschieden steht, ist nicht entschieden.
> Ausgangspunkt im Kern: `PROCESS_CORE.md` §13 Punkt 6.

## 1 · Problem

Prüffristen, Wartungen (intern und extern), wiederkehrende Lieferungen und Abos (Produkt oder
Software) leben heute im Kopf. Ist ein Auftrag abgeschlossen, weiss das System nicht, dass er in
zwölf Monaten wieder fällig ist.

## 2 · Ziel

**Was sich wiederholt, wird nicht vergessen – und läuft so weit wie möglich von selbst.**

Mit **einer** Logik für alle Fälle. Kranprüfung, Service-Vertrag, INEXXIO 365 und monatliche
Lieferung unterscheiden sich nur in der Konfiguration des Auftrags, nicht im Modell.

## 3 · Grundsätze (entschieden)

1. **Eine Logik, am Auftrag.** Es gibt keine Fallunterscheidung.
2. **Jede Wiederholung ist ein ganz gewöhnlicher Auftrag.** Er läuft durch und endet wie jeder
   andere. Zwischen zwei Wiederholungen ist das Stück frei, also nicht im Prozess.
3. **Eine Wiederkehr gibt es nur an einem regulären Auftrag, nie an einer Abweichung.**
4. **Der Takt ist Zeit, an einem festen Kalendertag** (wie bei einem Abo). Zähler wie
   Betriebsstunden oder Kilometer kommen später; das Modell lässt nur Platz dafür.
5. **Eine fällige Wiederholung wartet, bis sie entstehen kann, und entsteht dann sofort.**
   Steckt das Stück gerade in einem anderen Auftrag (auch einem von Hand angelegten), wartet
   sie. **Keine Periode geht verloren**: jede wird ein Auftrag, der Reihe nach. Aufträge von
   Hand sind jederzeit möglich und verschieben den Kalender nicht.
6. **Jederzeit änderbar und beendbar, ohne Kündigungsfrist.** Ändert sich der Ablauf (z. B.
   ein Prüfpunkt mehr), wird die Wiederkehr beendet und ein neuer Auftrag mit eigener
   Wiederkehr angelegt.
7. **Der Vertrag ist die Wiederkehr.** Ein Papier ist höchstens ein Dokument daran. Abschliessen
   und kündigen durch den Kunden geschieht später online (eigenes Projekt, «wie bei jedem Abo»).
8. **Alles ist ein Stück.** Ein fremder Kran ist ein Artikel mit Instanz, ein Abo auch (z. B.
   Artikel «INEXXIO 365», eine Instanz je Abo). Pauschale und «je Einsatz» sind damit dieselbe
   Logik (V6).
9. **Die Eigentumswahl bleibt frei.** Ein Kundenstück nicht zu uns zu holen, liegt in der
   Verantwortung dessen, der den Auftrag anlegt. Es gibt keine Sperre dafür.
10. **`Verkauft` ist ein regulärer Start** (07.11.2026, Richtung entschieden, Folgen in §4
    geprüft). Regulär beginnt, was **ruht**: `Freigegeben` (bei uns) oder `Verkauft` (bei der
    Partei). → V1.
11. **Die Wiederkehr legt selbst an** (07.11.2026, → V2).
12. **Die Wiederkehr ist eine Schlaufe im Prozessbild**, gezeichnet und geschaltet wie die
    Rückführung (07.11.2026, → V3).
13. **Zahlung: Was vorher festgelegt ist, gilt weiter; was bewusst offen blieb, wird jedes Mal
    neu festgelegt** (07.11.2026, → O1).
14. **Was die Wiederholung nimmt, sagt der Mensch je Zeile ausdrücklich** (Vorschlag 07.11.2026,
    → V3): «dieselben Stücke» oder «nach FIFO».

## 4 · Befunde aus dem Code

- **Warum ein verkauftes Stück heute eine Abweichung ist.** Der Regelstart ist genau ein
  Zustand, `Freigegeben` (`statuses.START_BEFORE`, PROCESS_CORE §12.2,
  `order_state.deviation_flags`, SYSTEM_LOGIC T7e und U6c). Der Grund damals: «Das Greifen IST
  die Rücknahme». Ein verkauftes Stück zu greifen hiess Retoure, und das Label sichert die
  Nachweisbarkeit. **An Service wurde dabei nicht gedacht**, obwohl der Test
  `test_return_repair_and_cancelled_return` die Reparatur am verkauften Stück schon kennt.
- **Was V1 berührt (geprüft 07.11.2026):**
  - **Eine Stelle ändert sich:** `deviation_flags` vergleicht gegen eine Menge
    (`Freigegeben`, `Verkauft`) statt gegen einen Zustand.
  - **Eine Stelle darf sich NICHT ändern:** `consumption._free` und FIFO lesen ebenfalls
    `START_BEFORE` und nehmen nur, was bei uns frei ist. Ein Kundenkran darf nie verbaut oder
    per FIFO genommen werden. Darum braucht es zwei Namen: «frei bei uns» (bleibt
    `Freigegeben`) und «regulärer Start» (die Menge). Wer nur `START_BEFORE` umstellt,
    öffnet genau dieses Loch.
  - **`is_deviation` wirkt heute nur als Zeichen am Symbol.** Es sperrt nichts; Exklusivität,
    Rückführung und Sperren hängen nicht daran. Neu läse es Grundsatz 3.
  - **Eine Retoure** (`Verkauft` → Zahlung «geht an uns») trägt das Zeichen dann nicht mehr.
    Belegt bleibt sie durch ihre Zahlung und das Start-Ereignis im Log (`status_before`).
  - **Die Farbe ist nicht die Regel:** `Verbaut` ist auch grün und bleibt eine Abweichung
    (Ausbau). Die Regel heisst «ruht», nicht «grün».
  - **Nachzuziehen:** PROCESS_CORE §12.2, SYSTEM_LOGIC T7e und U6c, die Kommentare in
    `domain/statuses.py` (`VERKAUFT`), CLAUDE.md («greifen nur als Abweichung»); ein Test
    «Service am verkauften Stück ist regulär», einer «Retoure ist regulär und «an uns»
    belegt», und ein Wächter, dass Verbrauch und FIFO weiter nur `Freigegeben` nehmen.
- **«Verkauft» ist nicht «Freigegeben».** Ein verkauftes Stück wird am Ende eines Auftrags
  wieder «Verkauft» (Eigentum aus dem jüngsten Zahlungsmodul, `voucher.sold_units`).
- **Ein fremder Kran, der per Erzeugungsauftrag («Neu») ohne Zahlung angelegt wird, endet
  `Freigegeben`.** Er steht dann in unserem Bestand, und FIFO dürfte ihn einem anderen Kunden
  geben. → O2.
- **Der Preis steht am Beleg, nicht im Modul.** Das Modul gibt Partei, Fristen,
  Lieferbedingung und Eigentum vor (`VOUCHER_PRESETS`). Ein neuer Beleg beginnt bei
  «Offerte». → O1.
- **Die Uhr gibt es schon:** «Der Takt» (`services/tick.TASKS`, Cloud Scheduler alle 5
  Minuten, Advisory-Lock, Getanes im Log). Die Wiederkehr wird dort eine Aufgabe mehr.
- **«Zu tun» am Auftrag gibt es schon:** `services/todo` zählt anstehende Papiere am Auftrag;
  dieselbe Zahl am Symbol trägt eine wartende Wiederkehr (→ O3).
- **Ob Stücke von Hand oder per FIFO gewählt wurden, speichert heute niemand.** FIFO ist im
  Entwurf nur ein Vorschlag (`definition-lines.StockPicker`, `preselect`). Nach der Freigabe
  hat jede Lager-Zeile eine fertige Liste von Stücken (`order_lines` + `order_units`), und
  `validate_draft` verlangt genau so viele gewählte Stücke wie die Menge. Die Regel «von Hand
  gewählt → dieselben, sonst FIFO» lässt sich darum **nicht ableiten**. → V3, Grundsatz 14.
- **Wie das System heute mit «geht nicht» umgeht** (Vorbild für O3 und O6):
  - **Beim Freigeben** nennt `orders.validate_draft` alles, was fehlt, als Sätze (Stück ist
    endgültig, zu wenig gewählt, Artikel darf nichts erzeugen). Der Knopf ist gesperrt, und
    der Hover nennt die Sätze. Es entsteht nichts.
  - **Im Verbrauch** ist Unterdeckung kein Zustand (`StepNeed`: gebraucht · verfügbar · am
    Ort). Das Modul ist einfach nicht fertig und bietet «holen lassen» oder «Nachschub
    anlegen» an. Angelegt wird nichts von selbst.
  - **In der Datenerfassung** ist der Halt eine Auskunft, keine Sperre, und das System bietet
    einen Auftrag mit vorgewählten Stücken an.
  - Gemeinsam ist allen: **der Grund steht als Satz da, nichts entsteht still, der Mensch
    entscheidet.**
- **Was es sonst schon gibt:** einen Auftragsentwurf mit vorgewählten Stücken und Ablauf
  (`OrderSeed`), append-only Zeilen «ab Stichtag» (`time_contracts`), den Schalter
  «kehrt zurück ↔ bleibt hier» unter dem Ziel (`flow-column.ReturnRow`, prozessbild §8.1a).

## 5 · Vorschläge

- **V1 · `Verkauft` wird ein regulärer Start** (Richtung entschieden). Umsetzung siehe §4.
- **V2 · Anlegen, nicht anbieten** (entschieden). Die Wiederkehr IST der Entscheid des
  Menschen, nur im Voraus getroffen. Der Grundsatz «automatisch angelegt wird nie etwas» wird
  genauer gefasst: **Nichts entsteht ohne Entscheid eines Menschen.** Anlegen heisst Freigeben,
  mit derselben Prüfung wie von Hand (`orders.validate_draft`).
- **V3 · Die Schlaufe** (Richtung entschieden). Eine Linie vom Ziel zurück an den Anfang der
  Spalte, dorthin, wo die Stücke gewählt werden.
  - **Der Schalter steht unter dem Ziel**, wie die Rückführung: «wiederholt sich» ↔
    «einmalig», dazu Takt und nächster Termin.
  - **Die Linie folgt prozessbild §8.1a:** ein Zug aus `polyPath`, dockt unten an der letzten
    und oben an der ersten Zeile der Spalte an, Haarlinie bis zur ersten Wiederholung, danach
    kräftig. Kein Strichmuster, keine eigene Farbe.
  - **Am Anfang steht, was die Wiederholung nimmt**, je Lager-Zeile eine **Pflichtwahl ohne
    Vorbelegung** (wie das Eigentum am Beleg): «dieselben Stücke» (Service, Abo, fremder Kran)
    oder «nach FIFO» (Lieferung). Eine Zeile «Neu» erzeugt jedes Mal neu. Mehr Möglichkeiten
    gibt es nicht. Ausdrücklich, weil es sich nicht ableiten lässt (§4) und weil eine falsche
    Annahme teuer wäre: wer z. B. zwölf Kartuschen von Hand wählt und «dieselben» bekäme,
    würde nächsten Monat dieselben, schon verkauften Kartuschen noch einmal liefern.
  - **FIFO nimmt weiter nur `Freigegeben`**, «dieselben Stücke» darf auch `Verkauft` (V1).
  - **Neben einer Abweichung:** Die Schlaufe ist ein Zug wie jede Querlinie und bekommt ihre
    Spur aus `process-flow.channels`. Sie reicht über die ganze Spalte, also bekommt sie die
    äusserste Spur, und eine Abweichung daneben liegt innen.
  - **Gespeichert wird append-only**, wie die Verträge der Zeiterfassung: «ab Stichtag: alle
    N Monate am Tag X», später «ab Stichtag: einmalig». Wiederholt wird die eingefrorene
    Definition des Vorlage-Auftrags (Module und Zeilen).
- **V4 · Nie doppelt.** Je Wiederkehr und Periode höchstens ein Auftrag (Unique-Index).
  «Fällig» und «nächster» sind abgeleitet; davon wird nichts gespeichert.
- **V5 · Die Uhr ist der Takt** (gebaut): eine Aufgabe in `services/tick.TASKS`. Sie darf
  beliebig oft laufen, ohne etwas doppelt anzulegen (V4).
- **V6 · Abo durchgespielt** (bestätigt 07.11.2026): Artikel «INEXXIO 365», eine Instanz je
  Abo. Der Vorlage-Auftrag hat genau dieses Stück und ein Modul Zahlung (Einnahme, «geht an
  die Partei»). Jeden Monat entsteht derselbe Auftrag mit einer Rechnung. Einsätze (Reparatur,
  Ersatzgerät) sind gewöhnliche Aufträge daneben. Geht nur zusammen mit V1.

## 6 · Offen

- **O1 · Die Zahlung in der Schlaufe** – entschieden 07.11.2026 (Grundsatz 13). Ein Satz für
  alle Fälle: **Was in der Vorlage zugesagt ist, gilt weiter; was offen war, bleibt offen.**
  - Die Zahlung weiss von der Schlaufe (Idee Clemens): Die Offerte nennt die Wiederkehr
    («alle 12 Monate, bis auf Widerruf»), die Annahme gilt für jede Wiederholung.
  - Jede Wiederholung übernimmt Partei, Anschrift, Eigentum und Positionen.
  - **Fester Preis** (Abo, Pauschale): die Wiederholung steht gleich auf «Zusage»; fällig ist
    nur «Rechnung stellen». Dass die Rechnung von selbst hinausgeht, wäre der erste Eintrag in
    `voucher.AUTO_RELEASE`. Bis dahin steht sie in «zu tun».
  - **Preis nach Aufwand** (Wartung): die Position kommt ohne Preis, der Beleg beginnt bei
    «Offerte», und ein Mensch trägt ein.
  - Ob ein Preis fest ist, sagt eine Vorgabe am Zahlungsmodul («Preis: fest · je Mal»),
    neben den heutigen `VOUCHER_PRESETS`.
  - Das ändert PROCESS_CORE §13.6 («die Zahlung muss von ihr nichts wissen»), aber nur an
    dieser einen Stelle.
- **O2 · Ein fremdes Stück aufnehmen.** Der erste Vorschlag (Erzeugungsauftrag mit Zahlung
  «geht an die Partei») ist **verworfen**: Er hängt das Eigentum an Geld. Wird diese Zahlung
  storniert, gehört der Kundenkran plötzlich uns, und FIFO dürfte ihn weitergeben.
  Neuer Vorschlag: **Eigentum bei der Entstehung.**
  - Eine Zeile «Neu» trägt eine Angabe «gehört: uns | Partei X». Die Vorgabe ist «uns».
  - Die Ableitung bleibt eine Ableitung: das jüngste Zahlungsmodul entscheidet, **und ohne
    Zahlungsmodul gilt der Eigentümer bei der Entstehung** (heute fest «uns»).
  - Folge: Der fremde Kran endet «Verkauft», nie in unserem Bestand und nie bei FIFO. Ein Storno
    ändert daran nichts, weil keine Zahlung beteiligt ist.
  - Offen: Das Wort «Verkauft» passt für einen nie verkauften Kran nicht ganz. Die Bedeutung im
    Katalog ist «gehört einer anderen Partei». Behalten oder umbenennen (z. B. «Bei Partei»)?
- **O3 · Fällig, aber es geht gerade nicht** (Stück in einem anderen Auftrag, zu wenig frei bei
  FIFO, Stück verschrottet, Artikel ersetzt). Vorschlag, zusammen mit O6, **eine** Regel:
  - Der Takt stellt dieselbe Frage wie der Knopf «Freigeben» (`orders.validate_draft`). Eine
    zweite Prüfung gibt es nicht.
  - Ist die Antwort «es fehlt …», entsteht nichts. Die Sätze stehen als Zahl oben am Symbol des
    Vorlage-Auftrags (Hover) und im Feed «zu tun» (`services/todo`, wie anstehende Papiere).
  - Alle 5 Minuten wird neu gefragt. Ist die Antwort leer, entsteht der Auftrag sofort.
  - **Keine Periode geht verloren** (Grundsatz 5): Ist schon die nächste fällig, entstehen sie
    der Reihe nach, wegen der Exklusivität immer einer nach dem anderen. Je Periode höchstens
    ein Auftrag heisst nur «nie doppelt», nicht «auslassen».
  - Bei zu wenig Bestand (FIFO) bietet «zu tun» wie im Verbrauch «Nachschub anlegen» an.
- **O4 · Vorlauf** – später. Idee: «fertig bis» statt «beginnt am», mit der Dauer aus dem Log
  gelernt (wie lange die letzten Wiederholungen liefen; beim ersten Mal die Vorlage selbst).
  Nichts eintippen.
- **O5 · Kunde sieht Fristen** – später, mit dem Shop.
- **O6 · Stück weg** (verschrottet, Artikel ersetzt) – dieselbe Regel wie O3. Ein dauerhafter
  Grund bleibt in «zu tun» stehen, mit dem Angebot «Wiederkehr beenden». Von selbst endet
  nichts.

### Weitere Punkte, die noch festzulegen sind

- **O7 · Wer handelt?** Jedes Schreiben braucht einen Handelnden (`core/actor.act`). Vorschlag:
  das System, im Namen der Person, die die Wiederkehr gesetzt hat (wie die KI im Namen der
  Person). So steht im Log, wessen Entscheid es war.
- **O8 · Welche Anschrift?** Der Beleg friert die Anschrift je Vorgang ein. Zieht der Kunde um,
  nimmt die Wiederholung dann die alte (aus der Vorlage) oder den heutigen Standard aus dem
  Adressbuch? Vorschlag: den heutigen Standard.
- **O9 · Unbezahlt.** Die Stücke passieren die Zahlung mit der Zusage, ein Auftrag kann also
  abgeschlossen sein, während die Rechnung offen ist. Soll die nächste Wiederholung warten,
  solange eine Rechnung überfällig ist? Vorschlag: nein, Überfälliges zählt schon heute in
  «zu tun»; Liefersperre erst, wenn es gebraucht wird.
- **O10 · Monatsende.** «Jeden Monat am 31.» im Februar? Vorschlag: der letzte Tag des Monats.
- **O11 · Wer darf eine Wiederkehr setzen und beenden?** Jede Person mit ERP-Zugang (wie das
  Freigeben eines Auftrags) oder nur der Admin?
- **O12 · Geht die Abo-Rechnung von selbst hinaus?** Heute geht kein Papier von selbst
  (`voucher.AUTO_RELEASE` leer). Vorschlag: zuerst «Prüfen und freigeben» in «zu tun»;
  automatisch erst, wenn es sich bewährt hat.

## 7 · Rückfragen und Antworten

| | Frage | Antwort |
|---|---|---|
| F1 | Was soll besser werden? | Wiederholtes gerät nicht in Vergessenheit, möglichst automatisch; eine Logik für alles |
| F2 | Welcher Fall zuerst? | keiner – eine Logik für alle |
| F3 | Anlegen oder anbieten? | anlegen (V2); wartend als Zahl am Symbol und im Feed «zu tun» (O3) |
| F4 | Kalender oder letzte Erledigung? | fester Kalendertag (wie ein Abo) |
| F5 | Takte ausser Zeit? | später; nur vorsehen |
| F6 | Voriger Auftrag noch offen? | warten, bis das Stück frei ist, dann sofort; keine Periode geht verloren |
| F7 | Jeder Kran ein Stück? | ja, auch ein fremder (Artikel + Instanz) |
| F8 | Service am verkauften Stück eine Abweichung? | nein → V1, Folgen §4 |
| F9 | Je Einsatz oder Pauschale? | dieselbe Logik, das Abo ist ein Stück (V6) |
| F10 | Vertrag als eigenes Ding? | die Wiederkehr ist der Vertrag; Abschluss später online |
| F11 | Wie endet sie? | jederzeit änderbar und beendbar, ohne Frist |
| F12 | Ablauf ändert sich? | beenden, neuer Auftrag, neue Wiederkehr |
| | Darstellung? | Schlaufe im Prozessbild wie die Rückführung, nicht als eigene Karte (V3) |
| | Was nimmt die Wiederholung? | von Hand gewählt → dieselben, sonst FIFO; da nicht ableitbar: Pflichtwahl je Zeile (V3) |
| | Zahlung fest oder offen? | was vorher festgelegt ist, gilt; was offen blieb, wird jedes Mal festgelegt (O1) |
