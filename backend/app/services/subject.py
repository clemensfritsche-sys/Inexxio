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

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import Instance, InstanceOrderLink, Order
from .admin import log_audit
from . import inventory
from .inventory import allocate, fifo_candidates
from .order_lines import lines_for
from .processes import order_custom_steps
from .quantity import qty_sum, to_qty
from .reservation import free_qty, reserve, reserved_for
from .serialization import create_instances_for_order


def record_link(db: Session, instance_object_id: int | None, order_id: int) -> None:
    """Verarbeitung einer Instanz durch einen Auftrag **dauerhaft** festhalten (idempotent) –
    unabhängig von späteren Bindungen/Reservierungen (siehe ``InstanceOrderLink``)."""
    if not instance_object_id:
        return
    exists = (
        db.query(InstanceOrderLink.id)
        .filter(InstanceOrderLink.instance_object_id == instance_object_id,
                InstanceOrderLink.order_id == order_id)
        .first()
    )
    if not exists:
        db.add(InstanceOrderLink(instance_object_id=instance_object_id, order_id=order_id))


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


def classify_pick(order: Order, insts: list) -> str | None:
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
    die Folge. Rein (schreibt nicht)."""
    if not insts:
        return PICK_NORMAL
    if any((i.disposition or "") == "sold" for i in insts):
        return PICK_RETURN
    if any(is_bound(order, i) for i in insts):
        return PICK_DEVIATION
    return PICK_NORMAL


def is_bound(order: Order, inst) -> bool:
    """Ist dieses Stück **gebunden** – also für diesen Auftrag nicht frei verfügbar?

    Gebunden heisst: nicht (mehr) frei am Lager (in Arbeit, verbaut, gesperrt) ODER die
    freie Menge deckt die Instanz nicht ganz (für einen FREMDEN Auftrag reserviert). Was
    dieser Auftrag selbst reserviert hat, zählt als frei – er greift ja auf sein eigenes zu.

    EINE Stelle, zwei Nutzer: sie entscheidet, ob eine Auswahl eine Abweichung ist
    (``classify_pick``), und sie verhindert, dass freie und gebundene Stücke im selben
    Auftrag landen (``routers/orders``). Rein (schreibt nicht)."""
    from .inventory import is_in_stock
    from .quantity import to_qty
    from .reservation import free_qty, reserved_for
    if not is_in_stock(inst):
        return True
    return free_qty(inst) + reserved_for(inst, order.id) < to_qty(inst.quantity)


def holding_order(db: Session, inst) -> Order | None:
    """**Welcher laufende Auftrag hat dieses Stück gerade in der Hand?**

    Die Klammer zwischen Auftrag und Abweichung ist die Instanz – also wird auch der
    Eltern-Auftrag einer Abweichung daraus **abgeleitet** statt eingegeben: entweder der
    Auftrag, der sie als Subjekt hält, oder der, der sie erzeugt hat. Läuft keiner mehr
    (das Stück liegt fertig am Lager), gibt es keinen Eltern – eine Abweichung darf auch
    allein stehen (späte Reklamation)."""
    for oid in (inst.subject_of_order_id, inst.order_id):
        if not oid:
            continue
        o = db.query(Order).filter(Order.id == oid, Order.is_active == True).first()
        if o is not None and o.status == "released":
            return o
    return None


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
    scheitert (kein Subjekt, keine Instanz, keine Fehlermeldung). Eine reine (Entwurfs-)Pin-
    Auswahl ohne Schritte kippt den Auftrag ebenfalls NICHT (sonst scheitert die Herstellung).

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

    Entscheidend ist die **deklarierte Subjekt-Rolle** der Schritte (siehe ``subject_kind``);
    eine Pin-Auswahl ohne Schritte erzeugt trotzdem (statt an fehlendem Bestand zu scheitern),
    und ein Schritt, der Bestand hereinbringt (Beschaffung), erzeugt ebenfalls.

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
    from .reservation import reserve, reserved_for
    bound = chosen_subjects(db, order)
    if not bound:
        raise HTTPException(409, detail="Für diesen Unter-Auftrag sind keine Instanzen gewählt")
    for inst in bound:
        record_link(db, inst.object_id, order.id)
        if is_in_stock(inst) and reserved_for(inst, order.id) <= 0:
            reserve(inst, order.id, to_qty(inst.quantity))
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
    for inst in pinned:                                    # fixierte: erst bei Freigabe „scharf"
        if not inventory.is_in_stock(inst):
            raise HTTPException(
                409, detail=f"Instanz {inst.object_id} ist nicht freigegeben/am Lager – Freigabe nicht möglich")
        need = to_qty(inst.quantity) - reserved_for(inst, order.id)
        if free_qty(inst) < need:                          # von einem anderen Auftrag belegt
            raise HTTPException(
                409, detail=f"Instanz {inst.object_id} ist bereits für einen anderen Auftrag reserviert")
        reserve(inst, order.id, need)                      # ganze Pin-Instanz, OHNE Teilung
        record_link(db, inst.object_id, order.id)
    remaining = to_qty(quantity) - qty_sum(i.quantity for i in pinned)
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
