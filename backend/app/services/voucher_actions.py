"""►►► **Die Handlungen am Beleg** – jedes Verb EINMAL (``VERBS``), ``can`` als Auskunft
und Tor (``assert_allowed``), ``apply`` als die eine Tür. ◄◄◄

Was ein Verb an Stammdaten braucht, steht in ``REQUIRED_FOR`` (``gaps``); die Eingabe-Leser
(``_int`` · ``amount_of`` · ``_days`` · ``_day`` · ``_text``) stehen hier, weil nur Handlungen
lesen, was hereinkommt.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import clock
from ..core.config import payment_service_ready
from ..domain import currency as cur
from ..domain import incoterms as inc
from ..domain import modules
from ..domain import voucher as vo
from ..models import (
    Order, OrderUnit, ProcessStep,
    UserProfile, Voucher, VoucherEntry, VoucherQuote,
)
from . import address_book, sites
# Wer ohnehin alles sieht – Personal hat keine verengte Sicht (die eine Stelle).
from .people import STAFF_ROLES
from .voucher import (
    addressee_of, agreed_amount, balance_of, changed_since_offer, days_after, deviation,
    documents_of, due_days_of, entries_of, expired, fingerprint, hold, inbound,
    is_billed, lines_of, minus, next_reminder, of_step, ownership_of, parties_on,
    party_of, priced_dicts, quotes_of, service_day, units_problem, where_of,
)
from .voucher_head import (
    account_for, business_possible, destination, document_head, embed_lines,
    fit_to_address, freeze, has_goods, incoterm_place_of, is_export, issuer_company,
    services_of, sync_lines,
)
from .voucher_money import (
    AUTO_RELEASE, book, follow_up, papers_due, refundable,
)


# ---------------------------------------------------------------------------
# ►►► DIE VERBEN — EINE Deklaration je Verb ◄◄◄
# ---------------------------------------------------------------------------
#
# Die vier Fragen über ein Verb stehen in **einer Zeile** («eine Sache, eine Stelle»):
#
# ``stages``  in welchen Stufen ist es erlaubt?
# ``needs``   welche Stammdaten müssen dafür da sein? (kumulativ, siehe ``REQUIRED_FOR``)
# ``party``   darf die **Gegenpartei** es? – und zwar als Regel, nicht als Liste je
#             Richtung: «wer den Preis empfängt, nimmt an oder lehnt ab».
# ``run``     welche Funktion führt es aus? ``None`` = eigener Weg (``pay_online``
#             **löst** eine Zahlung aus und bucht nichts – gebucht wird, wenn der
#             Zahlungsdienst es meldet).

#: Wer die Gegenpartei sein darf – vier Regeln, keine Liste je Richtung.
NEVER = "never"
ALWAYS = "always"
#: Nur, wo **sie** den Preis nennt (Ausgabe): dann offeriert sie.
IF_THEY_PRICE = "they"
#: Nur, wo **wir** ihn nennen (Einnahme): dann nimmt sie an. Unseren Preis zu
#: überschreiben wäre keine Antwort, sondern eine Gegenofferte – und die ist ein neuer
#: Beleg.
IF_WE_PRICE = "we"


@dataclass(frozen=True)
class Verb:
    """**Eine Handlung am Beleg** – alles über sie in einer Zeile."""

    stages: tuple[str, ...]
    run: Optional[Callable[..., None]] = None
    needs: tuple[str, ...] = ()
    party: str = NEVER

    def allows(self, flow: vo.Direction) -> bool:
        """Darf die **Gegenpartei** dieses Verb – bei dieser Richtung?"""
        if self.party == ALWAYS:
            return True
        if self.party == IF_THEY_PRICE:
            return flow.quoted_by == vo.BY_PARTY
        if self.party == IF_WE_PRICE:
            return flow.quoted_by == vo.BY_US
        return False


# ---------------------------------------------------------------------------
# ►►► WAS DIESES MODUL AN STAMMDATEN BRAUCHT ◄◄◄
# ---------------------------------------------------------------------------
#
# **``StepNeed`` für Stammdaten**: je Lücke eine Zeile (wo · was · warum), kein Zustand.
# Durchgesetzt über ``can`` (der Knopf fehlt) und ``assert_allowed`` (dieselbe Liste).
# **Gestaffelt und kumulativ**: eine Anfrage braucht weniger als eine Rechnung.
#
# ``(seite, feld, beschriftung, grund)`` – ``seite`` ist ``us`` oder ``party``.
REQUIRED_FOR: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "ask": (
        ("us", "name", "Firma und Rechtsform",
         "Ein Beleg nennt die Rechtsperson, die ihn stellt."),
        ("us", "address", "Anschrift",
         "Ohne Sitz ist der Aussteller nicht bestimmbar."),
        ("us", "contact", "E-Mail oder Telefon",
         "Ohne Kontaktweg landet jede Rückfrage im Telefonbuch."),
    ),
    # **Die Gegenpartei steht erst mit der ZUSAGE fest.** Beim Anfragen ist sie noch nicht
    # gewählt, und das ist der Sinn der Stufe: man fragt mehrere.
    "agree": (
        ("party", "name", "Name",
         "Ein Beleg braucht einen Adressaten."),
        ("party", "address", "Anschrift",
         "Eine Zusage bindet eine Rechtsperson – die braucht einen Sitz."),
        ("us", "uid", "UID / MWST-Nummer",
         "Ohne sie kann dem Empfänger der Vorsteuerabzug verweigert werden "
         "(MWSTG Art. 26)."),
    ),
    "bill": (
        ("us", "iban", "IBAN",
         "Auf eine Rechnung gehört, wohin überwiesen wird."),
        ("party", "uid", "UID / MWST-Nummer",
         "Beim Reverse Charge schuldet der Leistungsempfänger die Steuer – ohne seine "
         "Nummer trägt das Verfahren nicht."),
    ),
}


def ownership_problem(row: Voucher) -> Optional[str]:
    """►►► **Ohne Wahl des Eigentums geht kein Beleg hinaus und keiner wird zugesagt.** ◄◄◄
    Zwei Formen einer Regel: dieser Satz am gesperrten Knopf, ``_assert_ownership_chosen``
    als Tor."""
    if ownership_of(row) is None:
        return (f"Ohne Wahl beim {vo.OWNERSHIP_LABEL} ist offen, wem die Stücke danach "
                f"gehören – «" + "» oder «".join(l for _, l in vo.OWNERSHIP) + "».")
    return None


def _assert_ownership_chosen(row: Voucher) -> None:
    problem = ownership_problem(row)
    if problem:
        raise HTTPException(status_code=400, detail=problem)


def _has(side: dict[str, Any], field: str) -> bool:
    """Steht diese Angabe wirklich da? **Leer ist nicht vorhanden.**"""
    if field == "contact":
        return bool(side.get("email") or side.get("phone"))
    return bool(side.get(field))


def gaps(db: Session, row: Voucher, *, action: str,
         party_id: Optional[int] = None) -> list[dict[str, Any]]:
    """►►► **Welche Angaben fehlen, um DIESE Handlung zu tun?** ◄◄◄

    Je Lücke eine Zeile mit dem **Datensatz** (klickbar), dem **Feld** und einem Satz, der
    sagt, **warum dieser Beleg sie braucht**. Was daraus folgt, entscheidet ein Mensch –
    wie bei ``StepNeed``: hingehen und eintragen.

    **Gestaffelt und kumulativ** (``Verb.needs``): ``charge`` verlangt auch, was ``ask``
    und ``agree`` verlangen. Eine Rechnung ohne Adressaten gibt es nicht, nur weil man
    schon zugesagt hat.

    **Zwei Sonderfälle, beide benannt:** die **IBAN** verlangt nur, wer einzieht (auf
    einer Lieferantenrechnung steht *seine* Bankverbindung); die **UID des Empfängers**
    verlangt nur ein Beleg, der *Reverse Charge* trägt – im Inland ist sie nicht
    vorgeschrieben, und ein Pflichtfeld, das meistens leer bleiben darf, ist keines.
    """
    # **Geprüft wird die Partei, um die es GEHT.** Beim Zuschlag steht sie in der
    # Nutzlast, nicht am Beleg – die Zusage prüfte sich sonst gegen eine leere Gegenseite
    # und wäre nie möglich. Und wo noch gar keine feststeht, wird die Gegenseite nicht
    # geprüft: beim Anfragen gibt es sie noch nicht, und der Knopf muss trotzdem da sein.
    look = party_id if party_id is not None else party_of(db, row)
    head = document_head(db, row, won=True, party_id=look)
    flow = vo.of(row.direction)
    us, party = ((head["supplier"], head["customer"]) if flow.collects
                 else (head["customer"], head["supplier"]))
    sides = {"us": us, "party": party}
    known = look is not None
    # **Reverse Charge steht an der POSITION** – und nur eine gebuchte Zeile verlangt die
    # Nummer; vor der Zusage gibt es noch nichts, wofür sie zählte.
    reverse = any(ln.vat == "reverse" for ln in lines_of(db, row))
    out: list[dict[str, Any]] = []
    for stage in VERBS[action].needs if action in VERBS else ():
        for side, field, label, why in REQUIRED_FOR[stage]:
            if field == "iban" and not flow.collects:
                continue
            if side == "party" and not known:
                continue
            if field == "uid" and side == "party" and not reverse:
                continue
            if field == "iban":
                # **Die IBAN der Gesellschaft, die den Beleg stellt** – nicht die des
                # Betreibers: überwiesen wird an den Aussteller.
                if getattr(issuer_company(db, row), "iban", None):
                    continue
                out.append(_gap(sides["us"], label, why))
                continue
            if not _has(sides[side], field):
                out.append(_gap(sides[side], label, why))
    return out


def next_action(row: Voucher) -> str:
    """**Welche Handlung steht an dieser Stufe an?** – die, deren Lücken zählen.

    Eine Liste aller Lücken über alle Stufen wäre eine Mängelliste statt einer Auskunft:
    sie nennte Angaben, die erst in drei Schritten gebraucht werden, und niemand wüsste,
    welche gerade im Weg steht.
    """
    return "bill" if row.stage != vo.OFFER else "ask"


def _gap(side: dict[str, Any], label: str, why: str) -> dict[str, Any]:
    """Eine Lücke als Zeile – **wo** sie hingehört, **was** fehlt, **warum**."""
    return {
        "record_object_id": side.get("object_id"),
        "record_label": side.get("name") or side.get("label") or "",
        "field_label": label,
        "why": why,
    }


def can(db: Session, row: Voucher, viewer: Optional[UserProfile]) -> list[str]:
    """►►► **Was darf DIESER Betrachter an DIESEM Beleg tun?** ◄◄◄

    Stufe **mal** Lage **mal** Rolle **mal** Vollständigkeit, an einer Stelle – dieselbe
    Antwort reist mit (``can`` im Embed) und weist in ``assert_allowed`` ab. **Auskunft und
    Tor**, nie zwei Massstäbe.
    """
    flow = vo.of(row.direction)
    out = [k for k, v in VERBS.items() if row.stage in v.stages]
    order, step = where_of(db, row)
    # ►►► **Passen die Stücke nicht mehr, bleibt nur «Stornieren»** – in jeder Stufe. ◄◄◄
    if order is not None and step is not None and units_problem(db, row, order, step):
        out = [a for a in out if a == "revoke"]
    money = balance_of(db, row)
    quotes = quotes_of(db, row)
    billed = is_billed(row)
    drop: set[str] = set()
    if row.stage == vo.OFFER:
        if not quotes:
            drop |= {"revoke", "decline"}
        if not (quotes or parties_on(row)):
            drop.add("unask")
        # **Annehmen geht nur, solange die Offerte gilt** – und nur die aktuelle Fassung.
        if expired(db, row) or changed_since_offer(db, row) \
                or not any(q.state in (vo.QUOTED, vo.CHOSEN) for q in quotes):
            drop.add("agree")
        # **Einen fremden Preis erfasst nur, wo die Gegenpartei ihn nennt.**
        if flow.quoted_by == vo.BY_US or not quotes:
            drop.add("quote")
        # **Fremdwährung nur ins Ausland** – wo wir den Preis nennen.
        if flow.quoted_by == vo.BY_US and not vo.abroad(destination(db, row)[0]):
            drop.add("currency")
    if not billed:
        drop |= {"pay", "pay_online", "writeoff", "tip", "remind", "export", "accept"}
    if deviation(db, row) is None:
        drop.add("accept")
    else:
        # **Bezahlt wird erst nach dem Entscheid über die Abweichung.**
        drop |= {"pay", "pay_online", "writeoff", "tip"}
    if money.open <= vo.SETTLED_TOLERANCE:
        drop |= {"pay", "pay_online", "writeoff"}
    if money.open >= -vo.SETTLED_TOLERANCE:
        drop |= {"refund", "tip"}
    if not (flow.collects and not minus(row)):
        drop.add("tip")
    if row.stage == vo.CANCELLED:
        drop |= {"writeoff", "tip", "remind", "export"}
    nxt = next_reminder(db, row)
    if nxt is None or nxt[1] > clock.today():
        drop.add("remind")
    if not (billed and is_export(db, row) and not row.export_number):
        drop.add("export")
    if not reversible(db, row):
        drop.add("reverse")
    if not papers_due(db, row):
        drop.add("release")
    # ►►► **Online bezahlen**: nur wo das Geld **zu uns** fliesst, mit eingerichtetem
    # Dienst und offenem Betrag. **Zurück auf die Karte** nur, wo eine Karten-Zahlung
    # dasteht, die man zurückgeben kann.
    if not (inbound(row) and payment_service_ready()):
        drop.add("pay_online")
    # **Wer schuldet zurück?** An einer Gutschrift ist ihr offener Betrag, was wir
    # erstatten; an einer Rechnung das Zuviel.
    owe_back = (money.open > vo.SETTLED_TOLERANCE if minus(row)
                else money.open < -vo.SETTLED_TOLERANCE)
    if not (owe_back and payment_service_ready() and refundable(db, row)):
        drop.add("refund_online")
    # **Was Angaben braucht, die es nicht gibt, steht hier nicht – für jede Rolle.** Die
    # Lücken speisen ``can``; die Vollständigkeit ist damit keine zweite Regel.
    out = [a for a in out if a not in drop
           and not (VERBS[a].needs and gaps(db, row, action=a))]
    if viewer is not None and viewer.role not in STAFF_ROLES:
        # Die Gegenpartei darf nur, was ihre Rolle im Beleg hergibt – und nur, solange sie
        # tatsächlich angefragt ist.
        if not any(q.party_id == viewer.object_id for q in quotes):
            return []
        return [a for a in out if VERBS[a].allows(flow)]
    return out


def reversible(db: Session, row: Voucher) -> list[VoucherEntry]:
    """►►► **Welche Geld-Zeilen sich als «falsch erfasst» gegenbuchen lassen.** ◄◄◄ Von Hand
    erfasste (eine Karten-Zeile meldet der Dienst – sie geht über «zurück auf die Karte»),
    die nicht selbst eine Gegenbuchung sind und noch nicht gegengebucht wurden."""
    rows = entries_of(db, row)
    undone = {e.reverses_id for e in rows if e.reverses_id is not None}
    return [e for e in rows if e.reverses_id is None and e.id not in undone
            and e.method != vo.CARD]


def assert_allowed(db: Session, row: Voucher, action: str,
                   viewer: Optional[UserProfile],
                   party_id: Optional[int] = None) -> None:
    """►►► **Das Tor zu ``can`` – zwei Formen einer Regel, ein Namensstamm.** ◄◄◄

    Sie liest **dieselbe** Liste, auf dem gesperrten Beleg (``hold``). Nennt die Nutzlast
    die Partei (Zuschlag), gelten zusätzlich deren Lücken – ``can`` kennt sie noch nicht.
    Öffentlich, weil nicht jedes Verb durch ``apply`` läuft (Karte, Erstattung).
    """
    hold(db, row)
    needs = action in VERBS and bool(VERBS[action].needs)
    allowed = action in can(db, row, viewer)
    # **Zwei Gründe, zwei Handlungen**: eine fehlende Angabe (hingehen und eintragen) und
    # die Stufe bzw. der Zugang (siehe unten).
    missing = (gaps(db, row, action=action, party_id=party_id)
               if needs and (party_id is not None or not allowed) else [])
    if allowed and not missing:
        return
    if missing:
        first = missing[0]
        raise HTTPException(
            status_code=400,
            detail=(f"Dafür fehlt {first['field_label']} bei «{first['record_label']}». "
                    f"{first['why']}"
                    + (f" (und {len(missing) - 1} weitere Angabe"
                       f"{'n' if len(missing) > 2 else ''})" if len(missing) > 1 else "")),
        )
    flow = vo.of(row.direction)
    # **Der Satz nennt den richtigen Grund**: fehlt allein der Zugang (die Stufe stimmt),
    # sagt er das, nicht die Stufe.
    if (action in VERBS and not VERBS[action].allows(flow)
            and viewer is not None and viewer.role not in STAFF_ROLES):
        raise HTTPException(
            status_code=409,
            detail=(f"«{action}» ist an diesem Beleg nicht Ihre Handlung – darüber "
                    f"entscheidet die andere Seite."),
        )
    raise HTTPException(
        status_code=409,
        detail=(f"«{action}» geht hier nicht: der Beleg steht auf "
                f"«{flow.label_of(row.stage)}»."),
    )


# ---------------------------------------------------------------------------
# ►► DIE HANDLUNGEN
# ---------------------------------------------------------------------------

def apply(db: Session, *, order: Order, step: ProcessStep, action: str,
          payload: dict[str, Any], actor: Optional[UserProfile] = None) -> Voucher:
    """**Eine Handlung am Beleg** – ein Endpunkt, eine Tabelle.

    Danach räumt der Beleg selbst nach (``follow_up``): ein Dokument geht hinaus, wo die
    Partei eine neue Stufe zu sehen bekommt, und die Stücke ziehen weiter, sobald sie
    dürfen. Beides ist keine Handlung, die jemand vergessen könnte.
    """
    row = of_step(db, step.id)
    if row is None:
        raise HTTPException(status_code=404,
                            detail="Zu diesem Modul gibt es keinen Beleg.")
    if action not in VERBS:
        raise HTTPException(status_code=400,
                            detail=f"«{action}» ist keine Handlung an einem Beleg.")
    # **Die Nutzlast weiss, um wen es geht** – beim Zuschlag steht die Gegenpartei dort,
    # und die Vollständigkeitsprüfung muss sie kennen, bevor ``_agree`` sie setzt.
    assert_allowed(db, row, action, actor, _int(payload.get("party")))
    run = VERBS[action].run
    if run is None:
        raise HTTPException(
            status_code=409,
            detail=(f"«{action}» ändert den Beleg nicht – diese Handlung hat ihren "
                    f"eigenen Weg."))
    run(db, order=order, step=step, row=row, data=payload, actor=actor)
    db.flush()
    follow_up(db, order=order, step=step, row=row, actor=actor)
    return row


def _reject_fixed(step: ProcessStep, data: dict[str, Any]) -> None:
    """Eine Vorgabe des Moduls (``Beleg.presets_of``) ändert man am Modul, nicht am Beleg."""
    fixed = modules.Beleg.presets_of(step.config)
    for key in data:
        if key in fixed and data[key] != fixed[key]:
            raise HTTPException(
                status_code=409,
                detail=(f"«{modules.Beleg.PRESET_LABELS.get(key, key)}» gibt das Modul vor – "
                        f"geändert wird es dort, für jeden künftigen Auftrag."))


def _currency(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**In welcher Währung wird gehandelt?** – eine je Beleg, nicht je Zeile.

    **Umgerechnet wird nichts** – den Kurs braucht erst die Buchhaltung. Eine Fremdwährung
    gibt es, wo wir den Preis nennen, nur mit einer Lieferadresse im Ausland (``can``).
    """
    try:
        row.currency = cur.assert_code(data.get("currency"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _issuer(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Wer stellt diesen Beleg?** – nur eine unserer Gesellschaften."""
    value = _int(data.get("issuer"))
    if value is not None:
        sites.require_own(db, value)
    row.issuer_company_id = value


def _incoterm(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Lieferbedingung** – nur die Klausel. **Der Ort ist kein Feld**: er folgt aus
    der Klausel und den Anschriften (``incoterm_place_of``)."""
    _reject_fixed(step, {"incoterm": data.get("incoterm")})
    try:
        row.incoterm = inc.assert_incoterm(data.get("incoterm"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    row.incoterm_place = None


def _terms(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Fristen und die Gültigkeit** – sofort geschrieben, geprüft erst beim
    Hinausgehen. Nur gesendete Felder wirken; was das Modul vorgibt, steht fest."""
    _reject_fixed(step, {k: data[k] for k in ("payment_days", "lead_days", "valid_days")
                         if k in data})
    if "payment_days" in data:
        row.payment_days = _days(data.get("payment_days"))
    if "lead_days" in data:
        row.lead_days = _days(data.get("lead_days"))
    if "valid_days" in data:
        days = _days(data.get("valid_days"))
        if days == 0:
            raise HTTPException(status_code=400,
                                detail="Eine Offerte gilt mindestens einen Tag.")
        row.valid_days = days


def _add_party(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
               data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Gegenpartei wählen** – wählen ist nicht anbieten: festgehalten wird nur, wen
    der Beleg betrifft (geprüft von ``_party``); hinaus geht er erst mit «Anbieten»."""
    flow = vo.of(row.direction)
    number = _party(db, step=step, value=data.get("party"), flow=flow)
    if number is None:
        raise HTTPException(
            status_code=400,
            detail=f"Ohne Objektnummer gibt es keinen {vo.PARTY}, den man wählen könnte.")
    if number not in parties_on(row):
        row.parties = [*parties_on(row), number]
    db.flush()


def _address(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **An wen und wohin** – geschäftlich oder privat, Rechnungs- und Lieferadresse. ◄◄◄

    Aus dem Adressbuch **des Adressaten**, vorbelegt mit seinen Standards. Nur gesendete
    Felder wirken, ``null`` heisst «die Vorgabe». Eine fremde Anschrift wird abgewiesen.
    """
    number = addressee_of(db, row)
    u = (db.query(UserProfile).filter(UserProfile.object_id == number).first()
         if number is not None else None)
    if u is None:
        raise HTTPException(status_code=400, detail=(
            f"An wen der Beleg geht, steht noch nicht fest – gewählt wird, sobald genau "
            f"ein {vo.PARTY} dasteht."))
    if "bill_to_company" in data:
        wanted = data.get("bill_to_company")
        if wanted and not business_possible(u):
            raise HTTPException(status_code=400, detail=(
                f"«{u.display_name}» handelt hier privat – eine eigene Gesellschaft ist nie "
                f"Gegenpartei, und ohne Firma gibt es kein Geschäftskonto."))
        if wanted != row.bill_to_company:
            # **Ein anderes Konto, andere Anschriften** – es gelten die Standards des neuen.
            row.billing_address_id = None
            row.delivery_address_id = None
        row.bill_to_company = wanted
    account = account_for(u, row)
    for key, col, kind in (("billing_address", "billing_address_id", "billing"),
                           ("delivery_address", "delivery_address_id", "delivery")):
        if key not in data:
            continue
        aid = _int(data.get(key))
        hit = address_book.pick(db, u.id, aid, kind, account) if aid is not None else None
        if aid is not None and (hit is None or hit.id != aid):
            raise HTTPException(status_code=400, detail=(
                f"Anschrift {aid} steht nicht im "
                f"{'Geschäftskonto' if account == address_book.BUSINESS else 'Privatkonto'} "
                f"von «{u.display_name}»."))
        setattr(row, col, aid)
    fit_to_address(db, row, lines_of(db, row))


def _ownership(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
               data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Wem die Stücke danach gehören** – frei wählbar bis zur Zusage, keine
    Prüfung: eine Angabe des Menschen, die im Log steht, wenn die Stücke passieren. ◄◄◄"""
    _reject_fixed(step, {"ownership": data.get("ownership")})
    try:
        row.ownership = vo.assert_ownership(data.get("ownership"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _price(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Die Positionen schreiben — gespeichert, nicht abgeschickt.** ◄◄◄

    **Die Menge kommt nie aus der Nutzlast** – sie ist die Zahl der Einzelinstanzen.
    **Preis, Satz und Teilbetrag nur, wo WIR den Preis nennen**; die Leistung und die
    Zoll-Angaben in beiden Richtungen – sie beschreiben die Sache, nicht das Angebot.
    **Der Satz ist eine Folge der Anschrift**: angeboten wird nur, was dort gilt.
    """
    flow = vo.of(row.direction)
    rows = {ln.id: ln for ln in sync_lines(db, row, order, step)}
    delivery, seat = destination(db, row)
    kinds = services_of(db, list(rows.values()))
    for raw in data.get("lines") or []:
        found = rows.get(_int(raw.get("id")))
        if found is None:
            continue
        if flow.quoted_by == vo.BY_US:
            if "price" in raw:
                found.price = amount_of(raw.get("price"), row.currency, allow_negative=True)
            if "part" in raw:
                found.part = amount_of(raw.get("part"), row.currency)
            if "vat" in raw:
                try:
                    key = vo.assert_vat(raw.get("vat") or vo.DEFAULT_VAT)
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e))
                allowed = vo.vat_choices(service=kinds.get(found.article_id or 0, False),
                                         delivery_country=delivery, seat_country=seat)
                if key not in allowed:
                    raise HTTPException(status_code=400, detail=(
                        f"«{vo.vat_label(key)}» gilt hier nicht – die Anschrift lässt "
                        + ", ".join(vo.vat_label(k) for k in allowed) + " zu."))
                found.vat = key
        if "text" in raw:
            found.text = _text(raw.get("text"), 300)
        if "hs_code" in raw:
            found.hs_code = _text(raw.get("hs_code"), 12)
        if "origin_country" in raw:
            found.origin_country = _text(raw.get("origin_country"), 60)
        if "weight_kg" in raw:
            found.weight_kg = _weight(raw.get("weight_kg"))
    db.flush()


def _ask(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Anbieten bzw. anfragen – und «Erneut anbieten» ist dieselbe Handlung.** ◄◄◄

    **Ohne Angabe sind es alle zugelassenen**, sonst wen der Beleg trägt. Wer abgesagt hat,
    wird nicht wieder angeschrieben.

    **Wer den Preis nennt, schickt ihn mit**: bei einer Einnahme ist der Betrag die
    Brutto-Summe der Positionen, und die Fristen kommen vom Beleg. Ein erneutes Anbieten
    erneuert Betrag, Fristen und Datum – die Frist der Gültigkeit beginnt neu, und die
    vorige Fassung ist überholt.

    **Mit dem ersten Hinausgehen frieren die Stücke ein** (``unit_ids``): ab hier spricht
    der Beleg über genau diese.
    """
    from . import voucher_docs
    flow = vo.of(row.direction)
    allowed = modules.Beleg.parties_allowed(step.config)
    wanted = list(data.get("parties") or []) or allowed or parties_on(row)
    _assert_ask(db, row, step, wanted)
    _freeze_units(db, row, order)
    lead, days = row.lead_days, row.payment_days
    priced = priced_dicts(db, row) if flow.quoted_by == vo.BY_US else []
    amount = vo.gross_of(priced, row.currency) if priced else None
    existing = {q.party_id: q for q in quotes_of(db, row)}
    sent: list[int] = []
    for value in wanted:
        number = _party(db, step=step, value=value, flow=flow)
        if number is None or number in sent:
            continue
        q = existing.get(number)
        if q is not None and q.state == vo.DECLINED:
            continue
        if q is None:
            q = VoucherQuote(voucher_id=row.id, party_id=number)
            db.add(q)
        elif flow.quoted_by != vo.BY_US:
            continue
        q.state = vo.QUOTED if priced else vo.ASKED
        q.amount = amount
        q.lead_days, q.payment_days = lead, days
        q.sent_on = clock.today()
        sent.append(number)
    db.flush()
    if flow.quoted_by == vo.BY_US:
        row.offered_hash = fingerprint(db, row)
        if flow.collects:
            for number in sent:
                voucher_docs.issue(db, row=row, kind=vo.OFFER_DOC, actor=actor,
                                   party_id=number)


def _freeze_units(db: Session, row: Voucher, order: Order) -> None:
    """**Mit dem ersten Hinausgehen frieren die Stücke ein** (``unit_ids``) – ab hier
    spricht der Beleg über genau die, die jetzt offen im Auftrag stehen."""
    if row.unit_ids is None:
        row.unit_ids = sorted(
            int(i) for (i,) in db.query(OrderUnit.instance_unit_id).filter(
                OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None)).all())


def _quote(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Eine Offerte der Gegenpartei erfassen** – Betrag, Fristen, ihre Referenz (bei
    einem Online-Kauf die Bestellnummer) und der Link zur Bestellung. Eine Gegenpartei trifft
    ausschliesslich ihre eigene Zeile."""
    line = _target(db, row, data, actor)
    if "amount" in data:
        line.amount = amount_of(data.get("amount"), row.currency)
    if "lead_days" in data:
        line.lead_days = _days(data.get("lead_days"))
    if "payment_days" in data:
        line.payment_days = _days(data.get("payment_days"))
    if "reference" in data:
        line.reference = _text(data.get("reference"), 120)
    if "link" in data:
        line.link = _text(data.get("link"), 500)
    if line.amount is None:
        raise HTTPException(status_code=400,
                            detail="Ohne Betrag ist es keine Offerte.")
    _assert_terms(line.lead_days, line.payment_days)
    line.state = vo.QUOTED
    line.sent_on = line.sent_on or clock.today()


def _decline(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Eine Angebotszeile **absagen** – in beide Richtungen dasselbe. Abgesagt ist
    abgesagt: der Preis fällt mit ihr weg."""
    line = _target(db, row, data, actor)
    line.state = vo.DECLINED
    line.amount = None
    line.lead_days = None
    line.payment_days = None


def _agree(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Den Zuschlag geben** – ab hier ist eine zweite Partei gebunden. ◄◄◄

    Die gewählte Zeile geht auf ``gewaehlt``, und damit steht alles fest. **Bei einer
    Einnahme gilt, was angeboten wurde** – der Betrag der Zeile, nicht eine neue Rechnung
    (ein geänderter Beleg muss zuerst erneut angeboten werden, ``can``). Bei einer
    **Ausgabe** darf die Nutzlast nachverhandeln.

    Der Belegkopf friert ein, der Ort der Lieferbedingung auch; danach ziehen die Stücke
    von selbst weiter (``follow_up``), und die Auftragsbestätigung geht hinaus.
    """
    from . import voucher_docs
    flow = vo.of(row.direction)
    number = _party(db, step=step, value=data.get("party"), flow=flow)
    if number is None:
        raise HTTPException(status_code=400,
                            detail=f"Ohne {vo.PARTY} gibt es keine Zusage.")
    line = next((q for q in quotes_of(db, row) if q.party_id == number), None)
    if line is None:
        raise HTTPException(
            status_code=400,
            detail=(f"{vo.PARTY} {number} ist hier nicht angefragt – zugesagt wird an "
                    f"einer Zeile des Angebotsspiegels."))
    if line.state == vo.DECLINED:
        raise HTTPException(
            status_code=409,
            detail=(f"{vo.PARTY} {number} hat abgesagt. Wer doch will, bekommt zuerst "
                    f"wieder ein Angebot."))
    if flow.quoted_by != vo.BY_US:
        if "amount" in data:
            line.amount = amount_of(data.get("amount"), row.currency)
        if "lead_days" in data:
            line.lead_days = _days(data.get("lead_days"))
        if "payment_days" in data:
            line.payment_days = _days(data.get("payment_days"))
    if line.amount is None:
        raise HTTPException(status_code=400,
                            detail="Ohne Betrag gibt es keine Zusage.")
    _assert_terms(line.lead_days, line.payment_days)
    _assert_ownership_chosen(row)
    _freeze_units(db, row, order)
    for other in quotes_of(db, row):
        if other.id != line.id and other.state == vo.CHOSEN:
            other.state = vo.QUOTED
    # **Der Kopf friert ein – VOR dem Stufenwechsel gelesen**, damit ``billing_of`` noch
    # ableitet statt eine leere Kopie zurückzugeben.
    row.head = freeze(db, row, number)
    line.state = vo.CHOSEN
    row.incoterm_place = incoterm_place_of(db, row)
    row.stage = vo.AGREED
    row.agreed_on = clock.today()
    db.flush()
    if vo.CONFIRM_DOC in AUTO_RELEASE and vo.CONFIRM_DOC in papers_due(db, row):
        voucher_docs.issue(db, row=row, kind=vo.CONFIRM_DOC, actor=actor)


def _unask(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Eine Anfrage zurückziehen bzw. eine Wahl zurücknehmen** – diesen Partner von
    diesem Beleg wegnehmen (Soft-Delete), nur vor der Zusage."""
    number = _int(data.get("party"))
    if number is not None and number in parties_on(row):
        row.parties = [n for n in parties_on(row) if n != number]
        for q in quotes_of(db, row):
            if q.party_id == number:
                q.is_active = False
        db.flush()
        return
    _target(db, row, data, actor).is_active = False
    db.flush()


def _revoke(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Stornieren** – ein Wort in jeder Stufe; was es bewirkt, folgt aus ihr. ◄◄◄

    * vor der Zusage: das Angebot gilt nicht mehr;
    * nach der Zusage: der Auftrag gilt nicht mehr – es ist nichts geschuldet;
    * **nach der Rechnung: die Gutschrift über die ganze Rechnung entsteht von selbst**
      (eigene Nummer, Bezug auf die Rechnung). Was schon bezahlt ist, geht zurück
      («Erstatten» bleibt möglich).

    Hat die Partei schon etwas gesehen, bekommt sie Bescheid – eine allgemeine Mail, ohne
    den Grund (der bleibt intern, ``cancel_note``). Die Stücke führt ein ganz gewöhnlicher
    Abweichungsauftrag weiter.
    """
    from . import voucher_docs
    flow = vo.of(row.direction)
    row.cancel_note = _text(data.get("note"), 200)
    billed = is_billed(row)
    if billed and flow.collects and not row.credit_number:
        row.credit_number = _our_number(db, row)
    told = _told(db, row) if flow.collects else []
    row.stage = vo.CANCELLED
    row.cancelled_on = clock.today()
    db.flush()
    for party in told:
        voucher_docs.issue(db, row=row, kind=vo.CREDIT_DOC if billed else vo.STORNO_DOC,
                           actor=actor, party_id=party)


def _told(db: Session, row: Voucher) -> list[int]:
    """**Wer vom Storno erfährt** – die gebundene Partei, sonst jede, die ein Papier bekam."""
    bound = party_of(db, row)
    if bound is not None:
        return [bound]
    out: list[int] = []
    for d in documents_of(db, row):
        if d.party_id is not None and d.party_id not in out:
            out.append(d.party_id)
    return out


def _bill(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
          data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Die Rechnung stellen bzw. erfassen — und damit IST der Beleg eine.** ◄◄◄

    **Wo WIR den Preis nennen**, ist die Summe der Positionen die Rechnung (Teilbeträge
    eingeschlossen; eine Position mit null steht nicht darauf). Die Nummer vergeben wir.

    **Wo die Gegenpartei ihn nennt**, schreiben wir ihre Rechnung ab – so, wie sie auf
    dem Papier steht: Betrag, Satz, **Rechnungsnummer**, **Rechnungsdatum** und **ihre
    MWST-Nummer** (ohne sie kein Vorsteuerabzug, MWSTG Art. 28). Das **Foto** der Rechnung
    ist Pflicht – es ist der Beleg. Weicht der Betrag von der Zusage ab, steht die
    Differenz als Zeile, und bezahlt wird erst nach dem Entscheid (``accept``).
    """
    from . import voucher_docs
    flow = vo.of(row.direction)
    if flow.quoted_by == vo.BY_US:
        priced = [ln for ln in priced_dicts(db, row)
                  if vo.line_net(ln, row.currency) != 0]
        if not priced:
            raise HTTPException(
                status_code=400,
                detail=(f"Ohne Preis gibt es nichts zu berechnen – bei einer "
                        f"{flow.label} nennen wir ihn."))
        gross = vo.gross_of(priced, row.currency)
        split = vo.vat_split(priced, row.currency)
    else:
        given = amount_of(data.get("amount"), row.currency)
        gross = given if given is not None else agreed_amount(db, row)
        if gross is None:
            raise HTTPException(status_code=400, detail="Ohne Betrag ist es keine Rechnung.")
        try:
            split = vo.split_at(gross, data.get("vat") or vo.DEFAULT_VAT, row.currency)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        _record_original(db, row, data, split)
    if gross == 0:
        raise HTTPException(status_code=400,
                            detail="Eine Rechnung über null ist keine.")
    if flow.reference is not None and not row.number:
        number = _text(data.get("reference"), 120)
        if not number:
            raise HTTPException(
                status_code=400,
                detail=(f"Ohne {flow.reference} lässt sich diese Rechnung nicht "
                        f"zuordnen – sie steht auf seinem Papier."))
        row.number = number
    elif not row.number:
        row.number = _our_number(db, row)
    booked = _day(data.get("billed_on")) or clock.today()
    row.billed_on = booked
    row.due_on = days_after(booked, due_days_of(db, row))
    row.amount = gross
    row.vat = split
    # **Das Leistungsdatum kommt aus dem PROZESS** – der Tag, an dem die Stücke dieses
    # Modul erreicht haben (MWSTG Art. 26 Bst. c).
    row.service_date = service_day(db, step) or booked
    row.stage = vo.BILLED
    db.flush()
    if flow.collects:
        voucher_docs.issue(db, row=row,
                           kind=vo.CREDIT_DOC if minus(row) else vo.INVOICE_DOC, actor=actor)


def _record_original(db: Session, row: Voucher, data: dict[str, Any],
                     split: list[dict[str, str]]) -> None:
    """►►► **Die Lieferantenrechnung, wie sie auf dem Papier steht.** ◄◄◄ Das Dokument ist
    Pflicht (Feld ``voucher.original``); die MWST-Nummer, sobald Steuer darauf steht (ohne
    sie kein Vorsteuerabzug)."""
    original = _module_document(db, row, data, "voucher.original", (
        "Ohne die Rechnung als Dokument geht es nicht – sie ist der Beleg, aufbewahrt zehn "
        "Jahre."))
    taxed = any(Decimal(r.get("tax") or "0") != 0 for r in split)
    uid = _text(data.get("party_uid"), 40)
    if taxed and not uid:
        raise HTTPException(status_code=400, detail=(
            "Ohne MWST-Nummer des Lieferanten gibt es keinen Vorsteuerabzug "
            "(MWSTG Art. 28) – sie steht auf seiner Rechnung."))
    row.original_id = original
    row.party_uid = uid


def _accept(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Lieferantenrechnung so annehmen, wie sie ist** – mit Grund. Die Differenz
    bleibt als Zeile stehen; jetzt wird bezahlt."""
    note = _text(data.get("note"), 200)
    if not note:
        raise HTTPException(status_code=400, detail=(
            "Eine Abweichung nimmt man mit Grund an – er bleibt als Nachweis stehen."))
    row.deviation_note = note


def correction_problem(db: Session, row: Voucher,
                       target: Optional[Voucher]) -> Optional[str]:
    """►►► **Kann ``row`` diesen Beleg mindern?** – der Satz, oder ``None``. ◄◄◄

    Gemindert wird eine gestellte **Rechnung** in derselben Richtung – nie der Beleg selbst
    und nie eine Gutschrift (damit kann keine Kette und kein Kreis entstehen). Zwei Formen
    einer Regel: ``_assert_correction`` ist das Tor, ``correctable`` filtert mit ihr.
    """
    if target is None or not target.is_active:
        return "Diesen Beleg gibt es nicht."
    if target.id == row.id:
        return "Ein Beleg korrigiert nicht sich selbst."
    if minus(target):
        return (f"«{target.number or target.id}» ist selbst eine Gutschrift – gemindert wird "
                f"die Rechnung, nicht ihre Korrektur.")
    if not is_billed(target):
        return "Dieser Beleg trägt noch keine Rechnung – es gibt nichts zu korrigieren."
    if target.direction != row.direction:
        return (f"Eine {vo.of(row.direction).label} korrigiert keine "
                f"{vo.of(target.direction).label}: das Geld flösse in die andere Richtung.")
    return None


def _assert_correction(db: Session, row: Voucher, target: Optional[Voucher]) -> None:
    """Das Tor zu ``correction_problem`` – derselbe Satz, nur geworfen."""
    problem = correction_problem(db, row, target)
    if problem:
        raise HTTPException(status_code=400, detail=problem)


def _correct(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Welche Rechnung mindert dieser Beleg?** Der Verweis darf über Auftragsgrenzen zeigen
    – die Gutschrift gehört dorthin, wo die Ware zurückkommt (``correction_problem``)."""
    value = _int(data.get("corrects"))
    if value is None:
        row.corrects_id = None
        return
    target = db.query(Voucher).filter(Voucher.id == value).first()
    _assert_correction(db, row, target)
    row.corrects_id = target.id
    # **Vorbelegt ist der Rechnungsbetrag** – je Position der Preis der korrigierten
    # Rechnung, wo dieselbe Ware wieder dasteht. Ein Limit gibt es nicht.
    prices = {ln.article_id: ln for ln in lines_of(db, target)}
    for ln in lines_of(db, row):
        src = prices.get(ln.article_id)
        if src is not None and ln.price is None:
            ln.price, ln.vat = src.price, src.vat


def _entry(db: Session, row: Voucher, *, amount: Decimal, kind: str = vo.PAYMENT,
           data: Optional[dict[str, Any]] = None, method: Optional[str] = None,
           reason: Optional[str] = None, reverses: Optional[int] = None) -> VoucherEntry:
    """**Eine Geld-Zeile von Hand** – geschrieben über ``book``."""
    data = data or {}
    entry = VoucherEntry(
        voucher_id=row.id, amount=amount, kind=kind,
        booked_on=_day(data.get("booked_on")) or clock.today(),
        reference=_text(data.get("reference"), 120),
        note=_text(data.get("note"), 200), method=method, reason=reason,
        reverses_id=reverses, iban=_iban(data.get("iban")),
    )
    book(db, row, entry)
    return entry


def _method(row: Voucher, value: Any) -> Optional[str]:
    """**Wie bezahlt wurde** – von Hand bar oder per Überweisung; **mit Karte nur, wo WIR
    zahlen** (die Firmenkarte). Eine Karte, die uns bezahlt, meldet der Zahlungsdienst."""
    try:
        return vo.assert_method(value, card=not inbound(row))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _pay(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Eine Zahlung erfassen** – vorbelegt mit dem Offenen. Positiv: wer überzahlt, tut
    das mit einem grösseren Betrag; zurück geht es mit «Erstatten»."""
    given = amount_of(data.get("amount"), row.currency)
    value = given if given is not None else balance_of(db, row).next_payment
    if value is None or value <= 0:
        raise HTTPException(status_code=400, detail="Ohne Betrag keine Zahlung.")
    method = _method(row, data.get("method"))
    # **Eine Erstattung per Überweisung braucht das Konto, wohin** – es kommt über den
    # gewöhnlichen Verlauf und wird hier eingetragen (keine Anfrage, kein Formular).
    if minus(row) and method == vo.TRANSFER and not _iban(data.get("iban")):
        raise HTTPException(status_code=400, detail=(
            "Zuerst die IBAN eintragen – wohin die Erstattung geht."))
    _entry(db, row, amount=value, data=data, method=method)


def _refund(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Erstatten** – das Geld geht dorthin zurück, woher es kam (bar, an die IBAN).
    Vorbelegt mit dem, was zu viel ist. Auf die Karte geht es über den Zahlungsdienst."""
    owed = -balance_of(db, row).open
    given = amount_of(data.get("amount"), row.currency)
    value = given if given is not None else owed
    if value is None or value <= 0:
        raise HTTPException(status_code=400, detail="Hier ist nichts zu erstatten.")
    method = _method(row, data.get("method"))
    if method == vo.TRANSFER and not _iban(data.get("iban")):
        raise HTTPException(status_code=400, detail=(
            "Eine Überweisung braucht die IBAN – sie kommt über den gewöhnlichen Verlauf "
            "und wird hier eingetragen."))
    _entry(db, row, amount=-value, data=data, method=method)


def _writeoff(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Ausbuchen** – der Rest als eigene Zeile mit Grund; kein Geld fliesst. Rechtlich eine
    Entgeltsminderung (MWSTG Art. 41) – ihre Steuer rechnet erst die Buchhaltung."""
    try:
        reason = vo.assert_reason(data.get("reason"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _entry(db, row, amount=balance_of(db, row).open, kind=vo.WRITEOFF, data=data,
           reason=reason)


def _tip(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Als Trinkgeld behalten** – was zu viel kam, bleibt als eigene Zeile stehen. Es ist
    Entgelt (MWSTG Art. 24) – seine Steuer rechnet erst die Buchhaltung."""
    _entry(db, row, amount=-balance_of(db, row).open, kind=vo.TIP, data=data)


def _reverse(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**«Falsch erfasst?»** – die Gegenbuchung genau dieser Zeile, für einen Tippfehler.
    Gelöscht wird nichts; beide Zeilen bleiben stehen."""
    wanted = _int(data.get("entry"))
    found = next((e for e in reversible(db, row) if e.id == wanted), None)
    if found is None:
        raise HTTPException(status_code=409, detail=(
            "Diese Zeile lässt sich nicht gegenbuchen – sie ist schon gegengebucht, ist "
            "selbst eine Gegenbuchung oder kam vom Zahlungsdienst."))
    _entry(db, row, amount=-found.amount, kind=found.kind, method=found.method,
           reason=found.reason, reverses=found.id,
           data={"note": vo.REVERSE_WORD.rstrip("?")})


def _remind(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Mahnen** – die nächste Stufe, als Dokument mit Mail. Nichts geht von selbst;
    ``can`` lässt es erst zu, wenn die Stufe fällig ist (zehn Tage Abstand). ◄◄◄"""
    from . import voucher_docs
    step_no, _when = next_reminder(db, row) or (None, None)
    if step_no is None:
        raise HTTPException(status_code=409, detail="Hier ist keine Mahnung fällig.")
    voucher_docs.issue(db, row=row, kind=vo.REMINDER_DOC, actor=actor, level=step_no)


def _export(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Den Ausfuhrnachweis erfassen** – Nummer der Veranlagungsverfügung und das Dokument
    (PDF oder Bild, hochgeladen). Ohne ihn gilt der Nullsatz nicht; erledigt ist der Beleg
    erst damit."""
    message = ("Der Ausfuhrnachweis braucht die Nummer der Veranlagungsverfügung und das "
               "Dokument dazu.")
    number = _text(data.get("reference"), 60)
    if not number:
        raise HTTPException(status_code=400, detail=message)
    photo = _module_document(db, row, data, "voucher.export", message)
    row.export_number, row.export_photo_id = number, photo


def _release(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Ein anstehendes Papier freigeben** – es entsteht und geht hinaus (``voucher_docs``)."""
    from . import voucher_docs
    kind = _text(data.get("kind"), 16)
    if kind not in papers_due(db, row):
        raise HTTPException(status_code=409, detail=(
            f"«{vo.DOCUMENTS.get(kind or '', kind or '–')}» steht hier nicht an."))
    voucher_docs.issue(db, row=row, kind=kind, actor=actor)


def _module_document(db: Session, row: Voucher, data: dict[str, Any], field: str,
                     message: str) -> int:
    """►►► **Ein Dokument in einem Feld des Moduls** – gewählt (``data.original``, eine
    Dokumentnummer) oder schon im Feld. Es kommt ins Pflichtfeld (``documents.set_field``):
    änderbar, nie leer, nie löschbar, solange es dort steht. ◄◄◄"""
    from ..models import Document
    from . import documents
    chosen = _int(data.get("original"))
    order = db.query(Order).filter(Order.id == row.order_id).first()
    part = f"step:{row.step_id}"
    if chosen is None:
        found = documents.field_document(db, order.object_id, field, part)
        chosen = found.object_id if found is not None else None
    doc = (db.query(Document).filter(Document.object_id == chosen,
                                     Document.deleted_at.is_(None)).first()
           if chosen is not None else None)
    if doc is None:
        raise HTTPException(status_code=400, detail=message)
    documents.set_field(db, document_object_id=doc.object_id, object_id=order.object_id,
                        part=part, field=field, actor=None)
    return doc.object_id


def _weight(value: Any) -> Optional[Decimal]:
    """Ein Gewicht in kg – oder ``None``. Nie negativ."""
    if value in (None, ""):
        return None
    try:
        found = Decimal(str(value).strip().replace("'", "").replace(",", "."))
    except Exception:
        raise HTTPException(status_code=400, detail=f"«{value}» ist kein Gewicht.")
    if found < 0 or found > Decimal("999999"):
        raise HTTPException(status_code=400, detail=f"«{value}» ist kein Gewicht.")
    return found.quantize(Decimal("0.001"))


def _iban(value: Any) -> Optional[str]:
    """Eine IBAN in Normalform (ohne Leerzeichen, gross) – oder ``None``."""
    text = "".join(str(value or "").split()).upper()
    if not text:
        return None
    if not (15 <= len(text) <= 34 and text[:2].isalpha() and text[2:4].isdigit()):
        raise HTTPException(status_code=400, detail=f"«{value}» ist keine IBAN.")
    return text


#: ►►► **DIE EINE TABELLE.** ◄◄◄ Wer ein Verb hinzufügt, schreibt eine Zeile und hat damit
#: Stufe, Stammdaten, Zugang und Wirkung erklärt. Die Lage (abgelaufen, Stücke weg,
#: überzahlt …) prüft ``can`` – an derselben Stelle für Knopf und Tür.
VERBS: dict[str, Verb] = {
    # **Vor der Zusage** – hier wird der Beleg geschrieben. Die Währung gehört dem, der
    # den Preis nennt.
    "currency": Verb(stages=(vo.OFFER,), run=_currency, party=IF_THEY_PRICE),
    "issuer": Verb(stages=(vo.OFFER,), run=_issuer),
    "incoterm": Verb(stages=(vo.OFFER,), run=_incoterm),
    "terms": Verb(stages=(vo.OFFER,), run=_terms),
    "price": Verb(stages=(vo.OFFER,), run=_price),
    "party": Verb(stages=(vo.OFFER,), run=_add_party),
    "address": Verb(stages=(vo.OFFER,), run=_address),
    "ownership": Verb(stages=(vo.OFFER,), run=_ownership),
    "correct": Verb(stages=(vo.OFFER,), run=_correct),
    "ask": Verb(stages=(vo.OFFER,), run=_ask, needs=("ask",)),
    "unask": Verb(stages=(vo.OFFER,), run=_unask),
    "quote": Verb(stages=(vo.OFFER,), run=_quote, needs=("ask",), party=IF_THEY_PRICE),
    "decline": Verb(stages=(vo.OFFER,), run=_decline, party=ALWAYS),
    "agree": Verb(stages=(vo.OFFER,), run=_agree, needs=("ask", "agree"),
                  party=IF_WE_PRICE),
    # **Stornieren** – ein Wort in jeder Stufe (vor der Zusage erst, wenn etwas
    # hinausging, ``can``).
    "revoke": Verb(stages=(vo.OFFER, vo.AGREED, vo.BILLED), run=_revoke),
    # **DIE Rechnung** – eine Schwelle von ``agreed`` nach ``billed``.
    "bill": Verb(stages=(vo.AGREED,), run=_bill, needs=("ask", "agree", "bill")),
    "accept": Verb(stages=(vo.BILLED,), run=_accept),
    # **Das Geld** – auch nach dem Storno muss es zurückgehen können.
    "pay": Verb(stages=(vo.BILLED,), run=_pay),
    "refund": Verb(stages=(vo.BILLED, vo.CANCELLED), run=_refund),
    "writeoff": Verb(stages=(vo.BILLED,), run=_writeoff),
    "tip": Verb(stages=(vo.BILLED,), run=_tip),
    "reverse": Verb(stages=(vo.BILLED, vo.CANCELLED), run=_reverse),
    "remind": Verb(stages=(vo.BILLED,), run=_remind),
    "export": Verb(stages=(vo.BILLED,), run=_export),
    # **Ein anstehendes Papier freigeben** (Auftragsbestätigung, Quittung – ``papers_due``).
    "release": Verb(stages=(vo.AGREED, vo.BILLED), run=_release),
    # ``run=None``: **sie ändern den Beleg nicht.** Gebucht wird erst, wenn der
    # Zahlungsdienst es meldet. Eigener Weg, **dieselbe Tür** (``assert_allowed``).
    "pay_online": Verb(stages=(vo.BILLED,), party=ALWAYS),
    "refund_online": Verb(stages=(vo.BILLED, vo.CANCELLED)),
}


def _target(db: Session, row: Voucher, data: dict[str, Any],
            actor: Optional[UserProfile]) -> VoucherQuote:
    """**Welche Angebotszeile ist gemeint?**

    Eine **Gegenpartei** trifft ausschliesslich ihre eigene – gelesen aus dem angemeldeten
    Benutzer, nie aus der Nutzlast: sonst entschiede die Nutzlast, wessen Preis geändert
    wird. Personal nennt die Partei.
    """
    internal = actor is None or actor.role in STAFF_ROLES
    number = _int(data.get("party")) if internal else (
        actor.object_id if actor else None)
    rows = quotes_of(db, row)
    if number is None and internal and len(rows) == 1:
        # Steht genau eine Zeile da, ist sie gemeint – danach zu fragen wäre eine Frage
        # mit genau einer richtigen Antwort.
        return rows[0]
    found = next((q for q in rows if q.party_id == number), None)
    if found is None:
        raise HTTPException(
            status_code=404,
            detail=f"{vo.PARTY} {number} ist an diesem Beleg nicht angefragt.")
    return found


# ---------------------------------------------------------------------------
# ►► DIE GEGENPARTEI
# ---------------------------------------------------------------------------

def _party(db: Session, *, step: ProcessStep, value: Any,
           flow: vo.Direction) -> Optional[int]:
    """Die gewählte Gegenpartei prüfen – gegen die Freigabe und gegen die Wirklichkeit.

    **Leer heisst frei, aber nicht «irgendwer»**: wo die Definition niemanden nennt, muss
    es die Objektnummer trotzdem geben. Eine Auswahl, die der Dienst danach abwiese, wäre
    keine.
    """
    if value in (None, "", 0):
        return None
    number = _int(value)
    if number is None:
        raise HTTPException(status_code=400,
                            detail=f"«{value}» ist keine Objektnummer.")
    allowed = modules.Beleg.parties_allowed(step.config)
    if allowed and number not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(f"{vo.PARTY} {number} ist an diesem Modul nicht zugelassen. Erlaubt: "
                    + ", ".join(str(n) for n in allowed) + "."))
    found = (
        db.query(UserProfile)
        .filter(UserProfile.object_id == number, UserProfile.is_active.is_(True))
        .first()
    )
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=f"{number} ist kein Datensatz, mit dem man handeln kann.")
    return number


# ---------------------------------------------------------------------------
# ►► KLEINE HELFER — jeder mit genau einer Aufgabe
# ---------------------------------------------------------------------------

def _int(value: Any) -> Optional[int]:
    """Eine Zahl aus der Nutzlast – **tolerant**, denn hier wird nur nachgesehen."""
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def amount_of(value: Any, code: str, *, allow_negative: bool = False) -> Optional[Decimal]:
    """Ein Betrag aus der Nutzlast (``vo.amount``) – unlesbar ist ein 400 mit Satz."""
    try:
        return vo.amount(value, code, allow_negative=allow_negative)
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


def ask_problem(db: Session, row: Voucher, step: ProcessStep,
                parties: Optional[list[int]] = None,
                lines: Optional[list[dict[str, Any]]] = None) -> Optional[str]:
    """►►► **Was fehlt noch, damit dieser Beleg HINAUSGEHEN kann?** ◄◄◄ – oder ``None``.

    Zwei Formen einer Regel: der Satz reist mit (``VoucherEmbed.ask_problem``, der Knopf
    steht gesperrt da und sagt im Hover, was fehlt), ``_assert_ask`` wirft ihn. Pflicht ist,
    was auf dem Beleg steht – Preis je Position, bei einer Ausfuhr die Zoll-Angaben, bei Ware
    die Lieferbedingung, beide Fristen, das Eigentum –, gelesen wie es dasteht
    (``embed_lines``). Alles Fehlende auf einmal, je Position benannt. ``parties``/``lines``
    gibt der Aufrufer mit, wo er sie schon hat.
    """
    flow = vo.of(row.direction)
    # **Ohne Gegenpartei gibt es nichts anzufragen** – zwei Quellen, dieselben wie in
    # ``_ask``: was die Definition zulässt und wen der Beleg selbst schon trägt.
    if parties is None:
        parties = modules.Beleg.parties_allowed(step.config) or parties_on(row)
    if not parties:
        return (f"Ohne {vo.PARTY} gibt es nichts anzufragen – dieses Modul lässt "
                f"jeden zu, also muss hier stehen, wen es betrifft.")
    found: list[str] = []
    priced = flow.quoted_by == vo.BY_US
    # ►►► **Zoll nur bei einer Ausfuhr** – Tarif, Ursprung und Gewicht braucht der Zoll,
    # im Inland niemand. ◄◄◄
    export = is_export(db, row)
    for ln in (lines if lines is not None else embed_lines(db, row)):
        what = f"Position «{ln['article_name'] or ln['id']}»"
        if priced and ln["price"] is None:
            found.append(f"{what}: ohne Preis gibt es nichts anzubieten.")
        if not export or ln.get("is_service"):
            continue
        gaps = [label for key, label in (("hs_code", vo.HS_CODE_LABEL),
                                         ("origin_country", vo.ORIGIN_LABEL),
                                         ("weight_kg", vo.WEIGHT_LABEL))
                if not str(ln.get(key) or "").strip()]
        if gaps:
            found.append(f"{what}: {' · '.join(f'«{g}»' for g in gaps)} fehlt – eine "
                         f"Ausfuhr braucht es. Am Artikel hinterlegt, steht es auf jedem "
                         f"Beleg von selbst; hier eingetragen, gilt es für diesen Beleg.")
    # **Eine Lieferbedingung gibt es nur bei Ware** – eine Dienstleistung reist nicht.
    if not row.incoterm and has_goods(db, row):
        found.append(f"Ohne {inc.LABEL} ist nicht vereinbart, wer Fracht, Versicherung "
                     f"und Zoll trägt – und genau darüber wird sonst gestritten.")
    if priced:
        if not priced_dicts(db, row) and not any("Preis" in f for f in found):
            found.append(f"Ohne Preis gibt es nichts anzubieten – bei einer {flow.label} "
                         f"nennen wir ihn, nicht der {vo.PARTY}.")
        found.append(terms_problem(row.lead_days, row.payment_days) or "")
    # **Zuletzt das Eigentum** – bewusst gewählt, ohne Vorbelegung.
    found.append(ownership_problem(row) or "")
    found = [f for f in found if f]
    if len(found) < 2:
        return found[0] if found else None
    return "\n".join(f"– {f}" for f in found)


def _assert_ask(db: Session, row: Voucher, step: ProcessStep,
                parties: list[int]) -> None:
    """Das Tor zu ``ask_problem`` – **derselbe Satz**, nur geworfen."""
    problem = ask_problem(db, row, step, parties=parties)
    if problem:
        raise HTTPException(status_code=400, detail=problem)


def terms_problem(lead: Optional[int], days: Optional[int]) -> Optional[str]:
    """►►► **Ein Angebot nennt beide Fristen.** ◄◄◄ – der Satz, oder ``None``.

    Sie sind kein Beiwerk: aus der **Lieferfrist** kommt der Termin, aus der
    **Zahlungsfrist** die Fälligkeit jeder Rechnung – und, wenn sie null ist, die
    Vorauszahlung. Fehlt eine, hat niemand über den Zeitpunkt gesprochen.

    **Null ist ein gültiger Wert und hat einen Namen** («Sofort» · «Vorauszahlung»): darum
    steht die Prüfung auf ``is None`` und nicht auf ``not value``.

    **Zwei Formen, ein Namensstamm**: ``_assert_terms`` wirft ihn an einer Angebotszeile,
    ``ask_problem`` trägt ihn an den gesperrten Knopf.
    """
    for value, label in ((lead, vo.LEAD_TERM_LABEL), (days, vo.PAYMENT_TERM_LABEL)):
        if value is None:
            return (f"Ohne {label} ist es kein Angebot – aus ihr folgt der Termin "
                    f"bzw. die Fälligkeit. «{vo.LEAD_TERMS[0][1]}» und "
                    f"«{vo.PAYMENT_TERMS[0][1]}» sind gültige Antworten (0 Tage).")
    return None


def _assert_terms(lead: Optional[int], days: Optional[int]) -> None:
    """Das Tor zu ``terms_problem`` – derselbe Satz, nur geworfen."""
    problem = terms_problem(lead, days)
    if problem:
        raise HTTPException(status_code=400, detail=problem)


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


def _our_number(db: Session, row: Voucher) -> str:
    """►►► **Unsere nächste Nummer im Auftrag** – ``<Auftragsnummer>-<laufend>``, ab ``-1``. ◄◄◄

    Rechnungen **und** Gutschriften ziehen aus derselben Zählung (eine Gutschrift ist ein
    eigenes Dokument mit eigener Nummer, MWSTG Art. 26); stornierte zählen mit, eine Nummer
    wird nie zweimal vergeben. Gezählt wird unter der Sperre des Auftrags – zwei Module, die
    gleichzeitig stellen, bekommen zwei Nummern. Nur, was **wir** nummerieren: eine erfasste
    Lieferantenrechnung trägt die Nummer der Gegenpartei.
    """
    order = (db.query(Order).filter(Order.id == row.order_id)
             .with_for_update().one())
    used = (
        db.query(func.count(Voucher.number) + func.count(Voucher.credit_number))
        .filter(Voucher.order_id == order.id, Voucher.direction == vo.IN)
        .scalar()
    ) or 0
    return f"{order.object_id}-{used + 1}"
