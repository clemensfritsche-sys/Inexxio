"""**Die Fälle.** Jeder mit vorher notiertem Soll (`SYSTEM_LOGIC.md`).

Gelesen wird von zwei Seiten: ``test_scenarios.py`` fährt sie als Wächter,
``scripts/scenario_report.py`` schreibt daraus die Soll/Ist-Tabelle.

Konvention: ``soll`` nennt nur, was der Fall **beweisen** soll. Alles andere wird nicht
behauptet – ein Test, der alles prüft, prüft nichts.
"""

from typing import Any

from fastapi import HTTPException

from tests.scenarios import (
    A_LAGER, A_MIX, A_NEU, B_BATCH, B_EINZEL, C_1, C_2, C_VIELE,
    D_BLOCK, D_ERFASSUNG, D_SCRAP, D_VERBRAUCH, E_1, E_2, E_3, E_KEINE,
    F_AUTO, F_GEKAPPT, F_GEMISCHT, F_NORMAL, Case, World, free_stock,
)

CASES: list[Case] = []


def case(cid: str, title: str, axes: dict[str, str], soll: dict[str, Any],
         note: str = "", impossible: str | None = None,
         open_finding: str | None = None):
    def deco(fn):
        CASES.append(Case(id=cid, title=title, axes=axes, soll=soll, run=fn,
                          note=note, impossible=impossible,
                          open_finding=open_finding))
        return fn
    return deco


def _speaks(detail: str) -> bool:
    """**Nennt die Meldung die betroffene Sache?**

    Nicht «ist sie lang genug» – das misst Prosa, nicht Auskunft. Gefragt ist, ob der
    Leser weiss, *worum* es geht: eine Nummer (Stück · Auftrag · Zeile) oder ein in «»
    genannter Name. «Bestätigen nicht möglich» wäre eine Sackgasse mit Ausrufezeichen.
    """
    return any(c.isdigit() for c in detail) or "«" in detail


def _err(fn, *a, **kw) -> dict[str, Any]:
    """Einen erwarteten Fehler einfangen – Code **und** ob die Meldung etwas sagt."""
    try:
        fn(*a, **kw)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return {"code": exc.status_code, "spricht": _speaks(detail),
                "meldung": detail[:90]}
    except Exception as exc:                                   # noqa: BLE001
        return {"code": type(exc).__name__, "spricht": False, "meldung": str(exc)[:90]}
    return {"code": None, "spricht": False, "meldung": "<kein Fehler>"}


# ===========================================================================
# Block 1 · Grundlauf – Herkunft × Serialisierung × Menge × Modultyp
# ===========================================================================

@case("S01", "Erzeugen · einzeln · 1 · Datenerfassung",
      {"A": A_NEU, "B": B_EINZEL, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "states": {"freigegeben": 1}, "instanzen": 1,
       "scans": 1, "probleme": []})
def s01(w: World):
    art = w.article(serialization="unit")
    order = w.produce(art, 1)
    scans = len(w.work(order, w.steps(order)[0]))
    w.run_all(order)
    return {"status": w.status(order), "states": w.states(order),
            "instanzen": len(w.instances(order)), "scans": scans,
            "probleme": w.problems(order)}


@case("S02", "Erzeugen · Charge · 1 · Datenerfassung",
      {"A": A_NEU, "B": B_BATCH, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "states": {"freigegeben": 1}, "instanzen": 1, "scans": 1})
def s02(w: World):
    art = w.article(serialization="batch")
    order = w.produce(art, 1)
    scans = len(w.work(order, w.steps(order)[0]))
    w.run_all(order)
    return {"status": w.status(order), "states": w.states(order),
            "instanzen": len(w.instances(order)), "scans": scans}


@case("S03", "Erzeugen · einzeln · 2 → zwei Instanzen, zwei Scans",
      {"A": A_NEU, "B": B_EINZEL, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "states": {"freigegeben": 2}, "instanzen": 2, "scans": 2})
def s03(w: World):
    art = w.article(serialization="unit")
    order = w.produce(art, 2)
    scans = len(w.work(order, w.steps(order)[0]))
    w.run_all(order)
    return {"status": w.status(order), "states": w.states(order),
            "instanzen": len(w.instances(order)), "scans": scans}


@case("S04", "Erzeugen · Charge · 2 → EINE Instanz, EIN Scan, ZWEI Erfassungen",
      {"A": A_NEU, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "states": {"freigegeben": 2}, "instanzen": 1,
       "scans": 1, "erfassungen": 2},
      note="Ein Scan, n Erfassungen – die Zahl kommt aus der Ziehung.")
def s04(w: World):
    from app.models import Capture

    art = w.article(serialization="batch")
    order = w.produce(art, 2)
    step = w.steps(order)[0]
    scans = len(w.work(order, step))
    w.run_all(order)
    n = w.db.query(Capture).filter(Capture.order_id == order.id).count()
    return {"status": w.status(order), "states": w.states(order),
            "instanzen": len(w.instances(order)), "scans": scans, "erfassungen": n}


@case("S05", "Erzeugen · Charge · 600 – die Menge ist kein Sonderfall",
      {"A": A_NEU, "B": B_BATCH, "C": C_VIELE, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "stück": 600, "instanzen": 1, "scans": 1,
       "erfassungen": 600})
def s05(w: World):
    from app.models import Capture

    art = w.article(serialization="batch")
    order = w.produce(art, 600)
    step = w.steps(order)[0]
    scans = len(w.work(order, step))
    w.run_all(order)
    n = w.db.query(Capture).filter(Capture.order_id == order.id).count()
    return {"status": w.status(order), "stück": len(w.numbers(order)),
            "instanzen": len(w.instances(order)), "scans": scans, "erfassungen": n}


@case("S06", "Verschrotten · einzeln · 1 → Endzustand, Auftrag abgeschlossen",
      {"A": A_NEU, "B": B_EINZEL, "C": C_1, "D": D_SCRAP, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "states": {"verschrottet": 1}, "probleme": []},
      note="Ein Ausgang IST ein Ende – kein vierter Auftragsstatus.")
def s06(w: World):
    art = w.article(serialization="unit", template=[w.dispose("scrap")])
    order = w.produce(art, 1)
    w.run_all(order)
    return {"status": w.status(order), "states": w.states(order),
            "probleme": w.problems(order)}


@case("S07", "Verschrotten · Charge · 2 → beide Stücke terminal",
      {"A": A_NEU, "B": B_BATCH, "C": C_2, "D": D_SCRAP, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "states": {"verschrottet": 2}})
def s07(w: World):
    art = w.article(serialization="batch", template=[w.dispose("scrap")])
    order = w.produce(art, 2)
    w.run_all(order)
    return {"status": w.status(order), "states": w.states(order)}


@case("S08", "Sperren · einzeln · 1 → gesperrt, aber nicht terminal",
      {"A": A_NEU, "B": B_EINZEL, "C": C_1, "D": D_BLOCK, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "states": {"gesperrt": 1}, "wählbar": True})
def s08(w: World):
    from app.domain import statuses as st

    art = w.article(serialization="unit", template=[w.dispose("block", "Klärung")])
    order = w.produce(art, 1)
    w.run_all(order)
    number = w.numbers(order)[0]
    return {"status": w.status(order), "states": w.states(order),
            "wählbar": st.is_selectable(w.unit_status(number))}


