"""Wächter gegen **auseinanderlaufende Spiegel** zwischen Backend und Frontend.

Ein paar Aufzählungen existieren zwangsläufig auf beiden Seiten: das Frontend braucht
zu jedem Schritttyp ein **Symbol** und ein Label, und die will man nicht bei jedem
Seitenaufbau nachladen. Diese TypeScript-Unions sind aber **von Hand** gepflegt (nicht
aus dem OpenAPI-Schema generiert) – und damit gab es bisher **keinen** Schutz:

* Ein neuer Schritttyp im Backend fällt im Frontend lautlos auf den Rohwert zurück
  (``STEP_META[t]?.label ?? t`` zeigt dann «resource» statt «Ressource»).
* ``Record<StepType, …>`` erzwingt zwar Vollständigkeit – aber nur über die **veraltete**
  Union. Fehlt der neue Typ dort, meldet TypeScript nichts.
* Ein entfernter Typ (wie seinerzeit ``lagerplatz``) bleibt als toter Zweig stehen.

Statt die Listen zur Laufzeit über einen zusätzlichen Endpunkt zu koppeln (Round-Trip,
Ladezustand, Fehlerfall), prüft dieser Test sie **beim Bauen** gegeneinander. Der
Spiegel bleibt schnell, das Auseinanderlaufen wird unmöglich.

Massgeblich ist immer das Backend.
"""

import pathlib
import re

import pytest

FRONTEND = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"


def _ts_union(path: pathlib.Path, type_name: str) -> set[str]:
    """Die Literale einer TypeScript-Union: ``export type X = 'a' | 'b';`` → {a, b}."""
    src = path.read_text(encoding="utf-8")
    m = re.search(rf"export type {type_name}\s*=\s*([^;]+);", src)
    assert m, f"{type_name} nicht in {path.name} gefunden"
    return set(re.findall(r"'([^']+)'", m.group(1)))


def _ts_record_labels(path: pathlib.Path, const_name: str) -> dict[str, str]:
    """``export const X: Record<…> = { key: { label: 'Text', … }, … }`` → {key: Text}."""
    src = path.read_text(encoding="utf-8")
    m = re.search(rf"export const {const_name}[^=]*=\s*\{{(.*?)\n\}};", src, re.S)
    assert m, f"{const_name} nicht in {path.name} gefunden"
    return dict(re.findall(r"(\w+)\s*:\s*\{[^}]*?label:\s*'([^']*)'", m.group(1)))


@pytest.mark.parametrize("type_name, backend_values, quelle", [
    ("StepType", None, "domain/event_types.REGISTRY"),
    ("LocationType", None, "schemas/movement.LOCATION_TYPES"),
    ("ArticleUnit", None, "schemas/article.ALLOWED_UNITS"),
])
def test_frontend_unions_match_backend(type_name, backend_values, quelle):
    """Die handgepflegten TS-Unions decken sich exakt mit den Backend-Listen."""
    from app.domain import event_types
    from app.schemas.article import ALLOWED_UNITS
    from app.schemas.movement import LOCATION_TYPES

    expected = {
        "StepType": set(event_types.REGISTRY),
        "LocationType": set(LOCATION_TYPES),
        "ArticleUnit": set(ALLOWED_UNITS),
    }[type_name]
    actual = _ts_union(FRONTEND / "types" / "index.ts", type_name)
    assert actual == expected, (
        f"{type_name} (frontend/src/types/index.ts) weicht von {quelle} ab.\n"
        f"  nur im Backend:  {sorted(expected - actual)}\n"
        f"  nur im Frontend: {sorted(actual - expected)}"
    )


def test_step_labels_match_the_registry():
    """Die Schritt-Labels im Frontend sind exakt die der Ereignis-Registry.

    Die Symbole bleiben im Frontend (dort gehören sie hin) – der **Text** kommt aus der
    einen Quelle, sonst heisst derselbe Schritt an zwei Orten verschieden."""
    from app.domain import event_types

    meta = _ts_record_labels(FRONTEND / "lib" / "process.ts", "STEP_META")
    expected = {k: et.label for k, et in event_types.REGISTRY.items()}
    assert meta == expected, (
        "STEP_META (frontend/src/lib/process.ts) weicht von domain/event_types.REGISTRY ab.\n"
        f"  Backend:  {expected}\n"
        f"  Frontend: {meta}"
    )


