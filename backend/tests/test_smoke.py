"""Smoke tests — verify the app can be imported and key modules are wired up."""
import pytest

from app.core.config import get_settings
from app.routers import (
    admin, article_process, articles, auth, contact, erp, health, orders,
)


def test_settings_loads():
    s = get_settings()
    assert s.app_name


def test_routers_importable():
    assert hasattr(admin, "router")
    assert hasattr(articles, "router")
    assert hasattr(article_process, "router")
    assert hasattr(orders, "router")
    assert hasattr(auth, "router")
    assert hasattr(contact, "router")
    assert hasattr(erp, "router")
    assert hasattr(health, "router")


def test_models_exposed_from_package():
    """Models are re-exported from the package regardless of their file."""
    from app.models import (
        Article, ArticleProcessStep, AuditLog, CompanySettings,
        Order, PurchaseOrder, UserProfile,
    )

    assert UserProfile.__tablename__ == "user_profiles"
    assert Article.__tablename__ == "articles"
    assert ArticleProcessStep.__tablename__ == "article_process_steps"
    assert Order.__tablename__ == "orders"
    assert PurchaseOrder.__tablename__ == "purchase_orders"
    assert AuditLog.__tablename__ == "audit_log"
    assert CompanySettings.__tablename__ == "company_settings"
    # Das nie verdrahtete Notification-Modell ist entfernt (Cleanup 2026-07).
    import app.models as models_pkg
    assert not hasattr(models_pkg, "Notification")


def test_auth_helpers_decoupled():
    """Auth verification, provisioning and sync are separate, callable units."""
    from app.core import auth

    assert callable(auth._verify_firebase_token)
    assert callable(auth._resolve_user)
    assert callable(auth._sync_user_profile)
    assert callable(auth.get_current_user)


def test_self_update_schema_excludes_employment_fields():
    """Regression guard for the mass-assignment fix."""
    from app.schemas.admin import UserProfileUpdate

    fields = UserProfileUpdate.model_fields.keys()
    for forbidden in ("role", "department", "job_title", "employment_start_date", "weekly_hours"):
        assert forbidden not in fields


def test_article_create_validation():
    """Stammdaten-Pflichtfelder werden validiert (Grösse aufsteigend, Gewicht > 0)."""
    from decimal import Decimal

    from app.schemas.article import ArticleCreate

    ok = ArticleCreate(
        name="  Welle  ", unit="Stk", serialization="unit",
        size="3 X 40 x 600", weight_kg=Decimal("2.5"),
    )
    assert ok.name == "Welle"          # getrimmt
    assert ok.size == "3x40x600"       # normalisiert

    with pytest.raises(ValueError):    # Grösse absteigend
        ArticleCreate(name="x", unit="mm", serialization="batch", size="600x40x3", weight_kg=Decimal("1"))
    with pytest.raises(ValueError):    # Gewicht 0
        ArticleCreate(name="x", unit="mm", serialization="batch", size="1x2", weight_kg=Decimal("0"))
    with pytest.raises(ValueError):    # > 3 Nachkommastellen
        ArticleCreate(name="x", unit="mm", serialization="batch", size="1x2", weight_kg=Decimal("1.2345"))
    with pytest.raises(ValueError):    # ungültige Einheit
        ArticleCreate(name="x", unit="xx", serialization="unit", size="1x2", weight_kg=Decimal("1"))


def test_object_id_allocator_shared_across_types():
    """Der Nummernkreis ist objekttyp-übergreifend (UserProfile + Article)."""
    from app.services import objects

    assert objects.OBJ_ID_START == 100_000_001
    assert objects.UserProfile.object_id in objects._OBJECT_ID_COLUMNS
    assert objects.Article.object_id in objects._OBJECT_ID_COLUMNS
    assert objects.Order.object_id in objects._OBJECT_ID_COLUMNS
    assert objects.Instance.object_id in objects._OBJECT_ID_COLUMNS
    # Bestellungen laufen unter der Auftragsnummer → KEINE eigene Objektnummer
    assert not hasattr(objects, "PurchaseOrder")


def test_landed_unit_cost_calculation():
    """Einstandspreis netto/Stück = Bestellsumme ÷ Menge."""
    from decimal import Decimal

    from app.models import PurchaseOrder
    from app.services.purchase import compute_landed_unit_cost

    po = PurchaseOrder(order_id=1, article_id=1, quantity=5, order_total=Decimal("75.00"))
    assert compute_landed_unit_cost(po) == Decimal("15.0000")  # 75 / 5

    po.order_total = None  # ohne Bestellsumme kein Preis
    assert compute_landed_unit_cost(po) is None


def test_supplier_fields_mandatory_always_included():
    """Pflicht-Stammdaten sind für den Lieferanten immer sichtbar."""
    from app.services.article_fields import MANDATORY_FIELD_KEYS, normalize_shared_fields

    assert set(normalize_shared_fields(None)) >= set(MANDATORY_FIELD_KEYS)
    assert set(normalize_shared_fields([])) >= set(MANDATORY_FIELD_KEYS)
    out = normalize_shared_fields(["unknown_key", "name"])
    assert "unknown_key" not in out                      # unbekannt verworfen
    assert set(MANDATORY_FIELD_KEYS) <= set(out)         # Pflicht erzwungen


def test_purchase_responsibility_separation():
    """Besteller (Mitarbeiter) kann selbst beschaffen (offerieren UND bestellen); der
    zugewiesene Lieferant kann zusätzlich selbst offerieren; nur Bestellen/Annehmen bleibt
    dem Besteller vorbehalten."""
    from app.models import PurchaseOrder, UserProfile
    from app.services.purchase import _transition_allowed

    staff = UserProfile(role="employee", id=1)
    supplier = UserProfile(role="supplier", id=2)
    po = PurchaseOrder(order_id=1, article_id=1, quantity=1, mode="supplier", supplier_id=2)

    # Offerte: Lieferant ODER Besteller (Selbst-Beschaffung). Bestellen/Annehmen: nur Besteller.
    assert _transition_allowed(po, "quoted", supplier) is True
    assert _transition_allowed(po, "quoted", staff) is True
    assert _transition_allowed(po, "ordered", staff) is True
    assert _transition_allowed(po, "ordered", supplier) is False
    assert _transition_allowed(po, "rejected", staff) is True
    assert _transition_allowed(po, "received", staff) is True
    assert _transition_allowed(po, "received", supplier) is False

    # Webshop: Mitarbeiter macht alles, keine Lieferanten-Offerte
    po.mode = "webshop"
    po.supplier_id = None
    assert _transition_allowed(po, "ordered", staff) is True
    assert _transition_allowed(po, "received", staff) is True


def test_purchase_order_transitions_map():
    """Verschlankter Ablauf: requested→quoted→ordered→received (+rejected)."""
    from app.services.purchase import _FROM

    assert _FROM["quoted"] == {"requested"}
    assert _FROM["ordered"] == {"quoted", "requested"}   # supplier + webshop
    assert _FROM["received"] == {"ordered"}
    assert "confirmed" not in _FROM and "approved" not in _FROM


def test_purchase_order_update_schema_validates_status():
    """Ungültiger Zielstatus wird abgelehnt; gültiger akzeptiert."""
    from decimal import Decimal

    import pytest

    from app.schemas.purchase_order import PurchaseOrderUpdate

    assert PurchaseOrderUpdate(status="ordered").status == "ordered"
    with pytest.raises(ValueError):
        PurchaseOrderUpdate(status="approved")  # altes Modell – nicht mehr erlaubt
    with pytest.raises(ValueError):
        PurchaseOrderUpdate(order_total=Decimal("-1"))


def test_purchase_step_source_is_optional_override():
    """Die Bezugsquelle gehört zur Artikel-Spezifikation; der Beschaffungs-Schritt ERBT sie
    und braucht daher KEINE eigene Quelle (früher Pflicht). Optional überschreibbar."""
    from app.schemas.article_process_step import ArticleProcessStepCreate

    # Ohne Quelle → ok (erbt vom Artikel)
    inherit = ArticleProcessStepCreate(step_type="purchase", mode="supplier")
    assert inherit.supplier_id is None and inherit.webshop_url is None
    # Optionaler Override am Schritt bleibt möglich
    override = ArticleProcessStepCreate(step_type="purchase", mode="supplier", supplier_id=42)
    assert override.supplier_id == 42
    override2 = ArticleProcessStepCreate(step_type="purchase", mode="webshop",
                                         webshop_url="https://shop.example/x")
    assert override2.webshop_url == "https://shop.example/x"


def test_procurement_source_step_over_article():
    """resolve_source: die Bezugsquelle wird im **Schritt** definiert (max. Flexibilität,
    mehrere Quellen je Prozess); der Artikel-Default dient als Vorbelegung/Fallback."""
    from types import SimpleNamespace as NS

    from app.services.purchase import has_source, resolve_source

    art_sup = NS(procurement_mode="supplier", default_supplier_id=7, default_webshop_url=None)
    art_empty = NS(procurement_mode="supplier", default_supplier_id=None, default_webshop_url=None)
    step_none = NS(supplier_id=None, webshop_url=None)
    step_sup = NS(supplier_id=99, webshop_url=None)
    step_web = NS(supplier_id=None, webshop_url="https://b.example/y")

    # Schritt-Quelle gewinnt
    assert resolve_source(step_sup, art_sup) == ("supplier", 99, None)
    assert resolve_source(step_web, art_sup) == ("webshop", None, "https://b.example/y")
    # Kein Schritt-Override → Artikel-Default als Fallback
    assert resolve_source(step_none, art_sup) == ("supplier", 7, None)
    # Weder Schritt noch Artikel → Modus ohne konkrete Quelle
    assert resolve_source(step_none, art_empty) == ("supplier", None, None)
    assert resolve_source(None, None) == ("supplier", None, None)

    # has_source: Freigabe-Sperre – Schritt ODER Artikel deckt die Quelle
    assert has_source(step_sup, art_empty) is True     # Quelle am Schritt
    assert has_source(step_none, art_sup) is True       # Quelle am Artikel (Fallback)
    assert has_source(step_none, art_empty) is False    # nirgends hinterlegt
    assert has_source(None, None) is False


def test_process_step_types_and_optional_config():
    """Datenerfassung/Bewegung brauchen keinen Lieferanten; Prüfumfang default 100 %."""
    import pytest

    from app.schemas.article_process_step import ALLOWED_STEP_TYPES, ArticleProcessStepCreate

    assert set(ALLOWED_STEP_TYPES) == {"purchase", "inspection", "movement", "resource", "scrap", "block", "sale", "document"}
    # «serialization» ist kein eigener Schritt mehr (Instanzen entstehen bei Freigabe)
    with pytest.raises(ValueError):
        ArticleProcessStepCreate(step_type="serialization")
    # Eine Datenerfassung OHNE Erfassungsfeld ist ein Schritt ohne Inhalt – im Auftrag
    # gäbe es nichts zu erfassen, der Auftrag käme dort nicht weiter.
    with pytest.raises(ValueError):
        ArticleProcessStepCreate(step_type="inspection")
    one_field = [{"label": "Oberfläche", "type": "bool"}]
    insp = ArticleProcessStepCreate(step_type="inspection", capture_fields=one_field)
    assert insp.sample_percent == 100                 # Default: ganze Menge
    insp2 = ArticleProcessStepCreate(step_type="inspection", sample_percent=10, capture_fields=one_field)
    assert insp2.sample_percent == 10


def test_instances_created_at_release_not_as_step():
    """Bestands-Instanzen entstehen bei der Freigabe – «serialization» ist kein Schritt."""
    from app.schemas.article_process_step import ALLOWED_STEP_TYPES
    from app.services import process, serialization

    assert "serialization" not in ALLOWED_STEP_TYPES
    assert "serialization" not in process.STEP_LABELS
    # Neue API: Instanzen werden bei der Freigabe erzeugt (kein /serialize-Schritt)
    assert callable(serialization.create_instances_for_order)
    assert not hasattr(serialization, "serialize_for_order")


def test_release_delegates_status_flip_to_release_order():
    """Regression: die Freigabe (draft → released) muss den Statuswechsel **release_order**
    überlassen. ``update_order`` darf den Status NICHT vorab über die generische Schleife
    setzen – sonst ist der Auftrag beim Aufruf schon „released", ``release_order`` kehrt wegen
    „nicht mehr draft" sofort zurück und stellt KEIN Subjekt her: keine Instanzen, keine
    Objektnummern, keine Fehlermeldung (stiller Blindgänger, den der Nutzer meldete)."""
    import inspect as _inspect
    from app.routers import orders as orders_router
    from app.services import orders as orders_svc

    upd_src = _inspect.getsource(orders_router.update_order)
    # Der Status der Freigabe wird aus dem Payload GENOMMEN, nicht vorab gesetzt.
    assert 'payload.pop("status")' in upd_src
    assert 'wants_release = payload.get("status") == "released"' in upd_src
    assert "release_order(db, order" in _inspect.getsource(orders_router._do_release)
    # Die generische Setz-Schleife läuft NACH dem Herausnehmen des Freigabe-Status.
    assert upd_src.index("wants_release =") < upd_src.index("_apply_fields(")

    # release_order ist der EINZIGE Pfad, der den Statuswechsel vollzieht – und schützt sich
    # gegen Nicht-Entwürfe (Idempotenz). Beides zusammen macht die Reihenfolge zwingend.
    rel_src = _inspect.getsource(orders_svc.release_order)
    assert 'order.status = "released"' in rel_src
    assert 'if order.status != "draft":' in rel_src


def test_movement_step_target_config():
    """Bewegung: Zieltyp wird validiert; ohne Typ kein festes Zielobjekt."""
    import pytest

    from app.schemas.article_process_step import ArticleProcessStepCreate

    # Ohne Vorgabe (Lagerist entscheidet)
    free = ArticleProcessStepCreate(step_type="movement")
    assert free.target_location_type is None and free.target_location_id is None

    # Festes Ziel
    fixed = ArticleProcessStepCreate(step_type="movement", target_location_type="instance", target_location_id=100_000_500)
    assert fixed.target_location_type == "instance"
    assert fixed.target_location_id == 100_000_500

    # Zielobjekt ohne Typ → wird verworfen
    dangling = ArticleProcessStepCreate(step_type="movement", target_location_id=100_000_500)
    assert dangling.target_location_id is None

    with pytest.raises(ValueError):
        ArticleProcessStepCreate(step_type="movement", target_location_type="unsinn")


def test_movement_target_validates_location_type():
    """Ein Zielstandort ist ein **Halter**: user | instance | company.

    Der frühere Typ ``lagerplatz`` ist ersatzlos entfallen (eigener Datensatztyp ohne
    Logik) und muss beim Schreiben abgewiesen werden."""
    import pytest

    from app.schemas.movement import LOCATION_TYPES, MovementTarget

    assert set(LOCATION_TYPES) == {"user", "instance", "company"}
    ok = MovementTarget(instance_id=100_000_010, location_type="company", location_id=100_000_002)
    assert ok.location_type == "company"
    for gone in ("strasse", "lagerplatz"):
        with pytest.raises(ValueError):
            MovementTarget(instance_id=1, location_type=gone, location_id=2)


def test_movement_in_process_engine():
    """Die Prozess-Engine kennt den Bewegungsschritt (Label + Raw-Status)."""
    from app.services.process import STEP_LABELS

    assert STEP_LABELS["movement"] == "Bewegung"
    assert "serialization" not in STEP_LABELS    # kein eigener Schritt mehr


def test_instance_always_has_location_field():
    """Instanzen tragen einen Standort (location_type/location_id)."""
    from app.models import Instance

    assert hasattr(Instance, "location_type")
    assert hasattr(Instance, "location_id")


def test_inspection_capture_is_per_sample():
    """Datenerfassung erfasst je Stichprobe (Instanz) einen Wertesatz."""
    from app.schemas.inspection import InspectionUpdate, InspectionSample

    upd = InspectionUpdate(samples=[
        InspectionSample(instance_id=100_000_010, slot=1, values={"len": 10.1}),
        InspectionSample(instance_id=100_000_010, slot=2, values={"len": 9.9}),
    ], note="ok")
    assert len(upd.samples) == 2 and upd.samples[1].slot == 2
    # Altfelder gibt es nicht mehr
    assert "values" not in InspectionUpdate.model_fields
    assert "checked_count" not in InspectionUpdate.model_fields


def test_eval_fields_falls_back_to_gut_schlecht():
    """Ohne Maske wird je Probe ein synthetisches Gut/Schlecht (_ok) bewertet."""
    from app.services.inspection import eval_fields, DEFAULT_OK_FIELD

    fields = eval_fields(None)
    assert fields == [DEFAULT_OK_FIELD] and fields[0]["type"] == "bool"


def test_article_name_capped_and_trimmed():
    """Freie Namensgebung, aber zentral getrimmt und auf NAME_MAX_LENGTH gekappt."""
    from app.schemas.article import ArticleCreate, NAME_MAX_LENGTH, clean_article_name

    assert clean_article_name("  Hallo Welt  ") == "Hallo Welt"
    assert len(clean_article_name("X" * 60)) == NAME_MAX_LENGTH
    with pytest.raises(ValueError):
        clean_article_name("   ")                       # leer → Pflichtfeld
    # Der Create-Schema-Pfad kappt ebenfalls (Frontend begrenzt zusätzlich).
    assert len(ArticleCreate(name="A" * 50).name) == NAME_MAX_LENGTH


def test_article_name_similarity_recognizes_shared_stem():
    """Fuzzy-Vorschläge (ohne KI): gemeinsamer Wortstamm wird erkannt, Fremdes nicht."""
    from app.services.article_names import _similarity, _MIN_SCORE

    assert _similarity("Schraubendreher", "Schraubendreher") == 1.0
    # «Akkuschrauber»/«Schraubenzieher» teilen den Stamm «schraub» → Vorschlag.
    assert _similarity("Akkuschrauber", "Schraubendreher") >= _MIN_SCORE
    assert _similarity("Schraubenzieher", "Schraubendreher") >= _MIN_SCORE
    # Substring-Bonus: die Kernbezeichnung matcht stark.
    assert _similarity("Schraub", "Schraubendreher") > 0.5
    # Unverwandte Namen bleiben unter der Schwelle (kein Rausch-Vorschlag).
    assert _similarity("Welle", "Dichtung") < _MIN_SCORE
    assert _similarity("Bolzen", "Schraubendreher") < _MIN_SCORE


def test_storage_location_record_type_is_gone():
    """Der Datensatztyp **Lagerplatz** ist vollständig entfernt – Modell, Schema, Router
    und Registry-Eintrag. Ein Standort ist nur noch ein Halter (Person/Instanz/Unternehmen)
    oder gar keiner; «standortlos» ist ein regulärer Zustand."""
    import importlib

    import app.models as models
    from app.services import objects

    assert not hasattr(models, "StorageLocation")
    assert "storage_location" not in objects._TYPE_MODELS
    for mod in ("app.models.storage_location", "app.schemas.storage_location",
                "app.routers.storage_locations"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod)


def test_order_step_info_carries_completion():
    """Stepper-Schritt trägt Abschluss-Info (wer/wann) für den Hover-Tooltip."""
    from app.schemas.order import OrderStepInfo

    assert "completed_by" in OrderStepInfo.model_fields
    assert "completed_at" in OrderStepInfo.model_fields


def test_object_reference_schema():
    """Generischer Verweis («Verwendung» je Objektnummer): Typ, Nummer, Label, Zeit."""
    from app.schemas.instance import ObjectReference

    for f in ("kind", "ref_type", "object_id", "label", "at"):
        assert f in ObjectReference.model_fields


def test_instance_orders_schema_and_service():
    """Eine Instanz ist die Summe aller Aufträge, die sie angefasst haben."""
    from app.schemas.instance import InstanceOrderRef
    from app.services import references

    for f in ("object_id", "status", "roles", "at"):
        assert f in InstanceOrderRef.model_fields
    assert callable(references.instance_orders)


def test_recurrence_locked_after_release():
    """Wiederkehr ist nur im Entwurf einstellbar – nach Freigabe sperrt
    ensure_mutable jede Inhaltsänderung (inkl. der Wiederkehr-Felder)."""
    import pytest
    from fastapi import HTTPException
    from app.services.lifecycle import ensure_mutable

    ensure_mutable("draft", {"recurrence_active": True}, "Auftrag")   # erlaubt
    with pytest.raises(HTTPException):
        ensure_mutable("released", {"recurrence_active": True}, "Auftrag")


def test_capture_field_evaluation():
    """Soll-Ist mit Toleranz, Gut/Schlecht, Text werden korrekt bewertet."""
    from app.services.inspection import evaluate, field_ok

    measure = {"key": "len", "type": "measure", "target": 100.0, "tolerance": 0.5}
    assert field_ok(measure, 100.3) is True       # innerhalb Toleranz
    assert field_ok(measure, 101.0) is False      # ausserhalb
    assert field_ok(measure, "") is False         # nicht erfasst
    assert field_ok({"key": "b", "type": "bool"}, True) is True
    assert field_ok({"key": "b", "type": "bool"}, False) is False
    assert field_ok({"key": "t", "type": "text"}, "ok") is True  # informativ

    fields = [measure, {"key": "b", "type": "bool"}]
    assert evaluate(fields, {"len": 100.0, "b": True}) is True
    assert evaluate(fields, {"len": 100.0, "b": False}) is False


def test_capture_field_normalize_assigns_keys():
    """Erfassungsfelder bekommen eindeutige Keys; Nicht-Measure ohne Soll/Tol."""
    from app.schemas.article_process_step import normalize_capture_fields

    out = normalize_capture_fields([
        {"label": "Länge", "type": "measure", "target": 10, "tolerance": 1},
        {"label": "Sauber", "type": "bool", "target": 5},
    ])
    assert out[0]["key"] and out[1]["key"]
    assert out[0]["key"] != out[1]["key"]
    assert out[1]["target"] is None  # bool → kein Sollwert


def test_inspection_escalation_decision():
    """Ungenügende Teil-Stichprobe stuft auf 100 % hoch; bei vollem Umfang endgültig failed."""
    from app.services.inspection import escalate_decision

    assert escalate_decision(False, 10, True) == "passed"      # alles ok
    assert escalate_decision(True, 100, True) == "passed"
    assert escalate_decision(False, 10, False) == "escalate"   # Teilstichprobe ungenügend
    assert escalate_decision(True, 10, False) == "failed"      # bereits hochgestuft → failed
    assert escalate_decision(False, 100, False) == "failed"    # von Beginn 100 %
    assert escalate_decision(False, None, False) == "failed"   # None = 100 %


def test_inspection_model_and_embed_have_escalated():
    """Datenerfassung trägt das Hochstufungs-Flag (Modell + Embed)."""
    from app.models import Inspection
    from app.schemas.inspection import InspectionEmbed

    assert hasattr(Inspection, "escalated")
    assert "escalated" in InspectionEmbed.model_fields


def test_purchase_step_defines_receiving_location():
    """Lieferadresse/Wareneingang wird im Beschaffungsschritt geführt (PO + Embed)."""
    from app.models import PurchaseOrder
    from app.schemas.purchase_order import PurchaseEmbed

    # Die Lieferadresse ist die Firmenadresse (kein Lagerplatz-Zeiger mehr).
    assert not hasattr(PurchaseOrder, "receiving_location_id")
    assert "receiving_location_id" not in PurchaseEmbed.model_fields


def test_resource_line_schema_validates():
    """Ressourcen-Zeile: Artikel + Menge > 0; Modus pro Zeile (consume|tool)."""
    import pytest

    from app.schemas.article_process_step import ResourceLine

    assert ResourceLine(article_id=5, quantity=2).mode == "consume"   # Default
    assert ResourceLine(article_id=5, mode="tool").quantity == 1      # Menge-Default
    with pytest.raises(ValueError):
        ResourceLine(article_id=5, mode="unsinn")
    with pytest.raises(ValueError):
        ResourceLine(article_id=5, quantity=0)


def test_resource_step_requires_lines():
    """Ein resource-Schritt braucht mindestens eine Zeile."""
    import pytest

    from app.schemas.article_process_step import ArticleProcessStepCreate, ResourceLine

    with pytest.raises(ValueError):
        ArticleProcessStepCreate(step_type="resource")
    ok = ArticleProcessStepCreate(
        step_type="resource",
        resource_lines=[ResourceLine(article_id=5, quantity=2, mode="tool")],
    )
    assert ok.resource_lines[0].article_id == 5 and ok.resource_lines[0].mode == "tool"


def test_resource_step_in_engine_and_model():
    """Engine kennt «Ressource»; Ausführungs-Marker + released_at vorhanden."""
    from app.models import Instance, ResourceUsage
    from app.schemas.article_process_step import ALLOWED_STEP_TYPES
    from app.services.process import STEP_LABELS

    assert ResourceUsage.__tablename__ == "resource_usages"
    assert STEP_LABELS["resource"] == "Ressource"
    assert "resource" in ALLOWED_STEP_TYPES
    assert hasattr(Instance, "released_at")     # FIFO-Basis


def test_reservation_no_split_keeps_object_number():
    """Mengengenaue Reservierung/Verbrauch OHNE Teilung: die Instanz behält IMMER ihre
    Objektnummer; nur Menge und Reservierung ändern sich – es entsteht KEIN neues Objekt.
    Eine Charge kann sich auf mehrere Aufträge aufteilen (Reservierungs-Map)."""
    from app.services.reservation import reserve, take, free_qty, reserved_for
    from app.services.resource import _Fifo
    from app.services.inventory import available_qty

    class C:
        def __init__(self, q):
            self.quantity = q
            self.reservations = None
            self.reserved_quantity = 0

    batch = C(100)
    reserve(batch, 7, 30)
    assert batch.reserved_quantity == 30 and reserved_for(batch, 7) == 30
    assert free_qty(batch) == 70                  # 70 bleiben frei verfügbar (keine Teilung)
    reserve(batch, 9, 20)                          # zweiter Auftrag teilt sich dieselbe Charge
    assert batch.reserved_quantity == 50 and free_qty(batch) == 50
    take(batch, 30, by_order_id=7)                 # Auftrag 7 verbraucht seine 30
    assert batch.quantity == 70                    # selbe Instanz, nur weniger Menge
    assert reserved_for(batch, 7) == 0 and reserved_for(batch, 9) == 20

    # available_qty zählt frei + eigene Reservierung; _Fifo entnimmt je Auftrag entsprechend.
    a, b = C(1), C(5)
    assert available_qty([a, b], None) == 6
    f = _Fifo([a, b], order_id=9)
    cand, take, whole = f.take(3)
    assert cand is a and take == 1 and whole is True    # Einzelteil ganz ins Produkt


def test_required_sample_math():
    """Prüfumfang = aufgerundet Menge × % (mind. 1, höchstens Menge)."""
    from app.services.process import required_sample

    assert required_sample(30, 10) == 3
    assert required_sample(30, 100) == 30
    assert required_sample(5, 10) == 1     # mind. 1
    assert required_sample(30, None) == 30  # ohne Angabe = 100 %
    assert required_sample(0, 50) == 0


def test_order_desired_date_must_be_future():
    """Wunsch-Liefertermin in der Vergangenheit wird abgelehnt, heute/Zukunft ok."""
    from datetime import date, timedelta

    import pytest

    from app.schemas.order import OrderCreate

    base = dict(article_id=100_000_001, quantity=1)
    assert OrderCreate(**base, desired_delivery_date=date.today()).desired_delivery_date == date.today()
    future = date.today() + timedelta(days=5)
    assert OrderCreate(**base, desired_delivery_date=future).desired_delivery_date == future
    with pytest.raises(ValueError):
        OrderCreate(**base, desired_delivery_date=date.today() - timedelta(days=1))


