"""►►► **Die Rolle ist der Zugang – und der Firmenname die Erklärung** (#1042/#1043). ◄◄◄

Zwei Vereinfachungen am Benutzer-Datensatz, und beide nehmen etwas **weg**:

* Die Rolle beantwortet nur noch *darf diese Person ins ERP?* – «Lieferant» und «Kunde»
  waren eine Aussage über **Vorgänge**, nicht über die Person: wer Partner einer Ausgabe
  ist, ist dort Lieferant, bei einer Einnahme Kunde, und dieselbe Person kann beides sein.
* Der **Firmenname** sagt, ob dieser Datensatz als Firma auftritt. Ein Kontotyp
  (*Privat ↔ Geschäft*) stand daneben und sagte dasselbe.

Dazu die Adressen: **zwei, nicht drei**, und die Rechnungsadresse ist **freiwillig**.

Geprüft wird über die **echten** Dienstpfade (``people.apply_profile_update``,
``voucher.billing_of``) und gegen echtes PostgreSQL – die interessanten Fehler liegen
zwischen den Schritten.
"""

import re
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.models import CompanySettings, UserProfile
from app.schemas.admin import ErpAdminUpdate, UserProfileResponse, UserProfileUpdate
from app.services import people, voucher
from tests.runner import BACKEND, session


def _db():
    return session()


def _user(db, **kw) -> UserProfile:
    u = UserProfile(firebase_uid=kw.pop("uid", "uid-1"),
                    email=kw.pop("email", "a@b.ch"), role=kw.pop("role", "user"),
                    object_id=kw.pop("object_id", None), **kw)
    db.add(u)
    db.flush()
    return u


# ---------------------------------------------------------------------------
# ►► Die Rolle: der Zugang, nichts weiter
# ---------------------------------------------------------------------------

def test_the_role_is_the_access_and_nothing_else():
    """►►► **Drei Werte, und sie sagen den Zugang.** ◄◄◄

    *«Lieferant ↔ Kunde ist eine Eigenschaft des VORGANGS, nicht der Person.»* Eine Spalte
    am Datensatz muss sich für eines entscheiden und liegt damit in der Hälfte der Fälle
    falsch – gelesen wurde die Unterscheidung ohnehin von niemandem: jedes echte Tor im
    Haus fragt ``STAFF_ROLES``.

    Bug-Formen: (a) die Tür kennt wieder einen Vorgangs-Wert; (b) ``ROLES`` und das
    ``Literal`` laufen auseinander; (c) irgendeine Stelle im Dienst vergleicht noch mit
    «supplier»/«customer» als *Rolle*.
    """
    assert people.ROLES == ("admin", "employee", "user")
    assert set(people.STAFF_ROLES) < set(people.ROLES)
    door = re.search(r'Role = Literal\[([^\]]+)\]',
                     (BACKEND / "app" / "schemas" / "admin.py").read_text("utf-8"))
    assert door and sorted(re.findall(r'"(\w+)"', door.group(1))) == sorted(people.ROLES), (
        "Die Tür kennt andere Rollen als der Dienst (a/b)."
    )
    # (c) – als **Rolle** gibt es die beiden Wörter nicht mehr. ``voucher`` kennt sie als
    # die MWSTG-Rollen des Papiers (Leistungserbringer ↔ -empfänger); gemeint ist hier
    # die Rolle des *Benutzers*, und die wird gegen eine Zeichenkette verglichen.
    for name in ("services/people.py", "services/voucher.py", "core/auth.py",
                 "routers/erp.py", "routers/auth.py"):
        src = (BACKEND / "app" / name).read_text("utf-8")
        for bad in ("'supplier'", '"supplier"', "'customer'", '"customer"'):
            assert f"role == {bad}" not in src and f"role in ({bad}" not in src, (
                f"«{name}» vergleicht die Benutzer-Rolle mit {bad} (c)."
            )


