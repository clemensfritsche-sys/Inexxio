"""Die Vergabe – anfragen, anbieten, vergeben, abnehmen (ADR 009 §3.6).

**Ein Endpunkt je Vorgang, keiner je Zustand.** Geschrieben wird nie ein Zustand,
sondern eine Handlung; welcher Zustand daraus folgt, entscheidet die Registry
(``domain/vergabe``). Ein ``PATCH {state: …}`` wäre die zweite Stelle, an der die
Übergangsmatrix gepflegt wird.

**Eigener Router, nicht unter ``/orders``.** Eine Vergabe gehört keinem Auftrag: heute
hängt sie an einer Fuhre, künftig an einer Bedarfszeile. Sie unter den Auftrag zu hängen
hiesse, den zweiten Nutzer später umziehen zu müssen.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Award, UserProfile
from ..schemas.award import (
    AwardCreate, AwardResponse, DeliverInput, GrantInput, OfferCreate, ReasonInput,
)
from ..services import awards as awards_svc
from ..services.admin import log_audit

router = APIRouter(prefix="/api/v1/erp/awards", tags=["awards"])


def _get(db: Session, award_id: int) -> Award:
    row = db.query(Award).filter(Award.id == award_id).first()
    if not row:
        raise HTTPException(404, "Diese Vergabe gibt es nicht.")
    return row


@router.post("", response_model=AwardResponse, status_code=201)
def request_award(data: AwardCreate, db: Session = Depends(get_db),
                  user: UserProfile = Depends(require_employee)):
    """**Anfragen** (V1) – durch den Klick eines Menschen.

    Idempotent: gibt es für denselben Anlass schon eine offene, kommt sie zurück. Ein
    Modul wird oft betrachtet, bevor jemand handelt – eine zweite Zeile je Blick wäre
    ein Vorgang, den niemand bestellt hat.
    """
    award = awards_svc.request(
        db, subject_object_id=data.subject_object_id,
        target_object_id=data.target_object_id, channel=data.channel,
        provider_object_id=data.provider_object_id, actor_id=user.id)
    log_audit(db, "awards", "request", f"Vergabe {award.id} angefragt ({award.channel})",
              user_id=user.id, object_id=award.subject_object_id)
    db.commit()
    return awards_svc.to_response(db, award)


@router.get("/{award_id}", response_model=AwardResponse)
def read_award(award_id: int, db: Session = Depends(get_db),
               _: UserProfile = Depends(require_employee)):
    return awards_svc.to_response(db, _get(db, award_id))


@router.post("/{award_id}/offers", response_model=AwardResponse, status_code=201)
def add_offer(award_id: int, data: OfferCreate, db: Session = Depends(get_db),
              user: UserProfile = Depends(require_employee)):
    """Ein Angebot eintragen (V2) – der Weg des Kanals «Lieferantenportal».

    Derselbe Vorgang wie beim Plattform-Kanal, nur langsamer: Rate-Shopping IST eine
    Ausschreibung. Darum dieselbe Zeile und kein zweiter Mechanismus.
    """
    award = _get(db, award_id)
    awards_svc.add_offer(
        db, award, provider_object_id=data.provider_object_id, amount=data.amount,
        currency=data.currency, days=data.days, label=data.label)
    log_audit(db, "awards", "offer", f"Angebot zu Vergabe {award.id}",
              user_id=user.id, object_id=award.subject_object_id)
    db.commit()
    return awards_svc.to_response(db, award)


@router.post("/{award_id}/grant", response_model=AwardResponse)
def grant(award_id: int, data: GrantInput, db: Session = Depends(get_db),
          user: UserProfile = Depends(require_employee)):
    """**Vergeben** (V3) – ab hier ist ein Zweiter gebunden.

    Das System wählt nie selbst: es darf Angebote holen und das günstigste vorwählen,
    die Wahl trifft ein Mensch. Danach rührt es nichts mehr an, es meldet.
    """
    award = _get(db, award_id)
    awards_svc.grant(db, award, offer_id=data.offer_id,
                     provider_object_id=data.provider_object_id, amount=data.amount,
                     currency=data.currency, due_at=data.due_at, actor_id=user.id)
    log_audit(db, "awards", "grant", f"Vergabe {award.id} vergeben",
              user_id=user.id, object_id=award.subject_object_id)
    db.commit()
    return awards_svc.to_response(db, award)


@router.post("/{award_id}/deliver", response_model=AwardResponse)
def deliver(award_id: int, data: DeliverInput, db: Session = Depends(get_db),
            user: UserProfile = Depends(require_employee)):
    """**Erbracht** (V4) – und erst jetzt entsteht die Ablage.

    Der Ort ist eine Beobachtung: geschrieben wird er, wenn etwas angekommen ist, nicht
    wenn es bestellt wurde. Über ``places.record``, dieselbe eine Stelle wie überall.
    """
    award = _get(db, award_id)
    awards_svc.deliver(db, award, unit_ids=data.instance_unit_ids, actor_id=user.id)
    log_audit(db, "awards", "deliver",
              f"Vergabe {award.id} erbracht, {len(data.instance_unit_ids)} Stück",
              user_id=user.id, object_id=award.subject_object_id)
    db.commit()
    return awards_svc.to_response(db, award)


@router.post("/{award_id}/reject", response_model=AwardResponse)
def reject(award_id: int, data: ReasonInput, db: Session = Depends(get_db),
           user: UserProfile = Depends(require_employee)):
    """**Abgelehnt** (V5) – der Vorgang endet ohne Vergabe."""
    award = _get(db, award_id)
    awards_svc.reject(db, award, reason=data.reason, actor_id=user.id)
    log_audit(db, "awards", "reject", f"Vergabe {award.id} abgelehnt",
              user_id=user.id, object_id=award.subject_object_id)
    db.commit()
    return awards_svc.to_response(db, award)


@router.post("/{award_id}/fail", response_model=AwardResponse)
def fail(award_id: int, data: ReasonInput, db: Session = Depends(get_db),
         user: UserProfile = Depends(require_employee)):
    """**Gescheitert** (V6) – vergeben, aber nicht erbracht. **Grund ist Pflicht.**

    Kein Zurücknehmen: die Matrix geht nie rückwärts, und eine Korrektur ist ein neuer
    Eintrag. Danach bekommt die Sache eine ganz normale **zweite** Vergabe – dass das
    geht, folgt daraus, dass «gescheitert» terminal ist und nicht mehr als offen zählt.
    """
    award = _get(db, award_id)
    awards_svc.fail(db, award, reason=data.reason, actor_id=user.id)
    log_audit(db, "awards", "fail", f"Vergabe {award.id} gescheitert: {award.reason}",
              user_id=user.id, object_id=award.subject_object_id)
    db.commit()
    return awards_svc.to_response(db, award)
