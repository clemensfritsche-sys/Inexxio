"""**Personen und Firmen für Tests – an EINER Stelle**, mit Nummern aus dem echten Kreis.

Die Nummer kommt immer aus ``objects.next_object_id`` (Sequence + Registry), nie aus
``random``: eine erfundene Nummer steht in keiner Registry, und zwei Läufe können sie
doppelt ziehen. Als Fixture gebunden: ``make_person``, ``make_firm``, ``own_company``
(``tests/conftest.py``). Artikel und Aufträge baut ``tests.scenarios.World``.
"""

from typing import Any, Optional


def new_person(db, role: str = "user", *, company: Optional[int] = None,
               email: Optional[str] = None, uid: Optional[str] = None,
               first_name: str = "Lea", last_name: Optional[str] = None, **extra: Any):
    """Eine Person mit Rolle (``people.ROLES``), optional einer Firma zugeordnet."""
    from app.models import UserProfile
    from app.services.objects import next_object_id

    oid = next_object_id(db, "user")
    person = UserProfile(firebase_uid=uid or f"uid-{oid}", email=email or f"p{oid}@x.ch",
                         role=role, object_id=oid, first_name=first_name,
                         last_name=last_name if last_name is not None else f"M{oid}",
                         company_object_id=company, **extra)
    db.add(person)
    db.flush()
    return person


def new_firm(db, name: Optional[str] = None, form: str = "AG", *, own: bool = False,
             uid: Optional[str] = None, **extra: Any):
    """Eine Firma – fremd (Identität) oder eigene Gesellschaft (``own``); weitere Spalten
    (``country`` …) als Schlüsselwort."""
    from app.models import CompanySettings
    from app.services.objects import next_object_id

    oid = next_object_id(db, "organization")
    firm = CompanySettings(object_id=oid, company_name=name or f"Firma {oid}",
                           legal_form=form, is_own=own, uid_number=uid,
                           **{"email": "", **extra})
    db.add(firm)
    db.flush()
    return firm
