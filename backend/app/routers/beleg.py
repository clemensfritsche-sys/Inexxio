"""**Die Seite der Partei** – ein Dokument über seinen unerratbaren Link, ohne Anmeldung.

Wer den Link hat, sieht genau dieses eine Dokument und handelt als die Partei, an die es
ging: annehmen, ablehnen, mit Karte bezahlen. **Dieselben Verben wie im ERP** – ``can`` ist
die Tür (``services/voucher_docs.public_act``); eine zweite Logik gibt es nicht. Dazu die
**AGB** als A4-Dokument (``/agb`` der Website).
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models import Order, Voucher
from ..schemas.process import PaymentSetup
from ..services import address, agb as agb_svc, document, sites, stripe_pay
from ..services import voucher as voucher_svc
from ..services import voucher_docs

router = APIRouter(prefix="/api/v1/public", tags=["public"])


class StationOut(BaseModel):
    who: str
    title: str
    text: str
    #: ``done`` · ``active`` · ``ahead``
    state: str


class NoteOut(BaseModel):
    """Ein Satz statt einer Handlung – abgelaufen, überholt, storniert."""
    kind: str
    title: str
    text: str
    link: Optional[str] = None


class BelegView(BaseModel):
    """**Was die Seite zeigt** – das eingefrorene Papier, der Weg, die Handlungen."""
    #: Der Link des gezeigten Dokuments (ist ein neueres da, ist es dessen).
    token: str
    kind: str
    word: str
    number: Optional[str] = None
    html: str
    note: Optional[NoteOut] = None
    #: ``agree`` · ``decline`` · ``pay_online`` – was die Partei jetzt tun kann.
    actions: list[str] = Field(default_factory=list)
    stations: list[StationOut] = Field(default_factory=list)
    open: Optional[str] = None
    currency: str = "CHF"
    agb: Optional[str] = None


class AgbOut(BaseModel):
    """Die geltenden AGB – ihr Datum und das A4-Dokument."""
    valid_from: str
    html: str


def _doc(db: Session, token: str):
    rec = voucher_docs.by_token(db, token)
    if rec is None:
        raise HTTPException(status_code=404, detail="Diesen Beleg gibt es nicht.")
    return rec


@router.get("/beleg/{token}", response_model=BelegView)
def view(token: str, db: Session = Depends(get_db)) -> Any:
    """Ein Dokument ansehen – das Papier, wie es hinausging, und was jetzt möglich ist."""
    return voucher_docs.public_view(db, _doc(db, token))


def _act(db: Session, token: str, action: str) -> Any:
    rec = _doc(db, token)
    voucher_docs.public_act(db, rec, action)
    db.commit()
    voucher_docs.send_pending(db)
    return voucher_docs.public_view(db, _doc(db, token))


@router.post("/beleg/{token}/accept", response_model=BelegView)
def accept(token: str, db: Session = Depends(get_db)) -> Any:
    """**Die Offerte annehmen** – als die Partei; die Auftragsbestätigung geht hinaus."""
    return _act(db, token, "agree")


@router.post("/beleg/{token}/decline", response_model=BelegView)
def decline(token: str, db: Session = Depends(get_db)) -> Any:
    """**Die Offerte ablehnen** – als die Partei."""
    return _act(db, token, "decline")


@router.post("/beleg/{token}/payment", response_model=PaymentSetup)
def payment(token: str, db: Session = Depends(get_db)) -> Any:
    """**Mit Karte bezahlen** – die Zahlungsabsicht über den offenen Betrag. Gebucht wird
    erst, wenn der Zahlungsdienst es meldet."""
    rec = _doc(db, token)
    if "pay_online" not in voucher_docs.public_view(db, rec)["actions"]:
        raise HTTPException(status_code=409, detail="Hier ist nichts mit Karte zu bezahlen.")
    row = db.query(Voucher).filter(Voucher.id == rec.voucher_id).first()
    order = db.query(Order).filter(Order.id == row.order_id).first()
    return PaymentSetup(**stripe_pay.prepare(db, row=row, order=order))


@router.get("/agb", response_model=AgbOut)
def terms(db: Session = Depends(get_db)) -> Any:
    """**Die AGB, die heute gelten** – als A4-Dokument in der Vorlage aller Dokumente."""
    agb = agb_svc.current()
    if agb is None:
        raise HTTPException(status_code=404, detail="Es sind keine AGB hinterlegt.")
    operator = sites.find_operator(db)
    seat = address.of_company(operator) if operator is not None else {}
    sender = " · ".join(x for x in (sites.legal_name(operator) or "", seat.get("street1") or "",
                                    " ".join(y for y in (seat.get("zip"), seat.get("city"))
                                             if y),
                                    voucher_svc._uid(operator) or "") if x and x != "—")
    return AgbOut(valid_from=agb.key, html=document.standalone_agb(agb, sender=sender))
