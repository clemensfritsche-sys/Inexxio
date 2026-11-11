# Projektakte «Aufgaben» – wer macht was

> **Kopfstatus:** Konzept, Fassung 6 · **nichts gebaut** · Lead: Claude · Entscheid: Clemens
> Fritsche · seit 10.11.2026 · zuletzt 11.11.2026 (ein Datum «bis» oder «ab», Admin sieht alle Zeichen)
> Bild (das ERP, wie es damit aussieht – 1:1, klickbar): https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r
> Diese Akte ist die **eine** Quelle für Ziel, Regeln und Entscheide des Projekts «Aufgaben». Was hier
> nicht als **entschieden** steht, ist nicht entschieden. Frühere Fassungen: Git-Geschichte dieser
> Datei. Vorgänger: `docs/konzept/lernende-firma.md` §3, `docs/konzept/wiederkehr.md` O18.

## 0 · Die ganze Funktion in fünf Sätzen

1. **Eine Aufgabe ist eine Stelle im ERP, an der jemand etwas tun muss** – abgeleitet, nie angelegt,
   nie abgehakt. Erledigt, wenn die Sache erledigt ist; nicht da, solange man wartet.
2. **Jede Aufgabe hat zwei Angaben, beide abgeleitet:** eine **Kompetenz** (vom Modul oder der Art)
   und ein **«fällig ab»**.
3. **Wer frei wird, bekommt die Aufgabe, die am längsten fällig ist und die er kann.** Eine Person, eine
   Aufgabe. Neues bekommt nur, wer eingestempelt ist.
4. **Ich sehe nur meine:** zuoberst im Feed, und im Datensatz das rote Zeichen an der Stelle; dort
   auch «Abgeben». Der Admin sieht zusätzlich das rote Zeichen überall, wo es etwas zu tun gibt.
5. **Gespeichert wird nur dreierlei:** wer was kann, wer woran ist, und am Auftrag ein Datum («bis» oder «ab»).

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
- **Nur meins** – ausser der Admin: er sieht im Feed das rote Zeichen an jedem Datensatz, an dem es
  etwas zu tun gibt (ohne wer, ohne Was). Zuoberst steht auch bei ihm nur seine eigene Aufgabe.
- **Eine Farbe, kein Text.** Das rote Zeichen sagt «hier weiter»; was zu tun ist, sieht man an der
  Stelle selbst. **Eine Aufgabe hat darum keinen Satz** – nur Schlüssel, Stelle, Kompetenz und «fällig
  ab». Kein Code, der Sätze baut.
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

Welche Aufgabe welche Kompetenz braucht, regelt §4.1 (sie folgt dem Ort); im Prozess-Editor («Wer kann
das?») lässt sich die Vorgabe eines Schritts gegen eine aus derselben Liste tauschen. Gespeichert wird nur, wer welche
hat (`person_competences`, vom Admin am Personendatensatz). Die letzte Person einer Kompetenz kann sie
nicht verlieren; der Admin gibt sie nur Befähigten.

### 4.1 · Welche Kompetenz eine Aufgabe braucht – sie folgt dem Ort

Keine Tabelle je Art. **Die Kompetenz folgt der Stelle, an der das rote Zeichen steht** – vier Regeln:

| Das Zeichen steht … | Kompetenz |
|---|---|
| **an einem Prozessschritt** | die des Schritts: Vorgabe des Moduls (`Module.competence`, neben Farbe und Symbol), am Schritt tauschbar gegen eine aus der Liste |
| **an einer fremden Person** (Kunde, Lieferant) | Kommunizieren |
| **an mir selbst** (oder an etwas, das an mich gerichtet ist) | nur ich |
| **an einer eigenen Gesellschaft** | Recht Admin |

Vorgaben der Module: Datenerfassung → Prüfen · Verbrauch → Bauen · Bewegen → Bewegen · Aussondern →
Bewegen · Zahlung → Verrechnen.

Damit sind alle 19 Arten von heute abgedeckt, ohne dass eine einzeln aufgeführt wird:

| Ort | Aufgaben von heute |
|---|---|
| Prozessschritt | Schritt ausführen (alle fünf Module) · Zahlung weiterbringen («Sie sind dran», `voucher_view.situation`) · Mahnen · Dokument nachreichen (an der Zahlung) · gehaltene Stücke klären (an der Datenerfassung) · Wiederholung klären (am ersten Schritt, dort würde der Nachfolger beginnen) |
| fremde Person | Nachricht beantworten (auch Anruf, Erinnerung, Kontaktformular) · Mail neu senden · Vorschlag aus Mail prüfen · Angaben ergänzen |
| ich | eigene Angaben · «Gehen» nachtragen · Nachweis nachreichen · Dokument unterschreiben |
| eigene Gesellschaft | Feiertage · Rechtstexte |

