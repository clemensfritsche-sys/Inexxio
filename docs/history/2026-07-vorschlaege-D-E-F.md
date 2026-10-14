# Konzept-Vorschläge D · E · F (Juli 2026)

> Drei offene Design-Entscheide zum Auswählen. Jeder Vorschlag: **Problem → Empfehlung →
> Warum → Skizze → Aufwand → offene Fragen**. Grundhaltung: das *bestehende* Kernmodell
> (Auftrag → Prozess → Instanz, `ensure_supply`, `replaced_by_id`, die EINE Stock-Helper-
> Stelle `inventory.in_stock_clauses`) maximal wiederverwenden statt neue Maschinerie bauen.

---

## D — Öffentliche Rechtsdokumente (AGB/Datenschutz/…) über das Dokument-Modul

### Problem
AGB & Datenschutz sind heute **hartkodierte React-Seiten** (`(public)/agb`, `(public)/datenschutz`).
Sie sollen stattdessen aus dem **Dokument-Modul** kommen (nummeriert, datiert, unveränderlich – wie
für die 10-Jahres-Archivierung gefordert) und auf der Website verlinkt sein. Deine Idee: am Unternehmen
ein Feld «AGB-Dokumentennummer»; freigegebene Instanz-Nummer eintragen → dieses Dokument wird verwendet.
Offene Frage: **Wie wird getauscht**, wenn sich der Text ändert – neuer Auftrag + Verschrotten, oder
neuer Artikel + Ersetzen?

### Empfehlung: **Zeiger, kein Ersetzen** («Pointer, not replacement»)
**Weder** Verschrotten **noch** Artikel-Ersetzen. Ein Rechtsdokument ist von Natur aus **append-only**:
jede Fassung ist eine eigene, unveränderliche Instanz mit Datum. Welche gerade *gilt*, ist eine
**Unternehmens-Entscheidung** – also ein **Zeiger am Unternehmen**, nicht eine Eigenschaft der Instanz.

Am `company_settings` ein kleines Slot-Feld:
```
legal_documents (JSONB) = { "agb": 100000123, "datenschutz": 100000124, "impressum": … }
```
Neue Fassung veröffentlichen = **drei triviale Schritte**:
1. Auftrag mit `document`-Schritt anlegen (Text via KI-Schreibhilfe möglich).
2. Freigeben → unveränderliche, nummerierte, datierte Dokument-Instanz.
3. Den Slot-Zeiger auf die neue Instanz-Nummer setzen. **Fertig.**

Die **alte** Instanz bleibt – sie ist die historische Fassung, weiter über ihre Nummer auflösbar. Kein
Verschrotten (würde die Historie zerstören), kein neuer Artikel (der Inhalt lebt im *Auftrag*, nicht am
Artikel).

### Warum das die eleganteste Lösung ist
- **Erfüllt die AGB-Akzeptanz-Pflicht** («Zeitstempel + Version in DB») geschenkt: die *Version* IST die
  Instanz-Objektnummer. Bei der Zustimmung zusätzlich `agb_document_id` speichern → «Welcher genau
  akzeptierte Kunde X am 5.1.?» ist ein **einziger Objekt-Lookup** – wasserdicht im Streitfall.
- **Website = amtliche Optik**: die `/agb`-Seite rendert die Zeiger-Instanz mit `DocumentView` (seit
  «online = PDF» inkl. Briefkopf/Fusszeile). Fällt der Zeiger weg → Fallback auf den heutigen Text
  (migrationsfreundlich).
- **Ein Muster für alle Typen** (AGB, Datenschutz, Widerruf, Liefer-/Zahlungsbedingungen …).
- Es ist **philosophisch dasselbe wie `replaced_by_id`** – nur wohnt der Zeiger am Unternehmen (dort
  gehört die «gilt gerade»-Entscheidung hin), nicht an der Instanz.

### Skizze
- `company_settings.legal_documents JSONB`.
- Public-Endpoint `GET /legal/{kind}` → löst den Zeiger auf → gibt Inhalt + Nummer + Datum (öffentlich,
  cachebar).
