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


def _staff(db):
    """Ein Mitarbeiter – wer ohnehin ins ERP darf, sieht alles."""
    return _party(db, "Wir AG", role="employee")


def _agree(db, *, order, step, party, amount: str, days: int | None = None,
           staff=None):
    """Der Regelweg bis zur Zusage: **anfragen → offerieren → Zuschlag**.

    Ein Geldvorgang ist kein Formular, das eine Seite ausfüllt – darum gibt es hier
    keine Abkürzung. Genau diese drei Schritte macht auch die Oberfläche.
    """
    from app.services import deal as svc
    actor = staff or _staff(db)
    svc.apply(db, order=order, step=step, action="ask",
              payload={"parties": [party.object_id]}, actor=actor)
    svc.apply(db, order=order, step=step, action="quote",
              payload={"party": party.object_id, "amount": amount,
                       "payment_days": days}, actor=actor)
    svc.apply(db, order=order, step=step, action="agree",
              payload={"party": party.object_id}, actor=actor)
    db.flush()


def _confirm_money(db, order, step):
    """Ein «Zahlung»-Modul abschliessen – **ohne Scan und ohne Instanz**.

    Genau das tut die Oberfläche: ein Knopf, ein Vorgang. Ohne Instanz bewegt
    ``confirm_step`` alles, was davorsteht.
    """
    from app.services import process as proc
    proc.confirm_step(db, order=order, step_id=step.id, actor_id=None, values={})
    db.flush()


# ---------------------------------------------------------------------------
# §1 – es bewegt keine Stücke, und es scannt nicht
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

        _agree(db, order=order, step=rows[0], party=kunde, amount="1200.00")
        _confirm_money(db, order, rows[0])

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


def test_a_money_module_is_confirmed_without_a_scan():
    """►►► **Kein Scan – und das ist eine Eigenschaft, keine Ausnahme.** ◄◄◄

    Ein Scan beantwortet «habe ich das richtige physische Ding vor mir». Dieses Modul tut
    mit dem Stück gar nichts: es stellt etwas in Rechnung. Ein Etikett zu scannen, um eine
    Rechnung zu stellen, ist eine Geste ohne Aussage.

    Bug-Form: ``requires_verification`` bleibt geerbt ``True``. Dann verlangt
    ``confirm_step`` eine Instanz und eine Verifikationsart – und der Vorgang liesse sich
    nur abschliessen, indem jemand ein Etikett scannt, das mit der Rechnung nichts zu tun
    hat. **Und es wäre ein Vorgang JE INSTANZ**: bei drei Kisten drei Bestätigungen für
    einen Auftrag, der einmal erledigt wird.
    """
    from app.domain import modules
    from app.services import deal as svc, process as proc
    db = _db()
    try:
        assert modules.get("zahlung").requires_verification is False

        lieferant = _party(db, "Härterei AG")
        art = _article(db, "Welle",
                       steps=[_money_step(direction="out", parties=[lieferant])])
        # **Zwei Instanzen** vor dem Modul – ein Auftrag, EINE Bestätigung.
        from app.models import ProcessStep
        src = _article(db, "Welle (Vorlauf)", steps=[{
            "module_type": "datenerfassung",
            "config": {"points": [{"label": "Sichtprüfung", "type": "bool"}]},
        }])
        numbers = _stock(db, src, 2) + _stock(db, src, 3)
        order = proc.release(
            db,
            lines=[{"article_object_id": src.object_id, "quantity": len(numbers),
                    "origin": "lager",
                    "units": [{"number": n, "from_order": None} for n in numbers]}],
            steps=[_money_step(direction="out", parties=[lieferant])], actor_id=None,
        )
        db.flush()
        step = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
                .order_by(ProcessStep.position).first())
        assert len(proc.step_work(db, order, step)) == 2, "Zwei Instanzen warten."

        _agree(db, order=order, step=step, party=lieferant, amount="90.00")
        # **Ohne Instanz und ohne Verifikation** – und es geht durch.
        proc.confirm_step(db, order=order, step_id=step.id, actor_id=None, values={})
        db.flush()
        assert not proc.step_work(db, order, step), (
            "Ein Vorgang ohne Instanz bewegt alles, was davorsteht – sonst bräuchte ein "
            "Auftrag so viele Bestätigungen, wie Kisten davorstehen."
        )
        assert svc.of_step(db, step.id).stage == "done"
        assert art is not None
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
        # **Wie man zugeht, unterscheidet sich – WAS man tut, nicht.**
        assert out["ask_verb"] == "Anfragen" and inn["ask_verb"] == "Anbieten"
        assert (out["stages"][0]["verb"] == inn["stages"][0]["verb"]
                == "Auftrag bestätigen"), (
            "Der Zuschlag heisst in beiden Richtungen gleich – zwei Wörter für dieselbe "
            "Handlung wären eines zu viel."
        )
        assert [s["key"] for s in out["stages"]] == [s["key"] for s in inn["stages"]]
    finally:
        db.rollback(); db.close()


