# Projektakte «Sortiment» – Produkte, Shop, Seriennummer, Ersatzteile

> **Kopfstatus:** Fassung 2 · **Konzept, Runde 1b** (9 Entscheide, §6) · Lead: Claude · Entscheid:
> Clemens Fritsche · seit 12.11.2026 · zuletzt 14.11.2026
> Bild (Website und ERP, wie es damit aussieht – Nachbau aus dem echten CSS, klickbar):
> https://claude.ai/artifact/MHpch5gZnxsAGKWLoVHFLA
> Diese Akte ist die **eine** Quelle für Ziel, Themen, Vorschläge, Entscheide und Plan des Projekts.
> Was hier nicht als **entschieden** steht, ist nicht entschieden. Das Bild zeigt, die Akte hält fest.
> Vorgänger: `docs/backlog.md` «Shop» · `docs/attic.md` «Verkauf und Shop» (alter Anlauf, entfernt
> August 2026) · `docs/history/2026-09-13-konzept-beleg-shop-besitz.md` (Frage 1) ·
> `docs/konzept/wiederkehr.md` (Abo) · `website/WEBSITE_PLAN.md` Entscheid 127 (Symbol rechts im Kopf,
> «Meine Produkte» im Konto).

## 0 · Die ganze Idee in acht Sätzen (Fassung 2)

1. **Verkauft wird der Artikel – mit einer Karte «Verkauf».** Kein neuer Objekttyp. Der Artikel bleibt
   in dem, was er *ist* (Spezifikation, Prozess), unveränderlich; die Karte «Verkauf» sagt, wie wir ihn
   *anbieten* (Texte, Bilder, Optionen, Preise, Wege, für wen), und ist jederzeit änderbar – wie
   Dokumente und Notizen heute schon am Artikel hängen, ohne ihn zu ändern. **Die Karte gehört der
   Artikel-Kette:** ersetzt ein neuer Artikel den alten, trägt er dieselbe Karte, von selbst.
2. **Eine Bestellung ist eine Offerte, die der Kunde annimmt.** Im Shop macht das System die Offerte
   aus der Wahl des Kunden, und «Bestellen» ist die Zusage. Beim Kran macht ein Mensch die Offerte –
   als Artikel mit Karte «Verkauf» **nur für diese Firma** –, und der Kunde bestellt ihn auf derselben
   Seite. Ein Ort für jede Bestellung: Shop und Projekt sehen gleich aus.
3. **Jede Bestellung ist ein Auftrag mit einem Zahlungsmodul und einer Lieferung.** Den Ablauf baut
   das System aus einer kleinen Regel: Ware (ab Lager oder neu erzeugt) + Lieferart (Paket, Abholen,
   Spedition, Montage) → Modul-Liste. Keine Vorlage je Produkt, keine Handarbeit.
4. **Vorauszahlung ist EINE Zahl** (0 % = Rechnung, 30 % = Anzahlung, 100 % = Vorauszahlung) am einen
   Zahlungsmodul – nie zwei Einnahme-Module. Standard der Gesellschaft, bekannte Kunden haben ihre
   eigene Zahl (Kondition am Partner).
5. **Was zusammen bestellt wird, geht zusammen.** Ein Korb für alles; angeboten werden nur Lieferarten,
   die jede Position erlaubt (Funk zum Kran fährt auf dem Tieflader mit).
6. **Ein Preis gilt je Markt**, vom ERP vorgeschlagen, vom Menschen gesetzt; darunter Kunden- und
   Firmenpreise (Kaskade Markt → Partner → Vorgang).
7. **Die Seriennummer ist eine Tür** – für jede Instanz, nicht nur die Maschine: Kran, Motor, Schlauch.
   Der QR trägt eine Adresse mit der Nummer; die Nummer ist das Wesentliche, die Adresse nur der Weg.
8. **Ersatzteile kommen aus dem, was wirklich verbaut ist**, in allen Stufen. Bestellbar ist, was eine
   Karte «Verkauf» hat; alles andere ist mit einem Klick angefragt.

## 1 · Problem und Ziel

**Heute:** Die Website zeigt Leistungen und einen handgepflegten Teile-Katalog
(`website/src/config/catalog.mjs`, «ohne Preis, ohne Warenkorb», `PartCatalog.astro`). Am Artikel
gibt es keinen Verkaufspreis, keinen Text, kein Bild, kein «öffentlich» (`models/article.py`). Ein
Auftrag kann nur vom Personal angelegt werden (`routers/orders.py:247`). Der QR-Code auf dem Etikett
trägt nur die nackte Nummer (`frontend/src/lib/scan.ts:13`), eine öffentliche Seite dazu gibt es nicht.
Die Stückliste eines Geräts kennt das ERP – aber nur das Personal sieht sie.