**Keine Aufgaben** (bleiben, wie sie sind): Hinweise ohne Handlung (KI-Deckel, Pause zu kurz); offene
Gespräche und Aufnahmen als Zahl am «+»; alles, worauf wir warten (Kunde, Material, Rückführung).

**Eine neue Funktion**, die etwas zu tun erzeugt, braucht nur ihre Quelle mit dem Ort. Die Kompetenz
ergibt sich; nichts zu pflegen, keine Tabelle, die man vergessen kann.

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
| Schritt eines Auftrags mit «ab» X | **X** – oder seit es zu tun ist, falls später |
| Zeiterfassung | der Tag, der fehlt |

- Keine erfundenen Fristen (kein «5 Tage», kein «1 Tag»). Ohne Termin heisst «jetzt».
- Was noch nicht fällig ist, kommt erst, wenn nichts Fälliges da ist (man arbeitet vor, statt zu warten).
- Eine Regel, eine Sortierung; ein Auftrag mit Termin rückt von selbst nach vorne, sobald sein
  «fällig ab» erreicht ist.

## 7 · Ein Datum am Auftrag – «bis» oder «ab»

**Genau ein Datum, nie zwei, nichts zu rechnen.** Der Mensch wählt, was er weiss:
- **«bis» X** – fertig bis X (Liefertermin). Der Auftrag ist **sofort fällig** und reiht sich nach Alter ein.
  Steht am **Ende** des Prozessbilds.
- **«ab» X** – nicht vor X (Service beim Kunden, Inspektion). Der Auftrag wird **ab X fällig**. Steht am
  **Start** des Prozessbilds.
- **Kein Datum** – so schnell wie möglich, sofort fällig.

Beide Plätze sind die runden Symbole, die das Prozessbild schon hat (`flow-column.Terminal`); keine neue
Karte. Im Entwurf je ein Datumsfeld – wer das eine füllt, leert das andere.
- **Die Zahlung zeigt das Datum** auf Offerte und Zusage, mit seinem Wort («Liefertermin» bzw.
  «Ausführung ab») – gespeichert ist es nur am Auftrag.
- **Wiederholung:** der Nachfolger bekommt das Datum aus ihrem Takt, mit demselben Wort.
- **Beschaffen für einen Auftrag:** der Entwurf schlägt «bis» = das Datum des Auftrags vor, für den
  beschafft wird. Keine Verknüpfung; der Service wartet am Verbrauch, bis das Teil da ist.
- **Verschieben** ist ein Ereignis im Log.

### 7.1 · Was das Log dafür schon festhält

Jedes Stück an jedem Schritt mit Zeitstempel und handelnder Person (`process_log`: `start`, `step`,
`end`, `handover`, `return`, `capture`, `sample`), jede Zahlung mit ihren Stufen (`voucher.action`),
jede Änderung am Datum (Trigger am Auftrag). Dazu neu: `task.assigned` · `task.done` ·
`task.returned` · `task.handed`. Damit lässt sich später jede Dauer nachrechnen – nichts geht verloren,
auch wenn heute nichts daraus vorgeschlagen wird.



## 8 · Was man sieht

| Stelle | Neu |
|---|---|
| Feed ohne Filter | zuoberst **eine** Zeile: der Datensatz meiner Aufgabe, wie jede andere Zeile, mit rotem Zeichen und Rahmen. Darunter der Feed wie heute, nach Nummer. |
| Datensatz | rotes Zeichen am Symbol und an der Stelle. Hover: «Zu tun» bzw. «Niemand da, der das kann» – sonst nichts; am Zeichen der Stelle zusätzlich «Abgeben» |
| Auftrag | ein Datum: «ab» am Start oder «bis» am Ende des Prozessbilds |
| Prozess-Editor | «Wer kann das?» – nur die Auswahl, keine Liste der Personen |
| Personendatensatz | Karte «Kompetenzen» (Admin klickt), Gesellschaft aus dem Personenkreis |

