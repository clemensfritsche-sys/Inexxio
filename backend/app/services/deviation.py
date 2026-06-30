"""Abweichungen – vereinheitlicht Abbruch-Folgeauftrag, Fehler/Reklamation, Nacharbeit.

Eine **Abweichung** ist ein **Unter-Auftrag** (``orders.parent_order_id``), der aus einem
laufenden Eltern-Auftrag heraus entsteht und auf dessen Instanzen wirkt. Der Eltern-Auftrag
**pausiert**, solange die Abweichung offen ist (``process._is_paused_by_deviation``).

Sonderfall **Abbruch**: «Abbrechen» bricht NICHT sofort ab, sondern erzwingt einen
**Folgeauftrag** (eine Abweichung), der die im Prozess befindlichen Instanzen übernimmt.
Das Original wird erst **inaktiv**, wenn der Folgeauftrag **freigegeben** ist – so liegen
nie undefinierte Teile herum.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Instance, InstanceOrderLink, Order
from .admin import log_audit
from .events import emit
from .objects import next_object_id
from .subject import order_active_instances, record_link


def open_deviations(db: Session, parent: Order) -> list[Order]:
    """Aktive (Entwurf/freigegeben) Abweichungs-Unteraufträge eines Auftrags."""
    if not parent.object_id:
        return []
    return (
        db.query(Order)
        .filter(Order.parent_order_id == parent.object_id, Order.is_active == True,
                Order.status.in_(("draft", "released")))
        .order_by(Order.object_id)
        .all()
    )


def instance_open_deviation(db: Session, instance_object_id: int | None) -> Order | None:
    """Die (eine) noch offene Abweichung, die diese Instanz bereits als Subjekt führt –
    sonst ``None``. Grundlage für die Regel «höchstens EINE aktive Abweichung je Instanz»:
    verhindert, dass Instanz- und Prozess-Ebene gleichzeitig dieselbe Instanz greifen."""
    if not instance_object_id:
        return None
    return (
        db.query(Order)
        .join(InstanceOrderLink, InstanceOrderLink.order_id == Order.id)
        .filter(Order.parent_order_id.isnot(None), Order.is_active == True,
                Order.status.in_(("draft", "released")),
                InstanceOrderLink.instance_object_id == instance_object_id,
                InstanceOrderLink.is_active == True)
        .first()
    )


def _resolve_subjects(db: Session, parent: Order, instance_object_ids: list[int] | None) -> list[Instance]:
    """Die betroffenen Instanzen einer Abweichung: explizit gewählte (Instanz-Ebene) oder –
    ohne Auswahl – alle Instanzen des Eltern-Auftrags (Prozess-Ebene)."""
    if instance_object_ids:
        rows = (
            db.query(Instance)
            .filter(Instance.object_id.in_(instance_object_ids), Instance.is_active == True)
            .order_by(Instance.object_id)
            .all()
        )
        if len(rows) != len(set(instance_object_ids)):
            raise HTTPException(400, detail="Mindestens eine gewählte Instanz wurde nicht gefunden")
        return rows
    # Prozess-Ebene (ohne Auswahl): alle noch AKTIVEN Instanzen – ein bereits verschrottetes
    # Teil wird nicht erneut in eine Abweichung gezogen.
    return order_active_instances(db, parent)


def create_deviation(db: Session, parent: Order, instance_object_ids: list[int] | None,
                     actor_id: int, title_prefix: str = "Abweichung zu") -> Order:
    """Eine **Abweichung** (Unter-Auftrag) zu ``parent`` anlegen, die auf die betroffenen
    Instanzen wirkt (Instanz- oder Prozess-Ebene). Entwurf; der Nutzer definiert die
    Auflösung (Schritte) und gibt frei. Committet NICHT (der Aufrufer schliesst ab)."""
    insts = _resolve_subjects(db, parent, instance_object_ids)
    if not insts:
        raise HTTPException(409, detail="Keine Instanzen für die Abweichung vorhanden")
    # Regel: höchstens EINE aktive Abweichung je Instanz (kein gleichzeitiges Greifen auf
    # Instanz- UND Prozess-Ebene). Wer zuerst kommt, hält die Instanz, bis er abgeschlossen ist.
    for inst in insts:
        existing = instance_open_deviation(db, inst.object_id)
        if existing:
            raise HTTPException(
                409,
                detail=f"Instanz {inst.object_id} hat bereits eine offene Abweichung "
                       f"(Auftrag {existing.object_id}) – diese zuerst abschliessen.",
            )
    devi = Order(
        object_id=next_object_id(db, "order"), status="draft",
        article_id=parent.article_id, quantity=len(insts),
        parent_order_id=parent.object_id, reason="deviation",
        title=f"{title_prefix} {parent.object_id}",
    )
    db.add(devi)
    db.flush()
    for inst in insts:                       # betroffene Instanzen an die Abweichung binden
        inst.subject_of_order_id = devi.id
        # Sofort dauerhaft in der Instanz-Historie festhalten (nicht erst bei Freigabe):
        # die Abweichung erscheint ab Anlage unter «Aufträge» der Instanz, unabhängig von
        # der wandernden ``subject_of_order_id``-Bindung (InstanceOrderLink = Quelle der Wahrheit).
        record_link(db, inst.object_id, devi.id)
    log_audit(db, "orders", None, f"Abweichung zu {parent.object_id} angelegt", actor_id,
              object_id=devi.object_id)
    emit(db, "order.deviation_opened", object_type="order", object_id=devi.object_id,
         payload={"parent": parent.object_id, "instances": [i.object_id for i in insts]},
         actor_id=actor_id)
    return devi


def create_abort_followup(db: Session, order: Order, actor_id: int) -> Order:
    """Beim Abbruch einen **Folgeauftrag** (Abweichung) erzeugen, der die im Prozess
    befindlichen Instanzen übernimmt. Committet NICHT (der Aufrufer schliesst ab)."""
    if order.status != "released":
        raise HTTPException(400, detail="Nur ein freigegebener Auftrag braucht einen Folgeauftrag")
    if order.abort_into_id:
        raise HTTPException(409, detail="Für diesen Auftrag ist bereits ein Folgeauftrag offen")
    follow = create_deviation(db, order, None, actor_id, title_prefix="Abbruch von")
    order.abort_into_id = follow.object_id   # Original = «Abbruch ausstehend»
    log_audit(db, "orders", "abort_into_id", str(follow.object_id), actor_id, object_id=order.object_id)
    emit(db, "order.abort_requested", object_type="order", object_id=order.object_id,
         payload={"followup": follow.object_id}, actor_id=actor_id)
    return follow


def auto_deviation_from_inspection(db: Session, order: Order, actor_id: int | None) -> Order | None:
    """Bei **fehlgeschlagener Datenerfassung** automatisch eine Abweichung auf die
    durchgefallenen Instanzen anlegen (ersetzt die frühere Auto-Reklamation). Idempotent:
    solange eine Abweichung dieses Auftrags offen ist, wird keine weitere erzeugt."""
    if open_deviations(db, order):
        return None
    insts = (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )
    failed = [i.object_id for i in insts if i.quality == "failed" and i.object_id]
    if not failed:
        return None
    return create_deviation(db, order, failed, actor_id or 0, title_prefix="Datenerfassung-Abweichung zu")


def revoke(db: Session, followup: Order, actor_id: int) -> Order | None:
    """**Abbruch/Abweichung zurücknehmen** – solange der Folgeauftrag erst **Entwurf** ist
    (noch nicht vollzogen). Die vorgemerkten Instanzen gehen ans Original zurück, ein
    ausstehender Abbruch (``abort_into_id``) wird gelöscht, der Folgeauftrag wird inaktiv.

    Das Original ist danach **automatisch nicht mehr pausiert** und läuft **unverändert**
    weiter: Ein Entwurf-Folgeauftrag hat die Reservierungen des Originals NIE gelöst (das
    passiert erst bei der Freigabe), darum bleibt alles 1:1 erhalten. Committet NICHT.
    Liefert den (wieder laufenden) Eltern-Auftrag."""
    if followup.parent_order_id is None:
        raise HTTPException(400, detail="Das ist kein Unter-Auftrag (Folgeauftrag).")
    if followup.status != "draft":
        raise HTTPException(
            409, detail="Nur ein noch nicht freigegebener Folgeauftrag kann zurückgenommen werden.")
    parent = db.query(Order).filter(Order.object_id == followup.parent_order_id).first()
    # Vorgemerkte Instanzen ans Original zurückgeben (Bindung + Verarbeitungs-Link lösen).
    for inst in db.query(Instance).filter(
        Instance.subject_of_order_id == followup.id, Instance.is_active == True
    ).all():
        inst.subject_of_order_id = None
    for link in db.query(InstanceOrderLink).filter(
        InstanceOrderLink.order_id == followup.id, InstanceOrderLink.is_active == True
    ).all():
        link.is_active = False
    if parent and parent.abort_into_id == followup.object_id:
        log_audit(db, "orders", "abort_into_id", None, actor_id,
                  object_id=parent.object_id, old_value=str(followup.object_id))
        parent.abort_into_id = None
    old = followup.status
    followup.status = "inactive"
    log_audit(db, "orders", "status", "inactive", actor_id,
              object_id=followup.object_id, old_value=old)
    emit(db, "order.abort_revoked", object_type="order",
         object_id=(parent.object_id if parent else followup.object_id),
         payload={"followup": followup.object_id}, actor_id=actor_id)
    return parent


def apply_abort_on_release(db: Session, followup: Order, actor_id: int) -> None:
    """Wird ein Abbruch-Folgeauftrag **freigegeben**, das Original endgültig **abbrechen**:
    Reservierungen lösen, ABER die übernommenen Instanzen NICHT deaktivieren (sie gehören
    jetzt dem Folgeauftrag). Committet NICHT."""
    if not followup.parent_order_id:
        return
    parent = db.query(Order).filter(Order.object_id == followup.parent_order_id).first()
    if not parent or parent.abort_into_id != followup.object_id or parent.status == "inactive":
        return
    from .deactivation import cancel_order_effects
    old = parent.status
    parent.status = "inactive"
    cancel_order_effects(db, parent, actor_id, keep_instances=True)
    log_audit(db, "orders", "status", "inactive", actor_id, object_id=parent.object_id, old_value=old)
    emit(db, "order.aborted", object_type="order", object_id=parent.object_id,
         payload={"followup": followup.object_id}, actor_id=actor_id)
