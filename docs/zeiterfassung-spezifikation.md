# Zeiterfassung – Spezifikation

INEXXIO ECS · Stand 24.10.2026 · Status: **umgesetzt** (Migration 154). Im Zweifel gilt der
Code: `backend/app/domain/timekeeping.py` (Regeln, Wörter), `services/timekeeping.py`
(rechnen, die eine Schreibstelle), `frontend/src/components/erp/time/`.
Rundenbericht: `docs/history/2026-10-24-zeiterfassung.md`.

---

## 1. Grundsätze

1. **Funktioniert immer.** Robust bei vergessenen Stempeln, Doppelklicks, wackligem Netz,
   Vertragswechsel und Zeitumstellung.
2. **So einfach wie möglich.** Ein Wischknopf, ein Werkzeug «Erfassen», eine Karte.
3. **So günstig wie möglich.** Keine Hardware, keine Zusatz-Tools, keine Lizenzen.
4. **Eine Regel, eine Logik für alle.** Keine Gruppen, keine Ausnahmen.
5. **Gespeichert wird nur, was jemand eingibt. Alles andere wird berechnet.**
6. **Gelöscht wird nichts.** Eine Änderung ist ein neuer Eintrag, der den alten ersetzt.
7. **Nur online.** Ohne Netz wird nichts gespeichert, ein Satz sagt es («Keine Verbindung –
   nicht gestempelt. Bitte erneut wischen, sobald das Netz da ist.»).

---

## 2. Ort im System

- Ein **Abschnitt «Zeiterfassung» im Personendatensatz** (kein Reiter, kein Modul, keine
  Team-Seite): zwischen Kommunikation und Stammdaten, eine Trennlinie mit dem Wort, darunter
  **eine Karte**.
- Sichtbar **nur im eigenen Datensatz** (Personal) und **für den Admin** (bei jeder Person mit
  Personal-Rolle). Geprüft vom Server (`timekeeping.may_see`).
- Der Admin kann im Datensatz einer anderen Person **dasselbe** wie sie (stempeln, erfassen,
  korrigieren – vermerkt «durch Anna Roth»), dazu: Verträge, Buchungen, Korrekturen ohne
  7-Tage-Frist.
- An der **eigenen Gesellschaft** (Stammdaten, ganz unten, nur Admin): eine Karte
  «Zeiterfassung» mit Feiertagen, Absenzarten und Regeln.
- Das frühere Feld «Pensum» (und «Eintrittsdatum») im Profil ist weg – beides steht im Vertrag.

---

## 3. Datenmodell (gespeichert)

### 3.1 Vertrag – `time_contracts` (append-only)

| Feld | Regel |
|---|---|
| `person_object_id` | Pflicht |
| `valid_from` | Stichtag, eindeutig je Person |
| `weekly_minutes` | Wochenstunden; **0 = Austritt** |
| `workdays` | Arbeitstage (Mo–So, Bitmaske), mindestens einer |
| `vacation_weeks` | mindestens gesetzlich (Alter am Stichtag: bis 20 → 5, sonst 4); leer = gesetzlich |
| `company_object_id` | eine **eigene** Gesellschaft (vorbelegt mit der Firma der Person) – bestimmt Feiertage und Nachweis-Regeln |

- Gültig ist am Tag D der Vertrag mit dem neuesten Stichtag ≤ D. Eintritt = erster Vertrag,
  jede Änderung = neuer Vertrag (auch in der Zukunft: «Geplant»), Austritt = 0 h.
- **Soll je Arbeitstag = Wochenstunden ÷ Anzahl Arbeitstage** (25 h an Mo–Mi = 8:20 h);
  an einem Feiertag 0.
- Verlangt das Geburtsdatum der Person (Jugendschutz, gesetzliche Ferien).
- Ein Vertrag wird nie geändert; ein Fehler wird mit einem neuen Vertrag oder einer Buchung
  behoben.

### 3.2 Einträge – `time_entries` (append-only)

EINE Tabelle für alles, was einen Tag füllt oder ein Konto bewegt:

| `kind` | Bedeutung | Felder |
|---|---|---|
| `in` / `out` | Kommen / Gehen | `at` (Zeitpunkt, UTC), `source` = `swipe` · `manual` |
| `absence` | Absenz | `art`, `day` … `until`, `minutes` je Tag (leer = **ganzer Tag** = Tagessoll), `note`, `proof_url` |
| `booking` | Buchung (nur Admin) | `day`, `minutes` (Stundenkonto ±), `vacation_minutes` (Ferien ±), `note` (Grund, Pflicht) |
| `void` | Rücknahme eines Eintrags | `replaces_id` |

