# PROCESS_CORE — die Grundlogik des Prozesses

> **Verbindlich und systemweit.** Wer ein Prozessschrittmodul baut, hält sich hieran. Was hier
> nicht steht, ist nicht entschieden — und wird nicht erfunden.
>
> **Diese Datei beschreibt den IST-STAND – sonst nichts.** Wie die Regeln entstanden sind
> (Begründungen, verworfene Wege, frühere Fassungen), steht in
> **`docs/history/2026-11-10-process-core-chronik.md`** (die frühere PROCESS_CORE.md, wörtlich).
>
> Stand: November 2026. Einzelinstanz-Modell, Entscheide A1–A6; §1–§12 sind gebaut. Fünf
> Module: **Datenerfassung** (§9.0–§9.3, §9.5) · **Aussondern** (§9.4) · **Verbrauch** (§9.6) ·
> **Bewegen** (§9.8) · **Zahlung** (`beleg`, §9.15). Entfernte Module: §9.9/§9.9a/§9.12–9.14
> (Verweis auf `docs/attic.md`). Zeichenregeln des Prozessbilds: `docs/prozessbild.md`.

---

## 1. Der Auftrag

Ein Auftrag hat **genau einen Anfang und genau ein Ende**; dazwischen eine geordnete Folge von
**Prozessschrittmodulen** — alles, was im Unternehmen getan wird. Die Module werden einzeln
definiert (§9).

```
   DEFINITION        welche Einzelinstanzen?
       │
     ( ▶ ) START     Freigegeben/Verkauft → Im Prozess
       │
   [ Modul 1 ]       bleibt Im Prozess
   [ Modul 2 ]       bleibt Im Prozess   (ausser an einem Ausgang, §4.6)
      ...
     ( ⚑ ) ENDE      Im Prozess → Freigegeben (bzw. Verkauft)
```

## 2. Was sich bewegt: ausschliesslich Einzelinstanzen

Im Prozess bewegen sich **nur Einzelinstanzen** — nie ein Artikel, nie eine Instanz. Artikel und
Instanz sind Ordner; jede Ansicht auf ihrer Ebene ist Filterung oder Summierung.

### 2.1 Die Definition steht vor dem Start

**Vor** dem Start steht die Definition: mit welchen Einzelinstanzen der Auftrag arbeitet. **Ohne
Definition kein Start.** Eine Definitionszeile beantwortet drei Fragen, **in dieser Reihenfolge**
(jedes Feld ist gesperrt, bis das davor steht, und nennt den Grund):

| # | Angabe | Regel |
|---|---|---|
| 1 | **Artikel** | Pflicht. |
| 2 | **Menge** | Ganzzahl ≥ 1 (Menge 0 gibt es nicht). Referenziert **immer exakt Einzelinstanzen**. |
| 3 | **Herkunft** | `Neu` (wird erzeugt) oder `Lager` (bestehende Stücke). Pflicht. |

**Harte Mengen-Invariante**: Menge N heisst exakt N Einzelinstanzen im Prozess
(`services/materialize.assert_quantity`), geprüft bei der Freigabe auf dem *Plan* (vor der ersten
Objektnummer) und auf dem *Ergebnis*; eine Abweichung bricht die Transaktion ab.

#### Herkunft `Neu` — der Erzeugungsauftrag

- Der Prozess ist die **Vorlage des Artikels** (§8.2), gespiegelt, im Entwurf nicht editierbar und
  bei der Freigabe als **Kopie** übernommen. Ohne Vorlage ist `Neu` nicht wählbar (mit Grund).
- Bei der Freigabe entstehen die Einzelinstanzen (`Freigegeben`) und passieren im selben Zug das
  Start-Objekt nach `Im Prozess`.
- **«Neu» steht für sich allein**: mehrere Definitionszeilen nur mit Herkunft `Lager`.

#### Herkunft `Lager` — bestehende Stücke

- Gewählt werden **konkrete** Einzelinstanzen; **FIFO ist die Vorauswahl**, sichtbar und einzeln
  abwählbar. Der Prozess ist frei modellierbar. **Hier entsteht nie eine neue Nummer.**
- Die Auswahl sperrt noch nichts; die Exklusivität greift bei der Freigabe (§3).

### 2.2 Wo Einzelinstanznummern entstehen

> **Neue Einzelinstanznummern entstehen ausschliesslich beim Freigeben eines Auftrags, und
> ausschliesslich für Definitionszeilen mit der Herkunft `Neu`.**

Die eine Erzeugungsstelle ist `services/instances.create_instances` (Wächter: niemand sonst
vergibt einen Suffix). Die Serialisierung des Artikels entscheidet als **Zahlenpaar**
(`materialize.plan`): Einzelserialisierung, Menge 3 → `(3, 1)` = 3 Instanzen mit je `…-1`;
Charge → `(1, 3)` = 1 Instanz mit `…-1 …-2 …-3`. Objektnummern kommen als Block aus
`object_id_seq`; der Suffix läuft je Instanz, monoton, ohne Wiederverwendung.

Nur die definierten Einzelinstanzen werden verarbeitet: kein Nachschieben, kein Ersetzen zur
Laufzeit; ein Verstoss ist ein harter Fehler (409, benannte Ursache).

## 3. Exklusivität (A3, hart und systemweit)

> **Eine Einzelinstanz ist zu jedem Zeitpunkt in genau EINEM Auftrag aktiv.**

**Aktiv** = im Prozess eines freigegebenen Auftrags (exklusiv); **referenziert** = historischer
Verweis (abgeschlossener Auftrag, Log; beliebig oft).

- Ein aktives Stück in einem zweiten Auftrag zu definieren ist ein **harter, sprechender Fehler**
  (nennt Stück und Auftrag). Erzwungen **auf Datenbankebene** (§11.2).
- Reservierung, Anteil und Unterdeckung gibt es nicht.
- **Keine Ausnahme**: auch der Abweichungsauftrag (§12) **entzieht** das Stück, statt es ein
  zweites Mal aktiv zu machen.

### 3.1 Wann wird ein Stück wieder frei?

1. **Normalfall:** sobald es **das Ende-Objekt passiert** hat. Der Auftrag ist abgeschlossen, wenn
   alle seine Stücke durch sind — eine Folge, keine eigene Regel.
2. **Ausgang:** ein terminales Modul (§4.6) schliesst die Zugehörigkeit ebenso.
3. **Abweichung:** ein anderer Auftrag entzieht das Stück (§12). Eine Abbruch-Funktion gibt es
   nicht: abgebrochen wird, indem eine Abweichung alle Stücke mit gekappter Rückführung entzieht
   (`SYSTEM_LOGIC.md` §4.4).

## 4. Die Statusregel (Kern)

> **Wer ein Modul passiert und weiterläuft, bleibt `Im Prozess`.** Ein Status ändert sich nur beim
> **Eintreten** (Start, §4.1) und beim **Hinausgehen**: am Ende (§4.2), an einem **Ausgang**
> (Aussondern, §4.6) oder für die **Komponenten** des Verbrauchs (§9.6).

Ein Prozessschritt speichert **keinen Übergang**: `process_steps` und `article_process_steps`
haben kein `status_before`/`status_after` (Migration 186). Was beim Hinausgehen geschieht, sagt
der Modultyp (`Module.exit_status_for`, `domain/modules.py`):

| Modul | `exit_status_for` |
|---|---|
| Datenerfassung · Bewegen · Zahlung | `None` — alle laufen weiter |
| Aussondern | `Verschrottet` bzw. `Gesperrt` aus `config.mode` — für die ankommenden Stücke |
| Verbrauch | `Verbaut` — für die **Komponenten**, die es zieht; das Produkt läuft weiter |

Vor jedem Bestätigen prüft `process.confirm_step` (`_ready_at`), dass die wartenden Stücke
`Im Prozess` stehen — sonst ein sauberer Fehler mit Stück, Ist- und erwartetem Status. Die
**Ereignisse im Log** tragen weiterhin `status_before`/`status_after`: Tatsachen, keine
Definition (§11.3).

