# Projektakte «Aufgaben» – wer macht was

> **Kopfstatus:** Konzept, Fassung 2 · **nichts gebaut** · Lead: Claude · Entscheid: Clemens
> Fritsche · seit 10.11.2026 · zuletzt 10.11.2026 (Rückmeldung zu Fassung 1 eingearbeitet)
> Bild (das ERP, wie es damit aussieht – 1:1, klickbar): https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r
> Diese Akte ist die **eine** Quelle für Ziel, Regeln, Modell, Plan und Entscheide des Projekts
> «Aufgaben». Was hier nicht als **entschieden** steht, ist nicht entschieden. Das Bild zeigt, die
> Akte hält fest. Fassung 1 steht in der Git-Geschichte dieser Datei. Vorgänger:
> `docs/konzept/lernende-firma.md` §3 («feste Zuständigkeit kommt mit dem Projekt «Aufgaben»») und
> `docs/konzept/wiederkehr.md` O18.

## 0 · Kurzfassung (zum Prüfen)

1. **Eine Aufgabe ist eine Ableitung, keine Zeile.** Das ERP weiss schon, wo etwas zu tun ist
   (Prozessschritt, offene Nachricht, anstehendes Papier, fehlende Angabe …). Niemand legt eine
   Aufgabe an, niemand hakt sie ab: sie verschwindet, sobald die Sache erledigt ist – und solange
   sie gerade nicht machbar ist (man wartet), gibt es sie nicht.
2. **Kompetenz statt Abteilung.** Wer eine Kompetenz hat, bekommt die Aufgaben dazu – egal, was er
   sonst tut. Kompetenzen gibt der Admin. **Eine Kompetenz ohne Person gibt es nicht.**
3. **Eine Aufgabe gehört genau einer Person. Eine Person hat genau eine Aufgabe: «Dran».**
4. **Wer frei wird, bekommt die nächste Aufgabe, die er kann.** Die Reihenfolge rechnet das System;
   Stufen oder Farben sieht niemand. Die Person tut, was zuoberst steht.
5. **Keine neue Oberfläche.** Ohne Filter steht im Feed zuoberst genau **eine** Zeile: mein Dran –
   der Datensatz selbst, kein eigener Bereich, keine Karte, kein «Öffnen». Darunter die übrigen
   Datensätze nach Aufgaben sortiert. Im Datensatz steht «Du bist dran» **dort, wo man es tut**
   (am Schritt, an der Nachricht, an der Karte) – nicht im Kopf.
6. **Abgeben ist ein Klick** – ohne Grund. Die Aufgabe geht an die nächste freie Person, die sie kann.
7. **Nichts blockiert.** Jeder darf weiterhin alles tun, was er darf. Wer eine fremde Aufgabe
   erledigt, hat sie erledigt.

## 1 · Problem

- **«Zu tun» sagt nur «wo», nie «wer».** Die Zahl hängt am Datensatz. Eine offene Mail zählt bei
  allen, die im Verlauf stehen: alle sehen sie, zuständig ist niemand.
- **Die Hauptarbeit fehlt.** Dass an einem Auftrag ein Prozessschritt dran ist, zählt heute
  nirgends – man muss den Auftrag öffnen. Aufträge sind aber der Hauptweg, wie etwas getan wird.
- **Keine Reihenfolge.** Was zuerst? Heute entscheidet, wer zuerst hinschaut.
- **Abteilungsdenken** droht, sobald man Zuständigkeit «nach Stelle» baut.
- **Zehn Dinge gleichzeitig** heisst: zehn Dinge halb.

## 2 · Ziel

**Jede Person weiss jederzeit, was sie jetzt tun soll – und alles, was zu tun ist, hat genau eine
Person. Ohne dass jemand plant, verteilt oder nachfragt.**

Messpunkte (nach rund drei Monaten, einmal von Hand aus dem Log):
1. Keine Aufgabe liegt länger als eine Stunde ohne Person, während jemand frei ist, der sie kann.
2. Kein Verteilen von Hand.
3. Keine neue Maske, kein neuer Datensatztyp.

## 3 · Grundsätze

