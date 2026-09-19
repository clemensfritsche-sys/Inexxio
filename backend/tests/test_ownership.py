"""**Der Besitz — ein zweiter Zeiger, gesetzt vom Zahlungsmodul.**

Die Regeln aus ``docs/arbeitsauftrag-besitz.md``. Der Kern in einem Satz: *wo ein Stück
liegt* und *wem es gehört* sind zwei Aussagen, die einander nicht bedingen — und keine von
beiden ist ein Status.

Geprüft über die **echten** Dienstpfade gegen echtes PostgreSQL: die interessanten Fehler
entstehen zwischen den Schritten, nicht in einem nachgestellten Zustand.

Jede Prüfung nennt in ihrem Docstring ihre **Bug-Form** — ein Wächter, der nie anschlägt,
ist von einem kaputten nicht zu unterscheiden.
"""

import os
import pathlib
import uuid

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
    """Ein Haus, das Belege stellen kann – dieselbe Szene wie im Beleg-Wächter."""
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


def _party(db, name: str, role: str = "customer"):
    from app.models import UserProfile
    from app.services import objects as obj
    user = UserProfile(
        firebase_uid=f"test-{uuid.uuid4()}", email=f"{uuid.uuid4()}@example.test",
        company_name=name, role=role, object_id=obj.next_object_id(db),
        address_line1="Werkweg 3", postal_code="9000", city="St. Gallen", country="CH",
        vat_number="CHE-999.888.777 MWST",
    )
    db.add(user)
    db.flush()
    return user


def _article(db, name: str, *, steps):
    """Ein Artikel mit **Beleg → Bewegen** – und die Reihenfolge ist die Aussage.

    ►►► **Das Modul danach ist der ganze Punkt.** ◄◄◄ Es hält den Auftrag am Laufen, und
    damit steht jedes Stück nach dem Verkauf **immer noch** auf ``Im Prozess`` – die Lage,
    an der «Verkauft» als *Status* scheitert und wegen der es einen zweiten Zeiger gibt.
    Stünde der Beleg allein, ginge der Auftrag mit ihm zu Ende, und der Statuswechsel auf
    ``Freigegeben`` käme vom **Ende-Objekt**; die Prüfung mässe dann etwas anderes, als
    sie behauptet.

    Die Zoll-Angaben stehen am Artikel und reisen von dort auf den Beleg – seit #964 sind
    sie Pflicht, bevor er hinausgeht.
    """
    from app.models import Article
    from app.services import article_process as tpl, objects as obj
    art = Article(object_id=obj.next_object_id(db), name=name, unit="stk",
                  serialization="batch", hs_code="848210", origin_country="CH")
    db.add(art)
    db.flush()
    # **Bewegen als Nachfolger**, nicht Datenerfassung: es verlangt keine Werte, und
    # fachlich ist es genau der Fall, um den es geht – erst wechselt das Eigentum, dann
    # geht die Ware hinaus (bei umgekehrter Reihenfolge wäre es der Eigentumsvorbehalt).
    tpl.create_steps(db, art, [*steps, {"module_type": "bewegen",
                                        "config": {"target": None}}])
    db.flush()
    return art


def _money_step(*, direction: str, parties, transfer: bool) -> dict:
    """Ein Beleg-Modul – mit der **einen** neuen Angabe: wechselt hier das Eigentum?"""
    return {"module_type": "beleg",
            "config": {"direction": direction,
                       "transfer": transfer,
                       "instruction": "",
                       "parties": [{"party": p.object_id,
                                    "ref": "" if direction == "in" else "Art. 4711"}
                                   for p in parties]}}


