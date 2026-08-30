# SYSTEM_LOGIC — die Regeln, wie sie sein sollen

> **Was dieses Dokument ist.** Die Prozesslogik als **Sollzustand**, in prüfbaren Sätzen.
> Nicht «so macht es der Code», sondern «so muss es sein» — damit sich der Code dagegen
> testen lässt und nicht gegen sich selbst.
>
> **Was es nicht ist.** Keine Architekturbeschreibung (die steht in `PROCESS_CORE.md`)
> und keine Zusammenfassung der Implementierung. Wo Sollzustand und Code auseinandergehen,
> ist das ein **Befund** und steht in `FINDINGS.md` — nicht hier.
>
> Reihenfolge: dieses Dokument entstand **vor** der Testkampagne. Das ist keine Formalie:
> ein systematisch falscher Code besteht seine eigenen Tests immer.

---

## 0. Das Modell in fünf Zeilen

```
Artikel     Ordner + Spezifikation + Vorlage des Erzeugungsprozesses. Keine Menge.
  └─ Instanz      Gruppe mit eigener 9-stelliger Objektnummer. Keine Mengen-Spalte.
       └─ Einzelinstanz   DAS Arbeitsobjekt. Immer genau 1 Stück. Eigener Status.
                          Nummer = <Instanznummer>-<Suffix>, nie aus dem Nummernkreis.

Auftrag     geordnete Modul-Liste + Definitionszeilen. Entsteht ERST mit der Freigabe.
```

Im Prozess wird **ausschliesslich** mit Einzelinstanzen gearbeitet. Jede Ansicht auf
höherer Ebene (Instanz, Artikel, Bestand) ist Filterung oder Summierung — nie eine eigene
Datenquelle.

---

## 1. Statuslogik

### 1.1 Alle Status, vollständig

Die Liste ist **geschlossen**. Ein Wert, der hier nicht steht, ist im System nicht
gültig — weder als Eingabe noch als gespeicherter Wert. Drei Achsen teilen sich die
Wörter, wo sie dasselbe meinen.

| Wert | Beschriftung | Achsen | terminal | selektierbar | Ton | Bestand |
|---|---|---|---|---|---|---|
| `freigegeben` | Freigegeben | Einzelinstanz · Artikel | nein | **ja** | grün | **lebend** |
| `im_prozess` | Im Prozess | Einzelinstanz · Auftrag | nein | **ja** | gelb | **lebend** |
| `gesperrt` | Gesperrt | Einzelinstanz | nein | **ja** | gelb | **lebend** |
| `verbaut` | Verbaut | Einzelinstanz | nein | **ja** | **grün** | historisch |
| `verschrottet` | Verschrottet | Einzelinstanz | **ja** | **nein** | rot | historisch |
| `abgeschlossen` | Abgeschlossen | Auftrag | – | – | grün | – |
| `abgebrochen` | Abgebrochen | Auftrag | – | – | rot | – |
| `inaktiv` | Inaktiv | Artikel | – | – | rot | – |  ← **abgeleitet** aus `replaced_by_id`

**Bedeutung je Wert:**

- **`freigegeben`** — An der Einzelinstanz: sie steckt in **keinem** Auftrag, sie ist
  einsatzbereit. Am Artikel: er ist freigegeben und auftragsfähig. Dasselbe Wort für
  «einsatzbereit», auf zwei Achsen.
- **`im_prozess`** — An der Einzelinstanz: sie ist in **genau einem** Auftrag aktiv. Am
  Auftrag: es ist noch etwas unterwegs.
- **`gesperrt`** — Aus dem Verkehr gezogen, **physisch noch da**. Nicht einplanbar,
  solange die Sperre gilt — **aber selektierbar**: das Greifen durch einen Auftrag **ist**
  das Aufheben. Es gibt bewusst keinen «Entsperren»-Endpunkt.
- **`verbaut`** — **Steckt in einem anderen Stück.** Es hat seinen Zweck erreicht: kein
  Mangel, kein Verlust – darum grün. Zur **Historie**, weil es nicht im Regal liegt;
  als Bestand geführt wäre es Material, das niemand greifen kann, ohne vorher etwas
  auseinanderzunehmen. **Nicht endgültig:** Demontage ist real, und ein Auftrag darf das
  Stück zurückholen – das Greifen IST der Ausbau, genau wie beim Sperren.
- **`verschrottet`** — Aus dem Verkehr gezogen und **physisch weg**. Endgültig.
- **`abgeschlossen`** — Der Auftrag ist **seinen definierten Weg zu Ende gegangen**.
  Nicht «hat das Ende-Objekt passiert»: ein **Ausgang** (terminales Modul) ist ebenfalls
  ein Ende.
- **`abgebrochen`** — Das Ziel ist **nicht mehr erreichbar** (siehe §2.2).
- **`inaktiv`** — Artikel ausser Betrieb: er **erzeugt nichts Neues**. Bestehende
  Stücke laufen weiter, «ab Lager» bleibt erlaubt. **Abgeleitet, nicht gesetzt**:
  er gilt genau dann, wenn ein Nachfolger den Artikel abgelöst hat
  (`replaced_by_id`, PROCESS_CORE §5.5). Es gibt keinen Schalter dafür – und damit
  auch keinen Weg zurück: wer den Vorgänger weiterbauen will, ersetzt ihn nicht.

**Nur ein Einzelinstanz-Zustand darf terminal sein.** Er ist der einzige, der gespeichert
und geändert wird; Auftrags- und Artikelzustände sind abgeleitet bzw. anderswo geführt.

