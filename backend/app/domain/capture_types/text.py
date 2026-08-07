"""Freitext — der einfachste Fall und damit die Vorlage für jeden weiteren."""

from .base import CaptureType


class Text(CaptureType):
    key = "text"
    label = "Text"
    order = 10


TYPE = Text()
