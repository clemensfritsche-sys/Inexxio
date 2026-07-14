"""Regressions-Guards für die Folgethemen-Umsetzung des Architektur-Reviews 2026-07
(docs/review-2026-07.md §3 – alle Punkte ausser «fehlgeschlagener Schritt ist terminal»).

DB-los (wie test_smoke): reine Funktionen mit SimpleNamespace-Fakes + Quelltext-Guards."""
import inspect
from decimal import Decimal
from types import SimpleNamespace

import pytest


# ─── CheckoutIntent-Reaper ────────────────────────────────────────────────────────

def test_intent_reaper_exists_and_uses_cancel_path():
    from app.services.sales import reap_stale_intents
    src = inspect.getsource(reap_stale_intents)
    assert "cancel_intent" in src                 # regulärer Storno-Pfad (löst Reservierungen)
    assert 'status == "pending"' in src           # nur unbezahlte
    assert "with_for_update" in src               # kein Race mit spätem Webhook


def test_sweep_reaps_intents():
    import app.routers.maintenance as m
    assert "reaped_intents" in m.SweepResult.model_fields
    assert "reap_stale_intents" in inspect.getsource(m.run_sweep)


# ─── Benutzer-Identität: deaktiviert = gesperrt ───────────────────────────────────

def test_deactivated_user_is_locked_out_not_reprovisioned():
    # Bug: ein deaktivierter Benutzer bekam beim Re-Login still ein NEUES Profil (neue
    # Objektnummer) – alle Referenzen der alten Identität verwaisten.
    from app.core.auth import _resolve_user
    src = inspect.getsource(_resolve_user)
    assert "403" in src and "deaktiviert" in src
    # Suche schliesst inaktive ein (sonst würde der Inaktive nie gefunden → Neuanlage).
    assert "is_active == True" not in src.split("def _resolve_user", 1)[-1].split("_create_user")[0] \
        or "user.is_active" in src


def test_admin_can_reactivate_user():
    import app.routers.admin as admin_router
    assert hasattr(admin_router, "reactivate_user")
    src = inspect.getsource(admin_router.reactivate_user)
    assert "is_active = True" in src and "log_audit" in src


# ─── Consent-Gate serverseitig ────────────────────────────────────────────────────

def test_assert_acknowledged_raises_403():
    from app.services.consent import assert_acknowledged
    src = inspect.getsource(assert_acknowledged)
    assert "pending_documents" in src and "403" in src


def test_consent_gate_wired_on_critical_routes():
    import app.routers.orders as orders_router
    import app.routers.shop as shop_router
    shop_src = inspect.getsource(shop_router)
    assert shop_src.count("assert_acknowledged") >= 2      # Checkout + Retoure-Anfrage
    # Lieferanten-Gate an der Beschaffung (nur Rolle supplier – Personal bleibt frei).
    purch = inspect.getsource(orders_router.update_order_purchase)
    assert "assert_acknowledged" in purch and '"supplier"' in purch


# ─── Parteien-Substitution ───────────────────────────────────────────────────────

def test_signer_substitution_service_and_endpoint():
    from app.services.document import substitute_signer
    src = inspect.getsource(substitute_signer)
    assert '"pending", "rejected"' in src          # nur offene Freigaben substituierbar
    assert "is_active == True" in src              # neue Partei muss aktiver Benutzer sein
    assert 'status = "pending"' in src             # Ablehnung der alten gilt nicht für die neue
    import app.routers.orders as orders_router
    assert hasattr(orders_router, "substitute_order_document_signer")


def test_signer_substitution_schema():
    from app.schemas.document import SignerSubstitution
    s = SignerSubstitution(old_signer_object_id=100000001, new_signer_object_id=100000002)
    assert s.step_id is None


# ─── doc_visibility als Lese-Zugriffsfilter ──────────────────────────────────────

def _vis_check(monkeypatch, viewer, vis, signer_ids=(), audience=None):
    from app.services import document as doc_svc, orders as orders_svc
    monkeypatch.setattr(doc_svc, "signoffs_for",
                        lambda db, doc: [SimpleNamespace(signer_object_id=i) for i in signer_ids])
    step = SimpleNamespace(doc_visibility=vis, doc_audience=audience,
                           doc_audience_roles=["supplier"], doc_audience_person_ids=[])
    return orders_svc._doc_content_visible(None, step, SimpleNamespace(id=1), viewer)


