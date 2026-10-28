# PROCESS_CORE — die Grundlogik des Prozesses

> **Verbindlich und systemweit.** Wer ein Prozessschrittmodul baut, hält sich hieran.
> Was hier nicht steht, ist nicht entschieden — und wird nicht erfunden.
>
> Stand: Oktober 2026. Einzelinstanz-Modell, Entscheide A1–A6; §1–§12 sind gebaut. Fünf
> Prozessschrittmodule: **Datenerfassung** (§9.0–§9.3, §9.5) · **Aussondern** (§9.4) ·
> **Verbrauch** (§9.6) · **Bewegen** (§9.8) · **Zahlung** (`beleg`, §9.15). Entfernte Module
> stehen in §9.9/§9.9a/§9.12–9.14 als Verweis auf `docs/attic.md`. Wie das Prozessbild
> gezeichnet wird, steht in `docs/prozessbild.md`; wie die Regeln entstanden sind, in
> `docs/history/`.

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

Die Module werden **einzeln definiert** (§9).

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

Eine Definition, die nach der Freigabe nicht mehr wackelt, macht eine ganze Klasse von
Fehlern unmöglich (zwei Aussagen über dasselbe Stück durch umgehängte Anteile, gekürzte
Reservierungen) — statt sie zu bewachen.

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
  Sonst hebelt der erste Parallelzugriff sie aus (§11.2).
- **Folge, ausdrücklich gewollt: Reservierung, Anteil und Unterdeckung entfallen
  ersatzlos.** Nichts davon wird gebaut, auch nicht vorbereitend.
- Solange ein Stück in einem Auftrag steckt, ist es für jeden anderen tabu. **Es gibt
  keine Ausnahme** — auch der Abweichungsauftrag (§12) ist keine: er **entzieht** das
  Stück dem laufenden Auftrag, statt es ein zweites Mal aktiv zu machen.

### 3.1 Wann wird ein Stück wieder frei?

1. **Normalfall:** Ein Stück wird frei, sobald es **das Ende-Objekt passiert** hat — nicht
   erst, wenn der Auftrag abgeschlossen ist. Der Auftrag ist abgeschlossen, wenn alle
   seine Stücke das Ende passiert haben; das ist eine **Folge**, keine eigene Regel.
2. **Ausgang:** ein terminales Modul (§4.6) schliesst die Zugehörigkeit ebenso.
3. **Abweichung:** ein anderer Auftrag entzieht das Stück (§12). Eine Abbruch-Funktion
   gibt es nicht: abgebrochen wird ein Auftrag, indem ihm eine Abweichung alle Stücke mit
   gekappter Rückführung entzieht (`SYSTEM_LOGIC.md` §4.4) – das zwingt dazu, ihr
   Schicksal zu regeln.

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

Der Endzustand ist ein **Wert des Ende-Objekts**, heute für jeden Auftrag `Freigegeben`
— ein Stück ist danach wieder verfügbar. Er darf **an keiner zweiten Stelle** hart codiert
werden. Kein UI, keine Auswahl: der Wert existiert, er ist nicht wählbar.

**Eine Ausnahme liest das Ende-Objekt selbst, statt sie zu speichern:** ein Stück, das
einer anderen Partei **gehört**, wird am Ende **`Verkauft`** statt `Freigegeben`
(`process._finish`). Wem es gehört, ist eine Ableitung aus dem jüngsten nicht stornierten
Zahlungsmodul, das es passiert hat (`voucher.sold_units`, §9.15). Ein Stück, das in seinen
Quell-Auftrag zurückkehrt, bleibt `Im Prozess`.

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
Stücke **einer** Instanz ab; `confirm_step` ist darum ein **Teil**-Abschluss und gibt
zurück, was er bewirkt hat (`{moved, held, result}`).

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

**Es gibt genau EINE Option, und das ist der Abweichungsauftrag.** Auch der ungeprüfte
Rest wird so behandelt: ein Auftrag über die übrigen Stücke, mit der Stichprobe, die man
dort wählt — eine eigene «100 %-Kontrolle» daneben wäre ein zweiter Weg zum selben
Ergebnis.

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

Eine Sperre bräuchte einen Schlüssel – einen zweiten Weg neben der Erfassung, mit der
Frage, wer ihn drehen darf. Solange das Urteil selbst der Ausweg ist, gibt es diese Frage
nicht.

Daraus folgt eine harte Regel für die Oberfläche: **der Haltezustand steht NEBEN dem Weg
nach vorn, nie an seiner Stelle.** Ein Modul, das bei `held` Formular und Scan-Knopf durch
die Entscheidung ersetzt, erfindet eine Sperre ohne Schlüssel, die es im Dienst nicht gibt.
Wächter:
`test_capture_module.test_a_hold_is_never_a_dead_end` und
`test_source_process.test_a_hold_is_shown_beside_the_way_forward_not_instead_of_it`.

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

**Warum das eine EIGENSCHAFT ist und keine Regel im Editor.** Einmal deklariert, dreimal
gelesen: der Editor blendet aus, die Freigabe weist ab, das Bild endet. Der Editor allein
wäre eine **Bitte**, die Freigabe allein meldete es erst am Schluss. Ein neuer Modultyp mit
`terminal = True` erbt alle drei Wirkungen, ohne eine Zeile dafür.

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
| `Verbaut` | Grün | Stück | history | Steckt in einem anderen Stück (§9.6). Nicht endgültig: das Greifen IST der Ausbau. |
| `Verkauft` | Grün | Stück | history | Gehört einer anderen Partei (§4.2, §9.15). Behält seinen Ort; das Greifen IST die Retoure. |
| `Verschrottet` | Rot | Stück | history | Aus dem Verkehr gezogen und **physisch weg**. Endgültig. |
| `Abgeschlossen` | Grün | Auftrag | — | **Den definierten Weg zu Ende gegangen.** |
| `Abgebrochen` | Rot | Auftrag | — | Ziel nicht mehr erreichbar. |
| `Inaktiv` | Rot | Artikel | — | Ausser Betrieb: erzeugt nichts Neues. **Abgeleitet** aus `replaced_by_id` (§5.5). |

Dieselbe Liste trägt die Zustände eines **Dokuments** (Freigegeben · Unterschrift angefragt ·
Abgelehnt · Gelöscht, abgeleitet – `docs/dokumente.md`); sie gehören nicht zum Prozess.

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
  `routers/orders`). Ein eigenes Feld dafür wäre eine zweite Antwort auf dieselbe Frage.
- **nicht** die Farbe: der Ton sagt «gut · offen · Problem», `terminal` sagt «gibt es einen
  Weg zurück» – `Verbaut` ist aufhebbar **und** grün (`SYSTEM_LOGIC.md` §1.1).
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
«Zählt dieser Zustand zum aktuellen Bestand?» ist ein Feld am Status (`stock`), und sein
**Fehlen ist ein Fehler beim Start** (`_check`), kein stiller Standardwert – eine eigene
Liste daneben vergässe man beim nächsten neuen Zustand. Zur Laufzeit reist die Antwort als
`StockState.stock` mit den Daten – die Oberfläche entscheidet nichts und meldet einen
Zustand ohne Zuordnung, statt ihn zu raten.

**Mehr nicht.** Die früher vorgeschlagenen Werte sind zurückgezogen, jeder mit Grund:

| zurückgezogen | Grund |
|---|---|
| `verfügbar` | wäre ein **zweites Wort für `Freigegeben`** — genau die Doppelung, die dieses System überall abbaut |
| `gebunden` | war der Reservierungs-Begriff. **A3 streicht Reservierung ersatzlos** — der Wert wäre vorbereitendes Bauen für etwas, das es nicht geben soll |
| `verbraucht` | Endzustand. **A6 sagt: heute genau einer** – und das Aussondern (§9.4) hat seine zwei eigenen, weil es sie wirklich braucht |

**Eine frisch angelegte Einzelinstanz ist `Freigegeben`** (`INITIAL_UNIT_STATUS`): sie ist
einsatzbereit und in keinem Auftrag – genau das heisst das Wort.

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
`CATALOG`. Der Trigger wird aus genau dieser Liste erzeugt (`statuses.terminal_guard_sql`)
und bei **jedem Start** nachgezogen (`main.lifespan` → `_sync_database_rules`), damit die
Datenbank von ihr nicht abweichen kann.

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

