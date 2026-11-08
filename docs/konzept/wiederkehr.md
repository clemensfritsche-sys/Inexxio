# Projektakte «Wiederkehrende Aufträge»

> **Kopfstatus:** in Klärung · **nichts gebaut** · Lead: Claude · Entscheid: Clemens Fritsche ·
> seit 06.11.2026 · zuletzt 08.11.2026 (neunte Runde) · Bauplan in §8
> Bild (Ist-Stand 1:1, Schlaufe, Abo): https://claude.ai/artifact/Lk5AKy8G1CTWi68ZxA57uj
> Diese Akte ist die **eine** Quelle für Ziel, Grundsätze, Vorschläge und Entscheide. Das Bild
> zeigt, die Akte hält fest. Was hier nicht als entschieden steht, ist nicht entschieden.
> Ausgangspunkt im Kern: `PROCESS_CORE.md` §13 Punkt 6.

## 0 · Kurzfassung (zum Prüfen)

**So funktioniert es**
1. Die Schlaufe wird **im Entwurf** eines ganz gewöhnlichen Auftrags eingeschaltet: unter dem Ziel
   der Schalter «einmalig ↔ wiederholt sich»; die Linie läuft vom Ziel zurück an den Anfang. Mit
   der Freigabe ist sie eingefroren wie alles am Auftrag. Nach der Freigabe lässt sich keine mehr
   einschalten.
2. **Eingestellt wie ein Dauerauftrag:** wie oft, ab wann, bis wann (unbefristet · Datum ·
   Anzahl). Je Lager-Zeile: «gleiche Einzelinstanzen» oder «FIFO»; eine Zeile «Neu» erzeugt jedes
   Mal neu. Fällt der Tag auf den 29.–31., gilt in kürzeren Monaten der letzte Tag.
3. **Der Takt prüft alle 5 Minuten:** Ist der nächste Termin eines Auftrags mit Schlaufe erreicht
   und hat er noch keinen Nachfolger, stellt er dieselbe Frage wie der Knopf «Freigeben», dazu:
   wäre es eine Abweichung? Der Nachfolger ist eine **1:1-Kopie**: dieselben Module, dieselben
   Zeilen, **dieselbe Schlaufe**.
   - nichts fehlt → der Auftrag entsteht sofort (im Namen der Person, die die Schlaufe setzte),
   - fehlt gerade → er **wartet** und fragt wieder; die Zahl am Symbol nennt den Grund,
   - fehlt für immer → **geht nicht mehr**; nur «Beenden».
4. **Jede Wiederholung ist ein gewöhnlicher Auftrag.** Jeder Auftrag hat höchstens **einen**
   Nachfolger; so entsteht eine Kette, und keine Periode geht verloren. Aufträge von Hand gehen
   jederzeit und verschieben nichts. Ein Auftrag ist nach seinem Ziel abgeschlossen, für immer.
5. **Zahlung wie bei jedem Auftrag:** Was im Modul vorgegeben ist (Partei, Eigentum, Fristen,
   neu auch Positionen mit Preis), kommt mit. Was beim Ausführen gewählt wird (Anschrift, ein
   offener Preis), wird beim Ausführen gewählt, mit dem neuesten Stand. **Immer dieselben
   Schritte:** Offerte → Zusage → Rechnung. Hat die Partei die Wiederholung schon zugesagt und
   sind alle Preise vorgegeben, **macht das System Offerte und Zusage selbst** und schreibt
   dazu, worauf es sich stützt. Die Rechnung geht mit «Prüfen und freigeben».
6. **Beenden** jederzeit, am **neuesten** Auftrag der Kette (dem ohne Nachfolger), endgültig. Was
   läuft, läuft fertig. Ältere Aufträge zeigen nur «weiter in Auftrag …». Ändern gibt es nicht;
   weiter geht es mit einem neuen Auftrag. Setzen und beenden darf jede Person mit ERP-Zugang.

**Was sich an Bestehendem ändert**
- **«Verkauft» wird ein regulärer Start** (keine Abweichung mehr). FIFO und Verbrauch nehmen
  weiter nur «Freigegeben».
- **«Automatisch angelegt wird nie etwas»** wird zu **«Nichts entsteht ohne Entscheid eines
  Menschen»**; die Schlaufe ist dieser Entscheid, im Voraus.
- **Die Zahlung kennt die Schlaufe** an einer Stelle: Die Offerte nennt die Wiederholung; in
  einer Wiederholung führt das System Offerte und Zusage mit denselben Verben aus, die sonst ein
  Mensch auslöst (PROCESS_CORE §13.6 wird angepasst). Dazu, allgemein und nicht nur für die
  Schlaufe: **Positionen mit Preis als Vorgabe im Zahlungsmodul.**
