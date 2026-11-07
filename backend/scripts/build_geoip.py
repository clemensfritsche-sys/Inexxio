"""Baut die IP→Land-Tabelle für ``services/geoip.py`` (läuft im Docker-Build).

Quelle ist **DB-IP «IP to Country Lite»** (CC BY 4.0, monatlich neu, ohne Konto). Wir
nehmen den laufenden Monat, sonst den vorigen, und schreiben eine kompakte Fassung:
benachbarte Bereiche mit demselben Land werden zusammengezogen, Adressen als Zahl.

►►► Scheitert der Download, scheitert der Build NICHT. ◄◄◄ Ohne Tabelle kennt die Website
das Land des Besuchers nicht und zeigt die Kontaktdaten des Betreibers – genau das, was sie
heute ohnehin zeigt. Ein Fremddienst darf ein Deploy nicht anhalten.

Aufruf: ``python scripts/build_geoip.py [quelle.csv.gz]`` (mit Datei: ohne Download).
"""

from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import ipaddress
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "assets" / "geoip" / "ip-country.csv.gz"
URL = "https://download.db-ip.com/free/dbip-country-lite-{month}.csv.gz"


def _months() -> list[str]:
    today = dt.date.today().replace(day=1)
    prev = (today - dt.timedelta(days=1)).replace(day=1)
    return [today.strftime("%Y-%m"), prev.strftime("%Y-%m")]


def _download() -> tuple[bytes, str] | None:
    for month in _months():
        url = URL.format(month=month)
        try:
            with urllib.request.urlopen(url, timeout=60) as r:   # noqa: S310 – feste https-Adresse
                return r.read(), month
        except Exception as e:  # noqa: BLE001 – jede Störung heisst «ohne Tabelle weiter»
            print(f"GeoIP: {url} nicht erreichbar ({e})")
    return None


def _rows(raw: bytes):
    with gzip.open(io.BytesIO(raw), "rt", encoding="utf-8") as f:
        for start, end, cc in csv.reader(f):
            a, b = ipaddress.ip_address(start), ipaddress.ip_address(end)
            if len(cc) == 2 and cc != "ZZ":
                yield a.version, int(a), int(b), cc.upper()


def build(raw: bytes, source: str) -> int:
    merged: list[list] = []
    for fam, a, b, cc in sorted(_rows(raw)):
        last = merged[-1] if merged else None
        if last and last[0] == fam and last[3] == cc and last[2] + 1 >= a:
            last[2] = max(last[2], b)
        else:
            merged.append([fam, a, b, cc])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="ascii") as f:
        f.write(f"# {source} - IP Geolocation by DB-IP (https://db-ip.com), CC BY 4.0\n")
        for fam, a, b, cc in merged:
            f.write(f"{fam},{a},{b},{cc}\n")
    return len(merged)


def main() -> None:
    if len(sys.argv) > 1:
        raw, source = Path(sys.argv[1]).read_bytes(), Path(sys.argv[1]).name
    else:
        got = _download()
        if got is None:
            print("GeoIP: keine Tabelle – die Website zeigt die Kontaktdaten des Betreibers.")
            return
        raw, source = got[0], f"dbip-country-lite-{got[1]}"
    print(f"GeoIP: {build(raw, source)} Bereiche → {OUT}")


if __name__ == "__main__":
    main()
