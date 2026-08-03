"""**Mengen sind Mengen, keine Zeilenzahlen.**

Eine Instanz ist keine Sache, sondern eine **Menge**: `unit` trägt genau ein Stück,
`batch` beliebig viele – auch gebrochene (2.5 kg, 0.75 m²). Genau daraus entsteht die
wiederkehrende Fehlerklasse dieses Systems: *jemand zählt Zeilen, wo er Mengen summieren
müsste*. Eine Charge à 500 Schrauben ist EINE Zeile und FÜNFHUNDERT Stück; `len(insts)`
liefert dann 1, und die Zahl wandert als Menge weiter.

Belegte Fälle:
  * Testnotiz #72  – der Prüfumfang rechnete mit der *Zahl* der Subjekte: eine Abweichung
    auf EINE Charge à 5 Stk ergab 1 Probe statt 5.
  * Testnotiz #333 – die Bestands-Filter zählten Instanzen: «2» statt 500 Schrauben.
  * `provisioning._sub_order` schrieb `quantity=len(insts)` – ein Bereitstellungs-Auftrag
    für eine 500er-Charge stand als «1 Stk» da.

Die Fehler haben denselben Bau, also braucht es EINEN Wächter statt drei Einzelfixes.
Er sucht per AST (nicht per Textsuche) nach Mengen-Feldern, die aus einer **Anzahl**
befüllt werden.

Warum das Datenmodell trotzdem so bleibt: «eine Instanz = eine Zeile mit einer Menge»
statt «N Zeilen à 1 Stück» ist keine Bequemlichkeit, sondern Voraussetzung. Eine Charge
darf 2.5 kg sein – «2.5 Zeilen» gibt es nicht –, die Objektnummer ist systemweit eindeutig
(QR-Scan, Referenzen, Standort-Kette), und eine 1000er-Charge wären 1000 Zeilen für jede
Reservierung. Die Teilmengen-Logik (`reservation.py`, `location_split.py`) ist der Preis
dafür, und sie steht an genau zwei Stellen.
"""

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

# Felder, die eine **Menge** tragen (Decimal), keine Anzahl.
QUANTITY_FIELDS = {"quantity", "reserved_quantity", "move_quantity", "qty"}
# Ausdrücke, die eine **Anzahl** liefern.
COUNTING_CALLS = {"len", "count"}


def _counts_rows(node: ast.AST) -> bool:
    """Liefert dieser Ausdruck eine Anzahl (``len(x)`` / ``x.count()``)?"""
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    if isinstance(fn, ast.Name) and fn.id in COUNTING_CALLS:
        return True
    return isinstance(fn, ast.Attribute) and fn.attr in COUNTING_CALLS


def test_no_quantity_is_filled_from_a_row_count():
    """Ein Mengen-Feld darf nie aus einer Zeilen-Anzahl befüllt werden.

    Gemeint sind Schlüsselwort-Argumente (``Order(quantity=len(insts))``) und Zuweisungen
    (``inst.quantity = len(rows)``). Wer wirklich Zeilen zählen will, benennt die Variable
    anders – das Mengen-Feld ist für Mengen da. Richtig ist ``qty_sum(i.quantity for i in …)``
    (so macht es ``deviation.create_deviation`` seit Testnotiz #72)."""
    offenders: list[str] = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(APP).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg in QUANTITY_FIELDS and _counts_rows(kw.value):
                        offenders.append(f"{rel}:{kw.value.lineno}  {kw.arg}=<Anzahl>")
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    name = target.attr if isinstance(target, ast.Attribute) else (
                        target.id if isinstance(target, ast.Name) else None)
                    if name in QUANTITY_FIELDS and _counts_rows(node.value):
                        offenders.append(f"{rel}:{node.lineno}  {name} = <Anzahl>")
    assert not offenders, (
        "Hier wird eine ANZAHL in ein MENGEN-Feld geschrieben. Eine Charge à 500 ist EINE "
        "Zeile und 500 Stück – richtig ist qty_sum(i.quantity for i in …):\n  "
        + "\n  ".join(offenders)
    )


# ─── Die Stichprobe kennt keine Charge-Sonderregel mehr ──────────────────────────

