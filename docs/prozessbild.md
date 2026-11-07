# Das Prozessbild – Zeichenregeln

> **Verbindlich** für `services/flow.py` (der Graph) und `components/erp/process-flow.tsx`
> · `process-columns.tsx` (Layout und Linien). Ausgelagert aus `PROCESS_CORE.md` §8; die
> Abschnittsnummern (§8.1a′ … §8.1c, §10.2) sind geblieben, damit Verweise im Code
> weiter treffen. Was ein Stück im Prozess darf, steht in `PROCESS_CORE.md`; hier steht,
> wie es gezeichnet wird. Ein §-Verweis ohne Datei meint `PROCESS_CORE.md`, ausser er
> nennt einen Abschnitt dieser Datei (§8.1a…§8.1c, §10.2).

---

### 8.1a′ Das Bild ist ein GRAPH, und der Server liefert ihn

Die Oberfläche **layoutet und zeichnet**. Sie leitet nichts ab. Vier Ebenen, strikt
getrennt — mehr Begriffe gibt es nicht:

| Ebene | | |
|---|---|---|
| **1 Graph** | `services/flow.build` | **Knoten**: `start` · `module` · `end` · `fork` · `join`. **Kanten**: Verbindung zwischen genau zwei Knoten. |
| **2 Position** | `FlowEdge.units` | Wo ein Stück steht — **immer eine Kante**, nie ein Knoten, nie ein Zwischenraum. |
| **3 Kantenzustand** | `FlowEdge.walked` | Kräftig, wenn laut **Log** mindestens **eine Einzelinstanz diese Kante genommen** hat. Sonst Haarlinie. Kein dritter Wert, nie gesetzt. |
| **4 Layout/Pfade** | `process-flow.polyPath` | **Ein** Generator zeichnet **jede** Linie – Achse, Ausscherung, Rückführung. |

**Abzweige- und Rückführpunkt sind eigene Knoten.** Fachlich bleibt es *ein*
Zustandspunkt «vor Modul X» (§12.4, `current_step_id`); im Bild ist es seine Darstellung
in der Zeit — davor und danach. Erst dadurch lässt sich sagen, wer **geblieben** ist (auf
dem Bypass `fork → join`) und wer **zurückkam** (auf `join → Modul`). Als ein Knoten
standen beide an derselben Stelle, und die Zeichnung verschwieg die Runde.

**Der Graph wird aus dem Ereignis-Log abgeleitet, nicht aus dem Zustand.** Ein
`handover`-Eintrag verschwindet nie: eine Abzweigung, die einmal passiert ist, bleibt im
Bild, auch wenn das Stück längst zurück und weitergezogen ist. Alle Zähler sind
Zeilenzahlen im Log und können nur wachsen — daraus folgt «eine einmal kräftige Kante
wird nie wieder schwach» **von selbst**, statt bewacht zu werden.

**Der Kantenzustand gehört der KANTE, nicht dem Punkt.** Der Hauptstrang ist keine
durchgehende Linie, sondern eine Folge von Kanten, und jede beantwortet ihre eigene
Frage. «Hier ist Material angekommen» gilt für die Kante **zum** Abzweigepunkt; ob danach
noch jemand geradeaus weiterging, ist eine andere. Nimmt eine Abweichung **alle** Stücke
mit, hat den geraden Weg niemand genommen — er ist dünn, obwohl unmittelbar darüber sehr
wohl Material stand. Gerechnet wird das als **Bilanz entlang der Achse**: sie beginnt mit
dem, was am Punkt angekommen ist, jeder Abzweigepunkt zieht seine Ausgescherten ab, jeder
Rückführpunkt addiert seine Rückkehrer (`flow._branches`). Kein `if` je Kantenart, kein
Sonderfall «Abweichung nimmt alles» — die Zahl ist grösser als null oder eben nicht.
Gezählt werden dafür **Einzelinstanzen**, nicht Log-Zeilen: ein Stück kann dieselbe
Stelle mehrfach verlassen (Abweichung der Abweichung), und die Bilanz ginge sonst nicht
auf.

