"""Geschäftslogik für den Prozessschritt «Verkauf» – das Spiegelbild der Beschaffung.

Rein kaufmännisch (der physische Versand läuft über die Bewegung, Ziel = Kunde):
    requested → confirmed → invoiced → paid   (+ cancelled)

- ``instantiate_for_order``: bei Auftragsfreigabe je sale-Schritt einen Verkauf anlegen.
- ``apply_update``: Feldeingaben + Statusübergänge.
"""

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Article, Order, Sale, UserProfile
from ..models.base import utcnow
from . import process
from .admin import log_audit
from .events import emit
from .order_lines import lines_for

_STAFF_ROLES = ("admin", "employee")
# Erlaubte Übergänge: Zielstatus → zulässige Ausgangsstatus
_FROM = {
    "confirmed": {"requested"},
    "invoiced": {"confirmed"},
    "paid": {"invoiced"},
    "cancelled": {"requested", "confirmed", "invoiced"},
}
_EDITABLE = ("order_total", "vat_rate", "currency", "customer_id", "invoice_number",
            "payment_method", "payment_reference")
# Zahlungsart, die Personal manuell wählen kann (kein Kartenterminal nötig – der übliche
# B2B-Weg ist die Rechnung/QR-Rechnung). 'stripe' setzt das System selbst (Shop-Zahlung);
# 'terminal' (Stripe Terminal / Kartenleser vor Ort) ist vorgesehen, aber noch nicht wählbar.
PAYMENT_METHODS_STAFF = ("invoice", "cash", "twint", "other")


def unit_price(sale: Sale) -> Optional[Decimal]:
    """Verkaufs-Stückpreis netto = Verkaufsbetrag ÷ Menge."""
    if sale.order_total is None or not sale.quantity:
        return None
    return (sale.order_total / sale.quantity).quantize(Decimal("0.0001"))


def customer_for_order(db: Session, order: Order) -> Optional[UserProfile]:
    """Der Kunde dieses Auftrags = Kunde seines Verkaufs-Belegs (``kind='sale'``). Grundlage
    für den **Pflicht-Versand zum Kunden**: die auf einen Verkauf folgende Bewegung geht
    IMMER an diesen Kunden (kein frei wählbares Ziel). Ein Mehrpositionen-Auftrag hat EINEN
    Kunden (alle Belege teilen ihn) → der erste Beleg mit gesetztem Kunden genügt."""
    sale = (
        db.query(Sale)
        .filter(Sale.order_id == order.id, Sale.kind == "sale",
                Sale.is_active == True, Sale.customer_id.isnot(None))
        .order_by(Sale.id)
        .first()
    )
    if not sale or not sale.customer_id:
        return None
    return db.query(UserProfile).filter(UserProfile.id == sale.customer_id).first()


def price_from_article(db: Session, article_id: int, quantity: int) -> Optional[dict]:
    """Preis-Vorschau EINES Artikels aus der **Shop-Preis-Pipeline** – Single Source of
    Truth: der ERP-Direktverkauf tippt keinen Betrag frei ein, sondern übernimmt densel-
    ben Basispreis wie der Shop (``article_prices``). Bewusst über ``resolve_one_time_price``
    (nicht ``resolve_primary_price``): ein Artikel kann NEBEN einem Abo zusätzlich einen
    Einmalkauf-Preis tragen – der ERP-Direktverkauf nutzt dann IMMER diesen, unabhängig
    davon, welche Preisoption im Shop als „primär" (oberste Option) gilt. ``None`` nur,
    wenn der Artikel ausschliesslich über ein Abo verkauft wird (rein interne Artikel ohne
    jeden Preis bleiben ebenfalls manuell einzutragen – siehe ``_EDITABLE``)."""
    from . import pricing
    art = db.query(Article).filter(Article.id == article_id).first()
    if not art:
        return None
    price = pricing.resolve_one_time_price(db, article_id)
    if not price:
        return None
    view = pricing.price_view_for(db, price, "CHF", country=None, customer=None)
    if not view or view.get("net") is None:
        return None
    return {
        "order_total": (Decimal(view["net"]) * quantity).quantize(Decimal("0.01")),
        "vat_rate": Decimal(str(view["tax_rate"])) if view.get("tax_rate") is not None else None,
        "currency": "CHF",
    }


