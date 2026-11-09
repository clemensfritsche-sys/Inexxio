# Änderungsakte – was entschieden ist, was umgesetzt wird, was offen ist

> **Der eine Ort für Entscheide des Inhabers.** Jeder Punkt hat eine Nummer, die bleibt. Ein
> Entscheid wird hier eingetragen, bevor oder während er umgesetzt wird; erledigt heisst: mit
> Commit. Grundlage: die Gesamtprüfung vom 09.11.2026 (`docs/history/2026-11-09-gesamtpruefung.md`).
> Grundsätze: funktioniert (robust) · so einfach wie möglich · so günstig wie möglich.

Stand: 09.11.2026

## 1. Entschieden: bleibt so

| Nr. | Thema | Entscheid |
|---|---|---|
| E1 | Gutschrift-Nummer (4a) | Bleibt am Beleg – dort sichert die Datenbank, dass keine Nummer doppelt vorkommt. |
| E2 | Lieferantenrechnung nach dem Buchen ersetzen (Befund F1) | Bleibt vorerst, wie es ist. |
| E3 | Arztzeugnis geht beim Nachreichen zur KI (Befund F3) | Bleibt so. |
| E4 | Umlagern und Inventur ohne Auftrag | **Bewusst nicht möglich.** Jede Bewegung eines Stücks geht durch einen Auftrag. |
| E5 | Eine E-Mail-Adresse je Person | Bleibt so. |
| E6 | Verlauf einer Firma wandert mit der Person, wenn sie die Stelle wechselt | Bleibt so. |
| E7 | Zwei-Faktor-Anmeldung für den Admin | **Bewusst nicht.** |
| E8 | Ausführen über MCP | Kommt später (siehe `docs/konzept/mcp.md`). |
| E9 | Ereignis-Verzeichnis für das Log | **Nicht gewünscht.** Im Log steht, was passiert ist – keine zusätzlichen Regeln. |
| E10 | Belege ohne Ware (Leistungs-Artikel, V5) | **Nicht umsetzen.** |
| E11 | Lohn-Export der Zeiterfassung | **Nicht gewünscht.** |
| E12 | Mengen in m/kg/l als «Gebinde mit Menge» (V4) | **Nicht umsetzen** – die Logik Instanz · Charge · Einzelinstanz (Menge immer 1) bleibt. |
| E13 | Handgriffe aus fremden Mails (V9) | **Bleibt, wie es ist** – keine Sonderlogik. |
| E14 | Klick-Tests der Oberfläche (V8b) | **Nicht gewünscht.** |

## 2. Freigegeben: wird umgesetzt