### 4.1 Start und Ende sind systemweit fest (A2)

| Objekt | Übergang |
|---|---|
| **Start** | `Freigegeben` bzw. `Verkauft` (`statuses.REGULAR_STARTS`) → `Im Prozess`; wer anderes greift, ist eine Abweichung (§12.2) |
| **Ende** | `Im Prozess` → `Freigegeben`, oder `Verkauft`, wenn das Stück einer anderen Partei gehört (§4.2) |

Beides sind Systemübergänge, **nicht je Auftrag einstellbar**.

### 4.2 Der Endzustand ist EIN Wert an EINER Stelle (A6)

Der Endzustand steht einmal in der Fachschicht (`statuses.DEFAULT_END_STATUS` = `Freigegeben`)
und wird nur vom Ende-Objekt gelesen (`process._finish`) — kein UI, keine Auswahl, keine Spalte
am Auftrag. **Ausnahme, abgeleitet statt gespeichert:** ein Stück, das einer anderen Partei
**gehört**, wird **`Verkauft`** — laut dem jüngsten nicht stornierten Zahlungsmodul, das es
passiert hat (`voucher.sold_units`, §9.15). Ein Stück, das in seinen Quell-Auftrag zurückkehrt,
bleibt `Im Prozess`.

### 4.3 Die Kette muss schliessen

**Hinter einem Ausgang steht nichts** (`domain/chain.assert_closes`). Eine Kette aus Modulen,
die ihre Stücke «Im Prozess» weiterreichen, schliesst immer; ein Modul hinter einem terminalen
(§4.6) ist ein Fehler — an **beiden** Definitionsorten (§8): bei der Freigabe des Auftrags
(`release`) und beim Anlegen der Artikel-Vorlage (`article_process`).

### 4.4 Ein Vorgang ist EINE Instanz — und sie wird zuerst bestätigt

Erst die Instanz verifizieren, dann die Eingabe — durchgesetzt an der einen Ausführungsstelle
(`process.confirm_step` → `_verified_instance`, 400). **Der Scan verifiziert die INSTANZ**: das
Etikett klebt an ihr, eine Einzelinstanz hat keine Objektnummer (§2.2). Eine Charge über 12
Stück ist 1 Scan, 12 Einzelserialisierte sind 12 — ohne `if` nach der Serialisierung. Ein
Bestätigen deckt genau die Stücke **einer** Instanz ab und gibt zurück, was es bewirkt hat
(`{moved, held, result}`).

- **Die Tastatur ist die Alternative, nicht die Umgehung**: die Nummer tippen im selben Dialog,
  geloggt als `verification` ∈ `scan` | `manual` im `capture`-Ereignis.
- **Global**: ein Modultyp ohne physischen Bezug schaltet sie mit
  `Module.requires_verification = False` ab.

### 4.5 «Nicht bestanden» rückt nicht vor — und legt nichts an

Ergibt eine Erfassung ein negatives Urteil: (1) die Erfassung ist geloggt und eingefroren;
(2) **nichts rückt vor** — die Stücke bleiben am Modul stehen, sichtbar mit Grund; (3) das System
**bietet** einen Abweichungsauftrag mit vorgewählten Stücken an (auch für den ungeprüften Rest),
**legt ihn aber nicht an** — angelegt wird er wie jeder Auftrag (§12.6a).

- **Angehalten wird die ganze Instanz**, nicht nur die Stichprobe (ISO 2859-1).
- Die Regel steht in `confirm_step`; ein Modultyp sagt nur sein Urteil (`CaptureType.verdict`).
- **Der Halt ist eine AUSKUNFT, keine Sperre** (`held_units`: «welche haben zuletzt ein
  negatives Urteil?»). Erneut erfassen geht **immer**; das nächste Urteil ersetzt das letzte
  (§9.2). In der Oberfläche steht der Halt **neben dem Weg nach vorn, nie an seiner Stelle**
  (Wächter `test_capture_module.test_a_hold_is_never_a_dead_end`,
  `frontend/scripts/process-ui.test.mjs`).

### 4.6 Ein terminales Modul ist ein AUSGANG, kein Durchgang

Ein Modul kann das Stück aus dem Auftrag **hinausführen**; es sagt das an seiner Registry-Zeile
(`Module.terminal`), und daraus folgt alles ohne Fallunterscheidung:

- der Editor bietet dahinter nichts an, ein Modul, das dahinter gerät, wird gemeldet
  (`lib/modules.chainProblems`); dahinter steht kein Modul (`chain.assert_closes`, §4.3);
- das Bild endet dort, kein `end`-Knoten (`flow.build`); es passiert das Ende-Objekt nicht
  (`process._finish`); es wird nie von selbst durchlaufen (`process._run_through`);
- **eine geplante Rückführung endet**: der Quell-Auftrag zählt seine Ausleihen über die
  **offene** Zugehörigkeit (`waiting_counts`, `pending_returns`), das Aussondern schliesst sie
  (`_pass` mit `next_step_id=None`). Er wartet nicht mehr, sein Modul ist frei; bleibt ihm nichts,
  ist sein Ziel unerreichbar. `return_to_order_id` bleibt unangetastet.

Der Auftragsstatus braucht keinen neuen Wert (`_derive`): wer aussondert, ist `Abgeschlossen`;
wem die Stücke dadurch endgültig fehlen, `Abgebrochen`.

## 5. Statuswerte (A1, A4)

### 5.1 Geschlossene Liste

Eine **geschlossene, systemweite** Statusliste; Module erfinden nie eigene Werte. Erweitert wird
sie an **genau einer Stelle**: `domain/statuses.CATALOG`.

### 5.2 Die Werte

`backend/app/domain/statuses.py` ist die eine Quelle; das Frontend bekommt sie **generiert**
(`scripts/dump_statuses.py` → `frontend/src/lib/status-catalog.ts`). Eine Zeile trägt
Beschriftung, Ampelton, **Achsen** (Stück · Auftrag · Artikel) und, für Stücke, **Bestand** oder
**Historie** (`stock`); Reihenfolge, Gruppierung und Farbe sind abgeleitet.

| Wert | Farbe | Achsen | Bestand | Bedeutung |
|---|---|---|---|---|
| `Freigegeben` | Grün | Stück · Artikel | live | Einsatzbereit, in keinem Auftrag. Anfangs- und regulärer Endzustand. |
| `Im Prozess` | Orange | Stück · Auftrag | live | Im Prozess genau eines freigegebenen Auftrags. |
| `Gesperrt` | Orange | Stück | live | Aus dem Verkehr gezogen, **physisch noch da**. Aufhebbar. |
| `Verbaut` | Grün | Stück | history | Steckt in einem anderen Stück (§9.6). Das Greifen IST der Ausbau. |
| `Verkauft` | Grün | Stück | history | Gehört einer anderen Partei (§4.2, §9.15). Behält seinen Ort; das Greifen IST die Retoure. |
| `Verschrottet` | Rot | Stück | history | **Physisch weg.** Endgültig. |
| `Abgeschlossen` | Grün | Auftrag | — | **Den definierten Weg zu Ende gegangen.** |
| `Abgebrochen` | Rot | Auftrag | — | Ziel nicht mehr erreichbar. |
| `Inaktiv` | Rot | Artikel | — | Erzeugt nichts Neues. **Abgeleitet** aus `replaced_by_id` (§5.5). |

Dieselbe Liste trägt die Zustände eines **Dokuments** (`docs/dokumente.md`); sie gehören nicht zum
Prozess.

- **«Abgeschlossen»** heisst «Zugehörigkeit geschlossen und vor keinem Modul mehr»
  (`order_state.order_statuses`) — auch ein Ausgang (§4.6) ist ein Ende.
- **`terminal` = «endgültig?»**; daraus folgen Wählbarkeit (`is_selectable`) und der Schutz in der
  Datenbank (§5.3), nicht die Farbe (`SYSTEM_LOGIC.md` §1.1).
- **Das Greifen IST das Aufheben** (Gesperrt, Verbaut, Verkauft); einen Endpunkt «entsperren» gibt
  es nicht. **Nichts wird gelöscht**: Gesperrtes ist ein eigenes Segment im Bestand,
  Verschrottetes steht in der Historie.
