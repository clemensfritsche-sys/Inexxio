"""Fachlicher Kern (domain) – deklarative Definitionen, die KEINE DB und keine Services
kennen.

Hier liegt die **eine** Quelle der Wahrheit für die fachlichen Aufzählungen, aus denen der
Rest des Systems liest, statt eigene verstreute Tabellen zu pflegen:

  * ``statuses``      – jeder Zustand mit Beschriftung, Ampelton, Achsen und Endgültigkeit
  * ``modules``       – die Prozessschrittmodule und was jedes von ihnen deklariert
  * ``capture_types`` – die Erfassungspunkt-Typen (ein neuer Typ ist eine neue Datei)
  * ``sampling``      – die Stichprobe als EINE Zahl
  * ``chain``         – die Kettenregel (was darf hinter was stehen)
  * ``voucher``       – der Beleg: Richtung, Stufen, Steuer, Saldo
  * ``currency`` · ``incoterms`` · ``uid`` – Währung, Lieferbedingung, Firmennummer
  * ``communication`` – Kanäle und Regeln der Nachrichten
"""
