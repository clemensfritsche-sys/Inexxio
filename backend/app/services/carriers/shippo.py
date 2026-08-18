"""**Shippo** – Pay-per-Label, ein Schlüssel, sofort nach der Registrierung nutzbar.

Neu geschrieben (ADR 009 Stufe 5). Shippo legt die Sendung schon beim **Abruf** an und
gibt je Tarif eine eigene Referenz zurück; gekauft wird allein gegen diese – die Sendung
muss der Aufrufer nicht kennen. Genau darum ist ``shipment_ref`` in der Naht optional:
zwei Anbieter, zwei Abläufe, **eine** Schnittstelle.

Shippo rechnet in Zoll und Pfund, wenn man nichts anderes sagt. Der Adapter schickt
darum ausdrücklich ``cm``/``kg`` – die Umrechnung steht hier und nirgends sonst.
"""

from decimal import Decimal
from typing import Any, Optional

import httpx
from fastapi import HTTPException

from ...core.config import get_settings
from .base import (
    Address, Carrier, CarrierOffer, UNZUSTELLBAR, Label, Parcel, Quote, Tracking,
    UNTERWEGS, ZUGESTELLT,
)

_DELIVERED = {"DELIVERED"}
_FAILED = {"RETURNED", "FAILURE"}


class Shippo(Carrier):
    key = "shippo"
    label = "Shippo"

    def available(self) -> bool:
        return bool(get_settings().shippo_api_key)

    # ── Tarife ──────────────────────────────────────────────────────────────────
    def quote(self, sender: Address, receiver: Address, parcel: Parcel) -> Quote:
        data = self._post("/shipments/", {
            "address_from": _addr(sender),
            "address_to": _addr(receiver),
            "parcels": [{
                "length": str(parcel.length_cm), "width": str(parcel.width_cm),
                "height": str(parcel.height_cm), "distance_unit": "cm",
                "weight": str(parcel.weight_kg), "mass_unit": "kg",
            }],
            "async": False,
        })
        offers = [
            CarrierOffer(
                carrier=r.get("provider") or "Shippo",
                service=(r.get("servicelevel") or {}).get("name") or "Versand",
                amount=Decimal(str(r.get("amount") or "0")),
                currency=(r.get("currency") or "USD").upper()[:3],
                days=int(r["estimated_days"]) if r.get("estimated_days") else None,
                ref=str(r.get("object_id") or ""),
            )
            for r in data.get("rates") or []
            if r.get("object_id")
        ]
        # Shippo erklärt eine leere Liste selbst («Herkunftsland nicht unterstützt»).
        # Diese Sätze **weiterzugeben statt zu schlucken** ist der Unterschied zwischen
        # einer Auskunft und einem Achselzucken.
        messages = [
            str(m.get("text") or m.get("message") or "").strip()
            for m in data.get("messages") or []
        ]
        if parcel.hazmat:
            messages.append("Gefahrgut – die Tarife gelten nur ohne Gefahrgut-Zuschlag.")
        return Quote(offers=offers, messages=[m for m in messages if m],
                     shipment_ref=str(data.get("object_id") or ""))

    # ── Kauf ────────────────────────────────────────────────────────────────────
    def buy(self, offer_ref: str, *, shipment_ref: str = "") -> Label:
        """Gekauft wird allein gegen die **Tarif**-Referenz – die Sendung steht schon."""
        data = self._post("/transactions/", {
            "rate": offer_ref, "label_file_type": "PDF", "async": False,
        })
        if (data.get("status") or "").upper() not in ("SUCCESS", "QUEUED", "WAITING"):
            reason = "; ".join(str(m.get("text") or "") for m in data.get("messages") or [])
            raise HTTPException(502, f"Shippo hat das Etikett nicht ausgestellt: {reason}")
        return Label(
            label_url=data.get("label_url") or "",
            tracking_number=data.get("tracking_number") or "",
            tracking_url=data.get("tracking_url_provider") or "",
            shipment_ref=shipment_ref or str(data.get("object_id") or ""),
        )

    # ── Verfolgung ──────────────────────────────────────────────────────────────
    def track(self, tracking_number: str, *, carrier: str = "") -> Tracking:
        if not carrier:
            # Shippo verlangt den Frachtführer im Pfad. Ohne ihn zu raten wäre eine
            # Anfrage auf Verdacht – und die Antwort darauf wäre nicht verlässlich.
            return Tracking(UNTERWEGS, "Ohne Frachtführer lässt sich bei Shippo nicht "
                                       "nachverfolgen.")
        data = self._get(f"/tracks/{carrier.lower()}/{tracking_number}")
        status = ((data.get("tracking_status") or {}).get("status") or "").upper()
        detail = (data.get("tracking_status") or {}).get("status_details") or status
        if status in _DELIVERED:
            return Tracking(ZUGESTELLT, detail)
        if status in _FAILED:
            return Tracking(UNZUSTELLBAR, detail)
        return Tracking(UNTERWEGS, detail)

    # ── HTTP ────────────────────────────────────────────────────────────────────
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"ShippoToken {get_settings().shippo_api_key}"}

    def _get(self, path: str) -> dict:
        return self._call("GET", path)

    def _post(self, path: str, body: dict) -> dict:
        return self._call("POST", path, json=body)

    def _call(self, method: str, path: str, **kw: Any) -> dict:
        s = get_settings()
        try:
            r = httpx.request(method, f"{s.shippo_api_url}{path}",
                              headers=self._headers(), timeout=s.carrier_timeout_s, **kw)
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Shippo ist nicht erreichbar: {exc}") from exc
        if r.status_code >= 400:
            raise HTTPException(502, f"Shippo meldet {r.status_code}: {r.text[:200]}")
        return r.json() if r.content else {}


def _addr(a: Address) -> dict[str, Optional[str]]:
    return {"name": a.name or "—", "street1": a.street, "zip": a.zip, "city": a.city,
            "country": a.country, "email": a.email or None, "phone": a.phone or None}
