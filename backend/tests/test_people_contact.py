"""Telefon und Anmelde-E-Mail einer Person – die Regeln aus ``services/people``."""

from types import SimpleNamespace

from app.services import people


def _person(country=None, email="alt@beispiel.ch", pid=1):
    addresses = [SimpleNamespace(country=country)] if country else []
    return SimpleNamespace(id=pid, email=email, addresses=addresses, is_active=True)


def test_a_phone_is_written_the_way_one_reads_it():
    assert people.tidy_phone(_person("CH"), "079 505 83 02") == "+41 79 505 83 02"
    assert people.tidy_phone(_person(), "+41795058302") == "+41 79 505 83 02"
    assert people.tidy_phone(_person(), "0041 79 505 83 02") == "+41 79 505 83 02"
    # Ohne Anschrift gilt die Schweiz; ohne feste Gruppierung bleibt die Nummer, wie getippt.
    assert people.tidy_phone(_person(), "079  505 83 02") == "+41 79 505 83 02"
    assert people.tidy_phone(_person("DE"), "0171  1234567") == "0171 1234567"


def test_the_login_email_changes_only_to_a_free_address(monkeypatch):
    me = _person()
    other = _person(email="belegt@beispiel.ch", pid=2)
    monkeypatch.setattr(people, "by_email", lambda db, e: other if e == other.email else None)
    assert people.email_problem(None, me, "Neu@Beispiel.ch ") is None
    assert "keine E-Mail-Adresse" in people.email_problem(None, me, "neu-beispiel")
    assert "bereits Ihre" in people.email_problem(None, me, "ALT@beispiel.ch")
    assert "«belegt@beispiel.ch»" in people.email_problem(None, me, "belegt@beispiel.ch")
    other.is_active = False
    assert people.email_problem(None, me, "belegt@beispiel.ch") is None
