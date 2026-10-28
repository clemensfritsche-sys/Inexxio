from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.auth import require_admin, require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.admin import (
    CompanyCreate,
    CompanyPerson,
    CompanySettingsResponse,
    CompanySettingsUpdate,
    TerritoryAssign,
    TerritoryCompany,
    TerritoryCountry,
    TerritoryMapResponse,
    TerritoryRegion,
)
from ..services import sites

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ─── Settings ─────────────────────────────────────────────────────────────────

def _people_of(db: Session, oids: list[int]) -> dict[int, list[CompanyPerson]]:
    """Die Personen je Firma – EINE Abfrage für alle Firmen."""
    out: dict[int, list[CompanyPerson]] = {o: [] for o in oids}
    if not oids:
        return out
    for u in (db.query(UserProfile)
              .filter(UserProfile.company_object_id.in_(oids), UserProfile.object_id.isnot(None))
              .order_by(UserProfile.last_name, UserProfile.first_name).all()):
        out[u.company_object_id].append(CompanyPerson(object_id=u.object_id, name=u.display_name,
                                                      email=u.email, role=u.role))
    return out


def _company_responses(db: Session, companies: list) -> list[CompanySettingsResponse]:
    """Unternehmens-Antworten mit **abgeleiteten** Feldern – der Betreiber einmal gefragt, die
    Personen in einer Abfrage. ``is_operator``, ``has_address`` und ``website`` sind
    Projektionen (``sites.find_operator``, ``address.has_content``, ``sites.website_url``);
    die IBAN steht unmaskiert da – sie steht auf jeder Rechnung, die wir stellen."""
    from ..services import address
    op = sites.find_operator(db)
    people_of = _people_of(db, [c.object_id for c in companies if c.object_id])
    out = []
    for company in companies:
        resp = CompanySettingsResponse.model_validate(company)
        resp.is_operator = bool(op and op.id == company.id)
        resp.has_address = address.has_content(address.of_company(company))
        resp.website = sites.website_url()
        resp.legal_name = sites.legal_name(company)
        resp.people = people_of.get(company.object_id, [])
        out.append(resp)
    return out


def _company_response(db: Session, company) -> CompanySettingsResponse:
    return _company_responses(db, [company])[0]


@router.get("/settings/public")
def get_public_settings():
    """Ohne Anmeldung: der **Google-Maps-Schlüssel** für die Adress-Suche – sonst nichts.

    Er kommt aus der Deploy-Konfiguration der Umgebung (``GOOGLE_MAPS_API_KEY``), nicht aus
    der Datenbank: so überlebt er einen Neuaufbau, und dev und prod haben je ihren eigenen.
    Er steht ohnehin im Browser (in Google Cloud auf die Adressen eingeschränkt). Impressum
    und Kontaktdaten liefert die Website bzw. ``/public/contact``."""
    from ..core.config import get_settings
    return {"google_maps_api_key": get_settings().google_maps_api_key or None}


# ─── Unternehmen (Gesellschaften) ─────────────────────────────────────────────
#
# EIN gleichrangiger Datensatztyp (``organization``). Jede Gesellschaft ist vollständig:
# eigene Rechtsidentität, Bank, MWST. Anlegen/Ändern sind **admin-only** (fix vorgegeben);
# an der Sichtbarkeit im ERP ändert das nichts. Die Rechtsidentität wird auf JEDEM
# Datensatz gepflegt (die US-Gesellschaft hat ihre eigene). Eine Plattform-Konfiguration
# in der Datenbank gibt es nicht (der Maps-Schlüssel kommt aus dem Deploy).

