"""**Die Vergabe — der Zyklus, EINMAL** (PROCESS_CORE §15.5, SYSTEM_LOGIC §7.3, ADR 009).

Eine Vergabe ist der Vorgang «ein Dritter erbringt eine Leistung für uns»: heute ein
**Transport**, morgen eine **Beschaffung**. Beides ist derselbe Ablauf — anfragen,
Angebote bekommen, vergeben, abnehmen —, also steht er hier **einmal** und nicht je Modul
neu.

**Der KANAL ist die einzige Variable.** Er ändert, *woher* die Angebote kommen — nie,
*welche* Zustände es gibt:

* ``plattform`` — aus einer API, in Sekunden; das günstigste ist vorgewählt.
* ``portal``    — von einem Menschen, der sie im Lieferantenportal eintippt.
* ``selbst``    — gar nicht; selbst bestellt, nur dokumentiert.

**Rate-Shopping IST eine Ausschreibung**, sie dauert nur 2 Sekunden statt 2 Tage. Was
beim Paketversand wie ein technischer Sonderweg aussieht, ist derselbe Vorgang wie eine
Frachtanfrage an zwei Spediteure. Darum stehen die Zustände hier als **Registry** und
nicht als ``if/else`` je Kanal — ein neuer Kanal ist ein Adapter, kein neuer Zyklus.

**Die Matrix ist monoton — sie geht nie rückwärts.** Daraus folgt der einzige nicht
offensichtliche Zustand: eine vergebene, aber nie erbrachte Leistung wird
``gescheitert`` (terminal, **Grund Pflicht**), und die Sache bekommt eine **ganz normale
zweite** Vergabe. Ein «Zurücknehmen» wäre der bequemere Weg und der falsche: eine
Korrektur ist im ganzen Haus ein **neuer Eintrag**, nie eine geänderte Zeile (G5.1) —
und mit dem Rückwärtsschritt stünden am Ende zwei Zeilen gleichzeitig auf ``vergeben``,
ohne dass irgendetwas sagte, welche gilt.
"""

from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Die Zustände
# ---------------------------------------------------------------------------

#: Der Bedarf ist draussen, noch kein Angebot.
ANGEFRAGT = "angefragt"
#: Mindestens ein Angebot liegt vor.
ANGEBOTEN = "angeboten"
#: Ein Dritter ist **gebunden**. Ab hier rührt das System nichts mehr an — es meldet.
VERGEBEN = "vergeben"
#: Die Leistung ist erbracht (angekommen).
ERBRACHT = "erbracht"
#: Der Vorgang endet ohne Vergabe.
ABGELEHNT = "abgelehnt"
#: Vergeben, aber **nicht** erbracht. Grund ist Pflicht.
GESCHEITERT = "gescheitert"


@dataclass(frozen=True)
class State:
    """Ein Zustand der Vergabe — mit allem, was über ihn zu wissen ist.

    ``terminal`` heisst «für diese Vergabe gibt es keinen Weg mehr» — nicht «für die
    Sache»: eine gescheiterte Vergabe ist zu Ende, die Fuhre darunter bekommt eine neue.
    """

    key: str
    label: str
    #: Ampelton, wie im Statuskatalog: grün = gut · gelb = offen · rot = Problem.
    tone: str
    terminal: bool = False
    #: Ist ab hier ein **Zweiter gebunden**? Dann rührt das System nichts an, es meldet.
    binding: bool = False
    #: Verlangt der Übergang **hierher** einen Grund? Ohne ihn steht später da, dass
    #: etwas gescheitert ist, aber nicht warum.
    needs_reason: bool = False


CATALOG: tuple[State, ...] = (
    State(ANGEFRAGT, "Angefragt", tone="pending"),
    State(ANGEBOTEN, "Angeboten", tone="pending"),
    State(VERGEBEN, "Vergeben", tone="pending", binding=True),
    State(ERBRACHT, "Erbracht", tone="done", terminal=True, binding=True),
    State(ABGELEHNT, "Abgelehnt", tone="danger", terminal=True),
    State(GESCHEITERT, "Gescheitert", tone="danger", terminal=True, needs_reason=True),
)

STATES: dict[str, State] = {s.key: s for s in CATALOG}
KEYS: tuple[str, ...] = tuple(STATES)

