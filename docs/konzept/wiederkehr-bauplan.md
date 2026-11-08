# Wiederkehrende Aufträge – Bauplan

> **Kopfstatus:** Entwurf (08.11.2026), nichts gebaut · gehört zur Projektakte
> `docs/konzept/wiederkehr.md` (Grundsätze §3, Speicherung §4b, Entscheide §6) · Bild:
> https://claude.ai/artifact/Lk5AKy8G1CTWi68ZxA57uj
> Gebaut wird auf einem Feature-Branch (`claude/wiederkehr`); nach `develop` erst nach Freigabe.

## Leitplanken (aus der Akte, verbindlich)

- **Eine Wiederholung ist ein ganz gewöhnlicher Auftrag**, nur ausgelöst vom Takt. Sie entsteht
  über **denselben Weg wie «Freigeben»** (`orders.validate_draft` → `orders.create_order`). Es
  gibt keinen zweiten Anlageweg und keine Sonderregel im Prozess.
- **Nichts Neues, wo es Bestehendes gibt:** der Takt (`services/tick.TASKS`), das Log
  (Ereignisse, eindeutiger Index wie `ix_log_decided`), die Verben der Zahlung (`VERBS`), «zu tun»
  (`services/todo`), der Liniengenerator (`polyPath`).
- **Zwei Formen einer Regel, nie zwei Regeln:** was eine Wiederholung verhindert, sagt **eine**
  Funktion als Satz (`loop.problem`) und prüft **dieselbe** beim Anlegen.
- **Keine neue Infrastruktur, keine laufenden Kosten.**

## Schritte

Jeder Schritt ist für sich lauffähig, getestet und einzeln deploybar. Die Reihenfolge folgt den
Abhängigkeiten.

### 0 · Soll notieren (nur Doku)
- `SYSTEM_LOGIC.md`: die neuen Sätze als Soll, **bevor** gebaut wird (Verkauft regulär; je
  Schlaufe und Periode höchstens ein Auftrag; keine Periode geht verloren; endgültig weg ⇒ geht
  nicht mehr; nie ein Teil-Auftrag; Abweichung trägt keine Schlaufe).
- `tests/matrix.py`: die Zeilen dazu, mit Soll.
- `PROCESS_CORE.md` §13 Punkt 6 wird ein eigener Abschnitt «Wiederkehr» (Verweis auf die Akte);
  §12.2 Regelstart; §13.6 die eine Stelle der Zahlung.

### 1 · `Verkauft` ist ein regulärer Start (V1)
- `domain/statuses`: ein **zweiter Name** `REGULAR_STARTS = {FREIGEGEBEN, VERKAUFT}` neben
  `START_BEFORE` (bleibt `Freigegeben` – Bestand, FIFO, Verbrauch).
- `order_state.deviation_flags` vergleicht gegen `REGULAR_STARTS`.
- Hinweis im Entwurf ohne «(Abweichung)» (`definition-lines.tsx`).
- Tests: Service am verkauften Stück ist regulär · Retoure ist regulär und durch «geht an uns»
  belegt · **Wächter:** FIFO und Verbrauch nehmen nie ein verkauftes Stück (gegen die Bug-Form
  «`START_BEFORE` auf die Menge umgestellt» gegengeprüft).
- Doku: SYSTEM_LOGIC T7e/U6c, Kommentare in `statuses.py`, CLAUDE.md.

### 2 · Preise als Vorgabe im Zahlungsmodul (allgemein)
- `VOUCHER_PRESETS` um **Positionen** erweitert (Artikel/Text, Menge, Preis, Steuersatz); leer =
  wie heute (wird in der Offerte gesetzt). Eingefroren mit dem Modul wie jede Vorgabe.
- Der Beleg übernimmt vorgegebene Positionen beim Entstehen; sie sind `fixed` (punktiert, Hover).
- Nützt jedem Auftrag. Tests: mit und ohne Vorgabe; eine vorgegebene Position lässt sich am Beleg
  nicht ändern.

### 3 · Die Schlaufe: Kalender und Speicherung
- `domain/loop.py` (rein, ohne Datenbank): Takte (wöchentlich · monatlich · vierteljährlich ·
  halbjährlich · jährlich), **Perioden** ab «erste Ausführung», Ende (unbefristet · Datum ·
  Anzahl), Monatsende → letzter Tag, Tage in Europe/Zurich. Tests: 31. im Februar, Schaltjahr,
  Jahreswechsel, Ende nach Anzahl.