@case("S09", "Lager · einzeln · 1 – bestehendes Stück, kein neues",
      {"A": A_LAGER, "B": B_EINZEL, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "states": {"freigegeben": 1}, "neue_stück": 0,
       "abweichung": False})
def s09(w: World):
    from app.models import InstanceUnit

    art, numbers = free_stock(w, serialization="unit", quantity=1)
    before = w.db.query(InstanceUnit).count()
    order = w.take(art, numbers, steps=[w.capture()])
    after = w.db.query(InstanceUnit).count()
    w.run_all(order)
    return {"status": w.status(order), "states": w.states(order),
            "neue_stück": after - before, "abweichung": w.is_deviation(order)}


@case("S10", "Lager · Teilmenge einer Charge – 1 von 3",
      {"A": A_LAGER, "B": B_BATCH, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"stück_im_auftrag": 1, "status": "abgeschlossen", "rest_frei": 2},
      note="Der Auftrag greift Einzelinstanzen, nicht die Instanz.")
def s10(w: World):
    art, numbers = free_stock(w, serialization="batch", quantity=3)
    order = w.take(art, numbers[:1], steps=[w.capture()])
    w.run_all(order)
    rest = [n for n in numbers[1:] if w.unit_status(n) == "freigegeben"]
    return {"stück_im_auftrag": len(w.numbers(order)), "status": w.status(order),
            "rest_frei": len(rest)}


@case("S11", "ZWEI «Neu»-Zeilen – welche Vorlage gälte?",
      {"A": A_MIX, "B": B_EINZEL, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True},
      note="Ein Auftrag hat EINEN Erzeugungsprozess; zwei Vorlagen sind zwei Aufträge. "
           "«Neu» + «Lager» ist dagegen erlaubt – das ist die Montage (S11b).")
def s11(w: World):
    a1, _ = free_stock(w, serialization="unit", quantity=1)
    a2, _ = free_stock(w, serialization="unit", quantity=1)
    return _err(w.release, lines=[
        {"article_object_id": a1.object_id, "quantity": 1, "origin": "neu", "units": []},
        {"article_object_id": a2.object_id, "quantity": 1, "origin": "neu", "units": []},
    ], steps=[w.capture()])


@case("S11b", "MONTAGE: «Neu» + «Lager» in EINEM Auftrag",
      {"A": A_MIX, "B": B_EINZEL, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "stück": 2, "neue_stück": 1},
      note="Die Regel heisst «höchstens eine Neu-Zeile», nicht «Neu steht allein» – sonst "
           "wäre ausgerechnet die Montage verboten (Produkt erzeugen, Teile verbauen).")
def s11b(w: World):
    product = w.article(serialization="unit", template=[w.capture()])
    part, numbers = free_stock(w, serialization="unit", quantity=1)
    order = w.release(lines=[
        {"article_object_id": product.object_id, "quantity": 1, "origin": "neu",
         "units": []},
        {"article_object_id": part.object_id, "quantity": 1, "origin": "lager",
         "units": [{"number": numbers[0], "from_order": None}]},
    ])
    w.run_all(order, values=World.GOOD)
    return {"status": w.status(order), "stück": len(w.numbers(order)),
            "neue_stück": len([n for n in w.numbers(order) if n not in numbers])}


@case("S16", "MONTAGE: 2 Teile → 1 Baugruppe, Stückliste abgeleitet",
      {"A": A_MIX, "B": B_EINZEL, "C": C_2, "D": D_VERBRAUCH, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "produkt": "freigegeben",
       "teile": {"verbaut": 2}, "stückliste": 2},
      note="Die Stückliste ist kein Feld: sie sind die Stücke, die denselben Auftrag als "
           "«Verbaut» verlassen haben.")
def s16(w: World):
    from app.services import genealogy

    part, numbers = free_stock(w, serialization="unit", quantity=2)
    product = w.article(serialization="unit",
                        template=[w.consume(part.object_id), w.capture()])
    order = w.release(lines=[
        {"article_object_id": product.object_id, "quantity": 1, "origin": "neu",
         "units": []},
        {"article_object_id": part.object_id, "quantity": 2, "origin": "lager",
         "units": [{"number": n, "from_order": None} for n in numbers]},
    ])
    w.run_all(order, values=World.GOOD)
    made = [n for n in w.numbers(order) if n not in numbers]
    return {
        "status": w.status(order),
        "produkt": w.unit_status(made[0]),
        "teile": {w.unit_status(numbers[0]): len(
            [n for n in numbers if w.unit_status(n) == w.unit_status(numbers[0])])},
        "stückliste": len(genealogy.parts_of(w.db, w.unit(made[0]))),
    }


@case("S17", "Verbrauch nennt einen Artikel, den der Auftrag nicht hat",
      {"A": A_NEU, "B": B_EINZEL, "C": C_1, "D": D_VERBRAUCH, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True},
      note="Ein Verbrauchsmodul ohne Material wäre ein stiller Durchgang, der aussieht "
           "wie eine Montage.")
def s17(w: World):
    other, _ = free_stock(w, serialization="unit", quantity=1)
    product = w.article(serialization="unit", template=[w.consume(other.object_id)])
    return _err(w.release, lines=[
        {"article_object_id": product.object_id, "quantity": 1, "origin": "neu",
         "units": []},
    ])


@case("S18", "DEMONTAGE: ein verbautes Stück wird zurückgeholt",
      {"A": A_LAGER, "B": B_EINZEL, "C": C_1, "D": D_VERBRAUCH, "E": E_KEINE, "F": "–"},
      {"vorher": "verbaut", "abweichung": True, "nachher": "freigegeben",
       "stückliste_bleibt": 1, "steckt_noch_drin": False},
      note="«Verbaut» ist nicht terminal – das Greifen IST der Ausbau. Die Stückliste "
           "kommt aus dem Log und verliert das Teil darum NICHT.")
def s18(w: World):
    from app.services import genealogy

    part, numbers = free_stock(w, serialization="unit", quantity=1)
    product = w.article(serialization="unit", template=[w.consume(part.object_id)])
    build = w.release(lines=[
        {"article_object_id": product.object_id, "quantity": 1, "origin": "neu",
         "units": []},
        {"article_object_id": part.object_id, "quantity": 1, "origin": "lager",
         "units": [{"number": numbers[0], "from_order": None}]},
    ])
    w.run_all(build, values=World.GOOD)
    made = [n for n in w.numbers(build) if n not in numbers][0]
    before = w.unit_status(numbers[0])

    strip = w.take(part, [numbers[0]], steps=[w.capture()])
    w.run_all(strip, values=World.GOOD)
    parts = genealogy.parts_of(w.db, w.unit(made))
    return {
        "vorher": before,
        "abweichung": w.is_deviation(strip),
        "nachher": w.unit_status(numbers[0]),
        "stückliste_bleibt": len(parts),
        "steckt_noch_drin": parts[0]["still_in"] if parts else None,
    }


@case("S12", "Gemischt: zwei Lager-Zeilen, zwei Artikel",
      {"A": A_MIX, "B": B_EINZEL, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "stück": 2, "instanzen": 2})
