"""Guards für das Dokument-Freigabe-Modul: endliche Freigabe-Parteien (Unterschriften-/
Bestätigungs-Layer), issued↔done-Trennung, sequenzielle Reihenfolge, «Meine Dokumente».
DB-los – reine Funktionen, Schema-Validierung, Struktur/Verdrahtung (wie test_smoke)."""
import inspect
from types import SimpleNamespace

import pytest


# ─── Modell & Schema ──────────────────────────────────────────────────────────

def test_signoff_model_columns():
    from app.models import DocumentSignoff
    for col in ("document_id", "order_id", "signer_object_id", "action", "order_index",
                "status", "signature_url", "reason", "acted_at", "acted_by"):
        assert col in DocumentSignoff.__table__.columns


def test_document_issued_separate_from_done():
    # ZWEI Achsen: 'issued' (Inhalt eingefroren) getrennt von 'done' (alle Parteien signiert).
    from app.models import Document
    assert "issued" in Document.__table__.columns
    assert "done" in Document.__table__.columns


def test_step_declares_signers_and_audience():
    from app.models import ArticleProcessStep
    for col in ("doc_signers", "sign_sequential", "doc_audience",
                "doc_audience_roles", "doc_audience_person_ids", "doc_visibility"):
        assert col in ArticleProcessStep.__table__.columns


def test_doc_signer_action_validation():
    from app.schemas.article_process_step import DocSigner
    assert DocSigner(signer_object_id=100000001, action="confirm").action == "confirm"
    assert DocSigner(signer_object_id=100000001, action="sign").action == "sign"
    with pytest.raises(Exception):
        DocSigner(signer_object_id=100000001, action="stamp")


def test_normalize_doc_signers_dedupes_keeps_order():
    from app.schemas.article_process_step import normalize_doc_signers
    out = normalize_doc_signers([
        {"signer_object_id": 100000003, "action": "sign"},
        {"signer_object_id": 100000001, "action": "confirm"},
        {"signer_object_id": 100000003, "action": "sign"},   # Dublette
    ])
    assert [s["signer_object_id"] for s in out] == [100000003, 100000001]
    assert normalize_doc_signers([]) is None


def test_signoff_action_schema_validation():
    from app.schemas.document import SignoffAction
    for a in ("confirm", "sign", "reject", "withdraw"):
        assert SignoffAction(action=a).action == a
    with pytest.raises(Exception):
        SignoffAction(action="approve")


def test_audience_visibility_validation():
    from app.schemas.article_process_step import ArticleProcessStepCreate
    # 'none'/'' → None (kein offenes Publikum); ungültig → Fehler.
    assert ArticleProcessStepCreate(step_type="document", doc_audience="none").doc_audience is None
    assert ArticleProcessStepCreate(step_type="document", doc_audience="all").doc_audience == "all"
    with pytest.raises(Exception):
        ArticleProcessStepCreate(step_type="document", doc_audience="everyone")
    with pytest.raises(Exception):
        ArticleProcessStepCreate(step_type="document", doc_visibility="secret")


# ─── Freigabe-Logik (rein) ────────────────────────────────────────────────────

def test_signoffs_complete_pure():
    from app.services.document import signoffs_complete
    assert signoffs_complete([]) is True   # ohne Parteien: sofort freigegeben (rückwärtskompatibel)
    assert signoffs_complete([SimpleNamespace(status="signed")]) is True
    assert signoffs_complete([SimpleNamespace(status="signed"), SimpleNamespace(status="pending")]) is False
    assert signoffs_complete([SimpleNamespace(status="rejected")]) is False


def test_fact_status_document_reads_done():
    # Der Prozessschritt bleibt AKTIV (nicht done), solange Parteien signieren – erst wenn
    # 'done' (alle signiert) gesetzt ist, gilt der Schritt als erledigt (unveränderte Engine).
    from app.services.process import _fact_status
    assert _fact_status("document", SimpleNamespace(done=True)) == "done"
    assert _fact_status("document", SimpleNamespace(done=False)) == "open"
    assert _fact_status("document", None) == "open"


def test_act_on_signoff_only_named_party():
    # Nur die benannte Person (Objektnummer-Abgleich) darf handeln – Kernaussage im Quelltext.
    from app.services import document
    src = inspect.getsource(document.act_on_signoff)
    assert "user.object_id != signoff.signer_object_id" in src
    assert "Nur die benannte Person" in src


def test_sequential_enforced_in_source():
    from app.services import document
    src = inspect.getsource(document._assert_actionable)
    assert "sign_sequential" in src
    assert "order_index" in src


def test_issue_creates_signoffs_and_defers_completion():
    from app.services import document
    src = inspect.getsource(document.record_document)
    assert "doc.issued = True" in src
    assert "_create_signoffs" in src
    assert "_maybe_complete" in src   # ohne Parteien sofort done, sonst aufgeschoben


# ─── Verdrahtung (Endpoints) ──────────────────────────────────────────────────

def test_audience_scope_pure():
    # Offenes Anerkennungs-Publikum eines Dokument-Schritts (all / roles / persons).
    from app.services.consent import _in_audience
    all_step = SimpleNamespace(doc_audience="all", doc_audience_roles=None, doc_audience_person_ids=None)
    assert _in_audience(SimpleNamespace(role="supplier", object_id=1), all_step) is True
    roles_step = SimpleNamespace(doc_audience="roles", doc_audience_roles=["supplier"], doc_audience_person_ids=None)
    assert _in_audience(SimpleNamespace(role="supplier", object_id=1), roles_step) is True
    assert _in_audience(SimpleNamespace(role="customer", object_id=1), roles_step) is False
    persons_step = SimpleNamespace(doc_audience="persons", doc_audience_roles=None, doc_audience_person_ids=[100000009])
    assert _in_audience(SimpleNamespace(role="customer", object_id=100000009), persons_step) is True
    assert _in_audience(SimpleNamespace(role="customer", object_id=100000010), persons_step) is False
    none_step = SimpleNamespace(doc_audience=None, doc_audience_roles=None, doc_audience_person_ids=None)
    assert _in_audience(SimpleNamespace(role="admin", object_id=1), none_step) is False


