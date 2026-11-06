# Projektakte «Die lernende Firma»

> **Kopfstatus:** definiert, bereit zur Umsetzung · **Phase 1 (das Log) gebaut** (06.11.2026) ·
> Lead: Claude · Entscheid: Clemens Fritsche · seit 03.11.2026
> Mockup (1:1 im ERP): https://claude.ai/artifact/8jAy56JQ1jEESPwgRHPSSK
> Diese Akte ist die **eine** Quelle für Ziel, Regeln, Plan und Entscheide – sie beschreibt den
> gültigen Stand. Wie er entstand, steht in der Git-Geschichte dieser Datei und in
> `docs/history/2026-11-06-das-log.md`. Was hier nicht steht, ist nicht entschieden.

## 1 · Problem

Wissen entsteht überall – im Gespräch, auf Montage, in Mails, in Aufträgen. Das meiste bleibt im
Kopf, verändert sich bei jeder Übergabe (stille Post), ist später nicht auffindbar und geht mit den
Leuten. Rückmeldungen erreichen nicht, wer handeln kann, und ob eine Massnahme gewirkt hat, prüft
niemand. Die Firma lernt darum nicht verlässlich aus dem, was sie erlebt.

## 2 · Ziel

**Eine Firma, die nichts vergisst und sich von selbst verbessert – ohne dass jemand es managt oder
überwacht.**

Messpunkte (nach rund drei Monaten im Alltag, einmal von Hand aus dem Log ausgewertet):

1. **Erfassen unter 30 Sekunden** – jede Montage, jedes Kundengespräch hinterlässt eine Notiz.
2. **In 30 Sekunden gefunden** – was über einen Datensatz bekannt ist, steht dort, mit Quelle.
3. **Wichtiges ist nicht zu übersehen** – es ist am Datensatz angeheftet, bis es erledigt ist.
4. **Keine neue Insel** – Bestehendes wird zusammengeführt; es entsteht kein neuer Datentyp.

## 3 · Grundsätze

- **Die KI arbeitet nach dem Ziel, ein Mensch kontrolliert.** Keine Wenn-dann-Regeln, keine
  Kategorien, keine Listen – ein Auftrag (wer wir sind, was wir wollen) und echte Daten. Die KI
  schreibt nie selbst; sie schlägt vor, ein Mensch entscheidet.
- **Gearbeitet wird nur im ERP.** Eine Regel für alles, keine Ausnahmen.
- **Ein Wissenswerkzeug, kein Management-Werkzeug:** kein Dashboard, kein Rückblick, keine Termine.
  Wer was tut, regeln Aufträge; feste Zuständigkeit kommt mit dem Projekt «Aufgaben».
- **Die gerade Linie für alles, was festgehalten wird:**
  1. **Ein Weg für jede Eingabe:** gesprochen, geschrieben, fotografiert oder als Datei – die KI
     hört, liest oder sieht es und macht daraus **Text** (Abschrift, Bildbeschreibung, Inhalt).
     Dieser Text ist, was man wiederfindet und woraus das System lernt – auch beim Foto.
  2. **Bleibt das Original wichtig?** Nein → **Notiz** (eine Nachricht; vom Gesprochenen bleibt nur
     der Text). Ja → **Dokument** mit Nummer (Foto, Scan, Datei, Video – unterschreibbar,
     sendbar, in ein Pflichtfeld hängbar). Änderungen → **Log**. Etwas zu tun → **Auftrag**.
- **Nichts wird gelöscht, korrigiert wird** – wie überall im ERP.
- **Kultur** (Fehler melden ist sicher; wer meldet, hört, was daraus wurde) ist Teil des Ziels,
  kann aber nicht gebaut werden – sie wird vorgelebt.

## 4 · Aufbau in vier Schichten

| Schicht | Inhalt | Phase |
|---|---|---|
| 1 · **Das Log** | was geschehen ist – jede Handlung, eine Stelle | 1 (gebaut) |
| 2 · **Wissen am Datensatz** | ein Verlauf je Nummer: Nachrichten, Notizen, Dokumente, Änderungen | 2 |
| 3 · **KI** | ablegen, vorschlagen, anheften, lernen – mit den Rechten der Person | 3 |
| 4 · **Oberflächen** | «Erfassen» (Schreiben, Foto, Datei, später Sprache) | 3 + 4 |