Eine Regel, die erst beim letzten Klick nein sagt, ist sichtbar erst, wenn man alles getan
hat. **`Gesperrt` ist nicht terminal** und bleibt greifbar: das Greifen IST das Aufheben
(§5.2).

**Warum so tief, und nicht im Modul.** Der Schreiber, der Schaden anrichtet, ist oft keiner
der Dienstpfade, sondern ein Skript, eine Migration oder eine Reparatur mit einer
veralteten Statusliste. Gegen ihn hilft nur die Tabelle selbst.

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

### 5.5 Ausser Betrieb nehmen und ersetzen — der Lebenszyklus des Artikels

> ►►► **«Ausser Betrieb» ist keine eigene Angabe — es ist die Folge des Ersetzens.** ◄◄◄
>
> Es gibt genau **eine** Angabe, ``articles.replaced_by_id``, und der Zustand fällt aus ihr
> heraus (``Article.status`` ist eine **Projektion**, keine Spalte). Einen Schalter
> «inaktiv» gibt es nicht: zwei Angaben über dieselbe Sache liessen einen Artikel ohne
> Nachfolger an einem Schalter hängen, den niemand mehr findet.
>
> **Der eine Preis, ausdrücklich abgenommen:** ein abgelöster Artikel erzeugt nichts Neues
> mehr — auch nicht als **Ersatzteil**; wer den Vorgänger weiterbauen will, ersetzt ihn
> nicht. Bestehende Stücke bleiben unberührt: «ab Lager» ist weiterhin erlaubt.

**Die Wirkung ist eine einzige und steht an einer Stelle** (``articles.may_create``): ein
Artikel ausser Betrieb **erzeugt nichts Neues**. Alles andere bleibt: bestehende Stücke
laufen weiter, laufende Aufträge laufen zu Ende (ihr Prozess ist eine eingefrorene Kopie,
§6.5), und ein Auftrag «ab Lager» darf sie weiterhin greifen — sonst würde jedes Stück
eines ausgelaufenen Artikels zur Leiche, die sich nicht einmal mehr aussondern liesse.

#### Was das für die Stücklisten ringsum heisst: **melden, nicht erzwingen**

Ein Artikel, dessen Stückliste einen ausser Betrieb genommenen nennt, bleibt
**erzeugbar**, solange Restbestand da ist — das ist die Wirklichkeit, und sie zu verbieten
wäre eine Regel gegen den Betrieb. Er **sagt es aber selbst**: die Auskunft steht am
Datensatz (``services/bom.py`` → ``ArticleResponse.bom``), transitiv über beliebig viele
Stufen, mit dem **Weg** dorthin und — falls es einen gibt — dem **Nachfolger**. Die Kaskade
entsteht damit beim **Lesen** und reicht genau so weit, wie jemand hinschaut; markiert oder
gespeichert wird nichts.

Dieselbe Ableitung beantwortet die Gegenrichtung: **wer verbaut mich?** Das ist die Antwort
auf «was mache ich kaputt, wenn ich diesen Artikel ausser Betrieb nehme» — und sie steht
**am Datensatz, nicht in einem Dialog**: ein Dialog zeigt sie einmal, dem, der klickt; der
Datensatz zeigt sie immer, allen. Deshalb gibt es zur Statusaktion **keine Rückfrage**.

> Gelesen werden ausschliesslich die **Artikel-Vorlagen**
> (``article_process_steps.config.lines``), nie die eingefrorenen Kopien eines laufenden
> Auftrags: ihn von aussen zu bewerten hiesse, eine Definition zu beurteilen, die längst
> festgeschrieben ist. Gefiltert wird in der Datenbank (JSONB-Containment ``@>``) —
> im Python nachzufiltern hiesse, für jede Artikel-Anzeige sämtliche Vorlagen zu laden.

#### Ersetzen ist eine Angabe an der Anlage des NACHFOLGERS

Ein Artikel wird nicht versioniert, er wird **ersetzt** («Kein Ersetzen zur
Laufzeit», §2.2, gilt für die Einzelinstanzen eines laufenden Auftrags – nicht für die
Stammdaten). Eine Änderung an Spezifikation
oder Prozess ist ein *anderer* Artikel; der alte bleibt stehen, weil seine Stücke, seine
Aufträge und seine Nachweise auf ihn zeigen. Was die beiden verbindet, ist genau eine
Angabe: ``articles.replaced_by_id`` (alt → neu).

Gesetzt wird sie bei der **Anlage des Nachfolgers** (``ArticleCreate.replaces_object_id``)
— dort hat sie ihren einen Moment, und dort wird sie auch gedacht: man legt den neuen an
und sagt dabei, welchen er ablöst. Ein Feld am Vorgänger («wer löst mich ab?») wäre
jederzeit änderbar und damit eine zweite Wahrheit über dieselbe Kette.

**Ersetzen nimmt ausser Betrieb** — das ist keine zusätzliche Wirkung, sondern die
Bedeutung: wer abgelöst ist, erzeugt nichts Neues mehr. Der Zustand **ist** die Projektion
dieser einen Angabe. Ein Vorgang, ein Aufruf, eine Transaktion.

Drei Ablehnungen, jede mit ihrem Grund im Satz (``articles.assert_replaceable``):

| Lage | Antwort |
|---|---|
| Ein Artikel ersetzt **sich selbst** | abgewiesen — eine Kette im Kreis hat keinen neuesten Stand |
| Der Vorgänger ist **bereits ersetzt** | abgewiesen, **unter Nennung** des bestehenden Nachfolgers |
| Der Nachfolger führt über seine Kette **zum Vorgänger zurück** | abgewiesen — daraus entstünde ein Kreis |

Gelesen wird die Kette **zyklensicher und gekappt** (``chain_of``, ``MAX_CHAIN``) — dasselbe
zweite Netz wie beim Lesen einer Stückliste oder einer Ortskette: was in den Daten nicht
vorkommen darf, fängt man beim Lesen ab und nicht erst, wenn eine Ansicht hängt.

**Die Gegenrichtung ist eine Abfrage, keine zweite Spalte** (``predecessor_of``): der
Rückweg ist die Umkehrung derselben Kante, und eine gespiegelte Spalte wäre die zweite
Stelle, an der die Kette auseinanderläuft.

#### Darstellung

Reihe (ersetzt / ersetzt durch), «wird verbaut in» und die gemeldeten Lücken stehen als
**ein schmaler Streifen über der Spezifikation**; im **Anlage-Modus** steht dort die
Auswahl «Ersetzt Artikel». Der Streifen lädt sich selbst über das `GET`-Detail – ein Pfad
liefert das Umfeld. Wächter: ``tests/test_article_lifecycle.py``.

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

Ein Artikel mit Objektnummer, aber leerem Prozess wäre ein Datensatz, der eine Zusage
macht, die er nicht halten kann.

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
Prozess wird nicht wieder zum Entwurf. Was nicht mehr passt, geht in eine Abweichung
(§12), nicht in eine Änderung.


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

### 8.1a Das Bild — Zeichenregeln in `docs/prozessbild.md`

Wie das Prozessbild entsteht und gezeichnet wird, steht in **`docs/prozessbild.md`**
(§8.1a′ Graph vom Server · §8.1a″ Ports, Kanäle, ein Linien-Layer · §8.1a‴
Kreuzungsfreiheit · §8.1a Liniensystem · §8.1b drei Spuren · §8.1c Entwurf · §10.2
Technologie). Der Kern in drei Sätzen: **der Server liefert einen Graph** (`services/flow.build`,
Knoten `start · module · end · fork · join`, eine Position ist immer eine Kante),
abgeleitet aus dem **Ereignis-Log**, nicht aus dem Zustand; **eine Linie ist kräftig, wenn
laut Log mindestens eine Einzelinstanz diese Kante genommen hat**, sonst Haarlinie, und
eine einmal kräftige Kante wird nie wieder schwach; **die Oberfläche layoutet und zeichnet**
(`process-flow.polyPath`, ein Generator für jede Linie) und leitet nichts ab. Verletzte
Invarianten stehen als `FlowGraph.problems` rot im Bild, statt eine falsche Zeichnung
anzubieten.

### 8.2 Artikel-Reiter «Erzeugungsprozess» — die Vorlage

