"""►►► **Der Belegkopf** – beide Parteien, ihre Anschriften, der Aussteller, und was aus
der Anschrift folgt (Steuersatz, Währung, Ausfuhr, Lieferort, die Positionen). ◄◄◄

Bis zur Zusage eine Ableitung, danach eingefroren (``freeze``). Liest nur den Kern
(``services/voucher``).
"""

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..domain import incoterms as inc
from ..domain import modules
from ..domain import uid as uid_fmt
from ..domain import voucher as vo
from ..models import (
    Article, Order, ProcessStep,
    UserProfile, Voucher, VoucherLine,
)
from . import address, address_book, people, sites
from .voucher import (
    addressee_of, amount_text, balance_of, forget, frozen_lines, house_currency,
    lines_of, minus, once, party_of, process_lines,
)


# ---------------------------------------------------------------------------
# ►► DIE POSITIONEN — und was aus der Anschrift folgt
# ---------------------------------------------------------------------------

def sync_lines(db: Session, row: Voucher, order: Order,
               step: Optional[ProcessStep] = None) -> list[VoucherLine]:
    """►►► **Die Positionen aus dem Prozess nachziehen — nur bis zum ersten Hinausgehen.** ◄◄◄

    Das ist der ganze Einfrier-Mechanismus: solange nichts hinausgegangen ist, sind
    Artikel und Mengen das, was im Auftrag steht; danach nie wieder (``frozen_lines``).
    Verlässt danach ein Stück den Auftrag, passt der Beleg nicht mehr – das sagt
    ``units_problem``, und es bleibt nur «Stornieren».

    **Was ein Mensch eingetragen hat, überlebt** (Preis, Satz, Leistung, Teilbetrag, Zoll):
    nachgezogen werden Artikel und Menge. Eine neue Zeile bekommt die **Leistung aus dem
    Modul** vorbelegt («Was ist zu tun?»).

    **Zwei gleichzeitige Anzeigen legen dieselbe Zeile nicht zweimal an**:
    ``ON CONFLICT DO NOTHING`` gegen ``uq_voucher_lines_article``.

    Danach passen Steuersatz und Währung zur Anschrift (``fit_to_address``) – solange der Beleg
    noch geschrieben wird.
    """
    rows = lines_of(db, row)
    if frozen_lines(row):
        if row.stage == vo.OFFER:
            fit_to_address(db, row, rows)
        return rows
    counts = dict(process_lines(db, order))
    order_index = {a: i for i, a in enumerate(counts)}
    known = {r.article_id for r in rows if r.article_id is not None}
    missing = [a for a in counts if a not in known]
    if missing:
        task = modules.Beleg.instruction_of(step.config) if step is not None else ""
        db.execute(
            pg_insert(VoucherLine)
            .values([{"voucher_id": row.id, "article_id": a, "quantity": counts[a],
                      "vat": vo.DEFAULT_VAT, "position": order_index[a],
                      "text": task or None} for a in missing])
            .on_conflict_do_nothing(index_elements=["voucher_id", "article_id"],
                                    index_where=text("is_active"))
        )
        forget(db)
        rows = lines_of(db, row)
    by_article = {r.article_id: r for r in rows if r.article_id is not None}
    free = [r for r in rows if r.article_id is None]
    for article, n in counts.items():
        found = by_article.get(article)
        if found is not None:
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
    forget(db)
    rows = lines_of(db, row)
    fit_to_address(db, row, rows)
    return rows


def services_of(db: Session, rows: list[VoucherLine]) -> dict[int, bool]:
    """**Ware oder Dienstleistung** je Artikel – eine Abfrage für alle Zeilen."""
    ids = tuple(sorted({ln.article_id for ln in rows if ln.article_id is not None}))
    if not ids:
        return {}
    return dict(once(db, ("services", ids), lambda: {
        a.id: bool(a.is_service)
        for a in db.query(Article).filter(Article.id.in_(ids)).all()}))


