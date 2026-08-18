# PROCESS_CORE — die Grundlogik des Prozesses

> **Verbindlich und systemweit.** Wer ein Prozessschrittmodul baut, hält sich hieran.
> Was hier nicht steht, ist nicht entschieden — und wird nicht erfunden.
>
> Stand: August 2026, nach dem Basis-Neuaufbau (Einzelinstanz-Modell), der Neuanlage des
> Datensatztyps «Auftrag» und den Entscheiden A1–A6. Die frühere Prozesslogik ist
> ersatzlos entfernt; nichts davon ist Vorlage.
>
> **Stand der Umsetzung:** §1–§12 sind **gebaut und im Browser durchgeprüft**. Das erste
> echte Prozessschrittmodul ist die **Datenerfassung** (§9); das frühere Testmodul ist
> ersatzlos entfallen.

---

## 1. Der Auftrag

Ein Auftrag hat **genau einen Anfang und genau ein Ende**. Dazwischen liegt eine
geordnete Folge von **Prozessschrittmodulen** — alles, was im Unternehmen getan wird.

```
        ┌──────────────────────────┐
        │  DEFINITION              │   welche Einzelinstanzen?
        └──────────────────────────┘
                    │
                  ( ▶ )  START      Freigegeben → Im Prozess
                    │
              [ Modul 1 ]
                    │
              [ Modul 2 ]
                    │
                   ...
                    │
                  ( ⚑ )  ENDE       Im Prozess → Freigegeben
```

Die einzelnen Module werden **einzeln definiert** und sind hier bewusst nicht
aufgezählt. Das erste wird die Datenerfassung sein.

---

## 2. Was sich bewegt: ausschliesslich Einzelinstanzen

Im Prozess bewegen sich **nur Einzelinstanzen** — nie ein Artikel, nie eine Instanz.
Artikel und Instanz sind Ordner; jede Ansicht auf ihrer Ebene ist Filterung oder
Summierung, nie eine eigene Datenquelle.

### 2.1 Die Definition steht vor dem Start

**Vor** dem Start-Symbol steht die Definition: mit welchen Einzelinstanzen dieser
Auftrag arbeitet. **Ohne Definition kein Start.**

Eine Definitionszeile beantwortet drei Fragen, **in dieser Reihenfolge**:

| # | Angabe | Regel |
|---|---|---|
| 1 | **Artikel** | Pflicht. Sperrt alles Weitere, bis er steht. |
| 2 | **Menge** | Ganzzahl ≥ 1. Referenziert **immer exakt Einzelinstanzen**. |
| 3 | **Herkunft** | `Neu` (wird erzeugt) oder `Lager` (bestehende Stücke). Pflicht. |

Die Reihenfolge ist nicht Geschmack: ohne Artikel ist die Menge nicht deutbar
(Einzelserialisierung oder Charge?), ohne Menge ist die Herkunft nicht entscheidbar
(welche Stücke denn?). Jedes Feld ist gesperrt, bis das davor beantwortet ist, und
nennt den Grund im Klartext.

**Harte Mengen-Invariante.** Menge N heisst: danach laufen **exakt N Einzelinstanzen**
im Prozess — nicht mehr, nicht weniger. Sie steht an einer Stelle
(`services/materialize.assert_quantity`) und wird bei der Freigabe zweimal gerufen: auf
dem *Plan* (reine Arithmetik, vor der ersten Objektnummer) und auf dem *Ergebnis*. Eine
Abweichung bricht die Transaktion ab.

#### Herkunft `Neu` — der Erzeugungsauftrag

- Der Prozess darunter ist die **Vorlage des Artikels** (§8.2), gespiegelt und bei der
  Freigabe als **Kopie** übernommen. Er ist hier nicht editierbar: ein Versionsstempel
  auf etwas, das man danach ändert, wäre eine Behauptung.
- Hat der Artikel keine Vorlage, ist `Neu` **nicht wählbar** — mit Klartext-Grund.
- Bei der Freigabe entstehen die Einzelinstanzen, Status `Freigegeben`, und passieren
  im selben Zug das Start-Objekt nach `Im Prozess`.

#### Herkunft `Lager` — bestehende Stücke

- Es werden **konkrete** Einzelinstanzen gewählt. **FIFO ist die Vorauswahl**, sichtbar
  und einzeln abwählbar — eine unsichtbare Automatik wäre hier das Schlimmste: man sähe
  erst nach der Freigabe, welche Stücke es getroffen hat.
- Der Prozess darunter ist **frei modellierbar**: was mit vorhandenem Material geschehen
  soll, weiss nur dieser eine Auftrag.
- **Hier entsteht nie eine neue Nummer.**
- Die Auswahl sperrt noch nichts; die Exklusivitätsprüfung greift bei der Freigabe (§3).

### 2.2 Wo Einzelinstanznummern entstehen

> **Neue Einzelinstanznummern entstehen ausschliesslich beim Freigeben eines Auftrags,
> und ausschliesslich für Definitionszeilen mit der Herkunft `Neu`.**

Kein Import, kein Direkteintrag, kein Modul. Die eine Erzeugungsstelle ist
`services/instances.create_instances`; ein Wächter hält fest, dass ausserhalb dieses
Moduls niemand einen Suffix vergibt.

**Wie die Menge auf Datensätze fällt, entscheidet die Serialisierung des Artikels** —
und zwar als **Zahlenpaar, nicht als zweiter Codepfad** (`materialize.plan`):

| Serialisierung | Menge 3 | Ergebnis |
|---|---|---|
| Einzelserialisierung | `(3, 1)` | 3 Instanzen mit je einer Einzelinstanz `…-1` |
| Charge | `(1, 3)` | 1 Instanz mit `…-1` `…-2` `…-3` |

In beiden Fällen ist das Produkt die Menge. Objektnummern kommen als Block aus der
**Sequence** (`object_id_seq`), nie aus `MAX(nummer)+1`; der Suffix läuft **je Instanz**,
monoton, ohne Wiederverwendung — eine gelöschte Einzelinstanz lässt keine nachrücken.

Nur die definierten Einzelinstanzen dürfen im Auftrag verarbeitet werden.

- Kein Nachschieben zur Laufzeit.
- Kein Ersetzen zur Laufzeit.
- Ein Verstoss ist ein **harter Fehler** (HTTP 409, benannte Ursache), kein Durchwinken.

Diese Härte ist der Grund, warum das Modell überhaupt neu gebaut wurde. Im
Vorgängersystem war die Menge eines Auftrags ein bewegliches Ziel: Anteile wurden
umgehängt, Reservierungen gekürzt, Ausleihen zurückgereicht. Jede dieser Bewegungen
war eine Stelle, an der zwei Aussagen über dasselbe Stück entstehen konnten. Eine
Definition, die nach der Freigabe nicht mehr wackelt, macht diese ganze Klasse von
Fehlern unmöglich — statt sie zu bewachen.

---

## 3. Exklusivität (A3, hart und systemweit)

> **Eine Einzelinstanz ist zu jedem Zeitpunkt in genau EINEM Auftrag aktiv.**

| Begriff | Bedeutung | Exklusiv? |
|---|---|---|
| **aktiv** | Das Stück befindet sich im Prozess eines freigegebenen Auftrags. | **ja** |
| **referenziert** | Historischer Verweis: abgeschlossener Auftrag, Ereignis-Log. | nein |

- Der Versuch, ein bereits aktives Stück in einem zweiten Auftrag zu definieren, ist ein
  **harter, sprechender Fehler** — er nennt das Stück und den Auftrag, in dem es aktiv
  ist. Kein stilles Überschreiben, kein Duplizieren.
- Die Regel wird **auf Datenbankebene** erzwungen, nicht nur in der Anwendungslogik.
  Sonst hebelt der erste Parallelzugriff sie aus (§10.2).
- **Folge, ausdrücklich gewollt: Reservierung, Anteil und Unterdeckung entfallen
  ersatzlos.** Nichts davon wird gebaut, auch nicht vorbereitend.
- Solange ein Stück in einem Auftrag steckt, ist es für jeden anderen tabu. **Es gibt
  keine Ausnahme** — auch der Abweichungsauftrag (§12) ist keine: er **entzieht** das
  Stück dem laufenden Auftrag, statt es ein zweites Mal aktiv zu machen.

### 3.1 Wann wird ein Stück wieder frei?

1. **Normalfall:** Ein Stück wird frei, sobald es **das Ende-Objekt passiert** hat — nicht
   erst, wenn der Auftrag abgeschlossen ist. Der Auftrag ist abgeschlossen, wenn alle
   seine Stücke das Ende passiert haben; das ist eine **Folge**, keine eigene Regel.
2. **Abbruch:** Jedes Stück, das beim Abbruch noch nicht am Ende ist, wird mit einem
   **eigenen Log-Eintrag** freigegeben (`Im Prozess → Freigegeben`, Grund: Abbruch). Kein
   stiller Statuswechsel — ein Abbruch ist ein Ereignis wie jedes andere.

---

## 4. Die Statusregel (Kern)

Für **jedes** Objekt im Prozess — Start, jedes Modul, Ende — ist definiert:

| | |
|---|---|
| **Vorher** | Welchen Status muss die Einzelinstanz haben, um eintreten zu dürfen? |
| **Nachher** | Welchen Status hat sie danach? |

```
Freigegeben ──▶ ( ▶ ) ──▶ Im Prozess ──▶ [ Modul A ] ──▶ Status X ──▶ ...
```

**Das Vorher/Nachher-Paar ist Pflichtbestandteil jeder Moduldefinition.** Ein Modul
ohne definierten Übergang ist nicht anlegbar — der Fehler kommt beim Anlegen, nicht
erst bei der Ausführung.

Passt der Ist-Status nicht zum Vorher-Status, ist das ein **sauberer Fehler** mit
Nennung von Stück, Ist-Status und erwartetem Status. Kein Durchwinken, kein
stillschweigendes Anpassen.

### 4.1 Start und Ende sind systemweit fest (A2)

| Objekt | Übergang |
|---|---|
| **Start** | `Freigegeben` → `Im Prozess` |
| **Ende** | `Im Prozess` → `Freigegeben` |

Beides ist **nicht je Auftrag einstellbar**. Damit ist die Kettenprüfung bei der
Freigabe verlässlich und nicht von Modelliersorgfalt abhängig.

### 4.2 Der Endzustand ist EIN Wert an EINER Stelle (A6)

Heute ist der Endzustand **immer** `Freigegeben` — ein Stück ist danach wieder
verfügbar. Es gibt genau einen Endzustand.

Für später ist offen gehalten, dass das letzte Modul mehrere Endzustände bestimmen
kann (verkauft, verbaut, ausgesondert …). **Konsequenz für heute:** der Endzustand wird
als **konfigurierbarer Wert des Ende-Objekts** modelliert, der auf `Freigegeben`
festgesetzt ist. Er darf **an keiner zweiten Stelle** hart codiert werden — sonst kostet
die Erweiterung einen Umbau statt einer Änderung.

Kein UI, keine Auswahllogik dafür. Der Wert existiert, er ist nur nicht wählbar.

**Der Ort ist `orders.end_status`.** Damit bleibt die Schrittliste rein (§10.1 hält Start
und Ende bewusst aus ihr heraus) und der Wert hat trotzdem genau eine Adresse. Die
Fachlogik **liest** ihn (`order.end_status`); sie schreibt ihn nirgends hin – ein Wächter
hält fest, dass `DEFAULT_END_STATUS` an genau einer Stelle vorkommt.

### 4.3 Die Kette muss schliessen

Beim Freigeben wird die Kette geprüft: das **Nachher** jedes Objekts muss das
**Vorher** des folgenden erfüllen. Eine Lücke ist ein Freigabe-Fehler, kein
Laufzeit-Problem.

Das ist der Unterschied zwischen einer Regel und einer Hoffnung: ein Prozess, der
freigegeben werden konnte, kann nicht mitten drin an einem Statuskonflikt hängen
bleiben.

### 4.4 Ein Vorgang ist EINE Instanz — und sie wird zuerst bestätigt

Bevor jemand an einem Modul arbeitet, muss feststehen, dass er **das richtige Ding vor
sich hat**. Also: erst die Instanz verifizieren, dann die Eingabe. Ohne Verifikation ist
sie **nicht möglich** — durchgesetzt an der einen Ausführungsstelle
(`process.confirm_step` → `_verified_instance`, 400), nicht als ausgegrautes Feld. Ein
Knopf, der nicht tut, was er verspricht, ist keine Sperre, sondern eine Bitte.

**Der Scan verifiziert die INSTANZ, nicht die Einzelinstanz.** Das ist keine
Vereinfachung, sondern die einzige Möglichkeit: das Etikett klebt am physischen Ding, und
eine Einzelinstanz zieht bewusst keine Objektnummer (§2.2) — es kann für sie gar kein
Etikett geben. Daraus fällt der Unterschied von selbst heraus:

| Serialisierung | Instanzen davor | Scans | Erfassungen |
|---|---|---|---|
| `batch`, 12 Stück | 1 | **1** | 1 |
| `unit`, 12 Stück | 12 | **12** | 12 |

Kein `if`, keine Abfrage nach der Serialisierung im Modul. Ein Bestätigen deckt genau die
Stücke **einer** Instanz ab; darum ist `confirm_step` seit dieser Runde ein **Teil**-
Abschluss und gibt zurück, was er bewirkt hat (`{moved, held, result}`).

**Die Tastatur ist die Alternative, nicht die Umgehung.** Wer die Kamera nicht nutzen
kann, tippt die Nummer — im selben Dialog. Auch das ist eine Bestätigung, und sie wird
als solche geloggt (`verification` ∈ `scan` | `manual` im `capture`-Ereignis). Ohne den
Vermerk wäre die Tastatur eine stille Umgehung statt einer protokollierten Alternative.

**Global, nicht modulspezifisch.** Ein künftiger Modultyp ohne physischen Bezug (ein
reiner Rechenschritt) schaltet sie mit `Module.requires_verification = False` ab — an
seiner Registry-Zeile, ohne dass die Ausführungsstelle eine Fallunterscheidung bekommt.

### 4.5 «Nicht bestanden» rückt nicht vor — und legt nichts an

Ergibt eine Erfassung ein negatives Urteil, passiert **dreierlei und nicht mehr**:

1. Die Erfassung ist geloggt und eingefroren (sie ist eine Tatsache, auch die schlechte).
2. **Nichts rückt vor** — die Stücke bleiben an diesem Modul stehen, sichtbar mit Grund.
3. Das System **bietet** den Folgeauftrag an, mit vorgewählten Stücken.

