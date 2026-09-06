"""**Der Zahlungsdienst — dünn, und die Oberfläche bleibt unsere.**

Zwei Funktionen: eine Zahlung **vorbereiten** und eine Rückmeldung **entgegennehmen**.
Mehr nicht – eine Erstattung löst man im Dashboard des Dienstes aus, und der Webhook bucht
sie wie jede andere Rückmeldung.

## Das ERP nennt Betrag und Währung. Der Dienst kassiert.

Im Vorgängersystem war es umgekehrt – dort stand wörtlich «Stripe ist Quelle der
Wahrheit», und daraus folgte fast die ganze Komplexität: ``stripe_*``-Snapshot-Spalten an
vier Tabellen, ein Webhook, der **Aufträge erzeugte**, ein ``CheckoutIntent`` mit
Reservierungen und ein Aufräumer für verlassene Warenkörbe. Hier gibt der Geldvorgang
Betrag und Währung vor, und der Webhook schreibt **eine Zeile Geld**
(``deal.record_payment``).

## ►►► Bezahlt wird BEI UNS, nicht dort ◄◄◄

Vorher war es eine **gehostete Kasse**: ein Link, und der Zahlende stand auf einer fremden
Seite mit fremdem Namen, fremder Schrift und fremder Adresszeile. Jetzt entsteht hier nur
eine **Zahlungsabsicht** (``PaymentIntent``), und ihr ``client_secret`` geht an unsere
eigene Karte im ERP – das Formular ist unseres, die Wörter sind unsere, der Knopf ist
unserer.

**Was trotzdem vom Dienst kommt, sind die Eingabefelder selbst** (ein Element in einem
iframe), und das ist ihr Sinn: so berührt **keine Kartennummer je unseren Server**. Und
die 3-D-Secure-Abfrage gehört der Bank, nicht uns – sie liesse sich gar nicht nachbauen.

## ►►► Was wir wissen, fragen wir nicht ◄◄◄

Name, E-Mail und Rechnungsadresse der Gegenpartei stehen im ERP. Sie reisen darum **mit
der Antwort** an unsere Karte, die sie dem Element als feste Werte übergibt – der Zahlende
tippt sie nicht ein zweites Mal ab.

**Nur was wir wirklich haben.** Fehlt die Adresse, sagt die Antwort das (``address:
None``) und das Element fragt sie – eine erfundene halbe Adresse wäre schlimmer als die
Frage. Dieselbe Regel wie überall im Haus: die Genauigkeit ist die der Quelle.

## Was es bewusst NICHT gibt

* **Keinen Kunden-Datensatz beim Dienst** (``Customer``, ``stripe_customer_id``). Wer ihn
  führte, hätte zwei Stammdaten für dieselbe Person – und die zweite ausserhalb des ERP.
  Die Angaben reisen je Zahlung mit; sie stehen ohnehin schon bei uns.
* **Keine Quittungs-Mail des Dienstes** (``receipt_email``). Sie trüge fremdes Briefpapier
  für einen Vorgang, der bei uns steht; der Nachweis ist die Zeile im Geldvorgang, und die
  sieht die Gegenpartei in ihrer eigenen Ansicht.
* **Keinen eigenen Erstattungs-Knopf.** Der Dienst bietet ihn an, und «erstattet wird auf
  dem Weg, auf dem gezahlt wurde» ist dort ohnehin die einzige Möglichkeit. Der Rückweg
  bleibt lückenlos: ``charge.refunded`` bucht eine **negative** Zahlung.
* **Keine Liste von Zahlungsarten bei uns.** Welche angeboten werden (Karte, TWINT, …),
  entscheidet das Konto beim Dienst – ``automatic_payment_methods``. Eine zweite Liste
  hier wäre die Stelle, an der beim nächsten Freischalten jemand nichts sieht.
* **Kein Stripe Tax.** Es berechnete eine Zahl, die wir nicht kennen – die Umkehrung des
  Grundsatzes oben. Die Steuer gehört an den Beleg, wenn die Rechnung kommt.
* **Kein Customer Portal, keine Subscriptions.** Wiederkehrende Aufträge werden eine
  **Schlaufe im Prozess** (PROCESS_CORE §13), kein Abo-Objekt beim Zahlungsdienst.
* **Keine ``stripe_*``-Spalten.** Die Id steht in ``deal_entries.reference`` – in derselben
  Spalte, in der bei einer Überweisung der Zahlungszweck steht. Ein Feld, zwei Wege.

## Ohne Schlüssel gibt es das alles nicht

``config.payment_service_ready()`` ist ``False``, der Knopf erscheint gar nicht erst
(``deal.can`` führt ``pay_online`` dann nicht), und der Webhook antwortet mit 404. Ein
503-Stub wäre die Behauptung, hier sei etwas abgeschaltet – es ist schlicht nicht
eingerichtet.
"""

