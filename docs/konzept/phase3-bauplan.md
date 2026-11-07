# Phase 3 · KI – Bauplan (Vertrag zwischen Backend und Oberfläche)

> **Kopfstatus:** gebaut (07.11.2026) · gehört zur Projektakte
> `docs/konzept/lernende-firma.md` (§4.3, §4.4, §6 «Phase 3»). Was hier steht, ist die
> Schnittstelle, gegen die gebaut wird; ändert sie sich, wird sie hier geändert.

## Grundsätze (aus der Akte, verbindlich)

- Die KI **liest, was jedes Personal sehen darf – nie mehr als die Person, nie Privates**
  (ihr Ergebnis sieht jedes Personal), **schreibt nie** – sie schlägt vor, ein Mensch
  entscheidet. Jeder Aufruf geht durch **eine Tür** (`services/ai.py`), ein Deckel, ein Log.
- **Keine neue Insel:** eine Erfassung, ein Vorschlag, ein Entscheid, ein Hinweis sind
  **Ereignisse im Log** (`services/log.event`). Eine Notiz ist eine Nachricht (Kanal `note`).
  Neu ist nur `ai_memory` (Bedeutungs-Zahlen, abgeleitet aus dem Log, kein Wissen).
- **Übernehmen = Tippen:** ein Vorschlag am Feld schreibt über dasselbe `onChange` und
  Auto-Save wie die Hand. **Ob ein Vorschlag offen ist, wird abgeleitet** – ein Entscheid
  wird nie «gesetzt», ausser «verworfen» (✕).
- **Robust:** fällt die KI aus (kein Schlüssel, Deckel, Fehler), bleibt die Eingabe roh am
  Datensatz und wird im Takt nachgeholt; der Mensch kann immer von Hand ablegen.

## Die Ereignisse im Log

| Ereignis | `object_id` | `payload` |
|---|---|---|
| `intake` | der Datensatz, der beim Erfassen offen war, sonst die Person | `{text, hint}` – die rohe Eingabe |
| `proposal` | der Datensatz, an dem der Vorschlag steht | `{kind, field?, value?, label, draft?, parts?, source}` (unten) |
| `proposal.decided` | wie der Vorschlag | `{proposal, outcome, value?}` – `outcome`: `accepted` · `changed` · `rejected` · `gone` |
| `pin` | der Datensatz | `{items: [{key, text}]}` – die Hinweise, die die KI gewählt hat |
| `pin.solved` | der Datensatz | `{pin, key}` |
| `ai.call` | – | wie bisher, dazu `chf` (Kosten des Aufrufs) |

**Arten eines Vorschlags (`kind`):**

- `change` – ein Feld ändern: `field` (Spaltenname, aus `proposals.FIELDS[typ]`), `value`
  (Text), `label` (Wort für das Feld). Offen, bis (a) ✕ (`rejected`) oder (b) das Log danach
  eine Änderung genau dieses Feldes an genau diesem Datensatz zeigt (`accepted`, wenn der
  neue Wert dem Vorschlag gleicht, sonst `changed`) oder (c) der Datensatz weg ist (`gone`).
- `create` – etwas anlegen: `draft = {type: "user" | "organization", values: {...}}`; offen,
  bis ✕ oder bis ein Datensatz dieses Typs mit diesen Werten entstanden ist (dann
  `accepted`). «Entwurf öffnen» öffnet den bestehenden Entwurf vorausgefüllt.
- `file` – eine Erfassung ablegen: `parts = [{object_id, text, subject}]`; offen, bis «Stimmt
  so» (`accepted`/`changed`, je nachdem ob der Mensch Teile änderte) oder ✕.

`source = {text, object_id?, message_id?, intake?}` – woher der Vorschlag kommt («Erfassung
von Hans-Peter», «Mail von Vreni Kunz: Betreff»), kurz; **nie die Worte einer Erfassung** (die
sieht bis «Stimmt so» nur, wer erfasst hat).

