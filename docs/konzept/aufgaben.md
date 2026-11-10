# Projektakte «Aufgaben» – wer macht was

> **Kopfstatus:** Konzept · **nichts gebaut** · Lead: Claude · Entscheid: Clemens Fritsche ·
> seit 10.11.2026
> Bild (das ERP, wie es damit aussieht – 1:1, klickbar): https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r
> Diese Akte ist die **eine** Quelle für Ziel, Regeln, Modell, Plan und Entscheide des Projekts
> «Aufgaben». Was hier nicht als **entschieden** steht, ist nicht entschieden. Das Bild zeigt, die
> Akte hält fest. Vorgänger: `docs/konzept/lernende-firma.md` §3 («feste Zuständigkeit kommt mit
> dem Projekt «Aufgaben»») und `docs/konzept/wiederkehr.md` O18.

## 0 · Kurzfassung (zum Prüfen)

1. **Eine Aufgabe ist eine Ableitung, keine Zeile.** Das ERP weiss heute schon, wo etwas zu tun
   ist (ein Prozessschritt hat Stücke, eine Nachricht ist offen, ein Papier steht an …). Diese
   Stellen werden zu **einer** Liste «Aufgaben». Niemand legt eine Aufgabe von Hand an, niemand
   hakt sie ab: sie verschwindet, sobald die Sache erledigt ist.
2. **Kompetenz statt Abteilung.** Jede Person hat Kompetenzen («kann Kranprüfung», «kann
   Offerten»), vergeben vom Admin. Jede Aufgabe verlangt höchstens **eine** Kompetenz. Wer sie
   hat, kann die Aufgabe bekommen – egal, was er sonst macht.
3. **Eine Aufgabe gehört genau einer Person. Eine Person hat genau eine Aufgabe: «Dran».**
   Beides steht als Regel in der Datenbank (zwei eindeutige Schlüssel) – eine Doppelvergabe ist
   unmöglich, nicht verboten.
4. **Zugeteilt wird beim Freiwerden (Pull).** Wird eine Person frei (Aufgabe erledigt, «Kommen»,
   abgegeben), bekommt sie die **oberste** Aufgabe, die sie kann. Der Rest wartet im Topf
   «Alle Aufgaben», für alle sichtbar.
5. **Die Reihenfolge rechnet das System** – erklärbar, in drei Stufen: **dringend** (eine Frist
   ist vorbei) → **Termin** (früher zuerst) → **wartet am längsten**. Ein einziger Handgriff von
   Hand: **«Vorziehen»** (mit Grund, im Log).
6. **Gezeigt wird im Feed, keine neue Maske.** Ein Filter «Aufgaben» im Feed, oben die eine Karte
   «Dran», am Datensatz eine Leiste «Du bist dran». «Zu tun» heisst künftig «Aufgaben».
7. **Nichts blockiert.** Jeder darf im ERP jederzeit alles tun, was er darf – die Zuteilung ist
   Orientierung, keine Sperre. Wer eine fremde Aufgabe erledigt, hat sie erledigt.

## 1 · Problem

- **«Zu tun» zählt am Ding, nicht bei der Person.** Die Zahl am Symbol sagt: «an diesem Auftrag,
  dieser Person, dieser Gesellschaft ist etwas offen». Sie sagt nicht, **wer** es tun soll. Eine
  offene Mail zählt beim Kunden **und** bei jedem Mitarbeitenden, der im Verlauf steht – alle
  sehen sie, keiner ist zuständig.
- **Die Hauptarbeit fehlt in «zu tun».** Dass an einem Auftrag ein Prozessschritt dran ist
  (Stücke warten an einer Datenerfassung, an einem Bewegen), zählt heute **nirgends** – man muss
  den Auftrag öffnen. Dabei sind Aufträge der Hauptweg, wie im Unternehmen etwas getan wird.
- **Keine Reihenfolge.** Was zuerst? Heute entscheidet, wer zuerst hinschaut.
- **Abteilungsdenken droht, sobald man Zuständigkeit «nach Stelle» baut.** Genau das soll nicht
  entstehen: «Mein Job ist X, alles andere nicht.»
- **Zehn Dinge gleichzeitig** heisst: zehn Dinge halb. Wechseln kostet Zeit und Fehler.

## 2 · Ziel

**Jede Person weiss jederzeit, was sie jetzt tun soll – und alles, was zu tun ist, hat genau eine
Person. Ohne dass jemand plant, verteilt oder nachfragt.**

Messpunkte (nach rund drei Monaten, einmal von Hand aus dem Log):

1. **Keine Aufgabe ohne Person**, die länger als eine Stunde frei im Topf liegt, während jemand
   mit der Kompetenz frei ist.
