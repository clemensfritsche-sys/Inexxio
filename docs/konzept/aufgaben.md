# Projektakte «Aufgaben» – wer macht was

> **Kopfstatus:** Fassung 13 · **Runde 1 gebaut** (11.11.2026, Branch `claude/aufgaben`, Bericht
> `docs/history/2026-11-11-aufgaben-runde1.md`) · Runde 2 (Datum) offen · Lead: Claude · Entscheid: Clemens
> Fritsche · seit 10.11.2026 · zuletzt 11.11.2026 · Umsetzung in zwei Runden (§12)
> Bild (das ERP, wie es damit aussieht – 1:1, klickbar): https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r
> Diese Akte ist die **eine** Quelle für Ziel, Regeln, Entscheide und Plan des Projekts «Aufgaben». Was
> hier nicht steht, ist nicht entschieden. Der Weg dahin (Fassungen 1–11, verworfene Anläufe) steht in
> der Git-Geschichte dieser Datei. Vorgänger: `docs/konzept/lernende-firma.md` §3 («feste Zuständigkeit
> kommt mit dem Projekt «Aufgaben»»), `docs/konzept/wiederkehr.md` O18.

## 0 · Die ganze Funktion

1. **Eine Aufgabe ist eine Stelle im ERP, an der jemand etwas tun muss** – abgeleitet, nie angelegt, nie
   abgehakt. Erledigt ist sie, wenn die Sache erledigt ist; solange man wartet, gibt es sie nicht.
2. **Jede Aufgabe hat zwei Angaben, beide abgeleitet:** eine **Kompetenz** (folgt dem Ort, §3) und ein
   **Datum** (§5).
3. **Wer frei wird, bekommt die Aufgabe mit dem frühesten Datum, die er darf und kann.** Eine Person hat
   genau eine Aufgabe, eine Aufgabe genau eine Person.
4. **Man sieht nur die eigene:** zuoberst im Feed, und im Datensatz das rote Zeichen an der Stelle. Der
   Admin sieht zusätzlich das rote Zeichen an jedem Datensatz, an dem es etwas zu tun gibt.
5. **Gespeichert wird nur dreierlei:** wer was kann, wer woran ist, und am Auftrag ein Datum.

## 1 · Problem und Ziel

**Heute:** «zu tun» sagt nur *wo* etwas offen ist, nie *wer* es tun soll – eine offene Mail zählt bei
allen, zuständig ist niemand. Die Hauptarbeit (ein Prozessschritt ist dran) zählt nirgends. Es gibt keine
Reihenfolge.

**Ziel:** jede Person weiss jederzeit, was sie jetzt tun soll, und alles, was zu tun ist, hat genau eine
Person – ohne dass jemand plant, verteilt oder nachfragt. Ohne Abteilungen: jeder macht alles, was er kann.
Eine Sache zur Zeit statt einer Liste.

## 2 · Grundsätze

- **Ableitung statt Spalte.** Gespeichert wird nur, was ein Mensch entscheidet.
- **Eine Sache, eine Stelle.** Die Kompetenzen stehen einmal im Code; das Datum nur am Auftrag.
- **Recht ≠ Kompetenz.** Das Recht (`domain/policy`) ist das Tor (darf ich?), die Kompetenz die Zuteilung
  (soll ich es bekommen?). Zugeteilt wird nur, wer darf **und** kann.
- **Ein Fokus.** Die Person tut, was zuoberst steht.
- **Eine Farbe, kein Text.** Das rote Zeichen sagt «hier weiter». Was zu tun ist, sieht man an der Stelle
  selbst – eine Aufgabe trägt darum keinen Satz.
- **Nichts blockiert.** Jeder darf weiterhin alles tun, was er darf. Wer eine fremde Aufgabe erledigt, hat
  sie erledigt.
- **Keine Überwachung, keine Gamification.** Das Log hält fest, wer wann dran war; daraus entsteht keine
  Rangliste und keine Auswertung je Person (CH ArGV 3 Art. 26).

## 3 · Kompetenz

**Acht, eine Liste im Code** (`domain/competences.py`):