Der Takt schreibt die abgeleiteten Entscheide fest (`proposal.decided`, Handelnder System),
damit jeder Vorschlag mit Entscheid ein **Fall** ist, aus dem gelernt wird. Je Vorschlag gibt
es **genau einen** Entscheid (eindeutiger Index `ix_log_decided`; ein zweiter ist 409).

## API (`/api/v1/erp`, Personal)

```
POST /intake                    {text, hint_object_id?}           → Intake
GET  /intake/open                                                  → Intake[]   (meine, noch nicht abgelegt)
POST /intake/{id}/file          {parts: [{object_id, text, subject?}]} → Intake (abgelegt: notes gefüllt)
GET  /proposals?object_id=N                                        → Proposal[] (offen, an diesem Datensatz)
POST /proposals/{id}/reject                                        → Proposal   (✕)
GET  /pins/{object_id}                                             → Pinned
POST /pins/{object_id}/refresh                                     → Pinned     («neu ansehen», KI)
POST /pins/{object_id}/solve    {key}                              → Pinned
```

```ts
Intake   = { id: number /* log id */, at, text, hint_object_id: number|null,
             parts: Part[], proposals: Proposal[], filed: boolean,
             notes: {object_id, message_id}[], problem: string|null }
Part     = { object_id: number, label: string /* «Benutzer · Hans Muster» */,
             text: string, subject: string }
Proposal = { id: number /* log id */, at, object_id, object_label, kind: 'change'|'create'|'file',
             field: string|null, label: string, value: string|null, current: string|null,
             draft: {type: 'user'|'organization', values: Record<string,string>}|null,
             parts: Part[]|null, source: {text, object_id: number|null, at} }
Pinned   = { proposals: Proposal[] /* immer, zuerst */,
             hints: {key: string, text: string, entry_key: string|null}[],
             refreshed_at: string|null, problem: string|null }
```

- `POST /intake` legt **sofort** die rohe Eingabe ab (`intake`) und lässt dann die KI ablegen
  (höchstens ~45 s, unter der Grenze von Firebase Hosting). Klappt das nicht, kommt ein Teil
  zurück (der ganze Text am Hinweis-Datensatz bzw. an der Person) und `problem` sagt warum –
  der Mensch kann trotzdem «Stimmt so». Der Takt holt offene Erfassungen ohne Vorschlag nach.
- `POST /intake/{id}/file` legt **je Teil eine Notiz** an seinem Datensatz an (Betreff =
  `subject`, sonst die ersten Worte), schreibt den Entscheid und gibt die Erfassung zurück.
- «zu tun» (`GET /erp/todo`) zählt offene Vorschläge am Datensatz (Abschnitt `vorschlaege`,
  Wort «n Vorschläge») und **meine** offenen Erfassungen an meiner Person.

## Die KI (`services/ai.py` + `services/ai_tools.py`)

- `ai.converse(db, *, task, actor, system, content, schema, tools)` – eine Schleife mit
  Werkzeugen (höchstens `Task.rounds`), Antwort in fester Form (structured outputs), jeder
  Aufruf ein `ai.call`; nie eine Ausnahme, `ai.problem()` sagt warum nichts kam.
- **Lese-Werkzeuge** (`ai_tools.tools_for(db)`, alle mit dem gemeinsamen Betrachter
  `ai_tools.reader()`: Rolle `employee`, ohne eigene Nummer): `find(q)` – Datensätze nach
  Nummer oder Name · `record(object_id)` – das Wichtigste eines Datensatzes ·
  `history(object_id)` – die neuesten Einträge seines Verlaufs (`history.page`). Was nicht
  jedes Personal sehen darf (Zeiterfassung, private Dokumentteile), gibt es für die KI nicht –
  auch wenn ein Admin handelt; er steht im Log (`ai.call`).
