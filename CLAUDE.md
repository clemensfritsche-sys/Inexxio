# INEXXIO – Enterprise Central System

> **Diese Datei beschreibt den IST-STAND – sonst nichts.** Wie das System so geworden ist
> (die Runden, Testnotizen, Messungen, verworfenen Anläufe), steht in
> **`docs/history/2026-10-claude-md-chronik.md`** (die frühere CLAUDE.md, wörtlich).
> **Ein Rundenbericht gehört nach `docs/history/`, nicht in CLAUDE.md.**
>
> **Lesereihenfolge:** `CLAUDE.md` (Kontext, Regeln, was gebaut ist) → `PROCESS_CORE.md`
> (die Prozesslogik, verbindlich vor jeder Arbeit am Prozess; die Zeichenregeln des
> Prozessbilds in `docs/prozessbild.md`) → `SYSTEM_LOGIC.md` (die
> Regeln als prüfbare Sätze, Sackgassen-Analyse) → `docs/attic.md` (was entfernt ist und
> welche Entscheidung darin steckt) → `docs/history/` (warum es so wurde). Dazu
> `backend/CLAUDE.md`, `frontend/CLAUDE.md`, `website/WEBSITE_PLAN.md` für die Teilprojekte.
> Anforderungen (Zielbild, mit Kopfstatus): `docs/Lastenheft_v1.0.md`.
> **Entscheide des Inhabers** (bleibt so · wird umgesetzt · offen): `docs/aenderungsakte.md`.

