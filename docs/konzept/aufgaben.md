# Projektakte «Aufgaben» – wer macht was

> **Kopfstatus:** Konzept, Fassung 3 · **nichts gebaut** · Lead: Claude · Entscheid: Clemens
> Fritsche · seit 10.11.2026 · zuletzt 10.11.2026 (zweite Rückmeldung eingearbeitet)
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

`domain/tasks.KINDS`: jede Art Aufgabe nennt **ihre** Kompetenz. Die Kompetenzen sind die Menge, die
dort vorkommt – keine Tabelle, kein Katalog, keine Pflegemaske:

| Kompetenz | Arten |
|---|---|
| Kundendienst | Nachricht beantworten · Angaben eines Kunden ergänzen · Vorschlag aus Mail prüfen |
| Verkauf | Schritt Zahlung (Einnahme) · Papier freigeben · Mahnen · Wiederholung klären |
| Einkauf | Schritt Zahlung (Ausgabe) |
| Logistik | Schritt Bewegen |
| Montage | Schritt Verbrauch |
| Prüfen | Schritt Datenerfassung |
| Qualität | Schritt Aussondern |
| – (nur ich) | eigene Zeiterfassung, eigene Angaben |
| – (Recht Admin) | Gesellschaft pflegen |

Ein neues Modul bringt seine Art mit. Gespeichert wird nur die Zuordnung **Person ↔ Kompetenz**
(`person_competences`), gesetzt vom Admin am Personendatensatz. **Die letzte Person einer Kompetenz
kann sie nicht verlieren** (Regel `competences.drop_problem` ↔ Tor); weil die Menge aus dem Code kommt,
prüft ein Wächter beim Start, dass jede Kompetenz mindestens eine Person hat (sonst Meldung über
`core/report`).

**Offen: Befähigung** (E3). «Prüfen» deckt die Wareneingangskontrolle wie die Kranprüfung. Darf nicht
jeder die Kranprüfung, braucht es eine zweite Angabe – siehe §8.

### 5.3 · Zuteilung

Gespeichert: `task_focus` – je Person höchstens eine Zeile, je Aufgabe höchstens eine Person (zwei
eindeutige Schlüssel). Gerechnet an einer Stelle (`services/tasks.dispatch`), beim Lesen, im Takt und
nach Stempel, Abgeben, Kompetenz-Änderung:
1. Aufräumen: gibt es die Aufgabe nicht mehr → erledigt; fehlt Recht oder Kompetenz, oder ist die
   Person nicht mehr da → frei.
2. Die Freien in der Reihenfolge, wie lange sie frei sind; **jede nimmt die Aufgabe mit der
   frühesten Frist, die sie kann**.
3. Ins Log: `task.assigned` · `task.done` · `task.returned` · `task.handed`.

**Abgeben:** ein Klick an der Dran-Zeile. Wer abgibt, bekommt dieselbe Aufgabe 30 Minuten nicht wieder.
**Dringendes unterbricht nicht** – es kommt zur nächsten Person, die frei wird und es kann.

### 5.4 · Reihenfolge: früheste Frist zuerst

**Jede Aufgabe hat eine Frist, und die früheste kommt zuerst.** Das ist die ganze Regel.

| Aufgabe | Frist |
|---|---|
| Schritt eines Auftrags | Termin des Auftrags (§5.6); ohne Termin: Entstehen + 5 Arbeitstage |
| Nachricht | Eingang + 2 h (wie heute «überfällig») |
| Mahnen | Fälligkeit der Rechnung |
| Papier, Dokument, Angaben, Vorschlag | Entstehen + 5 Arbeitstage |
| Zeiterfassung | der Tag, der fehlt |

Warum das trägt: «Früheste Frist zuerst» ist die bekannte Regel, die verspätete Aufgaben am kleinsten
hält (Earliest Deadline First, Jackson 1955). Sie hat einen Parameter (die Standardfrist), keine
Gewichte und kein Lernen. Sie ist unabhängig von der Grösse der Firma, und eine Aufgabe ohne Termin
wird mit der Zeit von selbst dringend – nichts bleibt liegen. **Schwäche:** sie ist so gut wie die
Termine. Wer Termine zu früh setzt, drängelt vor. Darum hat nur der Auftrag einen Termin, und er ist
die Abmachung mit der Partei.

### 5.5 · Wer ist da

Mit Zeiterfassung: wer eingestempelt ist, ohne Absenz heute. Ohne Zeiterfassung: gilt als da. Bei
«Gehen» bleibt die Aufgabe bis zum nächsten «Kommen», ausser ihre Frist ist verpasst oder die Person
hat am nächsten Arbeitstag eine Absenz.

