"""**Der Beleg — das neu aufgebaute Zahlungsmodul.**

Die Regeln, die hier geprüft werden, sind die aus ``docs/neuaufbau-zahlungsmodul.md``.
Fachlich dieselben wie beim Vorgänger (``domain/deal``); **neu sind die drei Formen**, und
genau die prüft dieser Wächter:

1. ►►► **Ein Verb hat EINE Deklaration** (``VERBS``). ◄◄◄ Beim Vorgänger stand es an vier
   Stellen (``ACTIONS`` · ``REQUIRED_FOR``/``_UP_TO`` · ``HANDLERS`` ·
   ``Direction.party_actions``), und die vierte bekam ein neues Verb nicht mit.
2. ►►► **Der Angebotsspiegel ist eine Tabelle**, keine Liste an einem Feld.
3. ►►► **Die Position gibt es in EINER Form** – eingefroren wird durch die **Stufe**.

Dazu drei Spalten, die **Ableitungen** geworden sind (*mit wem · was vereinbart ist ·
welche Zahlungsfrist*): am Vorgänger standen sie neben der gewählten Angebotszeile, und
derselbe Beleg konnte damit zwei Dinge sagen.

Und die eine Regel, die alles zusammenhält: **es bewegt keine Stücke.**

Geprüft über die **echten** Dienstpfade gegen echtes PostgreSQL.
"""

import os
import pathlib
import uuid
from decimal import Decimal

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]


# ═══════════════════════════════════════════════════════════════════════════════
# ►► DIE SZENE — ein Haus, ein Partner, ein Auftrag mit einem Beleg-Modul
# ═══════════════════════════════════════════════════════════════════════════════

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
        db = SessionLocal()
        _house(db)
        return db
    except Exception as exc:  # pragma: no cover - reine Umgebungsfrage
        pytest.skip(f"Kein PostgreSQL erreichbar ({type(exc).__name__}: {exc}) – "
                    f"DATABASE_URL setzen, damit diese Regeln wirklich laufen.")


def _house(db):
    """**Ein Haus, das Belege stellen kann.**

    Seit das Modul seine Vollständigkeit selbst meldet (``gaps``), ist eine Gesellschaft
    ohne Anschrift, Rechtsform, Kontaktweg und MWST-Nummer kein Betrieb, der eine Offerte
    schreiben darf – genau das ist die Regel, nicht ein Fixture-Detail.
    """
    from app.models import CompanySettings
    from app.services import objects as obj, sites
    house = sites.find_operator(db)
    if house is None:
        house = CompanySettings(is_operator=True, object_id=obj.next_object_id(db))
        db.add(house)
    house.company_name = house.company_name or "Inexxio"
    house.legal_form = house.legal_form or "AG"
    house.street = house.street or "Bahnhofstrasse"
    house.street_nr = house.street_nr or "1"
    house.zip_code = house.zip_code or "8001"
    house.city = house.city or "Zürich"
    house.country = house.country or "CH"
    house.vat_number = house.vat_number or "CHE-100.200.300 MWST"
    house.email = house.email or "rechnung@inexxio.test"
    house.iban_encrypted = house.iban_encrypted or "CH9300762011623852957"
    db.flush()
    return house


def _party(db, name: str, role: str = "supplier"):
    from app.models import UserProfile
    from app.services import objects as obj
    user = UserProfile(
        firebase_uid=f"test-{uuid.uuid4()}", email=f"{uuid.uuid4()}@example.test",
        company_name=name, role=role, object_id=obj.next_object_id(db),
        address_line1="Werkweg 3", postal_code="9000", city="St. Gallen", country="CH",
    )
    db.add(user)
    db.flush()
    return user


def _article(db, name: str, *, steps=None):
    """Ein Artikel **mit** Erzeugungsprozess – «Neu» ist sonst gar nicht wählbar.

    **Der Erzeugungsprozess IST der Prozess des Auftrags** (die Freigabe friert ihn ein),
    also steht das Beleg-Modul hier und nicht am Auftrag. Eine Datenerfassung mit einem
    Punkt davor ist der kürzeste gültige Anfang.
    """
    from app.models import Article
    from app.services import article_process as tpl, objects as obj
    art = Article(object_id=obj.next_object_id(db), name=name, unit="stk",
                  serialization="batch")
    db.add(art)
    db.flush()
    tpl.create_steps(db, art, [
        {"module_type": "datenerfassung",
         "config": {"points": [{"label": "Sichtprüfung", "type": "bool"}]}},
        *(steps or []),
    ])
    db.flush()
    return art


def _step(*, direction: str = "in", parties=(), task: str = "Härten auf 58 HRC") -> dict:
    """Ein Beleg-Modul – **zwei** Angaben, mehr gibt es nicht."""
    return {"module_type": "beleg",
            "config": {"direction": direction,
                       "parties": [{"party": p.object_id, "ref": task} for p in parties]}}


