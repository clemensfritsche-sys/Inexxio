# FINDINGS — Befunde des Audits

> Sortiert nach Schwere. Zu jedem Befund die **Ursache**, nicht nur das Symptom — und wo
> mehrere zur selben Wurzel gehören, steht das dabei.
>
> **Runde 1 (Audit) hat nichts implementiert.** Die einzigen Änderungen waren der
> Testapparat selbst und **eine** Korrektur an der bestehenden Wächter-Suite (🟠-2), die
> den Datenbestand beschädigt hat, über den geprüft werden soll.
>
> **Runde 2 (Folgerunde, auf Freigabe)** hat 🟠-1 behoben und 🟠-3 **entschieden**. Was
> dabei entstanden ist, steht je Befund unter «Erledigt» — und die Fundliste zu `is_active`
> ab «Fundliste» weiter unten.

---

## Zusammenfassung

| Schwere | Anzahl | |
|---|---|---|
| 🔴 verletzt eine Grundregel / führt zu falschen Daten | **0** | — |
| 🟠 Sackgasse · Inkonsistenz · unklares Verhalten | **3** | 🟠-1 ✅ · 🟠-2 ✅ · 🟠-3 ✅ |
| 🟡 Verbesserungspotenzial | **5** | 🟡-1 … 🟡-5 |

> **Stand nach der Folgerunde:** alle drei 🟠 sind **erledigt** — zwei behoben, einer
> entschieden. Die Einzelheiten stehen unten je Befund unter «Erledigt».

**Es gibt keinen 🔴-Befund.** Alle sechs Grundregeln aus `SYSTEM_LOGIC.md` §3 halten über
71 Szenarien und 15 Invarianten (238 Aufträge · 1884 Einzelinstanzen · 7881 Log-Einträge).
Insbesondere: Exklusivität hält auch unter echter Nebenläufigkeit, terminale Status sind
auf allen drei Ebenen dicht, und die Mengenbilanz stimmt nach Aussonderung wie nach
Rückführung.

---

## 🟠-1 · Ein **inaktiver Artikel** kann weiterhin Aufträge und neue Instanzen erzeugen

**Fall:** S98 — Soll `400`, Ist: kein Fehler.

**Was passiert.** `PATCH /erp/articles/{id}` nimmt `status: "inaktiv"` an (der Validator
lässt jeden Wert aus `ARTICLE_STATUSES` zu). Danach lässt sich mit demselben Artikel ein
Erzeugungsauftrag anlegen — es entstehen neue Einzelinstanzen eines Artikels, der ausser
Betrieb ist.

**Ursache.** `process.resolve_lines` prüft `article.is_active` — den **Soft-Delete-Flag**
— aber nicht den **fachlichen** Status. Das sind zwei verschiedene Achsen, und das steht
sogar so im Modell (`models/article.py`: «`is_active` bleibt der Soft-Delete-Flag,
unabhängig vom fachlichen `status`»). Geprüft wird die eine, gemeint ist die andere.

**Warum es kein 🔴 ist.** Es entstehen keine falschen Daten — die erzeugten Instanzen sind
in sich korrekt. Es ist eine **Regel ohne Wirkung**: «Inaktiv = ausser Betrieb, endgültig»
(`SYSTEM_LOGIC` §1.1) wird nirgends durchgesetzt.

### ✅ Erledigt

Die Regel steht jetzt an **einer** Stelle und heisst nach der Frage, nicht nach einem
Zustand: `articles.may_create(article)` — *«darf dieser Artikel NEUE Einzelinstanzen
erzeugen?»*, mit dem Grund als Rückgabe (dieselben zwei Formen wie
`process.pick_problem`).

| | |
|---|---|
| **Gesperrt** | ausschliesslich Herkunft **Neu** |
| **Erlaubt** | **Lager** — sonst wäre jedes Stück eines ausgelaufenen Artikels eine Leiche, die sich nicht einmal mehr aussondern liesse (S98b beweist es) |
| **Wann** | bei der **Freigabe**, nicht laufend. Ein laufender Auftrag läuft zu Ende, auch wenn der Artikel zwischenzeitlich inaktiv gesetzt wird — sein Prozess ist eine eingefrorene Kopie |
| **Wo sonst** | die Auswahl-Liste sperrt «Neu» und nennt **denselben Satz** (`ArticleOption.create_problem`); der Artikel bleibt in der Liste, damit sein Restbestand erreichbar ist |