## Was ist Inexxio?
Zentrales Unternehmenssystem für ein produzierendes Schweizer KMU (AG, Maschinenbau,
ca. 10 Mitarbeitende, ca. 1'000 Artikel). Ziel ist Website + ERP + Buchhaltung + HR +
Qualitätsmanagement; **gebaut sind heute das Fundament, der Prozess mit fünf Modulen, das
CRM mit Kommunikation, die Zeiterfassung, die Dokumente (eine Ablage) und die öffentliche
Website** (siehe «Status»).

## Architektur

**Im Einsatz** – verdrahtet und in Betrieb:
```
Frontend:  Next.js 16, React 19, TypeScript strict, App Router, Tailwind CSS (statischer Export)
Website:   Astro 7 (website/), reines HTML, gleiche Hosting-Site wie das ERP
Backend:   FastAPI (Python 3.12), SQLAlchemy 2.1, Pydantic v2, Alembic
DB:        PostgreSQL (Cloud SQL), universeller 9-stelliger Nummernkreis
Auth:      Firebase Authentication (Magic Link · Google SSO · Passkeys/WebAuthn)
Dateien:   Cloud Storage, je Umgebung ein Bucket (inexxio-dev-files · inexxio-prod-files,
           privat, FILES_BUCKET vom Deploy); ohne Bucket in der DB. Eine Stelle:
           services/attachments, ausgeliefert über einen unerratbaren Token
Karten:    Google Places (Adress-Suche in jedem Adressfeld); Schlüssel je Umgebung aus dem
           Secret Manager (GOOGLE_MAPS_API_KEY), nicht aus der Datenbank
Infra:     Google Cloud Run (europe-west6) + Firebase Hosting; Cloud Scheduler ruft alle
           5 Minuten den Takt (POST /api/v1/internal/tick, Google-Token, infra/README.md)
Zahlung:   Stripe – eigene Bezahlkarte im ERP (Payment Element + Webhook). OPTIONAL:
           ohne Schlüssel gibt es den Dienst nicht (docs/stripe-setup.md)
E-Mail:    Gmail API – je eigener Gesellschaft ein Postfach, Abgleich + Versand.
           OPTIONAL: ohne OAuth-Client wird eine Mail nur erfasst (docs/gmail-setup.md)
KI:        Claude API (Anthropic SDK) – EINE Tür services/ai.py: Lesen (Haiku 5.5),
           Verfassen, Gespräch, Folgen (Sonnet 5.5, mit Werkzeugen), «Auf einen Blick» (Haiku 5.5), Deckel
           10 CHF je Tag, jeder Aufruf im Log (Kosten, Dauer); im Gespräch Websuche und Lesen
           von Seiten (Werkzeuge des Anbieters, je Suche 1 Rappen unter dem Deckel). Abschreiben: Gemini über
           Vertex AI; Bedeutungs-Zahlen: Vertex AI + pgvector. OPTIONAL: ohne ANTHROPIC_API_KEY
           bleibt das Gespräch Text; ohne Vertex fehlen Abschreiben und Suche nach Bedeutung
           («Der Assistent» unten)
Scanner:   OpenCV.js (Paket @techstark/opencv-js, als /vendor/opencv-<Version>.js
           ausgeliefert, geladen erst beim Scannen)
```

**Geplant, aber NICHT verdrahtet** (keine Zeile Code): Typesense (Suche) ·
Carrier-Anbindung (Versand). Was davon einmal gebaut und
wieder entfernt wurde, steht in `docs/attic.md`.

## Monorepo-Struktur
```
inexxio/
├── CLAUDE.md · PROCESS_CORE.md · SYSTEM_LOGIC.md · README.md
├── website/          ← öffentliche Website (Astro) – WEBSITE_PLAN.md, START.md
├── frontend/         ← Next.js: /erp (ERP), /konto, /login, /abmelden, /agb – frontend/CLAUDE.md
├── backend/          ← FastAPI – backend/CLAUDE.md
│   └── app/{core,domain,models,schemas,routers,services}/, alembic/, scripts/, tests/
├── firebase.json     ← Hosting, Rewrites, Security-Header, Weiterleitungen alter Pfade
├── .github/workflows ← quality.yml (das Gate), deploy-dev.yml (develop), deploy-prod.yml (main)
├── infra/README.md   ← Infrastruktur, wie sie eingerichtet ist (Umgebungen, Kosten, Rollback)
├── scripts/          ← check-schema.sh (nach jedem Deploy) · dump-db.sh · reset-dev-db.sql ·
│                       same-code.mjs (hat sich nur Text geändert, nie Code? – Prüfung für
│                       Arbeiten an Kommentaren)
└── docs/             ← adr/ (gültige, mit Kopfstatus; historische in history/adr/) · attic.md · backlog.md (offen, auch die Befunde)
                         · design-system/ · prozessbild.md · gmail-setup.md · stripe-setup.md
                         · passkeys.md · dokumente.md · history/
```
Messwerkzeug: `backend/scripts/deadcode.py` – «was liest eigentlich niemand mehr?» für
Backend und Frontend (Erreichbarkeit + Exporte ohne Leser).

## Datenmodell (gültig)

```
Artikel        Ordner + Spezifikation + Erfassungsmaske + Erzeugungsprozess. Keine Menge.
  └─ Instanz   reine Gruppe (kind = einzeln | batch), eigene Objektnummer, KEINE Menge –
               die Menge IST die Anzahl ihrer Einzelinstanzen.
       └─ Einzelinstanz   das EINZIGE Arbeitsobjekt. Menge immer 1 (nicht gespeichert),
                          eigener Status, Nummer = <Instanznr>-<Suffix> (nicht aus
                          object_id_seq), Ort als Zeiger.
```
- **Einzelinstanz-Regel:** im Prozess wird ausschliesslich mit Einzelinstanzen gearbeitet.
  Jede Ansicht höherer Ebene (Instanz, Artikel, Bestand) ist Filterung/Summierung, nie eine
  eigene Datenquelle. Eine Einzelinstanz zieht **keine** Objektnummer – es kann für sie gar
  kein Etikett geben; gescannt wird immer die **Instanz**.
- **Auftrag** → geordnete Modul-Liste (eingefrorene Kopie des Prozesses) → Einzelinstanzen
  passieren sie. **Artikel und Auftrag entstehen erst mit ihrer Freigabe** (ein `POST`,
  Anlegen = Freigeben); bis dahin lebt der Entwurf im Browser, ohne Zeile und ohne Nummer.
  Ein Artikel wird danach nicht mehr geändert.
- **Das Log** (`log`, Projektakte `docs/konzept/lernende-firma.md` §1): **eine** Tabelle,
  append-only, für alles, was geschieht. **Die Datenbank schreibt es selbst**: ein Trigger
  (`domain/log.log_row`) an jeder Tabelle hält jede Änderung fest – wer (`actor_kind`
  person · ai · system · external, `actor_id` = Objektnummer), woher (`source`, `request_id`
  je Anfrage), an welchem Ding (`object_id`, `domain/log.OBJECT`), nur das Geänderte
  (`changes`); Geheimes und Binäres nie im Klartext. **Wer handelt**, setzt `core/actor.act`
  an einer Stelle (Anmeldung, `public(…)` an öffentlichen Routen, Start, Migration) – **ohne
  Handelnden scheitert jedes Schreiben**. Fachliche Ereignisse ohne Zeilen-Änderung schreibt
  `services/log.event` (z. B. `ai.call`, `mail.send_failed`, `document.read`,
  `voucher.action`). Unveränderlich per Trigger (auch `TRUNCATE`); einzige Ausnahme die
  Schwärzung `log.redact`, die sich selbst einträgt. Je abgeschlossenem Tag ein verkettetes
  Siegel (`log_seal`, `log.seal_due` beim Start und im Takt, `log.verify`).
- **Ereignisse des Prozesses** stehen im Log als `process.<art>` (`process._pass` ist die
  eine Schreibstelle, über `log.process_events`); gelesen über die Sicht `process_log`
  (`models.ProcessEvent`). Bild, Protokoll, Stückliste und Journey sind **Ableitungen aus dem
  Log**, nie aus dem heutigen Zustand.
- **Exklusivität**: ein Stück ist in genau einem Auftrag aktiv – als partieller
  Unique-Index auf der offenen Zugehörigkeit (`order_units`).
- **Dokument** (`docs/dokumente.md`): Datei + Art + Name + Referenz(en), eigene
  Objektnummer. Neun Regeln; die wichtigsten: dieselbe Datei ist dasselbe Dokument, vorher gibt
  es nichts (Entwurf im Browser, «Freigeben» legt an), es erscheint genau dort, wohin seine
  Referenz zeigt, ein **Pflichtfeld** (`domain/documents.FIELDS`) ist änderbar, nie leer,
  gelöscht wird nur, was nirgends hängt; die Angaben (`facts`) sind ein JSON-Objekt bis 64 KB
  (`domain/documents.clean_facts`). Zustand abgeleitet: Freigegeben · Unterschrift
  angefragt · Abgelehnt · Gelöscht.
- **Status** (`domain/statuses.py`, `CATALOG`): ein Eintrag trägt Beschriftung, Ampelton,
  Achsen, Bestand ↔ Historie (`stock`) und Endgültigkeit (`terminal`); ein Stück-Status ohne
  `stock` lässt die App nicht starten. Das Frontend **bekommt** den Katalog generiert
  (`scripts/dump_statuses.py` → `frontend/src/lib/status-catalog.ts`). Stücke: Freigegeben ·
  Im Prozess · Gesperrt · Verbaut · Verkauft · Verschrottet. **Verschrottet ist endgültig**,
  durchgesetzt in `_pass` **und** per DB-Trigger `trg_instance_units_terminal` – ohne
  Umgehung. **`Verkauft`** schreibt das Ziel des Auftrags: was einer anderen Partei gehört,
  wird dort «Verkauft» statt «Freigegeben» – Historie wie Verbaut (kein Bestand, kein FIFO, kein
  Verbrauch), aber ein **regulärer Start** (Service beim Kunden, Retoure).
- **Auftragsstatus** (Im Prozess · Abgeschlossen · Abgebrochen) ist abgeleitet (`_derive`),
  nie gesetzt. **Abgeschlossen** = den definierten Weg zu Ende gegangen (auch über einen
  Ausgang). Es gibt **keine Abbruch-Funktion**: der Abbruch ist eine Abweichung mit gekappter
  Rückführung.
- **Die Wiederholung** (PROCESS_CORE §6.6, Projektakte `docs/konzept/wiederkehr.md`,
  `domain/loop.py` · `services/loop.py` · `components/erp/loop-card.tsx`): eingeschaltet nur im
  Entwurf eines regulären Auftrags (Takt, Ab, Bis, je Lager-Zeile «gleiche Einzelinstanzen» oder
  «FIFO»), eingefroren als Ereignis `loop.set`. **Jeder Auftrag hat höchstens einen Nachfolger**,
  eine 1:1-Kopie über `orders.create_order` (`loop.next`, eindeutiger Index); der Takt legt ihn am
  Termin an. Fehlt etwas, **wartet** er (keine Periode geht verloren); ist ein Stück verschrottet,
  «geht nicht mehr» – beides in «zu tun». Beendet wird am neuesten Auftrag (`loop.ended`). Die
  Zahlung geht jedes Mal Offerte → Zusage → Rechnung; mit Zusage des Vorgängers und allen Preisen
  vorgegeben macht das System Anfrage und Zusage still (`loop.agreed`). Zustand abgeleitet:
  läuft · wartet · geht nicht mehr · beendet · abgeschlossen · weiter im Nachfolger.
- **Abweichungen sind ganz gewöhnliche Aufträge** (PROCESS_CORE §12): wer Stücke greift, die
  nicht regulär starten (`statuses.REGULAR_STARTS`: `Freigegeben`, `Verkauft`), ist
  automatisch eine dokumentierte Abweichung (entzogen, gesperrt, verbaut). Ob ein Stück zurückkehrt, ist eine Eigenschaft der **Verbindung**
  (`order_units.return_to_order_id`). Solange eine Rückführung aussteht, ist das Modul
  gesperrt (durchgesetzt in `process.confirm_step`). **Das Greifen IST das Aufheben**
  (Gesperrt, Verbaut, Verkauft) – kein «entsperren»-Endpunkt.
- **Ort** = Zeiger am Stück (`instance_units.place_object_id` ↔ `place_unit_id`, höchstens
  eines): Halter ist eine Instanz, ein Benutzer oder ein Unternehmen, beim Verbauen das
  Träger-Stück. Ändert nie Status oder Zugehörigkeit; keine Zyklen; **jedes Stück behält
  seinen Ort, ausser es ist verschrottet** (auch Gesperrt und Verkauft). Wird ein verbautes
  Stück gegriffen (Ausbau), bekommt es den Ort seines Trägers (`places.take_out`). Eine
  Schreibstelle: `services/places.py`.
- **Eigentum ist eine Ableitung, keine Spalte** (`voucher.sold_units`): das jüngste nicht
  stornierte Zahlungsmodul, das ein Stück passiert hat, sagt «geht an die Partei» oder «geht
  an uns» (ohne Zahlungsmodul: uns). Gelesen wird es nur am Ziel (`process._finish`): an die
  Partei → **Verkauft**, sonst **Freigegeben**. Ein Storno wirkt damit von selbst; zurück in
  den Bestand kommt Verkauftes nur über eine Retoure «an uns».
- **Artikel-Lebenszyklus**: keine Versionierung – Änderung = neuer Artikel, der den alten
  **ersetzt** (`replaces_object_id` bei der Anlage → `replaced_by_id`). «Inaktiv» ist eine
  **Projektion** von `replaced_by_id`, kein Schalter. Nur ein freigegebener Artikel erzeugt
  Neues (`articles.may_create`); «ab Lager» bleibt erlaubt.
- **Person, Firma, Adressbuch, Nachricht** – siehe «CRM».

## Die Module (heute fünf)

Was ein Modultyp ist, steht in `backend/app/domain/modules.py` (`MODULES`); was er im
Editor mitbringt, in `frontend/src/lib/modules.ts`. Ausgeführt wird jedes Modul über
**einen** Endpunkt (`…/steps/{id}/confirm`, `process.confirm_step`). Rahmenregeln, die jedes
Modul erbt: **`Module.terminal` = Ausgang** (Editor bietet dahinter nichts an, Freigabe
weist ab, das Bild endet dort); **`Module.passes_itself` = lässt von selbst durch** (kein
«Bestätigen» von Hand, der Satz dazu; der Kern fragt die Eigenschaft, nie den Beleg – heute nur
die Zahlung); Kettenregel `domain/chain.py`; Farbe/Symbol reisen mit dem
Schritt (`ModuleFacts`), Unbekanntes sieht unbekannt aus; ein abgeschlossenes Modul zeigt
sein Protokoll (`services/record.py`, eine Ableitung für alle); ein Modul zeigt seine Sache
in jedem Zustand, nur die Aktionen hängen daran, ob es dran ist. **Jedes Modul beschreibt seine
Einstellungen** neben `clean_config` als JSON-Schema mit Beispielen (`Module.config_schema`,
Erfassungstypen `CaptureType.FIELDS`, `sampling.SCHEMA`); daraus beschreibt sich `ModuleInput`
(`module_type` als `enum`, je Typ `x-config-by-module-type`; Herkunft einer Zeile und Takt/Wahl der Wiederholung ebenfalls als `enum`) und damit jede Route, die Schritte
nimmt – die KI liest es über `handlung`. Wächter `test_module_config_schema`: was `clean_config`
liest, ist beschrieben, und umgekehrt.

- **Datenerfassung** (PROCESS_CORE §4.4/§4.5/§9.0–§9.5, `capture-work.tsx`): **Ein Vorgang
  ist EINE Instanz** – Charge = 1 Scan, Einzelserialisierung = n Scans. Ohne Verifikation
  400; die Tastatur ist die Alternative im Scan-Dialog und wird als `verification='manual'`
  geloggt. **Der Scan gilt der Instanz, die Erfassung der Einzelinstanz** (Nutzlast Nummer →
  Punkt → Wert, Deckung in beide Richtungen). **«Nicht bestanden» rückt nicht vor** und legt
  nichts an; der Halt ist eine **Auskunft** (`held_units`), keine Sperre – das System bietet
  einen gewöhnlichen Auftrag mit vorgewählten Stücken an. **Die Stichprobe ist EINE Zahl**
  (Anteil an der Gesamtmenge, `domain/sampling.py`), gezogen einmal je Modul mit
  Erfassungspunkten beim Erreichen, zufällig, eingefroren als `sample`-Ereignis. **Bestätigt
  wird nur, was gezogen ist** (`process._drawn_only`); der ungeprüfte Rest läuft erst, wenn die
  Stichprobe durch und bestanden ist (`process.carry_on`). Erfassungspunkte: Text · Ja/Nein · Bild (nur
  Kamera, genau eine Aufnahme je Stück) · Signatur · Soll-Ist (mit Einheit) – je Typ eine
  Datei in `domain/capture_types/`.
- **Aussondern** (§9.4): Verschrotten (`Verschrottet`, endgültig) ↔ Sperren (`Gesperrt`)
  ist ein **Parameter** (`config.mode`), der Zustand wird abgeleitet (`exit_status_for`).
  Ein **Ausgang**. Der **Grund ist Pflicht beim Modellieren** (`config.reason`), zur Laufzeit
  ist der Scan die Bestätigung.
- **Verbrauch** (§9.6): Komponenten **treten am Modul ein** (`process._enter_at_step`); die
  Stückliste (`config.lines`) gilt **je Produkt-Stück** und wird beim Erreichen gerechnet.
  Welche Komponente in welches Produkt ging, steht im Log (`payload.into`); die Stückliste
  eines Stücks ist eine Ableitung (`services/genealogy`). **Nichtverfügbarkeit ist kein
  Zustand** (`StepNeed`: gebraucht · verfügbar · davon am Ort); das Material muss dort
  liegen, wo das Produkt liegt (`material_place`, «am Ort» heisst in der Halter-Kette).
  **Aus welchen Kisten genommen wird, sagt der Server** (`StepNeed.plan`: älteste zuerst, am
  Ort, wenn verlangt; dazu `missing` · `misplaced`) – die Oberfläche rechnet nicht nach.
  `Verbaut` ist nicht terminal (Demontage = Greifen). Kein Ausgang.
- **Bewegen** (§9.8): setzt den Ort, ändert keinen Status. Das **Ziel ist optional**:
  definiert → der Scan verifiziert, offen → der Scan wählt. **Ware zuerst, Ziel zuletzt**
  (der Ziel-Scan ist die Quittung der Ablage). Eine Spedition ist ein Einkauf, also ein
  Zahlungs-Modul daneben – Bewegen weiss nichts davon.
- **Zahlung** (§9.15, Schlüssel `beleg`, `domain/voucher.py` · `services/voucher*.py` (Kern →
  Kopf → Geld → Handlungen → Ansicht, `backend/CLAUDE.md`) · `services/voucher_docs.py` ·
  `beleg-work.tsx`): Geld mit einer zweiten Partei, **Einnahme ↔
  Ausgabe** als Einstellung (`Direction`). Stufen `offer → agreed → billed` (+ `cancelled`);
  **Erledigt ist abgeleitet** (Saldo 0, bei Export mit Ausfuhrnachweis). **Jedes Verb steht an
  EINER Stelle** (`VERBS`), **`can` ist Auskunft UND Tor**, die Leiste der Karte ist
  `situation` (nie leer ausser Erledigt/Storniert – Wächter «keine Sackgasse»). **Die Stücke
  passieren das Modul von selbst** – mit der Zusage, bei Vorauszahlung mit dem Geld
  (`process.carry_on` – die eine Stelle, die auch die Stichprobe fragt). **Preise** gibt das Modul
  bei einer Einnahme je Artikel vor, wenn gewünscht (`Beleg.PRICES`, netto, Hauswährung; am
  Beleg fest, `voucher_head.preset_prices`; den Steuersatz entscheidet die Anschrift).
  **Eigentum** «geht an die Partei · geht an uns» ist eine
  **Pflichtwahl ohne Vorbelegung** (`ownership_problem`: ohne Wahl kein Anbieten, keine
  Zusage), eingefroren mit der Zusage; am Ziel macht sie aus dem Stück Verkauft oder
  Freigegeben. **Der Beleg IST die Rechnung – eine je Modul**; ein
  **Wort für den Storno** («Stornieren»), nach der Rechnung entsteht die Gutschrift über die
  ganze Rechnung von selbst; «Rechnung zurücknehmen» gibt es nicht. Passen die Stücke nicht
  mehr (`units_problem`), bleibt nur «Stornieren». Geld-Zeilen: Zahlung · Ausbuchung (mit
  Grund) · Trinkgeld, «falsch erfasst?» bucht eine Zeile gegen, **eine Referenz gehört zu
  genau einer Zahlung** (Unique-Index). Gültigkeit der Offerte in Tagen, **angenommen wird nur
  die aktuelle Fassung** (`offered_hash`). **Die Anschrift entscheidet** Steuersatz (Ware:
  Lieferadresse, Dienstleistung: Sitz; Ausland fest Export bzw. Reverse Charge), Fremdwährung,
  Zoll und den Ort der Lieferbedingung; die eigene Gesellschaft ist nie Gegenpartei.
  Lieferantenrechnung mit Nummer, Datum, MWST-Nr. und dem **Dokument** (Feld
  `voucher.original`, die Werte liest die KI vor); Abweichung → «So annehmen» mit
  Grund. **Ausfuhrnachweis** = Nummer der Veranlagungsverfügung + ihr Dokument (Feld
  `voucher.export`) – beide über `components/erp/document-field.tsx`. Teilbetrag je Position. Mahnung 3 Stufen à 10 Tage, von Hand. **Jedes Papier**
  (Offerte, AB, Rechnung, Quittung, Stornierung, Gutschrift, Mahnung) entsteht aus **einer
  A4-Vorlage** (`services/a4.py`), nennt je Position die **Seriennummer** (Instanznummer,
  `voucher.serials_of`), ist ein **Dokument** (Feld `voucher.doc`, nie löschbar; Art, Nummer,
  Stufe in seinen Angaben, je Partei ein gewöhnlicher Link `document_links`; ausgestellt ist es mit dem ersten Link, «Senden» teilt nur – keine Mahnstufe, keine Partei), trägt die
  AGB der stellenden Gesellschaft auf eigenen A4-Seiten. **Vorschau → Freigeben**: was ein Papier
  hinausgibt (`voucher.PAPER_VERBS`), zeigt die Karte vorher (`voucher_docs.preview`,
  zurückgerollter Lauf); **AB und Quittung stehen an** (`voucher.papers_due`, «zu tun») und
  gehen immer mit «Prüfen und freigeben» durch einen Menschen (Verb `release`), nie von selbst. Es geht
  mit Link `/dokument?t=…` per Mail hinaus – **dieselbe Seite wie jedes Dokument**; ist es ein
  Papier eines Belegs, handelt die Partei dort mit denselben Verben. **Unsere Rechnung trägt den Tag, an dem sie gestellt wird** (eine Lieferantenrechnung das
  Datum auf ihrem Papier). Steuer je Position (MWSTG Art. 26), gerundet je Satz auf der Summe; **eine Währung
  je Vorgang**. Drei Wege zum Geld: bar · Überweisung (Swiss QR-Rechnung) · Karte (Stripe,
  gebucht nur vom Webhook; zurück auf die Karte nur, was geschuldet ist).
- **Zahlungen-Liste** (`services/payment_list.py`, `GET /erp/payments`): eine Ableitung an
  jeder Person (Abschnitt) und an jeder eigenen Gesellschaft (Reiter); Überfälliges zählt in
  «zu tun».

Entfernt (nur noch Vermerk): Ausliefern · Beschaffen · Verkauf · «Zahlung (alt)» – siehe
`docs/attic.md`.

## CRM

- **Die Rolle ist der Zugang**: `admin` · `employee` · `user` (`policy.ROLES`). Ins ERP darf
  genau `policy.STAFF_ROLES` (admin, employee), im Frontend **nur** über `isStaff()` · `isAdmin()`
  (`lib/record-status.ts`). **Wer was darf, steht in `domain/policy.RULES`** (Wächter
  `test_policy`: kein Rollenvergleich daneben). **Kundendaten ändert jedes Personal**, Rollen und
  Mitarbeitende nur der Admin (`person.edit` · `person.staff`; die Oberfläche fragt `may_edit`). **Lieferant ↔ Kunde ist eine Eigenschaft des Vorgangs**, nicht
  der Person. **Admin wird nur `initial_admin_email`** (beim Login), nie «wer zuerst
  kommt». Personen werden nicht deaktiviert; Personal kann eine Person anlegen
  (`POST /erp/records`, das Anmeldekonto entsteht bei der ersten Anmeldung).
- **Der Zugang einer Person** (Karte «Zugang» am Personendatensatz, `components/erp/person-access`
  – dasselbe Bauteil wie «Sicherheit» im Konto; `routers/access.py`): ihre Passkeys (entfernen) und
  ihre Verbindungen mit Claude (trennen), sichtbar und änderbar nur für sie selbst und den Admin
  (`policy` «person.access», `may_access`). Einen Passkey einrichten kann nur die Person auf ihrem
  Gerät (Konto).
- **Es bestellt immer eine Person**; die Firma ist höchstens Rechnungsempfänger «z. H.».
  **Eine fremde Firma ist ihre Identität** – Name, Rechtsform, UID (`sites.EXTERNAL_FIELDS`).
  Eigene Gesellschaften (`is_own`, nur Admin) tragen Anschrift, Bank, Währung, Gebiete und
  stellen Belege; genau eine ist **Betreiber** der Website (`sites.find_operator`). Die
  Firma einer Person ist eine **Zuordnung** (`user_profiles.company_object_id`).
- **Jeder darf eine Firma anlegen – der Schlüssel entscheidet**: `uid_key` (UID ohne
  Satzzeichen, Prüfziffer eCH-0097 selbst geprüft) bzw. `name_key` (Name + Rechtsform),
  beide eindeutig in der DB; `sites.resolve` erkennt oder legt an. Eine Dublette ist
  unmöglich, nicht verboten. Kunden sehen keine fremden Firmen.
- **Adressbuch** (`services/address_book.py`): die Anschriften gehören der Person, in zwei
  Konten (`private` · `business`, Letzteres nur mit Firma), dieselbe Maske in Konto und ERP;
  je Konto genau ein Standard je Art. Der Beleg wählt daraus (Verb `address`) und friert ein.
- **Kommunikation** (`domain/communication.py`, `services/communication.py`,
  `components/erp/communication.tsx`): **Alles ist eine Nachricht** (E-Mail, Anruf, intern,
  Notiz, Erinnerung) – ohne Objektnummer, ohne Status, ohne Typfeld. **Jede Nachricht hat einen
  Betreff, und das Anliegen IST der Betreff** (ohne «Re:» usw.; als Spalte `messages.topic` mit
  Index `(topic, at)`, gesetzt nur vom Modell mit dem Betreff, `Message._topic`). **Offen** = an
  uns, Zeitpunkt erreicht, keine spätere Nachricht von uns mit demselben Betreff; **überfällig
  nach 2 h** – «beantwortet» ist EINE Abfrage (`communication._ANSWERED`), die je Kandidatin nur
  ihr Anliegen liest; eine Antwort zählt erst, wenn sie draussen ist (nicht wartend, nicht
  aufgegeben – `mail.gave_up`). **Die Richtung ist eine Tatsache der Nachricht**
  (`messages.inbound`, gesetzt, wenn sie entsteht) – nicht die Rolle des Absenders: schreibt ein
  Mitarbeiter von seiner privaten Adresse an das Postfach, kam die Mail von aussen. Intern heisst
  intern (nur Mitarbeitende); was von aussen kam, bekommt die Antwort nach aussen. Die Beteiligten sind **Datensätze** (`message_parties.object_id`):
  An/Cc/Bcc immer Personen, **«Betrifft» jeder Datensatz**. Verlauf einer Firma = der ihrer
  Personen. Feed-Zeichen am Symbol (`detail-frame` → `RecordIcon`).
- **Notiz** (Kanal `note`, `domain/communication.NOTE`): Wissen an einem Datensatz, keine Bitte –
  nie offen (`asks` aus, `quiet`), nie hinaus, **nie eine Antwort** (schliesst kein Anliegen). **Eine Heimat**; gehört sie woandershin, wird
  korrigiert, nicht gelöscht (`communication.move_note`: Vermerk «ungültig – gehört zu …» am
  falschen, Inhalt mit «verschoben von …» am richtigen Datensatz; eine Oberfläche dafür gibt es
  noch nicht).
- **Der Verlauf** (`services/history.py`, `GET /erp/history/{nummer}`,
  `components/erp/history.tsx`): **ein Verlauf für jeden Datensatz** – Person, Firma, Auftrag,
  Artikel, Instanz, Dokument –, gemischt nach Zeit und **in Seiten** (30, Cursor `before` =
  Zeit · Art · Nummer; nie alles): Nachrichten (`communication.page`, Rundschreiben einmal),
  Dokumente an ihm (`access.visible`) und Änderungen aus dem Log an seiner Nummer – **je Handlung
  (`request_id`) ein Block**, technisch `feld: alt → neu`, Ereignisse mit Name und einfachen
  Angaben; übersetzt nur die Tabellennamen (`domain/log.TABLE_WORDS`). Nicht gezeigt: die
  Log-Zeilen von Nachrichten und die Nummernvergabe (`history.HIDDEN`, EINE Liste); die
  Zeiterfassung einer Person nur ihr selbst und dem Admin. An Person und Firma ist er die Liste
  der Kommunikation (mit Eingabe an der Person); andere Datensätze haben keine Eingabe.
- **Gmail-Postfach je eigener Gesellschaft** (`services/mailbox.py`, Kanal `c<Objektnummer>`,
  verbindet nur ein Admin; persönliche Postfächer gibt es nicht). Die Kontakt-E-Mail der
  Gesellschaft **ist** das Postfach (gesetzt durch Verbinden, geleert durch Trennen). Abgleich
  über **Push**: Gmail meldet jede neue Mail über Pub/Sub (`POST /api/v1/mail/push`, angemeldet
  wie der Takt), das Postfach wird sofort abgeholt (`mailbox.push`); die Anmeldung bei Gmail
  (`mailbox.watch`, 7 Tage) erneuert der Takt (`mailboxes.watch_until`; einmal
  `infra/setup-gmail-push.sh`). Der Takt holt alle 5 Minuten als Netz ab; ohne Push auch das
  offene ERP (`POST /erp/messages/sync`, 30 s je Postfach) – mit Push fragt es nur, ob etwas
  Neues da ist (`latest`). Ein unbekannter
  Absender wird Person (`people.ensure`), Massenpost nicht; eine eigene Adresse ist nie eine
  Person; eine Mail, die sich nicht verarbeiten lässt, wird übersprungen (Log). Senden: jede
  Mail genau einmal (einzeln gesperrt, sofort festgeschrieben), nur über ein verbundenes
  Postfach; **nie doppelt**: jede Mail, die hinaus soll, bekommt ihre Kennung (`Message-ID`, zufällig,
  `@mail.inexxio`) mit der Nachricht gespeichert (`Message._message_id`), vor jedem Senden fragt Gmail
  danach, und der Abgleich holt eine eigene Kennung nie herein; nach drei Abweisungen durch Gmail ist
  sie **nicht gesendet** (`communication._FAILED`, an der Mail mit «Neu senden»,
  `POST /erp/messages/{id}/resend`; die Versuche zählen danach von vorn) und der Grund steht als
  interne Nachricht im Verlauf. **Was die Gesellschaft schreibt, schreibt die
  Gesellschaft**: automatische Mails (Bestätigung, Newsletter-Bitte, Beleg ohne Mensch) und was direkt
  in Gmail hinausging, haben die Gesellschaft als Absenderin, nicht den Admin des Postfachs. Ist
  das Postfach einer Mail getrennt, wählt die Antwort ihres von Hand – nie still ein anderes.
  **Nie verloren**: dasselbe Postfach neu verbunden macht weiter, wo es aufhörte; ist Gmails Stand zu
  alt, kommen alle Mails seit dem letzten Abgleich (seitenweise). Erledigt im ERP =
  gelesen in Gmail. **Ein Anhang** bleibt in Gmail, bis ihn jemand öffnet – dann geht er in den
  Entwurf eines Dokuments (`mailbox.attachment`); ebenso die Fotos des Kontaktformulars.
- **Eine Stelle für jede Mail des Hauses** (`services/outbox.py`): `deliver` (anlegen, bauen, zum
  Versand geben – Beleg, Dokument, Eingangsbestätigung, Newsletter-Bitte), `build` (auch die
  Antwort aus dem Verlauf), `firm`, `signer`. **Gebaut beim Anlegen, nie beim Versand.**
- **Eine Mail-Vorlage** (`services/mail_layout.py`, `compose`): Kopf · Betreff als
  Überschrift · Inhalt · Unterschrift mit dem Menschen im Namen der Gesellschaft · Fuss; was
  im Verlauf steht, ist Wort für Wort, was hinausging (`messages.html`). Antworten nennen den
  ganzen Faden (`References`); Zitate fallen beim Abholen weg – **wo das Mailprogramm sie
  markiert** (HTML-Teil: Gmail `gmail_quote`, Outlook `divRplyFwdMsg`, Apple `blockquote
  type=cite` …, `mail_parse.QUOTE_CLASSES` · `QUOTE_STOPS`), sonst an ihren Mustern im Text
  (`mail_parse._QUOTE`); eine Grussformel-Erkennung (`domain/communication.is_greeting`). **Ein Unterzeichner**
  für jede Mail (`mail_layout.as_signer`: Name + Profilbild). **Das Bild der Unterschrift**
  (`services/portrait.py`): schräge Streifen, die sich einmal öffnen, links eine rote Kante –
  ein GIF (das erste Bild ist das fertige, für Outlook), durchsichtig für hell und dunkel,
  ausgeliefert über `GET /api/v1/mail/portrait/<signiert>.gif` (Foto oder Initialen),
  gerechnet beim ersten Abruf, dann vom CDN gehalten.
- **Drei Versandarten einer E-Mail** (`domain/communication.DELIVERIES`): **Mail** (An/Cc
  sehen einander, Bcc bleibt Bcc) · **Rundschreiben** (Information an mehrere: je Person
  eine eigene Nachricht mit Anrede, im «An» nur sie) · **Newsletter** (ebenso, aber nur an
  Angemeldete, mit Abmeldelink im Fuss und `List-Unsubscribe`-Kopf). Rundschreiben und
  Newsletter sind **je Empfänger eine Nachricht** (`messages.group_id` → die erste,
  `messages.newsletter`) – im Verlauf steht, was hinausging; der Verlauf zeigt die Gruppe
  einmal («an 23»). Hinaus gehen sie über den Abgleich (`mailbox.send_due`, 20 je Lauf);
  ein Newsletter prüft die Einwilligung beim Senden noch einmal. Die Empfänger wählt heute
  der Mensch von Hand (`MessageIn.to` = Liste von Personen, kein Filter); eine Auswahl per
  KI setzt später genau dort an. **Die Leiste hat drei Arten** (Mail · Anruf · Intern); stehen
  zwei oder mehr im «An» einer neuen Mail, fragt dieselbe Eingabe in der Zeile **«Versand»**:
  «Alle sehen einander» · «Jede Person einzeln» (Rundschreiben), dazu «Als Newsletter» –
  keine eigene Maske; Anrede und Newsletter-Fuss fest sichtbar. **Nur ein Modus**: eine Mail
  geht hinaus oder wartet auf ihr Postfach («nur erfassen» gibt es nicht; ohne verbundenes
  Postfach bietet die Eingabe keine E-Mail an).
- **Newsletter «Post von INEXXIO»** (`domain/newsletter.py`, `services/newsletter.py`,
  `routers/newsletter.py`): **Einwilligung ist ein Nachweis** (`newsletter_consents`,
  append-only, Quelle + Wortlaut + Zeitpunkt); angemeldet = jüngste Zeile, **zwei
  Zustände**. Double Opt-in über eine Mail mit einem Knopf (bei einer Person in ihrem
  Verlauf; die Anmeldung von der Website legt **keine** Person an – die Adresse steht im
  Link, die Person entsteht mit dem Klick); nur das Konto meldet direkt an (Adresse
  bestätigt). **Das ERP meldet niemanden an** – es schickt die Bitte, oder es meldet ab.
  Links signiert an einer Stelle (`core/signed`, Schlüssel `LINK_SECRET`, der frühere aus
  `database_url` prüft mit); Bestätigungs- und Abmeldeseite mit Knopf (gegen Link-Scanner),
  One-Click nach RFC 8058. Anmeldestellen:
  Häkchen im Anfrage-Formular (nie vorausgewählt), Einladung in der Eingangsbestätigung,
  Seite `/newsletter` (Link im Fuss), Konto. Wörter: `website/src/config/newsletter.mjs`.
- **Kontaktformular der Website** → offene Nachricht im ERP (`services/inquiry`), siehe
  «Website».

## Der Takt

Cloud Scheduler ruft alle 5 Minuten, Tag und Nacht, `POST /api/v1/internal/tick` – was nicht
von einem offenen Browser abhängen darf. **Die Aufgaben stehen an einer Stelle**
(`services/tick.TASKS`): Siegel des Logs · Wiederholungen anlegen (`loop`) · Mails holen und senden · Aufnahmen
(`voice`) · die KI (Gespräche nachholen, auf die sie nicht antwortete, Vorschläge aus Mails,
«Auf einen Blick» vorbereiten, Bedeutungs-Zahlen für «im Wissen suchen»; alles unter 50 s, `ai.until`). Je Aufgabe eigene Sitzung
(das System, `job`), Advisory-Lock (läuft sie anderswo: übersprungen), Zeitgrenze, ein
Fehlschlag hält die übrigen nicht auf (Antwort 500 → Alarm). Getanes steht im Log
(`tick.<name>`), Leerlauf nicht. Anmeldung: Google-Token (OIDC) des Dienstkontos `inexxio-tick@`, geprüft
in `core/oidc` (`TICK_AUDIENCE`, `TICK_SERVICE_ACCOUNT`; ohne sie 503). Eingerichtet im Deploy
(Job «Takt»), einmal je Projekt `infra/setup-takt.sh` (Dienstkonto, Rechte, Alarm per Mail).

## Der Assistent (Phase 5, Projektakte `docs/konzept/lernende-firma.md`, Bauplan `docs/konzept/phase5-bauplan.md`)

- **Zwei Dinge: Gespräch und Vorschlag.** Im «+» sagt die Person, was ist (Text, Sprache, Foto,
  Datei, Stecknadel); die KI redet mit und bereitet **Vorschläge** vor (im Code: Handgriff) – alles,
  was das ERP kann. **Die KI führt nie aus.** Im Gespräch hat ein Vorschlag nur **Öffnen** (zum
  Entwurf, überall, wo es «Neu anlegen» gibt, sonst zum Datensatz) und **✕**; der Entwurf bekommt
  den **ganzen** Wertesatz (Auftrag: alle Zeilen, Schritte mit Einstellungen, Wiederholung; Artikel:
  Felder, Schritte, Vorgänger – `lib/proposal-draft`), was er nicht darstellen kann, nennt er oben; entschieden wird
  **am Datensatz** in «Auf einen Blick»: was sich ändert (`feld: alt → neu`, wie es jetzt ist,
  `handgriff.changes_of`) und **Übernehmen** – je Vorschlag einzeln, kein «Alles übernehmen».
  **Wissen** ist das Ergebnis: Notizen und Dokumente am richtigen Datensatz.
- **Ein Vorschlag ist die echte Route** (`services/handgriff.py`): Methode, Pfad, Werte; übernommen
  im selben Prozess über ASGI, **mit den Rechten der Person** (`core/auth.ACTING`) und denselben
  Prüfungen – kein zweiter Weg. Welche Handlungen es gibt, **folgt aus den Routen**
  (`handgriff.operations`: schreibt, verlangt Personal, nimmt JSON; mit Datei → nur von Hand; nichts
  aus `routers/assistant`) – **keine Liste, keine Regel, nur Rechte**. Die KI bekommt sie als
  **Katalog** (`ai_tools.catalog`, aus den Routen erzeugt, nie gepflegt) im zwischengespeicherten
  Auftrag, die Felder einer Handlung schlägt sie nach (`handlung`) – **jedes Feld sagt dort selbst,
  was es braucht** (siehe Leitbild «Das Feld erklärt sich»), keine Regel nur für die KI. **Lesen** ebenso: `abrufen` ruft
  jede lesende Route des Personals (`handgriff.reads` · `look`), als `ai_tools.reader`, in eigener
  Sitzung, verworfen; den offenen Datensatz bekommt sie gleich mit der Nachricht.
- **Vorbereiten = Probelauf** in eigener Sitzung, dann verworfen (Regel 1: nach aussen erst nach
  dem Speichern, `core/outside`); was nicht geht, wird keine Karte, die KI erfährt den Satz der
  Route. **Fehlen nur Werte** (400/422, `handgriff.incomplete`), wird es trotzdem ein Vorschlag –
  ergänzt wird im Entwurf; «Übernehmen» sagt sonst den Satz der Route. Was die Person nicht darf,
  wird nie eine Karte. **Übernehmen genau einmal** (`handgriff.done`, eindeutiger Index
  `ix_log_handgriff_done`), ganz oder gar nicht. **Aufeinander aufbauen:** `{"$handgriff": n}` in
  den Werten, der Vorschlag wartet, das ERP setzt die Nummer ein.
- **Alles sind Ereignisse im Log**, keine Tabelle: `talk` (eine Nachricht, `by` person · ai; die
  erste IST das Gespräch), `handgriff`, `handgriff.done`, `handgriff.dropped`, `talk.failed`,
  `talk.stop`, `pin`. **Offen ist abgeleitet.** Ein Gespräch ist **privat** (wer es führt, und der Admin), offen,
  solange ein Handgriff offen ist oder die KI nicht geantwortet hat; abgeschlossen wird es nicht
  mehr gezeigt. Was die KI selbst weglegt (einen Handgriff ersetzt), steht nicht im Gespräch –
  die Person sieht nur das Ergebnis. Diese Ereignisse stehen nicht im Verlauf (`history.HIDDEN_EVENTS`).
- **Das «+»** (`components/erp/capture/capture-sheet.tsx`): Eingabe wie bei Claude – **das Feld
  bleibt immer stehen** (Stecknadel und Anhänge als Chips darin; Dateien auch mit Ctrl+V oder
  hineinziehen); **vor dem Senden gibt es nichts am Server**, was im Feld steht, ist der Entwurf
  (`lib/draft`, nur im Browser, bleibt beim Schliessen). Darüber das Gespräch (Blasen, die Antwort
  der KI als Markdown – sie formatiert, wie sie will; Vorschlag-Karten `handgriff-card.tsx`), «←»
  zurück zur Übersicht: «Offene Gespräche» und «Neu anlegen». **Die Antwort kommt live**
  (`talk.stream`, NDJSON): die Nachricht steht sofort, darunter jeder Schritt der KI («liest …»,
  «bereitet vor: …»), dann ihr Text Wort für Wort (`{text}`); solange ist ➤ der Stopp (`talk.stop`). Das Gespräch läuft
  **direkt am Dienst** (`BACKEND_URL`, `GET …/assistant/door`) – nicht durch das Hosting mit seinen
  60 s; begrenzt durch Schritte, Deckel und «Stopp», die Uhr (240 s, Cloud Run 300 s) ist nur das
  Netz. Die KI arbeitet in eigenem Faden und eigener Sitzung; reisst die Leitung, arbeitet sie zu
  Ende. Eine Sperre je Gespräch: Stream und Takt antworten nie beide. 📷/📄 legen die Datei in den Korb und hängen sie an die Nachricht – die KI liest sie
  und bereitet das Dokument vor («Öffnen» öffnet den Dokument-Entwurf mit der Datei; mit
  der Freigabe ist der Vorschlag erledigt, `…/done`). Die Zahl am «+» = meine offenen Gespräche und
  Aufnahmen, die nicht abgeschrieben werden konnten (`lib/assistant.useUnfinished`).
- **Die Stecknadel = Rückmeldung zur Software** (`lib/pin-point.ts`): auf eine Stelle zeigen →
  «Stelle: Seite · Datensatz · Herkunft (`data-where-*`) · Element» vor dem Text; der Hinweis ist
  der Artikel **«ERP»** (auf `/erp`) bzw. **«Website»**.
- **Das «+» auf der Website** (`website/src/scripts/capture.ts`): nur für angemeldetes Personal;
  öffnet `/erp/erfassen` (dasselbe «+») in einem Rahmen – das Gespräch läuft dort, die Stecknadel
  zeigt auf die Website, «Neu anlegen» und «Öffnen» springen ins ERP (`?neu=…&handgriff=…`, `?open=…`).
- **Claude über MCP** (`services/mcp.py`, `routers/mcp.py`, Projektakte `docs/konzept/mcp.md`):
  der eigene Claude der Person (Claude.ai, Desktop, Code) verbindet sich mit `/api/v1/mcp` und
  arbeitet **als die Person** – mit denselben Werkzeugen wie das «+» (`ai_tools.tools_for` ·
  `erp_tools`), aber mit ihren Rechten. Er liest und bereitet vor; ein Vorschlag aus Claude ist
  privat (`payload.mcp`) und wird in «Auf einen Blick» am Datensatz übernommen – nie über MCP. Anmelden ist OAuth 2.1 über die bestehende Anmeldung, **ohne Tabelle**:
  Client-Kennung, Code und Zugang sind signiert (`core/signed`), der Code (PKCE S256) gilt genau
  einmal (`mcp.grant`, eindeutiger Index), getrennt ist getrennt (`mcp.revoked`); nur Personal.
  **Offen** ist eine Verbindung, solange sie nicht getrennt und zuletzt (Erlauben oder jüngste
  Erneuerung) vor höchstens 30 Tagen benutzt ist (`mcp._OPEN`, dieselbe Abfrage für Liste und jede
  Anfrage) – trennt jemand in Claude selbst, fällt sie so von selbst weg. Gesehen und getrennt im
  Konto (Sicherheit) und am ERP-Datensatz (Karte «Zugang», selbst · Admin). Erlauben auf `/erp/verbinden`; das Hosting leitet
  `/.well-known/oauth-*` an den Dienst. Protokoll: JSON-RPC über einen `POST`, ohne SDK.
- **Vorschläge aus Mails** (`services/follow.py`): eine neue Mail einer bekannten Person liest die
  KI im Takt und bereitet Vorschläge am Datensatz vor (Probelauf mit den Rechten der Person, die
  das Postfach verbunden hat); sie stehen in «Auf einen Blick» und zählen dort in «zu tun» – wer ihn
  öffnet, entscheidet. Ein Fehlschlag zählt (`mail.follow_failed`), nach dem dritten gilt die Mail
  als geprüft.
- **Auf einen Blick** (`services/pins.py`, `components/erp/pinned.tsx`) unten im Verlauf: offene
  Vorschläge (aus Mails für jedes Personal, aus Gesprächen nur die eigenen), dann **das Wissen, das
  jetzt zählt** (höchstens drei Aussagen mit Datum und Quelle). Neu gewählt **nur, wenn sich im
  Umfeld etwas geändert hat** (`services/surroundings`: was in denselben Handlungen geschah und
  worauf die eigenen Zeilen zeigen, eine Stufe, höchstens 50; die Marke ist die jüngste Log-Id) –
  beim Öffnen kommt sofort der letzte Stand, die Oberfläche fragt je Stand des Umfelds höchstens
  einmal neu. **Vorbereitet im Takt** (`pins.ahead`, schnelles Modell): zuletzt geöffnete Datensätze
  (30 Tage, je Lauf höchstens 10), deren Umfeld sich änderte. Am Deckel bleibt der letzte Stand.
- **Im Wissen suchen** (`services/memory.py`, Migration 174): Notizen, Dokumente und entschiedene
  Handgriffe (aus Gesprächen nur ausgeführte) bekommen Bedeutungs-Zahlen (Vertex AI, `ai_memory`,
  pgvector; der Takt holt nach). Werkzeug `wissen` der KI; gefunden wird nur, was jedes Personal
  sehen darf. Ohne Vertex keine Suche nach Bedeutung, sonst nichts.
- **Die KI liest, was jedes Personal sehen darf** (`ai_tools.reader`: Rolle `employee`, ohne eigene
  Nummer) – auch wenn ein Admin spricht. **Einen Datensatz liest sie über die Route, die ihn einem
  Menschen zeigt** (`ai_tools.ROUTES` → `handgriff.look`): dieselben Felder, dieselben Rechte; ein
  Dokument dazu mit seinem gelesenen Text (nach `access`). Eine Tür: `services/ai.py` (`converse` mit Werkzeugen,
  Aufgaben `talk` · `follow` · `pin` · `read` · `compose`, je Zug ein `ai.call` mit Kosten und Dauer
  `ms`; Anleitung und Werkzeuge im Zwischenspeicher des Anbieters, `cache_control`; `ai.until` hält
  jede Anfrage über das Hosting unter 60 s). Der Auftrag steht wörtlich in `backend/app/assets/ai/auftrag.md`.
  Fällt die KI aus, bleibt das Gespräch Text; der Takt antwortet nach (`talk.catch_up`).
- **Deckel in Franken** (`AI_DAILY_CAP_CHF`, 10 je Schweizer Tag, Preise in `ai.PRICES`); ab 80 %
  ein Hinweis für den Admin (rotes Zeichen am Betreiber, `tasks._hints`).
- **Sprache** (Phase 4, `docs/konzept/phase4-bauplan.md`, `services/recordings.py`,
  `components/erp/capture/recorder.tsx`): «Aufnehmen» im «+» – dezent in der Leiste der Eingabe
  (Punkt, Zeit, Pegel von rechts nach links, ■; Bildschirm bleibt an); **30 s Stille halten von
  selbst an** (`lib/recorder.silence`). Der Browser schickt **alle 30 s ein Stück**, je **5 Minuten ein Abschnitt** (eine
  eigene Datei); ein Stück wird wiederholt, solange die Seite lebt (aufgegeben nur bei einer
  Abweisung); fällt das Mikrofon aus, endet die Aufnahme sauber. Bricht sie ab, gilt sie nach
  **30 Minuten Ruhe** als gestoppt – nichts bis dahin geht verloren. **Gemini** (Vertex AI, `ai.transcribe`, `gemini-3.5-flash`, dieselbe Tür
  und derselbe Deckel) schreibt je Abschnitt ab – Hochdeutsch in Schweizer Schreibweise, auch bei
  Mundart; der Text kommt **ans Ende des Feldes** (`recording.done.text`, die Stecknadel davor;
  währenddessen «schreibt ab …» im Feld) – die Person ergänzt und **schickt ihn selbst**; erst mit
  dem Senden gilt die Aufnahme als gesendet (`TalkIn.recordings`, im `talk`-Ereignis). Eine
  Aufnahme ist kein Gespräch: sie steht nicht unter «Offene Gespräche» und zählt nicht, ausser sie
  liess sich nicht abschreiben. Was sich nicht abschreiben lässt (kein Stück 0, über 15 MB, zweimal abgelehnt,
  sechsmal gescheitert), wird **mit Vermerk** «[Abschnitt n: …]» übersprungen. **Vom Gesprochenen
  bleibt nur der Text:** die Stücke
  (`recording_chunks`, Bytes über `attachments.put_object` in einem **eigenen Bucket ohne Soft
  Delete** `RECORDINGS_BUCKET`, sonst in der Zeile – nie im Datei-Bucket; nicht im Log) gehen nach
  der Abschrift, spätestens nach einem Tag (Takt `voice`; dazu die Regel im Bucket,
  `infra/setup-sprache.sh`) – was bis dahin abgeschrieben ist, kommt ins Gespräch. Gescheiterte
  Aufnahmen stehen sieben Tage mit Grund im «+». `recordings.advance` treibt eine Aufnahme so weit, wie
  die Zeit reicht – in der Anfrage («schreibt ab …») und im Takt. Eine Aufnahme sieht nur, wer
  aufnahm (und der Admin).

## Zeiterfassung

Verbindlich: **`docs/zeiterfassung-spezifikation.md`**. Kurz:
- **Ein Abschnitt im Personendatensatz** (zwischen Kommunikation und Stammdaten, EINE Karte,
  `components/erp/time/`), sichtbar nur im eigenen Datensatz und für den Admin
  (`timekeeping.may_see`). Der Admin kann dasselbe wie die Person, dazu Verträge und Buchungen.
- **Gespeichert wird nur Eingegebenes**: `time_contracts` (Vertrag ab Stichtag – Wochenstunden,
  Arbeitstage, Ferienwochen, Gesellschaft; 0 h = Austritt), `time_entries` (Stempel, Absenz,
  Buchung, Rücknahme – eine Änderung **ersetzt** per `replaces_id`), `holidays`,
  `company_settings.time_rules`. Verträge und Einträge sind **append-only per DB-Trigger**.
  Stundenkonto, Ferien, Hinweise und Aufgaben sind Ableitungen (`timekeeping.ledger`).
- **Eine Schreibstelle** `timekeeping.record` (Person gesperrt, `entry_problem` ↔
  `assert_entry`, ein neuer Eintrag); der Wisch `timekeeping.swipe` (Serverzeit,
  Idempotenz-Schlüssel, 60-s-Sperre); die Vorschau `timekeeping.preview` prüft mit derselben
  Regel, ohne zu schreiben. Alles in Minuten, Tage in Europe/Zurich.
- Sieben Absenzarten mit je EINER Wirkung (Erfüllt · Ferien · Entfällt), Regeln Schweiz und
  die Reglement-Sätze (ⓘ) in `domain/timekeeping`; geschickt mit der Ansicht (`vocab`).
- **7-Tage-Regel – für alles und alle** (`domain/timekeeping.closed`): kein Stempel, keine Absenz,
  keine Buchung, kein Vertrag, kein Feiertag älter als 7 Tage, auch nicht durch den Admin; ein
  Vertrag ändert sich nur durch einen neuen; die Vergangenheit korrigiert eine Buchung. Im
  Kalender **blass**. Ein Nachweis lässt sich jederzeit nachreichen. Nur online. Geprüft werden
  die Tage, die sich ändern: eine Absenz über die Grenze bekommt **«Ende ändern»** (Ersatz-Eintrag
  mit gleichem Beginn, `timekeeping.end_from`), ihr abgeschlossener Teil bleibt; ein Feiertag im
  abgeschlossenen Zeitraum wird abgewiesen, nie still übergangen.
- Was eine Person zu tun hat (Zeiterfassung, eigene Pflichtangaben), ist eine Aufgabe nur für sie
  – siehe «Aufgaben».
- **Nachweis einer Absenz** ist ein Dokument (Feld `time.proof`, «Nachreichen» öffnet den
  Entwurf); eine lose Datei im Korb nimmt `timekeeping.record` nicht an.

## Aufgaben – wer macht was (Projektakte `docs/konzept/aufgaben.md`, gebaut)

- **Eine Aufgabe ist eine Stelle im ERP, an der jemand etwas tun muss** – abgeleitet, nie
  angelegt, nie abgehakt (`services/tasks.collect`): Stücke warten an einem Schritt (nicht an der
  Zahlung, nicht bei offener Rückführung, am Verbrauch nur mit Material am Ort) · die Zahlung sagt
  «wir sind dran» (`voucher_view.situation` → `ours`: Offerte, Rechnung, Papier, Ausfuhrnachweis,
  Mahnen, Bezahlen, Erstatten) · offene Nachrichten (`communication.open_threads`) · Wiederholung ·
  Vorschläge aus Mails · eigene Zeiterfassung und Pflichtangaben (nur die Person) · Feiertage und
  Rechtstexte (Admin). Der KI-Deckel ist ein **Hinweis** (nie zugeteilt, nur der Admin sieht ihn).
  Eine Aufgabe trägt keinen Satz: Schlüssel, Ort (`object_id` + `part` = `data-todo`), Kompetenz,
  Datum.
- **Kompetenz** (`domain/competences`, acht: Kommunizieren · Verrechnen · Bewegen · Bauen ·
  Prüfen · Schweissen · Elektrik · Kranprüfung). **Sie folgt dem Ort**: am Schritt die des Schritts
  (`Module.competence`, im Editor tauschbar über `Module.clean_step` – Feld «Wer kann das?»), an
  einer fremden Person Kommunizieren, an mir nur ich, an der eigenen Gesellschaft das Recht Admin.
  Wer was kann: `user_profiles.competences`, nur am Personal, gesetzt vom Admin im Feld
  «Kompetenzen» der Stammdaten (dasselbe PATCH); **die letzte Person einer Kompetenz kann sie nicht
  verlieren** (`competences.drop_problem` ↔ `assert_drop`).
- **Zuteilung** (`tasks.dispatch`, unter `locks.TASKS`, beim Lesen und im Takt): wer da und frei
  ist – wer am längsten frei ist zuerst – bekommt die Aufgabe mit dem **frühesten Datum**, die er
  darf und kann (Arztpraxis-Modell). **Eine Person, eine Aufgabe; eine Aufgabe, eine Person**
  (`task_focus`: eine Zeile je Person, `task_key` eindeutig). **Anwesenheit in drei Sätzen**
  (`tasks.presence`, aus der Zeiterfassung): Neues nur eingestempelt (ohne Vertrag: da); was man
  hat, bleibt; ausser bei einer Absenz. **Abgeben** (`POST /erp/tasks/{key}/hand`) ohne Grund; die
  Aufgabe kommt erst nach einer anderen zurück (`handed_key`).
- **Was man sieht** (`GET /erp/tasks`, `tasks.view`): die eigene Aufgabe zuoberst im Feed (ohne
  Filter und Suche, `FeedPanel.mine`); das **rote Zeichen** am Symbol und an der Stelle (`TodoChip`,
  `TodoAt`, am Schritt `useTodoAt`) – Hover nur «Zu tun»; an meiner Aufgabe wird es «Abgeben».
  Der Admin sieht das Zeichen an jedem Datensatz mit Aufgaben; alle sehen «!», wo niemand
  Anwesendes es kann. Woran andere arbeiten, steht nirgends (nur im Log).
- **Das eine Datum am Auftrag** (`domain/order_date.py`, `orders.date_kind` · `date_on`): «bis» X
  (fertig bis, am Ende des Prozessbilds) oder «ab» X (nicht vor, am Start) – nie beide, leer = so
  schnell wie möglich. Gesetzt im Entwurf, verschoben mit `POST /erp/orders/{nr}/date` (solange im
  Prozess, nie in die Vergangenheit). **Arztpraxis-Modell**: eine Aufgabe am Auftrag (Schritt,
  Zahlung) hat als Datum X statt «seit wann»; bei «ab» gibt es sie vorher nicht
  (`tasks._dated`). Offerte und AB nennen es («Liefertermin» · «Ausführung ab»), verschoben ist
  eine gesendete Offerte überholt (`voucher.fingerprint`). Die Wiederholung gibt dem Nachfolger
  dasselbe Wort und denselben Abstand zu seinem Termin (nie vor heute, `loop._next_date`);
  «Nachschub» und «Holen lassen» am Verbrauch schlagen das Datum als «bis» vor.

## Leitbild (VERBINDLICH)

### ERP ist Master – alles andere ist Spiegelbild
Jeder Datensatz hat **genau EINEN Ort, an dem er gepflegt wird: das ERP.** Konto, Website
und alles andere sind Spiegel. Dieselbe fachliche Angabe ist **nie an zwei Stellen
editierbar**; ausserhalb des ERP schreibt nur der **Selbstbedienungs-Pfad** einer Person auf
ihre eigenen Daten, und zwar über **denselben Pfad** (`people.apply_profile_update`).
**Das ERP muss ALLES können**, was aussen geht (`ErpAdminUpdate` erbt von
`UserProfileUpdate`). **Jede Route der Selbstbedienung** (`/api/v1/auth/…`) steht in
`domain/policy.SELF_SERVICE` – mit ihrem Gegenstück am ERP-Datensatz oder als `SelfOnly` mit Grund
(Passkey einrichten, Anmelde-E-Mail wechseln); Wächter `test_erp_master`, Prüfung
`docs/history/2026-11-11-erp-master-pruefung.md`.

### Eine Sache, eine Stelle
Gleiche Bedeutung → gleicher Name, gleiche Datenform, **eine** Implementierung:
`services/address.py` (Adressen) · `services/people.py` (Personennamen, Personensuche
`people.search` hinter `GET /erp/people`) · `services/address_book.py` · `services/places.py`
(Orte, Halter) · `services/lookup.py` («welchen Datensatz meinst du», Nummer ODER Name) ·
`services/sites.py` (Gesellschaften) · `objects.obj_nr` (Objektnummer) · `objects.TYPES` (**welche Typen eine Nummer tragen** – Tabelle und Wort; Namen über die Registry, `record_labels`) · `core/clock` (**jetzt, Tag, Zeitstempel** – `utcnow` · `day` · `stamp`; Wächter `test_clock`) · `core/locks` (**jede Sperre** – Räume und Schlüssel, `xact` · `hold`; Wächter `test_locks`) · `domain/policy.py` (**wer
darf was** – eine Regeltabelle `RULES`, `may` ↔ `require`; Rollen nur dort) · `domain/errors.py`
(**jede Abweisung**: `Invalid` · `Forbidden` · `NotFound` · `Conflict` …, EINE Antwortform
`{detail, code, field?}`) · `domain/number.py` (jede Zahl aus einer Eingabe) ·
`services/documents.py` (jede Datei, `file` ist die einzige Anlage) · `services/handgriff.py` (jede
Handlung der KI – die echte Route) · `core/outside.py` (alles nach aussen) · `services/ai.py` (jeder
KI-Aufruf) · `components/erp/document-draft.tsx` (jeder Entwurf) ·
`components/form/field.tsx` + `use-field.ts` (jedes Eingabefeld, ESLint-Wächter) ·
`components/erp/address-field.tsx` · `object-select.tsx` (jedes Referenzfeld) ·
`lib/when.ts` (die einzige Datums-Ausgabe) · `lib/use-autosave.ts`. Zwei Wege für dieselbe
Sache sind ein Bug, auch wenn beide funktionieren.

### Das Feld erklärt sich – für Mensch und KI
Eine Regel steht **am Feld** (Länge, Muster, Einheit, Bereich, Beispiel, worauf eine Nummer zeigt –
`Field(description=…)`, Beschreibungen aus der Fachschicht erzeugt, wo es Listen sind) und gelangt
von dort ins JSON-Schema, das die KI über `handlung` liest; was sich nicht am Feld sagen lässt,
lehrt die Route im Probelauf mit einem Satz. **Nie still korrigieren** (zu lang wird abgewiesen,
nicht gekürzt), **jede Abweisung nennt ihr Feld** (422: `field` und `fields` = je Feld der Satz –
die Oberfläche schreibt ihn ans Feld, statt die Regel nachzubauen). Wächter
`tests/test_felder_erklaert.py`: jedes Feld einer Handlung beschrieben · kein Feld kürzt still ·
Abweisung mit Feld · Partner ist eine Person.

### Zwei Formen einer Regel – nie zwei Regeln
Braucht eine Regel eine Form, die den **Grund** nennt, und eine, die **prüft/abweist**,
stehen beide in EINEM Modul mit demselben Namensstamm (`release.pick_problem` ↔
`unpickable`, `voucher_rules.ask_problem` ↔ `assert_ask`, `articles.may_create`). So sagen
Oberfläche und Dienst garantiert dasselbe.

### Weitere Grundsätze
- **Ableitung statt Spalte** – eine gespeicherte Kopie ist die zweite Wahrheit (offen,
  fällig, Auftragsstatus, «inaktiv», Stückliste, Bild).
- **Nichtverfügbarkeit ist kein Zustand** – `StepNeed`/`DataGap` sind Zeilen; das System
  **bietet an**, der Mensch entscheidet; automatisch angelegt wird nie etwas.
- **`can` ist Auskunft UND Tor** – ein Knopf, der nie etwas tun kann, steht nicht da.
- **Kein Löschen, Gegenbuchung** – Soft-Delete, Korrekturbelege, Log append-only.
- **`busy` sperrt Handlungen, nie Geometrie** – ein Auto-Save verschiebt nichts.
- **Nichts scheitert still** – eine Betriebsmeldung geht durch EINE Stelle mit Stufe (`core/report`:
  info · warn · error; ERROR geht per Mail, `infra/setup-meldungen.sh`), ein gescheiterter Abruf meldet sich (`lib/notice`), eine
  gescheiterte Migration macht den Deploy rot (`/health` → `scripts/check-schema.sh`), ein
  Ausfall der KI nennt seinen Grund (`ai.problem`).
- **Über die API-Grenze wird generiert, nicht gespiegelt**: Status-Katalog
  (`scripts/dump_statuses` → `lib/status-catalog.ts`) und Vokabular (`scripts/dump_vocab` →
  `lib/vocab.ts`: Instanz-Arten, Modulschlüssel und -farben, Erfassungstypen, `CapturePoint`,
  Aussondern-Modi, Geld-Richtungen, -Stufen und -Vorgaben, Incoterms, Versandarten, Kanal-Arten,
  Symbole der Zeiterfassung, Takte der Wiederholung); was die Oberfläche selbst hält (Symbol,
  Farbwert, Hover), ist gegen die generierten Schlüssel getippt (`Record<ModuleKey, …>`) – ein
  neuer Schlüssel ist ein Typfehler. Die CI prüft, dass alles Generierte aktuell ist. Jeder Aufruf in `lib/api.ts` trifft eine Backend-Route
  (`tests/test_api_routes.py`).

## Konventionen
- DB-Felder snake_case, Englisch · API `/api/v1/{resource}` · Timestamps UTC in der DB.
- **Speichern am Ende der Anfrage** (`core/database.DB`, `scope="function"`): kein Router und
  kein Dienst einer Anfrage ruft `commit` (`flush` genügt für eine Nummer; Wächter
  `test_handgriff`); Hintergrundarbeit (Takt, Abgleich, Abschreiben) speichert je Einheit.
- **Soft-Delete**: nie hard delete, nur `is_active=false` – und `is_active` gibt es **nur, wo
  wirklich gelöscht wird** (`models/base.SoftDeleteMixin`: Adressen, Referenzen, Feiertage,
  Postfächer, Nachrichten, Belegzeilen und -angebote, Passkeys, Firmen). Append-only-Tabellen,
  Ableitungen und Belege tragen die Spalte nicht. `is_active` (Soft-Delete) und `status`
  (fachlich) sind zwei Achsen – nicht verwechseln.
- **Fehler**: eine Art aus `domain/errors` mit einem Satz, der die Sache **nennt** (Nummer oder
  Name in «»); Dienste und Fachschicht kennen kein HTTP (Wächter `test_errors`). Die Antwort ist
  überall `{detail, code, field?}` (bei 422 dazu `fields`); die Oberfläche liest sie als `ApiError`
  (`message`, `code`, `field`, `fields`).
- Max. Funktionslänge 80 Zeilen · TypeScript strict, kein `any` · ESLint `no-unused-vars`.
- **Autosave** überall (`lib/use-autosave.ts`, debounced 3 s, Enter sofort, Rückmeldung im
  Karten-Kopf). Kein Speichern-Knopf – Ausnahme: das Anlegen eines Prozessschritts.
- **Datum** nur über `lib/when.ts` (`when` = Auskunft, `day` = Tag auf dem Papier).
- **Nummernkreis**: universell 9-stellig, 100'000'001–999'999'999, für ALLE Objekte;
  Registry `objects` (hält auch Nummern entfernter Typen). Einzelinstanz-Nummern und
  Rechnungsnummern (`<Auftragsnummer>-<laufend>`) sind Namen, keine Objektnummern. Rechnung
  und Gutschrift ziehen aus **einer** Zählung je Auftrag (unter Sperre, je Nummer ein
  Unique-Index); die Gutschrift ist ein eigenes Papier und nennt die Originalrechnung mit
  Nummer und Datum.
- **MWST CH** (`domain/voucher.VAT_RATES`): 8.1 % · 2.6 % · 3.8 % · 0 % Export (Ware ins Ausland) ·
  0 % Reverse Charge (Dienstleistung an eine Firma im Ausland, mit ihrer MWST-Nr.) · 0 % nicht im
  Inland steuerbar (Dienstleistung an eine Privatperson im Ausland) – je mit Pflichtsatz auf dem Beleg.

## Design System (VERBINDLICH)
Grundlage ALLER Oberflächen (Website, Konto, ERP). Regeln: **`docs/design-system/README.md`**
(vor UI-Arbeit lesen), Skill `inexxio-design-system`. Tokens **nur** in
`frontend/src/styles/design-system/colors_and_type.css` (die Website generiert ihre daraus).
Farbe = Bedeutung: **kühle, neutrale Grautöne** (v4) tragen die Fläche, **Rot (`inexxio`) ist
der eine laute Akzent** (nie in Überschriften), **Slate (`accent`) die leise Stimme**. Website:
eine Überschrift-Form, Rot nur für die Anfrage, Glas (`.ix-glass*`) nur dort, nie im ERP;
Vorlage `docs/design-system/reference/mockups/Startseite v4.dc.html`. Wörter: kein
«Fixpreis», keine «Werkstatt». ERP: Struktur vor Fläche (Haarlinien statt
Schatten), Status als Punkt + Wort, Lucide-Symbole statt Text, tabellarische Zahlen,
Infotexte im Hover, 8-px-Raster, Inter / Inter Tight. **Die Alt-Palette ist weg** (`slate-*`,
`blue-*`, `gray-*`, `brand-*`, `#2563eb`: 0 Vorkommen). Eine unbekannte Tailwind-Klasse oder
CSS-Variable erzeugt still nichts – hinsehen, nicht nur bauen.

## Schema
- **Die Migration ist der einzige Weg.** `backend/start.sh` fährt `alembic upgrade head` bei
  **jedem** Start, auf jeder Umgebung. Scheitert der Lauf, **startet der Dienst nicht** (Cloud
  Run behält die alte Revision); einzige Ausnahme ist «Can't locate revision» (die DB ist
  neuer als der Code, nach einem Revert) – dann startet er mit Warnung. Es gibt **keine
  Start-Netze** mehr (kein `create_all`, keine Spalten-/Index-Netze, keine Daten-Reparaturen
  beim Start; entfernt Oktober 2026, `docs/attic.md`).