**Es gibt genau EINE Option, und das ist der Abweichungsauftrag** (Testnotiz #713).
Daneben stand einmal eine «100 %-Kontrolle» über den ungeprüften Rest. Sie war **kein
zweiter Mechanismus**, sondern derselbe: ein Abweichungsauftrag über die übrigen Stücke
mit der Stichprobe «alle». Zwei Wege zu demselben Ergebnis sind einer zu viel — und der
zweite war der schwächere, weil er die Stichprobe der Auflösung stillschweigend festlegte,
statt sie wählen zu lassen. Entfallen ist sie **ersatzlos**: der Knopf, die Gruppe `rest`
im Dienst und die im Endpunkt. Wer den Rest behandeln will, legt einen Auftrag an und
wählt ihn aus — der eine Weg, den es für alles gibt.

Es legt ihn **nicht** an. Ein automatischer Entwurf wäre ein Auftrag, den niemand
bestellt hat — und er zöge Stücke aus dem laufenden Auftrag, ohne dass jemand zugestimmt
hätte (§12.6a: die Auswahl nennt, wo sie zugreift). Angelegt wird er über **denselben**
Weg wie jeder Auftrag; die Vorauswahl ist der ganze Unterschied.

**Angehalten wird die ganze Instanz, nicht nur die Stichprobe.** Fällt die Stichprobe
durch, ist sie nicht mehr repräsentativ, und der ungeprüfte Rest ist verdächtig
(ISO 2859-1: Sortierprüfung). Ihn weiterlaufen zu lassen hiesse, ihn hinterher wieder
einzusammeln.

Auch das ist **global**: die Regel steht in `confirm_step`, nicht im Modul. Ein Modultyp
muss nur sagen, wie sein Urteil lautet (`CaptureType.verdict`).

**Der Haltezustand ist eine AUSKUNFT, keine Sperre — und darum hat er auch keinen
Schlüssel.** «Angehalten» heisst nicht, dass der Dienst die Eingabe verweigert; es heisst,
dass die Stücke stehen geblieben sind. `held_units` beantwortet die Frage «welche haben
zuletzt ein negatives Urteil?» und sonst nichts. Eine erneute Erfassung ist damit **immer**
möglich, und sie ist der eine Ausweg: das nächste Urteil ersetzt das letzte (§9.2 — was
erfasst wurde, hängt am Stück, und der Log behält beide).

Das ist keine Nachlässigkeit, sondern die Bedingung dafür, dass der Haltezustand kein
**toter Punkt** ist. Eine Sperre bräuchte einen Schlüssel; dieser Schlüssel wäre ein
zweiter Weg neben der Erfassung, und er müsste entscheiden, wer ihn drehen darf. Solange
das Urteil selbst der Ausweg ist, gibt es diese Frage nicht.

Daraus folgt eine harte Regel für die Oberfläche: **der Haltezustand steht NEBEN dem Weg
nach vorn, nie an seiner Stelle.** Ein Modul, das bei `held` das Formular und den
Scan-Knopf durch die Entscheidung ersetzt, erfindet eine Sperre, die es im Dienst nicht
gibt — und die erfundene Sperre hat keinen Schlüssel, weil der Dienst gar nicht weiss, dass
er einen ausgeben müsste. Der Auftrag steht dann für immer still, obwohl jeder
Backend-Aufruf ihn weiterbewegen würde. Wächter:
`test_capture_module.test_a_hold_is_never_a_dead_end` und
`test_frontend_mirrors.test_a_hold_is_shown_beside_the_way_forward_not_instead_of_it`.

### 4.6 Ein terminales Modul ist ein AUSGANG, kein Durchgang

Ein Modul kann das Stück aus dem Auftrag **hinausführen**, statt es weiterzureichen. Es
sagt das an seiner Registry-Zeile (`Module.terminal`), und daraus folgt alles Weitere —
ohne eine einzige Fallunterscheidung im Ablauf:

| Folge | warum |
|---|---|
| **Der Editor bietet dahinter nichts an** | die Modul-Palette steht *vor* dem Ende; wo es keines gibt, gibt es sie nicht. Ein Modul, das durch Umsortieren dahinter gerät, wird gemeldet (`lib/modules.chainProblems`) |
| **Hinter ihm steht kein Modul** (Freigabe-Fehler) | was dort ankommt, verlässt den Auftrag – das nächste Modul bekäme nie ein Stück, und eine tote Definition sieht aus wie ein Prozess |
| **Die Kette endet dort** | das Ende-Objekt dahinter zu verlangen wäre falsch: es kommt nie ein Stück an |
| **Das BILD endet dort** (`flow.build`) | kein `end`-Knoten; die ausgesonderten Stücke stehen auf der Kante, die aus dem Modul hinausführt |
| **Es passiert das Ende-Objekt nicht** (`_finish`) | es ist selbst eines |
| **Eine geplante Rückführung endet** | die Rückkehr hängt am Ende-Objekt – dorthin kommt das Stück nie |

**Warum das eine EIGENSCHAFT ist und keine Regel im Editor.** Es wird nicht dreimal
aufgeschrieben, sondern einmal deklariert und dreimal gelesen: der Editor blendet aus, die
Freigabe weist ab, das Bild endet. Der Editor allein wäre eine **Bitte** (eine fehlende
Schaltfläche hindert keinen API-Aufruf und keine Artikel-Vorlage); die Freigabe allein
liesse den Menschen modellieren, was nie laufen kann, und meldete es erst am Schluss. Und
das Bild ist keine Kosmetik: hängte es hinter den Ausgang ein Ende-Objekt, stünden die
ausgesonderten Stücke auf einer Kante, die niemand gegangen ist – die Invariantenprüfung
(§10) meldet das zu Recht. Ein neuer Modultyp mit `terminal = True` erbt alle drei
Wirkungen, ohne eine Zeile dafür.

**Die letzte Zeile ist der Kern und kostet keine Zeile Wartelogik.** Ein Quell-Auftrag
zählt seine Ausleihen über die **offene** Zugehörigkeit (`waiting_counts`,
`pending_returns`); das Aussondern schliesst sie (`_pass` mit `next_step_id=None`). Damit
wartet er nicht mehr, sein Modul ist nicht mehr gesperrt, und bleibt ihm nichts, ist sein
Ziel unerreichbar – **genau wie bei einer gekappten Rückführung**, nur ausgelöst durch die
Aussonderung statt bei der Definition.

`return_to_order_id` bleibt dabei **unangetastet**. Die Absicht «kehrt zurück» war da; sie
nachträglich zu löschen hiesse, die Vergangenheit umzuschreiben. Gezählt wird ohnehin
nicht sie, sondern die offene Zeile.

**Und der Auftragsstatus braucht keinen neuen Wert.** Die bestehende Regel (`_derive`)
trägt beide Fälle: wer noch etwas unterwegs oder angekommen hat, ist `Im Prozess` bzw.
`Abgeschlossen`; wem nichts bleibt, dessen Ziel ist unerreichbar → `Abgebrochen`. Ein
Auftrag, der aussondert, hat damit **getan, wozu er da war** (`Abgeschlossen`) – und der
Auftrag, dem die Stücke dadurch endgültig fehlen, ist `Abgebrochen`. Beides fällt heraus,
ohne dass jemand es deklariert.

---

## 5. Statuswerte (A1, A4)

### 5.1 Geschlossene Liste

Es gibt eine **geschlossene, systemweite** Statusliste. **Module wählen daraus aus, sie
erfinden nie eigene Werte.** Ein Modul mit unbekanntem Status ist nicht anlegbar.

- Technisch als **Enum/Referenztabelle**, nicht als Freitextfeld.
- Erweiterung der Liste ist ein bewusster Systemeingriff an **genau einer Stelle** im
  Code.

### 5.2 Die Werte

`backend/app/domain/statuses.py` ist die eine Quelle. Das Frontend **spiegelt sie nicht,
es bekommt sie**: `scripts/dump_statuses.py` schreibt `frontend/src/lib/status-catalog.ts`,
genau wie `api.ts` aus dem OpenAPI-Schema entsteht. Ein Spiegel, den ein Test vergleicht,
findet ein Auseinanderlaufen erst hinterher; eine generierte Datei kann gar nicht
abweichen.

**Ein Status trägt alles, was über ihn zu wissen ist** – in EINER Zeile: Beschriftung,
Ampelton, welche **Achsen** ihn tragen (Einzelinstanz · Auftrag · Artikel) und, für
Stücke, ob er zum **Bestand** oder zur **Historie** zählt. Alles Weitere ist abgeleitet:
Achsenlisten, Anzeige-Reihenfolge, Gruppierung im Bestand, Farbe, Frontend-Katalog.

| Wert | Farbe | Achsen | Bestand | Bedeutung |
|---|---|---|---|---|
| `Freigegeben` | Grün | Stück · Artikel | live | Einsatzbereit, in keinem laufenden Auftrag. Anfangs- **und** (heute einziger) regulärer Endzustand. |
| `Im Prozess` | Orange | Stück · Auftrag | live | Im Prozess genau eines freigegebenen Auftrags. |
| `Gesperrt` | Orange | Stück | live | Aus dem Verkehr gezogen, **physisch noch da**. Nicht einplanbar, solange die Sperre gilt – **aufhebbar**. |
| `Verschrottet` | Rot | Stück | history | Aus dem Verkehr gezogen und **physisch weg**. Endgültig. |
| `Abgeschlossen` | Grün | Auftrag | — | **Den definierten Weg zu Ende gegangen.** |
| `Abgebrochen` | Rot | Auftrag | — | Ziel nicht mehr erreichbar. |
| `Inaktiv` | Rot | Artikel | — | Ausser Betrieb, endgültig. |

**«Abgeschlossen» heisst nicht «hat das Ende-Objekt passiert».** Ein **Ausgang** (§4.6)
ist ebenfalls ein Ende: wer dort ausgesondert wird, ist seinen Weg zu Ende gegangen.
Das ist keine neue Regel, sondern die genauere Beschreibung der bestehenden – gezählt
wird «Zugehörigkeit geschlossen **und** vor keinem Modul mehr stehend»
(`process.order_statuses`), nie «am Ende-Objekt angekommen». Ein Abweichungsauftrag, der
verschrottet, ist damit **abgeschlossen** und braucht keinen vierten Wert; `Abgebrochen`
bleibt dem vorbehalten, dessen Stücke stehen bleiben, ohne irgendein Ende zu erreichen.

**«Gibt es einen Weg zurück?» ist eine Eigenschaft des Status, keine Farbfrage.** Die
Eigenschaft heisst `terminal` und beantwortet die stärkste Frage, die man an einen
Zustand stellen kann: *ist er endgültig?* Alles Weitere **folgt daraus**, statt daneben
zu stehen:

- **Wählbarkeit** (`is_selectable`) – aus einem Endzustand heraus gibt es nichts mehr zu
  tun, also nimmt ihn kein Auftrag auf (`process.release`, Auswahl-Liste in
  `routers/orders`). Das war einmal ein eigenes Feld `selectable`; zwei Felder für
  dieselbe Frage sind zwei Stellen, an denen sie verschieden beantwortet werden kann.
- die **Farbe** – was endgültig ist, ist rot; was aufhebbar ist, orange.
- der **Schutz in der Datenbank** – siehe §5.3.

Daraus fällt das **Zurückholen** von selbst heraus: ein gesperrtes Stück nimmt ein ganz
gewöhnlicher Auftrag auf, das Start-Objekt setzt es auf `Im Prozess` wie jedes andere.
**Das Greifen IST das Aufheben** – es braucht keinen zweiten Mechanismus und keinen
Endpunkt «entsperren». Ein verschrottetes wird abgewiesen: das Ding gibt es nicht mehr,
ein Auftrag darauf wäre ein Auftrag auf nichts.

**Nichts wird gelöscht.** Beide bleiben Datensätze und bleiben sichtbar – im Bestand als
eigenes Segment (gesperrt) bzw. im Historie-Block (verschrottet), am Stück mit Zeitpunkt,
Auftrag und Person aus dem Ereignis-Log.

**Eine fachliche Zuordnung gehört an den Status, nicht in die Ansicht, die sie braucht.**
«Zählt dieser Zustand zum aktuellen Bestand?» stand einmal als eigene Liste daneben
(`LIVE_UNIT_STATUSES`) – die Form, die man beim nächsten neuen Zustand vergisst: er wäre
stillschweigend als Bestand gezählt worden, weil «alles, was ein Stück tragen kann»
zufällig heute dasselbe ist. Jetzt ist es ein Feld, und sein **Fehlen ist ein Fehler beim
Start** (`_check`), kein stiller Standardwert. Zur Laufzeit reist die Antwort als
`StockState.stock` mit den Daten – die Oberfläche entscheidet nichts und meldet einen
Zustand ohne Zuordnung, statt ihn zu raten.

**Mehr nicht.** Die früher vorgeschlagenen Werte sind zurückgezogen, jeder mit Grund:

| zurückgezogen | Grund |
|---|---|
| `verfügbar` | wäre ein **zweites Wort für `Freigegeben`** — genau die Doppelung, die dieses System überall abbaut |
| `gebunden` | war der Reservierungs-Begriff. **A3 streicht Reservierung ersatzlos** — der Wert wäre vorbereitendes Bauen für etwas, das es nicht geben soll |
| `verbraucht` | Endzustand. **A6 sagt: heute genau einer** – und das Aussondern (§9.4) hat seine zwei eigenen, weil es sie wirklich braucht |

*`gesperrt` stand hier einmal als «erfunden, weil die Fehlerbehandlung nicht entschieden
ist». Sie ist es jetzt (§4.5), und das Aussondern-Modul (§9.4) braucht den Wert – er ist
damit kein Vorrat mehr, sondern die Aussage eines gebauten Vorgangs.*

**Eine frisch angelegte Einzelinstanz ist `Freigegeben`** (`INITIAL_UNIT_STATUS`): sie ist
einsatzbereit und in keinem Auftrag – genau das heisst das Wort. Der frühere Platzhalter
`new` aus dem Basis-Neuaufbau ist mit Migration `104` entfallen.

### 5.3 Ein Endzustand ist endgültig – und das steht in der Datenbank

Ein Zustand mit `terminal = True` wird **nicht verlassen**. Nicht «soll nicht», sondern
**kann nicht** – die Regel liegt so tief, dass niemand an ihr vorbeikommt:

| Ebene | Wo | Wofür |
|---|---|---|
| Die eine Schreibstelle | `process._pass` | jeder Statuswechsel der Prozesslogik (Start · Modul · Ende). Bricht mit **409 und einem Satz** ab, bevor etwas geschrieben ist. |
| Die **Auswahl** | `process.pick_problem` | ein Stück in einem Endzustand wird nirgends angeboten, nirgends vorgewählt, nirgends aufgenommen (siehe unten). |
| Die Tabelle selbst | Trigger `trg_instance_units_terminal` | **alles andere** – Reparaturskript, Migration, Sicherheitsnetz, `UPDATE` von Hand. |
| Der Abgleich | `flow._verify_history` | falls doch etwas vorbeikam: der Log sagt Endzustand, die Zeile sagt etwas anderes → als Problem im Bild. |

**Es gibt keine Umgehung.** Kein Parameter, kein Force-Flag, keine Administrator-Ausnahme.
Wer eine bräuchte, hat kein Sonderrecht, sondern ein Modellproblem: ein Zustand, den man
doch verlassen können muss, ist schlicht **nicht terminal** – und das ist eine Zeile im
`CATALOG`. Der Trigger wird aus genau dieser Liste erzeugt und bei **jedem Start**
nachgezogen (`main._ensure_columns`), damit die Datenbank von ihr nicht abweichen kann.

**Und «endgültig» heisst auch: unerreichbar.** Ein Stück in einem terminalen Zustand ist
für **jede weitere Prozessaktion** aus dem Spiel – kein Abweichungstrigger, keine
Vorselektion, keine Aufnahme in einen Auftrag. Alle drei Wirkungen kommen aus derselben
einen Frage (`process.pick_problem` → `is_terminal`), und keine davon zählt einen Status
auf:

| Wo | Wirkung |
|---|---|
| Auswahl-Liste (`unit_options`) | als **nicht verfügbar** ausgewiesen, mit Grund im Hover |
| Oberfläche (`isPickable`) | der Abweichungstrigger **erscheint gar nicht**; eine vorgewählte Nummer fällt aus der Auswahl |
| Entwurf (`orders.validate_draft`) | **nicht freigebbar**, und der Grund steht da |
| Freigabe (`process.release`) | 409 |

Vorher sagte nur die letzte nein – und zwar erst beim Klick. Das ist die unangenehmste
Form einer Regel: sichtbar erst, wenn man alles getan hat. **`Gesperrt` ist nicht
terminal** und bleibt greifbar: das Greifen IST das Aufheben (§5.2).

**Warum so tief, und nicht im Modul.** Der Schreiber, der wirklich Schaden anrichtet, ist
nicht der, an den man denkt. Eine Alt-Reparatur im Startvorgang setzte
`UPDATE instance_units SET status='freigegeben' WHERE status NOT IN ('freigegeben','im_prozess')`
– eine Liste aus einer Zeit, in der es nur diese beiden Zustände gab. Als `Gesperrt` und
`Verschrottet` dazukamen, wurde sie still falsch, und seither hat **jeder Start** jedes
ausgesonderte Stück zurückgesetzt. Über keinen Dienstpfad und in keiner einzelnen Anfrage
war das nachstellbar; eine Prüfung im Modul hätte nichts genützt. Die Lehre steht in der
Reparatur selbst: sie nimmt ihre Liste jetzt aus dem `CATALOG` und repariert nur, was er
**nicht kennt**.

### 5.4 Farbe

| Farbe | Bedeutung |
|---|---|
| **Grün** | Anfang / Ende |
| **Orange** | im Prozess |
| **Rot** | Problem |
| eigene Farbfamilie | Prozessmodule |

Farbe ist **an den Status gebunden, nie an die Position**. Es gibt **eine einzige
zentrale Zuordnung** Status → Farbe; keine Farblogik in einzelnen Komponenten. Sonst
skaliert die Darstellung nicht: derselbe Zustand sähe an zwei Stellen verschieden aus.

Prozessmodule tragen eine eigene, davon getrennte Farbfamilie — sie sind keine Zustände
und dürfen nicht wie welche aussehen.

---

## 6. Lebenszyklus des Auftrags

### 6.1 Entwurf

Klick auf «+» im Datensatzbereich öffnet einen Auftragsentwurf.

**Der Entwurf existiert NUR im UI.** Keine DB-Zeile, keine reservierte Objektnummer,
kein Autosave. Wird er verworfen, bleibt **keine Spur** zurück.

**Damit gibt es keinen gespeicherten Zustand «Entwurf».** Ein Auftrag existiert erst ab
der Freigabe; die Prozessmodellierung passiert im Browser, und `process_steps` entsteht
mit der Freigabe in derselben Transaktion. Einen «Speichern»-Pfad neben der Freigabe gibt
es nicht.

### 6.2 Freigabebedingungen (hart)

Der Auftrag kann **nicht** freigegeben werden, solange nicht **beides** erfüllt ist:

1. mindestens **eine Einzelinstanz** ist definiert
2. mindestens **ein Prozessschrittmodul** ist definiert

- Der Freigabe-Knopf im Kopf ist bis dahin **deaktiviert**.
- Er zeigt **im Klartext**, welche Bedingung noch fehlt. Kein stummes Nichts-Passiert.
- Die Prüfung liegt **zusätzlich serverseitig**. Eine deaktivierte Schaltfläche ist
  keine Absicherung, sondern eine Bitte.

Die eine Stelle dafür ist `services/orders.validate_draft` — sie ist bereits verdrahtet
und wird von Router **und** Oberfläche gelesen, damit es nie zwei Massstäbe gibt.

**Für den Artikel gilt dasselbe, Wort für Wort** (`services/articles.missing_for_release`):
er kann nicht freigegeben werden, solange nicht **beides** steht — alle Pflichtfelder der
Spezifikation **und** mindestens ein Prozessschrittmodul. Und weil ein Artikel erst mit
seiner Freigabe entsteht (§2.2), heisst das: bis dahin gibt es **keine Zeile und keine
Objektnummer**. Kein Autosave, kein Zwischenspeichern, kein Datensatz «Entwurf».

*Vorher war es anders, und das war ein Fehler:* das Formular speicherte, sobald die
Spezifikation stand. Es entstand ein Artikel mit Objektnummer, der nichts erzeugen
konnte, weil sein Prozess leer war — ein Datensatz, der eine Zusage macht, die er nicht
halten kann.

### 6.3 Was «Freigeben» auslöst — exakte Reihenfolge

Freigeben = den Prozess starten. Der Klick ist der Trigger.

| # | Schritt |
|---|---|
| 1 | **Definitionszeilen auflösen** (§2.1), Prozess bestimmen (Vorlage bei `Neu`, sonst der modellierte). |
| 2 | **Freigabebedingungen prüfen** (§6.2) + Statuskette (§4.3). Nicht erfüllt → Abbruch mit klarer Meldung. |
| 3 | **Exklusivitätsprüfung** (§3) für die `Lager`-Stücke. Verletzt → Abbruch, nichts wird angelegt. |
| 4 | **Mengen-Invariante auf dem Plan** (§2.1). Stimmt sie nicht → Abbruch. |
| 5 | **Datensatz anlegen**, Objektnummer vergeben. Definitionszeilen und Prozessschritte schreiben. |
| 6 | **Neue Einzelinstanzen erzeugen** (`Neu`-Zeilen) — die einzige Stelle im System, an der das geschieht (§2.2). |
| 7 | **Mengen-Invariante auf dem Ergebnis.** |
| 8 | **Workflow anstossen:** alle Stücke passieren das Start-Objekt und wechseln `Freigegeben` → `Im Prozess`. |
| 9 | **Ereignis loggen und einfrieren.** |
| 10 | Das **nachfolgende Prozessschrittmodul wird aktiv.** |

**Die Schritte 1–4 liegen alle vor Schritt 5 — mit Grund.** Ein abgebrochener
Freigabe-Versuch verbraucht damit **keine** Objektnummer, egal woran er scheitert.

Alle Schritte laufen als **eine Transaktion**. Bricht einer ab, bleibt nichts
Halbfertiges zurück — kein Auftrag ohne Prozess, keine Einzelinstanz in einem
Zwischenzustand.

**Die Prüfungen stehen vor der Nummernvergabe — mit Grund.**
`nextval` ist absichtlich **nicht** transaktional; sonst wäre es kein
nebenläufigkeitssicherer Zähler. Läge die Exklusivitätsprüfung hinter der Nummernvergabe,
verbrennte **jeder** Verstoss eine Objektnummer. So verbrennt keiner eine. Der partielle
Unique-Index bleibt das Netz für den echten Parallelfall; schlägt er zu, geht genau dann
eine Nummer verloren – der einzige Fall, in dem eine Lücke entsteht, und der seltenste.
Ein Wächter hält die Reihenfolge fest.

### 6.4 Nach der Freigabe

Die Prozessstruktur ist **eingefroren**. Nur noch Ausführung, keine Modellierung. Der
Übergang ist ein bewusster, einmaliger Akt und **nicht umkehrbar**: ein freigegebener
Prozess wird nicht wieder zum Entwurf. Was nicht mehr passt, wird abgebrochen, nicht
umgeschrieben.

### 6.5 Definitionen rasten ein (A5)

Eine einmal gesetzte Definition ist **nicht an Ort und Stelle editierbar**. Änderung
ausschliesslich durch **Löschen und Neuanlegen** des Moduls.

Damit gibt es keine schleichende Mutation, und der Ereignis-Log bleibt eindeutig: ein
Modul ist von seiner Anlage bis zu seiner Löschung dasselbe.

Nach der Freigabe ist auch das nicht mehr möglich — die Struktur ist eingefroren.

**Für die Liste der Einzelinstanzen gilt sie nicht** – dort ist «löschen und neu anlegen»
dasselbe wie «bearbeiten», die Regel liefe leer. Sie meint **Modul-Definitionen**: ein
Modul hat keinen Bearbeiten-Zustand, nur einen Papierkorb.

---

## 7. Richtung und Historie

### 7.1 Nur von oben nach unten

Einzelinstanzen wandern **ausschliesslich abwärts**. Kein Rücksprung, keine Schleife,
keine Wiederholung an Ort und Stelle.

Was schiefgeht, geht **seitlich** in einen Abweichungsauftrag und kommt an **genau der
Stelle** zurück, an der es ausgeschert ist — die Bewegung innerhalb eines Auftrags bleibt
damit abwärts (§12).

### 7.2 Geloggt und eingefroren

Beim Passieren eines Prozessobjekts wird bestätigt bzw. eingegeben. Daraus entsteht ein
Eintrag im **Ereignis-Log**:

- **append-only** — es gibt keinen Update- und keinen Delete-Pfad
- **unveränderlich** — nachträglich weder änderbar noch löschbar
- **vollständig** — wer, wann, welches Stück, welcher Übergang, welche Eingaben

Eine Korrektur ist ein **neuer Eintrag**, nie eine Änderung des alten. Was gemessen
wurde, wird nicht nachträglich schöngeschrieben.

### 7.3 Zwei Fragen, keine dritte

Das System beantwortet:

- **Was läuft jetzt?** — der Laufzeit-Zustand
- **Was ist passiert?** — das Ereignis-Log

Es beantwortet **nicht**: was passieren wird. Keine Vorhersage, keine Simulation, keine
Hochrechnung. Eine Kante unterhalb der aktuellen Stelle trägt keine Aussage über
Material, das sie noch nicht geführt hat.

### 7.4 Die Journey — ein Prozess, aufgeteilt in Aufträge

Eine Einzelinstanz läuft nacheinander durch viele Aufträge und ist immer in **genau
einem** aktiv (§3). Damit ist alles ein einziger langer Prozess; die Aufteilung in
Aufträge ist eine Sicht darauf, keine Unterbrechung. Die **Journey** setzt sie wieder
zusammen: über dem Start steht der Auftrag davor, unter dem Ende der danach.

**Abgeleitet, nicht gepflegt.** Es gibt keine Spalten `vorheriger_auftrag` /
`naechster_auftrag`. Solche Zeiger müssten bei jeder Freigabe mitgeschrieben werden und
laufen irgendwann auseinander — und dann ist die Journey unbrauchbar für genau das, was
sie belegen soll. Die Quelle ist der **Ereignis-Log** (§11.3): er hält je Statuswechsel
fest, welches Stück in welchem Auftrag war, und seine `id` ist die Zeitachse.

```
Vorgänger  = der Auftrag des letzten Ereignisses VOR dem ersten Ereignis
             dieses Stücks in diesem Auftrag
Nachfolger = der Auftrag des ersten Ereignisses NACH dem letzten
```

Beides ist damit lückenlos: was nicht im Log steht, ist nicht passiert.

Daraus fällt eine Regel heraus, die niemand schreiben muss: ein Nachbar erscheint erst,
**wenn es ihn wirklich gibt**. Ein Auftrag entsteht mit seiner Freigabe (§6.1) — vorher
schreibt er nichts in den Log, also kann er auch nicht als Nachbar auftauchen.

**Gruppiert, nicht aufgezählt.** Je Nachbar-Auftrag ein Verweis mit Stückzahl («aus
100000123 · 5000»). Dieselbe Entscheidung wie bei den Stück-Gruppen im Prozessbild
(§10.1): bei 5000 Stück lautet die Frage «wie viele kamen woher», nicht «welche». Wer die
einzelnen Nummern will, öffnet den genannten Auftrag.

**Kein Nachbar heisst: nichts.** Kein Platzhalter, keine Zeile «kein Vorgänger». Ein
Erzeugungsauftrag hat keinen — seine Stücke sind hier entstanden.

**Ein Index ist kein zweiter Datenbestand.** `process_events (instance_unit_id, id)`
macht «welcher Auftrag war vor bzw. nach diesem?» zu einem Sprung an die Nachbar-Zeile.
Er beschleunigt eine Frage; er beantwortet sie nicht. Zwei Abfragen je Auftrag,
unabhängig von der Stückzahl.

---

## 8. Wo der Prozess lebt

Der **Auftrag** ist der Ort, an dem Prozesse **ausgeführt und gemanagt** werden.
Definiert werden sie an genau zwei Orten — mit **identischer Darstellung**:

| Ort | Zweck | Ausführung möglich? |
|---|---|---|
| **Auftrag** | Konkreter Prozess für konkrete Einzelinstanzen | **ja** |
| **Artikel** | Erzeugungsprozess / Arbeitsplan als **Vorlage** | **nein** |

Beide benutzen **dieselben** Bauteile: `ProcessColumns` (Modus `definition`) und
`AddModule`. Der einzige Unterschied ist der **fehlende Definitionsbereich** über dem
Start: ein Artikel hat keine Einzelinstanzen, und welche durchlaufen, entscheidet
ausschliesslich der Auftrag.

### 8.1 Eine Komponente, zwei Modi

Die Prozessdarstellung ist **eine** wiederverwendbare Komponente mit zwei Modi:

| Modus | Zeigt | Erlaubt |
|---|---|---|
| `definition` | Start · Module · Ende | Modul hinzufügen, löschen, sortieren |
| `ausfuehrung` | dazu: Zustand je Objekt, aktuelle Stelle | nichts an der Struktur |

Zweimal bauen ist an dieser Stelle der teuerste Fehler. Beide Modi werden **schon im
Auftrag** gebraucht — der Entwurf ist `definition`, der freigegebene Auftrag ist
`ausfuehrung`. Der Artikel benutzt später nur den ersten; er ist damit **kein neuer
Fall**, sondern derselbe Modus an einem anderen Datensatz.

Die **Definitions-Liste der Einzelinstanzen** ist bewusst **nicht** Teil des Diagramms,
sondern ein Slot darüber: der Artikel hat keine Einzelinstanzen, und ein Diagramm, das
sie voraussetzt, wäre dort nicht wiederverwendbar.

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
`GET …/units?edge=…`). Vorher zählte die Pille aus dem Graph und das Dropdown holte «alle
Stücke an Schritt X»: an einem Punkt mit Teilung stand «1 Stk» und im Aufklappen zwei
Nummern. Zwei Fragen an dieselbe Sache laufen auseinander, sobald die Sache feiner wird.

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
Anfang des Bogens. Vorher lag davor noch ein gerades Stück auf der Achse – sichtbar als
überstehendes Endchen, das die Hauptlinie überlagerte.

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

