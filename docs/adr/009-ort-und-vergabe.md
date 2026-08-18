# ADR 009 – Ort und Vergabe: eine Beobachtung und ein Zyklus

Status: **angenommen** (August 2026) · Regeln: `PROCESS_CORE.md` §9.8 + §15 ·
Prüfbare Sätze: `SYSTEM_LOGIC.md` §7 · Wächter: `backend/tests/test_place.py`

---

## 1 · Warum es diesen Eintrag gibt

Das System hat seit dem Basis-Neuaufbau **keinen Ortsbegriff**. Das ist kein Versehen,
sondern das Ergebnis eines dreifachen Scheiterns: der Vorgänger hatte einen, und er hat
dreimal an derselben Wand gestanden. `SYSTEM_INTENT` §5a benennt die Lücke als die
grösste zwischen Absicht und Modell — *«wo ist es»* ist für freien Bestand heute
unbeantwortbar. `SYSTEM_LOGIC` §5.6 hält sie als bewusst offene Entscheidung fest, mit
dem Satz, um den es hier geht:

> Der Vorgänger hatte eine Standort-Kette; sie wieder aufzunehmen heisst, ihre Fehler
> nicht mitzunehmen.

Dieser Eintrag nennt die Fehler, damit sie benannt sind und nicht nur gemieden werden.

---

## 2 · Die Historie des Scheiterns

Alle Zeilenangaben aus Commit `2351bda` (dem letzten Stand vor dem Basis-Neuaufbau).

### 2.1 `movement.py` — die Fallunterscheidung, welche Stücke ein Modul anfasst

`movable_instances(db, order, step)` beantwortete die Frage «welche Stücke bewegt dieser
Schritt?» mit **drei** Zweigen und vier Ausnahmen darin: Retoure → nur `sold`;
Pflicht-Versand (`mode='customer'`) → verkaufte **und** eigene **und** ganz reservierte,
aber nicht gesperrte, aber nicht der unverkaufte Rest einer teilverkauften Charge; sonst
→ aktive Instanzen.

Jeder dieser Zweige ist eine nachträgliche Korrektur (die Kommentare nennen die
Testnotizen #646/#647 mitsamt ihren Symptomen: «vorher wurde die ganze Rest-Charge zum
Kunden bewegt und stand danach fälschlich als freier Bestand beim Kunden»). **Der Fehler
ist nicht der einzelne Zweig, sondern dass es überhaupt Zweige gab**: ein Modul las den
Verbleib und den Auftragsgrund, um zu entscheiden, woran es arbeitet. Damit hing die
Bewegung an Wissen über Verkauf, Retoure, Reservierung und Sperre — vier Bereiche, deren
Änderung jedes Mal hier ankam.

> **Die Regel daraus:** *Was vor dem Modul steht, ist was vor dem Modul steht.* Null
> Fälle. Ein Modul liest den Ort nie, um zu entscheiden, welche Stücke es anfasst.

### 2.2 `location_split.py` — die Mengen-Map

Eine Charge lag zu 300 in Behälter A und zu 700 in Behälter B. Weil eine Instanz eine
**Menge** war und ihre Objektnummer physisch am Etikett klebte, durfte sie nicht geteilt
werden. Also merkte sich die eine Zeile eine Standort→Menge-Map:

```
locations = {"100000123": {"t": "instance", "q": "300"},
             "100000124": {"t": "instance", "q": "700"}}   # Summe = quantity
```

Dazu, wörtlich aus dem Docstring: *«Ist die Charge an EINEM Ort → Map `None`, der Skalar
ist die Wahrheit. Verteilt → die Map ist die Wahrheit, der Skalar spiegelt die grösste
Teilmenge (denormalisiert).»*

**Zwei Wahrheiten mit einem Umschalter dazwischen.** Daraus folgten `reconcile` (die Map
nach einer Teil-Verschrottung nachziehen), `trim`, `set_single` (eine verteilte Charge
wieder zusammenführen) und die Pflicht jeder Leseseite, den richtigen der beiden Wege zu
kennen. 177 Zeilen, deren einziger Zweck es war, eine Menge auf Orte zu verteilen.