- **Basis `161`** (`alembic/versions/161_baseline.sql`, eingefroren aus `pg_dump`) fasst die
  früheren 161 Migrationen zusammen; jede Änderung ist eine neue Migration ab `162`.
- **Eine gescheiterte Migration bleibt nie unbemerkt**: `/health` sagt `schema` (`current` ·
  `behind`), `revision` und `head` (503, wenn etwas nicht stimmt); nach jedem Deploy liest
  `scripts/check-schema.sh` das und macht den Lauf rot.
- **Der Start schreibt nur, was aus dem Code folgt**: die Trigger aus der Fachschicht
  (`statuses.terminal_guard_sql`, `timekeeping.append_only_sql`, `log.triggers_sql` – die
  Funktionen des Logs und je Tabelle ihr Zeilen-Trigger; eine Tabelle, die `domain/log.OBJECT`
  nicht kennt, hält den Start an), den Betreiber als Datensatz
  und die Rechtstexte als Dokumente (`main.lifespan`). Er löscht nichts und ernennt niemanden
  – Admin wird nur `initial_admin_email`, beim Login (`core/auth`).
- **Neue Tabelle** = voller Spaltensatz in der Migration (inkl. geerbter `is_active`,
  `created_at`, `updated_at`); Datenänderungen stehen in der Migration selbst.
  **Zwei-Deploy-Regel für Drops**: erst das Mapping weg, im Folge-Deploy die Spalte (Liste in
  `docs/backlog.md`). Ein Wächter baut das Schema aus den Migrationen und verlangt beide
  Richtungen: alles, was ein Modell kennt (Tabelle, Spalte, Index, Fremdschlüssel), steht da,
  und nichts, was kein Modell kennt (Ausnahmen in `PENDING_DROP`).