**Ziel:** Was INEXXIO verkauft, vermietet oder im Abo anbietet, steht **einmal im ERP** und erscheint
überall richtig – auf der Website, bei Google, im Konto des Kunden, auf dem QR-Code der Maschine. Ein
Kunde bestellt in so wenigen Klicks wie möglich; ein Besitzer findet sein Ersatzteil in Sekunden.

**Erfolg messen wir ohne Statistik-Cookies** (Leitbild): an Aufträgen aus dem Shop, Klicks bis zur
Bestellung (gezählt am Server, nie am Menschen), Anfragen aus der Geräteseite.

## 2 · Grundsätze (aus dem Leitbild abgeleitet, zum Bestätigen)

- **ERP ist Master.** Website, Feed, Konto sind Spiegel. Gepflegt wird nur im ERP.
- **Eine Sache, eine Stelle.** Ein Preis steht an genau einer Stelle; ein Text an genau einer.
- **Ableitung statt Spalte.** Verfügbar, Lieferzeit, «neu», «ausverkauft», «Nachfolger» – alles
  gerechnet, nie gesetzt.
- **Bestellung = Auftrag.** Kein zweites Modell für Shop-Bestellungen, kein Warenkorb im ERP.
- **Nichts entsteht ohne Entscheid eines Menschen** – im Shop ist der Mensch der Kunde: sein Klick
  «Bestellen» ist die Freigabe des Auftrags und die Zusage der Offerte.
- **Die KI bereitet vor, der Mensch gibt frei** – auch für Texte, Übersetzungen und Bilder.
- **So einfach, robust und günstig wie möglich** – kein Shop-System von aussen (Shopify & Co.), kein
  zweiter Server, keine Suchmaschine, solange es ohne geht.

## 3 · Was es heute schon gibt (Anknüpfungspunkte, gemessen am Code 12.11.2026)

| Was | Wo | Bedeutung für den Shop |
|---|---|---|
| Artikel mit Spezifikation, Ersetzen statt Ändern | `models/article.py`, `services/articles.py` | Technik und Lebenszyklus stehen; Text/Bild/Preis fehlen |
| Bestand je Stück, nie gespeichert | `services/instances.article_states` | «ab Lager» rechenbar; «verkaufbar jetzt» fehlt noch als Funktion |
| Auftrag in einem Aufruf, mit Wiederholung und Datum | `orders.create_order`, `domain/loop.py`, `domain/order_date.py` | Bestellung, Abo, Liefertermin «bis» |
| Zahlungsmodul komplett (Offerte → Zusage → Rechnung, MWST, Incoterms, Karte, QR, Mahnung, Gutschrift) | `domain/voucher.py`, `services/voucher*.py` | Herz des Checkouts – bereit |
| Preise als Vorgabe im Modul | `Beleg.PRICES`, `voucher_head.preset_prices` | gleiche Idee wie eine Preisliste, nur am falschen Ort |
| Stille Zusage ohne Mensch | `loop.agreed` (`services/loop.py:317`) | Vorbild: der Klick des Kunden ist die Zusage |
| Eigentum «geht an die Partei ↔ an uns» | `voucher.sold_units` | Kauf ↔ **Miete** ist genau diese Wahl |
| Stückliste je Gerät | `services/genealogy` (eine Stufe) | Ersatzteil-Baum, digitaler Zwilling |
| Seriennummer auf jedem Papier | `voucher.serials_of` | «Sie haben Seriennummer X gekauft» |
| Dokumente mit Referenz an Artikel/Instanz | `services/documents.py`, `DocumentRef` | Anleitung, Konformität – öffentlich fehlt |
| Dokumentseite für Kunden (annehmen, ablehnen, bezahlen) | `/dokument`, `routers/public_documents.py` | Zahlen nach der Bestellung |
| Anmeldung Magic Link · Google · Passkey, Adressbuch | `core/auth`, `services/address_book.py` | Bestellen ohne Passwort |
| Firma per UID, Dublette unmöglich | `services/sites.resolve` | B2B-Bestellung mit Firma |
| Gesellschaft je Land | `sites.company_for_country` | Markt ↔ verkaufende Gesellschaft |
| Teile-Katalog «1:1 aus dem ERP vorbereitet» | `website/src/config/catalog.mjs` | erste Produkte, sofort |
| Kunden lesen eigene Aufträge (API, ohne Oberfläche) | `routers/orders.py:64-83` | Konto «Meine Bestellungen» |
| Vertex AI (Gemini) über eine Tür | `services/ai.py` | Bild-Aufbereitung, Übersetzung |
| `cad_url` am Artikel | `models/article.py` | einziger Ansatz zu 3D |