**Wer wartet, hat nichts verlassen.** Die Bilanz beginnt mit «wer ist an diesem Punkt
angekommen» — und dafür muss der Log zwei Dinge auseinanderhalten, die er gleich
aufschreibt: *Modul passiert* und *Auftrag an diesem Modul verlassen* sind beide ein
`step`-Eintrag. Unterschieden werden sie allein durch die **Zugehörigkeit**: verlassen
heisst geschlossene Zeile, warten heisst offene (`flow._exit_points`). Ohne diese
Bedingung galt jedes wartende Stück als ausgetreten und wurde abgezogen; warteten alle,
stand die Bilanz auf null und die Achse hinter dem Abzweigepunkt war eine Haarlinie,
obwohl die Stücke sie gegangen sind und dort stehen.

**Und die Linienstärke wird gegen den LOG geprüft, nicht nur gegen die Positionen**
(`flow._verify_walked`): *wer ein Modul passiert hat, ist die Kante davor gegangen* —
ausgenommen, wer erst dort eingetreten ist (`_enter_at_step`; er hat sie nie gesehen).
Die Invariante «wo etwas steht, ist etwas gewesen» trägt nur so lange, wie noch jemand
dortsteht; in einem **abgeschlossenen** Auftrag ist jede Zugehörigkeit geschlossen, keine
Achsenkante hat mehr Mitglieder, und eine falsche Haarlinie fiele durch jedes Netz.
Zwei Herleitungen derselben Aussage: die Bilanz **muss** rechnen (ein Bypass ist eine
Differenz), diese hier kann nur zählen — weichen sie ab, steht es da, statt still
gezeichnet zu werden.

**Eine Kante über die Auftragsgrenze** (`out`/`back`) nennt den Nachbarn als
`order:<Objektnummer>`. Das Frontend zeichnet sie, wenn **beide Enden im Bild stehen** –
darum muss keine Seite wissen, welche Spalten gerade sichtbar sind, und beide Richtungen
stammen aus dem Log dessen, bei dem sie passiert sind.

**Die Nachbarn kommen aus demselben Graph** (`Graph.neighbours` → `OrderResponse.
deviations`). Es gab die Frage zweimal: die Spalten daneben aus einer eigenen Log-Abfrage,
die Abzweigungen aus den Kanten. Zwei Ableitungen derselben Sache laufen auseinander, und
man sieht es erst am Bildschirm — als Abzweigepunkt **ohne** seinen Nachbarn: kein Block,
keine Linie, nur der Punkt. Ein Nachbar existiert jetzt genau dann, wenn es seine Kante
gibt. *Der übergeordnete Auftrag bleibt beim Log: im eigenen Graph gibt es ihn nicht, die
Übernahme steht in **seinem**.*

**Eine Position hat genau eine Adresse: die Kante.** Der Zähler an der Pille und die Liste
beim Aufklappen fragen **dieselbe** (`FlowEdge.members` → `flow.units_on`,
`GET …/units?edge=…`). Zwei Fragen an dieselbe Sache laufen auseinander, sobald die Sache
feiner wird – an einem Punkt mit Teilung stünde sonst «1 Stk» und im Aufklappen zwei
Nummern.

**Invarianten** (`tests/test_flow_graph.py`, gegen echtes PostgreSQL): jede Einzelinstanz
hat genau eine Position · die Summe der Positionen ist die Stückzahl des Auftrags · Zähler
und Aufklappen fragen dieselbe Position · jede Kante hat genau einen Zustand · eine
kräftige Kante bleibt kräftig · jeder Pfad stammt aus dem einen Generator · keine zwei
Kanten teilen sich einen Kanal · keine Kante überlagert einen Knoten-Container. Verletzt
heisst **sichtbar kaputt**: `FlowGraph.problems` wird als rote Notiz gerendert, statt eine
falsche Zeichnung anzubieten.

### 8.1a″ Wie eine Linie geführt wird — Ports, Kanäle, ein Layer

Die drei Regeln sind aus etablierten Diagramm-Werkzeugen übernommen, nicht erfunden. Sie
sind der Grund, warum «mehrere Abweichungen» kein neuer Fall mehr ist.