## Tests und CI
- Das Gate steht **einmal** in `.github/workflows/quality.yml`: auf jedem Push eines
  Feature-Branches, jedem Pull Request und vor Dev- **und** Prod-Deploy; drei Jobs parallel
  (mit pip-/npm-Cache). Frontend `type-check` · `lint` (ESLint trägt die Hausregeln: Datum
  nur über `lib/when`, Rollen nur über `isStaff`, kein `disabled={busy}` an Feldern) ·
  `npm test` · Build; Backend `ruff check` (nur F-Regeln, `backend/ruff.toml`), `pytest
  tests/ -rs` mit `INEXXIO_REQUIRE_DB=1` (ohne DB ein Fehler, kein stiller Skip; das Schema
  baut der Testlauf aus den Migrationen), generierte Dateien (`openapi.json`, `api.ts`,
  `status-catalog.ts`) aktuell; Website `npm test`, `astro check`, `export-erp.mjs
  --check`, Build mit `check-site`. Aus dem Deploy baut das Gate nicht (`build: false`).
- **Tests prüfen Verhalten, nicht Quelltext** – Regeln der Oberfläche prüft die Oberfläche selbst
  (`frontend/scripts/*.test.mjs`, auf dem Syntaxbaum, `scripts/lib/source.mjs`); kein Backend-Test liest
  ihren Quelltext (Wächter `test_tests_read_behaviour`); Personen und Firmen kommen aus
  `tests/factories.py` (Fixtures `make_person`, `make_firm`, `own_company`), die
  Beleg-Szene aus `tests/scenes/voucher.py`.
