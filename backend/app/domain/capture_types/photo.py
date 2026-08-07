"""Bild — Foto oder Upload.

Erfasst wird die **Präsenz**: es liegt eine Aufnahme vor oder nicht. Was darauf zu sehen
ist, beurteilt ein Mensch – darum trägt dieser Typ kein Urteil.
"""

from .base import CaptureType


class Photo(CaptureType):
    key = "photo"
    label = "Bild"
    order = 30


TYPE = Photo()
