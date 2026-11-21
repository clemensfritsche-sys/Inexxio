"""►►► **Die Kompetenzen – EINE Liste** (Projektakte `docs/konzept/aufgaben.md` §3). ◄◄◄

Was eine Person kann, damit ihr eine Aufgabe zugeteilt wird. Fünf sind die Tätigkeiten, die das
ERP tun lässt (je Modul eine Vorgabe, ``Module.competence``, dazu Kommunizieren für alles an einer
fremden Person); drei sind besonders und werden nur am Prozessschritt gewählt.

Welche Kompetenz eine Aufgabe braucht, steht hier **nicht** je Art: sie folgt dem Ort, an dem die
Aufgabe steht (``services/tasks.competence_of``). Gespeichert wird nur, wer welche hat
(``user_profiles.competences``). **Eine Kompetenz ohne Person gibt es nicht** – die letzte Person
kann sie nicht verlieren (``drop_problem`` ↔ ``assert_drop``).
"""

from __future__ import annotations

from typing import Iterable, Optional

from .errors import Invalid

KOMMUNIZIEREN = "Kommunizieren"
VERRECHNEN = "Verrechnen"
BEWEGEN = "Bewegen"
BAUEN = "Bauen"
PRUEFEN = "Prüfen"

#: Die Liste – in der Reihenfolge, in der die Oberfläche sie zeigt.
COMPETENCES: tuple[str, ...] = (
    KOMMUNIZIEREN, VERRECHNEN, BEWEGEN, BAUEN, PRUEFEN,
    "Schweissen", "Elektrik", "Kranprüfung",
)


def clean(raw: object) -> Optional[str]:
    """Eine Kompetenz aus einer Eingabe – ein Wort der Liste oder nichts."""
    if raw is None or raw == "":
        return None
    if raw not in COMPETENCES:
        raise Invalid(f"«{raw}» ist keine Kompetenz. Möglich: {', '.join(COMPETENCES)}.",
                      field="competence")
    return str(raw)


def clean_list(raw: Iterable[object] | None) -> list[str]:
    """Die Kompetenzen einer Person – jedes Wort aus der Liste, einmal, in ihrer Reihenfolge."""
    given = {clean(r) for r in (raw or [])} - {None}
    return [c for c in COMPETENCES if c in given]


def drop_problem(competence: str, holders_after: int) -> Optional[str]:
    """►► **Warum diese Kompetenz nicht entzogen werden kann** – oder ``None``. ◄◄

    ``holders_after``: wie viele Personen sie danach noch hätten."""
    if holders_after < 1:
        return (f"«{competence}» hat sonst niemand. Zuerst einer anderen Person geben – "
                f"eine Kompetenz ohne Person gibt es nicht.")
    return None


def assert_drop(competence: str, holders_after: int) -> None:
    """Das Tor zu ``drop_problem``."""
    problem = drop_problem(competence, holders_after)
    if problem:
        raise Invalid(problem, field="competences")