from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..core.config import get_settings, payment_service_ready
from ..domain import currency as cur
from ..domain import deal as dm
from ..models import Deal, Order
from . import deal as deal_svc

#: Was wir vom Zahlungsdienst hören wollen — und sonst nichts. Jede weitere Meldung wird
#: **quittiert und ignoriert**: ein Ereignis, das niemand liest, ist kein Fehler, und ein
#: 400 darauf brächte den Dienst nur dazu, es endlos erneut zuzustellen.
#:
#: ``payment_intent.succeeded`` ist die Meldung der **eigenen** Kasse – die frühere
#: ``checkout.session.completed`` gehörte der gehosteten und kommt nie mehr. Sie trägt
#: ``amount_received`` und die ``pi_…``-Id, und genau die nennt später auch eine
#: Erstattung: darum findet ``deal.of_reference`` den Vorgang ohne eine zweite Spalte.
PAID = "payment_intent.succeeded"
REFUNDED = "charge.refunded"
EVENTS = (PAID, REFUNDED)


def _api():
    """Das SDK mit gesetztem Schlüssel – oder ein klarer Fehler, kein Absturz."""
    if not payment_service_ready():
        raise HTTPException(
            status_code=404,
            detail=("Es ist kein Zahlungsdienst eingerichtet "
                    "(STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY fehlen)."),
        )
    import stripe
    stripe.api_key = get_settings().stripe_secret_key
    return stripe


def _minor(amount: Decimal, code: str) -> int:
    """Der Betrag in der **kleinsten Einheit** – und die hängt an der Währung.

    ►►► ``× 100`` ist die Falle, die man nie bemerkt. ◄◄◄ Sie stimmt für CHF, EUR und
    USD, also für alles, was man beim Bauen ausprobiert – und ist bei **JPY** um den
    Faktor hundert falsch: 1000 Yen würden als 100 000 Yen belastet. Der Faktor kommt
    darum aus ``domain/currency`` (ISO 4217), nicht aus einer Konstante.

    Gerechnet auf dem ``Decimal``, nie über ``float``.
    """
    return int((amount.scaleb(cur.minor_units(code))).quantize(Decimal("1")))


