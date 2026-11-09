"""►►► **Die Handlungen am Beleg** – jedes Verb EINMAL (``VERBS``), ``can`` als Auskunft
und Tor (``assert_allowed``), ``apply`` als die eine Tür. ◄◄◄

Was ein Verb an Stammdaten braucht, steht in ``REQUIRED_FOR`` (``gaps``); die Eingabe-Leser
(``_int`` · ``amount_of`` · ``_days`` · ``_day`` · ``_text``) stehen hier, weil nur Handlungen
lesen, was hereinkommt.
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from ..core import clock
from ..core.config import payment_service_ready
from ..domain import voucher as vo
from ..models import (
    Order, ProcessStep,
    UserProfile, Voucher,
)
# Wer ohnehin alles sieht – Personal hat keine verengte Sicht (die eine Stelle).
from .voucher import (
    balance_of, changed_since_offer, deviation,
    expired, hold, inbound,
    is_billed, minus, next_reminder, of_step, parties_on,
    quotes_of, units_problem, where_of,
)
from .voucher_head import (
    destination, is_export,
)
from .voucher_money import (
    follow_up, papers_due, refundable,
)
from ..domain.errors import Conflict, Invalid, NotFound
from ..domain import policy
from .voucher_input import _int
from .voucher_billing import _accept, _bill, _correct, _export, _pay, _refund, _release, _remind, _reverse, _revoke, _tip, _writeoff, reversible
from .voucher_rules import NEEDS, gaps
from .voucher_offer import _add_party, _address, _agree, _ask, _currency, _decline, _incoterm, _issuer, _ownership, _price, _quote, _terms, _unask


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
#: Nur, wo **wir** ihn nennen (Einnahme): dann nimmt sie an (eine Gegenofferte ist ein
#: neuer Beleg).
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


def next_action(row: Voucher) -> str:
    """**Welche Handlung steht an dieser Stufe an?** – die, deren Lücken zählen.

    Nur die Lücken, die gerade im Weg stehen – keine Mängelliste über alle Stufen.
    """
    return "bill" if row.stage != vo.OFFER else "ask"


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
    if not policy.inside(viewer):
        # Die Gegenpartei darf nur, was ihre Rolle im Beleg hergibt – und nur, solange sie
        # tatsächlich angefragt ist.
        if not any(q.party_id == viewer.object_id for q in quotes):
            return []
        return [a for a in out if VERBS[a].allows(flow)]
    return out


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
        raise Invalid(f"Dafür fehlt {first['field_label']} bei «{first['record_label']}». "
                    f"{first['why']}"
                    + (f" (und {len(missing) - 1} weitere Angabe"
                       f"{'n' if len(missing) > 2 else ''})" if len(missing) > 1 else ""))
    flow = vo.of(row.direction)
    # **Der Satz nennt den richtigen Grund**: fehlt allein der Zugang (die Stufe stimmt),
    # sagt er das, nicht die Stufe.
    if (action in VERBS and not VERBS[action].allows(flow)
            and not policy.inside(viewer)):
        raise Conflict(f"«{action}» ist an diesem Beleg nicht Ihre Handlung – darüber "
                    f"entscheidet die andere Seite.")
    raise Conflict(f"«{action}» geht hier nicht: der Beleg steht auf "
                f"«{flow.label_of(row.stage)}».")


# ---------------------------------------------------------------------------
# ►► DIE HANDLUNGEN
# ---------------------------------------------------------------------------

def apply(db: Session, *, order: Order, step: ProcessStep, action: str,
          payload: dict[str, Any], actor: Optional[UserProfile] = None) -> Voucher:
    """**Eine Handlung am Beleg** – ein Endpunkt, eine Tabelle.

    Danach räumt der Beleg selbst nach (``follow_up``): Dokument hinaus, Stücke weiter.
    """
    row = of_step(db, step.id)
    if row is None:
        raise NotFound("Zu diesem Modul gibt es keinen Beleg.")
    if action not in VERBS:
        raise Invalid(f"«{action}» ist keine Handlung an einem Beleg.")
    # **Die Nutzlast weiss, um wen es geht** – beim Zuschlag steht die Gegenpartei dort,
    # und die Vollständigkeitsprüfung muss sie kennen, bevor ``_agree`` sie setzt.
    assert_allowed(db, row, action, actor, _int(payload.get("party")))
    run = VERBS[action].run
    if run is None:
        raise Conflict(f"«{action}» ändert den Beleg nicht – diese Handlung hat ihren "
                    f"eigenen Weg.")
    run(db, order=order, step=step, row=row, data=payload, actor=actor)
    db.flush()
    follow_up(db, order=order, step=step, row=row, actor=actor)
    return row


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
    "ask": Verb(stages=(vo.OFFER,), run=_ask, needs=NEEDS["ask"]),
    "unask": Verb(stages=(vo.OFFER,), run=_unask),
    "quote": Verb(stages=(vo.OFFER,), run=_quote, needs=NEEDS["quote"], party=IF_THEY_PRICE),
    "decline": Verb(stages=(vo.OFFER,), run=_decline, party=ALWAYS),
    "agree": Verb(stages=(vo.OFFER,), run=_agree, needs=NEEDS["agree"],
                  party=IF_WE_PRICE),
    # **Stornieren** – ein Wort in jeder Stufe (vor der Zusage erst, wenn etwas
    # hinausging, ``can``).
    "revoke": Verb(stages=(vo.OFFER, vo.AGREED, vo.BILLED), run=_revoke),
    # **DIE Rechnung** – eine Schwelle von ``agreed`` nach ``billed``.
    "bill": Verb(stages=(vo.AGREED,), run=_bill, needs=NEEDS["bill"]),
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


# ---------------------------------------------------------------------------
# ►► DIE GEGENPARTEI
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ►► KLEINE HELFER — jeder mit genau einer Aufgabe
# ---------------------------------------------------------------------------