| Kompetenz | Vorgabe für |
|---|---|
| Kommunizieren | alles an einer fremden Person (§3.1) |
| Verrechnen | Modul Zahlung |
| Bewegen | Module Bewegen und Aussondern |
| Bauen | Modul Verbrauch |
| Prüfen | Modul Datenerfassung |
| Schweissen · Elektrik · Kranprüfung | nur am Schritt gewählt |

- Jedes Modul nennt seine Vorgabe (`Module.competence`, neben Farbe und Symbol).
- Im Prozess-Editor lässt sich die Vorgabe eines Schritts im Feld «Wer kann das?» gegen eine aus derselben
  Liste tauschen (Verbrauch: Bauen oder Schweissen). Der Schritt wählt, er definiert nichts. Eingefroren
  mit der Freigabe. Keine Liste der Personen dabei.
- Gespeichert wird nur, wer welche hat – **eine Spalte an der Person** (`user_profiles.competences`),
  gesetzt vom Admin als Feld in den Stammdaten (dasselbe PATCH wie jedes Feld, Recht «person.competences»
  = Admin). Keine eigene Tabelle, keine eigene Karte, keine eigene Route. Der Admin gibt sie nur Befähigten.
- **Nie ohne Person:** die letzte Person einer Kompetenz kann sie nicht verlieren
  (`competences.drop_problem` ↔ Tor). Eine neue Kompetenz ist eine Zeile Code.

### 3.1 · Die Kompetenz folgt dem Ort

Keine Tabelle je Art Aufgabe. Die Kompetenz ergibt sich aus der Stelle, an der das rote Zeichen steht:

| Das Zeichen steht … | Kompetenz |
|---|---|
| an einem **Prozessschritt** | die des Schritts |
| an einer **fremden Person** (Kunde, Lieferant) | Kommunizieren |
| an **mir selbst** oder an etwas, das an mich gerichtet ist | nur ich |
| an einer **eigenen Gesellschaft** | Recht Admin |

Eine neue Funktion, die etwas zu tun erzeugt, braucht nur ihre Quelle mit dem Ort – die Kompetenz ergibt
sich, nichts zu pflegen.

## 4 · Was eine Aufgabe ist – alle Quellen

Alle Quellen gibt es heute schon; zwei kommen dazu.

| Ort | Aufgabe | Quelle |
|---|---|---|
| Prozessschritt | Stücke warten am Schritt (alle fünf Module; Verbrauch erst, wenn das Material am Ort liegt) | `order_view` (`waiting`), `StepNeed` – **neu** |
| Prozessschritt | Zahlung: wir sind dran (anbieten, Rechnung stellen oder erfassen, Papier freigeben, bezahlen, erstatten, Partner wählen) | `voucher_view.situation` – **neu** |
| Prozessschritt | Mahnen · Dokument nachreichen (an der Zahlung) | `payment_list.overdue_counts` · `requirements` |
| Prozessschritt | gehaltene Stücke klären (an der Datenerfassung) | `held_units` |
| Prozessschritt | Wiederholung klären (am ersten Schritt) | `loop.todo_items` |
| fremde Person | Nachricht beantworten (auch Anruf, Erinnerung, Kontaktformular) · Mail neu senden · Vorschlag aus Mail prüfen · Angaben ergänzen | `communication`, `handgriff.open_mail_counts`, `people.missing_fields` |
| ich | eigene Angaben · «Gehen» nachtragen · Nachweis nachreichen · Dokument unterschreiben | `people.missing_fields`, `timekeeping.tasks`, Dokumente |
| eigene Gesellschaft | Feiertage · Rechtstexte | `holidays`, `legal` |

**Keine Aufgaben:** Hinweise ohne Handlung – der KI-Deckel meldet sich künftig über `core/report`
(Betriebsmeldung, an einer Stelle), die Pause-Hinweise bleiben in der Zeiterfassung; offene
Gespräche und Aufnahmen – Zahl am «+» wie heute; gesperrte Stücke; alles, worauf wir warten (Kunde,
Material, Rückführung).

