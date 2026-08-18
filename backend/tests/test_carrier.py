"""**Der Kanal «Plattform»** — die Regeln K1–K7 aus `SYSTEM_LOGIC` §7.3a, als Wächter.

Ein Adapter ist die Naht zu einem Dritten. Genau darum wird hier **nicht** über das Netz
geprüft: ein Test, der eine fremde API braucht, prüft deren Verfügbarkeit und nicht die
eigene Regel. Geprüft wird, was uns gehört — dass der Adapter keinen Zustand setzt, dass
das Paket abgeleitet ist, dass es ohne Schlüssel den Kanal nicht gibt, und dass Tracking
den Ort über dieselbe eine Stelle schreibt wie ein Scan.

Wo eine Aussage über **Code** geht («ein Adapter kennt keinen Auftrag»), steht ein
AST-Wächter: mit einem Verhaltenstest ist sie nicht widerlegbar.

Jeder Wächter nennt seine **Bug-Form**.
"""

import ast
from decimal import Decimal

import pytest

from .support import (
    StubCarrier as _Stub, carrier_offer as _offer, live_sources, make_company,
    make_units, session, source, with_carriers as _with,
)

ZUERICH = dict(street="Industriestrasse", street_nr="4", zip_code="8000", city="Zürich",
               country="CH")
BERN = dict(street="Bahnhofplatz", street_nr="1", zip_code="3000", city="Bern",
            country="CH")


def _pair(db):
    return (make_company(db, "Werk Nord", **ZUERICH).object_id,
            make_company(db, "Werk Süd", **BERN).object_id)


def _addr(country="CH"):
    from app.services.carriers import Address
    return Address(name="X", street="Weg 1", zip="8000", city="Zürich", country=country)


def _parcel():
    from app.services.carriers import Parcel
    return Parcel(weight_kg=Decimal("2"), length_cm=Decimal("10"),
                  width_cm=Decimal("10"), height_cm=Decimal("10"))


# ═══════════════════════════════════════════════════════════════════════════════
# K1 — Ein Adapter setzt nie einen Zustand
# ═══════════════════════════════════════════════════════════════════════════════

def test_a_carrier_offer_goes_through_the_same_one_place():
    """**Was ein Adapter liefert, wird wie ein getipptes Angebot geschrieben.**

    Bug-Form: der Adapter (oder der Tarifabruf) setzt selbst `angeboten`. Dann gäbe es
    zwei Stellen, an denen der Zyklus voranschreitet – und die zweite kennt die Matrix
    nicht. Geprüft wird die Wirkung: nach dem Abruf steht die Vergabe auf «Angeboten»,
    **weil** ``add_offer`` gelaufen ist, nicht weil jemand den Zustand gesetzt hat.
    """
    from app.domain import vergabe
    from app.services import awards

    db = session()
    try:
        src, dst = _pair(db)
        with _with([_Stub(offers=[_offer(40), _offer(90, service="Priority", ref="r2")])]):
            award = awards.request(db, subject_object_id=src, target_object_id=dst,
                                   channel=vergabe.PLATTFORM, actor_id=None)
            messages = awards.quote(db, award, sender=_addr(), receiver=_addr("DE"),
                                    parcel=_parcel(), unit_ids=[])
        assert messages == []
        assert award.state == vergabe.ANGEBOTEN
        rows = awards.offers(db, award)
        assert [float(o.amount) for o in rows] == [40, 90], "Günstigstes zuerst."
        assert all(o.provider_object_id is None and o.provider_name for o in rows), (
            "Ein Frachtführer ist kein ERP-Datensatz – er wird benannt, nicht erfunden.")
        assert all(o.carrier == "stub" and o.external_ref for o in rows), (
            "Ohne Adapter und Tarif-Referenz liesse sich das Angebot nicht kaufen.")
    finally:
        db.rollback()
        db.close()


