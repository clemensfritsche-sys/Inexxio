"""**Zahlung: ein Modul für Geld — beide Richtungen, drei Achsen, keine Reihenfolge.**

Die Regeln, die hier geprüft werden, sind die des Moduls «Zahlung»
(``domain/deal`` · ``services/deal``):

1. **Es bewegt keine Stücke.** Ein Durchläufer: ``Im Prozess`` → ``Im Prozess``, kein
   Ausgang, kein Ortswechsel, kein neuer Status. Genau daraus folgt, dass keine andere
   Regel im System von ihm wissen muss.
2. **Die Richtung ist eine Einstellung, kein zweites Modul.** Ein Schlüssel, eine Kachel;
   was Einnahme von Ausgabe unterscheidet, sind Wörter aus ``domain/deal.DIRECTIONS``.
3. **Forderung und Geld sind zwei Achsen.** Vorauszahlung, Anzahlung, Teilzahlung,
   Gutschrift und Erstattung sind dieselbe Mechanik in anderer Folge – **kein Modus**.
4. **``can`` ist Auskunft UND Tor**: dieselbe Tabelle zeigt die Knöpfe und weist ab.
5. **Ohne Zusage schliesst nichts ab**, und mit ``prepaid`` erst nach dem Geld.
6. **Es hängt an keiner Zeile des Beschaffungs-/Verkaufs-Belegs** – die beiden alten
   Module sollen ersatzlos löschbar sein.

Geprüft über die **echten** Dienstpfade gegen echtes PostgreSQL.
"""

import os
import pathlib
import re
from decimal import Decimal

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _db():
    """Eine Sitzung gegen echtes PostgreSQL – oder ein Skip **mit Grund**."""
    import sys
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("FIREBASE_PROJECT_ID", "test")
    try:
        from app.core.database import Base, SessionLocal, engine
        import app.main as main
        Base.metadata.create_all(engine)
        main._ensure_columns()
        return SessionLocal()
    except Exception as exc:  # pragma: no cover - reine Umgebungsfrage
        pytest.skip(f"Kein PostgreSQL erreichbar ({type(exc).__name__}: {exc}) – "
                    f"DATABASE_URL setzen, damit diese Regeln wirklich laufen.")


def _party(db, name: str, role: str = "supplier"):
    from app.models import UserProfile
    from app.services import objects as obj
    import uuid
    user = UserProfile(
        firebase_uid=f"test-{uuid.uuid4()}", email=f"{uuid.uuid4()}@example.test",
        company_name=name, role=role, object_id=obj.next_object_id(db),
    )
    db.add(user)
    db.flush()
    return user


def _article(db, name: str, *, steps: list[dict] | None = None):
    from app.models import Article
    from app.services import article_process as tpl, objects as obj
    art = Article(object_id=obj.next_object_id(db), name=name, unit="stk",
                  serialization="batch")
    db.add(art)
    db.flush()
    if steps:
        tpl.create_steps(db, art, steps)
        db.flush()
    return art


def _money_step(*, direction: str = "out", parties=(), subject: str = "Härten",
                prepaid: bool = False) -> dict:
    """Ein «Zahlung»-Modul – vier Angaben, mehr gibt es nicht."""
    return {"module_type": "zahlung",
            "config": {"direction": direction, "subject": subject,
                       "parties": [p.object_id for p in parties],
                       "prepaid": prepaid}}


def _make(db, *, quantity: int, article, steps=None):
    """Ein freigegebener Erzeugungsauftrag über diesen Artikel."""
    from app.models import ProcessStep
    from app.services import process as proc
    order = proc.release(
        db,
        lines=[{"article_object_id": article.object_id, "quantity": quantity,
                "origin": "neu", "units": []}],
        steps=steps or [], actor_id=None,
    )
    db.flush()
    rows = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
            .order_by(ProcessStep.position).all())
    return order, rows