> **Die Regel daraus:** Die Aufteilung ist ein `GROUP BY`. «990 im Regal, 10 am Band» sind
> zehn Einzelinstanzen mit anderem Halter. Keine Map, kein Skalar, kein Umschalter.
> **`location_split.py` darf nicht wiederkehren.**

Das ist erst seit dem Basis-Neuaufbau möglich: die Einzelinstanz *ist* das Arbeitsobjekt
und trägt keine Mengen-Spalte (`SYSTEM_LOGIC` G1.4). Die Mengen-Map war die richtige
Antwort auf ein Datenmodell, das es nicht mehr gibt.

### 2.3 `provisioning.py` — das System, das selbst anlegt

404 Zeilen, deren Grundsatz lautete: *«Geplant wird, was der Nutzer will. Angelegt wird,
was die Physik verlangt.»* Jeder Schritttyp deklarierte seinen Bereitstellungsort; stimmte
Ist ≠ Soll, legte das System einen **Bereitstellungs-Unter-Auftrag** an.

Das Modul steht heute auf `AUTO_PROVISIONING = False` — abgeschaltet nach Testnotiz #204,
weil (a) der abgeleitete Unter-Auftrag im Ablauf **nicht als Unter-Auftrag erkennbar** war
und wie ein regulärer Schritt des Hauptprozesses aussah, und (b) seine Blockade nicht das
Gewollte traf. Davor waren bereits die fest eingebauten Begleit-Bewegungen (`companion`,
`locked`) aus demselben Grund entfallen.

Dreimal derselbe Befund: **ein Transport, den das System selbst anlegt, gehört niemandem.**
Niemand hat ihn gewollt, niemand erkennt ihn wieder, und wenn er klemmt, fehlt der Mensch,
der ihn auflösen könnte.

> **Die Regel daraus:** Das System legt nichts an — es **bietet an**. Ein Transport
> entsteht ausschliesslich durch den Klick eines Menschen auf einen vorausgefüllten
> Entwurf. Durchgesetzt als AST-Wächter, nicht als Vorsatz.

### 2.4 `logistics.py` — die gespeicherte Klassifikation

560 Zeilen für die Frage «ist das ein Versand oder eine innerbetriebliche Bewegung?».
Gespeichert wurden `transport_mode` (internal · parcel · freight) und eine Sendungsart;
Migration `076` hat die Werte `auto/carrier/self/none` wieder abgeschafft, Migration `081`
die Spalte `article_process_steps.transport_mode` — sie trug da noch **eine zweite,
veraltete Whitelist**, und ein Test prüfte ausgerechnet die veraltete.

Die Klassifikation selbst war richtig und ist es geblieben: *zwei Orte mit
unterschiedlicher Adresse → Versand, sonst intern.* Falsch war, sie zu **speichern**.

> **Die Regel daraus:** Richtung und Transportklasse werden **gerechnet**, nie gespeichert.
> Sie sind die Differenz zweier Halterorte, und die kennt das System jederzeit.

### 2.5 Der gemeinsame Nenner

Alle vier Module beantworteten dieselbe Frage zweimal — einmal als gespeicherter Wert und
einmal als Ableitung. Das ist exakt die Fehlerklasse, gegen die `SYSTEM_LOGIC` G3.4
geschrieben ist («eine Zahl, die abgeleitet werden kann, wird abgeleitet»), und sie hat
sich hier deshalb so hartnäckig gehalten, weil der Ort *fühlbar* wie ein Feld aussieht.

---

## 3 · Die Entscheidung

### 3.1 Der Ort ist eine Beobachtung, kein Schritt

Eine append-only Tabelle `unit_places`: **Einzelinstanz · Halter · wer · wann · woher**
(`scan` | `tracking`). Der aktuelle Ort ist die letzte Zeile; die Historie fällt geschenkt
an, weil nichts überschrieben wird.

**Bewusst NICHT im `process_events`-Log.** Eine Ablage muss auch **ohne Auftrag** möglich
sein — freier Bestand ist der Normalzustand eines Lagers, und genau dort war die Antwort
bisher leer (`SYSTEM_INTENT` §5a). Der Ereignis-Log hängt an `order_id`/`step_id`; ein Ort
ohne Auftrag hätte dort keine Zeile. Diese Unabhängigkeit **ist** die Robustheit: der Ort
funktioniert, wenn der Prozess stillsteht.