def fit_to_address(db: Session, row: Voucher, rows: list[VoucherLine]) -> None:
    """►►► **Steuersatz und Währung folgen der Anschrift** – solange geschrieben wird. ◄◄◄

    Steht ein Satz, den die Anschrift nicht zulässt (Ausland: nur Export bzw. Reverse
    Charge; Inland: kein Nullsatz), wird er der erste zulässige – bewusst ohne Rückfrage:
    der Satz ist hier keine Wahl, sondern eine Folge. Eine **Fremdwährung** gibt es nur mit
    einer Lieferadresse im Ausland; sonst gilt die Hauswährung.

    Nur, wo **wir** den Preis nennen (Einnahme): bei einer Ausgabe steht die Steuer auf
    *seinem* Papier.
    """
    if vo.of(row.direction).quoted_by != vo.BY_US:
        return
    delivery, seat = destination(db, row)
    kinds = services_of(db, rows)
    changed = False
    for ln in rows:
        allowed = vo.vat_choices(service=kinds.get(ln.article_id or 0, False),
                                 delivery_country=delivery, seat_country=seat)
        if ln.vat not in allowed:
            ln.vat = allowed[0]
            changed = True
    house = house_currency(db)
    if not vo.abroad(delivery) and row.currency != house:
        row.currency = house
        changed = True
    if changed:
        db.flush()


def destination(db: Session, row: Voucher) -> tuple[Optional[str], Optional[str]]:
    """►►► **Wohin geht die Leistung?** – (Land der Lieferadresse, Land des Sitzes) des
    Leistungsempfängers. ◄◄◄

    Bei einer Ausgabe sind **wir** der Empfänger. Ohne Adressaten (noch niemand gewählt
    oder mehrere angefragt) gibt es kein Land – und damit kein Ausland.
    """
    if not vo.of(row.direction).collects:
        ours = dict((row.head or {}).get("ours") or _ours(db, row))
        return ours.get("country"), ours.get("country")
    number = party_of(db, row) or addressee_of(db, row)
    who = billing_of(db, row, number) if number is not None else {}
    seat = (who.get("address") or {}).get("country")
    delivery = (who.get("delivery") or {}).get("country") or seat
    return delivery, seat


def has_goods(db: Session, row: Voucher) -> bool:
    """Trägt der Beleg **Ware**? Ohne Ware gibt es keine Lieferbedingung und keinen Zoll."""
    rows = lines_of(db, row)
    kinds = services_of(db, rows)
    return any(not kinds.get(ln.article_id or 0, False) for ln in rows) or not rows


def is_export(db: Session, row: Voucher) -> bool:
    """►►► **Ist das eine Ausfuhr?** – Einnahme, Ware, Lieferadresse im Ausland. ◄◄◄ Dann
    gilt 0 % Export, Zolltarif, Ursprung und Gewicht sind Pflicht, und erledigt ist der
    Beleg erst mit dem Ausfuhrnachweis."""
    if not vo.of(row.direction).collects or minus(row):
        return False
    delivery, _seat = destination(db, row)
    return vo.abroad(delivery) and has_goods(db, row)


def incoterm_place_of(db: Session, row: Voucher) -> Optional[str]:
    """►►► **Der benannte Ort – abgeleitet, nicht getippt.** ◄◄◄

    E/F-Klauseln (EXW, FCA, FAS, FOB): die Versandadresse des Leistungserbringers.
    C/D-Klauseln: die Lieferadresse des Empfängers. Nach der Zusage steht er eingefroren
    am Beleg (``incoterm_place``)."""
    if not row.incoterm:
        return None
    if row.stage != vo.OFFER and row.incoterm_place:
        return row.incoterm_place
    head = document_head(db, row, won=True)
    side = head["supplier"] if inc.place_at_ours(row.incoterm) else head["customer"]
    return side.get("ship_city") or side.get("city") or None