def _order(db, *, quantity: int, article, steps=None, actor=None):
    """Ein freigegebener Erzeugungsauftrag über diesen Artikel."""
    from app.models import ProcessStep
    from app.services import process as proc
    order = proc.release(
        db,
        lines=[{"article_object_id": article.object_id, "quantity": quantity,
                "origin": "neu", "units": []}],
        steps=steps or [], actor_id=getattr(actor, "id", None),
    )
    db.flush()
    rows = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
            .order_by(ProcessStep.position).all())
    return order, rows


def _scene(db, *, direction: str = "in", quantity: int = 3, parties=None):
    """Ein Auftrag mit **einem** Beleg-Modul – die Szene fast jeder Prüfung hier."""
    from app.services import voucher as svc
    who = parties if parties is not None else [_party(db, "Muster AG", "customer")]
    art = _article(db, f"Welle {uuid.uuid4().hex[:6]}",
                   steps=[_step(direction=direction, parties=who)])
    order, steps = _order(db, quantity=quantity, article=art)
    step = next(s for s in steps if s.module_type == "beleg")
    row = svc.of_step(db, step.id)
    assert row is not None, "Die Freigabe hat keinen Beleg angelegt."
    return order, step, row, who, art


def _price(db, order, step, row, *, price: str = "100.00", vat: str = "normal"):
    """Jede Position bepreisen – das ist ein **eigenes** Verb (`price`), kein `ask`."""
    from app.services import voucher as svc
    lines = svc.sync_lines(db, row, order)
    svc.apply(db, order=order, step=step, action="price",
              payload={"lines": [{"id": ln.id, "price": price, "vat": vat}
                                 for ln in lines]})
    db.flush()


# ═══════════════════════════════════════════════════════════════════════════════
# ►► §1 – EIN VERB HAT EINE DEKLARATION
# ═══════════════════════════════════════════════════════════════════════════════

def _code(path: pathlib.Path) -> str:
    """Der **Code**, ohne Docstrings und Kommentare.

    Ein Wächter, der die Prosa mitliest, schlägt an, weil jemand den Fehler *beschreibt*,
    den er verhindern soll – das ist im Haus schon mehrfach passiert.
    """
    import ast
    src = path.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                             ast.Module)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                src = src.replace(doc, "")
    return "\n".join(l.split("#")[0] for l in src.splitlines())