def s12(w: World):
    a1, n1 = free_stock(w, serialization="unit", quantity=1)
    a2, n2 = free_stock(w, serialization="unit", quantity=1)
    order = w.release(lines=[
        {"article_object_id": a1.object_id, "quantity": 1, "origin": "lager",
         "units": [{"number": n1[0], "from_order": None}]},
        {"article_object_id": a2.object_id, "quantity": 1, "origin": "lager",
         "units": [{"number": n2[0], "from_order": None}]},
    ], steps=[w.capture()])
    w.run_all(order)
    return {"status": w.status(order), "stück": len(w.numbers(order)),
            "instanzen": len(w.instances(order))}


@case("S13", "Zwei Module hintereinander",
      {"A": A_NEU, "B": B_EINZEL, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "module": 2, "states": {"freigegeben": 2}})
def s13(w: World):
    art = w.article(serialization="unit", template=[w.capture(), w.capture()])
    order = w.produce(art, 2)
    w.run_all(order)
    return {"status": w.status(order), "module": len(w.steps(order)),
            "states": w.states(order)}


@case("S14", "Erfassung → Verschrotten: der Ausgang steht am Schluss",
      {"A": A_NEU, "B": B_EINZEL, "C": C_1, "D": D_SCRAP, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "states": {"verschrottet": 1}, "probleme": []})
def s14(w: World):
    art = w.article(serialization="unit", template=[w.capture(), w.dispose("scrap")])
    order = w.produce(art, 1)
    w.run_all(order)
    return {"status": w.status(order), "states": w.states(order),
            "probleme": w.problems(order)}


@case("S15", "Modul HINTER einem Ausgang – nicht anlegbar",
      {"A": A_NEU, "B": B_EINZEL, "C": C_1, "D": D_SCRAP, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True})
def s15(w: World):
    return _err(w.article, serialization="unit",
                template=[w.dispose("scrap"), w.capture()])


# ===========================================================================
# Block 2 · Stichprobe
# ===========================================================================

@case("S20", "Stichprobe 50 % von 4 → 2 gezogen",
      {"A": A_NEU, "B": B_BATCH, "C": C_VIELE, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"gezogen": 2, "rest": 2, "erfassungen": 2})
def s20(w: World):
    from app.models import Capture

    art = w.article(serialization="batch",
                    template=[w.capture(sample={"percent": 50})])
    order = w.produce(art, 4)
    step = w.steps(order)[0]
    row = w.work(order, step)[0]
    w.run_all(order)
    n = w.db.query(Capture).filter(Capture.order_id == order.id).count()
    return {"gezogen": row["sample"], "rest": row["rest"], "erfassungen": n}


@case("S21", "Stichprobe 25 % von 3 → aufgerundet 1",
      {"A": A_NEU, "B": B_BATCH, "C": C_VIELE, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"gezogen": 1, "rest": 2})
def s21(w: World):
    art = w.article(serialization="batch",
                    template=[w.capture(sample={"percent": 25})])
    order = w.produce(art, 3)
    row = w.work(order, w.steps(order)[0])[0]
    return {"gezogen": row["sample"], "rest": row["rest"]}


@case("S22", "Stichprobe 1 % von 2 → nie leer",
      {"A": A_NEU, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"gezogen": 1},
      note="«0 von 5» ist keine Prüfung, sondern ihr Ausfall.")
def s22(w: World):
    art = w.article(serialization="batch", template=[w.capture(sample={"percent": 1})])
    order = w.produce(art, 2)
    row = w.work(order, w.steps(order)[0])[0]
    return {"gezogen": row["sample"]}


@case("S23", "Anteil an der GESAMTMENGE, nicht je Instanz",
      {"A": A_LAGER, "B": B_BATCH, "C": C_VIELE, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"gezogen_gesamt": 2, "instanzen": 2},
      note="Zwei Chargen à 2, 50 % → 2 gesamt, nicht 1 je Charge.")
def s23(w: World):
    a1, n1 = free_stock(w, serialization="batch", quantity=2)
    a2, n2 = free_stock(w, serialization="batch", quantity=2)
    order = w.release(lines=[
        {"article_object_id": a1.object_id, "quantity": 2, "origin": "lager",
         "units": [{"number": n, "from_order": None} for n in n1]},
        {"article_object_id": a2.object_id, "quantity": 2, "origin": "lager",
         "units": [{"number": n, "from_order": None} for n in n2]},
    ], steps=[w.capture(sample={"percent": 50})])
    rows = w.work(order, w.steps(order)[0])
    return {"gezogen_gesamt": sum(r["sample"] for r in rows), "instanzen": len(rows)}


@case("S24", "Der ungezogene Rest läuft ohne Erfassung durch – sichtbar",
      {"A": A_NEU, "B": B_BATCH, "C": C_VIELE, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "erfassungen": 2, "stück": 4})
def s24(w: World):
    from app.models import Capture

    art = w.article(serialization="batch", template=[w.capture(sample={"percent": 50})])
    order = w.produce(art, 4)
    w.run_all(order)
    n = w.db.query(Capture).filter(Capture.order_id == order.id).count()
    return {"status": w.status(order), "erfassungen": n, "stück": len(w.numbers(order))}


@case("S25", "Die Ziehung ist eingefroren – zweimal gefragt, dieselbe Antwort",
      {"A": A_NEU, "B": B_BATCH, "C": C_VIELE, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"gleich": True})
def s25(w: World):
    from app.services import sampling as smp

    art = w.article(serialization="batch", template=[w.capture(sample={"percent": 50})])
    order = w.produce(art, 6)
    step = w.steps(order)[0]
    ids = [u.id for u in [w.unit(n) for n in w.numbers(order)] if u]
    first = smp.drawn_at(w.db, order=order, step=step, unit_ids=ids)
    smp.ensure(w.db, order=order, step=step, actor_id=None)
    second = smp.drawn_at(w.db, order=order, step=step, unit_ids=ids)
    return {"gleich": first == second and len(first) == 3}


# ===========================================================================
# Block 3 · «Nicht bestanden»
# ===========================================================================

@case("S30", "Ein schlechtes Stück hält die GANZE Instanz an",
      {"A": A_NEU, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"bewegt": 0, "angehalten": 2, "urteil": "failed", "states": {"im_prozess": 2}})
def s30(w: World):
    art = w.article(serialization="batch")
    order = w.produce(art, 2)
    step = w.steps(order)[0]
    inst = w.work(order, step)[0]["instance_object_id"]
    out = w.confirm(order, step, instance=inst, values=w.BAD)
    return {"bewegt": out["moved"], "angehalten": out["held"], "urteil": out["result"],
            "states": w.states(order)}


@case("S31", "Der Halt hat einen Ausgang: erneut erfassen",
      {"A": A_NEU, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"nach_schlecht_held": True, "nach_gut_held": False, "status": "abgeschlossen"},
      note="Der Halt ist eine Auskunft, keine Sperre.")
def s31(w: World):
    art = w.article(serialization="batch")
    order = w.produce(art, 2)
    step = w.steps(order)[0]
    inst = w.work(order, step)[0]["instance_object_id"]
    w.confirm(order, step, instance=inst, values=w.BAD)
    held_bad = w.work(order, step)[0]["held"]
    w.confirm(order, step, instance=inst, values=w.GOOD)
    rows = w.work(order, step)
    return {"nach_schlecht_held": held_bad,
            "nach_gut_held": rows[0]["held"] if rows else False,
            "status": w.status(order)}


@case("S32", "Ein «nicht bestanden» legt NICHTS an",
      {"A": A_NEU, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"neue_aufträge": 0})
