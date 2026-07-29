"""Mehrstandort (Variante A) – die Regeln, die nicht auseinanderlaufen dürfen.

Die Umstellung von «ein Unternehmen» auf «n Standorte» ist nur an EINER Stelle riskant:
überall dort, wo Code sich bisher «die Firma» selbst geholt hat. Solange es eine Zeile
gab, war jede Schreibweise richtig – ab der zweiten entscheidet die Zeilenreihenfolge der
Datenbank, welcher Standort gemeint ist. Genau davor schützen diese Tests.
"""

import ast
import inspect
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _source(rel: str) -> str:
    return (APP / rel).read_text(encoding="utf-8")


def _code(fn) -> str:
    """Der **ausgeführte** Rumpf einer Funktion – ohne Docstring.

    Nötig, weil die Docstrings hier gerade erklären, was der Code NICHT tut («kein
    ``commit``»). Ein Textvergleich über die ganze Quelle würde daran scheitern und den
    Wächter unbrauchbar machen."""
    tree = ast.parse(inspect.getsource(fn))
    node = tree.body[0]
    if ast.get_docstring(node):
        node.body = node.body[1:]
    return ast.unparse(node)


# ─── Die Auflösung ist EINE Stelle ───────────────────────────────────────────────

def test_nobody_resolves_the_company_by_hand_anymore():
    """Kein Modul darf «die Firma» noch selbst zusammensuchen.

    Die beiden Formen, die es früher gab, sind beide unbrauchbar geworden:
      * ``CompanySettings.id == 1``  – der Hauptsitz ist über ``is_primary`` definiert,
        nicht über einen Schlüsselwert;
      * ``query(CompanySettings)…first()`` – eine **willkürliche** Zeile.

    Erlaubt sind nur ``services/sites.py`` selbst (dort steht die Regel) und
    ``locations.py`` (Batch-Labels holen gezielt Standorte über ihre Objektnummer)."""
    allowed = {"services/sites.py", "services/locations.py"}
    offenders = []
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP).as_posix()
        if rel in allowed:
            continue
        src = path.read_text(encoding="utf-8")
        # Kommentare/Docstrings dürfen die Alt-Form nennen (sie erklären ja den Wechsel) –
        # geprüft wird der ausgeführte Code.
        code = "\n".join(
            line.split("#")[0] for line in src.splitlines() if not line.strip().startswith("#")
        )
        if "CompanySettings.id == 1" in code:
            offenders.append(f"{rel}: CompanySettings.id == 1")
        if "query(CompanySettings).first()" in code.replace(" ", ""):
            offenders.append(f"{rel}: query(CompanySettings).first()")
    assert not offenders, (
        "Diese Stellen wählen einen Standort willkürlich statt über services/sites.py:\n  "
        + "\n  ".join(offenders)
    )


def test_sites_module_offers_both_forms_of_the_same_rule():
    """``primary`` (schreibend, legt an) und ``find_primary`` (rein lesend).

    Zwei Formen EINER Regel sind in Ordnung – zwei Regeln wären es nicht. Die Lese-Form
    ist Pflicht in fremden Transaktionen (Preis-Pipeline, Shop-Konfig, PDF): ein ``commit``
    dort würde die halbfertige Arbeit des Aufrufers mit festschreiben."""
    from app.services import sites

    assert callable(sites.primary) and callable(sites.find_primary)
    assert "commit" not in _code(sites.find_primary), "find_primary muss ein reines Lesen bleiben"
    # …und die Schreib-Form baut auf der Lese-Form auf, statt die Regel zu wiederholen.
    assert "find_primary(db)" in inspect.getsource(sites.primary)


def test_read_only_callers_never_commit_a_foreign_transaction():
    """Preis-Pipeline, Shop-Konfig, Provider-Wahl und PDF-Briefkopf lesen den Hauptsitz –
    sie dürfen ihn nicht anlegen, weil sie mitten in einer fremden Transaktion laufen."""
    for rel in ("services/pricing.py", "services/selling.py", "services/logistics.py",
                "services/payments/__init__.py", "routers/shop.py", "routers/documents.py"):
        src = _source(rel)
        assert "import find_primary" in src, f"{rel} muss die Lese-Form nutzen"
        assert "import primary" not in src, f"{rel} darf den Hauptsitz nicht anlegen"


# ─── Standort ≠ Firma ────────────────────────────────────────────────────────────