def _stock(db, article, quantity: int) -> list[str]:
    """``quantity`` **freie** Stücke: erzeugen und einmal durchlaufen lassen.

    Der Artikel braucht dafür einen Erzeugungsprozess – «Neu» ist erst wählbar, wenn die
    Vorlage mindestens ein Modul hat. Eine Datenerfassung ohne Punkte ist der kürzeste.
    """
    from app.domain import modules
    from app.services import process as proc
    from tests.support import per_unit
    order, rows = _make(db, quantity=quantity, article=article)
    numbers = _numbers(db, order)
    for step in rows:
        while True:
            work = proc.step_work(db, order, step)
            if not work:
                break
            instance = work[0]["instance_object_id"]
            # Die Schlüssel der Erfassungspunkte kommen aus der Definition – ein
            # ausgedachter wäre ein zweiter Massstab, und der Server weist ihn zu Recht ab.
            answers = {p["key"]: True for p in modules.points_of(step.config)}
            proc.confirm_step(
                db, order=order, step_id=step.id, actor_id=None, verification="scan",
                instance_object_id=instance,
                values=per_unit(db, order=order, step=step,
                                instance_object_id=instance, values=answers),
            )
            db.flush()
    db.flush()
    return numbers


def _numbers(db, order) -> list[str]:
    """Alle Stücknummern dieses Auftrags – aus derselben Quelle wie die Oberfläche."""
    from app.models import InstanceUnit, OrderUnit
    from app.services import process as proc
    units = (db.query(InstanceUnit)
             .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
             .filter(OrderUnit.order_id == order.id)
             .order_by(InstanceUnit.id).all())
    got = proc.unit_numbers(db, units)
    return [got[u.id] for u in units]


def _confirm_all(db, order, step):
    """Bestätigen, bis nichts mehr davorsteht – nach jedem Vorgang neu gefragt."""
    from app.services import process as proc
    while True:
        work = proc.step_work(db, order, step)
        if not work:
            return
        proc.confirm_step(db, order=order, step_id=step.id, actor_id=None, values={},
                          instance_object_id=work[0]["instance_object_id"],
                          verification="scan")
        db.flush()


# ---------------------------------------------------------------------------
# §1 – es bewegt keine Stücke
# ---------------------------------------------------------------------------

def test_the_module_never_touches_a_single_unit():
    """**Ein Durchläufer: kein neuer Status, kein Ausgang, kein Ort, kein Stück.**

    Bug-Form: ein Geldmodul, das den Zustand des Stücks ändert (etwa auf «Verkauft»).
    Dann müsste jede andere Regel im System von ihm wissen – Statusliste, Bestand,
    Kettenregel, FIFO –, und für jede Kombination aus Geld und Ware gäbe es wieder einen
    eigenen Fall.
    """
    from app.domain import modules, statuses as st
    from app.models import InstanceUnit
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle (Verkauf)",
                       steps=[_money_step(direction="in", parties=[kunde],
                                          subject="Fertigung nach Zeichnung")])
        before = db.query(InstanceUnit).count()
        order, rows = _make(db, quantity=4, article=art)
        assert db.query(InstanceUnit).count() - before == 4, "Die Freigabe erzeugt sie."

        mod = modules.get("zahlung")
        assert mod.terminal is False, "Ein Geldvorgang ist kein Ausgang."
        assert mod.moves is False, "Ein Geldvorgang bewegt nichts."
        assert mod.buys is None, "Es trägt keinen Beschaffungs-Beleg."
        assert mod.status_before == st.IM_PROZESS
        assert mod.status_after == st.IM_PROZESS

        svc.apply(db, order=order, step=rows[0], action="agree",
                  payload={"party": kunde.object_id, "amount": "1200.00"})
        _confirm_all(db, order, rows[0])
        db.flush()

        units = db.query(InstanceUnit).order_by(InstanceUnit.id.desc()).limit(4).all()
        assert {u.status for u in units} == {st.FREIGEGEBEN}, (
            "Nach dem Ende steht das Stück frei wie nach jedem Durchläufer – ein "
            "Geldvorgang hat keinen eigenen Zustand am Material."
        )
        assert all(u.place_object_id is None and u.place_unit_id is None for u in units), (
            "Ein Geldvorgang hat den Ort angefasst – wo etwas liegt, sagen die "
            "Bewegen-Module, nicht das Geld."
        )
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §2 – die Richtung ist eine Einstellung
# ---------------------------------------------------------------------------

