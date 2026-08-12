# CONCEPT_REVIEW — hält das Modell die Wirklichkeit aus?

> **Andere Frage als die Testkampagne.** Die fragte: *folgt der Code den Regeln?* Antwort
> war ja (71 Fälle, 15 Invarianten, kein 🔴). Hier ist die Frage: **sind die Regeln
> richtig?** Ein System, das seine eigenen Regeln perfekt befolgt, kann trotzdem das
> falsche Modell haben — und es merkt es nie selbst.
>
> **Grundlage:** die Absicht in `SYSTEM_INTENT.md`, die Regeln in `SYSTEM_LOGIC.md` und
> `PROCESS_CORE.md`, und der **aktuelle** Code (`domain/`, `models/`, `services/process.py`,
> `sampling`, `capture_types`, Router-Wächter), gelesen auf Stand `fd0471f`.
>
> **Nichts implementiert.** Kein Fix, auch kein kleiner. Wo ich spekuliere, steht es dabei.
>
> **Kein akuter Datenfehler gefunden.** Die Invarianten halten; es gibt nichts zu
> reparieren. Was hier steht, sind Modell- und Beschreibungsfragen.

---

# 1 · Die Realitätsprobe

Zwölf Vorgänge, wie sie in einem Maschinenbaubetrieb mit zehn Leuten vorkommen. Gefragt
ist nicht, ob es eine Schaltfläche gibt, sondern ob das **Modell** den Vorgang kennt.

| # | Vorgang | Trägt das Modell ihn? |
|---|---|---|
| 1 | **Montage** — 4 Teile werden zu 1 Baugruppe | **Nein, strukturell nicht** (§1.1) |
| 2 | **Teilung** — eine 6-m-Stange wird in 3 Stücke gesägt | **Nein, strukturell nicht** (§1.1) |
| 3 | **Zerlegung** — eine Baugruppe wird in Teile zerlegt | **Nein** — Umkehrung von 1 |
| 4 | **Verbrauch** — 600 Schrauben da, 3 verbaut, 597 übrig | Der **Rest** trägt sauber. Der **Verbrauch** nicht (§1.1) |
| 5 | **Etwas liegt einfach da**, ohne je in einem Auftrag gewesen zu sein | Nur über einen Pseudo-Erzeugungsauftrag (§1.2) |
| 6 | **Inventurdifferenz** 597 gezählt, 594 gefunden | **Ja, und zwar richtig** (§1.3) |
| 7 | **Dauer** an einem Modul | Daten ja, Auswertung nein, **Soll** gar nicht (§1.4) |
| 8 | **Etwas hängt seit sechs Wochen** | **Nein** — ununterscheidbar von «läuft» (§1.4) |
| 9 | **Kundenrückläufer** — Maschine kommt nach zwei Jahren zurück | **Ja, mustergültig** (§1.5) |
| 10 | **Falsche Erfassung**, später entdeckt | Nur solange das Stück noch am Modul steht (§1.6) |
| 11 | **Sonderfreigabe** (ausserhalb Toleranz, bewusst angenommen) | Mechanisch ja, **nachweislich nein** (§1.7) |
| 12 | **Berechtigungen** / zwei Personen gleichzeitig | Attribution ja, **Autorisierung nein** (§1.8) |

## 1.1 · Montage, Teilung, Verbrauch — die eine grosse Lücke

**Das Modell kennt genau EINE Art von Beziehung zwischen Stücken: die zeitliche.** Ein
Stück hat ein Vorher und ein Nachher (die Journey, §7.4). Es hat **keine** Beziehung
*zu einem anderen Stück*: kein «besteht aus», kein «steckt in», kein «wurde geteilt in».

Für einen Maschinenbauer ist das die Kernoperation. Vier Beobachtungen:

**a) Der Zustand fehlt — und das ist dokumentiert.** `domain/statuses` nennt ausdrücklich
`verbraucht` als *«nicht angelegt, weil erfunden — wäre ein zweiter Endzustand»*. Die
Entscheidung ist getroffen. Sie ist aber über ein **Wort** getroffen worden, nicht über
einen **Vorgang**: nirgends steht, dass damit Montage und Verbrauch nicht abbildbar sind.

