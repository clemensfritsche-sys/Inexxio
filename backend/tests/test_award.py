"""**Die Vergabe** — die Regeln aus `SYSTEM_LOGIC` §7.3, als Wächter.

Eine Vergabe ist der Vorgang «ein Dritter erbringt eine Leistung für uns»: heute ein
Transport, morgen eine Beschaffung. Der Zyklus steht **einmal** (`domain/vergabe`), und
der **Kanal** ist die einzige Variable — er ändert, *woher* die Angebote kommen, nie,
*welche* Zustände es gibt.

Diese Datei prüft beides, weil beides scheitern kann:

* **Verhalten** über die echten Dienstpfade gegen echtes PostgreSQL. Ein nachgestellter
  Zustand fände genau das nicht, worauf es hier ankommt — dass eine Ablage erst mit der
  **Erbringung** entsteht und nicht mit der Absicht.
* **Quelltext**, wo die Aussage über Code geht. «Es gibt genau eine Schreibstelle für
  einen Zustandswechsel» ist mit einem Verhaltenstest nicht widerlegbar: ein zweiter
  Schreibweg funktioniert ja.

Jeder Wächter nennt seine **Bug-Form** — was falsch wäre, wenn er ausbliebe. Ein Wächter,
der nie anschlägt, ist von einem kaputten nicht zu unterscheiden.
"""

import ast

import pytest

from .support import (
    StubCarrier, carrier_offer, live_sources, make_company, make_units, session,
    source, with_carriers,
)

# Die Hilfen stehen in ``tests/support`` – eine Stelle, mehrere Wächter.

ZUERICH = dict(street="Industriestrasse", street_nr="4", zip_code="8000", city="Zürich",
               country="CH")
BERN = dict(street="Bahnhofplatz", street_nr="1", zip_code="3000", city="Bern",
            country="CH")


def _pair(db):
    """Zwei Halter an **verschiedenen** Anschriften – also ein Versand (§15.4)."""
    return (make_company(db, "Werk Nord", **ZUERICH).object_id,
            make_company(db, "Werk Süd", **BERN).object_id)


def _carrier(db, name: str = "Spediteur AG") -> int:
    """Ein Dritter, den es wirklich gibt – ``_assert_exists`` schreibt streng."""
    return make_company(db, name, **ZUERICH).object_id


# ═══════════════════════════════════════════════════════════════════════════════
# V1 — Eine Anfrage entsteht durch einen Klick, und zwar genau einmal
# ═══════════════════════════════════════════════════════════════════════════════

def test_a_request_is_idempotent_per_occasion():
    """**Zweimal anfragen ergibt EINE Vergabe, nicht zwei.**

    Bug-Form: jede Betrachtung des Moduls legte eine Zeile an. Ein Modul wird oft
    angesehen, bevor jemand handelt – am Ende stünden fünf Anfragen für eine Fuhre, und
    keine sagte, welche gilt.
    """
    from app.domain import vergabe
    from app.models import Award
    from app.services import awards

    db = session()
    try:
        src, dst = _pair(db)
        first = awards.request(db, subject_object_id=src, target_object_id=dst,
                               channel=vergabe.PORTAL, actor_id=None)
        second = awards.request(db, subject_object_id=src, target_object_id=dst,
                                channel=vergabe.PORTAL, actor_id=None)
        assert first.id == second.id, "Eine zweite Anfrage für dieselbe Fuhre ist keine zweite Vergabe."
        rows = db.query(Award).filter(Award.subject_object_id == src,
                                      Award.target_object_id == dst).all()
        assert len(rows) == 1, f"Erwartet EINE Zeile, gefunden {len(rows)}."
    finally:
        db.rollback()
        db.close()