**Alles Weitere ist abgeleitet, nicht zweitgepflegt:** «selektierbar» folgt aus
`terminal`, der Schutz in der Datenbank ebenso, und die Bestands-Zugehörigkeit ist eine
Eigenschaft am Status. Es darf keine zweite Liste geben, die jemand nachziehen muss.

**Die Farbe folgt NICHT aus `terminal`.** Hier stand einmal «endgültig = rot, aufhebbar =
gelb» – das stimmte, solange die einzigen Ausgänge *Verschrottet* und *Gesperrt* hiessen.
Mit *Verbaut* stimmt es nicht mehr: aufhebbar **und** grün, weil es seinen Zweck erreicht
hat. Der Ton sagt «gut · offen · Problem», `terminal` sagt «gibt es einen Weg zurück» –
zwei Fragen, und eine Regel, die beide beantwortet, wäre beim nächsten Zustand falsch.

> **Drei Wörter beantworten hier zwei Fragen** (`CONCEPT_REVIEW` §3). Kein Verhalten ist
> davon falsch — die Kosten trägt, wer neu dazukommt, und `is_active` hat gezeigt, dass
> solche Kosten irgendwann als Fehler anfallen:
>
> * **`terminal`** heisst am **Status** «für dieses Stück gibt es keinen Weg mehr» und am
>   **Modul** «die Reise endet hier». Beim Aussondern mit `mode=block` lauten die Antworten
>   verschieden: ein **terminales Modul** setzt einen **nicht-terminalen** Status.
> * **`release`** heisst als Vorgang «den Auftrag **starten**», als Spalte
>   (`OrderUnit.released_at`) «die Zugehörigkeit ist **beendet**». `released_at IS NULL`
>   liest sich wie «noch nicht freigegeben» und bedeutet «noch aktiv».
> * **`freigegeben`** meint am Stück «in keinem Auftrag», am Artikel «auftragsfähig» — und
>   die gleichnamige **Aktion** («Auftrag freigeben») ist genau der Vorgang, der ein Stück
>   aufhören lässt, freigegeben zu sein.

### 1.2 Die vollständige Übergangsmatrix (Einzelinstanz)

> **Jeder nicht aufgeführte Übergang ist verboten.**
> Es gibt genau **eine** Schreibstelle für einen Statuswechsel; jeder Wechsel schreibt im
> selben Atemzug einen Eintrag in den Ereignis-Log. Ein zweiter Schreibweg wäre eine
> zweite Wahrheit.

| # | von | nach | Ereignis | Auslöser / Bedingung |
|---|---|---|---|---|
| T1 | *(entsteht)* | `freigegeben` | Erzeugung | Nur bei der Freigabe eines Auftrags mit `Neu`-Zeile. Die einzige Stelle im System, an der Einzelinstanznummern entstehen. |
| T2 | `freigegeben` | `im_prozess` | **start** | Auftragsfreigabe. Der **Regelstart**. |
| T3 | `im_prozess` | `im_prozess` | **start** | Auftragsfreigabe, Stück wird einem **laufenden** Auftrag entzogen → der neue Auftrag ist eine **Abweichung**. |
| T4 | `gesperrt` | `im_prozess` | **start** | Auftragsfreigabe, gesperrtes Stück wird gegriffen → **Sonderfreigabe**, ebenfalls eine Abweichung. |
| T5 | `im_prozess` | `im_prozess` | **step** | Modul «Datenerfassung», Urteil **bestanden**. Ein Durchläufer. |
| T6 | `im_prozess` | `verschrottet` | **step** | Modul «Aussondern», Ausprägung *Verschrotten*. **Terminal.** |
| T7 | `im_prozess` | `gesperrt` | **step** | Modul «Aussondern», Ausprägung *Sperren*. |
| T7b | `im_prozess` | `verbaut` | **step** | Modul «Verbrauch», für die **genannten Artikel**. Der Rest passiert dasselbe Modul unverändert (T5) – der Ausgang gilt je Stück, nicht je Modul. |
| T7c | `verbaut` | `im_prozess` | **start** | Auftragsfreigabe, verbautes Stück wird gegriffen → **Demontage**, ebenfalls eine Abweichung. |
| T8 | `im_prozess` | `freigegeben` | **end** | Das Stück passiert das Ende-Objekt und kehrt **nirgends** zurück. Der Wert ist der `end_status` des Auftrags (heute immer `freigegeben`, an einer Stelle hinterlegt). |
| T9 | `im_prozess` | `im_prozess` | **end** | Das Stück passiert das Ende-Objekt und **kehrt in seinen Quell-Auftrag zurück**. Es bleibt im Prozess — es ist ja in einem. |

**Ereignisse ohne Statuswechsel** (sie stehen im Log, ändern aber nichts am Zustand):

| Ereignis | Bedeutung |
|---|---|
| **handover** | Das Stück hat *diesen* Auftrag verlassen (geschrieben beim **Quell**-Auftrag). |
| **return** | Das Stück ist zurückgekehrt (geschrieben beim **Ziel**-Auftrag). |
| **sample** | Das Stück wurde in die Stichprobe **gezogen**. Gezogen zu sein ist keine Zustandsänderung. |
| **capture** | Es wurde erfasst, mit Urteil **je Stück**. Gemessen wird, was da ist. |

**Ausdrücklich verboten und auf drei Ebenen geschützt:**

- `verschrottet` → **irgendetwas**. Geschützt an der einen Schreibstelle (409 mit Satz
  und Stücknummer, bevor irgendetwas geschrieben ist), durch einen **Datenbank-Trigger**
  (er kennt auch Reparaturskripte, Migrationen und `UPDATE` von Hand) und durch den
  **Abgleich Log ↔ Zeile** (Widerspruch: der Log sagt Endzustand, die Zeile sagt anderes).
