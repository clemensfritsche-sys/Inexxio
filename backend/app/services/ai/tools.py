"""Rechte-gescopte Tool-Schicht (ADR 004, Anforderung 1 – die Sicherheitsgrenze).

Jedes Tool ist ein dünner Wrapper um die BESTEHENDE autorisierte Service-Schicht
(``visible_orders``, ``can_view``, ``in_stock_clauses``, ``next_object_id`` …) und
läuft mit den **effektiven Rechten des Principals** (Delegation). Die verfügbare
Tool-Menge ist **rollenabhängig** (Whitelist je Rolle) – ein Kunde sieht nur
Shop-/eigene-Bestell-Tools, nie ERP-Interna. Daten-Scoping ergibt sich damit aus
der Authz, nicht aus dem Prompt.

Autonomie-Policy («erweiterte Autonomie», Entscheid des Auftraggebers):
* **Lesen** – immer autonom.
* **Entwürfe anlegen** (Artikel/Auftrag, Status ``draft``, reversibel) – autonom,
  attribuiert der KI (Audit + Event), delegierender Mensch im Kontext.
* **Kritisch** (Freigabe = erzeugt Instanzen/reserviert Bestand; später Geld/E-Mail)
  – NIE direkt: die KI legt nur einen ``AiAction``-Vorschlag an, den der Mensch im
  Chat bestätigt (``actions.py``)."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...domain import event_types
from ...models import Article, ArticleProcessStep, Event, Instance, Order, UserProfile
from ..admin import log_audit
from ..events import emit
from ..inventory import in_stock_clauses
from ..objects import next_object_id
from ..orders import visible_orders
from .principal import AiPrincipal

_LIMIT = 25   # harte Obergrenze je Tool-Antwort (Kontext-/Kostenbudget)


def _num(oid: int | None) -> str | None:
    return str(oid) if oid is not None else None


# ─── Lese-Tools (Grounding) ────────────────────────────────────────────────────────

def _t_list_articles(db: Session, p: AiPrincipal, args: dict) -> Any:
    q = db.query(Article).filter(Article.is_active == True)
    if args.get("status"):
        q = q.filter(Article.status == args["status"])
    if args.get("query"):
        q = q.filter(Article.name.ilike(f"%{args['query']}%"))
    rows = q.order_by(Article.object_id.desc()).limit(_LIMIT).all()
    return [{
        "object_id": _num(a.object_id), "name": a.name, "status": a.status,
        "unit": a.unit, "serialization": a.serialization,
        "material": a.material, "landed_unit_cost": str(a.landed_unit_cost) if a.landed_unit_cost is not None else None,
    } for a in rows]


def _t_get_article(db: Session, p: AiPrincipal, args: dict) -> Any:
    a = (
        db.query(Article)
        .filter(Article.object_id == int(args["object_id"]), Article.is_active == True)
        .first()
    )
    if not a:
        return {"error": "Artikel nicht gefunden"}
    stock = (
        db.query(func.coalesce(func.sum(Instance.quantity - Instance.reserved_quantity), 0))
        .filter(Instance.article_id == a.id, Instance.is_active == True, *in_stock_clauses())
        .scalar()
    )
    return {
        "object_id": _num(a.object_id), "name": a.name, "status": a.status,
        "unit": a.unit, "serialization": a.serialization, "size": a.size,
        "weight_kg": str(a.weight_kg) if a.weight_kg is not None else None,
        "material": a.material, "surface": a.surface,
        "min_order_qty": str(a.min_order_qty) if a.min_order_qty is not None else None,
        "safety_stock": str(a.safety_stock) if a.safety_stock is not None else None,
        "landed_unit_cost": str(a.landed_unit_cost) if a.landed_unit_cost is not None else None,
        "free_stock": int(stock or 0),
        "sales_published": a.sales_published,
    }


def _article_ref(db: Session, article_pk: int | None) -> dict | None:
    """Interne Artikel-PK → sprechende Referenz (Objektnummer + Name) fürs Modell."""
    if article_pk is None:
        return None
    a = db.query(Article.object_id, Article.name).filter(Article.id == article_pk).first()
    return {"object_id": _num(a[0]), "name": a[1]} if a else None


def _t_list_orders(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Aufträge – über ``visible_orders`` gescopt (Staff alles, Lieferant nur eigene)."""
    q = visible_orders(db, p.effective)
    if args.get("status"):
        q = q.filter(Order.status == args["status"])
    rows = q.order_by(Order.object_id.desc()).limit(_LIMIT).all()
    return [{
        "object_id": _num(o.object_id), "status": o.status,
        "article": _article_ref(db, o.article_id), "quantity": o.quantity,
        "reason": o.reason, "desired_delivery_date": str(o.desired_delivery_date) if o.desired_delivery_date else None,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    } for o in rows]


