# Projektakte «Sortiment» – Produkte, Shop, Seriennummer, Ersatzteile

> **Kopfstatus:** Fassung 7 · **Konzept, Runde 1 – Abläufe** (35 Entscheide, §6) · Lead: Claude ·
> Entscheid: Clemens Fritsche · seit 12.11.2026 · zuletzt 14.11.2026
> Bild (Website und ERP, wie es damit aussieht – Nachbau aus dem echten CSS, klickbar):
> https://claude.ai/artifact/MHpch5gZnxsAGKWLoVHFLA
> Diese Akte ist die **eine** Quelle für Ziel, Themen, Vorschläge, Entscheide und Plan des Projekts.
> Was hier nicht als **entschieden** steht, ist nicht entschieden. Das Bild zeigt, die Akte hält fest.
> Vorgänger: `docs/backlog.md` «Shop» · `docs/attic.md` «Verkauf und Shop» (alter Anlauf, entfernt
> August 2026) · `docs/history/2026-09-13-konzept-beleg-shop-besitz.md` (Frage 1) ·
> `docs/konzept/wiederkehr.md` (Abo) · `website/WEBSITE_PLAN.md` Entscheid 127 (Symbol rechts im Kopf,
> «Meine Produkte» im Konto).

## 0 · Das grosse Bild (Fassung 5)

**Ein Weg für alles.** Was verkauft wird, ist ein Artikel mit Karte «Verkauf» – für alle oder nur für
einen Kunden (das Projekt). Der Korb ist der Entwurf; «Bestellen» gibt frei und sagt zu.

1. **Korb = Entwurf, im Browser.** Am Server gibt es vorher nichts.
2. **«Bestellen» = ein Klick.** Daraus entsteht **je Rhythmus ein Auftrag**: der Kauf einer, ein Abo oder
   eine Miete im selben Korb je ein eigener (mit Schlaufe). Jeder Auftrag hat seine Nummer = seine
   Bestellnummer; die Bestätigung nennt alle (wie Apple: Kauf-Nummer + AppleCare-Vertrag).
3. **Der Kunde tippt nur, was nur er weiss:** E-Mail, Name, Lieferadresse (Firma/UID freiwillig).
   Alles andere im Auftrag und im Zahlungsmodul kommt aus dem ERP (§5 F24).
4. **Eine Karte «Verkauf» geht erst auf «für alle», wenn sie vollständig ist** (Preis, Lieferart …). So
   trifft der Kunde nie auf eine Lücke (F29).
5. **Regeln hängen am Artikel, nie im Code** (E24): Transportgrösse, Lieferzeit, Anzahlung.
6. **Anzahlung = ein zweites Zahlungsmodul** vor dem Rest – wie im Kern schon entschieden (E22).
7. **Auf Bestellung – ohne Kern-Änderung** (F25 Fassung 7): Standard-Artikel → Nachschub + die Bestellung
   wartet eingefroren wie eine Wiederholung; Projekt-Artikel → ein Auftrag, dessen Erzeugungsprozess den
   Verkauf selbst enthält.
8. **Etikett:** QR mit Adresse `https://id.inexxio.com/<Nummer>` (F15, E32).

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

## 5 · Vorschläge (Fassung 7 – nach der sechsten Rückmeldung vom 14.11.2026)

> Neueste Fassung zuerst. Wo eine ältere Fassung derselben Nummer folgt, gilt die neuere.
> Die Abläufe zum Durchklicken: Bild, Ansicht «Abläufe».

### F25 Fassung 7 – «Auf Bestellung» ohne jede Kern-Änderung

Dein Einwand stimmt: ein Auftrag startet mit definierten Einzelinstanzen, gewählt wird nur Freigegebenes,
und ein Stück aus einem laufenden Auftrag zu greifen wäre eine Abweichung. Die Regel «mindestens ein
Stück am Start» bleibt (E34). Fassungen 5 und 6 sind verworfen.

**Die Lösung unterscheidet drei Lagen – jede nur mit Bestehendem:**

| Lage | Was beim «Bestellen» entsteht | Bestehende Logik |
|---|---|---|
| **An Lager** | der Verkaufs-Auftrag, sofort, Zeile «Lager» (FIFO) | Freigabe wie heute |
| **Standard-Artikel, nicht an Lager** | der **Nachschub** (Bauauftrag mit «Neu», unverändert) + die Bestellung als **eingefrorener Entwurf**; der Verkaufs-Auftrag entsteht **von selbst**, sobald die Ware frei ist | wie die Wiederholung: Entscheid im Voraus eingefroren, der Takt legt an, solange etwas fehlt, **wartet** er (`loop`); Zusage still wie `loop.agreed` |
| **Projekt-Artikel (nur für einen Kunden)** | **ein** Auftrag mit «Neu» – sein **Erzeugungsprozess enthält selbst** Anzahlung, Bau, Prüfung, Rest-Zahlung, Lieferung | «Neu» übernimmt den Prozess des Artikels (`release.steps_for`) – der Kran-Artikel ist ja nur für diesen einen Kunden, sein Prozess darf den Verkauf enthalten |

**Warum das sauber ist:**
- Kein Stück wird je «vorgemerkt», keines aus einem laufenden Auftrag gegriffen, keine Kern-Regel geändert.
- **Geld ohne Ware gibt es nicht** (E10): wer vorab zahlen soll (Anzahlung), hat ein Projekt – dort
  steht die Zahlung im Prozess vor dem Bau. Ein Standard-Artikel auf Bestellung wird bezahlt, wenn er da
  ist (Vorauszahlung vor dem Versand oder Rechnung).
- **Damit niemand dem Wartenden das Stück wegschnappt:** «verfügbar» ist für den Shop eine Ableitung –
  *frei minus, was wartenden Bestellungen versprochen ist*. Keine Reservierung, keine Spalte.