def test_site_fields_and_update_schema_cannot_drift():
    """Der Spiegel zwischen «was gilt je Standort» (Service) und dem Update-Schema (API).

    Läuft er auseinander, entsteht genau der verbotene Zustand: ein Feld, das die API
    annimmt, das der Service aber verwirft (stille Datenverluste) – oder umgekehrt eine
    Angabe der Rechtsidentität, die an einem Nebenstandort landet."""
    from app.schemas.admin import SiteBase
    from app.services.sites import SITE_FIELDS

    assert set(SiteBase.model_fields) == set(SITE_FIELDS)


def test_a_branch_office_cannot_carry_legal_identity_or_system_config():
    """Rechtsidentität und Systemkonfiguration gehören dem Hauptsitz – an EINER Stelle.

    Stünde die UID an jedem Standort, gäbe es dieselbe Angabe n-mal; genau das verbietet
    «eine Sache, eine Stelle»."""
    from app.services.sites import SITE_FIELDS

    forbidden = (
        "uid_number", "vat_number", "trade_register_nr", "share_capital", "legal_form",
        "iban", "qr_iban", "bank", "website", "stripe_publishable_key", "legal_documents",
        "shop_currencies", "payments_provider", "pricing_zone_factors", "vat_method",
    )
    leaked = [f for f in forbidden if f in SITE_FIELDS]
    assert not leaked, f"Diese Angaben dürfen nicht je Standort existieren: {leaked}"


def test_creating_a_site_never_makes_a_second_primary():
    """Es gibt genau EINEN Hauptsitz – sonst hätte «die Firma» zwei Antworten.

    Erzwungen wird das doppelt: im Code (``is_primary=False`` beim Anlegen) und in der
    Datenbank (partieller Unique-Index, Migration 090)."""
    from app.services import sites

    src = inspect.getsource(sites.create)
    assert "is_primary=False" in src

    migration = (APP.parent / "alembic/versions/090_multi_site.py").read_text(encoding="utf-8")
    assert "UNIQUE INDEX" in migration and "WHERE is_primary" in migration


def test_migration_puts_existing_data_on_the_primary_site_without_rewriting_rows():
    """Der Migrationsplan in einem Satz: die vorhandene Zeile WIRD der Hauptsitz.

    Ihre Objektnummer bleibt gültig, deshalb muss keine einzige Instanz und kein einziger
    Auftrag umgeschrieben werden – der Bestand hängt an der Objektnummer, nicht an ``id``."""
    migration = (APP.parent / "alembic/versions/090_multi_site.py").read_text(encoding="utf-8")
    assert "UPDATE company_settings SET is_primary = true" in migration
    # Nur der ausgeführte Teil zählt – der Modul-Docstring erklärt die Bestandsdaten und
    # darf die Tabellen selbstverständlich beim Namen nennen.
    tree = ast.parse(migration)
    upgrade = next(n for n in tree.body if getattr(n, "name", None) == "upgrade")
    code = ast.unparse(upgrade)
    for table in ("instances", "orders", "purchase_orders", "shipments"):
        assert table not in code, f"Migration 090 darf {table} nicht anfassen"


# ─── Der Kern: das Ziel einer Bewegung ist SEIN Standort ─────────────────────────

def test_movement_target_resolves_the_addressed_site_not_the_head_office():
    """Die eine Stelle, an der Mehrstandort steht und fällt.

    ``logistics.target_address`` beantwortet «welche Anschrift hat dieses Ziel?». Nahm sie
    – wie früher – irgendeine Zeile, bekäme JEDES Standort-Ziel die Adresse des Hauptsitzes.
    Quelle und Ziel sähen für ``classify_movement`` identisch aus, und ein Transport
    Werk A → Werk B ginge still als «innerbetrieblich» durch statt als Versand mit Tarif
    und Label."""
    from app.services import logistics

    src = inspect.getsource(logistics.target_address)
    assert "by_object_id(db, lid)" in src, (
        "target_address muss den adressierten Standort über seine Objektnummer auflösen"
    )


def test_company_holder_label_reads_the_addressed_site():
    """Dasselbe für die Anzeige: das Label eines ``company``-Halters ist der Name GENAU
    dieses Standorts. (War schon immer objektnummern-basiert – hier festgehalten, damit es
    so bleibt.)"""
    from app.services import locations

    for fn in (locations.location_label, locations.location_labels):
        assert "object_id" in inspect.getsource(fn)


def test_no_syntax_errors_in_touched_modules():
    """Billiger Rundum-Schutz: alle angefassten Module parsen."""
    for rel in ("services/sites.py", "services/locations.py", "services/logistics.py",
                "services/orders.py", "services/admin.py", "services/pricing.py",
                "services/selling.py", "routers/admin.py", "schemas/admin.py",
                "models/admin.py"):
        ast.parse(_source(rel))