def _t_get_order(db: Session, p: AiPrincipal, args: dict) -> Any:
    o = visible_orders(db, p.effective).filter(Order.object_id == int(args["object_id"])).first()
    if not o:
        return {"error": "Auftrag nicht gefunden (oder keine Berechtigung)"}
    return {
        "object_id": _num(o.object_id), "status": o.status,
        "article": _article_ref(db, o.article_id), "quantity": o.quantity, "reason": o.reason,
        "parent_order_id": _num(o.parent_order_id),
        "released_at": o.released_at.isoformat() if o.released_at else None,
        "completed_at": o.completed_at.isoformat() if o.completed_at else None,
    }


def _t_inventory(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Freier Bestand je Artikel (verbrauchbar = quality=passed & disposition=in_stock)."""
    q = (
        db.query(Article.object_id, Article.name, Article.unit,
                 func.coalesce(func.sum(Instance.quantity - Instance.reserved_quantity), 0))
        .join(Instance, Instance.article_id == Article.id)
        .filter(Article.is_active == True, Instance.is_active == True, *in_stock_clauses())
        .group_by(Article.object_id, Article.name, Article.unit)
    )
    if args.get("article_object_id"):
        q = q.filter(Article.object_id == int(args["article_object_id"]))
    rows = q.order_by(Article.object_id.desc()).limit(_LIMIT).all()
    return [{"article_object_id": _num(r[0]), "name": r[1], "unit": r[2], "free_stock": int(r[3])}
            for r in rows]


def _t_recent_events(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Domain-Event-Strom (nur Staff) – die Faktenquelle für «was ist passiert?»."""
    q = db.query(Event)
    if args.get("object_id"):
        q = q.filter(Event.object_id == int(args["object_id"]))
    if args.get("event_type"):
        q = q.filter(Event.event_type == args["event_type"])
    rows = q.order_by(Event.id.desc()).limit(min(int(args.get("limit") or _LIMIT), _LIMIT)).all()
    return [{
        "event_type": e.event_type, "object_type": e.object_type,
        "object_id": _num(e.object_id), "payload": e.payload,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    } for e in rows]


def _t_shop_products(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Shop-Sortiment (Kaufberatung) – über ``sales.can_view`` gescopt: public für alle,
    private nur für zugewiesene Kunden. Kein ERP-Detail, nur Verkaufsdaten."""
    from .. import sales as sales_svc
    user = p.effective if p.on_behalf_of else None
    products = sales_svc.list_products(db, user, "CHF", "CH", "de")
    needle = (args.get("query") or "").strip().lower()
    out = []
    for prod in products:
        title = (prod.get("title") or prod.get("name") or "")
        if needle and needle not in title.lower():
            continue
        out.append({
            "object_id": _num(prod.get("object_id")),
            "title": title,
            "subtitle": prod.get("subtitle"),
            "fulfillment": prod.get("fulfillment"),
            "prices": [
                {"kind": pr.get("kind"), "interval": pr.get("interval"),
                 "sub_type": pr.get("sub_type"), "view": pr.get("view")}
                for pr in (prod.get("prices") or [])
            ],
        })
        if len(out) >= _LIMIT:
            break
    return out


def _t_my_orders(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Eigene Shop-Bestellungen des Kunden (exakt die «Meine Bestellungen»-Sicht)."""
    from .. import sales as sales_svc
    if not p.on_behalf_of:
        return []
    rows = sales_svc.list_customer_orders(db, p.on_behalf_of.id)
    return [{
        "order_object_id": _num(r.get("order_object_id")),
        "title": r.get("title"), "status": r.get("status"),
        "quantity": r.get("quantity"),
        "gross_total": str(r.get("gross_total")) if r.get("gross_total") is not None else None,
        "currency": r.get("currency"),
        "is_subscription": r.get("is_subscription"),
        "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
    } for r in rows[:_LIMIT]]


# ─── Schreib-Tools (erweiterte Autonomie: Entwürfe direkt, Kritisches als Vorschlag) ─

def _t_create_article_draft(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Artikel-ENTWURF anlegen – derselbe Pfad wie ``POST /articles`` (reversibel,
    Status draft). Attribution: KI (Audit/Event), Mensch als Delegations-Kontext."""
    name = (args.get("name") or "").strip()
    if not name:
        return {"error": "Name ist Pflicht"}

    def _dec(key: str) -> Decimal | None:
        v = args.get(key)
        if v in (None, ""):
            return None
        try:
            return Decimal(str(v))
        except InvalidOperation:
            return None

    article = Article(
        object_id=next_object_id(db, "article"),
        status="draft",
        name=name,
        unit=(args.get("unit") or "Stk"),
        serialization=(args.get("serialization") or "unit"),
        size=args.get("size") or None,
        weight_kg=_dec("weight_kg"),
        material=args.get("material") or None,
        surface=args.get("surface") or None,
        min_order_qty=_dec("min_order_qty"),
        safety_stock=_dec("safety_stock"),
    )
    db.add(article)
    db.flush()
    log_audit(db, "articles", None,
              f"Artikel '{article.name}' per KI angelegt (im Auftrag von {p.effective.display_name})",
              p.actor.id, object_id=article.object_id)
    emit(db, "ai.article_created", object_type="article", object_id=article.object_id,
         payload={"name": article.name, "on_behalf_of": p.effective.id}, actor_id=p.actor.id)
    db.commit()
    return {"created": True, "object_id": _num(article.object_id), "name": article.name,
            "status": "draft", "hint": "Entwurf – Prozess & Freigabe wie gewohnt im ERP."}


def _t_create_order_draft(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Auftrags-ENTWURF anlegen (Artikel + Menge) – reversibel; die Freigabe bleibt
    ein kritischer Schritt (Vorschlag/Genehmigung bzw. ERP-Knopf)."""
    article = (
        db.query(Article)
        .filter(Article.object_id == int(args["article_object_id"]), Article.is_active == True)
        .first()
    )
    if not article:
        return {"error": "Artikel nicht gefunden"}
    if article.status != "released":
        return {"error": "Nur freigegebene Artikel können in einem Auftrag referenziert werden"}
    try:
        qty = int(args.get("quantity") or 0)
    except (TypeError, ValueError):
        qty = 0
    if qty <= 0:
        return {"error": "Menge muss > 0 sein"}
    desired = None
    if args.get("desired_delivery_date"):
        try:
            desired = date.fromisoformat(str(args["desired_delivery_date"]))
        except ValueError:
            return {"error": "Ungültiges Datum (erwartet YYYY-MM-DD)"}
    order = Order(
        object_id=next_object_id(db, "order"),
        status="draft",
        # Auftrag referenziert den Artikel über die INTERNE PK (siehe routers/orders._validate_article).
        article_id=article.id,
        quantity=qty,
        desired_delivery_date=desired,
    )
    db.add(order)
    db.flush()
    log_audit(db, "orders", None,
              f"Auftrag per KI angelegt: {qty}× '{article.name}' (im Auftrag von {p.effective.display_name})",
              p.actor.id, object_id=order.object_id)
    emit(db, "ai.order_created", object_type="order", object_id=order.object_id,
         payload={"article_id": article.object_id, "quantity": qty, "on_behalf_of": p.effective.id},
         actor_id=p.actor.id)
    db.commit()
    return {"created": True, "object_id": _num(order.object_id), "status": "draft",
            "article": article.name, "quantity": qty,
            "hint": "Entwurf – die Freigabe ist ein separater, bestätigungspflichtiger Schritt."}


def _t_get_order_steps(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Die Prozessschritte eines Auftrags lesen (Reihenfolge, Typ, Label)."""
    o = visible_orders(db, p.effective).filter(Order.object_id == int(args["object_id"])).first()
    if not o:
        return {"error": "Auftrag nicht gefunden (oder keine Berechtigung)"}
    rows = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.order_id == o.id, ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )
    return {
        "order_object_id": _num(o.object_id), "status": o.status,
        "steps": [{"step_id": s.id, "type": s.step_type, "label": event_types.label(s.step_type)}
                  for s in rows],
    }


def _t_add_order_step(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Einen Prozessschritt an einen Auftrags-ENTWURF anhängen (reversibel) – über
    denselben Pfad wie der ERP-Prozess-Editor (`POST /orders/{id}/steps`)."""
    from ...routers.article_process import _create, _order_owner
    from ...schemas.article_process_step import ArticleProcessStepCreate
    step_type = args.get("step_type")
    if step_type not in event_types.ORDER_STEP_TYPES:
        return {"error": f"Unbekannter Schritt-Typ. Erlaubt: {', '.join(event_types.ORDER_STEP_TYPES)}"}
    o = visible_orders(db, p.effective).filter(Order.object_id == int(args["order_object_id"])).first()
    if not o:
        return {"error": "Auftrag nicht gefunden (oder keine Berechtigung)"}
    if o.status != "draft":
        return {"error": f"Auftrag ist '{o.status}' – Schritte lassen sich nur im Entwurf hinzufügen"}
    try:
        data = ArticleProcessStepCreate(
            step_type=step_type,
            mode=("consume" if step_type == "resource" else "supplier"),
        )
        resp = _create(db, _order_owner(db, o.object_id), data, p.actor)
    except HTTPException as e:
        return {"error": str(e.detail)}
    emit(db, "ai.order_step_added", object_type="order", object_id=o.object_id,
         payload={"step_type": step_type, "on_behalf_of": p.effective.id}, actor_id=p.actor.id)
    db.commit()
    return {"added": True, "order_object_id": _num(o.object_id), "step_id": resp.id,
            "step_type": step_type, "label": event_types.label(step_type),
            "hint": "Schritt-Details (z. B. Ziel/Prüfmaske) können im ERP-Prozess-Editor ergänzt werden."}


def _t_propose_release_order(db: Session, p: AiPrincipal, args: dict) -> Any:
    """KRITISCH: Auftrag freigeben – nur als Vorschlag (menschliches Gate im Chat)."""
    from .actions import create_proposal
    o = visible_orders(db, p.effective).filter(Order.object_id == int(args["object_id"])).first()
    if not o:
        return {"error": "Auftrag nicht gefunden (oder keine Berechtigung)"}
    if o.status != "draft":
        return {"error": f"Auftrag ist '{o.status}' – nur Entwürfe lassen sich freigeben"}
    art = _article_ref(db, o.article_id)
    art_label = art["name"] if art else "–"
    action = create_proposal(
        db, p, "release_order",
        payload={"object_id": o.object_id},
        summary=f"Auftrag {o.object_id} freigeben ({o.quantity or '–'}× {art_label})",
        target_object_id=o.object_id,
    )
    return {"proposed": True, "action_id": action.id,
            "summary": action.summary,
            "hint": "Wartet auf menschliche Bestätigung (Karte im Chat)."}


# ─── Registry: Definitionen (Anthropic-Tool-Schema) + Rollen-Whitelist ─────────────

ToolFn = Callable[[Session, AiPrincipal, dict], Any]


def _tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required or [],
        },
    }


_DEFINITIONS: dict[str, dict] = {
    "list_articles": _tool(
        "list_articles",
        "ERP-Artikel suchen/auflisten (Stammdaten). Nutze dies für Fragen zu Artikeln.",
        {"query": {"type": "string", "description": "Namenssuche (Teilstring)"},
         "status": {"type": "string", "enum": ["draft", "released", "inactive"]}},
    ),
    "get_article": _tool(
        "get_article",
        "Einen Artikel im Detail lesen (inkl. freiem Lagerbestand).",
        {"object_id": {"type": "integer", "description": "9-stellige Objektnummer"}},
        ["object_id"],
    ),
    "list_orders": _tool(
        "list_orders",
        "Aufträge auflisten (automatisch auf die Rechte der Person gescopt).",
        {"status": {"type": "string", "enum": ["draft", "released", "completed", "inactive"]}},
    ),
    "get_order": _tool(
        "get_order",
        "Einen Auftrag im Detail lesen.",
        {"object_id": {"type": "integer"}},
        ["object_id"],
    ),
    "inventory_summary": _tool(
        "inventory_summary",
        "Freier Lagerbestand je Artikel (verbrauchbar: freigegeben & am Lager, abzüglich Reservierungen).",
        {"article_object_id": {"type": "integer", "description": "optional: nur dieser Artikel"}},
    ),
    "recent_events": _tool(
        "recent_events",
        "Die letzten Domain-Events (was ist im System passiert). Optional nach Objekt/Typ gefiltert.",
        {"object_id": {"type": "integer"}, "event_type": {"type": "string"},
         "limit": {"type": "integer"}},
    ),
    "shop_products": _tool(
        "shop_products",
        "Shop-Sortiment für Kaufberatung (publizierte Produkte mit Preisen, CHF).",
        {"query": {"type": "string", "description": "Titelsuche (Teilstring)"}},
    ),
    "my_orders": _tool(
        "my_orders",
        "Die eigenen Shop-Bestellungen der angemeldeten Person (Status, Betrag).",
        {},
    ),
    "create_article_draft": _tool(
        "create_article_draft",
        "Einen neuen Artikel als ENTWURF anlegen (reversibel). Nur wenn die Person das ausdrücklich möchte.",
        {"name": {"type": "string"}, "unit": {"type": "string", "enum": ["Stk", "m", "kg", "l"]},
         "serialization": {"type": "string", "enum": ["unit", "batch"]},
         "size": {"type": "string"}, "weight_kg": {"type": "string"},
         "material": {"type": "string"}, "surface": {"type": "string"},
         "min_order_qty": {"type": "string"}, "safety_stock": {"type": "string"}},
        ["name"],
    ),
    "create_order_draft": _tool(
        "create_order_draft",
        "Einen Auftrag als ENTWURF anlegen (Artikel + Menge, reversibel). Danach ggf. mit "
        "add_order_step Prozessschritte anhängen. Nur auf ausdrücklichen Wunsch.",
        {"article_object_id": {"type": "integer", "description": "Objektnummer des (freigegebenen) Artikels"},
         "quantity": {"type": "integer"},
         "desired_delivery_date": {"type": "string", "description": "YYYY-MM-DD, optional"}},
        ["article_object_id", "quantity"],
    ),
    "get_order_steps": _tool(
        "get_order_steps",
        "Die Prozessschritte (Ablauf) eines Auftrags lesen.",
        {"object_id": {"type": "integer"}},
        ["object_id"],
    ),
    "add_order_step": _tool(
        "add_order_step",
        "Einen Prozessschritt an einen Auftrags-Entwurf anhängen. Schritt-Typen: "
        "purchase (Beschaffung), resource (Ressource/Material/Betriebsmittel), "
        "inspection (Datenerfassung/Prüfung), movement (Bewegung/Einlagern), "
        "scrap (Verschrotten), sale (Verkauf), document (Dokument).",
        {"order_object_id": {"type": "integer"},
         "step_type": {"type": "string",
                       "enum": ["purchase", "resource", "inspection", "movement", "scrap", "sale", "document"]}},
        ["order_object_id", "step_type"],
    ),
    "propose_release_order": _tool(
        "propose_release_order",
        "KRITISCH: die Freigabe eines Auftrags VORSCHLAGEN (erzeugt Instanzen/reserviert Bestand). "
        "Wird erst nach menschlicher Bestätigung ausgeführt.",
        {"object_id": {"type": "integer"}},
        ["object_id"],
    ),
}

_EXECUTORS: dict[str, ToolFn] = {
    "list_articles": _t_list_articles,
    "get_article": _t_get_article,
    "list_orders": _t_list_orders,
    "get_order": _t_get_order,
    "inventory_summary": _t_inventory,
    "recent_events": _t_recent_events,
    "shop_products": _t_shop_products,
    "my_orders": _t_my_orders,
    "create_article_draft": _t_create_article_draft,
    "create_order_draft": _t_create_order_draft,
    "get_order_steps": _t_get_order_steps,
    "add_order_step": _t_add_order_step,
    "propose_release_order": _t_propose_release_order,
}

# Rollen-Whitelist: die Rolle begrenzt die Tool-Menge (und damit die Angriffsfläche).
_BY_ROLE: dict[str, tuple[str, ...]] = {
    "admin": ("list_articles", "get_article", "list_orders", "get_order", "inventory_summary",
              "recent_events", "shop_products", "create_article_draft", "create_order_draft",
              "get_order_steps", "add_order_step", "propose_release_order"),
    "employee": ("list_articles", "get_article", "list_orders", "get_order", "inventory_summary",
                 "recent_events", "shop_products", "create_article_draft", "create_order_draft",
                 "get_order_steps", "add_order_step", "propose_release_order"),
    "supplier": ("list_orders", "get_order"),
    "customer": ("shop_products", "my_orders"),
    # Autonome KI-Läufe (ohne Delegation): nur lesen – bewusst eng.
    "ai": ("list_articles", "get_article", "inventory_summary", "recent_events"),
}


def tools_for(principal: AiPrincipal) -> list[dict]:
    names = _BY_ROLE.get(principal.effective_role, ())
    return [_DEFINITIONS[n] for n in names]


def execute(db: Session, principal: AiPrincipal, name: str, args: dict) -> Any:
    """Tool ausführen – NUR wenn es in der Rollen-Whitelist des Principals liegt.
    (Zweite Verteidigungslinie: selbst ein halluzinierter Tool-Aufruf ausserhalb der
    Whitelist wird hier abgewiesen, nicht erst im Modell.)"""
    if name not in _BY_ROLE.get(principal.effective_role, ()):
        return {"error": "Dieses Tool ist für diese Rolle nicht verfügbar"}
    fn = _EXECUTORS.get(name)
    if not fn:
        return {"error": f"Unbekanntes Tool '{name}'"}
    try:
        return fn(db, principal, args or {})
    except Exception as e:
        db.rollback()
        print(f"WARNING: AI tool '{name}' failed: {type(e).__name__}: {e}", flush=True)
        return {"error": "Tool-Ausführung fehlgeschlagen"}
