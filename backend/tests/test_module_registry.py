"""**Was ein Modultyp ist, sagt die Registry** (``domain/modules``) – und der Schritt trägt es.

Beschriftung, Farbfamilie, «Ausgang?», das Verb auf dem Knopf, der Übergang und der
Ortsbedarf hängen am Typ, nie an einer Spalte und nie an der Oberfläche. Ein gespeicherter
Schritt bringt sie in jeder Antwort mit (``ModuleFacts``): die Oberfläche rät nichts – auch
nicht im freigegebenen Auftrag, wo kein Modul-Katalog geladen ist (die Aussonderung sah dort
einmal aus wie eine Datenerfassung).
"""

from app.domain import modules, statuses as st
from app.schemas.order import ProcessStepResponse


def _step(module_type: str, config: dict) -> dict:
    m = modules.get(module_type)
    return ProcessStepResponse(id=7, position=1, module_type=module_type, config=config,
                               status_before=m.status_before, status_after=m.status_after
                               ).model_dump(mode="json")


def test_a_step_brings_what_its_type_says():
    scrap = _step(modules.AUSSONDERN, {"mode": "scrap", "reason": "Ausschuss"})
    block = _step(modules.AUSSONDERN, {"mode": "block", "reason": "Prüfen"})
    assert (scrap["label"], scrap["tone"], scrap["terminal"]) == (
        "Aussondern", modules.get(modules.AUSSONDERN).tone, True)
    assert (scrap["action"], block["action"]) == ("Verschrotten", "Sperren"), (
        "Das Verb hängt an der Ausprägung – aus der Registry, nicht aus der Oberfläche.")
    capture = _step(modules.DATENERFASSUNG, {"points": [{"label": "OK", "type": "bool"}]})
    assert capture["terminal"] is False and capture["tone"] != scrap["tone"]


def test_a_module_is_named_by_its_type_and_an_unknown_type_is_not_dressed_up():
    assert modules.label(modules.DATENERFASSUNG) == "Datenerfassung"
    assert modules.label("gibtsnicht") == "gibtsnicht"


def test_the_transition_and_the_place_are_declared_not_configured():
    """Die Datenerfassung misst, sie verändert nichts – der Übergang ist fest, nicht
    einstellbar. Wo das Material des Verbrauchs liegen muss, folgt aus dem Produkt; ein
    Ortsfeld am Modul wäre eine zweite Ortsangabe neben dem Ziel eines Bewegen-Moduls."""
    m = modules.get(modules.DATENERFASSUNG)
    assert (m.status_before, m.status_after) == (st.IM_PROZESS, st.IM_PROZESS)
    assert modules.get(modules.VERBRAUCH).material_place == modules.AT_PRODUCT
