"""Gebiets-/Multi-Gesellschaften-Aufteilung – DB-freie Wächter (ADR 006).

Die DB-abhängige Auflösung (``sites.company_for_country``/``set_territory``/``territory_map``)
wird gegen echtes Postgres verifiziert (nicht in CI – dort kein Postgres); hier stehen die
reinen Invarianten der Stammdaten + Quelltext-Garantien."""

import inspect


def test_regions_are_a_fixed_nonempty_set():
    from app.services import geography

    assert len(geography.REGIONS) >= 5
    assert len(geography.REGION_CODES) == len(set(geography.REGION_CODES))   # eindeutig
    for r in geography.REGIONS:
        assert {"code", "label", "pos"} <= set(r)
        assert isinstance(r["pos"], list) and len(r["pos"]) == 2


def test_every_country_maps_to_a_valid_region_exactly_once():
    """Totalität-Basis: jedes gelistete Land liegt in genau EINER gültigen Region – kein Land
    in zwei Regionen, keine verwaiste Region-Referenz."""
    from app.services import geography

    seen: dict[str, str] = {}
    for region, countries in geography._BY_REGION.items():
        assert region in geography.REGION_CODES, f"{region} ist keine gültige Region"
        for cc in countries:
            assert len(cc) == 2 and cc.isupper(), f"{cc} ist kein ISO-2-Code"
            assert cc not in seen, f"{cc} ist doppelt ({seen.get(cc)} + {region})"
            seen[cc] = region


def test_region_of_country_is_tolerant():
    from app.services import geography

    assert geography.region_of_country("US") == "NAM"
    assert geography.region_of_country("us") == "NAM"      # Grossschreibung egal
    assert geography.region_of_country("DE") == "EUR"
    assert geography.region_of_country("CH") == "EUR"
    assert geography.region_of_country("JP") == "ASIA"
    assert geography.region_of_country("BR") == "LATAM"
    # Unbekannt/leer → None (der Aufrufer macht daraus den Betreiber-Fallback).
    assert geography.region_of_country("XX") is None
    assert geography.region_of_country("") is None
    assert geography.region_of_country(None) is None
    # Kernmärkte abgedeckt.
    for cc in ("US", "CA", "MX", "BR", "AR", "DE", "FR", "GB", "CH", "IT", "ES", "CN", "JP",
               "IN", "AU", "AE", "ZA"):
        assert geography.region_of_country(cc) in geography.REGION_CODES


def test_company_for_country_is_read_only_with_operator_fallback():
    """Quelltext-Garantie: die Auflösung committet nicht (Pflicht in fremden Transaktionen)
    und fällt auf den Betreiber (``find_operator``), nie auf eine willkürliche ``.first()``."""
    from app.services import sites

    src = inspect.getsource(sites.company_for_country)
    assert "find_operator" in src                 # Betreiber-Fallback
    assert "region_of_country" in src             # Land → Region
    assert ".commit(" not in src                  # rein lesend


def test_operator_owns_everything_not_claimed():
    """Quelltext-Garantie: ``set_territory`` speichert NUR **Abweichungen** – eine Zuweisung
    an die ohnehin zuständige Gesellschaft LÖSCHT die Zeile (keine wirkungslosen Ansprüche)."""
    from app.services import sites

    src = inspect.getsource(sites.set_territory)
    assert "db.delete(" in src                            # Standard = Zeile entfernen
    assert "_default_owner_id(db, code)" in src


# ─── Ausnahmen je Land: Land ≻ Region ≻ Betreiber ────────────────────────────────

def test_an_area_is_a_region_or_a_country_and_never_both():
    """Der Gebiets-Code ist EINE Spalte für Region ODER Land – der Unterschied ist aus der
    **Form** abgeleitet (ISO-2 = 2 Zeichen, Regions-Code ≥ 3). Kollisionsfrei per
    Konstruktion: kein Regions-Code darf zweistellig sein."""
    from app.services import geography

    for code in geography.REGION_CODES:
        assert len(code) >= 3, f"Regions-Code {code} kollidiert mit ISO-2"
        assert not geography.is_country_code(code)
    for cc in ("CH", "li", "US"):
        assert geography.is_country_code(cc)

    # normalize_area akzeptiert beides – und NUR Bekanntes (kein Anspruch auf ein Gebiet,
    # das es gar nicht gibt).
    assert geography.normalize_area("eur") == "EUR"
    assert geography.normalize_area("li") == "LI"
    assert geography.normalize_area("XX") is None
    assert geography.normalize_area("") is None
    assert geography.normalize_area(None) is None


def test_country_beats_region_in_the_resolution():
    """Quelltext-Garantie der Vorrangordnung **Land ≻ Region ≻ Betreiber**: die Land-Abfrage
    steht VOR der Regions-Abfrage – sonst wäre eine Ausnahme wirkungslos."""
    from app.services import sites

    src = inspect.getsource(sites.company_for_country)
    at_country = src.index("_claim_owner(db, code)")
    at_region = src.index("region_of_country")
    assert at_country < at_region, "Die Land-Ausnahme muss VOR der Region greifen"
    assert ".commit(" not in src                          # weiterhin rein lesend


def test_a_country_exception_falls_back_to_its_region_not_to_the_operator():
    """Ein Land ohne eigenen Anspruch gehört dem Besitzer **seiner Region** (nicht dem
    Betreiber) – deshalb ist genau das die Aufräum-Regel beim Zurücksetzen."""
    from app.services import sites

    src = inspect.getsource(sites._default_owner_id)
    assert "is_country_code" in src
    assert "region_of_country" in src
    assert "_claim_owner" in src

    # ``country_map`` liefert den EFFEKTIVEN Besitzer je Land – dieselbe Vorrangordnung als
    # Batch (die Oberfläche leitet «ist Ausnahme» daraus ab, statt ein zweites Flag zu führen).
    src = inspect.getsource(sites.country_map)
    assert "territory_map" in src
    assert "COUNTRY_REGION" in src


def test_territory_table_is_a_new_table_not_a_new_column():
    """Neue Tabelle → ``create_all`` deckt sie; sie braucht KEIN Spalten-Safety-Net.
    (Der Wächter stellt sicher, dass niemand versehentlich eine Spalte auf einer bestehenden
    Tabelle einführt, die dann im Lifespan-Netz fehlen würde.)"""
    from app.models import CompanyTerritory

    assert CompanyTerritory.__tablename__ == "company_territories"
    cols = {c.name for c in CompanyTerritory.__table__.columns}
    assert cols == {"id", "region", "company_id"}


# ─── Slice 2: Seller of Record je Verkauf (eingefroren) + Beleg-/Absender-Identität ──