| Nr. | Thema | Was genau | Stand |
|---|---|---|---|
| U1 | MCP härten (F7) | Rückkehr-Adressen nur Claude (claude.ai, claude.com) und der eigene Rechner (Claude Code); Erneuerung genau einmal und an den Client gebunden, 30 Tage; jeder Zugang nennt Umgebung und Empfänger; die volle Rückkehr-Adresse steht auf «Claude verbinden». | erledigt (Migration 180) |
| U2 | KI-Kosten zählen immer (F8, Teil) | Jeder KI-Aufruf wird sofort für sich gespeichert – der Deckel sieht ihn auch, wenn das Gespräch danach abbricht; kein zweites Bezahlen ohne Zählen. | **zurückgestellt** – geht nur, wenn das unveränderliche Log ausserhalb der Antwort geschrieben wird; das ist nicht einfach und elegant (Bedingung des Inhabers). Das Risiko ist klein (nur wenn der Dienst mitten in einer Antwort stirbt). |
| U3 | Beträge (F10) | EIN Betrags-Leser für alles; nimmt «1'234.50», «1’234.50», «1 234,50». | erledigt (`domain/number`) |
| U4 | Kundendaten | Jede Person mit ERP-Zugang (Mitarbeitende, Admin) darf Kundendaten ändern. Rollen und die Daten von Mitarbeitenden bleiben beim Admin. | erledigt (`policy` `person.edit` · `person.staff`, `may_edit`) |
| U5 | Rechte an EINER Stelle | `domain/policy.py`: «darf diese Person das – und wenn nicht, warum?» Alle verstreuten Rollenprüfungen (≈60 in 20 Dateien) dorthin; ein Wächter verbietet neue daneben. Im Frontend kommt «darf» vom Server statt aus der Rolle. | erledigt (`domain/policy`, Wächter `test_policy`) |
| U6 | Fehler: EIN Modell, überall gleich | Eine Fehlerart in der Fachschicht (`Rejected`: nicht gefunden · nicht erlaubt · passt nicht · Konflikt), EIN Übersetzer in die Antwort, überall dieselbe Form `{code, message, field?}`; im Frontend EINE Anzeige. Keine Web-Ausnahmen mehr in `domain/`. | erledigt (`domain/errors`, Wächter `test_errors`) |
| U7 | Frontend lädt überall gleich | Die ~26 Stellen, die noch von Hand laden, gehen über React Query (Cache, Neu-Laden nach jeder Änderung, Fehlermeldung); ein Wächter verbietet das Laden von Hand. | erledigt (Wächter `scripts/queries.test.mjs`; Konto mit demselben Query-Client) |
| U8 | Ein Dialog-Baustein | Die sechs eigenen Dialoge (Anmelden, Scannen, «+», Passkey-Hinweis, Rückkehr vom Link, `controls.Dialog`) auf EINEN Baustein (Fokus, Escape, Hintergrund). | erledigt (`lib/use-dialog.ts`, Wächter `scripts/dialog.test.mjs`) |
| U9 | Grosse Dateien teilen | Ohne Verhaltensänderung: `voucher_actions.py` (1'339 Zeilen) nach Stufen; die Logik aus `routers/orders.py` (962) in einen Dienst; `mailbox.py` (938) in Abgleich und Senden. | erledigt (Beleg in `voucher_rules` · `voucher_input` · `voucher_offer` · `voucher_billing` · `voucher_actions`; Auftragsansicht in `services/order_view` (Router 962 → 581 Zeilen); `mail_parse` aus `mailbox`) |
| U10 | Browser-Schutzregeln (CSP) | Was gefahrlos geht: kein `unsafe-eval`, keine Platzhalter-Domains (`*.a.run.app`, `*.googleapis.com`) – nur die genauen Adressen. | erledigt, soweit gefahrlos (genaue Google-Adressen, der eigene Dienst statt `*.a.run.app`); `unsafe-inline`/`unsafe-eval` bleiben – Next-Export, Google Maps und der Scanner brauchen sie, ohne Test im Browser nicht entfernbar |
| U11 | Prod-Backup | Vor dem Go-live: Point-in-Time-Recovery auf Prod einschalten, eine Rückspiel-Probe; der Deploy prüft, dass es an ist. | offen – bei Go-live |
| U12 | Ferien im unbezahlten Urlaub (V2) | Ein freier Tag mitten in einem ganztägigen unbezahlten Urlaub baut keine Ferien auf (`timekeeping._accrues`, `covering`). | erledigt |
| U13 | Mails nie doppelt, nie verloren (V3) | Kennung = die eigene Nummer der Mail im ERP (`Message-ID`, `mailbox.own_message_id`); vor jedem Senden fragt Gmail danach (`rfc822msgid:`). Dasselbe Postfach neu verbunden macht weiter, wo es aufhörte; ist Gmails Stand zu alt, kommen alle Mails seit dem letzten Abgleich, seitenweise. | erledigt |
| U14 | Rechnungsdatum (F9) | Unsere Rechnung trägt immer den Tag, an dem sie gestellt wird; nur eine Lieferantenrechnung trägt das Datum auf ihrem Papier. | erledigt |
| U15 | Eine Meldestelle (V7) | `core/report.py`: `info` · `warn` · `error`, eine JSON-Zeile mit Stufe; auch `logging` geht dorthin. Mail bei ERROR: einmal `infra/setup-meldungen.sh PROJEKT EMAIL`. | erledigt (Mail-Alarm: Skript einmal ausführen) |
| U16 | Dienstleistung an Private im Ausland (V1) | Dritter 0-%-Satz «Nicht im Inland steuerbar» (Vermerk MWSTG Art. 8 Abs. 1). Geht die Rechnung an eine **Firma** im Ausland: Reverse Charge mit ihrer MWST-Nr.; an eine **Privatperson**: nicht im Inland steuerbar, ohne Nummer (`vo.vat_choices(business=…)`, `voucher_head.recipient_business`). | erledigt |
| U17 | 7-Tage-Regel für alles und alle | Kein Stempel, keine Absenz, keine Buchung, kein Vertrag, kein Feiertag älter als 7 Tage – auch nicht durch den Admin (`domain/timekeeping.closed`). Ein Vertrag ändert sich nur durch einen neuen Vertrag; die Vergangenheit korrigiert eine Buchung im offenen Zeitraum. Ein Nachweis lässt sich jederzeit nachreichen (er ändert keine Zahl). | erledigt |
| U18 | Frontend schneller laden (V8a) | Die Detailansichten und das «+» laden erst beim Öffnen (`next/dynamic`): beim Öffnen des ERP 1'468 → 1'024 KB JavaScript. | erledigt |

## 3. Vorschläge: Entscheid offen

### V1 – Dienstleistung an Privatkunden im Ausland (F2)
**Recht:** Eine Dienstleistung gilt dort als erbracht, wo der **Empfänger** seinen Sitz oder
Wohnort hat (MWSTG Art. 8 Abs. 1, «Empfängerortsprinzip») – für Firmen **und** Privatpersonen
(Ausnahmen Art. 8 Abs. 2, z. B. Arbeiten an einem Grundstück: dort, wo es liegt). Ist der
Empfänger im Ausland, ist die Leistung **in der Schweiz nicht steuerbar**: 0 %, mit Vermerk.
«Reverse Charge» (der Empfänger rechnet die Steuer selbst ab) gibt es nur bei **Firmen**; nur
dort braucht es seine MWST-Nummer. Eine Privatperson hat keine – heute lässt sich ihre Rechnung
darum nicht stellen. (Reparaturen an einer Maschine sind nach Schweizer Recht übrigens eine
**Lieferung**, MWSTG Art. 3 Bst. d – sie folgen dem Ort der Ware, nicht dieser Regel.)
**Vorschlag (klein):** ein Satz mehr im Katalog: «Nicht im Inland steuerbar» (0 %, Vermerk
«Ort der Leistung im Ausland, MWSTG Art. 8 Abs. 1»). Bei einer Dienstleistung ins Ausland
wählt das System selbst: **mit** MWST-Nr. der Gegenpartei → Reverse Charge, **ohne** → nicht im
Inland steuerbar. Die MWST-Nr. ist nur noch beim Reverse Charge Pflicht (wie heute).

### V2 – Ferien laufen im unbezahlten Urlaub am Wochenende weiter (F4)
**Was passiert:** Ferien wachsen jeden Kalendertag um 1/365 des Jahresanspruchs. An einem Tag
mit unbezahltem Urlaub wird dieser Anteil gekürzt – aber nur an Arbeitstagen; Samstag und
Sonntag mitten im Urlaub wachsen voll weiter (rund 2/7 zu viel).
**Vorschlag (klein):** Ein Kalendertag, der **innerhalb** eines ganztägigen unbezahlten Urlaubs
liegt (vom ersten bis zum letzten Tag), wächst nicht – auch am Wochenende. Ein halber Tag
unbezahlt kürzt wie heute nur diesen Tag.

### V3 – Mails: nie doppelt, nie verloren (F5, F6)
**Doppelt:** Heute wird erst gesendet, dann gespeichert. Stirbt der Dienst genau dazwischen,
sieht der nächste Abgleich «noch nicht gesendet» und schickt nochmals.
**Vorschlag:** Jede Mail bekommt **vor** dem Senden ihre eigene, feste Kennung (Message-ID aus
ihrer Nummer), und wir merken uns «Senden begonnen». Findet der nächste Abgleich eine Mail mit
«begonnen», fragt er Gmail zuerst: «gibt es eine gesendete Mail mit dieser Kennung?» – ja →
als gesendet vermerken, nein → senden. So geht jede Mail höchstens einmal hinaus.
**Verloren beim Neu-Verbinden:** Wird dasselbe Postfach neu verbunden, macht der Abgleich dort
weiter, wo der alte aufhörte (statt «ab jetzt»). Ist Gmails Stand zu alt, holt er alles seit dem
letzten Abgleich, seitenweise (statt nur 2 Tage / 200).

### V4 – Mengen in m, kg, l (und warum 10'000 Schrauben 40'000 Log-Zeilen machen)
Siehe **Abschnitt 5**. Entscheid: Ansatz «Gebinde mit Menge» ja/nein.

### V5 – Geld: Belege ohne Ware (Miete, Versicherung, eigene Dienstleistungen)
**Heute:** Jeder Auftrag bewegt Stücke; ein Beleg ganz ohne Ware geht nicht.
**Vorschlag (ohne die Grundregel zu brechen):** ein **Leistungs-Artikel** – ein Artikel mit
der Eigenschaft «Leistung» (Miete Halle, Versicherung, Montagestunde, Serviceeinsatz). Ein
Auftrag **erzeugt** davon ein Stück, das Zahlungsmodul rechnet es ab, und am Ziel wird es
«Erbracht» (endgültig, kein Bestand) statt «Freigegeben». Dazu:
- Monatsmiete = derselbe Auftrag mit **Wiederholung** (gibt es schon) – jeden Monat von selbst.
- Die Lieferantenrechnung nimmt **mehrere Steuersätze** (je Satz ein Betrag), wie unsere
  eigene Rechnung es schon kann.
- Nichts Neues an Prozess, Beleg, Log: nur eine Eigenschaft am Artikel und ein Zustand.

### V6 – Zeiterfassung: Monatsabschluss und Lohn
**Problem heute:** Alles wird ab dem ersten Vertrag neu gerechnet. Wer rückwirkend einen
Vertrag, einen Feiertag oder ein Geburtsdatum ändert, ändert still schon bezahlte Monate.
**Vorschlag – so sollte es laufen:**
1. Bis zum 7. des Folgemonats kann jede Person ihren Monat noch korrigieren (7-Tage-Regel gilt
   schon).
2. Danach **schliesst der Admin den Monat ab** (ein Knopf, für alle). Das System friert je
   Person die Zahlen ein: Soll, Ist, Saldo, Ferien, Absenzen, Überzeit – als Eintrag, der sich
   nie mehr ändert.
3. Ein abgeschlossener Monat ändert sich nie mehr. Rückwirkendes (Vertrag, Feiertag) wirkt erst
   ab dem ersten offenen Monat; eine Korrektur ist eine **Buchung im laufenden Monat** (gibt es
   schon).
4. **Lohn-Export:** pro abgeschlossenen Monat eine Datei (CSV) für die Lohnbuchhaltung.
5. **Überzeit** (ArG: über 45 bzw. 50 h/Woche, höchstens 170 h im Jahr) wird getrennt von den
   Überstunden gezählt und im Abschluss mitgeführt.
Nebeneffekt: die Berechnung beginnt beim letzten Abschluss – schnell, auch nach Jahren.

### V7 – Eine Meldestelle für den Betrieb («Warnungen mit Schweregrad»)
**Worum es geht:** nicht um Meldungen auf dem Bildschirm, sondern um das, was der Dienst
**für den Betreiber** notiert («Gmail nicht erreichbar», «Takt gescheitert»). Heute 28-mal von
Hand geschrieben, ohne Stufe – Google kann daraus keinen Alarm machen.
**Vorschlag:** EINE Stelle (`core/report.py`) für jede solche Meldung, mit Stufe (Info ·
Warnung · Fehler); bei «Fehler» schickt Google eine Mail (wie heute beim Takt). Entscheid:
ja/nein.

### V8 – Frontend: ein Paket von 2,2 MB, keine Klick-Tests
Siehe Abschnitt 4 (Erklärung). Vorschlag: (a) schwere Teile erst laden, wenn man sie öffnet;
(b) 5–8 automatische Klick-Tests gegen Dev. Entscheid: ja/nein je Teil.

### V9 – KI: Handgriffe aus fremden Mails
Siehe Abschnitt 4 (Erklärung). Vorschlag: (a) der Probelauf eines Handgriffs aus einer Mail
läuft mit den Rechten «jedes Personal», nicht des Admins; (b) die Karte zeigt deutlich «aus einer
Mail von aussen» und die echte Handlung (Pfad, Werte) neben dem Satz der KI; (c) Geld bewegen und
etwas hinausschicken wird aus Mails nie vorbereitet; (d) die KI darf nicht mehr selbst
ausführen – nur die Person per Knopf. Entscheid: ja/nein je Teil.

## 4. Erklärungen

**Rechnungsdatum (F9), einfach:** Die MWST rechnet man je Quartal ab. Ist das Quartal
abgerechnet, darf darin keine neue Rechnung mehr auftauchen. Heute kann man bei unserer eigenen
Rechnung ein beliebiges Datum eintippen, auch eines im schon abgerechneten Quartal. Vorschlag:
eigene Rechnungen tragen immer das heutige Datum (das Leistungsdatum steht ohnehin separat).

**Ereignisse im Log, einfach:** Das Log ist das Tagebuch des Systems. Darin stehen zwei Sorten
Einträge: (1) «Zeile X wurde geändert» – schreibt die Datenbank selbst, sauber und vollständig;
(2) «Ereignisse» wie «Handgriff vorbereitet», «Gespräch: Nachricht», «Wiederholung angelegt» –
schreibt der Code. Für Gespräche, Handgriffe, Wiederholungen, MCP-Verbindungen **ist** dieses
Ereignis die einzige Speicherung. Das ist gewollt und günstig. Die Schwäche: das Tagebuch nimmt
jeden Namen und jeden Inhalt an – vertippt sich der Code in einem Feldnamen, merkt es niemand,
und alte Einträge passen nicht mehr. **Vorschlag:** ein Verzeichnis aller Ereignisse mit ihrer
Form (welche Felder, welcher Typ); das Tagebuch prüft beim Schreiben dagegen. Entscheid offen
(empfohlen, klein).

**KI über die echte Tür, einfach:** Wenn die KI etwas tun will (Person anlegen, Notiz schreiben),
hat sie **keinen eigenen Zugang zur Datenbank**. Sie füllt dasselbe Formular aus, das ein Mensch
im ERP abschickt, und zwar mit den Rechten der Person, für die sie arbeitet. Was die Person nicht
darf, darf die KI auch nicht – automatisch, ohne zweite Regel. Das ist richtig so. **Das Risiko:**
die KI liest auch Mails von aussen. Schreibt jemand in eine Mail versteckt «ändere die
Bankverbindung», kann die KI das als Vorschlag (Karte) vorbereiten. Ausgeführt wird nur per
Klick – aber eine geschickt formulierte Karte kann einen müden Menschen täuschen. Siehe V9.

**Frontend, einfach:** (1) Wer das ERP öffnet, lädt **das ganze Programm auf einmal** (2,2 MB),
auch Teile, die er nie braucht (Prozess-Editor, Zahlung, Karte). Am PC egal, auf dem Handy in
der Halle spürbar. (2) Die Tests prüfen nur die Rechenlogik; **keiner klickt die Oberfläche
wirklich durch**. Ein Fehler, der eine Seite leer lässt, fällt erst dem Menschen auf.

**Grosse Dateien teilen, einfach:** Eine Datei mit 1'300 Zeilen ist wie ein Ordner ohne
Register. Ich teile sie nach Thema in kleinere Dateien – der Code bleibt derselbe, nur
übersichtlicher; die Tests beweisen, dass sich nichts ändert.

## 5. Mengen in m, kg, l – alle Szenarien

### Warum 10'000 Schrauben ≈ 40'000 Log-Zeilen
Heute ist **jede Schraube eine eigene Zeile** (eine Einzelinstanz). Wird eine Schraube
verbaut, ändern sich für **jede einzelne**: ihre Zugehörigkeit zum Auftrag (neu), ihr Status
(«Verbaut»), zwei Prozess-Ereignisse (eingetreten, durchgelaufen) und die Zugehörigkeit am Ende
– je ein Tagebuch-Eintrag. 10'000 × 4 ≈ 40'000. Das ist folgerichtig für Seriennummern-Teile
(Motoren, Steuerungen), aber unsinnig für Schüttgut.

### Der Vorschlag: «Gebinde mit Menge»
- **Stückartikel** (Seriennummer, `kind = einzeln`): bleiben **genau wie heute** – ein Stück =
  eine Zeile, Menge immer 1.
- **Chargenartikel** (`kind = batch`: Schrauben, Stangen, Blech, Kabel, Öl): eine Einzelinstanz
  ist ein **Gebinde** und trägt eine **Menge** in der Einheit des Artikels (Stk, m, kg, l), mit
  bis zu 3 Nachkommastellen. Eine Kiste mit 10'000 Schrauben = **1 Zeile** mit Menge 10'000.
- **Teilen statt Zählen:** Wird nur ein Teil gebraucht, entsteht aus dem Gebinde ein neues
  Gebinde mit genau dieser Menge (eigene Nummer `<Instanz>-<n+1>`); der Rest behält seine
  Nummer und Menge minus Teil. Das abgeteilte Gebinde ist ein ganz normales Arbeitsobjekt.
  → Die Einzelinstanz-Regel bleibt: **im Prozess wird nur mit Einzelinstanzen gearbeitet.**
- **Bestand** = Summe der Mengen (statt Anzahl Zeilen). Ein Stückartikel hat Menge 1 je Zeile –
  dieselbe Rechnung für beide.

### Szenarien
| # | Szenario | Heute | Mit «Gebinde mit Menge» |
|---|---|---|---|
| 1 | Wareneingang 3 Stangen à 6 m | 3 Stück, Länge unbekannt | 3 Gebinde à 6.000 m (oder 1 Gebinde 18 m, wie geliefert) |
| 2 | Wareneingang 10'000 Schrauben | 10'000 Zeilen | 1 Gebinde, Menge 10'000 Stk |
| 3 | Verbrauch 2.35 m Stange je Produkt | geht nicht | Teilen: 2.35 m werden ein eigenes Gebinde und «Verbaut» im Produkt; die Stange hat noch 3.65 m |
| 4 | Verbrauch 4 Schrauben je Produkt | 4 Zeilen ändern sich (×4 Log) | Teilen: 1 Gebinde à 4 Stk wird «Verbaut»; Kiste −4 |
| 5 | Bedarf grösser als ein Gebinde (5 m, Stange hat 3.65) | – | zwei Teile aus zwei Gebinden (FIFO), beide im Produkt vermerkt |
| 6 | Reststück 0.12 m | – | bleibt ein Gebinde mit 0.12 m; verschrotten mit Modul «Aussondern» (wie heute) |
| 7 | Verkauf 10 m Kabel | 10 «Stück»? | Zahlungsmodul: Position 10 m × Preis/m; beim Start des Auftrags werden 10 m abgeteilt |
| 8 | Prüfung (Datenerfassung) an einer Charge | 1 Scan je Instanz | unverändert – gescannt wird die Instanz |
| 9 | Bewegen eines Teils (5 kg aus einem 25-kg-Sack) | – | Auftrag mit Bewegen über 5 kg: 5 kg werden abgeteilt und bewegt (E4: nur über Auftrag) |
| 10 | Schwund/Messdifferenz (Sack hat 24.6 statt 25 kg) | – | Abweichungs-Auftrag mit Datenerfassung «Ist-Menge»; Differenz abteilen und aussondern – nachvollziehbar, nie still |
| 11 | Stückliste eines Produkts (Genealogie) | Zeile je Schraube | «4 Stk Schrauben aus Kiste 100000123-1», «2.35 m aus Stange …-2» – genauer als heute |
| 12 | Wiederholung (Abo) mit Material | wie heute | unverändert – die Menge steht in der Zeile |
| 13 | Preise | je Stück | je Einheit (CHF/m, CHF/kg); Betrag = Menge × Preis, gerundet auf Rappen |
| 14 | Verschrotten eines ganzen Gebindes | – | wie heute ein Stück |

### Was sich am Code ändert (ehrlich)
- Datenbank: `instance_units.amount` (Dezimalzahl, leer = 1), `order_lines.quantity` und die
  Mengen in der Stückliste (Verbrauch) werden Dezimalzahlen. Eine Migration, kein Datenverlust
  (heutige Zahlen bleiben gültig).
- **Der grosse Teil:** überall, wo heute «Anzahl Zeilen = Menge» gezählt wird (Bestand,
  Positionen im Beleg, Fortschritt im Prozessbild, Stichprobe, Verbrauch, FIFO), wird zu
  «Summe der Mengen». Das sind viele Stellen, aber jede ist gleich einfach. Tests über alle
  Szenarien oben vorher notiert (Matrix), dann umgebaut.
- **Teilen** ist EINE neue Schreibstelle (`instances.split`), sonst nichts Neues.
- Aufwand: gross (L), Risiko: mittel – weil Mengen überall vorkommen. Empfehlung: in einer
  eigenen Runde, mit der Szenario-Matrix zuerst.

### Was es nicht löst (bewusst)
Kein Umrechnen zwischen Einheiten (kg ↔ m) – ein Artikel hat genau eine Einheit. Keine
Reservierung (Material wird erst beim Erreichen des Moduls genommen, wie heute).

## 6. Aufräumen – Gesamtdurchsicht 09.11.2026 (Entscheid offen)

Gemessen mit `backend/scripts/deadcode.py` und drei unabhängigen Durchsichten (Schema, Backend,
Frontend); die wichtigsten Funde von Hand nachgeprüft. Entscheide E1–E14 nicht neu aufgerollt.

### A – Datenbank (klein, sicher)
- **A1 Tote Spalten**: `captures.note` (nie gelesen, nie geschrieben) ·
  `process_steps.source_article_id` (nur geschrieben) · `webauthn_credentials.transports`,
  `device_type` · `attachments.width`, `height` (niemand liest sie) · `log_seal.sealed_at` (prüfen).
  Zwei-Deploy-Regel.
- **A2 Doppelte Indizes**: `ix_vouchers_step_id` (neben `uq_vouchers_step`) ·
  `ix_time_contracts_person_object_id` · `ix_instance_units_instance_id` (je Anfang eines anderen) ·
  `ix_log_actor_at` (jede Abfrage filtert auch `event`). Weniger Schreibarbeit am Log.
- **A3 Kopie statt Ableitung**: `mailboxes.address` (die Adresse IST die Kontakt-E-Mail der
  Gesellschaft; Rest der persönlichen Postfächer in `mailbox.address_of`).
- **A4 (gross, nur prüfen)**: `article_process_steps` und `process_steps` haben dieselbe Form;
  `webauthn_challenges` könnte signiert werden wie MCP (ohne Tabelle). Nutzen klein → **nicht empfohlen**.

### B – Backend
- **B1 Eine Typ-Tabelle** «Typ → Tabelle, Wort» (heute an drei Stellen: `objects`, `ai_tools`,
  `records`); Namen auflösen über die Nummern-Registry statt sechs Abfragen.
- **B2 Die KI liest nur über die echten Routen** (`ai_tools.record` gibt heute rohe Spalten mit
  einer Ausschlussliste aus – eine neue Spalte ginge ungefragt an die KI). Datenschutz.
- **B3 Ein Zahlen-Leser**: `capture_types/measure._number` eigener Leser (`1'250` scheitert) →
  `domain/number`.
- **B4 Rechte ganz in `policy`**: `core/auth.require_role` prüft daneben; Literal `"admin"` an 3 Stellen.
- **B5 Sperren an einer Stelle** (`core/locks`: Verzeichnis der Schlüssel, eine API; heute 6
  magische Zahlen in 5 Dateien, 2 Arten).
- **B6 Zeit an einer Stelle**: `core/clock.utcnow()` (heute 4× `_now`, 22× `datetime.now`),
  ein `dd.mm.yyyy` statt 9× `strftime`.
- **B7 Reste**: unbenutzter Parameter `timekeeping.locked(actor)` · Altschlüssel in
  `core/signed` (Frist, dann `LINK_SECRET` Pflicht) · falsche Docstrings (`sites.operator`,
  `articles`) · `contact.py`: Prüfung und Telefon-Regel in den Dienst · Dateinamen
  `document.py`→`paper.py`, `records.py`→`record_labels.py` · KI-Kosten als `Decimal`.
- **B8 Imports oben, Schichten-Wächter** (domain → nichts, models → domain, services → models);
  ~160 Imports in Funktionen, echte Zyklen nur zwei.
- **B9 (gross)**: Beleg je Anfrage einmal laden, dann rein rechnen – der Lese-Cache mit globalen
  Listenern fällt weg.

### C – Frontend
- **C1 Tot**: `module-ui.Actions`, CSS `.btn-primary`, `.erp-partyrow`.
- **C2 Eine Handlung = `useAction`** überall (heute ~20× eigenes `busy` + `.catch`); Netzfehler als
  eigene Art statt Textvergleich.
- **C3 Ein Baustein je Muster**: Popover (5× von Hand), Pflicht-Label (3 Fassungen, 3 Farben),
  Vollbild-Blätter ohne `useDialog` (Entwurf, Scanner: kein Escape), Zeilen, `'—'` 25× als Text.
- **C4 `lib/api.ts` aus den Typen** (`openapi-fetch`): ~70 % der 1117 Zeilen fallen weg, Body und
  Antwort werden geprüft.
- **C5 Quelltext-Tests** (4'822 Zeilen Python lesen TSX per Text) → Spiegel generieren wie den
  Status-Katalog, Formregeln in ESLint.
- **C6 (gross, schrittweise)**: Stile – 1'037 Inline-Stile neben Klassen; grosse Bauteile
  (Composer, «+», Artikel) in Hook + Ansicht teilen.

### Empfehlung
Runde 1 (klein, sicher): A1, A2, A3, B3, B4, B6, B7, C1, C2, C3. Runde 2: B1, B2, B5, B8, C4, C5.
Später/nur bei Bedarf: B9, C6. Nicht: A4.
