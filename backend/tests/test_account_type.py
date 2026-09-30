"""►►► **Der Kontotyp – und die EINE Rechnungs-E-Mail** (Testnotiz #1042). ◄◄◄

*«Eine Information existiert genau einmal.»* Zwei Dinge waren vermischt:

* die **Rechnungs-E-Mail** gab es **zweimal** als Eingabefeld – einmal bei den Adressen
  und einmal unter den Unternehmensinformationen («Rechnungs-E-Mail (Firma)»);
* die **Sichtbarkeit der Firmenfelder** hing an der **Rolle** (`supplier`), also an einer
  Berechtigungsfrage, obwohl «wer bin ich wirtschaftlich» eine Stammdatenfrage ist.

Geprüft wird über die **echten** Dienstpfade (``people.apply_profile_update``,
``voucher.billing_of``), nicht an einem nachgestellten Zustand: die interessanten Fehler
liegen zwischen den Schritten.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.domain import accounts
from app.models import CompanySettings, UserProfile
from app.schemas.admin import ErpAdminUpdate, UserProfileResponse, UserProfileUpdate
from app.services import people, voucher
from tests.runner import session


def _db():
    return session()


# ---------------------------------------------------------------------------
# ►► die Regel selbst (rein rechnend)
# ---------------------------------------------------------------------------

def test_the_role_supplier_forces_a_business_account():
    """►►► **Ein Lieferant ist immer eine Firma.** ◄◄◄

    Man bestellt nicht bei einer Privatperson, und seine Rechnung trägt eine
    Rechtsperson. Darum **erzwingt** die Rolle den Kontotyp, statt ihn nur vorzuschlagen:
    ein Vorschlag wäre die Stelle, an der ein Lieferant ohne Firmennamen entsteht.

    Bug-Form: die Rolle wird nur als Vorgabe gelesen, ein gespeichertes «privat»
    überstimmt sie.
    """
    assert accounts.effective("supplier", accounts.PRIVATE) == accounts.BUSINESS
    assert accounts.effective("supplier", None) == accounts.BUSINESS
    assert accounts.is_forced("supplier") and not accounts.is_forced("customer")


def test_a_stored_choice_beats_the_company_name():
    """►►► **Wer auf «Privat» stellt, bleibt privat – mit Firmennamen in der Zeile.** ◄◄◄

    *«Vorhandene Werte werden nicht gelöscht, nur nicht angezeigt und nicht verwendet.»*
    Genau darum ist der gespeicherte Wert stärker als die Ableitung – und genau darum
    gibt es **keinen Backfill**: ein ``UPDATE`` mit derselben Bedingung liefe im
    Lifespan-Netz bei jedem Start und flippte diese Wahl zurück.

    Bug-Form: die Ableitung gewinnt (dann ist die Wahl nach dem nächsten Start weg).
    """
    assert accounts.effective("customer", accounts.PRIVATE,
                              company_name="Muster AG") == accounts.PRIVATE
    assert accounts.effective("customer", accounts.BUSINESS,
                              company_name=None) == accounts.BUSINESS


def test_an_old_row_is_read_from_its_company_name():
    """**``NULL`` heisst «noch nicht entschieden» – dann IST der Firmenname die Antwort.**

    Tolerant lesen: ein unbekannter Wert (eine Zeile aus einer künftigen Fassung, oder
    Datenmüll) wird wie ``NULL`` behandelt. Eine Ausnahme wäre eine Ansicht, die an einer
    alten Zeile abstürzt.

    Bug-Form: ``NULL`` gilt stumpf als «Privat» – dann verliert jedes bestehende
    Geschäftskonto seinen Firmennamen auf dem Beleg, ohne dass jemand etwas geändert hat.
    """
    assert accounts.effective("customer", None, company_name="Muster AG") == accounts.BUSINESS
    assert accounts.effective("customer", None, company_name="  ") == accounts.PRIVATE
    assert accounts.effective("customer", "kaputt", company_name="Muster AG") == accounts.BUSINESS


def test_the_uid_stays_optional():
    """**Firmenname und Rechtsform sind Pflicht, die UID nicht.**

    Nur MWST-pflichtige Firmen haben eine – ein Pflichtfeld, das die Hälfte der Firmen
    nicht ausfüllen kann, ist keines.

    Bug-Form: die UID steht in ``REQUIRED_FIELDS``.
    """
    fields = dict(accounts.REQUIRED_FIELDS)
    assert set(fields) == {"company_name", "legal_form"}
    assert accounts.missing({"company_name": "Muster", "legal_form": "AG"}) == ()
    assert accounts.missing({"company_name": "Muster", "legal_form": " "}) == ("Rechtsform",)


# ---------------------------------------------------------------------------
# ►► die Tür: was ankommt und was nicht
# ---------------------------------------------------------------------------

def test_the_second_billing_email_is_gone_from_the_door():
    """►►► **Die Rechnungs-E-Mail gibt es GENAU EINMAL.** ◄◄◄

    Das zweite Feld («Rechnungs-E-Mail (Firma)») ist ersatzlos entfernt – aus UI, Modell
    **und** Tür. Ein trotzdem gesendeter Wert wird **verworfen**: ein Feld, das die
    Oberfläche nicht anbietet, der Dienst aber annimmt, wäre eine Hintertür zu einer
    Angabe, die niemand liest – und genau das war es (es hatte **keinen** Leser).

    Dasselbe gilt für ``invoice_company``: bei Kontotyp «Geschäft» trägt die
    Rechnungsadresse den Firmennamen als erste Zeile, und der steht in ``company_name``.

    Bug-Form: eines der beiden Felder ist wieder im Schema – dann entsteht die Doppelung
    von neuem.
    """
    for schema in (UserProfileUpdate, ErpAdminUpdate, UserProfileResponse):
        assert "company_billing_email" not in schema.model_fields, schema.__name__
        assert "invoice_company" not in schema.model_fields, schema.__name__
    assert not hasattr(UserProfile, "company_billing_email")
    assert not hasattr(UserProfile, "invoice_company")
    # Und die Tür verwirft ihn wirklich, statt ihn zu schlucken:
    sent = UserProfileUpdate.model_validate(
        {"company_billing_email": "x@y.ch", "invoice_company": "Muster AG",
         "invoice_email": "rechnung@muster.ch"})
    assert sent.model_dump(exclude_unset=True) == {"invoice_email": "rechnung@muster.ch"}


def test_the_account_type_is_a_whitelist_at_the_door():
    """**Ein Tippfehler kommt nicht stillschweigend an.**

    Dieselbe Bauart wie ``Role``: die Tür kennt die zwei Werte, und der generierte
    Frontend-Typ trägt damit die Union statt eines freien Strings.

    Bug-Form: ``account_type`` ist ein freier String – dann landet «Geschaeft» in der
    Spalte, und ``effective`` liest es tolerant als «Privat».
    """
    with pytest.raises(Exception):
        UserProfileUpdate.model_validate({"account_type": "Geschaeft"})
    assert UserProfileUpdate.model_validate(
        {"account_type": "business"}).account_type == "business"


def test_the_response_carries_the_effective_account_type():
    """►►► **Die Antwort sagt, was GILT – nie die rohe Spalte.** ◄◄◄

    Sonst müsste jede Oberfläche die Ableitung nachbauen, und die erste, die es vergisst,
    zeigt einem Lieferanten «Privat».

    Bug-Form: die Antwort reicht ``account_type`` durch – dann steht bei einem Lieferanten
    ``null``, und die Oberfläche blendet seine Firmenfelder aus.
    """
    raw = dict(id=1, object_id=100000001, firebase_uid="u", email="a@b.ch",
               photo_url=None, role="supplier", last_sign_in_provider=None,
               passkey_count=0, is_active=True, created_at="2026-01-01T00:00:00Z",
               updated_at="2026-01-01T00:00:00Z", first_name=None, last_name=None,
               phone=None, address_line1=None, address_line2=None, city=None,
               postal_code=None, state_region=None, country="CH", ship_name=None,
               ship_company=None, ship_address_line1=None, ship_address_line2=None,
               ship_city=None, ship_postal_code=None, ship_state_region=None,
               ship_country=None, invoice_first_name=None, invoice_last_name=None,
               invoice_address_line1=None, invoice_address_line2=None,
               invoice_city=None, invoice_postal_code=None, invoice_country=None,
               invoice_email=None, invoice_same_as_shipping=False, date_of_birth=None,
               account_type=None, company_name=None, legal_form=None, uid_number=None,
               vat_number=None, vat_registered=False, trade_register_nr=None,
               trade_register_canton=None, company_website=None,
               bank_account_holder=None, bank_iban=None, bank_bic=None, bank_name=None,
               company_object_id=None, department=None, job_title=None,
               employment_start_date=None, weekly_hours=None, language="de",
               notification_email=True, notification_inapp=True, newsletter_opt_in=False,
               last_login_at=None, terms_accepted_at=None, terms_version=None)
    assert UserProfileResponse.model_validate(raw).account_type == accounts.BUSINESS
    kunde = UserProfileResponse.model_validate({**raw, "role": "customer"})
    assert kunde.account_type == accounts.PRIVATE
    mit_firma = UserProfileResponse.model_validate(
        {**raw, "role": "customer", "company_name": "Muster AG"})
    assert mit_firma.account_type == accounts.BUSINESS


# ---------------------------------------------------------------------------
# ►► der Schreibpfad (echte Dienstpfade)
# ---------------------------------------------------------------------------

def _user(db, **kw) -> UserProfile:
    u = UserProfile(firebase_uid=kw.pop("uid", "uid-1"),
                    email=kw.pop("email", "a@b.ch"), role=kw.pop("role", "customer"),
                    object_id=kw.pop("object_id", None), **kw)
    db.add(u)
    db.flush()
    return u


def test_switching_to_business_needs_a_legal_person():
    """►►► **Ein Geschäftskonto nennt seine Rechtsperson** – serverseitig. ◄◄◄

    «Muster» ist keine Rechtsperson, «Muster AG» ist eine, und auf einem Beleg steht die,
    die haftet (MWSTG Art. 26). Geprüft an der **einen** Schreibstelle, nicht am Feld: die
    Oberfläche ist die freundliche Hälfte, und sie ist nicht der einzige Aufrufer.

    Bug-Formen: (a) die Prüfung steht nur im Browser; (b) die Rechtsform fehlt in der
    Prüfung, und «Muster» geht als Rechtsperson durch.
    """
    db = _db()
    try:
        u = _user(db, first_name="Max", last_name="Muster")
        with pytest.raises(HTTPException) as err:
            people.apply_profile_update(
                db, u, UserProfileUpdate(account_type="business"), actor_id=1)
        assert "Firmenname" in err.value.detail and "Rechtsform" in err.value.detail

        with pytest.raises(HTTPException) as err:
            people.apply_profile_update(
                db, u, UserProfileUpdate(account_type="business", company_name="Muster"),
                actor_id=1)
        assert "Rechtsform" in err.value.detail and "Firmenname" not in err.value.detail

        people.apply_profile_update(
            db, u, UserProfileUpdate(account_type="business", company_name="Muster",
                                     legal_form="AG"), actor_id=1)
        assert people.account_type(u) == accounts.BUSINESS
    finally:
        db.rollback()
        db.close()


def test_an_incomplete_business_row_stays_editable():
    """►►► **Geprüft wird der ÜBERGANG, nicht der Bestand.** ◄◄◄

    Dieselbe Feinheit wie bei ``assert_employment``, und aus demselben Grund: eine Prüfung
    auf den *Zustand* machte jeden bestehenden Lieferanten ohne Rechtsform unbearbeitbar –
    man käme nicht einmal dazu, sie nachzutragen, ohne sie im selben Zug mitzuschicken.

    Bug-Form: die Prüfung fragt den Zustand – dann lässt sich an so einer Zeile **nichts**
    mehr ändern, auch nicht die Telefonnummer.
    """
    db = _db()
    try:
        u = _user(db, uid="uid-2", email="c@d.ch", role="supplier", company_name="Alt AG")
        assert people.account_type(u) == accounts.BUSINESS  # Rolle erzwingt, Rechtsform fehlt
        people.apply_profile_update(db, u, UserProfileUpdate(phone="+41 44 000 00 00"),
                                    actor_id=1)
        assert u.phone == "+41 44 000 00 00"
        # Wer eine Pflichtangabe **leert**, stellt den neuen schlechten Zustand her:
        with pytest.raises(HTTPException):
            people.apply_profile_update(db, u, UserProfileUpdate(company_name=""), actor_id=1)
    finally:
        db.rollback()
        db.close()


def test_an_unknown_account_type_is_refused_by_the_service():
    """**Die Tür ist nicht der einzige Aufrufer** – darum prüft der Dienst selbst.

    Bug-Form: die Prüfung steht nur im Pydantic-``Literal``; wer den Dienst direkt ruft
    (ein Shop-Checkout, ein Import), schreibt einen Wert, den ``effective`` danach
    tolerant als «Privat» liest.
    """
    db = _db()
    try:
        u = _user(db, uid="uid-3", email="e@f.ch")
        with pytest.raises(HTTPException) as err:
            people.apply_profile_update(
                db, u, SimpleNamespace(model_dump=lambda **_: {"account_type": "Geschaeft"}),
                actor_id=1)
        assert "Geschaeft" in err.value.detail
    finally:
        db.rollback()
        db.close()


def test_a_private_account_keeps_its_company_name_but_does_not_use_it():
    """►►► **Ausblenden ist nicht löschen.** ◄◄◄

    Wer auf «Privat» wechselt, behält seinen Firmennamen in der Zeile – auf dem Beleg
    steht er nicht mehr, und im Anzeigenamen ebenso wenig.

    Bug-Formen: (a) ``billing_name`` liest das Feld roh (dann steht die Firma weiter auf
    dem Beleg); (b) der Wert wird beim Wechsel gelöscht (dann ist ein Versehen endgültig).
    """
    db = _db()
    try:
        u = _user(db, uid="uid-4", email="g@h.ch", first_name="Max", last_name="Muster",
                  company_name="Muster", legal_form="AG", account_type=accounts.BUSINESS)
        assert people.billing_name(u) == ["Muster AG", "z. H. Max Muster"]

        people.apply_profile_update(db, u, UserProfileUpdate(account_type="private"),
                                    actor_id=1)
        assert u.company_name == "Muster"          # (b) – nichts gelöscht
        assert people.billing_name(u) == ["Max Muster"]   # (a) – nichts benutzt
    finally:
        db.rollback()
        db.close()


def test_the_legal_person_is_composed_at_exactly_one_place():
    """**«Muster AG» + «AG» ist nicht «Muster AG AG».**

    Der Name der Rechtsperson entsteht in ``sites.legal_name`` – für unsere Gesellschaften
    **und** für ein Geschäftskonto. Eine zweite Zusammensetzung wäre genau die Stelle, an
    der die Form doppelt dasteht.

    Bug-Form: ``billing_name`` hängt die Rechtsform selbst an.
    """
    db = _db()
    try:
        u = _user(db, uid="uid-5", email="i@j.ch", company_name="Muster AG", legal_form="AG",
                  account_type=accounts.BUSINESS)
        assert people.billing_name(u) == ["Muster AG"]
    finally:
        db.rollback()
        db.close()


def test_a_business_account_without_a_person_is_named_by_its_company():
    """**Der Anzeigename fällt auf die Firma zurück – aber nur bei «Geschäft».**

    ``display_name`` ist person-first (#291); die Firma ist der Rückfall. Steht der
    Kontotyp auf «Privat», gilt er nicht: sonst trüge derselbe Datensatz an einer Stelle
    die Firma und auf dem Beleg die Person.

    Bug-Form: der Rückfall fragt nur, ob das Feld belegt ist.
    """
    db = _db()
    try:
        firma = _user(db, uid="uid-6", email="k@l.ch", company_name="Muster AG",
                      account_type=accounts.BUSINESS)
        assert firma.display_name == "Muster AG"
        privat = _user(db, uid="uid-7", email="m@n.ch", company_name="Muster AG",
                       account_type=accounts.PRIVATE)
        assert privat.display_name == "m@n.ch"
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# ►► der Leser: der Beleg
# ---------------------------------------------------------------------------

def test_the_billing_email_is_read_even_without_an_own_billing_address():
    """►►► **Ein Feld, das nur unter einer unsichtbaren Bedingung wirkt, ist schlimmer
    als keines.** ◄◄◄

    ``billing_of`` las die Rechnungs-E-Mail nur, wenn eine **eigene Rechnungsadresse**
    dastand (``own``) – die Oberfläche bietet sie aber unabhängig davon an. Wer bei
    «Rechnung = Lieferung» eine eintrug, schrieb damit in ein Feld, das niemand las: der
    Beleg ging still an die Login-Adresse.

    Bug-Form: die Lesestelle hängt wieder an ``own``.
    """
    db = _db()
    try:
        db.add(CompanySettings(company_name="Wir AG", legal_form="AG"))
        db.flush()
        u = _user(db, uid="uid-8", email="login@kunde.ch", object_id=100000042,
                  first_name="Max", last_name="Muster",
                  invoice_email="rechnung@kunde.ch")
        row = SimpleNamespace(party_id=None, issuer_company_id=None)
        who = voucher.billing_of(db, row, party_id=u.object_id)
        assert who["email"] == "rechnung@kunde.ch"

        u.invoice_email = None
        db.flush()
        assert voucher.billing_of(db, row, party_id=u.object_id)["email"] == "login@kunde.ch"
    finally:
        db.rollback()
        db.close()