Eine Aufgabe besteht nur aus: **Schlüssel** (stabil, z. B. `step:<Auftrag>:<Schritt>`), **Ort**
(Datensatz + Stelle, `data-todo`), **Kompetenz** (oder «nur Person X», oder ein Recht), **Datum**.

## 5 · Das Datum – das Arztpraxis-Modell

**Jede Aufgabe hat ein Datum. Aufgerufen wird das früheste.**

| Aufgabe | ihr Datum |
|---|---|
| alles ohne Datum (Nachricht, Papier, Angaben, Mahnung, Auftrag ohne Datum) | seit wann es zu tun ist – jede Quelle nennt ihren Zeitpunkt (Eingang, Erreichen des Schritts, Fälligkeit der Rechnung); kennt sie keinen, das Anlegedatum des Datensatzes |
| Auftrag «bis» X | X – darf früher getan werden, wenn nichts Früheres ansteht |
| Auftrag «ab» X | X – und nicht vorher (vorher gibt es die Aufgabe nicht) |
| Zeiterfassung | der Tag, der fehlt |

Wie in der Arztpraxis: wer ohne Termin kommt, hat als Datum seine Ankunft; wer einen Termin hat, dessen
Termin. Aufgerufen wird das früheste Datum; «ab» heisst zusätzlich: vorher nicht.

**Am Auftrag steht genau ein Datum – «bis» oder «ab», nie beide, nichts zu rechnen:**
- **«bis» X** – fertig bis X (Liefertermin), am **Ende** des Prozessbilds.
- **«ab» X** – nicht vor X (Service, Inspektion), am **Start** des Prozessbilds.
- **keins** – so schnell wie möglich.

Start und Ende sind die runden Symbole, die das Prozessbild schon hat (`flow-column.Terminal`); keine neue
Karte. Im Entwurf je ein Datumsfeld – wer das eine füllt, leert das andere. Verschieben geht jederzeit
(Ereignis im Log).
- Die **Zahlung zeigt das Datum** auf Offerte und Zusage («Liefertermin» bzw. «Ausführung ab»);
  gespeichert ist es nur am Auftrag.
- Die **Wiederholung** gibt dem Nachfolger das Datum aus ihrem Takt, mit demselben Wort.
- **Beschaffen für einen Auftrag:** bietet das System den Beschaffungsauftrag an, schlägt der Entwurf
  «bis» = das Datum des Auftrags vor, für den beschafft wird. Keine Verknüpfung.

**Grenze, ehrlich:** «bis» sagt, wann es fertig sein muss, nicht, wie lange es dauert. Braucht etwas drei
Tage, setzt der Mensch «bis» früher oder wählt «ab». Später kann das System die Dauer selbst abziehen
(aus dem Log, eher über die KI) – die Regel bleibt, nur das Datum wird «bis minus Dauer».

## 6 · Zuteilung und Anwesenheit

**Zuteilung – eine Schleife** (`services/tasks.dispatch`, unter einer Sperre aus `core/locks`):
1. Aufräumen: gibt es die Aufgabe einer Person nicht mehr → erledigt. Fehlt der Person Recht oder
   Kompetenz, oder hat sie eine Absenz → die Aufgabe ist wieder frei.
2. Die freien Personen, die am längsten frei ist zuerst; jede nimmt die Aufgabe mit dem frühesten Datum,
   die sie darf und kann.
3. Ins Log schreibt die Datenbank selbst (Trigger an `task_focus`) – keine eigenen Ereignisse.
   Im Verlauf eines Datensatzes erscheint das nicht (`history.HIDDEN`).

Gerechnet beim Lesen der Aufgaben, im Takt (alle 5 Minuten) und nach Stempel, Abgeben, Kompetenz-Änderung.

**Anwesenheit – drei Sätze** (aus der Zeiterfassung):
1. **Neues bekommt nur, wer eingestempelt ist.** Wer keine Zeiterfassung hat, gilt als da.
2. **Was ich dran habe, bleibt bei mir** – auch über «Gehen», bis zum nächsten «Kommen».
3. **Ausser ich habe eine Absenz** (Ferien, krank): dann geht es an die Nächste, die es kann.