- **Keine neue Tabelle.** Die Schlaufe besteht aus drei Ereignissen im Log (§4b). Es gibt keine
  «Vorlage» und keine Urreferenz: jeder Auftrag trägt seine eigene Schlaufe. Fällig, nächster,
  wartet: alles abgeleitet.

**Bewusst nicht:** Vorlauf (später), Fristen für den Kunden (mit dem Shop), Liefersperre bei
unbezahlt, Zähler wie Betriebsstunden, Wieder einschalten, Kopie als Entwurf.

**Folgen, die man kennen muss:** Nach langer Blockade kommen mehrere Perioden nacheinander. Ein
fester Preis bleibt fest; eine Erhöhung heisst beenden, neu anbieten, neue Schlaufe. Was im
laufenden Auftrag passiert (Abweichungen, gekappte Rückführung), passiert wie in jedem Auftrag.

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
6. **Jederzeit beendbar, ohne Kündigungsfrist.** Ändert sich etwas (Takt, Ablauf, ein Prüfpunkt
   mehr), wird die Wiederkehr beendet und ein neuer Auftrag mit eigener Wiederkehr angelegt
   (präzisiert 08.11.2026, O14).
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
14. **Was die Wiederholung nimmt, sagt der Mensch je Zeile ausdrücklich**: «gleiche
    Einzelinstanzen» oder «FIFO». Es steht **unten bei der Schlaufe**, zusammen mit Takt und Ende
    (07.11.2026, → V3).
15. **Eingestellt wird wie ein Dauerauftrag im E-Banking**: wiederholen (wöchentlich ·
    monatlich · vierteljährlich · halbjährlich · jährlich), erste Ausführung, Ende
    (unbefristet · am Datum · nach Anzahl). Nichts Eigenes erfinden (07.11.2026, → O10).
16. **Setzen, ändern und beenden darf jede Person mit ERP-Zugang** (07.11.2026, O11).
17. **Jede Wiederholung ist eine 1:1-Kopie ihres Vorgängers, Schlaufe eingeschlossen**
    (entschieden 08.11.2026). Es gibt keine Vorlage und keine Urreferenz; jeder Auftrag hat
    höchstens einen Nachfolger. Ein abgeschlossener Auftrag bleibt abgeschlossen, für immer.
    Beendet wird am neuesten Auftrag der Kette.
18. **Beenden ist endgültig, wie bei einem Dauerauftrag** (07.11.2026). Es gibt kein «Wieder
    einschalten» und keine Kopie als Entwurf. Wer weitermachen will, legt einen neuen Auftrag
    mit eigener Schlaufe an.

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
  - **Tests (geprüft 08.11.2026):** Kein Test und keine Zeile der Matrix verlangt «verkauft ⇒
    Abweichung» (`tests/matrix.py`, `test_zahlung_ablauf.test_return_repair_and_cancelled_return`
    prüft nur das Eigentum). Die Wächter für «gesperrt, verbaut, im Prozess ⇒ Abweichung» bleiben.
  - **Oberfläche:** Der Hover im Entwurf sagt heute «Verkauft – … (Abweichung)»
    (`definition-lines.tsx`); er wird ohne «(Abweichung)» geschrieben.
  - **Zu Ende gedacht:** Ein verkauftes Stück steckt in keinem Auftrag, also nimmt man es niemandem
    weg; es ist nicht gesperrt, also hebt man keine Sperre auf; es steckt in nichts, also baut man
    nichts aus. Genau diese drei Fälle sind der Grund für das Abweichungs-Zeichen
    (PROCESS_CORE §12.2: Entzug, Sonderfreigabe, Ausbau). Eine Retoure gehört nicht dazu: Sie ist
    eine Eigentumsfrage und steht in ihrer Zahlung. **V1 nimmt damit nur einen Fall heraus, der
    nie wirklich hineingehörte.**
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
- **Abweichungen in einer Wiederholung** (geprüft 08.11.2026): Die Wiederholung ist ein
  gewöhnlicher Auftrag; was in ihr passiert (Abzweigung, Rückführung, gekappte Rückführung,
  «Abgebrochen»), passiert wie in jedem Auftrag. Die Schlaufe liest davon nur eines: ob die
  Stücke für die **nächste** Periode frei sind. Ein Abweichungsauftrag selbst trägt nie eine
  Schlaufe (Grundsatz 3). Gefunden: kein Konflikt.
- **Wo die Schlaufe gezeichnet wird:** links. Im Prozessbild stehen Herkunfts-Aufträge links und
  Abweichungen rechts (`process-columns`). Ein Auftrag mit Schlaufe ist immer regulär, hat also
  nie Herkunfts-Aufträge: **die linke Seite ist immer frei.** Schlaufe und Abweichung kreuzen
  sich darum nie. Bild: Teil 3, «mit Abweichung».
- **Vorbild für «nie doppelt» im Log:** `ix_log_decided` (Migration 170) ist ein eindeutiger
  Index auf einem Feld der Nutzlast eines Ereignisses (je Vorschlag genau ein Entscheid).
