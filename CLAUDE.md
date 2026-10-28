# INEXXIO – Enterprise Central System

> **Diese Datei beschreibt den IST-STAND – sonst nichts.** Wie das System so geworden ist
> (die Runden, Testnotizen, Messungen, verworfenen Anläufe), steht in
> **`docs/history/2026-10-claude-md-chronik.md`** (die frühere CLAUDE.md, wörtlich).
> **Ein Rundenbericht gehört nach `docs/history/`, nicht in CLAUDE.md.**
>
> **Lesereihenfolge:** `CLAUDE.md` (Kontext, Regeln, was gebaut ist) → `PROCESS_CORE.md`
> (die Prozesslogik, verbindlich vor jeder Arbeit am Prozess) → `SYSTEM_LOGIC.md` (die
> Regeln als prüfbare Sätze, Sackgassen-Analyse) → `docs/attic.md` (was entfernt ist und
> welche Entscheidung darin steckt) → `docs/history/` (warum es so wurde). Dazu
> `backend/CLAUDE.md`, `frontend/CLAUDE.md`, `website/WEBSITE_PLAN.md` für die Teilprojekte.
> Anforderungen (Zielbild, mit Kopfstatus): `docs/Lastenheft_v1.0.md`.

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
Infra:     Google Cloud Run (europe-west6) + Firebase Hosting
Zahlung:   Stripe – eigene Bezahlkarte im ERP (Payment Element + Webhook). OPTIONAL:
           ohne Schlüssel gibt es den Dienst nicht (docs/stripe-setup.md)
E-Mail:    Gmail API – je eigener Gesellschaft ein Postfach, Abgleich + Versand.
           OPTIONAL: ohne OAuth-Client wird eine Mail nur erfasst (docs/gmail-setup.md)
KI:        Claude API (Anthropic SDK) – EINE Tür services/ai.py: Lesen (Haiku 5.5),
           Verfassen (Sonnet 5.5), 300 Aufrufe je Tag, jeder Aufruf im Log. OPTIONAL: ohne
           ANTHROPIC_API_KEY geht alles ausser Verfassen (docs/dokumente.md)
Scanner:   OpenCV.js (Paket @techstark/opencv-js, als /vendor/opencv-<Version>.js
           ausgeliefert, geladen erst beim Scannen)
```

**Geplant, aber NICHT verdrahtet** (keine Zeile Code): Typesense (Suche) ·
Carrier-Anbindung (Versand). Was davon einmal gebaut und
wieder entfernt wurde, steht in `docs/attic.md`.

## Monorepo-Struktur
```
inexxio/
├── CLAUDE.md · PROCESS_CORE.md · SYSTEM_LOGIC.md · SYSTEM_INTENT.md · FINDINGS.md
├── website/          ← öffentliche Website (Astro) – WEBSITE_PLAN.md, START.md
├── frontend/         ← Next.js: /erp (ERP), /konto, /login, /abmelden, /agb – frontend/CLAUDE.md
├── backend/          ← FastAPI – backend/CLAUDE.md
│   └── app/{core,domain,models,schemas,routers,services}/, alembic/, scripts/, tests/
├── firebase.json     ← Hosting, Rewrites, Security-Header, Weiterleitungen alter Pfade
├── .github/workflows ← quality.yml (das Gate), deploy-dev.yml (develop), deploy-prod.yml (main)
├── infra/README.md   ← Infrastruktur, wie sie eingerichtet ist (Umgebungen, Kosten, Rollback)
├── scripts/          ← check-schema.sh (nach jedem Deploy) · dump-db.sh · reset-dev-db.sql
└── docs/             ← adr/ (mit Kopfstatus) · attic.md · backlog.md · design-system/ ·
                         gmail-setup.md · stripe-setup.md · passkeys.md · dokumente.md ·
                         history/
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
- **Ereignis-Log** (`process_events`), append-only: jeder Statuswechsel schreibt genau dort
  (`process._pass` ist die eine Schreibstelle). Bild, Protokoll, Stückliste und Journey sind
  **Ableitungen aus dem Log**, nie aus dem heutigen Zustand.