**b) Die Sperre ist eine Zeile, und sie hat einen anderen Zweck.** `_assert_single_new`
(Testnotiz #693) verbietet «Neu» zusammen mit irgendeiner anderen Zeile. Der Grund ist
gut: ein Erzeugungsauftrag trägt den Versionsstempel **genau eines** Artikels, und für
eine zweite Zeile wäre der Stempel eine Behauptung.

Die Nebenwirkung ist, dass **exakt der Auftrag verboten ist, der eine Montage wäre**:

```
Zeile 1  Rahmen      Lager   1        ─┐
Zeile 2  Motor       Lager   1         ├─ verbrauchen
Zeile 3  Schrauben   Lager   8        ─┘
Zeile 4  Maschine    Neu     1        ─── erzeugen
```

Und in der Historie steht ausdrücklich, dass dieser Fall einmal vorgesehen war: *«Ersetzt
die frühere Annahme ‹Artikel A Neu + Artikel B Lager ist ein normaler Fall›.»* Er wurde
weggeregelt, um eine Stempelfrage zu lösen — ohne zu bemerken, dass er die Montage ist.

**c) Zwei Aufträge helfen nicht.** Man könnte die Teile in Auftrag A aussondern und die
Baugruppe in Auftrag B erzeugen. Dann sind es zwei Aufträge ohne gemeinsames Stück — und
die Journey verbindet über das **Stück**. Die Verbindung ist damit endgültig weg. Die
Stückliste einer ausgelieferten Maschine wäre nicht mehr herleitbar: genau der Nachweis,
den ein Kunde nach einem Schadensfall verlangt.

**d) Die elegante Lösung liegt bereits da.** Wären die vier Zeilen oben **ein** Auftrag,
bräuchte es für die Genealogie **kein neues Feld**: die Stückliste ist «welche Stücke
waren im selben Auftrag wie dieses und haben ihn verbraucht verlassen». Eine Ableitung
über den Log, wie alles andere auch. Was fehlt, sind drei Dinge, und alle drei sind
Einträge, keine Mechanismen:

1. ein Endzustand `verbaut` (Katalog, eine Zeile — `Status.terminal = True`);
2. ein Modul, das ihn setzt (das Aussondern-Modul kann bereits **eine Ausprägung je
   Zielzustand**, `MODES`; fachlich ist «verbauen» aber kein «aussondern», also eher ein
   eigenes Modul mit demselben Muster);
3. die Aufhebung von `_assert_single_new` **für den Fall genau einer `Neu`-Zeile** — der
   Versionsstempel bleibt eindeutig, denn es gibt weiterhin nur eine Vorlage.

Punkt 3 ist die eigentliche Erkenntnis: die Regel ist **einen Tick zu breit gefasst**.
Sie müsste heissen *«höchstens eine `Neu`-Zeile»*, sie heisst heute *«eine `Neu`-Zeile
und sonst nichts»*.

**Teilung** (6-m-Stange → 3 Stücke) ist derselbe Fall in die Gegenrichtung und zusätzlich
von D1 betroffen: die Länge hat im Modell ohnehin keinen Platz. Sie ist der schwächere
Fall — als Erfassungswert an einem Datenerfassungsmodul lässt sie sich führen, und nach
dem Sägen wären es drei neue Stücke aus einem verbrauchten. Also derselbe Mechanismus.

> **Einordnung: 🔴 Modellfehler.** Nicht, weil eine Funktion fehlt, sondern weil die
> Datenstruktur die Beziehung nicht kennt — und weil eine bestehende Regel den einzigen
> Weg dorthin versperrt.

## 1.2 · Etwas, das einfach daliegt

Einzelinstanzen entstehen an **genau einer** Stelle: `materialize.create_for_line`, bei
der Freigabe eines Auftrags mit einer `Neu`-Zeile. Das ist eine gute Regel — jede Existenz
hat einen Anlass.

Der Preis: **Zukaufteile und Anfangsbestand brauchen einen Artikel mit
«Erzeugungsprozess»**, sonst weist `steps_for` mit 400 ab. Ein Maschinenbauer kauft den
Grossteil zu; für jedes Zukaufteil muss also ein Prozess modelliert werden, der in
Wahrheit ein Wareneingang ist. Fachlich ist das sogar richtig (Wareneingangsprüfung *ist*
ein Prozess, und ein Datenerfassungsmodul passt exakt). **Falsch ist nur der Name**: der
Reiter heisst «Erzeugungsprozess», und der Versionsstempel behauptet «so ist dieses Stück
entstanden» — bei einem Zukaufteil ist es aber beim Lieferanten entstanden.

> **🟡 Beschreibungsfehler, kein Modellfehler.** Der Mechanismus trägt; der Name führt in
> die Irre und wird beim Anlegen des zwanzigsten Zukaufartikels als Umweg empfunden.

## 1.3 · Inventurdifferenz — hier ist das Modell besser als erwartet

**Fehlbestand (3 Stück weg):** ein `Lager`-Auftrag greift genau die drei Nummern, ein
Aussondern-Modul mit `mode=scrap` und dem Grund «Inventurdifferenz 08/2026». Fertig. Der
Nachweis ist vollständig, die Menge stimmt danach, und — das ist der schöne Teil — **der
Mensch muss sagen, welche drei fehlen.** Er kann es nicht umgehen. Das ist unbequem und
sachlich richtig: welche drei fehlen, weiss das System nicht, und eine Automatik würde
raten.

