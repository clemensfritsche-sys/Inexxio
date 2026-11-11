# Projektakte «Aufgaben» – wer macht was

> **Kopfstatus:** Konzept, Fassung 5 · **nichts gebaut** · Lead: Claude · Entscheid: Clemens
> Fritsche · seit 10.11.2026 · zuletzt 11.11.2026 (vereinfacht: ein Termin, neun Kompetenzen, Gesellschaft über den Personenkreis)
> Bild (das ERP, wie es damit aussieht – 1:1, klickbar): https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r
> Diese Akte ist die **eine** Quelle für Ziel, Regeln, Modell, Plan und Entscheide des Projekts
> «Aufgaben». Was hier nicht als **entschieden** steht, ist nicht entschieden. Frühere Fassungen
> stehen in der Git-Geschichte dieser Datei. Vorgänger: `docs/konzept/lernende-firma.md` §3 und
> `docs/konzept/wiederkehr.md` O18.

## 0 · Kurzfassung

1. **Eine Aufgabe ist eine Ableitung.** Das ERP weiss, wo etwas zu tun ist. Niemand legt eine
   Aufgabe an oder hakt sie ab; sie verschwindet, wenn die Sache erledigt ist, und es gibt sie
   nicht, solange man wartet.
2. **Neun Kompetenzen, eine Liste im Code:** je Modul eine, dazu drei besondere, am Schritt wählbar.
   Der Admin gibt sie. Eine Kompetenz ohne Person ist unmöglich.
3. **Eine Aufgabe gehört genau einer Person; eine Person hat genau eine Aufgabe.**
4. **Wer frei wird, bekommt die Aufgabe mit der frühesten Frist, die er kann.** Eine Regel, keine
   Stufen. Die Person tut, was zuoberst steht.
5. **Im Feed steht zuoberst meine eine Aufgabe – sonst ändert sich nichts.** Der Feed bleibt nach
   Nummer sortiert. Im Datensatz steht an der Stelle, wo es zu tun ist, das rote Zeichen «zu tun».
   Kein Banner, kein Text, keine Bilder anderer Personen.
6. **Abgeben ist ein Klick am roten Zeichen** (Hover zeigt «Abgeben»), ohne Grund.
8. **Ein Termin oder keiner.** Mit Termin ist alles am Auftrag bis dahin fällig; ohne «so schnell wie
   möglich».
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
- **Eine Sache, eine Stelle.** Die Kompetenzen stehen einmal im Code; der Schritt wählt nur.
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

**Neun Kompetenzen, eine Liste im Code** (`domain/competences.py`). Keine Abteilungen: die ersten
sechs sind die Tätigkeiten, die das ERP tun lässt (je Modul eine, dazu Kommunizieren), die letzten drei
die besonderen, die nicht jeder kann.

| Kompetenz | Vorgabe für |
|---|---|
| Kommunizieren | Nachricht beantworten · Angaben eines Kunden ergänzen · Vorschlag aus Mail prüfen |
| Verrechnen | Zahlung (Offerte, Zusage, Rechnung, Bestellung, Lieferantenrechnung) · Papier freigeben · Geld erfassen · Mahnen · Wiederholung klären |
| Bewegen | Bewegen |
| Bauen | Verbrauch |
| Prüfen | Datenerfassung |
| Aussondern | Aussondern |
| Schweissen | – am Schritt gewählt |
| Elektrik | – am Schritt gewählt (Steuerung, Funk) |
| Kranprüfung | – am Schritt gewählt (nur Befähigte) |
| – nur ich | eigene Zeiterfassung, eigene Angaben |
| – Recht Admin | Gesellschaft pflegen (Feiertage, Rechtstexte) |

**Am Schritt wählbar:** jedes Modul bringt seine Vorgabe mit; im Prozess-Editor lässt sie sich im
Feld «Wer kann das?» gegen eine aus derselben Liste tauschen (Verbrauch: Bauen oder Schweissen). Der
Schritt definiert nichts, er wählt – es bleibt eine Stelle. Eingefroren mit der Freigabe.