def test_there_are_two_stages_and_done_is_not_one_of_them():
    """►►► **«Abgeschlossen» ist ein Zustand, keine Stufe.** ◄◄◄

    Unumkehrbar sind zwei Dinge: nichts zugesagt · zugesagt. «Erledigt» und «Storniert»
    sind **Ausgänge** – man kommt dort an, statt hindurchzugehen.

    Bug-Form: «Abgeschlossen» steht als dritte Stufe in der Kette. Dann liest sich ein
    Zustand wie ein Schritt, und der Geld-Teil – der eigentlich dort hingehört – hängt
    darunter als loser Knopfstreifen (genau die gemeldete Verwirrung).
    """
    from app.domain import deal as dm
    from app.services import deal as svc
    db = _db()
    try:
        assert dm.STAGES == (dm.OFFER, dm.AGREED), (
            f"Zwei Stufen erwartet, gefunden: {dm.STAGES}"
        )
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)
        facts = svc.embed_data(db, order=order, step=rows[0])
        assert len(facts["stages"]) == 2
        assert [s["label"] for s in facts["stages"]] == ["Angebot", "Auftrag"]

        _agree(db, order=order, step=rows[0], party=kunde, amount="10.00")
        _confirm_money(db, order, rows[0])
        facts = svc.embed_data(db, order=order, step=rows[0])
        assert facts["stage"] == dm.DONE
        assert all(s["done"] for s in facts["stages"]), "Beide Stufen sind gegangen."
        assert not any(s["active"] for s in facts["stages"])
        # **Der Zustand braucht trotzdem ein Wort** – sonst erfindet es die Oberfläche.
        assert facts["stage_label"] == "Erledigt"
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
        assert facts["party_word"] == "Kunde"
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §3 – was gehandelt wird, sagt der Prozess
# ---------------------------------------------------------------------------

def test_what_is_traded_is_derived_and_the_specification_travels():
    """►►► **Kein Artikelfeld – die Zeilen sind der Prozess.** ◄◄◄

    Die Einzelinstanzen des Auftrags tragen ihren Artikel, der Artikel seine
    Spezifikation. Beides reist mit, damit die Gegenpartei weiss, worum es geht.

    Bug-Form (1): ein getipptes Artikelfeld – die zweite Aussage über dieselbe Sache, und
    die getippte gewinnt auch dann, wenn sie falsch ist. Bug-Form (2): die Spezifikation
    reist nicht mit – dann steht auf dem Beleg ein Betrag und sonst nichts, und der
    Lieferant weiss nicht, was er härten soll.
    """
    from app.models import Article
    from app.services import deal as svc
    db = _db()
    try:
        lieferant = _party(db, "Härterei AG")
        art = _article(db, "Welle 40x200",
                       steps=[_money_step(direction="out", parties=[lieferant])])
        db.query(Article).filter(Article.id == art.id).update(
            {"material": "1.4301", "surface": "geschliffen"})
        db.flush()
        order, rows = _make(db, quantity=6, article=art)

        facts = svc.embed_data(db, order=order, step=rows[0])
        assert len(facts["lines"]) == 1
        line = facts["lines"][0]
        assert line["quantity"] == 6 and line["article_name"] == "Welle 40x200"
        assert line["article_object_id"] == art.object_id
        values = {f["label"]: f["value"] for f in line["spec"]}
        assert values.get("Werkstoff") == "1.4301", (
            "Die Spezifikation reist nicht mit – der Lieferant sieht einen Betrag und "
            "sonst nichts."
        )
        # **Der Satz ist FREIWILLIG** (#796): was gehandelt wird, sagen die Zeilen.
        cfg = rows[0].config or {}
        assert cfg.get("subject") == "Härten"
        from app.domain import modules
        assert modules.get("zahlung").clean_config(
            {"direction": "in", "parties": []})["subject"] == "", (
            "Ohne Satz muss das Modul anlegbar sein – ein Pflichtfeld, das oft nichts "
            "aufzunehmen hat, lädt zu einer Eingabe ein, die niemand liest."
        )
    finally:
        db.rollback(); db.close()


