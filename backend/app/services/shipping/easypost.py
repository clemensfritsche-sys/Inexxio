"""EasyPost-Adapter (Carrier-Aggregator, https://easypost.com).

Strategische Wahl (ADR 005): Self-Serve wie Stripe (Test-Key sofort, Pay-per-Label,
keine Vertrags-Eintrittsbarriere), sehr sauberes REST-API (der «Stripe des Versands»),
international skalierbar (100+ Carrier, u. a. DHL Express/UPS/FedEx für CH-Ausland).
Hinter dem Gateway-Interface bleibt der Anbieter jederzeit austauschbar (Sendcloud/
Shippo wären Drop-in-Adapter).

API-Fluss (v2, HTTP-Basic mit API-Key als Benutzername):
  POST /v2/shipments               {shipment: {to_address, from_address, parcel}} → rates[]
  POST /v2/shipments/{id}/buy      {rate: {id}} → postage_label.label_url + tracking_code

Einheiten: EasyPost rechnet in **Inches/Ounces** – Umrechnung aus cm/kg hier im Adapter.
Fehler werden als HTTPException 502 mit EasyPost-Meldung durchgereicht (kein Crash).
"""

from fastapi import HTTPException

from ...core.config import get_settings
from .base import ShippingProvider

_TIMEOUT = 20.0
_CM_PER_INCH = 2.54
_OZ_PER_KG = 35.274


def _parcel_payload(p: dict) -> dict:
    """Unser Paket (cm/kg) → EasyPost-Parcel (inches/oz), defensiv mit Minima."""
    def _in(v, default):
        try:
            return max(round(float(v) / _CM_PER_INCH, 1), 0.1)
        except (TypeError, ValueError):
            return default
    try:
        oz = max(round(float(p.get("weight_kg") or 0.5) * _OZ_PER_KG, 1), 1.0)
    except (TypeError, ValueError):
        oz = 17.6   # ~0.5 kg
    return {
        "length": _in(p.get("length_cm"), 11.8),   # 30 cm
        "width": _in(p.get("width_cm"), 7.9),      # 20 cm
        "height": _in(p.get("height_cm"), 5.9),    # 15 cm
        "weight": oz,
    }


def _parse_rate(r: dict) -> dict | None:
    """Ein EasyPost-Rate-Objekt in unser neutrales Format bringen (tolerant)."""
    try:
        amount = float(r.get("rate"))
    except (TypeError, ValueError):
        return None
    rid = str(r.get("id") or "")
    if not rid:
        return None
    days = r.get("delivery_days")
    if days is None:
        days = r.get("est_delivery_days")
    return {
        "rate_id": rid,
        "carrier": str(r.get("carrier") or "Carrier"),
        "service": str(r.get("service") or "") or None,
        "amount": amount,
        "currency": str(r.get("currency") or "USD").upper(),
        "days": int(days) if isinstance(days, (int, float)) else None,
        "provider_rate_id": rid,
    }


class EasyPostShipping(ShippingProvider):
    name = "easypost"
    supports_rates = True

    def _client(self):
        import httpx
        settings = get_settings()
        return httpx.Client(
            base_url=settings.easypost_api_url,
            auth=(settings.easypost_api_key, ""),   # HTTP Basic: Key als Benutzername
            timeout=_TIMEOUT,
        )

    def _post(self, path: str, payload: dict) -> dict:
        try:
            with self._client() as client:
                resp = client.post(path, json=payload)
        except Exception as exc:   # Netzwerk/Timeout – sauber melden, nie crashen
            raise HTTPException(502, detail=f"Versand-Anbieter nicht erreichbar: {exc}") from exc
        if resp.status_code >= 400:
            try:
                msg = (resp.json().get("error") or {}).get("message") or resp.text[:300]
            except Exception:
                msg = resp.text[:300]
            raise HTTPException(502, detail=f"EasyPost-Fehler ({resp.status_code}): {msg}")
        return resp.json()

    def rates(self, address_from: dict, address_to: dict, parcels: list[dict]) -> dict:
        parcel = _parcel_payload((parcels or [{}])[0])   # EIN Paket je Shipment (EasyPost)
        payload = {"shipment": {
            "from_address": address_from,
            "to_address": address_to,
            "parcel": parcel,
        }}
        data = self._post("/shipments", payload)
        rates = [x for x in (_parse_rate(r) for r in data.get("rates") or []) if x]
        return {"provider_shipment_id": str(data.get("id") or "") or None, "rates": rates}

    def buy(self, provider_shipment_id: str | None, provider_rate_id: str) -> dict:
        if not provider_shipment_id:
            raise HTTPException(409, detail="Versand-Referenz fehlt – bitte Tarife neu laden")
        data = self._post(f"/shipments/{provider_shipment_id}/buy",
                          {"rate": {"id": provider_rate_id}})
        label = data.get("postage_label") or {}
        tracker = data.get("tracker") or {}
        return {
            "label_url": label.get("label_url"),
            "tracking_number": data.get("tracking_code"),
            "tracking_url": tracker.get("public_url"),
            "provider_shipment_id": str(data.get("id") or "") or provider_shipment_id,
        }
