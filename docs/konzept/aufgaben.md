# Projektakte «Aufgaben» – wer macht was

> **Kopfstatus:** Konzept, Fassung 4 · **nichts gebaut** · Lead: Claude · Entscheid: Clemens
> Fritsche · seit 10.11.2026 · zuletzt 11.11.2026 (Gesellschaften, Termine und Planung, Kompetenzliste)
> Bild (das ERP, wie es damit aussieht – 1:1, klickbar): https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r
> Diese Akte ist die **eine** Quelle für Ziel, Regeln, Modell, Plan und Entscheide des Projekts
> «Aufgaben». Was hier nicht als **entschieden** steht, ist nicht entschieden. Frühere Fassungen
> stehen in der Git-Geschichte dieser Datei. Vorgänger: `docs/konzept/lernende-firma.md` §3 und
> `docs/konzept/wiederkehr.md` O18.

## 0 · Kurzfassung

1. **Eine Aufgabe ist eine Ableitung.** Das ERP weiss, wo etwas zu tun ist. Niemand legt eine
   Aufgabe an oder hakt sie ab; sie verschwindet, wenn die Sache erledigt ist, und es gibt sie
   nicht, solange man wartet.
2. **Jede Art Aufgabe nennt ihre Kompetenz – an einer Stelle, im Code.** Was man einer Person
   geben kann, ist daraus abgeleitet. Der Admin gibt sie. Eine Kompetenz ohne Person ist unmöglich.
3. **Eine Aufgabe gehört genau einer Person; eine Person hat genau eine Aufgabe.**
4. **Wer frei wird, bekommt die Aufgabe mit der frühesten Frist, die er kann.** Eine Regel, keine
   Stufen. Die Person tut, was zuoberst steht.
5. **Im Feed steht zuoberst meine eine Aufgabe – sonst ändert sich nichts.** Der Feed bleibt nach
   Nummer sortiert. Im Datensatz steht an der Stelle, wo es zu tun ist, das rote Zeichen «zu tun».
   Kein Banner, kein Text, keine Bilder anderer Personen.
6. **Abgeben ist ein Klick**, ohne Grund.
7. **Nichts blockiert.** Jeder darf weiterhin alles tun, was er darf.

## 1 · Problem

- «Zu tun» sagt nur «wo», nie «wer»: eine offene Mail zählt bei allen, zuständig ist niemand.
- Die Hauptarbeit fehlt: dass an einem Auftrag ein Schritt dran ist, zählt heute nirgends.
- Keine Reihenfolge – wer zuerst hinschaut, entscheidet.
- Abteilungsdenken droht, sobald man Zuständigkeit nach Stelle baut.
- Zehn Dinge gleichzeitig heisst: zehn Dinge halb.

## 2 · Ziel

**Jede Person weiss jederzeit, was sie jetzt tun soll – und alles, was zu tun ist, hat genau eine
Person. Ohne dass jemand plant, verteilt oder nachfragt.**

Messpunkte (nach rund drei Monaten, einmal aus dem Log): keine Aufgabe liegt über eine Stunde ohne
Person, während jemand frei ist, der sie kann · kein Verteilen von Hand · keine neue Maske.

## 3 · Grundsätze

- **Aufgabe = Ableitung.** Gespeichert wird nur, was ein Mensch entscheidet (wer welche Kompetenz
  hat) und wer gerade dran ist.
- **Eine Sache, eine Stelle.** Die Kompetenz steht an der Art der Aufgabe – nirgends sonst.
- **Recht ≠ Kompetenz.** Das Recht (`domain/policy`) ist das Tor, die Kompetenz die Zuteilung.
  Zugeteilt wird nur, wer darf **und** kann. «Admin» ist ein Recht.
- **Jeder macht alles, was er kann.** Keine Abteilungen, keine Teams.
- **Ein Fokus.** Die Person tut, was das System ihr gibt.
- **Ich sehe nur meins.** Woran andere arbeiten, muss niemand wissen, um seine Sache zu tun.
- **Eine Farbe.** Das Zeichen «zu tun» ist rot. Keine Stufen, keine Farben für Wichtigkeit.
- **Keine Überwachung.** Das Log hält fest, wer wann dran war; keine Rangliste, keine Auswertung je
  Person (CH ArGV 3 Art. 26).

