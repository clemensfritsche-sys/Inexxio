"""**Der Beleg als Dienst** — Angebotsspiegel, Positionen, Forderungen, Zahlungen.

Der Neuaufbau des Zahlungsmoduls (``docs/neuaufbau-zahlungsmodul.md``). Fachlich dasselbe
wie sein Vorgänger ``services/deal``; verschieden ist die **Form**, und zwar an drei
Stellen, an denen der Vorgänger die Hälfte seiner Zeilen verbraucht hat:

1. ►►► **Ein Verb wird an EINER Stelle deklariert.** ◄◄◄ ``VERBS`` sagt je Verb: *in
   welcher Stufe · welche Stammdaten · wer darf · welche Funktion*. Beim Vorgänger waren
   das vier Tabellen (``ACTIONS`` · ``REQUIRED_FOR``/``_UP_TO`` · ``party_actions`` ·
   ``HANDLERS``), und die vierte bekam ein neues Verb nicht mit.

2. ►►► **Der Angebotsspiegel ist eine Tabelle.** ◄◄◄ Damit entfallen «nie an Ort ändern»,
   das Neubauen der ganzen Liste bei jeder Änderung und die JSONB-Containment-Abfrage für
   «woran ist dieser Betrachter beteiligt».

3. ►►► **Die Position gibt es in EINER Form.** ◄◄◄ Beim Vorgänger dreimal (abgeleitet ·
   je Angebot kopiert · eingefroren), angefasst an 21 Stellen. Eingefroren wird hier durch
   die **Stufe**: solange ``offer``, zieht ``sync_lines`` aus dem Prozess nach.

Und drei Spalten sind **Ableitungen** geworden – ``party_id``, ``amount``, ``due_days``
standen beim Vorgänger neben der gewählten Angebotszeile und wurden beim Zuschlag
hineinkopiert. Damit konnte derselbe Beleg zwei Dinge sagen, und eine eigene Regel musste
das verhindern. Als Ableitung kann der Widerspruch **nicht entstehen**.

**Kein Import aus ``deal``/``purchase``/``money``** – ein Quelltext-Wächter hält es so.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import payment_service_ready
from ..domain import currency as cur
from ..domain import incoterms as inc
from ..domain import modules
from ..domain import voucher as vo
from ..models import (
    Article, Instance, InstanceUnit, Order, OrderUnit, ProcessEvent, ProcessStep,
    UserProfile, Voucher, VoucherEntry, VoucherLine, VoucherQuote,
)
from ..models.process_event import KIND_START, KIND_STEP
from . import address, lookup, people, qrbill, sites

#: **Wer ohnehin alles sieht.** Für sie gibt es keine verengte Sicht – sie arbeiten im
#: ERP, und dort steht der ganze Auftrag.
STAFF_ROLES: tuple[str, ...] = ("admin", "employee")


# ---------------------------------------------------------------------------
# ►►► DIE VERBEN — EINE Deklaration je Verb ◄◄◄
# ---------------------------------------------------------------------------
#
# Beim Vorgänger stand ein Verb an **vier** Stellen, und das widersprach der eigenen
# Hausregel («eine Sache, eine Stelle»). Hier stehen die vier Fragen über ein Verb in
# **einer Zeile**:
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

#: Die eine Gegenhandlung an einer Geld-Zeile.
REVERSE = "reverse"


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
# *«Wenn das Modul zu wenig Angaben hat, um seinen Prozess abzuwickeln, dann muss es Alarm
# schlagen.»* – **Das ist kein neuer Mechanismus, es ist ``StepNeed`` für Stammdaten**:
# eine Zeile (wo sie hingehört · was fehlt · warum), **kein** Zustand und **kein**
# Pausenwert. Durchgesetzt über ``can``: fehlt etwas, führt ``can`` das Verb nicht – der
# Knopf ist gar nicht da –, und ``assert_allowed`` weist an derselben Liste ab.
#
# **Gestaffelt und kumulativ**: eine Anfrage braucht weniger als eine Rechnung. Stünde
# alles vor der ersten Handlung, hielte eine Angabe das Modul an, die erst in drei
# Schritten zählt – und man müsste sie erfinden, um weiterzukommen.
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
    "charge": (
        ("us", "iban", "IBAN",
         "Auf eine Rechnung gehört, wohin überwiesen wird."),
        ("party", "uid", "UID / MWST-Nummer",
         "Beim Reverse Charge schuldet der Leistungsempfänger die Steuer – ohne seine "
         "Nummer trägt das Verfahren nicht."),
    ),
}


# ---------------------------------------------------------------------------
# ►► LESEN
# ---------------------------------------------------------------------------

def of_step(db: Session, step_id: int) -> Optional[Voucher]:
    """Der aktive Beleg eines Moduls – oder ``None``. **Die eine Lesestelle.**"""
    return (
        db.query(Voucher)
        .filter(Voucher.step_id == step_id, Voucher.is_active.is_(True))
        .first()
    )


def entries_of(db: Session, row: Voucher) -> list[VoucherEntry]:
    """Die Geld-Zeilen, älteste zuerst – nur die gültigen."""
    return (
        db.query(VoucherEntry)
        .filter(VoucherEntry.voucher_id == row.id, VoucherEntry.is_active.is_(True))
        .order_by(VoucherEntry.booked_on, VoucherEntry.id)
        .all()
    )


def quotes_of(db: Session, row: Voucher) -> list[VoucherQuote]:
    """Der Angebotsspiegel – in der Reihenfolge, in der angefragt wurde."""
    return (
        db.query(VoucherQuote)
        .filter(VoucherQuote.voucher_id == row.id, VoucherQuote.is_active.is_(True))
        .order_by(VoucherQuote.id)
        .all()
    )


def lines_of(db: Session, row: Voucher) -> list[VoucherLine]:
    """Die Positionen – in ihrer Reihenfolge auf dem Papier."""
    return (
        db.query(VoucherLine)
        .filter(VoucherLine.voucher_id == row.id, VoucherLine.is_active.is_(True))
        .order_by(VoucherLine.position, VoucherLine.id)
        .all()
    )


# ---------------------------------------------------------------------------
# ►►► DIE DREI ABLEITUNGEN — was beim Vorgänger drei Spalten waren ◄◄◄
# ---------------------------------------------------------------------------
#
# *mit wem* · *was vereinbart ist* · *welche Zahlungsfrist* standen als Spalten neben der
# gewählten Angebotszeile und wurden beim Zuschlag hineinkopiert. Damit konnte derselbe
# Beleg zwei Dinge sagen – und eine eigene Regel musste verhindern, dass der Betrag von
# der Summe der Positionen abweicht. **Als Ableitung kann der Widerspruch gar nicht
# entstehen.**

def chosen_quote(db: Session, row: Voucher) -> Optional[VoucherQuote]:
    """**Die Angebotszeile, bei der zugesagt wurde** – oder ``None``.

    Sie ist die Antwort auf *mit wem · zu welchem Betrag · zu welchen Fristen*. Der
    Zustand ``gewaehlt`` entsteht nicht durch Tippen, sondern dadurch, dass ``_agree``
    hier zugesagt hat – ein Zustand ist eine Folge.
    """
    return next((q for q in quotes_of(db, row) if q.state == vo.CHOSEN), None)


def party_of(db: Session, row: Voucher) -> Optional[int]:
    """**Mit wem** – die Objektnummer der gewählten Gegenpartei."""
    q = chosen_quote(db, row)
    return q.party_id if q is not None else None


def agreed_amount(db: Session, row: Voucher) -> Optional[Decimal]:
    """**Was vereinbart ist** – der Betrag der gewählten Zeile."""
    q = chosen_quote(db, row)
    return q.amount if q is not None else None


def due_days_of(db: Session, row: Voucher) -> Optional[int]:
    """**Die vereinbarte Zahlungsfrist** – aus ihr kommen Fälligkeit und Vorauszahlung."""
    q = chosen_quote(db, row)
    return q.payment_days if q is not None else None


def balance_of(db: Session, row: Voucher) -> vo.Balance:
    """Die vier Zahlen dieses Belegs – gerechnet in ``domain/voucher``, gelesen hier."""
    return vo.balance(agreed_amount(db, row),
                      [(e.kind, e.amount) for e in entries_of(db, row)])


# ---------------------------------------------------------------------------
# ►►► DIE POSITIONEN — eine Form, und die Stufe friert sie ein ◄◄◄
# ---------------------------------------------------------------------------

def process_lines(db: Session, order: Order) -> list[tuple[int, int]]:
    """**Was steht im Auftrag?** – je Artikel eine Zeile ``(article_id, Stück)``.

    Derselbe Weg, aus dem der Prozess überall rechnet: offene Zugehörigkeit →
    Einzelinstanz → Instanz → Artikel. Sortiert, damit die Reihenfolge nicht von der
    Datenbank abhängt.

    **Über den ganzen Auftrag und nicht über den einzelnen Schritt.** Ein Angebot
    entsteht, *bevor* die Stücke am Modul ankommen – ein Beleg am Ende der Kette hätte
    sonst bis zuletzt eine leere Zeile. Und es ist fachlich richtig: dieselben sechs
    Wellen sind es, für die ich das Härten einkaufe und die ich danach verkaufe.
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


def sync_lines(db: Session, row: Voucher, order: Order) -> list[VoucherLine]:
    """►►► **Die Positionen aus dem Prozess nachziehen — NUR vor der Zusage.** ◄◄◄

    Das ist der ganze Einfrier-Mechanismus: solange der Beleg auf ``offer`` steht, sind
    Artikel und Mengen das, was im Auftrag steht; ab der Zusage nie wieder. Kein Feld je
    Zeile, keine zweite Tabelle, keine Kopie – und damit auch keine dritte Form, die beim
    nächsten Feld vergessen wird.

    **Was ein Mensch eingetragen hat, überlebt** (Preis, Satz, Zoll): nachgezogen werden
    Artikel und Menge, alles andere bleibt an seiner Zeile stehen. Eine Zeile, deren
    Artikel aus dem Auftrag verschwunden ist, verschwindet mit ihm – sie stünde sonst auf
    einem Beleg über etwas, das der Auftrag nicht mehr enthält.

    **Eine Zeile ohne Artikel bleibt immer** (Miete, Lohn, Gebühr): sie kommt nicht aus
    dem Prozess, also kann der Prozess sie auch nicht zurücknehmen.
    """
    rows = lines_of(db, row)
    if row.stage != vo.OFFER:
        return rows
    counts = dict(process_lines(db, order))
    by_article = {r.article_id: r for r in rows if r.article_id is not None}
    free = [r for r in rows if r.article_id is None]
    order_index = {a: i for i, a in enumerate(counts)}
    for article, n in counts.items():
        found = by_article.get(article)
        if found is None:
            found = VoucherLine(voucher_id=row.id, article_id=article,
                                quantity=n, vat=vo.DEFAULT_VAT,
                                position=order_index[article])
            db.add(found)
            by_article[article] = found
        else:
            found.quantity = n
            found.position = order_index[article]
    for article, found in list(by_article.items()):
        if article not in counts:
            # **Soft-Delete wie überall im Haus** – ein Beleg, der einmal eine Zeile
            # trug, soll sie nicht spurlos verlieren.
            found.is_active = False
            by_article.pop(article)
    for i, found in enumerate(free):
        found.position = len(counts) + i
    db.flush()
    return lines_of(db, row)