def _scene(db, *, direction: str = "in", transfer: bool = True, quantity: int = 3):
    """Ein Auftrag mit **einem** Modul – dem Beleg, bepreist und zugesagt.

    Bis zur Zusage kommt man nicht daran vorbei: ``assert_completable`` weist ein Modul in
    der Stufe «Angebot» ab, und ein Eigentumsübergang ohne Gegenpartei wäre eine Buchung
    ins Leere. Die Szene fährt darum den echten Weg.
    """
    from app.services import process as proc, voucher as svc
    from app.models import ProcessStep

    who = _party(db, "Muster AG")
    art = _article(db, f"Welle {uuid.uuid4().hex[:6]}",
                   steps=[_money_step(direction=direction, parties=[who],
                                      transfer=transfer)])
    order = proc.release(
        db,
        lines=[{"article_object_id": art.object_id, "quantity": quantity,
                "origin": "neu", "units": []}],
        steps=[], actor_id=None,
    )
    db.flush()
    steps = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
             .order_by(ProcessStep.position).all())
    step = next(s for s in steps if s.module_type == "beleg")
    row = svc.of_step(db, step.id)
    assert row is not None, "Die Freigabe hat keinen Beleg angelegt."

    svc.apply(db, order=order, step=step, action="incoterm",
              payload={"incoterm": "FCA", "incoterm_place": "Rorschach"})
    svc.apply(db, order=order, step=step, action="terms",
              payload={"lead_days": 0, "payment_days": 30})
    lines = svc.sync_lines(db, row, order)
    svc.apply(db, order=order, step=step, action="price",
              payload={"lines": [{"id": ln.id, "price": "100.00", "vat": "normal"}
                                 for ln in lines]})
    svc.apply(db, order=order, step=step, action="ask",
              payload={"parties": [who.object_id]})
    if direction == "out":
        svc.apply(db, order=order, step=step, action="quote",
                  payload={"party": who.object_id, "amount": "300.00",
                           "lead_days": 0, "payment_days": 30})
    svc.apply(db, order=order, step=step, action="agree",
              payload={"party": who.object_id})
    db.flush()
    return order, steps, step, row, who, art


def _confirm(db, order, step):
    """Bestätigen – je wartender Instanz einmal, wie die Scan-Regel es verlangt."""
    from app.services import process as proc
    for work in proc.step_work(db, order, step):
        proc.confirm_step(
            db, order=order, step_id=step.id, actor_id=None, values={},
            instance_object_id=work["instance_object_id"], verification="scan",
        )
    db.flush()


def _units(db, order):
    """Die Einzelinstanzen dieses Auftrags – frisch aus der Datenbank."""
    from app.models import InstanceUnit, OrderUnit
    return (db.query(InstanceUnit)
            .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
            .filter(OrderUnit.order_id == order.id)
            .all())


# ═══════════════════════════════════════════════════════════════════════════════
# ►► §1 – DER ZEIGER: er ändert NICHTS ausser sich selbst
# ═══════════════════════════════════════════════════════════════════════════════