**Abgeben:** ein Klick am roten Zeichen im Datensatz, ohne Grund. Wer abgibt, bekommt dieselbe Aufgabe erst
wieder, nachdem er eine andere hatte (keine Uhr). **Dringendes unterbricht nicht.** **Kein Hebel von Hand** (vorerst).

## 7 · Was man sieht

| Stelle | Neu |
|---|---|
| Feed ohne Filter | zuoberst **eine** Zeile: der Datensatz meiner Aufgabe, wie jede Zeile, mit rotem Zeichen und Rahmen. Darunter der Feed wie heute, nach Nummer. |
| Feed mit Filter | unverändert |
| Symbol eines Datensatzes | rotes Zeichen, wenn meine Aufgabe hier ist. **Admin:** rotes Zeichen an jedem Datensatz mit Aufgaben. **Alle:** «!» an einer Aufgabe, die niemand Anwesendes kann. |
| Im Datensatz | rotes Zeichen an der Stelle (Schritt, Nachricht, Abschnitt). Hover: «Zu tun» bzw. «Niemand da, der das kann»; am Zeichen der Stelle «Abgeben». |
| Personendatensatz | Feld «Kompetenzen» in den Stammdaten (Admin klickt) |
| Prozess-Editor | «Wer kann das?» |
| Auftrag | ein Datum: «ab» am Start oder «bis» am Ende |

Was heute «zu tun» an jedem Datensatz für alle zählt, fällt weg – gewollt, sonst wieder «alle sehen es,
keiner ist zuständig».

## 8 · Datenmodell (neu)

```
user_profiles.competences  TEXT[]          -- wer was kann (Wörter aus domain/competences)
task_focus                 person_object_id (Schlüssel), task_key (eindeutig, wo nicht leer),
                           since, handed_key, created_at, updated_at
                           -- eine Zeile je Person: task_key leer = frei, since = seit wann so,
                           -- handed_key = zuletzt abgegeben (gilt bis zur nächsten Aufgabe)
orders.date_on             DATE NULL
orders.date_kind           TEXT NULL       -- 'until' (bis) | 'from' (ab)
Schritt-Konfig             competence (Wahl aus der Liste; leer = Vorgabe des Moduls)
```

Was das Log schon festhält – jedes Stück an jedem Schritt mit Zeit und Person (`process_log`), jede
Zahlungsstufe, jede Änderung am Datum – reicht, um später Dauern nachzurechnen.

## 9 · Szenarien

1. **Kranprüfung «bis» Do:** Offerte → Verrechnen, «Teile bereitstellen» → Bewegen, Prüfprotokoll →
   Kranprüfung (am Schritt gewählt), Rechnung → Verrechnen. Datum aller Aufgaben: Do.
2. **Ersatzteil aus dem Shop** (ohne Datum): Datum = seit es zu tun ist; reiht sich nach Ankunft ein.
3. **Mail kommt, alle beschäftigt:** Datum = Eingang; die nächste freie Person mit Kommunizieren.
4. **Jahresinspektion «ab» 1. April:** vorher keine Aufgabe; ab dann normal.
5. **Schweisserin in den Ferien:** die Aufgabe wartet; am Datensatz «!» für alle.
6. **Service braucht Teil:** Beschaffung, vorgeschlagen «bis» = Datum des Service.
7. **Freitag dran, Montag zurück:** die Aufgabe ist noch da (Satz 2).
8. **«Gehen» fehlt:** Aufgabe nur für mich; ist sie dran, steht mein Datensatz oben.
9. **Fremde Aufgabe erledigt:** wer dran war, bekommt die nächste.
10. **Eine Person allein:** alles für sie, frühestes Datum zuerst.

## 10 · Bewusst nicht

Aufgaben anlegen · Listen zum Auswählen · Stufen, zweite Farbe, Text am Ort · Überblick, wer woran ist ·
Fristen, die niemand gesetzt hat · Vorlauf, Dauer je Schritt, Feinplanung · automatischer Vorschlag des
Datums (vorerst) · Gesellschaften (vorerst – nachrüsten ist eine Regel in der Zuteilung) · Hebel von Hand
(vorerst) · gesperrte Stücke als Aufgabe · Gamification · KI in der Reihenfolge.