def test_a_verb_is_declared_in_exactly_one_place():
    """►►► **Vier Fragen über ein Verb stehen in EINER Zeile.** ◄◄◄

    *In welcher Stufe · welche Stammdaten · wer darf · welche Funktion* – beim Vorgänger
    waren das vier Tabellen an vier Stellen, und die hinzugefügte Zeile in der vierten
    vergass man. Hier ist es ``VERBS``.

    Bug-Formen: (a) eine zweite Tabelle steht daneben; (b) ein Verb fehlt in ``VERBS``,
    wird aber trotzdem irgendwo geprüft; (c) ``can`` liest etwas anderes als ``VERBS``.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc

    code = _code(BACKEND / "app" / "services" / "voucher.py")
    for gone in ("ACTIONS", "HANDLERS", "_UP_TO", "party_actions"):
        assert f"{gone}:" not in code and f"{gone} =" not in code, (
            f"«{gone}» steht wieder als eigene Tabelle da (a) – vier Stellen für ein Verb "
            f"sind genau die Form, in der die vierte ein neues nicht mitbekommt."
        )
    # (b) **Jedes Verb, das irgendwo vorkommt, steht in `VERBS`.**
    for verb in ("ask", "quote", "decline", "agree", "revoke", "charge", "pay",
                 "reverse", "price", "currency", "issuer", "incoterm",
                 "pay_online", "refund_online"):
        assert verb in svc.VERBS, f"«{verb}» fehlt in VERBS (b)."
    # (c) **`can` liest genau diese Tabelle** – geprüft an der Stufe, nicht am Namen.
    for key, verb in svc.VERBS.items():
        assert verb.stages, f"«{key}» gilt in keiner Stufe (b)."
        for stage in verb.stages:
            assert stage in ("offer", "agreed", "done", "cancelled"), (
                f"«{key}» nennt die Stufe «{stage}», die es nicht gibt (b)."
            )


def test_who_may_act_follows_from_who_names_the_price():
    """►►► **Wer den Preis empfängt, nimmt an oder lehnt ab – er offeriert nicht.** ◄◄◄

    Die Regel steht am **Verb** (``Verb.party``) und wird gegen die Richtung ausgewertet;
    beim Vorgänger war sie eine eigene Ableitung an der Richtung.

    Bug-Formen: (a) die Gegenpartei darf bei einer Einnahme unseren Preis überschreiben;
    (b) sie darf bei einer Ausgabe zusagen (der Zuschlag ist unsere Entscheidung);
    (c) absagen darf sie in einer Richtung nicht.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo
    from app.services import voucher as svc

    income, expense = vo.of("in"), vo.of("out")
    assert not svc.VERBS["quote"].allows(income), (
        "Die Gegenpartei darf unseren Preis überschreiben (a) – das wäre eine "
        "Gegenofferte, und die ist ein neuer Beleg."
    )
    assert svc.VERBS["quote"].allows(expense), "Der Lieferant darf nicht offerieren."
    assert svc.VERBS["agree"].allows(income), "Der Kunde darf unser Angebot nicht annehmen."
    assert not svc.VERBS["agree"].allows(expense), (
        "Der Lieferant gibt sich selbst den Zuschlag (b)."
    )
    for flow in (income, expense):
        assert svc.VERBS["decline"].allows(flow), (
            "Absagen ist die eine Antwort, die in beide Richtungen dasselbe bedeutet (c)."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ►► §2 – DIE DREI FORMEN, DIE NEU SIND
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_offer_mirror_is_a_table_not_a_field():
    """►►► **Eine Angebotszeile ist eine Sache, keine Eigenschaft.** ◄◄◄

    Sie hat Zustand, Datum, Betrag und zwei Fristen. Als JSONB an der Kopfzeile musste die
    ganze Liste bei jeder Änderung neu gebaut werden (ein mutierter Wert fällt still aus
    dem ``UPDATE``), und «woran ist dieser Betrachter beteiligt?» war eine
    Containment-Abfrage.

    Bug-Formen: (a) ``quotes`` ist wieder eine Spalte; (b) eine Änderung an einer Zeile
    kommt nicht an; (c) ``mine`` findet die Gegenpartei nicht.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.models import Voucher
    from app.services import voucher as svc

    assert not hasattr(Voucher, "quotes"), (
        "Der Angebotsspiegel steht wieder als Feld am Beleg (a)."
    )
    db = _db()
    try:
        order, step, row, who, _art = _scene(db, direction="out",
                                             parties=[_party(db, "Härterei AG")])
        svc.apply(db, order=order, step=step, action="ask", payload={})
        db.flush()
        rows = svc.quotes_of(db, row)
        assert len(rows) == 1 and rows[0].party_id == who[0].object_id
        # (b) **Eine Änderung an EINER Zeile kommt an** – ohne Neubau der ganzen Liste.
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": who[0].object_id, "amount": "84.00",
                           "lead_days": 5, "payment_days": 30})
        db.flush()
        db.expire_all()
        again = svc.quotes_of(db, row)[0]
        assert again.amount == Decimal("84.0000"), f"Die Offerte kam nicht an (b): {again.amount}."
        assert again.lead_days == 5 and again.payment_days == 30
        assert again.sent_on is not None, "Das Datum des Hinausgehens fehlt."
        # (c) **Beteiligt ist, wer angefragt wurde** – eine gewöhnliche JOIN-Bedingung.
        found = svc.mine(db, who[0])
        assert found is not None and [r.id for r in found] == [row.id], (
            "Die Gegenpartei findet ihren Beleg nicht (c)."
        )
    finally:
        db.rollback(); db.close()


def test_a_position_exists_in_exactly_one_form():
    """►►► **Die Position gibt es einmal — und die STUFE friert sie ein.** ◄◄◄

    Beim Vorgänger dreimal: abgeleitet · je Angebot kopiert · eingefroren. Hier ist es
    eine Tabelle, und ``sync_lines`` läuft nur, solange nichts zugesagt ist.

    Bug-Formen: (a) ``agreed_lines`` ist zurück; (b) ``sync_lines`` zieht auch nach der
    Zusage nach – dann ändert sich ein zugesagter Beleg, weil der Auftrag Stücke verliert;
    (c) ein getippter Preis geht beim Nachziehen verloren.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.models import Voucher
    from app.services import voucher as svc

    assert not hasattr(Voucher, "agreed_lines"), (
        "Die eingefrorene Kopie der Positionen ist zurück (a)."
    )
    db = _db()
    try:
        order, step, row, who, _art = _scene(db, quantity=4)
        lines = svc.sync_lines(db, row, order)
        assert len(lines) == 1 and lines[0].quantity == 4
        # (c) **Was ein Mensch eingetragen hat, überlebt das Nachziehen.**
        _price(db, order, step, row, price="25.00")
        again = svc.sync_lines(db, row, order)
        assert again[0].price == Decimal("25.0000"), (
            f"Der Preis ist beim Nachziehen verloren gegangen (c): {again[0].price}."
        )
        # (b) **Ab der Zusage steht es fest** – und das misst man nur, wenn der Prozess
        #     sich danach wirklich **ändert**: der Auftrag verliert Stücke (genau der
        #     Fall, um den es geht). Ohne diese Zeilen prüfte der Wächter gar nichts.
        svc.apply(db, order=order, step=step, action="ask", payload={
            "parties": [who[0].object_id], "lead_days": 5, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": who[0].object_id})
        db.flush()
        from app.models import OrderUnit
        from datetime import datetime, timezone
        gone = (db.query(OrderUnit)
                .filter(OrderUnit.order_id == order.id,
                        OrderUnit.released_at.is_(None)).all())
        for u in gone[:3]:
            u.released_at = datetime.now(timezone.utc)
        db.flush()
        assert sum(n for _a, n in svc.process_lines(db, order)) == 1, (
            "Der Auftrag hat seine Stücke nicht verloren – dann misst der Wächter nichts."
        )
        before = [(l.article_id, l.quantity) for l in svc.lines_of(db, row)]
        svc.sync_lines(db, row, order)
        db.flush()
        after = [(l.article_id, l.quantity) for l in svc.lines_of(db, row)]
        assert before == after == [(_art.id, 4)], (
            f"Die zugesagten Positionen ziehen weiter nach (b): {before} → {after}."
        )
    finally:
        db.rollback(); db.close()


def test_three_columns_became_derivations():
    """►►► **Mit wem · was vereinbart ist · welche Frist — sie stehen an der ZEILE.** ◄◄◄

    Als Spalten daneben wurden sie beim Zuschlag hineinkopiert, und derselbe Beleg konnte
    danach zwei Dinge sagen; eine eigene Regel musste den Widerspruch verhindern. Als
    Ableitung kann er **nicht entstehen**.

    Bug-Formen: (a) eine der drei Spalten ist zurück; (b) die Ableitung liest eine andere
    Zeile als die gewählte; (c) der Betrag weicht von der Summe der Positionen ab.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.models import Voucher
    from app.services import voucher as svc

    for gone in ("party_id", "amount", "due_days"):
        assert not hasattr(Voucher, gone), (
            f"«{gone}» steht wieder als Spalte am Beleg (a) – dann kann der Beleg "
            f"etwas anderes sagen als seine gewählte Angebotszeile."
        )
    db = _db()
    try:
        a, b = _party(db, "Kunde A", "customer"), _party(db, "Kunde B", "customer")
        order, step, row, _who, _art = _scene(db, quantity=3, parties=[a, b])
        _price(db, order, step, row, price="10.00")
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"lead_days": 5, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": b.object_id})
        db.flush()
        assert svc.party_of(db, row) == b.object_id, "Die Ableitung liest die falsche Zeile (b)."
        assert svc.due_days_of(db, row) == 30
        # (c) **Der Betrag IST die Brutto-Summe** – 3 × 10.00 zu 8.1 %.
        assert svc.agreed_amount(db, row) == Decimal("32.4300"), (
            f"Der zugesagte Betrag ist nicht die Summe der Positionen (c): "
            f"{svc.agreed_amount(db, row)}."
        )
    finally:
        db.rollback(); db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ►► §3 – DIE REGEL, DIE ALLES ZUSAMMENHÄLT
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_module_never_touches_a_single_unit():
    """►►► **Es bewegt keine Stücke** – daraus folgt die ganze Robustheit. ◄◄◄

    Ein Durchläufer (``Im Prozess`` → ``Im Prozess``), kein Ausgang, kein Ortswechsel,
    kein neuer Status. Genau deshalb muss **keine andere Regel im System** von ihm wissen.

    Bug-Formen: (a) es ist terminal; (b) es setzt einen anderen Nachher-Zustand;
    (c) es bewegt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules, statuses as st

    mod = modules.get("beleg")
    assert mod.terminal is False, "Der Beleg ist ein Ausgang geworden (a)."
    assert mod.status_before == st.IM_PROZESS and mod.status_after == st.IM_PROZESS, (
        "Der Beleg ändert den Zustand eines Stücks (b)."
    )
    assert mod.moves is False, "Der Beleg bewegt Stücke (c)."
    assert mod.requires_verification is False, (
        "Der Beleg verlangt einen Scan – es gibt nichts zu verifizieren."
    )


def test_it_does_not_import_a_line_of_the_old_module():
    """►►► **Die Unabhängigkeit IST die Anforderung.** ◄◄◄

    Das alte Zahlungsmodul soll eines Tages ersatzlos gelöscht werden können – dann darf
    hier keine Zeile zu ändern sein. Dieselbe Regel hat sich beim Löschen von «Beschaffen»
    und «Verkauf» schon einmal ausgezahlt.

    Bug-Form: ein Import aus ``deal``/``purchase``/``money``.
    """
    for name in ("app/domain/voucher.py", "app/services/voucher.py",
                 "app/models/voucher.py", "app/schemas/voucher.py"):
        code = _code(BACKEND / name)
        for forbidden in ("import deal", "from .deal", "from ..domain import deal",
                          "domain import deal", "purchase", "invoices", "payments",
                          "domain import money"):
            assert forbidden not in code, (
                f"{name} hängt an «{forbidden}» – dann kostet das Löschen des alten "
                f"Moduls hier eine Zeile, und genau das soll es nicht."
            )


def test_the_two_vat_catalogues_do_not_drift():
    """►►► **Die befristete Doppelung hat einen Wächter.** ◄◄◄

    Der Steuerkatalog steht in **beiden** Fachkernen (``domain/deal`` und
    ``domain/voucher``). Ein gemeinsames drittes Modul wäre ein Umbau an Code, der
    gelöscht werden soll, und würde die beiden genau dann koppeln, wenn sie unabhängig
    sein müssen – aber zwei Kataloge können auseinanderlaufen, und ein Satzwechsel des
    Gesetzgebers kommt selten genug, dass es niemand merkt.

    **Dieser Wächter stirbt mit dem alten Modul** – dann gibt es wieder genau eine Fassung.

    Bug-Form: ein Satz wird nur auf einer Seite geändert.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    old = BACKEND / "app" / "domain" / "deal.py"
    if not old.exists():
        pytest.skip("Das alte Zahlungsmodul ist gelöscht – die Doppelung ist damit weg.")
    from app.domain import deal as dm, voucher as vo
    mine = [(v.key, v.rate, v.label, v.note) for v in vo.VAT_RATES]
    theirs = [(v.key, v.rate, v.label, v.note) for v in dm.VAT_RATES]
    assert mine == theirs, (
        "Die beiden Steuerkataloge sind auseinandergelaufen – solange es beide Module "
        "gibt, muss ein Satzwechsel auf beiden Seiten stehen."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ►► §4 – DER GANZE WEG, ÜBER DIE ECHTEN DIENSTPFADE
# ═══════════════════════════════════════════════════════════════════════════════

def test_an_income_runs_from_offer_to_paid():
    """**Positionen bepreisen → anbieten → annehmen → Rechnung → Zahlung.**

    Gemessen über die echten Dienstpfade, nicht nachgestellt: die interessanten Fehler
    entstehen zwischen den Schritten.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, who, _art = _scene(db, direction="in", quantity=6)
        _price(db, order, step, row, price="50.00")
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"lead_days": 5, "payment_days": 30})
        db.flush()
        assert svc.quotes_of(db, row)[0].state == "offeriert", (
            "Wo WIR den Preis nennen, geht die Zeile offeriert hinaus."
        )
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": who[0].object_id})
        db.flush()
        assert row.stage == "agreed" and row.agreed_on is not None
        money = svc.balance_of(db, row)
        assert money.agreed == Decimal("324.3000"), f"6 × 50.00 + 8.1 % ≠ {money.agreed}."
        svc.apply(db, order=order, step=step, action="charge", payload={})
        db.flush()
        charge = svc.live_charge(db, row)
        assert charge is not None and charge.amount == Decimal("324.3000")
        assert charge.reference == f"{order.object_id}-1", (
            f"Die Rechnungsnummer trägt nicht ihr Suffix: {charge.reference}."
        )
        assert charge.vat, "Die Steuer-Aufteilung ist nicht eingefroren."
        svc.apply(db, order=order, step=step, action="pay", payload={"method": "cash"})
        db.flush()
        assert svc.balance_of(db, row).open == Decimal("0.0000"), "Offen nach Vollzahlung."
    finally:
        db.rollback(); db.close()


def test_an_expense_lets_the_other_side_name_the_price():
    """**Anfragen → seine Offerte → Zuschlag** – die Ausgabe-Seite, und sie ist eine
    andere **Abfolge**, keine zweite Maschine."""
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc
    db = _db()
    try:
        a, b = _party(db, "Härterei A"), _party(db, "Härterei B")
        order, step, row, _who, _art = _scene(db, direction="out", parties=[a, b])
        # ►►► **Auch MIT Preisen an den Positionen geht sie leer hinaus.** ◄◄◄ Die Preise
        # werden hier direkt an die Zeilen geschrieben, nicht über `price` – das Verb
        # schreibt bei einer Ausgabe zu Recht nichts. Ohne sie wäre die Bug-Form gar nicht
        # herstellbar, und der Wächter prüfte nichts: **wer den Preis nennt, sagt die
        # Richtung**, nicht der Zufall, dass gerade keiner dasteht.
        for ln in svc.sync_lines(db, row, order):
            ln.price = Decimal("40.00")
        db.flush()
        svc.apply(db, order=order, step=step, action="ask", payload={})
        db.flush()
        rows = svc.quotes_of(db, row)
        assert [q.state for q in rows] == ["angefragt", "angefragt"], (
            "Bei einer Ausgabe geht die Zeile LEER hinaus – das ist ihr Sinn."
        )
        assert all(q.amount is None for q in rows), (
            "Die Anfrage trägt einen Preis – bei einer Ausgabe nennt ihn die Gegenpartei."
        )
        for who, amount in ((a, "120.00"), (b, "99.00")):
            svc.apply(db, order=order, step=step, action="quote",
                      payload={"party": who.object_id, "amount": amount,
                               "lead_days": 7, "payment_days": 30})
        db.flush()
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": b.object_id})
        db.flush()
        assert svc.party_of(db, row) == b.object_id
        assert svc.agreed_amount(db, row) == Decimal("99.0000")
        assert [q.state for q in svc.quotes_of(db, row)] == ["offeriert", "gewaehlt"]
    finally:
        db.rollback(); db.close()


def test_can_is_the_gate_and_not_only_a_hint():
    """►►► **Dieselbe Liste rendert die Knöpfe und weist ab.** ◄◄◄

    Bug-Formen: (a) ``assert_allowed`` lässt etwas durch, das ``can`` nicht führt;
    (b) die Ablehnung kommt ohne Grund; (c) sie nennt bei einer fehlenden Angabe die
    Stufe statt der Angabe.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, _who, _art = _scene(db)
        allowed = svc.can(db, row, None)
        assert "revoke" not in allowed, "Stornieren geht vor der Zusage (a)."
        with pytest.raises(HTTPException) as e:
            svc.assert_allowed(db, row, "revoke", None)
        assert e.value.status_code == 409, "Die falsche Stufe ist ein 409 (c)."
        assert str(e.value.detail).strip(), "Ablehnung ohne Grund (b)."
        assert "Offerte" in str(e.value.detail), (
            "Der Satz nennt die Stufe nicht – «geht nicht» ohne «woran es liegt» ist "
            "eine Sackgasse mit Ausrufezeichen."
        )
    finally:
        db.rollback(); db.close()


def test_a_missing_master_record_is_a_line_not_a_state():
    """►►► **Fehlende Stammdaten sind `StepNeed` für Stammdaten.** ◄◄◄

    Die Freigabe geht, das Modul bewegt nichts, und die Zeile sagt **wo · was · warum**.
    Durchgesetzt über ``can``: der Knopf ist gar nicht da.

    Bug-Formen: (a) das Verb steht trotz Lücke in ``can``; (b) die Zeile nennt den
    Datensatz nicht; (c) eine Absage oder ein Storno wird mitgesperrt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import sites, voucher as svc
    db = _db()
    try:
        order, step, row, _who, _art = _scene(db)
        house = sites.find_operator(db)
        # **Ohne Kontaktweg landet jede Rückfrage im Telefonbuch** – eine der drei
        # Angaben, die eine Anfrage verlangt.
        house.email = ""
        house.phone = ""
        db.flush()
        rows = svc.gaps(db, row, action="ask")
        assert rows, "Ohne Kontaktweg meldet das Modul keine Lücke."
        assert rows[0]["record_object_id"], "Die Lücke nennt ihren Datensatz nicht (b)."
        assert rows[0]["why"].strip(), "Die Lücke sagt nicht, warum."
        allowed = svc.can(db, row, None)
        assert "ask" not in allowed, "Anfragen geht trotz fehlender Anschrift (a)."
        assert "decline" in allowed, (
            "Absagen ist mitgesperrt (c) – dann wäre eine halbe Anschrift eine Sackgasse."
        )
    finally:
        db.rollback(); db.close()


def test_a_charge_is_reversed_by_a_counter_entry_never_deleted():
    """►►► **Gelöscht wird nichts.** ◄◄◄ Eine Rechnungsnummer ist vergeben.

    Bug-Formen: (a) es gibt einen Löschweg; (b) die Gegenzeile kopiert die Nummer;
    (c) sie spiegelt die Steuer nicht; (d) eine Zahlung lässt sich stornieren.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, who, _art = _scene(db, quantity=2)
        _price(db, order, step, row, price="100.00")
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"lead_days": 0, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": who[0].object_id})
        svc.apply(db, order=order, step=step, action="charge", payload={})
        db.flush()
        first = svc.live_charge(db, row)
        assert first is not None
        # (a) **Es gibt keinen Löschweg** – die Verben sind eine Liste, kein Glaube.
        assert "void" not in svc.VERBS and "delete" not in svc.VERBS, (
            "Ein Löschweg ist zurück (a)."
        )
        svc.apply(db, order=order, step=step, action="reverse",
                  payload={"entry": first.id})
        db.flush()
        rows = svc.entries_of(db, row)
        back = next(e for e in rows if e.reverses_id == first.id)
        assert back.amount == -first.amount
        assert back.reference != first.reference, "Die Gegenzeile kopiert die Nummer (b)."
        assert back.vat and Decimal(back.vat[0]["net"]) < 0, (
            "Die Gegenbuchung spiegelt die Steuer nicht (c)."
        )
        assert svc.balance_of(db, row).charged == Decimal("0.0000")
        # **Und danach darf die nächste entstehen** – die Regel ist keine Sackgasse.
        assert svc.live_charge(db, row) is None
        # (d) **Eine Zahlung ist ein Ereignis, kein Beleg.**
        svc.apply(db, order=order, step=step, action="charge", payload={})
        svc.apply(db, order=order, step=step, action="pay", payload={"method": "cash"})
        db.flush()
        payment = next(e for e in svc.entries_of(db, row) if e.kind == "payment")
        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=order, step=step, action="reverse",
                      payload={"entry": payment.id})
        assert e.value.status_code == 409 and "zweite Zahlung" in str(e.value.detail), (
            "Eine Zahlung lässt sich stornieren (d) – und der Satz nennt nicht den Weg."
        )
    finally:
        db.rollback(); db.close()


def test_one_live_invoice_per_module():
    """►►► **Je Modul genau EINE offene Forderung** – und das ist keine Sackgasse. ◄◄◄

    Gesperrt ist die zweite **positive** Forderung; eine **Gutschrift** bleibt möglich,
    und was falsch ist, wird storniert und neu gestellt.

    Bug-Formen: (a) eine zweite Rechnung geht durch; (b) eine Gutschrift wird mitgesperrt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, who, _art = _scene(db, quantity=2)
        _price(db, order, step, row, price="100.00")
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"lead_days": 0, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": who[0].object_id})
        svc.apply(db, order=order, step=step, action="charge",
                  payload={"amount": "100.00"})
        db.flush()
        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=order, step=step, action="charge",
                      payload={"amount": "50.00"})
        assert e.value.status_code == 409, "Eine zweite Rechnung geht durch (a)."
        # (b) **Die Gutschrift bleibt** – sie ist eine Minderung, keine zweite Rechnung.
        svc.apply(db, order=order, step=step, action="charge",
                  payload={"amount": "-20.00"})
        db.flush()
        assert svc.balance_of(db, row).charged == Decimal("80.0000"), (
            "Die Gutschrift wurde mitgesperrt (b)."
        )
    finally:
        db.rollback(); db.close()


