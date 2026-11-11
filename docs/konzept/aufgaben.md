# Projektakte «Aufgaben» – wer macht was

> **Kopfstatus:** Konzept, Fassung 6 · **nichts gebaut** · Lead: Claude · Entscheid: Clemens
> Fritsche · seit 10.11.2026 · zuletzt 11.11.2026 (neu vereinfacht: ein «fällig ab», Termin + Vorlauf,
> Gesellschaft abgeleitet, acht Kompetenzen)
> Bild (das ERP, wie es damit aussieht – 1:1, klickbar): https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r
> Diese Akte ist die **eine** Quelle für Ziel, Regeln und Entscheide des Projekts «Aufgaben». Was hier
> nicht als **entschieden** steht, ist nicht entschieden. Frühere Fassungen: Git-Geschichte dieser
> Datei. Vorgänger: `docs/konzept/lernende-firma.md` §3, `docs/konzept/wiederkehr.md` O18.

## 0 · Die ganze Funktion in fünf Sätzen

1. **Eine Aufgabe ist eine Stelle im ERP, an der jemand etwas tun muss** – abgeleitet, nie angelegt,
   nie abgehakt. Erledigt, wenn die Sache erledigt ist; nicht da, solange man wartet.
2. **Jede Aufgabe hat drei Angaben, alle abgeleitet:** eine **Kompetenz** (vom Modul oder der Art),
   eine **Gesellschaft** (wo die Ware liegt, sonst das Gebiet der Partei) und ein **«fällig ab»**.
3. **Wer frei wird, bekommt die Aufgabe, die am längsten fällig ist und die er kann** – zuerst aus der
   eigenen Gesellschaft. Eine Person, eine Aufgabe.
4. **Ich sehe nur meine:** zuoberst im Feed, und im Datensatz das rote Zeichen an der Stelle; dort
   auch «Abgeben». Für alle gleich, auch für den Admin.
5. **Gespeichert wird nur dreierlei:** wer was kann, wer woran ist, und am Auftrag Termin und Vorlauf.

## 1 · Problem und Ziel

«Zu tun» sagt heute nur «wo», nie «wer»; die Hauptarbeit (ein Schritt ist dran) zählt nirgends; es
gibt keine Reihenfolge. **Ziel:** jede Person weiss jederzeit, was sie jetzt tun soll, und alles, was zu
tun ist, hat genau eine Person – ohne dass jemand plant, verteilt oder nachfragt. Ohne Abteilungen:
jeder macht alles, was er kann.

## 2 · Grundsätze

- **Ableitung statt Spalte.** Gespeichert wird nur, was ein Mensch entscheidet.
- **Eine Sache, eine Stelle.** Kompetenzen stehen einmal im Code; der Termin nur am Auftrag.
- **Recht ≠ Kompetenz.** Das Recht (`domain/policy`) ist das Tor, die Kompetenz die Zuteilung.
- **Ein Fokus.** Eine Aufgabe je Person; die Person tut, was das System ihr gibt.
- **Nur meins, für alle gleich.** Kein Überblick, wer woran ist – auch nicht für den Admin.
- **Eine Farbe, kein Text.** Das rote Zeichen sagt «hier weiter»; was zu tun ist, sieht man.
- **Nichts blockiert.** Jeder darf weiterhin alles tun, was er darf.
- **Keine Überwachung, keine Gamification.**

## 3 · Ist-Analyse (Stand Code 10.11.2026)

| Quelle heute | Wo | Aufgabe künftig |
|---|---|---|
| offene Nachrichten | `communication.open_counts` | Nachricht beantworten |
| Zeiterfassung | `timekeeping.tasks` | nur die Person selbst |
| überfällige Rechnungen | `payment_list.overdue_counts` | Mahnen |
| Pflichtangaben | `people.missing_fields` | Kunde ergänzen · eigene: nur ich |
| Papiere, erwartete Dokumente | `papers_due` · `requirements` | freigeben · nachreichen |
| Wiederholung | `loop.todo_items` | klären |
| Feiertage, Rechtstexte | `holidays`, `legal` | nur Admin (Recht) |
| Handgriffe aus Mails | `handgriff.open_mail_counts` | Vorschlag prüfen |
| **neu:** Schritt mit wartenden Stücken | `order_view` (`waiting`) | Schritt ausführen |
| **neu:** Zahlung, nächste Handlung von uns | `voucher.situation` | Beleg weiterbringen |
| KI-Deckel 80 % | `todo._cap_item` | Hinweis, keine Aufgabe |