Gespeichert wird nur, wer welche hat (`person_competences`, vom Admin am Personendatensatz). **Nie ohne
Person:** die letzte Person einer Kompetenz kann sie nicht verlieren; ein Wächter meldet beim Start
(`core/report`), wenn eine Kompetenz der Liste niemand hat. Eine neue Kompetenz ist eine Zeile Code.

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

**Abgeben:** ein Klick am roten Zeichen im Datensatz (Hover zeigt «Abgeben»); im Feed nicht. Wer abgibt, bekommt dieselbe Aufgabe 30 Minuten nicht wieder.
**Dringendes unterbricht nicht** – es kommt zur nächsten Person, die frei wird und es kann.

### 5.4 · Reihenfolge: früheste Frist zuerst

**Jede Aufgabe hat eine Frist, die früheste kommt zuerst.** Das ist die ganze Regel (Earliest
Deadline First, Jackson 1955: hält Verspätungen am kleinsten; keine Gewichte, kein Lernen in der
Regel selbst, unabhängig von der Grösse).

| Aufgabe | Frist |
|---|---|
| Schritt eines Auftrags | der Termin des Auftrags; ohne Termin: Freigabe + 5 Arbeitstage (§5.6) |
| Nachricht | Eingang + 2 h (wie heute «überfällig») |
| Mahnen | Fälligkeit der Rechnung |
| Zeiterfassung, eigene Angaben | sofort (der Tag, der fehlt) – schnell gemacht |
| Papier, Dokument, Angaben eines Kunden, Vorschlag | Entstehen + 1 Arbeitstag |

Schwäche: die Regel ist so gut wie die Termine. Gesetzt wird nur der Termin, den der Markt vorgibt.

### 5.5 · Wer ist da

Mit Zeiterfassung: wer eingestempelt ist, ohne Absenz heute. Ohne Zeiterfassung: gilt als da. Bei
«Gehen» bleibt die Aufgabe bis zum nächsten «Kommen», ausser ihre Frist ist verpasst oder die Person
hat am nächsten Arbeitstag eine Absenz.

### 5.6 · Termin eines Auftrags

**Ein Feld, zwei Fälle.** Der Auftrag hat einen **Termin** (ein Kalendertag) oder keinen.
- **Mit Termin:** alles an diesem Auftrag ist bis zum Termin zu erledigen – jede seiner Aufgaben hat
  den Termin als Frist. Strikt, ohne Ausnahme.
- **Ohne Termin = so schnell wie möglich:** jede Aufgabe ist 5 Arbeitstage nach der Freigabe fällig.
  So steht ein solcher Auftrag weder hinter allem noch vor allem.

**Eine Stelle:** der Termin steht nur am Auftrag; die Zahlung liest ihn als Liefertermin (Offerte,
Zusage, Papier) – kein Feld im Beleg. Die Wiederholung setzt ihn je Nachfolger aus ihrem Takt.
Verschieben ist ein Ereignis im Log; ist er zugesagt, sagt die Zahlung, dass er sich vom Papier
unterscheidet.

**Beschaffen für einen anderen Auftrag** (Schlauchtrommel für den nächsten Service): ein eigener,
gewöhnlicher Auftrag. Bietet das System ihn an (weil am Verbrauch etwas fehlt), schlägt der Entwurf
**den Termin des Auftrags vor, für den beschafft wird** – der Mensch bestätigt. Keine Verknüpfung, keine
Kette von Terminen; der Service selbst wartet am Verbrauch, bis die Trommel da ist
(«Nichtverfügbarkeit ist kein Zustand»). Ob sie zu uns oder direkt zum Kunden kommt, sagt das Ziel des
Bewegen-Schritts.

