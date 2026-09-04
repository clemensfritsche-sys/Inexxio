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


def _money_step(*, direction: str = "out", parties=(), task: str = "Härten auf 58 HRC",
                prepaid: bool = False) -> dict:
    """Ein «Zahlung»-Modul – drei Angaben, mehr gibt es nicht.

    Je zugelassenem Partner **eine Pflichtangabe**, was bei ihm zu tun ist: seine
    Artikelnummer, sein Shop-Link oder ein Satz.
    """
    return {"module_type": "zahlung",
            "config": {"direction": direction,
                       "parties": [{"party": p.object_id, "ref": task} for p in parties],
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

    **Und wer den Preis nennt, sagt die Richtung** (Testnotiz #837): bei einer *Einnahme*
    geht das Angebot **mit** dem Betrag hinaus – ``ask`` weist ohne ihn ab. Der Helfer
    fragt darum die Angabe (``Direction.quoted_by``) und nennt keinen Schlüssel: ein
    ``if direction == "in"`` hier wäre die zweite Stelle für dieselbe Regel.
    """
    from app.domain import deal as dm
    from app.services import deal as svc
    actor = staff or _staff(db)
    ours = dm.of(svc.of_step(db, step.id).direction).quoted_by == dm.BY_US
    # ►►► **Wo wir den Preis nennen, sind die POSITIONEN der Preis** (MWSTG Art. 26). ◄◄◄
    #
    # Der Helfer nennt **eine Zeile ohne Artikel zu 0 %**: damit ist brutto = netto, und
    # die Zahlen der Prüfungen bleiben die Zahlen, um die es dort geht. Die **Steuer**
    # prüfen die Wächter, die sie meinen – ein Helfer, der sie nebenbei aufschlägt, machte
    # jede andere Prüfung zu einer über Rundung.
    svc.apply(db, order=order, step=step, action="ask",
              payload={"parties": [party.object_id],
                       **({"lines": [{"article": None, "price": amount, "vat": "0.00"}]}
                          if ours else {})}, actor=actor)
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
                                          task="Fertigung nach Zeichnung")])
        before = db.query(InstanceUnit).count()
        order, rows = _make(db, quantity=4, article=art)
        assert db.query(InstanceUnit).count() - before == 4, "Die Freigabe erzeugt sie."

        mod = modules.get("zahlung")
        assert mod.terminal is False, "Ein Geldvorgang ist kein Ausgang."
        assert mod.moves is False, "Ein Geldvorgang bewegt nichts."
        # **Und es gibt gar keinen Beschaffungs-Beleg mehr**, den es tragen könnte: die
        # Module «Beschaffen» und «Verkauf» sind entfernt, und mit ihnen die Vokabel
        # ``buys``. Ein Modul, das sie wieder kennt, hat den Handel ein zweites Mal.
        assert not hasattr(mod, "buys"), (
            "Ein Modul kennt wieder einen Beschaffungs-Beleg – der Geldvorgang ist "
            "die eine Stelle, an der Geld mit einer zweiten Partei fliesst."
        )
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
            _money_step(direction="out", parties=[lieferant], task="Härten"),
            _money_step(direction="in", parties=[kunde], task="Art. 4711"),
        ])
        order, rows = _make(db, quantity=2, article=art)

        out = svc.embed_data(db, order=order, step=rows[0])
        inn = svc.embed_data(db, order=order, step=rows[1])
        assert out["direction"] == dm.OUT and inn["direction"] == dm.IN
        # ►►► **Ein Wort für BEIDE Richtungen** (Testnotiz #802). ◄◄◄
        #
        # «Kunde» ↔ «Lieferant» war dieselbe Rolle in zwei Wörtern, und jede Aufrufstelle
        # musste sich das richtige holen. Ein Wort nimmt die falsche Wahl als Fehlerklasse
        # weg – und weil Singular = Plural ist, gibt es auch keine Beugung mehr, die
        # jemand rechnen könnte («Kundeen», #787).
        assert out["party_word"] == inn["party_word"] == dm.PARTY
        # **Wie man zugeht, unterscheidet sich – WAS man tut, nicht.**
        assert out["ask_verb"] == "Anfragen" and inn["ask_verb"] == "Anbieten"
        # ►►► **Man nimmt das ANGEBOT an – der Auftrag ist das Ergebnis** (#826). ◄◄◄
        #
        # «Auftrag bestätigen» benannte die Folge statt der Handlung: bestätigt wird, was
        # dasteht, und das ist ein Angebot bzw. eine Offerte. Und weiterhin in **beiden**
        # Richtungen dasselbe Wort – zwei wären eines zu viel.
        assert (out["stages"][0]["verb"] == inn["stages"][0]["verb"]
                == dm.AGREE_VERB == "Angebot annehmen"), (
            "Der Zuschlag heisst in beiden Richtungen gleich, und er benennt die "
            "Handlung – nicht ihre Folge."
        )
        # ►►► **Rechnung und Zahlung heissen ebenfalls überall gleich** (#828). ◄◄◄
        #
        # «Rechnung stellen» ↔ «Rechnung erfassen» und «Zahlungseingang» ↔ «Zahlung»
        # waren vier Wörter für zwei Handlungen. **Erfasst** wird beides – das System
        # bucht eine Zeile, es überweist nichts.
        assert (out["charge_word"] == inn["charge_word"] == "Rechnung erfassen"
                and out["payment_word"] == inn["payment_word"] == "Zahlung erfassen"), (
            "Die beiden Geld-Wörter hängen wieder an der Richtung."
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
    Vorgänge – aus einem Verkauf würde ein Einkauf, ohne dass jemand etwas tut.
    """
    from app.domain import deal as dm
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
        assert facts["party_word"] == dm.PARTY
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
        # ►►► **Was bei einem Partner zu tun ist, steht BEI IHM** (#805/#808). ◄◄◄
        #
        # Der frühere freiwillige Satz am Vorgang war dieselbe Angabe ein zweites Mal, nur
        # ohne Adressaten – und optional. Ein Feld, das man ausfüllen *kann*, wird an der
        # Hälfte der Stellen leer gelassen; dann sagt seine Leere nichts.
        cfg = rows[0].config or {}
        assert cfg["parties"][0]["ref"] == "Härten auf 58 HRC", (
            "Was bei diesem Partner zu tun ist, steht nicht bei ihm."
        )
        assert "subject" not in cfg, "Der abgeschaffte Satz ist zurück."
        from fastapi import HTTPException
        from app.domain import modules
        with pytest.raises(HTTPException):
            modules.get("zahlung").clean_config(
                {"direction": "in", "parties": [{"party": 100000001, "ref": ""}]})
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

        # Der Betrag gehört bei einer **Einnahme** zur Anfrage: wir nennen den Preis,
        # das Angebot geht mit ihm hinaus (#837). Gemeint ist hier die **Partei**-Angabe –
        # und die bleibt weg.
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"lines": [{"article": None, "price": "100.00",
                                      "vat": "0.00"}]}, actor=staff)
        facts = svc.embed_data(db, order=order, step=rows[0], viewer=staff)
        assert [q["party_object_id"] for q in facts["quotes"]] == [kunde.object_id], (
            "Ohne Angabe wurden nicht die zugelassenen Gegenparteien angefragt."
        )
        # ►►► **Und sie steht sofort als OFFERTE da** (#837) – nicht als leere Anfrage:
        # bei einer Einnahme ist das Angebot mit dem Preis hinausgegangen.
        assert facts["quotes"][0]["state"] == "offeriert", (
            "Unser eigenes Angebot steht als leere Anfrage da – dann sähe der Kunde ein "
            "Angebot ohne Preis."
        )
        assert facts["quotes"][0]["amount"] == "100.00"
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
            _money_step(direction="out", parties=[]),
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


def test_a_wrong_line_is_reversed_by_a_counter_booking_never_deleted():
    """►►► **Eine Rechnung löscht man nicht – man storniert sie** (#823/#824). ◄◄◄

    Eine Rechnungsnummer ist vergeben, ein Beleg ist draussen: eine Zeile verschwinden zu
    lassen behauptet, sie sei nie passiert. Das ist keine Buchhaltung.

    **Und es braucht keine neue Mechanik**: eine Gutschrift ist längst eine *negative
    Rechnung*, eine Erstattung eine *negative Zahlung* – eine Stornierung ist genau das,
    über den vollen Betrag. Also entsteht eine **zweite** Zeile: dieselbe Art, der
    negative Betrag, ``reverses_id`` auf die stornierte. Beide bleiben stehen, die Summe
    stimmt von selbst, ohne einen einzigen Sonderfall in ``balance``.

    Bug-Form: der Soft-Delete von früher (``is_active = False``). Dann ist der Saldo zwar
    richtig, die Zeile aber weg – und wer den Nachweis liest, sieht nicht, dass es sie
    gab.
    """
    from fastapi import HTTPException
    from app.models import DealEntry
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)
        step = rows[0]
        _agree(db, order=order, step=step, party=kunde, amount="100.00")
        # **Ohne Rechnung keine Zahlung** (#822) – erst fordern, dann kassieren.
        svc.apply(db, order=order, step=step, action="charge", payload={"amount": "100.00"})
        svc.apply(db, order=order, step=step, action="pay", payload={"amount": "10000.00"})
        row = svc.of_step(db, step.id)
        wrong = (db.query(DealEntry)
                 .filter(DealEntry.deal_id == row.id, DealEntry.kind == "payment").one())

        # ►►► **Eine Zahlung storniert man NICHT** (Testnotiz #842). ◄◄◄
        #
        # Sie ist ein **Ereignis** der Aussenwelt, kein Beleg, den wir ausstellen – man
        # macht sie nicht ungeschehen. Wer sich vertippt hat oder wem das Geld zurückkam,
        # bucht eine **zweite Zahlung**; welcher der beiden Fälle es ist, weiss nur ein
        # Mensch.
        with pytest.raises(HTTPException) as err:
            svc.apply(db, order=order, step=step, action="reverse",
                      payload={"entry": wrong.id})
        assert err.value.status_code == 409
        svc.apply(db, order=order, step=step, action="pay", payload={"amount": "-10000"})
        assert svc.balance_of(db, row).paid == Decimal("0.00")

        # **Die FORDERUNG dagegen ist ein Beleg** – und die storniert eine Gegenbuchung.
        bill = (db.query(DealEntry)
                .filter(DealEntry.deal_id == row.id, DealEntry.kind == "charge").one())
        svc.apply(db, order=order, step=step, action="reverse", payload={"entry": bill.id})
        assert svc.balance_of(db, row).charged == Decimal("0.00"), (
            "Die Gegenbuchung hebt die Forderung nicht auf – dann rechnet `balance` sie "
            "nicht mit, und es ist doch ein Sonderfall."
        )
        db.refresh(bill)
        assert bill.is_active is True, (
            "Die Zeile wurde weggeräumt statt storniert – ein Beleg, der einmal draussen "
            "war, verschwindet nicht rückwirkend aus dem Nachweis."
        )
        counter = (db.query(DealEntry)
                   .filter(DealEntry.reverses_id == bill.id).one())
        assert (counter.kind == bill.kind and counter.amount == -bill.amount), (
            "Die Gegenbuchung hat nicht dieselbe Art und den negativen Betrag."
        )
        # ►►► **Eine Stornorechnung ist ein EIGENER Beleg** (Testnotiz #841). ◄◄◄
        #
        # Sie kopierte die Nummer der stornierten: zwei Belege hiessen gleich, und in der
        # Serie fehlte die nächste Zahl. Jede Nummer wird genau **einmal** vergeben; der
        # Bezug wohnt in ``reverses_id``, nie in der Nummer.
        assert counter.reference and counter.reference != bill.reference, (
            "Die Stornorechnung trägt die Nummer der stornierten – dann heissen zwei "
            "Belege gleich, und die Serie hat eine Lücke."
        )
        assert counter.reference == f"{order.object_id}-2"
        assert bill.reference in (counter.note or ""), (
            "Der Verweis auf die stornierte Rechnung fehlt."
        )

        # **Zweimal stornieren gibt es nicht**, und eine Gegenbuchung storniert man
        # ebenso wenig – sonst entstünde eine Kette aus Vorzeichen, in der niemand mehr
        # sagen kann, was gilt.
        for target in (bill.id, counter.id):
            with pytest.raises(HTTPException) as err:
                svc.apply(db, order=order, step=step, action="reverse",
                          payload={"entry": target})
            assert err.value.status_code == 409
    finally:
        db.rollback(); db.close()