### 4.1 · Das Log (gebaut, Migrationen 166/167)

Die eine, unveränderliche Wahrheit darüber, was geschah – Grundlage für den Verlauf, das Lernen,
das Angeheftete, Nachvollziehbarkeit (Buchungsbelege 10 Jahre) und Fehlersuche. Ersetzt
`audit_log` und `process_events` (keine Rückwärtskompatibilität).

- **Eine Tabelle `log`:** `at` (Datenbank-Zeit) · `actor_kind` (`person` · `ai` · `system` ·
  `external`) · `actor_id` (Objektnummer; bei `ai` die Person, in deren Namen) · `source` ·
  `request_id` (verbindet eine Handlung) · `object_id` (der Datensatz) · `table_name`/`row_key` ·
  `action` (`insert` · `update` · `delete` · `event`) · `event` · `changes` (nur Geändertes:
  `{feld: [alt, neu]}`) · `payload`. Indizes für Verlauf, Handlung, Person, Ereignis, Zeit.
- **Die Datenbank schreibt es selbst:** ein Trigger an jeder Tabelle (`domain/log`); Geheimes und
  Binäres nie im Klartext. **Ohne Handelnden scheitert jedes Schreiben** – gesetzt an einer Stelle
  (`core/actor`: Anmeldung, `public(…)` an öffentlichen Routen, Start, Migration).
- **Fachliche Ereignisse** (keine Zeilen-Änderung) über `services/log.event`, in derselben
  Transaktion: `ai.call`, `mail.send_failed`, `voucher.action`, `document.read` … Die Ereignisse
  des Prozesses stehen als `process.<art>` darin (gelesen über die Sicht `process_log`).
- **Unveränderlich** per Trigger (auch `TRUNCATE`). **Siegel:** je abgeschlossenem Tag eine
  verkettete Prüfsumme (`log_seal`, `log.verify`). `log.redact` (Schwärzen) steht bereit, wird aber
  nicht genutzt (Entscheid 06.11.2026).
- **Wächter** (`tests/test_log.py`, je gegen die Bug-Form geprüft): jede Tabelle hat den Trigger ·
  ohne Handelnden scheitert es · jede Route mit Datenbank nennt einen Handelnden · das Log ist
  unveränderlich · das Siegel bemerkt jede nachträgliche Änderung.
- Nicht partitioniert (ein Index trägt auf Jahre). Website-Messung ist ein eigener Strom (später).

### 4.2 · Wissen am Datensatz

- **Jede Nummer hat einen Verlauf** – eine Komponente für jeden Datensatz, gemischt nach Zeit:
  Nachrichten (Mail, Anruf, intern, **Notiz**), Dokumente, Änderungen aus dem Log. **In Seiten**
  wie WhatsApp (die neuesten 30, ältere beim Scrollen) – er wächst nie mit.
- **Eine Notiz ist eine Nachricht:** Betreff, Text, Zeit, beantwortbar, als Erinnerung möglich.
  «Betrifft» darf **jeder Datensatz** sein (`message_parties.object_id` statt
  `person_object_id`). **Eine Heimat:** gültig ist immer genau ein Datensatz. Gehört eine Notiz
  woandershin, erfasst man das; die KI schlägt einen Vermerk «ungültig, gehört zu …» am falschen
  und die Notiz mit Verweis am richtigen Datensatz vor – nichts wird gelöscht.
- **Änderungen technisch, nicht als Sätze:** je Handlung ein Block – wer · wann · Tabelle ·
  `feld: alt → neu`. Übersetzt werden nur die Tabellennamen (ein Wort je Tabelle).
