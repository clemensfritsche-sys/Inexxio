"""Inaktiv setzen / Ersetzen – ohne Versionierung (CLAUDE.md).

Leitprinzip: **Inaktiv/Ersetzen sperrt nur die Zukunft** – es verändert nie
physischen Bestand (Instanzen) oder bereits angestossene Arbeit (laufende
Aufträge) im Stillen. Drei getrennte Lebenszyklen (Stammdaten-Status, Instanz,
Auftrag) werden nicht vermischt.

Artikel:
    - Inaktiv kaskadiert **nach oben** über ``consume``-Ressourcen: jeder Artikel,
      der ihn (transitiv) verbaut, wird ebenfalls inaktiv. Damit ist „kein Artikel
      mit inaktivem Bestandteil herstellbar" automatisch erzwungen. ``tool``-
      Referenzen kaskadieren nicht (vorhandene Werkzeug-Instanzen bleiben nutzbar).
    - Laufende (freigegebene) Aufträge: **auslaufen** (Default) oder **abbrechen**.
    - Instanzen werden NIE automatisch angefasst (Verschrotten ist separat/manuell).

Auftrag: inaktiv = abbrechen (Reservierungen frei, unfertige Produkt-Instanzen
    inaktiv). Kein Reaktivieren – Neustart = neuer Auftrag.

Lagerplatz: inaktiv nur, wenn leer (keine lagernden Instanzen) – sonst zuerst
    umlagern. Reaktivieren erlaubt.

Ersetzen: alter Datensatz inaktiv + **Duplikat als Entwurf** + Verknüpfung
    ``replaced_by_id`` (Nachvollziehbarkeit „was hat was ersetzt").
"""

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import Article, ArticleProcessStep, Instance, Order, Process, StorageLocation
from .admin import log_audit
from .events import emit
from .objects import next_object_id


# ─── Artikel: Kaskade über consume-Ressourcen ────────────────────────────────

def _consume_parent_map(db: Session) -> dict[int, set[int]]:
    """Umkehr-Index Komponente → {Eltern-Artikel, die sie verbrauchen}.

    Eltern = Artikel, die den ``produce``-Prozess in ihrer Stückliste führen (n:m).
    Verbrauch (consume) leitet sich aus der **Artikel-Art** ab: Betriebsmittel
    (``equipment``) kaskadiert NICHT."""
    from . import processes as processes_svc
    out: dict[int, set[int]] = {}
    # Nur die Produktions-Rezeptur (Quelle ``produce``) bildet die Stückliste – und
    # darin nur **Verbrauch**-Zeilen (``mode='consume'``). Betriebsmittel-Zeilen (``tool``)
    # machen das Produkt nicht herstellungs-abhängig vom Werkzeug (keine Kaskade).
    steps = (
        db.query(ArticleProcessStep)
        .join(Process, Process.id == ArticleProcessStep.process_id)
        .filter(ArticleProcessStep.step_type.in_(event_types.RESOURCE_TYPES),
                ArticleProcessStep.is_active == True,
                Process.source == "produce", Process.is_active == True)
        .all()
    )
    parents_cache: dict[int, list[int]] = {}
    for s in steps:
        if s.process_id not in parents_cache:
            parents_cache[s.process_id] = processes_svc.linked_article_ids(db, s.process_id)
        parents = parents_cache[s.process_id]
        if not parents:
            continue
        for line in (s.resource_lines or []):
            aid = line.get("article_id")
            mode = line.get("mode") or ("tool" if s.step_type == "tool" else "consume")
            if aid is None or mode != "consume":
                continue
            out.setdefault(aid, set()).update(parents)
    return out


def consume_parents(db: Session, article_db_id: int) -> set[int]:
    """Transitive Hülle aller Artikel, die ``article_db_id`` (direkt/indirekt)
    verbauen (ohne den Artikel selbst). Zyklensicher."""
    parents = _consume_parent_map(db)
    seen: set[int] = set()
    stack = [article_db_id]
    while stack:
        for p in parents.get(stack.pop(), ()):
            if p not in seen:
                seen.add(p)
                stack.append(p)
    return seen


def _affected_article_ids(db: Session, article: Article) -> set[int]:
    return consume_parents(db, article.id) | {article.id}


