# 2026-11-10 · Prozess, Aufträge, Module: Gesamtschau

## Anlass
Der Inhaber wollte Prozess, Prozesslogik und Auftragslogik ganzheitlich geprüft haben, wie zuvor die
Kommunikation: wo geht es einfacher, schlanker? Umgesetzt wurden A, B und C.

## A – klein
- **Prozessbild**: `flow._exit_points` und `_left_with` lasen dieselbe Abfrage («letzter Eintrag je
  Stück») zweimal – jetzt `flow._last_events`, einmal.
- **Nachbar-Aufträge mit einer Kennung**: Graph und Journey nennen sie gleich (`flow.Neighbour`,
  Objektnummer); der Übersetzer `order_view.order_ids` ist weg.
- Verworfen: drei angeblich tote Teile der Oberfläche (`samplePayload`, `isTerminal`,
  `validateForStep`) – sie werden intern und von den Tests gelesen.

## B – mittel
- **Eine Stelle, die fragt, was von selbst weiterzieht**: `process.carry_on` (Stichprobe durch →
  `_run_through`; Zahlungsmodul darf → `advance_payments`). Vorher fragten vier Orte, nicht überall
  beide (die Abzweigung nur die Stichprobe). Eine echte Folge davon liess sich nicht nachweisen –
  ein gegriffenes Stück macht den Beleg ohnehin unpassend (`units_problem`). Wächter
  `test_carry_on`, gegen die Bug-Form gegengeprüft.
- **PROCESS_CORE.md auf den Ist-Stand gekürzt** (2062 → 928 Zeilen, alle Abschnittsnummern
  erhalten); der Wortlaut davor: `2026-11-10-process-core-chronik.md`. Veraltete Code-Verweise darin
  korrigiert; zwei Verweise auf §13.6/§13.7 zeigen jetzt auf §6.6.

## C – gross
- **Ein Schritt speichert keinen Übergang mehr**. Jedes der fünf Module liess weiterlaufende Stücke
  «Im Prozess»; `status_before/after` an `process_steps` und `article_process_steps` war eine
  gespeicherte Kopie davon, die Kettenprüfung prüfte etwas, das nie falsch sein konnte. Jetzt sagt
  `Module.exit_status_for`, was beim Hinausgehen geschieht (Aussondern, Komponenten des Verbrauchs),
  und die Kettenregel ist nur noch «hinter einem Ausgang steht nichts». Migration 186 entfernt die
  Spalten in einem Zug (Entscheid des Inhabers: nicht rückwärtskompatibel, darum ohne
  Zwei-Deploy-Regel). Die Ereignisse im Log behalten Vorher/Nachher.

## Nicht geprüft
Das Zahlungsmodul (rund 5'200 Zeilen) nur überflogen – eigener Durchgang offen.

## Geprüft
Backend 811 grün, Frontend Typen · Lint · 161 Tests grün; generierte Dateien nachgezogen.
