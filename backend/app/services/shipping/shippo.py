"""Shippo-Adapter (Carrier-Aggregator, https://goshippo.com).

Strategische Wahl (ADR 005): Self-Serve wie Stripe (Test-Key sofort sichtbar nach
Registrierung, Pay-per-Label, keine Vertrags-Eintrittsbarriere), sauberes REST-API,
solide EU-Carrier-Abdeckung. Hinter dem Gateway-Interface bleibt der Anbieter jederzeit
austauschbar (EasyPost/Sendcloud wären Drop-in-Adapter).

API-Fluss (synchron, ``async=false``):
  POST /shipments/     {address_from, address_to, parcels}      → rates[] (inline, mit object_id)
  POST /transactions/  {rate: <rate_object_id>, label_file_type} → label_url + tracking_number

Einheiten: Shippo rechnet nativ in **cm/kg** – keine Umrechnung nötig. Der Kauf braucht
nur die Rate-Objektnummer (kein separater Shipment-Kauf-Endpunkt). Fehler werden als
HTTPException 502 mit Shippo-Meldung durchgereicht (kein Crash).
"""

from fastapi import HTTPException

from ...core.config import get_settings
from .base import ShippingProvider

_TIMEOUT = 20.0


def _parse_rate(r: dict) -> dict | None:
    """Ein Shippo-Rate-Objekt in unser neutrales Format bringen (tolerant)."""
    try:
        amount = float(r.get("amount"))
    except (TypeError, ValueError):
        return None
    rid = str(r.get("object_id") or "")
    if not rid:
        return None
    service = r.get("servicelevel") or {}
    days = r.get("estimated_days")
    return {
        "rate_id": rid,
        "carrier": str(r.get("provider") or "Carrier"),
        "service": str(service.get("name") or "") or None,
        "amount": amount,
        "currency": str(r.get("currency") or "CHF").upper(),
        "days": int(days) if isinstance(days, (int, float)) else None,
        "provider_rate_id": rid,
    }


def _messages(raw) -> list[str]:
    """Shippo-Hinweise (warum keine/weniger Tarife) in lesbare Strings bringen –
    z. B. »USPS: The origin country is not supported«. Diese Meldungen sind bei
    einer leeren Tarifliste die einzige Erklärung; sie dürfen nicht verloren gehen."""
    out: list[str] = []
    for m in raw or []:
        if isinstance(m, dict):
            src = str(m.get("source") or "").strip()
            txt = str(m.get("text") or m.get("code") or "").strip()
            out.append(f"{src}: {txt}" if src and txt else (txt or src))
        elif m:
            out.append(str(m))
    # Duplikate stabil entfernen (Shippo wiederholt dieselbe Meldung je Carrier).
    seen: set[str] = set()
    uniq = []
    for m in out:
        if m and m not in seen:
            seen.add(m)
            uniq.append(m)
    return uniq


class ShippoShipping(ShippingProvider):
    name = "shippo"
    supports_rates = True

    def _client(self):
        import httpx
        settings = get_settings()
        return httpx.Client(
            base_url=settings.shippo_api_url,
            headers={"Authorization": f"ShippoToken {settings.shippo_api_key}",
                     "Content-Type": "application/json"},
            timeout=_TIMEOUT,
        )

    def _post(self, path: str, payload: dict) -> dict:
        try:
            with self._client() as client:
                resp = client.post(path, json=payload)
        except Exception as exc:   # Netzwerk/Timeout – sauber melden, nie crashen
            raise HTTPException(502, detail=f"Versand-Anbieter nicht erreichbar: {exc}") from exc
        if resp.status_code >= 400:
            raise HTTPException(502, detail=f"Shippo-Fehler ({resp.status_code}): {resp.text[:300]}")
        return resp.json()

    def rates(self, address_from: dict, address_to: dict, parcels: list[dict]) -> dict:
        payload = {
            "address_from": address_from,
            "address_to": address_to,
            "parcels": [
                {
                    "length": str(p.get("length_cm") or 30),
                    "width": str(p.get("width_cm") or 20),
                    "height": str(p.get("height_cm") or 15),
                    "distance_unit": "cm",
                    "weight": str(p.get("weight_kg") or 0.5),
                    "mass_unit": "kg",
                }
                for p in (parcels or [{}])
            ],
            "async": False,
        }
        data = self._post("/shipments/", payload)
        rates = [x for x in (_parse_rate(r) for r in data.get("rates") or []) if x]
        return {
            "provider_shipment_id": str(data.get("object_id") or "") or None,
            "rates": rates,
            "messages": _messages(data.get("messages")),
        }

    def buy(self, provider_shipment_id: str | None, provider_rate_id: str) -> dict:
        # Shippo kauft direkt gegen die Rate-Objektnummer (kein Shipment-Kauf-Endpunkt).
        data = self._post("/transactions/",
                          {"rate": provider_rate_id, "label_file_type": "PDF", "async": False})
        if (data.get("status") or "").upper() not in ("SUCCESS", "QUEUED"):
            msgs = "; ".join(str(m.get("text") or m) for m in (data.get("messages") or [])) or "unbekannt"
            raise HTTPException(502, detail=f"Label-Kauf fehlgeschlagen: {msgs[:300]}")
        return {
            "label_url": data.get("label_url"),
            "tracking_number": data.get("tracking_number"),
            "tracking_url": data.get("tracking_url_provider"),
            "provider_shipment_id": provider_shipment_id,
        }