Damit ist auch `SYSTEM_INTENT` §5b beantwortet: die Geschichte bleibt lückenlos in dem,
was *geschah* — ein Stück, das drei Jahre im Regal liegt, hat weiterhin keinen Eintrag,
und das ist richtig. Neu ist, dass die **letzte** Beobachtung eine Antwort gibt.

### 3.2 Ein Halter ist eine Objektnummer — mehr nicht

Kein `location_type` neben der `id`. Objektnummern sind global eindeutig (9-stellig, EIN
Nummernkreis), der Typ ist daraus ableitbar. Das spart die Validierung, die Labels und
**jede** «unbekannter Typ»-Fallunterscheidung, die das alte Modell durchzog — dort musste
`location_label` einen Alt-Wert `'lagerplatz'` tolerant zu `None` auflösen, weil ein
gelöschter Typ sonst jede Ansicht zerlegt hätte.

Es gibt **keinen neuen Datensatztyp**:

| Ding | ist im System |
|---|---|
| Regal · Behälter · Palette · unser LKW | eine ganz normale **Instanz** |
| Werk Nord · Hauptsitz | ein **Unternehmen** (`company_settings`, gibt es) |
| Mitarbeiter · Kunde · DHL · Spediteur | ein **Benutzer** (gibt es) |

DHL wird angelegt wie jeder andere Lieferant. Ein Halter ist damit nichts, was jemand
*pflegen* muss — er ist ein Datensatz, den es aus einem anderen Grund ohnehin gibt.

### 3.3 Der Ort ändert nie einen Status und nie eine Zugehörigkeit

Das ist die Robustheitsgarantie, und sie ist **konstruktiv statt geprüft**: weil eine
Ablage nichts anfasst ausser dem Ort, muss keine andere Regel im System von ihr wissen.
Ein Stück darf gesperrt, verbaut, verschrottet oder in einer Abweichung sein — sein Ort
ist trotzdem einfach der letzte Scan.

Umgekehrt gilt dasselbe: **ein Ort blockiert nie.** Liegt etwas falsch, ist das kein
Zustand, sondern eine Auskunft — das Modul ist schlicht nicht fertig. Genau die Form, die
`StepNeed` heute schon hat (ein Feld, drei Lesarten: gedeckt · fehlt · liegt woanders).

### 3.4 Intern oder extern entscheidet die Adresse — EINE Funktion, zwei Nutzer

```
gleiche Adresse  →  intern   →  keine Vergabe-Zeile, gar nichts
andere  Adresse  →  extern   →  Vergabe (Paket ↔ Fracht aus Gewicht/Volumen VORGESCHLAGEN)
```

Verglichen wird die **Adresse**, nicht der Halter — sonst verlangte jeder Regalwechsel
einen Transport. Dieselbe Funktion beantwortet am Ressourcenmodul «liegt die Komponente
hier?». Zwei Nutzer, eine Regel; ihr Zuhause ist `services/address.py`, das die kanonische
Adressform für Person, Unternehmen und Carrier-Adapter bereits führt.

### 3.5 Das Modul «Bewegen» — zwei Körnungen, streng getrennt

| | |
|---|---|
| **Vorgang** | ein Scan = **eine Instanz**. Wie überall im Framework (§4.4). |
| **Fuhre** | (Ausgangsort → Ziel). Zwei Ausgangsorte sind **zwei** Fuhren, weil es physisch zwei Transporte sind. Drei Stücke am selben Ort sind eine Fuhre, ein Paket, ein Preis. |

Genau EINE Einstellung am Modul: das **Ziel** (ein Halter). Kein Transportmodus, keine
Quelle, keine Menge, kein Zeitpunkt — alles davon ist entweder abgeleitet (Modus) oder
gehört zur Laufzeit (Quelle, Menge, Zeitpunkt).

Das Modul **wartet auf niemanden**: jedes Stück läuft in seiner Welle weiter.

### 3.6 Das Bauteil «Vergabe» — der Zyklus, EINMAL

```
Angefragt → Angebote (n) → Vergeben → Erbracht    (+ Abgelehnt · Gescheitert)
```

mit: Dritter (immer ein Lieferant) · Kanal · Preis · Termin · Bindungsschwelle.

