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
    for verb in ("ask", "quote", "decline", "agree", "revoke", "bill", "unbill",
                 "issue", "correct", "pay", "price", "currency", "issuer", "incoterm",
                 "terms", "pay_online", "refund_online"):
        assert verb in svc.VERBS, f"«{verb}» fehlt in VERBS (b)."
    # (c) **`can` liest genau diese Tabelle** – geprüft an der Stufe, nicht am Namen.
    for key, verb in svc.VERBS.items():
        assert verb.stages, f"«{key}» gilt in keiner Stufe (b)."
        for stage in verb.stages:
            assert stage in ("offer", "agreed", "billed", "done", "cancelled"), (
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

    *``vouchers.amount`` gibt es seit dem Umbau wieder – es ist aber **eine andere
    Sache**: der eingefrorene Betrag der **Rechnung**, nicht der der Zusage. Geprüft wird
    darum die Ableitung selbst (``agreed_amount`` liest die Zeile), nicht die Abwesenheit
    eines Namens.*
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.models import Voucher
    from app.services import voucher as svc

    for gone in ("party_id", "due_days"):
        assert not hasattr(Voucher, gone), (
            f"«{gone}» steht wieder als Spalte am Beleg (a) – dann kann der Beleg "
            f"etwas anderes sagen als seine gewählte Angebotszeile."
        )
    src = _code(BACKEND / "app" / "services" / "voucher.py")
    body = src[src.index("def agreed_amount("):src.index("def due_days_of(")]
    assert "row.amount" not in body, (
        "Der zugesagte Betrag liest die Rechnung (a) – das sind zwei Zahlen zu zwei "
        "Zeitpunkten, und die Zusage steht an ihrer Angebotszeile."
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
                          "domain import deal", "import purchase", "from .purchase",
                          "import invoices", "from .invoices",
                          "import payments", "from .payments",
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
        svc.apply(db, order=order, step=step, action="bill", payload={})
        db.flush()
        assert row.stage == "billed", "Die Rechnung ist keine Schwelle geworden."
        assert row.amount == Decimal("324.3000")
        assert row.number == f"{order.object_id}-1", (
            f"Die Rechnungsnummer trägt nicht ihr Suffix: {row.number}."
        )
        assert row.vat, "Die Steuer-Aufteilung ist nicht eingefroren."
        svc.apply(db, order=order, step=step, action="issue", payload={})
        db.flush()
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


def _agreed(db, *, direction: str = "in", quantity: int = 2, price: str = "100.00",
            parties=None):
    """Eine Szene bis zur **Zusage** – bepreist, angeboten, angenommen."""
    from app.services import voucher as svc
    order, step, row, who, art = _scene(db, direction=direction, quantity=quantity,
                                        parties=parties)
    if direction == "in":
        _price(db, order, step, row, price=price)
    svc.apply(db, order=order, step=step, action="terms",
              payload={"lead_days": 0, "payment_days": 30})
    svc.apply(db, order=order, step=step, action="ask", payload={})
    if direction != "in":
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": who[0].object_id, "amount": price,
                           "lead_days": 7, "payment_days": 30})
    svc.apply(db, order=order, step=step, action="agree",
              payload={"party": who[0].object_id})
    db.flush()
    return order, step, row, who, art


def _credit(db, *, target, who, price: str = "40.00"):
    """Eine **Gutschrift** zu ``target`` – in einem **eigenen** Auftrag.

    Die Reihenfolge ist die des Belegs: erst zuordnen (das Verb ``correct`` gilt in der
    Stufe «Angebot»), dann bepreisen, anbieten und annehmen.
    """
    from app.services import voucher as svc
    order, step, row, _w, _a = _scene(db, quantity=1, parties=[who])
    svc.apply(db, order=order, step=step, action="correct",
              payload={"corrects": target.id})
    _price(db, order, step, row, price=price)
    svc.apply(db, order=order, step=step, action="terms",
              payload={"lead_days": 0, "payment_days": 30})
    svc.apply(db, order=order, step=step, action="ask", payload={})
    svc.apply(db, order=order, step=step, action="agree",
              payload={"party": who.object_id})
    db.flush()
    return order, step, row


def test_the_backfill_is_written_once_and_read_by_both():
    """►►► **Eine Datenänderung einer Migration braucht IMMER auch ein Netz.** ◄◄◄

    Die dev-Datenbank fährt kein ``alembic upgrade head`` (Testnotiz #778) – sie lebt von
    ``create_all`` plus den Netzen in ``main``. Für **Schema** gibt es vier davon; für
    **Daten** gab es keines, und genau hier zählt es: das Spalten-Netz zöge die acht neuen
    Spalten **leer** nach, während die alten Forderungs-Zeilen stehenblieben. Der Dienst
    liest seit dem Umbau jede aktive Zeile als **Zahlung** – jede alte Rechnung wäre ein
    Geldeingang, und der offene Betrag stünde im Minus.

    Geschrieben steht die Ableitung darum **einmal** (``domain/voucher``) und wird von
    **zwei** Stellen gelesen – dieselbe Bauart wie ``statuses.terminal_guard_sql``.

    Bug-Formen: (a) die Migration schreibt ihr eigenes SQL; (b) das Netz ruft sie gar
    nicht; (c) der Backfill ist nicht selbstbegrenzend, läuft also bei jedem Start erneut.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo

    mig = (BACKEND / "alembic" / "versions"
           / "138_der_beleg_ist_die_rechnung.py").read_text()
    net = _code(BACKEND / "app" / "main.py")
    assert "invoice_backfill_sql" in mig, (
        "Die Migration schreibt ihr eigenes SQL (a) – zwei Fassungen laufen beim nächsten "
        "Feld auseinander."
    )
    assert "invoice_backfill_sql()" in net, (
        "Das Lifespan-Netz zieht den Bestand nicht nach (b) – auf dev läse der Dienst "
        "jede alte Rechnung als Zahlung."
    )
    # *Gefragt ist der **Aufwärtsweg**: die Rücknahme setzt die Stufe zurück und darf
    # darum sehr wohl ein ``UPDATE vouchers`` tragen (gemessen, nachgeschärft).*
    up = mig[mig.index("def upgrade("):mig.index("def downgrade(")]
    assert "UPDATE vouchers" not in up, (
        "Die Migration führt eine zweite Fassung des Backfills (a)."
    )
    # (c) **Selbstbegrenzend**: der erste Lauf nimmt seine eigene Voraussetzung weg.
    first, *rest = vo.invoice_backfill_sql()
    assert "v.amount IS NULL" in first, (
        "Der Backfill greift auch nach dem ersten Lauf (c) – dann überschreibt jeder "
        "Start eine Rechnung, die inzwischen jemand bearbeitet hat."
    )
    assert any("is_active = false" in r and "kind = 'charge'" in r for r in rest), (
        "Die alten Forderungs-Zeilen bleiben aktiv (c) – der Dienst liest sie als "
        "Zahlungen."
    )


def test_a_module_carries_exactly_one_invoice():
    """►►► **Eine Rechnung je Modul — nicht als Regel, sondern als STRUKTUR.** ◄◄◄

    *«Nur eine Rechnung pro Zahlungsmodul. Habe ich Teilrechnungen, dann erstelle ich
    einfach 2 Zahlungsmodule.»*

    Bis hierher musste eine Funktion **zählen**, was eine «Forderung nach aussen» ist
    (nicht die Gegenbuchung, nicht die stornierte, nicht die negative) – eine Regel, die
    jemand durchsetzt und die man vergessen kann. Jetzt **ist** der Beleg die Rechnung:
    ``bill`` ist eine Schwelle von ``agreed`` nach ``billed``, und danach steht das Verb
    gar nicht mehr in ``can``.

    Bug-Form: ein zweites ``bill`` am selben Beleg geht durch.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, _who, _art = _agreed(db)
        svc.apply(db, order=order, step=step, action="bill", payload={})
        db.flush()
        assert row.stage == "billed" and row.amount == Decimal("216.2000")
        assert "bill" not in svc.can(db, row, None), (
            "«Rechnung stellen» steht nach der Rechnung noch da – dann ist die Regel "
            "wieder eine Zählung statt der Struktur."
        )
        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=order, step=step, action="bill", payload={})
        assert e.value.status_code == 409, "Eine zweite Rechnung geht durch."
    finally:
        db.rollback(); db.close()