**Nur meins oder überall ein Zeichen?** Entschieden: nur meins. Ausnahme, damit nichts unbemerkt liegt:
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
orders.date_on      DATE NULL      -- das eine Datum
orders.date_kind    TEXT NULL      -- 'until' (bis) | 'from' (ab)
Schritt-Konfig      competence (Wahl aus der Liste, sonst Vorgabe des Moduls)
```
Log: `task.assigned` · `task.done` · `task.returned` · `task.handed`.

## 11 · Szenarien

1. **Kranprüfung** (Beginn Mo, Termin Do): ab Mo fällig; Offerte → Verrechnen, «Teile bereitstellen» →
   Bewegen, Prüfprotokoll → Kranprüfung, Rechnung → Verrechnen.
2. **Ersatzteil aus dem Shop** (ohne Termin): sofort fällig, reiht sich nach Alter ein.
3. **Mail kommt, alle beschäftigt:** fällig seit Eingang; die nächste freie Person mit Kommunizieren.
4. **Deutsches Lager:** Bewegen geht nur an Leute der deutschen Gesellschaft; die Rechnung dazu stellt
   die Schweiz, wenn in Deutschland niemand Verrechnen kann.
5. **Schweisserin in den Ferien:** die Aufgabe wartet; am Datensatz «!» für alle.
6. **Service braucht Teil:** Beschaffung mit Termin = Beginn des Service.
7. **Wiederholung:** Nachfolger mit Beginn und Termin aus dem Takt.
8. **«Gehen» fehlt:** nur meine, fällig seit dem Tag; ist sie dran, steht mein Datensatz oben.

## 11a · Rundblick – was noch zu bedenken ist

- **Die Zahl «zu tun» an fremden Datensätzen fällt weg.** Heute sieht jeder an einem Kunden, dass eine
  Nachricht offen ist; künftig nur, wer dran ist (und «!», wenn es niemand kann). Gewollt – sonst wieder
  «alle sehen es, keiner ist zuständig».
- **Gesperrte Stücke** bleiben ohne Aufgabe (entschieden 11.11.2026).
- **Niemand eingestempelt** (Wochenende): wer am Freitag etwas dran hatte, hat es am Montag noch (§9,
  Satz 2); der Rest wartet, Montag früh bekommt die erste freie Person die am längsten fällige.
- **Person ohne Kompetenz** bekommt nur ihre eigenen Aufgaben. Gewollt.
- **Lange Aufgaben** (Montage über Tage) bleiben die eine Aufgabe; Kleines erledigen andere.
- **Später, ohne Umbau:** Handy-Mitteilung «Du bist dran», Vorschlag für Beginn aus dem Log (KI),
  Gesellschaften (§5), Hebel von Hand.

## 12 · Bewusst nicht

Aufgaben anlegen · Listen zum Auswählen · Stufen, zweite Farbe, Text am Ort · Überblick, wer woran ist
(auch nicht für den Admin) · erfundene Fristen · Dauer je Schritt, Feinplanung · Hebel von Hand
(vorerst) · Gamification · KI in der Reihenfolge.

## 13 · Bauplan

| Stufe | Inhalt |
|---|---|
| A · Eine Liste | `services/tasks` über alle Quellen (+ Schritt, + Beleg), Kompetenz, Gesellschaft, «fällig ab» |
| B · Kompetenzen | Liste in `domain/competences`, `Module.competence`, Regel «folgt dem Ort» (§4.1), Wahl am Schritt, `person_competences`, Karte, «nie ohne Person» |
| C · Dran | `task_focus`, Zuteilung, Anwesenheit, Feed-Zeile, rotes Zeichen nur für meins, «!» für Verwaiste, Abgeben |
| D · Datum | `orders.date_on` + `date_kind`, Zahlung zeigt es, Wiederholung, Beschaffung |

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
- Der Admin sieht alle roten Zeichen im Feed; sonst gleich wie alle. Keine Gamification.
- Mehrere frei: wer am längsten frei ist, zuerst.
- Nur wer da ist, bekommt Aufgaben.
- Acht Kompetenzen (§4). «Fällig ab» statt Fristen, ohne Termin = sofort (§6).
- Gesellschaften vorerst weggelassen (§5).
- Anwesenheit in drei Sätzen (§9).
- Ein Datum am Auftrag, «bis» oder «ab», nie beide, nichts zu rechnen; die Zahlung zeigt es (§7).
- Nur meins; verwaiste Aufgaben (niemand da, der es kann) zeigen «!» für alle (§8).

- Die Kompetenz folgt dem Ort (§4.1); eine Aufgabe hat keinen Satz; Hover nur «Zu tun».

**Offen:** nichts – bereit für Stufe A.

## 15 · Andere Wege

Liste für alle (Jira, Asana): Rosinenpicken, Doppelarbeit · Liste von Hand verteilt: einer plant ·
Kanban: Pflege, zweite Wahrheit · ERP-Feinplanung mit Vorgabezeiten je Schritt: veraltet, pflegeintensiv
· **Zuteilung nach Kompetenz, eine Sache je Person, ein «fällig ab»** (wie Service-Disposition, aber
abgeleitet aus dem ERP): niemand plant, nichts zu pflegen.