- **Exklusivität**: ein Stück ist in genau einem Auftrag aktiv – als partieller
  Unique-Index auf der offenen Zugehörigkeit (`order_units`).
- **Dokument** (`docs/dokumente.md`): Datei + Art + Name + Referenz(en), eigene
  Objektnummer. Neun Regeln; die wichtigsten: dieselbe Datei ist dasselbe Dokument, vorher gibt
  es nichts (Entwurf im Browser, «Freigeben» legt an), es erscheint genau dort, wohin seine
  Referenz zeigt, ein **Pflichtfeld** (`domain/documents.FIELDS`) ist änderbar, nie leer,
  gelöscht wird nur, was nirgends hängt. Zustand abgeleitet: Freigegeben · Unterschrift
  angefragt · Abgelehnt · Gelöscht.
- **Status** (`domain/statuses.py`, `CATALOG`): ein Eintrag trägt Beschriftung, Ampelton,
  Achsen, Bestand ↔ Historie (`stock`) und Endgültigkeit (`terminal`); ein Stück-Status ohne
  `stock` lässt die App nicht starten. Das Frontend **bekommt** den Katalog generiert
  (`scripts/dump_statuses.py` → `frontend/src/lib/status-catalog.ts`). Stücke: Freigegeben ·
  Im Prozess · Gesperrt · Verbaut · Verkauft · Verschrottet. **Verschrottet ist endgültig**,
  durchgesetzt in `_pass` **und** per DB-Trigger `trg_instance_units_terminal` – ohne
  Umgehung. **`Verkauft`** schreibt das Ziel des Auftrags: was einer anderen Partei gehört,
  wird dort «Verkauft» statt «Freigegeben» – Historie wie Verbaut (kein Bestand, kein FIFO,
  greifen nur als Abweichung).
- **Auftragsstatus** (Im Prozess · Abgeschlossen · Abgebrochen) ist abgeleitet (`_derive`),
  nie gesetzt. **Abgeschlossen** = den definierten Weg zu Ende gegangen (auch über einen
  Ausgang). Es gibt **keine Abbruch-Funktion**: der Abbruch ist eine Abweichung mit gekappter
  Rückführung.
- **Abweichungen sind ganz gewöhnliche Aufträge** (PROCESS_CORE §12): wer Stücke greift, die
  nicht auf dem Regelstart (`Freigegeben`) stehen, ist automatisch eine dokumentierte
  Abweichung. Ob ein Stück zurückkehrt, ist eine Eigenschaft der **Verbindung**
  (`order_units.return_to_order_id`). Solange eine Rückführung aussteht, ist das Modul
  gesperrt (durchgesetzt in `process.confirm_step`). **Das Greifen IST das Aufheben**
  (Gesperrt, Verbaut, Verkauft) – kein «entsperren»-Endpunkt.
- **Ort** = Zeiger am Stück (`instance_units.place_object_id` ↔ `place_unit_id`, höchstens
  eines): Halter ist eine Instanz, ein Benutzer oder ein Unternehmen, beim Verbauen das
  Träger-Stück. Ändert nie Status oder Zugehörigkeit; keine Zyklen; **jedes Stück behält
  seinen Ort, ausser es ist verschrottet** (auch Gesperrt und Verkauft). Eine Schreibstelle:
  `services/places.py`.
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
weist ab, das Bild endet dort); Kettenregel `domain/chain.py`; Farbe/Symbol reisen mit dem
Schritt (`ModuleFacts`), Unbekanntes sieht unbekannt aus; ein abgeschlossenes Modul zeigt
sein Protokoll (`services/record.py`, eine Ableitung für alle); ein Modul zeigt seine Sache
in jedem Zustand, nur die Aktionen hängen daran, ob es dran ist.