2. **Nichts Überfälliges unbemerkt:** eine dringende Aufgabe ist binnen 15 Minuten bei jemandem.
3. **Kein Verteilen von Hand:** «Vorziehen» höchstens ein paar Mal pro Woche.
4. **Keine neue Insel:** keine neue Maske, kein neuer Datensatztyp – Feed und Datensatz genügen.

## 3 · Grundsätze

- **Aufgabe = Ableitung.** Wo etwas zu tun ist, weiss die Quelle (Prozess, Kommunikation,
  Zahlung, Zeiterfassung …). Die Aufgabenliste speichert davon **nichts** – sie fragt die Quellen
  (wie heute `services/todo`). Erledigt ist, wenn die Quelle nichts mehr meldet. Keine zweite
  Wahrheit, kein Abhaken.
- **Gespeichert wird nur, was ein Mensch entscheidet oder was nicht abzuleiten ist:** wer welche
  Kompetenz hat · welche Kompetenz eine Aufgabe verlangt · wer gerade dran ist · was vorgezogen
  wurde.
- **Recht ≠ Kompetenz.** Das Recht (`domain/policy`) ist das **Tor**: darf ich das? Die Kompetenz
  ist die **Zuteilung**: soll ich das bekommen? Zugeteilt wird nur, wer **darf und kann**.
  «Admin» ist ein Recht, keine Kompetenz – ein Admin bekommt Aufgaben wie jeder andere, nach
  seinen Kompetenzen.
- **Jeder macht alles, was er kann.** Es gibt keine Abteilungen, keine Teams, keine Rollen
  ausser den drei Zugangsrollen. Wer eine Kompetenz hat, gehört für diese Aufgaben dazu.
- **Ein Fokus.** Eine Person hat genau eine Aufgabe «Dran». Mehr zeigt das System ihr nicht an
  erster Stelle – alles andere ist im Topf und läuft nicht weg.
- **Das System bietet an, der Mensch entscheidet** (Leitbild). Zuteilung ist ein Angebot; jeder
  kann abgeben, jeder kann jede Aufgabe, die er darf, sofort selbst erledigen.
- **Erklärbar statt klug.** Die Reihenfolge ist eine feste Regel in drei Stufen, kein Score und
  keine KI. Jede Aufgabe sagt im Hover, **warum** sie dort steht und **warum** sie bei dieser
  Person ist.
- **Keine Überwachung.** Das Log hält fest, wer wann dran war (es hält ohnehin alles fest). Daraus
  entsteht **keine** Rangliste und keine Leistungsauswertung je Person (CH ArGV 3 Art. 26:
  Systeme zur Verhaltensüberwachung am Arbeitsplatz sind verboten). Ausgewertet werden
  Durchlaufzeiten von Aufgaben und Aufträgen, nicht von Menschen.

## 4 · Ist-Analyse (Stand Code 10.11.2026)

**Was es schon gibt und wiederverwendet wird**

| Baustein | Wo | Rolle künftig |
|---|---|---|
| «zu tun» – sammelt offene Dinge je Datensatz | `services/todo.py` → `GET /erp/todo`, `lib/todo.ts`, Zahl am `RecordIcon` | wird **die Quelle der Aufgaben** (je Eintrag zusätzlich Art und Schlüssel) |
| Offene Nachrichten, überfällig nach 2 h | `communication.open_counts` | Aufgabenart «Nachricht beantworten» |
| Zeiterfassung: «Gehen» fehlt, Nachweis fällig | `timekeeping.tasks` | **persönlich** (nur die Person selbst) |
| Überfällige Rechnungen | `payment_list.overdue_counts` | «Mahnen» |
| Pflichtangaben fehlen | `people.missing_fields` | «Stammdaten ergänzen» |
| Papiere stehen an (AB, Quittung) | `voucher_money.papers_due` | «Papier prüfen und freigeben» |
| Erwartete Dokumente | `requirements.of_vouchers` | «Dokument nachreichen» |
| Wiederholung wartet | `loop.todo_items` | «Wiederholung klären» |
| Feiertage, Rechtstexte fehlen | `holidays.holiday_tasks`, `legal` | «Gesellschaft pflegen» (nur Admin darf) |
| Handgriffe aus Mails | `handgriff.open_mail_counts` | «Vorschlag prüfen» |
| Prozessschritt hat wartende Stücke | `order_view` (`waiting`, `waiting_for`), `process.confirm_step` | **neu als Quelle**: «Schritt ausführen» |
| Zahlung: nächste Handlung von uns | `voucher.situation` (`primary`, `can`) | **neu als Quelle**: «Beleg weiterbringen» |
| Anwesenheit | Zeiterfassung (Stempel, Absenzen) | wer gerade zugeteilt werden kann |
| Rechte | `domain/policy.RULES` (`may`) | das Tor vor jeder Zuteilung |
| Log | `log` (Trigger), `services/log.event` | Ereignisse `task.*`, Geschichte jeder Aufgabe |
| Sprung zur Stelle | `jumpToTodo` (`data-todo`) | Klick auf «Dran» springt dorthin |

