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
CRM mit Kommunikation und die öffentliche Website** (siehe «Status»).

## Architektur

**Im Einsatz** – verdrahtet und in Betrieb:
```
Frontend:  Next.js 14, TypeScript strict, App Router, Tailwind CSS (statischer Export)
Website:   Astro 7 (website/), reines HTML, gleiche Hosting-Site wie das ERP
Backend:   FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic v2, Alembic
DB:        PostgreSQL (Cloud SQL), universeller 9-stelliger Nummernkreis
Auth:      Firebase Authentication (Magic Link · Google SSO · Passkeys/WebAuthn)
Bilder:    in der Datenbank, ausgeliefert über einen unerratbaren Token
Karten:    Google Places (Adress-Suche in jedem Adressfeld)
Infra:     Google Cloud Run (europe-west6) + Firebase Hosting
Zahlung:   Stripe – eigene Bezahlkarte im ERP (Payment Element + Webhook). OPTIONAL:
           ohne Schlüssel gibt es den Dienst nicht (docs/stripe-setup.md)
E-Mail:    Gmail API – je eigener Gesellschaft ein Postfach, Abgleich + Versand.
           OPTIONAL: ohne OAuth-Client wird eine Mail nur erfasst (docs/gmail-setup.md)
```

**Geplant, aber NICHT verdrahtet** (keine Zeile Code): Typesense (Suche) · Claude API (KI)
· Cloud Storage (Datei-Ablage) · Carrier-Anbindung (Versand). Was davon einmal gebaut und
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
└── docs/             ← adr/ (mit Kopfstatus) · attic.md · backlog.md · design-system/ ·
                         gmail-setup.md · stripe-setup.md · passkeys.md · history/
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
- **Status** (`domain/statuses.py`, `CATALOG`): ein Eintrag trägt Beschriftung, Ampelton,
  Achsen, Bestand ↔ Historie (`stock`) und Endgültigkeit (`terminal`); ein Stück-Status ohne
  `stock` lässt die App nicht starten. Das Frontend **bekommt** den Katalog generiert
  (`scripts/dump_statuses.py` → `frontend/src/lib/status-catalog.ts`). Stücke: Freigegeben ·
  Im Prozess · Gesperrt · Verbaut · Verkauft · Verschrottet. **Verschrottet ist endgültig**,
  durchgesetzt in `_pass` **und** per DB-Trigger `trg_instance_units_terminal` – ohne
  Umgehung. `Verkauft` hat keinen Schreiber mehr, bleibt aber als Vokabular des Logs.
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
  Träger-Stück. Ändert nie Status oder Zugehörigkeit; keine Zyklen; wer zur Historie zählt,
  verliert seinen Ort (ausser Gesperrt). Eine Schreibstelle: `services/places.py`.
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
- **Zahlung** (§9.15, Schlüssel `beleg`, `domain/voucher.py` · `services/voucher.py` ·
  `beleg-work.tsx`): Geld mit einer zweiten Partei, **Einnahme ↔ Ausgabe** als Einstellung
  (`Direction`: wer den Preis nennt `quoted_by`, wer kassiert `collects`). **Bewegt keine
  Stücke.** Stufen `offer → agreed → billed` (+ Ausgänge `done`/`cancelled`). **Jedes Verb
  steht an EINER Stelle** (`services/voucher.VERBS`: Stufe · nötige Stammdaten · wer darf ·
  Funktion), und **`can` ist Auskunft UND Tor**. **Der Beleg IST die Rechnung – eine je
  Modul**; `bill` friert Nummer, Betrag, Steuer und Fälligkeit ein, `unbill` geht, solange
  kein Geld geflossen ist. Eine **Korrektur/Gutschrift ist ein eigener Beleg** in einem
  eigenen Modul (`corrects_id`, gern im Retourenauftrag – seine Positionen sind die Stücke,
  die zurückkommen). **Jede Zahl ist eine Menge**, die Richtung sagt der Beleg. Steuer je
  Position (MWSTG Art. 26), gerundet je Satz auf der Summe (`vat_split`); **eine Währung je
  Vorgang** mit ihren Nachkommastellen (`domain/currency.py`). Fehlende Stammdaten sind eine
  Zeile (`DataGap`), kein Zustand. **Mit der Zusage friert der Belegkopf ein**
  (`vouchers.head`). Wählen ist nicht anfragen (`party` schreibt, `ask` geht hinaus). Drei
  Wege zum Geld: bar (erfasst) · Überweisung (Auskunft mit RF-Referenz und Swiss
  QR-Rechnung, `services/qrbill`) · Karte (Stripe, gebucht nur vom Webhook).