### 5.6 · Der Termin (Vorschlag, eigenes Thema)

- **Ein Termin gehört dem Auftrag**, eine Spalte, ein Kalendertag (Europe/Zurich, wie die Wiederkehr).
- **Woher:** hat der Auftrag eine Zahlung als Einnahme, ist der Termin der Liefertermin, den die
  Offerte nennt und die Zusage festhält – eingetragen im Auftrag, gelesen vom Papier. Ohne Partei
  setzt ihn, wer den Auftrag freigibt; leer = Standardfrist. Die Wiederholung setzt ihn je
  Nachfolger aus ihrem Takt.
- **Verschieben** ist ein Ereignis im Log (alt → neu). Ist er schon zugesagt, sagt die Zahlung, dass
  er sich vom Papier unterscheidet – wie heute bei einer geänderten Offerte.
- **Jeder Schritt erbt ihn.** Untereinander gleiche Frist → wer länger wartet.

## 6 · Oberfläche (nur Bestehendes)

| Stelle | Neu |
|---|---|
| Feed ohne Filter | zuoberst **eine** Zeile: der Datensatz meiner Aufgabe, zweite Zeile der Satz («Prüfprotokoll an 1 Stück»), rotes Zeichen am Symbol, daneben das Symbol «Abgeben». Darunter der Feed wie heute, nach Nummer. |
| Feed mit Filter | unverändert |
| Datensatz | rotes Zeichen am Symbol, wenn meine Aufgabe hier ist; im Inhalt das rote Zeichen an der Stelle (am Schritt, an der Nachricht, am Abschnitt) |
| Andere Personen | nichts – woran andere arbeiten, steht nirgends (nur im Log) |
| Personendatensatz | Karte «Kompetenzen»: die abgeleitete Liste, der Admin klickt |
| Auftrag | Feld «Termin» (§5.6) |

## 7 · Datenmodell (neu)

```
person_competences  person_object_id, competence (Wort aus domain/tasks.KINDS), is_active, …
task_focus          person_object_id (eindeutig), task_key (eindeutig), since
orders.due_on       DATE NULL
```

## 8 · Befähigung (offen, E3)

Problem: eine Kompetenz je Art reicht, solange jeder, der «Prüfen» kann, auch alles prüfen darf.
Bei einer Kranprüfung stimmt das nicht.

| Weg | Wie | Eine Stelle? |
|---|---|---|
| **A · Nichts** | Der Admin gibt «Prüfen» nur Befähigten | ja – aber dann prüft niemand sonst den Wareneingang |
| **B · Befähigung am Artikel** | Ein Artikel kann sagen «nur befähigte Personen» (ein Häkchen). Dann ist der Artikel selbst die Kompetenz («Kranprüfung (Dienstleistung)»), die Liste je Person kommt daraus | ja – die Befähigung steht am Artikel, sonst nirgends |
| C · Fach am Schritt (Fassung 2) | Ein Name am Schritt im Prozess-Editor | nein – derselbe Name an vielen Schritten |

Vorschlag: **A zum Start, B sobald es gebraucht wird.** C nicht.

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
| **D · Termin** | `orders.due_on`, aus der Zahlung, Wiederholung (§5.6) |
| später | Befähigung am Artikel (§8), Kompetenz «lernt», Handy-Push, Hebel von Hand |

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

**Offen**
- E3 · Befähigung: A zum Start, B bei Bedarf? (§8)
- E4 · Termin wie §5.6? (ja)
- E9 · Woran andere arbeiten, sieht niemand – auch der Admin nicht? (ja; das Log hält es fest)
- E10 · Reihenfolge «früheste Frist zuerst» mit Standardfrist 5 Arbeitstage? (ja)

## 14 · Andere Wege

| Weg | Schwäche |
|---|---|
| Liste für alle (Jira, Asana) | Rosinenpicken, Doppelarbeit, Abteilungsdenken |
| Liste von Hand verteilt | einer plant, Listen wachsen |
| Kanban | Pflege, zweite Wahrheit neben dem ERP |
| **Zuteilung nach Kompetenz, eine Sache je Person** (wie Disposition im Service) | wenig Wahl – Ventil: Abgeben, und jeder darf alles tun |

## 15 · Verweise

Bild: https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r · Code: `services/todo.py`, `lib/todo.ts`,
`components/erp/feed-panel.tsx`, `detail-frame.tsx`, `domain/policy.py`, `services/process.py`,
`services/order_view.py`, `services/timekeeping.tasks`.
