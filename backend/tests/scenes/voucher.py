"""**Die Szene des Belegs** – ein Haus, eine Partei, ein Artikel mit Zahlungsmodul.

Gemeinsam für ``test_voucher_module`` und ``test_zahlung_ablauf``: das Haus (die
Betreiber-Gesellschaft mit allem, was ein Beleg verlangt, und ihren Rechtstexten), die
Gegenpartei mit Adressbuch, ein Lieferanten-Dokument, ein Artikel, dessen
Erzeugungsprozess das Zahlungsmodul trägt, und der freigegebene Auftrag dazu.
"""

import uuid
from decimal import Decimal
from typing import Optional

from tests.factories import new_firm, new_person


def house(db):
    """**Ein Haus, das Belege stellen kann** – Anschrift, Rechtsform, Kontaktweg,
    MWST-Nummer, IBAN und Rechtstexte. Ohne sie meldet der Beleg Lücken (``gaps``)."""
    from app.models import CompanySettings
    from app.services import objects as obj, sites
    home = sites.find_operator(db)
    if home is None:
        home = CompanySettings(is_operator=True, is_own=True,
                               object_id=obj.next_object_id(db, "organization"))
        db.add(home)
    for field, value in (("company_name", "Inexxio"), ("legal_form", "AG"),
                         ("street", "Industriestrasse"), ("street_nr", "12"),
                         ("zip_code", "9430"), ("city", "St. Margrethen"), ("country", "CH"),
                         ("vat_number", "CHE-100.200.300 MWST"),
                         ("email", "rechnung@inexxio.test"), ("phone", "+41 71 744 00 00"),
                         ("iban", "CH9300762011623852957")):
        if not getattr(home, field):
            setattr(home, field, value)
    db.flush()
    legal_documents(db, home)
    return home


def legal_documents(db, company):
    """AGB und Datenschutz als Dokumente der Gesellschaft – aus der Vorlage, wie die
    Übernahme beim Start sie anlegt (``services/legal``)."""
    from app.services import documents, legal
    for kind, field in legal.FIELD_OF.items():
        if legal.document_of(db, company, kind) is None:
            found = legal.template(kind)
            doc = legal._file_template(db, company, kind, found, found[0], None)
            documents.set_field(db, document_object_id=doc.object_id,
                                object_id=company.object_id, part=None, field=field, actor=None)


def document(db, raw=b"x", mime="image/webp", filename="r.webp", name="Test"):
    """Ein freigegebenes Dokument – wie es ein Feld des Moduls verlangt (Lieferantenrechnung,
    Ausfuhrnachweis)."""
    from app.services import documents
    doc, _ = documents.file(db, raw=raw + uuid.uuid4().hex.encode(), filename=filename,
                            mime=mime, art="Rechnung", name=name, source="file", refs=[],
                            actor=None)
    return doc


def party(db, name: str = "Muster AG", *, form: str = "AG", role: str = "user",
          country: str = "CH", firm: bool = True, own: bool = False, unique: bool = True,
          first_name: Optional[str] = "Anna", last_name: Optional[str] = "Keller",
          street: str = "Feldstrasse 8", zip_code: str = "9450", city: Optional[str] = None):
    """Die Gegenpartei: eine Person (mit fremder Firma, ohne oder als Teil des Hauses) und
    ihre Anschrift im Adressbuch. ``unique`` hängt dem Firmennamen ein Kürzel an (der
    Schlüssel aus Name + Rechtsform ist eindeutig)."""
    from app.services import address_book, sites
    company = None
    if own:
        company = sites.find_operator(db)
    elif firm:
        company = new_firm(db, f"{name} {uuid.uuid4().hex[:4]}" if unique else name, form,
                           country=country)
    user = new_person(db, role, first_name=first_name, last_name=last_name,
                      email=f"{uuid.uuid4().hex[:8]}@example.test",
                      company=company.object_id if company else None)
    user.last_name = last_name
    account = "business" if (company is not None and not own) else "private"
    city = city or ("Altstätten" if country == "CH" else "München")
    address_book.add(db, user, {"account": account, "street1": street, "zip": zip_code,
                                "city": city, "country": country}, None)
    db.flush()
    return user


def article(db, *, name: Optional[str] = None, steps=(), service: bool = False,
            capture: bool = True):
    """Ein Artikel mit Zoll-Angaben; sein Erzeugungsprozess IST der Prozess des Auftrags
    (eine Datenerfassung davor, ausser ``capture=False``)."""
    from app.models import Article
    from app.services import article_process as tpl, objects as obj
    art = Article(object_id=obj.next_object_id(db, "article"),
                  name=name or f"Kranhaken {uuid.uuid4().hex[:4]}", unit="stk",
                  serialization="batch", hs_code="848210", origin_country="CH",
                  weight_kg=Decimal("2.5"), is_service=service)
    db.add(art)
    db.flush()
    lead = [{"module_type": "datenerfassung",
             "config": {"points": [{"label": "Sichtprüfung", "type": "bool"}]}}] if capture else []
    tpl.create_steps(db, art, [*lead, *steps])
    db.flush()
    return art


def release(db, art, *, quantity: int, actor=None):
    """Der freigegebene Erzeugungsauftrag über ``art`` und seine Schritte in Reihenfolge."""
    from app.models import ProcessStep
    from app.services import release as release_svc
    order = release_svc.release(
        db, lines=[{"article_object_id": art.object_id, "quantity": quantity,
                    "origin": "neu", "units": []}],
        steps=[], actor_id=getattr(actor, "id", None))
    db.flush()
    steps = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
             .order_by(ProcessStep.position).all())
    return order, steps


def do(db, order, step, action, actor=None, **payload):
    """Eine Handlung am Beleg über die eine Tür (``voucher_actions.apply``)."""
    from app.services import voucher_actions
    row = voucher_actions.apply(db, order=order, step=step, action=action, payload=payload,
                                actor=actor)
    db.flush()
    return row