def test_a_sale_moves_the_owner_and_nothing_else():
    """►►► **Der Besitz wechselt – Status, Ort und Zugehörigkeit nicht.** ◄◄◄

    Das ist die Garantie, wegen der keine andere Regel im System von diesem Zeiger wissen
    muss – dieselbe, mit der der Ort gebaut wurde. Insbesondere steht das Stück danach
    **immer noch** auf ``Im Prozess``, wenn der Auftrag weiterläuft: genau daran scheitert
    «Verkauft» als Status.

    Bug-Formen: (a) der Übergang setzt zusätzlich einen Status; (b) er räumt den Ort;
    (c) er passiert gar nicht.
    """
    from app.domain import statuses as st
    from app.services import owners, places
    db = _db()
    try:
        order, _steps, step, _row, who, _art = _scene(db)
        before = _units(db, order)
        assert all(owners.owner_of(u) is None for u in before), (
            "Frisch erzeugte Stücke gehören uns – ``NULL`` ist der Normalfall.")

        # ►►► **Erst einen ORT geben, sonst misst die Prüfung nichts.** ◄◄◄ Ein frisch
        # erzeugtes Stück liegt nirgends; «der Übergang hat den Ort nicht angefasst» wäre
        # dann wahr, ohne dass es etwas heisst – gemessen: die Bug-Form (der Übergang
        # räumt den Ort) blieb genau daran stumm.
        from app.services import sites
        places.place(db, units=before, target=sites.find_operator(db).object_id)
        db.flush()

        was = {u.id: (u.status, places.place_of(u)) for u in before}
        assert all(p for _s, p in was.values()), "Die Szene hat keinen Ort gesetzt."

        _confirm(db, order, step)
        after = _units(db, order)

        assert after, "Die Szene hat keine Stücke."
        for unit in after:
            assert owners.owner_of(unit) == who.object_id, (
                f"(c) Einzelinstanz #{unit.id} gehört nach dem Verkauf immer noch uns – "
                f"der Übergang hat nicht stattgefunden.")
            assert unit.status == was[unit.id][0] == st.IM_PROZESS, (
                f"(a) Der Status ist «{unit.status}» statt «{was[unit.id][0]}». Besitz "
                f"ist kein Zustand – der Prozess besitzt diese Spalte, und hier läuft "
                f"der Auftrag weiter.")
            assert unit.status != st.VERKAUFT, (
                "(a) Der Übergang hat «Verkauft» geschrieben. Den Status schreibt heute "
                "kein Modul mehr – der Besitz sagt es genauer, und zwar ohne mit dem "
                "Prozess um dieselbe Spalte zu streiten.")
            assert places.place_of(unit) == was[unit.id][1], (
                "(b) Der Eigentumsübergang hat den Ort angefasst. Verkauft heisst nicht "
                "«beim Kunden» – das sind zwei Aussagen.")
    finally:
        db.rollback()
        db.close()


def test_without_the_declaration_nothing_moves():
    """►►► **Die Vorgabe ist AUS – Miete, Lohn und Transport übertragen nichts.** ◄◄◄

    Ein Zahlungsmodul ist der kleinste gemeinsame Nenner von Einkauf, Verkauf, Miete,
    Lohn, Gebühr und Spedition. Nur bei zweien davon wechselt das Eigentum, also ist die
    sichere Vorgabe die, bei der nichts geschieht: ein falsches *Ja* verschenkt
    stillschweigend Eigentum.

    Bug-Form: der Übergang hängt am **Modultyp** statt an der Deklaration – dann wechselt
    auch die Miete den Besitzer.
    """
    from app.services import owners
    db = _db()
    try:
        order, _steps, step, _row, _who, _art = _scene(db, transfer=False)
        _confirm(db, order, step)
        for unit in _units(db, order):
            assert owners.owner_of(unit) is None, (
                "Ein Beleg ohne «Eigentum wechselt» hat den Eigentümer gesetzt – dann "
                "überträgt auch eine Mietzahlung das Eigentum an der Maschine.")
    finally:
        db.rollback()
        db.close()


def test_the_direction_says_where_the_ownership_goes():
    """►►► **An wen, sagt die Richtung – kein zweites Feld.** ◄◄◄

    Wer kassiert, gibt die Ware ab; wer zahlt, bekommt sie. Bei einer **Ausgabe** kommt
    das Eigentum darum zu **uns** – und zwar zu der Gesellschaft, die den Beleg stellt,
    denn genau das ist die Frage «womit kann ich als jeweiliges Unternehmen wirtschaften».

    Bug-Form: die Richtung wird ignoriert und es geht immer an die Gegenpartei – dann
    gehört gekauftes Material dem Lieferanten.
    """
    from app.services import owners, sites
    db = _db()
    try:
        order, _steps, step, _row, who, _art = _scene(db, direction="out")
        _confirm(db, order, step)
        house = sites.find_operator(db)
        for unit in _units(db, order):
            got = owners.owner_of(unit)
            assert got != who.object_id, (
                "Bei einer **Ausgabe** ist das Eigentum an die Gegenpartei gegangen – "
                "wir haben bezahlt, also gehört es uns.")
            assert got == house.object_id, (
                f"Erwartet war unsere Gesellschaft {house.object_id}, gesetzt wurde "
                f"{got}.")
            assert owners.is_ours(db, got), (
                "Was unsere Gesellschaft besitzt, muss «unseres» heissen – sonst fällt "
                "eingekauftes Material aus dem eigenen Bestand.")
    finally:
        db.rollback()
        db.close()


