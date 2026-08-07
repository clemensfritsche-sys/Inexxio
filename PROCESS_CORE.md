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

---

## 5. Statuswerte (A1, A4)

### 5.1 Geschlossene Liste

Es gibt eine **geschlossene, systemweite** Statusliste. **Module wählen daraus aus, sie
erfinden nie eigene Werte.** Ein Modul mit unbekanntem Status ist nicht anlegbar.

- Technisch als **Enum/Referenztabelle**, nicht als Freitextfeld.
- Erweiterung der Liste ist ein bewusster Systemeingriff an **genau einer Stelle** im
  Code.

### 5.2 Die Werte

`backend/app/domain/statuses.py` ist die eine Quelle; `frontend/src/lib/process-status.ts`
spiegelt sie und wird dagegen getestet.

| Wert | Farbe | Bedeutung |
|---|---|---|
| `Freigegeben` | Grün | Einsatzbereit, in keinem laufenden Auftrag. Anfangs- **und** (heute einziger) Endzustand. |
| `Im Prozess` | Orange | Im Prozess genau eines freigegebenen Auftrags. |

**Mehr nicht.** Die früher vorgeschlagenen Werte sind zurückgezogen, jeder mit Grund:

| zurückgezogen | Grund |
|---|---|
| `verfügbar` | wäre ein **zweites Wort für `Freigegeben`** — genau die Doppelung, die dieses System überall abbaut |
| `gebunden` | war der Reservierungs-Begriff. **A3 streicht Reservierung ersatzlos** — der Wert wäre vorbereitendes Bauen für etwas, das es nicht geben soll |
| `gesperrt` | Problem-Zustand. Die Fehlerbehandlung im Modul ist **nicht entschieden** (§13.4) — ein Wert dafür wäre erfunden |
| `verbraucht` | Endzustand. **A6 sagt: heute genau einer** |

**Rot hat heute keinen Wert.** Der Ton steht in der Farbregel, aber es gibt noch keinen
Status dafür. Eine Farbe ohne Wert ist ehrlicher als ein erfundener Wert – die Anzeige
nutzt ihn trotzdem: ein **unbekannter** Wert wird rot gemeldet statt schöngefärbt.

**Eine frisch angelegte Einzelinstanz ist `Freigegeben`** (`INITIAL_UNIT_STATUS`): sie ist
einsatzbereit und in keinem Auftrag – genau das heisst das Wort. Der frühere Platzhalter
`new` aus dem Basis-Neuaufbau ist mit Migration `104` entfallen.

### 5.3 Farbe

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

Beide benutzen **dieselben** Bauteile: `ProcessDiagram` (Modus `definition`) und
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

### 8.2 Artikel-Reiter «Erzeugungsprozess» — die Vorlage

Neben «Spezifikation» trägt der Artikel den Reiter «Erzeugungsprozess»:

- Inhalt: **dieselbe** Darstellung wie im Auftrag (`ProcessDiagram`, Modus `definition`)
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

## 9. Das Prozessschrittmodul «Datenerfassung»

Es gibt heute **genau ein** Modul, und es ist das erste echte. Das frühere Testmodul war
ein Testvehikel für den Mechanismus und ist **ersatzlos entfallen** — den Mechanismus
gibt es jetzt echt.

Zweck: im Prozess laufend Daten erfassen und kontrollieren (Richtung Qualitätssicherung).

| | |
|---|---|
| Übergang | **Durchläufer**: `Im Prozess` → `Im Prozess`, **fest verdrahtet** (`domain/modules`). Es misst — es verändert den Zustand des Stücks nicht. Passt der Ist-Status nicht: sauberer Fehler. |
| Anlegen | Freier Name · **Erfassungspunkte**: je Punkt Bezeichnung, Typ, Pflicht ja/nein. Mindestens einer — ein Modul ohne Punkt stünde im Prozess und hätte nichts zu tun. |
| Laufzeit | Es zeigt die Einzelinstanzen, die gerade davorstehen, und die zu erfassenden Punkte. |
| **«Bestätigen»** | Pflichtpunkte prüfen (offen → Fehler, der sie **benennt**) · erfassen · Nachher-Status setzen · Ereignis loggen und einfrieren · Stück rückt vor. |