Wächter: **S98** (Neu → 400 mit sprechender Meldung) · **S98b** (Lager bleibt möglich).

---

## 🟠-2 · Der bestehende Wächter beschädigte den Bestand, den er bewacht

**Fall:** Invariante `I12` — 20 verwaiste Einzelinstanzen im Testbestand.

**Was passiert(e).** `tests/test_terminal_status._cleanup` räumte über **ein Stück** auf
(`DELETE FROM instance_units WHERE id = …`) und löschte die **Instanz** dazu. Der Test
`…out_of_reach…` hängt aber ein zweites Stück (gesperrt, Suffix 2) an dieselbe Instanz —
das blieb übrig: Instanz weg, Stück da. Jeder Lauf der Suite legte eines nach.

**Ursache.** Aufräumen über die falsche Ebene. Die Instanz ist der Ordner; wer sie löscht,
muss ihren Inhalt mitnehmen.

**Behoben** (die eine Ausnahme von «nichts implementieren»): `_cleanup` räumt jetzt über
`instance_id` auf. Nachgemessen: 0 Waisen nach einem vollen Lauf. Die Altlast im
Testbestand ist entfernt.

**Warum das hier steht und nicht unter «Kleinkram».** Es ist ein Wächter, der stillschweigend
Datenmüll produziert. Ohne die neue Invariante wäre er nie aufgefallen — und genau das ist
der Grund, warum die Invarianten das eigentliche Ergebnis dieser Kampagne sind.

---

## 🟠-3 · Es gibt keinen Weg, einen Auftrag abzubrechen

**Kein Testfall — ein Loch in der Landkarte** (`SYSTEM_LOGIC` §4.3, Risiko R2).

**Was fehlt.** Ein Auftrag hat genau zwei Ausgänge: alle Module bestätigen
(`Abgeschlossen`) oder alle Stücke verlieren (`Abgebrochen`). Einen dritten — «ich will
das nicht mehr» — gibt es nicht.

**Wann das weh tut.** Ein Auftrag, dessen Modul auf eine Rückführung wartet, kommt nur
weiter, wenn die Abweichung fertig wird. Wird sie es nie (falsch angelegt, Stück physisch
verschwunden), stehen **beide** für immer. Es gibt keinen Ausstieg.

**Die gute Nachricht aus dem Test:** die Wartekette selbst ist sauber. Sie löst sich über
drei Ebenen auf, sobald ganz unten ausgesondert wird (S47), und eine gekappte Verbindung
blockiert gar nicht erst (S44). Der einzige echte Klemmfall ist der Abweichungsauftrag,
den niemand mehr anfasst.

### ✅ Erledigt — durch eine Entscheidung, nicht durch eine Funktion

**Es gibt weiterhin keine Abbruch-Funktion, und das ist jetzt die Antwort.** Ein Auftrag
wird abgebrochen, indem ihm über einen **Abweichungsauftrag alle Stücke entzogen und die
Rückführung gekappt** wird.

Das ist der bessere Weg, weil er dazu **zwingt zu regeln, was mit den Stücken geschehen
soll** — verschrotten, sperren, weitergeben. Ein Knopf «abbrechen» liesse genau diese
Frage offen.

Der Auftragsstatus folgt dabei **ohne eine Zeile Code**: sind alle Stücke entzogen und
kommt keines zurück, ist `unterwegs = 0`, `verliehen = 0`, `angekommen = 0` — und das
ist genau `Abgebrochen`. Gemessen:

| Fall | Ergebnis |
|---|---|
| **S57** | alle Stücke entzogen + gekappt → Eltern `Abgebrochen`, wartet nicht, kein Modul gesperrt, Stücke verschrottet, Bild widerspruchsfrei |
| **S58** | derselbe Weg beim **obersten** Auftrag (Erzeugungsauftrag ohne Vorgänger) |
| **S59** | ein **liegengelassener** Abzweig klemmt seinen Eltern nicht — man entzieht ihm seinerseits die Stücke, beide Ebenen lösen sich auf |