- **Lokal testen wie die CI**: gegen ein Schema, das nur aus den Migrationen kommt
  (`tests/test_schema_is_built_by_the_migrations.py` baut es selbst).
- Die Matrix (`tests/matrix.py`, Soll vorher notiert) und die Invarianten
  (`tests/invariants.py`) prüfen, was wahr sein muss; Bericht:
  `python -m scripts.scenario_report`.
- **Jeder neue Wächter wird gegen seine Bug-Form gegengeprüft** – ein Wächter, der nie
  anschlägt, ist von einem kaputten nicht zu unterscheiden. Wächter prüfen die **Regel**,
  nicht die Form der heutigen Lösung.

## Website (`website/`)
Eigenes Teilprojekt (Astro 7, Node ≥ 22.12), getrennt vom ERP. **Zuerst lesen:**
`website/WEBSITE_PLAN.md` (geltende Entscheide), `website/START.md` (Start-Checkliste),
`website/OFFENE_PUNKTE.md` (generiert – nie von Hand ändern; «blockiert den Start» · «für
später»). Der ursprüngliche Auftrag liegt in `docs/history/2026-10-04-website-auftrag.md`.
- **Eine Quelle**: `website/src/config/site.mjs`; Texte setzen Werte mit `{{schlüssel}}` ein.
  Was nicht feststeht, steht nicht da (keine Platzhalter-Vermerke).