- **Deckel in Franken** (`AI_DAILY_CAP_CHF`, Vorgabe 10): Kosten je Aufruf aus den Tokens
  (Preise je Modell in `ai.PRICES`, USD → CHF fest), Summe des Tages aus den `ai.call`;
  ab 80 % ein Hinweis in «zu tun» des Admins; am Deckel kein Aufruf mehr (die Eingabe bleibt
  roh, der Takt holt nach).
- **Aufgaben:** `read` (Haiku, wie bisher) · `compose` (Sonnet, wie bisher) · `file`
  (Ablegen einer Erfassung, Sonnet, mit Werkzeugen) · `follow` (was aus einer eingehenden
  Mail folgt, Sonnet, mit Werkzeugen, im Takt) · `pin` (Hinweise zu einem Datensatz, Sonnet)
  · `embed` (Bedeutungs-Zahlen, Vertex AI).
- **Der Auftrag** steht wörtlich in `backend/app/assets/ai/auftrag.md` (aus der Akte §4.3);
  jede Aufgabe hängt nur ihr Antwortformat an.

## Lernen (`services/memory.py`, Migration 170)

- `ai_memory` (`log_id` → der Vorschlag, `embedding vector(768)`, `text`) – pgvector in der
  eigenen Datenbank. Bedeutungs-Zahlen von **Vertex AI** (`gemini-embedding-001`, 768
  Dimensionen, Region `VERTEX_REGION`, Vorgabe `europe-west3`), über `ai.embed`.
- Jeder **entschiedene** Fall, dessen Inhalt jedes Personal sehen darf (`change`/`create`;
  `file` nur `accepted`/`changed`, dann steht er als Notiz da), bekommt seine Zahlen beim
  Entscheid (im Takt nachgeholt, wenn es nicht gleich ging, und für die Entscheide des Takts).
- Vor `file`/`follow`: `memory.similar(db, text, k=5)` – die ähnlichsten Fälle (Quelle,
  Vorschlag, Entscheid, ggf. geänderter Wert) gehen in die Anfrage.
- Ohne Vertex (nicht eingerichtet, Fehler): keine ähnlichen Fälle – sonst nichts.

## Der Takt (`services/tick.TASKS`, neue Aufgabe `ai`)

Entscheide festschreiben · offene Erfassungen ohne Vorschlag nachholen · neue eingehende Mails
(bekannte Person, keine Massenpost, ab Einführung) auf Folgen prüfen (`follow`; ein Fehlschlag
zählt als `mail.follow_failed`, nach dem dritten ist die Mail geprüft) · fehlende
Bedeutungs-Zahlen nachholen. Unter der Zeitgrenze des Takts wiederholt das SDK nichts. Je Lauf begrenzt; am Deckel nur das, was keine KI braucht.

## Oberfläche

- **«+» im Feed = Erfassen:** oben rund festhalten – Foto · Datei · Schreiben (Aufnehmen kommt
  mit Phase 4, bis dahin kein Knopf); unten eckig neu anlegen (Person, Firma, Artikel, Auftrag,
  in den Farben des Feeds). Foto und Datei öffnen den bestehenden Dokument-Entwurf; der offene
  Datensatz ist der Hinweis.
- **Schreiben → «Abgelegt»:** je Teil der Datensatz (antippen = anderer, `ObjectSelect`) und
  der Text; darunter die Vorschläge; «Stimmt so» legt ab.
- **Vorschlag am Feld:** `useField` fragt die offenen Vorschläge des Datensatzes
  (`objectId`) und zeigt am Feld (`name`) das Zeichen wie «zu tun»; Darüberfahren/Tippen
  öffnet ein Fenster: neuer Wert, Quelle, «Übernehmen», ✕. Übernehmen ruft `onChange(value)`
  und speichert sofort (wie Enter).
- **Das Angeheftete** steht im Verlauf unten beim Neuesten: zuerst alle offenen Vorschläge
  (immer), dann die Hinweise der KI mit «neu ansehen»; ein Hinweis lässt sich lösen.