def test_one_module_two_directions_and_the_words_come_from_the_data():
    """**Ein Schlüssel, zwei Richtungen** – der Unterschied sind Wörter, keine Regel.

    Bug-Form: zwei Modultypen (wie «Beschaffen»/«Verkauf») oder ein ``if direction ==``
    im Dienst. Die erste Verzweigung ist eine Beschriftung, die zweite eine Regel, und
    ab der dritten gibt es zwei Vorgänge, die nur so tun, als wären sie einer.
    """
    from app.domain import deal as dm, modules
    from app.services import deal as svc
    db = _db()
    try:
        keys = [k for k, m in modules.MODULES.items() if isinstance(m, modules.Zahlung)]
        assert keys == ["zahlung"], f"Genau EIN Geldmodul erwartet, gefunden: {keys}"

        lieferant = _party(db, "Härterei AG")
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[
            _money_step(direction="out", parties=[lieferant], subject="Härten"),
            _money_step(direction="in", parties=[kunde], subject="Verkauf"),
        ])
        order, rows = _make(db, quantity=2, article=art)

        out = svc.embed_data(db, order=order, step=rows[0])
        inn = svc.embed_data(db, order=order, step=rows[1])
        assert out["direction"] == dm.OUT and inn["direction"] == dm.IN
        assert out["party_word"] == "Lieferant" and inn["party_word"] == "Kunde"
        # **Der Plural ist eine Angabe, keine Rechnung** – «Kunde» + «en» wäre «Kundeen».
        assert inn["party_plural"] == "Kunden"
        assert [s["label"] for s in out["stages"]] != [s["label"] for s in inn["stages"]]
        # Und die **Maschine** ist dieselbe: gleiche Schlüssel, gleiche Reihenfolge.
        assert [s["key"] for s in out["stages"]] == [s["key"] for s in inn["stages"]]
        assert out["can"] == inn["can"], "Was erlaubt ist, hängt an der Stufe, nicht an "
        "der Richtung."
    finally:
        db.rollback(); db.close()


def test_the_direction_is_frozen_on_the_deal_not_read_from_the_module():
    """**Die Richtung steht am Vorgang.** Ein laufender Auftrag ist eingefroren.

    Bug-Form: der Vorgang liest die Richtung bei jeder Anzeige aus der Konfiguration des
    Schritts. Ein späterer Umbau änderte damit **rückwirkend** die Bedeutung alter
    Vorgänge – aus einer Einnahme würde eine Ausgabe, ohne dass jemand etwas tut.
    """
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)
        assert svc.of_step(db, rows[0].id).direction == "in"

        # Jemand baut die Definition um (im Betrieb wäre es ein neuer Deploy).
        rows[0].config = {**(rows[0].config or {}), "direction": "out"}
        db.flush()

        # **Geprüft wird die ANTWORT, nicht die Spalte**: gefragt ist, was ein Mensch
        # danach zu sehen bekommt. Ein Wächter, der nur die Spalte liest, liesse genau
        # die Bug-Form durch, die zählt – einen Leser, der die Richtung neu ableitet.
        facts = svc.embed_data(db, order=order, step=rows[0])
        assert facts["direction"] == "in", (
            "Die Antwort hat die Richtung aus dem Schritt neu gelesen – damit ändert ein "
            "Umbau rückwirkend, was ein alter Vorgang bedeutet."
        )
        assert facts["party_word"] == "Kunde", (
            "Auch die Wörter folgen der eingefrorenen Richtung, nicht der heutigen "
            "Definition – sonst stünde an einer alten Einnahme plötzlich «Lieferant»."
        )
        assert svc.of_step(db, rows[0].id).direction == "in"
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §3 – zwei Achsen, keine Reihenfolge
# ---------------------------------------------------------------------------