- **Gestaltung v4** (Vorlage `docs/design-system/reference/mockups/Startseite v4.dc.html`):
  Startseite aus `components/home/*`. Die drei Bereiche, ihre Unterseiten, «Über uns», Service, Karriere und Ratgeber haben je ein
  eigenes Layout aus denselben Bausteinen (es gibt keine Bereichs-/Unterseiten-Vorlage mehr):
  `StageHero` (Kopf wie Porsche: grosses Wort, freigestelltes Bild mit weich auslaufenden Rändern) · `spezial/FieldCards`
  (Karten: Zeichnung, Titel, Satz, Pfeil) · `spezial/SolutionPath` (jeder Ablauf als Weg) ·
  `home/SpecialStage` (Bühne mit Umschalter, bis vier Felder) · `home/Stagger` (drei versetzte Karten,
  Überschrift dazwischen: `home/Guarantees`, Funk auf den Heukrananlagen) · `SeasonCalendar`
  (Wandkalender: Winter-Tausch, Saison-Check) · `PhotoCard` (Bildkarte; mit `illo` die Zeichnung, bis das Foto da ist) in `Magazine` (zwei Spalten
  versetzt, schmal zum Wischen: Katalog, Situationen) ·
  `ServiceTiers` (die drei Stufen als Treppe) · `FactGrid` (Sätze an Haarlinien) · `fahrzeug/*`, `kran/*`;
  Zeichnungen per Schlüssel über `lib/illustrations.ts`. Dazu `FaqStage` (höchstens 5 Fragen je
  Bereichsseite; Glas-Akkordeon über einem Bild zur offenen Frage, alle zu → Grundbild; schmal steht
  das Bild direkt über der offenen Frage) und `ContactSection` (Karte als Grund, Anfrage in zwei
  Schritten, ohne Springen; auf Wunsch eine Foto-Hilfe `hint` unter dem Formular) und `CallPanel`
  (dunkle Karte für den direkten Weg: Notfall auf /service, Bewerbung auf /karriere). Auch Service,
  Karriere und Ratgeber (Übersicht und Artikel) haben ein eigenes v4-Layout; jeder Artikel nennt seine
  Zeichnung in den Kopfangaben (`illo`).
  Freigestellte Bilder (WebP mit Transparenz) liegen in `src/assets/illustrations/`, nicht in
  der Fotoliste.
  Glas nur unter `html[data-site]` – der exportierte Kopf bleibt im ERP deckend.
