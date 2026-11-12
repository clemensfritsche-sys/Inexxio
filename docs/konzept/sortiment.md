# Projektakte «Sortiment» – Produkte, Shop, Seriennummer, Ersatzteile

> **Kopfstatus:** Fassung 1 · **Konzept, nichts entschieden** · Lead: Claude · Entscheid: Clemens
> Fritsche · seit 12.11.2026 · zuletzt 12.11.2026
> Bild (Website und ERP, wie es damit aussieht – Nachbau aus dem echten CSS, klickbar):
> https://claude.ai/artifact/MHpch5gZnxsAGKWLoVHFLA
> Diese Akte ist die **eine** Quelle für Ziel, Themen, Vorschläge, Entscheide und Plan des Projekts.
> Was hier nicht als **entschieden** steht, ist nicht entschieden. Das Bild zeigt, die Akte hält fest.
> Vorgänger: `docs/backlog.md` «Shop» · `docs/attic.md` «Verkauf und Shop» (alter Anlauf, entfernt
> August 2026) · `docs/history/2026-09-13-konzept-beleg-shop-besitz.md` (Frage 1) ·
> `docs/konzept/wiederkehr.md` (Abo) · `website/WEBSITE_PLAN.md` Entscheid 127 (Symbol rechts im Kopf,
> «Meine Produkte» im Konto).

## 0 · Die ganze Idee in sieben Sätzen (Vorschlag)

1. **Ein Produkt ist das Gesicht eines Artikels nach aussen.** Der Artikel bleibt, wie er ist
   (technisch, unveränderlich); das Produkt trägt, was der Kunde sieht – Name, Texte, Bilder, Video,
   3D, Dokumente, Preis, Sichtbarkeit – und ist jederzeit änderbar. Wird der Artikel ersetzt, zeigt
   das Produkt **von selbst** auf den neuen. Adresse, Bilder und Google-Platz bleiben.
2. **Bestellen ist ein Klick auf einer Seite** (Muster Tesla): wählen, Preis und Liefertermin sehen,
   bestellen. Kein Warenkorb für ein einzelnes Produkt, kein Konto vorher, keine zehn Schritte.
3. **Jede Bestellung ist ein ganz gewöhnlicher Auftrag** mit einem Zahlungsmodul. Den Ablauf legt
   nicht der Kunde fest und nicht jedes Mal ein Mensch, sondern ein **Verkaufsweg**, einmal im ERP
   modelliert (z. B. «Paket», «Abholung», «Lieferung mit Montage»).
4. **Ein Preis gilt je Markt.** Ein Markt ist ein Land (oder eine Gruppe von Ländern) mit Währung und
   Preisliste; Kaufkraft heisst: jeder Markt hat seinen Preis, vom ERP vorgeschlagen, vom Menschen
   gesetzt. Darunter gelten Kunden- und Firmenkonditionen (Kaskade Markt → Partner → Vorgang).
5. **Die Seriennummer ist eine Tür.** Auf jeder Maschine ein QR-Code mit einer Adresse
   (`inexxio.ch/s/<Nummer>`): Scannen zeigt das Gerät – Anleitung, Konformität, Zertifikate, Service,
   Ersatzteile. Der Besitzer sieht dazu seine Geschichte.
6. **Ersatzteile kommen aus dem, was wirklich verbaut ist.** Das ERP weiss je Stück, welche
   Komponente in welches Produkt ging (`services/genealogy`). Daraus wird der Teilebaum des Geräts –
   als Liste und, wo ein 3D-Modell da ist, als anklickbares Modell (der digitale Zwilling).
   Bestellbar ist, was ein Produkt hat; alles andere ist mit einem Klick angefragt.
