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

from ..domain import deal as dm
from ..domain import modules
from ..models import (
    Article, Deal, DealEntry, Instance, InstanceUnit, Order, OrderUnit, ProcessStep,
    UserProfile,
)
from . import article_fields, lookup

#: **Wer ohnehin alles sieht.** Für sie gibt es keine verengte Sicht – sie arbeiten im
#: ERP, und dort steht der ganze Auftrag.
STAFF_ROLES: tuple[str, ...] = ("admin", "employee")

#: ►►► **Was an welcher Stufe erlaubt ist — Auskunft UND Tor.** ◄◄◄
#:
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
ACTIONS: dict[str, tuple[str, ...]] = {
    dm.OFFER: ("ask", "quote", "decline", "agree"),
    dm.AGREED: ("revoke", "charge", "pay"),
    dm.DONE: ("charge", "pay"),
    dm.CANCELLED: ("charge", "pay"),
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


def embed_lines(db: Session, order: Order, row: Deal) -> list[dict[str, Any]]:
    """Die Zeilen **mit Namen und Spezifikation** – das, was die Gegenpartei liest.

    Die Spezifikation **reist mit**, sie wird nicht ausgewählt (``article_fields``): eine
    Spezifikation, die je nach Empfänger anders lautet, ist keine. Sie beschreibt die
    Sache; **was daran zu tun ist**, steht bei dem Partner, den es betrifft
    (``config.parties[].ref``).

    Eine Abfrage für alle Zeilen, nicht eine je Zeile.
    """
    lines = lines_of(db, order, row)
    found = {
        a.id: a
        for a in db.query(Article).filter(
            Article.id.in_([int(line["article"]) for line in lines])).all()
    } if lines else {}
    out: list[dict[str, Any]] = []
    for line in lines:
        art = found.get(int(line["article"]))
        out.append({
            "article_id": int(line["article"]),
            "article_object_id": art.object_id if art else None,
            "article_name": art.name if art else "",
            "quantity": int(line["quantity"]),
            "spec": article_fields.specification(art),
        })
    return out


# ---------------------------------------------------------------------------
# ►► ANLAGE — mit der Freigabe, idempotent
# ---------------------------------------------------------------------------

def instantiate_for_order(db: Session, order: Order) -> None:
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
    return stage


def _assert_allowed(db: Session, row: Deal, action: str,
                    viewer: Optional[UserProfile]) -> None:
    if action not in can(db, row, viewer):
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
    _assert_allowed(db, row, action, actor)
    HANDLERS[action](db, order=order, step=step, row=row, data=payload, actor=actor)
    db.flush()
    return row


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
    offered = _amount(data.get("amount"))
    if flow.quoted_by == dm.BY_US and offered is None:
        raise HTTPException(
            status_code=400,
            detail=(f"Ohne Betrag gibt es nichts anzubieten – bei einer {flow.label} "
                    f"nennen wir den Preis, nicht der {dm.PARTY}."),
        )
    fresh = ({"amount": f"{offered:.2f}", "state": dm.QUOTED}
             if offered is not None else {"amount": None, "state": dm.ASKED})
    lines = list(row.quotes or [])
    for value in wanted:
        number = _party(db, step=step, value=value, flow=flow)
        if number is None or any(q.get("party") == number for q in lines):
            continue
        lines.append({"party": number, "lead_days": _days(data.get("lead_days")),
                      "payment_days": _days(data.get("payment_days")), **fresh})
    _write_quotes(row, lines)


def _quote(db: Session, *, order: Order, step: ProcessStep, row: Deal,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Einen Preis an **einer** Angebotszeile eintragen.

    **Wer eintragen darf, entscheidet nicht die Nutzlast**: eine Gegenpartei trifft
    ausschliesslich ihre eigene Zeile (``_target`` liest ``actor.object_id``). Wer sie
    erst an der Tür formulierte, hätte die Regel beim zweiten Aufrufer nicht.
    """
    party = _target(row, data, actor)
    amount = _amount(data.get("amount"))
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
    changes: dict[str, Any] = {"amount": f"{amount:.2f}", "state": dm.QUOTED}
    for field in ("lead_days", "payment_days"):
        if field in data:
            changes[field] = _days(data.get(field))
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

    **Und hier frieren die Zeilen ein**: was zugesagt wurde, ändert sich nicht mehr
    dadurch, dass der Auftrag später Stücke verliert.
    """
    flow = dm.of(row.direction)
    party = _target(row, data, actor)
    line = _quote_of(row, party) or {}
    amount = _amount(data.get("amount")) if data.get("amount") is not None \
        else _amount(line.get("amount"))
    if amount is None:
        raise HTTPException(
            status_code=400,
            detail=(f"{dm.PARTY} {party} hat keinen Preis genannt – ohne Betrag "
                    f"gibt es keine Zusage. (0.00 ist erlaubt und heisst «kostenlos».)"),
        )
    _patch_quote(row, party, {"state": dm.CHOSEN})
    row.party_id = party
    row.amount = amount
    row.due_days = _days(data.get("payment_days")) or _days(line.get("payment_days"))
    row.stage = dm.AGREED
    row.agreed_on = date.today()
    row.agreed_lines = lines_of(db, order, row)


def _revoke(db: Session, *, order: Order, step: ProcessStep, row: Deal,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Stornieren – und der Vorgang **behält seinen Weg**.

    Ein Storno macht die Zusage nicht ungeschehen, er sagt nur, dass nichts mehr kommt.
    Die gegangenen Stufen bleiben darum stehen; das Geld darf weiterhin fliessen, denn
    eine Anzahlung muss erstattet werden können.
    """
    row.stage = dm.CANCELLED


def _charge(db: Session, *, order: Order, step: ProcessStep, row: Deal,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Eine **Forderung** buchen. Negativ ist die Gutschrift.

    **Die Automatik steckt in den Vorgaben, nicht in einem Modus**: Betrag = *zugesagt −
    berechnet* (nie negativ, ``Balance.next_charge``), Fälligkeit = *heute + Frist*,
    Nummer = ``<Auftragsnummer>-<laufend>``, wo wir nummerieren.
    """
    flow = dm.of(row.direction)
    given = _amount(data.get("amount"), allow_negative=True)
    value = given if given is not None else balance_of(db, row).next_charge
    if value is None:
        raise HTTPException(status_code=400, detail="Ohne Betrag keine Rechnung.")
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
    number = (_our_number(db, order) if flow.charge_reference is None
              else _text(data.get("reference"), 120))
    db.add(DealEntry(
        deal_id=row.id, kind=dm.CHARGE, amount=value, booked_on=booked,
        due_on=_day(data.get("due_on")) or _due(booked, row.due_days),
        reference=number, note=_text(data.get("note"), 200),
    ))


def _pay(db: Session, *, order: Order, step: ProcessStep, row: Deal,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Eine **Zahlung** buchen. Negativ ist die Erstattung.

    Vorgabe ist der **offene** Betrag, und auch er nie negativ: ist mehr gezahlt als
    gefordert, gibt es nichts vorzuschlagen – die Erstattung tippt ein Mensch.
    """
    given = _amount(data.get("amount"), allow_negative=True)
    value = given if given is not None else balance_of(db, row).next_payment
    if value is None:
        raise HTTPException(status_code=400, detail="Ohne Betrag keine Zahlung.")
    db.add(DealEntry(
        deal_id=row.id, kind=dm.PAYMENT, amount=value,
        booked_on=_day(data.get("booked_on")) or date.today(),
        reference=_text(data.get("reference"), 120),
        note=_text(data.get("note"), 200),
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
        reference=(_our_number(db, order) if flow.charge_reference is None else None),
        note=f"Storno zu {entry.reference}" if entry.reference else "Storno",
        reverses_id=entry.id,
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
    if not modules.prepaid(step.config):
        return
    money = balance_of(db, row)
    if not money.settled:
        raise HTTPException(
            status_code=409,
            detail=(f"«{flow.label}» wartet auf den Zahlungseingang: "
                    f"{money.paid} von {money.agreed} bezahlt. So ist dieses Modul "
                    f"eingestellt – erst das Geld, dann weiter."),
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

def _amount(value: Any, *, allow_negative: bool = False) -> Optional[Decimal]:
    try:
        return dm.amount(value, allow_negative=allow_negative)
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
        "charge_ref_label": flow.charge_reference,
        "payment_ref_label": dm.PAYMENT_REFERENCE,
        "charge_word": flow.charge_word,
        "payment_word": flow.payment_word,
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
        "prepaid": modules.prepaid(step.config),
        # **Die Freigabe-Liste ist die Konkurrenzliste** – sie geht eine Gegenpartei
        # nichts an, auch nicht die, die den Zuschlag hat.
        "allowed": _named(db, modules.parties_allowed(step.config)) if internal else [],
        "quotes": _quotes(db, row, step, viewer=viewer, internal=internal),
        "lines": embed_lines(db, order, row),
        "party_object_id": row.party_id if won else None,
        "party_name": (_named(db, [row.party_id])[0]["name"]
                       if row.party_id and won else None),
        "amount": _money(row.amount) if won else None,
        "due_days": row.due_days if won else None,
        "agreed_on": row.agreed_on if won else None,
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
        # ►► **Forderung und Geld sieht nur das Personal.** Was ein Kunde uns schuldet,
        #    geht einen angefragten Dritten nichts an.
        "charged": _money(money.charged) if internal else None,
        "paid": _money(money.paid) if internal else None,
        "open": _money(money.open) if internal else None,
        "uncharged": _money(money.uncharged) if internal else None,
        "next_charge": _money(money.next_charge) if internal else None,
        "next_payment": _money(money.next_payment) if internal else None,
        "settled": money.settled if internal else False,
        "entries": [
            {
                "id": e.id, "kind": e.kind, "amount": _money(e.amount),
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
            }
            for e in (entries if internal else [])
        ],
    }


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


def _money(value: Optional[Decimal]) -> Optional[str]:
    """Beträge reisen als **String**. Wo es auf den Rappen ankommt, wird nicht durch
    ``float`` gerechnet – auch nicht auf dem Weg durch JSON."""
    return None if value is None else f"{value:.2f}"


# ---------------------------------------------------------------------------
# ►► DIE VERTEILUNG — eine Zuordnung, damit «gibt es dieses Verb?» eine Frage ist
# ---------------------------------------------------------------------------
#
# Sie steht am Ende, weil sie die Funktionen darüber nennt, und als **Konstante**, weil
# sie eine Aussage ist: das sind die Handlungen dieses Moduls, und es gibt keine weiteren.
# Ein Löschweg (früher ``void``) ist damit nicht «nicht mehr aufgerufen», sondern schlicht
# nicht vorhanden – und ein Wächter kann es lesen, statt es zu glauben.
HANDLERS = {
    "ask": _ask, "quote": _quote, "decline": _decline, "agree": _agree,
    "revoke": _revoke,
    "charge": _charge, "pay": _pay, REVERSE: _reverse,
}