def test_the_lines_freeze_with_the_agreement():
    """**Was zugesagt wurde, ändert sich nicht mehr** – auch nicht, wenn der Auftrag
    später Stücke verliert.

    Bug-Form: die Zeilen werden immer neu abgeleitet. Dann steht auf einem bestätigten
    Auftrag über 6 Wellen plötzlich «4», weil eine Abweichung zwei herausgenommen hat –
    und der Lieferant hat etwas anderes zugesagt, als da steht.
    """
    from app.services import deal as svc
    db = _db()
    try:
        lieferant = _party(db, "Härterei AG")
        art = _article(db, "Welle",
                       steps=[_money_step(direction="out", parties=[lieferant])])
        order, rows = _make(db, quantity=6, article=art)
        _agree(db, order=order, step=rows[0], party=lieferant, amount="180.00")

        row = svc.of_step(db, rows[0].id)
        assert row.agreed_lines and row.agreed_lines[0]["quantity"] == 6

        # Ein Stück verlässt den Auftrag (wie es eine Abweichung täte).
        from app.models import OrderUnit
        from datetime import datetime, timezone
        unit = (db.query(OrderUnit)
                .filter(OrderUnit.order_id == order.id,
                        OrderUnit.released_at.is_(None)).first())
        unit.released_at = datetime.now(timezone.utc)
        db.flush()

        assert svc.lines_of(db, order, row)[0]["quantity"] == 6, (
            "Die Zeilen haben nachgezogen – damit steht auf dem Beleg etwas anderes, "
            "als zugesagt wurde."
        )
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §4 – der Vorgang hat zwei Parteien
# ---------------------------------------------------------------------------

def test_a_deal_is_asked_quoted_and_awarded():
    """►►► **Ein Geldvorgang ist kein Formular, das eine Seite ausfüllt.** ◄◄◄

    Wir fragen an bzw. bieten an, die Gegenpartei nennt ihren Preis, wir geben den
    Zuschlag. **Eine Liste, auch wenn fast immer einer drinsteht** – wer vergleichen will,
    fragt drei, und der Vergleich ist damit kein zweiter Mechanismus.

    Bug-Form: ``agree`` nimmt Gegenpartei und Betrag direkt entgegen. Dann gibt es keinen
    Angebotsspiegel, keine zweite Partei und nichts zu vergleichen – genau der Rückschritt
    gegenüber dem Beschaffungs-Beleg, der gemeldet wurde.
    """
    from app.domain import deal as dm
    from app.services import deal as svc
    db = _db()
    try:
        a, b = _party(db, "Härterei A"), _party(db, "Härterei B")
        staff = _staff(db)
        art = _article(db, "Welle",
                       steps=[_money_step(direction="out", parties=[a, b])])
        order, rows = _make(db, quantity=2, article=art)
        step = rows[0]

        # **Ohne Angabe: alle zugelassenen.**
        svc.apply(db, order=order, step=step, action="ask", payload={}, actor=staff)
        facts = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert {q["party_object_id"] for q in facts["quotes"]} == {a.object_id, b.object_id}
        assert all(q["state"] == dm.ASKED for q in facts["quotes"])

        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": a.object_id, "amount": "180.00", "lead_days": 5},
                  actor=staff)
        svc.apply(db, order=order, step=step, action="decline",
                  payload={"party": b.object_id}, actor=staff)
        facts = svc.embed_data(db, order=order, step=step, viewer=staff)
        got = {q["party_object_id"]: q for q in facts["quotes"]}
        assert got[a.object_id]["state"] == dm.QUOTED
        assert got[a.object_id]["amount"] == "180.00"
        assert got[b.object_id]["state"] == dm.DECLINED

        # **Der Zuschlag nimmt den Betrag aus der gewählten Zeile.**
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": a.object_id}, actor=staff)
        row = svc.of_step(db, step.id)
        assert row.stage == dm.AGREED and row.party_id == a.object_id
        assert row.amount == Decimal("180.00")
        facts = svc.embed_data(db, order=order, step=step, viewer=staff)
        chosen = [q for q in facts["quotes"] if q["state"] == dm.CHOSEN]
        assert [q["party_object_id"] for q in chosen] == [a.object_id], (
            "«gewählt» entsteht nicht durch Tippen, sondern dadurch, dass bei dieser "
            "Zeile zugesagt wurde."
        )
    finally:
        db.rollback(); db.close()


