"""Ja/Nein — Daumen hoch, Daumen runter.

Der einzige Typ neben ``measure``, der ein **Urteil** trägt: «nein» ist nicht bloss
ein Wert, sondern eine Aussage über das Stück.
"""

from typing import Any, Optional

from .base import CaptureType


class YesNo(CaptureType):
    key = "bool"
    label = "Ja/Nein"
    order = 20

    def missing(self, point: dict[str, Any], value: Any) -> bool:
        # Nicht angetippt ist nicht dasselbe wie «nein». Ohne diese Unterscheidung
        # zählte ein übersehener Pflichtpunkt als bewusstes «schlecht».
        return value not in (True, False)

    def verdict(self, point: dict[str, Any], value: Any) -> Optional[bool]:
        return value is True


TYPE = YesNo()