- **`stock` ist Pflicht** an jedem Stück-Status (sonst startet die App nicht, `_check`); eine neue
  Einzelinstanz ist `Freigegeben` (`INITIAL_UNIT_STATUS`).

### 5.3 Ein Endzustand ist endgültig – und das steht in der Datenbank

Ein Zustand mit `terminal = True` wird **nicht verlassen** — und kann es nicht:

| Ebene | Wo |
|---|---|
| Die eine Schreibstelle jedes Statuswechsels | `process._pass` (409 mit einem Satz, bevor etwas geschrieben ist) |
| Die Auswahl | `release.pick_problem` (nirgends angeboten, vorgewählt, aufgenommen) |
| Die Tabelle selbst | Trigger `trg_instance_units_terminal` (Skript, Migration, `UPDATE` von Hand) |
| Der Abgleich | Invariante I05 in `tests/invariants.py` (Log und Zeile widersprechen sich nicht) |

**Keine Umgehung** — kein Parameter, kein Force-Flag, keine Admin-Ausnahme. Der Trigger wird aus
dem Katalog erzeugt (`statuses.terminal_guard_sql`) und bei jedem Start nachgezogen
(`main.lifespan` → `_sync_database_rules`). **«Endgültig» heisst auch unerreichbar**, aus derselben
Frage (`release.pick_problem` → `is_terminal`): in der Auswahl-Liste (`routers/orders.unit_options`)
«nicht verfügbar» mit Grund, in der Oberfläche (`isPickable`) kein Abweichungstrigger, im Entwurf
(`orders.validate_draft`) nicht freigebbar, bei der Freigabe (`release.release`) 409. `Gesperrt`
ist nicht terminal.

### 5.4 Farbe

**Grün** Anfang/Ende · **Orange** im Prozess · **Rot** Problem · eine **eigene Farbfamilie** für
Prozessmodule (`Module.tone` → `lib/modules.MODULE_TONE`; sie sind keine Zustände). Farbe ist **an
den Status gebunden, nie an die Position**; es gibt **eine** zentrale Zuordnung Status → Farbe.

### 5.5 Ausser Betrieb nehmen und ersetzen — der Lebenszyklus des Artikels

> **«Ausser Betrieb» ist keine eigene Angabe — es ist die Folge des Ersetzens.** Die eine Angabe
> ist `articles.replaced_by_id`; `Article.status` ist eine **Projektion** (`Freigegeben` ·
> `Inaktiv`). Einen Schalter «inaktiv» gibt es nicht.

**Die Wirkung steht an einer Stelle** (`articles.may_create`): ein abgelöster Artikel **erzeugt
nichts Neues**, auch nicht als Ersatzteil. Bestehende Stücke und laufende Aufträge laufen weiter,
«ab Lager» bleibt erlaubt.

#### Was das für die Stücklisten ringsum heisst: **melden, nicht erzwingen**

Ein Artikel, dessen Stückliste einen abgelösten nennt, bleibt erzeugbar, **sagt es aber selbst**
(`services/bom.py` → `ArticleResponse.bom`; transitiv, mit Weg und Nachfolger), ebenso «wer verbaut
mich?» — am Datensatz, beim Lesen berechnet, ohne Rückfrage. Gelesen werden nur die
Artikel-Vorlagen (`article_process_steps.config.lines`, JSONB `@>`).

#### Ersetzen ist eine Angabe an der Anlage des NACHFOLGERS

Kein Versionieren: eine Änderung ist ein anderer Artikel, der den alten **ersetzt**
(`ArticleCreate.replaces_object_id` setzt `replaced_by_id`, in einer Transaktion). Abgewiesen
(`articles.assert_replaceable`): sich selbst ersetzen · Vorgänger bereits ersetzt (mit Nennung des
Nachfolgers) · Kreis. Die Kette wird zyklensicher und gekappt gelesen (`chain_of`, `MAX_CHAIN`),
die Gegenrichtung ist eine Abfrage (`predecessor_of`).

#### Darstellung

Ein schmaler Streifen über der Spezifikation (ersetzt / ersetzt durch, «wird verbaut in»,
Lücken), im Anlage-Modus die Auswahl «Ersetzt Artikel». Wächter: `tests/test_article_lifecycle.py`.

## 6. Lebenszyklus des Auftrags

### 6.1 Entwurf

«+» im Datensatzbereich öffnet einen Auftragsentwurf. **Er existiert NUR im UI**: keine DB-Zeile,
keine reservierte Objektnummer, kein Autosave; verworfen bleibt keine Spur. Einen gespeicherten
Zustand «Entwurf» gibt es nicht — ein Auftrag (mit `process_steps`) entsteht mit der Freigabe.

### 6.2 Freigabebedingungen (hart)

Freigegeben wird erst, wenn **mindestens eine Einzelinstanz** und **mindestens ein
Prozessschrittmodul** definiert sind. Der Knopf ist bis dahin deaktiviert und nennt im Klartext,
was fehlt; der Server prüft dasselbe (`services/orders.validate_draft`, gelesen von Router und
Oberfläche). **Für den Artikel gilt dasselbe** (`services/articles.missing_for_release`): alle
Pflichtfelder der Spezifikation und mindestens ein Modul; bis dahin keine Zeile, keine Nummer.

### 6.3 Was «Freigeben» auslöst — exakte Reihenfolge

| # | Schritt |
|---|---|
| 1 | **Definitionszeilen auflösen** (§2.1), Prozess bestimmen (Vorlage bei `Neu`, sonst der modellierte). |
| 2 | **Freigabebedingungen** (§6.2) + Kettenregel (§4.3). |
| 3 | **Exklusivität** (§3) für die `Lager`-Stücke. |
| 4 | **Mengen-Invariante auf dem Plan** (§2.1). |
| 5 | **Datensatz anlegen**, Objektnummer vergeben, Definitionszeilen und Prozessschritte schreiben. |
| 6 | **Neue Einzelinstanzen erzeugen** (`Neu`-Zeilen, §2.2). |
| 7 | **Mengen-Invariante auf dem Ergebnis.** |
| 8 | **Alle Stücke passieren das Start-Objekt** nach `Im Prozess`; Ereignisse geloggt. |
| 9 | Das **erste Modul wird aktiv.** |

**Eine Transaktion**; bricht ein Schritt ab, bleibt nichts Halbfertiges. Die Prüfungen 1–4 stehen
**vor** der Nummernvergabe (`nextval` ist nicht transaktional): ein abgewiesener Versuch
verbraucht keine Objektnummer; nur wenn der Unique-Index im echten Parallelfall zuschlägt, geht
eine verloren. Ein Wächter hält die Reihenfolge fest.

### 6.4 Nach der Freigabe

Die Prozessstruktur ist **eingefroren** und nicht umkehrbar — nur noch Ausführung. Was nicht mehr
passt, geht in eine Abweichung (§12).

### 6.5 Definitionen rasten ein (A5)

Eine Modul-Definition ist **nicht an Ort und Stelle editierbar**: Änderung nur durch **Löschen und
Neuanlegen** des Moduls, nach der Freigabe gar nicht mehr. Für die Liste der Einzelinstanzen gilt
die Regel nicht.

### 6.6 Die Wiederholung (Schlaufe)

Projektakte `docs/konzept/wiederkehr.md`, Sätze `SYSTEM_LOGIC.md` §5.10, Code `domain/loop.py` ·
`services/loop.py` (Einzelheiten auch in CLAUDE.md «Die Wiederholung»). Ein Auftrag, der sich im
Takt wiederholt — im **Prozess**, nicht am Preis.

- **Eingeschaltet nur im Entwurf** eines regulären Auftrags (`OrderCreate.loop`), eingefroren als
  `loop.set`: Takt (wöchentlich bis jährlich), Ab, Bis (unbefristet, Datum, Anzahl); je Lager-Zeile
  **gleiche Einzelinstanzen** oder **FIFO** (Pflicht, ohne Vorbelegung).