def test_the_repair_turns_an_old_role_into_access():
    """►►► **Eine Datenänderung braucht IMMER auch ein Netz** (gemessen). ◄◄◄

    Die dev-Datenbank fährt kein ``alembic upgrade head`` (#778). Ohne die Reparatur bliebe
    ``role = 'customer'`` stehen – und ``Role`` an der Tür kennt den Wert nicht mehr: jedes
    Speichern an so einer Zeile wäre ein 422 an einer Angabe, die niemand angefasst hat.

    Bug-Formen: (a) die Reparatur trifft die Altwerte nicht; (b) sie trifft **auch**
    Personal (dann verliert ein Admin seinen Zugang); (c) sie ist nicht selbstbegrenzend.
    """
    db = _db()
    try:
        alt = _user(db, uid="r-1", email="r1@x.ch", role="customer")
        lief = _user(db, uid="r-2", email="r2@x.ch", role="supplier")
        chef = _user(db, uid="r-3", email="r3@x.ch", role="admin")
        for stmt in people.repair_sql():
            db.execute(text(stmt))
        db.expire_all()
        assert alt.role == "user" and lief.role == "user", "Altwert bleibt stehen (a)."
        assert chef.role == "admin", "Die Reparatur nimmt Personal den Zugang (b)."
        # (c) – der zweite Lauf findet nichts mehr.
        again = db.execute(text(people.repair_sql()[0])).rowcount
        assert again == 0, "Die Reparatur ist nicht selbstbegrenzend (c)."
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# ►► Der Firmenname ist die Erklärung
# ---------------------------------------------------------------------------

def test_the_old_switches_are_gone_from_the_door():
    """►►► **Was die Oberfläche nicht anbietet, nimmt der Dienst nicht an.** ◄◄◄

    Vier Angaben haben ihre Bedeutung verloren: ``account_type`` (der Firmenname sagt es),
    ``invoice_same_as_shipping`` (die Felder sagen es), die acht ``ship_*`` (es gibt **zwei**
    Anschriften, nicht drei) und die beiden aus #1042. Ein trotzdem gesendeter Wert wird
    **verworfen** – ein Feld, das der Dienst annimmt und niemand liest, ist eine Hintertür.

    Bug-Form: eines der Felder ist wieder im Schema – dann entsteht die Doppelung von neuem.
    """
    gone = ("account_type", "invoice_same_as_shipping", "company_billing_email",
            "invoice_company", "ship_name", "ship_company", "ship_address_line1",
            "ship_address_line2", "ship_city", "ship_postal_code", "ship_state_region",
            "ship_country")
    for schema in (UserProfileUpdate, ErpAdminUpdate, UserProfileResponse):
        for field in gone:
            assert field not in schema.model_fields, f"{schema.__name__}.{field}"
    for field in gone:
        assert not hasattr(UserProfile, field), f"UserProfile.{field}"
    sent = UserProfileUpdate.model_validate(
        {"account_type": "business", "invoice_same_as_shipping": True,
         "ship_city": "Zürich", "invoice_email": "rechnung@muster.ch"})
    assert sent.model_dump(exclude_unset=True) == {"invoice_email": "rechnung@muster.ch"}


# ---------------------------------------------------------------------------
# ►► Der Leser: der Beleg
# ---------------------------------------------------------------------------

def test_the_billing_email_is_read_even_without_an_own_billing_address():
    """►►► **Ein Feld, das nur unter einer unsichtbaren Bedingung wirkt, ist schlimmer
    als keines** (Testnotiz #1042). ◄◄◄

    Bug-Form: die Lesestelle hängt wieder an ``own``.
    """
    db = _db()
    try:
        db.add(CompanySettings(company_name="Wir AG", legal_form="AG", is_own=True))
        db.flush()
        u = _user(db, uid="b-1", email="login@kunde.ch", object_id=100000142,
                  first_name="Max", last_name="Muster",
                  invoice_email="rechnung@kunde.ch")
        row = SimpleNamespace(party_id=None, issuer_company_id=None)
        assert voucher.billing_of(db, row, party_id=u.object_id)["email"] \
            == "rechnung@kunde.ch"
        u.invoice_email = None
        db.flush()
        assert voucher.billing_of(db, row, party_id=u.object_id)["email"] \
            == "login@kunde.ch"
    finally:
        db.rollback()
        db.close()


