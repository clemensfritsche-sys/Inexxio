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

    umlagern. Reaktivieren erlaubt.

Ersetzen: alter Datensatz inaktiv + **Duplikat als Entwurf** + Verknüpfung
    ``replaced_by_id`` (Nachvollziehbarkeit „was hat was ersetzt").
"""

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..models import Article, ArticleProcessStep, Instance, Order, OrderLine
from .admin import log_audit
from .events import emit
from .inventory import in_stock_clauses
from .objects import next_object_id
from .processes import has_custom_steps
from .reservation import release


def _order_article_filter(db: Session, ids: set[int]):
    """Auftrag referenziert einen der Artikel – direkt (``article_id``, Einzel-Artikel-
    Auftrag) ODER als Position eines Mehrpositionen-Auftrags (``order_lines``); sonst
    würde eine Artikel-Deaktivierung einen laufenden Mehrpositionen-Verkauf übersehen."""
    line_order_ids = db.query(OrderLine.order_id).filter(
        OrderLine.article_id.in_(ids), OrderLine.is_active == True)
    return or_(Order.article_id.in_(ids), Order.id.in_(line_order_ids))


# ─── Artikel: Kaskade über consume-Ressourcen ────────────────────────────────

def _consume_parent_map(db: Session) -> dict[int, set[int]]:
    """Umkehr-Index Komponente → {Eltern-Artikel, die sie verbrauchen}.

    Eltern = der Artikel, dessen **Artikel-Prozess** die Komponente in einer
    ``consume``-Zeile führt. Betriebsmittel-Zeilen (``tool``) kaskadieren NICHT."""
    out: dict[int, set[int]] = {}
    steps = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.step_type == "resource",
                ArticleProcessStep.is_active == True,
                ArticleProcessStep.article_id.isnot(None),
                ArticleProcessStep.order_id.is_(None))
        .all()
    )
    for s in steps:
        parent = s.article_id
        if not parent:
            continue
        for line in (s.resource_lines or []):
            aid = line.get("article_id")
            if aid is None or (line.get("mode") or "consume") != "consume":
                continue
            out.setdefault(aid, set()).add(parent)
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
        .filter(Order.is_active == True, Order.status == "released", _order_article_filter(db, ids))
        .order_by(Order.object_id)
        .all()
    )
    stock = (
        db.query(func.coalesce(func.sum(Instance.quantity), 0))
        .filter(Instance.is_active == True, Instance.article_id.in_(ids), *in_stock_clauses())
        .scalar()
    )
    return {"articles": parent_arts, "orders": orders, "stock": float(stock or 0)}


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
        Order.is_active == True, Order.status == "draft", _order_article_filter(db, ids)
    ).all():
        o.status = "inactive"
    # Freigegebene Aufträge: abbrechen (sonst auslaufen lassen). Ein Abbruch erzwingt – wie
    # das Auftrag-«Abbrechen» – einen **Folgeauftrag** für die im Prozess befindlichen Instanzen
    # (keine herrenlosen/vernichteten Teile). Nur Aufträge OHNE aktive Instanzen werden direkt inaktiv.
    if orders_mode == "cancel":
        from .deviation import abort_parent, create_deviation
        from .subject import order_active_instances
        for o in db.query(Order).filter(
            Order.is_active == True, Order.status == "released", _order_article_filter(db, ids)
        ).all():
            if order_active_instances(db, o):
                # Abweichungsauftrag übernimmt die Instanzen, das Original ist sofort abgebrochen.
                devi = create_deviation(db, o, None, actor_id, title_prefix="Abbruch von")
                abort_parent(db, o, devi, actor_id)
            else:
                log_audit(db, "orders", "status", "inactive", actor_id,
                          object_id=o.object_id, old_value=o.status)
                o.status = "inactive"
                cancel_order_effects(db, o, actor_id)
    emit(db, "article.deactivated", object_type="article", object_id=article.object_id,
         payload={"orders_mode": orders_mode, "affected": len(ids)}, actor_id=actor_id)


# ─── Auftrag: Abbruch ─────────────────────────────────────────────────────────

def cancel_order_effects(db: Session, order: Order, actor_id: int,
                         keep_instances: bool = False) -> None:
    """Beim Abbruch eines Auftrags: Reservierungen UND Bestands-Subjekte freigeben
    (Verkauf/Entnahme – zurück in den freien Bestand). Setzt NICHT den Status (Aufrufer).

    ``keep_instances`` – beim **Abbruch mit Folgeauftrag**: die im Prozess befindlichen
    Instanzen werden NICHT deaktiviert; sie gehören jetzt dem Folgeauftrag (kein
    Verschwinden physisch vorhandener Teile)."""
    # Reservierte Komponenten + als Subjekt gewählte Bestands-Instanzen freigeben
    # (mengengenau: nur die Reservierung dieses Auftrags lösen, Instanz bleibt erhalten).
    for inst in db.query(Instance).filter(
        or_(Instance.reservations.has_key(str(order.id)),  # noqa: W601
            Instance.subject_of_order_id == order.id),
        Instance.is_active == True,
    ).all():
        release(inst, order.id)
        if inst.subject_of_order_id == order.id:
            inst.subject_of_order_id = None
    # Bei Freigabe erzeugte, noch unfertige Produkt-Instanzen deaktivieren – ausser beim
    # Abbruch mit Folgeauftrag (dort übernimmt der Folgeauftrag die Instanzen).
    if not keep_instances:
        for inst in db.query(Instance).filter(
            Instance.order_id == order.id, Instance.is_active == True, Instance.quality == "pending"
        ).all():
            log_audit(db, "instances", "is_active", "false", actor_id,
                      object_id=inst.object_id, old_value="true")
            inst.is_active = False
    # **Nachschub-Kinder sind KEINE Ausnahme:** sie sind normale Produktionsaufträge. Fällt der
    # Bedarf weg (Eltern inaktiv), löst sich nur ihr Peg auf – ``process._peg_supply_to_parent``
    # ist bei totem Eltern ein No-op, ihr Output fliesst automatisch in den freien Bestand
    # (kein Sondercode, keine vernichteten Teile). Wer einen laufenden Nachschub stoppen will,
    # bricht ihn mit demselben Mechanismus ab.
    emit(db, "order.cancelled", object_type="order", object_id=order.object_id, actor_id=actor_id)


# ─── Ersetzen: Duplikat als Entwurf + Verknüpfung ────────────────────────────

def _copy_steps(db: Session, *, src_article_id: int | None = None, src_order_id: int | None = None,
                dst_article_id: int | None = None, dst_order_id: int | None = None) -> None:
    """Aktive Prozessschritte (Artikel- oder Auftrags-Prozess) tief kopieren."""
    q = db.query(ArticleProcessStep).filter(ArticleProcessStep.is_active == True)
    if src_article_id is not None:
        q = q.filter(ArticleProcessStep.article_id == src_article_id,
                     ArticleProcessStep.order_id.is_(None))
    else:
        q = q.filter(ArticleProcessStep.order_id == src_order_id)
    for s in q.order_by(ArticleProcessStep.position, ArticleProcessStep.id).all():
        db.add(ArticleProcessStep(
            article_id=dst_article_id, order_id=dst_order_id,
            position=s.position, step_type=s.step_type, companion=s.companion, mode=s.mode,
            supplier_id=s.supplier_id, webshop_url=s.webshop_url, shared_fields=s.shared_fields,
            sample_percent=s.sample_percent, capture_fields=s.capture_fields,
            target_location_type=s.target_location_type, target_location_id=s.target_location_id,
            resource_lines=s.resource_lines,
            # FIX: Dokument-Konfiguration (Migration 066) mitkopieren – ohne diese Felder
            # verlor «Ersetzen» (neue Fassung eines Rechts-/Publikums-Dokuments!) und die
            # Wiederkehr (_spawn_recurrence) still die Freigabe-Parteien, das Anerkennungs-
            # Publikum und die Sichtbarkeit: der Nachfolger hätte NIE mehr gated.
            doc_signers=s.doc_signers, sign_sequential=s.sign_sequential,
            doc_audience=s.doc_audience, doc_audience_roles=s.doc_audience_roles,
            doc_audience_person_ids=s.doc_audience_person_ids, doc_visibility=s.doc_visibility,
        ))
    db.flush()


def duplicate_article(db: Session, src: Article, actor_id: int) -> Article:
    """Spezifikation in einen neuen Entwurf kopieren – inkl. des **Artikel-Prozesses**
    (die Schritte werden mitkopiert; es gibt kein wiederverwendbares Prozess-Objekt)."""
    new = Article(
        object_id=next_object_id(db, "article"), status="draft",
        name=src.name, unit=src.unit, serialization=src.serialization, size=src.size,
        weight_kg=src.weight_kg,
        material=src.material, cad_url=src.cad_url, surface=src.surface,
        min_order_qty=src.min_order_qty, safety_stock=src.safety_stock,
        supplier_article_number=src.supplier_article_number,
        # FIX: restliche Spezifikations-/Steuerfelder mitkopieren – vorher verlor der
        # Nachfolger still Gefahrgut-Flag, Zielbestand, den fixierten Standort und v. a.
        # die Beschaffungsquelle (Artikel-Default) – ein purchase-Artikel liess sich dann
        # ohne Neueingabe nicht mehr freigeben (has_source-Gate).
        is_hazmat=src.is_hazmat, reorder_target=src.reorder_target,
        fixed_location_lat=src.fixed_location_lat, fixed_location_lng=src.fixed_location_lng,
        fixed_location_street=src.fixed_location_street, fixed_location_zip=src.fixed_location_zip,
        fixed_location_city=src.fixed_location_city, fixed_location_country=src.fixed_location_country,
        procurement_mode=src.procurement_mode, default_supplier_id=src.default_supplier_id,
        default_webshop_url=src.default_webshop_url,
    )
    db.add(new)
    db.flush()
    _copy_steps(db, src_article_id=src.id, dst_article_id=new.id)
    # Verkaufs-Profil + Preise + Zielgruppe mitkopieren, damit das Shop-Listing über den
    # Versionswechsel kanonisch fortbesteht (siehe ``services/sales.copy_sales_profile``).
    from .selling import copy_sales_profile
    copy_sales_profile(db, src, new)
    log_audit(db, "articles", None, f"Artikel als Ersatz für {src.object_id} angelegt",
              actor_id, object_id=new.object_id)
    return new


def duplicate_order(db: Session, src: Order, actor_id: int) -> Order:
    new = Order(object_id=next_object_id(db, "order"), status="draft", title=src.title,
                article_id=src.article_id, quantity=src.quantity,
                desired_delivery_date=src.desired_delivery_date)
    db.add(new)
    db.flush()
    if has_custom_steps(db, src):   # individuellen Ablauf mitkopieren
        _copy_steps(db, src_order_id=src.id, dst_order_id=new.id)
    log_audit(db, "orders", None, f"Auftrag als Ersatz für {src.object_id} angelegt",
              actor_id, object_id=new.object_id)
    return new
