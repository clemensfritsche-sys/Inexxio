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
| `Freigegeben` | Grün | Stück · Artikel | live | Einsatzbereit, in keinem laufenden Auftrag. Anfangs- **und** (heute einziger) Endzustand. |
| `Im Prozess` | Orange | Stück · Auftrag | live | Im Prozess genau eines freigegebenen Auftrags. |
| `Abgeschlossen` | Grün | Auftrag | — | Ziel erreicht. |
| `Abgebrochen` | Rot | Auftrag | — | Ziel nicht mehr erreichbar. |
| `Inaktiv` | Rot | Artikel | — | Ausser Betrieb, endgültig. |

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
| 1 | Gesamtmenge + gestapelte Leiste | `GET /erp/articles/{id}/stock` → `states`/`total` |
| 2 | eine Zeile je Instanz: Nummer · Menge · eigene Leiste | dieselbe Antwort, `instances` (seitenweise) |
| 3 | die Nummern der Stücke, je mit Zustand und Auftrag | `GET /erp/instances/{id}/units` (erst auf Klick) |

**Kein Filter.** Ein Filter ist meistens das Eingeständnis, dass die Standardansicht zu
viel Rauschen enthält; und er versteckt, was er nicht zeigt. Stattdessen ist die
**Aufteilung selbst das Bedienelement**: ein Segment der Leiste anklicken heisst «zeig mir
diese Nummern», der Rest bleibt sichtbar und tritt nur zurück. Zwei Blöcke statt eines
Filters — **Bestand** (offen) und **Historie** (zu); ein Block, dessen Zustände es nicht
gibt, steht gar nicht da.

**Welcher Block, sagt der Status** (§5.2), nicht die Ansicht: `StockState.stock` kommt mit
den Daten. Ein neuer Zustand wird damit an **genau einer Stelle** ergänzt und erscheint
hier ohne eine Zeile Änderung – mit Beschriftung, Farbe, Reihenfolge und im richtigen
Block. Ein Zustand **ohne** Zuordnung wird **gemeldet** statt einsortiert: ihn zu raten
wäre eine Behauptung, ihn wegzulassen ein stiller Verlust.

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
