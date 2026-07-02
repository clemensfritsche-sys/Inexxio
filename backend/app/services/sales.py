"""Geschäftslogik der **Verkaufs-Ebene am Artikel** + öffentlicher Shop.

Kernidee (wie überall: Definition am Artikel, Ausführung im Auftrag): der Verkauf ist
KEIN eigenes Objekt, sondern eine dritte, **lebende** Ebene am Artikel (Profil + Preise
+ Zielgruppe). Ein Kauf erzeugt einen **ganz normalen Auftrag** mit einem ``sale``- und
einem ``movement``-Schritt (Bestands-Operation, FIFO ab Lager); Preis/Währung/FX/Steuer
werden auf den ``sale``-Beleg **eingefroren** (Snapshot).
"""

from datetime import date, timedelta
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


def _price_rank(p: ArticlePrice) -> int:
    """Sortier-Rang: Abos zuerst (Produktabo, dann Nutzungsabo), zuletzt Einmalkauf."""
    if p.kind == "subscription":
        return 0 if p.sub_type == "product" else 1
    return 2


def prices_for(db: Session, article_id: int) -> list[ArticlePrice]:
    prices = (
        db.query(ArticlePrice)
        .filter(ArticlePrice.article_id == article_id, ArticlePrice.is_active == True)
        .all()
    )
    # Reihenfolge: Produktabo → Nutzungsabo → Einmalkauf (dann Hauptpreis, dann id).
    prices.sort(key=lambda p: (_price_rank(p), 0 if p.is_primary else 1, p.id))
    return prices


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
    """Live-Vorschau des Preises in CHF (Basis, inkl. Schweizer MWST). Fremdwährungen +
    finale länderabhängige Steuer übernimmt Stripe (Adaptive Pricing + Stripe Tax) an der
    Kasse – daher zeigt die ERP-Vorschau bewusst nur den CHF-Endpreis."""
    view = pricing.price_view(db, article, "CHF", country=None, customer=None)
    return [view] if view else []


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
    is_sub = data.kind == "subscription"
    price = ArticlePrice(
        article_id=article.id, kind=data.kind,
        interval=data.interval if is_sub else None,
        sub_type=(data.sub_type or "usage") if is_sub else None,
        amount_chf=data.amount_chf, compare_at_chf=data.compare_at_chf,
        is_primary=bool(data.is_primary),
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
        price.sub_type = None
    elif not price.sub_type:
        price.sub_type = "usage"
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
            article_id=dst.id, kind=p.kind, interval=p.interval, sub_type=p.sub_type,
            amount_chf=p.amount_chf, compare_at_chf=p.compare_at_chf, is_primary=p.is_primary,
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

    public → ja. private → nur zugewiesene Kunden (oder Personal).
    Voraussetzung: publiziert, aktiv, nicht inaktiv."""
    if not article.sales_published or not article.is_active or article.status == "inactive":
        return False
    if article.sales_visibility == "public":
        return True
    if user and user.role in ("admin", "employee"):
        return True
    return _is_assigned(db, article.id, user)


def _content(article: Article, lang: str) -> dict:
    data = article.sales_content or {}
    block = data.get(lang) or data.get("de") or data.get("en") or {}
    return block if isinstance(block, dict) else {}


def price_options(db: Session, article: Article, currency: str, country: str | None,
                  user: UserProfile | None) -> list[dict]:
    """Alle wählbaren Preis-Optionen eines Artikels (Einmalkauf/Nutzungsabo/Produktabo …),
    Hauptpreis zuerst – jede mit berechneter Preis-Sicht in ``currency``."""
    out: list[dict] = []
    for p in prices_for(db, article.id):
        out.append({
            "price_id": p.id, "kind": p.kind, "interval": p.interval,
            "sub_type": p.sub_type, "is_primary": p.is_primary,
            "view": pricing.price_view_for(db, p, currency, country, user),
        })
    return out


def to_product(db: Session, article: Article, currency: str, country: str | None,
               user: UserProfile | None, lang: str) -> dict:
    c = _content(article, lang)
    images = c.get("images") or []
    options = price_options(db, article, currency, country, user)
    return {
        "object_id": article.object_id,
        "title": c.get("title") or article.name,
        "subtitle": c.get("subtitle"),
        "description": c.get("description"),
        "images": [i for i in images if i],
        "visibility": article.sales_visibility,
        "fulfillment": article.sales_fulfillment or "make",
        "unit": article.unit,
        "price": (options[0]["view"] if options else None),
        "prices": options,
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


# ─── Shop: Warenkorb-Checkout (Defer-Modell, mehrere Positionen) ─────────────────

CENT = Decimal("0.01")


def _interval_days(interval: str | None) -> int:
    return 365 if interval == "year" else 30


# Mindestbindung eines PRODUKTABOS (wiederkehrende physische Lieferung) – state of the
# art: eine sofortige Kündigung direkt nach dem Abschluss (vor der ersten Lieferung)
# würde dem Geschäft die Gelegenheit nehmen, überhaupt zu erfüllen. Ein NUTZUNGSABO
# (``sub_type='usage'``, z. B. Software-/Geräte-Zugang) hat dagegen KEINE Mindestbindung –
# dort schadet eine sofortige Kündigung niemandem, der Zugang endet einfach zum
# Periodenende (Stripe ``cancel_at_period_end`` wäre der nächste Ausbauschritt).
PRODUCT_MINIMUM_TERM_CYCLES = 1


def earliest_cancellation_date(order: "Order") -> date | None:
    """Frühester Kündigungstermin eines Produktabos – ``None`` = sofort kündbar (kein
    aktives Produktabo, oder die Mindestlaufzeit (``PRODUCT_MINIMUM_TERM_CYCLES`` ×
    Periodenlänge ab Freigabe/erster Abrechnung) ist bereits erreicht)."""
    if (order.recurrence_kind != "product" or not order.recurrence_active
            or not order.released_at or not order.recurrence_interval_days):
        return None
    total_days = order.recurrence_interval_days * PRODUCT_MINIMUM_TERM_CYCLES
    earliest = (order.released_at + timedelta(days=total_days)).date()
    return earliest if earliest > date.today() else None


def _resolve_line(db: Session, item, customer: UserProfile) -> dict:
    """Eine Warenkorb-Position validieren und zu einer aufgelösten ``line`` verdichten
    (Artikel kanonisch, sichtbar, freigegeben; Preis-Option gehört zum Artikel)."""
    article = db.query(Article).filter(
        Article.object_id == item.article_object_id, Article.is_active == True).first()
    if not article:
        raise HTTPException(404, detail="Produkt nicht gefunden")
    article = canonical(db, article)
    if not can_view(db, article, customer):
        raise HTTPException(403, detail="Dieses Produkt ist nicht verfügbar")
    if article.status != "released":
        raise HTTPException(400, detail="Dieses Produkt ist noch nicht zum Kauf freigegeben")
    if item.price_id:
        price = db.query(ArticlePrice).filter(
            ArticlePrice.id == item.price_id, ArticlePrice.article_id == article.id,
            ArticlePrice.is_active == True).first()
        if not price:
            raise HTTPException(400, detail="Gewählte Preis-Option ist nicht verfügbar")
    else:
        price = pricing.resolve_primary_price(db, article)
    if not price:
        raise HTTPException(400, detail="Für dieses Produkt ist kein Preis hinterlegt")

    view = pricing.price_view_for(db, price, "CHF", country=None, customer=customer)
    qty = item.quantity
    return {
        "article_id": article.id, "article_object_id": article.object_id,
        "article_name": article.name, "price_id": price.id,
        "quantity": qty, "fulfillment": article.sales_fulfillment or "make",
        "kind": price.kind, "interval": price.interval, "sub_type": price.sub_type,
        "base_amount_chf": str((Decimal(price.amount_chf) * qty).quantize(CENT)),
        "net_chf": str((view["net"] * qty).quantize(CENT)) if view else None,
        "vat_rate": str(view["tax_rate"]) if view else None,
        "order_id": None,
    }


def checkout(db: Session, items: list, customer: UserProfile) -> tuple["object", dict]:
    """Warenkorb-Checkout (**Defer-Modell: erst zahlen, dann erfüllen**). Mehrere Positionen
    ⇒ EIN ``CheckoutIntent`` ⇒ EINE Zahlungs-Session. Der Auftrag je Position wird **erst
    bei bestätigter Zahlung** erzeugt (Made-to-Order). Ausnahme **stock** (limitierte
    Auflage): der Auftrag wird schon hier angelegt + reserviert (kein Überverkauf).

    Liefert (Intent, Provider-Ergebnis) – das Ergebnis trägt ``client_secret``/``session_id``
    (Stripe, eingebettete Kasse) bzw. ``payment_url`` (manueller Fallback)."""
    from .payments import get_provider
    from ..models import CheckoutIntent

    lines = [_resolve_line(db, it, customer) for it in items]
    # Abos werden separat abgeschlossen (Stripe: ein Subscription-Checkout je Vertrag).
    if any(l["kind"] == "subscription" for l in lines) and len(lines) > 1:
        raise HTTPException(
            400, detail="Ein Abo muss separat gekauft werden – bitte einzeln zur Kasse gehen.")

    total = sum((Decimal(l["base_amount_chf"]) for l in lines), Decimal("0"))
    intent = CheckoutIntent(customer_id=customer.id, status="pending",
                            lines=lines, amount_chf=total.quantize(CENT))
    db.add(intent)
    db.flush()

    # stock-Positionen: EIN gemeinsamer Verkaufsauftrag (mehrere Positionen = ein Auftrag,
    # ein Versand) – schon jetzt reserviert (Überverkauf vermeiden). make-Positionen bleiben
    # aufgeschoben (eigene Produktion + Verkauf erst bei Zahlung).
    stock_lines = [l for l in lines if l["fulfillment"] == "stock"]
    if stock_lines:
        order = _create_multiline_sale_order(db, stock_lines, customer, allow_backorder=False)
        for l in stock_lines:
            l["order_id"] = order.object_id
    _store_lines(intent, lines)
    db.commit()
    db.refresh(intent)

    provider = get_provider(db)
    result = provider.create_checkout(db, intent, customer)
    intent.provider = provider.name
    db.commit()
    return intent, result


def _store_lines(intent, lines: list) -> None:
    """``lines`` (JSONB) so zuweisen, dass SQLAlchemy die Änderung erkennt."""
    from sqlalchemy.orm.attributes import flag_modified
    intent.lines = list(lines)
    flag_modified(intent, "lines")


def _create_multiline_sale_order(db: Session, lines: list, customer: UserProfile,
                                 *, allow_backorder: bool = False) -> Order:
    """EIN **Verkaufsauftrag** über eine oder mehrere Positionen (Subjekt = stock/FIFO; er
    **erzeugt NIE selbst Instanzen** – er selektiert vorhandene, freigegebene). Je Position
    ein ``sale``-Schritt + ``Sale``-Beleg; EIN gemeinsamer ``movement``-Schritt (ein Versand).
    Wird sofort freigegeben.

    ``allow_backorder=False`` (ab Lager / limitierte Auflage): bindet streng per FIFO und
    schlägt bei Unterdeckung fehl (kein Überverkauf). ``allow_backorder=True`` («auf
    Bestellung»): bindet, was am Lager ist (ggf. nichts) – die **Fehlmenge** deckt
    anschliessend ein Nachschub-Unter-Auftrag (der Aufrufer ruft ``supply.ensure_supply``)."""
    from .events import emit
    from .objects import next_object_id
    from .orders import release_order

    single = len(lines) == 1
    title = (f"Shop-Kauf: {lines[0]['article_name']}" if single
             else f"Shop-Bestellung ({len(lines)} Positionen)")
    order = Order(
        object_id=next_object_id(db, "order"), status="draft",
        # Mehrpositionen-Auftrag hat keinen einzelnen Artikel; bei einer Position gesetzt.
        article_id=lines[0]["article_id"] if single else None,
        quantity=lines[0]["quantity"] if single else None,
        title=title,
    )
    # Abo nur bei genau einer Position (Abos werden einzeln gekauft).
    if single and lines[0]["kind"] == "subscription":
        l0 = lines[0]
        order.recurrence_active = True
        order.recurrence_kind = l0.get("sub_type") or "usage"
        order.recurrence_interval_days = _interval_days(l0.get("interval"))
        order.recurrence_anchor = utcnow().date() + timedelta(days=order.recurrence_interval_days)
    db.add(order)
    db.flush()

    # Je Position: ein Verkaufs-Schritt + Verkaufsbeleg.
    for i, line in enumerate(lines):
        sale_step = ArticleProcessStep(order_id=order.id, position=i, step_type="sale")
        db.add(sale_step)
        db.flush()
        db.add(Sale(
            order_id=order.id, article_id=line["article_id"], quantity=line["quantity"],
            step_id=sale_step.id, status="requested", customer_id=customer.id, currency="CHF",
            order_total=Decimal(line["net_chf"]) if line.get("net_chf") else None,
            vat_rate=Decimal(line["vat_rate"]) if line.get("vat_rate") else None,
            base_amount_chf=Decimal(line["base_amount_chf"]), fx_date=utcnow().date(),
            mode="shop",
        ))
    # EIN gemeinsamer Versand-Schritt (alle Positionen zum Kunden).
    db.add(ArticleProcessStep(order_id=order.id, position=100, step_type="movement",
                              target_location_type="user" if customer.object_id else None,
                              target_location_id=customer.object_id))
    db.flush()
    log_audit(db, "sales", None, f"Shop-Verkauf angefragt ({len(lines)} Position(en))",
              customer.id, object_id=order.object_id)

    if allow_backorder:
        # «auf Bestellung»: einheitliche Freigabe – reserviert, was am Lager ist (ggf. nichts).
        # Der Versand-Schritt bleibt «blockiert», bis der Nachschub liefert.
        release_order(db, order, customer.id)
    else:
        # ab Lager: streng FIFO binden (Überverkauf vermeiden – schlägt bei Unterdeckung fehl).
        order.status = "released"
        order.released_at = utcnow()
        _materialize_multiline(db, order, lines, customer)
        emit(db, "order.released", object_type="order", object_id=order.object_id,
             payload={"positions": len(lines), "via": "shop"}, actor_id=customer.id)
    db.flush()
    return order


def _materialize_multiline(db: Session, order: Order, lines: list, customer: UserProfile) -> None:
    """Subjekt eines Mehrpositionen-Verkaufsauftrags binden: je Position ``quantity`` Stück
    des Artikels **FIFO ab Lager** auswählen, dem Auftrag zuordnen und reservieren."""
    from .inventory import allocate, available_qty, fifo_candidates
    from .reservation import free_qty, reserve
    from .subject import record_link

    for line in lines:
        art_id, need = line["article_id"], line["quantity"]
        cands = fifo_candidates(db, art_id, for_order_id=None)
        have = available_qty(cands)
        if have < need:
            raise HTTPException(
                409, detail=f"Nicht genügend freigegebener Bestand für {line['article_name']}: "
                            f"benötigt {need}, verfügbar {have}")
        for cand, take in zip(cands, allocate(need, [free_qty(c) for c in cands])):
            if take <= 0:
                continue
            cand.subject_of_order_id = order.id
            reserve(cand, order.id, take)
            record_link(db, cand.object_id, order.id)
    log_audit(db, "instances", None, "Bestand für Verkaufsauftrag reserviert",
              customer.id, object_id=order.object_id)


def _split_snapshot(snap: dict | None, base: Decimal, total_base: Decimal) -> dict | None:
    """Den session-weiten Stripe-Snapshot **anteilig** auf eine Position herunterbrechen
    (proportional zur CHF-Basis). Bei Einzelposition = voller Snapshot."""
    if not snap:
        return None
    settlement = snap.get("settlement") or {}
    total = Decimal(str(settlement.get("total") or 0))
    tax = Decimal(str(settlement.get("tax") or 0))
    frac = (base / total_base) if total_base > 0 else Decimal("1")
    out = dict(snap)
    out["settlement"] = {
        "currency": settlement.get("currency") or "CHF",
        "total": str((total * frac).quantize(CENT)),
        "tax": str((tax * frac).quantize(CENT)),
    }
    return out


def fulfill_intent(db: Session, intent, snapshot: dict | None = None) -> int:
    """Bestätigte Zahlung verarbeiten (idempotent): je Position den Auftrag erzeugen
    (make) bzw. den schon reservierten (stock) finalisieren, Snapshot anteilig einfrieren
    und den Verkauf auf ``paid`` setzen. Liefert die Anzahl finalisierter Positionen."""
    from . import sale as sale_svc

    if intent.status == "completed":
        return 0
    customer = db.query(UserProfile).filter(UserProfile.id == intent.customer_id).first()
    if not customer:
        return 0

    lines = list(intent.lines or [])
    total_base = sum((Decimal(l.get("base_amount_chf") or 0) for l in lines), Decimal("0"))
    done = 0
    processed: set[int] = set()

    def _finalize_order_sales(order: Order, release_order: bool) -> int:
        """Alle Verkaufsbelege eines (Mehrpositionen-) Auftrags als bezahlt verbuchen."""
        n = 0
        for s in db.query(Sale).filter(Sale.order_id == order.id, Sale.is_active == True).all():
            per = _split_snapshot(snapshot, Decimal(s.base_amount_chf or 0), total_base)
            if snapshot and snapshot.get("subscription") and not order.stripe_subscription_id:
                order.stripe_subscription_id = snapshot["subscription"]
            sale_svc.finalize_paid(db, s, stripe=per, release_order=release_order)
            n += 1
        return n

    for line in lines:
        if line.get("order_id"):
            # stock: gemeinsamer Verkaufsauftrag (schon angelegt + reserviert) – nur einmal je Auftrag.
            oid = line["order_id"]
            if oid in processed:
                continue
            processed.add(oid)
            order = db.query(Order).filter(Order.object_id == oid).first()
            if order:
                done += _finalize_order_sales(order, release_order=False)  # bereits released
        else:
            # make («auf Bestellung»): EIN Verkaufsauftrag (Subjekt stock/FIFO). Ist kein
            # Bestand da, deckt ein **Nachschub-Unter-Auftrag** (Produktion) die Fehlmenge –
            # derselbe Mechanismus wie der «Nachschub»-Knopf im ERP. Der Versand-Schritt bleibt
            # blockiert, bis der Nachschub liefert (dann an den Verkauf gepinnt).
            from . import supply
            order = _create_multiline_sale_order(db, [line], customer, allow_backorder=True)
            line["order_id"] = order.object_id
            done += _finalize_order_sales(order, release_order=False)   # bereits freigegeben
            supply.ensure_supply(db, order, customer.id)
    intent.status = "completed"
    _store_lines(intent, lines)
    db.commit()
    return done


def _order_friendly_status(order: Order, sale: Sale) -> str:
    if sale.status == "cancelled":
        return "cancelled"
    if order and order.status == "completed":
        return "completed"
    if sale.status == "paid":
        return "processing"     # bezahlt, in Bearbeitung/Produktion/Versand
    return "requested"


def list_customer_orders(db: Session, customer_id: int) -> list[dict]:
    """Bestellungen eines Kunden (für «Meine Bestellungen» + ERP-User-Reiter), neueste zuerst.

    Eine Bestellung = ein Verkaufsbeleg (``sales``) unter seinem Auftrag. Abo-Infos kommen
    vom Auftrag (Stripe ist die Quelle für den Abo-Status)."""
    sales = (
        db.query(Sale)
        .filter(Sale.customer_id == customer_id, Sale.is_active == True)
        .order_by(Sale.id.desc())
        .all()
    )
    out: list[dict] = []
    for s in sales:
        order = db.query(Order).filter(Order.id == s.order_id).first()
        if not order or not order.is_active:
            continue
        article = db.query(Article).filter(Article.id == s.article_id).first()
        # Bruttobetrag: real bezahlter Snapshot (order_total netto + MWST) sonst CHF-Basis.
        gross = None
        currency = s.currency or "CHF"
        if s.order_total is not None and s.vat_rate is not None:
            gross = (Decimal(s.order_total) * (Decimal("1") + Decimal(s.vat_rate) / Decimal("100"))).quantize(CENT)
        elif s.base_amount_chf is not None:
            gross, currency = Decimal(s.base_amount_chf), "CHF"
        out.append({
            "order_object_id": order.object_id,
            "created_at": s.created_at,
            "title": order.title or (article.name if article else None),
            "article_object_id": article.object_id if article else None,
            "quantity": s.quantity or 1,
            "currency": currency,
            "gross_total": gross,
            "status": _order_friendly_status(order, s),
            "is_subscription": bool(order.recurrence_kind or order.recurrence_active or order.stripe_subscription_id),
            "sub_type": order.recurrence_kind,
            "interval": ("year" if (order.recurrence_interval_days or 0) >= 365 else "month") if order.recurrence_kind else None,
            "subscription_active": bool(order.recurrence_active),
            "has_subscription_management": bool(order.stripe_subscription_id),
            "cancellable_from": earliest_cancellation_date(order),
            **_customer_return_status(db, order, s),
        })
    return out


def _customer_return_status(db: Session, order, sale) -> dict:
    """Retoure-Status einer Bestellung (retournierbar/Frist/angefragt) – nur für einen normalen
    Verkauf (kein Abo, kein Unter-Auftrag). Kapselt den Import (zyklenfrei)."""
    if sale.kind != "sale" or order.recurrence_kind:
        return {"returnable": False, "return_requested": False, "return_deadline": None}
    from .customer_returns import return_status
    return return_status(db, order, sale, sale.customer_id)


def cancel_intent(db: Session, intent) -> None:
    """Checkout abgebrochen/abgelaufen: schon reservierte (stock-) Aufträge auflösen.
    make-Positionen haben (noch) keinen Auftrag – nichts zu tun. Idempotent."""
    from . import sale as sale_svc

    if intent.status in ("completed", "cancelled"):
        return
    processed: set[int] = set()
    for line in list(intent.lines or []):
        oid = line.get("order_id")
        if not oid or oid in processed:
            continue
        processed.add(oid)
        order = db.query(Order).filter(Order.object_id == oid).first()
        if not order:
            continue
        # Alle Belege des (Mehrpositionen-) Auftrags stornieren (löst Reservierungen).
        for sale in db.query(Sale).filter(Sale.order_id == order.id, Sale.is_active == True).all():
            sale_svc.mark_cancelled(db, sale)
    intent.status = "cancelled"
    db.commit()
