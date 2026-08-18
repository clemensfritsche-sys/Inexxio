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
from . import carriers, objects as obj, places


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
    if ch.key == vergabe.PLATTFORM and not carriers.available():
        # **Ohne Schlüssel gibt es den Kanal nicht** (K4). Er ist in der Oberfläche gar
        # nicht wählbar; hier steht die Regel, damit sie nicht nur eine Bitte ist.
        raise HTTPException(
            status_code=409,
            detail=("Es ist kein Frachtführer eingerichtet – über die Plattform lässt "
                    "sich darum nichts anfragen. Ohne Schlüssel gibt es diesen Weg "
                    "nicht; einen anderen Anbieter ersatzweise zu nehmen wäre eine "
                    "Wahl, die niemand getroffen hat."),
        )
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


def channel_availability() -> dict[str, Optional[str]]:
    """Welche Kanäle **jetzt** wählbar sind – ``None`` = geht, sonst der Grund.

    Das ist bewusst eine **andere Frage** als der generierte Katalog: der sagt, welche
    Kanäle es *gibt* (Beschriftung, Hinweis, ob sie Angebote kennen), diese Antwort sagt,
    ob sie *heute* benutzbar sind. Zwei Fragen, zwei Antworten – eine gemeinsame Liste
    wäre eine statische Datei, die eine Laufzeit-Tatsache behauptet.
    """
    out: dict[str, Optional[str]] = {k: None for k in vergabe.CHANNELS}
    if not carriers.available():
        out[vergabe.PLATTFORM] = ("Kein Frachtführer eingerichtet – ohne Schlüssel gibt "
                                  "es diesen Weg nicht.")
    return out


