"""**«Meinst du diesen hier?» — die eine Suchbedingung.**

Jedes Referenzfeld im Haus stellt dieselbe Frage: der Mensch tippt, und es kann eine
**Objektnummer** sein («00787») oder ein **Name** («Regal», «Schraube»). Er weiss beim
Tippen nicht, wonach er sucht – er sucht einfach.

Genau darum steht die Bedingung hier und nicht je Endpunkt: sie stand dreimal
ausgeschrieben (Halter, Instanzen) und an der vierten Stelle – der Artikel-Suche – trug
sie nur den Namen. Wer «100000743» tippte, fand nichts, obwohl die Nummer im Dropdown
darunter stand (Testnotiz #738). Ein Weg, der an drei Stellen richtig ist, ist keine
Regel; er ist ein Zufall.

**Was gesucht werden darf, entscheidet weiterhin der Aufrufer.** Dieses Modul liefert die
Bedingung, nicht die Erlaubnis: ``places.search`` bietet bewusst keine Artikel an, weil
``assert_placeable`` sie danach abwiese. Ein generischer «suche irgendwas»-Endpunkt
müsste diese fachliche Grenze je Aufrufstelle neu erfinden.
"""

from typing import Any

from sqlalchemy import String, func, or_


def matches(query: str, object_id_col: Any, *name_cols: Any):
    """SQL-Bedingung «Objektnummer-Teilstring **oder** Name enthält ``query``».

    Ohne Eingabe eine wahre Bedingung – dann filtert der Aufrufer nicht, statt eine
    leere Liste zu liefern; «nichts getippt» heisst «alles», nicht «nichts».

    Die Nummer wird als **Text** verglichen: gesucht wird nach einem *Teil* («00787»),
    nicht nach einem Wert. Ein Gleichheitsvergleich träfe nur die volle neunstellige
    Zahl – und die tippt niemand ab.
    """
    q = (query or "").strip()
    if not q:
        return True
    like = f"%{q.lower()}%"
    tests = [func.cast(object_id_col, String).like(f"%{q}%")]
    tests += [func.lower(func.coalesce(c, "")).like(like) for c in name_cols]
    return or_(*tests)