def prepare(db: Session, *, deal: Deal, order: Order,
            charge_id: Optional[int] = None) -> dict[str, Any]:
    """►►► **Eine Zahlung über den offenen Betrag vorbereiten.** ◄◄◄

    Zurück kommt, was **unsere** Karte zum Zeichnen braucht: das ``client_secret`` der
    Zahlungsabsicht, der öffentliche Schlüssel, Betrag und Währung zum Anzeigen – und die
    Angaben, die wir ohnehin haben, damit niemand sie ein zweites Mal tippt.

    **Der offene Betrag, nicht die Zusage**: eine Anzahlung ist längst gebucht, und wer
    die volle Summe verlangte, kassierte zweimal.

    **Gebucht wird hier nichts.** Diese Funktion ändert am Geldvorgang keine Zeile; die
    Zahlung entsteht, wenn der Dienst sie meldet (``handle_webhook``). Der Browser des
    Zahlenden ist keine Quelle – wer ihn nach der Zahlung schliesst, darf keine Buchung
    verschlucken.

    **Ohne Zustand bei uns**: jeder Aufruf erzeugt eine neue Absicht. Eine gespeicherte Id
    wäre eine zweite Wahrheit über eine Sache, die dem Dienst gehört; eine unbenutzte
    Absicht kostet nichts und verfällt dort von selbst.
    """
    stripe = _api()
    # ►►► **Bezahlt wird EINE Rechnung, nicht ein Saldo** (Testnotiz #858). ◄◄◄
    #
    # Vorher war es der offene Betrag des **ganzen Vorgangs** – bei zwei offenen
    # Rechnungen also eine Zahlung, die auf zwei Belege zeigt, und genau die soll es nicht
    # geben.
    #
    # ►►► **Und WELCHE, sagt der Aufrufer** (Testnotiz #859). ◄◄◄ Hier stand
    # ``charges[0]`` – die älteste offene. Damit war die zweite Rechnung **unbezahlbar**,
    # obwohl ihr Knopf danebenstand: wer ihn drückte, bezahlte die erste. Eine
    # Reihenfolge, die niemand angeordnet hat, ist keine Regel, sondern ein Zufall der
    # Sortierung. Ohne Angabe bleibt sie die Vorgabe – bei genau einer offenen ist das die
    # einzig mögliche Antwort.
    charges = deal_svc.open_charges(db, deal)
    if not charges:
        raise HTTPException(
            status_code=409,
            detail=("An diesem Vorgang ist keine Rechnung offen – man kassiert nicht, "
                    "was niemand gefordert hat."),
        )
    charge = next((c for c in charges if c.id == charge_id), None) if charge_id \
        else charges[0]
    if charge is None:
        raise HTTPException(
            status_code=409,
            detail=("Auf diese Rechnung ist nichts mehr offen – sie ist beglichen oder "
                    "storniert."),
        )
    owed = deal_svc.open_of(db, deal, charge)
    code = cur.assert_code(deal.currency)
    number = charge.reference or str(charge.id)
    intent = stripe.PaymentIntent.create(
        amount=_minor(owed, code),
        currency=code.lower(),
        # **Welche Arten angeboten werden, entscheidet das Konto** – Karte, TWINT, was
        # dort freigeschaltet ist. Eine Liste hier wäre die zweite Stelle, an der beim
        # nächsten Freischalten jemand nichts sieht.
        automatic_payment_methods={"enabled": True},
        # ►►► **Der Faden zurück – und er nennt die RECHNUNG** (Testnotiz #858). ◄◄◄
        #
        # Metadaten sind der **maschinelle** Ort: hier sucht man beim Dienst, hierüber
        # findet der Webhook den Vorgang, und hier steht, welche Rechnung gemeint war –
        # ohne eine ``stripe_*``-Spalte bei uns.
        metadata={"deal_id": str(deal.id), "charge_id": str(charge.id),
                  "invoice": number, "order": str(order.object_id)},
        # ►►► **Die Beschreibung ist der MENSCHLICHE Ort der Rechnungsnummer.** ◄◄◄
        #
        # Sie lautete ``f"{order.name} {order.object_id}"`` – und weil der Name des
        # Auftrags seine Nummer bereits enthält, stand dort «Auftrag 100000884 100000884».
        # Zusammengesetzt wird darum **selbst**, aus den Angaben, die eine Aussage haben:
        # welche Rechnung, welcher Auftrag.
        #
        # *Nicht hier: die «Zahlungsbeschreibung in der Abrechnung»
        # (``statement_descriptor``). Das ist der Name, den die **Bank** dem Karteninhaber
        # zeigt – höchstens 22 Zeichen, und er gehört dem Konto, nicht der einzelnen
        # Zahlung; er lautet «Stripe», solange das Konto nicht aktiviert ist
        # (``docs/stripe-setup.md`` §2).*
        description=f"Rechnung {number} · Auftrag {order.object_id}",
    )
    return {
        "client_secret": str(intent.client_secret),
        "publishable_key": get_settings().stripe_publishable_key,
        "amount": cur.money(owed, code),
        "currency": code,
        # **Wofür bezahlt wird** – die Karte nennt den Beleg, nicht nur eine Zahl.
        "invoice": number,
        "billing": deal_svc.billing_of(db, deal),
    }