7. **Alles nach aussen ist ein Spiegel des ERP.** Website, Google, später Amazon oder ein
   Händlerportal lesen dieselbe eine Quelle (ein Katalog-Feed). Keine Angabe wird ausserhalb gepflegt.

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
| A1 | Name des Projekts und der Dinge (Sortiment, Produkt, Shop?) | Vorschlag (§5 F1) |
| A2 | Produkt ↔ Artikel: eigenes Objekt oder Felder am Artikel | Vorschlag (§5 F2) |
| A3 | Ein Produkt = ein Artikel, oder Varianten/Optionen (Konfigurator) | Vorschlag (§5 F3) |
| A4 | Zubehör, Sets, «passt zu», «oft zusammen» | offen |
| A5 | Kategorien und Navigation (wo ein Produkt erscheint – mehrfach!) | Vorschlag (§5 F4) |
| A6 | Sichtbarkeit: öffentlich · nur angemeldet · nur Firma X · nur Person Y · intern | Vorschlag (§5 F5) |
| A7 | Lebenszyklus: Entwurf · veröffentlicht · auslaufend · ersetzt · zurückgezogen | Vorschlag (§5 F6) |
| A8 | Ersatzartikel / Nachfolger (kleine Änderung = neuer Artikel) | Vorschlag (§5 F6) |
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
| B7 | Sprachen: DE · FR · IT · EN (Schweiz!), Übersetzung durch die KI, Freigabe Mensch | offen |
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
| F2 | Ohne Konto bestellen (Konto entsteht mit der E-Mail, Magic Link) | Vorschlag |
| F3 | Firma oder privat (UID erkennt die Firma) | Vorschlag |
| F4 | Zahlungsarten: Karte · TWINT · Rechnung (QR) · Vorauszahlung; wer darf auf Rechnung? | offen |
| F5 | Warenkorb: nur für Teile (mehrere Positionen), nie für Anlagen | Vorschlag (§5 F13) |
| F6 | Doppelklick, Netzabbruch → nie zwei Aufträge (`source_reference`) | Vorschlag |
| F7 | Bestätigung: Seite + Mail + Auftragsbestätigung (Papier, wie heute «Prüfen und freigeben»?) | offen |

### G · Der Auftrag im ERP
| Nr. | Thema | Status |
|---|---|---|
| G1 | Wer legt den Ablauf fest? → Verkaufsweg (Vorlage) | Vorschlag (§5 F14) |
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

## 5 · Vorschläge zu den grossen Fragen (zum Entscheiden)

> Jede Frage: was ich vorschlage, warum, was die Alternative kostet. Antwort genügt mit «ja» oder
> der Nummer der Alternative.

**F1 – Namen.** Projekt «Sortiment»; das Ding heisst **Produkt** (Artikel bleibt das technische Ding);
auf der Website der Bereich «Produkte»; der Kauf heisst **Bestellung** (im ERP: ein Auftrag). Kein
Wort «Shop» in der Oberfläche. *Alternative:* «Shop» überall – kürzer, aber klingt nach Ramsch und
passt nicht zu Kran und Miete.

**F2 – Produkt als eigenes Objekt, nicht am Artikel.** Der Artikel ist nach der Freigabe
unveränderlich (`routers/articles.py:163`, «es gibt kein Ändern»). Ein Tippfehler im Text dürfte
sonst keinen neuen Artikel erzwingen. Das Produkt hat eine Objektnummer, einen Verlauf, Autosave und
zeigt auf **eine Artikel-Kette**: es verkauft immer das neueste freigegebene Glied (`replaced_by_id`).
*Alternative:* Felder am Artikel (der alte Anlauf, `docs/attic.md`) – jede Textänderung wäre ein neuer
Artikel, und beim Ersetzen müsste alles kopiert werden.

**F3 – Varianten als Optionen aus Artikeln.** Ein Produkt hat einen Grundartikel und optional
Gruppen von Optionen; **jede Option ist ein Artikel** (Zeile im Auftrag) mit eigenem Preis, z. B.
«Funk: ohne · Standard · Proportional». Die Wahl des Kunden ergibt genau die **Zeilen des Auftrags**.
Abhängigkeiten («Greifer B nur mit Spannweite ≥ 12 m») als einfache Regel je Option. Für eine
Anlage nach Mass: Konfigurieren, dann «Offerte anfordern» statt «Bestellen» (C7).
*Alternative:* jede Kombination ein eigener Artikel – bei 3 × 4 × 3 Optionen 36 Artikel.

**F4 – Kategorien als Stichworte, nicht als Baum.** Ein Produkt trägt Stichworte («Krantechnik»,
«Heukran», «Fahrmischer», «Verschleissteil»); jede Seite der Website zeigt die Produkte zu ihrem
Stichwort. So erscheint ein Produkt an mehreren Stellen, ohne Kopie. Die Bereichsseiten bleiben, wie
sie sind, und bekommen einen Block «Produkte».

**F5 – Sichtbarkeit in vier Stufen:** öffentlich · für angemeldete Kunden · nur für bestimmte
Firmen/Personen («Für Sie», gleiche Seite, mit Hinweis «Ihr Produkt») · intern. Persönliche Produkte
werden nie von Google gefunden und nie im Feed ausgeliefert.

**F6 – Lebenszyklus abgeleitet.** Gespeichert ist nur «veröffentlicht ab» und «zurückgezogen ab».
Daraus und aus der Artikel-Kette folgt: Entwurf · neu (30 Tage) · im Sortiment · Nachfolger
verfügbar · ausverkauft (zurückgezogen, Rest ab Lager) · nicht mehr erhältlich. Wird der Artikel
ersetzt (z. B. eine Prüfung mehr im Erzeugungsprozess), verkauft das Produkt **ab sofort den
neuen** – offene Aufträge behalten ihren (sie sind eingefroren). Restbestand des alten kann
«ab Lager» weiter verkauft werden, bis er weg ist.

