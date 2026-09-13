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
    # **Die Zoll-Angaben stehen am Artikel** und reisen von dort auf jeden Beleg – seit
    # #964 sind sie Pflicht, bevor er hinausgeht (`_assert_complete`).
    art = Article(object_id=obj.next_object_id(db), name=name, unit="stk",
                  serialization="batch", hs_code="848210", origin_country="CH")
    db.add(art)
    db.flush()
    tpl.create_steps(db, art, [
        {"module_type": "datenerfassung",
         "config": {"points": [{"label": "Sichtprüfung", "type": "bool"}]}},
        *(steps or []),
    ])
    db.flush()
    return art


def _step(*, direction: str = "in", parties=(), task: str = "Härten auf 58 HRC",
          ref: str = "Art. 4711") -> dict:
    """Ein Beleg-Modul – **drei** Angaben, mehr gibt es nicht.

    ``task`` ist **was zu tun ist** (am Modul, freiwillig), ``ref`` **wie man bei ihm
    bestellt** (je Partner, Pflicht – aber nur, wo wir bestellen). Zwei Fragen, zwei
    Angaben: als eine stellte sie beim Verkauf eine, die niemand beantworten kann.
    """
    return {"module_type": "beleg",
            "config": {"direction": direction,
                       "instruction": task,
                       "parties": [{"party": p.object_id, "ref": ref} for p in parties]}}


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
    # **Die Lieferbedingung gehört zum vollständigen Beleg** (#964) – ohne sie geht er
    # nicht hinaus, und fast jede Prüfung hier will ihn hinausgehen lassen.
    svc.apply(db, order=order, step=step, action="incoterm",
              payload={"incoterm": "FCA", "incoterm_place": "Rorschach"})
    db.flush()
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
                 "reverse", "price", "currency", "issuer", "incoterm", "terms",
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
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 5, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="ask", payload={"parties": [who[0].object_id]})
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
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 5, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="ask",
                  payload={})
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
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 5, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="ask",
                  payload={})
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
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 0, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="ask",
                  payload={})
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
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 0, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="ask",
                  payload={})
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
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 0, "payment_days": 0})
        svc.apply(db, order=order, step=step, action="ask",
                  payload={})
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": who[0].object_id})
        db.flush()
        with pytest.raises(HTTPException) as e:
            svc.assert_completable(db, step=step)
        assert e.value.status_code == 409, "Die Vorauszahlung hält nicht an (a)."
        # (b) **Dieselbe Szene mit 30 Tagen läuft durch.**
        order2, step2, row2, who2, _a2 = _scene(db, quantity=1)
        _price(db, order2, step2, row2, price="10.00")
        svc.apply(db, order=order2, step=step2, action="terms",
                  payload={"lead_days": 0, "payment_days": 30})
        svc.apply(db, order=order2, step=step2, action="ask",
                  payload={})
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


# ═══════════════════════════════════════════════════════════════════════════════
# ►► §5 – WAS EINE ANSICHT SCHREIBT, BLEIBT (Testnotizen #937 · #939 · #945)
# ═══════════════════════════════════════════════════════════════════════════════

def test_a_view_that_writes_its_lines_also_keeps_them():
    """►►► **Der getippte Preis kam nicht an – und der Grund lag im Lesepfad.** ◄◄◄

    Gemeldet (#937): *«Wenn ich 30 eingebe und warte, wird Auto-Save ausgelöst, aber der
    Wert wird nicht übernommen – nur mit Enter funktioniert es.»*

    Die Oberfläche war unschuldig. ``sync_lines`` legt die Positionszeilen beim **Anzeigen**
    an; ``get_db`` committet aber nie, und ein blosses ``flush`` fällt beim Schliessen der
    Sitzung zurück. Der Browser bekam damit Ids, **die es nicht gibt** – und ``_price``
    findet seine Zeile nicht und schreibt nichts. Dass es «mit Enter ging», war schlicht
    der **zweite** Versuch: der erste ``POST`` legt die Zeilen an und committet sie.

    Bug-Formen: (a) die Ansicht behält ihre Zeilen nicht; (b) sie vergibt bei jedem Aufruf
    neue Ids; (c) ein Preis auf die eben gezeigte Id kommt nicht an.
    """
    from app.models import VoucherLine
    from app.routers import orders as router
    from app.services import voucher as svc
    with _db() as db:
        _house(db)
        order, step, row, _who, _art = _scene(db)

        shown = router._steps(db, order)
        paper = next((s.voucher for s in shown if s.voucher is not None), None)
        assert paper is not None, "Die Ansicht zeigt keinen Beleg."
        ids = [ln.id for ln in paper.lines]
        assert ids, "Die Ansicht zeigt keine Position."

        # ►►► **Die Sitzung endet, ohne dass jemand committet** – genau wie ``get_db``.
        db.rollback()
        kept = db.query(VoucherLine).filter(VoucherLine.id.in_(ids)).count()
        assert kept == len(ids), (
            f"{kept} von {len(ids)} Positionen haben die Anzeige überlebt (a) – der "
            f"Browser hält damit Ids, die es in der Datenbank nicht gibt."
        )

        # (b) **Dieselbe Ansicht noch einmal: dieselben Ids.** Neue wären dasselbe
        # Problem mit einem Schritt Verzögerung.
        again = next(s.voucher for s in router._steps(db, order) if s.voucher is not None)
        assert [ln.id for ln in again.lines] == ids, (
            "Die zweite Anzeige vergibt andere Ids (b) – dann zeigt jede Ansicht auf "
            "Zeilen, die die nächste nicht mehr kennt."
        )

        # (c) **Und der Preis kommt an** – auf die Id, die dastand.
        svc.apply(db, order=order, step=step, action="price",
                  payload={"lines": [{"id": ids[0], "price": "30", "vat": "normal"}]})
        db.flush()
        assert svc.embed_lines(db, row)[0]["price"] == "30.00", (
            "Der Preis auf die eben gezeigte Id kommt nicht an (c) – genau die gemeldete "
            "Form: der Auto-Save läuft, und es passiert nichts."
        )