- `freigegeben` → `verschrottet` / `gesperrt` **direkt**. Aussondern ist ein Modul; ein
  Auftrag muss das Stück erst greifen (T2), dann aussondern (T6/T7).
- `gesperrt` → `verschrottet` **direkt**. Erst greifen (T4), dann aussondern.
- `verbaut` → `verschrottet` **direkt**. Erst ausbauen (T7c), dann aussondern.
- Jeder Wechsel **ohne** Log-Eintrag. Es gibt keinen.

**Es gibt keine Umgehung.** Kein Parameter, kein Force-Flag, keine
Administrator-Ausnahme. Wer eine bräuchte, hat ein Modellproblem: ein Zustand, den man
doch verlassen können muss, ist schlicht nicht terminal — und das ist eine Zeile im
Katalog.

### 1.3 Einheitlichkeitsprüfung

**Gibt es Status, die dasselbe bedeuten?**

- `freigegeben` steht auf **zwei** Achsen (Einzelinstanz, Artikel) mit unterschiedlichem
  Gegenstand, aber derselben Aussage: *einsatzbereit*. Bewusst dasselbe Wort.
- `im_prozess` steht auf **zwei** Achsen (Einzelinstanz, Auftrag). Der Auftrag ist im
  Prozess, solange seine Stücke es sind. Bewusst dasselbe Wort.
- `gesperrt` und `verschrottet` bedeuten **nicht** dasselbe: beide heissen «aus dem
  Verkehr gezogen», sie unterscheiden sich in der Umkehrbarkeit — und die ist genau die
  Eigenschaft `terminal`. Es ist ein Modul mit zwei Ausprägungen, nicht zwei Module.
- **Kein Duplikat gefunden.** Es gibt keine zwei Wörter für denselben Zustand.

**Gibt es Übergänge, die an zwei Stellen unterschiedlich behandelt werden?**

Der Sollzustand verlangt: **nein.** Konkret sind die Stellen, an denen dieselbe Frage
zweimal gestellt wird, und wie sie zusammenhängen müssen:

| Frage | Wo sie gestellt wird | Regel |
|---|---|---|
| «Darf ein Auftrag dieses Stück greifen?» | Freigabe · Entwurfs-Prüfung · Auswahl-Liste der Oberfläche | **Eine** Ableitung aus `terminal`. Die Auswahl-Liste darf nie mehr anbieten als die Freigabe annimmt — und nie weniger. |
| «Ist dieser Zustand endgültig?» | Schreibstelle · Datenbank-Trigger · Invariantenprüfung | **Eine** Liste (der Katalog), drei Leser. Der Trigger wird aus dem Katalog **erzeugt**, nicht von Hand geschrieben. |
| «Wartet dieser Auftrag auf eine Rückführung?» | Auftragsstatus · Modul-Sperre · Prozessbild | **Eine** Ableitung über die offenen rückführenden Verbindungen, entlang der ganzen Kette. |
| «Wer ist gezogen?» | Erfassungspflicht · Vorschau-Zahlen · Nummern-Liste | **Eine** Quelle: der `sample`-Eintrag im Log. Nie neu gewürfelt, nie aus dem Vorhandensein einer Erfassung abgeleitet. |

---

## 2. Auftragsstatus

### 2.1 Drei Werte, alle abgeleitet

Ein Auftrag hat genau **drei** Zustände, und **keiner** wird gesetzt. Es gibt keine
Status-Spalte am Auftrag; sie wäre der zweite Ort und liefe beim ersten vergessenen
Update weg.

«Freigegeben» kommt bewusst **nicht** vor: Freigeben ist die **Aktion**, mit der der
Auftrag entsteht, kein Zustand, in dem er verweilt.

Die Ableitung braucht genau drei Zahlen:

| Zahl | Definition |
|---|---|
| **angekommen** | Zugehörigkeiten, die **geschlossen** sind **und** vor keinem Modul mehr stehen. |
| **unterwegs** | Zugehörigkeiten, die **offen** sind **und** deren Stück es noch gibt. |
| **verliehen** | Stücke, die einer Abweichung geliehen sind **und zurückkommen** — über die **ganze Kette** gezählt. |

```
unterwegs > 0  oder  verliehen > 0   →  Im Prozess
sonst, angekommen > 0                →  Abgeschlossen
sonst                                →  Abgebrochen
```

**Die Reihenfolge ist nicht beliebig.** «Angekommen» darf «noch unterwegs» nicht
schlagen, sonst gälte ein Auftrag als fertig, sobald das erste Stück durch ist. Solange
alle Stücke im Gleichschritt laufen, fällt das nie auf — mit Abweichungen sofort.

### 2.2 Was «kann das Ziel nicht mehr erreichen» genau heisst

> **Abgebrochen = es ist nichts mehr unterwegs, nichts kommt zurück, und angekommen ist
> auch nichts.**

Das ist **keine** eigene Regel und **kein** vierter Wert — es ist der Rest der Ableitung.
Mit terminalen Modulen (Ausgängen) fällt es so:

| Lage | Auftrag |
|---|---|
| Alle Stücke ausgesondert (verschrottet **oder** gesperrt) | **Abgeschlossen** — der Ausgang IST das Ende des Weges. Wer aussondert, hat getan, wozu er da war. |
| Alle Stücke von Abweichungen **gekappt** übernommen | **Abgebrochen** — sie kommen nie zurück, es bleibt nichts. |
| Alle Stücke von Abweichungen **rückführend** übernommen | **Im Prozess** — verliehen zählt. |
| Ein Stück angekommen, eines in einer rückführenden Abweichung | **Im Prozess** — was noch unterwegs ist, gewinnt. |
| Ein Stück angekommen, eines gekappt übernommen | **Abgeschlossen** — mit reduzierter Menge. |
| In der Abweichung wurde ausgesondert (Kette bricht) | Der Abweichungsauftrag ist **Abgeschlossen**; der Auftrag darüber verliert das Stück endgültig und ist — wenn ihm nichts bleibt — **Abgebrochen**. |

**Der entscheidende Punkt:** ein Ausgang **schliesst die Zugehörigkeit** genauso wie das
Ende-Objekt. Damit endet die Warte-Kette von selbst, ohne eine Zeile Wartelogik — gezählt
wird über die **offene** Verbindung, und die gibt es nicht mehr. Die Absicht «kehrt
zurück» (`return_to_order_id`) bleibt dabei **unangetastet** stehen: sie war da, und die
Vergangenheit wird nicht umgeschrieben.

---

## 3. Die unverhandelbaren Grundregeln

Als prüfbare Sätze. Jeder ist so formuliert, dass ein Test ihn widerlegen könnte.

### G1 — Im Prozess wird ausschliesslich mit Einzelinstanzen gearbeitet

1. Jeder Statuswechsel im Prozess betrifft genau eine Einzelinstanz.
2. Es gibt keinen Prozessschritt, der eine Instanz oder einen Artikel als Ganzes bewegt.
3. Eine Instanz trägt **keinen** eigenen Status und **keine** Mengen-Spalte; beides wird
   aus ihren Einzelinstanzen abgeleitet.
4. Eine Einzelinstanz trägt **keine** Mengen-Spalte. Sie ist genau ein Stück — das ist
   ihre Definition, keine Einstellung.
5. Der **Scan** ist die Ausnahme, und sie ist keine: er verifiziert die **Instanz**, weil
   das Etikett am physischen Ding klebt. Gearbeitet wird trotzdem an ihren
   Einzelinstanzen. Charge = ein Scan / n Erfassungen; Einzelserialisierung = n Scans.

### G2 — Eine Einzelinstanz ist immer nur in genau einem Auftrag aktiv

1. **Aktiv** heisst: offene Zugehörigkeit zu einem Auftrag. **Referenziert** (Historie,
   Log, abgeschlossener Auftrag) ist beliebig oft erlaubt.
2. Der Versuch, ein aktives Stück in einem zweiten Auftrag zu **definieren**, ist ein
   harter, sprechender Fehler — er nennt das Stück und den Auftrag, in dem es aktiv ist.
3. Die Regel wird **auf Datenbankebene** erzwungen, nicht nur in der Anwendungslogik.
   Zwei gleichzeitige Freigaben lesen sonst beide «ist frei» und schreiben beide.
4. Der **Abweichungsauftrag ist keine Ausnahme**: er **entzieht** das Stück dem laufenden
   Auftrag (alte Zugehörigkeit schliessen, dann neue anlegen), statt es ein zweites Mal
   aktiv zu machen.
5. Reservierung, Anteil und Unterdeckung **entfallen ersatzlos**. Nichts davon wird
   gebaut, auch nicht vorbereitend.

### G3 — Nichts wird erfunden

1. Fehlende Pflichtdaten ergeben einen **sauberen Fehler mit Namen**, nie einen
   Platzhalter, Standardwert oder geschätzten Wert.
2. Eine Menge, die nicht aufgeht, bricht die Transaktion ab — sie wird nicht stillschweigend
   korrigiert.
3. Ein unbekannter Status wird **gemeldet**, nicht einsortiert. Eine Bestandsleiste, die
   ihn stillschweigend mitzählt, verbirgt genau den Fehler, den man sehen müsste.
4. Eine Zahl, die abgeleitet werden kann, wird **abgeleitet** und nicht gespeichert.
   Zwei Kopien laufen auseinander.
5. Ein `except`, das einen Fehler verschluckt, ist ein Fehler. Zulässig ist nur, einen
   Fehler in einen **sprechenderen** zu übersetzen.
6. **Ausnahmen, die erlaubt sind — und nur diese:** ein *unbekannter* Wert darf als roher
   Wert angezeigt werden (damit die Anzeige nicht lügt), und eine *Alt-Definition* darf
   einen dokumentierten Rückfall haben (siehe §5, Punkt 3). Beides ist ein Rückfall für
   **Historie**, nie für eine Eingabe.

### G4 — Terminale Status sind endgültig

1. Aus einem terminalen Status heraus gibt es **keinen** Übergang — aus keinem Anlass, an
   keiner Stelle, durch kein Modul.
2. Der Schutz gilt auf **drei** Ebenen: die eine Schreibstelle, die Tabelle selbst
   (Trigger), und der Abgleich Log ↔ Zeile.
3. Ein Stück in einem terminalen Status ist **überall unerreichbar**: die Auswahl-Liste
   weist es aus, der Entwurf ist nicht freigebbar, die Freigabe lehnt ab. Nicht erst beim
   letzten Klick.
4. **Es gibt keine Umgehung.**

### G5 — Was passiert ist, ist eingefroren

1. Der Ereignis-Log ist **append-only**: kein Update, kein Delete, kein `is_active`, kein
   `updated_at`. Eine Korrektur ist ein **neuer Eintrag**.
2. Die **Reihenfolge** ist die `id`, nicht der Zeitstempel — zwei Einträge können dieselbe
   Sekunde tragen.
