"""**Die Vergabe** – die eine Schreibstelle des Zyklus (ADR 009 §3.6, SYSTEM_LOGIC §7.3).

Der Ablauf steht in ``domain/vergabe`` (Zustände, Übergänge, Kanäle); hier steht, wie er
geschrieben wird. Ein zweiter Schreibweg wäre eine zweite Wahrheit – darum geht **jeder**
Zustandswechsel durch ``_move``, und das ruft ``vergabe.assert_transition``.

**Was dieses Modul NICHT tut:** es vergibt nie selbst. ``V3`` (angeboten → vergeben)
verlangt einen Menschen; das System darf Angebote **holen** und das günstigste
**vorwählen**, aber die Wahl treffen darf es nicht. Und ab ``vergeben`` rührt es nichts
mehr an – es meldet.

**Warum eine Vergabe nichts über den Ort weiss:** sie ist der kaufmännische Vorgang, der
Ort ist die Beobachtung. Erst wenn die Leistung **erbracht** ist, entsteht eine Ablage –
und die schreibt ``services/places``, wie jede andere auch. Ein Modul, das beides täte,
hätte wieder zwei Wahrheiten über denselben Vorgang.
"""

from datetime import datetime
from decimal import Decimal
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import vergabe
from ..models import Award, AwardOffer
from ..schemas.award import AwardOfferResponse, AwardResponse
from ..schemas.place import HolderRef
from . import objects as obj, places


def open_for(db: Session, subject_object_id: int,
             target_object_id: Optional[int] = None) -> Optional[Award]:
    """Die **offene** Vergabe eines Anlasses – oder ``None``.

    «Offen» ist abgeleitet (``vergabe.is_open``), keine zweite Liste. Eine gescheiterte
    zählt damit nicht mehr mit: genau deshalb kann die Fuhre eine neue bekommen, ohne
    dass zwei gleichzeitig auf ``vergeben`` stünden.
    """
    q = db.query(Award).filter(Award.subject_object_id == int(subject_object_id))
    if target_object_id is not None:
        q = q.filter(Award.target_object_id == int(target_object_id))
    for row in q.order_by(Award.id.desc()).all():
        if vergabe.is_open(row.state):
            return row
    return None


def request(db: Session, *, subject_object_id: int, target_object_id: Optional[int],
            channel: str, actor_id: Optional[int],
            provider_object_id: Optional[int] = None) -> Award:
    """Eine Vergabe **anfragen** (V1) – oder die offene zurückgeben, die es schon gibt.

    Idempotent, weil ein Modul mehrfach betrachtet wird, bevor jemand handelt: eine
    zweite Anfrage für dieselbe Fuhre wäre eine zweite Zeile, die niemand bestellt hat.
    """
    ch = vergabe.channel(channel)
    existing = open_for(db, subject_object_id, target_object_id)
    if existing:
        return existing

    if provider_object_id is not None:
        _assert_exists(db, provider_object_id, "Dritter")
    row = Award(
        subject_object_id=int(subject_object_id),
        target_object_id=int(target_object_id) if target_object_id else None,
        state=vergabe.ANGEFRAGT, channel=ch.key,
        provider_object_id=provider_object_id, actor_id=actor_id,
    )
    db.add(row)
    db.flush()
    return row


def add_offer(db: Session, award: Award, *, provider_object_id: int, amount: Decimal,
              currency: str = "CHF", days: Optional[int] = None,
              label: Optional[str] = None,
              external_ref: Optional[str] = None) -> AwardOffer:
    """Ein Angebot eintragen (V2) – **je Kanal derselbe Vorgang**.

    Ob ein Mensch es im Portal tippt oder ein Adapter es aus einer Schnittstelle holt,
    ändert nichts an dieser Zeile. Genau das ist der Grund, warum es keinen zweiten
    Mechanismus für Rate-Shopping gibt.
    """
    if not vergabe.CHANNELS[award.channel].offers:
        raise HTTPException(
            status_code=409,
            detail=(f"Der Kanal «{vergabe.CHANNELS[award.channel].label}» kennt keine "
                    f"Angebote – dort wird selbst bestellt und nur dokumentiert."),
        )
    _assert_exists(db, provider_object_id, "Anbieter")
    if Decimal(amount) < 0:
        raise HTTPException(400, "Ein Angebot kann nicht negativ sein.")

    offer = AwardOffer(
        award_id=award.id, provider_object_id=int(provider_object_id),
        amount=Decimal(amount), currency=(currency or "CHF").upper()[:3],
        days=days, label=label, external_ref=external_ref,
    )
    db.add(offer)
    if award.state == vergabe.ANGEFRAGT:
        _move(db, award, vergabe.ANGEBOTEN)
    db.flush()
    return offer


def offers(db: Session, award: Award) -> list[AwardOffer]:
    """Die Angebote, **günstigstes zuerst** – das ist die Vorwahl, nicht die Wahl.

    Sortiert wird hier und nicht im Adapter: welche Reihenfolge «am besten» heisst, ist
    eine fachliche Aussage und gehört nicht in eine Schnittstellen-Anbindung.
    """
    return (db.query(AwardOffer).filter(AwardOffer.award_id == award.id)
            .order_by(AwardOffer.amount.asc(), AwardOffer.id.asc()).all())


def cheapest(db: Session, award: Award) -> Optional[AwardOffer]:
    return next(iter(offers(db, award)), None)


