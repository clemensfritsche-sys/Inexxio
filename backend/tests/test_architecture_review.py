"""Regressions-Guards aus dem Architektur-/Logik-Review 2026-07.

DB-los (wie test_smoke): reine Funktionen mit SimpleNamespace-Fakes + Quelltext-Guards
für Verdrahtung, die sich ohne DB nicht ausführen lässt. Jeder Guard nennt den Bug,
den er verhindert.
"""
import inspect
from decimal import Decimal
from types import SimpleNamespace

import pytest


# ─── 1. Auto-Abweichung: Nachschub-Kinder unterdrücken sie nicht mehr ────────────

def test_open_deviations_filters_reason():
    # Bug: ohne reason-Filter zählte ein offener supply/return-Unterauftrag als «offene
    # Abweichung» → die Auto-Abweichung nach fehlgeschlagener Prüfung wurde übersprungen.
    from app.services.deviation import open_deviations
    src = inspect.getsource(open_deviations)
    assert 'Order.reason == "deviation"' in src


# ─── 2. Kunden-Versand: unverkaufter (Rest-)Bestand bleibt am Lager ──────────────

def _mk_inst(oid, disposition, qty="1", reservations=None):
    return SimpleNamespace(object_id=oid, disposition=disposition,
                           quantity=Decimal(qty), reservations=reservations or None,
                           reserved_quantity=Decimal("0"))


def test_movable_instances_customer_excludes_unsold_remainder(monkeypatch):
    # Bug: der Pflicht-Versand (mode='customer') bewegte nach einem Chargen-Teilverkauf
    # die GANZE Rest-Charge (in_stock) zum Kunden – unverkaufte Ware stand beim Kunden.
    from app.services import movement, subject
    sold = _mk_inst(100000001, "sold", "0")
    in_process = _mk_inst(100000002, "in_process", "3")
    remainder = _mk_inst(100000003, "in_stock", "7")                     # unverkaufter Rest
    covered = _mk_inst(100000004, "in_stock", "2", {"55": "2"})          # ganz für Auftrag 55
    monkeypatch.setattr(subject, "order_instances",
                        lambda db, order: [sold, in_process, remainder, covered])
    order = SimpleNamespace(reason=None, id=55, object_id=100000055)
    step = SimpleNamespace(mode="customer")
    out = movement.movable_instances(None, order, step)
    ids = {i.object_id for i in out}
    assert 100000003 not in ids            # Rest-Charge bleibt am Lager
    assert {100000001, 100000002, 100000004} <= ids


def test_movable_instances_return_takes_sold(monkeypatch):
    from app.services import movement, subject
    sold = _mk_inst(100000001, "sold", "0")
    scrapped = _mk_inst(100000002, "scrapped", "0")
    monkeypatch.setattr(subject, "order_instances", lambda db, order: [sold, scrapped])
    order = SimpleNamespace(reason="return", id=9)
    out = movement.movable_instances(None, order, SimpleNamespace(mode=None))
    assert [i.object_id for i in out] == [100000001]


def test_movement_embed_and_router_share_selection():
    # Embed (Versand-Beleg) und Ausführung müssen dieselbe Auswahlregel nutzen.
    from app.services import orders as orders_svc
    import app.routers.orders as orders_router
    assert "movable_instances" in inspect.getsource(orders_svc._movement_embed)
    assert "movable_instances" in inspect.getsource(orders_router._shipment_instances)


# ─── 3./4. Ersetzen/Wiederkehr verliert keine Konfiguration mehr ──────────────────

def test_copy_steps_copies_document_and_transport_config():
    # Bug: _copy_steps verlor doc_signers/… → «Ersetzen» einer Dokument-Fassung bzw. der
    # nächste Wartungszyklus verloren still die Freigabe-Parteien.
    # (``transport_mode`` am Schritt ist mit Migration 081 entfallen – der Modus lebt am
    # Versand-Beleg und wird zur Laufzeit ermittelt, es gibt am Schritt nichts zu kopieren.)
    from app.services.deactivation import _copy_steps
    src = inspect.getsource(_copy_steps)
    for field in ("doc_signers", "sign_sequential", "doc_audience", "doc_audience_roles",
                  "doc_audience_person_ids", "doc_visibility"):
        assert field in src, f"_copy_steps kopiert «{field}» nicht"