**Im Code gab es nichts zu löschen:** in allen aktiven Modulen (`core` · `catalog` ·
`capture`) existiert kein Endpunkt, keine Aktion, kein Statuswechsel und kein
Oberflächen-Element für einen Abbruch. Die Treffer auf «abort/abbrechen» liegen
ausschliesslich in den **abgeschalteten** Modulen (`sale`, `document`, `payments`,
`shop`), die mit dem Basis-Neuaufbau ohnehin nicht importierbar sind.

**Ein neues, latentes Risiko ist dabei entstanden und steht in der Landkarte** (R7): weil
der Abbruch über die Abweichung läuft, schliesst ein künftiger Modultyp mit
`units_may_leave = False` **auch den Abbruch**. Heute gibt es keinen solchen Typ; wer den
ersten baut, muss den Ausgang mitbeantworten.

---

## 🟡-1 · «Noch nicht erfasst: OK.» nennt den Punkt, aber nicht das Stück

**Fall:** S94 — Fehler kommt (400), Meldung nennt aber keine Nummer.

`capture_types.check_values` bekommt einen Wertesatz und weiss nicht, zu welcher
Einzelinstanz er gehört; `capture.record_for_step` ruft sie in einer Schleife
(`for values in captures.values()`) und reicht die Nummer nicht mit. Bei einer Charge über
1500 gezogene Stücke heisst die Meldung «Noch nicht erfasst: OK.» — und der Mensch sucht.

Der Nachbar-Fall macht es vor: `_captures_for` sagt «1 von 2 Einzelinstanzen sind noch
nicht erfasst: 100000123-2». Die Information ist da, sie geht nur eine Ebene tiefer
verloren.

---

## 🟡-2 · Zwei Fallback-Anzeigen im Auftrags-Detail

`components/erp/order-detail.tsx`:

- `ln.article_name ?? 'Artikel'` — ein **erfundenes Wort** als Anzeige. In der Praxis
  unerreichbar (`resolve_lines` verlangt einen existierenden Artikel), aber es ist genau
  das Muster, das `SYSTEM_LOGIC` §3 G3.6 ausschliesst.
- `stepInfo(order, step.id)?.action ?? ''` — ein **leerer Knopf** statt einer Meldung.
  Fehlt die Schritt-Auskunft, steht dort eine Schaltfläche ohne Beschriftung.

Beides ist klein. Beides ist eine Anzeige, die im Fehlerfall lügt statt zu melden.

---

## 🟡-3 · Zwei Vokabulare für den Artikel-Status ~~im Docstring~~

`models/article.py` beschreibt die Werte als `released` / `inactive`. Gültig sind
`freigegeben` / `inaktiv` (`domain/statuses`), und `main._ARTICLE_STATUS_FIXES` zieht
Altbestand darauf nach. ~~Der Code ist korrekt, der Docstring ist es nicht~~ — und er ist
die erste Stelle, an der jemand nachschaut.

### ⚠ Diese Einschätzung war zu milde — korrigiert in Runde 2

**«Der Code ist korrekt» stimmte nicht.** Es war nicht nur der Docstring: der
**ORM-Default derselben Spalte** stand ebenfalls auf `"released"`, und der gewinnt gegen
den Server-Default. Ich habe damals den Text gelesen und den Code daneben nicht — genau
der Fehler, vor dem der Befund selbst warnt.

Aufgefallen ist es erst, als mit `articles.may_create` ein Leser dazukam. Die
ausführliche Analyse steht als **Fund 4** in der Fundliste unten; behoben ist beides
(Docstring **und** Default), Wächter `test_the_article_status_has_exactly_one_vocabulary`.

**✅ Erledigt.**

---

## 🟡-4 · `modules.sample_of` fällt auf «alle» zurück

Fehlt die Stichprobenregel in einer gespeicherten Definition, gilt «alle». Das ist ein
**dokumentierter** Rückfall für Alt-Definitionen und in `SYSTEM_LOGIC` §5.3 ausdrücklich
als Ausnahme benannt. Er ist heute unerreichbar (jede neue Definition läuft durch
`Datenerfassung.clean_config`, das die Regel immer setzt).

Der Hinweis steht hier, weil ein Rückfall, dessen Anlass verschwunden ist, mit der Zeit
zu einem Standardwert wird, den niemand mehr hinterfragt.