def test_the_system_never_requests_by_itself():
    """**Das Modul «Bewegen» fragt nie von sich aus an** (§15.7, verbotene Form V-3).

    Bug-Form: das Erreichen des Moduls legte die Vergabe an. Genau daran sind die
    abgeleitete Bereitstellung und die Begleit-Bewegungen des Vorgängers gescheitert –
    das System hat Vorgänge erzeugt, die niemand bestellt hat, und niemand traute sich,
    sie zu löschen.

    Zwei Formen derselben Aussage: der **Quelltext** ruft es nicht, und ein Lauf über die
    echte Ausführungsstelle hinterlässt **keine** Zeile.
    """
    from app.domain import modules
    from app.models import Award
    from app.services import moving

    tree = ast.parse(source("services/moving.py"))
    calls = {
        f"{n.func.value.id}.{n.func.attr}"
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
    }
    assert "awards.request" not in calls, (
        "«Bewegen» darf keine Vergabe anlegen – es bietet sie an, ein Mensch klickt.")

    db = session()
    try:
        src, dst = _pair(db)
        order, _, units = make_units(db, quantity=1)
        step = _external_step(db, order, dst)
        before = db.query(Award).count()
        with pytest.raises(Exception) as err:
            moving.record_for_step(db, step=step, units=units,
                                   from_holder_object_id=src, actor_id=None)
        assert getattr(err.value, "status_code", None) == 409
        assert db.query(Award).count() == before, (
            "Ein abgewiesener Vollzug hat eine Vergabe angelegt – das System bietet an, "
            "es bestellt nicht.")
        assert modules.BEWEGEN in step.module_type
    finally:
        db.rollback()
        db.close()


def _external_step(db, order, target_object_id: int):
    from .support import make_move_step
    return make_move_step(db, order, target_object_id)


# ═══════════════════════════════════════════════════════════════════════════════
# V2 — Der Kanal ändert die Herkunft der Angebote, nie den Zyklus
# ═══════════════════════════════════════════════════════════════════════════════

def test_every_channel_runs_the_same_cycle():
    """**Plattform und Portal durchlaufen dieselben Zustände.**

    Bug-Form: ein `if channel == 'plattform'` mit eigenem Ablauf. Rate-Shopping IST eine
    Ausschreibung – sie dauert 2 Sekunden statt 2 Tage, und genau das ist der Unterschied.
    Ein zweiter Zyklus daneben wäre eine zweite Stelle, an der die Matrix gepflegt wird.
    """
    from app.domain import vergabe
    from app.services import awards

    db = session()
    try:
        seen = {}
        # Der Plattform-Kanal braucht einen eingerichteten Frachtführer (K4) – hier eine
        # **Teststrecke** statt eines Netzzugangs: geprüft wird der Zyklus, nicht die
        # Verfügbarkeit einer fremden API.
        for channel in (vergabe.PLATTFORM, vergabe.PORTAL):
            src, dst = _pair(db)
            carrier = _carrier(db, f"Spediteur {channel}")
            with with_carriers([StubCarrier(offers=[carrier_offer(42)])]):
                award = awards.request(db, subject_object_id=src, target_object_id=dst,
                                       channel=channel, actor_id=None)
            states = [award.state]
            offer = awards.add_offer(db, award, provider_object_id=carrier, amount=42)
            states.append(award.state)
            awards.grant(db, award, offer_id=offer.id, actor_id=None)
            states.append(award.state)
            awards.deliver(db, award, unit_ids=[], actor_id=None)
            states.append(award.state)
            seen[channel] = states

        assert seen[vergabe.PLATTFORM] == seen[vergabe.PORTAL] == [
            vergabe.ANGEFRAGT, vergabe.ANGEBOTEN, vergabe.VERGEBEN, vergabe.ERBRACHT
        ], f"Zwei Kanäle, zwei Abläufe: {seen}"
    finally:
        db.rollback()
        db.close()


def test_a_channel_without_offers_refuses_them():
    """**«Selbst bestellt» kennt keine Angebote** – und sagt das, statt sie zu schlucken.

    Bug-Form: das Angebot wird stillschweigend angenommen. Dann stünde ein
    Angebotsvergleich in einem Vorgang, in dem nie einer stattgefunden hat.
    """
    from app.domain import vergabe
    from app.services import awards

    db = session()
    try:
        src, dst = _pair(db)
        carrier = _carrier(db)
        award = awards.request(db, subject_object_id=src, target_object_id=dst,
                               channel=vergabe.SELBST, actor_id=None)
        with pytest.raises(Exception) as err:
            awards.add_offer(db, award, provider_object_id=carrier, amount=10)
        assert getattr(err.value, "status_code", None) == 409
        assert award.state == vergabe.ANGEFRAGT

        # Dort wird unmittelbar vergeben – Dritter und Preis stehen von Anfang an fest.
        awards.grant(db, award, offer_id=None, provider_object_id=carrier,
                     amount=10, actor_id=None)
        assert award.state == vergabe.VERGEBEN and award.provider_object_id == carrier
    finally:
        db.rollback()
        db.close()


