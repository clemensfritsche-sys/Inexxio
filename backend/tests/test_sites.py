"""Mehrstandort/Mehr-Gesellschaften – die Regeln, die nicht auseinanderlaufen dürfen.

EIN gleichrangiger Datensatztyp «Unternehmen» (``company_settings``, Feed ``organization``).
Jede Zeile ist eine vollständige juristische Einheit; die Rolle «Betreiber der Website» wird
**abgeleitet** (ältestes Unternehmen), nicht markiert. Diese Tests sind DB-frei (Quellcode-/
Schema-Inspektion) – die CI hat kein Postgres; das Laufzeitverhalten prüfe ich separat gegen
echtes Postgres.
"""

import ast
import inspect
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _source(rel: str) -> str:
    return (APP / rel).read_text(encoding="utf-8")


def _code(fn) -> str:
    """Der **ausgeführte** Rumpf einer Funktion – ohne Docstring (der erklärt gerade, was
    der Code NICHT tut)."""
    tree = ast.parse(inspect.getsource(fn))
    node = tree.body[0]
    if ast.get_docstring(node):
        node.body = node.body[1:]
    return ast.unparse(node)


# ─── Die Auflösung ist EINE Stelle ───────────────────────────────────────────────

def test_nobody_resolves_the_company_by_hand_anymore():
    """Kein Modul darf «die Firma» noch selbst zusammensuchen.

    ``CompanySettings.id == 1`` (der Betreiber ist über das Alter definiert, nicht über
    einen Schlüsselwert) und ``query(CompanySettings).first()`` (willkürliche Zeile) sind
    beide unbrauchbar geworden. Erlaubt sind nur ``services/sites.py`` (dort steht die
    Regel) und ``services/locations.py`` (Batch-Labels über die Objektnummer)."""
    allowed = {"services/sites.py", "services/locations.py"}
    offenders = []
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP).as_posix()
        if rel in allowed:
            continue
        src = path.read_text(encoding="utf-8")
        code = "\n".join(
            line.split("#")[0] for line in src.splitlines() if not line.strip().startswith("#")
        )
        if "CompanySettings.id == 1" in code:
            offenders.append(f"{rel}: CompanySettings.id == 1")
        if "query(CompanySettings).first()" in code.replace(" ", ""):
            offenders.append(f"{rel}: query(CompanySettings).first()")
    assert not offenders, (
        "Diese Stellen wählen ein Unternehmen willkürlich statt über services/sites.py:\n  "
        + "\n  ".join(offenders)
    )


def test_operator_is_chosen_with_an_age_fallback():
    """Der Betreiber ist **wählbar** (``is_operator``), fällt aber tolerant auf das
    **älteste** Unternehmen zurück, falls (noch) keine Zeile markiert ist.

    Das frühere ``is_primary`` stellte eine Zeile über die anderen (Kaste) und war die
    Ursache eines Deploy-Ausfalls; es ist aus dem Modell entfernt. ``is_operator`` bedeutet
    NUR «vertritt die Website» – editierbar, genau eine. Der Alters-Fallback stellt sicher,
    dass eine ausstehende Migration nie zu «kein Betreiber» führt."""
    from app.services import sites
    from app.models import CompanySettings

    op_code = _code(sites.find_operator)
    assert "is_operator" in op_code, "find_operator liest die gewählte Gesellschaft"
    assert "order_by" in op_code and ".first()" in op_code, "…mit Alters-Fallback"
    # is_primary ist raus (Modell UND – nach Migration 091 – DB); is_operator ist gemappt.
    cols = CompanySettings.__table__.columns.keys()
    assert "is_operator" in cols and "is_primary" not in cols


def test_operator_is_editable_and_exactly_one():
    """Den Betreiber setzen nimmt ihn allen anderen ab – genau EINE trägt den Titel.

    Doppelt abgesichert: ``set_operator`` löscht die übrigen explizit UND der partielle
    Unique-Index (Migration 091 + Lifespan-Netz) liesse zwei ``true`` gar nicht zu."""
    from app.services import sites

    code = _code(sites.set_operator)
    assert "id != company.id" in code, "die übrigen Gesellschaften werden angefasst"
    assert "is_operator" in code and "False" in code, "…und entmarkiert"
    from app.main import _COMPANY_DATA_FIXES
    joined = " ".join(_COMPANY_DATA_FIXES)
    assert "uq_company_settings_operator" in joined and "WHERE is_operator" in joined


def test_currency_is_a_per_company_field_derived_from_country():
    """Die Funktionswährung hängt an JEDER Gesellschaft (auto aus dem Land, editierbar) –
    Grundlage für «ein Preis, überall in Landeswährung»."""
    from app.services.sites import ENTITY_FIELDS, currency_for_country

    assert "currency" in ENTITY_FIELDS
    assert currency_for_country("USA") == "USD"
    assert currency_for_country("Schweiz") == "CHF"
    assert currency_for_country("Deutschland") == "EUR"
    assert currency_for_country(None) == "CHF"      # unbekannt → Heimatwährung