- Mehrere Positionen, eine davon nicht an Lager: die Bestellung wartet, bis **alle** frei sind
  (eine Lieferung, E11; Termin = späteste Position).

**Bestellnummer** (E19): beim Warten gibt es den Verkaufs-Auftrag noch nicht. Die Seite «Ihre Bestellung»
zeigt dann «in Herstellung» und den Bauauftrag; die Bestellnummer ist die Nummer des Verkaufs-Auftrags,
sobald er entsteht. *(Zu prüfen in Runde 3: ob der Kunde schon vorher eine Nummer braucht.)*

### F31 neu – Doppelklick und Netzabbruch: nie zwei Bestellungen

Gebaut wie der Wisch der Zeiterfassung (`timekeeping.swipe`: Idempotenz-Schlüssel) und die Mails
(`Message-ID` vor dem Senden):
1. Öffnet der Kunde «Bestellen», erzeugt der **Browser einen Schlüssel** für genau diesen Versuch.
2. Der Server legt den Auftrag **mit diesem Schlüssel** an – ein **eindeutiger Index** in der Datenbank.
3. Kommt derselbe Schlüssel nochmals (Doppelklick, Neuladen, Netz riss nach dem Speichern), legt der
   Server **nichts** an, sondern antwortet mit der schon bestehenden Bestellung.
4. **Stripe** bekommt denselben Schlüssel als `Idempotency-Key` – auch die Karte wird nie doppelt belastet;
   gebucht wird wie heute nur vom Webhook.
5. Ein Wächter-Test spielt es durch: zweimal derselbe Aufruf → ein Auftrag, eine Belastung.

### F32 neu – Produkt im Overlay, aber mit eigener Adresse

Deine Idee (Klick im Katalog öffnet ein leichtes Fenster statt einer neuen Seite) und die Adresse für
Google schliessen sich nicht aus – so machen es Airbnb und Instagram:
- Jedes Produkt hat **seine Seite** (`/produkte/funk-set-heukran`) – für Google, zum Teilen, zum direkten Öffnen.
- **Aus dem Katalog** öffnet sich dieselbe Seite als **Overlay** über dem Katalog; die Adresse oben
  wechselt mit. Schliessen = zurück zum Katalog, genau an dieselbe Stelle.
- Ein Inhalt, zwei Darstellungen – keine zweite Pflege.

### F25 Fassung 6 – «Auf Bestellung» mit der Logik, die es schon gibt

Deine Frage: «Ist ‹wartet auf den Bauauftrag› neu? Gibt es nicht schon eine Logik für Unterdeckung?»
**Ja, es gibt sie – beim Verbrauch.** Das «vorgemerkt»-Stück aus Fassung 5 wäre **neu** gewesen; das
Bestehende ist besser:

**Was heute schon da ist** (PROCESS_CORE §9.6, `services/consumption.py`, `process._enter_at_step`):
- Komponenten werden **nicht** bei der Freigabe gewählt. Sie **treten erst am Modul ein**, wenn es dran
  ist – aus dem freien Bestand, älteste zuerst (`StepNeed.plan`).
- **Nichtverfügbarkeit ist kein Zustand:** fehlt etwas, zeigt der Schritt «gebraucht 1 · verfügbar 0»
  und wartet; keine Aufgabe, solange nichts da ist.
- Das System **bietet an**: «Nachschub» (ein Auftrag, der es herstellt oder einkauft) oder «Holen lassen».
  Der Termin wird als «bis» vorgeschlagen.

**Dieselbe Logik für den Verkauf:**
1. Die Ware einer Bestellung tritt **am ersten Modul des Verkaufs-Auftrags** ein (dem
   Zahlungsmodul) – ab Lager sofort, sonst, **sobald sie frei ist**.
2. Fehlt sie: das Modul zeigt «gebraucht 1 · verfügbar 0» – und beim Bestellen wird der **Nachschub**
   gleich mit angelegt (der Bauauftrag, unverändert, wie heute aus «Nachschub»). Der Klick des Kunden ist
   der Entscheid dafür.
3. Ist der Kran gebaut, wird er Freigegeben (Lager) und **tritt von selbst ein** – wie eine Komponente.

**Eine Logik für alle Unterdeckungen** – Material in der Produktion wie Ware im Verkauf.

| Fall | Folge (alles bestehendes Verhalten) |
|---|---|
| Bau verzögert | Schritt wartet, Termin folgt dem Datum des Bauauftrags |
| Kran verschrottet | wieder «verfügbar 0» → Nachschub wird angeboten |
| Kunde storniert | der Kran bleibt nach dem Bau im Lager |
| Gleicher Artikel, zwei Kunden | älteste Bestellung zuerst (beim «nur für»-Kran gibt es keinen zweiten Kunden) |

**Die eine Änderung am Kern:** heute braucht jeder Auftrag bei der Freigabe **mindestens ein Stück**
(§6.2). Neu: «mindestens ein Stück am Start **oder** an einem Modul». Plus: der Eintritt am Modul, heute
nur am Verbrauch, gilt auch am ersten Modul eines Verkaufs.

**Offen (für den Bau):** «älteste Bestellung zuerst» heisst, der Eintritt fragt die Aufträge in der
Reihenfolge ihrer Freigabe – heute fragt jeder Schritt nur für sich.

### F15 Fassung 6 – Etikett in Kleinbuchstaben

`https://id.inexxio.com/100482117` – wie man es schreibt. Die Grossbuchstaben (etwas kleinerer QR)
lassen wir; der Unterschied ist nur auf sehr kleinen Etiketten spürbar.

### F28 Fassung 6 – Transport aus Grösse und Gewicht (dein Vorschlag)

Kein neues Feld: der Artikel hat **Grösse** (`L×B×H` mm, Pflicht bei der Freigabe) und **Gewicht**.
Die Transportart ist eine **Ableitung**:

| Transport | Grenze (Vorschlag, als Werte im ERP an der Gesellschaft) |
|---|---|
| Paket | bis 100 × 60 × 60 cm und 30 kg (Grenze der Post) |
| Palette | bis 120 × 80 × 180 cm und 1'000 kg |
| Lastwagen | alles darüber |

Die Bestellung nimmt die grösste nötige Art; Kleines fährt mit. Die Grenzen sind Daten, keine Regel im
Code – ändert die Post ihre Masse, ändert man eine Zahl.

### F30 Fassung 6 – Papiere aus dem, was es schon gibt

Ja: jedes Papier (Offerte, AB, Rechnung …) entsteht heute schon aus **einer** A4-Vorlage und wird als
Dokument abgelegt (`services/a4.py`, `voucher_docs`). «Als PDF» auf der Produktseite nutzt die
**Vorschau**, die es auch schon gibt (`voucher_docs.preview`: dieselbe Handlung im Probelauf, Papier
lesen, zurückrollen). Kein zweites Papier, keine zweite Vorlage. Abgelegt wird erst, was wirklich
bestellt wird.

### F19 Fassung 5 – Anzahlung ist ein zweites Zahlungsmodul (wie entschieden)

Im Kern ist es längst festgelegt: **«Anzahlung ist ein zweites Modul»** (`docs/history/2026-11-10-
process-core-chronik.md:1384`, `…/2026-10-process-core-9-15-chronik.md:120`) – jedes Zahlungsmodul hat
seine eigenen Positionspreise, die Anzahlung ist eine Zahlung wie jede andere. Der Vorschlag «eine
Prozentzahl» (Fassungen 2–4) ist **zurückgenommen**.

Für die Bestellung heisst das: die Karte «Verkauf» des Krans sagt «Anzahlung 30 %». Der Auftrag bekommt
dann **zwei** Zahlungsmodule: zuerst «Anzahlung» (die Kran-Position zu 30 %, Frist 0 = vorab), dann
«Rest» (70 % und alle übrigen Positionen). Ein Teil ohne Anzahlung → ein Zahlungsmodul.

### F22 Fassung 5 – Abo und Miete im Korb, wie bei den anderen

Dein Einwand: nicht neu erfinden. **So machen es die anderen** – Apple bietet AppleCare **im
Konfigurator** an («AppleCare+ hinzufügen»), Tesla das Software-Abo als **Option**, Amazon den
Schutzplan **im Korb**. Ein Klick für den Kunden; dahinter sind es getrennte Verträge mit eigenen
Nummern und eigenen Rechnungen.

Bei uns genau so: der Jahresservice ist eine **Option auf der Produktseite** und landet im Korb. Beim
«Bestellen» entsteht **je Rhythmus ein Auftrag** (Kauf einmal, Service jährlich mit Schlaufe). Die
Bestätigung zeigt beide Nummern. Damit bleibt **Bestellnummer = Auftragsnummer**, und der Kunde klickt
trotzdem nur einmal. Verkaufen heisst: die Option steht dort, wo der Kunde gerade entscheidet –
vorgewählt wird nichts.

### F24 Fassung 5 – Der Kunde tippt nur, was nur er weiss

Gemeint war **nicht**, dass der Kunde viel ausfüllt – im Gegenteil. Im Zahlungsmodul stehen rund ein
Dutzend Angaben (Partei, Anschrift, Gesellschaft, Währung, Preise, Eigentum, Frist, Lieferfrist,
Incoterm, Steuersatz). **Der Kunde gibt davon nur drei:** E-Mail, Name, Lieferadresse – Firma oder UID
freiwillig. **Alles andere füllt das ERP selbst** aus der Karte «Verkauf», dem Land und den Konditionen
(Tabelle unten, unverändert). Kein «Offerte anfordern» als Ausweg – der Gedanke ist gestrichen.

### F29 neu – Die Karte «Verkauf» geht erst auf «für alle», wenn sie vollständig ist

Wie heute der Entwurf eines Auftrags: das ERP sagt, was fehlt (`validate_draft`), und gibt erst frei,
wenn nichts fehlt. **Dieselbe Regel für die Karte «Verkauf»** – in zwei Formen in **einem** Modul
(Leitbild «Zwei Formen einer Regel»): `verkauf.problem` («Preis fehlt», «keine Lieferart») für die
Oberfläche, `verkauf.assert_…` als Tor. Der Schalter «für alle» geht erst, wenn die Liste leer ist.
**Folge:** auf der Website gibt es nie ein Produkt, das man nicht bestellen kann. Lücken sind ein
Problem im ERP, nie eines des Kunden.

### F28 neu – Transportgrösse statt «Schnittmenge»

«Schnittmenge» war unklar – und unnötig kompliziert. Einfacher, wie jede Spedition denkt:
- Jeder Artikel sagt in seiner Karte, **wie er mindestens transportiert werden muss:** Paket · Palette ·
  Lastwagen.
- **Kleines fährt beim Grossen mit.** Die Bestellung nimmt den **grössten nötigen** Transport:
  Schrauben + Kran → Lastwagen, die Schrauben liegen dabei.
- **Abholen** geht immer; **Montage** ist eine Option des Artikels (Einbau bei Ihnen), kein Transport.
- Damit gibt es **keinen Konflikt** mehr – und kein «separat bestellen». Eine neue Transportart ist eine
  Zeile im ERP (mit Rang), keine Zeile Code.
- «Lieferbar in»: heute gibt es **keine** Sperre nach Land, und es braucht vorerst keine – wenn je, dann
  als Ausnahme eines Marktes (E17).

### F25 Fassung 5 – Übergabe: wie es robust bleibt

**Die Lage:** der Kunde bestellt einen Kran, den es noch nicht gibt. Zwei Aufträge (E20):
**E** = Erzeugung (unverändert, wie heute mit «Neu»), **V** = Verkauf (Zahlung, Lieferung).