def test_the_addressee_is_the_one_we_asked():
    """►►► **«Anschrift fehlt», obwohl oben ein Empfänger steht** (Testnotiz #939). ◄◄◄

    Der Belegkopf las ``party_of`` – «mit wem wurde **abgeschlossen**», und das ist vor der
    Zusage ``None``. Eine **Offerte** ist aber adressiert, sobald sie an genau einen
    hinausgeht; dort stand niemand, und die Zeile darunter meldete eine fehlende Anschrift
    zu einer leeren Stelle.

    Bug-Formen: (a) der Kopf bleibt leer, obwohl genau einer angefragt ist; (b) bei
    mehreren wird einer geraten; (c) die Vollständigkeitsprüfung hält den Angefragten
    schon für gebunden.
    """
    from app.services import voucher as svc
    with _db() as db:
        _house(db)
        one = _party(db, "Muster AG", "customer")
        two = _party(db, "Zweit AG", "customer")
        order, step, row, _who, _art = _scene(db, parties=[one, two])
        _price(db, order, step, row)

        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 5, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"parties": [one.object_id]})
        db.flush()
        head = svc.document_head(db, row, won=True)
        them = head["customer"]
        assert them["object_id"] == one.object_id, (
            f"Der Kopf nennt «{them['object_id']}» statt des einen Angefragten (a) – und "
            f"meldet darunter eine Anschrift, die zu niemandem gehört."
        )
        assert them["address"], "Der Angefragte hat eine Anschrift, der Kopf zeigt keine."

        # (c) **Gebunden ist er damit nicht.** Die Lücken fragen weiter nach der Zusage –
        # sonst verlangte eine blosse Anfrage bereits die Angaben eines Vertrags.
        assert svc.gaps(db, row, action="ask") == [], (
            "Eine Anfrage verlangt die Angaben der Gegenseite (c) – die steht erst mit "
            "der Zusage fest, und genau dafür gibt es die Stufe."
        )

        # (b) **Zwei Angefragte sind ein Rundschreiben** – dann gibt es keinen Adressaten.
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 5, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"parties": [two.object_id]})
        db.flush()
        assert svc.addressee_of(db, row) is None, (
            "Bei zwei Angefragten wird einer geraten (b) – eine erfundene Adresse ist "
            "schlimmer als eine leere Zeile."
        )


def test_a_module_says_why_it_cannot_be_finished_yet():
    """►►► **«Vorgang abschliessen» über einer Offerte** (Testnotiz #945). ◄◄◄

    *«Ich weiss nicht, warum hier ‹Vorgang abschliessen› kommt – passt das schon in die
    bestehende Lösung?»* Der Knopf gehört dorthin (jedes Modul endet mit ihm), aber er
    stand als vollflächige Einladung über einem Beleg, den der Dienst gleich darauf mit
    409 abwies. **Zwei Formen einer Regel**: ``completion_problem`` nennt den Grund,
    ``assert_completable`` ist die Tür – und die Ansicht reicht ihn als ``step.blocked``
    durch.

    Bug-Formen: (a) es gibt keinen Grund, nur die Ablehnung; (b) der Grund kommt nicht am
    Schritt an; (c) die beiden Formen sagen Verschiedenes.
    """
    import pytest as _pytest
    from fastapi import HTTPException
    from app.routers import orders as router
    from app.services import process as proc, voucher as svc
    with _db() as db:
        _house(db)
        order, step, row, _who, _art = _scene(db)

        why = proc.completion_problem(db, step)
        assert why, "Eine Offerte lässt sich abschliessen? (a)"
        shown = next(s for s in router._steps(db, order) if s.id == step.id)
        assert shown.blocked == why, (
            f"Der Grund erreicht den Schritt nicht (b): «{shown.blocked}»."
        )

        # (c) **Dieselbe Regel, zwei Formen** – die Tür sagt wörtlich denselben Satz.
        with _pytest.raises(HTTPException) as err:
            svc.assert_completable(db, step=step)
        assert err.value.detail == why, (
            f"Tür und Auskunft sagen Verschiedenes (c): «{err.value.detail}» ≠ «{why}»."
        )

        # **Und ein Modul ohne Beleg ist nie gesperrt** – der Rahmen erbt nichts.
        plain = next(s for s in router._steps(db, order) if s.module_type != "beleg")
        assert plain.blocked is None, (
            "Ein Modul ohne Geldvorgang meldet eine Sperre – die Regel ist die des "
            "Belegs, nicht die des Rahmens."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ►► §12 – JEDE ZUSAGE NACH AUSSEN HAT IHRE GEGENHANDLUNG
# ═══════════════════════════════════════════════════════════════════════════════

def test_an_ask_can_be_taken_back():
    """►►► **Eine Anfrage zurückziehen** (Testnotiz #951). ◄◄◄

    *«Ich kann zwar mehrere User aufführen, jedoch kann ich sie nicht wie zuvor auch
    abwählen.»* – Und es gab dafür **nichts**: ``ask`` war das einzige Verb ohne
    Gegenhandlung, eine falsch gewählte Gegenpartei blieb für immer am Beleg. Die Hausregel
    steht seit dem Beschaffen-Modul: *jede Zusage nach aussen hat ihre Gegenhandlung an
    derselben Stelle.*

    **Soft-Delete wie überall** – was hinausging, wird nicht geleugnet; die Zeile ist nur
    nicht mehr Teil dieses Belegs. **Die zugesagte nicht**: dort hängt die Zusage, und ihre
    Gegenhandlung ist der Storno des ganzen Vorgangs.

    Bug-Formen, jede gegengeprüft: (a) es gibt das Verb nicht; (b) die Zeile wird
    **gelöscht** statt stillgelegt; (c) auch die zugesagte lässt sich abwählen; (d) das Verb
    steht schon da, bevor überhaupt etwas hinausgegangen ist.
    """
    import pytest as _pytest
    from fastapi import HTTPException
    from app.models import VoucherQuote
    from app.services import voucher as svc
    with _db() as db:
        _house(db)
        one = _party(db, "Muster AG", "customer")
        two = _party(db, "Zweit AG", "customer")
        order, step, row, _who, _art = _scene(db, parties=[one, two])
        _price(db, order, step, row)
        staff = _party(db, "Personal", "admin")

        # (d) Vor der ersten Anfrage gibt es nichts abzuwählen – und nichts abzubrechen.
        assert "unask" not in svc.can(db, row, staff), (
            "Abwählen steht da, bevor etwas hinausgegangen ist (d)."
        )
        assert "revoke" not in svc.can(db, row, staff), (
            "Abbrechen steht da, bevor etwas hinausgegangen ist (d) – es gibt dann nichts, "
            "was man zurücknehmen könnte."
        )

        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 5, "payment_days": 30}, actor=staff)
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"parties": [one.object_id, two.object_id]}, actor=staff)
        db.flush()
        assert len(svc.quotes_of(db, row)) == 2
        assert "unask" in svc.can(db, row, staff), "Das Verb fehlt (a)."

        svc.apply(db, order=order, step=step, action="unask",
                  payload={"party": two.object_id}, actor=staff)
        db.flush()
        assert [q.party_id for q in svc.quotes_of(db, row)] == [one.object_id], (
            "Die abgewählte Zeile steht weiter am Beleg (a)."
        )
        # (b) **Stillgelegt, nicht gelöscht** – die Historie ist nicht verhandelbar.
        gone = (db.query(VoucherQuote)
                .filter(VoucherQuote.voucher_id == row.id,
                        VoucherQuote.party_id == two.object_id).first())
        assert gone is not None and gone.is_active is False, (
            "Die Zeile ist weg statt stillgelegt (b) – ein Hard-Delete gibt es im Haus "
            "nirgends."
        )

        # (c) **Ab der Zusage gar nicht mehr** – und zwar ohne eine zweite Regel: die
        # unterlegenen Zeilen sind dann der Nachweis, warum so entschieden wurde, und die
        # gewählte nimmt man mit dem Storno zurück. Eine Sperre «die gewählte nicht» stand
        # hier einen Anlauf lang und war **unerreichbar**, weil `_agree` Zustand und Stufe
        # in einem Zug setzt: gemessen, entfernt, und die Stufe ist das Tor.
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": one.object_id}, actor=staff)
        db.flush()
        assert "unask" not in svc.can(db, row, staff), (
            "Nach dem Zuschlag lässt sich noch abwählen (c) – dann verschwindet der "
            "Nachweis, warum so entschieden wurde."
        )
        with _pytest.raises(HTTPException) as err:
            svc.apply(db, order=order, step=step, action="unask",
                      payload={"party": two.object_id}, actor=staff)
        assert err.value.status_code == 409, (
            f"Die Tür lässt es trotzdem durch (c): «{err.value.detail}»."
        )