def refund(db: Session, *, deal: Deal, entry_id: Optional[int],
           amount: Optional[str] = None) -> None:
    """►►► **Geld zurück – auf dem Weg, auf dem es gekommen ist** (Testnotiz #860). ◄◄◄

    *«Wenn bezahlt wurde, dann wurde bezahlt … ich kann bzw. soll können einen Betrag
    zurückerstatten.»* Bar und per Überweisung ist die Erstattung eine ganz gewöhnliche
    **negative Zahlung** – die gibt es längst. Eine **Karte** kann nur der Dienst
    zurückgeben, der sie belastet hat; ein Mensch kann sie nicht überweisen.

    *Hier stand eine Zeit lang die Begründung, warum es diese Funktion NICHT gibt («das
    Dashboard kann es ja»). Sie war richtig, solange niemand danach fragte – ein Knopf
    ohne Aufrufer ist toter Code. Jetzt gibt es den Aufrufer, und das Argument dreht sich
    um: wer im Dashboard erstattet, muss das ERP verlassen und dort die Zahlung
    wiederfinden, die hier eine Zeile mit einer Nummer ist.*

    **Gebucht wird auch hier nichts.** Der Dienst meldet die Erstattung
    (``charge.refunded``), und der Webhook schreibt die negative Zeile – dieselbe Regel wie
    beim Einziehen, und aus demselben Grund: die Buchung folgt dem Geld, nicht dem Klick.

    **Der Betrag ist optional**: ohne Angabe die ganze Zahlung. Eine Teilerstattung ist
    dieselbe Handlung mit einer kleineren Zahl – kein zweites Verb.
    """
    stripe = _api()
    entry = deal_svc.card_payment(db, deal, entry_id)
    code = cur.assert_code(deal.currency)
    # **Aus einer Eingabe wird an EINER Stelle eine Zahl** (``dm.amount``): sie liest ein
    # Komma als Dezimaltrennzeichen und rundet auf die kleinste Einheit *dieser* Währung.
    # Ein blosses ``Decimal(...)`` daneben wäre eine zweite Lesart – und bei einem
    # unlesbaren Wert eine Ablehnung ohne Erklärung: an der Tür ein 500 statt eines Satzes.
    try:
        # ``allow_negative`` steht hier bewusst offen: die **Grenzen** nennt der Satz
        # darunter, und er nennt beide. Ohne ihn käme bei «−5» die Erklärung einer
        # *Zusage* zurück («die Richtung sagt, wohin das Geld fliesst») – richtig für ein
        # Angebot, an einer Erstattung eine Antwort auf eine andere Frage.
        named = dm.amount(amount, code, allow_negative=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    back = entry.amount if named is None else named
    if not Decimal("0") < back <= entry.amount:
        raise HTTPException(
            status_code=400,
            detail=(f"Eine Erstattung liegt über null und höchstens bei dem, was gezahlt "
                    f"wurde – {cur.money(entry.amount, code)} {code}."),
        )
    # **Die Referenz IST die Zahlungsabsicht** (``pi_…``): sie steht in derselben Spalte,
    # in der bei einer Überweisung der Zahlungszweck steht – ein Feld, zwei Wege, keine
    # ``stripe_*``-Spalte. Der Dienst findet über sie die Belastung selbst; wir müssen
    # die ``ch_…`` gar nicht kennen.
    stripe.Refund.create(payment_intent=str(entry.reference),
                         amount=_minor(back, code))


def handle_webhook(db: Session, *, raw: bytes, signature: Optional[str]) -> str:
    """**Eine Rückmeldung entgegennehmen — und genau eine Zeile schreiben.**

    Signaturgeprüft: ohne gültige Signatur ist es keine Meldung des Dienstes, sondern ein
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
    """``payment_intent.succeeded`` → eine Zahlung über den **erhaltenen** Betrag.

    ``amount_received`` und nicht ``amount``: gebucht wird, was wirklich angekommen ist –
    bei einer Teilautorisierung sind das zwei verschiedene Zahlen, und nur die zweite ist
    eine Zahlung.
    """
    row = _deal_of(db, (data.get("metadata") or {}).get("deal_id"))
    if row is None:
        return "unknown"
    amount = _amount_of(data.get("amount_received"), row.currency)
    if amount <= 0:
        return "ignored"
    deal_svc.record_payment(
        db, row=row, amount=amount,
        reference=str(data.get("id") or "") or None,
        note="Zahlungsdienst",
        # ►►► **Die Rechnung reist mit** (Testnotiz #858). ◄◄◄ Welche gemeint war, stand
        # beim Vorbereiten fest – sie hier erneut zu suchen hiesse raten, denn zwischen
        # der Zahlung und ihrer Meldung kann eine zweite Rechnung entstanden sein.
        charge_id=_still_open(db, row, (data.get("metadata") or {}).get("charge_id")),
        # **Wie bezahlt wurde, weiss der Dienst** – und nur er: von Hand erfasst wäre die
        # Karte eine Behauptung ohne Beleg (``dm.MANUAL_METHODS`` weist sie darum ab).
        method=dm.CARD,
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
        method=dm.CARD,
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


def _still_open(db: Session, row: Deal, value: Any) -> Optional[int]:
    """►►► **Die Rechnung aus den Metadaten – falls es sie noch gibt.** ◄◄◄

    Metadaten sind Strings, und eine ältere Absicht (vor dieser Regel) trägt den Schlüssel
    gar nicht. Eine fehlende Zuordnung ist ehrlicher als eine geratene.

    **Und sie kann inzwischen storniert sein.** Zwischen «Jetzt bezahlen» und der Meldung
    des Dienstes liegen Minuten, in denen jemand die Rechnung zurücknehmen kann. Dann ist
    die Zahlung **trotzdem passiert** – Geld ist auf dem Konto, und ein Ereignis der
    Aussenwelt macht man nicht ungeschehen (#842). Gebucht wird sie darum in jedem Fall,
    nur **ohne** Zuordnung: sie gehört keiner Rechnung, weil die, für die sie gedacht war,
    nicht mehr steht.

    Was daraus folgt, ist genau das Richtige und braucht keine eigene Regel: der offene
    Betrag wird **negativ** – wir schulden –, und die Erstattung steht als Handlung da
    (``refund_online``, Testnotiz #860). Eine Sperre im Webhook wäre die Alternative
    gewesen, und sie wäre falsch: Geld, das wir nicht buchen, fehlt in der Buchhaltung
    und niemandem fällt es auf.
    """
    try:
        wanted = None if value in (None, "") else int(value)
    except (TypeError, ValueError):
        return None
    if wanted is None:
        return None
    return wanted if any(c.id == wanted for c in deal_svc.open_charges(db, row)) else None
