# Phase 5 · Der Assistent – Bauplan

> **Kopfstatus:** entschieden (08.11.2026), noch nicht gebaut · gehört zur Projektakte
> `docs/konzept/lernende-firma.md` (§6 Phase 5). Mockup und Konzept (Runde 14):
> https://claude.ai/artifact/8jAy56JQ1jEESPwgRHPSSK
> **Ersetzt**, sobald gebaut: Erfassung, Vorschläge, «Stimmt so», das Zeichen am Feld und die
> Hinweise aus `docs/konzept/phase3-bauplan.md`. Das Log, die Tür `services/ai.py`, der Deckel,
> die Sprache (Phase 4) und das Lernen bleiben.

## 1 · Ziel

Die KI wird ein **Assistent**: Sie bereitet alles vor, was die Person im ERP tun kann, und tut
nichts, was die Person nicht bestätigt. Es gibt nur zwei Dinge:

- **Gespräch:** Im «+» sagt die Person, was ist, mit Text, Sprache, Foto, Datei oder der
  Stecknadel. Die KI redet mit (was sie weiss, Rückfragen) und bereitet vor.
- **Handgriff:** Alles, was das ERP kann, von der KI vorbereitet und von der Person ausgeführt.
  Er läuft durch dieselbe Tür wie ihr Klick, mit ihren Rechten und denselben Prüfungen, vorher
  mit einem Probelauf und genau einmal.

**Wissen** ist das Ergebnis: Notizen und Dokumente am richtigen Datensatz, jede mit Verweis auf
ihr Gespräch. Das Angeheftete zeigt bei jedem Öffnen, was jetzt zählt.

## 2 · Grundsätze (verbindlich)

1. **Die KI handelt nie ohne die Person.** Ein Tipp oder ein Satz von ihr führt aus. Sonst
   geschieht nichts.
2. **Keine Listen, keine Regeln, nur Rechte.** Was die KI vorbereiten kann, folgt aus den
   Schnittstellen des ERP selbst. Es gibt keine Liste erlaubter Felder oder Handlungen, die
   jemand pflegt. Kommt im ERP eine Handlung dazu, kann die KI sie von selbst.
3. **Jeder Handgriff wird einzeln entschieden:** Ausführen, Entwurf öffnen, Ändern oder Weg,
   per Knopf oder per Satz. Es gibt kein «Alles übernehmen» und kein «Alles verwerfen».
   Ausgeführt ist ausgeführt; korrigiert wird mit einem neuen Handgriff (Gegenbuchung).
4. **Die Eingabe bleibt bewahrt.** Jede Nachricht eines Gesprächs steht unveränderlich im Log.
5. **Nicht rückwärtskompatibel.** Wir sind in der Entwicklung. Was dadurch anders wird oder
   wegfällt, ist in Ordnung. Altes wird entfernt (Code, Tabellen, Ereignisse, Doku), nicht
   mitgeschleppt. Es gibt keine Übergangslösungen und keine Umwege.
6. **Einfach vor schlau.** Jede Regel unten ist eine klare Logik an einer Stelle. Was die KI
   besser kann als Code (Formulieren, Zuordnen, neu Vorbereiten), macht die KI.
7. **So günstig wie möglich.** Die KI bekommt keine 139 Werkzeuge in jede Anfrage, sondern
   schlägt Handlungen nach, wenn sie sie braucht. Das Angeheftete wird nur neu berechnet, wenn
   sich etwas geändert hat.

## 3 · Begriffe

| Wort | Bedeutung |
|---|---|
| **Gespräch** | Die Nachrichten einer Person und der KI im «+». Privat: Es sehen nur die Person und der Admin. **Offen**, solange ein Handgriff darin offen ist oder die KI noch nicht geantwortet hat; sonst abgeschlossen und nicht mehr gezeigt (es bleibt im Log). |
| **Handgriff** | Ein vorbereiteter Aufruf genau einer Handlung des ERP (Methode, Pfad, Werte), mit einer Zeile, die sagt, was geschieht. **Offen**, bis er ausgeführt oder weggelegt ist. |
| **Probelauf** | Der Handgriff läuft ganz durch und wird dann verworfen. Das zeigt, ob er geht, bevor die Person ihn sieht. |
| **Wissen** | Notizen und Dokumente an Datensätzen. |
| **Umfeld** | Ein Datensatz und seine direkten Nachbarn in den Daten (eine Stufe). |