- **Höchstens ein Nachfolger je Auftrag**, eine 1:1-Kopie (`loop.next`, Index `ix_log_loop_next`),
  vom Takt am Termin angelegt über **denselben Weg wie «Freigeben»** (`orders.create_order`); nie
  eine Abweichung.
- **Fehlt etwas**, **wartet** er (keine Periode geht verloren); ist ein Stück verschrottet oder der
  Artikel ersetzt, **geht es nicht mehr** — beides in «zu tun» (`loop.problem`). **Beendet** am
  neuesten Auftrag (`loop.ended`).
- **Zahlung** jedes Mal Offerte → Zusage → Rechnung; mit Zusage des Vorgängers und allen Preisen
  vorgegeben still (`loop.agreed`).
- **Bild**: Karte «Wiederholen» unter dem Ende, Linie **links** zurück zum Start.

## 7. Richtung und Historie

### 7.1 Nur von oben nach unten

Einzelinstanzen wandern **ausschliesslich abwärts**. Was schiefgeht, geht **seitlich** in einen
Abweichungsauftrag und kommt an **genau der Stelle** zurück, an der es ausgeschert ist (§12).

### 7.2 Geloggt und eingefroren

Jedes Passieren schreibt einen Eintrag ins **Ereignis-Log**: append-only, unveränderlich,
vollständig (wer, wann, welches Stück, welcher Übergang, welche Eingaben). Eine Korrektur ist ein
**neuer Eintrag**.

### 7.3 Zwei Fragen, keine dritte

**Was läuft jetzt?** (Laufzeit-Zustand) und **Was ist passiert?** (Log) — **nicht**, was passieren
wird. Unterhalb der aktuellen Stelle steht keine Aussage über Material.

### 7.4 Die Journey — ein Prozess, aufgeteilt in Aufträge

Ein Stück läuft nacheinander durch viele Aufträge; die **Journey** (`services/journey.py`) zeigt
über dem Start den Auftrag davor, unter dem Ende den danach — **abgeleitet aus dem Log** (§11.3),
ohne Zeiger-Spalten: Vorgänger = Auftrag des letzten Ereignisses vor dem ersten dieses Stücks
hier; Nachfolger = Auftrag des ersten Ereignisses nach dem letzten. Ein Nachbar erscheint erst,
wenn es ihn gibt; **gruppiert** mit Stückzahl («aus 100000123 · 5000»), nach Stückzahl absteigend,
dann nach Nummer; kein Nachbar → nichts; ein gelöschter fällt heraus. Gemeint ist das **Stück**,
nicht der Artikel. Ein Index über Stück und `id` macht es zu zwei Abfragen je Auftrag.

## 8. Wo der Prozess lebt

Ausgeführt wird im **Auftrag**; definiert an zwei Orten mit **identischer Darstellung**: im
Auftrag (konkrete Einzelinstanzen, ausführbar) und am **Artikel** (Erzeugungsprozess als
**Vorlage**, nicht ausführbar). Beide nutzen dieselben Bauteile (`ProcessColumns` im Modus
`definition`, `AddModule`); dem Artikel fehlt nur der Definitionsbereich über dem Start.

### 8.1 Eine Komponente, zwei Modi

`definition` (Start · Module · Ende; hinzufügen, löschen, sortieren) und `ausfuehrung` (dazu
Zustand je Objekt und aktuelle Stelle; nichts an der Struktur). Der Entwurf ist `definition`, der
freigegebene Auftrag `ausfuehrung`. Die Liste der Einzelinstanzen ist ein Slot **über** dem
Diagramm, nicht Teil davon.

### 8.1a Das Bild — Zeichenregeln in `docs/prozessbild.md`

**Der Server liefert einen Graph** (`services/flow.build`, Knoten `start · module · end · fork ·
join`, eine Position ist immer eine Kante), abgeleitet aus dem **Log**, nicht aus dem Zustand.
**Eine Linie ist kräftig, wenn laut Log mindestens eine Einzelinstanz die Kante genommen hat**,
sonst Haarlinie. **Die Oberfläche layoutet und zeichnet** (`process-flow.polyPath`) und leitet
nichts ab; verletzte Invarianten stehen als `FlowGraph.problems` rot im Bild.

### 8.2 Artikel-Reiter «Erzeugungsprozess» — die Vorlage

Neben «Spezifikation»: dieselbe Darstellung, derselbe Modul-Editor; dort wird **nur der Prozess
definiert**. Die Vorlage liegt in `article_process_steps`, es gibt keinen Endpunkt, der sie
ausführt. Sie entsteht mit dem Artikel (ein `POST`, Anlegen = Freigeben) und ist danach nicht
mehr änderbar. Bei der Freigabe eines Erzeugungsauftrags wird sie in `process_steps` **kopiert**
(Kopie, nicht Verweis).

## 9. Die Prozessschrittmodule

Heute **fünf** (§9.0–§9.15); was ein Modultyp ist, steht in `domain/modules.py` (`MODULES`),
ausgeführt wird jeder über `…/steps/{id}/confirm` (`process.confirm_step`). **Was alle gemeinsam
haben, steht im Rahmen**: Statusregel (§4), Verifikation (§4.4), Halt (§4.5), Ausgang (§4.6),
Stichprobe (§9.3), Protokoll (§9.7).

**Was von selbst weiterzieht, steht an EINER Stelle** (`process.carry_on`): jeder Ort, an dem sich
etwas ändert (bestätigt, abgezweigt, zurückgekehrt, bezahlt), fragt in dieser Reihenfolge —
(1) Stichprobe durch → der ungezogene Rest läuft (`_run_through`, §9.3); (2) ein Zahlungsmodul
darf durchlassen (`advance_payments`, §9.15).

### 9.0 Das Modul «Datenerfassung»

Im Prozess Daten erfassen und kontrollieren (Richtung Qualitätssicherung). Ein **Durchläufer**:
wer es passiert, bleibt `Im Prozess`.

- **Anlegen**: kein Name (er steht im Typ) · Stichprobe (§9.3) · **Erfassungspunkte** (Bezeichnung
  und Typ, mindestens einer). **Alles, was angelegt ist, ist Pflicht**; die Bezeichnung wird bei
  der Freigabe verlangt.
- **Laufzeit**: eine Zeile **je Instanz**, die davorsteht, mit Vorschau vor dem Scan (Nummer,
  Artikel, «3 von 10 Stück erfassen · 7 laufen ohne Erfassung durch», was erfasst wird); je
  Instanz ein Scan-Knopf, dazu der Sammel-Knopf.
- **Bestätigen**: Instanz verifiziert (§4.4) · je gezogener Einzelinstanz ein Wertesatz (§9.5) ·
  fehlende Punkte → Fehler, der sie **benennt** · Urteil **je Stück** · bestanden → loggen, die
  Stücke rücken vor · ein «nicht bestanden» → §4.5.

### 9.1 Die Erfassungspunkt-Typen — eine geschlossene Liste aus Bausteinen

| Typ | Erfassung | Urteil? |
|---|---|---|
| `text` | Freitext | nein |
| `bool` | Ja/Nein (Daumen); «nicht angetippt» ist nicht «nein» | **ja** |
| `photo` | **genau eine Aufnahme je Stück, über die Kamera** (kein Upload, `Photo.missing`) | nein |
| `signature` | handschriftlich | nein |
| `measure` | Soll-Ist (Sollwert Pflicht, Toleranz optional) | **ja** |

**Jeder Typ ist eine eigene Datei** mit eigener Klasse (`domain/capture_types/`: prüfen, wissen was
fehlt, bewerten), die Registry findet sie selbst (`pkgutil`). Einen Typ «Objekt scannen» gibt es
nicht (`docs/attic.md`); Werkzeug-/Prüfmittel-Nachweis ist bewusst offen (`SYSTEM_LOGIC.md` §5.9).

### 9.2 Was erfasst wurde, hängt am Stück

