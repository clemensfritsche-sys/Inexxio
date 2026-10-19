"""Personen-Anzeige – **EINE** Stelle für «wie heisst diese Person?».

Die Regel selbst steht am Modell (``UserProfile.display_name``: «Vorname Nachname»
→ Firma → E-Mail, Notiz #291); hier steht die eine Stelle, die sie *anwendet*.

Nachgeschlagen wird in ZWEI verschiedenen Schlüsseln – über die 9-stellige ``object_id``
oder über die interne ``id``. Beides sind Ganzzahlen; wer die falsche Variante erwischt,
bekommt lautlos den falschen (oder keinen) Namen. Darum tragen die Funktionen hier
den Schlüssel **im Namen**.
"""

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import UserProfile
from . import sites
from .admin import log_audit

#: Wer im Haus arbeitet – und damit für **eine** unserer Gesellschaften.
#:
#: ►►► **Das ist die EINE Frage, die die Rolle beantwortet** (Testnotiz #1043). ◄◄◄
#: ``admin`` · ``employee`` · ``user``: *darf ins ERP* ↔ *darf es nicht*. Lieferant ↔
#: Kunde ist eine Aussage über **Vorgänge**, nicht über die Person.
ROLES = ("admin", "employee", "user")
STAFF_ROLES = ("admin", "employee")

#: ►►► **Was ein Firmenname nach sich zieht** (Testnotiz #1043). ◄◄◄ Die Rechtsform macht
#: aus «Muster» die Rechtsperson «Muster AG» – ohne sie ist ein Beleg keiner (MWSTG
#: Art. 26, dieselbe Angabe, die ``sites.legal_name`` an unserer eigenen Seite anhängt).
#: Die **UID bleibt freiwillig**: nur MWST-pflichtige Firmen haben eine, und ein
#: Pflichtfeld, das die Hälfte der Firmen nicht ausfüllen kann, ist keines.

def repair_sql() -> tuple[str, ...]:
    """►►► **Eine Datenänderung braucht IMMER auch ein Netz** (Testnotiz #1043). ◄◄◄

    ``start.sh`` fährt ``alembic upgrade head`` bei jedem Start, startet aber auch, wenn es
    scheitert (#778) – eine Reparatur, die nur in einer Migration steht, erreicht eine
    solche Datenbank nie. Beide Anweisungen hier stehen darum **an einer** Stelle und werden von der Migration **und** vom Lifespan-Netz gelesen;
    zweimal ausgeschrieben wären es zwei Wahrheiten (dieselbe Bauart wie
    ``domain/voucher.invoice_backfill_sql``).

    **(1) Die Rolle wird zum Zugang.** Wer nicht ins ERP darf, heisst ``user`` – vorher
    ``customer`` bzw. ``supplier``. Das ist nicht Kosmetik: ``Role`` an der Tür kennt die
    Altwerte nicht mehr, also liefe **jedes** Speichern an so einer Zeile in ein 422,
    und zwar an einer Angabe, die niemand angefasst hat.

    *(2) Die kopierte Rechnungsadresse stand hier – sie ist mit den Feldern ins Adressbuch
    gegangen (``address_book.migrate_sql`` erkennt die Kopie selbst).*

    Jede ist **selbstbegrenzend**: nach dem ersten Lauf trifft die Bedingung nicht mehr
    zu. Eine Reparatur mit einer gepflegten Liste veraltet (die Lehre aus Migration
    ``110``) – diese hier kann es nicht, weil die Liste **der Katalog selbst** ist
    (``ROLES``).

    ►►► **Geheilt wird, was der Katalog NICHT kennt.** ◄◄◄ Gemessen, nicht geglaubt: die
    erste Fassung stand auf ``WHERE role NOT IN ('admin','employee')`` – sie schrieb damit
    bei **jedem** Start jede Nicht-Personal-Zeile neu, auch die längst richtigen (gemessen:
    zweiter Lauf 2 statt 0 Zeilen). Dieselbe Fehlerform wie bei der Stück-Reparatur in
    Migration ``110``, nur eine Nummer harmloser.
    """
    roles = ", ".join(f"'{r}'" for r in ROLES)
    return (
        f"UPDATE user_profiles SET role = 'user' WHERE role NOT IN ({roles})",
        # ►►► **Eine E-Mail ist klein geschrieben** (CRM Schritt 1) – sonst sind «Hans@x.ch»
        # und «hans@x.ch» zwei Personen, und die Übernahme beim Login findet die erste
        # nicht. Eine Kollision bleibt stehen (sie braucht einen Menschen); selbstbegrenzend.
        "UPDATE user_profiles u SET email = lower(email) WHERE email <> lower(email) "
        "AND NOT EXISTS (SELECT 1 FROM user_profiles o "
        "WHERE o.id <> u.id AND lower(o.email) = lower(u.email))",
        # **Jede Person hat ihre Nummer ab der Anlage** – die Registry zieht
        # ``_backfill_object_registry`` danach nach. Vorher vergab der Feed sie beim Lesen.
        "UPDATE user_profiles SET object_id = nextval('object_id_seq') WHERE object_id IS NULL",
    )