- **Datenerfassung** (PROCESS_CORE §4.4/§4.5/§9.0–§9.5, `capture-work.tsx`): **Ein Vorgang
  ist EINE Instanz** – Charge = 1 Scan, Einzelserialisierung = n Scans. Ohne Verifikation
  400; die Tastatur ist die Alternative im Scan-Dialog und wird als `verification='manual'`
  geloggt. **Der Scan gilt der Instanz, die Erfassung der Einzelinstanz** (Nutzlast Nummer →
  Punkt → Wert, Deckung in beide Richtungen). **«Nicht bestanden» rückt nicht vor** und legt
  nichts an; der Halt ist eine **Auskunft** (`held_units`), keine Sperre – das System bietet
  einen gewöhnlichen Auftrag mit vorgewählten Stücken an. **Die Stichprobe ist EINE Zahl**
  (Anteil an der Gesamtmenge, `domain/sampling.py`), gezogen einmal je Modul beim Erreichen,
  zufällig, eingefroren als `sample`-Ereignis. Erfassungspunkte: Text · Ja/Nein · Bild (nur
  Kamera, genau eine Aufnahme je Stück) · Signatur · Soll-Ist (mit Einheit) – je Typ eine
  Datei in `domain/capture_types/`.
- **Aussondern** (§9.4): Verschrotten (`Verschrottet`, endgültig) ↔ Sperren (`Gesperrt`)
  ist ein **Parameter** (`config.mode`), der Zustand wird abgeleitet (`status_after_for`).
  Ein **Ausgang**. Der **Grund ist Pflicht beim Modellieren** (`config.reason`), zur Laufzeit
  ist der Scan die Bestätigung.
- **Verbrauch** (§9.6): Komponenten **treten am Modul ein** (`process._enter_at_step`); die
  Stückliste (`config.lines`) gilt **je Produkt-Stück** und wird beim Erreichen gerechnet.
  Welche Komponente in welches Produkt ging, steht im Log (`payload.into`); die Stückliste
  eines Stücks ist eine Ableitung (`services/genealogy`). **Nichtverfügbarkeit ist kein
  Zustand** (`StepNeed`: gebraucht · verfügbar · davon am Ort); das Material muss dort
  liegen, wo das Produkt liegt (`material_place`, «am Ort» heisst in der Halter-Kette).
  `Verbaut` ist nicht terminal (Demontage = Greifen). Kein Ausgang.
- **Bewegen** (§9.8): setzt den Ort, ändert keinen Status. Das **Ziel ist optional**:
  definiert → der Scan verifiziert, offen → der Scan wählt. **Ware zuerst, Ziel zuletzt**
  (der Ziel-Scan ist die Quittung der Ablage). Eine Spedition ist ein Einkauf, also ein
  Zahlungs-Modul daneben – Bewegen weiss nichts davon.
