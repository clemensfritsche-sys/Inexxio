"""**Der Lebenszyklus eines Artikels** — ausser Betrieb nehmen, ersetzen, und was das
für die Stücklisten ringsum bedeutet.

Der Knopf «Deaktivieren / ersetzen» war eine **Attrappe**: er rief einen Dialog, den es
seit dem Basis-Neuaufbau nicht mehr gibt, und tat darum nichts. «Ersetzen» war überhaupt
nie gebaut. Was hier geprüft wird, sind die Sätze, aus denen der Ersatz besteht — jeder
gegen seine **Bug-Form**:

1. **Ausser Betrieb ist ein Zustand, kein Ende** – der Weg zurück ist derselbe Knopf.
2. **Es wird gemeldet, nicht erzwungen** – wer einen ausser Betrieb genommenen Artikel
   verbaut, bleibt erzeugbar und **sagt es selbst**.
3. **Transitiv** – eine Lücke drei Stufen tiefer ist meine Auskunft, mit dem Weg dorthin.
4. **Die Lösung steht beim Problem** – gibt es einen Nachfolger, wird er genannt.
5. **Gefiltert wird in der Datenbank**, nicht im Python – sonst lädt jede Artikel-Anzeige
   sämtliche Vorlagen des Hauses.
6. **Ersetzen ist eine Angabe an der Anlage des Nachfolgers**, kein zweiter Aufruf – und
   es nimmt den Vorgänger im selben Zug ausser Betrieb.
7. **Ein Vorgänger hat genau einen Nachfolger** – und er lässt sich als Ersatzteil
   wieder aktiv setzen, ohne dass die Reihe zerfällt.
8. **Zyklensicher** in beide Richtungen (Stückliste und Ersetzungskette).
9. **Die Stückliste steht nur am Detail** – ``None`` heisst «nicht geladen».

Gefahren wird über die **echten** Dienstpfade gegen echtes PostgreSQL: die JSONB-Frage
«nennt diese Vorlage Artikel X?» gibt es in SQLite gar nicht, und eine nachgestellte
Antwort wäre keine.
"""

import pathlib
import re

import pytest

from tests.runner import session

BACKEND = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Bedienung – keine Regel wird hier nachgebaut
# ---------------------------------------------------------------------------

def _db():
    return session()


def _article(db, name: str, *, consumes: list[tuple[int, int]] | None = None):
    """Ein freigegebener Artikel; ``consumes`` gibt ihm ein Verbrauchsmodul.

    Über den **echten** Anlagepfad (``services/articles.create_article``) – damit prüft
    der Test die Regel und nicht eine handgestellte Zeile.
    """
    from app.services import articles as svc

    steps = [{"module_type": "datenerfassung",
              "config": {"points": [{"label": "OK", "type": "bool"}]}}]
    if consumes:
        steps.append({
            "module_type": "verbrauch",
            "config": {"lines": [{"article": a, "quantity": q} for a, q in consumes]},
        })
    art = svc.create_article(
        db, {"name": name, "unit": "Stk", "serialization": "unit",
             "size": "10x20", "weight_kg": 1, "steps": steps},
        actor_id=None)
    db.flush()
    return art


def _retire(db, article):
    """Ausser Betrieb nehmen — genau das, was der Knopf tut: ein Statuswechsel."""
    from app.domain import statuses as st
    article.status = st.INAKTIV
    db.flush()


def _detail(db, article):
    """Die Detail-Antwort, so wie sie die Oberfläche bekommt."""
    from app.routers.articles import _detail as build
    return build(db, article)