---

## 🟡-5 · Der Verlierer einer echten Nebenläufigkeit bekommt eine rohe Datenbankmeldung

**Fall:** S63 — Exklusivität hält (genau eine Freigabe gewinnt, genau eine offene
Zugehörigkeit bleibt). Der Verlierer sieht aber, je nach Timing, einen `IntegrityError`
statt des sprechenden Satzes aus `_assert_as_picked`.

Das ist der in `PROCESS_CORE` §6.3 ausdrücklich benannte Restfall («der partielle
Unique-Index bleibt das Netz für den echten Parallelfall»). Er ist selten, er verliert
keine Daten, und er kostet die einzige Objektnummer, die überhaupt je verloren geht.
Trotzdem: `G2.2` verlangt einen **sprechenden** Fehler, und dieser hier spricht Postgres.

---

# Fundliste `is_active` — die zwei Achsen, die beide «aktiv» heissen

> Der Auftrag war: **alle** Verwendungen durchgehen und melden, wo sonst noch die falsche
> der beiden gemeint ist. Systematisch ausgezählt, nicht stichprobenartig.

## Die Zahlen

| | |
|---|---|
| Verwendungen gesamt | **194** |
| davon in **abgeschalteten** Modulen (`sale` · `document` · `ai` · `payments` · `shop` …) | 112 — ausserhalb des Umfangs, sie sind nicht importierbar |
| davon in **aktiven** Modulen (`core` · `catalog` · `capture`) | **92** in 38 Dateien |
| Stellen, die `is_active = False` **setzen** | **8**, systemweit |

## Der Kern: wo kann die Verwechslung überhaupt entstehen?

Nur dort, wo ein Modell **beide** Achsen trägt. Ausgezählt über alle Modelle: fünf
Klassen — und davon liegen drei in abgeschalteten bzw. peripheren Bereichen
(`AiAction`, `DocumentSignoff`, `FeedbackNote`; bei der Notiz sind beide Achsen
ausdrücklich gemeint und werden getrennt gelesen).

**Im Prozessbereich bleiben genau zwei:**

| Modell | `is_active` | fachlicher Zustand | Befund |
|---|---|---|---|
| **`Article`** | Soft-Delete | `status` = Freigegeben ↔ Inaktiv | **war der Fehler** (🟠-1). `resolve_lines` las `is_active`, gemeint war `status`. |
| **`InstanceUnit`** | Soft-Delete | `status` = Freigegeben · Im Prozess · Gesperrt · Verschrottet | **kein Fehler, aber tote Filter** — siehe unten |

## Fund 1 · `Article` — behoben

`is_active` wird von der Anwendung **nie** gesetzt; erreichbar war es nur über
`PATCH /erp/articles/{id}` (Feld in `ArticleUpdate`). Es gab damit **zwei** Wege, einen
Artikel ausser Betrieb zu nehmen, und die Prozesslogik las den, den niemand benutzt.

**Behoben auf beiden Seiten:** die Regel fragt jetzt `articles.may_create` (den fachlichen
Zustand), und `is_active` ist **aus `ArticleUpdate` entfernt** — ein Artikel hat wieder
genau **eine** Achse, über die er ausser Betrieb geht.

## Fund 2 · `InstanceUnit` — fünf tote Filter und eine falsche Begründung

Eine Einzelinstanz wird **nie** deaktiviert (`models/instance_unit`: «Vergeben bleibt
vergeben»). Nachgezählt: keine einzige Stelle im System setzt `InstanceUnit.is_active =
False`. Damit sind alle Filter darauf immer wahr:

| Stelle | was sie tut |
|---|---|
| `process.waiting_counts` | filtert offene Ausleihen |
| `process.order_statuses` | filtert «unterwegs» |
| `process._resolve_units` | weist ein «deaktiviertes» Stück ab |
| `sampling._population` | filtert die Ziehungsmenge |
| `routers/orders.unit_options` | filtert die Auswahl-Liste |
| dazu `instances.*` (4×) und `Instance.is_active` (3×) | dasselbe eine Ebene höher |