- **Aufgabe = Ableitung.** Die Quellen wissen, was zu tun ist (heute `services/todo`, dazu
  Prozessschritt und Beleg). Gespeichert wird nur, was ein Mensch entscheidet oder nicht abzuleiten
  ist: wer welche Kompetenz hat, wer gerade dran ist.
- **Recht ≠ Kompetenz.** Das Recht (`domain/policy`) ist das Tor: darf ich das? Die Kompetenz ist die
  Zuteilung: soll ich das bekommen? Zugeteilt wird nur, wer **darf und kann**. «Admin» ist ein Recht.
- **Jeder macht alles, was er kann.** Keine Abteilungen, keine Teams, keine Rollen ausser den drei
  Zugangsrollen.
- **Ein Fokus.** Eine Person hat genau eine Aufgabe.
- **Die Person tut, was das System ihr gibt.** Keine Liste zum Auswählen, keine Prioritätsstufen.
- **Am Geschehen.** «Dran» steht dort, wo man es tut – nie als Banner.
- **Erklärbar.** Die Reihenfolge ist eine feste Regel (§6.4), keine KI. Im Hover steht, warum.
- **Keine Überwachung.** Das Log hält fest, wer wann dran war; daraus entsteht keine Rangliste und
  keine Leistungsauswertung je Person (CH ArGV 3 Art. 26).

## 4 · Ist-Analyse (Stand Code 10.11.2026)

| Baustein | Wo | Rolle künftig |
|---|---|---|
| «zu tun» – sammelt offene Dinge je Datensatz | `services/todo.py` → `GET /erp/todo`, `lib/todo.ts`, Zahl am `RecordIcon` | wird **die Quelle der Aufgaben** (je Eintrag Art, Schlüssel, Kompetenz) |
| Offene Nachrichten, überfällig nach 2 h | `communication.open_counts` | Nachricht beantworten |
| Zeiterfassung: «Gehen» fehlt, Nachweis | `timekeeping.tasks` | Aufgabe, die nur die Person selbst kann |
| Überfällige Rechnungen | `payment_list.overdue_counts` | Mahnen |
| Pflichtangaben fehlen | `people.missing_fields` | Angaben ergänzen (Kunde: Kundendienst; ich selbst: nur ich) |
| Papiere stehen an · erwartete Dokumente | `voucher_money.papers_due` · `requirements` | Papier prüfen und freigeben · Dokument nachreichen |
| Wiederholung wartet | `loop.todo_items` | Wiederholung klären |
| Feiertage, Rechtstexte fehlen | `holidays`, `legal` | nur der Admin darf |
| Handgriffe aus Mails | `handgriff.open_mail_counts` | Vorschlag prüfen |
| Prozessschritt hat wartende Stücke | `order_view` (`waiting`), `process.confirm_step` | **neu als Quelle** |
| Zahlung: nächste Handlung von uns | `voucher.situation` (`primary`, `can`) | **neu als Quelle** |
| Anwesenheit | Zeiterfassung | wer gerade zugeteilt werden kann |
| Sprung zur Stelle | `jumpToTodo` (`data-todo`) | Klick auf die Dran-Zeile springt an die Stelle |
| KI-Deckel 80 % | `todo._cap_item` | **Hinweis, keine Aufgabe** (nichts zu erledigen) |

## 5 · Begriffe

| Wort | Bedeutung |
|---|---|
| **Aufgabe** | Etwas, das ein Mensch jetzt mit einer Handlung im ERP erledigen kann – abgeleitet. Fester **Schlüssel**, ein **Ort** (Datensatz + Stelle), höchstens eine **Kompetenz**. |
| **Hinweis** | Etwas zum Wissen, nicht zum Erledigen (KI-Deckel, Pause zu kurz). Bleibt als Zahl am Datensatz, wird niemandem zugeteilt. |
| **Kompetenz** | Etwas, das eine Person kann. Zwei Sorten: **Tätigkeit** (fest im Code) und **Fach** (am Schritt angelegt). |
| **Dran** | Die eine Aufgabe, die einer Person gerade gehört. Wort im ERP. |
| **Frei** | Eine Person ist da (§6.5) und hat nichts dran. |

