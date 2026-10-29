# 2026-10-26 · «Verkauft» als Status, Eigentum abgeleitet

> Rundenbericht. Was gilt, steht in `CLAUDE.md` (Datenmodell: Status, Ort, Eigentum) und
> `PROCESS_CORE.md` §9.15s und «Jedes Stück behält seinen Ort».

## Ausgangslage
Das Eigentum stand als eigene Spalte am Stück (`instance_units.owner_object_id`, gesetzt beim
Passieren eines Zahlungsmoduls) und wurde als «verkauft an …» angezeigt. Ein verkauftes Stück
kam am Ziel trotzdem als «Freigegeben» in den Bestand und war per FIFO wählbar.

## Entscheid (mit dem Auftraggeber besprochen)
- **Eigentum: zwei Optionen, Pflichtwahl** – «geht an die Partei» · «geht an uns», ohne
  Vorbelegung; «bleibt» entfällt. Ohne Wahl kein Anbieten und keine Zusage.
- **Wem ein Stück gehört, wird abgeleitet**: das jüngste nicht stornierte Zahlungsmodul, das es
  passiert hat (`voucher.sold_units`). Keine gespeicherte Kopie – ein Storno wirkt von selbst.
- **Am Ziel** (`process._finish`): gehört es der Partei → «Verkauft», sonst «Freigegeben».
  Der Status wird weiter nur hier geschrieben; Bestand, FIFO, Verbrauch und Abweichung lesen
  nur den Status.
- **Ort**: jedes Stück behält ihn, ausser es ist verschrottet (vorher: wer zur Historie zählt).
- Die Spalte, das Schreiben beim Passieren (`on_pass`, `payload.owner`) und die Anzeige
  «verkauft an …» sind entfernt; Migration `156` droppt die Spalte in **einem** Deploy
  (Rückwärtskompatibilität ausdrücklich freigegeben).

## Verworfen
- Status erst bei vollständiger Zahlung: bei Rechnung mit Frist wäre das Stück am Ziel frei
  und müsste später von aussen auf «Verkauft» – ein Status ausserhalb des Prozesses.
- Spalte behalten und beim Storno zurücksetzen: zwei Schreibstellen.
- Nur den aktuellen Auftrag betrachten: eine Reparatur ohne Zahlung würde die Kundenmaschine
  zu unserem Bestand.
- Status «wie beim Eingang» wiederherstellen: braucht ein Gedächtnis über Abweichungen hinweg.

## Geprüft
Neue Tests in `test_zahlung_ablauf.py`: Pflichtwahl und Einfrieren; Verkauf → Verkauft, auch
unbezahlt; Storno im Lauf → Freigegeben; Verkauft behält den Ort; Einkauf → Freigegeben;
Reparatur → bleibt Verkauft; Retoure «an uns» hebt auf; stornierte Retoure → wieder Verkauft.
Jeder Wächter gegen seine Fehlerform geprüft (Storno ignoriert, Ort weg bei Historie, nie
Verkauft, keine Pflichtwahl – je rot).

## Bewusst offen
- Bauteil aus einem verkauften Produkt ausgebaut: erbt das Eigentum nicht.
- Kundenmaschinen, die nie uns gehörten (Eigentum bei der Erfassung).