**Was fehlt** (Lücken, alle vor oder neben dem Beleg): Produkt (Inhalt, Sichtbarkeit) · Preis je Markt
· Konditionen je Partner · Verkaufsweg (Ablauf-Vorlage) · Bestellen durch den Kunden (Recht + Route) ·
Herkunft am Auftrag gegen Doppelbestellung (`source_reference`) · öffentliche Dokumente · öffentliche
Geräteseite · Stückliste in allen Stufen · gespeicherte Karte (für Abo/Miete) · Versandkosten als
Position · Katalog-Feed.

## 4 · Themenkarte – alles, was wir durchgehen müssen

Jedes Thema bekommt eine Nummer, die bleibt. Status: **offen** · **Vorschlag** (Claude hat einen) ·
**entschieden** (mit Datum) · **später** (bewusst nicht jetzt). Reihenfolge der Bearbeitung: §7.

### A · Grundmodell
| Nr. | Thema | Status |
|---|---|---|
| A1 | Name des Projekts und der Dinge | **entschieden** E1 |
| A2 | Produkt ↔ Artikel: eigenes Objekt oder Karte am Artikel | Vorschlag neu (§5 F2): Karte «Verkauf» |
| A3 | Ein Produkt = ein Artikel, oder Varianten/Optionen (Konfigurator) | Vorschlag (§5 F3) |
| A4 | Zubehör, Sets, «passt zu», «oft zusammen» | offen |
| A5 | Kategorien und Navigation | **entschieden** E2 (Stichworte) |
| A6 | Sichtbarkeit | E7 + Vorschlag neu (§5 F5): aus · für alle · nur für |
| A7 | Lebenszyklus: Entwurf · veröffentlicht · auslaufend · ersetzt · zurückgezogen | Vorschlag (§5 F6) |
| A8 | Ersatzartikel / Nachfolger | **entschieden** E8 |
| A9 | Produkte ohne Ware: Dienstleistung, Service-Abo, Prüfung, Software (INEXXIO 365) | offen – berührt Entscheid E10 |

### B · Inhalt und Darstellung
| Nr. | Thema | Status |
|---|---|---|
| B1 | Texte: Titel, Satz, Beschreibung, Vorteile, technische Daten (aus der Spezifikation) | Vorschlag |
| B2 | Bilder: Upload, **einheitliche Aufbereitung durch die KI** (Licht, Hintergrund), Original bleibt | Vorschlag (§5 F7) |
| B3 | Bildsprache / Kampagne («Feuer und Eis» – eigener Look) | offen |
| B4 | Video (wie heute: MP4 + Standbild) | Vorschlag: wie Website |
| B5 | 3D-Ansicht: Onshape live oder Export (glTF) und selbst zeigen | Vorschlag (§5 F8) |
| B6 | Dokumente: Anleitung, Konformitätserklärung, Zertifikate, Datenblatt, Prüfberichte | Vorschlag (§5 F9) |
| B7 | Sprachen | **entschieden** E3; Weg: §5 F21 |
| B8 | Bewertungen, Referenzen, «im Einsatz bei» | später |

### C · Preise und Märkte
| Nr. | Thema | Status |
|---|---|---|
| C1 | Listenpreis am Produkt, mit «gültig ab» (Preisänderung ohne Löschen) | Vorschlag (§5 F10) |
| C2 | Märkte: Land → Gesellschaft, Währung, Preis (Kaufkraft) | Vorschlag (§5 F10) |
| C3 | Automatischer Vorschlag je Markt (Kaufkraft-Faktor, Kurs) – nie automatisch gesetzt | Vorschlag |
| C4 | Kunden-/Firmenpreise, Rabatt, Staffel (Menge), Projektpreis | Vorschlag: Kaskade |
| C5 | Aktionen, Gutscheincodes | später |
| C6 | Anzeige: Privat brutto inkl. MWST (Preisbekanntgabeverordnung), Firma netto | Vorschlag |
| C7 | «Preis auf Anfrage» (Grossanlage) → Konfigurieren, dann Offerte von Hand | Vorschlag |
| C8 | Rundung je Markt (CHF auf .–, EUR auf ,00) | offen |

### D · Angebotsformen
| Nr. | Thema | Status |
|---|---|---|
| D1 | Kaufen (Eigentum geht an die Partei) | Vorschlag – gibt es schon |
| D2 | Mieten (Eigentum bleibt bei uns, Wiederholung je Monat, Rückgabe) | Vorschlag (§5 F11) |
| D3 | Abo: Produkt (Lieferung je Takt) · Service/Prüfung · Software | Vorschlag – Wiederholung gibt es |
| D4 | Anzahlung, Teilzahlung, Raten | offen – Teilbetrag gibt es |
| D5 | Leasing über Dritte | später |