def test_a_cancel_is_reachable_at_every_step_that_happened():
    """►►► **Abbrechen geht, sobald etwas hinausgegangen ist** (Testnotiz #957). ◄◄◄

    *«Kannst du nochmals evaluieren, ob eigentlich immer ein Abbruch sauber und logisch
    korrekt etabliert ist zu jedem Schritt im Modul? Solange nicht angefangen wurde
    natürlich nicht, aber sobald der erste Schritt getriggert wurde.»*

    Der Beleg hat **zwei** Stufen, und beide führen jetzt ``revoke`` – vorher erst die
    Zusage: im Angebot stand ein hinausgeschickter Beleg **ohne jeden Ausweg** da. Die
    Bedingung «es ist etwas hinausgegangen» ist keine Stufe, sondern eine Frage an die
    Daten, und sie steht in ``can``.

    **Und das Wort hängt an der Stufe**: vor der Zusage gibt es keinen Auftrag, den man
    stornieren könnte – dort bricht man den Vorgang ab.

    Bug-Formen: (a) im Angebot gibt es keinen Abbruch; (b) er steht schon vor der ersten
    Anfrage da; (c) ein Wort für beide Stufen.
    """
    from app.domain import voucher as vo
    from app.services import voucher as svc
    with _db() as db:
        _house(db)
        order, step, row, who, _art = _scene(db)
        _price(db, order, step, row)
        staff = _party(db, "Personal", "admin")

        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 5, "payment_days": 30}, actor=staff)
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"parties": [who[0].object_id]}, actor=staff)
        db.flush()
        assert row.stage == vo.OFFER
        assert "revoke" in svc.can(db, row, staff), (
            "Im Angebot gibt es keinen Abbruch (a) – ein hinausgeschickter Beleg ohne "
            "Ausweg ist eine Sackgasse."
        )
        # (c) Zwei Stufen, zwei Wörter – und beide kommen aus **einer** Auflösung.
        assert vo.undo_word(vo.OFFER) != vo.undo_word(vo.AGREED), (
            "Dasselbe Wort in beiden Stufen (c) – vor der Zusage gibt es keinen Auftrag."
        )
        assert svc.embed_data(db, order=order, step=step,
                              viewer=staff)["undo"] == vo.undo_word(vo.OFFER), (
            "Der Beleg nennt ein anderes Wort als die Auflösung (c)."
        )

        svc.apply(db, order=order, step=step, action="revoke", payload={}, actor=staff)
        db.flush()
        assert row.stage == vo.CANCELLED
        # **Der Beleg behält seinen Weg** – das Datum der Anfrage bleibt stehen.
        assert svc.quotes_of(db, row)[0].sent_on is not None


