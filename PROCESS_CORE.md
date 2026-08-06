# PROCESS_CORE — die Grundlogik des Prozesses

> **Verbindlich und systemweit.** Wer ein Prozessschrittmodul baut, hält sich hieran.
> Was hier nicht steht, ist nicht entschieden — und wird nicht erfunden.
>
> Stand: August 2026, nach dem Basis-Neuaufbau (Einzelinstanz-Modell) und der
> Neuanlage des Datensatztyps «Auftrag». Die frühere Prozesslogik ist ersatzlos
> entfernt; nichts davon ist Vorlage.

---

## 1. Der Auftrag

Ein Auftrag hat **genau einen Anfang und genau ein Ende**. Dazwischen liegt eine
geordnete Folge von **Prozessschrittmodulen** — alles, was im Unternehmen getan wird.

```
        ┌──────────────────────────┐
        │  DEFINITION              │   welche Einzelinstanzen?
        └──────────────────────────┘
                    │
                  ( ▶ )  START
                    │
              [ Modul 1 ]
                    │
              [ Modul 2 ]
                    │
                   ...
                    │
                  ( ⚑ )  ENDE
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

### 2.2 Eine Einzelinstanz läuft in höchstens einem Auftrag

Eine Einzelinstanz ist **ein Stück**. Sie kann zu einem Zeitpunkt in höchstens einem
laufenden Auftrag stecken. Der Versuch, sie in einem zweiten zu definieren, ist ein
harter Fehler.

Das ersetzt ersatzlos: Reservierung, Anteil, Ausleihe, Rückgabe, Unterdeckung.

---

## 3. Die Statusregel (Kern)

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

### 3.1 Die Kette muss schliessen

Beim Freigeben wird die Kette geprüft: das **Nachher** jedes Objekts muss das
**Vorher** des folgenden erfüllen. Eine Lücke ist ein Freigabe-Fehler, kein
Laufzeit-Problem.

Das ist der Unterschied zwischen einer Regel und einer Hoffnung: ein Prozess, der
freigegeben werden konnte, kann nicht mitten drin an einem Statuskonflikt hängen
bleiben.

---

## 4. Richtung und Historie

### 4.1 Nur von oben nach unten

Einzelinstanzen wandern **ausschliesslich abwärts**. Kein Rücksprung, keine
Schleife, keine Wiederholung an Ort und Stelle.

Was schiefgeht, geht **seitlich** in einen Unterauftrag und kommt **unterhalb** der
Abzweigung zurück — die Bewegung bleibt damit abwärts. Der Mechanismus dafür ist
noch nicht definiert (§9).

### 4.2 Geloggt und eingefroren

Beim Passieren eines Prozessobjekts wird bestätigt bzw. eingegeben. Daraus entsteht
ein Eintrag im **Ereignis-Log**:

- **append-only** — es gibt keinen Update- und keinen Delete-Pfad
- **unveränderlich** — nachträglich weder änderbar noch löschbar
- **vollständig** — wer, wann, welches Stück, welcher Übergang, welche Eingaben

Eine Korrektur ist ein **neuer Eintrag**, nie eine Änderung des alten. Was gemessen
wurde, wird nicht nachträglich schöngeschrieben.

### 4.3 Zwei Fragen, keine dritte

Das System beantwortet:

- **Was läuft jetzt?** — der Laufzeit-Zustand
- **Was ist passiert?** — das Ereignis-Log

Es beantwortet **nicht**: was passieren wird. Keine Vorhersage, keine Simulation,
keine Hochrechnung. Eine Kante unterhalb der aktuellen Stelle trägt keine Aussage
über Material, das sie noch nicht geführt hat.

---

## 5. Zwei Lebenszyklen

| Lebenszyklus | Was passiert | Was ist erlaubt |
|---|---|---|
| **Entwurf** | Der Prozess wird modelliert | Struktur frei änderbar, Definition frei änderbar, **keine** Instanzen unterwegs |
| **Freigegeben** | Instanzen durchlaufen den Prozess | Struktur **eingefroren**, Definition **eingefroren**, nur noch Ausführung |

Der Übergang ist ein **bewusster, einmaliger Akt**. Er ist nicht umkehrbar: ein
freigegebener Prozess wird nicht wieder zum Entwurf. Was nicht mehr passt, wird
abgebrochen, nicht umgeschrieben.

### 5.1 Abgrenzung zum Anlage-Entwurf

«Entwurf» heisst an zwei Stellen etwas Verschiedenes, und die Verwechslung wäre
teuer:

| | |
|---|---|
| **Anlage-Entwurf** | Das Fenster vor dem ersten Speichern. Existiert **nur im Browser** — keine Zeile, keine Objektnummer. Wer wegklickt, lässt keine Spur. |
| **Lebenszyklus «Entwurf»** | Der gespeicherte Auftrag mit Objektnummer, dessen Prozess gerade modelliert wird. |

Der zweite beginnt, wo der erste endet.

---

## 6. Datenstruktur — drei Ebenen

Die Trennung ist die Voraussetzung für Skalierbarkeit. Sie ist zugleich die Lehre
aus dem Vorgängersystem: dort wurde der Zustand aus dem heutigen Bestand
**rekonstruiert**, und weil der Bestand ein bewegliches Ziel ist, schrieb jede
Änderung die Vergangenheit um.

### Ebene 1 — Prozessdefinition (die Modellierung)

```
process_steps
  id · order_id · position · module_type · config(JSONB)
  status_before · status_after
