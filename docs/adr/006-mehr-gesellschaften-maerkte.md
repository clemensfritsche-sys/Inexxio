# ADR 006 – Mehr-Gesellschaften & Weltmärkte: «wer fakturiert wird abgeleitet, nicht gewählt»

> ## Kopfstatus (August 2026): **teilweise gültig**
> **Gültig**: die Gebietskarte (`company_territories`, `services/geography.py`, die
> Weltkarte am Unternehmens-Datensatz) und die Auflösung Land → Region → Besitzer.
> **Entfallen**: alles, was am Verkauf hing – die fakturierende Gesellschaft am Beleg
> (`sales.seller_company_object_id`), der Versand-Absender und die Steuer-Anbindung. Die
> Gebietskarte beantwortet damit heute eine Frage, deren Konsequenz erst wieder entsteht,
> wenn es Belege gibt; sie steht bewusst weiter, weil sie die Aufteilung selbst hält.


Status: umgesetzt (Slice 1: Gebietskarte + Auflösung · Slice 2: Beleg-/Versand-Identität ·
Slice 3: Land-Ausnahmen + «Fakturiert durch» am Auftrag) · Datum: 2026-07-30

## Kontext

Ein produzierendes KMU verkauft weltweit, hat aber (heute) nur **eine** physische Präsenz
(CH). Es soll Aussenstellen/Gesellschaften abbilden können (z. B. eine US-Inc. ab genügend
Umsatz), **ohne** ein zweites ERP, eine zweite Website oder einen zweiten Produktkatalog –
das ist das harte No-Go. Mehrere Gesellschaften sind **Daten im einen System**.

Die verwirrende Frage «brauche ich in jedem Land, in dem ich verkaufe, eine Gesellschaft?»
löst sich, sobald man **fünf Konzepte trennt**, die sich wie eins anfühlen:

| Konzept | Was | Wie viele |
|---|---|---|
| **Gesellschaft** (juristische Einheit) | eigene Rechtsperson, Steuer-ID, Bank, Bücher | so **wenige wie möglich** |
| **Markt** (Kundensitz) | wo der Kunde ist | global |
| **Steuer-Registrierung** (MWST/OSS/Sales-Tax) | Recht/Pflicht, Steuer zu erheben | nach Bedarf – **ohne** dort zu gründen |
| **Warenort** (Fulfillment) | von wo die Ware abgeht | = Zahl der Lager |
| **Fakturierende Gesellschaft** (Seller of Record) | wer die Rechnung stellt | **abgeleitet** |

**Verkaufen ≠ Gesellschaft gründen.** Eine CH-AG kann als Exporteur in 120 Länder verkaufen
(Kunde = Importeur, 0 % Export). Man gründet eine zweite Gesellschaft nur bei echter
**Substanz/Nexus** (Lager, Personal, Betriebsstätte) oder wenn ein Markt es erzwingt
(US-Credibility/Banking/Sales-Tax). Der «Mittelsmann-Trick» (CH fakturiert alles, US-Lager
verschleiert die US-Steuer) ist **kein** Steuer-Shortcut – US-Bestand erzeugt US-Nexus für
den Warenbesitzer, egal wer fakturiert; das fangen Betriebsstätten-/Verrechnungspreis-Regeln.
Sauber ist entweder **reiner Export** (keine US-Substanz) oder die **US-Inc. als Prinzipal**
(mit Substanz, Intercompany) – nichts dazwischen.

## Entscheidung

### 1. Gebietsaufteilung: die Welt gehört immer jemandem (Totalität)

Die Welt ist in **feste Regionen** partitioniert (`services/geography.REGIONS`: NAM, EUR,
ASIA, LATAM, AFR, MEA, OCE). **Jede Region gehört genau EINER Gesellschaft.** Der **Betreiber**
(die Gesellschaft, die die eine Website vertritt) besitzt per Default **alles**; andere
Gesellschaften «beissen sich» einzelne Regionen ab (`company_territories` hält NUR diese
Abweichungen). Ein Land, das keiner Region zugeordnet ist, fällt ebenfalls auf den Betreiber.
So gehört **jeder Fleck der Erde jemandem** – es kann nie «kein Besitzer» geben.