**Was fehlt**
- Eine Antwort auf **«wer?»** (heute nur «wo?»).
- Der **Prozessschritt** als Aufgabe (die wichtigste Quelle fehlt).
- Kompetenzen, Termin am Auftrag, Zuteilung, Reihenfolge.
- Eine Trennung **Aufgabe ↔ Hinweis**: der KI-Deckel bei 80 % ist eine Auskunft, keine Aufgabe.

## 5 · Begriffe

| Wort | Bedeutung |
|---|---|
| **Aufgabe** | Etwas, das ein Mensch mit einer Handlung im ERP erledigen kann – abgeleitet aus einer Quelle. Hat einen festen **Schlüssel**, eine **Art**, einen **Ort** (Datensatz + Stelle) und höchstens eine **Kompetenz**. |
| **Art** | Was für eine Aufgabe (Schritt ausführen, Nachricht beantworten, Papier freigeben …) – fester Katalog im Code (`domain/tasks.KINDS`), wie `MODULES`. |
| **Hinweis** | Etwas, das man wissen soll, aber nicht «erledigen» kann (KI-Deckel, Pause zu kurz). Bleibt als Zahl am Datensatz, kommt **nicht** in den Topf. |
| **Kompetenz** | Etwas, das eine Person kann (Wissen, das sie umsetzen kann). Ein Name, vom Admin gepflegt. |
| **Dran** | Die **eine** Aufgabe, die einer Person gerade zugeteilt ist. |
| **Topf** | Alle Aufgaben, die gerade niemandem zugeteilt sind – sortiert. Im Feed «Alle Aufgaben». |
| **Persönlich** | Aufgaben, die nur eine bestimmte Person erledigen kann (eigene Zeiterfassung, eigene Stammdaten). Sie gehen nie in den Topf und belegen «Dran» nicht. |
| **Frei** | Eine Person ist anwesend und hat nichts «Dran». |

Wort im ERP: «Zu tun» wird **«Aufgaben»**. Die Person sieht **«Dran»**. Das ERP sagt heute schon,
ein Modul sei «dran» – dasselbe Wort, dieselbe Bedeutung: jetzt ist es an der Reihe.

## 6 · Das Modell

### 6.1 · Die Aufgabe (abgeleitet)

Jede Quelle liefert Zeilen dieser Form (eine Erweiterung von `TodoItem`):

```
key        fester Schlüssel, z. B. step:<Auftrag>:<Schritt> · msg:<Person>:<Betreff>
           · paper:<Beleg>:<Art> · dunning:<Rechnung> · loop:<Auftrag> · field:<Person>:<Feld>
kind       Art aus domain/tasks.KINDS
object_id  der Datensatz, an dem man es tut (Sprungziel)
anchor     die Stelle darin (data-todo)
label      ein Satz: «Prüfprotokoll an 1 Stück», «Antwort an Hans Bachmann»
competence höchstens eine Kompetenz (aus Schritt oder Art), sonst keine
since      seit wann sie getan werden kann (für «wartet am längsten»)
due        Termin, falls es einen gibt
overdue    ist eine Frist vorbei? (rot)
for_person nur bei persönlichen Aufgaben: wessen
rule       welches Recht nötig ist (policy-Schlüssel), Vorgabe «erp»
```

**Nur was jetzt getan werden kann, ist eine Aufgabe** («Nichtverfügbarkeit ist kein Zustand»):
fehlt Material am Ort (`StepNeed`), ist der Schritt gesperrt (Rückführung ausstehend), wartet die
Zahlung auf die Partei – dann gibt es **keine** Aufgabe. Sie entsteht von selbst, sobald es geht,
und `since` beginnt dann.

**Körnung:** eine Aufgabe je **(Auftrag, Schritt)**, nicht je Stück – 20 Stücke an einer
Endkontrolle sind eine Aufgabe «Endkontrolle an 20 Stück». Eine Nachricht je **Betreff** (das
Anliegen IST der Betreff). Ein Papier je Beleg und Art.

### 6.2 · Arten (erster Katalog)

