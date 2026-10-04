"""Was die öffentliche Website aus dem ERP liest – **nur lesend, ohne Anmeldung**.

►►► Das ERP ist die eine Quelle für Telefon, E-Mail und Anschrift (Testnotiz #1094). ◄◄◄
Die Website trägt dieselben Angaben beim Bauen als Vorgabe ins HTML (für Suchmaschinen und
ohne JavaScript) und tauscht sie beim Anzeigen gegen diese Antwort aus – ändert sich im ERP
eine Nummer, steht sie sofort überall auf der Website.

**Welches Unternehmen?** Das zum Land des Besuchers: Land aus der IP-Adresse
(``services/geoip``), Gesellschaft aus den Gebieten des ERP (``sites.company_for_country``:
Land ≻ Region ≻ Betreiber). ``?country=XX`` übersteuert das Land, ``?country=`` (leer)
fragt nach dem Betreiber – so liest der Website-Build die Vorgabe.

Herausgegeben wird nur, was ohnehin auf jeder Rechnung und im Impressum steht. Die
IP-Adresse wird nicht gespeichert.
"""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services import geoip, sites
from ..services import address as addr

router = APIRouter(prefix="/api/v1/public", tags=["website"])

# Vorwahl je Land – nur für die Wahl-Adresse (`tel:`), die Anzeige bleibt wie erfasst.
_CALLING = {"CH": "41", "LI": "423", "DE": "49", "AT": "43", "IT": "39", "FR": "33"}


class PublicContact(BaseModel):
    country: str | None          # erkanntes Land des Besuchers (ISO-2) oder None
    company_object_id: int | None
    name: str
    phone: str | None            # wie im ERP erfasst
    phone_e164: str | None       # für `tel:`
    email: str | None
    address_lines: list[str]     # Strasse, PLZ Ort, Land


def _e164(phone: str | None, country: str | None) -> str | None:
    raw = "".join(c for c in (phone or "") if c.isdigit() or c == "+")
    if not raw:
        return None
    if raw.startswith("+"):
        return raw
    if raw.startswith("00"):
        return "+" + raw[2:]
    code = _CALLING.get((addr.iso2(country) or "").upper())
    return f"+{code}{raw.lstrip('0')}" if code and raw.startswith("0") else raw


@router.get("/contact", response_model=PublicContact)
def public_contact(request: Request, response: Response, country: str | None = None,
                   db: Session = Depends(get_db)):
    if country is None:
        ip = geoip.client_ip(request.headers, request.client.host if request.client else None)
        country = geoip.country_of(ip)
    company = sites.company_for_country(db, country or None)
    # Je Besucher verschieden (Land) → nur im Browser zwischenspeichern, kurz.
    response.headers["Cache-Control"] = "private, max-age=300"
    if company is None:
        return PublicContact(country=country or None, company_object_id=None, name="",
                             phone=None, phone_e164=None, email=None, address_lines=[])
    a = addr.of_company(company)
    phone = (company.phone or "").strip() or None
    return PublicContact(
        country=country or None,
        company_object_id=company.object_id,
        name=sites.legal_name(company),
        phone=phone,
        phone_e164=_e164(phone, company.country),
        email=(company.email or "").strip() or None,
        address_lines=[line for line in addr.lines(a) if line.strip("— ")],
    )