**Kein Status-Feld beim Anlegen.** Der Übergang gehört zum Modultyp; zwei Auswahlen
hätten eine Entscheidung angeboten, deren einzige richtige Antwort schon feststand.

### 9.1 Die Erfassungspunkt-Typen — eine geschlossene Liste aus Bausteinen

| Typ | Erfassung | Urteil? |
|---|---|---|
| `text` | Freitext | nein |
| `bool` | Ja/Nein (Daumen hoch/runter) | **ja** |
| `photo` | Foto/Upload | nein |
| `signature` | handschriftlich | nein |
| `measure` | Soll-Ist-Vergleich (Sollwert **Pflicht**, Toleranz optional) | **ja** |

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

**Was ein «nicht bestanden» auslöst, ist weiterhin offen** (§13.4). Bis dahin ist das
Ergebnis eine Aussage über die **Messung**, kein Ereignis im Prozess — ein erfundener
Abzweig wäre schlimmer als keiner.

---

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

Ein Auftrag trägt das Wort «Abweichung», wenn **irgendein Stück ihn mit dem Status
`Im Prozess` betreten hat**. Genau diese Frage steht im Log:

```sql
kind = 'start' AND status_before = 'im_prozess'
```

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

Daraus folgt, wo die Abzweigung sitzt: Ein Stück kann nur abweichen, solange am Modul
noch **nichts eingegeben** wurde (§12.7) — es hat das Modul also gar nicht betreten. Die
Linie geht darum **vor** dem Modul von der Prozesslinie ab und führt an **denselben
Punkt** zurück; das Stück durchläuft das Modul danach regulär.

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

1. **Die weiteren Prozessschrittmodule.** Das erste ist gebaut (Datenerfassung, §9).
   *Offen daran: was bei «nicht bestanden» passiert (siehe 4) – und ob je Einzelinstanz
   einzeln erfasst wird oder einmal gemeinsam (§14, heute gemeinsam).*
2. **Darf ein Abweichungsauftrag noch ausgelöst werden, wenn in einem Modul bereits mit
   der Dateneingabe begonnen wurde?** Gebaut ist vorläufig die restriktivere Variante
   (nein) — als **Eigenschaft des Modultyps**, nicht als globale Regel (§12.7).
3. **Abbruch.** §3.1 schlägt vor, was mit den Stücken geschieht; wer abbrechen darf und
   was mit dem Auftrag selbst passiert, ist offen.
4. **Fehlerbehandlung im Modul.** Ein Modul kann scheitern (Prüfung nicht bestanden).
   Ist das ein Status, ein Abzweig, oder beides? Solange das offen ist, gibt es keinen
   roten Statuswert (§5.2).
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
| **Ein Modul bewegt alle Stücke, die davor stehen** | Ein Bestätigen je Stück wäre bei 500 Stück unbedienbar; die Historie bleibt trotzdem **je Stück** ein eigener Eintrag. |
| **Die Datenerfassung erfasst EINMAL für alle Davorstehenden** | Die einfachere der beiden plausiblen Varianten (die andere: je Stück ein eigener Wertesatz, also 5 Unterschriften bei 5 Stück). **Gespeichert wird trotzdem je Einzelinstanz** — das Modell nimmt die andere Variante damit vorweg, sie wäre eine Änderung an der Eingabe, nicht an der Datenhaltung. **Zur Entscheidung vorgelegt.** |
| **Der Übergang gehört zum Modultyp, nicht zum Anwender** | «Fest verdrahtet, nicht einstellbar» (Vorgabe). Zwei Status-Auswahlen beim Anlegen hätten eine Entscheidung angeboten, deren einzige richtige Antwort schon feststand — und deren falsche einen Prozess ergäbe, der nicht läuft. |
| **Ein neuer Erfassungspunkt ist standardmässig Pflicht** | Man legt einen Punkt an, weil er erfasst werden soll; «optional» ist die Ausnahme und steht als Häkchen daneben. |
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