Neben «Spezifikation» trägt der Artikel den Reiter «Erzeugungsprozess»:

- Inhalt: **dieselbe** Darstellung wie im Auftrag (`ProcessColumns`, Modus `definition`)
  und **derselbe** Modul-Editor. Kein Nachbau — der Schnitt aus §8.1 hat gehalten.
- Dort wird **ausschliesslich der Prozess definiert**, sonst nichts.
- **Kein Anstossen von Prozessen, keine Einzelinstanzen, keine Ausführung.** Das ist
  keine bewachte Regel, sondern eine fehlende Tür: die Vorlage liegt in einer eigenen
  Tabelle (`article_process_steps`), und es gibt keinen Endpunkt, der sie ausführt.
- Sie entsteht mit dem Artikel (ein `POST`, Anlegen = Freigeben) und ist danach nicht
  mehr änderbar.

**Kopie, nicht Verweis.** Bei der Freigabe eines Erzeugungsauftrags wird die Liste in
`process_steps` **kopiert** und mit `Article.process_version` gestempelt
(`process_steps.source_article_id`/`source_version`). Ein Verweis hiesse, dass eine
spätere Artikeländerung laufende Aufträge rückwirkend umschreibt — das widerspricht
«eingefroren» (§6.4).


---

## 9. Die Prozessschrittmodule

Es gibt heute **fünf**: die **Datenerfassung** (§9.0–§9.3, §9.5), das **Aussondern**
(§9.4), den **Verbrauch** (§9.6), das **Bewegen** (§9.8) und die **Zahlung** (§9.15). Was
ein Modultyp ist, steht in `domain/modules.py` (`MODULES`); ausgeführt wird jeder über
einen Endpunkt (`…/steps/{id}/confirm`, `process.confirm_step`).

**Was alle gemeinsam haben, steht nicht bei ihnen**, sondern im Rahmen: der Halt bei
«nicht bestanden» (§4.5), die Verifikation vor der Eingabe (§4.4), die Stichprobe (§9.3),
der Ausgang (§4.6) — und das **Protokoll** (§9.7). Ein neuer Modultyp erbt sie ohne eine
eigene Zeile.

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

*Einen Typ «Objekt scannen» gibt es nicht (`docs/attic.md`); dass es damit keinen
Nachweis für **Werkzeug und Prüfmittel** gibt, steht als bewusst offener Punkt in
`SYSTEM_LOGIC.md` §5.9.*

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

**Und die Zahl der SCANS folgt der Ziehung, nicht umgekehrt.** Ein Scan für eine Instanz
ohne gezogenes Stück bestätigte nichts – er wäre nur der Weg, das ungezogene Stück
weiterzubewegen.

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

Ein Wertesatz je Bestätigung, kopiert auf jedes gezogene Stück, wäre eine **Behauptung**:
zwei Zeilen, gemessen eine. Ein Nachweis mit mehr Zeilen als Messungen ist keiner.

**Die Nutzlast ist darum zweistufig**: Nummer der Einzelinstanz → (Punkt → Wert). Der
Server verlangt **Deckung in beide Richtungen** (`process._captures_for`) – ein Satz für
ein nicht gezogenes Stück ist ein Nachweis über etwas, das hier nie geprüft werden
sollte; ein fehlender ist eine Lücke, die hinterher aussieht wie «durchgelaufen, nichts
gemessen».

**Das Urteil hängt am Stück**, der Halt an der Instanz: jede Zeile trägt ihr eigenes
Ergebnis; fällt **eines** durch, bleibt die ganze Instanz stehen (§4.5) – eine
durchgefallene Stichprobe ist nicht mehr repräsentativ.

**Und das gilt bis in den Log hinein.** Das `capture`-Ereignis (§11.3) trägt je Stück
sein **eigenes** Ergebnis, nicht das der Bestätigung: sonst stünde bei 4 von 5 bestanden
auf allen fünf Zeilen «nicht bestanden», und welches Stück das schlechte war, liesse sich
nicht mehr lesen. Der Halt gehört der Instanz, das Urteil dem Stück.

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
verschwände. Dieselbe Regel wie im Prozessbild (`docs/prozessbild.md` §8.1a): *eine Ansicht der Vergangenheit
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

#### Material am richtigen Ort — dieselbe Aussage, eine Spalte weiter

Bestand reicht nicht nur zahlenmässig: er muss **dort** liegen, wo verbaut wird. Bis
hierher war `instance_units.place_*` ein Zeiger, den **keine Regel liest** (§9.8) — mit
diesem Modul wird er zur **Voraussetzung**, und zwar nur hier.

**Wo das Material liegen muss, ist abgeleitet, nicht konfiguriert.** Der Modultyp
deklariert die Frage (`Module.material_place = AT_PRODUCT`), beantwortet wird sie aus dem
**Ort der Produkte**: die Komponenten müssen dorthin, wo verbaut wird. Ein eigenes
Ortsfeld am Verbrauchsmodul wäre eine zweite Ortsangabe neben dem Ziel des
Bewegen-Moduls, und zwei können sich widersprechen; so entsteht die Anforderung von
selbst und niemand modelliert sie.

**«Am Ort» heisst in der KETTE, nicht «identische Nummer».** Die Schraube in der Kiste,
die auf Werkbank 5 steht, **ist** auf Werkbank 5 (`places.at_holder`). Die naive Lesart
wäre in der Praxis fast immer falsch: Material steht in Behältern, und der Behälter steht
am Arbeitsplatz.

**Wo nichts steht, wird nichts verlangt.** Liegen die Produkte nirgends — oder an
*verschiedenen* Orten — gibt es keine Anforderung. Eine erfundene sperrte das Modul auf
einen Ort, den nur ein Teil der Stücke teilt; und ohne diese Regel hielte die Änderung
jeden bestehenden Ablauf an, denn ein frisch erzeugtes Stück liegt nirgends.

**Nichtverfügbarkeit bleibt kein Zustand.** «Am falschen Ort» ist dieselbe Aussage wie
«zu wenig da», eine Spalte weiter: `StepNeed` nennt jetzt *gebraucht · verfügbar ·
**davon hier*** und den Arbeitsort dazu. Zwei Formen einer Regel — `needs` als Auskunft,
`plan` als Riegel (409 mit dem Ort im Text, bevor etwas geschrieben ist). Ein milderer
Riegel wäre eine Zeile, die «0 hier» meldet, und ein Modul, das trotzdem verbaut.

**Der Weg dorthin ist ein ganz gewöhnlicher Auftrag** mit einem Bewegen-Modul, dessen
Ziel der Arbeitsort ist — vorgewählt angeboten, **nie automatisch angelegt**. Dieselbe
Mechanik wie §4.5 bei «nicht bestanden»: das System bietet an, es legt nicht an. Es kann
nicht wissen, ob man lieber eine andere Kiste nimmt, das Werkstück zur Maschine bringt
oder die zwanzig Meter selbst läuft.

**Und die Sperre fällt heraus, statt gebaut zu werden.** Solange der Transportauftrag
läuft, ist das Stück `Im Prozess` mit offener Zugehörigkeit — der Verbrauch nimmt nur,
was frei ist, kann es also gar nicht greifen. Ist der Transport durch, ist es frei **und**
liegt richtig, und das Modul fragt beim nächsten Versuch neu. Keine Verknüpfung, kein
Wartezustand, keine Zeile Wartelogik: die bestehende Exklusivität tut es.

Drei Wege stehen damit an der Zeile, und alle drei gibt es schon: *eine andere Instanz
wählen* · *holen lassen* · *Nachschub anlegen*. Angeboten wird nur, was gerade Sinn ergibt.

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


### 9.8 Das Modul «Bewegen» — und der Ort darunter

Einzelinstanzen von A nach B bringen. Ein **Durchläufer**: `Im Prozess` → `Im Prozess`,
nicht terminal. Ein Ort ist kein Zustand — er ändert nie den Status und nie die
Zugehörigkeit, und **genau deshalb muss keine andere Regel im System von diesem Modul
wissen.** Das ist die Robustheitsgarantie, konstruktiv statt geprüft.

#### Der Ort: ein Zeiger, sonst nichts

`instance_units.place_object_id` — die Objektnummer des **Halters**. Kein Typfeld
daneben: Objektnummern sind systemweit eindeutig, der Typ ist ableitbar
(`objects.resolve_object_type`). Was es nicht gibt, kann nicht veralten.