3. Eine gezogene Stichprobe ist eingefroren. Sie wird nie neu gewürfelt.
4. Eine einmal **gegangene** Kante im Prozessbild wird nie wieder schwach.
5. Eine Ansicht der Vergangenheit darf **keine bewegliche Grösse lesen**. Was ein anderer
   Auftrag später mit dem Stück tat, gehört nicht in die Geschichte dieses Auftrags.
6. Eine Einzelinstanz wird nie gelöscht und nie deaktiviert. Ihre Nummer ist eine
   Identität, keine Position.

### G6 — Backend ist Master

1. Jede fachliche Ableitung entsteht im Backend. Das Frontend layoutet und zeichnet.
2. Das Prozessbild wird als **Graph** geliefert (Knoten, Kanten, Positionen,
   Kantenzustand) — die Oberfläche rechnet keine Prozesslogik.
3. Eine Regel, die die Oberfläche durchsetzt, aber der Dienst nicht kennt, ist ein
   **Fehler**: sie ist eine erfundene Sperre, und eine erfundene Sperre hat keinen
   Schlüssel.
4. Umgekehrt gilt: eine deaktivierte Schaltfläche ist **keine** Absicherung, sondern eine
   Bitte. Jede harte Regel liegt zusätzlich serverseitig.
5. Der Status-Katalog wird ins Frontend **generiert**, nicht gespiegelt. Ein Spiegel, den
   ein Test vergleicht, *findet* ein Auseinanderlaufen — verhindert es aber nicht.

---

## 4. Sackgassen-Analyse

> **Ein Zustand ohne Ausgang, der nicht ausdrücklich terminal ist, ist ein Fehler.**

### 4.1 Zustände einer Einzelinstanz

| # | Zustand | Wie kommt man hier raus? |
|---|---|---|
| U1 | `freigegeben`, keine offene Zugehörigkeit — **freier Bestand** | Ein beliebiger Auftrag greift es (T2). |
| U2 | `im_prozess`, offene Zugehörigkeit, steht vor Modul X | Modul X bestätigen (T5/T6/T7) **oder** ein anderer Auftrag greift es (T3, Abweichung). |
| U3 | `im_prozess`, **ausgeschert** — geschlossene Zeile mit Punkt, offene Zeile im Abweichungsauftrag | Der Abweichungsauftrag läuft durch: Rückkehr (T9) an denselben Punkt, oder Ende ohne Rückkehr (T8), oder Aussonderung (T6/T7). |
| U4 | `im_prozess`, Modul **angehalten** (letztes Urteil «nicht bestanden») | **Erneut erfassen** — das nächste Urteil ersetzt das letzte. Zusätzlich: ein Abweichungsauftrag kann das Stück greifen. **Der Halt ist eine Auskunft, keine Sperre.** |
| U5 | `im_prozess`, Modul **gesperrt** (wartet auf Rückführung) | Die ausstehende Rückführung abschliessen — dann fällt die Sperre von selbst. Oder: in der Abweichung wird ausgesondert, dann endet die Wartekette. |
| U6 | `gesperrt`, keine offene Zugehörigkeit — **gesperrter Bestand** | Ein **ganz gewöhnlicher** Auftrag greift es (T4). Das Greifen IST das Aufheben; es gibt bewusst keinen Entsperren-Endpunkt. |
| U6b | `verbaut` — steckt in einem anderen Stück | Ein **ganz gewöhnlicher** Auftrag greift es (T7c). Das Greifen IST der Ausbau; es gibt bewusst keinen «demontieren»-Endpunkt. **Die Stückliste des Produkts verliert es dabei nicht** – sie kommt aus dem Log, und was verbaut *war*, bleibt verbaut gewesen. |
| U7 | `verschrottet` | **Kein Ausgang — ausdrücklich terminal.** Das ist die Zusage, keine Sackgasse. |

**Unmögliche Kombinationen** (sie dürfen nicht vorkommen, und ihr Auftreten ist ein
Befund):

- Offene Zugehörigkeit **ohne** Zustandspunkt (`current_step_id NULL`): wer das Ende
  passiert, wird frei — die Zeile wird geschlossen.
- Zwei offene Zugehörigkeiten für dasselbe Stück (verletzt G2).
- `freigegeben` **mit** offener Zugehörigkeit: der Start setzt sofort `im_prozess`.
- `verschrottet` mit offener Zugehörigkeit: der Ausgang schliesst sie.

### 4.2 Zustände eines Auftrags

| # | Zustand | Wie kommt man hier raus? |
|---|---|---|
| O1 | `im_prozess`, ein Modul ist dran | Modul bestätigen. |
| O2 | `im_prozess`, das aktive Modul ist **gesperrt** (wartet auf Rückführung) | Zwei Wege: die Abweichung abschliessen — **oder ihr die Stücke ihrerseits entziehen** (§4.4). Der zweite gilt immer, auch wenn die Abweichung liegen bleibt. |
| O3 | `im_prozess`, das aktive Modul ist **angehalten** (Urteil «nicht bestanden») | Erneut erfassen (U4). |
| O4 | `im_prozess`, alle Stücke ausgeliehen (rückführend) | Die Abweichungen laufen durch — oder sie werden ihrerseits leergeräumt (§4.4). |
| O5 | `abgeschlossen` | Terminal für den Auftrag — er hat getan, wozu er da war. **Kein Ausgang nötig.** |
| O6 | `abgebrochen` | Terminal für den Auftrag — sein Ziel ist unerreichbar. **Kein Ausgang nötig.** |

