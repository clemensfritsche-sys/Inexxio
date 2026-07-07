"""Regression-Guards für die drei Änderungen (erp-document-versioning):

1. Öffentliche Rechtsdokumente: der Zeiger am Unternehmen ist ein **Artikel** (nicht eine
   Instanz). ``legal.resolve`` folgt der ``replaced_by_id``-Kette (neueste Fassung mit
   freigegebenem Beleg zuerst) und nimmt die erste freigegebene Instanz.
2. Wiederkehrende Aufträge (Wartung): ``_spawn_recurrence`` klont die auftrags-eigenen
   Prozessschritte auf den Nachfolger und trägt dieselben Subjekt-Instanzen mit.
3. Die Instanz-Ablauf-/Haltbarkeits-Funktion (MHD-Ausbuchung) ist vollständig entfernt.
"""
import inspect

import pytest


def test_legal_pointer_targets_article_via_replacement_chain():
    from app.services import legal

    assert hasattr(legal, "_replacement_chain")
    assert hasattr(legal, "_first_released_document")
    # Zeiger = Artikel-Objektnummer (Doku-Guard).
    assert "Artikel" in (legal.pointer.__doc__ or "")
    resolve_src = inspect.getsource(legal.resolve)
    assert "_replacement_chain" in resolve_src
    assert "reversed" in resolve_src                     # neueste Fassung zuerst
    chain_src = inspect.getsource(legal._replacement_chain)
    assert "replaced_by_id" in chain_src                 # folgt der Ersetzungs-Kette
    doc_src = inspect.getsource(legal._first_released_document)
    assert "in_stock_clauses" in doc_src                 # nur freigegebener Bestand
    assert "released_at" in doc_src                       # FIFO: erste zuerst


def test_recurrence_clones_custom_steps_and_carries_subject():
    from app.services import process

    sig = inspect.signature(process._spawn_recurrence)
    assert "subject_object_ids" in sig.parameters
    src = inspect.getsource(process._spawn_recurrence)
    # (1) eigene Auftrags-Schritte auf den Nachfolger kopieren
    assert "_copy_steps" in src
    assert "src_order_id=order.id" in src and "dst_order_id=child.id" in src
    # (2) gewählte Subjekt-Instanzen auf den Kind-Auftrag pinnen
    assert "subject_of_order_id = child.id" in src

    # recompute_completion erfasst die Subjekte VOR dem Lösen der Bindung und reicht sie durch
    rc = inspect.getsource(process.recompute_completion)
    assert "recurring_subjects" in rc
    assert "_spawn_recurrence(db, order, recurring_subjects)" in rc


def test_instance_expiry_mechanism_removed():
    # 1. Kein expiry-Service mehr
    with pytest.raises(ModuleNotFoundError):
        import app.services.expiry  # noqa: F401

    # 2. Instanz trägt kein Ablaufdatum, Artikel keine Haltbarkeit mehr
    from app.models import Article, Instance
    assert not hasattr(Instance, "expires_at")
    assert not hasattr(Article, "shelf_life_days")

    # 3. Der Wartungs-Sweep meldet nur noch Nachbestellungen (kein 'expired')
    from app.routers.maintenance import SweepResult
    assert "expired" not in SweepResult.model_fields
    assert "reordered" in SweepResult.model_fields

    # 4. release_instances setzt kein Ablaufdatum mehr
    from app.services import process
    assert "set_on_release" not in inspect.getsource(process.release_instances)

    # 5. Meldebestand/Zielbestand (E) bleiben – nur die Haltbarkeit fällt weg
    assert hasattr(Article, "safety_stock")
    assert hasattr(Article, "reorder_target")
