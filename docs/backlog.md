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

## Offen: Drops im Folge-Deploy (Zwei-Deploy-Regel)

Mapping entfernt (Runde 28.10.2026), Spalten stehen in `PENDING_DROP`; die Migration droppt sie
im nächsten Deploy:

```sql
ALTER TABLE user_profiles DROP COLUMN department, DROP COLUMN job_title,
  DROP COLUMN language, DROP COLUMN notification_email, DROP COLUMN notification_inapp;
```

## Erledigt: die letzten Drops (Migration `161`)

`company_settings.google_maps_api_key` (der Schlüssel kommt aus dem Deploy) und
`user_profiles.newsletter_opt_in` (die Übernahme-SQL steht wörtlich in `153`, Netz und
`legacy_repair_sql` sind weg). `PENDING_DROP` ist leer.

## Erledigt: die ausstehenden Drops (Migration `160`)

`voucher_documents.html` (seit `158` im Dokument), `user_profiles.employment_start_date` und
`.weekly_hours` (seit `154` im Vertrag).

## Erledigt: Spalten und Tabellen der entfernten Bereiche gedroppt (Migration `152`)

Der zweite Schritt der **Zwei-Deploy-Regel** für alles, was hier als «Folge-Deploy» stand –
nach **Sicherung der produktiven Datenbank** und ausdrücklicher Freigabe (Cleanup Oktober
2026, Paket F/G). Geprüft statt angenommen: keine der Spalten und Tabellen stand noch in
`Base.metadata`. Seither hält der Wächter
`tests/test_schema_is_built_by_the_migrations.test_nothing_is_left_that_no_model_knows`
die Rückrichtung fest – nach `upgrade head` steht nichts, das kein Modell kennt; eine
Spalte zwischen den beiden Schritten wird dort in `PENDING_DROP` vorgemerkt.

**60 Spalten:**

