# ADR 008 – Unterdeckung, Ausleihe und Pause: die Regel steht im Code

> ## Kopfstatus (August 2026): **historisch – die Regel-Tabelle existiert nicht mehr**
> `backend/tests/rules/table.py` und die Mechanik aus Ausleihe/Rückgabe/Pause sind mit dem
> Basis-Neuaufbau entfallen; die heutige Prozesslogik steht in `PROCESS_CORE.md`.
> **Gültig bleibt die Arbeitsweise**, die dieses ADR eingeführt hat und die das Projekt
> weiterführt: eine Regel wird **geschrieben, bevor sie geprüft wird** – sonst prüft man
> den Code gegen sich selbst, und ein systematisch falscher Code besteht seine eigenen
> Tests immer.


Status: **angenommen** (August 2026) · Tabelle: `backend/tests/rules/table.py`

## Warum es diesen Eintrag gibt

Dieser Bereich hat die meisten echten Logikfehler der letzten Wochen erzeugt (Notizen
#354 · #366 · #388 · #397 · #401 · #404 · #505 · #522/#523). Die Ursache war **nicht** das
Datenmodell – das Material-Journal (ADR 007) meldet in allen geprüften Fällen `drift: []`.
Die Ursache war, dass es **keine geschriebene Regel** gab: sie lebte als gewachsene Prosa
in `CLAUDE.md`, verteilt über zwanzig Absätze aus zwanzig Runden.

Prosa kann sich widersprechen, ohne dass es jemand merkt. Jede Testnotiz führte zu einer
Punkt-Korrektur an der Stelle, die gerade auffiel; zwei Runden später kippte die nächste
Notiz sie wieder. Zweimal wurde dieselbe Frage – *hat ein Auftrag mit festem Subjekt ein
Soll?* – in entgegengesetzte Richtungen entschieden (#388 → #397 → #522).

## Die Entscheidung

**Die Regel ist Code, nicht Text.** Sie steht als Tabelle in
`backend/tests/rules/table.py` und wird von `test_shortfall_rules.py` **ausgeführt**: jede
Zeile baut ihre Lage über die echten Dienste auf (Freigabe, Router-Pfad, Verschrottung) und
prüft, was die Oberfläche daraus liest. Damit ist ein Widerspruch nicht mehr mergebar – er
wird rot, und die Fehlermeldung nennt die **Begründung** der Zeile.

Dazu das **Szenario-Netz** (`test_scenario_chain.py`): die Kette, die im Praxistest wirklich
gefahren wird (Auftrag → Abweichung → Abweichung → Verschrottung → Klärung), in sechs
Stationen. Sie lief bisher nur von Hand – deshalb fielen Regressionen erst Tage später am
Bildschirm auf.

Beides läuft in der CI bei **jedem Push** gegen echtes PostgreSQL (Schritt «Regel-Tabelle +
Szenario-Netz»). Ohne Datenbank überspringen sie **mit Grund** – geprüft wird gegen
JSONB-Ansprüche und Zeilensperren, ein Ersatz-Backend würde eine Wahrheit prüfen, die es
nicht gibt.

## Die Regel in einem Satz

> Ein **regulärer** Auftrag hat ein **Soll** – was ihm fehlt, schuldet er: er wird gefragt,
> und bis entschieden ist, ruht er ganz. Ein Auftrag mit **festem Subjekt** (Abweichung ·
> Retoure · Bereitstellung) hat kein Soll, sondern eine **Arbeitsmenge**: verliert er ein
> Stück, hat er weniger zu tun – erst wenn ihm **nichts** bleibt, ist er gegenstandslos und
> wird gefragt.

Die sechs Zeilen der Tabelle sind die vollständige Ausformulierung davon; sie stehen dort
mitsamt Begründung und sind hier bewusst **nicht** wiederholt. Zwei Fassungen desselben
Satzes wären genau der Fehler, der zu diesem ADR geführt hat.

## Arbeitsweise (die eigentliche Lehre)

1. **Regel-Notiz ≠ Optik-Notiz.** Eine Notiz, die eine Regel ändert, wird nicht sofort
   umgesetzt: erst wird gesagt, welche Zeile der Tabelle sie kippt und was daraus folgt –
   danach entscheidet der Nutzer. Optik wird direkt umgesetzt.
2. **Regel ändern heisst Tabelle ändern.** Wer das Verhalten ändert, ändert zwangsläufig
   die Zeile *und* ihren Begründungssatz – sonst bricht der Test.
3. **Neue Fälle kommen als Zeile dazu**, nicht als Sonderfall im Code. Eine Zeile mehr ist
   billig; eine ungeschriebene Ausnahme kostet drei Runden.
