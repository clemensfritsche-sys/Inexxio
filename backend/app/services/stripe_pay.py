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
(``voucher.record_payment``).

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
* **Keine ``stripe_*``-Spalten.** Die Id steht in ``voucher_entries.reference`` – in derselben
  Spalte, in der bei einer Überweisung der Zahlungszweck steht. Ein Feld, zwei Wege.

## Ohne Schlüssel gibt es das alles nicht

``config.payment_service_ready()`` ist ``False``, der Knopf erscheint gar nicht erst
(``voucher.can`` führt ``pay_online`` dann nicht), und der Webhook antwortet mit 404. Ein
503-Stub wäre die Behauptung, hier sei etwas abgeschaltet – es ist schlicht nicht
eingerichtet.
"""

import logging
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, Iterator, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..core.config import get_settings, payment_service_ready
from ..domain import currency as cur
from ..domain import voucher as dm
from ..models import Order, Voucher
from . import voucher as voucher_svc

# ►►► **Der Adapter kennt EIN Geld-Modul – als Schnittstelle, nicht als Namen.** ◄◄◄
#
# Ein Geld-Modul bietet sechs Funktionen an: ``balance_of`` · ``card_payment`` ·
# ``refundable_amount`` · ``billing_of`` · ``record_payment`` · ``of_reference``. Diese
# Datei bekommt es darum **übergeben** und fragt nie, welches es ist.
#
# *Es waren einmal sieben: ``open_charges`` und ``open_of`` beantworteten «welche Rechnung
# ist gemeint und wie viel steht auf ihr offen». Die Frage hat seit dem Umbau genau eine
# Antwort – der Beleg **ist** die Rechnung –, und eine Frage mit genau einer Antwort
# stellt man nicht.*
#
# Der **Faden zurück** ist ein Schlüssel in den Metadaten der Zahlungsabsicht; er nennt
# zugleich das Modul. Es waren eine Runde lang zwei (das alte ``deal`` daneben) – und
# genau deshalb kostete dessen Löschung hier **eine Zeile** (Testnotiz #960).
MONEY: tuple[tuple[str, Any, Any], ...] = (
    ("voucher_id", voucher_svc, Voucher),
)


def key_of(svc: Any) -> str:
    """Unter welchem Schlüssel dieses Modul in den Metadaten steht."""
    return next(k for k, mod, _ in MONEY if mod is svc)


log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# ►► EIN ROHFEHLER DES DIENSTES ERREICHT NIE DEN BILDSCHIRM (Testnotiz #1018)
# ═══════════════════════════════════════════════════════════════════════════════
#
# *«Charge has already been refunded»* stand als Meldung in der Oberfläche – englisch,
# technisch, und über eine Lage, die **wir** kennen. Ein Fehlertext des Zahlungsdienstes
# ist für einen Entwickler geschrieben, nicht für den, der am Beleg steht.
#
# ►►► **Zwei Wege, und sie trennen sich hier.** ◄◄◄ Der **technische** Text geht ins Log
# (dort sucht ihn, wer ihn braucht), der **verständliche** Satz an die Tür. Und er kommt
# aus einer Zuordnung statt aus einer Übersetzung: ein Dienst-Fehler hat einen ``code``,
# und der ist stabil – sein Wortlaut nicht.
#
# **Die Vorgabe nennt keine Ursache.** «Der Zahlungsdienst hat die Anfrage abgelehnt» sagt
# weniger als eine geratene Erklärung, und weniger ist hier richtig: ein Satz, der eine
# falsche Ursache behauptet, schickt jemanden in die falsche Richtung.
STRIPE_TROUBLE = ("Der Zahlungsdienst hat die Anfrage abgelehnt. Die technischen Angaben "
                  "stehen im Protokoll.")
STRIPE_OFFLINE = ("Der Zahlungsdienst ist gerade nicht erreichbar. Bitte in einem Moment "
                  "erneut versuchen.")
#: Was wir auf Deutsch sagen können – der Rest bleibt bewusst allgemein.
STRIPE_REASONS: dict[str, str] = {
    "charge_already_refunded": ("Diese Zahlung ist bereits vollständig zurückerstattet."),
    "charge_already_captured": ("Diese Zahlung ist bereits abgeschlossen und lässt sich "
                                "nicht mehr ändern."),
    "charge_disputed": ("Zu dieser Zahlung läuft eine Rückbuchung des Karteninhabers – "
                        "solange lässt sie sich nicht erstatten."),
    "amount_too_large": "Der Betrag ist grösser als das, was gezahlt wurde.",
    "amount_too_small": "Der Betrag ist kleiner als der kleinste, den der Dienst annimmt.",
    "balance_insufficient": ("Das Guthaben beim Zahlungsdienst reicht für diese Erstattung "
                            "nicht aus."),
    "resource_missing": ("Der Zahlungsdienst kennt diesen Vorgang nicht (mehr)."),
    "card_declined": "Die Karte wurde abgelehnt.",
    "expired_card": "Die Karte ist abgelaufen.",
    "rate_limit": STRIPE_OFFLINE,
}


def _message(exc: Exception) -> str:
    """**Ein Satz, den ein Mensch versteht** – nie der Wortlaut des Dienstes."""
    code = str(getattr(exc, "code", "") or "")
    if code in STRIPE_REASONS:
        return STRIPE_REASONS[code]
    if type(exc).__name__ in ("APIConnectionError", "RateLimitError"):
        return STRIPE_OFFLINE
    return STRIPE_TROUBLE


@contextmanager
def _speaking(what: str) -> Iterator[None]:
    """►►► **Die eine Naht zum Dienst** – und alles, was durch sie kommt, spricht Deutsch.

    Sie steht um **jeden** Aufruf, der Geld bewegt (Vorbereiten, Erstatten): eine Stelle,
    die sie vergisst, ist genau die, an der wieder ein englischer Rohtext im Browser
    steht. Eine ``HTTPException`` reist unangetastet weiter – sie ist bereits unser Satz.
    """
    try:
        yield
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 – die Tür gibt nichts Technisches weiter
        log.warning("Zahlungsdienst: %s fehlgeschlagen – %s: %s",
                    what, type(exc).__name__, exc)
        raise HTTPException(status_code=409, detail=_message(exc))

#: Was wir vom Zahlungsdienst hören wollen — und sonst nichts. Jede weitere Meldung wird
#: **quittiert und ignoriert**: ein Ereignis, das niemand liest, ist kein Fehler, und ein
#: 400 darauf brächte den Dienst nur dazu, es endlos erneut zuzustellen.
#:
#: ``payment_intent.succeeded`` ist die Meldung der **eigenen** Kasse – die frühere
#: ``checkout.session.completed`` gehörte der gehosteten und kommt nie mehr. Sie trägt
#: ``amount_received`` und die ``pi_…``-Id, und genau die nennt später auch eine
#: Erstattung: darum findet ``voucher.of_reference`` den Vorgang ohne eine zweite Spalte.
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


def prepare(db: Session, *, svc: Any, row: Any, order: Order) -> dict[str, Any]:
    """►►► **Eine Zahlung über den offenen Betrag vorbereiten.** ◄◄◄

    Zurück kommt, was **unsere** Karte zum Zeichnen braucht: das ``client_secret`` der
    Zahlungsabsicht, der öffentliche Schlüssel, Betrag und Währung zum Anzeigen – und die
    Angaben, die wir ohnehin haben, damit niemand sie ein zweites Mal tippt.

    **Der offene Betrag, nicht die Zusage**: eine Anzahlung ist längst gebucht, und wer
    die volle Summe verlangte, kassierte zweimal.

    ►►► **Welche Rechnung gemeint ist, fragt niemand mehr.** ◄◄◄ Hier stand eine
    Auswahl über die offenen Forderungen des Vorgangs samt einem ``charge_id`` am
    Aufrufer – aus der Zeit, als ein Beleg mehrere Rechnungen tragen konnte. Seit er
    **die** Rechnung ist, ist der offene Betrag des Belegs der offene Betrag der
    Rechnung, und der frühere Fehler («kassiert wurde immer die älteste, egal an welchem
    Knopf man klickte», #859) kann gar nicht mehr entstehen.

    **Gebucht wird hier nichts.** Diese Funktion ändert am Beleg keine Zeile; die Zahlung
    entsteht, wenn der Dienst sie meldet (``handle_webhook``). Der Browser des Zahlenden
    ist keine Quelle – wer ihn nach der Zahlung schliesst, darf keine Buchung verschlucken.

    **Ohne Zustand bei uns**: jeder Aufruf erzeugt eine neue Absicht. Eine gespeicherte Id
    wäre eine zweite Wahrheit über eine Sache, die dem Dienst gehört; eine unbenutzte
    Absicht kostet nichts und verfällt dort von selbst.
    """
    stripe = _api()
    owed = svc.balance_of(db, row).open
    if owed <= 0:
        raise HTTPException(
            status_code=409,
            detail=("An diesem Beleg ist nichts offen – man kassiert nicht, was niemand "
                    "gefordert hat."),
        )
    code = cur.assert_code(row.currency)
    number = row.number or str(row.id)
    with _speaking("Zahlung vorbereiten"):
        intent = stripe.PaymentIntent.create(
            amount=_minor(owed, code),
            currency=code.lower(),
            # **Welche Arten angeboten werden, entscheidet das Konto** – Karte, TWINT, was
            # dort freigeschaltet ist. Eine Liste hier wäre die zweite Stelle, an der beim
            # nächsten Freischalten jemand nichts sieht.
            automatic_payment_methods={"enabled": True},
            # ►►► **Der Faden zurück.** ◄◄◄ Metadaten sind der **maschinelle** Ort: hier
            # sucht man beim Dienst, hierüber findet der Webhook den Beleg – ohne eine
            # ``stripe_*``-Spalte bei uns. Die Rechnungsnummer steht daneben, weil sie im
            # Dashboard lesbar sein soll; **gefunden** wird über den Beleg.
            metadata={key_of(svc): str(row.id),
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
        "billing": svc.billing_of(db, row),
    }


def refund(db: Session, *, svc: Any, row: Any, entry_id: Optional[int],
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

    **Der Betrag ist optional**: ohne Angabe der ganze **Rest**. Eine Teilerstattung ist
    dieselbe Handlung mit einer kleineren Zahl – kein zweites Verb.

    ►►► **Zweimal geklickt ist EINE Erstattung** (Testnotiz #1018). ◄◄◄ Der Knopf liess
    sich mehrfach drücken, und der zweite Aufruf brachte den Rohfehler des Dienstes
    («Charge has already been refunded») auf den Bildschirm. Drei Ebenen, und alle drei
    sind nötig, weil jede eine andere Lücke schliesst:

    * **Der Rest** (``svc.refundable_amount``) – die fachliche Wahrheit, sobald die
      Erstattung gebucht ist. Sie schliesst den Knopf.
    * **Der Idempotenz-Schlüssel** – das Fenster davor: zwischen Klick und Buchung liegt
      die Meldung des Webhooks, und in dieser Zeit sieht auch der Server noch nichts.
      Zwei Klicks in diesem Fenster tragen **denselben** Schlüssel, also entsteht beim
      Dienst genau eine Erstattung.
    * **Die deutsche Meldung** (``_speaking``) – das Netz darunter: was dem Dienst sonst
      noch missfällt, sagt er auf Englisch, und das gehört ins Log, nicht ins Bild.

    **Der Schlüssel nennt den Stand VOR dem Aufruf** (``refunded``): damit ist ein
    Doppelklick dasselbe Vorhaben (gleicher Stand, gleicher Betrag) – und zwei
    *nacheinander* gewollte Teilerstattungen über denselben Betrag sind es nicht, weil der
    Stand dazwischen gewachsen ist. Ein Schlüssel ohne ihn schluckte die zweite still.
    """
    stripe = _api()
    entry = svc.card_payment(db, row, entry_id)
    code = cur.assert_code(row.currency)
    # **Der Rest, nicht der Betrag der Zahlung** – eine teilweise erstattete Karte darf
    # nur noch um den Rest zurückgehen.
    rest = svc.refundable_amount(db, row, entry)
    done = entry.amount - rest
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
    back = rest if named is None else named
    if not Decimal("0") < back <= rest:
        raise HTTPException(
            status_code=409,
            detail=(f"Eine Erstattung liegt über null und höchstens bei dem, was von "
                    f"dieser Zahlung noch offen ist – {cur.money(rest, code)} {code}."
                    + (f" ({cur.money(done, code)} {code} sind bereits zurückgegangen.)"
                       if done > 0 else "")),
        )
    # **Die Referenz IST die Zahlungsabsicht** (``pi_…``): sie steht in derselben Spalte,
    # in der bei einer Überweisung der Zahlungszweck steht – ein Feld, zwei Wege, keine
    # ``stripe_*``-Spalte. Der Dienst findet über sie die Belastung selbst; wir müssen
    # die ``ch_…`` gar nicht kennen.
    with _speaking("Erstattung"):
        stripe.Refund.create(
            payment_intent=str(entry.reference),
            amount=_minor(back, code),
            idempotency_key=(f"refund:{key_of(svc)}:{row.id}:{entry.id}"
                             f":{_minor(done, code)}:{_minor(back, code)}"),
        )


def handle_webhook(db: Session, *, raw: bytes, signature: Optional[str]) -> str:
    """**Eine Rückmeldung entgegennehmen — und genau eine Zeile schreiben.**

    Signaturgeprüft: ohne gültige Signatur ist es keine Meldung des Dienstes, sondern ein
    Fremder, der Zahlungen erfinden möchte.

    **Idempotent über die Referenz** (``voucher.record_payment``): der Dienst stellt seine
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
    svc, row = _row_of(db, data.get("metadata") or {})
    if row is None:
        return "unknown"
    amount = _amount_of(data.get("amount_received"), row.currency)
    if amount <= 0:
        return "ignored"
    svc.record_payment(
        db, row=row, amount=amount,
        reference=str(data.get("id") or "") or None,
        # ►►► **Kein Vermerk «Zahlungsdienst»** (Testnotiz #999). ◄◄◄ Er stand als zweite
        # Angabe neben ``method=card`` – und der Zeile ist damit **zweimal** angesehen,
        # dass sie über den Dienst kam: einmal als Zahlungsart («Karte», die Angabe, nach
        # der man sie wiedererkennt) und einmal als Wort daneben. Ein Vermerk ist für das
        # da, was **sonst nirgends** steht.
        note=None,
        # ►►► **Eine Zuordnung braucht es nicht mehr.** ◄◄◄ Hier stand ``charge_id``:
        # welche Rechnung diese Zahlung meint, samt einer Prüfung, ob es sie noch gibt
        # (``_still_open``). Seit der Beleg **die** Rechnung ist, gehört die Zahlung
        # dorthin, wo sie hängt – und zwar auch dann, wenn die Rechnung inzwischen
        # zurückgenommen wurde: das Geld ist geflossen, ein Ereignis der Aussenwelt macht
        # man nicht ungeschehen (#842). Der offene Betrag wird dann **negativ** – wir
        # schulden –, und die Erstattung steht als Handlung da.
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
    # **Gesucht wird über die Referenz, nicht über eine Metadate** – eine Erstattung trägt
    # die Zahlungsabsicht, und die steht an genau einer Zeile im Haus. Gefragt werden
    # beide Module; wo es die Zeile gibt, gehört sie dem, der sie geschrieben hat.
    svc, row = next(((mod, found) for _, mod, _model in MONEY
                     if (found := mod.of_reference(db, intent)) is not None),
                    (None, None))
    if row is None:
        return "unknown"
    booked = 0
    for ref, amount in _refunds(data, intent, row.currency):
        svc.record_payment(
            db, row=row, amount=-amount,
            # **Eine eigene Referenz** – sonst fiele die Erstattung mit der Zahlung
            # zusammen, und die Idempotenz würfe sie weg.
            reference=ref,
            note="Erstattung",
            method=dm.CARD,
        )
        booked += 1
    if not booked:
        return "ignored"
    db.commit()
    return "refunded"


def _refunds(data: dict[str, Any], intent: str, code: Any) -> list[tuple[str, Decimal]]:
    """►►► **Je Erstattung eine Zeile — nicht die kumulierte Summe.** ◄◄◄

    ``amount_refunded`` an der Belastung ist **kumulativ**: nach zwei Teilerstattungen über
    je 30 steht dort 60. Gebucht wurde daraus eine einzige Zeile mit der Referenz
    ``pi_…:refund`` – und die zweite Meldung fand sie wieder (Idempotenz über die Referenz)
    und schrieb **nichts**. Der Betrag im Haus stand damit auf 30, während 60 zurückgingen;
    unauffällig, solange nur vollständig erstattet wird, und genau die Zahl, auf der
    ``refundable_amount`` beruht.

    Gelesen wird darum die **Liste** der Erstattungen; jede trägt ihre eigene Id, also
    ihre eigene Referenz, und die Idempotenz greift je Erstattung statt je Belastung.

    **Die älteste behält die alte Referenz** (``pi_…:refund``): eine Zeile aus der Zeit
    davor bedeutet genau sie – sonst entstünde bei der nächsten Zustellung eine zweite,
    und die Erstattung wäre doppelt gebucht. ``refunds.data`` kommt neueste zuerst.
    """
    rows = ((data.get("refunds") or {}).get("data")) or []
    if not rows:
        # **Eine Meldung ohne Liste** – dann ist die kumulierte Summe alles, was wir haben.
        amount = _amount_of(data.get("amount_refunded"), code)
        return [(f"{intent}:refund", amount)] if amount > 0 else []
    out: list[tuple[str, Decimal]] = []
    for i, r in enumerate(reversed(rows)):
        amount = _amount_of(r.get("amount"), code)
        if amount <= 0:
            continue
        out.append((f"{intent}:refund" if i == 0 else f"{intent}:refund:{r.get('id')}",
                    amount))
    return out


def _amount_of(value: Any, code: Any) -> Decimal:
    """Aus der kleinsten Einheit zurück – **in der Genauigkeit dieser Währung**.

    Die Gegenrichtung von ``_minor``, und dieselbe Falle: ein festes ``/ 100`` machte aus
    1000 Yen zehn.
    """
    return Decimal(str(value or 0)).scaleb(-cur.minor_units(code))


def _row_of(db: Session, meta: dict[str, Any]) -> tuple[Any, Any]:
    """►►► **Welches Geld-Modul, und welche Zeile?** ◄◄◄

    Der Schlüssel in den Metadaten nennt beides – ``voucher_id``. Damit
    braucht diese Datei keine Fallunterscheidung nach Modultyp und keine zweite Tabelle:
    was sie kennt, ist die **Schnittstelle**, nicht der Name.
    """
    for key, mod, model in MONEY:
        try:
            value = meta.get(key)
            if value in (None, ""):
                continue
            found = db.query(model).filter(model.id == int(value)).first()
        except (TypeError, ValueError):
            continue
        if found is not None:
            return mod, found
    return None, None
