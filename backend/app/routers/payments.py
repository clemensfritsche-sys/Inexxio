"""**Die eine Tür, durch die der Zahlungsdienst hereinruft.**

Ein Endpunkt, keine Anmeldung, eine Signaturprüfung. Er schreibt **eine Zeile Geld**
(``voucher_money.record_payment``); was daraus folgt (Quittung, die Stücke einer Vorauszahlung
ziehen weiter), geschieht dort an derselben Stelle wie bei einer erfassten Zahlung.

Er steht **nicht** im Auftrags-Router, obwohl der Beleg dort lebt: dieser Router ist
öffentlich, und die Grenze zwischen «angemeldetes Personal» und «ein Fremder mit einer
Signatur» soll man an der Datei sehen.
"""

from fastapi import APIRouter, Header, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..core.actor import public
from ..core.database import DB
from ..services import stripe_pay

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.post("/webhook", dependencies=[public("webhook")])
async def webhook(
    request: Request,
    stripe_signature: str = Header("", alias="Stripe-Signature"),
    db: Session = DB,
):
    """**Eine Rückmeldung des Zahlungsdienstes.**

    Der **rohe** Rumpf wird geprüft, nicht das geparste JSON: die Signatur gilt für die
    Bytes, und wer sie über ein neu serialisiertes Objekt prüfte, prüfte etwas anderes.

    Die Antwort ist immer ``200`` mit einem Wort, was geschehen ist – auch bei einem
    Ereignis, das uns nicht betrifft. Ein Fehlercode auf eine Meldung, die wir schlicht
    nicht lesen wollen, brächte den Dienst nur dazu, sie endlos erneut zuzustellen.
    Ungültige Signaturen sind davon ausgenommen (400): das ist kein fremdes Ereignis,
    sondern ein fremder Absender.
    """
    raw = await request.body()
    return {"status": await run_in_threadpool(_book, db, raw, stripe_signature or None)}


def _book(db: Session, raw: bytes, signature: str | None) -> str:
    """Buchen und Folgen – synchron, im Threadpool (nie in der Event-Loop)."""
    status = stripe_pay.handle_webhook(db, raw=raw, signature=signature)
    return status
