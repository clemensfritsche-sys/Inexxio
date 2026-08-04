"""**Die Regel-Tabelle: Unterdeckung, Ausleihe und Pause** – EINE Quelle, ausführbar.

Dieser Bereich ist der, in dem die meisten echten Logikfehler entstanden sind (Notizen
#354/#366/#388/#397/#401/#404/#505/#522). Der Grund war nicht das Datenmodell, sondern
dass es **keine geschriebene Regel** gab: sie lebte als gewachsene Prosa in CLAUDE.md,
und Prosa kann sich widersprechen, ohne dass es jemand merkt. Jede Notiz führte zu einer
Punkt-Korrektur, und die nächste Notiz kippte sie wieder.

Darum steht die Regel **hier** – als Daten, nicht als Text – und `test_shortfall_rules.py`
spielt jede Zeile über die ECHTEN Dienste gegen echtes PostgreSQL durch. Damit ist ein
Widerspruch nicht mehr mergebar: er wird rot.

**Die drei Fragen, die eine Zeile beantwortet:**

    Fehlmenge   Fehlt dem Auftrag etwas? (``process.subject_shortfalls``)
    Pause       Ruht dadurch sein ganzer Prozess? (``process.is_paused``)
    Soll        Was geschieht mit seiner Menge? (unverändert · gekürzt · abgebrochen)

**Gefragt wird niemand mehr** (Testnotiz #556). Die frühere dritte Frage – «wird ein Mensch
um eine Entscheidung gebeten?» – hatte nie zwei sinnvolle Antworten: hält noch jemand die
Menge, ist «warten» die einzige (und der Auftrag ruht dabei ohnehin); hält sie niemand mehr,
ist sie endgültig weg und das Soll sinkt darauf. Beides weiss das System besser als der
Mensch, also entscheidet es (``recovery.auto_resolve``).

**Die zwei Auftragsarten, die dabei alles entscheiden:**

    regulär       hat ein SOLL (Artikel + Menge). Was ihm fehlt, schuldet er – er wird
                  gefragt, und er ruht, bis entschieden ist.
    festes Subjekt (Abweichung · Retoure · Bereitstellung) hat KEIN Soll, sondern eine
                  Arbeitsmenge: bestimmte, bereits vorhandene Stücke. Verliert er eines,
                  hat er weniger zu tun – nicht «zu wenig». Erst wenn ihm NICHTS mehr
                  bleibt, ist er gegenstandslos und wird gefragt (sonst würde er lautlos
                  abgebrochen, Notiz #397).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    """Eine Zeile der Tabelle: Lage → erwartete Antwort des Systems."""

    id: str
    """Kurzname – erscheint im Testbericht, wenn die Zeile bricht."""
    lage: str
    """Was ist passiert (in einem Satz, ohne Fachjargon)."""
    art: str
    """``regular`` (hat ein Soll) | ``fixed`` (Abweichung & Co., hat eine Arbeitsmenge)."""
    rest: str
    """Was dem Auftrag bleibt: ``alles`` | ``teil`` | ``nichts``."""
    fehlmenge: bool
    """Meldet ``subject_shortfalls`` etwas?"""
    pause: bool
    """Ruht sein ganzer Prozess (``is_paused``)?"""
    soll: str
    """Was mit seiner Menge geschieht: ``unverändert`` | ``gekürzt`` | ``abgebrochen``.

    Seit die Entscheidung automatisch fällt (Testnotiz #556), ist das die eigentliche
    Konsequenz – ohne sie sähe «kein Fehlmenge, keine Pause» genauso aus wie ein Auftrag,
    bei dem gar nichts passiert ist."""
    warum: str
    """Die Begründung – sie steht hier, damit eine Änderung sie mitändern MUSS."""


#: Die Tabelle. Reihenfolge = Lesereihenfolge, nicht Priorität.
RULES: tuple[Rule, ...] = (
    Rule(
        id="regular-vollstaendig",
        lage="Regulärer Auftrag über 4 Stück, alle 4 sind da.",
        art="regular", rest="alles", fehlmenge=False, pause=False, soll="unverändert",
        warum="Sein Soll ist gedeckt – es gibt nichts zu entscheiden.",
    ),
    Rule(
        id="regular-teil-verloren",
        lage="Regulärer Auftrag über 4 Stück; 1 Stück wurde verschrottet.",
        art="regular", rest="teil", fehlmenge=False, pause=False, soll="gekürzt",
        warum=(
            "Das Stück ist endgültig weg – niemand kommt mehr damit zurück. Dann gibt es "
            "nichts zu entscheiden: sein Soll sinkt auf 3, und er läuft mit weniger normal "
            "zu Ende (Testnotiz #556). Vorher stand hier eine Frage an den Menschen, die "
            "nur eine sinnvolle Antwort hatte – und bis er sie beantwortete, ruhte der "
            "ganze Auftrag (Notiz #354)."
        ),
    ),
    Rule(
        id="regular-alles-verliehen",
        lage="Regulärer Auftrag; eine laufende Abweichung hat ALLE seine Stücke übernommen.",
        art="regular", rest="nichts", fehlmenge=True, pause=True, soll="unverändert",
        warum=(
            "Die Ausleihe IST die Unterdeckung: solange die Abweichung sie hält, hat er "
            "sie nicht – und **wartet**, statt gekürzt zu werden. Sein Soll bleibt, weil "
            "die Menge zurückkommen kann; der Prozess ruht so lange (``waiting_for``)."
        ),
    ),
    Rule(
        id="fixed-vollstaendig",
        lage="Abweichung über 4 Stück, alle 4 hat sie noch.",
        art="fixed", rest="alles", fehlmenge=False, pause=False, soll="unverändert",
        warum="Sie arbeitet an dem, was sie hat.",
    ),
    Rule(
        id="fixed-teil-verloren",
        lage=(
            "Abweichung über 4 Stück; ihre EIGENE Abweichung hat 1 Stück verschrottet."
        ),
        art="fixed", rest="teil", fehlmenge=False, pause=False, soll="unverändert",
        warum=(
            "Sie schuldet nichts – ihre Menge ist eine Arbeitsmenge, kein Soll. Sie hat "
            "jetzt weniger zu tun, und die Verschrottung WAR die Klärung. Sie erneut zu "
            "fragen wäre eine Schleife ohne Erkenntnisgewinn und hielte ihren Prozess an "
            "(Notizen #522/#523). Gefragt wird der reguläre Auftrag weiter oben, der die "
            "Menge wirklich schuldet."
        ),
    ),
    Rule(
        id="fixed-alles-verloren",
        lage="Abweichung über 1 Stück; genau dieses Stück wurde ihr weggenommen.",
        art="fixed", rest="nichts", fehlmenge=True, pause=True, soll="unverändert",
        warum=(
            "Jetzt ist sie gegenstandslos – aber die Abweichung, die es ihr genommen hat, "
            "läuft noch: das Stück kann zurückkommen. Sie wartet, wie jeder andere auch. "
            "Endet der Abzweig, ohne es zurückzugeben, IST «Menge reduzieren» ihr Abbruch "
            "(Notiz #397) – und der fällt dann automatisch (#556)."
        ),
    ),
    Rule(
        id="fixed-selbst-ausgesteuert",
        lage="Abweichung über 1 Stück; sie hat genau dieses Stück SELBST verschrottet.",
        art="fixed", rest="erledigt", fehlmenge=False, pause=False, soll="unverändert",
        warum=(
            "Das WAR ihr Auftrag. Sie hält danach nichts mehr – aber nicht, weil ihr etwas "
            "genommen wurde, sondern weil sie es ausgesteuert hat; der Unterschied ist "
            "nicht die Menge, sondern **warum** sie weg ist (Testnotiz #555). Ohne diese "
            "Unterscheidung meldete sie eine Fehlmenge über ihre volle Menge, wurde nie "
            "fertig, und der Eltern-Auftrag wartete für immer auf sie: genau der gemeldete "
            "Steckenbleiber. Das Journal weiss, wer ausgesteuert hat."
        ),
    ),
)


def rule(rule_id: str) -> Rule:
    """Eine Zeile beim Namen – damit ein Test sie nennen kann, statt sie zu kopieren."""
    for r in RULES:
        if r.id == rule_id:
            return r
    raise KeyError(rule_id)
