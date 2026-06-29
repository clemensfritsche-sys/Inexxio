"""Geschäftslogik der **Verkaufs-Ebene am Artikel** + öffentlicher Shop.

Kernidee (wie überall: Definition am Artikel, Ausführung im Auftrag): der Verkauf ist
KEIN eigenes Objekt, sondern eine dritte, **lebende** Ebene am Artikel (Profil + Preise
+ Zielgruppe). Ein Kauf erzeugt einen **ganz normalen Auftrag** mit einem ``sale``- und
einem ``movement``-Schritt (Bestands-Operation, FIFO ab Lager); Preis/Währung/FX/Steuer
werden auf den ``sale``-Beleg **eingefroren** (Snapshot).
"""

from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (
    Article, ArticlePrice, ArticleProcessStep, ArticleSalesAudience,
    CompanySettings, Order, Sale, UserProfile,
)
from ..models.base import utcnow
from . import pricing
from .admin import log_audit

DEFAULT_SHOP_CURRENCIES = ["CHF", "EUR", "USD"]


# ─── Shop-Währungen / Konfiguration ──────────────────────────────────────────────

def _settings(db: Session) -> CompanySettings | None:
    return db.query(CompanySettings).filter(CompanySettings.id == 1).first()


def shop_currencies(db: Session) -> list[str]:
    s = _settings(db)
    if s and s.shop_currencies:
        return [c.upper() for c in s.shop_currencies if c]
    return list(DEFAULT_SHOP_CURRENCIES)


def resolve_currency(db: Session, requested: str | None, country: str | None) -> str:
    """Anzeige-Währung bestimmen: ausdrücklicher Wunsch → Land-Zuordnung → Default."""
    currencies = shop_currencies(db)
    if requested and requested.upper() in currencies:
        return requested.upper()
    s = _settings(db)
    if country and s and s.shop_country_currency:
        mapped = (s.shop_country_currency or {}).get(country)
        if mapped and mapped.upper() in currencies:
            return mapped.upper()
    default = (s.shop_default_currency if s else None) or "CHF"
    return default.upper() if default.upper() in currencies else currencies[0]


# ─── Profil / Preise / Zielgruppe (ERP) ──────────────────────────────────────────

def _user_name(u: UserProfile | None) -> str | None:
    if not u:
        return None
    name = " ".join(p for p in [u.first_name, u.last_name] if p).strip()
    return u.company_name or name or u.email


def prices_for(db: Session, article_id: int) -> list[ArticlePrice]:
    return (
        db.query(ArticlePrice)
        .filter(ArticlePrice.article_id == article_id, ArticlePrice.is_active == True)
        .order_by(ArticlePrice.is_primary.desc(), ArticlePrice.id)
        .all()
    )


def audience_for(db: Session, article_id: int) -> list[dict]:
    rows = (
        db.query(ArticleSalesAudience)
        .filter(ArticleSalesAudience.article_id == article_id,
                ArticleSalesAudience.is_active == True)
        .order_by(ArticleSalesAudience.id)
        .all()
    )
    out: list[dict] = []
    for r in rows:
        u = db.query(UserProfile).filter(UserProfile.id == r.user_id).first()
        out.append({"id": r.id, "user_id": r.user_id, "name": _user_name(u),
                    "email": u.email if u else None, "object_id": u.object_id if u else None})
    return out


def previews(db: Session, article: Article) -> list[dict]:
    """Live-Vorschau des berechneten Preises je Shop-Währung (Inland-Steuer CH)."""
    out: list[dict] = []
    for cur in shop_currencies(db):
        view = pricing.price_view(db, article, cur, country=None, customer=None)
        if view:
            out.append(view)
    return out


def update_profile(db: Session, article: Article, data, actor_id: int) -> Article:
    """Verkaufs-Profil setzen (published/visibility/content) – IMMER editierbar,
    auch bei status='released' (die Freigabe friert nur Spezifikation + Prozess)."""
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        old = getattr(article, key, None)
        if str(old) != str(value):
            log_audit(db, "articles", key, str(value), actor_id,
                      object_id=article.object_id, old_value=str(old) if old is not None else None)
        setattr(article, key, value)
    db.commit()
    db.refresh(article)
    return article


