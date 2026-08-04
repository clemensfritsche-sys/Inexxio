"""**Jedes Stück hat eine eigene Nummer** – die Einheiten einer Instanz.

Bisher war eine Instanz eine **Menge**: «100000101 · 4 Stk». Wer wissen wollte, welches
der vier Stück gerade in einer Abweichung steckt, bekam keine Antwort – es gab die Frage
gar nicht, nur Summen. Genau daraus kam die wiederkehrende Fehlerklasse: zwei Halter,
eine Zahl, und keine Möglichkeit zu sagen, *welches* Stück gemeint ist.

Jetzt trägt jedes Stück eine eigene, physisch etikettierbare Nummer::

    100000101-1   100000101-2   100000101-3   100000101-4

**Ohne neue Datensätze.** Die Einheiten wohnen in der Instanz (``instances.units``), nicht
in eigenen Zeilen – exakt wie ``reservations`` («wer beansprucht wie viel») und
``locations`` («wo liegt wie viel»), nur eine Ebene genauer: hier steht **welches Stück**.

**Gespeichert werden Läufe, nicht Zeilen.** Eine Charge von 1000 Schrauben ist EIN Lauf
``1–1000``; nimmt eine Abweichung ein Stück, sind es zwei. So bleibt der Normalfall (alles
gleich) eine einzige kurze Zeile, und die Nummern gibt es trotzdem alle::

    units = [{"a": 1, "b": 970, "q": "1"},
             {"a": 971, "b": 1000, "q": "1", "o": 123}]

    a, b  Nummernbereich (einschliesslich). a == b → genau ein Stück.
    q     Menge **je Stück** – fast immer "1". Eine Charge, die sich nicht zählen lässt
          (2.5 kg), ist EIN Stück mit q = "2.5": Kilogramm bekommen keine Nummern.
    o     der Auftrag, der diese Stücke hält (fehlt = frei).

**Die Nummer ist eine Identität, keine Position.** Sie wird bei der Entstehung vergeben
und danach **nie** neu verteilt – ein Stück, das einmal ``-3`` war, bleibt ``-3``, auch
wenn ``-1`` und ``-2`` längst verschrottet sind. Darum wird auch nichts nachgezählt: die
höchste je vergebene Nummer steht in ``next``.

**Zuordnung ist tolerant, Buchhaltung ist streng** – dieselbe Haltung wie im Material-
Journal (ADR 007). Alt-Instanzen ohne Einheiten bekommen sie beim ersten Zugriff aus dem
heutigen Stand (``ensure`` – die Eröffnungsbilanz), und ``verify`` prüft, dass Einheiten
und Mengen/Ansprüche nicht auseinanderlaufen. Ein Widerspruch ist ein Bug im Aufrufer,
keine stille Korrektur.
"""

from decimal import Decimal
from typing import NamedTuple

from ..models import Instance
from .quantity import ZERO, qty_key, qty_sum, to_qty

#: Ab so vielen Läufen wird zusammengefasst, was ohnehin gleich ist (siehe ``_pack``).
#: Nur eine Aufräum-Grenze – die Nummern selbst gehen dabei nie verloren.
_MAX_RUNS = 400


class Unit(NamedTuple):
    """Ein Stück: seine Nummer, seine Menge und wem es gehört."""

    number: str                 # "100000101-3"
    index: int                  # 3
    quantity: Decimal
    holder: int | None          # Order.id | None = frei

    @property
    def free(self) -> bool:
        return self.holder is None


# ─── Lesen ────────────────────────────────────────────────────────────────────

def _runs(inst: Instance) -> list[dict]:
    """Die Läufe der Instanz (roh). Leer, wenn noch keine vergeben wurden."""
    data = inst.units or {}
    return list(data.get("r") or [])


