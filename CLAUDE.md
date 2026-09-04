# INEXXIO – Enterprise Central System

> ## ⚠ BASIS-NEUAUFBAU (August 2026) – ZUERST LESEN
>
> **Die Prozesslogik ist ersatzlos entfernt.** Alles weiter unten in dieser Datei, das
> Auftrag · Prozessschritt · Reservierung · Anteil · Material-Journal · Unterdeckung ·
> Bereitstellung · Nachschub · Abweichung · Verkauf/Shop beschreibt, ist **Historie** –
> es beschreibt ein System, das es so nicht mehr gibt. Nicht als Vorlage verwenden.
>
> **Das gültige Datenmodell ist:**
> ```
> Artikel        reiner Ordner + Spezifikation + Erfassungsmaske. Keine Menge, kein Bestand.
>   └─ Instanz   reine Gruppe (kind = einzeln|batch), eigene Objektnummer.
>                KEINE Mengen-Spalte – die Menge IST die Anzahl der Einzelinstanzen.
>        └─ Einzelinstanz   das EINZIGE Arbeitsobjekt. Menge immer exakt 1 (nicht
>                           gespeichert). Eigener Status. Nummer = <Instanznr>-<Suffix>,
>                           kumulierend, NICHT aus object_id_seq.
> ```
> **Einzelinstanz-Regel:** im Prozess wird ausschliesslich mit Einzelinstanzen gearbeitet –
> nie mit der Instanz, nie mit dem Artikel. Jede Ansicht auf höherer Ebene (Instanz,
> Artikel, Bestand) ist nur Filterung/Summierung, nie eine eigene Datenquelle.
>
> **Den zentralen Schalter gibt es nicht mehr** (Aufräumrunde August 2026). Während des
> Neuaufbaus stand in `core/features.py` eine Liste aktiver Bereiche, und die Module der
> abgeschalteten (`sales`, `documents`, `ai`) lagen unerreichbar daneben im Repo. Sie sind
> **entfernt**, nicht abgeschaltet – und damit schaltet der Schalter nichts mehr: er ist
> mitgegangen. Was weg ist, wo die letzte lauffähige Fassung liegt und welche fachliche
> Entscheidung darin steckt, steht in **`docs/attic.md`**; ein Wiederaufbau beginnt bei
> der Modellfrage dort, nicht bei der alten Datei.
>
> **Das Datenerfassungsmodul ist fertig** (PROCESS_CORE §4.4/§4.5/§9.3) – und die drei
> Regeln, die dabei entstanden sind, stehen im **Prozess-Framework**, nicht im Modul;
> jedes künftige erbt sie ohne eine eigene Zeile. **(1) Ein Vorgang ist EINE Instanz**:
> der Scan verifiziert das physische Ding, und das ist die Instanz – eine Einzelinstanz
> zieht bewusst keine Objektnummer, es kann für sie gar kein Etikett geben. Charge = ein
> Scan, Einzelserialisierung = n Scans, **ohne** eine einzige Abfrage nach der
> Serialisierung; `confirm_step` ist darum ein **Teil**-Abschluss. Ohne Verifikation ist
> die Eingabe **nicht möglich** (400 an der Ausführungsstelle, nicht nur ausgegraut); die
> Tastatur bleibt die Alternative und wird als `verification='manual'` mitgeloggt – ohne
> den Vermerk wäre sie eine stille Umgehung. **(2) «Nicht bestanden» rückt nicht vor und
> legt nichts an**: die Stücke bleiben stehen, das System **bietet** einen ganz
> gewöhnlichen Auftrag mit vorgewählten Stücken an. Angehalten wird die **ganze Instanz**
> samt ungeprüftem Rest – eine durchgefallene Stichprobe ist nicht mehr repräsentativ
> (ISO 2859-1). Die 100 %-Kontrolle ist **kein neuer Mechanismus**, nur eine andere
> Vorbelegung, und ihr Umfang ist der Rest **dieser Instanz an diesem Modul**.
> **(3) Die Stichprobe** ist eine Angabe in drei Formen (alle · Anzahl · Prozent,
> `domain/sampling.py`) und gilt **je Instanz** – ein Los ist die Instanz, «10 % von drei
> Chargen» heisst 10 % aus jeder. Gezogen wird bei der **Ankunft** (vorher steht die Menge
> nicht fest), **zufällig** (eine Rechenregel wäre vorhersagbar) und **eingefroren im Log**
> (`sample`-Ereignis); der ungezogene Rest läuft ohne Erfassung durch – **sichtbar**, nicht
> stillschweigend. Wächter: `tests/test_capture_module.py`.
>
> **Das zweite Modul ist «Aussondern»** (PROCESS_CORE §9.4) – und wie beim ersten stehen
> die Regeln, die dabei entstanden, im **Framework**: **Verschrotten** (`Verschrottet`,
> rot, endgültig) und **Sperren** (`Gesperrt`, gelb, physisch noch da) tun dasselbe – das
> Stück verlässt den Auftrag –, also ist der Unterschied ein **Parameter**, kein zweites
> Modul; den Zustand leitet das Modul ab (`status_after_for`), es gibt kein
> Status-Dropdown. **«Gibt es einen Weg zurück?» ist eine Eigenschaft des Status**
> (`Status.selectable`) und keine Farbfrage: Farbe, Freigabe-Prüfung und Auswahl-Liste
> folgen daraus, und daraus fällt das Zurückholen von selbst heraus – ein gesperrtes Stück
> nimmt ein **ganz gewöhnlicher Auftrag** auf, **das Greifen IST das Aufheben** (kein
> «entsperren»-Endpunkt). **Ein terminales Modul ist ein AUSGANG** (`Module.terminal`):
> hinter ihm steht kein Modul (Freigabe-Fehler mit Grund), die Kette endet dort, und es
> passiert das Ende-Objekt nicht – **womit auch eine geplante Rückführung endet, ohne eine
> Zeile Wartelogik**, denn gezählt wird über die **offene** Zugehörigkeit; die Absicht
> (`return_to_order_id`) bleibt als Historie stehen. Der **Auftragsstatus braucht keinen
> vierten Wert**: wer aussondert, hat sein Ziel erreicht (`Abgeschlossen`), wem die Stücke
> dadurch endgültig fehlen, dessen Ziel ist unerreichbar (`Abgebrochen`) – beides fällt aus
> `_derive` heraus. **Teilmengen gibt es hier nicht** (was ankommt, wird ausgesondert), der
> **Grund ist Pflicht beim Sperren** (ein gewöhnlicher Erfassungspunkt, den das *Modul*
> deklariert – wäre er konfigurierbar, könnte man ihn wegkonfigurieren) und beim
> Verschrotten ist der **Scan** die Bestätigung. Die Kettenregel wohnt jetzt in
> `domain/chain.py` und gilt an **beiden** Definitionsorten – vorher nur beim Auftrag, und
> eine Artikel-Vorlage mit gebrochener Kette wäre erst nach dem Einfrieren aufgefallen.
> Wächter: `tests/test_disposal_module.py`.
>
> **Das dritte Modul ist «Verbrauch» – der Zwilling des Aussonderns** (`domain/modules.
> Verbrauch`): dasselbe tun (das Stück verlässt den Kreislauf), nur mit anderem Ergebnis –
> `Verschrottet` heisst «gibt es nicht mehr», **`Verbaut`** heisst «steckt jetzt in etwas
> anderem». **Der Unterschied zum Aussondern ist die Reichweite**, und daraus folgt die
> einzige neue Regel: `Module.terminal` beantwortet **nur noch** «verlassen ALLE
> ankommenden Stücke den Auftrag hier?» – beim Verbrauch **nein**, also ist er kein
> Ausgang und die Kettenregel bleibt unangetastet (hinter ihm darf die Endprüfung stehen).
> **Gefragt wird nach dem ARTIKEL, nicht nach der Definitionszeile**, und das ist keine
> Bequemlichkeit: dasselbe Modul wird in der **Artikel-Vorlage** definiert (der
> Erzeugungsprozess IST der Montageplan), und dort gibt es noch keine Zeilen – eine
> Vorlage kann «Rahmen, Motor» meinen, aber nicht «Zeile 2». Die eine Stelle, an der diese
> Körnung zu grob ist (derselbe Artikel erzeugt UND verbraucht), wird bei der Freigabe
> **abgewiesen** statt still falsch gerechnet.
> **`_assert_single_new` heisst jetzt «HÖCHSTENS eine Neu-Zeile»** – die alte Fassung
> («Neu steht für sich allein») war einen Tick zu breit und verbot ausgerechnet die
> Auftragsform, die eine Montage ist: Produkt erzeugen, Teile verbauen. Der ursprüngliche
> Grund bleibt gewahrt, es gibt weiterhin **eine** Vorlage.
> **`Verbaut` ist NICHT terminal** – Demontage ist real, und das Greifen IST der Ausbau
> (wie beim Sperren); `Verschrottet` bleibt der einzige endgültige Zustand. Weil ein
> verbautes Stück nicht im Regal liegt, zählt es zur **Historie** – die erste Kombination
> «Historie + nicht terminal», und der Beleg, dass die beiden Eigenschaften unabhängig
> sind. Die **Farbe folgt darum nicht mehr aus `terminal`**: verbaut ist aufhebbar **und**
> grün, weil es sein Ziel erreicht hat.
> **Die Stückliste ist eine ABLEITUNG, kein Feld** (`services/genealogy`): die Stücke, die
> denselben Auftrag als `Verbaut` verlassen haben. Gelesen wird der **Log**, nicht der
> heutige Zustand – sonst verschwände ein ausgebautes Zahnrad **rückwirkend** aus der
> Vergangenheit des Getriebes (dieselbe Regel wie im Prozessbild §8.1a). Ein ausgebautes
> Teil bleibt darum in der Liste und wird als *ausgebaut* gezeigt.
> **Das Bild kennt den Ausgang jetzt als REGEL statt als Sonderfall** (`flow._exit_points`):
> wer wo hinausging, steht im Log (letzter Eintrag `step` statt `end`), also hängt die
> Ausgangs-Kante an **ihrem** Modul. Vorher hiess es «ist das letzte Modul terminal?» –
> beim Verbrauch wären die verbauten Stücke damit auf der Kante hinter dem Ende gelandet,
> unauffällig, weil das Produkt dort ja wirklich hinausging.
> **Werkzeug ist kein Verbrauch und bekommt kein Modul**: eine Fräse steckt real in zwanzig
> Aufträgen gleichzeitig, die Exklusivität liesse genau einen zu. Es ist darum ein
> **Erfassungspunkt «Objekt scannen»** (`capture_types/object_scan.py`, der sechste Typ –
> und er war genau das, was die Registry versprochen hat: **eine neue Datei**).
> Wächter: `tests/test_consumption_module.py` (jeder gegen seine Bug-Form gegengeprüft),
> Matrix S11 · S11b · S16 · S16b · S17 · S17b · S18.
>
> **Das Ressourcenmodul nachoptimiert: Stückliste, Bindung, Nichtverfügbarkeit**
> (PROCESS_CORE §9.6). Drei Ausbauten, und **die eine echte Verallgemeinerung ist der
> Eintrittspunkt**. Der Eintritt hing fest am **Start-Objekt** – genau EINE Stelle legte
> eine `OrderUnit` an und genau eine schrieb `start`; ein Modul, das sich sein Material
> erst holt, wenn es dran ist, brauchte darum eine zweite. Verallgemeinert wurde der
> **Punkt, nicht der Mechanismus** (`process._enter_at_step`): dieselbe Zeile, dasselbe
> `start`-Ereignis, dieselbe Exklusivität – nur steht das Stück danach vor **diesem**
> Modul statt vor dem ersten. Am Eintrag steht die Modul-`id`; genau daran unterscheidet
> der Graph die beiden (`flow._tally` zählt nur `step_id IS NULL` als «gestartet», sonst
> trüge die erste Kante Material, das dort nie war).
> **Die Menge gilt JE STÜCK und wird beim ERREICHEN gerechnet** (`config.lines` =
> `[{article, quantity}]`): «4× Schraube M6» heisst vier je Getriebe; bei drei Getrieben
> zwölf. Beim Definieren steht die Zahl der Produkte nicht fest – eine Vorlage, die eine
> Auftragsmenge nennt, ist bei der zweiten Menge falsch, und zwar stillschweigend. Damit
> stehen die Komponenten **nicht mehr im Bedarf**: `_assert_consumables_present` ist
> ersatzlos entfallen, geblieben ist nur die Regel, dass ein Auftrag nicht verbaut, was er
> selbst erzeugt.
> **Die Zuordnung steht im LOG, je Produkt-Stück** (`payload.into`): das ist die exakte
> Genealogie **ohne** `into_instance_id`. Der Log gab sie nicht von selbst her – zwischen
> «diese zwölf gingen in diesem Auftrag hinaus» und «diese vier gingen in dieses Getriebe»
> liegt genau eine Angabe, und sie gehört dorthin, wo der Log ohnehin festhält, was ein
> Modul festgehalten hat. Ein Feld am Datensatz wäre die zweite Wahrheit, die bei einer
> Demontage geleert würde. **Welche Schraube in welches Getriebe geht, ist keine
> menschliche Entscheidung** (sie sind austauschbar) – entscheidend ist, dass es
> aufgeschrieben ist; darum deterministisch statt geraten. Altbestand ohne `into` wird
> tolerant gelesen (Aussage auf Auftragsebene).
> **Nichtverfügbarkeit ist KEIN Zustand** (`StepNeed`): die Freigabe geht, das Modul
> bewegt nichts, und die Zeile nennt Artikel · gebraucht · verfügbar. Es gibt keinen
> Pausen-Wert und keine Verknüpfung auf einen Nachschub-Auftrag – das Modul ist schlicht
> nicht fertig. Angeboten werden zwei Wege, und **beide gibt es schon**: eine andere
> Instanz wählen (dieselbe Wahl, die der Scan trifft – sie reist als `sources` mit) und
> ein **ganz gewöhnlicher** Auftragsentwurf. Automatisch ausgewichen wird nie.
> **Im Editor ist es dieselbe Komponente wie der Bedarf** (`DefinitionLines perUnit`),
> nur mit zwei Fragen weniger: die Herkunft entfällt (eine Stückliste erzeugt nichts) und
> die konkreten Stücke ebenso – ein Modul ist eine **Vorlage**, es läuft je Auftrag und je
> Produkt-Stück erneut, und ein dort festgenageltes Stück wäre nach dem ersten Mal
> verbraucht. *Das ist die eine Abweichung vom Wortlaut des Auftrags («optional einzelne
> Instanzen selektierbar»): die Auswahl steht bei der **Ausführung**, wo derselbe Auftrag
> sie ohnehin verlangt.*
> **`Module.leaves` ist entfallen** – seit die Komponenten am Modul **eintreten** statt
> anzukommen, verlässt kein ankommendes Stück den Verbrauch, und die Ausführung fragt
> wieder schlicht `module.terminal`. Eine Regel weniger.
>
> **Ein Kamerascanmodul für alles – und die Vorschläge kommen aus der Regel, nicht vom
> Aufrufer** (`lib/scan.ts`, `components/scan/`): Es gab nie zwei Dialoge, aber eine
> **Suche je Aufrufstelle** (`ScanStep.suggest`/`candidates`) – der Feed brachte eine mit,
> ein Prozessschrittmodul nicht. Dort war die Vorschlagsliste damit **strukturell leer**:
> wer «00787» tippte, sah nichts, nur die volle neunstellige Nummer ging durch. Genau
> daraus entstanden alle drei gemeldeten Punkte – die Notlösung «Von Hand bestätigen»
> neben dem Scanner, die fehlende Teileingabe und der «Übernehmen»-Knopf, der beim
> Nicht-Treffer **gesperrt** war und so ausgerechnet den **Grund** verschwieg. Jetzt gilt
> eine Regel: **der Scanner bietet an, was er ANNIMMT** (`offersFor`) – bei einer
> Verifikation ist das `expected`, also braucht es dort gar keine Suche. Enter und Klick
> gehen direkt durch; passt es nicht, steht der Grund **im Zielrahmen** (dort ist der
> Blick, dort meldet die Farbe den Zustand). Die Tastatur ist damit die Alternative **im
> Dialog**, und **wie** bestätigt wurde, sagt er selbst (`onComplete(ids, via)`) statt ein
> zweiter Knopf daneben, der gar nichts verifizierte. Gemessen: 10 Logik-Prüfungen +
> 9 Browser-Prüfungen in Chromium (Teileingabe → Vorschlag → Klick → `manual`, falsche
> Nummer → Grund im Rahmen).
>
> **Die Stichprobe ist EINE Zahl: der Anteil an der GESAMTMENGE** (`domain/sampling.py`):
> alle (100 %) · Hälfte · Viertel · frei – die Kurzwege sind Werte derselben Zahl, keine
> eigenen Modi. «Je Instanz» ist zurückgenommen: ein Modul sieht die Summe dessen, was
> davorsteht, und «10 % von drei Chargen» ergab drei Ziehungen, von denen keine der Zahl
> auf dem Bildschirm entsprach (bei Einzelserialisierung sogar **100 %**, weil aus einem
> Stück immer mindestens eines gezogen wird). Gezogen wird darum **einmal je Modul**, wenn
> es erreicht wird, über den **vollen Bestand des Auftrags** – nicht je Welle, sonst wäre
> es wieder «je Instanz» (die Stücke kommen instanzweise an, §4.4). Aufgerundet, mindestens
> eines, höchstens alle: «0 von 5» ist keine Prüfung, sondern ihr Ausfall.
>
> **Ein Ausgang ist EINE Eigenschaft mit DREI Wirkungen** (`Module.terminal`): der Editor
> bietet dahinter nichts an (die Palette steht *vor* dem Ende – wo es keines gibt, gibt es
> sie nicht), die Freigabe weist ein Modul dahinter ab (das Netz, `domain/chain`), und das
> **Bild endet dort** (`flow.build` hängt kein `end`-Objekt an). Die dritte fehlte, und
> genau daraus kam die gemeldete Meldung «Kante `edge:end:done`: dort stehen
> Einzelinstanzen, aber sie gilt als nicht gegangen» – ein **echter** Fehler der Zeichnung,
> den die Invariantenprüfung zu Recht meldete (nachgestellt: mit der alten Zeichnung
> erscheint er wortgleich wieder). Ein neuer Modultyp mit `terminal = True` erbt alle drei.
>
> **Der Grund beim Aussondern ist Pflicht – beim MODELLIEREN** (`config.reason`, beide
> Ausprägungen). Warum ausgesondert wird, ist eine Eigenschaft des Ablaufs und lautet bei
> jedem Stück gleich; am Band wäre es ein Feld, das immer dasselbe aufnimmt. Zur Laufzeit
> erfasst das Modul darum **nichts** (der Scan ist die Bestätigung), und der Grund steht
> als Auskunft an der Ausführungsstelle (`ProcessStepResponse.reason`).
>
> **Zwei Fehler nebenbei, beide still:** (1) `ModuleConfigInput` kannte nur `points` –
> Pydantic verwarf beim Eintreffen **jedes** andere Feld. `mode` (Verschrotten ↔ Sperren)
> und `sample` kamen damit **nie** an, beide Vorgaben galten immer, ohne eine einzige
> Fehlermeldung; die Konfiguration ist jetzt ein freier Satz Werte, und was darin stehen
> darf, entscheidet allein der Modultyp (`Module.clean_config`). (2) Die **Modulfarbe**
> kam über einen Rückruf des Rahmens aus dem Modul-Katalog – und den lädt nur der Editor:
> im freigegebenen Auftrag kam nichts an, und der stille Rückfall `?? MODULE_TONE.slate`
> gab jedem Modul die Farbe der **Datenerfassung**. Sie reist jetzt als Feld mit dem
> Schritt (`ModuleFacts.tone`), ein Aufrufer kann sie nicht mehr vergessen, und
> `moduleTone` hat keinen Rückfall mehr auf eine echte Modulfarbe: Unbekanntes sieht
> kaputt aus, statt sich als anderes Modul auszugeben.
>
> **Die neue Prozesslogik steht in `PROCESS_CORE.md`** – verbindlich, vor jeder Arbeit am
> Prozess lesen. Kurzform: Auftrag → geordnete Modul-Liste → Einzelinstanzen passieren sie,
> jeder Statuswechsel schreibt einen Eintrag im append-only Ereignis-Log; Exklusivität als
> partieller Unique-Index. **Artikel und Auftrag entstehen erst mit ihrer Freigabe** – bis
> dahin lebt der Entwurf im Browser, ohne Zeile und ohne Objektnummer. Das erste echte
> Prozessschrittmodul ist die **Datenerfassung** (Erfassungspunkte: Text · Ja/Nein · Bild ·
> Signatur · Soll-Ist-Vergleich, je Typ eine Datei in `domain/capture_types/`).
> **Abweichungen sind ganz normale Aufträge** (PROCESS_CORE §12): ein Auftrag, der Stücke
> mit Status `Im Prozess` greift, entzieht sie dem laufenden Auftrag und trägt dafür ein
> **abgeleitetes** Label (im Bild ein Zeichen am Symbol, in Feed und Kopf dieselbe
> Komponente). Ob ein Stück zurückkehrt, ist eine Eigenschaft der **Verbindung**
> (`order_units.return_to_order_id`), nicht des Auftrags – darum funktionieren Schachtelung
> und Parallelität ohne zweite Regel. Kein `if abweichung:` im Code.
> **Die Abzweigung hängt an einem Zustandspunkt** («vor Modul X» = `current_step_id`), nicht
> an einem Modul – das Stück hat es nie betreten, und darum kehrt es an denselben Punkt
> zurück. **Solange eine Rückführung aussteht, ist das Modul gesperrt**: durchgesetzt an
> der EINEN Ausführungsstelle (`process.confirm_step`), dargestellt in der EINEN Modul-Karte
> (`StepCard`, `fieldset[disabled]`) – ein Modul fragt nicht, ob es darf.
> **Das Bild ist ein GRAPH, und der Server liefert ihn** (PROCESS_CORE §8.1a′,
> `services/flow.py` → `OrderResponse.flow`): **Knoten** (start · module · end · **fork** ·
> **join**), **Kanten** dazwischen, **Positionen** immer auf einer Kante, **Kantenzustand**
> nur gegangen ↔ ausstehend. Abgeleitet aus dem **Ereignis-Log**, nie aus dem aktuellen
> Zustand – darum verschwindet eine Abzweigung nicht mehr, sobald das Stück zurück ist,
> und «einmal kräftig bleibt kräftig» folgt aus der Append-only-Natur des Logs statt aus
> einem Wächter. **Der Kantenzustand gehört der KANTE, nicht dem Punkt**: der Hauptstrang
> ist eine **Folge** von Kanten, und «hier ist Material angekommen» gilt für die Kante zum
> Abzweigepunkt, nicht für den geraden Weg dahinter. Nimmt eine Abweichung **alle** Stücke,
> hat ihn niemand genommen → Haarlinie. Gerechnet als **Bilanz entlang der Achse** (jeder
> fork zieht ab, jeder join addiert, `flow._branches`), gezählt in **Einzelinstanzen** statt
> Log-Zeilen – kein `if` je Kantenart. **Die Nachbarn kommen aus DEMSELBEN Graph**
> (`Graph.neighbours`): die Spalte daneben und die Linie dorthin sind dieselbe Liste, ein
> Nachbar existiert genau dann, wenn es seine Kante gibt. Zwei Ableitungen ergaben sonst
> den Abzweigepunkt **ohne** seinen Nachbarn – kein Block, keine Linie, nur der Punkt.
> Abzweige- und Rückführpunkt sind **eigene Knoten**: nur so steht das
> gebliebene Stück auf dem Bypass und das zurückgekehrte hinter dem Zusammenfluss. Das
> Frontend **rechnet keine Prozesslogik** – es layoutet und zeichnet, und **jede** Linie
> geht durch den EINEN Generator (`process-flow.polyPath`, der ein zu kurzes
> Zwischenstück selbst begradigt statt es als Knick zu runden). **Geführt wird nach
> etablierter Diagramm-Praxis** (PROCESS_CORE §8.1a″), nicht nach Gefühl: **Ports** statt
> Flächen (React Flow *Handles* / bpmn-js *docking points* / Miro-Anker – `port()`; eine
> Querverbindung dockt an der **Spalte** an, an deren erster bzw. letzter Zeile, nie am
> `end`-Objekt mitten in ihr); **Kanäle** statt einer Gasse (ELK *tracks* – `channels()`
> färbt den Intervall-Graphen gierig nach Anfang, die Lücke wächst mit `gutterFor`,
> überschneidende Nachbarn stehen untereinander in einem Band); **ein** Linien-Layer mit
> `overflow: visible`, Platz kommt aus dem Layout statt aus einem Versatz. Damit ist «zwei
> Abweichungen» kein Sonderfall, sondern n statt 1.
> **Kreuzungsfreiheit entsteht im GRAPH** (PROCESS_CORE §8.1a‴): das Bild ist ein
> **Raupengraph** (Achse + Anhängsel) und darum genau dann kreuzungsfrei, wenn die
> Ansatz-Intervalle disjunkt sind – also bekommt **jeder Nachbar ein eigenes Paar
> `fork`/`join`** hintereinander auf der Achse (`fork:<Modul>:<Auftrag>`), statt dass
> sich alle eines teilen. Mit einem gemeinsamen Rückführpunkt musste der Rückweg des
> ersten an allen folgenden vorbei; jetzt ist jede Verbindung eine kurze Waagrechte und
> eine Kreuzung **unmöglich** statt vermieden (3, 4, 5 Abweichungen = 3, 4, 5 Paare;
> geschachtelte sind kein Fall). **Die Krümmung ist die Richtung**: der Fluss geht von
> oben nach unten, das Stück auf der Achse wird **immer stromabwärts** durchlaufen – die
> Zuführung schert damit aus, die Rückführung mündet ein, unterscheidbar ohne Pfeil und
> ohne Farbe. Sie beginnt **im** Punkt (ein Endstück darf ganz im Bogen aufgehen, darum
> liegt kein gerades Stück über der Hauptlinie), der senkrechte Takt ist eine Ableitung
> des Radius (`FLOW_GAP = 2·BEND`, im Raster **wie** in der Spalte) – zwischen einem
> Abzweigepunkt und **seinem** Rückführpunkt liegen **zwei Waagrechte** (`fork+BEND` und
> `join−BEND`), und übrig bleiben soll so viel Luft, wie der Punkt gross ist; der frühere
> Takt `2·BEND − 8` liess **einen** Pixel, im Bild also eine einzige Linie (gemessen: 1,6 px
> über 172 px gemeinsame Länge, sichtbar in der schmalen Nachbarspalte, nicht in der Mitte).
> Die Querverbindung ist EINE Waagrechte (`NEIGHBOUR_PAD` oben wie unten, Rückführpunkt am
> Ende seiner Zeile) – ausser zum **übergeordneten** Auftrag, dessen Punkte sein eigener
> Prozess setzt.
> **Der Entwurf ist dasselbe Bild, nur früher** (PROCESS_CORE §8.1c): nimmt die Auswahl
> einem laufenden Auftrag ein Stück ab, steht **er** schon vor der Freigabe in der linken
> Spur – mit dem Abzweigepunkt, der entstünde, und dem Rückführpunkt, falls zurückgeführt
> wird. Kein Nachbau: dieselbe Ableitung (`flow.build(..., planned=[…])` ← `/orders/validate`
> → `OrderValidation.parents`) und **EIN** Rahmen für beide Fälle (`ProcessColumns`; was in
> der Mitte steht, sagt der Aufrufer – laufender Auftrag oder Modul-Editor). Geprüft wird
> die **Gleichheit selbst**: Vorschau vor der Freigabe == echter Graph danach, bis auf
> Objektnummer und `walked` (nichts Geplantes ist je gegangen). Der Entwurf hat dafür eine
> **Adresse statt einer Nummer** – `DRAFT_OBJECT_ID = 0`, auf beiden Seiten dieselbe, sonst
> endete die Linie still im Nichts.
> **Der Rückführungs-Schalter steht AUF der Linie, die er schaltet** (§8.1a): eine Pille
> unter dem Ende-Objekt, also an der **letzten Zeile der Spalte** – genau dort dockt die
> Rückführungslinie an, sie geht von ihm ab. Er bleibt, wenn die Linie geht (sonst wäre die
> Entscheidung einmalig), und sagt seinen Zustand im Wort («kehrt zurück» ↔ «bleibt hier»),
> nie im Strichmuster. Drei Anläufe stehen dahinter, und der Unterschied ist jedes Mal
> *wo*: neben der Stückauswahl (Aussage ≠ Wirkung) · Ersatz-Knoten mit **eigener** Linie
> (zwei Rückweg-Linien für EINE Entscheidung) · Klick auf die ganze Nachbarspalte (kein
> Bedienelement, nur Fläche – man sieht ihr nicht an, dass sie etwas tut).
> **Die Linie sagt die Vergangenheit, die Pille die Gegenwart** (§8.1a): `walked` kommt aus
> dem Log (monoton, verschwindet nie), `units[].status` ist der HEUTIGE Zustand des Stücks.
> Eine Abzweigung bleibt darum für immer im Bild, das Wort daneben wechselt – «In
> Abweichung», solange es dort arbeitet, danach «Abgegeben» (gekappt) bzw. es verschwindet
> (zurückgekehrt, dann steht es wieder auf der Achse). Ein Zustandswort in der
> Gegenwartsform, das Vergangenes behauptet, ist ein Fehler, auch wenn es einmal stimmte.
> **Eine Blase, und zwar die unter dem Zeiger** (`globals.css`): geschachtelte Hinweise –
> die innere gewinnt (`:has`); und der Fokus-Weg (Touch/Tastatur) gilt **mit Maus nur für
> `:focus-visible`** – ein Klick liess seine Blase sonst stehen, während der Zeiger längst
> woanders war. Die **Historie** hängt an der **Kopfzeile** des Prozessobjekts (#790 – am
> Symbol war sie ein 32-px-Ziel), nie an einer gekürzten Beschriftung: `truncate` ist
> `overflow: hidden` und schneidet das `::after` weg – genau daran war sie am Modul
> unsichtbar und an Start/Ende sichtbar.
> **Herkunft und Verbleib sind ÄSTE desselben Strangs** (PROCESS_CORE §8.1a, §6): über dem
> Start und unter dem Ende verzweigt die Linie zu den Nachbar-Aufträgen – je Nachbar ein
> Ast mit Anzahl, alle auf **einer** Waagrechten zusammengeführt (ein Bus wie im Stammbaum,
> darum keine Überlagerung); die Zeile bricht nie um und ist gekappt (`JOURNEY_LIMIT`,
> Rest gezählt). **Gruppiert statt aufgezählt** – bei 3 wie bei 5000 Stück dasselbe Bild;
> wer die Nummern braucht, öffnet den Nachbarn, und dort ist er die Mitte (zwei Ebenen,
> keine Rekursion). Die eine Herkunft ohne Log-Eintrag ist die **Entstehung** («3× Blech»),
> denn ein Erzeugungsauftrag hat keinen Vorgänger; zusammen decken beide jedes Stück ab
> (gemessen) – deshalb ist der frühere Definitions-Container ersatzlos entfallen.
> **Freie und gebundene Stücke dürfen im selben Auftrag stehen** (§12.6a) – dafür braucht
> es keine Regel: die Absicht steht **je Stück** (`UnitPick.from_order`), nicht je Auftrag,
> und `return_to_order_id` entsteht nur für die geliehenen. Gemessen an den echten
> Dienstpfaden; eine zusätzliche Regel wäre eine zweite Aussage über dieselbe Sache.
> **Scrollbalken sind generell unsichtbar** (`globals.css`, `*`-Regel – nicht je
> Container): ein Balken kostet echte Breite, und wenn er beim Aufklappen erscheint,
> springt alles Zentrierte seitlich. Gescrollt wird unverändert. **Zähler und Aufklappen fragen
> dieselbe Position** (`FlowEdge.members` → `flow.units_on`, `GET …/units?edge=…`) – die
> frühere zweite Abfrage «alle Stücke an Schritt X» war gröber als das Bild und zeigte an
> einer Teilung beide Gruppen. Invarianten: `tests/test_flow_graph.py` (gegen echtes
> PostgreSQL, in der CI **nach** dem Schema-Aufbau).
> **Das Bild hat EIN Liniensystem** (PROCESS_CORE §8.1a/§8.1b): zwei Stärken – gegangen
> (kräftig) ↔ ausstehend (Haarlinie) –, keine dritte Farbe, keine Strichmuster; ob ein
> Stück zurückkehrt, sagt **ob es die Linie gibt**. Drei Spuren in **einem** Raster mit
> einer Zeile je Knoten: der Nebenauftrag steht in der Zeile seines Zustandspunkts, die
> Zeile wächst auf seine Höhe, die Hauptachse wächst mit – Teilung, zwei Wege,
> Zusammenfluss. Alle Spurmasse in `process-flow.LANE`, entschieden nach **effektiver
> CSS-Breite** des Rahmens (ein 13,3″-Notebook liefert 1440 CSS-Pixel, nicht 2560).
> **Die Auswahl nennt, wo sie zugreift** (PROCESS_CORE §12.6a): jeder gewählte Anteil trägt
> seine Absicht mit (`UnitPick.from_order` – «war frei» ↔ «aus Auftrag N»), und die Freigabe
> vergleicht sie mit der Wirklichkeit. Ohne das entschied die Reihenfolge der Klicks, welche
> **Art** Auftrag entsteht. EINE Auswahl-Logik: konkrete Stücke, vorher sichtbar, änderbar –
> FIFO schlägt vor, der Mensch übersteuert. **Seitwärts scrollen ist verboten**; nichts
> Unsichtbares darf die Breite bestimmen (ein `opacity:0`-Tooltip zählt zur Overflow-Fläche).
> **Der Bestand ist eine Summierung in drei Ebenen – ohne Filter** (PROCESS_CORE §10.3):
> Leiste über alles → eine Zeile je Instanz mit eigener Leiste → die Nummern auf Klick
> (`GET …/articles/{id}/stock`, `GET …/instances/{id}/units`). Ein Filter versteckt, was er
> nicht zeigt; hier ist die **Aufteilung selbst das Bedienelement** – ein Segment anklicken
> heisst «zeig mir diese Nummern», der Rest bleibt sichtbar. Die Instanz hat dabei **keinen
> Zustand, sondern eine Aufstellung** (`states`, Menge = ihre Summe): eine Gruppe mit drei
> freigegebenen und einem laufenden Stück hat keine richtige Einzel-Antwort. Genau daran
> starb der Vorgänger – er las `Instance.status`, eine Spalte, die es nicht gibt, und
> antwortete auf **jeden** Aufruf mit 500. Sortiert wird **aufsteigend nach Objektnummer =
> FIFO** (Nummern steigen, Instanz und Stücke entstehen gemeinsam – kein zweites Datum),
> gruppiert nach **Instanz** statt nach Zustand (die Leiste beantwortet den Zustand längst,
> und nach Zustand gruppiert stünde dieselbe Charge in zwei Gruppen). **Nie alles auf
> einmal**: 50 Instanzen bzw. 60 Nummern je Seite, gemessen 5 Abfragen und ~8–14 ms bei
> 300 Instanzen wie bei einer 5000er-Charge. Dieselbe Regel gilt im Instanz-Datensatz –
> dessen frühere Volle-Liste (`units_of`, gemessen 149 ms / 5000 Zeilen) ist **ersatzlos
> entfernt**, damit sie niemand versehentlich wieder benutzt.
> **Der Scanner ist wieder in Betrieb – und die Deutung ist austauschbar** (`lib/scan.ts`,
> `components/scan/`): der Knopf in der ERP-Suchleiste öffnet die Kamera, der Treffer öffnet
> den Datensatz (`resolveObject`). Drei Schichten, unverändert getrennt: Logik ohne React ·
> Kamera-Hook ohne ERP-Wissen · Dialog ohne Kamera-API. **Neu ist die Naht dazwischen**:
> `ScanReading` (`read` · `check` · `prompt`) sagt, was ein Kamerabild BEDEUTET – heute
> `objectCodes`, und der Dialog kennt weder ZXing noch Objektnummern. Eine zweite Deutung
> ist damit ein neues Objekt, kein Umbau. **Zwei Datenfehler behoben:** der 380-ms-
> Quittierungs-Timer lief nach Esc weiter (`onComplete` bewegte eine Instanz, die niemand
> mehr bewegen wollte), und der freie Lookup nahm **jede** 9-stellige Zahl an – der Rahmen
> wurde grün, und beim Aufrufer passierte stillschweigend nichts (404, verschluckt). Jetzt
> fragt `ScanStep.exists` nach, und der Grund steht im Bild. **Gerätetauglichkeit:**
> `pickCamera` meidet die Ultraweitwinkel-Linse (die bei 10 cm nicht scharf stellt – die
> häufigste Ursache für «erkennt nichts»), Taschenlampe über `torch`, und der native
> `BarcodeDetector` kommt zuerst: ZXing wird nur noch **dynamisch** geladen (Öffnen kostet
> **5 kB statt 112 kB gzip**). `autoFocus` hängt am Kamerazustand – läuft sie, bleibt die
> Bildschirmtastatur zu; der **Hardware-Scanner** bleibt trotzdem bedienbar, weil die erste
> Ziffer den Fokus holt und mitgenommen wird. Etikettendruck ist EIN Bauteil (`LabelButton`)
> an Artikel · **Instanz** · Auftrag – vorher gab es ihn nur am Artikel, also ausgerechnet
> nicht am Ding im Regal. **Gemessen, nicht gelesen**: 21 Prüfungen in Chromium mit echter
> Fake-Kamera (QR → Y4M), beide Kernfixes gegen ihre Bug-Form gegengeprüft. *Am Gerät
> offen: welche Linse `pickCamera` real trifft und ob `torch` greift – beides braucht ein
> Telefon.*
> **Der Bestand ist EIN Modul mit zwei Umfängen** (`components/erp/stock-view.tsx`,
> PROCESS_CORE §10.3): am **Artikel** sind die Zeilen seine Instanzen, an der **Instanz**
> direkt ihre Einzelinstanzen – dieselbe Karte, dieselbe Leiste, dieselbe Aufteilung, nur
> ein anderer Ausschnitt derselben Frage. Die Instanz-Ansicht ist damit exakt der Teilbaum,
> den man am Artikel aufklappt; vorher war sie eine schlichte Liste ohne Leiste und ohne
> Historie – zwei Fassungen, die beim ersten neuen Zustand auseinandergelaufen wären. Beide
> tragen jetzt die **Spezifikations-Karte** (`SPEC.card` + `SpecHead`/`SpecSection`, aus dem
> Artikel nach `fields.tsx` gezogen): sie ist die Anatomie **jeder** Detail-Ansicht, nicht
> die des Artikels – wer daneben etwas baute, schrieb sich sonst einen eigenen Kopf.
> **Ein neuer Status wird an genau EINER Stelle ergänzt** (`domain/statuses.py`): ein
> Eintrag trägt Beschriftung, Ampelton, **Achsen** und – für Stücke – ob er zum Bestand
> oder zur Historie zählt; alles Weitere ist abgeleitet. Der Frontend-Katalog wird
> **generiert** (`scripts/dump_statuses.py` → `lib/status-catalog.ts`, in der CI wie
> `api.ts` auf Aktualität geprüft) statt gespiegelt: ein Spiegel, den ein Test vergleicht,
> **findet** ein Auseinanderlaufen, verhindert es aber nicht. Und die fachliche Zuordnung
> «Bestand ↔ Historie» gehört an den **Status**, nicht in die Bestandsansicht – sie stand
> als eigene Liste daneben (`LIVE_UNIT_STATUSES`), also in genau der Form, die man beim
> nächsten Zustand vergisst: er wäre stillschweigend als Bestand gezählt worden. Jetzt ist
> es ein Feld, sein **Fehlen ein Fehler beim Start**, und zur Laufzeit reist die Antwort als
> `StockState.stock` mit den Daten; ein Zustand ohne Zuordnung wird in der Oberfläche
> **gemeldet** statt geraten.
>
> **Ein Endzustand ist endgültig – und das steht in der DATENBANK** (PROCESS_CORE §5.3,
> Migration `110`): Gemeldet war, dass ein **verschrottetes** Stück später wieder auf
> «Freigegeben» stand. Über keinen Dienstpfad und in keiner einzelnen Anfrage war das
> nachstellbar – und genau das war die Spur: der Schreiber sass **ausserhalb** der
> Prozesslogik. Eine Alt-Reparatur im Startvorgang (`main._ensure_columns`) setzte
> `UPDATE instance_units SET status='freigegeben' WHERE status NOT IN
> ('freigegeben','im_prozess')`; die Liste stammte aus der Zeit, als es nur diese beiden
> Zustände gab, und wurde still falsch, als **Gesperrt** und **Verschrottet** dazukamen.
> Seither hat **jeder Start – also jeder Deploy –** jedes ausgesonderte Stück
> zurückgesetzt (gemessen: `UPDATE 4`, beide Zustände auf `freigegeben`).
> **Die Lehre steckt in der Form des Schutzes, nicht im Einzelfix.** «Endgültig» ist eine
> **Eigenschaft des Status** (`Status.terminal`, aus der `is_selectable`, die Farbe und
> die Prüfungen folgen – das frühere zweite Feld `selectable` ist darin aufgegangen), und
> sie gilt auf drei Ebenen: **die eine Schreibstelle** (`process._pass`, 409 mit einem
> Satz und der Stück-Nummer, bevor etwas geschrieben ist) · **die Tabelle selbst** (Trigger
> `trg_instance_units_terminal`, aus dem `CATALOG` erzeugt und bei jedem Start nachgezogen
> – er kennt auch das Reparaturskript, die Migration und das `UPDATE` von Hand) · **der
> Abgleich Log ↔ Zeile** (`flow._verify_history`). Die dritte musste dabei umgebaut werden:
> eine Invariante, die **nur den Log** liest, hätte genau diesen Fehler nie gefunden – ein
> Schreiber ausserhalb der Prozesslogik hinterlässt gar keinen Eintrag. Gefragt wird darum
> nach dem **Widerspruch**: der Log sagt Endzustand, die Zeile sagt etwas anderes.
> **Es gibt keine Umgehung** – kein Parameter, kein Force-Flag. Wer eine bräuchte, hat ein
> Modellproblem: ein Zustand, den man doch verlassen können muss, ist nicht terminal, und
> das ist eine Zeile im `CATALOG`.
> Die Reparatur selbst nimmt ihre Liste jetzt aus dem Katalog und heilt nur, was er
> **nicht kennt**; und das Sicherheitsnetz **schreibt sein Schema fest, bevor es Daten
> anfasst** (vorher riss eine scheiternde Daten-Reparatur jede eben ergänzte Spalte mit in
> den Rollback – die Ausfallklasse von Migration `090`, eine Ebene tiefer).
> **«Abgeschlossen» heisst «den definierten Weg zu Ende gegangen»**, nicht «das
> Ende-Objekt passiert»: ein **Ausgang** ist ebenfalls ein Ende, ein Abweichungsauftrag,
> der verschrottet, ist also abgeschlossen. Keine Verhaltensänderung – genau das zählt
> `order_statuses` seit jeher –, nur die genauere Beschreibung.
> Wächter: `tests/test_terminal_status.py` (jede der drei Ebenen **gegen ihre Bug-Form**
> gegengeprüft).
>
> **Endgültig heisst auch UNERREICHBAR – und das war noch nicht so** (PROCESS_CORE §5.3):
> An einer **verschrotteten** Einzelinstanz stand der Abweichungstrigger weiterhin da, und
> sie wurde sogar **vorgewählt**. Die Daten waren nie in Gefahr (die Freigabe lehnte ab),
> aber die Ablehnung kam **erst beim letzten Klick** – die unangenehmste Form einer Regel:
> sichtbar erst, wenn man alles getan hat. Ursache war eine **weggeworfene Angabe** – die
> Antwort trägt den Zustand jedes Stücks, die Ansicht liess ihn beim Einlesen fallen
> (`order-detail`), danach *konnte* sie nicht mehr prüfen. Jetzt folgen **alle** Wirkungen
> aus der einen Eigenschaft (`pick_problem` → `is_terminal`, im Frontend `isPickable` aus
> dem **generierten** Katalog): die Auswahl-Liste weist es aus, der Trigger **erscheint
> gar nicht** (nicht ausgegraut – ein Knopf, der nie etwas tun kann, ist kein Angebot),
> die Vorauswahl lässt es fallen, der **Entwurf** ist nicht freigebbar und sagt warum, die
> Freigabe lehnt ab. Nebenbei geschlossen: die Prüfung sass im `source is None`-Zweig, galt
> also nur für **freie** Stücke – eine Regel aus Versehen, die beim nächsten Modul gekippt
> wäre. **Gesperrt bleibt greifbar** (das Greifen IST das Aufheben).
>
> **Der Scan gilt der Instanz, die Erfassung der EINZELINSTANZ** (PROCESS_CORE §9.5): Zwei
> verschiedene Dinge, und sie hingen aneinander – **ein** Wertesatz je Bestätigung, kopiert
> auf jedes gezogene Stück. Bei einer Charge über 2 entstanden zwei Messwerte, gemessen
> war einer; ein Nachweis mit mehr Zeilen als Messungen ist keiner. Die Zahl kommt jetzt
> aus der **Ziehung**: 1 Scan → 2 Erfassungen, ¼ von 6000 → 1 Scan → **1500**. Die Nutzlast
> ist zweistufig (Nummer → Punkt → Wert), und der Server verlangt **Deckung in beide
> Richtungen** – zu viel ist ein Nachweis über Ungeprüftes, zu wenig eine Lücke, die wie
> «durchgelaufen» aussieht. Das **Urteil hängt am Stück**, der Halt an der Instanz (ein
> einziges «nicht bestanden» hält alles an, §4.5). Welche Stücke gezogen sind, kommt **erst
> auf Klick** (`…/hold?group=sample` – dieselbe Auskunft wie die Vorauswahl der
> Entscheidung, nur eine dritte Gruppe); für die **Vorschau** genügen die Zahlen aus
> `step_work`. *Offen und bewusst nicht gebaut: ein Erfassungspunkt, der der ganzen Charge
> gilt (Verpackung intakt?) – das wäre eine Eigenschaft der **Instanz**, kein Wert je
> Stück; auf Verdacht gebaut wäre es die Kopie durch die Hintertür.*
>
> **Abweichung = der Start wich vom REGELSTART ab** (PROCESS_CORE §12.2): Die Regel hiess
> «Stück war `Im Prozess`», also «einem laufenden Auftrag entzogen» – technisch stimmig,
> fachlich zu eng. Ein **gesperrtes** Stück wieder in Betrieb zu nehmen gehört zu keinem
> laufenden Auftrag und fiel heraus, obwohl es in der Qualitätssicherung der Musterfall
> einer **Sonderfreigabe** ist. Jetzt: `status_before != START_BEFORE` – die Regel **nennt
> keinen Status mehr**, sondern vergleicht mit dem einen Regelstart (`Freigegeben`). Das ist
> zugleich die einfachere und die haltbarere: ein künftiger Zustand ist automatisch eine
> Abweichung, ohne dass ihn jemand einträgt, und die Richtung stimmt (wer zu viel ausweist,
> dokumentiert; wer zu wenig ausweist, verliert den Nachweis).
>
> **Der Bestand gruppiert je STATUS – und zählt keinen auf** (PROCESS_CORE §10.3): statt
> zwei fester Blöcke («Bestand»/«Historie», in denen ein neuer Zustand verschwand) eine
> Gruppe je Zustand, der wirklich vorkommt. Reihenfolge = Position im `CATALOG` =
> **Lebenszyklus**, dieselbe, die Leiste und Legende ordnet; Farbe = Ampelton; **zugeklappt**
> startet, was zur Historie zählt (`stock` bleibt damit eine gelesene Eigenschaft, nur nicht
> mehr die Gruppierung). Die **grosse Gesamtzahl im Kopf ist entfallen** – sie summierte
> auch Verschrottetes und war damit zugleich irreführend und uninformativ. Dieselbe
> Komponente am Artikel wie an der Instanz, wie bisher.
>
> **Modul-Vorschau vor dem Scan** (#708, zentral in `capture-work`, also erbt sie **jedes**
> Modul): was erfasst wird und an wie vielen Einzelinstanzen – **bevor** gescannt wird. Der
> Scan bleibt Voraussetzung für die **Eingabe**, war aber auch Voraussetzung für die
> **Auskunft**, und das war zu viel. Dazu je Instanz ein eigener Scan-Knopf; der grosse
> Sammel-Knopf bleibt. **Einheit beim Soll-Ist-Vergleich** (#707, `unit`, frei, ≤ 8 Zeichen):
> die Mengeneinheiten des Artikels (`Stk · mm · m2 · m3 · kg · l`) sind **nicht**
> wiederverwendbar – sie beantworten «worin wird die Menge geführt» und kennen weder °C noch
> bar; «Stk» wäre als Messeinheit sinnlos. Eine zweite **Liste** wäre endlos, also gar keine:
> das System rechnet nie mit der Einheit, es zeigt sie an. «Stichprobe» steht **über** den
> Knöpfen (#706), «der Gesamtmenge» ist entfallen (#705 – die Bezugsgrösse steht im Hover).
> **Die Instanz nennt ihren Artikel als Datensatz**: verlinkte Objektnummer im Werteraster
> statt eines abgeschriebenen Namens – ein Klick, immer aktuell. Der Typ heisst im Kopf
> jetzt «Instanz» statt «Instanzen» (der einzige Plural in `TYPE_META`; über EINEM Datensatz
> las er sich, als wären es mehrere).
> **Die Vorschlagssuche im Scanner funktionierte nie** – der Code war da, die Daten nicht:
> der Dialog filterte `step.candidates`, und der einzige Aufrufer (der freie Lookup im Feed)
> kann keine fertige Kandidatenliste mitgeben, also war die Quelle **immer leer**. Wer
> «00787» tippte, sah nichts. Jetzt reicht der Feed **seine eigene Suche** durch
> (`ScanStep.suggest` ← `feedMatch` + `api.getInstances`, entprellt, mit Veralterungs-
> Schutz), statt dass der Scanner eine zweite baut. **Nur die Vorschlagsquelle wird breiter,
> nicht die Gültigkeitsregel** (`validateForStep`): ein `restrict`-Schritt fragt `suggest`
> gar nicht erst, und der Hardware-Weg (volle Nummer + Enter) bleibt unberührt.
> **Gemessen, nicht gelesen**: 34 Prüfungen in Chromium (beide Umfänge, drei Blöcke inkl.
> eines erfundenen Zustands, Artikel-Link, Vorschlag aus Teilnummer, voller Scan, unbekannte
> Nummer); jeder neue Wächter gegen seine Bug-Form gegengeprüft.
>
> **Drei Fehler mit EINER Wurzel: eine Ansicht las eine Grösse, die sich weiterbewegt**
> (gemeldet an Auftrag 100000799 und 100000802 – «der Prozess kann nicht weiter laufen,
> obwohl eine Instanz vor der Modultüre steht» und «auf einmal eines im Prozess und eines
> verschrottet, obwohl hier gar nichts verschrottet wurde»). Beide sahen aus, als kämen sie
> aus dem Nichts, und beide waren nachstellbar.
> **(1) Die Oberfläche erfand eine Sperre, die der Dienst nicht hat – und die erfundene
> Sperre hatte keinen Schlüssel** (`capture-work.tsx`, PROCESS_CORE §4.5). Nach einem
> «nicht bestanden» steht die Instanz still; `held_units` ist dafür eine **Auskunft**
> («welche Stücke haben zuletzt ein negatives Urteil?»), und `confirm_step` lehnt eine
> erneute Erfassung **nie** ab – das nächste Urteil ersetzt das letzte, das ist der eine
> Ausweg. Das Modul rendete aber `held ? <Entscheidung/> : <Formular/>`: Formular und
> Scan-Knopf verschwanden genau dann, wenn man sie braucht, und die einzige verbliebene
> Handlung war ein Abweichungsauftrag. Kam der zurück, blieb `held` stehen – der Auftrag
> stand für immer, obwohl jeder Backend-Aufruf ihn weiterbewegt hätte. Jetzt steht die
> Entscheidung **neben** dem Weg nach vorn (`{work.held && …}` statt `held ? … : …`), und
> der Scan-Knopf hängt nur noch an der Verifikation. *Der erste Anlauf war falsch und wurde
> verworfen:* eine Sperre im Backend nachzubauen hätte einen Schlüssel gebraucht, und zwei
> bestehende Tests haben genau das gemeldet.
> **(2) Die Pille las den heutigen Zustand auch auf der ACHSE eines längst abgeschlossenen
> Auftrags** (`flow._rows`, §8.1a). «Die Linie sagt die Vergangenheit, die Pille die
> Gegenwart» stimmt – aber «Gegenwart» heisst *die dieses Auftrags*, und die endet mit ihm.
> Verschrottete ein Folgeauftrag eines seiner Stücke, stand im fertigen Bild plötzlich
> «eines im Prozess, eines verschrottet», ohne dass dort je etwas ausgesondert wurde. Die
> Achse liest den Status jetzt aus dem **Log** (`_left_with` = der letzte `status_after`
> dieses Auftrags); auf einer **Ausscherung** (`at` gesetzt) bleibt der heutige Zustand
> richtig – dort IST der Verbleib die Aussage. Vier Fälle, eine Tabelle, keine Sonderregel.
> **(3) Der Log schrieb das Urteil der BESTÄTIGUNG auf jedes Stück** (§9.5): fällt eines von
> fünf durch, ist die Bestätigung als Ganzes «nicht bestanden» – vier Zeilen waren damit
> falsch, und welches Stück das schlechte war, liess sich aus dem Nachweis nicht mehr lesen.
> Der Halt gehört der Instanz, das Urteil dem Stück.
> Wächter, jeder gegen seine Bug-Form gegengeprüft: `test_a_hold_is_never_a_dead_end`,
> `test_a_hold_is_shown_beside_the_way_forward_not_instead_of_it`,
> `test_a_finished_order_does_not_retell_what_happened_elsewhere`,
> `test_the_verdict_in_the_log_belongs_to_its_own_piece`.
>
> **Audit und Testkampagne – die Regel steht geschrieben, BEVOR sie geprüft wird**
> (`SYSTEM_LOGIC.md` · `TEST_REPORT.md` · `FINDINGS.md`): Die Prosa in dieser Datei
> beschreibt, wie das System **geworden** ist; sie ist kein Massstab, gegen den man testen
> kann. `SYSTEM_LOGIC.md` ist er – die Regeln als **prüfbare Sätze** (vollständige
> Statusliste mit Übergangsmatrix, die drei Auftragszustände samt Ableitung, sechs
> Grundregeln, und eine **Sackgassen-Analyse**: jeder Zustand, in dem ein Stück oder ein
> Auftrag landen kann, mit der Antwort «wie kommt man hier raus?»). Erst danach die Tests –
> andernfalls prüft man den Code gegen sich selbst, und ein systematisch falscher Code
> besteht seine eigenen Tests immer.
> **Die Matrix ist Daten, kein Code** (`tests/matrix.py`, 71 Fälle über sechs Achsen –
> Herkunft · Serialisierung · Menge · Modultyp · Schachtelung bis drei Ebenen ·
> Rückführung): jeder Fall trägt sein **vorher notiertes Soll**; `test_scenarios.py` fährt
> ihn als Wächter, `scripts/scenario_report.py` stellt Soll und Ist nebeneinander. Gefahren
> wird über die **echten** Dienstpfade gegen echtes PostgreSQL – die interessanten Fehler
> entstehen zwischen den Schritten, nicht in einem nachgestellten Zustand.
> **Die Invarianten sind das eigentliche Ergebnis** (`app/services/invariants.py`, 15
> Prüfungen, rein lesend): ein Szenariotest prüft, woran jemand gedacht hat – eine
> Invariante prüft, was **wahr sein muss**. Sie halten über 337 Aufträge · 2620
> Einzelinstanzen · 11 494 Log-Einträge, und ein Gegentest stellt drei Fehlerformen her
> und verlangt, dass sie gemeldet werden (ein Wächter, der nie anschlägt, ist von einem
> kaputten nicht zu unterscheiden). Bemerkenswert dabei: die Fehlerform «zwei offene
> Zugehörigkeiten» liess sich **nicht** herstellen, solange der partielle Unique-Index
> steht – erst nachdem er im Test kurz weicht. Das ist der beste verfügbare Beweis, dass
> er trägt.
> **Ergebnis: kein 🔴.** Zwei 🟠 (**beide inzwischen erledigt**, siehe unten) plus fünf 🟡.
> Dazu ein Befund im **eigenen Netz**: der Aufräumer der Wächter-Suite
> löschte über *ein Stück* und die Instanz dazu und liess Geschwister-Stücke verwaist
> zurück – gefunden von der neuen Invariante, an genau den Daten, die dieser Wächter
> hinterlässt. Behoben.
> **Zwei der drei ersten «Befunde» waren Testfehler**, und das steht so im Bericht: ein
> falsch notiertes Soll (nach der dritten Ebene wartet der oberste Auftrag zu Recht weiter)
> und ein Helfer, der einen leeren Wertesatz automatisch auffüllte. Ein Bericht, der das
> verschweigt, ist wertlos.
> **Ein bekannter Befund kann nicht verrotten** (`Case.open_finding`): die CI wird davon
> nicht rot, aber der Wächter **meldet**, sobald die Abweichung aufhört – dann ist er
> behoben und die Markierung muss weg.
>
> **Zwei Achsen, die beide «aktiv» heissen – und nur EINE ist gemeint** (`services/articles.
> may_create`): Das war der Befund 🟠-1. `is_active` ist der **Soft-Delete** («den Datensatz
> gibt es nicht»), `status` der **fachliche** Zustand (Freigegeben ↔ Inaktiv). Die Freigabe
> prüfte die erste, gemeint war die zweite – und weil die erste im ganzen Prozessbereich
> **nie gesetzt wird**, konnte die Prüfung gar nichts abweisen: ein längst ausser Betrieb
> genommener Artikel erzeugte weiter neue Einzelinstanzen.
> Die Regel lautet jetzt in einem Satz: **nur ein Artikel im Zustand «Freigegeben» erzeugt
> Neues.** Sie sperrt ausschliesslich die Herkunft **Neu** – **Lager bleibt erlaubt**, und
> zwar mit Absicht: sonst würde jedes Stück eines ausgelaufenen Artikels zur Leiche, die
> sich nicht einmal mehr aussondern liesse (S98b). Und sie greift **bei der Freigabe**, nicht
> laufend: ein bereits laufender Auftrag läuft zu Ende, sein Prozess ist eine eingefrorene
> Kopie, und ihn von aussen anzuhalten hiesse, die Vergangenheit umzuschreiben.
> **Zwei Formen derselben Regel** (wie `pick_problem`/`unpickable`): `may_create` gibt den
> **Grund** zurück, statt zu werfen – die Freigabe bricht damit ab (400), die Auswahl-Liste
> sperrt «Neu» und nennt **denselben Satz** (`ArticleOption.create_problem`). Zwei
> Formulierungen wären zwei Massstäbe.
> **Der dauerhafte Schutz ist keine Umbenennung, sondern das Wegnehmen der zweiten Achse.**
> Ein Namensteppich über 92 lebende `is_active`-Stellen in 38 Dateien wäre ein grosser
> Eingriff für ein Problem, das genau **zwei** Modelle betrifft (Artikel · Einzelinstanz),
> und der Rest davon ist ein völlig legitimer Soft-Delete. Also: am **Artikel** ist
> `is_active` nicht mehr von aussen setzbar (kein Feld in `ArticleUpdate` – es gibt genau
> einen Weg ausser Betrieb, und das ist `status`); an der **Einzelinstanz** wird es nirgends
> gesetzt, ihre Filter sind Gurt neben dem Hosenträger; und die eine Frage heisst nach der
> **Regel** (`may_create`) statt nach einem Zustand – ein `is_article_active` hätte dieselbe
> Falle nur eine Ebene weiter aufgestellt. Wächter:
> `test_a_record_goes_out_of_service_on_exactly_one_axis`.
>
> **Und der Fix förderte den schwereren Fehler zutage: der Artikel-Status gab es in ZWEI
> SPRACHEN** (`models/article.py`). Migration `107` hatte die **Daten** und den
> **Server**-Default auf die deutsche Liste gezogen (`freigegeben`/`inaktiv`) – der
> **ORM**-Default im Modell blieb auf `"released"` stehen, und der **gewinnt**: jede
> Artikel-Zeile, die ohne ausdrücklichen Status entsteht, trug wieder ein Wort, das die
> Statusliste nicht kennt. **Folgenlos, solange es keinen Leser gab** – `create_article`
> setzt den Status ausdrücklich, sonst fragte im aktiven Bereich niemand. `may_create` ist
> der erste, der die Frage wirklich beantworten muss, und beantwortete sie für jede so
> entstandene Zeile mit **nein**; gegen eine frisch aus den Migrationen gebaute Datenbank
> fiel damit sofort die halbe Suite aus. **Ehrlich eingegrenzt:** zur Datenverfälschung
> kam es nie – `main._ARTICLE_STATUS_FIXES` zieht bei jedem Start `released`/`draft` auf
> `freigegeben` nach; der Schaden war das **Fenster** bis zum nächsten Neustart. Dass es
> diesen Reparatur-Lauf gibt, macht den Befund kleiner; dass es ihn **braucht**, ist selbst
> das Symptom. Der Standardwert kommt jetzt aus dem **Katalog**,
> und ORM- wie Server-Default stehen in **derselben Zeile** – sie können nicht mehr
> getrennt veralten. In den **abgeschalteten** Bereichen (`ai`, `selling`) steht die alte
> Sprache noch: heute nicht importierbar, aber beim Wiedereinschalten mitzuziehen
> (`FINDINGS.md`, Fund 4). Wächter `test_the_article_status_has_exactly_one_vocabulary`
> prüft die **Quelle** des Standardwerts, nicht seinen heutigen Wert – ein Literal ist
> genau die Form, die beim nächsten Umbenennen stehen bleibt.
>
> **Der Abbruch IST eine Abweichung – es gibt keine Abbruch-Funktion** (SYSTEM_LOGIC §4.4,
> Befund 🟠-3): «Auftrag abbrechen» war der einzige Zustand ohne Ausgang. Gebaut wurde
> trotzdem nichts – **weil der Weg schon da war**: man legt einen ganz gewöhnlichen Auftrag
> an, der **alle** Stücke greift, und **kappt die Rückführung**. Das ist der bessere Weg,
> nicht bloss der billigere: ein Knopf «abbrechen» beantwortet nicht, was mit den Stücken
> geschieht – die Abweichung erzwingt genau diese Entscheidung, und sie ist im Log
> nachvollziehbar. `Abgebrochen` fällt danach **ohne eine Zeile Code** aus `_derive`:
> unterwegs 0 · verliehen 0 · angekommen 0. Geprüft, nicht behauptet – S57 (Abbruch über
> die Abweichung), **S58** (derselbe Weg beim **obersten** Auftrag, also ohne Elternteil)
> und S59 (ein liegengelassener Abzweig klemmt den Eltern nicht dauerhaft: wer ihn
> abbricht, gibt ihn frei). Damit hat **jeder** Zustand der Sackgassen-Analyse einen
> Ausgang; offen bleibt nur ein **latentes** Risiko (R7): ein künftiges Modul mit
> `units_may_leave = False` würde diesen Weg schliessen – heute gibt es keines.
>
> **`no-unused-vars` ist eingeschaltet** (`frontend/.eslintrc.json`, läuft in der CI): ein
> Knopf, der einen Zustand setzt, den niemand liest, war nicht auffindbar – `next/core-web-
> vitals` prüft ungenutzte Variablen nicht, und eine tote `useState`-Destrukturierung ist
> genau diese Form. Die Regel fand **46** Leichen aus dem Neuaufbau, darunter zwei
> API-Abfragen für einen Wert, den niemand liest (`settings` im Feed), eine ungenutzte
> Funktion, eine ganze Komponente (`CartButton`) – und den **Deaktivieren-Knopf am Artikel**,
> der denselben toten Zustand setzt (sein Dialog ist mit dem Neuaufbau entfallen; bewusst
> nur gemeldet, weil Deaktivieren endgültig ist). `_TYPE_MODELS` behauptet kein `document`
> mehr (abgeschaltetes Modul) – die Spalte bleibt aber im **Nummernraum**, sonst vergäbe
> `setval` eine Alt-Nummer ein zweites Mal.
> Wächter für das Fundament: `tests/test_frontend_mirrors.py`.
> Rollback-Punkt: Git-Tag `rollback/basis-20260806`, DB-Dump via `scripts/dump-db.sh`.
>
> **Testrunde 13.8.2026 (#717–#724) – drei Regeln in den RAHMEN, zwei Bauteile weniger.**
> **(1) Ein abgeschlossenes Modul zeigt lückenlos, was in ihm passiert ist** (#717,
> PROCESS_CORE §9.7): **eine** Ableitung über den Ereignis-Log (`services/record.py` →
> `GET …/steps/{id}/record`) und **eine** Komponente (`step-record.tsx`) – kein Protokoll je
> Modultyp, sonst fehlte die (n+1)-te beim nächsten Typ. Gespeichert wird dafür **nichts**:
> Übergang, Werte, Ziehung und Verbau-Ziel stehen längst da, gefehlt hat die Ansicht.
> **Ein Eintrag ist ein VORGANG, kein Stück** – nach einem «nicht bestanden» wird erneut
> erfasst, und **beides** ist passiert; je Stück zusammengefasst überschriebe die
> Wiederholung ausgerechnet die durchgefallene Messung. Eine Erfassung **ohne** folgendes
> `step` IST der Halt und steht darum ebenfalls da.
> **«Nicht gezogen» kommt aus der ZIEHUNG, nicht aus einem Vermerk** – das war der eine
> Fund beim Bauen: der Vermerk `sampled: False` am Übergang wird nur von **einem** der
> beiden Wege geschrieben, die ein Stück vorrücken lassen (dem Durchlauf am *nächsten*
> Modul); die ungezogenen Geschwister einer bestätigten Instanz trugen ihn nie. Gelesen
> wird jetzt das `sample`-Ereignis (`sampling.was_drawn`, aus `_drawn_already` **eine**
> Lesestelle geworden). Seitenweise und erst auf Klick, Gesamtzahl daneben.
> **(2) Ein Bild entsteht in der KAMERA, nicht im Dateidialog** (#718/#720): der Upload ist
> **ersatzlos entfernt**. Eine Datei aus der Galerie belegt nichts über *diesen* Vorgang;
> ein Nachweis, der auf beide Arten entstehen kann, ist hinterher keiner – man sieht ihm
> nicht an, welche es war. **Genau eine Aufnahme je Einzelinstanz**, nicht optional
> (`Photo.missing` verlangt genau einen nicht-leeren String – eine *Liste* geht nicht mehr
> durch), neu aufnehmen verwirft die alte. **Kamera und Decoder sind jetzt zwei Bauteile**
> (`components/scan/use-camera.ts` ↔ `use-barcode-scanner.ts`, Naht = der Rückruf `Attach`):
> die Trennung ging sauber, weil der Decoder in **einer** inneren Funktion sass – Strom,
> Linsenwahl (Ultraweitwinkel-Falle), Taschenlampe und Track-Aufräumen mussten nicht
> verdoppelt werden. Die Aufnahme spricht damit dieselbe Bildsprache wie der Scanner
> (Fläche = Kamerabild, milchige Chips darin) **ohne eine Zeile Decoder**.
> **(3) Der Erfassungstyp «Objekt scannen» ist ersatzlos entfernt** (#719) – eine gelöschte
> Datei, sonst nichts; die Registry hat die Vorhersage «ein neuer Typ ist eine neue Datei»
> damit in **beide** Richtungen bestätigt. **Er war zugleich der einzige Nachweis für
> Werkzeug und Prüfmittel**; dass es ihn nicht mehr gibt, steht als bewusst offener Punkt
> in `SYSTEM_LOGIC.md` §5.9 statt als stille Lücke im Code (G3). Der Weg zurück beginnt bei
> der **Modellfrage** (Nutzung ohne Exklusivität – eine Fräse steckt real in zwanzig
> Aufträgen), nicht bei einem Eingabefeld.
> **Ressourcenmodul:** die Stückliste steht **eingerückt unter ihrer Einzelinstanz** (#724 –
> «erst wohin, dann was»; bei mehreren Erzeugnissen ist die Einrückung die einzige Stelle,
> an der die Zugehörigkeit steht) und rechnet auf **deren** Stücke; angeboten wird nur, was
> Sinn ergibt (#723: Plan geht auf → nichts · reicht nicht, Bestand da → «Andere Instanz
> wählen» · gar nichts frei → nur «Nachschub»). Der Erklärtext «2 Stück je Einzelinstanz …»
> ist gelöscht (#722) – «Menge je Stück» als Feldname braucht kein Beispiel.
> Wächter: `tests/test_step_record.py` (jeder gegen seine Bug-Form gegengeprüft),
> `test_frontend_mirrors.py: test_a_picture_is_taken_never_uploaded` ·
> `…_the_object_scan_capture_type_is_gone` · `…_the_camera_is_one_layer_and_the_decoder_another` ·
> `…_the_flow_is_first_where_then_what`.
>
> **Wer vor dem nächsten Modul WARTET, hat den Auftrag nicht verlassen** (gemeldet: die
> Achse hinter einem Abzweigepunkt war eine Haarlinie, obwohl ein Stück sie gegangen ist).
> Der Log schreibt für «Modul passiert» und für «Auftrag an diesem Modul verlassen»
> **denselben** Eintrag (`step`) – `flow._exit_points` las nur den letzten davon und hielt
> damit jedes wartende Stück für ausgetreten; es wurde von `passed` abgezogen, und warteten
> alle, stand die Bilanz auf null. Unterschieden werden die beiden allein durch die
> **Zugehörigkeit** (verlassen = geschlossene Zeile, warten = offene) – die Regel stand
> wörtlich im Docstring, nur nie in der Abfrage.
> **Die eigentliche Lehre ist, warum es still passieren konnte.** Die Invariante «wo etwas
> steht, ist etwas gewesen» prüft die Zeichnung gegen die **Positionen** – und in einem
> **abgeschlossenen** Auftrag ist jede Zugehörigkeit geschlossen, keine Achsenkante hat
> mehr Mitglieder, also fällt dort eine falsche Haarlinie durch jedes Netz. Neu prüft
> `flow._verify_walked` gegen den **Log**: *wer ein Modul passiert hat, ist die Kante davor
> gegangen* (ausgenommen, wer erst dort eingetreten ist – `_tally.entered`). Zwei
> Herleitungen derselben Aussage: die Bilanz **muss** rechnen (ein Bypass ist eine
> Differenz), diese hier kann nur zählen; weichen sie ab, steht es als Problem da statt
> still gezeichnet zu werden. Dafür bleibt `tally.passed` **roh** – die Korrektur um die
> Austritte lebt in einer eigenen Grösse (`onward`), sonst prüfte die Invariante die
> Rechnung gegen sich selbst.
> Wächter: `tests/test_flow_graph.py: test_a_waiting_piece_is_not_an_exit` (gegen die
> Bug-Form gegengeprüft) · `…_the_line_strength_is_checked_against_the_log_not_only_the_positions`.

> **Das vierte Modul ist «Bewegen» — und darunter liegt der ORT** (PROCESS_CORE §9.8,
> Migration `111`). Der Vorgängerversuch wurde zurückgerollt, und der Grund steht im
> Revert: nicht die Ortslogik war falsch, sondern ihr **Umfang** — Ortsfundament, Modul,
> Bauteil «Vergabe», Kanal «Plattform» und Frachtführer-Adapter in einem Deploy, mit drei
> Migrationen. Diesmal nur das Fundament und das Modul.
> **Der Ort ist ein ZEIGER, kein Zustand**: `instance_units.place_object_id`, die
> Objektnummer des Halters. Er ändert nie den Status und nie die Zugehörigkeit — genau
> deshalb muss keine andere Regel im System von diesem Modul wissen (Robustheit
> konstruktiv statt geprüft). **Kein Typfeld daneben**: Objektnummern sind eindeutig, der
> Typ ist ableitbar; der Vorgänger führte `location_type` daneben und musste einen
> entfallenen Wert tolerant zu `None` auflösen, weil er sonst jede Ansicht zerlegte.
> **Gehalten wird die Einzelinstanz, Halter ist eine Objektnummer** — die Asymmetrie ist
> die einzig mögliche Aussage: eine Einzelinstanz zieht bewusst keine Objektnummer, es
> kann für sie gar kein Etikett geben. Halter ist damit **Instanz** (Regal, Behälter,
> LKW), **Benutzer** oder **Unternehmen**; kein neuer Datensatztyp, keine Whitelist.
> **Der Ort hängt am STÜCK**, nicht an der Gruppe: zwei Schrauben derselben Charge dürfen
> an zwei Orten liegen. Genau das konnte der Vorgänger nicht (Standort→Menge-Map an der
> Instanz **plus** denormalisierter Skalar, mit Umschalter dazwischen). **`NULL` ist
> regulär** – ein frisch erzeugtes Stück liegt nirgends.
> **Eine Spalte statt einer append-only Tabelle**, weil die Vergangenheit schon woanders
> steht: jede Bewegung läuft über `confirm_step` und schreibt Herkunft, Ziel und
> Transportart in `process_events`. *Die Grenze ist benannt* – ein späteres Ablegen
> **ausserhalb** eines Auftrags hätte dort keine Historie; dann kommt sie dort dazu.
> **Die eine Regel des sonst dummen Feldes: keine Zyklen** – verhindert beim Schreiben
> (`places.assert_placeable`), gekappt beim Lesen (`seen` + `MAX_STATIONS`); zwei Netze,
> weil das erste Altbestand nicht sieht.
> **Die Kette** (`Schraube › Behälter › Regal › Werk Nord`) endet beim Halter mit
> **Anschrift**. Aufgelöst wird sie **je Halter, nie je Stück** (`chains_for`,
> stufenweise in Batches): 60 Schrauben in einem Regal sind EINE Kette — je Zeile wären
> es 60 × Tiefe, die N+1-Falle, an der die Ortsanzeige des Vorgängers hing. **Gemessen,
> nicht behauptet**: der Wächter zählt die Abfragen (11 statt 660). In der Zeile steht
> der unmittelbare Halter, die volle Kette im **Hover** – ausgeschrieben wäre sie bei
> sechzig Zeilen eine Wand aus Text.
> **Das Ziel ist optional, und das ist eine Aussage**: definiert → der Scan ist die
> **Verifikation** dagegen (serverseitig, nicht nur im Dialog); offen → er ist die
> **Wahl**. Ein offenes Ziel, das aussieht wie eine Lücke, läse sich als Fehler – die
> Karte sagt darum «wird beim Ausführen gescannt».
> **Ware zuerst, Ziel zuletzt** (Standard jedes WMS beim Ein-/Umlagern): der Ziel-Scan ist
> die **Quittung der Ablage** und passiert zuletzt, weil das Hinlegen zuletzt passiert.
> Zuerst gescannt wäre er eine Absichtserklärung. Kein neuer Mechanismus – ein Schritt
> mehr in der bestehenden Scan-Sequenz; der Sammel-Scan quittiert das Ziel **einmal**.
> **Die Transportart gehört zur LAUFZEIT** (beim Modellieren steht nicht fest, ob das
> Stück nebenan liegt oder in Werk Nord). Nur **Manuell** ist wirksam; **Paket** und
> **Fracht** stehen sichtbar-gesperrt da, mit Grund im Hover – die eine bewusste
> Abweichung von «ein Knopf, der nie etwas tun kann, ist kein Angebot», weil er hier keine
> tote Funktion zeigt, sondern die Roadmap. Tragfähig macht sie zweierlei: die Liste nennt
> **alles mit seiner Verfügbarkeit** (Freischalten = ein Wert, kein Umbau), und **der
> Server weist einen gesperrten Kanal ab** – wäre die Sperre nur ausgegraut, wäre sie eine
> Bitte. **Die Transportliste ist zugleich das Bit** «bewegt dieses Modul?»: leer bei
> jedem anderen Typ, also braucht die Oberfläche keine Fallunterscheidung nach dem
> Modultyp (dieselbe Bauart wie `needs`).
> Wächter: `tests/test_move_module.py` (10 Prüfungen, **jede gegen ihre Bug-Form
> gegengeprüft**) + drei in `test_frontend_mirrors.py`.

> **Testnotizen-Runde 46 (#725–#733) — drei Notizen, EINE Ursache; und die Journey
> lernt den zweiten Eintrittspunkt.**
> **(1) Ein freier Scan-Schritt hatte keine Vorschlagsquelle** (#730/#731/#732). Gemessen,
> nicht vermutet: ein **Verifikations**-Schritt liefert bei «00825» sehr wohl einen
> Vorschlag (`offersFor` leitet ihn aus `expected` ab); ein **freier** Lookup liefert
> **null** — seine Quelle (`ScanStep.suggest`) ist eine Angabe je Aufrufer, und die hatte
> genau einer: der Feed. Genau daraus kamen alle drei Meldungen. #731 sah nur deshalb wie
> ein Instanz-Scan aus, weil im damaligen Build der **erste** Schritt der freie Ortsscan
> war («Wo stehen Sie?») – der Knopf hiess anders als das, was der Dialog fragte.
> Die Quelle ist jetzt eine **Halter-Suche** im Backend (`places.search`,
> `GET /erp/places?search=`): Objektnummer-Teilstring **oder** Name, über Instanz ·
> Benutzer · Unternehmen. **Angeboten wird nur, was auch Halter sein kann** — ein Artikel
> trägt eine Objektnummer, ist aber eine Gattung; ihn vorzuschlagen hiesse, eine Wahl
> anzubieten, die `assert_placeable` danach abweist. Drei Aufrufstellen, eine Antwort:
> das Zielfeld im Editor, der Zielort-Scan dort und der zur Laufzeit.
> **Das Zielfeld ist jetzt `SearchSelect`** — dieselbe Komponente wie jede Referenz im
> Haus, um ein **optionales `search`** erweitert: ohne es bleibt alles wie bisher
> (Optionen fertig, Filter im Browser), mit ihm kommen sie vom Server und `options` trägt
> nur noch die gewählte. Dieselbe Bauart wie beim Scanner (`candidates` ↔ `suggest`); ein
> zweites Auswahlfeld «mit Suche» wäre der erste Weg, der beim nächsten Feld ausläuft.
> **(2) Wer am MODUL eintritt, steht nicht am ANFANG des Prozesses** (#729 — die
> Logikfrage, und der Nutzer hatte recht). Ein Verbrauchsmodul holt sein Material beim
> Erreichen; der Auftrag, in dem es entstand, erschien darum als **vorgelagerter Auftrag**
> über dem Start — dort, wo die Herkunft des **Subjekts** steht. Nachgestellt und
> reproduziert. Die Unterscheidung musste nicht erfunden werden, sie stand längst im Log:
> der `start`-Eintrag trägt am Modul-Eintritt die Modul-`id`, am Start-Objekt nicht
> (`_enter_at_step`). Dieselbe Bedingung liest das Prozessbild seit jeher (`flow._tally`
> zählt nur `step_id IS NULL` als «gestartet») — die Journey las sie nicht.
> `journey._walked_the_process` ist jetzt die eine Stelle, und die **Gegenprobe steht
> daneben**: wer sein Subjekt aus einem anderen Auftrag greift, nennt ihn weiterhin. Ohne
> sie wäre die Korrektur von «die Journey abgeschaltet» nicht zu unterscheiden.
> **(3) Ein Zustand, der sich nicht ändert, ist keine Aussage** (#726). Im Modul-Protokoll
> stand je Eintrag der Nachher-Zustand — bei einem **Durchläufer** (Datenerfassung,
> Bewegen: `Im Prozess` → `Im Prozess`) in jeder Zeile dasselbe Wort. *Der erste Anlauf
> war zu grob und wurde von zwei bestehenden Wächtern gemeldet:* `status_after` trug
> zugleich «ist vorgerückt», und es wegzulassen machte «vorgerückt» und «nichts geändert»
> ununterscheidbar. Jetzt liefert der Dienst **beide** Zustände unverfälscht, und die
> Anzeige bildet die Differenz — sie fragt die **Daten**, nicht den Modultyp.
> **(4) Ein Modul, das an die Reihe kommt, klappt auf** (#727). `defaultOpen` war ein
> reiner `useState`-Startwert: wer den Auftrag öffnete, **bevor** die Stücke ankamen,
> bekam `false` — und dabei blieb es, auch als das Modul dran war. Der Effekt hängt an
> `defaultOpen` und nur daran: er läuft beim **Wechsel** des aktiven Moduls, nicht bei
> jedem Rendern; wer selbst zuklappt, bleibt zugeklappt.
> **(5) Kleineres, jedes an genau einer Stelle:** der Auftrags-Knopf am Stück trägt das
> **reguläre Auftragssymbol** (#728, `TYPE_META.order` — was daraus wird, entscheidet die
> Auswahl, nicht das Symbol); «Menge je Stück» heisst **«Menge je Einzelinstanz»** (#725 —
> das ist das Arbeitsobjekt des Systems); der Knopf des Bewegen-Moduls heisst **«Bewegung
> bestätigen»** (#733 — gescannt ist zu diesem Zeitpunkt längst, was der Knopf auslöst,
> ist die Buchung der Ablage).
> Wächter: `test_move_module.test_holders_are_searchable_by_number_and_by_name`,
> `test_consumption_module.test_a_component_does_not_become_a_preceding_order` +
> `…_the_real_journey_survives`, `test_step_record.test_a_pass_through_module_shows_no_
> state_but_an_exit_does`, dazu fünf in `test_frontend_mirrors.py` — jeder gegen seine
> Bug-Form gegengeprüft.

> **Material am richtigen Ort — der Ort wird zur VORAUSSETZUNG, und nur dort**
> (PROCESS_CORE §9.6/§9.8, Migration `112`). Bis hierher war `instance_units.place_*` ein
> Zeiger, den **keine Regel liest**. Sobald ein Modul Material an einem bestimmten Ort
> *braucht*, wird er zur Voraussetzung — und das ist **dieselbe Frage, die längst
> beantwortet ist**: der Verbrauch meldet fehlende **Menge** als `StepNeed`
> («Artikel · gebraucht · verfügbar», Nichtverfügbarkeit ist kein Zustand). **«Am
> falschen Ort» ist dieselbe Aussage, eine Spalte weiter**: *davon hier*. Kein neuer
> Status, kein Pausenwert, keine Wartelogik.
> **Wo das Material liegen muss, ist ABGELEITET** (`Module.material_place = AT_PRODUCT`
> → `consumption.required_place`): dort, wo das **Produkt** liegt. Ein eigenes Ortsfeld am
> Verbrauchsmodul wäre eine zweite Ortsangabe neben dem Ziel des Bewegen-Moduls, und zwei
> können sich widersprechen; so entsteht die Anforderung von selbst und niemand
> modelliert sie. **«Am Ort» heisst in der KETTE**, nicht «identische Nummer»: die
> Schraube in der Kiste, die auf Werkbank 5 steht, **ist** auf Werkbank 5
> (`places.at_holder`) — die naive Lesart wäre in der Praxis fast immer falsch. Und **wo
> nichts steht, wird nichts verlangt**: liegen die Produkte nirgends oder an
> *verschiedenen* Orten, gibt es keine Anforderung — ohne diese Regel hielte die Änderung
> jeden bestehenden Ablauf an.
> **Der Weg dorthin ist ein ganz gewöhnlicher Auftrag** mit einem Bewegen-Modul auf den
> Arbeitsort — **vorgewählt angeboten, nie automatisch angelegt** (dieselbe Mechanik wie
> §4.5 bei «nicht bestanden»; das Vorgängersystem hatte die Automatik gebaut und wieder
> abgeschaltet). **Und die Sperre fällt heraus, statt gebaut zu werden**: solange der
> Transport läuft, ist das Stück `Im Prozess` und damit gar nicht greifbar; danach ist es
> frei **und** liegt richtig. Drei Wege an der Zeile, alle drei gibt es schon: *andere
> Instanz wählen* · *holen lassen* · *Nachschub*.
> **Zwei Arten von Halter — die Genauigkeit ist die der QUELLE** (`place_object_id` ↔
> `place_unit_id`, `CHECK` = höchstens eines): was man **scannt**, ist ein Etikett, und
> ein Etikett hat die **Instanz**; beim **Verbauen** kennt das Modul das **Stück** genau,
> und diese Genauigkeit wegzuwerfen wäre eine erfundene Unschärfe («in 100000123» wären
> bei einer Charge 600 Getriebe — eine Gruppe, kein Ort). Weil das Stück auf den **Träger**
> zeigt und nicht auf dessen Anschrift, **wandert es mit**, wenn das Getriebe bewegt wird.
> *Nicht die Genealogie:* der Log sagt **worin** verbaut wurde (`payload.into`,
> unveränderlich, überlebt die Demontage), die Spalte sagt **wo es jetzt liegt** und wird
> beim Ausbau geräumt — dass beide auseinanderlaufen können, ist der Beweis, dass es zwei
> Fragen sind.
> **Wer zur Historie zählt, verliert seinen Ort** (`Status.stock` heisst wörtlich «liegt
> im Regal»): **Verschrottet** → keiner (der Status IST die Wo-Antwort), **Verbaut** →
> sein Träger, **Gesperrt** → **bleibt** (es liegt im Regal, nur unbenutzbar). Die Regel
> hängt am **Status** und steht an der einen Stelle, an der ein Status geschrieben wird
> (`process._pass`) — jedes künftige Modul erbt sie ohne eine Zeile.
> **`places` bleibt die EINE Schreibstelle** (`place` · `place_in` · `forget`,
> Quelltext-Wächter); die Kette läuft über beide Halter-Arten in **einem** Lauf
> (`_walk`, batchweise je Halter — 60 Schrauben in einem Regal sind eine Kette).
> Wächter: `tests/test_material_place.py` (11 Prüfungen, **jede gegen ihre Bug-Form
> gegengeprüft**) + vier in `test_frontend_mirrors.py`. Gemessen, nicht behauptet: die
> ganze Szene end-to-end über die echten Dienstpfade (40 verfügbar/0 hier → Transport →
> 12 hier → verbaut, Schraube liegt in `…-1` auf Werkbank 5).

> **Der Artikel-Lebenszyklus: «Inaktiv» ist ein ZUSTAND, kein Ende — und Ersetzen ist eine
> Angabe am NACHFOLGER** (PROCESS_CORE §5.5). Der Knopf «Deaktivieren / ersetzen» war eine
> **Attrappe**: er rief `setDialog('deactivate')`, aber den Dialog gab es seit dem
> Basis-Neuaufbau nicht mehr — er tat also nichts, und ein `eslint-disable` schleuste den
> toten Zustand am Wächter vorbei. «Ersetzen» war überhaupt nie gebaut.
> **Die Behauptung daneben war ebenfalls falsch:** «Inaktiv ist endgültig – kein
> Reaktivieren» widerspricht der Statusliste (`Status.terminal` gibt es **nur** auf der
> Stück-Achse), und daraus folgte, dass es keine Gegenaktion gab: ein versehentlich
> stillgelegter Artikel war für immer verloren, der einzige Ausweg hiess «dieselbe Sache
> noch einmal anlegen» – eine zweite Nummer für ein Ding. Damals wurde daraus **ein Knopf
> in zwei Richtungen**; *mit #773 ist auch der entfallen – siehe unten.*
> **Die Wirkung ist EINE und steht an EINER Stelle** (`articles.may_create`): ausser Betrieb
> heisst **erzeugt nichts Neues**. Alles andere bleibt – bestehende Stücke laufen weiter,
> laufende Aufträge zu Ende (eingefrorene Kopie), «ab Lager» bleibt erlaubt.
> **Die Kaskade wird GEMELDET, nicht erzwungen** (`services/bom.py`): wer einen ausser
> Betrieb genommenen Artikel verbaut, bleibt erzeugbar, solange Restbestand da ist – und
> **sagt es selbst**, transitiv über beliebig viele Stufen, mit dem **Weg** dorthin und dem
> **Nachfolger**, falls es einen gibt. Die Kaskade entsteht beim **Lesen** und reicht so
> weit, wie jemand hinschaut; markiert oder gespeichert wird nichts. Ein Erzwingen risse ein
> einzelnes ausgelaufenes Teil einen ganzen Baum mit, und niemand könnte die Restbestände
> aufbrauchen. Dieselbe Ableitung beantwortet die Gegenrichtung – **wer verbaut mich?** –,
> also «was mache ich kaputt, wenn ich das hier abschalte»: sie steht **am Datensatz, nicht
> in einem Dialog** (ein Dialog zeigt sie einmal, dem, der klickt), und **darum gibt es zur
> Statusaktion keine Rückfrage**. Gelesen werden nur die **Artikel-Vorlagen**, nie die
> eingefrorenen Kopien laufender Aufträge; gefiltert wird in der **Datenbank**
> (JSONB-Containment `@>`) – im Python nachzufiltern hiesse, für jede Artikel-Anzeige
> sämtliche Vorlagen des Hauses zu laden. Gemessen: **8 Abfragen** für ein dreistufiges Detail.
> **Ersetzen steht am Nachfolger, weil es genau EINEN Moment hat**
> (`ArticleCreate.replaces_object_id`): man legt den neuen Artikel an und sagt dabei,
> welchen er ablöst. Ein Feld am Vorgänger wäre jederzeit änderbar und damit eine zweite
> Wahrheit über dieselbe Kette. **Und es NIMMT ausser Betrieb** – keine zusätzliche Wirkung,
> sondern die Bedeutung; zwei Klicks wären zwei Gelegenheiten, den zweiten zu vergessen.
> Drei Ablehnungen mit Grund im Satz: sich selbst · bereits ersetzt (**unter Nennung** des
> bestehenden Nachfolgers) · Kreis. Die Kreisprüfung fragt **vorwärts ab dem Nachfolger** –
> die Kette des Vorgängers ist definitionsgemäss leer, dort zu suchen träfe nie zu (im
> Gegentest gefunden). Die Gegenrichtung «wen löse ich ab?» ist eine **Abfrage, keine zweite
> Spalte**.
> **Dargestellt als schmaler Streifen über der Spezifikation** – Reihe · wird verbaut in ·
> gemeldete Lücken, je eine Zeile mit Versalien-Mikro-Label und Haarlinie: nicht zu
> prominent, aber ohne Klick sichtbar. Im **Anlage-Modus** steht an derselben Stelle die
> Auswahl «Ersetzt Artikel» – dieselbe Frage, nur vorher. Gemessen in Chromium: 1440 · 1024 ·
> 375 px, **0 px** waagrechter Überlauf; innen enger als aussen (`rowGap 3` ↔ `gap 11`),
> damit eine umgebrochene Zeile auf dem Telefon nicht wie eine neue Auskunft aussieht.
> **Nebenbei entfallen:** `lifecycle.ensure_mutable` (null Aufrufer, verglich mit dem
> abgeschafften `"draft"` – sie hätte **jeden** Datensatz für gesperrt gehalten, sobald sie
> jemand gerufen hätte) und drei tote Props am Artikel-Fenster (`suppliers`, `onCancel`,
> `dialog`); `onRefresh` hat jetzt eine echte Aufgabe – eine Ersetzung ändert **zwei**
> Datensätze.
> Wächter: `tests/test_article_lifecycle.py` (13 Prüfungen, **jede gegen ihre Bug-Form
> gegengeprüft**). Gemessen, nicht behauptet: die ganze Szene end-to-end über die echten
> Router-Pfade (Maschine › Getriebe › Schraube, 20/20).

> **Testnotizen #734–#740 — «nichts» ist eine Wahl, ein Referenzfeld für alle, und die
> Auswahl fragt die richtige Frage.** Sieben Notizen, drei Themen.
> **(1) «Kein Ziel» stand an DREI Stellen und war an keiner wählbar** (#734/#735/#736):
> ein erklärender Platzhalter («leer lassen für …»), ein Erklärsatz darunter und ein
> X-Knopf daneben, mit dem man eine getroffene Wahl wieder wegnimmt. Keine davon ist die
> **Liste**, in der man wählt. `SearchSelect.emptyOption` führt sie jetzt als erste Zeile
> mit dem Wert `''`, und ein leeres Feld **zeigt sie an** statt eines Platzhalters – die
> getroffene Entscheidung steht da, nicht ihr Fehlen. Ein generisches Bauteil-Feature,
> kein Sonderfall des Bewegen-Moduls: jedes Referenzfeld, bei dem «nichts» gültig ist,
> erbt es (und der «Vorgänger entfernen»-Knopf am Artikel ist damit ebenfalls entfallen).
> **(2) Das Scan-Label nennt die SORTE, die Nummer hängt der Scanner an** (#737 —
> «Instanz 100000825 100000825 scannen»). Die Regel steht seit #145 im Haus
> (`objectCodes.prompt` setzt `expected` hinter das Label); drei Aufrufstellen schrieben
> sie trotzdem selbst hinein. Sie ist jetzt am **Typ** dokumentiert (`ScanStep.label`) und
> als Wächter formuliert: **kein** Scan-Label darf eine Objektnummer bauen. *Der erste
> Wächter dafür war zu eng (`^label:`) und liess die Bug-Form durch – die Zeile war ein
> einzeiliges Objektliteral; gemessen, nachgeschärft und gegen die Bug-Form gegengeprüft.*
> **(3) EIN Referenzfeld, überall** (#738, `components/erp/object-select.tsx`): «welchen
> Datensatz meinst du?» gab es in **vier** Bauarten – ein Auswahlfeld mit Server-Suche,
> eines mit fertigen Optionen, ein natives `<select>` über **alle** Artikel des Hauses
> und den Scanner mit eigener Suche. Wer «100000743» tippte, fand je nach Stelle etwas
> oder nichts. `ObjectSelect` ist **auf** `SearchSelect` gebaut (kein zweites Auswahlfeld
> daneben) und trägt die **Kamera im Feld**: tippen sucht, scannen trifft – beides führt
> zur selben Wahl, und der Scanner bekommt dieselbe Suche (`suggest`), damit auch dort
> eine Teileingabe etwas findet. *Der Scanner zuerst und die Eingabe darunter wäre am Band
> richtig und am Schreibtisch ein Umweg; umgekehrt genauso – darum nebeneinander.*
> **Die Suchbedingung selbst ist EINE** (`services/lookup.matches` – Nummer-Teilstring
> ODER Name): sie stand dreimal ausgeschrieben, und an der vierten Stelle – der
> Artikel-Suche – trug sie nur den Namen. **Kein generischer «suche irgendwas»-Endpunkt**:
> was eine Stelle anbieten darf, ist eine fachliche Frage (`places.search` liefert
> bewusst keine Artikel, weil `assert_placeable` sie danach abwiese). **Gemessen:** ein
> Auftragsentwurf bei 1151 Artikeln lud 300 Zeilen und rendete 300 `<option>`; jetzt
> höchstens 20, und die Objektnummer-Suche trifft überhaupt erst.
> **(4) Die Stück-Auswahl fragt die richtige Frage** (#739): sie schlug **verbaute**
> Stücke vor. Kein Zielkonflikt – der Katalog führt seit jeher **zwei** Antworten, und die
> Auswahl las die falsche: *«gibt es einen Weg zurück?»* (`Status.terminal` – Verbaut:
> **ja**, das Greifen IST der Ausbau) und *«liegt es im Regal?»* (`Status.stock` –
> Verbaut: **nein**, es steckt in einem anderen). Die Farbe ist eine **dritte** Frage und
> bleibt grün. `UnitOption` trägt darum beide (`available` · `in_stock`), und die
> Ableitung wohnt im Katalog (`statuses.IN_STOCK_UNIT_STATUSES`), nicht im Endpunkt – ein
> neuer Zustand gehört ihr automatisch an oder nicht. Verbautes verschwindet **nicht** aus
> der Liste; es steht in seiner Zustandsgruppe und nennt im Hover, was der Klick bedeutet.
> **(5) Und sie skaliert** (#740, `UnitChoices`, Migration `113`): bei zehntausend
> Schrauben war die flache Liste an **drei** Stellen falsch. Die **Vorauswahl** kam aus
> einer bei 300 gekappten Seite – sind die ersten Stücke verbaut, findet die Oberfläche
> **nichts**, obwohl freie da sind; sie kommt jetzt vom Server (`preselect`), denn FIFO ist
> eine Regel, keine Anzeige. Die **Zähler** kamen aus derselben Seite («300», wo
> fünfzigtausend liegen) und kommen jetzt aus einem Aggregat über den ganzen Artikel. Die
> **Herkunfts-Map** las **jede** offene Zugehörigkeit des Systems, um bei einer Seite
> nachzuschlagen – die schwerste Stelle, und die einzige, die bei kleinen Datenmengen
> unauffällig bleibt. Dazu Suche, Zustandsgruppen und Blättern.
> **Die Stücknummer wird gelesen, wie sie gebaut ist** (`instances.unit_number_matches`):
> «-7» meint den **Suffix**, «00123» die Instanz, «100000123-7» beides. Ohne die Trennung
> träfe «9» jede Instanz mit einer 9 in der Nummer – also fast alle.
> **Gescannt wird die INSTANZ, nie das Stück**: eine Einzelinstanz zieht bewusst keine
> Objektnummer, es kann für sie gar kein Etikett geben. Der Treffer setzt die Suche; die
> Stücke der Instanz stehen dann untereinander. Das ist keine Einschränkung, sondern die
> Einzelinstanz-Regel – und steht als Satz im Code, damit es niemand «nachrüstet».
> **Gemessen, nicht behauptet:** 50 000 Einzelinstanzen eines Artikels → **5 Abfragen**
> und ~100 ms je Seite; die Vorauswahl fällt mit dem Index von **15,3 auf 1,2 ms**
> (Migration `113` + Lifespan-Netz, beides gegen echtes PostgreSQL vierfach verifiziert:
> von null · idempotent · downgrade · über das Netz). Die neue Zeile in Chromium bei
> 1440 · 1180 · 1024 · 834 · 375 px: **0 px** waagrechter Überlauf.
> Wächter: `tests/test_unit_choices.py` (9 Prüfungen, **jede gegen ihre Bug-Form
> gegengeprüft** – eine davon war stumpf und musste nachgeschärft werden) + vier in
> `test_frontend_mirrors.py`.

> **Ein Bedienelement mit zwei Eingängen – und der Dialog ist sichtbar dasselbe Feld,
> nur gross** (`components/erp/object-select.tsx`, `components/scan/scan-dialog.tsx`):
> Zur Debatte stand, das Suchfeld ganz zu streichen und nur noch den Scan-Knopf zu
> zeigen – der Dialog trägt ja selbst eine Eingabe. **Verworfen, und der Grund ist ein
> Befund im Code**: die Trennung existierte längst und liegt an der richtigen Naht – die
> **Ausführung** (Erfassung, Bewegen zur Laufzeit, freier Lookup im Feed) hat schon heute
> kein Feld, dort IST der Scan die Wahl; `ObjectSelect` steht ausschliesslich an
> **Definitions**flächen (Modul-Ziel, Bedarfszeile, «Ersetzt Artikel»). Scan-only hätte
> also nicht zwei Wege zu einem gemacht, sondern die Band-Oberfläche in den Schreibtisch
> gezogen. Dazu drei harte Punkte: das Feld **verschwindet gar nicht** (es ist auch eine
> Anzeige – «100000292 · Regal B» bzw. «Beim Ausführen scannen» muss ohne Öffnen lesbar
> sein), die **Kamera beantwortet eine andere Frage** (ein Artikel ist eine Gattung, und
> eine **Einzelinstanz zieht bewusst keine Objektnummer** – eine scan-first-Welt kann für
> das zentrale Arbeitsobjekt nie vollständig sein), und die **Robustheit ginge rückwärts**
> (heute null Fehlerquellen, danach vier: Erlaubnis · Linse · Licht · Etikett; die Tastatur
> im Dialog ist ein Umweg durch den scheiternden Weg, kein Netz).
> **Die Doppelung war eine andere** – dieselbe Frage in zwei Formensprachen. Beide riefen
> seit #738 dieselbe Suche und lieferten dieselben Treffer; man sah es ihnen nur nicht an.
> Also: **EIN Bedienelement** – die Kamera sitzt am rechten **Innenrand** des Feldes
> (`SearchSelect.action`) und ersetzt dort das Zierzeichen (dass es eine Liste gibt, sagt
> der Klick; eine echte Aktion ist den Platz wert) –, und **drei Träger aus je einer
> Quelle**: der Platzhalter (`scan.LOOKUP_HINT`), die Zeilenform (`fields.OptionRow` –
> buchstäblich dasselbe Bauteil, Nummer tabellarisch, Name gedämpft) und die
> **«nichts»-Zeile** (`ScanStep.emptyOption`; vorher musste man den Dialog schliessen, um
> eine Entscheidung zu treffen, die er selbst anbietet).
> **`objectCodes.prompt` ist damit der Platzhalter, kein Handlungsauftrag mehr**: «scannen»
> war das Einzige, was die beiden Sätze auseinanderhielt, und in einem Textfeld ist das Verb
> falsch – dass gescannt wird, sagen Zielrahmen und Suchstrahl. Die **Sorte** wandert dafür
> aus dem Platzhalter in eine **Beschriftung** über der Leiste (dieselbe Typografie wie
> `fields.Label`): ein Platzhalter verschwindet beim ersten Zeichen, und im Vollbild bliebe
> dann nichts mehr, das sagt, wonach man sucht. Sie trägt denselben milchigen Grund wie
> Eingabe und Vorschläge – hier liegt Text auf einem Foto, «Struktur vor Fläche» setzt eine
> Fläche voraus, die ihn hält; ein Chip im Sinne von #126 ist sie nicht (der stand **neben**
> dem Platzhalter und sagte dasselbe zweimal).
> **Gemessen, nicht behauptet:** 29 Prüfungen in Chromium an den echten Komponenten – Kamera
> innerhalb des Feldes (kein zweiter Knopf, 4 px Luft, Text läuft nicht darunter), Liste zu
> beim Öffnen des Dialogs, Platzhalter Feld == Dialog, Zeilenform hier wie dort,
> «nichts» im Dialog wirkt und schliesst, Verifikation zeigt die erwartete Nummer **genau
> einmal**, Teileingabe schlägt weiterhin vor, **0 px** waagrechter Überlauf bei 1440 · 1024 ·
> 834 · 375 · 320 px. Wächter: `test_the_camera_lives_in_the_field_not_beside_it` ·
> `test_the_dialog_is_the_same_field_only_big` – **acht Bug-Formen gegengeprüft**, jede meldet.

> **Das fünfte Modul ist «Beschaffen» – EIN Tor nach draussen, drei Stufen, und das Modul
> räumt selbst auf** (PROCESS_CORE §9.9, Migration `114`). Es ist die Stelle, an der etwas
> von aussen kommt: gekaufte Ware, eine **Leistung** («Härten»), und – sobald ein Kanal
> dazukommt – auch der **Transport**. Denn Paket und Fracht sind kein Systembegriff: eine
> Sendung zu buchen IST ein Einkauf, und der Tarifvergleich IST ein Angebotsspiegel. Wer
> dafür ein eigenes Modul baute, hätte den Einkauf ein zweites Mal gebaut; Shippo ist damit
> ein **Offerten-Lieferant**, kein Konzept.
> **Es erzeugt keine Einzelinstanzen – und darum taucht eine Leistung nie im Bestand auf.**
> Stücke entstehen bei der Freigabe eines Erzeugungsauftrags, sonst nirgends. Das ist keine
> Regel, die dieses Modul einhält, sondern eine, die es gar nicht brechen kann: es legt
> nichts an. «Härten» steht auf dem Beleg und sonst nirgends – es braucht kein Feld, das
> einen Artikel aus dem Bestand ausschliesst.
> **Die Stufen gehören dem BELEG, nicht dem Stück** (`Anfrage → Bestellung → Wareneingang`):
> die Einzelinstanz steht von der Anfrage bis zum Wareneingang durchgehend auf `Im Prozess` –
> sie wartet, sie ändert sich nicht. «Angefragt» oder «Bestellt» an ihr wären Zustände, die
> gar keine Aussage über das Material sind (und in der Statusliste, in FIFO und im Bestand
> beantwortet werden müssten). Der Beleg ist damit eine ganz gewöhnliche Fachzeile **ohne
> eigene Objektnummer** (`purchases`), wie jede andere im Prozess.
> **Drei Stufen, weil drei Dinge unumkehrbar sind** – nichts zugesagt · zugesagt · erfüllt.
> «Preis steht» ist keine vierte: das ist der **Inhalt** der Anfrage, kein anderer Zustand
> der Welt. Und sie erscheinen **immer**, ob im Webshop gekauft oder beim Lieferanten
> bestellt wird; der Unterschied ist allein, **wer den Preis einträgt** (du oder er), nicht
> was passiert. Ein «Webshop-Modus» wäre derselbe Ablauf ein zweites Mal.
> **Mehrere Lieferanten sind eine LISTE, kein zweiter Mechanismus** (`config.suppliers`):
> die Definition sagt, bei wem bestellt werden **darf**, die Ausführung, bei wem bestellt
> **wurde** – zwei verschiedene Fragen. Je Zeile ein Preis und eine Lieferfrist
> (`purchases.quotes`); der Angebotsspiegel des Einkaufs und der Tarifvergleich des
> Transports sind dieselbe Zeile. **Ein Lieferant füllt ausschliesslich SEINE Zeile**, und
> fremde Preise sind kein Nebeneffekt einer Ansicht: gefiltert wird beim **Aufbau der
> Antwort**, nicht in der Oberfläche.
> **Ein Modul räumt selbst auf – die neue Rahmenregel.** Jede Zusage nach aussen hat ihre
> Gegenhandlung an derselben Stelle, und es ist **eine**: was `revoke` bewirkt, sagt die
> **Stufe** – vor der Bestellung nimmt es die Anfrage zurück (es war nichts zugesagt),
> ab ihr storniert es (dort liegt eine Bestellung beim Lieferanten). Zwei Verben für
> dieselbe Sache hiessen, dass der Aufrufer entscheidet, welches gerade gilt.
> **Was aber STÜCKE betrifft, entscheidet ein Mensch**: das Modul darf einen Auftrag
> **vorschlagen** (mit vorgewählten Stücken, wie §4.5 bei «nicht bestanden»), es legt
> keinen an. Automatik an dieser Stelle war im Vorgängersystem gebaut und wieder
> abgeschaltet.
> **Teillieferung ist Teilabschluss – kein eigener Mechanismus**: `confirm_step` ist seit
> §4.4 ein Teilabschluss, also bleibt der Beleg in «Bestellung», solange noch etwas
> davorsteht, und rückt von selbst weiter, wenn nichts mehr wartet.
> **Vor der Bestellung zieht die Menge still nach, ab ihr wird GEKLÄRT** – dieselbe Regel
> wie beim Beleg-Rebase: bis zur Zusage entscheidet das System, ab der Zusage der Mensch
> (`clarify_quantity` nennt «bestellt für N, gebraucht M»).
> **Und der stornierte Beleg behält seinen Weg**: die Kette steht still da, wo sie
> stehengeblieben ist – ein Storno macht die Bestellung nicht ungeschehen, er sagt nur,
> dass nichts mehr ankommt (dieselbe Regel wie «die Linie sagt die Vergangenheit», §8.1a).
> Die erste Fassung setzte bei `storniert` alle Stufen auf grau; ein stornierter Beleg sah
> damit aus wie einer, bei dem nie etwas geschehen war.
> **Und eine NEUE Tabelle fiel zwischen die Netze** (`purchases.is_active`): Es gibt drei,
> und sie fangen Verschiedenes – die **Migration** ist die Wahrheit, `create_all` legt eine
> fehlende **Tabelle** an (nie eine fehlende Spalte), `_COLUMN_SAFETY_NET` zieht fehlende
> **Spalten** nach. Dazwischen liegt genau eine Lücke: eine Tabelle, die es gibt, der aber
> eine Spalte des Modells fehlt. Das Modell erbt `is_active` von `Base`, die Migration
> nannte sie nicht – **lokal grün** (dort hatte `create_all` die Tabelle einmal vollständig
> angelegt), gegen ein frisches Schema fielen **140 Prüfungen** aus, weil jeder Lesezugriff
> auf den Beleg scheiterte. Die Ausfallklasse von Migration 090, eine Ebene tiefer.
> Der Wächter **baut das Schema wirklich** statt es zu glauben
> (`tests/test_schema_is_built_by_the_migrations.py`: Wegwerf-Datenbank, `alembic upgrade
> head`, dann Modell ↔ Schema für **jede** Tabelle; Netz-Spalten zählen als gedeckt) – und
> er ist gegen seine Bug-Form gegengeprüft. **Die Arbeitsregel daraus:** die Suite läuft
> einmal gegen die gewachsene Datenbank **und** einmal gegen ein Schema, das nur aus den
> Migrationen kommt – nur die zweite ist die, die die CI fährt.
> **Nachtrag aus dem ersten Test: ein unbekanntes Modul gab sich als ein anderes aus.**
> Gemeldet wurden drei Dinge – «Modultyp «beschaffen» ist dieser Oberfläche unbekannt», ein
> **«T»** als Symbol und eine **rote** Modulfarbe. Es war **ein** Befund: ein Browser-Stand,
> der älter ist als das Backend (nach jedem Deploy mit einem neuen Modul der Normalfall).
> Der Ton sagte dabei korrekt «kaputt» (`UNKNOWN_TONE`, so gewollt) – das **Symbol** log:
> es gab **drei** Rückfälle, und jeder zeigte ein echtes anderes Modul (`Blocks` = Verbrauch,
> `PackageX` = Aussondern, `CAPTURE_ICON.text` = der Erfassungspunkt «Text», also das
> gemeldete T). Jetzt gilt für das Symbol dieselbe Regel wie für die Farbe: **eine**
> Auflösung (`moduleIcon`), Rückfall ist ein **Fragezeichen** – Unbekanntes sieht unbekannt
> aus. Wächter `test_an_unknown_module_looks_unknown_not_like_another_one` (gegengeprüft).
> **Und die Farbe war unabhängig davon falsch gewählt**: `ink` (kühles Graublau) stand im
> Fluss neben der **Datenerfassung** und war von ihr nicht zu trennen – gemessen an den
> echten Karten, nicht geschätzt. Beschaffen trägt jetzt **`plum`** (gedämpftes Violett):
> Slate=Blau · Clay=Rotbraun · Moss=Grün · Sand=Gelbbraun – Violett ist die einzige
> Familie, die kein anderes Modul besetzt. Blaugrün rückte nur an **Bewegen** heran, ein
> warmes Grau las sich neben vier farbigen Karten wie **deaktiviert**.
> Wächter: `tests/test_purchase_module.py` (14 Prüfungen, jede gegen ihre Bug-Form
> gegengeprüft) + drei in `test_frontend_mirrors.py`. Gemessen in Chromium: 1440 · 1024 ·
> 834 · 375 · 320 px, **0 px** waagrechter Überlauf über alle fünf Stufen-Zustände.

> **Testnotizen #741–#749 — drei Wurzeln, neun Symptome** (Migration `115`):
> **(1) Ein Modul zeigt seine Sache in JEDEM Zustand – nur die Aktionen hängen daran, ob
> es dran ist** (#749, die eigentliche Wurzel). Die Ausführungsstelle hatte **zwei**
> Körper: aktiv das Formular, sonst eine hand-gepflegte **Aufzählung** dessen, was ein
> Modul tragen kann (Punkte · Umfang · Verb · Grund · Ziel). Diese Liste muss mit jedem
> neuen Modul-Fakt wachsen – und der Beschaffungs-Beleg stand nicht darin: ein
> abgeschlossenes Modul zeigte von ihm **nichts**. Jetzt ist es EIN Körper (`stepBody`),
> und `isActive` entscheidet allein über das **Handeln**; dieselbe Regel eine Ebene
> tiefer im Beleg selbst (`stage.active || stage.done`). Ein gesperrtes Eingabefeld ist
> dabei **keine** Lese-Anzeige – was feststeht, steht als Wert da (`ReadField`).
> **(2) Die Bestellmenge ist keine Eingabe** (#741): ein Beschaffungs-Modul sitzt in
> einem Prozess, und **wie viel bestellt wird, sagen die Einzelinstanzen, die davorstehen**
> (`purchase.quantity_of` → `unit_count`). Eine getippte Menge daneben war eine zweite
> Aussage über dieselbe Sache – und die getippte gewinnt, auch wenn sie falsch ist. Aus
> zwei Spalten wurde **eine**: `ordered_for` ist `NULL`, solange nichts bestellt ist, und
> friert mit der Bestellung ein (dort ist eine zweite Partei gebunden). *Die
> **Mindestbestellmenge** wird bewusst nicht aufgeschlagen: das Modul erzeugt keine
> Einzelinstanzen – für die Übermenge gäbe es gar keine Stücke.* Ebenso entfallen: der
> **Termin** (#745 – ableitbar aus Bestelldatum + Lieferfrist, also kein Feld) und der
> **Speichern-Knopf** (#748 – Auto-Save wie überall; er war die einzige Stelle im ERP mit
> einem und sah aus, als täte er nichts, weil der getippte Wert ja schon dastand).
> **Ohne Lieferfrist keine Offerte** (#743, im **Dienst**, nicht nur am Knopf): aus ihr
> kommt der Liefertermin, und zwei Angebote ohne Frist sind nicht vergleichbar. Die
> Lieferantenwahl ist eine **Zeile, die man anklickt** (#742 – kein Häkchen daneben), und
> Offerte/Absage sind **Symbole mit Erklärung im Hover** (#744).
> **(3) Die Lieferanten-Sicht ist eine Spiegelung, keine zweite Antwort** (#747): *Ein
> Lieferant sieht die Aufträge, in denen er **angefragt** ist – und von jedem nur sein
> eigenes Modul.* Das ist **eine** Frage (`purchase.mine`, JSONB-Containment in der
> Datenbank), die Feed **und** Detail lesen; die Verengung steht **in** der
> Antwort-Funktion (`orders._mine_only`), nicht an den Aufrufstellen – wer sie dort
> formulierte, hätte sie beim zweiten Endpunkt nicht. Blank ist eine **Liste** von
> Feldern (`_INTERNAL_FIELDS`), keine Bedingungskette: die Antwort für ihn ist
> buchstäblich die des Personals, aus der etwas herausgenommen wurde. Wer nicht beteiligt
> ist, bekommt **404** (403 bestätigt, dass es den Auftrag gibt). Die Oberfläche zeichnet
> ohne Prozessbild **dieselbe** Modul-Karte (`StepCard`), nur ohne Achse.
> **Nebenbei, gemessen statt vermutet:** `toLocaleString('de-CH')` liefert je nach
> ICU-Fassung `1’284.50` (Browser) oder `1'284.50` (Node). Das Design-System schreibt den
> **geraden** Apostroph fest, und dieselbe Zahl darf nicht je nach Laufzeit anders
> aussehen – server- und clientseitig gerendert wirft React die Seite weg. `formatAmount`
> schreibt den Trenner jetzt fest.
> **Und eine Spalte kann man nicht einfach abhängen**: `purchases.quantity` war `NOT NULL`
> **ohne** DB-Default (der Default war Python-seitig) – sie aus dem Modell zu nehmen liess
> jedes Insert auflaufen. Migration `115` löst zuerst die Sperre (beide Revisionen laufen
> damit), gedroppt wird im **Folge-Deploy**, zusammen mit `due_date`. Dafür gibt es jetzt
> ein `_NULLABLE_SAFETY_NET` neben dem Drop-Netz.
> Wächter: `tests/test_purchase_module.py` (18 Prüfungen) + vier in
> `test_frontend_mirrors.py`, jeder gegen seine Bug-Form gegengeprüft. Gemessen in
> Chromium: 1440 · 1024 · 834 · 375 · 320 px, **0 px** waagrechter Überlauf über sechs
> Beleg-Zustände; der abgeschlossene Beleg zeigt alles und hat **0** bedienbare Knöpfe.

> **Was beschafft wird, sagt der PROZESS; was zu tun ist, sagt das MODUL** (Migration
> `116`): Das Artikelfeld am Beschaffungs-Modul ist entfallen. Es war eine **zweite
> Aussage über dieselbe Sache** – die Einzelinstanzen, die vor dem Modul stehen, tragen
> ihren Artikel; die Zeilen des Belegs sind darum eine Ableitung (offene Zugehörigkeit →
> Einzelinstanz → Instanz → Artikel, gruppiert und gezählt). **Mehrere Artikel sind der
> Normalfall, kein Sonderfall**: stehen Stücke zweier Artikel davor, hat der Beleg zwei
> Zeilen – EINE Bestellung mit zwei Positionen, wie im echten Leben; es braucht dafür
> keine Regel, nur eine Gruppierung. Mit der Bestellung frieren sie ein
> (`purchases.ordered_lines` ersetzt `ordered_for`), davor gibt es sie gar nicht – sie
> **sind** der Prozess und ziehen von selbst nach. *Die eine Grenze, benannt statt
> versteckt: zwei Artikel bei **verschiedenen** Lieferanten sind zwei Bestellungen, also
> zwei Module – ein Beleg hat einen Lieferanten.*
> **Woher der Lieferant weiss, was zu tun ist – drei Schichten, jede an ihrem Ort:** die
> **Sache** aus der Artikel-Spezifikation (eingefroren, gilt für jeden Lieferanten), der
> **Auftrag** aus `config.instruction` am Modul («Härten auf 58 HRC» ist eine Eigenschaft
> *dieses* Schritts, nicht des Artikels – und ein Artikel hat mehrere Schritte), die
> **Nummer** an der Angebotszeile bzw. `reference` (sie gehört dem Lieferanten, nicht dem
> Teil). **Die Spezifikation reist mit dem Beleg, sie wird nicht ausgewählt**
> (`services/article_fields` – der alte Katalog «welche Felder sieht der Lieferant?» hatte
> null Aufrufer und kommt nicht zurück: bei zwei zugelassenen Lieferanten müsste dieselbe
> Frage zweimal beantwortet werden, und eine Spezifikation, die je nach Empfänger anders
> lautet, ist keine; wer etwas nicht zeigen will, schreibt es nicht hinein). Bewusst
> **nicht** dabei: `serialization` (sagt, wie *wir* zählen), MOQ/Sicherheitsbestand
> (unsere Dispositionsgrössen) und die **Lieferanten-Artikelnummer** – sie gehört genau
> einem, und sie allen zu zeigen wäre genau der Fehler, den die dritte Schicht vermeidet.
> **Der Auftrag ist Pflicht**, und er löst zugleich das Problem, das den Vorgänger zum
> Artikelfeld gezwungen hatte: eine gekaufte **Leistung** braucht keinen eigenen Artikel
> «Härten» mehr (einen Datensatz, der nie Material wird, in Bestand, Stückliste und
> Auswahl aber wie einer aussieht) – auf dem Beleg steht die **Welle**, die davorsteht.
> **Der Einstandspreis braucht genau EINE Zeile**: bei zwei Artikeln ist die Bestellsumme
> eine gemeinsame, sie durch die Gesamtmenge zu teilen ergäbe für beide denselben – und
> für beide falschen – Preis; die Aufteilung müsste ein Mensch vornehmen, also wird nichts
> geschrieben statt eine Zahl zu erfinden, mit der danach kalkuliert wird.
> **Zwei-Schritte-Regel wie gehabt:** `article_id` verliert in `116` nur seine
> `NOT NULL`-Sperre (`_NULLABLE_SAFETY_NET`), `ordered_lines` kommt ins
> `_COLUMN_SAFETY_NET`; gedroppt wird im **Folge-Deploy**, zusammen mit `quantity`,
> `due_date` und `ordered_for`.
> Wächter: `tests/test_purchase_module.py` (21 Prüfungen) + fünf in
> `test_frontend_mirrors.py` – **sechs Bug-Formen gegengeprüft** (nur die erste Zeile ·
> Einstandspreis bei zwei Zeilen · Lieferanten-Nummer reist mit · Spezifikation reist gar
> nicht · Auftrag optional · Auftrag erreicht den Beleg nicht). Die Suite läuft grün gegen
> die gewachsene Datenbank **und** gegen ein Schema, das nur aus den Migrationen kommt;
> Migration `116` von null · idempotent · downgrade · über das Lifespan-Netz verifiziert.
> Gemessen in Chromium: 1440 · 1024 · 834 · 375 · 320 px, **0 px** waagrechter Überlauf
> über sieben Beleg-Zustände (inkl. Zwei-Zeilen-Beleg); der abgeschlossene Beleg zeigt
> Zeilen, Spezifikation und Auftrag und hat **0** bedienbare Knöpfe.

> **Testnotizen #750–#754 — eine Ansicht für zwei Rollen, und `can` ist das Tor**
> (Migration `117`): **(1)** Der Beschaffungs-Beleg rendete jede Aktion, sobald die Stufe
> aktiv war. Ein **Lieferant** sah damit «Anfrage zurückziehen», «Bestellen»,
> «Stornieren» und den **Wareneingangs-Scan** – vier Knöpfe, die der Server mit 403
> abweist (`SUPPLIER_ACTIONS`; `confirm_step` ist `require_employee`). Die Lösung ist EIN
> Feld statt Rollenabfragen: **`PurchaseEmbed.can`** – was *dieser* Betrachter an *diesem*
> Beleg tun darf, abgeleitet an der einen Stelle, an der die Regel wohnt (`_can`:
> Stufe × Rolle). Die Oberfläche fragt `may(...)` und weiss danach nicht mehr, was ein
> Lieferant ist. **Und `can` ist nicht bloss eine Auskunft, sondern das Tor**: dieselbe
> Tabelle weist in `apply` ab – wäre es nur ein Anzeige-Hinweis, liefen Knopf und Tür beim
> nächsten Verb auseinander; `_only_in` ist darin aufgegangen (**eine Regel weniger**).
> Der **Wareneingang** steht mit in der Liste, obwohl er über `confirm_step` läuft: aus
> Sicht des Belegs ist er das Verb seiner dritten Stufe, und zwei Listen wären zwei
> Massstäbe. **Ein Datenleck nebenbei**: `quotes` war gefiltert, die getroffene Wahl
> nicht – ein angefragter, **nicht** gewählter Lieferant las Namen und Bestellsumme
> seines Konkurrenten. **Die Wörter sind allgemein** statt je Rolle formuliert («Offerte
> erfassen» – er gibt seine ab, wir schreiben seine auf; «Absage · liefert nicht»), und
> der Bestell-Knopf liest sein Wort aus `stage.verb` – dem Feld, das der Server längst
> liefert und das **niemand** las. Das **Modul-Protokoll** ist keine Modul-, sondern eine
> Ansichtsfrage: `stepBody(step, isActive, internal)` – die beiden Aufrufstellen sagen,
> was sie sind, kein `if role` irgendwo.
> **(2) Die Referenz sind ZWEI Dinge zu zwei Zeitpunkten** (#753, vom Nutzer selbst
> hergeleitet): *wie bestelle ich bei ihm* (seine Artikelnummer, der Shop-Link) ist eine
> Eigenschaft der **Paarung** Modul × Lieferant und gehört dorthin, wo man festlegt, wer
> in Frage kommt (`config.suppliers[].ref` – JSONB, keine Migration; die alte Form
> `[nr]` wird tolerant gelesen, `Beschaffen.suppliers_of` ist die eine Lesestelle); *wo
> ist die Sendung* entsteht erst **nach** der Bestellung und kommt vom Lieferanten –
> darum `purchases.tracking`, und `note` kommt zu den Lieferanten-Handlungen. Umbenannt
> statt weiterverwendet, weil daneben künftig `suppliers[].ref` steht: zwei Dinge, die
> «ref» heissen und Verschiedenes meinen, sind genau die Verwechslung, aus der die Notiz
> entstand. Ein `http`-Wert wird zum Link.
> **(3) Die Angebotszeile ist eine kleine Karte** (#752): bei ~460 px Spurbreite drängten
> sich Nummer, Name, zwei Eingaben und zwei 30-px-Quadrate in EINE Flexzeile. Neu zwei
> Zeilen mit Haarlinie – oben wer und wie viel, darunter (nur wenn offen **und** erlaubt)
> Eingaben und Aktionen; `CircleSlash` für die Absage, dasselbe Zeichen, mit dem das Haus
> «storniert» schreibt. **(4)** «Anfragen» ↔ «Bei 2 anfragen» waren zwei Beschriftungen
> für denselben Knopf – die Zahl fiel ausgerechnet weg, wenn sie am grössten ist (#750).
> **(5) Der Scan-Chip trägt das globale Symbol** (#754): `ScanStep.kind` versprach seit
> jeher «erwarteter Objekttyp → **Symbol** im Scanner», gerendert wurde nie eines. Symbol
> **und Wort** kommen jetzt aus `TYPE_META` (`SCAN_RECORD_TYPE` daneben, `scanKindLabel`
> als die eine Auflösung); zwei Aufrufstellen hören auf, «Instanz» von Hand hinzuschreiben.
> `process`/`object` bleiben ohne Symbol – sie sind kein Datensatztyp, und ein
> ausgeliehenes wäre eine Behauptung (die Lehre aus `moduleIcon`).
> Wächter: `tests/test_purchase_module.py` (24) + drei in `test_frontend_mirrors.py` –
> **acht Bug-Formen gegengeprüft**; *zwei Wächter waren dabei stumpf und liessen ihre
> eigene Bug-Form durch* (sie fragten nach dem **Vorkommen** eines Wortes statt nach der
> **Form** des Tors bzw. nach dem Rendern) – gemessen, nachgeschärft, erneut
> gegengeprüft. Suite grün gegen die gewachsene DB **und** gegen ein Schema nur aus den
> Migrationen; Migration `117` von null · idempotent · downgrade · über das Lifespan-Netz.
> Gemessen in Chromium: 1440 · 1024 · 834 · 375 · 320 px, **0 px** waagrechter Überlauf
> über zehn Beleg-Zustände – sechs aus Personal-, vier aus **Lieferantensicht**; der
> unterlegene Lieferant sieht 0 fremde Angaben, der abgeschlossene Beleg 0 Knöpfe.

> **Ein Pop-up ist ein Pop-up — und ein Datensatz hat EINE Breite** (Testnotizen
> #755–#766, Migration `118`): Elf Notizen, und der rote Faden ist zweimal derselbe —
> **eine Form, die ihre eigene Regel mitbringt, statt sie zu erben.**
> **(1) Angemeldet wird ÜBER der Seite, auf der man steht** (`components/auth/login-dialog.
> tsx`). Das Anmelden war eine **Seite** mit deckender Fläche: die Seite dahinter
> verschwand, also brauchte es einen Knopf «Zurück zur Startseite», um wieder
> herauszukommen — genau den Umweg, den ein Pop-up nicht hat. Jetzt ein halbtransparenter
> Schleier (`rgba(24, 20, 17, 0.42)` + `blur(3px)`), daneben klicken **und** `Esc`
> schliessen, und nach dem Anmelden landet man dort, wo man war (`fallback={pathname}`).
> **EIN Bauteil, zwei Aufrufer**: die Navbar öffnet es an Ort und Stelle, die Route
> `/login` bleibt als zweiter Weg (Umleitung, Lesezeichen) und sagt, was «daneben» dort
> heisst — zur Startseite. Nachgebaut wäre die zweite Anmeldung beim ersten neuen
> Anmeldeweg veraltet. *Next.js «intercepting routes» wären der modische Weg und hier
> der falsche: sie müssten die Gruppen `(public)` → `(auth)` überbrücken, und ein
> Zustandswechsel im Router ist kein Ersatz für einen Zustand in einer Komponente.*
> **Gemessen, nicht geglaubt** — und die Messung hat einen echten Fehler gefunden: mit
> `align-items: center` wird eine Karte, die **höher als das Fenster** ist, oben
> abgeschnitten, und in einem Scroll-Container ist alles vor der Startkante
> **unerreichbar** (375×420: Kopf bei −74 px, `scrollTop = 0` half nicht — auf einem
> Telefon im Querformat wäre das E-Mail-Feld schlicht weg). Zentriert wird darum über
> `margin: auto` an der Karte (Kopf bei +31 px). Dazu 1440 · 1280 · 1024 · 834 · 375 ·
> 320 px: **0 px** waagrechter Überlauf, Karte symmetrisch, Klick daneben schliesst,
> Klick **hinein** nicht.
> **(2) Ein Datensatz hat EINE Breite** (#763, `fields.DETAIL_MAXW` + `DetailBody`): die
> Artikel-Spezifikation war begrenzt, Instanz und Unternehmen liefen über die volle
> Fläche, das Unternehmen trug sogar eine dritte Zahl (760). Auf einem breiten Schirm las
> sich derselbe Datensatztyp je nach Reiter anders. Die Breite ist eine Eigenschaft der
> **Gattung** «Detail-Ansicht», nicht der einzelnen Ansicht — also steht sie einmal und
> wird geerbt; der Wächter verbietet jede eigene Satzbreite daneben (eine
> **Kürzungs**grenze an einer Zeile bleibt erlaubt, sie ist eine andere Sache).
> **(3) Der Artikel hat gar keine Reiter mehr** (#760/#761): der **Bestand** steht zuoberst
> in derselben Ansicht — «wie viel habe ich davon» wird an einem Artikel öfter gefragt als
> alles andere, und ein Klick dafür ist einer zu viel. Damit blieb nichts, was einen
> zweiten Reiter rechtfertigt. Und der **Name** steht nur noch im Kopf: er stand dort
> **und** als erstes Lesefeld der Spezifikation — zwei Anzeigen derselben Angabe sind
> nicht doppelt klar, sondern erzeugen die Frage, welche gilt. Die **Haarlinie** gehört
> seither dem Karten-Kopf (`SpecHead`, #762) statt jeder Aufrufstelle einzeln.
> **(4) Man deaktiviert keine Menschen** (#755, Migration `118`): «man wechselt höchstens
> die nutzerrolle. wenn jemand das unternehmen verlässt, dann wird er zum normalen user
> statt als mitarbeiter. er soll ja trotzdem weiterhin bei uns einkaufen dürfen gehen.»
> Beide Endpunkte sind ersatzlos entfallen. **Die Falle dabei:** damit könnte niemand mehr
> aufheben, was heute gesetzt ist — ein deaktivierter Benutzer wäre für immer ausgesperrt;
> Migration `118` hebt darum jede bestehende Deaktivierung auf. Die **Abweisung beim
> Login** bleibt trotzdem stehen, denn ihr eigentlicher Zweck ist ein anderer: sie
> verhindert, dass eine deaktivierte Zeile still als **neuer** Benutzer mit neuer
> Objektnummer wiederaufersteht. *Nebenbei gefunden und entfallen: der Reiter
> «Bestellungen» am Benutzer rendete **gar nichts** — seine Karte hängt am Verkaufs-Modul,
> und das ist im Basis-Neuaufbau abgeschaltet. Er kommt mit dem Verkauf zurück.*
> **(5) «Verwendung» ist vollständig gelöscht** (#764): Reiter, Ableitung
> (`services/references.py`), Router und Client-Aufruf — drei Dateien weniger. Den Reiter
> nur auszublenden hiesse, einen Endpunkt am Leben zu lassen, den niemand ruft.
> **(6) Der Symbol-Knopf besitzt seine Form in der KLASSE** (#757, dreimal gemeldet — und
> die Ursache war eine fehlende Zeile): `.erp-actbtn` zentrierte allein über seine
> **Polsterung**, es gab kein `justify-content`. Ein Text-Knopf sah damit richtig aus, und
> genau die Polsterung nimmt ein Symbol-Knopf weg (`padding: 0`). **Gemessen in Chromium:**
> das Symbol sass 1 px vom linken und 17 px vom rechten Rand — 16 px daneben; mit der
> Zeile 9/9, Δ 0.00 px, und der Text-Knopf unverändert. Wer das an der Aufrufstelle mit
> einer Inline-Breite «repariert», verschiebt es nur — darum eine eigene Ausprägung
> `.erp-actbtn-icon` und ein Wächter gegen die Inline-Breite.
> **(7) Die Bestellangabe ist Pflicht** (#756) — im **Dienst** (`Beschaffen._suppliers`
> weist eine leere ab und nennt den Lieferanten), nicht nur am Feld: ohne sie weiss der
> Lieferant nicht, was zu bestellen ist. **Der Scan-Chip ist entfallen** (#758): die Sorte
> steht im **Platzhalter**, ihr **Symbol** am Innenrand des Feldes — der frühere Einwand
> («ein Platzhalter verschwindet beim ersten Zeichen») ist damit beantwortet, nicht
> ignoriert. Und «Storniert» sagt nur noch das Wort (#759 — dass nichts mehr ankommt,
> steht in der Kette darunter).
> **(8) #766 war eine Frage, keine Meldung — und die Antwort war ein Satz.** Ob «Ersetzt
> Artikel» robust sei, ob nur inaktive Artikel wählbar sein sollten, und ob ein ersetzter
> Artikel als **Ersatzteil** wieder aktiv werden dürfe. Geprüft: die Logik stimmt.
> Ersetzen **bedeutet** ausser Betrieb nehmen (zwei Klicks wären zwei Gelegenheiten, den
> zweiten zu vergessen), und nur inaktive anzubieten machte den Normalfall zweistufig.
> Der Ersatzteil-Fall funktioniert längst — **ohne eigene Regel**: «ausser Betrieb» ist am
> Artikel ein gewöhnlicher Zustand in beide Richtungen, und `replaced_by_id` weiss davon
> nichts. Was fehlte, war der **Satz**: der Hinweis nannte nur die erste Hälfte, und genau
> daraus entstand die Sorge. Ergänzt, und mit einem Wächter festgehalten statt beim
> nächsten Umbau neu hergeleitet.
> Wächter: zehn neue in `test_frontend_mirrors.py` + zwei in `test_article_lifecycle.py`,
> **jeder gegen seine Bug-Form gegengeprüft** — *drei waren dabei stumpf und liessen ihre
> eigene Form durch* (ein Name statt des Renderns, eine Kürzungsbreite als Satzbreite
> gelesen, und ein Wächter, der seinen eigenen **Kommentar** mitlas und darum anschlug,
> weil jemand den Fehler *beschreibt*). Gemessen, nachgeschärft, erneut gegengeprüft.
> Suite grün gegen die gewachsene Datenbank **und** gegen ein Schema nur aus den
> Migrationen; Migration `118` von null · idempotent · downgrade · über das Lifespan-Netz,
> und ihre **Wirkung** gemessen (1 deaktivierte Zeile → 0).

> **Eine Sendung ist ein EINKAUF — der Beleg gehört keinem Modul** (PROCESS_CORE
> §9.8/§9.9, `domain/procurement.py`, Migration `119`): Es gibt mehrere Arten, etwas zu
> bewegen — selbst tragen, ein Roboter, oder eine Spedition beauftragen. Die letzte ist
> eine **Leistung, die man einkauft**, und dafür gibt es den Einkauf bereits.
> **Die Umdeutung, aus der alles folgt:** der Beleg war nie Teil des Beschaffen-Moduls. Im
> Datenmodell hängt er am **Schritt** (`purchases.step_id`, kein Modultyp), `_can` liest
> Stufe × Rolle, `assert_receivable`/`note_receipt` fragen nur, ob es zu diesem Schritt
> einen Beleg gibt. Gebunden war er durch genau **zwei Fäden**: er las `config.suppliers`
> und `config.instruction`. Sind die gekappt (`Module.suppliers_of` / `instruction_for`),
> trägt **jedes** Modul denselben Beleg — dieselben drei Stufen, dieselben Verben,
> **dieselbe Komponente**. «1:1 übernehmen» war damit keine Kopie, sondern das Wegnehmen
> der letzten zwei Fäden; `purchase-work.tsx` ist unangetastet geblieben.
> **Verworfen wurden drei Alternativen, je aus einem Grund:** *zwei Module hintereinander*
> («Speditionsleistung kaufen» → «Bewegen») — beim Modellieren weiss niemand, ob getragen
> oder verschifft wird, und ein vorgeplantes Modul wäre bei der Hälfte der Ausführungen
> sinnlos; *Transport als eigener Auftrag* — zirkulär, der Unterauftrag enthielte wieder
> ein Bewegen-Modul; *Beschaffen bekommt ein Ziel* — falsch herum: **jede** Bewegung hat
> ein Ziel, nur **manche** haben einen Beleg, und das Optionale gehört zu dem Modul, das
> immer da ist.
> **Selbst ↔ eingekauft ist EIN Bit, und es ist abgeleitet**: eingekauft wurde genau dann,
> wenn es einen Beleg gibt. Die Liste `manuell · paket · fracht` (mit `available`-Flag als
> Roadmap und einer Server-Sperre für gesperrte Kanäle) ist **ersatzlos entfallen** —
> *Paket* und *Fracht* sind keine zwei Arten, sondern zwei **Angebote** desselben
> Einkaufs; das entscheidet der Tarif, nicht der Modellierer. Ein Roboter ist «selbst»:
> unser Gerät, keine Rechnung. Die Transportart ist damit auch **keine Eingabe** mehr —
> eine getippte gewänne auch dann, wenn niemand eine Spedition beauftragt hat.
> **Der Ziel-Scan schliesst den Beleg** (Ankunft und Ablage sind ein Ereignis, also eine
> Bestätigung) — und dafür musste **keine Zeile** geändert werden: `assert_receivable`
> und `note_receipt` fragten schon immer nur `of_step`.
> **Vier Deklarationen am Modul, jede mit offensichtlicher Vorgabe:** `moves` (die Zeile,
> die die Liste als Bit ablöst), `buys` (`BUY_ALWAYS` = der Einkauf ist der Zweck, der
> Beleg entsteht mit der Freigabe ↔ `BUY_IF_CHOSEN` = er entsteht mit der Wahl),
> `landed_cost` und die beiden Fäden. **Die Falle, die still gewesen wäre:**
> `_write_landed_cost` schrieb *Summe ÷ Menge* auf den Artikel — bei einem Transport wäre
> das der **Frachttarif als Einstandspreis**, und damit würde danach kalkuliert (im
> Gegentest gemessen: 90.00 CHF am Artikel). Darum eine Deklaration statt eines
> `if module_type`.
> **`buy` ist eine Handlung des MODULS, nicht des Belegs** — bewusst nicht in `ACTIONS`
> (dort stehen die Verben eines Belegs, und `_can` ist ihr Tor; `buy` hat keine Stufe).
> Ein bestehender Wächter hat genau das gemeldet, als sie zuerst darin stand. Ihre
> Gegenhandlung ist dieselbe wie überall (`revoke`), und **was sie bewirkt, sagt das
> Modul**: wo der Einkauf der Zweck ist, bleibt der Beleg und verliert seine Angebote; wo
> er eine **Wahl** war, verschwindet er — sonst beantwortete sich «wurde eingekauft?» mit
> «ja», obwohl die Wahl weg ist. Dafür ist der Unique-Index **partiell** geworden
> (Migration `119`: ein *aktiver* Beleg je Modul), sonst wäre «eingekauft ↔ doch selbst ↔
> dann doch eingekauft» eine Sackgasse.
> **Shippo & Co. fallen heraus, statt gebaut zu werden** (heute bewusst nichts davon): ein
> Frachtführer ist ein **Lieferant**, ein Tarifvergleich ist der **Angebotsspiegel**, den
> der Beleg hat, die Sendungsnummer ist `purchases.tracking` (seit Migration 117). Später
> kommt genau **eine** Sache dazu: eine Angebotszeile, die eine Anbindung füllt statt ein
> Mensch — eine Eigenschaft des Lieferanten, kein Modul und kein Konzept.
> Wächter: vier in `tests/test_purchase_module.py`, drei in `test_frontend_mirrors.py`,
> zwei umgeschriebene in `test_move_module.py` — **jeder gegen seine Bug-Form
> gegengeprüft** (u. a. Frachttarif am Artikel · Beleg-Vokabel zurück an der Modul-Klasse ·
> Dienst sucht wieder EINEN Modultyp · Wahl nicht zurücknehmbar). Suite grün gegen die
> gewachsene Datenbank **und** gegen ein Schema nur aus den Migrationen; Migration `119`
> von null · idempotent · downgrade · über das Lifespan-Netz. Gemessen in Chromium:
> 1440 · 1280 · 1024 · 834 · 375 · 320 px, **0 px** waagrechter Überlauf, beide Optionen
> exakt gleich breit (Δ 0.00 px — die erste Wortwahl ergab bei 320 px 10.6 px Differenz).

> **Das sechste Modul ist «Verkauf» — dasselbe Tor, andere Richtung** (PROCESS_CORE §9.10/
> §9.11, Migration `122`). **Verkauf ist kein neues Konzept**: Einkauf und Verkauf sind
> *dasselbe Geschäft aus zwei Blickwinkeln* – jemand fragt, jemand nennt einen Preis,
> jemand sagt zu, jemand erfüllt. Drei Stufen, eine Schwelle, ein Storno, **ein Dienst**
> (`services/purchase`). Verschieden sind nur Wörter, Gegenpartei und die Hand, die den
> Preis einträgt – und alle drei stehen als **Daten** im `Flow` (`domain/procurement.
> FLOWS`), nicht als `if direction ==`: die erste Verzweigung ist eine Beschriftung, die
> zweite eine Regel, und ab der dritten gibt es zwei Belege, die nur so tun, als wären sie
> einer. Ein `services/sales.py` gibt es darum nicht, und ein Quelltext-Wächter hält es so.
> **Die Stufen wurden dafür neutral** (`offer · commitment · fulfilment · cancelled`) –
> «Wareneingang» an einem Verkaufs-Beleg wäre kein Name, sondern ein Irrtum mit Bestand;
> die alten Werte bleiben lesbar (`normalize`), Migration und Alias sind zwei Netze für
> dieselbe Umschrift. **Die Richtung steht am BELEG**, nicht am Modultyp: ein laufender
> Auftrag trägt seinen Prozess eingefroren, und ein Beleg soll auch dann noch sagen können,
> was er war, wenn sein Modul längst anders deklariert ist.
> **Der eine echte Unterschied ist der AUSGANG.** Der Einkauf endet mit dem Wareneingang
> und ist ein Durchläufer; der Verkauf endet mit der Lieferung, und was geliefert ist, ist
> weg (`terminal`, Status **`Verkauft`**). Alles Weitere folgt daraus ohne eine
> Fallunterscheidung – der Editor bietet dahinter nichts an, die Freigabe weist ab, das
> Bild endet dort (§4.6).
> **Die Retoure ist ein ganz gewöhnlicher Auftrag** – kein Retouren-Modul, kein «Retoure
> annehmen»-Endpunkt: er greift die verkauften Stücke, **das Greifen IST die Rücknahme**
> (wie beim Sperren und beim Verbauen). Und weil sein Start vom Regelstart abweicht, ist er
> **automatisch** eine dokumentierte Abweichung. **Die Farbe spielt dabei keine Rolle** –
> das war die Frage beim Entwurf: `Verkauft` ist **grün** (es hat sein Ziel erreicht) und
> löst trotzdem eine Abweichung aus, denn `deviation_flags` vergleicht mit dem *Regelstart*
> und nennt weder Farbe noch Status. `Verbaut` beweist das seit dem Verbrauchsmodul; eine
> Regel, die nach der Farbe fragte, liesse ausgerechnet die Retoure aus dem Nachweis fallen.
> **Und der Ort fällt weg, ohne eine Zeile im Modul**: `process._pass` räumt ihn für jeden
> Zustand mit `stock = HISTORY`. Wo das Stück beim Kunden liegt, ist nicht unsere Auskunft.
> **In der Definition steht nichts** – wer kauft, weiss beim Modellieren eines Artikels
> niemand (die Liste bleibt *möglich*, Pflicht ist sie nicht); und `landed_cost = False`,
> denn was ein Kunde zahlt, ist verhandelt und sagt nichts über unsere Kosten. **Ein
> Namensteppich blieb aus**: `Module.suppliers_of` heisst jetzt `parties_of` (beim Verkauf
> steht dort ein Kunde), der JSONB-Schlüssel `supplier` bleibt – er steht in laufenden
> Aufträgen, und eine Umschrift wäre ein Risiko ohne einen einzigen neuen Leser.
>
> **Testnotizen #778–#783 und der Order-to-Cash: die Forderung ist die DRITTE ACHSE**
> (PROCESS_CORE §9.11, Migration `123`). Gegen die üblichen ERP-Schritte geprüft, stand
> genau **ein** Loch: die **Fakturierung**. Angebot und Kundenauftrag sind die Stufen des
> Belegs, Kommissionierung und Versand sind **Bewegen-Module vor dem Verkauf-Modul**, der
> Zahlungseingang ist die Zahlungszeile – und **ATP gibt es bewusst nicht**: die Freigabe
> *ist* die Verfügbarkeitsprüfung, Reservierungen gibt es im System nirgends.
> **Die Antwort auf «eine Logik, die in allen Umständen passt» lautet: schreib die
> Reihenfolge nicht auf.** Ware · Forderung · Geld sind drei **unabhängige** Achsen, und
> jedes Szenario ist eine andere **Folge** derselben drei Grundhandlungen – Zahlungsziel,
> **Vorauszahlung**, **Anzahlung + Schlussrechnung**, Nachnahme, Shop, Retoure, Garantie,
> Kulanz. Für keines davon gibt es einen neuen Mechanismus und für keines einen Modus:
> wer eine Folge festschreibt, bekommt für jede Abweichung ein `if`. Wer zuerst Geld sehen
> will, stellt zuerst die Rechnung.
> **Und das System wurde dabei kleiner.** Die alte `credit`-Zahlung war eine Zahlung, bei
> der kein Geld fliesst – zusammengehalten von einer eigenen Regel («hat keinen
> Zahlweg»). Als **negative Rechnung** ist sie schlicht richtig: `payments.kind` und die
> Ausnahme sind **beide** entfallen. Eine Erstattung bleibt eine negative **Zahlung**.
> **Die Automatik steckt in den Vorgaben**, nicht in einem Modus: Betrag = *zugesagt −
> berechnet* (die Zahl `uncharged`, die es vorher gar nicht geben konnte), Fälligkeit =
> *heute + Frist*, Nummer = **`<Auftragsnummer>-<laufend>`** – dieselbe Regel wie beim
> Suffix der Einzelinstanz, und aus demselben Grund: eine Rechnung braucht einen Namen,
> aber keine eigene Objektidentität. Das `-1` der ersten fällt nach aussen weg, gespeichert
> bleibt es (sonst hiessen zwei Rechnungen gleich). Wer nummeriert, sagt der `Flow`.
> **Der Shop greift ohne einen einzigen neuen Endpunkt an** – gemessen, nicht behauptet
> (`test_a_shop_checkout_needs_no_new_endpoint`): Freigabe → `ask` → `order` → `invoice` →
> Zahllink → Webhook. **Und ohne Rechnung kein Zahllink**: man kassiert nicht, was niemand
> gefordert hat.
> **Ein Fehler, der beim Messen auffiel**: direkt nach der Zusage stand «Bezahlt» – offen
> ist dort null, weil noch **nichts gefordert** wurde. Dieselbe Zahl, eine ganz andere
> Aussage. Die Karte sagt jetzt «Nichts berechnet».
>
> **#778 war strukturell, nicht lokal.** «Dieser Wert ist bereits vergeben» beim Umschalten
> zwischen Beschaffen und Selbst war gegen ein migrationsgebautes Schema **nicht
> nachstellbar** (gemessen: 4× hin und her, fehlerfrei). Ursache: **der Deploy fährt kein
> `alembic upgrade head` gegen die dev-Datenbank** – sie lebt von `create_all` (fehlende
> *Tabellen*) + `_COLUMN_SAFETY_NET` (fehlende *Spalten*) + `_RAW_INDEX_SAFETY_NET`.
> Migration `119` machte `uq_purchases_step` **partiell**; dort stand darum weiter der
> volle Index aus `114`, und der zweite `buy` verletzte ihn. Das Netz hat für genau diesen
> Fall schon zwei Einträge – dieser fehlte. **Die Lehre ist grösser als die Notiz:** jede
> Index- oder Constraint-Änderung, die nur in einer Migration steht, erreicht dev nie.
> **#779 – jeder darf Kunde sein.** Die Rolle sagt, was jemand *für uns* tut, nicht ob er
> *bei uns* kaufen darf; ein Mitarbeiter, der eine Schraube kauft, ist ein Kunde. Kein
> `if role == 'customer'`, sondern `Flow.party_roles` (**leer heisst frei**, wie bei
> `parties_of`) – und **dieselbe** Angabe lesen Auswahlliste und Dienst. Beim Einkauf
> bleibt «Lieferant» eine Zulassung, die wir vergeben.
> **#780/#781 – ein Feld als Vielleicht ist schlimmer als keines.** «Auftrag an den
> Kundeen» und «Bestellangabe» standen am Verkauf, weil man sie *vielleicht* braucht.
> Aus zwei Booleans je Feld (vier Zustände, einer fehlte: «gibt es hier gar nicht») wurde
> **ein Wert mit drei Stufen** – `OFF` · `OPTIONAL` · `REQUIRED`. Verkauf: `instruction =
> OFF`. Ein Lieferhinweis gehört an das **Bewegen**-Modul, das die Lieferung *ist*.
> *Und zur Frage dahinter, gemessen statt behauptet: `if direction ==` gibt es **null
> Mal** – nicht im Beleg-Dienst, nicht in `payments`, nicht im Frontend.*
> **#782 – die Karte tippt niemand ab.** Sie entsteht beim Zahlungsdienst und kommt über
> den Webhook; sie von Hand zu erfassen wäre eine zweite Quelle für dieselbe Buchung.
> `money.MANUAL_METHODS` neben `METHODS` (zwei Formen einer Regel), durchgesetzt an der
> **Menschentür** (`purchase._pay`), nicht nur im Formular – und zwei Werte sind ein
> **Schieber**, keine Auswahlliste.
> **#783 – Container im Container, und der innere IST eine Modul-Karte.** Nicht
> nachgebaut, sondern **geteilt**: `ModuleShell` ist dasselbe Bauteil, das auch `StepCard`
> trägt. *Meine frühere Begründung («die dritte Fläche», #100/#104) ist damit überstimmt –
> ein Einkauf in einem Bewegen-Modul ist ein Vorgang mit eigener Identität, keine Fussnote
> am Rand.*
> **Drei Wächter mussten dabei umgeschrieben werden**, weil sie die **Form** der alten
> Lösung prüften (`<ModuleMark` in *dieser* Funktion, `borderLeft`) und damit angeschlagen
> hätten, obwohl die Regel besser erfüllt ist als vorher. Ein vierter las seinen eigenen
> Erklärtext mit (`_code_of` liest jetzt den **Code**, nicht die Prosa) und ein fünfter
> teilte am ersten Vorkommen eines Namens, das im Kommentar stand – er prüfte damit **gar
> nichts**. Alle nachgeschärft und gegen ihre Bug-Form gegengeprüft.
> Wächter: `tests/test_invoices.py` (9 Prüfungen, **jede gegen ihre Bug-Form
> gegengeprüft**) + fünf in `test_frontend_mirrors.py`; Suite grün gegen die gewachsene
> Datenbank **und** gegen ein Schema nur aus den Migrationen. Gemessen in Chromium an der
> **echten** Komponente: 1440 · 1280 · 1024 · 834 · 375 · 320 px, **0 px** waagrechter
> Überlauf über **acht** Beleg-Zustände (inkl. Anzahlung und Zwei-Rechnungen-Fall).

> **Das Geld ist eine ZEILE am Beleg, keine vierte Stufe** (`domain/money.py`,
> `services/payments.py`). **Es gibt keine Forderungs-Tabelle**: *offen* = Belegsumme −
> Gutschriften − Zahlungen, *fällig* = Zusagedatum + Zahlungsfrist, *überfällig* = beides.
> Drei Ableitungen, null Spalten – eine Spalte «offener Betrag» wäre die zweite Wahrheit,
> und die eine vergessene Nachzieh-Stelle fällt erst auf, wenn jemand mahnt. Ein
> **negativer** offener Betrag ist kein Fehler, sondern eine Aussage: dann schulden wir.
> **Zwei Arten, weil zwei Dinge Verschiedenes bedeuten**: `payment` (Geld ist geflossen,
> negativ = Erstattung) und `credit` (die Forderung wird gemindert, ohne dass Geld
> fliesst). Ohne sie liesse sich «wie viel hat der Kunde wirklich gezahlt» nicht mehr
> beantworten, und eine Retoure sähe aus wie eine offene Rechnung. **Ware und Geld sind
> entkoppelt**: Gutschrift ohne Rücknahme = Kulanz, Rücknahme ohne Gutschrift = Garantie –
> gekoppelt wäre keines von beiden abbildbar.
> **Der Weg des Geldes ist ein FELD, kein Modell**: Überweisung und Karte schreiben
> denselben Datensatz über dieselbe Funktion (`payments.record`) – bei der einen ruft ein
> Mensch, bei der anderen der Webhook. Ein Provider-Rahmen mit zwei Implementierungen
> wäre eine Abstraktion über einer Zeile.
> **Eine Referenz gehört zu genau EINER Zahlung im Haus**: am selben Beleg idempotent
> (der Dienst stellt mehrfach zu, ein Mensch erfasst denselben Auszug zweimal – zurück
> kommt die gebuchte Zeile), an einem **anderen** ein Irrtum mit **409 und der
> Auftragsnummer**, an der sie hängt. Ohne die Unterscheidung fand die Prüfung die fremde
> Zeile und gab sie zurück: `200`, nichts gebucht, der offene Betrag unverändert – und
> nichts sagte, warum. **Gefunden beim Messen, nicht beim Lesen** (die Fixtures des
> zweiten Messlaufs trugen die Referenzen des ersten). Ein stiller Nicht-Effekt ist
> schlimmer als ein Fehler; wer doch zweimal buchen muss, unterscheidet die Referenzen
> oder lässt sie leer.
> **`pay` hat darum keine Stufe** (wie `buy`): Geld fliesst, sobald zugesagt ist – und auch
> noch nach einem Storno, denn eine Anzahlung muss erstattet werden können.
>
> **Stripe ist zurück – dünn, und in die richtige Richtung** (`services/stripe_pay.py`,
> `docs/stripe-setup.md`). **Das ERP nennt Betrag und Währung, Stripe kassiert.** Im
> Vorgängersystem stand es wörtlich umgekehrt («Stripe ist Quelle der Wahrheit»), und
> daraus kam fast die ganze Komplexität: `stripe_*`-Snapshot-Spalten an vier Tabellen, ein
> Webhook, der **Aufträge erzeugte**, ein `CheckoutIntent` mit Reservierungen und ein
> Aufräumer für verlassene Warenkörbe. Heute schreibt der Webhook **eine Zeile Geld** und
> sonst nichts – kein Auftrag, keine Freigabe, keine Stufe. **Keine Reservierung, nirgends**:
> ein Shop-Kauf ist nichts anderes als eine Auftragsfreigabe, und sind die Stücke im selben
> Moment weg, meldet sie es – wie immer. **Ohne Schlüssel gibt es den Dienst nicht** (kein
> Stub, kein 503, kein Knopf); eine Überweisung ist kein Fallback, sondern der
> B2B-Normalfall. **Adaptive Pricing bleibt aus** – die eine Lehre, die unverändert gilt:
> sonst rechnete Stripe unseren Betrag mit seinem Kurs erneut um (angezeigt 11.80, belastet
> 11.82). Bewusst nicht: Stripe Tax · Customer Portal · Subscriptions · eingebettete Kasse.
> **Wiederkehr ist bewusst NICHT hier gebaut** (PROCESS_CORE §13.7): Wartung, Kalibrierung,
> monatliche Lieferung und ein Abo sind derselbe Fall – eine **Schlaufe mit Intervall im
> Prozess**. Im Vorgängersystem hing sie am *Preis* (`article_prices.kind` →
> `orders.recurrence_kind` → `_spawn_recurrence` → Auto-Fulfillment im Webhook → «Abos
> lassen sich nicht mischen»); steht sie im Prozess, muss der Verkauf von ihr nichts wissen
> und jedes andere Modul erbt sie.
> Wächter: `tests/test_sales_module.py` (19 Prüfungen, **jede gegen ihre Bug-Form
> gegengeprüft** – eine war dabei stumpf und liess ihre eigene Form durch: sie prüfte
> «ohne Zusage keine Fälligkeit», nicht «ohne **Frist** keine Fälligkeit»; gemessen,
> nachgeschärft, erneut gegengeprüft) + sieben in `test_frontend_mirrors.py`; zwei
> bestehende Wächter waren zu grob geworden und verboten die einzig richtige Lösung
> (ein geteilter `MODULE_FORM`-Eintrag, die durchgereichte `party_role`) – präzisiert und
> gegengeprüft. Suite grün gegen die gewachsene Datenbank **und** gegen ein Schema, das nur
> aus den Migrationen kommt; Migration `122` von null · idempotent · downgrade · über das
> Lifespan-Netz. Gemessen in Chromium: 1440 · 1280 · 1024 · 834 · 375 · 320 px, **0 px**
> waagrechter Überlauf über fünf Zustände der Zahlungszeile.

> **Altlasten-Bereinigung (August 2026) – was nicht gebraucht wird, ist WEG**
> (`docs/cleanup-2026-08.md`, `docs/attic.md`, Tag `attic/pre-cleanup-2026-08`).
> Der Basis-Neuaufbau hatte vier Bereiche liegen lassen (Verkauf/Shop · Dokumente · KI ·
> die Anbindungen für Zahlung/Versand/Datei-Ablage): abgeschaltet, aber vorhanden – und
> von einer **Ausnahmeliste im Wächter** umgangen, weil sie nicht einmal importierbar
> waren. Sie sind **gelöscht**, mitsamt dem Ereignis-Strom, den nach dem Neuaufbau kein
> Schreiber mehr füllte. Rund 11.500 Zeilen; was sie konnten und welche fachliche
> Entscheidung darin steckt, steht auf **einer Seite** (`docs/attic.md`).
> **Der Feature-Schalter geht mit.** Er hielt «an oder aus» an einer Stelle und meldete
> 503 mit Grund statt Schweigen – richtig, solange der Code da war und nur nicht laufen
> sollte. Jetzt gibt es nichts einzuschalten, und «abgeschaltet» zu melden, wo nichts
> existiert, ist eine Auskunft, die nicht stimmt; `404` ist die richtige. Der
> Frontend-Spiegel las ohnehin niemand (von keiner Seite aus erreichbar) und war in den
> Beschriftungen bereits abgewichen: ein Spiegel, den nur ein Test vergleicht.
> **Drei Funde, die das Löschen zutage gefördert hat.** (1) Der **Nummernraum** hing an
> einer Modellspalte (`DocumentFile.object_id` speiste `setval`, damit keine Nummer ein
> zweites Mal vergeben wird) – jetzt fragt er die **Registry**, die jede je vergebene
> Nummer hält, auch die eines Typs, den es nicht mehr gibt. Eine einzeln genannte
> Alt-Tabelle hätte man beim nächsten entfallenden Typ erneut nennen müssen.
> (2) Die Artikel-Spezifikation sendete bei **jedem** Speichern drei Gespenster-Felder
> (`procurement_mode` & Co.): gerendert war nie ein Feld dafür, gelesen hat sie seit dem
> Umbau des Beschaffen-Moduls niemand. (3) Die Navigation führte als **ersten Eintrag**
> auf `/shop` – eine Route, die der statische Export gar nicht kennt.
> **Die Alt-Palette ist auf 0.** `slate-*`, `blue-*`, `gray-*`, `#2563eb` und der
> `brand-*`-Vorrat sind entfernt; Blau als Link/Symbol-Chip wurde zur leisen Stimme
> (`accent`), Blau als CTA-Fläche zum Marken-Rot. **Gemessen, nicht geglaubt**: die
> öffentlichen Seiten in Chromium geprüft (Screenshot + Suche nach Text, dessen Farbe der
> Hintergrundfarbe entspricht) – und genau das fand den einen echten Fehler: `bg-dark`
> gibt es nicht, die Farbgruppe heisst `bg`, die Klasse also `bg-bg-dark`. Fünf dunkle
> Hero-Sektionen wären weiss auf weiss gewesen, und der Build hätte geschwiegen: eine
> unbekannte Tailwind-Klasse ist kein Fehler, sie erzeugt nur kein CSS.
> **Drei Namen für dieselbe Sache sind zwei zu viel** – `get_or_create_settings` →
> `primary` → `operator` ist auf `operator` eingedampft; die Docstrings sprachen dabei
> noch von «Hauptsitz» und «je Standort», Vokabular, das mit den gleichrangigen
> Gesellschaften abgeschafft wurde.
> **Die Frage «was liest eigentlich niemand mehr?» ist jetzt ein Werkzeug**
> (`backend/scripts/deadcode.py`), kein Tagewerk: Erreichbarkeit ab `app.main` bzw. ab den
> Next-Einstiegen, dazu Exporte ohne fremden Leser. Zwei Feinheiten, an denen eine naive
> Messung Lebendes als tot meldet, sind darin gelöst (ein Import führt jedes `__init__.py`
> aus; ein Paket, das seine Geschwister über `pkgutil` einsammelt, hat gar keine
> geschriebenen Importe).
> **Und die Sicherheitsnetze bleiben, was sie sind.** Gedroppt wurde in diesem Deploy
> **keine** Spalte: die Zwei-Deploy-Regel gilt, die Liste steht in `docs/backlog.md`. Aus
> `main.py` sind nur die **leeren** Netze entfallen (zwei leere Tupel samt ihrer
> Schleifen); jeder Eintrag, der eine Spalte schützt, steht unverändert – die Lehre aus
> Migration 090 ist teuer bezahlt.
> **Die 5.700 Zeilen Beschreibung des Vorgänger-Systems** sind aus dieser Datei heraus
> und liegen unverändert in `docs/history/2026-06-vorgaenger-system.md`. Sie beschrieben
> ein System, das es nicht mehr gibt – und `CLAUDE.md` liest **jede** Sitzung als Erstes.

> **Der Folge-Deploy – und zwei Vermutungen, die falsch waren** (Migration `120`,
> `docs/cleanup-2026-08.md` §5). Die Aufräumrunde hatte drei Punkte gemessen und liegen
> gelassen, weil sie **Verhalten** ändern statt aufzuräumen. Alle drei sind nachgezogen,
> und bei zweien war die im Bericht notierte Lösung **falsch** – das steht dort so, weil
> eine ungeprüfte Vermutung beim nächsten Mal als Tatsache gelesen wird.
> **(1) Die Zwei-Deploy-Regel ist einmal komplett durchlaufen**: 22 Spalten verloren im
> Aufräum-Deploy ihr Mapping und fallen jetzt. Die **Tabellen** der entfernten Bereiche
> bleiben bewusst stehen – eine Spalte, die niemand liest, kostet nichts; ein
> Tabellen-Drop kostet die Vergangenheit (`document_blobs` hält die Dateien selbst) und
> verlangt vorher eine Sicherung der **produktiven** Datenbank, die keine Migration
> ziehen kann.
> **(2) Die «freundliche Hälfte» lief doch** – nur über den Server. Der Befund «sie läuft
> gar nicht» war falsch: beide Entwürfe fragen `POST …/validate`, und `validate_draft`
> schickt die Modul-Konfiguration durch dieselbe `Module.clean_config`, an der auch die
> Freigabe abweist. Gemessen antwortet der Server «Lieferant 100000001 braucht eine
> Bestellangabe – seine Artikelnummer oder den Link…», wo die Browser-Fassung
> «Bestellangabe fehlt» sagte: die zweite war nicht nur doppelt, sondern **schlechter**.
> `moduleIncomplete` ist darum weg, und die zwei Wächter zeigen auf die **Regel** statt
> auf eine Zeichenkette – vorher prüften sie die *Anwesenheit einer toten Kopie*, schlugen
> also nicht an, obwohl sie keinen Aufrufer hatte, und hätten angeschlagen, wenn man sie
> entfernt. Einer war beim Gegenprüfen **stumpf** (`assert problems` war schon von der
> ohnehin gemeldeten fehlenden Einzelinstanz erfüllt) und prüft jetzt die **Differenz**.
> **(3) `minmax(0, 1fr)` war nicht der Fix** für den seitlichen Überlauf der Startseite:
> es lässt die Spalte schrumpfen, aber «Kernkompetenzen» ist bei `--h2` (dort 28 px) ein
> **unteilbares Wort von ~234 px** – der Überlauf wäre nur vom Raster in den Text
> gewandert. Der Abschnitts-Kopf steht jetzt unter 640 px **einspaltig** (dieselbe Grenze
> wie `.ix-wrap`; ein zweiter Wert wäre ein zweiter Umbruchpunkt, den man vergisst).
> Gemessen: **0 px** bei 1440 · 1280 · 1024 · 834 · 375 · 320 px, ab 640 px unverändert.

> **Der Einkauf im Bewegen-Modul: 1:1 sichtbar, mit Weg zurück — und «ausser Betrieb» ist
> keine eigene Angabe mehr** (Testnotizen #770–#775, PROCESS_CORE §9.8/§5.5,
> Migration `121`).
> **(1) Der Vorgang trägt seine eigene Identität** (`domain/procurement.LABEL`/`TONE`).
> Der Beleg war seit der Vorrunde 1:1 derselbe – **nur sah man es ihm nicht an**: er
> entstand im Hintergrund, und die Karte hiess weiter «Bewegen». Name und Farbe gehören
> darum dem **Vorgang**, nicht dem Modul, das ihn auslöst; das Modul «Beschaffen» **liest**
> sie, und der Beleg trägt sie mit sich (`PurchaseEmbed.label`/`tone`). Damit können die
> beiden nicht auseinanderlaufen, und die Ausführungsstelle schlägt nichts im Modul-Katalog
> nach – den lädt nur der Editor. Im Bewegen-Modul steht der Einkauf jetzt unter **seiner**
> Überschrift (getöntes Symbol · «Beschaffen» · Haarlinie – dieselbe Anatomie wie eine
> Modul-Karte, `ModuleMark` aus **einer** Quelle). **Nur wo der Einkauf nicht der Zweck
> ist** (`buys == BUY_IF_CHOSEN`): wo er es ist, sagt die Karte den Namen schon. Kein
> zweiter Rahmen – eine Karte in der Karte wäre die dritte Fläche. Und die Wahl heisst
> **«Selbst ↔ Beschaffen»**: «Einkaufen» war ein zweites Wort für dieselbe Sache.
> **(2) «Zurück» gibt es, BEVOR etwas zugesagt ist.** Der Knopf hing an `asked` – wer
> «Beschaffen» gewählt hatte, kam erst wieder heraus, **nachdem** er angefragt hatte, also
> ausgerechnet nicht dort, wo am wenigsten zugesagt ist. Es bleibt bei **einer**
> Gegenhandlung (`revoke`); was sie bewirkt, sagt die Stufe, und **wie sie heisst**, sagt
> der Beleg (`undo`: «Doch selbst erledigen» · «Anfrage zurückziehen» · «Bestellung
> stornieren»). **Dabei fiel eine Sackgasse auf:** nach einem **Storno** hatte die Stufe
> keine Handlung mehr, `assert_receivable` wies den Ziel-Scan mit 409 ab, und `ensure`
> fand die tote Zeile wieder – ein Transport, dessen Spedition absagte, konnte **nie** mehr
> stattfinden, auch nicht zu Fuss. Wer auch selbst kann, ist mit einem Storno wieder bei
> «selbst»: die Absage bleibt als Zeile stehen, sie ist nur nicht mehr *der* Beleg
> (`is_active = False`). **Eine** Ableitung (`_optional`), zwei Leser, kein zweiter Pfad –
> `assert_receivable` musste dafür nicht angefasst werden.
> **(3) Den Spediteur wählt man, wenn man weiss, wohin.** Die Lieferanten-Freigabe ist bei
> einem Transport **leer** («leer heisst frei»), und `Ask` rendete nur diese Liste: es stand
> **nichts** zum Anklicken da, der Knopf blieb gesperrt. Wo niemand zugelassen ist, wird
> jetzt gesucht (`/orders/supplier-options`, dasselbe `ObjectSelect` wie überall) – derselbe
> Knopf, dieselbe Aktion, nur eine andere Quelle. **Frei heisst nicht «irgendwer»**:
> `_assert_allowed` verlangt dort einen aktiven Lieferanten, sonst wäre die Liste eine Bitte.
> **(4) «Ausser Betrieb» ist die FOLGE des Ersetzens** (#773, Migration `121`): der Schalter
> ist entfallen, `Article.status` ist eine **Projektion** von `replaced_by_id` statt einer
> Spalte, und `may_create` liest die Tatsache. Die Spalte wurde von **zwei** Stellen gesetzt
> und von einer gelesen – ein von Hand stillgelegter Artikel **ohne** Nachfolger hing damit
> an genau dem Schalter, der ihn stillgelegt hatte. Die Migration heilt genau diese Zeilen
> (gemessen: von Hand inaktiv → freigegeben, abgelöst → bleibt inaktiv). **Der eine Preis,
> ausdrücklich abgenommen:** ein abgelöster Artikel erzeugt nichts Neues mehr – auch nicht
> als Ersatzteil (#766 ist damit zurückgenommen); wer den Vorgänger weiterbauen will,
> ersetzt ihn nicht. «Ab Lager» bleibt erlaubt. *Nebenbei geschlossen:*
> `articles.replaced_by_id` gab es in **keiner** Migration – sie kam nur über das
> Lifespan-Netz; `121` legt sie an, denn die Migration ist die Wahrheit.
> **(5) Ein Modul zeigt seine Sache in JEDEM Zustand – jetzt auch am Artikel** (#771):
> `renderStep: frozen ? undefined` liess im freigegebenen Prozess **gar keinen** Körper
> übrig – der Kopf klappte auf, und darin war nichts. Es ist derselbe Feldsatz, nur gesperrt
> (`fieldset[disabled]`, eine Zeile statt eines zweiten Layouts); möglich durch die
> **Umkehrform** derselben Zuordnung (`MODULE_FORM[…].draft`), die neben ihrem Gegenstück
> steht. Gemessen: der Weg `config → Entwurf → config` ist für **alle fünf** Modultypen die
> Identität, inklusive tolerantem Lesen der alten Lieferanten-Form.
> **(6) Die Menge kann nicht mehr null werden** (#774): ein geleertes Feld hiess `0` – also
> genau der Wert, den der Server als «ist zu klein» abweist; die Meldung kam nicht aus einem
> Fehler, sondern aus dem Tippen. Jetzt lebt die Eingabe während des Tippens lokal (leer ist
> ein Zwischenzustand), übernommen wird beim Verlassen, Untergrenze 1. **Nur** die
> Untergrenze: eine zu grosse Zahl ist eine Entscheidung, und dazu gehört der Satz des
> Servers. Gemessen: leer → 1, «7» → 7, «0» → 1.
> **(7) Kleineres:** der Bestand steht am Artikel **zwischen Spezifikation und Prozess**
> (#770 – erst was er ist, dann was es davon gibt, dann wie er entsteht); der Reiter
> «Dokumente» am Benutzer ist **vollständig entfernt** (#772 – zwei Überschriften über
> leeren Flächen; übrig blieb ein Reiter, der das ganze Formular trägt, also gibt es nichts
> mehr zu wählen).
> Wächter: `tests/test_purchase_module.py` (4 neue), `test_invariants.py` (2 neu
> formuliert), `test_article_lifecycle.py` (3 auf die neue Regel gezogen),
> `test_frontend_mirrors.py` (7 neue) – **jeder gegen seine Bug-Form gegengeprüft**; einer
> war dabei stumpf (er fragte nach `*article*.status =` und liess ausgerechnet
> `predecessor.status = …` durch) – gemessen, nachgeschärft, erneut gegengeprüft. Suite
> grün gegen die gewachsene Datenbank **und** gegen ein Schema nur aus den Migrationen
> (458); Migration `121` von null · idempotent · downgrade · über das Lifespan-Netz, ihre
> **Wirkung** gemessen. Gemessen in Chromium: 1440 · 1280 · 1024 · 834 · 375 · 320 px,
> **0 px** waagrechter Überlauf, nichts ragt aus der Prozessspur.

> **Testnotizen #775–#777: der Einkauf ist EIN Vorgang – überall gleich.** Drei Notizen,
> und der rote Faden ist derselbe: der Beleg am **Bewegen**-Modul verhielt sich anders
> als der am **Beschaffen**-Modul – er sah anders aus, liess sich nicht zurücknehmen wie
> er entstand, und wurde an einer anderen Stelle definiert, nämlich gar nicht.
> **(1) Ein Schalter hat zwei Richtungen** (#775): er stand fest auf `self` und
> **verschwand**, sobald ein Beleg entstand – das Bedienelement, mit dem man die
> Entscheidung getroffen hat, war weg, und der Weg zurück lag woanders (`revoke` **im**
> Beleg). Der Dienst konnte das längst: `buy → revoke → buy` läuft über die echten Pfade
> fehlerfrei durch (der partielle Unique-Index aus Migration 119 trägt), es war
> ausschliesslich die Oberfläche. Jetzt ist der Wert **abgeleitet**
> (`purchase ? 'bought' : 'self'`), beide Richtungen sind verdrahtet, und **ob es
> zurückgeht, sagt der Server** (`revoke ∈ purchase.can` – dieselbe Tabelle Stufe × Rolle,
> die auch das Tor ist). Eine Heuristik «hat hier schon jemand etwas eingegeben?» wäre die
> zweite, mildere Antwort. Ist die Wahl nicht mehr umkehrbar, **bleibt der Schalter
> stehen** – gesperrt, mit Grund im Hover: sonst beantwortet nichts mehr, was gewählt war.
> **(2) Der ganze Bereich trägt die Farbe seines Vorgangs** (#776) – als **Haarlinie**,
> nicht als Fläche: eine getönte Karte wäre die dritte (Modul-Karte → Beleg-Karte →
> Stufen-Zeile), und «Struktur vor Fläche» ist die ERP-Regel des Hauses.
> **(3) Was ein Beleg beim Definieren braucht, deklariert das Modul** (#777) – und die
> Antwort ist **nicht**, den abgeleiteten Satz editierbar zu machen: «Transport von A nach
> B» kennt der Vorgang selbst (Herkunft = heutiger Halter, Ziel = Modul-Ziel), ein
> Eingabefeld daneben wäre die zweite Aussage, und die getippte gewänne auch falsch. Was
> fehlte, ist das, was **nur ein Mensch weiss** («Hebebühne nötig», «nur werktags») – und
> dafür hat das Beschaffen-Modul längst ein Feld. Also tragen **beide** Module dieselben
> zwei Beleg-Angaben (`suppliers`, `instruction`); sie sind an `Module` gewandert, nicht an
> eine Klasse, und der Unterschied ist eine **Deklaration**: `suppliers_required` /
> `instruction_required` (Beschaffen: beide Pflicht, nichts ist ableitbar · Bewegen: beide
> freiwillig – wer fährt, entscheidet sich zur Laufzeit, und *was* zu tun ist, steht im
> abgeleiteten Satz). Zur Laufzeit ist der Auftrag **abgeleitet · ergänzt**, eine Formel
> mit zwei Summanden (`instruction_for` ← `derived_instruction`). Im Editor hängt der
> Block an **`buys`** statt an einer Liste von Modultypen: ein neuer einkaufender Typ
> bekommt ihn, ohne dass jemand das Frontend anfasst. `MODULE_FIELDS` trägt darum
> `beschaffen: null` – ausser seinem Beleg hat es nichts zu konfigurieren.
> Wächter: `test_purchase_module` (3 neue) + `test_frontend_mirrors` (2 neue, einer
> umgeschrieben) – **jeder gegen seine Bug-Form gegengeprüft**. Der umgeschriebene suchte
> wörtlich nach `if (purchase)` und prüfte damit die **Form** des Codes statt die Regel;
> er fragt jetzt, ob die Oberfläche wieder einen Modultyp nennt.

> **Testnotizen #784–#790 — was etwas IST, sagt es selbst; was es TUT, sagt es beim
> Hinsehen.** Sechs Notizen, und dreimal war die Ursache dieselbe: eine Angabe, die eine
> Oberfläche sich **ausrechnete** oder **danebenschrieb**, statt sie zu lesen.
> **(1) «Kundeen» — der Plural ist eine ANGABE, keine Rechnung** (#787,
> `Flow.party_plural`). Er wurde aus `party_word` gebaut: «Lieferant» + «en» =
> «Lieferanten» ✓, und beim Verkauf kam «Kundeen» heraus. Deutsche Beugung ist keine
> Zeichenkettenoperation – eine Regel, die bei **einem** Wort zufällig stimmt, ist keine.
> Er steht jetzt da, wo die übrigen Wörter dieser Richtung stehen, und reist mit.
> **Und die Bestellangabe gibt es nur, wo wir bestellen** (`Flow.party_ref`): sie
> beantwortet «wie bestelle ich bei ihm» – seine Artikelnummer, sein Shop-Link. Beim
> **Verkauf** liefern **wir**; das Feld stand dort als **Pflicht**angabe da, die niemand
> ausfüllen kann. Eine Eigenschaft der **Richtung**, nicht des Modultyps – jeder künftige
> Typ derselben Richtung erbt sie. Ein Wert, der trotzdem ankommt, wird **verworfen**:
> ein Feld, das die Oberfläche nicht anbietet, der Dienst aber annimmt, wäre eine
> Hintertür zu einer Angabe, die niemand liest.
> **(2) «Beim Ausführen definieren» — ein Satz, eine Stelle** (#785/#786,
> `scan.RUNTIME_CHOICE`). Dieselbe Aussage stand in zwei Fassungen nebeneinander: am Ziel
> des Bewegen-Moduls als Listen-Zeile «Beim Ausführen **scannen**», unter der
> Gegenpartei-Liste als Erklärsatz «Leer: freie Wahl beim Ausführen» – und der zweite war
> nicht einmal anklickbar, also genau die Form, in der man eine Wahl nicht wählen kann
> (#734–#736). *Scannen* ist zudem nur **einer** von zwei Wegen zur selben Wahl (daneben
> steht die Tastatur, und bei den zugelassenen Gegenparteien wird gar nicht gescannt):
> ein Wort, das den **Weg** nennt statt den **Zeitpunkt**, ist an der Hälfte der Stellen
> falsch. Auch die Laufzeit-Anzeige liest jetzt denselben Satz – ein Zustand, zwei
> Formulierungen wären zwei Aussagen.
> **(3) Eine Objektnummer ist eine KENNUNG, kein Hyperlink** (#784, `.erp-objid`). Blau,
> fett und unterstrichen sind die drei Marker, an denen man im Web einen Link erkennt –
> und im ERP steht diese Nummer in fast **jeder** Zeile: das Raster las sich als
> Linkliste, und die Kennung war die lauteste Angabe darin. Im Ruhezustand trägt sie
> darum die Farbe ihres Textes; dass sie führt, sagt der Zeiger und – sobald er darauf
> steht – Farbe **und** Unterstreichung (Farbe allein ist kein zugängliches Signal, WCAG
> 1.4.1), `:focus-visible` deckt den Tastaturweg. **Fett bleibt beides**: das ist die
> Auszeichnung der Kennung, kein Link-Marker – die Form ist dieselbe wie bei einer Nummer
> ohne Ziel (#282), und die Auszeichnung kommt allein aus der Klasse, denn inline greift
> kein `:hover`.
> **(4) Die Historie gilt für die KOPFZEILE, nicht für das Symbol** (#790). Sie hing am
> 32-px-Quadrat links – man musste es treffen, um zu erfahren, was an diesem Modul
> passiert ist. Die Kopfzeile ist der Container: sie läuft über die ganze Kartenbreite,
> und zugeklappt – der Normalfall – **ist** sie die Karte (gemessen: 1386 px statt 32 px
> Zielfläche bei 1440 px Fenster). Bewusst **nicht** der äussere Rahmen, obwohl der
> wörtlich «der ganze Container» wäre: darin steht der aufgeklappte Feldsatz, und eine
> Blase, die beim Tippen in einem Eingabefeld aufgeht, ist Störung statt Auskunft. Was
> **darin** eine eigene Blase trägt (Ziehgriff, Schloss, Löschen), gewinnt weiterhin –
> die Regel dafür steht in `globals.css` (`:has`), nicht am Bauteil. Die alte Warnung
> gilt unverändert: **nie an der Beschriftung**, die trägt `truncate`, und
> `overflow: hidden` schneidet ein `::after` weg.
> **(5) Die Bestandsleiste NENNT ihre Zustände – und ist das Bedienelement** (#789,
> PROCESS_CORE §10.3). Gemeldet war zweierlei: die Leiste zeigt nicht, wie viele Stücke
> je Kategorie – «gerade bei gleichfarbigen Status» –, und die Liste darunter ist zu
> lang. Es ist **ein** Befund. Der Katalog kennt **drei** Ampeltöne für **sechs**
> Zustände eines Stücks (*Freigegeben*, *Verbaut*, *Verkauft* sind alle grün, *Im
> Prozess* und *Gesperrt* beide gelb): zwei gleichfarbige Segmente nebeneinander sind
> **strukturell** nicht unterscheidbar, und keine Feinabstimmung des Tons ändert daran
> etwas – das **Wort** ist die Unterscheidung. Also stehen Punkt, Wort und Menge unter
> der Leiste **als Teil von ihr**, eine Haarlinie trennt die Segmente, und die
> Beschriftung ist zugleich die Auswahl. Damit ist die Liste aufklappbarer Sektionen
> **ersatzlos entfallen**: ihr Kopf sagte Zeile für Zeile das, was die Leiste eine Zeile
> höher schon zeigte, nur zwanzigmal höher. *Das ist kein Rückschritt hinter #716,
> sondern sein zweiter Schritt* – dort wurde eine Legende **neben** den Gruppen entfernt,
> also die Doppelung, nicht die Beschriftung; jetzt gibt es nur noch eine Fassung.
> **Genau EINER ist offen**, und zu Beginn keiner (dieselbe Regel wie #716): zwei
> Zustände gleichzeitig zu betrachten war der Grund, warum es Sektionen gab – und nie
> eine Frage, die jemand hatte. **Kein Filter**: was man nicht anklickt, steht weiterhin
> in der Leiste.
> **Nicht umgesetzt und bewusst offen: #788** (die Kettenregel beim Verkauf-Modul mit
> nachfolgendem Bewegen). Ausdrücklich zurückgestellt – die bestehende Logik bleibt.
> Wächter: fünf neue in `test_frontend_mirrors.py`, zwei umgeschriebene, einer in
> `test_purchase_module.py` präzisiert – **15 Bug-Formen gegengeprüft**, jede meldet.
> *Zwei der neuen waren dabei stumpf und liessen ihre eigene Form durch*: einer fragte
> nach dem **Vorkommen** von `cfg.label` und war schon durch den Hover-Text erfüllt, den
> es vorher auch gab; der andere prüfte `useState<string | null>(null)`, was in derselben
> Datei auch für die Fehlermeldung dasteht. Gemessen, nachgeschärft, erneut gegengeprüft.
> Suite grün gegen die gewachsene Datenbank (497) **und** gegen ein Schema nur aus den
> Migrationen (505). Gemessen in Chromium an den **echten** Komponenten: 1440 · 1280 ·
> 1024 · 834 · 375 · 320 px, **0 px** waagrechter Überlauf, sechs Zustände in der Leiste,
> nie zwei Ausschnitte offen, Blase an der Kopfzeile, Nummer ruhend unausgezeichnet und
> beim Zeigen `#2C6E8F` + Unterstreichung. *Die Messung hat sich dabei einmal selbst
> getäuscht: `transition: color .12s` – wer sofort misst, misst den Startwert des
> Übergangs.*

> **Das siebte Modul ist «Zahlung» — Geld mit einer zweiten Partei, und es steht KOMPLETT
> für sich** (PROCESS_CORE §9.12, Migration `124`). Die Frage dahinter war nicht «wie baue
> ich den Verkauf besser», sondern: **was haben Einkauf, Verkauf, eine eingekaufte
> Spedition, eine Leistung ohne Artikel und eine Vorauszahlung gemeinsam?** Nicht die
> **Ware** – die ist in jedem Fall eine andere. Sondern: **es fliesst Geld, und eine zweite
> Partei ist beteiligt.**
> **Die eine Regel, aus der die Robustheit folgt: das Modul bewegt keine Stücke.** Ein
> Durchläufer (`Im Prozess` → `Im Prozess`), `terminal = False`, `moves = False`,
> `buys = None`, kein Ortswechsel, kein neuer Status. Damit muss **keine andere Regel im
> System von ihm wissen** – keine Kettenregel, keine Statusliste, keine Bestandsansicht,
> keine Zeile in der Prozess-Engine; die Robustheit ist konstruktiv statt geprüft. Was
> physisch geschieht, sagen die Nachbarn: kommissioniert und ausgeliefert wird mit
> «Bewegen», ausgesondert mit «Aussondern». *Ein Verkauf besteht damit aus zwei Modulen
> statt aus einem, und das ist der Preis – der richtige: sobald dieses Modul auch Ware
> bewegte, bräuchte jede Kombination aus Geld und Ware wieder einen eigenen Fall, also
> genau die Lage, aus der es entstanden ist.*
> **Vier Angaben, und die erste entscheidet alles**: `direction` (Geld kommt ↔ Geld geht –
> daraus folgt **jedes Wort**), `parties` (zugelassene Gegenparteien, **leer heisst frei**),
> `subject` (worum es geht – Pflicht) und `prepaid` (erst weiter, wenn bezahlt). **Keine
> Menge** (die Zahl der Einzelinstanzen davor), **kein Artikel** (den tragen die Stücke),
> **kein Termin** (ableitbar) und **kein Betrag**: beim Modellieren steht er nicht fest, ein
> hier getippter wäre bei der zweiten Ausführung falsch – und zwar stillschweigend.
> **Die Richtung ist eine EINSTELLUNG, kein zweiter Modul-Schlüssel** – EIN Modul, EINE
> Kachel. Sie friert mit der Freigabe ein und reist mit dem Schritt, ist also so haltbar wie
> ein Schlüssel; am **Vorgang** wird sie zusätzlich festgeschrieben (`deals.direction`), denn
> läse er sie bei jeder Anzeige neu, änderte ein späterer Umbau **rückwirkend**, was ein
> alter Vorgang bedeutet.
> **Zwei Achsen, und darum kein einziger Modus** (`deals` = die Zusage, `deal_entries` =
> Forderungen **und** Zahlungen, Betrag darf negativ sein): Vorauszahlung, Anzahlung,
> Teilzahlung, Gutschrift und Erstattung sind dieselbe Mechanik in anderer **Folge**.
> *berechnet · bezahlt · offen · noch nicht berechnet* sind Ableitungen, **null Spalten** –
> eine gespeicherte «offen»-Spalte wäre die zweite Wahrheit. Und **`prepaid` fragt nach der
> ZUSAGE, nicht nach dem offenen Betrag**: direkt nach der Zusage ist *offen* null, weil
> noch **nichts gefordert** wurde – dieselbe Zahl, eine ganz andere Aussage.
> **`can` ist Auskunft UND Tor** (`services/deal.ACTIONS`): dieselbe Tabelle zeigt die
> Knöpfe und weist in `apply` ab. Geld darf ab der Zusage in **jeder** Stufe fliessen, auch
> nach dem Storno – eine Anzahlung muss erstattet werden können; und der Storno **behält
> seinen Weg**: er macht die Zusage nicht ungeschehen, er sagt nur, dass nichts mehr kommt.
> **Vollständig eigenständig, und das ist die Anforderung**: eigene Vokabel
> (`domain/deal`), eigener Dienst (`services/deal`), eigene Tabellen, eigene Endpunkte –
> **kein Import** aus `procurement`/`purchase`/`invoices`/`payments`. Wer «Beschaffen» und
> «Verkauf» eines Tages ersatzlos löscht, fasst hier keine Zeile an; ein Quelltext-Wächter
> hält es so. Die drei Berührungspunkte im Rahmen sind je **eine Zeile** und alle
> no-op ohne dieses Modul: Anlage bei der Freigabe, Sperre vor `confirm_step`, Abschluss
> danach.
> **Zwei Funde beim MESSEN, nicht beim Lesen:** (1) unsere Rechnungsnummern zählten fremde
> Belege mit – die erste eigene hiess «…-2», und eine Nummernserie mit Lücken ist
> buchhalterisch keine; (2) in der Beleg-Zeile war die **falsche Zelle flexibel**: das Datum
> bekam den Rest und behielt bei einer 227 px breiten QR-Referenz **39 px** – «20.8.2026»
> hat keine Umbruchstelle und malte sich 17 px über seine Box hinaus (gemessen 380,1 px bei
> 375 px Fenster, und **kein Element-Rahmen zeigte es, nur der Text selbst** – die
> Messung musste dafür nachgeschärft werden). Jetzt nimmt die **Referenz** den Rest und wird
> gekappt (voller Wert im Hover), das Datum nie.
> Wächter: `tests/test_deal_module.py` + `test_frontend_mirrors.py`; ein bestehender Wächter
> prüfte die **Form** der alten Lösung (Position von `<Wrapped` gegen `{isActive ?` im ganzen
> Rumpf) und schlug an, obwohl die Regel besser erfüllt war – er fragt jetzt den
> **gerenderten Baum**. Migration `124` von null · idempotent · downgrade · über das
> Lifespan-Netz verifiziert.
> *Nachtrag: `subject` ist inzwischen **freiwillig**, es gibt **zwei** Stufen statt drei, und
> die Gegenpartei hat einen eigenen Zugang – siehe die Runde unten.*

> **Der Geldvorgang hat ZWEI PARTEIEN — und was gehandelt wird, sagt der Prozess**
> (Testnotizen #791–#797, PROCESS_CORE §9.12, Migration `125`). Die Datenstruktur stimmte,
> der **Vorgang** nicht: die Karte war ein Buchungsformular statt eines Geschäfts zwischen
> zwei Parteien, sie sagte nicht, worum es geht, obwohl der Prozess es weiss, und sie zeigte
> **Werkzeuge statt eines Weges**.
> **Der Angebotsspiegel ist der Kern** (`deals.quotes`): wir fragen an bzw. bieten an, die
> Gegenpartei nennt ihren Preis oder sagt ab, wir geben den Zuschlag. **Eine Liste, auch wenn
> fast immer einer drinsteht** – n statt 1, damit der Vergleich kein zweiter Mechanismus ist;
> «gewählt» entsteht nicht durch Tippen, sondern dadurch, dass bei dieser Zeile zugesagt
> wurde. **Steht genau eine Gegenpartei in der Definition, gibt es nichts zu wählen** (#793):
> dann heisst der Knopf schlicht «Anfragen». Geändert wird eine Zeile durch **Neubau**, nie
> an Ort – ein mutierter JSONB-Wert fällt aus dem `UPDATE`, und die Offerte ist
> stillschweigend weg.
> **Worum es geht, ist ABGELEITET** (`lines`): je Artikel, dessen Einzelinstanzen im Auftrag
> stehen, eine Zeile mit Menge und Nummer – mehrere sind der Normalfall, und es braucht dafür
> keine Regel, nur eine Gruppierung. Die **Spezifikation reist mit** (erst auf Klick: im
> Normalfall interessiert die Zeile, nicht das Datenblatt) und wird **nicht ausgewählt** –
> eine Spezifikation, die je nach Empfänger anders lautet, ist keine. Mit der Zusage friert
> sie ein (`agreed_lines`): ab dort ist eine zweite Partei gebunden.
> **Damit wurde `subject` freiwillig** (#796): *was* gehandelt wird, sagt der Prozess; der
> Satz sagt, was **daran** zu tun ist, und das gibt es nicht bei jedem Vorgang. Ein
> Pflichtfeld, das oft nichts aufzunehmen hat, lädt zu einer Eingabe ein, die niemand liest.
> **Es gibt ZWEI Stufen, nicht drei.** Unumkehrbar sind zwei Dinge – nichts zugesagt ·
> zugesagt; «Abgeschlossen» stand als dritte da und war ein **Zustand** in einer Reihe von
> **Schritten**: man tut nichts, um ihn zu erreichen. Die dritte Zeile ist das **Geld**, und
> es ist bewusst keine Stufe (eine Zahlung macht aus einem Angebot keine Zusage, und sie darf
> vor der Erfüllung stehen wie danach). Das Verb der Schwelle heisst in **beiden** Richtungen
> «Auftrag bestätigen» – was passiert, ist dasselbe.
> **Eine naheliegende Handlung, und der Server sagt welche** (`next_charge` ↔ `next_payment`):
> erst fordern, dann kassieren; alles Übrige liegt unter «Weitere». Drei gleich laute Knöpfe
> sind kein Vorschlag. **Und keine Vorgabe ist je negativ** (#795) – «−250.00» stand als
> Rechnungsbetrag im Feld; eingebbar bleiben negative Beträge, das ist die Gutschrift.
> **Der Zugang der Gegenpartei ist ein ZUGANG, keine Rolle im Vorgang**: wer angefragt ist
> und nicht ins ERP darf, sieht **seine** Zeile und keine Zahl über Forderung und Geld –
> gefiltert beim **Aufbau der Antwort**, nicht in der Oberfläche. **Ein Mitarbeiter behält
> die volle Sicht, auch wenn er selbst die Gegenpartei ist**: die Frage lautet «darf dieser
> Betrachter ins ERP?», nicht «kommt seine Nummer im Vorgang vor» – sonst verlöre ein
> Einkäufer, den man einmal selbst anfragt, an genau diesem Auftrag die Zahlen, die er zum
> Arbeiten braucht.
> **Kein Scan** – ein Geldvorgang bewegt keine Stücke, es gibt nichts zu verifizieren, und
> ein Scan davor wäre ein erfundenes Hindernis. Die Frage steht am Modul
> (`Module.requires_verification`) und reist als `ModuleFacts.verifies` mit dem Schritt: die
> Ausführungsstelle nennt keinen Modultyp, und jedes künftige Modul ohne physisches
> Gegenstück erbt die Regel ohne eine Zeile.
> **Kleineres, jedes an genau einer Stelle:** der Entwurf beginnt als **Einnahme** (#791 –
> ein Schalter, der auf nichts steht, ist keine Frage, sondern eine Lücke, die der Server
> still füllt); der **Erklärsatz** unter den Feldern ist gelöscht (#792 – er sagte, was das
> Feld darüber zeigt); die **Richtung** steht als Symbol mit Hover statt als Dauertext (#797
> – Plus und Minus sind die Buchhaltungssprache selbst); die **gewählte Gegenpartei** wird
> gehalten und mit Nummer **und** Namen gezeigt (#794 – sonst stand das Feld nach dem Klick
> leer da, weil die Wahl noch nicht gespeichert war).
> **Und die MESSUNG musste nachgeschärft werden – in beide Richtungen.** Sie zählte
> Textknoten, um den Fehler von #790 zu finden (eine Zeile, die sich über ihre eigene Box
> hinaus malt, und **kein** Element-Rahmen zeigt es). Genau daran meldete sie jetzt 20,5 px
> bei 375 px – an einem `truncate`-Text, der wirklich **abgeschnitten** wird: eine Textbreite
> hinter `overflow: hidden` ist unsichtbar, kein Überlauf. Die Textbox wird darum an jedem
> schneidenden Vorfahren gekappt; **gegengeprüft**, dass die Bug-Form von #790 danach
> weiterhin meldet (45 px bei 320 px). Eine Messung, die die Lösung als Fehler meldet, ist so
> falsch wie eine, die den Fehler übersieht.
> Wächter: `tests/test_deal_module.py` (24 Prüfungen) + sieben neue in
> `test_frontend_mirrors.py` (zwölf insgesamt zum Geldmodul) –
> **jeder neue gegen seine Bug-Form gegengeprüft**; ein bestehender prüfte die **Form** der
> alten Lösung (`DEAL_STAGE.agreed` musste wörtlich vorkommen) und verbot damit die bessere
> Fassung – er fragt jetzt die **Regel**: kein Stufen-Wort im Rumpf. Suite grün gegen die
> gewachsene Datenbank (540) **und** gegen ein Schema nur aus den Migrationen (540);
> Migration `125` von null · idempotent · downgrade · über das Lifespan-Netz. Gemessen in
> Chromium an der **echten** Komponente: 1440 · 1280 · 1024 · 834 · 375 · 320 px, **0 px**
> waagrechter Überlauf über **sechs** Zustände (inkl. der Sicht der Gegenpartei); sie sieht
> **0** fremde Preise und **0** Zahlen über Geld, der erledigte Vorgang zeigt alles und hat
> **0** Handlungen.

> **Der Zugang zum MODUL war nicht eingeschränkt — nur der zum Auftrag** (Testnotizen
> #798–#801). Die Vorrunde hat die Gegenpartei aus dem *Auftrag* ausgeschlossen und ihr *im
> Modul* alles gelassen. **Gemessen über die echten Dienstpfade**, nicht gelesen: ein
> unterlegener Lieferant las nach dem Zuschlag an einen anderen dessen **Namen**, dessen
> **Preis**, Zahlungsfrist und Zusagedatum – und dazu die **Freigabe-Liste**, also die
> Konkurrenzliste selbst; das Wort «Auftrag stornieren» stand an einem Knopf, den es für
> ihn nie gibt.
> **Die Regel ist dieselbe wie beim Beschaffungs-Beleg** (`won`), und sie steht hier wörtlich
> gleich, obwohl die beiden Module bewusst keine Zeile Code teilen: *zwei Formen einer Regel
> sind in Ordnung; zwei Regeln nicht.* Die Freigabe-Liste fällt für **jede**
> Nicht-Personal-Sicht ganz weg, die Zusage für jede, die sie nicht selbst bekommen hat, und
> `undo` hängt an **`can`** statt an der Stufe.
> **Und sie sah ihre Aufträge in KEINER Liste.** `list_orders` fragte nur `purchase.mine` –
> das Detail fragte beide (`_visible`). Der Auftrag eines Geldvorgangs war damit nur über die
> direkte Adresse erreichbar (gemessen: `deal.mine` fand ihn, der Feed-Filter war leer).
> Beide lesen jetzt **eine** Ableitung (`orders._involved`); zwei Ableitungen derselben Frage
> laufen genau so auseinander. **Die Bestätigung fällt für sie weg** (`confirm_step` ist
> Personal-only): sie hängt an `internal` – der Aussage der Aufrufstelle über sich selbst –,
> nicht an einer Rollenabfrage, und die Regel gilt damit für **jedes** Modul.
> **Ein blosser `.erp-actbtn` ist kein Knopf** – das war die Ursache von «die Buttons sind
> nur Text», nicht der Geschmack: die Basisklasse hat `border: 1px solid transparent` und
> keine Fläche, erst `-primary`/`-neutral`/`-danger` machen daraus einen sichtbaren Knopf.
> `purchase-work` vergibt an jedem Knopf eine Ausprägung, `deal-work` an keinem. Jetzt trägt
> jeder eine – und **«Weitere» ist entfallen**: ein Auswahlmenü ist die richtige Form für
> viele gleichrangige Dinge, hier waren es drei, und eines davon (der Storno) ist die
> Gegenhandlung des ganzen Vorgangs. **Was man jetzt tun kann, muss man sehen**; welches das
> naheliegende ist, sagt die **Fläche** des Knopfes, kein Klick, der es erst hervorholt.
> **Die Bestellangabe gab es im Geldmodul gar nicht** – und die Begründung dafür war falsch:
> «wie bestelle ich bei ihm» ist keine Eigenschaft *von ihm*, sondern der **Paarung** Modul ×
> Gegenpartei (derselbe Lieferant führt je Teil eine andere Nummer). Sie steht jetzt wie beim
> Beschaffen-Modul in der Definition (`config.parties[].ref`) und zur Laufzeit an **seiner**
> Angebotszeile; **nur wo wir bestellen** (`Direction.party_ref` – beim Verkauf liefern wir),
> und ein trotzdem gesendeter Wert wird **verworfen**.
> **#799 Das Symbol bildet ab, was man TUT**: Einkaufswagen ↔ Handschlag – **dasselbe Paar
> wie der Handel** (`FLOW`), ein Haus, eine Bildsprache. Plus und Minus waren die
> Buchhaltungssprache, aber nicht die dessen, der davorsteht, und auf 15 px kaum
> unterscheidbar. **#798 Punkt und Wort teilen EINE Zeilenhöhe** statt zweier geratener
> Abstände (gemessen: Δy 0,0 px über alle sechs Zustände; die Bug-Form meldet 2 px).
> **#800** Offerte und Absage sind Symbol-Knöpfe wie im Beschaffungs-Beleg – «Offerte»
> beschreibt einen *Zustand*, der Knopf löst eine *Handlung* aus. **#801 Das Modul-Protokoll
> sagt jetzt, was es ist**: ohne Überschrift stand dort eine Einzelinstanz mit einem Namen
> und einer Uhrzeit, und die Frage «warum steht die hier?» war berechtigt. **Entfernt wird es
> nicht** – es ist der Nachweis, und bei einem Modul, das am Stück nichts ändert, bleibt
> genau das übrig: wer wann was bestätigt hat.
> **Und die aktive Zeile ist die lauteste**: gefüllter Punkt in der Akzentfarbe, Beschriftung
> in Versalien – wo man steht, sagt die Karte ohne ein Wort mehr.
> Wächter: 12 neue (7 in `test_frontend_mirrors.py`, 2 in `test_deal_module.py`, dazu die
> geschärften) – **jede Bug-Form gegengeprüft**; *einer war dabei stumpf und liess seine
> eigene durch* (er fragte, ob beide Klassennamen im Rumpf vorkommen, und war schon durch den
> Papierkorb-Knopf erfüllt) – er prüft jetzt die **Wahl** selbst. Ein bestehender verlangte
> wörtlich «Weitere» und hätte damit die bessere Lösung verboten; er fragt jetzt die Regel.
> Suite grün gegen die gewachsene Datenbank (548) **und** gegen ein Schema nur aus den
> Migrationen (548). Gemessen in Chromium an der **echten** Komponente: 1440 · 1280 · 1024 ·
> 834 · 375 · 320 px, **0 px** waagrechter Überlauf über sechs Zustände; der erledigte
> Vorgang hat **0** Handlungen, die Gegenpartei sieht **0** fremde Preise.

> **Das Geldmodul spricht EINE Sprache — und ein Feld weniger ist besser als ein
> optionales** (Testnotizen #802–#815). Fast alle vierzehn Notizen sagen dasselbe aus zwei
> Richtungen: die **Wörter hingen an der Richtung**, obwohl die Sache dieselbe ist («ich
> mag hier kein if else mehr»), und **optionale Felder sind schlimmer als keine** («ich bin
> sowieso kein Fan von optionalen Feldern»).
> **Ein Wort statt zweier:** «Kunde» ↔ «Lieferant» ist dieselbe Rolle – der andere im
> Geschäft – und heisst jetzt **Partner** (`deal.PARTY`); **Singular = Plural**, womit
> «Kundeen» (#787) *strukturell* erledigt ist statt durch einen zweiten gepflegten Wert.
> «Einnahme» ↔ «Ausgabe» heisst **Verkauf** ↔ **Einkauf** – dieselben Wörter und Symbole
> wie beim Handel (`FLOW`); im Editor «Geschäft» statt «Richtung» (#804) und **«Weiter,
> wenn» · zugesagt ↔ bezahlt** statt «Abschluss · Jederzeit» (#806/#807 – Beschriftung und
> Werte lesen sich als Satz). `Direction` trägt nur noch, was wirklich verschieden ist.
> **Ein Pflichtfeld statt zweier optionaler** (#805/#808/#803): der freiwillige Satz am
> Vorgang («Was ist daran zu tun?») und die Bestellangabe je Partner waren dieselbe Aussage
> zweimal, einmal ohne Adressaten – und die zweite gab es nur beim Einkauf. Übrig bleibt
> **eine** Angabe je Partner, **Pflicht**, in **beiden** Richtungen: *«Was ist zu tun?» –
> Artikelnummer, Link oder Beschreibung*. Sie steht bei dem, den sie betrifft, denn *bei
> ihm* bestellt man anders als bei dem anderen.
> **Und die Geld-Zeile hängt an `can`, nicht an «ist dieses Modul dran»** – der Fund aus dem
> Gespräch, gemessen über die echten Dienstpfade: der Dienst erlaubt Rechnung und Zahlung an
> einem **abgeschlossenen** Auftrag (Zahlungsziel!), die Karte bot **null** Knöpfe an. Eine
> erfundene Sperre, die der Dienst nicht kennt – und die erfundene hat keinen Schlüssel;
> dieselbe Fehlerform wie damals bei «nicht bestanden». Die beiden Stufen behalten `active`:
> dort ist es richtig.
> **Lieferverzug ist eine ABLEITUNG, kein Zustand** (#814): Termin = *Zusagedatum +
> Lieferfrist*, «verspätet» = *Termin vorbei und noch nicht erledigt* – **exakt dieselbe
> Form wie `overdue`** bei einer Forderung; zwei Ableitungen, null Spalten. Ohne vereinbarte
> Frist **kein** Termin (ein erfundener wäre schlimmer als keiner). Und was man dann tun
> kann, gibt es alles schon: warten · stornieren · das Geld läuft unabhängig weiter.
> **Die Karte:** der Kopf verschwendet keine Reihe mehr (#815 – Symbol **und** Wort als
> kompakte Marke; ohne den Satz daneben stand dort ein Quadrat allein auf voller Breite);
> der Modul-Knopf ist ein **Knopf** (#813 – wieder ein blosser `.erp-actbtn`, und die
> Basisklasse hat keine Fläche); Bestätigen und Absage sind **exakt gleich gross** (#810,
> gemessen 32 × 30 px, Δ 0,0); **abgesagt ist abgesagt** (#811 – kein Preis, keine Frist
> mehr an einer abgelehnten Zeile); das **Referenz-Feld ist entfallen** (#812 – niemand
> wusste, was hineingehört, und die Rechnungsnummer erzeugt der Server längst selbst; damit
> hatte die Handlung `note` keinen Aufrufer mehr und ist samt ihrer beiden Spalten-Mappings
> mitgegangen); und **wen man anfragt, wählt man aus** (#809 – die Zeile IST der Schalter,
> wie im Beschaffen-Modul).
> **Ein Fehler nebenbei, still:** `_quote` überschrieb Liefer- und Zahlungsfrist bei jedem
> Aufruf – wer nur den Betrag nachreichte, verlor beide. Über die Tür fiel es nicht auf
> (`DealUpdate.changes` schickt Ungesetztes gar nicht mit), aber die Regel «nur gesendete
> Felder wirken» gehört in den **Dienst**: die Tür ist nicht der einzige Aufrufer.
> Wächter: 4 neue in `test_frontend_mirrors.py`, 4 dort auf die neue Regel gezogen, dazu
> die angepassten in `test_deal_module.py` – **jede Bug-Form gegengeprüft**; *einer war
> dabei stumpf und liess seine eigene durch* (er sah nur `deal-work.tsx` und damit
> ausgerechnet nicht den gemeldeten Knopf in `order-detail.tsx`), ein zweiter las seinen
> **eigenen Erklärtext** mit und schlug an, weil jemand den Fehler beschreibt – beide
> nachgeschärft. Suite grün gegen die gewachsene Datenbank (552) **und** gegen ein Schema
> nur aus den Migrationen (552). Gemessen in Chromium: 1440 · 1280 · 1024 · 834 · 375 ·
> 320 px, **0 px** waagrechter Überlauf über sechs Zustände; der **erledigte** Vorgang
> bietet jetzt 2 Handlungen an (Rechnung, Zahlung) statt keiner.

> **Eine Rechnung löscht man nicht — man storniert sie** (Testnotizen #816–#829,
> Migration `126`). Vierzehn Notizen, vier Themen — und der wichtigste Befund war
> buchhalterisch: *«Soll man wirklich aktiv erfasste Rechnungen so löschen können? Ich
> denke eher in Richtung stornieren.»*
> **(1) Der Papierkorb war falsch, und die Lösung brauchte keine neue Mechanik** (#823/
> #824). Eine Rechnungsnummer ist vergeben, ein Beleg ist draussen – wer die Zeile
> verschwinden lässt, behauptet, sie sei nie passiert. `void` machte einen Soft-Delete:
> der Saldo stimmte, die Zeile war weg. Eine Gutschrift ist aber längst eine **negative
> Rechnung** und eine Erstattung eine **negative Zahlung** (§9.11) – eine **Stornierung
> ist genau das, über den vollen Betrag**. Also `reverse` statt `void`: eine zweite Zeile,
> dieselbe Art, der negative Betrag, `reverses_id` auf die stornierte. Beide bleiben
> stehen, `balance` rechnet sie **ohne einen einzigen Sonderfall**. Zwei Sperren fallen
> aus derselben Frage (eine Gegenbuchung storniert man nicht, eine stornierte Zeile
> ebenso wenig) und stehen in **beiden** Formen: in `can`, also fehlt der Knopf, und in
> `_reverse`, also weist die Tür ab. **Einen Löschweg gibt es nicht** – auch nicht für
> einen Tippfehler; eine Frist («innerhalb fünf Minuten») wäre eine erfundene Regel mit
> einer Uhr darin.
> **(2) Ausgegraut, obwohl man handeln kann** (#821) – und das war der Fix meines eigenen
> letzten Fixes. Gemessen: `dimmed={running && !isActive}` legte 55 % Deckkraft über die
> **ganze** Karte, während die Geld-Knöpfe längst funktionierten (ein Zahlungsziel läuft
> weiter, wenn die Ware draussen ist). Dieselbe Fehlerform wie eine erfundene Sperre, nur
> in Farbe. **Ob man kann, sagt der Schritt** (`ProcessStepResponse.open_actions`),
> abgeleitet aus derselben Tabelle, die auch das Tor ist – nicht ein Modultyp und keine
> Heuristik der Oberfläche. *Und die Angabe muss ankommen: eine Ableitung, die niemand
> durchreicht, ist im Browser `undefined`, und `!undefined` ist wahr – die Karte wäre
> danach **nie** gedämpft. Genau diese Form fällt sonst niemandem auf, darum prüft der
> Wächter sie mit.*
> **(3) Weniger Labels, sprechendere Werte** (#816/#817/#818/#819/#826/#828). *«Die
> Buttons sind selbsterklärend genug.»* Drei Labels standen über Bedienelementen, die für
> sich sprechen; sie sind entfallen. Und die Werte werden dafür richtig: «zugesagt» ↔
> «bezahlt» → **«Nach Zusage» ↔ «Nach Zahlung»** (einzeln gelesen klang «zugesagt» nach
> einem *Zustand* statt nach einer *Bedingung*). «Auftrag bestätigen» → **«Angebot
> annehmen»** (#826 – man nimmt das *Angebot* an, der Auftrag ist das Ergebnis).
> «Rechnung stellen» ↔ «Rechnung erfassen» und «Zahlungseingang» ↔ «Zahlung» waren vier
> Wörter für zwei Handlungen: **erfasst** wird beides (#828) – das System bucht eine
> Zeile, es überweist nichts. **Damit trägt `Direction` fast nichts mehr**: `undo`,
> `stage_verbs`, `money_label`, `charge_word` und `payment_word` sind Konstanten; übrig
> bleiben `label`, `hint`, `stage_labels` und `ask_verb` – die vier echten Unterschiede.
> **(4) Kleineres, jedes an einer Stelle.** Die **Rechnungsnummer** trägt immer ihr Suffix
> (#827, `<Auftragsnummer>-<laufend>`) – das weggelassene «-1» war eine Sonderregel für
> genau einen Fall, und dieselbe Serie hiess danach «100000801», dann «100000801-2».
> **Ohne Rechnung keine Zahlung** (#822 – man kassiert nicht, was niemand gefordert hat;
> die Vorauszahlung verliert nichts, sie ist «erst fordern, dann zahlen»). Der
> **Modul-Abschluss steht am Ende der Karte** (#829), hinter der Geld-Zeile – er stand
> mitten in der Kette und sagte «hier ist Schluss», während sichtbar noch etwas folgte.
> Das **Modul-Protokoll erscheint nur, wo es mehr zu berichten hat als die blosse
> Passage** (#825): erfasste Werte · ein Zustandswechsel · eine Verifikation – eine Frage
> an die **Daten**, kein `if module_type`; entfernt wird es nirgends, es ist der Nachweis.
> **Und der Fund beim Messen** (#820): das **Editor**-Feld war es nicht – dort räumt
> `SearchSelect.pick` seine Suche selbst auf (Chromium, zwei Adds hintereinander, beide
> Male leer). Stehen blieb der Name an der **Ausführungsstelle**, wo #794 die frische Wahl
> bewusst hält; sie fällt jetzt, **sobald sie als Zeile dasteht** – eine Ableitung, kein
> zweiter Zustand. Ein `key`-Zurücksetzen im Editor hätte nichts behoben und den Fund nur
> zugedeckt.
> Wächter: 6 neue in `test_frontend_mirrors.py`, 2 neue in `test_deal_module.py`, dazu 5
> auf die neue Regel gezogene – **jede Bug-Form gegengeprüft**; *drei bestehende prüften
> die **Form** der alten Lösung* (`<Label required>{DEAL_TASK}</Label>`, `selected=
> {picked}`, die wörtliche `StepRecord`-Bedingung) und hätten damit die bessere Fassung
> verboten – sie fragen jetzt die Regel. *Zwei neue lasen dabei ihren eigenen Docstring
> mit* (er nennt den Modultyp, um zu begründen, warum er nicht gefragt wird) – in `_code`
> gefasst. Suite grün gegen die gewachsene Datenbank (559) **und** gegen ein Schema nur
> aus den Migrationen (559); Migration `126` von null · idempotent · downgrade ·
> re-upgrade verifiziert. Gemessen in Chromium an der **echten** Komponente: 1440 · 1280 ·
> 1024 · 834 · 375 · 320 px, **0 px** waagrechter Überlauf über sechs Zustände (inkl.
> stornierter und stornierender Zeile); der erledigte Vorgang bietet Rechnung, Zahlung und
> zwei Stornos an, die Gegenpartei sieht **0** fremde Preise.

> **Man storniert einen BELEG, kein Ereignis** (Testnotizen #830–#842). Dreizehn Notizen,
> vier Themen — und der wichtigste ist wieder buchhalterisch, diesmal mit der richtigen
> Antwort vom Nutzer selbst.
> **(1) Der Storno lag auf der falschen Achse** (#842). *«wenn ich eine zahlung erfasst
> habe, dann habe ich sie ja erfasst, dann kann ich sie doch nicht mehr stornieren… dann
> muss ich sie durch eine weitere zahlung korrigieren oder???»* – Ja. Eine **Forderung**
> ist ein Beleg, den *wir* ausstellen; den nimmt eine Stornorechnung zurück. Eine
> **Zahlung** ist die Aufzeichnung dessen, was auf dem Konto passiert ist – ein Ereignis
> der Aussenwelt macht man nicht ungeschehen. `reverse` gilt darum **nur für eine
> Forderung** (im Dienst, nicht nur am Knopf; `can` führt das Verb gar nicht, wenn nur
> Zahlungen dastehen), und an einer Zahlung steht **«Korrigieren»** – **kein neues Verb**,
> sondern die gewöhnliche Erfassung mit dem **negativen Betrag vorbelegt**. Ob es ein
> Erfassungsfehler war oder ob das Geld zurückkam, weiss nur ein Mensch: *das System
> bietet an, der Mensch entscheidet* (dieselbe Regel wie §4.5). *Bewusst nicht gebaut und
> benannt: das **Ausziffern** offener Posten – bei meist einer Rechnung je Vorgang ist der
> Topf richtig, die Zuordnung wäre ein zweites Modell für dieselbe Zahl.*
> **(2) Jede Nummer wird genau EINMAL vergeben** (#841/#840). Die Storno-Zeile kopierte
> die Nummer der stornierten: zwei Belege hiessen gleich, und in der Serie fehlte die
> nächste Zahl. Eine Stornorechnung ist aber ein **eigener** Beleg – eigene Nummer,
> **Verweis** auf die stornierte (`reverses_id` und Vermerk, nie die Nummer). Und die
> andere Hälfte derselben Regel: **eine Nummer, die wir vergeben, tippt niemand ab** –
> das Feld gibt es genau dort, wo sie **von aussen** kommt (Lieferantenrechnung ·
> Zahlungsreferenz), und ein trotzdem gesendeter Wert wird **verworfen**, nicht ignoriert.
> **(3) Wer den Preis nennt, ist eine Eigenschaft der Richtung** (#837). *«Beim Verkaufen
> sage ich zuerst, was ich zu welchem Preis an wen offeriere.»* – Vorher schickte `ask` in
> **beiden** Richtungen eine leere Zeile hinaus; der Kunde sähe ein Angebot ohne Preis.
> Ein Angebot hat einen **Urheber** (`Direction.quoted_by`), und daraus folgt beides ohne
> Verzweigung: wer nennt, füllt **vor** dem Hinausgehen (die Zeile entsteht sofort als
> *offeriert*), und wer empfängt, **nimmt an oder lehnt ab**. `PARTY_ACTIONS` ist damit
> keine Konstante mehr, sondern eine **Ableitung** (`party_actions`) – die eine erlaubte
> Unterscheidung, und sie steht als Daten im Flow.
> **(4) «Einnahme» ↔ «Ausgabe» statt «Verkauf» ↔ «Einkauf»** (#831) – und das nimmt meine
> Wahl aus #804 zurück. Das Modul entstand aus der Einsicht, dass der kleinste gemeinsame
> Nenner **nicht die Ware** ist: Miete, Lohn, Gebühr, Spesen und ein Transport sind keine
> Käufe. Ein Wert, der «Verkauf» heisst, ist **enger als das Modul**. Darum auch **nicht**
> die Symbole des Handels – ein Handschlag über einer Mietzahlung behauptet ein Geschäft,
> das es nicht gibt; zwei Pfeile sagen, wohin das Geld fliesst, und mehr behauptet es nicht.
> **Kleineres, jedes an einer Stelle:** die **Abwahl gilt für die Anfrage, die man gerade
> stellt** (#835 – sie überlebte sie, und wer erst einen von zweien fragte, hatte den
> zweiten noch abgewählt: «Bei 0 anbieten», gesperrt, bis zum Refresh); **was eine Zahl
> ist, steht tabellarisch** (#839 – Betrag, Frist und Datum; die Objektnummer bleibt
> bewusst anders, sie ist eine **Kennung**, kein Messwert); **Nummer und Name brechen
> nicht um** (#838 – der Name wird gekappt); im Editor steht alles zu **einem** Partner auf
> **einer** Zeile (#833 – bei mehreren ist sie die einzige Stelle, an der die Zugehörigkeit
> steht) und der **Löschen-Knopf erscheint beim Hovern** (#832 – aber `@media (hover: none)`
> hält ihn auf Touch sichtbar: eine Funktion, die nur ein Zeiger findet, gibt es am Telefon
> nicht); an der Angebotszeile ist «Was ist zu tun?» eine **Auskunft**, keine Frage (#836 –
> Symbol + Wert, Erklärung im Hover); der Schalter heisst **«Zahlung abwarten» ↔ «Zahlung
> nicht abwarten»** (#834 – der Wert benennt jetzt die *Entscheidung*, nicht ihren
> Bezugspunkt); und die Liste heisst schlicht **«Partner»** (#830).
> Wächter: 3 neue in `test_deal_module.py`, 6 neue in `test_frontend_mirrors.py`, dazu 5
> auf die neue Regel gezogene – **jede Bug-Form gegengeprüft**; *einer war dabei stumpf und
> liess seine eigene durch* (er fragte, ob `e.kind === 'charge'` irgendwo im Rumpf steht,
> und war schon durch die Symbolwahl eine Zeile höher erfüllt) – er prüft jetzt das **Tor**.
> Zwei bestehende prüften die **Form** der alten Lösung (der wörtliche `ask`-Aufruf, die
> Handels-Symbole) und hätten die bessere verboten. Suite grün gegen die gewachsene
> Datenbank (568) **und** gegen ein Schema nur aus den Migrationen (568). Gemessen in
> Chromium an den **echten** Komponenten: 1440 · 1280 · 1024 · 834 · 375 · 320 px, **0 px**
> waagrechter Überlauf; die Partner-Zeile ist ab 834 px **eine** Zeile, der Löschen-Knopf
> steht im Ruhezustand auf Deckkraft 0 und beim Hovern auf 1 – **auf einem Touch-Gerät
> durchgehend auf 1**; das Nummernfeld fehlt bei einer Einnahme und steht bei einer
> Ausgabe; die Korrektur einer Zahlung ist mit «−1000.00» vorbelegt.

> **Eine Rechnung ohne Steuersatz ist keine — und der Satz hängt an der SACHE**
> (Testnotizen #843–#850, MWSTG Art. 26, Migration `127`). Der Geldvorgang trug **eine**
> Zahl: `deals.amount`, und `agreed_lines` hielt Artikel und Menge – **keinen Preis**.
> Damit fehlte genau das, was einen Beleg zu einem Beleg macht: Steuersatz und
> Steuerbetrag. **Das Modul muss es selbst können** – einen Verkaufsbereich am Artikel
> gibt es nicht, und ein Modul, das auf eine Angabe von aussen wartet, kann seine eigene
> Rechnung nicht stellen.
> **Die eine Regel, aus der alles folgt: der Positionspreis ist NETTO, jeder Betrag ist
> BRUTTO.** Damit bleibt `balance` unangetastet – *offen · bezahlt · uncharged* rechnen
> weiter mit derselben Zahl wie vorher, und keine der drei Achsen (Ware · Forderung ·
> Geld) muss von der Steuer wissen. Netto und Steuer sind **Ableitungen**, null Spalten.
> **Der Satz steht an der POSITION, nicht am Beleg** (`DealLine.vat`): sechs Wellen zu
> 8.1 % und eine Ausfuhr zu 0 % stehen auf demselben Papier – ein Satz je Beleg wäre bei
> jedem gemischten Geschäft falsch, und zwar stillschweigend, weil die Summe trotzdem
> aufgeht. **Gerundet wird je Satz auf der SUMME** (`domain/deal.vat_split`), nie je
> Position aufsummiert: bei zwölf Zeilen weicht die Summe der gerundeten Einzelbeträge
> sonst um Rappen ab, und eine MWST-Abrechnung kennt keine Rappen-Toleranz (gemessen:
> 3 × 5.00 zu 8.1 % ergibt 1.22, nicht 3 × 0.41 = 1.23).
> **Eine Teilrechnung verteilt sich ANTEILIG über alle Sätze** (`split_for`) – eine
> Anzahlung ist zum Satz der zugrunde liegenden Leistung zu versteuern; dem höchsten Satz
> zugeschlagen wäre sie zu viel Steuer, dem niedrigsten zu wenig. **Der letzte Anteil
> bekommt den Rest**, sonst ist die Summe der Zeilen nicht der Betrag der Rechnung.
> **Wer den Preis nennt, entscheidet die FORM** (`quoted_by`, seit #837): bei einer
> **Einnahme** nennen wir ihn als Positionen (dort hängt der Satz), und der Angebotsbetrag
> ist ihre Brutto-Summe – ein Betragsfeld daneben ist darum entfallen, es wäre nicht nur
> die zweite Aussage, sondern eine, die der Dienst abweist. Bei einer **Ausgabe** nennt
> die Gegenpartei eine Summe, und die Steuer steht auf **ihrer** Rechnung: dort wird der
> Satz bei der Erfassung gefragt, und nur dort.
> **Die gebuchte Zeile SPEICHERT ihre Steuer** (`deal_entries.vat`, `service_date`) statt
> sie nachzurechnen: ein Beleg behält, was auf ihm stand – nachgerechnet wäre die
> Vergangenheit eine Funktion der Gegenwart, und eine Abrechnung über ein abgeschlossenes
> Quartal ergäbe beim zweiten Lauf andere Zahlen. Der **Storno spiegelt sie** mit
> negativem Vorzeichen; sonst nähme er den Betrag zurück und die Steuer nicht.
> **Ein Fehler, der still gewesen wäre:** `DealUpdate` kannte `lines`, `vat` und
> `service_date` nicht – Pydantic verwirft unbekannte Felder **stillschweigend**, also
> wäre der Preis eines Angebots nie angekommen (dieselbe Falle wie damals bei
> `ModuleConfigInput`). Kein Dienst-Test hätte es gefunden: die rufen `apply` direkt. Der
> neue Wächter prüft darum die **Tür**. Und `assert_vat("acht Prozent")` warf ein
> `InvalidOperation` aus der Tiefe der `decimal`-Bibliothek – ein 500 statt eines Satzes.
> **Der bestätigte Auftrag ist jetzt ein BELEG** (#847 – «schaut total beschissen aus»):
> vier gleich laute Lesefelder in einem `auto-fit`-Raster, das je nach Breite in eine,
> zwei oder vier Spalten zerfiel, und der **Betrag** – die einzige Zahl, um die es geht –
> als drittes Kästchen von links. Jetzt die Ordnung eines Belegs: **wer** (eine Zeile) ·
> **was es kostet** (rechtsbündig Netto · Steuer je Satz · Total unter **einer**
> Haarlinie über beide Spalten) · **zu welchen Bedingungen** (klein daneben). Die
> **Positionen stehen nicht noch einmal darin** – sie stehen oben, seit die Zeile ihren
> Preis und ihren Satz trägt.
> **Kleineres, jedes an einer Stelle:** «Partner» steht im **Platzhalter** statt als
> eigene Zeile darüber (#843 – im Scan-Vollbild bleibt es eine Beschriftung, dort liegt
> Text auf einem Foto); der **Löschen-Knopf einer Zeile** sieht aus wie der am Modul
> selbst (#844, `RowDelete` – gemessen 26 × 26 px, kein Rahmen, keine Fläche, allein die
> Warnfarbe; die Hover-Einblendung bleibt eine Wahl des Aufrufers); die **Symbole** der
> Richtung kommen aus `FLOW` (#845 – zwei gespiegelte Pfeile sind auf 15 px dasselbe
> Zeichen mit anderer Neigung, Einkaufswagen und Handschlag sind verschiedene Dinge; die
> **Wörter** bleiben «Einnahme» ↔ «Ausgabe», #831 ist damit nicht zurückgenommen); **was
> der Partner ändert, kommt an** (#846 – ein `useState`-Startwert wird einmal gelesen, und
> wer danach etwas anderes korrigierte, schrieb die alte Frist **zurück**; nachgezogen
> wird beim Wechsel des Server-Werts, nicht bei jedem Rendern); der **Erklärsatz** unter
> der Karte ist gelöscht (#849 – er sagte dreimal dasselbe: Kopf, Geld-Zeile und der
> fehlende Knopf); das Verb heisst **«Vorgang abschliessen»** (#848 – «Auftrag erledigt»
> meinte den falschen Auftrag); und es gibt **ein** Nummernfeld für Rechnung und Zahlung
> (#850 – bei einer Einnahme trägt auch die Zahlung unsere Nummer).
> **Nebenbei gefunden:** an einer bereits offerierten Zeile liess sich die **Frist** nicht
> mehr ändern, ohne den Preis erneut zu behaupten – «nur gesendete Felder wirken» galt für
> die Fristen, nicht für den Betrag.
> Wächter: 7 neue in `tests/test_deal_module.py`, 6 neue in `test_frontend_mirrors.py`,
> dazu 6 auf die neue Regel gezogene – **jede Bug-Form gegengeprüft**; *zwei neue waren
> dabei stumpf und liessen ihre eigene durch* (einer fragte nach `value.rows.map`, das
> auch im Zeilen-Helfer steht; einer prüfte `<Label` über einem Bedienelement mit einer
> Fensterlogik, die an `</Label>` scheiterte). Und **`_body` war der Fehler selbst**: an
> einer Komponente mit verschachtelter Hilfsfunktion lieferte es 249 statt 3623 Zeichen,
> also von der Sache gar nichts – dafür gibt es jetzt `_component`. Suite grün gegen die
> gewachsene Datenbank (573) **und** gegen ein Schema nur aus den Migrationen (581);
> Migration `127` von null · idempotent · downgrade · über das Lifespan-Netz verifiziert.
> Gemessen in Chromium an den **echten** Komponenten: 1440 · 1280 · 1024 · 834 · 375 ·
> 320 px, **0 px** waagrechter Überlauf über sechs Zustände (inkl. zweier Steuersätze auf
> einem Beleg) und im Editor.

> **Der Handel ist WEG — was blieb, ist ein Scan; und ein Betrag hat eine WÄHRUNG**
> (Migration `128`, PROCESS_CORE §9.9/§9.9a/§9.12). Die Module **Beschaffen** und
> **Verkauf** sind ersatzlos gelöscht – nicht abgeschaltet: mit ihrem Beleg, ihren
> Tabellen-Mappings und ihren Diensten (`domain/procurement` · `domain/money` ·
> `services/purchase` · `services/invoices` · `services/payments` · `models/purchase` ·
> `models/invoice` · `models/payment` · `purchase-work.tsx`). Rund 4.400 Zeilen.
> **Der Grund ist keine Geschmacksfrage, sondern eine Doppelung.** Ihr Beleg war
> Angebot → Zusage → Erfüllung mit Angebotsspiegel, Rechnungen, Zahlungen und Storno –
> **genau das ist der Geldvorgang** (§9.12), nur ohne die Bindung an Ware und damit auch
> für Miete, Lohn, Gebühr, Spesen und eine eingekaufte Spedition brauchbar. Dass er
> damals bewusst **neben** ihnen gebaut wurde («kein Import aus `procurement`/
> `purchase`»), hat sich hier ausgezahlt: an ihm musste für die Löschung **keine Zeile**
> geändert werden.
> **Was übrig blieb, ist ein neues, sehr kleines Modul: «Ausliefern»** – ein Scan, ein Statuswechsel
> auf `Verkauft`, **sonst nichts**. Keine Konfiguration: an wen geliefert wird, steht im
> Geldvorgang desselben Auftrags; was, sagen die Stücke davor; wann, sagt der Log.
> **Und es ist ein AUSGANG** – *das* war der Fund beim Bauen. Die erste Fassung stand auf
> `terminal = False` mit dem Verweis auf den Verbrauch (der `Verbaut` setzt und ebenfalls
> kein Ausgang ist), und die **Kettenregel hat es sofort gemeldet**: beim Verbrauch
> bleiben die durchlaufenden Stücke auf `Im Prozess` – nur die Komponenten wechseln, und
> die treten dort erst ein. Hier wechselt **jedes** ankommende Stück; ein Modul dahinter
> erwartete `Im Prozess` und bekäme `Verkauft`, am Schluss bräche die Kette am
> Ende-Objekt. **Ein nicht-terminales Modul, das den Zustand ALLER Stücke ändert, kann es
> gar nicht geben.** Was danach kommen müsste, kommt davor – auch fachlich: man prüft,
> bevor man liefert, und der Geldvorgang verliert nichts, weil seine Geld-Zeilen an `can`
> hängen und nicht daran, ob das Modul dran ist (#821). **`Verkauft` bleibt trotzdem
> umkehrbar**: `Module.terminal` und `Status.terminal` sind zwei verschiedene Fragen –
> die Retoure ist ein ganz gewöhnlicher Auftrag, **das Greifen IST die Rücknahme**, und
> weil ihr Start vom Regelstart abweicht, ist sie automatisch eine dokumentierte
> Abweichung. Der **Ort** fällt ebenso ohne eine Zeile weg (`Verkauft` zählt zur
> Historie). Und ein **Transport ist dieses Modul nicht**: ein Muster beim Kunden, ein
> Computer beim Mitarbeiter, eine Konsignation – dort wechselt der Ort, und nichts ist
> verkauft; eine Ableitung «Ort ausserhalb ⇒ verkauft» wäre in genau diesen Fällen still
> falsch.
> **Der Steuersatz ist aus dem MODUL verschwunden** (Testnotiz #851 – der Nutzer hatte
> recht): er stand dort als «Vorgabe jeder neuen Position» und war damit eine Eigenschaft
> des Moduls – eine Vorlage, die für jeden künftigen Auftrag denselben Satz behauptet,
> obwohl er an der **Sache** hängt und die erst feststeht, wenn ein Auftrag läuft. Ein
> Vorgabewert, der bei der Hälfte der Aufträge überschrieben werden muss, ist kein
> Komfort, sondern die Zahl, die stehenbleibt, wenn es niemand tut. Mit ihm sind der
> `vat_rates`-Weg über den **Modul-Katalog** und die ganze `vatRates`-Prop-Kette im
> Editor entfallen: der Katalog reist mit dem **Vorgang**, und ein zweiter Weg zur selben
> Liste ist die Stelle, die beim nächsten Satzwechsel jemand vergisst.
> **Das Leistungsdatum kommt aus dem PROZESS** (#852 – ebenfalls richtig gesehen): es ist
> der Tag, an dem die Stücke das Modul **erreicht** haben, und das Rechnungsdatum ist es
> nicht (MWSTG Art. 26 Bst. c – eine zwei Wochen später geschriebene Rechnung verschöbe
> die Steuerperiode). Gelesen wird darum das `step`-Ereignis des **Vorgängers**, nicht das
> eigene: ein `step` an *diesem* Modul heisst «hier fertig». **Abgeleitet, nicht
> gespeichert** – und **vorbelegt, nicht erzwungen**: ein Mensch weiss von Teilleistungen,
> von denen der Log nichts weiss.
> **Und die Währung, state of the art** (`domain/currency.py`, `deals.currency`): **eine
> je Vorgang, nicht je Zeile** – zwei Währungen auf einem Beleg wären zwei Belege.
> Vorbelegt ist die des Betreibers; **änderbar bis zur Zusage, danach nicht mehr**, und
> das ist keine zusätzliche Regel, sondern dieselbe Tabelle: `currency` steht in
> `ACTIONS[OFFER]`, also fehlt der Knopf danach von selbst und `apply` weist ihn ab.
> ►►► **Die Nachkommastellen sind der Punkt, den man vergisst.** ◄◄◄ Fast alle Währungen
> haben zwei – und darum schreibt man `f"{x:.2f}"` bzw. `NUMERIC(x, 2)` und merkt nie,
> dass es falsch ist: **JPY und KRW haben null**, **KWD hat drei**. Ein Yen-Betrag mit
> zwei Nachkommastellen ist kein Rundungsfehler, sondern ein Betrag, den es nicht gibt.
> Die Stelligkeit hängt darum an **einer** Stelle und gilt auf **vier** Ebenen: Parsen ·
> Rechnen · Ausgeben · **Spalte** (`NUMERIC(18, 4)`). Beim Rechnen fiel dabei ein zweiter
> Fehler auf: `quantize` rundet ohne Angabe **statistisch** (banker's rounding) – 12.345
> wäre 12.34 geworden, während die Buchung kaufmännisch 12.35 bucht; eine Anzeige, die
> anders rundet als die Buchung, ist ein Rappen Differenz, den niemand erklären kann.
> **Umgerechnet wird nichts und gemischt wird nichts**: ein Kurs hat ein Datum und eine
> Quelle, und wer ohne beides umrechnet, erfindet Zahlen. In der Oberfläche steht sie
> **im Kopf des Vorgangs**, nicht an jeder Zahl – genannt beim **Total** und beim
> **offenen Betrag**, den Zahlen, die abgeschrieben und überwiesen werden.
> **Eine vierte Lücke zwischen den Netzen, und sie war die stillste**
> (`main._NUMERIC_SAFETY_NET`): eine fehlende Tabelle legt `create_all` an, eine fehlende
> Spalte das Spalten-Netz, eine gelöste `NOT NULL` das Nullable-Netz – eine Spalte mit zu
> **kleiner Skala** nimmt den Wert an und rundet ihn weg. Dieselbe Lehre wie bei den
> Indizes (#778): eine Typänderung, die nur in einer Migration steht, erreicht die
> dev-Datenbank nie. Gemessen: nach `downgrade 127` zieht der Start beides nach (Spalte
> **und** Skala 2 → 4).
> **Stripe ist bewusst geblieben** (`services/stripe_pay`, `docs/stripe-setup.md`): der
> Webhook schreibt jetzt eine Geld-Zeile am **Vorgang** statt am Beleg, und `_cents` ist
> `_minor(amount, code)` geworden – `× 100` wäre bei **JPY** um den Faktor hundert falsch
> (1000 Yen als 100 000 belastet). Heute ohne Bedienelement (der Zahllink-Knopf hing an
> der Beleg-Karte), aber vollständig verdrahtet.
> **Kleineres, jedes an einer Stelle:** `Module._object_id` steht wieder in der Basis (das
> Ziel des Bewegen-Moduls und der Partner des Zahlungs-Moduls stellen dieselbe Frage – was
> ein **fehlender** Wert bedeutet, sagt der Aufrufer); `ModuleShell` bleibt ein eigenes
> Bauteil, obwohl sein zweiter Träger entfallen ist; `formatAmount` nimmt die
> Nachkommastellen als Parameter; `SupplierOption` ist gelöscht.
> Wächter: `tests/test_delivery_module.py` (5 Prüfungen, **jede gegen ihre Bug-Form
> gegengeprüft**), 4 neue in `test_deal_module.py` (9 Bug-Formen), 3 neue in
> `test_frontend_mirrors.py` (8 Bug-Formen) – dazu **19 Wächter der gelöschten Module
> entfernt** und 6 auf die neue Regel gezogen. Suite grün gegen die gewachsene Datenbank
> **und** gegen ein Schema nur aus den Migrationen (je 508); Migration `128` von null ·
> idempotent · downgrade · re-upgrade verifiziert. Gemessen in Chromium an der **echten**
> Komponente: 1440 · 1280 · 1024 · 834 · 375 · 320 px, **0 px** waagrechter Überlauf über
> vier Zustände (inkl. eines JPY-Belegs und der Sicht der Gegenpartei) – und die Messung
> gegen ihre eigene Bug-Form gegengeprüft (+62,3 px bei einem unteilbaren Wort).

> ►►► **Bezahlt wird BEI UNS — und «Ausliefern» ist mitgegangen** (PROCESS_CORE §9.13).
> ◄◄◄
> **(1) Das Modul «Ausliefern» ist ersatzlos gelöscht.** Es kam mit dem Ende des Handels
> und war die letzte Zeile daraus: ein Scan und ein Statuswechsel auf `Verkauft`. Was
> *physisch* geschieht, sagen die Module, die es tun (**Bewegen** bringt es hin,
> **Zahlung** regelt das Geld) – und «das Stück gehört jetzt jemand anderem» ist kein
> Vorgang, sondern die Folge davon. Ein Modul, dessen ganze Aussage eine Folge ist,
> beschreibt nichts, was nicht schon dasteht.
> **`Verkauft` bleibt im Statuskatalog** – und das ist die eine Stelle, an der «weg ist
> weg» nicht gilt: der Katalog ist nicht nur die Liste dessen, was **entstehen** kann,
> sondern das **Vokabular des append-only Ereignis-Logs**. Jedes je ausgelieferte Stück
> trägt das Wort in seiner Zeile und in seiner Geschichte; ihn zu streichen machte
> Vergangenes nicht ungeschehen, sondern **unlesbar** (`flow._left_with` liest es aus dem
> Log, die Bestandsleiste gruppiert danach). Dieselbe Regel wie bei den Tabellen der
> entfernten Bereiche: was niemand mehr schreibt, kostet nichts; was die Vergangenheit
> trägt, wird nicht gelöscht.
> **(2) Der Zahllink ist weg – die Bezahlkarte ist unsere.** Bisher erzeugte
> `…/payment-link` eine **gehostete Kasse** beim Dienst: der Zahlende verliess das ERP und
> stand auf einer fremden Seite mit fremdem Namen, fremder Schrift und fremder
> Adresszeile. *Er hatte ausserdem seit dem Ende des Handels-Belegs **kein einziges
> Bedienelement** – ein Endpunkt, den niemand rief.* Jetzt entsteht nur eine
> **Zahlungsabsicht** (`stripe_pay.prepare`), und ihr Geheimnis geht an eine eigene Karte
> im ERP (`components/erp/pay-online.tsx`): Fläche, Wörter, Betrag, Knopf und Rückmeldung
> gehören uns. **Vom Dienst kommen nur die Eingabefelder** (ein *Payment Element* in einem
> iframe) – und das ist ihr Sinn, nicht ein Kompromiss: so berührt **keine Kartennummer je
> unseren Server**, und das ist der Unterschied zwischen «wir nehmen Karten an» und «wir
> sind PCI-pflichtig». Damit man die Naht nicht sieht, kommt das **Aussehen aus unseren
> Tokens** (`getComputedStyle` liest die CSS-Variablen des Hauses) statt aus einer
> geratenen Farbliste, die beim nächsten Design-Wechsel stehen bleibt.
> **(3) Was das ERP weiss, wird nicht gefragt.** Name, E-Mail und Rechnungsadresse der
> Gegenpartei reisen mit der Vorbereitung mit und werden dem Element als **feste Angabe**
> übergeben. **Die beiden Hälften gehören zusammen**: `fields: 'never'` heisst «wird
> mitgeliefert» – wer nur die eine schreibt, bekommt eine Ablehnung, und zwar erst beim
> Bezahlen. Und **nur, was wirklich dasteht**: fehlt die Adresse, fragt das Element sie;
> eine halbe Vorbelegung wäre schlechter als die Frage (die Genauigkeit ist die der
> Quelle). Bewusst **kein** Kunden-Datensatz beim Dienst (zwei Stammdaten für dieselbe
> Person, die zweite ausserhalb des ERP) und **keine** Quittungs-Mail von dort (fremdes
> Briefpapier für einen Vorgang, der bei uns steht).
> **(4) Die Gegenpartei bezahlt selbst** – das ist der Zweck. `Direction.party_actions`
> trägt `pay_online` in **beiden** Richtungen; *ob* es an diesem Vorgang überhaupt etwas
> zu bezahlen gibt, beantwortet eine Ebene höher `Direction.collects` (ein Zahlungsdienst
> **zieht ein**, er überweist nicht in unserem Namen). Zwei Stellen, die dieselbe Bedingung
> prüfen, wären zwei Massstäbe.
> **Und damit sieht sie die Zahlen** (`won` statt `internal` in `embed_data`): wer bezahlen
> soll, muss sehen, was er schuldet – eine Aufforderung ohne Betrag ist keine. Ein **Leck
> ist es nicht**: `won` heisst «dieser Betrachter *ist* die Gegenpartei dieses Vorgangs»,
> die Rechnungen sind seine. Ein angefragter, unterlegener Dritter sieht weiterhin nichts.
> **Buchen darf sie trotzdem nicht** – eine Buchung ist unsere Aussage über unser Konto.
> **(5) Drei Bedingungen, nicht vier – und die vierte fiel beim MESSEN.** «Es muss eine
> Rechnung geben» stand als eigene Bedingung da (die Regel von `pay`, #822) und liess sich
> **nicht gegenprüfen**: *offen* ist `Forderungen − Zahlungen`, ohne Forderung also nie
> positiv. Sie sagte nichts, was `open > 0` nicht schon sagt, und ist entfallen. Bei `pay`
> bleibt sie richtig – dort nennt ein Mensch den Betrag; hier **ist** der offene Betrag die
> Sache. *Ein Wächter, der nie anschlägt, ist von einem kaputten nicht zu unterscheiden.*
> **(6) `can` ist auch hier Auskunft UND Tor**, obwohl `pay_online` gar keine Handlung am
> Vorgang ist: es bucht nichts (das tut der Webhook) und hat darum **keinen** Eintrag in
> `HANDLERS`, sondern einen eigenen Endpunkt (`…/deal/payment`). Damit `apply` daran nicht
> mit einem `KeyError` – an der Tür ein **500** – zerbricht, antwortet es mit einem **Satz**
> (409). Und `_assert_allowed` heisst jetzt `assert_allowed`: es hat einen zweiten Aufrufer,
> und beide fragen dieselbe Liste.
> **(7) Der Anbieter steht NICHT im Geldvorgang.** «Ist ein Zahlungsdienst eingerichtet?»
> wohnt in `core/config.payment_service_ready()` – der Geldvorgang fragt eine
> **Eigenschaft**, keine Marke, und ein Quelltext-Wächter hält es so («stripe» kommt in
> `services/deal.py` nicht vor). Sie fragt nach **beiden** Schlüsseln: der geheime erzeugt
> die Absicht, der **öffentliche** rendert das Formular – einer allein wäre ein Knopf, der
> garantiert in einem leeren Dialog endet.
> **(8) Der Webhook hört jetzt `payment_intent.succeeded`** statt
> `checkout.session.completed` (die gehostete Kasse gibt es nicht mehr) und bucht
> `amount_received` – nicht `amount`: bei einer Teilautorisierung sind das zwei Zahlen, und
> nur die zweite ist eine Zahlung. **Ein bestehender Endpoint im Dashboard muss umgestellt
> werden** (`docs/stripe-setup.md` §3); sonst kassiert die Karte, und die Buchung bleibt
> aus.
> **Welche Zahlungsarten es gibt, entscheidet das Konto** (`automatic_payment_methods`) –
> Karte, **TWINT**, was dort freigeschaltet ist. Eine Liste bei uns wäre die zweite Stelle,
> an der beim nächsten Freischalten jemand nichts sieht.
> **Ein Paket dazu, und nur eines**: `@stripe/stripe-js` (der offizielle Lader, **dynamisch**
> importiert – was niemand öffnet, kostet niemanden etwas). Kein React-Wrapper: das Element
> wird in ein `<div>` gemountet, das sind vier Zeilen.
> Wächter: 4 neue in `tests/test_deal_module.py`, 3 neue in `test_frontend_mirrors.py` –
> **zehn Bug-Formen gegengeprüft, jede meldet**; *einer war dabei stumpf* (er las den
> Docstring des Adapters mit, der die bewusst fehlenden Dinge **aufzählt** – genau die
> Form, in der ein Wächter anschlägt, weil jemand den Fehler beschreibt: `_code()` liest
> jetzt den Code). Suite grün gegen ein Schema nur aus den Migrationen (509).
> *Offen und ausdrücklich benannt: `STRIPE_PUBLISHABLE_KEY` gibt es im Secret Manager noch
> nicht, und die Deploy-Zeile nennt ihn darum nicht – ein `--set-secrets` auf ein fehlendes
> Secret risse den **ganzen** Deploy mit. Bis dahin ist der Dienst schlicht nicht
> eingerichtet: kein Knopf, kein Fehler. Zwei Befehle in `docs/stripe-setup.md` §4/§5.*

> **WICHTIG:** Vollständige und verbindliche Projekt-Anforderungen in `docs/Lastenheft_v1.0.md` – vor Entwicklungsarbeiten konsultieren.

## Was ist Inexxio?
Zentrales Unternehmenssystem für ein produzierendes Schweizer KMU (AG, Maschinenbau).
Ziel ist die Kombination aus Website/Shop + ERP + Buchhaltung + HR + Qualitätsmanagement;
**gebaut ist heute das Fundament und der Prozess** (siehe «Was heute steht»).

Rechtsform: Aktiengesellschaft (AG), Schweiz
Branche: Produzierendes Gewerbe / Maschinenbau
Mitarbeiter: ca. 10 | Artikel: ca. 1'000

## Architektur

**Im Einsatz** – alles hier ist verdrahtet und läuft:
```
Frontend:  Next.js 14, TypeScript, App Router, Tailwind CSS (statischer Export)
Backend:   FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic v2, Alembic
DB:        PostgreSQL (Cloud SQL), universeller 9-stelliger Nummernkreis
Auth:      Firebase Authentication (Magic Link + Google SSO + Passkeys/WebAuthn)
Bilder:    in der Datenbank, ausgeliefert über einen unerratbaren Token
Karten:    Google Places (Adress-Suche in jedem Adressfeld)
Infra:     Google Cloud Run + Firebase Hosting
Analytics: Plausible (DSGVO-konform, lädt erst mit Einwilligung)
Zahlung:   Stripe – **eigene Bezahlkarte im ERP** (Payment Element + Webhook), kein
           Zahllink. **Optional**: ohne Schlüssel gibt es den Dienst nicht, und bezahlt
           wird per Überweisung (`docs/stripe-setup.md`)
```

**Geplant, aber NICHT verdrahtet** – hier steht heute keine Zeile Code:
Gmail API (E-Mail) · Typesense (Suche) · Claude API (KI) · Cloud Storage (Datei-Ablage) ·
Carrier-Anbindung (Versand). Was davon einmal gebaut und
wieder entfernt wurde, steht mit seinen Entscheidungen in `docs/attic.md`.

## Monorepo-Struktur
```
inexxio/
├── CLAUDE.md              ← Haupt-Kontext (IMMER zuerst lesen)
├── frontend/              ← Next.js 14 App
│   ├── CLAUDE.md          ← Frontend-spezifischer Kontext
│   └── src/
│       ├── app/
│       │   ├── (public)/  ← Öffentliche Website-Seiten
│       │   ├── (auth)/    ← Login
│       │   └── (erp)/     ← ERP / Auth-geschützte Seiten
│       ├── components/    ← UI-Komponenten
│       └── types/         ← TypeScript Interfaces
├── backend/               ← FastAPI Python
│   ├── CLAUDE.md          ← Backend-spezifischer Kontext
│   └── app/
│       ├── routers/       ← API Endpunkte
│       ├── models/        ← SQLAlchemy Modelle
│       ├── schemas/       ← Pydantic Schemas
│       ├── services/      ← Business Logic
│       └── core/          ← Config, Auth, DB-Connection
├── .env.example           ← Vorlage für Env-Variablen (nur, was der Code auch liest)
└── docs/
    ├── adr/               ← Architecture Decision Records (mit Kopfstatus je ADR)
    ├── attic.md           ← was entfernt wurde, wo es liegt, welche Entscheidung darin steckt
    ├── history/           ← Archiv: Beschreibungen nicht mehr existierender Systeme
    └── design-system/     ← Tokens, Marken-Grundlagen, Nutzung
```

Messwerkzeug: `backend/scripts/deadcode.py` beantwortet «was liest eigentlich niemand
mehr?» für beide Seiten (Erreichbarkeit + Exporte ohne Leser).

## Design System (VERBINDLICH)

> **Inexxio Design System** ist die EINE, verbindliche Grundlage für ALLE
> Oberflächen (Website, Shop, ERP). Jede neue oder geänderte UI **MUSS** darauf
> aufbauen. Es ist der in den Code übernommene Export aus **Claude Design**.
> Vollständige Regeln & Nutzung: **`docs/design-system/README.md`** (vor UI-Arbeit
> lesen), Marken-/Visual-Doku: `docs/design-system/brand-foundations.md`.

- **Quelle der Wahrheit für Tokens:** `frontend/src/styles/design-system/colors_and_type.css`
  (geladen als erstes CSS-Modul in `app/layout.tsx`). Token-Werte werden NUR dort
  definiert – niemals in `globals.css`, `tailwind.config.js` oder Komponenten hart
  kodieren.
- **Nutzung:** Tailwind-Utilities aus den Tokens (`bg-bg-2`, `text-fg-3`,
  `text-accent`, `border-border-1`, `rounded-ds-lg`, `shadow-ds-md`, `font-display`),
  CSS-Vars (`var(--fg-2)`) oder `.ix-*`-Typo-Helper.
- **Farbe = Bedeutung:** warme Neutraltöne tragen die Fläche; **Rot (`inexxio`) ist
  der EINE laute Akzent** (CTA / ein Headline-Wort / aktiv / Fehler, nie dekorativ);
  **Slate (`accent`) ist die leise Stimme** für Info/aktiv/Links im dichten ERP.
- **ERP:** Struktur vor Fläche (Haarlinien + Weissraum statt Schatten), Status als
  Punkt+Wort, Symbole (Lucide) statt Text, tabellarische Zahlen, Infotexte im Hover.
- **Die Alt-Palette ist weg** (August 2026): `slate-*`, `blue-*`, `gray-*`, `#2563eb`
  und der `brand-*`-Vorrat sind aus dem Code entfernt – **0 Vorkommen**. Wer sie wieder
  einführt, führt eine zweite Farbsprache ein; die Zuordnung steht als Lesehilfe in
  `docs/design-system/README.md §4`.
- Density: kompakt aber luftig – 8px-Grid. Font: Inter (Body) / Inter Tight (Display).

## Leitbild (VERBINDLICH)

### ERP ist Master – alles andere ist Spiegelbild
Jeder Datensatz hat **genau EINEN Ort, an dem er gepflegt wird: das ERP.** Oberflächen
ausserhalb des ERP (Konto/Profil, Admin-Seiten, Shop) sind **Spiegel** – sie zeigen an,
sie besitzen nicht. Konkret:

- Dieselbe fachliche Angabe darf **nie an zwei Stellen editierbar** sein. Existiert ein
  ERP-Datensatz dafür, ist die andere Stelle read-only mit Verweis («wird am ERP-Datensatz
  … gepflegt»).
- Ein Formular ausserhalb des ERP darf schreiben, wenn es der **Selbstbedienungs-Pfad** einer
  Person auf ihre EIGENEN Daten ist (Profil, Rechnungsadresse) – dann ist es derselbe
  Datensatz über denselben Endpunkt, nicht eine zweite Wahrheit.
- Beim Anfassen einer Oberfläche prüfen: *Gibt es diese Eingabe schon woanders?* Wenn ja,
  die schwächere Stelle zum Spiegel machen, statt die Logik zu duplizieren.
- **Das ERP muss ALLES können**, was aussenrum geht – nicht nur anzeigen. Konkret am
  Benutzer: `ErpAdminUpdate` **erbt** von `UserProfileUpdate` (alles, was die Person selbst
  pflegt) und ergänzt die Anstellungsdaten. Geprüft in `tests/test_frontend_mirrors.py`.
- Schreiben beide Oberflächen denselben Datensatz, tun sie es über **denselben Pfad**
  (`people.apply_profile_update` – gleiche Zuweisung, gleiches Audit-Log). Sonst ist eine
  Änderung je nach Herkunft nachvollziehbar oder eben nicht.

### Eine Sache, eine Stelle
Gleiches gleich behandeln: gleiche Bedeutung → gleicher Name, gleiche Datenform, **eine**
Implementierung (z. B. `services/address.py` für Adressen, `services/people.py` für
Personennamen, `services/places.py` für Orte und Halter, `services/lookup.py` für
«welchen Datensatz meinst du» (Nummer ODER Name), `objects.obj_nr` für die Objektnummer,
`components/erp/address-field.tsx` für jede Adress-Eingabe). Zwei Wege für dieselbe
Sache sind ein Bug, auch wenn beide funktionieren.

Braucht eine Regel zwei **Formen** – eine, die den **Grund** nennt, und eine, die über
eine ganze Liste **prüft** –, stehen beide nebeneinander in EINEM Modul und tragen
denselben Namensstamm: `process.pick_problem()` sagt, warum genau dieses Stück nicht
greifbar ist, `process.unpickable()` beantwortet dieselbe Frage für eine Auswahl. So
sagen Oberfläche und Freigabe garantiert dasselbe. Zwei Formen einer Regel sind in
Ordnung; zwei Regeln sind es nicht.

**Spiegel über die API-Grenze** (Frontend braucht Symbol/Label zu Backend-Aufzählungen)
sind erlaubt, aber getestet: `backend/tests/test_frontend_mirrors.py` vergleicht die
handgepflegten TS-Unions (`StepType`, `LocationType`, `ArticleUnit`) und die Labels gegen
die Backend-Quellen. So bleibt der Spiegel schnell und kann trotzdem nicht auseinanderlaufen.

## Konventionen
- Alle DB-Felder: snake_case, Englisch
- API-Endpunkte: /api/v1/{resource}
- Timestamps: IMMER UTC in DB, Frontend konvertiert mit Intl.DateTimeFormat
- Soft-Delete: Niemals hard delete – nur is_active=false
- Fehler: strukturiert, mit einem Satz, der die betroffene Sache **nennt** (Nummer oder
  Name in «») – «Bestätigen nicht möglich» ist eine Sackgasse mit Ausrufezeichen
- Max. Funktionslänge: 80 Zeilen
- TypeScript strict mode – kein `any` (geprüft: 0 Vorkommen)

## Nummernkreis
Universell 9-stellig: 100'000'001–999'999'999. Gilt für ALLE Objekte.
Tabelle: objects(id, object_type, created_at, updated_at, created_by, updated_by, is_active)

## Wichtige Entscheide
- **Artikel haben keine Versionierung**: Änderung → neuer Artikel, und der **Nachfolger**
  nennt seinen Vorgänger (`replaces_object_id` bei der Anlage → `replaced_by_id`). Ersetzen
  **bedeutet** ausser Betrieb nehmen – ein Vorgang, ein Aufruf.
- **Serialisierung**: `unit` = jedes Stück ein eigener Datensatz · `batch` = ein Datensatz
  trägt alle Stücke. Das Arbeitsobjekt ist in beiden Fällen die **Einzelinstanz**.
- **Autosave** überall: debounced 3 s, Enter löst sofort aus, Rückmeldung im Karten-Kopf.
  Kein Speichern-Knopf – die eine Ausnahme ist das Anlegen eines Prozessschritts.
- **MWST CH** (für den späteren Beleg vorgemerkt): 8.1 % Standard · 2.6 % Reduziert ·
  3.8 % Beherbergung · 0 % Export. EU B2B: 0 % + Reverse Charge (VAT-ID auf der Rechnung).

## Sicherheit

**Gebaut:**
- HTTPS/TLS, HSTS, CSP und die übrigen Security-Header (`firebase.json`)
- Anmeldung über Firebase; **Passkeys/WebAuthn** serverseitig (`services/passkey.py`)
- Secrets über Google Secret Manager (nie im Repo, nie in `.env.example`)
- **Optimistic Locking** (`services/lifecycle.ensure_version`) – heute am Artikel;
  jede weitere Schreibstelle, die es braucht, ruft dieselbe Funktion

**Vorgemerkt, nicht gebaut:** TOTP-MFA für Admins, Session-Timeout, Brute-Force-Sperre.

## DSGVO / Schweizer DSG
- CH DSG (01.09.2023) + DSGVO für EU
- Plausible Analytics: Privacy-by-Design, kein Cookie-Banner
- AGB-Akzeptanz: Zeitstempel + Version in DB
- 10-Jahres-Archivierung Buchungsbelege (unveränderlich)

## Pflichtregeln für Claude – vor jeder Änderung

> Diese Regeln sind VERBINDLICH und müssen bei jeder Arbeitssitzung eingehalten werden.

### 1. Immer zuerst mit Remote synchronisieren
Vor der ERSTEN Code-Änderung einer Sitzung zwingend ausführen:
```bash
git fetch origin develop
git pull origin develop
git log --oneline -5
git status
```
Erst danach dürfen Dateien gelesen oder editiert werden.

### 2. Dateien immer frisch lesen – niemals Zusammenfassungen vertrauen
Kontext-Komprimierungen (Context Summaries) beschreiben Dateien so, wie sie *waren*, nicht so, wie sie *aktuell* auf `develop` liegen. Vor jedem Edit die Datei mit dem Read-Tool neu laden.

### 3. Änderungen nur auf Basis des aktuellen `develop`-Stands
Niemals auf Basis von:
- gespeicherten Kontext-Beschreibungen aus einer früheren Session
- eigenen früheren Edits, die noch nicht gepusht/gemerged wurden
- Annahmen über den Dateiinhalt

### 4. Branch-Workflow
- Entwicklung auf Feature-Branch (z.B. `claude/...`)
- Merge nach `develop` erst nach expliziter Freigabe durch den User
- Direktes Pushen auf `develop` nur wenn ausdrücklich angewiesen

## Lokale Entwicklung
```bash
# Backend starten
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend starten
cd frontend && npm install
npm run dev

# Datenbank
createdb inexxio_local
cd backend && alembic upgrade head
```

## Status (aktuell halten)
Phase: 1 | Deployment: develop → https://inexxio-dev.web.app

### Was heute steht (Stand August 2026)

**Fundament, produktiv nutzbar**
- **Öffentliche Website**: Startseite, Über uns, Kontakt (Formular), Impressum, AGB,
  Datenschutz – statisch exportiert, Firmendaten dynamisch aus dem ERP.
- **Anmeldung**: Firebase (Magic Link · Google SSO · **Passkeys/WebAuthn**), als Pop-up
  über der Seite, auf der man steht. Cookie-/Einwilligungs-Layer ohne Fremd-CMP.
- **Konto**: «Mein Profil» (Person · Adressen · Kommunikation, ein Auto-Save) und
  «Sicherheit» (Passkeys verwalten).
- **ERP-Feed** (Master-Detail, eine Route): Benutzer · Artikel · Aufträge · Instanzen ·
  Unternehmen. Universelle 9-stellige Objektnummer, QR-Etikett und Kamera-Scan an jedem
  Datensatz.
- **Artikel**: Spezifikation (frei benannt, gekappt auf 32 Zeichen, Dubletten-Vorschläge
  ohne KI), Bestand in drei Ebenen, Reihe (ersetzt/ersetzt durch) und die gemeldete
  Stückliste – ausser Betrieb nehmen ist ein Statuswechsel in beide Richtungen.
- **Prozess**: Auftrag → geordnete Modul-Liste → Einzelinstanzen passieren sie; jeder
  Statuswechsel schreibt in den append-only Ereignis-Log. **Fünf Module** (Datenerfassung ·
  Aussondern · Verbrauch · Bewegen · **Zahlung**), Abweichungen als
  ganz gewöhnliche Aufträge, Prozessbild als serverseitig gerechneter Graph.
- **Zahlung** (§9.12): Geld mit einer zweiten Partei, in beide Richtungen dasselbe Modul –
  und es bewegt **keine Stücke**. Angebotsspiegel → Zusage → Rechnungen und Zahlungen als
  Zeilen daneben; *offen*, *fällig* und *überfällig* als Ableitung, null Spalten. Steuer je
  Position (MWSTG Art. 26) und **eine Währung je Vorgang** (ISO 4217, mit den
  Nachkommastellen der Währung).
- **Online bezahlen – in der eigenen Karte** (§9.13): «Jetzt bezahlen» öffnet das
  Zahlungsformular **im ERP**, nicht auf einer fremden Seite; die Gegenpartei bezahlt über
  ihren eigenen, engen Zugang. Was das ERP weiss (Name · E-Mail · Rechnungsadresse), wird
  nicht noch einmal gefragt. Gebucht wird nur vom **Webhook**.
- **Unternehmen**: mehrere gleichrangige Gesellschaften mit eigener Rechtsidentität,
  Gebietskarte, ein gewählter Betreiber für die eine Website.
- **Testnotizen** in der laufenden Oberfläche (nur Testumgebung), als Markdown kopierbar.

**Nicht vorhanden** (entfernt, nicht abgeschaltet – `docs/attic.md`): der **Shop**,
die Module **Beschaffen**, **Verkauf** und **Ausliefern** (§9.9a – was die ersten beiden
konnten, kann der Geldvorgang; das dritte war ein Scan und ein Statuswechsel),
Dokumente/Belege, Rechtstexte aus dem Dokumentmodul, KI-Assistent,
Versand-Anbindung, der Ereignis-Strom als Outbox. Ebenfalls nie gebaut: E-Mail (Gmail
API), Typesense-Suche, Buchhaltung, HR.

**Nächste Aufgabe**: Prozess-Module nach Bedarf. Der Wiederaufbau eines entfernten
Bereichs beginnt bei der Modellfrage in `docs/attic.md`, nicht bei der alten Datei.
Am Datenmodell ist **eines offen und es braucht einen Menschen**: die Tabellen der
entfernten Bereiche (`events`, `document_*`, `article_prices`, `ai_actions`, und neu
`purchases`, `invoices`, `payments` …) stehen noch. Kein Modell verweist auf sie, sie kosten nichts – aber ihr Drop ist unumkehrbar
und verlangt vorher eine Sicherung der **produktiven** Datenbank (`docs/backlog.md`).

## Deployment
- Trigger: Push auf Branch `develop`
- Workflow: .github/workflows/deploy-dev.yml
- Backend: Cloud Run (inexxio-dev, europe-west6)
- Frontend: Firebase Hosting (inexxio-dev → https://inexxio-dev.web.app)
- Nach Änderungen: git push → develop mergen → git push develop
- Erster Besuch nach Deploy: einmal Hard-Refresh (Ctrl+Shift+R) nötig

## Phasenplan
| Phase | Zeitraum | Inhalt |
|-------|----------|--------|
| 1 – Fundament | Mt. 1–5 | Google Cloud, Firebase Auth, Website DE+EN, ERP Kern |
| 2 – Kernprozesse | Mt. 6–10 | PO + Lieferantenportal, Produktion, SO + Kundenportal, Stripe |
| 3 – Erweiterungen | Mt. 11–16 | NCR/8D, CAPA, Audit, Risiko, ISO 9001, HR, Buchhaltung |
| 4 – KI & Auto | Mt. 17–22 | Bestellvorschlag KI, Semantische Suche, OCR |
| 5 – Advanced | Mt. 23+ | Bexio-Integration, Onshape API, ISO 14001 |