def is_done(db: Session, row: Voucher) -> bool:
    """►►► **Erledigt** – eine Ableitung, kein Knopf: gestellt, Saldo null und, bei einer
    Ausfuhr, der Nachweis da. ◄◄◄"""
    if row.stage != vo.BILLED:
        return False
    if is_export(db, row) and not row.export_number:
        return False
    return balance_of(db, row).even


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
    frozen = (row.head or {}).get("names") or {}
    delivery, seat = destination(db, row)
    out: list[dict[str, Any]] = []
    for ln in rows:
        art = found.get(ln.article_id) if ln.article_id is not None else None
        service = bool(art.is_service) if art else False
        weight = ln.weight_kg if ln.weight_kg is not None else (
            art.weight_kg if art else None)
        net = vo.line_net({"quantity": ln.quantity, "price": ln.price, "part": ln.part},
                          row.currency)
        out.append({
            # **Die Leistung** (Untertitel) und **Ware oder Dienstleistung** – die eine
            # Angabe am Artikel, aus der Steuersatz und Lieferbedingung folgen.
            "text": ln.text,
            "is_service": service,
            "kind_label": "Dienstleistung" if service else "Ware",
            # **Teilbetrag** – ``None`` heisst Vollbetrag; der Betrag der Zeile ist netto.
            "part": amount_text(ln.part, row.currency),
            "full": amount_text(vo.line_net({"quantity": ln.quantity, "price": ln.price},
                                       row.currency) if ln.price is not None else None,
                           row.currency),
            "net": amount_text(net, row.currency) if ln.price is not None else None,
            "weight_kg": f"{weight:.3f}".rstrip("0").rstrip(".") if weight is not None
            else None,
            # **Was an dieser Position wählbar ist** – die Anschrift entscheidet.
            "vat_choices": list(vo.vat_choices(service=service, delivery_country=delivery,
                                               seat_country=seat)),
            "id": ln.id,
            "article_id": ln.article_id,
            "article_object_id": art.object_id if art else None,
            # **Nach der Zusage der Name von damals** (``_freeze_lines``).
            "article_name": (frozen.get(str(ln.article_id))
                             or (art.name if art else "")),
            "quantity": ln.quantity,
            "hs_code": ln.hs_code or (art.hs_code if art else None) or None,
            "origin_country": (ln.origin_country
                               or (art.origin_country if art else None) or None),
            # **Ein Betrag verlässt den Dienst in der Stelligkeit seiner Währung** – die
            # Spalte hat vier Stellen, die Währung meist zwei (JPY null, KWD drei).
            "price": amount_text(ln.price, row.currency),
            "vat": vo.assert_vat(ln.vat),
            "vat_rate": str(vo.vat_of(ln.vat)),
            "vat_label": vo.vat_label(ln.vat),
            "vat_note": vo.vat_note(ln.vat),
        })
    return out


# ---------------------------------------------------------------------------
# ►► DER BELEGKOPF — beide Parteien, wie das Gesetz sie nennt
# ---------------------------------------------------------------------------

def issuer_company(db: Session, row: Voucher):
    """**Unsere Seite des Belegs** – die eingefrorene Gesellschaft.

    **Eine Lesestelle**, damit Belegkopf, Lückenprüfung und Einzahlungsschein nicht drei
    Antworten geben. Der **Betreiber** bleibt der Rückfall: ein Beleg ohne Aussteller wäre
    schlimmer als einer mit dem Betreiber.
    """
    return once(db, ("issuer", row.issuer_company_id), lambda: (
        sites.by_object_id(db, row.issuer_company_id) or sites.find_operator(db)))


def account_for(u: UserProfile, row: Voucher) -> str:
    """►►► **Aus welchem Konto der Beleg seine Anschriften nimmt.** ◄◄◄

    Wer ein **Geschäftskonto** hat (einer Firma zugeordnet ist), bestellt vorbelegt für
    die Firma – ausser der Beleg sagt «an die Person» (``bill_to_company is False``)."""
    if business_possible(u) and row.bill_to_company is not False:
        return address_book.BUSINESS
    return address_book.PRIVATE


