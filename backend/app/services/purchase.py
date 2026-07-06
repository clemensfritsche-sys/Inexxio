"""Geschäftslogik für das Prozessschritt-Modul «Purchase Order».

- ``instantiate_for_order``: erzeugt bei Auftragsfreigabe die Bestellung aus dem
  ``purchase``-Prozessschritt des Artikels.
- ``compute_landed_unit_cost``: Einstandspreis netto/Stück = Bestellsumme ÷ Menge.
- ``apply_update``: rollenabhängige Feldeingaben + Statusübergänge.

Verschlankter Ablauf:
    supplier:  requested → quoted → ordered → received   (+ rejected)
    webshop:   requested → ordered → received
"""

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Article, Order, PurchaseOrder, UserProfile
from ..models.base import utcnow
from . import process
from .admin import log_audit
from .events import emit

# Erlaubte Statusübergänge: Zielstatus → zulässige Ausgangsstatus
_FROM = {
    "quoted": {"requested"},                 # Lieferant offeriert
    "ordered": {"quoted", "requested"},      # Besteller bestellt / Webshop: Summe erfassen
    "received": {"ordered"},                 # Wareneingang
    "rejected": {"quoted"},                  # Besteller lehnt Offerte ab
}

_STAFF_ROLES = ("admin", "employee")
# Offerte-Felder (nur im Status «requested» editierbar)
_OFFER_FIELDS = {"order_total", "lead_time_days", "payment_terms_days"}
# Tracking ist ein optionales Detail von «Bestellt» (Status «ordered»)
_TRACKING_FIELDS = {"tracking_number"}


def _is_staff(user: UserProfile) -> bool:
    return user.role in _STAFF_ROLES


def _is_owner_supplier(po: PurchaseOrder, user: UserProfile) -> bool:
    return user.role == "supplier" and po.supplier_id == user.id


def _offer_editor(po: PurchaseOrder, user: UserProfile) -> bool:
    """Wer die Offerte/Bestellsumme erfassen darf: der **Besteller (Mitarbeiter) immer**
    (Selbst-Beschaffung – er ist nie blockiert, auch ohne zugewiesenen Lieferanten) sowie –
    im Lieferanten-Modus – der zugewiesene **Lieferant** über sein Portal."""
    return _is_staff(user) or _is_owner_supplier(po, user)


def compute_landed_unit_cost(po: PurchaseOrder) -> Optional[Decimal]:
    """Einstandspreis netto/Stück = Bestellsumme ÷ Menge (alles netto, exkl. MWST)."""
    if po.order_total is None or not po.quantity:
        return None
    return (po.order_total / po.quantity).quantize(Decimal("0.0001"))


def resolve_source(article: Article | None) -> tuple[str, Optional[int], Optional[str]]:
    """Bezugsquelle einer Bestellung → ``(mode, supplier_id, webshop_url)``.

    Die Quelle gehört **allein** zur Produktspezifikation (``articles.procurement_mode`` +
    ``default_supplier_id``/``default_webshop_url``): der ``purchase``-Schritt ist nur der
    Auslöser. KEIN Schritt-Override – WO ein Artikel bezogen wird, ist eine Eigenschaft des
    Produkts, nicht des einzelnen Schritts."""
    if article is not None:
        mode = article.procurement_mode or "supplier"
        if mode == "webshop" and article.default_webshop_url:
            return ("webshop", None, article.default_webshop_url)
        if article.default_supplier_id:
            return ("supplier", article.default_supplier_id, None)
        return (mode, None, None)
    return ("supplier", None, None)


def has_source(article: Article | None) -> bool:
    """Ist die Bezugsquelle vollständig hinterlegt? (Lieferant bei ``supplier`` bzw.
    Webshop-Link bei ``webshop``.) Grundlage der Freigabe-Sperre: ein Artikel/Auftrag mit
    Beschaffungs-Schritt ohne hinterlegte Quelle darf nicht freigegeben werden."""
    if article is None:
        return False
    if (article.procurement_mode or "supplier") == "webshop":
        return bool(article.default_webshop_url)
    return bool(article.default_supplier_id)