def article_impact(db: Session, article: Article) -> dict:
    """Wirkungsanalyse (Dry-Run) für die Vorschau: mitbetroffene Artikel,
    laufende (freigegebene) Aufträge und Lagerbestand (Stück, ``passed``)."""
    ids = _affected_article_ids(db, article)
    parent_arts = (
        db.query(Article)
        .filter(Article.id.in_(ids - {article.id}), Article.is_active == True,
                Article.status != "inactive")
        .order_by(Article.object_id)
        .all()
    )
    orders = (
        db.query(Order)
        .filter(Order.is_active == True, Order.status == "released", Order.article_id.in_(ids))
        .order_by(Order.object_id)
        .all()
    )
    stock = (
        db.query(func.coalesce(func.sum(Instance.quantity), 0))
        .filter(Instance.is_active == True, Instance.qc_status == "passed", Instance.article_id.in_(ids))
        .scalar()
    )
    return {"articles": parent_arts, "orders": orders, "stock": int(stock or 0)}


def deactivate_article(db: Session, article: Article, actor_id: int,
                       orders_mode: str = "phase_out") -> None:
    """Artikel + alle (transitiven) consume-Eltern inaktiv setzen. Entwurf-Aufträge
    werden mit-inaktiviert; freigegebene je ``orders_mode`` ausgelaufen/abgebrochen.
    Schreibt nur (flush); der Aufrufer committet."""
    ids = _affected_article_ids(db, article)
    for a in db.query(Article).filter(Article.id.in_(ids), Article.is_active == True).all():
        if a.status != "inactive":
            log_audit(db, "articles", "status", "inactive", actor_id,
                      object_id=a.object_id, old_value=a.status)
            a.status = "inactive"
    # Entwurf-Aufträge: harmlos mit-inaktivieren (kein Bestand/keine Reservierung)
    for o in db.query(Order).filter(
        Order.is_active == True, Order.status == "draft", Order.article_id.in_(ids)
    ).all():
        o.status = "inactive"
    # Freigegebene Aufträge: abbrechen (sonst auslaufen lassen)
    if orders_mode == "cancel":
        for o in db.query(Order).filter(
            Order.is_active == True, Order.status == "released", Order.article_id.in_(ids)
        ).all():
            log_audit(db, "orders", "status", "inactive", actor_id,
                      object_id=o.object_id, old_value=o.status)
            o.status = "inactive"
            cancel_order_effects(db, o, actor_id)
    emit(db, "article.deactivated", object_type="article", object_id=article.object_id,
         payload={"orders_mode": orders_mode, "affected": len(ids)}, actor_id=actor_id)


def article_reactivation_blocker(db: Session, article: Article) -> str | None:
    """Grund, warum ein Artikel NICHT reaktiviert werden darf (sonst ``None``):
    er wurde ersetzt, oder eine verbaute Komponente ist nicht (mehr) freigegeben."""
    if article.replaced_by_id:
        return "Artikel wurde ersetzt – bitte den Nachfolger verwenden"
    from . import processes as processes_svc
    linked_ids = processes_svc.linked_process_ids(db, article.id)
    if not linked_ids:
        return None
    steps = (
        db.query(ArticleProcessStep)
        .join(Process, Process.id == ArticleProcessStep.process_id)
        .filter(Process.id.in_(linked_ids), Process.source == "produce",
                Process.is_active == True,
                ArticleProcessStep.step_type.in_(event_types.RESOURCE_TYPES),
                ArticleProcessStep.is_active == True)
        .all()
    )
    for s in steps:
        for line in (s.resource_lines or []):
            aid = line.get("article_id")
            mode = line.get("mode") or ("tool" if s.step_type == "tool" else "consume")
            if aid is None or mode != "consume":
                continue
            comp = db.query(Article).filter(Article.id == aid).first()
            if comp and comp.status != "released":
                return f"Komponente {comp.object_id} ist nicht freigegeben"
    return None


# ─── Auftrag: Abbruch ─────────────────────────────────────────────────────────