Eine Erfassung ist eine Zeile in `captures` (Einzelinstanz, Auftrag, Modul); geschrieben nur
durch Bestätigen an einem Modul, gelesen frei (Instanz-Detail, Reiter «Datenerfassung»),
geändert nie. Ist es das letzte Modul, passiert das Stück im selben Zug das Ende (§3.1).

### 9.3 Die Stichprobe — EINE Zahl: der Anteil an der Gesamtmenge

Definition `domain/sampling.py`, Ziehung `services/sampling.py`. Ein **Anteil in Prozent**:
**alle** (100 %, Vorgabe) · **Hälfte** · **Viertel** · frei 1–100 %.

- **Bezug ist die GESAMTMENGE** des Auftrags an diesem Modul; aufgerundet, mindestens eines,
  höchstens alle.
- **Gezogen beim ERREICHEN** des Moduls, einmal je Modul, idempotent (`sampling.ensure`);
  **zufällig** (`random.sample` über die nach id sortierte Menge) und **eingefroren** als
  `sample`-Ereignis.
- **Erfassungen** = Stücke in der Stichprobe; **Scans** = Instanzen, zu denen sie gehören.
- **Der Rest läuft ohne Erfassung durch — sichtbar**: bewegt vom Dienst (`process.carry_on` →
  `_run_through`, im Log `sampled: False`), **erst wenn die Stichprobe dieses Moduls durch und
  bestanden ist** (`_sample_cleared`), kaskadierend über die folgenden Module. Ein Modul ohne
  Erfassungspunkte ist nie «durch»; ein terminales wird nie durchlaufen.

### 9.4 Das Modul «Aussondern» — verschrotten oder sperren

Zieht Einzelinstanzen **aus dem Verkehr** — **Verschrotten** (`Verschrottet`, physisch weg,
endgültig) oder **Sperren** (`Gesperrt`, physisch da, ein Auftrag greift es wieder, §5.2). Der
Zielzustand ist ein **Parameter** (`config.mode`), der Status folgt daraus
(`Module.exit_status_for`); ein Status-Dropdown gibt es nicht.

- **Terminal** (§4.6): `Im Prozess` → `Verschrottet`/`Gesperrt`, das Stück verlässt den Auftrag.
- **Anlegen**: Ausprägung und **Grund** (`config.reason`), beide Pflicht — der Grund wird beim
  **Modellieren** gegeben, für beide Ausprägungen; er reist als `ProcessStepResponse.reason` als
  Auskunft an die Ausführung. Keine Erfassungspunkte, keine Stichprobe.
- **Ausführen**: verifizieren (Scan-Pflicht, §4.4) · Zustand setzen · loggen. Der Scan ist die
  Bestätigung.
- **Keine Teilmengen**: was ankommt, wird ausgesondert; wer nur einen Teil meint, gibt nur ihn in
  den Auftrag. Verschrotten hat kein Ziel (kein «Schrottlager»).

### 9.5 Der Scan gilt der Instanz, die Erfassung der Einzelinstanz

> **Das sind zwei verschiedene Dinge und dürfen nie gekoppelt sein.**

Der Scan sagt etwas über das physische Ding (die Instanz), eine Messung über **ein Stück**. Die
Zahl der Erfassungen folgt der **Ziehung**: Charge über 2, «alle» → 1 Scan, **2** Erfassungen;
Charge über 6000, ¼ → 1 Scan, **1500**; Einzelserialisierung 3 → 3 und 3.

- **Zweistufige Nutzlast**: Nummer der Einzelinstanz → (Punkt → Wert); **Deckung in beide
  Richtungen** (`process._captures_for`).
- **Das Urteil hängt am Stück**, der Halt an der Instanz (§4.5); das `capture`-Ereignis trägt je
  Stück sein **eigenes** Ergebnis.
- **Gezogene Nummern erst auf Klick** (`…/steps/{id}/hold?group=sample`); die Vorschau nutzt die
  Zahlen aus `step_work`.

### 9.6 Das Modul «Verbrauch» — Montage und Materialverbrauch

> **Der Zwilling des Aussonderns**: `Verschrottet` heisst «gibt es nicht mehr», `Verbaut` «steckt
> jetzt in etwas anderem».

**Die Stückliste ist die Konfiguration** (`config.lines`): je Zeile **Artikel** + Menge **pro
Produkt-Stück** (1–1000, jeder Artikel einmal), gerechnet beim **Erreichen**. Im Editor dieselbe
Komponente wie der Bedarf am Auftragsanfang (`DefinitionLines`, `perUnit`), ohne Herkunft und ohne
konkrete Stücke — gewählt wird beim Ausführen.

#### Gebunden wird beim Erreichen — der zweite Eintrittspunkt

Die Komponenten **treten am Modul ein** (`process._enter_at_step` → `_pass`):
`Freigegeben ──(Scan)──▶ Im Prozess ──(Bestätigen)──▶ Verbaut`, beides im Log, mit demselben
`start`-Ereignis (mit Modul-`id`, `flow._tally`) und derselben Exklusivität. Das Produkt bleibt
`Im Prozess`. **Genommen wird nur, was frei ist** (`Freigegeben`, keine offene Zugehörigkeit) — ein
Verbrauch macht den Auftrag nie zur Abweichung.

#### Die Zuordnung steht im Log — je Produkt-Stück

Welche Komponente in welches Produkt ging, steht im Payload (`into`), kein Feld am Stück;
zugeteilt deterministisch, Produkt für Produkt (`consumption.plan`).

#### Nichtverfügbarkeit ist kein Zustand

Reicht der Bestand nicht, geht die Freigabe trotzdem; das Modul **bewegt nichts** und nennt
Artikel, Bedarf und Verfügbarkeit. Angeboten: *andere Instanz wählen* (`sources`) · *Nachschub
anlegen* (gewöhnlicher Entwurf). **Automatisch ausgewichen wird nie.**

#### Material am richtigen Ort — dieselbe Aussage, eine Spalte weiter

Wo das Material liegen muss, ist **abgeleitet** (`Module.material_place = AT_PRODUCT`): wo die
Produkte liegen, «am Ort» heisst **in der Kette** (`places.within`); liegen sie nirgends oder
verstreut, wird nichts verlangt. `StepNeed` nennt *gebraucht · verfügbar · davon hier* — `needs`
als Auskunft, `plan` als Riegel (409 mit dem Ort). Der Weg dorthin (*holen lassen*) ist ein
gewöhnlicher Auftrag mit Bewegen-Modul, vorgewählt angeboten, **nie automatisch angelegt**.

#### Was daraus folgt

- `Module.terminal` ist **False**; `Verbaut` ist nicht terminal (Ausbau = Greifen, `places.take_out`).
- **Die Stückliste eines Stücks ist eine Ableitung** (`services/genealogy`); Ausgebautes bleibt
  darin, als *ausgebaut*.
- Ein Auftrag **verbaut nicht, was er selbst erzeugt** (Freigabe-Fehler).

### 9.7 Das Protokoll — ein abgeschlossenes Modul zeigt lückenlos, was in ihm geschah

> **Feste Regel für ALLE Module**: auf Klick **alle erfassten Daten, je Einzelinstanz**.

**Eine** Ableitung über den Log (`services/record.py` → `GET …/steps/{id}/record`), **eine**
Komponente (`components/erp/step-record.tsx`); gespeichert wird dafür nichts.

- **Ein Eintrag ist ein VORGANG**, nicht ein Stück — eine Wiederholung nach «nicht bestanden»
  steht daneben. Gebaut aus `capture` (erfasst: Werte, Urteil je Stück, wer, wann) und `step`
  (passiert: Vorher/Nachher aus dem Log, Verifikation, ggf. `into`); ein `capture` ohne
  folgendes `step` ist ein «nicht bestanden».
- **«Nicht gezogen»** kommt aus dem `sample`-Ereignis (`sampling.was_drawn` / `drawn_at`).
- **Jeder Wert steht mit seiner Frage**; ein Wert zu einem unbekannten Punkt roh mit Schlüssel.
- **Erst auf Klick, seitenweise, mit Gesamtzahl.**

### 9.8 Das Modul «Bewegen» — und der Ort darunter