def instantiate_for_order(db: Session, order: Order, actor_id: int) -> list[PurchaseOrder]:
    """Bei Auftragsfreigabe je Beschaffungs-Schritt **des gewählten Prozesses** eine
    Bestellung anlegen (Mehr-Operationen-Routing über ``step_id``) – EIN Schritt, aber
    bei einem Mehrpositionen-Auftrag (``order_lines``) je Position eine eigene Bestellung
    (eigene Bestellsumme/Menge je Artikel; alle mit demselben ``step_id`` – analog
    ``sale.instantiate_for_order``).

    Idempotent: existiert für eine Position eines Schritts bereits eine Bestellung, wird
    sie übersprungen. Hat der Prozess keinen purchase-Schritt, passiert nichts.
    """
    steps = [d for d in process.order_step_defs(db, order) if d.step_type == "purchase"]
    if not steps:
        return []
    from .order_lines import lines_for
    lines = lines_for(db, order)
    targets = [(l.article_id, l.quantity) for l in lines] if lines else (
        [(order.article_id, order.quantity)] if order.article_id and order.quantity else [])
    if not targets:
        return []
    existing = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.order_id == order.id, PurchaseOrder.is_active == True)
        .all()
    )
    have_by_step: dict[int | None, set[int]] = {}
    for po in existing:
        have_by_step.setdefault(po.step_id, set()).add(po.article_id)
    # Artikel der Positionen batch-laden (Beschaffungs-Default je Position).
    arts = {a.id: a for a in db.query(Article).filter(
        Article.id.in_({art_id for art_id, _ in targets})).all()}
    created: list[PurchaseOrder] = []
    for step in steps:
        have = set(have_by_step.get(step.id, set()))
        if len(steps) == 1:
            have |= have_by_step.get(None, set())   # Altbestellung ohne step_id
        for art_id, qty in targets:
            if art_id in have:
                continue   # idempotent – diese Position hat schon ihre Bestellung
            # Bezugsquelle aus dem Artikel (Spezifikation) – als Snapshot auf die Bestellung
            # (die Bestellung bleibt stabil bei späteren Änderungen der Spezifikation).
            mode, supplier_id, webshop_url = resolve_source(arts.get(art_id))
            po = PurchaseOrder(
                order_id=order.id,
                article_id=art_id,
                quantity=qty,
                step_id=step.id,
                mode=mode,
                supplier_id=supplier_id,
                webshop_url=webshop_url,
                status="requested",
                # Der konkrete Lagerort (Wareneingang) wird erst beim Wareneingang gesetzt.
                receiving_location_id=None,
            )
            db.add(po)
            db.flush()
            have.add(art_id)
            log_audit(db, "purchase_orders", None, "Bestellung angefragt",
                      actor_id, object_id=order.object_id)
            created.append(po)
    # TODO(E-Mail): Lieferant über neue Bestellanfrage benachrichtigen (Gmail API, Phase 2)
    return created


def _editable_fields(po: PurchaseOrder, user: UserProfile) -> set[str]:
    """Felder, die der Aufrufer in diesem Status setzen darf.

    Nur die Offerte-/Bestell-Seite (Lieferant bzw. im Webshop-Modus der
    Mitarbeiter) darf etwas eingeben – saubere Trennung der Verantwortlichkeiten.
    Die Offerte ist nach dem Absenden (≠ requested) gesperrt.
    """
    fields: set[str] = set()
    if _offer_editor(po, user):
        if po.status == "requested":
            fields |= _OFFER_FIELDS
        if po.status == "ordered":
            fields |= _TRACKING_FIELDS
    return fields


def _transition_allowed(po: PurchaseOrder, target: str, user: UserProfile) -> bool:
    if po.mode == "webshop":
        # kein externer Lieferant – der Mitarbeiter führt den ganzen Schritt
        return _is_staff(user)
    # supplier-Modus: der Lieferant darf offerieren, der Besteller (Mitarbeiter) darf alles
    # treiben – inkl. Offerte selbst erfassen ODER direkt bestellen (Selbst-Beschaffung),
    # damit er nie auf einen separaten Lieferanten-Login angewiesen ist.
    if target == "quoted":
        return _is_staff(user) or _is_owner_supplier(po, user)
    if target in ("ordered", "rejected", "received"):
        return _is_staff(user)                           # Besteller
    return False