def test_an_empty_billing_address_falls_back_to_the_delivery_address():
    """►►► **Leer heisst erben – und eine KOPIE wird geräumt** (Testnotiz #1043). ◄◄◄

    Die Rechnungsadresse ist freiwillig: ob eine eigene hinterlegt ist, sagen die Felder
    selbst. Der frühere Schalter «Rechnungsadresse = Lieferadresse» liess die Oberfläche
    die Hauptadresse **hineinkopieren** – ``billing_of`` liest sie seither als *eigene*,
    und der Beleg zeigt dieselbe Anschrift zweimal untereinander.

    Bug-Formen: (a) leer wird nicht geerbt (dann steht auf dem Beleg keine Anschrift);
    (b) die Reparatur räumt eine **abweichende** Rechnungsadresse weg (Datenverlust);
    (c) sie räumt die Kopie nicht (dann bleibt die Doppelung).
    """
    db = _db()
    try:
        db.add(CompanySettings(company_name="Wir AG", legal_form="AG", is_own=True))
        db.flush()
        row = SimpleNamespace(party_id=None, issuer_company_id=None)

        leer = _user(db, uid="a-1", email="a1@x.ch", object_id=100000143,
                     first_name="Max", last_name="Muster",
                     address_line1="Industriestrasse 12", city="Zürich",
                     postal_code="8000", country="CH")
        who = voucher.billing_of(db, row, party_id=leer.object_id)
        assert who["address"]["line1"] == "Industriestrasse 12", "(a)"
        assert who["shipping"] == [], "Zweimal dieselbe Anschrift (a)."

        eigen = _user(db, uid="a-2", email="a2@x.ch", object_id=100000144,
                      first_name="Max", last_name="Muster",
                      address_line1="Industriestrasse 12", city="Zürich",
                      postal_code="8000", country="CH",
                      invoice_address_line1="Werkstrasse 3", invoice_city="Winterthur",
                      invoice_postal_code="8400", invoice_country="CH")
        who = voucher.billing_of(db, row, party_id=eigen.object_id)
        assert who["address"]["line1"] == "Werkstrasse 3"
        assert who["shipping"], "Die zweite Anschrift fehlt."

        kopie = _user(db, uid="a-3", email="a3@x.ch", object_id=100000145,
                      first_name="Max", last_name="Muster",
                      address_line1="Industriestrasse 12", city="Zürich",
                      postal_code="8000", country="CH",
                      invoice_first_name="Max", invoice_last_name="Muster",
                      invoice_address_line1="Industriestrasse 12", invoice_city="Zürich",
                      invoice_postal_code="8000", invoice_country="CH")
        for stmt in people.repair_sql():
            db.execute(text(stmt))
        db.expire_all()
        assert kopie.invoice_address_line1 is None, "Die Kopie bleibt stehen (c)."
        assert eigen.invoice_address_line1 == "Werkstrasse 3", "Datenverlust (b)."
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# ►► Die Firma ist ein Datensatz (CRM Schritt 1)
# ---------------------------------------------------------------------------

def _firm(db, name="Muster", form="AG", *, own=False, uid=None) -> CompanySettings:
    from app.services import objects as obj
    c = CompanySettings(object_id=obj.next_object_id(db, "organization"), company_name=name,
                        legal_form=form, is_own=own, uid_number=uid, email="", country="CH")
    db.add(c)
    db.flush()
    return c


def test_a_person_is_a_firm_through_its_link():
    """**Firma zuerst, Person als «z. H.»** – und die Firma kommt aus ihrem Datensatz.
    Bug-Form: die Rechtsform fehlt am Namen, oder eine Person ohne Firma gilt als Firma."""
    db = _db()
    try:
        privat = _user(db, uid="f-1", email="f1@x.ch", first_name="Eva", last_name="Meier")
        assert not people.is_business(privat)
        assert people.billing_name(privat) == ["Eva Meier"]
        firm = _firm(db)
        u = _user(db, uid="f-2", email="f2@x.ch", first_name="Max", last_name="Muster",
                  company_object_id=firm.object_id)
        db.refresh(u)
        assert people.billing_name(u) == ["Muster AG", "z. H. Max Muster"]
    finally:
        db.rollback()
        db.close()