| Art | Quelle | Kompetenz woher | persönlich? |
|---|---|---|---|
| Schritt ausführen (je Modultyp) | Prozess: Stücke warten am Schritt | **am Schritt** (im Prozess-Editor gesetzt), sonst Vorgabe der Art | nein |
| Beleg weiterbringen | Zahlung: `situation.primary` ist eine Handlung von uns | am Schritt, sonst Vorgabe | nein |
| Papier prüfen und freigeben | `papers_due` | Vorgabe der Art | nein |
| Dokument nachreichen | `requirements` | Vorgabe der Art | nein |
| Nachricht beantworten | offene Nachricht | Vorgabe der Art | nein |
| Mahnen | überfällige Rechnung | Vorgabe der Art | nein |
| Wiederholung klären | `loop` wartet / geht nicht mehr | Vorgabe der Art | nein |
| Vorschlag prüfen | offener Handgriff aus Mail | Vorgabe der Art | nein |
| Stammdaten ergänzen (Kunde) | `missing_fields` einer Partei | Vorgabe der Art | nein |
| Stammdaten ergänzen (selbst) | `missing_fields` an mir | – | **ja** |
| Zeiterfassung: «Gehen» fehlt, Nachweis | `timekeeping.tasks` | – | **ja** |
| Gesellschaft pflegen (Feiertage, Rechtstexte) | `holidays`, `legal` | Vorgabe; Recht `admin` | nein |

Die **Vorgabe je Art** stellt der Admin an **einer** Stelle ein (Karte «Aufgaben» am Betreiber):
Art → Kompetenz oder «jeder». Ohne Einstellung: jeder Mitarbeitende.

### 6.3 · Kompetenz

- **Ein Katalog**, gepflegt vom Admin: Name (eindeutig), aktiv ja/nein. Beispiele für INEXXIO:
  Kranprüfung · Montage Kran · Schweissen · Trommeltausch · Offerten & Verkauf · Einkauf ·
  Buchhaltung · Kundendienst (Mail, Telefon).
- **Zuordnung je Person**: «kann» – gesetzt vom Admin am Personendatensatz (Karte «Aufgaben &
  Kompetenzen»). Jede Änderung steht im Log (der Trigger schreibt sie ohnehin).
- **Eine Aufgabe verlangt höchstens eine Kompetenz.** Braucht ein Schritt zwei Dinge, ist das
  eine eigene Kompetenz («Prüfung Hubwerk») – das hält die Regel einfach und die Zuteilung
  eindeutig.
- **Am Prozessschritt** steht die Kompetenz im Editor (ein Feld «Wer kann das?», Vorgabe aus dem
  Artikel) und wird mit der Freigabe eingefroren wie alles am Auftrag. Darunter steht, **wie
  viele Personen** das heute können («3 Personen») – null ist eine Warnung, kein Fehler.

### 6.4 · Zuteilung (Dispatcher)

Gespeichert: **eine Tabelle `task_focus`** – je Person höchstens eine Zeile
(`person_object_id` eindeutig), je Aufgabe höchstens eine Person (`task_key` eindeutig), dazu
`since` und `how` (zugeteilt · selbst genommen · vom Admin). Damit sind die zwei Kernregeln
**Schlüssel der Datenbank** und können nicht verletzt werden.

**Wann wird zugeteilt?** Immer, wenn sich etwas ändert, das es betrifft – gerechnet an **einer**
Stelle (`services/tasks.dispatch`), aufgerufen:
- beim Lesen der Aufgaben (`GET /erp/tasks`, jeder offene Feed fragt ohnehin),
- im Takt (alle 5 Minuten, wie `loop`),
- nach «Kommen», «Gehen», «Abgeben», «Vorziehen».

**Der Ablauf (deterministisch, erklärbar):**
1. Alle Aufgaben aus den Quellen holen. Persönliche beiseite (sie gehen direkt an ihre Person).
2. **Aufräumen:** eine `task_focus`-Zeile, deren Aufgabe es nicht mehr gibt → **erledigt**
   (Ereignis `task.done`), Zeile weg. Hat die Person das Recht oder die Kompetenz verloren, ist
   sie abwesend, oder ist die Aufgabe dringend und die Person nicht eingestempelt → zurück in den
   Topf (`task.returned`, mit Grund).
3. **Freie Personen** bestimmen: Personal, anwesend (§6.6), ohne «Dran».
4. Den Topf **sortieren** (§6.5) und von oben nach unten durchgehen: für jede Aufgabe die freien
   Personen, die **dürfen und können**. Gibt es welche → die mit den **wenigsten anderen
   passenden Aufgaben im Topf** bekommt sie (so bleiben Spezialisten frei für das, was nur sie
   können); bei Gleichstand, wer **länger frei** ist; dann die kleinere Objektnummer.
5. Ereignis `task.assigned` (Person, Aufgabe, Grund).

**Selbst nehmen:** Jeder Freie kann eine Aufgabe aus dem Topf nehmen, die er darf und kann
(«Übernehmen»). Wer schon etwas «Dran» hat, gibt das dafür zuerst ab – ein Knopf, zwei Schritte im
Log.

