"""**Die eine Tür, durch die der Zahlungsdienst hereinruft.**

Ein Endpunkt, keine Anmeldung, eine Signaturprüfung. Er schreibt **eine Zeile Geld**
(``services/payments.record``) und sonst nichts – er erzeugt keinen Auftrag, gibt keinen
frei und ändert keine Stufe. Genau daran hing im Vorgängersystem die halbe Komplexität:
dort war der Webhook der Ort, an dem Bestellungen entstanden.

Er steht **nicht** im Auftrags-Router, obwohl der Beleg dort lebt: dieser Router ist
öffentlich, und die Grenze zwischen «angemeldetes Personal» und «ein Fremder mit einer
Signatur» soll man an der Datei sehen.
"""

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services import stripe_pay

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
    return {"status": stripe_pay.handle_webhook(
        db, raw=raw, signature=stripe_signature or None)}