def test_a_recipient_carries_its_own_address():
    """►►► **Je Angefragtem eine ganze Seite** (Testnotizen #951/#952). ◄◄◄

    *«Was mich noch stört: die jeweilige Anschrift ist nicht sichtbar … es müssen nicht alle
    auf einmal sein, aber immer mindestens eine geladen und ggf. auf Wunsch die anderen
    auch.»* – Ein **Beleg** hat einen Adressaten, also steht einer vollständig da; die
    übrigen reisen als ``recipients`` mit, und die Oberfläche schaltet um. Ein Endpunkt
    «Anschrift zu Nummer» wäre ein zweiter Weg zu einer Angabe, die der Beleg ohnehin
    liefert.

    ►►► **Und jede Seite nennt BEIDE Anschriften – immer** (#952/#975). ◄◄◄ *«Ich möchte,
    dass du das auch auf dem Leistungserbringer machst – standardmässig immer bei
    Informationen ausweisen, global etablieren, auch wenn sie zweimal das Gleiche anzeigt.
    Eine Logik für alles, Komplexität und If/Else verringern.»*

    Ein Beleg stellt zwei Fragen – *wohin die Rechnung, wohin die Ware* – und stellt sie auf
    jeder Seite gleich. Steht nur eine Anschrift da, trägt sie beide Beschriftungen: das ist
    die Auskunft «an dieselbe», nicht eine Doppelung. **Wo gar keine dasteht**, gibt es auch
    keine Beschriftung – dort sagt die Seite, dass sie fehlt.

    Bug-Formen: (a) die Seiten fehlen; (b) sie tragen keine Anschrift; (c) eine Gegenpartei
    bekommt die Konkurrenzliste; (d) die abweichende Lieferadresse fehlt; (e) die zweite
    Anschrift fällt weg, weil sie gleich ist; (f) die Beschriftungen fehlen bei einer
    einzigen Anschrift; (g) **unsere** Seite nennt sie nicht; (h) sie stehen auch da, wo es
    gar keine Anschrift gibt.
    """
    from app.domain import voucher as vo
    from app.services import voucher as svc
    with _db() as db:
        _house(db)
        one = _party(db, "Muster AG", "customer")
        two = _party(db, "Zweit AG", "customer")
        order, step, row, _who, _art = _scene(db, parties=[one, two])
        _price(db, order, step, row)
        staff = _party(db, "Personal", "admin")
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 5, "payment_days": 30}, actor=staff)
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"parties": [one.object_id, two.object_id]}, actor=staff)
        db.flush()

        seen = svc.embed_data(db, order=order, step=step, viewer=staff)
        got = [r["object_id"] for r in seen["recipients"]]
        assert got == [one.object_id, two.object_id], f"Die Seiten fehlen (a): {got}."
        assert all(r["address"] for r in seen["recipients"]), (
            "Eine Seite ohne Anschrift (b) – genau die Angabe, um die es ging."
        )
        # **Jede Seite sagt selbst, ob sie unsere ist** – daran unterscheidet die
        # Oberfläche die Blöcke, ohne ein Rollen-Wort zu vergleichen.
        assert all(r["ours"] is False for r in seen["recipients"])
        assert seen["supplier"]["ours"] != seen["customer"]["ours"]

        # (c) Die Liste der Angefragten ist die Konkurrenzliste.
        mine = svc.embed_data(db, order=order, step=step, viewer=two)
        assert mine["recipients"] == [], (
            "Eine Gegenpartei sieht die übrigen Angefragten (c)."
        )

        # (f) Eine einzige Anschrift steht unter **beiden** Beschriftungen – das ist die
        # Auskunft «an dieselbe» (#975).
        plain = next(r for r in seen["recipients"] if r["object_id"] == one.object_id)
        assert plain["shipping"] == plain["address"] and plain["address"], (
            "Die zweite Anschrift fehlt, wo es nur eine gibt (f)."
        )
        assert plain["address_label"] == vo.BILLING_LABEL
        assert plain["shipping_label"] == vo.SHIPPING_LABEL, (
            "Beschriftungen fehlen bei einer einzigen Anschrift (f)."
        )
        # (g) **Unsere** Seite beantwortet dieselben zwei Fragen.
        ours = seen["supplier"] if seen["supplier"]["ours"] else seen["customer"]
        assert ours["address"] and ours["shipping"] == ours["address"], (
            "Der Leistungserbringer nennt seine Anschriften nicht (g)."
        )
        # ►►► **Und die zweite Beschriftung sagt die RICHTUNG** (Testnotiz #979). ◄◄◄
        #
        # *«Beim Leistungserbringer wäre es evtl. besser/richtiger zu sagen Absendeadresse
        # oder so?»* – Ja: «Lieferadresse» heisst *wohin geliefert wird*, und an der
        # eigenen Anschrift des Leistungserbringers stand damit, man möge **ihm** dorthin
        # liefern. Hier ist es eine **Einnahme**, wir sind also der Leistungserbringer –
        # bei uns geht die Ware ab (*Versandadresse*), beim Empfänger kommt sie an.
        #
        # *Der Wächter verlangte hier zweimal `SHIPPING_LABEL` – also die Form der
        # damaligen Lösung, in der beide Seiten dasselbe sagten.*
        assert (ours["address_label"], ours["shipping_label"]) == (
            vo.BILLING_LABEL, vo.SHIPPING_FROM_LABEL), (
            "Unsere Seite trägt die falschen Beschriftungen (g/#979) – wer liefert, "
            "versendet, und «Lieferadresse» bittet ihn, an sich selbst zu liefern."
        )
        assert seen["supplier"]["shipping_label"] != seen["customer"]["shipping_label"], (
            "Beide Seiten sagen dasselbe (#979)."
        )

        # (d) Eine abweichende Rechnungsadresse macht zwei daraus.
        one.invoice_address_line1 = "Rechnungsweg 9"
        one.invoice_postal_code = "9000"
        one.invoice_city = "St. Gallen"
        db.flush()
        both = next(r for r in svc.embed_data(db, order=order, step=step,
                                             viewer=staff)["recipients"]
                    if r["object_id"] == one.object_id)
        assert any("Rechnungsweg 9" in x for x in both["address"]), (
            "Die Rechnungsadresse steht nicht auf dem Beleg – dafür ist sie da."
        )
        assert both["shipping"], "Die Lieferadresse fehlt, obwohl sie abweicht (d)."
        assert both["address_label"] == vo.BILLING_LABEL
        assert both["shipping_label"] == vo.SHIPPING_LABEL

        # (e) Und ist sie gleich, steht sie trotzdem unter beiden Beschriftungen – die
        # Frage «wohin die Ware» hat dann eben dieselbe Antwort (#975).
        one.invoice_address_line1 = one.address_line1
        one.invoice_postal_code = one.postal_code
        one.invoice_city = one.city
        one.invoice_country = one.country
        db.flush()
        same = next(r for r in svc.embed_data(db, order=order, step=step,
                                             viewer=staff)["recipients"]
                    if r["object_id"] == one.object_id)
        assert same["shipping"] == same["address"], (
            "Die zweite Anschrift fällt weg, weil sie gleich ist (e)."
        )

        # (h) **Wo gar keine dasteht, wird auch nichts beschriftet** – dort sagt die Seite,
        # dass sie fehlt; eine Beschriftung über einer Lücke wäre eine leere Behauptung.
        empty = svc.their_side(db, row, None)
        assert empty["address"] == [] and empty["shipping"] == []
        assert empty["address_label"] is None and empty["shipping_label"] is None, (
            "Beschriftungen über einer Seite ohne jede Anschrift (h)."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ►► TESTNOTIZEN #960–#974 – was hinausgeht, ist vollständig
# ═══════════════════════════════════════════════════════════════════════════════

def test_an_incomplete_document_does_not_go_out():
    """►►► **Was auf dem Beleg steht, ist PFLICHT** (Testnotiz #964). ◄◄◄

    *«Alle Eingabefelder hier in diesem Modul – also alles, was so leicht blau hinterlegt
    ist – sollen Muss-Felder sein.»*

    «Leicht blau hinterlegt» ist die Auszeichnung **änderbarer Werte** (`.ix-editable`,
    #922) – die Regel gilt also jedem Wert, den der Beleg trägt. Geprüft wird an der
    **einen** Stelle, an der er nach aussen geht (``_ask``); die rote Tönung im Browser
    ist die freundliche Hälfte derselben Regel, nie ein zweiter Massstab.

    **Gelesen wird der Wert, der auf dem Beleg STEHT** – die Zeile, wo sie etwas trägt,
    sonst der Artikel (``embed_lines``). Die rohe Spalte zu prüfen hiesse, eine Angabe zu
    verlangen, die sichtbar längst dasteht.

    Bug-Formen: (a) ohne Zolltarifnummer geht es trotzdem hinaus; (b) ohne Ursprungsland;
    (c) ohne Lieferbedingung; (d) der Satz nennt die Position nicht.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.services import voucher as svc

    db = _db()
    try:
        order, step, row, who, art = _scene(db)
        _price(db, order, step, row)

        # (c) Ohne Lieferbedingung – die Szene setzt sie, also wieder wegnehmen.
        row.incoterm, row.incoterm_place = None, None
        db.flush()
        with pytest.raises(HTTPException) as no_clause:
            svc.apply(db, order=order, step=step, action="terms",
                      payload={"lead_days": 10, "payment_days": 30})
            svc.apply(db, order=order, step=step, action="ask",
                      payload={})
        assert "Lieferbedingung" in no_clause.value.detail, (
            "Ohne Lieferbedingung geht der Beleg hinaus (c)."
        )
        svc.apply(db, order=order, step=step, action="incoterm",
                  payload={"incoterm": "FCA", "incoterm_place": "Rorschach"})

        # (a)/(b) Ohne Zoll-Angaben – sie stehen am Artikel und reisen von dort mit.
        for field, word in (("hs_code", "Zolltarifnummer"),
                            ("origin_country", "Ursprungsland")):
            keep = getattr(art, field)
            setattr(art, field, None)
            db.flush()
            with pytest.raises(HTTPException) as gone:
                svc.apply(db, order=order, step=step, action="terms",
                          payload={"lead_days": 10, "payment_days": 30})
                svc.apply(db, order=order, step=step, action="ask",
                          payload={})
            assert word in gone.value.detail, f"«{word}» ist keine Pflichtangabe (a/b)."
            # (d) **Der Satz nennt die Position** – «Ohne Zolltarifnummer …» über einem
            # Beleg mit zwölf Zeilen ist eine Sackgasse mit Ausrufezeichen.
            assert art.name in gone.value.detail, (
                "Der Satz nennt die betroffene Position nicht (d)."
            )
            setattr(art, field, keep)
            db.flush()

        # Und vollständig geht er hinaus.
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 10, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="ask",
                  payload={})
        assert svc.quotes_of(db, row), "Der vollständige Beleg geht nicht hinaus."
    finally:
        db.rollback(); db.close()


def test_the_document_head_names_no_kind_at_all():
    """►►► **Der Belegkopf nennt die Belegart gar nicht** (Testnotizen #974/#977). ◄◄◄

    *«Ich habe eigentlich gesagt, dass dies nicht angezeigt werden soll hier oben.»* – #974
    hiess «diese Anzeige verschwindet», und daraus die **Belegart** zu machen war die
    Auslegung einer Ablehnung, keine Umsetzung. Sie sagt oben auch nichts, was die Karte
    nicht schon sagt: wie weit der Beleg ist, steht als Punkt an jedem Abschnitt, und was
    als Nächstes zu tun ist, auf dem Knopf, der es tut.

    Damit hat ``document_label`` keinen Leser mehr – und eine Auflösung ohne Leser ist die
    zweite Wahrheit, die beim nächsten Umbau abweicht. **``label_of`` bleibt**: eine
    Fehlermeldung über die Stufe muss die Stufe nennen dürfen.

    Bug-Formen: (a) die Belegart ist als Feld zurück (Dienst oder Schema); (b) ``label_of``
    ist mitgezogen worden und kann die Stufe nicht mehr benennen.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo
    from app.schemas.voucher import VoucherEmbed

    # (a) Weder die Auflösung noch das Feld gibt es noch.
    assert not hasattr(vo.DIRECTIONS[vo.IN], "document_label"), (
        "«document_label» ist zurück – die Belegart hat keinen Leser mehr (a)."
    )
    assert "stage_label" not in VoucherEmbed.model_fields, (
        "«stage_label» reist wieder mit, obwohl der Belegkopf sie nicht nennt (a)."
    )
    # (b) Die Stufe hat weiterhin ihr eigenes Wort – für den Fehlersatz.
    for flow in vo.DIRECTIONS.values():
        assert flow.label_of(vo.DONE) == "Erledigt"
        assert flow.label_of(vo.CANCELLED) == "Storniert"
        assert flow.label_of(vo.OFFER) == flow.stage_labels[vo.OFFER]


def test_every_possible_party_carries_its_address():
    """►►► **Die Anschrift will man sehen, BEVOR man anbietet** (Testnotiz #962). ◄◄◄

    *«Zudem, und das stört mich immer noch: ich sehe die Anschrift(en) nicht. Ich bin im
    Offertenschritt, also der allerersten Stufe.»* – Genau dort ist noch **niemand**
    angefragt, und ``recipients`` trug nur die Angefragten: die Liste war leer, und die
    Anschrift, die man braucht, gab es gar nicht.

    Sie kommt jetzt aus der **Vereinigung** – zugelassen ∪ angefragt, Definition zuerst –,
    und die Oberfläche braucht dafür keine zweite Abfrage.

    Bug-Formen: (a) eine zugelassene, noch nicht angefragte Partei fehlt; (b) eine frei
    hinzugefügte fehlt; (c) eine steht doppelt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc

    db = _db()
    try:
        staff = _party(db, "Wir AG", "employee")
        one = _party(db, "Erste AG", "customer")
        two = _party(db, "Zweite AG", "customer")
        order, step, row, _who, _art = _scene(db, parties=[one, two])

        seen = [r["object_id"] for r in
                svc.embed_data(db, order=order, step=step, viewer=staff)["recipients"]]
        assert seen == [one.object_id, two.object_id], (
            f"Die zugelassenen Parteien tragen vor der Anfrage keine Seite (a): {seen}."
        )
        for r in svc.embed_data(db, order=order, step=step,
                                viewer=staff)["recipients"]:
            assert r["address"], "Eine Seite ohne Anschrift (a)."

        # (b)/(c) Angefragt ändert nichts an der Liste – sie ist eine Vereinigung.
        _price(db, order, step, row)
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 10, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"parties": [one.object_id]})
        again = [r["object_id"] for r in
                 svc.embed_data(db, order=order, step=step, viewer=staff)["recipients"]]
        assert again == [one.object_id, two.object_id], (
            f"Die Liste ändert sich mit der Anfrage (b/c): {again}."
        )
    finally:
        db.rollback(); db.close()


def test_a_quote_says_when_it_went_out_and_when_it_was_taken():
    """►►► **Der Moment steht schon da – er brauchte keine Spalte** (#968/#969). ◄◄◄

    *«… im Format ‹vor xx Tagen offeriert›, und beim Hovern das genaue Datum und
    Uhrzeit.»* – ``created_at`` einer Angebotszeile **ist** der Moment, in dem sie
    hinausging (``_ask`` legt sie genau dort an und nirgends sonst), und ``updated_at``
    der **gewählten** Zeile ist der Moment des Zuschlags (``_agree`` setzt ``CHOSEN`` in
    einem Zug mit der Stufe, und danach fasst kein Verb sie mehr an).

    ``sent_on`` bleibt daneben: das ist das **Datum auf dem Papier**.

    Bug-Formen: (a) der Moment fehlt; (b) er steht auch an einer Zeile ohne Zuschlag –
    dann behauptet sie einen, den es dort nie gab.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc

    db = _db()
    try:
        staff = _party(db, "Wir AG", "employee")
        one = _party(db, "Erste AG", "customer")
        two = _party(db, "Zweite AG", "customer")
        order, step, row, _who, _art = _scene(db, parties=[one, two])
        _price(db, order, step, row)
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 10, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="ask",
                  payload={})

        rows = svc.embed_data(db, order=order, step=step, viewer=staff)["quotes"]
        assert all(q["sent_at"] for q in rows), "Der Moment des Hinausgehens fehlt (a)."
        assert all(q["agreed_at"] is None for q in rows), (
            "Eine Zeile ohne Zuschlag behauptet einen (b)."
        )

        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": one.object_id})
        after = svc.embed_data(db, order=order, step=step, viewer=staff)["quotes"]
        taken = [q for q in after if q["agreed_at"] is not None]
        assert [q["party_object_id"] for q in taken] == [one.object_id], (
            "Der Moment des Zuschlags steht nicht an genau der gewählten Zeile (b)."
        )
    finally:
        db.rollback(); db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ►► TESTNOTIZEN #975–#978 – zwei Fragen, zwei Angaben
# ═══════════════════════════════════════════════════════════════════════════════

def test_what_to_do_travels_with_the_document_and_stays_optional():
    """►►► **«Was ist zu tun?» steht auf dem Beleg – und ist freiwillig.** ◄◄◄

    *«Es ist bewusst bei der Definition angelegt worden: bei einem Fertigungsprozess
    definiere ich im Vorhinein, was zu tun ist – im Prozess arbeite ich ihn nur noch ab.»*
    Genau darum steht der Satz am **Modul** und nicht am laufenden Beleg. Er reist mit,
    damit die Gegenpartei ihn liest – *sie* soll es ja tun.

    **Leer ist der Normalfall** und heisst «gemäss Spezifikation»: die Positionen sagen
    längst, *was* es ist. Ein Beleg, der dann «—» hinschreibt, sagt nichts.

    Bug-Formen: (a) der Satz erreicht den Beleg nicht; (b) die Beschriftung fehlt; (c) ein
    leerer Satz wird zu einem Wert; (d) die Gegenpartei sieht ihn nicht – sie soll es tun.
    """
    from app.domain import voucher as vo
    from app.services import voucher as svc
    db = _db()
    try:
        _house(db)
        who = _party(db, "Muster AG", "customer")
        order, step, row, _who, _art = _scene(db, parties=[who])
        staff = _party(db, "Personal", "admin")

        seen = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert seen["task"] == "Härten auf 58 HRC", (
            f"Der Auftrag erreicht den Beleg nicht (a): {seen['task']!r}."
        )
        assert seen["task_label"] == vo.TASK, "Die Beschriftung fehlt (b)."
        # (d) **Wer es tun soll, muss es lesen** – der Satz hängt nicht an `won`.
        theirs = svc.embed_data(db, order=order, step=step, viewer=who)
        assert theirs["task"] == "Härten auf 58 HRC", (
            "Die Gegenpartei sieht den Auftrag nicht (d)."
        )

        # (c) **Leer bleibt leer** – kein Platzhalter, kein «—».
        step.config = {**step.config, "instruction": ""}
        db.flush()
        assert svc.embed_data(db, order=order, step=step, viewer=staff)["task"] == "", (
            "Ein leerer Auftrag wird zu einem Wert (c)."
        )
    finally:
        db.rollback(); db.close()


def test_how_to_order_exists_only_where_we_order():
    """►►► **Die Bestellangabe ist eine Frage der RICHTUNG** (``Direction.party_ref``). ◄◄◄

    *«Bei der Verkaufsabwicklung habe ich keine Ahnung, was ich dort reinschreiben soll.
    Es ist ein Mussfeld – die Logik geht bei Verkaufsteilen nicht auf.»*

    Sie beantwortet «wie bestelle ich bei ihm» – seine Artikelnummer, sein Shop-Link. Beim
    **Verkauf** liefern wir; dort gibt es sie nicht, und ein trotzdem gesendeter Wert wird
    **verworfen** statt gespeichert.

    Bug-Formen: (a) sie steht am Verkaufs-Beleg; (b) sie fehlt am Einkaufs-Beleg.
    """
    from app.services import voucher as svc
    db = _db()
    try:
        _house(db)
        for direction, expected in (("in", ""), ("out", "Art. 4711")):
            who = _party(db, f"Partner {direction}", "customer")
            order, step, row, _who, _art = _scene(db, direction=direction, parties=[who])
            _price(db, order, step, row)
            staff = _party(db, f"Personal {direction}", "admin")
            svc.apply(db, order=order, step=step, action="terms",
                      payload={"lead_days": 5, "payment_days": 30}, actor=staff)
            svc.apply(db, order=order, step=step, action="ask",
                      payload={"parties": [who.object_id]}, actor=staff)
            db.flush()
            got = svc.embed_data(db, order=order, step=step,
                                 viewer=staff)["quotes"][0]["ref"]
            assert got == expected, (
                f"«{direction}»: die Bestellangabe ist {got!r} statt {expected!r} "
                f"({'a' if direction == 'in' else 'b'})."
            )
    finally:
        db.rollback(); db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ►► DER UMBAU VON «RECHNUNG & ZAHLUNG» — zwei Fächer, eine Handlung, eine Wahl
# ═══════════════════════════════════════════════════════════════════════════════

def test_an_invoice_is_issued_here_and_recorded_there():
    """►►► **«Rechnung stellen» ↔ «Rechnung erfassen»** – zwei Vorgänge, zwei Wörter.◄◄◄

    Bei einer **Einnahme** entsteht der Beleg hier, bekommt unsere Nummer und geht hinaus;
    bei einer **Ausgabe** schreiben wir ab, was der Lieferant geschickt hat. Beides hiess
    «Rechnung erfassen» – und ausgerechnet der Fall, in dem eine Rechnungsnummer vergeben
    wird, klang nach Abtippen. **Die Zahlung wird weiterhin in beiden Richtungen
    erfasst**: das System bucht eine Zeile, es überweist nichts.

    Bug-Formen: (a) beide Richtungen sagen dasselbe; (b) das Wort steht wieder als eine
    Konstante für beide da; (c) auch die Zahlung bekommt zwei Wörter.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo

    assert vo.of("in").charge_verb == vo.CHARGE_ISSUE, (
        "Bei einer Einnahme entsteht der Beleg hier – dann wird er gestellt (a)."
    )
    assert vo.of("out").charge_verb == vo.CHARGE_RECORD, (
        "Eine fremde Rechnung wird abgeschrieben, nicht gestellt (a)."
    )
    assert vo.of("in").charge_verb != vo.of("out").charge_verb, (
        "Beide Richtungen sagen dasselbe (a)."
    )
    assert not hasattr(vo, "CHARGE_WORD"), (
        "Das Wort steht wieder als eine Konstante für beide Richtungen da (b)."
    )
    # (c) **Nur die Forderung ist verschieden** – ein zweites Feld für die Zahlung wäre
    # ein Wert, den jemand einzeln falsch setzen kann.
    assert not any("payment" in f for f in vo.Direction.__dataclass_fields__), (
        "Auch die Zahlung hat ein Wort je Richtung bekommen (c)."
    )


def test_the_ways_to_the_money_come_from_can_and_say_what_they_do():
    """►►► **Der Weg zum Geld ist eine Wahl – und jeder Weg sagt, was er auslöst.** ◄◄◄

    Bar · Überweisung · Karte sind drei Antworten auf **eine** Frage; was dahinter
    passiert, ist verschieden (buchen ↔ Angaben zeigen ↔ Zahlformular öffnen). Angeboten
    wird nur, was dieser Betrachter darf – gelesen aus ``can``, der Liste, die ohnehin
    Auskunft **und** Tor ist.

    **Und die Gegenpartei bucht nicht**: für sie ist die Überweisung eine reine
    *Auskunft* – ``action`` und ``verb`` bleiben leer, und damit steht bei ihr kein Knopf,
    der nach Buchung aussieht.

    Bug-Formen: (a) es gibt Wege, obwohl nichts offen ist; (b) die Gegenpartei bekommt
    einen Buchungs-Weg; (c) ein Weg sagt nicht, ob er eine Auskunft mitbringt; (d) die
    Liste kommt nicht aus ``can``.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, who, _art = _scene(db, quantity=2)
        staff = _party(db, "Personal", "admin")
        _price(db, order, step, row, price="100.00")
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 0, "payment_days": 30}, actor=staff)
        svc.apply(db, order=order, step=step, action="ask",
                  payload={}, actor=staff)
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": who[0].object_id}, actor=staff)
        db.flush()

        # (a) **Ohne offene Forderung gibt es nichts zu begleichen.**
        empty = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert empty["ways"] == [] and empty["settle_charge"] is None, (
            "Es gibt Wege, obwohl nichts gefordert ist (a) – dann zeigt die Karte eine "
            "Wahl, die ins Leere führt."
        )

        svc.apply(db, order=order, step=step, action="charge", payload={}, actor=staff)
        db.flush()
        charge = svc.live_charge(db, row)
        assert charge is not None

        seen = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert seen["settle_charge"] == charge.id, (
            "Der Beleg nennt die Rechnung nicht, die begleichen werden soll."
        )
        ours = {w["key"]: w for w in seen["ways"]}
        assert vo.CASH in ours and vo.TRANSFER in ours, (
            f"Das Personal kann nicht bar und nicht per Überweisung buchen: {list(ours)}."
        )
        assert ours[vo.CASH]["action"] == "pay" and ours[vo.CASH]["verb"], (
            "Ein Weg sagt nicht, was er auslöst."
        )
        # (c) **Die Auskunft ist eine Eigenschaft des Weges** – die Oberfläche vergleicht
        # sonst den Schlüssel «transfer», und das ist der Spiegel über die API-Grenze.
        assert ours[vo.TRANSFER]["info"] is True, (
            "Die Überweisung bringt keine Auskunft mit (c)."
        )
        assert ours[vo.CASH]["info"] is False, "Bar bringt eine Auskunft mit (c)."

        # (b) **Die Gegenpartei sieht die Überweisung – und bucht nicht.**
        theirs = {w["key"]: w for w in
                  svc.embed_data(db, order=order, step=step,
                                 viewer=who[0])["ways"]}
        assert vo.CASH not in theirs, (
            "Die Gegenpartei bekommt einen Buchungs-Weg (b) – eine Buchung ist unsere "
            "Aussage über unser Konto."
        )
        assert theirs[vo.TRANSFER]["action"] is None, (
            "Die Überweisung ist für sie eine Buchung (b) statt einer Auskunft."
        )
        assert theirs[vo.TRANSFER]["info"] is True, (
            "Sie sieht die Bankverbindung nicht – dann kann sie gar nicht überweisen."
        )
        # (d) **Die Liste kommt aus `can`** – zwei Massstäbe wären ein Knopf, der
        # bereitsteht und dann scheitert.
        for key, way in ours.items():
            if way["action"]:
                assert way["action"] in seen["can"], (
                    f"«{key}» bietet «{way['action']}» an, was `can` nicht führt (d)."
                )
    finally:
        db.rollback()
        db.close()