def test_the_adapter_never_writes_a_state():
    """**Kein Adapter kennt die Vergabe** – Aussage über Code, darum als AST-Wächter.

    Bug-Form: ein Adapter importiert ``awards`` oder ``vergabe`` und schreibt selbst.
    Ein Verhaltenstest fände das nicht: der zweite Weg funktioniert ja.
    """
    for rel, src in live_sources():
        if not rel.startswith("services/carriers/"):
            continue
        tree = ast.parse(src)
        # **Modul UND Name.** ``from ...domain import vergabe`` nennt als Modul nur
        # «domain» – die Registry steht im importierten *Namen*. Ein Wächter, der nur das
        # Modul liest, liesse genau diesen Import durch (gegen die Bug-Form geprüft).
        names: set[str] = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                names.add(n.module or "")
                names |= {a.name for a in n.names}
            elif isinstance(n, ast.Import):
                names |= {a.name for a in n.names}
        for forbidden in ("awards", "vergabe", "process", "moving", "places", "models"):
            assert not any(forbidden in n.split(".") for n in names), (
                f"{rel} kennt «{forbidden}» – ein Adapter beantwortet drei Fragen und "
                f"kennt weder Vergabe noch Auftrag noch Ort (K2).")


# ═══════════════════════════════════════════════════════════════════════════════
# K3 — Das Paket ist abgeleitet, nie eingegeben
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_parcel_is_derived_and_never_guessed():
    """**Fehlt ein Gewicht, wird nicht geraten** – die Antwort nennt den Artikel.

    Bug-Form: ein Standard-Karton. Er ergäbe einen Preis, der beim Wiegen nicht stimmt,
    und der Fehler fiele erst auf der Rechnung des Frachtführers auf.
    """
    from app.models import Article, Instance
    from app.services import parcel

    db = session()
    try:
        _, instances, units = make_units(db, quantity=2)
        art = db.query(Article).filter(Article.id == instances[0].article_id).first()

        art.weight_kg = None
        db.flush()
        box, problems = parcel.of_units(db, [u.id for u in units])
        assert box is None and problems, "Ohne Gewicht darf kein Paket entstehen."
        assert str(art.object_id) in problems[0].message and "Gewicht" in problems[0].message

        art.weight_kg = Decimal("1.250")
        art.size = "40x3x600"
        db.flush()
        box, problems = parcel.of_units(db, [u.id for u in units])
        assert not problems
        assert box.weight_kg == Decimal("2.500"), "Zwei Stück wiegen zweimal."
        # »40x3x600« mm → aufsteigend 0.3 · 4.0 · 60.0 cm; gestapelt wächst die Höhe.
        assert (box.length_cm, box.width_cm) == (Decimal("0.3"), Decimal("4.0"))
        assert box.height_cm == Decimal("120.0"), "Zwei Stück stapeln sich."
    finally:
        db.rollback()
        db.close()


def test_the_size_means_one_thing():
    """»3x40x600« hat **eine** Bedeutung – und die gehört dem Artikel.

    Bug-Form: eine zweite Stelle, die dieselbe Zeichenkette anders versteht (mm ↔ cm,
    Reihenfolge). Dann hinge der Preis davon ab, wer gerade rechnet.

    Geprüft wird die **Aussage**, nicht die Mechanik: dass irgendwo ein ``split("x")``
    steht, ist kein Fehler – ``normalize_size`` prüft ja eine Eingabe und muss sagen, was
    daran falsch ist. Verboten ist eine zweite **Auslegung**; also darf ausser dem
    Artikel niemand aus der Zeichenkette Zahlen machen.
    """
    from app.schemas.article import parse_size
    from app.services.parcel import _cm

    assert parse_size("3x40x600") == (Decimal("3"), Decimal("40"), Decimal("600")), (
        "Der Artikel führt die Grösse in Millimetern – umgerechnet wird woanders.")
    assert parse_size("600X40X3") == (Decimal("3"), Decimal("40"), Decimal("600"))
    for bad in (None, "", "3x40", "a x b x c", "0x1x2", "3x40x600x7"):
        assert parse_size(bad) is None, f"«{bad}» ist kein Mass und darf keines ergeben."
    assert _cm("3x40x600") == (Decimal("0.3"), Decimal("4.0"), Decimal("60.0")), (
        "Die Umrechnung mm → cm ist das Einzige, was der Paket-Dienst tut.")

    readers = [rel for rel, src in live_sources()
               if rel not in ("schemas/article.py", "services/parcel.py")
               and ("parse_size" in src or ".size)" in src and "split" in src)]
    assert not readers, f"Die Grösse wird an weiteren Stellen ausgelegt: {readers}"


# ═══════════════════════════════════════════════════════════════════════════════
# K4 — Ohne Schlüssel gibt es den Kanal nicht
# ═══════════════════════════════════════════════════════════════════════════════