def assert_sale_compatible(db: Session, article_ids: set[int]) -> None:
    """Mehrere Artikel dürfen nur GEMEINSAM verkauft werden, wenn KEINER von ihnen
    ausschliesslich über ein Abo verkauft wird (Stripe: ein Checkout ist entweder
    Einmalkauf oder Abo; der Verkaufsschritt hat keine Möglichkeit, je Position ein
    anderes Preismodell zu wählen). Bei genau EINEM Artikel keine Einschränkung – ein
    einzelnes Abo lässt sich wie gewohnt verkaufen. Trägt ein Artikel NEBEN dem Abo auch
    einen Einmalkauf-Preis, gilt er nicht als exklusiv und darf mitgemischt werden
    (``pricing.is_subscription_exclusive``) – nur dann nutzt der Verkauf ohnehin den
    Einmalkauf-Preis (``price_from_article``)."""
    if len(article_ids) <= 1:
        return
    from . import pricing
    for aid in article_ids:
        if pricing.is_subscription_exclusive(db, aid):
            art = db.query(Article).filter(Article.id == aid).first()
            name = f"«{art.name}»" if art else f"Artikel #{aid}"
            raise HTTPException(
                400,
                detail=f"{name} ist ein Abo-Artikel – Abos lassen sich nur einzeln verkaufen, "
                       "nicht zusammen mit weiteren Positionen")


def _prefill_price(db: Session, sale: Sale, article_id: int) -> None:
    """Preis **aus dem Artikel** übernehmen (siehe ``price_from_article``) – die einzige
    Quelle der Wahrheit. Ohne Artikel-Preis bleibt der Betrag leer (Personal trägt ihn
    für diesen internen Artikel frei ein, wie bisher)."""
    view = price_from_article(db, article_id, sale.quantity)
    if not view:
        return
    sale.order_total = view["order_total"]
    sale.vat_rate = view["vat_rate"]
    sale.currency = view["currency"]


def instantiate_for_order(db: Session, order: Order, actor_id: int) -> list[Sale]:
    """Bei Auftragsfreigabe die Belege des `sale`-Schritts anlegen. **EIN** Schritttyp (`sale`),
    aber **zwei Modi – aus dem Subjekt ABGELEITET** (kein eigener Schritttyp, kein Button):

    - **Verkauf** (`kind='sale'`, Normalfall): je Artikel EIN Beleg (Einzel-Artikel oder je
      Position eines Mehrpositionen-Auftrags), Betrag aus dem Artikel-Preis (`_prefill_price`).
    - **Gutschrift/Rückerstattung** (`kind='credit'`): sobald der Auftrag auf **verkaufte**
      Instanzen wirkt (`is_return(order)`, Subjekt sold + `parent_order_id`=Original-Verkauf) – je
      Artikel der verkauften Instanzen EIN Gutschrift-Beleg, Betrag/MWST/Kunde aus dem Original
      abgeleitet (`_credit_targets`/`_prefill_credit`, editierbar für Kulanz/Teilbetrag).

    Jeder Beleg trägt die `step_id` seines Schritts (Mehr-Operationen-Routing). Idempotent."""
    from .subject import is_return
    steps = [d for d in process.order_step_defs(db, order) if d.step_type == "sale"]
    if not steps:
        return []
    credit = is_return(order)
    created: list[Sale] = []
    for step in steps:
        if credit:
            targets = _credit_targets(db, order)
        else:
            lines = lines_for(db, order)
            targets = [(l.article_id, l.quantity) for l in lines] if lines else (
                [(order.article_id, order.quantity)] if order.article_id and order.quantity else [])
        if not targets:
            continue
        have_articles = {
            s.article_id for s in
            db.query(Sale).filter(Sale.order_id == order.id, Sale.step_id == step.id,
                                  Sale.is_active == True).all()
        }
        for art_id, qty in targets:
            if art_id in have_articles:
                continue   # idempotent – dieser Artikel hat schon seinen Beleg
            sale = Sale(order_id=order.id, article_id=art_id, quantity=qty,
                        step_id=step.id, status="requested", mode="direct",
                        kind="credit" if credit else "sale")
            if credit:
                _prefill_credit(db, sale, order, art_id)
            else:
                _prefill_price(db, sale, art_id)
            db.add(sale)
            db.flush()
            log_audit(db, "sales", None, "Gutschrift angelegt" if credit else "Verkauf angefragt",
                      actor_id, object_id=order.object_id)
            created.append(sale)
    # TODO(E-Mail/Beleg): Auftragsbestätigung/Rechnung/Gutschrift erzeugen (Gmail API/PDF, Phase 2)
    return created