def s32(w: World):
    from app.models import Order

    art = w.article(serialization="batch")
    order = w.produce(art, 2)
    step = w.steps(order)[0]
    inst = w.work(order, step)[0]["instance_object_id"]
    before = w.db.query(Order).count()
    w.confirm(order, step, instance=inst, values=w.BAD)
    return {"neue_aufträge": w.db.query(Order).count() - before}


# ===========================================================================
# Block 4 · Abweichung, Schachtelung, Rückführung  ← der Schwerpunkt
# ===========================================================================

def _parent_with_child(w: World, *, quantity: int = 2, returns: bool = True,
                       child_template=None, take: int = 1):
    """Ein laufender Auftrag, aus dem eine Abweichung ``take`` Stücke nimmt."""
    art = w.article(serialization="batch", template=[w.capture(), w.capture()])
    parent = w.produce(art, quantity)
    numbers = w.numbers(parent)
    child = w.take(art, numbers[:take], from_order=parent.object_id, returns=returns,
                   steps=child_template or [w.capture()])
    return art, parent, child, numbers


@case("S40", "Eine Abweichung, normale Rückführung – zurück an denselben Punkt",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_1, "F": F_NORMAL},
      {"abweichung": True, "eltern_wartet_vorher": True, "eltern_wartet_nachher": False,
       "punkt_gleich": True, "eltern_status": "im_prozess", "probleme": []})
def s40(w: World):
    from app.models import OrderUnit

    art, parent, child, numbers = _parent_with_child(w)
    step0 = w.steps(parent)[0]
    punkt_vorher = (
        w.db.query(OrderUnit)
        .filter(OrderUnit.order_id == parent.id,
                OrderUnit.instance_unit_id == w.unit(numbers[0]).id)
        .order_by(OrderUnit.id).first().current_step_id
    )
    wartet_vorher = w.waits(parent)
    w.run_all(child)
    row = (
        w.db.query(OrderUnit)
        .filter(OrderUnit.order_id == parent.id,
                OrderUnit.instance_unit_id == w.unit(numbers[0]).id,
                OrderUnit.released_at.is_(None))
        .first()
    )
    return {"abweichung": w.is_deviation(child),
            "eltern_wartet_vorher": wartet_vorher,
            "eltern_wartet_nachher": w.waits(parent),
            "punkt_gleich": bool(row and row.current_step_id == punkt_vorher == step0.id),
            "eltern_status": w.status(parent), "probleme": w.problems(parent)}


@case("S41", "Zwei Abweichungen parallel – der Eltern wartet auf BEIDE",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_1, "F": F_NORMAL},
      {"verliehen": 2, "wartet_am_anfang": True, "wartet_nach_einer": True,
       "wartet_nach_beiden": False, "gesperrte_module": 1})
def s41(w: World):
    art = w.article(serialization="batch", template=[w.capture(), w.capture()])
    parent = w.produce(art, 2)
    numbers = w.numbers(parent)
    c1 = w.take(art, numbers[:1], from_order=parent.object_id, steps=[w.capture()])
    c2 = w.take(art, numbers[1:], from_order=parent.object_id, steps=[w.capture()])
    lent = w.lent(parent)
    am_anfang = w.waits(parent)
    gesperrt = len(w.blocked_steps(parent))
    w.run_all(c1)
    nach_einer = w.waits(parent)
    w.run_all(c2)
    return {"verliehen": lent, "wartet_am_anfang": am_anfang,
            "wartet_nach_einer": nach_einer, "wartet_nach_beiden": w.waits(parent),
            "gesperrte_module": gesperrt}


@case("S42", "Zwei Abweichungen nacheinander",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_1, "F": F_NORMAL},
      {"wartet_zwischendurch": True, "wartet_am_ende": False,
       "eltern_status": "im_prozess", "probleme": []})
def s42(w: World):
    art, parent, c1, numbers = _parent_with_child(w)
    w.run_all(c1)
    c2 = w.take(art, numbers[1:], from_order=parent.object_id, steps=[w.capture()])
    zwischen = w.waits(parent)
    w.run_all(c2)
    return {"wartet_zwischendurch": zwischen, "wartet_am_ende": w.waits(parent),
            "eltern_status": w.status(parent), "probleme": w.problems(parent)}


@case("S43", "Drei Ebenen tief, alle rückführend – die Kette trägt",
      {"A": A_LAGER, "B": B_BATCH, "C": C_1, "D": D_ERFASSUNG, "E": E_3, "F": F_NORMAL},
      {"a_wartet": True, "b_wartet": True, "a_status": "im_prozess",
       "nach_c_a_wartet": True, "nach_b_a_wartet": False,
       "a_am_schluss": "abgeschlossen", "stück": "freigegeben"},
      note="Leiht A an B und B an C, wartet auch A – nur eine Stufe tiefer. Nach C ist "
           "das Stück bei B, also wartet A weiter; erst nach B ist es zurück.")
def s43(w: World):
    art = w.article(serialization="batch", template=[w.capture(), w.capture()])
    a = w.produce(art, 1)
    n = w.numbers(a)
    b = w.take(art, n, from_order=a.object_id, steps=[w.capture()])
    c = w.take(art, n, from_order=b.object_id, steps=[w.capture()])
    a_wartet, b_wartet, a_status = w.waits(a), w.waits(b), w.status(a)
    w.run_all(c)
    nach_c = w.waits(a)
    w.run_all(b)
    nach_b = w.waits(a)
    w.run_all(a)
    return {"a_wartet": a_wartet, "b_wartet": b_wartet, "a_status": a_status,
            "nach_c_a_wartet": nach_c, "nach_b_a_wartet": nach_b,
            "a_am_schluss": w.status(a), "stück": w.unit_status(n[0])}


@case("S44", "Rückführung bei der Definition GEKAPPT – der Eltern wartet nicht",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_1, "F": F_GEKAPPT},
      {"eltern_wartet": False, "verliehen": 0, "eltern_läuft_weiter": "abgeschlossen",
       "eltern_stück": 1})
def s44(w: World):
    art, parent, child, numbers = _parent_with_child(w, returns=False)
    wartet, lent = w.waits(parent), w.lent(parent)
    w.run_all(parent)
    verblieben = sum(1 for n in numbers[1:] if w.unit_status(n) == "freigegeben")
    return {"eltern_wartet": wartet, "verliehen": lent,
            "eltern_läuft_weiter": w.status(parent), "eltern_stück": verblieben}


@case("S45", "AUTO-Kappung durch Verschrotten in der Abweichung",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_SCRAP, "E": E_1, "F": F_AUTO},
      {"wartet_vorher": True, "wartet_nachher": False, "kind_status": "abgeschlossen",
       "eltern_status": "abgeschlossen", "stück": "verschrottet", "eltern_rest": 1},
      note="Ohne eine Zeile Wartelogik: der Ausgang schliesst die Zugehörigkeit.")
def s45(w: World):
    art, parent, child, numbers = _parent_with_child(
        w, child_template=[w.dispose("scrap")])
    vorher = w.waits(parent)
    w.run_all(child)
    nachher = w.waits(parent)
    w.run_all(parent)
    rest = sum(1 for n in numbers[1:] if w.unit_status(n) == "freigegeben")
    return {"wartet_vorher": vorher, "wartet_nachher": nachher,
            "kind_status": w.status(child), "eltern_status": w.status(parent),
            "stück": w.unit_status(numbers[0]), "eltern_rest": rest}


