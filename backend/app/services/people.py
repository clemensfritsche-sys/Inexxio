"""Personen-Anzeige – **EINE** Stelle für «wie heisst diese Person?».

Die Regel selbst steht am Modell (``UserProfile.display_name``: «Vorname Nachname»
→ Firma → E-Mail, Notiz #291). Was fehlte, war die eine Stelle, die sie *anwendet*: derselbe
Zweizeiler lag sechsmal im Code (``sales._user_name``, ``resource._user_name``,
``document._user_name``, ``orders._supplier_name``, ``article_process._supplier_name``,
``document_files._user_name``, dazu ``locations._user_label``).

Das war nicht nur Wiederholung, sondern eine **Falle**: die Varianten schlugen in
ZWEI verschiedenen Schlüsseln nach – teils über die 9-stellige ``object_id``, teils
über die interne ``id``. Beides sind Ganzzahlen; wer die falsche Variante erwischt,
bekommt lautlos den falschen (oder keinen) Namen. Darum tragen die Funktionen hier
den Schlüssel **im Namen**.
"""

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import UserProfile
from . import sites
from .admin import log_audit

#: Wer im Haus arbeitet – und damit für **eine** unserer Gesellschaften.
STAFF_ROLES = ("admin", "employee")


def name(u: Optional[UserProfile]) -> Optional[str]:
    """Anzeigename einer bereits geladenen Person (``None`` bleibt ``None``)."""
    return u.display_name if u else None


def billing_name(u: Optional[UserProfile]) -> list[str]:
    """►►► **Wie diese Partei auf einem BELEG steht** – Firma zuerst. ◄◄◄

    ``display_name`` ist bewusst **person-first** («Vorname Nachname → Firma → E-Mail»,
    Notiz #291), und im ERP ist das richtig: man arbeitet mit Menschen.

    Auf einer **Rechnung** ist es falsch. Schuldner ist die *Muster AG*, nicht der
    Einkäufer, der dort arbeitet – und wer den Beleg bezahlt, braucht die Rechtsperson,
    die er in seiner Buchhaltung führt.

    Zurück kommen **Zeilen**, nicht ein Name: die Firma, und darunter die Person als
    «z. H.», wenn beide da sind. Ohne Firma bleibt die Person – das ist der B2C-Fall und
    korrekt.

    *Zwei Formen einer Regel sind in Ordnung; zwei Regeln nicht – darum steht sie hier
    neben ``display_name`` und nicht im Geldvorgang.*
    """
    if u is None:
        return []
    person = " ".join(p for p in (u.first_name, u.last_name) if p).strip()
    company = (u.company_name or "").strip()
    if company and person:
        return [company, f"z. H. {person}"]
    return [company or person or u.email]


def name_by_id(db: Session, user_id: Optional[int]) -> Optional[str]:
    """Anzeigename über die **interne** Primärschlüssel-Id (Fremdschlüssel-Spalten
    wie ``supplier_id``, ``customer_id``, ``inspector_id``, ``uploaded_by``)."""
    if not user_id:
        return None
    return name(db.query(UserProfile).filter(UserProfile.id == user_id).first())


def assert_employment(db: Session, user: UserProfile, fields: dict[str, Any]) -> None:
    """►►► **Wer Mitarbeiter WIRD, gehört zu einer Gesellschaft** (Testnotiz #905). ◄◄◄

    Ohne diese Zuordnung kann ein Beleg nicht sagen, wer ihn stellt – er nähme still den
    Betreiber, also die Gesellschaft, die die Website vertritt, auch wenn eine
    Schwestergesellschaft fakturiert.

    ►►► **Geprüft wird der ÜBERGANG, nicht der Bestand.** ◄◄◄ Das ist die eine
    Feinheit, und sie ist bewusst so: eine Prüfung auf den *Zustand* machte jede
    bestehende Personalzeile ohne Gesellschaft unbearbeitbar – man käme nicht einmal mehr
    dazu, die Gesellschaft nachzutragen, ohne sie im selben Zug mitzuschicken. Die
    Schreibstelle weist darum den **neuen** schlechten Zustand ab; den **bestehenden**
    meldet der Geldvorgang als ``DataGap`` – dieselbe Arbeitsteilung wie überall:
    *streng schreiben, tolerant lesen, Fehlendes benennen.*

    Und die Gesellschaft muss es **geben**: eine Objektnummer, die auf nichts zeigt, ist
    schlimmer als keine – sie sieht aus wie eine Zuordnung.
    """
    company = fields["company_object_id"] if "company_object_id" in fields \
        else user.company_object_id
    if company is not None and sites.by_object_id(db, company) is None:
        raise HTTPException(
            400, detail=f"«{company}» ist keine unserer Gesellschaften.")
    role = fields.get("role", user.role)
    if role in STAFF_ROLES and role != user.role and company is None:
        raise HTTPException(
            400,
            detail=(f"«{user.display_name}» braucht eine Gesellschaft, um als "
                    f"{'Administrator' if role == 'admin' else 'Mitarbeiter'} zu "
                    f"arbeiten – auf einem Beleg steht, wer ihn stellt."),
        )


def apply_profile_update(db: Session, user: UserProfile, data, actor_id: int) -> UserProfile:
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
    Datensatz."""
    fields = data.model_dump(exclude_unset=True)
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
