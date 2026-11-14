# Sortiment – unabhängige Prüfung des Bestellmodells (14.11.2026)

> Prüfung der Projektakte `docs/konzept/sortiment.md` (Fassung 13) gegen den Code auf `develop`, durch einen
> zweiten Prüfer ohne die Schlussfolgerungen der Akte. Ergebnis eingearbeitet in Fassung 14 (§0, §5).

**Urteil:** Das Modell trägt im Kern – Verkauf und Lieferung als eigene Aufträge, Weitergabe mit Herkunft,
Ausnahme als Unterdeckung passen zum System. Aber «keine Kern-Änderung» (E34) und «der Beleg bleibt, wie er
ist» (F25 F9) waren falsch.

**Blocker:**
- A1 – ein nur wartender Auftrag gilt als Abgebrochen (`order_state.py:273,436`; `advance_payments` bricht
  ab, `process.py:463`).
- A2 – Positionen, Seriennummern und Einfrieren lesen nur offene Zugehörigkeiten (`voucher.py:393,410`,
  `voucher_offer.py:254`); erwartete Stücke fehlen, `_units_gone` meldete «nur Stornieren».
- A3 – Stück tauschen bricht jede Zusage (`unit_ids` eingefroren, `units_problem`).
- A4 – `sold_units` (`voucher.py:611`) nimmt das jüngste Zahlungsmodul; ein Spediteur-Modul mit Pflichtwahl
  Eigentum kippt verkaufte Stücke zurück in den Bestand.
- A5 – `consumption._free` (`:96`) prüft den Ort nicht: Mietgeräte beim Kunden gelten als frei.

**Wichtig:** Anzahlung im Verkauf hält den Bau nicht auf · Storno während des Baus und nach Eintritt ·
abgebrochene Kartenzahlung (`pay` erst ab «gestellt», `voucher_actions.py:273`) · mehrere Belege, eine
Belastung · Anlage nimmt nur einen Auftrag · nie freigegebene Lieferung als Sackgasse · Gäste mit fremder
E-Mail · stille Abo-Zusage bei geändertem Preis · Abo hält das Gerät exklusiv · Miete mit Vorauszahlung ·
E34/§3 «keine Vormerkung».

**Klein:** «der Reihe nach» unnötig · Vorlagen ohne Kundengeld · Teillieferung · ein Datum je Kette ·
Sperr-Reihenfolge · Kompetenz der Unterdeckung am Start · AB von Hand · Schnittmenge vs. grösste Art.
Hinweis des Prüfers zu F28 (Grösse Pflicht → alle Artikel ersetzen) trifft nicht zu: Grösse und Gewicht
sind heute schon Pflicht (`services/articles.py:24-25`).

**Vereinfachungen, übernommen:** Lieferung immer automatisch · Anzahlung im Bauauftrag · Warten als
Definitionszeile · Unterdeckung in der Form `StepNeed` · Abo als «Neu»-Leistungsartikel · «frei» an einer Stelle.