**Abgeben:** jederzeit, mit einem Satz Grund («warte auf Rückruf», «brauche Hilfe»). Der Satz
geht als **interne Nachricht** in den Verlauf des Datensatzes (Kommunikation – kein neues
Feld), die Aufgabe zurück in den Topf, die Person bekommt sofort die nächste. Wer abgibt, bekommt
dieselbe Aufgabe in den nächsten 30 Minuten nicht wieder.

**Vom Admin zuweisen:** der Admin kann eine Aufgabe einer bestimmten Person geben. Hat sie schon
etwas «Dran», wird das **reserviert** («als Nächstes für …», gespeichert beim Vorziehen §6.5) –
ihr Fokus wird nie unterbrochen.

**Keine Person kann es:** die Aufgabe bleibt im Topf mit dem Zeichen «niemand kann das» und geht
an den **Admin** (der Admin kann alles zuweisen und jede Kompetenz vergeben). Sie liegt nie still.

### 6.5 · Reihenfolge

Eine Regel, drei Stufen, in dieser Folge:

1. **Vorgezogen** (von Hand, §unten) – in der Reihenfolge des Vorziehens.
2. **Dringend** – eine Frist ist vorbei: Nachricht über 2 h offen, Rechnung überfällig,
   Termin überschritten, Nachweis fällig ab `URGENT_DAYS`. Rot. Untereinander: am längsten
   überfällig zuerst.
3. **Termin nah** – Termin in den nächsten **5 Arbeitstagen**, früherer zuerst.
4. **Der Rest** – wartet am längsten zuerst (`since`). Ein Termin, der weiter weg liegt, zählt
   hier wie keiner – sonst stünde eine Sache für März vor einer, die seit einer Woche wartet.

**Woher kommt ein Termin?** Neu: der **Auftrag hat einen optionalen Termin** («fertig bis»,
Kalendertag Europe/Zurich, wie in der Wiederkehr). Gesetzt im Entwurf, verschiebbar am laufenden
Auftrag (Ereignis im Log, mit Grund) – er ist eine Abmachung, kein Teil des eingefrorenen
Prozesses. Jeder Schritt des Auftrags erbt ihn. Andere Termine kommen aus ihrer Quelle
(Fälligkeit der Rechnung, Gültigkeit der Offerte, Frist des Nachweises).

**Von Hand: «Vorziehen»** – der einzige Hebel. Jeder Mitarbeitende kann eine Aufgabe vorziehen,
mit **Pflicht-Grund** («Kunde steht still»). Sie kommt nach oben, bis sie erledigt ist. Der Grund
steht am Datensatz im Verlauf (interne Nachricht) und im Hover. Zurücknehmen kann es jeder. Keine
Prioritätszahlen, kein Ziehen in einer Liste: wo alles «Prio 1» ist, ist nichts Prio 1.

### 6.6 · Anwesenheit

- **Mit Zeiterfassung** (Vertrag vorhanden): zugeteilt wird nur, wer **eingestempelt** ist. Wer
  heute eine Absenz hat (Ferien, Krankheit …), bekommt nichts.
- **Ohne Zeiterfassung** (z. B. Admin ohne Vertrag): gilt als anwesend.
- **«Gehen» mit offener Aufgabe:** sie bleibt «Dran» bis zum nächsten «Kommen» (Fortsetzung am
  Morgen) – **ausser** sie wird dringend oder die Person hat am nächsten Arbeitstag eine Absenz:
  dann zurück in den Topf.

### 6.7 · Was die Person sieht

- **«Dran»** – eine Karte, ganz oben im Feed, auf jedem Gerät. Satz, Ort, Termin, seit wann, warum
  bei mir. Klick → der Datensatz öffnet sich und springt an die Stelle (`jumpToTodo`). Dazu
  **«Abgeben»**. Kein «Erledigt»-Knopf: erledigt meldet die Quelle.
- **Persönlich** – darunter klein, nur wenn es etwas gibt (««Gehen» fehlt am 07.11.»).
- **Danach** – die nächsten 3 Aufgaben im Topf, die ich könnte (zum Einschätzen, nicht zum
  Abarbeiten).
- **Alle Aufgaben** – der Filter im Feed: der ganze Topf, sortiert; je Zeile, wer dran ist (Bild),
  oder «frei». Darüber **«Jetzt»**: wer gerade woran ist (je anwesende Person ihr «Dran»). Das ist
  der Überblick «wer macht was» – für alle, nicht nur den Admin.
- **Am Datensatz** – im Kopf unter der Kopfzeile eine Leiste: «Du bist dran: …» bzw. «Lea Brunner
  ist dran: …» bzw. «Frei – Übernehmen». Die Zahl am Symbol bleibt (Aufgaben + Hinweise an diesem
  Datensatz), Hover je Abschnitt wie heute.