Der frühere Takt (`2·BEND − 8`) liess davon **einen** Pixel: rechnerisch
überschneidungsfrei, im Bild eine einzige Linie (gemessen: 1,6 px Abstand über 172 px
gemeinsame Länge). Sichtbar wurde es dort, wo nichts die beiden Punkte auseinanderzieht —
in der schmalen Nachbarspalte, nicht in der Mitte. Zwei Rhythmen hiessen darum: in einer
der beiden Ansichten stimmt es, in der anderen nicht.

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

Drei Anläufe stehen dahinter, und der Unterschied ist jedes Mal, *wo* die Entscheidung
sitzt: **neben der Stückauswahl** (die Aussage stand woanders als ihre Wirkung) · als
**Ersatz-Knoten mit eigener Linie** (zwei Rückweg-Linien für **eine** Entscheidung, und
die zweite war die erfundene) · als **Klick auf die ganze Nachbarspalte** (kein
Bedienelement, sondern eine Fläche ohne Aufforderung — man sieht ihr nicht an, dass sie
etwas tut, und trifft sie versehentlich).

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

### 8.2 Artikel-Reiter «Erzeugungsprozess» — die Vorlage

Neben «Spezifikation» trägt der Artikel den Reiter «Erzeugungsprozess»:

- Inhalt: **dieselbe** Darstellung wie im Auftrag (`ProcessColumns`, Modus `definition`)
  und **derselbe** Modul-Editor. Kein Nachbau — der Schnitt aus §8.1 hat gehalten.