def test_the_transfer_stands_in_the_log():
    """►►► **Dass es passiert ist, steht im LOG – nicht in einer zweiten Tabelle.** ◄◄◄

    Dieselbe Begründung wie beim Ort: die Nutzlast des ``step``-Ereignisses trägt Herkunft
    und Ziel, und damit steht der Vorgang dort, wo die Historie ohnehin steht. Der **Name**
    reist mit, weil er eingefroren gehört: er überlebt eine spätere Umfirmierung.

    Bug-Form: der Zeiger wird gesetzt, aber nichts geschrieben – dann lässt sich später
    nicht sagen, **wann** und **wodurch** das Eigentum gewechselt hat.
    """
    from app.models import ProcessEvent
    from app.models.process_event import KIND_STEP
    db = _db()
    try:
        order, _steps, step, _row, who, _art = _scene(db)
        _confirm(db, order, step)
        rows = (db.query(ProcessEvent)
                .filter(ProcessEvent.order_id == order.id,
                        ProcessEvent.step_id == step.id,
                        ProcessEvent.kind == KIND_STEP)
                .all())
        assert rows, "Kein Schritt-Ereignis am Beleg-Modul."
        for event in rows:
            moved = (event.payload or {}).get("owner")
            assert moved, (
                "Das Schritt-Ereignis nennt keinen Eigentumsübergang – dann steht er "
                "nirgends, und die Historie kennt ihn nicht.")
            assert moved["from"] is None and moved["to"] == who.object_id, (
                f"Herkunft und Ziel stimmen nicht: {moved}.")
            assert moved.get("label"), (
                "Der Name des neuen Eigentümers fehlt im Log – er gehört eingefroren "
                "dorthin, sonst ändert eine Umfirmierung die Vergangenheit.")
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ►► §2 – WER BESITZEN KANN
# ═══════════════════════════════════════════════════════════════════════════════

def test_only_a_legal_person_can_own_something():
    """►►► **Ein Regal hält Schrauben, es besitzt sie nicht.** ◄◄◄

    Besitzen kann eine natürliche oder eine juristische Person – mehr gibt es rechtlich
    nicht. Geprüft wird beim **Schreiben**, mit einem Satz, der sagt, was dort hingehört.

    Bug-Form: die Prüfung lässt jede Objektnummer durch – dann gehört eine Welle einem
    Regal, und keine Ansicht kann das mehr auflösen.
    """
    from fastapi import HTTPException
    from app.models import Instance
    from app.services import owners
    db = _db()
    try:
        _order, _steps, _step, _row, who, art = _scene(db)
        shelf = db.query(Instance).filter(Instance.article_id == art.id).first()
        assert shelf is not None

        with pytest.raises(HTTPException) as bad:
            owners.assert_ownable(db, shelf.object_id)
        assert bad.value.status_code == 400
        assert "besitzen" in bad.value.detail.lower(), (
            f"Der Satz sagt nicht, was dort hingehört: «{bad.value.detail}»")

        with pytest.raises(HTTPException):
            owners.assert_ownable(db, 999999999)

        # Und die beiden gültigen Fälle gehen durch – sonst prüfte der Wächter nur, dass
        # gar nichts erlaubt ist.
        assert owners.assert_ownable(db, who.object_id)
        assert owners.assert_ownable(db, None) is None
    finally:
        db.rollback()
        db.close()