def test_the_settle_charge_is_named_by_the_service_not_guessed():
    """►►► **Welche Rechnung begleicht man?** – der Dienst sagt es (#859/#866). ◄◄◄

    Je Modul lebt höchstens **eine** offene Forderung, die Frage hat damit genau eine
    Antwort. Sie in der Oberfläche zu suchen wäre eine zweite Regel neben ``open_charges``
    – und genau daraus kam #859 («kassiert wurde immer die älteste offene, egal an welchem
    Knopf jemand geklickt hat»).

    Bug-Formen: (a) eine stornierte Rechnung wird zum Ziel; (b) eine bezahlte bleibt es;
    (c) eine Gegenpartei ohne Zuschlag bekommt eine genannt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc
    db = _db()
    try:
        one = _party(db, "Muster AG", "customer")
        two = _party(db, "Zweit AG", "customer")
        order, step, row, _who, _art = _scene(db, quantity=2, parties=[one, two])
        staff = _party(db, "Personal", "admin")
        _price(db, order, step, row, price="100.00")
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 0, "payment_days": 30}, actor=staff)
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"parties": [one.object_id, two.object_id]}, actor=staff)
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": one.object_id}, actor=staff)
        svc.apply(db, order=order, step=step, action="charge", payload={}, actor=staff)
        db.flush()
        first = svc.live_charge(db, row)
        assert svc.embed_data(db, order=order, step=step,
                              viewer=staff)["settle_charge"] == first.id

        # (c) **Wer den Zuschlag nicht hat, sieht nichts** – auch keine Rechnungsnummer.
        assert svc.embed_data(db, order=order, step=step,
                              viewer=two)["settle_charge"] is None, (
            "Ein unterlegener Angefragter bekommt eine Rechnung genannt (c)."
        )

        # (a) **Storniert ist kein Ziel mehr.**
        svc.apply(db, order=order, step=step, action="reverse",
                  payload={"entry": first.id}, actor=staff)
        db.flush()
        assert svc.embed_data(db, order=order, step=step,
                              viewer=staff)["settle_charge"] is None, (
            "Eine stornierte Rechnung bleibt das Ziel (a) – auf sie zahlt niemand."
        )

        # (b) **Bezahlt ist kein Ziel mehr.**
        svc.apply(db, order=order, step=step, action="charge", payload={}, actor=staff)
        db.flush()
        second = svc.live_charge(db, row)
        seen = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert seen["settle_charge"] == second.id
        svc.apply(db, order=order, step=step, action="pay",
                  payload={"amount": seen["open"], "method": "cash"}, actor=staff)
        db.flush()
        done = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert done["settle_charge"] is None and done["ways"] == [], (
            "Eine bezahlte Rechnung bleibt das Ziel (b) – dann bietet die Karte an, "
            "etwas zu begleichen, das beglichen ist."
        )
    finally:
        db.rollback()
        db.close()


def test_a_term_typed_on_the_voucher_survives_a_reload():
    """►►► **Was auf dem Beleg steht, wird sofort geschrieben** (Testnotiz #985). ◄◄◄

    *«Eingaben in ‹Zahlungsfrist› und ‹Lieferfrist› werden nicht persistiert – nach einem
    Reload sind sie wieder weg.»*

    Und die Ursache war **keine Eigenheit dieser zwei Felder**: sie existierten
    ausschliesslich an der Angebotszeile, und die entsteht erst mit dem Anfragen. Sie
    waren damit die einzige Angabe des Belegs **ohne eigenes Verb** – getippt lebten sie
    nur im Browser und reisten allein in der Nutzlast von ``ask`` mit.

    Geprüft wird darum die **Regel**, nicht die zwei Felder: jede Angabe des Belegs hat
    ihr Verb, sie wird sofort geschrieben, und ``ask`` **kopiert** sie – wie den Betrag
    aus den Positionen.

    Bug-Formen: (a) ``terms`` fehlt, es gibt kein Verb dafür; (b) der Wert überlebt das
    erneute Lesen nicht; (c) die Ableitung liefert vor der Zusage nichts, also kommt er im
    Browser nie an; (d) ``ask`` nimmt eine Frist aus der Nutzlast (die zweite Aussage über
    dieselbe Sache – und die getippte gewänne); (e) «nur gesendete Felder wirken» gilt
    nicht: wer eine Frist ändert, verliert die andere; (f) die Null geht verloren.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc
    from app.models import Voucher

    db = _db()
    try:
        order, step, row, who, _art = _scene(db, quantity=2)
        _price(db, order, step, row, price="10.00")

        # (a)/(b) **Geschrieben, und zwar wirklich** – neu gelesen, nicht aus dem Objekt.
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 7, "payment_days": 0})
        db.flush()
        db.expire_all()
        again = db.query(Voucher).filter(Voucher.id == row.id).one()
        assert (again.lead_days, again.payment_days) == (7, 0), (
            f"Die Fristen überleben das Speichern nicht (a/b/f): "
            f"{again.lead_days}/{again.payment_days}."
        )

        # (c) **Und sie kommen im Browser an** – vor der Zusage gibt es keine gewählte
        #     Zeile, also muss die Ableitung auf den Entwurf zurückfallen.
        staff = _party(db, "Personal", "admin")
        seen = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert (seen["lead_days"], seen["due_days"]) == (7, 0), (
            f"Der Entwurf erreicht die Oberfläche nicht (c): "
            f"{seen['lead_days']}/{seen['due_days']} – das Feld steht nach jedem Reload "
            f"wieder leer."
        )
        assert seen["prepaid"] is True, (
            "«Zahlbar in 0 Tagen» ist die Vorauszahlung – auch als Entwurf (c)."
        )

        # (e) **Nur gesendete Felder wirken.**
        svc.apply(db, order=order, step=step, action="terms", payload={"lead_days": 3})
        db.flush()
        db.expire_all()
        again = db.query(Voucher).filter(Voucher.id == row.id).one()
        assert (again.lead_days, again.payment_days) == (3, 0), (
            f"Eine Änderung an EINER Frist nimmt die andere mit (e): "
            f"{again.lead_days}/{again.payment_days}."
        )

        # (d) **`ask` liest den Beleg, nicht die Nutzlast.**
        svc.apply(db, order=order, step=step, action="ask",
                  payload={"lead_days": 99, "payment_days": 99})
        db.flush()
        quote = svc.quotes_of(db, row)[0]
        assert (quote.lead_days, quote.payment_days) == (3, 0), (
            f"Eine Frist aus der Nutzlast gewinnt gegen den Beleg (d): "
            f"{quote.lead_days}/{quote.payment_days} – dann sagt derselbe Beleg zwei "
            f"Dinge, und die getippte Zahl schlägt die sichtbare."
        )

        # Und ab der Zusage gilt die **Vereinbarung**, nicht mehr der Entwurf.
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": who[0].object_id})
        db.flush()
        quote.payment_days = 14
        db.flush()
        assert svc.due_days_of(db, row) == 14, (
            "Nach der Zusage gilt die Frist der gewählten Angebotszeile."
        )
    finally:
        db.rollback()
        db.close()