Alle sammelt heute `services/todo` – es wird die eine Quelle der Aufgaben. Einen Liefertermin kennt
das ERP heute nirgends (weder Auftrag noch Beleg).

## 4 · Kompetenz

**Acht, eine Liste im Code** (`domain/competences.py`). Fünf für das, was das ERP tun lässt, drei
besondere, die nicht jeder kann:

| Kompetenz | Vorgabe für |
|---|---|
| Kommunizieren | Nachricht beantworten · Angaben eines Kunden ergänzen · Vorschlag aus Mail prüfen |
| Verrechnen | Zahlung (Offerte bis Rechnung, Bestellung, Lieferantenrechnung) · Papier freigeben · Geld erfassen · Mahnen · Wiederholung klären |
| Bewegen | Bewegen · Aussondern |
| Bauen | Verbrauch |
| Prüfen | Datenerfassung |
| Schweissen · Elektrik · Kranprüfung | am Schritt gewählt |
| – nur ich | eigene Zeiterfassung, eigene Angaben |
| – Recht Admin | Gesellschaft pflegen |

Jedes Modul bringt seine Vorgabe mit; im Prozess-Editor («Wer kann das?») lässt sie sich gegen eine
aus derselben Liste tauschen – der Schritt wählt, er definiert nichts. Gespeichert wird nur, wer welche
hat (`person_competences`, vom Admin am Personendatensatz). Die letzte Person einer Kompetenz kann sie
nicht verlieren; der Admin gibt sie nur Befähigten.

## 5 · Gesellschaft – vorerst weggelassen (Vorschlag)

Solange die Mitarbeitenden an einem Ort arbeiten, braucht die Zuteilung keine Gesellschaft. Kommt eine
zweite Gesellschaft mit eigenen Leuten, wird **eine Regel** in der Zuteilung ergänzt; die Daten dafür
gibt es schon. Der Entwurf dafür bleibt hier stehen:


**Welcher Gesellschaft eine Aufgabe gehört**, folgt aus dem, was das ERP schon weiss – in dieser Folge:
1. **Wo die Ware liegt** – für Schritte, die Stücke scannen (Bewegen, Verbrauch, Datenerfassung,
   Aussondern): die eigene Gesellschaft am Ende der Halter-Kette der wartenden Stücke.
2. **Das Gebiet der Partei** – für alles mit einer Partei (Zahlung, Nachricht, Angaben eines Kunden):
   die Gesellschaft, deren Gebiet das Land der Partei enthält (`sites.company_for_country`, die
   Gebietskarte gibt es schon). Liegt die Ware beim Kunden (Service vor Ort), gilt ebenfalls das Gebiet.
3. **Sonst** die Gesellschaft der Person, die den Auftrag freigab.

**Zu welcher Gesellschaft eine Person gehört:** ihr Personenkreis (`user_profiles.company_object_id`).
Ohne Zuordnung: alle.

**Eine Regel für die Zuteilung:** zuerst die Leute dieser Gesellschaft. Ist dort niemand da, der es
kann, alle anderen, die es können – **ausser die Aufgabe braucht Ware** (Fall 1): dann bleibt sie bei
den Leuten, wo die Ware liegt, und wartet. So bleibt die Arbeit am Ort am Ort, und Büroarbeit teilt sich
von selbst, ohne Einstellung.

## 6 · «Fällig ab» – eine Zahl ordnet alles

**Jede Aufgabe hat ein «fällig ab». Wer frei wird, bekommt die, die am längsten fällig ist.**

| Aufgabe | fällig ab |
|---|---|
| alles ohne Termin (Nachricht, Papier, Angaben, Mahnung, Schritt ohne Termin) | seit es zu tun ist |
| Schritt eines Auftrags mit Termin | **Termin minus Vorlauf** – oder seit es zu tun ist, falls später |
| Zeiterfassung | der Tag, der fehlt |

- Keine erfundenen Fristen (kein «5 Tage», kein «1 Tag»). Ohne Termin heisst «jetzt».
- Was noch nicht fällig ist, kommt erst, wenn nichts Fälliges da ist (man arbeitet vor, statt zu warten).
- Eine Regel, eine Sortierung; ein Auftrag mit Termin rückt von selbst nach vorne, sobald sein
  «fällig ab» erreicht ist.

## 7 · Termin und Vorlauf – am Auftrag

- **Termin** – ein Kalendertag oder leer (= so schnell wie möglich). Alles am Auftrag ist bis dahin
  zu erledigen.