- **Sichtbarkeit:** wer einen Datensatz öffnen darf, sieht seinen ganzen Verlauf.
- **Das Angeheftete** («auf einen Blick») steht im Verlauf **unten beim Neuesten** – kein eigener
  Bereich:
  - **offene Vorschläge immer und zuerst** – sie verschwinden nur durch einen Entscheid;
  - **Hinweise** (Einträge des Verlaufs, die jetzt wichtig sind) wählt die KI aus dem Ziel, so wenige
    wie möglich, **auf Abruf** («neu ansehen»); lösen kann sie jeder.
  Das Symbol kommt von der Art des Eintrags – keine Regel, keine Wahl der KI.
- **Kommunikation bleibt in der Bedienung, wie sie ist.** Andere Datensätze haben kein eigenes
  Eingabefeld – Wissen kommt über «Erfassen».
- **Die Kommunikation wird skalierbar** (geprüft 06.11.2026 – Struktur richtig, zwei Abfragen
  wachsen unbegrenzt): Verlauf in Seiten · das **Anliegen** (Betreff in Normalform) als Spalte mit
  Index, «offen» als Datenbank-Abfrage mit unveränderter Regel · ein **langer Wert** (über 2'000
  Zeichen) steht im Log als Prüfsumme (`sha256` + Länge) statt doppelt. Rundschreiben bleiben je
  Empfänger eine Nachricht (bewusst).

### 4.3 · KI

- **Die KI darf, was die Person darf, in ihrem Namen** – lesen frei im Rahmen der Rechte,
  schreiben nur als Vorschlag. Eine Tür: jeder Aufruf (Claude, Gemini, Hilfsmodell) über
  `services/ai.py` – ein Deckel, ein Log.
- **Ein Vorschlag steht dort, wo man es von Hand täte – nie ein eigenes Formular:**
  - **ändern:** das Zeichen wie bei «zu tun» am Datensatz im Feed, am Abschnitt und **am Feld**;
    darüberfahren oder tippen zeigt nur das Wesentliche (neuer Wert, Quelle, «Übernehmen», ✕).
    Übernehmen schreibt ins bestehende Feld – dieselbe Prüfung, dasselbe Auto-Save, dasselbe Log
    wie Tippen. Wer selbst tippt, erledigt ihn auch.
  - **anlegen:** «Entwurf öffnen» öffnet den bestehenden Entwurf vorausgefüllt; gespeichert wird
    erst mit der Freigabe.
  - **kein Feld auf dem Bildschirm:** im Angehefteten, mit demselben Fenster.
- **Ein Feld-Baustein für das ganze ERP:** das Speichern ist heute zentral (`lib/use-autosave`),
  das Feld nicht (rund 30 Dateien mit losen Eingaben). Darum: `useField` (Wert, Speichern, Prüfung,
  Fehler, Vorschlag) und `Field` (Text, Zahl, Datum, Auswahl, Mehrzeilig). **Logik zentral,
  Aussehen frei** – das Zahlungsmodul behält sein Aussehen, nutzt aber dieselbe Logik.
- **Gespeichert im Log, keine eigene Tabelle:** `proposal` (Datensatz, Feld bzw. Entwurf, Wert,
  Quelle) und `proposal.decided` (übernommen · selbst geändert · verworfen). Offen = ohne Entscheid.
  Offene Vorschläge zählen in «zu tun» und führen per Sprung zum Feld.
- **Robust:** Übernehmen = Tippen; weist das Feld ab, steht seine Meldung da; ist der Datensatz weg
  oder das Feld schon geändert, erledigt sich der Vorschlag; fällt die KI aus, bleibt die Eingabe
  roh am Datensatz und wird nachgeholt.
- **Lernen ohne Training – drei Gedächtnisse** (so arbeitet heute auch Claude selbst):
  1. **Wissen** – alles im ERP; die KI schlägt nach. Erster Hinweis: der Datensatz, der beim
     Erfassen offen ist (nur seine Nummer).
  2. **Erfahrung** – jeder Vorschlag mit Entscheid ist ein **Fall**; die KI bekommt die
     **ähnlichsten** Fälle mit. Gefunden über Bedeutungs-Zahlen (Hilfsmodell von Google Vertex AI,
     Region Europa; gespeichert mit `pgvector` in der eigenen Datenbank). Nichts wird vergessen.
  3. **Lektionen** – ein kurzes Notizbuch, das die KI selbst aus ihren Fällen verdichtet (mit
     Belegen); Clemens kann es lesen und kürzen. Ab rund 100 Fällen.
  Massstab: wie oft ein Vorschlag geändert oder verworfen wird.