def test_a_counterparty_sees_only_its_own_line_and_no_money():
    """►►► **Fremde Preise sind kein Nebeneffekt einer Ansicht.** ◄◄◄

    Eine Gegenpartei bekommt einen eigenen, sehr engen Zugang: **ihre** Angebotszeile –
    keine fremde, und keine Zahl über Forderung und Geld. Gefiltert wird beim **Aufbau
    der Antwort**, nicht in der Oberfläche.

    Bug-Form: der Filter steht in der Oberfläche (oder gar nicht). Dann liest ein
    angefragter Lieferant den Preis seines Konkurrenten – und was der Kunde uns schuldet.
    """
    from app.services import deal as svc
    db = _db()
    try:
        a, b = _party(db, "Härterei A"), _party(db, "Härterei B")
        staff = _staff(db)
        art = _article(db, "Welle",
                       steps=[_money_step(direction="out", parties=[a, b])])
        order, rows = _make(db, quantity=2, article=art)
        step = rows[0]
        svc.apply(db, order=order, step=step, action="ask", payload={}, actor=staff)
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": b.object_id, "amount": "999.00"}, actor=staff)

        seen = svc.embed_data(db, order=order, step=step, viewer=a)
        assert [q["party_object_id"] for q in seen["quotes"]] == [a.object_id], (
            "Eine Gegenpartei sieht eine fremde Angebotszeile."
        )
        assert "999.00" not in str(seen), "Der fremde Preis steckt noch in der Antwort."
        assert seen["open"] is None and seen["charged"] is None, (
            "Forderung und Geld gehen einen angefragten Dritten nichts an."
        )
        assert seen["entries"] == []

        # **Was sie TUN darf, sagt dieselbe Tabelle.**
        assert set(seen["can"]) == {"quote", "decline"}
        # **Und Personal sieht unverändert alles** – wer ohnehin ins ERP darf, braucht
        # keine verengte Sicht.
        full = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert len(full["quotes"]) == 2 and full["open"] is not None
        assert svc.mine(db, staff) is None, (
            "Ein Mitarbeiter bekäme eine verengte Sicht – er arbeitet im ERP und sieht "
            "dort den ganzen Auftrag."
        )
    finally:
        db.rollback(); db.close()


def test_a_counterparty_may_only_touch_its_own_line():
    """**Wer eintragen darf, entscheidet nicht die Nutzlast.**

    Bug-Form: ``_target`` liest ``party`` aus der Nutzlast. Dann trägt ein Lieferant den
    Preis seines Konkurrenten ein – oder überschreibt ihn.
    """
    from fastapi import HTTPException
    from app.services import deal as svc
    db = _db()
    try:
        a, b = _party(db, "Härterei A"), _party(db, "Härterei B")
        staff = _staff(db)
        art = _article(db, "Welle",
                       steps=[_money_step(direction="out", parties=[a, b])])
        order, rows = _make(db, quantity=2, article=art)
        step = rows[0]
        svc.apply(db, order=order, step=step, action="ask", payload={}, actor=staff)

        # a schickt die Nummer von b mit – gelesen wird trotzdem a.
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": b.object_id, "amount": "1.00"}, actor=a)
        got = {q["party_object_id"]: q
               for q in svc.embed_data(db, order=order, step=step, viewer=staff)["quotes"]}
        assert got[a.object_id]["amount"] == "1.00", "Die eigene Zeile wurde nicht getroffen."
        assert got[b.object_id]["amount"] is None, (
            "Eine Gegenpartei hat die Zeile einer anderen getroffen – die Nutzlast hat "
            "entschieden statt der angemeldete Benutzer."
        )
        # Und der Zuschlag gehört uns.
        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=order, step=step, action="agree",
                      payload={"party": a.object_id}, actor=a)
        assert e.value.status_code == 409
    finally:
        db.rollback(); db.close()