- **Vorlauf** – eine Zahl in Arbeitstagen: wie lange vor dem Termin der Auftrag fällig wird.
  **Vorgeschlagen** aus dem letzten Auftrag desselben Artikels (Freigabe bis Abschluss, aus dem Log –
  eine Zahl, keine Rechnung je Schritt); ohne frühere Aufträge leer = sofort fällig. Der Mensch kann
  ihn ändern. Gerechnet in Arbeitstagen der Gesellschaft (Feiertage gibt es schon).
- **Fällig ab** = Termin − Vorlauf, sichtbar am Auftrag.
- **Die Zahlung zeigt den Termin** auf Offerte und Zusage, als Liefertermin – gespeichert ist er nur am
  Auftrag. Sinnvoll, weil der Termin die ganze Arbeit betrifft, nicht nur das Geld, und weil es Aufträge
  ohne Zahlung gibt (Beschaffung, intern). Wer an der Zahlung den Termin ändert, ändert den des Auftrags.
- **Wiederholung** setzt den Termin je Nachfolger aus ihrem Takt; den Vorlauf übernimmt sie.
- **Beschaffen für einen Auftrag** (Schlauchtrommel für den nächsten Service): bietet das System den
  Beschaffungsauftrag an, weil am Verbrauch etwas fehlt, schlägt der Entwurf als Termin **«fällig ab»
  des Auftrags vor, für den beschafft wird**, als Vorlauf die Lieferzeit vom letzten Mal. Der Mensch
  bestätigt. Keine Verknüpfung; der Service wartet am Verbrauch, bis das Teil da ist.
- **Verschieben** ist ein Ereignis im Log.

Warum so und nicht feiner: eine Zahl je Auftrag hält bei frei angelegten Aufträgen, Abweichungen und
Service, der mal klein und mal gross ist – eine Dauer je Schritt nicht. Wird der Vorschlag oft
geändert, zeigt das Log es; dann erst lohnt mehr.

## 8 · Was man sieht

| Stelle | Neu |
|---|---|
| Feed ohne Filter | zuoberst **eine** Zeile: der Datensatz meiner Aufgabe, zweite Zeile der Satz. Darunter der Feed wie heute, nach Nummer. |
| Datensatz | rotes Zeichen am Symbol und an der Stelle; darüber fahren zeigt «Abgeben» (ein Klick, ohne Grund) |
| Auftrag | Termin · Vorlauf · Fällig ab |
| Prozess-Editor | «Wer kann das?» |
| Personendatensatz | Karte «Kompetenzen» (Admin klickt), Gesellschaft aus dem Personenkreis |

**Nur meins oder überall ein Zeichen?** Vorschlag: nur meins. Ausnahme, damit nichts unbemerkt liegt:
eine Aufgabe, die **niemand Anwesendes** kann (alle mit der Kompetenz abwesend), zeigt ihr rotes
Zeichen am Datensatz für alle – mit «!» statt Zahl und dem Grund im Hover. Für alle gleich.

## 9 · Zuteilung und Anwesenheit

`task_focus`: je Person höchstens eine Zeile, je Aufgabe höchstens eine Person (zwei eindeutige
Schlüssel). Eine Stelle (`services/tasks.dispatch`), beim Lesen, im Takt, nach Stempel, Abgeben und
Kompetenz-Änderung: aufräumen → die Freien, wer am längsten frei ist zuerst → jede nimmt die am
längsten fällige Aufgabe, die sie darf und kann. Wer abgibt, bekommt dieselbe Aufgabe 30 Minuten nicht
wieder. Dringendes unterbricht nicht.

**Anwesenheit – drei Sätze, gelesen aus der Zeiterfassung (gibt es schon):**
1. **Neues bekommt nur, wer eingestempelt ist.** Wer keine Zeiterfassung hat, gilt als da.
2. **Was ich dran habe, bleibt bei mir** – auch über «Gehen» bis zum nächsten «Kommen».
3. **Ausser ich habe eine Absenz** (Ferien, krank): dann geht es weiter an die Nächste, die es kann.

## 10 · Datenmodell (neu)

```
person_competences  person_object_id, competence (Wort aus domain/competences), is_active, …
task_focus          person_object_id (eindeutig), task_key (eindeutig), since
orders.due_on       DATE NULL      -- Termin
orders.lead_days    INT NULL       -- Vorlauf in Arbeitstagen
Schritt-Konfig      competence (Wahl aus der Liste, sonst Vorgabe des Moduls)
```
Log: `task.assigned` · `task.done` · `task.returned` · `task.handed`.

## 11 · Szenarien