- **Deckel in Franken:** 10 CHF je Tag für alle KI-Aufrufe, Hinweis bei 80 %. Am Deckel bleibt die
  Eingabe roh und wird am nächsten Tag nachgeholt.

**Der Auftrag an die KI** (versioniert im Repository, gilt für Ablegen, Vorschläge, Angeheftetes):

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

Bewusst nicht drin: Gründe, Beispiele für Wichtigkeit, Kategorien. Wächst der Text, wachsen Regeln
hinein – dann zurück aufs Ziel. Geprüft wird er an den drei Beispielen (Montage-Notiz Hans-Peter,
Meeting Heiri, Kundenmail).

### 4.4 · Oberflächen

- **«Erfassen»** – ein Knopf «+»: oben rund festhalten (Aufnehmen · Foto · Datei · Schreiben),
  unten eckig neu anlegen (Person, Firma, Artikel, Auftrag – in den Farben des Feeds). Foto und
  Datei öffnen den bestehenden Dokument-Entwurf.
- **«Abgelegt»** – schlicht: je Teil der Datensatz (antippen = anderer) und der Text; «Stimmt so».
  Ein Meeting wird in Teile mit je einer Heimat geteilt.
- **Aufnehmen im Browser:** Start/Stopp, auch ein ganzes Meeting; der Bildschirm bleibt an (Wake
  Lock); die Aufnahme geht **in Stücken** (alle 30 s) hoch – bricht sie ab, ist alles bis dahin da.
  Gespräche aufnehmen: Clemens trägt die Verantwortung. Ohne Netz wird nichts vorgesehen.
- **Abschreiben macht Gemini** (Test Clemens 06.11.2026: hervorragend, auch Mundart) über
  **Vertex AI**, Region Europa (Eingaben nicht zum Training); die Claude-API nimmt keine
  Audiodateien. **Verstehen und ablegen macht Claude.** Das Audio wird nach der Abschrift gelöscht
  (spätestens nach einem Tag, Regel im Speicher). Verarbeitet wird im Namen der Person, die
  aufgenommen hat.

### 4.5 · Infrastruktur: der Takt

**Cloud Scheduler ruft alle 5 Minuten, Tag und Nacht, `POST /internal/tick`** – eigenes Dienstkonto
nur mit diesem Recht, Anmeldung per Google-Token (OIDC), kein Geheimnis im Code, eingerichtet im
Deploy. Aufgaben: **Mails holen und senden** (auch ohne offenen Browser) · **Aufnahmen abschreiben
und ablegen** · **das Siegel des Logs**. Jede Aufgabe wiederholbar, einzeln gesperrt, mit
Zeitgrenze; Handlungen stehen im Log; mehrere Fehlschläge hintereinander → Mail von Cloud
Monitoring. Kosten ≈ 0 CHF (im Gratis-Kontingent).

Geprüft und verworfen: Pub/Sub ersetzt den Takt nicht (Gmail-Push ist laut Google nicht garantiert,
die Anmeldung läuft nach 7 Tagen ab) – höchstens später als Beschleuniger.

## 5 · Review gegen das Ziel (06.11.2026)

| Messpunkt | Wie | Stand |
|---|---|---|
| 1 · Erfassen < 30 s | ein Knopf, die KI legt ab, «Stimmt so» | erreicht |
| 2 · Gefunden < 30 s | alles am Datensatz, Verlauf in Seiten, Angeheftetes | **teilweise** – man muss wissen, bei welchem Datensatz (Fragen im Erfassen: später) |
| 3 · Nicht zu übersehen | Angeheftetes, offene Vorschläge zuerst, «zu tun» | **teilweise** – wartet am Datensatz, nicht bei der zuständigen Person («Aufgaben») |
| 4 · Keine neue Insel | Notiz = Nachricht, Vorschlag = Log, ein Feld-Baustein | erreicht |

