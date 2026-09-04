"""**Stripe — dünn, und in die richtige Richtung.**

Zwei Funktionen: eine Zahlungsaufforderung erzeugen und eine Rückmeldung entgegennehmen.
Mehr nicht – eine **Erstattung** löst man im Dashboard des Dienstes aus, und der Webhook
bucht sie wie jede andere Rückmeldung.

## Das ERP nennt Betrag und Währung. Stripe kassiert.

Im Vorgängersystem war es umgekehrt – dort stand wörtlich «Stripe ist Quelle der
Wahrheit», und daraus folgte fast die ganze Komplexität: ``stripe_*``-Snapshot-Spalten an
vier Tabellen, ein Webhook, der **Aufträge erzeugte**, ein ``CheckoutIntent`` mit
Reservierungen und ein Aufräumer für verlassene Warenkörbe. Hier gibt der Beleg Betrag und
Währung vor, und der Webhook schreibt **eine Zeile Geld** (``deal.record_payment``).

**Adaptive Pricing bleibt darum aus** – das ist die eine Lehre, die unverändert gilt: mit
ihm rechnete Stripe unseren Betrag mit *seinem* Kurs erneut um, und der Kunde sähe 11.80
und würde mit 11.82 belastet. Wir setzen die Präsentationswährung selbst, also gibt es nur
einen Kurs.

## Was es bewusst NICHT gibt

* **Kein eigener Erstattungs-Knopf.** Der Dienst bietet ihn selbst an, und «erstattet wird
  auf dem Weg, auf dem gezahlt wurde» ist dort ohnehin die einzige Möglichkeit. Der
  Rückweg bleibt lückenlos: ``charge.refunded`` bucht eine **negative** Zahlung.
* **Kein Provider-Rahmen mit zwei Implementierungen.** Der alte ``manual``-Provider war die
  Simulation eines Zahlungsdienstes – mit eigener Bezahlseite und einem
  ``/payments/simulate``-Endpunkt. Ohne Stripe zahlt man per **Überweisung**, und die
  trägt ein Mensch ein; das ist kein Fallback, sondern der B2B-Normalfall.
* **Kein Stripe Tax.** Es berechnete eine Zahl, die wir nicht kennen – genau die Umkehrung
  oben. Die Steuer gehört an den Beleg, wenn die Rechnung kommt.
* **Kein Customer Portal, keine Subscriptions.** Wiederkehrende Aufträge werden eine
  **Schlaufe im Prozess** (PROCESS_CORE §13), kein Abo-Objekt beim Zahlungsdienst.
* **Keine ``stripe_*``-Spalten.** Die Id steht in ``deal_entries.reference`` – in derselben
  Spalte, in der bei einer Überweisung der Zahlungszweck steht. Ein Feld, zwei Wege.

## Ohne Schlüssel gibt es das alles nicht

``available()`` ist ``False``, der Knopf erscheint gar nicht erst, und der Webhook
antwortet mit 404. Ein 503-Stub wäre die Behauptung, hier sei etwas abgeschaltet – es ist
schlicht nicht eingerichtet.
"""

from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..domain import currency as cur
from ..models import Deal
from . import deal as deal_svc, sites

#: Was wir vom Zahlungsdienst hören wollen — und sonst nichts. Jede weitere Meldung wird
#: **quittiert und ignoriert**: ein Ereignis, das niemand liest, ist kein Fehler, und ein
#: 400 darauf brächte Stripe nur dazu, es endlos erneut zuzustellen.
PAID = "checkout.session.completed"
REFUNDED = "charge.refunded"
EVENTS = (PAID, REFUNDED)


def available() -> bool:
    """**Ist ein Zahlungsdienst eingerichtet?** Genau dann, wenn ein Schlüssel da ist.

    Eine abgeleitete Antwort, keine Einstellung daneben: ein Schalter «Stripe aktiv», der
    ohne Schlüssel auf «an» stünde, wäre eine Behauptung.
    """
    return bool(get_settings().stripe_secret_key)


def _api():
    """Das SDK mit gesetztem Schlüssel – oder ein klarer Fehler, kein Absturz."""
    key = get_settings().stripe_secret_key
    if not key:
        raise HTTPException(
            status_code=404,
            detail="Es ist kein Zahlungsdienst eingerichtet (STRIPE_SECRET_KEY fehlt).",
        )
    import stripe
    stripe.api_key = key
    return stripe


def _minor(amount: Decimal, code: str) -> int:
    """Stripe rechnet in der **kleinsten Einheit** – und die hängt an der Währung.

    ►►► ``× 100`` ist die Falle, die man nie bemerkt. ◄◄◄ Sie stimmt für CHF, EUR und
    USD, also für alles, was man beim Bauen ausprobiert – und ist bei **JPY** um den
    Faktor hundert falsch: 1000 Yen würden als 100 000 Yen belastet. Der Faktor kommt
    darum aus ``domain/currency`` (ISO 4217), nicht aus einer Konstante.

    Gerechnet auf dem ``Decimal``, nie über ``float``.
    """
    return int((amount.scaleb(cur.minor_units(code))).quantize(Decimal("1")))