**1 · Ports statt Flächen** (React Flow nennt sie *Handles*, bpmn-js *docking points*,
Miro schlicht Ankerpunkte). Eine Linie beginnt und endet an einem **Punkt auf dem Rand**
eines Knotens (`process-flow.port`), nie irgendwo auf ihm und nie dahinter. Damit kennt
sie seine Fläche gar nicht mehr und kann nicht in ihn hineinragen – bei jeder Modulhöhe,
jedem Umbruch, jedem Auf- und Zuklappen, jeder Rahmenbreite. Eine **Querverbindung dockt
an der Spalte an**, nicht an einem Knoten darin: oben an deren erster, unten an deren
letzter Zeile. Am `end`-Objekt anzudocken war der Grund, warum die Rückführung senkrecht
durch alles lief, was darunter noch stand.

**2 · Kanäle statt einer Gasse** (ELK nennt sie *tracks* im *layer pipe*). Die Spurlücke
ist ein **Bündel**: jede Abzweigung bekommt ihre eigene senkrechte Spur. Zwei Spannen, die
sich überschneiden, bekommen verschiedene Spuren – das ist eine Färbung des
Intervall-Graphen, und für Intervalle ist **gierig nach Anfang sortiert optimal**
(`process-flow.channels`). Gerechnet wird auf **Zeilennummern**, nicht auf gemessenen
Pixeln: die Zuteilung steht fest, bevor irgendetwas gemessen ist, und die Lücke richtet
sich danach (`gutterFor`) statt umgekehrt. Deterministisch, nicht «meistens passt es».
Und Nachbarn, deren Spannen sich überschneiden, stehen **untereinander** in einem Band:
im selben Rasterfeld lägen zwei Rasterelemente sonst aufeinander.

**3 · Ein Linien-Layer, der nichts beschneidet.** Ein einziges SVG über der ganzen
Prozessfläche, `overflow: visible`, gehört keiner Spalte. Platz wird im **Layout** gemacht
(`paddingTop`/`paddingBottom` des Rasters), nicht mit einem Versatz an der Linie und nicht
mit z-index. Ein Zug, der einen Pixel über die gemessene Rahmenhöhe hinausliefe, fehlte
sonst still – und still fehlend ist genau das, was ein Prozessbild nicht darf.

**Der Zug beginnt IM Punkt.** Eine Ausscherung startet **auf** dem Abzweigepunkt und
knickt `BEND` daneben; weil ein **Endstück ganz im Bogen aufgehen darf** (die Halbierung
in `polyPath` gibt es nur zwischen zwei benachbarten Ecken), ist der Punkt zugleich der
Anfang des Bogens – kein gerades Endchen davor, das die Hauptlinie überlagert.

**Die Krümmung ist die Richtung.** Der Fluss läuft von oben nach unten, und das Stück,
mit dem eine Querlinie die Achse berührt, wird **immer stromabwärts durchlaufen**:

| | | |
|---|---|---|
| **hinaus** | der Punkt ist der **Anfang** | ab ihm hinunter, dann weg → die Kurve **schert aus** |
| **herein** | der Punkt ist das **Ende** | über ihm herein, dann hinunter → die Kurve **mündet ein** |

Damit sind Zuführung und Rückführung **allein an der Krümmung** zu unterscheiden – ohne
Farbe, ohne Pfeil, ohne Beschriftung; im Abweichungsauftrag spiegelverkehrt und nach
derselben Regel. Nach der **Lage des Ziels** zu entscheiden liegt nahe (die Linie ginge
dann «zur richtigen Seite hinaus»), kehrt die Aussage aber um: beide wären gleich
gekrümmt, und der Rückführpunkt sähe aus wie ein Abzweigepunkt.

**Der senkrechte Takt ist eine Ableitung des Radius** (`process-flow.FLOW_GAP` =
`2·BEND`), und er gilt im Raster **wie** in der Spalte. Zwischen einem Abzweigepunkt und
*seinem* Rückführpunkt liegen **zwei Waagrechte** — hinaus bei `fork + BEND`, herein bei
`join − BEND`. Übrig bleibt `FLOW_GAP + POINT − 2·BEND`, und genau das muss so viel sein,
dass zwei Linien als zwei zu lesen sind:

```
FLOW_GAP + POINT − 2·BEND  =  POINT      ⟹  FLOW_GAP = 2 · BEND
```

Ein kleinerer Takt ist rechnerisch überschneidungsfrei, im Bild aber eine einzige Linie –
sichtbar in der schmalen Nachbarspalte, wo nichts die beiden Punkte auseinanderzieht.
Darum gilt derselbe Takt im Raster und in der Spalte.

**Die Querverbindung ist EINE Waagrechte.** Der Nachbar trägt oben und unten denselben
Streifen Luft (`NEIGHBOUR_PAD` = `LEAD + BEND + 8`), und der **Rückführpunkt sitzt am
Ende seiner Zeile** – dort, wo der Nachbar aufhört. Damit liegen Ein- und Auslauf auf
einer Höhe und der Versatz in der Rückführung fällt weg (`polyPath.straighten` begradigt
den Rest). *Nicht überall möglich:* der **übergeordnete** Auftrag steht über alle Zeilen
gespannt, seine Punkte liegen dort, wo sein eigener Prozess sie hinlegt – zwei
unabhängige Abläufe lassen sich nicht auf eine Zeile ausrichten, ohne einen davon zu
verbiegen. Dort bleibt der Weg über den Kanal.

### 8.1a‴ Kreuzungsfreiheit — sie entsteht im Graph, nicht beim Zeichnen

Das Bild ist ein **Raupengraph**: eine Achse mit Anhängseln. Ein solcher Graph ist genau
dann kreuzungsfrei zeichenbar, wenn die Ansatz-**Intervalle** der Anhängsel einander
nicht überschneiden. Und weil ein Stück immer an den Punkt zurückkehrt, an dem es
ausgeschert ist (§12.4), ist jedes Intervall das eines **einzelnen** Zustandspunkts.

Daraus folgt die eine Regel: **je Nachbar ein eigenes Paar `fork`/`join`**, hintereinander
auf der Achse —

```
… → fork₁ → join₁ → fork₂ → join₂ → [ Modul ]
      └──►A──┘         └──►B──┘
```

— statt eines gemeinsamen Paares für alle. Mit **einem** Rückführpunkt liegt er unter dem
letzten Nachbarn, und der Rückweg des ersten muss an allen folgenden vorbei, quer durch
deren Hinwege: das war das Bild, das bei zwei Abweichungen «zu wirr» wurde. Mit eigenen
Paaren sind die Intervalle **disjunkt**, jeder Nachbar steht in den Zeilen seines eigenen
Punktes, jede Verbindung ist eine **kurze Waagrechte** – und eine Kreuzung ist damit nicht
vermieden, sondern **unmöglich**. Das skaliert linear: drei, vier, fünf Abweichungen sind
drei, vier, fünf Paare; geschachtelte sind gar kein Fall, weil ein Enkel im Bild des
Kindes steht, nicht in dem des Auftrags.

Die **Reihenfolge** ist chronologisch (aufsteigende Objektnummer): gleiche Daten, gleiches
Bild. Wer geblieben ist, steht auf dem Bypass der **ersten noch offenen** Abzweigung –
einer, nicht mehreren: eine Position ist eine Kante.

Invariante: `tests/test_flow_graph.py: test_branches_at_one_point_get_their_own_pair_and_never_overlap`
prüft die paarweise Disjunktheit am echten Knotenverlauf.

### 8.1a Das Liniensystem — zwei Stärken, sonst nichts

Eine Prozesslinie trägt genau **eine** Aussage, und die hat zwei Werte:

| | |
|---|---|
| **gegangen** | kräftig — **mindestens eine Einzelinstanz hat genau diese Kante genommen** |
| **ausstehend** | Haarlinie — hier ist noch keine gegangen |

Keine dritte Farbe, kein zweiter Linientyp, keine Strichmuster. Eine **Ausscherung** in
einen Nebenauftrag ist keine andere Art Linie, sondern derselbe Strang, der abzweigt —
sie folgt darum derselben Regel. Ob ein Stück zurückkehrt, sagt **ob es die Linie gibt**:
eine gekappte Ausleihe hat keinen Rückweg, und das Fehlen ist die Aussage.