def test_claim_and_money_are_two_axes_so_a_part_payment_needs_no_mode():
    """**Anzahlung, Teilzahlung, Gutschrift, Erstattung – alles dieselbe Mechanik.**

    Bug-Form: eine einzige Geld-Zahl am Vorgang. Dann ist «zugesagt 1200, berechnet 400,
    bezahlt 400» nicht mehr darstellbar, und eine Anzahlung braucht einen eigenen Modus.
    """
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)
        step = rows[0]
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": kunde.object_id, "amount": "1200.00",
                           "due_days": 30})

        # Anzahlung: eine Forderung über einen Teil – **kein Schalter**.
        svc.apply(db, order=order, step=step, action="charge",
                  payload={"amount": "400.00"})
        money = svc.balance_of(db, svc.of_step(db, step.id))
        assert money.charged == Decimal("400.00")
        assert money.open == Decimal("400.00")
        assert money.uncharged == Decimal("800.00"), (
            "«zugesagt − berechnet» ist die Vorgabe der nächsten Rechnung – ohne die "
            "zweite Achse gäbe es diese Zahl gar nicht."
        )

        svc.apply(db, order=order, step=step, action="pay", payload={})  # Vorgabe: offen
        money = svc.balance_of(db, svc.of_step(db, step.id))
        assert money.paid == Decimal("400.00") and money.open == Decimal("0.00")

        # Schlussrechnung ohne Betrag → die Vorgabe ist der Rest.
        svc.apply(db, order=order, step=step, action="charge", payload={})
        money = svc.balance_of(db, svc.of_step(db, step.id))
        assert money.charged == Decimal("1200.00") and money.uncharged == Decimal("0.00")

        # Gutschrift = **negative Forderung**, Erstattung = **negative Zahlung**.
        svc.apply(db, order=order, step=step, action="charge",
                  payload={"amount": "-200.00"})
        svc.apply(db, order=order, step=step, action="pay", payload={"amount": "-50.00"})
        money = svc.balance_of(db, svc.of_step(db, step.id))
        assert money.charged == Decimal("1000.00"), "Eine Gutschrift ist eine negative Rechnung."
        assert money.paid == Decimal("350.00"), "Eine Erstattung ist eine negative Zahlung."
        assert money.open == Decimal("650.00")
    finally:
        db.rollback(); db.close()


def test_a_wrong_line_can_be_taken_back_and_stays_readable():
    """**Ein Tippfehler ist keine Sackgasse** – und die Zeile bleibt lesbar.

    Bug-Form: keine Gegenhandlung. Dann wäre eine versehentlich gebuchte 10 000er-Zahlung
    für immer im offenen Betrag, und der einzige Ausweg hiesse «Datenbank anfassen».
    """
    from app.models import DealEntry
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)
        step = rows[0]
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": kunde.object_id, "amount": "100.00"})
        svc.apply(db, order=order, step=step, action="pay", payload={"amount": "10000.00"})
        row = svc.of_step(db, step.id)
        entry = db.query(DealEntry).filter(DealEntry.deal_id == row.id).one()

        svc.apply(db, order=order, step=step, action="void", payload={"entry": entry.id})
        assert svc.balance_of(db, row).paid == Decimal("0.00")
        db.refresh(entry)
        assert entry.is_active is False and entry.amount == Decimal("10000.00"), (
            "Die Zeile wurde hart gelöscht – was einmal gebucht war, muss lesbar bleiben."
        )
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §4 – can ist Auskunft UND Tor
# ---------------------------------------------------------------------------

def test_can_is_the_gate_not_only_a_hint():
    """**Dieselbe Tabelle zeigt die Knöpfe und weist ab.**

    Bug-Form: ``can`` ist nur eine Anzeige-Information, und ``apply`` prüft selbst (oder
    gar nicht). Dann liefen Knopf und Tür beim nächsten Verb auseinander – die Oberfläche
    böte etwas an, das der Server ablehnt, oder ein Anwender fände einen Weg um die Regel.
    """
    from fastapi import HTTPException
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)
        step = rows[0]

        facts = svc.embed_data(db, order=order, step=step)
        assert "charge" not in facts["can"], "Vor der Zusage gibt es nichts zu fordern."
        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=order, step=step, action="charge",
                      payload={"amount": "10.00"})
        assert e.value.status_code == 409, (
            "Der Dienst hat ein Verb angenommen, das `can` nicht führt – dann ist `can` "
            "nur ein Hinweis und keine Regel."
        )

        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": kunde.object_id, "amount": "100.00"})
        facts = svc.embed_data(db, order=order, step=step)
        assert {"charge", "pay", "revoke"} <= set(facts["can"])
        assert "agree" not in facts["can"], "Zweimal zusagen gibt es nicht."
    finally:
        db.rollback(); db.close()