**Gehalten wird die Einzelinstanz, Halter ist eine Objektnummer.** Diese Asymmetrie ist
kein Kompromiss, sondern die einzig mögliche Aussage: eine Einzelinstanz zieht bewusst
keine Objektnummer (§2.2), es kann für sie gar kein Etikett geben — also kann sie weder
gescannt noch als Ziel gewählt werden. Was man scannt, ist das physische Ding, und das
ist die **Instanz**: die Kiste, das Regal, die Palette. Halter ist damit alles mit einer
Nummer: **Instanz** (Regal, Behälter, LKW), **Benutzer** (Mitarbeiter, Kunde, Spediteur),
**Unternehmen** (Werk Nord, Hauptsitz). Kein neuer Datensatztyp, keine Whitelist.

#### Zwei Arten von Halter — die Genauigkeit ist die der Quelle

`place_object_id` trägt einen **gescannten** Halter (Instanz · Benutzer · Unternehmen);
`place_unit_id` einen **Träger**: das eine Stück, in dem dieses Stück steckt. Ein `CHECK`
erzwingt, dass höchstens eines gesetzt ist — der Ort bleibt **eine** Aussage, sie hat nur
zwei mögliche Formen.

Das ist keine Doppelung, sondern die einzig ehrliche Aufteilung: **was man scannt, ist ein
Etikett, und ein Etikett hat die Instanz** — feiner geht es nicht, ohne zu raten, welches
Stück der Charge gemeint war. Beim **Verbauen** dagegen kennt das Modul das Stück genau
(`consumption.plan` teilt je Produkt-Stück zu), und diese Genauigkeit wegzuwerfen wäre
eine erfundene Unschärfe: «in Instanz 100000123» wären bei einer Charge sechshundert
Getriebe, also eine Gruppe und kein Ort.

**Und weil das Stück auf den Träger zeigt und nicht auf dessen Anschrift, wandert es
mit**: wird das Getriebe bewegt, ist die Schraube darin automatisch mitbewegt — genau wie
eine Schraube in einer Kiste. Ein eingefrorener Ort wäre in dem Moment gelogen, in dem
das Getriebe die Werkbank verlässt.

**Nicht die Genealogie.** Der Log sagt, *worin* verbaut wurde (`payload.into`) —
unveränderlich, überlebt die Demontage. Diese Spalten sagen, *wo es jetzt liegt*, und
werden beim Ausbau geräumt. Dass die beiden auseinander laufen können, ist der Beweis,
dass es zwei Fragen sind (§9.6).

#### Jedes Stück behält seinen Ort – ausser es ist verschrottet

Die Regel für **jedes** Modul, ohne dass eines sie kennt (`process._pass`):

| Zustand | Ort |
|---|---|
| **Verschrottet** (endgültig) | keiner — es gibt das Ding nicht mehr; der Status IST die Wo-Antwort |
| **Verbaut** (Historie) | sein **Träger** — es liegt nicht im Regal, sondern in einem anderen Stück |
| **Verkauft** (Historie) | **bleibt** — es steht noch in der Halle, bis der Kunde es abholt (Bewegen) |
| **Gesperrt** (Bestand) | **bleibt** — es liegt im Regal, nur unbenutzbar |

Die Regel hängt am **Status** und steht an der einen Stelle, an der ein Status geschrieben
wird. Wer einen *neuen* Ort hat, setzt ihn im selben Zug — der Verbrauch seinen Träger.

**Der Ort hängt am Stück, nicht an der Gruppe.** Zwei Schrauben derselben Charge dürfen an
zwei Orten liegen — ein Stück, ein Ort; eine Standort→Menge-Map an der Instanz gibt es
nicht.

**`NULL` ist ein regulärer Zustand**, kein fehlender Wert: ein frisch erzeugtes Stück liegt
nirgends, bis ein Modul es irgendwohin bringt.

**Eine Spalte, keine append-only Tabelle** — weil die Vergangenheit schon woanders steht:
jede Bewegung läuft über `confirm_step` und schreibt dort ihren Eintrag in
`process_events`, mit Herkunft, Ziel und Transportart. Eine zweite Tabelle daneben wäre
eine zweite Wahrheit über denselben Vorgang. *Die Grenze ist benannt:* käme später ein
Ablegen **ausserhalb** eines Auftrags dazu, hätte genau dieser Weg keine Historie — dann
kommt sie dort dazu, und diese Spalte bleibt richtig.

#### Die eine Regel des sonst dummen Feldes: keine Zyklen

Läge Regal A im Behälter B und B im Regal A, liefe die Kette im Kreis — und mit ihr jede
Bestandsansicht. Zwei Netze, weil das erste nicht alles sieht: **verhindert beim
Schreiben** (`places.assert_placeable`: das Ziel darf nicht in dem liegen, was bewegt
wird, und nichts liegt in sich selbst) und **gekappt beim Lesen** (`seen` + `MAX_STATIONS`
— für Altbestand und alles, was an der Prüfung vorbei entstanden ist).

#### Die Kette

`Schraube › Behälter › Regal › Werk Nord` — von innen nach aussen, bis ein Halter eine
**Anschrift** trägt (Benutzer oder Unternehmen). Dort endet sie: das ist der Ort in der
Welt, alles davor ist die Verschachtelung darin. Eine Instanz gilt dabei als verortet,
wenn **alle** ihre Stücke am selben Halter liegen — das deckt den Normalfall (ein
serialisiertes Regal = ein Stück) mit ab, ohne ihn als Sonderfall zu behandeln, und
erfindet keine Antwort, wo es keine gibt.

**Aufgelöst wird je Halter, nie je Stück** (`places.chains_for`, stufenweise in Batches).
Sechzig Schrauben in einem Regal sind **eine** Kette; je Zeile aufzulösen wären es sechzig
mal Kettentiefe. Wächter: `test_move_module.test_the_chain_is_resolved_per_holder_not_per_piece`
zählt die Abfragen.

**Die Kette ist Dekoration, nie der Datensatz.** Scheitert ihre Auflösung (Altdaten,
gelöschter Halter), kostet das die Kette — die Ansicht bleibt lesbar.

#### Das Ziel ist optional — und das ist eine Aussage

Steht es in der Definition, ist der Ziel-Scan eine **Verifikation** dagegen: eine andere
Nummer wird abgewiesen, an der Ausführungsstelle und nicht nur im Dialog. Fehlt es, ist er
die **Wahl** — der Fall «bring es dorthin, wo gerade Platz ist», den eine Vorlage nicht
vorwegnehmen kann. Beide sind gültig, aber sie müssen **sichtbar** verschieden sein: ein
offenes Ziel, das aussieht wie eine Lücke, liest sich als Fehler in der Definition. Die
Karte sagt darum «wird beim Ausführen gescannt» statt gar nichts.

#### Ware zuerst, Ziel zuletzt

So arbeitet jedes Lagersystem beim Ein- und Umlagern (*scan item → scan destination bin*),
und der Grund ist physisch: **der Ziel-Scan ist die Quittung der Ablage.** Man hat das
Stück in der Hand, geht hin, legt ab, scannt — er passiert zuletzt, weil das Hinlegen
zuletzt passiert. Zuerst gescannt wäre er eine Absichtserklärung: zwischen «Ziel gescannt»
und «hingelegt» kann alles passieren, und der Nachweis behauptete etwas, das niemand
gesehen hat. (Beim **Kommissionieren** ist es umgekehrt — erst der Platz, dann die Ware.
Andere Operation: sie sucht, statt abzulegen.)

Kein neuer Mechanismus: die Scan-Sequenz ist genau dafür gebaut, und der Ziel-Schritt ist
einer mehr in derselben Liste. Der **Sammel-Scan** quittiert das Ziel **einmal** — eine
Fuhre geht an einen Ort; wer verschiedene Ziele hat, bestätigt einzeln.

#### Eine Spedition ist ein Einkauf

Wer eine Spedition beauftragt, legt ein Zahlungs-Modul (Ausgabe, §9.15) daneben; das
Bewegen-Modul weiss davon nichts – es bewegt. *Paket* und *Fracht* sind keine
Transportarten, sondern zwei Angebote desselben Einkaufs. Der frühere Einkaufs-Beleg am
Bewegen-Modul ist entfallen (`docs/attic.md`, «Die Handels-Module»).