def checkout_url(db: Session, *, deal: Deal, label: str) -> str:
    """►►► **Eine Zahlungsaufforderung über den offenen Betrag.** ◄◄◄

    Betrag **und** Währung kommen aus dem Vorgang; Stripe rechnet nichts um. Bezahlt
    wird genau das, was offen ist – nicht die Zusage: eine Anzahlung ist längst gebucht,
    und wer den vollen Betrag verlangte, kassierte zweimal.

    Die Rückmeldung kommt über den **Webhook**, nicht über die Rückkehr-URL: ein Browser,
    der nach der Zahlung geschlossen wird, darf keine Buchung verschlucken.
    """
    stripe = _api()
    open_amount = deal_svc.open_amount(db, deal)
    if open_amount <= 0:
        raise HTTPException(
            status_code=409,
            detail="An diesem Vorgang ist nichts offen – es gibt nichts zu bezahlen.",
        )
    code = cur.assert_code(deal.currency)
    base = sites.website_url()
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "quantity": 1,
            "price_data": {
                "currency": code.lower(),
                "unit_amount": _minor(open_amount, code),
                "product_data": {"name": label},
            },
        }],
        # **Wir setzen die Präsentationswährung.** Sonst rechnete Stripe unseren Betrag
        # mit seinem eigenen Kurs erneut um – angezeigt 11.80, belastet 11.82.
        adaptive_pricing={"enabled": False},
        # Der Faden zurück zum Vorgang. Er steht in den Metadaten und nicht in einer
        # eigenen Spalte: die Sitzung ist ein Vorgang bei Stripe, kein Datensatz bei uns.
        metadata={"deal_id": str(deal.id)},
        success_url=f"{base}/erp",
        cancel_url=f"{base}/erp",
    )
    return str(session.url)


# ►►► **Eine Erstattung wird im Dashboard des Dienstes ausgelöst, nicht hier.** ◄◄◄
#
# Hier stand eine ``refund``-Funktion – **ohne einen einzigen Aufrufer**. Sie hätte einen
# eigenen Knopf, eine Betragseingabe und eine Fehlerbehandlung gebraucht, um etwas zu tun,
# das der Dienst selbst schon anbietet; und «erstattet wird auf dem Weg, auf dem gezahlt
# wurde» ist dort ohnehin die einzige Möglichkeit.
#
# **Der Rückweg ist trotzdem lückenlos**: wer die Erstattung auslöst, ist dem Webhook
# gleich – ``charge.refunded`` bucht sie als negative Zahlung, mit eigener Referenz. Ein
# zweiter Auslöser wäre ein zweiter Weg zu derselben Buchung.


def handle_webhook(db: Session, *, raw: bytes, signature: Optional[str]) -> str:
    """**Eine Rückmeldung entgegennehmen — und genau eine Zeile schreiben.**

    Signaturgeprüft: ohne gültige Signatur ist es keine Meldung von Stripe, sondern ein
    Fremder, der Zahlungen erfinden möchte.

    **Idempotent über die Referenz** (``deal.record_payment``): der Dienst stellt seine
    Meldungen mehrfach zu – das ist zugesichert, nicht die Ausnahme. Ein zweiter Durchlauf
    bucht darum nichts, er findet die Zeile.
    """
    stripe = _api()
    secret = get_settings().stripe_webhook_secret
    if not secret:
        raise HTTPException(
            status_code=404,
            detail="Es ist kein Webhook-Geheimnis hinterlegt (STRIPE_WEBHOOK_SECRET).",
        )
    try:
        event = stripe.Webhook.construct_event(raw, signature or "", secret)
    except Exception:
        # Bewusst ohne Details: was genau nicht stimmte, geht den Absender nichts an.
        raise HTTPException(status_code=400, detail="Ungültige Signatur.")

    kind = str(event.get("type") or "")
    if kind not in EVENTS:
        return "ignored"
    data = (event.get("data") or {}).get("object") or {}
    handler = {PAID: _note_payment, REFUNDED: _note_refund}[kind]
    return handler(db, data)


def _note_payment(db: Session, data: dict[str, Any]) -> str:
    """``checkout.session.completed`` → eine Zahlung über den bezahlten Betrag."""
    row = _deal_of(db, (data.get("metadata") or {}).get("deal_id"))
    if row is None:
        return "unknown"
    amount = _amount_of(data.get("amount_total"), row.currency)
    deal_svc.record_payment(
        db, row=row, amount=amount,
        reference=str(data.get("payment_intent") or data.get("id") or "") or None,
        note="Zahlungsdienst",
    )
    db.commit()
    return "paid"


def _note_refund(db: Session, data: dict[str, Any]) -> str:
    """``charge.refunded`` → eine **negative** Zahlung über den erstatteten Betrag.

    Keine Gutschrift: es ist Geld geflossen, nur rückwärts. Ob die **Forderung** gemindert
    wird, ist eine andere Frage und eine menschliche Entscheidung (eine **negative
    Rechnung**) – genau darum sind Forderung und Geld zwei Achsen.
    """
    intent = str(data.get("payment_intent") or "")
    row = deal_svc.of_reference(db, intent)
    if row is None:
        return "unknown"
    amount = _amount_of(data.get("amount_refunded"), row.currency)
    if amount <= 0:
        return "ignored"
    deal_svc.record_payment(
        db, row=row, amount=-amount,
        # **Eine eigene Referenz** – sonst fiele die Erstattung mit der Zahlung zusammen,
        # und die Idempotenz würfe sie weg.
        reference=f"{intent}:refund",
        note="Erstattung",
    )
    db.commit()
    return "refunded"


def _amount_of(value: Any, code: Any) -> Decimal:
    """Aus der kleinsten Einheit zurück – **in der Genauigkeit dieser Währung**.

    Die Gegenrichtung von ``_minor``, und dieselbe Falle: ein festes ``/ 100`` machte aus
    1000 Yen zehn.
    """
    return Decimal(str(value or 0)).scaleb(-cur.minor_units(code))


def _deal_of(db: Session, value: Any) -> Optional[Deal]:
    try:
        return db.query(Deal).filter(Deal.id == int(value)).first()
    except (TypeError, ValueError):
        return None