def label(inst: Instance, index: int) -> str:
    """Die Nummer EINES Stücks – die eine Stelle, die das Format kennt.

    **Ohne Ausnahme.** Ein Einzelteil trägt ``-1`` genauso wie das erste Stück einer
    Charge, und eine nicht zählbare Charge (2.5 kg) ebenso. Eine Sonderregel «bei genau
    einem Stück ohne Zusatz» wäre eine zweite Schreibweise für dieselbe Sache – und jede
    Ansicht müsste sie kennen. Eine Regel, ein Format, überall gleich."""
    return f"{inst.object_id}-{index}"


def of(inst: Instance, *, holder: int | None = ..., limit: int | None = None) -> list[Unit]:
    """Die Einheiten einer Instanz, aufsteigend nach Nummer.

    ``holder`` filtert auf einen Auftrag (``None`` = nur die freien); ohne Angabe kommen
    alle. ``limit`` deckelt die Ausgabe – eine 1000er-Charge soll keine Liste mit 1000
    Chips erzeugen; wie viele es insgesamt sind, sagt ``count``."""
    out: list[Unit] = []
    for run in _runs(inst):
        if holder is not ... and run.get("o") != holder:
            continue
        q = to_qty(run.get("q", 1))
        for i in range(int(run["a"]), int(run["b"]) + 1):
            out.append(Unit(label(inst, i), i, q, run.get("o")))
            if limit is not None and len(out) >= limit:
                return out
    return out


def count(inst: Instance, *, holder: int | None = ...) -> int:
    """Wie viele Stück – ohne die Liste zu bauen (für «+N weitere»)."""
    return sum(int(r["b"]) - int(r["a"]) + 1 for r in _runs(inst)
               if holder is ... or r.get("o") == holder)


def numbers(inst: Instance, *, holder: int | None = ..., limit: int | None = None) -> list[str]:
    """Nur die Nummern – für Wächter und Protokolle."""
    return [u.number for u in of(inst, holder=holder, limit=limit)]


def rows(inst: Instance, *, holder: int | None = ..., limit: int | None = None,
         names: dict | None = None) -> list:
    """**Die Stücke als Zeilen** – Nummer · Menge · Zustand · Halter, die EINE Form, in der
    ein Teil überall genannt wird (Testnotizen #531/#532).

    Der Zustand kommt aus den beiden Instanz-Achsen; ob ein Stück **gebunden** ist, sagt
    sein Halter. ``names`` ist die bereits aufgelöste Auftrags-Tabelle
    (``{db_id: (objektnr, name, grund)}`` aus ``shares._orders``) – so bleibt es EINE
    Abfrage je Aufruf statt einer je Stück."""
    from ..schemas.instance import InstanceUnit
    from .inventory import rest_owner
    q, d = inst.quality or "pending", inst.disposition or "in_process"
    look = names or {}
    # **Der unbeanspruchte Rest gehört dem Erzeuger, solange er nicht am Lager liegt** –
    # dieselbe eine Regel wie bei den Anteilen (``inventory.rest_owner``). Ohne sie hiesse
    # dasselbe Stück im Detail «frei» und in der Aufteilung «Auftrag …003».
    rest = rest_owner(inst)
    out = []
    for u in of(inst, holder=holder, limit=limit):
        owner = u.holder if u.holder is not None else rest
        o = look.get(owner) if owner is not None else None
        out.append(InstanceUnit(
            number=u.number, quantity=float(u.quantity), quality=q, disposition=d,
            order_object_id=(o[0] if o else None), order_name=(o[1] if o else None),
            reason=(o[2] if o else None)))
    return out


def owned_by(inst: Instance, order_id: int) -> list[Unit]:
    """**Die Stücke, die diesem Auftrag gehören** – Anspruch ODER unbeanspruchter Rest.

    Dieselbe eine Regel wie bei den Anteilen (``inventory.rest_owner``): solange die Instanz
    nicht am Lager liegt, gehört der unbeanspruchte Rest ihrem Erzeuger. Ohne das hielte ein
    Erzeugungsauftrag «nichts», sobald ein Abzweig seine Ansprüche zurückgegeben hat."""
    from .inventory import rest_owner
    rest = rest_owner(inst)
    return [u for u in of(inst)
            if (u.holder if u.holder is not None else rest) == order_id]