| Tabelle | Spalten | Herkunft |
|---|---|---|
| `articles` | `landed_unit_cost`, `status`, `is_location` | Einstandspreis ohne Schreiber (B-08) · Zustand = Projektion von `replaced_by_id` (#773, B-20) · Lagerplatz-Kennzeichen |
| `company_settings` | `plausible_domain`, `article_names`, `bank`, `bic_swift`, `qr_iban_encrypted`, `share_capital`, `trade_register_nr`, `trade_register_canton`, `default_payment_days`, `default_skonto_days`, `default_skonto_pct`, `vat_method`, `vat_period`, `oss_active`, `oss_reg_number`, `vies_active`, `website` | Plausible (E5) und die Felder, die `sites.ENTITY_FIELDS` längst gestrichen hat |
| `user_profiles` | 4× `bank_*`, 6 Anschriftsfelder, 7× `invoice_*` + `invoice_email`, `company_billing_email`, `invoice_company`, `account_type`, `invoice_same_as_shipping`, 8× `ship_*`, `terms_accepted_at`, `terms_version` | CRM Schritt 1b/2 (Adressbuch), #1042/#1043, E2 |
| `voucher_entries` | `kind`, `due_on`, `vat`, `service_date`, `reverses_id`, `charge_id`, `reason` | seit Migration 138 ist der Beleg die Rechnung |
| `vouchers` | `issued_on` | #1047 – gestellt ist draussen |

**17 Tabellen:** `events`, `article_prices`, `article_sales_audience`, `fx_rates`,
`ai_actions`, `document_files`, `document_links`, `document_blobs`, `document_signoffs`,
`document_acknowledgements`, `purchases`, `invoices`, `payments`, `deals`,
`deal_entries`, `message_replies`, `voucher_allocations`. Die Objektnummern von
`document_files` sind vorher in die Registry (`objects`) übernommen worden – der
Nummernraum vergibt keine davon ein zweites Mal.

**Mit ihnen gefallen** (sie fassten eine gedroppte Spalte oder Tabelle an und wären beim
nächsten Start gescheitert): `domain/voucher.invoice_backfill_sql` und `magnitude_sql`,
`domain/communication.topic_repair_sql`, `services/address_book.migrate_sql`,
`business_sql` und `OLD_COLUMNS` (ihr SQL steht seither in den Migrationen 138/141/143/148
selbst), alle vier Einträge im `_NULLABLE_SAFETY_NET`, der Eintrag
`articles.landed_unit_cost` im `_COLUMN_SAFETY_NET` (er hätte die Spalte bei jedem Start
wieder angelegt) und der Alias `GET /erp/orders/voucher-parties`.

**Bewusst geblieben** (Entscheid E7): `articles.safety_stock`, `min_order_qty`,
`supplier_article_number`, `user_profiles.language`, `notification_email`,
`notification_inapp` – gemappt und vorgemerkt.

**Unumkehrbar**: der Rückweg der Migration legt nichts wieder an; die Daten liegen in der
Sicherung.

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


## Erledigt: der Zahlungsdienst ist eingerichtet (05.09.2026)

Alles gemessen, nichts vermutet:

| | |
|---|---|
| `STRIPE_SECRET_KEY` · `STRIPE_WEBHOOK_SECRET` | im Secret Manager (die Deploy-Zeile referenziert sie, der Deploy läuft) |
| Webhook-Adresse | `https://inexxio-dev.web.app/api/v1/payments/webhook` |
| Webhook-Ereignisse | `payment_intent.succeeded` + `charge.refunded` — **umgestellt, nicht neu angelegt**, das Signing Secret bleibt damit gültig |
| `STRIPE_PUBLISHABLE_KEY` | als **einfache Variable** in `--set-env-vars` (`docs/stripe-setup.md` §5) |

Der letzte Punkt war der einzige, den kein Werkzeug lesen konnte — Stripe bietet für den
*Publishable Key* keine API, er steht nur im Dashboard. Er ist **kein Geheimnis** (er
steht im Browser jedes Zahlenden, wie `NEXT_PUBLIC_FIREBASE_API_KEY` in derselben Datei),
also kostet er eine Zeile statt zweier `gcloud`-Befehle und einer IAM-Bindung.

## Offen und benannt: die Zahlungsarten sind eine Konto-Entscheidung

Keine Code-Frage — unser Code fragt `automatic_payment_methods` und führt bewusst **keine
eigene Liste**. Gemessen im Sandbox-Konto (`payment_method_configurations`, 05.09.2026):

- **TWINT ist aus** (`available: false` — Stripe schaltet es frei, wenn das Konto
  aktiviert ist). Karte ist an, bezahlen funktioniert also.
- **An sind daneben** Klarna, Link, Amazon Pay, Bancontact, EPS, BLIK, MB Way, Pix,
  Satispay, Apple Pay — für ein Schweizer B2B-ERP kaum passend, und sie stehen dem
  Zahlenden alle im Formular.

Beides ist ein Schalter unter **Settings → Payments → Payment methods**.

## Offen und benannt: der Status `Verkauft` ohne Schreiber

Mit dem Modul «Ausliefern» ist der einzige Schreiber von `verkauft` entfallen. Der Status
**bleibt** im `CATALOG`, und das ist kein Versehen: der Katalog ist zugleich das Vokabular
des append-only Ereignis-Logs (`flow._left_with`, die Bestandsleiste). Ihn zu streichen
machte Vergangenes unlesbar.

Wer ihn eines Tages wirklich entfernen will, misst zuerst – `SELECT count(*) FROM
instance_units WHERE status = 'verkauft'` **und** dasselbe über `process_events` – und
entscheidet dann. Eine Migration, die bestehende Zeilen «heilt», ist genau die
Fehlerklasse aus Migration 110.

## Die offene-Posten-Liste je Partner (und mit ihr die Sammelzahlung)

**Benannt, nicht versteckt** (PROCESS_CORE §9.15q). Seit eine Rechnung *der Beleg* ist,
liegen zwei Rechnungen desselben Kunden zwingend in **verschiedenen Modulen** – meist in
verschiedenen Aufträgen. Zwei Fragen haben damit keinen Ort mehr an *einem* Modul:

1. **«Was schuldet mir dieser Kunde insgesamt?»** Rechnung 10'000 (bezahlt) steht in Modul
   A, Gutschrift 600 (offen) in Modul B. Beide für sich sind korrekt; die Summe ist
   **Debitorenbuchhaltung**.
2. **Eine Überweisung über mehrere Rechnungen.** Auf dem Kontoauszug steht eine Zeile. Die
   modulinterne Aufteilung (#1010–#1017) beantwortete das innerhalb eines Belegs und ist
   gegenstandslos geworden; die **modulübergreifende** kommt mit der Liste zurück.

Der Umbau verursacht das nicht – er macht es sichtbar nötig: spätestens beim zweiten
Auftrag je Kunde wäre es ohnehin fällig. Bis dahin sind es zwei erfasste Zahlungen statt
einer: eine Zeile mehr auf dem Bildschirm, **keine falsche Zahl**.

## Der reine Rechnungsfehler nach dem Versand

Er braucht heute einen Auftrag über die **betroffenen Stücke** – das funktioniert und
dokumentiert sogar, worauf sich die Korrektur bezieht, fühlt sich aber schief an. Es ist
derselbe offene Punkt wie **«ein Beleg ganz ohne Ware»** (Miete, Lohn, Gebühr):
`assert_releasable` verlangt mindestens eine Einzelinstanz, also kann das System das auch
ohne diesen Umbau nicht. Fällt die Regel eines Tages, fällt sie für beide.