def grant(db: Session, award: Award, *, offer_id: Optional[int],
          actor_id: Optional[int], provider_object_id: Optional[int] = None,
          amount: Optional[Decimal] = None, currency: Optional[str] = None,
          due_at: Optional[datetime] = None) -> Award:
    """**Vergeben** (V3) – die Wahl eines Menschen, nie des Systems.

    Beim Kanal ``selbst`` gibt es kein Angebot; dort werden Dritter, Preis und Termin
    unmittelbar genannt. Bei den übrigen Kanälen ist das gewählte **Angebot** die
    Grundlage – ein daneben getippter Preis wäre eine zweite Wahrheit über dieselbe
    Vereinbarung.
    """
    if vergabe.CHANNELS[award.channel].offers:
        if offer_id is None:
            raise HTTPException(400, "Zum Vergeben gehört das gewählte Angebot.")
        offer = (db.query(AwardOffer)
                 .filter(AwardOffer.id == offer_id,
                         AwardOffer.award_id == award.id).first())
        if not offer:
            raise HTTPException(404, "Dieses Angebot gehört nicht zu dieser Vergabe.")
        award.chosen_offer_id = offer.id
        award.provider_object_id = offer.provider_object_id
        award.amount, award.currency = offer.amount, offer.currency
    else:
        if not provider_object_id:
            raise HTTPException(400, "Selbst bestellt – wer erbringt die Leistung?")
        _assert_exists(db, provider_object_id, "Dritter")
        award.provider_object_id = int(provider_object_id)
        award.amount = Decimal(amount) if amount is not None else None
        award.currency = (currency or "CHF").upper()[:3] if amount is not None else None

    if due_at is not None:
        award.due_at = due_at
    award.actor_id = actor_id
    _move(db, award, vergabe.VERGEBEN)
    db.flush()
    return award


def deliver(db: Session, award: Award, *, unit_ids: Iterable[int],
            actor_id: Optional[int]) -> Award:
    """**Erbracht** (V4) – und erst jetzt entsteht die Ablage.

    Der Ort ist eine Beobachtung: er wird geschrieben, wenn etwas **angekommen** ist,
    nicht wenn es bestellt wurde. Geschrieben wird er über ``places.record`` – dieselbe
    eine Stelle wie überall; eine eigene hier wäre die zweite.
    """
    _move(db, award, vergabe.ERBRACHT)
    ids = [int(u) for u in unit_ids]
    if ids and award.target_object_id:
        places.record(db, ids, award.target_object_id, actor_id=actor_id,
                      source="tracking" if award.channel == vergabe.PLATTFORM else "scan")
    award.actor_id = actor_id
    db.flush()
    return award


def reject(db: Session, award: Award, *, reason: str, actor_id: Optional[int]) -> Award:
    """**Abgelehnt** (V5) – der Vorgang endet ohne Vergabe."""
    award.reason = (reason or "").strip() or None
    award.actor_id = actor_id
    _move(db, award, vergabe.ABGELEHNT)
    db.flush()
    return award


def fail(db: Session, award: Award, *, reason: str, actor_id: Optional[int]) -> Award:
    """**Gescheitert** (V6) – vergeben, aber nicht erbracht. **Grund ist Pflicht.**

    Kein Zurücknehmen: die Matrix geht nie rückwärts, und eine Korrektur ist ein neuer
    Eintrag (G5.1). Die Sache bekommt danach eine ganz normale **zweite** Vergabe – dass
    das geht, folgt von selbst daraus, dass ``gescheitert`` terminal ist und
    ``open_for`` sie damit nicht mehr findet.
    """
    award.reason = (reason or "").strip() or None
    award.actor_id = actor_id
    _move(db, award, vergabe.GESCHEITERT, reason=reason)
    db.flush()
    return award


# ─── intern ──────────────────────────────────────────────────────────────────────

def _move(db: Session, award: Award, target: str, *, reason: str = "") -> None:
    """**Die eine Schreibstelle für einen Zustandswechsel.**

    Sie fragt die Registry und nicht sich selbst; damit kann kein Aufrufer einen
    Übergang erfinden, den die Matrix nicht kennt – auch nicht versehentlich.
    """
    vergabe.assert_transition(award.state, target, reason=reason)
    award.state = target


def _assert_exists(db: Session, object_id: int, what: str) -> None:
    """Streng schreiben: ein Dritter, den es nicht gibt, ist ein Tippfehler.

    Gelesen wird dagegen tolerant – dieselbe Haltung wie beim Halter (``places``).
    """
    holder = places.resolve_holder(db, object_id)
    if not holder.known:
        raise HTTPException(400, f"{what} {obj.obj_nr(object_id)} gibt es nicht.")


def to_response(db: Session, award: Award) -> AwardResponse:
    """Die API-Form einer Vergabe – **eine** Stelle, zwei Leser.

    Der Auftrags-Router zeigt sie an der Fuhre, der Vergabe-Router als Datensatz. Sie
    zweimal zusammenzubauen hiesse, dass die eine Ansicht ein Feld bekommt und die andere
    nicht – und zwar erst dann, wenn es zählt.
    """
    rows = offers(db, award)
    wanted = {o.provider_object_id for o in rows}
    for extra in (award.provider_object_id, award.target_object_id):
        if extra:
            wanted.add(extra)
    known = places.resolve_holders(db, list(wanted)) if wanted else {}

    def ref(object_id):
        if not object_id:
            return None
        h = known[object_id]
        return HolderRef(object_id=h.object_id, type=h.type, name=h.name)

    return AwardResponse(
        id=award.id, subject_object_id=award.subject_object_id,
        target=ref(award.target_object_id), state=award.state, channel=award.channel,
        provider=ref(award.provider_object_id), amount=award.amount,
        currency=award.currency, due_at=award.due_at, reason=award.reason,
        chosen_offer_id=award.chosen_offer_id,
        offers=[
            AwardOfferResponse(id=o.id, provider=ref(o.provider_object_id),
                               amount=o.amount, currency=o.currency, days=o.days,
                               label=o.label)
            for o in rows
        ],
    )