**Überbestand (3 Stück zu viel):** braucht einen `Neu`-Auftrag — mit dem Stempelproblem
aus §1.2.

> **✅ Kein Befund für den Fehlbestand.** Die Inventur braucht kein eigenes Modul; das ist
> ein Beleg dafür, dass die Grundmechanik trägt. Der Überbestand fällt unter §1.2.

## 1.4 · Dauer und Stillstand

Die Daten sind vollständig da: jedes `process_event` trägt `created_at`, `active_step_id`
sagt, wo ein Auftrag steht, `started_at` gibt es bereits als Funktion. **Was fehlt, ist
kein Datum, sondern ein Soll.** Ein Auftrag hat keinen Termin und ein Modul keine
geplante Dauer. Ohne Soll ist «steht seit sechs Wochen» nicht von «dauert eben sechs
Wochen» zu unterscheiden — und darum kann keine Auswertung, so gut sie gebaut wäre, die
Frage «was hängt?» beantworten.

Der Auftragsstatus verschärft es: er kennt drei Werte und keiner davon hat eine
Zeitachse. Ein vergessener Auftrag ist von einem laufenden nicht unterscheidbar, für
immer.

> **🟠 Modelllücke.** Nicht die Auswertung fehlt, sondern die Bezugsgrösse. Gehört zu
> derselben Wurzel wie «kein Ort» und «kein Zweck» (§5, Wurzel 2).

## 1.5 · Kundenrückläufer — das Modell in seiner besten Form

Eine Maschine kommt nach zwei Jahren zur Reparatur zurück. Ihr Stück ist `freigegeben`
und in keinem Auftrag; ein ganz gewöhnlicher `Lager`-Auftrag greift es, die Journey
verbindet das neue Kapitel mit dem alten, und die Reparatur steht in derselben Geschichte
wie die Fertigung. **Kein Sonderfall, keine Zeile Code, kein zweiter Datentyp.**

Genau das ist der Beweis, dass D1/D2/D4 richtig sind. Ich habe im ganzen Review keine
Stelle gefunden, an der die drei tragenden Entscheidungen selbst zu Problemen führen.

Eine Einschränkung, die zur Wurzel 2 gehört: die Maschine war zwei Jahre **beim Kunden**
und zählte die ganze Zeit als `freigegeben` — also als **Bestand**. Der Bestand enthält
alles, was je ausgeliefert wurde.

## 1.6 · Eine falsche Erfassung, später entdeckt

| Wann entdeckt | Weg |
|---|---|
| Stück steht noch am Modul | **Erneut erfassen** — das nächste Urteil ersetzt das letzte (`held_units` ist eine Auskunft, keine Sperre). Sauber gelöst. |
| Stück ist weitergezogen | **Kein Weg.** `_units_at` findet es dort nicht mehr, es gibt keine Ereignisart für eine Korrektur und keinen Endpunkt dafür. |

Der Docstring von `ProcessEvent` sagt: *«Eine Korrektur ist ein neuer Eintrag, nie eine
Änderung des alten.»* Das ist genau richtig gedacht — **den Eintrag gibt es nicht.**

Warum das mehr ist als Bequemlichkeit: ein Zahlendreher, den man im System nicht
korrigieren kann, wird auf Papier daneben korrigiert. Ab da ist das System nicht mehr die
Quelle, und zwar unbemerkt. Das ist Punkt 4.4 aus `SYSTEM_INTENT` — die gefährlichste
Fehlerform, weil sie nach Betrieb aussieht.

> **🟠 Implementierungslücke, klein.** Der Mechanismus (append-only) trägt sie bereits;
> es fehlt eine Ereignisart mit Verweis auf die korrigierte Zeile, Grund und Person. Die
> alten Werte bleiben stehen — das ist der Punkt.

## 1.7 · Sonderfreigabe (Konzession)

ISO 9001 §8.7 kennt drei Umgänge mit einem nicht konformen Ergebnis: **korrigieren**,
**aussondern**, **Sonderfreigabe**. Die ersten beiden trägt das Modell (Abweichungsauftrag
bzw. Aussondern-Modul). Die dritte:

Ein `measure`-Punkt ausserhalb der Toleranz ergibt `failed`; die ganze Instanz hält an.
Der vorgesehene Ausweg (`SYSTEM_LOGIC` §5.5) ist ein Abweichungsauftrag mit **gekappter
Rückführung**: die Stücke laufen dort weiter, der Eltern-Auftrag läuft mit weniger. Das
**funktioniert**, und mit einem `text`-Erfassungspunkt «Begründung der Sonderfreigabe» ist
sogar die Begründung im Nachweis.

Drei Dinge daran sind unbefriedigend:

1. **Der Rest des Prozesses muss von Hand nachmodelliert werden.** Der Folgeauftrag erbt
   nichts; niemand weiss hinterher, dass seine Module «die restlichen Schritte von Auftrag
   X» sind.