def rows_for(inst: Instance, indices, *, limit: int | None = None) -> list:
    """**Genau diese Stücke als Zeilen** – für aufgezeichnete Nummern aus dem Journal.

    Die Stücke müssen dafür nicht (mehr) existieren: eine verschrottete ``…-1`` behält ihre
    Nummer in der Geschichte, auch wenn sie aus der Karte entwertet ist. Menge und Zustand
    kommen aus der Instanz, soweit sie das Stück noch kennt – sonst aus ihrem Skalar."""
    from ..schemas.instance import InstanceUnit
    known = {u.index: u for u in of(inst)}
    q, d = inst.quality or "pending", inst.disposition or "in_process"
    out = []
    for i in sorted(int(n) for n in indices):
        u = known.get(i)
        out.append(InstanceUnit(number=label(inst, i),
                                quantity=float(u.quantity if u else 1),
                                quality=q, disposition=d))
        if limit is not None and len(out) >= limit:
            break
    return out


def total(inst: Instance) -> Decimal:
    """Die Summe der Einheiten-Mengen – muss ``instance.quantity`` entsprechen."""
    return qty_sum(to_qty(r.get("q", 1)) * (int(r["b"]) - int(r["a"]) + 1) for r in _runs(inst))


# ─── Schreiben – EINE Stelle ──────────────────────────────────────────────────

def _write(inst: Instance, runs: list[dict], nxt: int) -> None:
    """Läufe zurückschreiben: sortiert, verdichtet, ohne Leerläufe."""
    clean = [r for r in runs if int(r["b"]) >= int(r["a"])]
    clean.sort(key=lambda r: int(r["a"]))
    inst.units = {"r": _pack(clean), "next": nxt} if clean else {"r": [], "next": nxt}


def _same(a: dict, b: dict) -> bool:
    """Zwei Läufe beschreiben dasselbe – dann dürfen sie einer werden."""
    return a.get("o") == b.get("o") and qty_key(a.get("q", 1)) == qty_key(b.get("q", 1))


def _pack(runs: list[dict]) -> list[dict]:
    """Benachbarte, gleiche Läufe verschmelzen – der Normalfall bleibt EINE Zeile.

    Zusammengefasst wird nur, was **lückenlos** aneinandergrenzt: ``1–3`` und ``4–7``
    werden ``1–7``, ``1–3`` und ``5–7`` bleiben getrennt. Die Nummern ändern sich dabei
    nie – es ist reine Schreibweise."""
    out: list[dict] = []
    for run in runs:
        if out and _same(out[-1], run) and int(out[-1]["b"]) + 1 == int(run["a"]):
            out[-1] = {**out[-1], "b": int(run["b"])}
        else:
            out.append(dict(run))
    if len(out) > _MAX_RUNS:
        # Notbremse: mehr Läufe als sinnvoll (jedes zweite Stück anders). Die Nummern
        # bleiben, nur die Feinheit der Zuordnung geht verloren – besser als eine Instanz,
        # die niemand mehr laden kann.
        out = out[:_MAX_RUNS]
    return out


def create(inst: Instance, quantity, *, per_unit=None) -> None:
    """Bei der **Entstehung** die Nummern vergeben – ``-1`` bis ``-N``.

    ``per_unit`` ist die Menge je Stück (Standard 1). Ist die Gesamtmenge nicht in ganze
    Stücke teilbar (2.5 kg), entsteht **ein** Stück mit der ganzen Menge: Kilogramm bekommen
    keine laufenden Nummern, und ein halbes Stück gibt es nicht."""
    total_qty = to_qty(quantity)
    if total_qty <= 0:
        _write(inst, [], 1)
        return
    step = to_qty(per_unit) if per_unit is not None else Decimal(1)
    n = total_qty / step if step > 0 else Decimal(1)
    if step <= 0 or n != n.to_integral_value():
        # Nicht zählbar → ein Stück, das die ganze Menge trägt.
        _write(inst, [{"a": 1, "b": 1, "q": qty_key(total_qty)}], 2)
        return
    cnt = int(n)
    _write(inst, [{"a": 1, "b": cnt, "q": qty_key(step)}], cnt + 1)