- **Am Prozessschritt** – das Bild der Person, die dran ist, und die Kompetenz als Chip.

## 7 · Oberfläche (keine neue Maske)

| Stelle | Heute | Neu |
|---|---|---|
| Feed, Typ-Filter | Benutzer · Artikel · Aufträge · Instanzen · Unternehmen · Dokumente | **erster Chip «Aufgaben»** (Symbol `ListChecks`), Zahl = alle im Topf + meine |
| Feed, oben | Suche + Scan | dazu die Karte **«Dran»** (immer, auch ohne Filter) |
| Feed, Zeile | Symbol, Name, Nummer, Status | im Filter «Aufgaben»: zweite Zeile = Satz der Aufgabe, rechts Bild der Person / «frei», rot wenn dringend |
| Datensatz-Kopf | Symbol mit Zahl «zu tun» | dieselbe Zahl, Hover «Aufgaben»; darunter die **Dran-Leiste** |
| Personendatensatz | Kommunikation, Zeiterfassung, Stammdaten | neuer Abschnitt **«Aufgaben & Kompetenzen»**: Dran, Kompetenzen (Admin ändert), Hinweis, wenn eine Person die einzige mit einer Kompetenz ist |
| Betreiber (Gesellschaft) | Stammdaten, Gebiete, Postfach, Rechtstexte | Karte **«Aufgaben»**: Kompetenz-Katalog (Name, wie viele können es) und Vorgabe je Art |
| Prozess-Editor | Modul, Name, Einstellungen | Feld **«Wer kann das?»** (Kompetenz) je Schritt, mit Anzahl Personen |
| Auftragsentwurf | Prozess, Wiederholung | Feld **«Termin»** (optional) |

**Mobil:** «Dran» ist das Erste auf dem Bildschirm. Wer in der Halle steht, öffnet das ERP und
sieht genau eine Sache.

## 8 · Datenmodell (neu)

```
competences          id, name (eindeutig), is_active, created_at, updated_at
person_competences   person_object_id, competence_id, is_active, …   (eindeutig je Paar, Soft-Delete)
task_kind_rules      kind (PK), competence_id NULL = jeder           (Vorgabe je Art)
task_focus           person_object_id (eindeutig), task_key (eindeutig), since, how
task_pulls           task_key (eindeutig, solange offen), by_object_id, reason, for_object_id NULL,
                     at, is_active                                   (Vorziehen / reserviert)
orders.due_on        DATE NULL                                       (Termin)
Schritt-Konfig       competence_id im eingefrorenen Schritt (kein neues Feld am Modell nötig,
                     wenn der Schritt seine config als JSON trägt – zu prüfen)
```

Ereignisse im Log (`services/log.event`): `task.assigned` · `task.taken` · `task.returned` (mit
Grund) · `task.done` · `task.pulled` · `task.unpulled`. Daraus sind später Durchlaufzeiten
ableitbar – ohne eigene Statistik-Tabelle.

**Zwei Formen einer Regel:** `tasks.assign_problem(person, task)` (Grund, z. B. für den Hover
«Übernehmen» gesperrt: «Dafür fehlt Ihnen die Kompetenz «Kranprüfung»») ↔ `tasks._assert_assign`
(Tor). Wie überall.

## 9 · Szenarien (Durchspielen)

1. **Kranservice beim Kunden.** Auftrag «Prüfung Hallenkran», Termin Fr. Schritt 1 Zahlung
   (Offerte) → Aufgabe «Beleg weiterbringen», Kompetenz Offerten → geht an Marco (frei, kann
   Offerten). Kunde sagt zu → die Zahlung zieht weiter, Schritt 2 Bewegen «zum Kunden» → Aufgabe,
   keine Kompetenz → an die erste freie Person mit den wenigsten anderen Möglichkeiten (Lehrling
   Nico). Schritt 3 Datenerfassung «Prüfprotokoll», Kompetenz Kranprüfung → Lea (nur 2 Personen
   können das). Rechnung → Marco oder wer Offerten kann.
2. **Mail kommt rein, alle stecken in langen Aufgaben.** Die Mail ist eine Aufgabe ohne Person
   im Topf. Nach 2 h wird sie rot → oben im Topf, alle mit «Kundendienst» sehen sie. Wer kurz
   Luft hat, öffnet sie und antwortet – erledigt, ohne Zuteilung. Sein «Dran» bleibt seins.
3. **Material fehlt am Verbrauch.** Keine Aufgabe (nicht machbar). Liegt das Material da (nach
   Bewegen), entsteht die Aufgabe; wer dran war, ist längst bei etwas anderem.
