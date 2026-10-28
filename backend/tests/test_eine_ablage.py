"""►►► **Eine Ablage – Belege, Modulfelder, Rechtstexte sind Dokumente.** ◄◄◄

Jeder Wächter steht neben der Fehlerform, die er fängt: ein Papier ohne Dokument, eine
Übernahme, die zweimal anlegt, ein Rechtstext aus dem Code statt aus dem Feld, ein Papier,
das ohne Freigabe hinausgeht.
"""

import uuid

import pytest

from app.domain import voucher as vo
from app.models import Attachment, Document, DocumentRef
from app.services import documents, legal, todo, voucher as svc, voucher_docs
from tests.runner import session
from tests.test_zahlung_ablauf import _do, _house, _ready, _scene, _staff


@pytest.fixture
def db():
    """Wie in den Zahlungstests: eine Sitzung mit dem Haus, das Belege stellen kann (Anschrift,
    MWST-Nummer, AGB) – in einer leeren Datenbank gibt es sonst keines."""
    s = session()
    _house(s)
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_every_paper_is_a_document_in_the_module_field(db):
    """Bug-Formen: (a) das Papier steht nur in ``voucher_documents``; (b) es hängt nicht im
    Pflichtfeld des Moduls (dann liesse es sich löschen); (c) nicht bei der Partei."""
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    rec = svc.documents_of(db, row, vo.OFFER_DOC)[0]
    assert rec.document_id and not hasattr(rec, "html"), "(a)"
    doc = documents.field_document(db, order.object_id, "voucher.doc", f"step:{step.id}")
    assert doc is not None and doc.id == rec.document_id and doc.source == "voucher", "(b)"
    assert documents.delete_problem(db, doc), "(b) ein Beleg lässt sich nie löschen"
    refs = {r.object_id for r in documents.refs_of(db, [doc.id])[doc.id]}
    assert who.object_id in refs, "(c)"
    assert "Offerte" in voucher_docs.paper_of(db, rec)


def test_nothing_goes_out_without_release(db):
    """Bug-Form: eine Zusage oder ein Zahlungseingang gibt ein Papier von selbst hinaus."""
    assert svc.AUTO_RELEASE == (), "Heute geht kein Papier ohne Freigabe hinaus."
    order, step, row, who = _scene(db, first=True)
    _ready(db, order, step, row)
    _do(db, order, step, "ask")
    _do(db, order, step, "agree", party=who.object_id)
    assert not svc.documents_of(db, row, vo.CONFIRM_DOC)
    items = {t.object_id: [i.label for i in t.items] for t in todo.todo(db, _staff(db))}
    assert "Auftragsbestätigung freigeben" in items.get(order.object_id, []), (
        "Was ansteht, zählt ins «zu tun» des Auftrags.")


def test_adoption_seeds_the_legal_texts_once(db):
    """Bug-Formen: (a) die erste Übernahme lässt eine eigene Gesellschaft ohne AGB; (b) ein
    zweiter Start legt wieder an (dann entstünde «von selbst», was ein Mensch wählt)."""
    from app.models import CompanySettings
    from app.services import objects
    house = _house(db)
    # Eine Umgebung, die noch nie einen Rechtstext hatte (im Test zurückgerollt).
    db.query(DocumentRef).filter(DocumentRef.field.in_(tuple(legal.FIELD_OF.values()))).delete(
        synchronize_session=False)
    db.flush()
    first = legal.adopt_templates(db)
    assert first >= 2 and legal.document_of(db, house, legal.AGB) is not None, "(a)"
    late = CompanySettings(is_own=True, company_name="Später", legal_form="AG",
                           object_id=objects.next_object_id(db, "organization"))
    db.add(late)
    db.flush()
    assert legal.adopt_templates(db) == 0, "(b)"
    assert legal.document_of(db, late, legal.AGB) is None, "(b) – sie wählt selbst"