## 4 · Fünf Regeln, die es robust machen

1. **Nach aussen erst nach dem Speichern.** Alles, was das ERP nach aussen tut, geht durch eine
   Tür (`core/outside.py`). Ein Probelauf speichert nie, also geht dabei nie etwas hinaus.
2. **Handgriffe, die aufeinander aufbauen,** warten aufeinander. Das ERP setzt die Nummer ein,
   sobald der erste ausgeführt ist.
3. **Inzwischen geändert:** Beim Ausführen fragt das ERP das Log, ob sich der Datensatz seit der
   Vorbereitung geändert hat. Wenn ja, sagt die Karte was, und die KI bereitet neu vor. Nichts
   wird still überschrieben.
4. **Was die Hand braucht** (Scan, Kamera, Unterschrift, Bezahlen, Datei hochladen): Die KI
   bringt die Person zur Stelle, ausführen tut sie dort.
5. **Die KI liest, was jedes Personal sehen darf** (`ai_tools.reader`), wie heute. Ihr Ergebnis
   kann Wissen werden, das jedes Personal sieht.

## 5 · Drei Durchläufe

Jeder Durchlauf wird einzeln gebaut, getestet, gegengelesen und auf das «deployen» von Clemens
auf dev ausgerollt. Danach folgt der nächste.

| # | Durchlauf | Für die Person sichtbar |
|---|---|---|
| 1 | **Fundament:** Speichern an einer Stelle, die Tür nach aussen, der Probelauf, jede Schnittstelle beschrieben | fast nichts (Person anlegen ohne Anmeldekonto im Voraus) |
| 2 | **Gespräch und Handgriff** im «+» und im Angehefteten | das neue «+» |
| 3 | **Wissen:** Umfeld, Wissen bei jedem Öffnen, im Wissen suchen | das neue Angeheftete |

---

## 6 · Durchlauf 1 – Fundament

### 6.1 Speichern an einer Stelle

**Heute:** 94 Aufrufe von `db.commit()` in 24 Dateien speichern mitten in einer Handlung.
Scheitert danach etwas, bleibt ein halber Stand liegen, und ein Probelauf ist unmöglich.

**Neu:** Eine Anfrage speichert **einmal, am Ende**.

- `core/database.get_db` gibt die Sitzung heraus. Endet die Anfrage ohne Fehler, speichert sie
  (`commit`), sonst verwirft sie alles (`rollback`). FastAPI (0.162) führt diesen Teil aus,
  bevor die Antwort hinausgeht. Scheitert das Speichern, wird die Antwort ein Fehler, nie ein
  «ok» ohne Speicherung.
- Kein Router und kein Dienst ruft in einer Anfrage `commit` auf. Wo heute zwischengespeichert
  wird, um eine Nummer oder Id zu bekommen, genügt `db.flush()`.
- Wo ein Dienst einen erwarteten Konflikt auffängt (eindeutiger Index, zum Beispiel «dieselbe
  Datei ist dasselbe Dokument»), geschieht das in einem Sicherungspunkt
  (`db.begin_nested()`). Die Anfrage läuft danach sauber weiter.
- **Hintergrundarbeit** (der Takt, `loop`, das Abschreiben der Aufnahmen, die Sperren mit eigener
  Verbindung) hat eigene Sitzungen und speichert **je Einheit** (eine Mail, ein Auftrag, ein
  Abschnitt). Das bleibt so: Dort ist jede Einheit für sich ganz oder gar nicht.
- Die Anmeldung (`core/auth`, Verknüpfen über die bestätigte E-Mail) speichert ebenfalls an der
  Kante der Anfrage.

### 6.2 Die Tür nach aussen (`core/outside.py`)

Zwei Wörter, eine Datei:

- **`outside.after(db, fn)`:** `fn` läuft erst, nachdem diese Sitzung gespeichert hat
  (SQLAlchemy-Ereignis `after_commit`). Bei einem Verwerfen läuft sie nie. Das gilt für alles,
  was das ERP von sich aus hinausschickt: Mails (`mailbox.send`; scheitert es, bleibt die Mail
  `outgoing` und der Abgleich holt nach, wie heute), Newsletter-Mails, Bedeutungs-Zahlen beim
  Entscheid (`memory`).