**Die Linie sagt die Vergangenheit, die Pille die Gegenwart.** Das ist die Arbeitsteilung
zwischen beiden, und sie ist keine Konvention, sondern folgt aus ihren Quellen: ``walked``
kommt aus dem Log (monoton, verschwindet nie), ``units[].status`` ist der **heutige**
Zustand des Stücks. Eine Abzweigung bleibt darum für immer im Bild, aber das Wort daneben
wechselt: solange das Stück in einem anderen Prozess steht, heisst es «In Abweichung»;
danach «Abgegeben» (gekappt) bzw. es verschwindet (zurückgekehrt — dann steht es wieder
auf der Achse). Eine Zustandsanzeige in der Gegenwartsform, die Vergangenes behauptet,
ist ein Fehler, auch wenn sie einmal richtig war.

**«Gegenwart» heisst: die Gegenwart DIESES Auftrags — und die endet mit ihm.** Das ist die
Präzisierung, ohne die der Satz oben in sein Gegenteil kippt. Eine Kante der **Achse**
(`at is None` bei einer geschlossenen Zeile) sagt «hier hat der Auftrag das Stück
abgegeben»; was ein **anderer** Auftrag danach damit tat, ist nicht seine Geschichte.
Die Pille liest dort darum den Status aus dem **Log** — den letzten `status_after`, den
dieser Auftrag selbst geschrieben hat (`flow._left_with`). Auf einer **Ausscherung**
(`at` gesetzt) gilt weiterhin der heutige Zustand: dort IST der Verbleib die Aussage —
«In Abweichung» ↔ «Abgegeben» ist genau die Frage, ob das Stück noch woanders steht.

Vier Fälle, eine Tabelle, keine Sonderregel:

| Zeile | `at` | Pille |
|---|---|---|
| offen (Stück steht hier) | – | heutiger Status |
| geschlossen, **Achse** | `NULL` | Status aus dem Log — eingefroren |
| geschlossen, **Ausscherung** | gesetzt | heutiger Status |
| offen, Ausscherung | gesetzt | heutiger Status |

Ohne die zweite Zeile zeigte ein längst abgeschlossener Auftrag Ereignisse, die nie zu ihm
gehörten: verschrottet ein Folgeauftrag eines seiner Stücke, stand plötzlich «eines im
Prozess, eines verschrottet» in einem Bild, in dem nichts ausgesondert wurde. Der Fehler
sieht aus, als käme er aus dem Nichts — er kommt daraus, dass eine Ansicht der
Vergangenheit eine Grösse las, die sich weiterbewegt. Wächter:
`test_flow_graph.test_a_finished_order_does_not_retell_what_happened_elsewhere`.

**Herkunft und Verbleib sind Äste desselben Strangs** (§6). Über dem Start und unter dem
Ende steht, aus welchen Aufträgen die Einzelinstanzen kamen und wohin sie gingen — nicht
als Textzeile neben dem Bild, sondern als **Verzweigung**: jeder Nachbar fällt auf eine
gemeinsame Waagrechte und läuft von dort in das Start- bzw. aus dem Ende-Objekt. Ein
**Bus**, kein Bündel: die Äste treffen sich auf einer Linie und teilen sich danach den
Weg, wie in jedem Stammbaum — das ist die Zusammenführung selbst und darum keine
Überlagerung im Sinne von §8.1a″. Möglich ist es nur, weil die Zeile **nicht umbricht**
(sonst fiele ein Ast der oberen Reihe durch die untere) und weil sie **gekappt** ist
(`JOURNEY_LIMIT`, der Rest gezählt).

