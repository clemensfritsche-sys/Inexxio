# Projektakte «Wiederkehrende Aufträge»

> **Kopfstatus:** in Klärung · **nichts gebaut** · Lead: Claude · Entscheid: Clemens Fritsche ·
> seit 06.11.2026
> Bild (Ist-Stand 1:1 und Vorschläge): https://claude.ai/artifact/Lk5AKy8G1CTWi68ZxA57uj
> Diese Akte ist die **eine** Quelle für Ziel, Grundsätze, Vorschläge und Entscheide. Das Bild
> zeigt, die Akte hält fest. Was hier nicht als entschieden steht, ist nicht entschieden.
> Ausgangspunkt im Kern: `PROCESS_CORE.md` §13 Punkt 6.

## 1 · Problem

Prüffristen, Wartungen (intern und extern), wiederkehrende Lieferungen und Abos (Produkt oder
Software) leben heute im Kopf. Ist ein Auftrag abgeschlossen, weiss das System nicht, dass er in
zwölf Monaten wieder fällig ist.

## 2 · Ziel

**Was sich wiederholt, wird nicht vergessen – und läuft so weit wie möglich von selbst.**

Mit **einer** Logik für alle Fälle. Kranprüfung, Service-Vertrag, INEXXIO 365 und monatliche
Lieferung unterscheiden sich nur in der Konfiguration des Auftrags, nicht im Modell.

## 3 · Grundsätze (entschieden, 06.11.2026)

1. **Eine Logik, am Auftrag.** Es gibt keine Fallunterscheidung.
2. **Jede Wiederholung ist ein ganz gewöhnlicher Auftrag.** Er läuft durch und endet wie jeder
   andere. Zwischen zwei Wiederholungen ist das Stück frei, also nicht im Prozess.
3. **Eine Wiederkehr gibt es nur an einem regulären Auftrag, nie an einer Abweichung.**
4. **Der Takt ist Zeit, an einem festen Kalendertag** (wie bei einem Abo). Zähler wie
   Betriebsstunden oder Kilometer kommen später; das Modell lässt nur Platz dafür.
5. **Solange der vorige Auftrag offen ist, entsteht kein neuer.** Sobald er abgeschlossen ist,
   entsteht der neue sofort.
6. **Jederzeit änderbar und beendbar, ohne Kündigungsfrist.** Ändert sich der Ablauf (z. B.
   ein Prüfpunkt mehr), wird die Wiederkehr beendet und ein neuer Auftrag mit eigener
   Wiederkehr angelegt.
7. **Der Vertrag ist die Wiederkehr.** Ein Papier ist höchstens ein Dokument daran. Abschliessen
   und kündigen durch den Kunden geschieht später online (eigenes Projekt, «wie bei jedem Abo»).
8. **Alles ist ein Stück.** Ein fremder Kran ist ein Artikel mit Instanz, ein Abo auch (z. B.
   Artikel «INEXXIO 365», eine Instanz je Abo).
9. **Die Eigentumswahl bleibt frei.** Ein Kundenstück nicht zu uns zu holen, liegt in der
   Verantwortung dessen, der den Auftrag anlegt. Es gibt keine Sperre dafür.

## 4 · Befunde aus dem Code

- **Ein verkauftes Stück zu greifen, ist heute immer eine Abweichung** (Rückfrage F8). Der
  Regelstart ist genau ein Zustand, `Freigegeben` (`statuses.START_BEFORE`, PROCESS_CORE
  §12.2, `order_state.deviation_flags`, SYSTEM_LOGIC T7e und U6c). Der Grund damals: «Das
  Greifen IST die Rücknahme». Ein verkauftes Stück zu greifen hiess Retoure, und das Label
  soll die Nachweisbarkeit sichern. **An Service wurde dabei nicht gedacht.** Zusammen mit
  Grundsatz 3 hiesse das: An keinem Kundenstück wäre eine Wiederkehr möglich. → Vorschlag V1.
- **«Verkauft» ist nicht «Freigegeben».** Ein verkauftes Stück wird am Ende eines Auftrags
  wieder «Verkauft» (das Eigentum kommt aus dem jüngsten Zahlungsmodul, `voucher.sold_units`).
  Es ist also nie ein Regelstart.
- **Ein fremder Kran, der per Erzeugungsauftrag («Neu») angelegt wird, endet `Freigegeben`.**
  Er steht dann in **unserem** Bestand, und FIFO darf ihn nehmen. → offen O2.
- **Der Preis steht am Beleg, nicht im Modul.** Das Modul gibt nur Partei, Fristen,
  Lieferbedingung und Eigentum vor (`VOUCHER_PRESETS`). Ein neuer Beleg beginnt bei
  «Offerte» und braucht einen Menschen. → offen O1, der Kern jedes Abos.
- **Heute läuft nichts ohne Anfrage.** Der Mail-Abgleich läuft nur bei offenem ERP, das Siegel
  beim Start und im Abgleich. Ein Takt braucht eine Uhr. → V5.
- **Was es schon gibt:** einen Auftragsentwurf mit vorgewählten Stücken und Ablauf
  (`OrderSeed`, `order-detail.tsx`) und append-only Zeilen «ab Stichtag» (Verträge der
  Zeiterfassung, `time_contracts`).

## 5 · Vorschläge (nicht entschieden)