- `/agb`, `/datenschutz` holen ihn und rendern mit `DocumentView`; Fallback = eingebauter Text.
- Admin → Systemkonfiguration → Sektion «Rechtstexte»: je Typ ein `SearchSelect` freigegebener
  Dokument-Instanzen (+ «Neue Fassung verfassen» = öffnet einen Auftrag mit `document`-Schritt).

### Aufwand
**Klein–mittel.** Dokument-Instanz + `DocumentView` + Unveränderlichkeit existieren. Neu: ein JSONB-Feld,
ein Public-Resolver, zwei Website-Seiten umstellen, eine Admin-Sektion.

### Offene Fragen
- Slots als JSONB (flexibel, neue Typen ohne Migration) **oder** feste Spalten (`agb_document_id` …,
  typsicher)? → Empfehlung JSONB.
- Optional als Zuckerguss: die Instanzen zusätzlich als Kette verlinken (`supersedes`), damit ein
  Versions-Verlauf ohne den Slot rekonstruierbar ist.

---

## E — Wiederkehrende Aufträge vs. Ablaufdatum + Auto-Nachbestellung

### Problem
Zwei Mechanismen stehen zur Wahl (du tendierst zurück zu «Auftrag wiederholen»):
1. **«Auftrag wiederholen»** – zeitgesteuert (monatlich X produzieren/bestellen).
2. **Instanzen mit Ablaufdatum + Auto-Nachbestellung** (Vorlaufzeit, je Mindestbestand).

### Empfehlung: die drei **verwechselten** Konzepte sauber trennen – und **bestandsgetrieben** bauen
Es sind **drei orthogonale** Dinge:
| Konzept | Frage | Mechanismus |
|---|---|---|
| **Zeit-Wiederholung** | «alle 30 Tage 100 Stück» | Zeitplan (cron) |
| **Meldebestand** | «Freibestand < Sicherheitsbestand → nachbestellen» | Reorder-Point-Policy |
| **Ablaufdatum** | «Instanz ist über MHD → unbrauchbar» | Haltbarkeit → Abgang |

Das **Ablaufdatum treibt NICHT selbst die Nachbestellung** – es treibt eine **Ausbuchung** (Instanz über
MHD → Auto-Verschrottung/Abweichung), die den **Bestand senkt** → und *dadurch* die Meldebestands-Policy
auslöst. Sie **komponieren** also.

**Bau den Meldebestand (Nr. 2), nicht den Zeit-Cron.** Grund: der Kern kann das fast schon.
- `safety_stock` (optional) und `min_order_qty` existieren am Artikel.
- Die **Vorlaufzeit ist bereits abgeleitet** (`lead_time_days_low/high`) – das System kann sogar
  *vorausschauend* bestellen, bevor der Bestand 0 erreicht.
- **`supply.ensure_supply`** (ADR 003: rekursiv, idempotent, zyklensicher) ist **exakt dasselbe Primitiv**:
  «Bedarf nicht gedeckt → Nachschub-Auftrag über die Fehlmenge, fährt den Artikel-Prozess (produzieren
  ODER beschaffen)». Meldebestand = derselbe Aufruf, nur mit **Bestand als Auslöser** statt Auftrag.

### Design (ereignisgetrieben, nicht cron)
- Am Artikel: **Meldebestand** (= `safety_stock` wiederverwenden), **Zielbestand** (`reorder_target`),
  `min_order_qty` (da). Vorlauf schon abgeleitet.
- Ein schlanker Evaluator auf dem **Domain-Event-Strom** (jede Bestandsänderung emittiert bereits ein
  Event): bei Artikeln mit Meldebestand prüfen `Freibestand < Meldebestand`? Wenn ja **und** kein offener
  Nachschub deckt es schon (idempotent wie `ensure_supply`) → Nachschub-Auftrag über
  `max(Ziel − Frei, MOQ)`.