def test_lifecycle_locks_after_release():
    """Nach Freigabe sind nur noch Status/is_active änderbar."""
    import pytest

    from app.services.lifecycle import ensure_mutable

    # Entwurf: alles erlaubt
    ensure_mutable("draft", {"name": "x", "status": "released"}, "Artikel")
    # Freigegeben: nur Status/is_active
    ensure_mutable("released", {"status": "inactive"}, "Artikel")
    ensure_mutable("released", {"is_active": False}, "Artikel")
    with pytest.raises(Exception):
        ensure_mutable("released", {"name": "neu"}, "Artikel")
    with pytest.raises(Exception):
        ensure_mutable("completed", {"quantity": 5}, "Auftrag")


def test_order_status_allows_completed():
    """Auftrag kann automatisch abgeschlossen werden (Status 'completed')."""
    from app.schemas.order import ALLOWED_STATUS, OrderUpdate

    assert "completed" in ALLOWED_STATUS
    assert OrderUpdate(status="completed").status == "completed"


def test_purchase_runs_under_order_without_own_number():
    """Bestellung hat keine eigene Objektnummer; sie läuft unter dem Auftrag."""
    from app.models import PurchaseOrder
    from app.schemas.order import OrderResponse
    from app.schemas.purchase_order import PurchaseEmbed

    assert not hasattr(PurchaseOrder, "object_id")
    assert "object_id" not in PurchaseEmbed.model_fields
    # Auftrag bettet den Beschaffungsschritt ein
    assert "purchase" in OrderResponse.model_fields


def test_reclamation_is_a_deviation_order_not_a_separate_type():
    """Reklamation ist KEIN eigener Datentyp mehr – sie ist eine «Abweichung»
    (= Auftrag mit ``parent_order_id``). Der alte Claim-Typ ist vollständig
    entfernt: Modell, Schema, Router und Service existieren nicht mehr."""
    import importlib

    import pytest

    from app import models

    assert not hasattr(models, "Claim")
    for mod in ("app.models.claim", "app.schemas.claim",
                "app.routers.claims", "app.services.claims"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod)


def test_there_is_exactly_one_way_to_create_an_order():
    """**Ein Auftrag und ein Abweichungsauftrag entstehen auf demselben Weg** (Notiz #371).

    Der frühere Sonder-Endpunkt ``POST /orders/{id}/deviation`` (samt eigenem Schema) ist
    entfallen. Der Abkürzungs-Knopf an einer Instanz legt jetzt einen ganz gewöhnlichen
    Auftrag an und trägt die Instanz nur **vor** – Eingabehilfe, keine Fixierung. Ob daraus
    eine Abweichung wird, sagt weiterhin die Auswahl (``subject.classify_pick``).

    Der Service ``deviation.create_deviation`` bleibt – aber nur noch für die Fälle, die das
    SYSTEM selbst auslöst (fehlgeschlagene Datenerfassung, Artikel-Deaktivierung)."""
    import inspect as _inspect
    import app.schemas.order as order_schemas
    from app.routers import orders
    from app.schemas.order import OrderCreate
    from app.services import deviation

    assert not hasattr(orders, "open_deviation")
    assert not hasattr(order_schemas, "OrderDeviationCreate")
    # Die Anlage nimmt die Vorauswahl entgegen – über denselben Pfad wie jede Auswahl.
    assert "picks" in OrderCreate.model_fields
    assert "_set_chosen_instances(db, order, data.picks" in _inspect.getsource(orders.create_order)
    # Der Service bleibt für die systemseitigen Auslöser.
    create = _inspect.getsource(deviation.create_deviation)
    assert "parent_order_id=parent.object_id" in create and "record_link" in create


def test_a_sub_order_knows_which_step_it_interrupted():
    """**Beide Anlage-Wege vergeben dieselbe Position im Ablauf** (Testnotiz #377).

    Ein Unter-Auftrag steht im Fluss an der Stelle, an der er entstanden ist
    (``orders.origin_step_id``). Diese Zuordnung gibt es genau EINMAL
    (``deviation.interrupted_step_id`` = der Schritt, an dem der Eltern gerade steht) –
    und beide Wege benutzen sie: der systemseitige (``create_deviation``) UND der
    menschliche über die Instanz-**Auswahl** (``_make_deviation``).

    Genau der zweite vergab sie nicht, seit er der einzige menschliche Weg ist (Notiz #371):
    ohne Position landete die Abweichung im Fluss ganz vorne – also **vor** einem längst
    abgeschlossenen Schritt. Und wer die Auswahl zurücknimmt, verliert die Position wieder,
    sonst behielte ein gewöhnlicher Auftrag die Stelle einer Abweichung, die er nicht mehr
    ist."""
    import inspect as _inspect

    from app.routers import orders
    from app.services import deviation

    assert callable(deviation.interrupted_step_id)
    for src in (_inspect.getsource(deviation.create_deviation),
                _inspect.getsource(orders._make_deviation)):
        assert "interrupted_step_id" in src
    assert "order.origin_step_id = None" in _inspect.getsource(orders._clear_derived_marker)


def test_failed_inspection_triggers_deviation():
    """Die Datenerfassung eröffnet bei Nichtbestehen automatisch eine Abweichung
    (vormals «interne Reklamation») – idempotent, auf den Durchfaller-Instanzen."""
    import inspect as _inspect

    from app.services import deviation, inspection

    assert callable(deviation.auto_deviation_from_inspection)
    # Der Auto-Trigger ist in der Datenerfassung verdrahtet
    assert inspection.auto_deviation_from_inspection is deviation.auto_deviation_from_inspection
    src = _inspect.getsource(deviation.auto_deviation_from_inspection)
    # idempotent: nichts tun, wenn bereits eine Abweichung offen ist
    assert "open_deviations" in src


def test_only_one_open_deviation_per_instance():
    """Höchstens EINE aktive Abweichung je Instanz: create_deviation prüft jede Zielinstanz
    gegen offene Abweichungen und lehnt sonst ab (kein gleichzeitiges Greifen Instanz-/Prozess-Ebene)."""
    import inspect as _inspect

    from app.services import deviation

    assert callable(deviation.instance_open_deviation)
    guard = _inspect.getsource(deviation.instance_open_deviation)
    # Sucht eine offene (Entwurf/freigegeben) Abweichung (Unter-Auftrag) über die Instanz-Verknüpfung
    assert "parent_order_id" in guard and "InstanceOrderLink" in guard
    create = _inspect.getsource(deviation.create_deviation)
    assert "instance_open_deviation" in create and "409" in create


def test_order_response_exposes_sub_deviations():
    """Der Eltern-Auftrag macht seine Unter-Aufträge sichtbar – und sagt, ob er **ruht**.

    ``paused`` ist dabei KEIN eigener Zustand neben der Fehlmenge, sondern deren
    Projektion (``process.is_paused``) – es wird abgeleitet, nicht gespeichert."""
    import inspect as _inspect

    from app.schemas.order import OrderDeviationInfo, OrderResponse
    from app.services import orders as orders_svc

    assert "deviations" in OrderResponse.model_fields
    assert "paused" in OrderResponse.model_fields
    # Kein zweiter Nachbau im Response-Aufbau: es wird die EINE Regel gefragt.
    assert "process.is_paused(db, order)" in _inspect.getsource(orders_svc._fill_order_shortfall)
    for f in ("object_id", "status", "instance_count", "instance_object_ids"):
        assert f in OrderDeviationInfo.model_fields


def test_scrapped_instances_excluded_from_processing_and_completion():
    """Verschrottete/terminale Teile werden aus der weiteren Eltern-Verarbeitung UND dem
    Abschluss genommen – der Auftrag wird mit seinen GUTEN Teilen fertig (sie werden nicht
    mehr bewegt/geprüft/bestückt; die Anzeige zeigt sie weiter)."""
    import inspect as _inspect

    from app.services import inspection, movement, process, resource, subject

    # Terminaler Verbleib zentral deklariert + Filter-Helper
    assert set(subject.TERMINAL_DISPOSITIONS) == {"scrapped", "sold", "consumed"}
    src = _inspect.getsource(subject.order_active_instances)
    assert "TERMINAL_DISPOSITIONS" in src
    # Verarbeitungs-Pfade nutzen die AKTIVE Liste (nicht die volle); die Bewegung über
    # die EINE Auswahlregel movable_instances (Review 2026-07).
    assert "movable_instances" in _inspect.getsource(movement.record_movement)
    assert "order_active_instances" in _inspect.getsource(movement.movable_instances)
    assert "order_active_instances" in _inspect.getsource(resource) \
        and "order_instances(" not in _inspect.getsource(resource)
    insp_src = _inspect.getsource(inspection)
    assert "order_active_instances" in insp_src and "order_instances(" not in insp_src
    # Abschluss: nur «im Prozess» befindliche Instanzen kommen ans Lager (kein Wieder-
    # beleben eines verschrotteten, noch nicht bewerteten Teils)
    rel = _inspect.getsource(process.release_instances)
    assert 'disposition == "in_process"' in rel
    # Anzeige bleibt vollständig (to_order_response nutzt weiter die volle Liste)
    from app.services import orders as orders_svc
    assert "order_instances(db, order)" in _inspect.getsource(orders_svc.to_order_response)


def test_a_deviation_pauses_the_order_through_the_shortfall_not_a_second_rule():
    """**Eine Abweichung hält den Auftrag an – aber über die Fehlmenge, nicht daneben.**

    Beides ist wahr und das ist der Kern: der Eltern-Prozess ruht, solange eine Abweichung
    offen ist (Testnotiz #354) – und trotzdem gibt es dafür KEINEN eigenen Mechanismus.
    Die Abweichung nimmt ihr Stück heraus (``deviated_instance_ids``), daraus entsteht eine
    Unterdeckung, und ein Auftrag mit offener Fehlmenge ruht (``is_paused``). Ein Ausschuss
    oder eine weggenommene Reservierung erzeugen denselben Zustand über denselben Weg.

    Darum bleiben der frühere Sonder-Zustand (``_is_paused_by_deviation``) und sein Wächter
    an den Ausführungs-Endpunkten (``_assert_not_paused``) abgeschafft."""
    import inspect as _inspect

    from app.routers import orders
    from app.services import process

    # Kein zweiter Mechanismus – weder als Regel noch als Wächter.
    assert not hasattr(process, "_is_paused_by_deviation")
    assert not hasattr(orders, "_assert_not_paused")
    assert "_assert_not_paused" not in _inspect.getsource(orders)
    # Die Pause fragt die Fehlmenge, sonst nichts.
    paused = _inspect.getsource(process.is_paused)
    assert "_subject_shortfalls(db, order)" in paused
    assert "deviation" not in paused.split('"""')[-1]
    # Stattdessen: in Klärung gebundene Instanzen zählen nicht als gesichert …
    short = _inspect.getsource(process._secured_amounts)
    assert "deviated_quantities" in short and "in_clarification" in short
    dev = _inspect.getsource(process.deviated_quantities)
    # Die Klammer ist die **Instanz**, nicht der Eltern-Zeiger: eine an der Instanz
    # gemeldete Abweichung hängt an einem ganz anderen Auftrag und muss trotzdem zählen.
    assert "order_instances" in dev and "subject_of_order_id" in dev
    assert '"deviation"' in dev
    # … und werden vom Eltern-Auftrag auch nicht ans Lager freigegeben.
    assert "deviated_quantities" in _inspect.getsource(process.release_instances)
    # Abweichungs-Abschluss bewertet den Eltern-Auftrag neu
    rc = _inspect.getsource(process.recompute_completion)
    assert "parent_order_id" in rc and "recompute_completion(db, lender)" in rc


def test_article_deactivate_cancel_creates_followup():
    """Beim Deaktivieren eines Artikels mit «Abbrechen» übernimmt ein Abweichungsauftrag die
    Instanzen laufender Aufträge (statt Teile zu vernichten) – analog zum Auftrag-Abbruch."""
    import inspect as _inspect

    from app.services import deactivation

    src = _inspect.getsource(deactivation.deactivate_article)
    assert "create_deviation" in src and "abort_parent" in src and "order_active_instances" in src


def test_article_optional_fields_validation():
    """Optionale Stammdaten: Text getrimmt, leere → None, Mengen ≥ 0."""
    from decimal import Decimal

    import pytest

    from app.schemas.article import ArticleCreate, ArticleResponse

    base = dict(name="Welle", unit="Stk", serialization="unit", size="1x2", weight_kg=Decimal("1"))
    a = ArticleCreate(**base, material="  Stahl 1.4301  ", cad_url="", min_order_qty=Decimal("50"))
    assert a.material == "Stahl 1.4301"     # getrimmt
    assert a.cad_url is None                 # leer → None
    assert a.min_order_qty == Decimal("50")
    with pytest.raises(ValueError):
        ArticleCreate(**base, safety_stock=Decimal("-1"))   # negativ verboten
    # Response trägt optionale Felder + Durchlaufzeit-Spanne
    for f in ("material", "cad_url", "surface", "min_order_qty", "safety_stock",
              "lead_time_days_low", "lead_time_days_high"):
        assert f in ArticleResponse.model_fields


def test_order_has_lead_time_timestamps():
    """Auftrag trägt Eckdaten für die Durchlaufzeit (Freigabe → Abschluss)."""
    from app.models import Order

    assert hasattr(Order, "released_at")
    assert hasattr(Order, "completed_at")


def test_fact_tables_carry_step_id_for_routing():
    """Mehr-Operationen-Routing: jede Fachzeile ist an ihre Schritt-Definition gebunden."""
    from app.models import Inspection, Movement, PurchaseOrder, ResourceUsage

    for model in (PurchaseOrder, Inspection, Movement, ResourceUsage):
        assert hasattr(model, "step_id")
    # Ausführungs-Schemas erlauben die explizite Schritt-Wahl
    from app.schemas.inspection import InspectionUpdate
    from app.schemas.movement import MovementUpdate
    from app.schemas.resource import ResourceUpdate
    for schema in (InspectionUpdate, MovementUpdate, ResourceUpdate):
        assert "step_id" in schema.model_fields


def test_process_engine_routing_helpers():
    """Engine kann Status/Embed pro Schritt-Definition auflösen (nicht nur pro Typ)."""
    from app.services import process

    assert callable(process.fact_for_step)
    assert callable(process.resolve_exec_step)
    assert callable(process.build_order_steps)
    # Stepper-Infos tragen die Schritt-id (eindeutiger Routing-Schlüssel)
    from app.schemas.order import OrderStepInfo
    assert "id" in OrderStepInfo.model_fields
    for embed in ("purchase", "inspection", "movement", "resource"):
        assert embed in OrderStepInfo.model_fields


def test_fact_status_pure_mapping():
    """Roh-Status je Fachzeile (rein, ohne DB) – Grundlage des Steppers."""
    from types import SimpleNamespace as NS

    from app.services.process import _fact_status

    assert _fact_status("purchase", None) == "open"
    assert _fact_status("purchase", NS(status="received")) == "done"
    assert _fact_status("purchase", NS(status="rejected")) == "failed"
    assert _fact_status("inspection", NS(result="passed")) == "done"
    assert _fact_status("inspection", NS(result="failed")) == "failed"
    assert _fact_status("inspection", None) == "open"
    assert _fact_status("movement", NS()) == "done"
    assert _fact_status("resource", None) == "open"


def test_resolve_fact_routing_and_legacy():
    """Fachzeile je Schritt: exakt über step_id; Altzeile (None) nur beim Einzeltyp."""
    from types import SimpleNamespace as NS

    from app.services.process import _resolve_fact

    step1, step2 = NS(id=11), NS(id=12)
    rows = [NS(step_id=11), NS(step_id=12)]
    assert _resolve_fact(step1, rows, sole_of_type=False).step_id == 11
    assert _resolve_fact(step2, rows, sole_of_type=False).step_id == 12
    # Altzeile ohne step_id gehört dem einzigen Schritt seines Typs
    legacy = [NS(step_id=None)]
    assert _resolve_fact(step1, legacy, sole_of_type=True).step_id is None
    assert _resolve_fact(step1, legacy, sole_of_type=False) is None


def test_object_id_block_allocation():
    """next_object_ids gibt einen fortlaufenden Block (eine Query statt je Objekt)."""
    from app.services import objects

    assert objects.next_object_ids.__doc__  # vorhanden
    assert callable(objects.next_object_ids)


def test_is_step_active_removed():
    """Tote Typ-basierte Kurzform entfernt – Routing läuft über resolve_exec_step."""
    from app.services import process

    assert not hasattr(process, "is_step_active")


def test_inspection_values_column_removed():
    """Obsolete Spalte inspections.values (Altformat) entfernt – nur noch samples."""
    from app.models import Inspection

    assert not hasattr(Inspection, "values")
    assert hasattr(Inspection, "samples")


def test_event_outbox_model_and_router():
    """Domain-Event-Strom (Outbox): Modell append-only, Emit-Helper, Lese-API."""
    from app.models import Event
    from app.routers import events
    from app.schemas.event import EventResponse
    from app.services.events import emit

    assert Event.__tablename__ == "events"
    # append-only: kein Soft-Delete/Update-Flag
    assert not hasattr(Event, "is_active")
    assert not hasattr(Event, "updated_at")
    for f in ("object_id", "object_type", "event_type", "payload", "actor_id", "created_at"):
        assert hasattr(Event, f)
    assert callable(emit)
    assert hasattr(events, "router")
    for f in ("id", "object_type", "event_type", "created_at"):
        assert f in EventResponse.model_fields


def test_registry_fks_and_instance_search_wired():
    """Stufe 2: FK-Integrität der Quer-Referenzen + Instanz-Server-Suche/Count."""
    from app.services.objects import _FOREIGN_KEYS, ensure_foreign_keys
    from app.routers import instances as inst_router

    cols = {(t, c) for t, _, c in _FOREIGN_KEYS}
    # Die Kern-Quer-Referenzen sind als FK auf die Registry abgesichert
    assert ("instances", "location_id") in cols
    assert ("articles", "replaced_by_id") in cols
    assert callable(ensure_foreign_keys)
    # Instanz-Feed ist server-seitig durchsuchbar + zählbar
    assert callable(inst_router._apply_search) and hasattr(inst_router, "CountResponse")


def test_object_registry_wired():
    """Zentrale Objekt-Registry: Modell, Typ-Map und Auflösung/Backfill vorhanden."""
    from app.models import ObjectRef
    from app.services import objects

    assert ObjectRef.__tablename__ == "objects"
    # Eigenständige Objekttypen (Prozesse sind KEINE Objekte mehr – kein Eintrag).
    # Das Unternehmen selbst ist ebenfalls ein nummerierter ERP-Datensatz.
    # Das Prozessschritt-Dokument trägt KEINE eigene Nummer (Nummer = Instanz); ein
    # hochgeladenes Dokument (``DocumentFile``, Typ ``document``) hingegen schon.
    assert set(objects._TYPE_MODELS) == {
        "user", "article", "order", "instance", "organization", "document"}
    assert callable(objects.resolve_object_type) and callable(objects.backfill_registry)


def test_inventory_allocate_quantity_exact():
    """Mengengenaue Reservierung: nur der Bedarf wird belegt, Rest bleibt frei
    (behebt das Über-Sperren ganzer Chargen)."""
    from app.services.inventory import allocate

    # Charge 100, Bedarf 10 → 10 belegt, 90 bleiben (als Rest am selben Kandidaten)
    assert allocate(10, [100]) == [10]
    # Über mehrere Kandidaten FIFO auffüllen
    assert allocate(25, [10, 10, 10]) == [10, 10, 5]
    # Bedarf grösser als Bestand → so viel wie möglich
    assert allocate(50, [10, 10]) == [10, 10]
    # Kein Bedarf → nichts belegen
    assert allocate(0, [10, 10]) == [0, 0]
    # Zwei Aufträge teilen sich dieselbe Charge: A nimmt 10 von 100, B nimmt 10 vom Rest
    assert allocate(10, [90]) == [10]


def test_deactivation_replace_wired():
    """Inaktiv/Ersetzen: Service, Schemas und Endpunkte vorhanden + Validierung."""
    import pytest as _pytest
    from app.services import deactivation
    from app.schemas.deactivation import DeactivateRequest
    from app.models import Article, Order

    for f in ("consume_parents", "article_impact", "deactivate_article",
              "cancel_order_effects", "duplicate_article", "duplicate_order"):
        assert hasattr(deactivation, f)
    # Lagerplatz-Helfer sind mit dem Datensatztyp entfallen.
    for gone in ("storage_location_in_use", "duplicate_storage_location"):
        assert not hasattr(deactivation, gone)
    # Reaktivieren von Artikeln ist entfallen (inaktiv ist endgültig).
    assert not hasattr(deactivation, "article_reactivation_blocker")
    # replaced_by_id auf beiden Datensatztypen
    for m in (Article, Order):
        assert hasattr(m, "replaced_by_id")
    # orders_mode-Validierung
    assert DeactivateRequest().orders_mode == "phase_out"
    assert DeactivateRequest(orders_mode="cancel").orders_mode == "cancel"
    with _pytest.raises(Exception):
        DeactivateRequest(orders_mode="bogus")


def test_system_never_plans_process_steps():
    """**Der Kern:** das System legt von sich aus KEINEN Prozessschritt an. Der Nutzer
    modelliert den Ablauf; physisch nötige Transporte entstehen zur Laufzeit als
    Bereitstellungs-Unter-Auftrag (``services/provisioning.py``), nicht als Modul im Plan.

    Beim Modellieren ist gar nicht entscheidbar, ob eine Bewegung nötig sein wird – ob das
    Teil schon am Band liegt oder in Halle B, zeigt sich erst zur Laufzeit. Genau daran
    sind die früheren Zwangs-Bewegungen gescheitert."""
    import importlib

    import pytest

    from app.routers import article_process
    from app.services import selling

    # Das Säe-Modul ist ersatzlos entfernt.
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.services.process_steps")

    # Weder Router noch Shop-Pfad legen eine Bewegung an.
    router_src = _inspect_source(article_process)
    assert "seed" not in router_src
    shop_src = _inspect_source_fn(selling._create_multiline_sale_order)
    assert 'step_type="movement"' not in shop_src


def _inspect_source(mod):
    import inspect as _i
    return _i.getsource(mod)


def _inspect_source_fn(fn):
    import inspect as _i
    return _i.getsource(fn)


def test_provisioning_keeps_parent_subject_binding():
    """**Kritisch:** eine Bereitstellung darf ``subject_of_order_id`` NICHT umhängen.

    Die Instanz gehört weiterhin dem Eltern-Auftrag – die Bereitstellung transportiert sie
    bloss. Anders als bei Abweichung/Retoure (wo der Übergang gewollt ist) verlöre der
    Eltern sonst sein Subjekt: bei einem Erzeugungsauftrag stünde er ohne Instanzen da."""
    from app.services import provisioning

    # Geprüft wird die **Zuweisung**, nicht die Erwähnung: Kommentare dürfen (und sollen)
    # erklären, warum hier gerade NICHT umgehängt wird.
    for fn in (provisioning._create, provisioning._settle):
        src = _inspect_source_fn(fn)
        assert "subject_of_order_id =" not in src, f"{fn.__name__} hängt die Bindung um"
    # Die **Tatsache** prüfen, nicht die Schreibweise: die Bereitstellung hält die Instanz
    # nur über den Historien-Link fest (seit #413 mitsamt der übernommenen Menge).
    assert "record_link(db, inst.object_id, sub.id" in _inspect_source_fn(provisioning._create)


def test_provisioning_has_fixed_subject_and_cannot_recurse():
    """Eine Bereitstellung hat ein **festes Subjekt** (die Instanzen existieren, sie liegen
    nur falsch) – also keine Fehlmengen-Ableitung, kein Lager-FIFO. Und sie löst **keine
    weitere Bereitstellung** aus: sie IST die Bereitstellung (Rekursions-Schutz)."""
    from app.services import provisioning
    from app.services.subject import is_fixed_subject, is_provisioning

    class _O:
        reason = "provisioning"
    assert is_provisioning(_O()) and is_fixed_subject(_O())

    src = _inspect_source_fn(provisioning.ensure_provisioning)
    assert "order.reason == REASON" in src   # Selbst-Ausschluss


def test_provisioning_target_covers_every_step_type():
    """Jeder Schritttyp muss einen **auflösbaren** Bereitstellungsort haben – sonst gäbe es
    einen Schritt, für den das System nicht weiss, wohin sein Material soll. Die Zuordnung
    ist deklariert (``event_types``), die Auflösung kennt jeden deklarierten Wert."""
    from app.domain import event_types
    from app.services import provisioning

    src = _inspect_source_fn(provisioning.target_for)
    for et in event_types.REGISTRY.values():
        kind = et.provisioning
        if kind in (event_types.PROV_NONE, event_types.PROV_NOWHERE):
            continue          # kein fester Ort – bewusst
        const = {event_types.PROV_RECEIVING: "PROV_RECEIVING",
                 event_types.PROV_CUSTOMER: "PROV_CUSTOMER",
                 event_types.PROV_PRODUCT: "PROV_PRODUCT"}[kind]
        assert const in src, f"{et.key}: Bereitstellungsort {kind} wird nicht aufgelöst"


def test_provisioning_settles_only_inside_one_address():
    """Die Abstufung: **innerhalb derselben Adresse** bucht das System selbst (zwanzig Meter
    durch die Halle brauchen kein Formular), **über Adressgrenzen** bleibt der Auftrag offen
    für Tarif/Label/Quittierung. Entschieden wird das mit der bestehenden Logistik-
    Klassifikation (ADR 005) – kein zweites Regelwerk.

    Und: die automatische Buchung wird als **Behauptung** gekennzeichnet, nicht als bezeugte
    Übergabe (niemand hat gescannt)."""
    from app.services import provisioning

    internal = _inspect_source_fn(provisioning._is_internal)
    assert "logistics.classify_movement" in internal
    assert '!= "outside"' in internal
    assert "return False" in internal        # im Zweifel den Menschen fragen

    settle = _inspect_source_fn(provisioning._settle)
    assert "nicht quittiert" in settle


def test_resource_embed_per_product_breakdown():
    """Ressource-Embed zeigt den Verbrauch je Produkt-Instanz (welche Instanz wohin)."""
    from app.schemas.resource import ResourceEmbed, ResourcePlanItem, ResourceProductPlan

    assert "products" in ResourceEmbed.model_fields
    assert "into_instance_id" in ResourcePlanItem.model_fields
    plan = ResourceProductPlan(instance_id=100_000_050, kind="unit", quantity=1)
    assert plan.components == []


def test_no_process_object_anymore():
    """Prozesse sind keine eigenständigen Objekte mehr (kein Modell/Schema/Router)."""
    import importlib

    import pytest

    import app.models as models
    assert not hasattr(models, "Process")
    assert not hasattr(models, "ArticleProcessLink")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.schemas.process")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.routers.processes")


def test_step_belongs_to_article_or_order():
    """Ein Schritt hängt am Artikel (Entstehung) ODER am Auftrag (CUSTOM) – kein process_id."""
    from app.models import ArticleProcessStep
    cols = ArticleProcessStep.__table__.columns.keys()
    assert "article_id" in cols and "order_id" in cols
    assert "process_id" not in cols


