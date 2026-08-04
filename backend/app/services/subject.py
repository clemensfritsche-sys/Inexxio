"""Das **Subjekt** eines Auftrags – die Instanzen, auf die er wirkt.

Die Subjektart wird aus der **Gestalt des Auftrags abgeleitet** (kein Modus-Flag):

  • **produce** – Artikel + Menge, KEINE eigenen Schritte → der Auftrag fährt den
    Prozess des Artikels und ERZEUGT neue Instanzen.
  • **stock**   – eigene Schritte ohne vorgewählte Instanzen → das Subjekt wird per
    Artikel + Menge **FIFO ab Lager** allokiert (z. B. Verkauf über den Shop).
  • **chosen**  – ausgewählte, vorhandene Instanzen (``subject_of_order_id`` bei der
    Anlage gesetzt) → genau diese sind das Subjekt (Abweichung, gezielter Verkauf).

Das Subjekt wird bei der **Freigabe** hergestellt und – beim Bestands-Zugriff (stock/
chosen) – zugleich für genau diesen Auftrag **reserviert** (kein Doppelverkauf/-verbrauch).
Enthält der Ablauf einen Verkauf, verlassen die Subjekte bei Abschluss den Bestand
(``sold``, siehe ``process._finalize_subjects``); sonst bleibt der Verbleib unverändert.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import Instance, InstanceOrderLink, Order
from .admin import log_audit
from .events import emit
from . import inventory
from .inventory import allocate, fifo_candidates
from .order_lines import lines_for
from .processes import order_custom_steps
from .quantity import ZERO, to_qty
from .reservation import enforce, free_qty, reserve, reserved_for
from .serialization import create_instances_for_order


def pick_source(order: Order, inst) -> int | None:
    """**Wessen Anteil greift dieser Auftrag an dieser Instanz?** – die eine Nachschlagestelle.

    Die Auswahl hat es beim Klick festgehalten (``orders.pick_sources``); ohne Eintrag war
    der Anteil **frei** und es verliert niemand etwas. Damit muss die Freigabe nicht mehr
    raten, wen sie kürzt (siehe ``reservation.enforce``)."""
    src = (order.pick_sources or {}).get(str(inst.object_id))
    return int(src) if src is not None else None


def enforce_pick(db: Session, order: Order, inst) -> None:
    """Den Anspruch dieses Auftrags an dieser Instanz **scharf machen** – und den Vorgang
    festhalten, falls dabei jemand etwas verliert.

    **Der Wechsel ist die Geschichte.** Dass Instanz X ursprünglich Auftrag A zugeteilt war
    und nun Auftrag B gehört, sieht man später sonst nirgends – am Ende steht nur das
    Ergebnis. Die Spur ist kein neues Feld, sondern der **Event-Strom**, und sie hängt am
    **verlierenden** Auftrag: dort will man wissen, warum plötzlich etwas fehlt. Für den
    FIFO-Fall gilt exakt dasselbe wie für die Hand-Auswahl – eine Regel, nicht zwei.

    **Der genannte Anteil wird dabei verbraucht.** ``orders.pick_sources`` ist eine Angabe
    des **Entwurfs** («welche Zeile wurde geklickt»); mit der Freigabe hat sie ihre Wirkung
    getan. Sie danach stehen zu lassen wäre eine geladene Waffe: seit der genannte Anteil
    unbedingt verliert (#394), würde ein zweiter Durchlauf ihn ein zweites Mal kürzen. So
    ist die Einmaligkeit **konstruktiv** statt erhofft – die Spur bleibt im Event-Strom."""
    src = pick_source(order, inst)
    taken = enforce(inst, order.id, src)
    if src is not None:
        rest = {k: v for k, v in (order.pick_sources or {}).items() if k != str(inst.object_id)}
        order.pick_sources = rest or None
    if taken <= 0 or src is None:
        return
    holder = db.query(Order).filter(Order.id == src).first()
    if holder is None:
        return
    emit(db, "order.share_taken", object_type="order", object_id=holder.object_id,
         payload={"instance": inst.object_id, "quantity": float(taken),
                  "to_order": order.object_id, "article_id": inst.article_id,
                  "step_id": _blocked_step(db, holder, inst.article_id)})


def _blocked_step(db: Session, order: Order, article_id: int | None) -> int | None:
    """Der Schritt des verlierenden Auftrags, an dem der Verlust auffällt (für die Anzeige
    im Ablauf). Ohne passenden Schritt gehört die Spur dem Auftrag selbst."""
    from . import process
    return process.blocked_step_for_article(db, order, article_id) if article_id else None


def record_link(db: Session, instance_object_id: int | None, order_id: int,
                quantity: Decimal | None = None) -> None:
    """Verarbeitung einer Instanz durch einen Auftrag **dauerhaft** festhalten (idempotent) –
    unabhängig von späteren Bindungen/Reservierungen (siehe ``InstanceOrderLink``).

    ``quantity``: **wie viel** der Auftrag übernommen hat. Die Reservierung wird bei
    Abschluss gelöst; ohne diese Zahl wäre danach nicht mehr beantwortbar, wie viel je
    hineinging – und genau das zeigt der Fluss an seinen Kanten (Notiz #413). Wird die
    Menge nachgereicht (zweiter Aufruf mit Wert), füllt sie eine noch leere Zeile."""
    if not instance_object_id:
        return
    row = (
        db.query(InstanceOrderLink)
        .filter(InstanceOrderLink.instance_object_id == instance_object_id,
                InstanceOrderLink.order_id == order_id)
        .first()
    )
    if row is None:
        db.add(InstanceOrderLink(instance_object_id=instance_object_id, order_id=order_id,
                                 quantity=quantity))
        # Journal (ADR 007): «übernommen» – der Auftrag nimmt die Menge in seine Obhut.
        # Nur beim ERSTEN Mal (die Zeile ist idempotent, die Buchung soll es auch sein);
        # der Erzeuger übernimmt nicht (er hält seit «created»).
        from . import ledger
        inst = db.query(Instance).filter(Instance.object_id == instance_object_id).first()
        if inst is not None and inst.order_id != order_id:
            ledger.post(db, inst, quantity if quantity is not None else inst.quantity,
                        kind="taken", holder=order_id, src_holder="?")
    elif quantity is not None and row.quantity is None:
        row.quantity = quantity


def held_quantity(order: Order, inst) -> Decimal:
    """**Wie viel dieser Instanz gehört diesem Auftrag?** – die EINE Antwort.

    Eine Instanz ist eine **Menge**, und ein Auftrag hat fast nie die ganze: von einer
    Charge à 4 gehören ihm vielleicht 2 (``instances.reservations``). Wer stattdessen
    ``inst.quantity`` nimmt, rechnet mit fremdem Bestand – daraus entstand «Prüfumfang:
    4 von 2 Stück» (Testnotiz #399), und dieselbe Verwechslung ist die wiederkehrende
    Fehlerklasse rund um Chargen.

    Ohne eigenen Anspruch gehört ihm der **unbeanspruchte Rest** – als Erzeuger
    (``Instance.order_id``) oder als fixiertes Subjekt. «Rest» heisst dabei wirklich Rest:
    was gerade ANDERE halten, gehört nicht ihm. Die frühere Antwort «dann eben die ganze
    Instanz» zählte fremde Anteile mit, und sobald eine Abweichung 2 einer 4er-Charge
    übernommen hatte, hielten Eltern (4) und Abweichung (2) zusammen **6 von 4**
    (Testnotiz #432). Dieselbe Regel steht in ``shares.shares_for``: gehaltene Anteile plus
    Rest, und die Summe ist die Instanz. Rein (schreibt nicht)."""
    qty = reserved_for(inst, order.id)
    if qty > 0:
        return qty
    claimed = sum((to_qty(v) for v in (inst.reservations or {}).values()), ZERO)
    return max(to_qty(inst.quantity) - claimed, ZERO)


def give_back(db: Session, sub: Order, parent: Order, inst: Instance,
              need: dict | None = None) -> Decimal:
    """**Die Ausleihe endet – und das sind ZWEI Fragen, nicht eine** (Testnotiz #505).

    * **Buchung** («wo ist das Material?»): was der Unter-Auftrag noch hält, geht **immer**
      an den Verleiher zurück – auch an einen **Erzeuger**. Der hält seine Instanz zwar über
      ``Instance.order_id`` und braucht dafür keine Reservierung; das Journal aber kennt nur
      Buchungen. Ohne Rückgabe bliebe die Menge für immer in der Obhut des Unter-Auftrags,
      und die Achse des Eltern zeigte sie unterhalb der Teilung nicht mehr – exakt der
      gemeldete Befund («die Instanz hängt noch im Abweichungsauftrag»).
    * **Plan** («wer beansprucht es?»): reserviert wird nur, was der Verleiher noch braucht.
      Ein **Erzeuger** braucht nichts (sein Bestand ist über ``order_id`` gesichert), und wer
      inzwischen «Ersetzen» gewählt hat, ebenso wenig – der Rest bleibt unreserviert und wird
      beim Abschluss frei (Notiz #403).

    Genau diese zwei Fragen waren in EINER Bedingung verschmolzen (``inst.order_id ==
    parent.id`` → gar nichts tun), und weil die planerische Antwort dort «nichts» lautet,
    unterblieb auch die Buchung.

    ``need`` = die offene Fehlmenge je Artikel (wird fortgeschrieben); ``None`` = «gib den
    Anspruch vollständig zurück» (Verwerfen-Tür: die Auswahl wird zurückgenommen).
    Liefert die zurückgegebene Menge. Committet NICHT."""
    from . import ledger, units as U
    from .reservation import release as release_reservation, reserve
    held = reserved_for(inst, sub.id)
    if held <= 0 or (inst.disposition or "") in TERMINAL_DISPOSITIONS:
        return ZERO
    # **Welche Stücke zurückgehen – JETZT festhalten** (Testnotizen #543/#544): gleich hat
    # der Unter-Auftrag seinen Anspruch abgegeben, dann weiss es niemand mehr. Die Nummern
    # gehören in die Buchung, sonst zeigt die Vergangenheit später alles, was der Empfänger
    # gerade hält.
    moved = [u.index for u in U.of(inst, holder=sub.id)]
    release_reservation(inst, sub.id)      # die Bindung des Unter-Auftrags endet hier
    if inst.order_id != parent.id:
        gap = held if need is None else need.get(inst.article_id, ZERO)
        take = min(held, gap)
        if take > 0:
            reserve(inst, parent.id, take)
            if need is not None:
                need[inst.article_id] = gap - take
    ledger.post(db, inst, held, kind="returned", holder=parent.id, src_holder=sub.id,
                units=moved)
    return held


def return_borrowed(db: Session, sub: Order) -> None:
    """**Ein Unter-Auftrag mit festem Subjekt LEIHT – am Ende gibt er zurück** (Notiz #401).

    Abweichung, Retoure und Bereitstellung beschaffen nichts; sie nehmen dem Auftrag, an dem
    die Stücke hingen, etwas ab und geben es hinterher wieder. Solange sie laufen, fehlt es
    dort – **die Unterdeckung IST die Ausleihe**. Sind sie durch, kehrt es zurück; sonst
    behielte der Verleiher seine Fehlmenge für immer, obwohl nichts verloren ging: eine
    erfolgreich abgeschlossene Abweichung verlangte am Eltern eine Entscheidung über ein
    Stück, das längst wieder da war.

    Was den Bestand **verlassen** hat (verschrottet/verkauft/verbaut), kehrt nicht zurück –
    dort ist die Fehlmenge des Verleihers ehrlich. Ein **Erzeuger** als Verleiher bekommt die
    Menge sehr wohl zurück (die BUCHUNG gilt immer), braucht dafür aber keine Reservierung –
    er hält über ``Instance.order_id``; die Trennung steht in ``give_back`` (#505).

    **Zurück geht es an den nächsten LAUFENDEN Verleiher der Kette** (``lender_of``, Notiz
    #404): Auftrag → Abweichung → Abweichung. Wurde die mittlere abgebrochen (ihr blieb
    nichts, also ist sie gegenstandslos), darf das Stück nicht dort hängenbleiben – es kehrt
    dorthin zurück, wo es ursprünglich herkam, und der Hauptauftrag läuft weiter.

    **Und nur so viel, wie dort noch fehlt.** Hat der Verleiher inzwischen «Ersetzen»
    gewählt, ist sein Bedarf gedeckt; das zurückkommende Stück wäre dann Überschuss und
    bliebe für ihn reserviert liegen, ohne dass er es braucht (Notiz #403). Was er nicht
    mehr braucht, geht in den freien Bestand.

    Dieselbe Rückgabe vollzieht ``deviation.detach_sub_order`` beim Verwerfen – zwei Türen,
    EINE Regel (``give_back``). Committet NICHT."""
    from . import process
    parent = lender_of(db, sub)
    if parent is None:
        return
    need = process.subject_shortfalls(db, parent)
    for inst in order_instances(db, sub):
        give_back(db, sub, parent, inst, need)


def lender_of(db: Session, sub: Order) -> Order | None:
    """**Wem gehört das Geliehene?** – der nächste noch LAUFENDE Auftrag der Eltern-Kette.

    Ein Unter-Auftrag mit festem Subjekt hat sein Material von seinem Eltern. Ist der selbst
    ein Unter-Auftrag und inzwischen **abgebrochen** (ihm blieb nichts, also ist er
    gegenstandslos), gehört das Stück dem nächsten darüber. Ohne diesen Durchgriff blieb es
    beim Toten hängen und wurde schlicht frei – der Hauptauftrag ruhte weiter, obwohl seine
    Ware längst zurück war (Notiz #404).

    Zyklensicher; ``None``, wenn niemand mehr läuft. Rein (schreibt nicht)."""
    if not is_fixed_subject(sub):
        return None
    seen: set[int] = {sub.id}
    cur = sub
    while cur is not None and cur.parent_order_id:
        cur = db.query(Order).filter(Order.object_id == cur.parent_order_id).first()
        if cur is None or cur.id in seen:
            return None
        seen.add(cur.id)
        if cur.status == "released":
            return cur
    return None


def chosen_subjects(db: Session, order: Order, article_id: int | None = None) -> list[Instance]:
    """Die bei der Anlage ausgewählten Subjekt-Instanzen (Bestands-Auftrag). Mit
    ``article_id`` nur die einer Position eines **Mehrpositionen**-Auftrags (mehrere
    Artikel können unter demselben Auftrag fixiert sein)."""
    q = db.query(Instance).filter(Instance.subject_of_order_id == order.id, Instance.is_active == True)
    if article_id is not None:
        q = q.filter(Instance.article_id == article_id)
    return q.order_by(Instance.object_id).all()


def is_deviation(order: Order) -> bool:
    """Abweichung = Unter-Auftrag mit ``reason='deviation'`` (Reklamation/Fehler/Nacharbeit/
    Abbruch-Folgeauftrag). Wirkt auf bereits «in der Hand» befindliche Instanzen des Eltern-
    Auftrags – ohne Lager-FIFO/-Reservierung. Ein **Nachschub**-Unter-Auftrag (``reason=
    'supply'``) ist KEINE Abweichung: er produziert/beschafft neuen Bestand und läuft wie ein
    ganz normaler Produktionsauftrag (subject_kind ``produce``)."""
    return getattr(order, "reason", None) == "deviation"


def is_return(order: Order) -> bool:
    """Retoure/Erstattung = Auftrag mit ``reason='return'`` (Subjekt = **verkaufte** Instanzen
    eines Original-Verkaufs, ``parent_order_id``). Festes Subjekt wie eine Abweichung: KEIN
    Lager-FIFO/-Reservierung; pausiert den Eltern NICHT (der Verkauf ist abgeschlossen). Wird
    wie ein normaler Auftrag angelegt (verkaufte Instanzen wählen) und komponiert bestehende
    Module: **Bewegung** (Ware zurück ins Lager → sold→in_stock bei Abschluss) + **Rückerstattung**
    (``refund`` = Verkauf im Kredit-Modus, Geld zurück) + optional Prüfung/Verschrottung."""
    return getattr(order, "reason", None) == "return"


# Die drei Arten, die sich aus der **Instanz-Auswahl** ergeben. Es gibt keinen vierten
# Weg und keinen Schalter: WAS man wählt, sagt WAS es ist.
PICK_NORMAL, PICK_RETURN, PICK_DEVIATION = None, "return", "deviation"


def classify_pick(order: Order, insts: list, wanted: dict | None = None,
                  sources: dict | None = None) -> str | None:
    """**Die Auswahl bestimmt die Art des Auftrags** – EINE Regel, drei Ausgänge.

    Ein Auftrag und ein Abweichungsauftrag sind dasselbe; der Unterschied ist ein **Tag**,
    und dieses Tag wird nicht angeklickt, sondern **abgeleitet** – genau wie die Retoure es
    seit jeher tut:

        alle frei am Lager           → normaler Auftrag   (kein Tag)
        alle verkauft                → Retoure            (Geld zurück, Original = Eltern)
        mindestens eine **gebunden** → Abweichung         (in Arbeit / reserviert / gesperrt)

    «Gebunden» heisst: die Instanz existiert, ist aber gerade nicht frei verfügbar – sie
    steckt in einem Prozess, ist für einen anderen Auftrag reserviert oder gesperrt. Auf so
    etwas zuzugreifen KANN nur eine Abweichung sein; darum ist das Tag keine Frage, sondern
    die Folge.

    ``wanted`` = beanspruchte Teilmenge je Instanz-Objektnummer (fehlt sie, die ganze
    Instanz); ``sources`` = der jeweils **genannte** Halter. Rein (schreibt nicht)."""
    if not insts:
        return PICK_NORMAL
    if any((i.disposition or "") == "sold" for i in insts):
        return PICK_RETURN
    if any(is_bound(order, i, (wanted or {}).get(i.object_id),
                    (sources or {}).get(i.object_id)) for i in insts):
        return PICK_DEVIATION
    return PICK_NORMAL


def is_bound(order: Order, inst, want=None, source_id: int | None = None) -> bool:
    """Ist dieses Stück **gebunden** – also für diesen Auftrag nicht frei verfügbar?

    Gebunden heisst: nicht (mehr) frei am Lager (in Arbeit, verbaut, gesperrt) ODER die
    freie Menge deckt **die gewünschte Menge** nicht. Was dieser Auftrag selbst reserviert
    hat, zählt als frei – er greift ja auf sein eigenes zu.

    **Wer den Anteil eines anderen Auftrags nennt, greift Gebundenes an** – unabhängig
    davon, ob daneben noch etwas frei liegt (``source_id``, Testnotiz #394). Das ist die
    Kehrseite davon, dass der genannte Anteil bei der Freigabe unbedingt verliert
    (``reservation.enforce``): wer einem laufenden Auftrag etwas wegnimmt, macht damit eine
    Abweichung, auch wenn er das freie Stück daneben hätte haben können.

    ``want`` ist die beanspruchte Teilmenge; ohne Angabe die GANZE Instanz (unverändertes
    Verhalten). Die Menge gehört in die Frage, seit eine Auswahl Teilmengen tragen darf:
    von einer 5er-Charge, bei der 2 fremdreserviert sind, ist ein Zugriff auf 3 Stück ein
    ganz gewöhnlicher Bedarf – erst der Zugriff auf 4 ist eine Abweichung.

    EINE Stelle, zwei Nutzer: sie entscheidet, ob eine Auswahl eine Abweichung ist
    (``classify_pick``), und sie verhindert, dass freie und gebundene Stücke im selben
    Auftrag landen (``routers/orders``). Rein (schreibt nicht)."""
    from .inventory import is_in_stock
    from .quantity import to_qty
    from .reservation import free_qty, reserved_for
    if source_id is not None and source_id != order.id:
        return True
    if not is_in_stock(inst):
        return True
    need = to_qty(inst.quantity) if want is None else to_qty(want)
    return free_qty(inst) + reserved_for(inst, order.id) < need


def holding_orders(db: Session, inst, exclude_id: int | None = None) -> list[Order]:
    """**Welche laufenden Aufträge haben dieses Stück gerade in der Hand?**

    Drei Wege, es zu halten – und alle drei zählen:

    * er hat es als **Subjekt** gebunden (``subject_of_order_id``),
    * er hat es **erzeugt** (``order_id``),
    * er hat einen **Anspruch** darauf (``instances.reservations``).

    Der dritte ist der wichtigste und fehlte: sobald ein Entwurf die Subjekt-Bindung an sich
    zieht, ist der Auftrag, der das Stück tatsächlich gedeckt hat, nur noch über seinen
    Anspruch zu finden. Ohne ihn fand die Freigabe niemanden, dem sie etwas wegnimmt – und
    fragte darum auch nicht (gefunden im Praxis-Durchlauf zu Testnotiz #370).

    Rein (schreibt nicht); ``exclude_id`` blendet den fragenden Auftrag aus."""
    ids: list[int] = []
    for oid in (inst.subject_of_order_id, inst.order_id, *[int(k) for k in (inst.reservations or {})]):
        if oid and oid != exclude_id and oid not in ids:
            ids.append(oid)
    if not ids:
        return []
    rows = {
        o.id: o for o in db.query(Order).filter(
            Order.id.in_(ids), Order.is_active == True, Order.status == "released").all()
    }
    return [rows[i] for i in ids if i in rows]


def holding_order(db: Session, inst) -> Order | None:
    """Der **erste** laufende Auftrag, der dieses Stück hält – oder ``None``.

    Die Klammer zwischen Auftrag und Abweichung ist die Instanz; also wird auch der
    Eltern-Auftrag einer Abweichung daraus **abgeleitet** statt eingegeben. Läuft keiner
    mehr (das Stück liegt fertig am Lager), gibt es keinen Eltern – eine Abweichung darf
    auch allein stehen (späte Reklamation)."""
    found = holding_orders(db, inst)
    return found[0] if found else None


def is_provisioning(order: Order) -> bool:
    """Bereitstellung = Unter-Auftrag mit ``reason='provisioning'`` (``services/provisioning.py``).

    Bringt genau die Instanzen, die ein Schritt des Eltern-Auftrags braucht, an dessen
    Bereitstellungsort. Festes Subjekt wie Abweichung/Retoure: das Material existiert
    bereits, es liegt nur am falschen Ort – es gibt nichts zu produzieren, zu reservieren
    oder als Fehlmenge zu melden (das wäre der Nachschub, ``reason='supply'``)."""
    return getattr(order, "reason", None) == "provisioning"


def is_fixed_subject(order: Order) -> bool:
    """Unter-Auftrag, dessen Subjekt bereits FESTSTEHT (gewählte, vorhandene Instanzen) –
    Abweichung, Retoure ODER Bereitstellung. Kein Lager-Zugriff, keine Fehlmengen-Ableitung."""
    return is_deviation(order) or is_return(order) or is_provisioning(order)


def subject_kind(db: Session, order: Order) -> str:
    """Abgeleitete Subjektart (Artikel ist immer der Anker) – KEIN Modus-Flag, KEINE
    Quellen-Übersteuerung:

    ``produce`` – der Auftrag bringt Bestand **herein** und ERZEUGT neue Instanzen. Das
      gilt für KEINE eigenen Schritte (der Auftrag fährt den Artikel-Prozess) **ebenso wie
      für eigene Schritte, die Bestand hereinbringen** – Beschaffung/Ressource haben in der
      Registry die Subjekt-Rolle ``PRODUCE``. Es wird NIE vorhandener Bestand vorausgesetzt.
    ``stock``   – eigene Schritte, die auf **vorhandenen** Bestand zugreifen (Verkauf →
      ``STOCK``) bzw. bestehende Instanzen bearbeiten (Bewegung/Prüfung/Verschrottung →
      ``INSTANCE``): ``quantity`` Stück, FIFO ab Lager, optional durch fixierte Instanzen
      ergänzt. Was fehlt, deckt ein **Nachschub-Unter-Auftrag** (``services/supply.py``) –
      der zugreifende Schritt ist bis dahin blockiert.

    Massgeblich ist die **deklarierte** Subjekt-Rolle der Schritte (REA-Registry,
    ``event_types.derive_subject_mode`` mit ``SUBJECT_PRECEDENCE``) – NICHT die blosse
    Anwesenheit eines Schritts. So kippt ein Schritt, der Bestand HEREINBRINGT (Beschaffung),
    den Auftrag nicht fälschlich in eine Bestands-Operation, die dann still an „kein Bestand"
    scheitert (kein Subjekt, keine Instanz, keine Fehlermeldung).

    **Wer vorhandene Instanzen auswählt, erzeugt keine** (Testnotiz #392). Eine Auswahl ist
    die Aussage «das Material gibt es schon» – also ist der Auftrag eine Operation auf
    Bestand, nie eine Erzeugung. Vorher galt das Gegenteil («eine Pin-Auswahl ohne Schritte
    kippt den Auftrag NICHT»), und die Folge war ein stiller Widerspruch: der Auftrag lief
    den **Artikel**-Prozess, erzeugte NEUE Instanzen – und hielt die ausgewählten daneben
    fest. Weil ein Bestands-Auftrag einen **eigenen** Ablauf braucht, weist die Freigabe
    einen Auftrag ohne jeden Prozessschritt jetzt ab, statt ihn zur Erzeugung umzudeuten.

    Ein **Mehrpositionen**-Auftrag (mehrere Artikel über ``order_lines``, ``article_id``
    fehlt) ist IMMER ``stock`` – es gibt keinen EINEN Artikel-Prozess, den er sonst fahren
    könnte. Fehlt ihm noch ein Ablauf, blockiert das (wie gehabt) die Freigabe mit einer
    klaren Fehlermeldung, statt still am fehlenden Artikel zu scheitern."""
    if is_deviation(order):
        return "deviation"   # wirkt auf bereits vorhandene Instanzen (kein Lager-Zugriff)
    if is_return(order):
        return "return"      # wirkt auf verkaufte Instanzen des Eltern (kein Lager-Zugriff)
    if order.article_id is None and lines_for(db, order):
        return "stock"
    if chosen_subjects(db, order):
        return "stock"       # ausgewählte Instanzen → das Material existiert bereits
    steps = order_custom_steps(db, order.id)
    if not steps:
        return "produce"     # keine eigenen Schritte → Artikel-Prozess, erzeugt Instanzen
    # Eigene Schritte: die Subjektart ist die DEKLARIERTE Rolle (Registry), nicht die
    # Anwesenheit. Bringt der Ablauf Bestand herein (PRODUCE: Beschaffung/Ressource), ERZEUGT
    # der Auftrag – nur ein Zugriff auf vorhandenen Bestand (STOCK/INSTANCE) ist eine
    # Bestands-Operation.
    mode = event_types.derive_subject_mode({s.step_type for s in steps})
    return "produce" if mode == event_types.PRODUCE else "stock"


def order_instances(db: Session, order: Order) -> list[Instance]:
    """Die Instanzen, auf die der Auftrag wirkt (einheitlich, ohne Modus-Flag):

    Bestands-Auftrag → die von ihm **als Subjekt verarbeiteten** Instanzen. Massgeblich ist
    die **dauerhafte** Verarbeitungs-Historie (``instance_order_links``, bei der Freigabe
    geschrieben), vereinigt mit der aktuellen Bindung (``subject_of_order_id``; deckt den
    Entwurf VOR der Freigabe ab). So bleiben die Instanzen auch **nach Abschluss** sichtbar,
    obwohl die Bindung dann gelöst ist.
    Sonst (produzierender Auftrag) → die **unter ihm erzeugten** Instanzen."""
    oids = {
        row.instance_object_id
        for row in db.query(InstanceOrderLink.instance_object_id)
        .filter(InstanceOrderLink.order_id == order.id, InstanceOrderLink.is_active == True)
        .all()
    }
    oids |= {i.object_id for i in chosen_subjects(db, order)}
    # FIX: Links/Bindung UND selbst erzeugte Instanzen VEREINIGEN statt entweder/oder:
    # ein Erzeugungsauftrag schreibt für seine eigenen Instanzen keine Links – sobald ein
    # Nachschub-/Deckungs-Link dazukam (peg/cover), kollabierte die Menge auf NUR die
    # gepinnten Instanzen und die selbst produzierten verschwanden aus Bewegung/Prüfung/
    # Abschluss (sie wären still «am Lager» freigegeben worden, ohne je bewegt zu sein).
    if oids:
        return (
            db.query(Instance)
            .filter(or_(Instance.object_id.in_(oids), Instance.order_id == order.id),
                    Instance.is_active == True)
            .order_by(Instance.object_id)
            .all()
        )
    return (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )


# Terminaler Verbleib: das Teil ist aus dem Auftrag «raus» – verschrottet, verkauft oder
# verbaut. Solche Instanzen werden nicht mehr weiterverarbeitet (bewegt/geprüft/bestückt).
TERMINAL_DISPOSITIONS = ("scrapped", "sold", "consumed")


def order_active_instances(db: Session, order: Order) -> list[Instance]:
    """Wie ``order_instances``, aber OHNE Instanzen mit **terminalem Verbleib** (verschrottet/
    verkauft/verbaut). Für die laufende Verarbeitung UND den Abschluss: ein verschrottetes Teil
    soll nicht mehr bewegt/geprüft/bestückt werden – der Auftrag wird mit seinen GUTEN Teilen
    fertig (die volle Liste inkl. terminaler Teile bleibt für die Anzeige via ``order_instances``)."""
    return [i for i in order_instances(db, order)
            if (i.disposition or "") not in TERMINAL_DISPOSITIONS]


def materialize_subject(db: Session, order: Order, actor_id: int) -> None:
    """Bei Freigabe das Subjekt herstellen. Committet NICHT – der Aufrufer schliesst ab.

    stock   → ``quantity`` Instanzen des Artikels binden: zuerst die fixierten (gepinnten)
      Instanzen, den Rest **FIFO ab Lager** auffüllen – alle für diesen Auftrag reserviert.
    produce → neue Bestands-Instanzen erzeugen (Serialisierung aus dem Artikel).

    Entscheidend ist die **deklarierte Subjekt-Rolle** der Schritte (siehe ``subject_kind``):
    ein Schritt, der Bestand hereinbringt (Beschaffung), erzeugt ebenfalls – wer dagegen
    vorhandene Instanzen ausgewählt hat, erzeugt nie (#392).

    deviation → die (bereits vorhandenen) Subjekt-Instanzen werden nur übernommen, ohne
      Lager-Allokation/-Reservierung (sie sind schon in Arbeit/im Besitz)."""
    if is_fixed_subject(order):
        # Abweichung ODER Retoure: die gewählten (vorhandenen/verkauften) Instanzen nur
        # dauerhaft als verarbeitet vermerken – KEINE Lager-Allokation/-Reservierung.
        _bind_deviation_subjects(db, order, actor_id)
        return
    kind = subject_kind(db, order)   # abgeleitet (produce | stock | deviation | return)
    if kind == "stock":
        if order.article_id is not None:
            _allocate_stock_subject(db, order, actor_id)
        else:
            _allocate_stock_subject_multiline(db, order, actor_id)
        return
    create_instances_for_order(db, order, actor_id)


def _bind_deviation_subjects(db: Session, order: Order, actor_id: int) -> None:
    """Unter-Auftrag mit festem Subjekt (Abweichung/Retoure/Bereitstellung): die gewählten
    Instanzen dauerhaft als verarbeitet vermerken – **keine Lager-ALLOKATION** (es wird nichts
    gesucht, das Subjekt steht ja fest).

    **Reserviert wird trotzdem**, sobald eine Instanz am Lager liegt: ein freigegebener
    Unter-Auftrag hat sie in der Hand, also darf sie kein anderer Auftrag per FIFO wegnehmen.
    Ohne das war eine Instanz unter offener Abweichung für jeden anderen Auftrag frei
    verfügbar – und die Badge zeigte «Freigegeben», obwohl sie längst gebunden war. Nicht am
    Lager (in Arbeit, verkauft, gesperrt) → nichts zu reservieren, dort greift ohnehin kein
    FIFO. Beim Abschluss/Verwerfen löst ``release`` die Reservierung wieder."""
    from .inventory import is_in_stock
    from .reservation import enforce, reserve, reserved_for
    bound = chosen_subjects(db, order)
    if not bound:
        raise HTTPException(409, detail="Für diesen Unter-Auftrag sind keine Instanzen gewählt")
    for inst in bound:
        # Steht der Anspruch schon (beim Auswählen/Melden gesetzt, ggf. als Teilmenge),
        # bleibt er wie er ist – sonst gilt die ganze Instanz.
        if is_in_stock(inst) and reserved_for(inst, order.id) <= 0:
            reserve(inst, order.id, to_qty(inst.quantity))
        # **Und JETZT wird er scharf** (Testnotiz #370): bis zur Freigabe war es eine
        # Vormerkung, die niemandem etwas wegnahm. Hier setzt sie sich durch – wer dadurch
        # zu viel hätte, verliert entsprechend und meldet damit seine Unterdeckung.
        # Die Stelle gilt für BEIDE Wege: die Auswahl im Auftrag ebenso wie die
        # systemseitige Abweichung (fehlgeschlagene Datenerfassung, Artikel-Deaktivierung).
        enforce_pick(db, order, inst)
        # Die übernommene MENGE dauerhaft festhalten – die Reservierung wird bei Abschluss
        # gelöst, der Materialfluss braucht sie danach noch (Notiz #413).
        record_link(db, inst.object_id, order.id, held_quantity(order, inst))
    log_audit(db, "instances", None, "Unter-Auftrag übernimmt Instanzen", actor_id, object_id=order.object_id)


def _allocate_stock_for(db: Session, order: Order, article_id: int, quantity) -> None:
    """Kern der Bestands-Allokation für GENAU einen Artikel + Menge unter einem Auftrag:

    1. die fixierten (gepinnten) Instanzen DIESES Artikels prüfen – sie müssen
       **freigegeben** (qc passed) und am Lager sein, sonst ist die Freigabe nicht
       möglich – und reservieren;
    2. den **Rest FIFO ab Lager** auffüllen.
    Jede gebundene Instanz wird dauerhaft als „von diesem Auftrag verarbeitet" vermerkt.
    Wiederverwendet vom Einzel-Artikel-Auftrag (``order.article_id``) UND – je Position –
    vom Mehrpositionen-Auftrag (``order_lines``)."""
    pinned = chosen_subjects(db, order, article_id=article_id)
    claimed = ZERO
    for inst in pinned:                                    # fixierte: beim Auswählen beansprucht
        if not inventory.is_in_stock(inst):
            raise HTTPException(
                409, detail=f"Instanz {inst.object_id} ist nicht freigegeben/am Lager – Freigabe nicht möglich")
        # **Der Anspruch steht schon** – er wurde beim Auswählen gesetzt und trägt die
        # gewünschte (ggf. Teil-)Menge. Fehlt er (Altbestand/System-Pfad), gilt die ganze
        # Instanz und wird jetzt reserviert.
        want = reserved_for(inst, order.id)
        if want <= 0:
            want = to_qty(inst.quantity)
            if free_qty(inst) < want:                      # von einem anderen Auftrag belegt
                raise HTTPException(
                    409, detail=f"Instanz {inst.object_id} ist bereits für einen anderen Auftrag reserviert")
            reserve(inst, order.id, want)
        # Der Anspruch wird mit der Freigabe scharf – und zwar zulasten des **genannten**
        # Anteils (``orders.pick_sources``). Haben zwei Entwürfe dieselbe freie Menge
        # vorgemerkt, gewinnt der, der zuerst freigibt (``reservation.enforce``).
        enforce_pick(db, order, inst)
        claimed += want
        record_link(db, inst.object_id, order.id, want)
    remaining = to_qty(quantity) - claimed
    if remaining <= 0:
        return                                             # vollständig durch fixierte gedeckt
    cands = fifo_candidates(db, article_id, for_order_id=None, lock=True)   # freie Restmengen
    # **Partielle Deckung ist erlaubt** (kein Fehler mehr bei Unterdeckung): es wird FIFO
    # reserviert, was am Lager ist; die **Fehlmenge** deckt ein Nachschub-Unter-Auftrag
    # (``services/supply.py``). Der erste auf das Subjekt zugreifende Schritt (Bewegung/…)
    # bleibt so lange **blockiert** (abgeleitet aus dem Bestand), bis der Nachschub liefert.
    for cand, take in zip(cands, allocate(remaining, [free_qty(c) for c in cands])):
        if take <= 0:
            continue
        cand.subject_of_order_id = order.id               # Subjekt-Markierung (ganz/teilweise)
        reserve(cand, order.id, take)                     # mengengenaue Reservierung
        record_link(db, cand.object_id, order.id)


def _allocate_stock_subject(db: Session, order: Order, actor_id: int) -> None:
    """Subjekt eines Einzel-Artikel-Bestands-Auftrags **bei der Freigabe** binden +
    reservieren (siehe ``_allocate_stock_for``)."""
    if not order.article_id or not order.quantity:
        raise HTTPException(400, detail="Artikel und Menge sind für diesen Auftrag erforderlich")
    _allocate_stock_for(db, order, order.article_id, order.quantity)
    log_audit(db, "instances", None, "Bestand für Auftrag reserviert (ggf. teilweise)",
              actor_id, object_id=order.object_id)


def _allocate_stock_subject_multiline(db: Session, order: Order, actor_id: int) -> None:
    """Subjekt eines **Mehrpositionen**-Auftrags (``order_lines``) binden + reservieren:
    je Position dieselbe Logik wie beim Einzel-Artikel-Auftrag (fixiert zuerst, Rest FIFO),
    nur je Artikel/Menge der Position statt ``order.article_id``/``order.quantity``."""
    lines = lines_for(db, order)
    if not lines:
        raise HTTPException(400, detail="Mehrpositionen-Auftrag ohne Positionen")
    for line in lines:
        _allocate_stock_for(db, order, line.article_id, line.quantity)
    log_audit(db, "instances", None,
              f"Bestand für {len(lines)} Position(en) reserviert (ggf. teilweise)",
              actor_id, object_id=order.object_id)