2. **Der Befund bleibt unerledigt.** Im Log steht `failed`, und danach steht dort nichts
   mehr. Es gibt keine Verknüpfung «dieser Befund wurde durch jene Entscheidung erledigt».
   Die Frage *«welche Durchfaller des letzten Jahres wurden wie behandelt?»* ist nicht
   beantwortbar — obwohl beide Hälften der Antwort in der Datenbank stehen.
3. **Der bequemere Weg ist eine Fälschung.** Wer die Umstände nicht kennt, tippt einen
   passenden Messwert ein, und alles läuft weiter. Das System bietet den ehrlichen Weg
   an, aber es macht ihn deutlich teurer als den unehrlichen. Das ist eine Einladung, und
   Einladungen werden angenommen.

> **🟠 Modelllücke.** Nicht der Mechanismus fehlt, sondern die **Verknüpfung Befund ↔
> Entscheidung**. Sie ist dieselbe fehlende Verknüpfung wie in §2 unten.

## 1.8 · Berechtigungen und Gleichzeitigkeit

**Autorisierung:** Jeder Endpunkt hängt an `require_employee`. Es gibt keine Rolle je
Modultyp, keine Funktionstrennung, keine Vier-Augen-Regel. Wer sich anmelden kann, kann
600 Stück verschrotten.

Die Absicht wird davon **nicht** verletzt: `SYSTEM_INTENT` verlangt *«wer es zu
verantworten hat»*, und das ist über `actor_id` an jedem Ereignis lückenlos erfüllt.
Attribution ja, Autorisierung nein. Diese Unterscheidung ist wichtig, weil sie die
Dringlichkeit halbiert: der Nachweis ist vollständig, nur die Prävention fehlt.

Für zehn Leute ist eine flächendeckende Vier-Augen-Regel Theater. Was zählt, sind die
**unumkehrbaren** Vorgänge — heute genau einer: `Verschrotten`. Der Ort für die Regel
existiert bereits (`Module`, ein Attribut neben `terminal` und `requires_verification`).

**Gleichzeitigkeit:** `confirm_step` nimmt keine Sperre. Zwei Personen, die dieselbe
Instanz am selben Modul gleichzeitig bestätigen, lesen beide dieselbe Warteliste.
*Spekulation, nicht gemessen:* das ergibt zwei Erfassungszeilen und zwei Schritt-Ereignisse
für denselben Vorgang — kein kaputter Zustand, aber ein doppelter Nachweis. Die
Testkampagne hat Nebenläufigkeit ausdrücklich nur bei der **Freigabe** geprüft (S63);
`TEST_REPORT` §3 weist «Mehrbenutzer über HTTP» als nicht gefahren aus.

> **🟠 Autorisierung · 🟡 Gleichzeitigkeit (spekulativ).**

---

# 2 · Ist der Abweichungsauftrag überladen?

Er trägt heute: **Nacharbeit · Aussonderung · Auftragsabbruch · Aufhebung einer Sperre ·
100 %-Kontrolle · Wiedereingliederung** — und nach §1.3/§1.7 auch **Inventurdifferenz**
und **Sonderfreigabe**. Acht Vorgänge, ein Mechanismus.

**Der Mechanismus ist richtig, und ich würde nichts daran ändern.** Alle acht sind
tatsächlich dasselbe: *ein Auftrag greift ein Stück, das nicht frei verfügbar war.* Genau
darum gibt es nirgends ein `if abweichung:`, und genau darum lösen sich Ketten über drei
Ebenen ohne Sonderlogik auf (S43, S47). Das ist die beste Stelle des Modells.

**Das Label ist falsch, und das ist keine Kosmetik.** `deviation_flags` leitet ab: *«sein
Start wich vom Regelstart ab»*. Als Aussage stimmt das exakt — sie lautet
**«hier hat jemand auf gebundenes Material zugegriffen»**. Sie lautet *nicht* «hier ist
etwas schiefgegangen», und das ist, was jeder Leser im Wort «Abweichung» hört.

**Antwort auf die Frage:** ein Bericht «alle Abweichungen des letzten Jahres» wäre in
einem Jahr **nicht aussagekräftig**. Er listet die geplante 100 %-Kontrolle neben dem
Bruch einer Welle neben der Inventurbereinigung neben der Freigabe einer gesperrten
Charge. Als **Qualitätsbericht** ist er wertlos; als **Zugriffsbericht** ist er
vollständig und korrekt.

**Und der Grund ist immer derselbe wie in §1.7: es fehlt genau ein Feld.** Ein Auftrag
sagt heute nicht, **warum es ihn gibt**. Mit einem Pflicht-`Zweck` am Auftrag — einem
Satz, wie ihn das Aussondern-Modul für seinen Grund bereits verlangt — wird derselbe
Bericht sofort brauchbar, ohne eine Zeile Mechanik: gruppiert nach Zweck statt nach einem
abgeleiteten Etikett.