def business_possible(u: UserProfile) -> bool:
    """►►► **Kann diese Person hier geschäftlich handeln?** ◄◄◄ Nur mit einer Firma – und
    **nie für eine unserer eigenen Gesellschaften**: die eigene Gesellschaft kann nie
    Gegenpartei sein, niemand stellt sich selbst eine Rechnung. Ein Mitarbeiter handelt
    hier also privat (Spesen sind kein Sonderfall)."""
    firm = u.company
    return firm is not None and not bool(getattr(firm, "is_own", False))


def billing_of(db: Session, row: Voucher,
               party_id: Optional[int] = None) -> dict[str, Any]:
    """**Was auf dem Beleg über den Leistungsempfänger steht** – Name, Anschriften,
    Kontakt, UID.

    ►►► **Es bestellt immer eine PERSON.** ◄◄◄ Ist sie einer Firma zugeordnet, ist die
    Firma der **Rechnungsempfänger** («Muster AG, z. H. Hans Muster») – ausser der Beleg
    sagt «an die Person» (``row.bill_to_company is False``). Die **Anschriften** kommen
    aus **dem Konto**, an das die Rechnung geht (``account_for``): gewählt am Beleg, sonst
    der Standard des Kontos – eine Firma trägt bei uns keine.

    ►►► **Nach der Zusage ist es eine Kopie, keine Ableitung** (``row.head``). ◄◄◄ Für die
    gebundene Partei kommt zurück, was bei der Bestätigung dastand – zieht jemand um oder
    firmiert um, ändert das keine bestätigte Offerte und keine Rechnung, auch nicht den
    Einzahlungsschein und nicht die Vorbelegung der Bezahlkarte.
    """
    number = party_id if party_id is not None else party_of(db, row)
    frozen = row.head or {}
    if frozen and number in (None, frozen.get("party")):
        return dict(frozen.get("billing") or {})
    empty: dict[str, Any] = {"name": None, "email": None, "address": None}
    if number is None:
        return empty

    def derive() -> dict[str, Any]:
        u = db.query(UserProfile).filter(UserProfile.object_id == number).first()
        if u is None:
            return empty
        account = account_for(u, row)
        firm = u.company if account == address_book.BUSINESS else None
        billed = address_book.pick(db, u.id, row.billing_address_id, "billing", account)
        shipped = address_book.pick(db, u.id, row.delivery_address_id, "delivery", account)
        return {
            "party": number,
            "name": sites.legal_name(firm) if firm is not None else people.name(u),
            # **Auf dem Beleg steht die Rechtsperson, nicht ihr Vertreter** – Firma zuerst,
            # die Person als «z. H.» darunter (``people.billing_name``).
            "lines": people.billing_name(u, firm=firm is not None),
            # **Die Rechnungs-E-Mail steht an der Rechnungsadresse des Geschäftskontos** –
            # leer, und privat immer, gilt die der Person.
            "email": (billed.email if billed is not None else None) or u.email,
            "phone": u.phone,
            "uid": uid_of(firm),
            "address": {
                "line1": billed.street1, "line2": billed.street2, "city": billed.city,
                "postal_code": billed.zip, "country": billed.country,
            } if billed is not None else None,
            "shipping": address_book.lines(shipped),
            # **Wohin die Ware geht, als Ort** – für den Steuersatz (Ausland?) und den Ort der
            # Lieferbedingung. Ohne eigene Lieferadresse ist es die Rechnungsadresse.
            "delivery": _place(shipped or billed),
            # Die Firma, an die verrechnet wird (``None`` = an die Person).
            "company_object_id": getattr(firm, "object_id", None) if firm is not None else None,
            "billing_address_id": billed.id if billed is not None else None,
            "delivery_address_id": shipped.id if shipped is not None else None,
            "bill_to_company": firm is not None,
        }

    return dict(once(db, ("billing", getattr(row, "id", None), number, row.bill_to_company,
                           row.billing_address_id, row.delivery_address_id), derive))


