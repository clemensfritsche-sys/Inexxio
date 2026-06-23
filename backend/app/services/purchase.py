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
    """Wer die Offerte/Bestellsumme erfasst: im Webshop-Modus der Mitarbeiter, sonst der Lieferant."""
    if po.mode == "webshop":
        return _is_staff(user)
    return _is_owner_supplier(po, user)


def compute_landed_unit_cost(po: PurchaseOrder) -> Optional[Decimal]:
    """Einstandspreis netto/Stück = Bestellsumme ÷ Menge (alles netto, exkl. MWST)."""
    if po.order_total is None or not po.quantity:
        return None
    return (po.order_total / po.quantity).quantize(Decimal("0.0001"))


def instantiate_for_order(db: Session, order: Order, actor_id: int) -> list[PurchaseOrder]:
    """Bei Auftragsfreigabe je Beschaffungs-Schritt **des gewählten Prozesses** eine
    Bestellung anlegen (Mehr-Operationen-Routing über ``step_id``).

    Idempotent: existiert für einen Schritt bereits eine Bestellung, wird sie
    übersprungen. Hat der Prozess keinen purchase-Schritt, passiert nichts.
    """
    if not order.article_id or not order.quantity:
        return []
    steps = [d for d in process.order_step_defs(db, order) if d.step_type == "purchase"]
    if not steps:
        return []
    existing = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.order_id == order.id, PurchaseOrder.is_active == True)
        .all()
    )
    has_step = {po.step_id for po in existing if po.step_id is not None}
    legacy_unrouted = any(po.step_id is None for po in existing)
    created: list[PurchaseOrder] = []
    for step in steps:
        if step.id in has_step:
            continue
        if legacy_unrouted and len(steps) == 1:
            continue  # Altbestellung ohne step_id gehört dem einzigen Schritt
        po = PurchaseOrder(
            order_id=order.id,
            article_id=order.article_id,
            quantity=order.quantity,
            step_id=step.id,
            mode=step.mode,
            supplier_id=step.supplier_id,
            webshop_url=step.webshop_url,
            status="requested",
            # Der konkrete Lagerort (Wareneingang) wird erst beim Wareneingang gesetzt.
            receiving_location_id=None,
        )
        db.add(po)
        db.flush()
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
    # supplier-Modus: saubere Trennung der Verantwortlichkeiten
    if target == "quoted":
        return _is_owner_supplier(po, user)              # Lieferant offeriert
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
    # ein evtl. mitgesendetes Feld wird ignoriert.
    payload.pop("receiving_location_id", None)

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