def test_read_only_callers_never_commit_a_foreign_transaction():
    """Preis-Pipeline, Shop-Konfig, Provider-Wahl und PDF-Briefkopf lesen den Betreiber –
    sie dürfen ihn nicht anlegen, weil sie mitten in einer fremden Transaktion laufen.

    (``find_primary`` ist der rückwärts-kompatible Alias von ``find_operator``.)"""
    for rel in ("services/pricing.py", "services/selling.py", "services/logistics.py",
                "services/payments/__init__.py", "routers/shop.py", "routers/documents.py"):
        src = _source(rel)
        # Lese-Form: entweder direkt der Betreiber (find_operator/-primary) ODER die abgeleitete
        # fakturierende Gesellschaft (``sale.seller_company_for_order`` – ebenfalls rein lesend,
        # fällt intern auf find_operator zurück; ADR 006, Absender/Beleg des Sellers).
        assert ("import find_primary" in src or "import find_operator" in src
                or "seller_company_for_order" in src), \
            f"{rel} muss eine Lese-Form nutzen"
        assert "import primary" not in src and "import operator" not in src, \
            f"{rel} darf den Betreiber nicht anlegen"


# ─── EIN gleichrangiger Typ: jede Gesellschaft ist vollständig ───────────────────

def test_every_company_carries_its_own_legal_identity():
    """Kern der Kehrtwende: die US-Gesellschaft hat ihre EIGENE Rechtsidentität.

    Rechtsidentität/Bank/MWST müssen an JEDEM Datensatz editierbar sein
    (``sites.ENTITY_FIELDS``) – das frühere «nur der Hauptsitz trägt Identität» ist genau
    verkehrt und entfernt."""
    from app.services.sites import ENTITY_FIELDS

    must_be_per_company = (
        "uid_number", "vat_number", "trade_register_nr", "share_capital", "legal_form",
        "bank", "bic_swift", "vat_method", "vat_period",
    )
    missing = [f for f in must_be_per_company if f not in ENTITY_FIELDS]
    assert not missing, f"Diese Entitäts-Felder fehlen im per-Gesellschaft-Feldsatz: {missing}"


def test_platform_config_is_never_editable_per_company():
    """Die Plattform-Konfiguration (Stripe, Shop, Rechtstexte) gilt der EINEN Website, nicht
    je Gesellschaft. Sie darf über den per-Gesellschaft-Pfad NICHT setzbar sein – sonst
    trüge jede Aussenstelle einen eigenen Stripe-Key (dieselbe Angabe an n Stellen).

    ``apply_update`` schreibt nur ``ENTITY_FIELDS`` (+ Bank-Chiffren); Plattform-Felder
    werden ignoriert."""
    from app.services.sites import ENTITY_FIELDS, PLATFORM_FIELDS
    from app.services import sites

    leaked = [f for f in PLATFORM_FIELDS if f in ENTITY_FIELDS]
    assert not leaked, f"Plattform-Felder dürfen nicht je Gesellschaft editierbar sein: {leaked}"

    # apply_update wählt strikt über ENTITY_FIELDS (+ iban/qr_iban) – kein setattr über
    # beliebige Keys, das Plattform-Felder durchliesse.
    apply_code = _code(sites._apply_entity_fields)
    assert "ENTITY_FIELDS" in apply_code
    assert "stripe" not in apply_code and "legal_documents" not in apply_code


def test_creating_a_company_is_full_and_equal():
    """Anlegen setzt keinen Rang (kein ``is_primary=...``) und trägt volle Entitäts-Felder."""
    from app.services import sites

    create_code = _code(sites.create)
    assert "is_primary" not in create_code, "Anlegen darf keine Rang-Markierung setzen"
    assert "_apply_entity_fields" in create_code, "Anlegen trägt den vollen Entitäts-Feldsatz"


def test_response_exposes_derived_role_not_a_stored_flag():
    """Die Antwort trägt ``is_operator`` (abgeleitet) + ``has_address`` – aber kein
    gespeichertes Rang-Flag."""
    from app.schemas.admin import CompanySettingsResponse

    fields = CompanySettingsResponse.model_fields
    assert "is_operator" in fields and "has_address" in fields
    assert "is_primary" not in fields, "kein gespeichertes Rang-Flag in der Antwort"


# ─── Der Kern: das Ziel einer Bewegung ist SEIN Standort ─────────────────────────