Einzelinstanzen von A nach B bringen. Ein **Durchläufer** (bleibt `Im Prozess`), nicht terminal. Ein
Ort ändert nie Status oder Zugehörigkeit — darum muss keine andere Regel von diesem Modul wissen.
Eine Schreibstelle: `services/places.py`.

#### Der Ort: ein Zeiger, sonst nichts

`instance_units.place_object_id` = Objektnummer des **Halters**, ohne Typfeld
(`objects.resolve_object_type`): **Instanz** (Regal, Behälter, LKW), **Benutzer** (Mitarbeiter,
Kunde, Spediteur) oder **Unternehmen** (Werk, Hauptsitz).

#### Zwei Arten von Halter — die Genauigkeit ist die der Quelle

`place_object_id` = **gescannter** Halter; `place_unit_id` = **Träger**, das Stück, in dem dieses
steckt (beim Verbauen). Ein `CHECK` erlaubt höchstens eines; am Träger **wandert es mit**. Der Log
sagt, *worin* verbaut wurde (`payload.into`), die Spalten, *wo es jetzt liegt*.

#### Jedes Stück behält seinen Ort – ausser es ist verschrottet

In `process._pass`: **Verschrottet** → kein Ort · **Verbaut** → sein Träger · **Verkauft**,
**Gesperrt** → Ort bleibt. Ausgebaut bekommt es den Ort des Trägers (`places.take_out`). Der Ort
hängt am **Stück**; `NULL` ist regulär. Die Vergangenheit steht im Log (`process.step`).

#### Die eine Regel des sonst dummen Feldes: keine Zyklen

Verhindert beim Schreiben (`places.assert_placeable`), gekappt beim Lesen (`MAX_STATIONS`).

#### Die Kette

`Schraube › Behälter › Regal › Werk Nord` — bis ein Halter eine **Anschrift** trägt. Eine Instanz
ist verortet, wenn **alle** ihre Stücke am selben Halter liegen. **Aufgelöst je Halter, nie je
Stück** (`places.chains_for`; Wächter `test_move_module.test_the_chain_is_resolved_per_holder_not_per_piece`).
Scheitert die Kette, bleibt die Ansicht lesbar.

#### Das Ziel ist optional — und das ist eine Aussage

Definiert → der Ziel-Scan **verifiziert**; offen → er **wählt** («wird beim Ausführen gescannt»).

#### Ware zuerst, Ziel zuletzt

**Der Ziel-Scan ist die Quittung der Ablage.** Der Sammel-Scan quittiert das Ziel **einmal**.

#### Eine Spedition ist ein Einkauf

Dafür steht ein Zahlungs-Modul (Ausgabe, §9.15) daneben; Bewegen weiss davon nichts.

### 9.9 «Ausliefern» — entfernt

Siehe `docs/attic.md`. «Gehört jetzt jemand anderem» folgt aus Bewegen und Zahlung; `Verkauft`
schreibt das Ende-Objekt (§4.2, §9.15).

### 9.9a «Beschaffen» und «Verkauf» — entfernt

Siehe `docs/attic.md`. Einkauf und Verkauf sind ein Zahlungs-Modul (§9.15).

### 9.12–9.14 «Zahlung (alt)» — entfernt

Siehe `docs/attic.md`; Wortlaut in `docs/history/2026-09-zahlungsmodul-vorgaenger.md`. Was weiter
gilt, steht in §9.15.

### 9.15 Das Modul «Zahlung» — der Beleg

> Schlüssel `beleg`. `domain/voucher.py` · `services/voucher*.py` (Kern → Kopf → Geld →
> Handlungen → Ansicht, `backend/CLAUDE.md`) · Papiere `services/voucher_docs.py` +
> `services/a4.py` · Seite nach aussen `routers/public_documents.py` · Karte
> `components/erp/beleg-work.tsx`. Entstehung: `docs/history/2026-10-process-core-9-15-chronik.md`.

**Geld mit einer zweiten Partei, EIN Modul** für Einnahme ↔ Ausgabe (`Direction`). Der Vorgang
hängt am **Schritt**: ein Auftrag kann Ausgabe und Einnahme tragen; eine Anzahlung ist ein
zweites Modul.

#### Stufen, Verben, Leiste

```
offer      Angebot      schreiben · anbieten (ask) · annehmen (agree)
agreed     Auftrag      → bill: Nummer, Betrag, Steuer, Fälligkeit werden eingefroren
billed     Rechnung     → Geld (pay · refund · writeoff · tip · reverse) · Mahnung · Ausfuhrnachweis
cancelled  storniert    Ausgang
```

- **Jedes Verb an EINER Stelle** (`VERBS`, `voucher_actions`); **`can` ist Auskunft UND Tor**.
  **Erledigt ist abgeleitet** (`is_done`: gestellt ∧ Saldo 0 ∧ ggf. Ausfuhrnachweis). **Die
  Leiste** (`situation`) ist nie leer ausser bei Erledigt/Storniert («keine Sackgasse»).
- Jeder Wert wird sofort gespeichert, **geprüft beim Hinausgehen** (`ask`, `gaps`). **Wählen ist
  nicht anbieten** (`party` · `ask` · `unask`); die eigene Gesellschaft ist nie Gegenpartei.
- `config.instruction` (was zu tun ist) gehört dem Modul, `config.parties[].ref` (wie bestellen)
  der Paarung Modul × Partner. **Gültigkeit** in Tagen (Vorgabe 30); **angenommen wird nur die
  aktuelle Fassung** (`offered_hash`).

#### Die Stücke ziehen von selbst weiter – und das Eigentum wird abgeleitet

- **Die Stücke passieren das Modul von selbst** (`voucher.passable`, `process.carry_on`): mit der
  Zusage, bei Vorauszahlung mit der vollen Zahlung; kein «Bestätigen» (`PASSES_ITSELF`). Sie
  bleiben `Im Prozess`, ein Ort wird nicht gesetzt.
- **Eigentum** «geht an die Partei · geht an uns» ist eine **Pflichtwahl ohne Vorbelegung**
  (`ownership_problem`), eingefroren mit der Zusage; ausgewertet nur am Ende-Objekt
  (`voucher.sold_units`, §4.2). Ein Storno wirkt von selbst.
- **Passen die Stücke nicht mehr** (`units_problem`), bleibt nur «Stornieren».

#### Der Beleg IST die Rechnung – eine je Modul

Nummer (`<Auftragsnummer>-<laufend>`), Datum, Fälligkeit, Betrag und **eingefrorene Steuer**
stehen am Beleg. **Ein Wort für den Storno: «Stornieren»** (`revoke`); nach der Rechnung entsteht
die **Gutschrift über die ganze Rechnung** von selbst. Eine Korrektur ist ein eigener Beleg in
einem eigenen Modul (`correct` → `corrects_id`), auch über Auftragsgrenzen. Jede Zahl ist eine
Menge, nie negativ getippt (`minus`, `inbound`).

#### Geld, Zustand, Mahnung

Geld-Zeilen (`voucher_entries`): Zahlung · Ausbuchung (mit Grund) · Trinkgeld; «falsch erfasst?»
bucht gegen; **eine Referenz gehört zu genau einer aktiven Zahlung**. Drei Wege (`_ways`): bar ·
Überweisung (Swiss QR-Rechnung) · Karte (Stripe, gebucht **nur vom Webhook**). Der Zustand der
Rechnung ist abgeleitet (`invoice_state`). Teilbetrag je Position. **Mahnung** drei Stufen à 10
Tage, von Hand (`remind`).

#### Die Anschrift entscheidet

Steuer je Position (MWSTG Art. 26; Ware nach Lieferadresse, Dienstleistung nach Sitz;
`domain/voucher.VAT_RATES`), Fremdwährung (nur ins Ausland, eine je Vorgang), Zoll (nur Export) und
der Ort der Lieferbedingung (Incoterms 2020). **Lieferantenrechnung** mit Dokument
(`voucher.original`), Abweichung → «So annehmen» mit Grund; **Ausfuhrnachweis** mit Dokument
(`voucher.export`).