def test_one_allowed_party_is_not_a_question():
    """**Steht in der Definition genau eine Gegenpartei, gibt es nichts zu wählen** (#793).

    Gemeldet: «ich habe bei der Definition definiert, dass ich es an einen User verkaufen
    möchte. Jetzt fragt er mich nach dem Kunden.»

    Bug-Form: ``ask`` verlangt immer eine Nutzlast. Dann fragt die Ausführungsstelle nach
    einer Angabe, die längst getroffen ist – und die Definition war eine Dekoration.
    """
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        staff = _staff(db)
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)

        svc.apply(db, order=order, step=rows[0], action="ask", payload={}, actor=staff)
        facts = svc.embed_data(db, order=order, step=rows[0], viewer=staff)
        assert [q["party_object_id"] for q in facts["quotes"]] == [kunde.object_id], (
            "Ohne Angabe wurden nicht die zugelassenen Gegenparteien angefragt."
        )
        assert facts["allowed"][0]["object_id"] == kunde.object_id
    finally:
        db.rollback(); db.close()


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
        a, b = _party(db, "Härterei A"), _party(db, "Härterei B")
        staff = _staff(db)
        art = _article(db, "Welle", steps=[
            _money_step(direction="out", parties=[a]),
            _money_step(direction="out", parties=[], subject="frei"),
        ])
        order, rows = _make(db, quantity=1, article=art)

        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=order, step=rows[0], action="ask",
                      payload={"parties": [b.object_id]}, actor=staff)
        assert e.value.status_code == 400 and "nicht zugelassen" in str(e.value.detail)

        # Ohne Liste ist jeder erlaubt – aber es muss ihn geben, und es muss dastehen, wen.
        svc.apply(db, order=order, step=rows[1], action="ask",
                  payload={"parties": [b.object_id]}, actor=staff)
        with pytest.raises(HTTPException):
            svc.apply(db, order=order, step=rows[1], action="ask",
                      payload={"parties": [999999999]}, actor=staff)
        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=order, step=rows[1], action="ask", payload={}, actor=staff)
        assert "nichts anzufragen" in str(e.value.detail)
    finally:
        db.rollback(); db.close()


def test_a_quote_line_is_rebuilt_never_mutated():
    """**Eine Angebotszeile wird durch NEUBAU geändert, nie an Ort.**

    Bug-Form: der geladene JSONB-Wert wird mutiert. Dann sind geladener und aktueller Wert
    gleich, die Spalte fällt aus dem ``UPDATE``, und die Offerte ist stillschweigend weg –
    dieselbe Falle wie ``purchase._write`` und ``units._runs``.
    """
    from app.services import deal as svc
    db = _db()
    try:
        a = _party(db, "Härterei A")
        staff = _staff(db)
        art = _article(db, "Welle", steps=[_money_step(direction="out", parties=[a])])
        order, rows = _make(db, quantity=1, article=art)
        svc.apply(db, order=order, step=rows[0], action="ask", payload={}, actor=staff)
        svc.apply(db, order=order, step=rows[0], action="quote",
                  payload={"party": a.object_id, "amount": "42.50"}, actor=staff)
        db.commit()
        db.expire_all()
        row = svc.of_step(db, rows[0].id)
        assert row.quotes[0]["amount"] == "42.50", (
            "Die Offerte hat den Neustart nicht überlebt – der JSONB-Wert wurde an Ort "
            "mutiert und fiel aus dem UPDATE."
        )
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §5 – zwei Achsen, keine Reihenfolge
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
        _agree(db, order=order, step=step, party=kunde, amount="1200.00", days=30)

        svc.apply(db, order=order, step=step, action="charge",
                  payload={"amount": "400.00"})
        money = svc.balance_of(db, svc.of_step(db, step.id))
        assert money.charged == Decimal("400.00")
        assert money.open == Decimal("400.00")
        assert money.uncharged == Decimal("800.00"), (
            "«zugesagt − berechnet» ist die Vorgabe der nächsten Rechnung – ohne die "
            "zweite Achse gäbe es diese Zahl gar nicht."
        )

        svc.apply(db, order=order, step=step, action="pay", payload={})
        money = svc.balance_of(db, svc.of_step(db, step.id))
        assert money.paid == Decimal("400.00") and money.open == Decimal("0.00")

        svc.apply(db, order=order, step=step, action="charge", payload={})
        money = svc.balance_of(db, svc.of_step(db, step.id))
        assert money.charged == Decimal("1200.00") and money.uncharged == Decimal("0.00")

        svc.apply(db, order=order, step=step, action="charge",
                  payload={"amount": "-200.00"})
        svc.apply(db, order=order, step=step, action="pay", payload={"amount": "-50.00"})
        money = svc.balance_of(db, svc.of_step(db, step.id))
        assert money.charged == Decimal("1000.00"), "Eine Gutschrift ist eine negative Rechnung."
        assert money.paid == Decimal("350.00"), "Eine Erstattung ist eine negative Zahlung."
        assert money.open == Decimal("650.00")
    finally:
        db.rollback(); db.close()


