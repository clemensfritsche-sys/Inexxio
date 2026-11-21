"""**Was niemand verifiziert, steht nicht als «von Hand» im Protokoll.**

Die Zahlung lässt die Stücke von selbst durch (``process.carry_on``). Früher trug jeder
Eintrag dabei ``verification = manual`` – das Protokoll zeigte «Von Hand bestätigt», obwohl
niemand etwas bestätigt hatte.
"""

from app.models import ProcessEvent
from tests.test_zahlung_ablauf import _sold, db  # noqa: F401 – die Szene und ihre Sitzung


def test_units_passing_a_payment_carry_no_verification(db):  # noqa: F811
    order, step, row, who = _sold(db)
    passed = db.query(ProcessEvent).filter(ProcessEvent.step_id == step.id,
                                           ProcessEvent.kind == "step").all()
    assert passed, "Mit der Zusage sind die Stücke nicht weitergezogen."
    assert all(not (e.payload or {}).get("verification") for e in passed), (
        "Ein Eintrag der Zahlung trägt eine Verifikation – niemand hat etwas bestätigt.")
