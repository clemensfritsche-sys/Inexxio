"""Aus welchem Land kommt eine Anfrage? – nur für die **Kontaktdaten der Website**.

Die Tabelle baut ``scripts/build_geoip.py`` im Docker-Build (DB-IP Lite, CC BY 4.0). Gibt
es sie nicht, antwortet ``country_of`` mit ``None`` – und ``sites.company_for_country``
nimmt dann den Betreiber. Das Land ist eine **Annäherung** (VPN, Firmennetz, Mobilfunk);
dafür reicht es: falsch geraten zeigt es die Kontaktdaten einer Schwestergesellschaft.

**Gespeichert wird nichts** – weder Adresse noch Land. Geladen wird beim ersten Aufruf,
einmal je Instanz.
"""

from __future__ import annotations

import bisect
import gzip
import ipaddress
from functools import lru_cache
from pathlib import Path

TABLE = Path(__file__).resolve().parent.parent / "assets" / "geoip" / "ip-country.csv.gz"


@lru_cache(maxsize=1)
def _table() -> dict[int, tuple[list[int], list[int], list[str]]]:
    out: dict[int, tuple[list[int], list[int], list[str]]] = {4: ([], [], []), 6: ([], [], [])}
    if not TABLE.exists():
        return out
    with gzip.open(TABLE, "rt", encoding="ascii") as f:
        for line in f:
            if line.startswith("#"):
                continue
            fam, a, b, cc = line.rstrip("\n").split(",")
            starts, ends, ccs = out[int(fam)]
            starts.append(int(a))
            ends.append(int(b))
            ccs.append(cc)
    return out


def country_of(ip: str | None) -> str | None:
    """ISO-2 des Landes zu einer IP-Adresse – ``None``, wenn unbekannt oder privat."""
    try:
        addr = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return None
    if not addr.is_global:
        return None
    starts, ends, ccs = _table()[addr.version]
    i = bisect.bisect_right(starts, int(addr)) - 1
    if i >= 0 and int(addr) <= ends[i]:
        return ccs[i]
    return None


def client_ip(headers, peer: str | None) -> str | None:
    """Die Adresse des Besuchers: Firebase Hosting und Cloud Run setzen sie an den Anfang von
    ``X-Forwarded-For``; ohne Proxy (lokal) ist es die Gegenstelle."""
    forwarded = (headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return forwarded or peer
