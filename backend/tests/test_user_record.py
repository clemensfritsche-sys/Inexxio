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

def test_the_company_name_is_the_declaration():
    """►►► **Ein Feld statt Schalter plus Feld.** ◄◄◄

    Steht ein Firmenname da, tritt dieser Datensatz als Firma auf – sonst als
    Privatperson. Der frühere Kontotyp sagte dasselbe und konnte ihm widersprechen.

    *Nicht so: «sind alle Firmenfelder gefüllt?» als Erklärung lesen. Dann ist nie etwas
    unvollständig – der Server könnte nie sagen, dass die Rechtsform fehlt, und der Beleg
    wechselte still seinen Empfänger.*

    Bug-Formen: (a) ``is_business`` liest ein zweites Feld; (b) Leerzeichen gelten als
    Firma; (c) die Frage wird an einer Aufrufstelle selbst beantwortet.
    """
    db = _db()
    try:
        assert not people.is_business(None)
        assert not people.is_business(_user(db, uid="d-1", email="d1@x.ch"))
        assert not people.is_business(
            _user(db, uid="d-2", email="d2@x.ch", company_name="   ")), "(b)"
        assert people.is_business(
            _user(db, uid="d-3", email="d3@x.ch", company_name="Muster"))
        assert not hasattr(UserProfile, "account_type"), "(a)"
    finally:
        db.rollback()
        db.close()


def test_naming_a_company_needs_a_legal_form():
    """►►► **Wer eine Firma nennt, nennt ihre Rechtsform** – serverseitig. ◄◄◄

    «Muster» ist keine Rechtsperson, «Muster AG» ist eine, und auf einem Beleg steht die,
    die haftet (MWSTG Art. 26). Das ist die **ganze** Regel, die vom Kontotyp bleibt.

    Bug-Formen: (a) die Prüfung steht nur im Browser; (b) sie nennt die fehlende Angabe
    nicht; (c) sie verlangt zusätzlich die UID (die haben nur MWST-pflichtige Firmen).
    """
    db = _db()
    try:
        u = _user(db, uid="c-1", email="c1@x.ch", first_name="Max", last_name="Muster")
        with pytest.raises(HTTPException) as err:
            people.apply_profile_update(
                db, u, UserProfileUpdate(company_name="Muster"), actor_id=1)
        assert "Rechtsform" in err.value.detail and "Muster" in err.value.detail, "(b)"
        assert "UID" not in err.value.detail, "(c)"

        people.apply_profile_update(
            db, u, UserProfileUpdate(company_name="Muster", legal_form="AG"), actor_id=1)
        assert people.is_business(u) and u.uid_number is None
    finally:
        db.rollback()
        db.close()


def test_an_existing_company_without_a_legal_form_stays_editable():
    """►►► **Geprüft wird der ÜBERGANG, nicht der Bestand.** ◄◄◄

    Dieselbe Feinheit wie bei ``assert_employment``, und aus demselben Grund: eine Prüfung
    auf den *Zustand* machte jede bestehende Zeile ohne Rechtsform unbearbeitbar – man käme
    nicht einmal dazu, sie nachzutragen.

    Bug-Form: die Prüfung fragt den Zustand – dann lässt sich dort **nichts** mehr ändern,
    auch nicht die Telefonnummer.
    """
    db = _db()
    try:
        u = _user(db, uid="c-2", email="c2@x.ch", company_name="Alt AG")
        people.apply_profile_update(db, u, UserProfileUpdate(phone="+41 44 000 00 00"),
                                    actor_id=1)
        assert u.phone == "+41 44 000 00 00"
        # Wer eine Pflichtangabe **leert**, stellt den neuen schlechten Zustand her:
        with pytest.raises(HTTPException):
            people.apply_profile_update(db, u, UserProfileUpdate(legal_form=""), actor_id=1)
    finally:
        db.rollback()
        db.close()