def test_without_a_key_the_channel_does_not_exist():
    """**Nicht wählbar** statt «erscheint und scheitert» – und **kein Rückfall**.

    Bug-Form: der Vorgänger fiel auf «manual» zurück («nie kaputt») – und genau darum
    merkte niemand, dass nie ein Tarif kam.
    """
    from app.domain import vergabe
    from app.services import awards, carriers

    db = session()
    try:
        src, dst = _pair(db)
        with _with([]):
            assert not carriers.available()
            state = awards.channel_availability()
            assert state[vergabe.PLATTFORM] is not None, "Der Kanal muss den Grund nennen."
            assert state[vergabe.PORTAL] is None and state[vergabe.SELBST] is None
            with pytest.raises(Exception) as err:
                awards.request(db, subject_object_id=src, target_object_id=dst,
                               channel=vergabe.PLATTFORM, actor_id=None)
            assert getattr(err.value, "status_code", None) == 409

        # Und mit Schlüssel geht es – dieselbe Regel, andere Antwort.
        with _with([_Stub()]):
            assert awards.channel_availability()[vergabe.PLATTFORM] is None
            award = awards.request(db, subject_object_id=src, target_object_id=dst,
                                   channel=vergabe.PLATTFORM, actor_id=None)
            assert award.channel == vergabe.PLATTFORM
    finally:
        db.rollback()
        db.close()


def test_there_is_no_fallback_between_carriers():
    """Ein Etikett wird beim **gewählten** Frachtführer gekauft, nie beim nächstbesten.

    Bug-Form: eine Auto-Reihenfolge («Sendcloud ≻ Shippo ≻ manual»). Welcher Dritte
    fährt, ist eine Entscheidung – eine stille Ersatzwahl ist keine.
    """
    from app.services import carriers

    assert not hasattr(carriers, "provider_name"), (
        "Es gibt wieder einen «aktiven Anbieter» – gefragt werden alle eingerichteten.")
    with pytest.raises(Exception) as err:
        carriers.by_key("gibtsnicht")
    assert getattr(err.value, "status_code", None) == 400

    body = source("services/carriers/__init__.py")
    for word in ("manual", "fallback", "Rückfall auf"):
        assert f"= {word}" not in body and f'"{word}"' not in body, (
            f"«{word}» steht wieder als Ausweg im Code.")


# ═══════════════════════════════════════════════════════════════════════════════
# K5/K6 — Die Vergabe hält ihre Stücke; Tracking schreibt den Ort
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_award_holds_its_pieces_from_the_quote_on():
    """Wer Tarife holt, beschreibt ein **Paket** – und ein Paket hat einen Inhalt.

    Bug-Form: die Stücke werden erst beim Zustellen genannt. Dann wüsste das Tracking
    nicht, was angekommen ist – und es steht ja niemand am Ziel.
    """
    from app.domain import vergabe
    from app.services import awards

    db = session()
    try:
        src, dst = _pair(db)
        _, _, units = make_units(db, quantity=2)
        ids = [u.id for u in units]
        with _with([_Stub(offers=[_offer(40)])]):
            award = awards.request(db, subject_object_id=src, target_object_id=dst,
                                   channel=vergabe.PLATTFORM, actor_id=None)
            awards.quote(db, award, sender=_addr(), receiver=_addr("DE"),
                         parcel=_parcel(), unit_ids=ids)
        assert award.unit_ids == ids
        assert award.shipment_ref == "ship-1", (
            "Was der Kauf braucht, füllt der Adapter – der Aufrufer reicht es durch.")
    finally:
        db.rollback()
        db.close()