def test_an_unknown_third_party_is_a_typo():
    """**Streng schreiben:** einen Dritten, den es nicht gibt, nimmt niemand an.

    Bug-Form: die Objektnummer wird gespeichert und erst Monate später beim Lesen
    auffällig – dann steht in einem verbindlichen Vorgang ein Anbieter, den niemand
    auflösen kann. Gelesen wird dagegen tolerant, wie beim Halter.
    """
    from app.domain import vergabe
    from app.services import awards

    db = session()
    try:
        src, dst = _pair(db)
        award = awards.request(db, subject_object_id=src, target_object_id=dst,
                               channel=vergabe.PORTAL, actor_id=None)
        with pytest.raises(Exception) as err:
            awards.add_offer(db, award, provider_object_id=999_999_999, amount=1)
        assert getattr(err.value, "status_code", None) == 400
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# V3 — Das System wählt vor, der Mensch wählt
# ═══════════════════════════════════════════════════════════════════════════════

def test_the_system_preselects_but_never_grants():
    """**Das günstigste Angebot ist eine Vorwahl, keine Wahl.**

    Bug-Form: das Eintreffen des Angebots vergibt gleich mit – dann wäre ein Zweiter
    gebunden, ohne dass ein Mensch entschieden hat. Gegenprobe in derselben Prüfung: das
    **teurere** Angebot lässt sich vergeben. Wer das verbietet, hat aus der Vorwahl eine
    Wahl gemacht.
    """
    from app.domain import vergabe
    from app.services import awards

    db = session()
    try:
        src, dst = _pair(db)
        billig, teuer = _carrier(db, "Billig AG"), _carrier(db, "Teuer AG")
        with with_carriers([StubCarrier()]):
            award = awards.request(db, subject_object_id=src, target_object_id=dst,
                                   channel=vergabe.PLATTFORM, actor_id=None)
        awards.add_offer(db, award, provider_object_id=teuer, amount=90)
        awards.add_offer(db, award, provider_object_id=billig, amount=10)

        assert award.state == vergabe.ANGEBOTEN, (
            "Ein eingetroffenes Angebot vergibt nicht – es liegt vor.")
        assert [o.amount for o in awards.offers(db, award)] == [10, 90], (
            "Die Vorwahl ist «günstigstes zuerst».")
        assert awards.cheapest(db, award).provider_object_id == billig

        teures = [o for o in awards.offers(db, award) if o.provider_object_id == teuer][0]
        awards.grant(db, award, offer_id=teures.id, actor_id=None)
        assert award.provider_object_id == teuer and award.amount == 90, (
            "Der Mensch darf das teurere wählen – sonst war es keine Wahl.")
    finally:
        db.rollback()
        db.close()


def test_granting_without_a_chosen_offer_is_refused():
    """**Zum Vergeben gehört das gewählte Angebot** – bei jedem Kanal, der welche kennt.

    Bug-Form: ein daneben getippter Preis. Dann stünden zwei Beträge für dieselbe
    Vereinbarung da, und der Beleg sagte nicht, welcher gilt.
    """
    from app.domain import vergabe
    from app.services import awards

    db = session()
    try:
        src, dst = _pair(db)
        carrier = _carrier(db)
        award = awards.request(db, subject_object_id=src, target_object_id=dst,
                               channel=vergabe.PORTAL, actor_id=None)
        awards.add_offer(db, award, provider_object_id=carrier, amount=50)
        with pytest.raises(Exception) as err:
            awards.grant(db, award, offer_id=None, actor_id=None)
        assert getattr(err.value, "status_code", None) == 400
        assert award.state == vergabe.ANGEBOTEN
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# V4 — Erst die Erbringung schreibt einen Ort
# ═══════════════════════════════════════════════════════════════════════════════