«Zu tun» bleibt als Zahl am Symbol (was ist an diesem Datensatz offen). «Dran» sagt, was **meins** ist.

## 6 · Das Modell

### 6.1 · Die Aufgabe (abgeleitet)

Jede Quelle liefert: `key` (fest, z. B. `step:<Auftrag>:<Schritt>` · `msg:<Person>:<Betreff>` ·
`paper:<Beleg>:<Art>`) · `object_id` + `anchor` (Sprungziel) · `label` (ein Satz) · `competence`
(höchstens eine) · `only` (nur diese Person: eigene Zeiterfassung, eigene Angaben) · `rule`
(nötiges Recht, Vorgabe `erp`) · `since` · `due` · `overdue`.

**Nur was jetzt machbar ist, ist eine Aufgabe**: fehlt Material am Ort, ist der Schritt gesperrt,
wartet die Zahlung auf die Partei, wartet die Mail auf den Kunden – dann gibt es keine. Körnung: je
(Auftrag, Schritt) eine, nicht je Stück; je Betreff einer Nachricht eine; je Beleg und Papier eine.

### 6.2 · Kompetenz

**Zwei Sorten, beide ohne eigene Pflegemaske:**

- **Tätigkeit – fest im Code**, eine je Sache, die das ERP tun lässt. Jede Aufgabe, die nicht mehr
  verlangt, verlangt ihre Tätigkeit:

  | Tätigkeit | Aufgaben |
  |---|---|
  | Kundendienst | Nachrichten beantworten, Angaben von Kunden ergänzen, Vorschläge aus Mails prüfen |
  | Verkauf | Zahlung als Einnahme: Offerte, Zusage, Rechnung, Papiere freigeben, Mahnen, Wiederholung klären |
  | Einkauf | Zahlung als Ausgabe: Bestellung, Lieferantenrechnung |
  | Logistik | Bewegen |
  | Montage | Verbrauch (Komponenten verbauen) |
  | Prüfen | Datenerfassung |
  | Qualität | Aussondern (sperren, verschrotten) |

  Gesellschaft pflegen (Feiertage, Rechtstexte) ist ein **Recht** (Admin), keine Kompetenz.
  Ein neues Modul bringt seine Tätigkeit mit (`domain/modules`, wie Farbe und Symbol).
- **Fach – am Schritt angelegt.** Wo eine Tätigkeit nicht reicht (eine Kranprüfung darf nicht jeder,
  der «Prüfen» kann), wählt man im Prozess-Editor im Feld «Wer kann das?» ein Fach oder legt eines
  neu an – **immer zusammen mit mindestens einer Person**. Eingefroren mit der Freigabe wie alles am
  Auftrag.

**Eine Kompetenz ohne Person gibt es nicht** – durchgesetzt, nicht gewarnt: ein Fach entsteht nur mit
einer Person, die letzte Person einer Kompetenz kann sie nicht verlieren («zuerst einer anderen
Person geben»), eine Person mit der letzten Kompetenz bekommt eine andere Rolle erst, wenn sie
weitergegeben ist. Abwesenheit (Ferien) ist davon unberührt – dann wartet die Aufgabe (§9).

Gepflegt am Personendatensatz (Karte «Kompetenzen», Admin klickt, jede Änderung im Log). Keine Karte
am Unternehmen, kein Katalog, keine Vorgabe je Art.

### 6.3 · Zuteilung

Gespeichert: **`task_focus`** – je Person höchstens eine Zeile, je Aufgabe höchstens eine Person
(zwei eindeutige Schlüssel: unmöglich, nicht verboten).

Gerechnet an **einer** Stelle (`services/tasks.dispatch`), beim Lesen der Aufgaben, im Takt und nach
Stempel, Abgeben und Kompetenz-Änderung:
1. Aufgaben aus den Quellen holen.
2. **Aufräumen:** gibt es die Aufgabe einer Fokus-Zeile nicht mehr → erledigt (`task.done`). Fehlt
   der Person Recht oder Kompetenz, oder ist sie nicht mehr da → zurück (`task.returned`).
