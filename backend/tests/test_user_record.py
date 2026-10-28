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
    for name in ("services/people.py", "services/voucher.py", "services/voucher_head.py",
                 "services/voucher_actions.py", "services/voucher_view.py", "core/auth.py",
                 "routers/erp.py", "routers/auth.py"):
        src = (BACKEND / "app" / name).read_text("utf-8")
        for bad in ("'supplier'", '"supplier"', "'customer'", '"customer"'):
            assert f"role == {bad}" not in src and f"role in ({bad}" not in src, (
                f"«{name}» vergleicht die Benutzer-Rolle mit {bad} (c)."
            )


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
            "ship_country", "address_line1", "address_line2", "city", "postal_code",
            "state_region", "country", "invoice_first_name", "invoice_last_name",
            "invoice_address_line1", "invoice_address_line2", "invoice_city",
            "invoice_postal_code", "invoice_country", "invoice_email")
    for schema in (UserProfileUpdate, ErpAdminUpdate, UserProfileResponse):
        for field in gone:
            assert field not in schema.model_fields, f"{schema.__name__}.{field}"
    for field in gone:
        assert not hasattr(UserProfile, field), f"UserProfile.{field}"
    sent = UserProfileUpdate.model_validate(
        {"account_type": "business", "invoice_same_as_shipping": True,
         "ship_city": "Zürich", "invoice_email": "rechnung@muster.ch",
         "address_line1": "Weg 1", "phone": "044"})
    assert sent.model_dump(exclude_unset=True) == {"phone": "044"}, (
        "Die Anschrift steht im Adressbuch – ein Feld am Benutzer ist eine Hintertür.")


# ---------------------------------------------------------------------------
# ►► Der Leser: der Beleg
# ---------------------------------------------------------------------------