**Warum V sofort entstehen muss:** der Kunde zahlt (an)  und bekommt seine Auftragsbestätigung beim
Bestellen – dafür braucht es V mit seinem Zahlungsmodul ab Tag 1.

**Wie es geht:**
1. «Bestellen» legt **E** an. E erzeugt die Stücke **sofort mit Nummer** (macht «Neu» heute schon).
2. Im selben Klick entsteht **V** mit genau diesen Stücken – Zeile «aus Auftrag E».
3. Ein Stück ist in genau **einem** Auftrag aktiv (Exklusivität, DB-Index). Darum steht es in V
   zunächst **«wartet auf E»** – eine Zugehörigkeit, die noch nicht offen ist (der Index zählt nur
   offene).
4. **Erreicht ein Stück das Ende von E, öffnet sich seine Zugehörigkeit in V** – in derselben Stelle und
   Transaktion, die heute schon das Ende eines Auftrags schreibt (`process._finish`). Ins Log kommt
   «übergeben an V».

**Robust heisst: jeder Fall endet in etwas, das es heute schon gibt.**

| Was passiert | Folge |
|---|---|
| Alles läuft | E endet → Stück tritt in V ein → Zahlung → Lieferung → Verkauft |
| E verzögert sich | V wartet; der Liefertermin von V folgt dem Datum von E |
| Stück wird in E verschrottet | V zeigt «kann nicht geliefert werden» → Aufgabe; Stornieren oder neues Stück (wie die Wiederholung «geht nicht mehr») |
| Kunde storniert V | die Vormerkung fällt weg; E läuft fertig, das Stück wird **Freigegeben** = Lager |
| E wird abgebrochen (Abweichung) | wie verschrottet: V meldet es |

Dazu ein **Wächter**: kein Stück wartet auf einen Auftrag, der schon zu Ende ist.

*Alternative (einfacher, aber gegen E20):* **ein** Auftrag = Erzeugungsprozess + Lieferung angehängt.
Nichts muss warten – dafür ist der Erzeugungsprozess im Auftrag nicht mehr «rein».

### F30 neu – «Offerte als PDF» (was gemeint war)

Ein Firmenkunde will oft ein **Papier** für seinen Chef oder die Bank, bevor er bestellt. Statt dafür
einen eigenen Ablauf (Offerte erstellen, senden, annehmen) zu bauen: auf der Produktseite des Krans ein
Knopf «Als PDF», der **genau diese Seite** als A4-Offerte ausgibt (aus der A4-Vorlage, die jeder Beleg
schon nutzt). Bestellt wird dann trotzdem auf der Seite. **Optional** – wenn es nicht gebraucht wird,
fällt es weg.

### F15 Fassung 5 – Etikett: `id.inexxio.com` (nochmals hinterfragt)

Drei Möglichkeiten, ehrlich verglichen:

| | Pfad `inexxio.com/i/…` | **Subdomain `id.inexxio.com/…`** | eigene zweite Domain |
|---|---|---|---|
| Kosten | 0 | 0 | ~20 CHF/Jahr |
| Unabhängig von der Website | nein (Regel im Hosting der Website) | **ja** – zeigt per DNS auf einen eigenen kleinen Dienst | ja |
| Risiko | Website-Umbau kann `/i/` verschieben | gering | zweite Domain kann vergessen werden |

**Empfehlung: Subdomain `id.inexxio.com`.** Sie gehört zur Domain, die wir ohnehin behalten, ist aber
**ein eigenes Ding**: sie macht nur «Nummer → Geräteseite» und kann in Minuten woandershin zeigen, egal
wie die Website gebaut ist. Das ist das Muster von GS1 (ein Resolver nur zum Weiterleiten).

**Sauber definiert:**
- Inhalt des QR: `HTTPS://ID.INEXXIO.COM/100482117` – **in Grossbuchstaben**: dann nutzt der QR-Code
  den kompakten Zeichensatz, wird kleiner und liest sich besser auf einem kleinen Motor-Etikett.
  Browser behandeln es gleich.
- Der Dienst kennt genau zwei Antworten: Nummer bekannt → Weiterleitung auf die Geräteseite (Sprache des
  Handys); unbekannt → Seite «Gerät nicht gefunden – Nummer eingeben».
- Der ERP-Scanner liest weiter nur die Nummer (`scan.ts`) – alte Etiketten gehen.
- Die Domain ist **inexxio.com** (E25).

### F18 Fassung 4 – Projekt = Artikel «nur für» (dein Einwand, übernommen)

Fassung 3 hatte für das Projekt einen zweiten Weg (ein Mensch gibt frei, der Kunde sagt später zu). Dein
Einwand ist einfacher und richtig: **ein Projekt ist ein Artikel, der nur für einen Kunden freigegeben
ist.** Der Kunde sieht ihn auf der Produktseite, bestellt ihn mit «Bestellen» – genau wie ein Teil.
- Die **Offerte als Papier** (PDF mit AGB) ist dann eine Ansicht dieser Seite – «Als Offerte
  herunterladen» –, kein eigener Vorgang.
- **Gültigkeit**: die Karte «Verkauf» hat ein «sichtbar bis» (z. B. 30 Tage).
- Verhandelt der Kunde etwas um, ändert man die Karte (Preis) oder macht einen neuen Kran-Artikel, der
  den alten ersetzt (E8 gilt).
- Folge: im Shop durchläuft das Zahlungsmodul die Stufe «Offerte» nicht mehr sichtbar – die Zusage
  geschieht mit der Freigabe (wie heute schon die stille Zusage der Wiederholung, `loop.agreed`).

### F22 Fassung 4 – Abo und Miete: eigener Auftrag, nicht im Korb

