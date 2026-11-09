"""►►► **Wer darf was – EINE Stelle** (Änderungsakte U5). ◄◄◄

Jede Handlung, die nicht jedes Personal darf, steht hier **einmal**: wer sie darf, und der Satz,
der sagt, warum nicht. Dienste fragen nur noch hier – ``may`` (Auskunft, z. B. für einen Knopf)
oder ``require`` (Tor: wirft ``Forbidden`` mit dem Satz). Zwei Formen einer Regel, nie zwei
Regeln. Ein Wächter (``tests/test_policy.py``) verbietet Rollenvergleiche ausserhalb.

**Drei Arten von Regeln**

* ``STAFF`` – jedes Personal (Admin, Mitarbeitende).
* ``ADMIN`` – nur der Admin.
* ``SELF`` – die Person selbst (``owner`` = ihre Objektnummer) und der Admin.

Die Rolle ist der Zugang (``ROLES``); ins ERP darf ``STAFF_ROLES``. Wer handelt, ist eine Person
(``role``, ``object_id``) – oder niemand (``None``: das System, z. B. der Takt). Das System ist
**innen** (``inside``), aber es hat keine Rechte einer Person.
"""

from dataclasses import dataclass
from typing import Any, Optional

from .errors import Forbidden

ADMIN_ROLE, EMPLOYEE_ROLE, USER_ROLE = "admin", "employee", "user"
ROLES = (ADMIN_ROLE, EMPLOYEE_ROLE, USER_ROLE)
#: Wer ins ERP darf – im Frontend gespiegelt (``lib/record-status.isStaff``).
STAFF_ROLES = (ADMIN_ROLE, EMPLOYEE_ROLE)

STAFF, ADMIN, SELF = "staff", "admin", "self"


@dataclass(frozen=True)
class Rule:
    who: str
    why: str


#: ►►► **Die Regeltabelle.** Handlung → wer darf, und der Satz, wenn nicht. ◄◄◄
RULES: dict[str, Rule] = {
    # Die Türen der Routen (``core/auth.require_employee`` · ``require_admin``)
    "erp": Rule(STAFF, "Dafür fehlt Ihnen die Berechtigung."),
    "admin": Rule(ADMIN, "Das darf nur der Admin."),
    # Personen und Firmen
    "person.edit": Rule(STAFF, "Personen ändern nur Mitarbeitende."),
    "person.staff": Rule(ADMIN, "Rollen und die Angaben von Mitarbeitenden ändert nur der Admin."),
    "company.own": Rule(ADMIN, "Unsere eigenen Gesellschaften pflegt nur der Admin."),
    "company.legal": Rule(ADMIN, "Rechtstexte setzt nur der Admin."),
    "mailbox.connect": Rule(ADMIN, "Ein Postfach verbindet oder trennt nur der Admin."),
    # Zeiterfassung
    "time.see": Rule(SELF, "Die Zeiterfassung führt nur die Person selbst oder der Admin."),
    "time.contract": Rule(ADMIN, "Verträge pflegt nur der Admin."),
    "time.booking": Rule(ADMIN, "Buchungen macht nur der Admin."),
    "time.company": Rule(ADMIN, "Feiertage und Regeln der Gesellschaft pflegt nur der Admin."),
    # Privates: Gespräche, Aufnahmen, Handgriffe aus dem eigenen Claude, private Dokumentteile
    "private": Rule(SELF, "Das sieht nur die Person selbst und der Admin."),
    # Überblick, den nur der Admin braucht
    "overview": Rule(ADMIN, "Diesen Überblick hat nur der Admin."),
}


def is_staff(who: Any) -> bool:
    """Gehört ``who`` zum Personal?"""
    return who is not None and getattr(who, "role", None) in STAFF_ROLES


def is_admin(who: Any) -> bool:
    return who is not None and getattr(who, "role", None) == ADMIN_ROLE


def inside(who: Any) -> bool:
    """Innen: das System (``None``) oder Personal – im Gegensatz zu einer Partei von aussen."""
    return who is None or is_staff(who)


def may(who: Any, action: str, owner: Optional[int] = None) -> bool:
    """►► **Darf ``who`` das?** – die Auskunft. ``owner`` = wessen Sache (bei ``SELF``). ◄◄"""
    rule = RULES[action]
    if not is_staff(who):
        return False
    if rule.who == STAFF or is_admin(who):
        return True
    if rule.who == SELF:
        return owner is not None and getattr(who, "object_id", None) == owner
    return False


def problem(who: Any, action: str, owner: Optional[int] = None) -> Optional[str]:
    """Der Satz, warum nicht – oder ``None``."""
    return None if may(who, action, owner) else RULES[action].why


def require(who: Any, action: str, owner: Optional[int] = None) -> None:
    """►► **Das Tor** – wirft ``Forbidden`` mit dem Satz der Regel. ◄◄"""
    why = problem(who, action, owner)
    if why is not None:
        raise Forbidden(why)