- Log-Ereignisse `loop.set` · `loop.created` · `loop.ended` (Akte §4b) mit Schema (Pydantic).
  **Migration:** eindeutiger Index auf (Vorlage, Periode) für `loop.created`, gebaut wie
  `ix_log_decided`; dazu ein Index zum Lesen offener Schlaufen.
- `services/loop.py`: `set` · `end` · `due` (fällige Perioden, abgeleitet) · `problem` (der eine
  Satz, warum es gerade nicht geht, oder «geht nicht mehr») · `create_due`.
- Regeln beim Setzen (Akte O14–O16): nur an einem regulären, freigegebenen Auftrag, der selbst
  keine Wiederholung ist; «Ab» heute oder später; je Lager-Zeile eine Wahl ohne Vorbelegung.
- `history.HIDDEN_EVENTS`? Nein: einschalten, jede Wiederholung und beenden stehen im Verlauf.

### 4 · Der Takt legt an
- `tick.TASKS` + `Task("loop", …)`. Je fällige Periode, älteste zuerst, in eigener Transaktion:
  Entwurf aus der eingefrorenen Definition bauen (Zeilen nach der Wahl: gleiche Einzelinstanzen
  bzw. FIFO-Vorschlag des Servers bzw. «Neu»), `validate_draft` fragen, bei leerer Antwort
  `create_order` + `loop.created` in **derselben** Transaktion. Handelnder «System» im Namen der
  Person aus `loop.set`.
- Antwort nicht leer → nichts schreiben (Leerlauf steht nicht im Log); `loop.problem` liefert den
  Satz für «zu tun». Zeitgrenze wie die anderen Aufgaben; was nicht fertig wird, nimmt der
  nächste Lauf.
- Zusätzlich zur Freigabe-Prüfung: **keine Abweichung** (alle Stücke in `REGULAR_STARTS`) und
  **keine endgültig weggefallene Einzelinstanz** (→ «geht nicht mehr»).
- `services/todo`: wartende und unmögliche Schlaufen zählen am Symbol des Vorlage-Auftrags (rot bei
  «geht nicht mehr»).
- Tests: nie doppelt (zwei Läufe gleichzeitig) · wartet und entsteht, sobald frei · mehrere
  Perioden nacheinander · verschrottet ⇒ geht nicht mehr · beendet ⇒ nichts mehr · Abweichung in
  einer Wiederholung stört die nächste nicht.

### 5 · Die Zahlung in der Wiederholung
- Die Offerte (Papier) nennt die Schlaufe, wenn es eine gibt; der Satz gehört zur **angenommenen
  Fassung** (`offered_hash`).
- Nach dem Anlegen einer Wiederholung: Sind alle Positionen vorgegeben **und** hat die Partei
  eine Fassung **mit** Schlaufe angenommen, führt **eine** Funktion `ask` und `agree` aus –
  dieselben Verben, Handelnder «System», Vermerk «gestützt auf die Zusage vom … zu Auftrag …»
  (Ereignis `voucher.action` wie immer). Sonst nichts: der Beleg wartet bei der Offerte.
- Hinaus geht nichts von selbst (AB und Rechnung über «Prüfen und freigeben»).
- Tests: Abo läuft bis «Rechnung stellen» · ohne Preis hält es bei der Offerte · Schlaufe erst nach
  der Annahme gesetzt ⇒ keine automatische Zusage.

### 6 · Oberfläche
- Unter dem Ziel der Schalter «einmalig ↔ Jährlich ab …» und die Karte (Wiederholen · Ab · Bis ·
  Nimmt · Beenden), wie im Bild. Zustand als Punkt + Satz. Beenden fragt einmal nach.
- Die Linie **links**, aus `polyPath`, Haarlinie bis zur ersten Wiederholung (prozessbild §8.1a);
  eine Wiederholung zeigt die Schlaufe ihrer Vorlage.
- `prozessbild.md` nachgezogen; Spiegel der Takte im Frontend getestet
  (`test_frontend_mirrors.py`).

### 7 · Abschluss
- CLAUDE.md (Ist-Stand), Akte-Kopfstatus «gebaut», Rundenbericht in `docs/history/`.

## Kosten
Keine neuen Dienste: der Takt läuft schon, die Datenbank auch. Je Lauf ein paar Abfragen.