**F7 – Bilder: Original bleibt, die KI macht eine Fassung.** Hochladen → die KI (Gemini Bild, über
Vertex wie heute) erstellt eine Fassung im Hausstil (Licht, Hintergrund, Schnitt) → am Produkt
stehen Original und Fassung nebeneinander → ein Mensch wählt. Nie ein Teil erfinden: die KI darf
Licht und Umfeld ändern, nie die Maschine. Kosten grob wenige Rappen je Bild (zu messen, M3).

**F8 – 3D: Export statt Onshape live.** Aus Onshape einmal je Artikel ein glTF/GLB exportieren
(Onshape kann das), als Datei am Artikel ablegen, auf der Website mit einem freien Betrachter
(`<model-viewer>`, Google, frei) zeigen. Onshape live hiesse: Anmeldung, Kosten, Abhängigkeit,
langsam – und Kunden würden die Konstruktion sehen. **Der Trick für den Zwilling:** die Teile im
Onshape-Modell tragen als Namen ihre Artikelnummer; dann weiss die Seite, welches Teil im Modell zu
welchem Artikel gehört, und kann das Teil des konkreten Geräts markieren.

**F9 – Dokumente: ein Feld «öffentlich» am Dokument-Link.** Anleitung und Datenblatt hängen am
**Artikel** (gelten für alle Stücke), Konformitätserklärung und Prüfbericht an der **Instanz** (gelten
für genau dieses Gerät). Öffentlich ist nur, was ausdrücklich so markiert ist; Gerätedokumente sieht
nur der Besitzer. Mit der Maschinenverordnung 2027 darf die Anleitung digital sein – der QR-Code
ist dann der gesetzliche Weg zur Anleitung (Papier auf Wunsch).

**F10 – Preise: eine Preisliste je Markt, mit «gültig ab».** Ein Markt = Länder + Gesellschaft +
Währung. Je Produkt (bzw. je Option) und Markt ein Preis mit Datum; eine Erhöhung ist eine neue Zeile
ab Datum, nie ein Überschreiben. Für einen neuen Markt schlägt das ERP Preise vor (Hauspreis × Faktor
des Marktes × Kurs, gerundet), der Mensch übernimmt. Darunter die Kaskade Markt → Partner →
Vorgang. Die Preisvorgabe im Zahlungsmodul (`Beleg.PRICES`) liest künftig diese Liste.

**F11 – Miete ist Kauf mit «geht an uns».** Das Zahlungsmodul kennt die Wahl schon. Miete =
Auftrag mit Bewegen zum Kunden, Wiederholung je Monat (Rechnung), am Ende Bewegen zurück. Der
Kunde sieht dasselbe Interface mit dem Umschalter **Kaufen · Mieten · Abo** – wie Tesla «Kauf ·
Leasing». Dafür fehlt: Karte speichern (Stripe), damit die Monatsrate von selbst geht.

**F12 – Letztes Stück.** Keine Reservierung (bleibt). Wer bestellt, bekommt beim Anlegen des
Auftrags das älteste freie Stück (FIFO). Ist es im selben Moment weg, wird die Zeile «auf
Bestellung» und die Bestätigung nennt den neuen Termin – der Kunde kann dann stornieren.

**F13 – Warenkorb nur, wo er hilft.** Eine Maschine bestellt man einzeln (direkt «Bestellen»,
wie Tesla). Teile bestellt man oft zu mehreren – dort ein Korb, der **im Browser** lebt (wie der
Entwurf), bis «Bestellen» ihn zu **einem** Auftrag macht.

**F14 – Verkaufsweg als Vorlage.** Einmal im ERP modelliert, wie ein Erzeugungsprozess: eine
Modul-Liste (z. B. Zahlung → Bewegen [Versand] → Ende, oder Zahlung → Verbrauch [Montage] →
Bewegen → Ende), dazu die Lieferart, ihr Preis und die Zahlungsbedingungen. Das Produkt sagt, welche
Verkaufswege es erlaubt; der Kunde wählt die Lieferart, das System baut daraus den Auftrag.
*Offen dabei:* wo die Vorlage wohnt (an der Gesellschaft oder als eigener Datensatz).