## 11 · Entscheide (10./11.11.2026)

Alles in §0–§10 ist entschieden. Insbesondere: «Dran» – eine Aufgabe je Person · Feed nach Nummer, zuoberst
die eigene · nur das rote Zeichen, ohne Text · Abgeben ohne Grund · Kompetenz folgt dem Ort, acht
Kompetenzen, nie ohne Person · Arztpraxis-Modell, ein Datum «bis» oder «ab» · Anwesenheit in drei Sätzen ·
Admin sieht alle roten Zeichen · «!» für verwaiste Aufgaben · Gesellschaften vorerst weg.

## 12 · Umsetzung

### 12.1 · Plan in zwei Runden

Jede Runde ist für sich nutzbar und wird auf einem eigenen Branch gebaut, geprüft und erst nach
Freigabe nach `develop` gebracht.

**Runde 1 · «Dran»** – Aufgaben sammeln, Kompetenzen, zuteilen, zeigen. Ohne Datum am Auftrag: jede
Aufgabe hat als Datum «seit es zu tun ist» (das Arztpraxis-Modell gilt schon, nur ohne Termine).

| # | Was | Wo |
|---|---|---|
| 1 | Kompetenzen: Liste, `Module.competence`, `competences.drop_problem` ↔ Tor; ins Vokabular für die Oberfläche | `domain/competences.py`, `domain/modules.py`, `scripts/dump_vocab` |
| 2 | Wahl am Schritt: `competence` in der Schritt-Konfiguration aller Module (gemeinsam), im JSON-Schema beschrieben | `domain/modules.py` (`clean_config`, `config_schema`) |
| 3 | Migration 188: `user_profiles.competences`, Tabelle `task_focus` (volle Spalten, Indizes; Log-Trigger kommt von selbst) | `alembic/versions/188_…` |
| 4 | **Sammeln:** `services/todo` wird `services/tasks.collect` – dieselben Quellen, dazu Prozessschritt und Zahlung; je Aufgabe Schlüssel, Ort, Kompetenz (§3.1), Datum. Hinweise getrennt. | `services/tasks.py` |
| 5 | Zahlung: `situation` sagt strukturiert, ob wir dran sind (ein Feld, kein Lesen des Satzes) | `services/voucher_view.py` |
| 6 | **Zuteilen:** `tasks.dispatch` (§6), Anwesenheit aus `timekeeping`, Abgeben; im Takt | `services/tasks.py`, `services/tick.TASKS` |
| 7 | Zwei Routen: `GET /erp/tasks` ersetzt `GET /erp/todo` (meine Aufgabe und die Zeichen, die ich sehe), `POST /erp/tasks/{key}/hand`. Kompetenzen über das bestehende PATCH der Person. | `routers/…`, `lib/api.ts` |
| 8 | Oberfläche: Zeile zuoberst im Feed, rotes Zeichen (nur meins · Admin alle · «!»), Zeichen an der Stelle mit «Abgeben», Feld «Kompetenzen» in den Stammdaten, «Wer kann das?» im Editor; die alte Zahl «zu tun» fällt weg | `feed-panel`, `detail-frame` (`RecordIcon`, `TodoChip`), `module-card`, `communication`, `process-designer`, `lib/tasks.ts` |
| 9 | Wächter: nie zwei Personen an einer Aufgabe · nie zwei Aufgaben an einer Person · nie ohne Recht oder Kompetenz · nie eine Kompetenz ohne Person · frühestes Datum zuerst · Schlüssel stabil · jede Quelle liefert einen Ort | `tests/` (Matrix mit vorher notiertem Soll) |
| 10 | Ist-Stand in CLAUDE.md, Rundenbericht in `docs/history/` | Doku |

**Runde 2 · «Datum»** – das eine Datum am Auftrag.