def test_order_modes_make_and_custom():
    """Auftrag trägt einen Modus (make|custom) statt Prozesswahl/Subjekt-Instanz."""
    import pytest

    from app.models import Order
    from app.schemas.order import OrderCreate, OrderResponse

    # Kein Modus-Flag mehr – die Subjektart wird abgeleitet (services/subject.py).
    for gone in ("mode", "process_id", "subject_instance_id"):
        assert gone not in Order.__table__.columns.keys()
    # Anker ist IMMER Artikel + Menge (kein Instanz-Pfad mehr bei der Anlage).
    assert OrderCreate(article_id=100_000_001, quantity=5).quantity == 5
    with pytest.raises(ValueError):
        OrderCreate()                                  # Artikel/Menge fehlen
    with pytest.raises(ValueError):
        OrderCreate(article_id=100_000_001, quantity=0)  # Menge muss > 0 sein
    for f in ("subject_role", "stock_effect", "sale", "instances", "steps"):
        assert f in OrderResponse.model_fields
    for gone in ("mode", "process_id", "process_source", "subject_instance_id"):
        assert gone not in OrderResponse.model_fields


def test_subject_role_and_stock_effect_declared():
    """Subjektart + Bestandswirkung werden aus den Schritt-Typen ABGELEITET (REA-Registry):
    Verkauf greift FIFO auf den Bestand zu (stock) und mindert ihn (decrease)."""
    from app.domain import event_types

    assert event_types.derive_subject_mode({"sale"}) == "stock"
    assert event_types.derive_subject_mode({"purchase", "resource"}) == "produce"
    assert event_types.derive_subject_mode({"inspection", "movement"}) == "instance"
    # gemischter Prozess: Verkauf dominiert die Subjektart (stock ≻ produce ≻ instance)
    assert event_types.derive_subject_mode({"purchase", "sale"}) == "stock"

    assert event_types.aggregate_stock_effect({"sale"}) == "decrease"
    assert event_types.aggregate_stock_effect({"purchase"}) == "increase"
    assert event_types.aggregate_stock_effect({"purchase", "sale"}) == "mixed"
    assert event_types.aggregate_stock_effect({"inspection", "movement"}) == "neutral"


def test_subject_service_derives_kind_without_mode_flag():
    """Das Subjekt wird ohne Modus-Flag abgeleitet; FIFO-Allokation lebt im Bestandsmodul."""
    from app.services import subject
    from app.services.inventory import available_qty, fifo_candidates

    assert callable(subject.subject_kind)         # chosen ≻ stock ≻ produce
    assert callable(subject.materialize_subject)
    assert callable(subject._allocate_stock_subject)
    assert callable(fifo_candidates) and callable(available_qty)


def test_instance_order_ref_has_no_mode_flag():
    """Die Auftragsliste einer Instanz zeigt Rollen + Status (kein Modus-Flag mehr)."""
    from app.schemas.instance import InstanceOrderRef

    assert "mode" not in InstanceOrderRef.model_fields
    for f in ("object_id", "status", "roles", "at"):
        assert f in InstanceOrderRef.model_fields


def test_every_step_module_is_universally_usable():
    """**Jedes Prozessschrittmodul ist universell einsetzbar** – am Artikel wie am Auftrag
    (Testnotiz #246).

    Früher waren Verkauf/Verschrotten/Sperren im Artikel-Prozess gesperrt, weil sie „auf
    vorhandenen Bestand wirken". Das stimmt, ist aber kein Grund für ein Verbot: ein
    Artikel-Prozess läuft immer IN einem Auftrag, dessen Instanzen existieren, sobald der
    Schritt an der Reihe ist. Eine Sperre gegen selten sinnvolle Kombinationen kostet mehr,
    als sie nützt.
    """
    from app.domain import event_types

    art = event_types.allowed_step_types("article")
    order = event_types.allowed_step_types("order")
    assert set(art) == set(order) == set(event_types.STEP_TYPES)
    # Jeder in der Registry deklarierte Typ ist auch wählbar – keine toten Module.
    assert {"purchase", "resource", "inspection", "movement", "scrap", "block", "sale", "document"} == set(art)


def test_webshop_url_is_validated():
    """Ein Webshop-Link muss ein gültiges http(s)-URL sein."""
    import pytest
    from app.schemas.article_process_step import ArticleProcessStepCreate

    ok = ArticleProcessStepCreate(step_type="purchase", mode="webshop",
                                  webshop_url="https://shop.example.com/artikel/5")
    assert ok.webshop_url.startswith("https://")
    for bad in ("kein-link", "ftp://example.com", "https://", "example.com"):
        with pytest.raises(ValueError):
            ArticleProcessStepCreate(step_type="purchase", mode="webshop", webshop_url=bad)


def test_order_update_accepts_instance_selection():
    """Die gewählten **Anteile** lassen sich im Entwurf anpassen (Mehrfachauswahl)."""
    from app.schemas.order import InstancePick, OrderUpdate

    assert "picks" in OrderUpdate.model_fields
    upd = OrderUpdate(picks=[InstancePick(instance_object_id=100_000_010),
                             InstancePick(instance_object_id=100_000_011, quantity=2,
                                          from_order_object_id=100_000_099)])
    assert [p.instance_object_id for p in upd.picks] == [100_000_010, 100_000_011]
    assert upd.picks[0].from_order_object_id is None      # freier Anteil
    assert upd.picks[1].from_order_object_id == 100_000_099


def test_sale_step_mirrors_purchase():
    """Verkauf = kaufmännisches Schrittmodul (Spiegel der Beschaffung), ohne Nummer."""
    from app.models import Sale
    from app.schemas.sale import ALLOWED_STATUS, SaleEmbed, SaleUpdate
    from app.services import process

    assert Sale.__tablename__ == "sales"
    assert not hasattr(Sale, "object_id")
    assert "object_id" not in SaleEmbed.model_fields
    assert set(ALLOWED_STATUS) == {"requested", "confirmed", "invoiced", "paid", "cancelled"}
    assert process._FACT_MODEL["sale"] is Sale
    assert process.STEP_LABELS["sale"] == "Verkauf"
    assert "status" in SaleUpdate.model_fields


def test_sale_fact_status_pure_mapping():
    """Verkauf-Schritt erledigt = 'paid'; fehlgeschlagen = 'cancelled' (rein)."""
    from types import SimpleNamespace
    from app.services.process import _fact_status

    assert _fact_status("sale", None) == "open"
    assert _fact_status("sale", SimpleNamespace(status="requested")) == "open"
    assert _fact_status("sale", SimpleNamespace(status="invoiced")) == "open"
    assert _fact_status("sale", SimpleNamespace(status="paid")) == "done"
    assert _fact_status("sale", SimpleNamespace(status="cancelled")) == "failed"


def test_recurrence_lives_on_order_not_separate_object():
    """Wiederkehr ist eine Eigenschaft des Auftrags – kein eigenes Objekt mehr."""
    from app.models import Order
    import app.models as models

    # Kein separates RecurringOrder-Objekt mehr
    assert not hasattr(models, "RecurringOrder")
    # Auftrag trägt die Wiederkehr-Konfiguration
    for col in ("recurrence_active", "recurrence_interval_days", "recurrence_lead_time_days",
                "recurrence_anchor", "recurring_parent_id"):
        assert col in Order.__table__.columns.keys()


def test_recurrence_due_pure():
    """``recurrence_due``: Entwurf + Termin − Vorlaufzeit erreicht → fällig (rein)."""
    from datetime import date, timedelta
    from app.models import Order
    from app.services.orders import recurrence_due

    today = date.today()
    due = Order(status="draft", recurrence_active=True, recurrence_lead_time_days=30,
                recurrence_anchor=today + timedelta(days=10))   # in 10 T fällig, Vorlauf 30 → jetzt
    assert recurrence_due(due) is True
    not_yet = Order(status="draft", recurrence_active=True, recurrence_lead_time_days=5,
                    recurrence_anchor=today + timedelta(days=60))
    assert recurrence_due(not_yet) is False
    # Nicht wiederkehrend / nicht Entwurf → nie fällig
    assert recurrence_due(Order(status="draft", recurrence_active=False)) is False
    assert recurrence_due(Order(status="completed", recurrence_active=True)) is False


def test_movement_has_tracking_for_outbound():
    """Bewegung trägt optionale Sendungsverfolgung (Versand zum Kunden)."""
    from app.models import Movement
    from app.schemas.movement import MovementEmbed, MovementUpdate

    for col in ("tracking_number", "carrier"):
        assert col in Movement.__table__.columns.keys()
        assert col in MovementUpdate.model_fields
        assert col in MovementEmbed.model_fields


def test_instance_has_subject_marker():
    """Bestands-Subjekte (Verkauf/Entnahme) sind je Auftrag markiert (subject_of_order_id)."""
    from app.models import Instance
    assert "subject_of_order_id" in Instance.__table__.columns.keys()


def test_object_id_sequence_ensured_outside_advisory_lock():
    """Der Nummernkreis-Generator (object_id_seq) wird bei JEDEM Start sichergestellt –
    NICHT hinter dem Advisory-Lock. Sonst startet ein Worker ohne Sequence und jede
    Objektanlage endet in einem 500 (nextval auf fehlende Sequence)."""
    import inspect as _inspect
    from app import main

    src = _inspect.getsource(main.lifespan)
    # Sequence-Sicherstellung steht VOR den gelockten Fixups
    assert "_ensure_object_id_sequence()" in src
    assert src.index("_ensure_object_id_sequence()") < src.index("_run_startup_fixups_once()")


def test_object_registry_shape_repaired_on_startup():
    """Eine veraltete `objects`-Tabelle (ohne `object_id`) wird beim Start
    repariert – sonst schlägt JEDE Objektanlage fehl (column object_id … does not
    exist). Läuft unbedingt und vor dem Registry-Backfill."""
    import inspect as _inspect
    from app import main

    assert callable(main._ensure_object_registry_shape)
    src = _inspect.getsource(main.lifespan)
    assert "_ensure_object_registry_shape()" in src
    assert src.index("_ensure_object_registry_shape()") < src.index("_run_startup_fixups_once()")


def test_unhandled_errors_return_structured_json():
    """Letzte Auffanglinie: unbehandelte Fehler liefern strukturiertes JSON (statt
    text/plain «Internal Server Error»), damit der Client die Ursache lesen kann."""
    from app.main import app
    from app.core.config import get_settings

    assert Exception in app.exception_handlers          # globaler Handler registriert
    assert hasattr(get_settings(), "app_env")           # Umgebung steuert Detail-Offenlegung


# ─── Deklarative Ereignis-Registry (REA-Kern) ───────────────────────────────────

def test_event_type_registry_declares_polarity():
    """REA-Kern: jeder Schritttyp DEKLARIERT seine Bestands-Polarität + Subjektrolle in
    EINER Registry (statt verstreuter Dicts oder einer aus der Prozessform erratenen
    Richtung)."""
    from app.domain import event_types as ev

    assert set(ev.STEP_TYPES) == {"purchase", "resource", "inspection", "movement", "scrap", "block", "sale", "document"}
    assert ev.RESOURCE_TYPES == ("resource",)   # consume/tool-Aliase entfernt
    # Polarität ist deklariert, nicht abgeleitet:
    assert ev.polarity("purchase") == ev.INCREASE
    assert ev.polarity("resource") == ev.INCREASE
    assert ev.polarity("sale") == ev.DECREASE
    assert ev.polarity("scrap") == ev.DECREASE     # Verschrotten mindert den Bestand
    assert ev.subject_role("scrap") == ev.INSTANCE  # wirkt auf bestehende Instanzen
    assert ev.polarity("movement") == ev.MOVE
    assert ev.polarity("inspection") == ev.NEUTRAL
    # Verkauf UND Gutschrift laufen über EINEN `sale`-Schritt (Modus aus dem Subjekt abgeleitet) –
    # es gibt keinen eigenen `refund`-Schritttyp mehr.
    assert "refund" not in ev.REGISTRY
    # Vorzeichen fürs Ledger (Event-Payload-Anreicherung):
    assert ev.delta_sign("purchase") == 1
    assert ev.delta_sign("sale") == -1
    assert ev.delta_sign("movement") == 0


def test_legacy_resource_aliases_removed():
    """consume/tool sind keine eigenen Schritttypen mehr – nur noch 'resource'
    (Modus je Zeile). Labels/Fachtabellen stammen aus der Registry."""
    from app.services.process import STEP_LABELS, _FACT_MODEL, RESOURCE_STEP_TYPES

    for alias in ("consume", "tool"):
        assert alias not in STEP_LABELS
        assert alias not in _FACT_MODEL
    assert RESOURCE_STEP_TYPES == ("resource",)
    assert set(STEP_LABELS) == {"purchase", "resource", "inspection", "movement", "scrap", "block", "sale", "document"}
    assert STEP_LABELS["resource"] == "Ressource"


def test_scrap_step_is_wired_end_to_end():
    """«Verschrotten» (scrap) ist ein vollwertiger Schritttyp: deklarierte Polarität,
    eigene Fachtabelle (Disposal), Service setzt disposition='scrapped' + schliesst ab."""
    import inspect as _inspect

    from app.domain import event_types as ev
    from app.models import Disposal
    from app.schemas.disposal import ScrapUpdate
    from app.schemas.order import OrderResponse, OrderStepInfo
    from app.services import process, scrap

    # Registry: Verschrotten mindert Bestand, wirkt auf bestehende Instanzen, Fact = Disposal.
    assert ev.REGISTRY["scrap"].fact == "Disposal"
    assert process._FACT_MODEL["scrap"] is Disposal
    # Fachtabelle (Abschluss-Marker, keine eigene Objektnummer)
    assert Disposal.__tablename__ == "disposals"
    assert "object_id" not in Disposal.__table__.columns.keys()
    # Schritt gilt als erledigt, sobald eine Disposal-Zeile existiert
    assert process._fact_status("scrap", None) == "open"
    assert process._fact_status("scrap", object()) == "done"
    # Embed im Auftrag/Schritt verfügbar
    assert "disposal" in OrderStepInfo.model_fields
    assert "disposal" in OrderResponse.model_fields
    # Service setzt disposition='scrapped' und schliesst den Schritt ab
    src = _inspect.getsource(scrap)
    assert 'inst.disposition = "scrapped"' in src
    assert "recompute_completion" in src
    # Mindestens eine Instanz wählen (kein leeres Verschrotten)
    assert ScrapUpdate().instance_ids == []


# ─── qc_status → quality + disposition (zwei orthogonale Achsen) ─────────────────

def test_qc_status_split_into_quality_and_disposition():
    """Das überladene ``qc_status`` ist in zwei orthogonale Achsen getrennt:
    ``quality`` (QC-Verdikt) + ``disposition`` (Verbleib). Einzelfeld gibt es nicht mehr."""
    from app.models import Instance
    from app.schemas.instance import InstanceEmbed, InstanceResponse

    cols = Instance.__table__.columns.keys()
    assert "quality" in cols and "disposition" in cols
    assert "qc_status" not in cols
    for schema in (InstanceResponse, InstanceEmbed):
        assert "quality" in schema.model_fields and "disposition" in schema.model_fields
        assert "qc_status" not in schema.model_fields


def test_in_stock_clauses_combine_both_axes():
    """«Verfügbar» = quality=passed UND disposition=in_stock – EINE Helper-Stelle
    (von Bestand/FIFO/Betriebsmittel geteilt, keine Drift)."""
    from app.services.inventory import in_stock_clauses

    clauses = in_stock_clauses()
    assert len(clauses) == 3   # quality, disposition, quantity > 0
    rendered = " ".join(str(c) for c in clauses)
    assert "quality" in rendered and "disposition" in rendered


def test_instance_order_link_is_immutable_history():
    """Die Auftrags-Historie einer Instanz hängt an einer UNVERÄNDERLICHEN Verweis-Tabelle
    (nicht an den wandernden Zeigern subject_/reserved_for_order_id)."""
    import app.models as models
    from app.models import InstanceOrderLink

    assert InstanceOrderLink.__tablename__ == "instance_order_links"
    assert "InstanceOrderLink" in models.__all__
    for col in ("instance_object_id", "order_id"):
        assert col in InstanceOrderLink.__table__.columns.keys()
    # KEINE eigene Objektnummer (läuft als reine Verknüpfung)
    assert "object_id" not in InstanceOrderLink.__table__.columns.keys()


def test_claim_clauses_use_free_capacity():
    """Verfügbarkeit/FIFO richtet sich nach der **freien Restmenge** (quantity −
    reserved_quantity), nicht nach einem Ganz-Instanz-Schloss: eine Charge mit freier
    Restmenge bleibt verfügbar (mengengenaue Reservierung, keine Teilung)."""
    from app.services.inventory import claim_clauses

    free = claim_clauses(None)
    assert len(free) == 1
    rendered = " ".join(str(c) for c in free)
    assert "reserved_quantity" in rendered and "quantity" in rendered
    assert "subject_of_order_id" not in rendered   # Vormerkung sperrt NICHT

    own = claim_clauses(42)
    own_rendered = " ".join(str(c) for c in own)
    assert "reserved_quantity" in own_rendered and " OR " in own_rendered   # + eigene Reservierung


def test_abort_is_reversible_and_supply_not_special_cased():
    """Abbruch ist ein Antrag: solange der Folgeauftrag Entwurf ist, kann er zurückgenommen
    werden (deviation.revoke) → Original läuft unverändert weiter. Nachschub-Kinder werden
    beim Abbruch NICHT mehr gesondert deaktiviert (Orphan-Nachschub → freier Bestand)."""
    import inspect as _inspect
    from app.routers import orders
    from app.services import deactivation, deviation

    assert hasattr(deviation, "revoke") and hasattr(orders, "revoke_followup")
    assert 'status != "draft"' in _inspect.getsource(deviation.revoke)   # nur Entwurf rücknehmbar
    # Die Aufräumarbeit selbst liegt in ``detach_sub_order`` – geteilt mit dem Abbruch eines
    # Unter-Auftrags, damit beide Türen dasselbe tun. Geprüft wird darum das Modul.
    rv = _inspect.getsource(deviation)
    assert "abort_into_id = None" in rv               # ausstehender Abbruch gelöscht
    # Instanzen ans Original zurück – hält der Eltern noch eine Reservierung, wandert die
    # Subjekt-Bindung dorthin ZURÜCK statt auf None (Review 2026-07).
    assert "inst.subject_of_order_id = (" in rv and "reserved_for" in rv
    # Endpoint delegiert an revoke.
    assert "deviation.revoke(" in _inspect.getsource(orders.revoke_followup)
    # Keine Nachschub-Sonderbehandlung mehr beim Abbruch.
    assert 'reason == "supply"' not in _inspect.getsource(deactivation.cancel_order_effects)


def test_get_order_self_heals_missing_step_facts():
    """Beim Lesen eines FREIGEGEBENEN Auftrags werden fehlende Beschaffungs-/Verkaufsbelege
    idempotent nachgezogen, damit die Prozessschritt-Details immer erscheinen (nie ein leeres
    Panel). Nur Personal, nur purchase/sale."""
    import inspect as _inspect
    from app.routers import orders

    assert hasattr(orders, "_ensure_step_facts")
    src = _inspect.getsource(orders._ensure_step_facts)
    assert 'order.status != "released"' in src          # nur freigegebene Aufträge
    assert "instantiate_purchase(" in src and "sale_svc.instantiate_for_order(" in src
    # get_order ruft die Selbstheilung vor dem Response-Aufbau.
    assert "_ensure_step_facts(" in _inspect.getsource(orders.get_order)


def test_buyer_can_self_procure_in_supplier_mode():
    """Beschaffung «auf Lieferant» ist nie eine Sackgasse: der Besteller (Mitarbeiter) darf
    die Bestellsumme selbst erfassen UND direkt bestellen – auch ohne zugewiesenen Lieferanten.
    Der zugewiesene Lieferant darf weiterhin selbst offerieren; ein fremder Lieferant nicht."""
    from types import SimpleNamespace
    from app.services import purchase

    staff = SimpleNamespace(role="employee", id=1)
    po_no_sup = SimpleNamespace(mode="supplier", supplier_id=None, status="requested")
    assert purchase._offer_editor(po_no_sup, staff) is True          # Felder editierbar
    assert purchase._editable_fields(po_no_sup, staff)               # Offerte-Felder freigegeben
    assert purchase._transition_allowed(po_no_sup, "ordered", staff) is True   # direkt bestellen
    assert purchase._transition_allowed(po_no_sup, "quoted", staff) is True    # oder Offerte erfassen

    po_sup = SimpleNamespace(mode="supplier", supplier_id=9, status="requested")
    owner = SimpleNamespace(role="supplier", id=9)
    other = SimpleNamespace(role="supplier", id=8)
    assert purchase._transition_allowed(po_sup, "quoted", owner) is True       # Lieferant offeriert
    assert purchase._offer_editor(po_sup, other) is False                      # fremder Lieferant nicht


def test_demand_supply_model_is_one_mechanism():
    """Bedarf-/Nachschub-Modell: ein nicht gedeckter Bedarf blockiert den Schritt (abgeleitet,
    kein Auto-Trigger); die Fehlmenge deckt ein Nachschub-Unter-Auftrag (reason='supply'), der
    bei Abschluss an den Eltern gepinnt wird. EIN Mechanismus (ERP-Knopf == Shop)."""
    import inspect as _inspect
    from app.services import orders, process, supply

    # Kern-API vorhanden.
    for fn in ("order_shortfalls", "step_shortfalls", "_step_blocked", "_peg_supply_to_parent"):
        assert hasattr(process, fn), fn
    assert hasattr(supply, "ensure_supply") and hasattr(orders, "release_order")
    assert not hasattr(process, "_release_dependent_sales")   # alte Make-Verkettung weg

    # 'blocked' ist ein abgeleiteter Schritt-Zustand (aus dem Bestand).
    bos = _inspect.getsource(process.build_order_steps)
    assert '"blocked"' in bos and "_step_blocked(db, order, d)" in bos

    # ensure_supply: rekursiv, idempotent, zyklensicher; legt reason='supply' an und gibt frei.
    es = _inspect.getsource(supply.ensure_supply)
    assert "ensure_supply(db, sup" in es                 # Rekursion (mehrstufige Stückliste)
    assert "_existing_open_supply" in es                 # Idempotenz
    assert "in chain" in es                              # Zyklus-Schutz über die Artikel-Kette
    assert 'reason="supply"' in es and "release_order(db, sup" in es

    # Pegging: Nachschub pinnt seine Stück bei Abschluss an den Eltern (reserve + Subjekt).
    peg = _inspect.getsource(process._peg_supply_to_parent)
    assert 'reason", None) != "supply"' in peg and "reserve(inst, parent.id" in peg

    # recompute_completion ruft das Pegging; die alte Verkettung ist ersetzt.
    rc = _inspect.getsource(process.recompute_completion)
    assert "_peg_supply_to_parent(db, order)" in rc

    # Nachschub ist KEINE Abweichung: er deckt einen Bedarf, er nimmt nichts heraus.
    assert 'Order.reason == "deviation"' in _inspect.getsource(
        __import__("app.services.deviation", fromlist=["x"]).open_deviations)

    # Freigabe ist EIN Pfad: Router, Shop-Zahlung und Nachschub nutzen release_order.
    assert "release_order(" in _inspect.getsource(__import__("app.routers.orders", fromlist=["x"]))
    assert "release_order(db, order" in _inspect.getsource(__import__("app.services.sale", fromlist=["x"])._release_on_payment)


def test_release_allows_partial_stock_no_hard_fail():
    """Freigabe scheitert NICHT mehr an Unterdeckung: das Subjekt wird teilweise reserviert,
    die Fehlmenge ist ein blockierter Schritt + Nachschub (kein 409 in der FIFO-Auffüllung)."""
    import inspect as _inspect
    from app.services import subject

    # Kern-Allokation (wiederverwendet von Einzel-Artikel-Auftrag UND Mehrpositionen).
    src = _inspect.getsource(subject._allocate_stock_for)
    # Der FIFO-Rest wirft keinen Bestands-Fehler mehr (Partielle Deckung erlaubt).
    assert "Nicht genügend freigegebener Bestand: benötigt" not in src
    assert "Partielle Deckung" in src


def test_subject_kind_follows_declared_step_roles():
    """#4b: Herstellung vs. Bestands-Operation wird aus der **deklarierten Subjekt-Rolle** der
    Schritte abgeleitet (REA-Registry, ``derive_subject_mode``/``SUBJECT_PRECEDENCE``) – NICHT
    aus der blossen Anwesenheit eines Schritts, NICHT aus einer Pin-Auswahl und NICHT aus einer
    Quellen-Übersteuerung (subject_source ist entfernt).

    Kern-Regel: ein Schritt, der Bestand **hereinbringt** (Beschaffung/Ressource → PRODUCE),
    lässt den Auftrag ERZEUGEN (neue Instanzen); nur ein Zugriff auf **vorhandenen** Bestand
    (Verkauf → STOCK, Bewegung/Prüfung/Verschrottung → INSTANCE) ist eine Bestands-Operation.
    Sonst würde ein Beschaffungs-Auftrag fälschlich als Bestands-Operation behandelt und
    scheiterte still an „kein Bestand" (keine Instanz, keine Objektnummer, keine Fehlermeldung)."""
    import inspect as _inspect
    from app.domain import event_types
    from app.services import subject, process

    # Verhalten der reinen Ableitung (ohne DB): PRODUCE-Schritte → produce, sonst stock.
    assert event_types.derive_subject_mode({"purchase"}) == event_types.PRODUCE
    assert event_types.derive_subject_mode({"resource"}) == event_types.PRODUCE
    assert event_types.derive_subject_mode({"sale"}) == event_types.STOCK
    assert event_types.derive_subject_mode({"movement"}) == event_types.INSTANCE
    assert event_types.derive_subject_mode({"purchase", "movement"}) == event_types.PRODUCE

    kind_src = _inspect.getsource(subject.subject_kind)
    mat_src = _inspect.getsource(subject.materialize_subject)
    # Ableitung über die Registry – keine „jeder Schritt = stock"-Verkürzung, keine
    # Quellen-Übersteuerung.
    assert "derive_subject_mode" in kind_src
    assert "subject_source" not in kind_src
    # Keine eigenen Schritte → Herstellung (produce), ein PRODUCE-Schritt bleibt Herstellung.
    assert 'return "produce"' in kind_src
    # materialize delegiert an subject_kind – die Fallunterscheidung steht dort, nicht hier.
    assert "subject_kind(db, order)" in mat_src
    # order_step_defs bleibt bei «eigene Schritte, sonst Artikel-Prozess» – die Auswahl
    # entscheidet dort NICHT mit (sonst verlöre ein abgeschlossener Auftrag rückwirkend
    # seinen Ablauf, sobald die Bindung gelöst ist).
    defs_src = _inspect.getsource(process.order_step_defs)
    assert "chosen_subjects" not in defs_src
    assert "article_steps(db, order.article_id)" in defs_src


def test_subject_kind_forces_stock_for_pooled_orders_without_steps():
    """Regression: ein Mehrpositionen-Auftrag (``order_lines``, ``article_id`` fehlt) hat
    KEINEN einzelnen Artikel-Prozess, den er sonst fahren könnte – ohne diesen Sonderfall
    hätte ``subject_kind`` ihn (mangels eigener Schritte) fälschlich als ``produce``
    eingestuft, und die Freigabe hätte still 0 Instanzen erzeugt (``order.article_id``/
    ``quantity`` sind ja NULL). Jetzt: pooled → immer ``stock``, fehlt der Ablauf noch,
    blockiert das (bestehende) „Bitte zuerst einen Prozessschritt definieren" die Freigabe
    statt eines stillen No-ops."""
    import inspect as _inspect
    from app.services import subject

    src = _inspect.getsource(subject.subject_kind)
    assert 'order.article_id is None and lines_for(db, order)' in src
    # Diese Prüfung steht VOR der has_custom_steps-Weiche (sonst zu spät).
    assert src.index("lines_for(db, order)") < src.index("order_custom_steps")