- **`outside.now(db, was)`:** Für das, was sofort eine Antwort von aussen braucht. Ausserhalb
  eines Probelaufs geschieht nichts Besonderes. In einem Probelauf löst es `NeedsHand(was)` aus,
  und der Handgriff wird «Öffnen» (Regel 4). Das betrifft:
  - Stripe: Zahlung vorbereiten, Rückzahlung
  - Postfach verbinden und trennen
  - Datei in den Speicher legen
  - KI-Aufrufe innerhalb einer Handlung (Lesen eines Dokuments, Verfassen)
- **Person anlegen ohne Anmeldekonto im Voraus:** `people.firebase_uid_for` fällt weg. Die Person
  bekommt ihr Konto bei der ersten Anmeldung. `core/auth._resolve_user` verknüpft schon heute
  über die bestätigte E-Mail. Eine Migration: `user_profiles.firebase_uid` darf leer sein
  (eindeutig, wenn gesetzt).
- **Wächter (prüft die Regel, nicht die Form):** Im Test laufen Probeläufe aller Handlungen, die
  ein Handgriff sein kann (6.3), mit gesperrtem Netz (`socket.connect` wirft). Jeder Versuch, im
  Probelauf hinauszugehen, macht den Test rot. Gegengeprüft: Ohne `outside.now` in der
  Stripe-Vorbereitung schlägt er an.

### 6.3 Der Probelauf (`services/handgriff.py`)

**Ein Handgriff läuft durch dieselbe Tür wie ein Klick.** Ausgeführt wird die echte Route des
ERP: im selben Prozess über ASGI (`httpx.ASGITransport` auf `app.main.app`), mit Methode, Pfad
und Werten des Handgriffs.

- **Wer handelt:** Die bereits angemeldete Person geht über eine Kontextvariable
  (`core/auth.acting_as`) an die Route. Gesetzt wird sie nur von `handgriff.run`, nie aus einer
  Anfrage von aussen. Die Route prüft die Rechte wie immer (`require_employee`, `require_admin`,
  `access`).
- **Eine Sitzung:** Dieselbe Kontextvariable reicht die Sitzung des Aufrufers an `get_db`
  (`core/database.ambient`). Die innere Route speichert dann nicht selbst. Speichern oder
  Verwerfen entscheidet `handgriff.run`.
- **`run(db, person, handgriff, probe=True)`:** ausführen, dann alles verwerfen. Antwort:
  - geht, oder
  - geht nicht, mit dem Satz der Route (zum Beispiel 409 «Die Rechnung … ist schon gestellt»), oder
  - braucht die Hand (`NeedsHand`).
- **`run(…, probe=False)`:** Es läuft derselbe Weg. Zusätzlich schreibt er in derselben
  Transaktion das Ereignis `handgriff.done`, dann wird gespeichert. Ein eindeutiger Index auf
  `handgriff.done` je Handgriff sorgt für **genau einmal**; ein zweites Ausführen gibt 409.
- **Welche Handlungen ein Handgriff sein können,** folgt aus der Route selbst, ohne Liste:
  - sie schreibt (nicht `GET`),
  - sie verlangt Personal (`require_employee` oder `require_admin` unter ihren Abhängigkeiten),
  - sie nimmt JSON.

  Eine Route mit Datei-Upload (`multipart`) braucht die Hand.
- Im Log steht wie bei jedem Klick die Person als Handelnde, dazu `source = "handgriff"`. Die
  Herkunft (Gespräch, Mail) steht im Ereignis `handgriff.done` mit derselben `request_id`.

### 6.4 Jede Schnittstelle beschreibt sich

Aus den Beschreibungen entstehen die Handlungen der KI (Durchlauf 2) und die Felder bei
«Ändern».

- Von 139 Routen haben 106 einen Satz (Docstring), 33 fehlt er. Diese 33 werden ergänzt. Der
  erste Satz sagt, was die Handlung tut, in den Worten der Oberfläche.