def test_only_the_delivery_creates_a_place():
    """**Der Ort folgt der Leistung, nicht der Absicht.**

    Bug-Form: die Vergabe schreibt den Ort schon beim Vergeben. Dann läge die Ware am
    Ziel, während sie noch auf dem Lastwagen steht – und «wo ist X» wäre eine
    Behauptung statt einer Beobachtung.
    """
    from app.domain import vergabe
    from app.services import awards, places

    db = session()
    try:
        src, dst = _pair(db)
        carrier = _carrier(db)
        _, _, units = make_units(db, quantity=2)
        ids = [u.id for u in units]

        award = awards.request(db, subject_object_id=src, target_object_id=dst,
                               channel=vergabe.PORTAL, actor_id=None)
        offer = awards.add_offer(db, award, provider_object_id=carrier, amount=25)
        awards.grant(db, award, offer_id=offer.id, actor_id=None)
        assert places.current(db, ids) == {}, (
            "Vergeben ist eine Absicht – dort liegt noch nichts.")

        awards.deliver(db, award, unit_ids=ids, actor_id=None)
        assert places.current(db, ids) == {i: dst for i in ids}
        assert award.state == vergabe.ERBRACHT
    finally:
        db.rollback()
        db.close()


def test_the_award_writes_the_place_through_the_one_place():
    """**Es gibt EINE Schreibstelle für den Ort** – ``places.record``.

    Bug-Form: die Vergabe legt ihre ``UnitPlace``-Zeile selbst an. Dann gäbe es zwei
    Stellen, an denen eine Beobachtung entsteht, und die zweite vergisst irgendwann, was
    die erste inzwischen tut (Quelle, Akteur, Reihenfolge).
    """
    tree = ast.parse(source("services/awards.py"))
    built = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "UnitPlace" not in built, (
        "Die Vergabe baut keine Ablage – sie ruft ``places.record``.")

    inside = {
        fn.name
        for fn in ast.walk(tree)
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "record"
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "places"
                for n in ast.walk(fn))
    }
    assert inside == {"deliver"}, (
        f"Den Ort schreibt allein die Erbringung, gefunden in: {sorted(inside)}.")


def test_arrival_is_read_from_the_place_not_from_the_award():
    """**Ob etwas angekommen ist, sagt der Ort** – nicht der Zustand einer Vergabe.

    Bug-Form: «gibt es eine erbrachte Vergabe für dieses Paar?» Eine erbrachte ist
    terminal und läge Monate später immer noch da; aus einem alten Vorgang zu schliessen,
    dass heute etwas am Ziel liegt, ist genau die Sorte Ableitung, die still falsch wird.

    Geprüft wird der Unterschied: nach einer Erbringung **ohne** Stücke muss der Vollzug
    weiterhin abweisen – die Vergabe ist erbracht, angekommen ist nichts.
    """
    from app.domain import vergabe
    from app.services import awards, moving

    db = session()
    try:
        src, dst = _pair(db)
        carrier = _carrier(db)
        order, _, units = make_units(db, quantity=1)
        step = _external_step(db, order, dst)

        award = awards.request(db, subject_object_id=src, target_object_id=dst,
                               channel=vergabe.PORTAL, actor_id=None)
        offer = awards.add_offer(db, award, provider_object_id=carrier, amount=25)
        awards.grant(db, award, offer_id=offer.id, actor_id=None)
        awards.deliver(db, award, unit_ids=[], actor_id=None)   # nichts angekommen

        with pytest.raises(Exception) as err:
            moving.record_for_step(db, step=step, units=units,
                                   from_holder_object_id=src, actor_id=None)
        assert getattr(err.value, "status_code", None) == 409, (
            "Eine erbrachte Vergabe ohne Ablage darf keine Ankunft behaupten.")

        # Und mit Ablage geht es durch, ohne dass irgendetwas ein zweites Mal geschrieben
        # wird: der Vollzug **liest** nur.
        from app.services import places
        places.record(db, [u.id for u in units], dst, actor_id=None)
        marks = moving.record_for_step(db, step=step, units=units,
                                       from_holder_object_id=src, actor_id=None)
        assert marks == {"from": src, "to": dst}
        assert len(places.history(db, units[0].id)) == 1, (
            "Der Vollzug schreibt am Ziel nichts nach – die Erbringung hat es getan.")
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# V5 / V6 — Die Matrix geht nie rückwärts
# ═══════════════════════════════════════════════════════════════════════════════