def test_the_address_book_has_exactly_one_default_of_each_kind():
    """►►► **Zwei Konten – und je Konto genau ein Standard je Art.** ◄◄◄

    Die erste Anschrift eines Kontos wird beides; eine abweichende Rechnungsadresse übernimmt
    den Titel, die Hauptadresse gibt ihn ab; wird sie entfernt, geht er an die
    **Hauptadresse** zurück – nicht an eine weitere Lieferadresse. Privat gibt es **keine**
    Rechnungs-E-Mail, im Geschäftskonto steht sie an der Anschrift. Ein Geschäftskonto gibt
    es nur mit Firma, und seine Standards sind unabhängig von den privaten.

    Bug-Formen: (a) die erste ist kein Standard; (b) zwei Standards; (c) ein Standard geht
    nach dem Entfernen an eine weitere Lieferadresse statt an die Hauptadresse; (d) eine unvollständige Anschrift geht
    durch; (e) eine fremde Anschrift lässt sich ändern; (f) die Datenbank liesse zwei
    Standards zu; (g) privat bleibt eine Rechnungs-E-Mail stehen; (h) ein Geschäftskonto
    ohne Firma; (i) das Geschäftskonto stiehlt den privaten Standard.
    """
    from app.services import address_book as book
    db = session()
    try:
        u = _user(db, uid="ab-1", email="ab1@x.ch")
        other = _user(db, uid="ab-2", email="ab2@x.ch")
        home = book.add(db, u, {"street1": "Weg 1", "zip": "8000", "city": "Zürich"}, 1)
        assert home.is_default_delivery and home.is_default_billing, "(a)"
        extra = book.add(db, u, {"street1": "Lager 5", "zip": "8000", "city": "Zürich"}, 1)
        assert not extra.is_default_delivery and not extra.is_default_billing
        office = book.add(db, u, {"street1": "Büro 2", "zip": "8400", "city": "Winterthur",
                                  "email": "rechnung@privat.ch",
                                  "is_default_billing": True}, 1)
        db.refresh(home)
        assert office.is_default_billing and not home.is_default_billing, "(b)"
        assert office.email is None, "(g)"
        assert book.pick(db, u.id, None, "billing", book.PRIVATE).id == office.id
        assert book.pick(db, u.id, None, "delivery", book.PRIVATE).id == home.id
        book.change(db, u, office.id, {"is_default_billing": False}, 1)
        assert office.is_default_billing, "Einen Standard nimmt man nicht weg."
        book.remove(db, u, office.id, 1)
        db.refresh(home)
        db.refresh(extra)
        assert home.is_default_billing and not extra.is_default_billing, "(c)"
        # Und spiegelbildlich: «abweichende Lieferadresse aus» gibt den Liefer-Standard an
        # die Hauptadresse zurück, nicht an eine weitere Lieferadresse.
        ship = book.add(db, u, {"street1": "Rampe 9", "zip": "8400", "city": "Winterthur",
                                "is_default_delivery": True}, 1)
        book.remove(db, u, ship.id, 1)
        db.refresh(home)
        db.refresh(extra)
        assert home.is_default_delivery and not extra.is_default_delivery, "(c)"
        with pytest.raises(HTTPException):
            book.add(db, u, {"street1": "Weg 3", "zip": "", "city": "Bern"}, 1)  # (d)
        with pytest.raises(HTTPException) as e:
            book.change(db, other, home.id, {"city": "Basel"}, 1)
        assert e.value.status_code == 404, "(e)"
        assert book.pick(db, other.id, home.id, "billing", book.PRIVATE) is None, "(e)"
        with pytest.raises(HTTPException):
            book.add(db, u, {"account": "business", "street1": "X", "zip": "1",
                             "city": "Y"}, 1)  # (h)
        u.company_object_id = _firm(db, "Acc").object_id
        db.flush()
        db.refresh(u)
        biz = book.add(db, u, {"account": "business", "street1": "Werk 1", "zip": "8400",
                               "city": "Winterthur", "email": "Rechnung@Firma.CH"}, 1)
        db.refresh(home)
        assert biz.is_default_delivery and biz.is_default_billing, "(i)"
        assert home.is_default_delivery and home.is_default_billing, "(i)"
        assert biz.email == "rechnung@firma.ch"
        assert book.pick(db, u.id, home.id, "billing", book.BUSINESS).id == biz.id, (
            "Eine Anschrift aus dem anderen Konto gilt nicht.")
        with pytest.raises(Exception):
            with db.begin_nested():
                db.execute(text(
                    "INSERT INTO addresses (owner_id, account, street1, zip, city, country, "
                    "is_default_delivery, is_default_billing, is_active, created_at, "
                    "updated_at) VALUES (:o, 'private', 'X', '1', 'Y', 'CH', true, false, "
                    "true, now(), now())"), {"o": u.id})
        # (f) – nur der Index hält zwei gleichzeitige Standards auf.
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# ►► Die Firma ist ein Datensatz (CRM Schritt 1)
# ---------------------------------------------------------------------------

def _uid() -> str:
    """Eine **gültige, frische** UID – eine feste kollidierte mit Daten, die schon stehen."""
    import random
    from app.domain import uid as u
    while True:
        digits = "".join(random.choice("0123456789") for _ in range(8))
        check = u._check_digit(digits)
        if check is not None:
            return u.display(f"CHE{digits}{check}")


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
    db = session()
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
    """►►► **Jeder darf eine Firma anlegen – der Schlüssel entscheidet, nie ein Mensch.** ◄◄◄

    Gleiche UID → dieselbe Firma, egal wie der Name getippt ist; ohne UID gleicher Name
    **und** gleiche Rechtsform (Gross-/Kleinschreibung, Leerzeichen, Punkte zählen nicht);
    eine UID-lose Firma bekommt die UID, sobald jemand sie mit Nummer nennt.

    Bug-Formen: (a) zwei Datensätze für dieselbe Firma; (b) eine Firma ohne Rechtsform;
    (c) die neue ist eigen; (d) eine falsche Prüfziffer geht durch; (e) eine unbekannte UID
    ohne Namen legt eine namenlose Firma an; (f) die UID-lose wird nicht übernommen.
    """
    db = session()
    known = _uid()
    try:
        a = _user(db, uid="m-1", email="m1@x.ch")
        b = _user(db, uid="m-2", email="m2@x.ch")
        c = _user(db, uid="m-3", email="m3@x.ch")
        d = _user(db, uid="m-4", email="m4@x.ch")
        people.apply_profile_update(db, a, UserProfileUpdate(new_company={
            "company_name": "Zahnrad  Werke", "legal_form": "GmbH"}), 1, staff=False)
        people.apply_profile_update(db, b, UserProfileUpdate(new_company={
            "company_name": "zahnrad werke GmbH", "legal_form": "G.m.b.H."}), 1, staff=False)
        assert a.company_object_id == b.company_object_id, "(a)"
        # (f) mit Nummer genannt: die UID-lose Firma bekommt sie.
        people.apply_profile_update(db, c, UserProfileUpdate(new_company={
            "company_name": "Zahnrad Werke", "legal_form": "GmbH",
            "uid_number": known.lower().replace("-", "") + " mwst"}), 1, staff=False)
        assert c.company_object_id == a.company_object_id, "(f)"
        db.refresh(a)
        assert a.company.uid_number == known and not a.company.is_own, "(c)"
        # Bekannte UID, anderer Name: dieselbe Firma.
        people.apply_profile_update(db, d, UserProfileUpdate(new_company={
            "company_name": "Ganz anders", "legal_form": "AG",
            "uid_number": known}), 1, staff=False)
        assert d.company_object_id == a.company_object_id, "(a)"
        for bad in ({"company_name": "Neu", "legal_form": " "},                     # (b)
                    {"company_name": "Neu", "legal_form": "AG",
                     "uid_number": "CHE-123.456.789"},                               # (d)
                    {"uid_number": _uid()}):                                         # (e)
            with pytest.raises(HTTPException):
                people.apply_profile_update(db, a, UserProfileUpdate(new_company=bad), 1,
                                            staff=False)
    finally:
        db.rollback()
        db.close()