Granularität ist die **Region** – die ~250 Länder muss niemand pflegen; das Beispiel
«CH bedient Europa+Asien, US bedient Amerika» ist ohnehin Region-Ebene. **Ein einzelnes Land
kann davon abweichen** (Slice 3): «Europa gehört der GmbH, Liechtenstein aber der Schweizer AG».
Das ist kein zweiter Mechanismus, sondern **derselbe Anspruch feiner geschnitten** – Region wie
Land stehen als Gebiets-Code in derselben Tabelle, der Unterschied ist aus der **Form**
abgeleitet (ISO-2 hat 2 Zeichen, jeder Regions-Code ≥ 3 → kollisionsfrei per Konstruktion,
`geography.is_country_code`). Vorrang: **Land ≻ Region ≻ Betreiber**. Gepflegt wird nur, was
tatsächlich abweicht: wird ein Gebiet der Gesellschaft zugewiesen, der es ohnehin zufiele, wird
die Zeile **gelöscht** statt eine wirkungslose Ausnahme zu speichern.

### 2. Seller of Record wird ABGELEITET (nicht per Auftrag gewählt)

Die fakturierende Gesellschaft folgt aus dem **Kundenland** – wie in diesem System alles
Wichtige abgeleitet wird (Subjektart, Transportklasse, Bereitstellung). Die EINE Auflösung ist
`services/sites.company_for_country(country)`: **Land → Region → Territorium-Besitzer →
Betreiber-Fallback** (rein lesend, Pflicht in fremden Transaktionen).

**Kein Dropdown, kein nachträglicher Wechsel** wie beim Transportmodus: die Verkaufs-
gesellschaft muss **vor der Zahlung feststehen** (Rechnung, Steuer, Währung, Zahlungskonto
hängen daran). Sie gehört darum in dieselbe Kategorie wie der Preis-/Währungs-Snapshot – sie
**friert bei der Freigabe/Zahlung ein** (Slice 2: `sales.seller_company_object_id`). Ein
Override wäre höchstens im **Entwurf** denkbar; heute (eine reale Gesellschaft) gibt es nichts
zu overriden.

### 3. Welche Adresse ist ausschlaggebend – getrennt je Frage

| Frage | Ausschlaggebend |
|---|---|
| **Fakturierende Gesellschaft** (Seller of Record) | **Rechnungsadresse** (Sitz/Domizil des Kunden) |
| **Steuersatz** (MWST/Sales-Tax bei Waren) | **Lieferadresse** (ship-to) – macht **Stripe Tax** |
| **Beleg-Kopf / B2B-Reverse-Charge** | Rechnungsadresse + VAT-ID |
| **Warenort** (Absender/Versand) | wo der Bestand liegt (ADR 005) |

Die Rechnungsadresse (rechtlicher Sitz) ist stabil und definiert die kaufmännische Beziehung;
die Steuer folgt getrennt der Lieferadresse. So kann ein deutscher Kunde mit Lieferung in die
Schweiz sauber behandelt werden (Seller nach DE-Sitz, Steuer nach CH-Lieferung).

### 4. Was global bleibt

- **Eine Website / ein Impressum**: der **Betreiber** ist die ausweisende Rechtsperson,
  wechselt NICHT nach Besucherland (`GET /admin/settings/public`). Nur die **Rechnung** hat je
  nach Seller einen anderen Aussteller.
- **Belegnummer global** (ein Nummernkreis) – rechtlich zulässig (Eindeutigkeit + Aussteller-
  Identifikation genügen); je-Gesellschaft-Kreise würden `resolve_object_type`/QR-Scan/globale
  Objektnummer-Eindeutigkeit zerlegen.
- **Ein Produktkatalog, ein Login, ein Shop.**
- **Zahlungskonto**: je Gesellschaft mit Rückfall auf **EIN geteiltes Stripe-Konto** (ein
  echtes US-Konto erst bei realer US-Gründung).

## Umsetzung (Slices)