- **Was es sonst schon gibt:** einen Auftragsentwurf mit vorgewählten Stücken und Ablauf
  (`OrderSeed`), append-only Zeilen «ab Stichtag» (`time_contracts`), den Schalter
  «kehrt zurück ↔ bleibt hier» unter dem Ziel (`flow-column.ReturnRow`, prozessbild §8.1a).

## 4b · Speicherung: keine neue Tabelle (Vorschlag 08.11.2026)

Die Schlaufe ist ein Entscheid, der geschieht («ab 14.11. jährlich», gesetzt von wem, wann),
also steht sie im Log, wie die Vorschläge und Entscheide der KI. Das Log ist ohnehin
unveränderlich und schreibt Handelnden und Zeit selbst; eine eigene Tabelle müsste genau das
nachbauen.

| Ereignis | an | Nutzlast | wann |
|---|---|---|---|
| `loop.set` | der Auftrag | Takt, sein Termin, Ende (Datum oder verbleibende Anzahl), je Lager-Zeile «gleiche Einzelinstanzen» oder «FIFO» | mit seiner Freigabe, **in derselben Transaktion** |
| `loop.next` | der Nachfolger | Vorgänger, Termin | wenn der Takt den Nachfolger anlegt, **in derselben Transaktion** |
| `loop.ended` | der Auftrag | – | beim Beenden (nur am neuesten der Kette) |

- **Nie doppelt:** ein eindeutiger Index auf den Vorgänger in `loop.next`, gebaut wie
  `ix_log_decided` – je Auftrag höchstens ein Nachfolger. Ein zweiter Lauf scheitert an der
  Datenbank, nicht an einer Prüfung.
- **Der Nachfolger** bekommt sein eigenes `loop.set`: dieselbe Einstellung, der nächste Termin, bei
  «nach Anzahl» eins weniger. Bei 0 oder nach dem Enddatum entsteht keins mehr – die Kette endet
  von selbst.
- **Abgeleitet:** «läuft» = `loop.set`, kein `loop.next` mit ihm als Vorgänger, kein
  `loop.ended`; «fällig» = sein Termin plus Takt ist erreicht; «wartet» = fällig, und die
  Freigabe-Prüfung sagt «fehlt»; «weiter in Auftrag …» = sein Nachfolger aus `loop.next`.
- **Unveränderlich** ist das Log ohnehin; «nur anhängen» braucht keinen eigenen Trigger.
- **Gestrichen:** die Anzeige «2 Aufträge bisher». Sie braucht niemand, der Verlauf zeigt die
  Aufträge. Bräuchte man sie, wäre sie eine Zählung der Kette im Log.
- **Und die Zeiterfassung?** (Rückfrage 08.11.2026) Sie bleibt, wie sie ist. Ihre Einträge
  sind Daten, mit denen täglich gerechnet wird (Stundenkonto aus vielen Einträgen, Ersetzungen,
  7-Tage-Regel, nur für die Person sichtbar); dafür ist eine eigene Tabelle richtig, und das Log
  hält jede Zeile ohnehin selbst fest. Die Verträge (`time_contracts`) sind älter als das Log;
  heute stünden sie vielleicht dort, aber umbauen brächte nichts. Die Wiederkehr berührt die
  Zeiterfassung nicht.
- **Die Alternative**, falls Einstellungen im Log stören: eine kleine Tabelle mit append-only
  Zeilen wie `time_contracts`, dazu eine Spalte am Auftrag für den Vorgänger mit eindeutigem
  Index. Funktioniert genauso, ist eine Tabelle und eine Spalte mehr.
- Alles, was die Schlaufe tut, steht damit im Log: einschalten, jeder Nachfolger, beenden; dazu
  `tick.loop` (nur wenn etwas getan wurde) und die Freigabe des Auftrags wie bei jedem Auftrag.

## 5 · Vorschläge

- **V1 · `Verkauft` wird ein regulärer Start** (entschieden 08.11.2026). Umsetzung siehe §4.
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
    Vorbelegung** (wie das Eigentum am Beleg): «gleiche Einzelinstanzen» (Service, Abo, fremder Kran)
    oder «FIFO» (Lieferung). Eine Zeile «Neu» erzeugt jedes Mal neu. Mehr Möglichkeiten
    gibt es nicht. Ausdrücklich, weil es sich nicht ableiten lässt (§4) und weil eine falsche
    Annahme teuer wäre: wer z. B. zwölf Kartuschen von Hand wählt und «gleiche Einzelinstanzen» bekäme,
    würde nächsten Monat dieselben, schon verkauften Kartuschen noch einmal liefern.
  - **FIFO nimmt weiter nur `Freigegeben`**, «gleiche Einzelinstanzen» darf auch `Verkauft` (V1).
  - **Neben einer Abweichung:** Die Schlaufe läuft links (§4), die Abweichung wie heute rechts.
    Gezeichnet mit demselben Liniengenerator (`polyPath`).
  - **Gespeichert** als Ereignisse im Log (§4b). Wiederholt wird die eingefrorene Definition
    des Vorgängers (Module, Zeilen, Schlaufe), als 1:1-Kopie.