def test_every_transition_outside_the_matrix_is_refused():
    """**Jeder nicht aufgeführte Übergang ist verboten** – systematisch, nicht beispielhaft.

    Bug-Form: ein Parameter oder ein Force-Flag, das an der Matrix vorbeiführt.
    Insbesondere `vergeben → angefragt`: ein Gebundener wird nicht stillschweigend
    entbunden.
    """
    from app.domain import vergabe

    refused = 0
    for src in vergabe.KEYS:
        for dst in vergabe.KEYS:
            if dst in vergabe.TRANSITIONS.get(src, ()):
                continue
            with pytest.raises(Exception) as err:
                vergabe.assert_transition(src, dst, reason="wie auch immer")
            assert getattr(err.value, "status_code", None) == 409, f"{src} → {dst}"
            refused += 1
    assert refused == len(vergabe.KEYS) ** 2 - sum(
        len(v) for v in vergabe.TRANSITIONS.values())
    assert vergabe.VERGEBEN not in vergabe.TRANSITIONS[vergabe.VERGEBEN]
    for terminal in (vergabe.ERBRACHT, vergabe.ABGELEHNT, vergabe.GESCHEITERT):
        assert vergabe.TRANSITIONS[terminal] == (), (
            f"«{terminal}» ist endgültig – ein Weg hinaus wäre ein zweiter Mechanismus.")


def test_the_matrix_can_never_go_backwards():
    """**Die Monotonie wird beim Start geprüft, nicht im Betrieb.**

    Bug-Form: eine Rückwärtskante wird in der Tabelle eingetragen. Sie wäre genau der
    Weg, den `gescheitert` ersetzt – und ohne diese Prüfung fiele sie erst auf, wenn zwei
    Zeilen gleichzeitig auf `vergeben` stünden und niemand sagen könnte, welche gilt.
    """
    from app.domain import vergabe

    order = {s.key: i for i, s in enumerate(vergabe.CATALOG)}
    for src, targets in vergabe.TRANSITIONS.items():
        for dst in targets:
            assert order[dst] > order[src], f"Rückwärtskante {src} → {dst}"

    # Gegenprobe: mit einer Rückwärtskante MUSS die Prüfung anschlagen.
    echt = vergabe.TRANSITIONS
    try:
        vergabe.TRANSITIONS = dict(echt, **{vergabe.VERGEBEN: (vergabe.ANGEFRAGT,)})
        with pytest.raises(RuntimeError):
            vergabe._assert_monotonic()
    finally:
        vergabe.TRANSITIONS = echt
    vergabe._assert_monotonic()


def test_failing_needs_a_reason():
    """**«Gescheitert» ohne Grund gibt es nicht.**

    Bug-Form: der Grund ist optional. Dann steht später da, dass es nicht geklappt hat –
    aber nicht warum, und der zweite Versuch macht denselben Fehler.
    """
    from app.domain import vergabe
    from app.services import awards

    db = session()
    try:
        src, dst = _pair(db)
        carrier = _carrier(db)
        award = awards.request(db, subject_object_id=src, target_object_id=dst,
                               channel=vergabe.PORTAL, actor_id=None)
        offer = awards.add_offer(db, award, provider_object_id=carrier, amount=25)
        awards.grant(db, award, offer_id=offer.id, actor_id=None)

        with pytest.raises(Exception) as err:
            awards.fail(db, award, reason="   ", actor_id=None)
        assert getattr(err.value, "status_code", None) == 400
        assert award.state == vergabe.VERGEBEN, "Ein abgewiesener Wechsel wechselt nichts."

        awards.fail(db, award, reason="Sendung verschollen", actor_id=None)
        assert award.state == vergabe.GESCHEITERT
        assert award.reason == "Sendung verschollen"
    finally:
        db.rollback()
        db.close()