- Kein neuer Auftrags-Typ, aber **ohne Eltern** → neuer `reason='replenishment'` (eigenständiger
  Nachschub, nicht an einen Eltern gepinnt).
- **Ablaufdatum** separat: `instances.expires_at` + `articles.shelf_life_days`; ein täglicher Sweep
  «über MHD → Abweichung/Verschrottung» (nutzt `scrap`/`deviation`, die es gibt). Der Abgang senkt den
  Bestand → Meldebestand greift.

**Ereignisgetrieben schlägt Cron**: reagiert genau dann, wenn der Bestand fällt (Verkauf, Verschrottung,
MHD-Ausbuchung) – präziser und billiger als ein nächtlicher Lauf, und passt 1:1 zur bestehenden
«Bedarf → Nachschub»-Philosophie. Keine Überproduktion.

### «Auftrag wiederholen» (Zeit) – bewusst zweitrangig
Zeit-Wiederholung auf der **Verkaufsseite** gibt es schon: das **Produktabo** (`sub_type='product'`,
wiederkehrende Lieferung via `invoice.paid`-Hook). Für eine echte *fixe interne Fertigungskadenz* ist ein
Vorlagen-Auftrag + Zeitplan ein dünnes Add-on – aber als «Zeitplan, der denselben Supply-/Produce-Pfad
aufruft», **nicht** als parallele Engine. Meist ist der Meldebestand ohnehin klüger (produziert nur den
echten Bedarf).

### Merksatz
**«Nicht die Zeit soll bestellen, sondern der Bestand.»** Die Aufgabe des Kalenders ist nur die
Haltbarkeit (MHD) – und die senkt den Bestand, wodurch sie denselben Nachbestell-Auslöser füttert.

### Aufwand
**Mittel.** Neu: 1–2 Artikel-Felder (Meldebestand = vorhandenes `safety_stock`, Zielbestand),
`instances.expires_at` + `articles.shelf_life_days`, ein Event-Evaluator (→ `replenishment`-Supply-Order),
ein täglicher MHD-Sweep. Alles auf bestehenden Supply-/Scrap-/Deviation-Primitiven.

### Offene Fragen
- Meldebestand auf **Freibestand** (ohne Reservierungen) oder physischen Bestand rechnen? → Empfehlung
  Freibestand (das ist die ehrliche Deckungslücke, konsistent mit `_subject_shortfalls`).
- Vorausschauend (Vorlaufzeit einrechnen) ab Start, oder erst reaktiv beim Unterschreiten? → reaktiv
  starten, vorausschauend als Ausbaustufe.

---

## F — Lagerplatz als Artikel + Instanz (Vereinheitlichung)

### Problem
`StorageLocation` ist ein eigenes Modell/Feed mit eigener Objektnummer, Status-Fluss, `note`,
«Verwendung»-Reiter. Instanzen tragen `location_type ∈ lagerplatz|user|instance`. Du willst den
Lagerplatz über **Artikel + Instanz** abbilden (alles ist eine Instanz) – **grenzgenial einfach**.

### Kern-Erkenntnis
Das Instanz-Standortmodell **kann Instanz-in-Instanz bereits** (`location_type='instance'`). Ein
Lagerplatz ist nur «ein Behälter-Instanz, in der andere Instanzen liegen». Damit fällt eine echte
**Lager-Hierarchie** (Gebäude → Raum → Regal → Fach → Behälter) als **Baum von Instanzen** heraus –
mächtiger als die heutige flache Tabelle (ein fahrbarer Behälter, der selbst den Raum wechselt, ist
heute kaum modellierbar – als Instanz-in-Instanz **schon**).

### Empfehlung: die **Abstraktion** vereinheitlichen, per **einem Marker + einer Klausel** – zweiphasig
Die *eine* saubere Idee: **Ein Lagerplatz IST eine Instanz eines «Lagerplatz»-Artikels, Behältnis über das
bestehende `location_type='instance'`.**