- Referenzen auf Datensätze bekommen **einen Typ** (`schemas/common.ObjectNr`, im Schema
  `format: "objekt"`). So erkennt «Ändern» ein Referenzfeld, ohne Namen zu raten.
- Wächter: Jede Route hat einen Satz; jede Handlung, die ein Handgriff sein kann, hat für jedes
  Pflichtfeld einen Typ, den «Ändern» darstellen kann.

### 6.5 Fertig, wenn …

- alle bisherigen Tests grün sind (Backend, Frontend, Website),
- ein Test zeigt: Eine Route, die schreibt und danach scheitert, hinterlässt nichts,
- ein Test zeigt: Der Probelauf jeder möglichen Handlung hinterlässt nichts (Zeilenzahl aller
  Tabellen und Log vorher = nachher) und geht nie hinaus (Netz gesperrt),
- ein Test zeigt: `outside.after` läuft nach dem Speichern, nach dem Verwerfen nie,
- eine angelegte Person sich anmelden kann und ihr Datensatz verknüpft wird,
- kein `commit` in einer Anfrage mehr steht (Wächter über den Quelltext von `routers/` und den
  Diensten, die Anfragen bedienen; die Hintergrundarbeit ist ausgenommen, weil sie eigene
  Sitzungen hat).

---

## 7 · Durchlauf 2 – Gespräch und Handgriff

### 7.1 Die Ereignisse im Log (keine neue Tabelle)

| Ereignis | `object_id` | `payload` |
|---|---|---|
| `talk` | der offene Datensatz, sonst die Person | `{talk, by: "person" \| "ai", text, hint?, files?}`: eine Nachricht. `talk` = Id der ersten Nachricht (das Gespräch). |
| `handgriff` | der Datensatz, den er betrifft | `{talk?, mail?, method, path, body, line, depends?, seen}`: vorbereitet und im Probelauf gelungen |
| `handgriff.done` | wie oben | `{handgriff, result?}`, genau einer je Handgriff (eindeutiger Index). `result` = Nummer, die die Handlung angelegt hat. |
| `handgriff.dropped` | wie oben | `{handgriff, by: "person" \| "ai"}`, weggelegt oder durch einen neuen ersetzt |
| `ai.call` | – | wie heute |

- **Offen ist abgeleitet:** ein Handgriff ohne `done` und ohne `dropped`. Ein Gespräch ist
  offen, wenn darin ein Handgriff offen ist oder die letzte Nachricht von der Person ist.
- **Wissen mit Herkunft:** Eine Notiz, die ein Handgriff anlegt, entsteht in derselben Handlung
  (`request_id`) wie sein `handgriff.done`. Daraus folgt ihr Gespräch; es braucht keine neue
  Spalte.
- Diese Ereignisse stehen nicht im Verlauf (`history.HIDDEN_EVENTS`); dort stehen ihre Folgen.
  Ein Gespräch sieht nur, wer es führt, und der Admin.

### 7.2 Die KI im Gespräch (`services/assistant.py`)

- **Ein Zug:** Die Person schreibt (oder die Aufnahme wird Text). Die KI antwortet über
  `ai.converse` mit Text und den Handgriffen, die folgen. Sie redet mit (was sie weiss,
  Rückfragen), beginnt aber kein Gespräch von sich aus.
- **Werkzeuge:**
  - **lesen:** `find`, `record`, `history` (wie heute, als `reader`), ab Durchlauf 3 auch
    `wissen`;
  - **`handlungen(suchwort)`:** die passenden Handlungen mit ihrem Satz, aus der OpenAPI-Beschreibung
    des ERP (6.3, 6.4);
  - **`handlung(name)`:** Felder, Typen und Prüfungen einer Handlung;
  - **`vorbereiten(name, pfad, werte, zeile, depends?)`:** macht den Probelauf und gibt «geht»
    oder den Grund zurück. Die KI korrigiert, bis es geht, oder sagt im Gespräch, warum nicht.
    Nur was geht, wird eine Karte. Was die Hand braucht, wird eine Karte «Öffnen».