@case("S46", "Gemischt: eine Abweichung rückführend, eine gekappt",
      {"A": A_LAGER, "B": B_BATCH, "C": C_VIELE, "D": D_ERFASSUNG, "E": E_1, "F": F_GEMISCHT},
      {"verliehen": 1, "wartet": True, "nach_rückkehr_wartet": False,
       "eltern_status": "im_prozess"})
def s46(w: World):
    art = w.article(serialization="batch", template=[w.capture(), w.capture()])
    parent = w.produce(art, 3)
    numbers = w.numbers(parent)
    zurueck = w.take(art, numbers[:1], from_order=parent.object_id, steps=[w.capture()])
    w.take(art, numbers[1:2], from_order=parent.object_id, returns=False,
           steps=[w.capture()])
    lent, wartet = w.lent(parent), w.waits(parent)
    w.run_all(zurueck)
    return {"verliehen": lent, "wartet": wartet,
            "nach_rückkehr_wartet": w.waits(parent), "eltern_status": w.status(parent)}


@case("S47", "Aussondern auf EBENE 3, während 1 und 2 warten",
      {"A": A_LAGER, "B": B_BATCH, "C": C_1, "D": D_SCRAP, "E": E_3, "F": F_AUTO},
      {"a_wartet_vorher": True, "b_wartet_vorher": True,
       "a_wartet_nachher": False, "b_wartet_nachher": False,
       "a_status": "abgebrochen", "b_status": "abgebrochen", "c_status": "abgeschlossen",
       "stück": "verschrottet"},
      note="Löst sich die Wartekette bis nach oben auf?")
def s47(w: World):
    art = w.article(serialization="batch", template=[w.capture(), w.capture()])
    a = w.produce(art, 1)
    n = w.numbers(a)
    b = w.take(art, n, from_order=a.object_id, steps=[w.capture()])
    c = w.take(art, n, from_order=b.object_id, steps=[w.dispose("scrap")])
    a_vor, b_vor = w.waits(a), w.waits(b)
    w.run_all(c)
    return {"a_wartet_vorher": a_vor, "b_wartet_vorher": b_vor,
            "a_wartet_nachher": w.waits(a), "b_wartet_nachher": w.waits(b),
            "a_status": w.status(a), "b_status": w.status(b), "c_status": w.status(c),
            "stück": w.unit_status(n[0])}


@case("S48", "Eltern abschliessen, während ein GEKAPPTER Unterauftrag noch läuft",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_1, "F": F_GEKAPPT},
      {"eltern_status": "abgeschlossen", "kind_status": "im_prozess"})
def s48(w: World):
    art, parent, child, numbers = _parent_with_child(w, returns=False)
    w.run_all(parent)
    return {"eltern_status": w.status(parent), "kind_status": w.status(child)}


@case("S49a", "ALLE Stücke in Abweichungen, rückführend → Eltern Im Prozess",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_1, "F": F_NORMAL},
      {"eltern_status": "im_prozess", "unterwegs": 0, "verliehen": 2})
def s49a(w: World):
    art, parent, child, numbers = _parent_with_child(w, take=2)
    return {"eltern_status": w.status(parent), "unterwegs": len(w.work(parent, w.steps(parent)[0])),
            "verliehen": w.lent(parent)}


@case("S49b", "ALLE Stücke gekappt übernommen → Eltern Abgebrochen",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_1, "F": F_GEKAPPT},
      {"eltern_status": "abgebrochen", "verliehen": 0})
def s49b(w: World):
    art, parent, child, numbers = _parent_with_child(w, take=2, returns=False)
    return {"eltern_status": w.status(parent), "verliehen": w.lent(parent)}


@case("S50", "Abweichung auf ein Stück, das schon in einer Abweichung ist",
      {"A": A_LAGER, "B": B_BATCH, "C": C_1, "D": D_ERFASSUNG, "E": E_2, "F": F_NORMAL},
      {"erlaubt": True, "c_ist_abweichung": True, "offene_zeilen": 1})
def s50(w: World):
    from app.models import OrderUnit

    art = w.article(serialization="batch", template=[w.capture(), w.capture()])
    a = w.produce(art, 1)
    n = w.numbers(a)
    b = w.take(art, n, from_order=a.object_id, steps=[w.capture()])
    c = w.take(art, n, from_order=b.object_id, steps=[w.capture()])
    offen = (
        w.db.query(OrderUnit)
        .filter(OrderUnit.instance_unit_id == w.unit(n[0]).id,
                OrderUnit.released_at.is_(None))
        .count()
    )
    return {"erlaubt": c is not None, "c_ist_abweichung": w.is_deviation(c),
            "offene_zeilen": offen}


@case("S51", "Gesperrtes Stück greifen = Sonderfreigabe (auch eine Abweichung)",
      {"A": A_LAGER, "B": B_EINZEL, "C": C_1, "D": D_BLOCK, "E": E_KEINE, "F": "–"},
      {"vorher": "gesperrt", "abweichung": True, "nachher": "freigegeben"},
      note="Das Greifen IST das Aufheben – es gibt keinen Entsperren-Endpunkt.")
def s51(w: World):
    art = w.article(serialization="unit", template=[w.dispose("block", "Klärung")])
    order = w.produce(art, 1)
    number = w.numbers(order)[0]
    w.run_all(order)
    vorher = w.unit_status(number)
    rescue = w.take(art, [number], steps=[w.capture()])
    ist_abw = w.is_deviation(rescue)
    w.run_all(rescue)
    return {"vorher": vorher, "abweichung": ist_abw, "nachher": w.unit_status(number)}


@case("S52", "Ein gesperrtes Modul lässt sich nicht bestätigen",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_1, "F": F_NORMAL},
      {"code": 409, "spricht": True})
def s52(w: World):
    art, parent, child, numbers = _parent_with_child(w)
    step = w.steps(parent)[0]
    inst = w.instances(parent)[0]
    return _err(w.confirm, parent, step, instance=inst)


# ===========================================================================
# Block 5 · Exklusivität aktiv brechen
# ===========================================================================

@case("S60", "Dasselbe Stück zweimal in EINEM Auftrag",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True})
def s60(w: World):
    art, numbers = free_stock(w, serialization="batch", quantity=2)
    return _err(w.release, lines=[{
        "article_object_id": art.object_id, "quantity": 2, "origin": "lager",
        "units": [{"number": numbers[0], "from_order": None},
                  {"number": numbers[0], "from_order": None}],
    }], steps=[w.capture()])


@case("S61", "Auswahl behauptet «aus Auftrag N», Stück ist frei",
      {"A": A_LAGER, "B": B_EINZEL, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 409, "spricht": True},
      note="Ein Auftrag darf nie unbemerkt seine Art ändern.")
def s61(w: World):
    art, numbers = free_stock(w, serialization="unit", quantity=1)
    other = w.produce(art, 1)
    return _err(w.take, art, numbers, from_order=other.object_id, steps=[w.capture()])


@case("S62", "Auswahl behauptet «frei», Stück läuft in einem Auftrag",
      {"A": A_LAGER, "B": B_BATCH, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 409, "spricht": True})
def s62(w: World):
    art = w.article(serialization="batch")
    running = w.produce(art, 1)
    numbers = w.numbers(running)
    return _err(w.take, art, numbers, from_order=None, steps=[w.capture()])