def ensure(inst: Instance) -> None:
    """**Eröffnungsbilanz** für eine Instanz ohne Nummern (Altbestand).

    Sie bekommt keine erfundene Historie, sondern genau ihren heutigen Stand: so viele
    Stücke, wie ihre Menge hergibt, verteilt auf die Halter ihrer Ansprüche. Ab dort ist
    die Zuordnung vollständig. Idempotent."""
    if _runs(inst) or (inst.units or {}).get("r") is not None:
        return
    create(inst, inst.quantity)
    for key, val in (inst.reservations or {}).items():
        _assign(inst, int(key), to_qty(val))


# ─── Zuordnung: welche Stücke gehören wem ─────────────────────────────────────

def _split(runs: list[dict], at: int) -> list[dict]:
    """Einen Lauf so aufteilen, dass ``at`` der Anfang eines Laufs ist."""
    out: list[dict] = []
    for r in runs:
        a, b = int(r["a"]), int(r["b"])
        if a < at <= b:
            out.append({**r, "b": at - 1})
            out.append({**r, "a": at})
        else:
            out.append(dict(r))
    return out


def _take_units(runs: list[dict], want: Decimal, pick) -> tuple[list[dict], Decimal]:
    """``want`` (Menge) aus den Läufen nehmen, die ``pick`` akzeptiert – ergibt die
    Nummern, die wechseln. Liefert die betroffenen Läufe und die tatsächliche Menge."""
    got, hit = ZERO, []
    for r in runs:
        if got >= want or not pick(r):
            continue
        q = to_qty(r.get("q", 1))
        if q <= 0:
            continue
        need = int(((want - got) / q).to_integral_value(rounding="ROUND_CEILING"))
        take = min(need, int(r["b"]) - int(r["a"]) + 1)
        if take <= 0:
            continue
        hit.append((r, take))
        got += q * take
    return hit, got


def _assign(inst: Instance, order_id: int, qty) -> Decimal:
    """``qty`` an Stücken diesem Auftrag zuordnen – **freie zuerst**, dann fremde.

    Fremde nur, soweit nötig: wer sich einen Anteil nimmt, den ein anderer hielt, nimmt
    genau so viele Stücke, wie ihm fehlen (dieselbe Rangfolge wie ``shares.losses``)."""
    want = to_qty(qty) - held_quantity(inst, order_id)
    if want <= 0:
        return ZERO
    runs = _runs(inst)
    moved = ZERO
    for accept in (lambda r: r.get("o") is None,
                   lambda r: r.get("o") not in (None, order_id)):
        if moved >= want:
            break
        hit, _ = _take_units(runs, want - moved, accept)
        for run, take in hit:
            a = int(run["a"])
            runs = _split(runs, a + take)
            for r in runs:
                if int(r["a"]) >= a and int(r["b"]) < a + take:
                    r["o"] = order_id
            moved += to_qty(run.get("q", 1)) * take
    _write(inst, runs, _next(inst))
    return moved


def _next(inst: Instance) -> int:
    return int((inst.units or {}).get("next") or 1)


def held_quantity(inst: Instance, order_id: int) -> Decimal:
    """Wie viel Menge dieser Auftrag an Stücken hält (Gegenstück zur Reservierung)."""
    return qty_sum(to_qty(r.get("q", 1)) * (int(r["b"]) - int(r["a"]) + 1)
                   for r in _runs(inst) if r.get("o") == order_id)


