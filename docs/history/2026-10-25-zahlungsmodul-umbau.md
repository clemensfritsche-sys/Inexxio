# 2026-10-25 · Umbau des Zahlungsmoduls

> Rundenbericht. Was jetzt gilt, steht in `PROCESS_CORE.md` §9.15s und in `CLAUDE.md`
> («Zahlung»). Ausgangsstand: develop `b6c4e91` (deployt). **Bewusst ohne
> Rückwärtskompatibilität**: Entwicklungsphase, alte Belege dürfen unbrauchbar werden.

## Ziel
Ein Zahlungsmodul, das ohne Erklärung bedienbar ist: die Leiste sagt immer, was als
Nächstes kommt, jedes Dokument sieht gleich aus, die Partei handelt selbst über einen Link.

## Was gebaut wurde
- **Datenmodell** (Migration `155`, Netze in `main.py`): Gültigkeit, Eigentum, eingefrorene
  Stücke (`unit_ids`), Fingerabdruck der Offerte (`offered_hash`), Gutschrift-Nummer aus
  Storno, Lieferantenrechnung (MWST-Nr., Foto, Abweichung), Ausfuhrnachweis; Teilbetrag,
  Text, Gewicht je Position; Art/Grund/Gegenbuchung/IBAN je Geld-Zeile mit Unique-Index auf
  der Referenz; Tabelle `voucher_documents`; `instance_units.owner_object_id`;
  `articles.is_service`. Die Stufe `done` wird auf `billed`/`agreed` abgebildet.
- **Logik** (`domain/voucher`, `services/voucher`): `situation` (die Leiste), `balance`
  (ein Saldo statt verstreuter Summen – behebt die doppelt gezählte Ausbuchung),
  `units_problem`, `vat_choices` nach Anschrift, `place_at_ours`, Mahnstufen, neue Verben
  (`writeoff`, `tip`, `reverse`, `remind`, `export`, `accept`, `ownership`), `revoke` als
  einziges Storno-Wort. Die Stücke passieren selbst (`process.advance_payments`).
- **Dokumente** (`services/document`, `services/voucher_docs`, `services/agb`): eine
  A4-Vorlage für Offerte, AB, Rechnung (mit QR-Zahlteil), Quittung, Stornierung, Gutschrift,
  Mahnung; eingefroren mit Token; AGB als Markdown je Fassung (`app/assets/agb/`); Mail mit
  dem Papier-Block (`mail_layout.Paper`).
- **Kundenseite** `/beleg?t=…` und `/agb` (öffentliche Routen `routers/beleg.py`).
- **Zahlungen-Liste** an Person und eigener Gesellschaft, Überfälliges in «zu tun».
- **Karte** im ERP neu (`components/erp/beleg/`), Modul-Vorgaben im Editor, Artikel
  «Ware ↔ Dienstleistung» bei der Anlage, «verkauft an …» im Prozessbild.

## Geprüft
- `tests/test_zahlung_ablauf.py`: 26 Abläufe von Anfang bis Ende (Einnahme, Ausgabe,
  Vorauszahlung, Storno vor/nach Rechnung, Teilbetrag, Ausland, Mahnung, Erstattung,
  Trinkgeld, Ausbuchung, Gegenbuchung, abweichende Lieferantenrechnung, Kundenseite).
- `tests/test_voucher_module.py` an das neue Verhalten angepasst (u. a. kein `unbill`, Storno
  mit Gutschrift, Erstattung erst nach Storno).
- Dokumente gerendert und angesehen (Rechnung mit QR-Zahlteil, Mahnung, Quittung,
  Offerten-Mail); korrigiert: doppeltes «z. H.», «CH»-Zeile im Inland, Platzhalter in den
  AGB, Überlappung langer Wörter mit dem Logo.

## AGB neu (Weisung 25.10.2026)
`app/assets/agb/2026-01-01.md` ist ganz neu geschrieben – auf INEXXIO zugeschnitten (Krane
nach Mass, Kranservice, Heukrananlagen, Fahrzeugtechnik, Speziallösungen) und auf den Ablauf
im System: verbindliche Offerte mit Gültigkeit, Annahme nur der aktuellen Fassung über den
Link, Mehrarbeit nur nach Zustimmung, Zahlungswege, Mahnung in bis zu drei Stufen, Lieferung
nach Incoterm, Abnahme mit Protokoll, ersetzte Teile, Zufriedenheitsgarantie, INEXXIO 365,
Gratis-Inspektion, Storno. **Kein Skonto; Mahngebühren nur allgemein, ohne Betrag.** Ein Teil
für Geschäftskunden, einer für Endkunden (Gewährleistung 2 Jahre neu / 1 Jahr gebraucht,
Gerichtsstand am Wohnsitz, Widerrufsrecht für EU-Fernabsatz). Eine rechtliche Durchsicht
durch eine Fachperson ist empfohlen.

## Verworfen
- PDF-Erzeugung auf dem Server: das eingefrorene HTML wird im Browser gedruckt.
- Mahngebühr und Verzugszins im System: nicht gebaut.
- Automatisches Setzen der Gutschrift-Bezugsrechnung: sie wird vorgeschlagen, gewählt wird
  von Hand.

## Offen
- Dokumente der Gegenseite (Lieferant stellt) werden nicht erzeugt, nur erfasst.
- Ohne verbundenes Postfach werden Mails nur erfasst, nicht gesendet.