def test_tracking_writes_the_place_through_the_one_place():
    """**Tracking ist eine Beobachtung wie ein Scan** – dieselbe Tabelle, `source` anders.

    Bug-Form: ein eigener Schreibweg für Tracking. Dann gäbe es zwei Stellen, an denen
    ein Ort entsteht, und die zweite vergisst irgendwann, was die erste tut.
    """
    from app.domain import vergabe
    from app.models import UnitPlace
    from app.services import awards, places

    db = session()
    try:
        src, dst = _pair(db)
        _, _, units = make_units(db, quantity=2)
        ids = [u.id for u in units]
        unterwegs, geliefert = _Stub(offers=[_offer(40)]), _Stub(offers=[_offer(40)],
                                                                 delivered=True)
        with _with([unterwegs]):
            award = awards.request(db, subject_object_id=src, target_object_id=dst,
                                   channel=vergabe.PLATTFORM, actor_id=None)
            awards.quote(db, award, sender=_addr(), receiver=_addr("DE"),
                         parcel=_parcel(), unit_ids=ids)
            offer = awards.cheapest(db, award)
            awards.grant(db, award, offer_id=offer.id, actor_id=None)
            assert award.tracking_number == "TRK-1" and award.label_url, (
                "Vergeben heisst beim Plattform-Kanal: Etikett kaufen.")
            state, _detail = awards.track(db, award, actor_id=None)
            assert state == "unterwegs"
            assert places.current(db, ids) == {}, "Unterwegs liegt noch nichts am Ziel."

        with _with([geliefert]):
            state, _detail = awards.track(db, award, actor_id=None)
        assert state == "zugestellt"
        assert award.state == vergabe.ERBRACHT
        assert places.current(db, ids) == {i: dst for i in ids}
        rows = db.query(UnitPlace).filter(UnitPlace.instance_unit_id == ids[0]).all()
        assert rows[-1].source == "tracking", (
            "Eine Ablage aus dem Tracking muss sich von einem Scan unterscheiden lassen.")
    finally:
        db.rollback()
        db.close()


def test_a_failed_transport_is_not_automatically_a_failed_award():
    """**Ab «Vergeben» rührt das System nichts an – es meldet.**

    Bug-Form: eine gescheiterte Sendung setzt die Vergabe automatisch auf «Gescheitert».
    Das ist die Feststellung eines Menschen, mit Pflicht-Grund (V6) – und ohne ihn stünde
    später da, dass es nicht geklappt hat, aber nicht warum.
    """
    from app.domain import vergabe
    from app.services import awards
    from app.services.carriers import UNZUSTELLBAR, Tracking

    class _Kaputt(_Stub):
        def track(self, tracking_number, *, carrier=""):
            return Tracking(UNZUSTELLBAR, "Sendung verloren")

    db = session()
    try:
        src, dst = _pair(db)
        with _with([_Kaputt(offers=[_offer(40)])]):
            award = awards.request(db, subject_object_id=src, target_object_id=dst,
                                   channel=vergabe.PLATTFORM, actor_id=None)
            awards.quote(db, award, sender=_addr(), receiver=_addr("DE"),
                         parcel=_parcel(), unit_ids=[])
            awards.grant(db, award, offer_id=awards.cheapest(db, award).id, actor_id=None)
            state, detail = awards.track(db, award, actor_id=None)
        assert state == "unzustellbar" and detail
        assert award.state == vergabe.VERGEBEN, (
            "Das System hat die Vergabe beendet – das darf nur ein Mensch, mit Grund.")
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# K7 — Tarife werden nie von selbst geholt
# ═══════════════════════════════════════════════════════════════════════════════

def test_rates_are_never_fetched_by_the_system():
    """**Der Mensch klickt** – auch hier (§15.7).

    Bug-Form: ein Abruf beim Öffnen des Moduls. Das wäre ein Vorgang bei einem Dritten,
    den niemand bestellt hat – und bei manchen Anbietern kostet er.
    """
    for rel in ("services/moving.py", "services/process.py", "services/places.py"):
        tree = ast.parse(source(rel))
        calls = {
            f"{n.func.value.id}.{n.func.attr}"
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
        }
        assert "awards.quote" not in calls and "carriers.active" not in calls, (
            f"{rel} holt Tarife von sich aus – das ist ein Vorgang bei einem Dritten.")

    # Und die Ableitung der Fuhre fragt keinen Frachtführer.
    assert "carriers" not in source("services/moving.py"), (
        "Die Fuhren-Vorschau kennt Frachtführer – dann kostet ein Blick ins Modul Geld.")


def test_the_old_shipping_gateway_is_gone():
    """**Der Vorgänger ist ersatzlos weg** – nicht «liegt noch daneben».

    Bug-Form: der alte Ordner bleibt liegen und jemand hält ihn für die Wahrheit. Der
    Vorgänger fiel stillschweigend auf «manual» zurück und speicherte eine
    Transportklasse – zwei der sechs verbotenen Formen aus ADR 009.
    """
    import pathlib
    from .support import APP

    assert not (APP / "services" / "shipping").exists(), (
        "Der alte Versand-Ordner liegt wieder da.")
    for rel, src in live_sources():
        assert "services.shipping" not in src and "from .shipping" not in src, (
            f"{rel} verweist auf den alten Versand-Ordner.")
    assert isinstance(pathlib.Path(APP), pathlib.Path)   # nur zur Lesbarkeit