**`Gescheitert` ist der Ausgang aus «vergeben, aber nie erbracht»** (Nutzer-Entscheid,
August 2026): terminal, mit Pflicht-Grund; die Fuhre bekommt danach eine **ganz normale
zweite** Vergabe. Kein Zurücknehmen — die Matrix geht nie rückwärts, und eine Korrektur
ist im ganzen Haus ein **neuer Eintrag**, nie eine geänderte Zeile. Damit steht auch nie
mehr als eine Vergabe je Fuhre auf `vergeben`.

**Der Kanal ist die einzige Variable:**

| Kanal | Angebote kommen … |
|---|---|
| `plattform` | aus einer API, in Sekunden — günstigstes vorgewählt |
| `portal` | von einem Menschen, der sie im Lieferantenportal eintippt |
| `selbst` | gar nicht — selbst bestellt, nur dokumentiert |

**Rate-Shopping IST eine Ausschreibung**, sie dauert nur 2 Sekunden statt 2 Tage. Das ist
die eigentliche Einsicht dieses ADR: was beim Paketversand wie ein technischer Sonderweg
aussieht, ist derselbe Vorgang wie eine Frachtanfrage an zwei Spediteure — nur schneller.
Ein zweiter Mechanismus dafür wäre eine zweite Wahrheit über denselben Zyklus.