- **V4 · Nie doppelt.** Je Schlaufe und Periode höchstens ein Auftrag, eindeutiger Index im Log
  (§4b). «Fällig» und «nächster» sind abgeleitet.
- **V5 · Die Uhr ist der Takt** (gebaut): eine Aufgabe in `services/tick.TASKS`. Sie darf
  beliebig oft laufen, ohne etwas doppelt anzulegen (V4).
- **V6 · Abo durchgespielt** (bestätigt 07.11.2026): Artikel «INEXXIO 365», eine Instanz je
  Abo. Der erste Auftrag hat genau dieses Stück und ein Modul Zahlung (Einnahme, «geht an
  die Partei»). Jeden Monat entsteht derselbe Auftrag mit einer Rechnung. Einsätze (Reparatur,
  Ersatzgerät) sind gewöhnliche Aufträge daneben. Geht nur zusammen mit V1.

## 6 · Offen

- **O1 · Die Zahlung in der Schlaufe** – präzisiert 08.11.2026: **immer dieselben Schritte,
  nur manchmal automatisch, und immer dokumentiert.**
  - Eine Wiederholung ist ein neuer Auftrag aus derselben eingefrorenen Definition, das
    Zahlungsmodul eingeschlossen. **Was im Modul vorgegeben ist**, kommt mit (Partei, Eigentum,
    Fristen, Lieferbedingung). **Was beim Ausführen gewählt wird**, wird beim Ausführen gewählt,
    mit dem neuesten Stand (die Anschrift aus dem Adressbuch, ein offener Preis).
  - **Neu, allgemein:** Positionen mit Preis als Vorgabe im Zahlungsmodul, neben den heutigen
    `VOUCHER_PRESETS`. Das nützt jedem Auftrag, nicht nur der Schlaufe.
  - **Der Beleg geht jedes Mal Offerte → Zusage → Rechnung.** Kein Schritt wird übersprungen,
    keine Stufe wird gesetzt. Die Offerte des ersten Auftrags nennt die Wiederholung (aus `loop.set`:
    «jährlich, ab 14.11.2027, bis auf Widerruf»). Hat die Partei sie angenommen und sind **alle**
    Preise vorgegeben, führt das System in jeder Wiederholung **Anbieten und Zusagen selbst aus –
    mit denselben Verben** (`VERBS`), die sonst ein Mensch auslöst, als Handelnder «System» im
    Namen der Person, mit dem Vermerk «gestützt auf die Zusage vom 28.10.2026 zu Auftrag
    100004812». In der Karte stehen die Stationen darum ✓ Offerte ✓ Auftragsbestätigung, mit
    diesem Satz; im Log stehen beide Handlungen wie sonst auch.
  - Fehlt ein Preis, hält der Automat bei der Offerte an, und ein Mensch macht weiter, wie bei
    jedem Beleg.
  - Die Papiere (Offerte, AB) entstehen wie immer als Dokumente; hinaus geht nichts von selbst.
    Die Rechnung geht mit «Prüfen und freigeben» (O12).
  - **Wo:** eine Funktion an einer Stelle (Takt, nach dem Anlegen). Der Beleg selbst kennt
    keine Schlaufe, kein `if` in Verben, Stufen oder Papieren.
  - PROCESS_CORE §13.6 («die Zahlung muss von ihr nichts wissen») wird an dieser einen Stelle
    angepasst.
- **O2 · Ein fremdes Stück aufnehmen** – entschieden 07.11.2026: **nichts Besonderes.** Ein
  fremder Kran wird angelegt wie jeder Artikel (Artikel, Erzeugungsauftrag «Neu»). Bis er eine
  Zahlung «geht an die Partei» passiert, steht er als `Freigegeben` bei uns; das ist so gewollt.
  FIFO schlägt ihn dann zwar vor, aber nur als Vorschlag im Entwurf, den ein Mensch sieht.
  Die Vorschläge «Zahlung bei der Aufnahme» und «Eigentum bei der Entstehung» sind verworfen.
