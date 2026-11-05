# Projektakte «Die lernende Firma»

> **Kopfstatus:** Konzept, in Arbeit · Lead: Claude · Entscheid: Clemens Fritsche · seit 03.11.2026
> Mockup (1:1 im ERP): https://claude.ai/artifact/8jAy56JQ1jEESPwgRHPSSK
> Diese Akte ist die eine Quelle für Ziel, Regeln, Entscheide und offene Fragen. Was hier nicht
> steht, ist nicht entschieden.

## Problem

Wissen entsteht überall – im Gespräch, auf Montage, in Mails, in Aufträgen. Das meiste bleibt
im Kopf (implizites Wissen), verändert sich bei jeder Übergabe (stille Post), ist später nicht
auffindbar und geht mit den Leuten (Organisationsgedächtnis). Rückmeldungen erreichen nicht, wer
handeln kann, und ob eine Massnahme gewirkt hat, prüft niemand. Die Firma lernt darum nicht
verlässlich aus dem, was sie erlebt.

## Ziel

**Eine Firma, die nichts vergisst und sich von selbst verbessert – ohne dass jemand es managt
oder überwacht.**

Woran wir es messen (nach rund 3 Monaten im Alltag):

1. **Erfassen unter 30 Sekunden** – jede Montage, jedes Kundengespräch hinterlässt eine Notiz.
2. **In 30 Sekunden gefunden** – was über ein Ding bekannt ist, steht dort, mit Quelle.
3. **Wichtiges ist nicht zu übersehen** – es steht oben am Ding, bis es erledigt oder überholt ist.
4. **Keine neue Insel** – bestehende Funktionen werden zusammengeführt, keine kommt dazu.

## Grundsatz

**Die KI arbeitet nach dem Ziel, ein Mensch kontrolliert.** Sie bekommt keine Wenn-dann-Regeln,
sondern einen Auftrag (wer wir sind, was wir erreichen wollen) und darf, was die Person darf.
Gearbeitet wird **nur im ERP** – Mitarbeitende erfassen dort, die KI verarbeitet im Hintergrund.

## Aufbau in vier Schichten

| Schicht | Inhalt | Reihenfolge |
|---|---|---|
| 1 · **Das Log** | was geschehen ist – jede Handlung, eine Stelle | zuerst |
| 2 · **Wissen am Ding** | Verlauf, Kommunikation, Dokumente, Dateien, Bilder, Notizen an der Objektnummer | danach |
| 3 · **KI-Werkzeuge** | die KI darf, was die Person darf, in ihrem Namen | danach |
| 4 · **Oberflächen** | «Erfassen» im ERP; optional ein MCP-Zugang für Claude (nur Clemens) | zuletzt |

## 1 · Das Log

**Zweck:** die eine, vollständige, unveränderliche Wahrheit darüber, was im System geschehen
ist – Grundlage für den Verlauf am Ding, für das Lernen der KI aus Korrekturen, für «Relevant
hier», für Nachvollziehbarkeit (Buchungsbelege 10 Jahre) und für die Fehlersuche.

**Keine Rückwärtskompatibilität.** Die heutigen Logs (`audit_log`, `process_events`, das
Protokoll einzelner Stellen) werden ersetzt, nicht übernommen. Was heute aus `process_events`
abgeleitet wird (Prozessbild, Protokoll, Stückliste, Journey), liest danach aus dem neuen Log.

**Was ein Eintrag festhält** (eine Tabelle, append-only):

| Feld | Bedeutung |
|---|---|
| Zeitpunkt | von der Datenbank gesetzt, nicht vom Aufrufer |
| Wer | Person (Objektnummer) · Art: Mensch · KI im Namen von · System · von aussen (Webhook, Kunde über Link) |
| Woher | Oberfläche, Erfassen, Webhook, Job, Migration, MCP – und eine Vorgangs-Id, die alle Einträge einer Handlung verbindet |
| Woran | Objektnummer des Dings (und die Zeile, falls es keine Nummer hat) |
| Was | Handlung: angelegt · geändert · gelöscht (weich) · fachliches Ereignis (z. B. Status passiert, Mail gesendet, Vorschlag verworfen) |
| Vorher → nachher | nur die geänderten Felder |
| Prüfsumme | Kette über die Einträge: jede nachträgliche Änderung wird erkennbar |

