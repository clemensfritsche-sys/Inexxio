# FINDINGS — Befunde des Audits

> Sortiert nach Schwere. Zu jedem Befund die **Ursache**, nicht nur das Symptom — und wo
> mehrere zur selben Wurzel gehören, steht das dabei.
>
> **Es wurde nichts implementiert.** Die einzigen Änderungen dieser Runde sind der
> Testapparat selbst und **eine** Korrektur an der bestehenden Wächter-Suite (🟠-2), die
> den Datenbestand beschädigt hat, über den geprüft werden soll.

---

## Zusammenfassung

| Schwere | Anzahl | |
|---|---|---|
| 🔴 verletzt eine Grundregel / führt zu falschen Daten | **0** | — |
| 🟠 Sackgasse · Inkonsistenz · unklares Verhalten | **3** | 🟠-1 · 🟠-2 · 🟠-3 |
| 🟡 Verbesserungspotenzial | **5** | 🟡-1 … 🟡-5 |

**Es gibt keinen 🔴-Befund.** Alle sechs Grundregeln aus `SYSTEM_LOGIC.md` §3 halten über
67 Szenarien und 15 Invarianten (238 Aufträge · 1884 Einzelinstanzen · 7881 Log-Einträge).
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

**Die Frage, die vor dem Fix steht** (nicht von mir zu entscheiden): gilt die Sperre für
**alles** oder nur für «Neu»? Ein Auftrag, der **bestehende** Stücke eines
ausgelaufenen Artikels prüft oder aussondert, ist fachlich sinnvoll — man muss den
Restbestand ja noch abwickeln. Neue Stücke zu **erzeugen** ist es nicht. Meine Empfehlung:
nur die `Neu`-Zeile sperren, `Lager` erlauben.

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

**Bewusst offen** (`PROCESS_CORE` §13.3). Ich baue hier nichts auf Verdacht — aber es
gehört auf die Landkarte, weil es der einzige Zustand ohne Ausgang ist, der nicht
ausdrücklich terminal ist.

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

## 🟡-3 · Zwei Vokabulare für den Artikel-Status im Docstring

`models/article.py` beschreibt die Werte als `released` / `inactive`. Gültig sind
`freigegeben` / `inaktiv` (`domain/statuses`), und `main._ARTICLE_STATUS_FIXES` zieht
Altbestand darauf nach. Der Code ist korrekt, der Docstring ist es nicht — und er ist die
erste Stelle, an der jemand nachschaut.

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