### 9.9 «Ausliefern» — entfernt

Siehe `docs/attic.md` («Kleinere Entfernungen»). «Gehört jetzt jemand anderem» ist die
Folge aus Bewegen und Zahlung; `Verkauft` schreibt das Ende-Objekt (§4.2, §9.15).

### 9.9a «Beschaffen» und «Verkauf» — entfernt

Siehe `docs/attic.md` («Die Handels-Module»). Einkauf und Verkauf sind ein Zahlungs-Modul
(§9.15) neben den Modulen, die das Material bewegen.

### 9.12–9.14 «Zahlung (alt)» — entfernt

Siehe `docs/attic.md`; Wortlaut in `docs/history/2026-09-zahlungsmodul-vorgaenger.md`. Was
davon weiter gilt, steht in §9.15.

### 9.15 Das Modul «Zahlung» — der Beleg

> Schlüssel `beleg`. Fachkern `domain/voucher.py`, Dienst `services/voucher.py` (`VERBS`,
> `can`, `situation`), Papiere `services/voucher_docs.py` + `services/document.py`,
> Kundenseite `routers/beleg.py`, Liste `services/payment_list.py`, Karte
> `components/erp/beleg-work.tsx`. Tabellen `vouchers` · `voucher_lines` · `voucher_quotes`
> · `voucher_entries` · `voucher_documents`. Entstehung und frühere Fassungen §9.15a–s:
> `docs/history/2026-10-process-core-9-15-chronik.md`.

**Geld mit einer zweiten Partei, in beide Richtungen EIN Modul.** Einnahme ↔ Ausgabe ist
eine Einstellung (`Direction`), kein zweiter Modul-Schlüssel; Einkauf, Verkauf, eine
eingekaufte Spedition, Miete oder Gebühr sind derselbe Vorgang. Der Vorgang hängt am
**Schritt**, nicht am Auftrag: ein Auftrag kann eine Ausgabe und eine Einnahme tragen, eine
Anzahlung ist ein zweites Modul.

#### Stufen, Verben, Leiste

```
offer      Angebot      schreiben · anbieten (ask) · annehmen (agree)
agreed     Auftrag      → bill: Nummer, Betrag, Steuer, Fälligkeit werden eingefroren
billed     Rechnung     → Geld (pay · refund · writeoff · tip · reverse) · Mahnung · Ausfuhrnachweis
cancelled  storniert    Ausgang
```

- **Jedes Verb steht an EINER Stelle** (`VERBS`): Stufen, nötige Stammdaten, ob die
  Gegenpartei es darf, die Funktion. **`can` ist Auskunft UND Tor** – dieselbe Antwort zeigt
  die Knöpfe und weist eine Anfrage ab, für das ERP wie für die Kundenseite.
- **Erledigt ist abgeleitet** (`is_done`): gestellt ∧ Saldo 0 (∧ Ausfuhrnachweis bei Export).
  Eine Stufe «done» oder einen Knopf «abschliessen» gibt es nicht.
- **Die Leiste** (`situation`) nennt Stand, wer dran ist und die eine Handlung; sie ist nie
  leer ausser bei Erledigt/Storniert – ein Wächter prüft, dass jeder Zustand einen nächsten
  Schritt hat («keine Sackgasse»).
- **Jeder änderbare Wert wird sofort gespeichert** (Fristen, Währung, Aussteller,
  Lieferbedingung, Preis, Steuersatz, Zoll, Partei, Anschrift, Eigentum) – keiner lebt nur
  im Browser. **Geprüft wird beim Hinausgehen** (`ask`, `gaps`): was auf dem Beleg steht,
  ist Pflicht, und der Satz nennt die Position. Die Tönung im Browser ist die freundliche
  Hälfte derselben Regel.
- **Wählen ist nicht anbieten**: die Partei wählt `party` (sofort gespeichert), `ask` geht
  hinaus, `unask` nimmt beides zurück. Mögliche Parteien = zugelassene der Definition ∪
  gewählte ∪ angefragte (`_possible_parties`). Die eigene Gesellschaft ist nie Gegenpartei.
- **Was zu tun ist** (`config.instruction`, frei, leer = «gemäss Spezifikation») gehört dem
  Modul; **wie bestellen** (`config.parties[].ref`) der Paarung Modul × Partner und nur, wo
  wir bestellen (`Direction.party_ref`).
- **Gültigkeit** in Tagen ab «Anbieten» (Vorgabe 30); abgelaufen → «Erneut anbieten».
  **Angenommen wird nur die aktuelle Fassung** (`offered_hash`): wer danach ändert, bietet
  erneut an.

#### Die Stücke ziehen von selbst weiter – und das Eigentum wird abgeleitet

- **Die Stücke passieren das Modul von selbst** (`voucher.passable`,
  `process.advance_payments`): mit der Zusage, bei Vorauszahlung erst mit der vollen
  Zahlung. Einen «Bestätigen»-Knopf gibt es nicht (`PASSES_ITSELF`); der Status bleibt
  `Im Prozess`, ein Ort wird nicht gesetzt.
- **Eigentum** «geht an die Partei · geht an uns» ist eine **Pflichtwahl ohne Vorbelegung**
  (`ownership_problem`: ohne Wahl kein Anbieten, keine Zusage), eingefroren mit der Zusage.
- **Wem ein Stück gehört, ist eine Ableitung** (`voucher.sold_units`): das jüngste nicht
  stornierte Zahlungsmodul, das es passiert hat. Gelesen wird sie nur am Ende-Objekt
  (`process._finish`, §4.2): gehört es der Partei, wird es **Verkauft** (Historie, behält
  seinen Ort), sonst **Freigegeben**. Ein Storno wirkt damit von selbst; eine Retoure «an
  uns» gibt frei; eine Reparatur ohne Zahlungsmodul lässt Verkauftes Verkauft.
- **Passen die Stücke nicht mehr** (`units_problem`: ein eingefrorenes Stück hat den Auftrag
  verlassen, ohne das Modul zu passieren), bleibt nur «Stornieren»; die übrigen führt ein
  gewöhnlicher Abweichungsauftrag weiter.

#### Der Beleg IST die Rechnung – eine je Modul

- Nummer, Datum, Fälligkeit, Betrag und Steuer stehen **am Beleg** (`vouchers`), nicht in
  einer Forderungszeile. «Eine Rechnung je Modul» ist damit die Struktur, keine Regel.
  Rechnungsnummer `<Auftragsnummer>-<laufend>`.
- **Die Steuer wird eingefroren**, nicht nachgerechnet: eine spätere Änderung am Katalog
  ändert keine gestellte Rechnung.
- **Ein Wort für den Storno: «Stornieren»** (`revoke`), in jeder Stufe. Nach der Rechnung
  entsteht die **Gutschrift über die ganze Rechnung von selbst** (`credit_number`, eigene
  Nummer); «Rechnung zurücknehmen» gibt es nicht. Was bezahlt ist, geht über «Erstatten»
  zurück.
- **Eine Korrektur ist ein eigener Beleg in einem eigenen Modul** (`correct` →
  `corrects_id`), auch über Auftragsgrenzen: die Gutschrift gehört dorthin, wo die Ware
  zurückkommt, und ihre Positionen entstehen aus den Stücken, die zurückkommen. Die
  Warenlogik ist die Mengenkontrolle des Geldes.
- **Jede Zahl auf dem Beleg ist eine Menge**, nie negativ getippt. Ob ein Beleg mindert,
  sagt `corrects_id` (`minus`); die Wörter auf den Knöpfen sagen es («Gutschrift stellen»,
  «Erstattung erfassen», `charge_word`/`payment_word`). Wohin das Geld fliesst, ist
  `inbound` (= `collects != minus`) – es entscheidet über Zahlungsdienst und QR-Rechnung.

#### Geld, Zustand, Mahnung

- **Geld-Zeilen** (`voucher_entries`) haben eine Art: Zahlung (negativ = Erstattung) ·
  Ausbuchung (Grund aus fester Liste, Entgeltsminderung) · Trinkgeld (Entgelt). «Falsch
  erfasst?» bucht genau eine Zeile gegen. **Eine Referenz gehört zu genau einer aktiven
  Zahlung** (Unique-Index).