def test_audience_supersede_and_dedupe_in_source():
    # Kanonisch (Q2): ein ersetzter Artikel wird übersprungen (Nachfolger fordert neue Anerkennung);
    # gegen die Rechtsdokument-Zeiger wird per Objektnummer dedupliziert.
    from app.services import consent
    src = inspect.getsource(consent._audience_obligations)
    assert "replaced_by_id is not None" in src
    assert "continue" in src
    ack_src = inspect.getsource(consent.acknowledge)
    assert "AUDIENCE_KIND" in ack_src


def test_pdf_signoff_block_pure():
    # Freigabe-Block im PDF (DocuSign-Prinzip): Bild als data-URI, sonst Bestätigt/ausstehend.
    from app.services.document_render import _signoffs_html
    assert _signoffs_html(None) == ""
    assert _signoffs_html([]) == ""
    html = _signoffs_html([
        {"name": "Anna", "action": "sign", "status": "signed", "image": "data:image/png;base64,AAA", "acted_at": None},
        {"name": "Bob", "action": "confirm", "status": "pending", "image": None, "acted_at": None},
    ])
    assert "data:image/png;base64,AAA" in html and "Anna" in html
    assert "ausstehend" in html and "Freigaben" in html


def test_pdf_render_accepts_signoffs_param():
    import inspect as _inspect
    from app.services import document_render
    from app.routers import documents as docs_router
    assert "signoffs" in _inspect.signature(document_render.render_pdf).parameters
    src = _inspect.getsource(docs_router.get_document_pdf)
    assert "signoffs=" in src


def test_signature_transparency_flattened_to_white_not_black():
    # Regression «schwarzer Balken»: ein transparentes PNG (dunkle Striche auf transparent,
    # wie die gezeichnete Unterschrift) darf NICHT komplett schwarz werden.
    from PIL import Image
    from app.services.attachments import _flatten_to_rgb
    img = Image.new("RGBA", (60, 20), (0, 0, 0, 0))     # voll transparent
    img.putpixel((30, 10), (15, 23, 42, 255))            # ein dunkler Strich-Pixel
    rgb = _flatten_to_rgb(img)
    assert rgb.mode == "RGB"
    assert rgb.getpixel((0, 0)) == (255, 255, 255)       # transparenter Grund → WEISS (nicht schwarz)
    assert rgb.getpixel((30, 10))[0] < 60                # der Strich bleibt dunkel
    # Ein Bild ohne Alpha bleibt unverändert konvertiert.
    assert _flatten_to_rgb(Image.new("RGB", (4, 4), (200, 100, 50))).getpixel((0, 0)) == (200, 100, 50)


def test_object_document_carries_signoffs():
    # Das freigegebene Dokument (Reiter «Dokumente» / Instanz) trägt den Freigabe-Layer,
    # damit die Unterschrift auch dort (nicht nur im Auftrags-Panel) sichtbar ist.
    from app.schemas.document_file import ObjectDocument
    assert "signoffs" in ObjectDocument.model_fields
    import inspect as _inspect
    from app.routers import document_files
    assert "signoffs=document_svc.signoff_views" in _inspect.getsource(document_files._gen_entry)


def test_passkey_name_auto_defaulted():
    # Passkey-Name ist optional – ohne Eingabe wird serverseitig automatisch vergeben.
    import inspect as _inspect
    from app.services import passkey
    src = _inspect.getsource(passkey.complete_registration)
    assert 'f"Passkey {n + 1}"' in src


def test_user_document_overview_wired():
    # PRIMÄRE Sicht am ERP-Benutzer-Datensatz: offene Freigaben + Anerkennungen + Erledigt.
    from app.services import consent
    assert hasattr(consent, "user_document_overview")
    from app.routers import consent as consent_router
    assert "/api/v1/consent/user/{user_object_id}/documents" in {r.path for r in consent_router.router.routes}
    from app.schemas.consent import UserDocumentOverview
    for f in ("signoffs", "acks", "history"):
        assert f in UserDocumentOverview.model_fields


def test_my_history_endpoint_wired():
    # «Meine Dokumente → Erledigt»: bereits unterschriebene/anerkannte Dokumente bleiben sichtbar.
    from app.services import consent
    assert hasattr(consent, "my_document_history")
    from app.routers import consent as consent_router
    assert "/api/v1/consent/my-history" in {r.path for r in consent_router.router.routes}
    from app.schemas.consent import MyHistoryDocument
    for f in ("kind", "title", "object_number", "acted_at", "label", "content"):
        assert f in MyHistoryDocument.model_fields


def test_signoff_endpoints_wired():
    from app.routers import orders, consent as consent_router
    order_paths = {r.path for r in orders.router.routes}
    assert "/api/v1/erp/orders/{object_id}/document/signoff/{signoff_id}" in order_paths
    assert "/api/v1/erp/orders/{object_id}/document/withdraw" in order_paths
    consent_paths = {r.path for r in consent_router.router.routes}
    assert "/api/v1/consent/my-documents" in consent_paths
    assert "/api/v1/consent/signoffs/{signoff_id}" in consent_paths