def test_an_issued_invoice_cannot_be_taken_back():
    """►►► **Ab dem Versenden ist die Rechnung unveränderlich.** ◄◄◄

    Davor gibt es ``unbill`` – dieselbe Anatomie wie ``ask``/``unask``: *jede Zusage nach
    aussen hat ihre Gegenhandlung an derselben Stelle*, und sie endet genau dort, wo der
    Beleg wirklich hinausgeht. Was danach falsch bleibt, korrigiert ein **eigener Beleg**.

    Bug-Form: ``unbill`` nach ``issue`` geht durch.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, _who, _art = _agreed(db)
        svc.apply(db, order=order, step=step, action="bill", payload={})
        db.flush()
        assert "unbill" in svc.can(db, row, None), (
            "Eine Rechnung im Haus lässt sich nicht zurücknehmen – dann ist ein "
            "Tippfehler eine Sackgasse."
        )
        svc.apply(db, order=order, step=step, action="issue", payload={})
        db.flush()
        assert row.issued_on is not None
        assert "unbill" not in svc.can(db, row, None)
        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=order, step=step, action="unbill", payload={})
        assert e.value.status_code == 409, (
            "Eine versendete Rechnung lässt sich zurücknehmen – draussen liegt ein "
            "Papier, das jemand gelesen hat."
        )
    finally:
        db.rollback(); db.close()


def test_an_invoice_with_a_payment_cannot_be_taken_back():
    """**Wo Geld geflossen ist, war die Rechnung draussen** – was immer jemand angeklickt
    hat.

    Bug-Form: ``unbill`` bei eingegangener Zahlung geht durch.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, _who, _art = _agreed(db)
        svc.apply(db, order=order, step=step, action="bill", payload={})
        svc.apply(db, order=order, step=step, action="issue", payload={})
        svc.apply(db, order=order, step=step, action="pay",
                  payload={"method": "cash", "amount": "10.00"})
        db.flush()
        # Selbst ohne das Versand-Datum bliebe sie stehen: die Zahlung allein genügt.
        row.issued_on = None
        db.flush()
        assert "unbill" not in svc.can(db, row, None)
        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=order, step=step, action="unbill", payload={})
        assert e.value.status_code == 409, (
            "Eine bezahlte Rechnung lässt sich zurücknehmen – dann steht Geld auf einem "
            "Beleg, den es nicht mehr gibt."
        )
    finally:
        db.rollback(); db.close()


def test_a_withdrawn_invoice_keeps_its_number():
    """►►► **Die Nummer bleibt am Beleg — und wird wiederverwendet.** ◄◄◄

    Eine zurückgenommene Rechnung ist **nie hinausgegangen**: es gibt sie nach aussen
    nicht, niemand kann nach ihr fragen, und die neu gestellte ist **derselbe Beleg**,
    korrigiert, bevor er das Haus verliess.

    *Das Konzept hatte «sie verbraucht ihre Nummer» notiert – aus der Zeit, als eine
    Rechnung eine Zeile war. Seit sie der Beleg ist, gäbe es keine zweite Zeile, die die
    verbrauchte Nummer halten könnte: man bräuchte eine Spalte nur dafür.*

    Bug-Form: die neu gestellte Rechnung bekommt eine andere Nummer.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, _who, _art = _agreed(db)
        svc.apply(db, order=order, step=step, action="bill", payload={})
        db.flush()
        first = row.number
        assert first == f"{order.object_id}-1"
        svc.apply(db, order=order, step=step, action="unbill", payload={})
        db.flush()
        assert row.stage == "agreed" and row.billed_on is None and row.amount is None
        assert row.number == first, "Die Nummer ist mit der Rücknahme verschwunden."
        svc.apply(db, order=order, step=step, action="bill", payload={})
        db.flush()
        assert row.number == first, (
            f"Die neu gestellte Rechnung heisst «{row.number}» statt «{first}» – dann "
            f"hat die Serie eine Lücke, zu der es keinen Datensatz gibt."
        )
    finally:
        db.rollback(); db.close()


def test_there_is_no_reverse_verb_at_the_module():
    """►►► **Die Entscheidung «Storno oder Gutschrift» trifft niemand mehr.** ◄◄◄

    Sie fällt aus dem **Zeitpunkt** heraus: vor dem Versenden gibt es nur ``unbill``,
    danach nur den Korrekturbeleg. Ein Verb, das je nach Bezahlstatus «Stornieren» oder
    «Gutschrift» hiess, waren zwei Sachverhalte, die so taten, als wären sie einer.

    Bug-Form: ``reverse`` steht wieder in ``VERBS``.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo
    from app.services import voucher as svc

    assert "reverse" not in svc.VERBS, "«reverse» ist zurück."
    for gone in ("reverse_word", "CREDIT_WORD", "STORNO_WORD"):
        assert not hasattr(vo, gone), f"«{gone}» ist zurück."


