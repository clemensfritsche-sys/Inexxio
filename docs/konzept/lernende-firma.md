# Projektakte «Die lernende Firma»

> **Kopfstatus:** Konzept, in Arbeit; **Phase 1 (das Log) gebaut** (06.11.2026) · Lead: Claude · Entscheid: Clemens Fritsche · seit 03.11.2026
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
2. **In 30 Sekunden gefunden** – was über einen Datensatz bekannt ist, steht dort, mit Quelle.
3. **Wichtiges ist nicht zu übersehen** – es steht oben am Datensatz, bis es erledigt oder überholt ist.
4. **Keine neue Insel** – bestehende Funktionen werden zusammengeführt, keine kommt dazu.

## Grundsatz

**Die KI arbeitet nach dem Ziel, ein Mensch kontrolliert.** Sie bekommt keine Wenn-dann-Regeln,
sondern einen Auftrag (wer wir sind, was wir erreichen wollen) und darf, was die Person darf.
Gearbeitet wird **nur im ERP** – Mitarbeitende erfassen dort, die KI verarbeitet im Hintergrund.

## Aufbau in vier Schichten

| Schicht | Inhalt | Reihenfolge |
|---|---|---|
| 1 · **Das Log** | was geschehen ist – jede Handlung, eine Stelle | zuerst |
| 2 · **Wissen am Datensatz** | der Verlauf: Nachrichten, Notizen, Dokumente und Änderungen an der Objektnummer | danach |
| 3 · **KI-Werkzeuge** | die KI darf, was die Person darf, in ihrem Namen | danach |
| 4 · **Oberflächen** | «Erfassen» im ERP; optional ein MCP-Zugang für Claude (nur Clemens) | zuletzt |

## 1 · Das Log

**Zweck:** die eine, vollständige, unveränderliche Wahrheit darüber, was im System geschehen
ist – Grundlage für den Verlauf am Datensatz, für das Lernen der KI aus Korrekturen, für «Relevant
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
| Woran | Objektnummer des Datensatzes (und die Zeile, falls es keine Nummer hat) |
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

### Technische Spezifikation (gebaut, Migration 166)

**Tabelle `log`** (nicht partitioniert, siehe «Abweichungen vom Entwurf»):

| Spalte | Typ | Inhalt |
|---|---|---|
| `id` | bigint | fortlaufend |
| `at` | timestamptz | `now()` der Datenbank |
| `actor_kind` | text | `person` · `ai` · `system` · `external` |
| `actor_id` | bigint | Objektnummer der handelnden Person (bei `ai`: die Person, in deren Namen) |
| `source` | text | `ui` · `capture` · `web` · `link` · `webhook` · `login` · `probe` · `job` · `start` · `migration` · `mcp` · `test` |
| `request_id` | uuid | verbindet alle Einträge einer Handlung |
| `object_id` | bigint | Objektnummer des Datensatzes, falls die Zeile eine hat oder an einem hängt |
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

**Abweichungen vom Entwurf (beim Bauen entschieden):**
- **Keine Partitionierung.** Bei unseren Mengen (einige hunderttausend Einträge im Jahr) trägt
  ein Index auf `(object_id, at)` auf Jahre; Monats-Partitionen bräuchten einen Job, der sie
  rechtzeitig anlegt – eine Stelle mehr, die vergessen werden kann. Nachrüstbar, wenn das Log
  in die zig Millionen geht.
- **Versiegelt wird beim Start und im Abgleich** (`POST /erp/messages/sync`, läuft, solange das
  ERP offen ist) statt «nachts per Job» – es gibt keinen Zeitplaner, und ein Tag wird erst sechs
  Stunden nach Mitternacht (UTC) versiegelt, damit keine laufende Transaktion fehlt.
- **Wer handelt, sagt jede Route ausdrücklich** (`get_current_user` oder `public(…)`); der
  Wächter prüft das **für jede Route** statt «jede schreibende Route hinterlässt einen Eintrag»
  – eine Anfrage, die nichts ändert, braucht keinen.