Sie sind **harmlos** — aber eine davon trug eine **falsche Begründung**: der Docstring von
`order_statuses` behauptete, ohne die Bedingung «hätte `Abgebrochen` keinen Erzeuger und
wäre ein Wert, den nie jemand sieht». Das stimmt nicht: `Abgebrochen` entsteht, wenn eine
Abweichung alle Stücke nimmt und die Rückführung gekappt ist (S49b · S57 · S58 · S59).
Eine Erklärung, die einen Mechanismus erfindet, ist schlimmer als keine — **korrigiert**.

**Die Filter selbst bleiben stehen.** Sie kosten nichts, sie machen die Aussage «das Stück
gibt es noch» vollständig, und sie zu entfernen wäre ein Eingriff in fünf geprüfte
Abfragen ohne fachlichen Gewinn. Festgehalten ist stattdessen die **Tatsache**, dass
nichts sie auslöst (Wächter `test_a_record_goes_out_of_service_on_exactly_one_axis`).

## Fund 3 · Zwei Stellen, die «alle Artikel» meinen und den Soft-Delete lesen

`routers/orders.article_options` und `routers/articles` filtern `Article.is_active`. Das
ist **richtig so** — gemeint ist der Soft-Delete («Datensatz ausgeblendet»), nicht der
fachliche Zustand. Wichtig ist, was sie **nicht** tun: sie blenden einen `inaktiven`
Artikel **nicht** aus. Genau das muss so sein, sonst wäre sein Restbestand über «Lager»
unerreichbar.

## Fund 4 · Der Artikel-Status gab es in **zwei Sprachen** — gefunden durch den Fix selbst

> **Das ist der schwerste Fund dieser Runde**, und er wäre eine Regression gewesen, hätte
> ihn die Testmatrix nicht sofort gemeldet.

Derselbe Fehlertyp wie 🟠-1 («zwei Ausdrücke für dieselbe Sache»), nur eine Ebene tiefer:
`articles.status` existierte als **deutsches** Wort (`freigegeben`/`inaktiv`, aus
`domain/statuses`) **und** als englisches (`released`/`inactive`).

Migration `107` hat beides bereinigt — die **Daten** und den **Server**-Default. Nicht
mitgezogen wurde der **ORM**-Default im Modell:

```python
status: Mapped[str] = mapped_column(String(20), default="released", nullable=False)
```

**Und der ORM-Default gewinnt.** Jede Artikel-Zeile, die über SQLAlchemy ohne
ausdrücklichen Status entsteht, trug damit wieder `"released"` — ein Wort, das die
Statusliste nicht kennt.

**Warum es zwei Deploys lang niemandem auffiel: es gab keinen Leser.**
`services/articles.create_article` setzt den Status ausdrücklich (`st.FREIGEGEBEN`), und
sonst fragte im aktiven Bereich niemand danach. Der Widerspruch war folgenlos — bis
`may_create` der erste Leser wurde, der die Frage *«ist dieser Artikel freigegeben?»*
wirklich beantworten muss. Für jede so entstandene Zeile lautete die Antwort **nein**:

```
400: Zeile 1: Artikel 100000011 ist «released» – ein Artikel ausser Betrieb erzeugt
keine neuen Einzelinstanzen.
```

**Wie weit der Schaden reichte — ehrlich eingegrenzt.** Nicht bis zur Datenverfälschung:
`main._ARTICLE_STATUS_FIXES` zieht bei **jedem Start** `released`/`draft` auf
`freigegeben` nach. Ein so entstandener Artikel wäre also spätestens beim nächsten Deploy
geheilt worden. Der Schaden war ein **Zeitfenster**: zwischen der Anlage eines solchen
Artikels und dem nächsten Neustart hätte `may_create` ihn zu Unrecht gesperrt — mit einer
Meldung, die auf einen Zustand zeigt, den der Nutzer nie gesetzt hat. Dass es diesen
Reparatur-Lauf gibt, macht den Befund kleiner; dass es ihn **braucht**, ist selbst das
Symptom.

**Behoben an der Wurzel:** der Standardwert kommt aus dem Katalog (`st.FREIGEGEBEN`), und
ORM- und Server-Default stehen ausdrücklich nebeneinander in derselben Zeile — sie können
nicht mehr getrennt veralten. Die Testhelfer schrieben denselben Literal-Wert und tun es
nicht mehr; sie benutzen jetzt den Standardwert und prüfen ihn damit gleich mit.