## 4 · Ist-Analyse (Stand Code 10.11.2026)

| Baustein | Wo | Rolle künftig |
|---|---|---|
| «zu tun» – sammelt offene Dinge je Datensatz | `services/todo.py`, `lib/todo.ts`, Zahl am `RecordIcon` | wird **die Quelle der Aufgaben** |
| Offene Nachrichten, überfällig nach 2 h | `communication.open_counts` | Nachricht beantworten |
| Zeiterfassung: «Gehen» fehlt, Nachweis | `timekeeping.tasks` | nur die Person selbst |
| Überfällige Rechnungen | `payment_list.overdue_counts` | Mahnen |
| Pflichtangaben fehlen | `people.missing_fields` | Kunde ergänzen · eigene: nur ich |
| Papiere · erwartete Dokumente | `papers_due` · `requirements` | Papier freigeben · Dokument nachreichen |
| Wiederholung wartet | `loop.todo_items` | Wiederholung klären |
| Feiertage, Rechtstexte fehlen | `holidays`, `legal` | nur der Admin darf |
| Handgriffe aus Mails | `handgriff.open_mail_counts` | Vorschlag prüfen |
| Prozessschritt hat wartende Stücke | `order_view` (`waiting`) | **neu als Quelle** |
| Zahlung: nächste Handlung von uns | `voucher.situation` | **neu als Quelle** |
| KI-Deckel 80 % | `todo._cap_item` | Hinweis, keine Aufgabe |

**Was sich an «zu tun» ändert:** heute zählt die Zahl am Symbol alles Offene an einem Datensatz, für
alle. Künftig zeigt das rote Zeichen **nur, was ich tun muss** – genau eine Stelle.

## 5 · Das Modell

### 5.1 · Die Aufgabe (abgeleitet)

Jede Quelle liefert: `key` (fest) · `kind` (die Art) · `object_id` + `anchor` (wo) · `label` (ein
Satz) · `only` (nur diese Person) · `rule` (nötiges Recht) · `due` (Frist, §5.4). **Nur was jetzt
machbar ist, ist eine Aufgabe.** Körnung: je (Auftrag, Schritt) eine; je Betreff einer Nachricht eine;
je Beleg und Papier eine.

### 5.2 · Kompetenz – an einer Stelle

**Die Liste steht einmal im Code** (`domain/competences.py`), mit einer Eigenschaft je Kompetenz:
**Werk** (an den Ort gebunden, §5.7) oder **Büro** (für alle Gesellschaften). Gespeichert wird nur,
wer welche hat (`person_competences`, vom Admin am Personendatensatz). Eine neue Kompetenz ist eine
Zeile Code.

| Kompetenz | Art | Vorgabe für |
|---|---|---|
| Kundendienst | Büro | Nachricht beantworten · Angaben eines Kunden ergänzen · Vorschlag aus Mail prüfen |
| Verkauf | Büro | Zahlung als Einnahme (Offerte, Zusage, Rechnung) · Papier freigeben · Wiederholung klären |
| Einkauf | Büro | Zahlung als Ausgabe (Bestellung, Lieferantenrechnung) |
| Finanzen | Büro | Geld erfassen · Mahnen · Ausbuchen |
| Logistik | Werk | Bewegen |
| Montage | Werk | Verbrauch |
| Schweissen | Werk | – (am Schritt gewählt) |
| Elektrik | Werk | – (am Schritt gewählt: Steuerung, Funk) |
| Prüfen | Werk | Datenerfassung |
| Kranprüfung | Werk | – (am Schritt gewählt; nur Befähigte) |
| Qualität | Werk | Aussondern |
| – nur ich | – | eigene Zeiterfassung, eigene Angaben |
| – Recht Admin | – | Gesellschaft pflegen (Feiertage, Rechtstexte) |

