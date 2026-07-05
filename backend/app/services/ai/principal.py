"""Delegation (ADR 004): «KI handelt im Auftrag von Nutzer X».

Der ``AiPrincipal`` bündelt die zwei Achsen jeder KI-Aktion:

* **Attribution** (*wer hat gehandelt*): immer die KI-Identität (``actor``) –
  Audit-Log/Event-Strom zeigen «User KI», mit ``on_behalf_of`` als Kontext.
* **Autorisierung** (*was darf sie dabei sehen/tun*): immer der **effektive Nutzer**
  (der delegierende Mensch). Alle Tools scopen ihre Daten über die BESTEHENDEN
  Authz-Helfer (``visible_orders``, ``can_view``, Rollen-Checks) mit
  ``principal.effective`` – ein Kunde bekommt über die KI exakt das, was er auch im
  Frontend sähe. Ein Prompt kann daran nichts ändern, weil die Fehlmenge nie ins
  Modell gelangt."""

from dataclasses import dataclass

from ...models import UserProfile

STAFF_ROLES = ("admin", "employee")


@dataclass(frozen=True)
class AiPrincipal:
    actor: UserProfile                 # die KI-Identität (Attribution)
    on_behalf_of: UserProfile | None   # der delegierende Mensch (None = autonom)

    @property
    def effective(self) -> UserProfile:
        """Der Nutzer, dessen Rechte gelten. Autonom (ohne Delegation) gilt die
        KI-Identität selbst – deren Rolle ``'ai'`` ist in keinem Staff-/Kunden-Gate
        enthalten, autonome Läufe sehen also nur explizit freigegebene Tools."""
        return self.on_behalf_of or self.actor

    @property
    def effective_role(self) -> str:
        return self.effective.role

    @property
    def is_staff(self) -> bool:
        return self.effective_role in STAFF_ROLES