1. **Kranprüfung** (Termin Do, Vorlauf 3): ab Mo fällig; Offerte → Verrechnen, «Teile bereitstellen» →
   Bewegen, Prüfprotokoll → Kranprüfung, Rechnung → Verrechnen.
2. **Ersatzteil aus dem Shop** (ohne Termin): sofort fällig, reiht sich nach Alter ein.
3. **Mail kommt, alle beschäftigt:** fällig seit Eingang; die nächste freie Person mit Kommunizieren.
4. **Deutsches Lager:** Bewegen geht nur an Leute der deutschen Gesellschaft; die Rechnung dazu stellt
   die Schweiz, wenn in Deutschland niemand Verrechnen kann.
5. **Schweisserin in den Ferien:** die Aufgabe wartet; am Datensatz «!» für alle.
6. **Service braucht Teil:** Beschaffung mit Termin = «fällig ab» des Service, Vorlauf = Lieferzeit.
7. **Wiederholung:** Nachfolger mit Termin aus dem Takt, Vorlauf übernommen.
8. **«Gehen» fehlt:** nur meine, fällig seit dem Tag; ist sie dran, steht mein Datensatz oben.

## 12 · Bewusst nicht

Aufgaben anlegen · Listen zum Auswählen · Stufen, zweite Farbe, Text am Ort · Überblick, wer woran ist
(auch nicht für den Admin) · erfundene Fristen · Dauer je Schritt, Feinplanung · Hebel von Hand
(vorerst) · Gamification · KI in der Reihenfolge.

## 13 · Bauplan

| Stufe | Inhalt |
|---|---|
| A · Eine Liste | `services/tasks` über alle Quellen (+ Schritt, + Beleg), Kompetenz, Gesellschaft, «fällig ab» |
| B · Kompetenzen | `domain/competences`, Wahl am Schritt, `person_competences`, Karte, «nie ohne Person» |
| C · Dran | `task_focus`, Zuteilung, Anwesenheit, Feed-Zeile, rotes Zeichen nur für meins, «!» für Verwaiste, Abgeben |
| D · Termin und Vorlauf | `orders.due_on`, `orders.lead_days`, Vorschlag aus dem Log, Zahlung zeigt ihn, Wiederholung, Beschaffung |

Wächter (je gegen seine Bug-Form): nie zwei Personen an einer Aufgabe · nie zwei Aufgaben an einer
Person · nie ohne Recht oder Kompetenz · Ware-Aufgaben nie an eine andere Gesellschaft · nie eine
Kompetenz ohne Person · am längsten fällig zuerst (Matrix mit vorher notiertem Soll).

## 14 · Entscheide

**Entschieden (10./11.11.2026)**
- «Dran»: eine Aufgabe je Person; die Person tut, was zuoberst steht.
- Feed nach Nummer, zuoberst nur meine eine Aufgabe; im Datensatz nur das rote Zeichen, ohne Text.
- Abgeben am roten Zeichen, ohne Grund. Dringendes unterbricht nicht. Kein Hebel von Hand (vorerst).
- Kompetenzen einmal im Code, am Schritt wählbar; der Admin gibt sie nur Befähigten; nie ohne Person.
- Aussondern gehört zu Bewegen.
- Kein Überblick für den Admin; alle gleich. Keine Gamification.
- Mehrere frei: wer am längsten frei ist, zuerst.
- Nur wer da ist, bekommt Aufgaben.
- Acht Kompetenzen (§4). «Fällig ab» statt Fristen, ohne Termin = sofort (§6).

**Offen (Vorschlag in Klammern)**
- E21 · Gesellschaften vorerst weglassen (§5)? (ja – nachrüsten ist eine Zeile in der Zuteilung, kein neues Datenfeld)
- E23 · Termin + Vorlauf am Auftrag, Vorlauf vorgeschlagen aus dem letzten Mal; die Zahlung zeigt ihn (§7)? (ja)
- E24 · Nur meins; verwaiste Aufgaben (niemand da, der es kann) zeigen «!» für alle (§8)? (ja)

## 15 · Andere Wege

Liste für alle (Jira, Asana): Rosinenpicken, Doppelarbeit · Liste von Hand verteilt: einer plant ·
Kanban: Pflege, zweite Wahrheit · ERP-Feinplanung mit Vorgabezeiten je Schritt: veraltet, pflegeintensiv
· **Zuteilung nach Kompetenz, eine Sache je Person, ein «fällig ab»** (wie Service-Disposition, aber
abgeleitet aus dem ERP): niemand plant, nichts zu pflegen.
