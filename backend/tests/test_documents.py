"""►►► **Dokumente – die Regeln, gegen ihre Fehlerform geprüft.** ◄◄◄

Freigeben (Regel 1–3), Erscheinen (4), Pflichtfeld (6), Löschen (8), Zugriff (9), Suche.
Jeder Wächter steht neben dem Fall, der ihn brechen würde.
"""

import io
import json
import random
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.auth import require_employee
from app.core.database import get_db
from app.domain import documents as dd
from app.domain import statuses as st
from app.models import Attachment, AuditLog, Document, Order, UserProfile
from app.routers import attachments as att_router
from app.routers import documents as router
from app.services import access, documents as docs, objects

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def _person(db, role="employee") -> UserProfile:
    oid = random.randint(900_000_000, 999_999_999)
    u = UserProfile(firebase_uid=f"uid-{oid}", email=f"p{oid}@x.ch", role=role,
                    object_id=oid, first_name="Lea", last_name=f"M{oid}")
    db.add(u)
    db.flush()
    return u


def _png(color=(200, 10, 10)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 60), color).save(buf, format="PNG")
    return buf.getvalue()


def _file(db, actor, raw=None, refs=(), **kw):
    return docs.file(db, raw=raw or (PDF + str(random.random()).encode()), filename="a.pdf",
                     mime="application/pdf", art=kw.get("art", "Lieferschein"),
                     name=kw.get("name", "Hydro AG LS 1"), source="file",
                     refs=list(refs), actor=actor)


@pytest.fixture
def world(db):
    db.commit = db.flush            # zurückrollbar bleiben
    staff = _person(db)
    app = FastAPI()
    app.include_router(router.router)
    app.include_router(att_router.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_employee] = lambda: staff
    return SimpleNamespace(db=db, staff=staff, client=TestClient(app), app=app)


# ─── Regel 1–3: Freigeben ──────────────────────────────────────────────────────

def test_release_creates_number_file_refs_and_log(world):
    db, staff = world.db, world.staff
    person = _person(db, "user")
    doc, existed = _file(db, staff, refs=[docs.RefIn(person.object_id)])
    assert not existed and doc.object_id and doc.file_id
    assert objects.resolve_object_type(db, doc.object_id) == "document"
    assert [r.object_id for r in docs.refs_of(db, [doc.id])[doc.id]] == [person.object_id]
    assert db.query(AuditLog).filter(AuditLog.object_id == doc.object_id,
                                     AuditLog.field_name == "freigegeben").count() == 1
    assert docs.status_of(doc, []) == st.FREIGEGEBEN


def test_same_file_twice_is_the_same_document(world):
    raw = PDF + b"same"
    first, _ = _file(world.db, world.staff, raw=raw)
    again, existed = _file(world.db, world.staff, raw=raw, art="Anderes")
    assert existed and again.id == first.id
    assert world.db.query(Document).filter(Document.sha256 == first.sha256).count() == 1


def test_release_needs_art_and_name(world):
    with pytest.raises(HTTPException) as e:
        _file(world.db, world.staff, art=" ", name="x")
    assert e.value.status_code == 400


def test_unknown_reference_is_refused(world):
    with pytest.raises(HTTPException):
        _file(world.db, world.staff, refs=[docs.RefIn(999_999_998)])


def test_scanned_pages_become_one_pdf(world):
    r = world.client.post("/api/v1/erp/documents", data={
        "art": "Lieferschein", "name": "LS 2", "source": "scan", "refs": "[]"},
        files=[("files", ("1.png", _png(), "image/png")),
               ("files", ("2.png", _png((1, 2, 3)), "image/png"))])
    assert r.status_code == 201, r.text
    d = r.json()["document"]
    assert d["mime"] == "application/pdf" and d["pages"] == 2 and d["source"] == "scan"
    assert d["preview_url"].endswith("/preview")
    assert world.client.get(d["preview_url"]).headers["content-type"] == "image/png"


# ─── Regel 4: Erscheinen ───────────────────────────────────────────────────────

def test_document_appears_exactly_where_its_reference_points(world):
    db, staff = world.db, world.staff
    a, b = _person(db, "user"), _person(db, "user")
    doc, _ = _file(db, staff, refs=[docs.RefIn(a.object_id)])
    assert [d.id for d in docs.shown_on(db, a.object_id, staff)] == [doc.id]
    assert docs.shown_on(db, b.object_id, staff) == []
    tiles = world.client.get(f"/api/v1/erp/documents/of/{a.object_id}").json()
    assert [t["object_id"] for t in tiles] == [doc.object_id]


# ─── Regel 6: Pflichtfeld ──────────────────────────────────────────────────────

def test_mandatory_field_is_changed_never_emptied(world):
    db, staff = world.db, world.staff
    target = _person(db, "user")
    first, _ = _file(db, staff)
    second, _ = _file(db, staff)
    docs.set_field(db, document_object_id=first.object_id, object_id=target.object_id,
                   part=None, field="company.agb", actor=staff)
    (ref,) = docs.refs_of(db, [first.id])[first.id]
    with pytest.raises(HTTPException) as e:
        docs.detach(db, first, ref.id, staff)
    assert e.value.status_code == 409
    docs.set_field(db, document_object_id=second.object_id, object_id=target.object_id,
                   part=None, field="company.agb", actor=staff)
    assert docs.field_document(db, target.object_id, "company.agb").id == second.id
    assert docs.refs_of(db, [first.id])[first.id] == []      # das alte hängt nirgends mehr