- **`replaces_id`**: eine Änderung ist ein neuer Eintrag, der den alten ersetzt (höchstens
  einmal – Unique-Index). Was gilt, ist abgeleitet: nicht ersetzt und keine Rücknahme.
- `created_by` hält fest, wer erfasst hat; `idem_key` macht einen Wisch idempotent.
- **DB-Trigger** `trg_time_entries_append_only` / `trg_time_contracts_append_only`: kein
  UPDATE, kein DELETE – auch nicht von Hand.

### 3.3 Feiertage – `holidays`

Gesellschaft · Tag · Name. Es zählt nur, was übernommen ist. Stammdaten: ein falscher
Feiertag wird entfernt (Soft-Delete, Audit-Log).

### 3.4 Regeln der Gesellschaft – `company_settings.time_rules`

`{"canton": "TG", "proof": {"krank": 3}}` – der Kanton (für den Vorschlag der Feiertage) und
je Absenzart, ab welchem Arbeitstag ein Nachweis nötig ist.

### 3.5 Absenzarten (Katalog im Code, je EINE Wirkung)

| Art | Wirkung | Nachweis (Vorgabe) |
|---|---|---|
| Ferien | **Ferien** – zählt als Arbeitszeit, geht vom Guthaben ab | – |
| Krankheit | **Erfüllt** – zählt als Arbeitszeit | Arztzeugnis ab Tag 3 |
| Unfall | Erfüllt | Arztzeugnis ab Tag 3 |
| Militär/Zivildienst | Erfüllt | Dienstbescheinigung immer |
| Mutter-/Vaterschaft | Erfüllt | Bescheinigung immer |
| Bezahlte Absenz | Erfüllt | – |
| Unbezahlter Urlaub | **Entfällt** – Soll fällt weg, keine Ferien wachsen an | – |

Nicht zusammengelegt: Krankheit (KTG/OR 324a) und Unfall (UVG) zahlen verschiedene
Versicherungen, Militär und Elternschaft die EO. Eine feste gesetzliche Frist fürs
Arztzeugnis gibt es nicht – der Betrieb legt sie fest (üblich: ab Tag 3).

### 3.6 Regeln Schweiz (im Code, `domain/timekeeping`)

Arbeitstage Mo–Fr (Vorschlag) · 42 h (Vorschlag) · höchstens 45 h/Woche · Ruhezeit 11 h
(unter 18: 12 h) · Pausen 15/30/60 min ab 5½/7/9 h · Nacht 23–06 · Sonntag gesperrt ·
Mindestferien 4 Wochen, bis 20: 5 · Korrektur durch Mitarbeitende 7 Tage. Keine Obergrenze
fürs Stundenkonto, keine Schwelle fürs Ferienguthaben.

---

## 4. Berechnungen (nie gespeichert)

Alles in **Minuten**, je Tag D, in Europe/Zurich (Zeitpunkte als UTC – richtig auch an der
Zeitumstellung).

- **Block** = Kommen bis zum nächsten Gehen; gehört zum Tag des Kommens (auch über
  Mitternacht). Ein Kommen ohne Gehen **läuft höchstens 14 h** (ArG Art. 10: Tagesarbeit in
  14 h); danach ist der Tag **offen** («Gehen» fehlt), und der nächste Wisch ist wieder
  «Kommen».
- **Ist(D)** = Summe der Blöcke; heute inklusive des laufenden.
- **Absenz am Tag**: an einem Arbeitstag gilt die **jüngste** Absenz, die ihn deckt – eine neue
  ersetzt an ihren Tagen eine ältere (krank in den Ferien: die Ferien kommen zurück).
  Minuten = Tagessoll (ganzer Tag) bzw. min(Minuten, Tagessoll). An Nicht-Arbeitstagen wirkt
  keine Absenz – Ferien über einen Feiertag ziehen dort nichts ab.
- **Saldo(D)** = Ist + Gutschrift − Soll (bei «Entfällt» sinkt das Soll).
- **Stundenkonto** = Summe der Saldi bis **gestern** (ein offener Tag zählt erst, wenn er
  vollständig ist) + Buchungen.
- **Ferien** = Anspruch Tag für Tag (Ferienwochen × Wochenstunden ÷ 365, auch am Wochenende,
  nicht bei «Entfällt»), minus Bezug bis heute, plus Buchungen. **Anzeige in Stunden**, in
  Klammern in Tagen (÷ Tagessoll des aktuellen Vertrags): `121:48 h (14.5 Tage)`. **Negativ
  erlaubt** (Ferien im Voraus), dann rot. Kein Reset zum Jahreswechsel.