- Dort wird **ausschliesslich der Prozess definiert**, sonst nichts.
- **Kein Anstossen von Prozessen, keine Einzelinstanzen, keine Ausführung.** Das ist
  keine bewachte Regel, sondern eine fehlende Tür: die Vorlage liegt in einer eigenen
  Tabelle (`article_process_steps`), und es gibt keinen Endpunkt, der sie ausführt.
- Sie friert mit der Artikel-Freigabe ein (`status != 'draft'` ⇒ read-only).

**Kopie, nicht Verweis.** Bei der Freigabe eines Erzeugungsauftrags wird die Liste in
`process_steps` **kopiert** und mit `Article.process_version` gestempelt
(`process_steps.source_article_id`/`source_version`). Ein Verweis hiesse, dass eine
spätere Artikeländerung laufende Aufträge rückwirkend umschreibt — das widerspricht
«eingefroren» (§6.4).

*Zum Namen: «Erzeugungsprozess» statt «Prozess», weil er sagt, wofür der Prozess da ist
— wie ein Stück entsteht — und weil damit Platz bleibt, falls ein Artikel später eine
zweite Art Vorlage trägt. «Prozess» wäre der Behälter, nicht die Sache.*

---

## 9. Die Prozessschrittmodule

Es gibt heute **drei**: die **Datenerfassung** (§9.1–§9.3), das **Aussondern** (§9.4) und
den **Verbrauch** (§9.6). Das frühere Testmodul war ein Testvehikel für den Mechanismus
und ist **ersatzlos entfallen** — den Mechanismus gibt es jetzt echt.

**Was alle drei gemeinsam haben, steht nicht bei ihnen**, sondern im Rahmen: der Halt bei
«nicht bestanden» (§4.5), die Verifikation vor der Eingabe (§4.4), die Stichprobe (§9.3)
— und das **Protokoll** (§9.7). Ein vierter Modultyp erbt sie ohne eine eigene Zeile.

### 9.0 Das Modul «Datenerfassung»

Zweck: im Prozess laufend Daten erfassen und kontrollieren (Richtung Qualitätssicherung).