**Am Schritt wählbar:** jedes Modul bringt seine Vorgabe mit; im Prozess-Editor lässt sie sich im
Feld «Wer kann das?» gegen eine andere **aus derselben Liste** tauschen (Verbrauch: Montage oder
Schweissen). Der Schritt definiert nichts, er wählt – es bleibt eine Stelle. Darunter steht, wer es
heute kann. Eingefroren mit der Freigabe.

**Nie ohne Person:** die letzte Person einer Kompetenz kann sie nicht verlieren; ein Wächter meldet
beim Start (über `core/report`), wenn eine Kompetenz der Liste niemand hat.

### 5.3 · Zuteilung

Gespeichert: `task_focus` – je Person höchstens eine Zeile, je Aufgabe höchstens eine Person (zwei
eindeutige Schlüssel). Gerechnet an einer Stelle (`services/tasks.dispatch`), beim Lesen, im Takt und
nach Stempel, Abgeben, Kompetenz-Änderung:
1. Aufräumen: gibt es die Aufgabe nicht mehr → erledigt; fehlt Recht oder Kompetenz, oder ist die
   Person nicht mehr da → frei.
2. Die Freien in der Reihenfolge, wie lange sie frei sind (wer am längsten frei ist, zuerst); **jede
   nimmt die Aufgabe mit der frühesten Frist, die sie darf und kann**. Das ist die ganze Zuteilung –
   eine Schleife, eine Sortierung.
3. Ins Log: `task.assigned` · `task.done` · `task.returned` · `task.handed`.

**Abgeben:** ein Klick an der Dran-Zeile. Wer abgibt, bekommt dieselbe Aufgabe 30 Minuten nicht wieder.
**Dringendes unterbricht nicht** – es kommt zur nächsten Person, die frei wird und es kann.

### 5.4 · Reihenfolge: früheste Frist zuerst

**Jede Aufgabe hat eine Frist, die früheste kommt zuerst.** Das ist die ganze Regel (Earliest
Deadline First, Jackson 1955: hält Verspätungen am kleinsten; keine Gewichte, kein Lernen in der
Regel selbst, unabhängig von der Grösse).

| Aufgabe | Frist |
|---|---|
| Schritt eines Auftrags | aus dem Plan des Auftrags (§5.6) |
| Nachricht | Eingang + 2 h (wie heute «überfällig») |
| Mahnen | Fälligkeit der Rechnung |
| Zeiterfassung, eigene Angaben | sofort (der Tag, der fehlt) – schnell gemacht |
| Papier, Dokument, Angaben eines Kunden, Vorschlag | Entstehen + 1 Arbeitstag |

Schwäche: die Regel ist so gut wie die Fristen. Darum rechnet das System die Fristen der Aufträge
selbst (§5.6) – von Hand gesetzt wird nur der Termin, den der Markt vorgibt.

### 5.5 · Wer ist da

Mit Zeiterfassung: wer eingestempelt ist, ohne Absenz heute. Ohne Zeiterfassung: gilt als da. Bei
«Gehen» bleibt die Aufgabe bis zum nächsten «Kommen», ausser ihre Frist ist verpasst oder die Person
hat am nächsten Arbeitstag eine Absenz.

### 5.6 · Termin und Plan eines Auftrags

**Der Termin – zwei Felder am Auftrag, vier Fälle.** `frühestens` und `spätestens` (Kalendertage):

| frühestens | spätestens | Fall | Beispiel |
|---|---|---|---|
| – | – | **so schnell wie möglich** | Ersatzteil aus dem Shop |
| – | X | **bis Tag X** | Trommeltausch, Liefertermin |
| X | X | **am Tag X** | Kranprüfung beim Kunden, Monteure vor Ort |
| A | B | **Zeitfenster** | Jahresinspektion (nicht zu früh, nicht zu spät) |

**Eine Stelle:** der Termin steht nur am Auftrag; die Zahlung liest ihn als Liefertermin (Offerte,
Zusage, Papier) – kein Feld im Beleg. Die Wiederholung setzt beide Felder je Nachfolger aus ihrem
Takt (zyklische Wartung = Zeitfenster). Verschieben ist ein Ereignis im Log; ist er zugesagt, sagt die
Zahlung, dass er sich vom Papier unterscheidet.