- **Die Ereignisse des Prozesses** stehen als `process.<art>` im Log; Bild, Protokoll, Stückliste
  und Journey lesen sie unverändert über die Sicht `process_log`. Die bisherigen Einträge sind
  übernommen (der Invarianten-Bericht ist vor und nach der Umstellung Zeichen für Zeichen gleich).
- **Lesen sensibler Daten:** `document.read` (ERP), `document.viewed` und `voucher.viewed` (Link
  der Partei), `ai.call` (KI). Dateien hinter einem Token (`/attachments/…`) tragen keinen
  Menschen – ihr Abruf steht nicht im Log.
- **`audit_log` und `process_events`** standen einen Deploy lang ungemappt da und sind mit
  Migration 167 gefallen (Zwei-Deploy-Regel; vorher holte sie nach, was die alte Fassung beim
  Ausrollen noch schrieb).

**Website-Messung ist ein eigener Strom, nicht das Log.** Klicks und Wege von anonymen Besuchern
sind Messdaten, keine Handlungen im System – viel mehr, kurzlebiger, anonym. Sie gehen in
**BigQuery** (gebaut für genau solche Mengen und Auswertungen, günstig bei unseren Zahlen); das ERP
liest daraus verdichtete Zahlen, nicht jede Zeile. Wird aus einem Besucher ein Kunde (Anfrage),
beginnt seine Spur im Log.

## 2 · Wissen am Datensatz

- **Jeder Datensatz hat eine Nummer, jede Nummer einen Verlauf.** Der Verlauf zeigt, was zu ihm
  gehört, gemischt nach Zeit: **Nachrichten** (Mail, Anruf, intern, **Notiz**), **Dokumente** und
  **Änderungen** (aus dem Log).
- **Eine Notiz ist eine Nachricht.** Sie hat Betreff, Text, Zeitpunkt, kann eine Erinnerung sein,
  beantwortet werden und – wenn sie falsch ist – gelöscht werden (weich). «Betrifft» darf **jeder
  Datensatz** sein: Person, Firma, Auftrag, Artikel, Instanz, Dokument … (in `message_parties`
  heisst die Spalte künftig `object_id` statt `person_object_id`). Das Log bleibt reines
  Protokoll dessen, was geschah – kein Inhaltsspeicher.
- **Eine Heimat:** jeder Eintrag gehört genau einem Datensatz; nichts wird doppelt abgelegt. Eine
  Aufnahme mit mehreren Themen (z. B. ein Meeting) teilt die KI in Teile, jeder mit seiner Heimat.
- **Datensatz oder Eintrag:** Ein Datensatz (mit Nummer) hat einen eigenen Zustand oder wird von
  anderswo angesprochen. Notiz → Nachricht (Eintrag). Änderung → Log. Foto, Scan, Datei, Video →
  Dokument. Etwas zu tun → Auftrag (immer mit Stücken; Immaterielles über einen Artikel, z. B.
  «Website»).
- **Der Verlauf lädt in Seiten** (wie WhatsApp): die neuesten 30, ältere beim Scrollen, über einen
  Index auf (Datensatz, Zeit). Er wächst nie mit. Eine Komponente für jeden Datensatz.
- **Änderungen erscheinen technisch, nicht als Sätze:** eine Handlung (dieselbe `request_id`) ist
  ein Block – wer · wann · Tabelle · `feld: alt → neu`. Übersetzt werden nur die Tabellennamen
  (ein schlankes Wörterbuch, ein Wort je Tabelle); Feldnamen bleiben, wie sie sind. Keine
  Sonderfälle je Ereignis.
- **Sichtbarkeit:** wer einen Datensatz öffnen darf, sieht seinen ganzen Verlauf. Zugriff wird nur
  auf Ebene des Datensatzes geregelt, nicht innerhalb.
