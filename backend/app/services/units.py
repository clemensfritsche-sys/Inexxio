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
    x     der **Endzustand**, wenn diese Stücke den Bestand verlassen haben
          (``scrapped`` · ``sold`` · ``consumed``); fehlt = lebendig.
    s     freigegeben – dieses Stück hat sein Prozessziel erreicht.
    t     **seit wann am Lager** – der Zeitpunkt der ERSTEN Freigabe dieses Stücks.

**Die FIFO-Zeit gehört zur Menge, nicht zur Instanz.** Sie war die letzte Grösse, die noch
instanzweit stand (``instances.released_at``) – und damit die letzte, die bei einer Charge
lügen konnte: werden drei Stück heute und eines in vier Wochen frei, trugen alle vier das
Datum von heute. Zustand (``s``/``x``), Menge (``q``), Halter (``o``) und Standort hängen
längst am Stück; die Zeit tut es jetzt auch.

Drei Regeln, und alle drei folgen daraus, dass ``t`` eine **Tatsache über die Vergangenheit**
ist – keine abgeleitete Grösse:

  * **Gesetzt beim ersten Mal** (``mark_released``) und danach **nie** überschrieben. «Seit
    wann liegt es am Lager» meint den Moment, in dem genau dieses Stück freigegeben wurde –
    nicht den Abschluss irgendeines Auftrags.
  * **Eine Retoure setzt die Uhr nicht zurück** (``restore``): ein zurückgenommenes Teil ist
    so alt wie beim ersten Mal. Sonst wäre es das *jüngste* im Lager und ginge als letztes
    hinaus – bei FIFO als Alterungsschutz genau verkehrt.
  * **Altbestand bekommt seine Eröffnungsbilanz** (``ensure``): Stücke ohne ``t`` erben den
    heutigen Stand der Instanz (``released_at``, ersatzweise ``created_at``) – ab dort ist
    die Zeit persistent am Stück, ohne erfundene Historie.

``fifo_since`` ist die Antwort für die Sortierung; ``inventory.fifo_candidates`` liest sie.

**Die Nummer ist eine Identität, keine Position.** Sie wird bei der Entstehung vergeben
und danach **nie** neu verteilt – ein Stück, das einmal ``-3`` war, bleibt ``-3``, auch
wenn ``-1`` und ``-2`` längst verschrottet sind. Darum wird auch nichts nachgezählt: die
höchste je vergebene Nummer steht in ``next``.