### E · Verfügbarkeit und Lieferzeit
| Nr. | Thema | Status |
|---|---|---|
| E1 | «ab Lager» ↔ «auf Bestellung» ↔ «auf Anfrage» – abgeleitet aus Bestand und Erzeugungsprozess | Vorschlag |
| E2 | Lieferzeit: Lager → Versandtage; sonst Fertigungszeit (zuerst Feld, später aus dem Log gelernt) | Vorschlag |
| E3 | Letztes Stück, zwei Käufer gleichzeitig (es gibt keine Reservierung) | Vorschlag (§5 F12) |
| E4 | Anzeige «noch 3 an Lager»? (Ehrlichkeit vs. Konkurrenz sieht mit) | offen |

### F · Bestellweg (Checkout)
| Nr. | Thema | Status |
|---|---|---|
| F1 | Klicks: Produkt → Wählen → Bestellen → Kontakt/Adresse → Bezahlen → fertig | Vorschlag (Bild) |
| F2 | Ohne Konto bestellen | **entschieden** E5 |
| F3 | Firma oder privat (UID erkennt die Firma) | Vorschlag |
| F4 | Zahlungsarten; wer darf auf Rechnung? | Vorschlag (§5 F19) |
| F5 | Warenkorb | Vorschlag neu (§5 F13): ein Korb, eine Lieferung |
| F6 | Doppelklick, Netzabbruch → nie zwei Aufträge (`source_reference`) | Vorschlag |
| F7 | Bestätigung: Seite + Mail + Auftragsbestätigung (Papier, wie heute «Prüfen und freigeben»?) | offen |

### G · Der Auftrag im ERP
| Nr. | Thema | Status |
|---|---|---|
| G1 | Wer legt den Ablauf fest? | Vorschlag (§5 F20): Ware + Lieferart |
| G2 | Versand: Paket, Spedition (Ausgabe als zweites Zahlungsmodul), Abholung, Montage | Vorschlag |
| G3 | Versandkosten als Position auf der Rechnung | offen – Code-Frage (Positionen ohne Stück) |
| G4 | Liefertermin = Datum «bis» am Auftrag (gibt es) | Vorschlag |
| G5 | Teillieferung | offen |
| G6 | Aufgaben: wer packt, wer prüft (Kompetenzen gibt es) | Vorschlag – geschenkt |

### H · Nach dem Kauf
| Nr. | Thema | Status |
|---|---|---|
| H1 | Konto: «Meine Bestellungen» (Stand, Papiere, Bezahlen) | Vorschlag |
| H2 | Konto: «Meine Geräte» (alles, was mir gehört – mit Seriennummer) | Vorschlag |
| H3 | Storno vor Lieferung (Wort «Stornieren» gibt es) | Vorschlag |
| H4 | Widerruf 14 Tage (EU-Privatkunden Pflicht, Schweiz nicht) | offen – Recht |
| H5 | Retoure, Garantie, Reklamation (Retoure «an uns» gibt es im Modell) | offen |
| H6 | Service buchen, Prüfung fällig (Wiederholung) | später |

### I · Seriennummer, QR, digitaler Zwilling, Ersatzteile
| Nr. | Thema | Status |
|---|---|---|
| I1 | QR-Code mit Adresse statt nackter Nummer (scannt im ERP weiter) | Vorschlag (§5 F15) |
| I2 | Öffentliche Geräteseite: was jeder sieht, was nur der Besitzer sieht | Vorschlag (§5 F15) |
| I3 | Nummer erraten (Nummern sind fortlaufend) | Vorschlag (§5 F15) |
| I4 | QR auch auf Baugruppen (Motor, Steuerung) – Liebherr-Muster | Vorschlag |
| I5 | Teilebaum: alle Stufen (heute eine), Baugruppe ↔ Einzelteil wählbar | Vorschlag (§5 F16) |
| I6 | Digitaler Zwilling in 3D: Teil im Modell anklicken | Vorschlag (§5 F8, F16) |
| I7 | Teil bestellen ↔ anfragen (mit Gerät und Teil vorausgefüllt) | Vorschlag |
| I8 | Intern: Monteur scannt im Service dasselbe | Vorschlag – dieselbe Seite |
| I9 | Zugekaufte Komponenten ohne Stückliste (z. B. Motor eines Lieferanten) | offen |

