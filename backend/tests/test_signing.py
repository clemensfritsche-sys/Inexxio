"""►►► **Verfassen, Senden, Unterschreiben** – gegen ihre Fehlerform geprüft. ◄◄◄"""

import base64
import io
import random
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.domain import statuses as st
from app.models import DocumentLink, Message, UserProfile
from app.services import ai, composing, documents, signing


def _person(db, role="employee", name="Lea"):
    oid = random.randint(900_000_000, 999_999_999)
    u = UserProfile(firebase_uid=f"uid-{oid}", email=f"p{oid}@x.ch", role=role, object_id=oid,
                    first_name=name, last_name=f"M{oid}")
    db.add(u)
    db.flush()
    return u


def _png() -> str:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (60, 20), (20, 20, 20)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _paper(signers=()):
    return composing.Paper(reply="Hier ist der Vertrag.", art="Vertrag", name="Wartung 2027",
                           title="Wartungsvertrag", intro=["Zwischen den Parteien …"],
                           sections=[composing.Section(title="1. Gegenstand", paragraphs=["Wartung."])],
                           signers=list(signers))


def _composed(db, staff, signer):
    html = composing.render(db, _paper(), [(signer.object_id, signer.display_name)])
    doc, _ = documents.file(db, raw=html.encode(), filename="v.html", mime="text/html", art="Vertrag",
                            name=f"Wartung {random.random()}", source="compose", refs=[], actor=staff)
    signing.request(db, doc, [signer.object_id], staff)
    return doc


def test_compose_goes_through_the_gate_and_sets_the_paper(db, monkeypatch):
    """Bug-Formen: (a) Verfassen ruft die KI am Tor vorbei; (b) das Papier steht nicht in der
    Vorlage; (c) ein Name wird zur falschen Person."""
    staff = _person(db)
    calls = []

    class Fake:
        def __init__(self):
            self.messages = SimpleNamespace(parse=lambda **kw: calls.append(kw) or SimpleNamespace(
                parsed_output=_paper(["Niemand Unbekannt"]), stop_reason="end_turn",
                usage=SimpleNamespace(input_tokens=1, output_tokens=1)))
    monkeypatch.setattr(ai, "ready", lambda: True)
    monkeypatch.setattr(ai, "used_today", lambda db: 0)
    monkeypatch.setattr(ai, "_client", lambda *a: Fake())
    paper = composing.compose(db, actor=staff, turns=[composing.Turn(who="user", text="Vertrag")],
                              current=None)
    assert paper and calls and calls[0]["model"] == ai.TASKS["compose"].model, "(a)"
    html = composing.render(db, paper, [])
    assert "Wartungsvertrag" in html and 'class="sheet legal a4"' in html, "(b)"
    assert composing.signers_of(db, paper.signers) == [], "(c) kein Treffer ist keine Person"


def test_send_sign_and_the_signature_stands_on_the_paper(db):
    """Bug-Formen: (a) ohne Unterschrift gilt es schon; (b) die Unterschrift steht nicht auf
    dem Papier; (c) zweimal unterschreiben geht; (d) der Link läuft ab."""
    staff, signer = _person(db), _person(db, "user", "Hans")
    doc = _composed(db, staff, signer)
    assert documents.status_of(doc, documents.signatures_of(db, [doc.id])[doc.id]) == st.UNTERSCHRIFT_ANGEFRAGT, "(a)"
    (link,) = signing.send(db, doc, [signer.object_id], "Bitte bis Freitag.", staff)
    assert db.query(Message).filter(Message.id == link.message_id).first() is not None
    assert signing.view(db, link)["actions"] == ["sign", "decline"]
    signing.sign(db, link, _png())
    view = signing.view(db, link)
    assert view["status"] == st.FREIGEGEBEN and "data:image/png;base64" in view["html"], "(b)"
    with pytest.raises(HTTPException) as e:
        signing.sign(db, link, _png())
    assert e.value.status_code == 409, "(c)"
    assert not hasattr(DocumentLink, "expires_at"), "(d) ein Link hat kein Ablaufdatum"


def test_declined_is_the_end_and_deleted_is_a_note(db):
    """Bug-Formen: (a) nach einer Ablehnung unterschreibt noch jemand; (b) ein gelöschtes
    Dokument wirft einen Fehler statt eines Hinweises (410)."""
    staff, a, b = _person(db), _person(db, "user", "A"), _person(db, "user", "B")
    doc = _composed(db, staff, a)
    signing.request(db, doc, [b.object_id], staff)
    la, lb = signing.send(db, doc, [a.object_id, b.object_id], "", staff)
    signing.decline(db, la, "Preis stimmt nicht")
    assert documents.status_of(doc, documents.signatures_of(db, [doc.id])[doc.id]) == st.ABGELEHNT
    assert signing.view(db, lb)["actions"] == [], "(a)"
    for r in documents.refs_of(db, [doc.id])[doc.id]:
        r.is_active = False
    db.flush()
    documents.delete(db, doc, "Entwurf verworfen", staff)
    with pytest.raises(HTTPException) as e:
        signing.view(db, la)
    assert e.value.status_code == 410, "(b)"


def test_a_signature_must_be_a_real_png(db):
    staff, signer = _person(db), _person(db, "user")
    doc = _composed(db, staff, signer)
    (link,) = signing.send(db, doc, [signer.object_id], "", staff)
    for bad in ("", "data:image/png;base64,AAAA", "data:text/html;base64,PGI+"):
        with pytest.raises(HTTPException):
            signing.sign(db, link, bad)


def test_a_full_name_becomes_exactly_one_person(db):
    """Bug-Formen: (a) ein ganzer Name findet niemanden; (b) ein Nachname trifft jeden mit ihm."""
    hans = _person(db, "user", "Hansjakob")
    _person(db, "user", "Hansjakob")          # gleicher Vorname, anderer Nachname
    assert composing.signers_of(db, [hans.display_name]) == [
        {"object_id": hans.object_id, "name": hans.display_name}], "(a)"
    assert composing.signers_of(db, [hans.last_name]) == [], "(b)"