def test_location_labels_cover_every_type():
    """Zu JEDEM gültigen Standort-Typ gibt es eine Frontend-Beschriftung – sonst zeigt
    die Oberfläche den Rohwert («company» statt «Unternehmen»)."""
    from app.schemas.movement import LOCATION_TYPES

    meta = _ts_record_labels(FRONTEND / "lib" / "process.ts", "LOCATION_META")
    assert set(meta) == set(LOCATION_TYPES), (
        f"LOCATION_META deckt {sorted(meta)} ab, gültig sind {sorted(LOCATION_TYPES)}"
    )


# ─── ERP-First ────────────────────────────────────────────────────────────────────

def test_erp_record_can_edit_everything_the_person_can():
    """**ERP ist Master:** am ERP-Benutzer-Datensatz muss ALLES änderbar sein, was die
    Person in ihrem Konto selbst pflegen kann – plus die Anstellungsdaten.

    Vorher war ``ErpAdminUpdate`` eine schmale Extra-Liste (Rolle, Abteilung, Titel,
    Eintritt, Pensum). Name, Adresse, Firmenangaben und Bankverbindung konnte das ERP
    nur ANZEIGEN; ändern konnte sie allein die Person im Konto – die Wahrheit lag also
    ausserhalb des ERP, genau verkehrt herum."""
    from app.schemas.admin import ErpAdminUpdate, UserProfileUpdate

    self_service = set(UserProfileUpdate.model_fields)
    erp = set(ErpAdminUpdate.model_fields)
    assert self_service <= erp, (
        "Das ERP kann diese Felder NICHT ändern, die Person aber schon: "
        f"{sorted(self_service - erp)}"
    )
    # … und die Anstellungsdaten bleiben dem ERP vorbehalten (nicht selbst änderbar).
    assert {"role", "department", "job_title", "employment_start_date", "weekly_hours"} <= erp - self_service


def test_both_profile_write_paths_share_one_implementation():
    """Konto-Selbstbedienung und ERP-Datensatz beschreiben denselben Datensatz – und
    jetzt über denselben Pfad (inkl. Audit-Log). Vorher protokollierte nur das ERP:
    eine im Konto geänderte IBAN hinterliess keine Spur."""
    import inspect

    from app.routers import auth as auth_router, erp as erp_router
    from app.services import people

    for src in (inspect.getsource(auth_router.update_me),
                inspect.getsource(erp_router.update_erp_record)):
        assert "apply_profile_update" in src
    assert "log_audit" in inspect.getsource(people.apply_profile_update)


def test_record_status_is_derived_in_exactly_one_place():
    """**Feed und Detailfenster zeigen denselben Zustand – weil sie dieselbe Funktion lesen.**

    Ein ERP-Datensatz zeigt überall dasselbe: Name · Objektnummer · Status. Für den *Namen*
    gibt es die eine Ableitung längst (``lib/record-name.ts``); für den *Zustand* gab es sie
    nicht – der Feed baute die Badge in einer fünfarmigen Fallunterscheidung selbst, jedes
    Detailfenster noch einmal. Genau so sind sie auseinandergelaufen (Testnotiz #379): der
    Feed zeigte an einem Unternehmen hart verdrahtet «Unternehmen» (die Datensatzart!),
    während das Detail längst «Freigegeben»/«Inaktiv» sagte.

    Der Wächter prüft die **Struktur**, nicht den Text: ein Status-Konfigurations-Literal
    (``label`` + ``color``/``bg``) darf nur unter ``lib/`` stehen. Wer im Feed oder in einem
    Detailfenster wieder eine eigene Badge baut, fällt hier auf."""
    literal = re.compile(r"label:\s*['\"][^'\"]*['\"]\s*,\s*(color|bg|\.\.\.TONE)")
    surfaces = [FRONTEND / "app" / "(erp)" / "erp" / "page.tsx"]
    surfaces += sorted((FRONTEND / "components" / "erp").glob("*-detail.tsx"))
    offenders = [p.name for p in surfaces if literal.search(p.read_text(encoding="utf-8"))]
    assert not offenders, (
        "Diese Oberflächen bauen ihre Status-Badge selbst statt sie aus `lib/record-status` "
        f"zu lesen – so laufen Feed und Detail wieder auseinander: {offenders}"
    )
    # … und die eine Ableitung deckt jeden Datensatztyp ab.
    src = (FRONTEND / "lib" / "record-status.ts").read_text(encoding="utf-8")
    for fn in ("userStatus", "articleStatus", "orderStatus", "instanceStatus", "organizationStatus"):
        assert f"export function {fn}" in src, f"{fn} fehlt in lib/record-status.ts"