- **O3 · Fällig, aber es geht gerade nicht** (Stück in einem anderen Auftrag, zu wenig frei bei
  FIFO, Stück verschrottet, Artikel ersetzt). Vorschlag, zusammen mit O6, **eine** Regel:
  - Der Takt stellt dieselbe Frage wie der Knopf «Freigeben» (`orders.validate_draft`). Eine
    zweite Prüfung gibt es nicht. **Dazu eine Frage:** wäre der Auftrag eine Abweichung? Steht
    ein Stück z. B. auf `Gesperrt` (die letzte Prüfung ist durchgefallen), gilt das als «fehlt
    gerade» – sonst entstünde eine Wiederholung als Abweichung (Grundsatz 3).
  - Ist die Antwort «es fehlt …», entsteht nichts. Die Sätze stehen als Zahl oben am Symbol des
    neuesten Auftrags der Kette (Hover) und im Feed «zu tun» (`services/todo`, wie anstehende Papiere).
  - Alle 5 Minuten wird neu gefragt. Ist die Antwort leer, entsteht der Auftrag sofort.
  - **Keine Periode geht verloren** (Grundsatz 5): Ist schon die nächste fällig, entstehen sie
    der Reihe nach, wegen der Exklusivität immer einer nach dem anderen. Je Periode höchstens
    ein Auftrag heisst nur «nie doppelt», nicht «auslassen».
  - Bei zu wenig Bestand (FIFO) bietet «zu tun» wie im Verbrauch «Nachschub anlegen» an.
- **O4 · Vorlauf** – später. Idee: «fertig bis» statt «beginnt am», mit der Dauer aus dem Log
  gelernt (wie lange die letzten Wiederholungen liefen; beim ersten Mal der erste Auftrag selbst).
  Nichts eintippen.
- **O5 · Kunde sieht Fristen** – später, mit dem Shop.
- **O6 · Stück weg** (verschrottet, Artikel ersetzt) – entschieden 07.11.2026: dieselbe Regel
  wie O3, aber der Grund vergeht nicht. Die Schlaufe steht rot auf «geht nicht mehr», die Zahl am
  Symbol ist rot, und es gibt **nur «Beenden»**, wie bei einem Dauerauftrag (Grundsatz 18). Von
  selbst endet nichts. Bild: Teil 3, Zustand «geht nicht mehr».
- **Beenden**: «Ab heute beenden» in der Einstellung der Schlaufe, am neuesten Auftrag der Kette.
  Es wird eine Zeile «ab heute: beendet» (append-only, endgültig). Was schon entstanden ist,
  läuft normal zu Ende. Die Linie verschwindet; war sie schon kräftig (es gab Wiederholungen),
  bleibt sie nach prozessbild §8.1a kräftig stehen, und der Schalter sagt «einmalig».
  **Verbaut man sich damit etwas?** Nein: Ein neuer Auftrag kann jederzeit dieselben Instanzen
  nehmen und eine eigene Schlaufe tragen. Es fehlt nur die Bequemlichkeit einer Kopie, keine
  Möglichkeit. Das ist auch der Weg, wenn sich der Ablauf ändert (F12).

### Weitere Punkte, die noch festzulegen sind

- **O7 · Wer handelt?** – ok 07.11.2026: das System, im Namen der Person, die die Wiederkehr
  gesetzt hat.
- **O8 · Welche Anschrift?** – entschieden 07.11.2026: die **heutige**. Ändert sich nichts,
  ändert sich nichts; ist im Adressbuch eine neuere Standard-Anschrift, nimmt die Wiederholung
  diese.
- **O9 · Unbezahlt** – entschieden 07.11.2026: nichts vorsehen, bleibt wie heute. Gut zu wissen:
  Bei **Vorauszahlung** (Zahlungsfrist 0 Tage) passieren die Stücke die Zahlung erst mit dem
  Geld (`voucher.passable`). Ein unbezahltes Abo hält damit seinen Auftrag offen, und die
  nächste Wiederholung wartet von selbst. Das folgt aus der heutigen Regel, nichts Neues.
- **O10 · Monatsende** – entschieden 07.11.2026: wie ein Dauerauftrag. Die erste Ausführung
  legt den Tag fest. Fällt er auf den 29.–31., gilt in kürzeren Monaten der letzte Tag des
  Monats. Wochenenden verschieben nichts (ein Auftrag ist keine Buchung).
- **O11 · Rechte** – entschieden 07.11.2026: jede Person mit ERP-Zugang.
- **O12 · Geht die Abo-Rechnung von selbst hinaus?** – ok 07.11.2026: zuerst «Prüfen und
  freigeben» in «zu tun»; automatisch (`voucher.AUTO_RELEASE`) erst, wenn es sich bewährt hat.

- **O13 · Ein Stück der Schlaufe ist endgültig weg** – entschieden 08.11.2026. Beim Anlegen
  einer Wiederholung gehen nur Einzelinstanzen hinein, die `Freigegeben` oder `Verkauft` sind.
  - **endgültig weg** (`Verschrottet`): die Schlaufe **geht nicht mehr**. Sie läuft nie mit einem
    Teil weiter, auch nicht mit Vermerk; das wäre eine harte Regel, verbogen. Ein Mensch beendet
    sie und legt einen neuen Auftrag an (Grundsatz 18).
  - **gerade nicht frei** (in einem Auftrag, gesperrt, verbaut): die Wiederholung **wartet**, bis
    es frei ist.
  - Was danach im laufenden Auftrag passiert, ist Sache des Auftrags (Abweichungen wie überall).