def test_money_still_flows_after_a_cancellation():
    """**Eine Anzahlung muss erstattet werden können.**

    Bug-Form: Geld hängt an der Stufe. Dann wäre nach einem Storno keine Erstattung mehr
    buchbar, und der Betrag stünde für immer als «bezahlt» da.
    """
    from app.domain import deal as dm
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)
        step = rows[0]
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": kunde.object_id, "amount": "500.00"})
        svc.apply(db, order=order, step=step, action="charge", payload={})
        svc.apply(db, order=order, step=step, action="pay", payload={"amount": "500.00"})
        svc.apply(db, order=order, step=step, action="revoke", payload={})

        facts = svc.embed_data(db, order=order, step=step)
        assert facts["stage"] == dm.CANCELLED
        assert "pay" in facts["can"], "Nach einem Storno ist die Erstattung der Normalfall."
        # **Der Weg bleibt gegangen**: ein Storno macht die Zusage nicht ungeschehen.
        assert facts["stages"][0]["done"] is True
        assert not any(s["active"] for s in facts["stages"])

        svc.apply(db, order=order, step=step, action="pay", payload={"amount": "-500.00"})
        assert svc.balance_of(db, svc.of_step(db, step.id)).paid == Decimal("0.00")
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §5 – ohne Zusage schliesst nichts ab; mit prepaid erst nach dem Geld
# ---------------------------------------------------------------------------

def test_nothing_closes_before_the_deal_is_agreed():
    """**Ohne Zusage steht kein Betrag fest** – es gibt nichts abzuschliessen.

    Bug-Form: ``confirm_step`` läuft durch, obwohl niemand etwas zugesagt hat. Der
    Auftrag wäre fertig, und der Vorgang stünde für immer auf «Angebot».
    """
    from fastapi import HTTPException
    from app.services import process as proc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=2, article=art)
        work = proc.step_work(db, order, rows[0])
        with pytest.raises(HTTPException) as e:
            proc.confirm_step(db, order=order, step_id=rows[0].id, actor_id=None,
                              values={}, verification="scan",
                              instance_object_id=work[0]["instance_object_id"])
        assert e.value.status_code == 409
        assert "zugesagt" in str(e.value.detail)
    finally:
        db.rollback(); db.close()


def test_prepaid_holds_the_module_until_the_money_is_there():
    """**Vorauszahlung ist kein Modus, sondern eine Sperre am Abschluss.**

    Bug-Form: ``prepaid`` ist nur eine Anzeige, oder es wird über den offenen Betrag
    geprüft. Der offene Betrag ist direkt nach der Zusage **null** – weil noch nichts
    gefordert wurde –, und das hiesse «bezahlt», obwohl kein Rappen geflossen ist.
    """
    from fastapi import HTTPException
    from app.services import deal as svc, process as proc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle",
                       steps=[_money_step(direction="in", parties=[kunde], prepaid=True)])
        order, rows = _make(db, quantity=2, article=art)
        step = rows[0]
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": kunde.object_id, "amount": "300.00"})
        db.flush()

        money = svc.balance_of(db, svc.of_step(db, step.id))
        assert money.open == Decimal("0.00") and money.settled is False, (
            "«offen = 0» heisst hier «nichts gefordert», nicht «bezahlt»."
        )
        work = proc.step_work(db, order, step)
        with pytest.raises(HTTPException) as e:
            proc.confirm_step(db, order=order, step_id=step.id, actor_id=None, values={},
                              verification="scan",
                              instance_object_id=work[0]["instance_object_id"])
        assert e.value.status_code == 409 and "Zahlungseingang" in str(e.value.detail)

        svc.apply(db, order=order, step=step, action="charge", payload={})
        svc.apply(db, order=order, step=step, action="pay", payload={})
        db.flush()
        assert svc.balance_of(db, svc.of_step(db, step.id)).settled is True
        _confirm_all(db, order, step)          # jetzt läuft es durch
        assert svc.of_step(db, step.id).stage == "done"
    finally:
        db.rollback(); db.close()