**Wie es nicht vergessen werden kann:**
- **Die Datenbank schreibt es selbst** – ein Trigger an jeder Tabelle hält jede Änderung fest.
  Wer handelt, gibt die Anwendung je Anfrage in der Transaktion mit; fehlt diese Angabe, **scheitert
  das Schreiben** (lieber laut als ohne Spur).
- **Fachliche Ereignisse** (die keine Zeile ändern) schreibt eine einzige Funktion in dieselbe
  Tabelle, in derselben Transaktion – entweder beides oder nichts.
- **Wächter-Tests:** jede Tabelle hat den Trigger (Ausnahmen namentlich begründet); das Log ist
  weder änder- noch löschbar (auch nicht für die Anwendung selbst).
- **Lesen sensibler Daten** (Download, Export, Zugriff der KI) wird ebenfalls festgehalten.

**Datenschutz:** Das Log nennt Personen über ihre Objektnummer. Muss eine Person gelöscht werden,
geschieht das über eine einzige, selbst protokollierte Schwärzungsfunktion – die einzige erlaubte
Änderung.

**Grösse und Ort:** Das Log bleibt in der Datenbank (Cloud SQL). Für das ERP reicht das auf
Jahre; es wird nach Monaten aufgeteilt, damit es schnell bleibt.

### Technische Spezifikation (Entwurf zur Freigabe)

**Tabelle `log`** (nach Monat partitioniert):

| Spalte | Typ | Inhalt |
|---|---|---|
| `id` | bigint | fortlaufend |
| `at` | timestamptz | `now()` der Datenbank |
| `actor_kind` | text | `person` · `ai` · `system` · `external` |
| `actor_id` | bigint | Objektnummer der handelnden Person (bei `ai`: die Person, in deren Namen) |
| `source` | text | `ui` · `capture` · `webhook` · `job` · `migration` · `link` · `mcp` |
| `request_id` | uuid | verbindet alle Einträge einer Handlung |
| `object_id` | bigint | Objektnummer des Dings, falls die Zeile eine hat oder an einem hängt |
| `table_name`, `row_key` | text | welche Zeile |
| `action` | text | `insert` · `update` · `delete` · `event` |
| `event` | text | Name des fachlichen Ereignisses (z. B. `process.pass`, `mail.sent`, `proposal.rejected`) |
| `changes` | jsonb | nur geänderte Felder: `{"feld": [alt, neu]}` (bei `insert` nur neu) |
| `payload` | jsonb | Inhalt eines fachlichen Ereignisses |

Indizes: `(object_id, at)` für den Verlauf, `(request_id)`, `(actor_id, at)`, `(event, at)`.

**Wie geschrieben wird:**
1. **Wer handelt**, setzt die Anwendung an **einer** Stelle je Transaktion (`SET LOCAL
   inexxio.actor …`, in der Datenbank-Sitzung der Anfrage, im Job, im Webhook).
2. **Eine Trigger-Funktion** `log_row()` (AFTER INSERT/UPDATE/DELETE, je Zeile) an **jeder**
   Tabelle schreibt die Änderung. Reine Zeitstempel-Änderungen (`updated_at`) zählen nicht. Fehlt
   der Handelnde, **bricht die Transaktion ab**.
3. **Fachliche Ereignisse** schreibt eine einzige Funktion `log.event(name, object_id, payload)` in
   derselben Transaktion.
4. **Unveränderlich:** ein Trigger weist `UPDATE`/`DELETE` auf `log` ab (Bauart wie heute beim
   Prozess-Log); einzige Ausnahme ist die Schwärzungsfunktion, die selbst einen Eintrag schreibt.