def _clear_primary(db: Session, article_id: int, keep_id: int | None) -> None:
    for p in db.query(ArticlePrice).filter(
        ArticlePrice.article_id == article_id, ArticlePrice.is_active == True,
        ArticlePrice.is_primary == True,
    ).all():
        if p.id != keep_id:
            p.is_primary = False


def create_price(db: Session, article: Article, data, actor_id: int) -> ArticlePrice:
    price = ArticlePrice(
        article_id=article.id, kind=data.kind,
        interval=data.interval if data.kind == "subscription" else None,
        amount_chf=data.amount_chf, compare_at_chf=data.compare_at_chf,
        tax_class=data.tax_class, is_primary=bool(data.is_primary),
    )
    db.add(price)
    db.flush()
    # Erster Preis ist automatisch der Hauptpreis; ein neuer Hauptpreis verdrängt den alten.
    if price.is_primary or not _other_primary_exists(db, article.id, price.id):
        price.is_primary = True
        _clear_primary(db, article.id, price.id)
    log_audit(db, "article_prices", None, f"Preis {price.amount_chf} CHF angelegt",
              actor_id, object_id=article.object_id)
    db.commit()
    db.refresh(price)
    return price


def _other_primary_exists(db: Session, article_id: int, exclude_id: int) -> bool:
    return db.query(ArticlePrice.id).filter(
        ArticlePrice.article_id == article_id, ArticlePrice.is_active == True,
        ArticlePrice.is_primary == True, ArticlePrice.id != exclude_id,
    ).first() is not None


def _get_price(db: Session, article: Article, price_id: int) -> ArticlePrice:
    price = db.query(ArticlePrice).filter(
        ArticlePrice.id == price_id, ArticlePrice.article_id == article.id,
        ArticlePrice.is_active == True,
    ).first()
    if not price:
        raise HTTPException(404, detail="Preis nicht gefunden")
    return price


def update_price(db: Session, article: Article, price_id: int, data, actor_id: int) -> ArticlePrice:
    price = _get_price(db, article, price_id)
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(price, key, value)
    if price.kind != "subscription":
        price.interval = None
    if payload.get("is_primary"):
        _clear_primary(db, article.id, price.id)
    log_audit(db, "article_prices", "update", str(payload), actor_id, object_id=article.object_id)
    db.commit()
    db.refresh(price)
    return price


def delete_price(db: Session, article: Article, price_id: int, actor_id: int) -> None:
    price = _get_price(db, article, price_id)
    price.is_active = False
    log_audit(db, "article_prices", "is_active", "false", actor_id,
              object_id=article.object_id, old_value="true")
    # Wird der Hauptpreis entfernt, den nächsten verbliebenen zum Hauptpreis machen.
    if price.is_primary:
        price.is_primary = False
        nxt = db.query(ArticlePrice).filter(
            ArticlePrice.article_id == article.id, ArticlePrice.is_active == True,
        ).order_by(ArticlePrice.id).first()
        if nxt:
            nxt.is_primary = True
    db.commit()


def add_audience(db: Session, article: Article, user_id: int, actor_id: int) -> ArticleSalesAudience:
    user = db.query(UserProfile).filter(UserProfile.id == user_id, UserProfile.is_active == True).first()
    if not user:
        raise HTTPException(400, detail="Benutzer nicht gefunden")
    existing = db.query(ArticleSalesAudience).filter(
        ArticleSalesAudience.article_id == article.id,
        ArticleSalesAudience.user_id == user_id,
    ).first()
    if existing:
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing
    row = ArticleSalesAudience(article_id=article.id, user_id=user_id)
    db.add(row)
    log_audit(db, "article_sales_audience", None, f"Kunde {user_id} zugewiesen",
              actor_id, object_id=article.object_id)
    db.commit()
    db.refresh(row)
    return row


def remove_audience(db: Session, article: Article, row_id: int, actor_id: int) -> None:
    row = db.query(ArticleSalesAudience).filter(
        ArticleSalesAudience.id == row_id, ArticleSalesAudience.article_id == article.id,
    ).first()
    if not row:
        raise HTTPException(404, detail="Zuweisung nicht gefunden")
    row.is_active = False
    log_audit(db, "article_sales_audience", "is_active", "false", actor_id,
              object_id=article.object_id, old_value="true")
    db.commit()


