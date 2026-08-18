"""Sendcloud-Adapter (europäischer Carrier-Aggregator, https://www.sendcloud.com).

Warum Sendcloud (statt Shippo) für eine Schweizer AG: **native Herkunft Schweiz** –
Swiss Post/DPD/DHL & Co. lassen sich ab CH nutzen (Shippos geteilte Gratis-Carrier
können CH-Herkunft NICHT). Self-serve API-Keys, ohne eigenen Carrier-Vertrag über
Sendclouds Tarife startbar, kostenlose Test-Labels («Unstamped letter»).

Auth: HTTP-Basic mit **Public Key** (User) + **Secret Key** (Passwort). Einheiten: kg.

API-Fluss (v2):
  GET  /shipping_methods?from_country=CH&to_country=AT   → verfügbare Versandarten + Preise
  POST /parcels  {parcel: {…, shipment:{id}, request_label:true}}  → Label-URL + Tracking

Fehler werden als HTTPException 502 mit Sendcloud-Meldung durchgereicht (kein Crash).
Hinweise (leere Tarifliste) landen wie beim Shippo-Adapter in ``messages``.

*Bewusst v1/robust gehalten:* Preise kommen aus ``shipping_methods.countries[].price``
(Sendcloud-Tarif; für exakte gewichtsgenaue Preise gäbe es die Shipping-Price-API als
Ausbaustufe). Die Absenderadresse zieht Sendcloud aus der im Panel hinterlegten
Default-Absenderadresse (CH-Lager). Label-URLs sind Sendcloud-authentifiziert – der
direkte Download aus dem Browser ist eine dokumentierte Ausbaustufe (Backend-Proxy).
"""

import re

from fastapi import HTTPException

from ...core.config import get_settings
from .base import ShippingProvider

_TIMEOUT = 20.0


def _to_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _split_street(street: str) -> tuple[str, str]:
    """Strasse → (Strasse ohne Nr., Hausnummer). Sendcloud will die Hausnummer separat."""
    s = (street or "").strip()
    m = re.search(r"^(.*?)[\s,]+(\d+\s*[a-zA-Z]?)$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return s, ""


def _parse_method(m: dict, to_country: str, currency: str) -> dict | None:
    """Eine Sendcloud-Versandart ins neutrale Rate-Format bringen (tolerant)."""
    mid = m.get("id")
    if mid is None:
        return None
    price = None
    for c in m.get("countries") or []:
        if str(c.get("iso_2") or "").upper() == to_country.upper():
            price = _to_float(c.get("price"))
            break
    carrier = str(m.get("carrier") or "").strip() or "Carrier"
    return {
        "rate_id": str(mid),
        "carrier": carrier,
        "service": str(m.get("name") or "") or None,
        "amount": price if price is not None else 0.0,
        "currency": (currency or "EUR").upper(),
        "days": None,
        "provider_rate_id": str(mid),
    }


class SendcloudShipping(ShippingProvider):
    name = "sendcloud"
    supports_rates = True

    def _client(self):
        import httpx
        s = get_settings()
        return httpx.Client(
            base_url=s.sendcloud_api_url,
            auth=(s.sendcloud_public_key, s.sendcloud_secret_key),
            headers={"Content-Type": "application/json"},
            timeout=_TIMEOUT,
        )

    def _request(self, method: str, path: str, **kw) -> dict:
        try:
            with self._client() as client:
                resp = client.request(method, path, **kw)
        except Exception as exc:   # Netzwerk/Timeout – sauber melden, nie crashen
            raise HTTPException(502, detail=f"Versand-Anbieter nicht erreichbar: {exc}") from exc
        if resp.status_code >= 400:
            raise HTTPException(502, detail=f"Sendcloud-Fehler ({resp.status_code}): {resp.text[:300]}")
        return resp.json()

    def _weight(self, parcels: list[dict]) -> float:
        w = 0.0
        for p in parcels or []:
            w += _to_float(p.get("weight_kg")) or 0.0
        return round(w or 0.5, 3)

    def rates(self, address_from: dict, address_to: dict, parcels: list[dict]) -> dict:
        s = get_settings()
        from_c = str((address_from or {}).get("country") or "CH").upper()
        to_c = str((address_to or {}).get("country") or "CH").upper()
        weight = self._weight(parcels)
        data = self._request("GET", "/shipping_methods",
                             params={"from_country": from_c, "to_country": to_c})
        methods = data.get("shipping_methods") or []
        rates = []
        for m in methods:
            minw = _to_float(m.get("min_weight")) or 0.0
            maxw = _to_float(m.get("max_weight"))
            if maxw is not None and not (minw <= weight <= maxw):
                continue
            countries = {str(c.get("iso_2") or "").upper() for c in (m.get("countries") or [])}
            if countries and to_c not in countries:
                continue
            r = _parse_method(m, to_c, s.sendcloud_currency)
            if r:
                rates.append(r)
        messages = []
        if not rates:
            messages.append(
                f"Keine Sendcloud-Versandart für {from_c}→{to_c} bei {weight} kg. In Sendcloud "
                "unter »Einstellungen → Carriers« einen Carrier für diese Herkunft/Strecke "
                "aktivieren (z. B. Swiss Post ab CH).")
        return {"provider_shipment_id": None, "rates": rates, "messages": messages}

    def buy(self, shipment: dict, provider_rate_id: str) -> dict:
        to = (shipment or {}).get("address_to") or {}
        weight = self._weight((shipment or {}).get("parcels") or [])
        street, house = _split_street(str(to.get("street1") or ""))
        method_id = int(provider_rate_id) if str(provider_rate_id).isdigit() else provider_rate_id
        parcel = {
            "name": str(to.get("name") or "Empfänger")[:75],
            "address": (street or "-")[:75],
            "city": str(to.get("city") or "")[:75],
            "postal_code": str(to.get("zip") or ""),
            "country": str(to.get("country") or "CH").upper()[:2],
            "weight": f"{weight:.3f}",
            "request_label": True,
            "shipment": {"id": method_id},
        }
        if house:
            parcel["house_number"] = house
        if to.get("email"):
            parcel["email"] = to["email"]
        if to.get("phone"):
            parcel["telephone"] = to["phone"]
        data = self._request("POST", "/parcels", json={"parcel": parcel})
        p = data.get("parcel") or {}
        label = p.get("label") or {}
        normal = label.get("normal_printer") or []
        label_url = (normal[0] if isinstance(normal, list) and normal else None) or label.get("label_printer")
        return {
            "label_url": label_url,
            "tracking_number": p.get("tracking_number"),
            "tracking_url": p.get("tracking_url") or p.get("carrier_tracking_url"),
            "provider_shipment_id": str(p.get("id")) if p.get("id") is not None else None,
        }