def line_dicts(db: Session, row: Voucher) -> list[dict[str, Any]]:
    """Die Positionen in der Form, in der ``domain/voucher`` rechnet.

    Die Mathematik kennt keine Datenbank: sie bekommt ``{quantity, price, vat}`` und gibt
    Netto, Steuer und Brutto zurück. Diese Übersetzung steht **einmal**.
    """
    return [{"quantity": ln.quantity,
             "price": str(ln.price) if ln.price is not None else None,
             "vat": ln.vat}
            for ln in lines_of(db, row)]


def priced_dicts(db: Session, row: Voucher) -> list[dict[str, Any]]:
    """Nur die Positionen, die wirklich einen Preis tragen.

    Bei einer **Ausgabe** gibt es keine – dort nennt die Gegenpartei eine Summe, und die
    Steuer steht auf *ihrer* Rechnung. Der Unterschied ist damit eine **Zahl**, keine
    Fallunterscheidung nach Richtung.
    """
    return [ln for ln in line_dicts(db, row) if ln["price"] is not None]


def embed_lines(db: Session, row: Voucher) -> list[dict[str, Any]]:
    """Die Positionen **mit Namen und Zoll-Angaben** – das, was die Gegenpartei liest.

    ►►► **Zoll: der Artikel belegt vor, der Beleg trägt den Wert.** ◄◄◄ Die
    Zolltarifnummer ist eine Eigenschaft der **Sache**; welche auf *diesem* Beleg steht,
    ist eine Aussage **dieses Geschäfts** – dieselbe Beziehung wie beim Preis. Steht in
    der Zeile ein Wert, gilt er; sonst der des Artikels. **Zurückgeschrieben wird
    nichts** – ein Beleg korrigiert keine Stammdaten.

    **Der Satz reist als Schlüssel, mit Zahl und Name daneben**: seit *Export* und
    *Reverse Charge* zwei Katalogzeilen sind, ist «0.00» mehrdeutig – und eine Anzeige,
    die «normal %» schreibt, weil sie den Schlüssel für eine Zahl hält, ist genau der
    Fehler, den eine zweite Auflösung im Browser produziert.

    Eine Abfrage für alle Zeilen, nicht eine je Zeile.
    """
    rows = lines_of(db, row)
    ids = [ln.article_id for ln in rows if ln.article_id is not None]
    found = {a.id: a for a in db.query(Article).filter(Article.id.in_(ids)).all()} \
        if ids else {}
    out: list[dict[str, Any]] = []
    for ln in rows:
        art = found.get(ln.article_id) if ln.article_id is not None else None
        out.append({
            "id": ln.id,
            "article_id": ln.article_id,
            "article_object_id": art.object_id if art else None,
            "article_name": art.name if art else "",
            "quantity": ln.quantity,
            "hs_code": ln.hs_code or (art.hs_code if art else None) or None,
            "origin_country": (ln.origin_country
                               or (art.origin_country if art else None) or None),
            # ►►► **Ein Betrag verlässt den Dienst in der Stelligkeit seiner Währung**
            # (Testnotiz #931). ◄◄◄ Die Spalte ist `NUMERIC(18, 4)` – gross genug für
            # jede Währung –, und `str()` schreibt ihre volle Skala aus: «30.0000».
            # Das ist keine Anzeigefrage der Oberfläche: dieselbe Zahl steht gleich im
            # Eingabefeld, und wer sie dort liest, tippt vier Nachkommastellen weiter.
            # Gerundet wird darum **hier**, an der einen Stelle, an der ein Betrag das
            # Haus verlässt – und mit der Stelligkeit der Währung, nie fest auf zwei
            # (JPY hat null, KWD drei).
            "price": _money(ln.price, row.currency),
            "vat": vo.assert_vat(ln.vat),
            "vat_rate": str(vo.vat_of(ln.vat)),
            "vat_label": vo.vat_label(ln.vat),
            "vat_note": vo.vat_note(ln.vat),
        })
    return out


# ---------------------------------------------------------------------------
# ►► ANLAGE — mit der Freigabe, idempotent
# ---------------------------------------------------------------------------

def house_currency(db: Session) -> str:
    """**Die Währung des Hauses** – die des Betreibers, tolerant gelesen.

    Gibt es (noch) keinen Betreiber, gilt ``currency.DEFAULT``: ein harter Fehler beim
    Freigeben eines Auftrags wäre die falsche Antwort auf eine fehlende Stammdatenzeile.
    """
    operator = sites.find_operator(db)
    try:
        return cur.assert_code(getattr(operator, "currency", None))
    except ValueError:
        return cur.DEFAULT


def issuer_of(db: Session, actor_id: Optional[int]) -> Optional[int]:
    """**Welche unserer Gesellschaften stellt den Beleg?** – die des Freigebenden.

    ``None`` heisst «der Betreiber» – der Rückfall bleibt, er ist nur nicht die Regel.
    """
    if actor_id is None:
        return None
    u = db.query(UserProfile).filter(UserProfile.id == actor_id).first()
    return getattr(u, "company_object_id", None)


def instantiate_for_order(db: Session, order: Order,
                          *, actor_id: Optional[int] = None) -> None:
    """Jedes Beleg-Modul dieses Auftrags bekommt seinen Beleg.

    **Bei der Freigabe und nicht beim Erreichen**: mit wem und worüber gehandelt wird,
    steht in der Definition, und ein Angebot einzuholen dauert – wer erst beim Erreichen
    anfragt, wartet die Frist ab, nachdem alles andere fertig ist.

    Idempotent (der partielle Unique-Index trägt); ohne ein solches Modul ein No-op.
    """
    rows = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id,
                ProcessStep.module_type == modules.BELEG)
        .all()
    )
    for step in rows:
        if of_step(db, step.id) is not None:
            continue
        db.add(Voucher(
            order_id=order.id, step_id=step.id,
            direction=vo.assert_direction(
                modules.get(step.module_type).direction_of(step.config)),
            # Die Währung kommt vom Betreiber, nicht aus einem Feld: der Normalfall ist
            # die Hauswährung, und ihn zu tippen wäre eine Eingabe mit genau einer
            # richtigen Antwort.
            currency=house_currency(db),
            issuer_company_id=issuer_of(db, actor_id),
            stage=vo.OFFER,
        ))
    if rows:
        db.flush()


# ---------------------------------------------------------------------------
# ►► WER SIEHT WAS — und wer darf was
# ---------------------------------------------------------------------------

def mine(db: Session, viewer: Optional[UserProfile]) -> Optional[list[Voucher]]:
    """**Woran ist dieser Betrachter beteiligt?** ``None`` = an allem.

    Beteiligt ist, wer **angefragt** wurde – seine Zeile steht im Angebotsspiegel. Seit
    der eine Tabelle ist, ist das eine gewöhnliche ``JOIN``-Bedingung statt einer
    JSONB-Containment-Abfrage.

    **Personal bekommt ``None``** – wer ohnehin ins ERP darf, braucht keine verengte
    Sicht. **Sonst fragt diese Funktion nicht nach der Rolle**: jeder darf Gegenpartei
    sein – die Rolle sagt, was jemand *für uns* tut, nicht ob wir mit ihm Geld austauschen.
    """
    if viewer is None or viewer.role in STAFF_ROLES:
        return None
    if viewer.object_id is None:
        return []
    return (
        db.query(Voucher)
        .join(VoucherQuote, VoucherQuote.voucher_id == Voucher.id)
        .filter(VoucherQuote.party_id == viewer.object_id,
                VoucherQuote.is_active.is_(True))
        .all()
    )


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
    head = _head_for(db, row, look)
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
                if getattr(issuer_company(db, row), "iban_encrypted", None):
                    continue
                out.append(_gap(sides["us"], label, why))
                continue
            if not _has(sides[side], field):
                out.append(_gap(sides[side], label, why))
    return out


def _head_for(db: Session, row: Voucher, party_id: Optional[int]) -> dict[str, Any]:
    """Der Belegkopf, wie er **mit dieser Partei** aussähe – ohne den Beleg zu ändern.

    Dieselbe Ableitung wie ``document_head``; ein zweiter Kopf-Aufbau daneben wäre die
    zweite Wahrheit, die beim nächsten Feld auseinanderläuft.
    """
    return document_head(db, row, won=True, party_id=party_id)