#: **Die vollständige Übergangsmatrix.** Jeder nicht aufgeführte Übergang ist verboten;
#: es gibt keinen Parameter und kein Force-Flag, der daran vorbeiführt.
#:
#: Sie ist **monoton**: kein Ziel steht in der Liste eines Zustands, der später kommt.
#: ``_assert_monotonic`` prüft das beim Start – eine Rückwärtskante wäre genau der
#: Fehler, den ``gescheitert`` vermeidet, und sie liesse sich sonst versehentlich
#: eintragen.
#:
#: **``angefragt`` → ``vergeben`` ist keine Ausnahme, sondern der Kanal ``selbst``.** Wo
#: es keine Angebote gibt, kann es den Zustand «es liegen welche vor» nicht geben; ohne
#: diese eine Kante wäre ``selbst`` eine Sackgasse (angefragt, für immer). Ein Kanal
#: **mit** Angeboten kann sie trotzdem nicht benutzen – dort ist das gewählte Angebot
#: Pflicht, und sobald eines eingetroffen ist, steht die Vergabe auf ``angeboten``. Die
#: Matrix sagt, welche Zustandsfolgen es gibt; der Kanal sagt, woher die Angebote kommen.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    ANGEFRAGT: (ANGEBOTEN, VERGEBEN, ABGELEHNT),
    ANGEBOTEN: (VERGEBEN, ABGELEHNT),
    VERGEBEN: (ERBRACHT, GESCHEITERT),
    ERBRACHT: (),
    ABGELEHNT: (),
    GESCHEITERT: (),
}


# ---------------------------------------------------------------------------
# Die Kanäle — die einzige Variable
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Channel:
    """Woher die Angebote kommen. **Nicht**, welche Zustände es gibt."""

    key: str
    label: str
    hint: str
    #: Bringt dieser Kanal von sich aus Angebote? ``selbst`` nicht – dort ist die
    #: Vergabe eine Dokumentation dessen, was jemand ohnehin schon bestellt hat.
    offers: bool = True


PLATTFORM = "plattform"
PORTAL = "portal"
SELBST = "selbst"

CHANNELS: dict[str, Channel] = {c.key: c for c in (
    Channel(PLATTFORM, "Plattform",
            "Angebote kommen aus einer Schnittstelle – in Sekunden, günstigstes vorgewählt"),
    Channel(PORTAL, "Lieferantenportal",
            "Der Dritte trägt sein Angebot selbst ein"),
    Channel(SELBST, "Selbst bestellt",
            "Kein Angebotsvergleich – der Vorgang wird nur dokumentiert", offers=False),
)}


# ---------------------------------------------------------------------------
# Fragen an die Registry
# ---------------------------------------------------------------------------

def state(key: str) -> State:
    """Zustand zu einem Schlüssel. Unbekannt = harter Fehler, kein Rückfall."""
    found = STATES.get(key)
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=(f"«{key}» ist kein Vergabe-Zustand. Erlaubt: "
                    + ", ".join(f"{s.label} ({s.key})" for s in CATALOG) + "."),
        )
    return found


def channel(key: str) -> Channel:
    found = CHANNELS.get(key)
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=(f"«{key}» ist kein Vergabe-Kanal. Erlaubt: "
                    + ", ".join(f"{c.label} ({c.key})" for c in CHANNELS.values()) + "."),
        )
    return found


def assert_transition(current: str, target: str, *, reason: str = "") -> None:
    """Darf dieser Übergang stattfinden? Wenn nicht: ein Satz, der sagt warum.

    **Die eine Prüfstelle.** Sie steht hier und nicht im Dienst, damit ein zweiter
    Aufrufer sie nicht umgehen kann – dieselbe Form wie der Endzustand am Stück (§5.3).
    """
    state(current), state(target)          # beide müssen es geben
    allowed = TRANSITIONS.get(current, ())
    if target not in allowed:
        ways = (", ".join(STATES[a].label for a in allowed)
                if allowed else "keiner – dieser Zustand ist endgültig")
        raise HTTPException(
            status_code=409,
            detail=(f"Eine Vergabe kann von «{STATES[current].label}» nicht nach "
                    f"«{STATES[target].label}» wechseln. Möglich wäre: {ways}."),
        )
    if STATES[target].needs_reason and not reason.strip():
        raise HTTPException(
            status_code=400,
            detail=(f"«{STATES[target].label}» braucht einen Grund – ohne ihn steht "
                    f"später da, dass es nicht geklappt hat, aber nicht warum."),
        )


def is_open(key: str) -> bool:
    """Läuft diese Vergabe noch? Abgeleitet aus ``terminal`` – keine zweite Liste."""
    return not state(key).terminal


def _assert_monotonic() -> None:
    """**Die Matrix geht nie rückwärts.** Geprüft beim Import, nicht beim Betrieb.

    Ein Rückwärts-Übergang wäre genau der Weg, den ``gescheitert`` ersetzt – und er
    liesse sich in einer Tabelle versehentlich eintragen, ohne dass ein Test ihn führe.
    """
    order = {s.key: i for i, s in enumerate(CATALOG)}
    for src, targets in TRANSITIONS.items():
        for dst in targets:
            if order[dst] <= order[src]:
                raise RuntimeError(
                    f"Vergabe-Matrix geht rückwärts: {src} → {dst}. Eine Korrektur ist "
                    f"ein NEUER Eintrag, nie eine geänderte Zeile (SYSTEM_LOGIC G5.1)."
                )


_assert_monotonic()
