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

    assert set(SubOrderStep.model_fields) == {"id", "step_type", "state"}, (
        "Der Teaser braucht Modul + Zustand – den Namen dazu holt das Frontend aus STEP_META."
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
    for part in ("function BranchArm", "function BranchCell", "function SubProcess"):
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
    for gone in ("function TeaserStep", "WebkitMaskImage"):
        assert gone not in flow, (
            f"{gone}: ein Abzweig braucht kein zweites Vokabular und keinen Kasten (#418/#420).")
    # EINE Modul-Karte für den ganzen Fluss – Hauptachse wie Abzweig.
    assert flow.count("function StepCard") == 1, "Es gibt genau EINE Modul-Karte."
    assert "<StepCard compact" in flow, (
        "Der Abzweig nutzt dieselbe Karte, nur eine Nummer kleiner – kein eigenes Bauteil.")
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
    assert "borderRadius" not in flow.split("const ELBOW")[1].split("// ─── Materialfluss")[0], (
        "Ecken werden gezeichnet, nicht aus Rahmenkanten zusammengesetzt.")
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
    assert "maxWidth: 1340" in detail, "Der Fluss bekommt eine eigene, breitere Spur."


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
    assert '<Elbow dir="fork-right" strong={reached}' in flow, "Der Weg in den Abzweig ist gegangen."
    assert "strong={reached && closed}" in flow, "Der Rückweg wird stark, wenn der Abzweig durch ist."


def test_the_flow_shows_what_material_moves():
    """**Auf jeder Kante steht, WAS fliesst** (Testnotiz #413).

    Die eigentliche Geschichte eines Auftrags ist nicht die Reihe seiner Module, sondern das
    **Material**: welche Instanz, wie viel davon, und was unterwegs damit passiert. Genau
    daran sieht man, dass 2 Stück in eine Abweichung gingen und **0 zurückkamen**, weil sie
    verschrottet wurden.

    Damit die Zahl auch nach Abschluss noch stimmt, steht die übernommene Menge dauerhaft am
    Verarbeitungs-Link (``instance_order_links.quantity``, Migration 097) – Reservierungen
    werden gelöst, der Fluss braucht sie danach noch. Gerechnet wird **von unten nach oben**:
    unten steht, was der Auftrag heute hält, und jeder Ast gibt seine Bilanz nach oben weiter –
    keine zweite Buchführung."""
    from app.models import InstanceOrderLink
    from app.schemas.order import FlowLot, OrderDeviationInfo
    from app.services import orders as ord_svc

    assert "quantity" in InstanceOrderLink.__table__.columns, (
        "Ohne die Menge am Link ist «wie viel ging da rein?» nach Abschluss verloren.")
    for f in ("flow_in", "flow_out"):
        assert f in OrderDeviationInfo.model_fields, f
    assert set(FlowLot.model_fields) >= {"instance_object_id", "quantity", "article_name"}

    import inspect as _inspect
    src = _inspect.getsource(ord_svc._sub_order_flow)
    assert "_terminal_amounts" in src, (
        "Was den Bestand endgültig verlassen hat, kommt aus dem Event-Strom – dauerhaft.")
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "function FlowLotChip" in flow and "function plusBalance" in flow
    assert "for (let i = nodes.length - 1; i >= 0; i--)" in flow, (
        "Die Mengen werden von unten nach oben zurückgerechnet.")


def test_the_bypass_carries_what_stayed_on_the_order():
    """**Am Abzweig steht auch, was NICHT abgezweigt ist** (Testnotiz #425).

    Eine Abweichung nimmt fast nie alles: von 4 Stück gehen 2 hinein, 2 bleiben auf dem
    Hauptauftrag. Sichtbar war nur die eine Hälfte – die Menge, die in den Abzweig ging.
    Jetzt läuft die Achse als **Bypass** neben ihm weiter und trägt genau das, was auf ihr
    geblieben ist.

    Damit die Zahl darüber stimmt, hängt die Rückrechnung am **Zustand** des Astes: läuft er
    noch, ist alles Hineingegangene weiterhin dort (oben waren 4); ist er durch, fehlt nur,
    was unterwegs verloren ging."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "isOpen(b) ? lot.quantity : lot.quantity - (back.get(id)?.quantity ?? 0)" in flow, (
        "Ein laufender Abzweig hält sein Material noch – ein abgeschlossener hat es "
        "zurückgegeben, bis auf das Verlorene.")
    assert "<FlowLots lots={edges[i + 1]} small />" in flow, (
        "Der Bypass nennt, was auf dem Hauptauftrag geblieben ist (#425).")


def test_no_edge_shows_material_it_has_not_carried_yet():
    """**Was später einmal hier sein wird, ist nicht vorhersehbar** (Testnotiz #421).

    Die Kanten wurden von unten nach oben aus dem heutigen Bestand gerechnet – und damit
    stand auch an Modulen, die noch gar nicht dran sind, schon eine Menge. Das ist eine
    Behauptung über die Zukunft: welche Instanz ein Verkauf am Ende führt, entscheidet sich
    erst, wenn er dran ist.

    Material trägt darum nur, was der Fluss schon erreicht hat."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "{reached && <FlowLots lots={edges[i]} />}" in flow, (
        "Unterhalb des Fortschritts trägt keine Kante eine Menge (#421).")
    assert "{done && <FlowLots lots={edges[nodes.length]} />}" in flow, (
        "Auch die letzte Kante erst, wenn der Auftrag durch ist.")
    assert "{closed && outLots.size > 0 && (" in flow, (
        "Was ein Abzweig zurückgibt, steht erst da, wenn es zurück ist.")


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
    assert "_lot_meta(db, insts)" in _inspect.getsource(ord_svc._sub_order_flow), (
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
    assert "function OrderRefNode" in flow and flow.count("<OrderRefNode") == 2, (
        "Herkunft und Rückweg sind derselbe Verweis, zweimal benutzt (#438).")
    assert "TYPE_META.order" in flow and "from '@/lib/erp-record'" in flow, (
        "Das Aussehen eines Auftrags steht an EINER Stelle – der Verweis leiht es sich (#439).")
    assert 'caption="Hervorgegangen aus"' in flow and 'caption="Gibt zurück an"' in flow


def test_a_finished_step_stays_readable_while_the_order_rests():
    """**Ruhen heisst: nicht weiterarbeiten – nicht: nichts mehr ansehen** (Testnotiz #442).

    Seit ein ruhender Auftrag den ganzen Fluss stilllegt (#378), liess sich **kein** Modul
    mehr öffnen – auch keines, das längst erledigt ist. Damit war das Protokoll eines fertigen
    Schritts (was gemessen wurde, wer quittiert hat) unerreichbar, solange irgendwo eine
    Abweichung offen war.

    Ein **erledigter** Schritt trägt aber keine Aktion, sondern eine Aufzeichnung; ihn zu
    öffnen kann nichts auslösen. Zu bleibt darum nur, was noch zu tun wäre – dort lehnt das
    Backend ohnehin mit 409 ab, und genau davor sollte #378 bewahren."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "const readable = !paused || s.state === 'done'" in flow, (
        "Ein erledigter Schritt bleibt lesbar, auch wenn der Auftrag ruht.")
    assert "onClick={readable ? () => onSelectStep(String(s.id)) : undefined}" in flow
    assert "const selected = selectedId === String(s.id) && readable" in flow


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

    Im **Entwurf** bleibt sie – dort ist sie das Formular, nicht eine Wiederholung."""
    flow = (FRONTEND / "components" / "erp" / "order-flow.tsx").read_text(encoding="utf-8")
    assert "goal?: { due?: string | null; seller?: string | null }" in flow
    assert "{goal.due}" in flow, "Der Liefertermin steht sichtbar am Endknoten."
    detail = (FRONTEND / "components" / "erp" / "order-detail.tsx").read_text(encoding="utf-8")
    assert ") : showProcess ? null : (" in detail, (
        "Sobald der Prozess läuft, sagt er alles – die Karte entfällt (#447).")
    assert "goal={{" in detail and "record.desired_delivery_date" in detail
