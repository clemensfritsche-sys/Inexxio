"""Bild — **eine Aufnahme, über die Kamera** (Testnotizen #718/#720).

Erfasst wird die **Präsenz**: es liegt eine Aufnahme vor oder nicht. Was darauf zu sehen
ist, beurteilt ein Mensch – darum trägt dieser Typ kein Urteil.

**Genau eine Aufnahme, nicht mehr.** Der Wert ist eine URL, keine Liste. Eine Liste
liesse offen, welche der Aufnahmen die gemeinte ist, und «mehr ist besser» ist bei einem
Nachweis das Gegenteil von genau: gefragt war ein Bild dieses Stücks.

**Und sie kommt aus der Kamera, nicht aus einer Datei.** Das Hochladen ist ersatzlos
entfallen – ein Bild aus der Galerie belegt nichts über *diesen* Vorgang, es belegt nur,
dass es irgendwann eine Datei gab. Durchgesetzt wird das in der Oberfläche (es gibt keine
Dateiauswahl mehr); hier steht die Form, die dabei herauskommt.
"""

from typing import Any

from .base import CaptureType


class Photo(CaptureType):
    key = "photo"
    label = "Bild"
    order = 30

    def missing(self, point: dict[str, Any], value: Any) -> bool:
        """Genau **eine** Aufnahme – alles andere gilt als nicht erfasst.

        Eine Liste wird damit abgewiesen statt stillschweigend angenommen: sie wäre der
        alte Mehrfach-Upload, und ein Nachweis, der sich in der Form unterscheidet, ist
        hinterher nicht mehr vergleichbar.
        """
        return not isinstance(value, str) or not value.strip()


TYPE = Photo()