3. Freie Personen bestimmen.
4. Aufgaben in der Reihenfolge (§6.4) durchgehen; je Aufgabe die Freien, die **dürfen und können**;
   die mit den **wenigsten anderen passenden Aufgaben** bekommt sie (Spezialisten bleiben frei für
   das, was nur sie können), bei Gleichstand wer länger frei ist.
5. `task.assigned` ins Log.

**Abgeben:** ein Klick am Ort, ohne Grund. Die Aufgabe geht an die nächste freie Person, die sie
kann; wer abgibt, bekommt dieselbe Aufgabe für 30 Minuten nicht wieder, und sofort seine nächste.
Wer etwas mitteilen will, schreibt wie immer eine Notiz an den Datensatz.

**Dringendes unterbricht nicht.** Es ist die nächste Aufgabe für die erste Person, die frei wird und
es kann. Gesehen wird es nicht von allen, sondern von der Person, die es bekommt.

### 6.4 · Reihenfolge (nach aussen unsichtbar)

Eine feste Regel, ohne Stufen oder Farben in der Oberfläche:
1. **Eine Frist ist verpasst** (Nachricht über 2 h offen, Rechnung überfällig, Termin überschritten) –
   am längsten verpasst zuerst.
2. **Termin in den nächsten 5 Arbeitstagen** – früherer zuerst.
3. **Der Rest** – wartet am längsten zuerst (ein Termin weiter weg zählt wie keiner).

Warum gerade diese Aufgabe, steht im Hover («Termin Fr 14.11.», «Antwort seit über 2 h offen»).
**Termin am Auftrag:** neu, optional, ein Kalendertag; jeder Schritt erbt ihn.

### 6.5 · Wer ist da

- Mit Zeiterfassung: nur wer **eingestempelt** ist; eine Absenz heute → nichts.
- Ohne Zeiterfassung (z. B. Admin ohne Vertrag): gilt als da.
- «Gehen» mit einer Aufgabe dran: sie bleibt bis zum nächsten «Kommen» – ausser die Frist wird
  verpasst oder die Person hat am nächsten Arbeitstag eine Absenz, dann geht sie weiter.

## 7 · Oberfläche (nur Bestehendes)

| Stelle | Heute | Neu |
|---|---|---|
| Feed ohne Filter | Datensätze | **zuoberst eine Zeile: mein Dran** (der Datensatz; zweite Zeile «DRAN · Prüfprotokoll an 1 Stück», Klick springt an die Stelle); darunter Datensätze mit Aufgaben in der Reihenfolge des Systems (rechts klein, wer dran ist), dann der Rest. Ist nichts dran: eine leise Zeile «Gerade nichts für dich». |
| Feed mit Filter | Typ | unverändert |
| Datensatz | Zahl am Symbol | unverändert; **kein** Banner im Kopf |
| Am Ort (Schritt, Nachricht, Karte) | – | eine Zeile: Bild + «Du bist dran.» (+ warum) + Abgeben-Symbol, bzw. «Marco Keller ist dran.» bzw. «Kommt zur nächsten freien Person mit «Verkauf»» |
| Prozessschritt (Kopf) | Name | dazu die Kompetenz als Chip |
| Prozess-Editor | Modul, Einstellungen | Feld **«Wer kann das?»** (Tätigkeit des Moduls · Fach · neues Fach mit Person) und wer es kann |
| Personendatensatz | Kommunikation, Zeiterfassung, Stammdaten | Karte **«Kompetenzen»** (Tätigkeiten, Fach; Admin klickt) |
| Auftragsentwurf | – | Feld **«Termin»** (optional) |
| Persönliches («Gehen» fehlt) | Zahl an mir | gewöhnliche Aufgabe, die nur ich kann: ist sie dran, steht mein eigener Datensatz zuoberst |

## 8 · Datenmodell (neu)