- **Austritt**: Schlussstand (Konto, Ferien) am Vortag – der Wert für die Lohnabrechnung.
- **Ferien danach** (Vorschau): Guthaben heute minus alle geplanten Ferien, mit dieser Absenz.

---

## 5. Abläufe

### 5.1 Stempeln – der Wischknopf
- Volle Breite: die Bahn ist das Soll (grau), die grüne Fläche das Ist, in der Mitte leise
  «4:51 / 8:24 h»; Hover: «Anwesend seit 07:42 · heute 4:51 h von 8:24 h».
- Abwesend → links grün «Kommen ›», nach rechts wischen; anwesend → rechts rot «‹ Gehen»,
  nach links. Ausgelöst ab 70 % des Weges; Tastatur Pfeil/Enter.
- Serverzeit. Ein Schlüssel je Wisch (zweimal gesendet = einmal geschrieben); ein zweiter
  Wisch innert 60 s und eine schon geltende Richtung (zweites Gerät) schreiben nichts.

### 5.2 Ein Tag – Einträge und «Erfassen»
- Tag antippen → rechts (schmal: darunter) der Tag: Titel «Freitag, 23.10.2026» mit Hinweisen,
  Stempel (Kommen grün, Gehen rot), höchstens eine Absenz (mit Spanne, «ersetzt»,
  Nachweis/«Hochladen», «Zurücknehmen»). Ein offener Tag zeigt «Gehen · fehlt» mit «+».
- Eine Änderung steht **an der Zeile**: «geändert» (Hover: «Vorher 07:55 · geändert von …,
  Datum Zeit»), «nachgetragen», «durch Anna Roth». Unverändert übernommen = keine Änderung.
- **Ein Knopf «Erfassen»**: die Art als Symbole (Name im Hover und im Titel): Kommen/Gehen
  (nicht in der Zukunft) und die sieben Absenzarten (nur an Arbeitstagen). Stempel: Uhrzeit.
  Absenz: Umfang «Ganzer Tag | Stunden», Dauer pro Tag, Bis (oder einen späteren Tag im
  Kalender antippen). **Vorschau vom Server** (`/entries/preview`, dieselbe Regel wie beim
  Speichern): Ersetzt · Wirkung · Arbeitstage · Stunden · Ferien danach · Nachweis – oder der
  Satz, warum es nicht geht. Kein halber Tag; Ferien auch stundenweise.
- Prüfungen: Kommen/Gehen wechseln sich ab; nicht in der Zukunft («Liegt in der Zukunft –
  jetzt ist es 12:33.»); kein Stempel an einem ganztägigen Absenztag; nicht ohne Vertrag;
  Absenz beginnt an einem Arbeitstag, Dauer > 0 und ≤ Tagessoll, ganzer Tag nicht an einem Tag
  mit Stempeln, Bis ≥ Tag, höchstens ein Jahr.
- «Gehen» nach Mitternacht (02:00 nach Kommen 22:00) wird als Folgetag erkannt.

### 5.3 Die 7-Tage-Regel
Eigene Einträge lassen sich 7 Tage zurück ändern; ältere Tage sind **abgeschlossen** – im
Kalender **blass** (antippen geht, der Tag sagt «Abgeschlossen – Änderung über die
Administration» ⓘ). Der Admin ist nicht beschränkt. Ein **Nachweis** lässt sich jederzeit
nachreichen.

### 5.4 Vertrag und Buchungen (Admin)
Unter «Vertrag» (aufklappbar): die Verträge (Eintritt/ab/Austritt, «42 h/Woche · Mo–Fr ·
5 Wochen Ferien · Inexxio AG», Aktuell/Geplant/Abgelöst; Austritt mit Schlussstand), «Neuer
Vertrag» (Gültig ab, Wochenstunden, Arbeitstage Mo–So, Ferienwochen), die Buchungen (Datum ·
Grund · wer · «+4:00 h · Ferien +25:12 h (+3 Tage)») und «Neue Buchung» (Übertrag bei
Einführung, Auszahlung, Korrektur – nie geändert, Fehler = Gegenbuchung).

### 5.5 Feiertage (Admin, an der Gesellschaft)
Kanton wählen → «Vorschlag für Kanton TG laden» (OpenHolidays, CC BY 4.0) → abwählen →
«Übernehmen (n)»; «Ortsfeiertag» von Hand; einen entfernen. Ist der Dienst nicht erreichbar,
sagt es ein Satz.

