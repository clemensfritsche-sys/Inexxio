"""Signatur — handschriftlich, als Bild.

Technisch dasselbe wie ``photo`` (Präsenz, kein Urteil) und trotzdem ein **eigener** Typ:
die Bedeutung ist eine andere, die Eingabe ist eine andere (Zeichenfläche statt Kamera),
und eine Unterschrift als «Bild» zu führen hiesse, sie später nicht wiederzufinden.
"""

from .base import CaptureType


class Signature(CaptureType):
    key = "signature"
    label = "Signatur"
    order = 40


TYPE = Signature()