def test_a_suggestion_is_never_negative():
    """►►► **Eine Vorgabe ist nie negativ** (Testnotiz #795). ◄◄◄

    Gemeldet: «warum wurde hier ein Minus-Betrag vorausgewählt – macht keinen Sinn.»

    ``uncharged`` und ``open`` dürfen negativ sein (überberechnet bzw. überzahlt) – das
    ist eine gültige **Aussage**. Als **Vorschlag** in einem Eingabefeld ist sie es nicht.

    Bug-Form: das Feld bekommt ``uncharged`` roh. Dann steht «−250.00» als Vorgabe da, und
    ein Klick stellt eine Rechnung über minus 250. Negative Beträge bleiben **eingebbar** –
    das ist die Gutschrift.
    """
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)
        step = rows[0]
        _agree(db, order=order, step=step, party=kunde, amount="100.00")

        # Mehr berechnet als zugesagt und mehr gezahlt als gefordert.
        svc.apply(db, order=order, step=step, action="charge", payload={"amount": "350.00"})
        svc.apply(db, order=order, step=step, action="pay", payload={"amount": "400.00"})
        money = svc.balance_of(db, svc.of_step(db, step.id))
        assert money.uncharged == Decimal("-250.00") and money.open == Decimal("-50.00")
        assert money.next_charge is None, (
            "Eine Rechnung über minus 250 wurde vorgeschlagen."
        )
        assert money.next_payment is None, "Eine Zahlung über minus 50 wurde vorgeschlagen."

        facts = svc.embed_data(db, order=order, step=step)
        assert facts["next_charge"] is None and facts["next_payment"] is None
        assert facts["uncharged"] == "-250.00", "Die Aussage selbst bleibt lesbar."

        # Und eine Gutschrift bleibt eingebbar.
        svc.apply(db, order=order, step=step, action="charge", payload={"amount": "-250.00"})
        assert svc.balance_of(db, svc.of_step(db, step.id)).charged == Decimal("100.00")
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
        _agree(db, order=order, step=step, party=kunde, amount="100.00")
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
# §6 – can ist Auskunft UND Tor
# ---------------------------------------------------------------------------

def test_can_is_the_gate_not_only_a_hint():
    """**Dieselbe Tabelle zeigt die Knöpfe und weist ab.**

    Bug-Form: ``can`` ist nur eine Anzeige-Information, und ``apply`` prüft selbst (oder
    gar nicht). Dann liefen Knopf und Tür beim nächsten Verb auseinander.
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

        _agree(db, order=order, step=step, party=kunde, amount="100.00")
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
        _agree(db, order=order, step=step, party=kunde, amount="500.00")
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
# §7 – ohne Zusage schliesst nichts ab; mit prepaid erst nach dem Geld
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
        with pytest.raises(HTTPException) as e:
            proc.confirm_step(db, order=order, step_id=rows[0].id, actor_id=None,
                              values={})
        assert e.value.status_code == 409
        assert "nicht bestätigt" in str(e.value.detail)
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
        _agree(db, order=order, step=step, party=kunde, amount="300.00")

        money = svc.balance_of(db, svc.of_step(db, step.id))
        assert money.open == Decimal("0.00") and money.settled is False, (
            "«offen = 0» heisst hier «nichts gefordert», nicht «bezahlt»."
        )
        with pytest.raises(HTTPException) as e:
            proc.confirm_step(db, order=order, step_id=step.id, actor_id=None, values={})
        assert e.value.status_code == 409 and "Zahlungseingang" in str(e.value.detail)

        svc.apply(db, order=order, step=step, action="charge", payload={})
        svc.apply(db, order=order, step=step, action="pay", payload={})
        db.flush()
        assert svc.balance_of(db, svc.of_step(db, step.id)).settled is True
        _confirm_money(db, order, step)
        assert svc.of_step(db, step.id).stage == "done"
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §8 – die Nummer, und die Unabhängigkeit
# ---------------------------------------------------------------------------

def test_we_number_our_own_invoices_and_never_theirs():
    """**Wer nummeriert, sagt die Richtung.**

    Bug-Form: das System erfindet auch bei einer **Ausgabe** eine Nummer. Dann stünde auf
    einer Lieferantenrechnung eine Nummer, die es beim Lieferanten nie gab.
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
        _agree(db, order=order, step=rows[0], party=kunde, amount="100.00")
        _agree(db, order=order, step=rows[1], party=lieferant, amount="100.00")

        # **Die fremde Rechnung ZUERST** – genau hier lag der Fehler: sie verbrauchte die
        # Zählung, und unsere erste eigene hiess «…-2». Eine Nummernserie mit Lücken ist
        # buchhalterisch keine.
        svc.apply(db, order=order, step=rows[1], action="charge", payload={"amount": "10"})
        svc.apply(db, order=order, step=rows[0], action="charge", payload={"amount": "60"})
        svc.apply(db, order=order, step=rows[0], action="charge", payload={"amount": "40"})

        ours = db.query(DealEntry).join(
            svc.Deal, DealEntry.deal_id == svc.Deal.id).filter(
            svc.Deal.step_id == rows[0].id).order_by(DealEntry.id).all()
        assert [e.reference for e in ours] == [str(order.object_id),
                                               f"{order.object_id}-2"]
        theirs = db.query(DealEntry).join(
            svc.Deal, DealEntry.deal_id == svc.Deal.id).filter(
            svc.Deal.step_id == rows[1].id).one()
        assert theirs.reference is None, (
            "Bei einer Ausgabe hat das System eine Nummer erfunden – die vergibt die "
            "Gegenpartei, und eine erfundene wäre eine Behauptung."
        )
    finally:
        db.rollback(); db.close()