Deine Frage: «Muss ich einmal für den Kauf und einmal für das Abo abschliessen?» – **Ja, und so machen
es die anderen auch:** Apple (iPhone + AppleCare monatlich), Amazon («Spar-Abo»), Tesla
(Fahrzeug + Software-Abo): der Kauf ist **eine** Bestellung, das Abo ein **eigener Vertrag** mit eigenen
Rechnungen. Oft im selben Zug angeboten («AppleCare dazu?»), aber getrennt abgeschlossen.

Bei uns: «Abonnieren» und «Mieten» sind eigene Knöpfe auf der Produktseite, sie gehen **nicht in den
Korb**. Jeder Knopf legt einen Auftrag mit Schlaufe an – eine eigene Bestellung mit eigener Nummer.
Damit gilt ohne Ausnahme: **eine Bestellung = ein Auftrag = Bestellnummer = Auftragsnummer.** Nach dem
Kauf eines Krans darf die Seite fragen: «Wartungsvertrag dazu?» – ein Klick, zweite Bestellung.

### F24 neu – Jedes Feld des Zahlungsmoduls hat eine Quelle

Was das Zahlungsmodul braucht (`domain/modules.py` `Beleg`, `services/voucher_rules.py`), und woher
es bei einer Bestellung kommt:

| Feld | Quelle |
|---|---|
| Richtung | immer **Einnahme** |
| Partei | die bestellende **Person** (aus der E-Mail, `people.ensure`); Firma «z. H.» aus der UID |
| Anschrift | Eingabe beim Bestellen (Google Places), landet im Adressbuch der Person |
| Gesellschaft (stellt den Beleg) | aus dem Land der Lieferadresse (`sites.company_for_country`) |
| Positionen und Preise | Karte «Verkauf» + gewählte Optionen, Preis des Marktes (F23, F26) |
| Währung | Markt der Lieferadresse (F26) |
| Eigentum | «Kaufen» → geht an die Partei · «Mieten» → geht an uns |
| Zahlungsfrist / Vorauszahlung | Kaskade Gesellschaft → Partner → Karte «Verkauf» (F19) |
| Lieferfrist | abgeleitet: Lager → Versandtage; aus Auftrag → dessen Datum «bis» |
| Lieferbedingung (Incoterm) | aus der Lieferart (Abholen → EXW, Paket/Spedition → DAP Kunde) |
| Steuersatz | wie heute: entscheidet die Anschrift |

Fehlt eine Quelle, kann die Seite nicht «Bestellen» anbieten, sondern nur «Offerte anfordern» – nie
eine halbe Bestellung.

### F19 Fassung 4 – Vorauszahlung: wie heute, Anzahlung später

**Heute definiert** (`domain/voucher.py:191`): **«Vorauszahlung IST der Wert 0»** der Zahlungsfrist – kein
Schalter daneben. Ist die Frist 0, laufen die Stücke erst weiter, wenn **voll** bezahlt ist
(`PROCESS_CORE` §9.15); sonst mit der Zusage. Das genügt für den Shop vollständig:
- Neukunde: Frist 0 → Karte/TWINT/QR, Ware nach Zahlung.
- Bekannte Firma: Frist 30 Tage (Kondition am Partner) → Ware sofort, Rechnung.

**Anzahlung** (30 % beim Kran) kann das Modul heute **nicht** (entweder alles vorab oder nichts). Das
kommt erst, wenn die Maschinen in den Shop gehen – Vorschlag dann: eine zweite Zahl neben der Frist
(«davon vorab in %»). Bis dahin: Kran mit Frist 0 oder mit Frist und Vertrauen.

### F25 neu – Übergabe: der Erzeugungs-Auftrag gibt seine Stücke weiter

Dein Entscheid (E20): bei «auf Bestellung» gibt es **zwei Aufträge**; der Erzeugungs-Auftrag bleibt
unverändert. Die offene Frage war: der Verkaufs-Auftrag braucht bei der Freigabe Stücke – die gibt es
aber erst nach der Erzeugung. Die Lösung:

1. **Beim Bestellen** entstehen beide in einem Zug: zuerst der Erzeugungs-Auftrag (er legt die Stücke
   **sofort** an, mit Nummer – das tut «Neu» heute schon), dann der Verkaufs-Auftrag mit genau diesen
   Stücken als Zeile **«aus Auftrag X»**.
2. **Solange X läuft**, stehen die Stücke im Verkaufs-Auftrag als «kommt aus Auftrag X» – sie sind dort
   **vorgemerkt, nicht aktiv** (die Exklusivität bleibt: ein Stück ist in genau einem Auftrag aktiv).
3. **Am Ende von X** werden sie Freigegeben und treten im selben Zug in den Verkaufs-Auftrag ein. Die
   **Übergabe ist ein Ereignis im Log**, keine Spalte (wie `loop.next`).
4. Zahlung und Zusage gelten ab dem ersten Tag; der Kunde sieht sogar seine **Seriennummer von Anfang an**.

Allgemein: eine Zeile im Verkaufs-Auftrag ist **«Lager»** oder **«aus Auftrag X»**. X kann eine Erzeugung
sein – oder später ein Einkauf (Ware vom Lieferanten). Eine Regel für beides.

### F26 neu – Währung: ein Kurs je Markt, vom Menschen gesetzt

**Heute** (`domain/currency.py`): ein Beleg hat **eine** Währung; Fremdwährung nur für Lieferungen ins
Ausland; **es rechnet nicht um** – mit Absicht: «wer umrechnet, ohne zu sagen *wann* und *woher*,
erfindet Zahlen». Der alte Shop scheiterte genau daran (zwei Kurse für einen Kauf, `docs/attic.md`).

**Vorschlag – sagt «wann» und «woher»:**
- Ein **Markt** (F23) hat eine Währung und **einen Kurs mit Datum**, vom Menschen gesetzt
  («1 CHF = 1.04 EUR, gilt ab 01.01.2027») – kein Tageskurs, der Preise täglich springen lässt.