### 4.4 Der Abbruch IST eine Abweichung

> **Es gibt keine Abbruch-Funktion, und das ist eine Entscheidung — kein Loch.**

Ein Auftrag wird abgebrochen, indem ihm über einen **Abweichungsauftrag alle Stücke
entzogen und die Rückführung gekappt** wird.

**Warum das der bessere Weg ist:** er zwingt dazu, zu regeln, **was mit diesen Stücken
geschehen soll** — verschrotten, sperren, an einen anderen Auftrag übergeben. Ein Knopf
«abbrechen» liesse genau diese Frage offen und hinterliesse Stücke ohne Bestimmung.

**Der Auftragsstatus folgt von selbst.** Es braucht dafür keine Zeile Code: sind alle
Stücke entzogen und kommt keines zurück, ist `unterwegs = 0`, `verliehen = 0`,
`angekommen = 0` — und das ist genau `Abgebrochen` (§2.1). Geprüft in der Matrix:

| Fall | was er beweist |
|---|---|
| **S57** | alle Stücke entzogen und gekappt → Eltern `Abgebrochen`, wartet nicht mehr, kein Modul gesperrt, und die Stücke haben ein definiertes Schicksal |
| **S58** | derselbe Weg beim **obersten** Auftrag (Erzeugungsauftrag, kein Vorgänger) |
| **S59** | ein **liegengelassener** Abzweig klemmt seinen Eltern nicht dauerhaft — man entzieht ihm seinerseits die Stücke, und beide Ebenen lösen sich auf |

**Damit ist O2 kein Risiko mehr, sondern ein Zustand mit zwei Ausgängen.**

### 4.5 Bekannte Risiken auf dieser Landkarte

Diese Punkte sind **nicht** behauptete Fehler — sie sind die Stellen, an denen die
Landkarte dünn ist und an denen darum getestet wird.

| Risiko | Frage | Stand |
|---|---|---|
| **R1 — die Wartekette** | Wartet ein Auftrag auf eine Abweichung, die ihrerseits wartet: löst sich die Kette bis nach oben auf? | **geprüft** (S43 · S47) — ja, über drei Ebenen |
| **R2 — kein Abbruch** | Ein Auftrag, dessen Abweichung nie fertig wird: gibt es einen Ausgang? | **beantwortet** (§4.4) — ja, man entzieht ihr die Stücke (S59) |
| **R3 — Nebenläufigkeit** | Zwei gleichzeitige Freigaben mit demselben freien Stück | **geprüft** (S63) — genau eine gewinnt; der Verlierer bekommt je nach Timing eine rohe Datenbankmeldung (🟡-5) |
| **R4 — Stichprobe und Rückkehr** | Kann ein Stück durch eine Abweichung der Prüfung entgehen? | **geprüft** (S26) — nein, das Modul ist gesperrt, solange etwas zurückkommt |
| **R5 — Artikel inaktiv** | Lässt sich mit einem inaktiven Artikel noch etwas erzeugen? | **behoben** (S98 · S98b) — «Neu» gesperrt, «Lager» bleibt |
| **R6 — leere Menge** | Stimmt die Mengenbilanz nach vollständiger Aussonderung? | **geprüft** (S81) — ja, die Zeilen bleiben, nur der Zustand wechselt |
| **R7 — `units_may_leave`** | Ein künftiger Modultyp mit Aussenwirkung (Einkauf, Verkauf) darf `units_may_leave = False` setzen. Dann lässt sich ein Stück vor diesem Modul **nicht** herausnehmen — und weil der Abbruch genau darüber läuft (§4.4), wäre der Ausgang zu. | **latent, ungeprüft.** Heute gibt es keinen solchen Modultyp. Wer den ersten baut, muss den Ausgang mitbeantworten. |
| **R8 — Korrektur nach dem Vorrücken** | Eine Erfassung ist falsch und fällt erst auf, wenn das Stück das Modul verlassen hat. Gibt es einen Weg? | **nein** (`CONCEPT_REVIEW` §1.6). Solange das Stück davorsteht, ersetzt das nächste Urteil das letzte (U4); danach findet `_units_at` es dort nicht mehr, und eine Ereignisart für eine Korrektur gibt es nicht. Der Docstring von `ProcessEvent` verspricht sie bereits. **Ohne sie wandert die Korrektur auf Papier — und ab da ist das System nicht mehr die Quelle.** |
| **R9 — gleichzeitiges Bestätigen** | Zwei Personen bestätigen dieselbe Instanz am selben Modul im selben Moment. | **ungeprüft, Vermutung.** `confirm_step` nimmt keine Sperre; beide lesen dieselbe Warteliste. Erwartet wird kein kaputter Zustand, aber ein **doppelter Nachweis** (zwei Erfassungszeilen, zwei Schritt-Ereignisse). S63 prüft Nebenläufigkeit nur bei der **Freigabe**. |
| **R10 — wer darf** | Jeder Endpunkt hängt an `require_employee`; es gibt keine Rolle je Modultyp. Wer sich anmelden kann, kann 600 Stück verschrotten. | **bewusst offen.** Die **Attribution** ist lückenlos (`actor_id` an jedem Ereignis) — damit ist die Absicht «wer es zu verantworten hat» erfüllt. Was fehlt, ist **Prävention** bei den unumkehrbaren Vorgängen. Der Ort für die Regel existiert (`Module`, neben `terminal`/`requires_verification`). |

### 4.6 Was ausserhalb dieser Landkarte liegt