- **Drei Wege zum Geld**: bar · Überweisung (eine Auskunft: Bankverbindung, Referenz, Swiss
  QR-Rechnung `services/qrbill`) · Karte (eigene Bezahlkarte mit Stripe Payment Element,
  gebucht **nur vom Webhook**, zurück auf die Karte nur, was geschuldet ist;
  `docs/stripe-setup.md`). Welche Wege es gibt, sagt der Server (`_ways`).
- **Der Zustand einer Rechnung ist abgeleitet** (`invoice_state`, Toleranz `0.05`) aus
  Betrag und Rest: offen · teilweise · beglichen · überfällig · überzahlt · storniert. Eine
  Überzahlung ist ein Guthaben, das ein Mensch zurückzahlt oder verrechnet – nie
  automatisch.
- **Teilbetrag je Position** (netto); jedes Zahlungsmodul steht für sich.
- **Mahnung**: drei Stufen, je 10 Tage, von Hand (`remind`); die Stufe ist die Zahl der
  Mahn-Dokumente. Überfälliges zählt in «zu tun» der Person; eine eigene Mahnliste gibt es
  nicht.

#### Die Anschrift entscheidet

Beide Anschriften (Rechnung, Lieferung bzw. beim Erbringer «Versand») stehen auf beiden
Seiten, auch wenn sie gleich sind. Aus ihnen folgt:

- **Steuer** je Position (MWSTG Art. 26), gerundet je Satz auf der Summe: Ware nach
  Lieferadresse (Ausland fest 0 % Export), Dienstleistung nach Sitz (Ausland Reverse
  Charge). Sätze: `domain/voucher.VAT_RATES`.
- **Fremdwährung** nur ins Ausland, **eine Währung je Vorgang**; **Zoll** (Tarif, Ursprung,
  Gewicht) nur bei Export; der **Ort der Lieferbedingung** (Incoterms 2020) abgeleitet –
  E/F: Versandadresse des Erbringers, C/D: Lieferadresse.

**Lieferantenrechnung**: Nummer, Datum, MWST-Nr. (bei Steuer Pflicht) und das **Dokument**
(Feld `voucher.original`, die Werte liest die KI vor). Weicht sie von der Zusage ab, wird
erst nach «So annehmen» mit Grund bezahlt (`accept`). **Ausfuhrnachweis** = Nummer der
Veranlagungsverfügung + ihr Dokument (Feld `voucher.export`).

#### Die Papiere

- **Jedes Papier** (Offerte, Auftragsbestätigung, Rechnung, Quittung, Stornierung,
  Gutschrift, Mahnung – `DOCUMENTS`) entsteht aus **einer A4-Vorlage**
  (`services/document.py`), nennt je Position die Seriennummer (`serials_of`), trägt die
  AGB der stellenden Gesellschaft auf eigenen Seiten und ist ein **Dokument** (Feld
  `voucher.doc`, nie löschbar; `voucher_documents` hält nur Link, Partei und Mail).
- **Vorschau → Freigeben**: was ein Papier hinausgibt (`PAPER_VERBS`), zeigt die Karte
  vorher (`voucher_docs.preview`, zurückgerollter Lauf). Auftragsbestätigung und Quittung
  **stehen an** (`papers_due`, «zu tun») und gehen mit «Prüfen und freigeben» (`release`),
  nie von selbst (`AUTO_RELEASE` ist leer).
- Hinaus geht es per Mail über das Postfach der Gesellschaft mit einem Link `/beleg?t=…`;
  dort handelt die Partei mit denselben Verben (annehmen, ablehnen, bezahlen).
- **Die Zahlungen-Liste** (`GET /erp/payments`) ist eine Ableitung an jeder Person und an
  jeder eigenen Gesellschaft.

**Offen und benannt** (`docs/backlog.md`): die offene-Posten-Liste je Partner (mit der
Sammelzahlung über mehrere Module), ein Beleg ganz ohne Ware (`assert_releasable` verlangt
mindestens eine Einzelinstanz), die automatische Freigabe einzelner Papiere, Bankabgleich
(camt.053).

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

### 10.2 Technologie

Fluss-Layout mit einem SVG-Overlay auf gemessenen Ankern (kein Canvas, keine
Graph-Bibliothek) – Begründung und geprüfte Alternativen in `docs/prozessbild.md` §10.2.

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

Die Ansicht an der Instanz ist damit exakt der Teilbaum, den man am Artikel aufklappt;
zwei Fassungen trennten sich beim ersten neuen Zustand.

**Drei Ebenen, jede vollständiger als die darüber:**

| Ebene | Zeigt | Kommt von |
|---|---|---|
| 1 | die **beschriftete Leiste**: ein Segment je Zustand, darunter Punkt · Wort · Menge | `GET /erp/articles/{id}/stock` → `states` |
| 2 | zum **gewählten** Zustand eine Zeile je Instanz: Nummer · Menge **in diesem Zustand** | dieselbe Antwort, `instances` (seitenweise) |
| 3 | die Nummern der Stücke, je mit Zustand und Auftrag | `GET /erp/instances/{id}/units` (erst auf Klick) |

**Kein Filter.** Ein Filter ist meistens das Eingeständnis, dass die Standardansicht zu
viel Rauschen enthält; und er versteckt, was er nicht zeigt. Stattdessen ist die
**Aufteilung selbst das Bedienelement**: ein Segment anklicken heisst «zeig mir diese
Nummern», und der Rest bleibt in der Leiste sichtbar.

**Die Leiste NENNT ihre Zustände — die Farbe allein kann es nicht.**
Der Katalog kennt **drei** Ampeltöne für **sechs** Zustände eines Stücks: *Freigegeben*,
*Verbaut* und *Verkauft* sind alle grün, *Im Prozess* und *Gesperrt* beide gelb. Zwei
gleichfarbige Segmente nebeneinander sind damit **strukturell** nicht unterscheidbar, und
keine Feinabstimmung des Tons ändert daran etwas — das Wort ist die Unterscheidung.
Also stehen Punkt, Wort und Menge **unter der Leiste, als Teil von ihr**, eine Haarlinie
trennt die Segmente, und die Beschriftung ist zugleich die Auswahl – es gibt nur **eine**
Fassung, keine Sektionen je Zustand daneben.

**Und genau EINER ist offen**, zu Beginn keiner: eine Gruppe, die von selbst offensteht,
entscheidet für den Betrachter, was ihn interessiert; die Mengen in der Leiste sagen ihm,
ob sich das Öffnen lohnt.


**Die Ansicht zählt dabei keinen einzigen Status auf.** Alles folgt aus dem Status selbst
(§5.2):

| Frage | Antwort kommt von |
|---|---|
| Welche Segmente gibt es? | den gelieferten `states` – nie einer Liste in der Ansicht |
| In welcher **Reihenfolge**? | der Position im `CATALOG` = **Lebenszyklus** (Freigegeben → Im Prozess → Gesperrt → Verbaut → Verkauft → Verschrottet) |
| Welche **Farbe**? | dem Ampelton des Status |
| Zählt es zum Bestand? | `stock` – eine Eigenschaft am Status |

Ein neuer Zustand erscheint damit **ohne eine Zeile Änderung** an seiner Stelle im
Lebenszyklus, in seiner Farbe, mit seinem Wort. Ein Zustand **ohne** Zuordnung wird
**gemeldet** statt einsortiert.

**Keine Gesamtzahl im Kopf.** Sie summierte auch Verschrottetes (das ist kein Bestand) und
sagte nicht, wovon. Die Zahlen stehen an der Leiste, je eine je Zustand.

**Die Karte ist die der Spezifikation** (`SPEC.card` + `SpecHead` aus `fields.tsx`) – die
Anatomie jeder Detail-Ansicht, nicht die des Artikels.

**Die Instanz hat keinen Zustand, sondern eine Aufstellung.** Eine Gruppe mit drei
freigegebenen und einem laufenden Stück hat keinen einen Zustand; jede gewählte Antwort
wäre eine Behauptung. `states` zählt darum auf, und die Menge ist die Summe — **eine**
Abfrage, zwei Lesarten.

**Kein Sonderfall für Einzelserialisierung.** Eine Einzelinstanz ist eine Instanz mit
Menge 1 — dieselbe Zeile, dieselbe Leiste, dieselbe Nummernliste. Und die Leiste ist
**ein** Bauteil für beide Massstäbe (Artikel wie Instanz): eine zweite «kleine» Leiste
wäre eine zweite Regel dafür, wie ein Zustand aussieht.