**Worauf der Termin zielt:** auf den **letzten Schritt, der an der Ware etwas tut** (Bewegen,
Verbrauch, Datenerfassung, Aussondern) – die Lieferung, die Prüfung vor Ort. Zahlungen danach (die
Rechnung) folgen dem Termin. Das System erkennt diesen Schritt selbst; nichts zu markieren.

**Der Plan – rückwärts gerechnet, Dauern gelernt.** Für jeden Schritt kennt das System eine
**Dauer** – nicht geschätzt, sondern **aus dem Log**: wie lange dieser Schritt dieses Artikels früher
gedauert hat (vom Erreichen bis zum Bestätigen, also inklusive Warten), und zwar die Dauer, die
**8 von 10** Malen gereicht hat. Gibt es keine 5 früheren Male: dieselbe Zahl über alle Artikel für
dieses Modul; gibt es auch das nicht: 1 Arbeitstag. Gerechnet in Arbeitstagen der Gesellschaft
(Feiertage gibt es schon).

- **Frist eines Schritts** = Termin minus die Dauern aller Schritte, die danach bis zum Termin noch
  kommen. Der Ziel-Schritt hat den Termin selbst.
- **«Am Tag» / Zeitfenster:** der Ziel-Schritt wird erst am Tag `frühestens` zur Aufgabe; alles davor
  (Teile bereitstellen) läuft nach Plan früher.
- **So schnell wie möglich:** der Termin ist **heute + Summe der Dauern** – derselbe Plan, nur
  vorwärts. Darum steht so ein Auftrag nicht hinter allem anderen und nicht vor allem anderen.
- **Gefährdet** heisst: die Frist eines Schritts ist vorbei. Das braucht keine eigene Anzeige – die
  Aufgabe steht dann bei der nächsten freien Person ganz vorne.
- Abweichungen sind gewöhnliche Aufträge: gleicher Plan. Ein grosser Austausch bei einer Wartung ist
  ein eigener Auftrag mit eigenem Termin.

Am Auftrag steht je Schritt leise die Frist («bis Mi 12.11.»), im Hover die Herkunft der Dauer.

**Später, und dann sehr wertvoll – Liefertermin vorschlagen:** beim Anbieten rechnet die Zahlung den
frühesten Termin, der hält (heute + Summe der Dauern + was gerade vor diesen Kompetenzen wartet). Der
Verkauf sagt dem Kunden nur noch, was das Werk halten kann.

### 5.7 · Mehrere eigene Gesellschaften

- **Zu welcher Gesellschaft eine Person gehört, sagt ihr Vertrag** (Zeiterfassung, gibt es schon) –
  kein neues Feld. Ohne Vertrag (Admin): alle.
- **Büro-Kompetenzen gelten überall** – eine Rechnung der deutschen Gesellschaft kann jemand in der
  Schweiz stellen.
- **Werk-Kompetenzen nur am Ort:** die Aufgabe geht nur an Leute der Gesellschaft, **bei der die Ware
  ist** – abgeleitet aus dem Ort der Stücke (die Halter-Kette endet an einer eigenen Gesellschaft).
  Ist die Ware beim Kunden (Service vor Ort), gilt die Gesellschaft, die den Auftrag fakturiert
  (`sites.company_for_country`, gibt es schon); ohne Zahlung die Gesellschaft der Person, die ihn
  freigab.
- Keine Einstellung, keine Zuordnung von Hand.

## 6 · Oberfläche (nur Bestehendes)

| Stelle | Neu |
|---|---|
| Feed ohne Filter | zuoberst **eine** Zeile: der Datensatz meiner Aufgabe, zweite Zeile der Satz («Prüfprotokoll an 1 Stück»), rotes Zeichen am Symbol, daneben das Symbol «Abgeben». Darunter der Feed wie heute, nach Nummer. |
| Feed mit Filter | unverändert |
| Datensatz | rotes Zeichen am Symbol, wenn meine Aufgabe hier ist; im Inhalt das rote Zeichen an der Stelle (am Schritt, an der Nachricht, am Abschnitt) |
| Andere Personen | nichts – woran andere arbeiten, steht nirgends (nur im Log) |
| Personendatensatz | Karte «Kompetenzen»: die abgeleitete Liste, der Admin klickt |
| Auftrag | Felder «Frühestens» · «Spätestens» (§5.6); je Schritt leise die Frist |
| Prozess-Editor | Feld «Wer kann das?» – Vorgabe des Moduls, tauschbar gegen eine aus der Liste |