- **Zahlung** (§9.15/§9.15s, Schlüssel `beleg`, `domain/voucher.py` · `services/voucher.py` ·
  `services/voucher_docs.py` · `beleg-work.tsx`): Geld mit einer zweiten Partei, **Einnahme ↔
  Ausgabe** als Einstellung (`Direction`). Stufen `offer → agreed → billed` (+ `cancelled`);
  **Erledigt ist abgeleitet** (Saldo 0, bei Export mit Ausfuhrnachweis). **Jedes Verb steht an
  EINER Stelle** (`VERBS`), **`can` ist Auskunft UND Tor**, die Leiste der Karte ist
  `situation` (nie leer ausser Erledigt/Storniert – Wächter «keine Sackgasse»). **Die Stücke
  passieren das Modul von selbst** – mit der Zusage, bei Vorauszahlung mit dem Geld
  (`process.advance_payments`). **Eigentum** «geht an die Partei · geht an uns» ist eine
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
  A4-Vorlage** (`services/document.py`), nennt je Position die **Seriennummer** (Instanznummer,
  `voucher.serials_of`), ist ein **Dokument** (Feld `voucher.doc`, nie löschbar;
  `voucher_documents` hält nur Link, Partei, Mail), trägt die
  AGB der stellenden Gesellschaft auf eigenen A4-Seiten. **Vorschau → Freigeben**: was ein Papier
  hinausgibt (`voucher.PAPER_VERBS`), zeigt die Karte vorher (`voucher_docs.preview`,
  zurückgerollter Lauf); **AB und Quittung stehen an** (`voucher.papers_due`, «zu tun») und
  gehen mit «Prüfen und freigeben» (Verb `release`), nie von selbst (`AUTO_RELEASE` leer). Es geht
  mit Link `/beleg?t=…` per Mail hinaus; auf dieser Seite handelt die Partei mit denselben
  Verben. Steuer je Position (MWSTG Art. 26), gerundet je Satz auf der Summe; **eine Währung
  je Vorgang**. Drei Wege zum Geld: bar · Überweisung (Swiss QR-Rechnung) · Karte (Stripe,
  gebucht nur vom Webhook; zurück auf die Karte nur, was geschuldet ist).
- **Zahlungen-Liste** (`services/payment_list.py`, `GET /erp/payments`): eine Ableitung an
  jeder Person (Abschnitt) und an jeder eigenen Gesellschaft (Reiter); Überfälliges zählt in
  «zu tun».

Entfernt (nur noch Vermerk): Ausliefern · Beschaffen · Verkauf · «Zahlung (alt)» – siehe
`docs/attic.md`.

## CRM

- **Die Rolle ist der Zugang**: `admin` · `employee` · `user` (`people.ROLES`). Ins ERP darf
  genau `people.STAFF_ROLES` (admin, employee), im Frontend **nur** über `isStaff()`
  (`lib/record-status.ts`). **Lieferant ↔ Kunde ist eine Eigenschaft des Vorgangs**, nicht
  der Person. **Admin wird nur `initial_admin_email`** (beim Login), nie «wer zuerst
  kommt». Personen werden nicht deaktiviert; Personal kann eine Person anlegen
  (`POST /erp/records`, Firebase-Konto sofort).
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
  Erinnerung) – ohne Objektnummer, ohne Status, ohne Typfeld. **Jede Nachricht hat einen
  Betreff, und das Anliegen IST der Betreff** (ohne «Re:» usw.). **Offen** = an uns, Zeitpunkt
  erreicht, keine spätere Nachricht von uns mit demselben Betreff; **überfällig nach 2 h**.
  Intern heisst intern (nur Mitarbeitende); wer von aussen schreibt, bekommt die Antwort von
  aussen. Verlauf einer Firma = der ihrer Personen. Feed-Zeichen am Symbol
  (`fields.IconMark`).
- **Gmail-Postfach je eigener Gesellschaft** (`services/mailbox.py`, Kanal `c<Objektnummer>`,
  verbindet nur ein Admin; persönliche Postfächer gibt es nicht). Die Kontakt-E-Mail der
  Gesellschaft **ist** das Postfach (gesetzt durch Verbinden, geleert durch Trennen). Abgleich
  solange das ERP offen ist (`POST /erp/messages/sync`, 30 s je Postfach); ein unbekannter
  Absender wird Person (`people.ensure`), Massenpost nicht; eine eigene Adresse ist nie eine
  Person; eine Mail, die sich nicht verarbeiten lässt, wird übersprungen (Log). Senden: jede
  Mail genau einmal (einzeln gesperrt, sofort festgeschrieben), nur über ein verbundenes
  Postfach; nach drei Abweisungen durch Gmail steht der Grund als interne Nachricht im Verlauf. Erledigt im ERP =
  gelesen in Gmail. **Ein Anhang** bleibt in Gmail, bis ihn jemand öffnet – dann geht er in den
  Entwurf eines Dokuments (`mailbox.attachment`); ebenso die Fotos des Kontaktformulars.