Das Feld ist auch nach der strengsten Hausregel zulässig. Der Test lautet: *lässt es sich
ableiten?* Der Zweck eines Auftrags kann aus nichts abgeleitet werden — er existiert nur
im Kopf dessen, der ihn erteilt. Damit ist er kein zweiter Ort für eine bestehende
Wahrheit, sondern die einzige Stelle für eine neue.

---

# 3 · Ein Wort, zwei Bedeutungen

Systematisch gesucht, nach dem Muster von `is_active` ↔ `status`. Fünf Funde, zwei davon
neu und einer davon unangenehm.

| Wort | Bedeutung A | Bedeutung B | Kollidiert? |
|---|---|---|---|
| **`release` / `released_at`** | `process.release()` = **den Auftrag starten** | `OrderUnit.released_at` = die Zugehörigkeit ist **beendet** | **Ja, im selben Modul.** Dasselbe Wort für Anfang und Ende. |
| **`terminal`** | `Status.terminal` = das **Stück** kann nicht mehr weiter | `Module.terminal` = die **Reise** endet hier | **Ja.** Aussondern mit `mode=block` ist ein terminales Modul mit **nicht**-terminalem Status. |
| **`freigegeben`** | Stück: «in keinem Auftrag» | Artikel: «auftragsfähig» | bekannt (FINDINGS «B») — **dazu C:** «freigeben» ist auch die **Aktion**, die ein Stück aufhören lässt, freigegeben zu sein. |
| **`Abgeschlossen`** | Auftrag: den definierten Weg zu Ende gegangen | umfasst «alle Stücke verschrottet» | Dokumentiert und verteidigt, aber ein Leser erwartet «erfolgreich». |
| **`is_active`** | Soft-Delete | fachlicher Zustand | bekannt und behoben (FINDINGS 🟠-1 / Fundliste) |

**Die beiden neuen sind unterschiedlich schwer.**

`release`/`released_at` ist eine **Lesefalle**: wer `released_at IS NULL` sieht, liest
«noch nicht freigegeben» statt «noch aktiv». Sie hat noch keinen Fehler erzeugt, weil sie
an genau drei Stellen steht — aber sie ist die Sorte Falle, die beim vierten Leser
zuschlägt.

`terminal` ist die interessantere: **zwei verschiedene Fragen mit demselben Namen, deren
Antworten auseinandergehen dürfen.** «Endet die Reise?» und «Gibt es einen Weg zurück?»
sind wirklich zwei Fragen, und beim Sperren lauten die Antworten ja/nein. Der Code hält
sie sauber getrennt (`Module.terminal` steuert Kette und `_finish`, `Status.terminal`
steuert Farbe, Auswählbarkeit und DB-Trigger) — aber jeder Leser muss diese Trennung erst
selbst herstellen. Das ist genau das Muster von `is_active`, nur eine Ebene höher: **nicht
zwei Wahrheiten, sondern ein Name für zwei Wahrheiten.**

> **🟡 beide.** Kein Verhalten falsch, aber die Kosten fallen bei dem an, der als Nächstes
> dazukommt. Umbenennen ist billig, solange es keinen Altbestand betrifft — und keiner
> der beiden Namen steht in Daten.

---

# 4 · Zehnmal grösser

| Fall | Bricht etwas **konzeptionell**? |
|---|---|
| **50 000 Stück in EINEM Auftrag** | Nein — aber ein Auftrag mit 100 %-Stichprobe verlangt **50 000 Wertesätze in einer Anfrage**. |
| **200 gleichzeitige Aufträge** | Nein konzeptionell. `waiting_counts` liest bei **jeder** Feed-Abfrage **alle** offenen Ausleihen systemweit (bekannt, FINDINGS «A»). |
| **Fünf Jahre Log** | Nein. Grössenordnung ~5–10 Mio. Zeilen; für Postgres nichts. Es gibt **kein Archivierungskonzept** — und darf keines geben: der Log **ist** die Wahrheit. Das ist konsistent, sollte aber irgendwo stehen. |
| **Eine Reise über 40 Aufträge** | **Ja, und das ist der interessante Fund.** |

**Zu 50 000:** die Mengen selbst tragen — `_pass` arbeitet auf Listen und stückelt in
1000er-Blöcke, nichts ist quadratisch. Die Grenze liegt woanders: die Erfassung gehört
**je Einzelinstanz** (§9.5, und das ist richtig — zwei Schrauben haben zwei Durchmesser).
Bei 100 % über 50 000 Stück sind das 50 000 Wertesätze in einem HTTP-Aufruf. Genau dafür
gibt es die Stichprobe — aber der **Vorgabewert ist 100 %**. Die Vorgabe ist damit für
grosse Chargen die einzige unbrauchbare Einstellung. *(Nicht gemessen; ab welcher Zahl es
praktisch kippt, gehört in eine Lastmessung, nicht in dieses Review.)*

