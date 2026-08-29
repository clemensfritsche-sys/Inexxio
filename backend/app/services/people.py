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

from typing import Optional

from sqlalchemy.orm import Session

from ..models import UserProfile
from .admin import log_audit


def name(u: Optional[UserProfile]) -> Optional[str]:
    """Anzeigename einer bereits geladenen Person (``None`` bleibt ``None``)."""
    return u.display_name if u else None


def name_by_id(db: Session, user_id: Optional[int]) -> Optional[str]:
    """Anzeigename über die **interne** Primärschlüssel-Id (Fremdschlüssel-Spalten
    wie ``supplier_id``, ``customer_id``, ``inspector_id``, ``uploaded_by``)."""
    if not user_id:
        return None
    return name(db.query(UserProfile).filter(UserProfile.id == user_id).first())


def apply_profile_update(db: Session, user: UserProfile, data, actor_id: int) -> UserProfile:
    """Profil-Felder schreiben – **EIN** Pfad für beide Oberflächen.

    Denselben Datensatz beschreiben zwei Wege: der ERP-Benutzer-Datensatz (Personal)
    und die Selbstbedienung im Konto (die Person auf ihre eigenen Daten). Das ist so
    gewollt – beides ist derselbe Datensatz, keine zweite Wahrheit. Nur **protokolliert**
    hat es bisher allein der ERP-Weg: eine im Konto geänderte IBAN hinterliess keine
    Spur im Audit-Log, eine im ERP geänderte schon.

    Diese Stelle vereint beides: gleiche Zuweisung, gleiche Protokollierung, egal von
    welcher Oberfläche. Committet NICHT (der Aufrufer entscheidet)."""
    for key, value in data.model_dump(exclude_unset=True).items():
        old_val = getattr(user, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "user_profiles", key, new_str, actor_id,
                      object_id=user.object_id, old_value=old_str)
        setattr(user, key, value)
    return user