def test_reservation_becomes_firm_only_at_release():
    """#1: Der Pin im Entwurf merkt nur **vor** (subject_of_order_id); **scharf reserviert**
    (reserved_for_order_id) wird erst bei der Freigabe – mit Freigabe-Validierung."""
    import inspect as _inspect
    from app.routers import orders
    from app.services import subject

    pin_src = _inspect.getsource(orders._set_chosen_instances)
    assert "subject_of_order_id = order.id" in pin_src
    assert "reserved_for_order_id" not in pin_src        # Entwurf reserviert NICHT

    alloc_src = _inspect.getsource(subject._allocate_stock_for)
    assert "reserve(cand, order.id, take)" in alloc_src  # erst hier scharf (mengengenau)
    assert "next_object_id" not in alloc_src             # KEINE Teilung / neue Nummer
    # Freigabe-Validierung: nur freigegebene (passed/in_stock) Instanzen sind freigebbar
    # Die Bestands-Regel («freigegeben UND am Lager») steht nur noch an EINER Stelle –
    # als Query-Bedingung (in_stock_clauses) und als Objekt-Prüfung (is_in_stock).
    assert "is_in_stock" in alloc_src
    from app.services import inventory as _inv
    rule = _inspect.getsource(_inv.is_in_stock)
    assert 'quality == "passed"' in rule and 'disposition == "in_stock"' in rule
    assert "record_link" in alloc_src                   # Historie dauerhaft festhalten


def test_completion_releases_binding_history_survives():
    """#1/#4: Bei Abschluss werden Reservierung UND Bindung gelöst (Instanz wird wieder frei),
    aber die Auftrags-Historie bleibt über instance_order_links erhalten."""
    import inspect as _inspect
    from app.services import process, references, subject

    comp_src = _inspect.getsource(process.recompute_completion)
    assert "release(inst, order.id)" in comp_src          # Reservierung mengengenau lösen
    assert "inst.subject_of_order_id = None" in comp_src

    # Die Auftragsliste einer Instanz liest die dauerhafte Verknüpfung (nicht nur Zeiger).
    ref_src = _inspect.getsource(references._instance_hits)
    assert "InstanceOrderLink" in ref_src
    # order_instances zeigt die Subjekte auch nach Abschluss (über die Verknüpfung).
    oi_src = _inspect.getsource(subject.order_instances)
    assert "InstanceOrderLink" in oi_src


def test_no_batch_split_anywhere():
    """Eine Charge wird NIE in eine zweite Instanz mit eigener Objektnummer geteilt –
    weder bei der Subjekt-Allokation noch beim Reservieren oder Verbrauchen von Komponenten
    (die physische Etikett-/Objektnummer muss erhalten bleiben)."""
    import inspect as _inspect
    from app.services import subject, resource
    from app.models import Instance

    for fn in (subject._allocate_stock_subject, resource.reserve_resources, resource._consume_line):
        src = _inspect.getsource(fn)
        assert "next_object_id" not in src, f"{fn.__name__} darf keine neue Instanz-Nummer vergeben"

    # Reservierung wird mengengenau auf der Instanz geführt (Map + Summe), nicht durch Teilung.
    for col in ("reservations", "reserved_quantity"):
        assert col in Instance.__table__.columns.keys()


def test_order_deviation_fields_and_kind():
    """Abweichung = Auftrag mit Eltern (parent_order_id); Abbruch-Folgeauftrag via abort_into_id.
    Eine Abweichung ist subjektartig «deviation» und wirkt auf vorhandene Instanzen ohne
    Lager-Allokation; ohne eigene Schritte hat sie (noch) keinen Ablauf."""
    from types import SimpleNamespace
    from app.models import Order
    from app.services import subject

    for col in ("parent_order_id", "abort_into_id", "reason"):
        assert col in Order.__table__.columns.keys()

    # Abweichung = Unter-Auftrag mit reason='deviation' (ein Nachschub, reason='supply', ist KEINE).
    assert subject.is_deviation(SimpleNamespace(reason="deviation")) is True
    assert subject.is_deviation(SimpleNamespace(reason="supply")) is False
    assert subject.is_deviation(SimpleNamespace(reason=None)) is False

    import inspect as _inspect
    kind_src = _inspect.getsource(subject.subject_kind)
    assert 'is_deviation(order)' in kind_src and '"deviation"' in kind_src
    # materialize bindet Abweichungs-Instanzen ohne Stock-Allokation
    mat_src = _inspect.getsource(subject.materialize_subject)
    assert "_bind_deviation_subjects" in mat_src


def test_abort_is_a_deed_not_a_request():
    """**Abbrechen ist ein Vollzug, kein Antrag – und kein zweiter Knopf.**

    Früher blieb das Original «Abbruch ausstehend» (weiterhin ``released``) und wurde erst
    inaktiv, wenn der Folgeauftrag freigegeben war; bis dahin liess sich der Abbruch
    zurücknehmen. Ein Auftrag, den man abbrechen kann und der danach weiterläuft, ist aber
    nicht abgebrochen. Jetzt ist er im selben Moment inaktiv – und der Weg dorthin ist
    derselbe wie für jede Abweichung – und **kein eigener Schalter mehr**: bleibt dem Eltern
    nichts übrig, IST «Auftragsmenge reduzieren» der Abbruch (Testnotiz #366)."""
    import inspect as _inspect
    from app.routers import orders
    from app.services import deviation, process, recovery

    # Kein Flag und kein eigener Endpunkt mehr: der Abbruch ist die Konsequenz der
    # Unterdeckungs-Antwort, gestellt bei der Freigabe.
    assert not hasattr(orders, "open_deviation")
    cq = _inspect.getsource(recovery.confirm_quantity)
    assert "abort_parent(db, order, into, actor_id)" in cq and "r <= 0 for r in" in cq
    # … und der Alt-Weg legt keinen Folgeauftrag mehr an.
    assert "create_abort_followup" not in _inspect.getsource(orders)
    assert not hasattr(deviation, "create_abort_followup")
    assert not hasattr(deviation, "apply_abort_on_release")

    # Sofortiger Vollzug: inaktiv + Instanzen bleiben (sie gehören dem Abweichungsauftrag).
    ap = _inspect.getsource(deviation.abort_parent)
    assert 'parent.status = "inactive"' in ap and "keep_instances=True" in ap
    assert "parent_order_id=parent.object_id" in _inspect.getsource(deviation.create_deviation)

    # Kein «Abbruch ausstehend» mehr – und keine Pause: ``abort_into_id`` ist nur noch der
    # Zeiger «fortgeführt in …», der Abbruch selbst ist im Moment des Meldens vollzogen.
    assert not hasattr(process, "_is_paused_by_deviation")
    assert 'abort_into_id' not in _inspect.getsource(process.recompute_completion)
    # Ein abgebrochener Auftrag lässt sich nicht über das Zurücknehmen wiederbeleben.
    assert 'holder.status == "inactive"' in _inspect.getsource(deviation.revoke)


def test_a_deviation_can_have_its_own_deviation():
    """Auch eine Abweichung kann schiefgehen (die Nacharbeit misslingt) – dann muss man das
    melden können. Verboten bleibt nur das GLEICHZEITIGE Greifen zweier Vorgänge auf dieselbe
    Instanz; die Kette Abweichung → Abweichung ist erlaubt."""
    import inspect as _inspect
    from app.services import deviation

    src = _inspect.getsource(deviation.create_deviation)
    assert "if existing and existing.id != parent.id:" in src


def test_sale_customer_is_never_optional():
    """#2: Ein Verkauf ohne Kunde ist fachlich unzulässig – spätestens zur Bestätigung Pflicht."""
    import inspect as _inspect
    from app.services import sale

    src = _inspect.getsource(sale._apply_transition)
    assert "customer_id is None" in src
    assert "Kunde ist erforderlich" in src


def test_company_is_numbered_erp_record():
    """#5: Das Unternehmen ist ein vollwertiger ERP-Datensatz mit universeller Objektnummer.
    Die Nummer wird lazy bei der ersten Abfrage vergeben (kein Profil-Sonderfall mehr).

    Geprüft wird das **Modul** ``services/sites.py``, nicht eine einzelne Funktion: seit
    Migration 090 trägt ``company_settings`` mehrere Zeilen, und die Vergabe sitzt dort
    statt in ``admin.get_or_create_settings`` (das nur noch auf den Hauptsitz delegiert).
    Die Fachaussage ist unverändert – nur die Stelle hat sich verschoben."""
    import inspect as _inspect
    from app.models import CompanySettings
    from app.schemas.admin import CompanySettingsResponse
    from app.services import admin, sites

    assert "object_id" in CompanySettings.__table__.columns.keys()
    assert "object_id" in CompanySettingsResponse.model_fields
    # Die Objektnummer wird lazy vergeben (Typ "organization") – für JEDEN Standort.
    src = _inspect.getsource(sites)
    assert "object_id is None" in src
    assert 'next_object_id(db, "organization")' in src
    # …und «die Firma» bleibt über den vertrauten Einstieg erreichbar.
    assert "primary" in _inspect.getsource(admin.get_or_create_settings)


def test_company_object_id_assigned_at_startup_and_exposed_public():
    """#5-Bug: Die Objektnummer der Firma wird DETERMINISTISCH beim Start vergeben
    (nicht erst, wenn jemand die Admin-Einstellungen öffnet) und über den öffentlichen
    Settings-Endpoint mitgeliefert – sonst erscheint der ERP-Datensatz «Unternehmen» nie."""
    import inspect as _inspect
    from app import main
    from app.routers import admin as admin_router

    fixups = _inspect.getsource(main._run_startup_fixups_once)
    assert "_ensure_company_object_id()" in fixups
    assert "get_or_create_settings" in _inspect.getsource(main._ensure_company_object_id)
    # Öffentlicher Endpoint (vom ERP-Feed genutzt) liefert die Objektnummer mit.

    assert '"object_id": s.object_id' in _inspect.getsource(admin_router.get_public_settings)


# ─── Mehrpositionen-Aufträge (order_lines) + Verkaufs-Herkunft/Zahlungsart ─────────

def test_an_order_is_created_as_a_whole_or_not_at_all():
    """**Ein Auftrag entsteht als Ganzes – oder gar nicht** (Testnotiz #386).

    ``POST /erp/orders`` nimmt alles entgegen, was der Entwurf im Browser gesammelt hat:
    Artikel + Menge (Pflicht wie eh und je), weitere **Positionen**, den auftragseigenen
    **Ablauf**, die **Instanz-Auswahl** und die Antwort auf eine ausgelöste Unterdeckung –
    und gibt ihn im selben Aufruf frei. Erst dort bekommt er seine **Objektnummer**.

    Vorher entstand er beim Tippen (Auto-Save) und wartete als Entwurf; wer es sich anders
    überlegte, hinterliess eine nummernlose Leiche im System."""
    import pytest as _pytest
    from pydantic import ValidationError
    from app.schemas.order import OrderCreate

    with _pytest.raises(ValidationError):
        OrderCreate()   # Artikel + Menge sind Pflicht wie eh und je
    order = OrderCreate(article_id=1, quantity=2)
    assert order.quantity == 2
    for field in ("lines", "steps", "picks", "shortfall_response"):
        assert field in OrderCreate.model_fields, field
    # Auch eine **Position** bringt ihre Auswahl mit – sonst ginge sie beim Erteilen
    # verloren (der zweite Aufruf, den es hier nicht mehr gibt).
    from app.schemas.order import OrderLineCreate
    assert "picks" in OrderLineCreate.model_fields


def test_add_order_line_endpoint_exists_and_converts_anchor():
    """``POST /orders/{id}/lines`` macht einen bestehenden Einzel-Artikel-Auftrag (falls
    nötig) zu einem Mehrpositionen-Auftrag: der bisherige Anker (``article_id``/``quantity``)
    wandert in eine erste ``OrderLine`` (Position 0), bevor die neue Position dazukommt –
    Reservierungen/Instanzen-Historie bleiben unberührt, nur die Bedarfs-Darstellung wechselt.
    Funktioniert AUCH, nachdem der Auftrag schon gespeichert wurde (Entwurf genügt)."""
    import inspect as _inspect
    from app.routers import orders as orders_router

    # Der Entwurfs-Schutz sitzt am Endpunkt; die Auftrags-Anlage teilt sich mit ihm die
    # EINE Implementierung ``_add_line`` (sie kommt ohnehin nur aus dem Entwurf).
    assert 'order.status != "draft"' in _inspect.getsource(orders_router.add_order_line)
    src = _inspect.getsource(orders_router._add_line)
    assert "OrderLine(order_id=order.id, article_id=order.article_id" in src   # Anker -> Position 0
    assert "order.article_id = None" in src and "order.quantity = None" in src
    assert "next_pos" in src   # neue Position wird angehängt, nicht überschrieben


def test_pooled_orders_reuse_generic_step_editor():
    """Ein Mehrpositionen-Auftrag definiert seinen Ablauf über denselben generischen
    Step-Editor wie jeder andere Auftrag (``ProcessSteps``/``_create``) – KEIN Sonderpfad,
    KEINE automatisch angelegten Schritte bei der Positions-Anlage."""
    import inspect as _inspect
    from app.routers import orders as orders_router

    add_src = _inspect.getsource(orders_router._add_line)
    assert "ArticleProcessStep(" not in add_src   # legt KEINE Schritte automatisch an


def test_pooled_orders_need_no_special_case():
    """Verkauf ist EIN Schritt (auch bei mehreren Artikeln – mehrere Belege teilen sich ihn,
    ``services/sale.py``). Da das System keine Schritte mehr plant, gibt es für Mehrpositionen-
    Aufträge auch keinen Sonderfall: die Bereitstellung leitet sich je Schritt ab, unabhängig
    von der Zahl der Positionen."""
    import inspect as _inspect

    from app.routers import article_process
    from app.services import provisioning

    assert not hasattr(article_process._Owner, "seed")
    assert not hasattr(article_process._Owner, "sync")
    # Die Ableitung kennt nur Schritte, keine Positionen.
    src = _inspect.getsource(provisioning.ensure_provisioning)
    assert "pooled" not in src and "order_lines" not in src


def test_pooled_order_step_types_all_allowed():
    """Nutzer-Feedback: Prozessschrittmodule sollen universell einsetzbar sein – KEINE
    Mehrpositionen-spezifische Schritttyp-Whitelist mehr. Beschaffung/Ressource/
    Datenerfassung skalieren jetzt über ``order_lines.effective_quantity`` bzw. legen
    (Beschaffung) je Position eine eigene Fachzeile an, statt mit dem (bei Mehrpositionen
    NULL) ``order.quantity`` zu rechnen."""
    import inspect as _inspect
    from app.routers import article_process
    from app.services import inspection, order_lines, process, purchase, resource

    src = _inspect.getsource(article_process._create)
    assert 'owner.pooled' not in src
    assert 'nur Verkauf und Bewegung' not in src

    assert hasattr(order_lines, "effective_quantity")
    assert "purchase" in process.MULTI_FACT_STEP_TYPES

    purchase_src = _inspect.getsource(purchase.instantiate_for_order)
    assert "lines_for(db, order)" in purchase_src

    resource_src = _inspect.getsource(resource.reserve_resources)
    assert "effective_quantity(db, order)" in resource_src

    # Modul statt Einzelfunktion: die Fachaussage ist «die Datenerfassung rechnet nicht mit
    # ``order.quantity``», nicht «genau diese Zeile steht in genau dieser Funktion».
    assert "effective_quantity(db, order)" in _inspect.getsource(inspection)


def test_sale_step_resolves_via_step_not_first_match():
    """Regression: `PATCH /orders/{id}/sale` nahm früher blind die ERSTE Sale-Zeile des
    Auftrags (``Sale.filter(order_id=...).first()``). Jetzt wie movement/resource/inspection
    über ``resolve_exec_step`` aufgelöst (``step_id``) – und ALLE Belege des Schritts
    (``facts_for_step``) gemeinsam aktualisiert (``apply_update_bulk``), da ein Verkaufs-
    Schritt bei mehreren Artikeln mehrere Belege trägt."""
    import inspect as _inspect
    from app.routers import orders as orders_router

    src = _inspect.getsource(orders_router.update_order_sale)
    assert "Sale.filter" not in src.replace(" ", "")   # keine direkte Query mehr
    assert 'resolve_exec_step(db, order, "sale", data.step_id)' in src
    assert "facts_for_step(db, order, step)" in src
    assert "apply_update_bulk(db, sales, data, current_user)" in src


def test_sale_is_one_step_with_one_fact_per_article():
    """Kernregel (Nutzer-Feedback): Verkauf ist – wie Bewegung – EIN Prozessschritt, auch
    bei mehreren Artikeln (Mehrpositionen-Auftrag) – KEINE mehreren gleichartigen Schritte
    hintereinander. ``instantiate_for_order`` legt dafür je Artikel/Position EINEN Beleg an,
    alle unter demselben Schritt (``step_id``); ein Einzel-Artikel-Auftrag bleibt unverändert
    (ein Schritt, ein Beleg)."""
    import inspect as _inspect
    from app.services import process, sale as sale_svc

    inst_src = _inspect.getsource(sale_svc.instantiate_for_order)
    # EIN `sale`-Schritt (kein separater sequentieller); je Artikel/Position EIN Beleg unter
    # demselben step_id. Der Kredit-Modus (Gutschrift) wird aus dem Subjekt abgeleitet (is_return).
    assert 'd.step_type == "sale"' in inst_src
    assert "is_return(order)" in inst_src
    assert "lines_for(db, order)" in inst_src
    assert 'mode="direct"' in inst_src

    # Status-Aggregation: 'done' erst, wenn ALLE Belege eines Schritts bezahlt sind
    # (generisch für jeden Mehrfach-Beleg-Schritttyp, nicht nur Verkauf).
    assert process._aggregate_status("sale", []) == "open"

    class _S:
        def __init__(self, status):
            self.status = status
    assert process._aggregate_status("sale", [_S("paid"), _S("paid")]) == "done"
    assert process._aggregate_status("sale", [_S("paid"), _S("requested")]) == "open"
    assert process._aggregate_status("sale", [_S("cancelled"), _S("cancelled")]) == "failed"


def test_sale_price_is_single_source_of_truth_from_article():
    """«Preise vom Artikel übernehmen – Single Source of Truth»: der Betrag kommt aus der
    Shop-Preis-Pipeline (``article_prices``), NICHT aus einem frei getippten Feld. Bei
    MEHREREN Belegen (Mehrpositionen) ist der Betrag über die Aktualisierung nicht mehr
    direkt editierbar – nur bei genau einem Beleg (Einzel-Artikel-Fall bzw. Artikel ohne
    hinterlegten Preis) bleibt die manuelle Eingabe als Fallback möglich."""
    import inspect as _inspect
    from app.services import sale as sale_svc

    prefill_src = _inspect.getsource(sale_svc._prefill_price)
    assert "price_from_article(db, article_id, sale.quantity)" in prefill_src
    price_src = _inspect.getsource(sale_svc.price_from_article)
    assert "pricing.resolve_one_time_price(db, article_id)" in price_src
    assert "pricing.price_view_for" in price_src

    bulk_src = _inspect.getsource(sale_svc.apply_update_bulk)
    assert "_MONEY_FIELDS" in bulk_src
    assert "len(sales) == 1" in bulk_src   # nur bei einem Beleg frei editierbar


def test_sale_mode_and_payment_method_fields():
    """Herkunft (`mode`: shop/direct) + manuelle Zahlungsart (`payment_method`) sind an den
    Verkauf angehängt – der Shop setzt `mode='shop'`/`payment_method='stripe'` selbst; ein
    personal-erfasster Verkauf braucht KEIN Kartenterminal (Rechnung ist der übliche B2B-Weg,
    `payment_method` bleibt frei wählbar: invoice/cash/twint/other)."""
    import inspect as _inspect
    from app.services import sale as sale_svc, selling as selling_svc
    from app.schemas.sale import ALLOWED_PAYMENT_METHODS

    assert set(ALLOWED_PAYMENT_METHODS) == {"invoice", "cash", "twint", "other"}
    assert "payment_method" in sale_svc._EDITABLE and "payment_reference" in sale_svc._EDITABLE
    assert 'mode="shop"' in _inspect.getsource(selling_svc._create_multiline_sale_order)
    assert 'sale.payment_method = "stripe"' in _inspect.getsource(sale_svc._apply_stripe_snapshot)
    # Manuelle Zahlung ohne gewählte Art -> sinnvoller Default (Rechnung), kein Terminal nötig.
    assert '"invoice"' in _inspect.getsource(sale_svc._apply_transition)


def test_subject_shortfalls_aggregate_across_lines():
    """Mehrere Positionen eines Sammel-Auftrags können GLEICHZEITIG eine Fehlmenge haben
    (verschiedene Artikel) – ``_subject_shortfalls`` liefert ein Dict über ALLE Positionen,
    nicht nur den einen ``order.article_id`` des Einzel-Artikel-Falls. ``ensure_supply``
    iteriert bereits über dieses Dict (kein Zusatz-Code für Mehrpositionen-Nachschub nötig)."""
    import inspect as _inspect
    from app.services import process, supply

    src = _inspect.getsource(process._subject_targets)
    assert "lines_for(db, order)" in src
    assert "order.article_id and order.quantity" in src
    # ensure_supply iteriert bereits generisch über {article_id: qty} – funktioniert
    # unverändert für Mehrpositionen, sobald die Shortfalls mehrere Artikel enthalten.
    assert "order_shortfalls(db, order).items()" in _inspect.getsource(supply.ensure_supply)


def test_supply_pegging_recognizes_pooled_subject():
    """Regression: Nachschub-Pegging prüfte ob ``order.article_id == parent.article_id`` –
    bei einem Sammel-Auftrag (``parent.article_id`` ist NULL) war das NIE wahr, gepegते
    Stück wurden zwar reserviert, aber nicht als Subjekt markiert (fehlten in der
    Instanzen-Liste des Auftrags). Jetzt zusätzlich über die Positionen (``order_lines``)
    geprüft."""
    import inspect as _inspect
    from app.services import process

    src = _inspect.getsource(process._peg_supply_to_parent)
    assert "lines_for(db, parent)" in src
    assert "any(l.article_id == order.article_id for l in lines_for(db, parent))" in src


def test_article_deactivation_sees_pooled_orders():
    """Regression: die Wirkungsanalyse/Kaskade einer Artikel-Deaktivierung filterte Aufträge
    nur über ``Order.article_id.in_(ids)`` – ein Mehrpositionen-Auftrag referenziert seinen
    Artikel aber nur über ``order_lines`` und wäre NIE gefunden worden (Artikel liesse sich
    deaktivieren, während ein Mehrpositionen-Verkauf ihn noch aktiv reserviert)."""
    import inspect as _inspect
    from app.services import deactivation

    src = _inspect.getsource(deactivation._order_article_filter)
    assert "OrderLine.article_id.in_(ids)" in src
    impact_src = _inspect.getsource(deactivation.article_impact)
    deactivate_src = _inspect.getsource(deactivation.deactivate_article)
    assert "_order_article_filter(db, ids)" in impact_src
    assert deactivate_src.count("_order_article_filter(db, ids)") == 2


def test_deviation_release_does_not_require_article_and_quantity():
    """Regression (Nutzer-Feedback): eine Abweichung, die von einem Mehrpositionen-Eltern-
    Auftrag abstammt, erbt dessen ``article_id=NULL`` – hat aber KEINE ``order_lines`` (ihr
    Subjekt sind fixierte Instanzen). Die Freigabe-Validierung verlangte fälschlich Artikel
    + Menge und lehnte die Freigabe IMMER ab, sobald ein Ablauf (z. B. Bewegung) definiert
    war."""
    import inspect as _inspect
    from app.routers import orders as orders_router

    # Die Freigabe-Vorbedingungen stehen gebündelt in ``_assert_releasable`` (eine Stelle,
    # drei Gates) statt inline in ``update_order``.
    src = _inspect.getsource(orders_router._assert_releasable)
    assert 'not is_multiline and not subject.is_fixed_subject(order) and (not order.article_id or not order.quantity)' in src.replace("\n", " ").replace("  ", " ")
    assert "_assert_releasable(db, order)" in _inspect.getsource(orders_router._do_release)


def test_subscription_mixing_check_moved_to_sale_step_creation():
    """Regression (Nutzer-Feedback): "Ein Abo lässt sich nicht mit weiteren Positionen
    kombinieren" kam bisher sofort beim Hinzufügen EINER Position (add_order_line) – auch
    wenn gar kein Verkauf beabsichtigt war (z. B. nur Bewegen/Prüfen). Der Check gehört an
    das Hinzufügen des SALES-Prozessschritts."""
    import inspect as _inspect
    from app.routers import article_process, orders as orders_router

    add_src = _inspect.getsource(orders_router._add_line)
    assert "assert_sale_compatible" in add_src
    assert 'process.has_step(db, order, "sale")' in add_src   # nur relevant, wenn Sales existiert

    create_src = _inspect.getsource(article_process._create)
    assert 'data.step_type == "sale"' in create_src
    assert "assert_sale_compatible" in create_src


def test_subscription_mixing_recognizes_one_time_price_alongside_abo():
    """Regression: ein Artikel mit Abo-Preis UND zusätzlichem Einmalkauf-Preis wurde bisher
    (über ``resolve_primary_price``, das Abos zuerst sortiert) fälschlich als reiner
    Abo-Artikel behandelt und blockierte jede Mischung – obwohl der ERP-Verkauf ohnehin
    den Einmalkauf-Preis nutzt (``price_from_article``)."""
    import inspect as _inspect
    from app.services import pricing

    src = _inspect.getsource(pricing.is_subscription_exclusive)
    assert "resolve_one_time_price" in src


def test_purchase_and_inspection_use_effective_quantity_not_order_quantity():
    """Regression: Beschaffung/Ressource/Datenerfassung rechneten direkt mit
    ``order.quantity`` – bei einem Mehrpositionen-Auftrag ist das NULL, was den
    Ressourcen-Bedarf/die Stichprobenzahl auf 0 kollabieren liess (stiller Blindgänger,
    keine Fehlermeldung)."""
    import inspect as _inspect
    from app.services import inspection, process, resource

    assert "order.quantity or 0" not in _inspect.getsource(resource.reserve_resources)
    assert "order.quantity or 0" not in _inspect.getsource(resource.build_resource_embed)
    assert "(order.quantity or 0)" not in _inspect.getsource(process._component_needs)
    assert "(order.quantity or 0)" not in _inspect.getsource(process.step_shortfalls)
    assert "effective_quantity" in _inspect.getsource(inspection)
    assert "order.quantity" not in _inspect.getsource(inspection.required_count)


def test_purchase_creates_one_order_per_position_sharing_step_id():
    """Wie ``sale.instantiate_for_order``: bei einem Mehrpositionen-Auftrag legt der EINE
    Beschaffungs-Schritt je Artikel/Position eine eigene ``PurchaseOrder`` an (eigene
    Bestellsumme/Menge), alle unter demselben ``step_id``."""
    import inspect as _inspect
    from app.services import purchase

    src = _inspect.getsource(purchase.instantiate_for_order)
    assert "lines_for(db, order)" in src
    assert "step.id" in src

    bulk_src = _inspect.getsource(purchase.apply_update_bulk)
    assert "len(pos) == 1" in bulk_src
    assert "article_id" in bulk_src