**Nachtrag (August 2026): der offene Rest ist erledigt.** Gemeldet war, dass die alte
Sprache in den abgeschalteten Bereichen (`services/ai`, `services/selling`) noch stand und
beim Wiedereinschalten mitzuziehen wäre. Diese Dateien sind gelöscht (`docs/attic.md`) —
damit ist die Ausnahmeliste im Wächter entfallen, und er gilt **ohne Ausnahme**.

Wächter: `test_the_article_status_has_exactly_one_vocabulary` — prüft die **Quelle** des
Standardwerts (nicht seinen heutigen Wert), die Gleichheit von ORM- und Server-Default und
dass **kein** Modul die alte Sprache spricht. Gegen die Bug-Form gegengeprüft.

## Zur Frage «hilft eine Umbenennung?»

**Nein — jedenfalls nicht als globale Umbenennung, und die empfehle ich ausdrücklich
nicht.** `is_active` steht in 194 Verwendungen, in Migrationen, in API-Schemas und in
generierten Frontend-Typen. Eine Umbenennung wäre ein grosser, riskanter Eingriff, der
den Grossteil legitimer Soft-Delete-Verwendungen anfasst — und die Verwechslung entsteht
gar nicht dort, sondern nur an den **zwei** Modellen, die beide Achsen tragen.

**Was stattdessen dauerhaft schützt — und umgesetzt ist:**

1. **Die zweite Achse wegnehmen, wo sie keine Bedeutung hat.** Am Artikel ist `is_active`
   nicht mehr von aussen setzbar. Es gibt genau einen Weg ausser Betrieb.
2. **Die Frage nach der Regel benennen, nicht nach dem Zustand.** `articles.may_create`
   statt `is_article_active`. Ein Name, der «aktiv» enthält, hätte dieselbe Falle nur eine
   Ebene weiter aufgestellt.
3. **Einen Wächter, der die Tatsache festhält**
   (`test_a_record_goes_out_of_service_on_exactly_one_axis`): nichts deaktiviert einen
   Prozess-Datensatz über den Soft-Delete, `ArticleUpdate` nimmt `is_active` nicht mehr
   entgegen, und die Freigabe **fragt** die Regel, statt sie nachzubauen.

---

# Rückblick — wie ich das System heute nochmals bauen würde

> Der ehrliche Teil. Ich habe zwei Tage in diesem Modell gelesen, geprüft und Fehler
> gesucht; das ist die Grundlage für das Folgende, nicht ein Gefühl.

## Was sich bewährt hat — und zwar deutlich

**1 · Die Einzelinstanz als einziges Arbeitsobjekt.** Das ist die beste Entscheidung im
ganzen Modell. Sie hat die Fehlerklasse «Zeilen zählen statt Mengen summieren», die das
Vorgängersystem wieder und wieder produziert hat, **strukturell** beseitigt: es gibt
keine Mengen-Spalte, also kann keine driften. In 67 Szenarien inklusive einer Charge über
600 Stück gab es dazu keinen einzigen Befund.

**2 · Der Ereignis-Log als Quelle, die Projektionen als Ableitung.** Append-only, `id` als
Zeitachse, **eine** Schreibstelle. Der schwerste Fehler der letzten Wochen (ein
verschrottetes Stück stand wieder auf «Freigegeben») kam von einem Schreiber **ausserhalb**
dieser Stelle — und wurde gefunden, weil Log und Zeile sich widersprachen. Die Invariante
`I05` prüft heute genau diesen Widerspruch.

**3 · Exklusivität als partieller Unique-Index.** Nicht als Anwendungsregel. Der Beweis
kam beim Bauen der Gegenprobe: die Fehlerform «zwei offene Zugehörigkeiten» liess sich
**nicht** herstellen, solange der Index steht. Eine Regel, die man nicht brechen kann,
schlägt jede, die man prüfen muss.

**4 · «Terminal» als Eigenschaft, aus der alles folgt.** Farbe, Auswählbarkeit,
Schreibschutz, DB-Trigger und Invariante lesen dieselbe Zeile im Katalog. Ein neuer
Endzustand ist ein Eintrag — kein Rundgang durch fünf Dateien.