def test_ours_means_us_or_one_of_our_companies():
    """►►► **«Gehört uns» ist nicht dasselbe wie ``NULL``.** ◄◄◄

    Kaufen zwei unserer Gesellschaften Material, gehört jedes Stück *einer* von beiden –
    und beides ist unseres. Eine zweite Spalte «ist das unseres» wäre die zweite Wahrheit.

    Bug-Form: ``is_ours`` prüft nur auf ``None`` – dann fällt alles, was eine Gesellschaft
    gekauft hat, aus dem eigenen Bestand.
    """
    from app.services import owners, sites
    db = _db()
    try:
        house = sites.find_operator(db)
        outsider = _party(db, "Fremd AG")
        assert owners.is_ours(db, None), "``NULL`` heisst uns."
        assert owners.is_ours(db, house.object_id), (
            "Was unsere eigene Gesellschaft besitzt, ist unseres – sonst zählt jeder "
            "Einkauf aus dem Bestand heraus.")
        assert not owners.is_ours(db, outsider.object_id), (
            "Fremdes wird als unseres gezählt – dann kann man Beistellung verkaufen.")
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ►► §3 – DER BESTAND: zwei Aufteilungen DERSELBEN Menge
# ═══════════════════════════════════════════════════════════════════════════════

def test_both_bars_describe_the_same_pieces():
    """►►► **Zustand und Eigentum summieren sich auf dieselbe Zahl.** ◄◄◄

    *«Ich muss den globalen Überblick behalten und zugleich wissen, mit was ich
    wirtschaften kann.»* – Zwei Fragen über **dieselben** Stücke. Summierten sie sich
    verschieden, wären es zwei Auskünfte über zwei Dinge, und niemand könnte sie
    nebeneinander lesen.

    Bug-Form: die Eigentums-Aufstellung zählt nur den lebenden Bestand (oder nur eine
    Seite) – dann fehlen der zweiten Leiste die verkauften Stücke, und sie ist kürzer.
    """
    from app.services import instances as inst, owners
    db = _db()
    try:
        order, _steps, step, _row, _who, art = _scene(db, quantity=4)
        _confirm(db, order, step)

        by_status = inst.article_states(db, article_id=art.id)
        by_owner = owners.counts_for_article(db, article_id=art.id)
        assert sum(by_status.values()) == sum(by_owner.values()) == 4, (
            f"Zustand {by_status} und Eigentum {by_owner} beschreiben nicht dieselbe "
            f"Menge – zwei Leisten übereinander wären dann zwei Behauptungen.")
    finally:
        db.rollback()
        db.close()


def test_one_owner_is_no_statement():
    """►►► **Eine Leiste mit einem Segment sagt nichts.** ◄◄◄

    Gehört alles uns, kommt die Aufstellung **leer** zurück: «Uns 20» über einer Leiste,
    die ohnehin die Gesamtmenge zeigt, kostet eine Zeile und sagt nichts. Dieselbe Regel
    wie bei den Zuständen – was es nicht zu unterscheiden gibt, steht nicht da.

    Bug-Form: sie liefert immer ein Segment – dann steht unter jedem Artikel des Hauses
    eine zweite Leiste ohne Aussage.
    """
    from app.services import owners
    db = _db()
    try:
        order, _steps, step, _row, who, art = _scene(db, quantity=2)
        assert owners.shares(db, owners.counts_for_article(db, article_id=art.id)) == [], (
            "Gehört alles uns, ist die Eigentums-Leiste eine Zeile ohne Aussage.")

        # Nur die **Hälfte** verkaufen, damit sich wirklich etwas unterscheidet: dafür
        # bekommt ein Stück seinen Eigentümer direkt über die eine Schreibstelle.
        units = _units(db, order)
        owners.transfer(db, units=units[:1], to=who.object_id)
        db.flush()
        rows = owners.shares(db, owners.counts_for_article(db, article_id=art.id))
        assert len(rows) == 2, f"Erwartet zwei Segmente, bekommen: {rows}"
        assert rows[0]["ours"] and rows[0]["name"] == owners.US, (
            "Unsere Seite steht nicht zuerst – sie ist der Bezugspunkt, vor dem man die "
            "fremde liest.")
        assert rows[1]["owner_object_id"] == who.object_id and not rows[1]["ours"]
        assert rows[1]["name"] != str(who.object_id), (
            "Der fremde Eigentümer steht als nackte Nummer da – der Name kommt aus "
            "derselben Auflösung wie beim Halter.")
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ►► §4 – DIE FORM: eine Schreibstelle, kein eigenes Modul
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
    return "\n".join(line.split("#")[0] for line in src.splitlines())


