"""Quer-Referenzen zweier ERP-Objekte:

* ``instance_orders`` – alle **Aufträge**, die eine Instanz angefasst haben. Eine
  Instanz ist die Summe aller Prozesse; Prozesse werden ausschliesslich durch
  Aufträge angestossen. Pro Auftrag werden die Rollen gesammelt (was er mit der
  Instanz tat), sortiert nach der **tatsächlichen Aktionszeit** an der Instanz –
  jüngste zuerst (NICHT nach Objektnummer/Anlage-Reihenfolge).
"""

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import (
    Article, ArticleProcessStep, Inspection, Instance, InstanceOrderLink, Order,
    ResourceUsage,
)
from .locations import _obj_nr


def instance_orders(db: Session, instance: Instance) -> list[dict]:
    """Aufträge, die diese Instanz angefasst haben (mit gesammelten Rollen).

    Zwei Schritte: **sammeln**, welcher Auftrag sie wann in welcher Rolle angefasst hat –
    und daraus **Zeilen bauen** (Name · Objektnummer · Status, jüngste zuerst)."""
    return _order_rows(db, _instance_hits(db, instance))


def _instance_hits(db: Session, instance: Instance) -> dict[int, dict]:
    """Welcher Auftrag hat diese Instanz wann und in welcher Rolle angefasst?
    ``{order_db_id: {"roles": [...], "at": datetime}}``"""
    oid = instance.object_id
    # order_db_id -> {"roles": [...], "at": datetime}
    hits: dict[int, dict] = {}

    def add(order_db_id: int | None, role: str, at: datetime | None) -> None:
        if not order_db_id:
            return
        h = hits.setdefault(order_db_id, {"roles": [], "at": at})
        if role not in h["roles"]:
            h["roles"].append(role)
        # JÜNGSTE Aktion dieses Auftrags an der Instanz behalten (für „neueste zuerst"):
        # ein Verkauf, der die Instanz später anfasst (verkauft), gehört über die Produktion,
        # die sie früher erzeugt hat – auch wenn der Produktionsauftrag die höhere Nummer hat.
        if at and (h["at"] is None or at > h["at"]):
            h["at"] = at

    # Herkunft (make: erzeugt) / aktuelle Bindung (Entwurf) / Reservierung
    add(instance.order_id, "Erzeugt", instance.created_at)
    add(instance.subject_of_order_id, "Bearbeitet", instance.updated_at)
    add(instance.reserved_for_order_id, "Reserviert", instance.updated_at)

    # Dauerhafte Verarbeitungs-Historie: jeder Auftrag, der diese Instanz als Subjekt
    # verarbeitet hat (bei der Freigabe festgehalten) – unabhängig davon, dass die
    # veränderliche Bindung bei Abschluss/Abbruch gelöst wird (behebt „Auftrag fehlt
    # nach Abschluss"). Eine Quelle der Wahrheit für die Auftrags-Historie der Instanz.
    for link in (
        db.query(InstanceOrderLink)
        .filter(InstanceOrderLink.instance_object_id == oid, InstanceOrderLink.is_active == True)
        .all()
    ):
        add(link.order_id, "Bearbeitet", link.created_at)

    # Datenerfassungen, deren Stichprobe diese Instanz nennt
    for ins in (
        db.query(Inspection)
        .filter(Inspection.is_active == True, Inspection.samples.contains([{"instance_id": oid}]))
        .all()
    ):
        add(ins.order_id, "Datenerfassung", ins.updated_at)

    # Ressource: verbraucht (eingebaut) bzw. als Betriebsmittel genutzt.
    # JSONB-Containment filtert in SQL vor (vorher wurden ALLE resource_usages der
    # Datenbank geladen und in Python gescannt – unbegrenzt wachsend); die Python-Prüfung
    # unten klassifiziert nur noch die wenigen Treffer (verbaut vs. Betriebsmittel).
    usage_filter = or_(
        ResourceUsage.details.op("@>")({"consume": [{"picks": [{"instance_id": oid}]}]}),
        ResourceUsage.details.op("@>")({"tools": [{"instance_ids": [oid]}]}),
    )
    for u in db.query(ResourceUsage).filter(
        ResourceUsage.is_active == True, usage_filter
    ).all():
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

    return hits