def _source(name: str) -> str:
    return (BACKEND / "app" / "services" / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1 · Ausser Betrieb ist ein Zustand, kein Ende
# ---------------------------------------------------------------------------

def test_out_of_service_is_a_state_not_an_end():
    """**Der Weg zurück ist derselbe Knopf.**

    Bug-Form: «Inaktiv ist endgültig – kein Reaktivieren». Das stand als Kommentar in der
    Oberfläche und war die Begründung dafür, dass es keine Gegenaktion gab. Es widerspricht
    aber der Statusliste: ``Status.terminal`` gibt es nur auf der Stück-Achse
    (``domain/statuses``), und ``Inaktiv`` trägt es nicht. Ein Artikel, den man versehentlich
    ausser Betrieb genommen hat, wäre sonst für immer verloren – und der einzige Ausweg
    hiesse «denselben Artikel noch einmal anlegen», also eine zweite Nummer für dieselbe Sache.
    """
    from app.domain import statuses as st

    db = _db()
    try:
        art = _article(db, "Rückweg")
        assert not st.is_terminal(st.INAKTIV), (
            "«Inaktiv» darf nicht terminal sein – sonst gäbe es keinen Weg zurück, und "
            "genau das behauptete die Oberfläche."
        )
        _retire(db, art)
        assert art.status == st.INAKTIV
        # …und zurück, über denselben gewöhnlichen Statuswechsel.
        art.status = st.FREIGEGEBEN
        db.flush()
        from app.services import articles as svc
        assert svc.may_create(art) is None, "Wieder aktiv heisst wieder erzeugbar."
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# 2 · Wer mich verbaut, steht an mir – gefiltert in der Datenbank
# ---------------------------------------------------------------------------

def test_used_in_names_who_builds_me():
    """**«Was mache ich kaputt?» steht am Datensatz, nicht in einem Dialog.**

    Bug-Form: die Frage wurde gar nicht gestellt – der Knopf nahm einen Artikel ausser
    Betrieb (bzw. hätte es getan), ohne dass irgendwo stand, wer ihn braucht.
    """
    from app.services import bom

    db = _db()
    try:
        screw = _article(db, "Schraube M6")
        other = _article(db, "Nichts damit")
        gear = _article(db, "Getriebe", consumes=[(screw.object_id, 4)])

        names = [r.object_id for r in bom.used_in(db, screw)]
        assert names == [gear.object_id], (
            f"Genau das Getriebe nennt die Schraube – gefunden {names}."
        )
        assert bom.used_in(db, other) == [], "Wer niemanden nennt, wird nirgends genannt."
        # Der Verwender trägt seinen Zustand mit: «(ausser Betrieb)» ist eine Warnung,
        # ohne den Zustand wäre es eine blosse Aufzählung.
        assert bom.used_in(db, screw)[0].status == gear.status
    finally:
        db.rollback()
        db.close()


def test_used_in_is_filtered_in_the_database():
    """**Die Frage gehört in die Abfrage.**

    Bug-Form (erste Fassung dieser Datei): alle ``(Article, ArticleProcessStep)`` laden und
    im Python filtern. Das ist bei drei Artikeln unauffällig und bei tausend die Sekunde,
    die jede Artikel-Anzeige kostet – für eine Frage, die PostgreSQL mit ``@>`` beantwortet.
    """
    src = _source("bom.py")
    assert ".contains(" in src and "JSONB" in src, (
        "``used_in`` muss über JSONB-Containment filtern (``@>``), nicht im Python."
    )
    body = src[src.index("def used_in("):src.index("def _walk_down(")]
    assert "for owner, step in" not in body, (
        "Kein Nachfiltern im Python – wer hier eine Schleife über alle Vorlagen sieht, "
        "hat die Bug-Form zurück."
    )


# ---------------------------------------------------------------------------
# 3+4 · Ausser Betrieb genommene Zutaten – transitiv, mit Weg und Nachfolger
# ---------------------------------------------------------------------------

def test_a_retired_input_is_reported_with_its_path():
    """**Transitiv, und der Weg dorthin steht dabei.**

    Maschine → Getriebe → Schraube. Wird die Schraube ausser Betrieb genommen, ist das
    eine Auskunft der **Maschine** – sonst müsste jemand die Stückliste von Hand
    absteigen, um zu verstehen, warum seine Maschine nicht mehr baubar ist.

    Bug-Form: nur die direkte Stückliste lesen – dann meldet die Maschine nichts, obwohl
    ihr ein Teil fehlt.
    """
    from app.services import bom

    db = _db()
    try:
        screw = _article(db, "Schraube M6")
        gear = _article(db, "Getriebe", consumes=[(screw.object_id, 4)])
        machine = _article(db, "Maschine", consumes=[(gear.object_id, 1)])
        _retire(db, screw)

        rows = bom.retired_inputs(db, machine)
        assert [r.article.object_id for r in rows] == [screw.object_id]
        assert [v.object_id for v in rows[0].via] == [gear.object_id], (
            "Der Weg nennt die Stufe dazwischen – ohne ihn wüsste niemand, WO das Problem sitzt."
        )
        # Direkt darüber ist der Weg leer: die Schraube steht dort in der eigenen Stückliste.
        assert bom.retired_inputs(db, gear)[0].via == ()
        # Und wer nichts davon verbaut, meldet nichts.
        assert bom.retired_inputs(db, screw) == []
    finally:
        db.rollback()
        db.close()


def test_a_retired_input_names_its_successor():
    """**Die Lösung steht dort, wo das Problem gemeldet wird.**

    Bug-Form: nur «Schraube M6 ist ausser Betrieb» melden. Dann sucht der Mensch den
    Nachfolger von Hand – obwohl das System ihn kennt.
    """
    from app.services import articles as svc, bom

    db = _db()
    try:
        old = _article(db, "Schraube alt")
        gear = _article(db, "Getriebe", consumes=[(old.object_id, 4)])
        new = _article(db, "Schraube neu")
        svc.apply_replacement(db, predecessor=old, successor=new)
        db.flush()

        row = bom.retired_inputs(db, gear)[0]
        assert row.article.object_id == old.object_id
        assert row.replaced_by is not None and row.replaced_by.object_id == new.object_id
        assert row.replaced_by.name == "Schraube neu"
    finally:
        db.rollback()
        db.close()


def test_a_retired_input_is_reported_not_forbidden():
    """**Melden, nicht erzwingen.**

    Der Verwender bleibt **erzeugbar**, solange Restbestand da ist – das ist die
    Wirklichkeit, und sie zu verbieten wäre eine Regel gegen den Betrieb. Verboten ist
    nur, was der ausser Betrieb genommene Artikel selbst tut: **Neues** erzeugen.

    Bug-Form: die Kaskade erzwingen – dann reisst ein einzelnes ausgelaufenes Teil einen
    ganzen Baum von Artikeln mit, und niemand kann die Restbestände noch aufbrauchen.
    """
    from app.services import articles as svc, bom

    db = _db()
    try:
        screw = _article(db, "Schraube M6")
        gear = _article(db, "Getriebe", consumes=[(screw.object_id, 4)])
        _retire(db, screw)

        assert svc.may_create(screw) is not None, "Der ausser Betrieb genommene erzeugt nichts."
        assert svc.may_create(gear) is None, (
            "Der Verwender bleibt erzeugbar – die Lücke ist eine Auskunft, keine Sperre."
        )
        assert gear.status != screw.status, "Und er wird auch nicht mitgezogen."
        assert bom.retired_inputs(db, gear), "Gemeldet wird sie trotzdem."
    finally:
        db.rollback()
        db.close()


def test_the_bom_graph_survives_a_cycle():
    """**Zyklensicher.**

    Der Stücklisten-Graph ist nirgends gegen Kreise geschützt (die einzige Prüfung gilt je
    Auftrag, nicht über Artikel hinweg). Bug-Form: ohne ``seen`` läuft die Ansicht endlos –
    und zwar nicht beim Anlegen, sondern beim Öffnen eines Artikels.
    """
    from app.models import ArticleProcessStep
    from app.services import bom

    db = _db()
    try:
        a = _article(db, "Kreis A")
        b = _article(db, "Kreis B", consumes=[(a.object_id, 1)])
        # A verbraucht B – der Kreis entsteht von Hand, weil kein Dienstpfad ihn zulässt.
        db.add(ArticleProcessStep(
            article_id=a.id, position=9, module_type="verbrauch",
            status_before="freigegeben", status_after="freigegeben",
            config={"lines": [{"article": b.object_id, "quantity": 1}]}))
        _retire(db, b)
        db.flush()

        rows = bom.retired_inputs(db, a)      # muss enden, nicht hängen
        assert [r.article.object_id for r in rows] == [b.object_id]
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# 5 · Ersetzen – eine Angabe an der Anlage des Nachfolgers
# ---------------------------------------------------------------------------

def test_the_successor_takes_the_predecessor_out_of_service():
    """**Ein Vorgang, ein Aufruf.**

    Bug-Form: zwei Klicks – erst den Nachfolger anlegen, dann den Vorgänger ausser
    Betrieb nehmen. Das ist eine Gelegenheit, den zweiten zu vergessen, und dann laufen
    zwei «gültige» Fassungen nebeneinander.
    """
    from app.domain import statuses as st
    from app.services import articles as svc

    db = _db()
    try:
        old = _article(db, "Fassung 1")
        new = svc.create_article(
            db, {"name": "Fassung 2", "unit": "Stk", "serialization": "unit",
                 "size": "10x20", "weight_kg": 1,
                 "steps": [{"module_type": "datenerfassung",
                            "config": {"points": [{"label": "OK", "type": "bool"}]}}],
                 "replaces_object_id": old.object_id},
            actor_id=None)
        db.flush()

        assert old.replaced_by_id == new.object_id, "Die Kante zeigt alt → neu."
        assert old.status == st.INAKTIV, (
            "Ersetzen NIMMT ausser Betrieb – das ist keine zusätzliche Wirkung, sondern "
            "die Bedeutung: wer abgelöst ist, erzeugt nichts Neues mehr."
        )
        assert new.status == st.FREIGEGEBEN
        # Und beide Richtungen der Kette stehen an der Antwort.
        assert _detail(db, old).replaced_by.object_id == new.object_id
        assert _detail(db, new).replaces.object_id == old.object_id
    finally:
        db.rollback()
        db.close()


def test_a_replaced_predecessor_can_be_set_active_again():
    """**Der Vorgänger bleibt als Ersatzteil lieferbar** – und die Reihe bleibt stehen.

    Die Frage aus Testnotiz #766: darf man einen abgelösten Artikel wieder aktiv setzen,
    ohne dass die Ersetzung verlorengeht? Ja – und zwar **ohne eine eigene Regel**: am
    Artikel ist «ausser Betrieb» ein gewöhnlicher Zustand in beide Richtungen (Wächter 1),
    und ``replaced_by_id`` ist eine **andere** Angabe, die davon nichts weiss. Genau
    dieser Zusammenhang war die Sorge, und er wird hier festgehalten, statt ihn beim
    nächsten Umbau neu herleiten zu müssen.

    Bug-Form: eine Kopplung «Status → Reihe» (der Statuswechsel räumt ``replaced_by_id``,
    oder ``may_create`` fragt zusätzlich nach der Reihe). Dann wäre das Reaktivieren
    entweder wirkungslos oder es zerrisse die Kette – und das Ersatzteilgeschäft ginge
    nur noch über eine zweite Nummer für dasselbe Ding.
    """
    from app.domain import statuses as st
    from app.services import articles as svc

    db = _db()
    try:
        old = _article(db, "Fassung 1")
        new_art = svc.create_article(
            db, {"name": "Fassung 2", "unit": "Stk", "serialization": "unit",
                 "size": "10x20", "weight_kg": 1,
                 "steps": [{"module_type": "datenerfassung",
                            "config": {"points": [{"label": "OK", "type": "bool"}]}}],
                 "replaces_object_id": old.object_id},
            actor_id=None)
        db.flush()
        assert old.status == st.INAKTIV and old.replaced_by_id == new_art.object_id

        # Der ganz gewöhnliche Statuswechsel – dasselbe, was der Knopf im Kopf tut.
        old.status = st.FREIGEGEBEN
        db.flush()

        assert svc.may_create(old) is None, (
            "Wieder aktiv heisst wieder erzeugbar – genau darum geht es beim Ersatzteil. "
            "Wer hier zusätzlich nach der Reihe fragt, macht das Reaktivieren wirkungslos."
        )
        # **Nach** der Frage geprüft: eine Kopplung «Status → Reihe» räumt die Kante
        # genau dann, wenn jemand hinschaut – der Wächter muss den Zustand also danach
        # lesen, sonst prüft er einen Moment, den es so nicht mehr gibt.
        assert old.replaced_by_id == new_art.object_id, (
            "Die Reihe hängt nicht am Status – ein reaktivierter Vorgänger bleibt "
            "abgelöst, sonst gäbe es zwei neueste Fassungen."
        )
        detail = _detail(db, old)
        assert detail.replaced_by is not None and detail.replaced_by.object_id == new_art.object_id, (
            "Und die Antwort sagt weiterhin, wer ihn abgelöst hat."
        )
        # Zweimal ersetzen bleibt trotzdem verboten – die Reihe steht ja noch.
        assert svc.replaceable_problem(old) is not None, (
            "Ein reaktivierter Vorgänger ist kein unbeschriebenes Blatt: er hat seinen "
            "Nachfolger, und ein zweiter wäre eine zweite «neueste Fassung»."
        )
    finally:
        db.rollback()
        db.close()


def test_the_replacement_hint_says_both_halves():
    """**Was fehlte, war der Satz** – nicht die Möglichkeit (Testnotiz #766).

    Der Hinweis am Auswahlfeld sagte nur, dass der Vorgänger ausser Betrieb geht. Wer ihn
    liest, hält das für endgültig und traut sich nicht – obwohl der Weg zurück ein Klick
    ist. Bug-Form: die halbe Aussage, die formal stimmt und in der Praxis abschreckt.
    """
    src = (BACKEND.parent / "frontend" / "src" / "components" / "erp"
           / "article-detail.tsx").read_text(encoding="utf-8")
    # **Gelesen wird die Komponente, nicht die Datei.** Ein Satz irgendwo sonst in
    # `article-detail.tsx` würde den Wächter sonst beruhigen, ohne dass er dort steht,
    # wo man wählt – gemessen: mit dem Dateiende als Grenze geht genau das durch.
    body = src[src.index("function ReplacesPicker"):]
    hint = body[:body.index("\n}\n") + 3]
    assert "wieder aktiv setzen" in hint, (
        "Der Hinweis muss die zweite Hälfte nennen: der Vorgänger lässt sich als "
        "Ersatzteil wieder aktiv setzen."
    )
    assert "Reihe bleibt" in hint, (
        "…und dass die Ersetzung dabei bestehen bleibt – sonst klingt Reaktivieren wie "
        "ein Zurücknehmen der Ablösung."
    )


def test_an_article_is_replaced_at_most_once():
    """**Ein Vorgänger hat genau einen Nachfolger** – und die Ablehnung nennt ihn.

    Bug-Form: zwei Nachfolger zulassen. Dann gibt es zwei «neueste Fassungen», und keine
    Auflösung kann sagen, welche gilt.
    """
    from fastapi import HTTPException
    from app.services import articles as svc

    db = _db()
    try:
        old = _article(db, "Fassung 1")
        new = _article(db, "Fassung 2")
        svc.apply_replacement(db, predecessor=old, successor=new)
        db.flush()

        third = _article(db, "Fassung 3")
        with pytest.raises(HTTPException) as e:
            svc.apply_replacement(db, predecessor=old, successor=third)
        assert str(new.object_id) in str(e.value.detail), (
            "Die Ablehnung nennt den bestehenden Nachfolger – sonst sucht ihn der Mensch."
        )
        # Und die Regel gibt es genau EINMAL: die Anlage stellt dieselbe Frage.
        with pytest.raises(HTTPException):
            svc.create_article(
                db, {"name": "Fassung 4", "unit": "Stk", "serialization": "unit",
                     "size": "10x20", "weight_kg": 1,
                     "steps": [{"module_type": "datenerfassung",
                                "config": {"points": [{"label": "OK", "type": "bool"}]}}],
                     "replaces_object_id": old.object_id},
                actor_id=None)
    finally:
        db.rollback()
        db.close()


def test_the_replacement_chain_survives_a_cycle():
    """**Auch die Ersetzungskette wird gekappt gelesen.**

    Bug-Form: ohne ``seen`` liesse ein Kreis in ``replaced_by_id`` jede Auflösung «wer ist
    die neueste Fassung?» endlos laufen – und die läuft bei **jedem** Öffnen eines Artikels.
    """
    from app.services import articles as svc

    db = _db()
    try:
        a = _article(db, "Kette A")
        b = _article(db, "Kette B")
        svc.apply_replacement(db, predecessor=a, successor=b)
        b.replaced_by_id = a.object_id      # der Kreis, von Hand
        db.flush()

        chain = svc.chain_of(db, a)         # muss enden, nicht hängen
        assert [c.object_id for c in chain] == [b.object_id], (
            "Die Kette wird **vor** dem zweiten Besuch gekappt – ein Artikel steht in "
            "seiner eigenen Kette genau einmal, nämlich am Anfang."
        )
        # …und der Kreis wird abgewiesen, wenn ihn jemand über den Dienstpfad zöge:
        # C ersetzt B, aber B führt über seine Kette schon zu C zurück.
        from fastapi import HTTPException
        b.replaced_by_id = None
        c = _article(db, "Kette C")
        svc.apply_replacement(db, predecessor=b, successor=c)
        b.replaced_by_id = None          # B wieder frei – der Kreis läge allein in C→…→B
        c.replaced_by_id = b.object_id
        db.flush()
        with pytest.raises(HTTPException) as e:
            svc.assert_replaceable(db, b, c)
        assert "Kreis" in str(e.value.detail), (
            "Gefragt wird VORWÄRTS ab dem Nachfolger – die Kette des Vorgängers ist "
            "definitionsgemäss leer, dort zu suchen träfe nie zu."
        )
    finally:
        db.rollback()
        db.close()


def test_an_article_never_replaces_itself():
    """Eine Kette, die auf sich selbst zeigt, hat keinen neuesten Stand."""
    from fastapi import HTTPException
    from app.services import articles as svc

    db = _db()
    try:
        a = _article(db, "Ich selbst")
        with pytest.raises(HTTPException) as e:
            svc.assert_replaceable(db, a, a)
        assert "selbst" in str(e.value.detail)
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# 6 · Die Stückliste steht nur am Detail
# ---------------------------------------------------------------------------

def test_the_bom_is_loaded_at_the_detail_only():
    """``None`` heisst «nicht geladen», nicht «nichts gefunden».

    Bug-Form: die Stückliste im Feed mitliefern. Zwei Abfragen je Artikel × zweihundert
    Artikel je Feed-Aufruf – und der Feed braucht sie nicht, er zeigt eine Liste.
    Umgekehrt wäre eine **leere** Stückliste im Feed eine Falschaussage: sie sähe aus wie
    «dieser Artikel wird nirgends verbaut».

    **Auch die Schreibpfade antworten ohne sie.** Das Umfeld ist eine eigene Frage; sie
    dort mitzurechnen hiesse, sie zweimal zu stellen und trotzdem nur dort zu haben, wo
    zufällig gerade geschrieben wurde.
    """
    from app.routers.articles import _out

    db = _db()
    try:
        screw = _article(db, "Schraube M6")
        _article(db, "Getriebe", consumes=[(screw.object_id, 4)])

        assert _out(screw).bom is None, "Im Feed bleibt sie ungeladen."
        detail = _detail(db, screw)
        assert detail.bom is not None and len(detail.bom.used_in) == 1

        src = (BACKEND / "app" / "routers" / "articles.py").read_text(encoding="utf-8")
        assert src.count("return _detail(") == 1, (
            "Genau EIN Pfad liefert das Umfeld: das ``GET``-Detail."
        )
    finally:
        db.rollback()
        db.close()


def test_the_dead_deactivate_dialog_is_gone():
    """**Kein Knopf, der nichts tut** – und keine Behauptung, die nicht stimmt.

    Zwei Bug-Formen in derselben Datei: ``setDialog`` ohne Dialog (der Knopf war eine
    Attrappe, ausdrücklich mit ``eslint-disable`` am Wächter vorbeigeschleust) und der
    Kommentar «Inaktiv ist endgültig», der der Statusliste widerspricht.
    """
    src = (BACKEND.parent / "frontend" / "src" / "components" / "erp"
           / "article-detail.tsx").read_text(encoding="utf-8")
    assert "setDialog" not in src, (
        "Der tote Deaktivieren-Dialog ist entfallen – ein Knopf, der nie etwas tun kann, "
        "ist kein Angebot."
    )
    assert "eslint-disable-next-line no-unused-vars" not in src, (
        "Kein Wächter mehr, an dem vorbeigeschleust wird."
    )
    # **Geprüft wird die Tat, nicht das Wort.** «Inaktiv ist endgültig» stand als
    # Begründung dafür, dass es keine Gegenaktion gibt – widerlegt ist sie nicht dadurch,
    # dass der Satz verschwindet, sondern dadurch, dass der Weg zurück da ist.
    assert re.search(r"changeStatus\(FREIGEGEBEN\)", src), (
        "Es muss einen Weg zurück geben – sonst ist «ausser Betrieb» faktisch endgültig, "
        "egal was daneben steht."
    )
    assert re.search(r"data-tip=\"Inaktiv setzen", src) and re.search(r"data-tip=\"Aktiv setzen", src), (
        "Die beiden Richtungen heissen «Inaktiv setzen» ↔ «Aktiv setzen»."
    )