| | |
|---|---|
| Übergang | **Durchläufer**: `Im Prozess` → `Im Prozess`, **fest verdrahtet** (`domain/modules`). Es misst — es verändert den Zustand des Stücks nicht. Passt der Ist-Status nicht: sauberer Fehler. |
| Anlegen | **Kein Name** (er steht im Typ, #682) · **Stichprobe** (§9.3) · **Erfassungspunkte**: je Punkt Bezeichnung und Typ. Mindestens einer — ein Modul ohne Punkt stünde im Prozess und hätte nichts zu tun. **Alles, was angelegt ist, ist Pflicht**; ein «optional»-Häkchen gibt es nicht mehr. |
| Laufzeit | Eine Zeile **je Instanz**, die davorsteht (§4.4) – mit **Vorschau, bevor gescannt wird**: Objektnummer, Artikel, Umfang («3 von 10 Stück erfassen · 7 laufen ohne Erfassung durch») und **was** erfasst wird. Je Instanz ein eigener Scan-Knopf; der Sammel-Knopf bleibt. |
| **«Bestätigen»** | Instanz verifiziert? (§4.4, sonst 400) · **je gezogener Einzelinstanz ein Wertesatz** (§9.5) · alle Punkte erfasst? (offen → Fehler, der sie **benennt**) · erfassen · Urteil **je Stück** · **bestanden**: Nachher-Status setzen, Ereignis loggen, Stücke rücken vor — **ein einziges «nicht bestanden»**: §4.5. |

**Kein Status-Feld beim Anlegen.** Der Übergang gehört zum Modultyp; zwei Auswahlen
hätten eine Entscheidung angeboten, deren einzige richtige Antwort schon feststand.

### 9.1 Die Erfassungspunkt-Typen — eine geschlossene Liste aus Bausteinen

| Typ | Erfassung | Urteil? |
|---|---|---|
| `text` | Freitext | nein |
| `bool` | Ja/Nein (Daumen hoch/runter) | **ja** |
| `photo` | **genau eine Aufnahme, über die Kamera** (kein Upload) | nein |
| `signature` | handschriftlich | nein |
| `measure` | Soll-Ist-Vergleich (Sollwert **Pflicht**, Toleranz optional) | **ja** |

**Das Bild entsteht in der Kamera, nicht im Dateidialog.** Eine Datei aus der Galerie
belegt nichts über *diesen* Vorgang; sie belegt nur, dass es irgendwann eine Datei gab.
Ein Nachweis, der auf **beide** Arten entstehen kann, ist hinterher keiner — man sieht ihm
nicht an, welche der beiden es war. Der Upload ist darum ersatzlos entfallen, nicht
ausgeblendet, und die Regel steht serverseitig (`Photo.missing`).
**Genau eine Aufnahme je Einzelinstanz**, und nicht optional: bei mehreren bliebe offen,
welche die gemeinte ist; bei keiner wäre der Punkt ein Vermerk statt eines Belegs. Neu
aufnehmen geht (das verwirft die alte) — *sammeln* nicht.

*Ein Typ **«Objekt scannen»** hat existiert und ist ersatzlos entfernt (Testnotiz #719).
Er war zugleich der einzige Nachweis für **Werkzeug und Prüfmittel**; dass es diesen
Nachweis damit nicht mehr gibt, steht als bewusst offener Punkt in `SYSTEM_LOGIC.md` §5.9
— nicht stillschweigend gestrichen.*

Geschlossen wie die Statuswerte (§5.1) — aber ein Typ ist nicht nur ein Wort, sondern
**Verhalten**: prüfen, wissen was fehlt, bewerten. Darum ist jeder Typ eine eigene Datei
mit einer eigenen Klasse (`domain/capture_types/`), und die Registry findet sie selbst
(`pkgutil`). **Ein sechster Typ ist eine neue Datei, sonst nichts** — keine Aufzählung,
die man vergisst, und keine `if type == …`-Kette, in der man eine von drei Stellen
übersieht.

*«Nicht angetippt» ist bei `bool` nicht dasselbe wie «nein»* — sonst zählte ein
übersehener Pflichtpunkt als bewusstes «schlecht».

### 9.2 Was erfasst wurde, hängt am Stück

Eine Erfassung ist eine Zeile in `captures`, mit Fremdschlüssel auf die **Einzelinstanz**
— und auf Auftrag und Modul, aus denen sie stammt. Es gibt **keinen** Endpunkt, der eine
Erfassung ohne Modul schreibt: erfasst wird, wenn ein Stück davorsteht und jemand
bestätigt. Gelesen wird frei (Instanz-Detail, Reiter «Datenerfassung»); geändert nie.

Ist es das **letzte** Modul, passiert das Stück im selben Zug das Ende-Objekt und wird
frei (§3.1).

**Was ein «nicht bestanden» auslöst, steht in §4.5** — es ist keine Modulregel, sondern
eine Prozessregel, und jedes künftige Modul erbt sie.

### 9.3 Die Stichprobe — EINE Zahl: der Anteil an der Gesamtmenge

Nicht jede Prüfung geht über alle Stücke. Die Regel steht in der **Definition**
(`domain/sampling.py`), gezogen wird sie zur **Laufzeit**. Sie ist **eine Angabe**, und
zwar ein Anteil in Prozent; die Kurzwege sind Werte derselben Zahl, keine eigenen Modi:

| Kurzweg | Anteil |
|---|---|
| **alle** | 100 % — Vorgabe: wer nichts sagt, prüft alles. |
| **Hälfte** | 50 % |
| **Viertel** | 25 % |
| **Anteil** | frei getippt, 1–100 % |

Drei Entscheidungen, jede an einer Stelle:

**Die Bezugsgrösse ist die GESAMTMENGE.** Ein Modul steht im Prozess und sieht, was
davorsteht: die Summe aller Einzelinstanzen dieses Auftrags. Eine Regel «je Instanz» wäre
eine Aussage über etwas, das an dieser Stelle niemand fragt — bei drei Chargen ergäbe
«10 %» dreimal eine eigene Ziehung, und die Zahl auf dem Bildschirm stimmte mit keiner
davon überein. **Aufgerundet, mindestens eines, höchstens alle**: «0 von 5» ist keine
Prüfung, sondern ihr Ausfall, und «12 von 5» keine Menge. Beide Grenzen sind die
konservative Richtung — im Zweifel wird mehr geprüft, nicht weniger.

**Gezogen wird, wenn das Modul ERREICHT wird** — nicht bei der Freigabe und nicht je
Welle. Vorher steht die Menge nicht fest: eine Abweichung kann Stücke entzogen haben. Und
die Stücke kommen in **Wellen** an (ein Vorgang ist eine Instanz, §4.4) — zöge man je
Welle, wäre «die Hälfte» in Wahrheit «die Hälfte aus jeder Kiste», also wieder die Regel
je Instanz. `sampling.ensure` zieht darum **einmal je Modul**, über den vollen Bestand
des Auftrags, und ist **idempotent** je Modul.

**Zufällig, aber eingefroren.** Wer gezogen wurde, entscheidet `random.sample` über die
nach id sortierte Menge — und das Ergebnis steht als `sample`-Ereignis im Log
(§11.3, append-only). Damit ist die Auswahl **nachweisbar** und ändert sich nicht mehr,
wenn jemand die Seite neu lädt. Eine deterministische Ableitung (jedes n-te Stück) wäre
vorhersagbar und damit als Stichprobe wertlos.

**Der Rest läuft ohne Erfassung durch — sichtbar.** Das steht in der Zeile («nicht
gezogen, läuft ohne Erfassung durch») und ist keine stille Auslassung. Bestätigt wird für
die gezogenen Stücke; vorgerückt wird die **ganze** Instanz.

**Und die Zahl der SCANS folgt der Ziehung, nicht umgekehrt** (Testnotiz #714). Die
Reihenfolge stand einmal auf dem Kopf: jede wartende Instanz wurde zum Scan angeboten,
und erst danach entschied die Ziehung, ob es dort etwas zu erfassen gab. Bei zwei
Instanzen und 50 % waren das zwei Scans für **eine** Erfassung; der zweite bestätigte
nichts — er war nur der Weg, das ungezogene Stück weiterzubewegen.

| ergibt sich aus | |
|---|---|
| **Zahl der Erfassungen** | Einzelinstanzen in der Stichprobe |
| **Zahl der Scans** | **Instanzen**, zu denen diese gehören |

Bewegt wird das Ungezogene darum vom Dienst (`process._run_through`) — und zwar **erst,
wenn die Stichprobe dieses Moduls durch und bestanden ist** (`_sample_cleared`), nicht
schon bei der Ankunft. Das ist keine Bequemlichkeit, sondern §4.5: fällt die Stichprobe
durch, ist der ungeprüfte Rest verdächtig (ISO 2859-1) und darf den Betrieb nicht längst
verlassen haben. Ein Modul **ohne** Erfassungspunkte ist damit nie «durch» — beim
Aussondern *ist* der Scan die Bestätigung, und die kann niemand einsparen. Das folgt aus
der Bedingung, es steht nicht als Abfrage nach dem Modultyp daneben.

### 9.4 Das Modul «Aussondern» — verschrotten oder sperren

Es zieht Einzelinstanzen **aus dem Verkehr**. Zwei Fälle, **ein** Modul:

| Ausprägung | Zustand danach | physisch | Weg zurück |
|---|---|---|---|
| **Verschrotten** | `Verschrottet` | weg | nein, endgültig |
| **Sperren** | `Gesperrt` | **weiterhin da** | ja – ein Auftrag greift es (§5.2) |

Sie tun dasselbe: das Stück verlässt den Auftrag, die Reise endet hier. Der einzige
Unterschied ist der Zielzustand – also ist es ein **Parameter**, kein zweites Modul.
Gewählt wird er bei der Definition (`config.mode`); den **Status leitet das Modul ab**
(`Module.status_after_for`), es gibt kein Status-Dropdown. Das ist der Unterschied
zwischen «welchen Zustand willst du?» (eine Eingabe, die man falsch ausfüllen kann) und
«was soll passieren?» (eine fachliche Wahl, aus der der Zustand **folgt**).

| | |
|---|---|
| Übergang | `Im Prozess` → `Verschrottet` bzw. `Gesperrt`. **Terminal** (§4.6): das Stück verlässt den Auftrag. |
| Anlegen | **Zwei** Angaben, beide Pflicht: die Ausprägung und der **Grund**. Keine Erfassungspunkte, keine Stichprobe. |
| Laufzeit | Eine Zeile je Instanz (§4.4) – dieselbe wie überall, inklusive Scan-Pflicht. |
| **Ausführen** | Verifizieren · Zustand setzen · loggen · das Stück verlässt den Auftrag. **Nichts zu erfassen** – der Grund steht in der Definition. |

**Teilmengen gibt es hier nicht.** Was am Modul ankommt, wird ausgesondert – ohne Auswahl
und ohne Stichprobenmechanismus. Wer nur einen Teil meint, gibt nur diesen Teil in den
Auftrag; eine zweite Auswahl daneben wäre ein zweiter Weg zur selben Entscheidung.

**Der Grund ist Pflicht — und er wird beim MODELLIEREN gegeben.** Warum an dieser Stelle
ausgesondert wird, ist eine Eigenschaft des Ablaufs («Ausschuss aus der Sichtprüfung») und
lautet bei jedem Stück gleich; am Band wäre es ein Feld, das immer dasselbe aufnimmt —
eine Erfassung ohne Erkenntnis. Ohne Grund ist das Modul **nicht anlegbar**: eine
Aussonderung, deren Anlass später niemand mehr kennt, ist ein Loch im Nachweis. Er gilt
für **beide** Ausprägungen — beim Sperren, weil sonst niemand weiss, ob man sie aufheben
darf; beim Verschrotten, weil es endgültig ist und die Frage «warum» dann gar nicht mehr
gestellt werden kann.

*Ein Erfassungspunkt ist er damit **nicht** mehr: das Modul erfasst zur Laufzeit gar
nichts, der Scan ist die Bestätigung. Er steht in der Definition (`config.reason`) und
reist als `ProcessStepResponse.reason` an die Ausführungsstelle – als Auskunft, nicht als
Eingabefeld.*

---

### 9.5 Der Scan gilt der Instanz, die Erfassung der Einzelinstanz

> **Das sind zwei verschiedene Dinge und dürfen nie gekoppelt sein.**

Der **Scan** ist eine Aussage über das physische Ding: das Etikett klebt an der Instanz,
eine Einzelinstanz zieht bewusst keine Objektnummer (§4.4). Eine **Messung** ist eine
Aussage über **ein Stück** – zwei Schrauben aus derselben Charge haben zwei Durchmesser.

Daraus folgt die Zahl, und zwar aus der **Ziehung**, nie aus der Zahl der Scans:

| Lage | Scans | Erfassungen |
|---|---|---|
| Charge über 2, Stichprobe «alle» | 1 | **2** |
| Charge über 6000, Stichprobe ¼ | 1 | **1500** |
| Einzelserialisierung 3, «alle» | 3 | 3 |

Vorher stand hier **ein** Wertesatz je Bestätigung, kopiert auf jedes gezogene Stück. Das
war nicht bloss unbequem – es war eine **Behauptung**: zwei Zeilen, gemessen eine. Ein
Nachweis mit mehr Zeilen als Messungen ist keiner.

**Die Nutzlast ist darum zweistufig**: Nummer der Einzelinstanz → (Punkt → Wert). Der
Server verlangt **Deckung in beide Richtungen** (`process._captures_for`) – ein Satz für
ein nicht gezogenes Stück ist ein Nachweis über etwas, das hier nie geprüft werden
sollte; ein fehlender ist eine Lücke, die hinterher aussieht wie «durchgelaufen, nichts
gemessen».

**Das Urteil hängt am Stück**, der Halt an der Instanz: jede Zeile trägt ihr eigenes
Ergebnis; fällt **eines** durch, bleibt die ganze Instanz stehen (§4.5) – eine
durchgefallene Stichprobe ist nicht mehr repräsentativ.

**Und das gilt bis in den Log hinein.** Das `capture`-Ereignis (§11.3) trägt je Stück
sein **eigenes** Ergebnis, nicht das der Bestätigung. Der Unterschied fällt erst auf,
wenn er zählt: bestanden 4 von 5 Stück und fällt eines durch, ist die Bestätigung als
Ganzes «nicht bestanden» – schrieb der Log diesen einen Wert auf alle fünf Zeilen, waren
vier davon **falsch**, und aus dem Nachweis liess sich hinterher nicht mehr lesen, welches
Stück das schlechte war. Der Halt gehört der Instanz, das Urteil dem Stück; wer beides in
dasselbe Feld schreibt, verliert das zweite.

**Welche Stücke gezogen sind, kommt erst auf Klick** (`…/steps/{id}/hold?group=sample`) –
dieselbe Auskunft, aus der auch die Vorauswahl der Entscheidung kommt. Bei 1500 gezogenen
Stücken darf diese Liste nicht in jeder Auftrags-Antwort mitreisen; für die **Vorschau**
genügen die Zahlen aus `step_work`.

### 9.6 Das Modul «Verbrauch» — Montage und Materialverbrauch

> **Der Zwilling des Aussonderns.** Beide führen ein Stück aus dem Kreislauf; der
> Unterschied ist, was aus ihm geworden ist: `Verschrottet` heisst «gibt es nicht mehr»,
> `Verbaut` heisst «steckt jetzt in etwas anderem».

**Die Stückliste ist die Konfiguration**: je Zeile ein **Artikel** und eine Menge **pro
Einzelinstanz** («4× Schraube M6 je Getriebe»). Artikel und nicht Definitionszeilen –
dasselbe Modul wird auch in der Artikel-Vorlage definiert, und dort gibt es noch keine
Zeilen. Gerechnet wird beim **Erreichen** (3 Getriebe ⇒ 12 Schrauben), nicht beim
Definieren: wie viele Produkte ankommen, steht dann noch gar nicht fest.

Im Editor ist es **dieselbe Komponente wie der Bedarf am Auftragsanfang**
(`DefinitionLines`, `perUnit`), nur mit zwei Fragen weniger. Die *Herkunft* entfällt –
eine Stückliste erzeugt nichts. Und die *konkreten Stücke* ebenso, und zwar nicht aus
Bequemlichkeit: ein Modul ist eine **Vorlage**, es läuft je Auftrag und je Produkt-Stück
erneut; ein hier festgenageltes Stück wäre nach dem ersten Mal verbraucht. Gewählt wird
beim Ausführen, wo es eine echte Wahl ist.

#### Gebunden wird beim Erreichen — der zweite Eintrittspunkt

Bis hierher hing der Eintritt **fest am Start-Objekt**: `release` legte die
Zugehörigkeiten an und schrieb den `start`-Eintrag, und es gab keine zweite Stelle, die
das konnte. Eine Komponente, die schon dort gebunden würde, wäre für jeden anderen
Auftrag gesperrt, solange die Montage läuft – obwohl sie im Regal liegt. Der Statusweg
lautet darum:

```
Freigegeben ──(Scan)──▶ Im Prozess ──(Bestätigen)──▶ Verbaut
```

Beide Übergänge sind **eigene Einträge im Log**, geschrieben von derselben Stelle wie
jeder andere (`process._enter_at_step` → `_pass`). Verallgemeinert wurde der **Punkt**,
nicht der Mechanismus: dieselbe Zeile in `order_units`, dasselbe `start`-Ereignis,
dieselbe Exklusivität. Nur die Antwort auf «und wo steht es dann?» ist eine andere –
nicht vor dem ersten Modul, sondern vor **diesem**. Am `start`-Eintrag steht dafür die
Modul-`id`; genau daran unterscheidet der Graph die beiden (`flow._tally`).

**Genommen wird nur, was frei ist** – Zustand `Freigegeben`, keine offene Zugehörigkeit.
Das ist keine zusätzliche Regel, sondern dieselbe, aus der auch das Abweichungs-Label
liest (§12.2): wer am Regelstart steht, war regulär verfügbar. Zwei Folgen, beide
gewollt: ein Verbrauch macht einen Auftrag **nie** stillschweigend zur Abweichung, und
ein Stück, das in einem anderen Auftrag läuft, kann nicht unter ihm weggezogen werden.

#### Die Zuordnung steht im Log — je Produkt-Stück

Der Log gibt die Zuordnung nicht von selbst her: zwischen «diese zwölf Schrauben gingen
in diesem Auftrag hinaus» und «diese vier gingen in dieses Getriebe» liegt genau eine
Angabe. Sie steht im **Payload** des `verbaut`-Eintrags (`into`), also dort, wo der Log
ohnehin festhält, was ein Modul festgehalten hat.

Das ist **kein Ersatzfeld**. Ein `into_instance_id` an der Einzelinstanz wäre eine zweite
Wahrheit, die bei einer Demontage geleert würde – womit die Vergangenheit des Getriebes
verschwände. Dieselbe Regel wie im Prozessbild (§8.1a): *eine Ansicht der Vergangenheit
darf keine bewegliche Grösse lesen.*

**Welche Schraube in welches Getriebe geht, ist keine menschliche Entscheidung** –
Schrauben desselben Artikels sind austauschbar. Entscheidend ist, dass die Zuordnung
aufgeschrieben wird; darum ist sie deterministisch (der Reihe nach, Produkt für Produkt)
statt geraten.

#### Nichtverfügbarkeit ist kein Zustand

Reicht der Bestand nicht, passiert dreierlei – und nichts davon ist ein Auftragszustand:

* die **Freigabe geht** (der Bestand ist eine Frage der Laufzeit, keine der Freigabe),
* das Modul **bewegt nichts**, auch das Produkt nicht,
* die Meldung nennt **Artikel, Bedarf und Verfügbarkeit** im Klartext.

Das Modul ist schlicht **nicht fertig**. Ein eigener «wartet auf Material»-Wert wäre ein
Zustand mehr, den jemand wieder verlassen müsste, und eine Verknüpfung auf einen
Nachschub-Auftrag ein Wartezustand, den niemand auflöst.

Angeboten werden zwei Wege, und **beide gibt es schon**: *eine andere Instanz wählen*
(dieselbe Wahl, die der Scan ohnehin trifft – sie reist als `sources` mit) und
*Nachschub anlegen* (ein ganz gewöhnlicher Auftragsentwurf mit diesem Artikel, ohne
Verknüpfung; das Modul fragt beim nächsten Versuch neu). **Automatisch ausgewichen wird
nie:** welches Material verbaut wird, ist eine Entscheidung, und eine unsichtbare
Automatik sähe man erst am fertigen Erzeugnis.

#### Was daraus folgt

* `Module.terminal` bleibt **False**. Es kommt gar nichts an, was ginge: das Produkt
  läuft weiter, die Komponenten treten hier ein. Die Kettenregel (§4.6) bleibt
  unangetastet – hinter der Montage darf die Endprüfung stehen.
* `Verbaut` ist **nicht terminal**: Demontage ist real, und das Greifen IST der Ausbau
  (wie beim Sperren). `Verschrottet` bleibt der einzige endgültige Zustand.
* **Die Stückliste ist eine Ableitung** (`services/genealogy`) – kein Feld, keine
  Tabelle, keine Beziehung. Ein ausgebautes Teil bleibt darum in der Liste und wird als
  *ausgebaut* gezeigt.
* Ein Auftrag **verbaut nicht, was er selbst erzeugt** (Freigabe-Fehler). Die
  Konfiguration trifft Artikel; die eine Stelle, an der diese Körnung zu grob ist, wird
  abgewiesen statt still falsch gerechnet.

### 9.7 Das Protokoll — ein abgeschlossenes Modul zeigt lückenlos, was in ihm geschah

> **Feste Regel für ALLE Module, heute und künftig.** Ein abgeschlossenes Modul zeigt auf
> Klick lückenlos, was in ihm passiert ist — **alle erfassten Daten, je Einzelinstanz**.

Und darum steht sie **hier**, nicht bei einem Modul. Ein Protokoll je Modultyp wäre
dieselbe Ansicht n-mal, und die (n+1)-te fehlte beim nächsten Typ — genau die Sorte Lücke,
die man erst bemerkt, wenn jemand einen Nachweis braucht. Gebaut ist sie als **eine**
Ableitung über den Ereignis-Log (`services/record.py` → `GET …/steps/{id}/record`) und
**eine** Komponente (`components/erp/step-record.tsx`, gerendert von der Modul-Karte, wenn
sie nicht die aktive ist).

**Gespeichert wird dafür nichts.** Alles steht schon da: der Übergang im Log, die Werte in
`captures`, die Ziehung als `sample`-Ereignis, das Ziel einer verbauten Komponente im
Payload (`into`). Was gefehlt hat, war die Ansicht.

**Ein Eintrag ist ein VORGANG, nicht ein Stück.** Ein Stück kann dasselbe Modul mehrfach
passieren — nach einem «nicht bestanden» wird erneut erfasst (§4.5), und **beides ist
passiert**. Der Log ist append-only; je Stück zusammengefasst überschriebe die
Wiederholung die Vergangenheit, und ausgerechnet der interessante Teil (die durchgefallene
Messung) verschwände.

Ein Vorgang wird aus zwei Ereignissen gebaut, in der Reihenfolge, in der sie geschrieben
werden:

| Ereignis | trägt |
|---|---|
| `capture` | **erfasst** — Werte, Urteil je Stück, wer, wann |
| `step` | **passiert** — Nachher-Zustand, Verifikation, ggf. `into` |

Eine Erfassung **ohne** folgendes `step` ist genau das, was «nicht bestanden» heisst: es
wurde gemessen, und es rückte nichts vor. Sie steht darum ebenfalls als Eintrag da.

**«Nicht gezogen» kommt aus der Ziehung, nicht aus einem Vermerk.** Ein Stück ohne
`capture` ist nicht automatisch ungezogen — ein Modul ohne Erfassungspunkte hat für *kein*
Stück einen. Die Aussage steht im `sample`-Ereignis, und das ist die einzige Stelle, an
der sie steht (`sampling.was_drawn` / `drawn_at`). Ein Vermerk am Übergang wäre der zweite
Ort, und er wäre unvollständig: ihn schreibt nur **einer** der beiden Wege, die ein Stück
vorrücken lassen — der Durchlauf am *nächsten* Modul, nicht der Vorgang am eigenen.

**Jeder Wert steht mit seiner Frage** («Länge: 10», nicht «laenge: 10»); die Beschriftung
kommt aus der Definition, das Urteil je Punkt aus seinem Typ. Ein Wert zu einem Punkt, den
die Definition nicht mehr kennt, wird **trotzdem** gezeigt — roh und mit seinem Schlüssel.
Ihn wegzulassen hiesse, aus einem Nachweis etwas zu entfernen, das erfasst wurde.

**Erst auf Klick, seitenweise, und die Gesamtzahl steht daneben.** Bei einer 6000er-Charge
sind es tausende Vorgänge; in jeder Auftrags-Antwort wären sie ein Vielfaches des
Auftrags. Ein *stiller* Deckel läse sich wie Vollständigkeit — bei einem Nachweis die
gefährlichste Form einer Lücke.


## 10. Darstellung

### 10.1 Regeln

- **Nur Vergangenheit und Gegenwart.** Oberhalb der aktuellen Stelle steht, was war; an
  ihr, was ist. Darunter steht **kein Material** — der Fluss sagt nicht voraus.
- **Ein Prozessobjekt = eine Komponente.** Kein Copy-Paste je Modultyp; der Modultyp ist
  Konfiguration, nicht ein eigenes Bauteil.
- **Niemals feste Pixelwerte oder absolute Positionen.** Knoten bestimmen ihre Position
  **selbst**; die Linien werden daraus **berechnet** — nicht umgekehrt.
- **Knoten-Layout und Linien-Layer sind getrennt.** Die Linien sind eine reine
  Darstellung **über** der Struktur, nie deren Träger.
- **Responsive**, inkl. Fenster-Resize und Zoom. Auf schmalen Geräten degradiert die
  Darstellung auf die mittlere Spalte. **Nie waagrecht scrollen** — bei einem Diagramm
  verliert man dabei die Achse aus dem Blick, also genau das, worum es geht.
- **Keine erfundenen Daten, keine Fallback-Anzeigen.** Fehlt etwas, kommt ein Fehler mit
  Ursache und Ort.

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

### 10.3 Der Bestand — eine Frage, drei Ebenen, kein Filter

Der Bestand beantwortet **eine** Frage: *wie viel habe ich, in welchem Zustand, unter
welcher Nummer?* Er ist reine **Summierung über Einzelinstanzen** — die
Einzelinstanz-Regel (§2) auf der Anzeige-Ebene.

**EIN Modul, zwei Umfänge** (`components/erp/stock-view.tsx`). Dieselbe Frage steht an
zwei Orten, und sie unterscheiden sich ausschliesslich im **Umfang der Daten**, nie in
der Darstellung:

| Aufruf | Umfang | Die Zeilen sind |
|---|---|---|
| Artikel, Reiter «Bestand» | alles von diesem Artikel | seine **Instanzen**, aufklappbar zu ihren Nummern |
| Instanz-Datensatz | diese eine Gruppe | direkt ihre **Einzelinstanzen** |

Die Ansicht an der Instanz ist damit exakt der Teilbaum, den man am Artikel aufklappt.
Zwei Fassungen hätten sich beim ersten neuen Zustand, beim ersten Design-Wechsel und bei
der ersten Regel (Bestand ↔ Historie) getrennt — genau so stand es hier: der Artikel
hatte drei Ebenen mit Leiste und Legende, die Instanz eine schlichte Liste.

**Drei Ebenen, jede vollständiger als die darüber:**

| Ebene | Zeigt | Kommt von |
|---|---|---|
| 1 | gestapelte Leiste + **eine Gruppe je Zustand** | `GET /erp/articles/{id}/stock` → `states` |
| 2 | in jeder Gruppe eine Zeile je Instanz: Nummer · Menge **in diesem Zustand** | dieselbe Antwort, `instances` (seitenweise) |
| 3 | die Nummern der Stücke, je mit Zustand und Auftrag | `GET /erp/instances/{id}/units` (erst auf Klick) |

**Kein Filter.** Ein Filter ist meistens das Eingeständnis, dass die Standardansicht zu
viel Rauschen enthält; und er versteckt, was er nicht zeigt. Stattdessen ist die
**Aufteilung selbst das Bedienelement**: eine Gruppe aufklappen heisst «zeig mir diese
Nummern», der Rest bleibt sichtbar.

**Eine Gruppe je Zustand — und die Ansicht zählt keinen einzigen auf.** Gruppiert wird
über die Zustände, die wirklich vorkommen (`states`); alles Weitere folgt aus dem Status
selbst (§5.2):

| Frage | Antwort kommt von |
|---|---|
| Welche Gruppen gibt es? | den gelieferten `states` – nie einer Liste in der Ansicht |
| In welcher **Reihenfolge**? | der Position im `CATALOG` = **Lebenszyklus** (Freigegeben → Im Prozess → Gesperrt → Verschrottet), dieselbe wie Leiste und Legende |
| Welche **Farbe**? | dem Ampelton des Status |
| **Zugeklappt** oder offen? | `stock`: was zur **Historie** zählt, startet zu |

Ein neuer Zustand erscheint damit **ohne eine Zeile Änderung** an seiner Stelle im
Lebenszyklus, in seiner Farbe. Vorher waren es zwei feste Blöcke (Bestand/Historie) – eine
Aufteilung, in der ein neuer Zustand verschwand, statt sich zu zeigen. Ein Zustand **ohne**
Zuordnung wird **gemeldet** statt einsortiert.

**Keine Gesamtzahl im Kopf.** Sie summierte alles – auch Verschrottetes – und war damit
zugleich irreführend (das ist kein Bestand) und uninformativ (sie sagte nicht, wovon). Die
Zahlen stehen an den Gruppen, je eine je Zustand.

**Die Karte ist die der Spezifikation** (`SPEC.card` + `SpecHead` aus `fields.tsx`) – die
Anatomie jeder Detail-Ansicht, nicht die des Artikels. Sie stand lokal im Artikel und war
dort auf «Spezifikation» festgenagelt; wer daneben etwas baute, schrieb sich einen eigenen
Kopf, und dann sahen die Karten nur noch *ähnlich* aus.

**Die Instanz hat keinen Zustand, sondern eine Aufstellung.** Eine Gruppe mit drei
freigegebenen und einem laufenden Stück hat keinen einen Zustand (Testnotiz #675); jede
gewählte Antwort wäre eine Behauptung. `states` zählt darum auf, und die Menge ist die
Summe — **eine** Abfrage, zwei Lesarten. Genau daran scheiterte der Vorgänger: er las
`Instance.status`, eine Spalte, die es nicht gibt, und endete bei jedem Aufruf mit 500.

**Kein Sonderfall für Einzelserialisierung.** Eine Einzelinstanz ist eine Instanz mit
Menge 1 — dieselbe Zeile, dieselbe Leiste, dieselbe Nummernliste. Und die Leiste ist
**ein** Bauteil für beide Massstäbe (Artikel wie Instanz): eine zweite «kleine» Leiste
wäre eine zweite Regel dafür, wie ein Zustand aussieht.

**Sortierung: aufsteigend nach Objektnummer = FIFO.** Nummern werden aufsteigend
vergeben, und eine Instanz entsteht mit ihren Stücken (§2.2) — aufsteigend ist damit die
Reihenfolge, in der das Material entstanden ist. Der Feed sortiert absteigend, weil man
dort den zuletzt angelegten Datensatz sucht; hier sucht man das älteste Material. **Ein
eigenes Datum braucht es dafür nicht**, und es wäre die zweite Wahrheit neben der Nummer.

**Gruppiert wird nach Instanz, nicht nach Zustand.** Die Vorgängeransicht gruppierte nach
Zustand, weil sie keine Leiste hatte — die Gruppenköpfe *waren* die Übersicht. Mit der
Leiste ist diese Frage oben beantwortet, und die Instanz ist die Klammer, die zählt: sie
trägt die Objektnummer, die man scannt und zitiert. Nach Zustand gruppiert erschiene
dieselbe Charge in zwei Gruppen und ihre Menge nirgends vollständig.

**Nie alles auf einmal.** Instanzen kommen seitenweise (50), Nummern erst auf Klick und
auch dann seitenweise (60). Die Leiste oben gilt trotzdem für den **ganzen** Artikel —
eine Aggregation, die sich beim Blättern ändert, beantwortet «wie viel habe ich» nicht.
Dieselbe Regel gilt im **Instanz-Datensatz**: eine Ansicht, die die Regel einhält, und
eine Nachbaransicht, die sie einen Klick weiter bricht, ist keine Regel.

---

## 11. Datenstruktur — drei Ebenen

Die Trennung ist die Voraussetzung für Skalierbarkeit. Sie ist zugleich die Lehre aus
dem Vorgängersystem: dort wurde der Zustand aus dem heutigen Bestand **rekonstruiert**,
und weil der Bestand ein bewegliches Ziel ist, schrieb jede Änderung die Vergangenheit
um.

### 11.1 Ebene 1 — Prozessdefinition (die Modellierung)

```
process_steps
  id · order_id · position · module_type · config(JSONB)
  status_before · status_after
```

**Eine geordnete Liste, kein allgemeiner Graph.** Ein Auftrag hat einen Anfang, ein Ende
und dazwischen eine Folge — `position` ist die Kante. Verzweigungen entstehen nicht
innerhalb der Definition, sondern als **eigener Auftrag** daneben (Abweichungsauftrag, §12).
Ein Kantenmodell würde eine Freiheit anbieten, die es fachlich nicht gibt, und jede
Auswertung müsste danach mit Zyklen und toten Ästen rechnen.

Start und Ende sind **keine Zeilen**: es gibt genau einen von jedem, ihre Position ist
implizit, und ihre Übergänge gehören zum System, nicht zur Modellierung (§4.1).

**Die `id` IST die Identität eines Moduls.** Sie entsteht mit der Zeile und ändert sich
nie; der Ereignis-Log (§11.3) zeigt ausschliesslich auf sie — nie auf einen Namen, nie
auf die Position. **Ein Namensfeld gibt es nicht**: wie ein Modul heisst, sagt sein Typ
(`domain/modules`). Es hatte genau eine richtige Antwort und war trotzdem Pflicht — und
als Identität taugte es nie, denn ein Name lässt sich ändern, doppelt vergeben oder leer
lassen, und dann zeigt die Historie auf etwas, das es so nie gab. Die `position` taugt
ebenso wenig: sie beschreibt eine Reihenfolge, keine Sache.

### 11.2 Ebene 2 — Laufzeit-Zustand (wo steht was)

```
instance_units.status        welchen Status hat das Stück
order_units.current_step_id  an welchem Objekt steht es   (NULL = am Ende)
order_units.released_at      NULL = aktiv, sonst Historie
```

**Alles davon ist Projektion, nicht Wahrheit.** Die Wahrheit steht in Ebene 3. Diese
Spalten existieren nur, damit Feed, Filter und Bestandsabfragen ohne Log-Replay
auskommen. Sie werden **ausschliesslich** beim Schreiben eines Log-Eintrags nachgezogen
— es gibt keinen zweiten Schreibweg.

Ein Wächter prüft die Ableitbarkeit: `Projektion == Replay(Log)`. Weicht es ab, ist das
ein Fehler, der **gemeldet** wird — nicht einer, der still korrigiert wird.

**Die Exklusivität (§3) steht als partieller Unique-Index auf `order_units`:**

```sql
CREATE UNIQUE INDEX uq_order_units_active
    ON order_units (instance_unit_id) WHERE released_at IS NULL;
```

Das ist genau die Trennung aus §3, in einer Spalte: *aktiv* (`released_at IS NULL`) ist
exklusiv, *referenziert* (die Zeile bleibt nach der Freigabe stehen) ist beliebig oft
erlaubt. Ein abgeschlossener Auftrag behält damit seine Liste, ohne seine Stücke zu
blockieren.

Der Index steht in der Migration **und** im Lifespan-Netz. Er ist die einzige Stelle, an
der die Regel nicht umgangen werden kann: in der Anwendungslogik geprüft, lesen zwei
gleichzeitige Freigaben beide «ist frei» und schreiben beide.

### 11.3 Ebene 3 — Ereignis-Log (die eingefrorene Historie)

```
process_events
  id · order_id · step_id · instance_unit_id
  status_before · status_after
  payload(JSONB)  actor_id  created_at
```

Append-only. Kein Update, kein Delete, kein `is_active`. Die Reihenfolge ist die `id` —
sie ist die Zeitachse.

Der Log trägt damit **zwei** Fragen, nicht eine: was ist mit diesem Auftrag passiert
(§7.2) und **wo war dieses Stück vorher bzw. nachher** (§7.4). Für die zweite steht ein
Index `(instance_unit_id, id)` daneben — dieselbe Tabelle, nur eine zweite Leserichtung.

**Eigene Tabelle, nicht der bestehende `events`-Strom.** Der ist ein Beobachtungs-Outbox
für KI und Analytik mit freier Payload; hier geht es um die Quelle der Wahrheit für den
Zustand. Beides in einer Tabelle hiesse, eine «nice to have»-Spur und eine verbindliche
Buchführung in denselben Zeilen zu führen — und die schwächere Garantie gewinnt immer.

---

## 12. Abweichungsaufträge

Der definierte Prozess ist das **Soll**. Was in der Wirklichkeit davon abweicht — nochmals
kontrollieren, nacharbeiten, aussortieren, zurückschicken — sind unendlich viele Fälle.
Sie werden nicht aufgezählt und nicht als Modultypen vorgesehen. Sie werden **mit einem
Auftrag** dargestellt.

### 12.1 Ein Abweichungsauftrag ist 1:1 ein regulärer Auftrag

Kein neuer Datensatztyp, keine zweite Tabelle, kein zweiter Endpunkt, kein Sonderweg bei
der Freigabe. Dieselbe Definition (§2.1), dieselbe Exklusivität (§3), dieselben Module,
derselbe Log.

> **Wer im Code nach `if abweichung:` sucht, hat es falsch gebaut.**

Was ihn ausmacht, ist **nichts an ihm selbst**, sondern die Herkunft seiner Stücke: er
greift Einzelinstanzen, die in diesem Moment `Im Prozess` stehen. Das ist keine Ausnahme
von §3, sondern deren Anwendung — das Stück wird dem laufenden Auftrag **entzogen**, nicht
ein zweites Mal aktiv gemacht. In einer Transaktion: die alte Zugehörigkeit schliessen,
dann die neue anlegen. Der partielle Unique-Index sieht nie zwei aktive Zeilen; er ist
damit auch hier die Stelle, an der die Regel nicht umgangen werden kann.

### 12.2 Das Label ist abgeleitet, nicht gesetzt

> **Ein Auftrag ist eine Abweichung, wenn sein Start vom Regelstart abwich.**

Der Regelstart ist genau **ein** Zustand (`statuses.START_BEFORE` = *Freigegeben*, §4.1):
so beginnt ein Stück, das regulär verfügbar war. Alles andere ist ein Zugriff auf
Material, das gerade **nicht** zur Verfügung stand. Genau diese Frage steht im Log:

```sql
kind = 'start' AND status_before <> 'freigegeben'
```

**Die Regel nennt keinen Status.** Sie hiess einmal `status_before = 'im_prozess'`, also
«einem laufenden Auftrag entzogen» – technisch stimmig, fachlich zu eng: ein **gesperrtes**
Stück wieder in Betrieb zu nehmen gehört zu keinem laufenden Auftrag und fiel damit heraus,
obwohl es in der Qualitätssicherung der Musterfall einer **Sonderfreigabe** ist. Der Zweck
des Labels ist die **Nachweisbarkeit**; ein Nachweis, der den auffälligsten Fall auslässt,
ist keiner.

Als Vergleich gegen den einen Regelstart ist sie zugleich die **einfachere** Regel und die
haltbarere: ein künftiger Zustand ist automatisch eine Abweichung, ohne dass ihn jemand
hier einträgt. Die Richtung stimmt – wer zu viel ausweist, dokumentiert; wer zu wenig
ausweist, verliert den Nachweis. Ein **terminales** Stück kommt dabei nie vor: es lässt
sich gar nicht erst greifen (§5.3).

Kein Feld, kein Flag, keine Pflege. Es ist die Frage selbst, an den Log gestellt — und
damit per Konstruktion nie veraltet.

### 12.3 Die Rückführung ist eine Eigenschaft der VERBINDUNG

Nicht des Auftrags. Sie steht als **eine Spalte** an der Zugehörigkeit:

```
order_units.return_to_order_id   in welchen Auftrag kehrt dieses Stück zurück
                                 NULL = nirgendwohin
```

Das ist der Grund, warum Schachtelung und Parallelität **ohne eine zweite Regel**
funktionieren: jede Kante entscheidet für sich. Ein Stück kann durch fünf Aufträge
wandern, von denen der dritte gekappt ist — dann endet die Kette dort, und zwar für alle
darüber gleichermassen. Stünde die Eigenschaft am *Auftrag*, müsste sie für jede Kante
gelten, die je an ihm hängt; ein Auftrag, der Stücke aus zwei verschiedenen Aufträgen
holt, hätte dann eine Antwort für zwei Fragen.

Zwei Fälle, **eine Logik**:

| | Der Hauptauftrag |
|---|---|
| **rückführend** | wartet auf das Stück und läuft danach an derselben Stelle weiter |
| **gekappt** | läuft mit **reduzierter Menge** ganz normal weiter — er wartet nicht |

Die Menge des Hauptauftrags wird dabei nirgends dekrementiert. Sie *ist* die Zahl seiner
aktiven Zugehörigkeiten; ein entzogenes Stück ist schlicht keine mehr.

### 12.4 Die Abzweigung hängt an einem ZUSTANDSPUNKT, nicht an einem Modul

Ein **Zustandspunkt** ist die Stelle auf der Prozesslinie, an der ein Stück wartet —
zwischen zwei Objekten, nicht in einem. Er hat bereits eine Identität in den Daten:

```
order_units.current_step_id   „steht VOR diesem Modul“   (NULL = nach dem Ende)
```

Ein Punkt heisst also «vor Modul X». **Das Modul benennt ihn, es besitzt ihn nicht.**

Daraus folgt, wo die Abzweigung sitzt — und zwar als **eine** Regel, nicht als Liste von
Fällen:

> Die Abzweigung hängt an der **aktuellen Position** der Einzelinstanz. Vor dem Modul,
> wenn sie davorsteht; dahinter, wenn sie es passiert hat.

Heute ist der erste Fall der einzige, den es gibt: ein Stück steht **immer** vor dem
Modul, wenn es abweicht — auch nach einem «nicht bestanden», denn das rückt ausdrücklich
nicht vor (§4.5). Die Linie geht darum vor dem Modul ab und führt an **denselben Punkt**
zurück; das Stück durchläuft das Modul danach regulär.

> **Achtung, hier stand eine zu enge Begründung.** «Ein Stück kann nur abweichen, solange
> am Modul noch nichts eingegeben wurde (§12.7) — es hat das Modul also gar nicht
> betreten» stimmt für den Regelfall, aber nicht für den wichtigsten: nach einer
> **durchgefallenen** Erfassung ist sehr wohl etwas eingegeben, und genau dort *bietet*
> §4.5 die Abweichung an. Die Position ist trotzdem «davor», weil nichts vorgerückt ist —
> und **das** ist der Grund, nicht die Eingabe. Was daraus folgt und was noch offen ist,
> steht in `SYSTEM_LOGIC.md` §5.5.

```
        ⋮
   ● Zustandspunkt  ──────────▶  [ Abweichungsauftrag ]
        │           ◀╌╌╌╌╌╌╌╌╌╌
   [ Modul ]
        ⋮
```

**Die Rückkehrposition braucht darum kein eigenes Feld.** Beim Ausscheren wird die Zeile
des Quell-Auftrags geschlossen (`released_at`), ihr `current_step_id` aber **nicht
angefasst**. Die Stelle steht damit schon dort, wo sie hingehört; die Rückkehr ist das
Wiederöffnen genau dieser Zeile.

| `current_step_id` einer geschlossenen Zeile | Bedeutung |
|---|---|
| `NULL` | angekommen — das Stück hat das Ende passiert |
| gesetzt | ausgeschert — und das ist die Stelle, an die es zurückkehrt |

Ein gemerkter «Rücksprungpunkt» wäre eine zweite Aussage über dieselbe Sache und könnte
von der ersten abweichen. Diese hier kann es nicht.

**Im Bild gibt es keinen Rückfall.** Ein Zustandspunkt wird gezeichnet, wenn dort etwas
steht — anwesend **oder** ausgeschert — **oder** wenn eine Abzweigung an ihm ansetzt. Der
letzte Fall ist der, an dem es zuerst fehlte: sind alle Stücke ausgeschert oder längst
zurück und weitergezogen, steht am Punkt nichts mehr, und die Linie fiel auf das
nächstbeste Element zurück — das Modul. Weil ein Punkt nach dem Modul heisst, vor dem er
liegt, ist sein Anker **berechenbar** (`statePointId`); gesucht oder geraten wird nichts.

Und weil ein Abweichungsauftrag an **mehreren** Punkten zugreifen kann, ist die Angabe
eine **Liste** (`RelatedOrder.branches`). Ein Einzelwert hätte sich für einen entschieden
und die anderen verschwiegen.

### 12.5 «Wartet auf Rückführung» wird abgeleitet

Gezählt werden die **offenen rückführenden Verbindungen**, die auf diesen Auftrag zeigen —
über die ganze Kette nach oben, denn ein Stück, das zwei Ebenen tiefer steckt, kommt
ebenso zurück. Kein Zähler, kein Flag, nichts, das jemand zu dekrementieren vergessen
kann.

Aus derselben Quelle fällt der **Auftragsstatus** — ebenfalls abgeleitet, nie gesetzt:

```
noch etwas aktiv oder verliehen  →  Im Prozess
sonst, mindestens eines angekommen  →  Abgeschlossen
sonst  →  Abgebrochen
```

Die Reihenfolge ist nicht beliebig: «angekommen» darf «noch unterwegs» nicht schlagen,
sonst gilt ein Auftrag als fertig, sobald das erste Stück durch ist. Solange alle Stücke
im Gleichschritt laufen, fällt das nie auf — mit Abweichungen sofort.

### 12.6 Ein Modul, auf dessen Rückführung gewartet wird, ist GESPERRT

Was gleich zurückkommt, gehört zu dem, was an dieser Stelle bearbeitet wird. Bestätigen
hiesse, ohne dieses Stück fortzufahren — und hinterher wäre es zurück, aber der Zug
abgefahren.

- **Der Inhalt bleibt sichtbar.** Man will sehen, was drinsteht.
- **Keine Eingabe, kein Bestätigen, kein Absenden** — auch nicht über die API.
- Der Grund steht am Modul und **nennt den Abweichungsauftrag**, in dem das Stück gerade
  steckt: dort ist etwas zu tun, damit es weitergeht.

**Gekappte Ausleihen sperren nichts** (§12.3): sie kommen nie zurück, der Auftrag läuft
mit weniger Stücken weiter und wartet ausdrücklich nicht. Ohne diese Unterscheidung
stünde jedes Modul, aus dem je etwas ausgesondert wurde, für immer still. **Die Kette
zählt** (§12.5): leiht A an B und B weiter an C, ist auch A gesperrt.

**Die Regel steht an genau zwei Stellen, und keine davon ist ein Modul:**

| | |
|---|---|
| Durchsetzung | `process.confirm_step` — der EINE Mechanismus, den jedes Modul auslöst |
| Darstellung | `StepCard` — die EINE Karte, die jedes Modul rendert (`fieldset[disabled]`) |

> **Ein Modul fragt nicht, ob es darf. Ihm wird gesagt, dass es nicht darf.**

Ein künftiger Einkauf oder Verkauf erbt beides, ohne eine Zeile dafür zu schreiben.
`fieldset[disabled]` schaltet jede Eingabe und jeden Knopf darin ab, ganz gleich was das
Modul rendert — die Sperre muss nicht wissen, was sie sperrt.

### 12.6a Die Auswahl nennt, wo sie zugreift

Ein Entwurf lebt im Browser, die Freigabe passiert später. Dazwischen kann jemand anders
dasselbe Stück nehmen. Die Exklusivität (§3) verhindert, dass beide es halten — sie sagt
aber nicht, **wer** verliert.

Darum trägt jeder gewählte Anteil seine **Absicht** mit (`UnitPick.from_order`):

| Auswahl | Bedeutung |
|---|---|
| `null` | «ich nehme ein freies Stück» |
| Objektnummer | «ich hole es aus genau diesem Auftrag» — das ist die Abweichung |

Die Freigabe vergleicht die Absicht mit der Wirklichkeit (`process._assert_as_picked`).
Weicht sie ab, passiert **nichts**, und der Fehler nennt beide Seiten. Ohne diese Prüfung
entschied die Reihenfolge der Klicks, welche **Art** Auftrag entsteht: ein als frei
gewähltes Stück, das inzwischen lief, machte die Freigabe still zur Abweichung und entzog
es dem anderen Auftrag — mit `return_to = NULL`, also für immer.

Das ist optimistisches Sperren mit dem Wert, den der Mensch gesehen hat, und es ist **eine**
Auswahl-Logik für beide Fälle: konkrete Stücke, vorher sichtbar, änderbar. Einen zweiten
Weg «nur nach Kriterium» gibt es nicht — die Kriterien-Auswahl ist der Normalfall dieser
einen: FIFO schlägt vor, der Mensch übersteuert.

**Ein Auftrag darf nie unbemerkt seine Art ändern.**

**Freie und gebundene Stücke dürfen im selben Auftrag stehen** — und es braucht dafür
**keine** Regel. Die Frage «grün und orange nicht mischen» ist bereits beantwortet, nur
eine Ebene tiefer: die Absicht steht **je Stück**, nicht je Auftrag. Damit ist eine
gemischte Auswahl kein Zwitter, sondern schlicht ein Auftrag, der ein freies Stück
übernimmt *und* einem laufenden eines abnimmt — beide Wege gehen durch dasselbe
Start-Objekt (§4.1), und `return_to_order_id` entsteht genau für die geliehenen. Auch die
Rückführung ist keine Ausnahme: ein freies Stück kommt aus keinem Auftrag, es kann darum
nirgends zurückkehren. Gemessen an den echten Dienstpfaden (eine Zeile, zwei Zeilen,
gekappt und rückführend): Graph widerspruchsfrei, Nachbar-Liste korrekt, Bypass korrekt.
Eine zusätzliche Regel wäre eine zweite Aussage über dieselbe Sache — und die überstimmt
irgendwann die erste.

### 12.7 Wann darf ein Stück ein Modul verlassen?

**Offene Entscheidung** (§13.2). Gebaut ist die restriktivere Variante: solange in einem
Modul mit der Eingabe **begonnen** wurde, ist der Auslöser gesperrt.

Sie steht als **Eigenschaft des Modultyps** (`Module.units_may_leave`), nicht als globale
Regel — denn die richtige Antwort hängt am Modul: eine begonnene Datenerfassung ist
verlorene Tipparbeit, eine ausgelöste Bestellung ist Aussenwirkung. Ein Modultyp, der
etwas Unwiderrufliches tut, wird die Antwort «nein» brauchen, während sie für die
Datenerfassung eher «ja» lautet.

**Serverseitig kann diese Regel nicht erzwungen werden**, und das ist kein Versäumnis:
eine nicht bestätigte Eingabe existiert nirgends — nicht in der Datenbank, nicht im Log.
Nur das Fenster, in dem getippt wird, kennt diesen Zustand. Die Sperre ist deshalb eine
Vorsichtsmassnahme in der Oberfläche; die *Regel* wohnt am Modultyp und wird dort
beantwortet, sobald ein Modul mit Aussenwirkung existiert.

### 12.8 Darstellung — drei Spalten, eine Komponente

```
   übergeordneter Auftrag  │   dieser Auftrag   │   Abweichungsaufträge
   (verblasst)             │   (der Fokus)      │   (verblasst)
```

- Eine Seitenspalte erscheint **nur**, wenn es dort etwas gibt.
- Die Nachbarn zeigen **exakt den Prozess, der in ihnen definiert ist** — nicht eine
  Zusammenfassung, nicht ein Symbol. **Dieselbe Komponente** (`FlowColumn`), nur mit
  `faded`. Ein eigener «Kurzform»-Renderer wäre eine zweite Darstellung derselben Sache
  und liefe irgendwann auseinander.
- Ein Klick öffnet den Nachbarn: er wird zur Mitte, und seine Nachbarn erscheinen um ihn
  herum. Es gibt keine Sonderansicht — nur einen anderen Auftrag in der Mitte.
- **Die Prozesslinien führen.** Eine Querlinie geht dorthin, wo das Stück ausgeschert
  ist, und eine **gestrichelte** kommt dorthin zurück, wo es weitergeht. Ist die
  Rückführung gekappt, fehlt die zweite Linie — das Bild sagt es, ohne ein Wort.
- **Skalierung:** die Seitenspalte rendert **höchstens drei** Nachbarn voll; der Rest
  steht als Zeile «+N weitere» mit der Gesamtzahl und ist anklickbar. Abschneiden mit
  Zähler, nicht gruppieren: eine Gruppe müsste einen gemeinsamen Nenner behaupten, den es
  bei Abweichungen nicht gibt.

---

## 13. Bewusst noch nicht definiert

Diese Punkte gehören zur Grundlogik, sind aber **nicht** entschieden. Sie werden einzeln
nachgetragen — nicht beim Bauen erraten.

1. **Die weiteren Prozessschrittmodule.** Zwei sind fertig: Datenerfassung (§9.0–§9.3)
   und Aussondern (§9.4). *Nicht mehr offen: die Erfassungsgrösse ist die **Instanz**
   (§4.4), was bei «nicht bestanden» passiert steht in §4.5, und ein Modul darf das
   Stück aus dem Auftrag hinausführen (§4.6).*
2. **Darf ein Abweichungsauftrag noch ausgelöst werden, wenn in einem Modul bereits mit
   der Dateneingabe begonnen wurde?** Gebaut ist vorläufig die restriktivere Variante
   (nein) — als **Eigenschaft des Modultyps**, nicht als globale Regel (§12.7).
3. **Abbruch.** §3.1 schlägt vor, was mit den Stücken geschieht; wer abbrechen darf und
   was mit dem Auftrag selbst passiert, ist offen.
4. **~~Fehlerbehandlung im Modul.~~ Entschieden (§4.5): weder Status noch automatischer
   Abzweig.** Das Stück bleibt stehen, das Ergebnis ist geloggt, und der Mensch
   entscheidet — angeboten wird ein ganz gewöhnlicher Auftrag mit vorgewählten Stücken.
   «Nicht bestanden» ist eine Aussage über die **Messung**, kein Zustand des Stücks; ein
   Stück in einem Abweichungsauftrag ist `Im Prozess`, dort, wo es hingehört. Was daraus
   folgt, entscheidet der Folgeauftrag — und **wenn** er aussondert, sagt das sein Modul
   (§9.4), nicht die Datenerfassung.
5. **Zwei `Neu`-Zeilen mit verschiedenen Vorlagen.** Heute ein harter Fehler: ein Auftrag
   hat einen Prozess (§14). Ob es dafür je einen Fall gibt, ist nicht entschieden.
6. **Die Vorlage im Entwurf abweichen lassen.** Heute nicht möglich — der Stempel wäre
   sonst eine Behauptung. Falls es gebraucht wird, ist es ein eigener Vorgang
   («Prozess dieses Auftrags von der Vorlage lösen»), kein stilles Editieren.

---

## 14. Getroffene Annahmen

Wo die Vorgabe eine Lücke liess, steht hier die gewählte Variante — jede ist die
einfachste, die die Regeln erfüllt, und jede ist an einer Stelle änderbar.

| | |
|---|---|
| **Die Statusliste hat genau zwei Werte** | `Freigegeben` ersetzt `verfügbar` (ein Zustand, ein Wort). `gebunden`/`gesperrt`/`verbraucht` sind zurückgezogen — Gründe in §5.2. |
| **Ein neues Stück ist `Freigegeben`** | Alles andere bräuchte eine Regel, wie es das wird — und die gibt es noch nicht. |
| **Kein gespeicherter Zustand «Entwurf»** | Folgt zwingend aus §6.1 + §6.3. Der «Speichern»-Knopf ist entfallen; es gibt nur «Freigeben». |
| **Exklusivität als partieller Unique-Index auf `order_units`** | Die Zuordnungstabelle behält die Historie, `released_at IS NULL` ist «aktiv». Eine Spalte an der Einzelinstanz wäre ebenso exklusiv, verlöre aber die Liste des abgeschlossenen Auftrags. |
| **Exklusivitätsprüfung VOR der Nummernvergabe** | Sonst verbrennt jeder Verstoss eine Objektnummer (§6.3). |
| **`orders.end_status` als Ort des Endzustands** | Hält die Schrittliste rein und gibt dem Endzustand seine eine Adresse. |
| **A5 gilt für Modul-Definitionen, nicht für die Instanz-Liste** | Bei einer Liste wäre «löschen und neu anlegen» dasselbe wie «bearbeiten». |
| **Der Auftrag kennt `released` und `completed`** | «Abgeschlossen» ist abgeleitet: alle Stücke sind durch. Kein Feld, das jemand von Hand setzt. |
| **Ein Modul bewegt alle Stücke einer INSTANZ, die davor stehen** | *(Ersetzt «alle Stücke, die davor stehen».)* Ein Bestätigen je Stück wäre bei 500 Stück unbedienbar — je **Instanz** ist es die richtige Grösse, weil der Scan die Instanz verifiziert (§4.4): eine Charge ist ein Griff, zwölf Einzelteile sind zwölf. Die Historie bleibt **je Stück** ein eigener Eintrag. |
| **Die Datenerfassung erfasst EINMAL je Instanz** | *(Ersetzt «einmal für alle Davorstehenden» — entschieden über §4.4.)* Nicht die bequemere, sondern die einzig mögliche Grösse: ein Wertesatz gehört zu **einem** Urteil, und verifiziert wird eine Instanz. **Gespeichert wird weiterhin je Einzelinstanz**, damit die Zeile in deren Historie steht. |
| **Die Stichprobe wird zufällig gezogen, nicht gerechnet** | «Jedes n-te Stück» wäre vorhersagbar und damit als Stichprobe wertlos. Gezogen wird, wenn das Modul **erreicht** wird (vorher steht die Menge nicht fest), und **eingefroren im Log** — sie ändert sich nicht mehr, wenn jemand die Seite neu lädt (§9.3). |
| **Die Stichprobenregel gilt über die GESAMTMENGE** | *(Ersetzt «je Instanz».)* Ein Modul sieht die Summe dessen, was davorsteht – «10 %» heisst 10 % davon. Je Instanz gerechnet stünde «10 %» am Bildschirm, während in Wahrheit aus jeder Kiste einzeln gezogen wird (und aus einer Kiste mit einem Stück immer dieses eine). |
| **Ein «nicht bestanden» hält die GANZE Instanz an** | Auch die nicht gezogenen Stücke: eine durchgefallene Stichprobe ist nicht mehr repräsentativ, der Rest ist verdächtig (Sortierprüfung). Ihn weiterlaufen zu lassen hiesse, ihn hinterher wieder einzusammeln. |
| **Die 100 %-Kontrolle ist ein gewöhnlicher Auftrag** | Kein neuer Mechanismus — nur eine andere Vorbelegung (der ungeprüfte Rest statt der Durchfaller). Ihr Umfang ist der Rest **dieser Instanz an diesem Modul**: Stücke, die anderswo laufen oder längst am Lager liegen, hat dieses Modul nie behandelt, und eine Aussage über sie wäre eine über Material, das hier nie war. |
| **Die Nummern der Entscheidungs-Gruppen kommen erst auf Klick** | Bei einer 6000er-Charge wäre der «Rest» sechstausend Nummern — mitgeliefert bei jedem Öffnen des Auftrags. Eigener Endpunkt (`GET …/steps/{id}/hold`). |
| **Die Art der Bestätigung steht im Log** | `scan` oder `manual`. Ohne den Vermerk wäre die Tastatur eine stille Umgehung der Scan-Pflicht statt ihrer protokollierten Alternative. |
| **Zwei Zustände statt einem «ausgesondert»** | Sie unterscheiden sich in genau einer Sache, und die zählt: ob es einen Weg zurück gibt. Ein gemeinsamer Wert mit einem Flag daneben wäre dieselbe Aussage in zwei Feldern – und die Farbe müsste sie erraten. |
| **`Gesperrt` zählt zum Bestand** | Das Stück liegt im Regal. Es in die Historie zu legen hiesse, den Bestand kleiner zu melden, als er ist; die Leiste zeigt es als eigenes Segment, und genau das ist die Auskunft. |
| **Das Greifen IST das Aufheben der Sperre** | Kein Endpunkt «entsperren», kein zweiter Weg: ein gewöhnlicher Auftrag nimmt das Stück auf, das Start-Objekt setzt es auf «Im Prozess». Ein eigener Mechanismus wäre eine zweite Art, dasselbe zu tun. |
| **Verschrotten ist keine Bestandsbewegung mit Ziel** | Es gibt kein «Schrottlager». Der Zustand IST die Aussage «gibt es nicht mehr»; ein Lagerort dafür wäre ein Ort für etwas, das weg ist. |
| **Aussondern kennt keine Teilmengen** | Was am Modul ankommt, wird ausgesondert. Wer nur einen Teil meint, gibt nur diesen Teil in den Auftrag – eine Auswahl im Modul wäre ein zweiter Weg zur selben Entscheidung. |
| **Der Grund ist Pflicht beim Sperren, nicht beim Verschrotten** | Eine Sperre ohne Begründung ist in drei Monaten wertlos. Beim Verschrotten ist der Scan die Bestätigung; ein zweites Feld macht den Fall nicht häufiger richtig. |
| **Der Grund ist ein Erfassungspunkt, den das MODUL deklariert** | Kein neuer Mechanismus, aber auch keine Konfiguration: wäre er einstellbar, könnte man ihn wegkonfigurieren – und genau er ist der Sinn der Sperre. |
| **Ein terminales Modul darf nur zuletzt stehen** | Alles dahinter bekäme nie ein Stück. Eine tote Definition durchzulassen wäre schlimmer als ein Freigabe-Fehler: sie sieht aus wie ein Prozess. |
| **Die Kettenregel gilt auch für die Artikel-Vorlage** | Sie stand nur in der Auftrags-Freigabe; ein Erzeugungsprozess mit gebrochener Kette liess sich anlegen und scheiterte erst beim ersten Auftrag – dann aber ist der Artikel eingefroren und nicht mehr zu reparieren. Jetzt in `domain/chain.py`, von beiden Definitionsorten gerufen. |
| **Der Auftragsstatus bekommt keinen vierten Wert** | Die bestehende Regel trägt beide Fälle: wer aussondert, hat sein Ziel erreicht (`Abgeschlossen`); wem die Stücke dadurch endgültig fehlen, dessen Ziel ist unerreichbar (`Abgebrochen`). |
| **Der Übergang gehört zum Modultyp, nicht zum Anwender** | «Fest verdrahtet, nicht einstellbar» (Vorgabe). Zwei Status-Auswahlen beim Anlegen hätten eine Entscheidung angeboten, deren einzige richtige Antwort schon feststand — und deren falsche einen Prozess ergäbe, der nicht läuft. **Der Typ darf dabei seine eigene Konfiguration lesen** (`status_after_for`, seit dem Aussondern): gewählt wird «was soll passieren», nicht «welcher Status». |
| **Alles, was angelegt ist, ist Pflicht** | *(Ersetzt «standardmässig Pflicht, optional als Häkchen».)* Man legt einen Punkt an, weil er erfasst werden soll. Ein Häkchen daneben wäre die Frage, warum man einen Punkt anlegt, den niemand ausfüllen muss — und jeder ausgeschaltete eine Lücke, die erst später auffällt. |
| **Ein Erfassungspunkt-Typ ist eine Datei, keine Zeile in einer Liste** | Ein Typ ist **Verhalten** (prüfen · fehlt der Wert · bewerten), nicht nur ein Wort. Als `if/else` verteilt sich das auf drei Stellen, von denen man die dritte vergisst. |
| **Der Artikel entsteht erst bei seiner Freigabe** | Dieselbe Regel wie beim Auftrag (§6.1) und aus demselben Grund. Ein Artikel, der schon eine Objektnummer hat, aber nichts erzeugen kann, ist ein Datensatz mit einer Zusage, die er nicht halten kann. |
| **`articles.status` kennt nur noch `released` und `inactive`** | `draft` hatte keinen Zustand mehr zu beschreiben: vor der Freigabe gibt es keine Zeile. Vorgefundene Entwürfe (Ergebnis des behobenen Fehlers) werden **inaktiv** — nicht gelöscht, denn ihre Objektnummer ist vergeben. |
| **Der Erzeugungsprozess ist nach der Freigabe nicht mehr änderbar** | Er entsteht mit dem Artikel; es gibt keinen Endpunkt, der ihn danach anfasst. Ein «Modul nachträglich hinzufügen» wäre eine Tür in einen Datensatz, der bereits Aufträge speist — und die Kopien in laufenden Aufträgen trügen einen Stempel, der nicht mehr stimmt. |
| **Reiter-Name «Erzeugungsprozess»** | Sagt, wofür der Prozess da ist, und lässt Platz für eine zweite Art Vorlage. |
| **Mehrere Definitionszeilen sind erlaubt** | Aber nur mit Herkunft `Lager`: «Neu» steht für sich allein (#693, siehe unten). |
| **Ein Auftrag hat EINEN Prozess** | Bringen zwei `Neu`-Zeilen verschiedene Vorlagen mit, ist das ein harter Fehler mit Klartext-Grund. Welcher gälte, kann das System nicht entscheiden — und raten wäre hier besonders teuer. |
| **Die gespiegelte Vorlage ist im Entwurf NICHT editierbar** | Ein Versionsstempel auf etwas, das man danach ändert, wäre eine Behauptung. Geändert wird am Artikel. Ein reiner `Lager`-Auftrag bleibt frei modellierbar. |
| **Menge 0 gibt es nicht** | Weder für `Neu` noch für `Lager`. Eine Zeile ohne Stück bewegt nichts, und die Freigabe verlangt ohnehin mindestens eine Einzelinstanz (§6.2). Wer nur modellieren will, tut das am Artikel. |
| **Grosse Mengen werden GEZÄHLT, nicht aufgelistet** | Das Diagramm zeigt je Zustand eine Pille mit Anzahl (`unit_groups`, eine SQL-Gruppierung); die Nummern holt `GET …/units`, wenn jemand aufklappt. Die Historie ist auf 200 Einträge gedeckelt **und weist das aus** — eine stumm gekappte Liste sähe aus wie die ganze Wahrheit. Die Datenhaltung bleibt pro Einzelinstanz; es gibt kein Aggregat-Feld. |
| **`order_lines` wird festgeschrieben** | Nicht weil eine Ansicht sie bräuchte, sondern weil die **Herkunft** sonst verloren ginge: dass diese drei Stücke erzeugt und jene zwei geholt wurden, steht hinterher nirgends im Bestand. |
| **Die Journey meint das STÜCK, nicht den Artikel** | Zwei Aufträge sind Nachbarn, wenn sie dieselbe Einzelinstanz nacheinander bearbeitet haben (§7.4). «Derselbe Artikel» wäre eine andere Frage — und eine, die der Bestand beantwortet. |
| **Mehrere Nachbarn: nach Stückzahl absteigend** | Der Hauptstrom zuerst. Bei Gleichstand die Objektnummer — eine willkürliche, aber stabile Reihenfolge ist besser als eine wechselnde. |
| **Ein gelöschter Nachbar fällt aus der Liste** | Statt als Zeile mit leerem Namen zu erscheinen. Eine Zeile, die auf nichts zeigt, ist schlimmer als keine Zeile. |
| **Fehlermeldungen sagen was und wo** | Ein `RequestValidationError`-Handler an EINER Stelle übersetzt jeden Eingabefehler in Klartext und nennt den Feldpfad («Prozessschrittmodule → 1 → Modultyp: fehlt»). Rohe Validator-Texte gehen ins Log. Ein Feld ohne hinterlegte Bezeichnung erscheint mit seinem technischen Namen — unschön, aber ehrlich und auffällig; eine erfundene Übersetzung wäre schlimmer. |
| **Die Rückführung wird bei der DEFINITION entschieden** | Sie steht als Frage an der Zeile, sobald ein gewähltes Stück in einem anderen Auftrag aktiv ist («kehrt zurück» / «bleibt hier»), und wird bei der Freigabe zu `return_to_order_id`. Nachträglich umschaltbar wäre sie nicht: der Hauptauftrag richtet sein Verhalten daran aus, sobald das Stück weg ist. |
| **Zwei Ereignisarten für den Wechsel: `handover` und `return`** | Ein Stück, das den Auftrag wechselt, ist keines der drei bestehenden Ereignisse. Ohne eigene Art müsste man den Auftragswechsel aus einem `step` erschliessen, das gar keines ist. Der **Eintritt** in den Abweichungsauftrag bleibt dagegen ein gewöhnliches `start` — sein `status_before = Im Prozess` **ist** das Merkmal (§12.2), eine vierte Art wäre dieselbe Aussage doppelt. |
| **Beim Ausscheren wechselt der Status NICHT** | Das Stück bleibt `Im Prozess` — es ist ja weiterhin in Arbeit, nur woanders. Ein Zwischenstatus («ausgeschert») wäre ein Zustand, den §5.2 nicht kennt, und er müsste beim Zurückkommen wieder zurückgenommen werden. |
| **Höchstens 3 Nachbarn voll, der Rest als Zähler** | Abschneiden statt gruppieren: eine Gruppe müsste einen gemeinsamen Nenner behaupten, den es bei Abweichungen nicht gibt. Der Zähler nennt die **Gesamtzahl** — eine stumm gekappte Spalte sähe aus wie die ganze Wahrheit. |
| **Die Sperre bei begonnener Eingabe sitzt in der Oberfläche** | Sie kann nirgends sonst sitzen: eine nicht bestätigte Eingabe existiert weder in der Datenbank noch im Log. Die **Regel** wohnt trotzdem am Modultyp (`Module.units_may_leave`, §12.7) — dort, wo sie beantwortet wird, sobald ein Modul mit Aussenwirkung existiert. |
| **Ein Zustandspunkt heisst nach dem Modul, vor dem er liegt** | Er braucht keine eigene Identität: `current_step_id` beantwortet «wo steht dieses Stück» bereits. Damit ist der Anker der Abzweigung berechenbar statt suchbar — und der Rückfall «gibt es den Punkt nicht, nimm das Modul» entfällt ersatzlos. |
| **Ein Abweichungsauftrag kann an mehreren Punkten ansetzen** | Darum eine Liste. Zwei rückführende Abweichungen am selben Punkt bleiben dagegen im Gleichschritt — die Sperre (§12.6) sorgt dafür; zwei **verschiedene** Punkte entstehen erst über eine gekappte. |
| **Die Bezeichnung eines Erfassungspunktes bleibt** | Sie ist nicht der eliminierte Name (das war der **Modul**name, #682/#686), sondern die **Frage, die im Prozess gestellt wird** — ohne sie steht dort ein Daumen hoch/runter ohne Text. Verlangt wird sie bei der **Freigabe**, nicht im Schema: der Entwurf legt den Punkt beim Klick an und füllt ihn beim Tippen. |
| **«Neu» steht für sich allein** | Ein Erzeugungsauftrag fährt die Vorlage genau dieses Artikels; ihr Versionsstempel gilt nur für seine Stücke. Die Regel liest sich von beiden Enden gleich: mit «Neu» kommt keine zweite Zeile dazu, und zu einer zweiten Zeile lässt sich «Neu» nicht wählen. *(Ersetzt die frühere Annahme «Artikel A `Neu` + Artikel B `Lager` ist ein normaler Fall».)* |
| **Ein Modul startet eingeklappt, ausser es ist dran** | Im laufenden Auftrag ist das «dran» das aktive Modul, im Entwurf das zuletzt angelegte – dieselbe Aussage, zwei Orte. |
| **Der Kopf löst die Typ-Identität selbst auf** | Symbol, Farbfamilie und Eyebrow kommen aus `TYPE_META`; die Aufrufer können sie nicht mehr übergeben. Der runde Symbol-Kasten beim Benutzer ist die eine **Form**regel, die vom Typ abhängt – sie steht in derselben Komponente, damit keine Aufrufstelle sie neu erfindet. |

---

## Anhang — Was aus dem Vorgängersystem NICHT übernommen wird

Zur Klarstellung, weil es in der Historie ausführlich dokumentiert ist und verlockend
nah liegt:

Reservierung · Anteil · Ausleihe und Rückgabe · Unterdeckung mit Antwortlogik ·
Material-Journal als Mengenbuchhaltung · Bereitstellung als abgeleiteter Unter-Auftrag ·
Nachschub-Pegging · Abweichung als Mengen-Entzug.

Alles davon existierte, weil eine Instanz eine **Menge** war und ein Auftrag seine Menge
zur Laufzeit verlieren konnte. Beides gibt es nicht mehr. Wer eines dieser Konzepte
wieder braucht, hat vermutlich §2.1 oder §3 aufgeweicht.