**5 · Der Rückführpunkt braucht kein Feld.** Beim Ausscheren wird die Zeile geschlossen
und `current_step_id` **nicht angefasst** — die Rückkehr ist das Wiederöffnen genau dieser
Zeile. Das ist der eleganteste Teil des Modells, und die dreistufige Kette (S43, S47) hat
ihn ohne eine Zeile Sonderlogik getragen.

## Was ich anders machen würde

**A · Der Auftragsstatus wird aus drei Zahlen abgeleitet — und eine davon kostet eine
rekursive Abfrage.** `waiting_counts` liest **alle** offenen Ausleihen des Systems und
verfolgt die Kette in Python nach oben. Das ist heute günstig (Abweichungen sind selten),
aber es ist die einzige Stelle im Modell, an der eine Ableitung nicht lokal ist. Mit dem
Wissen von heute würde ich die Kette als **rekursive SQL-Abfrage** (`WITH RECURSIVE`)
formulieren — dieselbe Regel, aber an einer Stelle und ohne die Python-Schleife, die man
beim vierten Verwendungsfall vergisst mitzuziehen.

**B · «Freigegeben» bedeutet auf zwei Achsen zweierlei.** Am Stück «in keinem Auftrag», am
Artikel «auftragsfähig». Der Katalog behauptet, das sei dasselbe («einsatzbereit») — das
ist eine sprachliche Brücke, keine fachliche. Sie hat mich beim Schreiben von
`SYSTEM_LOGIC` §1.1 aufgehalten, und sie wird jeden aufhalten, der neu dazukommt. Ich
würde die Artikel-Achse eigene Wörter geben (`aktiv` / `ausgelaufen`) und die
Statusliste **je Achse** führen — sie ist ohnehin schon nach Achsen gefiltert.

**C · `is_active` **und** `status` an denselben Datensätzen.** Genau daraus ist 🟠-1
entstanden: geprüft wird der Soft-Delete-Flag, gemeint war der fachliche Zustand. Zwei
Boolesch-artige Achsen nebeneinander sind eine Einladung, die falsche zu lesen. Mit dem
Wissen von heute: **eine** Achse, und «gelöscht» ist ein Wert darin.

**D · Der Test-Aufbau hätte von Anfang an so aussehen müssen wie jetzt.** Die bestehende
Suite ist gut geschrieben, aber sie ist eine Sammlung von **Einzelbeweisen** — jeder Test
baut seine Welt selbst, mit eigenen Hilfsfunktionen. Daraus kam 🟠-2 (jeder räumt anders
auf) und daraus kam, dass es bis heute keine Matrix gab. Ein gemeinsames `World`-Objekt
und Fälle **als Daten** hätten von Beginn an mehr Fälle für weniger Zeilen ergeben.

## Wo sich Komplexität angesammelt hat, die es nicht bräuchte

**`services/process.py` ist 1726 Zeilen.** Darin stecken vier Dinge, die wenig miteinander
zu tun haben: die Schreibstelle (`_pass`), die Freigabe, die Ausführung und **acht**
Ableitungsfunktionen für die Anzeige (`step_work`, `held_numbers`, `order_statuses`,
`waiting_counts`, `returning_home`, `pending_returns`, `deviation_flags`, `active_step_id`).
Die Regeln sind je einzeln am richtigen Ort — aber sie liegen in derselben Datei wie der
Mechanismus, den sie beschreiben. Das ist die Stelle, an der ich als Nächstes trennen
würde: **Mechanismus** (schreiben) von **Auskunft** (lesen).

**Ansonsten: erstaunlich wenig.** Es gibt keine tote Achse, keine zweite Statusliste, kein
`if abweichung:`. Die Prosa in den Docstrings ist umfangreich, aber sie ersetzt hier
tatsächlich Architekturdokumentation — und der Auditverlauf zeigt, dass sie stimmt.

---

# Empfehlungen — was sich wirklich lohnt

