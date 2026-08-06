# PROCESS_CORE — die Grundlogik des Prozesses

> **Verbindlich und systemweit.** Wer ein Prozessschrittmodul baut, hält sich hieran.
> Was hier nicht steht, ist nicht entschieden — und wird nicht erfunden.
>
> Stand: August 2026, nach dem Basis-Neuaufbau (Einzelinstanz-Modell), der Neuanlage des
> Datensatztyps «Auftrag» und den Entscheiden A1–A6. Die frühere Prozesslogik ist
> ersatzlos entfernt; nichts davon ist Vorlage.
>
> **Stand der Umsetzung:** §1–§10 sind **gebaut und im Browser durchgeprüft**. Das
> Prozessschrittmodul ist heute ein bewusstes Platzhalter-**Testmodul** (§9) – das erste
> echte wird die Datenerfassung.

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
- Solange ein Stück in einem Auftrag steckt, ist es für jeden anderen tabu. Es gibt
  keine Ausnahme, bis der Unterauftrag-Mechanismus (§11.2) definiert ist.

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
| `gesperrt` | Problem-Zustand. Die Fehlerbehandlung im Modul ist **nicht entschieden** (§11.5) — ein Wert dafür wäre erfunden |
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

### 6.3 Was «Freigeben» auslöst — exakte Reihenfolge

Freigeben = den Prozess starten. Der Klick ist der Trigger.

| # | Schritt |
|---|---|
| 1 | **Freigabebedingungen prüfen** (§6.2) + Statuskette (§4.3). Nicht erfüllt → Abbruch mit klarer Meldung. |
| 2 | **Exklusivitätsprüfung** (§3). Verletzt → Abbruch, nichts wird angelegt. |
| 3 | **Datensatz anlegen**, Objektnummer vergeben. |
| 4 | **Workflow anstossen:** die definierten Einzelinstanzen passieren das Start-Objekt und wechseln `Freigegeben` → `Im Prozess`. |
| 5 | **Ereignis loggen und einfrieren.** |
| 6 | Das **nachfolgende Prozessschrittmodul wird aktiv.** |

Alle Schritte laufen als **eine Transaktion**. Bricht einer ab, bleibt nichts
Halbfertiges zurück — kein Auftrag ohne Prozess, keine Einzelinstanz in einem
Zwischenzustand.

**Schritt 2 und 3 sind gegenüber der ursprünglichen Vorgabe getauscht — mit Grund.**
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

Was schiefgeht, geht **seitlich** in einen Unterauftrag und kommt **unterhalb** der
Abzweigung zurück — die Bewegung bleibt damit abwärts. Der Mechanismus dafür ist noch
nicht definiert (§11.2).

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

---

## 8. Wo der Prozess lebt

Der **Auftrag** ist der Ort, an dem Prozesse **ausgeführt und gemanagt** werden.
Definiert werden sie an genau zwei Orten — mit **identischer Darstellung**:

| Ort | Zweck | Ausführung möglich? |
|---|---|---|
| **Auftrag** | Konkreter Prozess für konkrete Einzelinstanzen | **ja** |
| **Artikel** | Erzeugungsprozess / Arbeitsplan als **Vorlage** | **nein** |

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

### 8.2 Artikel-Reiter «Erzeugungsprozess» — Konzept, NICHT bauen

Neben «Spezifikation» bekommt der Artikel einen zweiten Reiter:

- Inhalt: **1:1-Spiegelung** der Prozessdarstellung — Start, Module, Ende.
- Dort wird **ausschliesslich der Prozess definiert**, sonst nichts.
- **Kein Anstossen von Prozessen, keine Einzelinstanzen, keine Ausführung.** Das
  passiert später ausschliesslich im Auftrag.
- Freigabebedingung Artikel (analog, hart):
  1. alle Pflichtfelder der Spezifikation ausgefüllt
  2. mindestens ein Prozessschrittmodul im Erzeugungsprozess definiert

**Jetzt nur berücksichtigen, nicht bauen.** Konkret: die Komponente aus §8.1 so
schneiden, dass sie ohne Umbau am Artikel läuft.

*Zum Namen: «Erzeugungsprozess» statt «Prozess», weil er sagt, wofür der Prozess da ist
— wie ein Stück entsteht — und weil damit Platz bleibt, falls ein Artikel später eine
zweite Art Vorlage trägt. «Prozess» wäre der Behälter, nicht die Sache.*

---

## 9. Das Prozessschrittmodul «Testmodul»

Es gibt heute **genau ein** Modul, und es ist bewusst ein Platzhalter — ein Testvehikel
für den Mechanismus, nicht das spätere Datenerfassungsmodul.

| | |
|---|---|
| Anlegen | Freier Name · **Vorher-** und **Nachher-Status** aus der geschlossenen Liste. Beides Pflicht — ohne sie ist es nicht anlegbar (§4). |
| Laufzeit | Es zeigt die Einzelinstanzen, die gerade davor stehen. |
| **«Schritt bestätigen»** | Vorher-Status prüfen (passt nicht → sauberer Fehler) · Nachher-Status setzen · Ereignis loggen und einfrieren · Stück rückt vor. |

Mehr nicht. Keine Felder, keine Eingaben, keine Fachlogik. Ist es das **letzte** Modul,
passiert das Stück im selben Zug das Ende-Objekt und wird frei (§3.1).

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
innerhalb der Definition, sondern als **eigener Auftrag** daneben (Unterauftrag, §11.2).
Ein Kantenmodell würde eine Freiheit anbieten, die es fachlich nicht gibt, und jede
Auswertung müsste danach mit Zyklen und toten Ästen rechnen.

Start und Ende sind **keine Zeilen**: es gibt genau einen von jedem, ihre Position ist
implizit, und ihre Übergänge gehören zum System, nicht zur Modellierung (§4.1).

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

**Eigene Tabelle, nicht der bestehende `events`-Strom.** Der ist ein Beobachtungs-Outbox
für KI und Analytik mit freier Payload; hier geht es um die Quelle der Wahrheit für den
Zustand. Beides in einer Tabelle hiesse, eine «nice to have»-Spur und eine verbindliche
Buchführung in denselben Zeilen zu führen — und die schwächere Garantie gewinnt immer.

---

## 12. Bewusst noch nicht definiert

Diese Punkte gehören zur Grundlogik, sind aber **nicht** entschieden. Sie werden einzeln
nachgetragen — nicht beim Bauen erraten.

1. **Die Prozessschrittmodule selbst.** Erstes: Datenerfassung.
2. **Der Unterauftrag-Mechanismus.** Die Skizze zeigt Abzweigungen nach rechts und
   zurück. Wann zweigt es ab, was nimmt der Unterauftrag mit, wo mündet er, was passiert
   mit dem Status des Stücks währenddessen?
3. **Der übergeordnete Auftrag.** Die linke Spalte — Gegenrichtung von (2).
4. **Abbruch.** §3.1 schlägt vor, was mit den Stücken geschieht; wer abbrechen darf und
   was mit dem Auftrag selbst passiert, ist offen.
5. **Fehlerbehandlung im Modul.** Ein Modul kann scheitern (Prüfung nicht bestanden).
   Ist das ein Status, ein Abzweig, oder beides? Solange das offen ist, gibt es keinen
   roten Statuswert (§5.2).

---

## 13. Getroffene Annahmen

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
| **Reiter-Name «Erzeugungsprozess»** | Sagt, wofür der Prozess da ist, und lässt Platz für eine zweite Art Vorlage. |

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