def name(u: Optional[UserProfile]) -> Optional[str]:
    """Anzeigename einer bereits geladenen Person (``None`` bleibt ``None``)."""
    return u.display_name if u else None


def is_business(u: Optional[UserProfile]) -> bool:
    """**Tritt diese Person als FIRMA auf?** – genau dann, wenn sie einer Firma zugeordnet
    ist. Die Firma ist ein eigener Datensatz (CRM Schritt 1); ohne sie ist die Person
    privat."""
    return u is not None and u.company is not None


def billing_name(u: Optional[UserProfile], *, firm: bool = True) -> list[str]:
    """►►► **Wie diese Partei auf einem BELEG steht** – Firma zuerst. ◄◄◄

    ``display_name`` ist bewusst **person-first**, und im ERP ist das richtig. Auf einer
    **Rechnung** ist Schuldner die *Muster AG*, nicht ihr Einkäufer: zurück kommen darum
    **Zeilen** – die Firma (mit Rechtsform, ``sites.legal_name``) und darunter die Person
    als «z. H.». Ohne Firma bleibt die Person – der B2C-Fall, und ebenso, wo der Beleg
    «an die Person» sagt (``firm=False``)."""
    if u is None:
        return []
    person = " ".join(p for p in (u.first_name, u.last_name) if p).strip()
    company = sites.legal_name(u.company) if (firm and is_business(u)) else ""
    if company and person:
        return [company, f"z. H. {person}"]
    return [company or person or u.email]


def name_by_id(db: Session, user_id: Optional[int]) -> Optional[str]:
    """Anzeigename über die **interne** Primärschlüssel-Id (Fremdschlüssel-Spalten
    wie ``created_by``, ``uploaded_by``)."""
    if not user_id:
        return None
    return name(db.query(UserProfile).filter(UserProfile.id == user_id).first())


def assert_employment(db: Session, user: UserProfile, fields: dict[str, Any]) -> None:
    """►►► **Personal gehört zu einer UNSERER Gesellschaften** (Testnotiz #905). ◄◄◄

    Die Zuordnung «Firma der Person» ist eine für alle (CRM Schritt 1): ein Kunde zeigt
    auf seine Firma, ein Mitarbeiter auf unsere. Für Personal muss sie darum **eigen**
    sein – auf einem Beleg steht, wer ihn stellt, und eine Kundenfirma stellt keine.

    **Geprüft wird der ÜBERGANG, nicht der Bestand**: wer Personal *wird* oder als
    Personal die Firma *wechselt*. Eine bestehende Zeile ohne Gesellschaft bleibt
    bearbeitbar – ihre Lücke meldet der Beleg."""
    role = fields.get("role", user.role)
    if role not in STAFF_ROLES:
        return
    company = fields["company_object_id"] if "company_object_id" in fields \
        else user.company_object_id
    if role == user.role and "company_object_id" not in fields:
        return
    who = "Administrator" if role == "admin" else "Mitarbeiter"
    if company is None:
        raise HTTPException(
            400, detail=(f"«{user.display_name}» braucht eine unserer Gesellschaften, um als "
                         f"{who} zu arbeiten – auf einem Beleg steht, wer ihn stellt."))
    sites.require_own(db, company, what=f" – «{user.display_name}» arbeitet als {who}")


def _company_fields(db: Session, fields: dict[str, Any], actor_id: Optional[int], *,
                    staff: bool) -> None:
    """►►► **Die Firma einer Person: genannt, nicht gesucht.** ◄◄◄

    Eine **genannte** Firma (``new_company`` – UID, sonst Name und Rechtsform) wird erkannt
    oder angelegt (``sites.resolve``) und wird zur gewählten. **Eine Nummer wählt nur das
    Personal**: eine Kundin, die eine beliebige Objektnummer schicken dürfte, könnte sich
    jeder Firma anhängen und deren Namen lesen – die Zuordnung über die UID ist die
    einzige, die sie selbst vornimmt. ``None`` (die Zuordnung lösen) darf jede Person.
    Schreibt in ``fields``."""
    new = fields.pop("new_company", None)
    if not staff and fields.get("company_object_id") is not None:
        raise HTTPException(403, detail=(
            "Die eigene Firma nennt man über ihre UID – bzw. Firmenname und Rechtsform."))
    if new:
        fields["company_object_id"] = sites.resolve(
            db, new, actor_id, allow_own=staff).object_id
    oid = fields.get("company_object_id")
    if oid is not None:
        company = sites.by_object_id(db, oid)
        if company is None or not company.is_active:
            raise HTTPException(400, detail=f"«{oid}» ist keine Firma.")


