"""►►► **Die Anschriften einer Person – zwei Konten, eine Stelle.** ◄◄◄

Konto (die Person selbst) und ERP (das Personal) schreiben **denselben** Datensatz über
**dieselben** Funktionen – gleiche Prüfung, gleiches Audit-Log. Der Beleg liest hier, welche
Anschrift gilt (``pick``), und friert sie mit der Zusage ein.

**Zwei Konten, dieselbe Form** (``ACCOUNTS``): *privat* und das *Geschäftskonto*. Je Konto
gibt es eine **Hauptadresse** (Standard-Rechnungsadresse), optional eine **abweichende
Lieferadresse** und optional **weitere Lieferadressen**. Der einzige Unterschied: im
Geschäftskonto trägt die Rechnungsadresse eine **Rechnungs-E-Mail**; privat geht die
Rechnung an die E-Mail der Person (wie bei jedem Online-Konto).

**Zwei Standards je Konto, und es gibt sie immer, sobald es eine Anschrift gibt**: die
erste wird beides; eine entfernte Lieferadresse gibt ihren Titel an die Hauptadresse
zurück.
"""

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Address, UserProfile
from . import address as fmt
from .admin import log_audit

#: Die beiden Konten einer Person.
PRIVATE, BUSINESS = "private", "business"
ACCOUNTS = (PRIVATE, BUSINESS)
#: Was ein Eintrag trägt – Feldnamen = Spalten.
FIELDS = ("street1", "street2", "zip", "city", "region", "country", "email")
#: **Je Konto genau ein Standard** – als Index, nicht als Prüfung. Gelesen von Migration
#: ``143`` und vom Lifespan-Netz; die frühere Fassung ohne Konto fällt dort weg.
ADDRESS_INDEXES = (
    "DROP INDEX IF EXISTS uq_addresses_default_delivery",
    "DROP INDEX IF EXISTS uq_addresses_default_billing",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_addresses_default_delivery_account "
    "ON addresses (owner_id, account) WHERE is_active AND is_default_delivery",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_addresses_default_billing_account "
    "ON addresses (owner_id, account) WHERE is_active AND is_default_billing",
)
#: Die beiden Standards: ``delivery`` = wohin die Ware, ``billing`` = wohin die Rechnung.
KINDS = {"delivery": "is_default_delivery", "billing": "is_default_billing"}


def account_of(value: Optional[str]) -> str:
    """Das Konto aus einer Angabe – unbekannt ist ein Fehler, nicht «privat»."""
    acc = value or PRIVATE
    if acc not in ACCOUNTS:
        raise HTTPException(400, detail=f"Ein Konto «{acc}» gibt es nicht.")
    return acc


def of(db: Session, owner: UserProfile, account: Optional[str] = None) -> list[Address]:
    """Die aktiven Anschriften einer Person (eines Kontos), älteste zuerst."""
    q = db.query(Address).filter(Address.owner_id == owner.id, Address.is_active.is_(True))
    if account is not None:
        q = q.filter(Address.account == account)
    return q.order_by(Address.id).all()


def default(db: Session, owner_id: int, kind: str, account: str) -> Optional[Address]:
    """Die Standard-Anschrift dieser Art in diesem Konto – oder ``None``."""
    return (db.query(Address)
            .filter(Address.owner_id == owner_id, Address.account == account,
                    Address.is_active.is_(True), getattr(Address, KINDS[kind]).is_(True))
            .first())


def pick(db: Session, owner_id: Optional[int], address_id: Optional[int],
         kind: str, account: str) -> Optional[Address]:
    """►►► **Welche Anschrift gilt?** – die gewählte, wenn sie dieser Person und diesem
    Konto gehört, sonst der Standard des Kontos. ◄◄◄

    Eine fremde Anschrift auf einem Beleg wäre schlimmer als gar keine – und eine aus dem
    anderen Konto ebenso (die Firma bekäme die Rechnung an die Wohnung)."""
    if owner_id is None:
        return None
    if address_id is not None:
        found = (db.query(Address)
                 .filter(Address.id == address_id, Address.owner_id == owner_id,
                         Address.account == account, Address.is_active.is_(True)).first())
        if found is not None:
            return found
    return default(db, owner_id, kind, account)