**Bewusst nicht (jetzt):** Rückwärtsplanung mit gelernten Dauern (Fassung 4). Bei frei angelegten
Aufträgen, Abweichungen und Service, der mal klein und mal gross ist, sind frühere Dauern kein
verlässlicher Massstab. Der Termin genügt: die Zuteilung holt das Dringendste zuerst. Kommt später
heraus, dass Termine oft knapp werden, ist der erste nächste Schritt der **Liefertermin-Vorschlag**
beim Anbieten – nicht ein Plan je Schritt.

### 5.7 · Mehrere eigene Gesellschaften

- **Zu welcher Gesellschaft eine Person gehört, sagt der Personenkreis der Gesellschaft** – die
  Zuordnung der Person zur Firma (`user_profiles.company_object_id`), die es schon gibt. Ohne
  Zuordnung (Admin): alle.
- **Jede Aufgabe gehört einer Gesellschaft:** ein Auftrag der, die ihn fakturiert (Zahlung), sonst
  der Person, die ihn freigab; eine Nachricht dem Postfach, in dem sie liegt.
- **Eine Regel:** hat die Gesellschaft selbst jemanden mit der Kompetenz, machen es ihre Leute – sonst
  alle, die es können. Was am Ort sein muss, bleibt am Ort (die deutsche Gesellschaft hat eigene
  Leute für Bewegen); was dort niemand kann, wird von selbst geteilt (Rechnungen der deutschen
  Gesellschaft stellt die Schweiz). Keine Einstellung, keine Unterscheidung von Arten.

### 5.8 · Der Admin

Der Admin sieht, wer woran ist – **ohne neue Ansicht:** im Feed zeigt die zweite Zeile jeder
Mitarbeiterin und jedes Mitarbeiters statt Nummer und Status «Dran: …», «frei» oder die Absenz. Nur
der Admin (`policy` «overview»). Keine Zahlen, keine Dauer, keine Rangliste.

### 5.9 · Motivation statt Gamification

Keine Punkte, keine Ranglisten, keine Abzeichen: sie messen Menschen, verleiten zum Rosinenpicken und
grenzen an Überwachung. Was motiviert, ist schon gebaut: **eine Sache statt einer Liste**, und
**Fortschritt, der sich zeigt** – erledigt, und die nächste ist da; ist nichts mehr dran, steht da
«Gerade nichts für dich». Später denkbar, nur für die Person selbst: «heute 7 erledigt» im eigenen
Datensatz.

## 6 · Oberfläche (nur Bestehendes)

| Stelle | Neu |
|---|---|
| Feed ohne Filter | zuoberst **eine** Zeile: der Datensatz meiner Aufgabe, zweite Zeile der Satz, rotes Zeichen am Symbol. Darunter der Feed wie heute, nach Nummer. |
| Feed (Admin) | bei Mitarbeitenden statt Nummer und Status: «Dran: …» · «frei» · Absenz |
| Datensatz | rotes Zeichen am Symbol und an der Stelle, wo es zu tun ist; Hover zeigt «Abgeben» |
| Auftrag | Feld «Termin» (leer = so schnell wie möglich) |
| Prozess-Editor | Feld «Wer kann das?» – Vorgabe des Moduls, tauschbar gegen eine aus der Liste |
| Personendatensatz | Karte «Kompetenzen» (neun, Admin klickt) und die Gesellschaft aus dem Personenkreis |

## 7 · Datenmodell (neu)

```
person_competences  person_object_id, competence (Wort aus domain/competences), is_active, …
task_focus          person_object_id (eindeutig), task_key (eindeutig), since
orders.due_on       DATE NULL
Schritt-Konfig      competence (Wahl aus domain/competences, sonst Vorgabe des Moduls)
```

## 8 · Befähigung

Entschieden: der Admin gibt eine Kompetenz nur Befähigten. Die Kranprüfung ist eine eigene Kompetenz,
am Schritt gewählt; den Wareneingang prüft weiterhin jeder mit «Prüfen».

## 9 · Szenarien

