"""**Die eine Tür, durch die der Zahlungsdienst hereinruft.**

Ein Endpunkt, keine Anmeldung, eine Signaturprüfung. Er schreibt **eine Zeile Geld**
(``voucher_money.record_payment``); was daraus folgt (Quittung, die Stücke einer Vorauszahlung
ziehen weiter), geschieht dort an derselben Stelle wie bei einer erfassten Zahlung.

Er steht **nicht** im Auftrags-Router, obwohl der Beleg dort lebt: dieser Router ist
öffentlich, und die Grenze zwischen «angemeldetes Personal» und «ein Fremder mit einer
Signatur» soll man an der Datei sehen.
"""

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services import stripe_pay, voucher_docs

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.post("/webhook")
async def webhook(
    request: Request,
    stripe_signature: str = Header("", alias="Stripe-Signature"),
    db: Session = Depends(get_db),
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
    status = stripe_pay.handle_webhook(db, raw=raw, signature=stripe_signature or None)
    # **Was die Zahlung ausgelöst hat (die Quittung), geht gleich hinaus** – festgeschrieben
    # hat ``handle_webhook`` schon.
    voucher_docs.send_pending(db)
    return {"status": status}