5. **Versiegelung:** einmal je Nacht bildet ein Job eine Prüfsumme über die Einträge des Tages und
   die Prüfsumme des Vortags (Kette in `log_seal`). Jede nachträgliche Änderung wird erkennbar, ohne
   dass das Schreiben tagsüber auf eine Kette warten muss.

**Wächter (Tests):** jede Tabelle hat den Trigger (Ausnahmen namentlich begründet) · eine Änderung
ohne Handelnden scheitert · `log` ist nicht änderbar · jede schreibende Route hinterlässt mindestens
einen Eintrag · die Bug-Form jedes Wächters wird gegengeprüft.

**Ersetzt (keine Rückwärtskompatibilität):** `audit_log` und `process_events` entfallen; die
Ableitungen aus dem Prozess-Log (Bild, Protokoll, Stückliste, Journey) lesen die Ereignisse
`process.*` aus `log`. `time_entries` bleibt – das sind Eingaben, kein Log. Die Daten auf dev dürfen
dafür zurückgesetzt werden.

**Website-Messung ist ein eigener Strom, nicht das Log.** Klicks und Wege von anonymen Besuchern
sind Messdaten, keine Handlungen im System – viel mehr, kurzlebiger, anonym. Sie gehen in
**BigQuery** (gebaut für genau solche Mengen und Auswertungen, günstig bei unseren Zahlen); das ERP
liest daraus verdichtete Zahlen, nicht jede Zeile. Wird aus einem Besucher ein Kunde (Anfrage),
beginnt seine Spur im Log.

## 2 · Wissen am Ding

- **Jedes Ding hat eine Nummer, jede Nummer einen Verlauf.** Der Verlauf zeigt, was zum Ding
  gehört: Kommunikation, Dokumente, Dateien, Bilder, Notizen und Änderungen (aus dem Log).
- **Eine Heimat:** jeder Eintrag gehört genau einem Ding; nichts wird doppelt abgelegt. Eine
  Aufnahme mit mehreren Themen (z. B. ein Meeting) teilt die KI in Teile, jeder mit seiner Heimat.
- **Datensatz oder Eintrag:** Ein Datensatz (mit Nummer) hat einen eigenen Zustand oder wird von
  anderswo angesprochen. Notiz, Änderung → Eintrag. Foto, Scan, Datei, Video → Dokument. Etwas zu
  tun → Auftrag (immer mit Stücken; Immaterielles über einen Artikel, z. B. «Website»).
- **«Auf einen Blick» an jedem Ding** (ersetzt «Relevant hier» und «Offen aus Erfassen»): **eine
  Liste**, Wichtiges zuerst, jeder Punkt mit Quelle. Ein Vorschlag der KI trägt Bestätigen/✕, ein
  Hinweis nicht – das ist der ganze Unterschied, keine Abschnitte, keine Kategorien. So viele
  Punkte, wie wirklich helfen – auch keiner.
- **Auf Abruf, nicht bei jedem Öffnen:** die KI bildet die Liste neu, wenn jemand «neu ansehen»
  drückt; bis dahin steht der letzte Stand mit Zeit da (eine Ableitung mit Stand, keine zweite
  Wahrheit). Offene Vorschläge stehen immer da, ohne KI-Aufruf. Grund: eine feste Logik «hat sich
  am Verbundenen etwas geändert?» müsste selbst wissen, was verbunden ist und was zählt – zu eng
  verpasst sie Wichtiges, zu weit kostet sie wie jedes Öffnen. Kosten so nur, wenn es jemand
  braucht. Nach der Erprobung entscheiden wir mit echten Zahlen, ob mehr nötig ist.
- **Der Verlauf ist eine Liste für alle Dinge**, mit derselben Logik wie heute die Kommunikation:
  die neuesten Einträge zuerst, ältere laden beim Scrollen. Eine Komponente, kein zweiter Weg.