---

## 6. Hinweise (Ampel – sie warnt nur)

| Hinweis | Bedingung | Ton |
|---|---|---|
| Pause fehlt | Mindestpause nicht erreicht | orange |
| Nachtarbeit | Block in 23–06 | rot |
| Unter 18: über 9 h | Alter < 18, Tag > 9 h | rot |
| Ruhezeit zu kurz | < 11 h (unter 18: 12 h), am späteren Tag | rot |
| Über 45 h/Woche | an dem Tag, der die Grenze überschreitet (Mo–So) | rot |
| Sonntagsarbeit | Stempel am Sonntag ausserhalb der Arbeitstage | rot |
| Stempel fehlt | offener Tag | orange (Aufgabe) |
| Nachweis fehlt | Nachweis fällig, nicht hochgeladen | orange (Aufgabe) |

Im Kalender ein Punkt oben rechts (rot gewinnt), am Tag als Pille. Nie ein automatischer Abzug.

---

## 7. «Zu tun» – die Zahl am Symbol

`GET /api/v1/erp/todo` (`services/todo`): je Datensatz eine Zahl oben rechts am Symbol (Feed
und Kopf) – **offene Nachrichten + Aufgaben der Zeiterfassung (offener Tag, fälliger
Nachweis) + fehlende Pflichtangaben**, an einer eigenen Gesellschaft **fehlende Feiertage**.
Orange; **rot**, sobald etwas dringend ist (überfällige Nachricht, Aufgabe ab 5 Tagen).
Hover listet je Abschnitt, Klick im Kopf springt hin; dieselbe kleine Zahl steht an
«Zeiterfassung», «Stammdaten», «Person», «Adressen», «Feiertage». Die Zeiterfassung zählt nur
für die Person selbst und den Admin, die Feiertage nur für den Admin.

**Feiertage fällig**: laufendes Jahr ohne Feiertag → sofort rot; nächstes Jahr ab 1. Oktober
orange, ab 1. Dezember rot – nur für eine Gesellschaft, auf die ein Vertrag lautet.

**Pflichtangaben** stehen **im Backend** (`people.required_fields` / `missing_fields`):
Vorname, Nachname, Telefon, eine Adresse, für Personal das Geburtsdatum. Das Konto zeigt
daraus den Fortschritt («Profil zu 80 % vollständig»), das ERP die Zahl – ERP ist Master.

---

## 8. Rollen und Rechte

| Aktion | Mitarbeitende (eigener Datensatz) | Admin (jeder Personal-Datensatz) |
|---|---|---|
| Stempeln, erfassen, korrigieren | ✓, 7 Tage zurück | ✓, unbegrenzt (vermerkt «durch …») |
| Nachweis nachreichen | ✓ jederzeit | ✓ |
| Vertrag, Buchungen sehen | ✓ | ✓ |
| Vertrag anlegen, buchen | – | ✓ |
| Feiertage, Kanton, Nachweis-Regeln | – | ✓ |

---

## 9. Datenschutz

Jede Person sieht nur ihre eigenen Daten, der Admin alle. Keine Standortdaten, keine
Verhaltensüberwachung – erfasst werden nur Zeitpunkte. Nachweise sind Bilder (Foto/Scan),
ausgeliefert über einen unerratbaren Token. Gelöscht wird nichts.

---

## 10. Das Reglement – an der Stelle, an der es gilt

Kein eigener Text-Dialog: die Sätze stehen als ⓘ an Karte, Stundenkonto, Ferien, Vertrag,
Kalender, Tag (Pausen, Grenzen), «Erfassen», Buchungen, Feiertagen, Absenzarten und Regeln –
**eine Quelle** (`domain/timekeeping.TEXTS`), vom Server mitgeliefert.

---

## 11. Bewusst nicht im Umfang

Genehmigungen · Offline-Stempeln · Export/Lohnbuchhaltung (später) · Team-Seite ·
Schnellzugriff ausserhalb des Datensatzes · Schichtpläne · Projekt-/Auftragszeit ·
Geofencing · Obergrenze Stundenkonto · Schwelle Ferienguthaben · halbe Tage (Stunden genügen)
· automatische Löschung nach 5 Jahren (gelöscht wird nichts).

## 12. Offen

1. Export für die Lohnbuchhaltung (Bexio/Klara).
2. Benachrichtigung des Admins über die Zahl am Symbol hinaus.
3. Wechselnde Schichtpläne.
4. Verrechnung von Minusstunden/Ferien beim Austritt – hängt davon ab, wer kündigt (Treuhand).