# ─── Regel 8: Löschen ──────────────────────────────────────────────────────────

def test_only_what_hangs_nowhere_can_be_deleted(world):
    db, staff = world.db, world.staff
    person = _person(db, "user")
    doc, _ = _file(db, staff, refs=[docs.RefIn(person.object_id)])
    assert docs.delete_problem(db, doc)
    with pytest.raises(HTTPException) as e:
        docs.delete(db, doc, "weg", staff)
    assert e.value.status_code == 409
    (ref,) = docs.refs_of(db, [doc.id])[doc.id]
    docs.detach(db, doc, ref.id, staff)
    file_id = doc.file_id
    docs.delete(db, doc, "Bewerbung abgeschlossen", staff)
    assert doc.file_id is None and doc.sha256 is None and doc.deleted_at
    assert db.query(Attachment).filter(Attachment.id == file_id).first() is None
    assert docs.status_of(doc, []) == st.GELOESCHT
    assert (doc.art, doc.name, doc.delete_reason) == ("Lieferschein", "Hydro AG LS 1",
                                                     "Bewerbung abgeschlossen")


def test_deleted_file_can_be_released_again(world):
    raw = PDF + b"again"
    doc, _ = _file(world.db, world.staff, raw=raw)
    docs.delete(world.db, doc, "falsch", world.staff)
    again, existed = _file(world.db, world.staff, raw=raw)
    assert not existed and again.id != doc.id


# ─── Regel 9: Zugriff ──────────────────────────────────────────────────────────

def test_a_private_part_is_seen_only_by_the_person_and_the_admin(world):
    db, staff = world.db, world.staff
    owner, colleague, admin = _person(db), _person(db), _person(db, "admin")
    doc, _ = _file(db, owner)
    docs.set_field(db, document_object_id=doc.object_id, object_id=owner.object_id,
                   part="time:42", field="time.proof", actor=owner)
    refs = docs.refs_of(db, [doc.id])[doc.id]
    assert access.may(owner, refs) and access.may(admin, refs)
    assert not access.may(colleague, refs)
    q = db.query(Document).filter(Document.id == doc.id)
    assert access.visible(q, colleague).count() == 0
    assert access.visible(q, owner).count() == 1
    assert access.visible(q, admin).count() == 1
    with pytest.raises(HTTPException) as e:
        docs.readable(db, doc.object_id, colleague)
    assert e.value.status_code == 404


def test_customers_see_no_documents_in_the_erp(world):
    customer = _person(world.db, "user")
    doc, _ = _file(world.db, world.staff)
    assert not access.may(customer, [])
    assert access.visible(world.db.query(Document).filter(Document.id == doc.id),
                          customer).count() == 0


# ─── Suche ────────────────────────────────────────────────────────────────────

def test_search_finds_number_name_and_read_text(world):
    db, staff = world.db, world.staff
    doc, _ = _file(db, staff, name="Stahl Gerlafingen Charge 0921")
    doc.text = "Abnahmeprüfzeugnis 3.1 Zahnradpumpe G2-16"
    doc.keywords = "certificate steel"
    db.flush()
    for q in (str(doc.object_id), "gerlafingen", "zahnradpumpe", "steel"):
        assert doc.id in [d.id for d in docs.search(db, staff, q)], q
    assert docs.snippet(doc, "zahnradpumpe")


# ─── Die Routen ───────────────────────────────────────────────────────────────

def test_routes_release_reference_and_delete(world):
    db, staff = world.db, world.staff
    order_person = _person(db, "user")
    r = world.client.post("/api/v1/erp/documents", data={
        "art": "Vertrag", "name": "Wartung HK-12", "source": "file",
        "refs": json.dumps([{"object_id": order_person.object_id}])},
        files=[("files", ("v.pdf", PDF + b"route", "application/pdf"))])
    assert r.status_code == 201, r.text
    d = r.json()["document"]
    assert d["refs"][0]["label"].startswith("Benutzer · ") and d["delete_problem"]
    oid = d["object_id"]
    r = world.client.delete(f"/api/v1/erp/documents/{oid}/refs/{d['refs'][0]['id']}")
    assert r.status_code == 200 and r.json()["delete_problem"] is None
    r = world.client.post(f"/api/v1/erp/documents/{oid}/delete", json={"reason": "falsch"})
    assert r.status_code == 200 and r.json()["status"] == st.GELOESCHT
    assert r.json()["file_url"] is None


def test_uploaded_html_is_never_served_with_scripts(world):
    doc, _ = docs.file(world.db, raw=b"<script>alert(1)</script>", filename="x.html",
                       mime="text/html", art="Notiz", name="x", source="file", refs=[],
                       actor=world.staff)
    r = world.client.get(docs.file_url(world.db, doc))
    assert r.headers.get("content-security-policy") == "sandbox"


def test_part_and_field_vocabulary_is_closed():
    assert dd.PART.match("time:12") and dd.PART.match("unit:100000027-3")
    assert not dd.PART.match("foo:1") and not dd.PART.match("time:")
    assert all("." in k for k in dd.FIELDS)