Entfernt (nur noch Vermerk): Ausliefern · Beschaffen · Verkauf · «Zahlung (alt)» – siehe
`docs/attic.md`.

## CRM

- **Die Rolle ist der Zugang**: `admin` · `employee` · `user` (`people.ROLES`). Ins ERP darf
  genau `people.STAFF_ROLES` (admin, employee), im Frontend **nur** über `isStaff()`
  (`lib/record-status.ts`). **Lieferant ↔ Kunde ist eine Eigenschaft des Vorgangs**, nicht
  der Person. **Admin wird nur `initial_admin_email`** (Start und Login), nie «wer zuerst
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
  Absender wird Person, Massenpost nicht; eine eigene Adresse ist nie eine Person. Senden:
  jede Mail genau einmal (einzeln gesperrt, sofort festgeschrieben). Erledigt im ERP =
  gelesen in Gmail.
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
  Zustände**. Double Opt-in über eine Mail mit einem Knopf (sie steht im Verlauf); nur das
  Konto meldet direkt an (Adresse bestätigt). **Das ERP meldet niemanden an** – es schickt
  die Bitte, oder es meldet ab. Links signiert (HMAC, Schlüssel aus `database_url`),
  Abmeldeseite mit Knopf (gegen Link-Scanner), One-Click nach RFC 8058. Anmeldestellen:
  Häkchen im Anfrage-Formular (nie vorausgewählt), Einladung in der Eingangsbestätigung,
  Seite `/newsletter` (Link im Fuss), Konto. Wörter: `website/src/config/newsletter.mjs`.
- **Kontaktformular der Website** → offene Nachricht im ERP (`services/inquiry`), siehe
  «Website».

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
`components/erp/address-field.tsx` · `object-select.tsx` (jedes Referenzfeld) ·
`lib/when.ts` (die einzige Datums-Ausgabe) · `lib/use-autosave.ts`. Zwei Wege für dieselbe
Sache sind ein Bug, auch wenn beide funktionieren.

### Zwei Formen einer Regel – nie zwei Regeln
Braucht eine Regel eine Form, die den **Grund** nennt, und eine, die **prüft/abweist**,
stehen beide in EINEM Modul mit demselben Namensstamm (`process.pick_problem` ↔
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
- **Spiegel über die API-Grenze sind getestet** (`backend/tests/test_frontend_mirrors.py`):
  Instanz-Arten (`models/instance.KINDS`), Modul-/Erfassungssymbole, Modulschlüssel,
  `CapturePoint`, Aussondern-Modi, Geld-Richtungen und -Stufen; der Status-Katalog ist
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

## Schema und Netze
- **Die Migration ist die Wahrheit.** `backend/start.sh` fährt `alembic upgrade head` bei
  **jedem** Start, auf jeder Umgebung, auch auf dev. Scheitert der Lauf, startet uvicorn
  trotzdem, und dann tragen die **Lifespan-Netze** in `main._ensure_columns` – sie sind der
  **zweite Weg**, kein Ersatz: `_COLUMN_SAFETY_NET` (Spalten) · `_NUMERIC_SAFETY_NET` (Skala)
  · `_NULLABLE_SAFETY_NET` · `_INDEX_SAFETY_NET` · `_RAW_INDEX_SAFETY_NET` (Indizes, CHECKs,
  Fremdschlüssel). `create_all` legt nur fehlende **Tabellen** an.
- **Jede Datenänderung einer Migration braucht ihr Netz** – je eine Funktion mit eigenem
  Savepoint in `main._DATA_REPAIRS` (lesen ihre SQL aus der Fachschicht, z. B.
  `statuses.terminal_guard_sql`, `people.repair_sql`); eine
  Reparatur heilt nur, was der Katalog **nicht** kennt.
- **Der Start löscht nichts und ernennt niemanden**: kein `DROP TABLE`, der Formwächter
  (`_check_core_tables_shape`) **meldet** eine fremde Form, Admin wird nur
  `initial_admin_email`.
- **Neue Tabelle** = voller Spaltensatz in der Migration (inkl. geerbter `is_active`,
  `created_at`, `updated_at`). **Neue Spalte/Index** = Migration **und** Netz.
  **Zwei-Deploy-Regel für Drops**: erst das Mapping weg, im Folge-Deploy die Spalte
  (Liste in `docs/backlog.md`). Ein Wächter verlangt: nach `upgrade head` steht nichts, was
  kein Modell kennt (Ausnahmen in `PENDING_DROP`), und kein Netz nennt eine ungemappte
  Spalte. Migration `152` hat alles Ausstehende gedroppt (60 Spalten, 17 Tabellen
  entfernter Bereiche – nach Sicherung der produktiven DB).

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
  (`services/invariants.py`) prüfen, was wahr sein muss; Bericht:
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
  Startseite aus `components/home/*`. Die drei Bereiche, ihre Unterseiten und «Über uns» haben je ein
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
  Schritten, ohne Springen; auf Wunsch eine Foto-Hilfe `hint` unter dem Formular). `Hero` (Bildkarte)
  trägt noch die Karriere.
  Freigestellte Bilder (WebP mit Transparenz) liegen in `src/assets/illustrations/`, nicht in
  der Fotoliste.
  Glas nur unter `html[data-site]` – der exportierte Kopf bleibt im ERP deckend.