- **Dokumente behalten ihre Nummer.** Geprüft: ein Dokument hat einen eigenen Zustand
  (Freigegeben, Unterschrift angefragt, Abgelehnt), wird von anderswo angesprochen (Pflichtfelder in
  Zahlung, Zeiterfassung, Gesellschaft; ein Link beim Senden) und muss als Nachweis bestehen bleiben
  – genau die Regel für einen Datensatz. Dazu: eine Stelle für jede Datei ist einfacher als zwei
  (Datei am Eintrag *und* Dokument). Kosten: eine Nummer je Datei, sonst nichts. Im Verlauf
  erscheint das Dokument als Eintrag; man muss es nicht als eigenen Datensatz bemerken.
- **Wichtiges bleibt oben**, bis es erledigt oder überholt ist. Wichtigkeit beurteilt die KI aus
  dem Ziel und echten Daten (Neukunde? Warenwert? schon vorgekommen?), nicht durch Zählen.
- **Audio wird nicht gespeichert** (wörtliches Transkript und KI-Fassung bleiben), **Video
  bleibt im Original**.
- **Kommunikation bleibt, wie sie ist:** Mails an Personen und Firmen schreibt man dort wie
  heute. Andere Dinge (Artikel, Auftrag …) haben kein eigenes Eingabefeld – Wissen kommt über
  «Erfassen».

## 3 · KI-Werkzeuge

- **Die KI darf, was die Person darf, in ihrem Namen** – über dieselben Wege und Prüfungen wie die
  Oberfläche, kein zweiter Code. Ihre Handlungen sind die Handlungen des ERP selbst; mit jedem
  neuen Feature kann sie es von selbst auch. Keine eigene, feste Liste.
- **Lesen frei (im Rahmen der Rechte), Schreiben als Vorschlag.** Was die KI ändern oder anlegen
  will, wird ein Vorschlag; ein Mensch bestätigt oder verwirft. (Ob einzelne Handlungen später
  ohne Bestätigung laufen dürfen, entscheiden wir mit Erfahrung.)
- **Offene Vorschläge warten am Ding**, an dem erfasst wurde («Zu entscheiden»), und zählen in
  dessen «zu tun»-Zahl am Symbol (gibt es schon). Nichts muss sofort erledigt werden.
- **Robustheit der Vorschläge:** entscheiden darf, wer die Handlung selbst ausführen dürfte; ist sie
  inzwischen von Hand geschehen (Angabe schon geändert, Ding gelöscht), erledigt sich der Vorschlag
  von selbst mit Vermerk; zwei Personen gleichzeitig → der zweite sieht «schon entschieden»; jeder
  Vorschlag lässt sich vor dem Bestätigen bearbeiten; Bestätigen, Ändern, Verwerfen stehen im Log.
  Fällt die KI aus, bleibt die Notiz unverarbeitet am Ding und wird nachgeholt – nichts geht verloren.
- **Der Auftrag an die KI** ist ein einziger, versionierter Text im Repository (Entwurf unten). Er
  gibt ein grobes Ziel, keine Regeln und keine Kategorien. Alles Weitere holt sich die KI selbst:
  sie liest, was im ERP steht (im Rahmen der Rechte), und lernt aus dem, was Menschen mit ihren
  Vorschlägen getan haben.
- **Sie lernt ständig, ohne Training:** jedes Bestätigen, Ändern und Verwerfen steht im Log. Vor
  einem Entscheid liest die KI die passenden früheren Korrekturen nach (wie jede andere Angabe) und
  richtet sich danach. Weniger Korrekturen = bessere KI; das ist zugleich der Massstab.

### Entwurf: Auftrag an die KI