**Slice 1 (dieser Deploy) – Fundament, ohne Geld-/Beleg-Risiko:**
- `services/geography.py` (Regionen + ISO-2-Land→Region, unbekannt → Betreiber).
- `models.CompanyTerritory` (`company_territories`, Region unique) + Migration 092
  (idempotent, downgrade; neue Tabelle → `create_all` deckt sie im Lifespan).
- `sites.company_for_country` / `territory_map` / `set_territory`.
- Admin `GET/PUT /admin/territories`; Frontend **abstrakte Weltkarte** (Region-Kacheln,
  Klick-Zuweisung, Betreiber-Default) im Unternehmens-Reiter «Gebiete».

**Slice 2 – Beleg-/Versand-Identität (berührt Rechnung/Versand):**
- `sales.seller_company_object_id` (Snapshot bei Freigabe/Zahlung) + Ableitung aus der
  Kunden-Rechnungsadresse.
- Beleg-Briefkopf (`routers/documents.py:_company`) und **Versand-Absender**
  (`services/logistics.py`) nehmen den **Seller** statt immer den Betreiber.

**Slice 3 – sichtbar + feiner:**
- **«Fakturiert durch» am Auftrag** (`OrderResponse.seller_company_object_id/_name`): die
  abgeleitete Gesellschaft steht in der Auftragsspezifikation, Objektnummer klickbar. **Nur bei
  einem Verkauf/einer Retoure** gesetzt (ein Produktions-/Beschaffungsauftrag hat keinen Kunden,
  also keinen Fakturierenden) und nur fürs Personal sichtbar – es ist eine interne Buchungs-
  Angabe. Wer fakturiert, war bis dahin nur im PDF sichtbar; ab jetzt sieht man es, **bevor**
  der Beleg entsteht.
- **Land-Ausnahmen** (`geography.is_country_code`/`normalize_area`, `sites.country_map`/
  `_default_owner_id`): Region-Kachel oder Land, EIN Panel, EINE Zuweisung. Die Oberfläche
  leitet «ist Ausnahme» daraus ab, dass der Besitzer eines Landes vom Besitzer seiner Region
  abweicht – **kein zweites Flag**, das auseinanderlaufen könnte. Ländernamen liefert
  `Intl.DisplayNames` im Browser (keine zweite Länderliste im Repository).

## Bewusst (noch) NICHT gebaut

- **Steuer-Origin je Gesellschaft**: `services/tax.py` verankert die Origin hart in CH
  (`is_ch_area`, CH-Sätze). Für eine nicht-CH-Gesellschaft (US/DE) stimmt die **Anzeige**-
  Steuer nicht; die **reale** Steuer rechnet Stripe Tax destinationsbasiert korrekt. Origin
  je Seller kommt mit dem Steuerregime je Gesellschaft (Step 6, braucht ohnehin eine reale
  zweite Gesellschaft).
- **Intercompany** (CH produziert → US verkauft, Transferpreis) – der schwere Teil, erst mit
  realer US-Substanz.
- **Eigenes Stripe-Konto je Gesellschaft** – heute ein geteiltes Konto (ein Merchant-of-Record).
- Ein **Kunden-Währungsumschalter** im Shop (Backend trägt `currency` bereits).
- **Sub-Land-Gebiete** (US-Bundesstaat, CH-Kanton) – die Steuer je Staat rechnet ohnehin
  Stripe Tax; ein eigener Seller je Bundesstaat wäre eine Gesellschaft, kein Gebiet.

## Konsequenzen

- Multi-Site fällt **aus der bestehenden Regel heraus**, statt eine zweite zu brauchen: die
  adress-basierte Logistik-Klassifikation (ADR 005) macht einen Transport zwischen zwei
  Gesellschaften mit unterschiedlicher Adresse automatisch zu **Versand**; die Gebietskarte
  liefert nun den **Seller**, der auf Beleg/Absender greift.
- Keine Schema-Bombe: `company_territories` ist eine **neue Tabelle** (kein Spalten-Zusatz auf
  einer bestehenden), damit ausserhalb der Migrations-/Lifespan-Ausfallklasse von 090.
  Gegen echtes Postgres 16 verifiziert (create_all-Pfad, Auflösung, Totalität, Idempotenz,
  Downgrade, Lifespan-Neuschöpfung).