**Sortierung: aufsteigend nach Objektnummer = FIFO.** Nummern werden aufsteigend
vergeben, und eine Instanz entsteht mit ihren Stücken (§2.2) — aufsteigend ist damit die
Reihenfolge, in der das Material entstanden ist. Der Feed sortiert absteigend, weil man
dort den zuletzt angelegten Datensatz sucht; hier sucht man das älteste Material. **Ein
eigenes Datum braucht es dafür nicht**, und es wäre die zweite Wahrheit neben der Nummer.

**Gruppiert wird nach Instanz, nicht nach Zustand.** Die Frage nach dem Zustand
beantwortet die Leiste oben, und die Instanz ist die Klammer, die zählt: sie
trägt die Objektnummer, die man scannt und zitiert. Nach Zustand gruppiert erschiene
dieselbe Charge in zwei Gruppen und ihre Menge nirgends vollständig.

**Nie alles auf einmal.** Instanzen kommen seitenweise (50), Nummern erst auf Klick und
auch dann seitenweise (60). Die Leiste oben gilt trotzdem für den **ganzen** Artikel —
eine Aggregation, die sich beim Blättern ändert, beantwortet «wie viel habe ich» nicht.
Dieselbe Regel gilt im **Instanz-Datensatz**: eine Ansicht, die die Regel einhält, und
eine Nachbaransicht, die sie einen Klick weiter bricht, ist keine Regel.

---

## 11. Datenstruktur — drei Ebenen

Die Trennung ist die Voraussetzung für Skalierbarkeit: ein Zustand, der aus dem heutigen
Bestand **rekonstruiert** wird, schreibt mit jeder Änderung die Vergangenheit um.

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

Der Index steht in der Migration (`uq_order_units_active`). Er ist die einzige Stelle, an
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

**Eine eigene Tabelle, und zwar die EINZIGE.** Einen zweiten, allgemeinen Ereignis-Strom
gibt es nicht (`docs/attic.md`): wer Analytik braucht, liest **diesen** Log — er ist die
Wahrheit über das Material.

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

**Die Regel nennt keinen Status.** «Einem laufenden Auftrag entzogen» wäre zu eng: ein
**gesperrtes** Stück wieder in Betrieb zu nehmen ist der Musterfall einer
**Sonderfreigabe**, ebenso Demontage (`Verbaut`) und Retoure (`Verkauft`). Der Zweck des
Labels ist die **Nachweisbarkeit**.

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

Auch nach einer **durchgefallenen** Erfassung steht das Stück «davor», weil nichts
vorgerückt ist — die Position ist der Grund, nicht die Eingabe. Was daraus folgt und was
offen ist, steht in `SYSTEM_LOGIC.md` §5.5.

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
steht — anwesend **oder** ausgeschert — **oder** wenn eine Abzweigung an ihm ansetzt, auch
wenn alle Stücke längst zurück und weitergezogen sind. Weil ein Punkt nach dem Modul
heisst, vor dem er liegt, ist sein Anker **berechenbar** (`statePointId`).

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

Jeder Modultyp erbt beides, ohne eine Zeile dafür zu schreiben.
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
Weicht sie ab, passiert **nichts**, und der Fehler nennt beide Seiten. Sonst entschiede
die Reihenfolge der Klicks, welche **Art** Auftrag entsteht: ein als frei gewähltes Stück,
das inzwischen läuft, machte die Freigabe still zur Abweichung.

Das ist optimistisches Sperren mit dem Wert, den der Mensch gesehen hat, und es ist **eine**
Auswahl-Logik für beide Fälle: konkrete Stücke, vorher sichtbar, änderbar. Einen zweiten
Weg «nur nach Kriterium» gibt es nicht — die Kriterien-Auswahl ist der Normalfall dieser
einen: FIFO schlägt vor, der Mensch übersteuert.

**Ein Auftrag darf nie unbemerkt seine Art ändern.**

**Freie und gebundene Stücke dürfen im selben Auftrag stehen** — und es braucht dafür
**keine** Regel: die Absicht steht **je Stück**, nicht je Auftrag. Beide Wege gehen durch
dasselbe Start-Objekt (§4.1), und `return_to_order_id` entsteht genau für die geliehenen;
ein freies Stück kommt aus keinem Auftrag und kann nirgends zurückkehren.


### 12.7 Wann darf ein Stück ein Modul verlassen?

**Offene Entscheidung** (§13.2). Gebaut ist die restriktivere Variante: solange in einem
Modul mit der Eingabe **begonnen** wurde, ist der Auslöser gesperrt.

Sie steht als **Eigenschaft des Modultyps** (`Module.units_may_leave`), nicht als globale
Regel — denn die richtige Antwort hängt am Modul: eine begonnene Datenerfassung ist
verlorene Tipparbeit, ein hinausgegangenes Angebot ist Aussenwirkung.

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
  ist, und eine zweite kommt dorthin zurück, wo es weitergeht. Ist die
  Rückführung gekappt, fehlt die zweite Linie — das Bild sagt es, ohne ein Wort.
- **Skalierung:** die Seitenspalte rendert **höchstens drei** Nachbarn voll; der Rest
  steht als Zeile «+N weitere» mit der Gesamtzahl und ist anklickbar. Abschneiden mit
  Zähler, nicht gruppieren: eine Gruppe müsste einen gemeinsamen Nenner behaupten, den es
  bei Abweichungen nicht gibt.

---

## 13. Bewusst noch nicht definiert

Diese Punkte gehören zur Grundlogik, sind aber **nicht** entschieden. Sie werden einzeln
nachgetragen — nicht beim Bauen erraten.

1. **Weitere Prozessschrittmodule** nach Bedarf. Fünf sind gebaut (§9); ein
   Wiederaufbau eines entfernten beginnt bei der Modellfrage in `docs/attic.md`.
2. **Darf ein Abweichungsauftrag noch ausgelöst werden, wenn in einem Modul bereits mit
   der Dateneingabe begonnen wurde?** Gebaut ist vorläufig die restriktivere Variante
   (nein) — als **Eigenschaft des Modultyps**, nicht als globale Regel (§12.7).
3. **Wer darf aussondern, verschrotten, stornieren?** Heute jede Person mit Zugang zum
   ERP (`SYSTEM_LOGIC.md` §4.5, R10). Der Abbruch selbst ist entschieden: es gibt keine
   Abbruch-Funktion, sondern eine Abweichung mit gekappter Rückführung (§3.1).
4. **Zwei `Neu`-Zeilen mit verschiedenen Vorlagen.** Heute ein harter Fehler: ein Auftrag
   hat einen Prozess (§14). Ob es dafür je einen Fall gibt, ist nicht entschieden.
5. **Die Vorlage im Entwurf abweichen lassen.** Heute nicht möglich — der Stempel wäre
   sonst eine Behauptung. Falls es gebraucht wird, ist es ein eigener Vorgang
   («Prozess dieses Auftrags von der Vorlage lösen»), kein stilles Editieren.
6. **Wiederkehrende Aufträge — eine Schlaufe mit Intervall im Prozess.** Wartung,
   Kalibrierung, monatliche Lieferung und ein Abo sind **derselbe** Fall: eine Regel, die
   in einem Takt einen ganz gewöhnlichen Auftrag erzeugt. Bewusst **nicht** als
   Eigenschaft des **Preises** (so hing es im Vorgängersystem, `docs/attic.md` «Verkauf und
   Shop»): steht die Wiederkehr im Prozess, muss die Zahlung von ihr nichts wissen — und
   jedes andere Modul erbt sie.

---

## 14. Getroffene Annahmen

Wo die Vorgabe eine Lücke liess, steht hier die gewählte Variante — jede ist die
einfachste, die die Regeln erfüllt, und jede ist an einer Stelle änderbar.