def test_clearing_the_company_name_makes_it_a_private_record():
    """►►► **Das ersetzt den Schalter.** ◄◄◄

    «Privat» war einmal eine eigene Wahl; jetzt ist es die Abwesenheit eines Firmennamens.
    Ihn zu leeren muss darum **erlaubt** sein – sonst wäre ein versehentlich eingetragener
    Name endgültig, und der Datensatz für immer eine Firma.

    Bug-Form: die Prüfung läuft auch beim Leeren (dann verlangt sie die Rechtsform zu
    einer Firma, die es gerade nicht mehr gibt).
    """
    db = _db()
    try:
        # ►►► **Gemessen an der Zeile, an der es ZÄHLT**: ohne Rechtsform. ◄◄◄ Der erste
        # Anlauf nahm eine vollständige Firma – dort fällt die Regel ohnehin nicht an, und
        # die Bug-Form (der Vorab-Ausstieg fehlt) ging durch.
        u = _user(db, uid="c-3", email="c3@x.ch", first_name="Max", last_name="Muster",
                  company_name="Muster")
        people.apply_profile_update(db, u, UserProfileUpdate(company_name=""), actor_id=1)
        assert not people.is_business(u)
        assert people.billing_name(u) == ["Max Muster"]

        # Und auch von einer vollständigen Firma weg – ohne dass etwas gelöscht wird.
        v = _user(db, uid="c-4", email="c4@x.ch", first_name="Eva", last_name="Meier",
                  company_name="Meier", legal_form="GmbH")
        people.apply_profile_update(db, v, UserProfileUpdate(company_name=""), actor_id=1)
        assert not people.is_business(v)
        assert v.legal_form == "GmbH", "Ausblenden ist nicht löschen."
    finally:
        db.rollback()
        db.close()


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

def test_a_private_record_is_named_by_his_own_name():
    """**Firma zuerst, Person als «z. H.»; ohne Firma bleibt die Person.**

    ``display_name`` ist person-first (#291) und fällt auf die Firma zurück; ``billing_name``
    ist firmen-first, weil auf einer Rechnung die Rechtsperson steht.

    Bug-Formen: (a) der Beleg trägt die Firma, obwohl keine dasteht; (b) der Anzeigename
    bevorzugt die Firma vor der Person.
    """
    db = _db()
    try:
        firma = _user(db, uid="n-1", email="n1@x.ch", first_name="Max", last_name="Muster",
                      company_name="Muster", legal_form="AG")
        assert people.billing_name(firma) == ["Muster AG", "z. H. Max Muster"]
        assert firma.display_name == "Max Muster", "(b)"

        privat = _user(db, uid="n-2", email="n2@x.ch", first_name="Eva", last_name="Meier")
        assert people.billing_name(privat) == ["Eva Meier"], "(a)"

        ohne = _user(db, uid="n-3", email="n3@x.ch", company_name="Muster AG")
        assert ohne.display_name == "Muster AG"
    finally:
        db.rollback()
        db.close()


def test_the_legal_person_is_composed_at_exactly_one_place():
    """**«Muster AG» + «AG» ist nicht «Muster AG AG».**

    Der Name der Rechtsperson entsteht in ``sites.legal_name`` – für unsere Gesellschaften
    **und** für einen Benutzer mit Firmennamen.

    Bug-Form: ``billing_name`` hängt die Rechtsform selbst an.
    """
    db = _db()
    try:
        u = _user(db, uid="n-4", email="n4@x.ch", company_name="Muster AG", legal_form="AG")
        assert people.billing_name(u) == ["Muster AG"]
    finally:
        db.rollback()
        db.close()


def test_the_billing_email_is_read_even_without_an_own_billing_address():
    """►►► **Ein Feld, das nur unter einer unsichtbaren Bedingung wirkt, ist schlimmer
    als keines** (Testnotiz #1042). ◄◄◄

    Bug-Form: die Lesestelle hängt wieder an ``own``.
    """
    db = _db()
    try:
        db.add(CompanySettings(company_name="Wir AG", legal_form="AG"))
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
        db.add(CompanySettings(company_name="Wir AG", legal_form="AG"))
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
