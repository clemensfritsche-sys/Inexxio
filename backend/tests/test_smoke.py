"""Smoke tests — verify the app can be imported and key modules are wired up."""
import pytest

from app.core.config import get_settings
from app.routers import (
    admin, article_process, articles, auth, claims, contact, erp, health,
    orders, storage_locations,
)


def test_settings_loads():
    s = get_settings()
    assert s.app_name


def test_routers_importable():
    assert hasattr(admin, "router")
    assert hasattr(articles, "router")
    assert hasattr(article_process, "router")
    assert hasattr(orders, "router")
    assert hasattr(storage_locations, "router")
    assert hasattr(claims, "router")
    assert hasattr(auth, "router")
    assert hasattr(contact, "router")
    assert hasattr(erp, "router")
    assert hasattr(health, "router")


def test_models_exposed_from_package():
    """Models are re-exported from the package regardless of their file."""
    from app.models import (
        Article, ArticleProcessStep, AuditLog, CompanySettings, Notification,
        Order, PurchaseOrder, StorageLocation, UserProfile,
    )

    assert UserProfile.__tablename__ == "user_profiles"
    assert Article.__tablename__ == "articles"
    assert ArticleProcessStep.__tablename__ == "article_process_steps"
    assert Order.__tablename__ == "orders"
    assert PurchaseOrder.__tablename__ == "purchase_orders"
    assert StorageLocation.__tablename__ == "storage_locations"
    assert AuditLog.__tablename__ == "audit_log"
    assert Notification.__tablename__ == "notifications"
    assert CompanySettings.__tablename__ == "company_settings"


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
    assert objects.StorageLocation.object_id in objects._OBJECT_ID_COLUMNS
    # Reklamationen sind eigenständige Objekte mit eigener Nummer (RMA-Nr.)
    assert objects.Claim.object_id in objects._OBJECT_ID_COLUMNS
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
    """Lieferant offeriert/bestätigt, Besteller gibt frei/nimmt Ware an – getrennt."""
    from app.models import PurchaseOrder, UserProfile
    from app.services.purchase import _transition_allowed

    staff = UserProfile(role="employee", id=1)
    supplier = UserProfile(role="supplier", id=2)
    po = PurchaseOrder(order_id=1, article_id=1, quantity=1, mode="supplier", supplier_id=2)

    # Lieferant offeriert, Besteller bestellt/lehnt ab/nimmt Ware an
    assert _transition_allowed(po, "quoted", supplier) is True
    assert _transition_allowed(po, "quoted", staff) is False
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


def test_process_step_requires_consistent_mode():
    """Lieferant-Modus braucht supplier_id, Webshop-Modus braucht URL."""
    import pytest

    from app.schemas.article_process_step import ArticleProcessStepCreate

    ok = ArticleProcessStepCreate(mode="supplier", supplier_id=42)
    assert ok.supplier_id == 42
    ok2 = ArticleProcessStepCreate(mode="webshop", webshop_url="https://shop.example/x")
    assert ok2.webshop_url == "https://shop.example/x"
    with pytest.raises(ValueError):
        ArticleProcessStepCreate(mode="supplier")
    with pytest.raises(ValueError):
        ArticleProcessStepCreate(mode="webshop")


def test_process_step_types_and_optional_config():
    """Datenerfassung/Bewegung brauchen keinen Lieferanten; Prüfumfang default 100 %."""
    import pytest

    from app.schemas.article_process_step import ALLOWED_STEP_TYPES, ArticleProcessStepCreate

    assert set(ALLOWED_STEP_TYPES) == {"purchase", "inspection", "movement", "resource", "sale"}
    # «serialization» ist kein eigener Schritt mehr (Instanzen entstehen bei Freigabe)
    with pytest.raises(ValueError):
        ArticleProcessStepCreate(step_type="serialization")
    insp = ArticleProcessStepCreate(step_type="inspection")
    assert insp.sample_percent == 100                 # Default: ganze Menge
    insp2 = ArticleProcessStepCreate(step_type="inspection", sample_percent=10)
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


def test_movement_step_target_config():
    """Bewegung: Zieltyp wird validiert; ohne Typ kein festes Zielobjekt."""
    import pytest

    from app.schemas.article_process_step import ArticleProcessStepCreate

    # Ohne Vorgabe (Lagerist entscheidet)
    free = ArticleProcessStepCreate(step_type="movement")
    assert free.target_location_type is None and free.target_location_id is None

    # Festes Ziel
    fixed = ArticleProcessStepCreate(step_type="movement", target_location_type="lagerplatz", target_location_id=100_000_500)
    assert fixed.target_location_type == "lagerplatz"
    assert fixed.target_location_id == 100_000_500

    # Zielobjekt ohne Typ → wird verworfen
    dangling = ArticleProcessStepCreate(step_type="movement", target_location_id=100_000_500)
    assert dangling.target_location_id is None

    with pytest.raises(ValueError):
        ArticleProcessStepCreate(step_type="movement", target_location_type="unsinn")