def test_the_deal_closes_only_when_nothing_waits_anymore():
    """**Teilabschluss braucht keine eigene Regel** – ``confirm_step`` ist einer.

    Bug-Form: der Vorgang springt beim ersten bestätigten Stück auf «abgeschlossen».
    Dann stünde ein Vorgang als erledigt da, während die Hälfte der Ware noch wartet.
    """
    from app.services import deal as svc, process as proc
    db = _db()
    try:
        lieferant = _party(db, "Härterei AG")
        # **Zwei Instanzen** vor dem Modul: zwei Erzeugungsaufträge legen sie an, ein
        # dritter greift beide ab Lager. Ein Auftrag hat genau EINEN Erzeugungsprozess –
        # zwei «Neu»-Zeilen wären ein anderer Fehler, nicht dieser Fall.
        from app.models import ProcessStep
        art = _article(db, "Welle", steps=[{
            "module_type": "datenerfassung",
            "config": {"points": [{"label": "Sichtprüfung", "type": "bool"}]},
        }])
        numbers: list[str] = []
        for qty in (2, 3):
            numbers += _stock(db, art, qty)
        order = proc.release(
            db,
            lines=[{"article_object_id": art.object_id, "quantity": len(numbers),
                    "origin": "lager",
                    "units": [{"number": n, "from_order": None} for n in numbers]}],
            steps=[_money_step(direction="out", parties=[lieferant])], actor_id=None,
        )
        db.flush()
        step = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
                .order_by(ProcessStep.position).first())
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": lieferant.object_id, "amount": "90.00"})
        work = proc.step_work(db, order, step)
        assert len(work) == 2, "Zwei Instanzen warten."

        proc.confirm_step(db, order=order, step_id=step.id, actor_id=None, values={},
                          instance_object_id=work[0]["instance_object_id"],
                          verification="scan")
        db.flush()
        assert svc.of_step(db, step.id).stage == "agreed", (
            "Der Vorgang ist abgeschlossen, obwohl noch Stücke davorstehen."
        )
        _confirm_all(db, order, step)
        assert svc.of_step(db, step.id).stage == "done"
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §6 – die Gegenpartei
# ---------------------------------------------------------------------------

def test_an_allowed_list_is_a_rule_and_an_empty_one_means_free():
    """**Leer heisst frei, aber nicht «irgendwer».**

    Bug-Form (1): die Liste wird nicht geprüft – dann ist die Freigabe im Editor eine
    Dekoration. Bug-Form (2): eine leere Liste heisst «niemand» – dann liesse sich ein
    Modul, das die Wahl bewusst offenlässt, überhaupt nicht ausführen.
    """
    from fastapi import HTTPException
    from app.services import deal as svc
    db = _db()
    try:
        a = _party(db, "Härterei A")
        b = _party(db, "Härterei B")
        art = _article(db, "Welle", steps=[
            _money_step(direction="out", parties=[a]),
            _money_step(direction="out", parties=[], subject="frei"),
        ])
        order, rows = _make(db, quantity=1, article=art)

        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=order, step=rows[0], action="agree",
                      payload={"party": b.object_id, "amount": "10.00"})
        assert e.value.status_code == 400 and "nicht zugelassen" in str(e.value.detail)
        svc.apply(db, order=order, step=rows[0], action="agree",
                  payload={"party": a.object_id, "amount": "10.00"})

        # Ohne Liste ist jeder erlaubt – aber es muss ihn geben.
        svc.apply(db, order=order, step=rows[1], action="quote",
                  payload={"party": b.object_id})
        with pytest.raises(HTTPException):
            svc.apply(db, order=order, step=rows[1], action="quote",
                      payload={"party": 999999999})
    finally:
        db.rollback(); db.close()


def test_only_sent_fields_change_anything():
    """**Wer den Betrag ändert, verliert nicht die Notiz.**

    Bug-Form: der Dienst schreibt jedes Feld der Nutzlast, auch die nicht gesendeten.
    Dann löschte jeder Aufruf alles, was er nicht ausdrücklich wiederholt – und das fällt
    erst auf, wenn jemand die Notiz sucht.
    """
    from app.services import deal as svc
    db = _db()
    try:
        lieferant = _party(db, "Härterei AG")
        art = _article(db, "Welle",
                       steps=[_money_step(direction="out", parties=[lieferant])])
        order, rows = _make(db, quantity=1, article=art)
        step = rows[0]
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": lieferant.object_id, "note": "Hebebühne nötig",
                           "due_days": 14})
        svc.apply(db, order=order, step=step, action="quote", payload={"amount": "42.50"})
        row = svc.of_step(db, step.id)
        assert row.amount == Decimal("42.50")
        assert row.note == "Hebebühne nötig", "Eine nicht gesendete Angabe wurde geleert."
        assert row.due_days == 14
        assert row.party_id == lieferant.object_id
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §7 – die Nummer, und die Unabhängigkeit
# ---------------------------------------------------------------------------

