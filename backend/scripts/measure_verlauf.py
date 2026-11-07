"""Messung: Verlauf und «zu tun» bei 50'000 Nachrichten (Phase 2, Schritt 2.3).

Legt in EINER Transaktion 500 Kunden, 10 Mitarbeitende und 50'000 Nachrichten an (je
Anfrage von aussen eine Antwort von uns, jede zehnte bleibt offen), misst und rollt alles
zurück – die Datenbank bleibt, wie sie war. Ziel: eine Seite des Verlaufs < 200 ms, «zu tun»
< 300 ms.

    cd backend && DATABASE_URL=… python -m scripts.measure_verlauf [Anzahl]
"""

import statistics
import sys
import time

from sqlalchemy import text

from app.core.actor import system_session
from app.services import communication, history, objects, todo
from app.models import UserProfile

SEED = """
INSERT INTO messages (sender_object_id, channel, subject, topic, body, at, outgoing,
                      read_marked, newsletter, is_active, created_at, updated_at)
SELECT CASE WHEN g % 2 = 0 THEN c.oid ELSE s.oid END,
       :box,
       CASE WHEN g % 2 = 0 THEN 'Anliegen ' || (g / 2) % 2000 ELSE 'Re: Anliegen ' || (g / 2) % 2000 END,
       'anliegen ' || (g / 2) % 2000,
       'Text ' || g,
       now() - make_interval(mins => (:n - g) * 3),
       false, false, false, true, now(), now()
  FROM generate_series(0, :n - 1) g
  JOIN LATERAL (SELECT oid FROM tmp_customers WHERE k = (g / 2) % 500) c ON true
  JOIN LATERAL (SELECT oid FROM tmp_staff WHERE k = (g / 2) % 10) s ON true
 WHERE NOT (g % 2 = 1 AND (g / 2) % 10 = 0)          -- jede zehnte Anfrage bleibt offen
"""

PARTIES = """
INSERT INTO message_parties (message_id, object_id, role)
SELECT m.id, c.oid, 'to' FROM messages m
  JOIN tmp_customers c ON m.subject LIKE 'Re: %' AND c.k = (split_part(m.subject, ' ', 3)::int) % 500
 WHERE m.id > :first
"""


def _time(fn, runs: int = 5) -> float:
    took = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        took.append((time.perf_counter() - t) * 1000)
    return statistics.median(took)


#: 52'632 Zeilen der Reihe – jede zehnte Antwort fehlt: genau 50'000 Nachrichten.
ROWS = 52_632


def main(n: int = ROWS) -> None:
    db = system_session("test")
    try:
        people = []
        for k in range(510):
            oid = objects.next_object_id(db, "user")
            people.append(UserProfile(firebase_uid=f"m-{oid}", email=f"m{oid}@x.ch",
                                      role="employee" if k < 10 else "user", object_id=oid,
                                      first_name="M", last_name=str(oid)))
        db.add_all(people)
        db.flush()
        db.execute(text("CREATE TEMP TABLE tmp_staff (k int, oid bigint) ON COMMIT DROP"))
        db.execute(text("CREATE TEMP TABLE tmp_customers (k int, oid bigint) ON COMMIT DROP"))
        db.execute(text("INSERT INTO tmp_staff VALUES " + ",".join(
            f"({k},{p.object_id})" for k, p in enumerate(people[:10]))))
        db.execute(text("INSERT INTO tmp_customers VALUES " + ",".join(
            f"({k},{p.object_id})" for k, p in enumerate(people[10:]))))
        first = db.execute(text("SELECT coalesce(max(id), 0) FROM messages")).scalar()
        t = time.perf_counter()
        db.execute(text(SEED), {"n": n, "box": "c999999990"})
        db.execute(text(PARTIES), {"first": first})
        db.execute(text("ANALYZE messages; ANALYZE message_parties; ANALYZE log"))
        total = db.execute(text("SELECT count(*) FROM messages")).scalar()
        print(f"angelegt in {time.perf_counter() - t:.1f} s – Nachrichten gesamt: {total}")
        staff, customer = people[0], people[10]
        admin = staff
        admin.role = "admin"
        db.flush()
        print(f"Seite Verlauf Kunde (100 Nachrichten):    "
              f"{_time(lambda: history.page(db, customer.object_id, staff)):6.1f} ms")
        print(f"Seite Verlauf Mitarbeiter (~2500):         "
              f"{_time(lambda: history.page(db, staff.object_id, staff)):6.1f} ms")
        p = history.page(db, staff.object_id, staff)
        print(f"zweite Seite (Cursor):                     "
              f"{_time(lambda: history.page(db, staff.object_id, staff, before=p.before)):6.1f} ms")
        counts = communication.open_counts(db)
        print(f"offen gezählt: {sum(c.open for c in counts)} Nachrichten bei {len(counts)} Personen")
        print(f"open_counts:                               "
              f"{_time(lambda: communication.open_counts(db)):6.1f} ms")
        print(f"«zu tun» (todo, Admin):                    "
              f"{_time(lambda: todo.todo(db, admin)):6.1f} ms")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else ROWS)
