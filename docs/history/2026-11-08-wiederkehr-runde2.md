# Wiederkehrende Aufträge – Runde 2: die Schlaufe (08.11.2026)

Projektakte `docs/konzept/wiederkehr.md` (Bauplan §8, Runde 2 = Schritte 3–7). Soll vorher
notiert in `SYSTEM_LOGIC.md` §5.10 (W1–W9).

## Was gebaut wurde

- **Fachkern ohne Datenbank** `domain/loop.py`: Takte (`EVERY`), Kalender wie ein Dauerauftrag
  (`after`: Tag der ersten Ausführung, sonst letzter Tag des Monats), Ende (Datum oder Anzahl,
  nicht beides), Wahl je Lager-Zeile (`same` · `fifo`, Pflicht), «Neu» → `new`; Prüfung in zwei
  Formen (`problems` ↔ `clean`), Zustände mit Wort und Ampelton (`STATES`).
- **Gespeichert nur im Log** (keine Tabelle): `loop.set` (die eingefrorene Einstellung, dazu wer
  sie einschaltete), `loop.next` (am Nachfolger, `{from, on}`), `loop.ended`, `loop.agreed`.
  Migration `173_wiederkehr`: eindeutiger Index `ix_log_loop_next` (höchstens ein Nachfolger je
  Auftrag, auch bei zwei gleichzeitigen Takten) und ein Teilindex zum Lesen.
- **Dienst** `services/loop.py`: `draft_problems` (in `validate_draft` und vor der Freigabe; nur
  am regulären Auftrag), `freeze`, `problem` (warum gerade kein Nachfolger: wartet ↔ geht nicht
  mehr), `due` (eine SQL-Abfrage), `create_next` (Entwurf als 1:1-Kopie → `orders.create_order` im
  Namen dessen, der eingeschaltet hat), `end` (nur am neuesten Auftrag), `view`, `todo_items`.
  FIFO über `consumption.free_numbers` (nur `Freigegeben`).
- **Takt**: Aufgabe `loop` in `tick.TASKS` (je Auftrag eigene Transaktion; ein Fehlschlag hält die
  übrigen nicht auf).
- **Zahlung**: dieselben Verben. Hatte der Vorgänger eine Zusage und gibt das Modul alle Preise
  vor, führt das System Anfrage und Zusage aus – still (`voucher_docs.quietly`, keine Mail) und
  festgehalten (`loop.agreed` mit Grundlage). Sonst bleibt der neue Beleg bei der Offerte. Die
  Offerte nennt die Wiederholung in den Konditionen.
- **«Zu tun»**: je wartendem oder unmöglichem Nachfolger ein Satz am neuesten Auftrag (rot, wenn
  es nie mehr geht).
- **Route** `POST /erp/orders/{id}/loop/end`; `OrderResponse.loop` (`LoopView`).
- **Oberfläche** `components/erp/loop-card.tsx`: im Entwurf ein leiser Knopf «Wiederholen» unter
  dem Ende, eingeschaltet die Karte (Takt · Ab · Bis · Nimmt); am laufenden Auftrag Punkt + Wort +
  Satz, die Zeilen, Vorher/Weiter in/Zusage aus und «Beenden» mit einer Rückfrage. Die Linie
  (`process-columns.LoopLine`) läuft links zurück zum Start, kräftig sobald es den Nachfolger gibt.

## Gemessen

- Backend: alle Tests grün (891), `ruff` sauber. Neu: `tests/test_wiederkehr.py` (Kalender, Anzahl/Datum,
  Entwurf und Einfrieren, nur regulär, Nachfolger nie doppelt, FIFO, verschrottet → nur Beenden,
  Beenden nur am neuesten, Anzahl beendet die Kette, Zahlung still mitgeführt, ohne Preis bleibt
  die Offerte, jeder Zustand hat Wort und Ton) und ein Spiegel-Wächter für Takte und Wahl.
- Gegenproben: ohne `quietly` schlägt der Zahlungstest an (eine Mail entstünde); ein falsches Wort
  in der Karte lässt den Spiegel-Wächter anschlagen.
- Frontend: `type-check`, `eslint .`, `npm test` (81), Build grün; Typen und `openapi.json` neu.
  Die Karte und die Linie sind nicht im Browser gemessen – zuerst auf `inexxio-dev` ansehen.

## Verworfen

- Eine eigene Tabelle für Schlaufen: die Einstellung ist ein Ereignis am Auftrag, der Zustand
  eine Ableitung – eine Tabelle wäre die zweite Wahrheit.
- `freeze` prüft nach der Freigabe nicht noch einmal: die gewählten Stücke stehen dann im eigenen
  Auftrag, die Prüfung «ist in Auftrag …» schlüge fälschlich an. Geprüft wird davor, mit derselben
  Funktion wie im Entwurf.
- Die Zustandswörter im Frontend: sie kommen fertig vom Server (`state_label`, `tone`).