**Zu 40 Aufträgen:** die Journey zeigt **einen** Nachbarn nach vorn und einen zurück. Eine
Lebensgeschichte über 40 Kapitel ist also nur durch 40 Klicks lesbar, und niemand sieht
sie je als Ganzes. Die Daten reichen vollständig — es gibt keine Ansicht dafür.

Das kollidiert direkt mit dem ersten Satz der Absicht: *«Jedes physische Stück hat eine
lückenlose Lebensgeschichte.»* Sie **existiert**, sie ist nur nirgends **lesbar**. Für
den Auditfall (ein Kunde reklamiert, man will die Geschichte einer Welle vorlegen) ist
das der praktisch wichtigste Mangel des ganzen Reviews — er ist zugleich der billigste:
eine Leseansicht über `process_events WHERE instance_unit_id = …`, ohne neue Daten.

> **🟠 Ansichtslücke, keine Modelllücke.** Und sie ist der Grund, warum sie bisher
> niemandem auffiel: aus der Sicht des Modells ist alles da.

---

# 5 · Befunde, nach Wurzel

Fünf Wurzeln erklären alles oben. Die Sortierung ist nach Schwere.

## 🔴 Wurzel 1 — Das Modell kennt nur die Zeitachse eines Stücks, keine Beziehung zu anderen

**Modellfehler.** Betrifft: Montage · Teilung · Zerlegung · Verbrauch · Stückliste ·
Genealogie · Bestandswahrheit nach Einbau.

Ein Stück hat ein Vorher und ein Nachher, aber kein «besteht aus». Für einen
Maschinenbaubetrieb ist das die Hauptoperation. Die Sperre dorthin ist heute **eine
Zeile** (`_assert_single_new`), die aus einem anderen, guten Grund eingeführt wurde.

Der Weg hinaus verlangt kein neues Konzept — er verlangt eine **Entscheidung**:
ein Endzustand `verbaut`, ein Modul, das ihn setzt, und eine Präzisierung der
Einzelinstanz-Regel von «eine `Neu`-Zeile und sonst nichts» auf «höchstens eine
`Neu`-Zeile». Danach ist die Stückliste eine Ableitung über den Log, wie alles andere.

*Warum es kein Implementierungsfehler ist:* die Datenstruktur trägt die Beziehung nicht.
Sie kann sie tragen (über den gemeinsamen Auftrag), aber niemand hat das je gesagt.

## 🟠 Wurzel 2 — Was sich nicht ableiten lässt, wurde mit weggeräumt

**Modellfehler, und der subtilste.** Betrifft: kein **Ort** · kein **Zweck** am Auftrag ·
kein **Termin** / keine Soll-Dauer.

Die Regel «nichts speichern, was sich ableiten lässt» (D9) ist die stärkste des Hauses und
hat die Fehlerklasse des Vorgängersystems strukturell beseitigt. Derselbe Reflex hat
danach auch drei Dinge entfernt, die sich **nicht** ableiten lassen und deshalb erfasst
werden müssten:

| | Warum es nicht ableitbar ist | Was heute fehlt |
|---|---|---|
| **Ort** | Wo etwas liegt, weiss nur, wer es hingelegt hat | «Wo ist es» — der **erste** Satz der Absicht — ist für freien Bestand unbeantwortbar |
| **Zweck** | Warum ein Auftrag existiert, weiss nur, wer ihn erteilt | Der Abweichungsbericht ist bedeutungslos (§2); eine Sonderfreigabe hat keinen Anlass (§1.7) |
| **Termin / Soll-Dauer** | Was geplant war, ist keine Beobachtung | «Hängt seit sechs Wochen» ist nicht erkennbar (§1.4) |

Der Prüfstein ist einfach und sollte in die Regeln: **ein Feld ist zulässig, wenn seine
Angabe aus keiner anderen im System herleitbar ist.** Danach sind alle drei zulässig — und
alles, was die alte Landkarte zu Recht verboten hat, bleibt verboten.

## 🟠 Wurzel 3 — Unveränderlich ist gebaut, die Korrektur daneben nicht

**Implementierungslücke.** Betrifft: falsche Erfassung nach dem Vorrücken (§1.6) ·
Verknüpfung Befund ↔ Entscheidung (§1.7, §2).

Beides ist derselbe fehlende Eintrag: ein Ereignis, das auf ein früheres zeigt und sagt,
was mit ihm geschehen ist. Der append-only-Log ist genau die Struktur, die das trägt; der
Docstring verspricht es bereits.

## 🟠 Wurzel 4 — Wer etwas tun *darf*, ist nicht modelliert