**Verbessert sich von selbst:** kommt ein ähnliches Problem wieder, findet die KI über ihre
Erfahrung den früheren Fall samt Massnahme und heftet ihn an.

**Richtiger Weg:** ja. Verworfen: ein Wiki (neue Insel) · ein Chat-Assistent als Ort des Wissens
(Wissen läge in Gesprächen statt am Datensatz) · Regeln und Kategorien (veralten) · ein
nachtrainiertes Modell (teuer, modellgebunden).

**Nachhaltig:** modellunabhängig (Auftrag, Fälle, Lektionen sind Daten) · wächst ohne Pflege (keine
Listen; jedes neue Feld kann Vorschläge) · robust (Ausfälle warten und werden nachgeholt, nichts wird
gelöscht) · skaliert (Seiten, Indizes, Bedeutungssuche in der eigenen Datenbank).

## 6 · Plan

| Phase | Inhalt | Stand |
|---|---|---|
| 1 | **Das Log** | gebaut (06.11.2026) |
| 2 | **Fundament:** Feld-Baustein · Prüfsumme im Log · Kommunikation skalierbar · Notiz an jedem Datensatz · ein Verlauf · der Takt | als Nächstes |
| 3 | **KI:** Lesen · Erfassen · Ablegen · Vorschläge · Angeheftetes · Lernen (Wissen + Erfahrung) · Deckel | offen |
| 4 | **Sprache:** Aufnehmen · Gemini · der Takt legt ab | offen |
| danach | Lektionen (ab ~100 Fällen) · Fragen im Erfassen · Projekt «Aufgaben» (Zuständigkeit je Prozessschritt) | offen |
| später | Suche in Inhalten · Website-Messung (BigQuery) · MCP-Zugang (nur für Clemens) | offen |

**Jede Phase:** Feature-Branch · Volltest · unabhängiges Gegenlesen · Deploy auf dev · Doku
nachgezogen · danach zwei Wochen im Alltag, dann Entscheid über die nächste.

### Schritte je Phase («fertig, wenn …»)

**Phase 2 · Fundament**

| # | Schritt | Fertig, wenn … |
|---|---|---|
| 2.1 | **Feld-Baustein:** `useField` + `Field`; alle bearbeitbaren Felder ziehen um; das Zahlungsmodul behält sein Aussehen | ein ESLint-Wächter findet keine lose Eingabe mehr · alle Tests grün · Detailseiten sehen aus wie vorher (Bildvergleich) |
| 2.2 | **Langer Wert als Prüfsumme im Log** | Wächter-Test mit einer langen Mail · `log.verify` grün |
| 2.3 | **Kommunikation skalierbar:** Seiten · Anliegen-Spalte mit Index · «offen» als Abfrage | Kommunikations-Tests unverändert grün · mit 50'000 Nachrichten: Seite < 200 ms, «zu tun» < 300 ms |
| 2.4 | **Notiz an jedem Datensatz:** `message_parties.object_id` (Zwei-Deploy-Regel) · Kanal «Notiz» · Korrektur per Vermerk | Notiz an Auftrag, Artikel, Instanz, Dokument erscheint in deren Verlauf; Korrektur zeigt Vermerk und Verweis |
| 2.5 | **Ein Verlauf für jeden Datensatz:** ein Endpunkt, eine Komponente, ein Wörterbuch der Tabellennamen | jeder Datensatztyp zeigt ihn · je Handlung ein Block `feld: alt → neu` |
| 2.6 | **Der Takt** (Mails, Siegel), eingerichtet im Deploy | auf dev kommen Mails ohne offenen Browser · je Tag ein Siegel · Alarm gegengeprüft |

**Phase 3 · KI**

