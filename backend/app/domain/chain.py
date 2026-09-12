"""**Die Statuskette — eine Aussage über Modul-Definitionen, ohne Datenbank.**

Sie steht hier und nicht im Prozess-Dienst, weil sie an **beiden** Definitionsorten gilt
(PROCESS_CORE.md §8): an der Artikel-Vorlage und am Auftrags-Prozess. Lag sie beim
Dienst, prüfte nur der Auftrag – und ein Artikel-Erzeugungsprozess, dessen Kette nicht
schliesst, liesse sich anlegen und scheiterte erst bei der ersten Freigabe. Das ist die
falsche Zeit: der Artikel entsteht mit seiner Freigabe und ist danach eingefroren.
"""

from typing import Any

from fastapi import HTTPException

from . import modules, statuses as st


def assert_closes(steps: list[dict[str, Any]]) -> None:
    """Die Kette muss schliessen (§4.3) — geprüft beim **Anlegen**, nicht zur Laufzeit.

    Geprüft wird gegen den **Vorher**-Status des Ende-Objekts (``END_BEFORE``), nicht
    gegen den Endzustand: das Ende ist ein Übergang wie jedes Modul, es *erwartet*
    «Im Prozess» und *setzt* ``order.end_status``. Beides zu verwechseln hiesse, vom
    letzten Modul zu verlangen, dass es den Endzustand selbst schon setzt.

    **Ein terminales Modul beendet die Kette.** Es ist kein Durchgang, sondern ein
    Ausgang: was dort ankommt, verlässt den Auftrag. Das Ende-Objekt dahinter zu
    verlangen wäre falsch – dort kommt nie ein Stück an –, und ein Modul dahinter wäre
    eine tote Definition, die aussieht wie ein Prozess.

    Das ist der Unterschied zwischen einer Regel und einer Hoffnung: ein Prozess, der
    freigegeben werden konnte, kann nicht mitten drin an einem Statuskonflikt hängen
    bleiben.
    """
    current = st.START_AFTER
    for i, step in enumerate(steps, start=1):
        before = step["status_before"]
        if before != current:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Die Statuskette bricht bei Schritt {i} "
                    f"«{modules.label(step['module_type'])}»: davor "
                    f"steht «{st.label(current)}», das Modul erwartet "
                    f"«{st.label(before)}»."
                ),
            )
        if modules.get(step["module_type"]).terminal:
            if i < len(steps):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Hinter «{modules.label(step['module_type'])}» kann kein Modul "
                        f"mehr stehen: was hier ankommt, verlässt den Auftrag – Schritt "
                        f"{i + 1} bekäme nie eine Einzelinstanz."
                    ),
                )
            return
        current = step["status_after"]
    if current != st.END_BEFORE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Die Statuskette bricht am Ende: der letzte Schritt endet auf "
                f"«{st.label(current)}», das Ende-Objekt erwartet "
                f"«{st.label(st.END_BEFORE)}»."
            ),
        )