### J · Recht
| Nr. | Thema | Status |
|---|---|---|
| J1 | AGB: Shop-Klauseln (Vertragsschluss, Lieferung, Gewährleistung, Miete, Abo) | offen |
| J2 | Preisbekanntgabeverordnung (CH): Endpreis inkl. MWST für Private | Vorschlag |
| J3 | Widerruf, Geoblocking, Verbraucherrecht für EU-Kunden | offen |
| J4 | Maschinenverordnung (EU) 2023/1230 ab 20.01.2027: Anleitung darf digital sein (QR!) | Vorschlag – Chance |
| J5 | CE / Konformitätserklärung je Seriennummer | offen |
| J6 | Export, Zoll (gibt es im Beleg), Sanktionen | offen |
| J7 | Datenschutz: kein Tracking, Konto ohne Zwang | Vorschlag – Leitbild |

### K · Gefunden werden (SEO, Marketing)
| Nr. | Thema | Status |
|---|---|---|
| K1 | Jede Produktseite statisch, schnell, mit eigener Adresse | Vorschlag (§5 F17) |
| K2 | Strukturierte Daten (Product, Offer, Preis, Verfügbarkeit) | Vorschlag |
| K3 | Google Merchant Center (Shopping) aus dem Feed | Vorschlag |
| K4 | Newsletter «neu im Sortiment» (gibt es) | später |
| K5 | Ratgeber-Artikel verlinken Produkte | Vorschlag |

### L · Kanäle und Schnittstelle
| Nr. | Thema | Status |
|---|---|---|
| L1 | **Ein Katalog-Feed** (öffentlich, JSON + XML) als einzige Schnittstelle nach aussen | Vorschlag (§5 F17) |
| L2 | Amazon, Galaxus, Händlerportal | später – liest denselben Feed |
| L3 | GS1-Nummern (GTIN) – nötig für Amazon/Google bei Handelsware | offen |
| L4 | Händler-/Wiederverkäufer-Preise | später |

### M · Betrieb
| Nr. | Thema | Status |
|---|---|---|
| M1 | Wer pflegt Produkte (Recht in `policy`), Freigabe «veröffentlichen» | Vorschlag |
| M2 | KI-Hilfe: Text, Übersetzung, Bild – je als Vorschlag am Produkt | Vorschlag |
| M3 | Kosten: Bilder-KI je Bild, Feed, Speicher | offen – messen |
| M4 | Aufgaben: «Produkt ohne Bild», «Preis fehlt im Markt», «Dokument fehlt» | Vorschlag |

## 5 · Vorschläge (Fassung 2 – nach der Rückmeldung vom 14.11.2026)

> Was entschieden ist, steht in §6. Hier steht, was offen ist, mit Begründung und Alternative.

### F2 neu – Verkauf am Artikel, nicht als eigenes Produkt

**Vorher** (Fassung 1): eigenes Objekt «Produkt». **Jetzt:** eine Karte **«Verkauf»** am Artikel.

Warum der Wechsel:
- **Ersatzteile:** jedes der rund 1'000 Teile wird mit einem Schalter verkäuflich, ohne 1'000 zweite
  Datensätze.
- **Nachfolger von selbst:** die Artikel-Kette (`replaces_object_id` → `replaced_by_id`) gibt es schon.
  Die Karte gehört der **Kette**, nicht dem einzelnen Glied: der neue Artikel zeigt sofort dieselbe
  Karte, Adresse und Google-Platz bleiben.
- **Optionen gehen trotzdem:** eine Option ist ein Verweis auf einen anderen Artikel (siehe F3) – dafür
  braucht es kein eigenes Objekt.
- **Kein Widerspruch zu «ein Artikel wird nicht geändert»:** unveränderlich ist, was der Artikel *ist*
  (Spezifikation, Erzeugungsprozess). Was wir mit ihm *tun* (lagern, dokumentieren, verkaufen), hängt
  an ihm und ändert sich – Bestand, Dokumente und Notizen tun das heute schon.

Was es kostet: der Satz in CLAUDE.md wird genauer («Spezifikation und Prozess eines Artikels werden
nicht mehr geändert; seine Karte «Verkauf» schon»). Ein Produkt ohne eigenen Artikel (z. B. ein Set)
ist ein Artikel, der seine Teile verbraucht – wie heute jede Baugruppe.

*Alternative:* eigenes Objekt «Produkt» (Fassung 1) – nur nötig, wenn ein Angebot mehrere *gleichrangige*
Artikel bündeln müsste. Das haben wir nicht gefunden.

### F3 – Optionen sind Artikel (bestätigt die Richtung)