def test_movement_target_validates_location_type():
    """Ein Zielstandort muss lagerplatz | user | instance sein."""
    import pytest

    from app.schemas.movement import LOCATION_TYPES, MovementTarget

    assert set(LOCATION_TYPES) == {"lagerplatz", "user", "instance"}
    ok = MovementTarget(instance_id=100_000_010, location_type="lagerplatz", location_id=100_000_002)
    assert ok.location_type == "lagerplatz"
    with pytest.raises(ValueError):
        MovementTarget(instance_id=1, location_type="strasse", location_id=2)


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


def test_article_names_catalog_normalized():
    """Artikelnamen-Katalog: getrimmt, eindeutig, leere verworfen."""
    from app.schemas.admin import CompanySettingsUpdate

    upd = CompanySettingsUpdate(article_names=["  Welle  ", "Welle", "", "Bolzen"])
    assert upd.article_names == ["Welle", "Bolzen"]


def test_storage_location_has_note():
    """Lagerplatz trägt eine optionale Bemerkung (Spalte bleibt, UI entfernt)."""
    from app.models import StorageLocation
    from app.schemas.storage_location import StorageLocationCreate

    assert hasattr(StorageLocation, "note")
    assert "note" in StorageLocationCreate.model_fields


def test_order_step_info_carries_completion():
    """Stepper-Schritt trägt Abschluss-Info (wer/wann) für den Hover-Tooltip."""
    from app.schemas.order import OrderStepInfo

    assert "completed_by" in OrderStepInfo.model_fields
    assert "completed_at" in OrderStepInfo.model_fields


def test_object_reference_schema():
    """Generischer Verweis (Lagerplatz-Verwendung): Typ, Objektnummer, Label, Zeit."""
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

    assert hasattr(PurchaseOrder, "receiving_location_id")
    assert "receiving_location_id" in PurchaseEmbed.model_fields


def test_storage_location_references_callable():
    """Lagerplatz hat einen Verwendungsnachweis (lagernde Instanzen + Artikel-Referenzen)."""
    from app.services import references

    assert callable(references.storage_location_references)


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


def test_resource_fifo_consumer_whole_and_split():
    """FIFO-Verbraucher: ganze Instanz umlagern vs. Charge teilentnehmen."""
    from app.services.resource import _Fifo, available_qty

    class C:
        def __init__(self, q): self.quantity = q

    a, b = C(1), C(5)
    assert available_qty([a, b]) == 6
    f = _Fifo([a, b])
    assert f.take(3) == (a, 1, True)        # Einzelteil ganz verbraucht
    cand, take, whole = f.take(2)           # Charge teilentnehmen
    assert cand is b and take == 2 and whole is False
    b.quantity -= 2                          # Aufrufer reduziert die Charge
    cand, take, whole = f.take(3)           # Restcharge (3) ganz
    assert cand is b and take == 3 and whole is True


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


def test_claim_is_standalone_object_with_number():
    """Reklamation ist ein eigenständiges Objekt mit eigener Nummer (RMA-Nr.)."""
    from app.models import Claim

    assert Claim.__tablename__ == "claims"
    assert hasattr(Claim, "object_id")
    # Bezug auf genau eine Instanz; Artikel/Auftrag werden denormalisiert geführt
    for f in ("instance_object_id", "article_object_id", "order_object_id",
              "direction", "reason", "resolution", "source"):
        assert hasattr(Claim, f)


def test_claim_schema_validates_enums():
    """Reklamation: Richtung/Grund/Status/Lösung werden gegen Whitelist geprüft."""
    import pytest

    from app.schemas.claim import ClaimCreate, ClaimUpdate

    ok = ClaimCreate(instance_object_id=100_000_010, direction="supplier",
                     reason="damage", title="  kaputt  ")
    assert ok.direction == "supplier" and ok.reason == "damage"
    assert ok.title == "kaputt"   # getrimmt

    assert ClaimUpdate(status="accepted").status == "accepted"
    assert ClaimUpdate(resolution="replace").resolution == "replace"
    with pytest.raises(ValueError):
        ClaimCreate(instance_object_id=1, direction="unsinn")
    with pytest.raises(ValueError):
        ClaimUpdate(status="erledigt")    # kein gültiger Status
    with pytest.raises(ValueError):
        ClaimUpdate(resolution="zauberei")
    with pytest.raises(ValueError):
        ClaimCreate(instance_object_id=1, quantity=0)   # Menge > 0


def test_claim_locks_after_terminal_status():
    """Abgeschlossene/abgelehnte Reklamationen sind inhaltlich gesperrt."""
    import pytest

    from app.services.claims import ensure_claim_mutable

    # Offen/angenommen: Inhalte änderbar
    ensure_claim_mutable("open", {"description": "x", "resolution": "rework"})
    ensure_claim_mutable("accepted", {"resolution_note": "ok"})
    # Terminal: nur Status/is_active
    ensure_claim_mutable("closed", {"status": "open"})
    ensure_claim_mutable("rejected", {"is_active": False})
    with pytest.raises(Exception):
        ensure_claim_mutable("closed", {"description": "neu"})
    with pytest.raises(Exception):
        ensure_claim_mutable("rejected", {"resolution": "credit"})