**Gruppiert nach Nachbar, nicht je Stück** — eine Verzweigung mit Anzahl. Bei drei
Instanzen sieht man dasselbe wie bei 5000; wer die Nummern braucht, öffnet den Nachbarn,
und dort ist er die Mitte. **Zwei Ebenen, mehr nicht**: Rekursion im Bild wäre Tiefe ohne
Grenze. Die eine Herkunft, die nicht im Log steht, ist die **Entstehung** — ein
Erzeugungsauftrag hat keinen Vorgänger, seine Stücke entstehen bei der Freigabe; sie
stehen als eigener Ast «N× ⟨Artikel⟩». Beide zusammen decken **jedes** Stück ab (gegen
echtes PostgreSQL gemessen: Erzeugung · Lagerzugriff · zwei Vorgänger · Abweichung), und
genau darum ist der frühere Definitions-Container entfallen: er sagte ein zweites Mal,
was am Baum steht.

**Auch im Entwurf, und dort mit dem echten Ziel** (§5 + §8.1c): sobald die Auswahl einem
laufenden Auftrag ein Stück abnimmt, steht **er** in der linken Spur — mit dem
Abzweigepunkt, der entstünde, und der Rückführung, wenn zurückgeführt wird.

**Der Schalter steht auf der Linie, die er schaltet**: eine Pille unter dem Ende-Objekt,
also an der **letzten Zeile der Spalte** — genau dort dockt die Rückführungslinie an
(§8.1a″), sie geht von ihm ab. Er **bleibt**, wenn die Linie geht (sonst wäre die
Entscheidung einmalig statt änderbar), und trägt seinen Zustand im Wort («kehrt zurück» ↔
«bleibt hier»), nicht im Strichmuster.

Nicht **neben der Stückauswahl** (die Aussage stünde woanders als ihre Wirkung), nicht als
**Ersatz-Knoten mit eigener Linie** (zwei Rückweg-Linien für eine Entscheidung) und nicht
als **Klick auf die ganze Nachbarspalte** (eine Fläche ohne Aufforderung).


**Kräftig läuft die Linie bis in das Modul, das jetzt dran ist.** «Vor Modul X stehen»
(`current_step_id`) und «X ist dran» (`active_step_id`) sind **dieselbe** Tatsache – der
Server sagt beides über denselben Zustand, und zwischen dem Zustandspunkt und dem Modul
liegt kein Prozessobjekt. Der Abstand dazwischen ist Layout (die Zeile macht Platz für
einen Nebenauftrag), kein Weg. Ein aktives Modul, zu dem eine Haarlinie führt, sähe aus,
als wäre es nicht erreicht.

Geometrie, verbindlich:

- Start- und Ende-Objekte werden **senkrecht** betreten und verlassen.
- Ecken sind gerundet, und der Radius entsteht an **einer** Stelle (`polyPath`).
- Eine Ausscherung geht von der **Achse** ab, nicht vom Rand der Spur. Ein Zustandsknoten
  ist so breit wie seine Spur; nähme man seinen rechten Rand, begänne die Linie weit
  neben der Prozesslinie und hinge sichtbar an nichts.
- Querlinien laufen in der **Spurlücke**, nie unter einer Karte hindurch: eine gezeichnete
  Linie, die ein Knoten verdeckt, ist eine Linie, die es für den Betrachter nicht gibt.
  Wie das erzwungen wird, steht in §8.1a″ — Ports, Kanäle, ein Layer.
- **Seitwärts scrollen ist verboten**, ausser es ist ausdrücklich gewollt. Gescrollt wird
  senkrecht. Insbesondere darf **nichts Unsichtbares die Breite bestimmen**: ein absolut
  positioniertes Kind (etwa ein Hover-Tooltip) zählt zur *scrollable overflow area*
  seiner Vorfahren – auch bei `opacity: 0`.

### 8.1b Drei Spuren — und warum der Nebenauftrag in einer Zeile steht

Der Auftrag steht in der Mitte, der übergeordnete links, die Abweichungen rechts. Das
Ganze ist **ein** Raster mit **einer Zeile je Knoten der Mitte**; ein Nebenauftrag steht
in der Zeile seines Zustandspunkts.

Das ist keine Layout-Laune, sondern die Bedingung dafür, dass die Verbindung kurz bleibt:
die Zeile wächst auf die Höhe des Nebenauftrags, und damit wächst **die Hauptachse an
genau dieser Stelle mit**. Übrig bleibt das Bild, das die Sache ohnehin ist — Teilung,
zwei parallele Wege, Zusammenfluss. Stehen die Spalten unabhängig nebeneinander, liegt der
Start des Nebenauftrags irgendwo, und die Linie muss quer über das halbe Bild.