def test_a_charge_says_how_it_stands():
    """►►► **Der Zustand einer Forderung – abgeleitet, mit Toleranz** (Testnotiz #991).◄◄◄

    *Offen · Teilweise bezahlt · Beglichen · Überfällig · Überzahlt · Storniert* – aus
    zwei Zahlen (Betrag und Rest), **null Spalten**. Und in den **drei** Ampeltönen des
    Hauses: eine vierte Farbe für Geld wäre eine zweite Farbsprache.

    ►►► **Die Überzahlung ist ein GUTHABEN** – der negative offene Betrag *ist* die Zahl.
    Eine eigene Guthaben-Tabelle wäre ein zweites Modell dafür; zurückgezahlt wird über
    die gewöhnliche negative Zahlung bzw. den Zahlungsdienst.

    Bug-Formen: (a) «teilweise bezahlt» gibt es nicht – eine angezahlte Rechnung sieht aus
    wie eine unberührte; (b) drei Rappen Restdifferenz halten sie für immer offen;
    (c) eine unbeglichene **Gutschrift** (negative Rechnung) heisst «Überzahlt»;
    (d) der Ton kommt aus einer eigenen Farbliste statt aus den drei des Hauses;
    (e) der Zustand erreicht die Oberfläche nicht.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from decimal import Decimal
    from app.domain import voucher as vo
    from app.services import voucher as svc

    d = Decimal
    # (a) **Angezahlt ist ein eigener Zustand.**
    assert vo.charge_state(d("100"), d("40"))["state"] == "partial", (
        "Eine angezahlte Rechnung sieht aus wie eine unberührte (a)."
    )
    assert vo.charge_state(d("100"), d("100"))["state"] == "open"
    # (b) **Rundungstoleranz** – sonst mahnt man wegen drei Rappen.
    assert vo.charge_state(d("100"), d("0.03"))["state"] == "settled", (
        "Drei Rappen halten die Rechnung offen (b)."
    )
    assert vo.charge_state(d("100"), d("0.00"))["state"] == "settled"
    # (c) **Eine Gutschrift ist eine negative Rechnung** – und unbeglichen ist sie offen,
    #     nicht überzahlt. Gerechnet wird mit dem Vorzeichen, nicht mit «grösser null».
    assert vo.charge_state(d("-100"), d("-100"))["state"] == "open", (
        "Eine unbeglichene Gutschrift heisst «Überzahlt» (c)."
    )
    assert vo.charge_state(d("-100"), d("-40"))["state"] == "partial"
    assert vo.charge_state(d("100"), d("-20"))["state"] == "overpaid"
    assert vo.charge_state(d("-100"), d("20"))["state"] == "overpaid"
    # Überfällig schlägt «offen», storniert schlägt alles.
    assert vo.charge_state(d("100"), d("100"), overdue=True)["state"] == "overdue"
    assert vo.charge_state(d("100"), d("0"), reversed_=True)["state"] == "reversed"
    # (d) **Drei Töne, keine vierte Farbe.**
    tones = {tone for _, tone in vo.CHARGE_STATES.values()}
    assert tones <= {"done", "pending", "danger"}, (
        f"Ein Ton ausserhalb der drei des Hauses (d): {tones}."
    )

    # (e) **Und er reist mit** – gemessen über den echten Dienstpfad.
    db = _db()
    try:
        order, step, row, who, _art = _scene(db, quantity=2)
        _price(db, order, step, row, price="100.00")
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 5, "payment_days": 30})
        svc.apply(db, order=order, step=step, action="ask", payload={})
        svc.apply(db, order=order, step=step, action="agree",
                  payload={"party": who[0].object_id})
        svc.apply(db, order=order, step=step, action="charge", payload={})
        db.flush()
        staff = _party(db, "Personal", "admin")
        seen = svc.embed_data(db, order=order, step=step, viewer=staff)
        entry = seen["entries"][0]
        assert entry["state_label"] and entry["state_tone"], (
            "Der Zustand erreicht die Oberfläche nicht (e) – dann rechnet sie ihn "
            "wieder selbst."
        )
        # Eine Anzahlung macht daraus «teilweise bezahlt».
        svc.apply(db, order=order, step=step, action="pay",
                  payload={"amount": "50.00", "method": "cash"})
        db.flush()
        again = svc.embed_data(db, order=order, step=step, viewer=staff)
        charge = next(e for e in again["entries"] if e["kind"] == "charge")
        assert charge["state"] == "partial", (
            f"Die angezahlte Rechnung sagt «{charge['state']}» (a/e)."
        )
    finally:
        db.rollback()
        db.close()