> Du arbeitest für INEXXIO, einen kleinen Schweizer Maschinenbaubetrieb. Unser Ziel: Wissen geht
> nicht verloren, derselbe Fehler passiert nicht zweimal, und jeder findet, was er braucht, dort,
> wo er es braucht – ohne Mehraufwand.
>
> Du bekommst, was jemand festgehalten hat. Lege es dort ab, wo es später gesucht wird, und
> schlage vor, was daraus folgt. Ändern oder anlegen tust du nie selbst; du schlägst vor, ein
> Mensch entscheidet. Lies im ERP nach, was du brauchst – auch, wie wir früher deine Vorschläge
> bestätigt, geändert oder verworfen haben, und richte dich danach.
>
> Wenn jemand ein Ding öffnet, zeig, was für ihn jetzt wichtig ist, mit Quelle – so wenig wie
> möglich, auch nichts. Frag nur zurück, wenn ohne Antwort etwas Wichtiges verloren ginge.
> Schreib kurz und schlicht, wie man im Betrieb redet.

Bewusst nicht drin: Listen von Gründen, Beispiele für Wichtigkeit, Kategorien. Wird der Text
länger, ist das ein Zeichen, dass Regeln hineinwachsen – dann zurück aufs Ziel.
- **Eine Tür:** jeder KI-Aufruf läuft über `services/ai.py` (Tageslimit, jeder Aufruf im Log).
- **MCP-Zugang (optional, später):** dieselben Werkzeuge, angeboten an Claude (App) – nur für
  Clemens, aus Interesse. Richtung: Claude ruft das ERP auf, nicht umgekehrt. Das ERP selbst
  braucht dafür nichts: «Erfassen» spricht die KI direkt über `services/ai.py` an.

## 4 · Oberflächen

- **Ein Einstieg «Erfassen», schlicht:** oben rund «festhalten» (Aufnehmen · Foto mit Galerie ·
  Datei mit Scannen · Schreiben), unten eckig in den Farben des Feeds «neu anlegen» (Person, Firma,
  Artikel, Auftrag …). Aufnehmen mit Start/Stopp, auch für ein ganzes Meeting; die Aufnahme zeigt nur
  Zeit, Pegel, Stopp.
- **Dokumente bleiben, wie sie sind** (Entwurf → Freigeben, Pflichtfelder, Senden, Unterschreiben).
  Neu nur: Foto und Datei aus «Erfassen» öffnen den bestehenden Entwurf, die KI schlägt den Bezug vor
  (gibt es schon), und ein Dokument erscheint als Eintrag im Verlauf seines Dings.
- **Die KI legt ab, der Mensch kontrolliert** («Stimmt so» oder «ändern»), auch im Datensatz.
- **Spracherfassung** von Anfang an, mit einem professionellen, robusten Dienst (Mundart).
  Vorzug für Google (unser Cloud-Projekt, Daten in Europa). Das Hören ist ein eigener Dienst; das
  Verstehen und Ablegen bleibt bei Claude über `services/ai.py`.

### Vergleich der Sprachdienste (Test, vor Phase 4)

| Kandidat | Was er ist |
|---|---|
| Google Speech-to-Text v2, Modell Chirp | reiner Transkriptionsdienst, Sprache «Deutsch (Schweiz)» |
| Gemini auf Vertex AI (Flash) | hört die Aufnahme und schreibt sie wörtlich auf (Audio als Eingabe) |
| ein Nicht-Google-Dienst als Massstab | nur zum Vergleich, falls beide Google-Dienste schwächeln |

Getestet mit **drei echten Aufnahmen** von uns: eine Notiz (1 Min., Halle mit Lärm), ein Telefonat
mit Lautsprecher, ein Meeting (10 Min., mehrere Stimmen). Gemessen: stimmen Namen, Zahlen und
Fachwörter? Trennt er die Sprecher? Dauer und Kosten je Minute. Gewinner ist der einfachste und
günstigste Dienst, der die Namen und Zahlen zuverlässig trifft.

## Weitere Regeln