Die Karte «Verkauf» eines Artikels hat Gruppen von Optionen; jede Option zeigt auf einen Artikel mit
Preis (Fangbremse, Speziallackierung, 2. Akku). Zwei Arten, die das System am Artikel erkennt:
- **Beilage** (der Artikel ist ein eigenes Stück, z. B. Funk-Sender): wird eine eigene Zeile des Auftrags.
- **Einbau** (geht in die Maschine, z. B. Fangbremse): verlangt, dass die Maschine erst gebaut wird –
  das ist ein **Projekt**: ein eigener Artikel je Kran (wie heute), mit der Option in seiner Stückliste.
  Der Kunde wählt die Optionen, ein Mensch macht daraus den Kran-Artikel und gibt ihn «nur für» den
  Kunden frei (F18).

### F5 neu – Sichtbarkeit in drei Zuständen

**Aus** (nicht verkauft) · **Für alle** · **Nur für …** (eine Liste aus Personen und Firmen). Eine Firma
in der Liste → alle ihre Personen sehen es; eine Person → nur sie. Kein «nur angemeldet», kein «intern»
(deine Rückmeldung). «Nur für» ist nie bei Google und nie im Feed.

**Besserer Preis für einen Kunden auf einem öffentlichen Produkt:** kein Code, sondern eine **Kondition
am Partner** (Kaskade): «Hof Brunner: 10 % auf alles» oder «Hof Brunner: Funk-Set 2'200». Ist der Kunde
angemeldet, sieht er seinen Preis; bestellt er als Gast mit derselben E-Mail, gilt er auch. Rabattcodes
(Marketing) bleiben später (C5).

### F13 neu – ein Korb, eine Lieferung

- **Ein Korb für alles** (Maschine, Funk, Schrauben). Er lebt im Browser, bis «Bestellen» ihn zu
  **einem** Auftrag macht.
- **Was zusammen bestellt wird, geht zusammen.** Jede Position sagt in ihrer Karte, welche Lieferarten
  sie erlaubt (Schraube: Paket, Abholen; Kran: Spedition, Abholen, Montage). Angeboten wird die
  **Schnittmenge**. Ist sie leer, schlägt die Seite vor: «Teile vorab separat senden?» → zwei Aufträge.
- Damit gilt immer: **eine Bestellung = ein Auftrag = ein Beleg = eine Rechnung.**

### F18 neu – Eine Bestellung ist eine angenommene Offerte (der Kern)

Der Kunde sieht **nie einen Prozess**, nur sein Geschäft: Offerte → Zusage → (Anzahlung) → Lieferung →
Rechnung → bezahlt. Genau das kann das Zahlungsmodul heute schon (`offer → agreed → billed`).

| | Shop (Teile, Funk) | Projekt (Kran) |
|---|---|---|
| Wer macht die Offerte? | das System, aus Wahl + Preisliste | ein Mensch: Kran-Artikel + Karte «Verkauf» **nur für** Hof Brunner |
| Wo sieht es der Kunde? | Produktseite | **dieselbe** Produktseite, «Für Sie» |
| Was ist «Bestellen»? | Zusage (Verb `agree`) | Zusage (Verb `agree`) |
| Danach | Seite «Ihre Bestellung» | Seite «Ihre Bestellung» |

**Eine Seite je Bestellung** («Ihre Bestellung»): Stand, Papiere (AB, Rechnung), Bezahlen,
Seriennummern, später «Meine Geräte». Sie ist die Weiterentwicklung der heutigen Seite `/dokument` mit
ihren Stationen (`components/beleg/stations.tsx`) – **kein zweiter Ort**: der Link in der Mail
(ohne Anmeldung) und das Konto zeigen dieselbe Seite. Damit gibt es **einen Ort der Interaktion**.

### F19 neu – Vorauszahlung ist EINE Zahl

Heute: Vorauszahlung = Zahlungsfrist 0 Tage (`PREPAID_DAYS`), die Stücke laufen erst bei Saldo 0.
**Neu:** eine Zahl «Vorauszahlung in %» am Zahlungsmodul. Die Stücke passieren die Zahlung, wenn
zugesagt **und** dieser Anteil bezahlt ist (`process.carry_on` – die eine Stelle). 0 % = auf Rechnung,
30 % = Anzahlung, 100 % = Vorauszahlung. Den Rest zeigt die Rechnung wie heute (Teilbetrag gibt es).

Woher die Zahl kommt (Kaskade): **Gesellschaft** (Standard, Vorschlag 100 % für Neukunden) →
**Partner** (bekannte Firma: 0 %, 30 Tage) → **Karte «Verkauf»** (Maschine: mindestens 30 %). Das
beantwortet O4 ohne Sonderregel: *neu zahlt voraus, bekannt per Rechnung* – entschieden wird es am
Partner, nicht «ab der zweiten Bestellung».

