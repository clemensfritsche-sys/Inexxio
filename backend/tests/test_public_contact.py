"""Kontaktdaten der Website aus dem ERP (Testnotiz #1094) – DB-frei.

Geprüft wird, was ohne Datenbank prüfbar ist: die IP→Land-Tabelle (Bauen und Nachschlagen),
die Wahl-Adresse und dass der Endpunkt das Unternehmen über die EINE Regel
(``sites.company_for_country``) findet statt selbst zu suchen.
"""

import csv
import gzip
import importlib
import inspect
import io
from pathlib import Path

from app.routers import website
from app.services import geoip

ROOT = Path(__file__).resolve().parents[1]


def _source_csv(rows) -> bytes:
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return gzip.compress(buf.getvalue().encode())


def test_the_table_is_built_merged_and_looked_up(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("build_geoip", ROOT / "scripts" / "build_geoip.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    out = tmp_path / "ip-country.csv.gz"
    monkeypatch.setattr(build, "OUT", out)
    raw = _source_csv([
        ["2.16.0.0", "2.16.0.255", "CH"],
        ["2.16.1.0", "2.16.1.255", "CH"],      # Nachbar, gleiches Land → zusammengezogen
        ["5.1.0.0", "5.1.255.255", "DE"],
        ["2001:db8::", "2001:db8::ffff", "AT"],
        ["9.9.9.0", "9.9.9.255", "ZZ"],        # unbekannt → fällt weg
    ])
    assert build.build(raw, "test") == 3
    monkeypatch.setattr(geoip, "TABLE", out)
    geoip._table.cache_clear()
    try:
        assert geoip.country_of("2.16.1.7") == "CH"
        assert geoip.country_of("5.1.2.3") == "DE"
        assert geoip.country_of("2.17.0.1") is None
        assert geoip.country_of("192.168.1.1") is None        # privat: nie ein Land
        assert geoip.country_of("kein ip") is None
    finally:
        geoip._table.cache_clear()


def test_without_a_table_there_is_no_country(tmp_path, monkeypatch):
    monkeypatch.setattr(geoip, "TABLE", tmp_path / "fehlt.csv.gz")
    geoip._table.cache_clear()
    try:
        assert geoip.country_of("5.1.2.3") is None
    finally:
        geoip._table.cache_clear()


def test_the_visitor_is_the_first_forwarded_address():
    assert geoip.client_ip({"x-forwarded-for": "5.1.2.3, 10.0.0.1"}, "10.0.0.9") == "5.1.2.3"
    assert geoip.client_ip({}, "10.0.0.9") == "10.0.0.9"


def test_the_dial_address_follows_the_company_country():
    assert website._e164("052 378 22 47", "Schweiz") == "+41523782247"
    assert website._e164("+49 30 123", "Schweiz") == "+4930123"
    assert website._e164("0041 52 378 22 47", None) == "+41523782247"
    assert website._e164("", "CH") is None


def test_the_company_is_found_by_the_one_rule():
    src = inspect.getsource(website.public_contact)
    assert "sites.company_for_country(" in src
    assert "CompanySettings" not in src