```

**Eine geordnete Liste, kein allgemeiner Graph.** Ein Auftrag hat einen Anfang, ein
Ende und dazwischen eine Folge — `position` ist die Kante. Verzweigungen entstehen
nicht innerhalb der Definition, sondern als **eigener Auftrag** daneben (Unterauftrag,
§9). Ein Kantenmodell würde eine Freiheit anbieten, die es fachlich nicht gibt, und
jede Auswertung müsste danach mit Zyklen und toten Ästen rechnen.

Start und Ende sind **keine Zeilen**: es gibt genau einen von jedem, ihre Position
ist implizit, und ihre Übergänge gehören zum System, nicht zur Modellierung (§10 Q2).

### Ebene 2 — Laufzeit-Zustand (wo steht was)

```
instance_units.status          welchen Status hat das Stück
instance_units.current_step_id an welchem Objekt steht es
```

**Beides ist Projektion, nicht Wahrheit.** Die Wahrheit steht in Ebene 3. Diese
Spalten existieren nur, damit Feed, Filter und Bestandsabfragen ohne Log-Replay
auskommen. Sie werden **ausschliesslich** beim Schreiben eines Log-Eintrags
nachgezogen — es gibt keinen zweiten Schreibweg.

Ein Wächter prüft die Ableitbarkeit: `Projektion == Replay(Log)`. Weicht es ab, ist
das ein Fehler, der gemeldet wird — nicht einer, der still korrigiert wird.

### Ebene 3 — Ereignis-Log (die eingefrorene Historie)

```
process_events
  id · order_id · step_id · instance_unit_id
  status_before · status_after
  payload(JSONB)  actor_id  created_at