def _parent_order(db: Session, order: Order) -> Order | None:
    if not order.parent_order_id:
        return None
    return db.query(Order).filter(Order.object_id == order.parent_order_id).first()


def original_sale_for(db: Session, order: Order, article_id: int) -> Sale | None:
    """Der Original-Verkaufs-Beleg (kind='sale') des Eltern-Auftrags für diesen Artikel –
    Grundlage der Gutschrift (Betrag/MWST/Kunde/Stripe-PaymentIntent)."""
    parent = _parent_order(db, order)
    if not parent:
        return None
    return (
        db.query(Sale)
        .filter(Sale.order_id == parent.id, Sale.article_id == article_id,
                Sale.kind == "sale", Sale.is_active == True)
        .order_by(Sale.id)
        .first()
    )


def _credit_targets(db: Session, order: Order) -> list[tuple[int, int]]:
    """Je Artikel der zurückkommenden (verkauften) Subjekt-Instanzen: (article_id, Anzahl).
    Bei Einzelteilen exakt; bei Chargen passt Personal den Betrag ggf. an (Restocking-Fee)."""
    from .subject import order_instances
    counts: dict[int, int] = {}
    for inst in order_instances(db, order):
        counts[inst.article_id] = counts.get(inst.article_id, 0) + 1
    return list(counts.items())


def _prefill_credit(db: Session, sale: Sale, order: Order, article_id: int) -> None:
    """Gutschrift-Betrag/MWST/Kunde/Original-Verweis aus dem Original-Verkauf ableiten:
    Stückpreis × zurückkommende Menge (Betrag = Magnitude; ``kind='credit'`` sagt die Richtung).
    Ohne auffindbaren Original-Beleg bleibt der Betrag leer (Personal trägt ihn ein)."""
    orig = original_sale_for(db, order, article_id)
    if not orig:
        return
    sale.original_sale_id = orig.id
    sale.customer_id = orig.customer_id
    sale.currency = orig.currency
    sale.vat_rate = orig.vat_rate
    if orig.order_total is not None and orig.quantity:
        unit = orig.order_total / orig.quantity
        sale.order_total = (unit * sale.quantity).quantize(Decimal("0.01"))


def _apply_transition(db: Session, sale: Sale, order: Order, target: str, user: UserProfile) -> None:
    if target not in _FROM:
        raise HTTPException(400, detail="Unbekannter Zielstatus")
    if sale.status not in _FROM[target]:
        raise HTTPException(400, detail=f"Übergang {sale.status} → {target} ist nicht erlaubt")
    if target in ("confirmed", "invoiced"):
        # Betrag als Single Source of Truth: fehlt er noch, frisch nachziehen – beim **Verkauf**
        # aus dem Artikel-Preis, bei der **Gutschrift** aus dem Original-Verkauf. Sonst bliebe ein
        # Mehrpositionen-Beleg stecken (Betrag dort nicht manuell editierbar).
        if sale.order_total is None and sale.article_id:
            if sale.kind == "credit":
                _prefill_credit(db, sale, order, sale.article_id)
            else:
                _prefill_price(db, sale, sale.article_id)
        if sale.order_total is None:
            raise HTTPException(400, detail="Betrag ist erforderlich")
        # Ein Verkauf ohne Kunde ist fachlich nicht zulässig – der Kunde ist NIE optional,
        # sobald der Verkauf bestätigt/fortgeschrieben wird (spätestens zur Bestätigung).
        if sale.customer_id is None:
            raise HTTPException(400, detail="Kunde ist erforderlich")
    is_credit = sale.kind == "credit"
    # Gutschrift-Beleg (Retoure): unveränderliche, fortlaufende Nummer bei der Bestätigung.
    if is_credit and target in ("confirmed", "invoiced") and not sale.credit_note_number:
        sale.credit_note_number = f"GS-{sale.id}"
    now = utcnow()
    if target == "confirmed":
        sale.confirmed_at = now
    elif target == "invoiced":
        sale.invoiced_at = now
    elif target == "paid":
        sale.paid_at = now
        if is_credit:
            # «Bezahlt» einer Gutschrift = **erstattet**: Stripe-Refund gegen den Original-
            # PaymentIntent (bzw. manuell/Direktverkauf → nur lokal als erstattet markiert).
            _issue_refund(db, sale)
            sale.refunded_at = now
        elif sale.payment_method is None:
            # Personal-erfasste Zahlung ohne gewählte Zahlungsart: Rechnung ist der übliche
            # B2B-Weg (kein Kartenterminal nötig) – sinnvoller Default statt eines leeren Felds.
            sale.payment_method = "invoice"
    old = sale.status
    sale.status = target
    log_audit(db, "sales", "status", target, user.id, object_id=order.object_id, old_value=old)
    event = "sale.refunded" if (is_credit and target == "paid") else f"sale.{target}"
    emit(db, event, object_type="order", object_id=order.object_id, actor_id=user.id)
    # **Label-Wechsel dann, wann es wirklich passiert:** ist der Verkauf bezahlt, verlässt die
    # Ware den Bestand → «verkauft» (nicht erst am Auftragsende). Idempotent; make-to-order zieht
    # beim Abschluss nach. Eine Gutschrift (kind='credit') bucht KEINEN Verkaufs-Abgang.
    if target == "paid" and not is_credit:
        process.sell_order_subjects(db, order)
    # Auftrag ggf. automatisch abschliessen (alle Schritte erledigt).
    process.recompute_completion(db, order)


