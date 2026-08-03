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


def test_a_person_is_managed_in_exactly_one_place():
    """**Eine Benutzerverwaltung, nicht zwei.**

    Neben dem ERP-Datensatz gab es eine zweite, **nicht verlinkte** Seite
    (``/admin/benutzer``) in der Alt-Palette, mit einer eigenen Rollen-Konfiguration und
    einer eigenen Tabelle. Sie war der einzige Ort, an dem sich eine Person deaktivieren
    bzw. reaktivieren liess – der ERP-Feed zeigte nur aktive Personen, also **musste** es
    sie geben. Jetzt gilt für die Person dieselbe Regel wie für Artikel und Auftrag:
    «inaktiv» ist ein **Zustand**, kein Verschwinden; der Datensatz bleibt im Feed und
    trägt seine Aktionen im Kopf.

    Damit ist auch der zweite **Schreibpfad für die Rolle** entfallen: sie wird am
    ERP-Datensatz gepflegt (``PATCH /erp/records/{object_id}``) – dieselbe fachliche
    Angabe darf nie an zwei Stellen editierbar sein (Leitbild «ERP ist Master»)."""
    import inspect

    from app.routers import admin as admin_router, erp as erp_router

    assert not (FRONTEND / "app" / "(erp)" / "admin" / "benutzer").exists(), (
        "Die zweite Benutzerverwaltung ist wieder da – eine Person wird am ERP-Datensatz "
        "verwaltet, nicht auf einer eigenen Seite.")
    assert not hasattr(admin_router, "update_user_role"), (
        "Zweiter Schreibpfad für die Rolle – sie gehört an den ERP-Datensatz.")
    # Der Feed zeigt JEDE Person; das Detail lässt sich auch deaktiviert öffnen.
    for fn in (erp_router.list_erp_records, erp_router.get_erp_record):
        assert "UserProfile.is_active == True" not in inspect.getsource(fn), fn.__name__
    # Deaktivieren/Reaktivieren bleiben, wo ihre Fachlogik sitzt (Selbst-Schutz,
    # System-KI, offene Dokument-Freigaben) – die Oberfläche ruft sie nur.
    assert hasattr(admin_router, "deactivate_user") and hasattr(admin_router, "reactivate_user")


def test_an_order_is_created_at_exactly_one_place():
    """**Ein Auftrag entsteht mit der Freigabe – nirgends sonst** (Testnotiz #386).

    Der Entwurf lebt im Browser: Bedarf, Positionen, Ablauf und Instanz-Auswahl sammelt
    das Anlage-Fenster lokal und schickt sie in EINEM Aufruf hinaus. Erst dort bekommt der
    Auftrag seine Objektnummer.

    Die Abkürzungs-Knöpfe an Artikel und Instanz waren die zweite Stelle: sie legten sofort
    einen Auftrag an, damit man hinspringen konnte – und wer sich anders entschied,
    hinterliess eine nummernlose Leiche. Sie öffnen jetzt dasselbe Fenster vorbelegt
    (``OrderSeed``) und schreiben nichts."""
    detail = (FRONTEND / "components" / "erp" / "order-detail.tsx").read_text()
    assert "api.createOrder(" in detail, "Das Anlage-Fenster erteilt den Auftrag."

    for name in ("article-detail.tsx", "instance-detail.tsx"):
        src = (FRONTEND / "components" / "erp" / name).read_text()
        assert "api.createOrder(" not in src, (
            f"{name} legt wieder selbst einen Auftrag an – ein Abkürzungs-Knopf belegt nur "
            "das Anlage-Fenster vor (OrderSeed).")
        assert "onCreateOrder" in src, f"{name} braucht den Weg ins Anlage-Fenster."


def test_the_picker_offers_shares_not_instances():
    """**Die Auswahl zeigt Anteile, nicht Instanzen.**

    Eine Charge, an der zwei Aufträge hängen, erscheint als **zwei Zeilen** – eine je
    Halter. Damit sagt der Klick zugleich, wem die Menge weggenommen wird; das Backend
    muss nicht mehr raten (``orders.pick_sources``). Der frühere Chip trug nur die
    Objektnummer und liess genau diese Frage offen.

    Und die Aufteilung ist **auf beiden Seiten** sichtbar: der Auftrag zeigt, wohin ein
    Anteil gewandert ist, die Instanz zeigt dieselbe Aussage aus der anderen Richtung."""
    detail = (FRONTEND / "components" / "erp" / "order-detail.tsx").read_text()
    assert "type Share = {" in detail and "shareKey(" in detail
    assert "from_order_object_id" in detail, "Der Klick muss den Halter mitschicken."
    # Die alte Ding-Auswahl ist abgelöst (``instance_object_ids`` bleibt nur als
    # **Lese**-Feld der Unter-Auftrags-Kurzinfo bestehen).
    assert "instance_object_ids:" not in detail and "instance_quantities" not in detail

    # (Wohin der Rest ging, stand kurzzeitig auch in der Auftragsspezifikation – dort ist
    #  es entfallen (#395); die Aufteilung zeigt das Instanz-Detail.)
    inst = (FRONTEND / "components" / "erp" / "instance-detail.tsx").read_text()
    assert "shares" in inst, "Das Instanz-Detail zeigt die Aufteilung."
    inst = (FRONTEND / "components" / "erp" / "instance-detail.tsx").read_text()
    assert "Aufteilung" in inst, "Die Instanz zeigt dieselbe Aufteilung."


