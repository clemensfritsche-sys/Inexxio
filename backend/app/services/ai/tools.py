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

import ipaddress
import json as _json
import re
import socket
from datetime import date
from decimal import Decimal, InvalidOperation
from html import unescape as _html_unescape
from typing import Any, Callable
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...domain import event_types
from ...models import (
    Article, ArticleProcessStep, Event, Instance, Order, UserProfile,
)
from ..admin import log_audit
from ..events import emit
from ..inventory import in_stock_clauses
from ..objects import next_object_id
from ..orders import visible_orders
from .principal import AiPrincipal

_LIMIT = 25   # harte Obergrenze je Tool-Antwort (Kontext-/Kostenbudget)


def _num(oid: int | None) -> str | None:
    return str(oid) if oid is not None else None


def _qnum(v) -> float | None:
    """Menge (Decimal/None) → JSON-tauglicher ``float`` für Tool-Antworten (Bruchmengen)."""
    return float(v) if v is not None else None


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
        "free_stock": _qnum(stock or 0),
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
        "article": _article_ref(db, o.article_id), "quantity": _qnum(o.quantity),
        "reason": o.reason, "desired_delivery_date": str(o.desired_delivery_date) if o.desired_delivery_date else None,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    } for o in rows]


def _t_get_order(db: Session, p: AiPrincipal, args: dict) -> Any:
    o = visible_orders(db, p.effective).filter(Order.object_id == int(args["object_id"])).first()
    if not o:
        return {"error": "Auftrag nicht gefunden (oder keine Berechtigung)"}
    steps = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.order_id == o.id, ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )
    return {
        "object_id": _num(o.object_id), "status": o.status,
        "article": _article_ref(db, o.article_id), "quantity": _qnum(o.quantity), "reason": o.reason,
        "parent_order_id": _num(o.parent_order_id),
        "released_at": o.released_at.isoformat() if o.released_at else None,
        "completed_at": o.completed_at.isoformat() if o.completed_at else None,
        "steps": [{"step_id": s.id, "type": s.step_type, "label": event_types.label(s.step_type)}
                  for s in steps],
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
    return [{"article_object_id": _num(r[0]), "name": r[1], "unit": r[2], "free_stock": _qnum(r[3])}
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

def _t_article_name_suggestions(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Bereits verwendete/ähnliche Artikelnamen zu einer Bezeichnung (lexikalisch, ohne KI) –
    damit die KI **vor** dem Anlegen prüft, ob ein passender Name schon existiert (Dubletten
    vermeiden). Liefert je Vorschlag Name + wie oft er vorkommt (``count``) + Ähnlichkeit."""
    from ...services import article_names
    q = str(args.get("query") or "").strip()
    limit = min(int(args.get("limit") or 8), 20)
    return [s.model_dump() for s in article_names.suggest(db, q, limit)]


def _clean_article_fields(args: dict) -> tuple[dict, str | None]:
    """KI-Eingaben für einen Artikel gegen **dieselben Regeln** normalisieren/prüfen wie
    der HTTP-Pfad (``schemas/article.py``). So wird ein falsch formatierter Wert (z. B.
    Grösse «15cm» oder «15 cm») mit einer **klaren Fehlermeldung** abgelehnt, die die KI im
    nächsten Schritt selbst korrigieren kann – statt roh in der DB zu landen. Liefert die
    geprüften Felder (nur die übergebenen – teilupdate-tauglich) ODER eine Fehlermeldung.

    Enthält NIE das Pflicht-`name`-Gate für ein Teilupdate: der Aufrufer entscheidet, ob
    ein fehlender Name ein Fehler ist (Anlage) oder erlaubt (Änderung)."""
    from ...schemas.article import (
        ALLOWED_SERIALIZATION, ALLOWED_UNITS, clean_article_name, normalize_size, validate_weight,
    )
    out: dict = {}
    if args.get("name") is not None:
        try:
            out["name"] = clean_article_name(str(args["name"]), required=True)
        except ValueError as e:
            return {}, str(e)
    if args.get("unit"):
        if args["unit"] not in ALLOWED_UNITS:
            return {}, f"Einheit muss eine von {', '.join(ALLOWED_UNITS)} sein"
        out["unit"] = args["unit"]
    if args.get("serialization"):
        if args["serialization"] not in ALLOWED_SERIALIZATION:
            return {}, "Serialisierung muss 'unit' (Einzelteil) oder 'batch' (Charge) sein"
        out["serialization"] = args["serialization"]
    if args.get("size") not in (None, ""):
        try:
            out["size"] = normalize_size(str(args["size"]))   # mm, aufsteigend, 'x'-getrennt
        except ValueError as e:
            return {}, str(e)
    if args.get("weight_kg") not in (None, ""):
        try:
            out["weight_kg"] = validate_weight(Decimal(str(args["weight_kg"])))
        except (ValueError, InvalidOperation):
            return {}, ("Gewicht muss eine Zahl in kg sein (> 0, max. 3 Nachkommastellen), "
                        "z. B. 2.5 – ohne Einheit im Wert")
    for f in ("material", "cad_url", "surface", "supplier_article_number"):
        if args.get(f) not in (None, ""):
            out[f] = str(args[f]).strip() or None
    for f in ("min_order_qty", "safety_stock"):
        if args.get(f) not in (None, ""):
            try:
                out[f] = Decimal(str(args[f]))
            except InvalidOperation:
                return {}, f"Ungültiger Zahlenwert für {f}"
    return out, None


def _t_create_article_draft(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Artikel-ENTWURF anlegen – mit **denselben Feld-Validierungen** wie ``POST /articles``
    (reversibel, Status draft). Attribution: KI (Audit/Event), Mensch als Delegations-Kontext."""
    if not str(args.get("name") or "").strip():
        return {"error": "Name ist Pflicht"}
    fields, err = _clean_article_fields(args)
    if err:
        return {"error": err, "hint": "Bitte das genannte Feld korrigieren und erneut anlegen."}

    article = Article(
        object_id=next_object_id(db, "article"),
        status="draft",
        name=fields["name"],
        unit=fields.get("unit", "Stk"),
        serialization=fields.get("serialization", "unit"),
        size=fields.get("size"),
        weight_kg=fields.get("weight_kg"),
        material=fields.get("material"),
        cad_url=fields.get("cad_url"),
        surface=fields.get("surface"),
        supplier_article_number=fields.get("supplier_article_number"),
        min_order_qty=fields.get("min_order_qty"),
        safety_stock=fields.get("safety_stock"),
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
    from ...services.quantity import is_whole, to_qty
    qty = to_qty(args.get("quantity") or 0)   # Bruchmengen erlaubt (kg/m²/…)
    if qty <= 0:
        return {"error": "Menge muss > 0 sein"}
    if article.serialization == "unit" and not is_whole(qty):
        return {"error": f"«{article.name}» ist ein Einzelteil – die Menge muss eine ganze Zahl sein"}
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
            "article": article.name, "quantity": _qnum(qty),
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
    """Einen Prozessschritt an einen Auftrags-ENTWURF anhängen (reversibel) – inkl.
    optionaler Beschaffungs-/Ziel-Konfig. Alle Typen: purchase, resource, inspection,
    movement, scrap, sale, document."""
    step_type = args.get("step_type")
    if step_type not in event_types.ORDER_STEP_TYPES:
        return {"error": f"Unbekannter Schritt-Typ. Erlaubt: {', '.join(event_types.ORDER_STEP_TYPES)}"}
    o = visible_orders(db, p.effective).filter(Order.object_id == int(args["order_object_id"])).first()
    if not o:
        return {"error": "Auftrag nicht gefunden (oder keine Berechtigung)"}
    return _add_step(db, p, "order", int(o.object_id), args)


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


# ─── Erweiterte Werkzeuge: Instanzen, Benutzer, Standorte, universelle Auflösung ───

def _instance_view(db: Session, i: Instance) -> dict:
    from ..locations import location_labels
    a = db.query(Article.object_id, Article.name).filter(Article.id == i.article_id).first()
    label = location_labels(db, [(i.location_type, i.location_id)]).get((i.location_type, i.location_id))
    return {
        "object_id": _num(i.object_id), "kind": i.kind, "quantity": _qnum(i.quantity),
        "serial_number": i.serial_number,
        "article": {"object_id": _num(a[0]), "name": a[1]} if a else None,
        "quality": i.quality, "disposition": i.disposition,
        "location": label, "location_type": i.location_type,
        "released_at": i.released_at.isoformat() if i.released_at else None,
        "reserved_quantity": _qnum(i.reserved_quantity),
    }


def _t_get_instance(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Eine Instanz (konkretes Stück/Charge) lesen – inkl. zugehörigem Artikel,
    Qualität, Disposition und Standort. Damit löst die KI Instanz → Artikel selbst auf."""
    i = db.query(Instance).filter(Instance.object_id == int(args["object_id"]), Instance.is_active == True).first()
    if not i:
        return {"error": "Instanz nicht gefunden"}
    return _instance_view(db, i)


def _t_list_instances(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Instanzen auflisten/zählen – optional gefiltert nach Artikel oder Suchbegriff
    (Objektnummer/Seriennummer). Antwortet auch auf «wie viele Instanzen…»."""
    q = db.query(Instance).filter(Instance.is_active == True)
    if args.get("article_object_id"):
        a = db.query(Article.id).filter(Article.object_id == int(args["article_object_id"])).first()
        if a:
            q = q.filter(Instance.article_id == a[0])
    if args.get("disposition"):
        q = q.filter(Instance.disposition == args["disposition"])
    total = q.count()
    rows = q.order_by(Instance.object_id.desc()).limit(_LIMIT).all()
    return {"count": total, "instances": [_instance_view(db, i) for i in rows]}


def _t_list_users(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Benutzerkonten auflisten/zählen (nur Personal). Beantwortet «wie viele User…».
    Rollen: admin, employee, supplier, customer, ai (System-KI)."""
    q = db.query(UserProfile).filter(UserProfile.is_active == True)
    if args.get("role"):
        q = q.filter(UserProfile.role == args["role"])
    rows = q.order_by(UserProfile.email).all()
    needle = (args.get("query") or "").strip().lower()

    def _match(u: UserProfile) -> bool:
        if not needle:
            return True
        return needle in (u.display_name or "").lower() or needle in (u.email or "").lower()

    users = [{
        "object_id": _num(u.object_id), "name": u.display_name, "email": u.email,
        "role": u.role, "is_active": u.is_active,
    } for u in rows if _match(u)]
    by_role: dict[str, int] = {}
    for u in rows:
        if _match(u):
            by_role[u.role] = by_role.get(u.role, 0) + 1
    return {"count": len(users), "by_role": by_role, "users": users[:_LIMIT]}


def _t_get_user(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Ein Benutzerkonto im Detail lesen (nur Personal)."""
    ident = args.get("object_id")
    q = db.query(UserProfile).filter(UserProfile.is_active == True)
    u = None
    if ident is not None:
        u = q.filter(UserProfile.object_id == int(ident)).first()
    elif args.get("email"):
        u = q.filter(UserProfile.email == str(args["email"]).lower()).first()
    if not u:
        return {"error": "Benutzer nicht gefunden"}
    return {
        "object_id": _num(u.object_id), "name": u.display_name, "email": u.email,
        "role": u.role, "company_name": u.company_name, "phone": u.phone,
        "city": u.city, "country": u.country, "is_active": u.is_active,
    }


def _t_resolve_object(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Universelle Objektnummer auflösen: sagt, WAS die Nummer ist (Artikel/Auftrag/
    Instanz/Benutzer/Lagerplatz) und liefert die Kernfakten. Erster Griff bei jeder
    9-stelligen Zahl, deren Art unklar ist."""
    from ..objects import resolve_object_type
    oid = int(args["object_id"])
    t = resolve_object_type(db, oid)
    if not t:
        return {"object_id": _num(oid), "type": None, "error": "Objektnummer nicht gefunden"}
    detail: Any = {}
    if t == "article":
        detail = _t_get_article(db, p, {"object_id": oid})
    elif t == "order":
        detail = _t_get_order(db, p, {"object_id": oid})
    elif t == "instance":
        detail = _t_get_instance(db, p, {"object_id": oid})
    elif t == "user":
        detail = _t_get_user(db, p, {"object_id": oid})
    return {"object_id": _num(oid), "type": t, "detail": detail}


def _t_open_page(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Den Nutzer an die passende Stelle in der App FÜHREN (Navigation) – das Frontend
    rendert dazu einen Knopf. Kein Datenzugriff; nur eine Zielangabe. So kann die KI
    «soll ich es dir zeigen?» direkt umsetzen (z. B. zum Shop-Produkt bei Kaufinteresse)."""
    kind = args.get("kind")
    oid = args.get("object_id")
    if kind == "shop_product" and oid:
        return {"navigate": {"path": f"/shop/product?id={int(oid)}", "label": "Zum Produkt"}}
    if kind == "erp_record" and oid:
        return {"navigate": {"path": f"/erp?open={int(oid)}", "label": "Datensatz öffnen"}}
    fixed = {
        "shop": {"path": "/shop", "label": "Zum Shop"},
        "cart": {"path": "/shop/cart", "label": "Zum Warenkorb"},
        "my_orders": {"path": "/konto", "label": "Zu meinen Bestellungen"},
    }
    if kind in fixed:
        return {"navigate": fixed[kind]}
    return {"error": "Unbekanntes Navigationsziel (kind)"}


def _t_company_info(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Firmen-/Systemkonfiguration lesen (Personal) – ohne Geheimnisse (keine IBAN/Keys)."""
    from ..admin import get_or_create_settings
    s = get_or_create_settings(db)
    return {
        "object_id": _num(s.object_id), "company_name": s.company_name, "legal_form": s.legal_form,
        "address": " ".join(x for x in [s.street, s.street_nr, s.zip_code, s.city, s.country] if x),
        "uid_number": s.uid_number, "vat_number": s.vat_number,
        "email": s.email, "phone": s.phone, "website": s.website,
        "vat_method": s.vat_method, "vat_period": s.vat_period,
        "default_payment_days": s.default_payment_days,
    }


def _t_audit_log(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Audit-Log lesen (nur Admin): wer hat was wann geändert. Optional gefiltert."""
    from ...models import AuditLog
    q = db.query(AuditLog)
    if args.get("object_id"):
        q = q.filter(AuditLog.object_id == int(args["object_id"]))
    if args.get("table_name"):
        q = q.filter(AuditLog.table_name == args["table_name"])
    rows = q.order_by(AuditLog.changed_at_utc.desc()).limit(min(int(args.get("limit") or _LIMIT), _LIMIT)).all()
    uids = {r.user_id for r in rows if r.user_id}
    names = {u.id: u.display_name for u in db.query(UserProfile).filter(UserProfile.id.in_(uids)).all()} if uids else {}
    return [{
        "object_id": _num(r.object_id), "table": r.table_name, "field": r.field_name,
        "old": r.old_value, "new": r.new_value, "by": names.get(r.user_id, r.user_id),
        "at": r.changed_at_utc.isoformat() if r.changed_at_utc else None,
    } for r in rows]


def _t_update_article(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Felder eines Artikel-ENTWURFS ändern (Name, Material, Gewicht …). Nur im Entwurf –
    mit **denselben Feld-Validierungen** wie am Detailfenster (Grösse mm/aufsteigend, Gewicht kg …)."""
    a = db.query(Article).filter(Article.object_id == int(args["object_id"]), Article.is_active == True).first()
    if not a:
        return {"error": "Artikel nicht gefunden"}
    if a.status != "draft":
        return {"error": f"Artikel ist '{a.status}' – nur Entwürfe sind editierbar (sonst «Ersetzen»)"}
    fields, err = _clean_article_fields(args)   # gleiche Regeln wie die Anlage
    if err:
        return {"error": err, "hint": "Bitte das genannte Feld korrigieren und erneut ändern."}
    if not fields:
        return {"error": "Keine gültigen Felder zum Ändern übergeben"}
    for f, v in fields.items():
        setattr(a, f, v)
    changed = list(fields.keys())
    log_audit(db, "articles", ",".join(changed), "per KI geändert", p.actor.id, object_id=a.object_id)
    emit(db, "ai.article_updated", object_type="article", object_id=a.object_id,
         payload={"fields": changed, "on_behalf_of": p.effective.id}, actor_id=p.actor.id)
    db.commit()
    return {"updated": True, "object_id": _num(a.object_id), "changed": changed}


# ─── Web-Recherche (Produkt/Seite verstehen, z. B. für Beschaffung per Link) ───────

_FETCH_TIMEOUT = 15.0
_FETCH_MAX_BYTES = 900_000
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _is_public_host(host: str) -> bool:
    """SSRF-Schutz: nur öffentlich erreichbare Hosts (keine internen/Cloud-Metadaten)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified):
            return False
    return True


def _meta(html: str, *keys: str) -> str | None:
    for k in keys:
        for pat in (
            r'<meta[^>]+(?:property|name)=["\']' + re.escape(k) + r'["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']' + re.escape(k) + r'["\']',
        ):
            m = re.search(pat, html, re.I)
            if m:
                return _html_unescape(m.group(1)).strip()
    return None


def _extract_product(url: str, html: str) -> dict:
    title = None
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        title = _html_unescape(re.sub(r"\s+", " ", m.group(1))).strip()
    product: dict = {}
    for block in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                            html, re.I | re.S):
        try:
            data = _json.loads(block.strip())
        except Exception:
            continue
        for node in (data if isinstance(data, list) else [data]):
            if not isinstance(node, dict):
                continue
            t = node.get("@type")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                offers = node.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                brand = node.get("brand")
                img = node.get("image")
                product = {
                    "name": node.get("name"),
                    "brand": brand.get("name") if isinstance(brand, dict) else brand,
                    "material": node.get("material"), "color": node.get("color"),
                    "sku": node.get("sku") or node.get("mpn"),
                    "gtin": node.get("gtin13") or node.get("gtin"),
                    "price": (offers or {}).get("price"),
                    "currency": (offers or {}).get("priceCurrency"),
                    "image": img if isinstance(img, str) else (img[0] if isinstance(img, list) and img else None),
                }
                break
        if product:
            break
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    text = _html_unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))).strip()[:1500]
    return {
        "final_url": url,
        "title": _meta(html, "og:title", "twitter:title") or title,
        "description": _meta(html, "og:description", "description"),
        "image": (product.get("image") if product else None) or _meta(html, "og:image", "twitter:image"),
        "product": {k: v for k, v in (product or {}).items() if v} or None,
        "text_excerpt": text,
        "note": "Automatisch aus der Seite extrahiert – plausibel prüfen. Manche Shops (z. B. Amazon) "
                "liefern evtl. nur Titel/Bild; ergänze offensichtliche Angaben sinnvoll.",
    }


def _t_fetch_web_page(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Eine öffentliche Webseite/Produktseite abrufen und Kerninfos extrahieren
    (Titel, Beschreibung, Bild, Preis/Marke/Material aus strukturierten Daten)."""
    import httpx
    url = str(args.get("url") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return {"error": "Ungültige URL (http/https erforderlich)"}
    if not _is_public_host(parsed.hostname):
        return {"error": "URL nicht erlaubt (nur öffentliche Adressen)"}
    try:
        with httpx.Client(follow_redirects=True, timeout=_FETCH_TIMEOUT,
                          headers={"User-Agent": _UA, "Accept-Language": "de,en;q=0.8"}) as c:
            r = c.get(url)
            fh = urlparse(str(r.url)).hostname
            if fh and not _is_public_host(fh):
                return {"error": "Weiterleitung auf nicht erlaubte Adresse"}
            html = r.text[:_FETCH_MAX_BYTES]
    except Exception as e:
        return {"error": f"Seite nicht erreichbar: {type(e).__name__}"}
    return _extract_product(str(r.url), html)


# ─── Prozessschritte an Artikel/Auftrag anhängen (mit Beschaffungs-/Ziel-Konfig) ───

def _build_step_create(db: Session, p: AiPrincipal, args: dict):
    """ArticleProcessStepCreate aus Tool-Argumenten bauen (purchase-webshop/-supplier,
    movement-Ziel …). Rückgabe: (schema | None, error | None)."""
    from ...schemas.article_process_step import ArticleProcessStepCreate
    st = args.get("step_type")
    kwargs: dict[str, Any] = {"step_type": st}
    if st == "purchase":
        if args.get("webshop_url"):
            kwargs["mode"] = "webshop"
            kwargs["webshop_url"] = str(args["webshop_url"])
        elif args.get("supplier_object_id"):
            u = db.query(UserProfile).filter(
                UserProfile.object_id == int(args["supplier_object_id"]), UserProfile.is_active == True).first()
            if not u:
                return None, {"error": "Lieferant nicht gefunden"}
            kwargs["mode"] = "supplier"
            kwargs["supplier_id"] = u.id
        else:
            return None, {"error": "Beschaffung braucht entweder webshop_url oder supplier_object_id"}
    elif st == "resource":
        kwargs["mode"] = "consume"
    elif st == "movement":
        tt = args.get("target_type")
        if tt:
            kwargs["target_location_type"] = tt
            tid = args.get("target_object_id")
            if tt == "user" and not tid:
                tid = p.effective.object_id      # «zu mir» = der angemeldete Nutzer
            if tid:
                kwargs["target_location_id"] = int(tid)
    try:
        return ArticleProcessStepCreate(**kwargs), None
    except Exception as e:
        return None, {"error": f"Ungültige Schritt-Angaben: {e}"}


def _add_step(db: Session, p: AiPrincipal, owner_kind: str, object_id: int, args: dict) -> Any:
    from ...routers.article_process import _create, _order_owner, _article_owner
    data, err = _build_step_create(db, p, args)
    if err:
        return err
    try:
        owner = _order_owner(db, object_id) if owner_kind == "order" else _article_owner(db, object_id)
        if owner.record.status != "draft":
            return {"error": f"{'Auftrag' if owner_kind == 'order' else 'Artikel'} ist freigegeben – Schritte nur im Entwurf"}
        resp = _create(db, owner, data, p.actor)
    except HTTPException as e:
        return {"error": str(e.detail)}
    emit(db, f"ai.{owner_kind}_step_added", object_type=owner_kind, object_id=object_id,
         payload={"step_type": args.get("step_type"), "on_behalf_of": p.effective.id}, actor_id=p.actor.id)
    db.commit()
    return {"added": True, f"{owner_kind}_object_id": _num(object_id), "step_id": resp.id,
            "step_type": args.get("step_type"), "label": event_types.label(args.get("step_type"))}


def _t_add_article_step(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Einen Prozessschritt an den ARTIKEL-Prozess (Entwurf) hängen – z. B. Beschaffung
    (webshop/Lieferant) oder Bewegung (Lieferziel). So entsteht «wie der Artikel beschafft
    wird». Erlaubt: purchase, resource, inspection, movement, document."""
    st = args.get("step_type")
    if st not in event_types.ARTICLE_STEP_TYPES:
        return {"error": f"Im Artikel-Prozess erlaubt: {', '.join(event_types.ARTICLE_STEP_TYPES)}"}
    return _add_step(db, p, "article", int(args["article_object_id"]), args)


def _t_propose_release_article(db: Session, p: AiPrincipal, args: dict) -> Any:
    """KRITISCH: einen Artikel freigeben (friert Spezifikation + Prozess ein; Voraussetzung
    für Bestellungen). Nur als Vorschlag – menschliche Bestätigung im Chat."""
    from .actions import create_proposal
    a = db.query(Article).filter(Article.object_id == int(args["object_id"]), Article.is_active == True).first()
    if not a:
        return {"error": "Artikel nicht gefunden"}
    if a.status != "draft":
        return {"error": f"Artikel ist '{a.status}' – nur Entwürfe sind freizugeben"}
    from ..processes import article_steps
    if not article_steps(db, a.id):
        return {"error": "Artikel hat noch keinen Prozessschritt – zuerst einen Ablauf hinterlegen"}
    action = create_proposal(
        db, p, "release_article", payload={"object_id": a.object_id},
        summary=f"Artikel {a.object_id} «{a.name}» freigeben (danach bestellbar)",
        target_object_id=a.object_id,
    )
    return {"proposed": True, "action_id": action.id, "summary": action.summary,
            "hint": "Wartet auf Bestätigung. Danach kannst du einen Auftrag darauf anlegen/freigeben."}


def _t_set_order_instances(db: Session, p: AiPrincipal, args: dict) -> Any:
    """Einen Auftrags-Entwurf auf **konkrete, bestehende Instanzen** fixieren (statt FIFO) –
    so wirkt ein Bewegungs-/Prüf-/Verschrottungs-Schritt auf genau diese Instanz(en).
    Voraussetzung: dieselbe Artikelzugehörigkeit wie der Auftrag (mit get_instance prüfen)."""
    from ...routers.orders import _set_chosen_instances
    o = visible_orders(db, p.effective).filter(Order.object_id == int(args["order_object_id"])).first()
    if not o:
        return {"error": "Auftrag nicht gefunden (oder keine Berechtigung)"}
    if o.status != "draft":
        return {"error": f"Auftrag ist '{o.status}' – Instanzen nur im Entwurf fixierbar"}
    ids = [int(x) for x in (args.get("instance_object_ids") or [])]
    try:
        _set_chosen_instances(db, o, ids)
        db.flush()
    except HTTPException as e:
        db.rollback()
        return {"error": str(e.detail)}
    log_audit(db, "orders", "instance_object_ids", ",".join(str(i) for i in ids), p.actor.id,
              object_id=o.object_id)
    emit(db, "ai.order_instances_set", object_type="order", object_id=o.object_id,
         payload={"instances": ids, "on_behalf_of": p.effective.id}, actor_id=p.actor.id)
    db.commit()
    return {"ok": True, "order_object_id": _num(o.object_id), "pinned_instances": [str(i) for i in ids],
            "hint": "Auf Freigabe wirkt der Auftrag genau auf diese Instanz(en)."}


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
        "ERP-Artikel suchen/auflisten (Spezifikation). Nutze dies für Fragen zu Artikeln.",
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
    "resolve_object": _tool(
        "resolve_object",
        "Sagt, WAS eine 9-stellige Objektnummer ist (Artikel/Auftrag/Instanz/Benutzer/Lagerplatz) "
        "und liefert die Kernfakten. Immer zuerst nutzen, wenn die Art einer Nummer unklar ist.",
        {"object_id": {"type": "integer"}},
        ["object_id"],
    ),
    "get_instance": _tool(
        "get_instance",
        "Eine Instanz (konkretes Stück/Charge) lesen – inkl. zugehörigem ARTIKEL, Qualität, "
        "Disposition, Standort. So findest du selbst heraus, zu welchem Artikel eine Instanz gehört.",
        {"object_id": {"type": "integer"}},
        ["object_id"],
    ),
    "list_instances": _tool(
        "list_instances",
        "Instanzen auflisten/zählen. Optional nach Artikel oder Disposition "
        "(in_process/in_stock/consumed/sold/scrapped).",
        {"article_object_id": {"type": "integer"},
         "disposition": {"type": "string",
                         "enum": ["in_process", "in_stock", "consumed", "sold", "scrapped"]}},
    ),
    "list_users": _tool(
        "list_users",
        "Benutzerkonten auflisten/zählen (Personal). Beantwortet «wie viele User/Kunden/Lieferanten». "
        "Optional nach Rolle (admin/employee/supplier/customer/ai) oder Suchbegriff.",
        {"role": {"type": "string", "enum": ["admin", "employee", "supplier", "customer", "ai"]},
         "query": {"type": "string"}},
    ),
    "get_user": _tool(
        "get_user",
        "Ein Benutzerkonto im Detail lesen (Personal) – per Objektnummer oder E-Mail.",
        {"object_id": {"type": "integer"}, "email": {"type": "string"}},
    ),
    "company_info": _tool(
        "company_info",
        "Firmen-/Systemkonfiguration lesen (Firmenname, Adresse, MWST, Zahlungsziel, Artikelnamen-Katalog).",
        {},
    ),
    "audit_log": _tool(
        "audit_log",
        "Audit-Log lesen (nur Admin): wer hat wann was geändert. Optional nach Objekt/Tabelle.",
        {"object_id": {"type": "integer"}, "table_name": {"type": "string"}, "limit": {"type": "integer"}},
    ),
    "fetch_web_page": _tool(
        "fetch_web_page",
        "Eine öffentliche Webseite/Produktseite (z. B. Amazon-Link) abrufen und Kerninfos "
        "extrahieren (Titel, Beschreibung, Bild, Preis/Marke/Material). Nutze dies, um aus "
        "einem Produktlink einen Artikel zu befüllen.",
        {"url": {"type": "string"}},
        ["url"],
    ),
    "shop_products": _tool(
        "shop_products",
        "Shop-Sortiment für Kaufberatung (publizierte Produkte mit Preisen, CHF).",
        {"query": {"type": "string", "description": "Titelsuche (Teilstring)"}},
    ),
    "open_page": _tool(
        "open_page",
        "Den Nutzer an die passende Stelle in der App FÜHREN (Navigation, rendert einen Knopf). "
        "Nutze dies, um «soll ich es dir zeigen?» umzusetzen – z. B. bei Kaufinteresse zum "
        "Shop-Produkt (kind=shop_product + object_id), zum Warenkorb (cart), zu «Meine "
        "Bestellungen» (my_orders) oder zu einem ERP-Datensatz (erp_record + object_id, nur Personal).",
        {"kind": {"type": "string", "enum": ["shop", "shop_product", "cart", "my_orders", "erp_record"]},
         "object_id": {"type": "integer", "description": "Objektnummer (bei shop_product/erp_record)"}},
        ["kind"],
    ),
    "my_orders": _tool(
        "my_orders",
        "Die eigenen Shop-Bestellungen der angemeldeten Person (Status, Betrag).",
        {},
    ),
    "article_name_suggestions": _tool(
        "article_name_suggestions",
        "Bereits verwendete/ähnliche Artikelnamen zu einer Bezeichnung finden (Dubletten "
        "vermeiden). IMMER vor create_article_draft aufrufen: passt ein vorhandener Name gut, "
        "diesen wiederverwenden; sonst einen neuen kurzen Namen wählen.",
        {"query": {"type": "string", "description": "Kernbezeichnung, z. B. «Schraubendreher»"},
         "limit": {"type": "integer"}},
        ["query"],
    ),
    "create_article_draft": _tool(
        "create_article_draft",
        "Einen neuen Artikel als ENTWURF anlegen (reversibel). Nur wenn die Person das "
        "ausdrücklich möchte. Fülle ALLE ableitbaren Felder – die Formate werden serverseitig "
        "geprüft; ein Fehler kommt als Meldung zurück, die du korrigieren kannst.",
        {"name": {"type": "string", "description": "Kurz & prägnant, max. 32 Zeichen (nicht der lange Shop-Titel)"},
         "unit": {"type": "string", "enum": ["Stk", "mm", "m2", "m3", "kg", "l"],
                  "description": "Mengeneinheit: Stk (Stück), mm, m2 (m²), m3 (m³), kg, l"},
         "serialization": {"type": "string", "enum": ["unit", "batch"],
                           "description": "unit = Einzelteil (ganze Stück), batch = Charge (auch Bruchmengen)"},
         "size": {"type": "string", "description": "Abmessungen in MILLIMETER, aufsteigend, mit 'x' getrennt – z. B. «3x40x600». KEINE Einheit im Wert (nicht «15cm»); cm/inch vorher in mm umrechnen."},
         "weight_kg": {"type": "string", "description": "Gewicht in KG als Dezimalzahl (> 0, max. 3 Nachkommastellen), z. B. «2.5». Nur die Zahl, ohne «kg»."},
         "material": {"type": "string"}, "surface": {"type": "string"}, "cad_url": {"type": "string"},
         "supplier_article_number": {"type": "string", "description": "z. B. Hersteller-/Shop-Artikelnummer, ASIN"},
         "min_order_qty": {"type": "string"}, "safety_stock": {"type": "string"}},
        ["name"],
    ),
    "update_article": _tool(
        "update_article",
        "Felder eines Artikel-ENTWURFS ändern (Name, Einheit, Material, Gewicht, Oberfläche, "
        "Lieferanten-Artikelnummer …). Nur im Entwurf. Formate wie bei create_article_draft.",
        {"object_id": {"type": "integer"}, "name": {"type": "string"},
         "unit": {"type": "string", "enum": ["Stk", "mm", "m2", "m3", "kg", "l"]},
         "serialization": {"type": "string", "enum": ["unit", "batch"]},
         "size": {"type": "string", "description": "Abmessungen in mm, aufsteigend, 'x'-getrennt (z. B. 3x40x600) – keine Einheit im Wert"},
         "weight_kg": {"type": "string", "description": "Gewicht in kg (> 0, max. 3 Nachkommastellen), nur die Zahl"},
         "material": {"type": "string"},
         "cad_url": {"type": "string"}, "surface": {"type": "string"},
         "supplier_article_number": {"type": "string"},
         "min_order_qty": {"type": "string"}, "safety_stock": {"type": "string"}},
        ["object_id"],
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
    "set_order_instances": _tool(
        "set_order_instances",
        "Einen Auftrags-Entwurf auf KONKRETE bestehende Instanzen fixieren (statt FIFO). "
        "So bearbeitet ein Auftrag genau diese Instanz(en) – z. B. eine bestimmte Instanz bewegen. "
        "Die Instanzen müssen zum Artikel des Auftrags gehören (mit get_instance auflösen).",
        {"order_object_id": {"type": "integer"},
         "instance_object_ids": {"type": "array", "items": {"type": "integer"}}},
        ["order_object_id", "instance_object_ids"],
    ),
    "add_order_step": _tool(
        "add_order_step",
        "Einen Prozessschritt an einen Auftrags-Entwurf anhängen. Typen: purchase (Beschaffung), "
        "resource, inspection (Datenerfassung), movement (Bewegung), scrap, sale (Verkauf), document. "
        "Für purchase optional webshop_url ODER supplier_object_id; für movement optional Ziel.",
        {"order_object_id": {"type": "integer"},
         "step_type": {"type": "string",
                       "enum": ["purchase", "resource", "inspection", "movement", "scrap", "sale", "document"]},
         "webshop_url": {"type": "string", "description": "Beschaffung per Online-Shop-Link"},
         "supplier_object_id": {"type": "integer", "description": "Beschaffung bei diesem Lieferanten"},
         "target_type": {"type": "string", "enum": ["place", "user", "instance", "company"],
                         "description": "Bewegungs-Ziel (user = zum angemeldeten Nutzer «zu mir»)"},
         "target_object_id": {"type": "integer"}},
        ["order_object_id", "step_type"],
    ),
    "add_article_step": _tool(
        "add_article_step",
        "Einen Prozessschritt an den ARTIKEL-Prozess (Entwurf) anhängen – definiert, WIE der "
        "Artikel beschafft/verarbeitet wird. Typen: purchase, resource, inspection, movement, document. "
        "Für Beschaffung per Link: step_type=purchase + webshop_url. Für Lieferung an den Nutzer: "
        "step_type=movement + target_type=user.",
        {"article_object_id": {"type": "integer"},
         "step_type": {"type": "string", "enum": ["purchase", "resource", "inspection", "movement", "document"]},
         "webshop_url": {"type": "string"}, "supplier_object_id": {"type": "integer"},
         "target_type": {"type": "string", "enum": ["place", "user", "instance", "company"]},
         "target_object_id": {"type": "integer"}},
        ["article_object_id", "step_type"],
    ),
    "propose_release_article": _tool(
        "propose_release_article",
        "KRITISCH: einen Artikel FREIGEBEN (Voraussetzung, um ihn zu bestellen). Nur als Vorschlag – "
        "die Person bestätigt im Chat.",
        {"object_id": {"type": "integer"}},
        ["object_id"],
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
    "resolve_object": _t_resolve_object,
    "open_page": _t_open_page,
    "get_instance": _t_get_instance,
    "list_instances": _t_list_instances,
    "list_users": _t_list_users,
    "get_user": _t_get_user,
    "company_info": _t_company_info,
    "audit_log": _t_audit_log,
    "fetch_web_page": _t_fetch_web_page,
    "article_name_suggestions": _t_article_name_suggestions,
    "create_article_draft": _t_create_article_draft,
    "update_article": _t_update_article,
    "add_article_step": _t_add_article_step,
    "propose_release_article": _t_propose_release_article,
    "create_order_draft": _t_create_order_draft,
    "get_order_steps": _t_get_order_steps,
    "add_order_step": _t_add_order_step,
    "set_order_instances": _t_set_order_instances,
    "propose_release_order": _t_propose_release_order,
}

# Rollen-Whitelist: die Rolle begrenzt die Tool-Menge (und damit die Angriffsfläche).
_BY_ROLE: dict[str, tuple[str, ...]] = {
    "admin": ("list_articles", "get_article", "list_orders", "get_order", "inventory_summary",
              "recent_events", "shop_products", "resolve_object", "open_page", "get_instance", "list_instances",
              "list_users", "get_user", "company_info", "audit_log", "fetch_web_page",
              "article_name_suggestions", "create_article_draft", "update_article", "add_article_step",
              "propose_release_article", "create_order_draft", "get_order_steps", "add_order_step",
              "set_order_instances", "propose_release_order"),
    "employee": ("list_articles", "get_article", "list_orders", "get_order", "inventory_summary",
                 "recent_events", "shop_products", "resolve_object", "open_page", "get_instance", "list_instances",
                 "list_users", "get_user", "company_info", "fetch_web_page",
                 "article_name_suggestions", "create_article_draft", "update_article", "add_article_step",
                 "propose_release_article", "create_order_draft", "get_order_steps", "add_order_step",
                 "set_order_instances", "propose_release_order"),
    "supplier": ("list_orders", "get_order", "open_page"),
    "customer": ("shop_products", "my_orders", "open_page"),
    # Autonome KI-Läufe (ohne Delegation): nur lesen – bewusst eng.
    "ai": ("list_articles", "get_article", "inventory_summary", "recent_events"),
}


# Tools, die den ERP-Datenbestand verändern (Feed-relevant) → das Frontend soll nach
# einem solchen KI-Lauf live neu laden. Vorschläge (propose_*) zählen NICHT: sie ändern
# nichts, bis der Mensch sie bestätigt (das läuft über den Aktions-Confirm-Pfad).
_WRITE_TOOLS: frozenset[str] = frozenset({
    "create_article_draft", "update_article", "create_order_draft",
    "add_article_step", "add_order_step", "set_order_instances",
})


def is_write_tool(name: str) -> bool:
    return name in _WRITE_TOOLS


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