### F20 neu – Wie der Ablauf entsteht (die kleine Regel)

Das System baut die Modul-Liste aus zwei Dingen:

1. **Woher kommt die Ware?** ab Lager → sie steht am Anfang. **Neu erzeugt** → zuerst der
   Erzeugungsprozess des Artikels, dann der Rest.
2. **Welche Lieferart?** Jede Lieferart ist eine kurze Modul-Folge, **einmal im ERP gepflegt** (an der
   Gesellschaft):

| Lieferart | Modul-Folge nach der Ware |
|---|---|
| Paket | Zahlung (Einnahme) → Bewegen (Ziel: Kunde) |
| Abholen | Zahlung (Einnahme) → Bewegen (Ziel: Kunde, Scan bei der Übergabe) |
| Spedition | Zahlung (Einnahme) → Zahlung (Ausgabe, Spediteur) → Bewegen |
| Montage | Zahlung (Einnahme) → Bewegen → Datenerfassung (Prüfung, Protokoll) |

**Befund im Code (muss gebaut werden):** ein Auftrag mit «Neu»-Zeile übernimmt heute den
Erzeugungsprozess des Artikels **unverändert** (`services/release.py:141`, `steps_for`) – eine Lieferung
lässt sich nicht anhängen. Vorschlag: **Neu = Erzeugungsprozess + Lieferart**; Stücke ab Lager in
derselben Bestellung **treten bei der Lieferart ein** (wie Komponenten heute am Verbrauch eintreten,
`process._enter_at_step`). Der Beleg entsteht wie heute bei der Freigabe – die Zusage (und Anzahlung)
gilt also ab dem ersten Tag, die Stücke passieren die Zahlung, wenn sie gebaut sind.

Spediteur: dessen Preis kennt bei der Bestellung niemand – das zweite Zahlungsmodul wartet als Aufgabe
«Spedition einkaufen» (Kompetenz Verrechnen). Der Kunde merkt davon nichts.

### F15 neu – QR: Adresse mit Nummer, eigene Etiketten-Adresse

Deine Sorge (Domain ändert sich – es ist ja schon einmal passiert: HS Steiner → INEXXIO) ist berechtigt.
Die robuste Lösung, wie sie Liebherr, Caterpillar und der Standard «GS1 Digital Link» machen:

- Der QR trägt **eine Adresse, in der die Nummer steht** (z. B. `https://<etikett>/100482117`).
- **Intern hängt nichts an der Adresse:** der ERP-Scanner liest jede 9-stellige Nummer aus jedem Text
  heraus (`frontend/src/lib/scan.ts` – heute schon so). Fällt die Adresse weg, funktioniert der Scan im
  ERP weiter.
- **Für Kunden** braucht es die Adresse: eine nackte Nummer öffnet mit der Handy-Kamera **nichts**.
- **Eine eigene, kurze Etiketten-Adresse**, die nur dafür da ist und nie aufgegeben wird (eine Domain
  kostet rund 20 CHF im Jahr) – unabhängig vom Firmennamen. Wechselt einmal die Website, leitet sie
  weiter.
- Unter dem QR steht die **Nummer als Text** – lesbar, abtippbar, auch in 30 Jahren.

**Jede Instanz kann ein Etikett tragen** (Kran, Motor, Steuerung, Schlauch-Charge) – das Modell kann es
schon: jede Instanz hat eine Objektnummer. Die Geräteseite eines Motors zeigt «verbaut in Kran 100 482
117» (`genealogy.built_into`), die des Krans seine Teile.

### F6 bestätigt mit deiner Ergänzung

Standard: der neue Artikel wird verkauft, der Rest des alten läuft **zuerst** aus (FIFO über die Kette
nimmt das älteste Stück). Soll sofort umgestellt werden: den Restbestand **sperren** (Aussondern
«Sperren» gibt es). Keine neue Funktion.

### F21 neu – Übersetzung ist eine Ableitung

Jedes Produkt in jeder Sprache der Website, ohne Sprachfeld in der Oberfläche (dein Entscheid). Gepflegt
wird **Deutsch**; die anderen Sprachen schreibt die KI beim Speichern und hält sie, bis sich der deutsche
Text ändert (Ableitung, gemerkt am Text). **Offen:** ohne Freigabe durch einen Menschen? Das wäre die
erste KI-Ausgabe, die ungeprüft hinausgeht – Vorschlag: ja, weil es nur übersetzt, nie erfindet; Fachwörter
hält eine kleine Wortliste je Sprache fest.

### Weiter gültig aus Fassung 1

