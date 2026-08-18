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
> **Der zentrale Schalter:** `backend/app/core/features.py` (`ACTIVE`), gespiegelt in
> `frontend/src/lib/features.ts`. Aktiv: `core`, `catalog`, `capture`. Abgeschaltet:
> `process`, `sales`, `documents`, `ai` – deren Prefixe beantwortet ein Stub mit 503 und
> Grund. Die Module dieser Bereiche liegen weiterhin im Repo, sind aber **nicht
> importierbar** (Liste in `tests/test_no_undefined_names.DISABLED_PREFIXES`).
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
> woanders war. Die **Historie** hängt am **Symbol** des Prozessobjekts, nie an einer
> gekürzten Beschriftung: `truncate` ist `overflow: hidden` und schneidet das `::after`
> weg – genau daran war sie am Modul unsichtbar und an Start/Ende sichtbar.
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

> **WICHTIG:** Vollständige und verbindliche Projekt-Anforderungen in `docs/Lastenheft_v1.0.md` – vor Entwicklungsarbeiten konsultieren.

## Was ist Inexxio?
Zentrales Unternehmenssystem für ein produzierendes Schweizer KMU (AG, Maschinenbau).
Kombination aus Website/Shop + ERP + Buchhaltung + HR + Qualitätsmanagement.

Rechtsform: Aktiengesellschaft (AG), Schweiz
Branche: Produzierendes Gewerbe / Maschinenbau
Mitarbeiter: ca. 10 | Artikel: ca. 1'000

## Architektur
```
Frontend:  Next.js 14, TypeScript, App Router, Tailwind CSS, PWA
Backend:   FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic v2, Alembic
DB:        PostgreSQL 15 (Cloud SQL), universeller 9-stelliger Nummernkreis
Auth:      Firebase Authentication (Magic Link + Google SSO + Passkeys/WebAuthn + TOTP MFA für Admin)
Storage:   Google Cloud Storage
Search:    Typesense (Phase 2)
Email:     Gmail API (info.inexxio@gmail.com Phase 1 → @inexxio.com ab Phase 2)
Payments:  Stripe (Phase 2)
KI:        Claude API (Anthropic)
Infra:     Google Cloud Run + Firebase Hosting
Analytics: Plausible Analytics (DSGVO-konform)
```

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
├── shared/
│   └── types.ts           ← Geteilte TypeScript-Typen
├── .env.example           ← Vorlage für Env-Variablen
└── docs/
    └── adr/               ← Architecture Decision Records
```

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
- **Alt = deprecated:** `slate-*` / `blue-600` / `brand-*` (blaue Alt-Marke) sind
  Altlast; beim Anfassen einer Komponente auf die Tokens migrieren (Tabelle in
  `docs/design-system/README.md §4`). Kein Big-Bang – inkrementell mitziehen.
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
Personennamen, `services/locations.py` für Standorte, `objects.obj_nr` für die
Objektnummer, `components/erp/address-field.tsx` für jede Adress-Eingabe). Zwei Wege für
dieselbe Sache sind ein Bug, auch wenn beide funktionieren.

Braucht eine Regel zwei **Formen** (SQL-Bedingung *und* Prüfung auf einem geladenen
Objekt), stehen beide nebeneinander in EINEM Modul und tragen denselben Namensstamm –
`inventory.in_stock_clauses()` / `inventory.is_in_stock()`. Zwei Formen einer Regel sind
in Ordnung; zwei Regeln sind es nicht.

**Spiegel über die API-Grenze** (Frontend braucht Symbol/Label zu Backend-Aufzählungen)
sind erlaubt, aber getestet: `backend/tests/test_frontend_mirrors.py` vergleicht die
handgepflegten TS-Unions (`StepType`, `LocationType`, `ArticleUnit`) und die Labels gegen
die Backend-Quellen. So bleibt der Spiegel schnell und kann trotzdem nicht auseinanderlaufen.

## Konventionen
- Alle DB-Felder: snake_case, Englisch
- API-Endpunkte: /api/v1/{resource}
- Timestamps: IMMER UTC in DB, Frontend konvertiert mit Intl.DateTimeFormat
- Soft-Delete: Niemals hard delete – nur is_active=false
- Fehler: Immer strukturiert { error: string, code: string, details?: any }
- Max. Funktionslänge: 80 Zeilen
- TypeScript strict mode – kein 'any'

## Nummernkreis
Universell 9-stellig: 100'000'001–999'999'999. Gilt für ALLE Objekte.
Tabelle: objects(id, object_type, created_at, updated_at, created_by, updated_by, is_active)

## Wichtige Entscheide
- Artikel haben keine Versionierung: Änderung → neuer Artikel + replaced_by_id
- BOM hat keine eigene Versionierung: neue BOM = neuer Artikel
- Serialisierung: qty=1→Einzelteil (unit), qty>1→Batch
- QC-Checks sind Arbeitsplan-Schritte (step_type='qc_check')
- Prozessabschluss: Pflichtfeld-Check + Signatur-Check vor Status 'Completed'
- Autosave: Debounced 3s, grüner Rahmen-Flash
- MWST CH: 8.1% Standard | 2.6% Reduziert | 3.8% Beherbergung | 0% Export
- MWST EU B2B: 0% + Reverse Charge (VAT-ID auf Rechnung)

## Sicherheit
- HTTPS/TLS 1.3, HSTS, CSP, Security Headers
- 2FA für Admin (TOTP Firebase MFA, verpflichtend)
- Session-Timeout 8h | Brute-Force Sperre nach 5 Versuchen
- Google Secret Manager für alle Secrets
- Optimistic Locking: updated_at-Vergleich vor jedem Update

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

### Tatsächlich gebaut (Stand Juni 2026)
- Monorepo-Struktur vollständig
- Backend: FastAPI mit UserProfile (Benutzer- & Profilverwaltung), Admin-Einstellungen, Audit-Log, Kontaktformular
- Backend: Artikel-Stammdaten (`articles`, Status draft/released/inactive, gemeinsamer Nummernkreis via `services/objects.py`)
- Frontend: Öffentliche Website (Homepage, Über uns, Kontakt, Impressum, AGB, Datenschutz)
- Frontend: ERP mit Reitern Benutzer + Artikel (Master-Detail-Feed)
- Frontend: Artikel-Anlage via «+» (Pflichtfelder Name/Einheit/Serialisierung/Grösse/Gewicht), Detailfenster mit Reitern Stammdaten/Prozess/Bestand
- Frontend: Admin Einstellungen + Benutzerverwaltung
- **Betriebskosten Monat-bis-heute** (`GET /admin/operating-costs`, `services/operating_costs.py`): am
  Unternehmens-Datensatz eine kompakte Übersicht der **tatsächlichen** laufenden Kosten – KI aus dem
  Event-Strom (verbrauchte Tokens × Modell-Tarif), Zahlungen aus Stripe-Gebühren der bezahlten Verkäufe,
  Infrastruktur als anteilige Google-Cloud-Schätzung; grosse Ist-Summe + Monats-Hochrechnung.
- Frontend: Profileinstellungen – **auf 4 Reiter konsolidiert**: «Mein Profil» (Person + Adresse +
  Rechnungsadresse + Newsletter/AGB-Nachweis, gestapelt), «Bestellungen & Abos», «Meine Dokumente»,
  «Sicherheit». Der frühere «Benachrichtigungen»-Reiter ist entfernt (die Toggles `notification_email`/
  `notification_inapp` hatten KEINE Backend-Wirkung – kein E-Mail-/In-App-System; Spalten bleiben für die
  spätere Gmail-Anbindung). Vollständigkeits-Badge (`useProfileCompletion`) rechnet Adresse/Rechnung neu
  dem Profil-Reiter zu. **Runde 2:** «Mein Profil» ist jetzt EINE Komponente (`profile-section.tsx`) mit
  **einem** Formular/Auto-Save und **drei** Containern – Persönliche Angaben (inkl. **Telefon**),
  **Adressen** (Liefer- + Rechnungsadresse über EINEN «Rechnungsadresse = Lieferadresse»-Schalter im
  gleichen Container), Kommunikation (Newsletter + AGB-Nachweis als **Tatsache**, nicht als Fake-Toggle).
  `contact-section.tsx`/`invoice-section.tsx`/`privacy-section.tsx` sind entfallen. Toggle-Optik ist
  einheitlich (`ToggleField`, rot = an). **Rechnungs-E-Mail** zeigt die Konto-Adresse als Platzhalter
  (leer = dorthin). **Adresszusatz** bleibt (Shippo-Etiketten brauchen c/o · Postfach · Stockwerk), wird
  aber erst auf «+ Adresszusatz» eingeblendet statt als leeres Dauerfeld.
- **Frische Daten nach einer Pause – ohne Polling** (`erp/page.tsx`, `lib/api.ts`, `lib/firebase.ts`):
  Der ERP-Feed war ein **Schnappschuss vom Seitenaufbau** (ein `useEffect([])`, sonst nichts) – wer ein
  paar Minuten weg war, sah alte Daten und musste F5 drücken. Verschärfend: der Bearer-Token ist ein
  In-Memory-Schnappschuss (Firebases proaktive Erneuerung ist ein Timer, der im Hintergrund-Tab
  gedrosselt wird), und **jeder 401 wurde still verschluckt** → der Feed rendete «Keine Datensätze»
  statt eines Fehlers. Zwei Eingriffe, beide kostenneutral: (1) `api.setTokenProvider` – bei einem 401
  wird **einmal** ein frischer Token geholt (`getIdToken(true)`) und dieselbe Anfrage wiederholt
  (registriert in `firebase.ts`, kein Import-Zyklus); (2) Rückkehr-Refresh: bei `visibilitychange`/
  `focus` lädt der Feed **einmal** nach – aber nur, wenn er älter als `STALE_AFTER_MS` (60 s) ist.
  Kein Intervall, kein Polling: ein Nachladen je Rückkehr, nichts beim kurzen Tab-Wechsel.
- **Code-Cleanup & Härtung (Juli 2026, `docs/cleanup-2026-07.md`)**: Migration `060` –
  **Meldebestand-Bug behoben** (`orders.reason` VARCHAR(12)→(20): `replenishment` hat 13
  Zeichen, JEDE Auto-Nachbestellung scheiterte vorher am Truncation-Fehler); GIN-Index auf
  `instances.reservations` + Indizes `sales.customer_id`/`orders.recurring_parent_id`/
  `purchase_orders.supplier_id`; PR-#90-Spalten in Alembic nachgezogen (Alembic = Schema-SSOT);
  tote Spalten (`orders.stripe_checkout_session_id`, `sales.fx_rate`), das nie verdrahtete
  `Notification`-Modell und die F-Rollback-Reste (#85) entfernt. **Race-Conditions gehärtet**
  (Row-Locks): Stripe-Webhook-Doppelzustellung (CheckoutIntent), FIFO-Allokation in allen
  Schreibpfaden (kein Überverkauf), `ensure_supply`/`check_article` (kein Doppel-Nachschub);
  Shop-Handler mit FX-/Stripe-Calls als `def` (kein Event-Loop-Blocking). Tote Endpunkte
  (`GET /shop/session/{id}`, `GET …/sales/audience`, `GET /erp/instances/{id}/documents`)
  + totes i18n (`frontend/messages/`, next-intl war nie installiert) entfernt. Wording
  kanonisch (Spezifikation/Charge/Instanz/Standort). Responsive: Inline-Grids kollabieren
  auf Mobile, Warenkorb auf Tokens + umbrechend, Touch-Ziele ≥40px, Freiraum fürs KI-Widget.
- **Architektur-/Logik-Review (Juli 2026, `docs/review-2026-07.md`)**: systematische Prüfung auf
  Zirkularitäten/Blockaden/Logiklücken; 15 Befunde sofort behoben. Kernpunkte: (1) **Shop-Versand
  repariert** – der Shop-Verkaufsauftrag legte seinen Versandschritt OHNE `locked`/`mode='customer'`
  an → nach Zahlung dauerhaft «blockiert», kein Shop-Auftrag konnte je versendet werden (Fix +
  Datenreparatur Migration `074`); (2) **«verkauft durch DIESEN Auftrag» zählt als GELIEFERT**
  (`process.sold_amounts_for_order` aus dem Event-Strom) statt als «verloren» – vorher Phantom-
  Fehlmengen nach Zahlung (Nachschub auf volle Menge dimensioniert, Chargen-Retoure kam mit Menge 1
  statt der verkauften Menge zurück; NACH Verkauf verschrottete Instanzen bleiben ehrlich fehlend);
  (3) **Kunden-Versand bewegt nur Verkauftes/Eigenes** (`movement.movable_instances`, EINE Auswahl-
  regel für Ausführung/Embed/Versand-Beleg) – vorher wanderte der unverkaufte Rest einer teilverkauf-
  ten Charge zum Kunden; reine Teilmengen-Sendung quittiert ohne Umlagerung statt 409; (4) **Kopier-
  Vollständigkeit**: `_copy_steps` (Ersetzen/Wiederkehr) kopiert jetzt `doc_signers`/`sign_sequential`/
  `doc_audience*`/`doc_visibility`/`transport_mode`, `duplicate_article` auch `is_hazmat`/`reorder_
  target`/Beschaffungsquelle (vorher: Consent-Lücke + Freigabe-Gate-Bruch beim
  Nachfolger); (5) **Unterschriften-Deadlocks**: Ausstellen prüft aktive Parteien, Admin-Deaktivierung
  blockiert bei offenen Signoffs, abgelehntes Signoff bleibt für den Eigentümer re-aktionabel und hält
  die sequenzielle Position; (6) **Consent-Supersede erst bei in Kraft getretener Nachfolge**
  (freigegebenes Dokument, nicht schon beim Entwurf-Nachfolger); (7) **Auto-Abweichung** wird nicht
  mehr von offenen Nachschub-Kindern unterdrückt (`open_deviations` filtert `reason='deviation'`);
  (8) **steckengebliebene Nachbestellung** (fehlgeschlagener Schritt) unterdrückt Auto-Nachbestellung
  nicht mehr (Stockout-Schutz); (9) **Race-Fixes**: Row-Locks in `release_order` (Doppel-Freigabe →
  doppelte Instanzen), `recovery.cover_from_stock` (Instanz-Wahl), `_issue_refund` (Doppel-Refund;
  zudem: Stripe-bezahlter Verkauf verlangt Stripe-Provider für die Erstattung), Kunden-Retoure
  (Doppelklick); Scrap prüft Meldebestand VOR dem Abschluss (keine Nachbestell-Kette).
  **Folgethemen-Umsetzung (gleicher Monat, `docs/review-2026-07.md §3`)**: Slice-Retouren
  (Teilmengen-Verkauf einer Charge ist retournierbar – Subjekte aus `process.sold_amounts_for_order`,
  Rückfluss mengengenau in die Original-Charge, event-idempotent, erst nach quittierter Rückgabe-
  Bewegung); Consent-Gate serverseitig (`consent.assert_acknowledged` an Checkout/Retoure/Lieferanten-
  Offerte); `doc_visibility` als Lese-Zugriffsfilter + **Parteien-Substitution** am laufenden Auftrag
  (`POST …/document/substitute-signer`); Benutzer-Identität (deaktiviert = 403 beim Login statt
  stiller Neuanlage; `POST /admin/users/{id}/reactivate` + FE-Knopf); **CheckoutIntent-Reaper** im
  Wartungs-Sweep (verlassene Warenkörbe geben Reservierungen nach 24 h frei); **Produktabo-Auto-
  Fulfillment** (`invoice.paid` released den Wiederkehr-Entwurf und verbucht die Zahlung);
  `legal_ack_config` entfernt (Migration 075); Kleinigkeiten (Preis-Pin committet keine fremden
  Änderungen mehr, Publikums-Obligationen ohne N+1, Refund-Ablehnung bei Alt-Beleg ohne Snapshot im
  Mehrpositionen-Fall). **Einzig offen aus dem Review: «fehlgeschlagener Schritt ist terminal»**
  (bewusst zurückgestellt – braucht ein «Schritt wiederholen»-Design).
- **Generische Auftrags-Prozess-Engine** (`services/process.py`): Der Auftrag führt eine geordnete
  Liste von Prozessschritten (`article_process_steps`, pro Artikel optional & frei sortierbar via
  `position`). Schritt-Status wird aus der Fachtabelle abgeleitet (keine Orchestrierungstabelle);
  Auftrag wird **automatisch `completed`**, wenn alle Schritte erledigt sind.
  **Bestands-Instanzen entstehen direkt bei der Auftragsfreigabe** (kein eigener Schritt mehr,
  `services/serialization.py`): Einzelteil → N Stück-Instanzen, Batch → 1 Charge à N (`instances`,
  eigene Objektnummer). Startstandort = **Lieferant** (Beschaffung mit Lieferant) sonst Wareneingang –
  volle Rückverfolgbarkeit/Aktionen ab Tag 1 (Standort, Seriennummer, Reklamation).
  **Instanz-Lebenszyklus – ZWEI getrennte Achsen** (Migration `030`, statt überladenem `qc_status`):
  `quality` ∈ pending|passed|**blocked** («darf man es verwenden?») und `disposition` ∈ in_process|in_stock|consumed|
  sold|scrapped («wo ist es?»). Neue Instanzen starten `(pending, in_process)`; bei Auftrags-Abschluss
  → `(passed, in_stock)` («Freigegeben, ab Lager verbrauchbar») via `process.recompute_completion` →
  `release_instances`. **FIFO-Basis ist die Freigabe des STÜCKS** (`units` → `t`, siehe unten);
  `released_at` an der Instanz ist nur noch deren Projektion. Datenerfassung gibt NICHT vorzeitig frei (nur
  Durchfaller → `quality=blocked` = «Gesperrt», Migration `085`). Verbaut → `disposition=consumed`, verkauft → `sold`, verschrottet →
  `scrapped`. **Verbrauchbar/zählbar = `quality=passed` UND `disposition=in_stock`** – die EINE Helper-
  Stelle `inventory.in_stock_clauses()` (von Bestand/FIFO/Betriebsmittel geteilt). Anzeige: eine Badge
  als Projektion beider Achsen (`lib/process.ts: instanceStatusConfig`).
  **Reservierung:** bei der Auftragsfreigabe werden die zu verbrauchenden Komponenten für genau diesen
  Auftrag reserviert (`instances.reserved_for_order_id`); reservierte Instanzen sind für andere Aufträge
  nicht verbrauchbar (FIFO blendet sie aus). Auflösung bei Abschluss/Deaktivierung des Auftrags.
  **Mehr-Operationen-Routing:** mehrere gleichartige Schritte (z. B. mehrere `resource`-Operationen)
  sind hintereinander möglich – jede Fachzeile trägt die `step_id` ihrer Schritt-Definition, der
  Status wird **pro Schritt** abgeleitet (`process.fact_for_step`/`resolve_exec_step`). Schritttypen:
  - **purchase** (Beschaffung): Bestellung `purchase_orders` unter dem Auftrag (keine eigene Nummer),
    Ablauf requested→quoted→ordered→received (+rejected); webshop: requested→ordered→received.
    Offerte = **eine Bestellsumme** (netto), Stück-/Einstandspreis = Summe÷Menge. Saubere
    Verantwortungstrennung (Lieferant offeriert, Besteller bestellt/nimmt an). Die **Lieferadresse**
    ist die **Firmenadresse**; den realen Wareneingangs-Ort setzt die **Bereitstellung** nach der
    abgeschlossenen Beschaffung (`provisioning.ensure_provisioning`) – NICHT mehr die Bestellung selbst.
    **Bezugsquelle wird IM PROZESSSCHRITT definiert** (max. Flexibilität – ein Prozess darf mehrere
    `purchase`-Schritte mit UNTERSCHIEDLICHEN Lieferanten/Quellen haben, was ein reines Artikel-Feld
    nicht abbilden kann): am Schritt `article_process_steps.mode` (supplier|webshop) +
    `supplier_id`/`webshop_url`. Der **Artikel-Standard** (`articles.procurement_mode` +
    `default_supplier_id`/`default_webshop_url`, Reiter «Spezifikation» → Beschaffung) dient als
    **Vorbelegung/Fallback**: das Schritt-Formular ist damit vorbelegt und leer gelassene Schritte erben
    ihn. `purchase.resolve_source(step, article)` ist die EINE Auflösung (Schritt ≻ Artikel-Default),
    ihr Ergebnis wird als Snapshot auf die Bestellung geschrieben; `serialization._initial_location`
    erbt den Lieferanten-Startort ebenso. **Freigabe-Gate** (`purchase.has_source(step, article)`): ein
    Artikel/Auftrag mit `purchase`-Schritt lässt sich nur freigeben, wenn die Bezugsquelle **am Schritt
    ODER als Artikel-Default** auflösbar ist (Router-Check in `articles.py`/`orders.py`; das Frontend
    warnt proaktiv am Schritt, `procurementReady`).
  - **inspection** = «**Datenerfassung**»: allgemeine Werterfassung (nicht nur QC) – nennt **konkret die
    zu prüfenden Instanzen** (Stichprobe). Prüfumfang % via `sample_percent`: Einzelteil → N zufällig
    (stabil) ausgewählte Instanzen; Charge → eine Instanz mit N Proben. Je Stichprobe ein Wertesatz
    (`inspections.samples`), konfigurierbare Maske (`capture_fields`: Soll-Ist mit Toleranz / Gut-Schlecht /
    Text; ohne Maske synthetisches Gut-Schlecht). **Ungenügende Teil-Stichprobe → Hochstufung auf 100 %**
    (`inspections.escalated`); erst bei vollem Umfang endgültig `failed`, dann je Instanz bewertet (Charge
    als Ganzes). Durchfaller werden **gesperrt** (`instances.quality='blocked'`, `services/inspection.py`) –
    derselbe Zustand wie beim Schritt «Sperren»; **geklärt wird nur über den Folgeauftrag**
    (`inspections.resolved_by_order_id`, siehe Testnotizen-Runde 6).
  - **movement** = «**Bewegung**»: bringt Instanzen an ihren Standort. Jede Instanz hat **immer** einen
    Standort (`instances.location_type` ∈ user|instance|company + `location_id` = Objektnummer des
    Ziels). Der Lagerist setzt je Instanz das Ziel (auch unterschiedliche Ziele pro Auftrag möglich);
    optionales Vorgabe-Ziel am Schritt – **ein** kombiniertes Auswahlfeld (Person/Instanz/Unternehmen),
    leer = Standort nicht definiert/frei wählbar. Abschluss-Marker = `movements` (analog inspection, keine
    eigene Nummer); Standorte direkt auf den Instanzen (`services/movement.py`, `services/locations.py`).
    **Charge auf mehrere Standorte verteilen – AUFTRAGSGETRIEBEN (`services/location_split.py`, Migration
    `067`)**: Eine Charge (z. B. 1000 Schrauben unter EINER Objektnummer) kann physisch auf mehrere
    Standorte verteilt sein (990 @ Eingang, 10 @ Band A) – **ohne Teilung der Instanz / ohne neue
    Objektnummer**, exakt nach dem Vorbild von `reservations`: `instances.locations` = Map
    `{ziel_objektnr: {"t":typ,"q":menge}}` (Summe = quantity). Ein Ort → Map `NULL`, der Skalar
    `location_*` ist die Wahrheit; verteilt → die Map ist die Wahrheit, der Skalar spiegelt die **grösste**
    Teilmenge (denormalisiert, wie `reserved_for_order_id`). **Das Verteilen geschieht AUSSCHLIESSLICH über
    einen regulären Auftrag + Bewegungsschritt, NICHT als Aktion an der Instanz:** ein Bestands-Auftrag über
    z. B. 10 Stück reserviert mengengenau 10 der 1000er-Charge (FIFO, `subject._allocate_stock_for`); der
    Bewegungsschritt verlagert **genau diese vom Auftrag reservierte Teilmenge** ans Ziel
    (`movement.record_movement`: `share = reserved_for(inst, order)`, dann `location_split.move`), der Rest
    bleibt liegen. GANZE Instanz / Erzeugung / Kunden-Versand / Retoure (keine Teil-Reservierung) →
    `location_split.set_single` (führt eine verteilte Charge wieder zusammen). Das Panel zeigt die bewegte
    Teilmenge (`InstanceEmbed.move_quantity`). Am **Instanz-Detail** ist die Verteilung nur **read-only**
    sichtbar (`components/erp/instance-locations.tsx`) – kein Verlagern dort. FIFO/Verbrauch/Reservierung
    sind **standortunabhängig** und unberührt; Teil-Verschrottung/-Verbrauch ziehen die Verteilung per
    `location_split.reconcile` nach. «Wer liegt hier?» (`references.object_references`) findet eine Charge
    auch über ihre Teil-Slices (`locations ? '<objektnr>'`, GIN-Index).
  - **consume** = «**Verbrauch**» / **tool** = «**Betriebsmittel**»: zwei Schritttypen – der
    **Modus ist der Schritttyp** (NICHT Artikel-Eigenschaft, NICHT pro Zeile; `article.kind` gibt es
    nicht mehr). Je Schritt eine Liste von Zeilen (`resource_lines` = [{article_id, quantity **pro
    Stück**}]). **consume**: Bauteil wird in die **Produkt-Instanz eingebaut** (Standort → `instance`)
    = Lagerabgang; Auswahl strikt **FIFO nach Freigabe des Stücks** (`units.fifo_since`),
    Chargen-**Teilentnahme**. **tool**: Werkzeug/Maschine wird nur **genutzt** (kein Lagerabgang, kein
    FIFO, freie Wahl). Nur **freigegebene** (qc passed) Instanzen verbrauchbar/nutzbar; Verfügbarkeit
    wird geprüft. Beide buchen in `resource_usages` (keine eigene Nummer); Genealogie via Instanz-
    «Verwendung» (Eingebaut in/Enthält, Betriebsmittel-Nutzung) – `services/resource.py`. Das Panel
    zeigt den Verbrauch **je Produkt-Instanz** (welche Komponenten-Instanz in welche Produkt-Instanz
    verbaut wird; Vorschau = FIFO-Plan, danach das Protokoll) – `ResourceEmbed.products`.
- **KEIN Prozess-Objekt mehr** (Migration `031`): Ein Prozess ist nur noch die geordnete Schrittliste,
  die ENTWEDER am **Artikel** (`article_process_steps.article_id`, «wie etwas entsteht», EIN Prozess je
  Artikel) ODER am **Auftrag** (`order_id`, individueller Ablauf) hängt. Keine Objektnummer, kein eigener
  Lebenszyklus, keine n:m-Verknüpfung, kein `is_standard`, keine `source`. Tabellen `processes` +
  `article_process_links` sind entfernt; Feed-Typ «Prozesse» weg. `services/processes.py` liefert nur noch
  `article_steps`/`order_custom_steps`/`has_custom_steps`. Schritt-CRUD generisch über
  `routers/article_process.py` (`/articles/{id}/steps` und `/orders/{id}/steps`).
- **Auftrags-Subjektart – EINE Bedingung: hat der Auftrag einen eigenen Ablauf?** (kein Modus-Flag,
  Testnotiz #622): **produce** (keine eigenen Schritte → fährt den **Artikel**-Prozess, und NUR der
  ERZEUGT Instanzen) | **stock** (eigener Ablauf → wirkt auf vorhandenen Bestand: FIFO ab Lager bzw.
  via `instances.subject_of_order_id` fixierte Instanzen). **Instanzen entstehen ausschliesslich aus
  dem Prozess des Artikels** – ein Auftrag mit eigenem Ablauf greift zu, er erzeugt nie.
  **Zurückgenommen (war ein schwerer Fehler):** früher leitete `subject.subject_kind` die Art über die
  deklarierte **Schritt-Rolle** ab (`derive_subject_mode`/`SUBJECT_PRECEDENCE`, `stock ≻ produce ≻
  instance`) – ein order-eigener **Beschaffungs**-Schritt trug `produce`, also erzeugte ein Auftrag mit
  «Beschaffen + Datenerfassung» neue Instanzen, obwohl der Mensch im Bedarf ausdrücklich «Ab Lager»
  gewählt hatte: zwei Aussagen über dieselbe Sache, und die unsichtbare gewann. Die Begründung der
  alten Regel (ein solcher Auftrag band bei leerem Lager still 0 Instanzen) ist weggefallen – heute
  meldet er eine **Unterdeckung** (sichtbar, blockiert den Schritt, Nachschub fährt den Artikel-Prozess,
  ADR 003). Die Rolle wird darum **gar nicht mehr deklariert** (siehe Registry-Punkt unten). Zweiter
  Riegel: `serialization.create_instances_for_order` weist einen Auftrag mit eigenem Ablauf selbst ab.
  Frontend spiegelt dieselbe eine Bedingung (`ProcessSteps.onStepsCount(n)` – die Schrittzahl IST die
  Antwort; `lib/process.isStockOperation` ist entfallen).
  `subject_instance_id`/`process_id`/`orders.mode` sind entfernt.
- **Freigabe auf Artikel-Ebene**: Die Artikel-Freigabe (Reiter «Spezifikation») friert Spezifikation **und**
  Prozess gemeinsam ein – Schritte sind nur im Artikel-Entwurf editierbar. Ein **make-Auftrag startet nur**,
  wenn der **Artikel freigegeben** ist (einzige Vorbedingung, `routers/orders.py`). Bei der Artikelanlage
  entsteht KEIN Auto-Prozess mehr; Schritte werden im Reiter «Prozess» direkt am Artikel gepflegt.
- **Deklarative Ereignis-Registry (REA-Kern, `app/domain/event_types.py`)**: EINE Quelle der Wahrheit
  für jeden Schritt-/Ereignistyp – Label, **Bestands-Polarität** (increase/decrease/move/neutral),
  **Bereitstellungsort** und Fachtabelle. *Die frühere **Subjekt-Rolle** (produce/stock/instance) samt
  `derive_subject_mode`/`SUBJECT_PRECEDENCE` ist **entfernt** (#622): sie war eine zweite Aussage
  darüber, ob ein Auftrag erzeugt, und überstimmte die ausdrückliche Wahl «Ab Lager». Die Regel steht
  jetzt allein in `subject.subject_kind`.* Die Polarität ist **deklariert**, nicht
  aus der Prozessform erraten. `process.STEP_LABELS`/`_FACT_MODEL`/`RESOURCE_STEP_TYPES`, die
  Lager-Richtung eines Auftrags (`aggregate_stock_effect`) und die Schema-Whitelist
  `ALLOWED_STEP_TYPES` lesen alle aus dieser Registry (`processes.derive_source`/`recompute_source`
  gibt es seit dem Wegfall des Prozess-Objekts nicht mehr).
  Die **`consume`/`tool`-Alt-Schritttypen sind entfernt** (nur noch `resource`,
  Modus je Zeile). Bestandswirksame Vorgänge schreiben ihre Polarität in den Event-Strom
  (`inventory.increased`, `resource.recorded` mit `polarity`/`delta`) → Event-Log als ökonomische Wahrheit.
- **Lager-Richtung wird ABGELEITET, nicht gewählt** (Frage 2): KEIN Richtungs-Dropdown mehr.
  `stock_effect` ist das **Aggregat der Schritt-Polaritäten**: increase | decrease | **mixed** (Zu- UND Abgang) |
  neutral – ehrlich auch bei gemischten Prozessen statt 1:1-Spiegel der Subjektart. Anzeige als Badge
  (`ProcessResponse.stock_effect`, `OrderResponse.process_stock_effect`).
- ERP-Feed: Datensätze nach Nummer **absteigend**; **Instanzen** sind eigener Feed-Typ
  (`/api/v1/erp/instances`, read-only Detail). Prozessdefinition im BPMN-Stil (Typ-Auswahl beim
  Hinzufügen, Drag&Drop-Reihenfolge, Start/Ende-Knoten).
- Status als **Prozess** (kein Dropdown): Entwurf →[Freigeben]→ Freigegeben →[Deaktivieren]→ Inaktiv
  (→[Reaktivieren]); gilt für Artikel/Auftrag (`lib/status-flow.ts`, `StatusFlow`)
- Frontend: Artikel-«Prozess»-Reiter (Schritttypen hinzufügen/sortieren), **Bestand**-Reiter zeigt die
  Instanzen. Auftrag heisst starr «Auftrag», nur **freigegebene** Artikel referenzierbar, Menge mit
  Artikel-Einheit, Wunsch-Liefertermin optional (Default «Schnellstmöglich»), Bedarf nach Freigabe
  read-only. Auftrag-Detail: Sektion **Instanzen** (bei Freigabe erzeugt, mit Standort/QC) +
  **Auftrag-Stepper** über alle Schritte (Schlüssel = Schritt-id, mehrere gleichartige möglich) + Panel
  des gewählten Schritts (Beschaffung/Datenerfassung/Bewegung/Ressource); Lieferant sieht nur die
  Beschaffung seiner Aufträge.
- **Standorte – der Datensatztyp «Lagerplatz» ist ERSATZLOS entfallen** (Juli 2026): ein Lagerplatz
  war ein eigener Datensatz mit Feed, Detailfenster, Status-Fluss, Adresse, Massen, Traglast und
  Flags – und **kein einziges** dieser Felder trug Logik (Nachweis: ausserhalb von Modell/Schema
  tauchten sie nur in der Kopierfunktion des «Ersetzen» auf). Faktisch war er eine **Objektnummer
  mit Namen**. Entfernt sind: Modell/Schema/Router `storage_locations`, Feed-Typ + Detailfenster,
  `storage_location_in_use`/`duplicate_storage_location`, `storage_location_references`,
  `address.of_storage`, das KI-Tool `storage_locations`, `company_settings.default_receiving_
  location_id` und `purchase_orders.receiving_location_id`.
  **Ein Standort ist nur noch ein Halter:** `LOCATION_TYPES` = **user | instance | company**
  (`company` = «im Betrieb», Adresse aus den Firmen-Stammdaten – der Ersatz für den internen
  Lagerort; ein benannter Platz/Behälter ist eine ganz normale **Instanz**). **Standortlos bleibt
  ein regulärer Zustand** (`serialization._initial_location` gibt `NULL` zurück, ausser die
  Lieferanten-Beschaffung ist der erste Schritt → Start beim **Lieferanten**).
  **Gelesen wird tolerant, geprüft nur beim Schreiben:** `location_label`/`location_labels` lösen
  einen unbekannten/veralteten Typ (Altbestand `'lagerplatz'`) zu `None` = «kein Standort» auf –
  nur `validate_location` und die Pydantic-Validatoren weisen ihn ab. Darum kann Altbestand keine
  Ansicht zerlegen (auf echtem PostgreSQL über alle Detail-/Feed-Endpunkte verifiziert).
  Zwei Stellen trugen echte Bedeutung und wurden dabei **besser**: die **Lieferadresse** für den
  Lieferanten ist jetzt die **Firmenadresse** statt einer Lagerplatz-Objektnummer (`orders._receiving_
  label`), und `logistics.target_address` hat endlich einen `company`-Zweig (vorher hätte ein
  Firmen-Ziel «Empfänger-Adresse unvollständig» ergeben). **Kern-Fix im gleichen Zug:**
  `process.return_subjects_to_stock` erkannte die Rückkehr einer Retoure an `location_type ==
  'lagerplatz'` – mit dem Wegfall des Typs hätte das **nie mehr** zugetroffen und keine Retoure
  wäre je wieder eingebucht worden; jetzt gilt «die Instanz liegt **nicht mehr beim Kunden**»
  (Kunde vom **Original-Verkauf**, da die Retoure selbst nur `kind='credit'`-Belege trägt).
  Mengeneinheiten: Stk/mm/m²/**m³**/kg/l. Den **Wareneingangs-Ort** setzt die **Bereitstellung**
  nach der abgeschlossenen Beschaffung (Ziel: die Firmenadresse, `locations.company_location`);
  der **Bewegungs**-Schritt verteilt von dort weiter.
- **Adressen: EINE Darstellung** (`services/address.py`): Person und Unternehmen
  tragen historisch **verschiedene Spaltennamen** (`address_line1`/`postal_code` an der Person
  vs. `street`+`street_nr`/`zip_code` am Unternehmen). Dieses Modul ist die eine Stelle, die
  das übersetzt – kanonische Form `{name,street1,street2,zip,city,state,country,email,phone}`
  (identisch mit dem Versand-Adress-Snapshot). `of_user(u, ship|invoice|home)` kapselt den
  **Rückfall auf die Wohnadresse** (stand vorher an jeder Aufrufstelle einzeln ausgeschrieben),
  `of_company`/`of_storage` die jeweilige Herkunft; dazu `one_line` (Anzeige), `lines`
  (Briefkopf/Etikett), `same` (normalisierter Ortsvergleich) und `iso2`. Es delegieren:
  `logistics` (`_addr_user`/`_addr_company`/`_addr_storage`/`same_place`/`iso2`),
  `document_render` (Briefkopf), `payments/stripe_provider` (Liefer-/Rechnungsadresse; die
  Stripe-Feldnamen bleiben, nur die Fallback-Logik ist zentral) und `ai/tools` (Firmen-Info).
- **Auftrag-Anlage: EINE Zeile je Position (UI-Refresh Runde 2, `order-detail.tsx`)**. Vorher zerfiel die
  Anlage in ~8 Container (Bedarf-Karte, 3 grosse Ziel-Karten, Ergebnis-Banner, Instanz-Picker-Karten,
  Ablauf) – und der **Mehrpositionen-Fall sah völlig anders aus** als der Einzel-Artikel-Fall (Ziel-Karten
  vs. Segment-Umschalter), sodass das Hinzufügen einer Position das Fenster umbaute. Jetzt: **eine Position
  = eine Zeile** (`PositionRow`) mit Artikel · Menge · **Quellen-Umschalter** und – nur bei Bedarf – der
  Instanz-Auswahl darunter; **dieselbe Zeile** für einen wie für viele Artikel (`lineSource`/`setLineSource`
  vereinheitlichen `goal` und `lineMode`). Statt Banner steht **eine Ergebniszeile** je Position («5 Stk ab
  Lager, älteste zuerst · nur 3 da – Rest per Nachschub»). Gesperrte Optionen nennen den Grund im **Hover**
  statt in der Fläche. **Wortwahl allgemein statt spezifisch:** «Herstellen / Beschaffen» → **Erzeugen**,
  «Aus dem Lager» → **Ab Lager**, «Instanz wählen» → **Auswählen**. Der Termin ist eine Zeile, kein
  Feld-Raster. `GoalCard`/`OutcomeBanner` sind entfallen. **Die Backend-Logik ist unverändert** – rein
  Präsentation (Subjektart wird weiterhin abgeleitet, nicht gewählt).
- **Code-Cleanup ERP (Juli 2026, Migration `081`)** – drei Runden, alles ohne Verhaltensänderung:
  **(1) Tote Achse Unterschrift/Foto (8 Spalten).** Beim Umbau der Datenerfassung auf frei
  konfigurierbare `capture_fields` wurden `photo`/`signature` normale **Feldtypen**; die alte
  Parallel-Mechanik blieb tot stehen: Definition (`article_process_steps.require_signature/
  signer_ids/require_photo/photo_instruction` – das Frontend setzte sie beim Anlegen hart auf
  `false` und las sie nie) und Ergebnis (`inspections.signature_url/signed_by/signed_at/photo_url`
  – **nirgends geschrieben**; gelesen wurde nur `signed_by`, das damit immer NULL war, der
  Auftrags-Embed zeigte also nie einen Unterzeichner). Dazu `article_process_steps.transport_mode`
  (trug die von `076` abgeschafften Werte + eine **zweite, veraltete** `ALLOWED_TRANSPORT_MODES` –
  zwei Wahrheiten für dieselbe Sache; ein Test prüfte ausgerechnet die veraltete) und
  `article_process_steps.locked` (Migration `079` hatte den Drop auf den Folge-Deploy vertagt).
  **(2) Überlange ERP-Kernfunktionen** auf die 80-Zeilen-Regel gebracht, entlang **fachlicher**
  Nähte statt nach Zeilenzahl: `to_order_response` 155→53 (`_fill_demand`/`_instance_embeds`/
  `_attach_step_embed`), `update_order` 123→62 (`_assert_status_transition` = die vollständige
  Zustandsmaschine, `_assert_releasable` = die drei Freigabe-Gates an EINER Stelle),
  `record_movement` 91→66, `record_scrap` 91→49 (`_scrap_one` kapselt «ganz oder Teilmenge»),
  `build_resource_embed` 86→58. *Bewusst gelassen: `render_pdf`/`run_chat`/`fulfill_intent` –
  ausserhalb des ERP-Kerns.*
  **(3) Quelltext-Guards robuster:** Tests, die eine Einzelfunktion zeilengenau prüften, prüfen
  jetzt das **Modul** – dieselbe Fachaussage, aber sie brechen nicht mehr bei jeder internen
  Umstrukturierung. Dazu drei ungenutzte Imports.
- **Bereitstellung: physische Bewegungen werden ABGELEITET, nicht geplant** (Juli 2026,
  `services/provisioning.py`, Migration `080`): Das System legt **KEINEN** Prozessschritt mehr
  an. Der Nutzer modelliert nur die **fachlichen** Schritte (kaufen, verbauen, verkaufen);
  jeder physische Transport, der daraus zwingend folgt, entsteht **zur Laufzeit**.
  **Warum die Vorgänger-Lösung falsch sein musste:** Beim Modellieren ist gar nicht
  entscheidbar, ob eine Bewegung nötig sein wird – ob die Schraube schon am Band liegt oder
  in Halle B, zeigt sich erst zur Laufzeit. Jedes vorgeplante Bewegungs-Modul rät deshalb:
  mal überflüssig (Teil liegt längst richtig), mal fehlend (Teil liegt woanders, aber niemand
  hat den Schritt eingeplant). Die gesperrten Pflicht-Bewegungen (`locked`, selbstheilend
  neu positioniert) und danach das einmalige Säen (`seed_companion_movements`) sind beide
  ersatzlos entfernt – `services/process_steps.py` gibt es nicht mehr, ebenso wenig den fest
  eingebauten Shop-Versandschritt.
  **Die vier Regeln:** (1) jeder Schritttyp deklariert in `domain/event_types.py`, **wo sein
  Material sein muss** (`provisioning`); (2) ist ein Schritt dran (oder gerade erledigt), wird
  **Ist ↔ Soll** verglichen; (3) stimmt es → **nichts passiert** (der häufigste Fall, komplett
  unsichtbar); (4) stimmt es nicht → ein **Bereitstellungs-Unter-Auftrag**
  (`orders.reason='provisioning'` + `orders.provisioning_step_id`) holt genau diese Instanzen
  an ihren Soll-Ort.
  **Warum Unter-Auftrag und nicht Schritt im Auftrag:** Ein Bewegungs-Schritt bewegt immer die
  Instanzen **seines** Auftrags (`movement.movable_instances`). Die Komponente aus Halle B
  gehört aber nicht zum Subjekt – sie ist eine Ressourcen-Zeile; der Schritt könnte sie gar
  nicht greifen. Ein Unter-Auftrag kann es, weil er ein **eigenes fixiertes Subjekt** trägt –
  exakt wie Abweichung und Retoure. Damit ist die Systematik symmetrisch: **nichts da** →
  `supply` (blockiert den Schritt) · **falscher Ort** → `provisioning` (blockiert den Schritt) ·
  **kaputt** → `deviation` (pausiert den ganzen Auftrag).
  **Der Zeitpunkt ist je Schritttyp verschieden – und muss es sein** (`_STAGE_BEFORE`):
  Ressource stellt **vor** der Ausführung bereit (die Komponente muss da sein, bevor verbaut
  wird), Beschaffung/Verkauf **danach** (die Ware kommt an bzw. geht hinaus, nachdem der
  kaufmännische Vorgang durch ist). Ohne die Trennung würde erst BESTELLTE Ware sofort in den
  Betrieb gebucht – buchhalterisch da, bevor sie geliefert ist.
  **Abstufung nach Distanz** (dieselbe Mechanik, andere Konsequenz – über die bestehende
  Adress-Klassifikation aus ADR 005, kein zweites Regelwerk): **innerhalb derselben Adresse**
  bucht der Unter-Auftrag sich sofort selbst ab (zwanzig Meter durch die Halle brauchen kein
  Formular); **über Adressgrenzen** bleibt er offen für Tarifwahl, Label und Quittierung.
  Die automatische Buchung ist eine **Behauptung**, keine Beobachtung – das Audit-Log hält sie
  ausdrücklich als «systemseitig zugewiesen, nicht quittiert» fest.
  **Zwei Fallstricke, beide getestet:** (a) Die Bereitstellung hängt `subject_of_order_id`
  **nicht** um (nur `record_link`) – sonst verlöre der Eltern-Auftrag sein Subjekt; (b) zum
  Kunden gehen **nur `sold`-Instanzen** über die VOLLE Instanzliste (`order_instances`), denn
  `sold` ist terminal und `order_active_instances` blendet es aus – über die aktive Liste
  hätte der Kundenversand nie ausgelöst, und eine teilverkaufte Charge wäre als Ganzes zum
  Kunden gewandert. Wächter: `test_smoke.py: test_system_never_plans_process_steps`,
  `…_keeps_parent_subject_binding`, `…_timing_differs_by_step_type`,
  `…_to_customer_only_moves_sold_units`, `…_sub_order_buckets_are_explicit_per_reason`.
  *Alt-Bestand:* früher gesäte Begleit-Bewegungen (`article_process_steps.companion`) bleiben
  gültige Schritte und behalten ihre Fachwirkung (`provisioning.is_companion`: festes Ziel
  «Kunde», Ausnahme von der Fehlmengen-Prüfung); nie ausgeführte werden von Migration `080`
  deaktiviert.
- **Standort-Kette «wo genau?»** (`locations.location_chain`, `InstanceResponse.location_path`):
  liefert den vollen Pfad von innen nach aussen – Instanz → Behälter → Unternehmen → **Anschrift**
  (`location_type='address'`, ohne Objektnummer). Zyklensicher, auf 10 Stationen begrenzt, und
  bewusst **nur im Instanz-Detail** gefüllt (ein Datensatz, ≤10 Auflösungen) – Feeds bleiben bei
  den Batch-Labels. Frontend: `components/erp/location-path.tsx` rendert sie als eingerückte
  Kette im bestehenden Karten-Design (Stationen klickbar, die Anschrift nicht – sie ist kein
  Datensatz). **Die Kette startet beim unmittelbaren Halter, NICHT bei der Instanz selbst** (die
  ist ja schon geöffnet – die frühere «Diese Instanz»-Zeile ist entfernt) und ist die **einzige**
  Standort-Anzeige im Instanz-Detail: die frühere zusätzliche «Standort»-Kachel im Glance-Grid ist
  entfallen. Sie rendert jetzt auch bei nur EINEM Halter bzw. «Nicht festgelegt» (kein
  Verschachtelungs-Schwellenwert mehr); bei einer verteilten Charge weist sie auf die
  Aufteilung darunter (`InstanceLocationsCard`) hin.
  **Die Kette ist Dekoration, nie der Datensatz** (`routers/instances.safe_location_path`):
  scheitert ihre Auflösung (Altdaten, gelöschter Halter), kostet das die Kette – die Instanz
  bleibt lesbar, der echte Fehler geht mit Objektnummer ins Log; das Frontend verwirft
  unbrauchbare Stationen still.
- **Wächter gegen `NameError` im Backend** (`tests/test_no_undefined_names.py`): ein im
  Funktionsrumpf benutzter, aber nie importierter Name ist in Python **kein** Import- oder
  Syntaxfehler – er fliegt erst, wenn genau dieser Pfad läuft. Genau so kam `LocationHop` in
  `routers/instances.py` durch alle Netze (Tests, `dump_openapi`, Deploy, App-Start alle grün)
  und liess trotzdem **jeden** Aufruf von `GET /erp/instances/{id}` mit 500 auflaufen. Der Test
  prüft über `symtable` (stdlib) je Modul, dass jeder als **global** aufgelöste Name nach dem
  Import wirklich existiert – und dass **jedes** Modul unter `app/` importierbar ist. Das ist
  die Python-Entsprechung zu ESLint, die im Backend gefehlt hat. Gemeldet wird nur, was
  **gelesen und nirgends gebunden** ist: Python 3.12 inlinet Comprehensions (PEP 709), womit
  `[k for k, m in KATALOG]` auf Modulebene `k`/`m` in die Symboltabelle legt, obwohl sie nie
  Modul-Attribut werden – gebunden und darum harmlos (CI läuft 3.12, lokal 3.11; die Regel ist
  über 3.11/3.12/3.13 gegengeprüft). Ein **Selbsttest** hält den Wächter scharf: er muss die
  Bug-Form melden und die Comprehension-Form durchlassen – ein Wächter, der nie anschlägt, ist
  von einem kaputten nicht zu unterscheiden.
- **Verbauen setzt den Standort über die EINE Schreibstelle** (`resource._relocate` →
  `location_split.set_single`): eine Komponente wandert beim Einbau auf die Produkt-Instanz
  (und damit über die Kette physisch mit ihr mit). Vorher wurde `location_type`/`location_id`
  direkt zugewiesen – eine zuvor auf mehrere Standorte **verteilte Charge behielt dabei ihre
  veraltete `locations`-Map** und galt gleichzeitig als verbaut UND anteilig woanders liegend.
- **Generischer Rückverweis «wer zeigt auf mich» je Objektnummer** (`services/references.object_references`,
  `GET /erp/objects/{id}/references`): was aktuell an einer Objektnummer **verortet** ist (`instances.
  location_id == id`, ohne Typ-Filter – Objektnummern sind global eindeutig) + referenzierende
  Prozessschritte. Reiter **«Verwendung»** generisch an Benutzer/Instanz (Frontend
  `components/erp/object-references.tsx`); `storage_location_references` delegiert darauf. AGB/Datenschutz-
  Artikelnummer wird auch **am ERP-Unternehmens-Datensatz** gepflegt (`organization-detail`, Sektion
  «AGB & Datenschutz»), nicht nur Admin → Einstellungen.
- **Consent-Gate: versionierte Bestätigung von Pflichtdokumenten** (`services/consent.py`,
  `routers/consent.py`, `models/document_acknowledgement.py`, Migration 064): Bestätigungspflichtige
  Dokumente sind **hart verdrahtet** (`consent.MUST_ACKNOWLEDGE_KINDS = ("agb",)`) – **kein Admin-Häkchen**,
  gilt für **jede** angemeldete Rolle (Mitarbeiter, **Lieferant**, Kunde, Admin; Endpunkte an
  `get_current_user`). Verlangt wird eine Art nur, wenn tatsächlich ein Dokument auflösbar ist. Die
  **Version** ist die Objektnummer der gültigen Dokument-Instanz (`legal.resolve` folgt der Artikel-/
  `replaced_by_id`-Kette). Wer welche Version wann bestätigt hat, liegt append-only in
  `document_acknowledgements` (Nachweis CH DSG/DSGVO; AGB spiegelt weiterhin `terms_accepted_at`). Am
  **Benutzer-ERP-Datensatz** wird der Nachweis gezeigt («AGB akzeptiert am … · Stand <Objektnr>»,
  `GET /consent/acknowledgements/{user_object_id}`). `GET /consent/pending` liefert offene Bestätigungen,
  `POST /consent/acknowledge` quittiert. Frontend: **blockierendes Modal** `components/consent/consent-
  gate.tsx` (in ERP-, Konto- und Public/Shop-Layout gemountet, self-contained via `onAuthChange`) – zeigt
  je ein Dokument mit «gelesen + akzeptieren», bis nichts mehr offen ist. **Serverseitig erzwungen**
  (`consent.assert_acknowledged`, 403) an den kritischen Aktionen: Shop-Checkout, Retoure-Anfrage,
  Lieferanten-Offerte (`PATCH …/purchase`, nur Rolle supplier) – das Modal ist kein reines UI-Gate mehr.
  *(Die nie ausgewertete Spalte `legal_ack_config` ist entfernt (Migration 075); Rollen-Feinsteuerung
  läuft über das Dokument-Publikum `doc_audience`.)*
- **Artikelnamen (frei + intelligente Vorschläge, KI-unabhängig)**: Namen sind **frei wählbar**
  (kein Katalog-Zwang mehr), aber auf **`NAME_MAX_LENGTH=32` Zeichen** gekappt (zentral in
  `schemas/article.py: clean_article_name`, Frontend `maxLength`). Beim Tippen schlägt das System
  **bereits verwendete oder ähnliche** Namen vor, um Dubletten zu vermeiden – **ohne KI/Kosten**,
  rein lexikalisch (Trigramm-Jaccard + Substring-/Wortstamm-Bonus, `services/article_names.py`,
  erkennt gemeinsame Stämme wie «schraub» → «Akkuschrauber»/«Schraubendreher»). Endpoint
  `GET /erp/articles/name-suggestions?q=…` (`ArticleNameSuggestion{name,count,score}`); Frontend
  `NameField` (Freitext + Vorschlags-Dropdown, Dubletten-Hinweis). Der frühere Admin-Katalog
  `company_settings.article_names` ist **vollständig entfernt** (Modell/Schema/API + Admin-UI) –
  Vorschläge stammen ausschliesslich aus echten Artikelnamen.
- **Optionale Artikel-Stammdaten** (dynamische Feldliste, nur bei Bedarf): `material`, `cad_url`
  (CAD-Link), `surface` (Oberfläche), `min_order_qty` (MOQ), `safety_stock` (Sicherheitsbestand).
  Im Spezifikation-Reiter über «+ Feld hinzufügen» einblendbar; nur befüllte Felder werden
  gespeichert/angezeigt. *Der frühere **«Fixierte Standort»** (`fixed_location_*` + `MapPicker`,
  Migration 069) ist mit Migration `088` **ersatzlos entfallen** (Notiz #168): er trug einen
  GPS-Punkt samt reverse-geocodierter Adresse, war aber rein deskriptiv – kein Bestands-Standort,
  keine Logik. Ein Artikel ist eine **Gattung**; einen Ort hat immer nur die **Instanz**
  (`instances.location_*` + `locations.location_chain`). Die Angabe war damit eine zweite,
  konkurrierende Antwort auf «wo ist das?» – und die schwächere.*
- **Durchlaufzeit** je Artikel (read-only, analog Preisspanne): kürzeste–längste Zeit zwischen Freigabe
  (`orders.released_at`) und Abschluss (`orders.completed_at`) über erledigte Aufträge
  (`ArticleResponse.lead_time_days_low/high`, berechnet in `routers/articles.py`).
- **Abweichung (vereinheitlicht Abbruch-Folgeauftrag / Fehler / Reklamation / Nacharbeit)**: KEIN eigener
  Datentyp – eine Abweichung ist ein **Unter-Auftrag** (`orders.parent_order_id`), der aus einem laufenden
  Eltern-Auftrag heraus entsteht und auf dessen Instanzen wirkt – OHNE Lager-FIFO/-Reservierung (die
  Instanzen sind bereits in Arbeit/im Besitz). Der Eltern-Auftrag **pausiert** (`process._is_paused_by_
  deviation`), solange eine Abweichung offen ist. `services/deviation.py`; Endpoint `POST /orders/{id}/
  deviation` («Abweichung melden», am Auftrag- und Instanz-Detail). **Auto-Trigger**: fehlgeschlagene
  Datenerfassung legt automatisch eine Abweichung auf die Durchfaller-Instanzen an (idempotent,
  `auto_deviation_from_inspection`). Der frühere eigenständige `Claim`-Typ ist **vollständig entfernt**
  (Migration 037 droppt `claims`).
  - **Abbruch ist ein Antrag, kein Vollzug (reversibel)**: «Abbrechen» (`POST /orders/{id}/abort`) setzt
    einen freigegebenen Auftrag NICHT direkt inaktiv, sondern erzeugt einen Folgeauftrag (Entwurf,
    `abort_into_id`) und **pausiert** das Original. Erst die **Freigabe** des Folgeauftrags vollzieht den
    Abbruch (`apply_abort_on_release`, `keep_instances=True`) – keine herrenlosen Teile. Bis dahin zwei Wege
    über DENSELBEN Mechanismus: Folgeauftrag **freigeben** (Schritt einlagern/verschrotten/nacharbeiten =
    Auflösung) ODER **«Abbruch zurücknehmen»** (`deviation.revoke`, `POST /orders/{id}/revoke`) → Original
    läuft **unverändert** weiter (ein Entwurf hat die Reservierungen nie gelöst). „Weitermachen" ist KEIN
    eigener Schritttyp, sondern das Zurücknehmen des Abbruchs. Ein Entwurf ohne Instanzen wird direkt inaktiv.
  - **Verschrotten** (`scrap`, Schritttyp, Migration 038, `services/scrap.py`): die definierte Auflösung
    einer Abweichung – gewählte Instanzen → `disposition='scrapped'` (Bestandsabgang, DECREASE/INSTANCE in
    der Registry); Abschluss-Marker `disposals` (keine eigene Nummer). Nur im **Auftrags-Ablauf** zulässig
    (nicht im Artikel-Prozess). Durchfaller sind im Panel vorausgewählt. **«Ersatz»** = Komposition aus
    `scrap` (defektes Teil raus) + Beschaffung/Bestand (neues herein) – kein monolithischer Schritt.
    **Ausschuss ist STANDORTLOS (Migration 070, kehrt 068 um):** die GANZ verschrottete Instanz verliert
    beim Verschrotten ihren Standort (`location_split.clear` in `services/scrap.py`) – ein Standort ist immer
    ein realer **Halter** (Person/Instanz/Unternehmen), den Ausschuss nicht mehr hat; der Endzustand
    `disposition='scrapped'` IST die «Wo»-Aussage. So findet «wer liegt hier» (`references`) ein
    verschrottetes Teil korrekt nicht mehr. **Kein Schrottplatz-Lagerort mehr** (`provisioning.
    send_to_scrapyard`/`resolve_scrap_location` + `company_settings.default_scrap_location_id` entfernt).
    Teil-Verschrottung lässt die gute Restmenge am Lager (Standort bleibt).
- **Bereitstellungsort — «Bewegung wird ABGELEITET, nicht orchestriert»** (`domain/event_types.py`
  `provisioning`, `services/provisioning.py`): jeder Schritttyp DEKLARIERT seinen Bereitstellungsort (wohin
  sein Subjekt/seine Inputs physisch müssen) — Beschaffung→Wareneingang, Verkauf→Kunde, Ressource→Produkt-
  Instanz/Arbeitsplatz, **Verschrotten→standortlos** (`PROV_NOWHERE`, kein Halter mehr),
  Datenerfassung/Bewegung/Dokument→kein fester Ort. Der
  EINE Reconciler `provisioning.reconcile_to(inst, typ, id)` vergleicht Ist↔Soll und bringt die **ganze**
  Instanz ans Ziel — **no-op, wenn schon da**; Teilmengen/Chargen laufen weiter auftragsgetrieben über den
  Bewegungs-Schritt (`location_split.move`). **Verschrotten** hat KEINEN Bereitstellungsort
  (`PROV_NOWHERE`): die Instanz wird standortlos (`location_split.clear`), kein Schrottplatz-Reconcile mehr.
  **Die Deklaration ist jetzt wirksam** (Juli 2026): `provisioning.target_for` löst sie in eine konkrete
  Objektnummer auf, und `ensure_provisioning` (aufgerufen aus `process.recompute_completion`, also nach
  JEDEM Schritt-Abschluss) legt bei Abweichung Ist↔Soll einen **Bereitstellungs-Unter-Auftrag** an – siehe
  «Bereitstellung» oben. Zuvor war der Eintrag reine Beschriftung: `reconcile_to` hatte genau EINEN
  Aufrufer (`resource._use_tool`). *Rückführung/WIP-Puffer/Werkzeug-Rückgabe/mehrstufige Montage sind über
  denselben Mechanismus abbildbar; scan-Quittierung im Verschrotten bleibt Backlog. Ortsfeste
  Betriebsmittel (das Produkt muss zur Maschine, nicht umgekehrt) sind bewusst NOCH NICHT gebaut.*
- **Logistik/Versand — «Versand wird ABGELEITET, nicht bestellt» (ADR 005, `docs/adr/005-logistik.md`,
  Migrationen `071`+`072`)**: der Bewegungs-Schritt kennt Quelle+Ziel → EINE Klassifikation
  (`services/logistics.classify_movement`) leitet die Transportklasse **adress-basiert, OHNE Geofence** ab
  (bewusst einfach: «von A nach B mit anderer Adresse → Versand, sonst intern»): **externe Person**
  (Kunde/Lieferant per Rolle) als Ziel → extern/outbound bzw. als Quelle → extern/inbound (**Abholung
  Lieferant / Kunden-Retoure = DIESELBE Engine**); **Ziel ohne Standort/Adresse → innerbetrieblich**; zwei
  **interne** Orte → Versand NUR bei belegten, **unterschiedlichen** Adressen (Mehr-Standort). Instanz-Ziele
  über die physische Kette (`resolve_physical_location`); `location_kind` (Ownership) + `same_place`
  (normalisierter Adressvergleich) sind die Bausteine. **Transport = EINE Wahl mit drei Optionen**
  `transport_mode` ∈ **internal** (innerbetrieblich, kein Carrier – Vollzug per Scan) | **parcel** (Paket) |
  **freight** (Stückgut/Palette): `logistics.recommend_mode` leitet aus Transportklasse + geschätzter Last
  die **Empfehlung** ab (vorgewählte Default-Auswahl, IMMER frei übersteuerbar am Beleg
  `shipments.transport_mode`). Die frühere **Doppelung Modus×Sendungsart** und die Werte
  `auto/carrier/self/none` sind **entfernt** (Migration `076`); die interne `kind`-Spalte (parcel|freight)
  spiegelt nur noch den Modus (freight ⟺ 'freight'). Der Artikel-Prozess wird nie mutiert; die Alt-Spalte
  `article_process_steps.transport_mode` ist **entfernt** (Migration `081`) – sie trug noch die von `076`
  abgeschafften Werte und eine zweite, veraltete Whitelist. Digitale Payloads = KEIN Fall.
  **Versand-Beleg `shipments`** (Fachzeile je Bewegungs-Schritt, KEINE eigene Nummer): Adress-Snapshots
  (Firma ↔ Ziel-Person/-Halter, Länder → ISO-2), **Paket-Schätzung aus Artikel-Daten** (Gewicht×Menge,
  Grösse mm→cm, Fallback-Karton), Gefahrgut-Warnung (`articles.is_hazmat`, optionales Spez-Feld «Gefahrgut»),
  Rate-Snapshot, Label, Tracking, Kosten; Status draft→quoted→purchased→done. **Carrier-Aggregator = Shippo**
  hinter dem Gateway-Muster (`services/shipping/`: base/shippo/manual, exakt wie payments): aktiviert sich
  selbst über `SHIPPO_API_KEY` (Self-Serve wie Stripe, Pay-per-Label; rechnet nativ cm/kg, Rates inline am
  Shipment, Kauf via `/transactions/`); ohne Key läuft `manual` (Carrier/Tracking von Hand – nie kaputt).
  Anbieter jederzeit austauschbar (EasyPost/Sendcloud = Drop-in-Adapter). **Best-Offer: günstigster =
  Default-Auswahl, Schnellster als Hinweis** (`logistics.quote` markiert cheapest/fastest). Endpunkte am
  Auftrag: `POST …/shipment/quote|buy`, `PATCH …/shipment`; Embed fährt im Bewegungs-Embed mit
  (`MovementEmbed.shipment`, Versand-Box im `movement-panel.tsx`: **3-Wege-Umschalter Im Betrieb | Paket |
  Fracht** mit markierter Empfehlung, Extern-/Gefahrgut-Chip, Tarifliste, Label-PDF, manuelle Erfassung;
  bei «Im Betrieb» keine Carrier-Maschinerie – nur Scan-Hinweis). `record_movement` schliesst den Beleg
  (purchased→done) und übernimmt
  Tracking – **der physische Vollzug bleibt scan-quittiert**. *Bewusst NICHT gebaut: Tracking-Webhooks,
  Carrier-Pickup-Orders, Multi-Parcel, Zoll-Dokumente, Versandkosten-Weiterverrechnung.*
- **Adress-Autofill (Google Places) + verschrottet = standortlos**: alle editierbaren Adressfelder nutzen
  Google-Places-Autovervollständigung (`components/erp/address-autocomplete.tsx` + `use-maps-key.ts`;
  Loader mit `libraries=places`) – Strasse tippen, Vorschlag wählen → Strasse/PLZ/Ort/Land (+Koordinaten)
  automatisch. Verdrahtet in Profil-Adresse/Rechnungsadresse und Unternehmens-Stammdaten. **Bugfix:** eine **verschrottete** Instanz zählt NIE mehr als
  «liegt hier» (`references.object_references` filtert `disposition != 'scrapped'`; Migration `072` nullt den
  Alt-Standort bereits verschrotteter Instanzen).
  - **Unterdeckung → EINE Formel & zwei Deckungs-Wege für ALLE Auftragsarten** (`services/recovery.py`,
    `process._subject_shortfalls`): Kann ein Auftrag sein Soll nicht (mehr) erfüllen – weil eine reservierte
    Instanz **ausgesteuert** wurde (Abweichung verschrottet ein verkauftes/reserviertes Teil) ODER weil ein
    **Erzeugungsauftrag Ausschuss** hatte –, wird die Fehlmenge **ehrlich** sichtbar. **Kein `subject_kind`-
    Sonderpfad mehr:** `_subject_shortfalls` = **Soll − Gesichert** über ALLE Arten. *Gesichert* = für den
    Auftrag **reservierte** Bestands-Instanzen (FIFO/gepinnt/gepeggter Nachschub) **plus selbst erzeugte
    gute** Instanzen; terminal verlorene (verschrottet/verkauft/verbaut) oder durchgefallene zählen nicht.
    So reagiert ein **Erzeugungsauftrag auf Ausschuss identisch** wie ein Bestands-Auftrag auf eine
    ausgesteuerte Reservierung (nur die **Abweichung** ist ausgenommen – ihr Subjekt sind fixierte
    Instanzen). **Core-Fix dazu:** `scrap.record_scrap` löst beim Verschrotten **ALLE** Reservierungen der
    Instanz (`reservation.release_all`) – ein verschrottetes Teil verlässt den Bestand endgültig und kann
    keinen Auftrag mehr beliefern. Der betroffene **Subjekt-Schritt wird «blockiert»** (abgeleitet, kein
    stilles Unterliefern). Personal hat am freigegebenen Auftrag **zwei Wege** (statt vier – „Mensch
    entscheidet"): (1) **Nachschub anlegen** – produzieren/beschaffen (`POST /supply`, ein Unter-Auftrag);
    (2) **Aus Lager decken** – freien Bestand **FIFO** reservieren (`POST /cover-stock` ohne ids), mit
    **Unterkategorie «bestimmte Instanz wählen»** (`POST /cover-stock` mit ids, inline-Picker) –
    `recovery.cover_from_stock`. `StepShortfall` trägt dafür die **Verfügbarkeit** (`available_quantity`/
    `available_instances`) aus freiem Lagerbestand; `_peg_supply_to_parent` erkennt das Subjekt eines
    Erzeugungsauftrags EBENSO wie eines Bestands-Verkaufs (kein Stock-Gate). Nur bei **Subjekt-Schritten**
    (movement/inspection/scrap/sale) – ein reiner Komponenten-Bedarf (Ressource) wird weiterhin über
    Nachschub gedeckt. **«Menge reduzieren» ist bewusst NICHT gebaut:** eine bezahlte Position wird erst
    reduziert, wenn sie zugleich sauber (Stripe) **gutgeschrieben** wird – kommt gebündelt mit der
    Gutschrift-Funktion (TODO), nicht als isolierte Mengen-Kürzung.
  - **EINE On-Hold-Sprache «Prozess angehalten»** (`order-detail.tsx: ProcessHoldNotice`, ersetzt
    `BlockedStepNotice`): Beide Gründe, warum ein Auftrag nicht weiterläuft, teilen sich EIN Muster (gleiche
    Optik wie die Pause-Leiste, `PauseCircle`/amber): (a) **Angehalten – Abweichung offen**
    (`record.paused`): der GANZE Auftrag ruht, solange eine Abweichung offen ist; die Notiz verlinkt die zu
    klärende Abweichung, KEIN interaktives Panel; (b) **Angehalten – Unterdeckung** (`step.state ===
    'blocked'`): nur der betroffene Schritt ruht, mit den zwei Deckungs-Wegen. **Pause blockiert die
    Schritt-Ausführung jetzt auch im UI:** bei `record.paused` wird kein interaktives Panel gerendert (das
    Backend lehnte die Ausführung schon immer via `_assert_not_paused` an ALLEN sechs Schritt-Endpunkten
    mit 409 ab – die Lücke war rein visuell). Ganz-Auftrag-Pause ist fachlich korrekt: eine Sendung mit
    offener Abweichung darf nicht teil-versendet werden, bevor klar ist, ob ein Stück ausgesteuert wird.
  - **Praxistest-Nachbesserungen (Runde 2)**: (1) **«Verkauf» ist ein Subjekt-Schritt**
    (`process.SUBJECT_STEP_TYPES`) – ein Verkaufsauftrag blockiert jetzt bei Unterdeckung (vorher traf
    `sale` weder Subjekt- noch Komponenten-Zweig → reagierte NICHT, wenn sein Bestand per Abweichung
    ausgesteuert wurde). (2) **Verkaufspreis zieht nachträglich nach**: wird der (Einmalkauf-)Preis erst
    NACH der Freigabe am Artikel hinterlegt, zeigt das Sale-Embed den ableitbaren Betrag (Panel nicht mehr
    blockiert) und die Bestätigung holt ihn frisch (`sale._apply_transition` → `_prefill_price`) – sonst
    blieb ein Mehrpositionen-Verkauf ohne editierbaren Betrag stecken. (3) **Charge teilverschrotten**
    (`ScrapUpdate.items` mit `quantity`, `reservation.reduce_quantity`): analog zur Ressourcen-Teilentnahme
    sinkt nur die Menge (keine Teilung/neue Nummer); überschüssige Reservierungen werden getrimmt (Recovery).
    (4) **Mehrpositionen-Auftrag: je Position FIFO ODER Instanz wählen** (nicht mehr global) – segmentierter
    Umschalter je Position (`order-detail.tsx: lineMode`/`PinPicker`/`SegBtn`); ein Auftrag mischt Positionen
    frei. (5) **Position löschen faltet auf Einzel-Artikel zurück**: sinkt ein Mehrpositionen-Auftrag auf
    EINE Position, wird `article_id`/`quantity` zurückgesetzt (`orders.remove_order_line`) – die Ziel-Karten
    aktualisieren sich (Herstellen wieder möglich). (6) **Bewegen-Scan wartet auf die Zielort-Listen**: der
    freie Zielort-Scan wird erst freigegeben, wenn Lagerplätze/Personen/Instanzen geladen sind
    (`movement-panel.tsx: scanReady`) – vorher konnte der letzte Scan-Schritt ohne Kandidaten „nichts
    anzeigen", bis man ihn per Einzel-Scan erneut auslöste.
- **ERP-UX-Konventionen**: Detailfenster speichern per **Auto-Save** (debounced, Enter löst sofort aus,
  grüner Rahmen-Flash; kein Speichern-Knopf – `lib/use-autosave.ts`). Referenz-Auswahlfelder sind
  durchsuchbar (`SearchSelect`, Suche auch per Objektnummer-Teilstring). Referenzierte **Objektnummern
  sind klickbar** und öffnen den Datensatz (`components/erp/obj-id.tsx` + `ErpNavContext`). Artikel ohne
  Prozessschritt sind **nicht freigebbar**. Auftrag-Stepper zeigt beim Hover Wer/Wann je erledigtem
  Schritt; Instanzen haben einen Reiter **Verwendung** (Verwendungsnachweise, neu→alt).
- **Design-Sprache (DAU-tauglich, «Symbole statt Text, Farbe = Bedeutung»)**: Status-Badges sind
  einheitlich **Symbol + semantische Farbe + Label** (`StatusCfg` mit `icon` in den `lib/*`-Status-
  Configs; `StatusBadge` rendert sie als Pille – Feed & Detail-Köpfe). **Ampel-Semantik (nur
  grün/gelb/rot, kein Blau/Petrol/Violett/Slate mehr):** GELB (`--warning`) = offen/in Arbeit/wartend
  (Entwurf, **In Arbeit**, Angefragt/Offeriert/Bestellt, Bestätigt/Verrechnet, Reserviert);
  GRÜN (`--success`) = gut/erledigt/frei (Freigegeben, Abgeschlossen, Geliefert, Bezahlt, am Lager,
  Verkauft, Verbaut); ROT (`--danger`) = Problem/Stopp/tot (Fehler, Abgelehnt, Storniert, **Inaktiv,
  Verschrottet**). Alles läuft über die drei `TONE`-Töne (`lib/status-flow.ts`); Rollen-Badges sind
  bewusst **neutral** (Identität, keine Ampelfarbe). Der Prozess-Stepper
  zeigt **Schritt-Symbole** statt Zahlen. Aktive Prozessschritte haben **eine** grosse, touch-taugliche
  Hauptaktion (`PrimaryButton`, ≥44 px, volle Breite) – «Was muss ich jetzt tun?» auf einen Blick.
  **Gemeinsames UI-Vokabular (`components/erp/fields.tsx`) – konsequent verwenden statt Eigenbau:**
  `Tooltip`/`InfoHint` (Erklärungen/Infotexte gehören in den **Hover**, ⓘ-Symbol – nicht in die
  Fläche), `TileShell`/`TILE` (Kachel-Grundform der Detail-Ansichten: Symbol-Kasten + Versalien-
  Label + Inhalt; jede Kachel trägt ihre eigene Haarlinie und steht in Weissraum – **kein**
  durchgefärbtes Raster, sonst erscheint eine unvollständige letzte Reihe als grauer Block),
  `SectionTitle` (Symbol + Versalien-Label + optional ⓘ + rechter Slot), `PanelHeader`
  (einheitlicher Prozessschritt-Kopf: getöntes Symbol + Titel + ⓘ + rechter Slot/Status – EIN Look
  über ALLE Schritt-Panels), `StatusBadge`, `PrimaryButton`. Leitsatz: «weniger ist mehr» – Symbole
  statt Text, Infotexte in den Hover, sofort erkennbar was Sache ist / was zu tun ist.
- **Bruchmengen (kg · m² · m³ · l, nicht nur ganze Stück)**: alle Mengen sind `Decimal`
  (DB `NUMERIC(14,3)`, Migration `055`): `instances.quantity/reserved_quantity`,
  `orders.quantity`, `order_lines.quantity`, `purchase_orders.quantity`, `sales.quantity`. Die
  **EINE** Mengen-Stelle `services/quantity.py` (`to_qty`/`qty_sum`/`is_whole`) kapselt
  Umwandlung/Rundung – Bestand/FIFO/Reservierung (`inventory`/`reservation`/`subject`/`process`/
  `resource`/`recovery`/`scrap`) rechnen exakt (kein `float`). Die Reservierungs-Map
  (`instances.reservations`) speichert Mengen als **String** (JSON-sicher); `events.emit`
  serialisiert `Decimal`→`float` für den Event-Strom. Am API-Rand sind Mengen `float` (TS
  `number` – Frontend unverändert). **Einzelteil-Artikel (`serialization='unit'`) dürfen nur
  GANZE Stück** (2.5 Schrauben gibt es nicht – Router-Check gegen die Serialisierung); **Chargen
  (`batch`) tragen Bruchmengen** (2.5 kg). Stichprobe: `required_sample` liefert ganze Proben
  (`ceil`, auch für 2.5 kg). Frontend-Inputs (Menge/Ressourcen-Zeile/Teil-Verschrottung)
  akzeptieren Nachkommastellen (kein `Math.trunc` mehr). *Shop-Kauf bleibt ganzzahlig (Stückzahl).*
- **Performance/Infra** (siehe `docs/architecture-review-2026-06.md`): Objektnummern über die
  Postgres-Sequence `object_id_seq` (race-sicher, `services/objects.py`). Auftrags-Feed `GET /orders`
  liefert schlanke `OrderSummary` (ohne Embeds); das Detail kommt **on-demand** via `getOrder(id)`.
  **Domain-Event-Strom** (Outbox) `events` + `GET /api/v1/events?after_id=…` für KI/Automatisierung
  (`services/events.py`). Schema-Management via Alembic (`start.sh`), Lifespan-Safety-Nets als Fallback.
- **QR-Code / Kamera-Scan (zentral, Frontend-only)**: die universelle Objektnummer ist der einzige
  Code-Inhalt. `lib/scan.ts` (`encodeObjectCode`/`parseScannedCode` – tolerant ggü. nackter Nummer &
  URL/Deep-Link; `validateForStep`). Zentraler Scanner: `ScanProvider` + `useScan({ title, steps,
  onComplete })` mountet EINE Dialog-Instanz am ERP-Layout. `ScanDialog` ist **Kamera-first**
  (ZXing `BrowserMultiFormatReader` – **alle** Code-Arten, lazy geladen) mit **sofort sichtbarer**
  manueller **semantischer Suche** (z. B. «003» → 100000003). Ein Scan-Vorgang ist eine **Sequenz**
  von Schritten (`steps`): je Schritt `expected` (Verifikation, grün/rot, Kamera läuft weiter) oder
  `restrict`+`candidates` (Lookup; Code ausserhalb des ERP → Fehlermeldung). **Prozess-Quittierung
  per Scan ist verbindlich:** Bewegung (aktueller Standort → Instanz → Zielstandort), Ressource
  (Produkt-Instanz → Komponente; Betriebsmittel), Datenerfassung (Instanz vor Erfassung).
  Etikettendruck via `printObjectLabel` (`qrcode.react`) im Detail-Kopf; Feed-Button «Scannen»
  öffnet den Datensatz. Kein Backend nötig (Objektnummer = Schlüssel, Feed kennt alle IDs).
- **Verkauf / Shop (MVP, am Artikel – kein eigenes «Angebot»-Objekt)**: Der Verkauf ist eine dritte,
  bewusst **lebende** Ebene am Artikel (analog `landed_unit_cost`): `articles.sales_published/
  sales_visibility/sales_content` + 1:n `article_prices` (mutabel, Soft-Delete) + `article_sales_audience`
  (private/unlisted). Die **Freigabe friert NUR Spezifikation + Prozess** ein – die Verkaufs-Ebene bleibt
  in jedem Status editierbar (eigene Endpunkte `…/articles/{id}/sales[/prices|/audience]`, alles geloggt).
  **Du pflegst NUR den Basispreis in CHF** (genau eine Zahl je Preis); alles andere wird abgeleitet.
  **Zwei unabhängige Achsen:** *Preismodell* (`article_prices.kind` = Einmalkauf | Abo → `orders.recurrence_*`)
  und *Verfügbarkeit* (`articles.sales_fulfillment`, jetzt **1-Bit-Backorder-Policy**): **make** = bei
  Mangel **Nachschub** (Made-to-Order) | **stock** = nur ab Lager FIFO (limitierte Auflage, kein
  Überverkauf). Der Verkauf ist IMMER ein stock/FIFO-Auftrag; was an Bestand fehlt, deckt ein
  **Nachschub-Unter-Auftrag** (ADR 003, siehe unten) – KEIN `subject_source` mehr.
  **Preis-Pipeline** (`services/pricing.py`, gestaffelt, jede Stufe optional): Basis-CHF → ① Kunden-/
  Gruppenpreis (Hook) → ② Zonen-/Kaufkraft-Faktor (PPP, `company_settings.pricing_zone_factors`, Default aus)
  → ③ Rabatt (Vergleichspreis visuell; Coupons = Erweiterung) → **Netto-CHF** → ④ Währung: **gepinnter** Kurs
  (`article_prices.pinned`, `charm_round`, **stabil bis Basis-Änderung oder >3 % Kurs-Drift** – KEINE
  Live-Umrechnung) → ⑤ MWST (`services/tax.py`, CH 8.1/2.6/3.8, Ausland 0 %). Tageskurse unveränderlich in
  `fx_rates` (Env `FX_SOURCE_URL`). **Kauf = ganz normaler Auftrag** mit `sale`-Schritt + `movement`
  (Versand); **Defer-Modell**: der Auftrag wird **erst bei bestätigter Zahlung freigegeben** (make erzeugt
  dann die Instanzen; stock reserviert schon bei Bestellung). Preis/Währung/Steuer werden auf den
  `sale`-Beleg **eingefroren** (Snapshot).
  **Zahlung – Stripe (Vollintegration, `services/payments/`)**: hosted **Checkout Session** (Redirect) für
  Einmalkauf (`mode=payment`) und Abo (`mode=subscription`). **Adaptive Pricing** (kein Währungsumschalter –
  Stripe zeigt die Lokalwährung an der Kasse; Website zeigt CHF) + **Stripe Tax** (`automatic_tax`,
  `tax_behavior=inclusive`). Stripe ist **Quelle der Wahrheit**: Webhook (signaturgeprüft) `checkout.session.
  completed` → Verkauf `paid`, Auftrag freigegeben, **realer Betrag/Lokalwährung/Steuer** als Snapshot
  (`sales.stripe_snapshot/stripe_payment_intent_id`, `orders.stripe_subscription_id`, `user_profiles.
  stripe_customer_id`). **Customer Portal** (Abo/Zahlungsmittel selbst verwalten) via `POST /shop/portal`.
  Provider-Auswahl automatisch `stripe`, sobald `STRIPE_SECRET_KEY` gesetzt ist; sonst `manual` (Fallback,
  `/shop/pay?token=…` + `/shop/payments/simulate`). Setup: `docs/stripe-setup.md`. **Shop** (öffentlich):
  `GET /shop/products|products/{id}` (public für alle, private nur zugewiesene Kunden, unlisted nur per Link;
  **kanonisiert über `replaced_by_id`** – ein ersetzter Artikel zeigt nahtlos auf den Nachfolger, URL/Listing
  brechen nicht), `POST /shop/checkout` (Login-Pflicht, kein Gast-Checkout). Frontend: ERP-Reiter **Verkauf**
  am Artikel (Autosave, Preise/Inhalt de+en/Zielgruppe/Verfügbarkeit/CHF-Vorschau) + Admin-Shop-Konfig
  (Provider/Zonen) + öffentlicher Shop (`/shop`, `/shop/product`, `/shop/cart`, `/shop/checkout`, `/shop/pay` für manual).
  **Ersetzen** kopiert das Verkaufs-Profil auf den Nachfolger. *Bewusst NICHT gebaut: Coupon-Engine,
  Bundles, Gast-Checkout, metered-Abos, kunden-/gruppenspezifische Preislisten, Auto-Fulfillment je
  Abo-Zyklus (TODO-/Extension-Hooks an Ort).*
- **Shop-Phase 8 (Warenkorb · eingebettete Kasse · zwei Abo-Typen · Vereinfachung)**:
  - **Warenkorb** (`lib/cart-context.tsx`, localStorage; `/shop/cart`): mehrere Artikel/Optionen ⇒
    **EINE** Checkout-Session. **Abos werden einzeln** gekauft (Store erzwingt das). **Mehrere
    Preis-Optionen je Produkt** (`ShopProduct.prices`) – der Kunde wählt am Produkt (Einmalkauf /
    Nutzungsabo / Produktabo) und legt in den Warenkorb.
  - **Aufgeschobene Auftragserzeugung** (`CheckoutIntent`, Migration `042`): der Auftrag entsteht
    **erst bei bestätigter Zahlung** (`sales.fulfill_intent`) – Made-to-Order erzeugt dann je
    Position einen Auftrag; **stock** wird schon bei der Bestellung als reservierter Auftrag angelegt
    (kein Überverkauf). Abbruch/Ablauf → `sales.cancel_intent`. Token = Intent-id.
  - **Eingebettete Stripe-Kasse** (`ui_mode='embedded'`, `/shop/checkout` mit
    `@stripe/react-stripe-js`): kein Redirect mehr. Der **Publishable Key** ist öffentlich und kommt
    aus `company_settings.stripe_publishable_key` über `GET /shop/config` (Admin → Systemkonfiguration).
  - **Lieferadresse aus dem Profil** wird auf den Stripe-Customer gespiegelt (Vorbefüllung der Kasse,
    keine Doppeleingabe) – `stripe_provider._profile_shipping`.
  - **Zwei Abo-Typen** (`article_prices.sub_type`, gespiegelt nach `orders.recurrence_kind`):
    **usage** = Nutzungsabo (Zugang/Miete, einmalige Erfüllung) | **product** = Produktabo
    (wiederkehrende Lieferung; **Auto-Fulfillment je Zyklus umgesetzt**: `invoice.paid` gibt den von
    `_spawn_recurrence` angelegten Entwurfs-Nachfolger frei und verbucht seinen Verkauf als bezahlt –
    idempotent, Zyklus 1/Retries treffen den bereits bezahlten Auftrag; `ensure_supply` deckt
    make-Artikel). Beide ohne Enddatum, aktiv kündbar (Customer Portal).
  - **Vereinfachung**: Steuerklasse (Stripe Tax übernimmt), Sichtbarkeit «Verborgen»/unlisted und
    DE/EN-Umschalter im Verkauf-Reiter **entfernt** (einsprachig, KI-Übersetzung später).
  - **Bedarf → Nachschub: EIN Unter-Auftrag-Mechanismus** (ADR 003, Migration `044`, ersetzt die
    frühere Make-Verkettung). Der Shop-Verkaufsauftrag ist IMMER ein **stock/FIFO**-Auftrag – er
    SELEKTIERT vorhandene, freigegebene Instanzen (erzeugt NIE selbst welche). Reicht der Bestand
    nicht, ist der betroffene Schritt **`blocked`** (abgeleitet aus dem Bestand, kein Auto-Trigger,
    `process.step_shortfalls`/`build_order_steps`); die Fehlmenge deckt ein **Nachschub-Unter-Auftrag**
    (`orders.parent_order_id` + `orders.reason='supply'`, `services/supply.ensure_supply`), der den
    **Artikel-Prozess** fährt (produziert/beschafft) und seine Stück bei Abschluss an den Eltern
    **pinnt** (`process._peg_supply_to_parent`) → der Schritt wird von selbst wieder aktiv.
    **Rekursiv** (mehrstufige Stückliste), **idempotent**, **zyklensicher**. Auslöser ist EINER:
    ERP-Knopf «Nachschub anlegen» (`POST /orders/{id}/supply`) bzw. Shop-Zahlung bei «auf Bestellung»
    rufen **dieselbe** `ensure_supply`. Freigabe = EIN Pfad (`services/orders.release_order`) für
    ERP/Shop/Nachschub; Unterdeckung ist KEIN Freigabe-Fehler mehr (Teil-Reservierung).
    `orders.subject_source` und `orders.fulfilled_by_order_id` sind **entfernt**;
    `process._release_dependent_sales` und `sales._create_production_order` ebenfalls.
  - **Eingebettete Kasse: Inline-Abschluss** (`redirect_on_completion='never'` + `onComplete`) – kein
    separates Erfolgs-Fenster, kein Abbruch-Hänger. **Adressen = Single Source of Truth «Profil»**:
    Liefer-/Rechnungsadresse werden auf den Stripe-Customer gespiegelt, KEINE Adress-Erfassung an der
    Kasse. **Bestellungen + Abos**: Kunde unter **Konto → «Bestellungen & Abos»** (+ Stripe-Portal),
    ERP am Benutzer-Datensatz als Karte **«Bestellungen»** (`GET /shop/orders`, `GET /erp/records/{id}/orders`).
  - **EIN Auftrag je Einkauf** (Mehrpositionen): die stock-Positionen eines Warenkorbs bilden **einen**
    Verkaufsauftrag (Instanz X + Y zusammen verkaufen & versenden) – je Position ein `sale`-Schritt +
    Beleg, EIN gemeinsamer `movement`-Schritt; `order.article_id=NULL` bei >1 Position; Subjekt = FIFO je
    Position (`_create_multiline_sale_order`/`_materialize_multiline`, `_finalize_subjects` ohne Artikel-
    Filter). make-Positionen (Produktion nötig) bleiben je ein eigener Auftrag (eigene Fertigungs-Timeline).
  - **Abo on-site kündigen** (`POST /shop/orders/{id}/cancel-subscription`): kündigt **zuerst bei Stripe**,
    spiegelt erst danach lokal (`provider.cancel_subscription`) – scheitert der Stripe-Call, bleibt das Abo
    aktiv (sauberer Fehler, kein stilles Weiterlaufen). Button im Konto-Reiter; Stripe-Portal bleibt für
    Zahlungsmittel.
- **ERP-Mehrpositionen-Aufträge + Direktverkauf (Herkunft/Zahlungsart)**: die Auftragsanlage bleibt
  **unverändert Einzel-Artikel** (Artikel + Menge, wie gewohnt per Auto-Save). Weitere Artikel lassen
  sich **jederzeit danach** ergänzen – auch nachdem der Auftrag schon gespeichert wurde, nicht nur bei
  der Anlage (`POST /orders/{id}/lines`, `services/order_lines.py`; wandelt beim ersten Aufruf den
  bisherigen Anker in Position 0 um, `order.article_id` wird `NULL`). `DELETE .../lines/{id}` entfernt
  eine Position (die letzte ist geschützt – ein Auftrag ohne jedes Subjekt wäre inkonsistent);
  `PATCH .../lines/{id}` fixiert Instanzen EINER Position statt FIFO (analog `instance_object_ids` am
  Einzel-Artikel-Auftrag). Ein Abo lässt sich – wie im Shop-Warenkorb – nicht mit weiteren Positionen
  mischen; der Check sitzt aber bewusst **am Hinzufügen des `sale`-Prozessschritts**
  (`sale.assert_sale_compatible`, aufgerufen aus `article_process.py: _create`), NICHT am Hinzufügen
  einer Position – eine weitere Position anzulegen, ohne dass überhaupt ein Verkauf beabsichtigt ist
  (z. B. nur Bewegen/Prüfen), darf nicht blockiert werden. `add_order_line` prüft nur die Rückrichtung
  (existiert bereits ein `sale`-Schritt, verhindert es eine nachträglich inkompatible Position). Ob ein
  Artikel „exklusiv" ein Abo ist, entscheidet `pricing.is_subscription_exclusive`/`resolve_one_time_price`
  über ALLE aktiven Preise (nicht nur die „primäre" Option) – ein Artikel mit Abo- UND Einmalkauf-Preis
  gilt nicht als exklusiv und lässt sich mischen (`sale.price_from_article` nutzt dann automatisch den
  Einmalkauf-Preis). `subject.subject_kind` erzwingt für einen Mehrpositionen-Auftrag **immer** `stock` (auch OHNE
  jeden Schritt) – schliesst die stille „0 Instanzen, keine Fehlermeldung"-Lücke, die entstünde, würde er
  fälschlich als `produce` behandelt.
  **Der Ablauf bleibt der GENERISCHE Step-Editor, unverändert** (`ProcessSteps`/`article_process.py`) –
  KEIN eigener Bypass, KEINE Sonderbehandlung: **jedes Prozessschrittmodul ist universell einsetzbar**,
  auch bei einem Mehrpositionen-Auftrag (keine Schritttyp-Whitelist mehr – Nutzer-Feedback: „Prozess-
  schrittmodule sollten, wenn auch immer möglich, universell einsetzbar sein"). `purchase` legt dafür
  wie `sale` je Position eine eigene Fachzeile an (`purchase.instantiate_for_order`, mehrere
  `PurchaseOrder` teilen sich den `step_id`; anders als beim Verkauf ist jede Bestellung eine EIGENE,
  unabhängig fortschreitende Beschaffung – `purchase.apply_update_bulk` verlangt bei >1 Position die
  betroffene `article_id`, statt eine gemeinsame Aktion zu erzwingen). `resource`/`inspection` skalieren
  jetzt über `order_lines.effective_quantity` (Summe der Positionsmengen) statt über das bei
  Mehrpositionen NULL-wertige `order.quantity`; eine Datenerfassung bleibt EINE Fachzeile über alle
  Instanzen des Auftrags hinweg (`inspections.article_id` jetzt nullable). `movement`/`scrap` waren
  bereits artikel-unabhängig und brauchten keine Änderung. Aber **genau EIN** `sale`-Schritt bedient
  **alle** Positionen (`sale.instantiate_for_order`
  legt bei Freigabe pro Position einen `Sale`-Beleg an, alle mit demselben `step_id`;
  `process.facts_for_step`/`_resolve_facts_multi` lösen die Liste auf) – **NIE mehrere sequentielle
  Sale-Schritte** («2-fache Prozessschrittmodule» war der zentrale Kritikpunkt der ersten, verworfenen
  Umsetzung). Die abgeleitete Bereitstellung zum Kunden funktioniert daher unverändert –
  EIN Sale-Schritt ⇒ EINE Sendung, kein Vervielfachungsrisiko.
  **Preis = Single Source of Truth vom Artikel** (`sale.price_from_article`, dieselbe Preis-Pipeline wie
  der Shop `services/pricing.py`): bei genau EINER Position bleibt der Betrag wie gewohnt frei editierbar
  (z. B. Artikel ohne hinterlegten Verkaufspreis); bei mehreren Positionen ist der Betrag **pro Position
  vom Artikel abgeleitet** und NICHT mehr frei eintippbar (`sale.apply_update_bulk` lehnt eine manuelle
  Betrags-Änderung dann ab) – kein einzelner Betrag mehr über unterschiedliche Artikel/Preismodelle
  gestülpt. Eine kombinierte Aktion (Bestätigen/Rechnung/Zahlung, EIN Kunde) wirkt auf **alle** Positionen
  gleichzeitig. Kernstellen generalisiert, Einzel-Artikel-Pfad unverändert: `subject._allocate_stock_for`
  (Kern aus `_allocate_stock_subject`), `process._subject_shortfalls` (dict über alle Positionen),
  `process._peg_supply_to_parent` (Nachschub-Pegging erkennt Mehrpositionen-Aufträge als Subjekt),
  `deactivation._order_article_filter` (Artikel-Deaktivierung findet Aufträge auch über `order_lines`).
  Frontend: die gewohnten 3 Ziel-Karten «Was möchten Sie tun?» bleiben unverändert – bei mehreren
  Positionen ist **«Herstellen» ausgegraut** (kein EINER Artikel-Prozess, den ein Mehrpositionen-Auftrag
  fahren könnte), nur FIFO/«Instanz wählen» bleiben (`order-detail.tsx: canProduce`); «Instanz wählen»
  zeigt dann **einen Picker je Position** (`PinLine`/`pinLines`). Eine dezente «+ Position hinzufügen»-
  Zeile im Bedarf-Feld ist **jederzeit im Entwurf** aktiv, nicht nur bei der Anlage
  (`AddPositionRow`/`api.addOrderLine`). `SalePanel` rendert die volle Belegliste (`OrderStepInfo.sales`)
  statt eines einzelnen Verkaufs. Zusätzlich `sales.mode` (shop/direct) + `payment_method`/
  `payment_reference` am Verkauf: ein personal-erfasster Verkauf braucht **kein Kartenterminal** –
  Rechnung ist der übliche B2B-Weg (wählbar: invoice/cash/twint/other; `payment_method='terminal'` für
  Stripe Terminal ist im Datenmodell vorgemerkt, aber **noch nicht** wählbar). **Regressions-Fix im
  gleichen Zug:** `PATCH /orders/{id}/sale` nahm bisher blind die erste Sale-Zeile eines Auftrags
  (`.first()`) – bei mehreren Verkaufs-Belegen hätte jede Aktualisierung dieselbe (falsche) Position
  getroffen; jetzt wie movement/resource/inspection über `resolve_exec_step`/`facts_for_step` (`step_id`)
  aufgelöst.
- **Nachbesserungen Mehrpositionen/Abo (Praxistest-Fixes)**:
  - **Freigabe-Ausnahme für Abweichungen**: eine Abweichung (Unter-Auftrag, `reason='deviation'`) hat ihr
    Subjekt bereits über fixierte Instanzen (`Instance.subject_of_order_id`), OHNE eigene `order_lines` –
    erbt bei einem Mehrpositionen-Eltern aber dessen `article_id=NULL`. Die Freigabe-Prüfung verlangte
    fälschlich trotzdem Artikel+Menge (`orders.py`: `wants_release`-Block prüft jetzt zusätzlich
    `subject.is_deviation(order)` und lässt Abweichungen ohne `order_lines` durch); Frontend-Pendant
    `order-detail.tsx: hasDemand` berücksichtigt `isSubOrder` ebenso.
  - **Alle Prozessschritt-Module sind jetzt universell einsetzbar** (Task 3): die künstliche
    «nur sale+movement»-Sperre in `article_process.py: _create` ist entfernt. `purchase` legt bei
    Mehrpositionen **eine unabhängige Bestellung je Position** an, alle mit gemeinsamem `step_id`
    (`purchase.instantiate_for_order`); jede Position schreitet **eigenständig** fort (eigener
    Lieferant/Zeitplan) – `purchase.apply_update_bulk` verlangt ab der zweiten Position die
    betroffene `article_id` zur Disambiguierung (auch für Status, keine erzwungene Sammelaktion wie
    beim Verkauf). `resource`/`inspection` nutzen jetzt `order_lines.effective_quantity` (Summe der
    Positionsmengen) statt des bei Mehrpositionen NULL-wertigen `order.quantity`
    (`inspections.article_id` dafür nullable, Migration `047`); eine Datenerfassung bleibt EINE
    Fachzeile über alle Instanzen. Frontend: `PurchaseStepPanel` rendert eine Zeile je `OrderPurchase`
    (`OrderStepInfo.purchases`), mit Artikel-Header sobald >1 Position.
  - **Abo-Mischungs-Prüfung verschoben + präzisiert** (Task 2): die Prüfung «Abo lässt sich nicht mit
    weiteren Positionen kombinieren» blockierte bisher schon beim reinen Hinzufügen einer Position
    (`add_order_line`), bevor überhaupt klar war, ob der Auftrag einen Verkauf durchläuft, UND erkannte
    Artikel mit **zusätzlichem** Einmalpreis fälschlich als Abo-exklusiv. Neu: `pricing.
    is_subscription_exclusive`/`resolve_one_time_price` prüfen korrekt über ALLE Preise eines Artikels
    (exklusiv nur, wenn GAR kein Einmalpreis existiert); die Prüfung (`sale.assert_sale_compatible`)
    greift jetzt am **`sale`-Schritt selbst** – sowohl beim Hinzufügen des `sale`-Moduls zu einem
    Mehrpositionen-Auftrag (`article_process.py: _create`) als auch umgekehrt beim Hinzufügen einer
    weiteren Position, wenn bereits ein `sale`-Schritt existiert (`orders.py: add_order_line`) – mit
    konkreter Fehlermeldung, die den betroffenen Artikel nennt.
  - **Abo-Mindestlaufzeit / Kündigungs-Cooldown** (Task 1, State-of-the-Art analog SaaS-Branche): ein
    **Produktabo** (`sub_type='product'`, wiederkehrende Lieferung) ist erst nach **einem vollen
    Abrechnungszyklus** ab Freigabe kündbar (`sales.earliest_cancellation_date`,
    `PRODUCT_MINIMUM_TERM_CYCLES=1`); ein **Nutzungsabo** (`sub_type='usage'`) hat keine Mindestlaufzeit.
    Personal/Admin kann jederzeit kündigen (Bypass). `routers/shop.py: cancel_subscription` weist eine
    verfrühte Kündigung mit 403 + Datum ab; `CustomerOrder.cancellable_from` liefert das Datum an den
    Kunden, `orders-list.tsx` deaktiviert den Kündigen-Knopf bis dahin mit Beschriftung «Kündbar ab …».
  - **UX: Hover-Begründung bei gesperrten Aktionen**: der Auftrag-Freigabe-Knopf zeigt per `title`-
    Tooltip den konkreten Grund, warum er (noch) ausgegraut ist, statt stillschweigend deaktiviert zu
    bleiben.
- **Retoure/Erstattung = ganz normaler Auftrag über das VEREINHEITLICHTE `sale`-Modul** (Migrationen
  `048`+`049`; der frühere separate `refund`-Schritt ist wieder entfernt): Eine Retoure wird angelegt **wie
  jeder andere Auftrag** – Artikel wählen, dann bei **«Instanz wählen»** statt Lager-Instanzen die
  **verkauften** Instanzen wählen (KEINE eigene Ziel-Karte mehr; `routers/orders._set_chosen_instances` +
  `_validate_pins` akzeptieren `sold`). Das Backend erkennt verkaufte Instanzen und macht den Auftrag zur
  Retoure: `orders.reason='return'` (festes Subjekt via `Instance.subject_of_order_id`, wie eine Abweichung –
  kein FIFO/keine Reservierung, **ohne** Eltern-Pause) + `parent_order_id` = der **Original-Verkauf**
  (`services/refund.original_sale_order`, Grundlage für Betrag/MWST/Kunde/Stripe-PaymentIntent). Lager- und
  verkaufte Instanzen lassen sich nicht mischen (gegensätzliche Geldrichtungen).
  - **EIN `sale`-Schritt, ZWEI Modi – aus dem Subjekt ABGELEITET** (kein eigener Schritttyp): normaler
    Auftrag → **Verkauf** (`kind='sale'`, Geld rein, Bestands-Abgang) | Retoure (Subjekt verkauft) →
    **Gutschrift/Erstattung** (`kind='credit'`, Geld raus, `sale.instantiate_for_order` über `is_return`).
    Betrag/Kunde aus dem Original abgeleitet (`_prefill_credit`), bei EINER Position **abweichend erfassbar**
    (Teil-Erstattung/**Kulanz**). Ablauf Bestätigen→Ausstellen→**Erstatten**: die «Zahlung» (`paid`) löst den
    **Stripe-Refund** aus, wenn der Verkauf via Stripe lief (`_issue_refund`/`provider.refund`, voll/anteilig,
    idempotent), sonst dokumentierte manuelle Gutschrift; Nummer `GS-{id}`, Event `sale.refunded`. Dasselbe
    Panel (`sale-panel.tsx`) rendert Verkauf ODER Gutschrift (Dual-Mode über `first.kind`); EIN Endpoint
    `PATCH /orders/{id}/sale`.
  - **Label-Wechsel dann, WANN es wirklich passiert (step-basiert, idempotent):**
    - **Verkauf bezahlt → «verkauft»**: `process.sell_order_subjects` (in_stock→sold, mengengenau) wird bei
      **sale-`paid`** aufgerufen (`sale._apply_transition`/`finalize_paid`) – nicht erst am Auftragsende;
      make-to-order zieht beim Abschluss nach. Die **Begleit-Bewegungen** (u. a. der Versand zum
      Kunden) sind von der Subjekt-Fehlmengen-Prüfung **ausgenommen** (`step_shortfalls`, `not
      is_companion(step)`), sonst würde der Versand blockiert, sobald die Ware «verkauft» (aus dem freien
      Bestand «weg») ist.
    - **Rückgabe-Bewegung durch → «freigegeben»**: `process.return_subjects_to_stock` (sold→in_stock, Menge
      auf ≥1) wird bei der **Bewegung** weg vom Kunden aufgerufen (`movement.record_movement`), nicht
      erst am Auftragsende. Movement/Scrap nehmen bei einer Retoure (bzw. Versand: Ziel=Person) auch
      **verkaufte** Instanzen auf. **Kulanz** (Ware NICHT bewegt) → bleibt `sold`, nur Geld zurück.
    - `_finalize_subjects` beim Abschluss ist nur noch das **Sicherheitsnetz** (ruft beide Helfer idempotent).
  - Geld (`sale`/Gutschrift) und Ware (`movement`) sind **frei kombinierbar** – Retoure mit Rücknahme,
    reine Kulanz-Gutschrift (Reklamation ohne Rückgabe), defekt→verschrotten+gutschreiben. **Löst nebenbei
    das «Menge reduzieren»-TODO** (Teil-Erstattung statt stiller Mengen-Kürzung). Original-Verkauf zeigt die
    Retoure als Unter-Auftrag (`OrderResponse.returns`). *Bewusst NICHT gebaut: Store-Credit/Guthaben.*
  - **Kunden-Retoure aus «Meine Bestellungen» (Online-Shop-Logik, `services/customer_returns.py`)**: der
    Kunde stösst zu einer **abgeschlossenen** Bestellung im **Rückgabefenster** (`RETURN_WINDOW_DAYS=30`)
    eine Rückgabe an (`POST /shop/orders/{id}/return`, optionaler Grund). Das legt – wie eine ERP-Retoure –
    einen Retoure-Unter-Auftrag an (verkaufte Instanzen als Subjekt, `parent`=Original-Verkauf) und gleich
    den üblichen **Ablauf** (Bewegung = Wareneingang + `sale` im Kredit-Modus = Gutschrift); das Personal
    verarbeitet ihn im ERP (Wareneingang buchen → Gutschrift bestätigen → Stripe-Refund). `CustomerOrder`
    trägt `returnable`/`return_requested`/`return_deadline`; `orders-list.tsx` zeigt «Retoure anfragen»
    (mit Frist) bzw. «Retoure angefragt». *Bewusst NICHT gebaut: Rücksende-Label/RMA-Tracking, Teil-
    Mengen-Auswahl durch den Kunden (Personal passt die Menge im ERP an).*
- **Versand zum Kunden geht IMMER an den Kunden** (Fix): die zu einem `sale`-Schritt gehörende
  Bewegung (Bereitstellung bzw. Alt-Bestand `mode='customer'`) hat als Ziel **fix den Kunden des Verkaufs** (`sale.customer_for_order`).
  Serverseitig erzwungen (`movement.record_movement` überschreibt die Ziel-Eingaben) UND im Embed als festes
  Ziel gezeigt (`orders._movement_embed`) – der Lagerist kann kein falsches Ziel wählen. Weil das Ziel fest
  ist, lädt das Movement-Panel **keine** Personen-/Instanz-Listen mehr (`movement-panel.tsx:
  hasFixedTarget` → spürbar schneller, gerade direkt nach dem Verkauf). **Das Ziel ist fest, der Schritt
  ist es nicht:** wer nicht versendet (Abholung, Streckengeschäft), löscht die Bewegung – sie ist seit
  Juli 2026 ein normaler Schritt (siehe «Zwangs-Prozessschrittmodule sind aufgelöst»).
- **KI-Layer (ADR 004, `docs/adr/004-ki-layer.md` – VOR KI-Arbeit lesen)**: vier dünne Schichten in
  `backend/app/services/ai/`. (1) **Gateway** (`gateway.py`): provider-agnostisch – **Vertex-EU Default**
  (`AI_PROVIDER=vertex` + `VERTEX_PROJECT_ID`, ADC-Auth), Anthropic-direkt swap-bar, Gemini-Bild
  («Nano Banana») via Vertex-REST; ohne Konfiguration **inaktiv statt kaputt** (503, ERP läuft normal).
  Modelle/Prompts versioniert in `registry.py` (`PROMPT_VERSION`), NIE in der Fachlogik. (2) **KI-Identität**
  (`identity.py`): System-`UserProfile` `role='ai'` mit Objektnummer, beim Start geseedet; Audit/Events
  zeigen «User KI»; Admin kann sie weder umrollen noch deaktivieren. **Delegation** (`principal.py`):
  Attribution = KI, **effektive Rechte = delegierender Mensch**. (3) **Rechte-gescopte Tools** (`tools.py`):
  rollen-gefilterte Whitelist (Kunde: shop/my_orders; Lieferant: nur eigene Aufträge; Staff: alles; autonom:
  read-only) – jedes Tool wrappt die BESTEHENDE Authz (`visible_orders`, `can_view`, `in_stock_clauses`);
  **Scoping = Authz, nicht Prompt**. **Zielbild: permission-scoped Vollparität** – die KI soll grundsätzlich
  ALLES einsehen/tun können, was der jeweilige Nutzer auch darf (Lesen breit, kritisches Schreiben hinter
  Bestätigung). Werkzeug-Set wächst entsprechend (Staff aktuell u. a. Artikel/Auftrag/Instanz/Benutzer/
  Standort/Firmen-Info/Audit-Log lesen, Artikel/Auftrag-Entwürfe + Prozessschritte + Instanz-Fixierung
  schreiben, `resolve_object` für jede Objektnummer). Kritisches (Freigabe/Geld/Löschen/Rolle) bleibt Gate. **Autonomie-Policy**: Entwürfe (Artikel/Auftrag, draft) legt die KI
  direkt an (reversibel); **Kritisches** (Auftrag freigeben) nur als `AiAction`-Vorschlag (Migration `054`)
  → menschliche Bestätigung im Chat → autorisierter Pfad (`actions.py`, idempotent). (4) **Endpunkte**
  `routers/ai.py`: `/api/v1/ai/{config,chat,write,image-edit,actions/{id}/confirm|reject}`; Events `ai.*`
  (Modell/Prompt-Version/Token je Lauf). **Frontend**: schwebendes Chat-Widget `components/ai/assistant.tsx`
  (ERP-, Konto-, Shop-Layout; Vorschlagskarten mit Bestätigen/Ablehnen), **KI-Schreibhilfe** im
  Dokument-Panel (`ai/write-assist.tsx`), **Shop-Bild-Bearbeitung** im Verkauf-Panel (`ai/image-assist.tsx`,
  Ergebnis = neues Attachment, Original bleibt). Untrusted-Text (Dokumente/Fremdtexte) ist DATEN, nie
  Instruktion. *Bewusst NICHT gebaut: autonome Freigaben/Geld/E-Mail, MCP-Server nach aussen, RAG/Vektor.*
  - **KI-Optimierungen (Kosten/Latenz/UX)**: (1) **Dynamische Modellwahl** (`registry.route`): einfache
    Lese-/Zählfragen laufen auf dem **leichten** Modell (`ai_chat_model_light`, Haiku) OHNE Reasoning
    (günstig/schnell), nur mehrstufige/schreibende Aufgaben (anlegen/bestellen/freigeben/Link) nutzen das
    **starke** Modell (`ai_chat_model`, Opus) mit adaptivem Reasoning – reine Heuristik (kein Vorab-Call),
    im Zweifel aufwärts. (2) **Knappe Antworten** (Prompt) + **Markdown-Rendering** im Chat (react-markdown +
    remark-gfm, Design-Tokens; **fett**/Listen/Tabellen). (3) **KI überall**: das Widget hängt im
    `(public)/layout` (Website+Shop), ERP-, Konto-Layout – rechte-gescopt, rendert nur für angemeldete
    Nutzer. (4) **Live-Refresh**: verändert die KI ERP-Daten (`AiChatResponse.changed=true` via
    `tools.is_write_tool`), feuert das Widget `inexxio:data-changed` → der Feed lädt sofort nach. Der
    Verlauf lädt beim Mounten (überlebt Seiten-Refresh); der Chat scrollt beim Öffnen ans Ende.
    (5) **Navigation/Hinführen** (`open_page`-Tool → `AiChatResponse.navigate`): die KI kann den Nutzer
    an die passende Stelle führen (Shop-Produkt/Warenkorb/«Meine Bestellungen»/ERP-Datensatz via
    `/erp?open=<Objektnr>`) – das Widget rendert dazu einen Knopf. Ein Kaufwunsch «leg es in den
    Warenkorb» wird NICHT abgewimmelt, sondern zum Produkt geführt. (6) **Rückfragen erlaubt**: bei
    echter Unklarheit fragt die KI kurz nach statt zu raten. (7) **Schreibhilfe** liefert ein
    vollständiges Dokument (mehrere ausformulierte Abschnitte), nie nur eine Überschrift.
- **Beleg-/Dokument-Modul (hochgeladene Fremd-Dokumente, KI-Aufnahme, Reiter «Dokumente»)**: Für
  unvermeidbare Fremd-Dokumente (Rechnungen, Lieferscheine, Anleitungen, Datenblätter, Zertifikate,
  Verträge), die MIT Lieferungen ins Unternehmen kommen – NICHT von Inexxio verfasst. **Abgrenzung:**
  das Prozessschritt-`Document` (`models/document.py`) sind Inexxio-EIGENE, verfasste Textdokumente
  (Nummer = Instanz); das neue `DocumentFile` (`models/document_file.py`) ist eine **hochgeladene
  Datei** mit **eigener Objektnummer** (Typ `document`). **Ablauf (ADR-004-Muster «Vorschlagen ≠
  Ausführen»):** Datei hochladen/fotografieren (`POST /ai/documents/analyze`, multipart) → die KI liest
  das PDF/Bild direkt (Vision/Document-Block, kein separates OCR; PDF-Textlayer wird zusätzlich per
  `pypdf` gratis extrahiert und als `extracted_text` gespeichert = spätere RAG-Basis) und erfasst über
  ein **erzwungenes Tool** `extract_document` strukturiert **Name, Typ, Zusammenfassung, Bezugsgrössen**
  (`services/ai/documents.py`). Aus den Bezugsgrössen matcht der Server **passende ERP-Objekte**
  (`match_candidates`: Artikel-Fuzzy via `article_names._similarity`, Lieferant/Firma, im Text genannte
  Objektnummern, plus das Kontext-Objekt) und legt einen **`AiAction`-Vorschlag** (`action_type=
  'link_document'`) an – NICHTS ist damit gespeichert. Der Mensch prüft/ändert **Name + Objektzuordnung**
  und **bestätigt** (`POST /ai/documents/{id}/confirm`) → erst dann materialisiert `documents.materialize`
  das `DocumentFile` + die **n:m-Verknüpfungen** (`document_links`). **Ein Dokument entsteht NIE
  objektlos** (Freigabe-Gate: min. 1 Verknüpfung; manuelle Objektnummer-Eingabe möglich). Ablehnen
  (`reject`) entfernt die Datei aus der Ablage. **Zuordnung ist n:m** (eine Rechnung betrifft Lieferant
  + mehrere Artikel + Auftrag). **Dublette** über `sha256` erkannt. **Speicher:** `services/storage.py` –
  **GCS**, wenn `settings.gcs_bucket` gesetzt (Cloud-Run-ADC, kein Key), sonst DB-Fallback
  (`document_blobs`); PDFs werden **byte-genau** abgelegt (kein JPEG-Re-Encode wie bei `attachments`).
  **Auslieferung authentifiziert** (`GET /erp/document-files/{id}/download`, `require_employee` – Rechnungen
  sind sensibel, NICHT der öffentliche Foto-Token-Weg). **Reiter «Dokumente» je ERP-Objekt**
  (`GET /erp/objects/{id}/documents`, generisch über die Objektnummer): vereint hochgeladene Dateien
  (via Links) UND die im Schritt «Dokument» erzeugten Dokumente. Frontend: `components/erp/object-
  documents.tsx` (`ObjectDocuments` + Upload-/Analyse-/Bestätigungs-Dialog, Kamera-Aufnahme), eingebunden
  in ALLE Detailansichten (Artikel/Auftrag/Instanz/Benutzer/Unternehmen). **RAG (semantische
  Suche über den `extracted_text`) ist bewusst im Backlog** – der weiche Start deckt «Objekt bekannt →
  Text am Objekt» ab; korpusweite Suche kommt später über das geplante Typesense. Ohne konfigurierte KI
  läuft das Modul weiter (Titel = Dateiname, manuelle Zuordnung). Migration `059`.

> **HINWEIS (aktuelles Kernmodell):** **Auftrag → Prozess → Instanz.** Der **Artikel** trägt seine
> **Spezifikation** (vormals «Stammdaten») + **einen** Prozess (Schritte inline, kein Prozess-Objekt, keine
> Objektnummer, keine n:m-Verknüpfung). **Freigabe auf Artikel-Ebene** friert Spezifikation + Prozess.
> Ein **Auftrag** ist der Trigger in zwei **Modi**: **make** (Artikel + Menge → fährt den Artikel-Prozess,
> ERZEUGT Instanzen) oder **custom** (ausgewählte vorhandene Instanzen + individueller Prozess am Auftrag).
> **Instanzschritte verarbeiten nur Instanzen**; Artikel dienen v. a. als FIFO-Bezug. Schritttypen: purchase,
> inspection, movement, **resource** (Verbrauch + Betriebsmittel, Modus je Zeile), **scrap** (Verschrotten),
> sale. `quality`+`disposition` als zwei Instanz-Achsen; `event_types`-Registry deklariert die Bestands-
> Polarität. **Unter-Auftrag** (`parent_order_id` + `reason`) – EIN Mechanismus, DREI Gründe:
> **Abweichung** (`reason='deviation'`: Abbruch-Folgeauftrag / Fehler / Reklamation / Nacharbeit,
> pausiert den Eltern; `Claim`-Typ entfernt), **Nachschub** (`reason='supply'`: deckt einen nicht
> vorrätigen Bedarf, blockiert nur den Schritt) und **Retoure/Erstattung** (`reason='return'`, Migrationen
> `048`+`049`: als **ganz normaler Auftrag** angelegt – bei «Instanz wählen» **verkaufte** Instanzen wählen
> → Backend leitet Retoure + `parent`=Original-Verkauf ab; Geld über das **vereinheitlichte `sale`-Modul im
> Kredit-Modus** (`kind='credit'` aus dem Subjekt abgeleitet + Stripe-Refund), Ware über die **Bewegung**.
> Festes Subjekt wie eine Abweichung, aber OHNE Eltern-Pause. Kein separater `refund`-Schritt mehr).
> **Label-Wechsel step-basiert** (wann es wirklich passiert): Verkauf bezahlt → sold; Rückgabe-Bewegung an
> weg vom Kunden → in_stock; Kulanz (nicht bewegt) → bleibt sold. **Bedarf→Nachschub (ADR 003):** ein ungedeckter Bedarf
> macht den Schritt `blocked` (abgeleitet); `supply.ensure_supply` legt rekursiv/idempotent/zyklensicher
> Nachschub-Unteraufträge an (Artikel-Prozess), die bei Abschluss an den Eltern **gepinnt** werden.
> **Verkauf/Shop** (MVP) lebt am Artikel (Profil + `article_prices` + Audience); **nur Basispreis CHF**
> gepflegt, Rest abgeleitet (gestaffelte Pipeline, gepinnte Fremdwährung). Zwei Achsen: Preismodell
> (Einmalkauf/Abo) + Verfügbarkeit (`sales_fulfillment` = 1-Bit-Backorder-Policy: make=Nachschub |
> stock=nur ab Lager). Kauf = stock/FIFO-Auftrag mit `sale`+`movement`-Schritt + Preis-Snapshot;
> Fehlmenge → Nachschub (kein `subject_source`/`fulfilled_by_order_id` mehr). **Warenkorb**
> (mehrere Positionen ⇒ ein Checkout; Auftrag entsteht aufgeschoben erst bei Zahlung via `CheckoutIntent`).
> **Zahlung = Stripe** (eingebettete Kasse `ui_mode='embedded'` + Adaptive Pricing + Stripe Tax,
> Webhook-gespiegelt; `manual` als Fallback ohne Keys). Zwei Abo-Typen (`sub_type` usage/product).
> **Inaktive Artikel sind endgültig** (kein Reaktivieren). Setup/Keys: `docs/stripe-setup.md`.
> E-Mail (Gmail API) ist **noch nicht** umgesetzt.

- **Öffentliche Rechtsdokumente (D, Zeiger auf einen Artikel)**: AGB/Datenschutz kommen aus dem
  **Dokument-Modul** statt aus hartkodiertem Seitentext. Am Unternehmen wird je Typ die **Objektnummer
  eines Artikels** hinterlegt (`company_settings.legal_documents` JSONB, `{"agb": <Artikel-Objektnr>,
  "datenschutz": …}`); die Website zieht dessen **erste Instanz mit ausgestelltem Dokument-Beleg**
  (`Document.done=True`) – massgeblich ist die **Ausstellung**, NICHT der Lagerstatus (`in_stock`) der
  Instanz; nur verschrottete Instanzen werden übersprungen. **Neue Fassung = neuer Artikel + «Ersetzen»**
  (`replaced_by_id`): die Auflösung folgt der Ersetzungs-Kette automatisch auf die **neueste Fassung mit
  ausgestelltem Beleg** (wie der Shop kanonisiert) – der Zeiger muss nicht angefasst werden; ein noch
  belegloser Nachfolger (Entwurf) wird übersprungen, die alte Fassung bleibt gültig, bis die neue
  tatsächlich einen ausgestellten Beleg hat. Alte Instanzen bleiben über ihre Objektnummer archiviert
  (Nachweis im Streitfall). Auflösung `services/legal.resolve` (Artikel→`replaced_by_id`-Kette→erste
  Instanz mit ausgestelltem `instance_document_embeds`); Public-Endpoint `GET /api/v1/legal/{kind}`
  (404 → Website-Fallback auf eingebauten Text). **Voraussetzung:** das Dokument muss in einem Auftrag
  auf den Artikel **ausgestellt** worden sein (Prozessschritt «Dokument» → «Ausstellen»).
  Frontend: `/agb` + `/datenschutz` rendern `<LegalDocument kind=… fallback={…}>` (DocumentView inkl.
  Briefkopf), Admin → Systemkonfiguration → «Rechtstexte» (Artikelnummer je Typ). Erfüllt die
  AGB-Akzeptanz-Version geschenkt.
- **Dokument-Freigabe & Pflichten (Unterschriften/Anerkennungen, DocuSign-Prinzip)**: Ein Dokument ist
  eine **ganz normale Instanz** (unveränderte Statuse `quality`/`disposition`); der Prozessschritt
  «Dokument» ist ein **Sub-Prozess** (wie `purchase`): **Entwurf → Ausgestellt (`documents.issued`, Inhalt
  eingefroren, unveränderliche Basis) → Freigaben laufen → Vollständig freigegeben (`documents.done`) →
  Instanz freigegeben, Auftrag abgeschlossen**. `done` wird NICHT im `_fact_status` erraten, sondern vom
  Service gesetzt, sobald alle Parteien signiert haben (`document._maybe_complete`; ohne Parteien fällt es
  bei «Ausstellen» zusammen → rückwärtskompatibel). **ZWEI Partei-Typen, am Schritt deklariert**
  (`article_process_steps`, Migration 066): (1) **Freigabe-Parteien** – endliche, geordnete Liste
  (`doc_signers` = [{signer_object_id, action `confirm`|`sign`}], `sign_sequential`), materialisiert bei
  «Ausstellen» als **append-only Layer** `document_signoffs` (EINE Tabelle für bestätigen OHNE Bild +
  unterschreiben MIT Bild). Erst wenn ALLE signiert haben, ist das Dokument freigegeben → **gated den
  Auftragsabschluss** (terminiert immer, weil endlich). Nur die **benannte Person** (Objektnummer-Abgleich)
  handelt; **sequenziell** = nur die kleinste offene `order_index` ist dran. Aktionen: sign/confirm/reject
  (mit Grund)/withdraw (eigene Unterschrift zurückziehen); Personal kann die **Ausstellung zurücknehmen**
  (`document.withdraw_issuance`, solange nicht `done`) → Inhalt wieder editierbar. (2) **Anerkennungs-
  Publikum** – offen (`doc_audience` = all|roles|persons + `doc_audience_roles`/`_person_ids`), ein
  **rollierendes, aktions-getriggertes Gate auf dem BEREITS freigegebenen Dokument** (`services/consent.
  _audience_obligations` → `document_acknowledgements`, kind='document', Version = Instanz-Objektnummer) –
  **blockiert den Auftrag NIE**, erscheint aber im **Consent-Gate-Modal** (jede Rolle). Kanonisch: ein
  Dokument, dessen Artikel **ersetzt** wurde, ist superseded → der Nachfolger fordert die neue Anerkennung
  (Q «neue Version = sofort neu bestätigen»). **Aufteilung Schritt↔Auftrag:** der Schritt deklariert die
  STRUKTUR (Parteien-Slots, Reihenfolge, Publikum, `doc_visibility`); der Auftrag füllt INHALT + sammelt
  die konkreten Unterschriften. **Lieferanten-Fähigkeits-Gate** (Offerte erst nach Bestätigung): über ein
  `supplier_terms`-Dokument mit `doc_audience=roles=[supplier]` – das Consent-Gate blockiert den Lieferanten,
  bis er anerkannt hat (kein Sonder-Check im Beschaffungs-Pfad). **Surfaces:** Prozess-Editor
  (`process-steps.tsx: DocConfigEditor` – Parteien per SearchSelect + Drag&Drop + `confirm`/`sign` je Zeile,
  sequenziell-Toggle, Publikum, Sichtbarkeit); Auftrags-Panel (`document-panel.tsx` – Ausstellen →
  Parteien-Liste mit Inline-Signatur `SignaturePad`/Bestätigen/Ablehnen + Zurücknehmen); **«Meine Dokumente»**
  (`account/sections/documents-section.tsx` – externe Parteien signieren im Konto, `GET/POST /consent/
  {my-documents,signoffs/{id}}`); der **Freigabe-Layer wird auf das Dokument gerendert** (Web `DocumentView`
  + PDF `document_render._signoffs_html`, Unterschrift-Bild als data-URI). Endpunkte am Auftrag
  (`POST …/document/signoff/{id}`, `…/document/withdraw`). **Sichtbarkeit ist als Lese-Zugriffsfilter
  erzwungen** (`orders._doc_content_visible`): Nicht-Personal sieht den Dokument-Inhalt im Auftrags-Embed
  nur nach `doc_visibility` (public → jeder | parties → Parteien/Publikum | internal → nur Personal);
  eine benannte Partei liest IMMER (man kann nicht unterschreiben, was man nicht sieht).
  **Parteien-Substitution am laufenden Auftrag** (`POST …/document/substitute-signer`, Personal,
  auditiert): das offene (pending/abgelehnte) Signoff wandert auf eine neue aktive Person – Position/
  Aktion bleiben, geleistete Unterschriften nie; fällt eine Partei aus, braucht der Auftrag keinen
  Abbruch mehr.
  - **Ausstehende Pflicht-Unterschriften senken die Profil-Vollständigkeit**: `useProfileCompletion`
    nimmt jetzt die Zahl **offener** Dokument-Pflichten (ausstehende Unterschriften/Bestätigungen +
    Anerkennungen, aus `/consent/my-documents` + `/consent/pending`) und zählt sie wie fehlende
    Pflichtfelder → das Profil zeigt **nicht «vollständig»**, solange etwas aussteht (Badge am Reiter
    «Meine Dokumente»). `account-shell` lädt die Zahl und aktualisiert live über das Fenster-Event
    `inexxio:documents-changed` (von `documents-section` nach jeder Aktion gefeuert).
  - **Dokument-Vorschau ist auf A4 begrenzt & überlaufsicher**: `DocumentView` rendert ein Blatt mit
    fester A4-Breite (`A4_WIDTH=794px`, zentriert, WYSIWYG mit dem PDF); Tabellen nutzen
    `table-layout:fixed` + Wortumbruch (Web **und** PDF `document_render`), lange Wörter/URLs/Code
    brechen um – **nichts kann breiter als der Satzspiegel werden** (kein horizontaler Überlauf/
    Beschnitt, auch bei KI-generierten breiten Tabellen).
- **Sicherheitsbestand + Auto-Nachbestellung (E, «Nicht die Zeit soll bestellen, sondern der Bestand»)**:
  **Sicherheitsbestand** = `articles.safety_stock`; fällt der **freie** Bestand darunter, legt
  `services/replenishment.check_article` einen eigenständigen Nachschub-Auftrag (`orders.reason=
  'replenishment'`, ohne Eltern) an und gibt ihn frei – füllt **auf den Sicherheitsbestand** auf
  (MOQ-gerundet), fährt den Artikel-Prozess (produzieren/beschaffen). *Der frühere separate
  «Zielbestand» (`reorder_target`) ist mit Migration `089` entfallen (Notiz #221): zwei Zahlen
  für dieselbe Frage, von denen die zweite fast immer leer blieb.* Reuse von
  `orders.release_order` (wie ADR-003-Nachschub, nur ohne Pegging), idempotent (ein offener Nachschub je
  Artikel). **Auslöser** reaktiv (nach Bestandsabgang – `scrap.record_scrap` ruft `check_article`) +
  periodisch über `POST /api/v1/erp/maintenance/sweep` (`replenishment.evaluate_all`, Personal-Knopf
  «Lagerwartung», künftig Cloud Scheduler). Der Sicherheitsbestand ist **auch am
  freigegebenen Artikel tunebar** (operative Steuergrössen, nicht eingefrorene Spezifikation).
  *Die frühere MHD-/Haltbarkeits-Achse (`instances.expires_at`, `articles.shelf_life_days`,
  `services/expiry.py`) ist bewusst entfernt (Migration 061) – eine Instanz „läuft" nicht mehr ab.*
- **Wiederkehrende Aufträge klonen Prozess + Subjekt (Wartung)**: `process._spawn_recurrence` zieht beim
  Abschluss den nächsten Auftrag (Entwurf) nach und erbt jetzt zusätzlich (a) die **auftrags-eigenen
  Prozessschritte** (via `deactivation._copy_steps`, `src_order_id`→`dst_order_id`) und (b) **dieselben
  gewählten Subjekt-Instanzen** (z. B. die zu wartende Maschine – in `recompute_completion` vor dem Lösen
  der Bindung erfasst, auf den Kind-Auftrag `subject_of_order_id` gepinnt, bei dessen Freigabe erneut
  reserviert). So läuft eine **wiederkehrende Wartung mit Prozess-im-Auftrag** vollständig weiter statt
  leer; ein reiner Erzeugungs-/Abo-Auftrag verhält sich unverändert (kein eigener Schritt → Artikel-Prozess).
- **Passkeys / passwortlose Anmeldung (WebAuthn/FIDO2, `docs/passkeys.md`)**: Firebase hat keinen nativen
  Passkey-Provider – die WebAuthn-Zeremonie läuft im Backend (`services/passkey.py`, `py_webauthn`), bei
  Erfolg wird ein Firebase **Custom Token** ausgestellt (`signInWithCustomToken`) → ab da normale Firebase-
  Session, restlicher Auth-Fluss unverändert. Modelle `webauthn_credentials`/`webauthn_challenges` (Migration
  `065`), Endpunkte unter `/api/v1/auth/passkeys` (register/login options+verify, list, delete). **RP-ID +
  Origin werden pro Request aus dem `Origin`-Header abgeleitet** und gegen `cors_origins` geprüft (multi-
  domain: localhost/dev/prod ohne feste Verdrahtung); Challenges sind DB-basiert (Cloud-Run-sicher, einmalig,
  5 min). Frontend: `lib/passkey.ts` + `@simplewebauthn/browser`, Login-Button «Mit Passkey anmelden»,
  Konto → Sicherheit «Passkeys» (hinzufügen/entfernen). **Deployment-Hinweis:** der Cloud-Run-SA
  braucht `roles/iam.serviceAccountTokenCreator` (Custom-Token-Signierung, siehe Doc).
- **Login-UX «state of the art, schlank & reibungslos» (Juli 2026)**: Der Anmelde-Flow ist auf Passkey-
  first getrimmt (Vorbild: SBB). (1) **Passkey-Autofill / Conditional UI** (`lib/passkey.
  loginWithPasskeyAutofill`, `passkeyAutofillSupported`, `cancelPasskeyAutofill`): das E-Mail-Feld trägt
  `autocomplete="email webauthn"`, beim Laden startet **still** eine `mediation:'conditional'`-Zeremonie
  (`useBrowserAutofill:true`) → der Passkey erscheint DIREKT im Autofill-Dropdown, ein Tap + Face/Touch ID
  meldet an, ganz ohne Knopf (Backend war schon usernameless: `login_options` ohne `allowCredentials`,
  `resident_key=REQUIRED`). Abbruch beim Verlassen via `WebAuthnAbortService`. (2) **Login-Seite reduziert**:
  zufällige `ix-var`-Optikvarianten entfernt, `Fingerprint`-Symbol statt `KeyRound`, Passkey-Knopf **über**
  Google (der schnelle Weg), dezenter Hinweis unter dem Feld; `Magic Link`→«Anmeldelink senden».
  (3) **Post-Login-Nudge** (`components/auth/passkey-nudge.tsx`, in ERP-/Konto-/Public-Layout gemountet wie
  das ConsentGate, aber **nicht** blockierend): direkt nach einem Login OHNE Passkey ein dezenter,
  wegklickbarer Anstoss «In Sekunden anmelden – Passkey einrichten» (nutzen-, nicht angst-orientiert; der
  stärkste Adoptions-Hebel). Erscheint NUR, wenn Plattform-Authenticator vorhanden **und** 0 Passkeys
  **und** kein Cooldown (localStorage `inexxio_passkey_nudge`: 30 Tage Ruhe nach «Später», max. 3×, dann
  nie mehr). (4) **Freundlicher Gerätename** aus dem User-Agent (iPhone/Mac/Windows-PC …) statt «Passkey 1»
  (`friendlyDeviceName`). (5) **Verify-Seite + Konto-Sicherheit** auf Design-Tokens + einheitlichen
  Karten-Look migriert; erster Passkey = roter CTA «Passkey einrichten», weitere dezent.
- **Cookie-/Einwilligungs-Layer (schlank, professionell, `docs/passkeys.md §2`)**: Erstanbieter-Consent
  ohne Fremd-CMP. `lib/consent.ts` (eine Wahrheit, Cookie `inexxio_consent` + localStorage, versioniert,
  6 Monate, Event-basiert); `components/consent/cookie-consent.tsx` (nicht blockierendes Banner +
  Einstellungs-Dialog, ZWEI ehrliche Kategorien: **Notwendig** immer aktiv + **Statistik** optional,
  «Ablehnen» = «Akzeptieren», keine Dark Patterns). **Plausible lädt erst mit Statistik-Einwilligung**
  (`components/analytics/plausible.tsx`, Domain aus `plausible_domain`; CSP in `firebase.json` um
  `plausible.io` erweitert). Footer-Link + Datenschutz-Button «Cookie-Einstellungen» (jederzeit
  widerrufbar). Datenschutz-Seite (Ziffer 3) auf den realen, cookie-armen Footprint aktualisiert.
- **UX-/Konsistenz-Runde (Juli 2026, deployt)**: (1) **KI-Artikelanlage validiert wie das Formular** –
  `ai/tools._clean_article_fields` schickt jede von der KI angelegte/aktualisierte Artikel-Spez durch die
  **echten** Pydantic-Validatoren (`schemas/article`: `clean_article_name`/`normalize_size`/`validate_weight`,
  Einheiten/Serialisierung-Whitelist); Fehler kommen als `{error,hint}` zurück → die KI korrigiert sich
  selbst (kein «15cm» mehr, Grösse mm/aufsteigend/×-getrennt, Gewicht in kg). Neues rechte-gescoptes
  Read-Tool `article_name_suggestions` (Dubletten vermeiden statt neu erfinden); Tool-Schemas + Prompt
  (`registry.PROMPT_VERSION`) präzisiert. (2) **Status auf reine Ampel konsolidiert** (`lib/status-flow.TONE`
  = nur noch pending=GELB/warning, done=GRÜN/success, danger=ROT/danger – die früheren Töne `info` (Slate)
  und `inactive` (Grau) sind entfallen): **In Bearbeitung/Reserviert/Offeriert/Bestellt/Bestätigt/Verrechnet
  = GELB**, **Inaktiv/Verschrottet = ROT** («Stopp/nicht verwendbar»), **Verkauft/Verbaut = GRÜN**. Die
  hartkodierten Blau/Petrol/Violett-Ausreisser (Instanz consumed/sold, Prozess-Stepper, PurchaseProgress,
  Dokument-Stufen, Rollen-Badges, Primär-Buttons) sind alle auf Tokens gezogen; Rollen-Badges sind neutral
  (Identität, keine Ampel), Primär-CTA = Rot (Design-System).
- **Status-NAMEN konsolidiert (Runde 2)**: gleiche Lebensphase → **dasselbe Wort**, überall.
  Auftrag «In Bearbeitung» **und** Instanz «Im Prozess» heissen beide **«In Arbeit»** (zwei Namen → einer;
  auch in der Kunden-Bestellliste `orders-list.tsx`); Instanz «Verbraucht» → **«Verbaut»** (passt zu
  «Verkauft»); Dokument «Freigaben laufen» → **«In Freigabe»**. Rollen-Badges + Unternehmens-Badge sind
  **grün** statt grau (ein aktiver Datensatz ist gültig; Grau läse sich als «aus»). (3) **Datenerfassung**: der Bug «Unterschrift konfiguriert, trotzdem Foto-Aufnahme
  angeboten» ist weg – Foto/Unterschrift sind reine `capture_fields`-Typen, der unbedingte `PhotoCapture`-
  Block je Probe ist entfernt. (4) **Auftrag-Shortcut**: kleiner Kopf-Knopf «Auftrag anlegen» am
  freigegebenen **Artikel** (neben Deaktivieren/Ersetzen) und an der **Instanz** (neben Abweichung) – legt
  den Auftrag an, fixiert bei der Instanz gleich diese als Subjekt, und springt hin (`ClipboardPlus`,
  `erp-idbtn`). (5) **Auftrag-Detail entschlackt**: die Subjektart-Zeile («Herstellung – erzeugt Instanzen»)
  und der Abschluss-Text sind entfernt; die **Abweichung** ist jetzt – wie an der Instanz – ein kleiner
  Flag-Knopf im Detail-Kopf (`erp-idbtn-flag`) statt einer Karte mitten im Feld. (6) **Bewegung/Versand**:
  siehe ADR-005-Bullet – der frühere «komisch differenzierte» Split (Klasse-Chip + auto/carrier/self/none-
  Select + Paket/Fracht-Toggle) ist EIN **3-Wege-Umschalter Im Betrieb | Paket | Fracht** mit markierter,
  abgeleiteter Empfehlung.
- **Testnotizen – «Pin setzen» statt Befunde dokumentieren** (Juli 2026, `docs/feedback.md`,
  Migration `082`): Beim Testen fallen laufend Dinge auf; teuer ist nicht das Erkennen, sondern das
  **Rekonstruieren des Kontexts** (wo war ich, welcher Datensatz, welche Rolle, was hat der Browser
  gemeldet). Ein Launcher unten **links** (die KI sitzt rechts) öffnet die Notizen der Seite;
  «Notiz anheften» schaltet in einen **Zeigemodus** (Element unter dem Cursor wird umrandet, Klick
  heftet die Notiz daran, `Esc` bricht ab), Kommentar tippen, Enter. **Sichtbar nur in der
  Testumgebung** (`NEXT_PUBLIC_ENVIRONMENT`/`APP_ENV`; die Produktion antwortet 404) und bewusst für
  **JEDE angemeldete Rolle** – auch aus Kunden-/Lieferantensicht muss gemeldet werden können.
  **Die Brücke vom Pixel zum Code sind nicht Koordinaten/Screenshots, sondern Text + DOM-Signatur:**
  die Oberfläche ist deutschsprachig, ihre Beschriftungen stehen im Repo meist genau einmal – der
  sichtbare Text des geklickten Elements (`anchor.label`) ist damit der beste greppbare Anker
  (dazu Selektor-Kette ohne Klassennamen, gekapptes `outerHTML`, relative Position `rx`/`ry`).
  Automatisch mitgeschnitten ausserdem: Route, **Objektnummer des offenen Datensatzes**, Rolle,
  Viewport, **Build-Commit** (`NEXT_PUBLIC_COMMIT_SHA`) und die letzten 5 Laufzeitfehler (Ringpuffer
  aus `error`/`unhandledrejection` – **kein** Monkey-Patching von `console.*`). Pins sitzen an ihren
  Elementen, solange die Liste offen ist (Ampel: offen gelb · erledigt grün · verworfen grau) –
  damit wird ein Fix **am Ort des Befunds** verifiziert statt aus einer Liste heraus.
  **Kein Geschäftsobjekt:** `feedback_notes` hat **keine Objektnummer**, keinen Feed, keinen
  Event-Strom und kein Audit-Log (Einordnung wie `ai_actions`/`attachments`); die Referenz auf den
  offenen Datensatz heisst darum `target_object_id` wie bei `AiAction` – `object_id` ist im System
  immer die EIGENE Nummer eines Datensatzes. Sichtbarkeit: Personal sieht alles, jede andere Rolle
  nur die eigenen Notizen. Weiterverarbeitung über **«Alle offenen Notizen als Markdown kopieren»**
  → Einfügen in eine Entwicklungs-Sitzung (Skill `.claude/skills/feedback/`); Wächter
  `tests/test_feedback.py`. *Bewusst NICHT gebaut: GitHub-Issue-Sync (Token im Backend = zweite
  Wahrheit), `html2canvas`-Screenshot, flächendeckende `data-*`-Anker, Voting/Threads/Kanban.*
  **Runde 2 (Präzision + Aufräumen):** (1) **Der Feed ist ein Master-Detail auf EINER Route** –
  `/erp` bleibt `/erp`, egal welcher Datensatz offen ist (`?open=` ist nur der Deep-Link von
  aussen). Notizen aus dem Detailfenster trugen darum **keine Objektnummer**; jetzt meldet die
  ERP-Seite ihre Auswahl an `feedback.setOpenRecord` (EINE Stelle: der `sel`-Effekt in
  `erp/page.tsx`), und `currentObjectId` zieht sie der URL vor. (2) **Dynamische Listen**
  (Prozess-Editor: sortierbare Schritte) machen eine `nth-of-type`-Kette wertlos – sie sagt nur
  «der dritte Block». Deshalb markieren sich `PanelHeader`/`SectionTitle` mit `data-fb-section`
  und der aktive Reiter (`DetailTabs`) mit `data-fb-tab`; die Notiz trägt jetzt
  **`context.view`** («Auftrag · Ablauf») und **`anchor.section`** («Bewegung») – beides
  positions**un**abhängig. (3) **Löschen/Zurücksetzen** (vorher gar nicht möglich):
  Papierkorb je Notiz, «Erledigte aufräumen» und «Alles zurücksetzen» (zweiter Klick bestätigt)
  – `DELETE /api/v1/feedback/{id}` bzw. `?scope=done|all`, **weich** (`is_active=false`) und
  über `visible_query` gescopt, damit niemand fremde Notizen wegräumt.

- **Testnotizen-Runde 1 (Instanz-Detail entdoppelt, Notizen #1–#6)**: erste über das Notiz-Widget
  gemeldete Befunde, alle Frontend. Kern war **Doppelung des Zustands**: die Statusbadge im Kopf
  einer Instanz ist bereits die Projektion beider Achsen (`quality`+`disposition`) – die Kachel
  «Letzte Bewegung» zeigte exakt dieselbe Beschriftung noch einmal (entfernt), und die Unterzeile
  der Bestands-Kachel schrieb sie ein drittes Mal aus («Qualität: durchgefallen», «Verkauft», …).
  Sie erklärt jetzt nur noch die **Zahl** (`Nicht am Lager` · `Am Lager` · `N reserviert` – die
  reservierte Menge steht nirgends sonst). Gleiches Muster im Bewegungs-Panel: das grüne Banner
  «Bewegung abgeschlossen» ist weg – dass der Schritt erledigt ist, sagt der Auftrags-Stepper
  (Symbol + Wer/Wann im Hover), im Panel zählt das Ergebnis. **Kachel-Raster:** das Raster war
  durchgehend in der Linienfarbe eingefärbt (Haarlinien über `gap: 1`), wodurch eine
  unvollständige letzte Reihe als **grauer Block** erschien; jetzt trägt jede Kachel ihre eigene
  Haarlinie und steht in Weissraum (Mindestspalte 160→260 px, damit auf breiten Schirmen keine
  schmalen Streifen entstehen). Die **Standort**-Karten sitzen im selben Raster (volle Breite)
  statt als eigene Karten darunter – möglich geworden durch `TileShell` in `fields.tsx`, das die
  dreifach kopierte Kachel-Anatomie zusammenführt. Homepage-Headline: «Industrie 4.0».

- **Testnotizen-Runde 2 (Artikel/Verkauf/Benutzer, Notizen #7–#22)**: (1) **Kennzahlen zeigen
  den Median** (`services/metrics.py: spread` → `(median, low, high)`, EINE Stelle für Lieferzeit
  UND Einstandspreis): ein einzelner Eil-Auftrag oder eine Kleinstmenge zu Apothekerpreisen zieht
  einen Mittelwert weg – der Median bleibt bei dem, was üblich ist. Die Spanne steht untergeordnet
  darunter («kürzeste … · längste …») und nur, wenn sie etwas Neues sagt.
  (2) **Kein Abschnitt «Beschaffung» in der Artikel-Spezifikation** mehr: WIE beschafft wird, steht
  ausschliesslich am Beschaffungs-Schritt im Reiter «Prozess»; geblieben sind ein Abschnitt
  **«Kennzahlen»** (abgeleitet) und die optionalen Angaben in der Basis-Gruppe.
  (3) **Verkauf-Reiter Symbol-first**: alle Wahlmöglichkeiten (Status · Sichtbarkeit · Verfügbarkeit ·
  Preisart · Intervall · Abo-Typ) sind EINE Zeile Symbol-Chips (`IconChoice`) statt Dropdown/Segment,
  jede Erklärung sitzt im **Hover** statt als Absatz in der Fläche; der **Vergleichspreis** ist
  entfallen (soll später automatisiert kommen), das Anlegen eines Preises läuft über **Auto-Save**
  statt Speichern/Abbrechen (bewusst längere Denkpause von 2,5 s, damit keine halb getippte Zahl
  committet wird). Die Datei ist dabei von der Alt-Palette (`#2563eb`/slate) auf Tokens migriert.
  (4) **Benutzer-Datensatz**: «Bestätigungen»-Karte und die AGB-Felder im System-Block entfernt –
  der Reiter **Dokumente** führt das vollständig (der nur dafür gebaute Endpunkt
  `GET /consent/acknowledgements/{id}` ist mit entfallen); neu **«Anmeldung»** (Google SSO ·
  Passkey · Anmeldelink · Passwort, aus `firebase.sign_in_provider`, Migration `083`) und
  **«Passkeys»** (Anzahl Geräte, eine gruppierte Abfrage). **Spiegel-Abgleich mit den
  Profileinstellungen** (Notiz #20): die Benachrichtigungs-Schalter sind auch im ERP entfernt (sie
  hatten nie Backend-Wirkung und fehlen im Profil längst), und die **Rechnungsadresse** erscheint
  jetzt für JEDE Rolle statt nur für Kunde/Lieferant – bei einer Mitarbeiterin sah das Personal
  ihre eigenen Eingaben sonst nicht.
  (5) Kleineres: Bestandsliste ohne Summenzeile + zentriert, Instanz-Detail auf allen Reitern
  zentriert, Auftrag-Shortcut getönt wie der Abweichung-Knopf (`.erp-idbtn-act`), Prozess-Schritt
  nennt nur noch den Prüfumfang (nicht die Zahl der Erfassungsfelder), Homepage-Headline.

- **Testnotizen-Runde 3 (Auftrag-Bedarf & Ablauf, Notizen #23–#31)**: (1) **Quelle als Schieber**
  (`SourceSwitch`): EIN Gleis mit gleitendem Reiter statt drei gleich aussehender Knöpfe – dass die
  Optionen einander ausschliessen, zeigt jetzt die Bewegung statt ein Erklärsatz; gesperrte Felder
  bleiben sichtbar und nennen den Grund im Hover. (2) **«Erzeugen» zeigt den Artikel-Prozess**
  (`ProcessSteps owner="articles" readOnly`) – **1:1-Spiegelung, keine Kopie**: dieselbe Komponente,
  dieselben Daten, nur lesend; geändert wird am Artikel. Vorher wurde die Aussage «der Artikel-Prozess
  läuft» nur behauptet. (3) **Ablauf sieht aus wie der Prozess-Reiter am Artikel** – die zusätzliche
  Karte um `ProcessSteps` ist weg (gleicher Editor ⇒ gleiche Optik), an allen drei Stellen
  (Ablauf, Unter-Auftrag, Spiegel). (4) **Instanz-Auswahl ist durchsuchbar** (ab 8 Instanzen
  Suchfeld nach Objektnummer + scrollende Liste) – bei dreistelligen Beständen war die Chip-Wolke
  nicht mehr bedienbar. (5) **«Wiederkehrend» ohne Häkchen und ohne Speichern-Knopf**: die Periode
  IST der Schalter (leer = einmalig), Auto-Save wie überall, und der Zustand steht als **Satz**
  darunter statt als Schalterstellung. Der widersprüchliche Zustand «angehakt, aber keine Periode»
  existiert damit nicht mehr. (6) **Zahlenfelder lassen nur Zahlen zu** (`fields.numericOnly` +
  `numericInputProps`, die EINE Regel): Komma→Punkt, höchstens ein Trenner, bewusst KEIN
  `input type="number"` (dessen Spinner/Scrollrad stören, und bei ungültiger Eingabe liefert es
  einen leeren Wert – getippte Zeichen verschwinden spurlos). Verdrahtet an Auftrags-Menge,
  Ressourcen-Zeile, Prüfumfang, Messwert, Wiederkehr-Perioden. (7) **Datensatz-Auswahlen zeigen die
  grösste Nummer zuerst** (`SearchSelect: newestFirst`) – Objektnummern werden aufsteigend vergeben,
  gemeint ist fast immer ein zuletzt angelegter Datensatz; greift nur, wenn alle Werte Zahlen sind.
  *Bewusst NICHT geändert: der «Freigeben»-Knopf bleibt **rot**. Rot ist im Design-System der EINE
  laute CTA-Akzent; Grün ist die Farbe des ZUSTANDS «freigegeben/erledigt». Wäre die Aktion grün,
  hiesse dieselbe Farbe gleichzeitig «tu es» und «ist getan» – die Badge daneben wird nach der
  Freigabe grün, das ist die Rückmeldung.*

- **Testnotizen-Runde 4 (Prozess-Editor & Datenerfassung, Notizen #32–#51)**: (1) **Eine
  durchgefallene Datenerfassung ist nicht mehr terminal** (#51, der einzige offene Punkt aus
  `docs/review-2026-07.md`): `all_steps_done` verlangt je Schritt `done` – ein Schritt auf
  «fehlgeschlagen» verhinderte den Abschluss **für immer**. Der Weg nach vorn ist jetzt gebaut:
  Abweichung klärt den Fall (nacharbeiten/verschrotten/ersetzen) → **«Erneut erfassen»** im Panel →
  neue Bewertung. Damit das etwas ändern kann, läuft `_apply_per_instance_qc` bei **jedem** Ergebnis
  (nicht nur beim Nichtbestehen) und **löst eine frühere Sperre** (`failed` → `pending`, nie direkt
  `passed` – freigegeben wird weiterhin erst beim Auftrags-Abschluss). Wächter
  `test_smoke.py: test_failed_inspection_is_not_terminal`. (2) **Datenerfassung ohne Erfassungsfeld
  ist keine mehr** (#41): Schema-Prüfung analog zur Ressource-Zeile (nicht nur im Formular) – ein
  solcher Schritt böte im Auftrag nichts zu erfassen. (3) **Prüfumfang als Voreinstellungen** (#36,
  #37): Chips «Alle · Jedes 2. · Jedes 4. · Stichprobe» statt Prozentfeld mit Erklärsatz; «…» blendet
  ein Zahlenfeld für Sonderwerte ein (ein gespeicherter Sonderwert geht nie verloren). (4) **Gut/
  Schlecht als Daumen** (#42), **eigene Farbfamilie für die Datenerfassung** (#44 – sie trug exakt
  die Tönung der Bewegung). (5) **Weniger Text, mehr Hover**: Bezugsquelle als **symbol-only
  Schieber** (#47, generischer `fields.IconSwitch` – dieselbe Mechanik wie der Bedarf-Schieber),
  Ressourcen-Legende (#45), Beschaffungs-Infotext (#48), Lieferanten-Hinweis (#49) und der
  Bild/Unterschrift-Kasten (#38) entfallen; «+ Ressource/Erfassungsfeld» wird zum blossen **«+»**,
  sobald die Liste nicht leer ist (#46); Headline «Für Lieferant sichtbar» (#50). (6) **Auswahl
  neueste zuerst repariert** (#34): `newestFirst` verlangte, dass ALLE Werte Zahlen sind – der
  Platzhalter «— wählen —» hat die Sortierung damit überall stillgelegt. Platzhalter bleiben jetzt
  vorn, der Rest wird sortiert. (7) **Namensgebung vereinheitlicht**: «Adresszeile 1/2» → **«Strasse
  und Hausnummer» / «Adresszusatz»** wie in den Profileinstellungen (#33); Verkauf «Publiziert/
  Entwurf» → **«Nicht sichtbar / Sichtbar»**, Ausgangszustand links (#32). (8) Ziel-Angabe am
  Bewegungsschritt: **Objektnummer zuerst**, dann die Bezeichnung (#43); Wiederkehr zeigt nur noch
  «Aktiv · alle N Tage» statt eines Erklärsatzes (#35).
  *Bewusst NICHT geändert: der «Hinzufügen»-Knopf im Schritt-Editor bleibt (#40) – Auto-Save würde
  einen halb konfigurierten Schritt anlegen, und genau das verbietet #41.*

- **Testnotizen-Runde 5 (Sperren-Modul, Notizen #52–#68)**: Kern ist ein **neuer Schritttyp
  `block` = «Sperren»** (#59) – das **reversible Gegenstück zum Verschrotten**: nicht alles, was
  aus dem Verkehr muss, ist Ausschuss (die defekte Maschine wartet auf ihre Wartung, das
  fragliche Los auf ein Laborergebnis). **Modelliert auf der Qualitäts-Achse**
  (`instances.quality='blocked'`), NICHT auf der Verbleibs-Achse: eine Sperre ändert nicht,
  *wo* etwas ist, sondern ob man es *verwenden darf*. Das ist der ganze Trick – weil
  `inventory.in_stock_clauses()` ohnehin `passed` UND `in_stock` verlangt, fällt eine gesperrte
  Instanz **ohne eine einzige zusätzliche Abfrage** aus FIFO, Verfügbarkeit, Bestandszählung und
  Reservierbarkeit; und weil `quality` von Natur aus veränderlich ist, ist die Rücknahme
  eingebaut statt nachgerüstet. Verschrotten dagegen ist `DECREASE`/terminal, standortlos und
  löst alle Reservierungen – Sperren ist `NEUTRAL`, lässt Standort, Menge und Reservierungen
  **unangetastet** (das Teil gehört weiterhin seinem Auftrag, es ist nur gerade nicht benutzbar).
  Schema-seitig kostet das **eine** Spalte: `disposals.mode` ∈ scrap|block (Migration `084`,
  `quality` ist ein freies VARCHAR). **Ein Panel, zwei Wirkungen** (`scrap-panel.tsx` mit
  `mode`-Prop) – die Instanz-Auswahl ist identisch, nur das Ergebnis nicht; Teilmengen gibt es
  nur beim Verschrotten (eine halbe Charge sperren hiesse, sie zu teilen). **Aufgehoben wird an
  der Instanz, nicht im Prozess** (`POST /erp/instances/{id}/unblock`, Knopf nur bei
  `quality='blocked'`): eine Maschine kommt aus der Wartung zurück, ohne dass jemand dafür einen
  Auftrag anlegen will. Der Zustand danach wird **abgeleitet statt gemerkt**
  (`scrap._restore_quality`: `released_at` gesetzt → `passed`, sonst `pending`) – kein
  verstecktes «vorherige Qualität»-Feld, das auseinanderlaufen könnte. Nur im **Auftrags**-Ablauf
  zulässig (wie `scrap`), Wächter `test_smoke.py: test_block_is_reversible_scrap_is_not`.
  **Wortschärfe im gleichen Zug:** `quality='failed'` hiess bisher ebenfalls «Gesperrt» – kurzzeitig
  hiess es dann «Durchgefallen» und stand neben «Gesperrt». *Runde 6 hat die beiden zu EINEM Zustand
  zusammengeführt (Migration `085`) – siehe unten.* Daneben: (2) **Ein Prozessschritt wird nicht mehr nachträglich umkonfiguriert** –
  die Sonderfälle «Sichtbare Felder» und «Dokument-Deklaration» hielten als einzige Module einen
  Bearbeiten-Zustand am Leben; wie überall sonst gilt jetzt löschen + neu anlegen. (3)
  **Lieferant am Beschaffungs-Schritt ist klickbar** (`ArticleProcessStepResponse.
  supplier_object_id` – `supplier_id` ist der INTERNE Schlüssel und darf nie als Objektnummer
  erscheinen), Symbol statt Wort. (4) **Dokument-Deklaration symbol-first**: Sichtbarkeit
  (Alle · Intern · Vertraulich) und Anerkennungs-Publikum (Niemand · Alle · Rollen · Personen)
  als `IconSwitch` mit Hover-Erklärung statt Segmented+Erklärsatz. (5) **Benutzernummer ist kein
  Formularfeld** – sie ist vergeben und unveränderlich, steht also als Versalien-Label +
  monospaced Nummer da statt in einem Eingabefeld, das zum Hineinklicken einlädt; dazu zwei
  Erklärkästen im Konto entfernt bzw. auf eine Zeile eingedampft.
  *Bewusst NICHT geändert (#68, wie #40): der «Hinzufügen»-Knopf bleibt – Auto-Save legte einen
  halb konfigurierten Schritt an, was #41 gerade verbietet.*

- **Testnotizen-Runde 6 (Sackgassen im Auftrag, Notizen #70–#75, Migration `085`)**: Fünf der
  sechs Befunde waren **derselbe Bug in verschiedenen Ausprägungen** – ein Auftrag, der nach
  einer fehlgeschlagenen Datenerfassung nicht mehr weiterkam.
  (1) **«Gesperrt» ist EIN Zustand mit EINEM Wort** (#73): eine durchgefallene Instanz trug
  `quality='failed'`, eine bewusst ausgesetzte `quality='blocked'`. Beides heisst «vorhanden,
  aber nicht verwendbar», beides fällt über dieselbe Bedingung aus FIFO/Bestand, beides ist
  aufhebbar – nur die Namen waren verschieden. Geschrieben wird jetzt **nur noch `blocked`**,
  `failed` wird tolerant GELESEN (Altbestand; Migration `085` zieht ihn nach). Damit es EINE
  Stelle bleibt, geht jeder Lesezugriff über `inventory.is_blocked()`/`unblocked_clauses()`
  statt über einen handgeschriebenen Vergleich (dieselbe Zwei-Formen-Regel wie
  `in_stock_clauses`/`is_in_stock`).
  (2) **Ein fehlgeschlagener Befund wird vom Folgeauftrag geklärt – von sonst nichts** (#70,
  #71). `all_steps_done` verlangt je Schritt `done`; ein Schritt auf «fehlgeschlagen» blieb es
  für immer → der Auftrag schloss **nie** ab und seine Instanzen wurden **nie** freigegeben
  (genau #71: die Abweichung lief korrekt durch, die Charge hing trotzdem in «In Arbeit»).
  Runde 4 hatte dafür einen Knopf «Erneut erfassen» ins Panel gesetzt – der ist **entfernt**
  (#70: «nur ein Folgeauftrag darf das») und war ohnehin eine Sackgasse, weil
  `resolve_exec_step` nur **aktive** Schritte ausführt und ein fehlgeschlagener das nicht ist
  (409). Stattdessen: schliesst die **Abweichung** ab, vermerkt `inspection.resolve_failed_by`
  den Klärer auf dem Befund (`inspections.resolved_by_order_id`), und `_fact_status` liest den
  Schritt als `done`. **Der Befund selbst bleibt `failed`** – was gemessen wurde, wird nicht
  nachträglich schöngeschrieben; die Klärung steht als eigener, nachvollziehbarer Vorgang
  daneben (Panel: «Geklärt durch <Objektnr>»).
  (3) **Der Prüfumfang bemisst sich an der geprüften MENGE, nicht an der Zahl der Subjekte**
  (#72): `required_count` rechnete mit `order.quantity`. Eine Abweichung auf EINE Charge à
  5 Stk trägt aber `quantity=1` (ein Subjekt) – bei «jede» kam so statt fünf Proben nur eine.
  Stichprobenzahl und Stichprobenziele stammen jetzt aus **derselben** Quelle
  (`inspection.inspected_quantity` → `order_active_instances`) und können nicht mehr
  auseinanderlaufen; `create_deviation` deklariert die Menge ebenfalls als Summe der
  Instanz-Mengen statt als deren Anzahl.
  (4) **Eine Bereitstellung ist keine Abweichung** (#75): `instance_open_deviation` filterte
  nicht auf `reason` – damit galt **jeder** Unter-Auftrag als «offene Abweichung», auch die
  automatisch abgeleitete **Bereitstellung** (`reason='provisioning'`, ein Unter-Auftrag mit
  genau einem Bewegungs-Schritt: exakt das «Folgeauftrag …475 mit aktivem Bewegen-Modul», das
  niemand angelegt hatte). Ein Abbruch scheiterte an dieser falschen Meldung. Jetzt zählt nur
  `reason='deviation'` – derselbe Filter, den `open_deviations` längst hatte.
  (5) **Der Feed zeigt den Status des Auftrags, nicht den seiner Bestellung** (#74): bei einem
  freigegebenen Auftrag schlug der **Beschaffungs**-Status durch – ein Auftrag, dessen
  Bestellung geliefert war, stand auf «Geliefert», obwohl Prüfung, Bewegung und Verkauf noch
  offen waren. Der Stand eines einzelnen Schritts ist nicht der Stand des Auftrags; er steht
  im Detail am Ablauf.
  Wächter: `test_smoke.py: test_failed_inspection_is_not_terminal` (erweitert),
  `test_blocked_is_one_state_with_one_word`, `test_only_a_deviation_counts_as_an_open_deviation`,
  `test_sample_size_comes_from_the_inspected_instances`.

- **Unter-Aufträge: sichtbar, abbrechbar, sauber gelöst** (Juli 2026, Folge-Analyse zu Runde 6):
  Drei Lücken desselben Themas – *was das System selbst anlegt, muss der Mensch sehen und wieder
  loswerden können*.
  (1) **Bereitstellungen waren unsichtbar**: `OrderResponse.provisionings` wurde geliefert, aber
  nirgends gerendert – Abweichung/Nachschub/Retoure hatten je eine Karte, die Bereitstellung
  nicht. Sie ist die **einzige automatisch entstehende** Unter-Auftragsart; genau darum muss sie
  sichtbar sein (sonst taucht wie in Notiz #75 ein fremder «Folgeauftrag mit aktivem Bewegen-Modul»
  auf, den niemand angelegt hat). Jetzt eigene Karte im Auftrag-Detail, Erklärung im Hover.
  (2) **Eine steckengebliebene Bereitstellung hat einen Ausweg**: sie blockiert den Schritt UND
  den Abschluss – lief sie nicht durch, war der Auftrag ohne Ausstieg tot. «Abbrechen» am
  Bereitstellungs-Datensatz ist die Aussage «das mache ich von Hand»; damit das hält, legt
  `provisioning.cancelled_for_step` sie **nicht neu an**. Marker ist der **abgebrochene
  Unter-Auftrag selbst** (`status='inactive'` zu diesem Schritt) – kein zusätzliches Feld, keine
  zweite Wahrheit, und das Audit-Log zeigt, wer die Bereitstellung wann übersprungen hat.
  (3) **EINE Aufräum-Stelle für Unter-Aufträge** (`deviation.detach_sub_order`): ein Unter-Auftrag
  hält drei Fäden zum Eltern – Subjekt-Bindung der Instanzen, Verarbeitungs-Links und (beim
  Abbruch-Folgeauftrag) `abort_into_id`. Wer nur den Status auf «inaktiv» setzte, liess alle drei
  stehen: der Eltern blieb **für immer pausiert** (`abort_into_id` nie NULL → auch kein neuer
  Abbruch mehr möglich) und seine Instanzen zeigten auf einen toten Auftrag. Beide Türen –
  «Zurücknehmen» (Entwurf) und «Abbrechen» (freigegeben) – gehen jetzt durch dieselbe Stelle, und
  ein Unter-Auftrag bekommt **nie** einen eigenen Folgeauftrag (sein Subjekt gehört ohnehin dem
  Eltern bzw. er transportiert nur); danach läuft der Eltern automatisch weiter.
  (4) Dazu: **«Abbruch ausstehend» ist im Feed ein eigener Zustand** statt «In Arbeit» – ein
  beantragter Abbruch sah sonst aus, als hätte er nichts bewirkt.
  Wächter: `test_smoke.py: test_sub_order_deactivation_goes_through_one_cleanup`,
  `test_cancelled_provisioning_is_not_recreated`.

- **Abbrechen ist ein Vollzug, kein Antrag – und kein zweiter Knopf** (Juli 2026, Migration
  `086`): Drei zusammenhängende Korrekturen am Abweichungs-Modell.
  (1) **Der Abbruch wirkt sofort.** Bisher blieb das Original `released` («Abbruch ausstehend»)
  und wurde erst inaktiv, wenn der Folgeauftrag freigegeben war; bis dahin liess er sich
  zurücknehmen. Das war als Sicherheitsnetz gedacht, aber falsch herum: *ein Auftrag, den man
  abbrechen kann und der danach weiterläuft, ist nicht abgebrochen.* Jetzt setzt
  `deviation.abort_parent` ihn im selben Moment auf inaktiv – endgültig, keine Reaktivierung;
  nur der Abweichungsauftrag lebt weiter und hält die Instanzen (`keep_instances`).
  `abort_into_id` ist nur noch der Zeiger «fortgeführt in …»; `apply_abort_on_release` und
  `create_abort_followup` sind entfallen, `_is_paused_by_deviation` hängt nur noch an offenen
  Abweichungen. Anzeige: **«Abgebrochen» (rot)** als Projektion über `orderStatusConfig(status,
  aborted)` – «Inaktiv» heisst verworfen, «Abgebrochen» heisst fortgeführt.
  (2) **EIN Vorgang, EIN Wort, EIN Symbol.** «Abbrechen» war ein zweiter Name und ein zweites
  UI für dieselbe Sache (es legte ja einen Abweichungsauftrag an). Die Status-Aktion ist weg;
  es gibt nur noch den Flag-Knopf **«Abweichungsauftrag»**, und der Unterschied ist eine
  **Eigenschaft des Vorgangs** statt eines zweiten Wegs: `OrderDeviationCreate.abort_parent`
  (Dialog: «Auftrag läuft weiter» ↔ «Auftrag abbrechen»). `POST /orders/{id}/abort` bedient nur
  noch das **Verwerfen** eines Unter-Auftrags bzw. eines Auftrags ohne Instanzen – ein anderer
  Vorgang, darum ein anderes Wort.
  (3) **Eine Abweichung darf ihre eigene Abweichung haben.** Die Regel «höchstens EINE aktive
  Abweichung je Instanz» traf auch die Instanzen, die schon in einer Abweichung steckten –
  misslang die Nacharbeit, liess sich das nicht melden. Jetzt gilt sie nur noch für das
  **gleichzeitige** Greifen zweier Vorgänge (`existing.id != parent.id`); die **Kette**
  Abweichung → Abweichung ist erlaubt und bildet die Realität ab.
  Wächter: `test_abort_is_a_deed_not_a_request`, `test_a_deviation_can_have_its_own_deviation`.

- **Eine offene Bereitstellung hält den ganzen Auftrag an – und steht im Ablauf** (Juli 2026):
  Gemeldeter Fall: Erzeugungsauftrag mit Beschaffung + Datenerfassung; die Bereitstellung
  schien erst NACH der Datenerfassung zu entstehen, obwohl sie zwischen die beiden gehört.
  **Der Zeitpunkt war schon richtig** (`purchase` deklariert `PROV_RECEIVING` + Stufe
  «danach» → sie entsteht, sobald die Bestellung geliefert ist). Falsch war die **Reichweite
  der Blockade**: `_step_blocked` fragte `open_provisioning(order, step.id)` – die
  Bereitstellung gehört aber zum **Beschaffungs**-Schritt, nicht zur Datenerfassung, also war
  die Datenerfassung ausführbar, während die Ware buchhalterisch noch beim Lieferanten lag
  (nur der Auftrags-*Abschluss* lief auf sie auf – von aussen sieht das aus wie «zu spät
  ausgelöst»). Jetzt gilt **eine Regel statt einer Fallunterscheidung**: *solange eine
  Bereitstellung offen ist, geht der Auftrag nicht weiter* (`open_provisioning(db, order)`).
  Damit braucht es keine fest verdrahtete Bewegung nach jedem Beschaffungs-Schritt.
  **Darstellung:** die Bereitstellung erscheint als **Knoten im Auftrags-Stepper** an ihrer
  Position – `OrderStepInfo.provisionings` (alle Bereitstellungen des Schritts) +
  `provisioning_stage` ∈ before|after, abgeleitet aus der bereits deklarierten Zeitpunkt-Regel
  (`provisioning._STAGE_BEFORE`). Sie bleibt ein **Unter-Auftrag**, der Knoten ist reine
  Projektion (Klick öffnet den Datensatz, kein Schritt-Panel); das Frontend platziert nur,
  es entscheidet nicht. Wächter: `test_smoke.py: test_open_provisioning_holds_the_whole_order`.

- **Testnotizen-Runde 7 (Auftrag sieht aus wie der Prozess, Notizen #79–#82)**: (1) **Der
  laufende Auftrag zeigt denselben Fluss wie die Definition** (#82, `components/erp/order-
  flow.tsx`): senkrechter BPMN-Fluss mit Start-/Endknoten und einer Karte je Modul – exakt
  die Bildsprache, in der man den Prozess am Artikel definiert hat. Vorher war es ein
  waagrechter Punkte-Stepper: dieselbe Sache in einer **zweiten** Bildsprache, und man musste
  erst übersetzen, welcher Punkt welches Modul ist. Geteilt werden die Fluss-Bausteine
  (`FlowTerm`/`Connector`/`kindColor`/`STEP_MAXW` aus `process-steps.tsx`) – EINE Quelle für
  die Optik. Der einzige Unterschied ist, was eine Karte **zeigt**: dort die Konfiguration,
  hier der Zustand (Erledigt · In Arbeit · Angehalten · Wartet · Fehler) und im Hover Wer/Wann.
  Die abgeleiteten **Bereitstellungen** sind Karten an ihrer Position im Fluss und öffnen ihren
  Datensatz (sie sind Unter-Aufträge, kein Modul). `process-stepper.tsx` + `toStepperState`
  sind damit ersatzlos entfallen. (2) **Der Auftrags-Kopf hat dieselbe Anatomie wie Artikel und
  Instanz** (#79): Symbol · Eyebrow · Titel · Objektnummer + Symbol-Aktionen in EINER Zeile,
  rechts Speicher-Anzeige und Status. Die Objektnummer stand vorher als eigener Kasten ganz
  rechts – ein drittes Layout für dieselbe Sache. (3) **Kein «Verwerfen»** (#81): ein
  Unter-Auftrag ist eine bewusste Entscheidung und wird durchgezogen, nicht weggeworfen. Die
  **einzige** Ausnahme ist die **Bereitstellung** – sie legt das System selbst an, also braucht
  sie einen Ausstieg; er heisst jetzt **«Bereitstellung übergehen»** (Symbol im Kopf) und sagt
  damit, was man entscheidet, statt generisch «verwerfen» zu heissen.

- **Testnotizen-Runde 8 (der Auftrag ist der Prozess, Notizen #83–#90, Migration `087`)**:
  (1) **Der Schritt wird dort bearbeitet, wo er im Fluss steht** (#84): die gewählte Modul-Karte
  klappt ihr Panel **in sich selbst** auf – dieselbe Anatomie wie die Konfiguration in der
  Definition. Der abgespaltene Container darunter ist weg, ebenso der Karten-Hintergrund um den
  Fluss (#83): ein Fluss aus Karten braucht keine Karte drumherum.
  (2) **Zustand ohne Wort** (#88): erledigte und noch nicht erreichte Schritte treten zurück
  (weisse Fläche, gedämpft), nur was JETZT dran ist, trägt seine Modulfarbe. Dazu ein Symbol
  statt eines Status-Textes – Haken (erledigt), Pause (angehalten), Kreuz (Fehler); Wer/Wann
  bleibt im Hover.
  (3) **Abweichungen stehen an ihrer Stelle im Ablauf** (#85): `orders.origin_step_id`
  (vormals `provisioning_step_id`, Migration `087`) beantwortet für **jede** Unter-Auftragsart
  dieselbe Frage – aus welchem Schritt ist er hervorgegangen? `create_deviation` schreibt den
  gerade aktiven Schritt hinein; der Fluss rendert die Abweichung als **dezenten Abzweig**
  (schmale Pille mit Aststück) statt als Karte über dem Prozess.
  (4) **«Auftragsspezifikation» statt «Bedarf», immer zuoberst** (#87) – und die bei der
  Freigabe entstandenen **Instanzen stehen in derselben Karte** (#86, `OrderInstances
  embedded`) statt in einer zweiten darunter: sie sind das Ergebnis derselben Aussage
  (Artikel + Menge), kein neues Thema.
  (5) **«In Arbeit» gibt es nicht mehr** (#89/#90): der EINE Name für «läuft gerade» ist
  **«Im Prozess»** – beim Auftrag, bei der Instanz, im Prozessschritt und in der
  Kunden-Bestellliste.
  (6) **Das Notiz-Werkzeug liegt über allem** (`z-[2000]`+): Dialoge/Lightboxen (bis `zIndex 70`)
  verdeckten den Launcher – ausgerechnet dort, wo man beim Testen gerade steht, liess sich
  nichts melden. Der Zeigemodus funktionierte schon immer über Overlays hinweg (Handler in der
  **Capture**-Phase am `document`), nur sichtbar war er nicht.

- **Testnotizen-Runde 9 (Kamera-first scannen, Panel entschlackt, Notizen #91–#104)**:
  (1) **Der Scan-Dialog IST die Kamera** (#94–#99, `components/scan/scan-dialog.tsx`): kein
  Kopf, kein Titel, kein Erklärtext, kein zweiter Kasten – die Sheet-Fläche ist der
  Kamerastrom, alles Weitere liegt darüber. Im Zielrahmen tastet ein **Suchstrahl**
  (`.ix-scanbeam`, `prefers-reduced-motion`-fest) das Bild ab, darunter steht die EINE
  Angabe, die zählt: **was** zu scannen ist («Instanz 100000479»). Die Suche ist eine
  milchige Leiste **im Bild** statt eines Blocks darunter; Klick daneben schliesst wie das ×.
  `ScanRequest.title` und `ScanStep.hint` sind ersatzlos entfallen (sie wurden nirgends mehr
  gerendert) – `label` ist der einzige Text.
  (2) **Panels ohne zweiten Rahmen und ohne zweiten Titel** (#100, #104): sie sitzen seit
  Runde 8 IN der Modul-Karte des Ablaufs; ihr eigener `cardStyle` (Rahmen, Fläche, Polsterung)
  und ihr `PanelHeader` waren damit Container-in-Container bzw. eine Titel-Dopplung – beides
  entfernt (Datenerfassung/Bewegung/Ressource/Verschrotten; Beschaffung/Verkauf/Dokument
  behalten ihren Kopf, weil er Status bzw. einen anderen Namen trägt). Der aufgeklappte
  Panel-Bereich trägt jetzt die **Modulfarbe** der Karte statt Weiss.
  (3) **Datenerfassung**: «Vorschau: Bestanden/Durchgefallen» entfällt (#103 – das Ergebnis
  steht nach dem Abschluss da), «Erfassung abschliessen» ist **gesperrt, solange nichts
  erfasst ist** (#101 – ein Klick auf einen leeren Satz hätte die Prüfung mit lauter
  Nichtwerten durchfallen lassen), der Prüfumfang ist eine Zeile statt eines grauen Kastens
  (#100). Der ⓘ-Text ist mit dem Kopf entfallen (#93). **Die Hochstufung auf 100 % bleibt**
  (#102 revidiert #93 ausdrücklich: «diese Funktion doch beibehalten»).
  (4) **Auftragsspezifikation im Kachel-Design** (#92, `SpecTile`/`TileShell`): dieselbe
  Sprache wie Artikel-Spezifikation und Instanz-Merkmale – Symbol-Kasten, Versalien-Label,
  Wert; responsiv über `auto-fit, minmax(min(100%, 260px), 1fr)`. Die Instanzen sind eine
  Kachel über die volle Breite im selben Raster.
  (5) **«Prozess» statt «Ablauf»** (#91) – auch bei Nachschub/Retoure/Abweichung.

- **Testnotizen-Runde 10 (Kamera-Sprache überall, Kopf aufgeräumt, Notizen #105–#122)**:
  (1) **Der Dokument-Dialog spricht die Scanner-Sprache** (#119): die Kamera-Phase ist jetzt
  dieselbe Fläche wie beim Objekt-Scanner – ganz Kamera, Zielrahmen mit Suchstrahl, alle
  Bedienelemente als milchige Chips **im Bild** (Auslöser · Datei hochladen · Objektnummer
  öffnen). Erst ab «Analyse» wird es ein normales Formular-Fenster: dort geht es um Text,
  nicht um Bild. `DocumentCamera` hat dafür einen `extra`-Slot für die Zusatzfunktion.
  Im Scanner selbst entfällt das × (#108 – Klick daneben und Esc schliessen ohnehin), und der
  Such-Platzhalter nennt das Ziel (#109: «Instanz 100000479 suchen»).
  (2) **Kein Footer mehr** (#105): der Streifen «Erstellt … Zuletzt geändert» am Fensterrand
  ist weg; die Angabe steht als Kachel in der Auftragsspezifikation, wo die übrigen Angaben
  stehen.
  (3) **Die Status-Aktion sitzt bei den Aktionen** (#117): «Freigeben» steht neben QR-Druck
  und Abweichung unter dem Titel; rechts bleibt nur der **Zustand**. Eine Aktion gehört zu den
  Aktionen, der Status zeigt an.
  (4) **Titel eines Mehrpositionen-Auftrags** (#107): es gibt keinen EINEN Artikel – der Titel
  nennt den ersten und wie viele noch dazugehören («Schraubendreher +2»), ohne Artikel bleibt
  es beim schlichten «Auftrag».
  (5) **Alle Symbol-Aktionen sind getönt** (#113/#115): ein Knopf ohne Fläche sah neben den
  getönten Nachbarn aus wie deaktiviert. `.erp-idbtn` trägt jetzt grundsätzlich eine dezente
  Tönung, Deaktivieren/Ersetzen eine rote (`.erp-idbtn-danger`).
  (6) **Bestand am Artikel**: neueste Instanz zuerst + Suchfeld (#111), ohne Auftragsnummer
  (#112 – am Artikel zählt die Instanz) und ohne die Überschrift «Bestand» (#114 – der Reiter
  sagt es bereits).
  (7) **Inhalte zentriert und responsiv** (#120/#121): Spezifikation und Dokumente stehen
  mittig statt links geklebt; die Spezifikations-Karte wächst mit (`clamp`-Polsterung, keine
  feste 720-px-Breite mehr).
  (8) **Herkunft einer Zahl gehört ans Label** (#122): «Median aus erledigten Aufträgen» ist
  ein ⓘ neben «Lieferzeit»/«Einstandspreis» statt einer eigenen Zeile darunter.
  (9) Datenerfassung: kein Live-Häkchen je Stichprobe mehr (#110) – es bewertete, während man
  noch tippt; das Ergebnis steht nach dem Abschluss da. Die Panels mit eigenem Kopf
  (Beschaffung/Verkauf/Dokument) haben ihren weissen Kasten verloren (#118) und tragen jetzt
  ebenfalls die Modulfarbe der Karte.
  (10) Die Prozess-Überschriften im **Entwurf** entfallen (#106/#116) – der Fluss mit
  Start-/Endknoten sagt selbst, was er ist; am laufenden Auftrag bleibt «Prozess».

- **Testnotizen-Runde 11 (gebundener Bestand, ruhige Aktionen, Notizen #123–#137)**:
  (1) **Ein freigegebener Unter-Auftrag reserviert seinen Bestand** (#131, `subject._bind_
  deviation_subjects`): eine Abweichung band ihre Instanzen bisher nur über
  `subject_of_order_id` + Verarbeitungs-Link – **FIFO sah sie weiterhin als frei**, ein
  beliebiger anderer Auftrag konnte sie wegnehmen, und die Badge zeigte «Freigegeben», obwohl
  sie längst gebunden waren. Jetzt wird reserviert, was am Lager liegt (in Arbeit/verkauft/
  gesperrt braucht es nicht – dort greift ohnehin kein FIFO); Abschluss und Verwerfen lösen
  die Reservierung über die bestehende `release`-Mechanik. Wächter
  `test_fixed_subject_sub_order_reserves_its_stock`.
  (2) **Die Schritt-Palette spricht die Sprache des Flusses** (#123/#124): Symbol in der
  **Modulfarbe** statt neutraler Kachel mit Text; der Name klappt beim Hover auf
  (`.erp-palette`, `prefers-reduced-motion`-fest), die Rolle steht im Tooltip.
  (3) **Ruhige Hauptaktion** (#125): `PrimaryButton` ist **schwarz** statt rot. Rot ist der
  EINE laute Akzent für die Entscheidung über den Datensatz («Freigeben»), nicht für die
  alltägliche Arbeit im Schritt – «Scannen & bewegen» in Rot las sich wie ein Fehler. Grün
  bleibt der Abschluss. Ebenso der Foto-Auslöser im Dokument-Dialog (#135); «Datei hochladen»
  ist dort nur noch ein Symbol (#136).
  (4) **Weniger Text im Bewegungs-Panel**: die Empfehlung markiert die Option selbst (Punkt +
  Hover) statt eines Erklärsatzes (#132); der Hinweis «Innerbetriebliche Bewegung – kein
  Versand» entfällt (#133 – der Umschalter sagt es bereits).
  (5) **Eine Aussage, eine Stelle** (#126): die Zielangabe im Scanner steht nur noch als
  **Platzhalter** im Suchfeld («Aktueller Standort suchen») statt zusätzlich als Chip im Bild.
  Im Dokument-Dialog entfällt die Objektnummer-Eingabe ganz (#134) – dafür gibt es die
  Feed-Suche.
  (6) **Abweichungs-Dialog** (#128–#130): kein Erklärtext, kein ×, und **nichts ist
  vorausgewählt oder hervorgehoben** – zwei gleichwertige Wege, die Entscheidung trifft der
  Mensch und nicht die Gestaltung.
  (7) **Feed ohne Scrollbalken** (#137, `.ix-noscrollbar`): gescrollt wird weiterhin (Rad,
  Trackpad, Touch, Tastatur), nur der Balken verschwindet.

- **Testnotizen-Runde 12 (eine Frage – eine Antwort, Notizen #138–#147)**: Der rote Faden
  dieser Runde ist Entdopplung: dieselbe Aussage stand jeweils an zwei Stellen oder in zwei
  Formen.
  (1) **Positionen tragen ihre Instanzen** (#141, `components/erp/order-positions.tsx`,
  ersetzt `order-instances.tsx` + `PositionsList`): Die Auftragsspezifikation zeigte oben die
  Positionen (Artikel → Menge) und darunter **alle** Instanzen des Auftrags als zweite flache
  Liste – bei mehreren Positionen war damit ausgerechnet die entscheidende Zuordnung
  unsichtbar: welche Instanz gehört zu welchem Artikel? Jetzt hängen die Instanzen eingerückt
  an einer Haarlinie unter **ihrer** Position (`InstanceEmbed.article_id` liefert die
  Zuordnung, sie war längst da). Der Einzel-Artikel-Auftrag ist dabei kein Sonderfall mehr,
  sondern ein Auftrag mit EINER Position – die getrennten Kacheln «Artikel»/«Menge» sind
  entfallen; ein Unter-Auftrag ohne Artikel zeigt titellos nur seine Instanzen. Eine Form für
  alle drei Fälle, umbrechend statt überlaufend (Mobile).
  (2) **Die verteilte Charge steht IM Standort-Container** (#147): «Standort» (Kette) und
  «Standort · verteilt» (Teilmengen) waren zwei Karten für dieselbe Frage – und die Kette
  darüber galt ohnehin nur für die **grösste** Teilmenge, war also bei einer verteilten Charge
  die halbe Wahrheit. Ab zwei Standorten ersetzen die Teilmengen die Kette an Ort und Stelle
  (Symbol · Halter · Objektnummer · Menge, Pille «verteilt · N Standorte» im Kachel-Kopf);
  `instance-locations.tsx` ist entfallen.
  (3) **Kein Footer mehr am Auftrag** (#140): Die Fussleiste trug drei Dinge, jedes hat einen
  besseren Ort – der **Fehler** steht zuoberst im Inhalt, direkt unter der Aktion, die ihn
  ausgelöst hat («Freigeben» sitzt im Kopf); der **Auto-Save-Status** war ohnehin schon als
  grüner Flash im Kopf; **«Abbrechen»** der Anlage steht bei den übrigen Aktionen. Der
  Anlage-Hinweis ist eine leise Zeile in der Karte, auf die er sich bezieht.
  (4) **Der Platzhalter sagt, was zu TUN ist** (#145): «Standort 100000292 scannen» statt
  «Aktueller Standort suchen» – die Zielnummer hängt der Scanner selbst an (`ScanStep.expected`),
  die Aufrufstellen nennen nur noch, WAS gescannt wird. Das Eingabefeld bleibt daneben
  unverändert benutzbar; die Platzhalter-Fläche wird lediglich zweckentfremdet.
  (5) **Die abgeleitete Klasse ist eine Empfehlung, die Wahl ist die Wahrheit** (#138): der
  Chip «Extern · Versand» beschrieb weiter die Ableitung, nachdem der Nutzer «Im Betrieb»
  gewählt hatte – jetzt richtet er sich nach der getroffenen Wahl.
  (6) Kleineres: ausgegraute Schritte behalten die **Farbe ihres Moduls** statt weiss zu
  werden (#139); der Einzel-Instanz-Scan-Knopf trägt dieselbe Stimme wie der grosse Knopf
  darunter (#144, schwarz statt blau); Vorschlagsliste im Scanner ohne Scrollbalken (#146);
  «Dokument in den Rahmen halten» (#143) und «geändert …» in der Angelegt-Kachel (#142)
  entfallen.
  *Zur Suchleistung (Frage in #146): das Filtern im Scanner ist eine lineare Suche über die
  Kandidaten mit Abbruch bei 6 Treffern – auch bei fünfstelligen Beständen unter einer
  Millisekunde je Tastendruck. Die Grenze liegt nicht dort, sondern im **Vorladen**: das
  Bewegungs-Panel holt für die freie Zielwahl einmal alle Personen + alle Instanzen
  (`api.getInstances()` ohne Begrenzung). Der Endpunkt kann bereits serverseitig suchen und
  paginieren (`search`/`limit`/`offset`), die Umstellung ist also eine Ein-Stellen-Änderung,
  sobald die Instanzzahl das rechtfertigt.*

- **Testnotizen-Runde 13 (weniger Wege, weniger Text, Notizen #148–#175, Migration `088`)**:
  (1) **Der Klick auf den Weg IST die Ausführung** (#152–#155, `deactivate-dialog.tsx`): Der
  Deaktivieren-Dialog liess erst eine Option wählen und darunter noch einmal bestätigen –
  zwei Schritte für EINE Entscheidung, dazu ein ×, ein «Abbrechen» und eine hervorgehobene
  Vorauswahl. Jetzt führen zwei gleichwertige Wege selbst aus («Deaktivieren» ↔ «Ersetzen»,
  #151 – derselbe prägnante Name, den der Artikel-Kopf ohnehin verwendet); geschlossen wird
  per Klick daneben oder `Esc`. Die **Wirkungsanalyse** bleibt (sie ist die Tatsachengrundlage,
  nicht die Erklärung), ihre Unterzeilen sind entfallen (#148–#150). Dialog-Rahmen und
  Wege-Knopf sind dabei zu `fields.tsx` gewandert (`Dialog`/`ChoiceButton`) – der
  Abweichungs-Dialog nutzte dieselbe Form schon, jetzt aus EINER Quelle.
  (2) **«Fixierter Standort» am Artikel ersatzlos entfernt** (#168, Migration `088`): sechs
  Spalten für GPS + reverse-geocodierte Adresse, rein deskriptiv – kein Bestands-Standort,
  keine Logik, gelesen nur von Formular, Lese-Ansicht und Kopierfunktion. Ein Artikel ist eine
  **Gattung**; einen Ort hat immer nur die **Instanz**. Damit ist auch `MapPicker` entfallen
  (Google Places bleibt für die Adressfelder).
  (3) **Die Bezugsquelle steht am Schritt. Punkt.** (#166): «Leer lassen, um den
  Artikel-Standard zu erben» zeigte auf einen Wert, den **niemand mehr setzen kann** – der
  Abschnitt «Beschaffung» in der Artikel-Spezifikation ist seit Runde 2 weg. Eine Option, deren
  Gegenstück unerreichbar ist, ist keine Option. Lieferant bzw. Webshop-Link sind jetzt
  Pflicht am Beschaffungs-Schritt; der Backend-Fallback auf den Artikel-Standard bleibt als
  **Lesepfad für Altbestand** (tolerant lesen, streng schreiben – wie bei den Standort-Typen).
  Dazu: der Hinweis in der Spezifikation entfällt (#169), das Lieferanten-Symbol ist ein
  **Gebäude** statt eines Lastwagens (#164 – gemeint ist die Firma, nicht der Transport), und
  der Chip-Hinweis unter «Für Lieferant sichtbar» ist weg (#165).
  (4) **Erfassungsfelder wählt man wie ein Prozessschrittmodul** (#172): eine Palette aus
  Symbolen, deren Name beim Hover aufklappt (`.erp-palette`) – erst WAS für ein Feld, dann die
  Konfiguration. Vorher: «Feld hinzufügen» → leere Zeile → Dropdown, also drei Handgriffe für
  eine Entscheidung, und eine Zeile, die vor der Wahl bereits «Soll-Ist» behauptete. Die Art ist
  danach das Symbol der Zeile, kein Feld mehr (umentscheiden = löschen + neu, wie beim Schritt).
  (5) **Die Abweichung gehört an den Schritt, den sie unterbrochen hat** (#175): Sie stand als
  Abzweig **unter** der Karte – was suggerierte, sie käme NACH dem Schritt, obwohl sie während
  seiner Ausführung gemeldet wurde. Eine Abweichung ist aber kein Knoten in der Reihenfolge,
  sondern die Aussage «hier ist etwas schiefgegangen» – und «hier» ist genau eine Karte. Sie
  steht jetzt **in** der Karte ihres Schritts (`origin_step_id`), als schmale Zeile unter dem
  Kopf. Eine Abweichung **ohne** Ursprungsschritt (an der Instanz gemeldet, oder bevor ein
  Schritt aktiv war) gehört keinem Schritt, sondern dem Auftrag – sie bleibt ein Abzweig, aber
  **vor** dem ersten Schritt. Damit ist die Liste in der Angehalten-Notiz überflüssig (#174),
  und deren Erklärabsatz ebenso (#173): «angehalten» sagt bereits, dass nichts geht.
  (6) **Schieberegler im Verkauf** (#159–#161): Status · Sichtbarkeit · Verfügbarkeit (und im
  gleichen Zug Art · Intervall · Abo-Typ) laufen über denselben `IconSwitch` wie am Bedarf und
  am Beschaffungs-Schritt – dass die Optionen einander ausschliessen, zeigt die Bewegung des
  Reiters statt ein zweiter Rahmen.
  (7) **Positionen dezenter** (#171): kein Zähler im Kopf (die Instanzen stehen darunter), das
  Wort «Instanz» nicht mehr in jeder Zeile (unter einer Position IST jede Zeile eine), und die
  Menge trägt kein zweites Fettgewicht neben dem Artikelnamen – in einer Zeile darf genau EINE
  Angabe laut sein.
  (8) **Freigeben steht bei den Aktionen** (#167): am Artikel wie am Auftrag unter dem Titel
  neben QR-Druck/Deaktivieren – rechts bleibt nur der Zustand. Nebeneffekt: die Aktion ist jetzt
  auf **jedem** Reiter erreichbar, nicht nur auf «Spezifikation».
  (9) Entfallen: Suchfeld im Artikel-Bestand (#157 – der Bestand EINES Artikels ist die kurze
  Liste; gesucht wird im Feed; revidiert #111), ⓘ bei «Inhalt»/«Preise» (#162/#163), «Noch kein
  Preis …» (#158), «verteilt · N Standorte» (#170 – die Zeilen sind die Aussage), «Nachfolger:»
  (#156).

- **Testnotizen-Runde 14 (ein Name, eine Bildsprache, Notizen #176–#193)**:
  (1) **Ein Datensatz zeigt Name · Objektnummer · Status – der TYP steht im Symbol** (#177,
  `services/orders.order_display_name` + `lib/record-name.ts`): Im Feed trug ein Auftrag als
  «Namen» das Wort **«Auftrag»** und eine Instanz das Wort **«Instanz»** – der Typ war in die
  Namensspalte gerutscht, und zwei Datensätze desselben Typs sahen identisch aus. Der Name
  wird jetzt **einmal im Backend** abgeleitet und als `OrderSummary.name`/`OrderResponse.name`
  geliefert (Feed und Detail lesen dasselbe Feld, können also nicht auseinanderlaufen):
  bewusst vergebener `title` ≻ Artikel ≻ erster Positions-Artikel «+N» ≻ «Auftrag» nur, wenn
  es wirklich nichts zu benennen gibt. Die Positions-Namen kommen über **eine** Batch-Abfrage
  (kein N+1). Frontend: `lib/record-name.ts` ist die EINE Ableitung für alle Typen und gibt
  `null` zurück, wenn ein Datensatz (noch) keinen Namen hat – den Platzhalter setzt die
  Oberfläche. Instanz-Detail und Auftrag-Detail lesen dieselbe Funktion; `orderTitle` in
  `order-detail.tsx` ist entfallen. Wächter `test_smoke.py:
  test_order_name_never_falls_back_to_the_type_word_when_there_is_a_name`.
  (2) **Gleiches Wort → gleiches Symbol** (#191): «Im Prozess» hiess am Auftrag `Hammer`
  (behauptete Fertigung – falsch für Beschaffung/Verkauf) und an der Instanz `Clock`
  (behauptete Warten – falsch für etwas, das läuft). Beide tragen jetzt `Loader`. Die Uhr
  bleibt, wo Warten die Aussage IST: «Angefragt».
  (3) **Der Beschaffungs-Ablauf spricht die Fluss-Sprache** (#182, `purchase-progress.tsx`):
  senkrecht, ein Knoten je Stufe an einer dünnen Linie – wie der Auftrags-Prozess. Der
  waagrechte Punkte-Stepper mit animiertem Lieferwagen ist weg (er brachte `@keyframes` in
  die Fläche); die **Lieferfrist ist keine Stufe, sondern eine Eigenschaft der Stufe
  «Bestellt»** und steht als schmaler Balken an ihrer Zeile.
  (4) **Beschaffungs-Panel entrümpelt**: ⓘ am Kopf (#192) und Statuswort in der Aktionszeile
  (#188 – der Zustand steht als Badge oben rechts) entfallen; Knöpfe in der Design-Sprache
  statt Blau (#187); «Webshop öffnen» ist ein Knopf mit Symbol statt blauer Fliesstext (#193);
  Beschriftungen nennen die Sache, der **Platzhalter** erklärt sie («Bestellsumme» +
  «ganze Menge, netto in CHF – z. B. 1250», #183–#186); «Artikel-Spezifikation (für Lieferant
  sichtbar)» → **«Spezifikation»** (#189).
  (5) **Die Abweichung hängt SEITLICH an ihrer Karte** (#178, `.erp-devbranch`): Runde 13
  hatte sie in die Karte gelegt – sie gehört aber zum Schritt, ist aber nicht Teil des Moduls
  (sie ist das, was es unterbrochen hat). Jetzt sitzt sie auf der **Höhe** der Karte, an einem
  kurzen Ast rechts daneben; unter 1180 px rutscht sie darunter.
  (6) **Versand ohne eigenen Kasten** (#179): die Transport-Wahl ist derselbe `IconSwitch` wie
  überall (die abgeleitete Empfehlung markiert sich mit einem Punkt – neues, generisches
  `mark`-Flag); der umgebende Rahmen ist entfallen (Panel im Modul im Fluss = drei Rahmen um
  dieselbe Sache).
  (7) **Positionen: Ausrichtung statt Schriftgrösse** (#176): EIN Raster über Positions- und
  Instanz-Zeilen (Nummer · Bezeichnung · Zahl/Zustand), Positionen durch Haarlinien getrennt,
  keine 18-px-Werte mehr (die Kachel erbt `TILE.v` bewusst nicht).
  (8) **Deaktivieren-Dialog: Folgen als Liste, Entscheidung an ihrer Zeile** (#180): die
  betroffenen Objektnummern sind **klickbar** (es sind Datensätze), «keine/keiner» steht leise
  da (dass nichts passiert, ist auch eine Antwort), und die einzige Zusatz-Entscheidung
  (Auslaufen lassen ↔ Abbrechen) sitzt als Schieberegler **direkt an der Zeile «Laufende
  Aufträge»** statt in einer zweiten Gruppe mit demselben Titel.
  (9) **Responsive** (#181): die Artikel-Spezifikation polstert mit `clamp` statt fixer 30 px
  (auf einem 360-px-Telefon frassen sie ein Sechstel der Breite), lange Werte brechen um.
  (10) **Multi-Site (#190) – Analyse, noch nicht gebaut.** Die Bewegungs-Logik ist bereits
  standort-agnostisch: ein Standort ist ein **Halter** (`user|instance|company`), und
  `logistics.classify_movement` entscheidet **adress-basiert** – «zwei interne Orte mit
  unterschiedlicher Adresse → Versand» ist heute schon der Mehr-Standort-Fall. Was fehlt, ist
  nur, dass `company` ein **Singleton** ist: `locations.company_location` liefert die eine
  Firma, `provisioning.target_for` löst `PROV_RECEIVING` darauf auf. Der Weg ist deshalb
  **kein Umbau, sondern eine Auflösung**: (a) `company_settings` von 1 auf n Zeilen (je
  Standort eine Objektnummer + Adresse, eine davon «Hauptsitz» für Rechnungen/Impressum);
  (b) der **Bedarf** bekommt einen Standort – am ehesten am Prozessschritt (`site_id`, leer =
  Standort des Auftrags), analog zur Bezugsquelle; (c) `target_for` löst `PROV_RECEIVING` auf
  **den Standort des Schritts** statt auf «die Firma» auf – ab da funktioniert die
  Bereitstellung unverändert weiter und erzeugt zwischen zwei Werken automatisch einen
  **Versand** statt einer innerbetrieblichen Bewegung, weil die Adressen sich unterscheiden.
  Genau das ist der Beweis, dass die Ableitung richtig gebaut ist: Multi-Site fällt aus der
  bestehenden Regel heraus, statt eine zweite zu brauchen.

- **Testnotizen-Runde 15 (der Name benennt die Sache, Notizen #194–#222, Migration `089`)**:
  (1) **Die abgeleitete Bereitstellung ist VORÜBERGEHEND ABGESCHALTET** (#204,
  `provisioning.AUTO_PROVISIONING = False`): Im Praxistest war der Bereitstellungs-Unter-Auftrag
  (a) im Ablauf nicht als Unter-Auftrag erkennbar – er sah aus wie ein regulärer Schritt des
  Hauptprozesses – und (b) seine Blockade traf nicht das Gewollte. Statt an der Oberfläche zu
  flicken, ist der **Auslöser** stillgelegt: es entsteht keine neue Bereitstellung, und eine
  vorhandene hält keinen Auftrag mehr an (sonst hinge ein Auftrag an einem Mechanismus fest,
  den es gerade nicht gibt). Bestehende Datensätze bleiben als Historie und lassen sich normal
  abschliessen/verwerfen. **EINE Konstante**, die ganze Ableitung (`target_for`, `misplaced`,
  `reconcile_to`, alle Tests) bleibt intakt – Wiedereinschalten ist ein Ein-Zeilen-Wechsel.
  Wächter `test_auto_provisioning_is_switched_off_at_exactly_one_place`.
  (2) **Der Name benennt die SACHE, nicht die Herkunft** (#205): ein Unter-Auftrag hiess
  «Bereitstellung für Beschaffung · Auftrag 100000500» – das beschreibt seine Entstehung, es
  ist kein Name. `order_display_name` bevorzugt jetzt Artikel ≻ Positionen ≻ **Artikel der
  fixierten Subjekt-Instanzen** ≻ `title` ≻ «Auftrag». Der Subjekt-Artikel kommt über EINE
  zusätzliche Batch-Abfrage im Feed bzw. aus dem bereits geladenen Instanz-Embed im Detail.
  (3) **«Zielbestand» ersatzlos entfernt** (#221, Migration `089`): zwei Zahlen für dieselbe
  Frage – `safety_stock` («ab wann nachbestellen?») und `reorder_target` («bis wohin?»), wobei
  die zweite fast immer leer blieb und die Nachbestellung dann ohnehin auf den
  Sicherheitsbestand auffüllte. Genau das ist jetzt die einzige Regel.
  (4) **Der Beschaffungs-Ablauf ist ein Prozess IM Prozess** (#194, `purchase-progress.tsx`):
  senkrechte Karten in der Modulfarbe, durch `Connector` verbunden – dieselben Bausteine wie
  der Auftrags-Fluss, nur eine Nummer kleiner; Start-/Endknoten entfallen (die Modul-Karte IST
  der Rahmen). Zustand ohne Wort, Lieferfrist als Balken **in** der Karte «Bestellt».
  (5) **Schieberegler, der nur die aktive Option ausschreibt** (#219/#220, `IconSwitch
  labelActiveOnly`): bei sechs Mengeneinheiten ringen sonst sechs Wörter nebeneinander um
  Aufmerksamkeit, obwohl nur eines gilt. Dafür wird der gleitende Reiter jetzt **gemessen**
  (ResizeObserver) statt als `100/N %` gerechnet – sonst stimmt er nicht mehr, sobald die
  Optionen unterschiedlich breit sind.
  (6) **Beschriftung nennt die Sache, der Platzhalter erklärt sie** (#207–#209, #211–#214,
  #216, #217): alle erklärenden Zeilen unter den Spezifikations-Feldern sind entfallen und in
  den Platzhalter gewandert («aufsteigend, mit «x» getrennt – z. B. 3x40x600»); «MOQ
  (Mindestbestellmenge)» → **Mindestbestellmenge**, «Meldebestand (Sicherheitsbestand)» →
  **Sicherheitsbestand**.
  (7) **Beschaffungs-Panel**: kein eigener Kopf mehr (#201 – die Modul-Karte heisst bereits
  «Beschaffung»), Lieferzeit ist **Pflicht** (#195 – ohne sie gibt es keinen Termin und keine
  Überfälligkeit), Tracking mit **Auto-Save** statt Speichern-Knopf und ohne «(optional)»
  (#198–#200), Rechenweg unter dem Stückpreis (#196) und der Kaufmännisch-Hinweis (#197)
  entfallen.
  (8) **Bewegen**: weder Überschrift «Versand» (#202 – die Karte heisst «Bewegen») noch der
  abgeleitete «Extern»-Chip (#203 – die getroffene Wahl steht direkt darunter; zwei
  gleichzeitig gültige Aussagen nebeneinander verwirren). Übrig bleibt die einzige Warnung mit
  Konsequenz: Gefahrgut.
  (9) **Der Schritt-Editor trägt die Farbe seines Moduls** (#222): man konfiguriert die Karte,
  die gleich im Fluss stehen wird – also sieht sie schon so aus (getöntes Symbol + Name als
  Kopf). (10) Feed etwas leichter (#206: 32-px-Symbol, halbfetter statt fetter Titel).

- **Testnotizen-Runde 16 (weniger Klicks, ein Kopf für alle, Notizen #223–#243)**:
  (1) **Die Paletten stehen offen** (#223, #229, #231 – «jeder Klick ist ein Klick zu viel»):
  die Prozessschritt-Module liegen sichtbar am Ende des Flusses (der Zwischenschritt
  «Prozessschritt hinzufügen» ist weg), die Erfassungsfeld-Palette ebenso, und die
  Ressourcen-Liste hält **immer eine leere Schlusszeile** bereit, die nachwächst, sobald sie
  einen Artikel bekommt. Leere Zeilen werden beim Speichern ohnehin verworfen.
  (2) **EIN Kopf für alle Datensatz-Fenster** (#242, `fields.DetailHeader`): Alle fünf
  Detail-Ansichten sahen sich ähnlich, aber keine zwei gleich – mal 26-px-Titel, mal 28,
  mal klebend, mal nicht; der **Benutzer** hatte sogar ein ganz eigenes Layout (44-px-Avatar,
  «Obj.-Nr.»-Block rechts). Die Anatomie ist jetzt verbindlich und spiegelt den Feed:
  Symbol · TYP (Eyebrow) · **Name** · Objektnummer mit den Aktionen · rechts der Zustand.
  Artikel/Auftrag/Instanz/Benutzer/Unternehmen teilen sie sich; die lokalen `H`/`S`-Kopfstile
  sind entfallen. Ein rundes Foto bleibt möglich (`avatar`-Slot).
  (3) **Der Anzeigename einer Person folgt EINER Regel** (#227): Firma → «Vorname Nachname»
  → E-Mail – genau wie `UserProfile.display_name` im Backend. Das Frontend wich hier ab und
  zeigte die Person, wo das Backend die Firma zeigte; beim Lieferanten ist die Firma der Name,
  unter dem man bestellt.
  (4) **Der Abweichungsauftrag ist überall als solcher gekennzeichnet** (#243): die
  Auftragsliste der Instanz zeigt jetzt Name · Objektnummer · Status **und** das gelbe
  Warnzeichen am Symbol – `InstanceOrderRef` trägt dafür `name`/`reason` (dieselbe
  Namens-Ableitung wie im Feed).
  (5) **Dokument-Modul lesbar** (#236, #241): eigene, kühl-graublaue Farbfamilie (die alte
  war exakt die Flächenfarbe des Fensters – die Karte verschwand darin), und die fertige
  Deklaration ist EINE Liste (Nr · Name · Aktion · Objektnummer) plus zwei
  Schlüssel-Wert-Zeilen statt fünf gestapelter Blöcke mit je eigener Überschrift.
  (6) **Die Sache beim Namen** (#228, #237, #238): «Erfassungsfelder», «Dokumentenfreigabe»,
  «Leseberechtigung», «Anerkennung» statt Fragen; die zugehörigen ⓘ entfallen (#235, #239).
  (7) **Ressource** trägt `Blocks` statt `Wrench` (#234): der Schritt setzt BEIDES ein –
  Material, das verbraucht wird, und Werkzeug, das genutzt wird; der Schraubenschlüssel ist
  innerhalb der Zeilen genau für den Werkzeug-Modus reserviert. Das Wort «Werkzeug» in der
  Zeile entfällt (#233 – das Symbol sagt es).
  (8) **Knöpfe in der Design-Sprache** (#230, #240): `erp-actbtn`/`erp-actbtn-primary` statt
  lokaler Stile; der Zurück-Kopf im Schritt-Editor ist entfallen (#226, #232 – «Abbrechen»
  ist der Weg heraus).
  (9) **Schieberegler hugged seinen Inhalt** (#224/#225): `labelActiveOnly` hat naturgemäss
  ungleich breite Optionen – der Regler ist darum `inline-flex` und füllt nicht mehr die
  ganze Spalte.

- **Testnotizen-Runde 17 (der Auftrag, der zuletzt arbeitet, gibt frei; Notizen #244–#262)**:
  (1) **Wer zuletzt an einer Instanz gearbeitet hat, gibt sie frei** (#262, `process.release_
  instances`): Freigegeben wurde bislang nur, was der **erzeugende** Auftrag hervorgebracht
  hat (`Instance.order_id`). Wird ein Auftrag abgebrochen und ein **Abweichungsauftrag** führt
  seine Instanzen fort, bleibt deren `order_id` beim abgebrochenen Original – sie wurden
  damit **nie** freigegeben: für immer «Im Prozess», unsichtbar für FIFO und Bestandszählung.
  Jetzt zählt beides: erzeugt-von **oder** Subjekt-von. Terminale/bewertete Teile bleiben wie
  bisher ausgenommen. Wächter `test_the_order_that_finishes_an_instance_releases_it`.
  (2) **Jedes Prozessschrittmodul ist universell einsetzbar** (#246): Verkauf/Verschrotten
  waren im Artikel-Prozess gesperrt, **«Sperren» stand in gar keiner Liste** und war damit
  nirgends wählbar. `STEP_TYPES_BY_OWNER` ist jetzt EINE Liste für Artikel und Auftrag – eine
  Sperre gegen selten sinnvolle Kombinationen kostet mehr, als sie nützt.
  (3) **Unter-Aufträge stehen an ihrem Schritt** (#259/#260): Nicht nur die Abweichung, auch
  der **Nachschub** merkt sich jetzt, aus welchem Schritt sein Bedarf stammt
  (`supply._blocked_step_id` → `orders.origin_step_id`) und erscheint als Pille am Ast neben
  der Modul-Karte. Die separate «Nachschub»-Liste im Auftrag ist entfallen – sie sagte
  dasselbe noch einmal und verschwieg, WO der Bedarf entstand.
  (4) **Der Beschaffungs-Ablauf trägt seine Eingaben in der aktiven Stufe** (#248,
  `PurchaseProgress renderActive`): Bestellsumme, Lieferzeit, Zahlungsziel und die Aktion
  sitzen in der Karte der Stufe, die gerade dran ist – genau wie ein Schritt-Panel in seiner
  Modul-Karte. Der fachliche Zustand («Angefragt») wanderte in den **Modul-Kopf** des Flusses
  (#247, `FlowCard badge`), wo man ihn ohne Öffnen sieht.
  (5) **Zahlenfelder ohne Minus** (#249/#250): Bestellsumme/Lieferzeit/Zahlungsziel laufen
  über `numericOnly` – eine negative Bestellsumme gibt es nicht.
  (6) **Der Lastwagen fährt wieder** (#251, `.ix-truck`/`.ix-road` in `globals.css`): er steht
  auf dem **echten** Fortschritt und wippt, die gestrichelte Strasse läuft ihm entgegen;
  `prefers-reduced-motion` stellt beides still. Die `@keyframes` liegen im Stylesheet, nicht
  als `<style>` in der Fläche (das war die Kritik aus #182).
  (7) **Ein Erfolg, eine Meldung** (#253): der Scanner meldete den Treffer doppelt – grüner
  Rahmen UND grüne Textpille. Geblieben ist der Rahmen; Text gibt es nur beim Fehlschlag,
  wo der GRUND zählt.
  (8) **Verschrotten/Sperren verlangen einen Grund** (#255): warum etwas ausgeschleust wurde,
  ist die eigentliche Information des Schritts – ohne sie bleibt im Nachhinein nur «weg». Der
  Schritt **deklariert** die Pflicht (wie die Datenerfassung ihre Felder); das Scannen ist die
  ruhige schwarze Hauptaktion (#256), rot bleibt dem Vollzug vorbehalten.
  (9) **«Es fehlt» statt eines Absatzes** (#257/#258): die Unterdeckungs-Notiz nennt Menge,
  Artikel und Objektnummer – der Erklärtext wiederholte nur, was Titel und Zeile ohnehin
  sagen; der Kasten ist zur Haarlinie geworden (sie sitzt IM Modul).
  (10) Kleineres: Tracking-Platzhalter «Tracking-Nummer» (#252). *#244/#245 (Unternehmens-Kopf
  und Status-Farbe) waren mit dem gemeinsamen `DetailHeader` aus Runde 16 bereits erledigt.*

- **Testnotizen-Runde 18 (Ausschleusen, eine Spezifikations-Karte, Notizen #263–#277)**:
  (1) **«Verschrotten» und «Sperren» sind EIN Modul «Ausschleusen»** (#277): Beide beantworten
  dieselbe Frage – *dieses Teil darf so nicht weiter* – und unterscheiden sich nur in der
  **Endgültigkeit**. Zwei Paletten-Einträge zwangen zu dieser Entscheidung, bevor man den
  Fall überhaupt beschrieben hatte. Jetzt gibt es einen roten Eintrag (`PackageX`); die
  Wirkung wählt ein `IconSwitch` **im Editor** (Verschrotten = endgültig, standortlos ↔
  Sperren = aufhebbar, bleibt liegen), und der **Grund ist bei beiden Pflicht** (#255) –
  warum etwas ausgeschleust wurde, ist die eigentliche Information des Schritts. Datenmodell
  unverändert: es bleiben zwei Schritttypen mit zwei Polaritäten (`DECREASE` ↔ `NEUTRAL`),
  nur die Oberfläche fasst sie zusammen. **Die Labels stehen dabei weiter in der Registry**
  (`domain/event_types.py`) – der Mirror-Test hat den Alleingang im Frontend prompt gemeldet,
  also sind auch «Beschaffen» (#274) und «Ausschleusen» dort umbenannt.
  (2) **Die Auftragsspezifikation ist EINE Karte** (#267, `fields.SPEC` + `fields.ReadField`):
  Sie stand als drei lose Kacheln nebeneinander, während der Artikel seine Angaben auf EINEM
  Blatt zeigt – zwei Formensprachen für dieselbe Sache. Karte, Werteraster und Lesefeld sind
  aus `article-detail.tsx` ins gemeinsame Vokabular gewandert; `OrderPositions` rendert
  seitdem als Lesefeld (volle Breite) statt als eigene Kachel, sonst wäre es eine Karte in
  der Karte. `specGrid`/`SpecTile` sind entfallen.
  (3) **Objektnummern ohne Tausender-Trennung** (#263, `lib/utils.formatObjectId`): eine
  Objektnummer ist eine **Kennung**, keine Menge – `100'000'451` liest sich als Betrag. EINE
  Formatierung (9-stellig, führende Nullen), die alle Ansichten teilen.
  (4) **Der Kopf ist überall derselbe – auch im Detail** (#264/#268): `DetailHeader` rendert
  die Status-Badge jetzt **selbst** (`status`-Prop), statt sie den Aufrufern zu überlassen;
  damit kann keine Ansicht mehr eine eigene Grösse wählen (die Instanz hatte eine grössere
  Pille). Der `right`-Slot trägt nur noch Zusätze (Speicher-Anzeige, «Abbrechen»).
  (5) **Der Beschaffungs-Ablauf benennt Tun und Zustand getrennt** (#271/#272/#275): der
  **aktive** Knoten trägt das Verb («Bestellen»), die erreichten Stufen den Zustand
  («Bestellt») – vorher hiess dieselbe Stufe beides. Wer/Wann steht im Hover (#276), der
  Arbeitsbereich der aktiven Stufe ist eine weisse Fläche im Modulrahmen (#273).
  (6) **Erfolgsmeldungen entfallen** (#266): dass ein Schritt erledigt ist, sagt seine Karte
  im Fluss (Symbol + Wer/Wann im Hover) – ein grünes Banner im Panel sagte es ein zweites Mal.
  (7) Kleineres: Menge bei **jeder** Instanz (#265 – Einheitlichkeit statt «mal hier, mal
  dort»), Startknoten auch beim leeren Prozess (#269), «Prozess des Artikels» entfällt (#270).

- **Unterdeckung: EINE Frage, DREI Antworten – und die Abweichung hält nichts mehr an**
  (Juli 2026, `services/recovery.py`, `process.deviated_instance_ids`): Praxistest an einem
  Erzeugungsauftrag (Beschaffung → interne Bewegung → Abweichung an EINER Instanz) zeigte,
  dass beide bisherigen Wege am Fall vorbeigingen: *Aus Lager decken* schickt ein fertiges
  Teil noch einmal durch den Prozess, und *Nachschub* lässt vier Instanzen warten, bis ein
  kompletter Unter-Auftrag durchgelaufen ist. Es fehlte die ehrlichste Antwort: **der
  Auftrag wird mit weniger fertig.**
  **(1) Eine Abweichung nimmt ihr Stück HERAUS, statt den Auftrag anzuhalten.** Früher
  pausierte JEDE offene Abweichung den GANZEN Eltern (`_is_paused_by_deviation`, dazu ein
  `_assert_not_paused`-Wächter an allen zwölf Ausführungs-Endpunkten) – unabhängig davon,
  wie viele Instanzen betroffen waren: ein schlechtes von fünf Stück legte die anderen vier
  still. Das war ein **zweiter** Mechanismus für etwas, wofür es längst eine präzise Sprache
  gibt – die **Unterdeckung**. Ein Stück in Klärung ist weder verloren noch gesichert, es ist
  **fehlend**: `deviated_instance_ids` nimmt es aus «Gesichert» heraus, der Schritt meldet
  «Es fehlt 1 Stk», der Rest läuft weiter. Der Schutz, für den die Pause gedacht war – *eine
  Sendung darf nicht teil-versendet werden* –, bleibt **abgeleitet statt deklariert**:
  Verkauf und Versand sind Subjekt-Schritte und blockieren bei einer Fehlmenge ohnehin. Damit
  ist es **eine Regel weniger**, nicht eine mehr: `_is_paused_by_deviation`, `_assert_not_paused`
  und `OrderResponse.paused` sind ersatzlos entfallen. Gegenstück: `release_instances` gibt
  nicht frei, was in einer offenen Abweichung steckt (der Eltern darf jetzt abschliessen,
  während die Klärung läuft – freigegeben wird vom Auftrag, der zuletzt daran arbeitet).
  **(2) Die Unterdeckung stellt genau EINE Frage** – *was soll mit der Fehlmenge geschehen?* –
  mit drei Antworten: **Wartet** = kein Knopf, sondern ein **Zustand** (`OrderStepInfo.
  waiting_for` – ist die Menge in einer offenen Abweichung oder einem laufenden Nachschub
  gebunden, ist die Entscheidung getroffen; die frühere Trennung «Nachschub läuft» ↔
  «Abweichung offen» ist EIN Feld geworden); **Ersetzen** = EIN Weg statt zweier Knöpfe
  (`POST /orders/{id}/cover` → erst freier Lagerbestand FIFO bzw. gezielt gewählte Instanzen,
  Rest per Nachschub – woher der Ersatz kommt, ist eine Verfügbarkeitsfrage, keine zweite
  Entscheidung; `/supply` + `/cover-stock` sind darin aufgegangen); **Menge bestätigen** =
  neu (`POST /orders/{id}/confirm-quantity`, `recovery.confirm_quantity`): das Soll sinkt auf
  das Gesicherte (5 bestellt, 1 in Klärung → 4 bestellt), der Schritt ist frei, der Auftrag
  läuft normal zu Ende. **Geld bleibt ehrlich:** eine bereits **bezahlte** Verkaufsposition
  lässt sich so NICHT kürzen (409) – dafür ist die Retoure/Gutschrift da (`sale`-Kredit-Modus
  + Stripe-Refund). Damit ist auch das alte «Menge reduzieren»-TODO sauber geschlossen.
  Wächter: `test_a_deviation_takes_its_instances_out_instead_of_pausing_the_order`,
  `test_shortfall_is_one_question_with_three_answers`, `test_waiting_is_a_state_not_a_button`,
  `test_a_shortfall_blocks_only_the_step_that_needs_it`.
  *Bewusst NICHT gebaut: die **Lieferanten-Reklamation** (`purchase` im Kredit-Modus, analog
  zum `sale`-Modul) – die Gegenrichtung des Einkaufs bleibt offen; und «ab Lager gedeckte
  Teile überspringen erledigte Schritte» (ausdrücklich verworfen: ein Schritt wirkt auf die
  Instanzen seines Auftrags, eine Ausnahme je Herkunft wäre eine zweite Regel).*

- **Testnotizen-Runde 19 (die Entscheidung bleibt am Schritt, Notizen #279–#286)**:
  (1) **Was entschieden wurde, steht im Ablauf** (#281, `OrderStepInfo.resolutions`): Dass
  eine Fehlmenge **ersetzt** oder die **Menge angepasst** wurde, ist die eigentliche
  Geschichte des Auftrags – ohne Spur sah man später nur noch das Ergebnis («läuft») und
  nicht, wie es dazu kam. Die Spur ist **kein neues Feld**, sondern der **Event-Strom**:
  `recovery._record_at_step` hängt jeder Entscheidung die Schritt-id an, `orders.
  _fill_step_resolutions` liest sie je Schritt zurück, der Fluss zeigt eine Zeile
  («Menge angepasst 5 → 4», «1 ab Lager ersetzt», Wer/Wann im Hover) – auch dann noch, wenn
  der Schritt längst wieder läuft. Die Frage «welcher Schritt vermisst diesen Artikel?» hat
  damit zwei Nutzer (Nachschub-Ursprung + Deckungs-Spur) und liegt an EINER Stelle
  (`process.blocked_step_for_article`, aus `supply.py` herausgezogen).
  (2) **«Ohne Ersatz weiter» statt «Menge bestätigen»** (#280): der alte Name sagte, was das
  System tut, nicht was der Mensch entscheidet – und der Gegensatz zu «Ersetzen» ist eben:
  gar nicht ersetzen.
  (3) **Eine Objektnummer sieht überall gleich aus** (#282, `ObjId`): sie erbte die
  Schriftgrösse ihrer Umgebung und wurde im 15,5-px-Lesefeld der Auftragsspezifikation zur
  lautesten Angabe der Zeile – obwohl sie eine **Kennung** ist, keine Aussage. Jetzt feste
  12,5 px/600, tabellarisch (Fortsetzung von #263); die Positions-Aufstellung beginnt
  wieder bei der normalen Lesegrösse.
  (4) **Zustand nur, solange er etwas sagt** (#279): der fachliche Zwischenstand im
  Modul-Kopf (Beschaffung/Verkauf) entfällt, sobald der Schritt erledigt ist – dass er durch
  ist, sagt der Haken daneben, «Geliefert» stünde als zweites Wort für dieselbe Aussage.
  (5) **Abweichungs-Dialog kurz und prägnant** (#284, `ChoiceButton` mit Symbol):
  «Läuft weiter – nur das betroffene Stück wird herausgenommen» ↔ «Abbrechen – endgültig,
  nur die Abweichung läuft weiter». Der alte Untertitel behauptete noch die Pause, die es
  seit der Unterdeckungs-Runde nicht mehr gibt. Die lokale Dublette von `ChoiceButton` in
  `order-detail.tsx` ist im gemeinsamen Vokabular aufgegangen.
  (6) **Der Kopf skaliert nicht mehr** (#286, `fields.HeaderAction`): die Status-Aktion war
  32 px hoch neben 28-px-Symbolknöpfen – die Zeile wuchs in dem Moment, in dem «Freigeben»
  erschien, und schrumpfte wieder, sobald es wegfiel. Artikel und Auftrag hatten dieselbe
  Zeile zweimal ausgeschrieben; jetzt eine Stelle, exakt 28 px.
  (7) Kleineres: Menge bei **jeder** Instanz auch im Artikel-Bestand (#285, `instanceLabel`
  – Einheitlichkeit statt «bei Chargen ja, bei Einzelteilen nein»); Label «Wirkung» im
  Ausschleusen-Editor entfällt (#283 – die beiden Optionen sagen es selbst).
- **Mehrstandort – Schritt 1: «das Unternehmen» wird zu «die Standorte»** (Juli 2026,
  Migration `090`, Variante A): Ein Betrieb kann Aussenstellen haben. Umgesetzt ist bewusst
  nur das **Fundament**; Bestand, Rechte und Bedarf bleiben unverändert (siehe unten).
  **Eine Spalte, keine neue Tabelle.** `company_settings` war ein Singleton (`id == 1`) und
  trägt jetzt n Zeilen – eine je Standort. Das ist deshalb so billig, weil ein Standort im
  Modell längst existierte: `instances.location_type='company'` zeigt auf eine **Objektnummer**,
  und `locations.location_label`/`location_chain` lösen sie darüber auf. Es gab bloss immer
  nur eine davon.
  **Was einmal gilt und was je Standort gilt, ist eine Frage der Schreibstelle, nicht der
  Tabelle:** der **Hauptsitz** (`is_primary`, partieller Unique-Index = genau EINER) trägt die
  **Rechtsidentität** (UID/MWST/HR/Aktienkapital/IBAN/Rechtsform) und die **Systemkonfiguration**
  (Stripe, Shop-Währungen, Rechtstexte, Plausible, Maps); **jeder** Standort trägt Name,
  Anschrift, Kontakt (`sites.SITE_FIELDS`, gespiegelt von `schemas/admin.SiteBase` – der
  Abgleich ist getestet). Ein Nebenstandort kann eine UID gar nicht erst annehmen; sonst
  stünde dieselbe Angabe an n Stellen.
  **Die eine Auflösung ist `services/sites.py`** – in zwei Formen derselben Regel (wie
  `inventory.is_in_stock` neben `in_stock_clauses`): `primary()` schreibend (legt an, vergibt
  die Objektnummer), `find_primary()` **rein lesend** – Pflicht in fremden Transaktionen
  (Preis-Pipeline, Shop-Konfig, Provider-Wahl, PDF-Briefkopf), wo ein `commit` die halbfertige
  Arbeit des Aufrufers festschreiben würde. `admin.get_or_create_settings` delegiert nur noch
  dorthin, **keine Aufrufstelle ändert sich**.
  **Der eigentliche Bug, den das behebt:** zehn Stellen holten sich «die Firma» selbst – mal
  `id == 1`, mal ein blosses `.first()`. Bei einer Zeile war beides dasselbe; ab der zweiten
  ist `.first()` eine **willkürliche Wahl**. Am schwersten wog `logistics.target_address`: sie
  hätte JEDEM Standort-Ziel die Adresse des Hauptsitzes gegeben – Quelle und Ziel sähen für
  `classify_movement` gleich aus, und ein Transport Werk A → Werk B ginge still als
  «innerbetrieblich» durch statt als Versand mit Tarif und Label. Sie löst jetzt über die
  **Objektnummer** auf; ein Wächter hält das fest (`tests/test_sites.py`).
  **Damit fällt Mehrstandort aus der bestehenden Regel heraus, statt eine zweite zu brauchen:**
  der Zweig «zwei interne Orte mit **unterschiedlicher** Adresse → Versand» (ADR 005) war
  gebaut und toter Code – er ist jetzt lebendig. Gegen echtes Postgres verifiziert: Hauptsitz →
  Werk Nord = `outside` (Empfehlung Paket), Hauptsitz → Hauptsitz = `inside`. Ein Standort
  **ohne** Anschrift ist gültig, aber logistisch stumm (bleibt innerbetrieblich) – das Detail
  sagt es (`SiteResponse.has_address`), statt es raten zu lassen.
  **Nummernkreis unverändert global** – die Objektnummer ist eine *Identität*, kein
  Belegnummernkreis; je-Standort-Kreise würden `resolve_object_type`, den QR-Scan und
  `references.object_references` (globale Eindeutigkeit) zerlegen. Ein neuer Standort bekommt
  eine ganz normale Nummer aus `object_id_seq` und ist damit sofort **Halter**.
  **Migration ohne Datenumzug:** die vorhandene Zeile *wird* der Hauptsitz, ihre Objektnummer
  bleibt gültig – keine Zeile in `instances`/`orders`/`shipments` wird angefasst.
  **Oberfläche:** je Standort eine Feed-Zeile (Typ `organization`, admin-only wie bisher),
  «+ Standort» im FAB (nur Admin), und EIN Detailfenster in zwei Ausprägungen – Hauptsitz mit
  Rechtsidentität/Bank/MWST/Integrationen, Nebenstandort mit Name/Anschrift/Kontakt.
  Endpunkte `GET/POST /admin/sites`, `PATCH /admin/sites/{object_id}` (alle **Admin**).
  *Bewusst NICHT gebaut (kommt in späteren Schritten):* **standort-getrennter Bestand** – FIFO
  bleibt EIN Topf über alle Standorte (liegt das Teil falsch, ist das ein Transport, kein
  Fehlbestand); **Standort-Rechte** – Personal sieht weiterhin alles, der Standort ist
  Anzeige, keine Berechtigungsgrenze; **`site_id` am Prozessschritt/Auftrag** (der Bedarf
  kennt seinen Standort noch nicht, Wareneingang und Lieferadresse sind fest der Hauptsitz);
  **Absender je Standort** auf Versandbeleg und Briefkopf (die *Klassifikation* liest den
  echten Standort, der *Beleg* nennt die Firma); **Standort löschen** (bearbeiten genügt
  vorerst – ein Standort mit Bestand bräuchte sonst eine eigene Wirkungsanalyse).
  - **⚠ Vorfall beim ersten Deploy (und die Lehre daraus).** Der Mehrstandort-Deploy hat
    das ERP und die öffentliche Website lahmgelegt: der Unternehmens-Datensatz war weg,
    **kein einziger Instanz-Datensatz** liess sich laden, dazu Impressum, Shop-Konfiguration
    und Shop-Produkte. Ursache war **nicht** die Fachlogik, sondern eine Deploy-Mechanik,
    die dieses Projekt längst kennt und für die es eine benannte Vorrichtung gibt:
    **`start.sh` startet uvicorn ausdrücklich auch dann, wenn Alembic scheitert**
    («schema fix will run in lifespan»). Das Lifespan-Sicherheitsnetz
    (`main._COLUMN_SAFETY_NET`) ist dafür der vorgesehene zweite Weg – und dort fehlte
    `company_settings.is_primary`. Migration 090 lief nicht, das Modell kannte die Spalte
    trotzdem, und damit endete **jede** Abfrage auf `company_settings` in einem 500.
    Dass das so weit trägt, liegt an der Rolle der Tabelle: sie wird nicht nur im Admin
    gelesen, sondern über `locations.location_label` von **jedem Standort-Label** (also
    dem ganzen Instanz-Feed) und von **unauthentifizierten** Endpunkten (Impressum,
    Shop). Eine fehlende Spalte hier ist kein ERP-Schluckauf, sondern ein Komplettausfall.
    **Drei Korrekturen, alle strukturell:** (1) `is_primary` **und** das ebenso fehlende
    `legal_documents` (Migration 057 – dieselbe Bombe, nur noch nicht gezündet) stehen im
    Sicherheitsnetz; ein Daten-Fix (`_COMPANY_DATA_FIXES`) setzt danach genau **einen**
    Hauptsitz und legt den partiellen Unique-Index an – ohne ihn trüge nach dem
    `ADD COLUMN DEFAULT false` **keine** Zeile die Markierung und die Firma erschiene als
    blosser «Standort» ohne Rechtsidentität (genau das zweite gemeldete Symptom).
    (2) **Migration 090 ist idempotent** – repariert das Netz das Schema, versucht Alembic
    090 beim nächsten Deploy erneut; ohne Wiederholbarkeit liefe sie auf «column already
    exists» auf, bliebe für immer auf 089 stehen und würde **jede künftige Migration**
    blockieren. (3) Der Wächter `test_every_company_settings_column_is_in_the_lifespan_
    safety_net` leitet die Erwartung aus dem **Modell** ab statt aus einer gepflegten
    Liste: was nicht im Initial-Schema steht, muss im Netz stehen. Er hat `legal_documents`
    sofort mitgefunden.
    **Verifiziert, nicht vermutet:** der Vorfall ist gegen echtes PostgreSQL reproduziert
    (Spalte gezogen → dieselben 500er) und die Heilung bewiesen (echter Lifespan über die
    kaputte Datenbank → alle zehn Endpunkte wieder 200, Hauptsitz markiert,
    Rechtsidentität sichtbar, zweiter Hauptsitz von der DB abgewiesen); dazu
    `alembic stamp 089 && upgrade head` auf dem bereits reparierten Schema plus ein
    downgrade/upgrade-Zyklus.
    **Regel für künftige Spalten:** eine neue Spalte auf einer **bestehenden** Tabelle ist
    erst fertig, wenn sie in der Migration UND im Lifespan-Sicherheitsnetz steht. Die
    Migration ist die Wahrheit, das Netz der zweite Weg – und beim Ausfall zählt nur der
    zweite Weg.

- **Mehrstandort → Mehr-Gesellschaften: EIN gleichrangiger Datensatztyp «Unternehmen»**
  (Juli 2026): Die kurzlebige «Hauptsitz + kastrierte Standorte»-Zwischenstufe ist
  aufgelöst. Jetzt gibt es genau **einen** Datensatztyp (`company_settings`, Feed
  `organization`); **jede Zeile ist eine vollständige juristische Einheit** – eigene
  Objektnummer, eigene Rechtsidentität (die US-Gesellschaft hat ihre **eigene** EIN/
  Steuer/Bank). Keine Zeile ist einer anderen untergeordnet.
  **Warum die Kehrtwende:** Aussenstellen in anderen Ländern sind keine blossen Adressen –
  andere Rechtsform, Steuer, Währung, eigener Rechnungs-Aussteller. «Nur der Hauptsitz
  trägt Identität» war damit genau verkehrt; jede Gesellschaft trägt ihre eigene. Das ist
  zugleich **flacher** (eine Klasse statt Kaste) – exakt die Komplexitätsreduktion, die
  gefordert war. **Hartes No-Go bleibt gewahrt:** ein ERP, eine Website, ein Produktkatalog,
  ein Login – mehrere Gesellschaften sind **Daten in diesem einen System**, nie ein zweites
  von irgendwas.
  **Der «Betreiber» ist abgeleitet, kein Flag** (`sites.operator`/`find_operator` = das
  **älteste** Unternehmen, kleinste `id`). Er vertritt die eine Website nach aussen
  (Impressum, Rechtstexte, Fallback) und trägt die **Plattform-/Systemkonfiguration**
  (`sites.PLATFORM_FIELDS`: Stripe, Shop-Währungen, `legal_documents`, Plausible, Maps) –
  die gibt es genau EINMAL. Das frühere `is_primary` ist **aus dem Modell entfernt** (es
  stellte eine Zeile über die anderen und war die Ursache des Deploy-Ausfalls); die
  DB-Spalte bleibt vorübergehend (Migration 091 dropt sie im Folge-Deploy), SQLAlchemy
  ignoriert die nicht gemappte Spalte, das Lifespan-Netz hält sie für die während des
  Cloud-Run-Rollouts noch laufende Vorgänger-Revision intakt – **gegen echtes Postgres
  verifiziert** (neue Revision fehlerfrei auf DB MIT `is_primary`; neue Zeilen bekommen
  den DB-Default `false`, die Alt-Revision bleibt konsistent).
  **Reichweite je Feld, nicht je Rang** (`services/sites.py`): `ENTITY_FIELDS` (Name,
  Anschrift, **Rechtsidentität**, Bank, MWST) sind an JEDEM Datensatz editierbar (`PATCH
  /admin/companies/{object_id}`); `PLATFORM_FIELDS` ignoriert `apply_update` bewusst – sie
  laufen nur über die Systemkonfiguration (`PATCH /admin/settings`, trifft den Betreiber),
  damit dieselbe Angabe nicht an zwei Stellen editierbar ist. Endpunkte: `GET/POST
  /admin/companies`, `GET/PATCH /admin/companies/{object_id}` (Admin). Der frühere
  `/admin/sites` + die `Site`-Schemas/-Typen sind entfallen; `SiteResponse.is_primary` →
  `CompanySettingsResponse.is_operator`/`has_address` (beide **abgeleitet**, kein Rang).
  **Impressum: global, wechselt NICHT nach Land** – der Betreiber der EINEN Website ist die
  ausweisende Rechtsperson (`/admin/settings/public` = ältestes Unternehmen); nur die
  **Rechnung** hat je nach Warenherkunft einen anderen Aussteller (kommt als Folgeschritt).
  **Oberfläche:** `organization-detail.tsx` rendert für JEDE Gesellschaft denselben vollen
  Feldsatz (kein `isPrimary`-Zweig mehr); `/admin/einstellungen` ist auf **reine
  Plattform-Konfiguration** eingedampft (Entitäts-Felder werden am Datensatz gepflegt,
  nicht doppelt); FAB «+ Unternehmen» (Admin). Am Betreiber ein **dezenter Hinweis**
  «Betreiber der Website» + die Konzern-Kosten (Gruppen-Kennzahl) – Fakt, kein Rang.
  Wächter `tests/test_sites.py` (u. a. `test_every_company_carries_its_own_legal_identity`,
  `test_platform_config_is_never_editable_per_company`,
  `test_operator_is_derived_from_age_not_from_a_flag`).
- **Gesellschaften – vollständig im ERP, Betreiber wählbar, Währung je Gesellschaft**
  (Juli 2026, Migration `091`): Drei Ausbauten am gleichrangigen Unternehmens-Datensatz.
  **(1) Der «Betreiber» ist WÄHLBAR** (`is_operator`, partieller Unique-Index = genau EINE
  Gesellschaft trägt den Titel; `sites.set_operator` nimmt ihn allen anderen ab). Vorher
  abgeleitet (ältestes) – der Nutzer wollte ihn setzen können. `find_operator` liest die
  gewählte Zeile, **tolerant mit Alters-Fallback** (keine Markierung → ältestes; so nie «kein
  Betreiber»). `is_primary` ist damit endgültig weg – Migration 091 seedet `is_operator` aus
  ihm (der bisherige Betreiber bleibt), dann Drop von Spalte+Index; das Lifespan-Netz führt
  `is_primary` im **Drop**-Netz und `is_operator`/`currency` im **Add**-Netz (belt-and-
  suspenders, falls Alembic scheitert). **Endpoint** `POST /admin/companies/{object_id}/operator`.
  Der Betreiber trägt Impressum + Systemkonfiguration; ein Wechsel zieht sie mit (die eine
  Website hat einen Absender).
  **(2) Systemkonfiguration ins ERP geholt, `/admin/einstellungen` GELÖSCHT.** Die Seite war
  nicht verlinkt (nur per URL erreichbar) – das Unternehmen wird ausschliesslich im ERP
  gepflegt. Die Plattform-Konfiguration (Stripe/Shop/Rechtstexte/Plausible/Maps) sitzt jetzt
  als Reiter **«System»** am **Betreiber**-Datensatz (nur dort – es gibt sie genau einmal;
  `SystemConfigSection` wiederverwendet, in einen `QueryClientProvider` gehängt). Route +
  Impressum-Fallback-Link entfernt.
  **(3) Währung je Gesellschaft** (`company_settings.currency`, ISO-3, Entitäts-Feld): **auto
  aus dem Land** vorbelegt (`sites.currency_for_country`: US→USD, DE→EUR, CH→CHF; unbekannt→
  CHF). Beim Anlegen gesetzt; im Formular beim Länderwechsel **vorgeschlagen** (nicht erzwungen,
  kein Überschreiben). Das ist die **Grundlage** für «ein Preis, überall in Landeswährung» –
  die Preis-Eingabe/-Anzeige-Mechanik (Katalogpreis bleibt EIN kanonischer CHF-Betrag, Ein-/
  Ausgabe über den FX-Anker `services/fx.get_rate`) ist der **nächste** Deploy (Geldpfad
  bewusst isoliert).
  **Verifiziert gegen echtes Postgres:** Migration 091 vom echten 090-Zustand (is_operator vom
  bisherigen Betreiber übernommen, currency default, is_primary weg, zweiter Betreiber vom
  Unique-Index abgewiesen) + idempotent; Betreiber-Wechsel (US wird Betreiber, Impressum folgt,
  CH verliert Titel, DB weist zwei Betreiber ab); Währung auto (US→USD); **Rollout über das
  Lifespan-Netz** (DB im 090-Zustand → Netz ergänzt is_operator/currency, dropt is_primary,
  seedet Betreiber → alle Endpunkte 200). Wächter `tests/test_sites.py`
  (`test_operator_is_chosen_with_an_age_fallback`, `test_operator_is_editable_and_exactly_one`,
  `test_currency_is_a_per_company_field_derived_from_country`,
  `test_is_primary_is_dropped_everywhere_not_re_added`).
  **Nächste Schritte (definiert):** (4) **Anzeige in Landeswährung + EINE Kursquelle → UMGESETZT**
  (siehe eigener Bullet «Währung: EINE Kursquelle» unten). (5) **Fakturierende
  Gesellschaft aus dem Warenort ableiten** (wie ADR-005-Versand) → Beleg zeigt ihre Identität;
  **Belegnummer bleibt global** (rechtlich zulässig); Zahlungskonto je Gesellschaft mit Rückfall
  auf EIN geteiltes Stripe-Konto (US-Konto erst bei echter US-Gründung – dann nur ein Key am
  Datensatz). (6+) Steuerregime je Gesellschaft (CH live, US-Stub), Intercompany-Verkauf
  (= `sale` mit interner Partei), Konsolidierung.
- **Währung: EINE Kursquelle (unser `fx`-Anker), Adaptive Pricing AUS** (Juli 2026, Geldpfad,
  kein Schema-Migrations-Bedarf – JSONB-Zeile): Der Kunde sah im Shop z. B. € 11.80 (unser
  Tageskurs), Stripe belastete aber € 11.82 – denn der Checkout schickte **CHF** und liess
  **Stripe Adaptive Pricing** mit STRIPES Kurs in die Lokalwährung umrechnen. Das waren **zwei
  Kursquellen**. Jetzt berechnet `selling._resolve_line` je Position den Betrag in der
  **Präsentationswährung** über dieselbe Pipeline `pricing.price_view_for` (unser `fx`-Anker,
  gepinnt + „schön" gerundet) und legt ihn als `presentment_currency`/`presentment_amount` auf
  die `CheckoutIntent`-Zeile; `stripe_provider._line_item` übergibt **genau diese Währung + diesen
  Betrag** an Stripe (Adaptive Pricing bewusst **AUS**, `docs/stripe-setup.md`). Damit ist
  **Anzeige == Belastung** per Konstruktion. `base_amount_chf` bleibt die **kanonische** CHF-Grösse
  (Reservierung/Report/anteilige Erstattung – währungsunabhängige Verhältnisse); die Kasse belastet
  die Präsentationswährung, das reale Settlement kommt über `_apply_stripe_snapshot` (liest
  `settlement.currency` schon immer dynamisch) auf `sales.currency` zurück → «Meine Bestellungen»/
  Refund folgen **automatisch** (Refund proportional über den Snapshot, währungsunabhängig).
  Der Client kann **keinen Betrag vorgeben**: `checkout(currency, country)` validiert die Währung
  gegen `shop_currencies` (`resolve_currency`), der Betrag wird immer neu gerechnet. **CHF-Shops
  unverändert** (Präsentation = CHF = Basis). Welche Währung der Shop zeigt, steuert die Shop-Konfig
  (Standard/Land); der Kurs kommt aus `fx_rates`. **ERP sichtbar:** der tote Feld-Rückgabewert
  `previews` ist wiederbelebt – Reiter «Verkauf» → «Kundenpreis» zeigt den Hauptpreis in JEDER
  Shop-Währung (dieselbe Pipeline, die belastet), live beim Ändern des CHF-Basispreises. Wächter
  `tests/test_sales.py` (`test_stripe_line_item_charges_presentment_currency`,
  `…_falls_back_to_chf_for_old_intents`, `…_subscription_keeps_presentment_currency`,
  `test_checkout_threads_presentment_currency_and_recomputes_amount`,
  `test_stripe_provider_does_not_rely_on_adaptive_pricing`). *Bewusst NOCH offen: Preis-**Eingabe**
  in Landeswährung (heute EINE CHF-Zahl gepflegt, Fremdwährung nur Anzeige – ein lossy Rück-
  Umrechnen wäre die Alternative), per-Gesellschaft-Produktwährung (Intercompany), Shop-Währungs-
  umschalter für den Kunden (Backend `resolve_currency`/Produkt-Endpunkte tragen `currency` bereits).*
- **Mehr-Gesellschaften & Weltmärkte – Gebietskarte (ADR 006, `docs/adr/006-mehr-gesellschaften-
  maerkte.md`, Migration 092, Slice 1)**: Die Welt ist in feste **Regionen** partitioniert
  (`services/geography.REGIONS`: NAM/EUR/ASIA/LATAM/AFR/MEA/OCE) + umfassende ISO-2-Land→Region-Map
  (unbekannt → Betreiber). **Jede Region gehört genau EINER Gesellschaft**; der **Betreiber** besitzt
  per Default die ganze Welt, andere Gesellschaften «beissen sich» Regionen ab
  (`company_territories`, Region unique – hält NUR Abweichungen). So gehört **jeder Fleck der Erde
  jemandem** (Totalität, «es kann nie kein Land ausgewählt werden»). Die EINE Auflösung ist
  `sites.company_for_country(country)` = **Land → Region → Territorium-Besitzer → Betreiber-Fallback**
  (rein lesend). Die **fakturierende Gesellschaft** (Seller of Record) wird daraus **abgeleitet**
  (kein Dropdown): ausschlaggebend ist die **Rechnungsadresse** (Kundensitz), die **Steuer** folgt
  getrennt der **Lieferadresse** (Stripe Tax), der **Warenort** ist der Versand-Absender (ADR 005).
  Sie friert – wie Preis/Währung – bei Freigabe/Zahlung ein (Slice 2). Endpunkte `GET/PUT
  /admin/territories`; Frontend **abstrakte Weltkarte** (`components/erp/territory-map.tsx`, Region-
  Kacheln geografisch angeordnet, Klick-Zuweisung, Betreiber-Default) im Unternehmens-Reiter
  **«Gebiete»** (an jeder Gesellschaft, hebt deren Regionen hervor). **Neue Tabelle** → `create_all`
  deckt sie im Lifespan (kein Spalten-Safety-Net nötig – ausserhalb der 090-Ausfallklasse); gegen
  echtes PG16 verifiziert (create_all-Pfad, Auflösung, Totalität, Idempotenz, Downgrade,
  Lifespan-Neuschöpfung). Wächter `tests/test_geography.py`. **Slice 2 (UMGESETZT, Migration 093):**
  `sales.seller_company_object_id` – die fakturierende Gesellschaft je Verkauf, aus der
  **Rechnungsadresse** des Kunden abgeleitet (`sale._seller_object_id_for_customer` →
  `company_for_country`) und – wie Preis/Währung – **bei Bestätigung/Zahlung eingefroren**
  (`sale._freeze_seller`, idempotent; in `_apply_transition` UND `finalize_paid`). Die EINE
  Auflösung `sale.seller_company_for_order` (Snapshot ≻ live aus Kundenland ≻ Betreiber, rein
  lesend) speist **Beleg-Briefkopf** (`documents.py:_company(db, order)`) UND **Versand-Absender**
  (`logistics._sender_company` ersetzt `_settings`). Ein Nicht-Verkaufs-Auftrag (kein Kunde) →
  Betreiber wie bisher. Neue Spalte auf bestehender `sales`-Tabelle → **im Lifespan-Safety-Net**
  (090-Lehre); gegen echtes PG16 verifiziert (Freeze idempotent trotz geänderter Karte = Beleg-
  Unveränderlichkeit, Migration idempotent/downgrade, `_ensure_columns`-Netz).
  **Slice 3 (UMGESETZT, ohne Migration):** zwei Verfeinerungen, beide ohne Schema-Änderung.
  (a) **«Fakturiert durch» am Auftrag** (`OrderResponse.seller_company_object_id/_name`, gefüllt in
  `orders.to_order_response`): wer fakturiert, war bis dahin erst im fertigen PDF sichtbar – jetzt
  steht es in der Auftragsspezifikation, **bevor** der Beleg entsteht (Objektnummer klickbar).
  Gesetzt **nur bei einem Verkauf/einer Retoure** (ein Produktions-/Beschaffungsauftrag hat keinen
  Kunden, also keinen Fakturierenden) und nur fürs **Personal** sichtbar – eine interne
  Buchungs-Angabe.
  (b) **Ausnahmen je Land** (`geography.is_country_code`/`normalize_area`, `sites.country_map`/
  `_default_owner_id`/`_claim_owner`): ein einzelnes Land kann von seiner Region abweichen («Europa
  gehört der GmbH, Liechtenstein aber der Schweizer AG»). Das ist **kein zweiter Mechanismus**,
  sondern derselbe Anspruch feiner geschnitten: Region **und** Land stehen als Gebiets-Code in
  derselben Spalte (`company_territories.region`), der Unterschied ist aus der **Form abgeleitet,
  nicht gespeichert** – ISO-2 hat 2 Zeichen, jeder Regions-Code ≥ 3, eine Kollision ist per
  Konstruktion unmöglich (Wächter). Vorrang: **Land ≻ Region ≻ Betreiber**. Gespeichert wird nur,
  was **abweicht**: eine Zuweisung an die ohnehin zuständige Gesellschaft LÖSCHT die Zeile (ein
  Land fällt dann auf den Besitzer seiner Region zurück, nicht auf den Betreiber). Die Oberfläche
  leitet «ist Ausnahme» daraus ab, dass der Besitzer eines Landes von dem seiner Region abweicht –
  **kein zweites Flag**; Ländernamen kommen aus `Intl.DisplayNames` (keine zweite Länderliste im
  Repository). EIN Panel für Region wie Land, Ausnahmen als Liste unter der Karte, die Region-Kachel
  nennt die Zahl ihrer Ausnahmen. Gegen echtes PG16 verifiziert (27 Prüfungen: Totalität ohne jeden
  Anspruch, Land schlägt Region, Zurücksetzen entfernt die Zeile, `country_map` == Einzelauflösung
  über alle 225 Länder, unbekanntes Gebiet → 400, ein Gebiet = ein Besitzer, Seller folgt der
  Ausnahme; dazu 8 Prüfungen am Auftrags-Embed inkl. Snapshot schlägt Live-Ableitung).
  *Bewusst später: Steuer-Origin je
  Gesellschaft (heute hart CH; Stripe Tax rechnet destinationsbasiert real), Intercompany
  (CH→US Transferpreis), eigenes Stripe-Konto je Gesellschaft, Sub-Land-Gebiete (US-Bundesstaat).
  **Impressum bleibt global** (Betreiber); **Belegnummer bleibt global** (ein Nummernkreis).*

- **Testnotizen-Runde 20 (der ERP-Benutzer ist der Master, das Profil der Spiegel, Notizen
  #294 #295)**: Der Benutzer-Datensatz im ERP und die Profileinstellungen zeigen **dieselben
  Daten** – aber sie sahen und funktionierten völlig verschieden: hier ein Raster aus neun
  Abschnitten mit eigener `Field`-Optik (Alt-Palette `#2563eb`/slate), Speichern über einen
  Knopf und eine Rechnungsadresse mit einem wirkungslosen Häkchen «Gleich wie Adresse»; dort
  drei Container, EIN Auto-Save, Google-Adress-Suche und ein Schalter, der die Rechnungsfelder
  tatsächlich **spiegelt**. Der Nutzer hat die bessere Seite benannt (#294: «in diesem
  speziellen fall möchte ich, dass dies von den Profileinstellungen übernommen wird») – also
  **übernimmt der Master die Struktur des Spiegels**, nicht umgekehrt: Der Profil-Reiter ist
  jetzt dieselbe Anatomie (Persönliche Angaben · Adressen · Kommunikation) aus **denselben
  Bausteinen** (`account/field.tsx`, `erp/address-field.tsx`, `account/use-autosave.ts`) – kein
  Nachbau, sondern Wiederverwendung, damit die beiden nicht wieder auseinanderlaufen können.
  **Die Spiegelung ist damit auch fachlich echt:** «Rechnungsadresse = Lieferadresse» kopiert
  im ERP jetzt dieselben Felder wie im Konto (vorher ein Häkchen, das nichts kopierte – zwei
  Wahrheiten, je nachdem wo man es setzte). **Was das ERP MEHR zeigt, bleibt** (#295, «das ERP
  muss ALLES können»): Rolle, Bankverbindung, die **admin-pflegbare** Anstellung (im Konto
  read-only) und der Block **System** (E-Mail · Anmeldung · Passkeys · Login/Erstellt/Geändert ·
  Firebase-UID). Nicht-Admins sehen dieselbe Struktur read-only (die Adresse als kompakte
  Zusammenfassung statt als Sucheingabe). Der Speichern/Verwerfen-Streifen am Fensterrand ist
  entfallen – Auto-Save wie überall, Rückmeldung im Karten-Kopf.

- **Testnotizen-Runde 21 (weniger Felder, dafür Pflicht; die Welt wird gemalt; Notizen
  #300–#323)**: Der Unternehmens-Datensatz hatte **24 Eingabefelder** – und die Frage des
  Nutzers war für fast jede Gruppe dieselbe: *brauche ich das überhaupt, jetzt oder in
  Zukunft?* Der Massstab war darum nicht «könnte man mal brauchen», sondern: **nennt es
  jemand auf einem Beleg, im Impressum oder in einer Regel?** Übrig bleiben **neun** – und
  genau deshalb dürfen sie **Pflicht** sein (#323: ein Formular, in dem alles optional ist,
  sagt nichts; eines mit neun Pflichtfeldern ist in zwei Minuten vollständig).
  (1) **Gestrichen, mit Begründung** (Modell, Schema, `ENTITY_FIELDS`, Frontend-Typ, API-
  Mapping): **Handelsregister-Nr., HR-Kanton, Aktienkapital** (#307) – in der Schweiz IST die
  HR-Nummer seit 2016 die UID, der Kanton steht im Register, Kapital muss ein Impressum nicht
  nennen; drei Zeilen, die abschrieben, was die UID schon sagt. **QR-IBAN, Bankname, BIC**
  (#313) – die IBAN trägt Land, Bank und Konto; die QR-Rechnung ist nicht gebaut, und für
  SEPA braucht es keinen BIC. **MWST-Methode/-Periode** (#314/#319/#321) – reine
  Buchhaltungs-Parameter (Phase 3), die nichts im System auswertete. **Zahlungsfrist und
  Skonto** (#316/#317/#318) – die gehören in die **Offerte**, wo sie je Geschäft verhandelt
  werden, nicht als stiller Firmen-Default. **OSS/VIES** (#320) – nie ausgewertet; die
  destinationsbasierte EU-Steuer rechnet Stripe Tax. Nachweis für alle: ausserhalb von
  Modell/Schema/Formular tauchte keines davon in einer Regel auf.
  (2) **Zwei Angaben füllt jetzt das System selbst.** Die **Währung** folgt dem Land (#304,
  `sites.currency_for_country`) und steht als Wert da, nicht als Auswahl – ändern geht über
  «Ändern», also bewusst, nicht im Vorbeitippen («auch wenn nicht gerade super einfach»). Die
  **Website-Adresse** ist die des Deployments (#309, `sites.website_url` ← `FRONTEND_BASE_URL`):
  read-only angezeigt, weil sie im Impressum und auf dem Briefkopf steht – ein Eingabefeld
  daneben wäre eine zweite Wahrheit, die beim ersten Domain-Wechsel still falsch wird.
  (3) **Der Name ist hart Pflicht** (#301/#302, jetzt «Unternehmensname»): er ist zugleich das
  **Halter-Label** (`locations.location_label`), eine namenlose Gesellschaft liesse jede
  Standort-Anzeige leer, die auf sie zeigt. `sites.apply_update` weist ihn leer ab (Anlegen tat
  das immer schon). Anschrift, UID, MWST-Nr., E-Mail, Telefon, Rechtsform und IBAN sind
  markierte Pflichtfelder (#305/#307/#310/#313) – gelbes Sternchen wie im Konto, kein Blocker.
  (4) **Dieselbe Anatomie wie Benutzer und Profil** (#308/#311/#312): EIN Formular, EIN
  **Auto-Save** (Speicher-Streifen weg), Karten statt Sektionsraster, **keine Symbole** in den
  Überschriften. Die Alt-Bausteine `Field`/`Sec` (slate/blue-Altpalette) wurden nur noch hier
  genutzt und sind entfallen; die `Card` wohnt jetzt im gemeinsamen Vokabular (`fields.tsx`).
  (5) **Rechtsform schlägt sich selbst vor** (#303): Freitext mit `datalist` je Land (CH → AG ·
  GmbH · Einzelunternehmen …, US → Inc. · LLC …). Eine API dafür gibt es nicht – die einzige
  verbindliche Quelle ist die ISO-20275-Liste der GLEIF, ein Download mit ~2600 Einträgen ohne
  Abfrage-Endpunkt; für acht Vorschläge der falsche Preis, und Rechtsformen ändern sich in
  Jahrzehnten. Also dieselbe Bauart wie die Land→Währung-Zuordnung: eine kleine, dokumentierte
  Tabelle im Frontend.
  (6) **GPS → Adresse** (#306, `AddressField`): «Aktuellen Standort verwenden» holt die
  Koordinaten vom Browser und lässt Googles Geocoder daraus einen Treffer machen – der durch
  **denselben** Zweig ins Formular läuft wie ein gewählter Vorschlag (`applyPlace`), statt
  einen zweiten Weg aufzumachen. Gilt für jede Adress-Eingabe, nicht nur die Firma.
  (7) **Die Weltkarte ist jetzt eine Karte** (#322, `components/erp/world-map.tsx`): 5°-Raster,
  72×25 Zellen, **nur Linien und Ecken** – jede Zelle ist ein echtes geografisches Feld, die
  Form entsteht aus der Menge. Umriss-Polygone wären bei zehn Stützpunkten Flecken geblieben;
  erkennbar wird eine Weltkarte über die *Verhältnisse*, und die liefert ein Raster geschenkt.
  Grönland und die Antarktis fehlen **bewusst**: sie liegen in keiner Region, und eine Fläche
  einzufärben, die keiner Region gehört, wäre eine gemalte Behauptung. Russland ist bis in den
  Osten europäisch eingefärbt – so steht es in `geography.py`, und die Karte darf nicht anders
  behaupten als die Auflösung entscheidet. Darunter dieselbe Aussage als Liste (die Karte kann
  nicht sagen, wie eine Gesellschaft heisst; die Liste nicht zeigen, wo Ozeanien liegt).
  (8) **Der Feed atmet** (#300): mehr Polsterung, kleineres Symbol – und der Zustand ist ein
  **Punkt mit Wort** statt einer gefüllten Pille (`StatusBadge plain`). Vierzig Pillen
  untereinander waren das, was die Liste schwer machte; das Design-System nennt Punkt+Wort
  ohnehin als Regelform und die gefüllte Badge als Ausnahme für Detail-Köpfe.
  > **Folge-Deploy:** die 14 DB-Spalten bleiben vorerst stehen (SQLAlchemy ignoriert sie) und
  > werden erst im **nächsten** Deploy per Migration gedroppt – exakt wie `is_primary` in 090→091.
  > Ein Drop im selben Deploy trifft die während des Cloud-Run-Rollouts noch laufende
  > Vorgänger-Revision, die sie noch mappt: das ist die Ausfallklasse von Migration 090.

- **Eine Instanz ist eine MENGE, kein Ding** (Juli 2026, `tests/test_quantity_rules.py`):
  Auf die Frage, ob eine Charge à N intern nicht besser **N Zeilen à 1 Stück** wäre (damit
  überall dieselbe Logik gilt wie beim Einzelteil), lautet die Antwort **nein** – und die
  Begründung steht jetzt am Modell (`models/instance.py`), damit sie nicht erneut erarbeitet
  werden muss: (a) eine Charge darf **gebrochen** sein (2.5 kg, 0.75 m²) – «2.5 Zeilen» gibt
  es nicht, und genau dafür existiert `batch`; (b) die **Objektnummer ist systemweit
  eindeutig** und der Schlüssel für QR-Scan, `references.object_references` und
  `locations.location_chain` – N Zeilen mit derselben Nummer bräuchten überall eine neue
  Antwort auf «welche davon?»; (c) eine 1000er-Charge wären 1000 Zeilen je Reservierung,
  FIFO-Zugriff und Umlagerung. Der Preis ist die Teilmengen-Logik, und die steht an genau
  zwei Stellen (`reservation.py` = wer beansprucht wie viel, `location_split.py` = wo liegt
  wie viel).
  **Die Beobachtung dahinter war trotzdem richtig** – es gibt eine wiederkehrende
  Fehlerklasse, sie heisst nur anders: **«Zeilen zählen statt Mengen summieren»**. Eine
  Charge à 500 ist EINE Zeile und FÜNFHUNDERT Stück, also liefert `len(insts)` die Zahl 1,
  wo 500 gemeint sind (Testnotiz #72: Prüfumfang; #333: Bestands-Filter). Statt weiterer
  Einzelfixes hält ein **AST-Wächter** die Regel: kein Mengen-Feld darf aus einer Anzahl
  befüllt werden. Er fand auf Anhieb **drei** Stellen – `provisioning._sub_order`
  (`quantity=len(insts)`), `customer_returns.request_return` und `routers/orders.py` (beide
  Retoure: eine zurückgegebene Charge à 5 Stk wurde als «1 Stk» gutgeschrieben; im selben
  `orders.py`-Zweig summierte die Nachbarzeile korrekt). Frontend-Pendant: `lib/process.ts`
  liefert `sumQuantity`/`formatQty` als die EINE Mengen-Stelle.
  **Und die Unterscheidung selbst ist geschrumpft:** `Instance.kind` ist jetzt ein
  **Etikett**, keine Regel – kein Fachmodul verzweigt mehr darauf (Wächter
  `test_the_batch_unit_difference_lives_in_exactly_one_module`). Möglich wurde das durch
  zwei Umbauten in der Datenerfassung:
  (1) **Die Stichprobe wird nach MENGE gezogen** (`inspection.sample_capacity`): jede Instanz
  liefert so viele Proben, wie ihre Menge hergibt, verteilt reihum. Daraus fällt beides
  heraus, was vorher zwei Zweige waren (Einzelteil: N Instanzen à eine Probe; Charge: eine
  Instanz mit N Proben) – **und der Fall «mehrere Chargen» wird zum ersten Mal richtig
  bedient**: die alte Bedingung `len(insts) == 1 and kind == 'batch'` griff nur bei *einer*
  Instanz, zwei Chargen à 100 ergaben darum **2** Proben statt 10.
  (2) **Was nicht beprobt wurde, wird nicht beurteilt** (`inspection.sample_verdicts`) – ein
  **ernster Fehler**: `_apply_per_instance_qc` gab JEDER Instanz des Auftrags ein Urteil, und
  wer nicht in der Stichprobe war, fiel über den Default `False` durch. Eine **bestandene**
  20 %-Stichprobe sperrte damit die übrigen 80 % (`quality='blocked'`) – sie verschwanden aus
  FIFO, Bestand und Verfügbarkeit, obwohl die Prüfung bestanden war. Eine Stichprobe sagt
  etwas über die gezogenen Stück; reicht das nicht, stuft `escalate_decision` auf 100 % hoch,
  und dann ist jede Instanz beprobt. Gegen echtes PostgreSQL nachgewiesen (vorher 4 von 5
  gesperrt, jetzt 0; Durchfaller werden weiterhin gesperrt).

- **Testnotizen-Runde 22 (wer arbeitet noch daran?, Notizen #324–#340)**: Zwei echte Fehler
  und eine Reihe Farb-/Wortkorrekturen.
  (1) **Freigegeben wird erst, wenn KEIN Auftrag mehr an der Instanz arbeitet** (#332,
  `process._worked_on_by_a_running_order`). Gemeldeter Fall: eine **Abweichung** auf eine
  Instanz eines noch **laufenden** Erzeugungsauftrags wurde abgeschlossen – und gab die
  Instanz frei. Sie stand damit «Freigegeben» am Lager (FIFO-verfügbar), während sie
  tatsächlich noch in Produktion war. Die Regel aus Notiz #262 («freigegeben wird von dem
  Auftrag, der zuletzt daran gearbeitet hat») war richtig gemeint, aber nur in EINE Richtung
  gebaut: sie prüfte, was in einer offenen Abweichung steckt, nicht, ob der **Erzeuger** noch
  läuft. Jetzt zählt der Status der höchstens zwei beteiligten Aufträge (Erzeuger
  `order_id`, festes Subjekt `subject_of_order_id`): ist einer noch `released`, wird nicht
  freigegeben. Der #262-Fix bleibt gültig, weil ein **abgebrochener** Auftrag nicht
  `released` ist – er hält nichts fest. Wächter
  `test_an_instance_is_not_released_while_another_order_still_works_on_it`.
  (2) **Ein leeres Pflichtfeld ist keine Datenbank-Verletzung** (#338): eine geleerte
  Rechtsform schickte `null` in eine NOT-NULL-Spalte, und der rohe psycopg2-Dump
  («NotNullViolation … Failing row contains (2, Inexxio LLC, null, Dah…») landete im
  Formular. Zwei Korrekturen: `sites._NOT_NULL_TEXT` schreibt für diese Spalten `""` statt
  `NULL` (leer heisst «noch nicht ausgefüllt», nicht «kein Wert erlaubt»), und ein eigener
  `IntegrityError`-Handler macht aus einem verletzten Constraint einen **400 mit einem
  Satz**, der die Spalte nennt – die Ursache gehört ins Log, nicht in die Oberfläche.
  (3) **Die Weltkarte, einen Tick kräftiger und mit runden Ecken** (#340/#336): jeder
  Gesellschafts-Ton hat jetzt **drei** Stärken – `dot` (Punkt/Kontur), `land` (die Fläche)
  und `bg` (Chips/Zeilen); die Karte nutzte bisher `bg` und verschwand darin. Die Ecken
  rundet ein SVG-Filter (weichzeichnen → Alpha hart zurückschneiden) je Region: er
  verschmilzt die Zellen einer Region zu EINER Fläche mit runder Aussenkante und lässt
  zwischen zwei Regionen genau die Naht stehen, die vorher fehlte.
  (4) **Der Beschaffungs-Ablauf trägt EINE Tönung** (#329): vorher lagen drei Flächen
  ineinander, von denen zwei identisch waren (Modul-Karte getönt → Stufen im *gleichen* Ton →
  weisser Eingabe-Block). Jetzt tönt nur die Modul-Karte; die Stufen sind **weisse Karten**
  darauf, und die aktive hebt sich über ihren **Rand** in Modulfarbe ab, mit nahtlos
  anhängendem Arbeitsbereich. Struktur vor Fläche.
  (5) **«Ausschleusen» heisst «Aussondern»** (#328) – der Begriff aus der Qualitätssicherung
  («Aussonderung fehlerhafter Teile»); «Ausschleusen» klang nach Logistik und sagte nicht,
  was mit dem Teil geschieht. Umbenannt in der Registry (`domain/event_types.py`), das
  Frontend spiegelt sie (Mirror-Test).
  (6) **Der Bestand zählt Stück, nicht Instanzen** (#333): eine Charge ist EINE Instanz über
  500 Schrauben – «2» als Bestand war schlicht falsch. Die Filter-Chips summieren jetzt die
  Menge und nennen die Einheit.
  (7) **Status ist EINE Form** (#334): die zwischenzeitliche «Punkt + Wort»-Variante im Feed
  ist wieder entfallen – derselbe Zustand darf nicht je nach Ort anders aussehen. Die Luft
  im Feed (#300) kommt aus Polsterung und Zeilenabstand, nicht aus einer zweiten Form.
  (8) **Betreiber-Stern in der Kopfzeile** (#339): «Als Betreiber der Website festlegen» war
  ein Knopf mitten in den Stammdaten – dabei ist das eine Rolle **über** dem Datensatz. Jetzt
  ein Stern bei den übrigen Kopf-Aktionen (gesetzt: leuchtend als Tatsache; nicht gesetzt:
  leiser Knopf, Erklärung im Hover).
  (9) **Weiche Format-Prüfung für Telefon/E-Mail** (#326, `account/field.fieldFormatIssue`):
  melden statt blockieren. Eine strenge Telefon-Regex sperrt irgendwann eine echte Nummer
  aus, und libphonenumber wären ~150 kB für ein Feld, das niemand automatisiert wählt –
  also ein Hinweis bei offensichtlichem Unsinn (zu wenige Ziffern, fremde Zeichen),
  gespeichert wird trotzdem.
  (10) Kleineres: Auftrags-Inhalt auf **880 px zentriert** wie die übrigen Detailfenster
  (#327 – vorher lief die Spezifikation über die volle Breite, während der Fluss darunter
  bei 600 px zentriert blieb); Scan-Knopf der Datenerfassung in der ruhigen schwarzen
  Hauptaktion statt blau-auf-gestrichelt (#330, letzte Stelle der Alt-Palette in der Datei);
  Website-Hinweis (#337) und Gebiets-Erklärabsatz (#335) entfallen; der AGB-Nachweis im
  Konto entfällt (#325 – Version und Datum gehören ins Dokumentenmanagement, sonst zwei
  Anzeigen derselben Tatsache).
  *#324 (GPS für die Lieferadresse im Konto) war bereits erfüllt: die GPS-Übernahme sitzt in
  `AddressField` und gilt damit für **jede** Adress-Eingabe – im Konto über «Ändern».*
  *#331 (fehlende Unterdeckungs-Info) ist keine Lücke: die Fehlmenge wird an dem **Schritt**
  gemeldet, der das Subjekt braucht – das ist die «Es fehlt»-Zeile, die angeheftet wurde. Ein
  Auftrag ohne Subjekt-Schritt (nur Beschaffung/Ressource) meldet weiterhin nichts; das ist
  bewusst so, weil ihm nichts fehlt, was er selbst bräuchte.*

- **Szenario-Durchlauf: alle implementierten Abläufe end-to-end nachgespielt (Juli 2026)**:
  **34 Szenarien / 100 Prüfungen** über die **echten** Service-Pfade gegen echtes
  PostgreSQL 16 – Erzeugung (Einzelteil/Charge/Bruchmenge), Datenerfassung (100 %,
  Teil-Stichprobe, Hochstufung, Durchfaller → Abweichung → Klärung), Abweichung/Abbruch/
  Zurücknehmen/Kette, Bestand/FIFO, Unterdeckung/Nachschub/«ohne Ersatz weiter»/gezielte
  Deckung, Aussondern (ganz · Teilmenge · Sperren/Entsperren), Verkauf + Retoure (Slice,
  ganze Instanz, Kulanz), Made-to-Order über den Nachschub, Ressource (Verbrauch ·
  Betriebsmittel · Fehlmenge), Bewegung/Standort-Verteilung, Sicherheitsbestand,
  Beschaffung (einzeln und mehrpositionig), Dokument-Schritt, Artikel-Deaktivierung,
  Wiederkehr, Mehrpositionen-Verkauf. **Vier echte Fehler**, alle aus derselben Wurzel:
  *seit den Bruchmengen (Migration `055`) ist jede Menge ein `Decimal`* – und an vier
  Stellen war das noch nicht angekommen.
  (1) **Der Prozessschritt «Ressource» war komplett unbenutzbar.** `resource_usages.details`
  bekam die entnommene Menge als `Decimal`; `json.dumps` kann das nicht, also brach **jede**
  Verbuchung eines Verbrauchs mit einem 500 ab – nicht beim Setzen des Feldes, sondern erst
  beim `flush`, mitten in der Transaktion. Der Event-Strom hatte seine eigene Normalisierung
  (`events._json_safe`), die elf **anderen** JSONB-Spalten nicht. Die Normalisierung sitzt
  jetzt an der **Grenze zur Datenbank** (`core.database.json_safe` als `json_serializer` der
  Engine): eine Stelle, und jede neue JSONB-Spalte erbt den Schutz. Sie ist ein **Netz, kein
  Vertrag** – wo es auf den Rappen ankommt (Geld, Reservierungen, Standort-Teilmengen),
  schreibt der Fachcode weiterhin bewusst **Strings**.
  (2) **Eine Retoure blähte den Bestand auf.** Die Rückgabe einer ganz verkauften Instanz
  buchte `max(Menge, verkauft, 1)` zurück – der feste Boden machte aus einer verkauften
  0.5-kg-Charge **1 kg**. «Mindestens eins» ist eine Aussage über *Stück*, nicht über
  *Mengen*. Jetzt gilt: zurück kommt, was hinausging (Event-Strom); Instanz-Menge und die 1
  sind nur noch Rückfälle für Altdaten.
  (3) **Nach einer Teil-Verschrottung war der Rest scheinbar belegt.** Es gab zwei fast
  gleiche Entnahme-Funktionen, die je EINEN halben Job machten: `consume` löste den Anspruch
  des Entnehmers, `reduce_quantity` deckelte fremde Ansprüche – und das Verschrotten griff
  zur falschen. Eine Charge à 10 mit 5 reservierten Stück behielt nach dem Verschrotten
  dieser 5 ihre Reservierung über 5 auf einer nur noch 5 Stück grossen Instanz: frei = 0.
  FIFO übersah den Rest, andere Aufträge meldeten eine Fehlmenge, die es nicht gab, und die
  **Auto-Nachbestellung bestellte den Sicherheitsbestand ein zweites Mal** (im Test: 8 statt
  3). Jetzt gibt es **eine** Regel – `reservation.take(inst, qty, by_order_id=…)` – und sie
  tut beides; die drei Aufrufer (Verbrauch, Verkauf, Verschrottung) teilen sie sich.
  (4) **Das Schema liess sich nicht aus den Migrationen aufbauen.** Eine Datenreparatur
  (`074`) griff auf `article_process_steps.locked` zu – eine Spalte, die **nie eine
  Migration angelegt** hatte (sie stammte aus dem Lifespan-`create_all` und wurde von `081`
  wieder entfernt). Auf einer frischen Datenbank brach `alembic upgrade head` genau dort ab;
  die laufende Umgebung merkt davon nichts, ein neues Projekt oder eine Wiederherstellung
  scheitert – dieselbe Ausfallklasse wie beim Deploy von Migration `090`: es zeigt sich erst,
  wenn es zählt. Die Reparatur überspringt jetzt, was es nicht gibt (wie `079` es immer
  schon tat), und die **CI baut das Schema bei jedem Push von null auf** (Postgres-16-Service
  + `alembic upgrade head` in den Quality gates) – die Behauptung «Alembic ist die
  Schema-Wahrheit» ist damit nachgewiesen statt geglaubt.
  **Kein Fehler, aber eine Sackgasse mit Weg nach vorn:** eine Charge **ohne** Standort lässt
  sich nicht teilverlagern – nach «10 von 1000 ans Band» lägen 990 weiterhin nirgends, und
  genau das kann die Verteilungs-Map nicht sagen (bei einem einzigen Slice ist der Skalar die
  Wahrheit und würde behaupten, die GANZE Charge sei am Band). Die Ablehnung bleibt, sie
  nennt jetzt aber den Weg: erst den gesamten Bestand einlagern, danach Teilmengen verlagern.
  **Bestätigt richtig** (Szenarien ohne Befund): Auto-Abschluss und Freigabe erst, wenn kein
  Auftrag mehr an der Instanz arbeitet; bestandene Teil-Stichprobe sperrt nichts, eine
  **durchgefallene** stuft erst auf 100 % hoch und schliesst erst dann endgültig ab;
  Abweichung nimmt ihr Stück heraus statt den Auftrag anzuhalten, darf ihre **eigene**
  Abweichung haben, und «Zurücknehmen» gibt die Bindung über die EINE Aufräum-Stelle
  zurück; Verschrotten löst **alle** Reservierungen, sodass die Fehlmenge eines fremden
  Auftrags ehrlich sichtbar wird; Ausschuss ist terminal **und** standortlos, Sperren
  reversibel unter Erhalt von Standort/Menge/Reservierungen; ein Komponenten-Bedarf
  blockiert den Schritt statt still unterzuliefern; Betriebsmittel werden genutzt, nicht
  verbraucht; ein Mehrpositionen-Verkauf hat **einen** `sale`-Schritt mit einem Beleg je
  Position, eine Mehrpositionen-**Beschaffung** dagegen je Position eine eigenständig
  fortschreitende Bestellung; Kulanz (keine Rückgabe-Bewegung) lässt die Ware beim Kunden;
  eine bezahlte Position lässt sich nicht still kürzen; ein Dokument ohne Parteien ist mit
  dem Ausstellen freigegeben; das Deaktivieren eines Artikels übergibt laufende Instanzen
  an einen Abweichungsauftrag statt sie herrenlos zu lassen. **Kein Überverkauf, bewiesen
  statt begründet:** ein Verkauf ohne Bestand bindet nichts, sein Schritt ist `blocked`,
  und JEDER Ausführungs-Endpunkt löst über `process.resolve_exec_step` auf, das «aktiv»
  verlangt – gedeckt wird über den Nachschub, dessen Stück beim Abschluss an den Eltern
  gepinnt werden. Wächter: `tests/test_quantity_rules.py`
  (`test_every_json_column_survives_a_decimal`, `test_a_returned_quantity_has_no_floor_of_one`)
  und `tests/test_fractional_quantities.py: test_take_releases_the_own_claim_and_trims_the_others`.

- **Vereinfachung: zwei if/else-Ketten sind Tabellen geworden (Juli 2026)** – beide ohne
  Verhaltensänderung, beide nach demselben Muster: *per-Typ-Wissen gehört in die Registry,
  nicht in eine Kette.*
  (1) **«Woran sieht man einem Schritt an, dass er durch ist?»** stand als if/elif über die
  Schritttypen in `process._fact_status` – dieselbe Aussage wie `domain/event_types.py`, nur
  an einer zweiten Stelle: ein neuer Typ musste in beiden gepflegt werden, und sie konnten
  still auseinanderlaufen. Jetzt deklariert jeder Eintrag `status_field` / `done` / `failed`
  (`None` = die blosse **Existenz** der Fachzeile ist die Erledigung – Bewegung, Ressource,
  Aussondern), und die Ableitung ist EINE Regel: **19 Zweige → 6**. Die eine Ausnahme ist
  bewusst generisch formuliert: ein Fehlschlag, den ein Folgeauftrag geklärt hat
  (`resolved_by_order_id`), gilt als erledigt – heute trägt nur die Datenerfassung dieses
  Feld, die Regel «geklärt ist erledigt» gilt aber für jeden Typ, der es bekommt.
  (2) **«Welche Felder trägt ein Schritt-Typ?»** entschied der Konstruktor in
  `routers/article_process._create` über ~14 einzelne `x if is_document else None` plus drei
  Flag-Variablen davor. Die Frage war nur durch Absuchen aller Zeilen zu beantworten, und ein
  neuer Typ hiess «überall eine Bedingung ergänzen». Jetzt liefert je Typ EINE Funktion genau
  seine Spalten (und prüft, was zu prüfen ist); alles andere bleibt leer (Modell-Default):
  **30 Zweige → 5, 65 → 34 Zeilen**. Wächter `test_a_step_type_only_fills_its_own_columns`
  (jeder Typ füllt nur seine eigenen Spalten, Beschaffung nie Lieferant UND Webshop) und
  `test_step_status_semantics_live_in_the_registry` (kein Statuswert mehr in der Ableitung).
  Gegen echtes PostgreSQL für **jeden** Schritttyp gegengeprüft: die geschriebene Zeile ist
  spaltenweise identisch zur vorherigen Fassung.
  *Bewusst NICHT angefasst:* `main._ensure_columns` – der Lifespan-Schutz ist bereits
  tabellengetrieben (je Schleife eine Art Schema-Reparatur); seine Zweige sind der Sache
  geschuldet, und ausgerechnet dieses Netz für Kosmetik anzufassen wäre nach der
  Migration-090-Geschichte das falsche Risiko.

- **Unterdeckung ist EINE Regel für alles (Juli 2026)** – tiefe Prüfung der Auftrags-/
  Unter-Auftrags-/Abweichungs-Logik über ~30 betriebliche Situationen gegen echtes
  PostgreSQL. Die Zustandsmaschine selbst hielt dicht; die **Wirkung** der Fehlmenge nicht.
  **Der Konstruktionsfehler:** die Fehlmenge blockierte eine hand-gepflegte Liste von fünf
  Schritttypen (`SUBJECT_STEP_TYPES`). Damit wirkte sie **zu hart oder gar nicht** – je
  nachdem, welche Schritte zufällig im Prozess standen: (a) hatte der Prozess einen
  Subjekt-Schritt, legte eine Abweichung an EINEM von fünf Teilen auch die **Prüfung der
  anderen vier** still (409 «Datenerfassung ist nicht an der Reihe») – exakt die Pause, die
  abgeschafft werden sollte, nur unter anderem Namen; (b) hatte er keinen (reine
  Beschaffung), schloss der Auftrag **still mit 3 von 4** ab, ohne Hinweis und ohne
  Entscheidung. Die Konsequenz hing an der Prozessform statt an der Sache.
  **Die eine Regel, zwei Hälften** – beide *deklariert*, keine Liste:
  1. **Blockieren tut sie nur, wer die Menge WEITERGIBT** – hinaus zum Kunden (`sale`) oder
     hinein ins Produkt (`resource`). Deklariert als `EventType.hands_over`. Erfassen,
     Aussondern und Bewegen laufen **immer** – sie arbeiten an dem, was da ist, und gerade
     wenn etwas fehlt, will man sie tun.
  2. **Fertig wird kein Auftrag, solange ihm etwas fehlt** (`recompute_completion`). Das ist
     der eigentliche Schutz gegen stilles Unterliefern – jetzt an EINER Stelle statt als
     Nebenwirkung eines blockierten Schritts. Der Mensch entscheidet über die drei Wege
     (Ersetzen · gezielt decken · ohne Ersatz weiter), dann ist der Auftrag durch. *Die
     guten Stück bleiben bis dahin `in_process` – richtig so: sie sind diesem Auftrag
     zugesagt und dürfen nicht per FIFO abwandern.*
  **Die Fehlmenge gehört dem AUFTRAG, nicht einem Schritt** (`OrderResponse.shortfall` +
  `waiting_for`, aus `OrderStepInfo` entfernt): sie ist «Soll − Gesichert» und dieselbe
  Zahl, egal welcher Schritt dran ist. Vorher hing sie an jedem Subjekt-Schritt – dieselbe
  Zahl mehrfach berechnet (samt FIFO-Abfrage **je Schritt**) und in einem Prozess ohne
  Subjekt-Schritt gar nicht sichtbar. `StepShortfall.kind` (subject|component) ersetzt die
  hand-gepflegte `SUBJECT_STEP_TYPES`-**Spiegelkonstante im Frontend**; die Notiz mit den
  drei Wegen steht jetzt **einmal** unter dem Fluss statt je Schritt.
  **Steckengeblieben ≠ unterwegs** (`process.is_stalled` + `supply.covering_sub_orders`):
  Ein Nachschub mit fehlgeschlagenem Schritt liefert nie mehr etwas. Er galt trotzdem als
  «läuft» – der Eltern zeigte für immer «wartet auf …», blendete darum die Deckungs-Wege
  aus, «Ersetzen» antwortete «der Bedarf ist bereits gedeckt» und ein zweiter Nachschub
  wurde als überflüssig verworfen: **kein Weg nach vorn**. Die Regel gab es bereits einmal
  (Auto-Nachbestellung) und fehlte an den zwei Stellen, an denen sie genauso zählt; jetzt
  liegt sie an EINER und alle drei lesen sie.
  **Der Verdacht hält das Teil ab der Meldung** (`create_deviation` reserviert sofort,
  `detach_sub_order` gibt frei): zwischen «Abweichung gemeldet» (Entwurf) und «Auflösung
  freigegeben» war das verdächtige Teil per FIFO für jeden anderen Auftrag greifbar.
  Dazu: bei Totalausschuss nennt «ohne Ersatz weiter» jetzt den echten Weg («Ersetzen» oder
  «Abbrechen») statt auf einen längst erledigten Abweichungsauftrag zu zeigen; drei
  Docstrings beschrieben noch die vor Migration `086` abgeschaffte «Abbruch ausstehend»-
  Semantik. Wächter: `test_a_shortfall_stops_handover_not_work`,
  `test_no_order_completes_while_something_is_missing`,
  `test_the_shortfall_belongs_to_the_order`,
  `test_a_reported_deviation_holds_its_instance_immediately`.

- **Testnotizen-Runde 23 (die Klammer ist die Instanz, Notizen #341–#351)**: Vier der zehn
  Notizen betrafen dieselbe Wurzel – **woran ein Auftrag und eine Abweichung einander
  erkennen**.
  (1) **«Es fehlt» stand an einem abgeschlossenen Auftrag** (#347, Regression aus der
  Unterdeckungs-Runde): die Fehlmenge wurde für JEDEN Auftrag gerechnet. Bei einem fertigen
  sind Reservierung und Subjekt-Bindung längst gelöst – «Soll − Gesichert» ergab die volle
  Menge als Phantom. Jetzt: **nur ein laufender Auftrag kann etwas schulden**
  (`order.status != "released"` → keine Fehlmenge). Ein Entwurf hat noch nichts zugesagt,
  ein abgeschlossener hat abgerechnet.
  (2) **Die Klammer zwischen Auftrag und Abweichung ist die INSTANZ, nicht der
  Eltern-Zeiger** (#348/#350). Ein Auftrag referenziert Instanzen; eine Abweichung tut
  dasselbe. Das Instanz-Detail meldet eine Abweichung am **Herkunfts**-Auftrag – ein
  anderer Auftrag, der auf dasselbe Stück zählt, lief darum ungerührt weiter und zeigte die
  Abweichung nie. `deviated_instance_ids` fragt jetzt «steckt eines MEINER Stücke in einer
  offenen Abweichung?» (über `order_instances`, ohne `parent_order_id`), und
  `deviation.deviations_touching` bringt jede Abweichung an einer eigenen Instanz in den
  Prozess – über die **dauerhafte** Verarbeitungs-Historie (`instance_order_links`), damit
  auch eine **geklärte** dokumentiert bleibt. *Fallstrick, getestet: eine Abweichung darf
  sich dabei nie selbst zählen – sonst gäbe sie beim Abschluss nichts frei (ihre eigene
  Statusänderung ist zum Abfragezeitpunkt noch nicht geflusht).*
  (3) **Am Auftrag gibt es nur den Abbruch** (#351): die Option «Läuft weiter» war lediglich
  eine Vorauswahl «alle Instanzen» – und WO ein Fehler auftritt, sagt man an der **Instanz**.
  Ein Weg weniger, dieselbe Fähigkeit; Server (`routers/orders.open_deviation`) und Dialog
  sagen dasselbe.
  (4) **Gebietskarte flächig, Zuweisung am Ort** (#342/#343/#344): die Karte füllt den
  Container, jede Fläche trägt **Gebiet + fakturierende Gesellschaft** als Beschriftung
  (`WorldMap.label`, Schwerpunkt über `regionAnchor` als Median – bei Europa bis Ostrussland
  zöge der Mittelwert ins Meer), und ein Klick öffnet die Zuweisung als Kärtchen **über der
  Fläche**. Die Liste unter der Karte sagte dasselbe ein zweites Mal und ist entfallen,
  ebenso die eigene Ausnahmen-Sektion – die Ausnahmen eines Gebiets stehen im selben
  Kärtchen (samt «+ Land»), und steht keine da, steht auch nichts da. Ist eine Gesellschaft
  geöffnet, treten die Gebiete der anderen zurück (`highlight`).
  (5) **Steuerliche Kennungen je Land** (#346, `TAX_IDS_BY_ISO2` neben `LEGAL_FORMS_BY_ISO2`):
  gefragt wird, was es dort gibt. Der Gewinn ist das **Weglassen** – die USA kennen keine
  Mehrwertsteuer, dort erscheint die «MWST-Nummer» gar nicht (statt als leeres Pflichtfeld).
  Dieselbe Bauart und derselbe Grund wie bei den Rechtsformen: eine Abfrage-API dafür gibt
  es nicht (VIES *prüft* bestehende USt-IdNrn, es sagt nicht, welche Kennungen ein Land
  kennt), und die Angaben sind träge. (6) IBAN-Hinweis entfällt (#345 – der maskierte Wert
  steht bereits als Platzhalter).
  *#341 (jede Instanz einzeln statt «2 Stk.») ist bewusst NICHT umgesetzt: eine Instanz ist
  eine **Menge**, kein Ding – eine Charge darf gebrochen sein (2.5 kg), die Objektnummer ist
  systemweit eindeutig (QR/Referenzen/Standort-Kette), und N Zeilen mit derselben Nummer
  bräuchten überall eine neue Antwort auf «welche davon?». Ausführlich am Modell
  (`models/instance.py`) und in `tests/test_quantity_rules.py`.*

- **Ein Auftrag und ein Abweichungsauftrag sind DASSELBE – der Unterschied ist ein Tag**
  (Juli 2026): Es gibt EINEN Weg, einen Auftrag anzulegen, EINE Tabelle, EIN Schema, EINEN
  Freigabe-Pfad. Der frühere Sonder-Endpunkt `POST /orders/{id}/deviation` bleibt als
  **Abkürzung**, ist aber kein zweiter Weg mehr – er teilt sich jede Regel mit der normalen
  Instanz-Auswahl.
  **Das Tag wird ABGELEITET, nicht angeklickt** (`subject.classify_pick`) – exakt so, wie
  die Retoure sich seit jeher ableitet: *die Auswahl bestimmt die Art des Auftrags.*
      alle frei am Lager           → gewöhnlicher Auftrag (kein Tag)
      alle verkauft                → Retoure      (Geld zurück, Original = Eltern)
      mindestens eine **gebunden** → Abweichung   (in Arbeit · reserviert · gesperrt)
  «Gebunden» heisst: die Instanz existiert, ist aber nicht frei verfügbar. Auf so etwas
  zuzugreifen KANN nur eine Abweichung sein – darum ist das Tag die **Folge** der Auswahl,
  nicht ihre Voraussetzung. `_validate_pins` kennt kein Vorab-Flag mehr und lässt **jede
  aktive Instanz** zu (nur Verschrottetes ist raus); der Picker zeigt gebundene Stück mit
  einem gelben Punkt und erklärt sie im Hover.
  **Der Eltern-Auftrag wird ebenfalls abgeleitet** (`subject.holding_order`): es ist der
  laufende Auftrag, der das Stück gerade in der Hand hat. Läuft keiner mehr (späte
  Reklamation an fertiger Ware), steht die Abweichung allein – das ist erlaubt.
  **Und die Unterdeckung wird SOFORT entschieden.** Nimmt die Auswahl einem laufenden
  Auftrag sein Stück weg, entsteht dort im selben Moment eine Fehlmenge; sie stillschweigend
  offen zu lassen hiesse, den Eltern ohne Entscheidung hängen zu lassen. Darum antwortet der
  Server mit **409 und nennt die betroffenen Aufträge**, bis eine der drei bekannten
  Antworten mitkommt (`OrderUpdate.shortfall_response` bzw. `OrderDeviationCreate`):
  **warten** (Fehlmenge bleibt offen – der Eltern wird nicht fertig) · **ersetzen**
  (`recovery.cover_shortfall`) · **ohne Ersatz weiter** (`recovery.confirm_quantity`).
  Die «Pause» des Eltern dauert damit genau so lange wie die Eingabe – es braucht keinen
  eigenen Pause-Mechanismus. Beide menschlichen Einstiege (Auswahl im Auftrag,
  Abkürzungs-Knopf an der Instanz) teilen sich `_assert_answered`/`_apply_shortfall_answer`;
  **systemseitig** angelegte Abweichungen (Auto-Abweichung nach Datenerfassung,
  Artikel-Deaktivierung) gehen direkt über den Service und lassen die Fehlmenge offen –
  dort entscheidet später ein Mensch am Auftrag.
  **Der eine verbleibende Unterschied ist keiner der Abweichung, sondern des Subjekts:** ein
  Auftrag auf **fixierte** Instanzen (Abweichung, Retoure, Bereitstellung) fährt NICHT den
  Artikel-Prozess (`order_step_defs`) – der beschreibt, wie etwas ENTSTEHT, und die Teile
  gibt es schon. Er braucht seinen eigenen Ablauf; alles andere (Modell, Felder, Status-Fluss,
  Freigabe, Prozessschritt-Module, Unter-Aufträge) ist identisch.
  Wächter: `test_an_order_and_a_deviation_order_are_the_same_thing`,
  `test_taking_a_busy_instance_forces_the_shortfall_decision`.

- **Testnotizen-Runde 24 (die EINE Pause-Regel, Notizen #352–#359)**: Der rote Faden ist,
  dass ein Auftrag genau EINEN Grund kennt, stillzustehen – und dass dieser Grund eine
  **Entscheidung** ist, kein Nebeneffekt.
  (1) **Ein Auftrag mit offener Fehlmenge ruht – ganz** (#354, `process.is_paused`). Die
  Zwischenstufe «eine Fehlmenge hält nur auf, wer die Menge weitergibt» (Registry-Flag
  `EventType.hands_over`, nur Verkauf und Ressource) ist zurückgenommen: solange eine
  Abweichung offen ist, darf der Eltern-Prozess nicht weiterlaufen. Der Grund ist nicht
  Vorsicht, sondern Reihenfolge – wer weiterarbeitet, während noch offen ist, ob ein Stück
  ausgesteuert wird, arbeitet womöglich am falschen Bestand. **Trotzdem gibt es dafür
  keinen eigenen Mechanismus:** die Abweichung nimmt ihr Stück heraus
  (`deviated_instance_ids`), daraus wird eine Unterdeckung, und eine Unterdeckung hält den
  Auftrag an. Ausschuss und weggenommene Reservierung erzeugen denselben Zustand über
  denselben Weg – es gibt kein «pausiert wegen Abweichung» neben «es fehlt etwas».
  Das ist unter dem Strich **eine Regel weniger**: `hands_over` und `SUBJECT_STEP_TYPES`
  sind beide entfallen, und `step_shortfalls` fragt für JEDEN Schritttyp dasselbe –
  die Fehlmenge des **Auftrags** plus den **eigenen** Material-Bedarf des Schritts
  (`_component_shortfall`, nur die Ressource hat einen). Die Pause ist heute kein stiller
  Nebeneffekt mehr, sondern die gewählte Antwort «Auftrag pausieren»; wer nicht warten
  will, ersetzt oder reduziert und läuft im selben Moment weiter. Neu ist auch, dass ein
  abgewiesener Schritt den **echten** Grund nennt (`process._not_now`): «Der Prozess ruht …
  bitte zuerst entscheiden» statt «ist (noch) nicht an der Reihe».
  (2) **Eine Frage, ein Fenster** (#352, `components/erp/shortfall-dialog.tsx`): Die drei
  Antworten heissen jetzt, wie sie sich auswirken – **Auftrag pausieren · Instanz ersetzen ·
  Auftragsmenge reduzieren** – und stehen in EINER kleinen Lightbox, die von beiden
  Einstiegen benutzt wird (Auswahl gebundener Instanzen im Auftrag/an der Instanz sowie die
  Unterdeckung am laufenden Auftrag). «Ersetzen» führt dort eine Ebene tiefer auf die
  gewohnten zwei Wege der Herkunft (älteste zuerst ↔ bestimmte Instanzen) – keine zweite
  Entscheidung, nur die Ausführung der ersten. Die drei früheren Eigenbau-Leisten
  (`ProcessHoldNotice`, `PositionRow`, `instance-detail`) sind darin aufgegangen.
  (3) **Unter-Aufträge stehen ZWISCHEN den Modulen** (#353, `SubOrderCard`): Abweichung,
  Nachschub und Bereitstellung sind dasselbe Muster – ein eigener Auftrag, hervorgegangen
  aus einem Schritt (`origin_step_id`) – und sehen darum gleich aus: ein eingerückter
  Knoten an seiner Stelle im Fluss. Vorher waren es drei Darstellungen (Bereitstellung als
  vollwertige Karte, Abweichung als Pille **seitlich** neben der Karte via `.erp-devbranch`,
  Abweichung ohne Ursprungsschritt als Abzweig davor). Eine Pille am Rand liest sich als
  Randnotiz – dabei ist eine offene Abweichung der Grund, warum alles ruht. Genau dort
  steht jetzt auch das «Es fehlt …» (#354): bei dem Unter-Auftrag, der die Menge bindet,
  statt zusätzlich als Kasten unter dem Fluss. Und: **ein blockierter Schritt zeigt sein
  Panel weiterhin** – was darin schon erledigt wurde (eine eingeholte Offerte, erfasste
  Werte), darf nicht verschwinden, nur weil der Prozess ruht.
  (4) **Der Bedarf eines ENTWURFS ist bearbeitbar – bei jedem Auftrag** (#355): Der
  Abkürzungs-Knopf an der Instanz nimmt einem die erste Auswahl ab, er soll sie nicht
  festnageln; weitere Instanzen oder Positionen ergänzt man wie überall. Dazu **kein
  Mischmasch**: freie und gebundene Stücke gehören nicht in denselben Auftrag (der freie
  Teil wäre ein gewöhnlicher Bedarf, der gebundene nimmt einem laufenden Auftrag etwas
  weg) – dieselbe Regel und dieselbe Form wie beim Verkauft/Lager-Mix. Beide Seiten lesen
  dieselbe Definition (`subject.is_bound`, aus `classify_pick` herausgezogen): der Server
  weist ab, die Oberfläche sperrt die jeweils andere Sorte, sobald die erste gewählt ist.
  (5) **«Auswählen» braucht genug wählbaren Bestand** (#356): gemessen am GANZEN Pool
  (frei + gebunden), nicht nur am freien – sonst wäre die Option eine Sackgasse, deren
  Auswahl sich nie vervollständigen liesse. Gesperrt mit dem Grund im Hover.
  (6) **Weltkarte** (#357): der Ausschnitt ist die **Bounding-Box der Landzellen** statt des
  vollen 72×25-Rasters (links standen drei reine Wasser-Spalten) – abgeleitet, damit er bei
  jeder Masken-Änderung stimmt; `regionAnchor` rechnet in denselben Koordinaten. Und die
  Beschriftung überlebt den Hover: unter dem Cursor wird die Fläche mit dem **kräftigen**
  Ton nachgezeichnet – genau der Ton, der auch die Schriftfarbe war –, also schreibt sie
  dort weiss. (7) Betriebskosten ohne Erklärabsatz (#358 – die Badge «gemessen · fix ·
  geschätzt» steht bereits an jeder Zeile); Status-Badge im gemeinsamen `DetailHeader` eine
  Spur grösser (#359, 11.5 px) – weil nur diese eine Stelle sie rendert, gilt das für jeden
  Datensatztyp gleich.
  Wächter: `test_a_shortfall_pauses_the_whole_order`,
  `test_the_pause_has_no_mechanism_of_its_own`,
  `test_a_deviation_pauses_the_order_through_the_shortfall_not_a_second_rule`,
  `test_the_subject_shortfall_is_type_agnostic`,
  `test_a_pick_never_mixes_free_and_bound_instances`,
  `test_a_refused_step_names_the_real_reason`.

- **Testnotizen-Runde 25 (eine Auswahl ist eine Menge, Notizen #360–#368, Migration `095`)**:
  *(#367/#368 waren wortgleich #353/#354 – sie waren beim Testen nur noch nicht deployt.)*
  (1) **Eine Auswahl beansprucht eine MENGE, kein Ding** (#361, `reservation.claim`): Von
  einer Charge à 500 liess sich bisher nur die GANZE Instanz wählen – bei einer Abweichung
  ist aber fast immer genau EIN Stück betroffen. Die Menge landet jetzt dort, wo sie
  hingehört: in derselben Reservierungs-Map, in die die FIFO-Allokation längst mengengenau
  schreibt. `reserve` **addiert** (FIFO füllt auf), `claim` **setzt** (der Mensch bestimmt)
  – zwei Formen derselben Sache, keine neue Spalte. Das Kürzen fremder Ansprüche ist dabei
  kein Nebeneffekt, sondern der Kern: nimmt eine Abweichung ein Stück aus einer Charge, die
  ein laufender Auftrag gedeckt hatte, schrumpft **genau dessen** Reservierung – und damit
  meldet er die Unterdeckung von selbst. `subject.is_bound` fragt seither nach der
  **gewünschten** Menge (3 von 5 freien ist ein gewöhnlicher Bedarf, erst 4 eine Abweichung),
  und `deviated_instance_ids` ist zu `deviated_quantities` geworden. Gegenstück:
  `detach_sub_order` gibt den Anspruch zurück – ohne das behielte der Eltern seine Fehlmenge
  für immer (im Praxistest gefunden).
  (2) **Bleibt nichts übrig, IST das der Abbruch** (#366): Der «Abbrechen»-Knopf im
  Auftragskopf ist entfallen. Einen Auftrag abzubrechen heisst, seine Teile in einen anderen
  zu überführen – und genau das tut man, indem man einen Auftrag anlegt und dessen Instanzen
  auswählt. Der Eltern meldet dann eine Unterdeckung, und wenn ihm **nichts** bleibt, ist
  «Auftragsmenge reduzieren» sein Abbruch (`recovery.confirm_quantity` → `abort_parent`,
  `into` = der fortführende Auftrag). Vorher lief genau dieser Fall in einen 409 («ergäbe
  Menge 0») und der Auftrag stand ohne Ausweg. `OrderDeviationCreate.abort_parent` ist
  entfallen – dieselbe Entscheidung, deren Konsequenz mit dem Rest skaliert.
  (3) **Eine Auswahl, drei Sorten** (#360): frei (grün) · gebunden (gelb) · **verkauft**
  liegen in DEMSELBEN Picker; die Sorte bestimmt die Art des Auftrags (`classify_pick`).
  Der separate `RefundSubjectPicker` ist entfallen – auch eine Rücksendung muss genau sagen,
  WELCHES Stück zurückkommt, FIFO ergäbe dort keinen Sinn. Verschrottet bleibt die eine rote
  Ausnahme (daran ist nichts mehr zu tun); **«Gesperrt» ist gelb** – es lässt sich entsperren
  (der Wert stand längst auf `TONE.pending`, nur der Kommentar behauptete noch Rot).
  (4) **Ein Unternehmen ist schliessbar – endgültig** (#364/#365, `company_settings.is_active`):
  Status war «Unternehmen» – das ist die Datensatzart und steht bereits als Eyebrow. Jetzt
  dieselben zwei Wörter wie überall: **Freigegeben** / **Inaktiv**. Dazu ein Schliessen-Knopf
  im Kopf. **Keine Reaktivierung** (bewusst entschieden): eine wiedereröffnete Gesellschaft
  ist rechtlich eine andere – neue UID/EIN, neues HR-Datum, neue Belegkreise; sie als
  dieselbe weiterzuführen hiesse, auf ihren Belegen eine Rechtsperson zu nennen, die es so
  nicht mehr gab. Geschützt bleiben der **Betreiber** (Absender der einen Website) und die
  **letzte** Gesellschaft; die Gebiete der geschlossenen fallen an den Betreiber zurück.
  (5) **Weltkarte** (#362/#363): runde Ecken wie jede andere Karte; die Beschriftung
  überlebt den Hover (auf der kräftig nachgezeichneten Fläche schreibt sie weiss – vorher
  war Schriftfarbe == Füllfarbe).
  Wächter: `test_a_pick_claims_a_quantity_not_a_thing`,
  `test_a_company_can_be_closed_but_never_reopened`, `test_abort_is_a_deed_not_a_request`,
  `test_the_order_level_deviation_is_the_abort`.

- **Testnotizen-Runde 26 (der Entwurf nimmt niemandem etwas weg, Notizen #369–#373)**:
  (1) **Ein Entwurf merkt vor, die Freigabe wird scharf** (#370, `reservation.claim` /
  `enforce`): Die Unterdeckungs-Frage stand beim **Auswählen** – zu früh, denn danach
  definiert man den Auftrag ja erst fertig (Artikel, Menge, Instanzen können sich noch
  ändern), und die Entscheidung über den anderen Auftrag wäre womöglich gleich wieder
  falsch. Jetzt sind es drei Formen derselben Sache, klar nach ihrem Moment getrennt:
  `reserve` **addiert** (FIFO füllt auf) · `claim` **setzt** (der Mensch wählt, ohne
  jemandem etwas wegzunehmen – die Summe darf die Instanz-Menge übersteigen, `free_qty`
  fällt auf 0, für FIFO ist das Stück gesprochen) · `enforce` **setzt sich durch** (bei der
  Freigabe: wer dadurch zu viel hätte, verliert entsprechend – **daraus** entsteht die
  Unterdeckung). Gefragt wird dort, wo es weh tut: `_enforce_claims` an der Freigabe;
  `enforce` selbst sitzt in `subject._bind_deviation_subjects`/`_allocate_stock_for`, damit
  auch die **systemseitige** Abweichung (fehlgeschlagene Datenerfassung, Artikel-
  Deaktivierung) scharf wird und nicht nur der Weg über den Router. Folgerichtig zählt für
  `deviated_quantities` nur noch eine **freigegebene** Abweichung.
  (2) **EIN Weg, einen Auftrag anzulegen** (#371): Der Sonder-Endpunkt
  `POST /orders/{id}/deviation` samt `OrderDeviationCreate` ist entfallen. Der
  Abkürzungs-Knopf an einer Instanz legt einen **ganz gewöhnlichen** Auftrag an und trägt
  die Instanz nur **vor** (`OrderCreate.instance_object_ids`) – Eingabehilfe, keine
  Fixierung: abwählen, ersetzen, ergänzen geht wie überall, und **das Tag folgt mit**
  (`_clear_derived_marker` – vorher blieb «Abweichung» kleben, wenn man auf eine freie
  Instanz wechselte). Damit ist auch der zweite Knopf «Abweichung melden» an der Instanz
  entfallen: es gibt einen Knopf, und was daraus wird, sagt der Zustand der Instanz.
  (3) **Was den Schritt AUFHÄLT, steht VOR ihm** (#372): Abweichung und Nachschub sind
  Hindernisse – von oben nach unten gelesen «erst das hier, dann dieser Schritt». Vorher
  standen sie **unter** einem Schritt, den man womöglich noch gar nicht begonnen hatte. Die
  **Bereitstellung** ist das Gegenstück (sie folgt aus dem Schritt) und behält ihre
  deklarierte Stufe (`_STAGE_BEFORE`).
  (4) **Die Mengen-Eingabe kappt, statt zu meckern** (#373, `QtyChip`): Wer in ein Feld
  tippt, das schon «2» enthält, erzeugt kurz «21» – ging das direkt an den Server, kam
  «Instanz … hat nur 2». Jetzt lebt die Eingabe lokal, wird auf das Machbare gekappt und
  erst beim Verlassen übernommen; die Server-Prüfung bleibt das Netz.
  (5) **Weltkarte: 810 gefilterte Knoten → 7** (#369): jede 5°-Zelle war ein eigenes
  `<rect>` unter einem SVG-Filter – und der Filter (Offscreen-Puffer + Weichzeichner +
  Alpha-Schnitt) ist die teure Stelle, die beim Hereinscrollen zuschlug. Die Form ist
  identisch, steht aber je Region in EINEM `<path>`; dazu eine eigene Rasterebene
  (`willChange`/`contain: paint`), damit beim Scrollen nur noch zusammengesetzt wird.
  **Zwei echte Fehler dabei gefunden** (Praxis-Durchlauf, beide behoben): `holding_order`
  fand den Auftrag nicht mehr, der ein Stück über seine **Reservierung** hält, sobald ein
  Entwurf die Subjekt-Bindung an sich gezogen hatte – die Freigabe fragte darum niemanden
  (jetzt `subject.holding_orders`, alle drei Wege: Subjekt · Erzeuger · Anspruch). Und
  `_enforce_claims` las, bevor geschrieben war (`autoflush=False`): kommen Auswahl und
  Freigabe in EINEM Aufruf, stand die Bindung noch nicht in der Datenbank und die Frage
  blieb still aus.
  Wächter: `test_the_shortfall_question_comes_at_release_not_at_the_pick`,
  `test_there_is_exactly_one_way_to_create_an_order`,
  `test_a_pick_claims_a_quantity_not_a_thing`.

- **Testnotizen-Runde 27 (ein Unter-Auftrag steht an seiner Stelle, Notizen #375–#378)**:
  (1) **Die Abweichung stand im Ablauf ganz vorne – vor einem längst erledigten Schritt**
  (#377). Ein Unter-Auftrag bekommt seine Position aus `orders.origin_step_id`; vergeben
  wurde sie aber nur auf dem **systemseitigen** Weg (`create_deviation`). Seit die
  menschliche Anlage über die Instanz-**Auswahl** läuft (#371) war der einzige von Menschen
  benutzte Weg der eine, der sie **nicht** vergab – ohne Position landet ein Unter-Auftrag
  im «gehört dem Auftrag»-Topf und wird über dem Prozess gezeigt. Die Zuordnung gibt es
  jetzt **einmal** (`deviation.interrupted_step_id` = der Schritt, an dem der Eltern gerade
  steht), und **beide** Wege benutzen sie; wer die Auswahl zurücknimmt, verliert die
  Position wieder (`_clear_derived_marker`).
  **Im selben Zug ist die Darstellung eine Sache geworden:** `OrderStepInfo` trug für diese
  eine Aussage **drei** Felder (`provisionings` + `provisioning_stage` + `deviations`, dazu
  das nie befüllte `provisioning_order_object_ids`), und das Frontend setzte sie mit einer
  Fallunterscheidung wieder zusammen. Jetzt ist es **eine Liste** `sub_orders`, und jeder
  Unter-Auftrag trägt seine Position selbst (`stage` ∈ before | after, im Backend
  abgeleitet: Hindernis → davor · Bereitstellung → nach ihrer deklarierten Stufe). Das
  Frontend sortiert nur noch ein. Nebenbei erscheinen damit **Nachschub und Bereitstellung
  ohne Ursprungsschritt** überhaupt zum ersten Mal (sie wurden nirgends gerendert), und ein
  **zurückgenommener** Unter-Auftrag belastet den Ablauf nicht mehr – für alle drei Arten
  dieselbe Regel.
  (2) **Ruht der Auftrag, ruht der ganze Fluss** (#378): Das Backend lehnte jede Ausführung
  schon immer mit 409 ab (`process.is_paused` → jeder Schritt `blocked`), die Oberfläche
  zeigte den Schritt aber weiter in Modulfarbe und öffnete sein Panel – man konnte also
  weiterarbeiten wollen und lief in eine Fehlermeldung. Jetzt tritt **jedes** Modul zurück
  und keines lässt sich anwählen; farbig bleibt nur der Unter-Auftrag, der zu klären ist.
  EINE Regel am Fluss (`OrderFlow paused`), keine Fallunterscheidung je Schritt. Damit ist
  die Zeile «Bestand fehlt» am einzelnen Schritt entfallen – bei einem ruhenden Auftrag
  stünde sie an **allen**, obwohl es nur einen Grund gibt; der steht beim Unter-Auftrag,
  der die Menge bindet (#354). *Das revidiert die Ausnahme aus Runde 24 («ein blockierter
  Schritt zeigt sein Panel weiterhin») ausdrücklich.*
  (3) **Die Unterdeckungs-Frage ist eine Palette** (#375/#376): der Erklärabsatz ist
  entfallen (der Titel sagt, worum es geht; WAS fehlt steht im Ablauf), und die drei
  Antworten sind **Symbole, deren Name beim Hover aufklappt** – dieselbe Geste wie bei den
  Prozessschritt-Modulen. Sie kommt jetzt aus EINER Implementierung (`fields.PaletteButton`),
  die sich Modul-Palette, Erfassungsfeld-Palette und Unterdeckungs-Frage teilen.
  Wächter: `test_a_sub_order_knows_which_step_it_interrupted`,
  `test_sub_orders_know_where_they_came_from`, `test_open_provisioning_holds_the_whole_order`.

- **Testnotizen-Runde 28 + Tiefen-Cleanup (Notizen #379–#381)**:
  (1) **Der Zustand eines Datensatzes wird an EINER Stelle abgeleitet** (#379,
  `lib/record-status.ts`): Der ERP-Feed baute die Status-Badge in einer fünfarmigen
  Fallunterscheidung selbst, jedes Detailfenster noch einmal – zwei Stellen für dieselbe
  Aussage, und sie sind auseinandergelaufen: am Unternehmen zeigte der Feed hart verdrahtet
  **«Unternehmen»** (die Datensatz*art*!), während das Detail längst «Freigegeben»/«Inaktiv»
  sagte. Leiser, aber derselbe Fehler: das Benutzer-Detail liess das Symbol der Rollen-Badge
  weg. Die Lösung ist die, die es für den **Namen** längst gibt (`record-name.ts`, #177):
  eine Ableitung je Typ (`userStatus`/`articleStatus`/`orderStatus`/`instanceStatus`/
  `organizationStatus`), gelesen von Feed **und** Detail. Der Feed verteilt nur noch, er
  baut nichts mehr; `ROLE_CFG` ist aus `user-detail.tsx` (einer Komponente!) in die
  `lib`-Ebene gewandert, und «fällig» (wiederkehrend & Termin erreicht) gilt jetzt auch im
  Detail. **Fest verankert** durch `tests/test_frontend_mirrors.py:
  test_record_status_is_derived_in_exactly_one_place`: ein Status-Literal (`label` +
  `color`/`bg`) darf nur unter `lib/` stehen – der Wächter ist gegen die gemeldete Bug-Form
  gegengeprüft.
  (2) **Der Auftrag-Shortcut trägt den Ton des Zustands** (#380): ist die Instanz gebunden
  (gelbe Badge), wird aus dem Auftrag eine Abweichung – also sieht der Knopf schon vorher so
  aus (gelb statt slate, mit passendem Hover-Text). Das ist **keine zweite Regel**, sondern
  ein Blick auf dieselbe Badge (`status-flow.isPending`); die Entscheidung trifft weiterhin
  allein die Auswahl im Auftrag (`subject.classify_pick`).
  (3) **«Es fehlt …» am Unter-Auftrag entfällt** (#381) – dass der Prozess seinetwegen ruht,
  sagen die Pause am Knoten und der zurückgetretene Fluss; die Props `missing`/`waitingFor`
  am `OrderFlow` sind mit entfallen.
  **Tiefen-Cleanup im gleichen Zug** (netto −33 Zeilen bei 52 Dateien, ohne
  Verhaltensänderung): `fmtObjId` war ein historischer **Alias** auf `formatObjectId` –
  ausgerechnet re-exportiert aus `user-detail.tsx`, sodass 22 Dateien ihre Zahlen-
  Formatierung aus einem Detailfenster importierten; jetzt ein Name, ein Zuhause
  (`lib/utils`). Die Wer/Wann-Zeile («Name · 31.07.26, 21:52») entstand an vier Stellen
  einzeln → `utils.actorHint`/`localDateTime`. Die **Palette** (Symbol + aufklappender
  Name) stand dreimal → `fields.PaletteButton`. Tot und entfernt: `pricing.price_view`
  (0 Aufrufer), `lib/consent.hasConsent`, `PROCESS_MODE_LABEL`, `status-flow.
  lifecycleActions`, die **zweite** `SelectField`-Fassung in `fields.tsx`, die Komponente
  `ObjectLabel` (der Etikettendruck läuft seit #117 über den Kopf-Knopf), die CSS-Klassen
  `.erp-tool*`, `provisioning.sub_orders_for_step` sowie sechs ungenutzte Importe. Die
  80-Zeilen-Regel gilt wieder im ganzen ERP-Kern: `update_order` 92→36 (`_pop_pick_inputs`/
  `_assert_payload`/`_apply_fields`/`_do_release`), `_subject_shortfalls` 86→30
  (`_subject_targets` = das Soll, `_secured_amounts` = was der Auftrag schon hat),
  `return_subjects_to_stock` 88→38 (`_restock_one`), `references.instance_orders` 90→8
  (`_instance_hits` sammelt, `_order_rows` baut). *Bewusst NICHT angefasst:* `render_pdf`/
  `run_chat`/`fulfill_intent` (dokumentierte Ausnahmen ausserhalb des ERP-Kerns),
  `main._ensure_columns` (das Lifespan-Netz für Kosmetik anzufassen wäre nach der
  Migration-090-Geschichte das falsche Risiko), die `.ix-*`-Primitiven des
  Design-System-Exports (eine Design-Sprache prunt man nicht nach heutiger Nutzung) und die
  **Alt-Palette** in den Website-/Shop-Seiten (Big-Bang-Migration ist ausdrücklich nicht der
  Weg – beim Anfassen mitziehen).
- **«Inaktiv ist ein Zustand, kein Verschwinden» – die zweite Benutzerverwaltung ist
  aufgelöst** (Juli 2026, Folgeschritt zum Cleanup): `/admin/benutzer` war eine **zweite,
  nicht verlinkte** Benutzerverwaltung in der Alt-Palette – mit eigener Tabelle und einer
  dritten Rollen-Konfiguration. Sie war aber nicht einfach überflüssig: sie trug als
  **einzige** das Deaktivieren/Reaktivieren einer Person, denn der ERP-Feed zeigte nur
  **aktive** Benutzer. Genau daraus folgte ihre Existenz.
  **Die Wurzel war eine Ungleichbehandlung derselben Sache:** ein ausser Betrieb genommener
  **Artikel** behält `is_active=True` und bekommt `status='inactive'` – er bleibt im Feed
  und trägt eine rote Badge. Eine **Person** (und eine **Gesellschaft**) haben keine
  Status-Spalte; dort setzt die Deaktivierung `is_active=False`, und der Datensatz
  **verschwindet**. Derselbe fachliche Vorgang, zwei Verhalten – und für den einen braucht
  es dann zwangsläufig eine zweite Oberfläche.
  Jetzt gilt für **jeden** Datensatztyp dieselbe Regel: er bleibt im Feed und trägt
  «Inaktiv» (rot). Konkret: `GET /erp/records` (+ Detail, + Bestellungen, + Änderung) filtert
  `is_active` nicht mehr, `userStatus` projiziert *deaktiviert ≻ Rolle*, und der
  Benutzer-Datensatz trägt die Aktionen **Deaktivieren/Reaktivieren** im Kopf – dieselbe
  Anatomie wie das Schliessen am Unternehmen. Die Fachlogik bleibt unangetastet, wo sie
  steht (Selbst-Schutz, System-KI, Blockade bei offenen Dokument-Freigaben in
  `admin.deactivate_user`); die Oberfläche ruft sie nur.
  **Dieselbe Regel für die Gesellschaft – und damit ein stiller Fehler aus Runde 25
  behoben:** eine geschlossene Gesellschaft fiel ersatzlos aus dem ERP, ihre Historie war
  über **keine** Oberfläche mehr erreichbar. `all_companies` liefert jetzt wirklich *alle*
  (Feed); wer eine **Auswahl** braucht (wem lässt sich ein Gebiet zuweisen?), nimmt
  `selectable_companies` – zwei Fragen, zwei Namen, statt eines Filters, der beides meint.
  **Und ein zweiter Schreibpfad ist mit entfallen:** `PATCH /admin/users/{id}/role` (+
  `UserRoleUpdate` + `api.updateUserRole`) – die Rolle wird am ERP-Datensatz gepflegt
  (`PATCH /erp/records/{object_id}`, inkl. KI-Schutz). Dieselbe fachliche Angabe darf nie an
  zwei Stellen editierbar sein.
  Wächter: `tests/test_frontend_mirrors.py: test_a_person_is_managed_in_exactly_one_place`
  (Seite weg, kein zweiter Rollen-Pfad, Feed/Detail ohne `is_active`-Filter) und
  `test_a_company_can_be_closed_but_never_reopened` (Feed ja, Auswahl nein, Betreiber
  geschützt). Gegen echtes PostgreSQL verifiziert (`/var/tmp/ixpg/inactive.py`, 7/7).

- **Testnotizen-Runde 29 (wer keine Frage beantworten kann, wird nicht gefragt; Notizen
  #382–#388)**: Kern ist die **Abweichung auf eine Abweichung** – ein realer Fall, sobald
  man mit einer Klärung unzufrieden ist und eine zweite danebenstellt.
  (1) **Ein Auftrag mit festem Subjekt hat kein Soll – also auch keine Fehlmenge** (#388).
  «Menge reduzieren» lief bei ihm auf «Keine Fehlmenge – es gibt nichts zu reduzieren» auf,
  weil die Antwort auf **alle** Halter angewandt wurde. Eine Abweichung (ebenso Retoure/
  Bereitstellung) beschafft aber nichts – sie **behandelt** vorhandene Stücke. Nimmt ihr
  jemand eines weg, entsteht keine Unterdeckung: sie hat weniger zu tun. Bleibt ihr
  **nichts**, ist sie **gegenstandslos** und wird abgebrochen, mit Zeiger auf den Auftrag,
  der übernommen hat (`recovery.retire_if_subjectless` + `subject.still_holds`) – exakt die
  Mechanik, die es für den Eltern längst gibt (#366). Und weil sie nichts zu entscheiden
  hat, wird sie auch nicht gefragt: `_enforce_claims` stellt die Frage nur, wenn ein Halter
  mit **Soll** betroffen ist. Das ist eine Regel weniger, nicht mehr.
  (2) **In Klärung zählt jede offene Abweichung, nicht nur der letzte Zeiger** (#388, die
  tiefere Wurzel): `deviated_quantities` las `instances.subject_of_order_id` – und der trägt
  immer nur die **zuletzt** gesetzte Bindung. Bei zwei Abweichungen an derselben Charge fiel
  die erste still aus der Rechnung, und der Eltern-Auftrag führte zu viel als «gesichert».
  Massgeblich ist jetzt die **Anspruchs-Map** (`instances.reservations`) – dort steht je
  Auftrag die beanspruchte Menge; der Zeiger bleibt nur Rückfall für Altbestand ohne
  Anspruch. Damit geht auch «2 statt 1 Stück» ohne jede Fallunterscheidung auf: greift die
  zweite Abweichung mehr, als frei ist, verliert die erste – und ist bei 0 gegenstandslos.
  (3) **Die Unterdeckungs-Frage nennt, wen sie trifft** (#387, `OrderResponse.affects`):
  Der Entwurf weiss **vor** der Freigabe, welchen laufenden Aufträgen seine Auswahl etwas
  wegnimmt – Name · Objektnummer · Artikel · Menge, und ob dieser Betroffene überhaupt eine
  Entscheidung braucht. Vorher erfuhr man es erst als Fehlertext mit blossen Objektnummern.
  Am **laufenden** Auftrag ist der Betroffene er selbst – dieselbe Liste, dieselbe Form.
  Mehrere Betroffene sind ausdrücklich vorgesehen (ein Auftrag darf Instanzen aus
  verschiedenen laufenden Aufträgen greifen).
  (4) **Eine fremde Abweichung erscheint nur, solange sie offen ist** (#382): der Grund, sie
  im Prozess eines anderen Auftrags zu zeigen, ist, dass sie ihm **gerade** sein Stück
  entzieht. Eine geklärte entzieht nichts mehr – als Knoten stehen zu bleiben behauptete
  einen Halt, den es nicht gibt. Ihre Geschichte steht an der **Instanz** («Aufträge»); die
  **eigenen** Kinder eines Auftrags bleiben unverändert sichtbar. (Präzisiert #350.)
  (5) **Der Instanz-Shortcut wählt immer EIN Stück vor** (#385): er ist eine Eingabehilfe,
  kein Vorgriff auf die Menge – von einer Charge à 500 will man selten alle 500 behandeln.
  `OrderCreate.instance_quantities` trägt die Teilmenge gleich bei der Anlage mit; ändern
  lässt sie sich im Entwurf wie gehabt (bis zur vollen Instanz-Menge).
  (6) **Die Kachel heisst, was sie misst** (#384): «Am Lager» statt «Bestand» mit der
  Unterzeile «Nicht am Lager» – letztere war eine schiefe Zustandsaussage neben der Badge
  (die Instanz IST im Betrieb, sie ist nur nicht verfügbar) und dazu eine Doppelung. Jetzt
  erklärt sich die 0 von selbst, das ⓘ entfällt, und die Unterzeile trägt nur noch die
  reservierte Menge – die steht sonst nirgends.
  (7) **Der Stückpreis steht im Hover an der Zahl, aus der er kommt** (#383): Summe ÷ Menge
  – also ein `data-tip` an «Bestellsumme netto» statt eines eigenen hervorgehobenen Kastens
  darunter (`fields.Row` kann jetzt einen Hinweis tragen).
  Wächter: `test_a_fixed_subject_order_is_never_asked_for_a_shortfall_answer`,
  `test_clarification_counts_every_open_deviation_not_just_the_last_pointer`,
  `test_a_cleared_foreign_deviation_is_no_longer_shown_as_an_obstacle`.

- **Ein Auftrag entsteht als Ganzes – oder es hat ihn nie gegeben** (Testnotiz #386):
  Bisher entstand ein Auftrag beim **Tippen**: das Anlage-Fenster speicherte per Auto-Save,
  sobald Artikel und Menge dastanden, vergab dabei eine Objektnummer und liess einen Entwurf
  zurück, wenn man es sich anders überlegte. Jetzt gilt: **der Entwurf lebt im Browser**,
  und die **Freigabe IST die Anlage** – erst dort bekommt er seine Nummer. Wer wegklickt,
  hat verworfen; es bleibt nichts zurück, schon gar nichts ohne Nummer.
  **Ein Endpunkt, ein Moment** (`POST /erp/orders`): Bedarf, weitere **Positionen**, der
  auftragseigene **Ablauf**, die **Instanz-Auswahl** und die Antwort auf eine dadurch
  ausgelöste Unterdeckung kommen in EINEM Aufruf an; intern laufen sie durch **dieselben**
  Dienste wie bisher (`_add_line`, `article_process._create`, `_set_chosen_instances`,
  `_do_release`) – kein zweiter Weg, nur ein anderer Zeitpunkt. Scheitert etwas, wird die
  Transaktion verworfen: kein halber Auftrag, keine verbrauchte Nummer.
  **Die Oberfläche merkt davon fast nichts**, weil der Entwurf **dieselbe Form** hat wie ein
  gespeicherter Auftrag: `record = saved ?? draft`, und alles Weitere liest `record`, ohne
  zu wissen, woher es kommt. Geschrieben wird je nach Herkunft – in die API oder in den
  State. Wo bisher ein Formular direkt die API rief, ist der **Speicher** zur Wahl geworden
  statt der Code verdoppelt: `lib/step-store.ts` (`apiStepStore` ↔ `draftStepStore`, negative
  Pseudo-ids) hinter EINEM Schritt-Editor, und `RecurrenceCard` bekommt sein `persist` vom
  Aufrufer. Die Position bringt ihre Auswahl **mit** (`OrderLineCreate.instance_object_ids`)
  – sonst ginge sie beim Erteilen verloren, weil es den zweiten Aufruf nicht mehr gibt.
  **Die Abkürzungs-Knöpfe legen nichts mehr an** (Artikel- und Instanz-Detail): sie öffnen
  dasselbe Fenster **vorbelegt** (`OrderSeed` – Artikel, ein Stück, ggf. die Instanz) und
  schreiben nichts. Genau sie waren die zweite Anlage-Stelle: sie mussten einen Datensatz
  erzeugen, um hinspringen zu können.
  **Die Unterdeckungs-Frage kommt als Code, nicht als Satz:** die 409-Antwort trägt
  `code: shortfall_decision_required` + `affects` (`ApiError.detail`) – der Entwurf kann sie
  nicht vorher lesen, es gibt ja keinen Datensatz. Die Oberfläche erkennt sie daran und
  stellt dieselbe Frage wie am laufenden Auftrag (vorher wurde im Meldungstext nach Wörtern
  gesucht – eine umformulierte Meldung hätte sie still verschluckt).
  Wächter: `test_an_order_is_created_as_a_whole_or_not_at_all`,
  `test_frontend_mirrors.py: test_an_order_is_created_at_exactly_one_place`; gegen echtes
  PostgreSQL verifiziert (12 Prüfungen: Ablauf/Positionen/FIFO je Position, Anker-Auswahl
  überlebt die Umwandlung in Position 0, Position bringt ihre eigene mit, 409 nennt die
  Betroffenen **und es bleibt kein Auftrag zurück**, mit Antwort entsteht die Abweichung).

- **Anteile statt Instanzen: du wählst keinen Gegenstand, sondern eine MENGE MIT EINEM NAMEN**
  (August 2026, Migration `096`): Eine Instanz ist eine Menge, kein Ding – und ihre Menge ist
  **immer vollständig aufgeteilt**: jeder Anteil gehört genau einem Auftrag oder ist frei.
  Genau so stand es seit den Bruchmengen in `instances.reservations`; sichtbar war es nie.
  Jetzt zeigt die **Auswahl diese Zeilen**: `Charge X · 2 Stk · Auftrag …456` statt
  `Charge X`. Damit ist mit dem Klick beantwortet, **wem** man etwas wegnimmt.
  **Das war die Lücke im Datenmodell.** Hält eine Charge à 4 zwei Ansprüche (Hauptauftrag 2,
  Abweichung 2) und ein dritter Auftrag greift 1 Stück, musste die Freigabe **raten**, wer
  verliert – bei EINEM anderen Halter zufällig richtig, ab zwei Willkür (`enforce` kürzte
  den erstbesten). Der gewählte Halter steht jetzt in `orders.pick_sources`
  (`{instanz_objektnr: quell_auftrag}`, `None` = frei); `reservation.enforce` kürzt genau
  den. Der genannte Anteil ist dabei eine **Rangfolge, keine Ausschliesslichkeit**: wer 2 aus
  einer 2er-Charge nimmt, an der zwei Aufträge hängen, trifft zwangsläufig beide.
  **Eine Eingabeform statt zweier Maps:** `InstancePick{instance_object_id, quantity,
  from_order_object_id}` ersetzt `instance_object_ids` + `instance_quantities` in
  `OrderCreate`/`OrderUpdate`/`OrderLineCreate`/`OrderLinePins` – dieselbe Struktur an allen
  vier Stellen.
  **Was daraus von selbst folgt** (jeweils ohne eigene Regel):
  (1) **Wer gefragt wird = wem der Anteil gehörte.** Ein **freier** Anteil gehört niemandem →
  niemand wird gefragt, keine Unterdeckung. Die Rangfolge steht an EINER Stelle
  (`shares.losers`): genannter Anteil ≻ **Erzeuger** ≻ übrige Ansprüche, und nur so weit,
  wie wirklich etwas fehlt.
  (2) **Abweichung von der Abweichung braucht keinen Sonderfall.** Man klickt die Zeile des
  Abweichungsauftrags an – fertig. Gefragt wird er trotzdem nicht: eine Abweichung hat
  **kein Soll**, sondern eine Arbeitsmenge; nimmt man ihr etwas weg, hat sie weniger zu tun,
  und bleibt nichts, ist sie gegenstandslos (war schon so, gilt jetzt sichtbar).
  (3) **Der unbeanspruchte Rest ist nur AM LAGER frei** (`shares._creator`): steckt die
  Instanz noch in ihrem Erzeugungsauftrag, gehört der Rest IHM. Sonst zeigte die Auswahl
  «frei» an einem Stück mitten im Prozess, und der Erzeuger würde nicht gefragt.
  (4) **«Ersetzen» nur, wenn dem Auftrag egal ist, WELCHES Stück es ist**
  (`recovery.is_replaceable`, `StepShortfall.replaceable`): ein frisches Stück ist kein
  Ersatz, wenn das Fehlende die Geschichte dieses Auftrags trägt – er hat es **selbst
  erzeugt** oder ein Schritt hat **schon daran gearbeitet** (steht der Ablauf bei Schritt 3,
  hat ein neues Teil die Schritte 1–2 nie durchlaufen). **Material** ist immer austauschbar:
  der Auftrag braucht *fünf Schrauben*, nicht *diese fünf*. EINE Ableitung statt einer
  Fallunterscheidung je Auftragsart – und breiter als «nur Ressourcenmodul»: auch ein
  Verkauf ab Lager darf ersetzen, solange niemand daran gearbeitet hat.
  (5) **Der Wechsel ist dokumentiert – für FIFO wie für Hand-Auswahl gleich**
  (`subject.enforce_pick` → Event `order.share_taken`, gerendert als `StepResolution` am
  Schritt des **verlierenden** Auftrags): «1 Stk Instanz …123 → Auftrag …456». Und
  «Ersetzen» hält fest, **welche** Instanzen eingesprungen sind. Kein neues Feld, der
  Event-Strom trägt es.
  **Sichtbar auf beiden Seiten** (die Frage aus der Analyse): der Ursprungsauftrag zeigt
  unter seiner Instanz-Zeile «2 Stk → Auftrag …456» (`order-positions.tsx: ForeignShares`),
  das Instanz-Detail dieselbe Aufteilung aus der anderen Richtung. Kommt der Anteil zurück,
  verschwindet die Zeile.
  **Ein echter Fehler nebenbei gefunden** (gegen echtes PostgreSQL): `article_process._create`
  committete für sich – schlug bei der Auftrags-Anlage danach etwas fehl (z. B. die offene
  Unterdeckungs-Frage), blieb ein Auftrag **ohne Objektnummer** zurück. Genau das, was
  Testnotiz #386 abschaffen sollte; der Fall war nur in einem Test ohne Prozessschritte
  geprüft worden. `commit=False` bringt den Schritt in die Transaktion des Aufrufers.
  Wächter: `test_a_pick_names_the_share_it_takes`,
  `test_the_creator_holds_the_rest_until_it_reaches_stock`,
  `test_replacement_is_only_offered_when_the_piece_is_interchangeable`,
  `test_an_order_is_created_as_a_whole_even_with_steps`,
  `test_frontend_mirrors.py: test_the_picker_offers_shares_not_instances`.
  *Bewusst NICHT gebaut: die Restmenge nach «Menge reduzieren» automatisch nachbestellen –
  das ist ein ganz normaler neuer Auftrag, und der ist seit #386 ein Klick. Eine Kopplung
  brächte lauter Sonderfälle (welche Schritte? welche Instanzen? gepinnt?) zurück.*

- **Testnotiz #389 (der Kopf des Anlage-Fensters ist derselbe wie überall)**: Beim Anlegen
  fehlten die Reiter, der Titel war ein Platzhalter statt des abgeleiteten Namens, und ein
  «Abbrechen»-Knopf stand im Kopf – drei Abweichungen von der EINEN Anatomie (`DetailHeader`,
  Notiz #242). Jetzt: **Name** wie überall (sobald ein Artikel gewählt ist, heisst der Entwurf
  danach), **Reiter** stehen da (mit «Dokumente» gesperrt – die hängen an der Objektnummer,
  Grund im Hover), und die Nummer ist ein schlichtes **«—»** mit der Erklärung im Hover
  (`DetailHeader.objectIdHint`) statt eines Satzes in der Fläche. **Kein «Abbrechen»**:
  verworfen wird, indem man woanders hinklickt – ein Knopf dafür wäre ein zweiter Weg für
  etwas, das ohnehin von selbst passiert (#386).

- **Testnotizen #390/#391 (Teilmenge einer Charge – die Auswahl folgt den Zeilen, und die
  Frage nennt die richtige Zahl)**: Zwei Befunde aus demselben Vorgang «1 von 4 Stück einer
  Charge in eine Abweichung nehmen».
  (1) **1 von 4 ging nicht, 2 von 4 schon** (#390). Der Abkürzungs-Knopf an der Instanz
  merkte «1 Stk, **frei**» vor – aber eine Charge, die noch in ihrem Erzeugungsauftrag
  steckt, hat gar keinen freien Anteil (`shares._creator`: der Erzeuger hält den Rest). Die
  Vormerkung zeigte damit auf eine Zeile, die es in der Auswahl nicht gibt: unsichtbar, aber
  **zur Menge gezählt** – bei Auftragsmenge 1 galt die Zeile als «schon beisammen» und liess
  sich nicht mehr anklicken; bei Menge 2 war das Limit nicht erreicht, also ging es. Zwei
  strukturelle Korrekturen: die Vorauswahl **nennt** ihren Halter (`OrderSeed.instance.
  fromOrderObjectId`, gelesen aus `inst.shares`), und die Auswahl **folgt** dem aktuellen
  Stand (`reconcilePicks`) – ein Anteil ist eine Aussage über EINEN Moment, die Zeilen sind
  die Gegenwart; weichen sie ab, wandert die Auswahl auf die Zeile derselben Instanz, und
  ein Anteil, den es nicht mehr gibt, fällt weg. Dazu trägt jede Zeile ihre **Kapazität**:
  was der Auftrag selbst schon hält, ist im Entwurf noch nicht scharf und darf mitgezählt
  werden (sonst liesse sich eine bestehende Auswahl nicht mehr erhöhen).
  (2) **«verliert 4», obwohl nur 2 genommen wurden** (#391). `AffectedOrder.quantity` trug
  die **Sollmenge des Betroffenen** statt seines Verlusts – das las sich wie ein
  Totalverlust und machte die Entscheidung unmöglich. Jetzt rechnet dieselbe Stelle, die
  sagt WER verliert, auch WIE VIEL: `shares.losses` liefert `{auftrag: menge}` (genannter
  Anteil ≻ Erzeuger ≻ übrige, und nur so weit, wie wirklich etwas fehlt), `shares.losers`
  ist die zweite Form derselben Regel. Nicht laufende Halter zählen für die Arithmetik mit
  (`enforce` kürzt auch sie), erscheinen aber nicht in der Frage.
  *Das Backend war in beiden Fällen korrekt* – gegen echtes PostgreSQL nachgewiesen: 1, 2
  und 4 von 4 erzeugen jeweils genau die passende Abweichung und Fehlmenge. Wächter:
  `test_a_holder_loses_the_taken_quantity_not_its_own_order_quantity`,
  `test_the_picker_selection_follows_the_current_rows`; Harness `shares.py` 21/21.

- **Testnotizen #392/#393/#394 (der geklickte Anteil verliert wirklich – und wer nichts
  vorhat, gibt nichts frei)**: Drei Befunde aus dem Versuch «Abweichung von der Abweichung».
  (1) **Der genannte Anteil war folgenlos** (#394, `reservation.enforce` + `shares.losses`).
  Er war nur eine **Rangfolge für den Fehlbetrag**: lag daneben noch etwas Unbeanspruchtes,
  blieb er unangetastet und die Menge kam still von jemand anderem. Im gemeldeten Fall trug
  der neue Auftrag also den richtigen Eltern-Namen (die Abweichung), nahm das Material aber
  dem **Erzeugungsauftrag** weg – und weil ein festes Subjekt keine Unterdeckungs-Frage
  bekommt, wurde auch nichts gefragt. Jetzt gilt: **der geklickte Anteil gibt her, was
  dieser Auftrag beansprucht – unbedingt.** Ein Klick auf «1 Stk · Auftrag …557» ist eine
  Aussage über die **Herkunft**, nicht bloss über die Menge. Erst der Rest läuft wie bisher
  (freier Rest ≻ Erzeuger ≻ übrige Ansprüche); reicht dann immer noch nichts, schrumpft der
  eigene Anspruch. Die Kehrseite steht in `subject.is_bound`: **wer einen fremden Anteil
  nennt, greift Gebundenes an** → Abweichung, auch wenn daneben freier Bestand liegt.
  `subject.enforce_pick` **verbraucht** den Eintrag danach (`orders.pick_sources` ist eine
  Angabe des Entwurfs) – so ist die Einmaligkeit konstruktiv statt erhofft.
  Frontend-Hälfte: **wo es mehrdeutig ist, wird nicht geraten.** Der Abkürzungs-Knopf an der
  Instanz wählt nur noch vor, wenn die Instanz **genau EINEN** Anteil trägt; `reconcilePicks`
  folgt einer verwaisten Angabe ebenso nur bei einer einzigen Zeile. (Das «grösster Anteil
  gewinnt» aus #390 war unter der alten, folgenlosen Semantik harmlos – jetzt hiesse es, dem
  falschen Auftrag etwas wegzunehmen.)
  (2) **Ein Auftrag ohne jeden Prozessschritt liess sich freigeben** (#392). Ohne eigene
  Schritte fährt ein Auftrag den **Artikel**-Prozess – der beschreibt aber, wie etwas
  ENTSTEHT. Wer Instanzen **auswählt**, sagt «das Material gibt es schon»; trotzdem galt
  ausdrücklich «eine Pin-Auswahl kippt den Auftrag NICHT», und die Folge war ein stiller
  Widerspruch: der Auftrag lief den Artikel-Prozess, **erzeugte neue Instanzen** und hielt
  die ausgewählten daneben fest. Zwei Sätze, eine Regel: `subject.subject_kind` liefert bei
  gewählten Instanzen **`stock`**, und alles ausser einer Erzeugung braucht einen **eigenen**
  Ablauf (`_assert_releasable` prüft `order_custom_steps`, nicht irgendeinen auflösbaren
  Schritt). Das Frontend sperrt die Freigabe mit dem Grund im Hover. *`order_step_defs`
  bleibt bewusst unverändert («eigene Schritte, sonst Artikel-Prozess») – zöge die Auswahl
  dort mit, verlöre ein abgeschlossener Auftrag rückwirkend seinen Ablauf, sobald die
  Bindung gelöst ist.* Dazu ein Timing-Fund: die Freigabe liest Zustand, den **dieselbe
  Anfrage** eben geschrieben hat (`autoflush=False`) – ohne `db.flush()` sah das Gate die
  Auswahl gar nicht. Der Flush sitzt jetzt am Anfang von `_do_release` **und** in
  `orders.release_order` (dem EINEN Freigabe-Pfad, für Nachschub/Bereitstellung/Wiederkehr).
  (3) **«Schraubendreher 100000555 verliert 1 Schraubendreher»** (#393). Drei Fehler in
  einer Zeile: der Name eines Auftrags IST der Artikelname (die Zeile las sich wie ein
  Artikel), die Menge trug den Artikelnamen als Einheit (er stand schon links), und woher
  das Stück kommt, stand nirgends. Jetzt: Datensatzart + Name + Objektnummer · Menge in der
  **Einheit** · **Herkunftsinstanz** (`AffectedOrder.unit`/`sources`).
  Im gleichen Zug ist die Rechnung **entdoppelt**: `services/orders._fill_affected` hatte
  eine zweite Fassung, die meldete, was ein Halter überhaupt **hält** statt was er
  **verliert** – derselbe Fehler wie #391, nur an der anderen Oberfläche. Beide Stellen
  fragen jetzt `shares.affected`/`affected_rows`.
  Wächter: `test_a_named_share_always_loses_even_when_something_is_free`,
  `test_a_pick_is_never_a_production`,
  `test_the_shortfall_question_names_order_quantity_and_source`,
  `test_a_pick_is_not_guessed_when_it_is_a_decision`; gegen echtes PostgreSQL verifiziert
  (Harness `note394.py` 11/11 – die gemeldete Abfolge Schritt für Schritt, plus alle 13
  Szenario-Harnesses grün).

- **Testnotizen #395/#396/#397 (immer und immer dieselbe Logik – die letzte Ausnahme ist
  weg)**: Der Nutzer hat den Soll-Ablauf noch einmal in einem Satz formuliert: *ein Auftrag
  wird freigegeben, dabei wird die Unterdeckung des Auftrags abgefragt, an dem die Instanzen
  hingen, die Antwort wirkt auf genau diesen – und der neue Auftrag steht in dessen Prozess
  an der Stelle, an der es passiert ist.* Genau daran scheiterte die **Abweichung von der
  Abweichung**, weil zwei Ausnahmen im Weg standen.
  (1) **Ein festes Subjekt wurde nicht gefragt** (#397). Abweichung/Retoure/Bereitstellung
  galten als «hat kein Soll, also keine Fehlmenge» (#388): sie schrumpften lautlos mit und
  wurden **automatisch abgebrochen**, wenn nichts blieb – im gemeldeten Fall «Abgebrochen –
  fortgeführt im Abweichungsauftrag …563», ohne dass jemand gefragt wurde. Das war eine
  zweite Logik für dieselbe Lage. Jetzt hat auch ein festes Subjekt eine Fehlmenge; sein
  «Gesichert» ist nur ein anderes: es beschafft nichts, sondern **hält bestimmte Stücke**,
  also ist seine Fehlmenge schlicht, **was ihm weggenommen wurde** (`process._held_amounts`).
  Damit fällt es unter dieselbe Formel, bekommt dieselben drei Antworten – und «Menge
  reduzieren» IST sein Abbruch, wenn nichts bleibt (dieselbe Mechanik wie beim Eltern, #366),
  nur eben **entschieden** statt automatisch. `recovery.retire_if_subjectless` und
  `AffectedOrder.needs_decision` sind ersatzlos entfallen: **zwei Regeln weniger**.
  *Ein echter Fund dabei:* bei einer **Retoure** liegt die Menge beim Kunden – eine ganz
  verkaufte Instanz trägt keine Restmenge und kann keinen Anspruch führen. «Gebunden» heisst
  dort «vollständig gehalten», sonst hätte jede Retoure sofort eine Phantom-Fehlmenge
  gemeldet und sich selbst angehalten (gegen echtes PostgreSQL gefunden, `harness.py` S14).
  (2) **Ein Unter-Auftrag gehört genau EINEM Auftrag – seinem Eltern** (#397). Zusätzlich
  wurden *fremde* Abweichungen an denselben Instanzen hereingezogen (die Klammer sei die
  Instanz, nicht der Eltern-Zeiger, #350); in der Kette Auftrag → Abweichung → Abweichung
  stand die zweite damit auch im **Hauptauftrag**, obwohl sie dort nichts zu suchen hat – sie
  hat der ERSTEN etwas genommen. `deviations_touching` ist entfallen. Dass ein anderer
  Auftrag betroffen ist, sagt ihm heute die Unterdeckungs-Frage bei der Freigabe; dafür
  braucht es keinen Fremd-Knoten. *Für die **Rechnung** bleibt die Instanz die Klammer
  (`deviated_quantities`) – nur für die **Anzeige** gilt der Eltern-Zeiger.*
  (3) **Instanz XY im Auftrag ZZ** (#396): die Anteils-Zeile schrieb den Halter-Namen aus –
  der IST aber der Artikelname und damit in jeder Zeile derselbe; er sagte nichts und las
  sich wie ein Artikel. Jetzt zwei Objektnummern mit je einem Symbol davor (Instanz ·
  Auftrag/Abweichung), der Name steht im Hover.
  (4) **Die Auftragsspezifikation nennt Artikel und Instanz – sonst nichts** (#395): die
  Zeile «2 Stk → Auftrag …559» (`ForeignShares`) ist dort entfallen. Wohin ein Anteil ging,
  gehört in den Prozess bzw. an die Instanz.
  Wächter: `test_every_affected_order_is_asked_the_same_question`,
  `test_a_deviation_is_linked_by_the_instance_not_by_the_parent` (neu formuliert),
  `test_a_sub_order_is_shown_only_at_its_parent`; gegen echtes PostgreSQL verifiziert
  (`note397.py` 17/17 – die gemeldete Kette Schritt für Schritt, plus alle 14 Harnesses).

- **Testnotizen #398–#401 (eine Abweichung LEIHT – und gibt zurück)**: Vier Befunde, zwei
  davon in der Rechnung.
  (1) **Was ein Unter-Auftrag mit festem Subjekt hält, kehrt beim Abschluss zurück** (#401,
  `subject.return_borrowed`). Eine Abweichung nimmt dem Auftrag, an dem das Stück hing,
  etwas ab – **die Unterdeckung IST die Ausleihe**. Beim Abschluss wurde aber nur die eigene
  Reservierung gelöst: das Stück wurde damit **frei** statt zurückgegeben, und der Verleiher
  verlangte weiterhin eine Entscheidung über etwas, das längst wieder da war. Jetzt geht es
  an ihn zurück – **vor** dem Lösen der Reservierung, sonst greift die Rückgabe ins Leere.
  Verschrottetes/Verkauftes/Verbautes kehrt NICHT zurück (dort ist die Fehlmenge ehrlich),
  und ein **Erzeuger** als Verleiher braucht nichts zurück: er hält über `Instance.order_id`
  und war nie reserviert. Das Verwerfen (`deviation.detach_sub_order`) gab schon immer
  zurück – jetzt tun es beide Türen.
  (2) **«Wie viel dieser Instanz gehört diesem Auftrag?» hat genau EINE Antwort** (#399,
  `subject.held_quantity`). Der Prüfumfang las die **ganze** Instanz: ein Auftrag über 2 Stk
  einer 4er-Charge zeigte «Prüfumfang: 4 von 2 Stück (100 % Stichprobe)». Das ist die
  wiederkehrende Fehlerklasse rund um Chargen – wer `inst.quantity` nimmt, rechnet mit
  fremdem Bestand. Die Antwort (Anspruch ≻ ganze Instanz) steht jetzt an einer Stelle, und
  ihre drei Nutzer lesen sie: Stichprobenzahl, Stichproben-**Kapazität** je Instanz und
  `process._held_amounts`.
  (3) **Das Symbol sagt, WAS der Halter ist** (#398): die Anteils-Zeile zeigte ein
  Warndreieck, sobald der Anteil «gebunden» war – gebunden ist aber eine Aussage über die
  **Instanz**, ihr Halter kann ein ganz regulärer Auftrag sein. Es liest jetzt den Grund des
  Halters (`InstanceShare.reason`), nicht die Sorte des Anteils.
  (4) **Der Shortcut an der Instanz öffnet die Auswahl** (#400): trägt die Instanz mehrere
  Anteile, wird die Zeile nicht geraten (#394) – die **Instanz** kommt aber trotzdem mit,
  und der Bedarf steht auf «Auswählen». Vorher fiel er auf «Ab Lager» zurück und die Instanz
  war plötzlich gar nicht mehr im Spiel.
  Wächter: `test_a_deviation_borrows_and_gives_back`,
  `test_a_quantity_belongs_to_an_order_not_to_an_instance`,
  `test_the_share_icon_comes_from_the_holder_not_from_the_sort`; gegen echtes PostgreSQL
  verifiziert (`note401.py` 12/12 – Ausleihe zurück, Verschrottetes bleibt fehlend, 2 von 4
  ergibt 2 Proben; plus alle 15 Harnesses).

- **Testnotizen #402–#404 (die Ausleihe reicht durch die Kette – und nur, was gebraucht
  wird)**: Die Rückgabe aus #401 war richtig gedacht, aber zu kurz gebaut.
  (1) **Zurück geht es an den nächsten LAUFENDEN Verleiher** (#404, `subject.lender_of`).
  Kette Auftrag → Abweichung → Abweichung: nimmt die zweite der ersten alles, wird die erste
  gegenstandslos und abgebrochen. Schloss die zweite danach ab, endete die Rückgabe an der
  toten – das Stück wurde schlicht **frei**, und der Hauptauftrag ruhte für immer. Jetzt
  reicht sie durch bis zu dem, der noch läuft; die Pause dort löst sich von selbst.
  (2) **Und nur so viel, wie dort noch fehlt** (#403). Wer «Ersetzen» gewählt hat, ist
  gedeckt – das zurückkommende Stück bliebe sonst als Überschuss für ihn reserviert liegen
  (2 gebraucht, 3 gehalten). Was er nicht mehr braucht, geht in den freien Bestand.
  (3) **Ein Stück, das der Auftrag ohnehin hielt, ist kein Ersatz** (#403): deckt FIFO aus
  der freien Restmenge DERSELBEN Charge, ändert sich physisch nichts – dieselbe Instanz,
  dieselbe Nummer. Die Zeile «N ab Lager ersetzt» erschien trotzdem. Sie steht jetzt nur
  noch für wirklich **neue** Instanzen; kam alles aus dem eigenen Stück, steht gar nichts da.
  (4) **Erfasst ist erfasst** (#402): die Proben einer Datenerfassung wurden bei jedem Aufruf
  aus dem *Plan* neu gerechnet («wie viel gehört dem Auftrag?»). Nach dessen Abschluss ist
  die Reservierung gelöst – der Plan lieferte wieder die ganze Charge, und aus 2 erfassten
  Proben wurden 4 angezeigte. Eine **abgeschlossene** Prüfung ist eine Tatsache und rendert
  ihre gespeicherten Proben; solange sie läuft, bleibt der Plan massgeblich (nach einer
  Hochstufung auf 100 % sind ja zusätzliche Proben zu erfassen).
  (5) **Der Zustand gehört an den Knoten, nicht in ein Banner** (#404): der Unter-Auftrag im
  Ablauf trägt jetzt dieselbe Status-Badge wie überall (`OrderDeviationInfo.abort_into_id`
  unterscheidet «Abgebrochen» von «Inaktiv»). Damit ist der Abbruch-Banner überflüssig – die
  Badge im Kopf sagt es, und WO es weitergeht steht als Unter-Auftrag im Ablauf. Ein
  **abgebrochener** Auftrag ist zudem ebenso still wie ein ruhender: kein Schritt lässt sich
  mehr öffnen (dieselbe `paused`-Regel, keine zweite).
  Wächter: `test_the_loan_returns_along_the_chain_and_only_what_is_needed`,
  `test_a_finished_inspection_keeps_the_samples_it_captured`,
  `test_a_sub_order_carries_its_own_state_in_the_flow`; gegen echtes PostgreSQL verifiziert
  (`note404.py` 10/10 – die Kette über den abgebrochenen Auftrag hinweg, kein Überschuss,
  keine falsche Ersatz-Zeile, 2 Proben bleiben 2; plus alle 16 Harnesses).

- **Testnotizen #405/#406/#408 (kein Sammel-Else, keine tote Entscheidung)**:
  (1) **Ein entzogener Anteil ist kein Ersatz** (#405). Die Auflösungs-Zeile im Ablauf
  kannte zwei Zweige – «Menge angepasst» und ein **Sammel-Else** «N ab Lager ersetzt». Es
  gibt aber DREI Ereignisse; das dritte (`share_taken`, ein anderer Auftrag hat sich hier
  ein Stück geholt) fiel ins Else und las sich als Ersatz aus dem Lager. Wer «Auftrag
  pausieren» gewählt hatte, sah trotzdem «1 ab Lager ersetzt» – genau umgekehrt, dort ist
  etwas **weggegangen**. Jetzt drei Zweige, drei Sätze («… abgegeben an Auftrag …»).
  (2) **Wer die Menge wirklich hält, macht das Warten aus** (#406/#408). Nimmt eine
  Abweichung der Abweichung alles, wird die mittlere gegenstandslos und **abgebrochen** –
  gehalten wird die Menge dann von der untersten. `supply.covering_sub_orders` sah nur die
  **direkten** Kinder, fand niemanden mehr und der Eltern stellte die Unterdeckungs-Frage
  erneut: eine **tote Entscheidung**, obwohl längst entschieden ist und es läuft. Sie folgt
  jetzt der Kette nach unten (zyklensicher, Tiefen-Schranke) – der Auftrag zeigt «wartet auf
  …» und nennt den, der die Menge hält. Gegenstück zu `subject.lender_of`, das beim
  Zurückgeben nach oben läuft.
  (3) **Der Hover sagt den Zustand** (#408): ein abgebrochener Unter-Auftrag stand als
  «Geklärte Abweichung» da – er ist aber nicht geklärt, er wurde abgelöst. Der Knoten liest
  jetzt seine eigene Status-Badge; die feste `done`-Beschriftung ist entfallen.
  Wächter: `test_a_taken_share_is_not_a_replacement`,
  `test_waiting_follows_the_chain_so_there_is_no_dead_decision`; gegen echtes PostgreSQL
  verifiziert (`note404.py` 13/13).

- **Das Big Picture geht in BEIDE Richtungen (Testnotiz #409, Stufen 1+2)**: «am schluss ist ja
  alles ein prozess» – also zeigt der Fluss nicht nur, was in DIESEM Auftrag passiert, sondern
  auch, wie er mit den abgezweigten zusammenhängt. Die Richtung Eltern → Abzweig gab es längst
  (der Unter-Auftrags-Knoten steht seit Runde 27 an seiner Stelle im Ablauf); es fehlten die
  **Tiefe** und die **Gegenrichtung**.
  **(1) Woher kam ich – und wohin gebe ich zurück?** (`OrderResponse.origin`,
  `components/erp/order-flow.tsx: OrderBranchTeaser`). Ein abgezweigter Auftrag hing in der
  Luft: nirgends stand, aus welchem Auftrag und – vor allem – aus welchem **Schritt** er
  hervorgegangen ist, also die Antwort auf «warum gibt es mich?». Jetzt steht **über** dem
  Startknoten «aus Zange 100000576 · Datenerfassung» und **unter** dem Endknoten «zurück an
  100000576», beide gestrichelt angebunden (dort endet der eigene Ablauf und geht in einen
  anderen Auftrag über – `Connector dashed`, eine Variante desselben Bausteins). Ein Klick
  wechselt hinüber; im **Entwurf** eines Unter-Auftrags steht der Herkunfts-Teaser über dem
  Schritt-Editor, wo man gerade entscheidet, was mit den Stücken geschehen soll.
  **Gelesen wird die Mechanik, nicht eine zweite Behauptung** (`orders._return_target`): das
  Rückgabe-Ziel kommt aus derselben Ableitung, die es auch TUT – `subject.lender_of` für die
  Ausleihe (folgt der Kette über abgebrochene Zwischenstufen hinweg, #404) bzw. der Eltern für
  das Nachschub-Pegging, und nur solange dieser noch läuft. Ein fest verdrahtetes «der Eltern»
  wäre genau in dem Fall falsch, der am meisten verwirrt: Eltern abgebrochen, Kette läuft
  weiter. Der Name kommt aus `to_order_summaries` – dieselbe Ableitung wie im Feed, damit ein
  Datensatz nicht an zwei Stellen zwei Namen trägt.
  **(2) Der Prozess des Abzweigs, angeteasert** (`OrderDeviationInfo.steps` = `SubOrderStep`,
  `SubSteps`): der Knoten trägt den Ablauf des Unter-Auftrags als **Miniatur-Fluss** – ein
  Symbol je Modul in Modulfarbe, durch dieselben Verbinder gereiht, erledigte/noch nicht
  erreichte gedämpft, ein Problem über den Rand in der Ampelfarbe; der Hover nennt Modul und
  Zustand. Damit beantwortet er ohne Öffnen die Frage «wie weit ist das da drüben?».
  Abgeleitet wird er aus **derselben** Schritt-Ableitung wie der grosse Fluss
  (`process.build_order_steps`) – ein eigener «ist wohl erledigt»-Zweig liefe neben dem echten
  Zustand her. `SubOrderStep` trägt bewusst **kein Label**: Schrittnamen sind Registry-Wissen
  und stehen im Frontend an EINER Stelle (`lib/process.STEP_META`, gegen `domain/event_types.py`
  getestet); das Zustandswort ist dorthin gewandert (`STEP_STATE_LABEL`, «Im Prozess» wie
  überall). Derselbe Unter-Auftrag erscheint in der Auftrags-Liste UND an seinem Schritt –
  sein Teaser wird darum je Antwort nur einmal abgeleitet (Merker in `to_order_response`).
  Wächter: `test_the_flow_shows_the_branch_in_both_directions`,
  `test_frontend_mirrors.py: test_the_step_teaser_names_the_module_from_one_place`; gegen
  echtes PostgreSQL verifiziert (`note409.py` 14/14 – Herkunft samt Schritt, Rückweg über
  einen abgebrochenen Eltern hinweg, Teaser == echter Ablauf, Nachschub-Pegging).
  **Stufe 3 im Backlog (bewusst NOCH NICHT gebaut): die Instanz als roter Faden.** Die dritte
  Frage – «wo war Stück X wann, und was wurde dort mit ihm gemacht?» – ist keine Sicht auf
  einen Auftrag, sondern auf die **Instanz**: eine Kette aus dem Event-Strom (`order.share_taken`,
  Freigabe, Schritt-Fachzeilen) über alle Aufträge hinweg, die es angefasst haben. Sie **ersetzt
  dann den Reiter «Aufträge» im Instanz-Detailfenster** – der zeigt heute eine Liste von
  Aufträgen, wo eine Geschichte hingehört. Erst danach ist das Big Picture vollständig: Auftrag
  → Abzweig (Stufe 1+2) und Instanz → alle Aufträge (Stufe 3).

- **Testnotizen #410/#411 (der Abzweig IST ein Prozess – und die Entscheidung steht am
  Rückfluss)**: Der Schritt-Teaser aus #409 war zu wenig – «hier habe ich mir schon viel mehr
  erwartet». Richtig gesehen: eine Reihe kleiner Symbole zeigt, DASS es den Abzweig gibt, aber
  nicht, dass der Hauptprozess an dieser Stelle **anhält und über ihn läuft**.
  (1) **Die Hauptlinie wird gekappt** (`order-flow.tsx: SubOrderBranch`): an der Stelle des
  Unter-Auftrags führt sie in einen eigenen kleinen Fluss – **Startknoten mit dem Verweis auf
  den Abzweig**, darunter **seine Prozessschritte als Karten** (`SubStepCard`), am Schluss der
  **Endknoten mit der Ablenkung zurück**. Keine neue Bildsprache, sondern dieselbe eine Nummer
  kleiner: dieselben Terminal-Knoten (`FlowTerm size`), dieselben Verbinder (`Connector
  height`), dieselben Modulfarben, dieselbe Zustands-Regel (nur was JETZT dran ist, trägt
  Farbe). Gestrichelter Rahmen = «gehört nicht zu dieser Linie», wie beim Herkunfts-Teaser.
  Der ganze Kasten öffnet den Unter-Auftrag; seine Schritte sind bewusst **nicht** einzeln
  anwählbar – ein Schritt wird in SEINEM Auftrag bearbeitet.
  (2) **Die Entscheidung steht am Rückfluss** – die Antwort auf die offene Frage der Notiz
  («beim Herabsetzen der Menge weiss ich noch nicht ganz»). Eine Unterdeckungs-Entscheidung
  beantwortet genau eine Frage: *und was ist, wenn der Abzweig zurückkommt?* Also steht sie
  dort, wo er zurückkommt, statt in der Karte des Schritts:
  **ohne Entscheidung** → «zurück in den Prozess» (Nachschub: «deckt den Bedarf») und der
  ganze Rest des Flusses tritt zurück – *warten, bis das hier durch ist*;
  **Menge reduziert** → «Menge angepasst 5 → 4» – das Stück bleibt beim Abzweig, der Auftrag
  läuft **mit weniger** weiter;
  **ersetzt** → «1 ab Lager ersetzt» – an dieser Stelle ist etwas anderes eingemündet.
  Datenseitig ist das **kein neues Feld**: es sind die `StepResolution`s des Schritts, nur an
  ihrem richtigen Ort. Hat ein Schritt einen Abzweig, wandern sie an dessen Rückfluss – sonst
  bleiben sie am Schritt (`resolutions={atBranch ? [] : res}`; dieselbe Aussage nie zweimal).
  (3) **«Angelegt» am Auftrag ist entfallen** (#411): der Auftrag war der **einzige**
  Datensatztyp mit einem Anlage-Zeitstempel als Feld – Artikel, Instanz, Person und
  Unternehmen führen keinen. Er sagte auch nichts Neues: die **Objektnummer** ist aufsteigend
  vergeben (Reihenfolge), der **Prozess** nennt je Schritt Wer/Wann im Hover, und seit ein
  Auftrag als Ganzes entsteht (#386) ist «angelegt» derselbe Moment wie «freigegeben»; bei
  einem Abzweig steht die Entstehung ohnehin am Ursprungsschritt des Eltern-Auftrags.
  Wächter: `test_a_sub_order_is_drawn_as_a_process_inside_the_process`.

- **Testnotizen #412–#415 (der Anteil ist der Massstab; Entscheidungen sind Gates)**:
  (1) **Aussondern wirkt auf den ANTEIL des Auftrags, nicht auf die Instanz** (#412/#414,
  `scrap._scrap_one`): Eine 4er-Charge kann zu 2 einem Auftrag und zu 2 einer Abweichung
  gehören. «Ganz» wurde aber an `inst.quantity` gemessen – eine Abweichung, die 2 hielt,
  verschrottete damit **alle 4**: fremdes Material weg, `disposition='scrapped'`, und der
  Eltern-Auftrag stand mit einer Fehlmenge da, die niemand verursacht hatte. Genau das
  meldeten beide Notizen («nur ein Stück verschrottet» → «Verschrottet»; «nur 2 von 4» →
  «4 Stk. Verschrottet»). Die Frage hat längst eine Antwort – `subject.held_quantity`
  (Notiz #399, dort für den Prüfumfang) –, sie wurde hier nur nie gestellt. Jetzt gilt:
  «ganz» heisst nur dann ganz, wenn der Auftrag die **ganze** Instanz hält; sonst ist auch
  «alles» eine Teilmenge (Menge sinkt, Rest bleibt fremd), und mehr als den eigenen Anteil
  weist der Server ab (400).
  **Im gleichen Zug ist die Anzeige entdoppelt:** `InstanceEmbed.move_quantity` war in
  Wahrheit schon «der Anteil dieses Auftrags», hiess aber nach seinem einzigen Zweck und
  war NULL, sobald der Auftrag die ganze Instanz hielt. Es heisst jetzt `held_quantity`,
  ist im Auftrags-Kontext **immer** gesetzt, und alle Leser teilen es sich (Bewegungs-Panel,
  Aussondern-Panel, Positionsliste, Entwurfs-Auswahl) – im Frontend über die eine Stelle
  `lib/process.heldOf`.
  **Zur Idee «Charge in xxx_1, xxx_2 … zerlegen» (#412): bewusst NICHT gebaut.** Das
  Anteils-Modell beantwortet «wie viel gehört wem» bereits vollständig (`instances.
  reservations`); der Fehler war, dass das Aussondern es ignoriert hat. Eine Zerlegung
  brächte dagegen genau die Probleme zurück, wegen derer eine Instanz eine **Menge** ist:
  Bruchmengen (2.5 kg lassen sich nicht in Stücke schneiden), die systemweit eindeutige
  Objektnummer (QR-Scan, Referenzen, Standort-Kette) und 1000 Zeilen je Reservierung.
  (2) **#415 war eine Folge davon** – gegen echtes PostgreSQL nachgewiesen: mit korrekter
  Teilmenge (2 von 4) reduziert «Menge reduzieren» den Auftrag sauber auf 2, die Fehlmenge
  ist weg und der Schritt wieder aktiv. Mit der ganzen Charge verschrottet blieb nichts
  übrig, und «Menge reduzieren» wurde folgerichtig zum Abbruch.
  (3) **Der Abzweig ist ein paralleler Pfad mit Gates** (#413, `order-flow.tsx`): klassische
  Flowchart-Grammatik statt eingerücktem Kasten – die Linie **teilt sich** (`Fork`, ⊓), links
  läuft die **Hauptspur** (`MainLane`), rechts der Abzweig mit seinem eigenen Prozess, unten
  führen die Pfade **zusammen** (`Merge`, ⊔). Der Zustand der Hauptspur IST die Aussage:
  **gestrichelt** = hier fliesst nichts, bis der Abzweig durch ist · **durchgezogen** = der
  Hauptprozess läuft weiter, während der Abzweig daneben arbeitet.
  **Am Zusammenfluss steht das Gate** (`Gateway`, Raute) – und damit ist die
  Unterdeckungs-Entscheidung ein **Knoten im Prozess** statt einer Notiz darunter: offen →
  anklickbar («Es fehlt 2 Stk · entscheiden»), wartend → Uhr, entschieden → die Auflösung
  («Menge angepasst 4 → 2»). Alle drei Zustände sind **abgeleitet** (`gateState`) aus
  Auflösungen, Abzweig-Status und Fehlmenge – kein neues Feld. Steht der Prozess ohne
  Abzweig still (Ausschuss in der Erzeugung), bekommt die Entscheidung dieselbe Raute vor
  dem Schritt, der nicht weiterkommt – EIN Baustein, zwei Plätze. `ProcessHoldNotice` ist
  entfallen: es gibt keine zweite Stelle mehr für dieselbe Frage.
  Wächter: `test_an_order_only_scraps_the_share_it_holds`,
  `test_the_decision_is_a_gate_in_the_flow`; gegen echtes PostgreSQL verifiziert
  (`note412.py`/`note415.py`), alle 17 Harnesses grün.

- **Der Fluss zeigt das MATERIAL, nicht nur die Module (#413 Layout, Migration `097`)**:
  Der Nutzer hat das Ziel-Layout in Claude Design entworfen; umgesetzt ist das **Konzept**,
  nicht die Pixel.
  (1) **Die Achse wird nie gekappt** (`components/erp/order-flow.tsx`): der Hauptprozess
  läuft in EINER senkrechten Achse (Breite `MAIN`), ein Unter-Auftrag hängt als **Ast**
  rechts daran (`BranchArm`). Die Zwischenstufe – ihn im Fluss auszuklappen (Fork/Merge,
  eigene Terminal-Knoten) – ist zurückgenommen: ein Unter-Auftrag ist ein **eigener
  Datensatz** mit eigenem Fenster; ihn hier auszubreiten baut dasselbe zweimal.
  (2) **Der Abzweig ist bewusst ANGESCHNITTEN** (`BranchTeaser`): Objektnummer als Reiter
  auf dem Rand, Name, Status und seine Module – dann läuft er rechts über eine
  CSS-Maske aus. Das ist die Einladung, ihn zu öffnen (ein Klick lädt den Datensatz),
  statt einer harten Kante.
  (3) **Auf jeder Kante steht, WAS fliesst** (`EdgePill`): «4 × 100000590». Die eigentliche
  Geschichte eines Auftrags ist nicht die Reihe seiner Module, sondern das Material – welche
  Instanz, wie viel, und was unterwegs damit passiert. Am Abzweig steht die **Bilanz**:
  2 rein, **0 zurück** (rote Pille), weil verschrottet. Mehrere Artikel/Instanzen sind der
  Normalfall: je Instanz eine Zeile, ab der vierten «+N» mit vollständigem Hover.
  **Gerechnet wird von unten nach oben** – unten steht, was der Auftrag heute hält, und jeder
  Ast gibt seine Bilanz (rein − zurück) an die Kante über sich weiter. Keine zweite
  Buchführung, keine Event-Rekonstruktion.
  (4) **Die Menge steht dauerhaft am Verarbeitungs-Link** (`instance_order_links.quantity`,
  Migration `097` + Lifespan-Netz): Reservierungen werden bei Abschluss gelöst – ohne diese
  Zahl wäre «wie viel ging da rein?» danach nicht mehr beantwortbar. `record_link` nimmt sie
  an allen zehn Aufrufstellen entgegen; `NULL` = Altbestand, dort fällt es auf den
  abgeleiteten Anteil zurück (tolerant lesen, streng schreiben). Was den Bestand endgültig
  verlassen hat, kommt aus dem **Event-Strom** (`_terminal_amounts`, `inventory.decreased`) –
  ebenso dauerhaft. Das ist zugleich das Fundament für die Instanz-Historie (Stufe 3).
  (5) **Im Unter-Auftrag geht der Blick zurück**: `OrderChain` (wo stehe ich? – die ganze
  Kette bis zur Wurzel, `OrderOrigin.chain`), darüber der **Eltern-Prozess als
  angeschnittener Teaser** mit dem Ast, der hierher führte (`OriginArm`,
  `OrderOrigin.parent_steps`), und am Ende die Rückweg-Pille (`ReturnArm`). Dieselbe
  Bildsprache in beide Richtungen.
  (6) **Die Modul-Karte trägt Nummer und Kurzzeile**: «Beschaffen 100000589–01 · 4 Stk ·
  Lieferant Weber AG». Die Nummer verankert den Schritt im Auftrag, die Kurzzeile kommt aus
  dem Embed, den der Schritt ohnehin trägt (Lieferant/Menge · Ziel · Proben) – nichts wird
  dafür zusätzlich geladen.
  Wächter: `test_a_sub_order_is_a_regular_process_beside_the_axis`,
  `test_the_flow_shows_what_material_moves`; gegen echtes PostgreSQL verifiziert
  (`note413.py` 10/10 – 4 rein/4 zurück, 2 rein/**0 zurück**, Menge am Link, Kette +
  Eltern-Teaser), alle 18 Harnesses grün.

- **Testnotizen-Runde 30 (ein Prozess, drei Spuren, Notizen #416–#420)**: Fünf Notizen,
  EIN Thema – der Abzweig war ein Fremdkörper im eigenen Fluss.
  (1) **Ein Unter-Auftrag wird ganz regulär dargestellt** (#418, «keine Sonderbehandlung.
  ein design / ein system für alles»): seine Module sind dieselben `StepCard`s wie auf der
  Hauptachse – gleiche Anatomie, gleiche Modulfarbe, gleiche Zustands-Symbole, gleiche
  Nummerierung («100000591–01»). Der Miniatur-`TeaserStep` (Symbol + Name, halb so gross,
  kein Detail) war eine **zweite Bildsprache für dieselbe Sache**: «Datenerfassung» sah
  nebenan anders aus als auf der Achse. Es gibt jetzt genau EINE Modul-Karte im Fluss, mit
  `compact` als einzigem Unterschied; was ein Abzweig nicht mitliefert (Kurzzeile,
  Beleg-Status), bleibt leer – ein fehlendes Detail, kein anderes Bauteil.
  (2) **Die Abzweigung geht oben mittig in den Unterprozess** (#417): waagrecht aus der
  Achse bis zur **Mitte** der Seitenspur, dann senkrecht in seinen Kopf hinein – und dort
  läuft die Linie **durch** ihn hindurch, vom Kopf über seine Module bis zu dem, was
  zurückkommt. Vorher stiess der Ast seitlich an einen Kasten, in dem gar keine Linie war;
  ein «Prozess» ohne Prozesslinie ist keiner. Gestrichelt ist ab jetzt **ausschliesslich**
  der Übergang zwischen zwei Aufträgen (Abzweigung · Herkunft · Rückweg) – aus EINER Stelle
  (`LINK_H`/`LINK_V`); der Prozess selbst ist hier wie dort durchgezogen.
  (3) **Kein Container um den Abzweig** (#420): was ihn zusammenhält, ist der Prozess selbst
  – sein **Kopf** (dieselbe Anatomie wie ein Modul, aber gestrichelt umrandet: die im Fluss
  längst etablierte Bedeutung für «gehört nicht zu dieser Linie»), seine Linie, seine
  Module, und oben/unten die Mengen (`flow_in`/`flow_out`). Damit ist er zugleich **besser
  sichtbar** (volle Modulfarben statt 0.7-Opazität hinter einer Maske) **und dezenter**
  (kein zweiter Rahmen um etwas, das schon aus Karten besteht). Die weggeblendete Kante
  (`WebkitMaskImage`) ist mit entfallen – sie war die Entschuldigung dafür, dass der Abzweig
  nicht hinpasste.
  (4) **Der Hauptprozess läuft durch die MITTE** (#419): eine Zeile des Flusses ist jetzt
  **drei Spuren** – links der Auftrag, aus dem dieser hervorging (und wohin er zurückgibt),
  in der Mitte die eigene Achse, rechts die Abzweige. Vorher lag die Achse links, weil
  rechts die Äste hingen; die **Herkunft** musste sich darum nach oben zwängen, obwohl sie
  fachlich dasselbe ist wie ein Abzweig, nur aus der Gegenrichtung. Jetzt sind `OriginArm`
  und `ReturnArm` exakte Spiegelbilder von `BranchCell` (gleiche Elbow-Geometrie, gleiche
  Bausteine) und stehen auf **derselben** Seite. Weil beide Seitenspuren echte Modul-Karten
  tragen, bekommt das Diagramm im Detailfenster eine eigene, breitere Spur (`maxWidth: 1340`
  statt der 880-px-Satzbreite) – es bleibt zentriert, also in einer Flucht mit der
  Spezifikation darüber, und scrollt notfalls in **seinem eigenen** Kasten, nie die Seite.
  (5) **Was gegangen ist, ist eine starke Volllinie** (#416): die Achse trägt den
  Fortschritt selbst – der durchlaufene Teil kräftig (`--fg-2`, 3 px), der Rest Haarlinie.
  Gerechnet wird der **führende** erledigte Lauf, damit eine durchgehende Linie entsteht
  («wie weit ist er?») statt verstreuter starker Stücke; ein offener Abzweig hält sie an,
  genau dort, wo auch der Prozess anhält. Dieselbe Regel im Unterprozess.
  Wächter: `test_a_sub_order_is_a_regular_process_beside_the_axis`,
  `test_the_main_process_runs_down_the_middle`,
  `test_what_has_been_walked_is_a_strong_solid_line`,
  `test_the_branch_names_the_module_from_one_place`.

- **Testnotizen-Runde 31 (die Linie, und was sie trägt, Notizen #421–#429)**: Neun Notizen,
  zwei Themen – die **Linie** und das **Material** auf ihr.
  (1) **EINE Linie, EINE Regel** (#422/#429): die volle schwarze Linie läuft durch alles, was
  passiert und abgeschlossen ist, bis zu dem Modul, das aussteht; ab dort Haarlinie. Das gilt
  **überall gleich** – auch auf dem Weg in einen Abzweig hinein, in ihm drin und zurück.
  **Gestrichelte Linien gibt es im Fluss nicht mehr**: sie waren eine zweite Aussage neben
  «stark ↔ Haarlinie» und haben sie überschrieben, sobald eine Abweichung offen war (genau der
  gemeldete Bug: eine ausgelöste Abweichung machte aus Volllinien Strichlinien). Ein Abzweig
  ist kein Sonderfall mit eigener Strichart, sondern ein gegangener Weg wie jeder andere.
  (2) **Fork und Merge** (#424/#423): die Abzweigung verlässt die Achse waagrecht, geht oben
  mittig in den Unterprozess – und **unten wieder zurück in die Achse** (die Rücklinie fehlte
  ganz). Alle vier Ecken (Fork · Merge · Herkunft · Rückweg) kommen aus EINEM Baustein
  `Elbow` und sind leicht gerundet; gezeichnet als zwei Rahmenkanten eines Kastens, damit die
  Rundung genau eine `border-radius` ist und keine zweite Geometrie.
  (3) **Der Bypass trägt, was geblieben ist** (#425): zwischen Fork und Merge läuft die Achse
  weiter und nennt die Menge, die NICHT abgezweigt ist – «4 kamen an, 2 gingen in die
  Abweichung, 2 blieben hier». Damit die Zahl darüber stimmt, hängt die Rückrechnung am
  **Zustand** des Astes: läuft er noch, ist alles Hineingegangene weiterhin dort; ist er
  durch, fehlt nur, was unterwegs verloren ging. Vorher wurde nur der Verlust zurückgerechnet
  – bei einer offenen Abweichung meldete die Kante über dem Fork darum zu wenig.
  (4) **Keine Menge unterhalb des Fortschritts** (#421): die Kanten wurden von unten nach oben
  aus dem heutigen Bestand gerechnet – und behaupteten damit an Modulen, die noch gar nicht
  dran sind, welche Instanzen sie einmal führen werden. Das ist nicht vorhersehbar; Material
  trägt nur, was der Fluss erreicht hat. Ebenso am Abzweig: **was zurückkommt, steht erst da,
  wenn es zurück ist.**
  (5) **Eine Kante trägt vier Angaben** (#426, `FlowLot` + `OrderResponse.flow_lots`): welche
  **Instanz**, welcher **Artikel**, **wo** sie liegt und **wie viel**. Kurz steht «4 ×
  100000595», im Hover eine kleine Karte mit Artikel · Standort · Menge – und **beide**
  Objektnummern öffnen ihren Datensatz. Aufgelöst wird das **einmal im Backend**
  (`orders._lot_meta`, batch, kein N+1) und in EINER Form: dieselbe Zeile speist die
  Hauptachse und die Abzweige (`flow_in`/`flow_out`), statt dass die Achse ihre Angaben aus
  `InstanceEmbed` + Positionsliste zusammensucht.
  (6) **Die Herkunft zeigt EINEN Schritt** (#427): der Eltern-Prozess gehört in den
  Eltern-Auftrag; hier zählt die Stelle, aus der es hervorging – gefunden über
  `OrderOrigin.step_id` (nicht über den Typ: ein Prozess darf zwei Datenerfassungen haben).
  Dass davor mehr liegt, sagt eine dezente Zeile darüber («⋯ 2 Schritte davor»). Links ist
  damit so ausführlich wie rechts, und Eltern-Kopf und Abzweig-Kopf sind **derselbe** Knoten
  (`OrderNode`), kein Nachbau.
  (7) **Die Brotkrumen-Kette ist entfallen** (#428, `OrderChain` + `OrderOrigin.chain` +
  `OrderRef`): der aktuelle Auftrag steht im Kopf des Fensters, der übergeordnete im
  Herkunfts-Knoten des Flusses – sie sagte beides ein zweites Mal.
  Wächter: `test_the_bypass_carries_what_stayed_on_the_order`,
  `test_no_edge_shows_material_it_has_not_carried_yet`,
  `test_a_flow_lot_names_instance_article_location_and_quantity`,
  `test_the_origin_shows_one_step_not_the_whole_parent_process`; die bestehenden Fluss-Wächter
  verbieten jetzt ausdrücklich jede gestrichelte Linie.

- **Testnotizen-Runde 32 (weniger behaupten, mehr zeigen, Notizen #430–#439)**: Ein echter
  Rechenfehler und neun Vereinfachungen.
  (1) **Ein Anteil kann nie grösser sein als die Instanz** (#432, `subject.held_quantity`):
  Die Antwort auf «wie viel dieser Instanz gehört diesem Auftrag» fiel ohne eigenen Anspruch
  auf die **ganze** Instanz zurück – gedacht für den Erzeuger, der sein Erzeugnis ja komplett
  hält. Sobald aber eine Abweichung 2 einer 4er-Charge übernahm, hielten Eltern (4, über den
  Erzeuger-Rückfall) und Abweichung (2, über ihren Anspruch) zusammen **6 von 4**, und genau
  diese 6 standen auf der Kante des Flusses. Der Rückfall ist jetzt der **Rest**
  (Instanzmenge − alle Ansprüche) – dieselbe Regel, die `shares.shares_for` seit jeher
  rendert; sie stand nur an zwei Stellen verschieden. Das korrigiert nebenbei jede weitere
  Aussage über «den Anteil»: Prüfumfang, Aussondern, Bewegung.
  (2) **Zwei Ecken, wo zwei Ecken sind** (#430/#431): Fork und Merge münden in eine Achse,
  die darüber und darunter weiterläuft – das ist ein **T**. Herkunft und Rückweg dagegen
  treffen die Achse dort, wo sie **beginnt** bzw. **endet**: dort biegt die Linie ab und
  braucht auch an dieser Stelle einen Radius. Gelöst mit einem zweiten Kästchen von genau
  `BEND`×`BEND`, dessen Rand damit ein reiner Viertelkreis ist – keine zweite Geometrie.
  (3) **Der Abzweig zeigt seinen Prozess, keine Kurzinfo über ihn** (#435): die Kopfkarte
  («Abweichung · Name · Status») ist entfallen; in der Seitenspur steht der Unterprozess so,
  wie er im Unter-Auftrag steht – eigener Start- und Endknoten, dieselben Modul-Karten. Ein
  Klick auf irgendetwas davon lädt den Datensatz. Was die Kopfkarte trug, sagt jetzt der
  Hover; **was** dort passiert, sagen die Module selbst.
  (4) **Die Herkunft ist ein Verweis, keine Vorschau** (#436/#437): der eine Prozessschritt
  des Eltern und die Zeile «N Schritte davor» sind zurückgenommen (beide waren aus #427) –
  der Verweis auf den übergeordneten Auftrag genügt, sein Prozess ist einen Klick entfernt.
  `OrderOrigin.parent_steps`/`step_id`/`step_type` sind damit entfallen.
  (5) **Ein Verweis auf einen Auftrag sieht aus wie ein Auftrag** (#438/#439,
  `OrderRefNode`): Symbol und getönte Fläche kommen aus der EINEN Quelle
  (`lib/erp-record.TYPE_META.order`), die Anatomie ist die des Detail-Kopfs (Symbol ·
  Eyebrow · Name · Objektnummer). **Herkunft und Rückweg teilen sich den Baustein** – zwei
  Richtungen, eine Form; der frühere Rückweg war eine kleine Pille und damit eine zweite
  Sprache für dieselbe Aussage.
  (6) **Nur die offene Entscheidung ist ein Knoten** (#434): «wartet» und die bereits
  getroffene Antwort waren reine Information – und die trägt der Fluss ohnehin: ein offener
  Abzweig IST das Warten, eine Auflösung steht als Zeile an ihrer Stelle. `gateFor` ist
  entfallen; übrig bleibt, was man anklicken kann.
  (7) **Die Hover-Karte arbeitet mit Symbolen** (#433): Artikel · Standort · Menge als drei
  Zeilen mit je einem Lucide-Symbol, das Wort im Titel – statt Versalien-Beschriftungen. Die
  Instanz steht bereits in der Pille selbst und wird nicht wiederholt.
  Wächter: `test_a_share_never_exceeds_the_instance`,
  `test_the_origin_is_a_reference_not_a_preview`; die Fluss-Wächter verlangen jetzt eigene
  Terminal-Knoten am Abzweig und verbieten Kopfkarte, `gateFor` und «wartet».

- **Testnotizen-Runde 33 (eine Ecke ist EIN Pfad, Notizen #440–#448)**: Der Auslöser war
  die Optik der Ecken – und die Ursache lag eine Ebene tiefer, in der Geometrie.
  (1) **Feste Spuren statt elastischer** (#445, `MAIN`/`SIDE`/`GAP`/`RUN`): Die Seitenspuren
  waren `flex: 1` und füllten den ganzen verfügbaren Rest – das Diagramm wurde so breit wie
  das Fenster, ohne dass die Fläche etwas trug, **und** die Länge einer Abzweigung war erst
  zur Laufzeit bekannt. Gezeichnet wurde sie deshalb aus CSS-Rahmenkanten mit
  `border-radius`: an der Naht zweier Kästchen sah man jede halbe Pixelverschiebung, und die
  Strichstärke lief in der Rundung aus. Mit festen Breiten ist der Weg von der Achse zur
  Spurmitte eine **Konstante** – und damit lässt sich jede Ecke als **EIN SVG-Pfad** zeichnen
  (ein Strich, eine Strichstärke, ein echter Viertelkreis, keine Naht). Nebenbei ist das
  Diagramm ~150 px schmaler und ruhiger.
  (2) **Ein erledigter Schritt bleibt lesbar, auch wenn der Auftrag ruht** (#442,
  Regression aus #378): Seit ein ruhender Auftrag den ganzen Fluss stilllegt, liess sich
  **kein** Modul mehr öffnen – auch keines, das längst durch ist. Damit war das Protokoll
  eines fertigen Schritts unerreichbar, solange irgendwo eine Abweichung offen war. Ein
  erledigter Schritt trägt aber keine Aktion, sondern eine Aufzeichnung; ihn zu öffnen kann
  nichts auslösen. Zu bleibt nur, was noch zu tun wäre – dort lehnt das Backend ohnehin mit
  409 ab, und genau davor sollte #378 bewahren.
  (3) **Das Ziel hängt am Prozessende** (#446) – und die **Spezifikations-Karte entfällt**
  (#447): Wann der Auftrag fertig sein soll, ist die Aussage des Endknotens, nicht eine Zeile
  in einer Karte darüber; im Hover steht zusätzlich die fakturierende Gesellschaft. Und läuft
  der Prozess, steht auch alles andere schon in ihm (Instanz · Menge auf der Kante, Artikel
  und Standort im Hover) – eine Karte, die dasselbe aufzählt, wäre eine zweite Wahrheit. Im
  **Entwurf** bleibt sie: dort ist sie das Formular, keine Wiederholung.
  (4) **Die Terminal-Knoten nennen ihren Prozess** (#443/#444): «Start · Auftrag 100000594»
  im Hover, am Abzweig entsprechend seiner – seit die Kopfkarte weg ist (#435), ist das die
  Stelle, an der «welcher Auftrag ist das?» beantwortet wird.
  (5) **Keine internen Nummern an der Oberfläche** (#440): die Schritt-Nummer
  («100000596–01») war eine Hilfskonstruktion für die Entwicklung und beantwortet keine
  Frage, die ein Mensch am Auftrag hat – der Schritt heisst nach seinem Modul, und wo er
  steht, sagt seine Position im Fluss. Ersatzlos entfernt.
  (6) **Keine doppelte Angabe im Hover** (#441): Menge und Instanz stehen bereits in der
  Pille; im Hover bleiben Artikel und Standort. Dafür trägt die Pille jetzt die **Einheit**
  («4 Stk. × 100000595») – sonst ginge «kg» verloren.
  (7) **Der Rückweg zeigt nach unten** (#448, `ArrowDown` statt `CornerDownLeft`).
  Wächter: `test_a_finished_step_stays_readable_while_the_order_rests`,
  `test_the_process_is_narrow_and_its_step_numbers_are_gone`,
  `test_the_order_goal_hangs_at_the_end_of_the_process`; der Ecken-Wächter verlangt jetzt
  einen **Pfad** statt Rahmenkanten.

- **Testnotizen-Runde 34 (die Abzweigung ist eine Gabelung – und ein Auftrag ist einen Klick
  entfernt, Notizen #449–#456)**:
  (1) **Auftrag auf das, was gerade dran ist** (#455, NEU – `FlowShortcut`): an der Kante, an
  der die starke Linie endet, liegt das Material des Augenblicks – und genau darauf will man
  einen Auftrag ansetzen (in der Praxis meist eine Abweichung). Ein bewusst blasser Knopf
  (im Hover deutlich, mit Erklärung) nimmt **alle** Instanzen dieser Kante mit: mehrere
  Artikel werden zu mehreren **Positionen**, jede mit ihren Instanzen und Mengen
  (`seedFromLots` gruppiert nach Artikel, `OrderSeed.lines`). Angelegt wird dabei nichts –
  der Entwurf lebt im Browser (#386) –, und **was** daraus wird, entscheidet weiterhin die
  Auswahl (`subject.classify_pick`): der Knopf ist eine Eingabehilfe, kein zweiter
  Anlage-Weg (#371).
  (2) **Die Abzweigung ist eine Gabelung, kein T** (#456): die Linie biegt oben mit demselben
  Radius aus der Achse ab, mit dem sie unten in den Unterprozess einläuft – und mündet
  ebenso wieder ein. Möglich, weil die Geometrie seit #445 fest ist: der Pfad beginnt
  schlicht `BEND` über der Zelle, mitten auf der Achse.
  (3) **Kein Symbol für etwas, das die Linie schon sagt** (#450/#452): Uhr («in Arbeit») und
  Pause sind entfallen. Dass der Prozess an diesem Modul steht, sieht man daran, dass es
  aktiv ist und die starke Linie hier endet; dass er ruht, daran, dass die starke Linie nicht
  hinführt und kein Modul aktiv ist. Übrig bleiben die zwei Aussagen, die man der Linie
  **nicht** ansieht: **durch** (Wer/Wann im Hover) und **fehlgeschlagen**.
  (4) **Ein Nachbar-Prozess blasst zum Rand hin aus** (#453, `fade`): der Abzweig nach
  rechts, der übergeordnete Auftrag nach links. Er bleibt vollständig lesbar und sagt
  trotzdem «hier geht es weiter, klick mich an». Das ist **nicht** die Maske aus #420
  zurück: dort war sie die Entschuldigung für einen angeschnittenen Teaser, hier ist der
  Nachbar ganz da und blasst nur an der Aussenkante aus. Die Verbindungslinie bleibt voll –
  sie gehört zu diesem Fluss, nicht zum Nachbarn.
  (5) **Ein zweiter Klick schliesst wieder** (#449): dafür braucht «zu» einen eigenen Wert –
  `null` heisst «nichts gewählt» und fällt auf den aktiven Schritt zurück, der leere String
  heisst «bewusst geschlossen».
  (6) **Zeigefinger auch dort, wo der Klick am Container hängt** (#454): im Abzweig öffnet
  die ganze Spalte den Datensatz; die Modul-Karte erbt den Cursor (`inherit`), statt ihn mit
  `default` zu widerrufen.
  (7) **Die Überschrift «Auftragsspezifikation» entfällt** (#451) – sie stand über einer
  Karte, die es beim laufenden Auftrag gar nicht mehr gibt (#447), und im Entwurf ist das
  Formular sich selbst genug (wie schon #106/#116 im Prozess-Editor).
  Wächter: `test_the_process_point_offers_a_shortcut_onto_its_material`,
  `test_the_flow_shows_state_only_where_the_line_does_not`; der Abzweig-Wächter kennt jetzt
  den Unterschied zwischen «Kasten mit Maske» (verboten) und «Kante blasst aus» (gewollt).

- **Testnotizen-Runde 35 (wo steht der Prozess wirklich?, Notizen #457–#462)**: Zwei echte
  Fehler an der Abkürzung aus #455 – beide hatten dieselbe Wurzel: **eine Annahme, die bei
  genau einem Halter zufällig stimmte.**
  (1) **An einem offenen Abzweig steht der Prozess eine Kante tiefer** (#459): Die Abkürzung
  sass an der Kante, an der die starke Linie endet – bei einem Abzweig ist das die Kante
  **über** dem Fork, und die zählt noch alles zusammen (4 Stk). Tatsächlich hat sich das
  Material dort längst geteilt: 2 gingen in die Abweichung, 2 blieben auf dem Hauptauftrag.
  Wer oben ansetzt, legt einen Auftrag auf Stücke an, die woanders hängen. Die tiefste
  **erreichte** Stelle der Achse ist der **Bypass** – und der IST der Prozess-Punkt
  (`atBypass = walked < nodes.length && !!nodes[walked].branches`). Keine Sonderregel: die
  beiden Bedingungen schliessen einander aus, die Abkürzung steht immer an genau einer Kante.
  (2) **Eine Vorauswahl nennt ihren Halter – «nicht genannt» ist nicht «frei»** (#461): Der
  neue Auftrag hatte Artikel und Menge, aber die falsche Instanz. Ursache war eine Sorte, die
  es zweimal gab: `from_order_object_id` kannte `null` = «der freie Anteil», und eine
  **fehlende** Angabe wurde genauso gelesen. Das Material am Prozess-Punkt gehört aber diesem
  Auftrag; frei ist daran nichts. `reconcilePicks` suchte also einen freien Anteil, fand bei
  mehreren Anteilen keinen und liess die Auswahl fallen – bei genau EINER Zeile griff der
  Rückfall «es gibt ja nur eine», und der konnte die falsche sein. Zwei Hälften, beide nötig:
  `seedFromLots(lots, holderObjectId)` **nennt** den Halter (die Abkürzung weiss ihn – es ist
  der Auftrag, dessen Fluss sie zeigt), und wo nichts genannt ist, bleibt es `undefined`
  statt `null` (`named = p.from_order_object_id !== undefined`). Geraten wird nur noch dort,
  wo es nichts zu raten gibt.
  (3) **Ein Nachbar-Prozess tritt deutlich zurück** (#460): «man soll klar erkennen, dass die
  links und rechts dargestellten Prozesse nicht im Fokus stehen». Die Maske aus #453 blasst
  nur die Aussenkante aus – die Mitte des Nachbarn blieb genauso laut wie der eigene Prozess.
  Er ist jetzt **als Ganzes** gedämpft und blasst zusätzlich aus; beim Hovern kommt er ganz
  nach vorn. Der Hover ist CSS (`.ix-flow-aside` in `globals.css`), kein State – ein
  `onMouseEnter` je Nachbar wäre React-Arbeit für eine reine Optik-Frage. Die
  Verbindungslinie bleibt unberührt: sie gehört zu diesem Fluss, nicht zum Nachbarn.
  (4) **Vergangenes verblasst auf der Kante wie am Modul** (#462): ein erledigter Schritt
  tritt zurück, die Mengen-Angabe darüber tat es nicht – und war damit lauter als der
  Schritt, zu dem sie gehört. Dieselbe Dämpfung, dieselbe Regel.
  (5) **Die Zielangabe steht NEBEN dem Endknoten** (#457): darunter schob sie den Kreis nach
  oben und drückte die letzte Kante zusammen. Absolut gesetzt bleibt der Kreis auf der Achse,
  die Beschriftung hängt rechts daneben.
  Wächter: `test_a_preselected_share_names_its_holder`,
  `test_what_is_past_steps_back_on_the_edges_too`; die Guards für Abkürzung, Bypass, Ziel
  und Nachbar-Spuren sind auf die neuen Regeln gezogen.

- **Zwei gleichzeitig laufende Abzweige – und EINE Stelle, an der der Prozess steht**
  (Juli 2026, Testnotizen #463–#468):
  **(1) Mehrere Unter-Aufträge an derselben Stelle** – die offene Gestaltungsfrage: im
  Drei-Spuren-Bild (links Herkunft · Mitte eigener Prozess · rechts Abzweige) ist für zwei
  Abzweige **nebeneinander** kein Platz, und eine vierte Spur oder ein Scrollbalken sind
  ausgeschlossen. *(Die erste Antwort – je Ast ein eigener Fork mit eigenem Bypass, also
  «zwei aufeinander folgende Teilungen» – ist in Runde 37 zurückgenommen; sie behauptete eine
  Reihenfolge, die es zwischen gleichzeitig laufenden Ästen nicht gibt. Siehe unten.)*
  **(2) «Stark ist es dort, wo der Prozessschritt gerade aktiv ist»** (#464/#467/#468) – die
  Regel des Nutzers, jetzt als **eine** Ableitung (`here`) statt dreier Zähler. Daraus folgt
  alles: *läuft der Auftrag nicht mehr* (abgeschlossen/abgebrochen/Entwurf) → **gar keine**
  Stelle, denn sein Material ist längst beim übergeordneten Auftrag, dort steht der aktive
  Schritt: alles verblasst, und die Abkürzung verschwindet (#467/#468 – sie sass an der
  letzten Kante eines fertigen Unter-Auftrags und hätte einen Auftrag auf zurückgegebene
  Stücke angesetzt). *Steht er an einem Abzweig* → am **Bypass**; die Kante darüber zählt noch
  alles zusammen und ist damit Vergangenheit (#464). Sonst → an der Kante über dem nächsten
  offenen Modul. `OrderFlow` bekommt dafür ein Bit (`running = status === 'released'`) statt
  einer Vermutung.
  **(3) Ein künftiger Schritt lässt sich ansehen** (#465): #378 hatte am ruhenden Auftrag
  **alles** verschlossen, #442 die erledigten wieder geöffnet – die künftigen blieben zu,
  obwohl sie in einem laufenden Auftrag jederzeit zu öffnen sind. Zu bleibt jetzt genau
  **einer**: der, an dem es hängt (`state === 'blocked'|'active'`) – dort lehnt das Backend
  mit 409 ab, und davor sollte #378 bewahren. Alles andere ist Lesen und kann nichts auslösen.
  **(4) «1 abgegeben an …» nur, wo es nicht schon dasteht** (#466): wer sich hier einen Anteil
  geholt hat, wird dadurch zur **Abweichung dieses Auftrags** (`_make_deviation`: Eltern = wer
  das Stück hielt) – steht also ohnehin als Abzweig im Fluss, mit der Menge auf seiner Kante.
  Die Zeile war damit eine zweite Erzählung desselben Vorgangs. Sie bleibt nur für den Fall,
  in dem der Nehmer **nicht** als Abzweig erscheint: greift eine Auswahl über mehrere Halter,
  wird nur der erste sein Eltern – die übrigen erfahren sonst nirgends, warum ihnen etwas
  fehlt (`Resolutions` filtert, EINE Stelle für alle Auflösungszeilen).
  **(5) Keine Überschrift «Prozess»** (#463) – ein Diagramm mit Start-, End- und Modulknoten
  sagt selbst, was es ist (wie #106/#116/#451).
  Wächter: `test_a_taken_share_is_not_told_twice`; die Guards für Abkürzung, verblasste
  Kanten, Lesbarkeit und Seitenspur sind auf die neuen Regeln gezogen.

- **Mehrere Abzweige an derselben Stelle sind EINE Teilung in mehrere Richtungen**
  (Juli 2026, Praxis-Rückmeldung + Testnotiz #469): Die Zwischenstufe aus der Runde davor –
  je Ast ein eigener Fork mit eigenem Bypass, gelesen als «zwei aufeinander folgende
  Teilungen» – ist zurückgenommen. Sie rechnete zwar korrekt, hatte aber drei Folgen, die
  alle dieselbe Wurzel hatten: **sie unterstellte eine Reihenfolge, die es zwischen
  gleichzeitig laufenden Ästen nicht gibt.**
  (1) **Zum zweiten Ast führte nur eine Haarlinie.** Die Achse ist ein **Präfix** («stark bis
  zur offenen Stelle», #422) – und ein Präfix setzt eine Reihenfolge voraus. Zwei Abweichungen
  laufen aber nebeneinander; zu **beiden** ist ein Weg gegangen worden. Die Stärke eines
  Abzweig-Wegs hängt darum jetzt an **seinem** Zustand (`branchStarted`), nicht am Fortschritt
  der Achse: der Fork ist stark, sobald irgendein Ast gestartet ist, der Rückweg erst, wenn
  die **ganze** Teilung durch ist. Die Achse selbst bleibt ein Präfix – sie ist ja sequenziell.
  (2) **Überlagerung der Linien.** Zwei Äste hiessen zwei Fork/Merge-Paare mit einer S-Kurve
  dazwischen (einmünden, sofort wieder abbiegen). Jetzt gibt es **einen** Fork und **einen**
  Merge; die Unterprozesse hängen untereinander in der Spur, verbunden durch ein Stück Achse.
  (3) **Die Achse trug einen Zwischenstand statt der Wahrheit** (#469): «2 Stk», obwohl von
  4 Stück bereits 2 und 1 abgezweigt waren und der Auftrag nur noch **1** hielt. Mit EINEM
  Fork ist der Bypass wieder das, was der Auftrag wirklich hat.
  **Wie viel wohin geht, sagt die Menge über jedem Unterprozess** – dafür braucht es keine
  zweite Teilung. Das Drei-Spuren-Bild bleibt unangetastet, und es ist ein Bauteil weniger
  (`BranchCell` ist in `BranchArm` aufgegangen).
  Wächter: `test_parallel_sub_orders_are_one_split_in_several_directions`,
  `test_what_has_been_walked_is_a_strong_solid_line` (Fork/Merge-Regel).

- **Das Material eines Auftrags: EINE Quelle, unbewegliche Menge, Ampelfarbe** (Aug. 2026,
  Testnotizen #479–#482, `services/orders.order_material`): Die Mengen im Fluss waren
  **zweimal verschieden hergeleitet** – die Achse eines Auftrags aus `held_quantity` (was er
  **gerade** hält), der Abzweig aus dem Verarbeitungs-Link (was er **übernommen** hat).
  Damit zeigte derselbe Vorgang je nach Blickrichtung zwei Zahlen; und weil «gerade gehalten»
  ein **bewegliches Ziel** ist (Reservierung gelöst, verschrottet, freigegeben), war die eine
  davon nach jeder Zustandsänderung falsch. Genau daher kamen die wiederkehrenden
  Mengen-Fehler.
  **Die Regel, die alles auflöst** (vom Nutzer formuliert): *die Menge verschwindet nicht,
  nur der Zustand ändert sich.* Daraus folgt:
  (1) **EINE Ableitung für beide Leser** – `order_material(db, order)` liefert das Material
  (Menge = `instance_order_links.quantity`, geschrieben und **nie wieder geändert**) und
  daneben, was der Auftrag dem Bestand **endgültig** entzogen hat. `OrderResponse.flow_lots`
  und `OrderDeviationInfo.flow_in` lesen dieselbe Funktion – der Teaser im Eltern-Auftrag
  kann darum gar nicht mehr von dem abweichen, was der geöffnete Unter-Auftrag zeigt (#482).
  (2) **Nach dem Verschrotten steht dort weiterhin «1 Stk»** – nur **rot** (#481): jede
  Materialzeile trägt die beiden Instanz-Achsen (`quality`/`disposition`) und die Oberfläche
  projiziert sie mit derselben Regel wie an der Instanz selbst (`instanceStatusConfig`) auf
  eine **Ampelfarbe + Symbol**. Die zweite Mengenliste `flow_out` («0 zurück») ist ersatzlos
  entfallen.
  (3) **Kommt nichts zurück, führt gar keine Linie zurück** (#481.3) – die einfachste
  denkbare Darstellung für «die Menge des Hauptauftrags wurde reduziert» bzw. «alles
  verschrottet». Abgeleitet aus `flow_in − flow_lost`, kein Feld.
  (4) **Gerechnet wird von OBEN nach unten**: oben das Material (eine Tatsache), an jeder
  Teilung geht ab, was abzweigt. Die frühere Rückrechnung von unten (`plusBalance`) stand auf
  dem beweglichen Ziel und ist entfallen.
  Wächter `test_the_flow_shows_what_material_moves`; gegen echtes PostgreSQL 16 verifiziert
  (13 Prüfungen: 4 → 2 + 1 + 1, Verschrotten lässt die Zahl stehen, Teaser == eigene Achse,
  0 zurück ⇒ keine Rücklinie).

- **Testnotizen-Runde 38 (ansehen darf man alles, Notizen #470–#478)**:
  (1) **Jeder Prozessschritt lässt sich öffnen** (#471, revidiert #378/#442/#465): ein Panel
  zu öffnen ist **Lesen**; ob sich darin etwas ausführen lässt, entscheidet ohnehin das
  Backend (`resolve_exec_step` – nur der aktive Schritt, sonst 409 mit dem echten Grund). Die
  Sperre am ruhenden Auftrag war eine zweite, rein visuelle Regel daneben – und sie verbarg
  ausgerechnet die Daten, die man beim Klären einer Abweichung braucht.
  (2) **Schon am Ziel ist kein Fehler, sondern erledigt** (#477/#478, `location_split.move`):
  wer keinen Quellstandort nennt, sagt «bring es dorthin» – liegt es bereits dort, ist genau
  das erreicht. **No-op statt 400**, dieselbe Haltung wie beim Bereitstellen.
  (3) **Die Liste der Datenerfassung scrollt ohne Balken** (#473, `fields.ScrollFade`): die
  Kante, an der noch etwas liegt, **blasst aus** – oben wie unten, und jede nur dann, wenn
  dort wirklich etwas ist. Dazu kompakter (300 px statt 420), damit man früher merkt, dass es
  weitergeht. Dieselbe Sprache, in der die Nachbar-Prozesse im Fluss zurücktreten.
  (4) **Das Ergebnis-Banner der Datenerfassung entfällt** (#472) – jede Probe trägt ihre
  Farbe, das Banner erzählte dasselbe ein zweites Mal. Geblieben ist, was die Liste **nicht**
  sagen kann: wer erfasst hat, und ob ein Folgeauftrag den Befund geklärt hat.
  (5) **Symbol statt Ampelpunkt** in der Anteils-Auswahl (#475): ein Punkt trägt nur die
  Farbe, ein Symbol die Aussage – frei am Lager · gebunden · verkauft; gewählt der Haken.
  (6) **Dass man die Menge tippen kann, muss man sehen** (#476): getönte Fläche + Stift statt
  einer blossen Pille.
  (7) **Der Hover gilt genau EINEM Abzweig** (Praxis-Rückmeldung): lagen alle Äste einer
  Teilung in demselben `aside`-Kasten, hellten sie gemeinsam auf – man sah also nicht, welchen
  man gleich öffnet.
  (8) Hover-Karte einer Materialzeile über allem (#474, `zIndex 200` – sie stand hinter dem
  Endknoten); am Prozessende steht nur noch **wann** (#470) – dass es der Liefertermin ist,
  sagt die Stelle, und das Wort steht im Hover.

- **Ein Zustand gehört zur MENGE, nicht zur Instanz** (Aug. 2026, Testnotizen #483–#485):
  Der wiederkehrende Fehler war ein **Modellfehler**, kein Anzeigefehler. `instances.quality`/
  `disposition` sind **Skalare** – bei Einzelserialisierung stimmt das (eine Instanz = 1 Stück
  = ein Zustand), bei einer **Charge** nicht: von 4 Stück können 3 in Arbeit und 1
  verschrottet sein. Die Oberfläche behauptete darum EINEN Zustand für die ganze Menge (eine
  gerade verschrottete Teilmenge blieb grün «Freigegeben»).
  **Die Lösung folgt dem Muster, das es im Haus schon zweimal gibt** – `instances.reservations`
  (Anspruch je Menge) und `instances.locations` (Standort je Menge): eine **Materialzeile
  beschreibt genau eine Menge in genau einem Zustand**, und dieselbe Instanz kann mehrere
  Zeilen haben. `order_material` zerlegt die übernommene Menge in das, was dieser Auftrag
  ausgesteuert hat (je Art, aus `_terminal_amounts` – jetzt `{objektnr: {scrapped|sold|
  consumed: menge}}`), und den **lebenden Rest**. Der Rest ist **gebunden** (`reserved`),
  solange der Auftrag läuft – sonst stünde ein Stück in Arbeit als «frei am Lager» da (#485).
  *Der Vorschlag, eine Charge intern in `Nummer_01…_04` zu zerlegen, führt zum selben
  Ergebnis – aber ohne dessen Kosten: eine Charge darf gebrochen sein (2.5 kg), ihre
  Objektnummer ist systemweit eindeutig (QR/Referenzen/Standort-Kette), und 1000 Zeilen je
  Reservierung wären ein hoher Preis für eine Anzeige-Frage.*
  Frontend: der Lot-Schlüssel ist **Instanz + Zustand** (`lotKey`) statt der Objektnummer –
  sonst führte das Zusammenfassen genau den einen Zustand wieder ein; `minusBranches` zieht
  je Instanz ab, **lebendes Material zuerst**.
  **Am Instanz-Detail dieselbe Frage aus der anderen Richtung** (#484): die Kachel heisst
  **«Menge & Zustand»** und zeigt jede Teilmenge mit Ampelfarbe und Halter – Quelle ist die
  Anteils-Aufteilung, die es längst gibt (`services/shares.py`), nicht eine zweite Rechnung.
  Wächter `test_the_flow_shows_what_material_moves` (erweitert); gegen echtes PostgreSQL 16
  verifiziert (17 Prüfungen, u. a. «2 Stk zerfallen in 1 verschrottet + 1 lebend, Summe
  bleibt 2»).

- **Testnotizen #486/#487**: (1) **Ein künftiger Schritt zeigt seine Planung** (#487): «Wird
  aktiv, sobald der vorherige Schritt erledigt ist» war die einzige Auskunft – vier Panels
  brachen vorher ab und verbargen damit genau das, was man wissen will (*was soll hier
  passieren?*). Prüfumfang, Ziel, Ressourcenzeilen und Lieferant standen längst im Panel.
  Jetzt rendert **jedes** Modul seine Planung, `fields.PlannedNotice` sagt an EINER Stelle,
  dass sie noch nicht dran ist, und die Aktionen bleiben aus. (2) **«Menge angepasst 4 → 3»
  entfällt** (#486) – dass der Prozess mit weniger weiterläuft, sagt der Fluss selbst: der
  Abzweig führt nicht mehr zurück.

- **Eine durchlaufene Kante zeigt den Zustand von DAMALS** (Aug. 2026, Testnotiz #488):
  Eine Materialzeile las immer den **heutigen** Zustand – wurde ein Stück später
  verschrottet, stand es rückwirkend auf **jeder** Kante rot, die es passiert hatte, als es
  noch in Arbeit war. Damit liess sich der Verlauf nicht mehr nachvollziehen, obwohl genau
  das der Zweck des Flusses ist.
  **Die Regel (vom Nutzer formuliert): beim Abschluss eines Schritts friert der Zustand
  ein.** Was danach passiert ist, gab es an dieser Stelle noch nicht; nur dort, wo der
  Prozess **gerade steht**, gilt der aktuelle Zustand.
  Umgesetzt ohne neue Speicherung: jede Abgangs-Zeile trägt ihren **Zeitpunkt**
  (`FlowLot.at`, aus dem Event-Strom – `_terminal_amounts` gruppiert jetzt nach
  `(Art, Zeitpunkt)`), jede Kante ihren **Stichtag** (`cutoffs[i]` = Abschluss des letzten
  Schritts darüber, davor `BEGIN`), und `asOf` nimmt Abgänge nach dem Stichtag zurück – die
  Menge zählt dort wieder zu dem, was der Auftrag **hielt** («Im Prozess», gelb). Der
  Zustand ist damit **abgeleitet statt gemerkt**: kein Schnappschuss-Feld, das auseinander
  laufen könnte.
  **Und der Abzweig zeigt beides**: oben, was hineinging (Zustand von damals), unten
  dieselbe **Menge** in ihrem heutigen Zustand – aber nur, wenn er ein anderer ist. Das
  präzisiert #481: die Menge schrumpft nicht, sie wechselt die Farbe, und man sieht **wo**.
  Wächter `test_what_is_past_steps_back_on_the_edges_too` (erweitert); gegen echtes
  PostgreSQL 16 verifiziert (19 Prüfungen).

- **Der Abzweig im Eltern-Auftrag IST der Unter-Auftrag – kein Interpretationsspielraum**
  (Aug. 2026, Testnotizen #489–#492): Derselbe Abzweig zeigte zwei verschiedene Bilder – im
  Eltern-Auftrag **ohne** Rückweg (dort wurde aus dem Material gerechnet), beim **Öffnen**
  mit. Ursache waren **zwei Ableitungen** derselben Frage: die eine fragte, ob überhaupt
  etwas zurückkommt, die andere nur, **wem** es zurückginge.
  (1) **EINE Regel** (`orders.returns_material`): was übernommen wurde, minus dem, was den
  Bestand endgültig verlassen hat. Sie speist beides – `OrderDeviationInfo.returns_material`
  (Abzweig im Eltern) und `_return_target` (Rückweg-Knoten im Unter-Auftrag). Getrennt
  hergeleitet konnten sie auseinanderlaufen; jetzt können sie es nicht mehr.
  (2) **Dieselbe Karte, dieselbe Grösse** (#491): der `compact`-Modus der Modul-Karte ist
  ersatzlos entfallen und die **Seitenspur ist so breit wie die Hauptspur** (`SIDE = MAIN`) –
  ein Abzweig ist ein regulärer Prozess (#418), also sehen seine Module aus wie alle anderen.
  Damit auch der fachliche Zwischenstand stimmt, trägt `SubOrderStep` jetzt `status`
  (Beschaffung/Verkauf); `stepBadge(typ, status)` ist die EINE Stelle, die ihn rendert.
  (3) **Keine Untertitel am Modul** (#490): «ganz oder gar nicht» – wer die Details sehen
  will, öffnet den Schritt und sieht dort ALLES. Eine halbe Zeile daneben war eine zweite,
  unvollständige Wahrheit; `stepDetail` ist entfallen.
  (4) **Kein Scrollbalken am Diagramm** (#489, `.ix-noscrollbar`) – gescrollt wird weiterhin.
  Wächter: `test_a_sub_order_is_a_regular_process_beside_the_axis` (verbietet `compact`),
  `test_the_branch_names_the_module_from_one_place`; gegen echtes PostgreSQL 16 verifiziert
  (21 Prüfungen – u. a. «Teaser und eigene Ansicht sagen dasselbe» für beide Abzweige).

- **Der Entwurf trägt schon den Rahmen – und die Rückgabe-Linie IST die Entscheidung**
  (August 2026, `components/erp/order-flow.tsx: DraftFlowFrame`): Wer gebundene Instanzen
  wählt, hat eine **Abweichung** – und die hängt nach der Freigabe als Abzweig am laufenden
  Auftrag. Das Bild dafür gab es längst (drei Spuren, Herkunft links, Rückweg unten); es kam
  nur einen Schritt zu spät. Jetzt steht es schon beim **Modellieren** da: der Schritt-Editor
  sitzt in der **Mitte** desselben Rahmens, links die Aufträge, denen die Auswahl ihr Material
  wegnimmt. Dieselben Bausteine (`Row`/`Axis`/`Elbow`/`FlowTerm`/`OrderRefNode`), dieselbe
  Geometrie, kein zweites Vokabular – und ohne Halter ändert sich gar nichts: der Editor steht
  frei im Weissraum wie am Artikel (ein gewöhnlicher neuer Auftrag geht aus nichts hervor).
  **Die Unterdeckungs-Frage wird dadurch gezeichnet statt angeklickt.** Von ihren drei
  Antworten sind zwei schlicht die Frage, ob das Material zurückkommt:
      Linie da    → **warten** (`wait`)     – der Halter ruht, bis die Menge wieder da ist
      Linie weg   → **reduzieren** (`accept`) – er wird mit dem fertig, was ihm bleibt
  Geklickt wird die Linie selbst (Rückgabe-Knoten kappt, Zeile darunter schaltet wieder an);
  gemerkt wird die **Ausnahme** (`cutReturns`), damit ein neu hinzukommender Halter
  automatisch zurückgibt, ohne dass ein Effekt Listen abgleichen müsste. **«Ersetzen» bleibt
  bewusst draussen**: das ist keine Aussage über diesen Entwurf, sondern eine Beschaffung im
  anderen Auftrag – sie gehört dorthin, wo sie wirkt (`ShortfallDialog` am laufenden Auftrag).
  **Je Halter eine Antwort – am API-Rand wie in der Oberfläche.** `shortfall_response` (ein
  Skalar, per Schleife auf ALLE Betroffenen angewandt) ist zu `shortfall_responses`
  `{Objektnummer: Antwort}` geworden: wer aus zwei laufenden Aufträgen Stücke nimmt, darf den
  einen warten lassen und den anderen reduzieren – eine Antwort über alle wäre eine
  Entscheidung, die so niemand getroffen hat. `_answer_for(answers, holder)` ist die EINE
  Auflösung, die Prüfung und Anwendung teilen; fehlt auch nur eine Antwort, wird die Frage
  für alle gestellt, genannt werden aber nur die **offenen**. Der Dialog ist damit nur noch
  das **Netz** für Halter, die der Fluss nicht zeigen konnte (eine Auswahl kann über den
  genannten Anteil hinaus auf weitere Ansprüche durchgreifen, `shares.losses`) – und weil die
  409-Antwort selbst sagt, wen es trifft, liest die Oberfläche jetzt in **beiden** Pfaden
  diese Liste statt eines womöglich veralteten `affects` am Datensatz.
  **Ein echter Fehler dabei gefunden** (gegen echtes PostgreSQL 16): `_resolve_picks` ist
  nach `{instanz: menge}` geschlüsselt – zwei angeklickte Zeilen **derselben** Instanz
  überschrieben einander **still**. Aus «3 von A und 2 von B» wurde «2 von B»: der Auftrag war
  plötzlich kleiner als gewählt, und A wurde nie gefragt. Die Mengen zählen jetzt zusammen
  (Obergrenze über die Summe geprüft), genannt bleibt der **erste** Halter, den Rest verteilt
  `shares.losses` nach ihrer Rangfolge – gefragt werden dadurch beide. *Offen und bewusst
  nicht gebaut:* auf EINER Instanz verliert der zweite genannte Halter erst nach dem freien
  Rest, weil `orders.pick_sources` je Instanz nur EINEN Halter trägt; per-Anteil-Exaktheit
  bräuchte dort eine Liste mit Mengen und ist eine eigene Runde wert. Der Normalfall –
  mehrere Instanzen in verschiedenen Aufträgen – ist exakt.
  Wächter: `test_every_holder_gets_its_own_answer`, `test_two_shares_of_one_instance_add_up`,
  `test_frontend_mirrors.py: test_the_draft_is_framed_like_the_order_it_will_become`; gegen
  echtes PostgreSQL 16 verifiziert (14 + 8 Prüfungen: beide Halter genannt, halbe Antwort
  genügt nicht, warten ↔ reduzieren wirken getrennt, freier Anteil fragt niemanden, zwei
  Zeilen derselben Instanz zählen zusammen).

- **Der Zustand gehört zum MATERIAL, und eine Teilung hat DREI Stellen** (August 2026,
  Testnotizen #493–#499): Zwei Fundamente waren falsch; alles darüber war Kompensation.
  **(1) `reserved` war eine Aussage über den betrachtenden Auftrag** (#495). Es hiess «der
  Auftrag, den ich gerade ansehe, läuft noch» (`order.status == 'released'`) – damit sah
  DASSELBE Stück im selben Moment verschieden aus: gelb («Reserviert») vom laufenden Eltern,
  grün («Freigegeben», also **frei am Lager**) vom abgeschlossenen Abzweig, obwohl es die
  ganze Zeit dem Eltern gehörte. Das war nie eine Eigenschaft der Menge, sondern der
  **Blickrichtung**. Jetzt sagt es, was es behauptet: *beansprucht ein Auftrag diese Menge?*
  (`instances.reserved_quantity`). Damit ist der Zustand überall derselbe – dieselbe Frage,
  dieselbe Antwort wie am Instanz-Detail –, und der lebende Rest zerfällt sauber in
  **gebunden** und **frei** (Zustand pro Menge, wie #483/#485 verlangt).
  **(2) Der Bypass ist nicht dasselbe wie «unterhalb der Zusammenführung»** (#496). Eine
  Teilung hat drei Stellen – *über* ihr das ganze Material, **neben** ihr das nicht
  Abgezweigte, *unter* ihr das Verbliebene **plus** das Zurückgekommene. Gerechnet wurde mit
  **zwei** Mengen: Bypass und «alles darunter» teilten sich eine. Damit die Zahl unten
  aufging, musste der Bypass verfälscht werden (bei einem abgeschlossenen Ast wurde nur das
  Verschrottete abgezogen) – und ein Stück, das VOLLSTÄNDIG in die Abweichung ging, stand
  trotzdem neben ihr auf dem Hauptprozess, obwohl es dort nie vorbeikam. Jetzt sagt jede
  Stelle, was sie ist: `minus` nimmt weg, was abzweigt (**immer** `flow_in` – wer abzweigt,
  ist nicht daneben), `plus` legt an der Zusammenführung dazu, was zurück **ist**. Dafür ist
  die Frage «was ging hinein» von «was ist zurück» getrennt: **`flow_back`** ist leer,
  solange der Ast läuft (vorher wäre es eine Vorhersage), und `returns_material` liest
  dieselbe eine Ableitung (`orders.returning_material`).
  **(3) Der Prozessbaum** (#493, `orders.material_trace`): Ein Auftrag ist keine Insel – vor
  dem Startknoten steht jetzt der **reguläre** Auftrag, aus dem sein Material kam, nach dem
  Endknoten der, an den es weiterging. Quelle ist die **Verarbeitungs-Historie**
  (`instance_order_links`, dauerhaft und chronologisch – ihr Docstring hatte genau das
  vorgesehen). Bewusst **nur reguläre** Aufträge: eine Abweichung ist eine Episode INNERHALB
  dieses Vorgangs und steht ohnehin als Abzweig im Bild; der eigene Eltern fällt heraus, weil
  er schon in der linken Spur steht. Ohne regulären Vorgänger ist der **Erzeuger** die
  Herkunft. Dargestellt in der **Material**sprache (Pille auf der Linie, Menge + Objektnummer,
  klickbar) – ein voller Auftrags-Knoten meint etwas anderes («dieser Auftrag ging aus jenem
  hervor», nicht «sein Material kam von dort»).
  **(4) Kleinigkeiten am Entwurfs-Rahmen:** kein zweiter Start-/Endknoten (#498 – der
  Schritt-Editor zeichnet seinen Fluss samt Terminals selbst); die **Schere sitzt AUF der
  Rückgabe-Linie** statt als kleines Zeichen im Knoten (#499, «manage dort das Zeugs, wo es
  auftritt») – gekappt heisst schlicht *keine Linie*, der Knoten bleibt und trägt den Knopf,
  der sie wiederbringt (die zweite Liste darunter ist entfallen); und der Rückweg eines
  Unter-Auftrags nennt **was** zurückgeht (#497), statt es nur zu behaupten.
  Wächter: `test_a_split_has_three_places_not_two`, `test_the_flow_is_a_tree_not_an_episode`,
  `test_the_draft_is_framed_like_the_order_it_will_become`, `test_the_flow_shows_what_material_moves`;
  gegen echtes PostgreSQL 16 verifiziert (16 + 16 Prüfungen: der gemeldete Fall Schritt für
  Schritt – Bypass leer, solange der Ast läuft UND nachdem er durch ist; derselbe Zustand aus
  beiden Blickrichtungen; Verschrottetes kommt nicht zurück; der Baum überspringt
  Unter-Aufträge und den eigenen Eltern).

- **Das Material-Journal – der Neuaufbau des Fundaments (ADR 007, Migration `098`)**:
  Nach den Bug-Runden #341–#499 hat der Nutzer den Reset verlangt: *«Ich muss 3 Sachen
  wissen – was muss ich mit was im Moment machen, was kommt voraussichtlich als Nächstes,
  und was ist passiert. Und das, was passiert ist, kann unter keinen Umständen mehr
  geändert werden.»* Die Analyse (vollständig in `docs/adr/007-material-ledger.md`, VOR
  jeder Arbeit an Instanz-Zustand/Mengen LESEN): fast alle Bugs hatten dieselben drei
  Wurzeln – (1) der Zustand ist ein **Skalar an der Instanz**, die Realität ist eine
  **Menge** (Charge: 3 in Arbeit + 1 verschrottet); (2) «wer hält wie viel» stand an
  **vier Stellen** (`reservations`/`subject_of_order_id`/`reserved_for_order_id`/
  `order_id`), die Regeln immer wieder zusammenraten mussten; (3) die **Vergangenheit
  wurde aus der Gegenwart rekonstruiert** (bewegliche Ziele) – die `asOf`-Mechanik der
  Oberfläche war Kompensation dafür, dass die Daten keine Geschichte haben.
  **Das Modell: Bestand ist ein Konto, jede Veränderung eine Buchung, Buchungen sind
  unveränderlich.** Eine Menge ist zu jedem Zeitpunkt in genau einem **Topf**
  `(Halter · Qualität · Verbleib)`; jedes fachliche Ereignis ist eine Journalzeile
  (`material_moves`, append-only – es existiert KEIN Update-/Delete-Pfad):
  `created | opening | taken | returned | released | sold | consumed | scrapped |
  blocked | unblocked`. Daraus folgen die drei Antworten ohne weitere Regeln:
  **Passiert** = die Zeilen (`ledger.history`, as-of per `up_to_id` – eine Abfrage, keine
  Rekonstruktion) · **Jetzt** = der Kontostand (`ledger.lots`, Zustand JE MENGE – das
  Chargen-Problem löst sich im Modell statt in der Anzeige) · **Als Nächstes** = der Plan
  (Schritte, unverändert – er darf sich ändern).
  **Ein Schreibweg** (`services/ledger.py`): die fachlichen Dienste buchen an ihren
  semantischen Punkten – `serialization` (created), `subject.record_link` (taken),
  `process.release_instances` (released), `subject.return_borrowed` +
  `deviation.detach_sub_order` (returned – beide Türen), `process.sell_order_subjects`
  (sold), `process._restock_one` (returned aus dem terminalen «sold»-Topf – der EINE
  legitime Weg dort heraus, `src_disposition='sold'`), `resource` (consumed), `scrap`
  (scrapped/blocked/unblocked), `inspection` (blocked/unblocked), Abschluss-Release in
  `recompute_completion`. **Buchhaltung streng, Zuordnung tolerant**: eine Buchung
  entnimmt nie mehr als da ist (Drain: bevorzugt derselbe Halter, dann grösste lebende
  Töpfe); was fehlt, wird als `note='!unbalanced'` SICHTBAR gebucht statt still
  verschluckt – `ledger.verify_instance` findet Drift (Journal ↔ Projektion).
  **Eröffnungsbilanz statt Migration**: Alt-Instanzen bekommen vor ihrer ersten Buchung
  ein `opening` mit dem heutigen Stand (aus den Projektionen) – keine gelogene Historie;
  `created` eröffnet NICHT (Entstehen hat keine Vergangenheit – der erste gefundene
  Harness-Bug: doppelte 4→8). Aufträge ohne Journal werden weiter aus Links + Event-Strom
  gelesen (tolerant lesen, streng schreiben).
  **Bereits umgestellt auf Journal-Lesen**: `_flow_back`/`returns_material` («was kam
  zurück?» = die tatsächlichen Rückgabe-Buchungen `ledger.departed_of`, je Zustand – die
  Status-Fallunterscheidung «leer solange er läuft» LÖST SICH AUF: ein laufender Ast hat
  schlicht noch keine Rückgaben; Legacy-Pfad nur für Alt-Aufträge ohne Buchungen) und der
  **Instanz-Verlauf** (Big-Picture-Stufe 3: `InstanceResponse.history` +
  `MoveJournal` im Reiter «Aufträge» – wann · was · wie viel · Zustand danach ·
  beteiligter Auftrag, chronologisch, klickbar).
  **Die alten Spalten sind ab jetzt PROJEKTIONEN** (Lesehilfen für Feed-Badges/FIFO-SQL;
  die Reservierungs-Map bleibt zusätzlich das PLANUNGs-Instrument – Ansprüche sind
  Absichten, keine physischen Ereignisse, sie gehören nicht ins Journal).
  **Ausbaustufen (definiert in ADR 007)**: (2) `order_material`/Fluss-Kanten vollständig
  aufs Journal, `as_of` als Journal-Abfrage statt Stichtags-Arithmetik im Frontend;
  (3) Skalar-Spalten stilllegen (Folge-Deploy-Muster), FIFO auf Journal-Töpfe, `shares`
  als reine Journal-Sicht.
  Wächter: `test_the_material_journal_answers_the_three_questions` (append-only, alle
  zehn semantischen Punkte buchen, Kontostand je Topf, `!unbalanced` sichtbar); gegen
  echtes PostgreSQL 16 verifiziert (`journal.py` 24/24 – kompletter Lebenszyklus durch
  die ECHTEN Service-/Router-Pfade: Erzeugung → Abweichung nimmt 1 von 4 → verschrottet →
  Eltern reduziert → Datenerfassung → Abschluss → Verkauf → Rückgabe aus «sold»; nach
  jedem Schritt Kontostand == Projektion und der as-of-Stand von vorher unverändert;
  plus alle 5 bestehenden Harnesses regressions-frei, Migration 098 von null +
  idempotent).

- **Material-Journal Ausbaustufe 2: die Achse liest das Journal, der Verlauf steht an
  beiden Enden** (August 2026, Fortsetzung ADR 007 auf ausdrücklichen Nutzer-Wunsch
  «alles nochmals neu betrachten, freie Hand, nicht rückwärtskompatibel»):
  **(1) `order_material` ist eine Journal-Sicht** (`ledger.order_view`): alles, was je in
  einen Auftrag hineingebucht wurde, ist genau EINMAL da – als noch gehaltener Topf, als
  terminaler Topf (ihm zugeschrieben, mit Zeitpunkt aus der Buchung) oder als abgegebene
  Menge (im Zustand, in dem sie ging). Kein `held_quantity`, keine Links-Menge, keine
  Reservierungs-Map mehr im Lesepfad – die Grössen, die sich bewegen, können die
  Vergangenheit nicht mehr umschreiben. Eine **Rückkehr verzehrt ihre Abgabe-Zeile**
  (`consume_departed` – sonst stünde Zurückgekehrtes doppelt: abgegeben UND gehalten;
  im Harness gefunden). «Gebunden» ist eine Eigenschaft des **Topfs** (gehalten UND am
  Lager), nie des Betrachters (#495) – auch eine Abgabe-Zeile trägt den Zustand des
  Materials (ging es in fremde Obhut → gebunden). Die Achse eines ABGESCHLOSSENEN
  Abzweigs zeigt den **eingefrorenen** Abgabe-Zustand mit Zeitstempel (#488) – dass der
  Eltern es inzwischen freigegeben hat, ist SEINE Gegenwart, kein Widerspruch.
  Alt-Aufträge ohne Buchungen → `_order_material_legacy` (tolerant lesen).
  **(2) Drei im Umbau gefundene und behobene Fehler:** (a) `_drain` griff bei fehlender
  Quell-Angabe in den Topf eines FREMDEN Auftrags, obwohl freier Bestand daneben lag –
  Rangfolge jetzt: genannter Halter ≻ **freier Bestand** ≻ fremde Halter (dieselbe Regel
  wie `shares.losses`); (b) `post` las den Kontostand, bevor die eben ge-`add`-ete
  Eröffnung geflusht war → buchte gegen einen leeren Stand als `!unbalanced` (dieselbe
  Lehre wie #392: erst schreiben lassen, dann lesen – `db.flush()` vor `lots()`);
  (c) `returns_material` hatte WIEDER zwei Regeln (Teaser ≠ eigene Ansicht – exakt was
  #492 verbietet) → EINE Regel: lebendes Material vorhanden ⇒ der Weg führt zurück
  (läuft er noch, WIRD es kommen; ist er durch, IST es gegangen).
  **(3) Der Verlauf steht an BEIDEN Enden derselben Geschichte:** `OrderResponse.history`
  (nur Personal) + gemeinsame Komponente `components/erp/move-journal.tsx` – am
  **Instanz**-Detail nennt der Chip den Auftrag, am **Auftrags**-Detail die Instanz.
  Im Auftrag steht er als «Verlauf» direkt unter dem Fluss: oben JETZT (aktiver Schritt +
  Material) und ALS NÄCHSTES (der Plan), darunter PASSIERT (die Buchungen) – die drei
  Fragen sind damit wörtlich die Seite.
  Wächter: `test_the_material_journal_answers_the_three_questions` (erweitert um
  Ausbaustufe 2: order_view, consume_departed, Drain-Rangfolge, history an beiden Enden);
  gegen echtes PostgreSQL 16: **alle 6 Harnesses grün (99 Prüfungen)** – die zwei
  Alt-Harnesses, die Mutationen von Hand simulierten (direkte Zuweisungen statt
  Service-Pfade), wurden dabei vom Journal ENTLARVT und auf die Buchungen nachgezogen:
  genau die Drift-Sichtbarkeit, für die das Journal gebaut ist.

- **Visualisierungs-Stufe: das Frontend ZEICHNET, der Server WEISS** (August 2026,
  ADR 007 Stufe 3; Antwort auf «Prozesslinien … semiguter codetechnischer Ansatz – mit dem
  Wissen von heute anders?»): Der Fluss-Renderer (`order-flow.tsx`, 1350 Zeilen) rechnete
  mitten im React-Code weiterhin WAHRHEIT aus – Material-Subtraktion an Teilungen
  (`minus`/`plus`), die Stichtags-Zeitmaschine (`asOf`/`cutoffs`), «wo steht der
  Prozess?». Genau diese Client-Arithmetik war die Quelle der wiederkehrenden
  Mengen-Notizen (#421/#425/#459/#464/#467/#469/#488/#496). Jetzt liefert das Backend die
  **fertig gerechnete Achse**: `OrderResponse.flow_nodes`/`flow_edges`
  (`orders._fill_flow_view`) – Knotenliste (Schritt/Teilung), Fortschritt
  (`reached`/`passed`), der EINE Prozess-Punkt (`live`; keiner an einem nicht laufenden
  Auftrag), Material je Kante im **Zustand von damals** (`_as_of` serverseitig; die
  letzte Kante zeigt das ERGEBNIS – ein Stichtag würde dort die Abschluss-Freigabe
  zurückdrehen) und der **Bypass** je Teilung (live = Journal-Custody `held+terminal`,
  Vergangenheit = Stand von damals − Abzweig). **Gefiltert statt subtrahiert:** die
  Journal-Zeile weiss, wohin sie ging (`ledger.ViewRow.to_order`) – was in einen Abzweig
  ging, liegt unterhalb seiner Teilung in DESSEN Spur, nicht mehr auf der Achse; was
  zurückkam, ist wieder gehalten (Rückkehr verzehrt die Abgabe-Zeile). Zweite Hälfte:
  die **Prozesslinien wohnen in EINEM Modul** (`components/erp/flow-line.tsx` –
  Spurbreiten `MAIN/SIDE/GAP/ARM/BEND/RUN`, `Axis`, `Elbow`-Pfade, Drei-Spuren-`Row`,
  `aside`); `order-flow.tsx` importiert sie und zeichnet nur noch (Entwurfs-Rahmen
  `DraftFlowFrame` inklusive). `running`-Prop entfallen (steckt in der Server-Sicht).
  Wächter: `test_the_frontend_draws_and_the_server_knows` (FE ohne jede
  Material-Arithmetik, Server-Funktionen vorhanden, Linien-Modul die eine Quelle);
  PG16-Harness `flowview.py` (19 Prüfungen: 1 Schritt/2 Kanten mit live-Punkt oben,
  offene Abweichung → Teilung vor dem Schritt + Bypass 3 als live-Stelle, Kante über dem
  Fork zeigt 4 im Zustand von davor, abgeschlossen → keine live-Stelle und letzte Kante
  3, Alt-Auftrag ohne Journal → Legacy-Kanten). **Zwei Fehler dabei gefunden** (vom
  Harness, nicht vom Ahnen): die letzte Kante eines abgeschlossenen Auftrags drehte per
  Stichtag ausgerechnet die Abschluss-Freigabe zurück, und der Bypass einer VERGANGENEN
  Teilung war leer, weil die Custody-Sicht nach Abschluss nichts mehr hält.

- **Testnotizen-Runde 30 (die Ausleihe kommt zurück, das Layout steht still, Notizen
  #502–#505)**: Ein echter Datenfehler und drei Ursachen von Unruhe.
  (1) **Die Rückgabe sind ZWEI Fragen, nicht eine** (#505, `subject.give_back`). Gemeldet:
  «der Abweichungsauftrag wurde abgeschlossen, die Instanz sollte zum Hauptauftrag
  zurückkehren – wird aber nicht angezeigt, es scheint, als hänge sie noch im Abzweig».
  Genau so war es: `return_borrowed` übersprang eine Instanz, deren Verleiher ihr
  **Erzeuger** ist (`inst.order_id == parent.id`) – richtig gedacht für die
  **Reservierung** (ein Erzeuger hält über `Instance.order_id` und braucht keine), aber in
  derselben Bedingung hing auch die **Buchung**. Das Journal kennt nur Buchungen: ohne
  Rückgabe blieb die Menge für immer in der Obhut des Unter-Auftrags, und die Achse des
  Eltern zeigte sie unterhalb der Teilung nicht mehr (gegen echtes PostgreSQL
  reproduziert: `created → taken(main→dev) → released(dev→frei)`, **keine** Rückgabe).
  Jetzt trennt EINE Stelle die beiden Fragen – *wo ist das Material?* (immer zurück an den
  Verleiher) und *wer beansprucht es?* (nur, soweit er noch etwas braucht) –, und **beide
  Türen** (Abschluss und Verwerfen) gehen hindurch.
  (2) **Vor UND nach jedem Modul steht, was fliesst** (#505): das Material eines Auftrags
  ist eine Tatsache und liegt auf seiner **ganzen** Achse. Die frühere Regel «erst ab
  `reached`» liess ausgerechnet unterhalb des aktiven Moduls eine Lücke, die sich las wie
  «hier ist nichts mehr». Das revidiert #421 ausdrücklich – dessen Sorge (eine Behauptung
  über die Zukunft) ist mit der Server-Sicht erledigt: gerechnet wird aus dem Journal von
  oben nach unten, nicht aus dem heutigen Bestand hochgerechnet. Wie weit der Prozess ist,
  sagt allein die **Linienstärke**. Dazu präzisiert: **neben** einer Teilung liegt nur, was
  NICHT abgezweigt ist – auch nachdem der Ast zurückgegeben hat (es lief durch ihn hindurch,
  nicht an ihm vorbei, `_returned_from`).
  (3) **Die Palette klappt auf, ohne etwas zu bewegen** (#502/#503). Der Knopf wuchs beim
  Hovern selbst; in einer umbrechenden Zeile schob das den nächsten Eintrag eine Reihe
  tiefer – und weil er dabei **unter dem Cursor wegwanderte**, endete der Hover, er
  schrumpfte, der Hover begann erneut: die Rückkopplung war das gemeldete «Springen und
  Hüpfen». Jetzt hat der Knopf eine feste Grösse (44 px) und die Pille wächst als absolut
  positionierte Fläche aus ihm heraus – dieselbe Bewegung, aber das Layout steht still.
  (4) **Eine Hover-Erklärung blasst nie aus** (#504): sie steckte in gedämpften Behältern
  (vergangene Kante, zurückgetretene Nachbar-Spur) und erbte deren Deckkraft – gegen eine
  geerbte `opacity` kann ein Kind sich nicht wehren. Sie hängt jetzt im **Portal am `body`**
  (ausserhalb jeder Dämpfung, jeder Überlauf-Kante, jeder Stapel-Ordnung); gedämpft bleibt
  allein die Pille.
  (5) **Prozesslinien, codetechnisch nachgezogen** (Rückmeldung «gefühlter optischer Versatz
  beim Radius»): die vier handgeschriebenen Ecken-Pfade (je eigene Bogen-Mathematik und
  Sweep-Flags – vier Stellen, an denen ein Radius auseinanderlaufen konnte) sind zu **einem
  Polygonzug je Ecke** geworden; wie eine Ecke aussieht, entscheidet die eine Funktion
  `roundedPath` (Drehrichtung aus dem Kreuzprodukt, nicht von Hand). Der sichtbare Versatz
  hatte zwei Ursachen, beide behoben: an einer Ecke trafen **zwei verschiedene Bits**
  aufeinander (3 px Achse ↔ 2 px Ecke – jetzt liest die Ecke dasselbe Bit wie ihr
  Achsenstück, `reached` oben, `passed` unten), und zwei getrennt gezeichnete Elemente
  treffen sich nie pixelgenau (jetzt **überlappen** sie um 1 px, `OVERLAP` – so kann an
  keiner Naht ein Spalt entstehen).
  Wächter: `test_a_deviation_borrows_and_gives_back` (erweitert),
  `test_the_material_is_on_the_whole_axis_and_only_predictions_are_left_out`,
  `test_the_palette_unfolds_without_moving_anything`,
  `test_a_hover_explanation_is_never_dimmed`; PG16-Harness `note505.py` (11 Prüfungen:
  die gemeldete Abfolge Schritt für Schritt).

- **Systemprotokoll am Auftrag – ein Audit-Log für die Fehlersuche** (August 2026,
  `services/diagnostics.py`, `GET /api/v1/erp/orders/{id}/diagnostics`): Auf Wunsch
  «damit ich verstehe, was das System macht und warum es scheitert – und darüber
  rapportieren kann». Der Abschnitt «Verlauf» beantwortet die **fachliche** Frage (was ist
  mit dem Material passiert); eine Ebene tiefer zählt, **welcher Mechanismus** eine Zahl
  erzeugt hat und ob die abgeleiteten Grössen noch zueinander passen.
  **Keine vierte Wahrheit:** das Protokoll stellt die drei Ströme nebeneinander, die es
  ohnehin gibt – `audit_log` (**Absicht**: wer hat welches Feld geändert) · `events`
  (**Wirkung**: welches fachliche Ereignis lief los) · `material_moves` (**Bestand**, ADR
  007) – und daneben den **Befund**: den abgeleiteten Zustand zum Abfragezeitpunkt
  (Schritte samt `state`, Fehlmenge, Unter-Aufträge, je Instanz Projektion **und**
  Journal-Kontostand, Anteils-Aufteilung) inklusive **Drift-Prüfung**
  (`ledger.verify_instance`). Ein Bug ist fast immer ein Widerspruch zwischen zwei dieser
  Angaben – nebeneinander gestellt sieht man ihn sofort statt nach einer Stunde
  Rekonstruktion. Der **Umfang ist die Nachbarschaft** des Auftrags (seine Unter-Aufträge
  und alle beteiligten Instanzen), denn dort passieren die Fehler, die man am Auftrag
  bemerkt.
  **Kein Datensatz, sondern eine Sicht:** keine Objektnummer, kein Feed, rein lesend,
  Personal-only, **auf Klick** geladen (sie ist um Grössenordnungen umfangreicher als der
  Auftrag). «Als Markdown kopieren» erzeugt den vollständigen Bericht (Befund + Anteile +
  Chronologie + Build-Commit) zum Einfügen in eine Entwicklungs-Sitzung – dieselbe Brücke
  wie bei den Testnotizen, nur für den Maschinenzustand statt für das Pixel. Ein Deckel je
  Strom verhindert Riesen-Antworten und sagt es (`truncated`) – ein stiller Deckel läse sich
  wie Vollständigkeit. Wächter `test_the_order_carries_a_system_log_for_bug_reports`; gegen
  echtes PostgreSQL über den Router-Pfad verifiziert (JSON-fähig inkl. `Decimal`, alle drei
  Quellen, 404 bei unbekanntem Auftrag).

- **Testnotizen-Runde 31 (das Protokoll spricht Deutsch, die Palette hat eine Namenszeile,
  Notizen #506–#514)**: Zwei echte Befunde im Protokoll selbst und eine dritte Antwort auf
  die Palette.
  (1) **Das Systemprotokoll war ein Tabellen-Abzug** – jetzt spricht es (#506–#512).
  `2.0 · 296/in_process → 297/in_process`: 296/297 sind **interne Schlüssel**
  (`orders.id`), die niemand in Objektnummern übersetzen kann; die Zeile war damit
  wertlos. Drei Regeln lösen das: **Objektnummern statt interner Schlüssel**
  (`_Names.order` → «Abweichung 100000610»), **ein Satz statt Rohwerten** («1 übernommen:
  Auftrag … → Abweichung …», Rohwerte bleiben im Hover/Bericht), und **der Befund zuerst
  in Klartext** (`zusammenfassung` – worum es geht, was passiert ist, warum es nicht
  weitergeht, vor der ersten Tabellenzeile). Dazu Zustände in Worten («noch nicht bewertet
  · in Arbeit (zählt nicht zum Lagerbestand)» statt «pending · in_process») – das
  beantwortet nebenbei #508: Bestand VOR dem Wareneingang ist kein Fehler, denn «in
  Arbeit» zählt nicht zum Lager (gezählt wird `passed`+`in_stock`).
  (2) **Zwei Meldungen waren schlicht falsch bzw. doppelt** – an der Quelle behoben:
  «Ressourcen reserviert» stand **unbedingt** im Protokoll, auch bei einem Auftrag ganz
  ohne Verbrauchs-Schritt, wo nichts zu reservieren war (#506/#512) → protokolliert wird
  jetzt nur, was **tatsächlich** reserviert wurde, mit Menge und Instanz. Und «Status
  draft → released» war der Fussabdruck einer **internen** Zwischenstufe: ein Auftrag
  entsteht als Ganzes (#386), er war nie ein gespeicherter Entwurf – die Zeile ist weg,
  «Auftrag erteilt und freigegeben» bleibt (#507). Schlanker wurde es zusätzlich durch
  `MIRRORED_BY_JOURNAL`: ein Ereignis, das dasselbe sagt wie eine Buchung im selben
  Augenblick, ist keine zweite Information.
  (3) **Die Palette bekommt eine Namenszeile** (#509/#510, revidiert #502/#503): zwei Wege
  sind gescheitert, beide an derselben Wurzel – der Name braucht Platz, den die Reihe
  nicht hat. Wuchs der **Knopf**, brach die Zeile um und er wanderte unter dem Cursor weg
  (Flackern); wuchs eine **Pille** aus ihm heraus, überdeckte sie die Nachbarn. Jetzt hat
  der Name seinen eigenen Platz: **eine reservierte Zeile unter der Palette** (feste Höhe,
  zentriert; solange niemand zeigt, steht dort, was zu tun ist). EIN Baustein
  (`fields.Palette`) für alle drei Paletten – Module, Erfassungsfelder, Unterdeckung.
  (4) **Das Material steht UNTER dem Startknoten** (#513) – im Abzweig wie im geöffneten
  Auftrag: der Startknoten markiert den Anfang, das Material fliesst danach. Vorher stand
  es darüber, und derselbe Vorgang sah je nach Ansicht anders aus.
  (5) **Kommt nichts zurück, steht da, was daraus geworden ist** (#514): am Ende eines
  Abzweigs die ausgesonderte Menge in ihrer Ampelfarbe (rot) – ohne Linie, denn es fliesst
  nichts zurück. «Keine Rücklinie» sagte DASS, nicht WARUM. *(Der Entscheidungs-Knoten am
  Eltern bleibt: er ist der einzige Weg, die Unterdeckung zu beantworten.)*
  Wächter: `test_the_system_log_is_readable_without_prior_knowledge`,
  `test_the_palette_name_has_its_own_line`, `test_a_sub_order_is_a_regular_process_beside_
  the_axis` (erweitert um #513/#514).

- **Testnotizen-Runde 32 (ein festes Subjekt arbeitet mit dem, was es hat, Notizen
  #515–#523)**: Das Systemprotokoll hat den Kern selbst gezeigt – die Kette
  Auftrag → Abweichung → Abweichung stellte **dieselbe Frage auf jeder Ebene**.
  (1) **Ein Auftrag mit festem Subjekt hat kein Soll – bis ihm NICHTS mehr bleibt**
  (#522/#523, `process._fixed_subject_shortfall`): Verliert eine Abweichung über 4 Stück
  eines davon (ihre eigene Abweichung hat es verschrottet), fehlt ihr nichts – sie hat
  **weniger zu tun**, und die Verschrottung WAR die Klärung. Sie danach erneut zu fragen
  war eine Schleife ohne Erkenntnisgewinn, die zudem ihren ganzen Prozess anhielt
  («Warum ist dieser Prozessschritt nicht aktiv?»). Gefragt wird jetzt der Auftrag, der
  die Menge wirklich **schuldet** – der reguläre Eltern – und die Abweichung nur dann,
  wenn ihr **nichts** mehr bleibt: dann ist sie gegenstandslos, und «Menge reduzieren» ist
  ihr Abbruch (genau der Befund von #397, der damit erhalten bleibt).
  (2) **Eine Menge, ein Zustand, EINE Zeile** (#520): der Rückblick (`_as_of`) drehte
  ausgesteuerte Mengen in «in Arbeit» zurück, **ohne sie mit der ohnehin gehaltenen Zeile
  zu verschmelzen** – auf der Kante stand «3 Stk × 613» UND «1 Stk × 613» statt «4 Stk ×
  613». Behoben in Backend und Frontend (dieselbe Regel, beide Seiten).
  (3) **Keine Prognosen** (#521, revidiert die zweite Hälfte von #505): eine Kante
  unterhalb des Prozess-Punktes trägt kein Material – was ein Modul einmal führen wird,
  ist nicht vorhersehbar. Die in #505 gemeldete Lücke war ohnehin keine Anzeige-, sondern
  eine **Buchungs**frage (die fehlende Rückgabe), und die ist behoben.
  (4) **Zuerst die Freigabe, dann ihre Folgen** (#517): «Bestellung angefragt» stand im
  Protokoll VOR «Auftrag freigegeben», obwohl die Bestellung erst aus der Freigabe
  entsteht – `release_order` schreibt sein Ereignis jetzt als erstes; der doppelte
  Audit-Eintrag am Router ist entfallen.
  (5) **Die Palette: ein Symbol, im Hover sein Name** (#518, dritter Anlauf nach
  #502/#503 und #509/#510). Der wachsende Knopf brach die Zeile um, die herauswachsende
  Pille überdeckte die Nachbarn, die Namenszeile darunter schrieb den Namen zweimal hin.
  Übrig bleibt das Einfachste: fester Knopf, Hover = **Name** (die lange Erklärung ist
  entfallen). Dazu steht die Palette jetzt **vor** der Zielflagge (#519) – ein Modul wird
  in den Prozess eingefügt, nicht dahinter.
  (6) **Material steht NIE nach der Zielflagge** (#516): im Abzweig gehört es – wie auf der
  Hauptachse – zwischen das letzte Modul und den Endknoten. Kommt nichts zurück, steht dort
  die ausgesonderte Menge in Rot (#514).
  (7) **Der Zustand entfällt im Hover** (#515) – die Ampelfarbe der Pille sagt ihn bereits;
  im Hover bleiben Artikel und Standort.
  Wächter: `test_every_affected_order_is_asked_the_same_question` (präzisiert),
  `test_no_edge_shows_material_it_has_not_carried_yet`,
  `test_the_palette_shows_its_name_in_the_hover`,
  `test_the_system_log_is_readable_without_prior_knowledge` (erweitert um #517).

- **Die Regel steht im Code, nicht in der Prosa** (ADR 008, `docs/adr/008-unterdeckung.md`;
  August 2026, **ohne Funktionsänderung**): Unterdeckung/Ausleihe/Pause hat die meisten
  echten Logikfehler erzeugt (#354 · #366 · #388 · #397 · #401 · #404 · #505 · #522/#523) –
  **nicht** wegen des Datenmodells (das Journal meldet überall `drift: []`), sondern weil es
  **keine geschriebene Regel** gab: sie lebte als gewachsene Prosa hier in dieser Datei,
  verteilt über zwanzig Absätze aus zwanzig Runden. Prosa kann sich widersprechen, ohne dass
  es jemand merkt; zweimal wurde dieselbe Frage (*hat ein festes Subjekt ein Soll?*) in
  entgegengesetzte Richtungen entschieden.
  **Jetzt ist die Regel eine ausführbare Tabelle** (`backend/tests/rules/table.py`): sechs
  Zeilen, jede mit Lage, erwarteter Antwort (Fehlmenge · Pause) und **Begründung**.
  `test_shortfall_rules.py` baut jede Zeile über die **echten** Dienste auf (Freigabe,
  Router-Pfad, Verschrottung – kein Nachstellen von Zuständen) und prüft, was die Oberfläche
  daraus liest. Bricht eine Zeile, steht ihre Begründung im Fehlertext: wer die Regel ändert,
  ändert zwangsläufig auch den Satz, der sie erklärt.
  Dazu das **Szenario-Netz** (`test_scenario_chain.py`): die Kette, die im Praxistest wirklich
  gefahren wird (Auftrag → Abweichung → Abweichung → Verschrottung → Klärung) in sechs
  Stationen – bisher lief sie nur von Hand, weshalb Regressionen erst Tage später am
  Bildschirm auffielen. Beides läuft in der **CI bei jedem Push** gegen echtes PostgreSQL
  (Schritt «Regel-Tabelle + Szenario-Netz»); ohne Datenbank überspringen sie **mit Grund**
  (gegen SQLite wäre die geprüfte Wahrheit eine andere: JSONB-Ansprüche, Zeilensperren).
  Wächter `test_the_rule_table_runs_on_every_push` – ein Netz, das stillschweigend
  abgeschaltet ist, ist von einem kaputten nicht zu unterscheiden.
  **Arbeitsweise daraus** (die eigentliche Lehre): eine **Regel**-Notiz wird nicht sofort
  umgesetzt – erst wird gesagt, welche Zeile sie kippt und was daraus folgt, dann entscheidet
  der Nutzer; **Optik**-Notizen werden direkt umgesetzt. Neue Fälle kommen als **Zeile** dazu,
  nicht als Sonderfall im Code.

- **«Wie viel bearbeitet dieser Auftrag?» – die zweite Regel neben der Unterdeckung**
  (August 2026, `services/order_lines.py`, erste Arbeit **gegen** die Regel-Tabelle): Sie hängt
  an derselben Unterscheidung wie ADR 008 und war genau dort falsch, wo die Unterscheidung
  fehlte. Ein **regulärer** Auftrag bearbeitet seine **Zusage** – gespeichert, weil sie eine
  Entscheidung ist, und sie schrumpft nicht, nur weil gerade ein Stück in Klärung ist (sonst
  gäbe er seine Komponenten frei und müsste sie neu anfordern, sobald die Ausleihe zurückkommt).
  Ein Auftrag mit **festem Subjekt** bearbeitet seine **Arbeitsmenge**: was ihm von seinen
  Instanzen noch gehört (`subject.held_quantity` – dieselbe eine Antwort, aus der schon der
  Prüfumfang kommt, #399). Beides beantwortet jetzt **eine** Funktion (`effective_quantity`);
  die reine Anlage-Aussage heisst `declared_quantity` («auf 4 Stück eröffnet» – gilt auch nach
  dem Abschluss noch).
  **Der Befund war gemessen, nicht vermutet:** eine Abweichung, auf 4 Stück eröffnet, die eines
  an ihre eigene Abweichung verloren hatte, verlangte weiter Komponenten für 4 – **8 statt 6
  Schrauben**. Keine Anzeigefrage: der Überschuss war für jeden anderen Auftrag gesperrt und
  erzeugte dort eine Fehlmenge, die es nicht gab. Betroffen waren alle Leser derselben Frage
  (`resource.reserve_resources`, `process._component_needs`/`_component_shortfall`,
  `provisioning._component_candidates`) – die Datenerfassung hatte sich die Antwort längst
  selbst gebaut, weil die gemeinsame Stelle sie nicht gab.
  *Bewusst NICHT geändert:* die bei der **Freigabe** gebuchte Reservierung (damals hielt der
  Auftrag die volle Menge – sie war richtig; der Überschuss löst sich mit seinem Abschluss) und
  die **gespeicherte** Menge selbst. Sie lässt sich nicht ableiten: ein abgeschlossener
  Unter-Auftrag hält nichts mehr, eine abgeleitete Menge stünde dort auf 0.
  Neue Zeile im Netz: `tests/rules/test_working_quantity.py` (gegen die Bug-Form gegengeprüft).

- **Jedes Stück hat eine eigene Nummer** (August 2026, `services/units.py`, Migration `099`):
  Eine Instanz war eine **Menge** unter EINER Nummer – «100000101 · 4 Stk». Welches der vier
  Stück gerade in einer Abweichung steckt, liess sich nicht sagen; es gab die Frage gar nicht,
  nur Summen. Genau daraus kam die wiederkehrende Fehlerklasse (zwei Halter, eine Zahl, kein
  Weg zu sagen *welches*). Jetzt trägt jedes Stück **`100000101-1` … `-4`**.
  **Ohne neue Datensätze – und ohne Zeilen-Explosion.** Die Stücke wohnen IN der Instanz
  (`instances.units`), gespeichert als **Läufe**: eine Charge über 1000 Schrauben ist EIN Lauf
  (`{"r":[{"a":1,"b":1000,"q":"1"}],"next":1001}` – **56 Zeichen**), nimmt eine Abweichung drei
  Stück, sind es zwei Läufe. Die Nummern gibt es trotzdem alle. Dasselbe Muster wie
  `reservations` («wer beansprucht wie viel») und `locations` («wo liegt wie viel»), nur eine
  Ebene genauer: hier steht **welches Stück**.
  **Die Nummer ist eine Identität, keine Position** – einmal vergeben, nie neu verteilt. Wird
  ein Stück verschrottet, ist seine Nummer **entwertet** und kommt nie wieder (`next` merkt sich
  die höchste je vergebene); die übrigen behalten ihre. **Der Zusatz gilt ohne Ausnahme:** auch
  ein Einzelteil trägt `-1`, ebenso eine nicht zählbare Charge (2.5 kg = EIN Stück mit 2.5 –
  Kilogramm lassen sich nicht durchnummerieren, aber die Schreibweise bleibt dieselbe). Eine
  Sonderregel «bei genau einem Stück ohne Zusatz» wäre eine zweite Schreibweise für dieselbe
  Sache, und jede Ansicht müsste sie kennen.
  **Sie hängen an derselben Engstelle wie die Reservierung** (`reservation._write` →
  `units.sync`, `take` → `units.drop`): weil das die einzige Stelle ist, an der sich «wer
  beansprucht wie viel» ändert, ist es auch die einzige, an der sich «welche Stücke» ändern muss.
  Mengen und Nummern können damit nicht auseinanderlaufen – es gibt keinen zweiten Weg, an dem
  man es vergessen könnte; `units.verify` zeigt einen Drift, statt ihn still zu korrigieren
  (dieselbe Rolle wie `ledger.verify_instance`). Altbestand bekommt seine Nummern beim ersten
  Zugriff aus dem heutigen Stand (`ensure` – Eröffnungsbilanz wie im Material-Journal, keine
  erfundene Historie).
  **Drei Angaben, immer und überall** (Testnotizen #531/#532): **Nummer inkl. Zusatz · Menge ·
  Zustand**. Sie stehen in EINER Form (`InstanceUnit`), damit keine Ansicht sich eine eigene
  baut – und der Zustand als die beiden Instanz-Achsen, damit ihn jede mit **derselben**
  Projektion einfärbt (`instanceStatusConfig`). Zwei Dichten derselben Zeile aus EINER Quelle
  (`components/erp/unit-numbers.tsx`): `UnitList` ausgeschrieben (Instanz-Detail, Hover der
  Fluss-Kante), `UnitChips` kompakt als Zusatz zu einer Zeile, die Menge und Zustand schon nennt
  (Auswahl, Positionen). Das **Instanz-Detail listet jedes Stück einzeln** (#531, Kachel
  «Stücke», aufsteigend) statt nach Anteilen zusammengefasst – die Zusammenfassung sagte, wie
  VIEL in welchem Zustand ist, aber nicht WELCHES Teil. Die **Pille im Fluss** nennt die
  Objektnummer inkl. Zusatz (#532, zusammenhängende Nummern als Spanne `…-1…-4`); die
  vollständige Liste steht im Hover. Auf den Kanten nur für Material, das der Auftrag noch hält:
  für Mengen, die ihn verlassen haben, wäre eine geratene Zuordnung schlimmer als keine.
  **Wem der unbeanspruchte Rest gehört, ist EINE Regel** (`inventory.rest_owner`: der Erzeuger,
  solange die Instanz nicht am Lager liegt) – vorher stand sie nur bei den Anteilen, und dasselbe
  Stück hiess im Detail «frei» und in der Aufteilung «Auftrag …003».
  Listen sind ausserhalb des Instanz-Details gekappt (`shares.UNIT_PREVIEW`), `unit_count` nennt
  die Gesamtzahl.
  Wächter `tests/rules/test_units.py` (Nummern, Einzelteil ohne Zusatz, kg ohne Nummern,
  disjunkte Halter, entwertete Nummer, Sichtbarkeit) + `test_smoke.py:
  test_every_piece_is_numbered_at_exactly_one_place`. Gegen echtes PostgreSQL 16 verifiziert
  (19 Prüfungen; Migration von null, idempotent, downgrade; Lifespan-Netz mit gezogener Spalte).
  *Nächster Schritt (bewusst noch nicht): Zustand **je Stück** statt je Instanz – dann würde
  eine verschrottete Nummer stehen bleiben und rot werden, statt zu verschwinden («die Menge
  verschwindet nicht, nur der Zustand ändert sich», #481). Dafür müssten `quality`/`disposition`
  Projektionen der Läufe werden.*

- **Testnotizen-Runde 36 (eine Instanzanzeige ist überall dieselbe, Notizen #533–#540)**:
  Sechs der acht Notizen hatten **eine** Wurzel – auf der Kante über einer Teilung standen
  **zwei** Pillen für dieselbe Sache: «3 Stk» (gehalten, mit Nummern) und «1 Stk» (abgegeben,
  **ohne** Nummern, weil die Zuordnung nur für gehaltenes Material gefüllt wurde).
  (1) **Was hier noch auf der Achse liegt, liegt hier NOCH** (#537 – der Nutzer hatte die
  Ursache selbst benannt: «du gibst den Unterauftrag frei, entziehst die Instanzen dem
  Hauptauftrag und erst dann frierst du die Vergangenheit ein»). Eine Menge, die erst weiter
  unten abzweigt, war an dieser Stelle unverändert beim Auftrag – `axis_lots` präsentiert sie
  darum oberhalb ihres Splits als **gehalten**. Die Kante zeigt jetzt «4 Stk × …-1…-4», der
  Bypass die drei, die blieben, der Abzweig das eine, das ging.
  (2) **Die Nummern kommen von dem, der die Menge JETZT hält** – der Auftrag selbst oder der
  Abzweig, in den sie ging (`ViewRow.to_order`). Damit trägt **jede** Zeile ihre Stücke, egal
  aus welcher Richtung man sie ansieht (#536/#539/#540). Nur endgültig Ausgesondertes trägt
  keine mehr: seine Nummern sind entwertet, und eine geratene Zuordnung wäre schlimmer als
  keine.
  (3) **Eine Menge, ein Zustand, EINE Zeile** (`orders._merge_lots`): Zeilen derselben Instanz
  im selben Zustand werden verschmolzen (Mengen summiert, Nummern vereinigt und **aufsteigend**
  sortiert – dieselbe Ordnung wie im Instanz-Detail). Zwei Pillen für dieselbe Sache sind keine
  zwei Informationen.
  (4) **Keine Prognosen – auch nicht neben der Achse** (#538): eine Teilung, die der Prozess
  noch nicht erreicht hat, weiss nicht, was neben ihr liegen wird. Die Kanten hielten sich
  längst an #521, der **Bypass** tat es nicht.
  (5) **EINE Breite für den Prozess – überall** (#534): der Schritt-Editor war 600 px breit,
  der laufende Fluss 460 – dieselbe Sache in zwei Massen. `STEP_MAXW` ist jetzt `flow-line.MAIN`;
  die Breite gehört zum Linien-Layout, also steht sie dort.
  (6) **Mittig auf der Achse** (#533/#535): die Material-Pillen stehen zentriert, der
  Abkürzungs-Knopf hängt absolut daneben (vorher war «Container + Knopf» ein gemeinsamer Block –
  zentriert war die Gruppe, nicht das Material); und die Palette hat ihren Aussenabstand
  verloren, damit die Konnektoren oben wie unten den Takt geben.
  Wächter: `tests/rules/test_units.py: test_a_lot_always_names_its_pieces`.

- **Die Nummern gehören zur BUCHUNG, nicht zur heutigen Karte** (August 2026, Migration
  `100`, Testnotizen #541–#544): Der Nutzer hatte die Ursache exakt benannt – «sobald der
  Unterprozess abgeschlossen wurde, wurde die Vergangenheit angepasst». Gemessen: nach dem
  Abschluss zeigte die Abweichung «1 Stk × …-1, -2, -3, -4» statt «1 Stk × …-1». Die
  Nummern wurden aus dem **heutigen Halter** abgeleitet; gab der Abzweig beim Abschluss
  seine Stücke zurück, hielt er nichts mehr, und der Fallback lieferte **alle**.
  **Eine abgeleitete Antwort kann keine Vergangenheit sein** – genau die Prämisse von
  ADR 007. `material_moves.units` trägt jetzt die Nummern **dieser** Buchung; die Fluss-
  Zeile liest sie von dort (`ViewRow.units` → `units.rows_for`). Ein Abschluss ändert oben
  nichts mehr, und eine **verschrottete** Nummer bleibt in der Geschichte benennbar (die
  offene Grenze der Vorrunde ist damit geschlossen).
  **Wer die Nummern liefert, ist EINE Regel mit einer benannten Ausnahme**
  (`ledger._moved_units`): normalerweise schnappt die Buchung, was der Ziel-Halter gerade
  **beansprucht** (der Aufrufer hat unmittelbar davor umgehängt) – bewusst nur der Anspruch,
  nicht der über `Instance.order_id` geerbte Rest, der für eine einzelne Buchung viel zu
  breit wäre. Wer Stücke **entwertet** oder abgibt, nennt sie ausdrücklich: `scrap` über
  `reservation.take(gone=[…])`, `subject.give_back` hält sie **vor** dem Lösen fest.
  Dazu: **die Nummern gehen mit der Menge** – `_minus` zieht am Bypass genau die Stücke ab,
  die durch den Abzweig gingen (`_returned_from` nennt sie aus der Buchung), statt irgendwelche
  (#544). Und `units.owned_by` ist die eine Ableitung für gehaltene Zeilen (Anspruch ODER
  unbeanspruchter Rest – dieselbe Regel wie bei den Anteilen).
  **#542: nur der Schritt, der DRAN ist, lässt sich bedienen.** Ansehen darf man jeden
  (#471) – aber ein Schritt, der noch nicht an der Reihe ist oder gerade ruht, bietet keine
  Eingabe an (`planned = stepState !== 'active'` in allen vier Panels). Das Backend lehnte
  sie ohnehin mit 409 ab; ein Knopf, der nicht tut, was er verspricht, ist schlimmer als
  keiner.
  Wächter `tests/rules/test_units.py: test_the_past_keeps_its_numbers` (Abschluss ändert
  die Vergangenheit nicht; am Bypass passen Menge und Nummern zusammen und enthalten nicht,
  was durch den Abzweig ging). Gegen echtes PostgreSQL 16 verifiziert (Harness `note537.py`:
  laufender UND abgeschlossener Abzweig).

- **Parallel ist nur, was gleichzeitig läuft** (August 2026, Testnotizen #545–#548):
  (1) **#548 – der eigentliche Fehler war die Zeichnung, nicht die Daten.** Zwei
  Abweichungen aus demselben Schritt landeten in EINER Teilung – auch dann, wenn die erste
  längst abgeschlossen war, als die zweite entstand. Der Bypass rechnete beide ab (auch die
  zurückgegebene Menge), und Mengen und Nummern passten nicht mehr zusammen. Das Journal war
  dabei die ganze Zeit korrekt (`drift: []`, 3+1=4). Jetzt gruppiert `orders._waves` nach
  **Lebenszeit**: ein Abzweig kommt in die laufende Welle, wenn er sich mit JEDEM darin
  überschneidet (`completed_at` vs. `released_at`) – sonst beginnt eine neue. Zwei
  aufeinanderfolgende Abweichungen sind damit zwei Teilungen **nacheinander**, und jeder
  Bypass rechnet nur seinen eigenen Ast ab. Ohne Zeitstempel (Altbestand) gilt
  «überschneidet sich», damit nichts auseinanderfällt.
  (2) **#545 – die Materialpille trägt den Zustand als FLÄCHE**: Ampelfarbe als Hintergrund,
  Schrift darauf. Vorher sagten Rahmen, Symbol UND Schriftfarbe dasselbe dreimal – das
  wirkte überladen.
  (3) **#546/#547 – ein Mass für alles**: der Unterprozess hatte eigene Terminal-Knoten
  (30 px statt 52) – «eine Nummer kleiner» war eine zweite Massstab-Regel, die man der Sache
  ansah. Ebenso trägt der Schritt-Editor jetzt das Symbol-Mass der Karte, die er anlegt
  (38 px). Zusammen mit `STEP_MAXW = MAIN` (#534) ist damit jede Prozess-Darstellung –
  Entwurf, laufender Auftrag, Haupt- oder Unter-Auftrag – dieselbe Grösse.
  Wächter: `tests/rules/test_units.py: test_parallel_only_means_at_the_same_time` (zwei
  Teilungen nacheinander; und überall passen Menge und Nummern zusammen). Gegen echtes
  PostgreSQL 16 verifiziert (Harness `note548.py`, 6/6 – genau die gemeldete Abfolge).

- **Die Stücke folgen der Menge – und keines verschwindet** (August 2026, Testnotizen
  #549–#553): Zwei Befunde, eine gemeinsame Wurzel – die Stücke wurden **abgeleitet**
  statt geführt.
  (1) **Der genannte Anteil bestimmt, WELCHE Stücke gemeint sind** (#553). Gemeldet:
  «-2 und -3 sind in die Abweichung geflossen, -4 blieb im Hauptprozess … dann hat es die
  Logik zerschossen – auf einmal ist -3 im Hauptprozess und -4 im Unter-Unterprozess».
  Genau so war es, und es war kein Zufall: die Mengen-Seite hält sich längst an den
  angeklickten Anteil (`reservation.enforce` – «der genannte Anteil verliert IMMER», #394),
  die **Stücke** taten es nicht. `units.sync` griff zuerst in den *freien* Topf – der aber
  ist nicht herrenlos: solange die Instanz nicht am Lager liegt, gehört er ihrem **Erzeuger**
  (`inventory.rest_owner`). Also nahm die Abweichung der Abweichung dem **Hauptauftrag** sein
  Stück, und beim anschliessenden Geradeziehen der Mengen bekam er dafür irgendein anderes
  zurück – zwei Aufträge hatten getauscht, ohne dass jemand etwas getan hätte. Jetzt reicht
  `reservation._write` dieselbe Angabe durch, mit der die Menge arbeitet (`taker`/`source`
  aus `orders.pick_sources`), und `units._assign` bedient sich in dieser Rangfolge:
  **genannter Anteil ≻ frei ≻ fremd** – vom genannten die **höchsten** Nummern, wie
  `_release` sie zurückgibt. Der Halter ist damit keine Vermutung mehr.
  (2) **Ein Stück verschwindet nicht, es ändert seinen Zustand** (#549) – dieselbe Regel,
  die für die Menge seit #481 gilt, eine Ebene genauer. `units.drop` strich die Nummer aus
  der Karte; das Instanz-Detail zeigte danach `-2, -3, -4` und niemand konnte sagen, wo
  `-1` geblieben war. Jetzt bleibt der Lauf stehen und trägt seinen **Endzustand**
  (`{"x": "scrapped"|"sold"|"consumed"}`); gelesen wird er nur auf Nachfrage
  (`include_gone`), für alles Rechnende (`of`/`count`/`total`/`held_quantity`/`verify`)
  zählt er nicht mehr mit. Das Instanz-Detail listet ihn rot – über dieselbe Projektion wie
  jeden anderen Zustand. **Und es gibt einen Weg zurück**: `units.restore` holt aus dem
  «verkauft»-Topf, wenn eine **Retoure** kommt (die eine Ausnahme, die das Material-Journal
  als `src_disposition='sold'` längst kennt) – vorher trug eine zurückgenommene Instanz
  wieder eine Menge, aber **kein einziges Stück**.
  *Beides zusammen behob nebenbei einen dritten Befund, den der Harness zeigte:* eine Kante
  des Flusses meldete «4 Stk» und nannte nur 3 Nummern – die vierte war die verschrottete,
  deren Nummer es nicht mehr gab. Im gleichen Zug buchen Verkauf und Verbrauch ihre Nummern
  jetzt ebenfalls ins Journal (`ledger.post(units=…)`), wie das Verschrotten es schon tat.
  (3) **Die offene Entscheidung ist eine Zeile, kein Gateway** (#551): die Raute war ein
  eigenes Bauteil mit eigener Formsprache für etwas, das der Fluss an dieser Stelle ohnehin
  sagt. Übrig bleibt dieselbe Form wie bei jeder anderen Auflösung (Punkt · Satz · Hover) –
  nur eben noch offen und darum anklickbar.
  (4) **«Geplant – wird aktiv, sobald …» entfällt** (#552): dass ein Schritt noch nicht dran
  ist, sagen die Linie (sie führt nicht hierher) und die gesperrten Aktionen. Die Regel
  «nur der aktive Schritt lässt sich bedienen» bleibt unverändert (#542).
  (5) **Gerade Strichstärken – sonst passt die Ecke nie zur Geraden** (#550, gemessen statt
  vermutet): die Achse ist ein `div`, die Ecke ein SVG-Pfad. Der Browser **rastert** die
  Fläche eines div auf ganze Gerätepixel, einen Pfad zeichnet er analytisch. Bei
  **ungerader** Breite fällt beides auseinander – die Achse liegt mittig in einer Spur
  gerader Breite, ihr Kasten beginnt auf einer halben Pixelgrenze (bei 3 px: 748.5) und wird
  auf 749 gerundet, der Strich bleibt bei 748.5 und ragt eine halbe Pixelbreite heraus.
  Genau das sah aus, «als ob der Radius über die gerade Linie hinausgeht», und zwar
  systematisch an jeder Gabelung. Nachgewiesen durch Auslesen der gezeichneten Pixelspalten
  (Chromium, `deviceScaleFactor` 1): Achse 749·750·751, Ecke zusätzlich 748. Mit **gerader**
  Breite (`lineW = strong ? 4 : 2`) liegen Kasten und Strich exakt gleich – unabhängig von
  der Pixeldichte; ein Ausrichten auf halbe Pixel hätte auf Retina genau den Fehler erzeugt,
  den es auf einfachen Bildschirmen behebt.
  Wächter: `tests/rules/test_units.py: test_a_named_share_hands_over_its_own_pieces`
  (gegen die Bug-Form gegengeprüft) und `…_a_piece_changes_its_state_it_does_not_vanish`,
  `test_smoke.py: test_the_decision_stands_at_its_place_in_the_flow`,
  `test_frontend_mirrors.py: test_a_future_step_shows_what_is_planned` +
  `…_a_sub_order_is_a_regular_process_beside_the_axis` (gerade Strichstärken). Gegen echtes
  PostgreSQL 16 verifiziert (Harness `note553.py`, 10/10 – die gemeldete Kette Schritt für
  Schritt; alle 12 Harnesses und die Regel-Tabelle unverändert grün).

- **Über eine Fehlmenge entscheidet das System (Testnotizen #554–#556)**: Drei Notizen,
  ein Thema – der Prozess blieb stehen und fragte statt weiterzulaufen.
  (1) **Ein Auftrag, der selbst ausgesteuert hat, ist FERTIG** (#555, der gemeldete
  Steckenbleiber). Zwei parallele Abweichungen: die eine verschrottet ihr Stück, die andere
  bewegt es nur und gibt es zurück – der Hauptprozess kam trotzdem nicht weiter. Ursache
  war die **Abweichung mit dem Verschrotten**: sie hielt danach nichts mehr und meldete
  darum eine Fehlmenge über ihre volle Menge, wurde nie `completed`, und der Eltern wartete
  für immer auf sie (`waiting_for`). Der Unterschied ist nicht die Menge, sondern **warum**
  sie weg ist: hat ein anderer sie genommen, fehlt sie; hat dieser Auftrag sie durch seinen
  eigenen Schritt ausgesteuert, IST das seine Erledigung. Das Journal weiss es genau
  (`process._disposed_amounts` liest die terminalen Buchungen, die IHM zugeschrieben sind).
  **Zweiter Fehler im selben Vorgang:** eine Rückgabe verzehrte die **älteste** Abgabe
  derselben Instanz statt ihre eigene (`ledger.order_view.consume_departed`) – bei zwei
  parallelen Abweichungen frass die Rückgabe der einen die Abgabe der anderen; die Achse
  behauptete danach, das Stück liege noch beim falschen Abzweig, und die Kante meldete
  «3 Stk» mit nur zwei Nummern. Wer zurückgibt, steht in der Buchung.
  (2) **Gefragt wird niemand mehr** (#556, ausdrückliche Entscheidung des Nutzers). Die
  Unterdeckungs-Frage hatte nie zwei sinnvolle Antworten – sie hing nur davon ab, wann man
  sie stellt: *hält noch jemand die Menge* → **warten** (und der Auftrag ruht dabei ohnehin);
  *hält sie niemand mehr* → sie ist endgültig weg, **das Soll sinkt darauf**. Beides weiss
  das System besser als der Mensch, also entscheidet `recovery.auto_resolve` – aufgerufen
  aus `process.recompute_completion`, der einen Stelle, an der sich der gelesene Zustand
  ändert (nach jedem Schritt-Abschluss, und über deren Rekursion beim Verleiher, sobald ein
  Abzweig endet). **Ein Verlust ist nicht dasselbe wie ein offener Bedarf**
  (`recovery._lost_amounts`): gekürzt wird nur, was **da war** und weg ist – eine Menge, die
  nie da war, wird beschafft, nicht weggekürzt (sonst kürzte sich ein Auftrag, dessen
  Nachschub noch nicht angelegt ist, selbst auf den Lagerbestand). Entfallen sind damit:
  `shortfall_responses` am API-Rand, der 409 `shortfall_decision_required`, `_assert_answered`/
  `_answer_for`/`_apply_shortfall_answer`, der `ShortfallDialog`, die `DecisionLine` im Fluss
  und die Schere auf der Entwurfs-Rückgabelinie (#499 – die Linie bleibt, sie ist jetzt eine
  **Aussage** statt einer Antwort). *Bewusst zurückgestellt (Backlog): «Ersetzen»
  (`recovery.cover_shortfall` + `POST …/cover` existieren weiter, es fragt nur niemand mehr
  danach) und der **Verkauf** – eine bezahlte Position darf nicht stillschweigend schrumpfen,
  dafür ist die Gutschrift da; sie bleibt mit ihrer Fehlmenge stehen.*
  (3) **Keine Prognose auf der Rückgabe-Kante** (#554): die eigene Ansicht eines
  Unter-Auftrags zeigte dort sein **lebendes Material** – also eine Vorhersage, und dazu eine
  andere als die, die derselbe Abzweig im Eltern zeigt (dort werden die Buchungen gelesen).
  Jetzt lesen beide dieselbe Quelle (`OrderOrigin.returned_lots` ← `_flow_back`): solange
  nichts zurück ist, steht dort nichts.
  **Die Regel-Tabelle (ADR 008) trägt die Änderung** – sie hat sie prompt gemeldet: Zeile
  `regular-teil-verloren` kippt von «Fehlmenge, Pause, ein Mensch entscheidet» auf «das Soll
  ist gekürzt, der Auftrag läuft». Neu ist die Spalte **`soll`** (unverändert · gekürzt ·
  abgebrochen) – ohne sie sähe «keine Fehlmenge, keine Pause» genauso aus wie ein Auftrag,
  bei dem gar nichts passiert ist – und die Zeile `fixed-selbst-ausgesteuert` (#555).
  Wächter: `tests/rules/table.py` + `test_shortfall_rules.py`,
  `test_scenario_chain.py: station_6`, `test_smoke.py: test_the_shortfall_decides_itself`,
  `…_every_affected_order_follows_the_same_rule`, `…_the_flow_shows_what_happened_not_a_question`.
  Gegen echtes PostgreSQL 16 verifiziert (Harness `note555.py` – die gemeldete Abfolge
  Schritt für Schritt: A wird fertig, B gibt zurück, der Hauptauftrag kürzt sich selbst auf
  2 und die Datenerfassung wird aktiv; alle 13 Harnesses grün).

- **Die gekappte Rückführung – und der Lauf, der beim Speichern verschwand** (August 2026,
  Testnotizen #557–#563, Migration `101`): Ein echter Speicherfehler, eine neue Aussage
  über die Zukunft, und drei Kleinigkeiten.
  (1) **Der geladene JSONB-Wert darf nie verändert werden** (#560/#561/#562, `units._runs`).
  Gemeldet als «hier wird nicht die richtige Suffix bzw. kein Suffix angezeigt» – mal
  richtig, mal nicht, ohne erkennbares Muster. Die Ursache ist eine klassische Falle:
  `units.py` las die Läufe aus `instances.units` und **veränderte die geladenen dicts an
  Ort und Stelle**. SQLAlchemy vergleicht beim Flush den geladenen mit dem aktuellen Wert –
  ist beides **dasselbe Objekt**, sind sie gleich, die Spalte fällt aus dem `UPDATE`, und
  die Änderung ist weg. Ob sie ankam, hing damit daran, ob im selben Vorgang zufällig noch
  jemand die Spalte neu zuwies: genau die scheinbare Willkür. `_runs` gibt jetzt **Kopien**
  zurück – die Frage ist damit gegenstandslos statt an jeder Schreibstelle einzeln zu
  beantworten.
  (2) **Was ein Abzweig weiterreicht, hat den Eltern nie erreicht** (#559,
  `ledger.RETURNING`). `departed_of` zählte **jede** lebende Abgabe als Rückgabe – auch die
  an eine *weitere* Abweichung eine Ebene tiefer. Ein Abzweig, der 2 Stück übernahm, davon
  1 an seine eigene Abweichung weitergab (die es verschrottete) und 1 zurückgab, meldete
  darum «2 zurück». Gezählt wird jetzt nur, was tatsächlich nach oben ging
  (`kind in ("returned", "released")`) – eine Weitergabe nach unten ist keine Rückgabe.
  Und die Rückgabe trägt **ihre eigenen Nummern** (`Departed.units`), nicht die, die der
  Auftrag einmal übernommen hat: er gibt ja womöglich weniger zurück, als er bekam.
  (3) **Wessen Anteil das ist, weiss die Auswahl – die Buchung soll es nicht raten**
  (`record_link(..., src_holder=…)`). Sie riet nach Topfgrösse: nahm eine Abweichung ihrem
  Abzweig ein Stück weg und hielt der Hauptauftrag gerade gleich viel, wurde die Übernahme
  **ihm** zugeschrieben, und dieselbe Nummer stand auf seiner Achse zweimal. Der Halter
  steht in `orders.pick_sources` und wird **vor** `enforce_pick` gelesen (das verbraucht die
  Angabe). Geraten wird nur noch, wo es nichts zu wissen gibt (FIFO ab freiem Lager).
  (4) **«Die Rückführung kappen» – EINE Aussage, die Kaskade folgt von selbst** (#563,
  `orders.returns_nothing`). Nimmt ein Unter-Auftrag ALLE Stücke seines Verleihers, kann
  das System nicht entscheiden, ob sie zurückkommen: **solange der Abzweig läuft, könnte
  es sein** – darum wartet der Verleiher (Regel-Zeile `regular-alles-verliehen`). Sagt der
  Mensch beim Anlegen, dass nichts zurückkommt, ist die Menge endgültig weg, und der
  Verleiher endet an dieser Stelle: **abgebrochen, fortgeführt im Abzweig**. Das ist keine
  neue Entscheidungslogik, sondern **dieselbe** automatische Auflösung (#556) mit einem
  Halter weniger: ein gekappter Auftrag deckt niemanden (`supply.covering_sub_orders`
  überspringt ihn, folgt aber SEINEN Abzweigen), gibt beim Abschluss nichts zurück
  (`subject.give_back`) und zeigt keinen Rückweg (`orders._return_target`). **Die Kaskade
  über beliebig viele Stufen braucht darum keine zweite Regel**: wird ein Verleiher dadurch
  selbst abgebrochen, deckt auch er niemanden mehr – `recovery.auto_resolve` ruft sich über
  `subject.lender_of` eine Ebene höher auf (zyklensicher). Genau der vom Nutzer genannte
  Fall: «im Unterauftrag wäre noch geplant gewesen, dass sie zurückkommen, aber im
  Unter-Unter-Auftrag wurden alle Instanzen genommen und die Rückführung gekappt → dann wird
  der Hauptauftrag und der erste Unterauftrag gekappt». Im Entwurf ist es die **Schere auf
  der Rückgabe-Linie** (#499): gekappt = **keine Linie** – kein zweiter Strichstil, wie
  #422/#429 es verlangen.
  (5) **Genommen wird von unten** (#558): `units._assign` gab die **höchsten** Nummern zuerst
  – ein Unterauftrag über die Anteile `-3`/`-4` bekam `-4`, während sonst überall von unten
  gezählt wird. Jetzt niedrigste zuerst in allen drei Rängen (genannter Anteil ≻ frei ≻
  fremd) – das Zurückgeben nimmt weiterhin die höchsten («was zuletzt kam, geht zuerst»),
  sodass der behaltene Satz von unten zusammenhängend bleibt.
  (6) **Die Linie führt IMMER heran** (#557): der Konnektor vom Startknoten zum Modul hing
  an `!adding` und fehlte damit genau dann, wenn man einen Schritt anlegt – der Editor stand
  ohne Anschluss unter dem grünen Punkt. Dieselbe Bedingung wie Start- und Endknoten.
  **Die Regel-Tabelle (ADR 008) trägt den neuen Fall als ZEILE, nicht als Sonderfall im
  Code**: `regular-rueckfuehrung-gekappt` (alles verliehen **und** gekappt → abgebrochen –
  der einzige Unterschied zu `regular-alles-verliehen`, und er kippt «warten» in «Ende»),
  `regular-teil-gekappt` (**gekappt heisst nicht abgebrochen**: bleiben 3 von 4, sinkt nur
  das Soll – der Abbruch hängt daran, dass NICHTS mehr bleibt) und `regular-kaskade-gekappt`
  (geprüft wird der OBERSTE einer dreistufigen Kette). Gegen die Bug-Form gegengeprüft: ohne
  `cut` meldet die Zeile wieder eine Fehlmenge von 4.
  **Beim Nachmessen ein Folgefehler gefunden – genau die Klasse, die #492 verbietet:** das
  Kappen war nur an EINER der beiden Oberflächen angekommen. Die eigene Ansicht des Abzweigs
  zeigte korrekt keinen Rückweg (`_return_target` prüfte die Flagge), der **Teaser im
  Eltern-Auftrag** zeichnete aber weiter eine Rückgabe-Linie – weil er die Frage «kommt etwas
  zurück?» ein zweites Mal selbst rechnete, aus dem Material. Jetzt lesen beide dieselbe
  Ableitung (`orders.returns_material`, um die Flagge erweitert und mit durchgereichter
  Materialliste, also ohne zweite Abfrage); die Sonderprüfung in `_return_target` ist damit
  entfallen. Wächter erweitert: der Abzweig muss die Ableitung **aufrufen**, nicht nachbauen.
  **Die vom Nutzer erbetenen «Fälle, die ich nicht auf dem Schirm habe»** sind gemessen
  (Harness `note563b.py` 21/21): Teil-Kappung kürzt statt abzubrechen · der gekappte Abzweig
  behält sein Stück und gibt beim Abschluss nichts zurück (der Abbruch wird nicht widerrufen)
  · bei zwei Verleihern trifft es nur den eigenen · eine **dreistufige** Kette bricht auf
  allen Ebenen ab, jede mit Zeiger auf ihre direkte Fortführung · `covering_sub_orders` ist
  danach leer (niemand wartet auf etwas, das nie eintrifft) · und beide Oberflächen sagen
  dasselbe.
  Wächter: `tests/rules/table.py` + `test_shortfall_rules.py`, `tests/rules/test_units.py`,
  `test_frontend_mirrors.py: test_the_draft_is_framed_like_the_order_it_will_become`.
  Gegen echtes PostgreSQL 16 verifiziert (Harnesses `note559.py` 11/11, `note563.py` 13/13
  inkl. der Kaskade; Migration 101 von null · idempotent · downgrade · **über das
  Lifespan-Netz** 16/16; alle 14 Harnesses und die Regel-Tabelle grün).

- **Testnotizen-Runde 40 (die Nummern überleben den Abschluss, Notizen #564–#570)**: Vier
  der sieben Notizen («hier fehlt die 1./2. Instanz», «die Instanz hat keinen Suffix»,
  «schon wieder Instanzen zerschossen») waren **ein** Fehler mit einer Wurzel.
  (1) **Eine abgeleitete Antwort kann die Vergangenheit nicht tragen – auch nicht für
  gehaltenes Material** (#567–#570). Seit #543/#544 stehen die Stück-Nummern in der
  **Buchung**; das galt aber nur für terminale und abgegebene Zeilen. Eine **gehaltene**
  Zeile liess sie offen, und die Oberfläche leitete sie aus der **heutigen Karte** ab
  (`units.owned_by`). Das hielt genau so lange, wie der Auftrag lief: beim Abschluss löst er
  seine Reservierung, die Karte kennt ihn nicht mehr – und seine fertige Achse zeigte «1 Stk
  × 100000651» **ohne eine einzige Nummer**. Beim teil-zurückgegebenen Auftrag war es
  schlimmer: eine **halbe** Liste, die vollständig aussieht («4 Stk × …-2, -3, -4»). Jetzt
  führt `ledger.order_view` den Nummernstand je Topf mit (was hereinkam minus was hinausging),
  und die zwei Buchungen, denen die Nummern fehlten, nennen sie: die **Entstehung**
  (`serialization` – der Moment, in dem es die Nummern zum ersten Mal gibt) und die
  **Freigabe** (`process.release_instances` + der Abschluss-Loop, dort **vor** dem Lösen des
  Anspruchs festgehalten – dieselbe Lehre wie bei `give_back`). Für Altbestand ohne
  aufgezeichnete Nummern bleibt der Rückfall auf die Karte, aber nur **ganz oder gar nicht**
  (`units.covers`): eine halbe Liste ist schlimmer als keine.
  (2) **Der Prozessbaum ist entfernt** (#565, revidiert #493): die Pille «1 kamen aus Auftrag
  …650» vor dem Startknoten. An einem Unter-Auftrag sagt die linke Spur längst «hervorgegangen
  aus …» und die rechte «gibt zurück an …» – dieselbe Beziehung ein zweites Mal, in einer
  anderen Sprache. `material_trace`/`MaterialOrder`/`material_from`/`material_to` und die
  `TraceChip`/`TraceRow` sind ersatzlos weg; der Wächter steht als **Negativ**, damit die
  Doppelung nicht nachwächst.
  (3) **Die Schere erklärt sich nicht mehr im Hover** (#564): was sie bewirkt, steht als
  Klartext im Knoten darunter («Gibt zurück an» ↔ «Keine Rückgabe – wird abgebrochen»), und
  ob die Linie da ist, sieht man. Der Name bleibt als `aria-label` – benannt für
  Screenreader, ohne Blase.
  Wächter: `tests/rules/test_units.py: test_a_finished_order_still_names_its_pieces` (gegen
  die Bug-Form gegengeprüft: ohne die Nummern in der Freigabe-Buchung meldet er «1.0 Stk nennt
  0 Nummern»), `test_frontend_mirrors.py: test_the_material_trace_is_gone`. Gegen echtes
  PostgreSQL 16 verifiziert (Harness `note567.py` 9/9 – die gemeldete Kette Schritt für
  Schritt, inkl. Altbestands-Rückfall; alle 16 Harnesses und die Regel-Tabelle grün).
  - **OFFEN und bewusst nicht in dieser Runde: #566 – «Ziel erreicht ⇒ grün Freigegeben».**
    Gemessen: hält ein gekappter Abzweig die **ganze** Instanz, wird sie beim Abschluss
    korrekt `passed`/`in_stock`. Hält er **ein Stück einer Charge**, bleibt die Instanz
    `pending`/`in_process` – und das ist bei EINEM Zustandsfeld auch richtig: die anderen
    drei Stücke sind noch in laufenden Aufträgen. Die Notiz verlangt damit den Schritt, der
    in diesem Dokument seit den Stück-Nummern als «nächster» vorgemerkt ist: **Zustand je
    Stück** statt je Instanz (`quality`/`disposition` als Projektion der Läufe). Der Preis
    ist nicht die Anzeige, sondern `inventory.in_stock_clauses()` – die SQL-Bedingung, aus
    der FIFO, Bestandszählung und Verfügbarkeit lesen; sie kann eine teil-freigegebene Charge
    aus den Skalaren nicht mehr beantworten und bräuchte eine mitgeführte Menge (dasselbe
    Denormalisierungs-Muster wie `reserved_for_order_id`/`location_*`). Das ist eine eigene
    Runde mit eigener Messung wert – ein Halbschritt (nur im Journal freigeben) würde die
    Instanz-Ansicht und die Achse widersprüchlich machen, also genau das, was #492 verbietet.

- **Der Zustand gehört zur MENGE – «Ziel erreicht ⇒ freigegeben» (Notizen #571/#572)**:
  Die in Runde 40 offen gelassene Frage ist umgesetzt, und sie hat das System **einfacher**
  gemacht statt komplizierter – zwei Regeln sind zu einer geworden.
  (1) **Freigegeben wird, was ein Auftrag nach der Rückgabe noch HÄLT** (#572). Vorher gab
  `release_instances` erst die ganze Instanz frei, und ein zweiter Wächter
  (`_worked_on_by_a_running_order`) nahm nachträglich zurück, was ein anderer laufender
  Auftrag noch bearbeitete. Weil dieser Wächter die **ganze Instanz** ausschloss, blieb ein
  fertiges Stück einer geteilten Charge für immer «Im Prozess» – der gemeldete Fall. Jetzt
  entscheidet die **Reihenfolge**: erst `return_borrowed`, dann freigeben, was übrig ist.
  Daraus fällt alles Frühere von selbst heraus – eine gewöhnliche Abweichung hat eben
  zurückgegeben und gibt nichts frei (#332), ein **gekappter** Abzweig behält sein Stück und
  gibt es frei, der Erzeuger gibt am Ende alles frei (#262). Der Wächter ist **ersatzlos
  entfallen**.
  (2) **Der Zustand steht am Stück, der Instanz-Skalar ist die Projektion**
  (`units.mark_released`/`all_released`, Marker `s` im Lauf – kein Schema-Wechsel, JSONB).
  Eine Charge kann geteilter Meinung sein: ein Stück durch den Prozess, drei in Arbeit –
  beides wahr, nur nicht über dieselbe Menge. `instances.quality`/`disposition` wechseln
  **konservativ** erst, wenn alle lebenden Stücke frei sind; damit liest
  `inventory.in_stock_clauses` (FIFO · Bestand · Verfügbarkeit) unverändert die Skalare und
  wird **nicht ungenauer als vorher** – eine teil-freigegebene Charge ist wie bisher noch
  nicht entnehmbar, sie sagt es jetzt bloss ehrlich. *(Der verbleibende Schritt wäre, die
  Verfügbarkeit ebenfalls je Stück zu führen – eine mitgeführte Menge neben den Skalaren,
  dasselbe Denormalisierungs-Muster wie `reserved_quantity`. Erst dann ist ein einzelnes
  Stück einer geteilten Charge auch FIFO-entnehmbar.)*
  (3) **«Inaktiv» sind ZWEI verschiedene Dinge** (#571): verworfen (nichts folgt) und
  **abgebrochen, fortgeführt in …** (`abort_into_id`, seit Migration 086). `_fill_step_
  sub_orders` schloss beide über denselben Status aus – der abgebrochene Abzweig verlor
  damit seine Position am Schritt, blieb aber in der Auftrags-Liste und rutschte im Fluss
  nach **ganz vorne**, vor einen längst erledigten Schritt. Genau der gemeldete Sprung. Ein
  abgebrochener Vorgang ist Teil der Geschichte seines Schritts; ein verworfener nicht.
  Wächter: `test_smoke.py: test_an_order_releases_what_it_still_holds` (prüft die
  **Reihenfolge** – `return_borrowed` vor `release_instances`), `tests/rules/test_units.py:
  test_an_order_releases_the_pieces_it_still_holds` (Verhalten: zurückgegeben ⇒ nichts frei ·
  gekappt ⇒ sein Stück frei · Skalar bleibt konservativ). Gegen echtes PostgreSQL 16
  verifiziert (`note571.py` 14/14 – die gemeldete Kette samt #332/#262-Gegenprobe; alle 16
  Harnesses und die Regel-Tabelle (34) grün).

- **Testnotizen-Runde 42 (freigegeben heisst frei, Notizen #573–#578)**: Vier der sechs
  Notizen hatten **eine** Wurzel – und die stammte aus der Runde davor.
  (1) **Ein freigegebenes Stück gehört niemandem mehr** (#573/#577). Der «unbeanspruchte
  Rest gehört dem Erzeuger» (`inventory.rest_owner`) gilt für das, was noch im Prozess ist.
  Als die Freigabe je Stück kam, fielen fertige Stücke – die ja keinen Halter mehr tragen –
  unter dieselbe Regel und wurden dem Erzeuger **erneut zugeschlagen**. Zwei sichtbare
  Folgen: das Instanz-Detail zeigte sie als «Reserviert» (gelb) statt «Freigegeben» (grün),
  und auf den Kanten des Erzeugers tauchten längst fertige Nummern wieder auf und
  verdrängten die, die er wirklich hält («…-1 war schon lange freigegeben, …-3 nicht mehr
  auffindbar»). `units.owned_by`/`rows` nehmen ein freigegebenes Stück jetzt aus dem Rest.
  (2) **Der Hover sagt dasselbe wie die Pille** (#574): `rows_for` las den Instanz-Skalar,
  und der bleibt bei einer teil-freigegebenen Charge bewusst «Im Prozess» – die Kante zeigte
  grün, ihre Hover-Karte gelb.
  (3) **Parallel ist nur, was gleichzeitig läuft – auch beim Abbruch** (#575): ein
  **abgebrochener** Auftrag trägt kein `completed_at` (er ist nie fertig geworden), ist aber
  sehr wohl zu Ende. `_waves` schaute nur auf `completed_at`, hielt ihn darum für laufend und
  zeichnete einen später entstandenen Abzweig **neben** ihn – obwohl der ihn abgelöst hatte.
  Jetzt endet ein Abzweig «abgeschlossen ODER abgebrochen».
  (4) **Ein abgebrochener Auftrag gibt nichts zurück** (#578): was er hielt, ist ausgesteuert
  oder im Auftrag, der ihn fortführt. Die Kappungs-Kaskade selbst lief korrekt (gemessen) –
  falsch war nur die Rückgabe-Linie, die einen Weg behauptete, den es nicht mehr gibt.
  (5) **Der Bypass steht mittig zwischen den beiden waagrechten Linien** (#576): die
  Abzweigung verlässt die Achse bei y = 0, die Einmündung trifft sie `BEND` über dem unteren
  Rand – die Zeilenmitte lag also einen halben Bogen zu tief. Ein `BEND`-hoher Abschnitt
  unter dem Material rückt es um genau diesen Betrag hoch (nur mit Einmündung: ohne sie gibt
  es keine zweite Linie).
  Wächter: `tests/rules/test_units.py: test_a_released_piece_belongs_to_nobody`,
  `test_smoke.py: test_a_finished_branch_is_not_drawn_as_parallel_and_shows_no_return`
  (gegengeprüft: ohne den `ended`-Fix landen beide Abzweige wieder in EINER Teilung). Gegen
  echtes PostgreSQL 16 verifiziert (`note573.py` 9/9; alle 17 Harnesses und die Regel-Tabelle
  (35) grün).

- **Testnotizen-Runde 43 (nicht an der Reihe heisst nicht bedienbar, Notizen #579–#585)**:
  (1) **Die Regel gehört ins Backend, nicht in jedes Panel** (#581/#582). «Ein Prozessschritt,
  der nicht dran ist, lässt sich nicht ausfüllen» war mehrfach gefordert und stand als
  `stepState !== 'active'` in **vier** Panels einzeln – Beschaffung, Verkauf und Dokument
  hatten nie eines. Vor allem aber blieb bei einem **abgebrochenen** Auftrag ein Schritt
  «aktiv», also griff die Sperre dort gar nicht: das Modul sah zurückgetreten aus, liess sich
  aber vollständig ausfüllen und nannte sogar Instanzen, die es längst nicht mehr gibt. Jetzt
  eine Regel an der Quelle (`process.build_order_steps`): **läuft der Auftrag nicht
  (Entwurf/abgebrochen/abgeschlossen), ist NICHTS an der Reihe** – jeder Schritt bleibt
  `locked` und damit überall nur lesbar. Die **zu bearbeitenden Instanzen** erscheinen erst,
  wenn das Modul aktiv ist (bis dahin kann sich alles ändern); die **Konfiguration** bleibt
  jederzeit sichtbar (#487).
  (2) **Gekappt heisst gar keine Linie** (#579): über dem Rückgabe-Knoten des Entwurfs wurde
  ein 18-px-Stück **unbedingt** gezeichnet und blieb als Strich ins Nichts stehen.
  (3) **Stark ist die Linie nur, wo etwas darüber geht** (#580/#584): zweigt an einer Stelle
  ALLES ab, bleibt auf dem Bypass nichts – eine volle Linie behauptete das Gegenteil. Die
  Abzweigung daneben bleibt stark: dort ist etwas gegangen.
  (4) **#583 gemessen statt geraten**: nach zwei Fehlversuchen die Geometrie in Chromium
  nachgebaut (`Row`/`Axis`/`Elbow` mit den echten Konstanten) und die Pixel ausgelesen –
  Abzweigung bei y = 0, Einmündung bei y = H − `BEND`, Pille exakt dazwischen: **0,0 px**.
  Mit vorhandener Einmündung stimmt es also; der gemeldete Restfall liess sich nicht
  reproduzieren. *Lehre: bei einer Optik-Frage, die zweimal zurückkommt, ist der Browser das
  billigere Werkzeug als das dritte Nachdenken.*
  (5) **#585 nur halb**: der Anzeige-Teil fällt unter die Linien-Regeln; der **Nummern**-Teil
  liess sich nicht reproduzieren (Harness `note585.py`: ein fremder Auftrag wird freigegeben
  und greift ein Stück – die Anzeige des alten Auftrags bleibt unverändert, auch bei
  Altbestand ohne Buchungs-Nummern).
  Wächter: `test_smoke.py`-Suite unverändert grün; gegen echtes PostgreSQL 16 verifiziert
  (`note573.py` 12/12 inkl. der neuen Schritt-Gate-Prüfung, alle 18 Harnesses, Regel-Tabelle
  (35) grün).
- **Die «Halter»-Mechanik rät nur noch dort, wo es etwas zu wissen gibt** (Notiz #585,
  belegt am Systemprotokoll): `inventory.rest_owner` schrieb den **freien, freigegebenen**
  Anteil einer Charge dem **abgebrochenen** Erzeuger zu («Auftrag 100000669»), während das
  Journal ihn als «freier Bestand» führte – zwei Antworten auf dieselbe Frage, und die
  geratene gewann. Jetzt nennt sie nur noch einen Auftrag, der **wirklich läuft**
  (`status='released'`), und ohne Session rät sie gar nicht (`db=None` → frei). Damit ist
  die letzte Stelle entschärft, an der die Zuordnung geraten statt gelesen wurde; die drei
  Leser (`units.rows`, `units.owned_by`, `shares`) reichen die Session durch.
  *Vollständig ersatzlos wird sie erst, wenn der Erzeuger seine Stücke bei der Entstehung
  **beansprucht** – dann ist die Anspruchs-Map die einzige Wahrheit. Das ist derselbe
  Schritt wie «wer hält wie viel → EINE Antwort».*
  Dazu ein Widerspruch im Systemprotokoll behoben: «0 von 2 Schritten erledigt · **alle
  Schritte durch**». Er entstand mit dem Gate aus #581 – ein nicht laufender Auftrag hat
  keinen aktiven Schritt mehr, und «kein aktiver Schritt» hiess dort «alles durch». Jetzt
  sagt es, was zutrifft: «nichts an der Reihe (Auftrag «inactive»)».

- **Testnotizen-Runde 44 (die Linie sagt, was passiert ist, Notizen #586/#589/#590)**: Drei
  Befunde aus derselben Kette (Auftrag → Abweichung A → Abweichung B → Abweichung C, deren
  Rückführung gekappt ist) – und alle drei haben **eine** Wurzel: eine Aussage über den
  **Fortschritt der Achse** wurde als Aussage über **geflossenes Material** gelesen.
  (1) **Läuft er noch → der Plan; ist er zu Ende → die Tatsache** (#590, `returns_material`).
  B reicht sein einziges Stück an C weiter und wird dadurch gegenstandslos – abgebrochen.
  Im Eltern-Auftrag A stand danach trotzdem «1 Stk kam zurück» nach einem Modul, das nie
  ausgeführt wurde, samt voller schwarzer Rückgabe-Linie. Zwei Ursachen, beide dieselbe
  Klasse: `_flow_back` fiel bei fehlender Rückgabe-**Buchung** auf die alte Ableitung
  «Übernommenes minus endgültig Verlorenes» zurück – eine Weitergabe nach unten ist nicht
  terminal, also las sie sich als Rückgabe nach oben; und `returns_material` fragte immer
  den Plan. Jetzt gilt: hat der Auftrag ein Journal, ist «keine Rückgabe-Buchung» **die
  Antwort** (die Ableitung bleibt der Lesepfad für Altbestand **ohne** Buchungen), und ein
  Auftrag, der **zu Ende** ist (abgeschlossen ODER abgebrochen), gibt zurück, was er
  zurückGEGEBEN hat. Damit ist der Sonderfall «abgebrochen → nichts» (#578) **eine Regel
  weniger**: er stand in `_return_target` und galt darum nur für die eigene Ansicht des
  Abzweigs – im Eltern zeichnete derselbe Vorgang weiter eine Linie (exakt die
  #492-Klasse). Er wohnt jetzt in `returns_material` und gilt für beide Oberflächen.
  (2) **Erreicht ≠ geflossen** (#589/#586, `FlowEdge.flowed` = `reached and bool(lots)`).
  Zweigt an einer Stelle ALLES ab, ist der Weg darunter erreicht **und trotzdem leer** – eine
  volle Linie behauptete dort, es sei etwas durchgegangen. Der Bypass las die Regel längst
  aus seinem Material (`lots.length > 0` im Frontend); jetzt gilt sie für die **ganze** Achse
  und steht **im Backend** statt zweimal in der Oberfläche. Die Rückgabe-Linie ist stark,
  wenn wirklich etwas zurück **ist** (`flow_back`), statt wenn die Achse weiterläuft – dünn
  heisst dann genau das Richtige: geplant, aber nichts gekommen.
  (3) **Der Anschluss MITTEN auf der Achse ist ein T, der an ihrem Ende eine Ecke** (#586).
  Fork und Merge liefen ein Stück **entlang** der Achse (erst `BEND` hinunter, dann hinaus);
  dieses Stück ist Achse und Ecke zugleich – trug es eine andere Strichstärke als das
  Achsenstück daneben, blieb dort ein schwarzer Stummel auf einer Haarlinie stehen
  (**gemessen: 7.6 px**). Ein T berührt die Achse in **einem Punkt**; die Frage ist damit
  gegenstandslos statt an jeder Stelle neu zu beantworten. Nebeneffekt: Fork und Merge sind
  echte **Spiegelbilder** (waagrecht genau auf ihrem Anschlusspunkt), also steht das Material
  **ohne Korrekturglied** mittig – der `BEND`-Ausgleich aus #576 ist entfallen, und die
  Materialzeile zwischen zwei aufeinanderfolgenden Unter-Aufträgen sitzt nicht mehr um
  `BEND`/2 daneben (gemessen: vorher 6 px Versatz, jetzt 0.00 px). Herkunft und Rückweg
  behalten ihre zwei Bögen: sie treffen die Achse dort, wo sie **beginnt bzw. endet**, und
  das ist eine Ecke des Weges, kein T (#430/#431).
  *Die Geometrie ist in Chromium **gemessen**, nicht überlegt (dieselbe Lehre wie #583/#550):
  Pfad abtasten, waagrechte Linien und Achsen-Stummel in Seiten-Koordinaten auslesen.*
  Wächter: `tests/rules/test_flow_lines.py` (Wirkung über die echten Dienst-Pfade gegen
  echtes PostgreSQL 16 – die gemeldete Kette Schritt für Schritt, **gegen die Bug-Form
  gegengeprüft**: sie meldet die Phantom-Rückgabe und die volle Linie auf der leeren Kante)
  + die Spiegel-Wächter in `test_frontend_mirrors.py`/`test_smoke.py`.
  *Offen (Regel-Notizen, warten auf die Entscheidung des Nutzers, ADR-008-Arbeitsweise):*
  **#587** (ein Beschaffungs-Modul fragt beim Erreichen automatisch an – verliert der Auftrag
  danach alle Instanzen, bleibt die Bestellung aktiv: braucht ein «storniert» am Beleg) und
  **#588** (ein Modul soll die Instanzen referenzieren, die von oben hereinkommen – und was
  mit bereits erfassten Daten geschieht, wenn ihm während der Arbeit Instanzen entzogen
  werden). Beide sind **dieselbe** Frage und gehören als Zeile in die Regel-Tabelle.

- **Ein Beleg gilt für die Menge, für die er ausgestellt wurde (Testnotizen #587/#588)**:
  Ein Beschaffungs-Modul fragt beim Erreichen automatisch an. Wurden dem Auftrag danach
  seine Instanzen entzogen (Abweichung) und er dadurch abgebrochen, blieb die Bestellung
  «Angefragt» stehen – der **Lieferant** sah eine offene Anfrage für etwas, das es nicht
  mehr gibt. Dieselbe Frage stellte #588 allgemein: was geschieht mit der Arbeit eines
  Moduls, wenn sich seine Grundlage unter ihm ändert?
  **Die Regel hat zwei Enden und ist EINE:**
      Die Menge sinkt   → der Beleg fällt auf seine **erste Stufe** zurück («Angefragt»),
                          und die Zahlen, die die Vereinbarung ausdrücken, sind geräumt.
                          Eine Offerte über 3 Stück ist keine über 2.
      Die Menge ist weg → er fällt auf seine **letzte Stufe**: **storniert**.
  **Die Stufen stehen in der Registry** (`domain/event_types.py`: `reset`/`reset_fields`/
  `voided`), nicht als if/else im Code – und damit gilt die Regel **für alle Module**: wer
  Stufen deklariert, bekommt sie geschenkt (heute Beschaffung + Verkauf). Wer keine hat, ist
  **nicht ausgenommen, sondern hat nichts zurückzunehmen**: Bewegung, Ressource und
  Aussondern schreiben ihre Zeile erst, wenn die Handlung geschehen ist – sie ist damit
  Vergangenheit. Aus demselben Grund bleibt ein **erledigter** Beleg unangetastet:
  eingetroffene Ware ist eingetroffen (ADR 007).
  **Vereinheitlicht statt verzweigt** (die Umsetzungsfrage des Nutzers): «Menge reduzieren»
  und «alles entzogen» sind derselbe Vorgang – `rebase.rebase_documents(db, order)` hat
  **keinen Modus-Parameter**, sondern liest am Auftrag ab, welches Ende gilt
  (`_stage_of`: läuft er → `reset`, sonst → `voided`). Zwei Aufrufstellen, beide «die
  Grundlage hat sich geändert»: `recovery.confirm_quantity` (das Soll sinkt) und
  `deactivation.cancel_order_effects` (der Auftrag endet – der Abbruch-Zweig läuft ohnehin
  dort hindurch). **Selbstheilend**: die Funktion vergleicht die Menge des Belegs mit dem
  heutigen Soll und tut nichts, wenn beides stimmt – ein verpasster Aufruf korrigiert sich
  beim nächsten. Das **Nachziehen der Menge ist der eigentliche «Rebase»**: ohne es stünde
  der Beleg beim nächsten Durchlauf wieder auf fremder Grundlage.
  **Kein neues Wort:** «Storniert» (`cancelled`) trägt der Verkauf längst, ebenso Sendung
  und Warenkorb – die Beschaffung bekommt es dazu. Es ist **nicht** dasselbe wie
  «Abgelehnt» (`rejected`): abgelehnt heisst, der Besteller sagt zu einer Offerte nein (eine
  Entscheidung); storniert heisst, der Vorgang hat seinen Gegenstand verloren. Der
  Beschaffungs-Ablauf zeigt bei «Storniert» den Weg, der **tatsächlich** gegangen wurde
  (aus dem Verlauf) – anders als «Abgelehnt», das nur aus «Offeriert» erreichbar ist. Ein
  Mensch kann `cancelled` nicht setzen (nicht in `ALLOWED_STATUS`): es ist eine Folge, keine
  Aktion. **Kein Schema-Wechsel** (die Spalte ist ein `VARCHAR`), also keine Migration.
  **Die Datenerfassung braucht nichts davon** (#588, zweite Hälfte): ihr Prüfumfang wird
  ohnehin aus den **aktiven Instanzen** abgeleitet (`inspection.inspected_quantity`, #72/
  #399) – sie passt sich also von selbst an, und bereits erfasste Proben bleiben **Tatsachen
  über die Stücke, an denen sie erhoben wurden**. *Bewusst NICHT gebaut: das Anlegen einer
  Abweichung sperren, solange jemand in einem Modul Daten erfasst (vom Nutzer selbst als
  «schön, aber komplex» erwogen). Eine Abweichung ist genau das, was man anlegt, wenn die
  Realität abweicht; sie zu sperren, während ein Formular offen ist, blockiert die einzige
  Handlung, die die Lage verlangt – und das System entscheidet sonst nirgends über Sperren,
  sondern über die Auswahl.*
  Wächter: `tests/rules/test_document_basis.py` – eine Tabelle im Stil von ADR 008 (Lage →
  erwartete Stufe + Menge + Vereinbarung, mit Begründung im Fehlertext), über die echten
  Dienst-Pfade gegen echtes PostgreSQL 16 und **gegen die Bug-Form gegengeprüft**.

- **Bis zur Zusage entscheidet das System, ab der Zusage der Mensch (Testnotizen #587/#588,
  Entscheid des Nutzers)**: Die Beleg-Regel bekommt ihre **Schwelle**. `EventType.binding`
  nennt die Stufen, ab denen eine **zweite Partei** gebunden ist – bei der Beschaffung
  «Bestellt»: die Ware ist in aller Regel unterwegs, und man widerruft sie nicht einseitig
  (bei «Offeriert» greift die Automatik weiter). Das System fasst einen solchen Beleg nicht
  an, sondern **meldet** die Abweichung; erst die Bestätigung des Menschen löst dieselbe
  Änderung aus. Damit bleibt die Ausnahme abbildbar, die es in der Realität gibt: man ruft
  den Lieferanten an.
  **Die Klärung ist abgeleitet, kein Merker** (`rebase.clarifications`): «Beleg-Menge ≠ Soll
  UND der Beleg ist bindend». Sie verschwindet in dem Moment, in dem jemand handelt – ein
  gespeicherter Marker könnte hängen bleiben. Sichtbar am Beschaffungs-Modul
  (`PurchaseEmbed.clarify_needed`, «Bestellt 3 Stk · gebraucht 2 Stk – mit Lieferant
  klären») mit **einer** Antwort: «Lieferant hat zugestimmt» (`POST …/purchase/clarify`,
  Personal – der Anruf ist eine interne Handlung). *«Bleibt wie bestellt» ist bewusst KEINE
  Option: eine Überlieferung ist ein Fall, den man klärt, kein Zustand zum Wegklicken.*
  **Kein zweiter Weg:** `apply_clarified` benutzt denselben `_apply` wie die Automatik – der
  Unterschied zwischen «das System darf» und «der Mensch entscheidet» ist genau EINE
  Bedingung im Automatik-Pfad, nicht zwei Implementierungen. Beide fragen dieselbe
  `_off_basis`. *Die **Lieferanten-Rücksendung** (Beleg im Kredit-Modus, Spiegelbild der
  Kunden-Retoure) bleibt wie bisher eine bewusste Lücke – ab «Geliefert» geht zurück nur,
  was man zurückSCHICKT.*
  Wächter: `tests/rules/test_document_basis.py` (Schwelle greift · Klärung wird gemeldet ·
  Bestätigung löst Reset bzw. Storno aus – gegen echtes PostgreSQL 16).

- **Testnotizen-Runde 45 (#591–#593)**:
  (1) **Runde Ecken überall – auch am Anschluss an die Achse** (#591): Das T aus #586 hatte
  zwar keinen Stummel mehr, war aber die einzige harte 90°-Ecke im ganzen Bild. Die Lösung
  ist keine Formfrage, sondern eine **Zuordnung**: der Anschluss-Bogen liegt ~8 px *entlang*
  der Achse, also **gehört er der Achse** – der Pfad wird an genau diesem Bogen geteilt
  (`roundedPath(…, splitAt)`) und in zwei Stärken gezeichnet; der Bogen nimmt die **stärkere**
  der beiden Linien, damit ein dünner Weg nie eine starke Achse zerschneidet. Fork und Merge
  sind dabei echte **Spiegelbilder** (beide Waagrechten `BEND` innerhalb der Zeile), das
  Material steht also weiterhin ohne Korrekturglied mittig. In Chromium gemessen: Versatz
  0.00 px an allen drei Stellen; im kritischen Fall (nichts kam zurück, Bypass trägt Material)
  ist der Bogen 4 px schwarz und der Rückweg 2 px grau.
  (2) **Der Lieferant sieht denselben Prozess wie das Personal** (#592): Er bekam ein flaches
  Formular – zwei Bildsprachen für dieselbe Sache, und er sah nicht, was vor und nach seiner
  Bestellung passiert. Jetzt dasselbe Diagramm, dieselben Modul-Karten. **Die Einschränkungen
  sind inhaltlich, nicht gestalterisch:** der **Verkaufs-Embed** (Kunde, Betrag, Marge) geht
  für Nicht-Personal gar nicht erst mit (Backend, `_attach_step_embed` – ein Filter in der
  Oberfläche wäre eine Bitte, keine Grenze); **bedienen** darf er nur seinen eigenen Schritt
  (EINE Bedingung in `StepPanel`, die übrigen Module bleiben als Karte sichtbar, klappen aber
  nichts auf); **Verlauf und Systemprotokoll** bleiben beim Personal. Die Sonder-Karte
  «Lieferung an» ist entfallen – die Lieferadresse steht im Beschaffungs-Modul, für beide
  Rollen an derselben Stelle.
  (3) **Jedes Modul kann mehrere Artikel** (#593, geprüft statt behauptet): Beschaffung und
  Verkauf tragen **einen Beleg je Position** unter EINEM Schritt (bei der Beschaffung
  schreitet jede Bestellung eigenständig fort – eigener Lieferant, eigene Lieferzeit; beim
  Verkauf ist es ein Vorgang mit einem Beleg je Position). Bewegung, Aussondern und
  Datenerfassung arbeiten auf den **Instanzen** und fragen gar nicht nach dem Artikel; wer
  eine Menge braucht, liest `order_lines.effective_quantity` statt der bei Mehrpositionen
  leeren Anker-Menge. Beides ist «mehrartikel-fähig» – ein Modul, das nichts vom Artikel
  wissen muss, braucht dafür keinen Mechanismus. Wächter `tests/rules/test_multi_article.py`.

- **Testnotizen-Runde 46 (die Menge entscheidet, nicht die Stufe; #594–#598)**:
  (1) **Ein Beleg steht auf fremder Grundlage, sobald seine MENGE nicht mehr stimmt**
  (#598, `rebase._off_basis`). Gemeldet: ein Auftrag über 3 Stück, ein Stück wird
  verschrottet, **bevor** die Beschaffung dran ist – beim Modul kommen 2 an, der Mensch
  bestellt 2, und danach meldet das System «Bestellt 3 Stk · gebraucht 2 Stk». Ursache war
  eine Abkürzung: stand der Beleg **schon** auf seiner ersten Stufe («Angefragt»), galt er
  als in Ordnung – «die Stufe stimmt» wurde mit «es gibt nichts zu tun» verwechselt. Die
  Anfrage blieb darum bei 3 stehen, und die Abweichung fiel erst beim **Bestellen** auf,
  also genau dann, wenn das System sie nicht mehr allein beheben darf (Zusage → Klärung).
  Massgeblich ist jetzt die Menge; die Stufe zählt nur noch dort, wo es keine Menge mehr
  gibt (der Auftrag ist zu Ende → letzte Stufe). Neue Zeile in der Beleg-Regel-Tabelle
  (`beleg-noch-angefragt`) plus der gemeldete Ablauf als eigener Wächter, beide gegen die
  Bug-Form gegengeprüft.
  (2) **Ein ganz ausgesteuertes Teil ist kein Drift** (aus demselben Systemprotokoll):
  «⚠ Journal und Projektion weichen ab – lebend 0 ≠ Projektion 1». Eine verschrottete
  Instanz BEHÄLT ihre Menge (#481) und liegt im Journal vollständig im terminalen Topf –
  das ist das erwartete Bild, nicht ein Widerspruch. `ledger.verify_instance` überspringt
  darum Instanzen, deren eigene `disposition` terminal ist. Ein Wächter, der im
  Normalbetrieb anschlägt, ist von einem kaputten nicht zu unterscheiden.
  (3) **Der Lieferant sieht den Auftrag durch SEIN Modul** (#594, revidiert #592): der
  vollständige Prozess war zu viel – was intern mit dem Material geschieht (welche Prüfung,
  welche Bewegung, welcher Verkauf), geht ihn nichts an. **Und zwar SEINES:** ein Auftrag
  darf mehrere Beschaffungen mit verschiedenen Lieferanten haben, und der eine sah bisher
  das Modul des anderen – massgeblich ist der **Beleg**, nicht der Schritttyp
  (`orders._own_steps`). Mit dem Ausschnitt gehen auch Verlauf, Material auf den Kanten und
  Unter-Aufträge nicht mehr mit: sie beschreiben den internen Lauf. Die Grenze steht im
  **Backend**; der Filter in der Oberfläche ist ersatzlos entfallen (er wäre eine Bitte,
  keine Grenze). Wächter `tests/rules/test_supplier_view.py` (Wirkung über den echten
  Antwort-Aufbau) + der umbenannte Spiegel-Test.
  (4) **Der Kopf sieht überall gleich aus – auch ohne Reiter** (#595): `paddingBottom: 0`
  gibt es nur, damit der rote Aktiv-Balken eines Reiters auf der Kopf-Haarlinie liegt
  (#290). Wo es keine Reiter gibt – der Lieferant sieht keine –, klebte die
  Objektnummer-Zeile ohne Abstand auf der Linie. Die Reiter sind darum ein **eigener Slot**
  der Kopf-Anatomie (`DetailHeader tabs=…`) statt beliebiger Kinder: der Kopf entscheidet
  seinen Fussabstand selbst, und die fünf Aufrufer können beim Abstand nicht mehr
  auseinanderlaufen (sie trugen 10 px und 16 px für dieselbe Zeile).
  (5) **Ein Knopf heisst, was er TUT** (#596): «Bestellen» statt «Bestellt» – der Zustand
  steht bereits an der Stufe daneben. Beide Wörter kommen aus derselben Stufen-Tabelle
  (`FLOW.verb`), also können Knopf und Knoten nicht auseinanderlaufen.
  (6) **Ein Modul hat genau EINE Breite** (#597): beim Hinzufügen, nach dem
  Zwischenspeichern und nach der Freigabe war dasselbe Modul verschieden breit. Der Grund
  war, dass die Breite auf zwei Arten entstand – im laufenden Fluss als **feste**
  Spaltenbreite, im Schritt-Editor als `max-width` je Karte, also «so breit wie der Platz,
  höchstens …». Eine Obergrenze ist keine Breite; sie schwankt mit ihrer Umgebung. Es gibt
  darum die Hauptspur als EINEN Baustein (`flow-line.Lane`), in den sich beide stellen –
  `STEP_MAXW` ist entfallen, keine Karte bringt mehr eine eigene Breite mit. Dazu dieselbe
  Karten-Anatomie im Editor wie im Fluss (Polsterung 13/16, Symbol-Kasten 34, Titel 15 px):
  eine Karte mit anderer Innenaufteilung wirkt verschieden breit, auch wenn sie es nicht ist.

- **Der Zustand einer Instanz ist die PROJEKTION über ihre Stücke** (August 2026,
  Testnotizen #601/#602/#604/#615): Zwei Fehler mit einer gemeinsamen Wurzel – eine Menge
  wurde als ein Ding behandelt.
  (1) **Übernommen wird, was reserviert wurde** (#615). Der FIFO-Zweig der Allokation liess
  das Mengen-Argument von `subject.record_link` weg; die Buchung fiel auf `inst.quantity`
  zurück. Ein Auftrag über **1 Stück** nahm damit eine 4er-Charge komplett in seine Obhut,
  gab beim Abschluss nur seinen Anspruch (1) frei – und hielt die restlichen 3 **für immer**
  (im Fluss die richtige Instanznummer mit der falschen Menge, im Bestand drei fehlende
  Stück, die niemand angefasst hatte). Der Parameter hat jetzt **keinen Vorgabewert** mehr:
  ein Vorgabewert macht aus einem vergessenen Argument eine stille Falschbuchung.
  (2) **Der Datensatz-Zustand wird ABGELEITET, nicht zugewiesen** (`units.project`/
  `sync_state`, #604). Ein Datensatz trägt genau einen Zustand, eine Charge aber viele –
  ein Stück verschrottet, zwei freigegeben, eines im Prozess. Die Frage ist nicht, welcher
  stimmt, sondern **welcher auf den Datensatz gehört**; die Rangfolge folgt dem, wonach man
  sucht: **≥ 1 Stück freigegeben → «am Lager»** (sonst fände FIFO die Charge nicht), sonst
  «Im Prozess», sonst der Endzustand (`_TERMINAL_RANK`). Gesperrt gewinnt, solange etwas
  lebt. Vorher wurde der Skalar in **einem Moment** zugewiesen (`all_released` beim
  Freigeben); schied danach ein Geschwister-Stück aus, kippte die Bedingung nachträglich,
  aber niemand rechnete sie neu – die Instanz blieb für immer «Im Prozess», obwohl im
  Detail jedes Stück «Freigegeben» zeigte (#601/#602). Als Projektion, nachgezogen in
  `mark_released`/`drop`/`restore`, kann das nicht mehr auseinanderlaufen.
  (3) **Die Kehrseite: die MENGE trägt die Wahrheit.** «Am Lager» sagt jetzt nur noch «hier
  liegt etwas Entnehmbares». Darum gibt es **zwei Fragen mit zwei Namen**:
  `reservation.free_qty` = «wem gehört nichts» (gesamt − beansprucht) und
  **`inventory.ready_qty`** = «was ist entnehmbar» (frei UND freigegeben, je Stück gezählt).
  Alle Allokations-Leser (FIFO, Ressource, Verkauf, Recovery, Verfügbarkeits-Anzeige) lesen
  die zweite – so kann FIFO kein Stück herausgeben, das noch mitten im Prozess ist; die
  Auswahl einer gebundenen Instanz (Abweichung) liest weiter die erste. Passend dazu fragt
  `inventory.rest_owner` nicht mehr nach dem **Instanz**-Skalar («am Lager → niemandem»),
  sondern nur noch, ob es einen laufenden Erzeuger gibt – ob ein einzelnes Stück frei ist,
  entscheidet `Unit.released`. Alt-Instanzen ohne Freigabe-Marken werden tolerant gelesen
  (`ensure` markiert eine Instanz am Lager als freigegeben).
  Wächter: `tests/rules/test_units.py: test_an_order_only_takes_over_the_share_it_reserved`,
  `…_the_instance_state_is_a_projection_over_its_pieces`,
  `…_fifo_never_hands_out_a_piece_that_is_still_in_process`; gegen echtes PostgreSQL 16
  verifiziert und **gegen beide Bug-Formen gegengeprüft**.

- **Testnotizen-Runde 47 (der Zustand steht am Stück, Notizen #599–#614)**: Die Runde
  hängt an der Projektion darüber – seit jedes Stück seinen Zustand trägt, kann die
  Oberfläche ihn auch zeigen.
  (1) **Jede Einheit sagt, wo sie liegt** (#605, `units.place`): die Standort-Verteilung
  der Instanz (`instances.locations`, eine Mengen-Map) wird der Reihe nach auf die
  aufsteigenden Stück-Nummern gelegt – **EINE Logik für Charge und Einzelteil**; liegt
  alles an einem Ort, bekommt es jedes Stück. Ein ausgeschiedenes Stück bleibt ohne
  Standort (Ausschuss hat keinen Halter). Damit ist die Standort-Karte darüber entfallen:
  «wo ist was?» hat genau eine Antwort, und sie steht an den Stücken.
  (2) **Die Kachel «Am Lager» entfällt** (#606) – die Zahl steht bei jeder Einheit, mit
  Zustand und Standort dazu. **«Stücke» heisst «Einheiten»** (#607).
  (3) **Der Bestand am Artikel ist eine Liste von STÜCKEN** (#600, `instance-list.tsx`
  neu): eine Zeile ist ein Stück, gruppiert nach Zustand (nicht gefiltert – ein Filter
  versteckt, gefragt war das Gegenteil), FIFO innerhalb der Gruppe, darüber eine
  Zusammenfassungs-Zeile «Punkt + Wort + Menge». Das ist genau der Grund, warum FIFO an
  der Instanz-Badge vorbeischaut: eine Charge kann geteilter Meinung sein.
  (4) **Der Prüfumfang ist ein Symbol-Schieber** (#610, `IconSwitch symbolOnly`) wie
  überall sonst; ein Prozent-Symbol blendet den Sonderwert ein. **Enter legt den Schritt
  an** (#611). Erfassungsfelder sind Zeilen mit Haarlinie statt Kacheln (#612).
  (5) **Die Aufgabe statt der Einstellung** (#614): «1 von 1 Stück prüfen» – der
  eingestellte Prozentsatz ist die Herkunft und steht im Hover. Die Stichproben-Zeile
  nennt die Objektnummer, nicht das Wort «Instanz» (#613).
  (6) **Abstände** (#599): der Konnektor vor der Modul-Palette gehört zu ihr – im
  freigegebenen Prozess gibt es sie nicht, und dann standen zwei hintereinander (doppelter
  Abstand zur Zielflagge). **Und die Spur steht mittig** (#609): seit sie eine feste
  Breite hat (#597), richtet sie sich im Block-Fluss links aus – im laufenden Auftrag
  zentriert `Row` sie, beim Anlegen niemand.

- **Der Shortcut merkt vor, er entscheidet nicht** (Testnotiz #608): Der «Auftrag anlegen»-
  Knopf am Instanz-Detail merkt jetzt **nur noch die Instanz** vor – keine Menge, keinen
  Anteil. Die Vorauswahl war über drei Runden gewachsen (ein Stück #385, aber nicht bei
  mehreren Anteilen #394, die Instanz trotzdem #400, und der Halter musste genannt werden
  #390/#553) und lief auf eine Fallunterscheidung über «wie viele Anteile hat diese
  Instanz» hinaus – bei einer Charge lautet die Antwort selten «einer». Ein Anteil ist seit
  #394 eine **Entscheidung** (der genannte verliert unbedingt); Entscheidungen füllt man
  nicht vor. Damit gilt EIN Weg für Einzelteil und Charge, für einen Anteil und für fünf.
  Genannt wird ein Halter nur noch dort, wo er wirklich bekannt ist: am Abkürzungs-Knopf im
  **Fluss** (`seedFromLots`) – dort nennt die Kante die Menge, und der Halter ist der
  Auftrag, dessen Fluss man ansieht.
  **Und der Knopf sagt nicht mehr voraus, was daraus wird** (nimmt #380 zurück): er trug die
  Farbe der Instanz-Badge und hiess bei einer gebundenen Instanz vorab
  «Abweichungsauftrag». Das kann die Badge gar nicht wissen – eine Charge mit teils freien,
  teils gebundenen Anteilen wird zum einen ODER zum anderen, je nachdem welche **Zeile** man
  anklickt (`subject.classify_pick`). EIN Knopf, ein Name, ein Ton; was es wird, zeigt der
  Entwurf sofort (gebundener Anteil → Halter links, Rückgabe-Linie unten).

- **Instanzen entstehen ausschliesslich aus dem Prozess des ARTIKELS** (Testnotiz #622, der
  schwerste Fehler dieser Runde): Ein regulärer Auftrag, im Bedarf ausdrücklich **«Ab Lager»**
  (FIFO, 2 Stk), mit einem eigenen Ablauf «Datenerfassung + Beschaffen» – die Freigabe legte
  **zwei neue Instanzen** an. Aus dem Nichts entstand Bestand, den niemand hergestellt hatte.
  **Die Ursache war eine zweite Aussage über dieselbe Sache.** Jeder Schritttyp deklarierte
  neben Polarität und Fachtabelle auch eine **Subjekt-Rolle**, und `derive_subject_mode`
  aggregierte sie über die Vorrangordnung `stock ≻ produce ≻ instance` zur Subjektart des
  Auftrags. Ein order-eigener **Beschaffungs**-Schritt trug `produce` – also gewann die
  unsichtbare Ableitung gegen die sichtbare Eingabe des Menschen.
  **Die Regel hat jetzt genau EINE Bedingung** (`subject.subject_kind`): *hat der Auftrag
  einen eigenen Ablauf?* Wenn ja → `stock` (er greift zu, er erzeugt nie); wenn nein → er
  fährt den **Artikel**-Prozess, und nur DER erzeugt. Der Grund für die alte Regel ist
  weggefallen: sie sollte verhindern, dass ein solcher Auftrag bei leerem Lager still 0
  Instanzen bindet – genau dafür gibt es heute die **Unterdeckung** (sichtbar, blockiert den
  zugreifenden Schritt, Nachschub fährt den Artikel-Prozess, ADR 003). Wer beschaffen will,
  was es noch nicht gibt, modelliert die Beschaffung **am Artikel**.
  **Und die Rolle wird gar nicht mehr deklariert.** `EventType.subject_role`,
  `subject_role()`, `derive_subject_mode()`, `SUBJECT_PRECEDENCE` und die Konstanten
  `PRODUCE`/`STOCK`/`INSTANCE` sind aus der Registry **entfernt**, ebenso der Spiegel
  `lib/process.isStockOperation` samt `STEP_SUBJECT_ROLE` im Frontend (die Schrittzahl IST
  die Antwort, also trägt `onStepsCount` nur noch sie). Eine tote Achse stehen zu lassen wäre
  die Einladung, dieselbe Ableitung wieder zusammenzusetzen – dieselbe Lehre wie bei der
  toten Unterschrift/Foto-Achse (Migration 081).
  **Zwei Riegel, nicht einer:** die Erzeugung prüft es zusätzlich selbst
  (`serialization.create_instances_for_order` weist einen Auftrag mit eigenem Ablauf ab).
  Ein Wächter allein an der Ableitung liesse jeden künftigen zweiten Aufrufer durch – und
  genau ein solcher Pfad hat den Schaden angerichtet.
  Wächter: `tests/rules/test_creation.py` (Wirkung über die echten Dienst-Pfade gegen echtes
  PostgreSQL 16 – der gemeldete Fall, **jeder** Schritttyp einzeln, die Gegenprobe «ohne
  eigenen Ablauf entsteht sehr wohl etwas» und der Riegel in der Erzeugung) +
  `test_smoke.py: test_only_the_article_process_creates_instances`,
  `…_stock_effect_is_declared_and_the_subject_role_is_gone`. **Gegen die Bug-Form
  gegengeprüft:** mit der alten Rollen-Ableitung meldet die Datei genau die drei
  `produce`-Typen (Beschaffung · Ressource · Dokument) und den gemeldeten Fall.

- **Testnotizen-Runde 48 (der Shortcut merkt vor, der Editor konfiguriert; #616–#621)**:
  (1) **Auch der Artikel-Shortcut merkt nur vor** (Nutzer-Wunsch, dieselbe Logik wie #608):
  er füllte «1 Stück» vor – eine Behauptung, die selten stimmt und trotzdem freigebbar
  aussieht. Vorgemerkt wird jetzt nur der **Artikel**; wie viel, woher und mit welchem
  Ablauf entscheidet der Mensch. Beide Knöpfe heissen im Hover schlicht **«Auftrag»** (#616)
  – was danach passiert, sieht man im Entwurf.
  (2) **Kein «Enter legt an»** (#621, nimmt #611 zurück): ein Schritt wird im Editor
  **konfiguriert**, nicht ausgefüllt – Bezugsquelle, Prüfumfang, Erfassungsfelder, Parteien.
  Eine Taste, die mitten in dieser Arbeit anlegt, legt fast immer etwas Halbfertiges an, und
  ein Schritt ist danach nicht mehr änderbar (löschen + neu). Das ist derselbe Grund, aus
  dem der «Hinzufügen»-Knopf bleibt (#40/#68).
  (3) **Der Hover kommt sofort – überall** (#618): `IconSwitch` nannte seine Optionen über
  `title`, also über den nativen Browser-Tooltip mit rund einer Sekunde Verzögerung. Genau
  da, wo das Symbol allein nicht trägt, ist das die Sekunde, in der man ratlos ist. Jetzt
  `data-tip` wie überall sonst – und weil es an EINER Stelle steht, gilt es für jeden
  Umschalter im Haus (Bezugsquelle, Sichtbarkeit, Aussondern, Verkauf, Transport …).
  **Ein Anteil lässt sich nicht zeichnen:** «jedes zweite Stück» hat kein Symbol, das ohne
  Vorwissen lesbar wäre. Der Prüfumfang schreibt darum die **geltende** Option aus
  (`labelActiveOnly`, dieselbe Lösung wie bei der Mengeneinheit #219/#220); die Symbole sind
  Griffe für die Alternativen (Stichprobe jetzt `FlaskConical` – eine Probe im Laborsinn).
  (4) **Im Formular wird alles vom linken Rand gelesen** (#619): die Erfassungsfeld-Palette
  stand zentriert unter einer linksbündigen Beschriftung. Zentriert bleibt sie dort, wo sie
  unter einer zentrierten Achse hängt (Modul-Palette im Fluss, Unterdeckungs-Dialog).
  (5) **Prägnanter** (#620): «Mindestens ein Erfassungsfeld nötig».
  (6) **Keine Zusammenfassung über dem Bestand** (#617): jede Zustands-Gruppe trägt Wort und
  Menge bereits im Kopf – eine Zeile, die dieselben Zahlen vorwegnimmt, sagt nichts Neues.

- **Testnotizen-Runde 49 («Reserviert» ist kein Zustand, der Name wächst daneben; #623–#626)**:
  Zwei der vier Notizen hingen an derselben Wurzel – **derselbe Zustand wurde an zwei
  Stellen verschieden beantwortet**.
  (1) **Ein ausdrücklicher Anspruch gilt immer** (#625, `units.rows`/`owned_by`). Gemeldeter
  Fall: eine freigegebene Charge à 4, ein Auftrag holt sich EIN Stück ab Lager – und das
  Instanz-Detail zeigte weiter alle vier als «Freigegeben». Dass eines davon in einem
  laufenden Auftrag steckt, stand nirgends, während die Anteils-Aufteilung daneben
  «1 · Auftrag …» sagte. Ursache war eine zu breite Fassung von #573/#577 («freigegeben
  heisst frei»): sie ist richtig für den **geerbten Rest** (der gehört dem Erzeuger nur,
  solange etwas im Prozess ist), aber falsch für den **ausdrücklichen** Anspruch. Jetzt
  sind es zwei Zweige statt eines.
  (2) **«Reserviert» ist ersatzlos entfallen** (#626, ausdrücklicher Wunsch). Es war ein
  dritter Zustand für etwas, das «Im Prozess» längst sagt: ein Stück, das ein laufender
  Auftrag hält, IST in einem Prozess. Der Unterschied («schon im Prozess» ↔ «am Lager und
  gebunden») war eine Frage des **Zeitpunkts**, nicht der Sache – verwendbar ist es in
  beiden Fällen nicht, und **wer es hält, steht jetzt daneben** (die Stück-Zeile nennt den
  Auftrag). Der dritte Parameter von `instanceStatusConfig` heisst darum `held` und bildet
  auf «Im Prozess» ab; ein Zustand weniger im ganzen System.
  Dazu war sein Auslöser am **Datensatz** zu grob: «irgendetwas ist beansprucht» stellte
  eine Charge à 4 mit EINEM gebundenen Stück als Ganzes auf Gelb, während die Liste
  darunter drei freie zeigte. Die Frage eines Datensatzes lautet **«ist hier noch etwas
  frei?»** – ist alles vergeben, ist er «Im Prozess», sonst «Freigegeben»
  (`record-status.instanceStatus`, die EINE Ableitung; `scrap-panel`/`order-positions`
  bauten sie sich bis dahin selbst zusammen, entgegen #379). Die DB-Skalare bleiben
  unangetastet: sie sind der Index für FIFO und Bestand, und reservierter Bestand ist
  weiterhin Bestand.
  (3) **Der Buttonname wächst im Hover DANEBEN heraus** (#624, vierter Anlauf – und der
  erste, der gemessen wurde). Die drei gescheiterten hatten alle dieselbe Wurzel: der Name
  braucht Platz, den die Reihe nicht hat. Wuchs der Knopf **im Fluss**, brach die Zeile um,
  er wanderte unter dem Cursor weg, der Hover endete, er schrumpfte – die Rückkopplung war
  das gemeldete «Springen» (#502/#503); eine Pille darüber sah gelöst aus (#509/#510), eine
  Zeile darunter schrieb den Namen zweimal hin (#518).
  Die Lösung trennt die beiden Grössen: **im Fluss** belegt der Knopf eine feste Zelle
  (44×44, `.erp-palette-cell`) – daran ändert der Hover NICHTS, also kann nichts umbrechen
  und nichts springen; **gezeichnet** wird er absolut darin und wächst nach rechts über den
  Nachbarn. Das Umbrechen in eine zweite Reihe passiert damit rein statisch. Dieselbe Geste
  am **Segment-Umschalter** (#624 ausdrücklich: «auch gleich beim Prüfumfang», `.ix-seg`) –
  dort darf er im Fluss wachsen: die Optionen links vom Cursor bleiben stehen, und der
  gleitende Reiter wird ohnehin gemessen.
  **In Chromium nachgemessen statt überlegt** (Lehre aus #583/#550): die sonst übliche
  `grid-template-columns: 0fr → 1fr`-Technik greift hier **nicht** – bei einem Knopf, der
  seine Breite aus dem Inhalt zieht, blieb er bei 44 px stehen; mit `max-width` wächst er
  auf 169 px. Gemessen wurden ausserdem: Zellen und Palettenhöhe bleiben bei jedem Hover
  identisch (auch beim letzten Knopf und bei bereits **umgebrochener** Reihe), und der
  Umschalter bleibt mit 193 → 273 px klar in seiner 460-px-Bahn.
  (4) **Kein «Erstellt» am Instanz-Detail** (#623): welches Datum wäre es – die Anlage des
  Datensatzes oder die Freigabe des Stücks, und bei einer Charge womöglich für jedes Stück
  ein anderes? Eine Zahl, die je nach Lesart etwas anderes meint, sagt weniger als keine.
  Wann wirklich etwas passiert ist, steht im **Verlauf** (Material-Journal), Buchung für
  Buchung.
  Wächter: `tests/rules/test_units.py: test_a_claimed_piece_names_the_order_that_holds_it`
  (gegen die Bug-Form gegengeprüft – ohne den Fix meldet er «Genau ein Stück nennt den
  Auftrag, der es hält (ist [])»), `test_frontend_mirrors.py:
  test_reserved_is_not_a_state_of_its_own`,
  `…_the_palette_name_grows_beside_the_symbol_without_moving_anything`.

- **Das Prozessbild ist responsiv – waagrecht scrollen gibt es nicht** (August 2026,
  `components/erp/flow-line.tsx`): Die Spurbreiten standen als **feste Zahlen** im Modul –
  drei Spuren à 460 px plus Luft ergaben **1432 px Mindestbreite**, und was nicht
  hineinpasste, wurde in einen waagrecht scrollenden Kasten gesteckt. Das traf **jedes**
  Gerät: schon ein 13″-MacBook hat im Detailfenster nur ~1060 px (Fenster − Feed − Polsterung),
  ein iPhone ~335. Bei einem Diagramm ist seitliches Scrollen besonders schlecht – man
  verliert die Achse aus dem Blick, also genau das, worum es geht.
  **Die Geometrie ist jetzt eine Funktion der gemessenen Breite** (`metricsFor`, EINMAL
  gemessen im `FlowFrame` per ResizeObserver, über einen Context an alles verteilt, was eine
  Linie zeichnet). Damit gibt es weiterhin genau EINE Quelle für jede Zahl – sie ist nur
  nicht mehr konstant. `MAIN`/`SIDE`/`LANE`/`RUN` als Modul-Konstanten sind entfallen; wer
  eine Spurbreite braucht, fragt `useFlow()`.
  **Zwei Ausprägungen, dieselben Bausteine:**
      Spuren      Drei Spuren nebeneinander (Herkunft · Achse · Abzweige) – das gewohnte
                  Bild. Die Spurbreite schrumpft mit dem Platz (460 → 240), sonst ändert
                  sich nichts.
      Gestapelt   Unter 3·240 + 2·26 = **772 px** passen drei lesbare Spuren nicht mehr
                  nebeneinander. Dann läuft ALLES in einer Spur: ein Abzweig ist ein
                  Unterprozess **auf** der Achse (mit seinen eigenen Terminal-Knoten), die
                  Ecken werden zu geraden Verbindungsstücken, die Abzweigung kürzer
                  (`ARM_STACKED`). Kein zweites Vokabular – dieselben Karten, dieselbe
                  Linie, nur ohne Seitwärtsbewegung; die Maske zur Kante entfällt (sie
                  behauptete «hier geht es seitwärts weiter»).
  **Die gemessene Spurbreite wird GERADE gemacht** – dieselbe Regel wie bei der Strichstärke
  (#550): die Achse sitzt mittig in ihrer Spur, also muss `(Spur − Strich)/2` ganzzahlig
  sein; bei ungerader Spur begänne ihr Kasten auf einer halben Pixelgrenze und der SVG-Pfad
  der Ecke läge daneben.
  **In Chromium an den echten Gerätebreiten gemessen** (Detailfenster = Fenster − Feed −
  40 px Polsterung), im laufenden Fluss, im Entwurfs-Rahmen und mit geöffnetem
  Schritt-Editor: 1440 → Spuren à 336 · 1280 → 284 · 1200 → 256 · 1024 → gestapelt · 834 →
  gestapelt · 375 → gestapelt · 320 → gestapelt. **Überall 0 px waagrechter Überlauf.**
  Nebenbei geschlossen: drei Stellen, die aus ihrer Spur ragen konnten – die Material-Pille
  (lange Nummernkette, jetzt gekürzt mit voller Angabe im Hover), der Abkürzungs-Knopf
  daneben (die Pille lässt ihm seinen Platz) und der **Liefertermin** am Endknoten (steht
  unter dem Knoten, wenn daneben kein Platz ist). Die Hover-Karte wird ins Fenster gezogen.
  Wächter: `test_frontend_mirrors.py: test_the_process_picture_never_scrolls_sideways`.

- **Die FIFO-Zeit gehört zur MENGE, nicht zur Instanz** (August 2026, `services/units.py`):
  Sie war die **letzte** Grösse, die noch instanzweit stand (`instances.released_at`) – und
  damit die letzte, die bei einer Charge lügen konnte: werden drei Stück heute und eines in
  vier Wochen frei, trugen alle vier das Datum von heute. Zustand (`s`/`x`), Menge (`q`),
  Halter (`o`) und Standort hängen längst am Stück; die Zeit tut es jetzt auch (Lauf-Feld
  `t`). Drei Regeln, alle drei aus der einen Einsicht, dass `t` eine **Tatsache über die
  Vergangenheit** ist und keine abgeleitete Grösse:
  (1) **Gesetzt beim ERSTEN Freigeben** (`mark_released`) und danach nie überschrieben –
  «seit wann am Lager» meint den Moment, in dem genau dieses Stück freigegeben wurde, nicht
  den Abschluss irgendeines Auftrags (das war der fachlich unscharfe Punkt).
  (2) **Eine Retoure setzt die Uhr nicht zurück** (`process._restock_one` setzt
  `released_at` nur noch, wenn es gar keines gibt; `units.restore` lässt `t` stehen): sie
  stand auf «jetzt», womit zurückgenommene Ware schlagartig die *jüngste* im Lager war und
  als letztes wieder hinausging – bei FIFO als Alterungsschutz genau verkehrt.
  (3) **Altbestand bekommt seine Eröffnungsbilanz** (`units.ensure`/`_open`) statt einer
  erfundenen Historie: Stücke ohne `t` erben `released_at`/`created_at` der Instanz.
  **Gelesen wird an EINER Stelle** – `units.fifo_since` (das älteste *entnehmbare* Stück,
  sonst das älteste freigegebene, sonst der Stand der Instanz) bzw. `fifo_key` für die
  Sortierung; `inventory.fifo_candidates` liest sie. Angezeigt am Stück
  (`InstanceUnit.in_stock_since`, Testnotiz #631) und im Artikel-Bestand als Reihenfolge.
  **`instances.released_at` bleibt** – als Projektion (erste Freigabe) und als **Dokument-
  datum** einer Dokument-Instanz. Das ist bewusst keine Doppelung: ein Dokument ist ab
  seiner Freigabe gültig, und genau ab da zählt es auch in der Reihenfolge (`legal.resolve`).
  **Derselbe Umbau behebt einen gemeldeten Fehler:** beim Verschrotten EINES Stücks stufte
  `sync_state` eine Charge, deren Stücke (noch) keine Freigabe-Marke trugen, aus dem Nichts
  auf «Im Prozess» zurück – jetzt trägt die Eröffnungsbilanz die Marke nach, statt den
  Zustand wegzuwerfen (tolerant lesen, streng schreiben).
  Wächter: `tests/rules/test_units.py` (`test_the_fifo_time_belongs_to_the_piece`,
  `…_fifo_orders_by_the_oldest_ready_piece`, `…_a_return_does_not_reset_the_fifo_clock`,
  `…_stock_without_marks_is_opened_not_downgraded`) – gegen beide Bug-Formen gegengeprüft,
  522 Prüfungen gegen echtes PostgreSQL 16.

- **Testnotizen-Runde 36 (eine Karte, ein Layout, Notizen #627–#636)**:
  (1) **Ein Modul steht sofort im Fluss und wird dort konfiguriert** (#635): Der Klick auf
  ein Palette-Symbol legt es an – «Abbrechen»/«Hinzufügen» sind entfallen. Damit fallen
  **drei** Darstellungen desselben Moduls auf **eine** zusammen (Anlage-Formular · Karte im
  Entwurf · Karte im freigegebenen Prozess); ist der Träger freigegeben, ist dieselbe Karte
  schlicht **gesperrt** (`fieldset[disabled]` – eine Zeile statt eines zweiten Layouts), und
  geändert wird per Auto-Save wie überall. Dass ein Modul dadurch **unfertig** beginnen darf,
  ist keine Lockerung, sondern der richtige Zeitpunkt: geprüft wird an der **Freigabe**
  (`processes.incomplete_steps`, gefordert nur, was wirklich nicht laufen kann – eine
  Datenerfassung ohne Maske erfasst ein synthetisches Gut/Schlecht und ist damit
  ausführbar; das Formular legt sie ohnehin mit einem Feld an). Die **Wirkung** des Moduls
  «Aussondern» ist seither eine Konfiguration statt eines zweiten Moduls: `step_type` ist
  im Update erlaubt, aber **nur** innerhalb scrap ↔ block (jeder andere Wechsel wäre ein
  anderes Modul – dafür gibt es löschen und neu anlegen).
  (2) **Der Palettenname steht im Hover ÜBER dem Symbol** (#630, vierter Anlauf nach
  #502/#503, #509/#518, #624): wuchs er aus dem Knopf nach rechts heraus, verdeckte er den
  Nachbarn. Er kommt jetzt aus der EINEN Tooltip-Mechanik des Hauses (`data-tip`) – sie
  schwebt über der Zeile, kostet keinen Platz im Layout und bleibt darum auch bei
  umbrechender Palette richtig.
  (3) **Ein Anteil bekommt Worte** (#636): «Alle · Jedes 2. · Jedes 4. · Stichprobe» stehen
  ausgeschrieben da. Das ist keine Ausnahme von «Symbole statt Text», sondern dessen
  Kehrseite – ein Anteil hat kein Bild, das man ohne Vorwissen liest (#618), und ein Symbol,
  das man raten muss, ist keines.
  (4) **Die Achse steht IMMER in der Mitte** (#627): eine Zeile **ohne** Seitenspuren ist nur
  die Spur – ein Kind fester Breite in einer Spalte –, und mit `alignItems: 'stretch'` klebte
  sie am linken Rand (in Chromium gemessen: 9…469 statt 279…739 in einer 1000-px-Fläche).
  Betroffen war jeder Auftrag ohne Abzweig, also der Normalfall. Zentriert wird jetzt im
  `FlowFrame`, an EINER Stelle.
  (5) **Der Artikel-Bestand liest dieselbe Aufbereitung wie überall** (#632,
  `instances.denorm`): er hatte eine zweite, kürzere Fassung **ohne** die Stücke – eine
  Charge à 4 stand darum als EIN Block mit dem Zustand des *Datensatzes* da, während
  dieselbe Charge im Instanz-Detail Stück für Stück drei Zustände zeigte.
  (6) **Kein Journal mehr in der Antwort** (#628/#629): die Buchungsliste am Auftrag und an
  der Instanz ist entfernt (`OrderResponse.history`/`InstanceResponse.history`,
  `MoveJournal`, `ledger.history`). Das Material-Journal bleibt die Wahrheit über die
  Vergangenheit (ADR 007) – es speist Fluss-Kanten, Stück-Zustände und das Systemprotokoll;
  als ausgeschriebene Liste sagte es nur ein zweites Mal, was der Fluss ohnehin zeigt.
  (7) Kleineres: die Wirkung im Ausschleusen-Editor als Symbol-Schieber mit Hover-Namen
  (#633), die Zeile «• Grund (Pflicht bei der Ausführung)» entfällt (#634 – der Grund ist
  Pflicht, das sagt die Ausführung selbst), die FIFO-Zeit steht an jeder Einheit (#631).

- **Sperren ist Verschrotten – nur reversibel** (August 2026, Testnotiz #646): Der Schritt
  «Aussondern · Sperren» setzte bisher nur eine Notiz an der Instanz (`quality='blocked'`).
  Das Stück hing danach weiter im Auftrag: der wurde nie fertig, seine Rückführung lief
  weiter, und die Anzeige sagte «Im Prozess» statt «Gesperrt». Jetzt ist der **Ablauf
  identisch zum Verschrotten** – es ist dasselbe Modul: der Auftrag ist mit dem Stück
  fertig, gibt es **nicht** zurück und schliesst ab. Der Unterschied ist allein die
  **Umkehrbarkeit**: Menge, Standort und Nummer bleiben, das Stück liegt danach **am Lager,
  gesperrt** (gelb) – im Bestand des Artikels sichtbar, für FIFO unsichtbar, und über einen
  ganz normalen Auftrag jederzeit wieder aufnehmbar.
  **Die Sperre gehört dabei zum STÜCK, nicht zur Instanz** (`units`-Lauf `l`): wer eines von
  vier Stück aussondert, sperrte vorher faktisch die ganze Charge, und umgekehrt überschrieb
  die Freigabe-Marke eines Stücks die Sperre in der Anzeige. Der Instanz-Skalar ist seither
  die **Projektion** darüber (`units.project`: «gesperrt» erst, wenn nichts Verwendbares mehr
  übrig ist – sonst fiele die ganze Charge aus FIFO, obwohl gute Stücke darin liegen; die
  **Menge** trägt die Wahrheit, `free_quantity` gibt nie ein gesperrtes Stück heraus).
  **Drei Regeln, die daraus folgen:** (1) gesperrt wird, was **dieser** Auftrag hält (wie
  beim Verschrotten, #412/#414); (2) was er selbst ausgesondert hat, **fehlt ihm nicht** –
  `_disposed_amounts` zählt neben terminalen Buchungen jetzt auch die Sperr-Abgabe, sonst
  meldete ein Sperr-Auftrag am Ende eine Fehlmenge über seine ganze Menge und würde
  **abgebrochen** statt abgeschlossen (die Regel von #555, jetzt auch im regulären Pfad);
  (3) ein gesperrtes Stück deckt **nie** ein Soll (`_secured_amounts`, ohne Ausnahme und
  ohne zu fragen, wer gesperrt hat – siehe unten).
  Wächter `tests/rules/test_units.py: test_blocking_ends_the_order_like_scrapping_does`,
  `…_a_blocked_piece_comes_back_through_an_order` (beide gegen die Bug-Form gegengeprüft);
  gegen echtes PostgreSQL 16 verifiziert.

- **Aus einer Sperre führt EIN Weg – derselbe, der jedes Stück gut macht** (August 2026,
  Nachtrag zu #646): Die erste Fassung kannte **zwei** ausdrückliche Ausgänge – einen Knopf
  «Sperre aufheben» an der Instanz und eine **bestandene Datenerfassung**. Zwei Wege zu
  demselben Ergebnis sind zwei Wahrheiten, und welcher gilt, hing an der Reihenfolge der
  Schritte. Beide sind ersatzlos entfallen (`scrap.unblock`, `POST …/instances/{id}/unblock`,
  `units.clear_block`, der `else`-Zweig in `inspection._apply_per_instance_qc`, der Knopf im
  Instanz-Detail).
  **Die eine Regel:** «freigegeben» und «gesperrt» sind dieselbe Frage mit entgegengesetzter
  Antwort – *darf man das verwenden?*. Also hebt die **Freigabe** die Sperre auf
  (`units.mark_released` löscht `l`), und freigegeben wird, was ein Auftrag beim Abschluss
  noch **hält** (`process.release_instances`, seit #572). Man legt einen ganz gewöhnlichen
  Auftrag an, wählt das gesperrte Stück, lässt ihn durchlaufen – fertig. **Welcher Schritt
  darin steht, ist gleichgültig** (im Nachweis eine blosse Bewegung); die Datenerfassung
  stellt nur noch fest, was schlecht ist.
  **Vier Stellen mussten dafür ehrlicher werden, jede eine Vereinfachung:**
  (a) `Unit.done` = «freigegeben UND verwendbar» – ein gesperrtes Stück ist nicht am Ziel,
  also gibt der Abschluss es frei (vorher `not u.released`, und ein gesperrtes trug sein
  `s` schon).
  (b) **`subject.is_bound` fragt dieselbe Frage wie FIFO**: *was wäre entnehmbar?*
  (`inventory.ready_qty`) statt *wem gehört nichts?* (`reservation.free_qty`). Ein gesperrtes
  Stück gehört niemandem – es galt darum als frei, und eine Charge mit einem gesperrten Stück
  liess sich als gewöhnlicher Bedarf greifen. Jetzt ist die Nacharbeit **automatisch** ein
  Auftrag mit festem Subjekt (Abweichung), und für den zählt nicht «gesichert», sondern «hält
  er es noch?» – womit die Herkunfts-Frage aus (3) oben (`_self_blocked_amounts`, eine
  Journal-Abfrage nur für diesen Sonderfall) **ersatzlos** entfällt.
  (c) `_bind_deviation_subjects` reserviert, was am Lager **liegt** (`inventory.lies_at_stock`
  – die Ortsfrage) statt nur, was verwendbar ist: sonst hielte der Nacharbeits-Auftrag sein
  Subjekt gar nicht und könnte es am Ende nicht freigeben.
  (d) `subject.give_back` gibt **nur das Geliehene** zurück (`min(gehalten, Fehlmenge des
  Verleihers)`, Rest bleibt bis zum Abschluss). Vorher gab es den ganzen Anspruch ab – was
  der Unter-Auftrag sich selbst vom freien Bestand geholt hatte, wurde damit frei, **bevor**
  `release_instances` es sehen konnte; ein nachgearbeitetes Stück blieb gesperrt. Am Ende ist
  es dasselbe (der Abschluss löst ohnehin jeden Anspruch), nur eben nach der Freigabe.
  **Die eine Unschärfe, benannt statt versteckt:** ein Anteil benennt *Instanz · Menge ·
  Halter*, nicht die einzelne Nummer. Aus einer teilweise gesperrten Charge bekommt eine
  Teilmenge darum die **verwendbaren** Stücke (`units._assign`: genannter Anteil ≻ frei &
  verwendbar ≻ frei ≻ fremd) – wer das gesperrte will, nimmt die ganze Menge. Ohne diese
  Reihenfolge entschiede die Nummerierung darüber, ob ein gewöhnlicher Bedarf ein gesperrtes
  Stück erwischt.
  *Die Buchungsart `unblocked` bleibt im Journal – Altbestand trägt sie, und die
  Vergangenheit wird nicht umgeschrieben (tolerant lesen, streng schreiben).*
  Wächter: `tests/rules/test_units.py: test_a_blocked_piece_comes_back_through_an_order`
  (gegen **beide** Bug-Formen gegengeprüft), `test_smoke.py: test_block_is_reversible_scrap_is_not`
  (kein `unblock`, kein `clear_block`, `mark_released` löscht die Sperre),
  `…_a_deviation_borrows_and_gives_back`; gegen echtes PostgreSQL 16 verifiziert (ganz
  gesperrte Instanz **und** teilweise gesperrte Charge, je über die echten Dienst-Pfade).

- **Verfügbarkeit ist eine MENGE – und es gibt genau EINE Antwort darauf** (August 2026,
  Testnotiz #647): Gemeldet: ein Auftrag über 4 Stück «Ab Lager» meldete «nicht genügend
  Material», während der Bestand-Reiter desselben Artikels voll war. Zwei Ursachen, beide
  dieselbe Art – *über Datensätze geredet, wo Mengen gemeint waren*, und beide im
  **Frontend**:
  (1) **Der Pool war gekappt.** Die Auswahl lud `getInstances(500)` – den **globalen**
  Instanz-Feed, neueste Objektnummer zuerst, über alle Artikel. Sobald mehr als 500 jüngere
  Instanzen existierten, war vom Bestand des gesuchten Artikels **nichts** dabei: die
  Oberfläche rechnete korrekt, nur über der leeren Menge. Sie liest jetzt denselben
  Endpunkt wie der Bestand-Reiter (`getArticleInstances`), **je Artikel des Auftrags** –
  eine Frage, eine Quelle, keine Obergrenze.
  (2) **«Frei» war ein Zustand des DATENSATZES**: `quality==passed && disposition==in_stock
  && kein fremder Reservierungs-Zeiger`. Der Zeiger (`reserved_for_order_id`) ist eine
  **Denormalisierung** für die Anzeige («wer hält das?»), kein Mengenwert – eine Charge à
  500 mit EINEM reservierten Stück galt damit als vollständig belegt. Und seit der
  Instanz-Zustand die **Projektion über die Stücke** ist (#604), sagt «am Lager» ohnehin nur
  «hier liegt etwas Entnehmbares», nicht «alles davon».
  **Die eine Zahl:** `InstanceResponse.available_quantity` = `inventory.ready_qty` – frei
  UND freigegeben UND nicht gesperrt, **je Stück** gezählt; exakt das, was die
  FIFO-Allokation nähme. Die Oberfläche summiert sie (plus den eigenen, noch nicht scharfen
  Anspruch – dasselbe wie `inventory.avail_amount`), statt sie aus Skalaren nachzubauen.
  **Systematischer Nachlauf** (der Auftrag lautete: dieselbe Fehllogik im ganzen System
  suchen). Der Allokations-Kern war sauber – `fifo_candidates`/`ready_qty`/`avail_amount`/
  `available_qty` rechnen durchgehend mit Mengen, `claim_clauses` filtert
  `reserved_quantity < quantity` (nicht «hat einen Zeiger»). Zwei AST-Läufe über `app/`
  (Anzahl→Mengenfeld · Anzahl↔Menge verglichen) fanden **keinen** Treffer; die vier
  verbliebenen `len(…)` auf Instanz-Listen sind echte Anzahlen (Log-Text, Nummern-Zähler,
  ID-Prüfung). **Ein weiterer Fund**: die **KI**-Werkzeuge «Artikel lesen»/«Bestand»
  rechneten mit dem SQL-Aggregat `sum(quantity − reserved_quantity)` – dieselbe Frage,
  andere Antwort: eine Charge «am Lager» mit gesperrten oder noch im Prozess stehenden
  Stücken zählte dort voll mit. Die KI hätte einem Menschen eine Zahl genannt, die das ERP
  nirgends zeigt; beide lesen jetzt `inventory.available` bzw. das neue
  `inventory.free_by_article` (EINE Abfrage, dieselbe Regel).
  Wächter `tests/rules/test_availability.py` (Oberfläche == Allokation, auch bei
  Teil-Reservierung und gesperrtem Stück · Bestand liegt nicht unter den jüngsten
  Objektnummern · KI nennt dieselbe Zahl) und `test_frontend_mirrors.py:
  test_availability_is_a_quantity_from_one_source` (kein gekappter Gesamt-Feed, keine
  Skalar-Ableitung in der Oberfläche) – gegen die Bug-Formen gegengeprüft, gegen echtes
  PostgreSQL 16.

- **Audit «Anzahl statt Menge» – vier Funde nach der Vermutung des Nutzers** (August 2026,
  Nachlauf zu #647): Die ursprüngliche Vermutung («er zählt Instanznummern statt Mengen»)
  traf den gemeldeten Fall nicht, war als **Klasse** aber richtig. Ein systematisches Audit
  über das ganze System hat sie viermal gefunden – nicht als `len(…)`, sondern in ihrer
  heutigen Form: **ein Skalar der Instanz beantwortet eine Frage, die der Menge gehört.**
  Seit der Zustand die Projektion über die Stücke ist (#604), sagt «freigegeben» nur noch
  «hier ist etwas Gutes», nicht «alles davon».
  (1) **`_secured_amounts` zählte selbst erzeugte Instanzen über den Skalar**
  (`unblocked_clauses`) und damit eine teilweise gesperrte Charge mit ihrer **vollen** Menge
  als gesichert: ein Erzeugungsauftrag über 4 Stück, von denen eines gesperrt ist, meldete
  **keine** Fehlmenge und wäre mit drei guten Stück «vollständig» geworden. Jetzt zieht er
  die gesperrte Menge ab – und zwar nur, was **noch bei ihm** liegt (was eine offene
  Abweichung übernommen hat, steckt schon in der Klärungs-Menge; zweimal abgezogen ergäbe
  eine Fehlmenge, die es nicht gibt). Der Skalar-Filter ist damit überflüssig geworden.
  (2) **Der Made-to-Order-Verkauf verkaufte Gesperrtes mit.** Der Bestands-Zweig prüft das
  seit #646 (`reserviert − gesperrt`), der Zweig für selbst erzeugte Instanzen daneben las
  den Skalar und schob die **ganze** Charge auf `sold`. Jetzt geht nur der gute Teil hinaus;
  der gesperrte Rest bleibt als Instanz am Lager.
  (3) **`units.drop` gab beim Verkauf ausgerechnet das gesperrte Stück heraus**: die Auswahl
  der Stücke lief für jeden Endzustand über dieselbe Reihenfolge (niedrigste Nummer zuerst).
  Welche Stücke gemeint sind, sagt jetzt der **Endzustand**: wer **aussondert**, nimmt das
  Untaugliche zuerst (das ist der Sinn des Vorgangs), wer **liefert** (verkauft/verbaut),
  nimmt das Gute – Eigentum bleibt dabei das erste Kriterium, Tauglichkeit entscheidet
  innerhalb. Damit trifft eine Teil-Verschrottung das defekte Stück statt das erste.
  (4) **Der Kunden-Versand hätte eine gesperrte Rest-Charge mitgenommen**: nach dem Verkauf
  des guten Teils IST die Rest-Instanz das Gesperrte, und ihr Anspruch deckt sie wieder
  vollständig (`movement.movable_instances`). Eine Zeile schliesst das.
  Dazu entfernt: **`DisposalEmbed.scrapped_count`** – es zählte die vollständig
  verschrotteten **Datensätze** (eine Teil-Verschrottung erschien als «0») und wurde nirgends
  gelesen. Was ausgesondert wurde, steht mengengenau im Journal und an den Stücken.
  **Was sauber war** (und geprüft ist): der Allokations-Kern, Prüfumfang, Ressourcen-Bedarf,
  Nachschub, Meldebestand, Retoure und Bereitstellung rechnen durchgehend mit Mengen; zwei
  AST-Läufe über `app/` (Anzahl→Mengenfeld · Anzahl↔Menge verglichen) melden nichts, und die
  verbliebenen `len(…)` auf Instanz-Listen sind echte Anzahlen (Proben, Log-Text,
  ID-Prüfung). Wächter in `tests/rules/test_availability.py` – jeder gegen seine Bug-Form
  gegengeprüft.

- **Testnotizen-Runde 37 (eine Zahl, eine Quelle, Notizen #637–#644)**:
  (1) **«x von N Stück prüfen» kommt aus EINER Rechnung** (#643): `required_count` las, was
  der Auftrag tatsächlich hält, das `N` daneben die *deklarierte* Auftragsmenge – nachdem ein
  Abzweig ein Stück übernommen hatte, stand da «1 von 2», obwohl nur noch eines da war. Neu
  trägt der Embed die Bezugsmenge selbst (`InspectionEmbed.inspected_quantity`).
  (2) **Ein Erfassungsfeld ohne Namen ist noch nicht fertig – aber es ist da** (#637):
  gespeichert werden nur benannte Felder; solange die Zeilen direkt aus dem Gespeicherten
  kamen, verschwand jede neu angelegte sofort wieder und ein zweites liess sich nie
  hinzufügen. Die Liste lebt jetzt im Editor, der Speicher bekommt, was fertig ist.
  (3) **Nichts ist vorausgewählt** (#638): eine neue Datenerfassung startet ohne Feld – was
  erfasst wird, ist eine Entscheidung.
  (4) **EINE Instanz-Zeile für alle Panels** (#642, `components/erp/instance-row.tsx`):
  Objektnummer · Menge · Zustand (+ Standort, wo er zählt), Haarlinien statt Kästen. Die
  zwei fast gleichen Nachbauten in Bewegung und Aussondern sind entfallen, ebenso das Wort
  «Instanz» in jeder Zeile einer Instanz-Liste.
  (5) **Der Bestand ist eingeklappt** (#644): je Instanz eine Zeile (Nummer · Menge), die
  Stücke auf Klick – die Auskunft bleibt, die Liste wird wieder lesbar.
  (6) Kleineres: «Zielstandort» ohne «(optional)» (#641); die Beschriftungszeilen der
  Entwurfs-Knoten entfallen (#639/#640 – dass ein Auftrag oben hergibt und unten
  zurückbekommt, sagen seine Stelle im Bild und der Pfeil).

- **Die Materialkette schliesst den Prozess – und die Zusage wird bei der Freigabe
  festgelegt** (August 2026, Testnotizen #648–#651):
  (1) **Woher die Menge kam und wohin sie ging** (#650/#651, `orders._fill_material_chain`,
  `MaterialHandover`): «Es ist alles ein Prozess, ein durchgehender Weg – von der Erzeugung
  bis zum Lebensende.» Sichtbar war davon nur die Seitenspur eines **Unter**-Auftrags
  («hervorgegangen aus …»); ein regulärer Auftrag begann im Nichts und endete im Nichts –
  die Kette brach genau dort, wo sie am meisten trägt. Jetzt steht **vor** dem Startknoten
  der letzte Auftrag, der genau diese Instanzmenge hielt, **nach** der Zielflagge der
  nächste – je Menge einer, mit Stück-Nummern und dem Zustand von **damals**.
  **Kein neues Vokabular:** ein `OrderRefNode` (der Verweis auf einen anderen Auftrag,
  #438/#439) und dazwischen die Kante mit ihrer Materialzeile – dieselbe Grammatik wie der
  ganze Fluss, und **ohne** gestrichelte Linie (die gibt es hier nicht, #422/#429).
  **Gelesen wird um genau EINEN Schritt** aus dem Material-Journal (ADR 007): der genannte
  Auftrag zeigt seinerseits seinen Vorgänger, also ist die Kette bis zur «Geburt» begehbar,
  ohne dass eine Ansicht sie auf einmal zeigen müsste. Ohne Auftrag steht das **offene
  Ende** da (**Entstanden** · **Freier Bestand** · Verkauft/Verbaut/Verschrottet) – das ist
  die Darstellung der Geburt, ohne einen Datensatz zu erfinden, den es nicht gibt.
  **Drei Dinge, die dabei falsch waren und es nicht bleiben durften:** (a) *der freie
  Bestand ist kein Halter, aber eine Station* – lag die Menge zwischendurch am Lager, wird
  über sie hinweg weitergelesen (`_HOP_SCAN`), sonst begänne die Kette bei jedem Zugriff
  von vorn; (b) *eine Buchung kann MEHRERE Nachbarn haben* – wer 4 Stück ans Lager freigibt,
  verliert sie womöglich an zwei Aufträge, also ist es eine **Liste**, und jeder Eintrag
  trägt die Menge, die **wirklich** diesen Weg genommen hat (die erste Fassung schrieb dem
  ersten Nehmer die ganze freigegebene Menge zu – im Harness gefunden); (c) *die
  Stück-Nummern kommen von der **nehmenden** Seite* – sie weiss, welche sie sich geholt
  hat; die Freigabe ans Lager weiss nur, wie viele sie hinlegte. Deckt eine Buchung den
  Übergang nicht ganz ab, bleibt die Angabe **leer**: welche Nummern gemeint wären, ist
  dann offen, und geraten wird hier nicht.
  **Am Unter-Auftrag bleibt die Kette still** (`known`): Eltern und Rückweg stehen längst
  in der Seitenspur – genau das war der Grund, aus dem der Prozessbaum in #565 gestrichen
  wurde, und genau das kommt hier nicht zurück.
  (2) **Ein Auftrag legt seine Zusage bei der FREIGABE fest** (#649,
  `orders.release_order(..., backorder=False)` → `process.recompute_completion(settle=…)`):
  Gemeldet war ein Auftrag mit dem Modul «Aussondern · Sperren», das sich nicht ausführen
  liess. Ursache war eine **Sackgasse**: er war über mehr Menge eröffnet worden, als es je
  gab – niemand hielt sie, niemand beschaffte sie, also blieb die Fehlmenge für immer offen
  und der Prozess ruhte. Die automatische Auflösung (#556) gab es zwar, sie lief aber nur
  **nach einem abgeschlossenen Schritt** – und kein Schritt konnte abschliessen. Jetzt
  läuft sie **auch bei der Freigabe**: was nie da war, senkt das Soll auf das Machbare, und
  der Auftrag läuft. Dafür ist `recovery._lost_amounts` entfallen – die Unterscheidung
  «war da und ist weg» ↔ «war nie da» war genau die Bedingung, die den Fall aussperrte.
  **Die eine Ausnahme ist deklariert, nicht geraten**: der Shop-Verkauf «auf Bestellung»
  gibt frei, *bevor* `ensure_supply` den Nachschub dimensioniert – er sagt das ausdrücklich
  (`backorder=True`), sonst kürzte er sich selbst auf den Lagerbestand.
  **Neue Zeile in der Regel-Tabelle** (ADR 008): `regular-nie-gedeckt` – ein Fall, der in
  ihr fehlte, weil er bis dahin gar nicht auflösbar war.
  (3) **Die einzige Einstellung eines Moduls nimmt seine ganze Breite** (#648):
  «Verschrotten ↔ Sperren» ist die einzige Konfiguration des Aussondern-Moduls – als kleine
  Symbol-Pille am linken Rand las sie sich wie eine Nebensache. Sie nimmt jetzt die Breite
  ihrer Karte, und weil der Platz da ist, stehen die **Wörter** da statt im Hover (nimmt
  #633 zurück; dieselbe Begründung wie #636 – ein Symbol, das man raten muss, ist keines).
  Technisch **kein neuer Schalter**, sondern der Normalmodus von `IconSwitch`: ohne
  `symbolOnly`/`labelActiveOnly` spannt er und jede Option trägt `flex: 1`.
  Wächter: `test_frontend_mirrors.py: test_the_material_chain_closes_the_process`,
  `…_the_only_setting_of_a_module_takes_its_full_width`, `test_smoke.py:
  test_the_shortfall_decides_itself`, `tests/rules/table.py: regular-nie-gedeckt`. Gegen
  echtes PostgreSQL 16 verifiziert (Materialkette über zwei reguläre Aufträge + einen
  Aussonderungs-Auftrag 12/12; der gemeldete #649-Fall 6/6 – und **gegen die Bug-Form
  gegengeprüft**: ohne `settle` meldet er wieder «Der Prozess ruht …» am gesperrten Modul).

- **Testnotizen-Runde 45 (die Freigabe fragt nicht über sich selbst, Notizen #653–#659)**:
  (1) **Gleicher Prozess ⇒ gleicher Zustand** (#658, «fataler Fehler» – und das war es).
  Ein Erzeugungsauftrag über drei Stück, eines per Abweichung verschrottet, die anderen
  beiden identisch bis ans Ende bewegt: danach stand das eine auf «Freigegeben», das
  andere auf «Im Prozess». Entschieden hat allein die **Reihenfolge der Schleife**.
  Die Ursache ist eine Frage über sich selbst: `recompute_completion` setzt
  `order.status = "completed"` **vor** der Freigabe, `release_instances` fragt über
  `inventory.rest_owner` die Datenbank «läuft mein Erzeuger noch?», und die erste Buchung
  ruft `db.flush()` – ab dem zweiten Stück lautete die Antwort «nein», also hielt der
  Auftrag angeblich nichts mehr. Genau die Klasse aus #392/#390: *der Zustand, der
  entscheidet, wird vom entscheidenden Vorgang verändert.* Die Freigabe **sagt** ihre
  Zugehörigkeit jetzt, statt sie zu erfragen (`units.owned_by(..., inherits_rest=…)`):
  wer erzeugt hat, hält den unbeanspruchten Rest – und er ist gerade hier. Für fremde
  Instanzen (festes Subjekt) gilt die alte Regel unverändert.
  (2) **Freigegeben wird an der ZIELFLAGGE, nicht am letzten Modul** (#658, zweite Hälfte –
  vom Nutzer so formuliert): nach dem letzten Modul hat sich an den Stücken nichts geändert,
  also stehen dort **beide** noch «Im Prozess» (gelb); dass sie ihr Ziel erreicht haben und
  freigegeben sind, sagt die Materialkette **unter** der Flagge. Vorher zeigte die letzte
  Kante eines fertigen Auftrags den Stand NACH dem Abschluss – das Material wurde zwischen
  letztem Modul und Flagge grün, obwohl der Schritt daran nichts getan hat
  (`current_from = len(nodes) + 1`, also auch die letzte Kante eingefroren).
  (3) **Am Ziel steht, was es INS ZIEL geschafft hat** (#657): die Materialkette nannte
  auch den **eigenen Abzweig** als «Material weiter an …» – der steht aber längst als
  Teilung mitten im Prozess. Eigene Unter-Aufträge (Abweichung · Nachschub · Retoure ·
  Bereitstellung) bleiben darum aus der Kette, genau wie die Beziehungen, die schon in der
  Seitenspur stehen (#565). Im gleichen Zug trägt eine Übergabe **den Zustand NACH der
  Buchung** – in beide Richtungen derselbe Griff (`dst_*`): herein «so ist es angekommen»,
  hinaus «ins Ziel geschafft und freigegeben» bzw. «verschrottet»/«verkauft». Mit dem
  Quell-Topf stand am Ziel «Im Prozess», obwohl die Freigabe genau der Vorgang ist, den
  dieser Knoten meldet; `incoming_side` ist damit entfallen – **eine Regel weniger**.
  (4) **In einem Modul zählt WELCHE Instanz, nicht ihr Zustand** (#659): die Zeile eines
  Prozessschritts nennt Objektnummer · Menge (· Standort, wo er die Aussage des Schritts
  ist). Der Zustand steht direkt darüber im Fluss, in seiner Ampelfarbe – eine Badge je
  Zeile wiederholte ihn an der Stelle, an der er am wenigsten zählt.
  (5) **Kein Footer am Artikel** (#653, wie #140 am Auftrag): der Hinweis, warum noch nicht
  gespeichert wird, steht leise **in der Karte**, auf die er sich bezieht; ein echter Fehler
  in der Warnfarbe. Der Speicher-Status ist ohnehin der grüne Flash im Kopf, und verworfen
  wird durch Wegklicken (#389) – der «Abbrechen»-Knopf ist mit entfallen.
  (6) **Platzhalter nennen das Beispiel** (#655/#656): «z. B. 3x40x600» · «z. B. 2.5» –
  die Regel dahinter prüft ohnehin das Feld und meldet sie, wenn sie verletzt ist.
  (7) **«Zuerst die Spezifikation ausfüllen»** (#654): «Prozess zuerst wählen» stammte aus
  der Zeit des Prozess-Objekts (Migration 031) und nannte etwas, das es nicht mehr gibt.
  Wächter: `tests/rules/test_units.py: test_two_instances_of_one_order_end_in_the_same_state`
  (gegen die Bug-Form gegengeprüft), `test_frontend_mirrors.py:
  test_the_release_happens_at_the_goal_flag`, `…_a_module_row_shows_which_instance_not_its_state`,
  `…_the_material_chain_closes_the_process` (erweitert). Gegen echtes PostgreSQL 16
  verifiziert (der gemeldete Fall Schritt für Schritt, 7/7).

- **Ein Schritt ohne Material hat nichts zu tun – und der Auftrag arbeitet nur mit dem, was
  er hält** (August 2026, Testnotizen #652 · #660 · #662 · #663): Vier Notizen, zwei Wurzeln.
  (1) **«Nichts zu tun» ist nicht dasselbe wie «nicht getan»** (#652, vom Nutzer freigegeben).
  Nach dem Aussondern bleibt dem Auftrag nichts mehr; ein Modul danach wurde trotzdem
  «aktiv» und war eine **Sackgasse** – seine Ausführung wirft «Keine Instanzen vorhanden»,
  also konnte der Auftrag weder abschliessen noch enden (gemessen, nicht vermutet). Das
  Aussondern IST die Erledigung (#555), und ein Schritt, dessen Material der Auftrag nicht
  mehr hat, ist damit ebenfalls erledigt. **Nicht «Abgebrochen»:** abgebrochen heisst im
  System «das Ziel wurde NICHT erreicht, es geht woanders weiter» (`abort_into_id`) – beim
  Verschrotten wurde das Ziel erreicht, und es geht nirgends weiter.
  Der Riegel steht in der **Registry** (`EventType.needs_material`), nicht als Liste im
  Code: nur Schritte, die AN den Instanzen arbeiten (Datenerfassung · Bewegung · Aussondern ·
  Sperren · Verkauf), sind gemeint – wer Material **hereinbringt** (Beschaffung, Ressource)
  oder keins braucht (Dokument), bleibt unberührt, sonst wäre ein reiner Beschaffungsauftrag
  sofort «fertig». Und gefragt wird nur, wenn der Auftrag je Instanzen hatte.
  *Nicht geändert (und vom Nutzer bestätigt): die dünne Linie unterhalb der Teilung ist
  ehrlich – dort fliesst nichts mehr; und die Spiegelung Abzweig ↔ Unter-Auftrag stimmt
  (gemessen: gleiche Schritte, gleiches Material, gleiche Linienstärke).*
  (2) **Der Auftrag arbeitet nur mit dem, was er HÄLT** (#662/#663): `held_quantity` liess
  den unbeanspruchten Rest gelten, auch wenn das Stück längst **freigegeben** war – ein
  Abzweig übernimmt eines von zwei Stück, gibt es ans Lager, und der Eltern zählte es
  wieder zu sich. Folgen: «2 von 2 Stück prüfen», obwohl nur eines vor der Haustüre stand,
  und der Bewegungsschritt **bewegte das fremde Stück mit**. Freigegeben heisst frei –
  dieselbe Regel wie bei den Stücken (`units.owned_by`, #573/#577/#625), hier als Menge;
  `order_active_instances` liest sie mit, damit «woran arbeitet dieser Auftrag» und «was
  gehört ihm» dieselbe Antwort haben.
  (3) **Ein gekappter Abzweig hält die Achse nicht auf** (#660): `node_done` behandelte
  jeden offenen Ast als Blocker. Ein gekappter kommt aber nie zurück – der Eltern hat sein
  Soll längst reduziert und läuft weiter, sein nächstes Modul ist «an der Reihe». Linie und
  Modul-Zustand sagten zwei verschiedene Dinge über dieselbe Stelle; jetzt hält nur auf, wer
  noch etwas zurückgibt (`returns_material`).
  (4) #661 war die Bestätigung von (3) aus dem abgeschlossenen Zustand – keine Änderung.
  Wächter: `tests/rules/test_units.py: test_a_step_without_material_has_nothing_to_do`,
  `…_a_cut_branch_does_not_hold_up_the_parent` – **jeder gegen seine Bug-Form
  gegengeprüft** (ohne Fix meldet die Datei genau die gemeldeten Symptome: «2 statt 1»,
  dünne Linie am aktiven Modul, Auftrag bleibt `released`). Gegen echtes PostgreSQL 16
  verifiziert (7/7 die gemeldete Abfolge Schritt für Schritt).

- **Terminal wird eine Instanz an EINER Stelle – über ihre Stücke** (August 2026,
  Testnotizen #664–#668):
  (1) **Verschrottet heisst überall verschrottet** (#666, der eigentliche Fehler). Drei
  Stellen setzten `inst.disposition` direkt auf einen Endzustand und liessen die Karte
  unberührt: Verschrotten (ganze Instanz), Verkauf (Made-to-Order) und Verbrauch. Der
  Datensatz sagte «verschrottet», das Stück galt weiter als freigegeben – die
  Instanz-Ansicht und der Artikel-Bestand zeigten es als verfügbar. **Und es war keine
  Anzeigefrage:** `inventory.ready_qty` gab es weiter an FIFO heraus; nur die SQL-Bedingung
  `in_stock_clauses` filtert über den Skalar, darum sah es «im Hintergrund» richtig aus.
  Der robuste Riegel ist nicht ein vierter Einzelfix, sondern die Regel selbst: es gibt
  genau EINEN Weg terminal zu werden, und er geht über die Stücke (`units.drop` bzw. neu
  `units.drop_all`) – der Instanz-Skalar ist die **Projektion** darüber (#604), nie eine
  Zuweisung. Ein **AST-Wächter** liest den Quelltext, damit keine vierte Stelle still
  dazukommt (`test_an_instance_becomes_terminal_at_exactly_one_place`).
  (2) **Ein Unter-Auftrag trägt gar keine Materialkette** (#667/#668): woher sein Material
  kommt und wohin es zurückgeht, steht als Herkunfts- und Rückweg-Knoten in der **linken
  Spur** – zweimal dieselbe Beziehung war schon der Grund, aus dem der Prozessbaum in #565
  gestrichen wurde. Schlimmer noch: die Kette nannte dort **fremde** Abzweige, durch die
  die Menge irgendwann einmal gelaufen war, und behauptete deren Zustand von damals falsch.
  Die Kette ist für den **regulären** Auftrag gebaut, der sonst im Nichts begänne; ein
  Unter-Auftrag beginnt nie im Nichts. *Nebenbei behoben:* eine **Selbst-Buchung**
  (verschrottet/verkauft im eigenen Topf) galt als eingehende Übergabe – ein Auftrag nannte
  damit sich selbst als Herkunft seines Materials.
  (3) **Auftrag und Menge stehen in EINER Zeile** (#665): als voller `OrderRefNode` war der
  Verweis lauter als der Prozess selbst, und dass die Materialpille darunter zu IHM gehört,
  musste man erst erschliessen. Jetzt zwei gleich leise Pillen nebeneinander (`OrderChip` +
  `FlowLots`) – die Zeile IST die Zuordnung.
  (4) **Im Hover steht nur noch der Standort – der von DAMALS** (#664). Er ist die einzige
  Angabe einer Materialzeile, die sich ändert, **ohne** dass eine Buchung entsteht (eine
  Bewegung verschiebt, sie bucht nicht um) – die Aufzeichnung dieser Wechsel gibt es aber
  längst: das **Audit-Log** (`instances`/`location`, alt → neu, mit Zeitstempel). Es wird
  nur **gelesen** (`_location_history`/`_location_at`, EINE Abfrage je Antwort), keine
  zweite Wahrheit angelegt; damit ist die Standort-Aussage einer Kante so ehrlich wie ihre
  Zustands-Aussage (#488). Artikel und Stück-Liste sind entfallen – mit einer einzigen
  Angabe braucht es auch keine Karten-Anatomie mehr (`LotFact` ist weg).
  (5) **Favicon**: die Marke steht als `src/app/icon.svg` im Browser-Tab (Next.js
  App-Router-Konvention, kein Link nötig); `public/brand/favicon.svg` war nirgends
  verdrahtet und trägt jetzt dasselbe Zeichen. Die `theme_color` des Manifests stand noch
  auf `#2563eb` – der abgelösten blauen Alt-Marke.
  Wächter: `tests/rules/test_units.py: test_an_instance_becomes_terminal_at_exactly_one_place`,
  `…_a_scrapped_piece_is_gone_everywhere` (gegen die Bug-Form gegengeprüft),
  `test_frontend_mirrors.py: test_the_material_chain_closes_the_process` (erweitert),
  `…_a_flow_lot_names_instance_article_location_and_quantity` (Hover). Gegen echtes
  PostgreSQL 16 verifiziert (Standort je Kante · Unter-Auftrag ohne Kette · verschrottetes
  Stück überall weg).

Nächste Aufgabe: **KI aktivieren** – `VERTEX_PROJECT_ID` (+ `roles/aiplatform.user` für den Cloud-Run-
Service-Account) setzen und Assistent/Schreibhilfe/Bild-KI in der Sandbox durchtesten (ADR 004);
Publishable Key (`pk_test_…`) in Admin → Systemkonfiguration hinterlegen + die
eingebettete Kasse/Warenkorb inkl. Mehrpositionen-Verkauf (Fehlbestand + Nachschub, Zahlungsart) in der
Sandbox testen (`docs/stripe-setup.md`); Retoure/Erstattung als Normalauftrag (verkaufte Instanzen unter
«Instanz wählen» → Bewegung zurück + Gutschrift im `sale`-Modul inkl. Stripe-Refund; Kulanz ohne Rücknahme)
in der Sandbox end-to-end prüfen; Abo-Mindestlaufzeit/
Kündigungs-Cooldown + Produktabo-Auto-Fulfillment (`invoice.paid`) in der Praxis prüfen;
Custom-Auftrag-UX verfeinern; Instanz = vollständige Ereignis-Historie; Scan-Quittierung im Wareneingang &
beim Verschrotten; E-Mail (Gmail API); Stripe Terminal für Vor-Ort-Zahlung (payment_method='terminal',
Phase 2+, aktuell nur vorgemerkt).

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
