"""►►► **Das Adressbuch – die eine Stelle für die Anschriften einer Person.** ◄◄◄

Konto (die Person selbst) und ERP (das Personal) schreiben **denselben** Datensatz über
**dieselben** Funktionen – gleiche Prüfung, gleiches Audit-Log. Der Beleg liest hier, welche
Anschrift gilt (``pick``), und friert sie mit der Zusage ein.

**Zwei Standards, und es gibt sie immer, sobald es eine Anschrift gibt**: die erste wird
beides, eine entfernte Standard-Anschrift gibt ihren Titel an die älteste verbliebene ab.
So beantwortet das Adressbuch «wohin, wenn niemand etwas sagt?» ohne Lücke.
"""

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Address, UserProfile
from . import address as fmt
from .admin import log_audit

#: Was ein Eintrag trägt – Feldnamen = Spalten.
FIELDS = ("street1", "street2", "zip", "city", "region", "country", "email")
#: Die beiden Standards: ``delivery`` = wohin die Ware, ``billing`` = wohin die Rechnung.
KINDS = {"delivery": "is_default_delivery", "billing": "is_default_billing"}


def of(db: Session, owner: UserProfile) -> list[Address]:
    """Die aktiven Anschriften einer Person, älteste zuerst."""
    return (db.query(Address)
            .filter(Address.owner_id == owner.id, Address.is_active.is_(True))
            .order_by(Address.id).all())


def default(db: Session, owner_id: int, kind: str) -> Optional[Address]:
    """Die Standard-Anschrift dieser Art – oder ``None``, wo es gar keine gibt."""
    return (db.query(Address)
            .filter(Address.owner_id == owner_id, Address.is_active.is_(True),
                    getattr(Address, KINDS[kind]).is_(True))
            .first())


def pick(db: Session, owner_id: Optional[int], address_id: Optional[int],
         kind: str) -> Optional[Address]:
    """►►► **Welche Anschrift gilt?** – die gewählte, wenn sie dieser Person gehört. ◄◄◄

    Eine gewählte Anschrift, die nicht (mehr) der Person gehört – weil der Beleg den
    Adressaten gewechselt hat oder sie entfernt wurde –, gilt nicht; dann der Standard.
    Eine fremde Anschrift auf einem Beleg wäre schlimmer als gar keine."""
    if owner_id is None:
        return None
    if address_id is not None:
        found = (db.query(Address)
                 .filter(Address.id == address_id, Address.owner_id == owner_id,
                         Address.is_active.is_(True)).first())
        if found is not None:
            return found
    return default(db, owner_id, kind)


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


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in FIELDS:
        if key not in data:
            continue
        value = data[key]
        value = value.strip() if isinstance(value, str) else value
        if key == "country":
            value = fmt.iso2(value)
        elif key == "email":
            value = (value or "").lower() or None
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
    """Diese Anschrift wird **der** Standard dieser Art – die bisherige gibt ihn ab.

    Zuerst abgeben, dann setzen (mit ``flush`` dazwischen): sonst stünden für einen
    Augenblick zwei Standards da, und der Unique-Index wiese den Wechsel selbst ab."""
    col = KINDS[kind]
    for other in of(db, _owner(db, a.owner_id)):
        if other.id != a.id and getattr(other, col):
            setattr(other, col, False)
    db.flush()
    setattr(a, col, True)
    log_audit(db, "addresses", col, str(a.id), actor_id, object_id=object_id)


def _owner(db: Session, owner_id: int) -> UserProfile:
    return db.query(UserProfile).filter(UserProfile.id == owner_id).one()


def add(db: Session, owner: UserProfile, data: dict[str, Any],
        actor_id: Optional[int]) -> Address:
    """Eine Anschrift hinzufügen. **Die erste wird beides** – Liefer- und
    Rechnungsadresse –, sonst gilt, was ``is_default_*`` sagt. Committet nicht."""
    a = Address(owner_id=owner.id, **_clean(data))
    a.country = a.country or "CH"
    _assert_complete(a)
    db.add(a)
    db.flush()
    log_audit(db, "addresses", None, f"Anschrift «{label(a)}» hinzugefügt", actor_id,
              object_id=owner.object_id)
    for kind, col in KINDS.items():
        if data.get(col) or default(db, owner.id, kind) is None:
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
    weg, man gibt ihn einer anderen**: ``is_default_*: false`` ist darum keine Handlung
    (sonst gäbe es eine Anschrift und keinen Standard). Committet nicht."""
    a = _own(db, owner, address_id)
    for key, value in _clean(data).items():
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
    er hat sie mit der Zusage eingefroren. War sie ein Standard, übernimmt die älteste
    verbliebene. Committet nicht."""
    a = _own(db, owner, address_id)
    was = {kind: getattr(a, col) for kind, col in KINDS.items()}
    a.is_active = False
    a.is_default_delivery = False
    a.is_default_billing = False
    db.flush()
    log_audit(db, "addresses", None, f"Anschrift «{label(a)}» entfernt", actor_id,
              object_id=owner.object_id)
    rest = of(db, owner)
    for kind, held in was.items():
        if held and rest:
            _set_default(db, rest[0], kind, actor_id, owner.object_id)
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

    * die **Hauptadresse** → Standard-Lieferadresse; Standard-Rechnungsadresse auch, wenn
      keine eigene Rechnungsadresse dasteht (dann trägt sie die Rechnungs-E-Mail);
    * eine **eigene Rechnungsadresse** → zweiter Eintrag, Standard-Rechnungsadresse, mit
      der Rechnungs-E-Mail – **ausser sie ist eine Kopie der Hauptadresse** (das schrieb
      der frühere Schalter); dann gibt es nur die eine.

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
    cols = ("owner_id, street1, street2, zip, city, region, country, email, "
            "is_default_delivery, is_default_billing, is_active, created_at, updated_at")
    return (
        f"INSERT INTO addresses ({cols}) "
        f"SELECT id, coalesce(address_line1, ''), nullif(address_line2, ''), "
        f"coalesce(postal_code, ''), coalesce(city, ''), nullif(state_region, ''), "
        f"{iso.format(c='country')}, "
        f"CASE WHEN {own_bill} THEN NULL ELSE nullif(lower(invoice_email), '') END, "
        f"true, NOT {own_bill}, true, now(), now() "
        f"FROM user_profiles WHERE {has_main}",
        f"INSERT INTO addresses ({cols}) "
        f"SELECT id, coalesce(invoice_address_line1, ''), nullif(invoice_address_line2, ''), "
        f"coalesce(invoice_postal_code, ''), coalesce(invoice_city, ''), NULL, "
        f"{iso.format(c='invoice_country')}, nullif(lower(invoice_email), ''), "
        f"NOT {has_main}, true, true, now(), now() "
        f"FROM user_profiles WHERE {own_bill}",
        "UPDATE user_profiles SET " + ", ".join(
            f"{c} = NULL" for c in OLD_COLUMNS if c != "country")
        + f" WHERE {has_main} OR coalesce(trim(invoice_address_line1), '') <> '' "
        f"OR coalesce(invoice_email, '') <> ''",
    )
