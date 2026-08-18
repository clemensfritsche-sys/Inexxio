"""**Sendcloud** – europäischer Aggregator mit nativer Schweiz-Herkunft.

Neu geschrieben (ADR 009 Stufe 5). Der Vorgänger sass hinter einem Gateway, das bei
fehlenden Schlüsseln stillschweigend auf «manual» zurückfiel – und genau darum merkte
niemand, dass nie ein Tarif kam. Hier gilt: **ohne Schlüssel gibt es diesen Anbieter
nicht** (``available()``), und ein Fehler ist ein Fehler.

Zwei Schlüssel, HTTP-Basic (Public = Benutzer, Secret = Passwort). Sendcloud rechnet
nativ in **Gramm** und **Zentimetern**; die Umrechnung steht hier und nirgends sonst.

*Der Kauf legt bei Sendcloud die Sendung an (``/parcels``) – anders als bei Shippo, wo
der Abruf sie schon anlegt. Beide Formen passen unter dieselben zwei Methoden, weil
``shipment_ref`` optional ist: der Adapter weiss, was sein Anbieter braucht, der Aufrufer
nicht.*
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

#: Was Sendcloud «zugestellt» bzw. «gescheitert» nennt. Alles andere ist unterwegs –
#: eine feinere Abstufung wäre Anzeige, keine Entscheidung (siehe ``base``).
_DELIVERED = {"delivered", "delivered_at_pickup_point"}
_FAILED = {"cancelled", "cancellation_requested", "delivery_failed", "returned_to_sender",
           "shipment_cancelled", "error_collecting"}


class Sendcloud(Carrier):
    key = "sendcloud"
    label = "Sendcloud"

    def available(self) -> bool:
        s = get_settings()
        return bool(s.sendcloud_public_key and s.sendcloud_secret_key)

    # ── Tarife ──────────────────────────────────────────────────────────────────
    def quote(self, sender: Address, receiver: Address, parcel: Parcel) -> Quote:
        """Versandmethoden für dieses Land und dieses Gewicht.

        Sendcloud beantwortet die Frage über ``/shipping_methods`` (Methoden je
        Land-Paar); der Preis hängt am Vertrag und kommt je Methode mit. Eine leere
        Liste ist eine **Antwort** – sie sagt, dass für diese Strecke nichts hinterlegt
        ist, und das steht in ``messages``.
        """
        if parcel.hazmat:
            return Quote(messages=["Gefahrgut – Sendcloud vermittelt dafür keine Tarife."])
        grams = int(Decimal(parcel.weight_kg) * 1000)
        data = self._get("/shipping_methods", params={
            "from_country": sender.country, "to_country": receiver.country,
        })
        offers, seen = [], set()
        for m in data.get("shipping_methods", []):
            price = _price_for(m, receiver.country)
            if price is None or not _fits(m, grams):
                continue
            ref = str(m.get("id"))
            if ref in seen:
                continue
            seen.add(ref)
            offers.append(CarrierOffer(
                carrier=(m.get("carrier") or "").title() or "Sendcloud",
                service=m.get("name") or "Versand",
                amount=Decimal(str(price)), currency=get_settings().sendcloud_currency,
                days=_days(m), ref=ref,
            ))
        if not offers:
            offers_msg = (f"Sendcloud hat für {sender.country} → {receiver.country} bei "
                          f"{grams} g keine Versandmethode hinterlegt.")
            return Quote(messages=[offers_msg])
        # Sendcloud legt die Sendung erst beim Kauf an – was sie dann braucht, packt der
        # **Adapter** hier zusammen. Der Aufrufer reicht es nur durch; müsste er es selbst
        # bauen, kennte er die Feldnamen eines Anbieters, und der nächste hat andere.
        return Quote(offers=offers, shipment_ref=_encode(receiver, parcel))

    # ── Kauf ────────────────────────────────────────────────────────────────────
    def buy(self, offer_ref: str, *, shipment_ref: str = "") -> Label:
        """Bei Sendcloud entsteht die Sendung **erst beim Kauf** (``/parcels``).

        Darum trägt ``shipment_ref`` hier die Anschrift und das Gewicht als JSON – der
        Adapter weiss, was sein Anbieter braucht; der Aufrufer reicht nur durch, was er
        beim Abruf bekommen hat.
        """
        payload = _decode(shipment_ref)
        if not payload:
            raise HTTPException(
                status_code=409,
                detail=("Für diesen Kauf fehlt die Sendung – bitte die Tarife erneut "
                        "holen. Sendcloud legt die Sendung erst beim Kauf an."),
            )
        payload["shipment"] = {"id": int(offer_ref)}
        payload["request_label"] = True
        data = self._post("/parcels", {"parcel": payload})
        parcel = data.get("parcel") or {}
        label = (parcel.get("label") or {}).get("label_printer") or ""
        return Label(
            label_url=label,
            tracking_number=parcel.get("tracking_number") or "",
            tracking_url=parcel.get("tracking_url") or "",
            shipment_ref=str(parcel.get("id") or ""),
        )

    # ── Verfolgung ──────────────────────────────────────────────────────────────
    def track(self, tracking_number: str, *, carrier: str = "") -> Tracking:
        data = self._get("/parcels", params={"tracking_number": tracking_number})
        rows = data.get("parcels") or []
        if not rows:
            return Tracking(UNTERWEGS, "Sendcloud kennt diese Sendungsnummer (noch) nicht.")
        status = ((rows[0].get("status") or {}).get("message") or "").strip()
        key = status.lower().replace(" ", "_")
        if key in _DELIVERED:
            return Tracking(ZUGESTELLT, status)
        if key in _FAILED:
            return Tracking(UNZUSTELLBAR, status)
        return Tracking(UNTERWEGS, status)

    # ── HTTP ────────────────────────────────────────────────────────────────────
    def _auth(self) -> tuple[str, str]:
        s = get_settings()
        return (s.sendcloud_public_key, s.sendcloud_secret_key)

    def _get(self, path: str, *, params: Optional[dict] = None) -> dict:
        return self._call("GET", path, params=params)

    def _post(self, path: str, body: dict) -> dict:
        return self._call("POST", path, json=body)

    def _call(self, method: str, path: str, **kw: Any) -> dict:
        s = get_settings()
        try:
            r = httpx.request(method, f"{s.sendcloud_api_url}{path}",
                              auth=self._auth(), timeout=s.carrier_timeout_s, **kw)
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Sendcloud ist nicht erreichbar: {exc}") from exc
        if r.status_code >= 400:
            raise HTTPException(502, f"Sendcloud meldet {r.status_code}: {r.text[:200]}")
        return r.json() if r.content else {}


def _price_for(method: dict, country: str) -> Optional[float]:
    """Der Preis für dieses Zielland – Sendcloud führt ihn je Land."""
    for row in method.get("countries") or []:
        if (row.get("iso_2") or "").upper() == country.upper():
            price = row.get("price")
            return float(price) if price is not None else None
    return None


def _fits(method: dict, grams: int) -> bool:
    lo, hi = method.get("min_weight"), method.get("max_weight")
    try:
        if lo is not None and grams < float(lo) * 1000:
            return False
        if hi is not None and grams > float(hi) * 1000:
            return False
    except (TypeError, ValueError):
        return True
    return True


def _days(method: dict) -> Optional[int]:
    for row in method.get("countries") or []:
        d = row.get("lead_time_hours")
        if d:
            return max(1, int(round(float(d) / 24)))
    return None


def _decode(ref: str) -> dict:
    import json
    try:
        out = json.loads(ref) if ref else {}
    except ValueError:
        return {}
    return out if isinstance(out, dict) else {}


def _encode(receiver: Address, parcel: Parcel) -> str:
    """Was Sendcloud beim **Kauf** braucht – vom Adapter gebaut, nie vom Aufrufer."""
    import json
    return json.dumps({
        "name": receiver.name or "Empfänger",
        "address": receiver.street, "city": receiver.city,
        "postal_code": receiver.zip, "country": receiver.country,
        "email": receiver.email or "", "telephone": receiver.phone or "",
        "weight": str(Decimal(parcel.weight_kg)),
    })