def test_after_a_failure_the_haul_gets_a_normal_second_award():
    """**Eine Korrektur ist ein NEUER Eintrag, nie eine geänderte Zeile** (G5.1).

    Bug-Form: ein «Zurücknehmen» auf `angefragt`. Es wäre der bequemere Weg und der
    falsche – am Ende stünden zwei Zeilen gleichzeitig auf `vergeben`, ohne dass
    irgendetwas sagte, welche gilt. Dass die zweite Vergabe geht, folgt **von selbst**
    daraus, dass `gescheitert` terminal ist: ``open_for`` findet sie nicht mehr.
    """
    from app.domain import vergabe
    from app.models import Award
    from app.services import awards

    db = session()
    try:
        src, dst = _pair(db)
        carrier = _carrier(db)
        first = awards.request(db, subject_object_id=src, target_object_id=dst,
                               channel=vergabe.PORTAL, actor_id=None)
        offer = awards.add_offer(db, first, provider_object_id=carrier, amount=25)
        awards.grant(db, first, offer_id=offer.id, actor_id=None)
        awards.fail(db, first, reason="Spediteur fährt nicht", actor_id=None)

        assert awards.open_for(db, src, dst) is None
        second = awards.request(db, subject_object_id=src, target_object_id=dst,
                                channel=vergabe.PORTAL, actor_id=None)
        assert second.id != first.id, "Die Fuhre bekommt eine ganz normale zweite Vergabe."

        rows = db.query(Award).filter(Award.subject_object_id == src,
                                      Award.target_object_id == dst).all()
        bound = [r for r in rows if r.state == vergabe.VERGEBEN]
        assert len(bound) == 0 and len(rows) == 2
        assert first.state == vergabe.GESCHEITERT, (
            "Die gescheiterte bleibt stehen und sagt, dass DIESER Versuch scheiterte.")
    finally:
        db.rollback()
        db.close()


def test_never_two_open_awards_for_one_haul():
    """**Höchstens eine offene Vergabe je Fuhre** – sonst entsteht «welche gilt?».

    Bug-Form: ``open_for`` nimmt die erste beste Zeile statt der offenen. Dann fände eine
    laufende Fuhre ihre alte, abgelehnte Vergabe und meldete einen Zustand von gestern.
    """
    from app.domain import vergabe
    from app.services import awards

    db = session()
    try:
        src, dst = _pair(db)
        first = awards.request(db, subject_object_id=src, target_object_id=dst,
                               channel=vergabe.PORTAL, actor_id=None)
        awards.reject(db, first, reason="doch nicht nötig", actor_id=None)
        second = awards.request(db, subject_object_id=src, target_object_id=dst,
                                channel=vergabe.PORTAL, actor_id=None)

        found = awards.open_for(db, src, dst)
        assert found is not None and found.id == second.id, (
            "Gefunden werden muss die **offene**, nicht die jüngste oder älteste.")
        assert vergabe.is_open(second.state) and not vergabe.is_open(first.state)
    finally:
        db.rollback()
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Die Form: EINE Registry, EINE Schreibstelle, kein Zustand als Eingabefeld
# ═══════════════════════════════════════════════════════════════════════════════

def _spoken_strings(tree: ast.AST) -> set[str]:
    """Alle Zeichenketten des **ausgeführten** Codes – ohne Doc-Texte.

    ``code_only`` taugt hier nicht: es wirft *alle* Zeichenketten weg, und gesucht wird
    ausgerechnet eine. Die Unterscheidung, auf die es ankommt – Prosa darf einen Zustand
    beim Namen nennen, Code nicht –, ist eine **strukturelle**, also fragt der Wächter den
    Syntaxbaum statt den Text.
    """
    docs = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        first = next(iter(node.body), None)
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            docs.add(id(first.value))
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs}


def test_the_states_live_in_exactly_one_registry():
    """**Die Zustandsliste steht genau einmal** – ein neuer Kanal ist ein Adapter.

    Bug-Form: eine zweite Liste (im Schema, in der Oberfläche, im Adapter). Sie läuft
    auseinander, sobald ein Zustand dazukommt – und zwar still: der zweite Ort behält
    seine alte Antwort, und niemand vergleicht sie.
    """
    from app.domain import vergabe

    for rel, src in live_sources():
        if rel == "domain/vergabe.py":
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:  # pragma: no cover - andere Baustelle
            continue

        second = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Assign)
                  for t in n.targets
                  if isinstance(t, ast.Name) and t.id == "TRANSITIONS"]
        assert not second, f"Zweite Übergangstabelle in {rel}."

        spoken = _spoken_strings(tree) & set(vergabe.KEYS)
        assert not spoken, (
            f"{rel} nennt den Zustand {sorted(spoken)} wörtlich – die Konstante steht in "
            f"``domain/vergabe``, damit ein Umbenennen nicht die halbe Anwendung "
            f"stillschweigend zurücklässt.")