**F15 – QR-Adresse und Geräteseite.** Neue Etiketten tragen `https://inexxio.ch/s/<Instanznummer>`
(der Scanner im ERP liest die Nummer heraus, `scan.ts` – alte Etiketten gehen weiter). Jeder sieht:
Produkt, Bild, öffentliche Dokumente, «Teil finden», «Service anfragen». Der Besitzer (angemeldet)
sieht zusätzlich: seine Papiere, Prüfberichte, Servicegeschichte. Gegen Durchprobieren der Nummern:
öffentlich steht nichts, was einem Fremden etwas über den Besitzer verrät. *Alternative:* ein
unerratbarer Zusatz im QR (sicherer, aber nicht mehr von Hand abtippbar).

**F16 – Teilebaum in allen Stufen, beides wählbar.** Der Baum folgt dem, was verbaut ist (Gerät →
Baugruppe → Teil). Der Kunde kann **jede Ebene** wählen: das ganze Fahrwerk oder nur die Rolle.
Bestellbar ist eine Ebene, wenn sie ein Produkt mit Preis hat; sonst «anfragen» mit Gerät und Teil
vorausgefüllt – nie eine Sackgasse. Mehrere Teile → Korb (F13).

**F17 – Website: Seite statisch, Preis live.** Die Produktseiten werden wie heute gebaut (schnell,
für Google lesbar). Preis, Verfügbarkeit und Lieferzeit holt die Seite beim Öffnen frisch aus dem
ERP (ein öffentlicher Katalog-Feed). «Veröffentlichen» im ERP stösst einen neuen Bau der Website an
(GitHub Actions, gratis). Derselbe Feed beliefert Google Shopping und später Amazon.
*Alternative:* jede Seite vom Server gerechnet – immer aktuell, aber zweite Darstellung neben Astro.

## 6 · Entschieden

*(noch nichts)*

## 7 · Vorgehen – wie wir es definieren

**Arbeitsweise:** je Runde ein Block der Themenkarte. Ich zeige ihn im **Bild** (Nachbau von Website
und ERP, klickbar), du schaust, sagst was gefällt und was nicht, und entscheidest die Fragen. Ich
trage Entscheide in §6 ein und ziehe Akte und Bild nach. Erst wenn alle Blöcke einer Bau-Etappe
entschieden sind, wird gebaut.

| Runde | Block | Im Bild |
|---|---|---|
| 1 | **Grundmodell** (A, F1–F6) und **Bestellweg** (F, F13) | Produktseite, Konfigurator, Bestellen, Produkt im ERP |
| 2 | **Preise und Märkte** (C, F10) | Preisliste im ERP, Seite im Markt DE/EUR |
| 3 | **Auftrag im ERP** (G, F14) und **Angebotsformen** (D, F11) | entstandener Auftrag, Verkaufsweg, Miete |
| 4 | **Seriennummer, QR, Ersatzteile, 3D** (I, F15, F16, F8) | Geräteseite, Teilebaum, Modell |
| 5 | **Inhalte und Bilder** (B, F7, F9) | Bild-Aufbereitung, Dokumente |
| 6 | **Nach dem Kauf** (H) und **Recht** (J) | Konto «Meine Bestellungen», «Meine Geräte» |
| 7 | **Gefunden werden, Kanäle** (K, L) und **Betrieb** (M) | Feed, Google-Vorschau |

**Bau-Etappen (Vorschlag, nach den Entscheiden zu bestätigen):**
1. **Katalog** – Produkt im ERP, öffentliche Produktseiten, Teile-Katalog aus dem ERP, Anfragen. Kein Preis nötig.
2. **Bestellen** – Preis je Markt, Verkaufsweg, Bestellen ohne Konto, Karte/QR, Konto «Meine Bestellungen».
3. **Gerät** – QR-Adresse, Geräteseite, Dokumente öffentlich, «Meine Geräte», Teilebaum, Teile bestellen.
4. **Miete und Abo** – Karte speichern, Wiederholung aus dem Shop.
5. **3D und Zwilling** – Modelle, anklickbare Teile.
6. **Kanäle** – Google Shopping, später weitere.

## 8 · Offene Fragen an den Inhaber (Runde 1)

Siehe §5 F1–F6 und F13. Dazu:
- **O1** Welche Produkte zuerst? (Vorschlag: die Verschleissteile Fahrmischer – sie sind schon
  vorbereitet, klein, oft gebraucht; dann Funk für Heukrane; Anlagen nach Mass nur «Offerte anfordern».)
- **O2** Verkaufen wir an Private oder nur an Firmen? (ändert Preisanzeige, Widerruf, AGB)
- **O3** In welche Länder liefern wir zuerst? (CH, LI, DE, AT?)
- **O4** Darf ein Neukunde auf Rechnung kaufen, oder nur Karte/Vorauszahlung?