#### Die Papiere

Jedes Papier (`DOCUMENTS`) entsteht aus **einer A4-Vorlage** (`services/a4.py`), nennt die
Seriennummern (`serials_of`), trägt die AGB und ist ein **Dokument** (`voucher.doc`, nie löschbar).
**Vorschau → Freigeben** (`PAPER_VERBS`, `voucher_docs.preview`); Auftragsbestätigung und Quittung
**stehen an** (`papers_due`) und gehen nie von selbst (`AUTO_RELEASE` leer). Hinaus per Mail mit
Link `/dokument?t=…`. Die Zahlungen-Liste (`services/payment_list.py`) ist eine Ableitung.
Offen: `docs/backlog.md`.

## 10. Darstellung

### 10.1 Regeln

- **Nur Vergangenheit und Gegenwart**; unterhalb der aktuellen Stelle **kein Material**.
- **Ein Prozessobjekt = eine Komponente**; der Modultyp ist Konfiguration.
- **Keine festen Pixel oder absoluten Positionen**: Knoten bestimmen ihre Position selbst, die
  Linien werden daraus berechnet; Knoten-Layout und Linien-Layer sind getrennt.
- **Responsive** (Resize, Zoom), schmal nur die mittlere Spalte; **nie waagrecht scrollen**.
- **Keine erfundenen Daten, keine Fallback-Anzeigen** — ein Fehler mit Ursache und Ort.
- **Grosse Mengen werden gezählt**: je Zustand eine Pille mit Anzahl (`unit_groups`), Nummern auf
  Klick (`GET …/units`); eine gekappte Historie sagt es.
- Ein Modul startet **eingeklappt, ausser es ist dran** (laufend das aktive, im Entwurf das
  zuletzt angelegte).

### 10.2 Technologie

Fluss-Layout mit SVG-Overlay auf gemessenen Ankern (kein Canvas, keine Graph-Bibliothek) –
Einzelheiten in `docs/prozessbild.md`.

### 10.3 Der Bestand — eine Frage, drei Ebenen, kein Filter

*Wie viel habe ich, in welchem Zustand, unter welcher Nummer?* — reine **Summierung über
Einzelinstanzen** (§2). **EIN Modul** (`components/erp/stock-view.tsx`) am Artikel (Reiter
«Bestand», Zeilen = Instanzen) und am Instanz-Datensatz (Zeilen = Einzelinstanzen).

| Ebene | Zeigt | Kommt von |
|---|---|---|
| 1 | **beschriftete Leiste**: je Zustand ein Segment mit Punkt · Wort · Menge | `GET /erp/articles/{id}/stock` → `states` |
| 2 | zum **gewählten** Zustand je Instanz: Nummer · Menge in diesem Zustand | dieselbe Antwort, `instances` (seitenweise, 50) |
| 3 | die Nummern der Stücke mit Zustand und Auftrag | `GET /erp/instances/{id}/units` (auf Klick, seitenweise, 60) |

**Kein Filter** — die Leiste ist das Bedienelement, sie **nennt** ihre Zustände, genau einer ist
offen (zu Beginn keiner). **Die Ansicht zählt keinen Status auf**: Segmente aus `states`,
Reihenfolge aus dem `CATALOG`, Farbe aus dem Ampelton, Bestand aus `stock`; Unbekanntes wird
gemeldet. Keine Gesamtzahl im Kopf; die Instanz hat eine Aufstellung, keinen Zustand; kein
Sonderfall für Einzelserialisierung. **Aufsteigend nach Objektnummer = FIFO**, gruppiert nach
Instanz; die Leiste gilt immer für das Ganze.

## 11. Datenstruktur — drei Ebenen

Definition, Laufzeit-Zustand und Log sind getrennt; die Wahrheit über das Geschehene steht nur
im Log.

### 11.1 Ebene 1 — Prozessdefinition (die Modellierung)

```
process_steps            id · order_id · position · module_type · config(JSONB)
article_process_steps    id · article_id · position · module_type · config(JSONB)
```

**Eine geordnete Liste, kein Graph** — `position` ist die Kante; Verzweigungen sind eigene
Aufträge (§12). **Kein Übergang je Schritt** (§4, Migration 186). Start und Ende sind **keine
Zeilen** (§4.1). **Die `id` IST die Identität eines Moduls** — der Log zeigt nur auf sie; ein
Namensfeld gibt es nicht (der Name kommt aus dem Typ). Daneben `order_lines`: die
festgeschriebenen Definitionszeilen, damit die **Herkunft** (erzeugt oder geholt) bleibt.

### 11.2 Ebene 2 — Laufzeit-Zustand (wo steht was)

```
instance_units.status        welchen Status hat das Stück
order_units.current_step_id  an welchem Objekt steht es   (NULL = am Ende)
order_units.released_at      NULL = aktiv, sonst Historie
```

**Projektion, nicht Wahrheit**: nachgezogen ausschliesslich beim Schreiben eines Log-Eintrags
(`process._pass`); die Invarianten (`tests/invariants.py`) melden, wenn Log und Zeile
auseinanderlaufen. **Die Exklusivität (§3) als partieller Unique-Index:**

```sql
CREATE UNIQUE INDEX uq_order_units_active
    ON order_units (instance_unit_id) WHERE released_at IS NULL;
```

*Aktiv* ist exklusiv, *referenziert* beliebig oft; ein abgeschlossener Auftrag behält seine Liste.

### 11.3 Ebene 3 — Ereignis-Log (die eingefrorene Historie)

```
log  (event = process.<art>, Sicht process_log / models.ProcessEvent)
  id · order_id · step_id · instance_unit_id · kind · status_before · status_after
  payload(JSONB) · actor_id · created_at
```

Der **eine Log** des Systems (CLAUDE.md «Das Log»), geschrieben nur von `process._pass` und seinen
Geschwistern über `services/log.process_events`; append-only, die `id` ist die Zeitachse.
**Vorher/Nachher sind Tatsachen** jedes Ereignisses (auch wo nichts wechselt: `capture`,
`sample`). Arten: `start` · `step` · `capture` · `sample` · `end` · `handover` · `return`; der
Eintritt in eine Abweichung ist ein `start` mit anderem Vorher als Freigegeben/Verkauft (§12.2).
Der Log beantwortet «was geschah hier» (§7.2) und «wo war das Stück davor/danach» (§7.4); einen
zweiten Ereignis-Strom gibt es nicht.

## 12. Abweichungsaufträge

Was vom Soll abweicht — nochmals kontrollieren, nacharbeiten, aussortieren, zurückschicken — wird
**mit einem Auftrag** dargestellt, nicht als Modultyp.

### 12.1 Ein Abweichungsauftrag ist 1:1 ein regulärer Auftrag

Kein eigener Datensatztyp, keine zweite Tabelle, kein zweiter Endpunkt, kein Sonderweg:
dieselbe Definition, Exklusivität, Module, derselbe Log.

> **Wer im Code nach `if abweichung:` sucht, hat es falsch gebaut.**

Ihn macht die Herkunft seiner Stücke aus (§12.2). Ein Stück aus einem laufenden Auftrag wird ihm
**entzogen** — in einer Transaktion: alte Zugehörigkeit schliessen, neue anlegen (`handover`).
Der Status **wechselt dabei nicht** (bleibt `Im Prozess`).

### 12.2 Das Label ist abgeleitet, nicht gesetzt

> **Ein Auftrag ist eine Abweichung, wenn sein Start vom Regelstart abwich.**

Regulär beginnt, was **ruht** (`statuses.REGULAR_STARTS`): `Freigegeben` (bei uns) oder
`Verkauft` (bei der Partei). Alles andere — entzogen, gesperrt, verbaut — ist eine dokumentierte
Abweichung, gefragt am Log (`order_state.deviation_flags`):

```sql
kind = 'start' AND status_before NOT IN ('freigegeben', 'verkauft')
```