def _ours(db: Session, row: Voucher) -> dict[str, Any]:
    """**Unsere Seite des Belegkopfs** – live, bis die Zusage sie einfriert."""
    flow = vo.of(row.direction)
    company = issuer_company(db, row)
    seat = address.of_company(company) if company is not None else None
    return {
        "ours": True,
        "object_id": getattr(company, "object_id", None),
        # **Der Name trägt die Rechtsform** – «Inexxio» ist keine Rechtsperson, «Inexxio
        # AG» ist eine, und auf einem Beleg steht die, die haftet.
        "name": sites.legal_name(company),
        # Eine Adresse ohne Ort ist keine: ``of_company`` liefert immer ein Gerüst,
        # ``has_content`` fragt, ob wirklich etwas drinsteht. **Wer liefert, versendet**
        # – daraus folgt die Beschriftung der zweiten Anschrift.
        **_addresses(address.lines(seat) if address.has_content(seat) else [],
                     [], sends=flow.collects),
        "uid": uid_of(company),
        "email": getattr(company, "email", None),
        "phone": getattr(company, "phone", None),
        # **Der Sitz als Ort** – woher die Ware abgeht (Lieferbedingung) und ob wir im
        # Inland sind.
        "city": (seat or {}).get("city") or None,
        "ship_city": (seat or {}).get("city") or None,
        "country": (seat or {}).get("country") or None,
    }


def _place(a) -> Optional[dict[str, Any]]:
    """Eine Anschrift aus dem Adressbuch als Ort – Ort, PLZ, Land."""
    if a is None:
        return None
    return {"city": a.city or None, "zip": a.zip or None, "country": a.country or None}


def uid_of(company) -> Optional[str]:
    """►►► **Die Nummer einer Firma, wie sie auf dem Beleg steht** – auf BEIDEN Seiten. ◄◄◄

    Die MWST-Nummer zuerst (eine Schweizer heisst «CHE-123.456.789 MWST»), sonst die UID;
    gegliedert über ``domain/uid.display``. Vorher stand unsere Seite roh, die des
    Partners gegliedert und ohne Zusatz – dieselbe Angabe zweimal anders auf einem Papier.
    """
    if company is None:
        return None
    vat = uid_fmt.display(company.vat_number)
    if vat:
        return f"{vat} MWST" if vat.startswith("CHE-") else vat
    return uid_fmt.display(company.uid_number) or None


def creditor_of(db: Session, row: Voucher) -> dict[str, Any]:
    """**Wer das Geld bekommt** – Name und Anschrift für den Einzahlungsschein.

    Die Anschrift ist die der Gesellschaft (``address.of_company``, die eine Stelle);
    Strasse und Nummer stehen darin zusammen – wie beim Zahlenden.
    """
    company = issuer_company(db, row)
    seat = address.of_company(company)
    return {
        "name": sites.legal_name(company) or "",
        "street": seat["street1"] if seat["street1"] != address.DASH else None,
        "zip": seat["zip"] or None,
        "city": seat["city"] or None,
        "country": seat["country"],
    }


def freeze(db: Session, row: Voucher, party: int) -> dict[str, Any]:
    """►►► **Der Belegkopf, wie er bei der Bestätigung dasteht** – zum Einfrieren. ◄◄◄

    Beide Parteien (``ours`` · ``billing``) und der Zahlungsempfänger des Einzahlungs-
    scheins (``creditor``). **Nicht** dabei ist die IBAN: sie sagt, wohin *heute* gezahlt
    wird, und ein eingefrorenes altes Konto schickte das Geld an eine geschlossene Bank.
    """
    return {"party": party, "ours": _ours(db, row), "creditor": creditor_of(db, row),
            "billing": billing_of(db, row, party), "names": _freeze_lines(db, row)}