def test_doc_visibility_enforced(monkeypatch):
    staff = SimpleNamespace(role="employee", object_id=100000001)
    supplier = SimpleNamespace(role="supplier", object_id=100000002)
    assert _vis_check(monkeypatch, staff, "internal") is True          # Personal immer
    assert _vis_check(monkeypatch, supplier, "internal") is False      # intern → verborgen
    assert _vis_check(monkeypatch, supplier, "public") is True
    # Benannte Partei liest IMMER (man kann nicht unterschreiben, was man nicht sieht).
    assert _vis_check(monkeypatch, supplier, "internal", signer_ids=(100000002,)) is True
    # parties → Anerkennungs-Publikum (Rolle supplier deklariert)
    assert _vis_check(monkeypatch, supplier, "parties", audience="roles") is True


def test_non_staff_order_endpoints_pass_viewer():
    import app.routers.orders as orders_router
    for fn in (orders_router.get_order, orders_router.update_order_purchase,
               orders_router.act_order_document_signoff):
        assert "viewer=" in inspect.getsource(fn)


# ─── Produktabo: Auto-Fulfillment je Zyklus ──────────────────────────────────────

def test_invoice_paid_fulfills_product_subscription_cycle():
    from app.services.payments.stripe_provider import StripeProvider
    src = inspect.getsource(StripeProvider._on_invoice_paid)
    assert "recurrence_chain" in src               # aktueller Träger der Abo-Kette
    assert 'kind == "product"' in src              # Nutzungsabo liefert nichts
    assert 'status == "draft"' in src              # idempotent (Zyklus 1/Retry trifft released)
    assert "release_order" in src and "finalize_paid" in src
    assert "ensure_supply" in src                  # make-Artikel: Fehlmenge → Nachschub


# ─── Teilverkaufte Charge: Slice-Retoure/-Restock ────────────────────────────────

def test_return_subjects_include_batch_slices(monkeypatch):
    # Ein Teilmengen-Verkauf (Charge besteht weiter, disposition in_stock) ist retournierbar:
    # das Slice-Subjekt kommt aus dem Event-Strom, nicht aus disposition='sold'.
    from app.services import customer_returns as cr, process
    batch = SimpleNamespace(object_id=100000010, disposition="in_stock")
    sold = SimpleNamespace(object_id=100000011, disposition="sold")
    scrapped = SimpleNamespace(object_id=100000012, disposition="scrapped")
    monkeypatch.setattr(cr, "order_instances", lambda db, order: [batch, sold, scrapped])
    monkeypatch.setattr(process, "sold_amounts_for_order",
                        lambda db, oid: {100000010: Decimal("3"), 100000011: Decimal("1"),
                                         100000012: Decimal("2")})
    subs = cr._return_subjects(None, SimpleNamespace(object_id=100000099))
    ids = {i.object_id for i in subs}
    assert ids == {100000010, 100000011}           # Slice + sold; verschrottet nie


def test_slice_restock_is_movement_gated_and_idempotent():
    from app.services import process
    src = inspect.getsource(process.return_subjects_to_stock)
    assert "movement_done" in src                  # erst nach quittierter Rückgabe-Bewegung
    assert "_already_restocked" in src             # Event-Marker (Abschluss ruft erneut)
    assert "to_qty(inst.quantity) + back" in src   # mengengenau in die Original-Charge


def test_return_movement_relocates_only_sold():
    # Die Rest-Charge eines Slice-Verkaufs wird bei der Retoure NICHT umgelagert.
    from app.services.movement import movable_instances
    src = inspect.getsource(movable_instances)
    assert '== "sold"' in src.split("is_return(order)", 1)[1].split("customer")[0]


# ─── legal_ack_config entfernt + Kleinigkeiten ───────────────────────────────────

def test_legal_ack_config_removed():
    from app.models import CompanySettings
    assert "legal_ack_config" not in CompanySettings.__table__.columns
    from app.services import consent
    assert not hasattr(consent, "_config")
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions" / "075_drop_legal_ack_config.py"
    assert "drop_column" in p.read_text()


def test_price_pin_never_commits_foreign_changes():
    from app.services.pricing import _pinned_net
    src = inspect.getsource(_pinned_net)
    assert "db.flush()" in src and "others" in src


def test_snapshotless_multiline_refund_refused():
    # Alt-Beleg ohne Positions-Snapshot bei Mehrpositionen-Kauf: Anteil nicht bestimmbar →
    # 409 statt Erstattung des GANZEN PaymentIntents (Überzahlung).
    from app.services.payments.stripe_provider import StripeProvider
    src = inspect.getsource(StripeProvider.refund)
    assert "sibling" in src and "409" in src
