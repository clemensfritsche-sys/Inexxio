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


def test_every_company_carries_its_own_legal_identity():
    """Kern der Kehrtwende: die US-Gesellschaft hat ihre EIGENE Rechtsidentität.

    Rechtsidentität, Anschrift, Währung und Bankverbindung müssen an JEDEM Datensatz
    editierbar sein (``sites.ENTITY_FIELDS``) – das frühere «nur der Hauptsitz trägt
    Identität» ist genau verkehrt und entfernt.

    Der Feldsatz ist seit Runde 21 **klein** (Testnotizen #307/#313/#314/#317–#321) – geprüft
    wird darum beides: dass die tragenden Angaben da sind UND dass die gestrichenen nicht
    zurückkommen. Ein Feld, das niemand auf einem Beleg, im Impressum oder in einer Regel
    nennt, ist kein Stammdatum, sondern Arbeit für jede weitere Gesellschaft."""
    from app.services.sites import ENTITY_FIELDS

    must_be_per_company = ("uid_number", "vat_number", "legal_form", "currency", "country")
    missing = [f for f in must_be_per_company if f not in ENTITY_FIELDS]
    assert not missing, f"Diese Entitäts-Felder fehlen im per-Gesellschaft-Feldsatz: {missing}"

    # Die IBAN ist Entität, läuft aber über die verschlüsselte Spalte (Sonderzweig in
    # ``_apply_entity_fields``) – sie steht deshalb bewusst NICHT in ENTITY_FIELDS.
    from app.services import sites
    assert "'iban'" in _code(sites._apply_entity_fields)

    dropped = (
        "trade_register_nr", "trade_register_canton", "share_capital",   # sagt die UID
        "qr_iban", "bank", "bic_swift",                                  # sagt die IBAN
        "vat_method", "vat_period",                                      # Buchhaltung (Phase 3)
        "default_payment_days", "default_skonto_pct", "default_skonto_days",  # Offerte
        "oss_active", "oss_reg_number", "vies_active",                   # nie ausgewertet
        "website",                                                       # abgeleitet (#309)
    )
    back = [f for f in dropped if f in ENTITY_FIELDS]
    assert not back, f"Gestrichene Felder sind zurück im Feldsatz: {back}"


def test_the_website_address_is_derived_not_typed():
    """Testnotiz #309: unter welcher Adresse die Website läuft, weiss das **Deployment** –
    kein Eingabefeld daneben, das beim ersten Domain-Wechsel still falsch wird.

    EINE Quelle (``sites.website_url`` ← ``FRONTEND_BASE_URL``); Impressum, Beleg-Briefkopf
    und die read-only Anzeige am Datensatz lesen alle sie."""
    from app.schemas.admin import CompanySettingsUpdate
    from app.services.sites import ENTITY_FIELDS, website_url

    assert "website" not in ENTITY_FIELDS
    assert "website" not in CompanySettingsUpdate.model_fields, \
        "Die Website-Adresse darf nicht wieder einsendbar werden"
    assert website_url() and not website_url().endswith("/")
    # Der zweite Leser (Beleg-Briefkopf) ist mit dem Dokumentmodul entfallen; die Regel
    # gilt unverändert für den, der geblieben ist.
    assert "website_url" in _source("routers/admin.py"), \
        "routers/admin.py muss die eine Ableitung lesen"


def test_a_company_never_loses_its_name():
    """Testnotiz #301: der Name ist Pflicht – und zwar hart, nicht als Formular-Kosmetik.

    Er ist zugleich das **Halter-Label** (``locations.location_label`` gibt für einen
    ``company``-Halter genau dieses Feld zurück): eine namenlose Gesellschaft liesse jede
    Standort-Anzeige leer, die auf sie zeigt. Anlegen prüfte das schon immer; Ändern nicht."""
    from app.services import sites

    for fn in (sites._new, sites.apply_update):
        code = _code(fn)
        assert "company_name" in code and "400" in code, \
            f"{fn.__name__} muss einen leeren Namen ablehnen"


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

    # apply_update wählt strikt über ENTITY_FIELDS (+ iban) – kein setattr über
    # beliebige Keys, das Plattform-Felder durchliesse.
    apply_code = _code(sites._apply_entity_fields)
    assert "ENTITY_FIELDS" in apply_code
    assert "stripe" not in apply_code and "legal_documents" not in apply_code


def test_creating_a_company_is_full_and_equal():
    """Anlegen setzt keinen Rang (kein ``is_primary=...``) und trägt volle Entitäts-Felder."""
    from app.services import sites

    create_code = _code(sites._new)
    assert "is_primary" not in create_code, "Anlegen darf keine Rang-Markierung setzen"
    assert "_apply_entity_fields" in create_code, "Anlegen trägt den vollen Entitäts-Feldsatz"


def test_response_exposes_derived_role_not_a_stored_flag():
    """Die Antwort trägt ``is_operator`` (abgeleitet) + ``has_address`` – aber kein
    gespeichertes Rang-Flag."""
    from app.schemas.admin import CompanySettingsResponse

    fields = CompanySettingsResponse.model_fields
    assert "is_operator" in fields and "has_address" in fields
    assert "is_primary" not in fields, "kein gespeichertes Rang-Flag in der Antwort"