def test_failed_inspection_triggers_claim():
    """Die Datenerfassung eröffnet bei Nichtbestehen automatisch eine Reklamation."""
    from app.services import claims, inspection

    assert callable(claims.auto_claim_from_inspection)
    # Der Auto-Trigger ist in der Datenerfassung verdrahtet
    assert inspection.auto_claim_from_inspection is claims.auto_claim_from_inspection


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
    assert set(objects._TYPE_MODELS) == {
        "user", "article", "order", "instance", "storage_location", "claim"}
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
    from app.models import Article, Order, StorageLocation

    for f in ("consume_parents", "article_impact", "deactivate_article",
              "cancel_order_effects", "storage_location_in_use",
              "duplicate_article", "duplicate_order", "duplicate_storage_location",
              "article_reactivation_blocker"):
        assert hasattr(deactivation, f)
    # replaced_by_id auf allen drei Datensatztypen
    for m in (Article, Order, StorageLocation):
        assert hasattr(m, "replaced_by_id")
    # orders_mode-Validierung
    assert DeactivateRequest().orders_mode == "phase_out"
    assert DeactivateRequest(orders_mode="cancel").orders_mode == "cancel"
    with _pytest.raises(Exception):
        DeactivateRequest(orders_mode="bogus")


def test_purchase_is_commercial_only_and_movements_planned():
    """Modul-Trennung: Purchase ist rein kaufmännisch (kein Standortwechsel mehr);
    Pflicht-Bewegungen rund um die Beschaffung werden korrekt geplant."""
    from app.services import purchase
    from app.services.process_steps import _plan

    # Purchase verschiebt keine Instanzen mehr – die Alt-Helfer sind entfernt
    assert not hasattr(purchase, "_relocate_to_receiving")
    assert not hasattr(purchase, "_resolve_received_location")

    P = ("purchase", "supplier")
    # Beschaffung als erster Schritt → nur Wareneingang danach (kein Versand)
    assert _plan([P]) == ["purchase", "wareneingang"]
    # Beschaffung mitten im Prozess (Lohnveredelung) → Versand DAVOR + Wareneingang DANACH
    assert _plan([("resource", None), P, ("inspection", None)]) == \
        ["resource", "versand", "purchase", "wareneingang", "inspection"]
    # Aufeinanderfolgende Beschaffungen: keine doppelte Bewegung dazwischen
    assert _plan([P, P]) == ["purchase", "wareneingang", "purchase", "wareneingang"]
    # Ohne Beschaffung keine Pflicht-Bewegung
    assert _plan([("resource", None), ("inspection", None)]) == ["resource", "inspection"]
    # Webshop-Beschaffung bekommt keinen Versand (kein Lieferant zum Hinsenden)
    assert _plan([("resource", None), ("purchase", "webshop")]) == \
        ["resource", "purchase", "wareneingang"]


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
    # Artikel + Menge (produce bzw. FIFO ab Lager)
    assert OrderCreate(article_id=100_000_001, quantity=5).quantity == 5
    with pytest.raises(ValueError):
        OrderCreate()                                  # weder Artikel/Menge noch Instanzen
    # Vorhandene Instanzen (chosen): mindestens eine, NICHT zusammen mit einem Artikel
    assert OrderCreate(instance_object_ids=[100_000_010]).instance_object_ids == [100_000_010]
    with pytest.raises(ValueError):
        OrderCreate(article_id=100_000_001, quantity=1, instance_object_ids=[100_000_010])
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

    assert set(ev.STEP_TYPES) == {"purchase", "resource", "inspection", "movement", "sale"}
    assert ev.RESOURCE_TYPES == ("resource",)   # consume/tool-Aliase entfernt
    # Polarität ist deklariert, nicht abgeleitet:
    assert ev.polarity("purchase") == ev.INCREASE
    assert ev.polarity("resource") == ev.INCREASE
    assert ev.polarity("sale") == ev.DECREASE
    assert ev.polarity("movement") == ev.MOVE
    assert ev.polarity("inspection") == ev.NEUTRAL
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
    assert set(STEP_LABELS) == {"purchase", "resource", "inspection", "movement", "sale"}
    assert STEP_LABELS["resource"] == "Ressource"


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


def test_claim_exposes_quality_and_disposition():
    """Reklamation denormalisiert beide Instanz-Achsen statt des alten qc_status."""
    from app.schemas.claim import ClaimResponse

    assert "instance_quality" in ClaimResponse.model_fields
    assert "instance_disposition" in ClaimResponse.model_fields
    assert "instance_qc_status" not in ClaimResponse.model_fields