Eine **Retoure** ist keine Abweichung, sondern eine Eigentumsfrage (`voucher.sold_units`). FIFO
und Verbrauch nehmen nur `Freigegeben`. Ein künftiger Zustand ist automatisch eine Abweichung; ein
terminales Stück lässt sich gar nicht greifen (§5.3). Kein Feld, kein Flag.

### 12.3 Die Rückführung ist eine Eigenschaft der VERBINDUNG

```
order_units.return_to_order_id   in welchen Auftrag kehrt dieses Stück zurück (NULL = nirgendwohin)
```

Jede Kante entscheidet für sich — Schachtelung und Parallelität brauchen keine zweite Regel.
Entschieden bei der **Definition** («kehrt zurück» / «bleibt hier»), nachträglich nicht
umschaltbar. **Rückführend**: der Hauptauftrag wartet und läuft danach an derselben Stelle weiter.
**Gekappt**: er läuft mit reduzierter Menge weiter. Seine Menge *ist* die Zahl seiner aktiven
Zugehörigkeiten.

### 12.4 Die Abzweigung hängt an einem ZUSTANDSPUNKT, nicht an einem Modul

Ein **Zustandspunkt** ist die Stelle, an der ein Stück wartet: `order_units.current_step_id` =
«steht VOR diesem Modul» (`NULL` = nach dem Ende).

> Die Abzweigung hängt an der **aktuellen Position** der Einzelinstanz. Vor dem Modul, wenn sie
> davorsteht; dahinter, wenn sie es passiert hat.

Heute steht ein Stück **immer** vor dem Modul, wenn es abweicht — auch nach «nicht bestanden»
(§4.5); die Linie geht vor dem Modul ab und kommt an **denselben Punkt** zurück, danach durchläuft
das Stück das Modul regulär (`SYSTEM_LOGIC.md` §5.5). **Die Rückkehrposition braucht kein Feld**:
beim Ausscheren wird die Zeile geschlossen (`released_at`), `current_step_id` bleibt — geschlossen
mit `NULL` = angekommen, gesetzt = ausgeschert und die Stelle der Rückkehr. Ein Zustandspunkt wird
gezeichnet, wenn dort etwas steht oder eine Abzweigung ansetzt (Anker `statePointId`); ein
Abweichungsauftrag kann an **mehreren** Punkten zugreifen (`RelatedOrder.branches`).

### 12.5 «Wartet auf Rückführung» wird abgeleitet

Gezählt werden die **offenen rückführenden Verbindungen** auf diesen Auftrag, über die ganze Kette
(`order_state.waiting_counts`, `pending_returns`). Daraus auch der **Auftragsstatus** (`_derive`):
noch etwas aktiv oder verliehen → `Im Prozess`; sonst mindestens eines angekommen →
`Abgeschlossen`; sonst `Abgebrochen` — in dieser Reihenfolge.

### 12.6 Ein Modul, auf dessen Rückführung gewartet wird, ist GESPERRT

Der Inhalt bleibt sichtbar; **keine Eingabe, kein Bestätigen** — auch nicht über die API. Der Grund
**nennt den Abweichungsauftrag**. Gekappte Ausleihen sperren nichts; **die Kette zählt** (A→B→C
sperrt auch A). Durchgesetzt in `process.confirm_step` (`_ready_at`), dargestellt von `StepCard`
(`fieldset[disabled]`) — keines davon ist ein Modul.

> **Ein Modul fragt nicht, ob es darf. Ihm wird gesagt, dass es nicht darf.**

### 12.6a Die Auswahl nennt, wo sie zugreift

Jeder gewählte Anteil trägt seine **Absicht** (`UnitPick.from_order`): `null` = «ein freies
Stück», eine Objektnummer = «aus genau diesem Auftrag» (die Abweichung). Die Freigabe vergleicht
Absicht und Wirklichkeit (`release._assert_as_picked`); weicht sie ab, passiert nichts, und der
Fehler nennt beide Seiten. **Ein Auftrag ändert nie unbemerkt seine Art.** Eine Auswahl-Logik:
FIFO schlägt vor, der Mensch übersteuert. Freie und gebundene Stücke dürfen im selben Auftrag
stehen; `return_to_order_id` entsteht nur für die geliehenen.

### 12.7 Wann darf ein Stück ein Modul verlassen?

**Offen** (§13, Punkt 2). Gebaut ist die restriktive Variante: wurde in einem Modul mit der
Eingabe begonnen, ist der Auslöser gesperrt. Die Regel ist eine **Eigenschaft des Modultyps**
(`Module.units_may_leave`, gelesen in `release._assert_may_leave`); die Sperre sitzt in der
Oberfläche, weil eine unbestätigte Eingabe weder in der Datenbank noch im Log existiert.

### 12.8 Darstellung — drei Spalten, eine Komponente

```
   übergeordneter Auftrag (verblasst) │ dieser Auftrag (Fokus) │ Abweichungsaufträge (verblasst)
```

Eine Seitenspalte nur, wenn es dort etwas gibt; die Nachbarn zeigen exakt ihren Prozess mit
**derselben Komponente** (`FlowColumn`, `faded`); ein Klick macht den Nachbarn zur Mitte. Eine
Querlinie führt dorthin, wo das Stück ausscherte, eine zweite zurück, wo es weitergeht (bei
gekappter Rückführung fehlt sie). Höchstens **drei** Nachbarn voll, der Rest als «+N weitere» mit
Gesamtzahl.

## 13. Bewusst noch nicht definiert

Nicht entschieden — nachgetragen einzeln, nicht beim Bauen erraten:

1. **Weitere Prozessschrittmodule** nach Bedarf; ein Wiederaufbau beginnt bei der Modellfrage in
   `docs/attic.md`.
2. **Darf ein Abweichungsauftrag noch ausgelöst werden, wenn in einem Modul mit der Eingabe
   begonnen wurde?** Vorläufig «nein», als Eigenschaft des Modultyps (§12.7).
3. **Wer darf aussondern, verschrotten, stornieren?** Heute jedes Personal (`SYSTEM_LOGIC.md`
   §4.5, R10). Eine Abbruch-Funktion gibt es nicht (§3.1).
4. **Zwei `Neu`-Zeilen mit verschiedenen Vorlagen** — heute ein harter Fehler (§14).
5. **Die Vorlage im Entwurf abweichen lassen** — heute nicht möglich; falls gebraucht, ein eigener
   Vorgang «von der Vorlage lösen».
6. ~~Wiederkehrende Aufträge~~ — entschieden und gebaut, §6.6.

## 14. Getroffene Annahmen

Wo die Vorgabe eine Lücke liess, gilt die einfachste Variante, die die Regeln erfüllt. Was oben
schon als Regel steht (§2–§12), wird hier nicht wiederholt; Begründungen in der Chronik.

| | |
|---|---|
| **Ein Auftrag hat EINEN Prozess** | Zwei `Neu`-Zeilen mit verschiedenen Vorlagen: harter Fehler mit Klartext. |
| **Die gespiegelte Vorlage ist im Entwurf nicht editierbar** | Geändert wird am Artikel; ein reiner `Lager`-Auftrag bleibt frei modellierbar. |
| **Reiter-Name «Erzeugungsprozess»** | Lässt Platz für eine zweite Art Vorlage. |
| **Ein Modul bewegt alle Stücke einer Instanz, die davorstehen** | Je Instanz, weil der Scan die Instanz verifiziert (§4.4); die Historie bleibt je Stück. |
| **Fehlermeldungen sagen was und wo** | Ein `RequestValidationError`-Handler übersetzt jeden Eingabefehler in Klartext mit Feldpfad («Prozessschrittmodule → 1 → Modultyp: fehlt»); ohne Bezeichnung erscheint der technische Name. |
| **Der Kopf löst die Typ-Identität selbst auf** | Symbol, Farbfamilie und Eyebrow aus `TYPE_META`; Aufrufer übergeben sie nicht. |

## Anhang — Was aus dem Vorgängersystem NICHT übernommen wird

Reservierung, Anteil, Ausleihe/Rückgabe, Unterdeckung, Material-Journal und Verwandtes gibt es
nicht; die Liste steht in `docs/history/2026-11-10-process-core-chronik.md`.