def test_a_sample_is_drawn_by_quantity_not_by_kind():
    """Wie viele Proben eine Instanz hergibt, sagt ihre **Menge** – nicht ihr ``kind``.

    Vorher gab es zwei Zweige (Charge → N Proben aus einer Instanz, Einzelteil → N
    Instanzen), und sie hingen an ``len(insts) == 1 and kind == 'batch'``. Zwei Chargen in
    einem Auftrag fielen damit in den Einzelteil-Zweig und ergaben **eine** Probe je Charge,
    egal wie gross sie war. Eine Regel deckt beides – und den dritten Fall gleich mit."""
    from app.services.inspection import sample_capacity

    assert sample_capacity(1) == 1              # Einzelteil: genau eine Probe
    assert sample_capacity(500) == 500          # Charge: so viele wie Stück
    assert sample_capacity("2.5") == 3          # Bruchmenge: aufgerundet (halbe Probe gibt es nicht)
    assert sample_capacity(0) == 1              # nie null Proben

    src = ast.unparse(ast.parse(pathlib.Path(
        APP / "services" / "inspection.py").read_text(encoding="utf-8")))
    fn = [n for n in ast.walk(ast.parse(src))
          if isinstance(n, ast.FunctionDef) and n.name == "sample_targets"]
    body = ast.unparse(fn[0])
    assert "batch" not in body, "Die Stichproben-Auswahl darf ``kind`` nicht mehr kennen"
    assert "sample_capacity" in body


def test_the_batch_unit_difference_lives_in_exactly_one_module():
    """``Instance.kind`` ist ein **Etikett**, keine Regel.

    Der Unterschied Charge/Einzelteil darf nur dort stehen, wo er *entsteht*
    (``services/serialization.py``: unit → N Instanzen à 1, batch → eine à N). Überall
    sonst zählt die **Menge**. Vorher verzweigte auch die Datenerfassung darauf – und weil
    ihre Bedingung ``len(insts) == 1 and kind == 'batch'`` lautete, war der Fall «zwei
    Chargen» schlicht nicht vorgesehen (eine Probe je Charge statt nach Menge).

    Der Test hält den erreichten Zustand fest: verzweigt wieder ein Fachmodul auf ``kind``,
    ist das eine bewusste Entscheidung – und keine, die unbemerkt einschleicht."""
    allowed = {"services/serialization.py"}
    offenders: list[str] = []
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP).as_posix()
        if rel in allowed:
            continue
        for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#")[0]
            if '.kind == "batch"' in code or ".kind == 'batch'" in code:
                offenders.append(f"{rel}:{num}")
    assert not offenders, (
        "Charge/Einzelteil darf nur services/serialization.py unterscheiden – sonst zählt "
        "die Menge (Instance.quantity):\n  " + "\n  ".join(offenders)
    )


def test_only_sampled_instances_get_a_verdict():
    """**Was nicht beprobt wurde, wird nicht beurteilt.**

    Vorher bekam jede Instanz des Auftrags ein Urteil, und wer nicht in der Stichprobe war,
    fiel über den Default ``False`` durch: eine BESTANDENE 20 %-Stichprobe sperrte die
    übrigen 80 % – sie verschwanden aus FIFO, Bestand und Verfügbarkeit. Reicht eine
    Stichprobe nicht, stuft ``escalate_decision`` auf 100 % hoch; DANN ist jede Instanz
    beprobt und bekommt ihr Urteil."""
    from app.services.inspection import DEFAULT_OK_FIELD, sample_verdicts

    fields = [dict(DEFAULT_OK_FIELD)]
    key = DEFAULT_OK_FIELD["key"]

    # Einzelteile: nur die gezogene Instanz (100000001) steht im Urteil.
    verdicts = sample_verdicts(fields, [{"instance_id": 100000001, "slot": 1, "values": {key: True}}])
    assert verdicts == {100000001: True}
    assert 100000002 not in verdicts, "Eine nicht beprobte Instanz darf kein Urteil bekommen"

    # Charge: mehrere Proben derselben Instanz – bestanden nur, wenn ALLE bestehen.
    charge = [
        {"instance_id": 100000009, "slot": 1, "values": {key: True}},
        {"instance_id": 100000009, "slot": 2, "values": {key: False}},
        {"instance_id": 100000009, "slot": 3, "values": {key: True}},
    ]
    assert sample_verdicts(fields, charge) == {100000009: False}

    # Ohne Proben gibt es kein Urteil (und damit keine Sperre).
    assert sample_verdicts(fields, []) == {}


# ─── Decimal an der Grenze zur Datenbank ─────────────────────────────────────────

def test_every_json_column_survives_a_decimal():
    """**Eine Menge muss in jede JSONB-Spalte passen.**

    Seit den Bruchmengen (Migration ``055``) ist jede Menge ein ``Decimal`` – und
    ``json.dumps`` kann das nicht. Das fällt nicht beim Schreiben des Feldes auf, sondern
    erst beim ``flush``: als ``TypeError`` mitten in der Transaktion, also als **500 auf dem
    ganzen Endpunkt**. Genau so war der Prozessschritt «Ressource» unbenutzbar –
    ``resource_usages.details`` bekam die entnommene Menge als ``Decimal``, und JEDE
    Verbuchung eines Verbrauchs brach ab. Der Event-Strom hatte seine eigene
    Normalisierung, die elf anderen JSONB-Spalten nicht.

    Deshalb hängt die Normalisierung an der **Engine** (``core.database``) und nicht in den
    Schreibern: jede neue JSONB-Spalte erbt den Schutz, ohne dass jemand daran denken muss."""
    import json
    from decimal import Decimal

    from app.core.database import engine, json_safe

    assert engine.dialect._json_serializer is not None, (
        "Die Engine braucht einen Decimal-festen json_serializer – sonst wirft die erste "
        "Menge in einer JSONB-Spalte einen TypeError mitten in der Transaktion.")

    payload = {"picks": [{"quantity": Decimal("2.500"), "into": 100000001}],
               "nested": {"total": Decimal("0.5")}, "plain": "ok", "none": None}
    dumped = json.loads(engine.dialect._json_serializer(payload))
    assert dumped["picks"][0]["quantity"] == 2.5
    assert dumped["nested"]["total"] == 0.5
    assert dumped["plain"] == "ok" and dumped["none"] is None
    # Exaktheit bleibt Sache des Schreibers: wo es auf den Rappen ankommt (Geld,
    # Reservierungen, Standort-Teilmengen), stehen bewusst Strings in der Spalte.
    assert json_safe(Decimal("1.005")) == 1.005