@router.get("/companies", response_model=list[CompanySettingsResponse])
def list_companies(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Alle Firmen – eigene und fremde, Betreiber zuerst. **Jeder Mitarbeiter** sieht sie:
    eine Kundenfirma ist ein ganz gewöhnlicher ERP-Datensatz."""
    return _company_responses(db, sites.all_companies(db))


@router.get("/companies/{object_id}", response_model=CompanySettingsResponse)
def get_company(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Ein Unternehmen mit vollem Feldsatz (frisch, für die Detail-Ansicht)."""
    return _company_response(db, sites.require(db, object_id))


@router.post("/companies", response_model=CompanySettingsResponse, status_code=201)
def create_company(
    data: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Neue Firma anlegen – **jeder Mitarbeiter**; eine **eigene** Gesellschaft nur ein
    Admin (``is_own``).

    Sie bekommt sofort eine Objektnummer und ist als **Halter** verwendbar: Instanzen
    können dort liegen, die Standort-Kette löst sie auf, und eine Bewegung dorthin wird –
    sobald sie eine eigene Anschrift trägt – automatisch als Versand statt als
    innerbetriebliche Bewegung klassifiziert (ADR 005)."""
    fields = data.model_dump(exclude_unset=True)
    own = bool(fields.pop("is_own", False))
    if own and current_user.role != "admin":
        raise HTTPException(403, detail="Eine eigene Gesellschaft legt nur ein Admin an.")
    company = sites.create(db, fields, current_user.id, own=own)
    return _company_response(db, company)


@router.patch("/companies/{object_id}", response_model=CompanySettingsResponse)
def update_company(
    object_id: int,
    data: CompanySettingsUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Felder einer Firma ändern – **derselbe Pfad für jede** (auch den
    Betreiber): Name, Anschrift, Währung, Rechtsidentität, Bank, MWST (``sites.apply_update``)."""
    company = sites.require(db, object_id)
    sites.apply_update(db, company, data.model_dump(exclude_unset=True), current_user.id,
                       admin=current_user.role == "admin")
    return _company_response(db, company)


@router.post("/companies/{object_id}/operator", response_model=CompanySettingsResponse)
def set_company_operator(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    """Diese Gesellschaft zum **Betreiber der Website** machen (Impressum + Systemkonfig).

    Genau EINE Gesellschaft trägt den Titel; das Setzen nimmt ihn allen anderen ab. Damit
    ist die Rolle **wählbar** (nicht mehr starr «das älteste»)."""
    company = sites.require(db, object_id)
    sites.set_operator(db, company, current_user.id)
    return _company_response(db, company)


@router.delete("/companies/{object_id}", response_model=CompanySettingsResponse)
def deactivate_company(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Ein Unternehmen **schliessen** (Soft-Delete, umkehrbar über ``…/reopen``). Der
    **Betreiber** und die **letzte** eigene Gesellschaft lassen sich nicht schliessen."""
    company = sites.require(db, object_id)
    if company.is_own and current_user.role != "admin":
        raise HTTPException(403, detail="Eine eigene Gesellschaft schliesst nur ein Admin.")
    sites.deactivate(db, company, current_user.id)
    return _company_response(db, company)


@router.post("/companies/{object_id}/reopen", response_model=CompanySettingsResponse)
def reopen_company(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    """Ein geschlossenes Unternehmen **wieder öffnen** – dieselbe Berechtigung wie das
    Schliessen."""
    company = sites.require(db, object_id)
    if company.is_own and current_user.role != "admin":
        raise HTTPException(403, detail="Eine eigene Gesellschaft öffnet nur ein Admin.")
    sites.reopen(db, company, current_user.id)
    return _company_response(db, company)


# ─── Gebiete (Weltkarte: welche Gesellschaft fakturiert welche Region) ────────────

def _territory_map_response(db: Session) -> TerritoryMapResponse:
    from ..services import geography
    op = sites.operator(db)
    mapping = sites.territory_map(db)                 # {region: company_object_id}
    companies = [
        # Der Datensatzname trägt seine Rechtsform (#910) – auf der Karte steht
        # dieselbe Gesellschaft wie im Feed und auf dem Beleg.
        TerritoryCompany(object_id=c.object_id, name=sites.legal_name(c),
                         is_operator=sites.is_operator(db, c))
        for c in sites.selectable_companies(db) if c.object_id is not None
    ]
    regions = [
        TerritoryRegion(code=r["code"], label=r["label"], pos=r["pos"],
                        company_object_id=mapping.get(r["code"]))
        for r in geography.REGIONS
    ]
    # Jedes bekannte Land mit seinem effektiven Besitzer (Land-Ausnahme ≻ Region ≻ Betreiber).
    # Die Oberfläche braucht die volle Liste als Auswahl und leitet die Ausnahmen daraus ab.
    countries_owner = sites.country_map(db)
    countries = [
        TerritoryCountry(code=code, region=region,
                         company_object_id=countries_owner.get(code))
        for code, region in sorted(geography.COUNTRY_REGION.items())
    ]
    return TerritoryMapResponse(regions=regions, countries=countries, companies=companies,
                                operator_object_id=op.object_id)


@router.get("/territories", response_model=TerritoryMapResponse)
def get_territories(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_admin),
):
    """Die **Gebietskarte**: jede Weltregion und jedes Land + die Gesellschaft, die es
    fakturiert. Nicht zugewiesene Regionen gehören dem **Betreiber** (er besitzt die Welt per
    Default); ein Land kann als **Ausnahme** von seiner Region abweichen."""
    return _territory_map_response(db)


@router.put("/territories/{area}", response_model=TerritoryMapResponse)
def assign_territory(
    area: str,
    data: TerritoryAssign,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    """Ein **Gebiet** einer Gesellschaft zuweisen (Weltkarte): eine Region («EUR») oder – als
    Ausnahme – ein einzelnes Land («LI»). ``null`` bzw. die ohnehin zuständige Gesellschaft =
    Standard wiederherstellen. Genau EINE Gesellschaft je Gebiet."""
    sites.set_territory(db, area, data.company_object_id, current_user.id)
    return _territory_map_response(db)