```
person_competences  person_object_id, competence (Text: Tätigkeit aus dem Code oder Fach),
                    is_active, …  (eindeutig je Paar; die letzte aktive Zeile einer Kompetenz
                    lässt sich nicht deaktivieren – Regel in services/competences, Index-Prüfung)
task_focus          person_object_id (eindeutig), task_key (eindeutig), since
orders.due_on       DATE NULL
Schritt-Konfig      competence (Fach) im eingefrorenen Schritt, sonst die Tätigkeit des Moduls
```
Log-Ereignisse: `task.assigned` · `task.returned` · `task.done` · `task.handed` (abgegeben).
Zwei Formen einer Regel: `competences.drop_problem` ↔ `assert_drop`, `tasks.assign_problem` ↔ Tor.

## 9 · Szenarien

1. **Kranservice beim Kunden.** Offerte (Verkauf) → Marco. Bewegen «zum Kunden» (Logistik) →
   die freie Person mit Logistik, die am wenigsten anderes kann (Nico). Prüfprotokoll (Fach
   Kranprüfung) → Lea. Rechnung (Verkauf) → wer mit Verkauf frei wird.
2. **Mail kommt, alle stecken in langen Aufgaben.** Sie wartet ohne Person. Nach 2 h steht sie
   vorne; wer mit Kundendienst als Nächstes frei wird, bekommt sie.
3. **Material fehlt am Verbrauch.** Keine Aufgabe. Liegt es da, entsteht sie.
4. **Lea wird krank.** Absenz → ihre Aufgabe geht weiter an eine freie Person mit Kranprüfung; ist
   keine da, wartet sie (im Hover: wer es kann und warum nicht da).
5. **Ich warte auf einen Rückruf.** Solange die Mail unbeantwortet beim Kunden liegt, ist es gar
   keine Aufgabe. Brauche ich trotzdem Abstand: Abgeben.
6. **Jemand erledigt eine fremde Aufgabe.** Die Quelle meldet nichts mehr → wer dran war, ist frei
   und bekommt die nächste.
7. **Nur eine Person im Betrieb.** Alles geht an sie, in der Reihenfolge.
8. **Eine Wiederholung entsteht** (wiederkehr O18): ihr erster Schritt ist eine Aufgabe → jemand ist
   dran. O18 ist damit beantwortet.
9. **Persönliches:** «Gehen» fehlt → Aufgabe nur für mich; ist sie dran, steht mein Datensatz oben.
10. **Admin entzieht die letzte Kompetenz** → abgewiesen mit Satz.

## 10 · Grenzfälle

- Schlüssel stabil (Wächter: zweimal lesen ohne Änderung = dieselben Schlüssel).
- Aufgabe verschwindet und kommt wieder (Kunde schreibt nochmals): gleicher Schlüssel, neu zugeteilt.
- Recht weg (Rolle `user`): Fokus weg. Kompetenz entzogen während dran: weiter an die Nächste.
- Automatische Schritte (Zahlung zieht selbst): keine Aufgabe, solange niemand von uns handeln muss.
- Externe (Kunde soll zahlen): nie eine Aufgabe bei uns; ihr Ausbleiben kann eine werden (Mahnen).
- Viele Stücke: jeder darf am Schritt bestätigen; zugeteilt bleibt eine Person.
- Takt schläft: zugeteilt wird beim nächsten Lesen.

## 11 · Bewusst NICHT

Kein Aufgaben-Datensatz zum Anlegen (etwas zu tun → Auftrag) · keine Liste zum Auswählen · keine
Prioritätsstufen, keine Farben für Wichtigkeit · keine Teams, Abteilungen · keine Kapazitätsplanung ·
keine Ranglisten · kein Bereich «Aufgaben», keine Karte am Unternehmen, kein Banner im Kopf · keine
KI in der Reihenfolge (später höchstens als Vorschlag).

## 12 · Bauplan