- **«Auf einen Blick» ist das Angeheftete oben im Verlauf** – kein eigener Bereich, eine
  Komponente mit dem Verlauf (wie angeheftete Nachrichten). Angeheftet sind Einträge des
  Verlaufs (Notiz, Mail, Dokument) und offene Vorschläge, Wichtiges zuerst, so wenige wie möglich –
  auch keiner. Das Symbol kommt von der **Art des Eintrags**, nicht von einer Regel und nicht von
  der KI. Was angeheftet wird, entscheidet die KI aus dem Ziel; lösen kann es jeder.
- **Auf Abruf, nicht bei jedem Öffnen:** die KI bildet das Angeheftete neu, wenn jemand «neu
  ansehen» drückt; bis dahin steht der letzte Stand mit Zeit da. Offene Vorschläge stehen immer
  da, ohne KI-Aufruf.
- **Dokumente behalten ihre Nummer** (eigener Zustand, von anderswo angesprochen, Nachweis); im
  Verlauf erscheinen sie als Eintrag.
- **Wichtiges bleibt oben**, bis es erledigt oder überholt ist. Wichtigkeit beurteilt die KI aus
  dem Ziel und echten Daten, nicht durch Zählen.
- **Audio wird nicht gespeichert** (wörtliches Transkript und KI-Fassung bleiben), **Video
  bleibt im Original**.
- **Kommunikation bleibt in der Bedienung, wie sie ist:** Mails an Personen und Firmen schreibt
  man dort. Andere Datensätze haben kein eigenes Eingabefeld – Wissen kommt über «Erfassen».

### Die Kommunikation wird skalierbar (zuerst, Teil von Phase 2)

Geprüft am 06.11.2026: die Datenstruktur (`messages` + `message_parties`, unveränderlich,
Dubletten per Index) ist richtig. Zwei Abfragen wachsen aber mit der Zeit unbegrenzt, eine Stelle
speichert doppelt:

1. **Der Verlauf lädt heute alles** (jede Nachricht seit Beginn) → Seiten wie oben.
2. **Die «zu tun»-Zahl rechnet über alle Nachrichten seit Beginn**, bei jedem Abruf → das
   **Anliegen** (Betreff in Normalform, `domain/communication.topic`) wird eine eigene Spalte mit
   Index. Die Regel «offen» bleibt Wort für Wort dieselbe, läuft aber als Datenbank-Abfrage nur
   über Anliegen, die noch offen sein können. Keine zweite Wahrheit: eine Nachricht ändert sich nie,
   also ändert sich ihr Anliegen nie.