def test_a_firm_exists_once_even_without_the_service():
    """**Die Dublette ist unmöglich, nicht verboten**: der Unique-Index hält zwei offene
    Firmen mit derselben UID bzw. ohne UID mit gleichem Namen und Rechtsform auf – auch
    dann, wenn niemand den Dienst fragt (zwei gleichzeitige Anlagen). Und der Dienst nennt
    die bestehende Firma, statt «Wert bereits vergeben» zu sagen.

    Bug-Formen: (a) der Index fehlt; (b) ``apply_update`` legt still eine zweite an;
    (c) ein UID-loser Name kollidiert mit einer Firma, die eine UID trägt."""
    from app.services import sites
    db = session()
    db.commit = db.flush
    known = _uid()
    try:
        first = sites.create(db, {"company_name": "Einmal Zufall " + known, "legal_form": "AG",
                                  "uid_number": known}, None)
        with pytest.raises(Exception):
            with db.begin_nested():
                twin = CompanySettings(company_name="Zweimal", legal_form="AG",
                                       uid_key=first.uid_key, name_key="zweimal|ag")
                db.add(twin)
                db.flush()
        other = sites.create(db, {"company_name": "Anders " + known, "legal_form": "AG"}, None)
        with pytest.raises(HTTPException) as e:
            sites.apply_update(db, other, {"uid_number": known}, None, admin=True)
        assert e.value.status_code == 409 and str(first.object_id) in e.value.detail, "(b)"
        same_name = sites.create(db, {"company_name": "Einmal Zufall " + known,
                                      "legal_form": "AG"}, None)
        assert same_name.id != first.id, "(c) – mit UID ist es eine andere Rechtsperson."
    finally:
        db.rollback()
        db.close()