- **V1 · `Verkauft` wird ein zweiter Regelstart.** Regulär beginnt, was ruht: in keinem
  Auftrag und nicht gesperrt, also `Freigegeben` (bei uns) oder `Verkauft` (bei der Partei).
  Abweichung bleiben Im Prozess (entzogen), Gesperrt (Sonderfreigabe) und Verbaut (Ausbau).
  Eine Retoure ist trotzdem nachgewiesen: durch ihre eigene Zahlung «geht an uns».
  Änderung: `START_BEFORE` wird eine Menge; SYSTEM_LOGIC T7e und U6c werden neu geschrieben.
- **V2 · Anlegen, nicht anbieten.** Die Wiederkehr IST der Entscheid des Menschen, nur im
  Voraus getroffen. Der Grundsatz «automatisch angelegt wird nie etwas» wird genauer gefasst:
  **Nichts entsteht ohne Entscheid eines Menschen.** Anlegen heisst Freigeben, mit derselben
  Prüfung wie von Hand. Scheitert sie (Stück im Prozess, Artikel ersetzt, es fehlt etwas),
  entsteht nichts. «Zu tun» nennt dann den Grund, und der Auftrag entsteht, sobald es geht.
- **V3 · Form: append-only am Auftrag**, wie die Verträge der Zeiterfassung. Eine Zeile sagt
  «ab Stichtag: alle N Monate am Tag X», eine spätere «ab Stichtag: beendet». Wiederholt wird
  die eingefrorene Definition des Vorlage-Auftrags (Zeilen und Module):
  - bestimmte Stücke → wieder dieselben,
  - FIFO → was dann frei ist,
  - «Neu» → neue Stücke (monatliche Lieferung).
- **V4 · Nie doppelt.** Je Wiederkehr und Periode gibt es höchstens einen Auftrag
  (Unique-Index). «Fällig» und «nächster» werden aus dem Takt und den schon erzeugten
  Aufträgen abgeleitet. Nichts wird davon gespeichert.
- **V5 · Die Uhr:** einmal täglich ein Aufruf (Cloud Scheduler, im Gratis-Kontingent),
  dazu derselbe Lauf beim Start. Der Lauf darf beliebig oft laufen, ohne etwas doppelt
  anzulegen (V4).
- **V6 · Abo durchgespielt** (Rückfrage «geht das mit einem Stück auf?»): Artikel
  «INEXXIO 365» mit einer Instanz je Abo. Der Vorlage-Auftrag hat eine Zeile «Lager» mit genau
  diesem Stück und ein Modul Zahlung (Einnahme, «geht an die Partei»). Jeden Monat entsteht
  derselbe Auftrag, also eine Rechnung. Einsätze (Reparatur, Ersatzgerät) sind gewöhnliche
  Aufträge daneben. Ab dem zweiten Monat steht das Stück auf «Verkauft». Das geht also nur
  zusammen mit V1. Damit sind **Pauschale und «je Einsatz» dieselbe Logik**, und Rückfrage F9
  erledigt sich.

## 6 · Offen

- **O1 · Die Zahlung in der Wiederholung.** Übernimmt der neue Beleg Positionen, Preise,
  Partei und Anschrift aus dem Vorlage-Beleg? Gilt die Zusage weiter (direkt «Rechnung
  stellen»), oder wird jedes Mal neu angeboten? Ohne diese Antwort läuft kein Abo von selbst.
- **O2 · Ein fremdes Stück aufnehmen**, ohne dass es in unseren Bestand fällt.
- **O3 · Verpasste Perioden:** eine nachholen oder alle? Bei einem Abo zählt jeder Monat, bei
  einer Prüfung nur die nächste.
- **O4 · Vorlauf:** den Auftrag X Tage vor dem Stichtag anlegen (Planung, Termin, Offerte)?
- **O5 · Sichtbarkeit:** sieht der Kunde seine Fristen im Konto (Kranbuch)?
- **O6 · Stück weg** (verschrottet, verkauft an Dritte): endet die Wiederkehr von selbst? Bei
  bestimmten Stücken wohl ja, bei FIFO nicht.

## 7 · Rückfragen und Antworten

| | Frage | Antwort (06.11.2026) |
|---|---|---|
| F1 | Was soll besser werden? | Wiederholtes gerät nicht in Vergessenheit, möglichst automatisch; eine Logik für alles |
| F2 | Welcher Fall zuerst? | keiner – eine Logik für alle |
| F3 | Anlegen oder anbieten? | unschlüssig, eher selbst anlegen → V2 |
| F4 | Kalender oder letzte Erledigung? | fester Kalendertag (wie ein Abo) |
| F5 | Takte ausser Zeit? | später; nur vorsehen |
| F6 | Voriger Auftrag noch offen? | nicht anlegen, solange offen; danach sofort |
| F7 | Jeder Kran ein Stück? | ja, auch ein fremder (Artikel + Instanz) |
| F8 | Service am verkauften Stück eine Abweichung? | nein, nachanalysieren → Befund §4, V1 |
| F9 | Je Einsatz oder Pauschale? | Frage unklar → mit V6 dieselbe Logik |
| F10 | Vertrag als eigenes Ding? | die Wiederkehr ist der Vertrag; Abschluss später online |
| F11 | Wie endet sie? | jederzeit änderbar und beendbar, ohne Frist |
| F12 | Ablauf ändert sich? | beenden, neuer Auftrag, neue Wiederkehr |