def test_duplicate_article_copies_spec_and_procurement_fields():
    # Bug: der Nachfolger verlor u. a. die Beschaffungsquelle (Freigabe-Gate has_source).
    from app.services.deactivation import duplicate_article
    src = inspect.getsource(duplicate_article)
    # (``fixed_location_*`` ist mit Migration 088 ersatzlos entfallen – ein Artikel ist eine
    #  Gattung, einen Ort hat nur die Instanz.)
    for field in ("is_hazmat", "reorder_target",
                  "procurement_mode", "default_supplier_id", "default_webshop_url"):
        assert field in src, f"duplicate_article kopiert «{field}» nicht"


# ─── 5. Verkauft-durch-diesen-Auftrag = GELIEFERT (Event-Strom) ───────────────────

def test_shortfalls_count_sold_as_delivered():
    from app.services import process
    src = inspect.getsource(process._subject_shortfalls)
    assert "sold_amounts_for_order" in src
    # … aber eine NACH dem Verkauf verschrottete Instanz zählt NICHT als geliefert.
    assert "scrapped" in src


def test_return_restores_sold_quantity_from_events():
    # Bug: eine voll konsumierte Chargen-Instanz (Menge 0, sold) kam als 1 statt der
    # tatsächlich verkauften Menge zurück (stiller Bestandsverlust bei Chargen-Retouren).
    from app.services import process
    src = inspect.getsource(process.return_subjects_to_stock)
    assert "sold_amounts_for_order" in src
    assert "parent_order_id" in src


def test_sold_amounts_skips_scrap_events():
    from app.services import process
    src = inspect.getsource(process.sold_amounts_for_order)
    assert "inventory.decreased" in src
    assert "reason" in src   # Verschrottung (reason='scrapped') ist kein Verkaufs-Abgang


# ─── Shop-Pfad: Pflicht-Versand + Nachschub-Dimensionierung ───────────────────────

def test_shop_ships_via_provisioning_not_a_planted_step():
    """Bug-Historie: Der Shop-Versandschritt war einmal nicht als Begleiter markiert → nach
    der Zahlung dauerhaft «blockiert» (die Ware gilt dann als verkauft, aus Sicht des freien
    Bestands weg) → kein Shop-Auftrag konnte je versendet werden (Migration 074).

    Diese Fehlerklasse ist strukturell weg: der Shop pflanzt **gar keinen** Versandschritt
    mehr. Der Verkauf deklariert seinen Bereitstellungsort (Kunde); ist er bezahlt, legt
    ``provisioning.ensure_provisioning`` die Sendung an – mit festem Subjekt, das per
    Definition keine Fehlmengen-Prüfung durchläuft (``subject.is_fixed_subject``)."""
    from app.domain import event_types
    from app.services.selling import _create_multiline_sale_order

    src = inspect.getsource(_create_multiline_sale_order)
    assert 'step_type="movement"' not in src
    assert "companion" not in src
    # Der Verkauf trägt den Bereitstellungsort, aus dem die Sendung abgeleitet wird.
    assert event_types.provisioning("sale") == event_types.PROV_CUSTOMER


def test_fulfill_intent_sizes_supply_before_selling():
    # Bug: ensure_supply lief NACH finalize_paid → die schon verkaufte Teilmenge zählte
    # als «verloren» und der Nachschub wurde auf die volle Menge dimensioniert.
    from app.services.selling import fulfill_intent
    src = inspect.getsource(fulfill_intent)
    make_branch = src.split("allow_backorder=True", 1)[1]
    assert make_branch.index("ensure_supply") < make_branch.index("_finalize_order_sales")


def test_migration_074_repairs_existing_shop_movements():
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions" / "074_shop_shipping_locked.py"
    src = p.read_text()
    assert "down_revision = '073'" in src
    assert "mode = 'customer'" in src and "locked = true" in src


# ─── 6. Consent: Supersede erst bei wirklich in Kraft getretener Nachfolge ────────