**Modelllücke, bewusst klein zu halten.** Betrifft: Berechtigungen (§1.8) ·
gleichzeitiges Bestätigen (§1.8, spekulativ).

Die Absicht ist erfüllt (Attribution). Was fehlt, ist Prävention bei genau den Vorgängen,
die man nicht rückgängig machen kann. Der Ort für die Regel existiert.

## 🟡 Wurzel 5 — Ein Name für zwei Fragen

**Beschreibungsfehler.** Betrifft: `release`/`released_at` · `Module.terminal` /
`Status.terminal` · «freigegeben» in drei Bedeutungen (§3).

Kein Verhalten ist falsch. Die Kosten trägt der nächste Leser — und `is_active` hat
gezeigt, dass diese Kosten irgendwann als Fehler anfallen.

---

# 6 · Die drei Fragen, ohne Diplomatie

## Trägt das Fundament?

**Ja.** Und zwar nicht knapp.

Die drei tragenden Entscheidungen — die Einzelinstanz als einziges Arbeitsobjekt, der
append-only-Log mit **einer** Schreibstelle, die Exklusivität als partieller Unique-Index
— sind richtig, und sie sind aus dem richtigen **Grund** richtig: sie beseitigen ihre
Fehlerklassen strukturell statt durch Wachsamkeit. Ich habe im ganzen Review **keine**
Stelle gefunden, an der eine von ihnen zum Problem wird. Der Kundenrückläufer (§1.5) und
die Inventurdifferenz (§1.3) fallen ohne eine Zeile Sonderlogik aus ihnen heraus; das ist
das stärkste Argument, das ein Modell haben kann.

**Aber es trägt eine engere Last, als die Absicht behauptet.** Es beweist lückenlos, was
mit einem Stück **innerhalb eines Auftrags** geschah. Es weiss nicht, **wo** ein Stück
ist, **warum** es einen Auftrag gibt, **wann** etwas fertig sein sollte, und **woraus**
etwas besteht. Die ersten drei sind nicht ableitbar (Wurzel 2), das vierte ist eine
fehlende Beziehung (Wurzel 1). Kein noch so gutes Ableiten wird sie hervorbringen.

## Was ist die grösste ungesehene Lücke?

**Dass das Modell keine Stückliste kennt** — und dass dieser Umstand in keiner Landkarte
steht.

Die Testkampagne konnte ihn nicht finden: sie prüft, ob die Regeln eingehalten werden, und
das werden sie. `PROCESS_CORE` §13 («bewusst noch nicht definiert») führt sechs Punkte,
keiner davon ist Montage. `SYSTEM_LOGIC` §5 führt vier, keiner davon ist Montage. Der
Katalog nennt `verbraucht` als «nicht angelegt, weil erfunden» — eine Entscheidung über
ein Wort, die den Vorgang mit erledigt hat, ohne ihn zu nennen.

Und die Sperre ist **eine einzige Zeile**, die aus einem anderen Grund entstand. Das ist
die unbequemste Erkenntnis dieses Reviews: die wichtigste Operation des Betriebs wurde
nicht verworfen, sondern **nebenbei ausgeschlossen**.

*Die zweitgrösste, weil sie praktisch schneller weh tut:* die Lebensgeschichte eines
Stücks existiert vollständig und ist nirgends als Ganzes lesbar (§4).

## Was ist die eleganteste Vereinfachung, die heute möglich ist?

**Der Auftrag bekommt einen Zweck — ein Pflichtfeld, ein Satz.**

Es ist keine Mechanik, kein Endpunkt, kein Zustand. Es kollabiert **drei** getrennte
Probleme auf einen Schlag:

* der Abweichungsbericht wird brauchbar (§2) — gruppiert nach Zweck statt nach einem
  abgeleiteten Etikett, das acht Dinge zusammenwirft;
* die Sonderfreigabe bekommt ihren Anlass (§1.7);
* das Kapitel bekommt seinen Titel (`SYSTEM_INTENT` §5c) — und damit beantwortet der
  Auftrag zum ersten Mal die Frage, die man einem Kapitel als erstes stellt.

Es folgt exakt dem Muster, das im Haus bereits steht: das Aussondern-Modul verlangt seinen
Grund **beim Modellieren**, mit derselben Begründung («eine Aussonderung, deren Anlass in
drei Monaten niemand mehr kennt, ist ein Loch im Nachweis»). Derselbe Satz gilt für jeden
Auftrag.

*Der Zweitplatzierte, falls «Vereinfachung» im engeren Sinn gemeint ist:* die
Umbenennung von `deviation_flags`. Sie kostet nichts, entfernt eine systematische
Fehllesung, und danach heisst die Sache, was sie ist — «Zugriff auf gebundenes Material».

---

# 7 · Empfehlung

