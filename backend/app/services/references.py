"""Verwendungsnachweise (Referenzen) einer Instanz – wo wird sie überall genutzt?

Liefert alle Stellen, an denen eine Instanz referenziert ist/wird, neueste zuerst:
Herkunftsauftrag, Datenerfassungen (QC-Stichprobe), Einbau in eine andere Instanz,
hier eingelagerte Instanzen sowie der aktuelle Standort (Lagerplatz/Person).
"""

from sqlalchemy.orm import Session

from ..models import (
    Article, ArticleProcessStep, Claim, Inspection, Instance, Order, ResourceUsage, StorageLocation,
)
from .locations import _obj_nr, location_label


def _order_obj_id(db: Session, order_id: int) -> int | None:
    o = db.query(Order).filter(Order.id == order_id).first()
    return o.object_id if o else None


def instance_references(db: Session, instance: Instance) -> list[dict]:
    oid = instance.object_id
    refs: list[dict] = []

    # Herkunftsauftrag (bei Freigabe erzeugt)
    onum = _order_obj_id(db, instance.order_id)
    if onum:
        refs.append({"kind": "Herkunftsauftrag", "ref_type": "order",
                     "object_id": onum, "label": _obj_nr(onum), "at": instance.created_at})

    # Datenerfassungen, deren Stichprobe diese Instanz nennt
    insps = (
        db.query(Inspection)
        .filter(Inspection.is_active == True, Inspection.samples.contains([{"instance_id": oid}]))
        .all()
    )
    for ins in insps:
        onum2 = _order_obj_id(db, ins.order_id)
        if onum2:
            refs.append({"kind": "Datenerfassung", "ref_type": "order",
                         "object_id": onum2, "label": _obj_nr(onum2), "at": ins.updated_at})

    # Eingebaut in eine andere Instanz (Host)
    if instance.location_type == "instance" and instance.location_id:
        refs.append({"kind": "Eingebaut in", "ref_type": "instance",
                     "object_id": instance.location_id, "label": _obj_nr(instance.location_id),
                     "at": instance.updated_at})

    # Hier eingelagerte/eingebaute Instanzen (Kinder)
    children = (
        db.query(Instance)
        .filter(Instance.is_active == True, Instance.location_type == "instance",
                Instance.location_id == oid)
        .all()
    )
    for ch in children:
        refs.append({"kind": "Enthält Instanz", "ref_type": "instance",
                     "object_id": ch.object_id, "label": _obj_nr(ch.object_id or 0),
                     "at": ch.updated_at})

    # Aktueller Standort (Lagerplatz/Person)
    if instance.location_type in ("lagerplatz", "user") and instance.location_id:
        refs.append({"kind": "Aktueller Standort", "ref_type": instance.location_type,
                     "object_id": instance.location_id,
                     "label": location_label(db, instance.location_type, instance.location_id) or _obj_nr(instance.location_id),
                     "at": instance.updated_at})

    # Reklamationen zu dieser Instanz
    claims = (
        db.query(Claim)
        .filter(Claim.is_active == True, Claim.instance_object_id == oid)
        .all()
    )
    for cl in claims:
        if cl.object_id:
            refs.append({"kind": "Reklamation", "ref_type": "claim",
                         "object_id": cl.object_id, "label": _obj_nr(cl.object_id),
                         "at": cl.created_at})

    # Als Betriebsmittel genutzt (Ressource-Schritt) – kein Standortwechsel
    for u in db.query(ResourceUsage).filter(ResourceUsage.is_active == True).all():
        tools = (u.details or {}).get("tools", [])
        if any(oid in (t.get("instance_ids") or []) for t in tools):
            onum = _order_obj_id(db, u.order_id)
            if onum:
                refs.append({"kind": "Als Betriebsmittel genutzt", "ref_type": "order",
                             "object_id": onum, "label": _obj_nr(onum), "at": u.updated_at})

    refs.sort(key=lambda r: r["at"], reverse=True)
    return refs


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