## 7 · Datenmodell (neu)

```
person_competences  person_object_id, competence (Wort aus domain/competences), is_active, …
task_focus          person_object_id (eindeutig), task_key (eindeutig), since
orders.earliest_on  DATE NULL
orders.latest_on    DATE NULL
Schritt-Konfig      competence (Wahl aus domain/competences, sonst Vorgabe des Moduls)
```
Die Dauern sind eine Ableitung aus `process_log` (keine Spalte); berechnet im Takt, gehalten im
Speicher wie das übrige Abgeleitete.

## 8 · Befähigung

Entschieden: **A** – der Admin gibt eine Kompetenz nur Befähigten. Für die Kranprüfung gibt es eine
eigene Kompetenz in der Liste (§5.2), am Schritt gewählt; damit prüft weiterhin jeder mit «Prüfen» den
Wareneingang.

## 9 · Szenarien

1. **Kranservice:** Offerte → freie Person mit Verkauf; «Zum Kunden» → Logistik; Prüfprotokoll →
   Prüfen; Rechnung → Verkauf.
2. **Mail kommt, alle beschäftigt:** sie wartet. Ihre Frist (2 h) macht sie früh; die nächste freie
   Person mit Kundendienst bekommt sie.
3. **Material fehlt:** keine Aufgabe, bis es da ist.
4. **Lea wird krank:** ihre Aufgabe geht an die nächste freie Person, die es kann; sonst wartet sie.
5. **Warten auf den Kunden:** keine Aufgabe.
6. **Fremde Aufgabe erledigt:** wer dran war, bekommt die nächste.
7. **Eine Person allein:** alles für sie, nach Frist.
8. **Wiederholung entsteht:** ihr erster Schritt ist eine Aufgabe (beantwortet wiederkehr O18).
9. **«Gehen» fehlt:** Aufgabe nur für mich; ist sie dran, steht mein Datensatz oben.
10. **Admin nimmt die letzte Kompetenz:** abgewiesen.

## 10 · Grenzfälle

Schlüssel stabil (Wächter) · Aufgabe kommt wieder (Kunde schreibt nochmals) → neu zugeteilt · Recht
weg → Fokus weg · automatische Schritte → keine Aufgabe, solange niemand von uns handeln muss ·
Externe → nie eine Aufgabe bei uns · viele Stücke: jeder darf bestätigen, zugeteilt bleibt eine Person
· Takt schläft → zugeteilt beim nächsten Lesen.

## 11 · Bewusst NICHT

Kein Aufgaben-Datensatz · keine Liste zum Auswählen · keine Stufen, keine zweite Farbe · keine
Teams · keine Kapazitätsplanung · keine Ranglisten · kein Bereich, keine Karte am Unternehmen, kein
Banner, kein «Du bist dran»-Text · keine Bilder, wer woran arbeitet · kein Hebel von Hand (vorerst) ·
keine KI in der Reihenfolge.

## 12 · Bauplan

| Stufe | Inhalt |
|---|---|
| **A · Eine Liste** | `services/tasks` über alle Quellen (+ Schritt, + Beleg), Frist je Aufgabe, Aufgabe ↔ Hinweis getrennt |
| **B · Kompetenzen** | `domain/tasks.KINDS`, `person_competences`, Karte am Personendatensatz, Regel «nie ohne Person» |
| **C · Dran** | `task_focus`, Zuteilung, Anwesenheit, Dran-Zeile im Feed, rotes Zeichen nur für meins, Abgeben |
| **D · Termin und Plan** | Frühestens/Spätestens am Auftrag, Zahlung liest sie, Wiederholung setzt sie; Dauern aus dem Log, Fristen rückwärts (§5.6) |
| **E · Gesellschaften** | Werk-Kompetenzen am Ort (§5.7) |
| später | Liefertermin vorschlagen (§5.6), Kompetenz «lernt», Handy-Push, Hebel von Hand |

