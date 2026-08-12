"""Objekt scannen — **womit** wurde gearbeitet.

Der Nachweis über ein Werkzeug, eine Maschine, ein Prüfmittel: die Objektnummer dessen,
was zum Einsatz kam. Erfasst wie jeder andere Wert; der Unterschied ist nur die Eingabe
(Kamera statt Tastatur).

**Warum das ein Erfassungspunkt ist und kein Modul.** Ein Werkzeug wird nicht verbraucht.
Liefe es über die Auftragsdefinition, griffe die Exklusivität (§3) – und eine Fräse wäre
in genau **einem** Auftrag, während sie real in zwanzig gleichzeitig steckt. Der
Materialfluss ist hier also die falsche Ebene: gefragt ist eine **Aussage über den
Vorgang**, nicht eine über den Verbleib des Werkzeugs. Genau dafür gibt es die
Datenerfassung.

**Kein Urteil.** Womit gearbeitet wurde, ist ein Beleg, keine Bewertung – ein erfundenes
«in Ordnung» wäre eine Aussage, die niemand getroffen hat.

**Keine Existenzprüfung hier.** Dieser Layer kennt die Datenbank nicht (und soll sie nicht
kennen: die Typen sind reine Regeln). Verifiziert wird über den **Scan-Dialog**, der nur
gelesene Objektnummern zurückgibt; eine von Hand getippte Nummer ist so vertrauenswürdig
wie ``verification='manual'`` an der Bestätigung – erlaubt, protokolliert, und als das
erkennbar.
"""

from typing import Any

from .base import CaptureType


class ObjectScan(CaptureType):
    key = "object"
    label = "Objekt scannen"
    order = 60

    def missing(self, point: dict[str, Any], value: Any) -> bool:
        return not str(value or "").strip()


TYPE = ObjectScan()
