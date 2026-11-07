# Projektakte «Wiederkehrende Aufträge»

> **Kopfstatus:** in Klärung · **nichts gebaut** · Lead: Claude · Entscheid: Clemens Fritsche ·
> seit 06.11.2026 · zuletzt 07.11.2026
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
5. **Solange der vorige Auftrag offen ist, entsteht kein neuer.** Sobald er abgeschlossen ist,
   entsteht der neue sofort.
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
  - **Am Anfang steht, was die Wiederholung nimmt:** «dieses Stück» (Service, Abo, fremder
    Kran) oder «nach FIFO» bzw. «neu» wie in der Vorlage (Lieferung). Mehr Möglichkeiten gibt
    es nicht.
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

- **O1 · Die Zahlung in der Schlaufe.** Vorschlag, ein Satz für alle Fälle: **Was in der
  Vorlage zugesagt ist, gilt weiter; was offen war, bleibt offen.**
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
- **O2 · Ein fremdes Stück aufnehmen.** Ein Artikel mit Instanz anlegen geht (Grundsatz 8).
  Nur endet ein Erzeugungsauftrag ohne Zahlung bei uns im Bestand (§4). Vorschlag: Der erste
  Auftrag ist zugleich die Aufnahme und die erste Prüfung, also Zeile «Neu: Brückenkran
  Fremdfabrikat», Datenerfassung, Zahlung «geht an die Partei». Am Ziel steht der Kran auf
  «Verkauft», und die Schlaufe nimmt «dieses Stück». Ob die Zahlung einen Betrag 0 annimmt
  («erste Inspektion gratis»), ist noch zu prüfen.
- **O3 · Fällig, aber das Stück ist nicht frei.** Vorschlag:
  - Es entsteht nichts. Die Zahl «zu tun» am Symbol des Vorlage-Auftrags und im Feed nennt
    den Grund, z. B. «Wiederholung 14.11.2027 wartet: 100004501-1 ist im Prozess».
  - Der Takt prüft alle 5 Minuten und legt an, sobald das Stück frei ist.
  - Der Kalender verschiebt sich nicht.
  - Je Periode höchstens ein Auftrag. Beginnt die nächste Periode, bevor die wartende
    entstanden ist, fällt die wartende aus und steht als «ausgelassen» im Verlauf des Auftrags.
    Nachgeholt wird nie von selbst.
- **O4 · Vorlauf** – später. Idee: «fertig bis» statt «beginnt am», mit der Dauer aus dem Log
  gelernt (wie lange die letzten Wiederholungen liefen; beim ersten Mal die Vorlage selbst).
  Nichts eintippen.
- **O5 · Kunde sieht Fristen** – später, mit dem Shop.
- **O6 · Stück weg** (verschrottet, Artikel ersetzt). Vorschlag wie überall: «Nichtverfügbarkeit
  ist kein Zustand». Die Wiederkehr endet nicht von selbst. «Zu tun» sagt «100004501-1 ist
  verschrottet – Wiederkehr beenden?», und der Mensch beendet. Vorbild: der Halt der
  Datenerfassung (eine Auskunft, keine Sperre) und `release.pick_problem` (der Grund in einem
  Satz).

## 7 · Rückfragen und Antworten

| | Frage | Antwort |
|---|---|---|
| F1 | Was soll besser werden? | Wiederholtes gerät nicht in Vergessenheit, möglichst automatisch; eine Logik für alles |
| F2 | Welcher Fall zuerst? | keiner – eine Logik für alle |
| F3 | Anlegen oder anbieten? | anlegen (V2); wartend in «zu tun» (O3) |
| F4 | Kalender oder letzte Erledigung? | fester Kalendertag (wie ein Abo) |
| F5 | Takte ausser Zeit? | später; nur vorsehen |
| F6 | Voriger Auftrag noch offen? | nicht anlegen, solange offen; danach sofort |
| F7 | Jeder Kran ein Stück? | ja, auch ein fremder (Artikel + Instanz) |
| F8 | Service am verkauften Stück eine Abweichung? | nein → V1, Folgen §4 |
| F9 | Je Einsatz oder Pauschale? | dieselbe Logik, das Abo ist ein Stück (V6) |
| F10 | Vertrag als eigenes Ding? | die Wiederkehr ist der Vertrag; Abschluss später online |
| F11 | Wie endet sie? | jederzeit änderbar und beendbar, ohne Frist |
| F12 | Ablauf ändert sich? | beenden, neuer Auftrag, neue Wiederkehr |
| | Darstellung? | Schlaufe im Prozessbild wie die Rückführung, nicht als eigene Karte (V3) |