def _apply_transition(db: Session, po: PurchaseOrder, order: Order, target: str,
                      user: UserProfile) -> None:
    """Statusübergang der Bestellung – **rein kaufmännisch**, ohne Standortwechsel.

    Jeder physische Transport (Versand zum Lieferanten, Wareneingang) läuft über
    den/die Pflicht-Bewegungsschritt(e) rund um die Beschaffung. ``received`` =
    Lieferung/Beleg bestätigt; das Einlagern erledigt danach die Bewegung."""
    if target not in _FROM:
        raise HTTPException(400, detail="Unbekannter Zielstatus")
    if po.status not in _FROM[target]:
        raise HTTPException(400, detail=f"Übergang {po.status} → {target} ist nicht erlaubt")
    if not _transition_allowed(po, target, user):
        raise HTTPException(403, detail="Keine Berechtigung für diesen Schritt")
    if target in ("quoted", "ordered") and po.order_total is None:
        raise HTTPException(400, detail="Bestellsumme ist erforderlich")
    if target == "ordered":
        lc = compute_landed_unit_cost(po)
        po.landed_unit_cost = lc
        if lc is not None:
            art = db.query(Article).filter(Article.id == po.article_id).first()
            if art:
                art.landed_unit_cost = lc
        po.ordered_at = utcnow()
    old = po.status
    po.status = target
    log_audit(db, "purchase_orders", "status", target, user.id,
              object_id=order.object_id, old_value=old)
    emit(db, f"purchase.{target}", object_type="order", object_id=order.object_id,
         actor_id=user.id)
    # Auftrag ggf. automatisch abschliessen (alle Prozessschritte erledigt)
    process.recompute_completion(db, order)
    # TODO(E-Mail): Statuswechsel an Lieferant/uns melden (Gmail API, Phase 2)


def apply_update(db: Session, po: PurchaseOrder, data, user: UserProfile) -> PurchaseOrder:
    """Felder setzen (rollen-/statusabhängig) und optional einen Statusübergang ausführen."""
    if not (_is_staff(user) or _is_owner_supplier(po, user)):
        raise HTTPException(403, detail="Keine Berechtigung für diese Bestellung")
    order = db.query(Order).filter(Order.id == po.order_id).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")

    payload = data.model_dump(exclude_unset=True)
    target = payload.pop("status", None)
    # Lagerort/Transport gehört nicht mehr zur Beschaffung (läuft über die Bewegung);
    # ein evtl. mitgesendetes Feld wird ignoriert. step_id/article_id sind reine
    # Routing-/Disambiguierungsfelder (Mehr-Operationen-Routing bzw. Mehrpositionen),
    # keine Felder DIESER Bestellung.
    payload.pop("receiving_location_id", None)
    payload.pop("step_id", None)
    payload.pop("article_id", None)

    editable = _editable_fields(po, user)
    for key, value in payload.items():
        if key not in editable:
            raise HTTPException(403, detail=f"Feld '{key}' darf in diesem Status nicht geändert werden")
        setattr(po, key, value)

    if target and target != po.status:
        _apply_transition(db, po, order, target, user)

    db.commit()
    db.refresh(po)
    return po


def apply_update_bulk(db: Session, pos: list[PurchaseOrder], data, user: UserProfile) -> list[PurchaseOrder]:
    """Aktualisierung eines Beschaffungs-Schritts – bei einem Mehrpositionen-Auftrag kann
    der Schritt MEHRERE Bestellungen tragen (eine je Artikel/Position). Anders als beim
    Verkauf (eine Sendung, eine gemeinsame Zahlung) ist jede Bestellung hier eine EIGENE,
    unabhängig fortschreitende Beschaffung (eigene Offerte/Lieferzeit, ggf. separat
    geliefert) – jede Aktion (auch ein Statuswechsel) betrifft daher GENAU EINE Position;
    bei mehreren muss ``article_id`` mitgegeben werden, um sie zu identifizieren."""
    if not pos:
        raise HTTPException(404, detail="Für diesen Auftrag existiert keine Bestellung")
    if len(pos) == 1:
        return [apply_update(db, pos[0], data, user)]
    target_article_id = getattr(data, "article_id", None)
    if target_article_id is None:
        raise HTTPException(400, detail="Bei mehreren Positionen bitte die betroffene angeben")
    po = next((p for p in pos if p.article_id == target_article_id), None)
    if not po:
        raise HTTPException(404, detail="Position nicht gefunden")
    return [apply_update(db, po, data, user)]
