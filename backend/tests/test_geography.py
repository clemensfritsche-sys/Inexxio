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
    """Quelltext-Garantie: ``set_territory`` speichert NUR Abweichungen vom Betreiber – eine
    Zuweisung an den Betreiber LÖSCHT die Zeile (die Tabelle hält keine Default-Zeilen)."""
    from app.services import sites

    src = inspect.getsource(sites.set_territory)
    assert "db.delete(" in src                    # Betreiber = Zeile entfernen
    assert "company.id == op.id" in src


def test_territory_table_is_a_new_table_not_a_new_column():
    """Neue Tabelle → ``create_all`` deckt sie; sie braucht KEIN Spalten-Safety-Net.
    (Der Wächter stellt sicher, dass niemand versehentlich eine Spalte auf einer bestehenden
    Tabelle einführt, die dann im Lifespan-Netz fehlen würde.)"""
    from app.models import CompanyTerritory

    assert CompanyTerritory.__tablename__ == "company_territories"
    cols = {c.name for c in CompanyTerritory.__table__.columns}
    assert cols == {"id", "region", "company_id"}


# ─── Slice 2: Seller of Record je Verkauf (eingefroren) + Beleg-/Absender-Identität ──

def test_seller_of_record_wiring_uses_the_derived_company():
    """Quelltext-Garantie: Beleg-Briefkopf UND Versand-Absender nehmen die abgeleitete
    fakturierende Gesellschaft (nicht mehr fix den Betreiber); die Auflösung ist rein lesend."""
    from app.services import sale as sale_svc, logistics
    from app.routers import documents

    src = inspect.getsource(sale_svc.seller_company_for_order)
    assert "seller_company_object_id" in src        # Snapshot zuerst
    assert "find_operator" in src                    # Betreiber-Fallback
    assert ".commit(" not in src                     # rein lesend
    # Beleg-Briefkopf (PDF) nimmt den Seller des Auftrags:
    assert "seller_company_for_order" in inspect.getsource(documents._company)
    # Versand-Absender nimmt den Seller des Auftrags:
    assert "seller_company_for_order" in inspect.getsource(logistics._sender_company)


def test_freeze_seller_is_idempotent_and_needs_a_customer():
    """Quelltext-Garantie: ``_freeze_seller`` setzt nie neu (Snapshot) und braucht einen Kunden."""
    from app.services import sale as sale_svc

    src = inspect.getsource(sale_svc._freeze_seller)
    assert "seller_company_object_id is not None" in src   # nie überschreiben
    assert "customer_id is None" in src                     # ohne Kunde: nichts


def test_seller_column_is_in_the_lifespan_safety_net():
    """Neue Spalte auf der bestehenden ``sales``-Tabelle MUSS im Lifespan-Netz stehen –
    sonst endete jede sales-Abfrage in einem 500, wenn Migration 093 nicht liefe (090-Lehre)."""
    from app.main import _COLUMN_SAFETY_NET

    assert ("sales", "seller_company_object_id", "BIGINT") in _COLUMN_SAFETY_NET