def test_the_owner_is_written_in_exactly_one_place():
    """►►► **Eine Sache, eine Stelle** – wie beim Ort (``places``). ◄◄◄

    Wer den Zeiger anderswo setzt, umgeht ``assert_ownable`` und schreibt keinen Log.

    Bug-Form: ein zweiter Schreiber taucht auf – z. B. ein Router, der das Feld direkt
    zuweist.
    """
    import re
    root = BACKEND / "app"
    allowed = {root / "services" / "owners.py"}
    for path in sorted(root.rglob("*.py")):
        if path in allowed:
            continue
        code = _code(path)
        assert not re.search(r"\.owner_object_id\s*=(?!=)", code), (
            f"{path.relative_to(BACKEND)} schreibt ``owner_object_id`` direkt. Die eine "
            f"Schreibstelle ist ``services/owners`` – daran hängen die Prüfung und der "
            f"Log.")


def test_there_is_no_ownership_module():
    """►►► **Der Eigentumsübergang ist die FOLGE eines Geschäfts, kein Modul.** ◄◄◄

    Genau daran ist «Ausliefern» gestorben (§9.13): ein Modul, dessen ganze Aussage eine
    Folge ist, beschreibt nichts, was nicht schon dasteht. Die Deklaration steht am
    **Beleg**.

    Bug-Form: jemand legt einen sechsten Modultyp an, der nur den Besitz setzt.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules

    assert set(modules.KEYS) == {"datenerfassung", "aussondern", "verbrauch",
                                 "bewegen", "beleg"}, (
        f"Die Modul-Liste hat sich geändert: {modules.KEYS}. Ein eigenes Modul für den "
        f"Eigentumsübergang gibt es nicht – er gehört zum Beleg.")
    # **Und jedes andere Modul überträgt nichts** – die Vorgabe steht in der Basisklasse,
    # nicht als Aufzählung an der Ausführungsstelle.
    for key, module in modules.MODULES.items():
        if key == modules.BELEG:
            continue
        assert not module.transfers_ownership({"transfer": True}), (
            f"«{key}» überträgt Eigentum, obwohl es kein Geldvorgang ist – dann genügt "
            f"ein durchgereichter Schlüssel, um Besitz zu verschieben.")


def test_the_write_place_knows_no_payment_module():
    """►►► **``owners`` schreibt einen Zeiger und kennt keinen Beleg.** ◄◄◄

    Dieselbe Regel, die den Beleg von seinem Vorgänger unabhängig gehalten hat: wer ihn
    eines Tages löscht, fasst hier keine Zeile an.

    Bug-Form: ``owners`` importiert ``voucher``, um die Gegenpartei selbst zu suchen.
    """
    code = _code(BACKEND / "app" / "services" / "owners.py")
    for foreign in ("voucher", "deal", "purchase"):
        assert f"import {foreign}" not in code, (
            f"``services/owners`` importiert ``{foreign}`` – die Schreibstelle soll einen "
            f"Zeiger setzen, nicht ein Geschäft verstehen.")


def test_history_keeps_its_owner():
    """►►► **Wer zur Historie zählt, verliert seinen ORT – nicht seinen BESITZ.** ◄◄◄

    Ein verbautes Stück steckt in einem anderen (der Ort wird neu gesetzt), ein
    verschrottetes ist weg. **Wem** es gehörte, bleibt trotzdem wahr – sonst verlöre eine
    Beistellung ihren Eigentümer genau in dem Moment, in dem sie in unser Produkt wandert.

    Bug-Form: ``_pass`` räumt neben dem Ort auch den Eigentümer.
    """
    code = _code(BACKEND / "app" / "services" / "process.py")
    assert "places_svc.forget" in code, "Der Ort wird nicht mehr geräumt?"
    assert "owners_svc.forget" not in code and "owner_object_id = None" not in code, (
        "Der Eigentümer wird beim Übergang in die Historie geräumt. Der Ort ist eine "
        "Aussage über ein Regal, der Besitz eine über eine Rechtsperson.")