1. **Kranservice:** Offerte → freie Person mit Verrechnen; «Zum Kunden» → Bewegen; Prüfprotokoll →
   Kranprüfung (am Schritt gewählt); Rechnung → Verrechnen.
2. **Mail kommt, alle beschäftigt:** sie wartet. Ihre Frist (2 h) macht sie früh; die nächste freie
   Person mit Kommunizieren bekommt sie.
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
| **B · Kompetenzen** | `domain/competences` (neun, Vorgabe je Modul), Wahl am Schritt, `person_competences`, Karte am Personendatensatz, Regel «nie ohne Person» |
| **C · Dran** | `task_focus`, Zuteilung, Anwesenheit, Dran-Zeile im Feed, rotes Zeichen nur für meins, Abgeben |
| **D · Termin** | `orders.due_on`, Zahlung liest ihn, Wiederholung setzt ihn, Vorschlag beim Beschaffen (§5.6) |
| **E · Gesellschaften** | Personenkreis, Regel §5.7; Admin-Zeile im Feed (§5.8) |
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

- Ein Termin oder keiner; ohne Termin: Freigabe + 5 Arbeitstage. ✔ (Vorschlag, zur Bestätigung)
- Keine Rückwärtsplanung mit gelernten Dauern. ✔
- Gesellschaft über den Personenkreis; keine Unterscheidung Werk/Büro. ✔
- Abgeben am roten Zeichen im Datensatz, nicht im Feed. ✔

**Offen (Vorschlag in Klammern)**
- E11 · Die neun Kompetenzen (§5.2)? (ja)
- E14 · Regel Gesellschaften: eigene Leute zuerst, sonst alle, die es können (§5.7)? (ja)
- E15 · Kleines (Papier, Angaben, Vorschlag): 1 Arbeitstag Frist? (ja)
- E16 · Admin sieht «Dran: …» in den Zeilen der Mitarbeitenden (§5.8)? (ja)
- E17 · Keine Gamification, Fortschritt nur als «die nächste ist da» (§5.9)? (ja)

## 14 · Andere Wege – und wohin es geht

| Weg | Schwäche |
|---|---|
| Liste für alle (Jira, Asana) | Rosinenpicken, Doppelarbeit, Abteilungsdenken |
| Liste von Hand verteilt | einer plant, Listen wachsen |
| Kanban | Pflege, zweite Wahrheit neben dem ERP |
| **Zuteilung nach Kompetenz, eine Sache je Person** (wie Disposition im Service) | wenig Wahl – Ventil: Abgeben, und jeder darf alles tun |

Was gute Systeme heute tun, und was wir davon nehmen:
- **ERP mit Rückwärtsterminierung** (Abacus, proALPHA, SAP): Fristen rückwärts vom Liefertermin – mit
  von Hand gepflegten Vorgabezeiten, die veralten. Für uns zu viel: der Termin genügt (§5.6).
- **Feinplanung (APS)** mit begrenzter Kapazität: genau, aber schwer und pflegeintensiv. Wir brauchen
  sie nicht: die Zuteilung beim Freiwerden ist die Kapazität – wer nicht frei ist, bekommt nichts.
- **Service-Disposition** (Salesforce Field Service, ServiceTitan): Kompetenz + Gebiet + Zeitfenster.
  Das ist §5.3 + §5.7 + §5.6 – ohne Zeitfenster.
- **Wohin es geht:** Systeme, die aus eigener Geschichte lernen (Dauern, Liefertermine, die halten),
  und Menschen, die nicht planen, sondern ihre eine Sache tun. Diese Akte nimmt die zweite Hälfte jetzt
  und die erste (Liefertermin-Vorschlag) später.

## 15 · Verweise

Bild: https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r · Code: `services/todo.py`, `lib/todo.ts`,
`components/erp/feed-panel.tsx`, `detail-frame.tsx`, `domain/policy.py`, `services/process.py`,
`services/order_view.py`, `services/timekeeping.tasks`.