Wächter (je gegen seine Bug-Form): nie zwei Personen an einer Aufgabe · nie zwei Aufgaben an einer
Person · nie zugeteilt ohne Recht oder Kompetenz · nie eine nicht machbare Aufgabe · nie eine
Kompetenz ohne Person · früheste Frist zuerst (Matrix mit vorher notiertem Soll).

## 13 · Entscheide

**Entschieden (10.11.2026)**
- «Dran» – eine Aufgabe je Person, strikt. ✔
- Kein Bereich, keine Unternehmen-Karte, kein Banner, kein Text am Ort – nur das rote Zeichen. ✔
- Feed nach Nummer; zuoberst nur meine eine Aufgabe. ✔
- Abgeben ohne Grund. ✔
- Dringendes geht an die, die es können und frei sind; es unterbricht nicht. ✔
- Kompetenz an einer Stelle (an der Art der Aufgabe); der Admin gibt sie; nie ohne Person. ✔
- Eine Farbe (rot) für «zu tun». ✔
- Nur wer da ist (eingestempelt), bekommt Aufgaben. ✔
- Kein Hebel von Hand – vorerst. ✔

- Befähigung: Weg A; Kranprüfung als eigene Kompetenz. ✔
- Termin steht am Auftrag; die Zahlung liest ihn. ✔
- Sind mehrere frei: wer am längsten frei ist, zuerst. ✔

**Offen (Vorschlag in Klammern)**
- E11 · Kompetenzliste wie §5.2 (11 Stück)? (ja – ergänzen, was fehlt)
- E12 · Termin als zwei Felder «frühestens / spätestens» (vier Fälle)? (ja)
- E13 · Plan rückwärts mit Dauern aus dem Log, «8 von 10» (§5.6)? (ja)
- E14 · Gesellschaften: Werk am Ort der Ware, Büro überall, Zugehörigkeit aus dem Vertrag (§5.7)? (ja)
- E15 · Standardfrist für Kleines (Papier, Angaben, Vorschlag): 1 Arbeitstag? (ja)
- E9 · Woran andere arbeiten, sieht niemand – auch der Admin nicht? (ja)

## 14 · Andere Wege – und wohin es geht

| Weg | Schwäche |
|---|---|
| Liste für alle (Jira, Asana) | Rosinenpicken, Doppelarbeit, Abteilungsdenken |
| Liste von Hand verteilt | einer plant, Listen wachsen |
| Kanban | Pflege, zweite Wahrheit neben dem ERP |
| **Zuteilung nach Kompetenz, eine Sache je Person** (wie Disposition im Service) | wenig Wahl – Ventil: Abgeben, und jeder darf alles tun |

Was gute Systeme heute tun, und was wir davon nehmen:
- **ERP mit Rückwärtsterminierung** (Abacus, proALPHA, SAP): Fristen rückwärts vom Liefertermin – aber
  mit **von Hand gepflegten** Vorgabezeiten, die veralten. Wir nehmen die Rechnung, nicht die Pflege:
  die Dauern kommen aus dem Log.
- **Feinplanung (APS)** mit begrenzter Kapazität: genau, aber schwer und pflegeintensiv. Wir brauchen
  sie nicht: die Zuteilung beim Freiwerden ist die Kapazität – wer nicht frei ist, bekommt nichts.
- **Service-Disposition** (Salesforce Field Service, ServiceTitan): Kompetenz + Gebiet + Zeitfenster.
  Das ist §5.3 + §5.7 + §5.6.
- **Wohin es geht:** Systeme, die aus eigener Geschichte lernen (Dauern, Liefertermine, die halten),
  und Menschen, die nicht planen, sondern ihre eine Sache tun. Genau dahin zielt diese Akte – ohne KI
  in der Regel, mit Zahlen aus dem eigenen Log.

## 15 · Verweise

Bild: https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r · Code: `services/todo.py`, `lib/todo.ts`,
`components/erp/feed-panel.tsx`, `detail-frame.tsx`, `domain/policy.py`, `services/process.py`,
`services/order_view.py`, `services/timekeeping.tasks`.