- **Der Auftrag** (`assets/ai/auftrag.md`) wird neu geschrieben, schlank, mit dem Ziel statt
  Beispielen:
  - Wissen ablegen, wohin es gehört,
  - vorbereiten, was folgt,
  - Nummer und Name nennen,
  - Datum und Quelle zu jeder Aussage, Neues vor Altem,
  - einen Widerspruch zwischen zwei Notizen benennen.
- **Fällt die KI aus oder ist der Deckel erreicht,** bleibt das Gespräch Text. Der Takt
  antwortet nach (Aufgabe `ai`), und der Mensch kann von Hand weitermachen.

### 7.3 Aufeinander aufbauen (Regel 2)

- In den Werten eines Handgriffs darf `{"$handgriff": <Id>}` stehen, gemeint ist die Nummer, die
  jener anlegt. Dazu `depends = [<Id>]`.
- Der Probelauf führt die Kette der Reihe nach im selben verworfenen Lauf aus. So ist auch der
  zweite geprüft, bevor der erste existiert.
- Solange der erste offen ist, zeigt die Karte «wartet auf …» und ist nicht ausführbar. Beim
  Ausführen ersetzt `handgriff.run` den Platzhalter durch `result` aus dem `handgriff.done` des
  ersten. Wird der erste weggelegt, ist der zweite blass mit Grund, und die KI bereitet auf
  Wunsch neu vor.

### 7.4 Inzwischen geändert (Regel 3)

- `seen` = die jüngste Log-Id am betroffenen Datensatz beim Vorbereiten.
- Beim Ausführen: eine Abfrage `log` an diesem Datensatz nach `seen`, ohne den Handgriff selbst.
  Gibt es etwas, wird nicht ausgeführt: 409 mit dem, was sich geändert hat. Die Karte zeigt es,
  mit «Neu vorbereiten» (die KI erstellt einen neuen Handgriff, der alte wird `dropped`).
- Dazu läuft das Ausführen ohnehin durch alle Prüfungen der Route. Was nicht mehr geht, sagt die
  Route selbst.

### 7.5 Die Karte

Jede Karte zeigt eine Zeile, was geschieht, mit Nummer und Name, bei einer Änderung `alt → neu`,
und die Herkunft (Gespräch, oder «Mail von …: Betreff»). Dazu ihre Handlungen:

| Knopf | Wirkung |
|---|---|
| **Ausführen** (bei einer Notiz «Ablegen») | `POST /erp/handgriffe/{id}/run` |
| **Entwurf öffnen** | bei Handlungen mit Entwurf (Artikel, Auftrag, Person, Firma, Dokument): der Entwurf öffnet ausgefüllt, gespeichert wird erst mit «Freigeben». Die Freigabe ist der Handgriff (`done`). |
| **Ändern** | Felder aus dem Schema der Handlung (Typ, Pflicht, Auswahl, Länge, Referenz → `ObjectSelect`), über den Feld-Baustein. Geprüft wird mit einem Probelauf derselben Route: Die Meldung ist der Satz der Route. Die Werte füllt die KI vor. |
| **Weg** | `handgriff.dropped` |
| **Öffnen** | nur bei «braucht die Hand»: springt zum Datensatz bzw. in den Entwurf |

Jede Wirkung geht auch **per Satz** im Gespräch («ja, aber 3 Stück», «den Auftrag nicht»). Die
KI führt dann nicht selbst aus: Sie bereitet neu vor oder legt weg, und ausgeführt wird nur,
wenn die Person «ausführen» sagt oder tippt.

### 7.6 Foto und Datei im Gespräch

- 📷 und 📄 legen die Datei in den **Korb** (`services/attachments`, wie die Fotos des
  Kontaktformulars) und hängen sie an die Nachricht (`files`). Die KI liest sie.
- Soll ein Dokument entstehen, ist das ein Handgriff «Dokument anlegen». «Entwurf öffnen» öffnet
  den Dokument-Entwurf mit der Datei und den gelesenen Werten. Mit «Freigeben» entsteht das
  Dokument wie heute (`documents.file`).
- Die Stecknadel und die Aufnahme bleiben, wie sie sind. Ihr Ergebnis ist eine Nachricht im
  Gespräch statt einer Erfassung.

### 7.7 Handgriffe aus Mails