def _freeze_lines(db: Session, row: Voucher) -> dict[str, str]:
    """►►► **Auch die Positionen sagen nach der Zusage, was bei ihr dastand.** ◄◄◄

    Artikel und Menge frieren durch die Stufe ein (``sync_lines``), Preis und Satz stehen
    an der Zeile. Zwei Angaben las der Beleg aber **live vom Artikel**: die Zoll-Angaben,
    wo die Zeile keine eigenen trug, und den **Namen**. Ein umbenannter Artikel oder eine
    nachgetragene Zolltarifnummer hätte damit eine bestätigte Offerte geändert. Die
    Zoll-Angaben werden darum in die Zeile geschrieben, der Name in den Kopf (je Artikel).
    """
    names: dict[str, str] = {}
    for ln, shown in zip(lines_of(db, row), embed_lines(db, row)):
        ln.hs_code = shown["hs_code"]
        ln.origin_country = shown["origin_country"]
        if ln.article_id is not None:
            names[str(ln.article_id)] = shown["article_name"]
    db.flush()
    return names


def document_head(db: Session, row: Voucher, *, won: bool,
                  party_id: Optional[int] = None,
                  internal: bool = False) -> dict[str, Any]:
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

    ►►► **Jede Seite sagt selbst, ob sie unsere ist** (``ours``). ◄◄◄ Welcher der beiden
    Blöcke die **Gegenpartei** ist, wechselt mit der Richtung – die Oberfläche muss das
    aber wissen, um beim Umschalten des Empfängers den richtigen Block zu tauschen. Ein
    Vergleich auf «Leistungserbringer» wäre ein Spiegel über die API-Grenze, der beim
    ersten Umbenennen still falsch wird; ``ours`` **ist** die Struktur.
    """
    flow = vo.of(row.direction)
    # **Der Adressat, nicht der Vertragspartner**: steht genau einer an, ist er es
    # längst – erst die Zusage bindet ihn.
    look = party_id if party_id is not None else addressee_of(db, row)
    # **Nach der Zusage ist unsere Seite eine Kopie** (``freeze``) – wie die Gegenseite.
    ours = dict((row.head or {}).get("ours") or _ours(db, row))
    theirs = their_side(db, row, look if won else None, internal=internal)
    supplier, customer = (ours, theirs) if flow.collects else (theirs, ours)
    return {
        "supplier": {"label": vo.SUPPLIER, "hint": vo.SUPPLIER_HINT,
                     **_labelled(supplier, sends=True)},
        "customer": {"label": vo.CUSTOMER, "hint": vo.CUSTOMER_HINT,
                     **_labelled(customer, sends=False)},
    }


def _labelled(side: dict[str, Any], *, sends: bool) -> dict[str, Any]:
    """**Beschriftungen sind Darstellung, keine Angabe** – eingefroren wird die Anschrift,
    die Beschriftung kommt immer frisch aus ``_addresses`` (sonst trüge ein bestätigter
    Beleg die Wörter von damals)."""
    if not side.get("address"):
        return side
    fresh = _addresses(side["address"], side.get("shipping") or [], sends=sends)
    return {**side, "address_label": fresh["address_label"],
            "shipping_label": fresh["shipping_label"]}


def _addresses(billed: list[str], shipped: list[str], *, sends: bool) -> dict[str, Any]:
    """►►► **Die Anschriften einer Belegseite – beide, immer, beschriftet.** ◄◄◄

    Eine Regel für beide Seiten: nur eine Anschrift → sie steht unter beiden Beschriftungen;
    keine → keine Beschriftung. ``sends`` heisst «Leistungserbringer»: bei ihm geht die
    Ware ab (Versand), beim Empfänger kommt sie an (Lieferung). Erfunden wird nichts.
    """
    if not billed:
        return {"address": [], "shipping": [],
                "address_label": None, "shipping_label": None}
    return {
        "address": billed,
        "shipping": shipped or billed,
        "address_label": vo.BILLING_LABEL,
        "shipping_label": vo.SHIPPING_FROM_LABEL if sends else vo.SHIPPING_LABEL,
    }


def their_side(db: Session, row: Voucher, party_id: Optional[int], *,
               internal: bool = False) -> dict[str, Any]:
    """**Die Gegenseite des Belegkopfs** – als eine Stelle, weil es zwei Leser gibt.

    Der Belegkopf zeigt **einen** Empfänger; sind mehrere angefragt, braucht die
    Oberfläche dieselbe Seite je Angefragtem (``recipients``). Zweimal gebaut liefen die
    beiden beim nächsten Feld auseinander.

    ``party_id is None`` heisst «dieser Betrachter darf sie nicht sehen» – dann ist die
    Seite leer, nicht erfunden.

    **Welche Rolle sie hat, steht in der Richtung**: die Gegenpartei ist genau dann
    der Leistungserbringer, wenn das Geld **nicht** zu uns fliesst.

    ►►► **Und am Adressaten steht, was noch wählbar ist** (``choice``) – Firma oder
    Person, welche Rechnungs- und welche Lieferadresse. Nur für das Personal, nur vor der
    Zusage: danach ist der Kopf eingefroren.
    """
    sends = not vo.of(row.direction).collects
    who = billing_of(db, row, party_id) if party_id is not None else {}
    seat = who.get("address") or {}
    lines = who.get("lines") or []
    return {
        "ours": False,
        "object_id": party_id,
        "name": (lines or [""])[0],
        "attn": lines[1] if len(lines) > 1 else None,
        # **Dieselbe Auflösung wie bei uns** – zwei Seiten, eine Regel.
        **_addresses(address.lines(address.make(
            street1=seat.get("line1") or "", street2=seat.get("line2") or "",
            zip=seat.get("postal_code") or "", city=seat.get("city") or "",
            country=seat.get("country"),
        )) if seat else [], who.get("shipping") or [], sends=sends),
        "uid": who.get("uid"),
        "email": who.get("email"),
        "phone": who.get("phone"),
        "city": seat.get("city") or None,
        "ship_city": (who.get("delivery") or {}).get("city") or seat.get("city") or None,
        "country": seat.get("country") or None,
        "choice": (choices_of(db, row, party_id, who)
                   if internal and party_id is not None else None),
    }


def choices_of(db: Session, row: Voucher, party_id: int,
               who: dict[str, Any]) -> Optional[dict[str, Any]]:
    """►►► **An wen und wohin – was am Adressaten noch wählbar ist.** ◄◄◄

    ``None``, wo nichts zu wählen ist: nach der Zusage (eingefroren), und an jedem
    anderen als **dem** Adressaten (die Wahl am Beleg gilt ihm). Die Möglichkeiten sind
    sein Adressbuch – eine fremde Anschrift kann man hier nicht wählen.
    """
    if row.stage != vo.OFFER or row.head or party_id != addressee_of(db, row):
        return None
    u = db.query(UserProfile).filter(UserProfile.object_id == party_id).first()
    if u is None:
        return None
    return {
        "company": sites.legal_name(u.company) if business_possible(u) else None,
        "person": people.name(u),
        "bill_to_company": bool(who.get("bill_to_company")),
        "billing_address_id": who.get("billing_address_id"),
        "delivery_address_id": who.get("delivery_address_id"),
        # **Die Anschriften des Kontos, an das die Rechnung geht** – eine aus dem anderen
        # Konto schickte die Rechnung der Firma an die Wohnung.
        "options": [{"id": a.id, "label": address_book.label(a)}
                    for a in address_book.of(db, u, account_for(u, row))],
    }
