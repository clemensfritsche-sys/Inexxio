"""**«Welchen Datensatz meinst du?» – Nummer ODER Name, an jeder Suche gleich** (#738).

Die Bedingung steht einmal (``services/lookup.matches``); geprüft wird, dass jede Suche des
Feeds und des Auftragsentwurfs sie wirklich anwendet: ein **Teil** der Objektnummer findet,
und ebenso ein Teil des Namens, gross oder klein. Bug-Form: eine Stelle sucht nur den Namen –
wer «100000743» in die Artikel-Auswahl tippte, fand nichts, obwohl die Nummer darunter stand.
(Halter sucht ``test_move_module.test_holders_are_searchable_by_number_and_by_name``.)
"""

import pytest
from fastapi.testclient import TestClient

from tests.scenarios import World


@pytest.fixture
def client(db, monkeypatch):
    from app.core.auth import get_current_user
    from app.core.database import get_db
    from app.main import app
    from tests.factories import new_person

    staff = new_person(db, "employee")
    monkeypatch.setattr(db, "commit", db.flush)
    app.dependency_overrides[get_current_user] = lambda: staff
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


SEARCHES = {
    "/api/v1/erp/articles": "article",
    "/api/v1/erp/instances": "instance",
    "/api/v1/erp/orders/article-options": "article",
}


@pytest.mark.parametrize("path", SEARCHES)
def test_every_search_finds_by_part_of_the_number_and_by_name(db, client, path):
    w = World(db)
    article = w.article()
    article.name = "Kugellager Spezial"
    order = w.produce(article, 1)
    db.flush()
    wanted = article.object_id if SEARCHES[path] == "article" else w.instances(order)[0]

    def found(q: str) -> set[int]:
        r = client.get(path, params={"search": q})
        assert r.status_code == 200, r.text
        return {row["object_id"] for row in r.json()}

    assert wanted in found(str(wanted)[3:8]), f"{path}: ein Teil der Nummer findet nichts"
    assert wanted in found("lager spez"), f"{path}: ein Teil des Namens findet nichts"
    assert wanted not in found("gibt-es-nicht"), f"{path}: die Suche filtert nicht"