def test_only_sent_fields_change_anything():
    """**Wer die Referenz ändert, verliert nicht die Notiz.**

    Bug-Form: der Dienst schreibt jedes Feld der Nutzlast, auch die nicht gesendeten.
    Dann löschte jeder Aufruf alles, was er nicht ausdrücklich wiederholt.
    """
    from app.services import deal as svc
    db = _db()
    try:
        lieferant = _party(db, "Härterei AG")
        staff = _staff(db)
        art = _article(db, "Welle",
                       steps=[_money_step(direction="out", parties=[lieferant])])
        order, rows = _make(db, quantity=1, article=art)
        step = rows[0]
        svc.apply(db, order=order, step=step, action="note",
                  payload={"note": "Hebebühne nötig"}, actor=staff)
        svc.apply(db, order=order, step=step, action="note",
                  payload={"reference": "BST-99"}, actor=staff)
        row = svc.of_step(db, step.id)
        assert row.reference == "BST-99"
        assert row.note == "Hebebühne nötig", "Eine nicht gesendete Angabe wurde geleert."
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


def test_an_employee_who_is_also_the_counterparty_keeps_the_full_view():
    """►►► **Die verengte Sicht ist ein ZUGANG, keine Rolle im Vorgang.** ◄◄◄

    Ein Mitarbeiter, der bei einem Vorgang als Gegenpartei eingetragen ist, arbeitet
    trotzdem im ERP – er sieht dort ohnehin den ganzen Auftrag, und eine zweite, engere
    Ansicht desselben Datensatzes wäre eine zweite Wahrheit über dieselbe Sache.

    Die Frage ist darum **«darf dieser Betrachter ins ERP?»** (``STAFF_ROLES``), nicht
    «kommt seine Nummer im Vorgang vor». Bug-Form: die Verengung hängt an der
    **Beteiligung** – dann verliert ein Einkäufer, der einmal selbst angefragt wird, an
    genau diesem Auftrag die Zahlen, die er zum Arbeiten braucht.
    """
    from app.services import deal as svc
    db = _db()
    try:
        # Derselbe Mensch: Mitarbeiter **und** eingetragene Gegenpartei.
        inside = _party(db, "Werkstatt intern", role="employee")
        outside = _party(db, "Härterei extern")
        staff = _staff(db)
        art = _article(db, "Welle", steps=[
            _money_step(direction="out", parties=[inside, outside])])
        order, rows = _make(db, quantity=2, article=art)
        step = rows[0]
        svc.apply(db, order=order, step=step, action="ask", payload={}, actor=staff)
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": outside.object_id, "amount": "999.00"}, actor=staff)

        assert svc.mine(db, inside) is None, (
            "Der Mitarbeiter bekommt eine verengte Sicht, weil er im Vorgang vorkommt – "
            "die Verengung ist ein Zugang, keine Rolle im Vorgang."
        )
        seen = svc.embed_data(db, order=order, step=step, viewer=inside)
        assert len(seen["quotes"]) == 2, (
            "Der Mitarbeiter sieht nur seine eigene Zeile – im ERP steht der ganze "
            "Vorgang, und zwei Ansichten desselben Datensatzes sind zwei Wahrheiten."
        )
        assert seen["open"] is not None and seen["charged"] is not None, (
            "Dem Mitarbeiter fehlen Forderung und Geld – ausgerechnet an dem Auftrag, "
            "an dem er selbst beteiligt ist."
        )
        # **Der Aussenstehende bleibt aussen** – sonst prüfte der Wächter nur, dass die
        # Verengung überhaupt nicht mehr greift.
        narrow = svc.embed_data(db, order=order, step=step, viewer=outside)
        assert len(narrow["quotes"]) == 1 and narrow["open"] is None
    finally:
        db.rollback(); db.close()