def test_a_counterparty_sees_its_own_line_and_no_foreign_price():
    """►►► **Wer nicht den Zuschlag hat, sieht ihn auch nicht.** ◄◄◄

    Gefiltert wird beim **Aufbau der Antwort**, nicht in der Oberfläche.

    Bug-Formen: (a) fremde Angebotszeilen; (b) der Name des Gewählten im Belegkopf;
    (c) Zahlen über Forderung und Geld; (d) die Freigabe-Liste (die Konkurrenzliste).
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc
    db = _db()
    try:
        a, b = _party(db, "Härterei A"), _party(db, "Härterei B")
        order, step, row, _who, _art = _scene(db, direction="out", parties=[a, b])
        svc.apply(db, order=order, step=step, action="ask", payload={})
        for who, amount in ((a, "120.00"), (b, "99.00")):
            svc.apply(db, order=order, step=step, action="quote",
                      payload={"party": who.object_id, "amount": amount,
                               "lead_days": 7, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": b.object_id})
        svc.apply(db, order=order, step=step, action="charge",
                  payload={"amount": "99.00", "vat": "normal"})
        db.flush()
        seen = svc.embed_data(db, order=order, step=step, viewer=a)
        assert seen is not None
        assert [q["party_object_id"] for q in seen["quotes"]] == [a.object_id], (
            "Der unterlegene Bieter sieht fremde Angebotszeilen (a)."
        )
        # **Bei einer Ausgabe ist die Gegenpartei der Leistungserbringer** – welche Seite
        # welche Rolle trägt, sagt die Richtung; geprüft wird darum die Seite, auf der der
        # Partner steht, nicht ein festes Wort.
        assert seen["supplier"]["name"] == "" and seen["supplier"]["object_id"] is None, (
            "Er liest den Namen des Gewählten im Belegkopf (b)."
        )
        assert seen["customer"]["name"], "Uns sieht jeder – ein Beleg ohne Aussteller ist keiner."
        assert seen["charged"] is None and seen["paid"] is None and seen["entries"] == [], (
            "Er liest Zahlen über Forderung und Geld (c)."
        )
        assert seen["allowed"] == [], "Er liest die Konkurrenzliste (d)."
        # **Und der Gewählte sieht seine Zahlen** – wer bezahlen soll, muss sehen, was er
        # schuldet; eine Aufforderung ohne Betrag ist keine.
        his = svc.embed_data(db, order=order, step=step, viewer=b)
        assert his is not None and his["charged"] == "99.00", (
            "Der Gewählte sieht seine eigene Rechnung nicht."
        )
    finally:
        db.rollback(); db.close()


def test_prepayment_is_the_payment_term_not_a_switch():
    """►►► **«Zahlbar in null Tagen ab Zusage» IST die Vorauszahlung.** ◄◄◄

    Kein Schalter in der Definition – die Frist sagt es, und ``assert_completable`` liest
    sie. **Ohne Frist keine Sperre**: dann hat niemand über den Zeitpunkt gesprochen.

    Bug-Formen: (a) das Modul lässt sich trotz offener Vorauszahlung abschliessen;
    (b) eine Frist von 30 Tagen sperrt ebenfalls.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, who, _art = _scene(db, quantity=1)
        _price(db, order, step, row, price="10.00")
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"lead_days": 0, "payment_days": 0})
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": who[0].object_id})
        db.flush()
        with pytest.raises(HTTPException) as e:
            svc.assert_completable(db, step=step)
        assert e.value.status_code == 409, "Die Vorauszahlung hält nicht an (a)."
        # (b) **Dieselbe Szene mit 30 Tagen läuft durch.**
        order2, step2, row2, who2, _a2 = _scene(db, quantity=1)
        _price(db, order2, step2, row2, price="10.00")
        svc.apply(db, order=order2, step=step2, action="ask",
                  payload={"lead_days": 0, "payment_days": 30})
        svc.apply(db, order=order2, step=step2, action="agree",
                  payload={"party": who2[0].object_id})
        db.flush()
        svc.assert_completable(db, step=step2)   # kein Fehler = die Regel greift nicht
    finally:
        db.rollback(); db.close()