def next_action(db: Session, row: Voucher) -> str:
    """**Welche Handlung steht an dieser Stufe an?** – die, deren Lücken zählen.

    Eine Liste aller Lücken über alle Stufen wäre eine Mängelliste statt einer Auskunft:
    sie nennte Angaben, die erst in drei Schritten gebraucht werden, und niemand wüsste,
    welche gerade im Weg steht.
    """
    return "charge" if row.stage != vo.OFFER else "ask"


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

    Stufe **mal** Rolle **mal** Vollständigkeit, an einer Stelle – dieselbe Antwort reist
    mit (``can`` im Embed) und weist in ``assert_allowed`` ab. **Auskunft und Tor**, nie
    zwei Massstäbe.
    """
    flow = vo.of(row.direction)
    out = [k for k, v in VERBS.items() if row.stage in v.stages]
    rows = entries_of(db, row)
    # ►►► **Ohne Rechnung keine Zahlung.** ◄◄◄ Man kassiert nicht, was niemand gefordert
    # hat. Die Vorauszahlung verliert nichts – sie ist «erst fordern, dann zahlen».
    if not any(e.kind == vo.CHARGE for e in rows):
        out = [a for a in out if a != "pay"]
    # ►►► **Stornieren geht, solange es einen stornierbaren BELEG gibt.** ◄◄◄ Drei Dinge
    # zählen nicht: eine **Zahlung** ist kein Beleg, sondern ein Ereignis (sie wird durch
    # eine zweite Zahlung korrigiert); eine **Gegenbuchung** storniert man nicht; und eine
    # bereits **stornierte** Zeile ebenso wenig – sonst entstünde eine Kette aus
    # Vorzeichen, in der niemand mehr sagen kann, was gilt.
    already = {e.reverses_id for e in rows if e.reverses_id is not None}
    if not any(e.kind == vo.CHARGE and e.reverses_id is None and e.id not in already
               for e in rows):
        out = [a for a in out if a != REVERSE]
    # ►►► **Online bezahlen: drei Bedingungen, alle hier.** ◄◄◄ Nur wo das Geld **zu uns**
    # fliesst (ein Zahlungsdienst zieht ein, er überweist nicht in unserem Namen), nur mit
    # eingerichtetem Dienst (sonst ein Knopf, der garantiert in einem leeren Dialog
    # endet), und nur wenn etwas **offen** ist.
    if not (flow.collects and payment_service_ready() and balance_of(db, row).open > 0):
        out = [a for a in out if a != "pay_online"]
    # **Zurückerstatten geht nur, wo auch eingezogen wurde** – und nur, wenn eine
    # Karten-Zahlung dasteht, die man zurückgeben kann.
    if not (flow.collects and payment_service_ready() and refundable(db, row)):
        out = [a for a in out if a != "refund_online"]
    # ►►► **EINE Rechnung je Modul.** ◄◄◄ Steht sie, bleibt nur die **Gutschrift** –
    # das ist kein zweites Verb, sondern derselbe Knopf mit negativem Betrag; gesperrt ist
    # allein die zweite *positive* Forderung, und das prüft ``_charge``.
    if viewer is not None and viewer.role not in STAFF_ROLES:
        # Die Gegenpartei darf nur, was ihre Rolle im Beleg hergibt – und nur, solange sie
        # tatsächlich angefragt ist.
        if not any(q.party_id == viewer.object_id for q in quotes_of(db, row)):
            return []
        return [a for a in out if VERBS[a].allows(flow)]
    # ►►► **Was Angaben braucht, die es nicht gibt, steht hier nicht.** ◄◄◄ Die Lücken
    # speisen ``can`` – die Vollständigkeit ist damit **keine zweite Regel**. Nur Verben,
    # die nach aussen wirken: eine Absage, ein Storno und jede Geld-Zeile müssen möglich
    # bleiben, sonst wäre eine halbe Anschrift eine Sackgasse.
    return [a for a in out if not (VERBS[a].needs and gaps(db, row, action=a))]


def assert_allowed(db: Session, row: Voucher, action: str,
                   viewer: Optional[UserProfile],
                   party_id: Optional[int] = None) -> None:
    """►►► **Das Tor zu ``can`` – zwei Formen einer Regel, ein Namensstamm.** ◄◄◄

    Sie liest **dieselbe** Liste: ein zweiter, milderer Massstab wäre ein Knopf, der
    bereitsteht und dann scheitert, oder eine Tür, die etwas durchlässt, das niemand
    anbietet. Öffentlich, weil nicht jedes Verb durch ``apply`` läuft.
    """
    if action in can(db, row, viewer):
        return
    # **«Geht nicht» ohne «woran es liegt» ist eine Sackgasse mit Ausrufezeichen.** Es gibt
    # zwei Gründe, und sie verlangen verschiedene Handlungen: die **Stufe** (zu früh oder
    # zu spät) und eine **fehlende Angabe** (hingehen und eintragen).
    missing = (gaps(db, row, action=action, party_id=party_id)
               if action in VERBS and VERBS[action].needs else [])
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
    """**Eine Handlung am Beleg** – ein Endpunkt, eine Tabelle."""
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
        # **Nicht jedes Verb in ``can`` ändert den Beleg.** ``pay_online`` löst eine
        # Zahlung aus und bucht nichts; es hat seinen eigenen Weg. Ohne diese Zeile wäre
        # der Zugriff ein Fehler an der Tür statt eines Satzes.
        raise HTTPException(
            status_code=409,
            detail=(f"«{action}» ändert den Beleg nicht – diese Handlung hat ihren "
                    f"eigenen Weg."))
    run(db, order=order, step=step, row=row, data=payload, actor=actor)
    db.flush()
    return row


def _currency(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**In welcher Währung wird gehandelt?** – eine je Beleg, nicht je Zeile.

    **Umgerechnet wird nichts.** Ein Kurs hat ein Datum und eine Quelle; wer ohne beides
    umrechnet, erfindet Zahlen. Dass es nach der Zusage nicht mehr geht, sagt ``VERBS``.
    """
    try:
        row.currency = cur.assert_code(data.get("currency"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _issuer(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Wer stellt diesen Beleg?** – der Fall, dass jemand für eine Schwester anbietet.

    **Nur eine unserer Gesellschaften**: eine Objektnummer, die auf nichts zeigt, wäre auf
    einem Beleg schlimmer als gar keine – sie sieht aus wie eine Angabe.
    """
    value = _int(data.get("issuer"))
    if value is not None and sites.by_object_id(db, value) is None:
        raise HTTPException(status_code=400,
                            detail=f"«{value}» ist keine unserer Gesellschaften.")
    row.issuer_company_id = value


def _incoterm(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
              data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Die Lieferbedingung** (Incoterms 2020) – wer Fracht, Versicherung und Zoll trägt.

    **Ein Katalog, kein Freitext**: «DAT» ist die Klausel von 2010 – wer sie schickt, soll
    das lesen statt still etwas Ungültiges zu vereinbaren. **Der benannte Ort ist Pflicht,
    sobald eine Klausel steht**: bei ``FCA`` entscheidet genau er, wo das Risiko übergeht.
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
                    f"keine Vereinbarung (z. B. «{key} Rorschach»)."))
    row.incoterm = key
    row.incoterm_place = place if key else None


def _price(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Die Positionen bepreisen — ein eigenes Verb, und das ist der Punkt.** ◄◄◄

    Beim Vorgänger reisten die Preise in der Nutzlast des **Anfragens** mit: man tippte
    sie und schickte sie im selben Zug hinaus. Damit gab es keinen Zustand «geschrieben,
    aber noch nicht angeboten» – und die Hausregel «gespeichert, nicht abgeschickt» galt
    ausgerechnet für das Herzstück des Belegs nicht.

    Hier ist die **Position der Beleg**: sie wird geschrieben, sooft jemand tippt, und
    ``ask`` schickt sie hinaus. Zwei Handlungen, zwei Verben.

    **Die Menge kommt nie aus der Nutzlast** – sie ist die Zahl der Einzelinstanzen im
    Auftrag (``sync_lines``). Eine getippte wäre die zweite Aussage über dieselbe Sache.

    **Preis und Satz nur, wo WIR den Preis nennen**; die Zoll-Angaben in beiden
    Richtungen – sie beschreiben die Ware, nicht das Angebot.
    """
    flow = vo.of(row.direction)
    rows = {ln.id: ln for ln in sync_lines(db, row, order)}
    for raw in data.get("lines") or []:
        found = rows.get(_int(raw.get("id")))
        if found is None:
            continue
        if flow.quoted_by == vo.BY_US:
            if "price" in raw:
                found.price = _amount(raw.get("price"), row.currency,
                                      allow_negative=True)
            if "vat" in raw:
                try:
                    found.vat = vo.assert_vat(raw.get("vat") or vo.DEFAULT_VAT)
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e))
        if "hs_code" in raw:
            found.hs_code = _text(raw.get("hs_code"), 12)
        if "origin_country" in raw:
            found.origin_country = _text(raw.get("origin_country"), 60)
    db.flush()


def _ask(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Die Gegenparteien **anfragen** bzw. ihnen **anbieten**.

    **Ohne Angabe sind es alle zugelassenen.** Steht in der Definition genau eine, ist die
    Wahl zur Laufzeit keine Wahl. Wo die Definition **niemanden** nennt, heisst das
    **frei**: dann muss die Nutzlast sagen, wen man fragt.

    ►►► **Wer den Preis nennt, schickt ihn mit.** ◄◄◄ Bei einer **Ausgabe** geht die Zeile
    leer hinaus, und das ist ihr Sinn. Bei einer **Einnahme** ist der Betrag die
    **Brutto-Summe der Positionen** – kein zweites Feld daneben: zwei Zahlen über dieselbe
    Sache liefen auseinander, und ein Angebot ohne Preis ist keines.
    """
    flow = vo.of(row.direction)
    allowed = modules.Beleg.parties_allowed(step.config)
    wanted = list(data.get("parties") or []) or allowed
    if not wanted:
        raise HTTPException(
            status_code=400,
            detail=(f"Ohne {vo.PARTY} gibt es nichts anzufragen – dieses Modul lässt "
                    f"jeden zu, also muss hier stehen, wen es betrifft."))
    lead, days = _days(data.get("lead_days")), _days(data.get("payment_days"))
    priced = priced_dicts(db, row) if flow.quoted_by == vo.BY_US else []
    if flow.quoted_by == vo.BY_US:
        if not priced:
            raise HTTPException(
                status_code=400,
                detail=(f"Ohne Preis gibt es nichts anzubieten – bei einer {flow.label} "
                        f"nennen wir ihn, nicht der {vo.PARTY}."))
        _assert_terms(lead, days)
    amount = vo.gross_of(priced, row.currency) if priced else None
    seen = {q.party_id for q in quotes_of(db, row)}
    for value in wanted:
        number = _party(db, step=step, value=value, flow=flow)
        if number is None or number in seen:
            continue
        seen.add(number)
        db.add(VoucherQuote(
            voucher_id=row.id, party_id=number,
            state=vo.QUOTED if priced else vo.ASKED,
            amount=amount, lead_days=lead, payment_days=days,
            # **Wann die Zeile hinausging** – die Chronik fragt danach, und das weiss nur
            # der Moment, in dem es passiert.
            sent_on=date.today(),
        ))
    db.flush()


def _quote(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Einen Preis an **einer** Angebotszeile eintragen.

    **Wer eintragen darf, entscheidet nicht die Nutzlast**: eine Gegenpartei trifft
    ausschliesslich ihre eigene Zeile (``_target`` liest den angemeldeten Benutzer).

    **Nur gesendete Felder wirken** – wer nur eine Frist nachreicht, nennt keinen Preis,
    und wer nur den Preis nachreicht, verliert die Fristen nicht. Die Regel steht im
    **Dienst** und nicht nur an der Tür: die Tür ist nicht der einzige Aufrufer.
    """
    line = _target(db, row, data, actor)
    if "amount" in data:
        line.amount = _amount(data.get("amount"), row.currency)
    if "lead_days" in data:
        line.lead_days = _days(data.get("lead_days"))
    if "payment_days" in data:
        line.payment_days = _days(data.get("payment_days"))
    # **Beide Fristen sind Pflicht, geprüft am ERGEBNIS** – aus ihnen kommen Termin und
    # Fälligkeit. Auf ``is None``, nicht auf ``not value``: die Null ist eine Angabe
    # («Sofort» · «Vorauszahlung»).
    if line.amount is None:
        raise HTTPException(status_code=400,
                            detail="Ohne Betrag ist es keine Offerte.")
    _assert_terms(line.lead_days, line.payment_days)
    line.state = vo.QUOTED
    line.sent_on = line.sent_on or date.today()


def _decline(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Eine Angebotszeile **absagen** – die eine Antwort, die in beide Richtungen dasselbe
    bedeutet. Der Preis fällt mit ihr weg: **abgesagt ist abgesagt**."""
    line = _target(db, row, data, actor)
    line.state = vo.DECLINED
    line.amount = None
    line.lead_days = None
    line.payment_days = None


def _agree(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
           data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Den Zuschlag geben** – ab hier ist eine zweite Partei gebunden. ◄◄◄

    Die gewählte Zeile geht auf ``gewaehlt``, und **damit steht alles fest**: mit wem, zu
    welchem Betrag, zu welchen Fristen. Es wird **nichts hineinkopiert** – der Vorgänger
    trug drei Spalten daneben, die dasselbe noch einmal sagten.

    **Bei einer Einnahme ist der Betrag die Summe der Positionen**, jetzt frisch gerechnet:
    wer nachverhandelt, ändert den Preis dort, wo er steht. Bei einer **Ausgabe** darf die
    Nutzlast nachverhandeln – dort ist die Summe die einzige Angabe der Gegenpartei.

    **Und die Positionen frieren ein** – nicht durch eine Kopie, sondern dadurch, dass
    ``sync_lines`` ab jetzt nicht mehr läuft.
    """
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
            detail=(f"{vo.PARTY} {number} hat abgesagt. Wer doch liefern will, gibt "
                    f"zuerst wieder eine Offerte ab."))
    # **Zuerst die Zeilen einfrieren** – danach ändert sich die Menge nicht mehr, und der
    # Betrag unten rechnet über genau das, was zugesagt wird.
    sync_lines(db, row, order)
    if flow.quoted_by == vo.BY_US:
        priced = priced_dicts(db, row)
        if not priced:
            raise HTTPException(
                status_code=400,
                detail=(f"Ohne Preis gibt es nichts zuzusagen – bei einer {flow.label} "
                        f"nennen wir ihn."))
        line.amount = vo.gross_of(priced, row.currency)
    else:
        # **Nur gesendete Felder wirken – und die Null ist eine Angabe.** ``0 or X`` wäre
        # genau die Falle, in der «zahlbar sofort» still zur Frist der Offerte wird.
        if "amount" in data:
            line.amount = _amount(data.get("amount"), row.currency)
        if "lead_days" in data:
            line.lead_days = _days(data.get("lead_days"))
        if "payment_days" in data:
            line.payment_days = _days(data.get("payment_days"))
    if line.amount is None:
        raise HTTPException(status_code=400,
                            detail="Ohne Betrag gibt es keine Zusage.")
    _assert_terms(line.lead_days, line.payment_days)
    for other in quotes_of(db, row):
        if other.id != line.id and other.state == vo.CHOSEN:
            other.state = vo.QUOTED
    line.state = vo.CHOSEN
    row.stage = vo.AGREED
    row.agreed_on = date.today()


def _revoke(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """**Stornieren.** Der Beleg **behält seinen Weg**: ein Storno macht die Zusage nicht
    ungeschehen, er sagt nur, dass nichts mehr kommt.

    Das Geld läuft weiter – eine Anzahlung muss erstattet werden können, und darum steht
    jede Geld-Zeile auch in der Stufe ``cancelled``.
    """
    row.stage = vo.CANCELLED
    row.cancelled_on = date.today()


def _charge(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
            data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Eine **Forderung** buchen. Negativ ist die Gutschrift.

    **Die Automatik steckt in den Vorgaben, nicht in einem Modus**: Betrag = *zugesagt −
    berechnet* (nie negativ), Fälligkeit = *heute + Frist*, Nummer =
    ``<Auftragsnummer>-<laufend>``, wo wir nummerieren.
    """
    flow = vo.of(row.direction)
    given = _amount(data.get("amount"), row.currency, allow_negative=True)
    value = given if given is not None else balance_of(db, row).next_charge
    if value is None:
        raise HTTPException(status_code=400, detail="Ohne Betrag keine Rechnung.")
    # ►►► **EINE Rechnung je Modul.** ◄◄◄ Gesperrt ist genau eine zweite **positive**
    # Forderung. Eine **Gutschrift** bleibt jederzeit möglich – sie ist eine Minderung
    # derselben Rechnung; und was falsch ist, wird **storniert und neu gestellt**, womit
    # die Regel keinen Zustand ohne Ausgang hinterlässt.
    live = live_charge(db, row)
    if live is not None and value > 0:
        raise HTTPException(
            status_code=409,
            detail=(f"Dieser Beleg hat bereits die Rechnung «{live.reference or live.id}» "
                    f"– je Zahlungs-Modul gibt es genau eine. Eine zweite gehört in ein "
                    f"zweites Zahlungs-Modul (Vorauszahlung und Restzahlung sind zwei "
                    f"Schritte im Prozess); was hier falsch ist, wird storniert und neu "
                    f"gestellt, und eine Minderung ist eine Gutschrift mit negativem "
                    f"Betrag."))
    booked = _day(data.get("booked_on")) or date.today()
    # **Eine Nummer, die WIR vergeben, tippt niemand ab** – ein gesendeter Wert wird
    # verworfen. Wo die Gegenpartei die Rechnung stellt, ist es **ihre** Nummer.
    number = (_our_number(db, order) if flow.reference is None
              else _text(data.get("reference"), 120))
    # ►►► **Die Steuer-Aufteilung wird EINGEFROREN, nicht gerechnet.** ◄◄◄ Aus den
    # Positionen nachgerechnet änderte sich die Steuer einer längst gestellten Rechnung,
    # sobald jemand eine Position anfasst (MWSTG Art. 26).
    priced = priced_dicts(db, row)
    if priced:
        split = vo.split_for(value, priced, row.currency)
    else:
        try:
            split = vo.split_at(value, vo.assert_vat(
                data.get("vat") or vo.DEFAULT_VAT), row.currency)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    db.add(VoucherEntry(
        voucher_id=row.id, kind=vo.CHARGE, amount=value, booked_on=booked,
        due_on=_day(data.get("due_on")) or _due(booked, due_days_of(db, row)),
        reference=number, note=_text(data.get("note"), 200),
        vat=split,
        # **Das Leistungsdatum kommt aus dem PROZESS**, nicht aus einem Feld: der Tag, an
        # dem die Stücke dieses Modul erreicht haben. Das Rechnungsdatum ist es nicht –
        # eine zwei Wochen später geschriebene Rechnung verschöbe die Steuerperiode.
        service_date=service_day(db, step) or booked,
    ))


def _pay(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
         data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """Eine **Zahlung** buchen. Negativ ist die Erstattung.

    Vorgabe ist der **offene** Betrag, und auch er nie negativ. **Und sie gehört zu genau
    EINER Rechnung** – seit es je Modul höchstens eine lebende gibt, ist sie gemeint.
    """
    charge = _charge_for_payment(db, row, data.get("charge_id"))
    given = _amount(data.get("amount"), row.currency, allow_negative=True)
    value = given if given is not None else (
        open_of(db, row, charge) if charge is not None
        else balance_of(db, row).next_payment)
    if value is None:
        raise HTTPException(status_code=400, detail="Ohne Betrag keine Zahlung.")
    flow = vo.of(row.direction)
    # **Die Karte tippt niemand ab**: sie entsteht beim Zahlungsdienst und kommt über den
    # Webhook – von Hand erfasst wäre sie eine Behauptung über eine Belastung, für die es
    # keinen Beleg gibt.
    try:
        method = vo.assert_method(data.get("method"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.add(VoucherEntry(
        voucher_id=row.id, kind=vo.PAYMENT, amount=value,
        booked_on=_day(data.get("booked_on")) or date.today(),
        reference=(None if flow.reference is None
                   else _text(data.get("reference"), 120)),
        note=_text(data.get("note"), 200),
        charge_id=charge.id if charge is not None else None,
        method=method,
    ))


def _reverse(db: Session, *, order: Order, step: ProcessStep, row: Voucher,
             data: dict[str, Any], actor: Optional[UserProfile]) -> None:
    """►►► **Eine Geld-Zeile stornieren — durch eine Gegenbuchung.** ◄◄◄

    **Gelöscht wird nichts.** Eine Rechnungsnummer ist vergeben, ein Beleg ist draussen;
    wer die Zeile verschwinden lässt, behauptet, sie sei nie passiert. Gebucht wird
    stattdessen eine **Gegenzeile**: dieselbe Art, der negative Betrag, ein Verweis auf
    die stornierte. Die Summe stimmt damit von selbst und braucht **keinen Sonderfall**.

    **Man storniert einen BELEG, kein Ereignis**: eine **Zahlung** ist die Aufzeichnung
    dessen, was auf dem Konto passiert ist – korrigiert wird sie durch eine **zweite,
    negative Zahlung**, und welcher der beiden Fälle es ist (Erfassungsfehler ↔
    Erstattung), weiss nur ein Mensch.
    """
    entry = (
        db.query(VoucherEntry)
        .filter(VoucherEntry.id == _int(data.get("entry")),
                VoucherEntry.voucher_id == row.id,
                VoucherEntry.is_active.is_(True))
        .first()
    )
    if entry is None:
        raise HTTPException(status_code=404,
                            detail="Diese Zeile gehört nicht zu diesem Beleg.")
    if entry.kind != vo.CHARGE:
        raise HTTPException(
            status_code=409,
            detail=("Eine Zahlung storniert man nicht – sie ist ein Ereignis, kein Beleg. "
                    "Erfasse eine zweite Zahlung mit dem negativen Betrag: das ist die "
                    "Korrektur eines Erfassungsfehlers ebenso wie eine Erstattung."))
    if entry.reverses_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Diese Zeile ist selbst eine Stornierung – sie storniert sich nicht.")
    if _reversal_of(db, entry.id) is not None:
        raise HTTPException(status_code=409, detail="Diese Zeile ist bereits storniert.")
    # ►►► **Eine Stornorechnung ist ein EIGENER Beleg.** ◄◄◄ Sie zieht die **nächste**
    # Nummer aus der Serie und nennt die stornierte im Vermerk: **jede Nummer wird genau
    # einmal vergeben**, und der Bezug wohnt in ``reverses_id``, nie in der Nummer.
    flow = vo.of(row.direction)
    db.add(VoucherEntry(
        voucher_id=row.id, kind=entry.kind, amount=-entry.amount,
        booked_on=date.today(), due_on=None,
        reference=(_our_number(db, order) if flow.reference is None else None),
        note=f"Storno zu {entry.reference}" if entry.reference else "Storno",
        reverses_id=entry.id,
        # **Die Gegenbuchung spiegelt die ganze Steuerzeile**, nicht nur ihre Zahlen:
        # Schlüssel, Name und Pflichtsatz gehören zur stornierten Aussage – sonst verlöre
        # sie ausgerechnet den Rechtsgrund, den sie zurücknimmt.
        vat=[{**r,
              "net": cur.money(-Decimal(r["net"]), row.currency),
              "tax": cur.money(-Decimal(r["tax"]), row.currency)}
             for r in (entry.vat or [])],
        service_date=entry.service_date,
    ))


#: ►►► **DIE EINE TABELLE.** ◄◄◄ Sie steht hier unten, weil sie die Funktionen darüber
#: nennt – und nicht, weil sie zweitrangig wäre: sie **ist** die Regel. Wer ein Verb
#: hinzufügt, schreibt eine Zeile und hat damit Stufe, Stammdaten, Zugang und Wirkung
#: erklärt. Beim Vorgänger waren es vier Stellen, und die vierte vergass man.
VERBS: dict[str, Verb] = {
    # **Vor der Zusage** – hier wird der Beleg geschrieben.
    "currency": Verb(stages=(vo.OFFER,), run=_currency),
    "issuer": Verb(stages=(vo.OFFER,), run=_issuer),
    "incoterm": Verb(stages=(vo.OFFER,), run=_incoterm),
    "price": Verb(stages=(vo.OFFER,), run=_price),
    "ask": Verb(stages=(vo.OFFER,), run=_ask, needs=("ask",)),
    "quote": Verb(stages=(vo.OFFER,), run=_quote, needs=("ask",), party=IF_THEY_PRICE),
    "decline": Verb(stages=(vo.OFFER,), run=_decline, party=ALWAYS),
    "agree": Verb(stages=(vo.OFFER,), run=_agree, needs=("ask", "agree"),
                  party=IF_WE_PRICE),
    # **Ab der Zusage** – und das Geld fliesst in **jeder** Stufe danach, auch nach dem
    # Storno: eine Anzahlung muss erstattet werden können, und eine Rechnung darf vor der
    # Erfüllung stehen wie danach. Wer das an die Stufe bände, hätte für jedes Szenario
    # ein ``if``.
    "revoke": Verb(stages=(vo.AGREED,), run=_revoke),
    "charge": Verb(stages=(vo.AGREED, vo.DONE, vo.CANCELLED), run=_charge,
                   needs=("ask", "agree", "charge")),
    "pay": Verb(stages=(vo.AGREED, vo.DONE, vo.CANCELLED), run=_pay),
    # **Ein Irrtum kennt keinen Zeitpunkt** – darum in jeder Stufe.
    REVERSE: Verb(stages=(vo.OFFER, vo.AGREED, vo.DONE, vo.CANCELLED), run=_reverse),
    # ``run=None``: **sie ändern den Beleg nicht.** Die eine **löst** eine Zahlung aus,
    # die andere gibt sie zurück – gebucht wird beides erst, wenn der Zahlungsdienst es
    # meldet. Eigener Weg, **dieselbe Tür** (``assert_allowed``).
    "pay_online": Verb(stages=(vo.AGREED, vo.DONE, vo.CANCELLED), party=ALWAYS),
    "refund_online": Verb(stages=(vo.AGREED, vo.DONE, vo.CANCELLED)),
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
# ►► DIE RECHNUNGEN — eine je Modul, und was daran hängt
# ---------------------------------------------------------------------------

def live_charge(db: Session, row: Voucher) -> Optional[VoucherEntry]:
    """►►► **DIE Rechnung dieses Moduls — oder ``None``.** ◄◄◄

    *«Nur eine Rechnung pro Zahlungsmodul. Habe ich Teilrechnungen, dann erstelle ich
    einfach 2 Zahlungsmodule.»* – Der Grund ist die **Zeit**: *Vorauszahlung → Leistung →
    Restzahlung* sind drei Zeitpunkte, ein Modul steht an einem.

    Gezählt wird, was eine *Forderung nach aussen* ist: eine **Gegenbuchung** ist keine
    Rechnung, eine **stornierte** Zeile ist keine mehr (genau das ist der Ausweg), und
    eine **Gutschrift** (negativ) ist eine Minderung, keine zweite Rechnung.
    """
    entries = entries_of(db, row)
    undone = {e.reverses_id for e in entries if e.reverses_id is not None}
    live = [e for e in entries
            if e.kind == vo.CHARGE and e.reverses_id is None
            and e.id not in undone and e.amount > 0]
    return live[0] if live else None


def open_charges(db: Session, row: Voucher) -> list[VoucherEntry]:
    """**Die Rechnungen, auf die noch etwas offen ist** – älteste zuerst.

    Ausgenommen die **stornierten** und die Stornozeilen selbst: das Paar hebt sich auf,
    und auf eine zurückgenommene Rechnung zahlt niemand.
    """
    entries = entries_of(db, row)
    undone = {e.reverses_id for e in entries if e.reverses_id is not None}
    return [e for e in entries
            if e.kind == vo.CHARGE and e.reverses_id is None and e.id not in undone
            and _open_of(entries, e) > 0]


def paid_on(db: Session, row: Voucher, charge: VoucherEntry) -> Decimal:
    """Was auf **diese** Rechnung schon geflossen ist – die Grundlage des Wortes.

    Eine bezahlte Rechnung nimmt man nicht «zurück», man schreibt sie **gut**; welches der
    beiden Wörter gilt, hängt an genau dieser Zahl.
    """
    return _paid_on(entries_of(db, row), charge)


def open_of(db: Session, row: Voucher, charge: VoucherEntry) -> Decimal:
    """Was auf **dieser** Rechnung noch offen ist – Betrag minus ihre Zahlungen."""
    return _open_of(entries_of(db, row), charge)


def refundable(db: Session, row: Voucher) -> list[VoucherEntry]:
    """**Die Karten-Zahlungen, die man zurückgeben kann** – jüngste zuerst.

    Nur eine **Karte**: bar und per Überweisung ist die Erstattung eine gewöhnliche
    negative Zahlung, die ein Mensch erfasst. Und nur eine **positive**: eine Erstattung
    erstattet man nicht. Ihre Referenz ist die Zahlungsabsicht – ohne sie fände der Dienst
    die Belastung nicht.
    """
    return [e for e in reversed(entries_of(db, row))
            if e.kind == vo.PAYMENT and e.method == vo.CARD and e.amount > 0
            and e.reference]


def card_payment(db: Session, row: Voucher,
                 entry_id: Optional[int]) -> VoucherEntry:
    """**Welche Karten-Zahlung ist gemeint?** – oder ein Satz, warum keine.

    Zwei Formen einer Regel: ``can`` beantwortet **ob** es etwas zu erstatten gibt und
    zeigt darum den Knopf, diese Funktion **welche** und ist das Tor.
    """
    rows = refundable(db, row)
    if not rows:
        raise HTTPException(
            status_code=409,
            detail=("Hier ist keine Karten-Zahlung erfasst. Bar und per Überweisung ist "
                    "eine Erstattung eine gewöhnliche Zahlung mit negativem Betrag."))
    if entry_id in (None, ""):
        return rows[0]
    found = next((e for e in rows if e.id == entry_id), None)
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=("Diese Zahlung lässt sich nicht über den Zahlungsdienst erstatten – "
                    "sie gehört zu einem anderen Beleg oder kam nicht per Karte."))
    return found


def _paid_on(entries: list[VoucherEntry], charge: VoucherEntry) -> Decimal:
    return sum((e.amount for e in entries
                if e.kind == vo.PAYMENT and e.charge_id == charge.id), Decimal("0"))


def _open_of(entries: list[VoucherEntry], charge: VoucherEntry) -> Decimal:
    return charge.amount - _paid_on(entries, charge)


def _charge_for_payment(db: Session, row: Voucher,
                        value: Any) -> Optional[VoucherEntry]:
    """**Auf welche Rechnung geht diese Zahlung?** – genannt oder vorbelegt.

    Es gibt je Modul höchstens eine lebende Rechnung – also ist sie gemeint. Bleibt
    **keine**, dann ``None``, und das ist kein Fehler: eine Erstattung gehört zu einer
    Rechnung, die längst beglichen ist. Ein **genannter** Wert wird streng geprüft, sonst
    hinge eine Zahlung an einem fremden Beleg.
    """
    if value not in (None, ""):
        wanted = _int(value)
        found = next((e for e in entries_of(db, row)
                      if e.id == wanted and e.kind == vo.CHARGE), None)
        if found is None:
            raise HTTPException(status_code=400,
                                detail="Diese Rechnung gehört nicht zu diesem Beleg.")
        return found
    return live_charge(db, row)


def _reversal_of(db: Session, entry_id: int) -> Optional[VoucherEntry]:
    """Die Gegenzeile zu dieser Zeile – oder ``None``. **Die eine Lesestelle.**"""
    return (
        db.query(VoucherEntry)
        .filter(VoucherEntry.reverses_id == entry_id, VoucherEntry.is_active.is_(True))
        .first()
    )


def of_reference(db: Session, reference: str) -> Optional[Voucher]:
    """**Zu welchem Beleg gehört diese Zahlungsreferenz?** – der Rückweg einer Erstattung."""
    row = (
        db.query(VoucherEntry)
        .filter(VoucherEntry.kind == vo.PAYMENT, VoucherEntry.reference == reference,
                VoucherEntry.is_active.is_(True))
        .first()
    )
    return (db.query(Voucher).filter(Voucher.id == row.voucher_id).first()
            if row is not None else None)


def record_payment(db: Session, *, row: Voucher, amount: Decimal,
                   reference: Optional[str] = None,
                   note: Optional[str] = None,
                   charge_id: Optional[int] = None,
                   method: Optional[str] = None) -> VoucherEntry:
    """**Eine Zeile Geld** – die Tür des Zahlungsdienstes.

    Ein Zahlungsdienst ruft nicht ``apply``: er hat keinen angemeldeten Benutzer, keine
    Stufe und keine Meinung darüber, was jemand darf. Er meldet **eine Tatsache**.

    ►►► **Idempotent über die Referenz.** ◄◄◄ Ein Dienst stellt dieselbe Meldung mehrfach
    zu – das ist kein Fehler, das ist sein Auslieferungsversprechen. Und eine Referenz
    gehört zu genau **einer** Zahlung im Haus: taucht sie an einem *anderen* Beleg auf,
    ist das ein Irrtum und kein Duplikat – er wird **genannt**, denn ein stiller
    Nicht-Effekt ist schlimmer als ein Fehler.
    """
    if reference:
        seen = (
            db.query(VoucherEntry)
            .filter(VoucherEntry.kind == vo.PAYMENT,
                    VoucherEntry.reference == reference,
                    VoucherEntry.is_active.is_(True))
            .first()
        )
        if seen is not None:
            if seen.voucher_id != row.id:
                raise HTTPException(
                    status_code=409,
                    detail=(f"Die Referenz «{reference}» hängt bereits an einem anderen "
                            f"Beleg. Zweimal dieselbe Zahlung gibt es nicht."))
            return seen
    entry = VoucherEntry(
        voucher_id=row.id, kind=vo.PAYMENT, amount=amount,
        booked_on=date.today(), reference=reference, note=note,
        charge_id=charge_id, method=method,
    )
    db.add(entry)
    db.flush()
    return entry


# ---------------------------------------------------------------------------
# ►► DIE DREI BERÜHRUNGSPUNKTE MIT DEM RAHMEN — je eine Zeile, no-op ohne dieses Modul
# ---------------------------------------------------------------------------

def assert_completable(db: Session, *, step: ProcessStep) -> None:
    """**Darf dieses Modul bestätigt werden?** – gerufen von ``process.confirm_step``.

    Drei Gründe, warum nicht, und alle drei sind derselbe Satz: der Beleg ist noch nicht so
    weit. Es gibt dafür **keinen Zustand am Stück** und keinen Pausenwert – das Modul ist
    schlicht nicht fertig.
    """
    row = of_step(db, step.id)
    if row is None:
        return
    flow = vo.of(row.direction)
    if row.stage == vo.OFFER:
        raise HTTPException(
            status_code=409,
            detail=(f"«{flow.label}»: der Auftrag ist noch nicht bestätigt – bis dahin "
                    f"steht kein Betrag fest, und es gibt nichts zu erledigen."))
    if row.stage == vo.CANCELLED:
        raise HTTPException(
            status_code=409,
            detail=(f"«{flow.label}» ist storniert. Die Stücke stehen still, bis jemand "
                    f"entscheidet, was mit ihnen geschieht – dafür gibt es den ganz "
                    f"gewöhnlichen Abweichungsauftrag."))
    # ►►► **Die Sperre ist die vereinbarte ZAHLUNGSFRIST.** ◄◄◄ «Zahlbar in null Tagen ab
    # Zusage» *ist* die Vorauszahlung – ein Schalter daneben wäre die zweite Aussage über
    # dieselbe Sache.
    if not vo.prepaid(due_days_of(db, row)):
        return
    money = balance_of(db, row)
    if not money.settled:
        raise HTTPException(
            status_code=409,
            detail=(f"«{flow.label}» wartet auf den Zahlungseingang: {money.paid} von "
                    f"{money.agreed} bezahlt. So ist es vereinbart – "
                    f"{vo.PAYMENT_TERMS[0][1]}, erst das Geld, dann weiter."))


def finish(db: Session, *, order: Order, step: ProcessStep) -> None:
    """Nach ``confirm_step``: steht nichts mehr davor, ist der Beleg **erledigt**.

    **Nur der Auftrag ist damit erledigt, nicht das Geld**: Forderungen und Zahlungen
    laufen weiter, denn ein Zahlungsziel endet nicht mit der Ware.
    """
    row = of_step(db, step.id)
    if row is None or row.stage != vo.AGREED:
        return
    waiting = (
        db.query(OrderUnit)
        .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None),
                OrderUnit.current_step_id == step.id)
        .count()
    )
    if waiting:
        return
    row.stage = vo.DONE
    db.flush()


def service_day(db: Session, step: ProcessStep) -> Optional[date]:
    """►►► **Wann wurde die Leistung erbracht?** – aus dem Prozess, nicht getippt. ◄◄◄

    Der Tag, an dem die Stücke **das Modul davor** verlassen haben, also bei diesem hier
    angekommen sind. **Das Rechnungsdatum ist es nicht**: eine zwei Wochen später
    geschriebene Rechnung verschöbe die Steuerperiode (MWSTG Art. 26 Bst. c).

    Gelesen wird darum das Ereignis des **Vorgängers**, nicht das eigene – ein ``step`` an
    *diesem* Modul heisst «hier fertig». Steht dieses Modul am Anfang, ist die Ankunft der
    **Start** des Auftrags. ``None`` heisst «hier ist noch nichts angekommen».
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
    found = q.order_by(ProcessEvent.id.desc()).first()
    return found[0].date() if found and found[0] else None


# ---------------------------------------------------------------------------
# ►► DER BELEGKOPF — beide Parteien, wie das Gesetz sie nennt
# ---------------------------------------------------------------------------

def issuer_company(db: Session, row: Voucher):
    """**Unsere Seite des Belegs** – die eingefrorene Gesellschaft.

    **Eine Lesestelle**, damit Belegkopf, Lückenprüfung und Einzahlungsschein nicht drei
    Antworten geben. Der **Betreiber** bleibt der Rückfall: ein Beleg ohne Aussteller wäre
    schlimmer als einer mit dem Betreiber.
    """
    return sites.by_object_id(db, row.issuer_company_id) or sites.find_operator(db)


def billing_of(db: Session, row: Voucher,
               party_id: Optional[int] = None) -> dict[str, Any]:
    """**Was wir über den Zahlenden schon wissen** – Name, Anschrift, Kontakt, UID.

    Der Zahlende ist die Gegenpartei **dieses Belegs**, nicht der Betrachter: auch wenn
    ein Mitarbeiter die Zahlung am Schalter auslöst, gehört die Rechnung dem Kunden.

    **Die Rechnungsadresse geht vor der Wohnadresse** – dafür ist sie da. Und geliefert
    wird nur eine **vollständige**: eine halbe wäre eine Vorbelegung, die das Formular
    danach doch wieder erfragt, nur falsch.
    """
    empty: dict[str, Any] = {"name": None, "email": None, "address": None}
    number = party_id if party_id is not None else party_of(db, row)
    if number is None:
        return empty
    u = db.query(UserProfile).filter(UserProfile.object_id == number).first()
    if u is None:
        return empty
    # Eine Rechnungsadresse gilt als hinterlegt, sobald irgendein Feld davon steht – sonst
    # mischte sich die eine Hälfte mit der anderen zu einer Adresse, die es nirgends gibt.
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
        # **Auf dem Beleg steht die Rechtsperson, nicht ihr Vertreter**: ``people.name``
        # ist person-first (im ERP richtig), Schuldner ist die *Muster AG*.
        # ``billing_name`` liefert darum Zeilen – **neben** ``name``, nicht an seiner
        # Stelle: zwei Formen einer Regel, nicht zwei Regeln.
        "lines": people.billing_name(u),
        "email": (u.invoice_email if own else None) or u.email,
        "phone": u.phone,
        # Dieselbe Rangfolge wie bei uns – die MWST-Nummer trägt den Vorsteuerabzug.
        "uid": u.vat_number or u.uid_number,
        "address": {
            "line1": line1, "line2": line2 or None, "city": city,
            "postal_code": zip_code, "country": address.iso2(country),
        } if full else None,
    }


def document_head(db: Session, row: Voucher, *, won: bool,
                  party_id: Optional[int] = None) -> dict[str, Any]:
    """►►► **Wer stellt den Beleg, und wer bekommt ihn** (MWSTG Art. 26). ◄◄◄

    Eine Rechnung ist erst eine, wenn sie **beide Seiten** nennt: Name mit Rechtsform, Ort,
    Kontaktweg und die **UID mit dem Zusatz MWST** dessen, der sie stellt – ohne ihn kann
    dem Empfänger der Vorsteuerabzug verweigert werden.

    **Welche Seite welche Rolle hat, sagt die Richtung** – über die Angabe, die es schon
    gibt (``collects``): wo das Geld zu uns fliesst, sind **wir** der Leistungserbringer.
    Ein zweites Feld «wer fakturiert» wäre dieselbe Aussage ein zweites Mal.

    **Was fehlt, wird nicht erfunden**: eine Seite ohne Anschrift trägt eine leere Liste,
    eine ohne UID ``None`` – die Oberfläche sagt dann klein, was fehlt. Eine erfundene
    Zeile wäre auf einem Beleg schlimmer als eine leere.

    **Und die Gegenseite hängt an ``won``** – wie jede andere Angabe über sie: wer nicht
    den Zuschlag hat, sieht **uns** (das steht auf jeder Rechnung, die wir stellen) und
    eine **leere** Gegenseite.
    """
    flow = vo.of(row.direction)
    company = issuer_company(db, row)
    who = billing_of(db, row, party_id) if won else {}
    seat = who.get("address") or {}
    seat_ours = address.of_company(company) if company is not None else None
    ours = {
        "object_id": getattr(company, "object_id", None),
        # **Der Name trägt die Rechtsform** – «Inexxio» ist keine Rechtsperson, «Inexxio
        # AG» ist eine, und auf einem Beleg steht die, die haftet.
        "name": sites.legal_name(company),
        # Eine Adresse ohne Ort ist keine: ``of_company`` liefert immer ein Gerüst,
        # ``has_content`` fragt, ob wirklich etwas drinsteht.
        "address": address.lines(seat_ours) if address.has_content(seat_ours) else [],
        "uid": (getattr(company, "vat_number", None)
                or getattr(company, "uid_number", None)),
        "email": getattr(company, "email", None),
        "phone": getattr(company, "phone", None),
    }
    number = (party_id if party_id is not None else party_of(db, row)) if won else None
    lines = who.get("lines") or []
    theirs = {
        "object_id": number,
        "name": (lines or [""])[0],
        "attn": lines[1] if len(lines) > 1 else None,
        "address": address.lines(address.make(
            street1=seat.get("line1") or "", street2=seat.get("line2") or "",
            zip=seat.get("postal_code") or "", city=seat.get("city") or "",
            country=seat.get("country"),
        )) if seat else [],
        "uid": who.get("uid"),
        "email": who.get("email"),
        "phone": who.get("phone"),
    }
    supplier, customer = (ours, theirs) if flow.collects else (theirs, ours)
    return {
        "supplier": {"label": vo.SUPPLIER, "hint": vo.SUPPLIER_HINT, **supplier},
        "customer": {"label": vo.CUSTOMER, "hint": vo.CUSTOMER_HINT, **customer},
    }


def transfer_info(db: Session, row: Voucher, charge: VoucherEntry) -> dict[str, Any]:
    """►►► **Wie man diese Rechnung überweist.** ◄◄◄

    Die dritte Bezahlart ist **keine Buchung**, sondern eine **Auskunft**: «Jetzt bezahlen»
    löst etwas aus, «Zahlung erfassen» schreibt etwas auf – die Überweisung braucht
    *Angaben*, damit der Zahlende sie selbst auslöst.

    **Bankverbindung im Klartext UND als QR** – nicht entweder-oder: der Code spart das
    Abtippen, der Klartext ist der Weg, wenn die Kamera nicht mitspielt. Wo es keinen QR
    geben kann (fremde Währung, keine CH-IBAN), steht der **Grund** statt einer leeren
    Fläche.
    """
    # **Überwiesen wird an den Aussteller**, nicht an den Betreiber: eine zweite Lesart
    # wäre ein QR-Code, der auf ein anderes Konto zeigt als der Beleg darüber.
    company = issuer_company(db, row)
    iban = getattr(company, "iban_encrypted", None)
    number = charge.reference or str(charge.id)
    amount = _open_of(entries_of(db, row), charge)
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


# ---------------------------------------------------------------------------
# ►► DIE GEGENPARTEI
# ---------------------------------------------------------------------------

def search_parties(db: Session, *, search: str = "",
                   limit: int = 20) -> list[UserProfile]:
    """**Wer kommt als Gegenpartei in Frage?** – gesucht, nicht als Liste geladen.

    Dieselbe Suchbedingung wie überall (``services/lookup``: Nummer **oder** Name).
    **Ohne Rollenfilter, und das ist eine Entscheidung**: eine Rolle sagt, was jemand *für
    uns* tut – nicht, ob wir mit ihm Geld austauschen dürfen. Wer einschränken will, nennt
    die zugelassenen Gegenparteien in der **Definition**.
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


def _amount(value: Any, code: str, *, allow_negative: bool = False) -> Optional[Decimal]:
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


def _assert_terms(lead: Optional[int], days: Optional[int]) -> None:
    """►►► **Ein Angebot nennt beide Fristen.** ◄◄◄

    Sie sind kein Beiwerk: aus der **Lieferfrist** kommt der Termin, aus der
    **Zahlungsfrist** die Fälligkeit jeder Rechnung – und, wenn sie null ist, die
    Vorauszahlung. Fehlt eine, hat niemand über den Zeitpunkt gesprochen.

    **Null ist ein gültiger Wert und hat einen Namen** («Sofort» · «Vorauszahlung»): darum
    steht die Prüfung auf ``is None`` und nicht auf ``not value``.
    """
    for value, label in ((lead, vo.LEAD_TERM_LABEL), (days, vo.PAYMENT_TERM_LABEL)):
        if value is None:
            raise HTTPException(
                status_code=400,
                detail=(f"Ohne {label} ist es kein Angebot – aus ihr folgt der Termin "
                        f"bzw. die Fälligkeit. «{vo.LEAD_TERMS[0][1]}» und "
                        f"«{vo.PAYMENT_TERMS[0][1]}» sind gültige Antworten (0 Tage)."))


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


def delivery_date(db: Session, row: Voucher) -> Optional[date]:
    """**Wann er liefern wollte** – Zusagedatum + Lieferfrist der gewählten Zeile.

    Dieselbe Form wie die Fälligkeit: eine Frist ist eine Vereinbarung, ein Datum ihre
    Folge. **Ohne Lieferfrist kein Termin** – ein erfundener wäre schlimmer als keiner.
    """
    q = chosen_quote(db, row)
    if row.agreed_on is None or q is None:
        return None
    return _due(row.agreed_on, q.lead_days)


def is_late(db: Session, row: Voucher) -> bool:
    """**Ist der Liefertermin vorbei, obwohl noch nichts geliefert ist?**

    Kein Zustand, sondern die Frage an zwei Daten – wie ``overdue`` bei einer Forderung.
    Erledigt und storniert sind **nicht** verspätet: dort kommt nichts mehr.
    """
    if row.stage != vo.AGREED:
        return False
    due = delivery_date(db, row)
    return due is not None and due < date.today()


def _our_number(db: Session, order: Order) -> str:
    """``<Auftragsnummer>-<laufend>`` – **immer mit Suffix**, ab ``-1``.

    Dieselbe Regel wie die Nummer einer Einzelinstanz. Gezählt wird über den **Auftrag**
    (zwei Module vergäben sonst dieselbe Nummer zweimal) und **nur, was WIR nummerieren** –
    sonst verbraucht eine erfasste Lieferantenrechnung die Zählung. Auch stornierte Zeilen
    zählen mit: eine einmal vergebene Nummer wird nicht erneut vergeben.

    *Die bewusste Grenze: kein Unique-Index darüber. Bei einem Einkauf steht dort die
    Nummer der Gegenpartei, und zwei Lieferanten dürfen beide eine «2026-001» schicken.*
    """
    used = (
        db.query(func.count(VoucherEntry.id))
        .join(Voucher, VoucherEntry.voucher_id == Voucher.id)
        .filter(Voucher.order_id == order.id, Voucher.direction == vo.IN,
                VoucherEntry.kind == vo.CHARGE)
        .scalar()
    ) or 0
    return f"{order.object_id}-{used + 1}"


def _money(value: Optional[Decimal], code: str) -> Optional[str]:
    """Ein Betrag als String – mit den Nachkommastellen **dieser** Währung."""
    return None if value is None else cur.money(value, code)


# ---------------------------------------------------------------------------
# ►► DIE ANTWORT
# ---------------------------------------------------------------------------

def embed_data(db: Session, *, order: Order, step: ProcessStep,
               viewer: Optional[UserProfile] = None) -> Optional[dict[str, Any]]:
    """Der Beleg, wie ihn die Ausführungsstelle braucht – oder ``None``.

    **Alles, was die Oberfläche zum Zeichnen braucht, reist mit**: Wörter, Stufen, Verben,
    Zahlen und was man tun darf. Sie fragt damit nie nach der Richtung und nie nach dem
    Modultyp.

    **Und eine Gegenpartei sieht nur ihren Teil.** Fremde Preise sind kein Nebeneffekt
    einer Ansicht: gefiltert wird hier, beim Aufbau der Antwort. Wer **nicht den Zuschlag**
    hat, sieht weder Namen noch Preis der übrigen – und die **Freigabe-Liste** ist die
    Konkurrenzliste selbst, sie fällt für jede Nicht-Personal-Sicht ganz weg.

    ►►► **Hier laufen die Positionen nach** (``sync_lines``). ◄◄◄ Das ist der einzige
    Schreibvorgang auf einem Lesepfad, und er ist Absicht: die Positionen **sind** der
    Prozess, solange nichts zugesagt ist, und sie brauchen eine Id, damit man sie bepreisen
    kann. Idempotent, durch einen Unique-Index abgesichert, und ab der Zusage ein No-op.
    """
    row = of_step(db, step.id)
    if row is None:
        return None
    flow = vo.of(row.direction)
    sync_lines(db, row, order)
    entries = entries_of(db, row)
    money = balance_of(db, row)
    chosen = chosen_quote(db, row)
    reversed_ids = {e.reverses_id for e in entries if e.reverses_id is not None}
    today = date.today()
    internal = viewer is None or viewer.role in STAFF_ROLES
    party = chosen.party_id if chosen is not None else None
    # **Den Zuschlag hat, wer zugesagt bekam** – für das Personal ist das immer wahr.
    won = internal or (party is not None and viewer is not None
                       and party == viewer.object_id)
    allowed = can(db, row, viewer)
    live = live_charge(db, row)
    # **Was sich über den Dienst zurückgeben lässt** – dieselbe Liste, die ``can`` befragt
    # und ``card_payment`` als Tor benutzt. Eine zweite Bedingung hier wäre ein zweiter
    # Massstab, und der bekäme die nächste Regel nicht mit.
    refund_ids = ({e.id for e in refundable(db, row)}
                  if "refund_online" in allowed else set())
    # **Worauf man überweisen kann** – offen und uns zustehend. Die Frage ist nicht «wer
    # darf?» (überweisen darf jeder), sondern «trägt der Einzahlungsschein eine
    # Bankverbindung, die es bei uns gibt?».
    transferable_ids = ({e.id for e in open_charges(db, row)}
                        if won and flow.collects else set())
    priced = priced_dicts(db, row)
    sums = vo.totals(vo.vat_split(priced, row.currency), row.currency)
    return {
        "direction": row.direction,
        "label": flow.label,
        # **Ein Wort für beide Richtungen** – es reist trotzdem mit, damit die Karte keine
        # eigene Konstante daneben hält.
        "party_word": vo.PARTY,
        "ask_verb": flow.ask_verb,
        # **Wer den Preis nennt, und wie das Nummernfeld heisst** – lauter Angaben, damit
        # die Oberfläche die Richtung nie selbst auswertet.
        "we_quote": flow.quoted_by == vo.BY_US,
        "ref_label": flow.reference,
        # **Die Steuer-Angaben** – Katalog, Vorgabe und Wörter reisen mit, damit die Karte
        # keine zweite Liste pflegt. **Der Pflichtsatz reist mit dem Satz**: eine zweite
        # Liste im Browser wäre die Stelle, die beim nächsten Tatbestand jemand vergisst.
        "vat_rates": [{"key": v.key, "rate": v.rate, "label": v.label, "note": v.note}
                      for v in vo.VAT_RATES],
        "vat_rate": vo.DEFAULT_VAT,
        "vat_label": vo.VAT_LABEL,
        "service_date_label": vo.SERVICE_DATE_LABEL,
        # **Die Lieferbedingung** – Katalog **und** Erklärung reisen mit: genau hier
        # entstehen die Fragen. Der fertige Satz kommt ebenfalls vom Server; im Browser
        # zusammengesetzt wäre er die zweite Schreibweise.
        "incoterm": row.incoterm,
        "incoterm_place": row.incoterm_place,
        "incoterm_text": inc.sentence(row.incoterm, row.incoterm_place),
        "incoterm_label": inc.LABEL,
        "incoterm_place_label": inc.PLACE_LABEL,
        "incoterm_place_hint": inc.PLACE_HINT,
        "incoterms": [{"key": t.key, "label": t.label, "hint": t.hint}
                      for t in inc.INCOTERMS],
        # **In welcher Währung?** Ein Betrag ohne sie ist keine Zahl – und mit ihr reisen
        # die Nachkommastellen, denn ein Yen-Betrag mit zwei Stellen ist keiner.
        "currency": row.currency,
        "currency_label": cur.label(row.currency),
        "currency_decimals": cur.minor_units(row.currency),
        "currencies": [{"code": c, "label": cur.label(c)} for c in cur.CURRENCIES],
        # **Wer den Beleg stellt** – vorgewählt, nicht geraten. Die Liste gibt es nur für
        # das Personal: eine Gegenpartei wählt nicht aus, wer ihr eine Rechnung stellt.
        "issuer": getattr(issuer_company(db, row), "object_id", None),
        "issuer_label": vo.ISSUER_LABEL,
        "issuers": [{"object_id": c.object_id, "name": sites.legal_name(c)}
                    for c in sites.selectable_companies(db)] if internal else [],
        # **Netto und Steuer sind ABLEITUNGEN der Positionen** – gerechnet je Satz auf der
        # Summe, damit zweimal Rechnen dasselbe ergibt, und nur für den, der die Zahlen
        # ohnehin sehen darf.
        "net": sums["net"] if won else None,
        "tax": sums["tax"] if won else None,
        "vat_split": vo.vat_split(priced, row.currency) if won else [],
        "charge_word": vo.CHARGE_WORD,
        "payment_word": vo.PAYMENT_WORD,
        "pay_online_word": vo.PAY_ONLINE_WORD,
        "open_word": vo.OPEN_WORD,
        "money_label": vo.MONEY_LABEL,
        "goods_title": vo.GOODS_TITLE,
        "quotes_title": vo.QUOTES_TITLE,
        "history_title": vo.HISTORY_TITLE,
        "task_label": vo.TASK,
        "party_number_label": vo.PARTY_NUMBER_LABEL,
        # **Das Wort der Gegenhandlung hängt an DEN HANDLUNGEN DIESES BETRACHTERS**, nicht
        # an der Stufe: sonst liest eine Gegenpartei «Auftrag stornieren» an einem Knopf,
        # den es für sie nie gibt.
        "undo": vo.UNDO if "revoke" in allowed else None,
        "stage": row.stage,
        "stage_label": flow.label_of(row.stage),
        "stages": _stages(row, flow),
        "can": allowed,
        # **Die Sperre ist eine ABLEITUNG der Zahlungsfrist**: «zahlbar in null Tagen ab
        # Zusage» *ist* die Vorauszahlung – ein Schalter daneben wäre die zweite Aussage.
        "prepaid": vo.prepaid(chosen.payment_days if chosen else None),
        # **Die üblichen Fristen mit ihren Namen** – «Vorauszahlung» ist ein
        # Geschäftsbegriff, «0» eine Ziffer, die man erklären muss.
        "payment_terms": [{"days": d, "label": name} for d, name in vo.PAYMENT_TERMS],
        "lead_terms": [{"days": d, "label": name} for d, name in vo.LEAD_TERMS],
        "term_free_min": vo.FREE_MIN,
        "term_free_label": vo.FREE_TERM_LABEL,
        "payment_term_label": vo.PAYMENT_TERM_LABEL,
        "lead_term_label": vo.LEAD_TERM_LABEL,
        # **Wie bezahlt wurde** – nur, was ein Mensch erfassen darf. Die Karte schreibt
        # allein der Webhook, also steht sie hier nicht.
        "methods": [{"key": k, "label": name} for k, name in vo.METHODS
                    if k in vo.MANUAL_METHODS],
        "method_label": vo.METHOD_LABEL,
        "transfer_word": vo.TRANSFER_WORD,
        "refund_word": vo.REFUND_WORD,
        "refund_online_word": vo.REFUND_ONLINE_WORD,
        # **Die Freigabe-Liste ist die Konkurrenzliste** – sie geht eine Gegenpartei nichts
        # an, auch nicht die, die den Zuschlag hat.
        "allowed": (_named(db, modules.Beleg.parties_allowed(step.config))
                    if internal else []),
        "quotes": _quotes(db, row, step, viewer=viewer, internal=internal),
        "lines": embed_lines(db, row),
        # **Der Belegkopf** – die beiden Parteien mit ihren Rollen (MWSTG Art. 26).
        # **Uns** sieht jeder: ein Beleg ohne Aussteller ist keiner, und wer bezahlen soll,
        # muss wissen, an wen. Die **Gegenseite** hängt an ``won``.
        **document_head(db, row, won=won),
        # **Was fehlt, um weiterzukommen** – gefragt nach der **nächsten** Handlung dieser
        # Stufe. Nur für das Personal: eine Gegenpartei kann unsere Stammdaten weder sehen
        # noch pflegen, und eine Meldung über einen fremden Datensatz wäre eine Sackgasse.
        "gaps": (gaps(db, row, action=next_action(db, row)) if internal else []),
        # ►►► **Die drei Ableitungen statt dreier Spalten.** ◄◄◄ *mit wem · was vereinbart
        # ist · welche Zahlungsfrist* stehen an der **gewählten Angebotszeile** – und weil
        # sie dort stehen, kann derselbe Beleg nicht zwei Dinge sagen.
        "party_object_id": party if won else None,
        "party_name": (_named(db, [party])[0]["name"] if party and won else None),
        "amount": _money(chosen.amount, row.currency) if (chosen and won) else None,
        "due_days": chosen.payment_days if (chosen and won) else None,
        "lead_days": chosen.lead_days if (chosen and won) else None,
        "agreed_on": row.agreed_on if won else None,
        "cancelled_on": row.cancelled_on if won else None,
        # ►►► **Der Liefertermin und der Verzug — zwei ABLEITUNGEN, null Spalten.** ◄◄◄
        # Ein Lieferverzug ist kein Zustand: der Termin ist *Zusagedatum + Lieferfrist*,
        # und «verspätet» heisst *Termin vorbei und noch nicht erledigt* – exakt dieselbe
        # Form wie ``overdue`` bei einer Forderung.
        "due_date": delivery_date(db, row) if won else None,
        "late": is_late(db, row) if won else False,
        # ►►► **Forderung und Geld sieht, wer den Zuschlag hat.** ◄◄◄ Wer bezahlen soll,
        # muss sehen, was er schuldet – eine Aufforderung ohne Betrag ist keine. Ein
        # **Leck ist es nicht**: ``won`` heisst «dieser Betrachter *ist* die Gegenpartei»,
        # die Rechnungen sind seine. Ein unterlegener Dritter sieht weiterhin nichts.
        "charged": _money(money.charged, row.currency) if won else None,
        "paid": _money(money.paid, row.currency) if won else None,
        "open": _money(money.open, row.currency) if won else None,
        "uncharged": _money(money.uncharged, row.currency) if won else None,
        # **Eine Rechnung je Modul** – die zweite Form derselben Regel, die ``_charge``
        # durchsetzt: steht sie, gibt es nichts mehr zu buchen, und der Vorschlag fällt mit
        # dem Knopf weg. Eine Vorgabe für eine Buchung, die der Dienst abweist, wäre ein
        # Angebot, das garantiert scheitert.
        "credit_only": bool(live) if won else False,
        "next_charge": (None if live is not None
                        else _money(money.next_charge, row.currency)) if won else None,
        "next_payment": _money(money.next_payment, row.currency) if won else None,
        "settled": money.settled if won else False,
        "entries": [
            {
                "id": e.id, "kind": e.kind, "amount": _money(e.amount, row.currency),
                "booked_on": e.booked_on, "due_on": e.due_on,
                "reference": e.reference, "note": e.note,
                # **Überfällig ist eine Ableitung, kein Zustand**: eine Forderung, deren
                # Tag vorbei ist, solange überhaupt noch etwas offen ist.
                "overdue": bool(e.kind == vo.CHARGE and e.due_on and e.due_on < today
                                and money.open > 0),
                # **Die beiden Richtungen derselben Angabe** – aus derselben geladenen
                # Liste: welche Zeile diese hier storniert, und ob sie selbst storniert
                # wurde. Im Browser müsste die zweite über die ganze Liste gesucht werden.
                "reverses": e.reverses_id,
                "reversed": e.id in reversed_ids,
                # **Worauf diese Zahlung geht** – nur die Id; die Nummer steht an der
                # Rechnung, und die Karte hat die ganze Liste.
                "charge_id": e.charge_id,
                "vat": list(e.vat or []),
                "service_date": e.service_date,
                "method": e.method,
                "method_label": vo.method_name(e.method),
                # **Storno ODER Gutschrift** – dieselbe Zeile, zwei Lagen: was bezahlt
                # ist, nimmt man nicht zurück, man schreibt es gut. Welches Wort gilt,
                # hängt an der Zahl, nicht an einem zweiten Verb.
                "reverse_word": (vo.reverse_word(_paid_on(entries, e))
                                 if e.kind == vo.CHARGE else None),
                "open": (_money(_open_of(entries, e), row.currency)
                         if e.kind == vo.CHARGE else None),
                "refundable": e.id in refund_ids,
                "transferable": e.id in transferable_ids,
            }
            # **Dieselbe Frage, dieselbe Antwort**: die Zeilen gehören dem, der den
            # Zuschlag hat – seine Rechnungen, seine Zahlungen.
            for e in (entries if won else [])
        ],
    }


def _quotes(db: Session, row: Voucher, step: ProcessStep, *,
            viewer: Optional[UserProfile], internal: bool) -> list[dict[str, Any]]:
    """Der Angebotsspiegel – **für die Gegenpartei nur ihre eigene Zeile**.

    Wer nicht den Zuschlag hat, sieht weder Namen noch Preis der übrigen: gefiltert wird
    beim Aufbau der Antwort, nicht in der Oberfläche.

    **Die Bestellangabe reist mit ihrer Zeile** (``config.parties[].ref``): sie sagt, wie
    man bei genau diesem hier bestellt, und steht darum bei ihm – nicht als eine Angabe am
    Beleg, die man bei jedem Vorgang neu abschreibt.
    """
    rows = quotes_of(db, row)
    if not internal:
        own = viewer.object_id if viewer else None
        rows = [q for q in rows if q.party_id == own]
    names = {n["object_id"]: n["name"]
             for n in _named(db, [q.party_id for q in rows])}
    return [
        {
            "id": q.id,
            "party_object_id": q.party_id,
            "party_name": names.get(q.party_id, ""),
            "ref": modules.Beleg.ref_for(step.config, q.party_id),
            "amount": _money(q.amount, row.currency),
            "lead_days": q.lead_days,
            "payment_days": q.payment_days,
            "state": q.state or vo.ASKED,
            "sent_on": q.sent_on,
        }
        for q in rows
    ]


def _stages(row: Voucher, flow: vo.Direction) -> list[dict[str, Any]]:
    """Die **zwei** Stufen mit Beschriftung, Verb und Zustand.

    **Ein Storno ist keine Stufe**, und «erledigt» auch nicht: keine ist dann aktiv, kein
    Verb wird angeboten – die gegangene Kette bleibt aber stehen, wo sie stand. Eine
    Fassung, die bei «storniert» alles grau setzt, liesse einen stornierten Beleg aussehen
    wie einen, bei dem nie etwas geschehen ist.
    """
    order = list(vo.STAGES)
    verbs = {vo.OFFER: vo.AGREE_VERB, vo.AGREED: vo.FINISH_VERB}
    # Storniert und erledigt wird erst ab der Zusage – so weit war er also.
    reached = (order.index(row.stage) if row.stage in order
               else order.index(vo.AGREED) + (1 if row.stage == vo.DONE else 0))
    return [
        {
            "key": key,
            "label": flow.label_of(key),
            "verb": verbs.get(key),
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
