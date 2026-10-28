"""Personen – **EINE** Stelle für «wie heisst sie?», «gibt es sie?» und «leg sie an».

* Der Name: die Regel steht am Modell (``UserProfile.display_name``: «Vorname Nachname»
  → Firma → E-Mail); hier steht die Stelle, die sie *anwendet*.
* Eine Person entsteht nur in ``ensure`` (Anmeldung, Personal, Mail, Anfrage, Newsletter);
  die E-Mail-Regel ist ``is_email``; gesucht wird mit ``search``.

Nachgeschlagen wird in ZWEI verschiedenen Schlüsseln – über die 9-stellige ``object_id``
oder über die interne ``id``. Beides sind Ganzzahlen; wer die falsche Variante erwischt,
bekommt lautlos den falschen (oder keinen) Namen. Darum tragen die Funktionen hier
den Schlüssel **im Namen**.
"""

import re
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import CompanySettings, UserProfile
from . import lookup, sites
from .admin import log_audit

#: Wer im Haus arbeitet – und damit für **eine** unserer Gesellschaften.
#:
#: ►►► **Das ist die EINE Frage, die die Rolle beantwortet.** ◄◄◄
#: ``admin`` · ``employee`` · ``user``: *darf ins ERP* ↔ *darf es nicht*. Lieferant ↔
#: Kunde ist eine Aussage über **Vorgänge**, nicht über die Person.
ROLES = ("admin", "employee", "user")
STAFF_ROLES = ("admin", "employee")

#: ►►► **Pflicht ist, was das Haus wirklich braucht** – EINE Liste für Konto und ERP. ◄◄◄
#: Das Konto zeigt daraus den Fortschritt, das ERP die Zahl «zu tun» am Symbol; beide
#: spiegeln, entschieden wird hier. Das Geburtsdatum ist Pflicht für das **Personal**: es
#: bestimmt Jugendschutz und gesetzliche Ferien der Zeiterfassung.
_REQUIRED: tuple[tuple[str, str, str, bool], ...] = (
    # (Feld, Wort, Abschnitt, nur Personal)
    ("first_name", "Vorname", "person", False),
    ("last_name", "Nachname", "person", False),
    ("phone", "Telefon", "person", False),
    ("date_of_birth", "Geburtsdatum", "person", True),
    # Mindestens eine Anschrift – Strasse, PLZ und Ort prüft das Adressbuch beim Anlegen.
    ("addresses", "Adresse", "adressen", False),
)


def required_fields(u: UserProfile) -> list[tuple[str, str, str]]:
    """Die Pflichtangaben dieser Person (Feld, Wort, Abschnitt)."""
    staff = u.role in STAFF_ROLES
    return [(k, label, sec) for k, label, sec, only_staff in _REQUIRED if staff or not only_staff]