def test_we_number_our_own_invoices_and_never_theirs():
    """**Wer nummeriert, sagt die Richtung.**

    Bug-Form: das System erfindet auch bei einer **Ausgabe** eine Nummer. Dann stünde auf
    einer Lieferantenrechnung eine Nummer, die es beim Lieferanten nie gab – eine
    Behauptung über ein fremdes Dokument.
    """
    from app.models import DealEntry
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        lieferant = _party(db, "Härterei AG")
        art = _article(db, "Welle", steps=[
            _money_step(direction="in", parties=[kunde], subject="Verkauf"),
            _money_step(direction="out", parties=[lieferant], subject="Härten"),
        ])
        order, rows = _make(db, quantity=1, article=art)
        for step, party in ((rows[0], kunde), (rows[1], lieferant)):
            svc.apply(db, order=order, step=step, action="agree",
                      payload={"party": party.object_id, "amount": "100.00"})
        # **Die fremde Rechnung ZUERST** – genau hier lag der Fehler: sie verbrauchte die
        # Zählung, und unsere erste eigene hiess «…-2». Eine Nummernserie mit Lücken ist
        # buchhalterisch keine. Gemessen beim Durchspielen der ganzen Szene, nicht gelesen.
        svc.apply(db, order=order, step=rows[1], action="charge", payload={"amount": "10"})
        svc.apply(db, order=order, step=rows[0], action="charge", payload={"amount": "60"})
        svc.apply(db, order=order, step=rows[0], action="charge", payload={"amount": "40"})

        ours = db.query(DealEntry).join(
            svc.Deal, DealEntry.deal_id == svc.Deal.id).filter(
            svc.Deal.step_id == rows[0].id).order_by(DealEntry.id).all()
        assert [e.reference for e in ours] == [str(order.object_id),
                                               f"{order.object_id}-2"], (
            "Unsere Rechnungsnummern folgen der Auftragsnummer – die erste ohne Zusatz."
        )
        theirs = db.query(DealEntry).join(
            svc.Deal, DealEntry.deal_id == svc.Deal.id).filter(
            svc.Deal.step_id == rows[1].id).one()
        assert theirs.reference is None, (
            "Bei einer Ausgabe hat das System eine Nummer erfunden – die vergibt die "
            "Gegenpartei, und eine erfundene wäre eine Behauptung."
        )
    finally:
        db.rollback(); db.close()


def test_the_money_module_shares_no_line_with_the_purchase_document():
    """►►► **Die Unabhängigkeit ist die Anforderung, also wird sie geprüft.** ◄◄◄

    «Beschaffen» und «Verkauf» sollen eines Tages ersatzlos gelöscht werden können. Das
    geht genau dann, wenn kein Baustein dieses Moduls sie liest.

    Bug-Form: irgendwo ein ``from ..domain import procurement`` oder ein Griff nach
    ``services/purchase``. Dann fällt beim Löschen der beiden alten Module dieses hier
    mit – und der Fehler zeigt sich erst dabei, also im denkbar ungünstigsten Moment.
    """
    forbidden = ("procurement", "purchase", "invoices", "payments", "money",
                 "stripe_pay")
    for name in ("app/domain/deal.py", "app/services/deal.py", "app/schemas/deal.py",
                 "app/models/deal.py"):
        code = (BACKEND / name).read_text(encoding="utf-8")
        # Nur echte Importe, nicht die Prosa: die Docstrings nennen die alten Module
        # ausdrücklich, und genau das sollen sie auch.
        imports = "\n".join(re.findall(r"^\s*(?:from|import)\s+.*$", code, re.M))
        for word in forbidden:
            assert word not in imports, (
                f"{name} importiert «{word}» – damit hängt das Geldmodul an der alten "
                f"Maschine, und «Beschaffen»/«Verkauf» sind nicht mehr löschbar."
            )