def _order_rows(db: Session, hits: dict[int, dict]) -> list[dict]:
    """Die gesammelten Treffer als Datensatz-Zeilen – jüngste Aktion zuerst."""
    if not hits:
        return []
    orders = {o.id: o for o in db.query(Order).filter(Order.id.in_(hits.keys())).all()}
    from . import orders as orders_svc
    art_ids = {o.article_id for o in orders.values() if o.article_id}
    art_names = (
        {a.id: a.name for a in db.query(Article).filter(Article.id.in_(art_ids)).all()}
        if art_ids else {}
    )
    out: list[dict] = []
    for order_db_id, h in hits.items():
        o = orders.get(order_db_id)
        if not o or not o.object_id:
            continue
        out.append({
            # Name + Art des Auftrags mitgeben: die Liste zeigt einen Datensatz, und ein
            # Datensatz zeigt überall Name · Objektnummer · Status (Notizen #177/#243) –
            # ein Abweichungsauftrag ist zudem als solcher gekennzeichnet.
            "object_id": o.object_id, "status": o.status, "reason": o.reason,
            "name": orders_svc.order_display_name(o, art_names.get(o.article_id)),
            "roles": h["roles"], "at": h["at"] or o.created_at,
        })
    # Nach der **tatsächlichen Aktionszeit** an der Instanz – jüngste zuerst (nicht nach
    # Objektnummer: die spiegelt die Anlage-Reihenfolge der Aufträge, nicht die Instanz-Zeitachse).
    out.sort(key=lambda r: (r["at"], r["object_id"]), reverse=True)
    return out


def object_references(db: Session, object_id: int) -> list[dict]:
    """**Wer zeigt auf diese Objektnummer?** – generisch für JEDEN Objekttyp (Instanz,
    Person, Behälter-Instanz, Unternehmen). Weil Objektnummern global eindeutig sind,
    identifiziert ``location_id == object_id`` den Standort zweifelsfrei – ohne Typ-Filter:

    * **verortete Instanzen** – alles, was aktuell an dieser Objektnummer liegt (bei einer
      Person gehaltene Teile, in einem Behälter gelagerte Instanzen …);
    * **Prozessschritte**, die sie als Ziel/Lieferadresse referenzieren (Artikel-Prozess).

    Neueste zuerst. EIN Query je Bezugsart (kein N+1). Andere Rückverweis-Arten (z. B.
    Auftrags-Historie einer Instanz) laufen bewusst über ``instance_orders``."""
    refs: list[dict] = []
    # Verortet ist eine Instanz hier, wenn ihr **skalarer** Standort diese Objektnummer ist
    # ODER ihre **Verteilungs-Map** eine Teilmenge hier führt (Charge auf mehrere Orte verteilt).
    # **Verschrottetes zählt NIE als «liegt hier»**: eine verschrottete Instanz hat keinen realen
    # Halter mehr (der Endzustand `scrapped` IST die Wo-Aussage) – auch ein evtl. noch nicht
    # bereinigter Alt-Standort (`location_id`) soll den Halter nicht mehr belegen.
    insts = (
        db.query(Instance)
        .filter(
            Instance.is_active == True,
            Instance.disposition != "scrapped",
            or_(
                Instance.location_id == object_id,
                Instance.locations.has_key(str(object_id)),
            ),
        )
        .all()
    )
    steps = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.is_active == True,
                ArticleProcessStep.target_location_id == object_id)
        .all()
    )
    art_ids = {i.article_id for i in insts} | {s.article_id for s in steps if s.article_id}
    arts = {a.id: a for a in db.query(Article).filter(Article.id.in_(art_ids)).all()} if art_ids else {}
    from . import location_split
    for i in insts:
        art = arts.get(i.article_id)
        name = art.name if art else "Instanz"
        # Menge, die HIER liegt (die ganze Instanz oder – bei einer verteilten Charge –
        # nur die Teilmenge an dieser Objektnummer).
        here = next((d["quantity"] for d in location_split.distribution(i)
                     if d["location_id"] == object_id), None)
        qty = f"{here:g} " if here is not None else ""
        refs.append({"kind": f"{name} · {qty}verortet", "ref_type": "instance",
                     "object_id": i.object_id, "label": _obj_nr(i.object_id or 0),
                     "at": i.updated_at})

    role = {"purchase": "Lieferadresse", "movement": "Bewegungsziel"}
    for st in steps:
        art = arts.get(st.article_id)
        if not art:
            continue
        refs.append({"kind": f"{art.name} · {role.get(st.step_type, 'Prozessschritt')}",
                     "ref_type": "article", "object_id": art.object_id,
                     "label": _obj_nr(art.object_id or 0), "at": st.updated_at})

    refs.sort(key=lambda r: r["at"], reverse=True)
    return refs