def apply_profile_update(db: Session, user: UserProfile, data, actor_id: int, *,
                         staff: bool) -> UserProfile:
    """Profil-Felder schreiben – **EIN** Pfad für beide Oberflächen.

    Denselben Datensatz beschreiben zwei Wege: der ERP-Benutzer-Datensatz (Personal)
    und die Selbstbedienung im Konto (die Person auf ihre eigenen Daten). Das ist so
    gewollt – beides ist derselbe Datensatz, keine zweite Wahrheit. Nur **protokolliert**
    hat es bisher allein der ERP-Weg: eine im Konto geänderte IBAN hinterliess keine
    Spur im Audit-Log, eine im ERP geänderte schon.

    Diese Stelle vereint beides: gleiche Zuweisung, gleiche Protokollierung, egal von
    welcher Oberfläche. Committet NICHT (der Aufrufer entscheidet).

    **Die Anstellungsregel steht hier und nicht im Router** (``assert_employment``): die
    Tür ist nicht der einzige Aufrufer, und zwei Oberflächen schreiben denselben
    Datensatz. **Dasselbe gilt für die Firma** (``_company_fields``)."""
    fields = data.model_dump(exclude_unset=True)
    _company_fields(db, fields, actor_id, staff=staff)
    assert_employment(db, user, fields)
    for key, value in fields.items():
        old_val = getattr(user, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "user_profiles", key, new_str, actor_id,
                      object_id=user.object_id, old_value=old_str)
        setattr(user, key, value)
    return user


def normalize_email(email: Optional[str]) -> str:
    """Eine E-Mail-Adresse, wie sie gespeichert und verglichen wird: **klein**, ohne Rand."""
    return (email or "").strip().lower()


def by_email(db: Session, email: Optional[str]) -> Optional[UserProfile]:
    """Die Person zu dieser E-Mail – ohne Rücksicht auf Gross-/Kleinschreibung."""
    key = normalize_email(email)
    if not key:
        return None
    return db.query(UserProfile).filter(func.lower(UserProfile.email) == key).first()


def firebase_uid_for(email: str, name: str) -> str:
    """►►► **Das Firebase-Konto zu dieser E-Mail** – gefunden oder angelegt. ◄◄◄

    Eine intern angelegte Person bekommt ihr Konto **sofort**: meldet sie sich später an
    (Magic Link, Google mit derselben Adresse), ist sie über die UID direkt **dieser**
    Datensatz – samt Historie. Gibt es das Konto schon, wird es übernommen."""
    from firebase_admin import auth as fb
    from ..core.auth import _init_firebase
    _init_firebase()
    try:
        return fb.get_user_by_email(email).uid
    except fb.UserNotFoundError:
        pass
    try:
        return fb.create_user(email=email, display_name=name or None,
                              email_verified=False).uid
    except Exception as e:      # noqa: BLE001 – der Dienst nennt den Grund
        raise HTTPException(502, detail=f"Das Anmeldekonto für «{email}» liess sich nicht "
                                        f"anlegen: {e}")


def create_person(db: Session, data, actor: UserProfile) -> UserProfile:
    """►►► **Eine Person anlegen** – ohne dass sie sich je angemeldet hat. ◄◄◄

    Minimum: Vorname, Nachname, E-Mail, Rolle. Die Objektnummer entsteht **sofort**, das
    Firebase-Konto ebenso; die E-Mail ist klein geschrieben und einmalig. Personal-Rollen
    vergibt nur ein Admin – wie an jeder anderen Stelle. Committet."""
    from .objects import next_object_id
    fields = data.model_dump(exclude_unset=True)
    first = (fields.pop("first_name", "") or "").strip()
    last = (fields.pop("last_name", "") or "").strip()
    email = normalize_email(fields.pop("email", ""))
    role = fields.pop("role", "user") or "user"
    missing = [label for label, v in (("Vorname", first), ("Nachname", last),
                                      ("E-Mail", email)) if not v]
    if missing:
        raise HTTPException(400, detail=f"Für eine neue Person fehlt: {', '.join(missing)}.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, detail=f"«{email}» ist keine E-Mail-Adresse.")
    if role in STAFF_ROLES and actor.role != "admin":
        raise HTTPException(403, detail="Personal-Rollen vergibt nur ein Admin.")
    taken = by_email(db, email)
    if taken is not None:
        raise HTTPException(409, detail=f"«{email}» gehört bereits {taken.object_id} "
                                        f"{taken.display_name}.")
    user = UserProfile(first_name=first, last_name=last, email=email, role="user",
                       firebase_uid="")
    _company_fields(db, fields, actor.id, staff=True)
    assert_employment(db, user, {"role": role, **fields})
    uid = firebase_uid_for(email, f"{first} {last}")
    if db.query(UserProfile).filter(UserProfile.firebase_uid == uid).first() is not None:
        raise HTTPException(409, detail=f"Das Anmeldekonto zu «{email}» gehört bereits "
                                        f"einer anderen Person.")
    user.firebase_uid = uid
    user.role = role
    user.company_object_id = fields.get("company_object_id")
    user.object_id = next_object_id(db, "user")
    db.add(user)
    db.flush()
    log_audit(db, "user_profiles", None, f"Person «{user.display_name}» angelegt",
              actor.id, object_id=user.object_id)
    db.commit()
    db.refresh(user)
    return user