def test_a_customer_names_its_firm_and_never_picks_or_edits_one():
    """►►► **Kunden sehen keine fremden Firmen.** ◄◄◄ Keine Firmensuche (nur Personal),
    keine Zuordnung über eine Objektnummer, keine Zuordnung zu einer unserer
    Gesellschaften – und eine fremde Firma trägt nur ihre Identität.

    Bug-Formen: (a) die Suche ist für jeden Angemeldeten offen; (b) eine Kundin hängt sich
    über eine Nummer an eine beliebige Firma; (c) sie wird über unsere UID unsere
    Mitarbeiterin; (d) eine fremde Firma nimmt eine Anschrift an; (e) der frühere Weg,
    die eigene Firma zu ändern, ist zurück."""
    import inspect
    from app.routers import auth, erp
    from app.services import sites
    src = inspect.getsource(erp.search_companies)
    assert "require_employee" in src, "(a)"
    assert "/me/company" not in inspect.getsource(auth), "(e)"
    assert not hasattr(people, "update_member_company"), "(e)"
    db = session()
    db.commit = db.flush
    try:
        foreign = _firm(db, "Kunde")
        sites._rekey(foreign)
        ours = _uid()
        own = _firm(db, "Wir " + ours, own=True, uid=ours)
        sites._rekey(own)
        db.flush()
        u = _user(db, uid="cn-1", email="cn1@x.ch")
        with pytest.raises(HTTPException) as e:
            people.apply_profile_update(db, u, UserProfileUpdate(
                company_object_id=foreign.object_id), 1, staff=False)
        assert e.value.status_code == 403, "(b)"
        with pytest.raises(HTTPException) as e:
            people.apply_profile_update(db, u, UserProfileUpdate(new_company={
                "uid_number": ours}), 1, staff=False)
        assert "unserer Gesellschaften" in e.value.detail, "(c)"
        with pytest.raises(HTTPException):
            sites.apply_update(db, foreign, {"city": "Bern"}, None, admin=True)   # (d)
        people.apply_profile_update(db, u, UserProfileUpdate(company_object_id=None), 1,
                                    staff=False)
    finally:
        db.rollback()
        db.close()


def test_the_uid_check_digit_is_checked_here():
    """**Die Prüfziffer (eCH-0097, Modulo 11) – ohne Register.** Bug-Formen: (a) eine
    falsche Prüfziffer geht durch; (b) Schreibweisen ergeben verschiedene Schlüssel;
    (c) eine EU-Nummer wird abgewiesen."""
    from app.domain import uid
    assert uid.problem("CHE-123.456.788") is None
    assert uid.problem("CHE-123.456.789"), "(a)"
    assert uid.normalize("che 123.456.788 MWST") == uid.normalize("CHE123456788"), "(b)"
    assert uid.display("che123456788") == "CHE-123.456.788"
    assert uid.problem("DE123456789") is None and uid.problem("ATU12345678") is None, "(c)"
    assert uid.problem("Muster"), "Freitext ist keine UID."


def test_staff_needs_one_of_our_companies():
    """**Personal arbeitet bei einer UNSERER Gesellschaften** – eine Kundenfirma stellt
    keine Belege. Bug-Form: ``assert_employment`` prüft nur, ob es die Firma gibt."""
    db = session()
    try:
        foreign, own = _firm(db, "Kunde"), _firm(db, "Wir", own=True)
        u = _user(db, uid="s-1", email="s1@x.ch", first_name="A", last_name="B")
        with pytest.raises(HTTPException) as e:
            people.apply_profile_update(
                db, u, ErpAdminUpdate(role="employee", company_object_id=foreign.object_id),
                actor_id=1, staff=True)
        assert "unserer Gesellschaften" in e.value.detail
        people.apply_profile_update(
            db, u, ErpAdminUpdate(role="employee", company_object_id=own.object_id),
            actor_id=1, staff=True)
        assert u.role == "employee"
    finally:
        db.rollback()
        db.close()


def test_a_person_is_created_without_ever_logging_in(monkeypatch):
    """**Name + E-Mail + Rolle, Nummer sofort, E-Mail klein und einmalig.** Bug-Formen:
    (a) keine Objektnummer; (b) die E-Mail behält Grossbuchstaben; (c) dieselbe E-Mail in
    anderer Schreibweise gilt als neu; (d) ein Mitarbeiter vergibt eine Personal-Rolle."""
    from app.schemas.admin import PersonCreate
    db = session()
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
    db = session()
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


def test_a_person_carries_no_bank_details():
    """**Eine Bankverbindung gibt es nur an UNSEREN Gesellschaften.** Bug-Form: die Person
    trägt sie wieder (Schema oder Modell)."""
    for cls in (UserProfileResponse, UserProfileUpdate, ErpAdminUpdate):
        assert not [f for f in cls.model_fields if f.startswith("bank_")], cls.__name__
    assert not [c for c in UserProfile.__mapper__.attrs.keys() if c.startswith("bank_")]


# ---------------------------------------------------------------------------
# ►► Cleanup Paket 8+9: eine Regel, eine Stelle
# ---------------------------------------------------------------------------

