"""►►► **Die Pflichtfelder – ein Dokument in ein Feld eines Datensatzes.** ◄◄◄

Regel 6: Ein Pflichtfeld ist änderbar, nie leer. Gesetzt wird es **in derselben Transaktion
wie die Freigabe** (``documents.file``) oder später mit einem schon freigegebenen Dokument
(``documents.set_field``) – nie zweistufig, sonst stünde ein Arztzeugnis für einen Moment
ohne seine Referenz da (und damit für jedes Personal sichtbar).

Je Feld steht hier, **wer** es setzen darf und **was** es am Datensatz auslöst. Die Regel
«änderbar, nie leer» steht nur einmal: in ``documents.set_field``.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Document, Instance, Order, ProcessStep, UserProfile
from . import documents, objects


def _id_of(part: Optional[str], kind: str) -> int:
    try:
        head, value = (part or "").split(":", 1)
        if head != kind:
            raise ValueError
        return int(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"«{part}» ist kein Teil der Art «{kind}».")


def _voucher(db: Session, object_id: int, part: Optional[str]):
    from . import voucher as vs
    step_id = _id_of(part, "step")
    order = db.query(Order).filter(Order.object_id == object_id).first()
    step = db.query(ProcessStep).filter(ProcessStep.id == step_id).first()
    row = vs.of_step(db, step_id) if step is not None else None
    if order is None or step is None or step.order_id != order.id or row is None:
        raise HTTPException(status_code=404, detail="Dieses Zahlungsmodul gibt es nicht.")
    return order, step, row


def _original(db: Session, actor: UserProfile, doc: Document, object_id: int,
              part: Optional[str], extra: dict[str, Any]) -> None:
    """Die Lieferantenrechnung im Zahlungsmodul (Ausgabe). Vor dem Buchen steht sie nur im
    Feld (das Modul füllt seine Felder daraus vor); nach dem Buchen ist es ein Ändern – weicht
    der Betrag ab, wird es mit Grund angenommen, gebucht wird nie neu von selbst."""
    from ..domain import voucher as vo
    from . import voucher_actions as va
    _order, _step, row = _voucher(db, object_id, part)
    if vo.of(row.direction).collects:
        raise HTTPException(status_code=409, detail="Eine Lieferantenrechnung gibt es nur bei einer Ausgabe.")
    if row.stage not in (vo.AGREED, vo.BILLED):
        raise HTTPException(status_code=409, detail="Die Rechnung kommt erst nach der Zusage.")
    if row.stage == vo.BILLED:
        note = " ".join(str(extra.get("note") or "").split())[:200]
        amount = extra.get("amount")
        if amount is not None and row.amount is not None and va.amount_of(amount, row.currency) != row.amount:
            if not note:
                raise HTTPException(status_code=400, detail=(
                    "Der Betrag weicht vom gebuchten ab – so annehmen geht nur mit Grund."))
            row.deviation_note = note
        row.original_id = doc.object_id


def _export(db: Session, actor: UserProfile, doc: Document, object_id: int,
            part: Optional[str], extra: dict[str, Any]) -> None:
    from ..domain import voucher as vo
    _order, _step, row = _voucher(db, object_id, part)
    if row.stage != vo.BILLED:
        raise HTTPException(status_code=409, detail="Der Ausfuhrnachweis kommt nach der Rechnung.")
    if row.export_number:
        row.export_photo_id = doc.object_id


def _proof(db: Session, actor: UserProfile, doc: Document, object_id: int,
           part: Optional[str], extra: dict[str, Any]) -> None:
    """Der Nachweis einer Absenz – über die EINE Schreibstelle der Zeiterfassung."""
    from ..schemas.timekeeping import EntryIn
    from . import timekeeping
    absence = _id_of(part, "time")
    person = db.query(UserProfile).filter(UserProfile.object_id == object_id).first()
    if person is None or not timekeeping.may_see(actor, person):
        raise HTTPException(status_code=404, detail="Diese Zeiterfassung gibt es nicht.")
    timekeeping.record(db, actor, person, EntryIn(
        kind="proof", replaces_id=absence, proof_url=documents.file_url(db, doc)))


def _photo(db: Session, actor: UserProfile, doc: Document, object_id: int,
           part: Optional[str], extra: dict[str, Any]) -> None:
    """Ein Bild der Datenerfassung – es hängt am Stück und erscheint bei seiner Instanz."""
    if db.query(Instance.id).filter(Instance.object_id == object_id).first() is None:
        raise HTTPException(status_code=404, detail="Diese Instanz gibt es nicht.")
    number = (part or "").split(":", 1)[-1]
    if not (part or "").startswith("unit:") or not number.startswith(objects.obj_nr(object_id)):
        raise HTTPException(status_code=400, detail=f"«{part}» ist kein Stück dieser Instanz.")


def _company(db: Session, actor: UserProfile, doc: Document, object_id: int,
             part: Optional[str], extra: dict[str, Any]) -> None:
    """AGB und Datenschutz einer eigenen Gesellschaft – setzt nur der Admin."""
    from . import sites
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="Rechtstexte setzt nur der Admin.")
    sites.require_own(db, object_id)


Handler = Callable[[Session, UserProfile, Document, int, Optional[str], dict[str, Any]], None]

#: ►►► **Was ein Pflichtfeld am Datensatz auslöst.** ◄◄◄ ``voucher.doc`` setzt nur das
#: Zahlungsmodul selbst (``voucher_docs``) – von aussen gibt es dafür keinen Weg.
HANDLERS: dict[str, Handler] = {
    "voucher.original": _original,
    "voucher.export": _export,
    "time.proof": _proof,
    "capture.photo": _photo,
    "company.agb": _company,
    "company.privacy": _company,
}


def apply(db: Session, *, actor: UserProfile, doc: Document, object_id: int,
          part: Optional[str], field: str, extra: Optional[dict[str, Any]] = None) -> Document:
    """Ein Dokument in ein Pflichtfeld – prüfen, auslösen, Referenz setzen."""
    handler = HANDLERS.get(field)
    if handler is None:
        raise HTTPException(status_code=400, detail=f"Das Feld «{field}» setzt man hier nicht.")
    handler(db, actor, doc, object_id, part, extra or {})
    return documents.set_field(db, document_object_id=doc.object_id, object_id=object_id,
                               part=part, field=field, actor=actor)