def missing_fields(u: UserProfile) -> list[dict]:
    """Was davon fehlt – in der Reihenfolge der Seite."""
    out = []
    for key, label, section in required_fields(u):
        val = getattr(u, key, None)
        empty = val is None or (isinstance(val, str) and not val.strip()) or \
            (isinstance(val, list) and not val)
        if empty:
            out.append({"key": key, "label": label, "section": section})
    return out


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
    """►►► **Personal gehört zu einer UNSERER Gesellschaften.** ◄◄◄

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
    if fields.get("phone"):
        fields["phone"] = tidy_phone(user, fields["phone"])
    for key, value in fields.items():
        old_val = getattr(user, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "user_profiles", key, new_str, actor_id,
                      object_id=user.object_id, old_value=old_str)
        setattr(user, key, value)
    return user


def tidy_phone(user: UserProfile, raw: str) -> str:
    """►►► **Die Telefonnummer so, wie man sie liest** – «+41 79 505 83 02». ◄◄◄

    Dieselbe Schreibweise wie auf der Website und unter jeder Mail (``services/phone``).
    Eine Landesnummer ohne Vorwahl («079 …») bekommt die Vorwahl aus dem Land der ersten
    Anschrift (ohne Anschrift die Schweiz, wie überall: ``address.iso2``); in einem Land
    ohne feste Gruppierung bleibt sie, wie getippt – eine geratene Gruppe wäre schlechter
    als keine."""
    from . import phone
    raw = " ".join(raw.split())
    country = user.addresses[0].country if user.addresses else None
    return phone.display(raw, phone.e164(raw, country)) or raw


def email_problem(db: Session, user: UserProfile, email: Optional[str]) -> Optional[str]:
    """►►► **Darf diese Person ihre Anmelde-E-Mail auf diese Adresse ändern?** ◄◄◄
    ``None`` = ja, sonst der Grund in einem Satz.

    Gefragt **vor** dem Bestätigungslink (``POST /auth/me/email-check``) und noch einmal,
    wenn die bestätigte Adresse mit dem Token ankommt (``core/auth._sync_user_profile``) –
    dieselbe Regel, damit nie Firebase die neue Adresse hat und das Profil die alte."""
    key = normalize_email(email)
    if not is_email(key):
        return f"«{email}» ist keine E-Mail-Adresse."
    if key == normalize_email(user.email):
        return "Das ist bereits Ihre Anmelde-E-Mail."
    other = by_email(db, key)
    if other is not None and other.id != user.id and other.is_active:
        return f"«{key}» gehört bereits zu einem anderen Konto – bitte melden Sie sich bei uns."
    return None


#: ►►► **Die EINE E-Mail-Regel** – derselbe Ausdruck wie im Formular der Website
#: (``website/src/config/inquiry.mjs`` → ``patterns.email``; ``tests/test_contact`` hält
#: beide gleich). Eine Adresse, die der Browser annimmt, nimmt auch der Server an.
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


def is_email(email: Optional[str]) -> bool:
    """Ist das eine E-Mail-Adresse (``EMAIL``, höchstens 160 Zeichen)?"""
    key = normalize_email(email)
    return len(key) <= 160 and EMAIL.match(key) is not None


def normalize_email(email: Optional[str]) -> str:
    """Eine E-Mail-Adresse, wie sie gespeichert und verglichen wird: **klein**, ohne Rand."""
    return (email or "").strip().lower()


def by_email(db: Session, email: Optional[str]) -> Optional[UserProfile]:
    """Die Person zu dieser E-Mail – ohne Rücksicht auf Gross-/Kleinschreibung."""
    key = normalize_email(email)
    if not key:
        return None
    return db.query(UserProfile).filter(func.lower(UserProfile.email) == key).first()


def search(db: Session, q: str = "", *, staff: bool = False,
           limit: int = 20) -> list[UserProfile]:
    """►►► **Welche Person ist gemeint?** – die EINE Personensuche. ◄◄◄

    Nummer, Firma, Vorname, Nachname oder E-Mail (``services/lookup``): wer «Muster»
    tippt, findet die Personen der Muster AG – in jedem Feld, das nach Personen fragt
    (Gegenpartei, Halter, Empfänger). **Ohne Rollenfilter**; ``staff`` engt auf das
    Personal ein (die Empfänger einer internen Nachricht).
    """
    firm = (select(CompanySettings.company_name)
            .where(CompanySettings.object_id == UserProfile.company_object_id)
            .scalar_subquery())
    query = db.query(UserProfile)
    if staff:
        query = query.filter(UserProfile.role.in_(STAFF_ROLES))
    return (
        query
        .filter(UserProfile.object_id.isnot(None),
                UserProfile.is_active.is_(True),
                lookup.matches(q, UserProfile.object_id, firm, UserProfile.first_name,
                               UserProfile.last_name, UserProfile.email))
        .order_by(UserProfile.object_id.desc())
        .limit(limit)
        .all()
    )


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
    fields = data.model_dump(exclude_unset=True)
    first = (fields.pop("first_name", "") or "").strip()
    last = (fields.pop("last_name", "") or "").strip()
    email = normalize_email(fields.pop("email", ""))
    role = fields.pop("role", "user") or "user"
    missing = [label for label, v in (("Vorname", first), ("Nachname", last),
                                      ("E-Mail", email)) if not v]
    if missing:
        raise HTTPException(400, detail=f"Für eine neue Person fehlt: {', '.join(missing)}.")
    if not is_email(email):
        raise HTTPException(400, detail=f"«{email}» ist keine E-Mail-Adresse.")
    if role in STAFF_ROLES and actor.role != "admin":
        raise HTTPException(403, detail="Personal-Rollen vergibt nur ein Admin.")
    taken = by_email(db, email)
    if taken is not None:
        raise HTTPException(409, detail=f"«{email}» gehört bereits {taken.object_id} "
                                        f"{taken.display_name}.")
    probe = UserProfile(first_name=first, last_name=last, email=email, role="user")
    _company_fields(db, fields, actor.id, staff=True)
    assert_employment(db, probe, {"role": role, **fields})
    uid = firebase_uid_for(email, f"{first} {last}")
    if db.query(UserProfile).filter(UserProfile.firebase_uid == uid).first() is not None:
        raise HTTPException(409, detail=f"Das Anmeldekonto zu «{email}» gehört bereits "
                                        f"einer anderen Person.")
    user = ensure(db, email, uid=uid, role=role, first=first, last=last, actor_id=actor.id)
    user.company_object_id = fields.get("company_object_id")
    db.commit()
    db.refresh(user)
    return user


#: ►►► **Die Anmelde-Kennung (``firebase_uid``) hat zwei Formen** – erklärt an dieser Stelle:
#: die **UID aus Firebase** (wer sich angemeldet hat, ``core/auth``, oder vom Personal angelegt
#: wurde – das Konto entsteht sofort, ``firebase_uid_for``) und ``mail:<adresse>``
#: (``contact_uid``) für einen **Kontakt ohne Anmeldekonto** (Mail, Anfrage, Newsletter).
#: Meldet er sich später mit dieser – bestätigten – Adresse an, übernimmt er genau diesen
#: Datensatz (``core/auth._resolve_user``).
def contact_uid(email: str) -> str:
    return f"mail:{normalize_email(email)}"[:128]


def split_name(name: str) -> Optional[tuple[str, str]]:
    """Vor- und Nachname aus einem Namen («Fritsche, Clemens» ist «Nachname, Vorname» – das
    Komma dreht). Sonst: das erste Wort ist der Vorname. ``None`` = kein Name."""
    raw = re.sub(r"\s+", " ", (name or "").replace('"', "")).strip()
    if "," in raw:
        last, _, first = raw.partition(",")
        raw = f"{first.strip()} {last.strip()}".strip()
    parts = raw.split(" ") if raw else []
    return (parts[0][:100], " ".join(parts[1:])[:100]) if parts else None


def ensure(db: Session, email: str, name: str = "", phone: str = "", *,
           uid: Optional[str] = None, role: str = "user", first: Optional[str] = None,
           last: Optional[str] = None, photo_url: Optional[str] = None,
           actor_id: Optional[int] = None) -> UserProfile:
    """►►► **Die Person zu dieser E-Mail – angelegt, wenn es sie nicht gibt.** ◄◄◄ Die EINE
    Stelle, an der eine Person entsteht (Anmeldung, Personal, Mail, Anfrage, Newsletter).

    Eine gefundene Person bleibt, wie sie ist – auch ihr Telefon: was jemand in ein
    öffentliches Formular tippt, schreibt nie in einen bestehenden Datensatz. Ohne ``uid``
    ist es ein Kontakt (``contact_uid``); ohne Namen heisst ein Kontakt wie der Anfang
    seiner Adresse. Committet nicht."""
    from .objects import next_object_id
    key = normalize_email(email)
    found = by_email(db, key) if key else None
    if found is not None and found.object_id:
        return found
    if first is None and last is None:
        fallback = (key.split("@")[0], "") if uid is None else (None, None)
        first, last = split_name(name) or fallback
    user = UserProfile(firebase_uid=uid or contact_uid(key), email=key, role=role,
                       first_name=(first or "")[:100] or None,
                       last_name=(last or "")[:100] or None,
                       phone=(phone or "")[:50] or None, photo_url=photo_url,
                       object_id=next_object_id(db, "user"))
    db.add(user)
    db.flush()
    log_audit(db, "user_profiles", None, f"Person «{user.display_name}» angelegt", actor_id,
              object_id=user.object_id)
    return user
