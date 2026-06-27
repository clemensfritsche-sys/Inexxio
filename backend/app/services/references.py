"""Quer-Referenzen zweier ERP-Objekte:

* ``instance_orders`` – alle **Aufträge**, die eine Instanz angefasst haben. Eine
  Instanz ist die Summe aller Prozesse; Prozesse werden ausschliesslich durch
  Aufträge angestossen. Pro Auftrag werden die Rollen gesammelt (was er mit der
  Instanz tat), chronologisch (Herkunft/ältester zuerst).
* ``storage_location_references`` – lagernde Instanzen + Artikel, die einen
  Lagerplatz referenzieren.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from ..models import (
    Article, ArticleProcessStep, Inspection, Instance, Order, ResourceUsage, StorageLocation,
)
from .locations import _obj_nr


def instance_orders(db: Session, instance: Instance) -> list[dict]:
    """Aufträge, die diese Instanz angefasst haben (mit gesammelten Rollen)."""
    oid = instance.object_id
    # order_db_id -> {"roles": [...], "at": datetime}
    hits: dict[int, dict] = {}

    def add(order_db_id: int | None, role: str, at: datetime | None) -> None:
        if not order_db_id:
            return
        h = hits.setdefault(order_db_id, {"roles": [], "at": at})
        if role not in h["roles"]:
            h["roles"].append(role)
        if at and (h["at"] is None or at < h["at"]):
            h["at"] = at

    # Herkunft (make: erzeugt) / Subjekt eines individuellen Auftrags / Reservierung
    add(instance.order_id, "Erzeugt", instance.created_at)
    add(instance.subject_of_order_id, "Bearbeitet", instance.updated_at)
    add(instance.reserved_for_order_id, "Reserviert", instance.updated_at)

    # Datenerfassungen, deren Stichprobe diese Instanz nennt
    for ins in (
        db.query(Inspection)
        .filter(Inspection.is_active == True, Inspection.samples.contains([{"instance_id": oid}]))
        .all()
    ):
        add(ins.order_id, "Datenerfassung", ins.updated_at)

    # Ressource: verbraucht (eingebaut) bzw. als Betriebsmittel genutzt
    for u in db.query(ResourceUsage).filter(ResourceUsage.is_active == True).all():
        details = u.details or {}
        consumed = any(
            p.get("instance_id") == oid
            for line in details.get("consume", []) for p in line.get("picks", [])
        )
        tooled = any(oid in (t.get("instance_ids") or []) for t in details.get("tools", []))
        if consumed:
            add(u.order_id, "Verbaut", u.updated_at)
        if tooled:
            add(u.order_id, "Betriebsmittel", u.updated_at)

    if not hits:
        return []
    orders = {o.id: o for o in db.query(Order).filter(Order.id.in_(hits.keys())).all()}
    out: list[dict] = []
    for order_db_id, h in hits.items():
        o = orders.get(order_db_id)
        if not o or not o.object_id:
            continue
        out.append({
            "object_id": o.object_id, "mode": o.mode, "status": o.status,
            "roles": h["roles"], "at": h["at"] or o.created_at,
        })
    out.sort(key=lambda r: r["object_id"])   # chronologisch: Herkunft zuerst
    return out


def storage_location_references(db: Session, loc: StorageLocation) -> list[dict]:
    """Verwendung eines Lagerplatzes: aktuell lagernde Instanzen + Artikel, deren
    Prozessschritte hierher referenzieren (Lieferadresse/Bewegungsziel), neueste zuerst."""
    lid = loc.object_id
    refs: list[dict] = []

    # Aktuell hier lagernde Instanzen (mit Artikelbezug)
    insts = (
        db.query(Instance)
        .filter(Instance.is_active == True, Instance.location_type == "lagerplatz",
                Instance.location_id == lid)
        .all()
    )
    for i in insts:
        art = db.query(Article).filter(Article.id == i.article_id).first()
        name = art.name if art else "Instanz"
        refs.append({"kind": f"{name} · lagernd", "ref_type": "instance",
                     "object_id": i.object_id, "label": _obj_nr(i.object_id or 0),
                     "at": i.updated_at})

    # Artikel-Prozessschritte, die diesen Lagerplatz als Ziel referenzieren
    steps = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.is_active == True,
                ArticleProcessStep.target_location_type == "lagerplatz",
                ArticleProcessStep.target_location_id == lid)
        .all()
    )
    role = {"purchase": "Lieferadresse", "movement": "Bewegungsziel"}
    for st in steps:
        art = db.query(Article).filter(Article.id == st.article_id).first()
        if not art:
            continue
        refs.append({"kind": f"{art.name} · {role.get(st.step_type, 'Prozessschritt')}",
                     "ref_type": "article", "object_id": art.object_id,
                     "label": _obj_nr(art.object_id or 0), "at": st.updated_at})

    refs.sort(key=lambda r: r["at"], reverse=True)
    return refs