| # | Schritt | Fertig, wenn … |
|---|---|---|
| 3.1 | **Lese-Werkzeuge** (Datensatz, Verlauf, Nummer/Name) mit den Rechten der Person | Test: die KI sieht nie mehr als die Person |
| 3.2 | **Erfassen** («+», Schreiben, Foto/Datei, neu anlegen; offener Datensatz als Hinweis) | auf dem Handy eine Notiz in unter 30 s |
| 3.3 | **KI legt ab** (Teile mit Heimat, «Abgelegt», «Stimmt so») | die drei Beispiele laufen durch |
| 3.4 | **Vorschläge** (`proposal`/`decided`, Zeichen in `useField`, Entwurf vorausgefüllt, feldlose im Angehefteten, «zu tun») | Übernehmen = Tippen · selbst getippt erledigt ihn · zwei gleichzeitig: beide im Log |
| 3.5 | **Das Angeheftete** (offene Vorschläge immer zuerst, Hinweise auf Abruf) | «neu ansehen» nimmt nie einen offenen Vorschlag weg |
| 3.6 | **Lernen – Wissen + Erfahrung** (Bedeutungs-Zahlen, ähnlichste Fälle) | nach einer Korrektur schlägt die KI im ähnlichen Fall anders vor |
| 3.7 | **Deckel in Franken** | am Deckel bleibt die Eingabe roh und wird nachgeholt |

**Phase 4 · Sprache**

| # | Schritt | Fertig, wenn … |
|---|---|---|
| 4.1 | **Aufnehmen im Browser** (Bildschirm an, Stücke alle 30 s, Löschregel 1 Tag) | Abbruch nach 10 Min. → die 10 Min. sind da |
| 4.2 | **Gemini schreibt ab** (Vertex AI, Region Europa, über `services/ai.py`) | eigene Testaufnahmen in Mundart: Namen und Zahlen stimmen |
| 4.3 | **Der Takt legt ab** (im Namen der Person; «Abgelegt» erscheint bei ihr) | eine Aufnahme von 1 Stunde läuft auf dev durch · Audio danach gelöscht |

## 7 · Entscheide

Der gültige Stand jedes Entscheids steht in den Abschnitten oben; hier die Liste zum Nachschlagen.

| Datum | Entscheid |
|---|---|
| 03.11. | Claude führt und empfiehlt, Clemens entscheidet. Kein Zählen, keine Termine. Die KI legt ab, der Mensch kontrolliert. Keine Ausnahme, auch nicht für Sicherheit. |
| 04.11. | Ziel statt Regeln. Name «Erfassen». Aufnehmen mit Start/Stopp. |
| 05.11. | Vier Schichten, das Log zuerst, keine Rückwärtskompatibilität. Nur im ERP; MCP höchstens persönlich für Clemens. Kommunikation bleibt in der Bedienung. Dokumente behalten ihre Nummer. Alles in einer Akte. |
| 06.11. | Phase 1 gebaut und ausgerollt. |
| 06.11. | Notiz = Nachricht an jedem Datensatz; das Log bleibt Protokoll. Verlauf in Seiten, Änderungen technisch. Sichtbarkeit nur auf Ebene des Datensatzes. Kommunikation skalierbar, langer Wert als Prüfsumme. |
| 06.11. | Vorschläge am Feld bzw. als vorausgefüllter Entwurf, kein eigenes Formular; minimales Fenster. Feld-Baustein: Logik zentral, Aussehen frei (Aufräumen ist Pflicht). |
| 06.11. | Angeheftetes unten im Verlauf; offene Vorschläge immer und zuerst; Hinweise auf Abruf. |
| 06.11. | Lernen mit drei Gedächtnissen (ohne Prüfsatz); Hilfsmodell von Google Vertex. Offener Datensatz als schlanker Hinweis. |
| 06.11. | Der Takt per Cloud Scheduler (5 Min.), Pub/Sub nicht. Deckel 10 CHF/Tag. |
| 06.11. | Sprache: Gemini über Vertex AI; Bildschirm bleibt an, Aufnahme in Stücken; Audio nach der Abschrift gelöscht; Gespräche aufnehmen in Verantwortung von Clemens. |
| 06.11. | Gerade Linie: ein Weg für jede Eingabe; Original wichtig → Dokument, sonst Notiz. Nichts löschen, korrigieren. |
| 06.11. | Plan in drei Phasen mit Schritten. Zurückgestellt: Suche in Inhalten, Fragen im Erfassen, Rückmeldung an Personen (→ «Aufgaben»). Nicht gemacht: Schwärzen, Ziel-Dashboard, Arbeiten ohne Netz. |