- Der **Preis in EUR ist eine Ableitung**: Hauspreis × Kurs × Kaufkraft-Faktor des Marktes, **auf eine
  feste Stufe gerundet** (z. B. ganze Euro). Wo das nicht passt, setzt man am Artikel einen festen
  EUR-Preis – Ausnahme, nicht Regel.
- **Anzeige:** Besucher aus Deutschland sieht Euro (Land aus der Anfrage); verbindlich wird die Währung
  mit der **Lieferadresse** – genau die heutige Regel «Fremdwährung nur ins Ausland».
- **Stripe** belastet genau diesen Betrag in dieser Währung (der Checkout gibt Betrag **und** Währung
  vor – Lehre aus dem alten Anlauf). Ein Kurs, eine Quelle: unsere.

### F27 neu – Ausnahmen ohne if-else: Eigenschaften + eine Regel

Statt Sonderfälle im Code: **jeder Artikel nennt in seiner Karte «Verkauf» Eigenschaften**, und der Korb
kennt **eine** Regel.

| Eigenschaft am Artikel | Regel im Korb |
|---|---|
| erlaubte Lieferarten | angeboten wird die **Schnittmenge** aller Positionen |
| Lieferzeit (Lager / aus Auftrag) | der Liefertermin ist der **späteste** aller Positionen |
| lieferbar in (Markt) | nur, was ins Land der Lieferadresse darf |
| Rhythmus (einmal / wiederkehrend) | Wiederkehrendes kommt nie in den Korb (F22) |

Ist die Schnittmenge leer (Kran nur Spedition, Paket-Teil nur Paket), zeigt der Korb **an der Zeile**,
was nicht zusammenpasst, und bietet an: «separat bestellen». **Eine neue Ausnahme ist eine neue
Eigenschaft am Artikel – keine neue Zeile Code.**

### F15 Fassung 4 – das Etikett, selbst gebaut, auf unserer Domain

Dein Entscheid (E16): QR mit Link, selbst gebaut. **Domain:** unsere eigene, mit einem festen kurzen
Pfad – **`inexxio.ch/i/<Nummer>`**. Eine zweite Domain bringt nichts, solange wir `inexxio.ch` nie
aufgeben (Verlängern kostet wenig; zieht die Website um, bleibt die Domain und leitet weiter).

Sauber aufgebaut heisst:
- **Eine Regel im Hosting** (`firebase.json`): `/i/<Nummer>` → Dienst → leitet auf die Geräteseite in der
  Sprache des Besuchers. Die Etikett-Adresse ist **nie** selbst eine Seite – so kann sich die Seite
  ändern, das Etikett nie.
- **`/i/` ist reserviert**: keine Website-Seite darf je so beginnen (`check-site` prüft es).
- Der ERP-Scanner liest weiter nur die Nummer (`scan.ts`) – Etiketten mit und ohne Adresse gehen.
- Unbekannte Nummer → freundliche Seite «Gerät nicht gefunden – Nummer eingeben / anfragen».


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

### F18 Fassung 3 – Bestellung = Auftrag, Korb = Entwurf (der Kern)

Fassung 2 sagte «eine Bestellung ist eine angenommene Offerte». Dein Einwand stimmt: einfacher ist,
**die Bestellung IST ein Auftrag** – das Zahlungsmodul kann Offerte, Zusage, Rechnung, Anzahlung,
Mahnung, Gutschrift schon.

**Wann entsteht der Auftrag – beim Korb oder beim Bestellen?** Beim **Bestellen**. Würde jeder Korb ein
Auftrag, dann:
- würden Stücke für Körbe gesperrt, die nie bestellt werden (die Exklusivität greift sofort),
- zöge jeder Besucher Objektnummern und füllte das Log mit Abgebrochenem,
- bräuchte es ein Aufräumen verlassener Körbe.

Dagegen ist «der Korb ist der Entwurf» genau die Regel, die im ERP heute schon gilt: der Entwurf lebt
im Browser, «Freigeben» legt an. **Kein neues Konzept.**

**Wer drückt «Freigeben»?**

| | Shop | Projekt (Kran) |
|---|---|---|
| Entwurf füllt | der Kunde (Korb) | ein Mensch im ERP |
| Freigabe | der Kunde: «Bestellen» | der Mensch |
| Zahlungsmodul danach | **zugesagt** (der Klick ist die Zusage) | **Offerte** – wartet auf den Kunden |
| Kunde sieht | «Ihre Bestellung» | dieselbe Seite, mit «Zusagen» |

Die Seite «Ihre Bestellung» ist der Auftrag, wie ihn der Kunde sieht (die API dafür gibt es:
`GET /erp/orders/{id}` liefert einer beteiligten Person heute schon ihren Teil, `services/order_view.py`).
Sie wächst aus der Seite `/dokument` (Stationen) – ein Ort, erreichbar über den Link in der Mail und im
Konto.

### F22 neu – Je Rhythmus ein Auftrag (Abo, Miete in derselben Bestellung)

Eine Schlaufe wiederholt immer den **ganzen** Auftrag (`domain/loop.py`). Darum:
- **Einmaliges** (Kauf, Montage) → Auftrag A.
- **Wiederkehrendes** (Wartung jährlich, Miete monatlich, Abo) → je Takt ein Auftrag B, C … mit Schlaufe.
- Alle tragen **dieselbe Bestellnummer** (Herkunft am Auftrag, gemeinsam für die Geschwister;
  eindeutig ist «Bestellnummer + Takt» – so entsteht auch beim Doppelklick nichts doppelt).
- Der Kunde sieht **eine** Seite: oben der Kauf, darunter «läuft jährlich: Wartung, nächste 03/2027».
- Geld: jeder Auftrag hat sein Zahlungsmodul, also eigene Rechnungen – üblich bei Abos (auch Apple,
  Swisscom trennen Kauf und Abo). Damit Abo-Rechnungen von selbst bezahlt werden, braucht es die
  **gespeicherte Karte** (Stripe, heute bewusst nicht gebaut – Bau-Etappe 4).