def test_a_payment_needs_no_allocation():
    """►►► **Welche Rechnung diese Zahlung meint, fragt niemand mehr.** ◄◄◄

    Je Modul gibt es **eine**, und sie *ist* der Beleg – die Frage hat genau eine Antwort,
    und eine Frage mit genau einer Antwort stellt man nicht. *Die Aufteilung über mehrere
    Rechnungen bleibt real; sie liegt jetzt zwingend über Modulgrenzen und gehört damit
    zur offenen-Posten-Liste (``docs/backlog.md``).*

    Bug-Form: eine Zuordnungs-Tabelle wird wieder gelesen.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    import app.models as models
    from app.models import VoucherEntry
    from app.services import voucher as svc

    assert not hasattr(models, "VoucherAllocation"), "Die Zuordnungs-Tabelle ist zurück."
    for gone in ("charge_id", "kind"):
        assert not hasattr(VoucherEntry, gone), (
            f"«{gone}» steht wieder an der Geld-Zeile – dann gibt es die Rechnung "
            f"zweimal."
        )
    code = _code(BACKEND / "app" / "services" / "voucher.py")
    for gone in ("paid_map", "allocate(", "live_charge", "open_charges"):
        assert gone not in code, f"«{gone}» wird wieder gelesen."
    for gone in ("allocate", "paid_map", "live_charge", "open_charges", "open_of"):
        assert not hasattr(svc, gone), f"«{gone}» ist zurück."


def test_a_correction_carries_the_reference_to_what_it_corrects():
    """►►► **Der Verweis steht auf dem PAPIER** (MWSTG Art. 26). ◄◄◄

    Eine **Ableitung** über ``corrects_id``, kein zweites Feld, das jemand abtippt: ohne
    ihn wäre eine Gutschrift eine zweite Rechnung mit negativem Vorzeichen, und niemand
    könnte sagen, was sie mindert.

    Bug-Formen: (a) ``corrects_id`` kommt nicht an; (b) der Verweis steht nicht in der
    Antwort; (c) ein Beleg korrigiert sich selbst; (d) eine Kette läuft im Kreis.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, who, art = _agreed(db)
        svc.apply(db, order=order, step=step, action="bill", payload={})
        svc.apply(db, order=order, step=step, action="issue", payload={})
        db.flush()
        back_order, back_step, back, _w, _a = _scene(db, quantity=1, parties=[who[0]])
        svc.apply(db, order=back_order, step=back_step, action="correct",
                  payload={"corrects": row.id})
        db.flush()
        assert back.corrects_id == row.id, "Der Verweis kommt nicht an (a)."
        seen = svc.embed_data(db, order=back_order, step=back_step, viewer=None)
        assert seen is not None and seen["corrects"] is not None, (
            "Der Verweis steht nicht in der Antwort (b) – dann kann er nicht auf dem "
            "Papier stehen."
        )
        assert seen["corrects"]["number"] == row.number
        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=back_order, step=back_step, action="correct",
                      payload={"corrects": back.id})
        assert e.value.status_code == 400, "Ein Beleg korrigiert sich selbst (c)."
        # (d) **Kein Kreis** – die Kette muss irgendwo enden. Dafür braucht es einen
        # zweiten gestellten Beleg, der auf den ersten zurückzeigt; der Verweis wird dort
        # von Hand gesetzt, weil das Verb in der Stufe «Rechnung» keinen Zugang mehr hat
        # (das hat seinen eigenen Wächter).
        credit_order, credit_step, credit = _credit(db, target=row, who=who[0])
        svc.apply(db, order=credit_order, step=credit_step, action="bill", payload={})
        db.flush()
        row.corrects_id = credit.id
        db.flush()
        third_order, third_step, _third, _w2, _a2 = _scene(db, quantity=1,
                                                           parties=[who[0]])
        with pytest.raises(HTTPException) as e:
            svc.apply(db, order=third_order, step=third_step, action="correct",
                      payload={"corrects": credit.id})
        assert e.value.status_code == 400 and "Kreis" in str(e.value.detail), (
            "Eine Kette aus Korrekturen läuft im Kreis (d)."
        )
    finally:
        db.rollback(); db.close()


def test_a_correction_may_live_in_another_order():
    """►►► **Die Gutschrift gehört dorthin, wo die Ware zurückkommt.** ◄◄◄

    *«Gerade bei Retouren wäre der Warenverkehr getrennt von der monetären Abwicklung –
    aber dort, wo das Geschehen ist, soll ich es auch abwickeln können.»*

    Und das Modell wird dadurch **kleiner**: die Positionen der Gutschrift entstehen von
    selbst aus den Stücken, die zurückkommen (``sync_lines``). Die **Warenlogik ist die
    Mengenkontrolle des Geldes** – man kann nicht mehr zurücknehmen, als geliefert wurde.

    Bug-Form: der Dienst weist einen Beleg aus einem fremden Auftrag ab.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, who, _art = _agreed(db)
        svc.apply(db, order=order, step=step, action="bill", payload={})
        svc.apply(db, order=order, step=step, action="issue", payload={})
        db.flush()
        back_order, back_step, back, _w, _a = _scene(db, quantity=1, parties=[who[0]])
        assert back_order.id != order.id, "Die Szene liegt im selben Auftrag."
        svc.apply(db, order=back_order, step=back_step, action="correct",
                  payload={"corrects": row.id})
        db.flush()
        assert back.corrects_id == row.id
        # **Und die Auswahl findet ihn** – gesucht wird über alle Aufträge desselben
        # Partners, nicht in dem einen, in dem man gerade steht.
        svc.apply(db, order=back_order, step=back_step, action="correct",
                  payload={"corrects": None})
        db.flush()
        found = svc.correctable(db, back, back_step)
        assert row.id in [r["id"] for r in found], (
            "Die Auswahl findet die Rechnung des anderen Auftrags nicht – dann müsste "
            "man die Gutschrift dort stellen, wo die Ware nicht ist."
        )
        assert found[0]["order_object_id"] == order.object_id
    finally:
        db.rollback(); db.close()


def test_a_correction_is_stored_with_a_negative_amount():
    """►►► **Die Positionen tragen positive Preise — das Vorzeichen setzt ``bill``.** ◄◄◄

    «3 × Getriebe à 200» ist die Aussage, und sie ist MWST-korrekt. Danach rechnet **jede**
    Zahl vorzeichenrichtig, ohne eine einzige Fallunterscheidung beim Lesen.

    Bug-Form: ``amount`` bleibt positiv, der Saldo addiert statt zu mindern.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, who, _art = _agreed(db)
        svc.apply(db, order=order, step=step, action="bill", payload={})
        svc.apply(db, order=order, step=step, action="issue", payload={})
        db.flush()
        back_order, back_step, back = _credit(db, target=row, who=who[0])
        svc.apply(db, order=back_order, step=back_step, action="bill", payload={})
        db.flush()
        assert back.amount is not None and back.amount < 0, (
            f"Die Gutschrift steht mit {back.amount} da – positiv addiert sie, statt zu "
            f"mindern."
        )
        assert svc.balance_of(db, back).open < 0, "Der Saldo mindert nicht."
    finally:
        db.rollback(); db.close()