- Am Artikel ein Marker `is_location` (bzw. ein System-Artikeltyp). Seine Instanzen sind Orte.
- Diese Orts-Instanzen werden über **die EINE Stelle `inventory.in_stock_clauses()`** aus dem Bestand
  ausgeschlossen (Join auf Artikel, `is_location=false`). **Das ist der Schlüssel**: weil Bestand/FIFO/
  Reservierung *alle* diesen einen Helper lesen, greift der Ausschluss überall gleichzeitig – der
  Explosionsradius bleibt an **einer** Stelle.
- Produkt-Instanzen nutzen dann `location_type='instance'` auf eine Orts-Instanz → **`lagerplatz` als
  eigener `location_type` verschwindet**; Bewegung/Scan/Etikett für «instance» existieren bereits, Orte
  erben sie **geschenkt**.
- Hierarchie fällt gratis an: der Standort einer Orts-Instanz ist wieder eine Orts-Instanz.

### Ehrliches Gegengewicht
Vereinheitlichung hat reale Kosten: `quality`/`disposition`, FIFO, Reservierung, Verkauf, Verschrottung,
Prüfung sind für ein Regal **inert** – man schleppt Maschinerie mit, die man mit «if is_location skip»
absichert. `default_receiving_location_id`, `resolve_receiving_location`, der Status-Fluss und der
StorageLocation-Feed hängen heute an der Tabelle. Das ist ein **Wirbelsäulen-Umbau**, kein kleiner.

### Warum die «Marker + eine Klausel»-Form trotzdem elegant ist
Du bekommst die echten Preise der Vereinheitlichung (ein Feed; QR/Scan/Bewegung/Hierarchie geschenkt;
Instanz-in-Instanz-Lagerbaum) durch **ein Boolean + eine Klausel**, während der **eine Stock-Helper als
Engstelle** den Schaden einschliesst. Reservierung/FIFO/Verkauf werden **nicht** herausgerissen – sie
sehen Orts-Instanzen schlicht nie, weil am *einen* Bestands-Tor gefiltert wird.

### Phasenplan (empfohlen – grenzgenial, aber nicht klein)
- **Phase 1 (mittel, reversibel):** `article.is_location` + Ausschluss in `in_stock_clauses` +
  Orts-Instanzen als Bewegungsziel via `location_type='instance'` zulassen. StorageLocation läuft
  **parallel** weiter.
- **Phase 2 (gross):** bestehende StorageLocations zu Orts-Instanzen migrieren, `location_type` auf
  `instance|user` verschlanken (`lagerplatz` raus), Tabelle/Feed/Router abbauen.

### Aufwand
**Gross** (Wirbelsäule) – aber der **Phase-1-Schnitt ist mittel und reversibel**. Empfehlung: Phase 1
bauen, live erproben, dann über Phase 2 entscheiden.

### Offene Fragen
- Braucht ein Ort einen Freigabe-Status (draft/released) wie heute, oder genügt «existiert»? → vermutlich
  genügt «existiert» (evtl. `disposition='in_stock'` als «nutzbar»).
- Ein generischer «Lagerplatz»-Artikel oder mehrere Typen («Regalfach», «Palettenstellplatz»,
  «Behälter»)? → mit einem starten, Typen bei Bedarf.

---

## Empfehlung in einem Satz je Thema
- **D:** Zeiger am Unternehmen auf die gültige (unveränderliche) Dokument-Instanz – kein Verschrotten,
  kein Ersetzen. *(klein–mittel, klar empfohlen)*
- **E:** **Bestandsgetriebener** Meldebestand über `ensure_supply` bauen (nicht Zeit-Cron); Ablaufdatum
  als separater Haltbarkeits-Sweep, der den Bestand senkt und denselben Auslöser füttert. *(mittel)*
- **F:** Vereinheitlichen über **`is_location` + eine Klausel in `in_stock_clauses`**, phasenweise;
  Phase 1 zuerst. *(Phase 1 mittel, Gesamt gross)*