| | |
|---|---|
| **Die Statusliste ist geschlossen und steht an einer Stelle** | `domain/statuses.CATALOG` (§5.2). `Freigegeben` statt `verfügbar` (ein Zustand, ein Wort); `gebunden` und `verbraucht` sind zurückgezogen — Gründe in §5.2. |
| **Ein neues Stück ist `Freigegeben`** | Es ist einsatzbereit und in keinem Auftrag; ein eigener Anfangszustand bräuchte eine Regel, wie es `Freigegeben` wird. |
| **Kein gespeicherter Zustand «Entwurf»** | Folgt zwingend aus §6.1 + §6.3. Der «Speichern»-Knopf ist entfallen; es gibt nur «Freigeben». |
| **Exklusivität als partieller Unique-Index auf `order_units`** | Die Zuordnungstabelle behält die Historie, `released_at IS NULL` ist «aktiv». Eine Spalte an der Einzelinstanz wäre ebenso exklusiv, verlöre aber die Liste des abgeschlossenen Auftrags. |
| **Exklusivitätsprüfung VOR der Nummernvergabe** | Sonst verbrennt jeder Verstoss eine Objektnummer (§6.3). |
| **`orders.end_status` als Ort des Endzustands** | Hält die Schrittliste rein und gibt dem Endzustand seine eine Adresse. |
| **A5 gilt für Modul-Definitionen, nicht für die Instanz-Liste** | Bei einer Liste wäre «löschen und neu anlegen» dasselbe wie «bearbeiten». |
| **Der Auftragsstatus ist abgeleitet, nie gesetzt** | Im Prozess · Abgeschlossen · Abgebrochen aus den Zugehörigkeiten (`_derive`, §12.5). Kein Feld, das jemand von Hand setzt. |
| **Ein Modul bewegt alle Stücke einer INSTANZ, die davor stehen** | Ein Bestätigen je Stück wäre bei 500 Stück unbedienbar — je **Instanz** ist es die richtige Grösse, weil der Scan die Instanz verifiziert (§4.4): eine Charge ist ein Griff, zwölf Einzelteile sind zwölf. Die Historie bleibt **je Stück** ein eigener Eintrag. |
| **Ein Scan je Instanz, ein Wertesatz je gezogener Einzelinstanz** | Verifiziert wird die Instanz, gemessen das Stück (§9.5); gespeichert wird je Einzelinstanz, damit die Zeile in deren Historie steht. |
| **Die Stichprobe wird zufällig gezogen, nicht gerechnet** | «Jedes n-te Stück» wäre vorhersagbar und damit als Stichprobe wertlos. Gezogen wird, wenn das Modul **erreicht** wird (vorher steht die Menge nicht fest), und **eingefroren im Log** — sie ändert sich nicht mehr, wenn jemand die Seite neu lädt (§9.3). |
| **Die Stichprobenregel gilt über die GESAMTMENGE** | Ein Modul sieht die Summe dessen, was davorsteht – «10 %» heisst 10 % davon. Je Instanz gerechnet stünde «10 %» am Bildschirm, während in Wahrheit aus jeder Kiste einzeln gezogen wird (und aus einer Kiste mit einem Stück immer dieses eine). |
| **Ein «nicht bestanden» hält die GANZE Instanz an** | Auch die nicht gezogenen Stücke: eine durchgefallene Stichprobe ist nicht mehr repräsentativ, der Rest ist verdächtig (Sortierprüfung). Ihn weiterlaufen zu lassen hiesse, ihn hinterher wieder einzusammeln. |
| **Die Nummern der angehaltenen und gezogenen Stücke kommen erst auf Klick** | Bei einer 6000er-Charge wären es tausende Nummern — mitgeliefert bei jedem Öffnen des Auftrags. Eigener Endpunkt (`GET …/steps/{id}/hold`). |
| **Die Art der Bestätigung steht im Log** | `scan` oder `manual`. Ohne den Vermerk wäre die Tastatur eine stille Umgehung der Scan-Pflicht statt ihrer protokollierten Alternative. |
| **Zwei Zustände statt einem «ausgesondert»** | Sie unterscheiden sich in genau einer Sache, und die zählt: ob es einen Weg zurück gibt. Ein gemeinsamer Wert mit einem Flag daneben wäre dieselbe Aussage in zwei Feldern – und die Farbe müsste sie erraten. |
| **`Gesperrt` zählt zum Bestand** | Das Stück liegt im Regal. Es in die Historie zu legen hiesse, den Bestand kleiner zu melden, als er ist; die Leiste zeigt es als eigenes Segment, und genau das ist die Auskunft. |
| **Das Greifen IST das Aufheben der Sperre** | Kein Endpunkt «entsperren», kein zweiter Weg: ein gewöhnlicher Auftrag nimmt das Stück auf, das Start-Objekt setzt es auf «Im Prozess». Ein eigener Mechanismus wäre eine zweite Art, dasselbe zu tun. |
| **Verschrotten ist keine Bestandsbewegung mit Ziel** | Es gibt kein «Schrottlager». Der Zustand IST die Aussage «gibt es nicht mehr»; ein Lagerort dafür wäre ein Ort für etwas, das weg ist. |
| **Aussondern kennt keine Teilmengen** | Was am Modul ankommt, wird ausgesondert. Wer nur einen Teil meint, gibt nur diesen Teil in den Auftrag – eine Auswahl im Modul wäre ein zweiter Weg zur selben Entscheidung. |
| **Der Grund des Aussonderns ist Pflicht – beim Modellieren, für beide Ausprägungen** | Er steht in der Definition (`config.reason`), nicht als Erfassungspunkt: er lautet für jedes Stück gleich, und zur Laufzeit ist der Scan die Bestätigung (§9.4). Ohne Grund ist das Modul nicht anlegbar. |
| **Ein terminales Modul darf nur zuletzt stehen** | Alles dahinter bekäme nie ein Stück. Eine tote Definition durchzulassen wäre schlimmer als ein Freigabe-Fehler: sie sieht aus wie ein Prozess. |
| **Die Kettenregel gilt auch für die Artikel-Vorlage** | Ein Erzeugungsprozess mit gebrochener Kette scheiterte erst beim ersten Auftrag – dann ist der Artikel eingefroren und nicht mehr zu reparieren. `domain/chain.py`, von beiden Definitionsorten gerufen. |

| **Der Auftragsstatus bekommt keinen vierten Wert** | Die bestehende Regel trägt beide Fälle: wer aussondert, hat sein Ziel erreicht (`Abgeschlossen`); wem die Stücke dadurch endgültig fehlen, dessen Ziel ist unerreichbar (`Abgebrochen`). |
| **Der Übergang gehört zum Modultyp, nicht zum Anwender** | «Fest verdrahtet, nicht einstellbar» (Vorgabe). Zwei Status-Auswahlen beim Anlegen hätten eine Entscheidung angeboten, deren einzige richtige Antwort schon feststand — und deren falsche einen Prozess ergäbe, der nicht läuft. **Der Typ darf dabei seine eigene Konfiguration lesen** (`status_after_for`): gewählt wird «was soll passieren», nicht «welcher Status». |
| **Alles, was angelegt ist, ist Pflicht** | Man legt einen Punkt an, weil er erfasst werden soll. Ein Häkchen daneben wäre die Frage, warum man einen Punkt anlegt, den niemand ausfüllen muss — und jeder ausgeschaltete eine Lücke, die erst später auffällt. |
| **Ein Erfassungspunkt-Typ ist eine Datei, keine Zeile in einer Liste** | Ein Typ ist **Verhalten** (prüfen · fehlt der Wert · bewerten), nicht nur ein Wort. Als `if/else` verteilt sich das auf drei Stellen, von denen man die dritte vergisst. |
| **Der Artikel entsteht erst bei seiner Freigabe** | Dieselbe Regel wie beim Auftrag (§6.1) und aus demselben Grund. Ein Artikel, der schon eine Objektnummer hat, aber nichts erzeugen kann, ist ein Datensatz mit einer Zusage, die er nicht halten kann. |
| **Der Artikel-Zustand ist eine Projektion** | `Freigegeben` oder `Inaktiv`, abgeleitet aus `replaced_by_id` (§5.5); eine Spalte `articles.status` gibt es nicht, einen Zustand «Entwurf» ebenso wenig – vor der Freigabe gibt es keine Zeile. |
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
| **«Neu» steht für sich allein** | Ein Erzeugungsauftrag fährt die Vorlage genau dieses Artikels; ihr Versionsstempel gilt nur für seine Stücke. Die Regel liest sich von beiden Enden gleich: mit «Neu» kommt keine zweite Zeile dazu, und zu einer zweiten Zeile lässt sich «Neu» nicht wählen. |
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