def copy_sales_profile(db: Session, src: Article, dst: Article) -> None:
    """Verkaufs-Profil + Preise + Zielgruppe auf den Nachfolge-Artikel mitkopieren
    (beim Ersetzen). So überlebt das Shop-Listing den Versionswechsel kanonisch."""
    dst.sales_published = src.sales_published
    dst.sales_visibility = src.sales_visibility
    dst.sales_content = src.sales_content
    for p in prices_for(db, src.id):
        db.add(ArticlePrice(
            article_id=dst.id, kind=p.kind, interval=p.interval, amount_chf=p.amount_chf,
            compare_at_chf=p.compare_at_chf, tax_class=p.tax_class, is_primary=p.is_primary,
        ))
    for r in db.query(ArticleSalesAudience).filter(
        ArticleSalesAudience.article_id == src.id, ArticleSalesAudience.is_active == True,
    ).all():
        db.add(ArticleSalesAudience(article_id=dst.id, user_id=r.user_id))
    db.flush()


# ─── Shop: Sichtbarkeit / Kanonisierung ──────────────────────────────────────────

def canonical(db: Session, article: Article) -> Article:
    """Dem ``replaced_by_id``-Pfad folgen → der aktuellste, nicht ersetzte Artikel."""
    seen = set()
    cur = article
    while cur.replaced_by_id and cur.replaced_by_id not in seen:
        seen.add(cur.replaced_by_id)
        nxt = db.query(Article).filter(Article.object_id == cur.replaced_by_id).first()
        if not nxt:
            break
        cur = nxt
    return cur


def _is_assigned(db: Session, article_id: int, user: UserProfile | None) -> bool:
    if not user:
        return False
    return db.query(ArticleSalesAudience.id).filter(
        ArticleSalesAudience.article_id == article_id,
        ArticleSalesAudience.user_id == user.id,
        ArticleSalesAudience.is_active == True,
    ).first() is not None


def can_view(db: Session, article: Article, user: UserProfile | None) -> bool:
    """Darf dieser (ggf. anonyme) Nutzer das Produkt im Detail sehen/kaufen?

    public/unlisted → ja (unlisted nur per direktem Link). private → nur zugewiesene
    Kunden (oder Personal). Voraussetzung: publiziert, aktiv, nicht inaktiv."""
    if not article.sales_published or not article.is_active or article.status == "inactive":
        return False
    if article.sales_visibility == "public" or article.sales_visibility == "unlisted":
        return True
    if user and user.role in ("admin", "employee"):
        return True
    return _is_assigned(db, article.id, user)


def _content(article: Article, lang: str) -> dict:
    data = article.sales_content or {}
    block = data.get(lang) or data.get("de") or data.get("en") or {}
    return block if isinstance(block, dict) else {}


def to_product(db: Session, article: Article, currency: str, country: str | None,
               user: UserProfile | None, lang: str) -> dict:
    c = _content(article, lang)
    images = c.get("images") or []
    return {
        "object_id": article.object_id,
        "title": c.get("title") or article.name,
        "subtitle": c.get("subtitle"),
        "description": c.get("description"),
        "images": [i for i in images if i],
        "visibility": article.sales_visibility,
        "unit": article.unit,
        "price": pricing.price_view(db, article, currency, country, user),
    }


def list_products(db: Session, user: UserProfile | None, currency: str,
                  country: str | None, lang: str) -> list[dict]:
    """Im Shop gelistete Produkte: publizierte **public** (für alle) + publizierte
    **private** des eingeloggten Kunden. **unlisted** wird nie gelistet (nur Direktlink).
    Kanonisiert über ``replaced_by_id`` (nur der aktuelle, nicht ersetzte Artikel)."""
    rows = (
        db.query(Article)
        .filter(Article.is_active == True, Article.status != "inactive",
                Article.sales_published == True, Article.replaced_by_id.is_(None))
        .order_by(Article.object_id.desc())
        .all()
    )
    out: list[dict] = []
    for a in rows:
        if a.sales_visibility == "public":
            pass
        elif a.sales_visibility == "private":
            if not (_is_assigned(db, a.id, user) or (user and user.role in ("admin", "employee"))):
                continue
        else:   # unlisted → nicht listen
            continue
        # Nur Produkte mit gepflegtem Preis listen.
        if not pricing.resolve_primary_price(db, a):
            continue
        out.append(to_product(db, a, currency, country, user, lang))
    return out


# ─── Shop: Checkout ──────────────────────────────────────────────────────────────

