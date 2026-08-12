# SYSTEM_INTENT — wofür dieses Modell da ist

> Geschrieben **vor** dem Konzeptreview und ohne hineinzuschauen, was ich dabei finden
> würde. Wenn die Absicht erst aus den Befunden entsteht, bestätigt sie sich selbst.

---

## 1 · Das Problem

Ein Maschinenbaubetrieb mit zehn Leuten weiss **alles** über seine Teile — verteilt auf
zehn Köpfe, ein paar Zettel und eine Tabelle. Das funktioniert, solange niemand fragt.

Gefragt wird, wenn etwas schiefgeht: ein Kunde reklamiert eine Welle, ein Auditor will
die Prüfprotokolle der letzten Lieferung sehen, jemand sucht die drei Stücke aus der
Charge, an denen der Fehler auffiel. Dann wird **rekonstruiert**. Rekonstruktion ist
Raten mit besserer Grammatik.

Der Zweck des Modells ist, dass diese Fragen **beantwortet** statt rekonstruiert werden.

## 2 · Was es beweisen können muss

Für **ein einzelnes physisches Stück**, zu **jedem Zeitpunkt**:

| | |
|---|---|
| **Was ist mit ihm geschehen** | jeder Zustandswechsel, in Reihenfolge, mit Zeitpunkt |
| **Wer verantwortet es** | je Wechsel eine Person |
| **Nach welcher Regel** | welcher Prozess galt, in welcher Fassung, welche Sollwerte |
| **Und dass das nicht nachträglich hingeschrieben wurde** | die Aufzeichnung ist unveränderlich |

Die vierte Zeile trägt die drei darüber. Ein Nachweis, den man ändern kann, ist eine
Behauptung mit Zeitstempel.

## 3 · Was es ohne das Modell wäre

Eine **Bestandsliste**. «Wir haben 600 Schrauben» beantwortet eine Frage zu einem
Zeitpunkt und keine einzige über die Vergangenheit. Genau daran ist das Vorgängersystem
gescheitert: es führte Mengen, und eine Menge hat keine Geschichte — sie hat nur einen
aktuellen Wert, und der lief immer wieder von der Wirklichkeit weg.

Der Bruch ist deshalb nicht «mehr Felder», sondern eine Umkehrung: **der Bestand ist
nicht die Wahrheit, sondern ihr Nebenprodukt.** Was wahr ist, steht im Ereignis-Log; alles
andere wird daraus gerechnet.

## 4 · Woran man merken würde, dass es gescheitert ist

Nicht an einer Fehlermeldung. An diesen vier Dingen:

1. **Jemand fragt einen Menschen statt das System.** Der erste Satz «da muss ich mal
   nachschauen» ist der Befund.
2. **Zwei Antworten auf dieselbe Frage.** Der Bestand sagt 597, die Kiste enthält 594,
   und beide Zahlen haben eine Quelle.
3. **Eine Zahl, die niemand herleiten kann.** Sobald irgendwo ein Wert steht, dessen
   Zustandekommen sich nicht zeigen lässt, ist er wertlos — auch wenn er stimmt.
4. **Die Erfassung wird umgangen.** Wenn die Wahrheit auf einem Zettel neben dem
   Bildschirm landet, weil sie im System nicht abbildbar war, ist das System ab da nicht
   mehr die Quelle. Das ist die gefährlichste Form, weil sie nach Betrieb aussieht.

---

## 5 · Wo meine Fassung von deiner abweicht

> Deine: *«Jedes physische Stück im Unternehmen hat eine lückenlose, unveränderliche
> Lebensgeschichte. Aufträge sind die Kapitel darin. Alles andere – Bestand, Auswertungen,
> Übersichten – ist nur eine Sicht auf diese Geschichte. Der Zweck ist Beweisbarkeit: Zu
> jedem Zeitpunkt für jedes Stück beantworten können, wo es ist, wo es war, was mit ihm
> geschah und wer es zu verantworten hat. ISO 9001 ist der äussere Treiber, aber der
> eigentliche Wert ist, dass niemand mehr raten muss.»*