def test_the_door_knows_every_field_it_accepts():
    """►►► **Pydantic verwirft Unbekanntes stillschweigend.** ◄◄◄

    Ein Feld, das die Tür nicht kennt, kommt **nie** an – und kein Dienst-Test findet das
    (die rufen den Dienst direkt). Dieselbe Falle wie damals bei ``ModuleConfigInput`` und
    ``DealUpdate``.

    Bug-Form: ein Verb erwartet ein Feld, das ``VoucherUpdate`` nicht führt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.schemas.voucher import VoucherUpdate
    known = set(VoucherUpdate.model_fields)
    for field in ("party", "parties", "lead_days", "payment_days", "amount",
                  "reference", "note", "booked_on", "due_on", "entry", "charge_id",
                  "lines", "vat", "currency", "method", "incoterm", "incoterm_place",
                  "issuer"):
        assert field in known, (
            f"«{field}» fehlt an der Tür – es käme nie an, und niemand würde es merken."
        )


def test_a_price_leaves_the_service_in_the_scale_of_its_currency():
    """►►► **Ein Betrag hat die Nachkommastellen SEINER Währung** (Testnotiz #931). ◄◄◄

    *«Warum hat das vier Stellen? Eine Währung hat doch immer zwei nachkommastellen.
    Bitte robuste Lösung hierfür finden.»*

    Fast – aber nicht ganz: **JPY hat null, KWD drei**, und genau darum ist «immer zwei»
    keine robuste Lösung, sondern dieselbe Falle eine Ebene weiter. Die Zahl steht im
    Vorgang, und ein Betrag verlässt den Dienst mit ihr.

    Die vier kamen aus der Spalte (`NUMERIC(18, 4)` – gross genug für jede Währung) und
    aus `str()`, das ihre volle Skala ausschreibt. Behoben wird es **am Dienst**, nicht in
    der Anzeige: dieselbe Zeichenkette steht gleich im Eingabefeld, und wer sie dort
    liest, tippt vier Nachkommastellen weiter.

    Bug-Formen: (a) der rohe Spaltenwert geht hinaus; (b) fest auf zwei Stellen gerundet.
    """
    from app.services import voucher as svc
    with _db() as db:
        _house(db)
        order, step, row, _who, _art = _scene(db)
        _price(db, order, step, row, price="30")

        lines = svc.embed_lines(db, row)
        assert lines, "Die Szene hat keine Position."
        assert lines[0]["price"] == "30.00", (
            f"«{lines[0]['price']}» statt «30.00» (a) – die Skala der Spalte ist nicht "
            f"die Stelligkeit der Währung."
        )

        # (b) **Dieselbe Position in einer nullstelligen Währung.** Wer fest auf zwei
        # rundet, schreibt hier «30.00» – einen Yen-Betrag, den es nicht gibt.
        svc.apply(db, order=order, step=step, action="currency",
                  payload={"currency": "JPY"})
        db.flush()
        yen = svc.embed_lines(db, row)
        assert yen[0]["price"] == "30", (
            f"«{yen[0]['price']}» statt «30» (b) – JPY hat keine Nachkommastellen."
        )
