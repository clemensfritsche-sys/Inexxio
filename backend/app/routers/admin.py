from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import require_admin, require_employee
from ..core.database import get_db
from ..models import AuditLog, UserProfile
from ..schemas.admin import (
    CompanyCreate,
    CompanySettingsResponse,
    CompanySettingsUpdate,
    TerritoryAssign,
    TerritoryCompany,
    TerritoryCountry,
    TerritoryMapResponse,
    TerritoryRegion,
    UserProfileResponse,
)
from ..services import sites
from ..services.admin import log_audit

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _mask_iban(value: str | None) -> str | None:
    if not value or len(value) < 8:
        return value
    return value[:4] + " **** **** **** " + value[-4:]


# ─── Settings ─────────────────────────────────────────────────────────────────

def _company_response(db: Session, company) -> CompanySettingsResponse:
    """Vollständige Unternehmens-Antwort mit maskierter Bank + **abgeleiteten** Feldern.

    ``is_operator`` (ältestes Unternehmen), ``has_address`` und ``website`` sind
    Projektionen, keine gespeicherten Flags – die eine Definition von «trägt echte
    Ortsangaben» steht in ``address.has_content``, die der Website-Adresse in
    ``sites.website_url``; hier werden sie nur angewandt."""
    from ..services import address
    resp = CompanySettingsResponse.model_validate(company)
    resp.iban_masked = _mask_iban(company.iban_encrypted)
    resp.is_operator = sites.is_operator(db, company)
    resp.has_address = address.has_content(address.of_company(company))
    resp.website = sites.website_url()
    return resp


@router.get("/settings", response_model=CompanySettingsResponse)
async def get_settings(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_admin),
):
    """Der **Betreiber** – Trägerin der Plattform-Konfiguration der einen Website. Der
    Reiter «System» am Unternehmens-Datensatz liest und schreibt genau diese Zeile."""
    return _company_response(db, sites.operator(db))


@router.patch("/settings", response_model=CompanySettingsResponse)
async def update_settings(
    data: CompanySettingsUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    s = sites.operator(db)
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "iban":
            s.iban_encrypted = value
            log_audit(db, "company_settings", key, "[UPDATED]", current_user.id)
        else:
            setattr(s, key, value)
            log_audit(db, "company_settings", key, str(value), current_user.id)
    db.commit()
    db.refresh(s)
    return _company_response(db, s)


@router.get("/settings/public")
async def get_public_settings(db: Session = Depends(get_db)):
    """No auth — used by Impressum, AGB, Datenschutz pages.

    Immer der **Betreiber** (das älteste Unternehmen): das Impressum nennt den Betreiber der
    Website – und der wechselt NICHT nach Besucherland (eine Website, ein Betreiber). Die
    übrigen Konzern-Gesellschaften werden – wenn gewünscht – zusätzlich aufgelistet, nicht
    umgeschaltet."""
    from ..services.sites import find_operator, website_url
    s = find_operator(db)
    if not s:
        return {"company_name": "Inexxio AG", "legal_form": "AG", "email": "info@inexxio.com",
                "website": website_url(), "country": "Schweiz"}
    return {
        "object_id": s.object_id,
        "company_name": s.company_name, "legal_form": s.legal_form,
        "street": s.street, "street_nr": s.street_nr, "zip_code": s.zip_code,
        "city": s.city, "country": s.country, "uid_number": s.uid_number,
        "vat_number": s.vat_number,
        "email": s.email, "phone": s.phone, "website": website_url(),
        "google_maps_api_key": s.google_maps_api_key,
    }


# ─── Unternehmen (Gesellschaften) ─────────────────────────────────────────────
#
# EIN gleichrangiger Datensatztyp (``organization``). Jede Gesellschaft ist vollständig:
# eigene Rechtsidentität, Bank, MWST. Anlegen/Ändern sind **admin-only** (fix vorgegeben);
# an der Sichtbarkeit im ERP ändert das nichts. Die Rechtsidentität wird hier – anders als
# beim früheren «Standort» – auf JEDEM Datensatz gepflegt (die US-Gesellschaft hat ihre
# eigene). Plattform-/Systemkonfiguration bleibt getrennt (``PATCH /admin/settings``).

@router.get("/companies", response_model=list[CompanySettingsResponse])
async def list_companies(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_admin),
):
    """Alle Unternehmen, Betreiber (ältestes) zuerst."""
    return [_company_response(db, c) for c in sites.all_companies(db)]


@router.get("/companies/{object_id}", response_model=CompanySettingsResponse)
async def get_company(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_admin),
):
    """Ein Unternehmen mit vollem Feldsatz (frisch, für die Detail-Ansicht)."""
    return _company_response(db, sites.require(db, object_id))


