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

from ..models import (
    Article, ArticleProcessStep, Instance, Order, PurchaseOrder, StorageLocation, UserProfile,
)
from ..models.base import utcnow
from . import process
from .admin import log_audit
from .events import emit
from .locations import resolve_receiving_location

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
    """Bei Auftragsfreigabe die Bestellung aus dem purchase-Prozessschritt anlegen.

    Idempotent: existiert bereits eine Bestellung zum Auftrag, wird nichts erzeugt.
    Hat der Artikel keinen purchase-Schritt, passiert nichts.
    """
    if not order.article_id or not order.quantity:
        return []
    existing = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.order_id == order.id, PurchaseOrder.is_active == True)
        .first()
    )
    if existing:
        return [existing]
    step = (
        db.query(ArticleProcessStep)
        .filter(
            ArticleProcessStep.article_id == order.article_id,
            ArticleProcessStep.step_type == "purchase",
            ArticleProcessStep.is_active == True,
        )
        .order_by(ArticleProcessStep.id)
        .first()
    )
    if not step:
        return []
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
    # TODO(E-Mail): Lieferant über neue Bestellanfrage benachrichtigen (Gmail API, Phase 2)
    return [po]


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


def _relocate_to_receiving(db: Session, po: PurchaseOrder, order: Order, actor_id: int) -> None:
    """Wareneingang: bei «received» wechseln die Instanzen an die Lieferadresse.

    Damit bildet der Beschaffungsschritt den physischen Wareneingang ab – die
    Instanzen verlassen den Lieferanten-Standort und liegen anschliessend an der
    im Schritt definierten Lieferadresse (sonst automatischer Wareneingang), von
    wo der Bewegungs-Schritt sie weiterverteilt."""
    recv_id = resolve_receiving_location(db, po)
    instances = (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .all()
    )
    for inst in instances:
        if (inst.location_type, inst.location_id) != ("lagerplatz", recv_id):
            log_audit(db, "instances", "location", f"lagerplatz:{recv_id}",
                      actor_id, object_id=inst.object_id,
                      old_value=f"{inst.location_type}:{inst.location_id}")
            inst.location_type = "lagerplatz"
            inst.location_id = recv_id


def _resolve_received_location(db: Session, recv_id: int | None) -> int:
    """Beim Wareneingang ist der aktuelle Lagerort PFLICHT (freigegebener Lagerplatz)."""
    if not recv_id:
        raise HTTPException(400, detail="Bitte den aktuellen Lagerort des Wareneingangs angeben")
    loc = (
        db.query(StorageLocation)
        .filter(StorageLocation.object_id == recv_id, StorageLocation.is_active == True)
        .first()
    )
    if not loc or loc.status != "released":
        raise HTTPException(400, detail="Lagerort muss ein freigegebener Lagerplatz sein")
    return recv_id


def _apply_transition(db: Session, po: PurchaseOrder, order: Order, target: str,
                      user: UserProfile, receiving_location_id: int | None = None) -> None:
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
    # Wareneingang: aktuellen Lagerort verpflichtend festhalten, dann Instanzen umlagern
    if target == "received":
        po.receiving_location_id = _resolve_received_location(db, receiving_location_id)
    old = po.status
    po.status = target
    log_audit(db, "purchase_orders", "status", target, user.id,
              object_id=order.object_id, old_value=old)
    emit(db, f"purchase.{target}", object_type="order", object_id=order.object_id,
         actor_id=user.id)
    if target == "received":
        _relocate_to_receiving(db, po, order, user.id)
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
    # Lagerort des Wareneingangs: kein frei editierbares Feld, sondern Pflichteingabe
    # beim Übergang auf «received» (vom Besteller erfasst).
    receiving_location_id = payload.pop("receiving_location_id", None)

    editable = _editable_fields(po, user)
    for key, value in payload.items():
        if key not in editable:
            raise HTTPException(403, detail=f"Feld '{key}' darf in diesem Status nicht geändert werden")
        setattr(po, key, value)

    if target and target != po.status:
        _apply_transition(db, po, order, target, user, receiving_location_id)

    db.commit()
    db.refresh(po)
    return po
