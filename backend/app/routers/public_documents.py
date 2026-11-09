"""**Die Seite eines Dokuments nach aussen** – über seinen Link, ohne Anmeldung. EINE Seite für
jedes Dokument, das hinausgeht (``services/signing``): wer den Link hat, sieht genau dieses
Dokument, unterschreibt oder lehnt ab, wenn er als Unterzeichner verlangt ist – und ist es ein
**Papier eines Belegs** (Offerte, Rechnung …), handelt er als die Partei: annehmen, ablehnen, mit
Karte bezahlen, mit denselben Verben wie im ERP (``voucher_docs.public_act``, ``can`` ist die
Tür). Ist es gelöscht: 410 mit einem Satz."""

from typing import Any

from fastapi import APIRouter
from sqlalchemy.orm import Session

from ..core.actor import public
from ..core.database import DB
from ..models import Order
from ..schemas.documents import DeclineIn, PublicDocument, SignIn
from ..schemas.process import PaymentSetup
from ..services import log, signing, stripe_pay, voucher_docs
from ..domain.errors import Conflict

router = APIRouter(prefix="/api/v1/public/document", tags=["public"])


def _page(db: Session, token: str) -> dict[str, Any]:
    """Was die Seite zeigt – das Dokument und, bei einem Papier eines Belegs, der Vorgang (dann
    zeigt sie das aktuelle Papier dieser Partei)."""
    link = signing.by_token(db, token)
    out = signing.view(db, link)
    found = voucher_docs.deal_of(db, link)
    if found is not None:
        deal = voucher_docs.public_view(db, *found)
        out["html"] = deal.pop("html")
        out["deal"] = deal
    return out


@router.get("/{token}", response_model=PublicDocument, dependencies=[public("link")])
def view(token: str, db: Session = DB):
    """Die Seite eines gesendeten Dokuments – **geöffnet** steht im Log (``document.viewed``,
    mit dem Empfänger des Links)."""
    out = _page(db, token)
    link = signing.by_token(db, token)
    log.event(db, "document.viewed", signing.doc_of(db, link).object_id,
              {"person": link.person_object_id}, table="document_links", row=link.id)
    db.flush()
    return out


@router.post("/{token}/sign", response_model=PublicDocument, dependencies=[public("link")])
def sign(token: str, data: SignIn, db: Session = DB):
    """**Unterschreiben** – endgültig."""
    signing.sign(db, signing.by_token(db, token), data.image)
    db.flush()
    return _page(db, token)


@router.post("/{token}/decline", response_model=PublicDocument, dependencies=[public("link")])
def decline(token: str, data: DeclineIn, db: Session = DB):
    """**Die Unterschrift ablehnen** – mit Grund; danach unterschreibt niemand mehr."""
    signing.decline(db, signing.by_token(db, token), data.reason)
    db.flush()
    return _page(db, token)


def _deal(db: Session, token: str):
    found = voucher_docs.deal_of(db, signing.by_token(db, token))
    if found is None:
        raise Conflict("Dieses Dokument ist kein Angebot und keine Rechnung.")
    return found


@router.post("/{token}/agree", response_model=PublicDocument, dependencies=[public("link")])
def agree(token: str, db: Session = DB):
    """**Die Offerte annehmen** – als die Partei; die Auftragsbestätigung geht hinaus."""
    voucher_docs.public_act(db, *_deal(db, token), "agree")
    db.flush()
    return _page(db, token)


@router.post("/{token}/reject", response_model=PublicDocument, dependencies=[public("link")])
def reject(token: str, db: Session = DB):
    """**Die Offerte ablehnen** – als die Partei."""
    voucher_docs.public_act(db, *_deal(db, token), "reject")
    db.flush()
    return _page(db, token)


@router.post("/{token}/payment", response_model=PaymentSetup, dependencies=[public("link")])
def payment(token: str, db: Session = DB):
    """**Mit Karte bezahlen** – die Zahlungsabsicht über den offenen Betrag. Gebucht wird
    erst, wenn der Zahlungsdienst es meldet."""
    row, rec = _deal(db, token)
    if "pay_online" not in voucher_docs.public_view(db, row, rec)["actions"]:
        raise Conflict("Hier ist nichts mit Karte zu bezahlen.")
    order = db.query(Order).filter(Order.id == row.order_id).first()
    return PaymentSetup(**stripe_pay.prepare(db, row=row, order=order,
                                             viewer=voucher_docs.party_user(db, rec)))
