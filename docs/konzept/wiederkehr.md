# Projektakte «Wiederkehrende Aufträge»

> **Kopfstatus:** in Klärung · **nichts gebaut** · Lead: Claude · Entscheid: Clemens Fritsche ·
> seit 06.11.2026 · zuletzt 08.11.2026 (fünfte Runde)
> Bild (Ist-Stand 1:1, Schlaufe, Abo): https://claude.ai/artifact/Lk5AKy8G1CTWi68ZxA57uj
> Diese Akte ist die **eine** Quelle für Ziel, Grundsätze, Vorschläge und Entscheide. Das Bild
> zeigt, die Akte hält fest. Was hier nicht als entschieden steht, ist nicht entschieden.
> Ausgangspunkt im Kern: `PROCESS_CORE.md` §13 Punkt 6.

## 0 · Kurzfassung (zum Prüfen)

**So funktioniert es**
1. Ein ganz gewöhnlicher Auftrag wird angelegt und freigegeben. Er ist die **Vorlage**. Unter
   seinem Ziel steht ein Schalter «einmalig ↔ wiederholt sich»; die Linie läuft vom Ziel zurück
   an den Anfang.
2. **Eingestellt wie ein Dauerauftrag:** wie oft, ab wann, bis wann (unbefristet · Datum ·
   Anzahl). Je Lager-Zeile: «gleiche Einzelinstanzen» oder «FIFO»; eine Zeile «Neu» erzeugt jedes
   Mal neu. Fällt der Tag auf den 29.–31., gilt in kürzeren Monaten der letzte Tag.
3. **Der Takt prüft alle 5 Minuten:** Ist eine Periode fällig und hat noch keinen Auftrag, stellt
   er dieselbe Frage wie der Knopf «Freigeben», dazu: wäre es eine Abweichung?
   - nichts fehlt → der Auftrag entsteht sofort (im Namen der Person, die die Schlaufe setzte),
   - fehlt gerade → er **wartet** und fragt wieder; die Zahl am Symbol nennt den Grund,
   - fehlt für immer → **geht nicht mehr**; nur «Beenden».
4. **Jede Wiederholung ist ein gewöhnlicher Auftrag.** Keine Periode geht verloren, je Periode
   höchstens einer, nacheinander. Aufträge von Hand gehen jederzeit und verschieben nichts.
5. **Zahlung:** übernimmt Partei, Eigentum und Positionen, die Anschrift ist die heutige.
   Fester Preis → gleich zugesagt, nur «Rechnung stellen» (mit «Prüfen und freigeben»).
   Offener Preis → beginnt bei der Offerte.
6. **Beenden** jederzeit, von jedem Auftrag der Schlaufe aus, endgültig. Was läuft, läuft fertig.
   Weiter geht es mit einem neuen Auftrag. Setzen und beenden darf jede Person mit ERP-Zugang.

**Was sich an Bestehendem ändert**
- **«Verkauft» wird ein regulärer Start** (keine Abweichung mehr). FIFO und Verbrauch nehmen
  weiter nur «Freigegeben».
- **«Automatisch angelegt wird nie etwas»** wird zu **«Nichts entsteht ohne Entscheid eines
  Menschen»**; die Schlaufe ist dieser Entscheid, im Voraus.
- **Die Zahlung kennt die Schlaufe** an einer Stelle: Die Offerte nennt die Wiederholung, die
  Zusage gilt weiter (PROCESS_CORE §13.6 wird angepasst).
- **Neu gespeichert** wird nur die Einstellung der Schlaufe (append-only) und die Wahl je Zeile.
  Fällig, nächster, wartet, Anzahl bisher: alles abgeleitet.

**Bewusst nicht:** Vorlauf (später), Fristen für den Kunden (mit dem Shop), Liefersperre bei
unbezahlt, Zähler wie Betriebsstunden, Wieder einschalten, Kopie als Entwurf.

**Folgen, die man kennen muss:** Nach langer Blockade kommen mehrere Perioden nacheinander. Eine
Schlaufe lässt nie still ein Stück weg. Ein fester Preis bleibt fest; eine Erhöhung heisst
beenden, neu anbieten, neue Schlaufe.

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
14. **Was die Wiederholung nimmt, sagt der Mensch je Zeile ausdrücklich**: «gleiche
    Einzelinstanzen» oder «FIFO». Es steht **unten bei der Schlaufe**, zusammen mit Takt und Ende
    (07.11.2026, → V3).