**Der übergeordnete Auftrag ist davon ausgenommen** (er spannt über alle Zeilen): er ist
vorher gelaufen und gehört nicht in den Takt dieser Achse. Eine eigene Zeile über dem Bild
schöbe den eigenen Prozess um seine ganze Höhe nach unten — und der ist das, was man sehen
will.

**Ein Nachbar ist sein Prozess — sonst nichts.** Keine Kopfkarte mit Art, Nummer, Status
und Stückzahl: dass es eine Abweichung ist, sagt die Abzweigung; wie weit sie ist, sagt
ihre Linie; wie viele Stücke unterwegs sind, sagen die Pillen an den Zustandspunkten.
Geblieben ist, was das Bild nicht kann — **hinführen**: ein Klick auf die Spalte öffnet den
Auftrag, der Rest steht im Hover. Dasselbe gilt für die Sperre eines Moduls: ein Symbol und
eine tote Eingabe, kein Absatz.

**Die Spurmasse stehen an genau einer Stelle** (`process-flow.LANE`). Entschieden wird
nach **effektiver CSS-Breite** des gemessenen Rahmens, nicht nach der Panel-Auflösung und
nicht per Media-Query: ein 13,3″-Notebook mit 2560 × 1600 Pixeln liefert dem Browser
1440 CSS-Pixel. Reicht die Breite nicht, stehen die Nachbarn untereinander — dieselben
Spalten, nur ohne Querlinien.

### 8.1c Der Entwurf ist dasselbe Bild, nur früher

Ein Entwurf, der einem laufenden Auftrag ein Stück abnimmt, zeigt ihn **schon vor der
Freigabe** in der linken Spur — mit dem Abzweigepunkt, der entstünde, und (falls
zurückgeführt wird) dem Rückführpunkt.

**Es gibt genau einen Rahmen** (`ProcessColumns`). Was in der Mitte steht, sagt der
Aufrufer: der laufende Auftrag seinen Server-Graph, der Entwurf seine Definition samt
Modul-Editor. Ein zweites Bauteil für «Bild mit Nachbarn» neben «Bild ohne Nachbarn» wäre
die zweite Darstellung derselben Sache — genau der Schnitt, den §8.1 verbietet. Ohne
Nachbarn ist das Bild schlicht die Spalte, und dann trägt sie ihr eigenes Mass.

**Die Vorschau ist keine zweite Wahrheit.** Sie kommt aus derselben Ableitung wie das
echte Bild — `flow.build(db, row, planned=[…])`, wobei `Planned` nur sagt, *an welchem
Zustandspunkt* eine Abzweigung *entstünde* und *ob* sie zurückführt. Nichts Geplantes ist
je **gegangen**: es gibt keine Log-Zeile dafür, also bleibt jede geplante Kante Haarlinie.
Geprüft wird die Gleichheit selbst — Vorschau vor der Freigabe gegen den echten Graph
danach, bis auf die Objektnummer und `walked` (`test_the_draft_shows_the_source_order_
exactly_as_it_will_be`, gegen echtes PostgreSQL).

**Der Entwurf hat eine Adresse, keine Objektnummer** (§6.1). Die Vorschau nennt ihn als
Ziel ihrer Abzweigung; dafür teilen sich beide Seiten `DRAFT_OBJECT_ID` (0 — der
Nummernkreis beginnt bei 100'000'001, eine Kollision ist unmöglich). Läuft der Wert
auseinander, fände die Linie ihr Ende nicht und verschwände **still**; ein Wächter
vergleicht die beiden Stellen.

**Woher der Zustandspunkt kommt:** aus der Absicht der Auswahl (`UnitPick.from_order`,
§12.6a) und der offenen Zeile des Quell-Auftrags (`OrderUnit.current_step_id`) — nicht aus
dem heutigen Aufenthaltsort. Sonst zeigte die Vorschau etwas anderes, als die Freigabe
täte.


### 10.2 Technologie-Entscheid: Fluss-Layout + SVG-Overlay auf gemessenen Ankern