- **Eine Mail-Vorlage** (`services/mail_layout.py`, `compose`): Kopf · Betreff als
  Überschrift · Inhalt · Unterschrift mit dem Menschen im Namen der Gesellschaft · Fuss; was
  im Verlauf steht, ist Wort für Wort, was hinausging (`messages.html`).
- **Drei Versandarten einer E-Mail** (`domain/communication.DELIVERIES`): **Mail** (An/Cc
  sehen einander, Bcc bleibt Bcc) · **Rundschreiben** (Information an mehrere: je Person
  eine eigene Nachricht mit Anrede, im «An» nur sie) · **Newsletter** (ebenso, aber nur an
  Angemeldete, mit Abmeldelink im Fuss und `List-Unsubscribe`-Kopf). Rundschreiben und
  Newsletter sind **je Empfänger eine Nachricht** (`messages.group_id` → die erste,
  `messages.newsletter`) – im Verlauf steht, was hinausging; der Verlauf zeigt die Gruppe
  einmal («an 23»). Hinaus gehen sie über den Abgleich (`mailbox.send_due`, 20 je Lauf);
  ein Newsletter prüft die Einwilligung beim Senden noch einmal. Die Empfänger wählt heute
  der Mensch von Hand (`MessageIn.to` = Liste von Personen, kein Filter); eine Auswahl per
  KI setzt später genau dort an. In der Eingabe stehen alle fünf Arten in einer Leiste
  (Mail · Rundschreiben · Newsletter | Anruf · Intern), Anrede und Newsletter-Fuss fest
  sichtbar.
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
- **7-Tage-Regel**: ältere Tage ändert nur der Admin, im Kalender **blass**. Nur online.
- **«Zu tun»** (`services/todo`, `GET /erp/todo`): EINE Zahl am Symbol jedes Datensatzes –
  offene Nachrichten + Aufgaben der Zeiterfassung + fehlende Pflichtangaben
  (`people.missing_fields`, Quelle auch für den Fortschritt im Konto) + fehlende Feiertage +
  anstehende Papiere und erwartete Dokumente am Auftrag + fehlende Rechtstexte (Admin).
- **Nachweis einer Absenz** ist ein Dokument (Feld `time.proof`, «Nachreichen» öffnet den
  Entwurf); eine lose Datei im Korb nimmt `timekeeping.record` nicht an.

## Leitbild (VERBINDLICH)

### ERP ist Master – alles andere ist Spiegelbild
Jeder Datensatz hat **genau EINEN Ort, an dem er gepflegt wird: das ERP.** Konto, Website
und alles andere sind Spiegel. Dieselbe fachliche Angabe ist **nie an zwei Stellen
editierbar**; ausserhalb des ERP schreibt nur der **Selbstbedienungs-Pfad** einer Person auf
ihre eigenen Daten, und zwar über **denselben Pfad** (`people.apply_profile_update`).
**Das ERP muss ALLES können**, was aussen geht (`ErpAdminUpdate` erbt von
`UserProfileUpdate`).

### Eine Sache, eine Stelle
Gleiche Bedeutung → gleicher Name, gleiche Datenform, **eine** Implementierung:
`services/address.py` (Adressen) · `services/people.py` (Personennamen, Personensuche
`people.search` hinter `GET /erp/people`) · `services/address_book.py` · `services/places.py`
(Orte, Halter) · `services/lookup.py` («welchen Datensatz meinst du», Nummer ODER Name) ·
`services/sites.py` (Gesellschaften) · `objects.obj_nr` (Objektnummer) ·
`services/documents.py` (jede Datei, `file` ist die einzige Anlage) · `services/ai.py` (jeder
KI-Aufruf) · `components/erp/document-draft.tsx` (jeder Entwurf) ·
`components/erp/address-field.tsx` · `object-select.tsx` (jedes Referenzfeld) ·
`lib/when.ts` (die einzige Datums-Ausgabe) · `lib/use-autosave.ts`. Zwei Wege für dieselbe
Sache sind ein Bug, auch wenn beide funktionieren.