Mit diesen zwei Sätzen ist jeder Fall abgedeckt, den wir gefunden haben:

| Fall | Aufträge |
|---|---|
| 2 Schrauben | 1 (Lager, Paket) |
| Funk-Set mit Einbau | 1 (Lager, Montage) |
| Kran nach Mass + Funk dazu | 1 (Neu + Lager tritt bei der Lieferart ein, F20) |
| Kran + Wartungsvertrag | 2 (Kauf; Wartung mit Schlaufe jährlich) |
| Miete Funk-Set 6 Monate | 1 mit Schlaufe monatlich, Eigentum «geht an uns» |
| Teile jetzt, Maschine später | 2 Bestellungen (der Kunde teilt, F13) |

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

### F15 Fassung 3 – QR wie GS1 Digital Link, konkret bei uns

**Was GS1 Digital Link ist** (GS1 = die Organisation hinter dem EAN-Strichcode): eine Regel, wie man
eine Nummer **in eine Web-Adresse** schreibt, damit **ein** QR-Code beides kann:
- die **Handy-Kamera** öffnet eine Web-Seite (die Adresse),
- jede **Software** (Kasse, Lager, unser ERP) liest die Nummer aus festen Stellen der Adresse heraus.

Beispiel GS1: `https://beliebige-domain.ch/01/07610000000001/21/ABC123` – «01» heisst «es folgt die
Artikelnummer (GTIN)», «21» heisst «es folgt die Seriennummer». **Die Domain ist frei wählbar und
austauschbar** – die Daten stecken im Pfad. Wer die Domain betreibt, leitet nur weiter («Resolver»).

**Die drei Gedanken, die wir übernehmen:**
1. **Die Nummer ist die Information, die Adresse nur der Weg.** Unser Scanner liest heute schon jede
   9-stellige Nummer aus jedem Text (`frontend/src/lib/scan.ts`) – die Domain ist ihm egal.
2. **Die Domain macht nur eines: weiterleiten.** Eine Regel im Hosting: `<etikett>/<Nummer>` →
   heutige Geräteseite in der Sprache des Handys. Zieht die Website einmal um, ändert man **diese eine
   Regel**; die Etiketten auf den Maschinen bleiben richtig.
3. **Eine Domain nur für Etiketten**, kurz, ohne Firmennamen-Risiko, nie aufgegeben (~20 CHF/Jahr).

**Konkret bei uns** – auf dem Etikett:

```
  ┌──────────┐   Heukrananlage HK 12
  │  QR-Code │   100 482 117
  │          │   <etikett>.ch/100482117
  └──────────┘
```

- Handy: öffnet die Geräteseite. ERP-Scanner: liest 100482117. Mensch: tippt die Nummer ab.
- **Volle GS1-Form erst, wenn wir GTIN-Nummern haben** (für Amazon/Google Shopping nötig, Mitgliedschaft
  GS1 Schweiz kostet jährlich – L3). Dann schreiben neue Etiketten zusätzlich `/01/<GTIN>/21/<Nummer>`;
  alte Etiketten gehen weiter, weil unsere Weiterleitung beide Formen versteht.

### F6 bestätigt mit deiner Ergänzung

Standard: der neue Artikel wird verkauft, der Rest des alten läuft **zuerst** aus (FIFO über die Kette
nimmt das älteste Stück). Soll sofort umgestellt werden: den Restbestand **sperren** (Aussondern
«Sperren» gibt es). Keine neue Funktion.

### F21 entschieden – Übersetzung: einmal, gespeichert, für jeden Text

**Nicht** bei jedem Besuch live (langsam, teuer, für Google unsichtbar), sondern **einmal beim
Speichern**: die KI übersetzt den deutschen Text in jede Sprache der Website, das Ergebnis wird
gespeichert und mit der Seite ausgeliefert. Ändert sich der deutsche Text, wird **nur dieser Text** neu
übersetzt. Kosten: Bruchteile eines Rappens je Text.

**Harte Regel (E13):** jeder Text der Website steht in **jeder** angebotenen Sprache – Produkttexte aus
dem ERP wie die festen Texte der Website. **Ein Wächter prüft es:** fehlt eine Sprache, bricht der Bau
der Website ab (wie `check-site` heute «Fixpreis» abbricht). Fachwörter hält eine kleine Wortliste je
Sprache fest.

### F23 neu – Märkte: die Welt gehört dem Hausmarkt, gepflegt wird nur die Ausnahme

Wie bei den Gebieten der Gesellschaften (`sites.company_for_country`): **ohne Eintrag gilt alles für alle
Länder** – Hauspreis in CHF, Hausgesellschaft. Ein **Markt ist nur eine Ausnahme**: eine Liste von
Ländern, für die etwas anders ist:
- andere **Währung** und **Preis** (z. B. DE/AT in EUR, Kaufkraft),
- andere **Gesellschaft** (wenn es einmal eine INEXXIO GmbH in Deutschland gibt – dann folgt es aus ihren
  Gebieten von selbst),
- **nicht lieferbar** (z. B. Sanktionsländer) → die Seite zeigt «Offerte anfordern».