4. **Lea wird krank.** Absenz eingetragen → ihr «Dran» geht zurück in den Topf (mit Grund «Lea
   abwesend»), der nächste Freie mit Kranprüfung bekommt es. Gibt es keinen: Zeichen «niemand
   frei», der Admin sieht es oben.
5. **Niemand hat die Kompetenz.** Neuer Schritt «Schweissnaht prüfen (VT)» – Editor zeigt
   «0 Personen». Der Auftrag kann trotzdem freigegeben werden; die Aufgabe landet beim Admin
   mit «niemand kann das». Er vergibt die Kompetenz oder macht es selbst.
6. **Ich warte auf einen Rückruf.** «Abgeben» mit «warte auf Rückruf Bachmann» → interne
   Nachricht im Verlauf, Aufgabe zurück im Topf (nicht wieder bei mir für 30 min). Kommt der
   Rückruf (Nachricht an uns), wird sie sowieso wieder sichtbar.
7. **Der Chef will etwas sofort.** «Vorziehen» mit Grund, optional «für Lea». Lea bekommt es,
   sobald ihr jetziges erledigt ist – nicht mitten hinein.
8. **Jemand erledigt eine fremde Aufgabe.** Der Schritt ist bestätigt → die Quelle meldet
   nichts mehr → die Person, die dran war, ist frei und bekommt die nächste. Kein Konflikt.
9. **Ein Mitarbeitender allein / nur der Admin.** Alles geht an ihn, in der Reihenfolge – das
   System ist dann eine gute, sortierte Liste. Funktioniert ab einer Person.
10. **Zwei Leute öffnen gleichzeitig «Übernehmen».** Der eindeutige Schlüssel lässt nur einen
    durch; der andere bekommt einen Satz («Marco ist schon dran») und die nächste.
11. **Eine Wiederholung entsteht** (wiederkehr O18): ihr erster Schritt ist eine Aufgabe → jemand
    ist dran. Damit ist O18 beantwortet, ohne Sonderweg.
12. **Eine Kundenperson ohne Mail ergänzen** (Stammdaten einer Partei) – kleine Aufgabe, geht an
    Kundendienst; sie ist kurz, gleich erledigt.
13. **Persönliches**: «Gehen» fehlt gestern – steht unter «Dran» bei mir, belegt «Dran» nicht,
    geht nie an jemand anderen.

## 10 · Grenzfälle (Regeln)

- **Aufgabe verschwindet und kommt wieder** (Kunde antwortet nochmals): gleicher Schlüssel →
  dieselbe Aufgabe, `since` neu. War sie gerade bei jemandem, ist sie inzwischen erledigt gewesen
  (`task.done`); sie wird neu zugeteilt.
- **Schlüssel muss stabil sein:** Nachrichten über Betreff + Person; Prozess über Auftrag +
  Schritt. Ein Wächter prüft: zweimal lesen ohne Änderung = dieselben Schlüssel.
- **Recht weg** (Rolle zu `user`): alle Zeilen der Person weg, Aufgaben zurück.
- **Kompetenz entzogen** während «Dran»: zurück in den Topf (Grund im Log).
- **Kompetenz gelöscht** (Soft-Delete): Schritte, die sie verlangen, gelten als «niemand kann
  das» bis der Admin entscheidet – keine stille Umdeutung zu «jeder».
- **Abweichungsauftrag**: ist ein gewöhnlicher Auftrag → gewöhnliche Aufgaben.
- **Ausgang-Module** (Aussondern): auch nur ein Schritt.
- **Automatische Schritte** (Zahlung zieht selbst weiter): keine Aufgabe, solange niemand von uns
  handeln muss.
- **Externe** (Kunde soll unterschreiben, zahlen): nie eine Aufgabe bei uns – aber deren Ausbleiben
  kann eine werden (Mahnen).
- **Viele Stücke, mehrere Leute wollen helfen:** jeder darf am selben Schritt bestätigen (es
  blockiert nichts). Zugeteilt bleibt eine Person. Teilen ist eine spätere Stufe (§12).
- **Mehrere eigene Gesellschaften:** Kompetenzen gelten für alle; eine Gesellschafts-Bindung
  gibt es erst, wenn sie gebraucht wird.
- **Takt läuft nicht** (Dienst schläft, min 0 Instanzen): zugeteilt wird beim nächsten Lesen –
  ein offenes ERP genügt. Nichts geht verloren, weil nichts gespeichert wird ausser der Fokus.
- **Datenschutz:** wer wann woran war, ist Log; Einsicht wie heute (Verlauf). Keine Auswertung je
  Person.

## 11 · Was wir bewusst NICHT bauen

- Kein Aufgaben-Datensatz zum Anlegen, kein «Aufgabe erstellen». Etwas zu tun → **Auftrag**
  (Leitbild der lernenden Firma: «Etwas zu tun → Auftrag»). Eine Erinnerung ist eine Nachricht.
