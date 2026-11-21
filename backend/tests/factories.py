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
    """Eine Person mit Rolle (``policy.ROLES``), optional einer Firma zugeordnet."""
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


def messages_of(db, object_id: int) -> list:
    """Der Verlauf eines Datensatzes als Nachrichten, älteste zuerst (``communication.page``)."""
    from app.services import communication as comm
    found, sizes = comm.page(db, comm.scope(db, object_id), None, comm.PAGE)
    out = comm.load(db, [i for i, _ in found])
    for m in out:
        m.recipients = sizes.get(m.id, 0)
    return out


#: Das Postfach der Tests – eine (gedachte) eigene Gesellschaft.
TEST_CHANNEL = "c999999990"


def post_office(db, monkeypatch, channel: str = TEST_CHANNEL):
    """►►► **Das Test-Postfach**: verbunden, und was hinaus soll, ist sofort draussen. ◄◄◄
    Eine Mail kennt nur zwei Wege – sie geht hinaus, oder sie wartet auf ihr Postfach; hier
    geht sie hinaus, ohne Gmail (``mailbox.send_after`` vermerkt sie als gesendet)."""
    import uuid
    from app.models import Mailbox, Message
    from app.services import mailbox
    box = mailbox.active(db, channel)
    if box is None:
        box = Mailbox(channel=channel, address=f"info+{channel}@example.ch",
                      owner_object_id=1, token="x")
        db.add(box)
        db.flush()

    def deliver(session) -> None:
        for m in session.query(Message).filter(Message.outgoing.is_(True)).all():
            m.outgoing, m.gmail_id = False, f"g-{uuid.uuid4().hex[:12]}"
        session.flush()
    monkeypatch.setattr(mailbox, "send_after", deliver)
    return box


def quiet_outbox(db) -> None:
    """Was andere Tests zum Versand gaben, gilt hier als draussen – ein Test, der zählt, was
    hinausgeht, sieht nur seine eigenen Mails (zurückgerollt mit dem Test)."""
    from app.models import Message
    db.query(Message).filter(Message.outgoing.is_(True)).update(
        {Message.outgoing: False}, synchronize_session=False)
    db.flush()