def test_a_state_changes_at_exactly_one_place():
    """**Jeder Zustandswechsel geht durch ``_move``** – und das fragt die Registry.

    Bug-Form: ein zweiter Schreibweg. Er funktioniert ja – deshalb findet ihn kein
    Verhaltenstest; er umgeht nur die Matrix, und das fällt erst auf, wenn ein Übergang
    stattgefunden hat, den es nicht geben darf.
    """
    tree = ast.parse(source("services/awards.py"))
    writers = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target] if isinstance(node, ast.AugAssign) else [])
            for t in targets:
                if isinstance(t, ast.Attribute) and t.attr == "state":
                    writers.add(fn.name)
    assert writers == {"_move"}, (
        f"``award.state`` wird ausserhalb von ``_move`` geschrieben: {sorted(writers)}.")

    # Und ``_move`` fragt wirklich die Registry, statt selbst zu urteilen.
    move = next(f for f in ast.walk(tree)
                if isinstance(f, ast.FunctionDef) and f.name == "_move")
    asks = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "assert_transition" for n in ast.walk(move))
    assert asks, "``_move`` muss ``vergabe.assert_transition`` rufen."


def test_there_is_no_endpoint_that_sets_a_state():
    """**Ein Endpunkt je Vorgang, keiner je Zustand.**

    Bug-Form: ein ``PATCH {state: …}``. Es wäre die zweite Stelle, an der die
    Übergangsmatrix gepflegt wird – und zwar die, die man vergisst.
    """
    tree = ast.parse(source("routers/awards.py"))
    methods = {
        d.func.attr
        for fn in ast.walk(tree)
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
        for d in fn.decorator_list
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
    }
    assert methods <= {"post", "get"}, (
        f"Geschrieben wird eine Handlung, kein Zustand – gefunden: {sorted(methods)}.")

    from app.schemas.award import AwardCreate, GrantInput, OfferCreate, ReasonInput
    for schema in (AwardCreate, GrantInput, OfferCreate, ReasonInput):
        assert "state" not in schema.model_fields, (
            f"{schema.__name__} nimmt einen Zustand entgegen – der ist eine Auskunft.")


def test_the_award_is_shown_at_the_haul_only_while_it_is_open():
    """**Die Vergabe an der Fuhre ist die Auskunft «woran liegt es»** – nicht mehr.

    Bug-Form: eine erbrachte oder abgelehnte Vergabe bleibt an der Fuhre stehen. Dann
    beschriebe eine Stelle, die die **Gegenwart** zeigt, einen Vorgang von gestern.

    Und innerbetrieblich gibt es gar keine: gleiche Anschrift, kein Dritter.
    """
    from app.domain import vergabe
    from app.services import awards, moving

    db = session()
    try:
        src, dst = _pair(db)
        order, _, units = make_units(db, quantity=1)
        step = _external_step(db, order, dst)
        from app.services import places
        places.record(db, [u.id for u in units], src, actor_id=None)
        # Die Arbeitsmenge kommt vom Aufrufer – dass sie aus dem **Prozess** stammt und
        # nie aus dem Ort, ist eine eigene Regel und steht als O6 in ``test_place``.
        at_step = units

        assert moving.hauls(db, step=step, units=at_step)[0].award is None, (
            "Ohne Anfrage gibt es keine – das System legt nichts an.")

        award = awards.request(db, subject_object_id=src, target_object_id=dst,
                               channel=vergabe.PORTAL, actor_id=None)
        shown = moving.hauls(db, step=step, units=at_step)[0].award
        assert shown is not None and shown.id == award.id

        awards.reject(db, award, reason="anders gelöst", actor_id=None)
        assert moving.hauls(db, step=step, units=at_step)[0].award is None, (
            "Eine beendete Vergabe ist Vergangenheit und gehört nicht an die Fuhre.")

        # Innerbetrieblich: gleiche Anschrift, kein Dritter, keine Vergabe.
        nord = make_company(db, "Werk Nord II", **ZUERICH).object_id
        internal_step = _external_step(db, order, nord)
        haul = moving.hauls(db, step=internal_step, units=at_step)[0]
        assert haul.internal and haul.award is None
    finally:
        db.rollback()
        db.close()