@case("S64", "Sequenzielle Übernahme: nie zwei offene Zugehörigkeiten",
      {"A": A_LAGER, "B": B_BATCH, "C": C_1, "D": D_ERFASSUNG, "E": E_1, "F": F_NORMAL},
      {"offene_zeilen": 1, "gesamt_zeilen": 2})
def s64(w: World):
    from app.models import OrderUnit

    art = w.article(serialization="batch", template=[w.capture(), w.capture()])
    a = w.produce(art, 1)
    n = w.numbers(a)
    w.take(art, n, from_order=a.object_id, steps=[w.capture()])
    uid = w.unit(n[0]).id
    q = w.db.query(OrderUnit).filter(OrderUnit.instance_unit_id == uid)
    return {"offene_zeilen": q.filter(OrderUnit.released_at.is_(None)).count(),
            "gesamt_zeilen": w.db.query(OrderUnit).filter(
                OrderUnit.instance_unit_id == uid).count()}


# ===========================================================================
# Block 6 · Terminale Status aktiv brechen
# ===========================================================================

def _scrapped(w: World):
    art = w.article(serialization="unit", template=[w.dispose("scrap")])
    order = w.produce(art, 1)
    number = w.numbers(order)[0]
    w.run_all(order)
    return art, number


@case("S70", "Verschrottetes Stück in einen NEUEN Auftrag",
      {"A": A_LAGER, "B": B_EINZEL, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 409, "spricht": True})
def s70(w: World):
    art, number = _scrapped(w)
    return _err(w.take, art, [number], steps=[w.capture()])


@case("S71", "Verschrottetes Stück per rohem UPDATE",
      {"A": "–", "B": B_EINZEL, "C": C_1, "D": D_SCRAP, "E": E_KEINE, "F": "–"},
      {"abgewiesen": True},
      note="Der Schutz ist eine Eigenschaft der Tabelle, keine Regel der Anwendung.")
def s71(w: World):
    from sqlalchemy import text

    art, number = _scrapped(w)
    unit = w.unit(number)
    w.db.flush()
    try:
        w.db.execute(text("UPDATE instance_units SET status='freigegeben' WHERE id=:i"),
                     {"i": unit.id})
        w.db.flush()
        return {"abgewiesen": False}
    except Exception:                                          # noqa: BLE001
        w.db.rollback()
        return {"abgewiesen": True}


@case("S72", "Auftrag mit verschrottetem Stück abschliessen",
      {"A": A_NEU, "B": B_EINZEL, "C": C_1, "D": D_SCRAP, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen"})
def s72(w: World):
    art = w.article(serialization="unit", template=[w.dispose("scrap")])
    order = w.produce(art, 1)
    w.run_all(order)
    return {"status": w.status(order)}


@case("S73", "Verschrottetes Stück in eine Abweichung ziehen",
      {"A": A_LAGER, "B": B_EINZEL, "C": C_1, "D": D_ERFASSUNG, "E": E_1, "F": F_NORMAL},
      {"code": 409, "spricht": True})
def s73(w: World):
    art, number = _scrapped(w)
    other = w.produce(art, 1)
    return _err(w.take, art, [number], from_order=other.object_id, steps=[w.capture()])


@case("S74", "Der ENTWURF meldet es – nicht erst der Klick",
      {"A": A_LAGER, "B": B_EINZEL, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"freigebbar": False, "grund_genannt": True})
def s74(w: World):
    from app.services import orders as orders_svc

    art, number = _scrapped(w)
    missing = orders_svc.validate_draft(w.db, {
        "lines": [{"article_object_id": art.object_id, "quantity": 1, "origin": "lager",
                   "units": [{"number": number, "from_order": None}]}],
        "steps": [w.capture()],
    })
    return {"freigebbar": not missing,
            "grund_genannt": any("Endzustand" in m for m in missing)}


# ===========================================================================
# Block 7 · Mengenintegrität
# ===========================================================================

@case("S80", "Menge N heisst: danach laufen exakt N Einzelinstanzen",
      {"A": A_NEU, "B": B_BATCH, "C": C_VIELE, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"soll": 7, "ist": 7})
def s80(w: World):
    art = w.article(serialization="batch")
    order = w.produce(art, 7)
    return {"soll": 7, "ist": len(w.numbers(order))}


@case("S81", "Nach der Aussonderung bleibt die Zeile – nur der Zustand wechselt",
      {"A": A_NEU, "B": B_BATCH, "C": C_2, "D": D_SCRAP, "E": E_KEINE, "F": "–"},
      {"zeilen_vorher": 2, "zeilen_nachher": 2, "states": {"verschrottet": 2}})
def s81(w: World):
    art = w.article(serialization="batch", template=[w.dispose("scrap")])
    order = w.produce(art, 2)
    vorher = len(w.numbers(order))
    w.run_all(order)
    return {"zeilen_vorher": vorher, "zeilen_nachher": len(w.numbers(order)),
            "states": w.states(order)}


@case("S82", "Nach der Rückführung stimmt die Menge des Eltern wieder",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_1, "F": F_NORMAL},
      {"eltern_stück": 2, "am_ende_frei": 2})
def s82(w: World):
    art, parent, child, numbers = _parent_with_child(w)
    w.run_all(child)
    w.run_all(parent)
    frei = sum(1 for n in numbers if w.unit_status(n) == "freigegeben")
    return {"eltern_stück": len(w.numbers(parent)), "am_ende_frei": frei}


@case("S83", "Lager-Zeile mit zu wenigen Stücken",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True})
def s83(w: World):
    art, numbers = free_stock(w, serialization="batch", quantity=2)
    return _err(w.release, lines=[{
        "article_object_id": art.object_id, "quantity": 2, "origin": "lager",
        "units": [{"number": numbers[0], "from_order": None}],
    }], steps=[w.capture()])