def _interval_days(interval: str | None) -> int:
    return 365 if interval == "year" else 30


def checkout(db: Session, article: Article, quantity: int, currency: str,
             customer: UserProfile) -> tuple[Order, Sale, str, str]:
    """Kauf abwickeln: Auftrag (Bestands-Operation, FIFO) mit ``sale``- und
    ``movement``-Schritt anlegen, freigeben, Preis-Snapshot auf den Verkauf einfrieren
    und die Zahl-URL des Providers zurückgeben. Liefert (Auftrag, Verkauf, URL, Provider)."""
    # Spät importiert (Vermeidung von Import-Zyklen über die Prozess-/Auftrags-Services).
    from . import process, sale as sale_svc, subject
    from .events import emit
    from .objects import next_object_id
    from .payments import get_provider

    article = canonical(db, article)
    if not can_view(db, article, customer):
        raise HTTPException(403, detail="Dieses Produkt ist nicht verfügbar")
    price = pricing.resolve_primary_price(db, article)
    if not price:
        raise HTTPException(400, detail="Für dieses Produkt ist kein Preis hinterlegt")

    from . import fx
    country = getattr(customer, "ship_country", None) or getattr(customer, "country", None)
    view = pricing.price_view(db, article, currency, country, customer)
    fx_rate = fx.get_rate(db, currency)
    today = utcnow().date()

    order = Order(
        object_id=next_object_id(db, "order"), status="draft",
        article_id=article.id, quantity=quantity,
        title=f"Shop-Kauf: {article.name}",
    )
    # TODO(Erweiterung – NICHT gebaut): Coupon-/Rabatt-Engine (über `compare_at` hinaus)
    #   und Bundles (mehrere Artikel je Kauf) wären hier die nächsten Stufen.
    if price.kind == "subscription":
        # Abo nutzt die vorhandenen recurrence_*-Felder (Kette beim Abschluss).
        # TODO(Erweiterung – NICHT gebaut): metered/limited-term Abos (verbrauchsbasiert).
        order.recurrence_active = True
        order.recurrence_interval_days = _interval_days(price.interval)
        order.recurrence_anchor = today + timedelta(days=order.recurrence_interval_days)
    db.add(order)
    db.flush()

    # Bestands-Operation: eigene Schritte ⇒ subject_kind = stock (FIFO ab Lager).
    # Reihenfolge: kaufmännischer Verkauf (Zahlung) → Bewegung (Versand zum Kunden).
    db.add(ArticleProcessStep(order_id=order.id, position=0, step_type="sale"))
    db.add(ArticleProcessStep(order_id=order.id, position=2, step_type="movement",
                              target_location_type="user" if customer.object_id else None,
                              target_location_id=customer.object_id))
    db.flush()

    # Freigabe (wie routers/orders.py): Subjekt herstellen (FIFO reservieren) + Verkauf anlegen.
    order.status = "released"
    order.released_at = utcnow()
    subject.materialize_subject(db, order, customer.id)
    sale_svc.instantiate_for_order(db, order, customer.id)
    emit(db, "order.released", object_type="order", object_id=order.object_id,
         payload={"article_id": order.article_id, "quantity": order.quantity, "via": "shop"},
         actor_id=customer.id)

    sale = db.query(Sale).filter(Sale.order_id == order.id, Sale.is_active == True).first()
    if not sale:
        raise HTTPException(500, detail="Verkauf konnte nicht angelegt werden")

    # ── Snapshot: Preis/Währung/FX/Steuer einfrieren (Katalog mutabel, Beleg fix) ──
    net_total = (view["net"] * quantity).quantize(Decimal("0.01"))
    sale.customer_id = customer.id
    sale.currency = currency
    sale.order_total = net_total
    sale.vat_rate = view["tax_rate"]
    sale.tax_class = price.tax_class
    sale.base_amount_chf = (Decimal(price.amount_chf) * quantity).quantize(Decimal("0.01"))
    sale.fx_rate = fx_rate
    sale.fx_date = today
    log_audit(db, "sales", None, f"Shop-Verkauf {net_total} {currency} (Snapshot)",
              customer.id, object_id=order.object_id)
    db.commit()
    db.refresh(order)
    db.refresh(sale)

    provider = get_provider(db)
    url = provider.create_checkout(db, order, sale)
    return order, sale, url, provider.name