Wir meinen dasselbe. Vier Stellen weichen ab, und jede ist ein Befund, kein Geschmack.

**a) «Wo es ist» steht in deiner Absicht — im Modell steht es nicht.**
Das System beantwortet **in welchem Auftrag** ein Stück ist und **vor welchem Modul** es
steht. Es gibt keinen Ort: keine Spalte, keine Tabelle, keinen Halter. Solange ein Stück
in einem Auftrag läuft, ist «vor Modul X» eine brauchbare Antwort. Sobald es frei ist —
und das ist der Normalzustand von Lagerbestand — ist die Antwort **leer**. Das ist die
grösste Lücke zwischen Absicht und Modell, und sie steht in keiner der bestehenden
Landkarten (`PROCESS_CORE` §13, `SYSTEM_LOGIC` §5) als offener Punkt.

**b) «Lückenlos» stimmt für Zustandswechsel, nicht für Zeit.**
Zwischen zwei Aufträgen passiert nichts, also steht nichts im Log. Ein Stück, das drei
Jahre im Regal liegt, hat für diese drei Jahre keinen Eintrag. Das ist richtig so — ein
Ereignis für «es lag weiter da» wäre Rauschen — aber es heisst: die Geschichte ist
lückenlos in dem, was **geschah**, nicht in dem, wo es **war**. Das ist wieder (a),
von der anderen Seite.

**c) «Aufträge sind die Kapitel» — aber ein Kapitel hat einen Titel.**
Ein Auftrag trägt heute drei Angaben: Objektnummer, den daraus gebildeten Namen
(«Auftrag 100000123») und den Endzustand. Kein Zweck, kein Anlass, kein Kunde, kein
Termin. Warum es dieses Kapitel gibt, lässt sich nur aus seinen Modulen erschliessen —
und bei zwei Aufträgen mit demselben Ablauf gar nicht.

**d) Ich würde einen zweiten Satz danebenstellen: das System ist auch das Arbeitsmittel.**
Deine Fassung ist rückwärtsgewandt, und das ist als Zweck richtig. Aber der Nachweis
entsteht **nur**, wenn die Erfassung im Arbeitsfluss liegt und nicht daneben. Ein
Nachweissystem, das zusätzliche Arbeit ist, wird gepflegt, solange jemand hinschaut. Die
Scan-Pflicht, die Stichprobe und «ein Vorgang ist eine Instanz» sind darum keine
Bequemlichkeit — sie sind die Bedingung dafür, dass Punkt 4.4 oben nicht eintritt.
Kurz: **Beweisbarkeit ist der Zweck, Bedienbarkeit ist ihre Voraussetzung.**

---

## 6 · Die tragenden Entscheidungen — und was jede unmöglich macht

Der interessante Teil ist die rechte Spalte. Eine Entscheidung, die nichts ausschliesst,
ist keine.