`services/follow.py` liest eine neue Mail einer bekannten Person wie heute, bereitet aber
Handgriffe vor statt Vorschläge (`mail` statt `talk`, Gegenstand = der Datensatz). Sie stehen im
Angehefteten ihres Datensatzes und zählen dort in «zu tun». Wer ihn öffnet, entscheidet.

### 7.8 Oberfläche

- **Das «+»** (`components/erp/capture/`) wird das Gespräch:
  - oben das Eingabefeld (unverändert: Schreiben, 🎤, 📷, 📄, 📌),
  - darüber die Nachrichten und die Karten,
  - darunter «Offene Gespräche» (statt «Nicht abgelegt») und «Neu anlegen».
  - Die Zahl am «+» = meine offenen Gespräche.
- **Angeheftet** (`pinned.tsx`) zeigt die offenen Handgriffe des Datensatzes als dieselben
  Karten (`handgriff-card.tsx`, eine Komponente für beide Orte).
- **Ändern:** `components/erp/capture/schema-form.tsx`, gebaut aus `Field`, `SelectField` und
  `ObjectSelect`.
- Wörter: «Gespräch», «Offene Gespräche», «Handgriff», «Ausführen», «Ablegen», «Entwurf öffnen»,
  «Ändern», «Weg», «Öffnen».

### 7.9 Was wegfällt (ganz, ohne Übergang)

| Bereich | Was wegfällt |
|---|---|
| Backend | `services/intake.py` (Erfassung, Ablegen, «Stimmt so», Verwerfen), `services/proposals.py` mit `FIELDS` und `CREATE_FIELDS`, die Ereignisse `intake`, `proposal`, `proposal.decided`, der Index `ix_log_decided` (per Migration), das Festschreiben der Entscheide im Takt, die Routen unter `/intake` und `/proposals` |
| Frontend | `capture/filed.tsx`, `capture/proposal-card.tsx`, `form/proposal-mark.tsx`, der Vorschlag in `use-field.ts` (`objectId`, `name` → Vorschlag), `ProposalClient`, `lib/proposals.ts`, `lib/settled.ts` |
| Lernen | `memory.py` lernt aus entschiedenen Handgriffen (`done` oder `dropped` durch die Person) statt aus Vorschlägen; dieselbe Tabelle `ai_memory` |

Alte Ereignisse bleiben im Log (es ist unveränderlich). Sie werden nirgends mehr gelesen.

### 7.10 Fertig, wenn …

- der Fall «Notiz, Artikel, Auftrag» durchläuft:
  - die Notiz ist abgelegt,
  - der Artikel wird über «Entwurf öffnen» freigegeben,
  - der Auftrag wartet und nimmt danach die Nummer des Artikels,
  - nichts entsteht doppelt,
- die Telefonnummer per Satz geändert wird («ändere bei Huber das Telefon auf …»), mit
  `alt → neu`,
- ein Test zeigt: Ein Handgriff wird genau einmal ausgeführt (zwei gleichzeitig: einer gelingt,
  einer 409),
- ein Test zeigt: Ändert jemand den Datensatz nach der Vorbereitung, wird nicht ausgeführt, und
  die Karte nennt die Änderung,
- ein Test zeigt: Die KI kann nur vorbereiten, was die Person darf. Ein Admin-Handgriff bei einer
  Mitarbeiterin wird nie eine Karte, denn der Probelauf gibt 403,
- eine Handlung, die die Hand braucht, als «Öffnen» erscheint,
- die KI aus einer Mail einen Handgriff am richtigen Datensatz vorbereitet und er dort in «zu
  tun» zählt,
- im Code kein Rest von Erfassung und Vorschlag steht (`scripts/deadcode.py` leer, `grep` nach
  `intake`, `proposal` leer ausser in Migrationen und Geschichte).

---

## 8 · Durchlauf 3 – Wissen

### 8.1 Das Umfeld (`services/surroundings.py`)

- Das Umfeld ist **eine Stufe** entlang der Verbindungen in den Daten, in beide Richtungen,
  abgeleitet aus den Fremdschlüsseln der Modelle (`Base.metadata`), ohne Liste.