def test_audience_supersede_requires_released_successor_doc():
    from app.services import consent
    assert hasattr(consent, "_superseded_by_released_doc")
    src = inspect.getsource(consent._audience_obligations)
    assert "_superseded_by_released_doc" in src
    assert "ArticleProcessStep.is_active == True" in src   # m5: inaktive Schritte gaten nicht
    chain_src = inspect.getsource(consent._superseded_by_released_doc)
    assert "seen" in chain_src   # zyklensicher


# ─── 7. Unterschriften: keine Deadlocks mehr ─────────────────────────────────────

def test_sequential_rejected_signoff_stays_actionable(monkeypatch):
    # Bug (Sackgasse): nach «Ablehnen» war die Partei selbst nicht mehr handlungsfähig
    # (nur pending zählte) UND die nächste Partei konnte an der Ablehnung vorbeiziehen.
    from app.services import document as doc_svc
    a = SimpleNamespace(id=1, order_index=0, status="rejected")
    b = SimpleNamespace(id=2, order_index=1, status="pending")
    monkeypatch.setattr(doc_svc, "_signoff_step",
                        lambda db, doc: SimpleNamespace(sign_sequential=True))
    monkeypatch.setattr(doc_svc, "signoffs_for", lambda db, doc: [a, b])
    doc_svc._assert_actionable(None, None, a)          # Ablehnende darf erneut handeln
    with pytest.raises(Exception):
        doc_svc._assert_actionable(None, None, b)      # Nächste darf NICHT überholen


def test_issue_rejects_inactive_declared_signer():
    # Bug (Deadlock): ein Signoff für eine deaktivierte Person könnte NIE erfüllt werden;
    # die Schritt-Definition ist nach Freigabe eingefroren (kein Reparatur-Pfad).
    from app.services.document import _create_signoffs
    src = inspect.getsource(_create_signoffs)
    assert "is_active == True" in src and "409" in src


def test_admin_deactivation_blocked_by_open_signoffs():
    import app.routers.admin as admin_router
    src = inspect.getsource(admin_router.deactivate_user)
    assert "DocumentSignoff" in src and "pending" in src


# ─── Nachbestellung/Deckung/Freigabe: Nebenläufigkeit & Steckenbleiber ────────────

def test_stuck_replenishment_does_not_suppress_future_reorders():
    # Bug: eine Nachbestellung mit fehlgeschlagenem Schritt (abgelehnte Beschaffung) blieb
    # für immer «released» und unterdrückte JEDE künftige Auto-Nachbestellung (Stockout).
    from app.services.replenishment import _open_replenishment
    src = inspect.getsource(_open_replenishment)
    assert "failed" in src


def test_replenishment_reuses_supply_can_supply():
    from app.services import replenishment, supply
    assert replenishment._can_supply is supply._can_supply


def test_cover_from_stock_locks_chosen_instances():
    # Bug: der «bestimmte Instanz wählen»-Pfad reservierte ohne Row-Lock (Überverkauf
    # bei zwei gleichzeitigen Deckungen derselben Instanz).
    from app.services.recovery import cover_from_stock
    assert "with_for_update" in inspect.getsource(cover_from_stock)


def test_release_order_locks_against_double_release():
    from app.services.orders import release_order
    src = inspect.getsource(release_order)
    assert "with_for_update" in src


def test_scrap_checks_replenishment_before_completion():
    # Reihenfolge: check_article VOR recompute_completion (sonst Nachbestell-Kette,
    # wenn der Scrap die eigene Nachbestellung abschliesst).
    from app.services.scrap import record_scrap
    src = inspect.getsource(record_scrap)
    assert src.index("check_article(db, art_id") < src.index("process.recompute_completion(db, order)")


def test_revoke_restores_parent_subject_binding():
    # Modul statt Einzelfunktion: die Aufräumarbeit liegt in ``detach_sub_order`` (geteilt mit
    # dem Abbruch eines Unter-Auftrags) – die Fachaussage ist dieselbe.
    from app.services import deviation
    src = inspect.getsource(deviation)
    assert "reserved_for" in src   # Bindung wandert zum Eltern zurück, wenn er reserviert hält