def cancel_order_effects(db: Session, order: Order, actor_id: int) -> None:
    """Beim Abbruch eines Auftrags: Reservierungen UND Bestands-Subjekte freigeben
    (Verkauf/Entnahme – zurück in den freien Bestand) und unfertige (``pending``)
    Produkt-Instanzen deaktivieren. Setzt NICHT den Status (Aufrufer)."""
    # Reservierte Komponenten + als Subjekt gewählte Bestands-Instanzen freigeben.
    for inst in db.query(Instance).filter(
        Instance.reserved_for_order_id == order.id, Instance.is_active == True
    ).all():
        inst.reserved_for_order_id = None
    for inst in db.query(Instance).filter(
        Instance.subject_of_order_id == order.id, Instance.is_active == True
    ).all():
        inst.subject_of_order_id = None
    # Bei Freigabe erzeugte, noch unfertige Produkt-Instanzen deaktivieren.
    for inst in db.query(Instance).filter(
        Instance.order_id == order.id, Instance.is_active == True, Instance.qc_status == "pending"
    ).all():
        log_audit(db, "instances", "is_active", "false", actor_id,
                  object_id=inst.object_id, old_value="true")
        inst.is_active = False
    emit(db, "order.cancelled", object_type="order", object_id=order.object_id, actor_id=actor_id)


# ─── Lagerplatz ───────────────────────────────────────────────────────────────

def storage_location_in_use(db: Session, loc: StorageLocation) -> bool:
    return db.query(Instance.id).filter(
        Instance.is_active == True, Instance.location_type == "lagerplatz",
        Instance.location_id == loc.object_id,
    ).first() is not None


# ─── Ersetzen: Duplikat als Entwurf + Verknüpfung ────────────────────────────

def duplicate_article(db: Session, src: Article, actor_id: int) -> Article:
    """Stammdaten in einen neuen Entwurf kopieren und die **Prozessstückliste**
    übernehmen (dieselben Prozess-Objekte erneut verlinken).

    Prozesse sind wiederverwendbare Objekte – beim Ersetzen wird der Recipe nicht
    dupliziert; soll der Nachfolger einen abweichenden Prozess haben, wird der
    Prozess einzeln ersetzt (und der Link getauscht)."""
    new = Article(
        object_id=next_object_id(db, "article"), status="draft",
        name=src.name, unit=src.unit, serialization=src.serialization, size=src.size,
        weight_kg=src.weight_kg,
        material=src.material, cad_url=src.cad_url, surface=src.surface,
        min_order_qty=src.min_order_qty, safety_stock=src.safety_stock,
        supplier_article_number=src.supplier_article_number,
    )
    db.add(new)
    db.flush()
    from . import processes as processes_svc
    for pid in processes_svc.linked_process_ids(db, src.id):
        processes_svc.link_process(db, new.id, pid)
    log_audit(db, "articles", None, f"Artikel als Ersatz für {src.object_id} angelegt",
              actor_id, object_id=new.object_id)
    return new


def duplicate_order(db: Session, src: Order, actor_id: int) -> Order:
    new = Order(object_id=next_object_id(db, "order"), status="draft", title=src.title,
                article_id=src.article_id, quantity=src.quantity,
                desired_delivery_date=src.desired_delivery_date,
                process_id=src.process_id, subject_instance_id=src.subject_instance_id)
    db.add(new)
    db.flush()
    log_audit(db, "orders", None, f"Auftrag als Ersatz für {src.object_id} angelegt",
              actor_id, object_id=new.object_id)
    return new


def duplicate_storage_location(db: Session, src: StorageLocation, actor_id: int) -> StorageLocation:
    new = StorageLocation(
        object_id=next_object_id(db, "storage_location"), status="draft", name=src.name, code=src.code,
        location_type=src.location_type, note=src.note, max_load_kg=src.max_load_kg,
        width_mm=src.width_mm, depth_mm=src.depth_mm, height_mm=src.height_mm,
        is_dry=src.is_dry, is_tempered=src.is_tempered, is_hazmat=src.is_hazmat,
        is_blocked=src.is_blocked, latitude=src.latitude, longitude=src.longitude,
        address_street=src.address_street, address_zip=src.address_zip,
        address_city=src.address_city, address_country=src.address_country,
    )
    db.add(new)
    db.flush()
    log_audit(db, "storage_locations", None, f"Lagerplatz als Ersatz für {src.object_id} angelegt",
              actor_id, object_id=new.object_id)
    return new