def add_offer(db: Session, award: Award, *, provider_object_id: Optional[int] = None,
              provider_name: Optional[str] = None, amount: Decimal = Decimal(0),
              currency: str = "CHF", days: Optional[int] = None,
              label: Optional[str] = None, carrier: Optional[str] = None,
              external_ref: Optional[str] = None) -> AwardOffer:
    """Ein Angebot eintragen (V2) – **je Kanal derselbe Vorgang**.

    Ob ein Mensch es im Portal tippt oder ein Adapter es aus einer Schnittstelle holt,
    ändert nichts an dieser Zeile. Genau das ist der Grund, warum es keinen zweiten
    Mechanismus für Rate-Shopping gibt.

    **Der Anbieter ist eine Objektnummer ODER ein Name.** Ein Frachtführer ist kein
    ERP-Datensatz; einen anzulegen wäre erfundene Daten. Beides leer ist ein Fehler –
    ein Angebot ohne Anbieter sagt nicht, wer es hält.
    """
    if not vergabe.CHANNELS[award.channel].offers:
        raise HTTPException(
            status_code=409,
            detail=(f"Der Kanal «{vergabe.CHANNELS[award.channel].label}» kennt keine "
                    f"Angebote – dort wird selbst bestellt und nur dokumentiert."),
        )
    name = (provider_name or "").strip() or None
    if provider_object_id is None and not name:
        raise HTTPException(400, "Ein Angebot ohne Anbieter sagt nicht, wer es hält.")
    if provider_object_id is not None:
        _assert_exists(db, provider_object_id, "Anbieter")
    if Decimal(amount) < 0:
        raise HTTPException(400, "Ein Angebot kann nicht negativ sein.")

    offer = AwardOffer(
        award_id=award.id,
        provider_object_id=int(provider_object_id) if provider_object_id else None,
        provider_name=name, carrier=carrier,
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
        award.provider_name = offer.provider_name
        award.carrier = offer.carrier
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
    # **Vergeben heisst beim Plattform-Kanal: Etikett kaufen.** Nicht als zweiter Schritt
    # daneben – die Vergabe IST der Kauf, und ein Etikett ohne Vergabe wäre eine Sendung,
    # zu der niemand ja gesagt hat. Scheitert der Kauf, scheitert die Vergabe (die
    # Transaktion rollt zurück): eine vergebene ohne Etikett wäre eine Zusage, die
    # niemand einlösen kann.
    if award.carrier and award.chosen_offer_id:
        _buy_label(db, award)
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


# ─── Der Kanal «Plattform» ───────────────────────────────────────────────────────

def quote(db: Session, award: Award, *, sender: carriers.Address,
          receiver: carriers.Address, parcel: carriers.Parcel,
          unit_ids: Iterable[int]) -> list[str]:
    """**Tarife holen** – und sie durch dieselbe Stelle schreiben wie ein getipptes Angebot.

    Das ist der ganze Kanal `plattform`: **Rate-Shopping IST eine Ausschreibung**, sie
    dauert nur 2 Sekunden statt 2 Tage. Darum gibt es hier keinen Zustandswechsel und
    keine zweite Tabelle – gerufen wird ``add_offer``, und der Zustand folgt daraus.

    **Gefragt werden ALLE eingerichteten Anbieter**, nicht ein ausgewählter: eine
    Ausschreibung fragt mehrere. Der Vorgänger wählte einen und fiel stillschweigend auf
    «manual» zurück – und genau darum merkte niemand, dass nie ein Tarif kam.

    Gibt die Meldungen zurück, die eine **leere** Liste erklären («Herkunftsland nicht
    unterstützt»). Ohne sie stünde da «keine Angebote», und niemand wüsste warum.
    """
    if award.channel != vergabe.PLATTFORM:
        raise HTTPException(
            status_code=409,
            detail=(f"Tarife gibt es nur beim Kanal «{vergabe.CHANNELS[vergabe.PLATTFORM].label}» "
                    f"– hier ist «{vergabe.CHANNELS[award.channel].label}» gewählt."),
        )
    if not vergabe.is_open(award.state):
        raise HTTPException(409, "Diese Vergabe ist zu Ende – Tarife ändern daran nichts.")
    for label, addr in (("Ausgangsort", sender), ("Ziel", receiver)):
        if not addr.complete:
            raise HTTPException(
                status_code=409,
                detail=(f"Dem {label} fehlt eine vollständige Anschrift – ohne sie kann "
                        f"kein Frachtführer einen Preis nennen."),
            )

    messages: list[str] = []
    for carrier in carriers.active():
        result = carrier.quote(sender, receiver, parcel)
        messages.extend(f"{carrier.label}: {m}" for m in result.messages)
        for row in result.offers:
            add_offer(
                db, award, provider_name=f"{row.carrier} · {row.service}",
                amount=row.amount, currency=row.currency, days=row.days,
                label=row.service, carrier=carrier.key, external_ref=row.ref,
            )
        if result.shipment_ref:
            # Was der Kauf später braucht. Der **Adapter** hat es gefüllt; hier wird es
            # nur aufbewahrt – der Aufrufer kennt die Feldnamen eines Anbieters nicht.
            award.shipment_ref = result.shipment_ref

    # **Die Vergabe hält ihre Stücke ab dem Angebot** (§15.5a): wer Tarife holt,
    # beschreibt ein Paket, und ein Paket hat einen Inhalt. Gebraucht wird er genau
    # einmal – beim Tracking, das die Ankunft meldet, ohne dass jemand am Ziel steht.
    award.unit_ids = [int(u) for u in unit_ids]
    db.flush()
    return messages


def track(db: Session, award: Award, *, actor_id: Optional[int]) -> tuple[str, str]:
    """**Wo ist die Sendung?** – und wenn sie da ist, entsteht die Ablage.

    Tracking ist eine **Beobachtung wie ein Scan**: dieselbe Tabelle, dieselbe eine
    Schreibstelle (``places.record``), nur ``source='tracking'``. Es ist keine zweite
    Wahrheit über den Ort – wer sie unterscheiden will, liest das Feld; wer nur wissen
    will, wo etwas liegt, merkt keinen Unterschied.

    Ein **gescheiterter** Transport wird nicht automatisch zu einer gescheiterten
    Vergabe: das ist eine Feststellung eines Menschen (V6, Grund Pflicht). Gemeldet wird
    er, mehr nicht – das System rührt ab ``vergeben`` nichts an, es meldet.
    """
    if not award.tracking_number or not award.carrier:
        raise HTTPException(
            status_code=409,
            detail="Diese Vergabe hat keine Sendungsnummer – es gibt nichts nachzuverfolgen.",
        )
    state = carriers.by_key(award.carrier).track(
        award.tracking_number, carrier=(award.provider_name or "").split(" · ")[0])
    if state.delivered and vergabe.is_open(award.state):
        deliver(db, award, unit_ids=award.unit_ids or [], actor_id=actor_id)
    return state.state, state.detail


def _buy_label(db: Session, award: Award) -> None:
    """Das gewählte Angebot kaufen → Etikett und Sendungsnummer.

    Gerufen aus ``grant`` und nirgends sonst: die Vergabe **ist** der Kauf. Ein eigener
    Endpunkt daneben wäre ein zweiter Weg zu einer Sendung, und dann gäbe es eine
    vergebene Vergabe ohne Etikett – eine Zusage, die niemand einlösen kann.
    """
    offer = db.query(AwardOffer).filter(AwardOffer.id == award.chosen_offer_id).first()
    if not offer or not offer.external_ref:
        return
    label = carriers.by_key(award.carrier).buy(
        offer.external_ref, shipment_ref=award.shipment_ref or "")
    award.label_url = label.label_url or None
    award.tracking_number = label.tracking_number or None
    award.tracking_url = label.tracking_url or None
    if label.shipment_ref:
        award.shipment_ref = label.shipment_ref


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
    # Nur **echte** Objektnummern auflösen: seit ein Anbieter ein Name sein darf, ist
    # ``provider_object_id`` oft leer – und ``None`` ist keine Nummer, die man nachschlägt.
    wanted = {o.provider_object_id for o in rows if o.provider_object_id}
    for extra in (award.provider_object_id, award.target_object_id):
        if extra:
            wanted.add(extra)
    known = places.resolve_holders(db, list(wanted)) if wanted else {}

    def ref(object_id):
        if not object_id or object_id not in known:
            return None
        h = known[object_id]
        return HolderRef(object_id=h.object_id, type=h.type, name=h.name)

    return AwardResponse(
        id=award.id, subject_object_id=award.subject_object_id,
        target=ref(award.target_object_id), state=award.state, channel=award.channel,
        provider=ref(award.provider_object_id), provider_name=award.provider_name,
        carrier=award.carrier, amount=award.amount,
        currency=award.currency, due_at=award.due_at, reason=award.reason,
        chosen_offer_id=award.chosen_offer_id,
        label_url=award.label_url, tracking_number=award.tracking_number,
        tracking_url=award.tracking_url,
        offers=[
            AwardOfferResponse(id=o.id, provider=ref(o.provider_object_id),
                               provider_name=o.provider_name, carrier=o.carrier,
                               amount=o.amount, currency=o.currency, days=o.days,
                               label=o.label)
            for o in rows
        ],
    )
