# ADR 006 – Standort = Halter (der Lagerplatz-Datensatz entfällt)

**Status:** Angenommen · Juli 2026 · Migration `077` · bewusst **nicht rückwärtskompatibel**

## Kontext

Der `lagerplatz` war ein eigenständiger ERP-Datensatztyp (Tabelle, Router, Feed, Detailansicht,
Status-Flow, Ersetzen-Logik) – nur damit eine Instanz sagen kann, *wo* sie liegt. Das ist teuer
für wenig Ertrag: jeder neue Platz braucht einen Datensatz-Lebenszyklus, und ein Artikel trug
zusätzlich einen «Fixierten Standort» (Karten-Picker), obwohl ein Artikel gar kein Ort ist.

## Entscheidung

**Ein Standort ist ein Halter.** Genau vier Arten – drei davon Datensatzobjekte mit
9-stelliger Objektnummer, die vierte eine Adresse direkt am Objekt:

| Typ        | Was                                        | Objektnummer |
|------------|--------------------------------------------|--------------|
| `place`    | Adresse/GPS **inline** (`instances.place`)  | – (das «Blatt») |
| `user`     | Person (Mitarbeiter/Lieferant/Kunde)        | ✓ |
| `instance` | andere Instanz (Behälter, Palette, LKW)     | ✓ |
| `company`  | das Unternehmen selbst (Betriebsadresse)    | ✓ |

Ein **benannter Platz** (Regal A, Wareneingang, LKW 1) ist damit eine ganz normale **Instanz**,
die andere Instanzen hält. Das ersetzt den Lagerplatz vollständig – und ist konsistent mit dem
übrigen Modell: ein Regal *ist* ein Ding, das das Unternehmen besitzt, also ein Artikel + Instanz
(mit Etikett, QR-Code und – falls gewünscht – eigenem Wartungsauftrag).

**Form des Orts = Versand-Adress-Snapshot** (`{name, street1, zip, city, country}` + `lat`/`lng`,
`schemas/place.py`). Damit verarbeiten `logistics.same_place`, `_addr_label` und die gesamte
Versand-Ableitung den Ort **ohne Übersetzung** – eine Form, eine Wahrheit.

## Chargen-Teilmengen: die EINE Regel

`instances.locations` (die mengengenaue Verteilungs-Map, ADR-Vorbild `reservations`) ist nach
**Objektnummer** geschlüsselt – GIN-indiziert, «wer liegt hier» über `locations ? '<nr>'`.

> **Verteilbar sind nur Halter mit Objektnummer (Instanz/Person/Unternehmen).
> Ein `place` hält immer die ganze (Rest-)Menge.**

Das ist keine willkürliche Einschränkung, sondern die ehrliche Abbildung der Wirklichkeit:
**eine Adresse kann zwei Plätze am selben Standort gar nicht unterscheiden** – «Band A» und
«Wareneingang» haben dieselbe Anschrift. Verteilen ist nur auf *benannten* Haltern sinnvoll, und
die tragen alle eine Nummer. Wer 990 Schrauben am Eingang und 10 am Band führen will, nutzt zwei
**Behälter-Instanzen**.

Folge: die Split-Engine (`services/location_split.py`) blieb **unverändert**. Neu sind nur
`is_at` / `set_target` / `set_place` – der Ist↔Soll-Abgleich, dessen Identität bei einem Ort die
**normalisierte Adresse** ist (statt einer Nummer). `move()` weist eine Teilmengen-Verlagerung auf
einen Ort mit einer klaren Meldung ab, statt still etwas Falsches zu tun.

## Konsequenzen

* `storage_locations` ist **weg** (Tabelle, Modell, Schema, Router, Feed-Typ, Registry-Eintrag,
  KI-Tool, Detailansicht, Status-Config). Migration `077` überführt jede Referenz in einen **Ort**
  (Adresse + GPS des Lagerplatzes werden inline übernommen); über mehrere Lagerplätze verteilte
  Chargen werden dabei auf ihren grössten Teilstandort zusammengeführt.
* **Wareneingang** = die **Firmenadresse** (aus den Unternehmens-Stammdaten). Die Zeiger
  `company_settings.default_receiving_location_id` und `purchase_orders.receiving_location_id`
  entfallen. Wohin die Ware im Haus geht, setzt danach die gesperrte Pflicht-Bewegung
  «Wareneingang» (Ziel: Ort | Behälter-Instanz | Unternehmen – eine **Person** ist dort unzulässig,
  das wäre ein Versand).
* **`company` ist neu ein Bewegungsziel** (vorher nur Startort). Nebenbei geschlossen: `company`
  hatte in `target_address` gar keinen Zweig, obwohl `location_kind` es als intern führte.
* **Retoure-Rückbuchung** prüft nicht mehr hart auf `lagerplatz`, sondern auf **Ownership**
  (`logistics.location_kind(...) == 'internal'`) – dieselbe Regel wie der Versand; sie trägt
  automatisch alle vier Halter-Arten.
* **Am Artikel gibt es keinen Standort mehr**: `articles.fixed_location_*` inkl. Karten-Picker ist
  endgültig entfernt. Der `MapPicker` lebt jetzt dort, wo er hingehört – im **Orts-Wähler**
  (`components/erp/place-picker.tsx`) des Bewegungs-Schritts.
* Ein Ort erscheint **nicht** im generischen Rückverweis («wer zeigt auf mich») – sein Halter ist
  kein Objekt. Das ist gewollt und dokumentiert.

## Bewusst nicht gebaut

* **Orte als wiederverwendbarer Katalog** (gespeicherte Adressen zur Auswahl). Wird erst
  interessant, wenn dieselbe Fremdadresse oft wiederkehrt; heute genügt Tippen/Karte, und
  wiederkehrende *eigene* Plätze sind ohnehin Behälter-Instanzen.
* **Verteilung auf Orte** – siehe Regel oben (fachlich nicht unterscheidbar).
* **Automatisches Anlegen einer «Wareneingang»-Behälter-Instanz** beim ersten Start. Der
  Wareneingang ist zunächst schlicht die Firmenadresse; einen benannten Behälter legt an, wer ihn
  braucht.