- **Bilder und Videos**: Foto nach `website/src/assets/photos/`, in `src/config/photos.mjs` bei
  `file` eintragen; Video (MP4) und sein erstes Bild als Standbild (gleicher Name, `.webp`) nach
  `website/public/video/`, beim Foto `video` eintragen – in Bühne und Seitenkopf steht dann ein
  gewöhnliches `<video autoplay muted loop playsinline poster>` statt des Fotos
  (`components/Media.astro`). Wörter «Fixpreis» und «Werkstatt» bricht `check-site` ab.
- **Dieselbe Hosting-Site wie das ERP** (`scripts/merge-hosting.mjs`, bricht bei Kollision
  ab). Die Website besitzt «/»; das ERP `/erp`, `/konto`, `/login`, `/abmelden`, `/agb`.
- **Kopf-Menü = Mobil-Menü**: Hauptzeile Speziallösungen · Krantechnik · Fahrzeugtechnik · Service ·
  Unternehmen (Über uns · Ratgeber · Karriere · Kontakt); Kontakt ist kein eigener Punkt – Telefon und
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
Passkeys serverseitig (`services/passkey.py`); Secrets nur im Google Secret Manager.
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
  · Unternehmen; Objektnummer, QR-Etikett und Kamera-Scan an jedem Datensatz.
- **Artikel** mit Spezifikation, Bestand in drei Ebenen, Reihe und gemeldeter Stückliste.
- **Prozess** mit fünf Modulen, Abweichungen, Prozessbild als Graph aus dem Log
  (`services/flow.py`) und Modul-Protokoll.
- **Beleg** (Modul «Zahlung») vollständig nach MWSTG Art. 26, Incoterms 2020, Korrekturbelege,
  Bezahlkarte, Swiss QR-Rechnung.
- **Unternehmen** (eigene Gesellschaften mit Gebietskarte und Postfach, ein Betreiber;
  fremde Firmen als Identität) und **CRM** mit Kommunikation und Gmail; Versandarten Mail ·
  Rundschreiben · Newsletter, Einwilligung als Nachweis.
- **Testnotizen** in der laufenden Oberfläche (nur Testumgebung; Skill `feedback`).

**Nicht vorhanden** (entfernt, nicht abgeschaltet – `docs/attic.md`): Shop, Module
Beschaffen/Verkauf/Ausliefern, «Zahlung (alt)», Dokumente/PDF, Rechtstexte aus dem
Dokumentmodul, KI-Assistent, Versand-Anbindung, Ereignis-Strom, Feature-Schalter, Kontotyp,
Statistik. Nie gebaut: Typesense-Suche, Buchhaltung, HR.

**Offen**
- Prozess-Module nach Bedarf; ein Wiederaufbau beginnt bei der Modellfrage in
  `docs/attic.md`, nicht bei der alten Datei.
- Newsletter-Versand über einen Dienst (heute Gmail, 20 je Abgleich), Rückläufer;
  Google Workspace, zentrale Gmail-Signatur, persönliche Postfächer – verschoben.
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