F7 (Bilder: Original + KI-Fassung) · F8 (3D als Export aus Onshape) · F9 (Dokumente: am Artikel
öffentlich, an der Instanz für den Besitzer) · F10 (Preis je Markt mit «gültig ab») · F11 (Miete =
Eigentum «geht an uns» + Wiederholung) · F12 (letztes Stück ohne Reservierung) · F14 → aufgegangen in
F20 · F16 (Teilebaum in allen Stufen) · F17 (Seite statisch, Preis live, ein Feed).

## 6 · Entschieden

| Nr. | Entscheid | Datum |
|---|---|---|
| E1 | **Namen (F1):** Projekt «Sortiment», das Ding «Produkt», der Kauf «Bestellung», auf der Website «Produkte», kein «Shop» in der Oberfläche. | 14.11.2026 |
| E2 | **Kategorien als Stichworte (F4).** | 14.11.2026 |
| E3 | **Jedes Produkt in allen Sprachen der Website** – kein Sprachfeld in der Oberfläche. | 14.11.2026 |
| E4 | **Firmen und Private gleich** – keine Unterscheidung im Ablauf. | 14.11.2026 |
| E5 | **Bestellen ohne Anmeldung** (wie Coop Vitality); das Konto ist freiwillig. | 14.11.2026 |
| E6 | **Keine Priorisierung von Produkten (O1)** – es muss für alles gehen: Teile, Zubehör, Maschinen, Projekte. | 14.11.2026 |
| E7 | **Sichtbarkeit:** kein Unterschied zwischen öffentlich und angemeldet, kein «intern». | 14.11.2026 |
| E8 | **Nachfolger (F6):** neuer Artikel wird verkauft, offene Aufträge behalten ihren, Rest läuft aus; sofort umstellen = Rest sperren. | 14.11.2026 |
| E9 | **Eine Stelle der Interaktion:** Shop und Projekt (Offerte, Bestätigung, Rechnung) laufen für den Kunden über denselben Produktebereich – nicht über verschiedene Stellen. | 14.11.2026 |

## 7 · Vorgehen – wie wir es definieren

Je Runde ein Block der Themenkarte: ich zeige ihn im **Bild**, du sagst, was gefällt, und entscheidest;
ich trage es in §6 ein. Gebaut wird erst, wenn eine Bau-Etappe ganz entschieden ist.

| Runde | Block | Stand |
|---|---|---|
| 1 | Grundmodell (A) und Bestellweg (F) | **1b läuft** – Fragen §8 |
| 2 | Preise und Märkte (C) | offen |
| 3 | Auftrag im ERP (G), Angebotsformen (D) | vorgezogen in F18–F20 |
| 4 | Seriennummer, QR, Ersatzteile, 3D (I) | F15 vorgezogen |
| 5 | Inhalte und Bilder (B) | offen |
| 6 | Nach dem Kauf (H), Recht (J) | offen |
| 7 | Gefunden werden, Kanäle (K, L), Betrieb (M) | offen |

**Bau-Etappen (Vorschlag):** 1 Katalog (Karte «Verkauf», Produktseiten, Anfragen) · 2 Bestellen
(Preis je Markt, Lieferarten, Neu + Lieferart, Vorauszahlung als Zahl, Seite «Ihre Bestellung») ·
3 Gerät (Etiketten-Adresse, Geräteseite, Teilebaum) · 4 Miete und Abo · 5 3D und Zwilling · 6 Kanäle.

## 8 · Offene Fragen an den Inhaber (Runde 1b)

- **N1** Verkauf als Karte am Artikel statt eigenem Produkt (F2 neu) – einverstanden?
- **N2** Eine Bestellung ist eine angenommene Offerte; eine Seite «Ihre Bestellung» für Shop und Projekt,
  aus der heutigen `/dokument`-Seite (F18) – einverstanden?
- **N3** Vorauszahlung als EINE Zahl, Standard 100 % für Neue, am Partner überschreibbar (F19)?
- **N4** Ein Korb, eine Lieferung, Schnittmenge der Lieferarten (F13 neu)?
- **N5** QR mit eigener kurzer Etiketten-Adresse + Nummer als Text (F15 neu)?
- **N6** Übersetzungen durch die KI ohne Freigabe (F21)?
- **N7** Sichtbarkeit «nur für»: Personen **und** Firmen wählbar (Firma = alle ihre Personen)?
- **O3** In welche Länder liefern wir? Wichtig für Markt, Währung, Recht. Vorschlag: wo kein Markt
  gepflegt ist, zeigt die Seite «Offerte anfordern» statt «Bestellen» – so geht es überall, ohne Risiko.