- **Bilder und Videos**: Foto nach `website/src/assets/photos/`, in `src/config/photos.mjs` bei
  `file` eintragen; Video (MP4) und sein erstes Bild als Standbild (gleicher Name, `.webp`) nach
  `website/public/video/`, beim Foto `video` eintragen – in Bühne und Seitenkopf steht dann ein
  gewöhnliches `<video autoplay muted loop playsinline poster>` statt des Fotos
  (`components/Media.astro`) – geladen nur ab 768 px und ohne «reduzierte Bewegung»
  (`VIDEO_MEDIA`), sonst das Standbild; ein Knopf auf der Bühne hält jede Bewegung an. Der
  Bildrückfall ist WebP. Das Logo steht je Seite einmal als `<symbol id="ix-logo">`
  (`<use>` in Kopf, Menü, Fuss). Wörter «Fixpreis» und «Werkstatt» bricht `check-site` ab;
  das Budget zählt das Video mit.
- **Dieselbe Hosting-Site wie das ERP** (`scripts/merge-hosting.mjs`, bricht bei Kollision
  ab). Die Website besitzt «/»; das ERP `/erp`, `/konto`, `/login`, `/abmelden`,
  `/dokument`, `/agb`, `/datenschutz`, `/impressum`, `/vendor`.
- **Rechtstexte**: **AGB und Datenschutz sind Dokumente jeder eigenen Gesellschaft**
  (Pflichtfelder `company.agb` · `company.privacy`, Karte «Rechtstexte», «Aus Vorlage
  übernehmen» nur Admin; `services/legal.py`). `/agb` zeigt die AGB der Gesellschaft zum Land des
  Besuchers, `/datenschutz` und `/impressum` die des Betreibers; das Impressum sind die Angaben des
  Betreibers in der Vorlage. Vorlage: `backend/app/assets/legal/<art>/<gültig ab>.md`; Name,
  Anschrift, Kontakt und UID setzt das ERP ein (`{{firma}}` …); ein PDF steht, wie es ist. Gezeigt als
  A4-Dokument aus derselben Vorlage wie jeder Beleg (`services/a4.py`), **in echte
  A4-Seiten geteilt** – der Download hat genau so viele Seiten, wie «Seite x/n» sagt; die Schrift
  steckt im Dokument (kein Abruf bei Google). Seite `components/beleg/legal-page.tsx`.
- **Keine Beispielbilder, kein Bildnachweis**: ein fehlendes Foto ist der graue Rahmen «Foto
  fehlt» (`Photo.astro`).
- **Kopf-Menü = Mobil-Menü**: Hauptzeile Speziallösungen · Krantechnik · Fahrzeugtechnik · Service ·
  Unternehmen (Über uns · Ratgeber · Kontakt · Karriere); Kontakt ist kein eigener Punkt – Telefon und
  «Anfrage stellen» rechts sind der Weg zu uns. Ein Punkt mit Unterseiten beginnt mit seiner Übersicht
  («Alles zu …», dunkel, Stapel der Bilder; bei «Unternehmen» die Kachel «Über uns»), dann die Unterseiten – EINE
  Liste (`Header.astro`, `tilesOf`). **Jede Kachel zeigt das Titelbild ihrer Seite, sonst die Zeichnung**;
  welche Seite welches Titelbild trägt, steht EINMAL in `src/lib/titles.ts` (auch der Seitenkopf liest
  dort). Die Menübilder laden erst, wenn der Kopf berührt wird (Kachelreihe vorher nicht im Layout).
  Das Konto-Symbol ist ein Link (abgemeldet → Anmelden, angemeldet → Konto); im Profil-Menü ist die
  erste Kachel (Bild, E-Mail, Firma) zugleich der Weg ins Konto, daneben nur «Abmelden».
- **Konto und ERP tragen DENSELBEN Kopf und Fuss** (`scripts/export-shell.mjs` →
  `frontend/scripts/site-shell.mjs`); der Anmeldezustand im Kopf ist ein **Anzeige-Cache**
  (`frontend/src/lib/account-cache.ts`).
- **Kontaktdaten kommen aus dem ERP** (`GET /api/v1/public/contact`, Gesellschaft zum Land
  des Besuchers über `sites.company_for_country`, sonst der Betreiber). Eine Telefonnummer
  für alles, keine Öffnungszeiten.
- **Das Formular** (`POST /api/v1/contact`) wird eine offene Nachricht im Postfach der
  Gesellschaft zum Besucherland; E-Mail Pflicht, Anhänge nur Bilder; Spam erzeugt nichts.
  Gespeichert wird vor jedem Versand; geht das nicht → 503, die Seite zeigt Telefon und
  mailto (an die ERP-Adresse). Das Vokabular ist generiert (`scripts/export-erp.mjs` →
  `backend/app/assets/website_contact.json`).
- **Jede Seite steht in `website/src/lib/pages.ts`** oder trägt `noindex`; `check-site.mjs`
  prüft Links, JSON-LD, Sitemap, Weiterleitungen alter hs-steiner.ch-Pfade, Budget.