def test_our_own_bank_account_is_not_masked():
    """►►► **Die eigene IBAN steht ausgeschrieben da** (Testnotiz #870). ◄◄◄

    *«Dieser Wert war nicht ausgefüllt, und trotzdem hatte das ERP eine Bankverbindung
    anzugeben. Das System darf nicht auf einmal aus dem Nichts Bankverbindungen
    zaubern.»* – Es zauberte nichts: die IBAN war gespeichert, sie kam nur **maskiert**
    zurück («CH12 **** **** **** 8901») und stand im Browser als **Platzhalter**, also
    genau dort, wo eine Oberfläche sagt «hier ist nichts». Ein Unternehmen mit
    Bankverbindung sah damit aus wie eines ohne – und der QR-Einzahlungsschein daneben
    wie erfunden.

    **Sie ist kein Geheimnis**: sie steht auf jeder Rechnung, die wir stellen, und im
    QR-Code, den wir dem Zahlenden hinlegen – gegenüber denselben Leuten, die sie hier
    sehen. Maskiert wird, was der Empfänger nicht sehen *soll*; hier war es das, was er
    sehen *muss*, um zu prüfen, ob es stimmt.

    Bug-Formen: (a) das maskierte Feld ist zurück; (b) irgendwo wird wieder maskiert;
    (c) der Wert erreicht die Antwort gar nicht (dann bleibt das Feld leer wie zuvor).
    """
    from app.schemas.admin import CompanySettingsResponse
    from app.routers import admin

    fields = CompanySettingsResponse.model_fields
    assert "iban_masked" not in fields, (
        "Die maskierte IBAN ist zurück (a) – dann sieht ein Unternehmen mit "
        "Bankverbindung wieder aus wie eines ohne."
    )
    assert "iban" in fields, "Die Antwort nennt die Bankverbindung gar nicht mehr."
    # **Gelesen wird der CODE, nicht die Prosa**: die Begründung nennt die maskierte
    # Nummer, um zu sagen, warum es sie nicht mehr gibt – ein Wächter, der den Fliesstext
    # mitliest, schlägt an, weil jemand den Fehler *beschreibt*.
    body = _code(admin._company_response)
    assert not hasattr(admin, "_mask_iban") and "****" not in body, (
        "Es wird wieder maskiert (b)."
    )
    assert "resp.iban = company.iban_encrypted" in body, (
        "Die IBAN erreicht die Antwort nicht (c) – das Modell heisst `iban_encrypted`, "
        "das Schema `iban`; ohne die Zuweisung bleibt sie leer, und das Feld sieht "
        "wieder aus wie ein nie ausgefülltes."
    )


# ─── Der Kern: das Ziel einer Bewegung ist SEIN Standort ─────────────────────────

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
    anlegen würde und Migration 091 rückgängig machte) und in keinem Modell. Gedroppt hat
    es Migration 091; das frühere Drop-Netz, das es bei jedem Start erneut versuchte, ist
    entfallen (Cleanup Oktober 2026, B-22) – eine Spalte ohne Mapping stört nichts."""
    from app.main import _COLUMN_SAFETY_NET
    from app.models import CompanySettings

    add = {(t, c) for t, c, _ in _COLUMN_SAFETY_NET}
    assert ("company_settings", "is_primary") not in add, "is_primary darf nicht wieder ergänzt werden"
    assert "is_primary" not in CompanySettings.__table__.columns, "is_primary ist zurück im Modell"
    assert ("company_settings", "is_operator", "BOOLEAN NOT NULL DEFAULT false") in _COLUMN_SAFETY_NET




def test_the_public_settings_name_only_the_maps_key_and_invent_nothing():
    """►►► **Ohne Anmeldung gibt es den Maps-Schlüssel – sonst nichts** (Cleanup Paket 4).

    Der Endpunkt lieferte Anschrift, UID und MWST, die niemand mehr las, und ohne Betreiber
    eine **erfundene** «Inexxio AG» mit info@inexxio.com. Plausible ist entfernt (E5) – sein
    Feld hatte die Antwort ohnehin nie erreicht, das Skript lud darum nie.

    Bug-Formen: (a) ein erfundener Firmenname ist zurück; (b) die Plausible-Domain ist zurück;
    (c) die Antwort trägt wieder Angaben ohne Leser."""
    from app.routers import admin
    from app.services import sites
    code = _code(admin.get_public_settings)
    assert "Inexxio" not in code and "info@" not in code
    assert "plausible" not in code
    assert "google_maps_api_key" in code and "uid_number" not in code and "street" not in code
    assert sites.PLATFORM_FIELDS == ("google_maps_api_key",)


def test_no_analytics_script_and_no_consent_layer():
    """Plausible war die **einzige** optionale Kategorie der Einwilligung – mit ihr gehen
    das Skript, der Cookie-Dialog und die Mess-Haken der Website (E5). Ein Haken, der
    nichts sendet, ist Code ohne Wirkung; eine Einwilligung ohne Gegenstand ist eine Frage,
    auf die keine Antwort etwas ändert."""
    root = APP.parents[1]
    hits = []
    for base in ("frontend/src", "website/src"):
        for p in (root / base).rglob("*"):
            if p.suffix not in {".ts", ".tsx", ".astro", ".mjs"} or "generated" in p.parts:
                continue
            text = p.read_text(encoding="utf-8")
            for needle in ("plausible", "data-track", "cookie-consent", "data-consent"):
                if needle in text.lower():
                    hits.append(f"{p.relative_to(root)}: {needle}")
    assert not hits, hits
