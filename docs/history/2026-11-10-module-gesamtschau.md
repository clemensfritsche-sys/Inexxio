# 2026-11-10 · Die fünf Prozess-Module: Gesamtschau, Fehler, A und B

## Anlass
Nach der Prüfung von Prozess und Auftrag wollte der Inhaber dieselbe Prüfung für jedes Modul
(Datenerfassung, Aussondern, Verbrauch, Bewegen, Zahlung). Drei Prüfungen liefen parallel; die
Befunde wurden am Code und mit Wegwerf-Tests nachgeprüft.

## Fehler (behoben, je mit Test, der gegen den alten Stand rot ist)
- **Stichprobe umgehbar**: eine Instanz ohne gezogenes Stück ging beim Bestätigen sofort
  weiter; fiel danach ein gezogenes Stück durch, war der verdächtige Rest schon fort. Jetzt
  bewegt Bestätigen nur Gezogenes (`process._drawn_only`), der Rest läuft mit `carry_on`.
  (Entscheid des Inhabers: so.)
- **Zahlung «von Hand bestätigt»** im Protokoll, obwohl niemand bestätigte.
- **Verbrauch nahm die grösste Kiste statt der ältesten** – die Oberfläche wählte, der Server
  folgte. Jetzt sagt der Server den Plan (`StepNeed.plan`).
- **Eine verschrottete Kiste brach die Ortskette** einer Charge.
- **Gutschrift über die Rechnung hinaus** möglich; **Storno einer Gutschrift** gab eine
  «Gutschrift» hinaus; **überfällige Lieferantenrechnung** zeigte «Letzte Mahnung».

## A – aufgeräumt
Stichprobe nur an Modulen mit Erfassungspunkten; «nicht bestanden» eine Konstante und eine
Regel (`held_units`), die zweite Frage nach den durchgefallenen Nummern weg; Protokoll ohne
Zwischenkopie; Orte: `place_from` · `one_place` · `describe_all`; FIFO eine Abfrage;
`AUTO_RELEASE` und Durchreicher weg; Belegmodule lesen einander über öffentliche Namen.

## B – eine Stelle
- «fehlt» / «am falschen Ort» rechnet nur der Server (`StepNeed.missing` · `misplaced`).
- Die Richtung eines Belegs speichert ein Bit (`collects`), der Rest ist abgeleitet.
- Ein Vokabular für den Stand eines Belegs (`vo.STATES`, `voucher.standing`) – Karte und
  Zahlungsliste sagen dasselbe («Beglichen» heisst jetzt Saldo 0, «Storniert» ist ein Stand).

## Bewusst nicht
- Satz «ohne MWST» für Lieferanten (Entscheid: so lassen).
- Das Urteil im `capture`-Ereignis des Logs bleibt (das Log ist der Nachweis je Stück).
- C (Zahlung als Eigenschaft des Moduls statt Abfrage im Kern) – erst erklärt, nicht gebaut.

## Geprüft
Backend 821 grün, Frontend Typen · Lint · 161 Tests grün, generierte Dateien aktuell.