**Ein Stück verschwindet nicht, es ändert seinen Zustand** (Testnotiz #549 – dieselbe
Regel, die für die Menge längst gilt, #481). Wer verschrottet, streicht die Nummer nicht
aus der Karte: sie bleibt stehen und trägt ihren Endzustand (``x``). Ein verschrottetes
``…-1`` ist damit weiterhin benennbar – im Instanz-Detail (rot) wie in der Geschichte –
statt aus der Liste zu fallen, als hätte es das Stück nie gegeben. Für **alles Rechnende**
zählt es nicht mehr mit: ``of``/``count``/``total``/``held_quantity`` übergehen es, es sei
denn, man fragt ausdrücklich danach.

**Zuordnung ist tolerant, Buchhaltung ist streng** – dieselbe Haltung wie im Material-
Journal (ADR 007). Alt-Instanzen ohne Einheiten bekommen sie beim ersten Zugriff aus dem
heutigen Stand (``ensure`` – die Eröffnungsbilanz), und ``verify`` prüft, dass Einheiten
und Mengen/Ansprüche nicht auseinanderlaufen. Ein Widerspruch ist ein Bug im Aufrufer,
keine stille Korrektur.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import NamedTuple

from ..models import Instance
from ..models.base import utcnow
from .quantity import ZERO, qty_key, qty_sum, to_qty

#: Ab so vielen Läufen wird zusammengefasst, was ohnehin gleich ist (siehe ``_pack``).
#: Nur eine Aufräum-Grenze – die Nummern selbst gehen dabei nie verloren.
_MAX_RUNS = 400


class Unit(NamedTuple):
    """Ein Stück: seine Nummer, seine Menge, wem es gehört – und ob es noch da ist."""

    number: str                 # "100000101-3"
    index: int                  # 3
    quantity: Decimal
    holder: int | None          # Order.id | None = frei
    state: str | None = None    # scrapped|sold|consumed = hat den Bestand verlassen
    released: bool = False      # hat sein Prozessziel erreicht → passed/in_stock
    since: datetime | None = None   # seit wann am Lager (FIFO-Basis, erste Freigabe)

    @property
    def free(self) -> bool:
        return self.holder is None

    @property
    def gone(self) -> bool:
        return self.state is not None


# ─── Die FIFO-Zeit ────────────────────────────────────────────────────────────

def _stamp(at: datetime | None = None) -> str:
    """Der Zeitpunkt, wie er im Lauf steht – ISO-8601 in UTC (JSON-sicher, sortierbar)."""
    return (at or utcnow()).astimezone(timezone.utc).isoformat()


def _time(raw) -> datetime | None:
    """Der Zeitpunkt eines Laufs als ``datetime`` – tolerant gegenüber Altbestand."""
    if not raw:
        return None
    try:
        val = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return val if val.tzinfo else val.replace(tzinfo=timezone.utc)


def _fallback(inst: Instance) -> datetime | None:
    """Was ein Stück ohne eigenen Zeitpunkt erbt – der heutige Stand der Instanz."""
    got = getattr(inst, "released_at", None) or getattr(inst, "created_at", None)
    if got is None:
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def fifo_since(inst: Instance) -> datetime | None:
    """**Seit wann liegt hier das älteste entnehmbare Stück?** – der FIFO-Schlüssel.

    Sortiert wird je Instanz (eine Zeile im Kandidatenfeld), gemeint ist aber das Stück,
    das als Nächstes hinausginge: das **älteste freie und freigegebene**. Gibt es keines,
    zählt das älteste freigegebene überhaupt; ohne jede Freigabe bleibt es beim Stand der
    Instanz (Altbestand) – tolerant lesen, streng schreiben."""
    free: list[datetime] = []
    any_released: list[datetime] = []
    fb = _fallback(inst)
    for run in _runs(inst):
        if run.get("x") or not run.get("s"):
            continue
        when = _time(run.get("t")) or fb
        if when is None:
            continue
        any_released.append(when)
        if run.get("o") is None:
            free.append(when)
    pool = free or any_released
    return min(pool) if pool else fb


#: Ohne jede Zeitangabe (theoretisch: weder Freigabe noch ``created_at``) sortiert die
#: Instanz nach vorn – sie ist dann die älteste, die wir kennen.
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def fifo_key(inst: Instance) -> datetime:
    """Derselbe Wert wie ``fifo_since``, aber **immer** vergleichbar (zeitzonen-bewusst).

    Sortierschlüssel müssen total sein: ein naives neben einem bewussten ``datetime``
    bringt die Sortierung zum Absturz, nicht bloss in die falsche Reihenfolge."""
    return fifo_since(inst) or _fallback(inst) or _EPOCH


# ─── Lesen ────────────────────────────────────────────────────────────────────

def _runs(inst: Instance) -> list[dict]:
    """Die Läufe der Instanz – als **Kopien**. Leer, wenn noch keine vergeben wurden.

    **Der geladene Wert darf nie verändert werden** (Testnotizen #560/#561/#562). SQLAlchemy
    entscheidet beim Speichern über einen **Vergleich** mit dem geladenen Wert, ob eine
    JSONB-Spalte überhaupt in das UPDATE kommt. Wer die geladenen Dicts an Ort und Stelle
    ändert, ändert damit auch den Vergleichswert – neu und alt sind gleich, die Spalte fällt
    aus dem UPDATE, und die Änderung ist nach dem Commit **spurlos weg**.

    Genau so kam der gemeldete Fall zustande: ``sync`` gab die Stücke eines abgeschlossenen
    Unter-Auftrags frei (``r.pop("o")`` auf den geladenen Läufen), im Speicher stimmte alles –
    und in der Datenbank hielt der Abzweig sein Stück weiter. Die Kante des Eltern-Auftrags
    fand darum kein einziges Stück mehr und zeigte «1 Stk» ohne Nummer.

    Kopien machen die Frage gegenstandslos: der geladene Wert bleibt unberührt, jede Änderung
    ist eine echte Änderung."""
    data = inst.units or {}
    return [dict(r) for r in (data.get("r") or [])]


def label(inst: Instance, index: int) -> str:
    """Die Nummer EINES Stücks – die eine Stelle, die das Format kennt.

    **Ohne Ausnahme.** Ein Einzelteil trägt ``-1`` genauso wie das erste Stück einer
    Charge, und eine nicht zählbare Charge (2.5 kg) ebenso. Eine Sonderregel «bei genau
    einem Stück ohne Zusatz» wäre eine zweite Schreibweise für dieselbe Sache – und jede
    Ansicht müsste sie kennen. Eine Regel, ein Format, überall gleich."""
    return f"{inst.object_id}-{index}"


def of(inst: Instance, *, holder: int | None = ..., limit: int | None = None,
       include_gone: bool = False) -> list[Unit]:
    """Die Einheiten einer Instanz, aufsteigend nach Nummer.

    ``holder`` filtert auf einen Auftrag (``None`` = nur die freien); ohne Angabe kommen
    alle. ``limit`` deckelt die Ausgabe – eine 1000er-Charge soll keine Liste mit 1000
    Chips erzeugen; wie viele es insgesamt sind, sagt ``count``.

    **Ausgeschiedene Stücke kommen nur auf Nachfrage** (``include_gone``): sie tragen ihre
    Nummer weiter, zählen aber zu keiner Menge mehr. Wer rechnet, will sie nicht; wer die
    Geschichte zeigt, schon."""
    out: list[Unit] = []
    for run in _runs(inst):
        if run.get("x") and not include_gone:
            continue
        if holder is not ... and run.get("o") != holder:
            continue
        q = to_qty(run.get("q", 1))
        when = _time(run.get("t")) or (_fallback(inst) if run.get("s") else None)
        for i in range(int(run["a"]), int(run["b"]) + 1):
            out.append(Unit(label(inst, i), i, q, run.get("o"), run.get("x"),
                            bool(run.get("s")), when))
            if limit is not None and len(out) >= limit:
                return out
    return sorted(out, key=lambda u: u.index)


def count(inst: Instance, *, holder: int | None = ..., include_gone: bool = False) -> int:
    """Wie viele Stück – ohne die Liste zu bauen (für «+N weitere»)."""
    return sum(int(r["b"]) - int(r["a"]) + 1 for r in _runs(inst)
               if (include_gone or not r.get("x"))
               and (holder is ... or r.get("o") == holder))


def numbers(inst: Instance, *, holder: int | None = ..., limit: int | None = None) -> list[str]:
    """Nur die Nummern – für Wächter und Protokolle."""
    return [u.number for u in of(inst, holder=holder, limit=limit)]


def rows(inst: Instance, *, holder: int | None = ..., limit: int | None = None,
         names: dict | None = None, include_gone: bool = False, db=None) -> list:
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
    # **Der unbeanspruchte Rest gehört dem Erzeuger, solange er nicht am Lager liegt UND
    # sein Erzeuger noch läuft** – dieselbe eine Regel wie bei den Anteilen
    # (``inventory.rest_owner``). Ohne sie hiesse dasselbe Stück im Detail «frei» und in der
    # Aufteilung «Auftrag …003». Ohne Session (reine Anzeige-Aufrufe) bleibt der Rest frei –
    # tolerant lesen, nie raten.
    rest = rest_owner(db, inst) if db is not None else None
    out = []
    for u in of(inst, holder=holder, limit=limit, include_gone=include_gone):
        # **Ein ausgeschiedenes Stück trägt seinen eigenen Endzustand** (#549) – nicht den
        # Skalar der Instanz: die lebt weiter, es nicht. Und es gehört niemandem mehr.
        if u.gone:
            out.append(InstanceUnit(number=u.number, quantity=float(u.quantity),
                                    quality=q, disposition=u.state))
            continue
        # **Ein AUSDRÜCKLICHER Anspruch gilt immer, der geerbte Rest nur im Prozess**
        # (Testnotiz #625, präzisiert #573/#577). Hier stand «freigegeben heisst frei» für
        # BEIDE Fälle – damit verschwand auch ein Stück, das ein laufender Auftrag
        # ausdrücklich beansprucht: es las sich als «Freigegeben», obwohl es längst in
        # einem Prozess steckt. Der Fehler von #573 war ein anderer: dort zog der
        # **Erzeuger** über den unbeanspruchten Rest (``rest_owner``) längst fertige Stücke
        # wieder an sich. Genau dieser Rückfall bleibt an die Bedingung «noch im Prozess»
        # geknüpft – der Anspruch selbst nicht.
        owner = u.holder if u.holder is not None else (None if u.released else rest)
        o = look.get(owner) if owner is not None else None
        # **Ein freigegebenes Stück sagt es auch dann, wenn seine Geschwister es noch nicht
        # sind** (Notiz #572): der Zustand gehört zur Menge, und eine Charge kann geteilter
        # Meinung sein. Der Instanz-Skalar bleibt die Projektion darüber.
        pq, pd = ("passed", "in_stock") if u.released else (q, d)
        out.append(InstanceUnit(
            number=u.number, quantity=float(u.quantity), quality=pq, disposition=pd,
            # **Seit wann am Lager** – die FIFO-Basis dieses Stücks (Testnotiz #631).
            # Sie steht dort, wo sie gilt: am Stück, nicht an der Instanz.
            in_stock_since=u.since if u.released else None,
            order_object_id=(o[0] if o else None), order_name=(o[1] if o else None),
            reason=(o[2] if o else None)))
    return out


def place(rows: list, slices: list) -> list:
    """**Jedem Stück seinen Standort geben** (Testnotiz #605) – EINE Logik für Chargen wie
    für Einzelteile.

    Die Instanz trägt ihre Standorte als **Mengen** (``instances.locations``: 990 @ Eingang,
    10 @ Band A) – genau wie die Ansprüche. Und genau wie dort wird daraus «welches Stück»,
    indem die Mengen der Reihe nach auf die aufsteigenden Nummern verteilt werden. Liegt
    alles an einem Ort, bekommt es jedes Stück; ein Einzelteil ist damit kein Sonderfall,
    sondern eine Charge mit einem Stück.

    Ein **ausgeschiedenes** Stück bleibt ohne Standort: Ausschuss hat keinen Halter mehr,
    sein Endzustand IST die Wo-Aussage (Migration 070)."""
    if not slices:
        return rows
    queue = [(d, float(d.get("quantity") or 0)) for d in slices]
    idx = 0
    for row in rows:
        if row.disposition in ("scrapped", "sold", "consumed"):
            continue
        need = float(row.quantity or 0)
        while idx < len(queue) and queue[idx][1] <= 0:
            idx += 1
        if idx >= len(queue):
            break
        d, left = queue[idx]
        row.location_label = d.get("location_label")
        row.location_object_id = d.get("location_id")
        queue[idx] = (d, left - need)
    return rows


def owned_by(inst: Instance, order_id: int, db=None) -> list[Unit]:
    """**Die Stücke, die diesem Auftrag gehören** – Anspruch ODER unbeanspruchter Rest.

    Dieselbe eine Regel wie bei den Anteilen (``inventory.rest_owner``): solange die Instanz
    nicht am Lager liegt, gehört der unbeanspruchte Rest ihrem Erzeuger. Ohne das hielte ein
    Erzeugungsauftrag «nichts», sobald ein Abzweig seine Ansprüche zurückgegeben hat."""
    from .inventory import rest_owner
    rest = rest_owner(db, inst) if db is not None else None
    # **Der geerbte Rest gilt nur im Prozess, der ausdrückliche Anspruch immer** (#573/#577
    # präzisiert durch #625): ohne die erste Hälfte zog ein Erzeugungsauftrag längst fertige
    # Stücke wieder an sich («…-1 war schon lange freigegeben»); ohne die zweite verlöre ein
    # Auftrag die Stücke, die er sich ausdrücklich vom Lager geholt hat.
    return [u for u in of(inst)
            if (u.holder == order_id if u.holder is not None
                else (not u.released and rest == order_id))]


def mark_released(inst: Instance, indices, at: datetime | None = None) -> Decimal:
    """**Diese Stücke haben ihr Prozessziel erreicht** – sie sind freigegeben (Notiz #572).

    Der Zustand einer Instanz war bisher genau EIN Paar Skalare für die ganze Menge. Bei
    einer Charge ist das zu grob: hat ein Abzweig sein Stück fertig durch den Prozess
    gebracht, während die drei anderen noch in laufenden Aufträgen stecken, ist «Im Prozess»
    für dieses eine Stück schlicht falsch – und für die anderen drei richtig. Beides ist
    wahr, nur eben nicht über dieselbe Menge.

    Darum steht die Freigabe dort, wo auch der Endzustand steht: **am Stück** (``s``). Die
    Instanz-Skalare bleiben die **Projektion** darüber (``all_released``) und wechseln erst,
    wenn alle lebenden Stücke frei sind. Das ist bewusst konservativ: ``in_stock_clauses``
    (FIFO, Bestand, Verfügbarkeit) liest weiterhin die Skalare und wird damit **nicht**
    ungenauer als vorher – eine teilweise freigegebene Charge ist wie bisher noch nicht
    entnehmbar, sie sagt es jetzt bloss ehrlich.

    Liefert die freigegebene Menge."""
    want = {int(i) for i in indices}
    if not want:
        return ZERO
    runs, freed = _runs(inst), ZERO
    stamp = _stamp(at)
    out: list[dict] = []
    for run in runs:
        if run.get("x") or run.get("s"):
            out.append(run)
            continue
        q = to_qty(run.get("q", 1))
        for a, b, hit in _slice(int(run["a"]), int(run["b"]), want):
            piece = {**run, "a": a, "b": b}
            if hit:
                # **Hier entsteht die FIFO-Zeit** – und nur hier: ein Stück ist «seit» dem
                # Moment am Lager, in dem es freigegeben wurde. Danach wird sie nie wieder
                # angefasst (auch eine Retoure setzt sie nicht zurück).
                piece["s"] = 1
                piece.setdefault("t", stamp)
                freed = qty_sum([freed, q * (b - a + 1)])
            out.append(piece)
    _write(inst, out, _next(inst))
    sync_state(inst)
    return freed


def _slice(a: int, b: int, want: set[int]):
    """Einen Lauf in Abschnitte zerlegen: getroffen / nicht getroffen, in Nummernfolge."""
    start, cur = a, (a in want)
    for i in range(a + 1, b + 2):
        hit = i in want if i <= b else not cur
        if hit != cur or i > b:
            yield start, i - 1, cur
            start, cur = i, hit
    return


def all_released(inst: Instance) -> bool:
    """Sind ALLE lebenden Stücke freigegeben?"""
    live = [r for r in _runs(inst) if not r.get("x")]
    return bool(live) and all(r.get("s") for r in live)


#: Welcher Endzustand gewinnt, wenn ALLE Stücke ausgeschieden sind – der endgültigste
#: zuerst. Eine Charge, von der 3 verkauft und 1 verschrottet wurde, ist als Datensatz
#: «verschrottet»: das ist die Aussage, die man nicht übersehen darf.
_TERMINAL_RANK = ("scrapped", "consumed", "sold")


def project(inst: Instance) -> tuple[str, str] | None:
    """**Der Zustand der INSTANZ ist die Projektion über ihre Stücke** (Testnotiz #604).

    Ein Datensatz trägt genau einen Zustand, eine Charge aber viele: von vier Stück kann
    eines verschrottet, zwei freigegeben und eines noch im Prozess sein. Alle drei Aussagen
    sind wahr – nur nicht über dieselbe Menge. Die Frage ist also nicht «welcher stimmt»,
    sondern **welcher gehört auf den Datensatz**.

    Die Rangfolge folgt dem, wonach man sucht:

        1. **≥ 1 Stück freigegeben → «Freigegeben · am Lager».** Sonst fände FIFO die Charge
           nicht, obwohl entnehmbare Stücke darin liegen – genau der Punkt des Nutzers. Dass
           nicht alles frei ist, sagt die **Menge**: ``free_quantity`` zählt Stücke, nicht
           den Skalar, und gibt darum nie ein Stück heraus, das noch im Prozess ist.
        2. **sonst ≥ 1 Stück lebendig → «Im Prozess».** Es ist da, nur noch nicht verwendbar.
        3. **sonst → der Endzustand**, der am meisten zählt (``_TERMINAL_RANK``).

    **Gesperrt gewinnt über allem** (solange etwas lebt): eine Sperre ist eine Aussage über
    die ganze Instanz («darf man das verwenden?»), kein Zustand eines einzelnen Stücks.

    Vorher wurde der Skalar **einmal zugewiesen** – in dem Moment, in dem der letzte lebende
    Anteil freigegeben wurde (``all_released``). Wurde später ein Geschwister-Stück
    verschrottet, kippte die Bedingung nachträglich, aber niemand rechnete sie neu: die
    Instanz blieb für immer «Im Prozess», obwohl im Detail jedes Stück «Freigegeben» zeigte
    (Testnotizen #601/#602). Als **Projektion** kann das nicht mehr auseinanderlaufen.

    ``None`` = keine Stücke bekannt (Altbestand) → der Skalar bleibt, wie er ist."""
    runs = _runs(inst)
    if not runs:
        return None
    live = [r for r in runs if not r.get("x")]
    if not live:
        states = {r.get("x") for r in runs}
        for name in _TERMINAL_RANK:
            if name in states:
                return (getattr(inst, "quality", None) or "pending", name)
        return None
    if (getattr(inst, "quality", None) or "") == "blocked":
        return ("blocked", "in_stock" if any(r.get("s") for r in live) else "in_process")
    if any(r.get("s") for r in live):
        return ("passed", "in_stock")
    return ("pending", "in_process")


def sync_state(inst: Instance) -> None:
    """Die Projektion auf die Instanz-Skalare anwenden – nach **jeder** Änderung an den
    Stücken. Das ist die EINE Stelle, an der ``quality``/``disposition`` aus den Stücken
    entstehen; wer sie sonst noch setzt, setzt eine Absicht (gesperrt, verkauft), die die
    Projektion beim nächsten Mal respektiert."""
    got = project(inst)
    if got is None:
        return
    inst.quality, inst.disposition = got


def free_quantity(inst: Instance) -> Decimal:
    """**Wie viel ist an dieser Instanz wirklich entnehmbar?** – freigegeben UND unbeansprucht.

    Seit der Skalar eine Projektion ist (#604), sagt «am Lager» nur noch «hier liegt etwas
    Entnehmbares», nicht «alles davon». Die Menge muss die Wahrheit tragen, sonst gäbe FIFO
    Stücke heraus, die noch mitten im Prozess sind. Gezählt wird darum je Stück.

    Ohne Stück-Daten (Altbestand) gibt es nichts zu verfeinern – dann gilt weiter die
    Mengen-Rechnung des Aufrufers. Ebenso, wenn eine Instanz am Lager liegt, ihre Stücke
    aber (noch) keine Freigabe-Marke tragen: **tolerant lesen, streng schreiben** – der
    Skalar ist dann die einzige Aussage, die es gibt."""
    runs = _runs(inst)
    if not runs:
        return to_qty(inst.quantity)
    live = [r for r in runs if not r.get("x")]
    if live and not any(r.get("s") for r in live) and (
            getattr(inst, "disposition", None) or "") == "in_stock":
        return qty_sum(to_qty(r.get("q", 1)) * (int(r["b"]) - int(r["a"]) + 1)
                       for r in live if r.get("o") is None)
    return qty_sum(to_qty(r.get("q", 1)) * (int(r["b"]) - int(r["a"]) + 1)
                   for r in runs
                   if not r.get("x") and r.get("s") and r.get("o") is None)


def covers(inst: Instance, indices, quantity) -> bool:
    """**Trägt diese Nummernliste die ganze Menge?** – der Ehrlichkeits-Test für Altbestand.

    Aufgezeichnete Nummern sind die Wahrheit über die Vergangenheit (#543/#544) – aber nur,
    wenn sie **vollständig** sind. Buchungen von vor Migration `100` tragen gar keine, und die
    Entstehung nannte ihre Stücke erst ab Testnotiz #567; ein Kontostand, der aus solchen
    Buchungen aufgebaut wird, kennt einen Teil der Menge nicht. Eine halbe Liste ist schlimmer
    als keine – sie sieht vollständig aus («4 Stk × …-2, -3, -4»). Passt die Summe nicht, fällt
    die Anzeige auf die heutige Karte zurück, also auf das Verhalten von vorher."""
    known = {u.index: u.quantity for u in of(inst, include_gone=True)}
    have = qty_sum(known.get(int(i), to_qty(1)) for i in indices)
    return have == to_qty(quantity)


def rows_for(inst: Instance, indices, *, limit: int | None = None) -> list:
    """**Genau diese Stücke als Zeilen** – für aufgezeichnete Nummern aus dem Journal.

    Die Stücke müssen dafür nicht (mehr) existieren: eine verschrottete ``…-1`` behält ihre
    Nummer in der Geschichte, auch wenn sie aus der Karte entwertet ist. Menge und Zustand
    kommen aus der Instanz, soweit sie das Stück noch kennt – sonst aus ihrem Skalar."""
    from ..schemas.instance import InstanceUnit
    known = {u.index: u for u in of(inst, include_gone=True)}
    q, d = inst.quality or "pending", inst.disposition or "in_process"
    out = []
    for i in sorted(int(n) for n in indices):
        u = known.get(i)
        # **Der Hover sagt dasselbe wie die Pille** (Testnotiz #574): ein freigegebenes
        # Stück ist freigegeben – auch hier. Vorher kam der Zustand aus dem Instanz-Skalar,
        # und der bleibt bei einer teilweise freigegebenen Charge bewusst «Im Prozess»;
        # die Kante zeigte also grün und ihre Hover-Karte gelb.
        if u and u.gone:
            pq, pd = q, u.state
        elif u and u.released:
            pq, pd = "passed", "in_stock"
        else:
            pq, pd = q, d
        out.append(InstanceUnit(number=label(inst, i),
                                quantity=float(u.quantity if u else 1),
                                quality=pq, disposition=pd))
        if limit is not None and len(out) >= limit:
            break
    return out


def total(inst: Instance) -> Decimal:
    """Die Summe der **lebenden** Einheiten – muss ``instance.quantity`` entsprechen."""
    return qty_sum(to_qty(r.get("q", 1)) * (int(r["b"]) - int(r["a"]) + 1)
                   for r in _runs(inst) if not r.get("x"))


# ─── Schreiben – EINE Stelle ──────────────────────────────────────────────────

def _write(inst: Instance, runs: list[dict], nxt: int) -> None:
    """Läufe zurückschreiben: sortiert, verdichtet, ohne Leerläufe."""
    clean = [r for r in runs if int(r["b"]) >= int(r["a"])]
    clean.sort(key=lambda r: int(r["a"]))
    inst.units = {"r": _pack(clean), "next": nxt} if clean else {"r": [], "next": nxt}


def _same(a: dict, b: dict) -> bool:
    """Zwei Läufe beschreiben dasselbe – dann dürfen sie einer werden.

    **Auch die FIFO-Zeit gehört dazu**: zwei Stücke, die an verschiedenen Tagen ans Lager
    kamen, beschreiben nicht dasselbe – sie zusammenzufassen hiesse, das ältere um sein
    Datum zu bringen."""
    return (a.get("o") == b.get("o") and a.get("x") == b.get("x")
            and bool(a.get("s")) == bool(b.get("s"))
            and a.get("t") == b.get("t")
            and qty_key(a.get("q", 1)) == qty_key(b.get("q", 1)))


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
    Stücke, wie ihre Menge hergibt, verteilt auf die Halter ihrer Ansprüche – und **liegt
    sie am Lager, sind ihre Stücke freigegeben** (sonst wäre eine Alt-Instanz nach der
    Eröffnung schlagartig nicht mehr entnehmbar, weil ``free_quantity`` je Stück zählt).
    Freigegebene Stücke erben dabei die **FIFO-Zeit der Instanz** (``released_at``,
    ersatzweise ``created_at``) – ab dort steht sie persistent am Stück, ohne dass jemals
    eine Zeit erfunden würde. Ab dort ist die Zuordnung vollständig. Idempotent.

    **Zwei Eröffnungen, eine Regel.** Auch eine Instanz, die ihre Nummern schon hat, kann
    aus einer Zeit stammen, in der es die Freigabe je Stück noch nicht gab: sie liegt am
    Lager, aber kein einziges Stück trägt die Marke. Das ist genau der gemeldete Fall –
    beim Verschrotten EINES Stücks zog ``sync_state`` die Projektion nach, fand nirgends
    eine Freigabe und stufte die ganze Charge auf «Im Prozess» zurück; aus dem Nichts
    standen drei freigegebene Stücke wieder in Arbeit. Die Antwort ist dieselbe wie oben:
    was am Lager liegt, IST freigegeben – die Marke wird nachgetragen, nicht der Zustand
    weggeworfen. Tolerant lesen, streng schreiben."""
    if not _runs(inst) and (inst.units or {}).get("r") is None:
        create(inst, inst.quantity)
        _open(inst)
        for key, val in (inst.reservations or {}).items():
            _assign(inst, int(key), to_qty(val))
        return
    _open(inst)


def _open(inst: Instance) -> None:
    """Die Eröffnungsbilanz der **Freigabe**: liegt die Instanz am Lager, trägt aber kein
    lebendes Stück eine Marke, erben alle die Freigabe und die FIFO-Zeit der Instanz."""
    if (getattr(inst, "disposition", None) or "") != "in_stock":
        return
    live = [r for r in _runs(inst) if not r.get("x")]
    if not live or any(r.get("s") for r in live):
        return
    old = _fallback(inst)
    seed = {"s": 1, **({"t": _stamp(old)} if old else {})}
    _write(inst, [r if r.get("x") else {**r, **seed} for r in _runs(inst)], _next(inst))


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


def _pick(runs: list[dict], want: Decimal, accept, *, newest: bool = False,
          gone: bool = False) -> tuple[list, Decimal]:
    """**Welche Stücke** ``want`` (Menge) aus den akzeptierten Läufen ausmachen – die EINE
    Traversierung für jeden Wechsel (zuordnen · freigeben · ausscheiden · zurückholen).

    ``newest`` nimmt am **oberen** Ende: was zuletzt kam, geht zuerst. ``gone`` wählt die
    Seite: lebende Stücke (Standard) oder ausgeschiedene (nur die Retoure holt von dort
    zurück). Liefert ``[(erste_nummer, anzahl)]`` und die tatsächlich erreichte Menge."""
    got, hit = ZERO, []
    for r in (reversed(runs) if newest else runs):
        if got >= want or bool(r.get("x")) is not gone or not accept(r):
            continue
        q = to_qty(r.get("q", 1))
        if q <= 0:
            continue
        need = int(((want - got) / q).to_integral_value(rounding="ROUND_CEILING"))
        take = min(need, int(r["b"]) - int(r["a"]) + 1)
        if take <= 0:
            continue
        hit.append((int(r["b"]) - take + 1 if newest else int(r["a"]), take))
        got += q * take
    return hit, got


def _apply(runs: list[dict], hit: list, change) -> list[dict]:
    """Die gewählten Nummernbereiche herausschneiden und ändern (Halter setzen/lösen,
    Endzustand vermerken). Die Nummern selbst bleiben dabei immer, wo sie sind."""
    for start, take in hit:
        runs = _split(_split(runs, start), start + take)
        for r in runs:
            if int(r["a"]) >= start and int(r["b"]) < start + take:
                change(r)
    return runs


def _assign(inst: Instance, order_id: int, qty, *, source: int | None = None) -> Decimal:
    """``qty`` an Stücken diesem Auftrag zuordnen – **der genannte Anteil zuerst**, dann
    freie, dann fremde.

    **Die Stücke folgen der Menge** (Testnotiz #553). Wer einen Anteil anklickt, sagt: *aus
    diesem Auftrag*. Die Mengen-Seite hält sich längst daran (``reservation.enforce`` – der
    genannte Anteil verliert immer); die Stücke taten es nicht, sie griffen zuerst in den
    freien Topf. Der ist aber nicht herrenlos: solange die Instanz nicht am Lager liegt,
    gehört er ihrem Erzeuger (``inventory.rest_owner``). Genau daraus entstand der
    Tausch – eine Abweichung der Abweichung nahm dem **Hauptauftrag** sein Stück, und
    beim Nachziehen der Mengen bekam er dafür irgendein anderes zurück.

    **Genommen wird von unten** – die niedrigsten Nummern zuerst (Testnotiz #558). Das ist
    die Ordnung, in der Stücke überall vergeben werden (``create`` zählt ab 1, ``drop``
    greift am Anfang der Läufe); eine Ausnahme nur für den genannten Anteil hätte dieselbe
    Geste an zwei Stellen verschieden aussehen lassen."""
    want = to_qty(qty) - held_quantity(inst, order_id)
    if want <= 0:
        return ZERO
    runs, moved = _runs(inst), ZERO
    ranks = ([lambda r: r.get("o") == source] if source is not None else []) + [
        lambda r: r.get("o") is None,
        lambda r: r.get("o") not in (None, order_id)]
    for accept in ranks:
        if moved >= want:
            break
        hit, got = _pick(runs, want - moved, accept)
        runs = _apply(runs, hit, lambda r: r.update(o=order_id))
        moved += got
    _write(inst, runs, _next(inst))
    return moved


def _next(inst: Instance) -> int:
    return int((inst.units or {}).get("next") or 1)


def held_quantity(inst: Instance, order_id: int) -> Decimal:
    """Wie viel Menge dieser Auftrag an Stücken hält (Gegenstück zur Reservierung)."""
    return qty_sum(to_qty(r.get("q", 1)) * (int(r["b"]) - int(r["a"]) + 1)
                   for r in _runs(inst) if r.get("o") == order_id and not r.get("x"))


def sync(inst: Instance, *, taker: int | None = None, source: int | None = None) -> None:
    """**Die Zuordnung der Ansprüche nachziehen** – der eine Aufruf nach jeder Änderung an
    ``instances.reservations``.

    Die Ansprüche sagen, *wie viel* wem gehört; hier wird daraus, *welche Stücke*. Wer zu
    viel hält, gibt seine höchsten Nummern ab; wer zu wenig hält, bekommt dazu. So bleiben
    Menge und Nummern zwangsläufig dieselbe Aussage.

    ``taker``/``source`` sagen, **wer** sich gerade etwas nimmt und **von wem** – dieselbe
    Angabe, mit der die Mengen-Seite arbeitet (``orders.pick_sources`` →
    ``reservation.enforce``). Ohne sie müssten die Stücke raten, und geraten wurde bisher
    zugunsten des freien Topfes – der aber dem Erzeuger gehört (Testnotiz #553)."""
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
            _assign(inst, oid, want, source=source if oid == taker else None)


def _release(inst: Instance, order_id: int, qty) -> None:
    """``qty`` an Stücken dieses Auftrags wieder freigeben (die höchsten Nummern zuerst –
    was zuletzt kam, geht zuerst zurück)."""
    runs = _runs(inst)
    hit, _ = _pick(runs, to_qty(qty), lambda r: r.get("o") == order_id, newest=True)
    _write(inst, _apply(runs, hit, lambda r: r.pop("o", None)), _next(inst))


def drop(inst: Instance, qty, *, state: str, by_order_id: int | None = None) -> list[int]:
    """Stücke **verlassen** den Bestand (verbaut · verkauft · verschrottet) – ihre Nummern
    werden nie wieder vergeben. Liefert die betroffenen Nummern.

    Genommen wird bevorzugt bei dem, der sie beansprucht hat: wer verschrottet, verschrottet
    sein eigenes Stück, nicht das des Nachbarn.

    **Die Nummer bleibt stehen** und trägt ab jetzt ihren Endzustand (Testnotiz #549). Sie
    aus der Karte zu streichen hiess, dass ein Stück aus dem Nichts verschwindet – im
    Instanz-Detail wie auf jeder vergangenen Kante des Flusses, die es noch getragen hat."""
    ensure(inst)
    runs, gone, remaining = _runs(inst), [], to_qty(qty)
    # Rangfolge: eigenes Stück ≻ freies ≻ fremdes.
    ranks = ([lambda r: r.get("o") == by_order_id] if by_order_id else []) + [
        lambda r: r.get("o") is None, lambda r: True]
    for accept in ranks:
        if remaining <= 0:
            break
        hit, got = _pick(runs, remaining, accept)
        for start, take in hit:
            gone.extend(range(start, start + take))
        runs = _apply(runs, hit, lambda r: (r.pop("o", None), r.update(x=state)))
        remaining -= got
    _write(inst, runs, _next(inst))
    sync_state(inst)
    return sorted(gone)


def restore(inst: Instance, qty, *, state: str) -> list[int]:
    """Ausgeschiedene Stücke **kehren zurück** – die Gegenrichtung von ``drop``.

    Es gibt genau einen legitimen Weg aus einem Endzustand heraus: die **Retoure** holt aus
    dem «verkauft»-Topf zurück (dieselbe Ausnahme, die das Material-Journal als
    ``src_disposition='sold'`` kennt). Verschrottet und verbaut kommen nie zurück.

    Zurück kommen die **niedrigsten** Nummern zuerst – dieselbe Reihenfolge, in der sie
    gegangen sind. Liefert die zurückgeholten Nummern für die Buchung."""
    ensure(inst)
    runs = _runs(inst)
    hit, _ = _pick(runs, to_qty(qty), lambda r: r.get("x") == state, gone=True)
    back = [i for start, take in hit for i in range(start, start + take)]
    _write(inst, _apply(runs, hit, lambda r: r.pop("x", None)), _next(inst))
    sync_state(inst)
    return sorted(back)


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
