"""Das **Subjekt** eines Auftrags – die Instanzen, auf die er wirkt.

Die Subjektart wird aus der **Gestalt des Auftrags abgeleitet** (kein Modus-Flag):

  • **produce** – Artikel + Menge, KEINE eigenen Schritte → der Auftrag fährt den
    Prozess des Artikels und ERZEUGT neue Instanzen.
  • **stock**   – eigene Schritte ohne vorgewählte Instanzen → das Subjekt wird per
    Artikel + Menge **FIFO ab Lager** allokiert (z. B. Verkauf über den Shop).
  • **chosen**  – ausgewählte, vorhandene Instanzen (``subject_of_order_id`` bei der
    Anlage gesetzt) → genau diese sind das Subjekt (Reklamation, gezielter Verkauf).

Das Subjekt wird bei der **Freigabe** hergestellt und – beim Bestands-Zugriff (stock/
chosen) – zugleich für genau diesen Auftrag **reserviert** (kein Doppelverkauf/-verbrauch).
Enthält der Ablauf einen Verkauf, verlassen die Subjekte bei Abschluss den Bestand
(``sold``, siehe ``process._finalize_subjects``); sonst bleibt der Verbleib unverändert.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Instance, InstanceOrderLink, Order
from .admin import log_audit
from .inventory import allocate, available_qty, fifo_candidates
from .processes import has_custom_steps
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


def chosen_subjects(db: Session, order: Order) -> list[Instance]:
    """Die bei der Anlage ausgewählten Subjekt-Instanzen (Bestands-Auftrag)."""
    return (
        db.query(Instance)
        .filter(Instance.subject_of_order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )


def is_deviation(order: Order) -> bool:
    """Abweichung = **Unter-Auftrag** (hat einen Eltern-Auftrag). Wirkt auf bereits «in der
    Hand» befindliche Instanzen des Eltern-Auftrags – ohne Lager-FIFO/-Reservierung."""
    return getattr(order, "parent_order_id", None) is not None


def subject_kind(db: Session, order: Order) -> str:
    """Abgeleitete Subjektart (Artikel ist immer der Anker):

    ``produce`` – KEINE eigenen Schritte → der Auftrag fährt den Artikel-Prozess und
      ERZEUGT neue Instanzen (auch jede **Beschaffung**: der Artikel-Prozess bringt den
      Bestand herein – es wird NIE vorhandener Bestand vorausgesetzt).
    ``stock``   – eigene Schritte → der Auftrag wirkt auf **vorhandene** Instanzen des
      Artikels (Wartung/Verkauf/Bewegung): ``quantity`` Stück, FIFO ab Lager, optional
      durch fixierte (gepinnte) Instanzen ergänzt/ersetzt.

    Massgeblich ist **allein** ``has_custom_steps`` – eigene Schritte = Operation am
    Bestand, keine = Herstellung. Eine reine (Entwurfs-)Pin-Auswahl ohne Schritte kippt
    den Auftrag NICHT in eine Bestands-Operation (sonst scheitert die Herstellung an
    „kein Bestand")."""
    if is_deviation(order):
        return "deviation"   # wirkt auf bereits vorhandene Instanzen (kein Lager-Zugriff)
    if has_custom_steps(db, order):
        return "stock"
    return "produce"


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
    if oids:
        return (
            db.query(Instance)
            .filter(Instance.object_id.in_(oids), Instance.is_active == True)
            .order_by(Instance.object_id)
            .all()
        )
    return (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )


def materialize_subject(db: Session, order: Order, actor_id: int) -> None:
    """Bei Freigabe das Subjekt herstellen. Committet NICHT – der Aufrufer schliesst ab.

    stock   → ``quantity`` Instanzen des Artikels binden: zuerst die fixierten (gepinnten)
      Instanzen, den Rest **FIFO ab Lager** auffüllen – alle für diesen Auftrag reserviert.
    produce → neue Bestands-Instanzen erzeugen (Serialisierung aus dem Artikel).

    Entscheidend ist **allein** ``has_custom_steps`` (siehe ``subject_kind``); eine
    Pin-Auswahl ohne Schritte erzeugt trotzdem (statt an fehlendem Bestand zu scheitern).

    deviation → die (bereits vorhandenen) Subjekt-Instanzen werden nur übernommen, ohne
      Lager-Allokation/-Reservierung (sie sind schon in Arbeit/im Besitz)."""
    if is_deviation(order):
        _bind_deviation_subjects(db, order, actor_id)
        return
    if has_custom_steps(db, order):
        _allocate_stock_subject(db, order, actor_id)
        return
    create_instances_for_order(db, order, actor_id)


def _bind_deviation_subjects(db: Session, order: Order, actor_id: int) -> None:
    """Abweichung: die gewählten Instanzen nur **dauerhaft als verarbeitet** vermerken –
    KEINE Lager-Allokation/-Reservierung. Die Instanzen können jeden Verbleib haben
    (in Arbeit, am Lager, …); die Abweichung wirkt direkt auf sie."""
    bound = chosen_subjects(db, order)
    if not bound:
        raise HTTPException(409, detail="Für die Abweichung sind keine Instanzen gewählt")
    for inst in bound:
        record_link(db, inst.object_id, order.id)
    log_audit(db, "instances", None, "Abweichung übernimmt Instanzen", actor_id, object_id=order.object_id)


def _allocate_stock_subject(db: Session, order: Order, actor_id: int) -> None:
    """Subjekt eines Bestands-Auftrags **bei der Freigabe** binden + reservieren:

    1. die fixierten (gepinnten) Instanzen prüfen – sie müssen **freigegeben** (qc passed)
       und am Lager sein, sonst ist die Freigabe nicht möglich – und reservieren;
    2. den **Rest FIFO ab Lager** auffüllen (Charge bei Bedarf geteilt).
    Jede gebundene Instanz wird dauerhaft als „von diesem Auftrag verarbeitet" vermerkt."""
    if not order.article_id or not order.quantity:
        raise HTTPException(400, detail="Artikel und Menge sind für diesen Auftrag erforderlich")

    pinned = chosen_subjects(db, order)
    for inst in pinned:                                    # fixierte: erst bei Freigabe „scharf"
        if not (inst.quality == "passed" and inst.disposition == "in_stock"):
            raise HTTPException(
                409, detail=f"Instanz {inst.object_id} ist nicht freigegeben/am Lager – Freigabe nicht möglich")
        need = inst.quantity - reserved_for(inst, order.id)
        if free_qty(inst) < need:                          # von einem anderen Auftrag belegt
            raise HTTPException(
                409, detail=f"Instanz {inst.object_id} ist bereits für einen anderen Auftrag reserviert")
        reserve(inst, order.id, need)                      # ganze Pin-Instanz, OHNE Teilung
        record_link(db, inst.object_id, order.id)
    remaining = order.quantity - sum(i.quantity for i in pinned)
    if remaining <= 0:
        return                                             # vollständig durch fixierte gedeckt
    cands = fifo_candidates(db, order.article_id, for_order_id=None)   # freie Restmengen
    have = available_qty(cands)
    if have < remaining:
        raise HTTPException(
            409, detail=f"Nicht genügend freigegebener Bestand: benötigt {remaining} weitere, verfügbar {have}")
    # FIFO mengengenau reservieren – die Instanz wird NIE geteilt (Objektnummer bleibt).
    for cand, take in zip(cands, allocate(remaining, [free_qty(c) for c in cands])):
        if take <= 0:
            continue
        cand.subject_of_order_id = order.id               # Subjekt-Markierung (ganz/teilweise)
        reserve(cand, order.id, take)                     # mengengenaue Reservierung
        record_link(db, cand.object_id, order.id)
    log_audit(db, "instances", None, "Bestand für Auftrag reserviert", actor_id, object_id=order.object_id)