def lines(a: Optional[Address]) -> list[str]:
    """Die Anschrift als Zeilen, wie sie auf einem Beleg steht (``address.lines``)."""
    if a is None:
        return []
    return fmt.lines(fmt.make(street1=a.street1, street2=a.street2 or "", zip=a.zip,
                              city=a.city, country=a.country))


def label(a: Address) -> str:
    """Eine Zeile, an der man die Anschrift in einer Auswahl wiedererkennt."""
    return ", ".join(p for p in (a.street1, " ".join(x for x in (a.zip, a.city) if x),
                                 a.country) if p)


def _clean(data: dict[str, Any], account: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in FIELDS:
        if key not in data:
            continue
        value = data[key]
        value = value.strip() if isinstance(value, str) else value
        if key == "country":
            value = fmt.iso2(value)
        elif key == "email":
            # **Privat gibt es keine Rechnungs-E-Mail** – die Rechnung geht an die Person.
            value = (value or "").lower() or None if account == BUSINESS else None
        elif key in ("street2", "region"):
            value = value or None
        else:
            value = value or ""
        out[key] = value
    return out


def _assert_complete(a: Address) -> None:
    """**Strasse, PLZ und Ort** – ohne sie ist es keine Anschrift, auf die man liefern
    oder eine Rechnung stellen kann (ein Beleg verlangt sie)."""
    missing = [name for name, v in (("Strasse", a.street1), ("PLZ", a.zip), ("Ort", a.city))
               if not (v or "").strip()]
    if missing:
        raise HTTPException(400, detail=(
            f"Eine Anschrift braucht Strasse, PLZ und Ort – es fehlt: {', '.join(missing)}."))
    if a.email and ("@" not in a.email or "." not in a.email.split("@")[-1]):
        raise HTTPException(400, detail=f"«{a.email}» ist keine E-Mail-Adresse.")


def _set_default(db: Session, a: Address, kind: str, actor_id: Optional[int],
                 object_id: Optional[int]) -> None:
    """Diese Anschrift wird **der** Standard dieser Art in ihrem Konto – die bisherige
    gibt ihn ab. Zuerst abgeben, dann setzen (``flush`` dazwischen): sonst stünden für
    einen Augenblick zwei Standards da, und der Unique-Index wiese den Wechsel ab."""
    col = KINDS[kind]
    for other in of(db, _owner(db, a.owner_id), a.account):
        if other.id != a.id and getattr(other, col):
            setattr(other, col, False)
    db.flush()
    setattr(a, col, True)
    log_audit(db, "addresses", col, str(a.id), actor_id, object_id=object_id)


def _owner(db: Session, owner_id: int) -> UserProfile:
    return db.query(UserProfile).filter(UserProfile.id == owner_id).one()


def add(db: Session, owner: UserProfile, data: dict[str, Any],
        actor_id: Optional[int]) -> Address:
    """Eine Anschrift hinzufügen. **Die erste eines Kontos wird beides** – Liefer- und
    Rechnungsadresse –, sonst gilt, was ``is_default_*`` sagt. Committet nicht.

    **Ein Geschäftskonto gibt es nur mit Firma** – ohne sie wäre es ein zweites
    Privatkonto unter anderem Namen."""
    account = account_of(data.get("account"))
    if account == BUSINESS and owner.company is None:
        raise HTTPException(400, detail=(
            f"«{owner.display_name}» hat kein Geschäftskonto – zuerst die Firma angeben."))
    a = Address(owner_id=owner.id, account=account, **_clean(data, account))
    a.country = a.country or "CH"
    _assert_complete(a)
    db.add(a)
    db.flush()
    log_audit(db, "addresses", None, f"Anschrift «{label(a)}» hinzugefügt", actor_id,
              object_id=owner.object_id)
    for kind, col in KINDS.items():
        if data.get(col) or default(db, owner.id, kind, account) is None:
            _set_default(db, a, kind, actor_id, owner.object_id)
    db.flush()
    return a


def _own(db: Session, owner: UserProfile, address_id: int) -> Address:
    a = (db.query(Address)
         .filter(Address.id == address_id, Address.owner_id == owner.id,
                 Address.is_active.is_(True)).first())
    if a is None:
        raise HTTPException(404, detail=f"Anschrift {address_id} gibt es bei "
                                        f"«{owner.display_name}» nicht.")
    return a


def change(db: Session, owner: UserProfile, address_id: int, data: dict[str, Any],
           actor_id: Optional[int]) -> Address:
    """Eine Anschrift ändern – oder zum Standard machen. **Einen Standard nimmt man nicht
    weg, man gibt ihn einer anderen**: ``is_default_*: false`` ist keine Handlung. Das
    **Konto** einer Anschrift ändert sich nie. Committet nicht."""
    a = _own(db, owner, address_id)
    for key, value in _clean(data, a.account).items():
        if getattr(a, key) != value:
            setattr(a, key, value)
            log_audit(db, "addresses", key, str(value), actor_id, object_id=owner.object_id)
    _assert_complete(a)
    for kind, col in KINDS.items():
        if data.get(col) and not getattr(a, col):
            _set_default(db, a, kind, actor_id, owner.object_id)
    db.flush()
    return a


def remove(db: Session, owner: UserProfile, address_id: int,
           actor_id: Optional[int]) -> None:
    """Eine Anschrift entfernen (Soft-Delete). **Ein Beleg, der sie trägt, behält sie** –
    er hat sie mit der Zusage eingefroren.

    War sie ein Standard, übernimmt ihn im selben Konto **die Hauptadresse** (der
    Standard der anderen Art) – so ist «abweichende Lieferadresse aus» genau das Entfernen
    der Lieferadresse –, sonst die älteste verbliebene. Committet nicht."""
    a = _own(db, owner, address_id)
    was = {kind: getattr(a, col) for kind, col in KINDS.items()}
    a.is_active = False
    a.is_default_delivery = False
    a.is_default_billing = False
    db.flush()
    log_audit(db, "addresses", None, f"Anschrift «{label(a)}» entfernt", actor_id,
              object_id=owner.object_id)
    rest = of(db, owner, a.account)
    for kind, held in was.items():
        if held and rest:
            other = "billing" if kind == "delivery" else "delivery"
            heir = default(db, owner.id, other, a.account) or rest[0]
            _set_default(db, heir, kind, actor_id, owner.object_id)
    db.flush()


# ─── Übernahme der Personenfelder (Migration 143 + Lifespan-Netz) ──────────────────

#: Die Felder am Benutzer, die das Adressbuch ablöst – sie verlieren ihr Mapping und
#: fallen im Folge-Deploy.
OLD_COLUMNS = ("address_line1", "address_line2", "city", "postal_code", "state_region",
               "country", "invoice_first_name", "invoice_last_name",
               "invoice_address_line1", "invoice_address_line2", "invoice_city",
               "invoice_postal_code", "invoice_country", "invoice_email")


def migrate_sql() -> tuple[str, ...]:
    """►►► **Die beiden Anschriften am Benutzer werden Einträge im Adressbuch.** ◄◄◄

    * die **Hauptadresse** → Standard-Lieferadresse des **Privatkontos**;
      Standard-Rechnungsadresse auch, wenn keine eigene Rechnungsadresse dasteht;
    * eine **eigene Rechnungsadresse** → zweiter Eintrag, Standard-Rechnungsadresse –
      **ausser sie ist eine Kopie der Hauptadresse** (das schrieb der frühere Schalter).

    Die frühere Rechnungs-E-Mail geht **nicht** mit: privat geht die Rechnung an die
    E-Mail der Person.

    Danach werden die Felder **geleert** – das macht den Lauf **selbstbegrenzend**:
    der zweite findet nichts mehr, auch wenn jemand später alle Anschriften entfernt.
    Der Name einer abweichenden Rechnungsadresse geht nicht mit: Empfänger ist die Person
    (bzw. ihre Firma), nicht ein dritter Name an einer Anschrift.

    Dieselbe Liste lesen Migration und Lifespan-Netz (die dev-Datenbank fährt kein
    ``alembic upgrade head``, #778)."""
    iso = ("CASE WHEN length(trim(coalesce({c}, ''))) = 2 THEN upper(trim({c})) "
           "ELSE 'CH' END")
    has_main = ("(coalesce(trim(address_line1), '') <> '' "
                "OR coalesce(trim(city), '') <> '')")
    copy = ("(coalesce(invoice_address_line1, '') = coalesce(address_line1, '') "
            "AND coalesce(invoice_postal_code, '') = coalesce(postal_code, '') "
            "AND coalesce(invoice_city, '') = coalesce(city, ''))")
    own_bill = f"(coalesce(trim(invoice_address_line1), '') <> '' AND NOT {copy})"
    cols = ("owner_id, account, street1, street2, zip, city, region, country, email, "
            "is_default_delivery, is_default_billing, is_active, created_at, updated_at")
    return (
        f"INSERT INTO addresses ({cols}) "
        f"SELECT id, 'private', coalesce(address_line1, ''), nullif(address_line2, ''), "
        f"coalesce(postal_code, ''), coalesce(city, ''), nullif(state_region, ''), "
        f"{iso.format(c='country')}, NULL, "
        f"true, NOT {own_bill}, true, now(), now() "
        f"FROM user_profiles WHERE {has_main}",
        f"INSERT INTO addresses ({cols}) "
        f"SELECT id, 'private', coalesce(invoice_address_line1, ''), "
        f"nullif(invoice_address_line2, ''), "
        f"coalesce(invoice_postal_code, ''), coalesce(invoice_city, ''), NULL, "
        f"{iso.format(c='invoice_country')}, NULL, "
        f"NOT {has_main}, true, true, now(), now() "
        f"FROM user_profiles WHERE {own_bill}",
        "UPDATE user_profiles SET " + ", ".join(
            f"{c} = NULL" for c in OLD_COLUMNS if c != "country")
        + f" WHERE {has_main} OR coalesce(trim(invoice_address_line1), '') <> '' "
        f"OR coalesce(invoice_email, '') <> ''",
    )


def business_sql() -> tuple[str, ...]:
    """►►► **Die Anschrift einer fremden Firma wird die des Geschäftskontos.** ◄◄◄

    Bis hierher stand die Anschrift an der **Firma** – jetzt gehört sie der Person, die
    für die Firma bestellt (die Firma trägt nur ihre Identität). Wer einer fremden Firma
    zugeordnet ist und noch **kein** Geschäftskonto-Eintrag hat, bekommt ihre Anschrift
    als Haupt- und Rechnungsadresse. Selbstbegrenzend: wer einen hat, wird übersprungen.
    Die E-Mail der Firma geht nicht mit – leer heisst «die E-Mail der Person»."""
    country = ("CASE WHEN length(trim(coalesce(c.country, ''))) = 2 "
               "THEN upper(trim(c.country)) "
               "WHEN lower(trim(c.country)) = 'deutschland' THEN 'DE' "
               "WHEN lower(trim(c.country)) = 'österreich' THEN 'AT' "
               "WHEN lower(trim(c.country)) = 'frankreich' THEN 'FR' "
               "WHEN lower(trim(c.country)) = 'italien' THEN 'IT' "
               "WHEN lower(trim(c.country)) = 'liechtenstein' THEN 'LI' ELSE 'CH' END")
    return (
        "INSERT INTO addresses (owner_id, account, street1, zip, city, country, "
        "is_default_delivery, is_default_billing, is_active, created_at, updated_at) "
        "SELECT u.id, 'business', trim(concat_ws(' ', c.street, c.street_nr)), "
        "coalesce(c.zip_code, ''), coalesce(c.city, ''), " + country + ", "
        "true, true, true, now(), now() "
        "FROM user_profiles u JOIN company_settings c ON c.object_id = u.company_object_id "
        "WHERE c.is_own IS NOT TRUE AND coalesce(trim(c.city), '') <> '' "
        "AND coalesce(trim(c.street), '') <> '' "
        "AND NOT EXISTS (SELECT 1 FROM addresses a WHERE a.owner_id = u.id "
        "AND a.account = 'business')",
    )