```

Append-only. Kein Update, kein Delete, kein `is_active`. Die Reihenfolge ist die
`id` — sie ist die Zeitachse.

**Eigene Tabelle, nicht der bestehende `events`-Strom.** Der ist ein
Beobachtungs-Outbox für KI und Analytik mit freier Payload; hier geht es um die
Quelle der Wahrheit für den Zustand. Beides in einer Tabelle hiesse, eine
«nice to have»-Spur und eine verbindliche Buchführung in denselben Zeilen zu führen —
und die schwächere Garantie gewinnt immer.

---

## 7. Statuswerte

Farben werden an den **Status** gebunden, nicht an die Position im Fluss. Sonst
skaliert die Darstellung nicht: derselbe Zustand sähe an zwei Stellen verschieden aus.

| Ton | Bedeutung |
|---|---|
| **Grün** | verfügbar / abgeschlossen — Anfangs- und Endzustand |
| **Orange** | im Prozess — unterwegs, gebunden, nicht verfügbar |
| **Rot** | Problem / gestoppt |

Prozessmodule tragen eine **eigene, davon getrennte** Farbfamilie — sie sind keine
Zustände, und sie dürfen nicht wie welche aussehen.

Welche Statuswerte es gibt und wer sie definieren darf, ist offen (§10 Q1).

---

## 8. Darstellung — was der Fluss zeigen darf

- **Nur Vergangenheit und Gegenwart.** Oberhalb der aktuellen Stelle steht, was war;
  an ihr, was ist. Darunter steht **kein Material** — der Fluss sagt nicht voraus.
- **Ein Prozessobjekt = eine Komponente.** Kein Copy-Paste je Modultyp; der Modultyp
  ist Konfiguration, nicht ein eigenes Bauteil.
- **Linien nie mit festen Pixelwerten.** Knoten bestimmen ihre Position selbst
  (Fluss-Layout); die Linien werden aus **gemessenen** Ankerpunkten berechnet
  (ResizeObserver → SVG-Overlay). Das muss mit 3 wie mit 50 Schritten tragen.
- **Responsive.** Auf schmalen Geräten degradiert die Darstellung auf die mittlere
  Spalte. Nie waagrecht scrollen — bei einem Diagramm verliert man dabei die Achse
  aus dem Blick, also genau das, worum es geht.
- **Keine erfundenen Daten, keine Fallback-Anzeigen.** Fehlt etwas, kommt ein Fehler
  mit Ursache und Ort.

---

## 9. Bewusst noch nicht definiert

Diese Punkte gehören zur Grundlogik, sind aber **nicht** entschieden. Sie werden
einzeln nachgetragen — nicht beim Bauen erraten.

1. **Die Prozessschrittmodule selbst.** Erstes: Datenerfassung.
2. **Der Unterauftrag-Mechanismus.** Die Skizze zeigt Abzweigungen nach rechts und
   zurück. Wann zweigt es ab, was nimmt der Unterauftrag mit, wo mündet er, was
   passiert mit dem Status des Stücks währenddessen?
3. **Der übergeordnete Auftrag.** Die linke Spalte — Gegenrichtung von (2).
4. **Abbruch.** Was passiert mit Stücken in einem abgebrochenen Auftrag?
5. **Fehlerbehandlung im Modul.** Ein Modul kann scheitern (Prüfung nicht bestanden).
   Ist das ein Status, ein Abzweig, oder beides?

---

## 10. Offene Fragen an den Auftraggeber

**Q1 — Statuswerte: geschlossene Liste oder frei je Modul?**
Eine **geschlossene** Systemliste (z. B. `verfügbar · im_prozess · gebunden ·
gesperrt · verbraucht`) macht Status auftragsübergreifend vergleichbar, erlaubt eine
Farbregel und eine Bestandsabfrage über alle Aufträge. Ein Modul wählt daraus, es
erfindet nicht. **Frei je Modul** ist flexibler, aber dann bedeutet «Status X» in
zwei Aufträgen womöglich Verschiedenes, und weder Farbe noch Bestand lassen sich
systemweit ableiten. *Empfehlung: geschlossen.*

**Q2 — Start und Ende: systemweit fest oder je Auftrag konfigurierbar?**
Trägt der Start immer `Freigegeben → Im Prozess` und das Ende immer
`Im Prozess → <Endzustand>`, oder soll man beides je Auftrag einstellen können?
*Empfehlung: systemweit fest — sonst ist die Kettenprüfung (§3.1) nur so gut wie
die Sorgfalt beim Modellieren.*

**Q3 — Eine Einzelinstanz in höchstens einem laufenden Auftrag (§2.2): bestätigt?**
Das ist die grösste Vereinfachung gegenüber dem Vorgängersystem und macht
Reservierung, Anteil und Unterdeckung ersatzlos überflüssig. Es heisst aber auch:
solange ein Stück in einem Auftrag steckt, ist es für jeden anderen tabu — bis der
Unterauftrag-Mechanismus (§9.2) definiert ist, gibt es keine Ausnahme.

**Q4 — Farbcodierung (§7): bestätigt?**
Grün = Anfang/Ende · Orange = im Prozess · Rot = Problem, gebunden an den **Status**;
Prozessmodule in eigener Farbfamilie.

**Q5 — Definition änderbar im Entwurf?**
Im Lebenszyklus «Entwurf» ist die Definition frei änderbar (§5). Korrekt — oder soll
die Definition schon **vor** der Freigabe einrasten, sobald sie einmal gesetzt ist?

**Q6 — Was ist der Endzustand?**
Am Ende steht laut Skizze wieder Grün. Heisst das, ein Stück ist danach wieder
**verfügbar** (zurück im Bestand), oder gibt es mehrere mögliche Endzustände
(verkauft, verbaut, ausgesondert), die das letzte Modul bestimmt?

---

## Anhang — Was aus dem Vorgängersystem NICHT übernommen wird

Zur Klarstellung, weil es in der Historie ausführlich dokumentiert ist und
verlockend nah liegt:

Reservierung · Anteil · Ausleihe und Rückgabe · Unterdeckung mit Antwortlogik ·
Material-Journal als Mengenbuchhaltung · Bereitstellung als abgeleiteter
Unter-Auftrag · Nachschub-Pegging · Abweichung als Mengen-Entzug.

Alles davon existierte, weil eine Instanz eine **Menge** war und ein Auftrag seine
Menge zur Laufzeit verlieren konnte. Beides gibt es nicht mehr. Wer eines dieser
Konzepte wieder braucht, hat vermutlich §2.1 oder §2.2 aufgeweicht.
