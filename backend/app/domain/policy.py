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
    # Der Zugang einer Person: Passkeys, Verbindungen mit Claude (``routers/access``)
    "person.access": Rule(SELF, "Den Zugang einer Person sieht und ändert nur sie selbst oder der Admin."),
    # Privates: Gespräche, Aufnahmen, Handgriffe aus dem eigenen Claude, private Dokumentteile
    "private": Rule(SELF, "Das sieht nur die Person selbst und der Admin."),
    # Überblick, den nur der Admin braucht
    "overview": Rule(ADMIN, "Diesen Überblick hat nur der Admin."),
}


@dataclass(frozen=True)
class SelfOnly:
    """Was nur die Person selbst kann – und der Satz, warum (kein Recht, eine Tatsache)."""
    why: str


_REC = "/api/v1/erp/records/{object_id}"

#: ►►► **ERP ist Master – was eine Person ausserhalb des ERP an sich selbst sieht oder tut.** ◄◄◄
#: Jede Route der Selbstbedienung (``/api/v1/auth/…``, angemeldet) → ihr Gegenstück am
#: ERP-Datensatz («METHODE /pfad»; mehrere als Tupel) – oder ``SelfOnly`` mit dem Grund. Der Wächter
#: ``tests/test_erp_master.py`` verlangt für jede solche Route einen Eintrag und dass jedes
#: Gegenstück eine echte Route ist. Die ganze Prüfung: ``docs/history/2026-11-11-erp-master-pruefung.md``.
SELF_SERVICE: dict[str, Any] = {
    "GET /api/v1/auth/me": f"GET {_REC}",
    "PATCH /api/v1/auth/me": f"PATCH {_REC}",
    "POST /api/v1/auth/me/email-check": SelfOnly(
        "Die Anmelde-E-Mail wechselt erst mit dem Klick auf den Link an die neue Adresse – nur die "
        "Person kann zeigen, dass sie ihr gehört. Das ERP zeigt die Adresse am Datensatz."),
    "POST /api/v1/auth/me/addresses": f"POST {_REC}/addresses",
    "PATCH /api/v1/auth/me/addresses/{address_id}": f"PATCH {_REC}/addresses/{{address_id}}",
    "DELETE /api/v1/auth/me/addresses/{address_id}": f"DELETE {_REC}/addresses/{{address_id}}",
    "GET /api/v1/auth/me/newsletter": "GET /api/v1/erp/newsletter/{object_id}",
    # Anmelden ist eine Einwilligung: das ERP bittet darum (invite) oder meldet ab.
    "PUT /api/v1/auth/me/newsletter": ("POST /api/v1/erp/newsletter/{object_id}/invite",
                                       "POST /api/v1/erp/newsletter/{object_id}/unsubscribe"),
    "GET /api/v1/auth/passkeys": f"GET {_REC}/passkeys",
    "DELETE /api/v1/auth/passkeys/{passkey_id}": f"DELETE {_REC}/passkeys/{{passkey_id}}",
    "POST /api/v1/auth/passkeys/register/options": SelfOnly(
        "Einen Passkey richtet die Person auf ihrem eigenen Gerät ein – der Schlüssel verlässt es nie."),
    "POST /api/v1/auth/passkeys/register/verify": SelfOnly(
        "Einen Passkey richtet die Person auf ihrem eigenen Gerät ein – der Schlüssel verlässt es nie."),
    "GET /api/v1/auth/me/mcp": f"GET {_REC}/mcp",
    "POST /api/v1/auth/me/mcp/{grant_id}/revoke": f"POST {_REC}/mcp/{{grant_id}}/revoke",
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