def _issue_refund(db: Session, credit: Sale) -> None:
    """Gutschrift erstatten: über den Zahlungs-Provider gegen den **Original-PaymentIntent**
    (Stripe – voll oder anteilig). Der manuelle/Direkt-Verkauf hat keinen Online-Beleg → der
    Provider liefert ``None``, die Gutschrift gilt lokal als erstattet (Abwicklung per
    Rechnung/QR offline). Idempotent (kein zweiter Refund, wenn schon eine ``stripe_refund_id``)."""
    if credit.stripe_refund_id:
        return
    orig = (db.query(Sale).filter(Sale.id == credit.original_sale_id).first()
            if credit.original_sale_id else None)
    from .payments import get_provider
    result = get_provider(db).refund(db, orig, credit)
    if result and result.get("refund_id"):
        credit.stripe_refund_id = result["refund_id"]
        credit.stripe_snapshot = result.get("snapshot")
        if result.get("payment_method"):
            credit.payment_method = result["payment_method"]


def _release_on_payment(db: Session, order: Order, actor_id: int | None) -> None:
    """Auftrag bei bestätigter Zahlung freigeben (Defer-Modell: erst zahlen, dann erfüllen)
    über die **einheitliche** Freigabe (kein Sonderpfad). Idempotent (No-op, wenn schon
    freigegeben). Die Fehlmenge eines Verkaufs «auf Bestellung» deckt anschliessend der
    Nachschub (``services/supply.py``)."""
    from .orders import release_order
    release_order(db, order, actor_id)


def _apply_stripe_snapshot(sale: Sale, snap: dict) -> None:
    """Real bezahlten Betrag/Währung/Steuer (Stripe) auf den Beleg einfrieren."""
    settlement = snap.get("settlement") or {}
    cur = (settlement.get("currency") or sale.currency or "CHF").upper()
    total = Decimal(str(settlement.get("total") or 0))      # brutto (inkl. Steuer)
    tax = Decimal(str(settlement.get("tax") or 0))
    net = total - tax
    sale.currency = cur
    sale.order_total = net.quantize(Decimal("0.01"))        # netto im Settlement (CHF)
    if net > 0:
        sale.vat_rate = (tax / net * Decimal("100")).quantize(Decimal("0.01"))
    sale.stripe_payment_intent_id = snap.get("payment_intent")
    sale.stripe_snapshot = snap
    sale.payment_method = "stripe"