## Sicherheit und Datenschutz
**Gebaut:** HTTPS/HSTS, CSP und Security-Header (`firebase.json`; Google nur mit den genauen
Adressen – Anmeldung, Karten; `connect-src` nennt den eigenen Cloud-Run-Dienst genau, der Deploy
setzt ihn statt `*.a.run.app` ein – dort läuft das Gespräch mit der KI live; `unsafe-inline`/
`unsafe-eval` bleiben, solange Next-Export, Google Maps und der Scanner sie brauchen); Firebase-Anmeldung,
Passkeys serverseitig (`services/passkey.py`); Secrets nur im Google Secret Manager. **Jede
Änderung** steht im Log (`log`, von der Datenbank selbst geschrieben, mit Handelndem und
Vorgang), jeder KI-Aufruf auch (`ai.call`, Handelnder `ai` im Namen der Person); geöffnete
Dokumente (`document.read`, `document.viewed`, `voucher.viewed`) ebenso. Das Log ist
unveränderlich und je Tag versiegelt; Schwärzen (Datenschutz) nur über `log.redact`. Hochgeladene Dateien, die nicht Bild oder PDF sind, kommen mit
`Content-Security-Policy: sandbox`.
**Vorgemerkt, nicht gebaut:** TOTP-MFA für Admins, Session-Timeout, Brute-Force-Sperre.
CH DSG + DSGVO: **keine Statistik, keine Cookies, kein Einwilligungs-Dialog** (Plausible
entfernt). Buchungsbelege unveränderlich (10 Jahre).

## Pflichtregeln für Claude – vor jeder Änderung
1. **Zuerst mit Remote synchronisieren** – vor der ersten Code-Änderung einer Sitzung:
   ```bash
   git fetch origin develop
   git pull origin develop
   git log --oneline -5
   git status
   ```
2. **Dateien immer frisch lesen** – Kontext-Zusammenfassungen beschreiben Dateien, wie sie
   *waren*. Vor jedem Edit die Datei neu laden.
3. **Nur auf Basis des aktuellen `develop`-Stands** ändern – nie auf Basis früherer
   Sitzungen, ungepushter eigener Edits oder Annahmen.
4. **Branch-Workflow**: Entwicklung auf Feature-Branch (z. B. `claude/...`); Merge nach
   `develop` erst nach ausdrücklicher Freigabe; direkt auf `develop` nur auf Anweisung.
5. **Im Zweifel gilt der Code.** Eine Doku-Aussage, die der Code widerlegt, wird korrigiert,
   nicht befolgt. Ausnahme `SYSTEM_LOGIC.md`: es ist das vorher notierte **Soll** der Tests –
   widerspricht der Code einem Satz dort, ist das ein Befund (`open_finding` +
   `docs/backlog.md`), keine Doku-Korrektur; ausser der Satz beschreibt einen Ist-Zustand
   («gebaut», «es gibt kein …»), dann gilt diese Regel.
6. **CLAUDE.md beschreibt nur den Ist-Stand.** Nach einer Runde wird der Stand hier
   nachgezogen; der **Rundenbericht** (was, warum, gemessen, verworfen) gehört als
   `docs/history/<JJJJ-MM-TT>-<thema>.md` nach `docs/history/`, nie hierher.
7. **Kein Pull Request nach `main`**, solange der Weg nach `main` nicht entschieden ist: gearbeitet
   und deployt wird auf `develop`; ein offener PR `develop` → `main` lässt bei jedem Push die
   Prüfung ein zweites Mal laufen (PR #236 deshalb im November 2026 geschlossen).
8. **Rollback-Punkte als Commit-Hash nennen** – Git-Tags lassen sich aus der
   Cloud-Umgebung nicht pushen und sind auf dem Remote nicht nachweisbar.

## Lokale Entwicklung
```bash
# Backend
cd backend && pip install --require-hashes -r requirements.lock
uvicorn app.main:app --reload --port 8000

# Website, danach Frontend (ohne Website-Build sind Kopf/Fuss Platzhalter)
cd website && npm install && npm run build
cd frontend && npm install && npm run dev

# Datenbank
createdb inexxio_local
cd backend && alembic upgrade head
```

## Deployment
- **Ein Ablauf** `.github/workflows/deploy.yml` (Gate **und** Build von Website + Frontend als
  Artefakt **gleichzeitig** → erst wenn beide grün: Backend nach Cloud Run + `check-schema.sh` →
  Hosting genau dieses Artefakts); `deploy-dev.yml` und `deploy-prod.yml` rufen ihn nur mit den
  Werten ihrer Umgebung auf (Prod nach der Freigabe). Die umgerechneten Bilder der Website liegen
  im Zwischenspeicher (`actions/cache`, `website/node_modules/.astro`). Rund 4–5 Minuten.
- **Dev**: Push auf `develop`. Cloud Run `inexxio-backend-dev` (europe-west6, min 0 / max 2),
  Firebase Hosting `inexxio-dev` → https://inexxio-dev.web.app; nie indexiert (X-Robots-Tag).
- **Prod**: Push auf `main`, mit manueller Freigabe (Environment `production`); setzt den
  `/api/**`-Rewrite per `jq` auf den Prod-Dienst und bricht sonst ab (min 0 / max 2 bis zum
  Go-live; mehr Instanzen erst ab Cloud SQL `db-g1-small`).
- Erster Besuch nach einem Deploy: einmal Hard-Refresh (Ctrl+Shift+R).

## Status (Stand November 2026) – aktuell halten
Phase 1 · Deployment develop → https://inexxio-dev.web.app

**Was heute steht** (Einzelheiten in den Abschnitten oben)
- **Website** INEXXIO (ehemals HS Steiner) in Gestaltung v4 (Glas-Kopf, Bühne mit Video), Modus
  `preview` bis `website/START.md` erledigt ist.
- **Anmeldung** (Magic Link · Google · Passkeys) als Pop-up bzw. `/login?from=…` – danach nie
  auf «/», sondern `?from=` oder der Startplatz der Rolle; das Pop-up ist Glas. **Konto**: EINE Seite
  im Stil der Website (der Name als grosses Wort im Kopf, Sprungleiste, Person · Adressen · Firma ·
  Newsletter · Sicherheit; Auto-Save, Adressen, Firma und Passkeys als Karten). **Anmelde-E-Mail
  ändern**: Server prüft (`people.email_problem`), Firebase schickt den Link an die neue Adresse
  (`verifyBeforeUpdateEmail`), das Profil übernimmt sie aus dem nächsten Token. Telefon schreibt
  der Server lesbar zurück (`people.tidy_phone`).
- **Verlauf** an jedem Datensatz (Nachrichten, Notizen, Dokumente, Änderungen aus dem Log – in
  Seiten); Notiz an jedem Datensatz (ohne eigene Eingabe ausser an der Person).
- **ERP-Feed** (Master-Detail, eine Route `/erp`): Benutzer · Artikel · Aufträge · Instanzen
  · Unternehmen · Dokumente; Objektnummer, QR-Etikett und Kamera-Scan an jedem Datensatz.
- **Artikel** mit Spezifikation, Bestand in drei Ebenen, Reihe und gemeldeter Stückliste.
- **Wiederkehrende Aufträge**: die Schlaufe im Entwurf (Karte «Wiederholen» unter dem Ende, Linie
  links zurück zum Start), Nachfolger im Takt, Zahlung mit stiller Zusage, «zu tun», Beenden.
- **Prozess** mit fünf Modulen, Abweichungen, Prozessbild als Graph aus dem Log
  (`services/flow.py`) und Modul-Protokoll.
- **Beleg** (Modul «Zahlung») vollständig nach MWSTG Art. 26, Incoterms 2020, Gutschriften,
  Bezahlkarte, Swiss QR-Rechnung; Stücke ziehen von selbst weiter, am Ziel «Verkauft»; jedes
  Papier als Dokument (A4-HTML, AGB als letzte Seiten), vorher als Vorschau, per Mail mit Link
  auf die eine Dokumentseite `/dokument` (annehmen, ablehnen, bezahlen); Zahlungen-Liste an Person und
  Gesellschaft.
- **Zeiterfassung** im Personendatensatz: Wischknopf, Stundenkonto und Ferien in Stunden,
  Monat und Tag mit «Erfassen», Verträge und Buchungen (Admin), Feiertage mit Vorschlag
  (OpenHolidays) an der Gesellschaft, «zu tun» am Symbol.
- **Unternehmen** (eigene Gesellschaften mit Gebietskarte und Postfach, ein Betreiber;
  fremde Firmen als Identität) und **CRM** mit Kommunikation und Gmail; Versandarten Mail ·
  Rundschreiben · Newsletter, Einwilligung als Nachweis.
- **Dokumente** (`docs/dokumente.md`): eine Ablage für jede Datei; Entwurf mit Scannen
  (Blatterkennung, mehrere Seiten → PDF) · Datei · Verfassen (KI); Lesen, Stichworte und
  Zuordnung durch die KI als Vorschlag; Pflichtfelder in Zahlung, Zeiterfassung, Datenerfassung
  und Gesellschaft; Senden je Empfänger mit Link ohne Ablauf, Unterschreiben auf `/dokument`.
- **Der Assistent** (Phasen 3–5): das «+» als Gespräch wie bei Claude (Schreiben, Aufnehmen im
  Feld, Foto, Datei, Stecknadel; auch auf der Website für Personal); die Antwort live, Wort für
  Wort, als Markdown; Diktieren ins Feld mit Auto-Stopp nach 30 s Stille; die KI bereitet Vorschläge vor – alles, was das ERP kann, mit Probelauf; im Gespräch nur
  «Öffnen», übernommen nur von der Person am Datensatz, genau einmal; Vorschläge aus Mails am
  Datensatz; «Auf einen Blick» mit dem Wissen, das jetzt zählt (im Takt vorbereitet); im Wissen
  suchen nach Bedeutung; Deckel in Franken (siehe «Der Assistent»); Rückmeldungen zur Software
  als Notiz an den Artikeln «ERP» und «Website»; **Claude über MCP** (lesen, vorbereiten) für
  jeden Claude-Client der Person.
- **Speichern an einer Stelle**: jede Anfrage speichert einmal, am Ende (`core/database.get_db`,
  ganz oder gar nicht); was nach aussen geht (Mails, Dateien, Zahlung, KI), geschieht erst danach
  bzw. nie in einem Probelauf (`core/outside`).

**Nicht vorhanden** (entfernt, nicht abgeschaltet – `docs/attic.md`): Shop, Module
Beschaffen/Verkauf/Ausliefern, «Zahlung (alt)», das alte Dokumentmodul (neu gebaut, siehe
oben), KI-Assistent, Versand-Anbindung, Ereignis-Strom, Feature-Schalter, Kontotyp,
Statistik. Nie gebaut: Typesense-Suche, Buchhaltung, HR.

**Offen**
- Prozess-Module nach Bedarf; ein Wiederaufbau beginnt bei der Modellfrage in
  `docs/attic.md`, nicht bei der alten Datei.
- Newsletter-Versand über einen Dienst (heute Gmail, 20 je Abgleich), Rückläufer;
  Google Workspace, zentrale Gmail-Signatur, persönliche Postfächer – verschoben.
- Zeiterfassung: Export für die Lohnbuchhaltung, Schichtpläne (`docs/zeiterfassung-spezifikation.md` §12).
- Dokumente: automatische Freigabe einzelner Papiere (nicht gebaut – heute gibt jedes ein Mensch frei); Zugriff von
  aussen auf Dokumente (heute nur über einen Link).
- Der Assistent: Lektionen (ab ~100 Fällen) · «Notiz gehört woandershin» als Handlung
  (`communication.move_note` steht bereit) · Massenänderungen
  (eine eigene Handlung im ERP, dann kann die KI sie) · Schwärzen der Bedeutungs-Zahlen.
- Bewusst offen: Werkzeug-/Prüfmittel-Nachweis (`SYSTEM_LOGIC.md` §5.9), Shop
  (`docs/backlog.md`), offene-Posten-Liste je Partner, TOTP-MFA.

## Phasenplan
| Phase | Zeitraum | Inhalt |
|-------|----------|--------|
| 1 – Fundament | Mt. 1–5 | Google Cloud, Firebase Auth, Website, ERP Kern |
| 2 – Kernprozesse | Mt. 6–10 | Einkauf + Lieferantenportal, Produktion, Verkauf + Kundenportal, Stripe |
| 3 – Erweiterungen | Mt. 11–16 | NCR/8D, CAPA, Audit, Risiko, ISO 9001, HR, Buchhaltung |
| 4 – KI & Auto | Mt. 17–22 | Bestellvorschlag KI, Semantische Suche, OCR |
| 5 – Advanced | Mt. 23+ | Bexio-Integration, Onshape API, ISO 14001 |