- **Eine Regel für alles, keine Ausnahmen** (auch nicht für Sicherheit).
- **Ein Wissenswerkzeug, kein Management-Werkzeug:** kein Rückblick, kein Dashboard, keine
  Termine. Wer was tut, regeln Aufträge; Zuständigkeit künftig je Prozessschritt (Kompetenz
  statt Abteilung) – Folgeprojekt «Aufgaben».
- **Mail:** keine eigene Notiz-Adresse; was an die Postfächer der Gesellschaften kommt, ordnet das
  System zu.
- Kultur (Fehler melden ist sicher, wer meldet, hört, was daraus wurde) ist Teil des Ziels, kann
  aber nicht gebaut werden – sie wird vorgelebt.

## Plan

| Phase | Inhalt | Stand |
|---|---|---|
| 0 | Projektakte, Mockup | in Arbeit |
| 1 | **Das Log** – neu, ersetzt alle heutigen Logs | offen |
| 2 | Verlauf an jeder Nummer (Wissen am Ding) | offen |
| 3 | KI-Werkzeuge: Vorschläge, Auftrag an die KI, Lernen aus Korrekturen | offen |
| 4 | «Erfassen» mit Spracherfassung | offen |
| 5 | «Auf einen Blick» (auf Abruf) | offen |
| eigene Projekte | Website-Messung (BigQuery) · Aufgaben («wer macht was») · MCP-Zugang (hier nur die Grundzüge) | offen |

Nach jeder Phase zwei Wochen im Alltag, dann Entscheid über die nächste.

## Entscheide (mit Datum)

- 03.11.2026 – Arbeitsweise: Claude führt, stellt Fragen mit Empfehlung; Clemens entscheidet.
- 03.11.2026 – Kein Zählen, keine Termine; Wichtiges bleibt oben am Ding. Das Werkzeug bewahrt
  Wissen, es führt keine Aufgaben. Keine Ausnahme für Sicherheit.
- 03.11.2026 – Die KI legt ab (auch aufgeteilt), der Mensch kontrolliert.
- 04.11.2026 – Ziel statt Regeln; Name «Erfassen»; Aufnehmen mit Start/Stopp; Wichtigkeit ohne
  feste Gründe.
- 05.11.2026 – Vier Schichten, das Log zuerst; **keine Rückwärtskompatibilität** für die heutigen
  Logs; Website-Messung als eigener Strom (BigQuery).
- 05.11.2026 – Gearbeitet wird nur im ERP; MCP höchstens als persönlicher Zugang für Clemens.
- 05.11.2026 – Kommunikation (Mails an Personen und Firmen) bleibt, wie sie ist.
- 05.11.2026 – «Auf einen Blick» an jedem Ding (Offenes + Wissen); Erfassen schlicht mit «neu
  anlegen» unten; Dokumente bleiben; berechnet bei Änderung. Noch nichts bauen – erst alles definieren.
- 05.11.2026 – «Offenes wartet am Ding» wird gebaut (Teil von Phase 3). Aufgaben, Website-Messung
  und MCP sind eigene Projekte; MCP hier nur in Grundzügen. Alles bleibt in dieser einen Akte.

- 05.11.2026 – «Auf einen Blick» ist eine Liste (Vorschläge mit Bestätigen/✕, Hinweise ohne), auf
  Abruf neu gebildet. Verlauf mit der Logik der Kommunikation. Dokumente behalten ihre Nummer.
  Auftrag an die KI: grobes Ziel, keine Regeln, sie lernt aus Korrekturen. Sprachdienst: Vorzug
  Google, Vergleich mit echten Aufnahmen.

## Offene Fragen

- Der Auftrag an die KI: Prüfung des Entwurfs an den drei Beispielen (Montage-Notiz,
  Meeting-Notiz, Kunden-Mail), sobald Phase 3 steht.
- Sprachtest: drei echte Aufnahmen (Notiz, Telefonat, Meeting) von Clemens.
- Folgeprojekt «Aufgaben» (wer macht was, Zuständigkeit je Prozessschritt).