**Geprüft, nicht vermutet.** Der Verdacht war richtig: der frühere SVG-Ansatz scheiterte
nicht an SVG. Zwei konkrete Ursachen, beide inzwischen belegt:

1. **Feste Spurbreiten** im Vorgängersystem. Daraus folgte, dass Ecken als
   CSS-Rahmenkanten gezeichnet wurden — und an der Naht zwischen einem gerasterten
   `div` und einem analytisch gezeichneten SVG-Pfad ist jede halbe Pixelverschiebung
   sichtbar.
2. **Ein Registrierungsfehler** in der ersten Fassung des neuen Rahmens: die Abmeldung
   eines Knotens lag in einem Effekt statt in der Callback-Ref. Im StrictMode räumte
   dessen doppelter Lauf jeden Knoten wieder aus der Messung — es wurde **keine einzige
   Linie** gezeichnet. Das sah aus wie «SVG funktioniert nicht».

Beides ist behoben und **im Browser nachgemessen** (Chromium, 320–1440 px, 3 wie 50
Module): Versatz Linie ↔ Knotenkante **0 px**, **0** absolut positionierte Knoten,
**0 px** waagrechter Überlauf.

**Geprüfte Alternativen:**

| Ansatz | Warum nicht |
|---|---|
| **CSS-Rahmen / Pseudo-Elemente am Knoten** | Kein eigener Layer nötig, aber: eine Linie, die von einer Spalte in eine andere läuft, ist so nicht darstellbar; die div/SVG-Rasterungsnaht kommt zurück; und **eine Bewegung entlang eines Pfades ist unmöglich** — das schliesst die geforderte Animation aus. |
| **Canvas** | Erst ab Tausenden von Kanten im Vorteil. Dafür: keine DOM-Knoten (kein Fokus, keine Tastaturbedienung, kein Hit-Testing geschenkt), keine Design-Tokens, und jede Animation muss von Hand durch `requestAnimationFrame` getrieben werden. Bei ≤ 50 Kanten ein Preis ohne Gegenwert. |
| **Graph-Bibliothek** (React Flow, D3) | 40–90 kB und ein eigenes Layout-Modell, das gegen «Knoten bestimmen ihre Position selbst» arbeitet. Wir haben keinen Graphen, sondern eine **Liste** (§10.1). Pan/Zoom/Minimap/Drag brauchen wir nicht. |

**Entscheid: SVG-Overlay auf gemessenen Ankern** — die einfachste Lösung, die alle drei
Anforderungen erfüllt.

**Wie es bei 50 Objekten und beim Resize stabil bleibt.** Es gibt keine gespeicherte
Position. Jeder Knoten meldet sich beim Rahmen an; ein `ResizeObserver` misst ihn und
den Rahmen, zusätzlich wird nach jedem Commit neu gemessen (ein Knoten kann wandern,
ohne seine Grösse zu ändern). Aus den Rechtecken entstehen die Pfade. Ob es 3 oder 50
Knoten sind, ändert nur die Länge einer Schleife; ob das Fenster 320 oder 1440 px breit
ist, ändert nur die gemessenen Zahlen. **Auch die Layout-Entscheidung (drei Spuren oder
eine) fällt an der gemessenen Breite** — nicht an einer Media-Query, sonst hätten Layout
und Linien zwei verschiedene Massstäbe.

**Wie eine spätere Animation andockt.** Ohne Umbau, weil die Linie bereits ein `<path>`
mit stabiler Identität ist:

| Gewünscht | Mittel |
|---|---|
| Fluss-Richtung andeuten | `stroke-dasharray` + animierter `stroke-dashoffset` |
| Aktiven Pfad hervorheben | `stroke`/`stroke-width` wechseln (CSS-Transition) |
| Stück wandert von Objekt zu Objekt | `path.getPointAtLength()` entlang derselben Kante — der Pfad ist schon da und schon vermessen |

Voraussetzung, die heute erfüllt ist: jede Kante hat einen **stabilen Schlüssel** über
Re-Renders hinweg. `prefers-reduced-motion` ist dann zu beachten.