def sync(inst: Instance) -> None:
    """**Die Zuordnung der Ansprüche nachziehen** – der eine Aufruf nach jeder Änderung an
    ``instances.reservations``.

    Die Ansprüche sagen, *wie viel* wem gehört; hier wird daraus, *welche Stücke*. Freie
    werden bevorzugt vergeben, und wem etwas genommen wurde, verliert genau so viele
    Stücke. So bleiben Menge und Nummern zwangsläufig dieselbe Aussage."""
    ensure(inst)
    claims = {int(k): to_qty(v) for k, v in (inst.reservations or {}).items()}
    runs = _runs(inst)
    # 1. Wer nichts (mehr) beansprucht, gibt seine Stücke frei.
    for r in runs:
        if r.get("o") is not None and claims.get(int(r["o"]), ZERO) <= 0:
            r.pop("o", None)
    _write(inst, runs, _next(inst))
    # 2. Wer zu viel hält, gibt der Reihe nach ab; wer zu wenig hält, bekommt dazu.
    for oid, want in sorted(claims.items(), key=lambda kv: -kv[1]):
        have = held_quantity(inst, oid)
        if have > want:
            _release(inst, oid, have - want)
    for oid, want in sorted(claims.items(), key=lambda kv: -kv[1]):
        if held_quantity(inst, oid) < want:
            _assign(inst, oid, want)


def _release(inst: Instance, order_id: int, qty) -> None:
    """``qty`` an Stücken dieses Auftrags wieder freigeben (die höchsten Nummern zuerst –
    was zuletzt kam, geht zuerst zurück)."""
    runs = list(reversed(_runs(inst)))
    hit, _ = _take_units(runs, to_qty(qty), lambda r: r.get("o") == order_id)
    runs = _runs(inst)
    for run, take in hit:
        b = int(run["b"])
        runs = _split(runs, b - take + 1)
        for r in runs:
            if int(r["a"]) > b - take and int(r["b"]) <= b:
                r.pop("o", None)
    _write(inst, runs, _next(inst))


def drop(inst: Instance, qty, *, by_order_id: int | None = None) -> list[str]:
    """Stücke **verlassen** die Instanz (verbaut · verkauft · verschrottet) – ihre Nummern
    werden nie wieder vergeben. Liefert die betroffenen Nummern.

    Genommen wird bevorzugt bei dem, der sie beansprucht hat: wer verschrottet, verschrottet
    sein eigenes Stück, nicht das des Nachbarn."""
    ensure(inst)
    runs = _runs(inst)
    gone: list[str] = []
    remaining = to_qty(qty)
    # Rangfolge: eigenes Stück ≻ freies ≻ fremdes.
    order = ([lambda r: r.get("o") == by_order_id] if by_order_id else []) + [
        lambda r: r.get("o") is None, lambda r: True]
    for accept in order:
        if remaining <= 0:
            break
        hit, _ = _take_units(runs, remaining, accept)
        for run, take in hit:
            a = int(run["a"])
            runs = _split(runs, a + take)
            keep = []
            for r in runs:
                if int(r["a"]) >= a and int(r["b"]) < a + take:
                    gone.extend(label(inst, i)
                                for i in range(int(r["a"]), int(r["b"]) + 1))
                    remaining -= to_qty(r.get("q", 1)) * (int(r["b"]) - int(r["a"]) + 1)
                else:
                    keep.append(r)
            runs = keep
    _write(inst, runs, _next(inst))
    return gone


def verify(inst: Instance) -> list[str]:
    """**Laufen Nummern und Mengen auseinander?** – dieselbe Rolle wie
    ``ledger.verify_instance``: sie korrigiert nichts, sie zeigt.

    Ein Befund hier ist ein Bug im Aufrufer (irgendwo wurde eine Menge geändert, ohne die
    Stücke nachzuziehen), keine Kontokorruption."""
    out: list[str] = []
    if not _runs(inst):
        return out
    if total(inst) != to_qty(inst.quantity):
        out.append(f"Summe der Stücke {total(inst)} ≠ Menge {to_qty(inst.quantity)}")
    for key, val in (inst.reservations or {}).items():
        want, have = to_qty(val), held_quantity(inst, int(key))
        if want != have:
            out.append(f"Auftrag {key}: beansprucht {want}, hält aber {have} an Stücken")
    seen: set[int] = set()
    for r in _runs(inst):
        rng = set(range(int(r["a"]), int(r["b"]) + 1))
        if rng & seen:
            out.append(f"Nummern doppelt vergeben: {sorted(rng & seen)[:5]}")
        seen |= rng
    return out