- Kein Kanban, keine Spalten, keine Prioritätsstufen 1–5, kein Ziehen in Listen.
- Keine Teams, Abteilungen, Stellenbeschreibungen.
- Keine Kapazitätsplanung, keine Gantt-Zeitachse, keine Schätzungen in Stunden.
- Keine Ranglisten, keine Leistungsauswertung je Person.
- Keine Push-Mitteilungen in Stufe 1 (das ERP ist offen; Handy-Push später).
- Keine KI in der Reihenfolge (erklärbar bleiben).

## 12 · Bauplan in Stufen

Jede Stufe ist für sich nützlich und einzeln ausrollbar.

| Stufe | Inhalt | Nutzen sofort |
|---|---|---|
| **A · Eine Liste** | `services/tasks` sammelt alle Quellen (die von `todo` + **Prozessschritt** + **Beleg weiterbringen**), Art und Schlüssel je Eintrag, Hinweis ↔ Aufgabe getrennt; Feed-Chip «Aufgaben» (sortiert nach §6.5); «zu tun» heisst «Aufgaben»; Termin am Auftrag | Man sieht alles, was zu tun ist, an einer Stelle, in einer Reihenfolge |
| **B · Kompetenzen** | Katalog, Zuordnung am Personendatensatz, Feld am Prozessschritt, Vorgabe je Art; der Chip zeigt «kann ich» / «kann ich nicht» | Jeder sieht, was er tun kann |
| **C · Dran** | `task_focus`, Dispatcher, Anwesenheit aus der Zeiterfassung, Karte «Dran», Dran-Leiste, Übernehmen, Abgeben, Vorziehen, «Jetzt» (wer macht was) | Eine Person, eine Sache – jede Sache, eine Person |
| **D · Lernen** (später) | Kompetenzstufe «lernt» (bekommt Aufgaben, wenn ein «kann» sie begleitet), Vorschlag der KI «Lea hat 10 Prüfungen sauber gemacht – Kompetenz geben?», Durchlaufzeiten je Aufgabenart, Handy-Push für «Dran», Teilen grosser Schritte | Kompetenz wächst, Abteilungen entstehen nicht |

Wächter (je gegen seine Bug-Form geprüft): eine Aufgabe nie bei zwei Personen · eine Person nie
mit zwei «Dran» · nie zugeteilt ohne Recht oder Kompetenz · nie eine Aufgabe, die nicht machbar ist ·
Schlüssel stabil · erledigt in der Quelle = weg aus `task_focus` · Reihenfolge = §6.5 (Matrix mit
vorher notiertem Soll) · persönliche Aufgaben nie im Topf.

## 13 · Offene Entscheide (Clemens)

| # | Frage | Vorschlag |
|---|---|---|
| E1 | Name im ERP: «Aufgaben» (Filter) und «Dran» (meine eine)? | ja |
| E2 | Strikt **eine** Aufgabe «Dran» je Person? | ja – mit den drei Ventilen: Abgeben, alles darf man trotzdem tun, Dringendes sehen alle |
| E3 | Wer darf «Vorziehen»? | jeder Mitarbeitende, mit Pflicht-Grund (sichtbar) – Alternative: nur Admin |
| E4 | Termin am Auftrag (optional, verschiebbar mit Grund)? | ja |
| E5 | Anwesenheit aus der Zeiterfassung (nur Eingestempelte bekommen Aufgaben)? | ja |
| E6 | Kompetenzen: eine Stufe «kann» jetzt, «lernt» später? | ja |
| E7 | Eine Kompetenz je Aufgabe (nicht mehrere)? | ja |
| E8 | «Jetzt» (wer ist woran) für alle sichtbar, nicht nur Admin? | ja – Transparenz statt Kontrolle, ohne Zahlen je Person |
| E9 | Zuteilung an «wer am wenigsten anderes kann» (Spezialisten schonen)? | ja |
| E10 | Reihenfolge Stufe A bauen, bevor Kompetenzen und Dran kommen? | ja |

## 14 · Verweise

- Bild (1:1 im ERP, Stufe C fertig, klickbar – Rolle Mitarbeiterin/Admin umschaltbar):
  https://claude.ai/artifact/4CpZXNTBtdTzuArnDSHY4r
- Quellen im Code: `backend/app/services/todo.py`, `frontend/src/lib/todo.ts`,
  `frontend/src/components/erp/feed-panel.tsx`, `detail-frame.tsx` (`RecordIcon`, `TodoChip`),
  `backend/app/domain/policy.py`, `backend/app/services/process.py` (`confirm_step`),
  `backend/app/services/order_view.py` (`waiting_for`), `services/timekeeping.tasks`.