### Zwei Formen einer Regel – nie zwei Regeln
Braucht eine Regel eine Form, die den **Grund** nennt, und eine, die **prüft/abweist**,
stehen beide in EINEM Modul mit demselben Namensstamm (`release.pick_problem` ↔
`unpickable`, `voucher.ask_problem` ↔ `_assert_ask`, `articles.may_create`). So sagen
Oberfläche und Dienst garantiert dasselbe.

### Weitere Grundsätze
- **Ableitung statt Spalte** – eine gespeicherte Kopie ist die zweite Wahrheit (offen,
  fällig, Auftragsstatus, «inaktiv», Stückliste, Bild).
- **Nichtverfügbarkeit ist kein Zustand** – `StepNeed`/`DataGap` sind Zeilen; das System
  **bietet an**, der Mensch entscheidet; automatisch angelegt wird nie etwas.
- **`can` ist Auskunft UND Tor** – ein Knopf, der nie etwas tun kann, steht nicht da.
- **Kein Löschen, Gegenbuchung** – Soft-Delete, Korrekturbelege, Log append-only.
- **`busy` sperrt Handlungen, nie Geometrie** – ein Auto-Save verschiebt nichts.
- **Nichts scheitert still** – ein gescheiterter Abruf meldet sich (`lib/notice`), eine
  gescheiterte Migration macht den Deploy rot (`/health` → `scripts/check-schema.sh`), ein
  Ausfall der KI nennt seinen Grund (`ai.problem`).
- **Spiegel über die API-Grenze sind getestet** (`backend/tests/test_frontend_mirrors.py`):
  Instanz-Arten (`models/instance.KINDS`), Modul-/Erfassungssymbole, Modulschlüssel,
  `CapturePoint`, Aussondern-Modi, Geld-Richtungen und -Stufen, Symbole der Zeiterfassung;
  der Status-Katalog ist
  generiert statt gespiegelt. Jeder Aufruf in `lib/api.ts` trifft eine Backend-Route
  (`tests/test_api_routes.py`).

## Konventionen
- DB-Felder snake_case, Englisch · API `/api/v1/{resource}` · Timestamps UTC in der DB.
- **Soft-Delete**: nie hard delete, nur `is_active=false`. `is_active` (Soft-Delete) und
  `status` (fachlich) sind zwei Achsen – nicht verwechseln.
- **Fehler** strukturiert, mit einem Satz, der die Sache **nennt** (Nummer oder Name in «»).
- Max. Funktionslänge 80 Zeilen · TypeScript strict, kein `any` · ESLint `no-unused-vars`.
- **Autosave** überall (`lib/use-autosave.ts`, debounced 3 s, Enter sofort, Rückmeldung im
  Karten-Kopf). Kein Speichern-Knopf – Ausnahme: das Anlegen eines Prozessschritts.
- **Datum** nur über `lib/when.ts` (`when` = Auskunft, `day` = Tag auf dem Papier).
- **Nummernkreis**: universell 9-stellig, 100'000'001–999'999'999, für ALLE Objekte;
  Registry `objects` (hält auch Nummern entfernter Typen). Einzelinstanz-Nummern und
  Rechnungsnummern (`<Auftragsnummer>-<laufend>`) sind Namen, keine Objektnummern.