| # | Entscheidung | Macht unmöglich | Absicht? |
|---|---|---|---|
| **D1** | **Die Einzelinstanz ist das einzige Arbeitsobjekt.** Keine Mengen-Spalte, nirgends. | Bruchmengen, Schüttgut, Meterware, Flüssigkeiten. Eine 6-m-Stange ist «1 Stück»; ihre Länge hat im Modell keinen Platz. | **Ja** für Stückgut (Anhang PROCESS_CORE). **Nein** für Meterware — die Begründung nennt Mengendrift, nicht kontinuierliches Material. |
| **D2** | **Exklusivität:** ein Stück ist in genau **einem** Auftrag aktiv (partieller Unique-Index). | Zwei gleichzeitige Vorgänge am selben Stück. Damit auch: ein Kundenauftrag als **Klammer** über mehrere Fertigungsaufträge — Aufträge können sich nur schachteln, nicht überlappen. | **Ja** (G2), die Konsequenz für die Klammer ist nirgends benannt. |
| **D3** | **Ein Auftrag ist eine geordnete Liste, kein Graph.** | Parallele Module, Schleifen, Verzweigung nach Ergebnis. | **Ja** (`ProcessStep`-Docstring). Die Schleife «prüfen → nacharbeiten → prüfen» trägt der Abweichungsauftrag — das funktioniert nachweislich. |
| **D4** | **Der Ereignis-Log ist append-only, mit genau einer Schreibstelle.** | Eine Aufzeichnung zu ändern. Damit heute auch: eine **falsche** Aufzeichnung zu korrigieren, sobald das Stück weitergezogen ist. | Die Unveränderlichkeit ist Absicht; **die fehlende Korrektur ist es nicht** — der Docstring verspricht sie («eine Korrektur ist ein neuer Eintrag»), gebaut ist sie nicht. |
| **D5** | **Geschlossene Statusliste, vier Werte am Stück.** | «verbaut», «verkauft», «beim Kunden», «unterwegs». Ein Stück verlässt den Bestand nur, indem es **verschrottet** wird. | Der Katalog nennt `verbraucht` ausdrücklich als nicht angelegt. Entschieden wurde über ein **Wort** — die Folge (Montage und Verbrauch sind nicht abbildbar) ist nirgends festgehalten. |
| **D6** | **Neue Stücke entstehen ausschliesslich bei der Freigabe eines Erzeugungsauftrags**, der die Artikel-Vorlage mit Versionsstempel kopiert. | Wareneingang ohne Auftrag, Anfangsbestand, Inventurüberschuss. Alles davon braucht einen Artikel mit «Erzeugungsprozess» — und der Stempel behauptet dann einen Ablauf, den es nicht gab. | Der Zwang zum Anlass ist Absicht. Dass der Stempel dabei eine Falschaussage wird, ist nicht bedacht. |
| **D7** | **Ein terminales Modul ist ein Ausgang**; der Zielzustand folgt aus seiner Ausprägung. | Nichts — dies ist der bestvorbereitete Erweiterungspunkt des Modells. | **Ja.** Ein künftiges «verbaut»/«verkauft» ist hier ein Eintrag, kein Umbau. |
| **D8** | **Der Auftragsstatus ist abgeleitet** aus drei Zahlen (angekommen · unterwegs · verliehen). | «pausiert», «wartet auf Material», «geplant», «überfällig». Ein Auftrag, an dem seit sechs Wochen niemand war, ist ununterscheidbar von einem, der gerade läuft. | Die Ableitung ist Absicht und richtig. Dass damit **jede Zeitaussage** fehlt, ist eine Folge, keine Entscheidung. |
| **D9** | **Es wird nichts gespeichert, was sich ableiten lässt.** | Zweite Wahrheiten. Das ist die stärkste Regel im Haus, und sie hat die Fehlerklasse des Vorgängersystems strukturell beseitigt. | **Ja** — mit einer Nebenwirkung, die dieses Review zum Kern hat: derselbe Reflex hat auch drei Dinge weggeräumt, die sich **nicht** ableiten lassen und darum erfasst werden müssten (Ort · Zweck · Termin). |
| **D10** | **Definitionen rasten bei der Freigabe ein.** | Einen laufenden Auftrag umplanen. | **Ja** (A5). Der Ausweg ist der Abweichungsauftrag; er kann **einschieben**, aber nicht **ersetzen** — die Rückkehr geht an denselben Punkt. |

---

## 7 · Der Satz, auf den es hinausläuft

**Ein Stück ist keine Zahl im Lager, sondern ein Ding mit einer Geschichte; ein Auftrag
ist ein Kapitel darin; und was man nicht belegen kann, hat nicht stattgefunden.**

Alles Weitere in `PROCESS_CORE.md` und `SYSTEM_LOGIC.md` ist die Ausführung dieses
Satzes. Wo das Modell heute an seine Grenze stösst, stösst es an **eine** Stelle: es
kennt die Geschichte eines Stücks **durch die Zeit** — und keine einzige Beziehung
**zu einem anderen Stück**. Das ist Gegenstand von `CONCEPT_REVIEW.md`.
