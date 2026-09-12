"""**Der Geldvorgang — Anlage, Handlungen, Rechnung.**

Der Dienst hinter dem Prozessschrittmodul «Zahlung». Er steht **vollständig für sich**:
kein Import aus ``services/purchase``, ``services/invoices``, ``services/payments`` oder
``domain/procurement``. Wer die Module «Beschaffen» und «Verkauf» eines Tages ersatzlos
löscht, fasst hier keine Zeile an.

## Ein Vorgang hat ZWEI Parteien

Ein Geldvorgang ist kein Formular, das eine Seite ausfüllt: jemand fragt, der andere
nennt einen Preis, einer sagt zu. Darum der **Angebotsspiegel** (``deals.quotes``, je
Gegenpartei eine Zeile) und darum bekommt die Gegenpartei einen eigenen, sehr engen
Zugang – sie sieht **ihre** Zeile und sonst nichts (``mine`` → ``orders._to_response``).

**Wer ohnehin ins ERP darf, braucht diese enge Sicht nicht**: für Personal gibt ``mine``
``None`` zurück – «an allem beteiligt». Ein Mitarbeiter, der zufällig Gegenpartei ist,
arbeitet weiter in der vollen Ansicht.

## Eine Handlung ist ein Befehl, kein Feld-Update

Neun Verben, ein Endpunkt (``POST …/steps/{id}/deal``). Was an einer Stufe erlaubt ist,
steht in **einer** Tabelle (``ACTIONS`` × ``Direction.party_actions``) – und dieselbe ist
**Auskunft und Tor**: die Oberfläche rendert einen Knopf genau dann, wenn sein Verb in
``can`` steht, und ``apply`` weist ab, was nicht darin steht.

## Was hier NICHT passiert

Kein Statuswechsel an einer Einzelinstanz, kein Ortswechsel, keine Objektnummer, kein
Auftrag. Dieses Modul hält die Stücke auf und lässt sie weiterlaufen; alles Physische tun
seine Nachbarn. Genau darum muss keine andere Regel im System von ihm wissen.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import payment_service_ready
from ..domain import currency as cur
from ..domain import deal as dm
from ..domain import incoterms as inc
from ..domain import modules
from ..models import (
    Article, Deal, DealEntry, Instance, InstanceUnit, Order, OrderUnit, ProcessEvent,
    ProcessStep, UserProfile,
)
from ..models.process_event import KIND_START, KIND_STEP
from . import address, lookup, people, qrbill, sites

#: **Wer ohnehin alles sieht.** Für sie gibt es keine verengte Sicht – sie arbeiten im
#: ERP, und dort steht der ganze Auftrag.
STAFF_ROLES: tuple[str, ...] = ("admin", "employee")

#: ►►► **Was an welcher Stufe erlaubt ist — Auskunft UND Tor.** ◄◄◄
#:
#: ``currency`` die Währung des Vorgangs setzen – **nur vor der Zusage**
#: ``ask``     die zugelassenen Gegenparteien anfragen bzw. ihnen anbieten
#: ``quote``   einen Preis an **einer** Angebotszeile eintragen
#: ``decline`` eine Angebotszeile absagen
#: ``agree``   den Zuschlag geben – ab hier ist eine zweite Partei gebunden
#: ``revoke``  stornieren. **Nur ab der Schwelle**: davor gibt es nichts zurückzunehmen.
#: ``charge``  eine **Forderung** buchen (negativ = Gutschrift)
#: ``pay``     eine **Zahlung** buchen (negativ = Erstattung)
#:
#: **Geld darf in jeder Stufe ab der Zusage fliessen** – auch nach dem Storno: eine
#: Anzahlung muss erstattet werden können, und eine Rechnung darf vor der Erfüllung
#: stehen und danach. Wer das an die Stufe bände, hätte für jedes Szenario ein ``if``.
#:
#: **Die Währung steht in genau EINER Stufe** – und das ist keine zusätzliche Regel,
#: sondern dieselbe Tabelle: ab der Zusage liegt draussen eine Zusage über *diese* Summe
#: in *dieser* Währung, und sie nachträglich umzuschreiben hiesse, die Zahl stehen zu
#: lassen und ihre Bedeutung zu ändern. Weil ``can`` das Tor ist, fehlt der Auswahl-Knopf
#: danach von selbst und ``apply`` weist ihn ab – ohne ein zweites ``if``.
#:
#: ``pay_online`` steht **neben** ``pay`` und in denselben Stufen: es ist dieselbe Achse
#: (Geld), nur die andere Hand. ``pay`` schreibt auf, was schon geschehen ist (eine
#: Überweisung liegt auf dem Konto); ``pay_online`` **löst es aus** und bucht selbst gar
#: nichts – gebucht wird, wenn der Dienst es meldet. Wer beide zu einem Verb machte,
#: bekäme einen Knopf, dessen Wirkung von einer Einstellung abhängt.
ACTIONS: dict[str, tuple[str, ...]] = {
    dm.OFFER: ("currency", "issuer", "incoterm", "ask", "quote", "decline", "agree"),
    dm.AGREED: ("revoke", "charge", "pay", "pay_online", "refund_online"),
    dm.DONE: ("charge", "pay", "pay_online", "refund_online"),
    dm.CANCELLED: ("charge", "pay", "pay_online", "refund_online"),
}

#: ►►► **Was die GEGENPARTEI darf — es folgt aus der RICHTUNG.** ◄◄◄
#:
#: Es stand als Konstante da («sie nennt ihren Preis oder sagt ab») und war damit die
#: Ausgabe-Sicht für beide Richtungen. **Wer den Preis nennt, offeriert; wer ihn empfängt,
#: nimmt an oder lehnt ab** – bei einer Einnahme darf der Kunde unseren Preis also gar
#: nicht überschreiben (Testnotiz #837). Die Liste wohnt darum in ``Direction``
#: (``party_actions``), abgeleitet aus ``quoted_by``.
#:
#: Weiterhin als **Schnittmenge** mit der Stufe und nicht als eigene Tabelle: zwei
#: Tabellen wären zwei Massstäbe, und der zweite bekäme das nächste Verb nicht mit.

#: ►►► **Eine Geld-Zeile STORNIEREN — mit einer Gegenbuchung.** ◄◄◄
#:
#: Es steht getrennt von ``ACTIONS``, weil es keine Handlung am *Vorgang* ist, sondern an
#: einer seiner Zeilen – und weil es in jeder Stufe geht: ein Irrtum kennt keinen Zeitpunkt.
#:
#: **Gelöscht wird nichts** (Testnotizen #823/#824). Eine Rechnungsnummer ist vergeben, ein
#: Beleg ist draussen – wer die Zeile verschwinden lässt, behauptet, sie sei nie passiert.
#: Storniert wird darum wie in jeder Buchhaltung: durch eine **Gegenzeile** mit dem
#: negativen Betrag. Beide bleiben stehen, die Summe stimmt von selbst, und der Nachweis
#: ist lückenlos.
#:
#: Das ist **keine neue Mechanik**: eine Gutschrift ist längst eine negative Rechnung und
#: eine Erstattung eine negative Zahlung (§9.11). Eine Stornierung ist genau das, über den
#: vollen Betrag – und darum rechnet ``balance`` sie ohne einen einzigen Sonderfall.
REVERSE = "reverse"


# ---------------------------------------------------------------------------
# ►► LESEN
# ---------------------------------------------------------------------------

def of_step(db: Session, step_id: int) -> Optional[Deal]:
    """Der aktive Vorgang eines Moduls – oder ``None``. **Die eine Lesestelle.**"""
    return (
        db.query(Deal)
        .filter(Deal.step_id == step_id, Deal.is_active.is_(True))
        .first()
    )


def _entries(db: Session, deal_id: int) -> list[DealEntry]:
    """Die Geld-Zeilen eines Vorgangs, älteste zuerst – nur die gültigen."""
    return (
        db.query(DealEntry)
        .filter(DealEntry.deal_id == deal_id, DealEntry.is_active.is_(True))
        .order_by(DealEntry.booked_on, DealEntry.id)
        .all()
    )


def balance_of(db: Session, row: Deal) -> dm.Balance:
    """Die vier Zahlen dieses Vorgangs – gerechnet in ``domain/deal``, gelesen hier."""
    return dm.balance(row.amount, [(e.kind, e.amount) for e in _entries(db, row.id)])


# ---------------------------------------------------------------------------
# ►►► EINE ZAHLUNG GEHÖRT ZU GENAU EINER RECHNUNG (Testnotiz #858)
# ---------------------------------------------------------------------------
#
# «Wenn ich eine Rechnung ausstelle, dann wird eine Zahlung auf genau diese Rechnung
# referenziert. Ich soll nicht eine Zahlung für zwei verschiedene Rechnungen erfassen
# können – dann lieber die 2 Rechnungen stornieren und eine daraus machen.»
#
# **Das ist die einfachere Regel, nicht die ärmere.** Der Weg für «eine Überweisung über
# zwei Rechnungen» ist eine Stornorechnung und eine gemeinsame neue – ein Vorgang, den es
# längst gibt, mit einem Beleg, den man vorzeigen kann. Die Alternative wäre eine
# Aufteilungstabelle (Ausziffern) für eine Zahl, die daneben ohnehin als Summe steht.
#
# ``balance`` bleibt davon unberührt: es rechnet über die **Summen**. Hier geht es um
# «worauf», nicht um «wie viel».

def live_charge(db: Session, row: Deal) -> Optional[DealEntry]:
    """►►► **DIE Rechnung dieses Moduls — oder ``None``.** ◄◄◄ (Testnotiz #866)

    *«Nur eine Rechnung pro Zahlungsmodul. Habe ich Teilrechnungen, dann erstelle ich
    einfach 2 Zahlungsmodule.»* – Und das ist die richtige Modellierung, weil der Grund
    die **Zeit** ist: *Vorauszahlung → Leistung → Restzahlung* sind drei Zeitpunkte, ein
    Modul steht an einem. Zwei Rechnungen an derselben Stelle wären zwei Aussagen über
    einen Moment, den es nur einmal gibt.

    **Die eine Lesestelle der Regel.** Gezählt wird, was eine *Forderung nach aussen* ist:

    * eine **Gegenbuchung** (``reverses_id``) ist keine Rechnung, sondern ihre Rücknahme;
    * eine **stornierte** Zeile ist keine mehr – genau das ist der Ausweg: was falsch ist,
      wird storniert und neu gestellt, und danach darf die nächste entstehen;
    * eine **Gutschrift** (negativ) ist eine Minderung, keine zweite Rechnung – Skonto,
      Teilretoure und Kulanz bleiben jederzeit möglich.

    Bleibt genau eine übrig: die Rechnung dieses Vorgangs.
    """
    entries = _entries(db, row.id)
    undone = {e.reverses_id for e in entries if e.reverses_id is not None}
    live = [e for e in entries
            if e.kind == dm.CHARGE and e.reverses_id is None
            and e.id not in undone and e.amount > 0]
    return live[0] if live else None


def paid_on(db: Session, row: Deal, charge: DealEntry) -> Decimal:
    """Was auf **diese** Rechnung schon geflossen ist – die Grundlage des Wortes.

    Eine bezahlte Rechnung nimmt man nicht «zurück», man schreibt sie **gut**
    (Testnotiz #860); welches der beiden Wörter gilt, hängt an genau dieser Zahl.
    """
    return _paid_on(_entries(db, row.id), charge)


def transfer_info(db: Session, row: Deal, charge: DealEntry) -> dict[str, Any]:
    """►►► **Wie man diese Rechnung überweist** (Testnotiz #865). ◄◄◄

    Die dritte Bezahlart ist **keine Buchung**, sondern eine **Auskunft**: «Jetzt
    bezahlen» löst etwas aus, «Zahlung erfassen» schreibt etwas auf – die Überweisung
    braucht *Angaben*, damit der Zahlende sie selbst auslöst.

    **Warum sie im Zahlungsdienst nicht vorkommt**, und das ist keine Lücke: für **CHF**
    bietet er gar keine Überweisung an, und wo er sie anbietet, kostet sie Gebühren für
    Geld, das sonst gratis ankommt. Genau deshalb überweist man.

    **Bankverbindung im Klartext UND als QR** – nicht entweder-oder: der Code spart das
    Abtippen, der Klartext ist der Weg, wenn die Kamera nicht mitspielt oder die Bank den
    Code nicht kennt. Wo es keinen QR geben kann (fremde Währung, keine CH-IBAN), steht
    der **Grund** daneben statt einer leeren Fläche.
    """
    # **Überwiesen wird an den Aussteller**, nicht an den Betreiber (Testnotiz #905):
    # dieselbe Gesellschaft, die im Belegkopf steht – eine zweite Lesart wäre ein QR-Code,
    # der auf ein anderes Konto zeigt als der Beleg darüber.
    company = issuer_company(db, row)
    iban = getattr(company, "iban_encrypted", None)
    number = charge.reference or str(charge.id)
    amount = _open_of(_entries(db, row.id), charge)
    creditor = {
        "name": sites.legal_name(company) or "",
        "street": getattr(company, "street", None),
        "street_nr": getattr(company, "street_nr", None),
        "zip": getattr(company, "zip_code", None),
        "city": getattr(company, "city", None),
        "country": address.iso2(getattr(company, "country", None) or "CH"),
    }
    who = billing_of(db, row)
    seat = who.get("address") or {}
    debtor = {
        "name": who.get("name") or "",
        "street": seat.get("line1"), "street_nr": "",
        "zip": seat.get("postal_code"), "city": seat.get("city"),
        "country": seat.get("country"),
    }
    trouble = qrbill.problem(iban=iban, currency=row.currency, amount=amount)
    code = None if trouble else qrbill.svg(qrbill.payload(
        iban=iban or "", creditor=creditor, amount=amount,
        currency=row.currency, debtor=debtor, number=number))
    return {
        "iban": iban, "creditor": creditor["name"],
        "reference": qrbill.reference(number),
        "amount": _money(amount, row.currency), "currency": row.currency,
        "invoice": number, "qr": code, "problem": trouble,
    }


def open_charges(db: Session, row: Deal) -> list[DealEntry]:
    """**Die Rechnungen, auf die noch etwas offen ist** – älteste zuerst.

    Ausgenommen sind die **stornierten** und die **Stornozeilen** selbst: das Paar hebt
    sich auf, und auf eine zurückgenommene Rechnung zahlt niemand. Ohne diese Regel stünde
    eine stornierte Rechnung weiterhin als Ziel in der Auswahl.
    """
    entries = _entries(db, row.id)
    undone = {e.reverses_id for e in entries if e.reverses_id is not None}
    return [e for e in entries
            if e.kind == dm.CHARGE and e.reverses_id is None and e.id not in undone
            and _open_of(entries, e) > 0]


def open_of(db: Session, row: Deal, charge: DealEntry) -> Decimal:
    """Was auf **dieser** Rechnung noch offen ist – Betrag minus ihre Zahlungen."""
    return _open_of(_entries(db, row.id), charge)


def refundable(db: Session, row: Deal) -> list[DealEntry]:
    """**Die Karten-Zahlungen, die man zurückgeben kann** – jüngste zuerst.

    Nur eine **Karte**: bar und per Überweisung ist die Erstattung eine gewöhnliche
    negative Zahlung, die ein Mensch erfasst (Testnotiz #860). Und nur eine **positive**:
    eine Erstattung erstattet man nicht.

    Ihre Referenz ist die Zahlungsabsicht (``pi_…``) – ohne sie fände der Dienst die
    Belastung nicht, und der Knopf wäre eine Zusage, die er nicht halten kann.
    """
    return [e for e in reversed(_entries(db, row.id))
            if e.kind == dm.PAYMENT and e.method == dm.CARD and e.amount > 0
            and e.reference]


def card_payment(db: Session, row: Deal, entry_id: Optional[int]) -> DealEntry:
    """►►► **Welche Karten-Zahlung ist gemeint?** ◄◄◄ – oder ein Satz, warum keine.

    Zwei Formen einer Regel, ein Namensstamm (wie ``pick_problem``/``unpickable``):
    ``can`` beantwortet **ob** es hier überhaupt etwas zu erstatten gibt und zeigt darum
    den Knopf, ``card_payment`` beantwortet **welche** und ist das Tor. Ohne Angabe die
    **jüngste** – der Normalfall ist eine einzige Zahlung, und dann gibt es nichts zu
    wählen.
    """
    rows = refundable(db, row)
    if not rows:
        raise HTTPException(
            status_code=409,
            detail=("Hier ist keine Karten-Zahlung erfasst. Bar und per Überweisung ist "
                    "eine Erstattung eine gewöhnliche Zahlung mit negativem Betrag."),
        )
    if entry_id in (None, ""):
        return rows[0]
    found = next((e for e in rows if e.id == entry_id), None)
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=("Diese Zahlung lässt sich nicht über den Zahlungsdienst erstatten – "
                    "sie gehört zu einem anderen Vorgang oder kam nicht per Karte."),
        )
    return found


def _paid_on(entries: list[DealEntry], charge: DealEntry) -> Decimal:
    """Was auf diese Rechnung geflossen ist – **aus der schon geladenen Liste**."""
    return sum((e.amount for e in entries
                if e.kind == dm.PAYMENT and e.charge_id == charge.id), Decimal("0"))


def _open_of(entries: list[DealEntry], charge: DealEntry) -> Decimal:
    paid = sum((e.amount for e in entries
                if e.kind == dm.PAYMENT and e.charge_id == charge.id), Decimal("0"))
    return charge.amount - paid


def _charge_for_payment(db: Session, row: Deal,
                        value: Any) -> Optional[DealEntry]:
    """**Auf welche Rechnung geht diese Zahlung?** – genannt, vorbelegt oder abgewiesen.

    ►►► **Seit #866 hat die Frage genau EINE Antwort.** ◄◄◄ Es gibt je Modul höchstens
    eine lebende Rechnung – also ist sie gemeint, und danach zu fragen wäre eine Frage
    mit genau einer richtigen Antwort.

    *Hier stand eine dritte Möglichkeit («mehrere offene → die Zahlung muss sagen,
    welche») samt einem Satz, der sie aufzählte. Sie ist mit der Regel entfallen, nicht
    weggelassen: eine zweite lebende Rechnung kann gar nicht mehr entstehen, und ein Ast,
    den niemand erreicht, ist von einem kaputten nicht zu unterscheiden.*

    Bleibt **keine** – dann ``None``, und das ist kein Fehler: eine Erstattung oder eine
    Korrektur gehört zu einer Rechnung, die längst beglichen ist.

    Ein **genannter** Wert wird streng geprüft: er muss eine Forderung *dieses* Vorgangs
    sein. Sonst hinge eine Zahlung an einem fremden Beleg, und die Zuordnung wäre eine
    Behauptung statt einer Angabe.
    """
    if value not in (None, ""):
        try:
            wanted = int(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400,
                                detail=f"«{value}» ist keine Rechnung.")
        found = next((e for e in _entries(db, row.id)
                      if e.id == wanted and e.kind == dm.CHARGE), None)
        if found is None:
            raise HTTPException(
                status_code=400,
                detail="Diese Rechnung gehört nicht zu diesem Geldvorgang.")
        return found
    return live_charge(db, row)


def process_lines(db: Session, order: Order) -> list[tuple[int, int]]:
    """**Was steht im Auftrag?** – je Artikel eine Zeile ``(article_id, Stück)``.

    Derselbe Weg, aus dem der Prozess überall rechnet: offene Zugehörigkeit →
    Einzelinstanz → Instanz → Artikel. Sortiert, damit die Reihenfolge des Vorgangs nicht
    von der Datenbank abhängt.

    **Über den ganzen Auftrag und nicht über den einzelnen Schritt.** Ein Angebot entsteht,
    **bevor** die Stücke am Modul ankommen – ein Verkaufs-Vorgang am Ende der Kette hätte
    sonst bis zuletzt eine leere Zeile, und man könnte nichts anbieten. Und es ist auch
    fachlich richtig: dieselben sechs Wellen sind es, für die ich das Härten einkaufe und
    die ich danach verkaufe.
    """
    rows = (
        db.query(Instance.article_id, func.count(OrderUnit.id))
        .join(InstanceUnit, InstanceUnit.instance_id == Instance.id)
        .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
        .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None))
        .group_by(Instance.article_id)
        .all()
    )
    return sorted(((int(a), int(n)) for a, n in rows), key=lambda r: r[0])


def lines_of(db: Session, order: Order, row: Deal) -> list[dict[str, Any]]:
    """**Die Zeilen des Vorgangs** – Artikel · Menge, und beides abgeleitet.

    Ein Geldvorgang sitzt in einem Prozess: **worum** es geht, sind die Einzelinstanzen
    des Auftrags – also ihre Artikel; **wie viele**, ist ihre Zahl. Beides von Hand zu
    wählen wären zwei Aussagen über dieselbe Sache.

    **Mit der Zusage frieren die Zeilen ein** (``agreed_lines``): dort ist eine zweite
    Partei gebunden, und was zugesagt wurde, ändert sich nicht mehr dadurch, dass der
    Auftrag später Stücke verliert.
    """
    if row.agreed_lines:
        return [dict(line) for line in row.agreed_lines]
    return [{"article": a, "quantity": n} for a, n in process_lines(db, order)]


def embed_lines(db: Session, order: Order, row: Deal,
                *, step: Optional[ProcessStep] = None) -> list[dict[str, Any]]:
    """Die Zeilen **mit Namen, Preis und Zoll-Angaben** – das, was die Gegenpartei liest.

    ►►► **Zolltarifnummer und Ursprungsland: der Artikel belegt vor, der Beleg trägt
    den Wert** (Testnotiz #915). ◄◄◄ Die Nummer ist eine Eigenschaft der **Sache**;
    welche auf *diesem* Beleg steht, ist eine Aussage **dieses Geschäfts** – dieselbe
    Beziehung wie beim Preis. Steht in der (eingefrorenen) Zeile ein Wert, gilt er;
    sonst der des Artikels. **Zurückgeschrieben wird nichts**: ein Beleg korrigiert
    keine Stammdaten.

    *Die ganze Spezifikation reist seit #916 nicht mehr mit – auf einem Beleg steht,
    was der Empfänger braucht. Die beiden Zoll-Angaben sind keine Beschreibung, sondern
    Voraussetzung der Ausfuhr.*

    Eine Abfrage für alle Zeilen, nicht eine je Zeile.
    """
    lines = lines_of(db, order, row)
    fallback = dm.DEFAULT_VAT
    found = {
        a.id: a
        for a in db.query(Article).filter(
            Article.id.in_([int(line["article"]) for line in lines
                            if line.get("article") is not None])).all()
    } if lines else {}
    out: list[dict[str, Any]] = []
    for line in lines:
        # **Eine Zeile ohne Artikel ist der Normalfall dort, wo es keine Stücke gibt**
        # (Miete, Lohn, Gebühr) – derselbe Mechanismus mit einer entarteten Zeile, kein
        # zweiter Fall. Sie trägt keinen Namen und keine Spezifikation; ihren Sinn sagt
        # die Angabe «Was ist zu tun?» beim Partner.
        ref = line.get("article")
        art = found.get(int(ref)) if ref is not None else None
        out.append({
            "article_id": int(ref) if ref is not None else None,
            "article_object_id": art.object_id if art else None,
            "article_name": art.name if art else "",
            "quantity": int(line["quantity"]),
            # Der eingefrorene Wert gewinnt; ohne ihn der des Artikels (#915).
            "hs_code": line.get("hs_code") or (art.hs_code if art else None) or None,
            "origin_country": (line.get("origin_country")
                               or (art.origin_country if art else None) or None),
            # ►►► **Preis und Satz gehören der Position** (MWSTG Art. 26). ◄◄◄
            #
            # Der **Preis ist netto** – so denkt und rechnet man –, und der **Satz hängt an
            # der Sache**: sechs Wellen zu 8.1 % und eine Ausfuhr zu 0 % stehen auf
            # demselben Papier. Solange nichts zugesagt ist, steht kein Preis da und der
            # Satz ist die **Vorgabe des Moduls**; vorbelegen, nie erfinden.
            "price": line.get("price"),
            # ►►► **Der Satz reist als SCHLÜSSEL – und mit seiner Zahl daneben.** ◄◄◄
            #
            # Seit *Export* und *Reverse Charge* zwei Katalogzeilen sind, ist «0.00»
            # **mehrdeutig**: zwei verschiedene Rechtsgründe mit verschiedenen
            # Pflichtsätzen. Gespeichert wird darum der Schlüssel – und weil eingefrorene
            # Belege noch die alte Zahl tragen, wird hier **normalisiert** (`assert_vat`
            # setzt «8.10» auf «normal» um). Die Oberfläche sieht damit immer einen
            # Schlüssel und braucht keine zweite Toleranzregel.
            #
            # **Prozentzahl und Name kommen mit**: eine Anzeige, die «normal %» schreibt,
            # weil sie den Schlüssel für eine Zahl hält, ist genau der Fehler, den eine
            # zweite Auflösung im Browser produziert.
            "vat": dm.assert_vat(line.get("vat") or fallback),
            "vat_rate": str(dm.vat_of(line.get("vat") or fallback)),
            "vat_label": dm.vat_label(line.get("vat") or fallback),
            "vat_note": dm.vat_note(line.get("vat") or fallback),
        })
    return out


# ---------------------------------------------------------------------------
# ►► ANLAGE — mit der Freigabe, idempotent
# ---------------------------------------------------------------------------

def house_currency(db: Session) -> str:
    """**Die Währung des Hauses** – die des Betreibers, tolerant gelesen.

    Eine Lesestelle, damit die Vorgabe nicht an zwei Orten steht. Gibt es (noch) keinen
    Betreiber, gilt ``domain/currency.DEFAULT``: ein Vorgang ohne Währung wäre ein Betrag
    ohne Aussage, und ein harter Fehler beim Freigeben eines Auftrags wäre die falsche
    Antwort auf eine fehlende Stammdatenzeile.
    """
    operator = sites.find_operator(db)
    code = getattr(operator, "currency", None)
    try:
        return cur.assert_code(code)
    except ValueError:
        return cur.DEFAULT


def issuer_of(db: Session, actor_id: Optional[int]) -> Optional[int]:
    """►►► **Welche unserer Gesellschaften stellt den Beleg?** (Testnotiz #905) ◄◄◄

    Die des **freigebenden Mitarbeiters** (``UserProfile.company_object_id``). ``None``
    heisst «der Betreiber» – der Rückfall bleibt, er ist nur nicht mehr die Regel.

    *Gelesen wird die interne Id, nicht die Objektnummer: ``actor_id`` ist der
    Fremdschlüssel, den der Prozess ohnehin durchreicht (``people`` trägt den Schlüssel
    deshalb im Namen).*
    """
    if actor_id is None:
        return None
    u = db.query(UserProfile).filter(UserProfile.id == actor_id).first()
    return getattr(u, "company_object_id", None)


def instantiate_for_order(db: Session, order: Order,
                          *, actor_id: Optional[int] = None) -> None:
    """Jedes «Zahlung»-Modul dieses Auftrags bekommt seinen Vorgang.

    **Bei der Freigabe und nicht beim Erreichen**: mit wem und worüber gehandelt wird,
    steht in der Definition, und ein Angebot einzuholen dauert – wer erst beim Erreichen
    anfragt, wartet die Frist ab, nachdem alles andere fertig ist.

    Idempotent (der partielle Unique-Index trägt); ohne ein solches Modul ein No-op.
    """
    rows = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id,
                ProcessStep.module_type == modules.ZAHLUNG)
        .all()
    )
    for step in rows:
        if of_step(db, step.id) is None:
            db.add(Deal(
                order_id=order.id, step_id=step.id,
                direction=dm.assert_direction(
                    modules.get(step.module_type).direction_of(step.config)),
                # ►►► **Die Währung kommt vom Betreiber, nicht aus einem Feld.** ◄◄◄
                #
                # Der Normalfall ist die Hauswährung, und ihn zu tippen wäre eine Eingabe
                # mit genau einer richtigen Antwort. Wer in einer anderen fakturiert,
                # ändert sie am Vorgang – bis zur Zusage.
                currency=house_currency(db),
                # ►►► **Und wer ihn stellt, steht ebenso am Vorgang.** ◄◄◄ Eingefroren
                # aus der Gesellschaft des Freigebenden – bei jeder Anzeige neu gelesen
                # änderte ein Wechsel rückwirkend, wer einen alten Beleg gestellt hat.
                issuer_company_id=issuer_of(db, actor_id),
                stage=dm.OFFER, quotes=[],
            ))
    if rows:
        db.flush()


# ---------------------------------------------------------------------------
# ►► WER SIEHT WAS — und wer darf was
# ---------------------------------------------------------------------------

def mine(db: Session, viewer: Optional[UserProfile]) -> Optional[list[Deal]]:
    """**Woran ist dieser Betrachter beteiligt?** ``None`` = an allem.

    Die eine Frage, aus der die ganze Gegenpartei-Sicht folgt. Beteiligt ist, wer
    **angefragt** wurde: seine Objektnummer steht in ``quotes``.

    **Personal bekommt ``None``** – wer ohnehin ins ERP darf, braucht keine verengte
    Sicht: er sieht den ganzen Auftrag und trägt dort ein, was einzutragen ist. Ein
    Mitarbeiter, der zufällig Gegenpartei ist, arbeitet weiter in der vollen Ansicht.

    **Sonst fragt diese Funktion nicht nach der Rolle.** Jeder darf Gegenpartei sein –
    die Rolle sagt, was jemand *für uns* tut, nicht ob wir mit ihm Geld austauschen.
    Gefiltert wird in der **Datenbank** (JSONB-Containment): die Alternative wäre, für
    jede Feed-Anzeige sämtliche Vorgänge des Hauses zu laden.
    """
    if viewer is None or viewer.role in STAFF_ROLES:
        return None
    if viewer.object_id is None:
        return []
    return (
        db.query(Deal)
        .filter(Deal.quotes.contains([{"party": viewer.object_id}]))
        .all()
    )


# ---------------------------------------------------------------------------
# ►►► WAS DIESES MODUL BRAUCHT — und was es meldet, wenn es fehlt ◄◄◄
# ---------------------------------------------------------------------------
#
# *«Wenn das Modul zu wenig Angaben hat, um seinen Prozess abzuwickeln, dann muss es
# Alarm schlagen.»*
#
# ►►► **Das ist kein neuer Mechanismus – es ist ``StepNeed`` für Stammdaten.** ◄◄◄
#
# Der Verbrauch meldet fehlendes **Material** als Zeile («Artikel · gebraucht ·
# verfügbar»), und die Regel dazu steht seit §9.6 im Haus: *Nichtverfügbarkeit ist KEIN
# Zustand.* Die Freigabe geht, das Modul bewegt nichts, und die Zeile sagt in Klartext,
# woran es liegt. Eine fehlende **Stammdatenangabe** ist dieselbe Aussage über einen
# anderen Gegenstand – also bekommt sie dieselbe Form und **keinen** Pausenwert.
#
# ►►► **Durchgesetzt wird sie ohne eine neue Regel: die Lücken speisen ``can``.** ◄◄◄
# Fehlt etwas, führt ``can`` das Verb nicht – der Knopf ist damit **nicht da** (ein Knopf,
# der nie etwas tun kann, ist kein Angebot), und ``assert_allowed`` weist an derselben
# Liste ab. Eine zweite Prüfung daneben wäre der zweite Massstab, den ``can`` gerade
# abschafft.
#
# ►►► **Gestaffelt je Handlung, nicht als ein Block.** ◄◄◄ Eine Anfrage braucht weniger
# als eine Rechnung. Stünde alles vor der ersten Handlung, hielte eine Angabe das Modul
# an, die erst in drei Schritten zählt – und man müsste sie erfinden, um weiterzukommen.

#: **Was wann verlangt wird** – eine Tabelle, keine Bedingungskette. Ein neues Feld ist
#: eine Zeile hier, und ein neues Modul deklariert seine eigene Liste.
#:
#: ``(seite, feld, beschriftung, grund)`` – ``seite`` ist ``us`` oder ``party``.
REQUIRED_FOR: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "ask": (
        ("us", "name", "Firma und Rechtsform",
         "Ein Beleg nennt die Rechtsperson, die ihn stellt."),
        ("us", "address", "Anschrift",
         "Ohne Sitz ist der Aussteller nicht bestimmbar."),
        ("us", "contact", "E-Mail oder Telefon",
         "Ohne Kontaktweg landet jede Rückfrage im Telefonbuch."),
    ),
    # ►►► **Die Gegenpartei steht erst mit der ZUSAGE fest.** ◄◄◄
    #
    # Beim Anfragen ist sie noch nicht gewählt – ``deals.party_id`` ist ``NULL``, und das
    # ist der Sinn der Stufe: man fragt mehrere. Ihre Angaben hier zu verlangen hiesse,
    # eine Anfrage an der Angabe scheitern zu lassen, die sie gerade erst erzeugt.
    "agree": (
        ("party", "name", "Name",
         "Ein Beleg braucht einen Adressaten."),
        ("party", "address", "Anschrift",
         "Eine Zusage bindet eine Rechtsperson – die braucht einen Sitz."),
        ("us", "uid", "UID / MWST-Nummer",
         "Ohne sie kann dem Empfänger der Vorsteuerabzug verweigert werden "
         "(MWSTG Art. 26)."),
    ),
    "charge": (
        ("us", "iban", "IBAN",
         "Auf eine Rechnung gehört, wohin überwiesen wird."),
        ("party", "uid", "UID / MWST-Nummer",
         "Beim Reverse Charge schuldet der Leistungsempfänger die Steuer – ohne seine "
         "Nummer trägt das Verfahren nicht."),
    ),
}


def _has(side: dict[str, Any], field: str) -> bool:
    """Steht diese Angabe wirklich da? **Leer ist nicht vorhanden.**"""
    if field == "contact":
        return bool(side.get("email") or side.get("phone"))
    value = side.get(field)
    return bool(value)


def gaps(db: Session, row: Deal, *, action: str,
         party_id: Optional[int] = None) -> list[dict[str, Any]]:
    """►►► **Welche Angaben fehlen, um DIESE Handlung zu tun?** ◄◄◄

    Zurück kommt je Lücke eine Zeile mit dem **Datensatz** (klickbar), dem **Feld** und
    einem Satz, der sagt, **warum dieser Beleg sie braucht**. Was daraus folgt, entscheidet
    ein Mensch – wie bei ``StepNeed``: hingehen und eintragen.

    **Gestaffelt und kumulativ**: ``charge`` verlangt auch, was ``ask`` und ``agree``
    verlangen. Eine Rechnung ohne Adressaten gibt es nicht, nur weil man schon zugesagt
    hat.

    **Zwei Sonderfälle, beide benannt:**

    * Die **IBAN** verlangt nur, wer **einzieht** (``collects``). Auf einer
      Lieferantenrechnung steht *seine* Bankverbindung, nicht unsere.
    * Die **UID des Empfängers** verlangt nur ein Beleg, der *Reverse Charge* trägt –
      im Inland ist sie nicht vorgeschrieben, und ein Pflichtfeld, das meistens leer
      bleiben darf, ist keines.
    """
    # ►►► **Geprüft wird die Partei, um die es GEHT.** ◄◄◄
    #
    # Beim Zuschlag steht sie in der **Nutzlast**, nicht am Vorgang: ``party_id`` wird
    # erst von ``_agree`` gesetzt, und die Prüfung läuft davor. Ohne diese Angabe prüfte
    # sich die Zusage gegen eine leere Gegenseite und wäre nie möglich.
    #
    # **Und wo noch gar keine feststeht, wird die Gegenseite nicht geprüft** – beim
    # Anfragen gibt es sie noch nicht, und der Knopf muss trotzdem da sein.
    look = party_id if party_id is not None else row.party_id
    head = _head_for(db, row, look)
    flow = dm.of(row.direction)
    us, party = ((head["supplier"], head["customer"]) if flow.collects
                 else (head["customer"], head["supplier"]))
    sides = {"us": us, "party": party}
    known = look is not None
    # **Reverse Charge steht an der POSITION** – gefragt sind die zugesagten Zeilen; vor
    # der Zusage gibt es noch keine, und dort verlangt auch niemand die Nummer.
    reverse = any(ln.get("vat") == "reverse" for ln in (row.agreed_lines or []))
    out: list[dict[str, Any]] = []
    for stage in _UP_TO.get(action, ()):
        for side, field, label, why in REQUIRED_FOR[stage]:
            if field == "iban" and not flow.collects:
                continue
            if side == "party" and not known:
                continue
            if field == "uid" and side == "party" and not reverse:
                continue
            if field == "iban":
                # **Die IBAN der Gesellschaft, die den Beleg stellt** – nicht die des
                # Betreibers: überwiesen wird an den Aussteller (``issuer_company``).
                company = issuer_company(db, row)
                if getattr(company, "iban_encrypted", None):
                    continue
                out.append(_gap(sides["us"], label, why))
                continue
            if not _has(sides[side], field):
                out.append(_gap(sides[side], label, why))
    return out


#: Welche Stufen eine Handlung **mitverlangt** – kumulativ, in der Reihenfolge des Belegs.
_UP_TO: dict[str, tuple[str, ...]] = {
    "ask": ("ask",),
    "quote": ("ask",),
    "agree": ("ask", "agree"),
    "charge": ("ask", "agree", "charge"),
}


def _head_for(db: Session, row: Deal, party_id: Optional[int]) -> dict[str, Any]:
    """Der Belegkopf, wie er **mit dieser Partei** aussähe – ohne den Vorgang zu ändern.

    Dieselbe Ableitung wie ``document_head``; nur wird die Gegenseite vorübergehend auf
    die genannte gesetzt. Ein zweiter Kopf-Aufbau daneben wäre die zweite Wahrheit, die
    beim nächsten Feld auseinanderläuft.
    """
    if party_id is None or party_id == row.party_id:
        return document_head(db, row, won=True)
    before = row.party_id
    try:
        row.party_id = party_id
        return document_head(db, row, won=True)
    finally:
        row.party_id = before


def _next_action(row: Deal) -> str:
    """**Welche Handlung steht an dieser Stufe an?** – die, deren Lücken zählen.

    Vor der Zusage ist es das Anbieten bzw. Anfragen, danach die Rechnung. Eine Liste
    aller Lücken über alle Stufen wäre eine Mängelliste statt einer Auskunft: sie nennte
    Angaben, die erst in drei Schritten gebraucht werden, und niemand wüsste, welche
    gerade im Weg steht.
    """
    return "charge" if row.stage != dm.OFFER else "ask"


def _gap(side: dict[str, Any], label: str, why: str) -> dict[str, Any]:
    """Eine Lücke als Zeile – **wo** sie hingehört, **was** fehlt, **warum**."""
    return {
        "record_object_id": side.get("object_id"),
        "record_label": side.get("name") or side.get("label") or "",
        "field_label": label,
        "why": why,
    }


def can(db: Session, row: Deal, viewer: Optional[UserProfile]) -> list[str]:
    """►►► **Was darf DIESER Betrachter an DIESEM Vorgang tun?** ◄◄◄

    Stufe **mal** Rolle, an einer Stelle – und dieselbe Antwort reist mit der Antwort mit
    (``DealEmbed.can``) und weist in ``apply`` ab.
    """
    stage = list(ACTIONS.get(row.stage, ()))
    rows = _entries(db, row.id)
    # ►►► **Ohne Rechnung keine Zahlung** (Testnotiz #822). ◄◄◄
    #
    # Man kassiert nicht, was niemand gefordert hat – der Satz steht seit §9.11 im Haus,
    # jetzt steht er auch in `can`. Damit gilt er in **beide** Richtungen: die Oberfläche
    # bietet den Knopf nicht an, und `apply` weist ihn ab.
    #
    # Die **Vorauszahlung** verliert dadurch nichts: sie ist «erst fordern, dann zahlen»
    # – die Rechnung kommt dort vor der Lieferung, nicht nach der Zahlung.
    if "pay" in stage and not any(e.kind == dm.CHARGE for e in rows):
        stage.remove("pay")
    # ►►► **Online bezahlen: DREI Bedingungen, alle an EINER Stelle.** ◄◄◄
    #
    # Es gibt ihn (1) nur, wo das Geld **zu uns** fliesst – ein Zahlungsdienst zieht ein,
    # er überweist nicht in unserem Namen (``Direction.collects``); (2) nur, wenn einer
    # **eingerichtet** ist – sonst wäre es ein Knopf, der garantiert in einem leeren
    # Dialog endet; und (3) nur, wenn wirklich etwas **offen** ist.
    #
    # *Hier stand eine vierte – «es muss eine Rechnung geben», die Regel von ``pay``
    # (#822). Beim Gegenprüfen war ihre Bug-Form **nicht herstellbar**: ``open`` ist
    # ``Forderungen − Zahlungen``, und ohne Forderung ist es null oder negativ. Sie sagte
    # also nichts, was ``open > 0`` nicht schon sagt. Bei ``pay`` ist das anders – dort
    # nennt ein Mensch den Betrag, und «ohne Rechnung keine Zahlung» ist eine echte
    # zusätzliche Aussage; hier ist der offene Betrag die Sache selbst.*
    #
    # Alle drei stehen hier, weil ``can`` **Auskunft und Tor** ist: der Knopf erscheint
    # genau dann, wenn der Endpunkt ihn auch bedient. Eine Bedingung, die nur dort stünde,
    # wäre ein Angebot, das beim Klicken scheitert.
    if "pay_online" in stage and not (
        dm.of(row.direction).collects
        and payment_service_ready()
        and balance_of(db, row).open > 0
    ):
        stage.remove("pay_online")
    # ►►► **Zurückerstatten geht nur, wo auch eingezogen wurde** (Testnotiz #860). ◄◄◄
    #
    # *«Ich kann bzw. soll können einen Betrag zurückerstatten.»* – Und der Weg dafür hängt
    # daran, **wie** das Geld kam: bar und per Überweisung ist die Erstattung eine
    # gewöhnliche negative Zahlung (die es längst gibt); eine **Karte** erstattet der
    # Dienst, der sie belastet hat, und der Webhook bucht die Zeile wie jede andere.
    #
    # Dieselben zwei Bedingungen wie beim Einziehen (Richtung, eingerichteter Dienst) plus
    # die eine, die es hier gibt: es muss eine **Karten-Zahlung** dastehen, die man
    # zurückgeben kann. Ohne sie wäre es ein Knopf, den der Dienst mit «unbekannte
    # Zahlung» abweist.
    if "refund_online" in stage and not (
        dm.of(row.direction).collects
        and payment_service_ready()
        and refundable(db, row)
    ):
        stage.remove("refund_online")
    if viewer is not None and viewer.role not in STAFF_ROLES:
        # Die Gegenpartei nennt ihren Preis oder sagt ab – und nur, solange sie
        # tatsächlich angefragt ist.
        if _quote_of(row, viewer.object_id) is None:
            return []
        return [a for a in stage if a in dm.of(row.direction).party_actions]
    # ►►► **Stornieren geht, solange es einen stornierbaren BELEG gibt.** ◄◄◄
    #
    # Drei Dinge sind abgezogen, und jedes hat seinen eigenen Grund: eine **Zahlung** ist
    # kein Beleg, sondern ein Ereignis (#842 – sie wird durch eine zweite Zahlung
    # korrigiert); eine **Gegenbuchung** storniert man nicht; und eine bereits
    # **stornierte** Zeile ebenso wenig – sonst entstünde eine Kette aus Vorzeichen, in
    # der niemand mehr sagen kann, was gilt. Fehlte hier auch nur einer davon, stünde das
    # Verb in ``can``, obwohl ``_reverse`` jede einzelne Zeile abweist: ein Knopf, der
    # garantiert scheitert.
    already = {e.reverses_id for e in rows if e.reverses_id is not None}
    if any(e.kind == dm.CHARGE and e.reverses_id is None and e.id not in already
           for e in rows):
        stage.append(REVERSE)
    # ►►► **Was Angaben braucht, die es nicht gibt, steht hier nicht.** ◄◄◄
    #
    # Die Lücken speisen ``can`` – damit ist die Vollständigkeit **keine zweite Regel**:
    # der Knopf erscheint gar nicht, und ``assert_allowed`` weist an derselben Liste ab.
    # Was fehlt, sagt die Karte daneben (``DealEmbed.gaps``), damit «geht nicht» nicht
    # ohne «woran es liegt» dasteht.
    #
    # Nur die Verben, die **nach aussen** wirken: eine Absage, ein Storno und jede
    # Geld-Zeile müssen möglich bleiben, auch wenn ein Stammdatenfeld fehlt – sonst wäre
    # eine unvollständige Anschrift eine Sackgasse, aus der niemand mehr herauskommt.
    return [a for a in stage if not (a in _UP_TO and gaps(db, row, action=a))]


def _int(value: Any) -> Optional[int]:
    """Eine Objektnummer aus der Nutzlast – **tolerant**, denn hier wird nur nachgesehen.

    Ein unlesbarer Wert ist hier keine Ablehnung: der Handler, der ihn wirklich braucht,
    weist ihn mit einem Satz ab. Diese Stelle sucht nur, wen sie prüfen soll.
    """
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def assert_allowed(db: Session, row: Deal, action: str,
                   viewer: Optional[UserProfile],
                   party_id: Optional[int] = None) -> None:
    """►►► **Das Tor zu ``can`` – zwei Formen einer Regel, ein Namensstamm.** ◄◄◄

    ``can`` nennt die erlaubten Verben (die Oberfläche rendert genau sie), ``assert_allowed``
    weist alles andere ab. Sie liest **dieselbe** Liste – ein zweiter, milderer Massstab
    wäre ein Knopf, der bereitsteht und dann scheitert, oder eine Tür, die etwas durchlässt,
    das niemand anbietet.

    Sie ist **öffentlich**, weil nicht jedes Verb durch ``apply`` läuft: ``pay_online``
    hat seinen eigenen Endpunkt und muss trotzdem an derselben Tür vorbei.
    """
    if action in can(db, row, viewer):
        return
    # ►►► **«Geht nicht» ohne «woran es liegt» ist eine Sackgasse mit Ausrufezeichen.** ◄◄◄
    #
    # Es gibt **zwei** Gründe, warum ein Verb fehlt, und sie verlangen verschiedene
    # Handlungen: die **Stufe** (dann ist es zu früh oder zu spät) und eine **fehlende
    # Angabe** (dann geht man hin und trägt sie ein). Ein Satz für beide nennte in der
    # Hälfte der Fälle die falsche Ursache – und der Mensch suchte am falschen Ort.
    missing = (gaps(db, row, action=action, party_id=party_id)
               if action in _UP_TO else [])
    if missing:
        first = missing[0]
        raise HTTPException(
            status_code=400,
            detail=(f"Dafür fehlt {first['field_label']} bei "
                    f"«{first['record_label']}». {first['why']}"
                    + (f" (und {len(missing) - 1} weitere Angabe"
                       f"{'n' if len(missing) > 2 else ''})" if len(missing) > 1 else "")),
        )
    flow = dm.of(row.direction)
    raise HTTPException(
        status_code=409,
        detail=(f"«{action}» geht hier nicht: der Vorgang steht auf "
                f"«{flow.label_of(row.stage)}»."),
    )


# ---------------------------------------------------------------------------
# ►► DIE HANDLUNGEN
# ---------------------------------------------------------------------------

def apply(db: Session, *, order: Order, step: ProcessStep, action: str,
          payload: dict[str, Any], actor: Optional[UserProfile] = None) -> Deal:
    """**Eine Handlung am Geldvorgang** – ein Endpunkt, neun Verben."""
    row = of_step(db, step.id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Zu diesem Modul gibt es keinen Geldvorgang.",
        )
    # **Die Nutzlast weiss, um wen es geht** – beim Zuschlag steht die Gegenpartei dort,
    # und die Vollständigkeitsprüfung muss sie kennen, bevor ``_agree`` sie setzt.
    assert_allowed(db, row, action, actor, _int(payload.get("party")))
    # ►►► **Nicht jedes Verb in ``can`` ändert den Vorgang.** ◄◄◄
    #
    # ``pay_online`` **löst** eine Zahlung aus und bucht nichts – es hat darum keinen
    # Eintrag hier und seinen eigenen Weg (``…/deal/payment``); gebucht wird erst, wenn
    # der Zahlungsdienst es meldet. Ohne diese Zeile wäre der Zugriff auf ``HANDLERS`` ein
    # ``KeyError`` und an der Tür ein **500** – eine Ablehnung ohne Erklärung, obwohl die
    # Antwort ein Satz ist.
    run = HANDLERS.get(action)
    if run is None:
        raise HTTPException(
            status_code=409,
            detail=(f"«{action}» ändert den Geldvorgang nicht – diese Handlung hat "
                    f"ihren eigenen Weg."),
        )
    run(db, order=order, step=step, row=row, data=payload, actor=actor)
    db.flush()
    return row


def _currency(db: Session, *, order: Order, step: ProcessStep, row: Deal,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **In welcher Währung wird gehandelt?** ◄◄◄

    Eine Angabe **je Vorgang**, nicht je Zeile: zwei Währungen auf einem Beleg gibt es
    nicht, das wären zwei Belege. Vorbelegt ist die Hauswährung
    (``house_currency``) – wer in einer anderen fakturiert, sagt es hier.

    **Streng geschrieben** (``currency.assert_code`` nennt die erlaubten): ein Code, den
    es nicht gibt, fällt sonst erst auf, wenn jemand eine Summe über zwei Währungen zieht.
    Dass es **nach der Zusage** nicht mehr geht, sagt ``ACTIONS`` – nicht diese Funktion.

    **Umgerechnet wird nichts.** Ein Kurs hat ein Datum und eine Quelle; wer ohne beides
    umrechnet, erfindet Zahlen. Die bereits genannten Beträge bleiben darum stehen: sie
    sind Angebote, und ein Angebot in einer anderen Währung ist ein neues Angebot.
    """
    try:
        row.currency = cur.assert_code(data.get("currency"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _issuer(db: Session, *, order: Order, step: ProcessStep, row: Deal,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Wer stellt diesen Beleg?** (Testnotiz #905) ◄◄◄

    Vorgewählt ist die Gesellschaft des freigebenden Mitarbeiters; hier wird sie
    korrigiert – der Fall, dass jemand für eine Schwestergesellschaft anbietet.

    **Nur eine unserer Gesellschaften**, und das wird geprüft: eine Objektnummer, die auf
    nichts zeigt, wäre auf einem Beleg schlimmer als gar keine – sie sieht aus wie eine
    Angabe. ``None`` ist erlaubt und heisst «der Betreiber».

    Dass es **nach der Zusage** nicht mehr geht, sagt ``ACTIONS`` – wie bei der Währung.
    """
    value = _int(data.get("issuer"))
    if value is not None and sites.by_object_id(db, value) is None:
        raise HTTPException(
            status_code=400, detail=f"«{value}» ist keine unserer Gesellschaften.")
    row.issuer_company_id = value


def _incoterm(db: Session, *, order: Order, step: ProcessStep, row: Deal,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Die Lieferbedingung** (Incoterms 2020). ◄◄◄

    Wer Fracht, Versicherung und Zoll trägt – die Angabe, die im Aussenhandel über
    Tausende entscheidet und ohne die jeder Beleg eine Rückfrage auslöst.

    **Ein Katalog, kein Freitext** (``incoterms.assert_incoterm`` nennt die erlaubten):
    «DAT» ist die Klausel von 2010, die es 2020 nicht mehr gibt – wer sie schickt, soll
    das lesen statt still etwas Ungültiges zu vereinbaren.

    **Der benannte Ort ist Pflicht, sobald eine Klausel steht**: «FCA» allein ist keine
    Vereinbarung – bei genau dieser Klausel entscheidet der Ort, wo das Risiko übergeht.
    Umgekehrt wird der Ort mit der Klausel gelöscht: ein Ort ohne Klausel sagt nichts.

    Dass es **nach der Zusage** nicht mehr geht, sagt ``ACTIONS`` – wie bei der Währung.
    """
    try:
        key = inc.assert_incoterm(data.get("incoterm"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    place = _text(data.get("incoterm_place"), 120)
    if key and not place:
        raise HTTPException(
            status_code=400,
            detail=(f"«{key}» braucht einen benannten Ort – ohne ihn ist die Klausel "
                    f"keine Vereinbarung (z. B. «{key} Rorschach»)."),
        )
    row.incoterm = key
    row.incoterm_place = place if key else None


def _priced(db: Session, *, order: Order, step: ProcessStep, code: str,
            data: dict[str, Any]) -> list[dict[str, Any]]:
    """►►► **Die Positionen mit Preis und Satz** – die Nutzlast nennt nur Preis und Satz.

    **Die Menge kommt aus dem Prozess, nie aus der Nutzlast** (dieselbe Regel wie überall
    im Haus): sie ist die Zahl der Einzelinstanzen, die vor dem Modul stehen. Eine
    getippte Menge wäre die zweite Aussage über dieselbe Sache – und die getippte gewinnt,
    auch wenn sie falsch ist.

    Eine Zeile **ohne Artikel** ist der Normalfall dort, wo es gar keine Stücke gibt
    (Miete, Lohn, Gebühr): Menge 1, Preis netto. Das ist derselbe Mechanismus mit einer
    entarteten Zeile, kein zweiter Fall.
    """
    counts = dict(process_lines(db, order))
    fallback = dm.DEFAULT_VAT
    out: list[dict[str, Any]] = []
    for raw in data.get("lines") or []:
        article = raw.get("article")
        price = _amount(raw.get("price"), code, allow_negative=True)
        if price is None:
            continue
        try:
            vat = dm.assert_vat(raw.get("vat") or fallback)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        out.append({
            "article": int(article) if article is not None else None,
            "quantity": counts.get(int(article), 0) if article is not None else 1,
            # **Gerundet je Währung**, nie fest auf zwei Stellen: ein Yen-Betrag mit
            # zwei Nachkommastellen behauptet eine Genauigkeit, die es nicht gibt.
            "price": cur.money(price, code),
            "vat": vat,
            # ►►► **Zoll-Angaben gehören zur Position** (Testnotiz #915). ◄◄◄ Leer heisst
            # «nimm die des Artikels» – als leerer String gespeichert wäre es die
            # Behauptung, es gebe keine.
            "hs_code": _text(raw.get("hs_code"), 12),
            "origin_country": _text(raw.get("origin_country"), 60),
        })
    return out


def _ask(db: Session, *, order: Order, step: ProcessStep, row: Deal,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Die Gegenparteien **anfragen** bzw. ihnen **anbieten**.

    **Ohne Angabe sind es alle zugelassenen.** Steht in der Definition genau eine, ist
    die Wahl zur Laufzeit keine Wahl – dann heisst der Knopf «Anbieten» und fragt nicht
    nach dem Kunden (Testnotiz #793). Nur wo mehrere zugelassen sind, ist die Auswahl
    eine echte Frage – und genau dort ist der Angebotsspiegel der Punkt.

    Wo die Definition **niemanden** nennt, heisst das **frei**: dann muss die Nutzlast
    sagen, wen man fragt.
    """
    flow = dm.of(row.direction)
    allowed = modules.parties_allowed(step.config)
    wanted = [n for n in (data.get("parties") or [])] or allowed
    if not wanted:
        raise HTTPException(
            status_code=400,
            detail=(f"Ohne {dm.PARTY} gibt es nichts anzufragen – dieses Modul "
                    f"lässt jeden zu, also muss hier stehen, wen es betrifft."),
        )
    # ►►► **Wer den Preis nennt, füllt ihn VOR dem Hinausgehen** (Testnotiz #837). ◄◄◄
    #
    # Bei einer **Ausgabe** fragen wir an und warten auf seine Offerte – die Zeile geht
    # leer hinaus, und das ist ihr Sinn. Bei einer **Einnahme** nennen **wir** den Preis:
    # ein Angebot ohne Betrag ist keines, und ihn danach nachzutragen hiesse, dem Kunden
    # zwischendurch eine leere Zeile zu zeigen.
    #
    # Der Betrag gilt für **alle** Zeilen dieser Anfrage – man bietet allen dasselbe an;
    # wer danach je Partner nachbessert, tut das über ``quote``.
    # ►►► **Wo WIR den Preis nennen, sind die POSITIONEN der Preis** (MWSTG Art. 26). ◄◄◄
    #
    # Ein Betrag allein trägt keinen Steuersatz, und ohne Satz ist eine Rechnung keine.
    # Der Angebotsbetrag ist darum die **Brutto-Summe der Positionen**, nicht mehr eine
    # getippte Zahl daneben – zwei Zahlen über dieselbe Sache liefen auseinander.
    priced = _priced(db, order=order, step=step, code=row.currency,
                     data=data) if flow.quoted_by == dm.BY_US else []
    if flow.quoted_by == dm.BY_US and not priced:
        raise HTTPException(
            status_code=400,
            detail=(f"Ohne Preis gibt es nichts anzubieten – bei einer {flow.label} "
                    f"nennen wir ihn, nicht der {dm.PARTY}."),
        )
    # ►►► **Wann die Zeile hinausging** (Testnotiz #918). ◄◄◄ Die Chronik des Belegs
    # fragt «wann wurde offeriert» – und das weiss nur der Moment, in dem es passiert.
    # Als Datum im JSONB, nicht als Spalte: es gehört der **Zeile**, und von denen gibt
    # es n (der Angebotsspiegel ist eine Liste).
    fresh = ({"amount": cur.money(dm.gross_of(priced, row.currency), row.currency),
              "lines": priced, "state": dm.QUOTED, "sent_on": date.today().isoformat()}
             if priced else {"amount": None, "lines": [], "state": dm.ASKED,
                             "sent_on": date.today().isoformat()})
    lead, days = _days(data.get("lead_days")), _days(data.get("payment_days"))
    # ►►► **Wer den Preis nennt, nennt auch die beiden Fristen** (Testnotizen #854/#856).
    # ◄◄◄ Sie sind der Rest der Zusage: aus der Lieferfrist kommt der Termin, aus der
    # Zahlungsfrist die Fälligkeit – **und die Vorauszahlung**. Ein Angebot ohne sie ist
    # eines, über das sich später niemand einig ist. Bei einer **Ausgabe** geht die Zeile
    # leer hinaus, und dort füllt sie die Gegenpartei (``_quote``).
    if priced:
        _assert_terms(lead, days)
    lines = list(row.quotes or [])
    for value in wanted:
        number = _party(db, step=step, value=value, flow=flow)
        if number is None or any(q.get("party") == number for q in lines):
            continue
        lines.append({"party": number, "lead_days": lead,
                      "payment_days": days, **fresh})
    _write_quotes(row, lines)


def _quote(db: Session, *, order: Order, step: ProcessStep, row: Deal,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Einen Preis an **einer** Angebotszeile eintragen.

    **Wer eintragen darf, entscheidet nicht die Nutzlast**: eine Gegenpartei trifft
    ausschliesslich ihre eigene Zeile (``_target`` liest ``actor.object_id``). Wer sie
    erst an der Tür formulierte, hätte die Regel beim zweiten Aufrufer nicht.
    """
    party = _target(row, data, actor)
    flow = dm.of(row.direction)
    # ►►► **Wer den Preis nennt, nennt ihn in derselben Form wie beim Anfragen.** ◄◄◄
    #
    # Bei einer **Einnahme** sind das die Positionen (dort hängt der Steuersatz); bei einer
    # **Ausgabe** nennt die Gegenpartei einen Gesamtbetrag – ihre Steuer steht auf ihrer
    # Rechnung, nicht in unserem Angebotsspiegel. Ein Verb, zwei Nutzlasten, und welche
    # gilt, sagt dieselbe Angabe wie überall (``quoted_by``).
    priced = _priced(db, order=order, step=step, code=row.currency,
                     data=data) if flow.quoted_by == dm.BY_US else []
    amount = dm.gross_of(priced, row.currency) if priced \
        else _amount(data.get("amount"), row.currency)
    # ►►► **Nur gesendete Felder wirken – auch für den Betrag.** ◄◄◄
    #
    # Wer nur eine **Frist** nachreicht, nennt keinen Preis: bei einer Einnahme steht er
    # längst in den Positionen, bei einer Ausgabe in der Zeile, die die Gegenpartei
    # gefüllt hat. Ohne diese Zeile war der Preis Pflicht bei **jedem** Aufruf – und die
    # Frist damit an einer bereits offerierten Zeile nicht mehr änderbar, ohne den Preis
    # noch einmal mitzuschicken (also ihn erneut zu behaupten).
    if amount is None:
        amount = _amount((_quote_of(row, party) or {}).get("amount"), row.currency)
    if amount is None:
        raise HTTPException(status_code=400,
                            detail="Ohne Betrag ist es keine Offerte.")
    # ►►► **Nur gesendete Felder wirken.** ◄◄◄
    #
    # Sie standen hier fest im Satz und wurden damit bei jedem Aufruf überschrieben – wer
    # nur den Betrag nachreicht, verlor beide Fristen. Über die Tür fällt es nicht auf
    # (``DealUpdate.changes`` schickt ungesetzte Felder gar nicht mit), aber die Regel
    # gehört in den **Dienst**: die Tür ist nicht der einzige Aufrufer, und ein Handler,
    # der auf sie angewiesen ist, ist beim zweiten falsch.
    changes: dict[str, Any] = {"amount": cur.money(amount, row.currency),
                               "state": dm.QUOTED}
    if priced:
        changes["lines"] = priced
    for field in ("lead_days", "payment_days"):
        if field in data:
            changes[field] = _days(data.get(field))
    # ►►► **Eine Offerte trägt beide Fristen** (Testnotizen #854/#856). ◄◄◄
    #
    # Geprüft wird das **Ergebnis**, nicht die Nutzlast: «nur gesendete Felder wirken»
    # bleibt gültig, wer also nur den Betrag nachreicht, behält seine Fristen. Fehlt
    # danach eine, ist die Zeile unvollständig – und das fällt sonst erst auf, wenn die
    # Rechnung keine Fälligkeit hat.
    before = _quote_of(row, party) or {}
    _assert_terms(*(_days_or_none(changes.get(f, before.get(f)))
                    for f in ("lead_days", "payment_days")))
    _patch_quote(row, party, changes)


def _decline(db: Session, *, order: Order, step: ProcessStep, row: Deal,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Eine Angebotszeile absagen – «kommt für uns nicht in Frage» bzw. «liefert nicht»."""
    _patch_quote(row, _target(row, data, actor), {"amount": None, "state": dm.DECLINED})


def _agree(db: Session, *, order: Order, step: ProcessStep, row: Deal,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Den **Zuschlag** geben – die Schwelle. Ab hier ist eine zweite Partei gebunden.

    Der Betrag kommt aus der **gewählten Zeile**; ein Wert in der Nutzlast übersteuert ihn
    (verhandelt wird auch am Telefon). Beides ist Pflicht: eine Zusage ohne Gegenpartei ist
    keine, und eine ohne Betrag ist eine, über die sich später niemand einig ist.

    ►►► **Wo die POSITIONEN den Preis tragen, gibt es keine zweite Zahl.** ◄◄◄

    Bei einer **Einnahme** nennen wir den Preis je Position, und der Betrag des Vorgangs
    *ist* ihre Brutto-Summe (``gross_of``) – dieselbe Summe, aus der auch Netto, Steuer je
    Satz und die Aufteilung einer Teilrechnung kommen (``vat_split``/``split_for``). Eine
    daneben getippte Zahl wäre nicht bloss eine zweite Wahrheit über dieselbe Sache,
    sondern eine, die den **Beleg widersprüchlich** macht: «Total 900» über einer
    Aufstellung, die auf 1000 aufgeht. Sie wird darum **abgewiesen**, nicht still
    verworfen – wer nachverhandelt, ändert den Preis dort, wo er steht.

    Bei einer **Ausgabe** nennt die Gegenpartei eine Summe; dort ist der Betrag die
    einzige Angabe, und ein Wert in der Nutzlast ist die Nachverhandlung.

    **Und hier frieren die Zeilen ein**: was zugesagt wurde, ändert sich nicht mehr
    dadurch, dass der Auftrag später Stücke verliert.
    """
    party = _target(row, data, actor)
    line = _quote_of(row, party) or {}
    priced = [dict(x) for x in (line.get("lines") or []) if x.get("price") is not None]
    given = _amount(data.get("amount"), row.currency) \
        if data.get("amount") is not None else None
    if priced:
        amount = dm.gross_of(priced, row.currency)
        if given is not None and given != amount:
            raise HTTPException(
                status_code=400,
                detail=(f"Der Betrag dieses Vorgangs ist die Summe seiner Positionen "
                        f"({cur.money(amount, row.currency)} {row.currency}) – eine "
                        f"zweite Zahl daneben würde den Beleg widersprüchlich machen. "
                        f"Wer nachverhandelt, ändert den Preis an der Position."),
            )
    else:
        amount = given if given is not None else _amount(line.get("amount"), row.currency)
    if amount is None:
        raise HTTPException(
            status_code=400,
            detail=(f"{dm.PARTY} {party} hat keinen Preis genannt – ohne Betrag "
                    f"gibt es keine Zusage. (0.00 ist erlaubt und heisst «kostenlos».)"),
        )
    _patch_quote(row, party, {"state": dm.CHOSEN})
    row.party_id = party
    row.amount = amount
    # ►►► **Die Null ist eine Angabe** – auch hier. ◄◄◄
    #
    # Es stand ``_days(payload) or _days(line)``, und damit fiel eine **null** aus der
    # Nutzlast durch: «Vorauszahlung» am Telefon vereinbart hiess `0`, `0 or X` ist `X`,
    # und es galt still die Frist der Offerte. Dieselbe Falle, gegen die ``_assert_terms``
    # ausdrücklich auf ``is None`` prüft – hier fehlte sie.
    wanted = _days(data.get("payment_days"))
    row.due_days = wanted if wanted is not None else _days(line.get("payment_days"))
    row.stage = dm.AGREED
    row.agreed_on = date.today()
    # **Und die Währung ist ab hier gebunden** – wie der Betrag und die Zeilen: draussen
    # liegt eine Zusage über *diese* Summe in *dieser* Währung.
    # ►►► **Eingefroren wird, was die GEWÄHLTE Zeile sagt.** ◄◄◄
    #
    # Trägt sie Positionspreise (wir haben den Preis genannt), sind sie die Zusage – mit
    # ihrem Steuersatz. Sonst bleiben es Artikel und Menge aus dem Prozess: bei einer
    # **Ausgabe** steht die Steuer auf **seiner** Rechnung, und eine hier erfundene wäre
    # eine Behauptung über ein fremdes Dokument.
    row.agreed_lines = priced or [dict(x) for x in (line.get("lines") or [])] \
        or lines_of(db, order, row)


def _revoke(db: Session, *, order: Order, step: ProcessStep, row: Deal,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Stornieren – und der Vorgang **behält seinen Weg**.

    Ein Storno macht die Zusage nicht ungeschehen, er sagt nur, dass nichts mehr kommt.
    Die gegangenen Stufen bleiben darum stehen; das Geld darf weiterhin fliessen, denn
    eine Anzahlung muss erstattet werden können.

    ►►► **Und wann es war, steht danach da** (Testnotiz #918). ◄◄◄ ``stage`` sagt
    **dass** storniert wurde; die Chronik des Belegs fragt nach dem **wann**, und
    ``updated_at`` ist die Antwort nicht – sie wandert bei jeder späteren Änderung mit.
    """
    row.stage = dm.CANCELLED
    row.cancelled_on = date.today()


def _charge(db: Session, *, order: Order, step: ProcessStep, row: Deal,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Eine **Forderung** buchen. Negativ ist die Gutschrift.

    **Die Automatik steckt in den Vorgaben, nicht in einem Modus**: Betrag = *zugesagt −
    berechnet* (nie negativ, ``Balance.next_charge``), Fälligkeit = *heute + Frist*,
    Nummer = ``<Auftragsnummer>-<laufend>``, wo wir nummerieren.
    """
    flow = dm.of(row.direction)
    given = _amount(data.get("amount"), row.currency, allow_negative=True)
    value = given if given is not None else balance_of(db, row).next_charge
    if value is None:
        raise HTTPException(status_code=400, detail="Ohne Betrag keine Rechnung.")
    # ►►► **EINE Rechnung je Modul** (Testnotiz #866) – durchgesetzt hier, angeboten in
    # ``embed_data`` (``credit_only``): zwei Formen einer Regel, ein Namensstamm.
    #
    # Gesperrt ist genau **eine zweite positive Forderung**. Eine **Gutschrift** (negativ)
    # bleibt jederzeit möglich – sie ist eine Minderung derselben Rechnung, keine zweite;
    # und was falsch ist, wird **storniert und neu gestellt**, womit die Regel keinen
    # Zustand ohne Ausgang hinterlässt.
    live = live_charge(db, row)
    if live is not None and value > 0:
        raise HTTPException(
            status_code=409,
            detail=(f"Dieser Vorgang hat bereits die Rechnung «{live.reference or live.id}» – "
                    f"je Zahlungs-Modul gibt es genau eine. Eine zweite gehört in ein "
                    f"zweites Zahlungs-Modul (Vorauszahlung und Restzahlung sind zwei "
                    f"Schritte im Prozess); was hier falsch ist, wird storniert und neu "
                    f"gestellt, und eine Minderung ist eine Gutschrift mit negativem "
                    f"Betrag."),
        )
    booked = _day(data.get("booked_on")) or date.today()
    # ►►► **Eine Nummer, die WIR vergeben, tippt niemand ab** (Testnotiz #840). ◄◄◄
    #
    # Sie entsteht aus der Serie – lückenlos und ohne Doppelung. Ein gesendeter Wert wird
    # darum **verworfen**, nicht bloss ignoriert: ein Feld, das die Oberfläche nicht
    # anbietet, der Dienst aber annimmt, wäre eine Hintertür zu genau der zweiten
    # Wahrheit, die es hier nicht geben darf.
    #
    # Wo die Gegenpartei die Rechnung stellt, ist es **ihre** Nummer – sie steht auf ihrem
    # Papier, und ohne sie liesse sich der Beleg nicht zuordnen.
    number = (_our_number(db, order) if flow.reference is None
              else _text(data.get("reference"), 120))
    # ►►► **Die Steuer-Aufteilung wird EINGEFROREN, nicht gerechnet.** ◄◄◄
    #
    # Ein gebuchter Beleg behält seine Steuerangabe. Aus den Positionen nachgerechnet
    # änderte sich die Steuer einer längst gestellten Rechnung, sobald jemand eine
    # Position anfasst – eine rückwirkend geänderte Steuerangabe, und genau das darf es
    # nicht geben (MWSTG Art. 26).
    #
    # **Wo Positionen mit Preis stehen** (wir haben ihn genannt), verteilt ``split_for``
    # den Betrag über ihre Sätze – bei einer **Teilrechnung** anteilig, denn eine
    # Anzahlung ist zum Satz der zugrunde liegenden Leistung zu versteuern.
    # **Sonst** (eine Ausgabe: die Steuer steht auf *seiner* Rechnung) nennt das Formular
    # den Satz, und wir schreiben ab, was auf dem Beleg steht.
    lines = [ln for ln in (row.agreed_lines or []) if ln.get("price") is not None]
    if lines:
        split = dm.split_for(value, lines, row.currency)
    else:
        try:
            split = dm.split_at(value, dm.assert_vat(
                data.get("vat") or dm.DEFAULT_VAT), row.currency)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    db.add(DealEntry(
        deal_id=row.id, kind=dm.CHARGE, amount=value, booked_on=booked,
        due_on=_day(data.get("due_on")) or _due(booked, row.due_days),
        reference=number, note=_text(data.get("note"), 200),
        vat=split,
        # ►►► **Das Leistungsdatum kommt aus dem PROZESS** (Testnotiz #852). ◄◄◄
        #
        # «Wann wurde die Leistung erbracht?» weiss der Auftrag: es ist der Tag, an dem
        # die Stücke dieses Modul erreicht haben. Das Rechnungsdatum ist es **nicht** –
        # eine Rechnung, die zwei Wochen später geschrieben wird, verschöbe damit die
        # Steuerperiode (MWSTG Art. 26 Bst. c).
        #
        # ►►► **Und es ist keine Eingabe** (Testnotiz #919). ◄◄◄ Es stand als Feld im
        # Formular und war damit die **zweite Aussage** über dieselbe Sache – die
        # getippte gewinnt, auch wenn sie falsch ist. Der Prozess weiss es besser als
        # jemand, der eine Rechnung schreibt. Ein trotzdem gesendeter Wert wird
        # **verworfen**: ein Feld, das die Oberfläche nicht anbietet, der Dienst aber
        # annimmt, wäre eine Hintertür zu einer Angabe, die niemand mehr prüft.
        service_date=service_day(db, step) or booked,
    ))


def _pay(db: Session, *, order: Order, step: ProcessStep, row: Deal,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Eine **Zahlung** buchen. Negativ ist die Erstattung.

    Vorgabe ist der **offene** Betrag, und auch er nie negativ: ist mehr gezahlt als
    gefordert, gibt es nichts vorzuschlagen – die Erstattung tippt ein Mensch.

    ►►► **Und sie gehört zu genau EINER Rechnung** (Testnotiz #858). ◄◄◄
    """
    charge = _charge_for_payment(db, row, data.get("charge_id"))
    given = _amount(data.get("amount"), row.currency, allow_negative=True)
    value = given if given is not None else (
        open_of(db, row, charge) if charge is not None
        else balance_of(db, row).next_payment)
    if value is None:
        raise HTTPException(status_code=400, detail="Ohne Betrag keine Zahlung.")
    # ►►► **Wo WIR nummerieren, tippt niemand – auch nicht an der Zahlung** (#850). ◄◄◄
    #
    # Die Regel galt nur für die Rechnung, und an der Zahlung stand weiter ein Feld: bei
    # einer **Einnahme** trägt aber auch sie unsere Nummer (sie referenziert unsere
    # Rechnung). Zwei Regeln für dieselbe Frage laufen genau so auseinander.
    flow = dm.of(row.direction)
    # ►►► **WIE bezahlt wurde – bar, Überweisung, Karte** (Testnotiz #865). ◄◄◄
    #
    # «Zahlung erfassen» heisst *aufschreiben, was passiert ist* – und das ist bei einer
    # eingegangenen Überweisung dasselbe wie bei Bargeld. Die Art gehört darum an die
    # **Zeile**, nicht in den Namen des Knopfes. Die **Karte** weist ``assert_method`` ab:
    # sie entsteht beim Zahlungsdienst, und von Hand erfasst wäre sie eine Behauptung über
    # eine Belastung, für die es keinen Beleg gibt (``record_payment`` schreibt sie).
    try:
        method = dm.assert_method(data.get("method"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.add(DealEntry(
        deal_id=row.id, kind=dm.PAYMENT, amount=value,
        booked_on=_day(data.get("booked_on")) or date.today(),
        reference=(None if flow.reference is None
                   else _text(data.get("reference"), 120)),
        note=_text(data.get("note"), 200),
        charge_id=charge.id if charge is not None else None,
        method=method,
    ))


def _reverse(db: Session, *, order: Order, step: ProcessStep, row: Deal,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Eine Geld-Zeile stornieren — durch eine Gegenbuchung.** ◄◄◄

    **Gelöscht wird nichts.** Eine Rechnungsnummer ist vergeben, ein Beleg ist draussen;
    wer die Zeile verschwinden lässt, behauptet, sie sei nie passiert – und genau so sah
    der frühere Papierkorb aus (Testnotizen #823/#824).

    Gebucht wird stattdessen eine **Gegenzeile**: dieselbe Art, der negative Betrag, ein
    Verweis auf die stornierte (``reverses_id``). Die Summe stimmt damit von selbst
    (``balance`` rechnet beide) und braucht **keinen Sonderfall**.

    **Zweimal stornieren geht nicht**, und eine Gegenzeile lässt sich nicht stornieren –
    sonst entstünde eine Kette aus Vorzeichen, in der niemand mehr sagen kann, was gilt.

    *Und es gibt keinen Löschweg mehr, auch nicht für einen Tippfehler: genau so
    korrigiert jede Buchhaltung der Welt, und eine Frist («innerhalb fünf Minuten») wäre
    eine erfundene Regel mit einer Uhr darin.*
    """
    entry = (
        db.query(DealEntry)
        .filter(DealEntry.id == data.get("entry"), DealEntry.deal_id == row.id,
                DealEntry.is_active.is_(True))
        .first()
    )
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="Diese Zeile gehört nicht zu diesem Vorgang.",
        )
    # ►►► **Man storniert einen BELEG, kein Ereignis** (Testnotiz #842). ◄◄◄
    #
    # Eine **Forderung** ist ein Beleg, den wir ausstellen – den kann man zurücknehmen,
    # und die Stornorechnung ist das übliche Mittel dafür. Eine **Zahlung** ist etwas
    # anderes: sie ist die Aufzeichnung dessen, was auf dem Konto passiert ist. Ein
    # Ereignis der Aussenwelt macht man nicht ungeschehen.
    #
    # Wer sich vertippt hat oder wem das Geld zurückkam, bucht eine **zweite Zahlung**
    # (negativ) – und *welcher* der beiden Fälle es ist, weiss nur ein Mensch. Die
    # Oberfläche bietet sie darum vorbelegt an; angelegt wird sie nicht von selbst.
    if entry.kind != dm.CHARGE:
        raise HTTPException(
            status_code=409,
            detail=("Eine Zahlung storniert man nicht – sie ist ein Ereignis, kein Beleg. "
                    "Erfasse eine zweite Zahlung mit dem negativen Betrag: das ist die "
                    "Korrektur eines Erfassungsfehlers ebenso wie eine Erstattung."),
        )
    if entry.reverses_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Diese Zeile ist selbst eine Stornierung – sie storniert sich nicht.",
        )
    if _reversal_of(db, entry.id) is not None:
        raise HTTPException(
            status_code=409,
            detail="Diese Zeile ist bereits storniert.",
        )
    # ►►► **Eine Stornorechnung ist ein EIGENER Beleg** (Testnotiz #841). ◄◄◄
    #
    # Sie kopierte die Nummer der stornierten: zwei Belege hiessen gleich, und in der
    # Serie fehlte die nächste Zahl. Eine Stornorechnung ist aber MWST-pflichtig ein
    # eigenes Dokument mit **eigener** Nummer und einem **Verweis** auf die stornierte.
    #
    # Die Regel dahinter gilt für jede Zeile: **jede Nummer wird genau einmal vergeben.**
    # Der Bezug wohnt in ``reverses_id`` (und im Vermerk), nie in der Nummer.
    flow = dm.of(row.direction)
    db.add(DealEntry(
        deal_id=row.id, kind=entry.kind, amount=-entry.amount,
        booked_on=date.today(), due_on=None,
        reference=(_our_number(db, order) if flow.reference is None else None),
        note=f"Storno zu {entry.reference}" if entry.reference else "Storno",
        reverses_id=entry.id,
        # **Die Gegenbuchung spiegelt die Steuer** – sonst hebt sie den Betrag auf, und
        # die Steuer der stornierten Rechnung bliebe für immer in der Abrechnung stehen.
        #
        # **Gespiegelt wird die ganze Zeile**, nicht nur ihre Zahlen: Schlüssel, Name und
        # Pflichtsatz gehören zur stornierten Aussage. Würden hier nur ``rate``, ``net``
        # und ``tax`` neu gebaut, verlöre die Gegenbuchung ausgerechnet den Rechtsgrund,
        # den sie zurücknimmt (und zwei Nullsätze wären danach nicht mehr zu trennen).
        vat=[{**r,
              "net": cur.money(-Decimal(r["net"]), row.currency),
              "tax": cur.money(-Decimal(r["tax"]), row.currency)}
             for r in (entry.vat or [])],
        service_date=entry.service_date,
    ))


def _reversal_of(db: Session, entry_id: int) -> Optional[DealEntry]:
    """Die Gegenzeile zu dieser Zeile – oder ``None``. **Die eine Lesestelle.**"""
    return (
        db.query(DealEntry)
        .filter(DealEntry.reverses_id == entry_id, DealEntry.is_active.is_(True))
        .first()
    )


# ---------------------------------------------------------------------------
# ►► DER ANGEBOTSSPIEGEL — geschrieben wird immer NEU, nie an Ort
# ---------------------------------------------------------------------------

def _write_quotes(row: Deal, lines: list[dict[str, Any]]) -> None:
    """Die Liste **ersetzen**, nie mutieren.

    Der geladene JSONB-Wert darf nicht an Ort geändert werden: sonst sind geladener und
    aktueller Wert gleich, die Spalte fällt aus dem ``UPDATE``, und die Offerte ist
    stillschweigend weg (dieselbe Falle wie ``purchase._write`` und ``units._runs``).
    """
    row.quotes = [dict(line) for line in lines]


def _quote_of(row: Deal, party: Optional[int]) -> Optional[dict[str, Any]]:
    """Die Zeile dieser Gegenpartei – oder ``None``. Die eine Lesestelle."""
    if party is None:
        return None
    return next((dict(q) for q in (row.quotes or []) if q.get("party") == party), None)


def _patch_quote(row: Deal, party: int, changes: dict[str, Any]) -> None:
    """Eine Zeile ändern – über Neubau der ganzen Liste."""
    lines = [dict(q) for q in (row.quotes or [])]
    for line in lines:
        if line.get("party") == party:
            line.update(changes)
            _write_quotes(row, lines)
            return
    raise HTTPException(
        status_code=404,
        detail=f"{party} ist an diesem Vorgang nicht angefragt.",
    )


def _target(row: Deal, data: dict[str, Any],
            actor: Optional[UserProfile]) -> int:
    """**Wessen Zeile ist gemeint?**

    Eine Gegenpartei trifft ausschliesslich ihre eigene – gelesen aus ``actor``, nie aus
    der Nutzlast. Das Personal nennt sie in der Nutzlast.
    """
    if actor is not None and actor.role not in STAFF_ROLES:
        return int(actor.object_id)
    try:
        return int(data["party"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Es fehlt die Angabe, um wessen Angebotszeile es geht.",
        )


# ---------------------------------------------------------------------------
# ►► DIE SPERRE UND DER ABSCHLUSS — beide am EINEN Ausführungs-Mechanismus
# ---------------------------------------------------------------------------

def assert_completable(db: Session, *, step: ProcessStep) -> None:
    """**Darf dieses Modul bestätigt werden?** – gerufen von ``process.confirm_step``.

    Drei Gründe, warum nicht, und alle drei sind derselbe Satz: der Geldvorgang ist noch
    nicht so weit. Es gibt dafür **keinen Zustand am Stück** und keinen Pausenwert – das
    Modul ist schlicht nicht fertig (dieselbe Haltung wie ``StepNeed`` beim Verbrauch).

    Ohne Geldvorgang ein No-op: jedes andere Modul läuft hier unverändert durch.
    """
    row = of_step(db, step.id)
    if row is None:
        return
    flow = dm.of(row.direction)
    if row.stage == dm.OFFER:
        raise HTTPException(
            status_code=409,
            detail=(f"«{flow.label}»: der Auftrag ist noch nicht bestätigt – bis dahin "
                    f"steht kein Betrag fest, und es gibt nichts zu erledigen."),
        )
    if row.stage == dm.CANCELLED:
        raise HTTPException(
            status_code=409,
            detail=(f"«{flow.label}» ist storniert. Die Stücke stehen still, bis "
                    f"jemand entscheidet, was mit ihnen geschieht – dafür gibt es den "
                    f"ganz gewöhnlichen Abweichungsauftrag."),
        )
    # ►►► **Die Sperre ist die vereinbarte ZAHLUNGSFRIST** (Testnotiz #854). ◄◄◄
    #
    # Sie stand einmal als Schalter in der Modul-Definition (``modules.prepaid(config)``)
    # und sagte, was die Frist ohnehin sagt: «zahlbar in null Tagen ab Zusage» *ist* die
    # Vorauszahlung. Zwei Angaben über eine Sache – und wer sie verschieden setzte, hatte
    # einen Vorgang, der etwas anderes sagt als er tut.
    if not dm.prepaid(row.due_days):
        return
    money = balance_of(db, row)
    if not money.settled:
        raise HTTPException(
            status_code=409,
            detail=(f"«{flow.label}» wartet auf den Zahlungseingang: "
                    f"{money.paid} von {money.agreed} bezahlt. So ist es vereinbart – "
                    f"{dm.PAYMENT_TERMS[0][1]}, erst das Geld, dann weiter."),
        )


def finish(db: Session, *, order: Order, step: ProcessStep) -> None:
    """Nach ``confirm_step``: steht nichts mehr davor, ist der Auftrag **erledigt**.

    Teilabschluss braucht dafür keine eigene Regel – ``confirm_step`` ist einer. **Nur
    der Auftrag ist damit erledigt, nicht das Geld**: Forderungen und Zahlungen laufen
    weiter, denn ein Zahlungsziel endet nicht mit der Ware.
    """
    row = of_step(db, step.id)
    if row is None or row.stage != dm.AGREED:
        return
    waiting = (
        db.query(OrderUnit)
        .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None),
                OrderUnit.current_step_id == step.id)
        .count()
    )
    if waiting:
        return
    row.stage = dm.DONE
    db.flush()


# ---------------------------------------------------------------------------
# ►► DER ZAHLUNGSDIENST — eine Tür, und sie ist NICHT die des Menschen
# ---------------------------------------------------------------------------
#
# Ein Zahlungsdienst ruft nicht ``apply``: er hat keinen angemeldeten Benutzer, keine
# Stufe und keine Meinung darüber, was jemand tun darf. Er meldet **eine Tatsache** –
# Geld ist geflossen –, und genau eine Zeile entsteht.
#
# Darum steht diese Naht hier und nicht in ``ACTIONS``: ``can`` ist das Tor für
# **Menschen**, und ein Webhook, der sich durch dasselbe Tor zwängen müsste, bräuchte
# einen erfundenen Akteur mit erfundenen Rechten.

def service_day(db: Session, step: ProcessStep) -> Optional[date]:
    """►►► **Wann wurde die Leistung erbracht?** – aus dem Prozess, nicht getippt. ◄◄◄

    Es ist der Tag, an dem die Stücke **das Modul davor** verlassen haben, also bei diesem
    hier angekommen sind. Genau das ist die Leistung, für die Rechnung gestellt wird.

    **Das Rechnungsdatum ist es nicht.** Eine Rechnung, die zwei Wochen später geschrieben
    wird, verschöbe damit die Steuerperiode – und bei einem Satzwechsel entscheidet das
    Leistungsdatum, welcher Satz gilt (MWSTG Art. 26 Bst. c). Zwei Angaben, ein Datum
    einzutippen wäre die dritte.

    **Gelesen wird darum das Ereignis des VORGÄNGERS**, nicht das eigene: ein ``step``
    an *diesem* Modul heisst «hier fertig», und das ist der Zeitpunkt, an dem die
    Rechnung ohnehin schon geschrieben sein soll. Steht dieses Modul am Anfang, ist die
    Ankunft der **Start** des Auftrags – dieselbe Frage, eine Stelle früher.

    ``None`` heisst «hier ist noch nichts angekommen»; dann bleibt es beim Buchungstag –
    ein Datum zu erfinden wäre schlimmer als keines.
    """
    before = (
        db.query(ProcessStep.id)
        .filter(ProcessStep.order_id == step.order_id,
                ProcessStep.position < step.position)
        .order_by(ProcessStep.position.desc())
        .first()
    )
    q = db.query(ProcessEvent.created_at).filter(ProcessEvent.order_id == step.order_id)
    q = (q.filter(ProcessEvent.step_id == before[0], ProcessEvent.kind == KIND_STEP)
         if before else
         q.filter(ProcessEvent.kind == KIND_START, ProcessEvent.step_id.is_(None)))
    row = q.order_by(ProcessEvent.id.desc()).first()
    return row[0].date() if row and row[0] else None


# ►►► **``open_amount`` ist entfallen** (Testnotiz #858). ◄◄◄
#
# Es lieferte den offenen Betrag des **ganzen Vorgangs** – also die Summe über womöglich
# zwei Rechnungen. Genau daraus entstünde die Zahlung, die auf zwei Belege zeigt. Kassiert
# wird darum über **eine** Rechnung (``open_charges`` + ``open_of``), und die nennt die
# Bezahlkarte auch: ohne Beleg keine Zahlung.


def of_reference(db: Session, reference: str) -> Optional[Deal]:
    """**Zu welchem Vorgang gehört diese Zahlungsreferenz?**

    Der Rückweg einer Erstattung: sie nennt die Referenz der ursprünglichen Zahlung, und
    die steht an genau einer Zeile im Haus (dieselbe Regel wie die Idempotenz unten).
    """
    row = (
        db.query(DealEntry)
        .filter(DealEntry.kind == dm.PAYMENT, DealEntry.reference == reference,
                DealEntry.is_active.is_(True))
        .first()
    )
    if row is None:
        return None
    return db.query(Deal).filter(Deal.id == row.deal_id).first()


def record_payment(db: Session, *, row: Deal, amount: Decimal,
                   reference: Optional[str] = None,
                   note: Optional[str] = None,
                   charge_id: Optional[int] = None,
                   method: Optional[str] = None) -> DealEntry:
    """**Eine Zeile Geld** – die Tür des Zahlungsdienstes.

    ►►► **Idempotent über die Referenz.** ◄◄◄ Ein Zahlungsdienst stellt dieselbe Meldung
    mehrfach zu (das ist kein Fehler, das ist sein Auslieferungsversprechen). Dieselbe
    Referenz ist dieselbe Zahlung – zurück kommt die **bereits gebuchte** Zeile, nicht
    eine zweite.

    **Und eine Referenz gehört zu genau EINER Zahlung im Haus**: taucht sie an einem
    *anderen* Vorgang auf, ist das ein Irrtum und kein Duplikat. Er wird **genannt** – ein
    stiller Nicht-Effekt (200, nichts gebucht, offener Betrag unverändert) ist schlimmer
    als ein Fehler.
    """
    if reference:
        seen = (
            db.query(DealEntry)
            .filter(DealEntry.kind == dm.PAYMENT, DealEntry.reference == reference,
                    DealEntry.is_active.is_(True))
            .first()
        )
        if seen is not None:
            if seen.deal_id != row.id:
                raise HTTPException(
                    status_code=409,
                    detail=(f"Die Referenz «{reference}» hängt bereits an einem anderen "
                            f"Geldvorgang. Zweimal dieselbe Zahlung gibt es nicht."),
                )
            return seen
    entry = DealEntry(
        deal_id=row.id, kind=dm.PAYMENT, amount=amount,
        booked_on=date.today(), reference=reference, note=note,
        # **Worauf sie geht, sagt der Aufrufer** – die Bezahlkarte hat die Rechnung
        # ausgewählt, bevor sie kassiert hat, und die Meldung trägt sie zurück. Eine
        # Erstattung kennt ihre Zahlung, nicht die Rechnung; dort bleibt es ``None``, und
        # das ist ehrlicher als eine geratene Zuordnung.
        charge_id=charge_id,
        # ►►► **Die Karte tippt niemand ab** (Testnotiz #865) – sie steht hier, weil der
        # Dienst sie meldet. ``assert_method`` weist sie an der Menschentür ab; die beiden
        # sind zwei Formen einer Regel, nicht zwei Regeln.
        method=method,
    )
    db.add(entry)
    db.flush()
    return entry


def billing_of(db: Session, deal: Deal) -> dict[str, Any]:
    """**Was wir über den Zahlenden schon wissen** – Name, E-Mail, Rechnungsadresse.

    Der Zahlende ist die Gegenpartei **dieses Vorgangs**, nicht der Betrachter: auch wenn
    ein Mitarbeiter die Zahlung am Schalter auslöst, gehört die Rechnung dem Kunden.

    ►►► **Zwei Leser, eine Auskunft.** ◄◄◄ Sie stand im Adapter des Zahlungsdienstes und
    wurde dort gebraucht, um das Bezahlformular vorzufüllen. Die **QR-Rechnung** stellt
    dieselbe Frage (wer überweist, und unter welcher Anschrift?) – zwei Fassungen davon
    liefen beim ersten neuen Adressfeld auseinander. Sie gehört darum an den **Vorgang**,
    den beide ohnehin in der Hand haben.

    **Die Rechnungsadresse geht vor der Wohnadresse** – dafür ist sie da; steht keine da,
    gilt die Hauptadresse. Und geliefert wird nur eine **vollständige**: Strasse, Ort und
    PLZ gehören zusammen, und eine halbe Adresse wäre eine Vorbelegung, die das Formular
    danach doch wieder erfragt – nur falsch.
    """
    empty: dict[str, Any] = {"name": None, "email": None, "address": None}
    if deal.party_id is None:
        return empty
    u = db.query(UserProfile).filter(UserProfile.object_id == deal.party_id).first()
    if u is None:
        return empty
    # **Eine Rechnungsadresse gilt als hinterlegt, sobald irgendein Feld davon steht** –
    # sonst mischte sich die eine Hälfte mit der anderen zu einer Adresse, die es nirgends
    # gibt.
    own = bool(u.invoice_first_name or u.invoice_last_name or u.invoice_address_line1
               or u.invoice_company)
    named = " ".join(x for x in (u.invoice_first_name, u.invoice_last_name) if x).strip()
    line1 = (u.invoice_address_line1 if own else u.address_line1) or ""
    line2 = (u.invoice_address_line2 if own else u.address_line2) or ""
    city = (u.invoice_city if own else u.city) or ""
    zip_code = (u.invoice_postal_code if own else u.postal_code) or ""
    country = (u.invoice_country if own else u.country) or u.country
    full = bool(line1.strip() and city.strip() and zip_code.strip())
    return {
        "name": (named or u.invoice_company if own else None) or people.name(u),
        # ►►► **Auf dem BELEG steht die Rechtsperson, nicht ihr Vertreter.** ◄◄◄
        #
        # ``people.name`` ist person-first (#291) – im ERP richtig, auf einer Rechnung
        # falsch: Schuldner ist die *Muster AG*. ``billing_name`` liefert darum Zeilen
        # (Firma, darunter «z. H. …»); wer nur einen String braucht, nimmt weiterhin
        # ``name``. Zwei Formen einer Regel, nicht zwei Regeln.
        "lines": people.billing_name(u),
        "email": (u.invoice_email if own else None) or u.email,
        "phone": u.phone,
        # **Dieselbe Rangfolge wie bei uns** – die MWST-Nummer trägt den Vorsteuerabzug,
        # die blosse UID ist immer noch besser als nichts.
        "uid": u.vat_number or u.uid_number,
        "address": {
            "line1": line1, "line2": line2 or None, "city": city,
            "postal_code": zip_code, "country": address.iso2(country),
        } if full else None,
    }


def issuer_company(db: Session, row: Deal):
    """►►► **Unsere Seite des Belegs** – die eingefrorene Gesellschaft. ◄◄◄

    **Eine Lesestelle**, damit Belegkopf, Lückenprüfung und Anzeige nicht drei Antworten
    auf dieselbe Frage geben. Der **Betreiber** bleibt der Rückfall – für jeden Vorgang,
    der vor dieser Angabe entstanden ist, und für jeden, dessen Gesellschaft es nicht
    mehr gibt: ein Beleg ohne Aussteller wäre schlimmer als einer mit dem Betreiber.
    """
    return sites.by_object_id(db, row.issuer_company_id) or sites.find_operator(db)


def document_head(db: Session, row: Deal, *, won: bool) -> dict[str, Any]:
    """►►► **Wer stellt den Beleg, und wer bekommt ihn** (MWSTG Art. 26). ◄◄◄

    Eine Rechnung ist erst eine, wenn sie **beide Seiten** nennt: Name und Ort, wie im
    Geschäftsverkehr aufgetreten, und die **UID mit dem Zusatz MWST** dessen, der sie
    stellt – ohne ihn kann dem Empfänger der Vorsteuerabzug verweigert werden.

    ►►► **Neu ist hier nichts als die ZUORDNUNG.** ◄◄◄ Beide Seiten stehen längst da:
    **uns** kennt ``sites.find_operator``, den **Partner** kennt ``billing_of`` –
    dieselbe Auskunft, aus der der Einzahlungsschein seinen Schuldner nimmt. Es gibt
    darum keine zweite Adressenlogik und kein neues Feld.

    **Welche Seite welche Rolle hat, sagt die Richtung** – und zwar über die Angabe, die
    es schon gibt: ``Direction.collects`` («fliesst das Geld zu uns?»). Wo es zu uns
    fliesst, sind **wir** der Lieferant; bei einer Ausgabe ist es der Partner. Ein
    zweites Feld «wer fakturiert» wäre dieselbe Aussage ein zweites Mal – und die beiden
    gerieten beim ersten Vorgang in Widerspruch, in dem jemand nur eine davon setzt.

    **Was fehlt, wird nicht erfunden**: eine Seite ohne hinterlegte Anschrift trägt
    ``address = None``, eine ohne UID ``uid = None``. Die Oberfläche sagt dann klein an
    der Stelle, was fehlt – eine erfundene Zeile wäre auf einem Beleg schlimmer als eine
    leere.

    ►►► **Und die Gegenseite hängt an ``won`` – wie jede andere Angabe über sie.** ◄◄◄
    Wer nicht den Zuschlag hat, sieht **uns** (das steht auf jeder Rechnung, die wir
    stellen) und eine **leere** Gegenseite: der Name des Konkurrenten stünde sonst im
    Belegkopf, während er zwei Zeilen weiter oben ausgeblendet ist. Ein bestehender
    Wächter hat genau das gefunden.
    """
    flow = dm.of(row.direction)
    company = issuer_company(db, row)
    who = billing_of(db, row) if won else {}
    seat = who.get("address") or {}
    seat_ours = address.of_company(company) if company is not None else None
    ours = {
        "object_id": getattr(company, "object_id", None),
        # ►►► **Der Name trägt die Rechtsform** (Arbeitsauftrag §1.4). ◄◄◄ «Inexxio» ist
        # keine Rechtsperson, «Inexxio AG» ist eine – und auf einem Beleg steht die, die
        # haftet. Die Regel wohnt bei den Gesellschaften (``sites.legal_name``), weil sie
        # eine Aussage über ein Unternehmen ist und nicht über einen Geldvorgang.
        "name": sites.legal_name(company),
        # **Eine Adresse ohne Ort ist keine.** ``of_company`` liefert immer ein Gerüst
        # (leere Strasse wird zu «—»); ``has_content`` fragt, ob wirklich etwas drinsteht –
        # sonst stünde auf dem Beleg ein Gedankenstrich, wo eine Anschrift hingehört.
        "address": address.lines(seat_ours) if address.has_content(seat_ours) else [],
        # **Die MWST-Nummer geht vor der blossen UID** – auf dem Beleg zählt die, die den
        # Vorsteuerabzug trägt; ohne sie steht die UID immer noch besser da als nichts.
        "uid": getattr(company, "vat_number", None) or getattr(company, "uid_number", None),
        # ►►► **Ein Beleg ohne Kontaktweg ist der, der eine Rückfrage per Telefonbuch
        # auslöst.** ◄◄◄ Beides steht am Unternehmen; es fehlte allein die Zeile hier.
        "email": getattr(company, "email", None),
        "phone": getattr(company, "phone", None),
    }
    theirs = {
        "object_id": row.party_id if won else None,
        # **Firma zuerst, Person als «z. H.»** – ``billing_name`` entscheidet das an der
        # einen Stelle, an der Personennamen im Haus gebaut werden.
        "name": (who.get("lines") or [""])[0],
        "attn": (who.get("lines") or [None, None])[1] if len(
            who.get("lines") or []) > 1 else None,
        "address": address.lines(address.make(
            street1=seat.get("line1") or "", street2=seat.get("line2") or "",
            zip=seat.get("postal_code") or "", city=seat.get("city") or "",
            country=seat.get("country"),
        )) if seat else [],
        # ►►► **Die UID der Gegenpartei gibt es sehr wohl** (Arbeitsauftrag §1.1). ◄◄◄
        #
        # Hier stand «eine UID der Gegenpartei führt das System nicht» – und das war
        # schlicht falsch: ``uid_number`` und ``vat_number`` stehen seit dem Fundament im
        # Benutzer-Datensatz. Eine Angabe wegzuwerfen, die man hat, ist teurer als eine
        # zu bauen, die man nicht hat.
        #
        # **Verlangt ist sie beim Reverse Charge**: ohne die Nummer des
        # Leistungsempfängers trägt das Verfahren nicht, und die Rechnung ist angreifbar.
        # Dieselbe Rangfolge wie bei uns – MWST-Nummer vor blosser UID.
        "uid": who.get("uid"),
        "email": who.get("email"),
        "phone": who.get("phone"),
    }
    supplier, customer = (ours, theirs) if flow.collects else (theirs, ours)
    return {
        "supplier": {"label": dm.SUPPLIER, "hint": dm.SUPPLIER_HINT, **supplier},
        "customer": {"label": dm.CUSTOMER, "hint": dm.CUSTOMER_HINT, **customer},
    }


# ---------------------------------------------------------------------------
# ►► DIE GEGENPARTEI
# ---------------------------------------------------------------------------

def search_parties(db: Session, *, search: str = "",
                   limit: int = 20) -> list[UserProfile]:
    """**Wer kommt als Gegenpartei in Frage?** – gesucht, nicht als Liste geladen.

    Dieselbe Suchbedingung wie überall (``services/lookup``: Nummer **oder** Name).

    **Ohne Rollenfilter, und das ist eine Entscheidung.** Eine Rolle sagt, was jemand
    *für uns* tut – nicht, ob wir mit ihm Geld austauschen dürfen: ein Mitarbeiter kauft
    eine Schraube, ein Kunde liefert einmal etwas zu. Wer einschränken will, nennt die
    zugelassenen Gegenparteien in der **Definition**; das ist die Stelle, an der eine
    solche Freigabe hingehört, und sie gilt dann auch beim Ausführen.
    """
    return (
        db.query(UserProfile)
        .filter(UserProfile.object_id.isnot(None),
                UserProfile.is_active.is_(True),
                lookup.matches(search, UserProfile.object_id,
                               UserProfile.company_name, UserProfile.first_name,
                               UserProfile.last_name, UserProfile.email))
        .order_by(UserProfile.object_id.desc())
        .limit(limit)
        .all()
    )


def _party(db: Session, *, step: ProcessStep, value: Any,
           flow: dm.Direction) -> Optional[int]:
    """Die gewählte Gegenpartei prüfen – gegen die Freigabe und gegen die Wirklichkeit.

    **Leer heisst frei, aber nicht «irgendwer»**: wo die Definition niemanden nennt,
    muss es die Objektnummer trotzdem geben. Eine Auswahl, die der Dienst danach
    abwiese, wäre keine.
    """
    if value in (None, "", 0):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400,
                            detail=f"«{value}» ist keine Objektnummer.")
    allowed = modules.parties_allowed(step.config)
    if allowed and number not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(f"{dm.PARTY} {number} ist an diesem Modul nicht zugelassen. "
                    f"Erlaubt: " + ", ".join(str(n) for n in allowed) + "."),
        )
    found = (
        db.query(UserProfile)
        .filter(UserProfile.object_id == number, UserProfile.is_active.is_(True))
        .first()
    )
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=f"{number} ist kein Datensatz, mit dem man handeln kann.",
        )
    return number


# ---------------------------------------------------------------------------
# ►► KLEINE HELFER — jeder mit genau einer Aufgabe
# ---------------------------------------------------------------------------

def _amount(value: Any, code: str, *, allow_negative: bool = False) -> Optional[Decimal]:
    try:
        return dm.amount(value, code, allow_negative=allow_negative)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _days(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        found = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400,
                            detail=f"«{value}» ist keine Anzahl Tage.")
    if not 0 <= found <= 365:
        raise HTTPException(status_code=400,
                            detail="Eine Frist liegt zwischen 0 und 365 Tagen.")
    return found


def _assert_terms(lead: Optional[int], days: Optional[int]) -> None:
    """►►► **Ein Angebot nennt beide Fristen** (Testnotizen #854/#856). ◄◄◄

    Sie sind kein Beiwerk: aus der **Lieferfrist** kommt der Termin (``_delivery``), aus
    der **Zahlungsfrist** die Fälligkeit jeder Rechnung – und, wenn sie null ist, die
    Vorauszahlung (``dm.prepaid``). Fehlt eine, hat niemand über den Zeitpunkt gesprochen,
    und das System müsste eines erfinden.

    **Null ist ein gültiger Wert und hat einen Namen** («Sofort» · «Vorauszahlung»): eine
    Software ist sofort da, und Vorkasse ist zahlbar in null Tagen. Genau darum steht die
    Prüfung auf ``is None`` und nicht auf ``not value`` – die Null ist eine Angabe.
    """
    for value, label in ((lead, dm.LEAD_TERM_LABEL), (days, dm.PAYMENT_TERM_LABEL)):
        if value is None:
            raise HTTPException(
                status_code=400,
                detail=(f"Ohne {label} ist es kein Angebot – aus ihr folgt der Termin "
                        f"bzw. die Fälligkeit. «{dm.LEAD_TERMS[0][1]}» und "
                        f"«{dm.PAYMENT_TERMS[0][1]}» sind gültige Antworten (0 Tage)."),
            )


def _day(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"«{value}» ist kein Datum.")


def _text(value: Any, limit: int) -> Optional[str]:
    found = str(value or "").strip()
    if len(found) > limit:
        raise HTTPException(status_code=400,
                            detail=f"Der Text ist zu lang (max. {limit} Zeichen).")
    return found or None


def _due(booked: date, days: Optional[int]) -> Optional[date]:
    """Fälligkeit = Rechnungsdatum + Frist. **Ohne Frist keine Fälligkeit** – ein
    erfundenes Datum wäre schlimmer als keines."""
    return None if days is None else booked + timedelta(days=days)


def _delivery(row: Deal) -> Optional[date]:
    """**Wann er liefern wollte** – Zusagedatum + Lieferfrist der gewählten Zeile.

    Dieselbe Form wie die Fälligkeit einer Rechnung: eine Frist ist eine Vereinbarung, ein
    Datum ihre Folge. **Ohne Lieferfrist kein Termin** – ein erfundener wäre schlimmer als
    keiner, und genau daran erkennt man, dass niemand über die Zeit gesprochen hat.
    """
    if row.agreed_on is None or row.party_id is None:
        return None
    line = _quote_of(row, row.party_id) or {}
    return _due(row.agreed_on, _days_or_none(line.get("lead_days")))


def _is_late(row: Deal) -> bool:
    """**Ist der Liefertermin vorbei, obwohl noch nichts geliefert ist?**

    Kein Zustand, sondern die Frage an zwei Daten – wie ``overdue`` bei einer Forderung.
    Erledigt und storniert sind **nicht** verspätet: dort kommt nichts mehr, und ein
    Vorwurf an einen abgeschlossenen Vorgang ist keine Auskunft.
    """
    if row.stage != dm.AGREED:
        return False
    due = _delivery(row)
    return due is not None and due < date.today()


def _days_or_none(value: Any) -> Optional[int]:
    """Eine gespeicherte Tageszahl – **tolerant**, denn hier wird gelesen, nicht geprüft.
    Ein alter JSONB-Wert darf keine Anzeige zerlegen."""
    try:
        return None if value in (None, "") else int(value)
    except (TypeError, ValueError):
        return None


def _our_number(db: Session, order: Order) -> str:
    """``<Auftragsnummer>-<laufend>`` – **immer mit Suffix**, ab ``-1``.

    ►►► Dieselbe Regel wie die Nummer einer Einzelinstanz (``<Instanznr>-<Suffix>``). ◄◄◄

    Die erste hiess einmal schlicht ``100000875``, und das Suffix kam erst ab der zweiten
    dazu – eine Sonderregel für den häufigsten Fall, und man sah der ersten Nummer nicht
    an, dass sie eine von mehreren sein kann (Testnotiz #827). Jetzt trägt jede Rechnung
    ihre Position, und ein Beleg sagt ohne Nachschlagen, der wievielte er ist.

    Gezählt wird über den **Auftrag** (zwei Module in einem Auftrag vergäben sonst
    dieselbe Nummer zweimal) und **nur, was WIR nummerieren** – sonst verbraucht eine
    erfasste Lieferantenrechnung die Zählung. Auch stornierte Zeilen zählen mit: eine
    einmal vergebene Nummer wird nicht erneut vergeben.

    *Die bewusste Grenze: es gibt dafür keinen Unique-Index. Bei einem **Einkauf** steht
    dort die Nummer der Gegenpartei, und zwei Lieferanten dürfen beide eine «2026-001»
    schicken – ein Index darüber wiese eine richtige Eingabe ab.*
    """
    used = (
        db.query(func.count(DealEntry.id))
        .join(Deal, DealEntry.deal_id == Deal.id)
        .filter(Deal.order_id == order.id, Deal.direction == dm.IN,
                DealEntry.kind == dm.CHARGE)
        .scalar()
    ) or 0
    return f"{order.object_id}-{used + 1}"


# ---------------------------------------------------------------------------
# ►► DIE ANTWORT
# ---------------------------------------------------------------------------

def embed_data(db: Session, *, order: Order, step: ProcessStep,
               viewer: Optional[UserProfile] = None) -> Optional[dict[str, Any]]:
    """Der Geldvorgang, wie ihn die Ausführungsstelle braucht – oder ``None``.

    **Alles, was die Oberfläche zum Zeichnen braucht, reist mit**: Wörter, Stufen,
    Verben, Zahlen und was man tun darf. Sie fragt damit nie nach der Richtung und nie
    nach dem Modultyp.

    **Und eine Gegenpartei sieht nur ihren Teil.** Fremde Preise sind kein Nebeneffekt
    einer Ansicht: gefiltert wird hier, beim Aufbau der Antwort.

    ►►► **Wer nicht den Zuschlag hat, sieht ihn auch nicht.** ◄◄◄

    Die Angebotszeilen waren gefiltert, die **getroffene Wahl** nicht – ein angefragter,
    unterlegener Lieferant las damit Namen, Preis, Frist und Datum seines Konkurrenten
    (gemessen über die echten Dienstpfade, nicht gelesen). Und die **Freigabe-Liste** ist
    die Konkurrenzliste selbst: sie fällt für jede Nicht-Personal-Sicht ganz weg.

    Dieselbe Regel hat der Beschaffungs-Beleg längst (``purchase._embed``). Zwei Formen
    einer Regel sind in Ordnung; zwei Regeln nicht – darum steht sie hier wörtlich gleich,
    obwohl die beiden Module bewusst keine Zeile Code teilen.
    """
    row = of_step(db, step.id)
    if row is None:
        return None
    flow = dm.of(row.direction)
    entries = _entries(db, row.id)
    money = balance_of(db, row)
    #: Welche Zeilen bereits eine Gegenbuchung haben – aus derselben geladenen Liste.
    reversed_ids = {e.reverses_id for e in entries if e.reverses_id is not None}
    today = date.today()
    internal = viewer is None or viewer.role in STAFF_ROLES
    # **Den Zuschlag hat, wer zugesagt bekam** – für das Personal ist das immer wahr.
    won = internal or (row.party_id is not None and viewer is not None
                       and row.party_id == viewer.object_id)
    allowed = can(db, row, viewer)
    #: **Die eine Rechnung dieses Moduls** – die Regel aus #866, einmal gelesen.
    live = live_charge(db, row)
    #: **Was sich über den Dienst zurückgeben lässt** – dieselbe Liste, die ``can``
    #: befragt und ``card_payment`` als Tor benutzt. Eine zweite Bedingung hier wäre ein
    #: zweiter Massstab, und der bekäme die nächste Regel nicht mit.
    refund_ids = ({e.id for e in refundable(db, row)}
                  if "refund_online" in allowed else set())
    #: **Worauf man überweisen kann** – offen und uns zustehend. Die Frage ist nicht «wer
    #: darf?» (überweisen darf jeder, es ist keine Handlung an unserem Vorgang), sondern
    #: «trägt der Einzahlungsschein eine Bankverbindung, die es bei uns gibt?».
    transferable_ids = ({e.id for e in open_charges(db, row)}
                        if won and flow.collects else set())
    return {
        "direction": row.direction,
        "label": flow.label,
        # **Ein Wort für beide Richtungen** – es reist trotzdem mit, damit die Karte
        # keine eigene Konstante daneben hält.
        "party_word": dm.PARTY,
        "ask_verb": flow.ask_verb,
        # **Wer den Preis nennt, und wie die beiden Nummernfelder heissen** – lauter
        # Angaben, damit die Oberfläche die Richtung nie selbst auswertet.
        "we_quote": flow.quoted_by == dm.BY_US,
        "ref_label": flow.reference,
        # **Die Steuer-Angaben** – Katalog, Vorgabe und Wörter reisen mit, damit die Karte
        # keine zweite Liste pflegt und für kein `if` nach der Richtung fragt.
        # **Der Pflichtsatz reist mit dem Satz** – die Karte baut keinen eigenen Text und
        # führt keine zweite Liste, die beim nächsten Tatbestand jemand vergisst.
        "vat_rates": [{"key": v.key, "rate": v.rate, "label": v.label, "note": v.note}
                      for v in dm.VAT_RATES],
        # ►►► **Die Vorgabe steht im Katalog, nicht am Modul** (Testnotiz #851). ◄◄◄
        #
        # Der Satz hängt an der **Sache** (was für eine Ware ist es?) und am **Empfänger**
        # (Ausfuhr?) – beim Modellieren eines Moduls weiss man beides nicht. Ein Feld dort
        # war eine Frage, die zu früh gestellt wird, und ihre Antwort galt danach für jede
        # Position, die je durch dieses Modul lief.
        "vat_rate": dm.DEFAULT_VAT,
        "vat_label": dm.VAT_LABEL,
        "service_date_label": dm.SERVICE_DATE_LABEL,
        # *Die Vorbelegung des früheren Eingabefeldes stand hier (#852) und ist mit ihm
        # entfallen (#919): das Datum kommt aus dem Prozess und steht an der **gebuchten
        # Rechnung** – dort, wo es rechtlich zählt, und nicht dort, wo man arbeitet.*
        # ►►► **Die Lieferbedingung** (Incoterms 2020, Arbeitsauftrag §3.2). ◄◄◄
        #
        # Katalog **und** Erklärung reisen mit: genau hier entstehen die Fragen, und die
        # Karte soll den Satz nicht zum zweiten Mal formulieren. Der fertige Satz
        # («FCA Rorschach (Incoterms 2020)») kommt ebenfalls vom Server – im Browser
        # zusammengesetzt wäre er die zweite Schreibweise.
        "incoterm": row.incoterm,
        "incoterm_place": row.incoterm_place,
        "incoterm_text": inc.sentence(row.incoterm, row.incoterm_place),
        "incoterm_label": inc.LABEL,
        "incoterm_place_label": inc.PLACE_LABEL,
        "incoterm_place_hint": inc.PLACE_HINT,
        "incoterms": [{"key": t.key, "label": t.label, "hint": t.hint}
                      for t in inc.INCOTERMS],
        # ►►► **In welcher Währung?** ◄◄◄ Ein Betrag ohne sie ist keine Zahl. Sie reist
        # **mit jedem Vorgang** mit, damit die Oberfläche nirgends «CHF» annimmt – und mit
        # ihr die Nachkommastellen, denn ein Yen-Betrag mit zwei Stellen ist keiner.
        "currency": row.currency,
        "currency_label": cur.label(row.currency),
        "currency_decimals": cur.minor_units(row.currency),
        # **Änderbar, solange nichts zugesagt ist** – und das steht in ``can``, nicht in
        # einem zweiten Feld daneben: dieselbe Liste zeigt den Knopf und weist ab.
        "currencies": [{"code": c, "label": cur.label(c)} for c in cur.CURRENCIES],
        # ►►► **Wer den Beleg stellt** (Testnotiz #905) – vorgewählt, nicht geraten. ◄◄◄
        #
        # Die Nummer steht ohnehin im Belegkopf; hier steht sie als **Wahl**, damit die
        # Oberfläche sie nicht aus dem Kopf zurückrechnen muss. Die Liste gibt es nur für
        # das Personal – eine Gegenpartei wählt nicht aus, wer ihr eine Rechnung stellt,
        # und die Gesellschaften des Hauses gehen sie nichts an.
        "issuer": getattr(issuer_company(db, row), "object_id", None),
        "issuer_label": dm.ISSUER_LABEL,
        # **Wählbar, nicht alle**: eine geschlossene Gesellschaft stellt keine neuen
        # Belege mehr – sie bleibt im Feed, aber nicht in einer Auswahl.
        "issuers": [{"object_id": c.object_id, "name": sites.legal_name(c)}
                    for c in sites.selectable_companies(db)] if internal else [],
        # ►►► **Netto, Steuer und die Aufteilung – ABLEITUNGEN der Positionen.** ◄◄◄
        #
        # Der Brutto-Betrag steht längst als ``amount`` da; ihn hier zu wiederholen wäre
        # eine zweite Zahl über dieselbe Sache. Gerechnet wird **je Satz auf der Summe**
        # (``domain/deal``), damit zweimal Rechnen dasselbe ergibt – und nur für den, der
        # die Zahlen ohnehin sehen darf.
        "net": _sums(row)["net"] if won else None,
        "tax": _sums(row)["tax"] if won else None,
        "vat_split": dm.vat_split(_priced_lines(row), row.currency) if won else [],
        "payment_word": flow.payment_word,
        # **Das dritte Geld-Wort** – «erfassen» heisst aufschreiben, was geschehen ist;
        # dieses hier lässt es geschehen. Es reist mit, damit die Karte keine eigene
        # Konstante daneben hält.
        "pay_online_word": flow.pay_online_word,
        "open_word": flow.open_word,
        "money_label": flow.money_label,
        # **Das Wort der Gegenhandlung hängt an DEN HANDLUNGEN DIESES BETRACHTERS**, nicht
        # an der Stufe: sonst liest eine Gegenpartei «Auftrag stornieren» an einem Knopf,
        # den es für sie nie gibt.
        "undo": flow.undo if "revoke" in allowed else None,
        "stage": row.stage,
        "stage_label": flow.label_of(row.stage),
        "stages": _stages(row, flow),
        "can": allowed,
        # ►►► **Die Sperre ist eine ABLEITUNG der Zahlungsfrist** (Testnotiz #854). ◄◄◄
        # Sie war eine Einstellung des Moduls; jetzt sagt sie, was auf dem Angebot steht.
        "prepaid": dm.prepaid(row.due_days),
        # **Die üblichen Fristen mit ihren Namen** – «Vorauszahlung» ist ein
        # Geschäftsbegriff, «0» eine Ziffer, die man erklären muss. Sie reisen mit, damit
        # die Karte keine zweite Liste pflegt (dieselbe Bauart wie ``vat_rates``).
        "payment_terms": [{"days": d, "label": name} for d, name in dm.PAYMENT_TERMS],
        "lead_terms": [{"days": d, "label": name} for d, name in dm.LEAD_TERMS],
        "term_free_min": dm.FREE_MIN,
        "term_free_label": dm.FREE_TERM_LABEL,
        "payment_term_label": dm.PAYMENT_TERM_LABEL,
        "lead_term_label": dm.LEAD_TERM_LABEL,
        # **Wie bezahlt wurde** (#865) – die Liste dessen, was ein Mensch erfassen darf.
        # Die Karte schreibt allein der Webhook, also steht sie hier nicht.
        "methods": [{"key": k, "label": name} for k, name in dm.METHODS
                    if k in dm.MANUAL_METHODS],
        "method_label": dm.METHOD_LABEL,
        # **Die dritte Bezahlart ist eine AUSKUNFT** (#865): Bankverbindung und QR-Code
        # sagen dem Zahlenden, was er ins E-Banking tippt – gebucht wird dabei nichts.
        "transfer_word": dm.TRANSFER_WORD,
        "refund_word": dm.REFUND_WORD,
        "refund_online_word": dm.REFUND_ONLINE_WORD,
        # **Die Freigabe-Liste ist die Konkurrenzliste** – sie geht eine Gegenpartei
        # nichts an, auch nicht die, die den Zuschlag hat.
        "allowed": _named(db, modules.parties_allowed(step.config)) if internal else [],
        "quotes": _quotes(db, row, step, viewer=viewer, internal=internal),
        "lines": embed_lines(db, order, row, step=step),
        # ►►► **Der Belegkopf** – die beiden Parteien mit ihren Rollen (MWSTG Art. 26).
        #
        # **Uns** sieht jeder – ein Beleg ohne Aussteller ist keiner, und wer bezahlen
        # soll, muss wissen, an wen. Die **Gegenseite** hängt an ``won``, wie jede andere
        # Angabe über sie.
        **document_head(db, row, won=won),
        # ►►► **Was fehlt, um weiterzukommen** (Arbeitsauftrag §2). ◄◄◄
        #
        # Gefragt wird nach der **nächsten** Handlung dieser Stufe – die, deren Knopf
        # gerade fehlt. Ein Mensch soll lesen können, *warum*, statt vor einer Karte ohne
        # Angebot zu stehen.
        #
        # **Nur für das Personal**: eine Gegenpartei kann unsere Stammdaten weder sehen
        # noch pflegen, und eine Meldung über einen Datensatz, den sie nicht öffnen darf,
        # wäre eine Sackgasse mit fremder Adresse.
        "gaps": (gaps(db, row, action=_next_action(row)) if internal else []),
        "party_object_id": row.party_id if won else None,
        "party_name": (_named(db, [row.party_id])[0]["name"]
                       if row.party_id and won else None),
        "amount": _money(row.amount, row.currency) if won else None,
        "due_days": row.due_days if won else None,
        "agreed_on": row.agreed_on if won else None,
        # ►►► **Wann storniert wurde** (Testnotiz #918) – die dritte Zeile der Chronik.
        "cancelled_on": row.cancelled_on if won else None,
        # ►►► **Der Liefertermin und der Verzug — zwei ABLEITUNGEN, null Spalten.** ◄◄◄
        #
        # Ein Lieferverzug ist kein Zustand: der Termin ist *Zusagedatum + Lieferfrist der
        # gewählten Zeile*, und «verspätet» heisst *Termin vorbei und noch nicht erledigt*
        # – **exakt dieselbe Form wie ``overdue``** bei einer Forderung. Ein eigener
        # Status dafür wäre ein Wert, den jemand pflegen müsste, und der beim ersten
        # vergessenen Nachziehen lügt.
        #
        # **Was man dann tun kann, gibt es alles schon**: warten · stornieren (die Stücke
        # stehen still, ein ganz gewöhnlicher Abweichungsauftrag entscheidet über sie) ·
        # und das Geld läuft unabhängig weiter – genau darum sind ``charge`` und ``pay``
        # auch nach dem Storno erlaubt, damit eine Anzahlung erstattet werden kann.
        "due_date": _delivery(row) if won else None,
        "late": _is_late(row) if won else False,
        # ►►► **Forderung und Geld sieht, wer den Zuschlag hat.** ◄◄◄
        #
        # Es war einmal ``internal`` – also nur das Personal –, und das war richtig,
        # solange niemand ausser uns etwas mit diesen Zahlen tun konnte. **Wer bezahlen
        # soll, muss sehen, was er schuldet**: eine Aufforderung ohne Betrag ist keine.
        #
        # Ein **Leck ist es nicht**, und die Regel ist dieselbe wie bei ``amount``,
        # ``due_days`` und der Steueraufteilung: ``won`` heisst «dieser Betrachter *ist*
        # die Gegenpartei dieses Vorgangs» – die Rechnungen sind **seine**, die Zahlungen
        # sind **seine**. Ein angefragter, unterlegener Dritter sieht weiterhin nichts.
        "charged": _money(money.charged, row.currency) if won else None,
        "paid": _money(money.paid, row.currency) if won else None,
        "open": _money(money.open, row.currency) if won else None,
        "uncharged": _money(money.uncharged, row.currency) if won else None,
        # ►►► **Eine Rechnung je Modul** (Testnotiz #866) – die zweite Form derselben
        # Regel, die ``_charge`` durchsetzt: steht sie, gibt es hier nichts mehr zu
        # buchen, und der Knopf **fehlt**. Der Vorschlag fällt mit ihm weg – eine Vorgabe
        # für eine Buchung, die der Dienst abweist, wäre ein Angebot, das garantiert
        # scheitert.
        #
        # *Er hiess in der Vorrunde «Gutschrift erfassen» und öffnete eine freistehende
        # negative Forderung. Das war ein zweiter Knopf mit demselben Wort wie die
        # Gutschrift **an der Rechnung** (``reverse_word``) – und ohne deren Bezug: die
        # Zeile gehörte zu keinem Beleg und stand in der Liste als zweite Rechnung
        # (Testnotiz #874). Was #866 für eine Korrektur vorsieht, steht in seinem eigenen
        # Fehlersatz: **stornieren und neu stellen**.*
        "credit_only": bool(live) if won else False,
        "charge_word": flow.charge_word,
        "next_charge": (None if live is not None
                        else _money(money.next_charge, row.currency)) if won else None,
        "next_payment": _money(money.next_payment, row.currency) if won else None,
        "settled": money.settled if won else False,
        # ►►► **Eine Liste offener Rechnungen gibt es nicht mehr** (#859/#866). ◄◄◄
        #
        # Sie füllte ein Auswahlfeld «auf welche Rechnung geht diese Zahlung?». Seit je
        # Modul höchstens **eine** lebt und der Zahlungs-Knopf **an ihrer Zeile** steht,
        # nennt er sie – statt danach zu fragen. Was auf einer Rechnung offen ist, steht
        # an ihr (``entries[].open``).
        "entries": [
            {
                "id": e.id, "kind": e.kind, "amount": _money(e.amount, row.currency),
                "booked_on": e.booked_on, "due_on": e.due_on,
                "reference": e.reference, "note": e.note,
                # **Überfällig ist eine Ableitung, kein Zustand**: eine Forderung, deren
                # Tag vorbei ist, solange überhaupt noch etwas offen ist.
                "overdue": bool(e.kind == dm.CHARGE and e.due_on and e.due_on < today
                                and money.open > 0),
                # **Die beiden Richtungen derselben Angabe** – gerechnet aus derselben
                # Liste, die ohnehin geladen ist: welche Zeile diese hier storniert, und
                # ob sie selbst storniert wurde. Im Browser müsste die zweite über die
                # ganze Liste gesucht werden, und der Server weiss es längst.
                "reverses": e.reverses_id,
                "reversed": e.id in reversed_ids,
                # ►►► **Worauf diese Zahlung geht** (Testnotiz #858). ◄◄◄ Nur die Id –
                # die Nummer steht an der Rechnung, und die Karte hat die ganze Liste.
                # Sie ein zweites Mal mitzuschicken wäre dieselbe Angabe doppelt.
                "charge_id": e.charge_id,
                "vat": list(e.vat or []),
                "service_date": e.service_date,
                # ►►► **Wie bezahlt wurde** (Testnotiz #865) – Schlüssel und Wort aus
                # **einer** Auflösung. ``None`` heisst «nicht festgehalten», nicht «bar»:
                # so steht jede Zahlung da, die es vor dieser Angabe schon gab.
                "method": e.method,
                "method_label": dm.method_name(e.method),
                # ►►► **Storno ODER Gutschrift — dieselbe Zeile, zwei Lagen** (#860). ◄◄◄
                # *«Wenn bezahlt wurde, dann kann ich ja quasi nicht mehr stornieren»* –
                # richtig, dann heisst es **Gutschrift**, und danach folgt die Erstattung.
                # Welches Wort gilt, hängt an der Zahl, nicht an einem zweiten Verb.
                "reverse_word": (dm.reverse_word(_paid_on(entries, e))
                                 if e.kind == dm.CHARGE else None),
                # **Was auf DIESER Rechnung noch offen ist** – die Gruppe darunter zeigt
                # ihre Zahlungen, und die Zahl daneben sagt, was davon fehlt.
                "open": (_money(_open_of(entries, e), row.currency)
                         if e.kind == dm.CHARGE else None),
                # **Zurückgeben kann man, was über die Karte kam** – bar und Überweisung
                # sind eine gewöhnliche negative Zahlung, und die gibt es längst.
                "refundable": e.id in refund_ids,
                # **Überweisen kann man auf eine offene Rechnung, die UNS zusteht** – der
                # Einzahlungsschein trägt unsere Bankverbindung.
                "transferable": e.id in transferable_ids,
            }
            # **Dieselbe Frage, dieselbe Antwort**: die Zeilen gehören dem, der den
            # Zuschlag hat – seine Rechnungen, seine Zahlungen. Er sieht sie, ein
            # unterlegener Dritter nicht.
            for e in (entries if won else [])
        ],
    }


def _priced_lines(row: Deal) -> list[dict[str, Any]]:
    """Die zugesagten Positionen, **soweit sie einen Preis tragen** – die eine Lesestelle.

    Ohne Preis gibt es nichts aufzuteilen: bei einer **Ausgabe** steht die Steuer auf
    *seiner* Rechnung, und eine hier erfundene wäre eine Behauptung über ein fremdes
    Dokument.
    """
    return [ln for ln in (row.agreed_lines or []) if ln.get("price") is not None]


def _sums(row: Deal) -> dict[str, str]:
    """Netto · Steuer · Brutto der Zusage – drei Zahlen aus einer Quelle."""
    return dm.totals(dm.vat_split(_priced_lines(row), row.currency), row.currency)


def _quotes(db: Session, row: Deal, step: ProcessStep, *,
            viewer: Optional[UserProfile], internal: bool) -> list[dict[str, Any]]:
    """Der Angebotsspiegel – **für die Gegenpartei nur ihre eigene Zeile**.

    Wer nicht den Zuschlag hat, sieht weder Namen noch Preis der übrigen: gefiltert wird
    beim Aufbau der Antwort, nicht in der Oberfläche.

    **Die Bestellangabe reist mit ihrer Zeile** (``config.parties[].ref``): sie sagt, wie
    man bei genau diesem hier bestellt, und steht darum bei ihm – nicht als eine Angabe am
    Beleg, die man bei jedem Vorgang neu abschreibt.
    """
    lines = [dict(q) for q in (row.quotes or [])]
    if not internal:
        own = viewer.object_id if viewer else None
        lines = [q for q in lines if q.get("party") == own]
    names = {n["object_id"]: n["name"]
             for n in _named(db, [q.get("party") for q in lines])}
    refs = {r[modules.Zahlung.PARTY]: r[modules.Zahlung.REF]
            for r in modules.parties_of(step.config)}
    return [
        {
            "party_object_id": q.get("party"),
            "party_name": names.get(q.get("party"), ""),
            "ref": refs.get(q.get("party"), ""),
            "amount": q.get("amount"),
            "lead_days": q.get("lead_days"),
            "payment_days": q.get("payment_days"),
            "state": q.get("state") or dm.ASKED,
            # **Die Positionen dieser Offerte** – nur, wo wir den Preis genannt haben.
            # Dort ist der Betrag ihre Brutto-Summe, keine zweite getippte Zahl.
            "lines": [dict(x) for x in (q.get("lines") or [])],
        }
        for q in lines
    ]


def _stages(row: Deal, flow: dm.Direction) -> list[dict[str, Any]]:
    """Die **zwei** Stufen mit Beschriftung, Verb und Zustand.

    **Ein Storno ist keine Stufe**, und «erledigt» auch nicht: keine ist dann aktiv, kein
    Verb wird angeboten – die gegangene Kette bleibt aber stehen, wo sie stand. Eine
    Fassung, die bei «storniert» alles grau setzt, liesse einen stornierten Vorgang
    aussehen wie einen, bei dem nie etwas geschehen ist.
    """
    order = list(dm.STAGES)
    # Storniert und erledigt wird erst ab der Zusage – so weit war er also.
    reached = (order.index(row.stage) if row.stage in order
               else order.index(dm.AGREED) + (1 if row.stage == dm.DONE else 0))
    return [
        {
            "key": key,
            "label": flow.label_of(key),
            "verb": flow.stage_verbs.get(key),
            "done": i < reached,
            "active": row.stage in order and i == reached,
        }
        for i, key in enumerate(order)
    ]


def _named(db: Session, numbers: list[Optional[int]]) -> list[dict[str, Any]]:
    """Objektnummern auf ihren Anzeigenamen – **eine** Abfrage, nicht eine je Zeile."""
    wanted = [n for n in numbers if n]
    if not wanted:
        return []
    rows = {
        u.object_id: u.display_name
        for u in db.query(UserProfile).filter(UserProfile.object_id.in_(wanted)).all()
    }
    return [{"object_id": n, "name": rows.get(n, str(n))} for n in wanted]


def _money(value: Optional[Decimal], code: str) -> Optional[str]:
    """Beträge reisen als **String**, in der Genauigkeit ihrer Währung.

    Wo es auf den Rappen ankommt, wird nicht durch ``float`` gerechnet – auch nicht auf
    dem Weg durch JSON. Und die Stellenzahl gehört der Währung: ``1000.00`` in Yen
    behauptet eine Genauigkeit, die es nicht gibt (``domain/currency.money``)."""
    return None if value is None else cur.money(value, code)


# ---------------------------------------------------------------------------
# ►► DIE VERTEILUNG — eine Zuordnung, damit «gibt es dieses Verb?» eine Frage ist
# ---------------------------------------------------------------------------
#
# Sie steht am Ende, weil sie die Funktionen darüber nennt, und als **Konstante**, weil
# sie eine Aussage ist: das sind die Handlungen dieses Moduls, und es gibt keine weiteren.
# Ein Löschweg (früher ``void``) ist damit nicht «nicht mehr aufgerufen», sondern schlicht
# nicht vorhanden – und ein Wächter kann es lesen, statt es zu glauben.
HANDLERS = {
    "currency": _currency,
    "issuer": _issuer,
    "incoterm": _incoterm,
    "ask": _ask, "quote": _quote, "decline": _decline, "agree": _agree,
    "revoke": _revoke,
    "charge": _charge, "pay": _pay, REVERSE: _reverse,
}
# ►►► **``pay_online`` und ``refund_online`` stehen bewusst NICHT darin.** ◄◄◄
#
# Sie ändern den Vorgang nicht: die eine **löst** eine Zahlung aus, die andere gibt sie
# zurück – gebucht wird beides erst, wenn der Zahlungsdienst es meldet. Sie haben darum
# ihren eigenen Weg (``…/deal/payment``, ``…/deal/refund``) und trotzdem dieselbe Tür
# (``assert_allowed``): ``can`` ist Auskunft **und** Tor, nicht zwei Massstäbe.