- **MWST CH** (`domain/voucher.VAT_RATES`): 8.1 % · 2.6 % · 3.8 % · 0 % Export · 0 %
  Reverse Charge (je mit Pflichtsatz auf dem Beleg).

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
- **Der Start schreibt nur, was aus dem Code folgt**: die drei Trigger aus der Fachschicht
  (`statuses.terminal_guard_sql`, `timekeeping.append_only_sql`,
  `process_log.append_only_sql`), den Betreiber als Datensatz
  und die Rechtstexte als Dokumente (`main.lifespan`). Er löscht nichts und ernennt niemanden
  – Admin wird nur `initial_admin_email`, beim Login (`core/auth`).
- **Neue Tabelle** = voller Spaltensatz in der Migration (inkl. geerbter `is_active`,
  `created_at`, `updated_at`); Datenänderungen stehen in der Migration selbst.
  **Zwei-Deploy-Regel für Drops**: erst das Mapping weg, im Folge-Deploy die Spalte (Liste in
  `docs/backlog.md`). Ein Wächter baut das Schema aus den Migrationen und verlangt beide
  Richtungen: alles, was ein Modell kennt (Tabelle, Spalte, Index, Fremdschlüssel), steht da,
  und nichts, was kein Modell kennt (Ausnahmen in `PENDING_DROP`).

## Tests und CI
- Das Gate steht **einmal** in `.github/workflows/quality.yml` und läuft vor Dev- **und**
  Prod-Deploy: Frontend `type-check` · `lint` · `npm test` · **Build**; Backend `ruff check`
  (nur F-Regeln, `backend/ruff.toml`);
  `alembic upgrade head` gegen ein leeres Schema, dann `pytest tests/ -rs` mit
  `INEXXIO_REQUIRE_DB=1` (ohne DB ein Fehler, kein stiller Skip); generierte
  Dateien (`openapi.json`, `api.ts`, `status-catalog.ts`) müssen aktuell sein. Website:
  `npm test`, `astro check`, `export-erp.mjs --check`, Build mit `check-site`,
  `OFFENE_PUNKTE.md` aktuell.
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
`website/OFFENE_PUNKTE.md` (generiert – nie von Hand ändern). `website/AUFTRAG.md` ist der
Wortlaut des Auftrags und in zentralen Punkten überholt.
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
  (`components/Media.astro`). Wörter «Fixpreis» und «Werkstatt» bricht `check-site` ab.
- **Dieselbe Hosting-Site wie das ERP** (`scripts/merge-hosting.mjs`, bricht bei Kollision
  ab). Die Website besitzt «/»; das ERP `/erp`, `/konto`, `/login`, `/abmelden`, `/beleg`,
  `/dokument`, `/agb`, `/datenschutz`, `/impressum`, `/vendor`.
- **Rechtstexte**: **AGB und Datenschutz sind Dokumente jeder eigenen Gesellschaft**
  (Pflichtfelder `company.agb` · `company.privacy`, Karte «Rechtstexte», «Aus Vorlage
  übernehmen» nur Admin; `services/legal.py`). `/agb` zeigt die AGB der Gesellschaft zum Land des
  Besuchers, `/datenschutz` und `/impressum` die des Betreibers; das Impressum sind die Angaben des
  Betreibers in der Vorlage. Vorlage: `backend/app/assets/legal/<art>/<gültig ab>.md`; Name,
  Anschrift, Kontakt und UID setzt das ERP ein (`{{firma}}` …); ein PDF steht, wie es ist. Gezeigt als
  A4-Dokument aus derselben Vorlage wie jeder Beleg (`services/document.py`), **in echte
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
  Im Profil-Menü ist die erste Kachel eine Auskunft, kein Knopf.
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
**Gebaut:** HTTPS/HSTS, CSP und Security-Header (`firebase.json`); Firebase-Anmeldung,
Passkeys serverseitig (`services/passkey.py`); Secrets nur im Google Secret Manager. **Jede
schreibende Anfrage** ans ERP steht im `audit_log` (`main.audit_writes`), jeder KI-Aufruf auch
(`on_behalf = ai`). Hochgeladene Dateien, die nicht Bild oder PDF sind, kommen mit
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
   nicht befolgt.