def test_whoever_did_not_win_does_not_see_the_award():
    """►►► **Wer nicht den Zuschlag hat, sieht ihn auch nicht.** ◄◄◄

    Die Angebotszeilen waren gefiltert, die **getroffene Wahl** nicht: ein angefragter,
    unterlegener Lieferant las Namen, Preis, Zahlungsfrist und Datum seines Konkurrenten –
    und dazu die **Freigabe-Liste**, also die Konkurrenzliste selbst.

    Gemessen über die echten Dienstpfade, nicht gelesen. Der Beschaffungs-Beleg hat
    dieselbe Regel längst (``purchase._embed``); zwei Formen einer Regel sind in Ordnung,
    zwei Regeln nicht.

    Bug-Formen: (a) die Zusage reist ungefiltert mit; (b) die Freigabe-Liste ebenso;
    (c) das Wort der Gegenhandlung steht da, obwohl es die Handlung nie gibt.
    """
    from app.services import deal as svc
    db = _db()
    try:
        a, b = _party(db, "Härterei A"), _party(db, "Härterei B")
        staff = _staff(db)
        art = _article(db, "Welle",
                       steps=[_money_step(direction="out", parties=[a, b])])
        order, rows = _make(db, quantity=2, article=art)
        step = rows[0]
        svc.apply(db, order=order, step=step, action="ask", payload={}, actor=staff)
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": a.object_id, "amount": "100.00",
                           "payment_days": 30}, actor=staff)
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": b.object_id, "amount": "999.00"}, actor=staff)
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": a.object_id}, actor=staff)

        lost = svc.embed_data(db, order=order, step=step, viewer=b)
        assert lost["party_object_id"] is None and lost["party_name"] is None, (
            "Der Unterlegene sieht, wer den Zuschlag hat."
        )
        assert lost["amount"] is None and lost["due_days"] is None, (
            "Der Unterlegene sieht den Preis des Konkurrenten."
        )
        assert lost["agreed_on"] is None and lost["reference"] is None
        assert lost["allowed"] == [], (
            "Die Freigabe-Liste ist die Konkurrenzliste – sie geht ihn nichts an."
        )
        assert "100.00" not in str(lost) and "Härterei A" not in str(lost), (
            "Irgendwo in der Antwort steckt der Konkurrent noch."
        )
        # **Kein Wort für eine Handlung, die es nie gibt.**
        assert lost["can"] == [] and lost["undo"] is None

        # **Wer den Zuschlag HAT, sieht seine Zusage** – sonst prüfte der Wächter nur,
        # dass gar nichts mehr durchkommt.
        won = svc.embed_data(db, order=order, step=step, viewer=a)
        assert won["party_object_id"] == a.object_id and won["amount"] == "100.00", (
            "Der Gewählte sieht seine eigene Zusage nicht."
        )
        # **Geld bleibt trotzdem Personalsache** – was wir schulden, ist unsere Buchhaltung.
        assert won["open"] is None and won["entries"] == []
    finally:
        db.rollback(); db.close()


def test_the_feed_shows_a_counterparty_the_orders_it_is_involved_in():
    """►►► **Eine Frage, zwei Leser** – Feed und Detail. ◄◄◄

    Der Feed fragte nur den Beschaffungs-Beleg (``purchase.mine``). Die Gegenpartei eines
    **Geldvorgangs** hatte damit ERP-Zugang, sah ihren Auftrag aber in **keiner Liste** –
    erreichbar nur über die direkte Adresse. Zwei Ableitungen derselben Frage laufen genau
    so auseinander.

    Bug-Formen: (a) der Feed fragt wieder nur eine der beiden Quellen; (b) ein Mitarbeiter
    bekommt plötzlich eine gefilterte Liste.
    """
    from app.routers.orders import _involved
    from app.services import deal as svc
    db = _db()
    try:
        p = _party(db, "Härterei A")
        staff = _staff(db)
        art = _article(db, "Welle", steps=[_money_step(direction="out", parties=[p])])
        order, rows = _make(db, quantity=2, article=art)
        step = rows[0]
        svc.apply(db, order=order, step=step, action="ask", payload={}, actor=staff)

        mine = _involved(db, p)
        assert mine is not None, "Eine Gegenpartei bekäme die volle Liste."
        assert (order.id, step.id) in mine, (
            "Der Auftrag des Geldvorgangs fehlt in der Liste – die Gegenpartei erreicht "
            "ihn nur noch über die direkte Adresse."
        )
        # **Personal bleibt Personal** – `None` heisst «sieht alles».
        assert _involved(db, staff) is None
    finally:
        db.rollback(); db.close()