def test_the_draft_is_framed_like_the_order_it_will_become():
    """**Was man gleich sehen wird, sieht man schon beim Modellieren.**

    Wer gebundene Instanzen wählt, hat eine Abweichung – und die hängt nach der Freigabe als
    Abzweig am laufenden Auftrag. Das Bild dafür gibt es längst; es kam bisher einen Schritt
    zu spät. Der Editor sitzt jetzt in der **Mitte** desselben Drei-Spuren-Bildes, links die
    Halter.

    **Und die Rückgabe-Linie IST die Entscheidung**: Linie da → der Halter wartet (``wait``),
    gekappt → seine Menge wird reduziert (``accept``). Man klickt also kein Wort in einem
    Dialog mehr an, sondern zeichnet den Fluss, den man meint – **je Halter einen**.

    «Ersetzen» bleibt bewusst draussen: das ist keine Aussage über diesen Entwurf, sondern
    eine Beschaffung im anderen Auftrag – sie gehört an den laufenden Auftrag.

    **Und die Schere sitzt AUF der Linie** (Testnotiz #499) – dort, wo entschieden wird, wird
    auch bedient. Gekappt heisst schlicht: keine Linie; der Knoten bleibt und trägt den Knopf,
    der sie wiederbringt. Keine zweite Liste darunter, kein zweiter Strichstil."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text()
    detail = (FRONTEND / "components" / "erp" / "order-detail.tsx").read_text()

    # Derselbe Rahmen, dieselben Bausteine – kein zweites Vokabular.
    assert "export function DraftFlowFrame" in flow
    for part in ("<Row ", "<Axis ", "<OrderRefNode", 'dir="in-from-left"', 'dir="out-to-left"'):
        assert part in flow, f"Der Entwurfs-Rahmen benutzt {part} wie der laufende Auftrag."
    assert "if (holders.length === 0) return <>{children}</>;" in flow, (
        "Ohne Halter kein Rahmen – ein gewöhnlicher neuer Auftrag geht aus nichts hervor.")
    # **Kein zweiter Start-/Endknoten** (#498): der Schritt-Editor zeichnet seinen Fluss
    # samt Terminal-Knoten selbst.
    assert 'title="Start · neuer Auftrag"' not in flow and 'title="Ende · neuer Auftrag"' not in flow, (
        "Der Editor bringt seine eigenen Terminal-Knoten mit – ein zweiter ist einer zu viel.")
    # Die Schere sitzt auf der Linie, nicht im Knoten; die gekappte Linie ist Abwesenheit.
    assert "function DraftCutList" not in flow, (
        "Es gibt keine zweite Liste für gekappte Linien – der Knoten selbst trägt den Schalter.")
    assert "{connected && <Elbow dir=\"out-to-left\" strong />}" in flow, (
        "Gekappt = keine Linie (kein zweiter Strichstil, #422/#429).")
    assert "left: SIDE / 2 + RUN / 2, top: 2 * BEND," in flow, (
        "Der Schalter sitzt auf dem waagrechten Stück der Rückgabe-Linie (#499).")

    # Die Antwort entsteht aus den gezeichneten Linien – je Halter eine.
    assert "shortfall_responses" in detail and "shortfall_response:" not in detail
    assert "returnsTo.has(h.object_id) ? 'wait' : 'accept'" in detail, (
        "Linie da = warten, gekappt = Menge reduzieren.")
    assert "'replace'" not in detail.split("function allAnswers")[1].split("\n  }")[0], (
        "«Ersetzen» ist keine Aussage über den Entwurf – es bleibt am laufenden Auftrag.")
    # Der Dialog ist nur noch das Netz für Halter, die der Fluss nicht zeigen konnte.
    assert "uncoveredAffects.length > 0 && (" in detail


def test_the_new_order_header_looks_like_every_other_one():
    """**Der Kopf des Anlage-Fensters ist derselbe wie überall** (Testnotiz #389).

    Symbol · Eyebrow · Name · Objektnummer + Aktionen · Zustand, dazu die Reiter. Fehlt
    etwas, dann nur die **Nummer** – die entsteht mit der Freigabe (#386); sie steht als
    Platzhalter da, die Erklärung im Hover.

    Und es gibt **kein «Abbrechen»**: verworfen wird, indem man woanders hinklickt."""
    detail = (FRONTEND / "components" / "erp" / "order-detail.tsx").read_text()
    assert "objectIdHint" in detail and "'—'" in detail
    assert "Nummer wird bei Freigabe vergeben" not in detail
    assert "erp-actbtn-neutral" not in detail, "Kein «Abbrechen» mehr im Kopf."
    # Die Reiter stehen auch beim Anlegen – «Dokumente» gesperrt, mit Grund im Hover.
    assert "disabled: isCreate" in detail


def test_a_sub_order_is_shown_only_at_its_parent():
    """**Ein Unter-Auftrag gehört genau EINEM Auftrag** (Testnotiz #397).

    Er ist dem Auftrag entstanden, dem er etwas weggenommen hat – und steht dort an dem
    Schritt, an dem es passiert ist. In der Kette Auftrag → Abweichung → Abweichung stand
    die zweite bisher auch im Hauptauftrag (die Klammer sei die Instanz, #350). Das ist
    falsch: sie hat der ERSTEN etwas genommen, nicht ihm. Dass ein anderer Auftrag betroffen
    ist, sagt ihm die Unterdeckungs-Frage bei der Freigabe – jeder Betroffene wird gefragt.

    Die Auswahl-Zeile nennt dazu **Instanz XY im Auftrag ZZ** mit Symbolen statt des
    Halter-Namens (#396): der Name eines Auftrags IST der Artikelname und damit in jeder
    Zeile derselbe – er sagte nichts und las sich wie ein Artikel."""
    from pathlib import Path
    fe = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "erp"
    detail = (fe / "order-detail.tsx").read_text()
    assert "`${sh.holderName || 'Auftrag'} · ${formatObjectId(sh.holderObjectId)}`" not in detail
    assert "Gehört ${sh.holderName || 'Auftrag'}" in detail, "Der Name gehört in den Hover."
    # Die Anteile gehören nicht in die Auftragsspezifikation (#395) – der Prozess sagt es.
    pos = (fe / "order-positions.tsx").read_text()
    assert "ForeignShares" not in pos, (
        "Die Spezifikation nennt Artikel und Instanz; wohin der Rest ging, steht im Prozess.")


def test_the_share_icon_comes_from_the_holder_not_from_the_sort():
    """**Das Symbol sagt, WAS der Halter ist – nicht, wie sein Anteil aussieht** (#398).

    Die Zeile zeigte ein Warndreieck, sobald der Anteil «gebunden» war (in Arbeit,
    reserviert, gesperrt). Gebunden ist aber eine Aussage über die **Instanz**; ihr Halter
    kann ein ganz regulärer Auftrag sein – und stand dann fälschlich als Abweichung da.

    Dazu (#400): der Abkürzungs-Knopf an einer Instanz öffnet die **Auswahl** – auch wenn
    die Zeile noch offen ist, weil die Instanz mehrere Anteile trägt. Ohne das fiel der
    Bedarf auf «Ab Lager» zurück und die Instanz war gar nicht mehr im Spiel."""
    from pathlib import Path
    fe = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "erp"
    detail = (fe / "order-detail.tsx").read_text()
    assert "holderReason: string | null;" in detail
    assert "sh.holderReason === 'deviation' ? <TriangleAlert" in detail, (
        "Das Symbol liest den Grund des Halters, nicht die Sorte des Anteils.")
    assert "useState<OrderGoal | null>(seed?.instance ? 'specific' : null)" in detail, (
        "Wer an einer Instanz startet, meint «Auswählen».")
    inst = (fe / "instance-detail.tsx").read_text()
    assert "rows.length === 1 ? { fromOrderObjectId:" in inst, (
        "Die Instanz kommt immer mit; nur der Anteil bleibt offen, wenn es mehrere gibt.")


def test_a_sub_order_carries_its_own_state_in_the_flow():
    """**Der Zustand gehört an den Knoten, nicht in ein Banner** (Testnotiz #404).

    Dass es einen Unter-Auftrag gibt, stand im Ablauf – sein **Status** nicht: man musste
    ihn öffnen, um zu wissen, ob noch etwas zu tun ist. Jetzt trägt der Knoten dieselbe
    Badge wie überall (``orderStatus``). Damit ist auch der Abbruch-Banner überflüssig: dass
    der Auftrag abgebrochen ist, sagt die Badge im Kopf, und WO es weitergeht steht als
    Unter-Auftrag im Ablauf.

    Und ein abgebrochener Auftrag ist ebenso still wie ein ruhender – an ihm ist nichts mehr
    zu tun, also lässt sich auch kein Schritt mehr öffnen."""
    from pathlib import Path
    from app.schemas.order import OrderDeviationInfo
    assert "abort_into_id" in OrderDeviationInfo.model_fields, (
        "«Abgebrochen» (fortgeführt) vs. «Inaktiv» (verworfen) – dieselbe Projektion wie überall.")
    fe = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "erp"
    flow = (fe / "order-flow.tsx").read_text()
    assert "orderStatus({ status: info.status" in flow, (
        "Der Zustand des Abzweigs kommt aus derselben Projektion wie überall.")
    assert "· ${cfg.label} – klicken zum Öffnen" in flow, (
        "Ohne Kopfkarte (#435) trägt der Hover den Zustand – gerendert wird der Prozess.")
    detail = (fe / "order-detail.tsx").read_text()
    assert "Abgebrochen – fortgeführt im Abweichungsauftrag" not in detail, (
        "Kein Banner – Kopf-Badge und Ablauf sagen es bereits.")
    assert "record.paused === true || record.status === 'inactive'" in detail


def test_the_branch_names_the_module_from_one_place():
    """**Der Abzweig leiht sich das Vokabular, er erfindet keins** (Testnotizen #409/#418).

    Der Prozess eines Unter-Auftrags zeigt je Modul Symbol und Namen und nennt im Hover
    seinen Zustand. Beides ist längst da: die Schrittnamen/-symbole in
    ``lib/process.STEP_META`` (gegen ``domain/event_types.py`` getestet) und – ebenfalls dort –
    das Zustandswort. Darum trägt ``SubOrderStep`` **kein** Label: würde der Name
    mitgeschickt, gäbe es ihn an zwei Stellen, und «Aussondern» hiesse irgendwann im Abzweig
    noch «Ausschleusen».
    """
    from app.schemas.order import SubOrderStep

    assert set(SubOrderStep.model_fields) == {"id", "step_type", "state", "status"}, (
        "Modul, Zustand und der fachliche Zwischenstand – mehr braucht der Teaser nicht, und "
        "weniger darf er nicht haben (#492). Den Namen holt das Frontend aus STEP_META."
    )
    lib = (FRONTEND / "lib" / "process.ts").read_text(encoding="utf-8")
    assert "export const STEP_STATE_LABEL" in lib and "export function stepStateLabel" in lib, (
        "Das Zustandswort eines Schritts gehört neben STEP_META, nicht in eine Ansicht."
    )
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    # Die **Tatsache** prüfen, nicht die Schreibweise: der Abzweig liest Symbol und Worte aus
    # der einen Quelle. (Ein zeilengenauer Vergleich bräche bei jeder Umbenennung einer
    # lokalen Variablen, ohne dass sich fachlich etwas geändert hätte.)
    assert "stepStateLabel(" in flow and "STEP_META[type]" in flow, (
        "Der Abzweig liest Symbol und Worte aus der einen Quelle."
    )
    # Und die Herkunft/der Rückweg werden gezeigt, nicht behauptet: EIN Baustein, zwei
    # Richtungen – wer daraus zwei Komponenten macht, lässt sie auseinanderlaufen.
    # Herkunft und Rückweg gehen in **beide** Richtungen – seit dem Layout-Umbau (#413)
    # als Kette oben (wo stehe ich?), Eltern-Teaser davor und Rückweg-Pille am Ende.
    # Die Brotkrumen-Kette ist entfallen (Notiz #428): der aktuelle Auftrag steht im Kopf des
    # Fensters, der übergeordnete im Herkunfts-Knoten des Flusses – sie sagte beides ein
    # zweites Mal. Herkunft und Rückweg bleiben, als Spiegelbild des Abzweigs.
    assert "OrderChain" not in flow, "Kein zweiter Ort für dieselbe Aussage (#428)."
    assert "function OriginArm" in flow and "function ReturnArm" in flow
    assert "'zurück an'" in flow or "zurück an" in flow


def test_a_sub_order_is_a_regular_process_beside_the_axis():
    """**Ein Abzweig ist ein ganz regulärer Prozess – keine Sonderbehandlung**
    (Testnotizen #417/#418/#420).

    Zwei Zwischenstufen sind damit überholt: ihn im Hauptfluss **auszuklappen** (eigene
    Terminal-Knoten mitten in der Achse) war zu viel; ihn als **angeschnittenen Teaser** mit
    eigenem, kleinerem Vokabular zu zeigen (``TeaserStep`` + Maske) war eine zweite
    Bildsprache für dieselbe Sache – «Datenerfassung» sah nebenan anders aus als auf der
    Achse, und der Kasten drumherum war ein zweiter Rahmen um etwas, das schon aus Karten
    besteht.

    Jetzt gilt: **ein Design, ein System.** Die Achse läuft ununterbrochen weiter; der
    Abzweig hängt daneben und ist dort ein normaler Prozess – dieselbe ``StepCard``, dieselbe
    Modulfarbe, dieselbe Nummerierung, seine Linie läuft **durch** ihn hindurch. Die
    Abzweigung geht dabei **oben mittig** in ihn hinein (#417), und gestrichelt ist nur der
    Übergang zwischen zwei Aufträgen."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    for part in ("function BranchArm", "function SubProcess"):
        assert part in flow, f"Dem Fluss fehlt {part}"
    # **Wie im Unter-Auftrag** (Testnotiz #435): eigener Start- und Endknoten, dieselben
    # Modul-Karten – und keine Kopfkarte davor. Wer einen Schritt anklickt, landet im
    # Datensatz dieses Auftrags; dafür braucht es keine zweite Zusammenfassung daneben.
    assert "function BranchHead" not in flow, (
        "Der Abzweig zeigt seinen Prozess, keine Kurzinfo über ihn (#435).")
    assert '<FlowTerm kind="start" size={30}' in flow and '<FlowTerm kind="end" size={30}' in flow, (
        "Ein Abzweig ist ein Prozess – mit Anfang und Ende, eine Nummer kleiner.")
    # **Und die Terminal-Knoten nennen ihren Prozess** (Notizen #443/#444): ohne Kopfkarte
    # (#435) ist der Hover die Stelle, an der «welcher Auftrag ist das?» beantwortet wird.
    assert "title={`Start · ${hint}`}" in flow and "title={`Ende · ${hint}`}" in flow
    assert "function TeaserStep" not in flow, (
        "Ein Abzweig braucht kein zweites, kleineres Vokabular (#418).")
    # **Das Ausblassen zum Rand ist zurück – aber aus dem umgekehrten Grund** (Notiz #453).
    # Früher war die Maske die Entschuldigung dafür, dass ein angeschnittener Teaser nicht
    # hinpasste (#420); jetzt ist der Nachbar-Prozess vollständig da und tritt nur zurück –
    # als Einladung, ihn zu öffnen. EINE Stelle (`aside`), zwei Richtungen: der Abzweig nach
    # rechts, der übergeordnete Auftrag nach links.
    #
    # **Und er tritt deutlich zurück** (Notiz #460): «man soll klar erkennen, dass die links
    # und rechts dargestellten Prozesse nicht im Fokus stehen». Eine Maske allein reichte
    # dafür nicht – sie blasst nur die Aussenkante aus, die Mitte des Nachbarn blieb genauso
    # laut wie der eigene Prozess. Darum ist der Nachbar **als Ganzes** gedämpft und blasst
    # zusätzlich aus; beim Hovern kommt er ganz nach vorn. Der Hover ist CSS, kein State:
    # ein `onMouseEnter` je Nachbar wäre React-Arbeit für eine reine Optik-Frage.
    assert "const aside = (to: 'left' | 'right', style?: React.CSSProperties)" in flow, (
        "Das Zurücktreten gibt es einmal.")
    assert "aside('right'" in flow and flow.count("aside('left')") == 2
    # **Und der Hover gilt genau EINEM Ast** (Praxis-Rückmeldung): lagen alle Abzweige einer
    # Teilung in demselben `aside`-Kasten, hellten sie beim Hovern gemeinsam auf – man sah
    # also nicht, welchen man gleich öffnet. Der Kasten sitzt darum je Ast, nicht je Spur.
    assert "{...aside('right', { width: '100%', minWidth: 0 })}" in flow, (
        "Jeder Abzweig tritt für sich zurück – und kommt für sich nach vorn.")
    assert "'ix-flow-aside'" in flow, "Die Optik steht im Stylesheet, nicht als Inline-Hover."
    css = (FRONTEND / "app" / "globals.css").read_text(encoding="utf-8")
    assert ".ix-flow-aside" in css and ".ix-flow-aside:hover" in css, (
        "Gedämpft und beim Hovern wieder ganz da – beides an EINER Stelle.")
    # EINE Modul-Karte für den ganzen Fluss – Hauptachse wie Abzweig.
    assert flow.count("function StepCard") == 1, "Es gibt genau EINE Modul-Karte."
    # **Der Abzweig sieht aus wie der geöffnete Unter-Auftrag – zu 100 %** (Testnotiz #492):
    # dieselbe Karte, dieselbe GRÖSSE (#491), derselbe Zwischenstand. Ein `compact`-Modus war
    # genau der Interpretationsspielraum, den es nicht geben darf.
    assert "compact" not in flow, "Eine Karte, eine Grösse (#491)."
    assert "const SIDE = MAIN;" in flow, (
        "Die Seitenspur ist so breit wie die Hauptspur – sonst sind die Karten nicht gleich.")
    assert "badge={stepBadge(st.step_type, st.status)}" in flow, (
        "Auch der fachliche Zwischenstand steht im Abzweig (#492).")
    # Die Abzweigung: waagrecht aus der Achse, dann senkrecht oben mittig hinein (#417) –
    # und **zurück in die Achse** (#424). Beide Ecken aus EINEM Baustein, leicht gerundet (#423).
    assert "function Elbow" in flow, "Eine Ecke der Prozesslinie gibt es genau einmal."
    for d in ("fork-right", "merge-right", "in-from-left", "out-to-left"):
        assert f"'{d}'" in flow, f"Dem Fluss fehlt die Ecke {d}"
    assert '<Elbow dir="fork-right"' in flow and '<Elbow dir="merge-right"' in flow, (
        "Ein Abzweig geht hinaus UND wieder zurück – sonst endet der Prozess im Nichts (#424).")
    # **Eine Ecke ist EIN Pfad, keine zusammengesetzten Rahmenkanten.** Aus CSS-Kästchen mit
    # ``border-radius`` gebaut, sah man an der Naht jede halbe Pixelverschiebung und die
    # Strichstärke lief in der Rundung aus. Möglich wurde der SVG-Pfad erst durch **feste**
    # Spurbreiten: seither ist der Weg von der Achse zur Spurmitte eine Konstante (#445).
    assert "borderRadius" not in flow.split("const ELBOW")[1].split("function Row")[0], (
        "Ecken werden gezeichnet, nicht aus Rahmenkanten zusammengesetzt.")
    # **Und die Abzweigung ist eine Gabelung, kein T** (Notiz #456): die Linie biegt oben mit
    # demselben Radius aus der Achse ab, mit dem sie unten wieder einmündet.
    assert "top: -BEND" in flow, "Der Fork beginnt über der Zelle, mitten auf der Achse."
    assert "<path d={d}" in flow and "strokeWidth={lineW" in flow, (
        "Ein Strich, eine Strichstärke – ein echter Viertelkreis (#423/#430/#431).")
    assert "const RUN = MAIN / 2 + GAP + SIDE / 2" in flow, (
        "Feste Spurbreiten machen die Länge einer Abzweigung berechenbar.")
    assert "onOpen?.(info.object_id)" in flow, "Der Abzweig öffnet den Datensatz."
    # Und der Hauptfluss behält seine Terminal-Knoten – die Achse wird nicht gekappt. Auch
    # sie nennen ihren Prozess im Hover (#443/#444).
    assert 'title={`Start · ${processLabel}`}' in flow and '`Ende · ${processLabel}`' in flow


def test_the_main_process_runs_down_the_middle():
    """**Der eigene Prozess läuft durch die Mitte** (Testnotiz #419).

    Er lag links, weil rechts die Abzweige hingen – die Herkunft musste sich darum nach oben
    zwängen. Mit einer mittigen Achse hat beides seinen festen Platz: **links** der Auftrag,
    aus dem dieser hervorging (und wohin er zurückgibt), **rechts** die, die er abgezweigt
    hat. Eine Zeile des Flusses ist damit drei Spuren – und weil beide Seitenspuren echte
    Modul-Karten tragen (#418), bekommt das Diagramm mehr Raum als die 880-px-Satzbreite des
    übrigen Fensters; waagrecht scrollt es notfalls in seinem eigenen Kasten, nie die Seite."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "left?: React.ReactNode; right?: React.ReactNode" in flow, (
        "Eine Zeile hat zwei Seitenspuren – links Herkunft, rechts Abzweige.")
    assert "left={<OriginArm" in flow and "left={<ReturnArm" in flow, (
        "Woher der Auftrag kam und wohin er zurückgibt, gehört auf DIESELBE Seite.")
    assert "right={<BranchArm" in flow, "Abzweige hängen rechts."
    assert "overflowX: 'auto'" in flow, "Ein breites Diagramm scrollt in seinem eigenen Kasten."
    detail = (FRONTEND / "components" / "erp" / "order-detail.tsx").read_text(encoding="utf-8")
    assert "maxWidth: 1460" in detail, "Der Fluss bekommt eine eigene, breitere Spur."


def test_what_has_been_walked_is_a_strong_solid_line():
    """**Was gegangen ist, ist eine starke Volllinie** (Testnotiz #416).

    Die Achse trug den Fortschritt nicht mit: erledigte und noch nicht erreichte Abschnitte
    sahen gleich aus, obwohl die Linie selbst die einfachste Stelle ist, um «so weit ist er»
    zu sagen – ganz ohne Wort. Jetzt ist der durchlaufene Teil kräftig, der Rest bleibt
    Haarlinie; **gestrichelt** bleibt reserviert für den Übergang in einen anderen Auftrag
    (Herkunft, Abzweig, Rückweg) und für den ruhenden Auftrag."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "function walkedSteps" in flow and "const lineColor" in flow, (
        "Der Fortschritt und die Linie, die ihn zeigt, gehören je an EINE Stelle.")
    assert "strong ? 'var(--fg-2)' : 'var(--border-2)'" in flow, "stark ↔ Haarlinie"
    assert "const reached = i <= walked" in flow, (
        "Kante i liegt über Knoten i – sie ist gegangen, wenn alles darüber erledigt ist.")
    # **Und die Regel gilt überall gleich** (Notiz #429): auch der Weg in einen Abzweig und
    # zurück ist ein gegangener Weg. Gestrichelte Linien gibt es im Fluss nicht mehr – sie
    # waren eine zweite Aussage neben «stark ↔ Haarlinie» und haben sie überschrieben, sobald
    # eine Abweichung offen war (#422).
    assert "dashed" not in flow, (
        "Ein Abzweig ist kein Sonderfall mit eigener Strichart – die Linie sagt nur, wie weit "
        "der Prozess gegangen ist (#422/#429).")
    # **Die Achse ist ein Präfix, ein Abzweig nicht.** «Stark bis zur offenen Stelle» setzt
    # eine Reihenfolge voraus – und zwischen gleichzeitig laufenden Ästen gibt es keine. Zu
    # jedem gestarteten Ast ist ein Weg gegangen worden, also hängt die Stärke dort an SEINEM
    # Zustand; sonst bekam der zweite, ebenfalls laufende Unter-Auftrag nur eine Haarlinie.
    assert '<Elbow dir="fork-right" strong={branches.some(branchStarted)}' in flow, (
        "Der Weg in eine Teilung ist gegangen, sobald irgendein Ast gestartet ist.")
    assert '<Elbow dir="merge-right" strong={branches.every((b) => !isOpen(b))}' in flow, (
        "Der Rückweg wird stark, wenn die GANZE Teilung durch ist.")


def test_the_flow_shows_what_material_moves():
    """**Auf jeder Kante steht, WAS fliesst – aus EINER Quelle** (Notizen #413/#479–#482).

    Die eigentliche Geschichte eines Auftrags ist nicht die Reihe seiner Module, sondern das
    **Material**: welche Instanz, wie viel davon, in welchem Zustand.

    Die Mengen waren zweimal verschieden hergeleitet: die Achse eines Auftrags aus
    ``held_quantity`` (was er **gerade** hält), der Abzweig aus dem Verarbeitungs-Link (was er
    **übernommen** hat). Damit zeigte derselbe Vorgang je nach Blickrichtung zwei Zahlen – und
    weil «gerade gehalten» ein bewegliches Ziel ist (Reservierung gelöst, verschrottet,
    freigegeben), war die eine davon nach jeder Zustandsänderung falsch.

    Jetzt gibt es **eine** Ableitung (``orders.order_material``) für beide Leser, und sie
    steht auf einer Tatsache, die sich nie ändert: ``instance_order_links.quantity``
    (Migration 097). Daraus folgt alles Weitere:

    * **Die Menge schrumpft nicht, der Zustand ändert sich** (#481): nach dem Verschrotten
      steht dort weiterhin «1 Stk» – nur rot. Die Instanz und ihre Menge verschwinden ja
      nicht. Darum trägt jede Zeile die beiden Instanz-Achsen und die Oberfläche projiziert
      sie auf die Ampelfarbe.
    * **Der Teaser zeigt, was der Unter-Auftrag selbst zeigt** (#482) – dieselbe Funktion,
      dieselben Zahlen, per Konstruktion.
    * **Gerechnet wird von OBEN nach unten**: oben das Material, an jeder Teilung geht ab,
      was abzweigt. Die frühere Rückrechnung von unten stand auf dem beweglichen Ziel."""
    from app.models import InstanceOrderLink
    from app.schemas.order import FlowLot, OrderDeviationInfo, OrderResponse
    from app.services import orders as ord_svc
    import inspect as _inspect

    assert "quantity" in InstanceOrderLink.__table__.columns, (
        "Ohne die Menge am Link ist «wie viel ging da rein?» nach Abschluss verloren.")
    for f in ("flow_in", "flow_lost"):
        assert f in OrderDeviationInfo.model_fields, f
    assert "flow_out" not in OrderDeviationInfo.model_fields, (
        "Es gibt keine zweite Mengenliste mehr – was zurückkommt, sagt die Linie (#481).")
    assert {"quality", "disposition"} <= set(FlowLot.model_fields), (
        "Der Zustand gehört an die Materialzeile – sonst kann sie keine Ampelfarbe tragen (#481).")

    # **EINE Quelle für beide Leser – und sie ist das Journal** (ADR 007, Ausbaustufe 2).
    # Achse und Abzweig lesen dieselbe Funktion, und die liest die Buchungen: alles, was je
    # hineingebucht wurde, ist genau einmal da – gehalten, terminal (mit Zeitpunkt) oder
    # abgegeben (im Zustand des Abgangs). Kein held_quantity, keine Links-Menge, keine
    # Reservierungs-Map im Lesepfad; Alt-Aufträge ohne Buchungen fallen auf die Legacy-
    # Ableitung zurück (tolerant lesen, streng schreiben).
    src = _inspect.getsource(ord_svc.order_material)
    assert "ledger.order_view" in src and "_order_material_legacy" in src, (
        "Die Achse liest das Journal; Altbestand die alte Ableitung.")
    legacy = _inspect.getsource(ord_svc._order_material_legacy)
    assert "InstanceOrderLink" in legacy and "_terminal_amounts" in legacy
    resp = _inspect.getsource(ord_svc.to_order_response)
    assert "resp.flow_lots, resp.flow_lost = order_material(db, order, instances)" in resp, (
        "Die Achse liest dieselbe Quelle wie der Abzweig.")
    assert "material, gone = order_material(db, sub)" in _inspect.getsource(ord_svc._sub_info)
    assert "held_quantity(order, i)" not in resp, (
        "«Was hält er gerade» ist ein bewegliches Ziel und darf die Kante nicht speisen.")
    assert "flow_lost" in OrderResponse.model_fields

    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "function FlowLotChip" in flow and "function minus(" in flow
    assert "for (let i = 0; i < nodes.length; i++)" in flow and "edges[0] = lotsOf(lots)" in flow, (
        "Gerechnet wird von oben nach unten – von der Tatsache aus, nicht vom beweglichen Ziel.")
    assert "function plusBalance" not in flow, "Die Rückrechnung von unten ist entfallen."
    assert "instanceStatusConfig(lot.quality, lot.disposition, lot.reserved)" in flow, (
        "Die Ampelfarbe kommt aus derselben Projektion wie an der Instanz selbst (#481).")
    # **Der Zustand hängt an der MENGE** (Testnotizen #483/#485): eine Charge kann zu 3 in
    # Arbeit und zu 1 verschrottet sein. Würden die Zeilen über die Objektnummer
    # zusammengefasst, gäbe es wieder EINEN Zustand für die ganze Menge – genau der Fehler.
    assert "const lotKey = (l: FlowLot) =>" in flow and "l.reserved ? 'r' : ''" in flow, (
        "Der Schlüssel ist Instanz + Zustand, nicht die Instanz.")
    view_src = _inspect.getsource(__import__("app.services.ledger", fromlist=["x"]).order_view)
    assert "TERMINAL" in view_src and "departed" in view_src, (
        "Die übernommene Menge zerfällt in gehaltene Töpfe, terminale und abgegebene.")
    # **Der Zustand ist eine Aussage über das MATERIAL, nie über den betrachtenden Auftrag**
    # (Testnotiz #495). ``reserved`` hiess «der Auftrag, den ich ansehe, läuft noch» – damit
    # sah dasselbe Stück im selben Moment gelb (vom laufenden Eltern) und grün (vom
    # abgeschlossenen Abzweig) aus. Jetzt sagt es, was es behauptet: beansprucht es jemand?
    mat_src = _inspect.getsource(ord_svc.order_material)
    assert "reserved=running" not in mat_src and "running = order.status" not in mat_src, (
        "Der Zustand darf nicht von der Blickrichtung abhängen (#495).")
    assert 'd == "in_stock"' in view_src, (
        "«Gebunden» heisst: gehalten UND am Lager – eine Eigenschaft des Topfs, nicht des "
        "Betrachters.")
    assert "b.returns_material" in flow and "back.length > 0" in flow, (
        "Kommt nichts zurück, führt auch keine Linie zurück (#481) – einfacher geht es nicht.")
    # **Und die Antwort kommt aus EINER Quelle** (Testnotiz #492): derselbe Abzweig zeigte im
    # Eltern-Auftrag keinen Rückweg (dort wurde aus dem Material gerechnet) und in seiner
    # EIGENEN Ansicht doch einen – weil die nur fragte, WEM er zurückgäbe, nicht OB.
    assert "returns_material" in OrderDeviationInfo.model_fields
    assert "if not returns_material(db, order):" in _inspect.getsource(ord_svc._return_target), (
        "Der Rückweg-Knoten liest dieselbe Regel wie der Abzweig im Eltern-Auftrag.")


def test_the_flow_is_a_tree_not_an_episode():
    """**Woher das Material kam, wohin es weiterging** (Testnotiz #493).

    Ein Auftrag ist keine Insel: seine Instanzen hatten vorher ein Leben und haben danach
    eines. Vor dem Startknoten steht darum der **reguläre** Auftrag, aus dem sie kamen, nach
    dem Endknoten der, an den sie weitergingen – damit wird aus einer Episode ein Faden, dem
    man über Auftragsgrenzen hinweg folgen kann.

    **Nur reguläre Aufträge**: eine Abweichung ist eine Episode INNERHALB dieses Vorgangs und
    steht ohnehin als Abzweig im Bild. Und der eigene Eltern-Auftrag fällt heraus – er steht
    schon in der linken Spur; zweimal dasselbe zu sagen macht es nicht klarer.

    Gelesen wird die **Verarbeitungs-Historie** (``instance_order_links``): dauerhaft und
    chronologisch, also auch dann noch vollständig, wenn Reservierungen längst gelöst sind."""
    import inspect as _inspect

    from app.schemas.order import MaterialOrder, OrderResponse
    from app.services import orders as osvc

    for f in ("material_from", "material_to"):
        assert f in OrderResponse.model_fields, f
    assert {"object_id", "name", "quantity"} <= set(MaterialOrder.model_fields)

    src = _inspect.getsource(osvc.material_trace)
    assert "InstanceOrderLink" in src and "order_by(InstanceOrderLink.id)" in src, (
        "Die Historie ist die Quelle – sie ist dauerhaft und chronologisch.")
    assert "o.reason" in src and "o.object_id == order.parent_order_id" in src, (
        "Unter-Aufträge und der eigene Eltern gehören nicht in den Baum.")
    assert "or regular(inst.order_id)" in src, (
        "Ohne regulären Vorgänger ist der Erzeuger die Herkunft.")

    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text()
    detail = (FRONTEND / "components" / "erp" / "order-detail.tsx").read_text()
    assert "function TraceChip" in flow and "<TraceRow rows={materialFrom} dir=\"in\"" in flow
    assert "<TraceRow rows={materialTo} dir=\"out\"" in flow
    assert "materialFrom={record.material_from ?? []}" in detail


def test_a_split_has_three_places_not_two():
    """**Über der Teilung · NEBEN ihr · UNTER ihr** (Testnotizen #425/#496).

    Eine Abweichung nimmt fast nie alles: von 4 Stück gehen 2 hinein, 2 bleiben auf dem
    Hauptauftrag – die Achse läuft als **Bypass** neben ihr weiter und trägt genau die 2.
    Unter der Zusammenführung kommt dazu, was der Ast zurückgegeben hat.

    Gerechnet wurde mit **zwei** Mengen: Bypass und «alles darunter» teilten sich eine. Damit
    die Zahl unten aufging, musste der Bypass verfälscht werden – bei einem abgeschlossenen
    Ast wurde nur das Verschrottete abgezogen, das Zurückgegebene blieb stehen. Ein Stück,
    das VOLLSTÄNDIG in die Abweichung ging, stand damit trotzdem neben ihr auf dem
    Hauptprozess, obwohl es dort nie vorbeikam.

    Jetzt sagt jede Stelle, was sie ist – und die Frage «was ging hinein» ist von «was ist
    zurück» getrennt (``flow_in`` ↔ ``flow_back``, letzteres leer solange der Ast läuft."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "isOpen(b) ? b.flow_in : b.flow_lost" not in flow, (
        "Wer abzweigt, ist nicht daneben – der Bypass zieht IMMER das Hineingegangene ab.")
    assert "beside[i] = minus(edges[i], flowOf(br, (b) => b.flow_in));" in flow
    assert "edges[i + 1] = plus(beside[i]!, flowOf(br, (b) => b.flow_back));" in flow
    assert "<EdgeMaterial lots={bypassAt(i, liveBypass(i))} small" in flow, (
        "Der Bypass hat seine eigene Menge – nicht die von unterhalb der Zusammenführung.")

    # Und die Trennung steht auch im Backend: was hineinging ≠ was zurück ist.
    from app.schemas.order import OrderDeviationInfo
    for field in ("flow_in", "flow_back", "flow_lost"):
        assert field in OrderDeviationInfo.model_fields, field
    import inspect as _inspect
    from app.services import orders as osvc
    # **Was zurück IST, sagt das Material-Journal** (ADR 007): die tatsächlichen
    # Rückgabe-Buchungen – ein laufender Abzweig hat schlicht noch keine. Die frühere
    # Status-Fallunterscheidung war die Simulation eines Journals; sie bleibt nur als
    # Lesepfad für Alt-Aufträge ohne Buchungen.
    back_src = _inspect.getsource(osvc._flow_back)
    assert "ledger.departed_of" in back_src, (
        "Was zurück IST, kommt aus den Buchungen – keine Vorhersage aus dem Hineingegangenen.")
    assert 'if sub.status in ("draft", "released")' in back_src, (
        "Alt-Aufträge ohne Journal: leer solange er läuft, danach die abgeleitete Rückgabe.")
    assert "returning_material" in _inspect.getsource(osvc.returns_material), (
        "«Kommt etwas zurück?» und «was kommt zurück?» sind EINE Ableitung.")


def test_parallel_sub_orders_are_one_split_in_several_directions():
    """**Zwei gleichzeitig laufende Unter-Aufträge – ohne vierte Spur und ohne Scrollbalken.**

    Mehrere Abweichungen am selben Schritt sind **EINE Teilung in mehrere Richtungen**, nicht
    mehrere Teilungen nacheinander: das Material verlässt die Achse an EINEM Punkt, und wie
    viel wohin geht, sagt die Menge über jedem Unterprozess. Daraus folgt zweierlei:

    * es gibt **einen** Fork und **einen** Merge – weniger Linien, keine Überlagerung, und
    * die Achse darunter trägt, was dem Auftrag **wirklich** geblieben ist (Testnotiz #469):
      wurden von 4 Stück 2 und 1 abgezweigt, steht dort 1 – nicht ein Zwischenstand nach der
      ersten von zwei Teilungen.

    Die Zwischenstufe – je Ast ein eigener Fork mit eigenem Bypass – rechnete zwar auch
    korrekt, behauptete aber eine Reihenfolge («erst A, dann B»), die es nicht gibt, und liess
    die Achse eine Menge tragen, die der Auftrag nie hielt.

    **Und die Linie zu einem Ast hängt an SEINEM Zustand, nicht am Fortschritt der Achse.**
    «Stark bis zur offenen Stelle» ist ein Präfix und setzt eine Reihenfolge voraus; zwischen
    gleichzeitig laufenden Ästen gibt es keine. Ohne diese Trennung bekam der zweite,
    ebenfalls laufende Unter-Auftrag nur eine Haarlinie."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "branches?: OrderDeviationInfo[]" in flow, (
        "Ein Knoten trägt die Äste EINER Teilung – daraus folgt ein Fork und ein Merge.")
    assert flow.count('<Elbow dir="fork-right"') == 1, (
        "Eine Teilung hat genau eine Abzweigung (#469).")
    assert flow.count('<Elbow dir="merge-right"') == 1, (
        "… und genau eine Einmündung.")
    assert "const byAge = (l: OrderDeviationInfo[]) => [...l].sort((a, b) => a.object_id - b.object_id)" in flow, (
        "Innerhalb einer Teilung ist die Reihenfolge die Entstehung.")
    assert "const branchStarted = (b: OrderDeviationInfo) => b.status !== 'draft';" in flow, (
        "Ob zu einem Ast ein Weg gegangen wurde, sagt SEIN Zustand.")
    assert "strong={branches.some(branchStarted)}" in flow, (
        "Der Fork ist stark, sobald irgendein Ast gestartet ist.")
    assert "{i > 0 && <Axis h={20} strong={branchStarted(b)} />}" in flow, (
        "Auch der zweite, gleichzeitig laufende Ast bekommt eine volle Linie.")
    assert "strong={branches.every((b) => !isOpen(b))}" in flow, (
        "Zurück auf die Achse geht es erst, wenn die GANZE Teilung durch ist.")
    assert "function BranchCell" not in flow, (
        "Fork und Merge gehören der Teilung, nicht dem einzelnen Ast.")


def test_no_edge_shows_material_it_has_not_carried_yet():
    """**Was später einmal hier sein wird, ist nicht vorhersehbar** (Testnotiz #421).

    Die Kanten wurden von unten nach oben aus dem heutigen Bestand gerechnet – und damit
    stand auch an Modulen, die noch gar nicht dran sind, schon eine Menge. Das ist eine
    Behauptung über die Zukunft: welche Instanz ein Verkauf am Ende führt, entscheidet sich
    erst, wenn er dran ist.

    Material trägt darum nur, was der Fluss schon erreicht hat."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "{reached && <EdgeMaterial lots={lotsAt(i, liveEdge(i))}" in flow, (
        "Unterhalb des Fortschritts trägt keine Kante eine Menge (#421).")
    assert "{done && <EdgeMaterial lots={lotsAt(nodes.length," in flow, (
        "Auch die letzte Kante erst, wenn der Auftrag durch ist.")
    assert "<FlowLots lots={backLots} small />" in flow and "info.flow_back" in flow, (
        "Unter dem Abzweig steht, was tatsächlich zurück IST – nicht eine Vorhersage aus "
        "dem, was hineinging (#481/#488/#496).")


def test_a_flow_lot_names_instance_article_location_and_quantity():
    """**Eine Kante trägt die vier Angaben, die den Verlauf nachvollziehbar machen**
    (Testnotiz #426): welche **Instanz**, welcher **Artikel**, **wo** sie liegt, **wie viel**.

    Kurz steht Menge × Instanz – alles Weitere im Hover, damit eine Kante eine Kante bleibt
    und keine Tabelle wird. Beide Objektnummern öffnen ihren Datensatz.

    Aufgelöst wird das **einmal im Backend** (batch, kein N+1) und in EINER Form: dieselbe
    Zeile speist die Hauptachse (``OrderResponse.flow_lots``) und die Abzweige
    (``flow_in``/``flow_out``). Zwei Formen für dieselbe Aussage wären zwei Wahrheiten."""
    from app.schemas.order import FlowLot, OrderResponse
    from app.services import orders as ord_svc

    assert {"instance_object_id", "article_object_id", "location_label", "quantity"} <= set(
        FlowLot.model_fields), "Instanz · Artikel · Standort · Menge"
    assert OrderResponse.model_fields["flow_lots"].annotation == list[FlowLot], (
        "Die Achse trägt dieselbe Zeile wie der Abzweig – eine Form, ein Leser.")
    import inspect as _inspect
    meta = _inspect.getsource(ord_svc._lot_meta)
    assert "location_labels(" in meta and "Article.id.in_" in meta, "batch, kein N+1"
    assert "_lot_meta(db, meta_insts)" in _inspect.getsource(ord_svc.order_material), (
        "Abzweig und Achse lösen dieselben Angaben an derselben Stelle auf.")
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "function FlowLotChip" in flow and "nav?.(lot.instance_object_id)" in flow
    # **Symbole statt Versalien-Beschriftungen** (Testnotiz #433) – und **keine doppelte
    # Angabe** (#441): Menge und Instanz stehen bereits in der Pille selbst, im Hover bleiben
    # Artikel und Standort. Je ein Symbol, das Wort im Titel; weniger ist mehr.
    for fact in ('icon={Package} title="Artikel"', 'icon={MapPin} title="Standort"'):
        assert fact in flow, f"Dem Hover fehlt {fact}"
    assert 'title="Menge"' not in flow, (
        "Die Menge steht in der Pille – ein zweites Mal im Hover wäre eine zweite Wahrheit.")
    assert "{qtyText(lot)} × {formatObjectId(lot.instance_object_id)}" in flow, (
        "Dafür trägt die Pille die Einheit – sonst ginge «kg» verloren.")
    assert "<ObjId value={lot.article_object_id} />" in flow, "Auch der Artikel ist klickbar."


def test_the_origin_is_a_reference_not_a_preview():
    """**Woher es kommt – ein Verweis, keine Vorschau** (Testnotizen #436/#437/#438/#439).

    Zwischenstufe war, im Herkunfts-Bereich einen Prozessschritt des Eltern zu zeigen und
    darüber, wie viele davor liegen. Beides ist zurückgenommen: der Verweis auf den
    übergeordneten Auftrag genügt – sein Prozess gehört in seinen Datensatz, einen Klick
    entfernt.

    Der Verweis trägt dafür die **visuelle Identität eines Auftrags** aus der einen Quelle
    (``lib/erp-record.TYPE_META.order``): dasselbe Symbol, dieselbe getönte Fläche wie im Feed
    und im Detail-Kopf. Ein Verweis auf einen Datensatz soll aussehen wie dieser Datensatz.
    Und der **Rückweg** ist derselbe Baustein, nur andersherum – nicht eine zweite Form für
    dieselbe Aussage."""
    from app.schemas.order import OrderOrigin

    for gone in ("chain", "parent_steps", "step_id", "step_type"):
        assert gone not in OrderOrigin.model_fields, (
            f"{gone}: die Herkunft ist ein Verweis, keine Vorschau des Eltern-Prozesses.")
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "MoreSteps" not in flow, "«N Schritte davor» ist entfallen (#437)."
    # **EIN Baustein für jeden Verweis auf einen Auftrag** (#438) – Herkunft wie Rückweg,
    # am laufenden Auftrag wie am Entwurf. Gezählt wird darum die Definition, nicht die
    # Verwendung: dass er mehrfach benutzt wird, ist ja genau der Punkt.
    assert flow.count("function OrderRefNode") == 1 and flow.count("<OrderRefNode") >= 2, (
        "Herkunft und Rückweg sind derselbe Verweis, mehrfach benutzt (#438).")
    assert "TYPE_META.order" in flow and "from '@/lib/erp-record'" in flow, (
        "Das Aussehen eines Auftrags steht an EINER Stelle – der Verweis leiht es sich (#439).")
    assert 'caption="Hervorgegangen aus"' in flow and 'caption="Gibt zurück an"' in flow


def test_a_finished_step_stays_readable_while_the_order_rests():
    """**Ruhen heisst: nicht weiterarbeiten – nicht: nichts mehr ansehen** (Notizen #442/#465).

    Seit ein ruhender Auftrag den ganzen Fluss stilllegt (#378), liess sich **kein** Modul
    mehr öffnen – auch keines, das längst erledigt ist. Damit war das Protokoll eines fertigen
    Schritts (was gemessen wurde, wer quittiert hat) unerreichbar, solange irgendwo eine
    Abweichung offen war. Dasselbe galt für einen **künftigen** Schritt: seine Planung liess
    sich nicht ansehen, obwohl genau das in einem laufenden Auftrag jederzeit geht (#465).

    **Ansehen darf man darum jeden Schritt** (#471). Ein Panel zu öffnen ist Lesen; ob sich
    darin etwas AUSFÜHREN lässt, entscheidet ohnehin das Backend (``resolve_exec_step``: nur
    der aktive Schritt, sonst 409 mit dem echten Grund). Die Sperre bei ruhendem Auftrag war
    eine zweite, rein visuelle Regel daneben – und sie verbarg ausgerechnet die Daten, die
    man beim Klären einer Abweichung braucht."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "const readable" not in flow, (
        "Es gibt keine zweite, rein visuelle Sperre neben der des Backends mehr.")
    assert "onClick={() => onSelectStep(String(s.id))}" in flow, (
        "Jeder Schritt lässt sich öffnen – erledigt, laufend oder künftig.")
    assert "const selected = selectedId === String(s.id);" in flow


def test_the_process_is_narrow_and_its_step_numbers_are_gone():
    """**Feste Spuren statt elastischer** (Testnotiz #445) – und **keine internen Nummern**
    an der Oberfläche (#440).

    Die Seitenspuren füllten den ganzen verfügbaren Rest; das Diagramm wurde dadurch so breit
    wie das Fenster, ohne dass die zusätzliche Fläche etwas trug. Feste Breiten machen es
    schmaler **und** berechenbar – erst dadurch lässt sich eine Ecke als ein Pfad zeichnen.

    Die Schritt-Nummer («100000596–01») war eine Hilfskonstruktion für die Entwicklung. Sie
    beantwortet keine Frage, die ein Mensch am Auftrag hat – der Schritt heisst nach seinem
    Modul, und wo er steht, sagt seine Position im Fluss."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "flex: 1" not in flow.split("function Row")[1].split("// ─── Materialfluss")[0], (
        "Die Spuren sind fest breit – sonst ist die Länge einer Abzweigung nicht berechenbar.")
    assert "'--flow-lane'" in flow, "Ohne Nachbarn fällt die Spurbreite auf 0."
    assert "stepNr" not in flow and "–${String(index + 1)" not in flow, (
        "Die Schritt-Nummer war intern – sie gehört nicht an die Oberfläche (#440).")


def test_the_order_goal_hangs_at_the_end_of_the_process():
    """**Das Ziel gehört ans Prozessende** (Testnotiz #446) – und die Spezifikations-Karte
    entfällt damit (#447).

    Wann der Auftrag fertig sein soll, ist die Aussage des **Endknotens**, nicht eine Zeile in
    einer Karte darüber. Und wenn der Prozess läuft, steht auch alles andere schon in ihm:
    welche Instanz mit welcher Menge unterwegs ist, trägt die Kante (samt Artikel und Standort
    im Hover). Eine Karte, die dasselbe noch einmal aufzählt, wäre eine zweite Wahrheit über
    demselben Auftrag.

    Im **Entwurf** bleibt sie – dort ist sie das Formular, nicht eine Wiederholung.

    **Und die Angabe steht NEBEN dem Knoten, nicht darunter** (Notiz #457): unter ihm
    schob sie den Endkreis nach oben und die letzte Kante zusammen. Absolut gesetzt bleibt
    der Kreis auf der Achse, wo er hingehört – die Beschriftung hängt daneben."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "goal?: { due?: string | null; seller?: string | null }" in flow
    assert "{goal.due}" in flow, "Der Liefertermin steht sichtbar am Endknoten."
    assert "position: 'absolute', left: '100%', top: '50%'," in flow, (
        "Die Zielangabe hängt rechts am Endknoten, ohne die Achse zu verschieben (#457).")
    detail = (FRONTEND / "components" / "erp" / "order-detail.tsx").read_text(encoding="utf-8")
    assert ") : showProcess ? null : (" in detail, (
        "Sobald der Prozess läuft, sagt er alles – die Karte entfällt (#447).")
    assert "goal={{" in detail and "record.desired_delivery_date" in detail


def test_the_process_point_offers_a_shortcut_onto_its_material():
    """**Ein Auftrag auf genau das, was gerade dran ist** (Testnotiz #455).

    An der Kante, an der die starke Linie endet, liegt das Material des Augenblicks – und
    genau darauf will man einen Auftrag ansetzen (in der Praxis meist eine Abweichung). Der
    Knopf nimmt **alle** Instanzen dieser Kante mit: mehrere Artikel werden zu mehreren
    Positionen, jede mit ihren Instanzen und Mengen.

    Angelegt wird dabei nichts – der Entwurf lebt im Browser (#386) –, und **was** daraus
    wird, entscheidet weiterhin die Auswahl (``subject.classify_pick``). Der Knopf ist eine
    Eingabehilfe, kein zweiter Weg, einen Auftrag zu erzeugen (#371).

    **An einem offenen Abzweig steht der Prozess eine Kante tiefer** (Notiz #459): dort hat
    sich das Material bereits geteilt – ein Teil ging in den Abzweig, der Rest blieb auf dem
    Hauptauftrag. Die Kante über dem Fork zählt beides zusammen; wer dort ansetzt, legt einen
    Auftrag auf Stücke an, die längst woanders hängen. Der Bypass ist die tiefste erreichte
    Stelle der Achse – und damit der Prozess-Punkt.

    **Und läuft der Auftrag nicht mehr, gibt es gar keine Stelle** (Notiz #468): sein Material
    ist beim übergeordneten Auftrag, der aktive Schritt steht dort. Ein Knopf, der hier einen
    Auftrag auf zurückgegebene Stücke ansetzt, zeigt ins Leere."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "function FlowShortcut" in flow and "function EdgeMaterial" in flow
    assert "const liveEdge = (i: number) => here?.at === i && !here.bypass;" in flow, (
        "Es gibt EINE Stelle, an der der Prozess steht – Kante und Abkürzung lesen sie.")
    assert "const liveBypass = (i: number) => here?.at === i && here.bypass;" in flow, (
        "Am Abzweig gehört sie an den Bypass, also an das, was geblieben ist (#459).")
    assert "onCreate={liveEdge(i) ? onCreateOrder : undefined}" in flow, (
        "Die Abkürzung sitzt dort, wo der Prozess steht – nicht an jeder Kante.")
    assert "onCreate={liveBypass(i) ? onCreateOrder : undefined}" in flow
    assert "onCreate={liveEdge(nodes.length) ? onCreateOrder : undefined}" in flow, (
        "Auch die letzte Kante trägt sie nur, solange der Auftrag läuft (#468).")
    assert "running = true" in flow and "running={record.status === 'released'}" in (
        FRONTEND / "components" / "erp" / "order-detail.tsx").read_text(encoding="utf-8"), (
        "Ob der Prozess noch läuft, sagt der Auftrags-Status – nicht eine Vermutung im Fluss.")
    detail = (FRONTEND / "components" / "erp" / "order-detail.tsx").read_text(encoding="utf-8")
    assert "export function seedFromLots" in detail and "byArticle" in detail, (
        "Eine Position ist ein Artikel – mehrere Instanzen desselben gehören zusammen.")
    assert "lines?: SeedLine[]" in detail, "Der Entwurf kann mehrere Positionen vorbelegen."
    page = (FRONTEND / "app" / "(erp)" / "erp" / "page.tsx").read_text(encoding="utf-8")
    assert "onCreateOrder={(sd) => startCreate('order', sd)}" in page, (
        "Der Auftrag entsteht über denselben Anlage-Weg wie jeder andere.")


def test_a_preselected_share_names_its_holder():
    """**Eine Vorauswahl nennt ihren Halter – «nicht genannt» ist nicht «frei»** (Notiz #461).

    Die Abkürzung übernahm Artikel und Menge korrekt, wählte aber die falsche Instanz vor.
    Ursache war eine Sorte, die es zweimal gab: ``from_order_object_id`` kannte
    ``null`` = «der freie Anteil» – und eine **fehlende** Angabe wurde genauso gelesen.

    Das Material am Prozess-Punkt gehört aber diesem Auftrag; frei ist daran nichts. Ohne
    Halter suchte ``reconcilePicks`` nach einem freien Anteil, fand bei mehreren Anteilen
    keinen und liess die Auswahl fallen – bei genau einer Zeile griff der Rückfall «es gibt
    ja nur eine», und der konnte die falsche sein.

    Zwei Hälften, beide nötig: die Abkürzung **nennt** den Halter (sie weiss ihn – es ist der
    Auftrag, dessen Fluss sie zeigt), und wo nichts genannt ist, bleibt es ``undefined``
    statt ``null``. Geraten wird nur noch dort, wo es nichts zu raten gibt (eine Zeile)."""
    detail = (FRONTEND / "components" / "erp" / "order-detail.tsx").read_text(encoding="utf-8")
    assert "export function seedFromLots(lots: FlowLot[], holderObjectId: number | null)" in detail, (
        "Die Abkürzung weiss, wem das Material gehört – also sagt sie es (#461).")
    assert "fromOrderObjectId: holderObjectId" in detail, (
        "Der Anteil am Prozess-Punkt hängt an diesem Auftrag, er ist nicht frei.")
    assert "const named = p.from_order_object_id !== undefined;" in detail, (
        "«nicht genannt» und «frei» sind zwei verschiedene Aussagen.")
    assert "i.fromOrderObjectId === undefined" in detail, (
        "Ein nicht genannter Halter bleibt nicht genannt – `null` wäre eine Behauptung.")
    assert "seedFromLots(picked, record.object_id ?? null)" in detail, (
        "Den Halter kennt der Auftrag, dessen Fluss die Abkürzung zeigt.")
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "onCreateOrder?: (lots: FlowLot[]) => void" in flow, (
        "Der Fluss reicht nur das Material weiter – wem es gehört, weiss sein Auftrag.")


def test_a_future_step_shows_what_is_planned():
    """**Ein künftiger Schritt zeigt seine Planung** (Testnotiz #487).

    «Wird aktiv, sobald der vorherige Schritt erledigt ist» war die einzige Auskunft – nett,
    aber sie beantwortet nicht die Frage, die man an dieser Stelle hat: *was soll hier
    eigentlich passieren?* Prüfumfang, Ziel, Ressourcenzeilen und Lieferant stehen längst im
    Panel; es wurde nur nicht gerendert, weil der Schritt vorher abgebrochen hat.

    Jetzt rendert **jedes** Modul seine Planung, eine Zeile sagt, dass sie noch nicht dran
    ist – und die **Aktionen bleiben aus**. Die Regel steht an EINER Stelle (`PlannedNotice`),
    damit sie nicht in vier Panels auseinanderläuft."""
    fields = (FRONTEND / "components" / "erp" / "fields.tsx").read_text(encoding="utf-8")
    assert "export function PlannedNotice()" in fields, "Die Zeile gibt es einmal."
    for name in ("inspection-panel", "movement-panel", "scrap-panel", "resource-panel"):
        src = (FRONTEND / "components" / "erp" / f"{name}.tsx").read_text(encoding="utf-8")
        assert "Wird aktiv, sobald" not in src, (
            f"{name}: der frühere Abbruch verbarg die Planung des Schritts.")
        assert "const planned = stepState === 'locked';" in src, f"{name}: kein Planungs-Zustand"
        assert "{planned && <PlannedNotice />}" in src, f"{name}: keine Notiz"
        assert "planned || saving" in src or "!planned &&" in src, (
            f"{name}: ein geplanter Schritt führt nichts aus.")


def test_a_taken_share_is_not_told_twice():
    """**Wer als Abzweig im Bild steht, braucht daneben keine Zeile mehr** (Testnotiz #466).

    «1 abgegeben an 100000597» war in aller Regel eine **zweite Erzählung desselben
    Vorgangs**: wer sich hier einen Anteil geholt hat, wird dadurch zur Abweichung DIESES
    Auftrags (``routers/orders._make_deviation``: Eltern = wer das Stück hielt) – steht also
    ohnehin als Abzweig im Fluss, mit der Menge auf seiner Kante.

    Ganz löschen wäre trotzdem falsch: greift eine Auswahl über **mehrere** Halter, wird nur
    der erste sein Eltern-Auftrag. Die übrigen erfahren sonst nirgends, warum ihnen plötzlich
    etwas fehlt – für sie bleibt die Zeile die einzige Spur."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "function Resolutions(" in flow, "Die Auflösungen einer Stelle kommen aus EINER Hand."
    assert "r.kind === 'share_taken'" in flow and "shown.has(r.other_order_object_id)" in flow, (
        "Ein Anteil, dessen Nehmer als Abzweig dasteht, wird nicht zweimal erzählt (#466).")
    assert "const shownSubs = new Set([...claimed, ...subOrders.map((x) => x.object_id)]);" in flow
    assert "<ResolutionLine" not in flow.split("function Resolutions(")[0], (
        "Auflösungen werden nirgends an `Resolutions` vorbei gerendert.")


def test_what_is_past_steps_back_on_the_edges_too():
    """**Stark ist es dort, wo der Prozessschritt gerade aktiv ist** (Notizen #462/#464/#467).

    Ein erledigter Prozessschritt tritt zurück; die Mengen-Angabe darüber tat es nicht und war
    damit lauter als der Schritt, zu dem sie gehört (#462). Zwei Stellen kamen dazu, beide mit
    derselben Wurzel – «vergangen» hing an einem Zähler statt an der einen Frage *wo steht der
    Prozess?*: die Kante **über einem offenen Abzweig** (dort hat sich das Material längst
    geteilt, #464) und die **letzte Kante eines abgeschlossenen Auftrags** (dessen Stücke sind
    zurückgegeben, der aktive Schritt steht im übergeordneten Auftrag, #467).

    Jetzt gibt es genau EINE Stelle (``here``), und alles andere ist Vergangenheit."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "opacity: past ? 0.55 : 1" in flow, "Vergangene Kanten sind gedämpft (#462)."
    assert "const here: { at: number; bypass: boolean } | null = !running ? null" in flow, (
        "Wo der Prozess steht, ist EINE Ableitung – und ohne laufenden Auftrag gibt es sie nicht.")
    assert "past={!liveEdge(i)}" in flow, (
        "Eine Kante ist Vergangenheit, sobald der Prozess nicht mehr an ihr steht.")
    assert "past={!liveEdge(nodes.length)}" in flow, (
        "Auch die letzte Kante – ein abgeschlossener Auftrag hat sein Material zurückgegeben.")
    assert "<FlowLots lots={inLots} small past={walked > 0} />" in flow, (
        "Auch im Abzweig: was hineinging, ist Vergangenheit, sobald er losgelaufen ist.")
    # **Und eine durchlaufene Kante zeigt den Zustand von DAMALS** (Testnotiz #488): wird ein
    # Stück später verschrottet, stand es sonst rückwirkend auf jeder Kante rot, die es
    # passiert hatte, als es noch in Arbeit war. Beim Abschluss eines Schritts friert der
    # Zustand ein; nur dort, wo der Prozess GERADE steht, gilt der aktuelle.
    assert "function asOf(lots: Lots, cutoff: string | null)" in flow, (
        "Der Rückblick gibt es einmal.")
    assert "const lotsAt = (i: number, live: boolean) => asOf(edges[i], live ? null : cutoffs[i]);" in flow, (
        "Live am Prozess-Punkt, eingefroren überall darüber.")
    assert "if (s?.state === 'done' && s.completed_at) last = s.completed_at;" in flow, (
        "Der Stichtag ist der Abschluss des Schritts darüber.")
    assert "opacity: past ? 0.55 : 1" in flow


def test_the_flow_shows_state_only_where_the_line_does_not():
    """**Kein Symbol für etwas, das die Linie schon sagt** (Testnotizen #450/#452).

    Dass der Prozess an diesem Modul steht, sieht man daran, dass es aktiv ist und die starke
    Linie hier endet; dass er ruht, daran, dass die starke Linie nicht hinführt und kein Modul
    aktiv ist. Ein Uhr- bzw. Pause-Symbol daneben wiederholt das nur.

    Übrig bleiben die zwei Aussagen, die man der Linie **nicht** ansieht: durch und
    fehlgeschlagen."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    marks = flow.split("const STATE_MARK")[1].split("};")[0]
    assert "done:" in marks and "failed:" in marks
    for gone in ("active:", "blocked:", "PauseCircle", "Clock3"):
        assert gone not in marks, f"{gone}: das sagt die Linie bereits (#450/#452)."
