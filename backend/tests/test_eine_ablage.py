"""►►► **Eine Ablage – Belege, Modulfelder, Rechtstexte sind Dokumente.** ◄◄◄

Jeder Wächter steht neben der Fehlerform, die er fängt: ein Papier ohne Dokument, eine
Übernahme, die zweimal anlegt, ein Rechtstext aus dem Code statt aus dem Feld, ein Papier,
das ohne Freigabe hinausgeht.
"""

import uuid

import pytest

from app.domain import voucher as vo
from app.models import Attachment, DocumentRef, VoucherDocument
from app.services import adopt, documents, legal, todo, voucher as svc, voucher_docs
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
    assert rec.document_id and rec.html is None, "(a)"
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


def test_adoption_takes_over_once(db):
    """Bug-Formen: (a) die Übernahme legt beim zweiten Start wieder an; (b) die Datei wird
    kopiert statt übernommen; (c) die Spalte zeigt danach noch auf den Korb."""
    order, step, row, who = _scene(db, direction="out", first=True)
    att = Attachment(token=uuid.uuid4().hex, filename="r.jpg", mime="image/jpeg",
                     data=b"\xff\xd8\xff" + uuid.uuid4().bytes)
    db.add(att)
    db.flush()
    row.original_id = att.id
    legacy = VoucherDocument(voucher_id=row.id, kind=vo.OFFER_DOC, number="X-1",
                             party_id=who.object_id, token=uuid.uuid4().hex,
                             html=f"<p>alt {uuid.uuid4().hex}</p>")
    db.add(legacy)
    db.flush()
    first = adopt.run(db)
    assert first["papers"] >= 1 and first["files"] >= 1
    assert legacy.document_id and legacy.html is None
    assert "<p>alt" in voucher_docs.paper_of(db, legacy)
    assert row.original_id >= adopt.FIRST_OBJECT_ID, "(c)"
    doc = documents.field_document(db, order.object_id, "voucher.original", f"step:{step.id}")
    assert doc is not None and doc.object_id == row.original_id and doc.file_id == att.id, "(b)"
    assert adopt.run(db) == {"papers": 0, "files": 0, "legal": 0}, "(a)"


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