def test_a_correction_mirrors_the_tax_split():
    """**Gespiegelt wird die ganze Zeile, nicht nur ihre Zahlen.**

    Schlüssel, Name und Pflichtsatz gehören zur Aussage, die zurückgenommen wird – sonst
    verlöre die Gutschrift ausgerechnet den Rechtsgrund, den sie mindert.

    Bug-Form: die Steuer wird nicht gespiegelt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, who, _art = _agreed(db)
        svc.apply(db, order=order, step=step, action="bill", payload={})
        svc.apply(db, order=order, step=step, action="issue", payload={})
        db.flush()
        back_order, back_step, back = _credit(db, target=row, who=who[0])
        svc.apply(db, order=back_order, step=back_step, action="bill", payload={})
        db.flush()
        assert back.vat, "Die Gutschrift trägt keine Steuer-Aufteilung."
        one = back.vat[0]
        assert Decimal(one["net"]) < 0 and Decimal(one["tax"]) < 0, (
            f"Die Steuer ist nicht gespiegelt: {one}."
        )
        assert one["vat"] == row.vat[0]["vat"] and one["label"] == row.vat[0]["label"], (
            "Der Rechtsgrund ist beim Spiegeln verlorengegangen."
        )
    finally:
        db.rollback(); db.close()


def test_the_frozen_tax_survives_a_price_change():
    """►►► **Ein Beleg behält, was auf ihm stand.** ◄◄◄

    Nachgerechnet wäre die Vergangenheit eine Funktion der Gegenwart, und eine Abrechnung
    über ein abgeschlossenes Quartal ergäbe beim zweiten Lauf andere Zahlen.

    Bug-Form: die Steuer wird beim Lesen nachgerechnet.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, _who, _art = _agreed(db)
        svc.apply(db, order=order, step=step, action="bill", payload={})
        db.flush()
        before = [dict(r) for r in row.vat]
        amount = row.amount
        # Die Positionen **hinter** dem Beleg verändern – so, wie es eine geänderte
        # Rechenregel täte.
        for line in svc.lines_of(db, row):
            line.price = Decimal("1.00")
        db.flush()
        seen = svc.embed_data(db, order=order, step=step, viewer=None)
        assert seen is not None and seen["invoice"] is not None
        assert seen["invoice"]["vat"] == before, (
            "Die Steuer der gestellten Rechnung wurde nachgerechnet."
        )
        assert row.amount == amount
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
        svc.apply(db, order=order, step=step, action="bill",
                  payload={"amount": "99.00", "vat": "normal",
                           "reference": "R-2026-7"})
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
        assert (seen["charged"] is None and seen["paid"] is None
                and seen["entries"] == [] and seen["invoice"] is None), (
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
                  "reference", "note", "booked_on", "billed_on", "issued_on",
                  "corrects", "entry",
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

        # (a) **Ohne gestellte Rechnung gibt es nichts zu begleichen.**
        empty = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert empty["ways"] == [], (
            "Es gibt Wege, obwohl nichts gefordert ist (a) – dann zeigt die Karte eine "
            "Wahl, die ins Leere führt."
        )

        # ►►► **Und auch die gestellte Rechnung genügt nicht: sie muss DRAUSSEN sein.**
        # ◄◄◄ Man kassiert nicht auf ein Papier, das der Zahlende nie gesehen hat.
        svc.apply(db, order=order, step=step, action="bill", payload={}, actor=staff)
        db.flush()
        assert svc.embed_data(db, order=order, step=step, viewer=staff)["ways"] == [], (
            "Es gibt Wege, obwohl die Rechnung noch im Haus liegt (a)."
        )
        svc.apply(db, order=order, step=step, action="issue", payload={}, actor=staff)
        db.flush()

        seen = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert seen["invoice"] is not None, (
            "Der Beleg trägt keine Rechnung – sie IST er."
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


def test_nobody_asks_which_invoice_is_meant():
    """►►► **Die Frage hat genau eine Antwort — also stellt man sie nicht.** ◄◄◄

    Hier stand ``settle_charge``: *welche Rechnung meint das Fach «Begleichen»?* Sie war
    nötig, solange ein Beleg mehrere Forderungszeilen tragen konnte – und genau daraus kam
    #859 («kassiert wurde immer die älteste offene, egal an welchem Knopf jemand geklickt
    hat»). Seit der Beleg **die** Rechnung ist, gibt es nichts mehr zu benennen.

    Bug-Formen: (a) die Angabe ist zurück; (b) eine bezahlte Rechnung bietet weiter Wege
    an; (c) ein unterlegener Angefragter liest sie.
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
        svc.apply(db, order=order, step=step, action="bill", payload={}, actor=staff)
        svc.apply(db, order=order, step=step, action="issue", payload={}, actor=staff)
        db.flush()
        seen = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert "settle_charge" not in seen, "Die Angabe ist zurück (a)."
        assert seen["ways"], "Nach dem Versenden gibt es keinen Weg zum Geld."

        # (c) **Wer den Zuschlag nicht hat, sieht die Rechnung gar nicht.**
        assert svc.embed_data(db, order=order, step=step,
                              viewer=two)["invoice"] is None, (
            "Ein unterlegener Angefragter liest die Rechnung (c)."
        )

        # (b) **Bezahlt heisst: nichts mehr zu begleichen.**
        svc.apply(db, order=order, step=step, action="pay",
                  payload={"amount": seen["open"], "method": "cash"}, actor=staff)
        db.flush()
        done = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert done["open"] == "0.00" and done["invoice"]["state"] == "settled", (
            "Eine vollständig bezahlte Rechnung steht nicht auf «beglichen» (b)."
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


def test_an_invoice_says_how_it_stands():
    """►►► **Der Zustand einer Rechnung – abgeleitet, mit Toleranz** (Testnotiz #991).◄◄◄

    *Offen · Teilweise bezahlt · Beglichen · Überfällig · Überzahlt* – aus zwei Zahlen
    (Betrag und Rest), **null Spalten**. Und in den **drei** Ampeltönen des Hauses: eine
    vierte Farbe für Geld wäre eine zweite Farbsprache.

    ►►► **EINE Funktion, nicht zwei.** ◄◄◄ Hier standen ``charge_state`` (je
    Forderungs-Zeile) und ``balance_state`` (über den Saldo) nebeneinander – zwei
    Ableitungen mit geteilten Wörtern und geteilter Toleranz, weil ein Beleg mehrere
    Forderungen tragen konnte. Seit der Beleg **die** Rechnung ist, sind Betrag und Saldo
    dieselben zwei Zahlen: eine Frage, eine Antwort.

    Bug-Formen: (a) «teilweise bezahlt» gibt es nicht – eine angezahlte Rechnung sieht aus
    wie eine unberührte; (b) drei Rappen Restdifferenz halten sie für immer offen;
    (c) eine unbeglichene **Gutschrift** (negative Rechnung) heisst «Überzahlt»;
    (d) der Ton kommt aus einer eigenen Farbliste statt aus den drei des Hauses;
    (e) der Zustand erreicht die Oberfläche nicht; (f) die beiden Ableitungen sind wieder
    zwei.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from decimal import Decimal
    from app.domain import voucher as vo
    from app.services import voucher as svc

    d = Decimal
    # (f) **Eine Ableitung, nicht zwei.**
    for gone in ("charge_state", "balance_state", "CHARGE_STATES", "BALANCE_STATES"):
        assert not hasattr(vo, gone), f"«{gone}» ist zurück (f)."
    # (a) **Angezahlt ist ein eigener Zustand.**
    assert vo.invoice_state(d("100"), d("40"))["state"] == "partial", (
        "Eine angezahlte Rechnung sieht aus wie eine unberührte (a)."
    )
    assert vo.invoice_state(d("100"), d("100"))["state"] == "open"
    # (b) **Rundungstoleranz** – sonst mahnt man wegen drei Rappen.
    assert vo.invoice_state(d("100"), d("0.03"))["state"] == "settled", (
        "Drei Rappen halten die Rechnung offen (b)."
    )
    assert vo.invoice_state(d("100"), d("0.00"))["state"] == "settled"
    # (c) **Eine Gutschrift ist eine negative Rechnung** – und unbeglichen ist sie offen,
    #     nicht überzahlt. Gerechnet wird mit dem Vorzeichen, nicht mit «grösser null».
    assert vo.invoice_state(d("-100"), d("-100"))["state"] == "open", (
        "Eine unbeglichene Gutschrift heisst «Überzahlt» (c)."
    )
    assert vo.invoice_state(d("-100"), d("-40"))["state"] == "partial"
    assert vo.invoice_state(d("100"), d("-20"))["state"] == "overpaid"
    assert vo.invoice_state(d("-100"), d("20"))["state"] == "overpaid"
    # Überfällig schlägt «offen».
    assert vo.invoice_state(d("100"), d("100"), overdue=True)["state"] == "overdue"
    # (d) **Drei Töne, keine vierte Farbe.**
    tones = {tone for _, tone in vo.INVOICE_STATES.values()}
    assert tones <= {"done", "pending", "danger"}, (
        f"Ein Ton ausserhalb der drei des Hauses (d): {tones}."
    )

    # (e) **Und er reist mit** – gemessen über den echten Dienstpfad.
    db = _db()
    try:
        order, step, row, _who, _art = _agreed(db, price="100.00")
        svc.apply(db, order=order, step=step, action="bill", payload={})
        svc.apply(db, order=order, step=step, action="issue", payload={})
        db.flush()
        staff = _party(db, "Personal", "admin")
        seen = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert seen["invoice"]["state_label"] and seen["invoice"]["state_tone"], (
            "Der Zustand erreicht die Oberfläche nicht (e) – dann rechnet sie ihn "
            "wieder selbst."
        )
        # ►►► **Und der Saldo sagt DASSELBE** – es ist dieselbe Zahl. ◄◄◄
        assert seen["open_state"] == seen["invoice"]["state"], (
            "Rechnung und Saldo geben zwei Antworten auf dieselbe Frage (f)."
        )
        # Eine Anzahlung macht daraus «teilweise bezahlt».
        svc.apply(db, order=order, step=step, action="pay",
                  payload={"amount": "50.00", "method": "cash"})
        db.flush()
        again = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert again["invoice"]["state"] == "partial", (
            f"Die angezahlte Rechnung sagt «{again['invoice']['state']}» (a/e)."
        )
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ►► Testnotizen #995–#1003 — wählen ist nicht anfragen, und der Saldo ist eine Farbe
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_party_is_chosen_before_it_is_asked():
    """►►► **Wählen und anfragen sind zwei Dinge** (Testnotiz #1000). ◄◄◄

    *«Wurde beim Anlegen kein Partner vorgewählt, lässt er sich nachträglich nicht mehr
    setzen. Die Auswahl wird korrekt angezeigt, aber nicht übernommen/persistiert.»*

    **Nachgestellt, nicht vermutet.** Die Wahl im freien Feld löste sofort ``ask`` aus –
    und das ist die Handlung, mit der der Beleg **nach aussen** geht: sie verlangt Preis,
    beide Fristen und die Lieferbedingung (#964/#985). An einem frischen Modul fehlt
    davon naturgemäss alles, der Dienst wies mit einem Satz ab, und die Wahl war weg.

    Damit war *«wen meine ich»* die letzte Angabe des Belegs **ohne eigenes Verb** –
    dieselbe Lücke wie bei den Fristen, nur eine Runde später. Die Regel gilt unverändert:
    *jeder änderbare Wert des Belegs wird sofort persistiert.*

    Bug-Formen: (a) das Verb ``party`` gibt es nicht; (b) die Wahl setzt einen
    unvollständigen Beleg voraus (also wieder ``ask``); (c) sie überlebt das erneute Lesen
    nicht; (d) sie erreicht den Belegkopf nicht – dann steht «Anschrift fehlt» über
    jemandem, den man eine Zeile höher ausgewählt hat; (e) ``ask`` findet sie nicht und
    verlangt die Nummer ein zweites Mal; (f) es gibt keinen Weg zurück; (g) irgendeine
    Nummer geht durch.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    import pytest as _pytest
    from fastapi import HTTPException
    from app.services import voucher as svc
    from app.models import Voucher

    db = _db()
    try:
        # **Ein Modul ohne vorgewählten Partner** – «leer heisst frei».
        order, step, row, _who, _art = _scene(db, parties=[])
        assert not step.config.get("parties"), "Die Szene hat doch einen Partner."
        them = _party(db, "Muster AG", "customer")

        # (a)/(b) **Die Wahl geht am frischen Beleg** – ohne Preis, ohne Fristen.
        assert "party" in svc.can(db, row, None), (
            "Es gibt kein Verb, mit dem man die Gegenpartei wählt (a)."
        )
        svc.apply(db, order=order, step=step, action="party",
                  payload={"party": them.object_id})
        db.flush()

        # (c) **Und sie überlebt** – neu gelesen, nicht aus dem Objekt.
        db.expire_all()
        again = db.query(Voucher).filter(Voucher.id == row.id).one()
        assert svc.parties_on(again) == [them.object_id], (
            f"Die Wahl überlebt das Speichern nicht (c): {svc.parties_on(again)}."
        )

        # (d) **Sie steht im Belegkopf** – der Adressat ist, wer gewählt ist.
        staff = _party(db, "Personal", "admin")
        seen = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert [r["object_id"] for r in seen["recipients"]] == [them.object_id], (
            "Die Wahl erreicht die Auswahl-Zeile nicht (d)."
        )
        assert seen["customer"]["object_id"] == them.object_id, (
            "Der Belegkopf kennt den Gewählten nicht (d) – dann meldet er «Anschrift "
            "fehlt» über jemanden, den man ausgewählt hat."
        )

        # (e) **`ask` findet sie von selbst** – ohne die Nummer ein zweites Mal zu nennen.
        _price(db, order, step, row, price="10.00")
        svc.apply(db, order=order, step=step, action="terms",
                  payload={"lead_days": 5, "payment_days": 30})
        db.flush()
        svc.apply(db, order=order, step=step, action="ask", payload={})
        db.flush()
        assert [q.party_id for q in svc.quotes_of(db, row)] == [them.object_id], (
            "«Anfragen» findet den gewählten Partner nicht (e)."
        )

        # (f) **Und es gibt den Weg zurück** – eine Handlung, ein Klick: die Zeile und die
        #     Wahl verschwinden zusammen.
        assert "unask" in svc.can(db, row, None), "Die Wahl lässt sich nicht zurücknehmen (f)."
        svc.apply(db, order=order, step=step, action="unask",
                  payload={"party": them.object_id})
        db.flush()
        assert not svc.quotes_of(db, row) and not svc.parties_on(row), (
            f"Zurückgenommen ist nur die Hälfte (f): {svc.parties_on(row)} / "
            f"{[q.party_id for q in svc.quotes_of(db, row)]}."
        )

        # (g) **Geprüft wird die Wahl selbst** – eine Auswahl, die der Dienst später
        #     abwiese, wäre keine.
        with _pytest.raises(HTTPException) as bad:
            svc.apply(db, order=order, step=step, action="party",
                      payload={"party": 999_999_999})
        assert bad.value.status_code == 400, (
            f"Irgendeine Nummer geht durch (g): {bad.value.status_code}."
        )
    finally:
        db.rollback()
        db.close()


def test_the_balance_says_how_it_stands_in_one_number():
    """►►► **Der Saldo — eine Zahl, und ihre Farbe ist die Aussage** (Testnotiz #997).◄◄◄

    *«Das Wort ‹Offen› entfällt, der Status wird ausschliesslich über die Farbe des
    Betrags getragen: offen orange · überfällig rot · beglichen grün · überzahlt grün mit
    ausgewiesenem Guthaben.»*

    ►►► **Und es ist DIESELBE Ableitung wie an der Rechnung.** ◄◄◄ Es waren einmal zwei
    (``charge_state`` je Zeile, ``balance_state`` über den Saldo), weil ein Beleg mehrere
    Forderungen tragen konnte. Seit er **die** Rechnung ist, sind Betrag und Saldo
    dieselben zwei Zahlen – zwei Funktionen dafür wären zwei Massstäbe.

    Bug-Formen: (a) der Zustand wird gar nicht geliefert, also rechnet ihn die Oberfläche
    wieder selbst; (b) Rechnung und Saldo geben zwei Antworten; (c) eine Gegenpartei ohne
    Zuschlag liest die Zahl mit.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc
    db = _db()
    try:
        # Zwei Angefragte, einer bekommt den Zuschlag – (c) braucht einen Unterlegenen.
        winner = _party(db, "Muster AG", "customer")
        loser = _party(db, "Zweiter", "customer")
        order, step, row, who, _art = _agreed(db, quantity=1, price="100.00",
                                              parties=[winner, loser])
        svc.apply(db, order=order, step=step, action="bill", payload={})
        svc.apply(db, order=order, step=step, action="issue", payload={})
        db.flush()
        staff = _party(db, "Personal", "admin")
        seen = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert seen["open_state"] == "open" and seen["open_state_tone"] == "pending", (
            f"Der Saldo sagt seinen Zustand nicht (a): {seen['open_state']}."
        )
        # Überzahlt: mehr geflossen, als gefordert war.
        svc.apply(db, order=order, step=step, action="pay",
                  payload={"amount": "150.00", "method": "cash"})
        db.flush()
        over = svc.embed_data(db, order=order, step=step, viewer=staff)
        assert over["open_state"] == "overpaid", (
            f"Die Überzahlung wird nicht erkannt: {over['open_state']}."
        )
        # (b) **Eine Frage, eine Antwort.**
        assert over["open_state"] == over["invoice"]["state"], (
            "Rechnung und Saldo geben zwei Antworten auf dieselbe Frage (b)."
        )
        # (c) **Wer keinen Zuschlag hat, liest keine Zahl** – und damit auch keinen
        #     Zustand über sie.
        blind = svc.embed_data(db, order=order, step=step, viewer=loser)
        # *Gefragt sind **alle** Angaben: der erste Anlauf prüfte nur den Schlüssel und
        # liess Wort und Ton durch – gemessen, nachgeschärft.*
        leaked = {k: blind[k] for k in
                  ("open", "open_state", "open_state_label", "open_state_tone")
                  if blind[k] is not None}
        assert not leaked, f"Ein Unterlegener liest den Saldo mit (c): {leaked}."
        assert blind["invoice"] is None, "Er liest die Rechnung mit (c)."
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ►► ZWEI ENTITÄTEN, KEIN BELEGTYP — Rechnung · Zahlung · Kleinbetragstoleranz
# ═══════════════════════════════════════════════════════════════════════════════

def test_there_is_no_document_type_only_a_sign_and_a_reference():
    """►►► **Es gibt KEINEN Belegtyp im Code — und auch keinen «Grund».** ◄◄◄

    *«Kein Belegtyp im Code. Vorzeichen positiv = Forderung, negativ = Korrektur.»*

    Das Datenmodell trägt genau **zwei** Dinge: den Beleg (der *ist* die Rechnung) und
    seine Zahlungen. Das **Vorzeichen** sagt, was jedes von beiden tut – eine Gutschrift
    ist eine negative Rechnung, eine Erstattung eine negative Zahlung.

    ►►► **Der «Grund» ist mitgegangen** (Testnotiz #1021). ◄◄◄ Er war ein Freitextfeld mit
    Vorschlagsliste – also die Belegart mit anderem Namen, nur ohne Wirkung. Beim Stellen
    einer Rechnung ist er überflüssig (die Positionen sagen es), bei einer Korrektur
    genügt die **Referenz auf den Beleg**, den sie korrigiert (``corrects_id``).

    Bug-Formen: (a) irgendwo steht wieder eine Belegart-Aufzählung; (b) der Grund ist
    wieder da (Vokabel, Modell, Tür oder Dienst); (c) die Geld-Zeile trägt wieder eine
    **Art**, und damit gibt es die Rechnung zweimal.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo
    from app.models.voucher import VoucherEntry
    from app.schemas.voucher import VoucherEmbed, VoucherEntryOut, VoucherUpdate

    # (a)/(c) **Es gibt keine Art mehr** – die beiden Entitäten sind zwei Tabellen.
    for name in ("KINDS", "CHARGE", "PAYMENT", "assert_kind"):
        assert not hasattr(vo, name), (
            f"«{name}» ist zurück (a/c) – eine Art an der Zeile heisst, dass die Rechnung "
            f"wieder in ihr steckt."
        )
    assert "kind" not in VoucherEntry.__mapper__.columns, (
        "Die Geld-Zeile trägt wieder eine Art (c)."
    )
    # (b) **Den Grund gibt es nirgends mehr.** Geprüft wird die Vokabel, das **Mapping**
    #     (eine Spalte in der Datenbank ist kein Feld im Code) und die **Tür** – ein Feld,
    #     das die Oberfläche nicht anbietet, der Dienst aber annimmt, wäre die Hintertür
    #     zu einer Angabe, die niemand liest.
    for name in ("REASONS", "REASON_LABEL", "assert_reason", "WRITE_OFF_REASON"):
        assert not hasattr(vo, name), f"«{name}» ist wieder da (b)."
    assert "reason" not in VoucherEntry.__mapper__.columns, (
        "Der Grund ist wieder ein gemapptes Feld (b)."
    )
    for schema in (VoucherUpdate, VoucherEntryOut, VoucherEmbed):
        assert not any("reason" in f for f in schema.model_fields), (
            f"«{schema.__name__}» führt den Grund wieder (b): "
            f"{[f for f in schema.model_fields if 'reason' in f]}."
        )
    assert VoucherUpdate(action="pay", amount="-12.00",
                         **{"reason": "Retoure"}).changes().get("reason") is None, (
        "Ein gesendeter Grund kommt wieder an (b) – dann gibt es ihn faktisch doch."
    )


def test_a_small_residue_may_be_written_off_but_never_by_itself():
    """►►► **Kleinbetragstoleranz — angeboten, nie automatisch.** ◄◄◄

    *«Restsaldo unter 1.00 CHF kann als Differenz ausgebucht werden. Nicht automatisch.»*

    Es ist **kein neuer Mechanismus**: ausgebucht wird über eine ganz gewöhnliche
    **Zahlung** mit Gegenvorzeichen und dem Vermerk «Rundungsdifferenz» – eine Zahlung ist
    hier definiert als *was den offenen Betrag mindert*, und der Vermerk sagt, dass kein
    Geld geflossen ist. ``Balance.write_off`` sagt nur, **ob** die Lage vorliegt und **wie
    viel**.

    *Sie war einmal eine negative **Forderung**; die gibt es nicht mehr, seit der Beleg
    selbst die Rechnung ist – ein dritter Zeilentyp für achtzig Rappen wäre ein
    Mechanismus für einen Rundungsfehler.*

    Bug-Formen: (a) über der Toleranz wird es trotzdem angeboten (die stille
    Abschreibung); (b) die Zahl kommt ohne Gegenvorzeichen und bucht die Differenz
    doppelt; (c) es passiert von selbst.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, _who, _art = _agreed(db, quantity=1, price="100.00")
        for line in svc.lines_of(db, row):
            line.vat = "export"          # 0 % – runde Zahlen
        db.flush()
        svc.apply(db, order=order, step=step, action="bill", payload={})
        svc.apply(db, order=order, step=step, action="issue", payload={})
        db.flush()
        # (a) Zwanzig Franken bucht niemand «versehentlich» aus.
        svc.apply(db, order=order, step=step, action="pay",
                  payload={"amount": "80.00", "method": "cash"})
        db.flush()
        assert svc.balance_of(db, row).write_off is None, (
            "Zwanzig Franken werden als Differenz angeboten (a) – das ist die stille "
            "Abschreibung."
        )
        # Rest 0.03 – die Lage, um die es geht.
        svc.apply(db, order=order, step=step, action="pay",
                  payload={"amount": "19.97", "method": "cash"})
        db.flush()
        offer = svc.balance_of(db, row).write_off
        # (b) **Mit dem Gegenvorzeichen** – eine Zahl, die man erst noch drehen muss, wird
        #     einmal nicht gedreht.
        assert offer == Decimal("-0.0300"), f"Die Vorgabe stimmt nicht (b): {offer}."
        # (c) **Nichts passiert von selbst.**
        assert svc.balance_of(db, row).open == Decimal("0.0300"), (
            "Die Differenz wurde von selbst ausgebucht (c)."
        )
        svc.apply(db, order=order, step=step, action="pay",
                  payload={"amount": str(-offer), "method": "cash",
                           "note": vo.WRITE_OFF_NOTE})
        db.flush()
        assert svc.balance_of(db, row).open == Decimal("0.0000")
        # **Es ist eine ganz gewöhnliche Zahlung** – kein eigener Mechanismus, kein
        # eigenes Feld: dieselbe Zeile wie jede andere, nur mit dem Vermerk.
        booked = svc.entries_of(db, row)[-1]
        assert booked.note == vo.WRITE_OFF_NOTE and booked.amount == -offer, (
            f"Die Ausbuchung ist keine gewöhnliche Zahlung: {booked.note} {booked.amount}."
        )
    finally:
        db.rollback()
        db.close()


def test_a_money_line_carries_the_moment_it_was_booked():
    """►►► **Eine Auskunft braucht einen ZEITPUNKT, kein Datum** (Testnotiz #1014). ◄◄◄

    *«Ein Ereignis von vor wenigen Minuten wird als ‹Heute› angezeigt.»* – Dreimal
    gemeldet, und es lag nie an der Anzeige-Funktion: sie bekam ``booked_on``, einen
    **reinen Tag**, und aus einem Tag ohne Uhrzeit lässt sich «vor 5 Minuten» nicht
    ableiten. Ihn zu erfinden wäre schlimmer – gefehlt hat der Zeitpunkt.

    Bug-Form: die Zeile reist ohne ``booked_at``, und der Browser muss wieder raten.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.services import voucher as svc
    db = _db()
    try:
        order, step, row, _who, _art = _agreed(db, quantity=1, price="10.00")
        svc.apply(db, order=order, step=step, action="bill", payload={})
        svc.apply(db, order=order, step=step, action="issue", payload={})
        svc.apply(db, order=order, step=step, action="pay",
                  payload={"amount": "1.00", "method": "cash"})
        db.flush()
        staff = _party(db, "Personal", "admin")
        seen = svc.embed_data(db, order=order, step=step, viewer=staff)
        line = seen["entries"][0]
        assert line.get("booked_at") is not None, (
            "Die Geld-Zeile reist ohne Zeitpunkt – dann heisst alles von heute «Heute»."
        )
        assert line["booked_at"] != line["booked_on"], (
            "Der Zeitpunkt ist der Belegtag – dann sagt er dasselbe und nichts mehr."
        )
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ►► EINE ERSTATTUNG GEHT GENAU EINMAL HINAUS (Testnotiz #1018)
# ═══════════════════════════════════════════════════════════════════════════════

class _Refused(Exception):
    """Ein Fehler des Zahlungsdienstes – mit ``code``, wie er wirklich einen trägt."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fake_stripe(monkey, *, raises=None):
    """Der Zahlungsdienst als **Attrappe** – hier wird unsere Logik geprüft, nicht seine.

    Sie merkt sich jeden Aufruf mitsamt dem Idempotenz-Schlüssel: genau der ist die
    Aussage, um die es geht.
    """
    from app.services import stripe_pay

    calls: list[dict] = []

    class _Refund:
        @staticmethod
        def create(**kw):
            calls.append(kw)
            if raises is not None:
                raise raises
            return {"id": "re_test"}

    class _Api:
        Refund = _Refund

    monkey.setattr(stripe_pay, "_api", lambda: _Api)
    return calls


def _card_scene(db):
    """Ein zugesagter Beleg mit **einer gebuchten Karten-Zahlung** über 100.00.

    Die Zahlungsabsicht trägt je Szene eine eigene Nummer – eine Referenz gehört zu genau
    **einer** Zahlung im Haus, und das ist eine Regel des Dienstes, kein Fixture-Detail.
    """
    from app.services import voucher as svc
    order, step, row, _who, _art = _agreed(db, quantity=1, price="100.00")
    svc.apply(db, order=order, step=step, action="bill", payload={})
    svc.apply(db, order=order, step=step, action="issue", payload={})
    db.flush()
    from app.domain import voucher as vo
    intent = f"pi_{uuid.uuid4().hex[:12]}"
    svc.record_payment(db, row=row, amount=Decimal("100.00"),
                       reference=intent, method=vo.CARD)
    db.flush()
    return order, step, row, intent


def _webhook_refund(db, row, intent, *, total: int, refunds: list[dict]):
    """**Was der Webhook buchen würde** – über dieselbe Ableitung, ohne seinen Commit.

    ``_note_refund`` committet (der Zahlungsdienst meldet eine Tatsache, und die soll
    stehen) – in einer Prüfung risse das die ganze Szene aus dem Rollback. Geprüft wird
    darum die Ableitung selbst (``_refunds``) und die Buchung über dieselbe Tür.
    """
    from app.domain import voucher as vo
    from app.services import stripe_pay, voucher as svc
    data = {"payment_intent": intent, "amount_refunded": total,
            "refunds": {"data": refunds}}
    for ref, amount in stripe_pay._refunds(data, intent, row.currency):
        svc.record_payment(db, row=row, amount=-amount, reference=ref,
                           note="Erstattung", method=vo.CARD)
    db.flush()


def test_a_refund_never_goes_out_twice(monkeypatch):
    """►►► **Zweimal geklickt ist EINE Erstattung** (Testnotiz #1018). ◄◄◄

    *«Der Button lässt sich mehrfach drücken, dann erscheint ein technischer Fehlertext
    des Zahlungsdienstes.»*

    Drei Ebenen, und jede schliesst eine andere Lücke: der **Rest** (die fachliche
    Wahrheit, sobald gebucht ist), der **Idempotenz-Schlüssel** (das Fenster zwischen
    Klick und Meldung des Webhooks) und die **deutsche Meldung** (alles, was dem Dienst
    sonst noch missfällt).

    Bug-Formen: (a) der Aufruf geht ohne Schlüssel hinaus; (b) nach der gebuchten
    Erstattung ist die Zahlung weiter erstattbar; (c) der zweite Aufruf geht trotzdem
    hinaus; (d) mehr als der Rest lässt sich erstatten.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.services import stripe_pay, voucher as svc
    db = _db()
    try:
        _order, _step, row, intent = _card_scene(db)
        entry = svc.refundable(db, row)[0]
        assert svc.refundable_amount(db, row, entry) == Decimal("100.0000")

        # (a) **Der Aufruf trägt einen Schlüssel** – und er nennt den Stand VOR ihm.
        calls = _fake_stripe(monkeypatch)
        stripe_pay.refund(db, svc=svc, row=row, entry_id=entry.id)
        assert len(calls) == 1 and calls[0].get("idempotency_key"), (
            f"Die Erstattung geht ohne Idempotenz-Schlüssel hinaus (a): {calls}."
        )
        first_key = calls[0]["idempotency_key"]
        # **Ein zweiter Klick im selben Fenster trägt denselben Schlüssel** – beim Dienst
        # entsteht damit genau eine Erstattung, obwohl hier noch nichts gebucht ist.
        stripe_pay.refund(db, svc=svc, row=row, entry_id=entry.id)
        assert calls[1]["idempotency_key"] == first_key, (
            "Zwei Klicks im Wartefenster tragen verschiedene Schlüssel – dann erstattet "
            "der Dienst zweimal."
        )

        # (b) **Sobald der Webhook gemeldet hat, gibt es nichts mehr zu erstatten.**
        _webhook_refund(db, row, intent, total=10000,
                        refunds=[{"id": "re_1", "amount": 10000}])
        assert svc.refundable_amount(db, row, entry) == Decimal("0"), (
            "Die vollständig erstattete Zahlung hat wieder einen Rest (b)."
        )
        assert entry.id not in [e.id for e in svc.refundable(db, row)], (
            "Sie steht weiter in der Liste (b) – dann bleibt der Knopf stehen."
        )
        # (c) **Und der Weg dorthin ist zu** – mit einem Satz, nicht mit einem Rohfehler.
        with pytest.raises(HTTPException) as err:
            stripe_pay.refund(db, svc=svc, row=row, entry_id=entry.id)
        assert err.value.status_code == 409 and "erstatten" in err.value.detail, (
            f"Der zweite Aufruf geht hinaus oder sagt nichts (c): {err.value.detail}."
        )
    finally:
        db.rollback()
        db.close()


def test_a_partial_refund_leaves_the_rest_and_only_the_rest(monkeypatch):
    """**Teilerstattung: der Rest ist die Grenze – und er stimmt.**

    ►►► **Und zweimal 30 nacheinander sind zwei Erstattungen.** ◄◄◄ Genau darum nennt der
    Idempotenz-Schlüssel den **Stand vor dem Aufruf**: ohne ihn trügen beide denselben,
    und die zweite würde beim Dienst still verschluckt – ein Nicht-Effekt, den niemand
    sieht.

    Bug-Formen: (a) nach 30 von 100 stehen wieder 100 zur Verfügung; (b) 80 gehen durch,
    obwohl nur 70 übrig sind; (c) die zweite Meldung des Dienstes bucht nichts (die
    kumulierte Summe fällt auf die Referenz der ersten); (d) die zweite Erstattung über
    denselben Betrag trägt denselben Schlüssel.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.services import stripe_pay, voucher as svc
    db = _db()
    try:
        _order, _step, row, intent = _card_scene(db)
        entry = svc.refundable(db, row)[0]
        calls = _fake_stripe(monkeypatch)
        stripe_pay.refund(db, svc=svc, row=row, entry_id=entry.id, amount="30.00")
        _webhook_refund(db, row, intent, total=3000,
                        refunds=[{"id": "re_1", "amount": 3000}])
        # (a)
        assert svc.refundable_amount(db, row, entry) == Decimal("70.0000"), (
            f"Der Rest stimmt nicht (a): {svc.refundable_amount(db, row, entry)}."
        )
        # (b) **Mehr als der Rest geht nicht** – und der Satz nennt beide Zahlen.
        with pytest.raises(HTTPException) as err:
            stripe_pay.refund(db, svc=svc, row=row, entry_id=entry.id, amount="80.00")
        assert err.value.status_code == 409 and "70" in err.value.detail, (
            f"Mehr als der Rest geht durch (b): {err.value.detail}."
        )
        # (c) **Die zweite Erstattung wird gebucht** – je Erstattung eine Referenz, nicht
        #     je Belastung: die kumulierte Summe fiel sonst auf die Zeile der ersten und
        #     verschwand still.
        # (d) **Zweimal derselbe Betrag, zwei Vorhaben** – der Stand dazwischen ist
        #     gewachsen, also ist es auch der Schlüssel.
        stripe_pay.refund(db, svc=svc, row=row, entry_id=entry.id, amount="30.00")
        assert calls[-1]["idempotency_key"] != calls[0]["idempotency_key"], (
            "Eine zweite Teilerstattung über denselben Betrag trägt denselben Schlüssel "
            "(d) – der Dienst verschluckt sie still."
        )
        stripe_pay.refund(db, svc=svc, row=row, entry_id=entry.id, amount="20.00")
        _webhook_refund(db, row, intent, total=5000,
                        refunds=[{"id": "re_2", "amount": 2000},
                                 {"id": "re_1", "amount": 3000}])
        assert svc.refunded_on(db, row, entry) == Decimal("50.0000"), (
            f"Die zweite Erstattung ist nicht angekommen (c): "
            f"{svc.refunded_on(db, row, entry)}."
        )
    finally:
        db.rollback()
        db.close()


def test_a_raw_error_of_the_payment_service_never_reaches_the_screen(monkeypatch):
    """►►► **Der Rohfehler geht ins LOG, der Satz an die Tür** (Testnotiz #1018). ◄◄◄

    *«Charge has already been refunded»* stand in der Oberfläche – englisch, technisch,
    und über eine Lage, die wir selbst kennen. Übersetzt wird über den **Code** des
    Fehlers, nicht über seinen Wortlaut: der ist stabil, der Text nicht.

    Bug-Formen: (a) der englische Rohtext steht in der Antwort; (b) ein unbekannter Code
    bringt trotzdem Technisches durch.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.services import stripe_pay, voucher as svc
    db = _db()
    try:
        _order, _step, row, _intent = _card_scene(db)
        entry = svc.refundable(db, row)[0]
        raw = "Charge ch_123 has already been refunded."
        _fake_stripe(monkeypatch, raises=_Refused("charge_already_refunded", raw))
        with pytest.raises(HTTPException) as err:
            stripe_pay.refund(db, svc=svc, row=row, entry_id=entry.id)
        # (a)
        assert raw not in err.value.detail and "refund" not in err.value.detail.lower(), (
            f"Der Rohtext des Dienstes steht in der Antwort (a): {err.value.detail}."
        )
        assert "bereits" in err.value.detail, (
            f"Der Satz sagt nicht, was los ist: {err.value.detail}."
        )
        # (b) **Was wir nicht übersetzen können, bleibt allgemein** – eine geratene
        #     Ursache schickt jemanden in die falsche Richtung.
        _fake_stripe(monkeypatch, raises=_Refused("something_new", "Internal oops at 0x1"))
        with pytest.raises(HTTPException) as err:
            stripe_pay.refund(db, svc=svc, row=row, entry_id=entry.id)
        assert err.value.detail == stripe_pay.STRIPE_TROUBLE, (
            f"Ein unbekannter Fehler bringt Technisches durch (b): {err.value.detail}."
        )
    finally:
        db.rollback()
        db.close()
