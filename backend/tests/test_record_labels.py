"""«Was ist diese Nummer, und wie heisst sie?» – der Typ aus der Registry, EINE Typ-Tabelle."""

from sqlalchemy import event

from app.services import objects, record_labels


def _statements(db, fn):
    seen = []
    engine = db.get_bind()
    listener = lambda *a: seen.append(a[2])     # noqa: E731
    event.listen(engine, "before_cursor_execute", listener)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    return result, seen


def test_a_name_asks_the_registry_then_only_its_own_table(db, make_person):
    """Bug-Form: je Aufruf alle sechs Tabellen befragen, auch wenn nur eine Person gesucht ist."""
    person = make_person("user")
    found, sql = _statements(db, lambda: record_labels.labels(db, [person.object_id]))
    assert found[person.object_id].type == "user"
    assert found[person.object_id].label.startswith("Benutzer · ")
    assert len(sql) == 2, sql


def test_every_type_has_a_name_and_a_word():
    assert set(record_labels._NAMES) == set(objects.TYPES)
    assert all(kind.word for kind in objects.TYPES.values())