def finalize_paid(db: Session, sale: Sale, stripe: dict | None = None,
                  release_order: bool = True) -> Sale:
    """Zahlungseingang verarbeiten: Auftrag freigeben (falls noch Entwurf), Snapshot
    einfrieren und den Verkauf auf ``paid`` setzen. Idempotent (Webhooks treffen mehrfach).

    ``stripe`` (optional): real bezahlte Beträge von Stripe (sonst gilt die eigene CHF-Pipeline,
    deren Snapshot bei der Bestellung gesetzt wurde).
    ``release_order=False``: Zahlung verbuchen, aber den Verkaufsauftrag NICHT freigeben
    (Make-to-Order: die Freigabe erfolgt erst, wenn die verknüpfte Produktion fertig ist)."""
    if sale.status == "paid":
        return sale
    order = db.query(Order).filter(Order.id == sale.order_id).first()
    actor_id = sale.customer_id
    if order:
        if release_order:
            _release_on_payment(db, order, actor_id)
        if stripe and stripe.get("subscription") and not order.stripe_subscription_id:
            order.stripe_subscription_id = stripe["subscription"]
    if stripe:
        _apply_stripe_snapshot(sale, stripe)
    now = utcnow()
    if sale.confirmed_at is None:
        sale.confirmed_at = now
    if sale.invoiced_at is None:
        sale.invoiced_at = now
    sale.paid_at = now
    sale.status = "paid"
    oid = order.object_id if order else None
    log_audit(db, "sales", "status", "paid", None, object_id=oid)
    emit(db, "sale.paid", object_type="order", object_id=oid)
    if order:
        # Bezahlt = «verkauft», sobald es wirklich passiert (Label-Wechsel bei Zahlung, nicht
        # erst am Auftragsende). Idempotent; make-to-order zieht beim Abschluss nach.
        if sale.kind != "credit":
            process.sell_order_subjects(db, order)
        process.recompute_completion(db, order)   # ggf. Auftrag abschliessen (Versand erfolgt)
    db.commit()
    db.refresh(sale)
    return sale


def mark_paid(db: Session, sale: Sale) -> Sale:
    """Kompatibilität: Zahlungseingang ohne externen Snapshot (eigene CHF-Pipeline)."""
    return finalize_paid(db, sale, stripe=None)


def mark_cancelled(db: Session, sale: Sale) -> Sale:
    """Zahlung abgebrochen/storniert: Verkauf ``cancelled`` und den (unbezahlten)
    Auftrag auflösen – Reservierungen freigeben, Auftrag inaktiv (kein herrenloser
    Bestand). Idempotent."""
    if sale.status in ("paid", "cancelled"):
        return sale
    sale.status = "cancelled"
    order = db.query(Order).filter(Order.id == sale.order_id).first()
    oid = order.object_id if order else None
    log_audit(db, "sales", "status", "cancelled", None, object_id=oid)
    emit(db, "sale.cancelled", object_type="order", object_id=oid)
    if order and order.status in ("draft", "released"):
        from .deactivation import cancel_order_effects
        if order.status == "released":
            cancel_order_effects(db, order, None)
        order.status = "inactive"
    db.commit()
    db.refresh(sale)
    return sale


def apply_update(db: Session, sale: Sale, data, user: UserProfile) -> Sale:
    if user.role not in _STAFF_ROLES:
        raise HTTPException(403, detail="Keine Berechtigung für diesen Verkauf")
    order = db.query(Order).filter(Order.id == sale.order_id).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    payload = data.model_dump(exclude_unset=True)
    payload.pop("step_id", None)
    target = payload.pop("status", None)
    if sale.status in ("paid", "cancelled") and (payload or target):
        raise HTTPException(400, detail="Abgeschlossener Verkauf ist gesperrt")
    for key in _EDITABLE:
        if key in payload:
            setattr(sale, key, payload[key])
    if target and target != sale.status:
        _apply_transition(db, sale, order, target, user)
    db.commit()
    db.refresh(sale)
    return sale


_MONEY_FIELDS = ("order_total", "vat_rate", "currency")


def apply_update_bulk(db: Session, sales: list[Sale], data, user: UserProfile) -> list[Sale]:
    """Eine Aktualisierung auf ALLE Verkaufsbelege EINES Verkaufs-Schritts anwenden – bei
    mehreren Artikeln (Mehrpositionen-Auftrag) teilen sie sich Kunde/Status/Zahlungsart
    (eine Sendung, eine Zahlung); der Betrag kommt **aus dem Artikel** (Single Source of
    Truth, ``price_from_article``) und ist bei mehreren Belegen NICHT frei editierbar –
    nur bei genau einem Beleg (Einzel-Artikel-Auftrag ODER ein Artikel ohne Preis) bleibt
    die manuelle Eingabe wie bisher möglich."""
    if not sales:
        raise HTTPException(404, detail="Für diesen Auftrag existiert kein Verkauf")
    if len(sales) == 1:
        return [apply_update(db, sales[0], data, user)]
    payload = data.model_dump(exclude_unset=True)
    if any(f in payload for f in _MONEY_FIELDS):
        raise HTTPException(
            400, detail="Bei mehreren Positionen kommt der Betrag vom Artikel – nicht direkt editierbar")
    return [apply_update(db, s, data, user) for s in sales]