- Reine Verbindungstabellen (zum Beispiel `order_units`, `document_refs`, `message_parties`)
  zählen nicht als Stufe. Erkannt werden sie an ihrer Form: zwei Verweise auf Datensätze und
  keine eigene Objektnummer.
- Begrenzt auf die **50 jüngsten** Nachbarn (eine Zahl an einer Stelle).
- Wächter: Für jeden Datensatztyp enthält das Umfeld die erwarteten Nachbarn. Zum Beispiel hat
  ein Auftrag seine Stücke, seinen Kunden und seinen Artikel, und eine Instanz hat ihren Artikel
  und ihre Aufträge.

### 8.2 Hat sich etwas geändert?

Eine Abfrage: die jüngste Log-Id über alle Nummern des Umfelds (Index `ix_log_object_at`; gemessen
mit 1 Mio. Log-Zeilen < 50 ms, sonst ein Index `(object_id, id)`). Ist sie grösser als beim
letzten Mal, wird neu gewählt.

### 8.3 Das Angeheftete bei jedem Öffnen

- Oben die **offenen Handgriffe** des Datensatzes (Durchlauf 2), immer und zuerst.
- Darunter **das Wissen, das jetzt zählt:** höchstens drei Aussagen, jede mit Datum, Quelle und
  Sprung zur Notiz oder zum Dokument.
- **Billig:** Der letzte Stand (`pin`-Ereignis mit `seen`) kommt sofort. Hat sich im Umfeld
  etwas geändert, rechnet ein zweiter Aufruf im Hintergrund neu, und das Angeheftete tauscht
  still aus. Am Deckel bleibt der letzte Stand.
- «neu ansehen» und «lösen» fallen weg (`pin.solved` wird nicht mehr geschrieben).

### 8.4 Im Wissen suchen

- Notizen und Dokumente (Text und Stichworte) bekommen Bedeutungs-Zahlen (Vertex, pgvector), in
  derselben Tabelle `ai_memory`, erweitert um die Art und den Verweis (per Migration). Der Takt
  holt Fehlendes nach.
- Werkzeug `wissen(frage)`: die 5 ähnlichsten Einträge, die `reader` sehen darf (`access`), mit
  Datum, Quelle und Datensatz. Es dient im Gespräch («wie im September bei …») und für das
  Angeheftete.
- Ohne Vertex gibt es keine Suche nach Bedeutung, sonst fehlt nichts.

### 8.5 Fertig, wenn …

- «die Pumpe tropft wieder» im Gespräch die Notiz «Wellendichtung undicht» vom September
  findet, mit Datum und Quelle,
- das Angeheftete beim zweiten Öffnen ohne Änderung keine KI ruft (Test zählt `ai.call`),
- eine Änderung an einem Stück des Auftrags das Angeheftete des Auftrags neu wählen lässt,
- zwei widersprüchliche Notizen als Widerspruch genannt werden, die neuere zuerst.

---

## 9 · Bewusst nicht (vorerst)

- **Viele Dinge auf einmal:** Es gibt keinen eigenen Mechanismus. Ein Handgriff ist genau eine
  Handlung des ERP. Braucht es eine Massenänderung, bekommt das ERP dafür eine Handlung, und
  dann kann die KI sie von selbst.
- Schwärzen der Bedeutungs-Zahlen, gemeinsame Gespräche, bedingte Erinnerungen («falls keine
  Antwort»).
- Die KI beginnt kein Gespräch von sich aus. Offene Gespräche überwacht das System nicht, das ist
  Führung.
- Ein «nicht wichtig»-Knopf, Lernsignale, eine Prüfsammlung.
- **Später:** dieselben Werkzeuge als MCP-Server (nur für Clemens).

## 10 · Je Durchlauf

1. Zuerst mit `develop` abgleichen, dann auf einem Feature-Branch arbeiten.
2. Volltest wie die CI: Backend gegen ein Schema nur aus den Migrationen, Frontend, Website.
3. Unabhängig gegenlesen und alle Befunde beheben.
4. Doku nachziehen: `CLAUDE.md`, `backend/CLAUDE.md`, `frontend/CLAUDE.md`, diese Akte und
   `lernende-firma.md`; Rundenbericht nach `docs/history/`.
5. Deploy auf dev auf das «deployen» von Clemens; prod bleibt unberührt.