| Was | Nutzen | Aufwand | Risiko | Empfehlung |
|---|---|---|---|---|
| **🟠-1 · Inaktiver Artikel sperrt «Neu»** | hoch — schliesst eine Regel ohne Wirkung; verhindert Bestand, den niemand haben will | **sehr klein** (eine Bedingung in `resolve_lines`, ein Testfall existiert bereits) | klein — Entscheidung nötig: nur `Neu` oder auch `Lager` | **umsetzen**, sobald du die Frage `Neu`/`Lager` entschieden hast |
| **🟠-2 · Aufräumer der Wächter-Suite** | hoch — sonst ist `I12` dauerhaft rot und niemand schaut mehr hin | winzig | keins | **bereits umgesetzt** |
| **🟠-3 · Auftrag abbrechen** | hoch — der einzige Zustand ohne Ausgang | **gross** (Was passiert mit den Stücken? Wer darf es? Was mit dem Auftrag selbst? Alles offen) | mittel — ein halb durchdachter Abbruch ist schlimmer als keiner | **nicht jetzt.** Erst entscheiden (`PROCESS_CORE` §13.3), dann bauen. Ich würde es nach dem nächsten Modultyp angehen, wenn klarer ist, was «Aussenwirkung» heisst |
| **🟡-1 · Fehlermeldung nennt das Stück** | mittel — bei 1500 Stück der Unterschied zwischen «suchen» und «hingehen» | klein (Nummer durch `record_for_step` reichen) | keins | **umsetzen**, wenn du ohnehin an der Datenerfassung bist |
| **🟡-2 · Zwei Fallback-Anzeigen** | klein — heute unerreichbar | winzig | keins | **mitnehmen**, wenn die Datei ohnehin angefasst wird. Kein eigener Vorgang |
| **🟡-3 · Docstring-Vokabular** | klein, aber es ist die erste Stelle, an der jemand nachschaut | winzig | keins | **mitnehmen** |
| **🟡-4 · Stichproben-Rückfall** | klein | winzig | keins | **stehen lassen.** Er ist dokumentiert und für Alt-Definitionen richtig |
| **🟡-5 · Rohe DB-Meldung bei echter Nebenläufigkeit** | klein — selten, kein Datenverlust | mittel (`IntegrityError` abfangen und übersetzen, ohne den Fehler zu verschlucken) | **mittel** — ein zu breiter `except` ist genau das, was G3 verbietet | **nicht umsetzen**, solange es Einzelbenutzer-Betrieb ist. Wieder aufnehmen, wenn mehrere Personen gleichzeitig freigeben |
| **A · `waiting_counts` als rekursives SQL** | mittel — eine Ableitung an einer Stelle statt in einer Python-Schleife | mittel | mittel — die Kettenlogik ist geprüft und läuft; ein Umbau riskiert genau den Teil, der am schwersten zu testen war | **nicht umsetzen.** Der Nutzen ist Eleganz, der Preis ist der einzige Teil des Modells, dessen Fehler man erst drei Ebenen tief sieht |
| **B · Eigene Wörter je Achse** | mittel — Verständlichkeit | **gross** (Katalog, generierter Frontend-Spiegel, Migration von Altbestand) | gross | **nicht umsetzen.** Ein Wort zu ändern, das in Daten steht, kostet mehr als es einbringt |
| **C · `is_active` und `status` zusammenlegen** | mittel | **sehr gross** (jede Tabelle, jede Abfrage, jede Migration) | gross | **nicht umsetzen.** Die Erkenntnis gehört in die Landkarte, nicht in einen Umbau |
| **D · `process.py` in Mechanismus und Auskunft trennen** | mittel — die Datei ist die meistgelesene des Systems | mittel (reines Verschieben, keine Regeländerung) | klein — die Wächter dieser Kampagne decken jede verschobene Funktion ab | **umsetzen, wenn Ruhe ist.** Jetzt gerade würde es die Diffs jeder laufenden Arbeit unlesbar machen |

## Was ich ausdrücklich **nicht** empfehle

- **Keinen Umbau am Rückführungs-Modell.** Es ist der komplexeste Teil und der einzige,
  der über drei Ebenen geprüft ist. Es funktioniert, und es funktioniert aus dem richtigen
  Grund (die Position steht schon da, sie wird nicht berechnet).
- **Keine zweite Statusliste**, auch nicht «nur für die Anzeige». Genau daraus ist die
  Klasse von Fehlern entstanden, die dieses Modell abgeschafft hat.
- **Keine Reparatur-Skripte** für die gefundenen Zustände. Es gibt nichts zu reparieren —
  alle Invarianten halten.