def test_a_named_company_is_found_before_it_is_created():
    """**Eindeutig gleich → dieselbe Firma; sonst eine neue, fremde.** Bug-Formen: (a) zwei
    Datensätze für dieselbe Firma; (b) eine Firma ohne Rechtsform; (c) die neue ist eigen."""
    db = _db()
    try:
        a = _user(db, uid="m-1", email="m1@x.ch")
        b = _user(db, uid="m-2", email="m2@x.ch")
        c = _user(db, uid="m-3", email="m3@x.ch")
        new = {"company_name": "Zahnrad  Werke", "legal_form": "GmbH",
               "uid_number": "CHE-111.222.333"}
        people.apply_profile_update(db, a, UserProfileUpdate(new_company=new), actor_id=1)
        people.apply_profile_update(
            db, b, UserProfileUpdate(new_company={"company_name": "zahnrad werke",
                                                  "legal_form": "gmbh"}), actor_id=1)
        people.apply_profile_update(
            db, c, UserProfileUpdate(new_company={"company_name": "Andere AG",
                                                  "legal_form": "x",
                                                  "uid_number": "che111222333"}), actor_id=1)
        assert a.company_object_id == b.company_object_id == c.company_object_id, "(a)"
        db.refresh(a)
        assert not a.company.is_own, "(c)"
        with pytest.raises(HTTPException):
            people.apply_profile_update(
                db, a, UserProfileUpdate(new_company={"company_name": "Neu",
                                                      "legal_form": " "}), actor_id=1)
    finally:
        db.rollback()
        db.close()


def test_staff_needs_one_of_our_companies():
    """**Personal arbeitet bei einer UNSERER Gesellschaften** – eine Kundenfirma stellt
    keine Belege. Bug-Form: ``assert_employment`` prüft nur, ob es die Firma gibt."""
    db = _db()
    try:
        foreign, own = _firm(db, "Kunde"), _firm(db, "Wir", own=True)
        u = _user(db, uid="s-1", email="s1@x.ch", first_name="A", last_name="B")
        with pytest.raises(HTTPException) as e:
            people.apply_profile_update(
                db, u, ErpAdminUpdate(role="employee", company_object_id=foreign.object_id),
                actor_id=1)
        assert "unserer Gesellschaften" in e.value.detail
        people.apply_profile_update(
            db, u, ErpAdminUpdate(role="employee", company_object_id=own.object_id),
            actor_id=1)
        assert u.role == "employee"
    finally:
        db.rollback()
        db.close()


def test_a_person_is_created_without_ever_logging_in(monkeypatch):
    """**Name + E-Mail + Rolle, Nummer sofort, E-Mail klein und einmalig.** Bug-Formen:
    (a) keine Objektnummer; (b) die E-Mail behält Grossbuchstaben; (c) dieselbe E-Mail in
    anderer Schreibweise gilt als neu; (d) ein Mitarbeiter vergibt eine Personal-Rolle."""
    from app.schemas.admin import PersonCreate
    db = _db()
    db.commit = db.flush     # die Szene wird am Ende verworfen
    monkeypatch.setattr(people, "firebase_uid_for", lambda email, name: f"fb-{email}")
    try:
        admin = SimpleNamespace(id=1, role="admin")
        u = people.create_person(db, PersonCreate(first_name="Hans", last_name="Muster",
                                                  email=" Hans.Muster@Firma.CH "), admin)
        assert u.object_id, "(a)"
        assert u.email == "hans.muster@firma.ch", "(b)"
        assert u.firebase_uid == "fb-hans.muster@firma.ch"
        with pytest.raises(HTTPException) as e:
            people.create_person(db, PersonCreate(first_name="X", last_name="Y",
                                                  email="HANS.MUSTER@firma.ch"), admin)
        assert e.value.status_code == 409 and str(u.object_id) in e.value.detail, "(c)"
        with pytest.raises(HTTPException) as e:
            people.create_person(db, PersonCreate(first_name="X", last_name="Y",
                                                  email="neu@firma.ch", role="employee"),
                                 SimpleNamespace(id=2, role="employee"))
        assert e.value.status_code == 403, "(d)"
        with pytest.raises(HTTPException):
            people.create_person(db, PersonCreate(first_name="", last_name="Y",
                                                  email="leer@firma.ch"), admin)
    finally:
        db.rollback()
        db.close()


def test_a_foreign_company_never_acts_as_ours():
    """**Belegsteller, Betreiber, Gebiet – nur eigene.** Bug-Form: ein Filter fehlt, und
    die IBAN eines Kunden landet im Einzahlungsschein."""
    from app.services import sites
    db = _db()
    try:
        foreign = _firm(db, "Kunde")
        with pytest.raises(HTTPException):
            sites.require_own(db, foreign.object_id)
        assert foreign not in sites.selectable_companies(db)
        with pytest.raises(HTTPException):
            sites.set_territory(db, "EUR", foreign.object_id, None)
    finally:
        db.rollback()
        db.close()