15. **Eingestellt wird wie ein Dauerauftrag im E-Banking**: wiederholen (wöchentlich ·
    monatlich · vierteljährlich · halbjährlich · jährlich), erste Ausführung, Ende
    (unbefristet · am Datum · nach Anzahl). Nichts Eigenes erfinden (07.11.2026, → O10).
16. **Setzen, ändern und beenden darf jede Person mit ERP-Zugang** (07.11.2026, O11).
17. **Die Schlaufe gehört allen Aufträgen, die aus ihr entstehen.** Jeder zeigt dieselbe
    Einstellung, und beendet werden kann sie von jedem aus.
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
    Vorbelegung** (wie das Eigentum am Beleg): «gleiche Einzelinstanzen» (Service, Abo, fremder Kran)
    oder «FIFO» (Lieferung). Eine Zeile «Neu» erzeugt jedes Mal neu. Mehr Möglichkeiten
    gibt es nicht. Ausdrücklich, weil es sich nicht ableiten lässt (§4) und weil eine falsche
    Annahme teuer wäre: wer z. B. zwölf Kartuschen von Hand wählt und «gleiche Einzelinstanzen» bekäme,
    würde nächsten Monat dieselben, schon verkauften Kartuschen noch einmal liefern.
  - **FIFO nimmt weiter nur `Freigegeben`**, «gleiche Einzelinstanzen» darf auch `Verkauft` (V1).
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
- **O6 · Stück weg** (verschrottet, Artikel ersetzt) – entschieden 07.11.2026: dieselbe Regel
  wie O3, aber der Grund vergeht nicht. Die Schlaufe steht rot auf «geht nicht mehr», die Zahl am
  Symbol ist rot, und es gibt **nur «Beenden»**, wie bei einem Dauerauftrag (Grundsatz 18). Von
  selbst endet nichts. Bild: Teil 3, Zustand «geht nicht mehr».
- **Beenden**: «Ab heute beenden» in der Einstellung der Schlaufe, von jedem ihrer Aufträge aus.
  Es wird eine Zeile «ab heute: beendet» (append-only, endgültig). Was schon entstanden ist,
  läuft normal zu Ende. Die Linie verschwindet; war sie schon kräftig (es gab Wiederholungen),
  bleibt sie nach prozessbild §8.1a kräftig stehen, und der Schalter sagt «einmalig».
  **Verbaut man sich damit etwas?** Nein: Ein neuer Auftrag kann jederzeit dieselben Instanzen
  nehmen und eine eigene Schlaufe tragen. Es fehlt nur die Bequemlichkeit einer Kopie, keine
  Möglichkeit. Das ist auch der Weg, wenn sich der Ablauf ändert (F12).

### Weitere Punkte, die noch festzulegen sind

- **O7 · Wer handelt?** Jedes Schreiben braucht einen Handelnden (`core/actor.act`). Vorschlag:
  das System, im Namen der Person, die die Wiederkehr gesetzt hat (wie die KI im Namen der
  Person). So steht im Log, wessen Entscheid es war.
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

## 6a · Sackgassen-Prüfung (07.11.2026)

Gefragt: Gibt es einen Zustand, aus dem man nicht mehr herauskommt?

| Fall | Was passiert | Ausweg | Sackgasse? |
|---|---|---|---|
| Stück steckt in einem Auftrag, der nie fertig wird | Wiederholung wartet, «zu tun» nennt den Auftrag | den Auftrag fertig machen oder abbrechen (Abweichung mit gekappter Rückführung) | nein |
| Stück verschrottet, Artikel ersetzt | «geht nicht mehr» | Beenden, dann ein neuer Auftrag | nein |
| Service-Vertrag über 3 Krane, einer verschrottet | die ganze Wiederholung geht nicht mehr (ein Auftrag läuft nicht halb) | beenden, neuer Auftrag mit den 2 übrigen | nein. Die Schlaufe lässt nie still ein Stück weg |
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