Streng in beide Richtungen. **«Jetzt»** heisst: es blockiert etwas oder es kostet fast
nichts. **«Nie»** heisst: der Nutzen ist Eleganz und der Preis ist Risiko.

| Was | Problem | Aufwand | Risiko | |
|---|---|---|---|---|
| **`deviation_flags` umbenennen** («Zugriff auf gebundenes Material») | §2 — ein Wort, das acht Vorgänge als Fehler ausweist | **winzig** — abgeleitetes Label, steht in keinen Daten | keins | **jetzt** |
| **Zweck am Auftrag** (Pflichtfeld, ein Satz) | §2, §1.7, Absicht §5c — drei Probleme, ein Feld | **klein** — eine Spalte, ein Eingabefeld, ein Wächter bei der Freigabe | klein | **jetzt** |
| **Korrektur-Ereignis** (`KIND_CORRECTION` mit Verweis, Grund, Person) | §1.6 — sonst wandert die Wahrheit auf Papier | **klein** — eine Ereignisart, ein Endpunkt, keine Änderung am Bestehenden | klein — die alten Werte bleiben stehen, das ist der Punkt | **jetzt** |
| **Lebenslauf-Ansicht** je Einzelinstanz | §4 — die Geschichte existiert und ist nicht lesbar | **klein** — eine Leseansicht auf `process_events`, keine neuen Daten | keins | **jetzt** |
| **Montage / Verbrauch** — Endzustand `verbaut`, ein Modul dafür, `_assert_single_new` auf «höchstens eine `Neu`-Zeile» präzisieren | 🔴 Wurzel 1 | **mittel** im Bau — **aber die Entscheidung ist gross** | **hoch, wenn halb durchdacht.** Ein Endzustand ist endgültig; ein falsch geschnittener kostet Daten | **jetzt entscheiden, danach bauen.** Vor dem nächsten Modultyp — er würde sonst auf einem Fundament stehen, das sich noch bewegt |
| **Ort** (Halter je Einzelinstanz) | Wurzel 2 — der erste Satz der Absicht | mittel | mittel — der Vorgänger hatte eine Standort-Kette; sie wieder zu bauen heisst, ihre Fehler nicht mitzunehmen | **später**, aber **jetzt in die Landkarte** als offener Punkt |
| **Termin am Auftrag / Soll-Dauer** | §1.4 — «hängt seit sechs Wochen» | klein | klein | **später** — sinnvoll erst, wenn genug Aufträge laufen, dass die Frage entsteht |
| **Berechtigung je Modultyp** (mindestens für unumkehrbare Vorgänge) | §1.8 | klein — ein Attribut am `Module`, ein Wächter | klein | **später** — Attribution deckt den Nachweis; die Prävention wird ab der ersten angelernten Aushilfe wichtig |
| **Sperre beim gleichzeitigen Bestätigen** | §1.8, spekulativ | klein (`SELECT … FOR UPDATE` auf den Schritt) | klein | **später** — erst messen, ob der Fall wirklich eintritt |
| **`released_at` / `terminal` umbenennen** | §3 — Lesefallen | klein, betrifft keine Daten | klein | **später** — mitnehmen, wenn die Dateien ohnehin angefasst werden. Kein eigener Vorgang |
| **Reiter «Erzeugungsprozess» umbenennen** (Zukaufteile) | §1.2 | winzig | keins | **später** — mitnehmen |
| **Graph statt geordneter Liste** (Parallelität, Verzweigung) | D3 | gross | gross | **nie.** Der Abweichungsauftrag trägt die Schleife nachweislich über drei Ebenen; ein Kantenmodell brächte Zyklen und tote Äste zurück |
| **Mengen-Spalte für Meterware** | D1 | gross | **sehr gross** — es ist genau die Fehlerklasse, die dieses Modell abgeschafft hat | **nie.** Meterware gehört über Teilung (Wurzel 1) gelöst, nicht über eine Menge |
| **Flächendeckende Vier-Augen-Regel** | §1.8 | mittel | mittel — sie wird umgangen, sobald sie stört | **nie** bei zehn Personen. Nur die unumkehrbaren Vorgänge |
| **`is_active` global umbenennen** | FINDINGS | sehr gross | gross | **nie** — bereits entschieden, gilt unverändert |

## Was ich ausdrücklich nicht empfehle

* **Kein Umbau am Rückführungs-Modell.** Es ist der komplexeste Teil, der einzige über
  drei Ebenen geprüfte, und er funktioniert aus dem richtigen Grund (die Position steht
  schon da, sie wird nicht berechnet).
* **Kein zweiter Datentyp «Abweichung».** Der Mechanismus ist die beste Stelle des
  Modells; das Problem ist ein Wort, kein Typ.
* **Kein Feld, das sich ableiten liesse.** Der Prüfstein aus Wurzel 2 ist ausdrücklich
  eine Erlaubnis für **drei** Angaben, keine Lockerung der Regel.