def test_movement_target_resolves_the_addressed_company_not_the_operator():
    """``logistics.target_address`` löst das adressierte Unternehmen über seine Objektnummer
    auf – nähme es den Betreiber, bekäme JEDES Ziel dessen Adresse und ein Transport
    Werk A → Werk B ginge still als «innerbetrieblich» durch statt als Versand."""
    from app.services import logistics

    src = inspect.getsource(logistics.target_address)
    assert "by_object_id(db, lid)" in src


def test_company_holder_label_reads_the_addressed_company():
    """Das Label eines ``company``-Halters ist der Name GENAU dieses Unternehmens (über die
    Objektnummer)."""
    from app.services import locations

    for fn in (locations.location_label, locations.location_labels):
        assert "object_id" in inspect.getsource(fn)


# ─── Deploy-Sicherheit: eine neue Spalte darf die Website nicht abschalten ────────

def test_every_company_settings_column_is_in_the_lifespan_safety_net():
    """Jede nachträglich ergänzte Spalte von ``company_settings`` MUSS im Lifespan-
    Sicherheitsnetz stehen (``main._COLUMN_SAFETY_NET``).

    ``start.sh`` startet uvicorn auch dann, wenn Alembic scheitert – das Netz ist der
    vorgesehene zweite Weg. Kennt das Modell eine Spalte, die die DB nicht hat, scheitert
    JEDE Abfrage auf der Tabelle; und ``company_settings`` liest der ganze Instanz-Feed
    (Standort-Label) sowie die öffentlichen Endpunkte (Impressum, Shop). Eine fehlende
    Spalte hier nimmt ERP UND Website mit – genau das ist beim ersten Mehrstandort-Deploy
    passiert. Die Erwartung wird aus dem MODELL abgeleitet, nicht aus einer Liste."""
    import re
    from app.main import _COLUMN_SAFETY_NET, _DROP_COLUMN_SAFETY_NET
    from app.models import CompanySettings

    initial = (APP.parent / "alembic/versions/001_initial_schema.py").read_text(encoding="utf-8")
    block = initial.split("'company_settings'", 1)[1].split("op.create_table", 1)[0]
    from_initial = set(re.findall(r"sa\.Column\(\s*'(\w+)'", block))
    assert "company_name" in from_initial, "Initial-Schema-Block nicht erkannt"

    net = {c for t, c, _ in _COLUMN_SAFETY_NET if t == "company_settings"}
    dropped = {c for t, c in _DROP_COLUMN_SAFETY_NET if t == "company_settings"}
    model = set(CompanySettings.__table__.columns.keys())

    missing = sorted(model - from_initial - net - dropped)
    assert not missing, (
        "Diese Spalten kennt das Modell, aber das Lifespan-Sicherheitsnetz nicht – "
        f"scheitert Alembic, sind ERP UND Website tot: {missing}\n"
        "→ in main._COLUMN_SAFETY_NET eintragen."
    )


def test_migrations_090_and_091_are_repeatable():
    """Repariert das Lifespan-Netz das Schema, versucht Alembic die Migration beim nächsten
    Deploy erneut – sie muss also wiederholbar sein, sonst bliebe Alembic hängen und
    blockierte jede künftige Migration."""
    for name in ("090_multi_site.py", "091_companies_operator_currency.py"):
        migration = (APP.parent / "alembic/versions" / name).read_text(encoding="utf-8")
        tree = ast.parse(migration)
        code = ast.unparse(next(n for n in tree.body if getattr(n, "name", None) == "upgrade"))
        assert "CREATE UNIQUE INDEX IF NOT EXISTS" in code, name
        # additive Spalten nur, wenn nicht vorhanden; Drops nur IF EXISTS
        assert "get_columns('company_settings')" in code or "IF EXISTS" in code, name


def test_is_primary_is_dropped_everywhere_not_re_added():
    """``is_primary`` ist endgültig weg: NICHT mehr im ADD-Netz (das es sonst wieder
    anlegen würde und Migration 091 rückgängig machte), sondern im DROP-Netz."""
    from app.main import _COLUMN_SAFETY_NET, _DROP_COLUMN_SAFETY_NET

    add = {(t, c) for t, c, _ in _COLUMN_SAFETY_NET}
    drop = set(_DROP_COLUMN_SAFETY_NET)
    assert ("company_settings", "is_primary") not in add, "is_primary darf nicht wieder ergänzt werden"
    assert ("company_settings", "is_primary") in drop, "is_primary gehört ins Drop-Netz"
    assert ("company_settings", "is_operator", "BOOLEAN NOT NULL DEFAULT false") in _COLUMN_SAFETY_NET


def test_no_syntax_errors_in_touched_modules():
    """Billiger Rundum-Schutz: alle angefassten Module parsen."""
    for rel in ("services/sites.py", "services/locations.py", "services/logistics.py",
                "services/orders.py", "services/admin.py", "services/pricing.py",
                "services/selling.py", "routers/admin.py", "schemas/admin.py",
                "models/admin.py"):
        ast.parse(_source(rel))
