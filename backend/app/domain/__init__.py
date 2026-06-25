"""Fachlicher Kern (domain) – deklarative Definitionen, die KEINE DB/Services kennen.

Hier liegt die **eine** Quelle der Wahrheit für die fachlichen Ereignis-/Schritt-
typen (``event_types``). Services/Router/Schemas lesen daraus, statt eigene
verstreute Tabellen zu pflegen.
"""
