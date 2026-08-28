"""**Die Testmatrix als Daten** – Soll steht vor dem Lauf, Ist entsteht dabei.

Warum die Fälle hier als Daten stehen und nicht als Testfunktionen: der Auftrag verlangt
eine Tabelle **Soll/Ist**, nicht «alles grün». Ein Fall ist darum ein Datensatz mit
erwartetem Ergebnis; wer ihn ausführt (pytest oder das Berichts-Skript), ist eine andere
Frage.

**Das Soll wird vor dem Lauf notiert**, nicht aus dem Lauf abgeleitet – sonst prüft der
Test den Code gegen sich selbst.

Gefahren wird über die **echten** Dienstpfade (``process.release``/``confirm_step``), nie
über nachgestellte Zustände: die interessanten Fehler entstehen zwischen den Schritten.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Die Achsen der Matrix (Auftrag §2.2)
# ---------------------------------------------------------------------------

#: A – Herkunft der Stücke
A_NEU, A_LAGER, A_MIX = "neu", "lager", "gemischt"
#: B – Serialisierung
B_EINZEL, B_BATCH = "einzel", "batch"
#: C – Menge
C_1, C_2, C_VIELE = "1", "2", "viele"
#: D – Modultyp
D_ERFASSUNG, D_SCRAP, D_BLOCK = "datenerfassung", "verschrotten", "sperren"
D_VERBRAUCH = "verbrauch"
#: E – Schachtelung
E_KEINE, E_1, E_2, E_3 = "0", "1", "2", "3"
#: F – Rückführung
F_NORMAL, F_GEKAPPT, F_AUTO, F_GEMISCHT = "normal", "gekappt", "auto-gekappt", "gemischt"


@dataclass
class Case:
    """Ein Szenario. ``soll`` ist die **vorher** notierte Erwartung."""

    id: str
    title: str
    axes: dict[str, str]
    soll: dict[str, Any]
    run: Callable[["World"], dict[str, Any]]
    #: Warum dieser Fall unmöglich ist – dann wird er nicht gefahren, sondern ausgewiesen.
    impossible: Optional[str] = None
    #: Worauf der Fall zielt (für den Bericht).
    note: str = ""
    #: **Ein bekannter, noch nicht behobener Befund** (``FINDINGS.md``).
    #:
    #: Das Soll bleibt stehen – es ist die Regel, nicht der Ist-Zustand. Der Fall gilt
    #: darum nicht als bestanden, sondern als **offen**, und die CI wird davon nicht rot.
    #:
    #: **Er kann aber auch nicht verrotten:** hört die Abweichung auf, meldet der Wächter
    #: das als Fehler («der Befund ist behoben – Eintrag entfernen»). Ein stillschweigend
    #: behobener Befund, dessen Markierung stehen bleibt, wäre eine Ausnahme, die niemand
    #: mehr hinterfragt.
    open_finding: Optional[str] = None


@dataclass
class Result:
    case: Case
    ist: dict[str, Any] = field(default_factory=dict)
    #: ``ok`` · ``abweichung`` · ``fehler`` · ``unmöglich`` · ``offen`` · ``behoben``
    verdict: str = "ok"
    error: Optional[str] = None

    @property
    def diffs(self) -> list[str]:
        out = []
        for key, want in self.case.soll.items():
            got = self.ist.get(key, "<fehlt>")
            if got != want:
                out.append(f"{key}: Soll {want!r} · Ist {got!r}")
        return out


# ---------------------------------------------------------------------------
# Die Welt – dünne Bedienung, keine Fachaussage
# ---------------------------------------------------------------------------

class World:
    """Bedienung der echten Dienste. **Keine Regel wird hier nachgebaut.**

    Jede Methode ist ein Aufruf in ``services/`` plus Auflösung von Objektnummern – wenn
    hier eine Fachaussage stünde, prüfte der Test sie gegen sich selbst.
    """

    ONE_POINT = [{"label": "OK", "type": "bool"}]
    GOOD = {"ok": True}
    BAD = {"ok": False}

    def __init__(self, db):
        self.db = db

    # ── Definitionen ────────────────────────────────────────────────────────

    def article(self, *, serialization: str = "unit",
                template: Optional[list[dict[str, Any]]] = None):
        """Ein freigegebener Artikel mit Erzeugungsprozess-Vorlage."""
        from app.models import Article
        from app.services import article_process as tpl, objects as obj

        art = Article(
            object_id=obj.next_object_id(self.db), name="Prüfstück", unit="stk",
            serialization=serialization, status="freigegeben",
        )
        self.db.add(art)
        self.db.flush()
        tpl.create_steps(self.db, art, template or [self.capture()])
        self.db.flush()
        return art

    @staticmethod
    def capture(sample: Optional[dict[str, Any]] = None,
                points: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
        config: dict[str, Any] = {"points": points if points is not None else World.ONE_POINT}
        if sample:
            config["sample"] = sample
        return {"module_type": "datenerfassung", "config": config}

    @staticmethod
    def dispose(mode: str = "scrap", reason: str = "Ausschuss") -> dict[str, Any]:
        return {"module_type": "aussondern", "config": {"mode": mode, "reason": reason}}

    @staticmethod
    def move(target: Optional[int] = None) -> dict[str, Any]:
        """Ein Bewegen-Modul. Ohne Ziel wird es beim Ausführen gescannt."""
        return {"module_type": "bewegen", "config": {"target": target}}

    def holder(self, *, name: str = "Werkbank"):
        """Ein physischer Halter – ein Regal, eine Werkbank, ein Behälter.

        Es ist eine ganz gewöhnliche **Instanz**: kein neuer Datensatztyp, keine
        Whitelist. Sie steht schon da, also braucht sie keinen Erzeugungsprozess –
        erzeugt wird sie hier direkt.
        """
        from app.models import Article
        from app.services import instances as inst_svc, objects as obj

        art = Article(object_id=obj.next_object_id(self.db), name=name, unit="stk",
                      serialization="einzeln", status="freigegeben")
        self.db.add(art)
        self.db.flush()
        made = inst_svc.create_instances(
            self.db, article=art, kind="einzeln", instance_count=1, units_each=1)
        self.db.flush()
        return made[0]

    def put(self, numbers: list[str], target: int) -> None:
        """Stücke an einen Halter legen – über die EINE Schreibstelle."""
        from app.services import instances as inst_svc, places
        places.place(self.db, units=[inst_svc.find_unit(self.db, n) for n in numbers],
                     target=target)
        self.db.flush()

    @staticmethod
    def consume(*lines: tuple[int, int]) -> dict[str, Any]:
        """Ein Verbrauchsmodul – je Zeile **Artikel + Menge pro Einzelinstanz**."""
        return {
            "module_type": "verbrauch",
            "config": {"lines": [{"article": a, "quantity": q} for a, q in lines]},
        }

    # ── Aufträge ────────────────────────────────────────────────────────────

    def release(self, *, lines: list[dict[str, Any]],
                steps: Optional[list[dict[str, Any]]] = None):
        from app.services import process as proc

        order = proc.release(self.db, lines=lines, steps=steps or [], actor_id=None)
        self.db.flush()
        return order

    def produce(self, article, quantity: int):
        """Erzeugungsauftrag – fährt die Vorlage des Artikels."""
        return self.release(lines=[{
            "article_object_id": article.object_id, "quantity": quantity,
            "origin": "neu", "units": [],
        }])

    def take(self, article, numbers: list[str], *, steps: list[dict[str, Any]],
             from_order: Optional[int] = None, returns: bool = True):
        """Lager-Auftrag auf genannte Stücke."""
        return self.release(
            lines=[{
                "article_object_id": article.object_id, "quantity": len(numbers),
                "origin": "lager", "returns": returns,
                "units": [{"number": n, "from_order": from_order} for n in numbers],
            }],
            steps=steps,
        )

    # ── Ausführung ──────────────────────────────────────────────────────────

    def steps(self, order):
        from app.services import process as proc
        return proc.steps_of(self.db, order)

    def work(self, order, step):
        from app.services import process as proc
        return proc.step_work(self.db, order, step)

    def confirm(self, order, step, *, instance: int, values: Optional[dict] = None,
                verification: str = "scan", sources: Optional[list[int]] = None,
                place: Optional[int] = None):
        """Ein Modul für **eine** Instanz bestätigen – mit einem Wertesatz je gezogenem Stück."""
        from app.services import process as proc
        from tests.support import per_unit

        payload = {}
        if proc.step_work(self.db, order, step):
            has_points = bool((step.config or {}).get("points"))
            if has_points:
                payload = per_unit(self.db, order=order, step=step,
                                   instance_object_id=instance,
                                   values=values if values is not None else self.GOOD)
        out = proc.confirm_step(
            self.db, order=order, step_id=step.id, values=payload,
            instance_object_id=instance, verification=verification,
            sources=sources, place=place, actor_id=None,
        )
        self.db.flush()
        return out

    def run_step(self, order, step, *, values: Optional[dict] = None,
                 sources: Optional[list[int]] = None, place: Optional[int] = None):
        """Ein Modul für **alle** wartenden Instanzen bestätigen (ein Vorgang je Instanz)."""
        out = []
        for row in list(self.work(order, step)):
            out.append(self.confirm(order, step, instance=row["instance_object_id"],
                                    values=values, sources=sources, place=place))
        return out

    def run_all(self, order, *, values: Optional[dict] = None):
        """Den ganzen Auftrag durchfahren, Modul für Modul."""
        for step in self.steps(order):
            self.run_step(order, step, values=values)
        return self.status(order)

    def needs(self, order, step) -> list[dict[str, Any]]:
        """Was dieses Modul jetzt braucht — Artikel, Menge, Verfügbarkeit, **Ort** (§4)."""
        from app.services import consumption, process as proc

        return [
            {"artikel": n.article_object_id, "je_stück": n.per_unit,
             "gebraucht": n.required, "verfügbar": n.available, "fehlt": n.missing,
             "hier": n.here, "am_falschen_ort": n.misplaced}
            for n in consumption.needs(
                self.db, step, products=proc.units_before(self.db, order, step))
        ]

    # ── Auskunft ────────────────────────────────────────────────────────────

    def status(self, order) -> str:
        from app.services import process as proc
        return proc.order_status(self.db, order)

    def numbers(self, order) -> list[str]:
        """Alle Stücknummern dieses Auftrags, in Nummernreihenfolge."""
        from app.models import InstanceUnit, OrderUnit
        from app.services import process as proc

        units = (
            self.db.query(InstanceUnit)
            .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
            .filter(OrderUnit.order_id == order.id)
            .order_by(InstanceUnit.id)
            .all()
        )
        got = proc.unit_numbers(self.db, units)
        return [got[u.id] for u in units]

    def unit(self, number: str):
        from app.services.instances import find_unit
        return find_unit(self.db, number)

    def unit_status(self, number: str) -> str:
        unit = self.unit(number)
        return unit.status if unit else "<weg>"

    def states(self, order) -> dict[str, int]:
        """Zustände der Stücke dieses Auftrags, gezählt."""
        out: dict[str, int] = {}
        for n in self.numbers(order):
            s = self.unit_status(n)
            out[s] = out.get(s, 0) + 1
        return out

    def instances(self, order) -> list[int]:
        """Objektnummern der Instanzen, die dieser Auftrag berührt."""
        from app.models import Instance, InstanceUnit, OrderUnit

        rows = (
            self.db.query(Instance.object_id)
            .join(InstanceUnit, InstanceUnit.instance_id == Instance.id)
            .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
            .filter(OrderUnit.order_id == order.id)
            .distinct()
            .all()
        )
        return sorted(int(o) for (o,) in rows)

    def waits(self, order) -> bool:
        """Wartet dieser Auftrag auf mindestens eine Rückführung?"""
        from app.services import process as proc
        return bool(proc.pending_returns(self.db, order))

    def blocked_steps(self, order) -> dict[int, list[int]]:
        from app.services import process as proc
        return proc.pending_returns(self.db, order)

    def lent(self, order) -> int:
        from app.services import process as proc
        return proc.waiting_counts(self.db, [order.id]).get(order.id, 0)

    def is_deviation(self, order) -> bool:
        from app.services import process as proc
        return proc.deviation_flags(self.db, [order.id])[order.id]

    def active_step(self, order):
        from app.services import process as proc
        return proc.active_step_id(self.db, order)

    def graph(self, order):
        from app.services import flow as flow_svc
        return flow_svc.build(self.db, order)

    def problems(self, order) -> list[str]:
        return list(self.graph(order).problems)

    # ── Bestand herstellen ──────────────────────────────────────────────────

    def stock(self, article, quantity: int) -> list[str]:
        """``quantity`` **freie** Stücke: erzeugen und einmal durchlaufen lassen."""
        order = self.produce(article, quantity)
        numbers = self.numbers(order)
        self.run_all(order)
        return numbers


def free_stock(world: World, *, serialization: str = "unit", quantity: int = 1):
    """Artikel + freie Stücke in einem Zug – der häufigste Aufbau."""
    article = world.article(serialization=serialization)
    return article, world.stock(article, quantity)