Ab **Vergeben** ist ein Zweiter gebunden → das System rührt nichts an, es **meldet**. Die
Regel gibt es schon (`EventType.binding` + die Klärungs-Zeile, ADR-Vorbild aus den
Testnotizen #587/#588); sie wird gelesen, nicht neu erfunden.

⇒ **Dieses Bauteil wird das künftige Beschaffungs-Modul mitbenutzen.** Es ist so gebaut,
dass dort keine zweite Implementierung nötig ist.

### 3.7 Vergabe-Datenhaltung: EINE Tabelle

*(Entscheidung des Nutzers, August 2026.)*

Eine Tabelle `awards` für Transport **und** künftige Beschaffung. Der Anlass steht als
blosse **Objektnummer** (`subject_object_id`) — keine Fachspalten, keine
Fallunterscheidung, keine nullable Sonderspalten, weil die Fachdaten dort bleiben, wo sie
hingehören (die Fuhre bzw. die Bedarfszeile). Der Typ ist ableitbar: **dieselbe Regel wie
beim Halter** (§3.2).

Verworfen wurden: *je Modul eine Tabelle* (der Zyklus wäre zweimal verdrahtet — zwei
Migrationen, zwei Router; genau die zweite Implementierung, die §3.6 vermeiden will) und
*Kopf + Rumpf* (mehr Teile, als der Fall braucht, und der Anlass stünde doppelt da).

### 3.8 Der Transport-Auftrag ist KEIN Abzweig

Ein Abzweig bedeutet im Prozessbild: Material hat **diese Achse verlassen** und kommt
zurück — und das Bild rechnet damit (jeder `fork` zieht ab, jeder `join` addiert,
`flow._branches`, PROCESS_CORE §8.1a). Ein Transport bewegt Stücke, die **nie auf der
Achse waren**; als Abzweig gezeichnet würde die Bilanz **falsch rechnen**.

Darstellung darum: **keine Kante.** Zwei klickbare Verweise — die Modul-Zeile nennt den
Auftrag, der Auftrag nennt seinen Anlass. Mehr Beziehung gibt es nicht, weil mehr nicht
wahr ist.

---

## 4 · Die vier Antworten auf die offenen Fragen

*(Nutzer-Entscheid, August 2026 — festgehalten, weil jede von ihnen eine Regel ist.)*

| Frage | Antwort | Begründung |
|---|---|---|
| **Kontext-Scan** | Der erste Scan eines Arbeitsgangs ist **immer** «wo bin ich» — ohne Vorgabewert. | Ein Scan mehr je Arbeitsgang. Dafür nennt jede Beobachtung eine wirklich gescannte Quelle, und nichts kann stillschweigend falsch landen. Ein gemerkter Ort wäre genau die Fehlerklasse, die niemand bemerkt. |
| **Person als Halter** | Nimmt jemand ein Teil mit, liegt es **bei ihm** (Benutzer-Objektnummer). | Der Benutzer ist ein Halter wie jeder andere — kein neuer Mechanismus. Der alte Ort wäre eine Behauptung über etwas, das dort nachweislich nicht liegt (G3). |
| **Vergabe-Tabelle** | **Eine**, Anlass als Objektnummer. | §3.7. |
| **Carrier-Adapter** | Die alten `services/shipping/*` werden **gelöscht** und komplett neu geschrieben. Shippo und Sendcloud bleiben als **Kanäle wieder implementierbar** — Zugangsdaten und Konfiguration sauber hinterlegt. | Der Altcode trägt das Vokabular des Altsystems (`shipments`, `transport_mode`); ihn anzupassen hiesse, es mitzunehmen. Die Anbieter-Wahl selbst bleibt richtig und wird nicht verworfen. |

---

## 5 · Was nicht wiederkommen darf

Als Liste, damit ein Wächter sie prüfen kann:

1. `movable_instances` mit Fallunterscheidungen (Retoure/Kunde/normal) — **null Fälle**.
2. Eine Mengen-Map je Standort (`location_split.py`).
3. Vom System angelegte Bewegungen oder Unter-Aufträge.
4. Eine gespeicherte `direction` (outbound/inbound) oder `transport_class`.
5. Ein `location_type` neben der Halter-Objektnummer.
6. Ein Modul, das den Ort liest, um zu entscheiden, **welche** Stücke es anfasst.

Jeder Punkt hat seinen Wächter (`SYSTEM_LOGIC` §7.4); vier davon sind AST-Prüfungen, weil
sie Aussagen über den **Quelltext** sind und nicht über ein Verhalten.

---

## 6 · Reihenfolge der Umsetzung

Jede Stufe für sich lauffähig und deploybar.

| # | Stufe | Inhalt |
|---|---|---|
| 1 | **Regeln** | dieses ADR · `PROCESS_CORE` §9.8 + §15 · `SYSTEM_LOGIC` §7 |
| 2 | **Fundament** | Halter · `unit_places` · Kette («wo ist X?») · «was liegt hier?» · Ablage-Endpunkt · Kontext-Scan |
| 3 | **Bewegen, intern** | komplett fertig inkl. Scan-Fluss und Wächtern |
| 4 | **Vergabe** | das Bauteil + Kanäle `selbst`/`portal` → die externe Fuhre |
| 5 | **Kanal Plattform** | Adapter neu geschrieben, Rate-Shopping, Label, Tracking |
| 6 | **Ressourcenmodul** | Adressprüfung + die zwei Angebote + der Verweis |

### 6.1 · Stand

| # | Stufe | Stand |
|---|---|---|
| 1 | Regeln | **fertig** – dieses ADR, `PROCESS_CORE` §9.8/§15, `SYSTEM_LOGIC` §7 |
| 2 | Fundament | **fertig** – Migration `111`, `services/places.py`, `routers/places.py` |
| 3 | Bewegen, intern | **fertig** – `domain/modules.Bewegen`, `services/moving.py`, Scan-Fluss |
| 4 | Vergabe | **fertig** – Migration `112`, `domain/vergabe.py`, `services/awards.py`, `AwardPanel` |
| 5 | Kanal Plattform | **fertig** – Migration `113`, `services/carriers/`, `services/parcel.py`, Tarifabruf am Modul |
| 6 | Ressourcenmodul | **fertig** – `SYSTEM_LOGIC` §7.3b (R1–R6), `_needs`/`_transports`, `NeedSource.here`, `StepNeed.transports` |

**Ein Fund aus Stufe 4, der die Regel geändert hat.** Der Kanal `selbst` war eine
**Sackgasse**: er kommt nie zu einem Angebot, und `vergeben` ging nur aus `angeboten` –
er blieb für immer `angefragt`. Behoben nicht mit einem zweiten Ablauf je Kanal, sondern
mit **einer Kante mehr in derselben Matrix** (`angefragt → vergeben`, §7.3-V3). Sie bleibt
monoton, und sie öffnet nichts, was sie nicht öffnen soll: dass ein Kanal **mit** Angeboten
sie nicht benutzen kann, folgt aus dem Dienst (dort ist das gewählte Angebot Pflicht, und
sobald eines eingetroffen ist, steht die Vergabe ohnehin auf `angeboten`). Zwei Aussagen,
jede an ihrem Ort: die **Matrix** sagt, welche Zustandsfolgen es gibt, der **Kanal** sagt,
woher die Angebote kommen.

Gefunden hat ihn der Wächter, nicht der Bildschirm – er steht als eigene Zeile in der
Sackgassen-Analyse (`SYSTEM_LOGIC` §7.5, V0).

**Was Stufe 4 bewusst NICHT gebaut hat**

* **Wer vergeben darf.** Jeder Endpunkt hängt an `require_employee`; ab `vergeben` entsteht
  eine Verpflichtung gegenüber einem Dritten, und das ist die erste Stelle im System, an
  der eine Rolle je Vorgang zählen könnte. Auf Verdacht gebaut wäre sie die Regel, die
  niemand bestellt hat (`SYSTEM_LOGIC` §7.6-2).
* **Eine Ankunft, die das Modul selbst meldet.** Der Ort ist eine **Beobachtung**: im
  Normalfall scannt der Mensch am Ziel die Stücke ein, und das ist die ganz gewöhnliche
  Ablage aus Stufe 2. `awards.deliver` schreibt den Ort für den Fall, in dem niemand
  scannt – das ist der **Tracking**-Weg und gehört zu Stufe 5.
* **Eine Rücksendung / Reklamation an den Dritten.** Der Zyklus kennt sie nicht; sie wäre
  die Gegenrichtung und braucht ihre eigene Regel, bevor sie Code wird.


### 6.2 · Stufe 5: was neu geschrieben und was gelöscht wurde

`services/shipping/` (Gateway + `manual` + Shippo + Sendcloud, 410 Zeilen) ist
**ersatzlos gelöscht**. An seine Stelle tritt `services/carriers/` – **neu geschrieben**,
mit denselben zwei Anbietern und ihren Schlüsseln, aber ohne die zwei verbotenen Formen,
die der Vorgänger trug:

* **Kein Rückfall.** Der alte Gateway wählte einen Anbieter (Sendcloud ≻ Shippo ≻ manual)
  und fiel stillschweigend auf «manual» zurück, wenn nichts konfiguriert war – «nie
  kaputt», und genau darum merkte niemand, dass nie ein Tarif kam. Jetzt werden **alle
  eingerichteten** gefragt (eine Ausschreibung fragt mehrere), und ohne Schlüssel gibt es
  den Kanal **nicht**.
* **Keine gespeicherte Transportklasse** (V-4). Ob eine Fuhre innerbetrieblich ist oder
  ein Versand, wird aus der **Adresse** gerechnet – wie in Stufe 3.

Die Schlüssel stehen unverändert in `core/config.py`
(`sendcloud_public_key`/`sendcloud_secret_key`/`sendcloud_api_url`/`sendcloud_currency`,
`shippo_api_key`/`shippo_api_url`) plus `carrier_timeout_s`. Ein **neuer** Anbieter ist
eine Datei in `services/carriers/` und eine Zeile in `_CARRIERS` – es gibt keine
Fallunterscheidung nach dem Anbieter in der Fachlogik; der Adapter **ist** sie.

**Was Stufe 5 bewusst NICHT gebaut hat**

* **Webhooks.** Tracking wird auf Klick abgefragt. Ein Webhook wäre ein zweiter
  Eingangsweg für dieselbe Beobachtung und bräuchte eine eigene Regel dafür, wem er
  gehört und wie er sich gegen einen Klick verhält.
* **Mehrere Pakete je Fuhre.** Was zusammen an einem Ort steht, ist **ein** Paket;
  wie es zerlegt wird, ist eine Frage der Verpackung und keine des Systems. Ein
  Packalgorithmus wäre eine Behauptung über eine Kiste, die niemand gesehen hat.
* **Abholtermine, Zolldokumente, Versandkosten-Weiterverrechnung.** Alle drei sind
  eigene Vorgänge mit eigenen Regeln.


### 6.3 · Stufe 6: der Ort steht NEBEN der Verfügbarkeit

Das Ressourcenmodul fragte bisher genau eine Frage: *ist genug da?* Mit dem Ort kommt eine
zweite dazu — *liegt es hier?* —, und der ganze schwierige Teil ist, dass sie die erste
**nicht überschreiben darf**. Die Regeln stehen als prüfbare Sätze in `SYSTEM_LOGIC` §7.3b
(R1–R6), und sie standen dort, **bevor** eine Zeile Code entstand.

**Der Ort zieht nichts ab** (R1). «200 verfügbar — in Werk 2» ist eine Auskunft. Genau das
ist die Stelle, an der der Vorgänger gescheitert ist: er hat aus einem Ort einen Zustand
gemacht, und ein Zustand blockiert. Hier senkt er keine Zahl, er sagt nur, dass ein
Transport daraus folgen **könnte** — die Entscheidung trifft ein Mensch.

**Verglichen wird die Anschrift, nicht der Halter** (R2), über **dieselbe** Funktion, die
auch die Fuhre klassifiziert (`places.same_place`). Der unterscheidende Fall ist die Kiste
im Werk: anderer Halter, gleiche Anschrift. Ein Halter-Vergleich könnte das nie sehen, und
jedes Umräumen im selben Werk stünde als Transport da. Die Anschrift einer Kiste hat sie
über die **Kette** — es gibt keine zweite Auflösung dafür.

**«Nicht bekannt» ist nicht «woanders»** (R3). `here` ist darum dreiwertig (`True` · `False`
· `None`), und `None` heisst: einer der beiden Orte ist unbekannt, es wird nicht geraten.
Ein Transport ins Ungewisse wäre schlimmer als keiner. Aus demselben Grund ist auch die
Frage «gebraucht **wo**?» offen, sobald die wartenden Stücke verteilt stehen — es gibt
dann keine einzelne richtige Antwort (`places.common_place`).

**Der Transport wird ABGELEITET, nicht gespeichert** (R4/R5). Die erste Fassung trug einen
Zeiger am Auftrag («aus welchem Modul kam ich?») — und die beiden Wächter aus dem
Basis-Neuaufbau haben ihn sofort gemeldet: eine fünfte Spalte auf einer Tabelle, die
bewusst vier hat, und sie kann veralten. Die Spalte ist samt Migration **zurückgenommen**;
gefragt wird stattdessen, was ohnehin wahr sein muss: *läuft ein Auftrag, der Material
dieses Artikels an genau meinen Ort bringt?* Das ist zugleich ehrlicher — ein von Hand
angelegter Transport erscheint genauso. **Gefragt wird nach dem ARTIKEL**, nicht nach der
freien Quell-Instanz: sobald der Transport das Material greift, ist es nicht mehr frei,
und der Verweis verschwände genau in dem Moment, in dem er gebraucht wird.

Er ist ein **leichter Verweis** (`TransportRef`), kein `RelatedOrder` und keine Kante: ein
Transport bewegt Stücke, die nie auf dieser Achse waren — jeder `fork` zieht ab und jeder
`join` addiert, also rechnete die Bilanz falsch (§15.8).

**Angeboten wird nur, was Sinn ergibt** (R6), und die Fallunterscheidung steht in der
**Oberfläche** — sie zeigt Knöpfe. Rechnen tut sie nicht: was hier liegt und was nicht,
sagt der Server je Quelle. Eine zweite Zahl «hier verfügbar» ist ausdrücklich verboten;
sie stünde neben der echten und beantwortete dieselbe Frage anders.

**Was Stufe 6 bewusst NICHT gebaut hat**

* **Einen Transport, den das System anlegt.** Der Knopf füllt einen ganz gewöhnlichen
  Auftragsentwurf vor (`OrderSeed.moveTo`) — angelegt wird er durch den Klick des Menschen.
  Genau daran sind die Begleit-Bewegungen und die abgeleitete Bereitstellung gescheitert.
* **Automatisches Ausweichen auf eine andere Instanz.** Die Auswahl ist dieselbe, die der
  Scan ohnehin trifft; sie zu erraten hiesse, eine Entscheidung zu treffen, deren Folgen
  physisch sind.
* **Eine Reservierung des unterwegs befindlichen Materials.** Der Verweis sagt, dass etwas
  kommt — er verspricht nicht, dass es für dieses Modul bestimmt ist. Ein Anspruch auf
  fremdes Material wäre eine Zusage, die niemand gegeben hat.