def test_subscription_cancellation_has_minimum_commitment():
    """State-of-the-art Mindestbindung: ein Produktabo (wiederkehrende physische Lieferung)
    lässt sich nicht sofort nach Abschluss wieder kündigen; ein Nutzungsabo hat keine
    Mindestbindung. Personal darf trotzdem jederzeit kündigen (Kulanz)."""
    import inspect as _inspect
    from app.routers import shop
    from app.services import selling

    fn_src = _inspect.getsource(selling.earliest_cancellation_date)
    assert 'order.recurrence_kind != "product"' in fn_src
    assert "earliest > date.today()" in fn_src

    cancel_src = _inspect.getsource(shop.cancel_subscription)
    assert "earliest_cancellation_date(order)" in cancel_src
    assert 'user.role not in ("admin", "employee")' in cancel_src


def test_scrap_releases_all_reservations_of_the_instance():
    """Core-Fix: Verschrotten löst NICHT nur die Reservierung des eigenen Auftrags, sondern
    ALLE Reservierungen der Instanz. Ein verschrottetes Teil verlässt den Bestand endgültig –
    hing es an einem Fremd-/Eltern-Auftrag (z. B. eine Abweichung steuert eine für den
    Eltern-Verkauf reservierte Instanz aus), wird dessen Fehlmenge dadurch ehrlich sichtbar."""
    import inspect as _inspect
    from app.services import reservation, scrap

    assert hasattr(reservation, "release_all")
    src = _inspect.getsource(scrap)
    assert "release_all(inst)" in src
    assert "release(inst, order.id)" not in src   # alter, undichter Aufruf ist ersetzt


def test_shortfall_is_one_question_with_three_answers():
    """**Unterdeckung: eine Frage, drei Antworten.**

    Vorher waren es zwei Knöpfe («Aus Lager decken» + «Nachschub anlegen»), die dem Menschen
    eine Verfügbarkeitsfrage als Entscheidung vorlegten – und es fehlte die ehrlichste
    Antwort: *der Auftrag wird mit weniger fertig*. Jetzt:

    1. **Wartet** – ein Zustand, kein Knopf (siehe ``orders._fill_step_shortfall``).
    2. **Ersetzen** – EIN Weg: erst freier Lagerbestand (FIFO oder gezielt), Rest per Nachschub.
    3. **Menge bestätigen** – Soll sinkt auf das Gesicherte; bezahlte Ware ausgenommen."""
    import inspect as _inspect
    from app.services import process, recovery

    assert hasattr(process, "subject_shortfalls")
    # (2) Ersetzen: EIN Aufruf, beide Quellen – kein zweiter Knopf mehr.
    cover = _inspect.getsource(recovery.cover_shortfall)
    assert "_cover_from_stock" in cover and "ensure_supply" in cover
    assert "instance_object_ids" in _inspect.getsource(recovery._cover_from_stock)
    assert "fifo_candidates" in _inspect.getsource(recovery._fifo_cover)
    assert not hasattr(recovery, "cover_from_stock")   # der Einzelweg ist aufgegangen
    # (3) Menge bestätigen: Soll sinkt, Geld bleibt ehrlich.
    conf = _inspect.getsource(recovery.confirm_quantity)
    assert "subject_shortfalls" in conf and "_assert_not_paid" in conf
    assert 'Sale.status == "paid"' in _inspect.getsource(recovery._assert_not_paid)


def test_waiting_is_a_state_not_a_button():
    """Ist die Fehlmenge bereits in einer offenen Abweichung oder einem laufenden Nachschub
    gebunden, ist die Entscheidung getroffen – die Oberfläche sagt dann nur noch, WORAUF
    gewartet wird. Die frühere Trennung «Nachschub läuft» ↔ «Abweichung offen» (zwei Felder,
    zwei Sprachen) ist EIN Feld geworden."""
    import inspect as _inspect
    from app.schemas.order import OrderResponse, OrderStepInfo
    from app.services import orders, supply

    # Die Fehlmenge – und damit «worauf wird gewartet» – gehört dem **Auftrag**, nicht
    # einem Schritt: dieselbe Zahl hing vorher an jedem Subjekt-Schritt und fehlte ganz,
    # wenn der Prozess keinen hatte.
    assert "waiting_for" in OrderResponse.model_fields
    assert "shortfall" in OrderResponse.model_fields
    assert "waiting_for" not in OrderStepInfo.model_fields
    assert "shortfall" not in OrderStepInfo.model_fields
    # «Wer deckt gerade» ist EINE Definition (``supply.covering_sub_orders``) – Abweichung
    # UND Nachschub, und ein **steckengebliebener** zählt nicht als «läuft». Sonst zeigte
    # der Eltern für immer «wartet auf …» und blendete genau die Wege aus, die ihn befreien.
    src = _inspect.getsource(supply.covering_sub_orders)
    assert '"deviation"' in src and '"supply"' in src and "is_stalled" in src
    assert "covering_sub_orders" in _inspect.getsource(orders._fill_order_shortfall)


def test_what_happened_stays_at_its_step():
    """**Was entschieden wurde, steht im Ablauf** (Notiz #281): dass eine Fehlmenge ersetzt
    oder die Menge angepasst wurde, ist die Geschichte des Auftrags – ohne Spur sieht man
    später nur das Ergebnis. Quelle ist der **Event-Strom**, kein neues Feld; die Zuordnung
    macht die Schritt-id im Payload (dieselbe Frage wie beim Nachschub-Ursprung)."""
    import inspect as _inspect
    from app.schemas.order import OrderStepInfo, StepResolution
    from app.services import orders, process, recovery

    assert "resolutions" in OrderStepInfo.model_fields
    assert {"kind", "quantity_from", "quantity_to"} <= set(StepResolution.model_fields)
    rec = _inspect.getsource(recovery._record_at_step)
    assert "blocked_step_for_article" in rec and '"step_id"' in rec
    # Beide Antworten hinterlassen ihre Spur …
    src = _inspect.getsource(recovery)
    assert '_record_at_step(db, order, aid, "order.covered_from_stock"' in src
    assert '"order.quantity_confirmed"' in src
    # … und der Ablauf liest sie je Schritt zurück.
    fill = _inspect.getsource(orders._fill_step_resolutions)
    assert 'payload or {}).get("step_id") == step.id' in fill
    # EINE Stelle beantwortet «welcher Schritt vermisst diesen Artikel?» (Nachschub + Deckung).
    assert hasattr(process, "blocked_step_for_article")


def test_recovery_endpoints_are_wired_and_staff_gated():
    """Beide Antworten sind über freigegeben-gescopte Endpunkte erreichbar – und die beiden
    alten Einzelwege («/supply», «/cover-stock») sind zu EINEM «/cover» zusammengefallen."""
    import inspect as _inspect
    from app.routers import orders

    cover = _inspect.getsource(orders.cover_shortfall)
    assert "recovery.cover_shortfall" in cover
    assert 'order.status != "released"' in cover
    conf = _inspect.getsource(orders.confirm_quantity)
    assert "recovery.confirm_quantity" in conf and 'order.status != "released"' in conf
    assert not hasattr(orders, "cover_stock") and not hasattr(orders, "create_supply")
    assert not hasattr(orders, "reduce_demand")


def test_subject_shortfall_is_one_formula_for_all_order_kinds():
    """EINE Fehlmengen-Formel für ALLE Auftragsarten (kein subject_kind-Sonderpfad): ein
    Erzeugungsauftrag meldet Ausschuss (Soll − erzeugte gute Instanzen) GENAU wie ein
    Bestands-Auftrag eine ausgesteuerte Reservierung. Nur die Abweichung ist ausgenommen."""
    import inspect as _inspect
    from app.services import process

    src = _inspect.getsource(process._subject_shortfalls)
    secured = _inspect.getsource(process._secured_amounts)
    assert 'subject_kind(db, order) != "stock"' not in src   # kein Stock-only-Sonderpfad mehr
    assert "is_fixed_subject(order)" in src                    # Abweichung UND Retoure ausgenommen
    assert "Instance.order_id == order.id" in secured          # zählt selbst erzeugte gute Instanzen
    assert "reservations.has_key" in secured                   # + reservierte Bestands-Subjekte
    # Nachschub-Pegging kennt das Subjekt eines Erzeugungsauftrags (nicht nur stock):
    peg = _inspect.getsource(process._peg_supply_to_parent)
    assert 'subject_kind(db, parent) == "stock"' not in peg


def test_step_shortfall_exposes_stock_availability_for_recovery():
    """Der **Auftrag** trägt, womit sich der Bedarf aus vorhandenem Lagerbestand decken
    liesse (für «Ersetzen» / «Bestimmte Instanz wählen»)."""
    import inspect as _inspect
    from app.schemas.order import ShortfallInstance, StepShortfall
    from app.services import orders

    assert "available_instances" in StepShortfall.model_fields
    assert "available_quantity" in StepShortfall.model_fields
    assert set(ShortfallInstance.model_fields) >= {"object_id", "quantity"}
    assert "available_instances" in _inspect.getsource(orders._fill_order_shortfall)


def test_a_shortfall_pauses_the_whole_order():
    """**Ein Auftrag mit offener Fehlmenge ruht** – und zwar ganz (Testnotiz #354).

    Der Pause-Wächter an den Ausführungs-Endpunkten (``_assert_not_paused``) bleibt
    abgeschafft: es gibt nur EINEN Weg, einen Schritt anzuhalten, und der ist die Fehlmenge.
    Solange sie offen ist, ist der aktive Schritt ``blocked``; wer nicht warten will,
    beantwortet die Unterdeckungs-Frage (ersetzen / Menge reduzieren) und läuft weiter."""
    import inspect as _inspect
    from app.routers import orders
    from app.services import process

    assert "_assert_not_paused" not in _inspect.getsource(orders)
    blocked = _inspect.getsource(process._step_blocked)
    assert "is_paused(db, order)" in blocked
    paused = _inspect.getsource(process.is_paused)
    assert "_subject_shortfalls(db, order)" in paused and "open_provisioning" in paused


def test_the_subject_shortfall_is_type_agnostic():
    """Regression (Verkauf, aber nicht nur er): dass ein Schritt auf die Fertigware wartet,
    hängt NICHT an seinem Typ. ``step_shortfalls`` beginnt für **jeden** Typ mit der
    Fehlmenge des Auftrags und legt nur den **eigenen** Material-Bedarf obendrauf –
    weder eine Typ-Liste noch ein Registry-Flag entscheidet mit."""
    import inspect as _inspect
    from app.services import process

    assert not hasattr(process, "SUBJECT_STEP_TYPES")
    src = _inspect.getsource(process.step_shortfalls)
    assert "_subject_shortfalls(db, order)" in src and "_component_shortfall(db, order, step)" in src
    for literal in ("'sale'", '"sale"', "'movement'", '"movement"'):
        assert literal not in src, "Schritttypen gehören nicht in die Fehlmengen-Regel"


def test_sale_price_refreshes_from_article_when_added_after_release():
    """Regression: ein nachträglich hinterlegter Einmalpreis zieht am Verkauf nach – die
    Bestätigung holt ihn frisch (``_prefill_price``), sonst bliebe ein Mehrpositionen-Verkauf
    ohne editierbaren Betrag ewig stecken."""
    import inspect as _inspect
    from app.services import sale

    src = _inspect.getsource(sale._apply_transition)
    assert "_prefill_price" in src


def test_scrap_supports_partial_batch_quantity():
    """Verschrotten erlaubt eine Teilmenge einer Charge (analog Ressourcen-Teilentnahme):
    nur die Menge sinkt, die Instanz bleibt (keine Teilung); volle Menge → scrapped."""
    import inspect as _inspect
    from app.schemas.disposal import ScrapItem, ScrapUpdate
    from app.services import reservation, scrap

    assert "quantity" in ScrapItem.model_fields
    assert "items" in ScrapUpdate.model_fields
    assert hasattr(reservation, "take")
    src = _inspect.getsource(scrap)
    assert "take(" in src and "release_all" in src


def test_removing_a_line_folds_back_to_single_article_order():
    """Sinkt ein Mehrpositionen-Auftrag beim Löschen auf EINE Position, wird er wieder ein
    gewöhnlicher Einzel-Artikel-Auftrag (article_id/quantity zurück) – so aktualisieren sich
    die Ziel-Karten (Herstellen wieder möglich, kein stock-Zwang)."""
    import inspect as _inspect
    from app.routers import orders

    src = _inspect.getsource(orders.remove_order_line)
    assert "order.article_id = anchor.article_id" in src


def test_sale_step_serves_both_sale_and_credit():
    """Verkauf UND Gutschrift/Erstattung laufen über EINEN Schritttyp `sale` (Fachtabelle Sale).
    Kein eigener `refund`/`return`-Schritttyp mehr – der Kredit-Modus wird aus dem Subjekt
    (verkaufte Instanzen, is_return) abgeleitet."""
    from app.domain import event_types as ev
    from app.services.process import _FACT_MODEL
    from app.models import Sale

    assert "refund" not in ev.REGISTRY and "return" not in ev.REGISTRY
    assert "refund" not in ev.ORDER_STEP_TYPES and "return" not in ev.ORDER_STEP_TYPES
    assert _FACT_MODEL["sale"] is Sale
    # Gutschrift-Felder am Sale-Fact (für den Kredit-Modus + Stripe-Refund):
    for f in ("kind", "original_sale_id", "credit_note_number", "stripe_refund_id", "refunded_at"):
        assert f in Sale.__table__.columns


def test_return_order_is_fixed_subject():
    """Eine Retoure/Erstattung (reason='return') wirkt auf fixierte (verkaufte) Instanzen –
    wie eine Abweichung fixiertes Subjekt (keine Fehlmenge). Sie nimmt dem Eltern-Auftrag
    nichts heraus: der Verkauf ist abgeschlossen, es gibt nichts mehr zu sichern."""
    import inspect as _inspect
    from app.services import deviation, subject

    assert "return" in _inspect.getsource(subject.is_return)
    assert "is_deviation(order) or is_return(order)" in _inspect.getsource(subject.is_fixed_subject)
    # Nur eine Abweichung nimmt Instanzen heraus – eine Retoure zählt dort nicht mit.
    assert 'Order.reason == "deviation"' in _inspect.getsource(deviation.open_deviations)


def test_credit_mode_derived_from_subject_with_stripe_refund():
    """Der Kredit-Modus (Gutschrift) wird aus dem Subjekt abgeleitet (is_return): der `sale`-
    Schritt legt dann einen ``Sale kind='credit'`` an, Betrag aus dem Original abgeleitet,
    Gutschrift-Nummer bei Bestätigung, Stripe-Refund bei «bezahlt» (bzw. manuell)."""
    import inspect as _inspect
    from app.services import sale as sale_svc
    from app.services.payments.base import PaymentProvider

    inst = _inspect.getsource(sale_svc.instantiate_for_order)
    assert "is_return(order)" in inst and 'kind="credit"' in inst
    trans = _inspect.getsource(sale_svc._apply_transition)
    assert "credit_note_number" in trans and "_issue_refund" in trans
    assert "refund" in [m for m in dir(PaymentProvider)]  # Provider-Schnittstelle


def test_disposition_flips_at_step_completion():
    """Der Label-Wechsel passiert, wann er wirklich geschieht (step-basiert, idempotent):
    - Verkauf **bezahlt** → in_stock→sold (``sell_order_subjects``, aufgerufen bei sale-paid).
    - Retoure-**Bewegung** weg vom Kunden → sold→in_stock (``return_subjects_to_stock``,
      aufgerufen in ``movement.record_movement``); Kulanz (nicht bewegt) bleibt sold.
    Eine Gutschrift (kind='credit') bucht KEINEN Verkaufs-Abgang."""
    import inspect as _inspect
    from app.services import process, sale as sale_svc, movement

    sell = _inspect.getsource(process.sell_order_subjects)
    assert "is_return(order)" in sell and 'inst.disposition = "sold"' in sell
    ret = _inspect.getsource(process.return_subjects_to_stock) + _inspect.getsource(process._restock_one)
    # Rückkehr = die Instanz liegt NICHT mehr beim Kunden (kein Halter-Typ-Vergleich mehr –
    # der hing am entfallenen 'lagerplatz' und hätte nie wieder zugetroffen).
    assert 'inst.disposition = "in_stock"' in ret
    assert "still_at_customer" in ret and "customer_for_order" in ret
    assert 'location_type != "lagerplatz"' not in ret   # die tote Bedingung ist weg
    # sale-paid ruft sell_order_subjects (nur kind='sale'):
    trans = _inspect.getsource(sale_svc._apply_transition)
    assert "sell_order_subjects" in trans and 'not is_credit' in trans
    # Retoure-Bewegung ruft return_subjects_to_stock:
    mv = _inspect.getsource(movement.record_movement)
    assert "return_subjects_to_stock" in mv


def test_return_via_selecting_sold_instances():
    """Retoure = Normalauftrag: bei «Instanz wählen» werden VERKAUFTE Instanzen gewählt → der
    Auftrag wird automatisch zur Retoure (reason='return' + parent=Original-Verkauf). Kein
    eigener refund-/refund-subject-Endpoint mehr."""
    import inspect as _inspect
    from app.routers import orders

    # Die alten refund-Endpoints existieren nicht mehr:
    assert not hasattr(orders, "set_refund_subject")
    assert not hasattr(orders, "update_order_refund")
    # Die Sold-Auswahl + Retoure-Markierung sitzt im generischen Pin-Pfad:
    src = _inspect.getsource(orders._set_chosen_instances)
    assert 'order.reason = "return"' in src and "original_sale_order" in src
    # Welche Art die Auswahl ergibt, entscheidet jetzt EINE Klassifikation – die Prüfung
    # lässt jede aktive Instanz zu, ``classify_pick`` leitet daraus Retoure/Abweichung ab.
    from app.services.subject import classify_pick
    import inspect as _i
    assert '"sold"' in _i.getsource(classify_pick)
    assert "classify_pick" in src


def test_customer_shipping_movement_targets_the_customer():
    """Der Pflicht-Versand nach einem Verkauf (mode='customer') geht IMMER an den Kunden des
    Verkaufs – das Ziel wird serverseitig erzwungen (nicht frei wählbar) und im Embed als festes
    Ziel gezeigt (kein Laden von Personen-/Instanz-Listen → schnell)."""
    import inspect as _inspect
    from app.services import movement, orders, sale as sale_svc

    assert callable(sale_svc.customer_for_order)
    # Die Ziel-Auflösung sitzt in ``_resolve_targets`` (von ``record_movement`` aufgerufen).
    rec = _inspect.getsource(movement._resolve_targets)
    assert 'step.mode != "customer"' in rec and "customer_for_order" in rec
    assert "_resolve_targets(" in _inspect.getsource(movement.record_movement)
    emb = _inspect.getsource(orders._movement_embed)
    assert 'step.mode == "customer"' in emb and "customer_for_order" in emb


def test_customer_return_wired_shop_style():
    """Kunden-Retoure aus «Meine Bestellungen» (Online-Shop): retournierbar-Status am
    CustomerOrder + Endpoint, der einen Retoure-Unter-Auftrag inkl. Ablauf (Bewegung + Gutschrift)
    anlegt und ein Rückgabefenster respektiert."""
    import inspect as _inspect
    from app.schemas.shop import CustomerOrder
    from app.services import customer_returns
    from app.routers import shop

    for f in ("returnable", "return_requested", "return_deadline"):
        assert f in CustomerOrder.model_fields
    assert customer_returns.RETURN_WINDOW_DAYS > 0
    req = _inspect.getsource(customer_returns.request_return)
    assert 'reason="return"' in req and 'step_type="movement"' in req and 'step_type="sale"' in req
    assert "request_return" in _inspect.getsource(shop.request_return)


def test_document_step_is_wired_end_to_end():
    """«Dokument» ist ein vollwertiger Schritttyp: NEUTRAL/PRODUCE in der Registry, Fachtabelle
    ``Document`` OHNE eigene Objektnummer (Nummer = Instanz), wird WÄHREND der Ausführung mit
    «Ausstellen» (``done``) abgeschlossen – nicht schon bei der Freigabe."""
    import types as _types

    from app.domain import event_types as ev
    from app.models import Document
    from app.schemas.order import OrderResponse, OrderStepInfo
    from app.services import document, process

    # Registry: keine Bestandswirkung, erzeugt einen Liefergegenstand (die Instanz).
    assert ev.REGISTRY["document"].polarity == ev.NEUTRAL
    assert ev.REGISTRY["document"].subject_role == ev.PRODUCE
    assert ev.REGISTRY["document"].fact == "Document"
    assert process._FACT_MODEL["document"] is Document
    # Fachtabelle OHNE eigene Objektnummer (Nummer = Instanz); mit ``done``.
    assert Document.__tablename__ == "documents"
    cols = Document.__table__.columns.keys()
    assert "object_id" not in cols and "version" not in cols and "done" in cols
    # Erledigt erst, wenn ausgestellt (done=True) – nicht schon, sobald die Fachzeile existiert.
    assert process._fact_status("document", None) == "open"
    assert process._fact_status("document", _types.SimpleNamespace(done=False)) == "open"
    assert process._fact_status("document", _types.SimpleNamespace(done=True)) == "done"
    # In beiden Kontexten wählbar; Embed im Auftrag/Schritt vorhanden
    assert "document" in ev.ARTICLE_STEP_TYPES and "document" in ev.ORDER_STEP_TYPES
    assert "document" in OrderStepInfo.model_fields
    assert "document" in OrderResponse.model_fields
    # Inhalts-Normalisierung ist tolerant (leerer Rohinhalt → wohlgeformte Struktur, kein Datum)
    norm = document.normalize_content(None)
    assert norm["title"] == "" and norm["body"] == "" and "document_date" not in norm


def test_article_create_requires_only_name():
    """Ein Artikel braucht bei der Anlage NUR den Namen: Einheit/Serialisierung bekommen einen
    Default (Stk / unit), Grösse & Gewicht bleiben optional (leer, z. B. bei einem Dokument).
    Es gibt kein ``physical``-Flag mehr."""
    from decimal import Decimal

    from app.schemas.article import ArticleCreate

    a = ArticleCreate(name="Vertrag")
    assert a.unit == "Stk" and a.serialization == "unit"
    assert a.size is None and a.weight_kg is None
    assert not hasattr(a, "physical")
    # Physische Attribute bleiben wählbar
    b = ArticleCreate(name="Schraube", size="3x40x600", weight_kg=Decimal("0.05"))
    assert b.size == "3x40x600"