6. **CLAUDE.md beschreibt nur den Ist-Stand.** Nach einer Runde wird der Stand hier
   nachgezogen; der **Rundenbericht** (was, warum, gemessen, verworfen) gehört als
   `docs/history/<JJJJ-MM-TT>-<thema>.md` nach `docs/history/`, nie hierher.
7. **Rollback-Punkte als Commit-Hash nennen** – Git-Tags lassen sich aus der
   Cloud-Umgebung nicht pushen und sind auf dem Remote nicht nachweisbar.

## Lokale Entwicklung
```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Website, danach Frontend (ohne Website-Build sind Kopf/Fuss Platzhalter)
cd website && npm install && npm run build
cd frontend && npm install && npm run dev

# Datenbank
createdb inexxio_local
cd backend && alembic upgrade head
```

## Deployment
- **Dev**: Push auf `develop` → `.github/workflows/deploy-dev.yml` (Quality → Backend →
  Frontend+Website). Backend Cloud Run `inexxio-backend-dev` (europe-west6), Frontend
  Firebase Hosting `inexxio-dev` → https://inexxio-dev.web.app.
- **Prod**: Push auf `main` → `deploy-prod.yml` mit manueller Freigabe (Environment
  `production`); setzt den `/api/**`-Rewrite per `jq` auf den Prod-Dienst und bricht sonst ab.
- Erster Besuch nach einem Deploy: einmal Hard-Refresh (Ctrl+Shift+R).

## Status (Stand Oktober 2026) – aktuell halten
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
- **ERP-Feed** (Master-Detail, eine Route `/erp`): Benutzer · Artikel · Aufträge · Instanzen
  · Unternehmen · Dokumente; Objektnummer, QR-Etikett und Kamera-Scan an jedem Datensatz.
- **Artikel** mit Spezifikation, Bestand in drei Ebenen, Reihe und gemeldeter Stückliste.
- **Prozess** mit fünf Modulen, Abweichungen, Prozessbild als Graph aus dem Log
  (`services/flow.py`) und Modul-Protokoll.
- **Beleg** (Modul «Zahlung») vollständig nach MWSTG Art. 26, Incoterms 2020, Gutschriften,
  Bezahlkarte, Swiss QR-Rechnung; Stücke ziehen von selbst weiter, am Ziel «Verkauft»; jedes
  Papier als Dokument (A4-HTML, AGB als letzte Seiten), vorher als Vorschau, per Mail mit Link
  auf die Kundenseite `/beleg` (annehmen, ablehnen, bezahlen); Zahlungen-Liste an Person und
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
- **Testnotizen** in der laufenden Oberfläche (nur Testumgebung; Skill `feedback`).

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
- Dokumente: automatische Freigabe einzelner Papiere (`voucher.AUTO_RELEASE`); Zugriff von
  aussen auf Dokumente (heute nur über einen Link).
- Bewusst offen: Werkzeug-/Prüfmittel-Nachweis (`SYSTEM_LOGIC.md` §5.9), Shop und «Besitz»
  (`docs/konzept-beleg-shop-besitz.md`), offene-Posten-Liste je Partner, TOTP-MFA.

## Phasenplan
| Phase | Zeitraum | Inhalt |
|-------|----------|--------|
| 1 – Fundament | Mt. 1–5 | Google Cloud, Firebase Auth, Website, ERP Kern |
| 2 – Kernprozesse | Mt. 6–10 | Einkauf + Lieferantenportal, Produktion, Verkauf + Kundenportal, Stripe |
| 3 – Erweiterungen | Mt. 11–16 | NCR/8D, CAPA, Audit, Risiko, ISO 9001, HR, Buchhaltung |
| 4 – KI & Auto | Mt. 17–22 | Bestellvorschlag KI, Semantische Suche, OCR |
| 5 – Advanced | Mt. 23+ | Bexio-Integration, Onshape API, ISO 14001 |
