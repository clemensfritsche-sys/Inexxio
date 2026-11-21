"""**Die Kettenregel — eine Aussage über Modul-Definitionen, ohne Datenbank.**

Sie steht hier und nicht im Prozess-Dienst, weil sie an **beiden** Definitionsorten gilt
(PROCESS_CORE.md §8): an der Artikel-Vorlage und am Auftrags-Prozess. Läge sie beim
Dienst, prüfte nur der Auftrag – und ein Artikel-Erzeugungsprozess, der nicht aufgeht,
liesse sich anlegen und scheiterte erst bei der ersten Freigabe.
"""

from typing import Any

from . import modules
from .errors import Invalid


def assert_closes(steps: list[dict[str, Any]]) -> None:
    """**Hinter einem Ausgang steht nichts** (§4.3) — geprüft beim **Anlegen**.

    Wer ein Modul passiert und weiterläuft, bleibt «Im Prozess» (``Module.exit_status_for``);
    eine Kette aus solchen Modulen schliesst immer. Offen ist nur eine Frage: ein
    **terminales** Modul ist kein Durchgang, sondern ein Ausgang – was dort ankommt, verlässt
    den Auftrag. Ein Modul dahinter bekäme nie ein Stück; es wäre eine tote Definition, die
    aussieht wie ein Prozess.
    """
    for i, step in enumerate(steps, start=1):
        module = modules.get(step["module_type"])
        if module.terminal and i < len(steps):
            raise Invalid(f"Hinter «{module.label}» kann kein Modul mehr stehen: was hier "
                          f"ankommt, verlässt den Auftrag – Schritt {i + 1} bekäme nie eine "
                          f"Einzelinstanz.")
