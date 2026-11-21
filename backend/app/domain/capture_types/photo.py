"""Bild — **eine Aufnahme, über die Kamera**.

Erfasst wird die **Präsenz**; was darauf zu sehen ist, beurteilt ein Mensch. **Genau eine
Aufnahme** (eine URL, keine Liste), und sie kommt aus der Kamera, nicht aus einer Datei –
durchgesetzt in der Oberfläche; hier steht die Form.
"""

from typing import Any

from .base import CaptureType


class Photo(CaptureType):
    key = "photo"
    label = "Bild"
    order = 30

    def missing(self, point: dict[str, Any], value: Any) -> bool:
        """Genau **eine** Aufnahme – alles andere (auch eine Liste) gilt als nicht erfasst."""
        return not isinstance(value, str) or not value.strip()


TYPE = Photo()