Ein neues Produkt ist damit sofort **weltweit** bestellbar, zum Hauspreis. Was ins Ausland geht,
regelt das Zahlungsmodul heute schon (0 % Export, Zoll, Incoterms). Offen für Runde 2: Versandkosten
ins Ausland (Paket hat einen Preis je Zone, Spedition auf Anfrage).

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
| E10 | **Verkauf als Karte «Verkauf» am Artikel** (N1, F2), der Kette gehörend; Optionen verweisen auf andere Artikel. Kein eigener Objekttyp «Produkt». | 14.11.2026 |
| E11 | **Ein Korb, eine Lieferung** (N4, F13) – Ausnahmen werden gesammelt, sobald sie auftauchen. | 14.11.2026 |
| E12 | **«Nur für»: Personen und Firmen wählbar** (N7); Firma = alle ihre Personen. | 14.11.2026 |
| E13 | **Jeder Text der Website in jeder angebotenen Sprache** – harte Regel mit Wächter; übersetzt einmal beim Speichern durch die KI, nicht live (F21). | 14.11.2026 |
| E14 | **Die Bestellung ist ein Auftrag** (nicht ein eigenes Ding «Offerte»); das Zahlungsmodul trägt Offerte, Zusage, Rechnung, Zahlung (F18 Fassung 3). | 14.11.2026 |
| E15 | **ERP ist Master bleibt** – nichts der Bestellung wird ausserhalb gepflegt. | 14.11.2026 |
| E16 | **QR mit Link, selbst gebaut** (nach dem Muster GS1 Digital Link, ohne GS1-Dienst). | 14.11.2026 |
| E17 | **Märkte nur als Ausnahme** – ohne Eintrag gilt die ganze Welt (wie die Gebiete der Gesellschaften); Währung siehe F26. | 14.11.2026 |
| E18 | **Projekt = Artikel «nur für» einen Kunden**, sonst derselbe Weg wie jedes Produkt (bestätigt). | 14.11.2026 |
| E19 | **Bestellnummer = Auftragsnummer.** | 14.11.2026 |
| E20 | **«Auf Bestellung» = zwei Aufträge:** der Erzeugungs-Auftrag bleibt unverändert, der Verkaufs-Auftrag ist der Auftrag der Bestellung (Mechanik F25). | 14.11.2026 |
| E21 | **Die Seite «Ihre Bestellung»** ist gewünscht – robust gebaut. | 14.11.2026 |
| E22 | **Anzahlung = ein zweites Zahlungsmodul** (wie im Kern entschieden), keine Prozentzahl am Modul. | 14.11.2026 |
| E23 | **Abo und Miete gehen in den Korb** wie bei den anderen (Option im Konfigurator); dahinter je Rhythmus ein Auftrag. | 14.11.2026 |
| E24 | **Regeln hängen am Artikel (im ERP), der Code kennt keine** – Lieferart, Lieferzeit, Anzahlung. | 14.11.2026 |
| E25 | **Domain inexxio.com**, nicht .ch. | 14.11.2026 |
| E26 | **Währung gehört zu «Preise je Markt» (Runde 2); CHF ist die Leitwährung.** | 14.11.2026 |
| E27 | **Kein «Offerte anfordern» als Ausweg** – der Kunde füllt nur das Nötigste, alles andere kommt aus dem ERP. | 14.11.2026 |
| E28 | **Papiere aus dem Bestehenden:** jedes Papier aus der einen A4-Vorlage, als Dokument abgelegt; «Als PDF» = die bestehende Vorschau (F30). | 14.11.2026 |
| E29 | **Kauf + Abo = zwei Aufträge, zwei Bestellnummern**; die Produktseite zeigt beide. | 14.11.2026 |
| E30 | **Transport aus Grösse und Gewicht des Artikels** (Ableitung, kein neues Feld; Grenzen als Daten, F28). | 14.11.2026 |
| E31 | **Karte «Verkauf» erst «für alle», wenn das ERP sie als vollständig prüft** (F29). | 14.11.2026 |
| E32 | **Etikett `https://id.inexxio.com/<Nummer>`, in Kleinbuchstaben** (F15). | 14.11.2026 |
| E33 | **«Als PDF» auf der Produktseite** – ja (F30). | 14.11.2026 |
| E34 | **Keine Kern-Änderung:** jeder Auftrag startet mit definierten Einzelinstanzen, gewählt wird nur Regulär-Startendes; nichts aus einem laufenden Auftrag greifen. | 14.11.2026 |
| E35 | **Transportgrenzen** Paket ≤ 100 × 60 × 60 cm / 30 kg · Palette ≤ 120 × 80 × 180 cm / 1'000 kg · sonst Lastwagen – als Werte im ERP. | 14.11.2026 |

## 7 · Vorgehen – wie wir es definieren

Je Runde ein Block der Themenkarte: ich zeige ihn im **Bild**, du sagst, was gefällt, und entscheidest;
ich trage es in §6 ein. Gebaut wird erst, wenn eine Bau-Etappe ganz entschieden ist.

| Runde | Block | Stand |
|---|---|---|
| 1 | Grundmodell (A) und Bestellweg (F) | **Abläufe** – Fragen §8, im Bild durchklickbar |
| 2 | Preise und Märkte (C) | offen |
| 3 | Auftrag im ERP (G), Angebotsformen (D) | vorgezogen in F18–F20 |
| 4 | Seriennummer, QR, Ersatzteile, 3D (I) | F15 vorgezogen |
| 5 | Inhalte und Bilder (B) | offen |
| 6 | Nach dem Kauf (H), Recht (J) | offen |
| 7 | Gefunden werden, Kanäle (K, L), Betrieb (M) | offen |

**Bau-Etappen (Vorschlag):** 1 Katalog (Karte «Verkauf», Produktseiten, Anfragen) · 2 Bestellen
(Preis je Markt, Lieferarten, Neu + Lieferart, Vorauszahlung als Zahl, Seite «Ihre Bestellung») ·
3 Gerät (Etiketten-Adresse, Geräteseite, Teilebaum) · 4 Miete und Abo · 5 3D und Zwilling · 6 Kanäle.

## 8 · Offene Fragen an den Inhaber (Runde 1, Abläufe)

- **N20** «Auf Bestellung» in drei Lagen (F25 Fassung 7) – im Bild unter «Abläufe» durchklicken.
- **N21** Doppelklick-Schutz wie beschrieben (F31)?
- **N22** Produkt als Overlay aus dem Katalog, mit eigener Adresse (F32)?

Danach: **Runde 2 – Preise, Märkte, Währung.**