| Stufe | Inhalt |
|---|---|
| **A · Eine Liste** | `services/tasks` über alle Quellen (+ Prozessschritt, + Beleg), Aufgabe ↔ Hinweis getrennt, Reihenfolge §6.4, Termin am Auftrag; Feed ohne Filter danach sortiert |
| **B · Kompetenzen** | Tätigkeiten im Code, Fach am Schritt, Karte am Personendatensatz, Regel «nie ohne Person» |
| **C · Dran** | `task_focus`, Zuteilung, Anwesenheit, Dran-Zeile im Feed, «Du bist dran» am Ort, Abgeben |
| **D · später** | Kompetenz «lernt», KI-Vorschlag für Kompetenzen aus dem Log, Handy-Push für «Dran», Teilen grosser Schritte |

Wächter (je gegen seine Bug-Form geprüft): nie zwei Personen an einer Aufgabe · nie zwei Aufgaben an
einer Person · nie zugeteilt ohne Recht oder Kompetenz · nie eine nicht machbare Aufgabe · nie eine
Kompetenz ohne Person · Reihenfolge = §6.4 (Matrix mit vorher notiertem Soll).

## 13 · Entscheide

**Entschieden (10.11.2026)**
- E1 · Wörter: «Dran» für die eine Aufgabe einer Person. ✔
- Kein eigener Bereich «Aufgaben», keine Karte am Unternehmen, kein Banner im Kopf: Dran steht im Feed
  zuoberst und am Ort. ✔
- Abgeben ohne Grund. ✔
- Dringendes geht an die, die es können **und frei sind** – nicht an alle. ✔
- Kompetenzen gibt der Admin. Eine Kompetenz ohne Person ist unmöglich. ✔
- Keine sichtbaren Prioritätsstufen; das System ordnet. ✔

**Offen (Vorschlag in Klammern)**
- E2 · Strikt **eine** Aufgabe je Person? (ja – siehe §14 zu den Alternativen)
- E3 · Kompetenzen: Tätigkeiten fest im Code + Fach am Schritt? (ja)
- E4 · Termin am Auftrag (optional)? (ja)
- E5 · Nur wer eingestempelt ist, bekommt Aufgaben? (ja)
- E6 · Darf Dringendes eine laufende Aufgabe unterbrechen? (nein)
- E7 · Braucht es einen Hebel von Hand («Vorziehen», «an Person geben»)? (nein – erst, wenn es fehlt)
- E8 · Wer am wenigsten anderes kann, bekommt es (Spezialisten schonen)? (ja)

## 14 · Andere Wege – und warum «Dran»

| Weg | Wie | Stärke | Schwäche |
|---|---|---|---|
| **Liste für alle** (klassisch, Jira/Asana) | Jeder sieht alles, nimmt sich etwas | einfach, autonom | Rosinenpicken, Doppelarbeit, Abteilungsdenken |
| **Persönliche Liste** (Outlook-Aufgaben) | Jemand verteilt von Hand | klar | einer muss planen; Listen wachsen |
| **Kanban mit Grenze** (Lean) | Spalten, höchstens n in Arbeit | Fluss sichtbar | braucht Pflege und Disziplin; eine zweite Wahrheit neben dem ERP |
| **Skill-basierte Zuteilung** (Callcenter, Service-Disposition) | System gibt der nächsten freien, passenden Person die nächste Sache | niemand plant, eindeutig | wenig Wahl |
| **«Dran»** = Skill-basierte Zuteilung mit Grenze 1, abgeleitet aus dem ERP | wie oben, Aufgaben entstehen und verschwinden von selbst | kein Pflegen, kein Planen, kein Abhaken, ein Fokus | wenig Wahl (Ventil: Abgeben, und jeder darf alles tun) |

Variante zum Abwägen: **«Dran» + die nächsten zwei zur Wahl** – mehr Selbstbestimmung, aber zurück
zum Aussuchen. Vorschlag: nicht; erst messen, ob Abgeben oft gebraucht wird.

## 15 · Verweise

- Bild: https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r (Rolle Mitarbeiterin/Admin umschaltbar).
- Code: `backend/app/services/todo.py`, `frontend/src/lib/todo.ts`,
  `frontend/src/components/erp/feed-panel.tsx`, `detail-frame.tsx` (`RecordIcon`),
  `backend/app/domain/policy.py`, `backend/app/services/process.py` (`confirm_step`),
  `backend/app/services/order_view.py`, `services/timekeeping.tasks`.