@router.post("/companies", response_model=CompanySettingsResponse, status_code=201)
async def create_company(
    data: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    """Neue Gesellschaft anlegen (nur Admin).

    Sie bekommt sofort eine Objektnummer und ist als **Halter** verwendbar: Instanzen
    können dort liegen, die Standort-Kette löst sie auf, und eine Bewegung dorthin wird –
    sobald sie eine eigene Anschrift trägt – automatisch als Versand statt als
    innerbetriebliche Bewegung klassifiziert (ADR 005)."""
    company = sites.create(db, data.model_dump(exclude_unset=True), current_user.id)
    return _company_response(db, company)


@router.patch("/companies/{object_id}", response_model=CompanySettingsResponse)
async def update_company(
    object_id: int,
    data: CompanySettingsUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    """Entitäts-Felder einer Gesellschaft ändern – **derselbe Pfad für jede** (auch den
    Betreiber): Name, Anschrift, Währung, Rechtsidentität, Bank, MWST.

    Die **Plattform-Konfiguration** wird bewusst NICHT hier gesetzt – ``sites.apply_update``
    ignoriert diese Felder; sie laufen über ``PATCH /admin/settings``, damit dieselbe Angabe
    nicht an zwei Stellen editierbar ist."""
    company = sites.require(db, object_id)
    sites.apply_update(db, company, data.model_dump(exclude_unset=True), current_user.id)
    return _company_response(db, company)


@router.post("/companies/{object_id}/operator", response_model=CompanySettingsResponse)
async def set_company_operator(
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
async def deactivate_company(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    """Ein Unternehmen **schliessen** (Soft-Delete, endgültig – keine Reaktivierung).

    Eine wiedereröffnete Gesellschaft ist rechtlich eine andere (neue UID/EIN, neues
    HR-Datum) – sie wird darum neu angelegt, nicht wiederbelebt. Der **Betreiber** und die
    **letzte** Gesellschaft lassen sich nicht schliessen; die Gebiete der geschlossenen
    fallen an den Betreiber zurück."""
    company = sites.require(db, object_id)
    sites.deactivate(db, company, current_user.id)
    return _company_response(db, company)


# ─── Gebiete (Weltkarte: welche Gesellschaft fakturiert welche Region) ────────────

def _territory_map_response(db: Session) -> TerritoryMapResponse:
    from ..services import geography
    op = sites.operator(db)
    mapping = sites.territory_map(db)                 # {region: company_object_id}
    companies = [
        TerritoryCompany(object_id=c.object_id, company_name=c.company_name,
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
async def get_territories(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_admin),
):
    """Die **Gebietskarte**: jede Weltregion und jedes Land + die Gesellschaft, die es
    fakturiert. Nicht zugewiesene Regionen gehören dem **Betreiber** (er besitzt die Welt per
    Default); ein Land kann als **Ausnahme** von seiner Region abweichen."""
    return _territory_map_response(db)


@router.put("/territories/{area}", response_model=TerritoryMapResponse)
async def assign_territory(
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


@router.get("/users", response_model=list[UserProfileResponse])
async def list_users(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return [UserProfileResponse.model_validate(u) for u in
            db.query(UserProfile).order_by(UserProfile.email).all()]


# **Ein Benutzer wird nicht deaktiviert – er wechselt die Rolle** (Testnotiz #755).
#
# Wer das Unternehmen verlässt, hört nicht auf zu existieren: er wird vom Mitarbeiter zum
# Kunden und darf weiter einkaufen. Ein Soft-Delete an der Person beantwortete eine Frage,
# die niemand stellt – und er hatte Folgen, die niemand wollte (die Anmeldung sperren,
# offene Dokument-Freigaben blockieren, eine Identität stilllegen, auf die Aufträge,
# Instanzen und Belege zeigen). Beide Endpunkte (`DELETE /users/{id}` und
# `POST /users/{id}/reactivate`) sind darum ersatzlos entfallen; gepflegt wird die Rolle,
# und das an der einen Stelle, an der jeder Datensatz gepflegt wird
# (`PATCH /erp/records/{object_id}`).
#
# Die Abweisung beim Login (`core/auth`) bleibt: sie verhindert, dass eine deaktivierte
# Alt-Zeile still als **neuer** Benutzer wiederaufersteht. Setzen kann diesen Zustand
# nichts mehr; Migration 118 hat die bestehenden aufgehoben.


# ─── Audit log ────────────────────────────────────────────────────────────────

@router.get("/audit-log")
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    table_name: str | None = Query(None),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_admin),
):
    q = db.query(AuditLog)
    if table_name:
        q = q.filter(AuditLog.table_name == table_name)
    total = q.count()
    logs = q.order_by(AuditLog.changed_at_utc.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [
            {"id": l.id, "object_id": l.object_id, "table_name": l.table_name,
             "field_name": l.field_name, "old_value": l.old_value, "new_value": l.new_value,
             "user_id": l.user_id, "changed_at_utc": l.changed_at_utc}
            for l in logs
        ],
    }