def test_a_returned_quantity_has_no_floor_of_one():
    """**Zurück kommt, was hinausging** – nicht «mindestens eins».

    Die Rückgabe einer ganz verkauften Instanz buchte die Menge über
    ``max(quantity, verkauft, 1)`` zurück. Der feste Boden machte aus einer verkauften
    0.5-kg-Charge bei der Retoure **1 kg**: der Bestand wuchs mit jeder Rückgabe einer
    Bruchmenge. «Mindestens 1» ist eine Aussage über *Stück*, nicht über *Mengen* – dieselbe
    Verwechslung wie oben, nur in der Gegenrichtung."""
    import ast

    src = (APP / "services" / "process.py").read_text(encoding="utf-8")
    # Die Rückbuchung sitzt in der Retoure-Schleife UND ihrem Je-Instanz-Helfer – geprüft
    # wird die Aussage, nicht der Zuschnitt der Funktionen.
    fns = [n for n in ast.walk(ast.parse(src))
           if isinstance(n, ast.FunctionDef) and n.name in ("return_subjects_to_stock", "_restock_one")]
    assert len(fns) == 2, "Retoure-Rückbuchung nicht gefunden"
    body = "".join(ast.unparse(n) for n in fns)
    assert "max(" not in body, (
        "Die zurückgebuchte Menge darf nicht über ein max(…, ONE) laufen – eine Bruchmenge "
        "käme sonst aufgerundet zurück.")
    assert "sold_amounts.get(inst.object_id) or" in body, (
        "Massgeblich ist die beim Verkauf abgebuchte Menge; die Instanz-Menge und die 1 sind "
        "nur Rückfälle für Altdaten.")


def test_a_share_never_exceeds_the_instance():
    """**Was ANDERE halten, gehört nicht mir** (Testnotiz #432).

    ``held_quantity`` beantwortet «wie viel dieser Instanz gehört diesem Auftrag». Ohne
    eigenen Anspruch fiel die Antwort auf die **ganze** Instanz zurück – gedacht für den
    Erzeuger, der sein Erzeugnis ja komplett hält. Sobald aber eine Abweichung 2 einer
    4er-Charge übernahm, hielten Eltern (4, über den Erzeuger-Rückfall) und Abweichung (2,
    über ihren Anspruch) zusammen **6 von 4** – und genau diese 6 standen auf der Kante des
    Flusses.

    Der Rückfall ist jetzt der **Rest**: Instanzmenge minus alle Ansprüche. Das ist dieselbe
    Regel, die ``shares.shares_for`` seit jeher rendert (gehaltene Anteile plus Rest, Summe =
    Instanz) – sie stand nur an zwei Stellen verschieden."""
    from decimal import Decimal

    from app.services.subject import held_quantity

    class _Inst:
        def __init__(self, qty, res):
            self.quantity, self.reservations = Decimal(qty), res

    class _Order:
        def __init__(self, oid):
            self.id = oid

    parent, deviation = _Order(1), _Order(2)
    # Niemand hält etwas: die ganze Instanz gehört dem Erzeuger (unverändert).
    assert held_quantity(parent, _Inst(4, {})) == Decimal(4)
    # Eigener Anspruch schlägt alles (unverändert).
    assert held_quantity(deviation, _Inst(4, {"2": "2"})) == Decimal(2)
    # **Der Fall aus der Notiz**: die Abweichung hält 2, der Erzeuger den Rest – nicht alles.
    inst = _Inst(4, {"2": "2"})
    assert held_quantity(parent, inst) == Decimal(2)
    assert held_quantity(parent, inst) + held_quantity(deviation, inst) == inst.quantity, (
        "Die Summe der Anteile ist die Instanz – nie mehr.")
    # Vollständig vergeben: für den Erzeuger bleibt nichts (kein negativer Rest).
    assert held_quantity(parent, _Inst(4, {"2": "4"})) == Decimal(0)