### Letzte Prüfung auf Schlupflöcher (08.11.2026, Vorschläge)

- **O14 · Ändern gibt es nicht** – entschieden 08.11.2026. Die Einstellung wird einmal gesetzt, danach nur beendet – wie ein
  Artikel und ein freigegebener Auftrag. Sonst stünden Grundsatz 6 («änderbar») und 18
  («beenden ist endgültig») gegeneinander.
- **O15 · Wo man sie setzt** – entschieden 08.11.2026: **nur im Entwurf**, vor der Freigabe, an
  einem Auftrag, der regulär startet (Grundsatz 3). Nach der Freigabe lässt sich keine Schlaufe
  mehr einschalten; dann legt man einen neuen Auftrag an. Die Kette (Grundsatz 17) macht
  «Wiederholung einer Wiederholung» unnötig: jede Wiederholung trägt die Schlaufe ohnehin weiter.
  «Ab» (der erste Termin) ist heute oder später.
- **O16 · Die automatische Zusage** – mit O15 erledigt. Weil die Schlaufe vor der Freigabe feststeht,
  nennt die Offerte des ersten Auftrags sie immer, und die Partei sagt **mit** der Wiederholung zu.
  Jede Wiederholung stützt sich auf die Zusage ihres Vorgängers (der sich wieder auf seinen stützt);
  der Vermerk nennt die ursprüngliche Annahme. Fehlt ein Preis, wartet der Beleg bei der Offerte.
- **O17 · Verbaut ist «gerade nicht frei», nicht «endgültig weg»** – ok 08.11.2026. Eine Schlaufe über ein
  verbautes Stück wartet, bis es ausgebaut ist – womöglich lange. Sichtbar in «zu tun»; beenden
  kann jeder. Endgültig ist nur `Verschrottet` (die eine Stelle: `statuses.terminal`).

## 6a · Sackgassen-Prüfung (07.11.2026)

Gefragt: Gibt es einen Zustand, aus dem man nicht mehr herauskommt?

| Fall | Was passiert | Ausweg | Sackgasse? |
|---|---|---|---|
| Stück steckt in einem Auftrag, der nie fertig wird | Wiederholung wartet, «zu tun» nennt den Auftrag | den Auftrag fertig machen oder abbrechen (Abweichung mit gekappter Rückführung) | nein |
| Stück verschrottet, Artikel ersetzt | «geht nicht mehr» | Beenden, dann ein neuer Auftrag | nein |
| Service-Vertrag über 3 Krane, einer verschrottet | «geht nicht mehr» (O13) | beenden, neuer Auftrag mit den 2 übrigen | nein |
| Prüfung durchgefallen, Kran `Gesperrt` | wäre eine Abweichung → wartet (O3) | Kran instand stellen (ein Auftrag hebt die Sperre auf) | nein |
| Zwei Schlaufen am selben Kran (Prüfung jährlich, Wartung halbjährlich) am selben Tag | Exklusivität: eine wartet auf die andere | keiner nötig, läuft nacheinander | nein. Beides in einem Besuch ist ein eigener Wunsch für später |
| Lange blockiert, mehrere Perioden fällig | entstehen der Reihe nach, keine geht verloren (Grundsatz 5) | wer das nicht will: beenden | nein, aber es kann eine Reihe von Aufträgen nacheinander geben, z. B. zwei Prüfungen kurz hintereinander |
| FIFO-Lieferung, Lager leer | «fehlt gerade: 12 gebraucht, 7 frei», wartet | Nachschub (wie im Verbrauch angeboten) | nein |
| Preis steigt beim Abo | fester Preis gilt weiter | beenden, neu anbieten, neue Schlaufe (F12) | nein |
| Takt fällt aus (Cloud Scheduler) | nichts entsteht, bis er wieder läuft; der Alarm geht per Mail (Takt) | holt nach: jede Periode ohne Auftrag ist weiter fällig | nein |
| Doppelt angelegt durch zwei Läufe | unmöglich: je Schlaufe und Periode ein Unique-Index | – | nein |

**Ergebnis:** keine Sackgasse. Jeder Halt hat einen Grund in einem Satz und einen Weg hinaus,
und der Weg ist immer eine Handlung, die es schon gibt (Auftrag fertig machen, abbrechen,
beenden, neuer Auftrag). Zwei Folgen sind gewollt, aber man muss sie kennen: Eine Schlaufe
lässt nie still ein Stück weg, und nach langer Blockade kommen die Perioden der Reihe nach.

## 8 · Bauplan (Entwurf 08.11.2026)

Gebaut wird auf einem Feature-Branch (`claude/wiederkehr`); nach `develop` erst nach Freigabe.
**In zwei Runden**, jede einzeln getestet und deploybar:
- **Runde 1 – Fundament** (Schritte 0–2): Soll notieren, `Verkauft` regulär, Preise als Vorgabe.
  Ändert Bestehendes, darum zuerst und für sich auf `inexxio-dev` prüfen.