> §4.1–§4.2 kartieren jeden Zustand, den es **gibt**. Diese Tabelle nennt die Vorgänge, für
> die es **keinen** gibt — sie können darum in keiner Sackgassen-Analyse auftauchen und
> sind bis zum Konzeptreview (`CONCEPT_REVIEW.md`) nirgends festgehalten gewesen.

| Vorgang | Warum das Modell ihn nicht kennt |
|---|---|
| **Montage** (4 Teile → 1 Baugruppe) | Es gibt **keine Beziehung zwischen zwei Einzelinstanzen** — nur die zeitliche (Journey §7.4). Kein «besteht aus», kein «steckt in». Dazu fehlt der Zustand: `verbraucht` ist im Katalog ausdrücklich **nicht angelegt**, und `_assert_single_new` (#693) verbietet die eine Auftragsform, die eine Montage wäre (verbrauchende `Lager`-Zeilen **plus** eine erzeugende `Neu`-Zeile). |
| **Teilung** (eine 6-m-Stange → 3 Stücke) | Umkehrung derselben Lücke. Zusätzlich hat die Länge im Modell keinen Platz (keine Mengen-Spalte, D1) — sie lässt sich nur als Erfassungswert führen. |
| **Verbrauch** | Ein Stück verlässt den Bestand heute ausschliesslich über `Verschrottet`. «Verbaut» als Endzustand gibt es nicht — der Bestand enthält damit auch alles, was eingebaut oder ausgeliefert wurde. |
| **Ort** | Es gibt keinen Halter, keine Standort-Spalte, keine Kette. Solange ein Stück in einem Auftrag läuft, ist «vor Modul X» die Antwort; bei **freiem** Bestand ist sie leer. Das ist die grösste Abweichung zwischen der Absicht (*«wo es ist»*) und dem Modell. |
| **Zweck eines Auftrags** | Ein Auftrag trägt Objektnummer, den daraus gebildeten Namen und den Endzustand. Warum es ihn gibt, steht nirgends — bei zwei Aufträgen mit demselben Ablauf ist es nicht einmal erschliessbar. |
| **Termin / Soll-Dauer** | Der Auftragsstatus hat keine Zeitachse. Ein Auftrag, an dem seit sechs Wochen niemand war, ist von einem laufenden nicht unterscheidbar. |

**Der gemeinsame Prüfstein für die letzten drei:** die Regel «nichts speichern, was sich
ableiten lässt» (G3) ist richtig und bleibt. Sie hat aber auch Angaben mit entfernt, die
sich **nicht** ableiten lassen — Ort, Zweck und Termin existieren nur im Kopf dessen, der
handelt. Ein Feld ist zulässig, **wenn seine Angabe aus keiner anderen im System
herleitbar ist**; alles Übrige bleibt verboten.

---

## 5. Was ausdrücklich (noch) nicht entschieden ist

Diese Punkte gehören zur Grundlogik, sind aber **nicht** entschieden. Sie werden
einzeln nachgetragen — nicht beim Bauen erraten. Ein Test darf hier nichts behaupten.

1. ~~**Abbruch eines Auftrags.**~~ **Entschieden** (§4.4): es gibt **keine**
   Abbruch-Funktion. Ein Auftrag wird abgebrochen, indem ihm über einen
   Abweichungsauftrag alle Stücke entzogen und die Rückführung gekappt wird — der Weg
   zwingt dazu, das Schicksal der Stücke zu regeln.
2. **Darf ein Abweichungsauftrag ausgelöst werden, während in einem Modul bereits mit der
   Eingabe begonnen wurde?** Gebaut ist die restriktivere Variante, **als Eigenschaft des
   Modultyps**, nicht als globale Regel. Serverseitig ist das nicht erzwingbar: eine nicht
   bestätigte Eingabe existiert nirgends.
   **Achtung, seit §4.4:** derselbe Schalter (`Module.units_may_leave`) entscheidet auch,
   ob sich ein Auftrag noch abbrechen lässt — siehe Risiko R7.
3. **Stichprobenregel fehlt in einer Alt-Definition** → es gilt «alle». Das ist ein
   dokumentierter Rückfall für **Historie**, kein Standardwert für neue Eingaben. Eine
   neue Definition trägt die Regel immer.
4. **Weitere Modultypen.** Zwei sind fertig (Datenerfassung, Aussondern). Was ein Modul
   mit Aussenwirkung (Einkauf, Verkauf) beim Herausnehmen eines Stücks tun muss, ist noch
   nicht entschieden — der Schalter dafür steht an einer Stelle.
5. ~~**Montage, Teilung, Verbrauch.**~~ **Entschieden und gebaut** (Modul «Verbrauch»):
   der Zustand `verbaut` steht im Katalog (**nicht** terminal – Demontage ist real), das
   Modul setzt ihn **je Artikel** statt je Modul, und `_assert_single_new` heisst jetzt
   «höchstens eine `Neu`-Zeile». Die **Stückliste ist eine Ableitung** über den
   gemeinsamen Auftrag (`services/genealogy`), gelesen aus dem **Log** – darum überlebt
   sie eine Demontage. Wächter: `tests/test_consumption_module.py`, Matrix S11 · S11b ·
   S16 · S17 · S18.
   **Offen bleibt die Teilung** (eine 6-m-Stange in drei Stücke): sie ist die
   Gegenrichtung derselben Lücke und braucht zusätzlich eine Antwort darauf, wie neue
   Stücke **ohne** Erzeugungsauftrag entstehen.
6. **Ort.** Ob und wie ein Halter je Einzelinstanz geführt wird (§4.6). Bis dahin ist
   *«wo ist es»* für freien Bestand unbeantwortbar. Der Vorgänger hatte eine
   Standort-Kette; sie wieder aufzunehmen heisst, ihre Fehler nicht mitzunehmen.
7. **Zweck des Auftrags.** Ein Pflichtfeld «warum gibt es diesen Auftrag» — ein Satz, wie
   ihn das Aussondern-Modul für seinen Grund bereits verlangt, und aus demselben Grund.
   Ohne ihn wirft das abgeleitete Label «Abweichung» acht verschiedene Vorgänge zusammen
   (`CONCEPT_REVIEW` §2), und eine Sonderfreigabe hat keinen dokumentierten Anlass.
8. **Termin und Soll-Dauer** (§4.6). Ohne Soll ist «hängt seit sechs Wochen» nicht von
   «dauert eben so lange» zu unterscheiden — und zwar unabhängig davon, wie gut eine
   Auswertung gebaut wäre.
9. **Werkzeug- und Prüfmittel-Nachweis — es gibt ihn nicht mehr.** Der Erfassungstyp
   «Objekt scannen» ist **ersatzlos entfernt** (Testnotiz #719, bewusste Entscheidung).
   Er war die einzige Stelle, an der «mit welchem Werkzeug wurde gearbeitet» bzw. «mit
   welchem Prüfmittel wurde gemessen» überhaupt festhaltbar war; damit ist diese Aussage
   im System **nirgends** mehr abgebildet.
   Das ist kein Verlust an Bequemlichkeit, sondern an Nachweisbarkeit: bei einer
   Messmittel-Rückführung (ISO 9001 §7.1.5) lautet die Frage rückwärts – *welche Teile
   wurden mit dem Gerät geprüft, das jetzt als dejustiert auffällt?* Ohne den Vermerk am
   Vorgang ist sie unbeantwortbar, und man sperrt im Zweifel alles.
   **Warum trotzdem ersatzlos:** ein Werkzeug ist **kein Verbrauch** — eine Fräse steckt
   real in zwanzig Aufträgen gleichzeitig, die Exklusivität der Einzelinstanz liesse
   genau einen zu. Der Erfassungspunkt war der billige Weg daran vorbei; er hat den
   Nachweis erfasst, ohne die Nutzung zu modellieren. Wer ihn zurückwill, entscheidet
   zuerst die Modellfrage (**Nutzung ohne Exklusivität**), nicht die Eingabefrage.

   > Bis dahin gilt: das System **behauptet nicht**, den Nachweis zu führen. Genau darum
   > steht der Punkt hier und nicht als stille Lücke im Code (G3).

### 5.5 Setzt die Abweichung nach einem «nicht bestanden» VOR oder NACH dem Modul an?

**Gebaut ist: davor.** Die Frage ist gestellt (Testnotiz #713) und die vorgeschlagene
Präzisierung der Regel ist übernommen (§12.4): *die Abzweigung hängt an der aktuellen
Position der Einzelinstanz.* Genau das rechnet `flow.build` — der Abzweigepunkt sitzt auf
`order_units.current_step_id`. Die Zeichnung ist damit **keine** Behauptung; sie gibt die
Position wieder.

Die eigentliche Frage ist darum nicht, wo gezeichnet wird, sondern: **rückt eine
durchgefallene Einzelinstanz vor?** Heute nicht (§4.5), und daran hängen drei Dinge:

| Was daran hängt | warum es ohne «steht davor» nicht geht |
|---|---|
| **Der Halt ist sichtbar** | `step_work` listet, was vor dem Modul steht. Rückt das Stück vor, verschwindet es aus dieser Liste — und mit ihm die Meldung «nicht bestanden» und die angebotene Abweichung. |
| **Nichts läuft still weiter** | Ein vorgerücktes Stück steht vor dem **nächsten** Modul und wird dort ganz normal bearbeitet. Ein durchgefallenes Stück liefe damit bis zum Ende durch und käme als «Freigegeben» ans Lager. |
| **Der Halt braucht keinen Schlüssel** | Ihn stattdessen zu **sperren** hiesse, eine Sperre einzuführen — und die bräuchte jemanden, der sie aufschliesst (§4.5 begründet ausführlich, warum es die nicht gibt). |

**Was die Notiz zu Recht bemängelt, bleibt bestehen:** kehrt ein Stück aus der Abweichung
an denselben Punkt zurück, durchläuft es das Modul ein **zweites** Mal — und §7.1 verbietet
die «Wiederholung an Ort und Stelle». Heute ist das der dokumentierte Ausweg aus dem Halt
(«das nächste Urteil ersetzt das letzte», §4.5); wer die Wiederholung nicht will, **kappt
die Rückführung** — dann läuft der Auftrag mit weniger Stücken weiter und die Nacharbeit
lebt im Folgeauftrag.

**Zu entscheiden ist also eine Modellfrage, nicht eine Zeichnungsfrage:** soll ein
durchgefallenes Stück vorrücken und stattdessen ein **Zustand** es anhalten (der nächste
Kandidat wäre `Gesperrt`, §5.2)? Das wäre die einzige Variante, die «nach dem Modul» trägt,
ohne stilles Weiterlaufen zu erlauben — und sie kehrt eine ausdrückliche Entscheidung um
(§13: «weder Status noch automatischer Folgeauftrag»). Darum steht sie hier und ist nicht
gebaut.

---

## 6. Die Testbarkeitsregel

Jeder Satz in §1–§4 muss durch einen automatisierten Test widerlegbar sein. Ein Satz, für
den es keinen Test gibt, wird in `TEST_REPORT.md` ausdrücklich als **nicht geprüft**
ausgewiesen — nicht als bestanden.