def test_the_staff_pair_has_exactly_one_home():
    """►►► **«Wer ist Personal?» steht EINMAL** (B-40/B-45): ``people.STAFF_ROLES``. ◄◄◄

    Das Paar stand fünfmal (drei Konstanten, ein Literal, ein ``require_role``). Fünf
    Antworten auf eine Frage laufen beim ersten neuen Rollenwert auseinander.

    Bug-Formen: (a) eine zweite Konstante ``STAFF_ROLES = …``; (b) das Paar als Literal
    irgendwo im Dienst; (c) die Tür ``require_employee`` zählt die Rollen selbst auf.
    """
    pair = re.compile(r'["\']admin["\'],\s*["\']employee["\']\s*\)')
    for path in (BACKEND / "app").rglob("*.py"):
        rel = path.relative_to(BACKEND / "app").as_posix()
        src = path.read_text("utf-8")
        if rel == "services/people.py":
            assert len(re.findall(r"^STAFF_ROLES\s*=", src, re.M)) == 1
            continue
        assert not re.search(r"^\s*STAFF_ROLES\b[^=\n]*=(?!=)", src, re.M), (
            f"«{rel}» definiert STAFF_ROLES ein zweites Mal (a).")
        assert not pair.search(src), f"«{rel}» zählt das Personal-Paar selbst auf (b)."
    auth = (BACKEND / "app" / "core" / "auth.py").read_text("utf-8")
    assert "require_employee = require_role(*STAFF_ROLES)" in auth, (
        "Die Tür zählt die Personal-Rollen selbst auf (c).")


def test_there_is_one_person_search_and_it_knows_the_firm():
    """►►► **EINE Personensuche** (B-41/B-48): ``people.search`` – Nummer, Firma, Name,
    E-Mail –, und jedes Personenfeld liest sie. ◄◄◄

    Vorher zweimal: ``voucher.search_parties`` fand die Personen der Muster AG über den
    Firmennamen, ``places.search`` (das Halter-Feld) nicht – dasselbe Wort, zwei Antworten.
    Der Endpunkt heisst ``GET /erp/people``; der Alias ``/erp/orders/voucher-parties`` stand
    einen Deploy lang daneben und ist mit Cleanup Paket F/G entfernt.

    Bug-Formen: (a) ``places`` sucht wieder selbst (ohne Firma); (b) ``voucher`` hat
    wieder eine eigene Suche; (c) der neue Pfad fehlt; (d) der Alias ist wieder da;
    (e) das Frontend ruft den alten Pfad.
    """
    from app.main import app
    from app.services import objects as obj, places
    db = session()
    try:
        firm = _firm(db, name=f"Kranbau{_uid()[-3:]}Zeta")
        u = _user(db, uid="uid-search", email="lea@zeta.test", first_name="Lea",
                  last_name="Muster", object_id=obj.next_object_id(db, "user"),
                  company_object_id=firm.object_id)
        found = {s.object_id for s in places.search(db, firm.company_name)}
        assert u.object_id in found, (
            "Das Halter-Feld findet die Person nicht über ihre Firma (a).")
        assert u.object_id in {p.object_id for p in people.search(db, firm.company_name)}
    finally:
        db.rollback()
        db.close()
    assert not hasattr(voucher, "search_parties"), "Der Beleg sucht wieder selbst (b)."
    from tests._routes import api_routes
    paths = {path for path, _ in api_routes(app)}
    assert "/api/v1/erp/people" in paths, "Der Pfad der Personensuche fehlt (c)."
    assert "/api/v1/erp/orders/voucher-parties" not in paths, (
        "Der Alias der alten Personensuche ist wieder da (d) – zwei Wege zu einer Suche.")
    client = (BACKEND.parent / "frontend" / "src" / "lib" / "api.ts").read_text("utf-8")
    assert "/api/v1/erp/people?" in client and "voucher-parties" not in client, (
        "Das Frontend ruft noch den alten Pfad (e).")


def test_a_firm_name_is_never_invented():
    """**Was fehlt, wird gesagt statt erfunden** (B-44): eine Firma ohne Namen heisst nicht
    «Inexxio AG». Jede Anlage nennt den Namen; das Modell hat keinen Vorgabewert.
    Bug-Form: ``company_name`` trägt wieder ``default="Inexxio AG"``."""
    assert CompanySettings.__table__.c.company_name.default is None