- **Runde 2 – die Schlaufe** (Schritte 3–7): Kalender, Log, Takt, Zahlung, Oberfläche, Abschluss.
  Backend und Oberfläche zusammen, weil die Schlaufe ohne Oberfläche niemand einschalten kann.

### Leitplanken (aus der Akte, verbindlich)

- **Eine Wiederholung ist ein ganz gewöhnlicher Auftrag**, nur ausgelöst vom Takt. Sie entsteht
  über **denselben Weg wie «Freigeben»** (`orders.validate_draft` → `orders.create_order`). Es
  gibt keinen zweiten Anlageweg und keine Sonderregel im Prozess.
- **Nichts Neues, wo es Bestehendes gibt:** der Takt (`services/tick.TASKS`), das Log
  (Ereignisse, eindeutiger Index wie `ix_log_decided`), die Verben der Zahlung (`VERBS`), «zu tun»
  (`services/todo`), der Liniengenerator (`polyPath`).
- **Zwei Formen einer Regel, nie zwei Regeln:** was eine Wiederholung verhindert, sagt **eine**
  Funktion als Satz (`loop.problem`) und prüft **dieselbe** beim Anlegen.
- **Keine neue Infrastruktur, keine laufenden Kosten.**

### Schritte

Jeder Schritt ist für sich lauffähig, getestet und einzeln deploybar. Die Reihenfolge folgt den
Abhängigkeiten.

#### 0 · Soll notieren (nur Doku)
- `SYSTEM_LOGIC.md`: die neuen Sätze als Soll, **bevor** gebaut wird (Verkauft regulär; je
  Schlaufe und Periode höchstens ein Auftrag; keine Periode geht verloren; endgültig weg ⇒ geht
  nicht mehr; nie ein Teil-Auftrag; Abweichung trägt keine Schlaufe).
- `tests/matrix.py`: die Zeilen dazu, mit Soll.
- `PROCESS_CORE.md` §13 Punkt 6 wird ein eigener Abschnitt «Wiederkehr» (Verweis auf die Akte);
  §12.2 Regelstart; §13.6 die eine Stelle der Zahlung.

#### 1 · `Verkauft` ist ein regulärer Start (V1)
- `domain/statuses`: ein **zweiter Name** `REGULAR_STARTS = {FREIGEGEBEN, VERKAUFT}` neben
  `START_BEFORE` (bleibt `Freigegeben` – Bestand, FIFO, Verbrauch).
- `order_state.deviation_flags` vergleicht gegen `REGULAR_STARTS`.
- Hinweis im Entwurf ohne «(Abweichung)» (`definition-lines.tsx`).
- Tests: Service am verkauften Stück ist regulär · Retoure ist regulär und durch «geht an uns»
  belegt · **Wächter:** FIFO und Verbrauch nehmen nie ein verkauftes Stück (gegen die Bug-Form
  «`START_BEFORE` auf die Menge umgestellt» gegengeprüft).
- Doku: SYSTEM_LOGIC T7e/U6c, Kommentare in `statuses.py`, CLAUDE.md.

#### 2 · Preise als Vorgabe im Zahlungsmodul (allgemein)
- `VOUCHER_PRESETS` um **Positionen** erweitert (Artikel/Text, Menge, Preis, Steuersatz); leer =
  wie heute (wird in der Offerte gesetzt). Eingefroren mit dem Modul wie jede Vorgabe.
- Der Beleg übernimmt vorgegebene Positionen beim Entstehen; sie sind `fixed` (punktiert, Hover).
- Nützt jedem Auftrag. Tests: mit und ohne Vorgabe; eine vorgegebene Position lässt sich am Beleg
  nicht ändern.

#### 3 · Die Schlaufe: Kalender und Speicherung
- `domain/loop.py` (rein, ohne Datenbank): Takte (wöchentlich · monatlich · vierteljährlich ·
  halbjährlich · jährlich), **Perioden** ab «erste Ausführung», Ende (unbefristet · Datum ·
  Anzahl), Monatsende → letzter Tag, Tage in Europe/Zurich. Tests: 31. im Februar, Schaltjahr,
  Jahreswechsel, Ende nach Anzahl.
- Log-Ereignisse `loop.set` · `loop.next` · `loop.ended` (§4b) mit Schema (Pydantic).
  **Migration:** eindeutiger Index auf den Vorgänger in `loop.next`, gebaut wie
  `ix_log_decided`; dazu ein Index zum Lesen laufender Schlaufen.
- Die Schlaufe ist Teil des **Entwurfs** (`OrderDraft`) und wird mit der Freigabe als `loop.set`
  geschrieben, in derselben Transaktion wie der Auftrag (O15). `validate_draft` prüft sie mit:
  regulärer Start, «Ab» heute oder später, je Lager-Zeile eine Wahl ohne Vorbelegung.