def test_document_pdf_renders_with_bundled_assets():
    """Der PDF-Renderer erzeugt ein nicht-leeres PDF im Inexxio-Design – Marken-Fonts UND das
    Logo sind gebündelt und werden offline eingebettet (kein Netzwerk nötig)."""
    from app.services import document_render

    font_dir = document_render._FONT_DIR
    for f in ("Inter-400.ttf", "Inter-700.ttf", "InterTight-700.ttf", "InterTight-800.ttf"):
        assert (font_dir / f).exists(), f"Font fehlt: {f}"
    assert document_render._LOGO_FILE.exists(), "Logo fehlt"
    from datetime import datetime, timezone
    pdf = document_render.render_pdf(
        {"title": "Testdokument",
         "body": "## §1\n\nInhalt mit **fett**, *kursiv* und einer Liste:\n\n- Punkt A\n- Punkt B\n\n"
                 "| Spalte | Wert |\n|---|---|\n| a | 1 |"},
        company={"company_name": "Inexxio AG", "street": "Industriestrasse", "street_nr": "12",
                 "zip_code": "8000", "city": "Zürich", "email": "info@inexxio.com"},
        object_id=100000123, issued_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    assert pdf[:4] == b"%PDF" and len(pdf) > 5000


def test_document_render_escapes_and_is_robust():
    """Der PDF-Renderer maskiert Nutzer-/Firmendaten kontextgerecht (HTML vs. CSS) und
    verkraftet adversariale Eingaben (Injection-Markup, überlanger Titel) ohne Absturz."""
    from app.services import document_render as dr

    # CSS-String-Escaper: Backslash/Quote maskiert, Zeilenumbruch entfernt (nicht html.escape!)
    assert dr._css_str('A "B" \\ C') == 'A \\"B\\" \\\\ C'
    assert "\n" not in dr._css_str("Zeile1\nZeile2")
    # Adversariale Firmen-/Inhaltsdaten + überlanger Titel → gültiges PDF, kein Crash
    pdf = dr.render_pdf(
        {"title": "X" * 400, "subtitle": "<b>x</b>",
         "body": "## <script>alert(1)</script>\n\na & b < c\n\n- <img src=x onerror=1>"},
        company={"company_name": 'A & B "Co" \\ Ltd', "email": "<img src=x>",
                 "street": "<style>*{}</style>", "zip_code": "8000", "city": "Zürich"},
        object_id=100000123,
    )
    assert pdf[:4] == b"%PDF" and len(pdf) > 5000


def test_document_redesign_shape():
    """Regressions-Schutz für das Redesign: das Dokument wird im Auftrag verfasst (kein
    ``next_object_id`` mehr, keine Vorlage am Schritt), die Instanz liefert Nummer & Datum,
    und es gibt kein ``physical``-Flag/Schritt-Guard mehr."""
    import inspect as _inspect

    from app.models import Article, ArticleProcessStep
    from app.routers import article_process
    from app.schemas.document import DocumentEmbed
    from app.services import document, serialization

    # Dokument-Fachzeile ohne eigene Nummer; Nummer/Datum kommen aus der Instanz.
    assert "next_object_id" not in _inspect.getsource(document.instantiate_for_order)
    assert {"object_number", "document_date"} <= set(DocumentEmbed.model_fields)
    assert callable(document.record_document) and callable(document.produced_instance)
    # Keine Typ-Trennung/kein Guard mehr; Artikel ohne physical, Schritt ohne document_content.
    assert "physical" not in Article.__table__.columns.keys()
    assert "document_content" not in ArticleProcessStep.__table__.columns.keys()
    assert "physical" not in _inspect.getsource(article_process._create)
    # Jeder Artikel erzeugt Instanzen (kein Early-Return für nicht-physisch mehr).
    assert "physical" not in _inspect.getsource(serialization.create_instances_for_order)


def test_operating_cost_model_pricing():
    """Modell-Preiszuordnung der Betriebskosten (Substring-Match, Opus als Default)."""
    from app.services.operating_costs import _price_for, _MODEL_PRICES

    assert _price_for("claude-opus-4-8") == _MODEL_PRICES["opus"]
    assert _price_for("claude-haiku-4-5-20251001") == _MODEL_PRICES["haiku"]
    assert _price_for("claude-sonnet-5") == _MODEL_PRICES["sonnet"]
    # Unbekannt/leer → konservativ Opus
    assert _price_for(None) == _MODEL_PRICES["opus"]
    assert _price_for("mystery-model") == _MODEL_PRICES["opus"]
    # Output ist stets teurer als Input
    for pin, pout in _MODEL_PRICES.values():
        assert pout > pin > 0


def test_order_reason_column_fits_all_reason_values():
    """Regression (Cleanup 2026-07, B1): 'replenishment' hat 13 Zeichen – die frühere
    Spaltenbreite VARCHAR(12) liess JEDE Auto-Nachbestellung mit einem Truncation-
    Fehler scheitern (SQLite-Tests prüfen Längen nicht, Postgres schon)."""
    from app.models import Order

    width = Order.__table__.c.reason.type.length
    for value in ("deviation", "supply", "return", "replenishment"):
        assert len(value) <= width, f"orders.reason zu schmal für '{value}'"


def test_allocation_write_paths_lock_fifo_candidates():
    """Regression (Cleanup 2026-07, B3): jede FIFO-**Allokation** (reservieren/verbrauchen)
    muss die Kandidaten sperren (SELECT … FOR UPDATE) – sonst reservieren zwei gleichzeitige
    Checkouts dieselbe letzte Instanz doppelt (Überverkauf). Reine Previews lesen ohne Lock."""
    import inspect as _inspect

    from app.services import recovery, resource, selling, subject

    for mod, fn in ((selling, "_materialize_multiline"), (subject, "_allocate_stock_for"),
                    (recovery, "_fifo_cover")):
        src = _inspect.getsource(getattr(mod, fn))
        assert "lock=True" in src, f"{mod.__name__}.{fn} alloziert ohne Row-Lock"
    src = _inspect.getsource(resource)
    assert src.count("lock=True") >= 2   # reserve_components + _consume_line

    from app.services.selling import fulfill_intent
    assert "with_for_update" in _inspect.getsource(fulfill_intent)


def test_provisioning_rule_book_declared():
    """«Bereitstellungsort» ist je Schritttyp DEKLARIERT (SSOT im event_types-Regelwerk):
    Beschaffung→Wareneingang, Verkauf→Kunde, Ressource→Produkt, Verschrotten→standortlos
    (kein Halter mehr), Datenerfassung/Bewegung/Dokument→kein fester Ort."""
    from app.domain import event_types as ev

    assert ev.provisioning("purchase") == ev.PROV_RECEIVING
    assert ev.provisioning("sale") == ev.PROV_CUSTOMER
    assert ev.provisioning("resource") == ev.PROV_PRODUCT
    assert ev.provisioning("scrap") == ev.PROV_NOWHERE
    for t in ("inspection", "movement", "document"):
        assert ev.provisioning(t) == ev.PROV_NONE
    # Unbekannter Typ → neutral (kein fester Ort), kein Absturz
    assert ev.provisioning("mystery") == ev.PROV_NONE


def test_provisioning_reconciler_is_noop_when_already_there():
    """Der EINE Reconciler bringt eine Instanz an ihren Bereitstellungsort und ist **no-op**,
    wenn sie (ausschliesslich) schon dort liegt – sonst verlagert er die ganze Instanz
    (verteilte Charge wird zusammengeführt)."""
    import types as _types

    from app.services import provisioning

    inst = _types.SimpleNamespace(location_type="instance", location_id=100000010, locations=None)
    assert provisioning.reconcile_to(inst, "instance", 100000010) is False   # schon da → no-op
    assert provisioning.reconcile_to(inst, "instance", 100000020) is True     # woanders → bewegt
    assert (inst.location_type, inst.location_id) == ("instance", 100000020)
    # Verteilte Charge (Map gesetzt) am selben Skalar-Ort ist NICHT no-op (Zusammenführung nötig).
    inst2 = _types.SimpleNamespace(location_type="instance", location_id=100000030,
                                   locations={"100000030": {"t": "instance", "q": "5"},
                                              "100000031": {"t": "instance", "q": "5"}})
    assert provisioning.reconcile_to(inst2, "instance", 100000030) is True
    assert inst2.locations is None                                            # zusammengeführt


def test_scrap_makes_whole_instance_locationless():
    """Verschrotten macht die GANZ verschrottete Instanz **standortlos** (ein Standort ist
    immer ein realer Halter – Person/Instanz/Unternehmen –, den Ausschuss nicht mehr hat).
    ``record_scrap`` ruft dafür ``location_split.clear``; kein Schrottplatz-Lagerort mehr
    (``send_to_scrapyard``/``resolve_scrap_location`` sind entfernt)."""
    import inspect as _inspect

    from app.services import scrap, provisioning, location_split

    src = _inspect.getsource(scrap)
    assert "location_split.clear" in src
    assert "send_to_scrapyard" not in src and "scrapyard" not in src
    # Die Schrottplatz-Maschinerie ist vollständig entfernt.
    assert not hasattr(provisioning, "send_to_scrapyard")
    assert not hasattr(provisioning, "resolve_scrap_location")
    # clear() macht standortlos (Skalar + Verteilungs-Map).
    clear_src = _inspect.getsource(location_split.clear)
    assert "location_type = None" in clear_src and "locations = None" in clear_src


def test_scrap_location_column_removed():
    """Der Ausschuss-Lagerort ist entfernt – kein Schrottplatz-Setting mehr am Unternehmen."""
    from app.models import CompanySettings
    from app.schemas.admin import CompanySettingsResponse, CompanySettingsUpdate

    assert "default_scrap_location_id" not in CompanySettings.__table__.columns
    assert "default_scrap_location_id" not in CompanySettingsResponse.model_fields
    assert "default_scrap_location_id" not in CompanySettingsUpdate.model_fields


def test_provisioning_timing_differs_by_step_type():
    """**Der Zeitpunkt ist je Schritttyp verschieden – und das muss er sein.**

    Ressource stellt VOR der Ausführung bereit (die Komponente muss da sein, bevor verbaut
    wird). Beschaffung und Verkauf stellen DANACH bereit (die Ware kommt an bzw. geht
    hinaus, nachdem der kaufmännische Vorgang durch ist).

    Ohne diese Trennung würde eine erst BESTELLTE Ware – Schritt aktiv, Ware noch beim
    Lieferanten – sofort in den Betrieb gebucht und wäre buchhalterisch da, bevor sie
    geliefert ist."""
    import inspect as _inspect

    from app.services import provisioning

    assert provisioning._STAGE_BEFORE == ("resource",)
    src = _inspect.getsource(provisioning.ensure_provisioning)
    assert 'if before and state not in ("active", "blocked")' in src
    assert 'if not before and state != "done"' in src


def test_provisioning_to_customer_only_moves_sold_units():
    """Eine **teilverkaufte Charge** darf nicht als Ganzes zum Kunden wandern.

    Der Verkauf bucht bei einer Teilmenge nur die Menge ab – die Instanz bleibt
    ``in_stock``. Würde sie mitbewegt, stünde der unverkaufte Rest danach als freier
    Bestand beim Kunden. Darum: nur ``sold``-Instanzen.

    Fallstrick, der hier mitgeprüft wird: ``sold`` ist eine **terminale** Disposition und
    wird von ``order_active_instances`` ausgeblendet – über diese Liste hätte der
    Kundenversand NIE ausgelöst."""
    import inspect as _inspect

    from app.services import provisioning
    from app.services.subject import TERMINAL_DISPOSITIONS

    assert "sold" in TERMINAL_DISPOSITIONS      # genau deshalb die volle Liste nötig
    src = _inspect.getsource(provisioning.subjects_for)
    assert "order_instances(db, order)" in src
    assert '(i.disposition or "") == "sold"' in src


def test_sub_order_buckets_are_explicit_per_reason():
    """Unter-Aufträge werden **explizit je Grund** einsortiert – kein Sammel-``else``.

    Sonst landet jeder neue Grund stillschweigend im Abweichungs-Topf: eine Bereitstellung
    erschiene dem Nutzer als «Abweichung» und liesse den Auftrag scheinbar pausieren."""
    import inspect as _inspect

    from app.schemas.order import OrderResponse
    from app.services import orders as orders_svc

    assert "provisionings" in OrderResponse.model_fields
    src = _inspect.getsource(orders_svc._order_sub_orders)
    assert '"provisioning": provisionings' in src
    assert "else deviations" not in src        # kein Sammel-Else mehr


def test_metrics_spread_median_first():
    """Kennzahlen aus der Historie: der Median trägt die Aussage, die Spanne ordnet ein.

    Bewusst Median statt Mittelwert – ein einzelner Eil-Auftrag (hier: 30 Tage) darf die
    übliche Dauer nicht verzerren. Typ-erhaltend, damit Geld ``Decimal`` bleibt."""
    from decimal import Decimal

    from app.services.metrics import spread

    assert spread([]) == (None, None, None)
    assert spread([5.0]) == (5.0, 5.0, 5.0)
    # Ausreisser: Mittelwert wäre 9.5, der Median bleibt bei 2
    assert spread([1.0, 2.0, 2.0, 30.0, None]) == (2.0, 1.0, 30.0)

    med, low, high = spread([Decimal("10.00"), Decimal("12.00"), Decimal("50.00")])
    assert (med, low, high) == (Decimal("12.00"), Decimal("10.00"), Decimal("50.00"))
    assert isinstance(med, Decimal)


def test_failed_inspection_is_not_terminal():
    """Eine durchgefallene Datenerfassung darf den Auftrag nicht endgültig festsetzen –
    aber aufgelöst wird sie NUR über den Folgeauftrag.

    ``all_steps_done`` verlangt für jeden Schritt ``done`` – ein Schritt, der auf
    «fehlgeschlagen» stehen bleibt, verhindert den Abschluss für immer, und seine Instanzen
    hängen dauerhaft in «In Arbeit». Der Weg nach vorn ist die **Abweichung**: schliesst sie
    ab, ist der Befund geklärt (``resolved_by_order_id``) und der Schritt erledigt. Der
    Befund selbst bleibt ``failed`` – gemessen ist gemessen.

    Es gibt bewusst KEIN «erneut erfassen» am fehlgeschlagenen Schritt (es wäre ohnehin eine
    Sackgasse: ``resolve_exec_step`` führt nur *aktive* Schritte aus)."""
    import inspect as _inspect

    from app.services import inspection as insp_mod
    from app.services import process as proc_mod

    src = _inspect.getsource(insp_mod)
    # Nicht mehr nur beim Nichtbestehen bewerten …
    assert 'if decision != "passed":\n        _apply_per_instance_qc' not in src
    assert "_apply_per_instance_qc(db, order, fields, stored)" in src
    # … und die Sperre ist rücknehmbar (gesperrt → pending), nie eine vorzeitige Freigabe.
    assert 'inst.quality = "pending"' in src
    assert 'inst.quality = "passed"' not in src

    # Die Klärung: nur ein abgeschlossener Abweichungs-Unterauftrag setzt sie.
    assert "def resolve_failed_by(" in src
    proc_src = _inspect.getsource(proc_mod)
    assert '(order.reason or "") == "deviation"' in proc_src
    assert "resolve_failed_by(db, parent, order)" in proc_src
    # … und ein so geklärter Befund macht den Schritt erledigt.
    assert 'return "done" if getattr(fact, "resolved_by_order_id", None) else "failed"' in proc_src


def test_blocked_is_one_state_with_one_word():
    """«Durchgefallen» und «gesperrt» waren zwei Werte für dieselbe Aussage.

    Beide heissen «vorhanden, aber nicht verwendbar», beide fallen über dieselbe Bedingung
    aus FIFO/Bestand, beide sind aufhebbar – nur die Namen waren verschieden. Seit
    Migration 085 gibt es EINEN geschriebenen Wert (``blocked``); ``failed`` wird nur noch
    tolerant GELESEN. Damit das eine Stelle bleibt, geht jeder Lesezugriff über
    ``inventory.is_blocked``/``unblocked_clauses`` statt über einen eigenen Vergleich."""
    import inspect as _inspect

    from app.services import deviation, inspection, inventory, process, scrap

    assert inventory.BLOCKED == "blocked"
    # Tolerant lesen: Altbestand zählt weiterhin als gesperrt.
    assert inventory.is_blocked(_Q("failed")) and inventory.is_blocked(_Q("blocked"))
    assert not inventory.is_blocked(_Q("passed")) and not inventory.is_blocked(_Q(None))

    # Kein zweiter Weg mehr: nirgends ein handgeschriebener quality-Vergleich auf 'failed'.
    for mod in (process, deviation, inspection, scrap):
        src = _inspect.getsource(mod)
        assert 'quality == "failed"' not in src, mod.__name__
        assert 'quality != "failed"' not in src, mod.__name__
    # Geschrieben wird ausschliesslich der eine Wert.
    assert 'inst.quality = "failed"' not in _inspect.getsource(inspection)
    assert "inst.quality = inventory.BLOCKED" in _inspect.getsource(inspection)


class _Q:
    """Minimales Instanz-Double – ``is_blocked`` liest nur ``quality``."""

    def __init__(self, quality):
        self.quality = quality


def test_sub_order_deactivation_goes_through_one_cleanup():
    """Ein Unter-Auftrag hält drei Fäden zum Eltern – wer nur den Status setzt, reisst keinen.

    Subjekt-Bindung, Verarbeitungs-Links und ``abort_into_id``: blieben sie stehen, wäre der
    Eltern für immer pausiert (``abort_into_id`` nie NULL → auch kein neuer Abbruch möglich)
    und seine Instanzen zeigten auf einen toten Auftrag. Beide Türen – «Zurücknehmen»
    (Entwurf) und «Abbrechen» (freigegeben) – gehen darum durch DIESELBE Aufräum-Stelle.
    Und ein Unter-Auftrag bekommt nie einen eigenen Folgeauftrag: sein Subjekt gehört ohnehin
    dem Eltern (Abweichung/Retoure) bzw. er transportiert nur (Bereitstellung)."""
    import inspect as _inspect

    from app.routers import orders as orders_router
    from app.services import deviation

    src = _inspect.getsource(deviation.detach_sub_order)
    assert "parent.abort_into_id = None" in src
    assert "link.is_active = False" in src
    assert "inst.subject_of_order_id = (" in src
    # «Zurücknehmen» hat die Logik nicht mehr selbst, sondern ruft sie.
    assert "detach_sub_order(db, followup, actor_id)" in _inspect.getsource(deviation.revoke)
    # … und der Abbruch eines Unter-Auftrags ebenso, statt still nur den Status zu setzen.
    abort_src = _inspect.getsource(orders_router.abort_order)
    assert "if order.parent_order_id is not None:" in abort_src
    assert "deviation.detach_sub_order(db, order, current_user.id)" in abort_src


def test_open_provisioning_holds_the_whole_order():
    """**Eine offene Bereitstellung hält den ganzen Auftrag an – nicht nur „ihren" Schritt.**

    Sie gehört zu dem Schritt, der sie ausgelöst hat (Beschaffung: die Ware kommt an, NACHDEM
    die Bestellung geliefert ist) und liegt im Ablauf damit VOR dem nächsten Schritt. Prüfte
    man nur den eigenen Schritt, liesse sich die Eingangskontrolle abschliessen, während die
    Ware buchhalterisch noch beim Lieferanten liegt – genau der gemeldete Fall. Eine Regel,
    kein Sonderfall je Schritttyp.

    Die **Position** im Ablauf folgt derselben, schon deklarierten Zeitpunkt-Regel: Ressource
    stellt vorher bereit, Beschaffung/Verkauf nachher. Das Frontend platziert nur."""
    import inspect as _inspect

    from app.services import orders as orders_svc, process, provisioning
    from app.schemas.order import OrderStepInfo

    # Die Bereitstellung hängt seit der Pause-Regel am **Auftrag** (``is_paused``), nicht
    # am einzelnen Schritt – dieselbe Aussage, nur eine Ebene höher.
    paused = _inspect.getsource(process.is_paused)
    assert "open_provisioning(db, order)" in paused
    assert "open_provisioning(db, order, step.id)" not in paused
    assert "is_paused(db, order)" in _inspect.getsource(process._step_blocked)

    # Knoten-Daten je Schritt: EINE Liste Unter-Aufträge, jeder mit seiner eigenen Stufe.
    si = OrderStepInfo(step_type="purchase", position=1, label="x", state="done")
    assert si.sub_orders == []
    assert provisioning._STAGE_BEFORE == ("resource",)
    # Die Stufen-Regel steht im Backend, nicht im Frontend – und sie ist EINE Funktion.
    assert orders_svc._sub_order_stage("provisioning", "purchase") == "after"
    assert orders_svc._sub_order_stage("provisioning", "resource") == "before"
    assert orders_svc._sub_order_stage("deviation", "purchase") == "before"
    assert orders_svc._sub_order_stage("supply", "purchase") == "before"
    fill = _inspect.getsource(orders_svc._fill_step_sub_orders)
    assert "Order.origin_step_id == step.id" in fill


def test_fixed_subject_sub_order_reserves_its_stock():
    """Ein freigegebener Unter-Auftrag hat seine Instanzen **in der Hand** – also sind sie
    reserviert, sobald sie am Lager liegen.

    Vorher band eine Abweichung ihre Instanzen nur über ``subject_of_order_id`` und den
    Verarbeitungs-Link: FIFO sah sie weiterhin als frei, ein beliebiger anderer Auftrag konnte
    sie wegnehmen – und die Badge zeigte «Freigegeben», obwohl sie längst gebunden waren.
    Reserviert wird nur, was am Lager liegt: in Arbeit / verkauft / gesperrt greift ohnehin
    kein FIFO. Beim Abschluss oder Verwerfen löst ``release`` die Reservierung wieder."""
    import inspect as _inspect

    from app.services import subject

    src = _inspect.getsource(subject._bind_deviation_subjects)
    assert "is_in_stock(inst)" in src
    assert "reserve(inst, order.id, to_qty(inst.quantity))" in src
    # Idempotent: eine zweite Freigabe reserviert nicht doppelt.
    assert "reserved_for(inst, order.id) <= 0" in src


def test_sub_orders_know_where_they_came_from():
    """Jeder Unter-Auftrag trägt seinen **Ursprungs-Schritt** – und damit eine Position im Ablauf.

    ``orders.origin_step_id`` beantwortet für JEDE Art dieselbe Frage: aus welchem Schritt des
    Eltern ist er hervorgegangen? Die Bereitstellung wartet für genau diesen Schritt, die
    Abweichung wurde an genau dieser Stelle gemeldet. Vorher hiess die Spalte
    ``provisioning_step_id`` und beantwortete die Frage nur für eine Art (Migration 087)."""
    import inspect as _inspect

    from app.models import Order
    from app.services import deviation, orders as orders_svc

    assert hasattr(Order, "origin_step_id") and not hasattr(Order, "provisioning_step_id")
    assert "origin_step_id=interrupted_step_id(db, parent)" in _inspect.getsource(deviation.create_deviation)
    # Der Ursprungs-Schritt ist der, an dem der Eltern gerade steht.
    act = _inspect.getsource(deviation.interrupted_step_id)
    assert '("active", "blocked", "failed")' in act
    # … und ALLE Arten werden je Schritt mitgeliefert – EINE Liste, kein Topf je Grund
    # (Abweichung, Nachschub, Bereitstellung stehen alle an ihrer Stelle im Ablauf).
    fill = _inspect.getsource(orders_svc._fill_step_sub_orders)
    assert "Order.origin_step_id == step.id" in fill
    assert "Order.reason" not in fill
    # Auch der Nachschub merkt sich, aus welchem Schritt sein Bedarf stammt.
    from app.services import supply as supply_svc
    assert "origin_step_id=process.blocked_step_for_article(db, order, art_id)" in _inspect.getsource(supply_svc)


def test_cancelled_provisioning_is_not_recreated():
    """Eine Bereitstellung entsteht automatisch – also muss sie auch abbrechbar sein.

    Sie blockiert den betroffenen Schritt UND den Abschluss; läuft sie nicht durch, wäre der
    Auftrag ohne Ausweg tot. Der Abbruch ist die Aussage «das mache ich von Hand». Damit das
    hält, darf die nächste Auswertung sie nicht sofort neu anlegen – Marker ist der
    abgebrochene Unter-Auftrag selbst (kein zusätzliches Feld, keine zweite Wahrheit)."""
    import inspect as _inspect

    from app.services import provisioning

    src = _inspect.getsource(provisioning.cancelled_for_step)
    assert 'Order.status == "inactive"' in src
    assert "Order.origin_step_id == step_id" in src
    assert "cancelled_for_step(db, order, step.id)" in _inspect.getsource(provisioning.ensure_provisioning)


def test_only_a_deviation_counts_as_an_open_deviation():
    """Ein Bereitstellungs-Unterauftrag ist keine Abweichung.

    ``instance_open_deviation`` filterte nicht auf ``reason`` – damit galt JEDER
    Unter-Auftrag, der die Instanz anfasst, als «offene Abweichung». Die automatisch
    abgeleitete **Bereitstellung** (ein Unter-Auftrag mit genau einem Bewegungs-Schritt)
    liess so einen Abbruch mit «Instanz … hat bereits eine offene Abweichung (Auftrag …)»
    scheitern – und zeigte auf einen Auftrag, den niemand angelegt hatte."""
    import inspect as _inspect

    from app.services import deviation

    for fn in (deviation.open_deviations, deviation.instance_open_deviation):
        assert 'Order.reason == "deviation"' in _inspect.getsource(fn), fn.__name__


def test_sample_size_comes_from_the_inspected_instances():
    """Der Prüfumfang bemisst sich an der geprüften MENGE, nicht an der Zahl der Subjekte.

    Eine Abweichung auf EINE Charge à 5 Stk trug ``order.quantity = 1`` (ein Subjekt) – bei
    «jede» kam so statt fünf Proben nur eine. Stichprobenzahl und Stichprobenziele stammen
    jetzt aus derselben Quelle (``order_active_instances``) und können nicht mehr
    auseinanderlaufen.

    **Und es ist die Menge, die dem Auftrag GEHÖRT** (Testnotiz #399): von einer Charge à 4,
    an der ihm 2 gehören, sind 2 zu prüfen – nicht 4 («Prüfumfang: 4 von 2 Stück»). Die
    Antwort darauf gibt es genau einmal (``subject.held_quantity``), und die Kapazität je
    Instanz liest dieselbe."""
    import inspect as _inspect

    from app.services import deviation, inspection

    src = _inspect.getsource(inspection.inspected_quantity)
    assert "order_active_instances(db, order)" in src
    assert "qty_sum(held_quantity(order, i) for i in insts)" in src, (
        "Nicht die ganze Instanz – was dem Auftrag gehört.")
    tgt = _inspect.getsource(inspection.sample_targets)
    assert "sample_capacity(held_quantity(order, inst))" in tgt, (
        "Zahl und Ziele lesen dieselbe Menge – sonst laufen sie auseinander.")
    assert "inspected_quantity(db, order)" in _inspect.getsource(inspection.required_count)
    # Auch die Abweichung selbst deklariert die Menge, nicht die Zahl der Instanzen.
    # Die Menge einer Abweichung ist die Summe der **beanspruchten Teilmengen** (ohne
    # Angabe die ganze Instanz) – nie die ANZAHL der Instanzen.
    dev_src = _inspect.getsource(deviation.create_deviation)
    assert "quantity=qty_sum(" in dev_src and "len(insts)" not in dev_src
    assert "quantity=len(insts)" not in _inspect.getsource(deviation.create_deviation)


def test_block_is_reversible_scrap_is_not():
    """«Sperren» und «Verschrotten» sind zwei Wege, dieselbe Instanz auszusteuern –
    aber auf VERSCHIEDENEN Achsen, und nur einer ist umkehrbar.

    Sperren wirkt auf ``quality`` («darf man es verwenden?») und lässt Standort, Menge und
    Reservierungen unangetastet; Verschrotten wirkt auf ``disposition`` («wo ist es») und
    macht die Instanz standortlos. Weil ``in_stock_clauses`` beides verlangt, fällt eine
    gesperrte Instanz ohne weitere Abfrage aus Bestand und FIFO."""
    import inspect as _inspect

    from app.domain import event_types as ev
    from app.services import scrap

    # Registry: eigener Schritttyp, wirkt auf bestehende Instanzen, teilt sich die
    # Marker-Fachzeile mit dem Verschrotten – aber ohne Bestandsvernichtung (NEUTRAL).
    block = ev.REGISTRY["block"]
    assert block.subject_role == ev.INSTANCE and block.fact == "Disposal"
    assert block.polarity == ev.NEUTRAL and ev.REGISTRY["scrap"].polarity == ev.DECREASE
    # Sperren hat KEINEN Bereitstellungsort (die Instanz bleibt stehen); Verschrotten
    # macht standortlos.
    assert block.provisioning == ev.PROV_NONE
    assert ev.REGISTRY["scrap"].provisioning == ev.PROV_NOWHERE
    # Nur im Auftrags-Ablauf, nie im Artikel-Prozess (wie das Verschrotten).
    # Wählbar ist «Sperren» in JEDEM Prozess-Kontext (Testnotiz #246).
    assert "block" in ev.allowed_step_types("article") and "block" in ev.allowed_step_types("order")
    assert "block" in ev.allowed_step_types("order")

    src = _inspect.getsource(scrap)
    assert "inst.quality = inventory.BLOCKED" in src   # Sperre auf der Qualitäts-Achse
    assert "def unblock(" in src                    # … und wieder aufhebbar
    # Der Zustand nach dem Entsperren wird ABGELEITET (kein gemerktes drittes Feld).
    assert "def _restore_quality(" in src


def test_order_name_never_falls_back_to_the_type_word_when_there_is_a_name():
    """Ein Datensatz zeigt **Name · Objektnummer · Status** – der TYP steht im Symbol.

    Vorher trug ein Auftrag im Feed als «Namen» das Wort «Auftrag»; zwei Aufträge sahen
    damit identisch aus. Der Name wird jetzt an EINER Stelle abgeleitet (Feed und Detail
    lesen dasselbe Feld), in dieser Reihenfolge: bewusster Titel ≻ Artikel ≻ erste Position
    «+N» ≻ und nur wenn es nichts zu benennen gibt: «Auftrag».
    """
    from app.models import Order
    from app.services.orders import order_display_name

    o = Order(title=None)
    assert order_display_name(o, None, None) == "Auftrag"          # nichts zu benennen
    assert order_display_name(o, "Schraubendreher", None) == "Schraubendreher"
    assert order_display_name(o, None, ["Schraube", "Mutter", "Blech"]) == "Schraube +2"
    assert order_display_name(o, None, ["Schraube"]) == "Schraube"
    # Der Name benennt die SACHE, nicht die Herkunft (Notiz #205): ein Unter-Auftrag heisst
    # nach dem Artikel seiner fixierten Instanzen, nicht «Bereitstellung für … Auftrag …».
    o2 = Order(title="Bereitstellung für Beschaffung · Auftrag 100000500")
    assert order_display_name(o2, None, None, ["Schraubendreher"]) == "Schraubendreher"
    # Ohne jedes Subjekt bleibt der bewusst vergebene Titel der beste verfügbare Name.
    assert order_display_name(o2, None, None, None).startswith("Bereitstellung")


def test_auto_provisioning_is_switched_off_at_exactly_one_place():
    """Die abgeleitete Bereitstellung ist **vorübergehend abgeschaltet** (Testnotiz #204) –
    und zwar an EINER Stelle, nicht verstreut über die Aufrufer.

    ``AUTO_PROVISIONING=False`` heisst: es entsteht keine neue Bereitstellung, und eine
    bereits vorhandene hält keinen Auftrag mehr an (sonst hinge ein Auftrag an einem
    Mechanismus fest, den es gerade nicht gibt). Die Ableitung selbst (Deklaration,
    ``target_for``, ``misplaced``) bleibt vollständig bestehen – Wiedereinschalten ist ein
    Ein-Zeilen-Wechsel.
    """
    from app.services import provisioning

    assert provisioning.AUTO_PROVISIONING is False
    for fn in (provisioning.ensure_provisioning, provisioning.open_provisioning):
        assert "if not AUTO_PROVISIONING" in _inspect_source_fn(fn)
    # Die Ableitung ist NICHT entfernt, nur stillgelegt.
    assert callable(provisioning.target_for) and callable(provisioning.misplaced)


def test_the_order_that_finishes_an_instance_releases_it():
    """**Freigegeben wird von dem Auftrag, der zuletzt an der Instanz gearbeitet hat.**

    Wird ein Auftrag abgebrochen und ein Abweichungsauftrag führt seine Instanzen fort, bleibt
    deren ``order_id`` beim abgebrochenen Original. Sah die Freigabe nur auf den **Erzeuger**,
    wurden diese Instanzen NIE freigegeben – für immer «Im Prozess», unsichtbar für FIFO und
    Bestandszählung (Testnotiz #262). Massgeblich ist darum erzeugt-von ODER Subjekt-von.
    """
    from app.services import process

    src = _inspect_source_fn(process.release_instances)
    assert "Instance.order_id == order.id" in src
    assert "Instance.subject_of_order_id == order.id" in src
    # Terminale/bereits bewertete Teile bleiben ausgenommen – nur «im Prozess» wird frei.
    assert 'Instance.quality == "pending"' in src
    assert 'Instance.disposition == "in_process"' in src


def test_an_instance_is_not_released_while_another_order_still_works_on_it():
    """**«Zuletzt daran gearbeitet» heisst: es arbeitet kein anderer Auftrag mehr daran.**

    Gemeldeter Fall (Testnotiz #332): eine Abweichung auf eine Instanz eines **laufenden**
    Erzeugungsauftrags wird abgeschlossen – und gab die Instanz frei, obwohl ihr Auftrag noch
    im Prozess war. Sie erschien damit am Lager (FIFO-verfügbar), während sie tatsächlich
    noch in Produktion steckte.

    Die Regel muss in BEIDE Richtungen gelten: weder gibt der Eltern frei, was in einer
    offenen Abweichung steckt (Notiz #262-Folge), noch gibt die Abweichung frei, was der
    Eltern noch bearbeitet. Massstab ist der **Status** des anderen Auftrags – ein
    abgebrochener (``inactive``) hält nichts fest, sonst wäre der #262-Fix wieder kaputt."""
    from app.services import process

    guard = _inspect_source_fn(process._worked_on_by_a_running_order)
    # Beide Bindungen zählen (Erzeuger UND festes Subjekt) …
    assert "inst.order_id" in guard and "inst.subject_of_order_id" in guard
    # … aber nur ein WIRKLICH laufender Auftrag hält fest (nicht abgebrochen/abgeschlossen).
    assert 'Order.status == "released"' in guard
    assert "Order.is_active == True" in guard
    # … und der abschliessende Auftrag hält sich nicht selbst fest.
    assert "oid != order.id" in guard

    src = _inspect_source_fn(process.release_instances)
    assert "_worked_on_by_a_running_order" in src, "Die Freigabe muss den Wächter benutzen"
    assert "still_running" in src


def test_a_step_type_only_fills_its_own_columns():
    """**Welche Felder ein Schritt-Typ trägt, steht an EINER Stelle** (Notiz: Vereinfachung).

    Vorher entschied das der Konstruktor über ~14 einzelne ``x if is_document else None``
    plus drei Flag-Variablen davor: «welche Felder hat ein Dokument-Schritt?» war nur durch
    Absuchen aller Zeilen zu beantworten, und ein neuer Typ hiess «überall eine Bedingung
    ergänzen». Jetzt liefert je Typ EINE Funktion genau seine Spalten – alles andere bleibt
    leer (Modell-Default). Der Test hält fest, dass kein Typ in fremde Felder schreibt."""
    from types import SimpleNamespace

    from app.domain import event_types
    from app.routers.article_process import _FIELDS_BY_TYPE
    from app.schemas.article_process_step import ArticleProcessStepCreate

    # Die Prüfungen fragen nur nach «gibt es das und ist es gültig?» – ein Stub genügt,
    # der auf jede Abfrage einen freigegebenen Artikel bzw. einen aktiven Lieferanten
    # zurückgibt. Geprüft wird hier die **Feld-Zuordnung**, nicht die Validierung.
    class _Db:
        def query(self, *a, **kw): return self
        def filter(self, *a, **kw): return self
        def first(self): return SimpleNamespace(status="released", role="supplier")

    def fields_for(**kw) -> dict:
        data = ArticleProcessStepCreate(**kw)
        fn = _FIELDS_BY_TYPE.get(data.step_type)
        return fn(_Db(), data) if fn else {}

    assert set(fields_for(step_type="purchase")) == {"supplier_id", "webshop_url", "shared_fields"}
    # Eine Datenerfassung braucht per Schema mindestens ein Erfassungsfeld (Notiz #41).
    ok_field = {"key": "ok", "label": "OK", "type": "bool"}
    assert set(fields_for(step_type="inspection", capture_fields=[ok_field])) == {
        "sample_percent", "capture_fields"}
    assert set(fields_for(step_type="movement")) == {"target_location_type", "target_location_id"}
    assert set(fields_for(step_type="resource",
                          resource_lines=[{"article_id": 1, "quantity": 2, "mode": "consume"}])
               ) == {"resource_lines"}
    assert set(fields_for(step_type="document")) == {
        "doc_signers", "sign_sequential", "doc_audience", "doc_audience_roles",
        "doc_audience_person_ids", "doc_visibility"}
    # Reine Marker-Schritte tragen ausser Typ/Position/Modus nichts.
    for marker in ("scrap", "block", "sale"):
        assert fields_for(step_type=marker) == {}, marker

    # Die Quelle einer Beschaffung ist Lieferant ODER Webshop – nie beides.
    both = fields_for(step_type="purchase", mode="webshop", webshop_url="https://x.ch")
    assert both["supplier_id"] is None and both["webshop_url"] == "https://x.ch"

    # Jeder Eintrag muss ein bekannter Schritttyp sein (kein toter Zweig).
    assert set(_FIELDS_BY_TYPE) <= set(event_types.REGISTRY)


def test_step_status_semantics_live_in_the_registry():
    """**Woran man einem Schritt ansieht, dass er durch ist, steht in der Registry.**

    ``process._fact_status`` war eine if/elif-Kette über die Schritttypen – dieselbe
    Aussage wie die Registry, nur an einer zweiten Stelle: ein neuer Typ musste in beiden
    gepflegt werden, und sie konnten still auseinanderlaufen. Jetzt deklariert jeder Typ
    ``status_field``/``done``/``failed``, und die Ableitung ist EINE Regel."""
    import ast
    import inspect as _inspect
    from app.domain import event_types
    from app.services.process import _fact_status

    reg = event_types.REGISTRY
    assert reg["purchase"].done == ("received",) and reg["purchase"].failed == ("rejected",)
    assert reg["inspection"].status_field == "result"
    assert reg["sale"].done == ("paid",)
    # Marker-Schritte: die blosse Existenz der Fachzeile IST die Erledigung.
    for marker in ("movement", "resource", "scrap", "block"):
        assert reg[marker].status_field is None, marker

    src = ast.unparse(ast.parse(_inspect.getsource(_fact_status)))
    for literal in ("'received'", "'rejected'", "'paid'", "'cancelled'", "'passed'"):
        assert literal not in src, (
            f"{literal} gehört in die Registry, nicht in die Ableitung – sonst gibt es die "
            "Aussage wieder zweimal")

    class Fact:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    assert _fact_status("purchase", None) == "open"
    assert _fact_status("purchase", Fact(status="received")) == "done"
    assert _fact_status("purchase", Fact(status="rejected")) == "failed"
    assert _fact_status("purchase", Fact(status="ordered")) == "open"
    assert _fact_status("movement", Fact()) == "done"
    assert _fact_status("document", Fact(done=False)) == "open"
    assert _fact_status("document", Fact(done=True)) == "done"
    # Ein Fehlschlag, den ein Folgeauftrag geklärt hat, gilt als erledigt – der Befund
    # selbst bleibt fehlgeschlagen (Testnotiz #70/#71).
    assert _fact_status("inspection", Fact(result="failed")) == "failed"
    assert _fact_status("inspection", Fact(result="failed", resolved_by_order_id=7)) == "done"


def test_a_pick_claims_a_quantity_not_a_thing():
    """**Eine Auswahl beansprucht eine MENGE, kein Ding** (Testnotiz #361).

    Von einer Charge à 500 will eine Abweichung oft genau EINE Schraube. Die Menge landet
    dort, wo sie hingehört – in derselben Reservierungs-Map, in die auch die FIFO-Allokation
    längst mengengenau schreibt (``reservation.claim`` setzt, ``reserve`` addiert). Damit
    braucht es weder eine neue Spalte noch eine zweite Buchführung: nimmt die Auswahl mehr,
    als frei ist, kürzt ``claim`` den fremden Anspruch – und **genau daraus** entsteht die
    Unterdeckung beim Auftrag, dem das Stück entzogen wird."""
    import inspect as _inspect
    from app.routers import orders
    from app.schemas.order import OrderLinePins, OrderUpdate
    from app.services import process, reservation, subject

    for schema in (OrderUpdate, OrderLinePins):
        assert "picks" in schema.model_fields, schema.__name__
    # ``claim`` SETZT (statt zu addieren) – und tastet dabei niemanden an (Notiz #370).
    cl = _inspect.getsource(reservation.claim)
    assert "m[str(order_id)] = want" in cl
    # Der Pin schreibt Bindung UND Anspruch.
    pick = _inspect.getsource(orders._set_chosen_instances)
    assert "claim(i, order.id, wanted[i.object_id])" in pick
    assert "release_reservation(prev, order.id)" in pick
    # Die Menge steckt in der Frage «ist das gebunden?» – 3 von 5 freien ist kein Sonderfall.
    assert "want" in _inspect.getsource(subject.is_bound)
    # Und die Klärungs-Menge ist eine Menge, kein Set.
    assert "-> dict[int, Decimal]" in _inspect.getsource(process.deviated_quantities)


def test_a_company_can_be_closed_but_never_reopened():
    """**Ein Unternehmen ist schliessbar – endgültig** (Testnotiz #365).

    Eine wiedereröffnete Gesellschaft ist rechtlich eine andere (neue UID/EIN, neues
    HR-Datum, neue Belegkreise); sie als dieselbe weiterzuführen hiesse, auf ihren Belegen
    eine Rechtsperson zu nennen, die es so nicht mehr gab. Darum gibt es kein «Reaktivieren»
    und kein «Ersetzen» – wer wieder eröffnet, legt ein neues Unternehmen an.

    Zwei Dinge bleiben geschützt: der **Betreiber** (Absender der einen Website) und die
    **letzte** Gesellschaft."""
    import inspect as _inspect
    from app.models import CompanySettings
    from app.services import sites

    assert hasattr(CompanySettings, "is_active")
    assert not hasattr(sites, "reactivate")
    src = _inspect.getsource(sites.deactivate)
    assert "company.is_operator" in src and "Betreiber" in src
    assert "others == 0" in src
    # Gebiete fallen zurück – jeder Fleck der Erde gehört weiterhin jemandem.
    assert "CompanyTerritory.company_id == company.id" in src
    # **Auflösung und Auswahl** sehen eine geschlossene Gesellschaft nicht mehr – der
    # **Feed** dagegen schon: «geschlossen» ist ein Zustand, kein Verschwinden (sonst wäre
    # ihre Historie über keine Oberfläche mehr erreichbar).
    assert "CompanySettings.is_active == True" in _inspect.getsource(sites.find_operator)
    assert "c.is_active" in _inspect.getsource(sites.selectable_companies)
    assert "CompanySettings.is_active" not in _inspect.getsource(sites.all_companies)


def test_a_pick_never_mixes_free_and_bound_instances():
    """**Kein Mischmasch** (Testnotiz #355): freie und gebundene Stücke gehören nicht in
    denselben Auftrag – der freie Teil wäre ein gewöhnlicher Bedarf, der gebundene nimmt
    einem laufenden Auftrag etwas weg. Dieselbe Regel und dieselbe Form wie beim
    Verkauft/Lager-Mix, und beide Seiten lesen dieselbe Definition (``subject.is_bound``)."""
    import inspect as _inspect
    from app.routers import orders
    from app.services import subject

    assert hasattr(subject, "is_bound")
    src = _inspect.getsource(orders._set_chosen_instances)
    assert "subject.is_bound(order, i, wanted[i.object_id], sources.get(i.object_id))" in src \
        and "nicht gemischt" in src


def test_a_refused_step_names_the_real_reason():
    """Ruht der Auftrag, liegt es nicht an der Reihenfolge – dann sagt der 409 das auch.

    «… ist (noch) nicht an der Reihe» stimmt zwar immer, hilft aber nicht weiter: der
    Ausweg ist die Unterdeckungs-Frage, und die muss in der Meldung stehen."""
    import inspect as _inspect
    from app.services import process

    src = _inspect.getsource(process._not_now)
    assert "is_paused(db, order)" in src
    for word in ("pausieren", "ersetzen", "reduzieren"):
        assert word in src, word
    assert "_not_now(db, order, label)" in _inspect.getsource(process.resolve_exec_step)


def test_the_pause_has_no_mechanism_of_its_own():
    """**Was einen Auftrag anhält, ist immer dasselbe: ihm fehlt etwas.**

    Es gibt keinen zweiten Zustand «pausiert wegen Abweichung» neben «es fehlt etwas» – eine
    offene Abweichung nimmt ihr Stück heraus (``deviated_instance_ids``) und erzeugt damit
    genau diese Fehlmenge. Darum darf in der Pause-Regel kein Schritttyp und kein Flag
    stehen: sie fragt die Fehlmenge, sonst nichts.

    Zwischenzeitlich stand hier ``EventType.hands_over`` (nur Verkauf/Ressource blockieren).
    Das Feld ist entfallen – ein Flag, das nur eine Blockade steuerte, die es so nicht mehr
    gibt, wäre eine zweite Wahrheit im Katalog."""
    import ast
    import inspect as _inspect
    from app.domain import event_types
    from app.services.process import _step_blocked, is_paused

    assert not hasattr(event_types.EventType, "hands_over")
    assert not any("hands_over" in str(et) for et in event_types.REGISTRY.values())

    # Nur der CODE zählt, nicht der Text: die Docstrings dürfen die abgeschaffte Regel
    # ruhig erwähnen (sie erklären, warum es sie nicht mehr gibt).
    def code(fn) -> str:
        tree = ast.parse(_inspect.getsource(fn))
        fn_node = tree.body[0]
        if isinstance(fn_node.body[0], ast.Expr) and isinstance(fn_node.body[0].value, ast.Constant):
            fn_node.body = fn_node.body[1:]
        return ast.unparse(tree)

    src = code(_step_blocked) + code(is_paused)
    assert "hands_over" not in src
    for literal in ("'inspection'", "'movement'", "'scrap'", "'sale'"):
        assert literal not in src, (
            f"{literal} gehört nicht in die Pause-Regel – sonst ist die Typ-Liste wieder da")


def test_no_order_completes_while_something_is_missing():
    """**Kein Auftrag geht «fertig», solange ihm etwas fehlt** – die zweite Hälfte derselben
    Regel und der eigentliche Schutz gegen stilles Unterliefern.

    Vorher hing der Schutz zufällig daran, ob der Prozess einen blockierenden Schritt
    enthielt: ein Auftrag über 4 Stück mit reiner **Beschaffung** schloss mit 3 gelieferten
    Stück ab – ohne Fehlmeldung, ohne Entscheidung. Jetzt entscheidet der Mensch über die
    drei Wege (Ersetzen · gezielt decken · ohne Ersatz weiter), und erst danach ist der
    Auftrag durch."""
    import ast
    import inspect as _inspect
    from app.services.process import recompute_completion

    src = ast.unparse(ast.parse(_inspect.getsource(recompute_completion)))
    assert "all_steps_done" in src and "_subject_shortfalls" in src, (
        "Der Abschluss muss BEIDES verlangen: alle Schritte erledigt UND nichts offen")


def test_the_shortfall_belongs_to_the_order():
    """Die Fehlmenge ist eine Aussage über den **Auftrag**, nicht über einen Schritt.

    Sie entsteht aus «Soll − Gesichert» und ist dieselbe Zahl, egal welcher Schritt gerade
    dran ist. Vorher hing sie an jedem Subjekt-Schritt (dieselbe Zahl mehrfach berechnet,
    samt FIFO-Abfrage je Schritt) – und in einem Prozess ohne Subjekt-Schritt war sie gar
    nicht sichtbar. ``kind`` unterscheidet Fertigware und Komponente, damit das Frontend
    keine eigene Schritttyp-Liste spiegeln muss."""
    from app.schemas.order import OrderResponse, OrderStepInfo, StepShortfall

    assert {"shortfall", "waiting_for"} <= set(OrderResponse.model_fields)
    assert "shortfall" not in OrderStepInfo.model_fields
    assert "waiting_for" not in OrderStepInfo.model_fields
    assert "kind" in StepShortfall.model_fields


def test_a_reported_deviation_holds_its_instance_immediately():
    """Ab der **Meldung**, nicht erst ab der Freigabe: ein am Lager liegendes Teil, über das
    eine Abweichung läuft, darf kein anderer Auftrag per FIFO wegnehmen. Zwischen «Verdacht
    gemeldet» und «Auflösung konfiguriert» war es vorher frei verfügbar."""
    import inspect as _inspect
    from app.services.deviation import create_deviation, detach_sub_order

    assert "claim(inst, devi.id, want)" in _inspect.getsource(create_deviation)
    # Und die EINE Aufräum-Stelle gibt sie wieder her.
    assert "release_reservation" in _inspect.getsource(detach_sub_order)


def test_only_a_running_order_can_be_short():
    """**Eine Fehlmenge hat nur ein laufender Auftrag** (Testnotiz #347).

    Ein Entwurf hat noch nichts zugesagt (und keine Instanzen), ein abgeschlossener oder
    abgebrochener hat abgerechnet – dort sind Reservierung und Subjekt-Bindung längst
    gelöst, «Soll − Gesichert» ergäbe die volle Menge als Phantom-Fehlmenge («Es fehlt 1×»
    an einem fertigen Auftrag). Die Fehlmenge beschreibt offene Arbeit, nicht Geschichte."""
    import ast
    import inspect as _inspect
    from app.services.process import _subject_shortfalls

    src = ast.unparse(ast.parse(_inspect.getsource(_subject_shortfalls)))
    assert "order.status != 'released'" in src, (
        "Nur ein laufender Auftrag kann etwas schulden – sonst meldet ein abgeschlossener "
        "seine volle Menge als Fehlmenge")


def test_a_deviation_is_linked_by_the_instance_not_by_the_parent():
    """**Die RECHNUNG folgt der Instanz, die ANZEIGE dem Eltern** (Notizen #348/#350/#397).

    Ein Auftrag referenziert Instanzen; eine Abweichung tut dasselbe. Für die Frage «was
    fehlt mir?» zählt darum die Instanz und nicht der Eltern-Zeiger: steckt eines meiner
    Stücke in einer offenen Abweichung, fehlt es mir – ganz gleich, an welchem Auftrag sie
    formal hängt (``deviated_quantities``).

    Für die **Darstellung** gilt das ausdrücklich NICHT (#397): ein Unter-Auftrag steht bei
    dem Auftrag, dem er etwas weggenommen hat – bei seinem Eltern. Sonst stünde in der Kette
    Auftrag → Abweichung → Abweichung die zweite auch im Hauptauftrag, obwohl sie dort nichts
    zu suchen hat. Dass ein anderer Auftrag betroffen ist, sagt ihm die Unterdeckungs-Frage
    bei der Freigabe."""
    import inspect as _inspect
    from app.services import deviation, orders
    from app.services.process import deviated_quantities

    short = _inspect.getsource(deviated_quantities)
    assert "order_instances" in short and "parent_order_id" not in short
    # Sich selbst zählt eine Abweichung nie – sonst gäbe sie beim Abschluss nichts frei.
    assert "discard(order.id)" in short

    assert not hasattr(deviation, "deviations_touching"), (
        "Der Fremd-Knoten ist entfallen – ein Unter-Auftrag gehört genau einem Auftrag.")
    subs = _inspect.getsource(orders._order_sub_orders)
    assert "Order.parent_order_id == order.object_id" in subs and "InstanceOrderLink.order_id == c.id" in subs


def test_the_order_level_deviation_is_the_abort():
    """**Am Auftrag gibt es nur den Abbruch** – aber ohne eigenen Weg dorthin (#351/#366).

    Ohne Instanz-Auswahl greift die Abweichung auf ALLE Instanzen; dem Eltern bleibt nichts,
    und die Antwort «Auftragsmenge reduzieren» vollzieht damit seinen Abbruch. Es gibt weder
    einen zweiten Endpunkt noch einen Schalter."""
    import inspect as _inspect
    from app.routers import orders
    from app.services import recovery

    # Es gibt keinen Abbruch-Weg mehr: man legt einen Auftrag an, wählt die Instanzen des
    # laufenden – und bei der Freigabe entscheidet die Antwort, was mit ihm geschieht.
    assert not hasattr(orders, "open_deviation")
    src = _inspect.getsource(orders._do_release)
    assert "_enforce_claims(db, order, answer, actor_id)" in src
    assert "_apply_shortfall_answer(db, holders, answer, actor_id, into=order)" in src
    assert "aborted" in _inspect.getsource(recovery.confirm_quantity)


def test_an_order_and_a_deviation_order_are_the_same_thing():
    """**Ein Auftrag und ein Abweichungsauftrag sind dasselbe – der Unterschied ist ein Tag.**

    Es gibt EINEN Weg, einen Auftrag anzulegen, EINE Tabelle, EIN Schema, EINEN
    Freigabe-Pfad. Was ihn zur Abweichung macht, wird **abgeleitet** (nicht angeklickt):
    ``subject.classify_pick`` liest es aus der Instanz-Auswahl – verkauft → Retoure ·
    gebunden (in Arbeit/reserviert/gesperrt) → Abweichung · frei → gewöhnlicher Auftrag.
    Genau so leitet die Retoure sich seit jeher ab; die Abweichung folgt derselben Regel
    statt einem eigenen Endpunkt mit eigenen Regeln."""
    import inspect as _inspect
    from app.models import Order
    from app.routers import orders
    from app.services import subject

    # Ein Modell, ein Tag: die Art ist ein Feld, kein eigener Typ.
    assert hasattr(Order, "reason")
    for name in ("classify_pick", "holding_order", "PICK_DEVIATION", "PICK_RETURN"):
        assert hasattr(subject, name), name

    pick = _inspect.getsource(subject.classify_pick)
    assert '"sold"' in pick and "is_bound(order, i, " in pick
    bound = _inspect.getsource(subject.is_bound)
    assert "is_in_stock" in bound and "free_qty" in bound and "reserved_for" in bound

    # Die Prüfung der Auswahl kennt kein Vorab-Flag mehr – sie lässt jede aktive Instanz zu.
    # Über den AST geprüft, damit ein Kommentar über die FRÜHERE Regel nicht mitzählt.
    import ast
    val = ast.unparse(ast.parse(_inspect.getsource(orders._resolve_picks)))
    assert "is_deviation" not in val, (
        "Die Art des Auftrags darf keine VORAUSSETZUNG der Auswahl sein, sondern ihre FOLGE")

    # Der Eltern-Auftrag wird abgeleitet, nicht eingegeben.
    make = _inspect.getsource(orders._make_deviation)
    assert "holding_order" in make and "parent_order_id" in make


def test_the_shortfall_question_comes_at_release_not_at_the_pick():
    """**Ein Entwurf nimmt niemandem etwas weg** (Testnotiz #370).

    Die Frage «was geschieht mit dem laufenden Auftrag?» stand früher schon beim Auswählen.
    Das war zu früh: danach definiert man den Auftrag ja erst fertig – Artikel, Menge und
    Instanzen können sich noch ändern, und die Entscheidung wäre womöglich gleich wieder
    falsch. Jetzt merkt die Auswahl nur vor (``claim``, ohne fremde Ansprüche anzutasten),
    und erst die **Freigabe** macht sie scharf (``enforce``) – dort, wo der andere Auftrag
    wirklich etwas verliert, steht auch die Frage."""
    import inspect as _inspect
    from app.routers import orders
    from app.schemas.order import OrderUpdate
    from app.services import reservation

    assert orders.SHORTFALL_ANSWERS == ("wait", "replace", "accept")
    assert "shortfall_response" in OrderUpdate.model_fields

    # Die Auswahl fragt NICHT mehr …
    assert "_assert_answered" not in _inspect.getsource(orders._make_deviation)
    # … die Freigabe schon.
    assert "_assert_answered(db, response, holders)" in _inspect.getsource(orders._enforce_claims)
    # Scharf wird der Anspruch in der Freigabe selbst – damit auch die systemseitig
    # angelegte Abweichung (Datenerfassung/Deaktivierung) ihn durchsetzt, nicht nur der
    # Weg über den Router.
    from app.services import subject
    assert "enforce_pick(db, order, inst)" in _inspect.getsource(subject._bind_deviation_subjects)
    assert "enforce_pick(db, order, inst)" in _inspect.getsource(subject._allocate_stock_for)
    # Vormerken tastet fremde Ansprüche nicht an, Durchsetzen schon.
    assert "over" not in _inspect.getsource(reservation.claim)
    assert "over" in _inspect.getsource(reservation.enforce)
    assert "recovery.cover_shortfall" in _inspect.getsource(orders._apply_shortfall_answer)
    assert "recovery.confirm_quantity" in _inspect.getsource(orders._apply_shortfall_answer)


def test_every_affected_order_is_asked_the_same_question():
    """**Eine Unterdeckung, eine Frage – für JEDEN Betroffenen** (Testnotiz #397).

    Eine Abweichung (ebenso Retoure/Bereitstellung) beschafft nichts, sie **behandelt**
    bestimmte Stücke. Daraus wurde der Schluss gezogen, sie habe kein Soll und brauche
    deshalb keine Frage: sie schrumpfte lautlos mit und wurde abgebrochen, wenn nichts
    blieb. Das waren zwei Logiken für dieselbe Lage – und in der Praxis endete eine
    Abweichung an einer Abweichung ohne jede Rückfrage im Abbruch der ersten.

    Ihr Soll sind schlicht die Stücke, die sie behandeln sollte; was ihr davon weggenommen
    wird, fehlt ihr (``process._held_amounts``). Damit fällt sie unter dieselbe Formel wie
    jeder andere Auftrag, bekommt dieselben drei Antworten – und «Menge reduzieren» IST ihr
    Abbruch, wenn nichts bleibt (dieselbe Mechanik wie beim Eltern, Notiz #366)."""
    import inspect as _inspect

    from app.routers import orders
    from app.services import process, recovery

    apply_src = _inspect.getsource(orders._apply_shortfall_answer)
    assert "is_fixed_subject" not in apply_src, "kein Sonderweg mehr für feste Subjekte"
    assert "recovery.cover_shortfall" in apply_src and "recovery.confirm_quantity" in apply_src
    assert not hasattr(recovery, "retire_if_subjectless"), (
        "Der automatische Abbruch ist in «Menge reduzieren» aufgegangen – eine Regel weniger.")
    # Gefragt wird, sobald überhaupt jemand betroffen ist.
    ask = _inspect.getsource(orders._enforce_claims)
    assert "if holders:" in ask and "is_fixed_subject" not in ask
    # Und das feste Subjekt hat eine Fehlmenge: Soll − was es noch hält.
    short = _inspect.getsource(process._subject_shortfalls)
    assert "_held_amounts(db, order) if is_fixed_subject(order)" in short
    held = _inspect.getsource(process._held_amounts)
    assert "reserved_for(inst, order.id)" in held and "subject_of_order_id != order.id" in held
    assert "targets.get(inst.article_id" in held, (
        "Bei einer Retoure liegt die Menge beim KUNDEN – eine verkaufte Instanz trägt keine "
        "Restmenge und kann keinen Anspruch führen; gebunden heisst dort «vollständig gehalten».")


def test_clarification_counts_every_open_deviation_not_just_the_last_pointer():
    """**Mehrere Abweichungen können dieselbe Charge mengenweise binden** (Testnotiz #388).

    Wer eine Abweichung nicht abbricht, sondern eine zweite danebenstellt, hat zwei offene
    Vorgänge an derselben Instanz. Gezählt wurde aber nur, worauf ``subject_of_order_id``
    zeigt – und das ist immer nur die **zuletzt** gesetzte Bindung. Die erste Abweichung
    fiel damit still aus der Rechnung, und der Eltern-Auftrag führte zu viel als
    «gesichert».

    Massgeblich ist die **Anspruchs-Map** (``instances.reservations``): dort steht je
    Auftrag die beanspruchte Menge, und die Summe über alle offenen Abweichungen ist, was
    in Klärung steckt. Der Zeiger bleibt nur der Rückfall für Altbestand ohne Anspruch."""
    import inspect as _inspect

    from app.services import process

    src = _inspect.getsource(process.deviated_quantities)
    assert "claimants" in src and "i.reservations" in src
    assert "qty_sum(reserved_for(i, d) for d in open_devs)" in src
    # Nicht mehr «nur die Instanzen mit Bindung» – die Map ist die Quelle.
    assert "mine = order_instances(db, order)" in src
    # Mehr als es gibt kann nicht in Klärung sein.
    assert "min(share, to_qty(i.quantity))" in src


def test_a_pick_names_the_share_it_takes():
    """**Du wählst keinen Gegenstand, sondern einen Anteil.**

    Eine Instanz ist eine MENGE, und ihre Menge ist immer vollständig aufgeteilt: jeder
    Anteil gehört genau einem Auftrag oder ist frei (``instances.reservations``). Wer
    auswählt, wählt darum drei Dinge zugleich – **welche** Instanz, **wie viel** davon und
    **wem** er es wegnimmt (``InstancePick``).

    Der dritte Punkt war die Lücke. Hält eine Charge à 4 zwei Ansprüche (Hauptauftrag 2,
    Abweichung 2) und ein dritter Auftrag greift 1 Stück, musste die Freigabe **raten**, wer
    verliert – bei EINEM anderen Halter zufällig richtig, ab zwei Willkür. Jetzt steht es in
    ``orders.pick_sources``, und ``reservation.enforce`` kürzt genau den.

    Der genannte Anteil ist dabei eine **Rangfolge, keine Ausschliesslichkeit**: wer 2 aus
    einer 2er-Charge nimmt, an der zwei Aufträge hängen, trifft zwangsläufig beide."""
    import inspect as _inspect
    from app.models import Order
    from app.routers import orders
    from app.schemas.order import InstancePick, OrderCreate, OrderLineCreate, OrderLinePins, OrderUpdate
    from app.services import reservation, shares

    for field in ("instance_object_id", "quantity", "from_order_object_id"):
        assert field in InstancePick.model_fields, field
    for schema in (OrderCreate, OrderUpdate, OrderLineCreate, OrderLinePins):
        assert "picks" in schema.model_fields, schema.__name__
        assert "instance_object_ids" not in schema.model_fields, schema.__name__
    assert hasattr(Order, "pick_sources")

    # Die Auswahl schreibt den Halter mit – IMMER, mit ``None`` für «frei».
    pick = _inspect.getsource(orders._resolve_picks)
    assert "sources[oid] = holder_id" in pick
    assert "subject.is_bound(order, i, want)" in pick, (
        "«frei oder gehalten» ist EINE Definition (``subject.is_bound``) – nicht zwei")

    # Und die Freigabe kürzt den GENANNTEN zuerst.
    enf = _inspect.getsource(reservation.enforce)
    assert "from_order_id" in enf and "ranked" in enf
    # Wer gefragt wird, steht an EINER Stelle – dieselbe Rangfolge.
    los = _inspect.getsource(shares.losses)
    assert "pick_sources" in los and "inst.order_id" in los
    # Und die **Menge** gehört zur Antwort, nicht nur der Auftrag (Notiz #391).
    assert "-> dict[int, Decimal]" in los


def test_the_creator_holds_the_rest_until_it_reaches_stock():
    """**Der unbeanspruchte Rest ist nur am Lager wirklich frei.**

    Steckt eine Instanz noch in ihrem Erzeugungsauftrag (in Arbeit, gesperrt), gehört der
    nicht beanspruchte Teil IHM – er hat ihn hervorgebracht. Ohne diese Regel zeigte die
    Auswahl «frei» an einem Stück, das mitten in einem Prozess hängt, und der Erzeuger
    würde bei einem Zugriff nicht gefragt."""
    import inspect as _inspect
    from app.services import shares

    src = _inspect.getsource(shares)
    assert "def _creator" in src and "is_in_stock" in src


def test_replacement_is_only_offered_when_the_piece_is_interchangeable():
    """**Ersatz gibt es nur, wenn dem Auftrag egal ist, WELCHES Stück es ist.**

    Ein frisches Stück ist kein Ersatz, wenn das Fehlende die Geschichte dieses Auftrags
    trägt: er hat es **selbst erzeugt** oder ein Schritt hat **schon daran gearbeitet**
    (steht der Ablauf bei Schritt 3, hat ein neues Teil die Schritte 1–2 nie durchlaufen).
    **Material** ist immer austauschbar – der Auftrag braucht *fünf Schrauben*, nicht
    *diese fünf*. EINE Ableitung statt einer Fallunterscheidung je Auftragsart."""
    import inspect as _inspect
    from app.schemas.order import StepShortfall
    from app.services import recovery

    assert "replaceable" in StepShortfall.model_fields
    src = _inspect.getsource(recovery.is_replaceable)
    assert 'subject_kind(db, order) != "produce"' in src
    assert 'state"] == "done"' in src


def test_an_order_is_created_as_a_whole_even_with_steps():
    """**Alles oder nichts – auch mit Ablauf.**

    Die Auftrags-Anlage spannt EINE Transaktion über Bedarf, Positionen, Ablauf und Auswahl
    (Testnotiz #386). Der Schritt-Editor committete aber für sich; schlug danach etwas fehl
    (z. B. die offene Unterdeckungs-Frage), blieb ein Auftrag **ohne Objektnummer** zurück –
    genau das, was #386 abschaffen sollte. Gegen echtes PostgreSQL gefunden."""
    import inspect as _inspect
    from app.routers import article_process, orders

    assert "commit: bool = True" in _inspect.getsource(article_process._create)
    assert "commit=False" in _inspect.getsource(orders.create_order)


def test_a_holder_loses_the_taken_quantity_not_its_own_order_quantity():
    """**«verliert 2» heisst 2 – nicht 4, nur weil der Auftrag über 4 lautet** (Notiz #391).

    Die Frage «was geschieht mit dem laufenden Auftrag?» stand mit der **Sollmenge des
    Betroffenen** da: wer 2 Stück aus einer 4er-Charge in eine Abweichung nimmt, las
    «verliert 4». Das ist keine Rundung, sondern eine andere Aussage – sie liest sich wie
    ein Totalverlust und macht die Entscheidung unmöglich.

    Was ein Halter verliert, rechnet dieselbe Stelle aus, die auch sagt, WER verliert
    (``shares.losses``): genannter Anteil ≻ freier Rest ≻ Erzeuger ≻ übrige. ``losers`` ist
    die zweite Form derselben Regel.

    Und es gibt sie **nur einmal**: die zweite Fassung in ``services/orders._fill_affected``
    meldete, was ein Halter überhaupt HÄLT statt was er VERLIERT – genau der gemeldete
    Fehler, nur an der anderen Oberfläche (laufender Auftrag statt Freigabe)."""
    import inspect as _inspect
    from app.services import orders as ord_svc, shares

    assert "-> dict[int, Decimal]" in _inspect.getsource(shares.losses)
    assert "losses(db, inst, order, want)" in _inspect.getsource(shares.losers), (
        "«wer verliert» und «wie viel» sind zwei Formen EINER Regel")
    # Die Menge wandert bis in die Frage – nicht die Sollmenge des Betroffenen.
    rows = _inspect.getsource(shares.affected_rows)
    assert "quantity=float(h.quantity)" in rows and "h.order.quantity" not in rows
    # Beide Oberflächen fragen dieselbe Stelle.
    fill = _inspect.getsource(ord_svc._fill_affected)
    assert "affected_rows(db, affected(db, order, picked))" in fill
    assert "reserved_for" not in fill, "keine zweite Rechnung für dieselbe Frage"


def test_the_picker_selection_follows_the_current_rows():
    """**Eine Auswahl ist eine Aussage über EINEN Moment; die Zeilen sind der Stand** (#390).

    Der Abkürzungs-Knopf an der Instanz kannte den Halter nicht und merkte «1 Stk, frei»
    vor – eine Zeile, die es in der Auswahl gar nicht gibt (die Charge gehört ihrem
    Erzeuger). Die Vormerkung war damit unsichtbar UND zählte zur Menge: bei Auftragsmenge
    1 galt die Zeile als «schon beisammen» und liess sich nicht mehr anklicken. 1 von 4
    ging nicht, 2 von 4 schon – genau der gemeldete Widerspruch.

    Zwei Korrekturen, beide strukturell: die Vorauswahl **nennt** ihren Halter, und die
    Auswahl **folgt** den aktuellen Zeilen (``reconcilePicks``), statt auf einen Anteil zu
    zeigen, den es nicht gibt."""
    from pathlib import Path
    fe = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "erp"
    detail = (fe / "order-detail.tsx").read_text()
    assert "function reconcilePicks" in detail
    assert "capacity" in detail, (
        "Ein gewählter Anteil darf zusätzlich das umfassen, was der Auftrag selbst hält – "
        "sein Anspruch ist im Entwurf noch nicht scharf.")
    inst = (fe / "instance-detail.tsx").read_text()
    assert "fromOrderObjectId" in inst, "Die Vorauswahl nennt ihren Halter."


def test_a_pick_is_never_a_production():
    """**Wer vorhandene Instanzen auswählt, erzeugt keine** (Testnotiz #392).

    Ein Auftrag ohne eigene Schritte fährt den **Artikel**-Prozess – der beschreibt, wie
    etwas ENTSTEHT. Wer aber Instanzen auswählt, sagt «das Material gibt es schon». Vorher
    galt ausdrücklich das Gegenteil («eine Pin-Auswahl kippt den Auftrag NICHT»), und die
    Folge war ein stiller Widerspruch: der Auftrag lief den Artikel-Prozess, ERZEUGTE neue
    Instanzen – und hielt die ausgewählten daneben fest. Freigeben liess er sich obendrein
    mit komplett leerem Ablauf.

    Zwei Sätze, eine Regel: die Auswahl macht den Auftrag zur **Bestands-Operation**, und
    eine Bestands-Operation braucht einen **eigenen** Ablauf."""
    import inspect as _inspect
    from app.routers import orders
    from app.services import subject

    kind = _inspect.getsource(subject.subject_kind)
    assert "if chosen_subjects(db, order):" in kind and 'return "stock"' in kind, (
        "Die Auswahl entscheidet über die Subjektart – an der EINEN Stelle, die sie ableitet.")
    gate = _inspect.getsource(orders._assert_releasable)
    assert "processes_svc.order_custom_steps(db, order.id)" in gate, (
        "Alles ausser einer Erzeugung braucht EIGENE Schritte – der Artikel-Prozess zählt "
        "dafür nicht (sonst genügte er als Ablauf für fremdes Material).")
    rel = _inspect.getsource(orders._do_release)
    assert rel.index("db.flush()") < rel.index("_assert_releasable"), (
        "Das Gate liest, was dieselbe Anfrage eben geschrieben hat (autoflush=False).")


def test_the_shortfall_question_names_order_quantity_and_source():
    """**Wer verliert wie viel wovon** – die Frage beantwortet drei Dinge (Notiz #393).

    Sie las sich als «Schraubendreher 100000555 verliert 1 Schraubendreher»: der Name eines
    Auftrags IST der Artikelname, also sah die Zeile aus wie ein Artikel; die Menge trug den
    Artikelnamen als Einheit (er stand schon links); und woher das Stück kommt, stand
    nirgends. Jetzt: Datensatzart + Name + Objektnummer, Menge in der **Einheit**, und die
    **Herkunftsinstanz**."""
    import inspect as _inspect
    from pathlib import Path
    from app.schemas.order import AffectedOrder
    from app.services import shares

    for field in ("unit", "sources", "quantity"):
        assert field in AffectedOrder.model_fields, field
    assert "needs_decision" not in AffectedOrder.model_fields, (
        "Jeder Betroffene braucht eine Antwort – es gibt keine zwei Sorten mehr (#397).")
    rows = _inspect.getsource(shares.affected_rows)
    assert "unit=art.unit" in rows and "AffectedShare(instance_object_id=oid" in rows
    fe = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "erp"
    dlg = (fe / "shortfall-dialog.tsx").read_text()
    assert "unitLabel(a.unit)" in dlg, "Die Menge trägt die Einheit, nicht den Artikelnamen."
    assert "a.article_name" not in dlg
    assert "'Abweichung' : 'Auftrag'" in dlg, "Die Zeile sagt, dass sie einen Auftrag meint."
    assert "instance_object_id" in dlg, "… und woher die Menge kommt."


def test_a_pick_is_not_guessed_when_it_is_a_decision():
    """**Wo es mehrdeutig ist, entscheidet der Mensch** (Testnotiz #394, Frontend-Hälfte).

    Seit der genannte Anteil bei der Freigabe wirklich verliert, ist die Wahl der Zeile
    keine Formsache mehr: den grössten Anteil zu raten (so kam #390 zustande) hiesse, dem
    falschen Auftrag etwas wegzunehmen. Trägt eine Instanz mehrere Anteile, wird darum
    nichts vorgewählt – und eine Auswahl, die auf keine Zeile passt, wandert nur dann auf
    eine andere, wenn es genau EINE gibt."""
    from pathlib import Path
    fe = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "erp"
    inst = (fe / "instance-detail.tsx").read_text()
    assert "rows.length === 1 ? { fromOrderObjectId:" in inst, (
        "Mehrere Anteile ⇒ kein vorgewählter Anteil – die Zeile ist eine Entscheidung. "
        "Die INSTANZ kommt trotzdem mit, sonst fiele der Bedarf auf «Ab Lager» (#400).")
    assert "reduce<" not in inst.split("function createOrderShortcut")[1].split("}")[0], (
        "Kein «grösster Anteil gewinnt» mehr.")
    detail = (fe / "order-detail.tsx").read_text()
    assert "rows.length === 1 ? rows[0] : null" in detail, (
        "reconcilePicks rät nicht – es folgt nur einer eindeutigen Zeile.")


def test_a_deviation_borrows_and_gives_back():
    """**Ein Unter-Auftrag mit festem Subjekt LEIHT – am Ende gibt er zurück** (Notiz #401).

    Eine Abweichung nimmt dem Auftrag, an dem das Stück hing, etwas ab; solange sie läuft,
    fehlt es dort – **die Unterdeckung IST die Ausleihe**. Ist sie erfolgreich durch (nichts
    verschrottet), kehrt das Stück dorthin zurück. Vorher wurde beim Abschluss nur die eigene
    Reservierung gelöst: das Stück wurde damit **frei** statt zurückgegeben, und der Verleiher
    verlangte eine Entscheidung über etwas, das längst wieder da war.

    Was den Bestand verlassen hat (verschrottet/verkauft/verbaut), kehrt NICHT zurück – dort
    ist die Fehlmenge ehrlich. Dieselbe Rückgabe vollzieht das Verwerfen
    (``deviation.detach_sub_order``) – zwei Türen, eine Regel."""
    import inspect as _inspect
    from app.services import deviation, process, subject

    ret = _inspect.getsource(subject.return_borrowed)
    assert "TERMINAL_DISPOSITIONS" in ret, "Verschrottetes kehrt nicht zurück."
    assert "inst.order_id == parent.id" in ret, (
        "Ein Erzeuger als Verleiher hält ohne Reservierung – er braucht nichts zurück.")
    assert "lender_of(db, sub)" in ret, (
        "Zurück an den nächsten LAUFENDEN Verleiher der Kette (#404).")
    assert "subject_shortfalls(db, parent)" in ret, (
        "Nur so viel, wie dort noch fehlt – sonst bliebe Überschuss reserviert (#403).")
    done = _inspect.getsource(process.recompute_completion)
    assert done.index("return_borrowed(db, order)") < done.index("release(inst, order.id)"), (
        "Zurückgeben, BEVOR die eigene Reservierung gelöst wird – sonst wird es frei.")
    # Die zweite Tür (verwerfen) gibt seit jeher zurück.
    assert "reserve(inst, parent.id, freed)" in _inspect.getsource(deviation.detach_sub_order)


def test_a_quantity_belongs_to_an_order_not_to_an_instance():
    """**Wie viel dieser Instanz gehört diesem Auftrag?** – EINE Antwort (Notiz #399).

    Eine Instanz ist eine Menge, und ein Auftrag hat fast nie die ganze: von einer Charge à 4
    gehören ihm vielleicht 2. Wer stattdessen ``inst.quantity`` nimmt, rechnet mit fremdem
    Bestand – daraus wurde «Prüfumfang: 4 von 2 Stück». Das ist die wiederkehrende
    Fehlerklasse rund um Chargen; sie hat jetzt genau eine Stelle
    (``subject.held_quantity``), und wer eine Menge braucht, fragt dort."""
    import inspect as _inspect
    from app.services import inspection, process, subject

    src = _inspect.getsource(subject.held_quantity)
    assert "reserved_for(inst, order.id)" in src and "to_qty(inst.quantity)" in src
    for fn in (inspection.inspected_quantity, inspection.sample_targets, process._held_amounts):
        assert "held_quantity" in _inspect.getsource(fn), fn.__name__


def test_the_loan_returns_along_the_chain_and_only_what_is_needed():
    """**Zurück geht es an den nächsten LAUFENDEN Verleiher – und nur, was dort fehlt**
    (Testnotizen #403/#404).

    Kette Auftrag → Abweichung → Abweichung: nimmt die zweite der ersten alles, wird die
    erste gegenstandslos und abgebrochen. Schliesst die zweite ab, darf das Stück nicht bei
    der toten hängenbleiben – es kehrt dorthin zurück, wo es herkam, und der Hauptauftrag
    läuft weiter. Vorher endete die Rückgabe am abgebrochenen Eltern; das Stück wurde
    schlicht frei und der Hauptauftrag ruhte für immer.

    Und zurück geht nur, was der Verleiher **noch braucht**: hat er inzwischen «Ersetzen»
    gewählt, ist sein Bedarf gedeckt – das zurückkommende Stück bliebe sonst als Überschuss
    für ihn reserviert liegen, obwohl er es nicht braucht."""
    import inspect as _inspect
    from app.services import recovery, subject

    ret = _inspect.getsource(subject.return_borrowed)
    assert "lender_of(db, sub)" in ret and "subject_shortfalls(db, parent)" in ret
    chain = _inspect.getsource(subject.lender_of)
    assert 'cur.status == "released"' in chain and "seen" in chain, "Kette, zyklensicher."
    # Und ein Stück, das der Auftrag ohnehin hielt, ist kein «Ersatz» (#403).
    cov = _inspect.getsource(recovery._fifo_cover)
    assert "was_mine = reserved_for(cand, order.id) > 0" in cov
    assert "not used.get(aid)" in _inspect.getsource(recovery.cover_shortfall)


def test_a_finished_inspection_keeps_the_samples_it_captured():
    """**Erfasst ist erfasst** (Testnotiz #402).

    Die Proben wurden bei jedem Aufruf aus dem *Plan* neu gerechnet («wie viel gehört dem
    Auftrag?»). Nach seinem Abschluss ist die Reservierung gelöst – der Plan lieferte dann
    wieder die ganze Charge, und aus 2 erfassten Proben wurden 4 angezeigte. Eine
    abgeschlossene Prüfung ist eine Tatsache; solange sie läuft, bleibt der Plan
    massgeblich (nach einer Hochstufung auf 100 % sind ja zusätzliche Proben zu erfassen)."""
    import inspect as _inspect
    from app.services import orders

    src = _inspect.getsource(orders._inspection_embed)
    assert 'insp.result in ("passed", "failed")' in src
    assert src.index("ie.required_count = len(ie.samples)") < src.index("sample_targets(db, order, step)")


def test_a_taken_share_is_not_a_replacement():
    """**Drei Ereignisse, drei Sätze – kein Sammel-Else** (Testnotiz #405).

    Die Auflösungs-Zeile kannte nur «Menge angepasst» und *alles andere* = «N ab Lager
    ersetzt». Damit las sich auch ein **entzogener** Anteil (``share_taken`` – ein anderer
    Auftrag hat sich hier ein Stück geholt) als Ersatz aus dem Lager: wer «Auftrag
    pausieren» gewählt hatte, sah trotzdem «1 ab Lager ersetzt». Genau umgekehrt – dort ist
    etwas weggegangen."""
    from pathlib import Path
    fe = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "erp"
    flow = (fe / "order-flow.tsx").read_text()
    for kind in ("quantity_confirmed", "covered_from_stock", "share_taken"):
        assert f"r.kind === '{kind}'" in flow, kind
    assert "abgegeben" in flow, "Ein entzogener Anteil ging WEG – er kam nicht dazu."


def test_waiting_follows_the_chain_so_there_is_no_dead_decision():
    """**Wer die Menge wirklich hält, macht das Warten aus** (Testnotiz #406).

    Nimmt eine Abweichung der Abweichung alles, wird die mittlere gegenstandslos und
    abgebrochen – gehalten wird die Menge dann von der untersten. Wer nur die direkten
    Kinder ansah, fand niemanden mehr und stellte die Frage erneut: eine **tote
    Entscheidung**, obwohl längst entschieden ist und es läuft.

    «Wartet» ist ein Zustand, kein Knopf (#354) – also muss die Antwort denjenigen finden,
    der die Menge hält, und nicht bloss den direkten Nachbarn."""
    import inspect as _inspect
    from app.services import supply

    src = _inspect.getsource(supply.covering_sub_orders)
    assert "frontier" in src and 'o.status == "inactive"' in src, (
        "Ein abgebrochener Unter-Auftrag hält nichts mehr – aber SEIN Nachfolger tut es.")
    assert "range(10)" in src, "Tiefen-Schranke statt Endlosschleife."


def test_the_flow_shows_the_branch_in_both_directions():
    """**Am Ende ist alles ein Prozess – und der geht in beide Richtungen** (Testnotiz #409).

    Der Eltern-Auftrag zeigte den Abzweig längst an seiner Stelle im Ablauf; die
    Gegenrichtung fehlte. Wer in einer Abweichung stand, sah nicht, aus welchem Auftrag und
    aus welchem **Schritt** sie hervorgegangen ist – und schon gar nicht, wohin ihre Stücke
    beim Abschluss zurückkehren.

    Der Wächter hält fest, dass beide Teaser **lesen**, was ohnehin gilt, statt es ein
    zweites Mal zu behaupten:

    * das Rückgabe-Ziel kommt aus derselben Ableitung, die es auch TUT
      (``subject.lender_of`` für die Ausleihe, das Pegging für den Nachschub) – ein fest
      verdrahteter «der Eltern» wäre falsch, sobald der Eltern abgebrochen wurde (#404);
    * der angeteaserte Ablauf des Abzweigs kommt aus derselben Schritt-Ableitung wie der
      grosse Fluss (``process.build_order_steps``) – ein eigener «ist wohl erledigt»-Zweig
      im Teaser würde neben dem echten Zustand herlaufen.
    """
    import inspect as _inspect
    from app.services import orders

    back = _inspect.getsource(orders._return_target)
    assert "lender_of(db, order)" in back, (
        "Wohin zurückgegeben wird, weiss die Mechanik der Ausleihe – nicht der Teaser.")
    assert 'order.reason == "supply"' in back and 'parent.status == "released"' in back

    teaser = _inspect.getsource(orders._sub_order_steps)
    assert "process.build_order_steps(db, sub)" in teaser, (
        "Der Teaser ist eine Verkleinerung desselben Flusses, keine zweite Rechnung.")
    assert "cache" in teaser, (
        "Derselbe Unter-Auftrag steht in der Auftrags-Liste UND an seinem Schritt – "
        "seine Ableitung darf je Antwort nur einmal laufen.")


def test_an_order_only_scraps_the_share_it_holds():
    """**Aussondern wirkt auf den ANTEIL, nicht auf die Instanz** (Testnotizen #412/#414).

    Eine Instanz ist eine Menge, und ihre Menge ist auf Aufträge aufgeteilt: von einer
    4er-Charge können 2 diesem Auftrag und 2 einer Abweichung gehören. ``_scrap_one`` mass
    «ganz» aber an ``inst.quantity`` – eine Abweichung, die 2 hielt, verschrottete damit
    **alle 4**: fremdes Material weg, und der Eltern-Auftrag stand mit einer Fehlmenge da,
    die niemand verursacht hatte.

    Dieselbe Frage hat längst eine Antwort (``subject.held_quantity``, Notiz #399) – sie
    wird hier nur endlich gestellt. Und die Oberfläche liest sie ebenso, statt eine zweite
    Rechnung aufzumachen (``lib/process.heldOf``)."""
    import inspect as _inspect
    from pathlib import Path

    from app.services import scrap

    src = _inspect.getsource(scrap._scrap_one)
    assert "held = held_quantity(order, inst)" in src, (
        "Der Massstab ist der Anteil des Auftrags, nicht die ganze Instanz.")
    assert "held >= to_qty(inst.quantity)" in src, (
        "«Ganz» heisst nur dann ganz, wenn der Auftrag die ganze Instanz hält.")
    assert "der Auftrag hält nur" in src, "Mehr als den eigenen Anteil kann niemand aussondern."

    fe = Path(__file__).resolve().parents[2] / "frontend" / "src"
    assert "export function heldOf" in (fe / "lib" / "process.ts").read_text(encoding="utf-8")
    for name in ("scrap-panel.tsx", "order-positions.tsx", "movement-panel.tsx"):
        assert "heldOf(" in (fe / "components" / "erp" / name).read_text(encoding="utf-8"), (
            f"{name} rechnet noch mit der ganzen Instanz statt mit dem Anteil des Auftrags")


def test_the_decision_is_a_gate_in_the_flow():
    """**Entscheidungen sind Gates, keine Notizen darunter** (Testnotiz #413).

    Eine Raute ist im Flowchart das Zeichen für «hier wird entschieden» – und genau das
    passiert an einer Unterdeckung. Offen ist das Gate **anklickbar** und stellt die eine
    Frage; ist entschieden, trägt dieselbe Raute die Antwort («Menge angepasst 4 → 2»).
    Damit ist die Entscheidung ein Knoten im Fluss statt einer Notiz unter ihm.

    Die frühere ``ProcessHoldNotice`` ist entfallen – zwei Orte für dieselbe Frage gibt es
    nicht mehr."""
    from pathlib import Path

    fe = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "erp"
    flow = (fe / "order-flow.tsx").read_text(encoding="utf-8")
    for part in ("function Gateway", "function ResolutionLine"):
        assert part in flow, f"Dem Fluss fehlt {part}"
    assert "transform: 'rotate(45deg)'" in flow, "Ein Gate ist eine Raute."
    # **Nur die offene Entscheidung ist ein Knoten** (Testnotiz #434). «wartet» und die
    # bereits getroffene Antwort waren reine Information – und die trägt der Fluss ohnehin:
    # ein offener Abzweig IST das Warten, eine Auflösung steht als Zeile an ihrer Stelle.
    assert "function gateFor" not in flow and "'waiting'" not in flow, (
        "Ein Zustand, den das Flussbild schon zeigt, braucht kein zweites Symbol (#434).")
    for kind in ("quantity_confirmed", "covered_from_stock", "share_taken"):
        assert f"r.kind === '{kind}'" in flow, kind
    detail = (fe / "order-detail.tsx").read_text(encoding="utf-8")
    assert "ProcessHoldNotice" not in detail, (
        "Die Fehlmenge-Notiz unter dem Fluss ist im Gate aufgegangen – eine Frage, ein Ort.")
    assert "decision={needsDecision ?" in detail