def test_there_is_no_way_to_delete_a_line_at_all():
    """**Kein Löschweg – auch nicht für einen Tippfehler.**

    Bug-Form: ``void`` steht neben ``reverse`` weiter zur Verfügung. Dann gäbe es zwei
    Wege für dieselbe Sache, und der bequemere ist der falsche. Genau so korrigiert jede
    Buchhaltung der Welt; eine Frist («innerhalb fünf Minuten darf man noch löschen»)
    wäre eine erfundene Regel mit einer Uhr darin.
    """
    from app.services import deal as svc
    assert "void" not in svc.HANDLERS, "Der Löschweg ist wieder da."
    assert svc.REVERSE in svc.HANDLERS


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
        assert {"charge", "revoke"} <= set(facts["can"])
        assert "agree" not in facts["can"], "Zweimal zusagen gibt es nicht."

        # ►►► **Ohne Rechnung keine Zahlung** (Testnotiz #822). ◄◄◄
        #
        # Man kassiert nicht, was niemand gefordert hat – der Satz steht seit §9.11 im
        # Haus, jetzt steht er auch in `can`, also in **beiden** Formen: der Knopf fehlt,
        # und die Tür weist ab. Die **Vorauszahlung** verliert dadurch nichts: sie ist
        # «erst fordern, dann zahlen».
        assert "pay" not in facts["can"], (
            "Zahlen geht, bevor irgendetwas gefordert wurde."
        )
        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=order, step=step, action="pay", payload={"amount": "1"})
        assert e.value.status_code == 409
        svc.apply(db, order=order, step=step, action="charge", payload={"amount": "100"})
        assert "pay" in svc.embed_data(db, order=order, step=step)["can"], (
            "Nach der Rechnung fehlt die Zahlung – dann ist die Sperre keine Bedingung, "
            "sondern ein Verbot."
        )
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
            _money_step(direction="in", parties=[kunde], task="Art. 4711"),
            _money_step(direction="out", parties=[lieferant], task="Härten"),
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
        # ►►► **Immer mit Suffix – auch die erste** (Testnotiz #827). ◄◄◄
        #
        # Früher fiel das «-1» der ersten nach aussen weg. Das war eine Sonderregel für
        # genau einen Fall: dieselbe Serie hiess «100019251», dann «100019251-2» – zwei
        # Formen für eine Nummer, und wer sie sortiert oder sucht, muss beide kennen.
        # Dieselbe Regel wie beim Suffix der Einzelinstanz: die Zählung ist die Zählung.
        assert [e.reference for e in ours] == [f"{order.object_id}-1",
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
    """**Nur gesendete Felder wirken** (``exclude_unset``).

    Wer den Betrag ändert, verliert nicht die Zahlungsfrist. Sonst löschte jeder Aufruf
    alles, was er nicht ausdrücklich wiederholt.

    *Geprüft am Angebotsspiegel, seit die Handlung ``note`` entfallen ist (#812): dort
    stehen mehrere Angaben nebeneinander, also ist es dieselbe Frage an einem Verb, das es
    noch gibt.*
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
        svc.apply(db, order=order, step=step, action="ask", payload={}, actor=staff)
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": lieferant.object_id, "amount": "100.00",
                           "lead_days": 14, "payment_days": 30}, actor=staff)
        # Nur den Betrag nachreichen – die beiden Fristen kommen nicht mit.
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": lieferant.object_id, "amount": "120.00"}, actor=staff)
        line = svc.of_step(db, step.id).quotes[0]
        assert line["amount"] == "120.00"
        assert line["lead_days"] == 14 and line["payment_days"] == 30, (
            "Ein Aufruf hat gelöscht, was er nicht wiederholt hat."
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
        assert lost["agreed_on"] is None
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


# ---------------------------------------------------------------------------
# Testnotizen #837 · #840 · #841 · #842 – wer den Preis nennt, und was
# Buchhaltung wirklich verlangt
# ---------------------------------------------------------------------------

def test_who_names_the_price_is_a_property_of_the_direction():
    """►►► **Ein Angebot hat einen Urheber** (Testnotiz #837). ◄◄◄

    *«Wenn ich einkaufe, sage ich was und von wem ich es offeriert haben möchte, die
    Gegenpartei trägt Preis ein und ich akzeptiere. Beim Verkaufen sage ich zuerst was ich
    zu welchem Preis an wen offeriere, Kunde bestätigt.»* – Exakt richtig, und vorher
    nicht abgebildet: ``ask`` schickte in **beiden** Richtungen eine leere Zeile hinaus,
    beim Verkauf sähe der Kunde also ein Angebot ohne Preis.

    Daraus folgt alles ohne eine Verzweigung: **wer nennt, füllt vor dem Hinausgehen**,
    und **wer empfängt, nimmt an oder lehnt ab** – unseren Preis zu überschreiben wäre
    keine Antwort, sondern eine Gegenofferte, und die ist ein neuer Vorgang.

    Bug-Formen: (a) die Einnahme geht ohne Betrag hinaus; (b) die Ausgabe verlangt einen
    (dann könnten wir seine Offerte gar nicht abwarten); (c) die Gegenpartei darf in der
    falschen Richtung offerieren bzw. zusagen.
    """
    from fastapi import HTTPException
    from app.domain import deal as dm
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        lieferant = _party(db, "Härterei AG")
        art = _article(db, "Welle", steps=[
            _money_step(direction="in", parties=[kunde]),
            _money_step(direction="out", parties=[lieferant]),
        ])
        order, rows = _make(db, quantity=1, article=art)
        staff = _staff(db)

        # (a) **Einnahme: ohne Betrag geht nichts hinaus.**
        with pytest.raises(HTTPException) as err:
            svc.apply(db, order=order, step=rows[0], action="ask",
                      payload={"parties": [kunde.object_id]}, actor=staff)
        assert err.value.status_code == 400
        # ►►► **Und der Preis sind die POSITIONEN** – dort hängt der Steuersatz. ◄◄◄
        svc.apply(db, order=order, step=rows[0], action="ask",
                  payload={"parties": [kunde.object_id], "lead_days": 5,
                           "lines": [{"article": None, "price": "500.00",
                                      "vat": "8.10"}]}, actor=staff)
        line = svc.embed_data(db, order=order, step=rows[0], viewer=staff)["quotes"][0]
        assert line["state"] == dm.QUOTED, (
            "Unser Angebot geht als leere Anfrage hinaus – dann sieht der Kunde ein "
            "Angebot ohne Preis."
        )
        # **Der Betrag ist die BRUTTO-Summe der Positionen**, keine getippte Zahl daneben:
        # 500.00 netto zu 8.1 % sind 540.50 brutto.
        assert line["amount"] == "540.50", (
            "Der Angebotsbetrag ist nicht die Brutto-Summe der Positionen – dann stehen "
            "zwei Zahlen über dieselbe Sache da."
        )
        assert line["lines"][0]["price"] == "500.00" and line["lines"][0]["vat"] == "8.10"
        assert line["lead_days"] == 5

        # (b) **Ausgabe: leer hinaus ist der Sinn** – wir warten auf seine Offerte.
        svc.apply(db, order=order, step=rows[1], action="ask",
                  payload={"parties": [lieferant.object_id]}, actor=staff)
        theirs = svc.embed_data(db, order=order, step=rows[1], viewer=staff)["quotes"][0]
        assert theirs["state"] == dm.ASKED and theirs["amount"] is None, (
            "Die Anfrage trägt schon einen Preis – dann haben wir ihn genannt, nicht er."
        )

        # (c) **Was die Gegenpartei darf, folgt aus derselben Angabe.**
        assert dm.of(dm.OUT).party_actions == ("quote", "decline")
        assert dm.of(dm.IN).party_actions == ("agree", "decline"), (
            "Der Kunde darf unseren Preis überschreiben – das ist keine Antwort auf ein "
            "Angebot, sondern eine Gegenofferte."
        )
        assert "quote" not in svc.can(db, svc.of_step(db, rows[0].id), kunde)
    finally:
        db.rollback(); db.close()


def test_a_number_we_assign_is_never_typed():
    """►►► **Eine Nummer, die WIR vergeben, tippt niemand ab** (Testnotiz #840). ◄◄◄

    Sie entsteht aus der Serie – lückenlos und ohne Doppelung. Ein Eingabefeld daneben ist
    die zweite Aussage über dieselbe Sache, und die getippte gewinnt, auch wenn sie falsch
    ist. Wo die **Gegenpartei** die Rechnung stellt, ist es dagegen **ihre** Nummer: sie
    steht auf ihrem Papier, und ohne sie liesse sich der Beleg nicht zuordnen.

    Bug-Formen: (a) ein gesendeter Wert gewinnt gegen die Serie; (b) die
    Lieferantenrechnung verliert ihre Nummer.
    """
    from app.models import DealEntry
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        lieferant = _party(db, "Härterei AG")
        art = _article(db, "Welle", steps=[
            _money_step(direction="in", parties=[kunde]),
            _money_step(direction="out", parties=[lieferant]),
        ])
        order, rows = _make(db, quantity=1, article=art)
        _agree(db, order=order, step=rows[0], party=kunde, amount="100.00")
        _agree(db, order=order, step=rows[1], party=lieferant, amount="60.00")

        # (a) **Verworfen, nicht ignoriert** – ein Feld, das der Dienst annimmt, obwohl
        # die Oberfläche es nicht anbietet, wäre eine Hintertür zur zweiten Wahrheit.
        svc.apply(db, order=order, step=rows[0], action="charge",
                  payload={"amount": "100.00", "reference": "VON HAND"})
        ours = (db.query(DealEntry).join(svc.Deal, DealEntry.deal_id == svc.Deal.id)
                .filter(svc.Deal.step_id == rows[0].id).one())
        assert ours.reference == f"{order.object_id}-1", (
            "Eine getippte Rechnungsnummer hat die Serie überschrieben."
        )
        # (b) **Seine Rechnung trägt seine Nummer.**
        svc.apply(db, order=order, step=rows[1], action="charge",
                  payload={"amount": "60.00", "reference": "RE-2026-4711"})
        theirs = (db.query(DealEntry).join(svc.Deal, DealEntry.deal_id == svc.Deal.id)
                  .filter(svc.Deal.step_id == rows[1].id).one())
        assert theirs.reference == "RE-2026-4711", (
            "Die Nummer der Gegenpartei wurde verworfen – dann lässt sich ihr Beleg "
            "nicht mehr zuordnen."
        )
    finally:
        db.rollback(); db.close()


def test_a_payment_is_an_event_and_is_corrected_by_a_second_one():
    """►►► **Man storniert einen BELEG, kein Ereignis** (Testnotiz #842). ◄◄◄

    *«wenn ich eine zahlung erfasst habe, dann habe ich sie ja erfasst, dann kann ich sie
    doch nicht mehr stornieren… dann muss ich sie durch eine weitere zahlung korrigieren
    oder???»* – Ja, genau so, und seine eigene Antwort ist die richtige.

    Eine **Forderung** ist ein Beleg, den *wir* ausstellen; ihn nimmt eine Stornorechnung
    zurück. Eine **Zahlung** ist die Aufzeichnung dessen, was auf dem Konto passiert ist –
    ein Ereignis der Aussenwelt macht man nicht ungeschehen. Ob es ein Erfassungsfehler
    war oder ob das Geld zurückkam, weiss ohnehin nur ein Mensch; beides ist eine zweite,
    negative Zahlung, und die gibt es längst.

    Bug-Formen: (a) eine Zahlung lässt sich stornieren; (b) ``can`` bietet das Verb an,
    obwohl nur Zahlungen dastehen (ein Knopf, der garantiert scheitert).
    """
    from fastapi import HTTPException
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)
        step = rows[0]
        _agree(db, order=order, step=step, party=kunde, amount="100.00")
        svc.apply(db, order=order, step=step, action="charge", payload={"amount": "100"})
        row = svc.of_step(db, step.id)

        # (b) **Die Forderung ist stornierbar** – solange es sie gibt.
        assert svc.REVERSE in svc.can(db, row, None)
        bill = svc._entries(db, row.id)[0]
        svc.apply(db, order=order, step=step, action="reverse", payload={"entry": bill.id})
        assert svc.REVERSE not in svc.can(db, row, None), (
            "Das Verb steht noch da, obwohl keine stornierbare Forderung übrig ist – ein "
            "Knopf, der garantiert scheitert."
        )

        # (a) **Eine Zahlung nicht** – und der Satz nennt den Weg.
        svc.apply(db, order=order, step=step, action="charge", payload={"amount": "100"})
        svc.apply(db, order=order, step=step, action="pay", payload={"amount": "100"})
        money = [e for e in svc._entries(db, row.id) if e.kind == "payment"][0]
        with pytest.raises(HTTPException) as err:
            svc.apply(db, order=order, step=step, action="reverse",
                      payload={"entry": money.id})
        assert err.value.status_code == 409
        assert "zweite Zahlung" in err.value.detail, (
            "Die Ablehnung nennt den Weg nicht – eine Sperre ohne Ausweg ist eine "
            "Sackgasse mit Ausrufezeichen."
        )
        # **Und der Weg funktioniert.**
        svc.apply(db, order=order, step=step, action="pay", payload={"amount": "-100"})
        assert svc.balance_of(db, row).paid == Decimal("0.00")
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# ►► DIE STEUER — die Position trägt ihren Satz (MWSTG Art. 26)
# ---------------------------------------------------------------------------

def test_the_rate_belongs_to_the_position_not_to_the_document():
    """►►► **Der Steuersatz hängt an der SACHE, nicht am Beleg** (MWSTG Art. 26). ◄◄◄

    Sechs Wellen zu 8.1 % und eine Ausfuhr zu 0 % stehen auf **demselben** Papier. Ein
    Satz je Beleg wäre bei jedem gemischten Geschäft falsch – und zwar stillschweigend,
    weil die Summe trotzdem aufgeht.

    **Gerundet wird je Satz auf der Summe**, nie je Position aufsummiert: bei zwölf
    Zeilen weicht die Summe der gerundeten Einzelbeträge sonst um Rappen ab, und eine
    MWST-Abrechnung kennt keine Rappen-Toleranz.

    Bug-Formen: (a) ein Satz für den ganzen Beleg; (b) je Position gerundet und dann
    summiert; (c) der Brutto-Betrag ist nicht die Summe der Positionen.
    """
    from app.domain import deal as dm

    lines = [
        {"article": 1, "quantity": 6, "price": "10.00", "vat": "8.10"},
        {"article": 2, "quantity": 2, "price": "50.00", "vat": "0.00"},
    ]
    split = dm.vat_split(lines, "CHF")
    assert [(r["rate"], r["net"], r["tax"]) for r in split] == [
        ("8.10", "60.00", "4.86"), ("0.00", "100.00", "0.00")
    ], "Die Aufteilung je Satz stimmt nicht – (a) oder (b)."
    assert dm.gross_of(lines, "CHF") == Decimal("164.86"), (
        "Der Brutto-Betrag ist nicht Netto + Steuer je Satz (c)."
    )

    # (b) **Je Satz auf der SUMME** – drei Zeilen, deren Einzelsteuern je 0.405 ergäben.
    thirds = [{"article": i, "quantity": 1, "price": "5.00", "vat": "8.10"}
              for i in range(3)]
    assert dm.vat_split(thirds, "CHF")[0]["tax"] == "1.22", (
        "Gerundet wurde je Position und dann summiert – 3 × 0.41 = 1.23 statt 1.22."
    )


def test_a_partial_invoice_carries_every_rate_it_touches():
    """►►► **Eine Anzahlung wird ANTEILIG über alle Sätze versteuert.** ◄◄◄

    Sie ist zum Satz der zugrunde liegenden Leistung zu versteuern; bei gemischten Sätzen
    also im Verhältnis der Positionen. Sie dem höchsten Satz zuzuschlagen wäre zu viel
    Steuer, dem niedrigsten zu wenig – beides ist falsch, und beides fällt erst bei der
    Abrechnung auf.

    **Der letzte Anteil bekommt den Rest**: sonst fehlt oder überschiesst ein Rappen, und
    die Summe der Zeilen wäre nicht der Betrag der Rechnung – ein Beleg, der sich selbst
    widerspricht.

    Bug-Formen: (a) alles auf einen Satz; (b) die Zeilen summieren nicht auf den Betrag.
    """
    from app.domain import deal as dm

    lines = [
        {"article": 1, "quantity": 6, "price": "10.00", "vat": "8.10"},
        {"article": 2, "quantity": 2, "price": "50.00", "vat": "0.00"},
    ]
    rows = dm.split_for(Decimal("80.00"), lines, "CHF")
    assert len(rows) == 2, "Die Teilrechnung kennt nur einen Satz (a)."
    total = sum(Decimal(r["net"]) + Decimal(r["tax"]) for r in rows)
    assert total == Decimal("80.00"), (
        f"Die Zeilen summieren auf {total}, die Rechnung lautet über 80.00 (b)."
    )

    # **Ohne Positionen nennt der Aufrufer den Satz** – eine *Ausgabe*: die Steuer steht
    # auf seiner Rechnung, und wir schreiben sie ab.
    at = dm.split_at(Decimal("108.10"), "8.10", "CHF")
    assert at == [{"rate": "8.10", "net": "100.00", "tax": "8.10"}], (
        "Aus einem Brutto-Betrag wird der Netto-Anteil nicht zurückgerechnet."
    )


def test_an_unknown_rate_is_refused_when_written_and_tolerated_when_read():
    """**Streng schreiben, tolerant lesen** – dieselbe Regel wie bei der Richtung.

    Ein getippter Satz ist einer, den es nicht gibt, und er fällt erst bei der Abrechnung
    auf: darum weist ``assert_vat`` ab. **Gelesen** wird tolerant – ein Wert, den es nicht
    geben dürfte, darf keine Anzeige eines laufenden Auftrags zerlegen.
    """
    from app.domain import deal as dm

    with pytest.raises(ValueError):
        dm.assert_vat("7.70")          # der alte Normalsatz – es gibt ihn nicht mehr
    with pytest.raises(ValueError):
        dm.assert_vat("acht Prozent")
    assert dm.assert_vat("8.10") == "8.10"
    # Tolerant gelesen: unlesbar heisst **0 %**, nicht «Absturz».
    assert dm.vat_of("7.70") == Decimal("7.70")
    assert dm.vat_of(None) == Decimal("0")
    assert dm.vat_of("was?") == Decimal("0")


def test_the_door_lets_the_positions_through():
    """►►► **Ein Feld, das die Tür nicht kennt, kommt NIE an.** ◄◄◄

    Pydantic verwirft unbekannte Felder stillschweigend – dieselbe Falle wie damals bei
    ``ModuleConfigInput`` (``mode`` und ``sample`` kamen nie an, ohne eine einzige
    Fehlermeldung). Ein Dienst, der ``lines`` liest, und eine Tür, die sie wegwirft, sind
    ein Fehler, den **kein** Dienst-Test findet: er ruft ``apply`` direkt.

    Geprüft wird darum die **Tür** (``DealUpdate``), nicht der Dienst.

    Bug-Form: eines der drei Felder fehlt im Schema.
    """
    from app.schemas.deal import DealUpdate

    sent = DealUpdate.model_validate({
        "action": "charge", "amount": "100.00", "vat": "2.60",
        "service_date": "2026-08-20",
        "lines": [{"article": None, "price": "10.00", "vat": "8.10"}],
    })
    changes = sent.changes()
    assert changes["vat"] == "2.60", "Der Steuersatz kommt an der Tür nicht an."
    assert str(changes["service_date"]) == "2026-08-20", (
        "Das Leistungsdatum kommt an der Tür nicht an."
    )
    assert changes["lines"] == [{"article": None, "price": "10.00", "vat": "8.10"}], (
        "Die Positionen kommen an der Tür nicht an – der Preis eines Angebots ginge "
        "stillschweigend verloren."
    )
    # **Nur gesendete Felder wirken**: was nicht mitkommt, steht auch nicht in `changes`.
    assert "lines" not in DealUpdate.model_validate({"action": "pay"}).changes()


def test_a_booked_document_keeps_its_tax_statement():
    """►►► **Die Steuer-Angabe wird GESPEICHERT, nicht nachgerechnet.** ◄◄◄

    Ein gebuchter Beleg behält, was auf ihm stand – auch wenn der Vorgang später andere
    Positionen trägt oder der Gesetzgeber den Satz ändert. Nachgerechnet wäre die
    Vergangenheit eine Funktion der Gegenwart, und eine Abrechnung über ein
    abgeschlossenes Quartal ergäbe beim zweiten Lauf andere Zahlen.

    **Und der Storno spiegelt sie**: die Gegenbuchung trägt dieselben Sätze mit negativem
    Vorzeichen – sonst nähme sie den Betrag zurück und die Steuer nicht.

    Bug-Formen: (a) die Zeile trägt keine Steuer; (b) der Storno trägt keine oder eine
    positive.
    """
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)
        step = rows[0]
        _agree(db, order=order, step=step, party=kunde, amount="100.00")
        svc.apply(db, order=order, step=step, action="charge",
                  payload={"amount": "108.10", "vat": "8.10",
                           "service_date": "2026-08-20"})
        row = svc.of_step(db, step.id)
        bill = svc._entries(db, row.id)[0]
        assert bill.vat, "Die gebuchte Forderung trägt keine Steuer-Angabe (a)."
        assert str(bill.service_date) == "2026-08-20", "Das Leistungsdatum fehlt."

        svc.apply(db, order=order, step=step, action="reverse", payload={"entry": bill.id})
        storno = [e for e in svc._entries(db, row.id) if e.reverses_id == bill.id][0]
        assert storno.vat, "Der Storno trägt keine Steuer-Angabe (b)."
        assert all(Decimal(v["tax"]) <= 0 and Decimal(v["net"]) <= 0 for v in storno.vat), (
            "Der Storno nimmt den Betrag zurück, die Steuer aber nicht (b)."
        )
    finally:
        db.rollback(); db.close()


def test_the_amount_of_an_offer_is_the_sum_of_its_positions():
    """►►► **Wo WIR den Preis nennen, ist der Betrag eine SUMME, keine Eingabe.** ◄◄◄

    Ein getippter Betrag neben gepreisten Positionen wäre die zweite Aussage über
    dieselbe Sache – und die getippte gewinnt, auch wenn sie falsch ist. Der Angebots-
    betrag ist darum die **Brutto**-Summe der Positionen (Netto + Steuer je Satz).

    **Die Menge kommt aus dem Prozess**, nicht aus der Nutzlast: sie ist die Zahl der
    Einzelinstanzen, die vor dem Modul stehen.

    Bug-Formen: (a) der Betrag ist netto; (b) die Menge wird aus der Nutzlast gelesen.
    """
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=2, article=art)
        step = rows[0]
        svc.apply(db, order=order, step=step, action="ask", payload={
            "parties": [kunde.object_id],
            # **Keine Menge in der Nutzlast** – zwei Wellen stehen vor dem Modul.
            "lines": [{"article": art.id, "price": "100.00", "vat": "8.10"}],
        }, actor=_staff(db))
        row = svc.of_step(db, step.id)
        quote = row.quotes[0]
        assert quote["amount"] == "216.20", (
            f"Der Angebotsbetrag lautet {quote['amount']} – erwartet 2 × 100.00 netto "
            f"plus 8.1 % = 216.20. (a) netto statt brutto, oder (b) die Menge kam nicht "
            f"aus dem Prozess."
        )
    finally:
        db.rollback(); db.close()


def test_a_term_only_change_keeps_the_price():
    """►►► **Nur gesendete Felder wirken – auch für den Betrag.** ◄◄◄

    Wer nur eine **Frist** nachreicht, nennt keinen Preis: bei einer Einnahme steht er in
    den Positionen, bei einer Ausgabe in der Zeile, die die Gegenpartei gefüllt hat. War
    der Preis bei jedem Aufruf Pflicht, liess sich die Frist an einer bereits offerierten
    Zeile nicht mehr ändern, ohne den Preis erneut zu behaupten – und bei einer Einnahme
    gar nicht, weil dort ein gesendeter Betrag **ignoriert** wird.

    **Und ohne jeden Preis bleibt es ein Fehler**: das ist keine Aufweichung der Regel,
    sondern ihre genaue Fassung.

    Bug-Formen: (a) die Frist-Änderung wird abgewiesen; (b) sie löscht den Preis;
    (c) eine Zeile ganz ohne Preis geht durch.
    """
    from fastapi import HTTPException
    from app.services import deal as svc
    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)
        step = rows[0]
        staff = _staff(db)
        svc.apply(db, order=order, step=step, action="ask", payload={
            "parties": [kunde.object_id],
            "lines": [{"article": art.id, "price": "100.00", "vat": "0.00"}],
        }, actor=staff)
        row = svc.of_step(db, step.id)
        assert row.quotes[0]["amount"] == "100.00"

        # (a)/(b) **Nur die Frist** – der Preis bleibt.
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": kunde.object_id, "payment_days": 60}, actor=staff)
        row = svc.of_step(db, step.id)
        assert row.quotes[0]["amount"] == "100.00", (
            "Die Frist-Änderung hat den Preis überschrieben (b)."
        )
        assert row.quotes[0]["payment_days"] == 60

        # (c) **Ohne jeden Preis bleibt es ein Fehler.**
        andere = _party(db, "Huber AG", role="customer")
        art2 = _article(db, "Buchse",
                        steps=[_money_step(direction="out", parties=[andere])])
        order2, rows2 = _make(db, quantity=1, article=art2)
        svc.apply(db, order=order2, step=rows2[0], action="ask",
                  payload={"parties": [andere.object_id]}, actor=staff)
        with pytest.raises(HTTPException) as err:
            svc.apply(db, order=order2, step=rows2[0], action="quote",
                      payload={"party": andere.object_id, "lead_days": 5}, actor=staff)
        assert err.value.status_code == 400 and "Betrag" in err.value.detail
    finally:
        db.rollback(); db.close()


# ---------------------------------------------------------------------------
# §9.12a – die WÄHRUNG: eine je Vorgang, gebunden mit der Zusage
# ---------------------------------------------------------------------------

def test_a_currency_is_one_per_deal_and_freezes_with_the_agreement():
    """►►► **Ein Betrag ohne Währung ist keine Zahl.** ◄◄◄

    «1000» ist tausend Franken oder tausend Yen, und das sind zwei sehr verschiedene
    Beträge. Solange nur eine Währung vorkommt, fällt es nicht auf – und beim ersten
    EU-Kunden ist es still falsch.

    **Eine je Vorgang, nicht je Zeile**: zwei Währungen auf einem Beleg gibt es nicht,
    das wären zwei Belege. Vorbelegt ist die Währung des **Betreibers**; änderbar bis zur
    Zusage, danach nicht mehr – draussen liegt dann eine Zusage über *diese* Summe in
    *dieser* Währung, und sie nachträglich umzuschreiben hiesse, die Zahl stehen zu
    lassen und ihre Bedeutung zu ändern.

    **Und ``can`` ist das Tor**, nicht nur die Auskunft: dieselbe Tabelle, aus der die
    Oberfläche ihren Knopf nimmt, weist in ``apply`` ab.

    Bug-Formen: (a) die Währung fehlt am Vorgang; (b) sie lässt sich nach der Zusage noch
    ändern; (c) ``can`` führt das Verb, obwohl der Dienst es abweisen würde (oder
    umgekehrt) – dann ist der Knopf eine Bitte.
    """
    from fastapi import HTTPException
    from app.domain import currency as cur
    from app.services import deal as svc

    db = _db()
    try:
        lieferant = _party(db, "Härterei AG")
        art = _article(db, "Welle", steps=[_money_step(parties=[lieferant])])
        order, rows = _make(db, quantity=2, article=art)
        step = rows[0]
        row = svc.of_step(db, step.id)
        staff = _staff(db)

        # (a) **Sie ist da** – und sie ist die des Hauses, nicht eine erfundene.
        assert row.currency == svc.house_currency(db), (
            "Der Vorgang trägt nicht die Währung des Betreibers (a) – dann steht dort "
            "eine Zahl, deren Bedeutung niemand kennt."
        )
        assert "currency" in svc.can(db, row, staff), (
            "Vor der Zusage lässt sich die Währung nicht wählen."
        )

        svc.apply(db, order=order, step=step, action="currency",
                  payload={"currency": "eur"}, actor=staff)
        assert row.currency == "EUR", "Die Wahl kommt nicht an (Gross-/Kleinschreibung)."

        # **Streng geschrieben** – ein Code, den es nicht gibt, fällt sonst erst auf,
        # wenn jemand eine Summe über zwei Währungen zieht.
        with pytest.raises(HTTPException) as unknown:
            svc.apply(db, order=order, step=step, action="currency",
                      payload={"currency": "XXX"}, actor=staff)
        assert unknown.value.status_code == 400
        assert "CHF" in unknown.value.detail, (
            "Die Ablehnung nennt die erlaubten Währungen nicht – dann ist sie eine "
            "Sackgasse mit Ausrufezeichen."
        )

        # (b) + (c) **Ab der Zusage ist sie gebunden** – in beiden Formen.
        _agree(db, order=order, step=step, party=lieferant, amount="1200.00", staff=staff)
        assert "currency" not in svc.can(db, row, staff), (
            "Die Währung steht nach der Zusage noch zur Wahl (b/c)."
        )
        with pytest.raises(HTTPException) as locked:
            svc.apply(db, order=order, step=step, action="currency",
                      payload={"currency": "USD"}, actor=staff)
        assert locked.value.status_code == 409, (
            "Die Tür lässt die Änderung durch (b) – dann ist `can` nur ein Hinweis, und "
            "der Knopf und das Tor laufen beim nächsten Verb auseinander."
        )
        assert row.currency == "EUR"

        # **Und sie reist mit der Antwort** – die Oberfläche rechnet nichts aus.
        embed = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert embed["currency"] == "EUR"
        assert embed["currency_decimals"] == cur.minor_units("EUR") == 2
        assert embed["currency_locked"] is True
        assert {c["code"] for c in embed["currencies"]} == set(cur.CURRENCIES)
    finally:
        db.rollback()
        db.close()


def test_the_decimals_come_from_the_currency_never_from_a_fixed_two():
    """►►► **JPY hat null Nachkommastellen, KWD hat drei** (ISO 4217). ◄◄◄

    Fast alle haben zwei – und darum schreibt man ``f"{x:.2f}"`` und merkt nie, dass es
    falsch ist. Ein Yen-Betrag mit zwei Nachkommastellen ist kein Rundungsfehler, sondern
    ein Betrag, den es nicht gibt; ein dreistelliger, auf zwei geschnitten, verliert
    still seine letzte Stelle – und zwar in der Richtung, in der die Zahl **kleiner**
    wird.

    Geprüft wird **die Rechnung**, nicht nur die Formatierung: die Steuer-Aufteilung
    rundet je Währung (``domain/deal._round``), und der gebuchte Betrag kommt mit der
    Genauigkeit seiner Währung an.

    Bug-Formen: (a) ein festes ``.2f`` in der Formatierung; (b) ein festes ``0.01`` beim
    Runden – dann stimmt die Anzeige und die Buchung nicht; (c) die Spalte schneidet ab
    (``NUMERIC(x, 2)``) – dann ist der Wert schon in der Datenbank falsch.
    """
    from decimal import Decimal
    from app.domain import currency as cur, deal as dm

    # (a) **Die Formatierung** kennt die Währung.
    assert cur.money(Decimal("1000.40"), "JPY") == "1000", (
        "Ein Yen-Betrag trägt Nachkommastellen (a) – die es in dieser Währung nicht gibt."
    )
    assert cur.money(Decimal("1.2345"), "KWD") == "1.235", (
        "Ein dreistelliger Betrag wird auf zwei geschnitten (a)."
    )
    assert cur.money(Decimal("12.345"), "CHF") == "12.35"

    # (b) **Die Rechnung** ebenso – dieselbe Zahl, zwei Währungen, zwei Ergebnisse.
    lines = [{"article": 1, "quantity": 3, "price": "1000", "vat": "8.10"}]
    assert dm.vat_split(lines, "JPY") == [{"rate": "8.10", "net": "3000", "tax": "243"}], (
        "Die Steuer wird nicht in der Genauigkeit der Währung gerechnet (b)."
    )
    assert dm.vat_split(lines, "CHF")[0]["tax"] == "243.00"

    # (c) **Und die Spalte trägt es** – vier Stellen decken jede ISO-4217-Währung.
    from app.models import Deal, DealEntry
    for model in (Deal, DealEntry):
        col = model.__table__.c["amount"]
        assert col.type.scale >= 3, (
            f"{model.__tablename__}.amount hat nur {col.type.scale} Nachkommastellen (c) "
            f"– ein dreistelliger Betrag verlöre seine letzte, und zwar in der Datenbank."
        )


def test_the_service_date_comes_from_the_process_not_from_the_invoice_date():
    """►►► **Wann wurde die Leistung erbracht?** – das weiss der Auftrag (Testnotiz #852).

    Es ist der Tag, an dem die Stücke dieses Modul **erreicht** haben. Das
    Rechnungsdatum ist es **nicht**: eine Rechnung, die zwei Wochen später geschrieben
    wird, verschöbe damit die Steuerperiode (MWSTG Art. 26 Bst. c).

    **Vorbelegt, nicht erzwungen** – ein Mensch weiss von Teilleistungen, von denen der
    Log nichts weiss. Und **abgeleitet, nicht gespeichert**: eine Spalte daneben wäre die
    zweite Wahrheit.

    Bug-Formen: (a) die Antwort trägt das Datum nicht – dann muss die Oberfläche es
    erfinden oder leer lassen; (b) eine gesendete Angabe wird überschrieben.
    """
    from datetime import date
    from app.domain import deal as dm
    from app.models import DealEntry
    from app.services import deal as svc

    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[
            {"module_type": "datenerfassung",
             "config": {"points": [{"label": "OK", "type": "bool"}]}},
            _money_step(direction="in", parties=[kunde]),
        ])
        order, rows = _make(db, quantity=2, article=art)
        staff = _staff(db)

        # Noch steht nichts am Geld-Modul – dann gibt es auch nichts vorzubelegen.
        assert svc.service_day(db, rows[1]) is None, (
            "Ein Datum entsteht aus dem Nichts – dann behauptet die Vorbelegung etwas."
        )

        # Die Stücke erreichen das Geld-Modul – über den echten Weg, mit Werten je Stück.
        from app.domain import modules as mods
        from app.services import process as proc
        from tests.support import per_unit
        while True:
            work = proc.step_work(db, order, rows[0])
            if not work:
                break
            inst = work[0]["instance_object_id"]
            proc.confirm_step(
                db, order=order, step_id=rows[0].id, actor_id=None, verification="scan",
                instance_object_id=inst,
                values=per_unit(db, order=order, step=rows[0], instance_object_id=inst,
                                values={p["key"]: True
                                        for p in mods.points_of(rows[0].config)}),
            )
            db.flush()
        arrived = svc.service_day(db, rows[1])
        assert arrived == date.today(), (
            "Das Leistungsdatum kommt nicht aus dem Prozess (a)."
        )
        embed = svc.embed_data(db, order=order, step=rows[1], viewer=staff)
        assert embed["service_date"] == arrived, (
            "Es reist nicht mit der Antwort (a) – dann erfindet es die Oberfläche."
        )

        _agree(db, order=order, step=rows[1], party=kunde, amount="500.00", staff=staff)
        svc.apply(db, order=order, step=rows[1], action="charge",
                  payload={"amount": "500.00"}, actor=staff)
        db.flush()
        booked = (db.query(DealEntry)
                  .filter(DealEntry.deal_id == svc.of_step(db, rows[1].id).id,
                          DealEntry.kind == dm.CHARGE).one())
        assert booked.service_date == arrived

        # (b) **Ein Mensch darf übersteuern** – er weiss von Teilleistungen.
        svc.apply(db, order=order, step=rows[1], action="charge",
                  payload={"amount": "1.00", "service_date": "2026-01-31"}, actor=staff)
        db.flush()
        rows_out = (db.query(DealEntry)
                    .filter(DealEntry.deal_id == svc.of_step(db, rows[1].id).id,
                            DealEntry.kind == dm.CHARGE)
                    .order_by(DealEntry.id).all())
        assert rows_out[-1].service_date == date(2026, 1, 31), (
            "Die gesendete Angabe wird überschrieben (b) – dann ist die Vorbelegung "
            "eine Vorschrift."
        )
    finally:
        db.rollback()
        db.close()


def test_the_module_no_longer_carries_a_tax_rate():
    """►►► **Der Steuersatz hängt an der SACHE, nicht am Modul** (Testnotiz #851). ◄◄◄

    Er stand als «Vorgabe jeder neuen Position» in der Definition und war damit eine
    Eigenschaft des **Moduls**: eine Vorlage, die für jeden künftigen Auftrag denselben
    Satz behauptet. Sechs Wellen zu 8.1 % und eine Ausfuhr zu 0 % stehen aber auf
    demselben Papier, und *welche* Sache gehandelt wird, steht erst fest, wenn ein
    Auftrag läuft.

    Gefragt wird er darum **je Position an der Ausführungsstelle**; die Vorbelegung ist
    der Normalsatz. Ein Wert, der trotzdem gesendet wird, wird **verworfen** – ein Feld,
    das die Oberfläche nicht anbietet, der Dienst aber annimmt, wäre eine Hintertür zu
    einer Angabe, die niemand liest.

    Bug-Form: ``vat_rate`` steht wieder in der Konfiguration – dann gibt es die Angabe an
    zwei Orten, und die im Modul gewinnt bei jedem neuen Auftrag.
    """
    from app.domain import deal as dm, modules
    from app.services import deal as svc

    clean = modules.get("zahlung").clean_config(
        {"direction": "in", "parties": [], "prepaid": False, "vat_rate": "2.60"})
    assert "vat_rate" not in clean, (
        "Der Steuersatz ist als Modul-Angabe zurück – dann behauptet eine Vorlage einen "
        "Satz für Sachen, die es beim Modellieren noch gar nicht gibt (#851)."
    )
    assert not hasattr(modules, "vat_rate"), (
        "Es gibt wieder eine Lesestelle für einen Modul-Steuersatz."
    )

    db = _db()
    try:
        kunde = _party(db, "Meier AG", role="customer")
        art = _article(db, "Welle", steps=[_money_step(direction="in", parties=[kunde])])
        order, rows = _make(db, quantity=1, article=art)
        embed = svc.embed_data(db, order=order, step=rows[0], viewer=_staff(db))
        assert embed["vat_rate"] == dm.DEFAULT_VAT, (
            "Die Vorbelegung an der Ausführungsstelle kommt nicht mehr aus dem Katalog."
        )
        assert [r["rate"] for r in embed["vat_rates"]] == [r for r, _ in dm.VAT_RATES], (
            "Der Katalog reist nicht mehr mit dem Vorgang – dann pflegt die Oberfläche "
            "eine zweite Liste."
        )
    finally:
        db.rollback()
        db.close()
