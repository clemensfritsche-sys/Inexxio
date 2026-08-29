# Backlog

Offene Themen, die bewusst **nicht** sofort umgesetzt werden. Jeder Eintrag nennt Ziel,
Vorschlag und – wichtig – was dagegen spricht bzw. noch zu entscheiden ist.

---

## 1. Standort-Modell überdenken: «Referenz oder Adresse» (zwei Fälle statt vier)

**Status:** Konzept · noch nicht entschieden
**Vorgeschichte:** Ein erster Anlauf (PR #103, Migration `077`) hat den Lagerplatz-Datensatztyp
sofort ganz entfernt und dabei die Instanz-Ansicht zerschossen → **zurückgerollt** (PR #104).
Der Lagerplatz **bleibt vorerst bestehen**. Ein neuer Anlauf braucht eine **neue**
Revisionsnummer (077 ist als No-op verbrannt) und muss **additiv** vorgehen.

### Das Ziel
Man will jederzeit wissen, **wo sich ein Datensatz befindet** – bei einer Person die
Lieferadresse, beim Unternehmen die Firmenadresse, bei einer Instanz: irgendwo in der Halle,
in einem Behälter, verbaut in einem Produkt, bei einer Person, unterwegs im LKW.

### Die Kritik am heutigen Modell
Der Standort-Typ ist heute eine Aufzählung (`lagerplatz | user | instance | company`), die so
tut, als wären das vier gleichrangige Dinge. Sind sie nicht – es sind **zwei Sorten**:

* **Objekte mit 9-stelliger Objektnummer** (Lagerplatz, Person, Instanz, Unternehmen)
* **eine rohe Adresse** (heute gar nicht abbildbar)

Daraus folgt: **der Typ ist redundant.** Objektnummern sind global eindeutig, und die Registry
(`services/objects.resolve_object_type`) weiss bereits, was `100000042` ist. `location_type`
neben `location_id` zu speichern verdoppelt eine Information, die die Nummer schon trägt →
Drift-Risiko, und jeder neue Halter-Typ zwingt zu einer Enum- plus Sechs-Stellen-Änderung.

### Der Vorschlag
> **Ein Standort ist entweder eine Referenz auf ein anderes Objekt – oder eine Adresse.**

```
standort = → Objektnummer   (irgendein Objekt; Typ wird abgeleitet, nicht gespeichert)
         | → Adresse/GPS    (das Blatt, Ende der Kette)
         | → nichts         (unbekannt – ehrlich)
```

Die Eigenschaft, die das Modell trägt:

> **Was einen Standort haben kann, kann auch Standort sein.**
> Instanz, Person, Unternehmen sind zugleich Halter und Gehaltene; die Kette endet **immer**
> bei einer Adresse.

### Die eine Regel für Menschen
> **Alles, was du benennen, etikettieren, scannen oder einzeln bewirtschaften willst, ist eine
> Instanz. Eine Adresse ist nur der geografische Endpunkt.**

Damit löst sich «irgendwo in der Halle»: *Halle Nord* und *Halle Süd* haben dieselbe Anschrift
und sind als Adressen **nicht unterscheidbar** → sie sind Behälter-Instanzen (mit Nummer,
Etikett, QR). Die Adresse ist erst die Ebene darunter.

### Was man dadurch gewinnt: die Kette als Antwort auf «wo genau?»
```
Schraube  100000042
  ↳ in Behälter 100000007
      ↳ in Halle Nord 100000003
          ↳ Musterstrasse 1, 8000 Zürich
```
Immer zwei abgeleitete Aussagen: **Halter** (unmittelbar) und **wo wirklich** (aufgelöste
Endadresse) – oder ehrlich «unbekannt».

Der Beleg, dass das Modell trägt: **ein LKW ist eine Instanz mit GPS-Adresse.** Ändert sich
seine Position, wandert *alles darin* automatisch mit – ohne eine Zeile Sonderlogik für
«Transit». Analog fällt «wer ist wo» (Mitarbeiter → Halle 2) gratis an.

### Eventualitäten-Check
| Fall | Abbildung |
|---|---|
| irgendwo in der Halle | → Halle-Instanz |
| im Behälter, der in der Halle ist | → Behälter → Halle → Adresse |
| verbaut im Produkt | → Produkt-Instanz |
| bei einer Person / beim Kunden / Lieferanten | → Person bzw. Unternehmen |
| unterwegs im LKW | → LKW-Instanz mit GPS |
| Baustelle ohne Datensatz | → direkt Adresse |
| verschrottet | → kein Standort (der Endzustand *ist* die Aussage) |
| Charge auf mehrere Plätze verteilt | → Map nach Objektnummer; Adresse = ganze Menge |

### Bewusst verworfen
* **Ort als eigenes Objekt** – maximal symmetrisch, holt aber genau den Lagerplatz-Datensatz
  zurück, den man loswerden will.
* **Eigene `object_locations`-Tabelle** – flexibler, kostet überall einen Join.
* **Standort rein aus dem Ereignis-Strom ableiten** (REA-konsequent, «wo war es am 3. Mai?») –
  teuer bei jedem Lesezugriff. Die Events protokollieren Bewegungen bereits, die Zeitreise ist
  also **später nachrüstbar**, ohne das Modell zu ändern.

### Offene Entscheidungen
1. Soll eine **Person** einen Standort-Ref bekommen («wer ist wo»)? Billig, aber ein neues
   Konzept für die Belegschaft.
2. **Wareneingang** als benannte Behälter-Instanz (scannbar/etikettierbar) oder weiterhin nur
   die Firmenadresse?
3. **Reihenfolge:** erst additiv Adresse + Unternehmen als Halter einführen (Lagerplatz läuft
   parallel weiter), Lagerplatz erst danach in einem eigenen, separat testbaren Schritt ablösen.

### Lehren aus dem gescheiterten ersten Anlauf
* **Additiv vor destruktiv.** Neue Halter-Art einführen und *live testen*, bevor der alte
  Datensatztyp verschwindet.
* **Migration und Code entkoppeln.** `start.sh` startet uvicorn auch bei fehlgeschlagener
  Migration – neue Pflichtspalten gehören darum **immer** ins Spalten-Sicherheitsnetz
  (`main.py: _COLUMN_SAFETY_NET`), sonst läuft der Dienst an und scheitert erst beim Datenzugriff.
* **Migrationserfolg verifizieren**, nicht aus einem grünen Deploy schliessen.

---

## 2. Chargen-Teilmengen an mehreren Plätzen

**Status:** heutige Lösung trägt · Feinschliff offen

**Heute:** `instances.locations` ist eine mengengenaue Map, geschlüsselt nach **Objektnummer**
(GIN-Index, «wer liegt hier» via `locations ? '<nr>'`), ohne die Instanz zu teilen und ohne neue
Objektnummer. Verteilt wird **auftragsgetrieben** über den Bewegungs-Schritt.

**Die Regel, die daraus folgt (und beim nächsten Anlauf explizit werden sollte):**
> Verteilbar ist nur auf Halter **mit Objektnummer**. Eine reine Adresse hält immer die ganze
> (Rest-)Menge.

Der Grund ist fachlich, nicht technisch: eine **Adresse kann zwei Plätze am selben Standort
nicht unterscheiden**. Wer im Haus verteilen will, nutzt Behälter-Instanzen.

**Offen:** ob die Regel als Guard erzwungen wird (klare Fehlermeldung statt stillem Fehlverhalten)
– das war im zurückgerollten Anlauf enthalten und sollte beim nächsten Mal wieder mitkommen.

## Folge-Deploy: Spalten droppen (Aufräumen August 2026)

Die Zwei-Deploy-Regel: **erst** verliert eine Spalte ihr Mapping (dieser Deploy), **dann**
wird sie gedroppt. Beides in einem Deploy trifft die während des Cloud-Run-Rollouts noch
laufende Vorgänger-Revision, die sie noch liest – die Ausfallklasse von Migration 090.

Alle unten genannten Spalten sind seit dem Aufräumen **nicht mehr gemappt**; keine trägt
eine `NOT NULL`-Sperre ohne DB-Default (geprüft), Inserts laufen also unverändert. Der
Drop ist eine gewöhnliche Migration im **nächsten** Deploy – nicht dringend, aber fällig.

| Tabelle | Spalten |
|---|---|
| `articles` | `procurement_mode`, `default_supplier_id`, `default_webshop_url`, `sales_published`, `sales_visibility`, `sales_fulfillment`, `sales_content` |
| `company_settings` | `logo_path`, `stripe_publishable_key`, `hcaptcha_site_key`, `shop_currencies`, `shop_country_currency`, `shop_default_currency`, `payments_provider`, `pricing_zone_factors`, `infra_monthly_chf`, `legal_documents`, `default_receiving_location_id` |
| `user_profiles` | `stripe_customer_id` |
| `purchases` | `reference`, `quantity`, `article_id`, `due_date`, `ordered_for` |

Dazu die **Tabellen** der entfernten Bereiche, die nur noch Daten halten:
`events`, `article_prices`, `article_sales_audience`, `fx_rates`, `ai_actions`,
`document_files`, `document_links`, `document_blobs`, `document_signoffs`,
`document_acknowledgements`. Vor dem Drop sichern (`scripts/dump-db.sh`) – die Historie
darin ist der einzige Grund, warum sie noch stehen.