| # | Was | Wo |
|---|---|---|
| 11 | Migration: `orders.date_on`, `orders.date_kind`; ändern als eigene Handlung (Log) | `alembic/…`, `services/orders` |
| 12 | Datum der Aufgaben nach §5; «ab» filtert vorher aus | `services/tasks.py` |
| 13 | Datumsfeld am Start («ab») und am Ende («bis») des Prozessbilds, im Entwurf und am laufenden Auftrag | `flow-column.Terminal`, Auftragsentwurf |
| 14 | Zahlung: Datum auf Offerte und Zusage | `services/a4.py`, Beleg-Papiere |
| 15 | Wiederholung: Datum je Nachfolger aus dem Takt; Beschaffung: Vorschlag im Entwurf | `services/loop.py`, Entwurf |
| 16 | Wächter, Doku | `tests/`, CLAUDE.md, `docs/history/` |

### 12.2 · Erster Durchlauf – kritisch geprüft

- **Ein Zeitpunkt «frei seit» ohne Log-Abfrage:** eine Zeile je Person in `task_focus`, die bleibt;
  `task_key` leer heisst frei, `since` sagt seit wann. Kein Suchen im Log für «wer ist am längsten frei».
- **Abgeben ohne zweite Tabelle:** `handed_key` in derselben Zeile.
- **Zahlung:** «Sie sind dran» steht heute als Satz; die Aufgabe darf keinen Satz lesen. Darum ein Feld in
  `situation` (Punkt 5) – klein, aber nötig.
- **Gleichzeitigkeit:** zwei Tabs, Takt und Anfrage zugleich – die Sperre um `dispatch` plus die zwei
  eindeutigen Schlüssel machen eine Doppelvergabe unmöglich.
- **Leistung:** `services/todo` fragt heute schon alle Quellen bei jedem Feed; für zehn Personen genügt
  das. Mehr erst, wenn es gemessen langsam ist.

### 12.3 · Zweiter Durchlauf – noch einfacher?

- **Runde 1 nicht weiter teilen.** Sammeln allein (ohne Zuteilen) wäre unsichtbar; Kompetenzen allein
  hätten keine Wirkung. Erst zusammen tragen sie – darum eine Runde.
- **Kein Umbau des «+».** Gespräche und Aufnahmen bleiben, wie sie sind.
- **Keine neue Seite, keine neue Karte.** Alles andere nutzt Bestehendes (Feed-Zeile,
  `RecordIcon`, `data-todo`, `Terminal`).
- **Runde 2 ist klein** und ändert an Runde 1 nur eine Zeile: woher das Datum kommt.
- Ergebnis: zwei Runden sind das Minimum, das trägt.

### 12.4 · Dritter Durchlauf – nochmals verschlankt (vor dem Start)

| Vorher | Jetzt | Gewinn |
|---|---|---|
| Tabelle `person_competences` | Spalte `user_profiles.competences` | eine Tabelle weniger; Änderungen stehen im Verlauf der Person (das Log schreibt sie) |
| Karte «Kompetenzen» + eigene Route | Feld in den Stammdaten, bestehendes PATCH | keine neue Karte, keine neue Route |
| eigene Log-Ereignisse `task.*` | Trigger an `task_focus` schreibt selbst | kein Code fürs Protokollieren |
| Sperre 30 Minuten nach Abgeben (`handed_at`) | gilt bis zur nächsten Aufgabe (`handed_key`) | keine Uhr |
| KI-Deckel als «zu tun» | Betriebsmeldung über `core/report` | eine Sonderquelle weniger |
| Kompetenz je Art | eine Funktion mit vier Fällen (§3.1) | nichts zu pflegen |

Neu im Code bleiben damit: **eine Tabelle, eine Spalte, zwei Routen, eine Liste von acht Wörtern, ein
Dienst** (`services/tasks`: sammeln + zuteilen) und an der Oberfläche **ein Feld, ein Auswahlfeld, eine
Feed-Zeile** – alles andere nutzt, was da ist.

## 13 · Verweise

Bild: https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r · Code heute: `services/todo.py`, `lib/todo.ts`,
`components/erp/feed-panel.tsx`, `detail-frame.tsx` (`RecordIcon`, `TodoChip`), `domain/policy.py`,
`domain/modules.py`, `services/process.py`, `services/order_view.py`, `services/voucher_view.py`,
`services/timekeeping.py`, `services/tick.py`.
