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

## Offen: die Tabellen der gelöschten Handels-Module

`purchases`, `invoices`, `payments` — die Module «Beschaffen» und «Verkauf» sind
ersatzlos gelöscht (PROCESS_CORE §9.9a), samt Modellen, Diensten und Endpunkten. **Kein
Modell verweist mehr auf sie**, also kann auch keine `NOT NULL` mehr ein Insert
auflaufen lassen: es schreibt niemand hinein.

**Bewusst nicht mitgedroppt** — dieselbe Regel wie bei den übrigen Alt-Tabellen (siehe
unten): eine Tabelle, die niemand liest, kostet nichts; ihr Drop kostet die Vergangenheit
(bezahlte Rechnungen und gebuchte Zahlungen aus der Zeit vor dem Geldvorgang), er ist
unumkehrbar und verlangt vorher eine Sicherung der **produktiven** Datenbank
(`scripts/dump-db.sh`) — die kann nur jemand mit Zugriff darauf ziehen, nicht eine
Migration.

*Der frühere Punkt «`payments.kind` droppen» geht darin auf: die Spalte fällt mit ihrer
Tabelle, wenn es soweit ist.*

## Offen: `deals.reference` und `deals.note` (Zwei-Deploy-Regel)

Beide haben ihr ORM-Mapping in dieser Runde verloren (Testnotiz #812): niemand wusste, was
in das Referenz-Feld gehört, und die Rechnungsnummer erzeugt der Dienst längst selbst
(`<Auftragsnummer>[-n]`). Damit hatte auch die Handlung `note` keinen Aufrufer mehr.

**Erst im Folge-Deploy droppen** — nicht im selben: sonst liefe die während des
Cloud-Run-Rollouts noch laufende Vorgänger-Revision gegen eine Tabelle ohne sie (die
Ausfallklasse von Migration `090`).

```sql
ALTER TABLE deals DROP COLUMN IF EXISTS reference;
ALTER TABLE deals DROP COLUMN IF EXISTS note;
```

*Nicht zu verwechseln mit `deal_entries.reference` / `.note`* — die tragen Rechnungsnummer
bzw. Zahlungszweck einer Geld-Zeile und bleiben.

## Erledigt: die toten Spalten sind gedroppt (Migration `120`)

Die **Zwei-Deploy-Regel** ist damit einmal komplett durchlaufen: im Aufräum-Deploy
verloren 22 Spalten ihr ORM-Mapping, im Folge-Deploy sind sie gefallen. Beides in einem
Deploy hätte die während des Cloud-Run-Rollouts noch laufende Vorgänger-Revision
getroffen – die Ausfallklasse von Migration `090`.

Betroffen waren `articles` (Beschaffungs-/Verkaufsfelder), `company_settings`
(Zahlungsanbieter, Shop-Währungen, hCaptcha, Rechtstexte, Infrastruktur-Kosten,
Wareneingangs-Ort), `user_profiles.stripe_customer_id` und `purchases` (Reste der
Umbauten 115/116). Geprüft statt angenommen: keine stand mehr in `Base.metadata`.
Verifiziert von null · idempotent · downgrade · über das Lifespan-Netz.

### Offen: die Tabellen der entfernten Bereiche

`events`, `article_prices`, `article_sales_audience`, `fx_rates`, `ai_actions`,
`document_files`, `document_links`, `document_blobs`, `document_signoffs`,
`document_acknowledgements`.

**Bewusst nicht mitgedroppt.** Eine Spalte, die niemand liest, kostet nichts; ein
Tabellen-Drop kostet die Vergangenheit, und er ist unumkehrbar. Diese Tabellen halten
Historie (in `document_blobs` liegen die Dateien selbst), und der Drop verlangt vorher
eine Sicherung der **produktiven** Datenbank (`scripts/dump-db.sh`) – die kann nur
jemand mit Zugriff darauf ziehen, nicht eine Migration.

**Reihenfolge, wenn es soweit ist:** sichern → prüfen, dass die Sicherung lesbar ist →
droppen. Kein Modell verweist mehr auf sie (geprüft), der Nummernraum hängt seit dem
Aufräumen an der **Registry** statt an einer Modellspalte – ein Drop kann also keine
Objektnummer ein zweites Mal vergeben lassen.

## Erledigt: die beiden Befunde der Aufräumrunde

**1. Die Modul-Vollständigkeitsprüfung im Browser ist gelöscht.**
Entschieden wurde nach dem Messen, nicht nach dem Gefühl: die «freundliche Hälfte» lief
längst – nur über den **Server**. Beide Entwürfe (Artikel wie Auftrag) fragen
`POST …/validate`, dessen `missing` im Hinweis des Freigabe-Knopfes steht, und
`validate_draft` schickt die Modul-Konfiguration durch dieselbe `Module.clean_config`,
die auch die Freigabe abweist. Gemessen antwortet der Server dort «Lieferant 100000001
braucht eine Bestellangabe – seine Artikelnummer oder den Link…», wo die Browser-Fassung
«Bestellangabe fehlt» sagte: die zweite war also nicht nur doppelt, sondern **schlechter**.
Die beiden Wächter zeigen jetzt auf die **Server**-Regel und sind gegen ihre Bug-Form
gegengeprüft – einer war dabei stumpf (`assert problems` war schon von der ohnehin
gemeldeten fehlenden Einzelinstanz erfüllt) und prüft jetzt die **Differenz**.

**2. Der seitliche Überlauf der Startseite ist behoben.**
Gemessen 0 px bei 1440 · 1280 · 1024 · 834 · 375 · 320 px (vorher 62 px bei 320, 7 px bei
375). Die im letzten Bericht vermutete Lösung `minmax(0, 1fr)` war **nicht** die richtige:
sie lässt die Spalte schrumpfen, aber «Kernkompetenzen» ist bei `--h2` (dort 28 px) ein
unteilbares Wort von ~234 px – der Überlauf wäre nur vom Raster in den Text gewandert.
Der Kopf steht jetzt unter 640 px **einspaltig** (dieselbe Grenze wie `.ix-wrap`), damit
der Titel die vollen 280 px bekommt. Ab 640 px ist das Bild unverändert zweispaltig.