- `services/loop.py`: `end` · `due` (abgeleitet) · `problem` (der eine Satz, warum es gerade nicht
  geht, oder «geht nicht mehr») · `create_next`.
- `history.HIDDEN_EVENTS`? Nein: einschalten, jede Wiederholung und beenden stehen im Verlauf.

#### 4 · Der Takt legt an
- `tick.TASKS` + `Task("loop", …)`. Je fälligem Auftrag ohne Nachfolger, älteste zuerst, in
  eigener Transaktion: den Entwurf als **1:1-Kopie** bauen (Module, Zeilen nach der Wahl: gleiche
  Einzelinstanzen bzw. FIFO-Vorschlag des Servers bzw. «Neu», die Schlaufe mit dem nächsten
  Termin), `validate_draft` fragen, bei leerer Antwort `create_order` + `loop.next` in
  **derselben** Transaktion. Handelnder «System» im Namen der Person, die die Kette begann.
- Antwort nicht leer → nichts schreiben (Leerlauf steht nicht im Log); `loop.problem` liefert den
  Satz für «zu tun». Zeitgrenze wie die anderen Aufgaben; was nicht fertig wird, nimmt der
  nächste Lauf.
- Zusätzlich zur Freigabe-Prüfung: **keine Abweichung** (alle Stücke in `REGULAR_STARTS`) und
  **keine endgültig weggefallene Einzelinstanz** (→ «geht nicht mehr»).
- `services/todo`: wartende und unmögliche Schlaufen zählen am Symbol des neuesten Auftrags der
  Kette (rot bei «geht nicht mehr»).
- Tests: nie doppelt (zwei Läufe gleichzeitig) · wartet und entsteht, sobald frei · mehrere
  Perioden nacheinander · verschrottet ⇒ geht nicht mehr · beendet ⇒ nichts mehr · Abweichung in
  einer Wiederholung stört die nächste nicht · nach Anzahl endet die Kette von selbst.

#### 5 · Die Zahlung in der Wiederholung
- Die Offerte (Papier) nennt die Schlaufe, wenn es eine gibt; der Satz gehört zur **angenommenen
  Fassung** (`offered_hash`).
- Nach dem Anlegen einer Wiederholung: Sind alle Positionen vorgegeben **und** hat die Partei
  beim Vorgänger zugesagt (selbst oder gestützt), führt **eine** Funktion `ask` und `agree` aus –
  dieselben Verben, Handelnder «System», Vermerk «gestützt auf die Zusage vom … zu Auftrag …»
  (Ereignis `voucher.action` wie immer). Sonst nichts: der Beleg wartet bei der Offerte.
- Hinaus geht nichts von selbst (AB und Rechnung über «Prüfen und freigeben»).
- Tests: Abo läuft bis «Rechnung stellen» · ohne Preis hält es bei der Offerte · die Zusage trägt
  über mehrere Glieder der Kette und nennt die ursprüngliche Annahme.

#### 6 · Oberfläche
- Im **Entwurf** unter dem Ziel der Schalter «einmalig ↔ wiederholt sich» und die Karte zum
  Einstellen (Wiederholen · Ab · Bis · Nimmt). Im **freigegebenen** Auftrag dieselbe Karte nur
  lesend; am neuesten der Kette «Beenden», an älteren «weiter in Auftrag …». Zustand als Punkt +
  Satz. Beenden fragt einmal nach.
- Die Linie **links**, aus `polyPath`, Haarlinie bis zur ersten Wiederholung (prozessbild §8.1a);
  jede Wiederholung zeigt ihre eigene Schlaufe.
- `prozessbild.md` nachgezogen; Spiegel der Takte im Frontend getestet
  (`test_frontend_mirrors.py`).

#### 7 · Abschluss
- CLAUDE.md (Ist-Stand), Kopfstatus dieser Akte «gebaut», Rundenbericht in `docs/history/`.

### Kosten
Keine neuen Dienste: der Takt läuft schon, die Datenbank auch. Je Lauf ein paar Abfragen.

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
| | Wo wird eingestellt? | unten bei der Schlaufe, wie ein Dauerauftrag (Grundsatz 15) |
| | Fremder Kran? | wie jeder Artikel, nichts Besonderes (O2) |
| | Wie beenden? | «Ab heute beenden», endgültig wie ein Dauerauftrag; weiter mit einem neuen Auftrag (Grundsatz 18) |
| | Zahlung fest oder offen? | was vorher festgelegt ist, gilt; was offen blieb, wird jedes Mal festgelegt (O1) |
| | Wo setzt man die Schlaufe? | nur im Entwurf; jede Wiederholung ist eine 1:1-Kopie mit eigener Schlaufe, keine Vorlage (Grundsatz 17, O15) |
| | Bauplan wo? | hier in §8, keine eigene Datei |