def test_legal_texts_come_from_the_company_field(db):
    """Bug-Formen: (a) die AGB kommen aus dem Code statt aus dem Feld; (b) ein PDF wird
    gesetzt, als wäre es Markdown; (c) eine Gesellschaft ohne AGB zählt nicht ins «zu tun»."""
    house = _house(db)
    text = legal.text_of(db, house, legal.AGB)
    assert text is not None and text.sections, "(a)"
    pdf, _ = documents.file(db, raw=b"%PDF-1.4\n" + uuid.uuid4().bytes, filename="agb.pdf",
                            mime="application/pdf", art="AGB", name="AGB 2027",
                            source="file", refs=[], actor=None)
    documents.set_field(db, document_object_id=pdf.object_id, object_id=house.object_id,
                        part=None, field="company.agb", actor=None)
    text = legal.text_of(db, house, legal.AGB)
    assert not text.sections and "AGB 2027" in text.intro[0], "(b)"
    _t, url, _v = legal.for_visitor(db, legal.AGB, "CH")
    assert url and url == documents.file_url(db, pdf), "Die Website zeigt die Datei, wie sie ist."
    for r in db.query(DocumentRef).filter(DocumentRef.object_id == house.object_id,
                                          DocumentRef.field == "company.privacy").all():
        r.is_active = False
    db.flush()
    items = {t.object_id: [i.label for i in t.items] for t in todo.todo(db, _staff(db))}
    assert "Datenschutz fehlt" in items.get(house.object_id, []), "(c)"


def test_a_form_photo_opens_as_the_file_it_was(db):
    """Ein Foto des Kontaktformulars öffnet sich im Entwurf als die Datei, die es war –
    derselbe Weg wie ein Anhang einer Mail. Bug-Form: der Index greift daneben."""
    import pytest
    from fastapi import HTTPException
    from app.models import Message
    from app.services import attachments, mailbox
    att = attachments.store_raw(db, b"\xff\xd8\xff" + uuid.uuid4().bytes, "a.jpg", "image/jpeg", None)
    msg = Message(sender_object_id=1, channel="c1", subject="x", body="",
                  attachments=[{"name": "a.jpg", "size": 3, "url": attachments.public_url(att)}])
    db.add(msg)
    db.flush()
    raw, mime, name = mailbox.attachment(db, msg, 0)
    assert raw == bytes(att.data) and mime == "image/jpeg" and name == "a.jpg"
    with pytest.raises(HTTPException):
        mailbox.attachment(db, msg, 1)


def test_a_file_is_private_unless_the_website_shows_it(db):
    """Eine Datei hinter ihrem Link ist **privat**: kein geteilter Zwischenspeicher (CDN,
    Proxy) behält sie. ``public`` nur für die Rechtstexte der Website. Bug-Form: jede Datei –
    Arztzeugnis, Rechnung – ging mit ``Cache-Control: public`` hinaus."""
    import io
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from PIL import Image
    from app.core.database import get_db
    from app.routers import attachments as router
    from app.services import attachments
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, "PNG")
    att = attachments.store_image(db, buf.getvalue(), "zeugnis.png", None)
    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    for path in (f"/api/v1/attachments/{att.token}", f"/api/v1/attachments/{att.token}/preview"):
        cache = client.get(path).headers["cache-control"]
        assert cache.startswith("private") and "public" not in cache, path
    _house(db)
    db.query(DocumentRef).filter(DocumentRef.field.in_(tuple(legal.FIELD_OF.values()))).delete(
        synchronize_session=False)
    db.flush()
    assert legal.adopt_templates(db) >= 1
    agb = db.query(Document).join(DocumentRef, DocumentRef.document_id == Document.id).filter(
        DocumentRef.field == legal.FIELD_OF[legal.AGB]).first()
    token = db.query(Attachment.token).filter(Attachment.id == agb.file_id).scalar()
    assert client.get(f"/api/v1/attachments/{token}").headers["cache-control"].startswith("public")