@case("S84", "Menge 0",
      {"A": A_NEU, "B": B_EINZEL, "C": "0", "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True})
def s84(w: World):
    art = w.article(serialization="unit")
    return _err(w.produce, art, 0)


# ===========================================================================
# Block 8 · «Nichts erfinden»
# ===========================================================================

@case("S90", "«Neu» ohne Erzeugungsprozess am Artikel",
      {"A": A_NEU, "B": B_EINZEL, "C": C_1, "D": "–", "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True})
def s90(w: World):
    from app.models import Article
    from app.services import objects as obj

    art = Article(object_id=obj.next_object_id(w.db), name="Ohne Vorlage", unit="stk",
                  serialization="unit", status="freigegeben")
    w.db.add(art)
    w.db.flush()
    return _err(w.produce, art, 1)


@case("S91", "Unbekannter Modultyp",
      {"A": A_NEU, "B": B_EINZEL, "C": C_1, "D": "–", "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True})
def s91(w: World):
    return _err(w.article, serialization="unit",
                template=[{"module_type": "zauberei", "config": {}}])


@case("S92", "Unbekannter Erfassungstyp",
      {"A": A_NEU, "B": B_EINZEL, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True})
def s92(w: World):
    return _err(w.article, serialization="unit",
                template=[w.capture(points=[{"label": "X", "type": "hellsehen"}])])


@case("S93", "Aussondern ohne Grund",
      {"A": A_NEU, "B": B_EINZEL, "C": C_1, "D": D_SCRAP, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True})
def s93(w: World):
    return _err(w.article, serialization="unit",
                template=[{"module_type": "aussondern", "config": {"mode": "scrap"}}])


@case("S94", "Pflichtpunkt nicht erfasst",
      {"A": A_NEU, "B": B_BATCH, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True},
      note="Der Fehler kommt – er nennt aber nur den Punkt, nicht das Stück.",
      open_finding="FINDINGS.md 🟡-1")
def s94(w: World):
    from app.services import process as proc

    art = w.article(serialization="batch")
    order = w.produce(art, 1)
    step = w.steps(order)[0]
    inst = w.work(order, step)[0]["instance_object_id"]
    # Der Wertesatz ist da, der Pflichtpunkt darin ist es nicht. (Über ``World.confirm``
    # wäre der Fall nicht stellbar – der Helfer füllt einen leeren Satz auf.)
    gezogen = proc.held_numbers(w.db, order, step, instance_object_id=inst, group="sample")
    return _err(proc.confirm_step, w.db, order=order, step_id=step.id,
                values={gezogen[0]: {}},
                instance_object_id=inst, verification="scan", actor_id=None)


@case("S95", "Wertesatz für ein NICHT gezogenes Stück",
      {"A": A_NEU, "B": B_BATCH, "C": C_VIELE, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True})
def s95(w: World):
    from app.services import process as proc

    art = w.article(serialization="batch", template=[w.capture(sample={"percent": 50})])
    order = w.produce(art, 4)
    step = w.steps(order)[0]
    inst = w.work(order, step)[0]["instance_object_id"]
    gezogen = proc.held_numbers(w.db, order, step, instance_object_id=inst, group="sample")
    # Der ungezogene Rest wird **abgeleitet**, nicht abgefragt: die Gruppe «rest» ist mit
    # der 100 %-Kontrolle entfallen (#713), die Frage «wer wurde nicht gezogen» bleibt.
    rest = [n for n in w.numbers(order) if n not in set(gezogen)]
    payload = {n: dict(w.GOOD) for n in gezogen}
    payload[rest[0]] = dict(w.GOOD)
    return _err(proc.confirm_step, w.db, order=order, step_id=step.id, values=payload,
                instance_object_id=inst, verification="scan", actor_id=None)


@case("S96", "Fehlender Wertesatz für ein gezogenes Stück",
      {"A": A_NEU, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True})
def s96(w: World):
    from app.services import process as proc

    art = w.article(serialization="batch")
    order = w.produce(art, 2)
    step = w.steps(order)[0]
    inst = w.work(order, step)[0]["instance_object_id"]
    gezogen = proc.held_numbers(w.db, order, step, instance_object_id=inst, group="sample")
    return _err(proc.confirm_step, w.db, order=order, step_id=step.id,
                values={gezogen[0]: dict(w.GOOD)},
                instance_object_id=inst, verification="scan", actor_id=None)


@case("S97", "Ohne Verifikation der Instanz",
      {"A": A_NEU, "B": B_BATCH, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True})
def s97(w: World):
    from app.services import process as proc

    art = w.article(serialization="batch")
    order = w.produce(art, 1)
    step = w.steps(order)[0]
    return _err(proc.confirm_step, w.db, order=order, step_id=step.id, values={},
                actor_id=None)


@case("S98", "Auftrag auf einen INAKTIVEN Artikel",
      {"A": A_NEU, "B": B_EINZEL, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"code": 400, "spricht": True},
      note="Nur ein freigegebener Artikel erzeugt Neues (articles.may_create).")
def s98(w: World):
    art = w.article(serialization="unit")
    art.status = "inaktiv"
    w.db.flush()
    return _err(w.produce, art, 1)


@case("S26", "Ein Stück, das in einer Abweichung war, entgeht der Prüfung nicht",
      {"A": A_LAGER, "B": B_EINZEL, "C": C_2, "D": D_ERFASSUNG, "E": E_1, "F": F_NORMAL},
      {"modul1_gesperrt": True, "am_modul2_erfasst": 2},
      note="Risiko R4 – kann ein Stück durch eine Abweichung der Stichprobe entkommen?")
def s26(w: World):
    from app.models import Capture

    art = w.article(serialization="unit", template=[w.capture(), w.capture()])
    parent = w.produce(art, 2)
    numbers = w.numbers(parent)
    child = w.take(art, numbers[:1], from_order=parent.object_id, steps=[w.capture()])
    gesperrt = bool(w.blocked_steps(parent))
    w.run_all(child)
    w.run_step(parent, w.steps(parent)[0])
    step2 = w.steps(parent)[1]
    w.run_step(parent, step2)
    n = (
        w.db.query(Capture)
        .filter(Capture.order_id == parent.id, Capture.step_id == step2.id)
        .count()
    )
    return {"modul1_gesperrt": gesperrt, "am_modul2_erfasst": n}


@case("S53", "Gesperrt ist nur DAS Modul mit der offenen Rückführung",
      {"A": A_LAGER, "B": B_EINZEL, "C": C_2, "D": D_ERFASSUNG, "E": E_1, "F": F_NORMAL},
      {"gesperrte_module": 1, "module_gesamt": 2},
      note="Eine Sperre über den ganzen Auftrag wäre zu grob.")
def s53(w: World):
    art = w.article(serialization="unit", template=[w.capture(), w.capture()])
    parent = w.produce(art, 2)
    numbers = w.numbers(parent)
    w.take(art, numbers[:1], from_order=parent.object_id, steps=[w.capture()])
    return {"gesperrte_module": len(w.blocked_steps(parent)),
            "module_gesamt": len(w.steps(parent))}


@case("S63", "NEBENLÄUFIGKEIT – zwei Freigaben mit demselben freien Stück",
      {"A": A_LAGER, "B": B_EINZEL, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"erfolge": 1, "offene_zeilen": 1},
      note="Risiko R3 – der Index ist die einzige Stelle, an der es nicht umgangen wird.")
def s63(w: World):
    import threading

    from app.models import OrderUnit
    from app.services import process as proc
    from tests.runner import session

    art, numbers = free_stock(w, serialization="unit", quantity=1)
    w.db.commit()

    lines = [{"article_object_id": art.object_id, "quantity": 1, "origin": "lager",
              "units": [{"number": numbers[0], "from_order": None}]}]
    steps = [w.capture()]
    start = threading.Barrier(2)
    outcome: list[tuple[bool, str]] = []
    lock = threading.Lock()

    def attempt():
        db = session()
        try:
            start.wait(timeout=10)
            proc.release(db, lines=[dict(ln) for ln in lines],
                         steps=[dict(s) for s in steps], actor_id=None)
            db.commit()
            with lock:
                outcome.append((True, ""))
        except Exception as exc:                               # noqa: BLE001
            db.rollback()
            with lock:
                outcome.append((False, type(exc).__name__))
        finally:
            db.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    check = session()
    try:
        unit = proc._resolve_units(check, [numbers[0]], seen=set())[0][0]
        offen = (
            check.query(OrderUnit)
            .filter(OrderUnit.instance_unit_id == unit.id,
                    OrderUnit.released_at.is_(None))
            .count()
        )
    finally:
        check.close()
    return {"erfolge": sum(1 for ok, _ in outcome if ok), "offene_zeilen": offen,
            "verlierer": next((e for ok, e in outcome if not ok), "–")}


@case("S85", "Eine gescheiterte Freigabe verbraucht KEINE Objektnummer",
      {"A": A_LAGER, "B": B_EINZEL, "C": C_1, "D": D_ERFASSUNG, "E": E_KEINE, "F": "–"},
      {"nummer_verbraucht": 0},
      note="Die Prüfungen liegen vor der Nummernvergabe (§6.3).")
def s85(w: World):
    from sqlalchemy import text

    art, number = _scrapped(w)

    def peek() -> int:
        return int(w.db.execute(text("SELECT last_value FROM object_id_seq")).scalar())

    vorher = peek()
    _err(w.take, art, [number], steps=[w.capture()])
    return {"nummer_verbraucht": peek() - vorher}


@case("S86", "Der Log ist die Wahrheit: Zustand == letzter Eintrag",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_ERFASSUNG, "E": E_1, "F": F_NORMAL},
      {"abweichungen": []},
      note="Projektion und Log dürfen nicht auseinanderlaufen.")
def s86(w: World):
    from app.models import InstanceUnit, ProcessEvent

    art, parent, child, numbers = _parent_with_child(w)
    w.run_all(child)
    w.run_all(parent)
    bad: list[str] = []
    for n in numbers:
        unit = w.unit(n)
        last = (
            w.db.query(ProcessEvent)
            .filter(ProcessEvent.instance_unit_id == unit.id)
            .order_by(ProcessEvent.id.desc()).first()
        )
        row = w.db.query(InstanceUnit).filter(InstanceUnit.id == unit.id).first()
        if last is not None and row.status != last.status_after:
            bad.append(f"{n}: Zeile {row.status} · Log {last.status_after}")
    return {"abweichungen": bad}


@case("S99", "Unbekannter Status wird gemeldet, nicht einsortiert",
      {"A": "–", "B": "–", "C": "–", "D": "–", "E": E_KEINE, "F": "–"},
      {"bestand": "unknown", "terminal": False, "wählbar": False, "beschriftung": "phantasie"})
def s99(w: World):
    from app.domain import statuses as st

    return {"bestand": st.stock_kind("phantasie"), "terminal": st.is_terminal("phantasie"),
            "wählbar": st.is_selectable("phantasie"), "beschriftung": st.label("phantasie")}


# ===========================================================================
# Block 9 · Der Abbruch IST eine Abweichung
# ===========================================================================
#
# Es gibt keine Abbruch-Funktion, und das ist eine Entscheidung, kein Loch: ein Auftrag
# wird abgebrochen, indem ihm über einen **Abweichungsauftrag alle Stücke entzogen und
# die Rückführung gekappt** wird. Der Weg zwingt dazu, zu regeln, **was mit den Stücken
# geschehen soll** – ein Knopf «abbrechen» liesse genau diese Frage offen.

@case("S57", "ABBRUCH: alle Stücke entzogen und gekappt → Auftrag abgebrochen",
      {"A": A_LAGER, "B": B_BATCH, "C": C_2, "D": D_SCRAP, "E": E_1, "F": F_GEKAPPT},
      {"eltern_status": "abgebrochen", "eltern_wartet": False,
       "module_gesperrt": 0, "abbrecher_status": "abgeschlossen",
       "stück": {"verschrottet": 2}, "probleme": []},
      note="Der Ausgang existiert – er heisst nur nicht «Abbrechen».")
def s57(w: World):
    art = w.article(serialization="batch", template=[w.capture(), w.capture()])
    opfer = w.produce(art, 2)
    numbers = w.numbers(opfer)
    # Der «Abbruch»: alle Stücke, Rückführung gekappt, und ein definiertes Schicksal.
    abbrecher = w.take(art, numbers, from_order=opfer.object_id, returns=False,
                       steps=[w.dispose("scrap", "Auftrag abgebrochen")])
    status_direkt = w.status(opfer)
    w.run_all(abbrecher)
    zustand: dict[str, int] = {}
    for n in numbers:
        s = w.unit_status(n)
        zustand[s] = zustand.get(s, 0) + 1
    return {"eltern_status": status_direkt, "eltern_wartet": w.waits(opfer),
            "module_gesperrt": len(w.blocked_steps(opfer)),
            "abbrecher_status": w.status(abbrecher), "stück": zustand,
            "probleme": w.problems(opfer)}


@case("S58", "ABBRUCH beim OBERSTEN Auftrag – ohne Elternteil",
      {"A": A_NEU, "B": B_EINZEL, "C": C_2, "D": D_SCRAP, "E": E_1, "F": F_GEKAPPT},
      {"eltern_status": "abgebrochen", "hat_eltern": False},
      note="Der Erzeugungsauftrag hat keinen Vorgänger – der Weg muss trotzdem gehen.")
def s58(w: World):
    from app.models import OrderUnit

    art = w.article(serialization="unit", template=[w.capture()])
    oberster = w.produce(art, 2)
    numbers = w.numbers(oberster)
    w.take(art, numbers, from_order=oberster.object_id, returns=False,
           steps=[w.dispose("scrap", "Auftrag abgebrochen")])
    # «Ohne Elternteil» heisst: keine Zeile dieses Auftrags führt irgendwohin zurück.
    hat_eltern = (
        w.db.query(OrderUnit)
        .filter(OrderUnit.order_id == oberster.id,
                OrderUnit.return_to_order_id.isnot(None))
        .count() > 0
    )
    return {"eltern_status": w.status(oberster), "hat_eltern": hat_eltern}


@case("S59", "Ein liegengelassener Abzweig klemmt den Eltern NICHT dauerhaft",
      {"A": A_LAGER, "B": B_BATCH, "C": C_1, "D": D_SCRAP, "E": E_2, "F": F_GEKAPPT},
      {"a_wartet_vorher": True, "a_wartet_nachher": False,
       "a_status": "abgebrochen", "b_status": "abgebrochen"},
      note="Der Ausweg aus O2: man entzieht dem stehengebliebenen Abzweig seinerseits "
           "die Stücke.")
def s59(w: World):
    art = w.article(serialization="batch", template=[w.capture(), w.capture()])
    a = w.produce(art, 1)
    n = w.numbers(a)
    b = w.take(art, n, from_order=a.object_id, steps=[w.capture()])   # bleibt liegen
    vorher = w.waits(a)
    w.take(art, n, from_order=b.object_id, returns=False,
           steps=[w.dispose("scrap", "Abzweig aufgelöst")])
    return {"a_wartet_vorher": vorher, "a_wartet_nachher": w.waits(a),
            "a_status": w.status(a), "b_status": w.status(b)}


@case("S98b", "Ein INAKTIVER Artikel bleibt über «Lager» abwickelbar",
      {"A": A_LAGER, "B": B_EINZEL, "C": C_1, "D": D_SCRAP, "E": E_KEINE, "F": "–"},
      {"status": "abgeschlossen", "states": {"verschrottet": 1}},
      note="Sonst wäre jedes Stück eines ausgelaufenen Artikels eine Leiche, die sich "
           "nicht einmal mehr aussondern liesse.")
def s98b(w: World):
    art, numbers = free_stock(w, serialization="unit", quantity=1)
    art.status = "inaktiv"
    w.db.flush()
    order = w.take(art, numbers, steps=[w.dispose("scrap", "Auslauf")])
    w.run_all(order)
    return {"status": w.status(order), "states": w.states(order)}