3. **Grosse Werte stehen im Log doppelt** (das Mail-HTML beim Anlegen) – ein Fehler aus Phase 1.
   Lösung nach Stand der Technik: ein langer Wert (über 2'000 Zeichen) steht im Log als
   **Prüfsumme** (`{"sha256": …, "len": …}`) statt als Inhalt. Eine Regel für alle Spalten, keine
   Liste; die Unveränderlichkeit bleibt beweisbar (der Wert in seiner Zeile muss zur Prüfsumme
   passen).
4. Rundschreiben bleiben je Empfänger eine eigene Nachricht (bewusst: im Verlauf steht, was
   hinausging).

## 3 · KI-Werkzeuge

- **Die KI darf, was die Person darf, in ihrem Namen** – über dieselben Wege und Prüfungen wie die
  Oberfläche, kein zweiter Code. Ihre Handlungen sind die Handlungen des ERP selbst; mit jedem
  neuen Feature kann sie es von selbst auch. Keine eigene, feste Liste.
- **Lesen frei (im Rahmen der Rechte), Schreiben als Vorschlag.** Was die KI ändern oder anlegen
  will, wird ein Vorschlag; ein Mensch bestätigt oder verwirft. (Ob einzelne Handlungen später
  ohne Bestätigung laufen dürfen, entscheiden wir mit Erfahrung.)
- **Ein Vorschlag öffnet nie ein eigenes Formular – er steht dort, wo man es von Hand täte.**
  Die eine Wahrheit bleibt das bestehende Feld mit seiner Prüfung und seinem Auto-Save; nichts
  wird nachgebaut (Mockup «Vorschlag am Feld»):
  - **Etwas ändern** (ein Wert an einem Datensatz): das Zeichen wie bei «zu tun» steht am
    Datensatz im Feed, am Abschnitt und **am Feld selbst**. Darüberfahren oder Tippen zeigt den
    Vorschlag – **nur das Wesentliche:** der neue Wert, eine Zeile Quelle, «Übernehmen», ✕ (das
    Feld zeigt den jetzigen Wert ja schon). «Übernehmen» schreibt den Wert ins Feld – das Feld
    speichert wie immer. Wer selbst tippt, erledigt den Vorschlag damit auch.
  - **Etwas anlegen** (Auftrag, Notiz an einem anderen Datensatz …): «Entwurf öffnen» öffnet den
    **bestehenden** Entwurf vorausgefüllt; freigegeben wird wie immer.
  **Ein Feld-Baustein für das ganze ERP.** Analyse 06.11.2026: das **Speichern** ist zentral
  (`lib/use-autosave.ts`, ein Saver für alles); das **Feld** nicht – `components/form/field.tsx`
  gibt es, genutzt wird es in 5 Dateien, in rund 30 Dateien stehen lose `<input>`/`<select>`
  (am meisten: Prozess-Editor, Beleg, Artikel, Dokument-Entwurf). **Aufräumen ist Pflicht und
  der erste Schritt:** ein `Field` für Text, Zahl, Datum, Auswahl und Mehrzeilig – Beschriftung,
  Pflicht-Stern, weiche Prüfung, Fehlermeldung, Vorschlags-Zeichen –, alle bearbeitbaren Felder
  ziehen darauf um, ein Wächter (ESLint) verbietet lose Eingaben in Datensätzen. Danach kann jedes heutige und künftige Feld Vorschläge von selbst; dazu «Entwurf
  vorausgefüllt öffnen» einmal für alle Entwürfe.
- **Was gespeichert wird:** je Vorschlag ein Log-Eintrag `proposal` – bei einer Änderung
  Datensatz, Feld (derselbe Name wie im Auto-Save) und neuer Wert; bei einer Anlage die Art des
  Entwurfs und seine Werte. Dazu die Quelle. Entschieden: `proposal.decided` (übernommen ·
  selbst geändert · verworfen). Offen = ohne Entscheid (Ableitung); «selbst geändert» erkennt das
  System daran, dass das Log eine spätere Änderung genau dieses Felds kennt.
- **Offene Vorschläge** zählen in der «zu tun»-Zahl des Datensatzes (gibt es schon) und führen per
  Sprung zum Feld (gibt es schon: `jumpToTodo`). Nichts muss sofort erledigt werden.
- **Robustheit:** Übernehmen ist dasselbe wie Tippen – dieselbe Prüfung, dasselbe Log; weist das
  Feld den Wert ab, steht die Meldung des Felds da. Zwei Personen gleichzeitig: wie heute beim
  Auto-Save, die spätere Änderung gilt, beide stehen im Log. Ist der Datensatz inzwischen gelöscht
  oder das Feld schon geändert, erledigt sich der Vorschlag von selbst. Fällt die KI aus, bleibt die
  Notiz unverarbeitet am Datensatz und wird nachgeholt.
- **Der Auftrag an die KI** ist ein einziger, versionierter Text im Repository (Entwurf unten). Er
  gibt ein grobes Ziel, keine Regeln und keine Kategorien. Alles Weitere holt sich die KI selbst:
  sie liest, was im ERP steht (im Rahmen der Rechte), und lernt aus dem, was Menschen mit ihren
  Vorschlägen getan haben.
- **Sie lernt ständig, ohne Training:** vor einem neuen Vorschlag bekommt sie die **letzten rund 20
  Entscheide** als Beispiele mit: was sie vorschlug, was der Mensch daraus machte (übernommen,
  anders getippt, verworfen). Wie ein neuer Mitarbeiter, der vor der Arbeit die letzten
  Korrekturen des Chefs liest. Ändert sich, wie wir es wollen, ändern sich die Beispiele von selbst. Keine Kategorien, keine Regeln, keine Suchmaschine –
  die Beispiele stehen schon im Log. Weniger Korrekturen = bessere KI; das ist zugleich der
  Massstab.

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
> Wenn jemand einen Datensatz öffnet, zeig, was für ihn jetzt wichtig ist, mit Quelle – so wenig wie
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
  (gibt es schon), und ein Dokument erscheint als Eintrag im Verlauf seines Datensatzes.
- **Die KI legt ab, der Mensch kontrolliert** («Stimmt so» oder «ändern»), auch im Datensatz.
- **Spracherfassung** von Anfang an, mit einem professionellen, robusten Dienst (Mundart).
  Vorzug für Google (unser Cloud-Projekt, Daten in Europa). Das Hören ist ein eigener Dienst; das
  Verstehen und Ablegen bleibt bei Claude über `services/ai.py`.

- **Lange Aufnahmen laufen im Hintergrund:** hochladen → Google schreibt ab (Minuten) → der
  **Takt** sieht nach, ob die Abschrift fertig ist, und gibt sie der KI → der Vorschlag erscheint
  am Datensatz. Ohne Netz wird nichts vorgesehen.

### Der Takt (Infrastruktur)

**Cloud Scheduler ruft alle 5 Minuten, Tag und Nacht, eine geschützte Adresse des ERP**
(`POST /internal/tick`, angemeldet mit einem Google-Dienstkonto per OIDC, kein Geheimnis im Code).
Er erledigt, was nicht an einem offenen Browser hängen darf:
- **neue Mails holen und Fälliges senden** – auch, wenn niemand das ERP offen hat (heute nur,
  solange ein Browser offen ist);
- **fertige Abschriften abholen** (siehe oben);
- **das Siegel des Logs** (einmal je Tag, die Prüfsumme aus Phase 1).
Jede Aufgabe ist wiederholbar und einzeln gesperrt; scheitert eine, läuft sie beim nächsten Takt.

Geprüft (06.11.2026): Pub/Sub (Google meldet sich selbst) ersetzt den Takt nicht – Google nennt
Gmail-Push nicht garantiert und verlangt regelmässiges Nachfragen; die Push-Anmeldung läuft nach 7
Tagen ab. Push wäre nur ein Beschleuniger – erst, wenn 5 Minuten stören.
**Kosten:** Cloud Scheduler 3 Aufträge gratis; 288 kurze Aufrufe je Tag bleiben im
Gratis-Kontingent von Cloud Run (bezahlt wird nur Rechenzeit während einer Anfrage). ≈ 0 CHF.

### Vergleich der Sprachdienste (Test, vor Phase 4)

| Kandidat | Was er ist |
|---|---|
| Google Speech-to-Text v2, Modell Chirp | reiner Transkriptionsdienst, Sprache «Deutsch (Schweiz)» |
| Gemini auf Vertex AI (Flash) | hört die Aufnahme und schreibt sie wörtlich auf (Audio als Eingabe) |
| ein Nicht-Google-Dienst als Massstab | nur zum Vergleich, falls beide Google-Dienste schwächeln |

**Clemens testet selbst, ohne Code** (nur eigene Test-Aufnahmen ohne Kundendaten – im kostenlosen
AI Studio darf Google Eingaben zur Verbesserung nutzen): Google Cloud Console (Projekt `inexxio-dev`) →
«Speech-to-Text» → «Transkriptionen» → Datei hochladen, Modell Chirp 3, Deutsch (Schweiz), Region
Europa; und aistudio.google.com → Audio hochladen → «Schreibe diese Aufnahme wörtlich auf, mit
Sprechern». Getestet mit **drei echten Aufnahmen** von uns: eine Notiz (1 Min., Halle mit Lärm), ein Telefonat
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
| 1 | **Das Log** – neu, ersetzt alle heutigen Logs | gebaut (06.11.2026) |
| 2 | Kommunikation skalierbar (Seiten, Anliegen-Spalte, Prüfsumme im Log) · Notiz an jedem Datensatz · Verlauf an jeder Nummer | offen |
| 3+4 | **ein Durchstich:** «Erfassen» (zuerst Schreiben) → KI legt ab → Vorschläge am Feld → Lernen; danach Sprache (nach dem Test) mit Pub/Sub | offen |
| 5 | Das Angeheftete im Verlauf (auf Abruf) | offen |
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

- 06.11.2026 – Phase 1 bauen und auf dev ausrollen (das Log); Spielraum für Verbesserungen beim
  Bauen.

- 06.11.2026 – Notiz = Nachricht, «Betrifft» jeder Datensatz; das Log bleibt Protokoll. Verlauf
  in Seiten, Änderungen technisch, schlankes Wörterbuch nur für Tabellennamen. Wer den Datensatz
  öffnen darf, sieht den ganzen Verlauf. Kommunikation skalierbar machen (zuerst). Langer Wert im
  Log als Prüfsumme. Vorschlag = gespeicherter ERP-Aufruf, im Log, eine Darstellung für alle.
  Lernen: letzte ~20 Entscheide als Beispiele. Phase 3 und 4 als ein Durchstich. Ohne Netz und Ziel-Messung werden nicht vorgesehen. Wort: «Datensatz» statt «Ding».

- 06.11.2026 – Takt per Cloud Scheduler (5 Min., Tag und Nacht); Pub/Sub nicht. Feld-Baustein
  für das ganze ERP (Aufräumen ist Pflicht, erster Schritt). «Auf einen Blick» = das Angeheftete
  oben im Verlauf; Symbol aus der Art des Eintrags. «Abgelegt» schlicht: je Teil Datensatz + Text.
- 06.11.2026 – Vorschläge stehen am Feld (Zeichen wie «zu tun», Fenster beim Darüberfahren,
  «Übernehmen» schreibt ins bestehende Feld) bzw. öffnen den bestehenden Entwurf vorausgefüllt –
  kein eigenes Formular.

## Offene Fragen

- Der Auftrag an die KI: Prüfung des Entwurfs an den drei Beispielen (Montage-Notiz,
  Meeting-Notiz, Kunden-Mail), sobald Phase 3 steht.
- Sprachtest: Clemens testet selbst (Anleitung oben) und meldet, was Namen, Zahlen, Fachwörter
  trafen.
- Schwärzen einer Person: welche Einträge gehören alle zu ihr (bewusst offen).
- **Lernen der KI** – Vorschlag drei Gedächtnisse (Wissen · ähnlichste Fälle · eigene Lektionen)
  plus ein **Prüfsatz** echter Fälle; Entscheid ausstehend.
- **Aufnehmen von Gesprächen:** Telefonate und Gespräche mit Aussenstehenden dürfen in der Schweiz
  nur mit Einwilligung aller aufgenommen werden (StGB Art. 179bis/ter) – wie fragen wir, wo steht
  es? Interne Meetings: alle wissen es.
- **Aufnahme im Browser bei gesperrtem Bildschirm:** ein Browser (vor allem iPhone) hält die
  Aufnahme an, wenn der Bildschirm ausgeht. Lösung: Bildschirm während der Aufnahme wach halten
  (Wake Lock) – oder später eine App.
- **Suchen («in 30 Sekunden gefunden»):** heute findet die Suche Datensätze über Nummer und Name,
  nicht Inhalte von Notizen und Mails. Vorschlag: dieselbe Bedeutungssuche wie beim Lernen, über
  Notizen, Mails, Dokumente – ein Suchfeld.
- **Notiz verschieben:** falsch abgelegt und schon bestätigt → «Betrifft» ändern (gewöhnliche
  Änderung, steht im Log).
- **KI-Deckel:** heute 300 Aufrufe je Tag; mit Erfassen und Meetings neu festlegen (Kosten je
  Notiz ≈ 1–3 Rp., Abschrift ≈ 2 Rp. je Minute).
- Folgeprojekt «Aufgaben» (wer macht was, Zuständigkeit je Prozessschritt).
