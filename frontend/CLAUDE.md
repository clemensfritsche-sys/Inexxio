# Frontend – Next.js 14 (TypeScript)

## Technologie
Next.js 14 (statischer Export), TypeScript strict, Tailwind CSS, App Router.
Dazu **punktuell**, nicht flächendeckend: React Query (nur `konto/page.tsx`),
react-hook-form + zod (nur das Kontaktformular), ZXing (nur als dynamisch geladener
Rückfall des Scanners).

## Starten
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # Production Build
```

## Struktur
```
src/app/
├── (public)/       ← Öffentliche Website (kein Auth)
│   ├── layout.tsx  ← Navbar + Footer
│   ├── page.tsx    ← Homepage
│   ├── ueber-uns/  ← Über uns
│   ├── kontakt/    ← Kontaktformular
│   ├── impressum/  ← Impressum (dynamisch aus API)
│   ├── agb/        ← AGB (B2B + B2C Tabs)
│   └── datenschutz/← Datenschutzerklärung
├── (auth)/
│   └── login/      ← Magic Link + Google SSO + Passkey (als Pop-up ODER als Route)
│       └── verify/ ← Rückkehr aus dem Magic Link
├── (account)/
│   └── konto/      ← «Mein Profil» + «Sicherheit» (Passkeys) – der Spiegel des
│                   #   eigenen Benutzer-Datensatzes, kein zweiter Ort der Wahrheit.
└── (erp)/          ← Auth-geschützte ERP-Seiten
    └── erp/        ← Universal Feed (Master-Detail) – EINZIGE ERP-Oberfläche.
                    #   Benutzer, Artikel, Aufträge, Instanzen und Unternehmen werden
                    #   ausschliesslich hier gepflegt (Detailfenster je Datensatz);
                    #   die Plattform-Konfiguration ist ein Reiter am Betreiber.
                    #   Die früheren Admin-Seiten (`einstellungen`, `benutzer`) waren
                    #   nicht verlinkte Zweitoberflächen und sind aufgelöst.
```

## Design System (VERBINDLICH — Inexxio Design System)
> Alle UI baut auf dem **Inexxio Design System** auf. Regeln & Nutzung:
> **`../docs/design-system/README.md`**. Vor UI-Arbeit lesen.
- **Tokens (Single Source of Truth):** `src/styles/design-system/colors_and_type.css`
  (erstes CSS-Modul in `src/app/layout.tsx`). Werte nur dort definieren.
- **Tailwind-Utilities daraus:** `bg-bg-1/2/3`, `text-fg-1/2/3/4`, `text-accent`,
  `text-inexxio`, `border-border-1/2`, `rounded-ds-lg`, `shadow-ds-sm/md`,
  `font-display` (Inter Tight) / `font-body` (Inter). Zahlen `.ix-tnum`.
- **Farb-Semantik:** warme Neutraltöne = Fläche · **Rot (`inexxio`) = der eine laute
  Akzent** (CTA/aktiv/Fehler) · **Slate (`accent`) = Info/aktiv/Links** im ERP.
- **ERP:** Haarlinien + Weissraum statt Schatten; Status = Punkt+Wort; Lucide-Icons
  funktional/sparsam; Karten `rounded-ds-lg`, 8px-Grid, `max-w-7xl mx-auto`.
- **Die Alt-Palette ist weg** (August 2026): `slate-*`, `blue-*`, `gray-*`, `#2563eb` und
  der `brand-*`-Vorrat sind aus dem Code entfernt – **0 Vorkommen**. Wer sie wieder
  einführt, führt eine zweite Farbsprache ein; die Zuordnung steht als Lesehilfe in
  `docs/design-system/README.md §4`.
- **Eine unbekannte Tailwind-Klasse ist kein Fehler** – sie erzeugt schlicht kein CSS, und
  der Build schweigt. Farbgruppe und Wert können gleich heissen (`bg-bg-dark`); nach einer
  Farbänderung an einer Fläche **hinsehen**, nicht nur bauen.

## i18n
Aktuell **einsprachig Deutsch**. Das frühere next-intl-Konzept (inkl. `/messages/*.json`)
war nie verdrahtet und ist entfernt (Cleanup 2026-07); EN kommt später (KI-Übersetzung geplant).

## Auth Guard
ERP-Seiten prüfen Firebase Auth. Nicht eingeloggt → Redirect zu /login.

## API-Integration
- Client: src/lib/api.ts (fetch wrapper mit Bearer Token)
- Firebase: src/lib/firebase.ts (Magic Link, Google Sign-In)
- React Query für Serverdaten-Caching

## Typen (Single Source of Truth)
- `src/types/api.ts` wird aus dem Backend-OpenAPI-Schema generiert – NICHT editieren.
- `src/types/index.ts` leitet `UserProfile` daraus ab (nur `role` wird auf die Union verengt).
- **`src/lib/status-catalog.ts` ebenso** – aus `backend/app/domain/statuses.py`. Die
  Statusliste ist eine **Quelle, kein Spiegel**: ein neuer Status ist EINE Zeile im
  Backend, und Beschriftung/Ampelton/Achsen/Bestands-Zugehörigkeit kommen von selbst
  hier an. `lib/process-status.ts` liegt daneben und trägt nur das **Symbol** – eine
  Gestaltungsfrage, die aus dem Fachmodell nicht kommen kann.
- Neu generieren nach Backend-Schema-Änderung:
  ```bash
  cd backend && python -m scripts.dump_openapi   # → backend/openapi.json
  cd backend && python -m scripts.dump_statuses  # → frontend/src/lib/status-catalog.ts
  cd frontend && npm run generate:types          # → src/types/api.ts
  ```

## Bestand (`components/erp/stock-view.tsx`)
EIN Modul, zwei Umfänge – am **Artikel** (Zeilen = seine Instanzen) und an der **Instanz**
(Zeilen = ihre Einzelinstanzen). Der Unterschied ist der Umfang der Daten, nie die
Darstellung; eine zweite Fassung liefe beim ersten neuen Zustand auseinander.

**Am Artikel steht er zuoberst in derselben Ansicht, nicht hinter einem Reiter**
(Testnotiz #760): «wie viel habe ich davon» wird dort öfter gefragt als alles andere.
Damit hat der Artikel **gar keine Reiter mehr** – es blieb nichts, was einen zweiten
rechtfertigt.

**Eine Gruppe je Zustand – und die Ansicht zählt keinen einzigen auf.** Gruppiert wird über
die gelieferten `states`; Reihenfolge = Position im `CATALOG` (= Lebenszyklus, dieselbe wie
Leiste und Legende), Farbe = Ampelton, **zugeklappt** startet, was zur Historie zählt
(`stock`). Ein neuer Zustand erscheint damit ohne eine Zeile Änderung an seiner Stelle;
die früheren zwei festen Blöcke waren die Form, in der er verschwand. Ein Zustand ohne
Zuordnung wird **gemeldet**, nicht geraten. **Keine Gesamtzahl im Kopf** – sie summierte
auch Verschrottetes.

Karte + Kopf + Werteraster kommen aus `fields.tsx` (`SPEC`, `SpecHead`, `SpecSection`,
`ReadField`) – die Anatomie **jeder** Detail-Ansicht.

## Datenerfassung (`components/erp/capture-work.tsx`)
Eine Zeile **je Instanz**, denn ein Vorgang ist eine Instanz (PROCESS_CORE §4.4): das
Etikett klebt am physischen Ding, und eine Einzelinstanz zieht keine Objektnummer. Charge
= ein Scan, Einzelserialisierung = n Scans – **ohne** Abfrage nach der Serialisierung.

- **Ohne Bestätigung kein Formular – und genau EIN Weg dorthin.** Der Scan ist der
  Regelweg (`useScan` mit `expected` = der Objektnummer, kein eigener Dialog), die
  Tastatur die Alternative **im selben Dialog** (die Leiste im Bild). Ein zweiter Knopf
  «Von Hand bestätigen» daneben ist entfallen: er war ein zweiter Weg zum selben Ziel und
  bestätigte gar nichts. **Wie** bestätigt wurde, sagt der Dialog selbst
  (`onComplete(ids, via)` – `scan` ↔ `manual`, vorsichtig gerechnet: eine getippte oder
  gewählte Nummer macht den ganzen Vorgang `manual`). Die **Regel** ist die Ablehnung im
  Backend (`process.confirm_step`), nicht das ausgegraute Feld.
- **«Nicht bestanden» hält an — und der Haltezustand steht NEBEN dem Weg nach vorn, nie an
  seiner Stelle.** Das Modul legt **nichts** an: es zeigt den Haltezustand und öffnet auf
  Klick einen ganz gewöhnlichen Auftragsentwurf mit vorgewählten Stücken (Nummern erst auf
  Klick: `api.stepHold`). Formular und Scan-Knopf bleiben dabei da (`{work.held && …}`,
  **nicht** `held ? … : …`): `held` ist eine **Auskunft** des Servers, keine Sperre –
  `confirm_step` lehnt eine erneute Erfassung nie ab, und das nächste Urteil ersetzt das
  letzte. Wer sie ausblendet, erfindet eine Sperre, die der Dienst nicht kennt, und die
  erfundene Sperre hat keinen Schlüssel: der Auftrag steht für immer still, obwohl jeder
  Backend-Aufruf ihn weiterbewegen würde (PROCESS_CORE §4.5).
- **Die Stichprobe kommt vom Server** – die Zeile nennt die Ziehung («3 von 10 …»), die
  Definition den Satz (`ProcessStepResponse.sample`). Die Oberfläche formuliert ihn nicht
  selbst; `sampling.describe` ist die eine Quelle. Sie ist **EINE Zahl: der Anteil an der
  Gesamtmenge** (alle · Hälfte · Viertel · frei, `SAMPLE_PRESETS`) – die Kurzwege sind
  Werte derselben Zahl, keine eigenen Modi.

## Prozessschrittmodule im Entwurf (`lib/modules.ts`)
**Was ein Modultyp mitbringt, steht als Zuordnung, nicht als `if`-Kette**: `MODULE_FORM`
(Nutzlast **und ihre Umkehrform**) und `MODULE_FIELDS` im Designer (der Feldsatz). Ein neuer
Typ ist je ein Eintrag; `test_frontend_mirrors` hält die Schlüssel mit `domain/modules.py`
deckungsgleich. Ein Modul-Entwurf entsteht an **einer** Stelle (`blankModule`).

- **Ein Modul zeigt seine Sache in JEDEM Zustand** (#771): der Editor rendert seinen
  Feldsatz auch im **eingefrorenen** Prozess – gesperrt über `fieldset[disabled]`, eine
  Zeile statt eines zweiten Layouts. Vorher stand dort `renderStep: frozen ? undefined`:
  der Kopf klappte auf, und darin war nichts. Möglich macht es `MODULE_FORM[…].draft`, die
  **Umkehrform** neben ihrem Gegenstück (`moduleFromConfig`) – zwei Formen einer Regel, ein
  Namensstamm; ein eigener Lese-Feldsatz wäre die Stelle, an der die nächste Angabe fehlt.

- **Aussondern** hat zwei Angaben, beide Pflicht: Verschrotten ↔ Sperren
  (`DISPOSAL_MODES`, Liste im Backend) und der **Grund**. Keine Erfassungspunkte, keine
  Stichprobe: der Grund gehört zur Definition, nicht ans Band – dort lautete er bei jedem
  Stück gleich. Zur Laufzeit steht er als Auskunft da (`ProcessStepResponse.reason`).
- **Farbe und «Ausgang?» reisen mit dem Schritt** (`DiagramStep.tone`/`.terminal`, gefüllt
  aus `ModuleFacts`). Sie waren einmal ein Rückruf des Rahmens, gefüttert aus dem
  Modul-Katalog – und den lädt nur der Editor: im freigegebenen Auftrag kam nichts an, und
  ein stiller Rückfall gab jedem Modul die Farbe der Datenerfassung. `moduleTone` hat
  darum **keinen** Rückfall auf eine echte Modulfarbe mehr; Unbekanntes sieht kaputt aus.
- **Symbol und Farbe haben je EINE Auflösung** (`moduleIcon` / `moduleTone`), und beide
  fallen auf **sichtbar unbekannt** zurück: ein Fragezeichen bzw. die Warnfarbe. Nie auf
  das Symbol eines anderen Moduls – vorher gab es drei Rückfälle (`Blocks` = Verbrauch,
  `PackageX` = Aussondern, `CAPTURE_ICON.text` = ein blosses **T**), und ein Browser-Stand,
  der älter ist als das Backend, liess ein neues Modul damit wie ein bekanntes aussehen.
- **Hinter einem terminalen Modul bietet der Editor nichts an** – dieselbe Eigenschaft,
  aus der die Freigabe ihren Fehler zieht und das Bild sein Ende (`chainProblems` meldet
  ein Modul, das durch Umsortieren dahinter geraten ist).
- **Das Verb auf dem Knopf kommt vom Server** (`ProcessStepResponse.action`):
  «Erfassen & bestätigen» · «Verschrotten» · «Sperren». Es hängt beim Aussondern an der
  Ausprägung – ein fester Text in der Oberfläche wäre eine zweite Aussage darüber.
- Die Laufzeit ist **dieselbe Komponente** (`CaptureWork`): Zeile je Instanz, **Vorschau**,
  Scan-Gate, dann **je gezogener Einzelinstanz ein Formular**.
- **Der Scan gilt der Instanz, die Erfassung der Einzelinstanz** (PROCESS_CORE §9.5). Die
  Nutzlast ist zweistufig (`Record<string, Record<string, unknown>>`: Nummer → Punkt →
  Wert); ein flacher Satz wäre **eine** Messung, aus der n gleiche würden. Die Nummern der
  gezogenen Stücke kommen **erst nach dem Scan** (`api.stepHold(…, 'sample')`) – bei 1500
  gehört diese Liste in keine Auftrags-Antwort; die Vorschau davor kommt mit den Zahlen aus
  `step_work` aus.
- **Die Vorschau steht zentral** (`Preview` in `capture-work`), also erbt sie **jedes**
  Modul: was erfasst wird und an wie vielen Stücken – bevor gescannt wird. Der Scan bleibt
  Voraussetzung für die **Eingabe**, nicht mehr für die **Auskunft**. Je Instanz ein eigener
  Scan-Knopf; der Sammel-Knopf bleibt.
- **Terminal heisst unerreichbar**: `isPickable(status)` aus dem generierten Katalog – der
  Abweichungstrigger erscheint an einem verschrotteten Stück **gar nicht**, und die
  Vorauswahl lässt es fallen (`o.available`). Dafür muss der Zustand **mitreisen**: ihn beim
  Einlesen wegzuwerfen war die Ursache, dass die Ansicht gar nicht prüfen konnte.

## Beschaffen (`components/erp/purchase-work.tsx`)
Der Beleg an der Ausführungsstelle: `Anfrage → Bestellung → Wareneingang` als **eine
Kette**, immer dieselbe – ob im Webshop gekauft oder beim Lieferanten bestellt wird. Der
Unterschied ist nur, **wer den Preis einträgt**; ein zweiter Ablauf wäre dieselbe Angabe
ein zweites Mal.

- **Zeilen, keine Modul-Karten.** Eine Stufe ist kein Modul – sähe sie aus wie eines,
  stünden im selben Bild zwei Massstäbe. Geteilt wird die **Regel**, nicht die Form:
  kräftige Linie bis zur offenen Stelle, Haarlinie danach (wie die Hauptachse).
- **Die Stufen kommen vom Server** (`PurchaseEmbed.stages` – Schlüssel · Beschriftung ·
  `verb` · `done` · `active`). Die Oberfläche zeichnet sie, sie erfindet sie nicht; das
  Verb auf dem Knopf («Bestellen», «Wareneingang buchen») gehört der aktiven Stufe.
- **Storniert ist keine Stufe**: keine ist aktiv, kein Verb wird angeboten – die Kette
  bleibt aber gegangen, wo sie war, und ein Satz daneben sagt, dass nichts mehr ankommt.
- **Das Modul räumt selbst auf**: EINE Gegenhandlung (`revoke`), deren Wirkung die Stufe
  bestimmt. Was **Stücke** betrifft, legt es nie selbst an – dafür gibt es den ganz
  gewöhnlichen Auftragsentwurf mit vorgewählten Stücken.
- **Der Wareneingang ist der Scan**, den jedes Modul kennt: `CaptureWork` steht als
  `children` in der Stufe «Bestellung» – kein zweiter Bestätigungsweg daneben.
- **Der Beleg steht in JEDEM Zustand da**, nur die Aktionen hängen an `active`
  (Testnotiz #749). Eine Stufe zeigt, was sie trägt, sobald sie dran **oder** vorbei ist
  (`stage.active || stage.done`) – ein abgeschlossenes Modul zeigte sonst von seinem
  Beleg nichts. Ein **gesperrtes Eingabefeld ist keine Lese-Anzeige**: was feststeht,
  steht als Wert da (`ReadField`).
- **Gefragt wird nur, was der Prozess nicht schon weiss**: keine Menge (sie ist die Zahl
  der Einzelinstanzen davor), kein Termin (ableitbar), kein Speichern-Knopf (Auto-Save).
  Ohne **Lieferfrist** keine Offerte – die Regel steht im Dienst, der Knopf ist die
  freundliche Hälfte.
- **Beträge über `formatAmount`** (`lib/utils`), nicht mit einer eigenen `toLocaleString`-
  Zeile: eine zweite Kopie weicht in den Nachkommastellen ab, und ihre Zahl sieht
  trotzdem richtig aus.

## Bewegen: selbst gebracht oder eingekauft (`order-detail.Wrapped`)
Ein Transport, den eine Spedition fährt, ist eine **Leistung, die man einkauft** – also
trägt das Bewegen-Modul denselben Einkaufs-Beleg wie das Beschaffen-Modul: dieselben drei
Stufen, dieselben Verben, **dieselbe Komponente** (`PurchaseWork` wird an genau einer
Stelle gerendert). Ein zweites «Versand»-Bauteil daneben wäre der Einkauf ein zweites Mal,
und das zweite veraltet beim ersten neuen Verb.

- **Die Oberfläche fragt zwei Eigenschaften, nie den Modultyp**: `step.moves` (Ziel-Scan?)
  und `step.buys` (`'if_chosen'` → die Wahl anbieten). Beide reisen mit dem Schritt, wie
  Farbe und Beschriftung – den Modul-Katalog lädt nur der Editor.
- **Die Wahl steht dort, wo ihre Folge steht** (`Wrapped`), und nur, solange es keinen
  Beleg gibt: danach ist sie beantwortet, und «zurück» ist die Gegenhandlung des Belegs
  (`revoke`), nicht ein zweiter Schalter daneben. Sie heisst **«Selbst ↔ Beschaffen»** –
  dasselbe Wort wie das Modul, das es sonst tut, aus **einer** Quelle (`PROCUREMENT`,
  gespiegelt von `domain/procurement`).
- **Und man sieht, dass es ein Einkauf ist** (#775): über dem Beleg steht seine eigene
  Überschrift (`ProcurementHead` – getöntes Symbol · Name · Haarlinie, dieselbe Anatomie
  wie eine Modul-Karte, `ModuleMark` aus einer Quelle). Nur wo der Einkauf **nicht** der
  Zweck des Moduls ist: wo er es ist, sagt die Karte den Namen schon. Name und Farbe kommen
  vom **Beleg** (`label`/`tone`) – der Modul-Katalog ist an der Ausführungsstelle nicht
  geladen, und die Identität eines Moduls, das dort gar nicht steht, wäre geborgt.
- **Der Weg zurück steht ab der ersten Stufe da** und trägt das Wort des Belegs (`undo`) –
  er hing an «schon angefragt», also ausgerechnet nicht dort, wo am wenigsten zugesagt ist.
- **Wo kein Lieferant zugelassen ist, wird gesucht** (`ObjectSelect` + `api.searchSuppliers`)
  statt eine leere Liste zu zeigen; die zugelassene Liste bleibt, wo es sie gibt.
- **Kein «womit» mehr.** Die Liste `manuell · paket · fracht` ist entfallen: *Paket* und
  *Fracht* sind zwei **Angebote** desselben Einkaufs. Übrig bleibt ein Bit (`HAULAGE`),
  und die Antwort ist abgeleitet – eingekauft wurde, wenn es einen Beleg gibt.
  `confirmStep` schickt darum keine Transportart mehr mit.

## Referenz-Eingabe (`components/erp/object-select.tsx`)
**«Welchen Datensatz meinst du?» hat EINE Bauart** (#738). `ObjectSelect` ist **auf**
`SearchSelect` gebaut – kein zweites Auswahlfeld daneben – und trägt zusätzlich die
**Kamera im Feld**: tippen sucht auf dem Server (Nummer **oder** Name, dieselbe Bedingung
wie im Backend: `services/lookup`), scannen trifft. Beides führt zur selben Wahl, und der
Scanner bekommt dieselbe Suche mit (`suggest`).

- **Kamera und Tastatur stehen nebeneinander.** Der Scanner zuerst und die Eingabe
  darunter wäre am Band richtig und am Schreibtisch ein Umweg; umgekehrt genauso.
- **Nebeneinander heisst aber EIN Bedienelement**: die Kamera sitzt am rechten
  **Innenrand des Feldes** (`SearchSelect.action`) und ersetzt dort das Zierzeichen –
  dass es eine Liste gibt, sagt der Klick, und eine echte Aktion ist den Platz wert. Ein
  eigener Knopf daneben waren zwei Flächen für **eine** Frage.
- **Und der Dialog ist sichtbar dasselbe Feld, nur gross**: derselbe Platzhalter
  (`scan.LOOKUP_HINT`), dieselbe Zeilenform (`fields.OptionRow` – buchstäblich dasselbe
  Bauteil, Nummer tabellarisch, Name gedämpft) und dieselbe «nichts»-Zeile. Die **Sorte**
  steht in beiden als Beschriftung darüber, nicht im Platzhalter: der verschwindet beim
  ersten Zeichen, und im Vollbild bliebe dann nichts mehr, das sagt, wonach man sucht.
- **Der Aufrufer besitzt die Wahl**: `value` ist die Nummer, `selected` der bekannte
  Datensatz dazu, `onChange(nr, option)` gibt die frisch gewählte Option mit. Wer ohnehin
  mehr über ihn wissen muss (Serialisierung, Vorlage, Grund), lädt ihn **einmal**.
- **`ObjectOption` trägt die API-Form** (`object_id`/`name`) – eine eigene Schreibweise
  wäre eine Übersetzung an jeder Aufrufstelle. Wer sein Namensfeld anders nennt
  (`PlaceRef.label`), reicht es in `find` als `name` durch.
- **«Nichts» ist eine Wahl**, kein X-Knopf daneben: `emptyOption` führt sie als erste
  Zeile der Liste, und ein leeres Feld **zeigt sie an** (#734–#736).
- **Kein natives `<select>` über Datensätze** – nicht durchsuchbar, und bei tausend
  Artikeln tausend Knoten je Zeile. Aufzählungen (Währung, Land, Ja/Nein) bleiben
  erlaubt: sie sind endlich und keine Referenz. Wächter in `test_frontend_mirrors.py`.

## Eine Detail-Ansicht hat EINE Breite (`fields.DETAIL_MAXW` / `DetailBody`)
Die Satzbreite ist eine Eigenschaft der **Gattung** «Detail-Ansicht», nicht der einzelnen
Ansicht: sie steht einmal und wird über `<DetailBody>` geerbt. Vorher brachte jede Ansicht
ihre eigene mit (Artikel begrenzt, Instanz und Unternehmen über die volle Fläche, das
Unternehmen mit einer dritten Zahl) – auf einem breiten Schirm las sich derselbe
Datensatztyp je nach Reiter anders. Ein Wächter verbietet jede eigene Satzbreite daneben;
eine **Kürzungs**grenze an einer Zeile (`maxWidth: 180` mit `ellipsis`) bleibt erlaubt –
das ist eine andere Sache.

## Anmelden ist ein Pop-up (`components/auth/login-dialog.tsx`)
EIN Bauteil, zwei Aufrufer: die **Navbar** öffnet es über der Seite, auf der man steht
(`fallback={pathname}` – nach dem Anmelden landet man dort wieder), die Route `/login` ist
der zweite Weg (Umleitung, Lesezeichen) und sagt, was «daneben klicken» dort heisst: zur
Startseite. Der Knopf «Zurück zur Startseite» ist damit entfallen – daneben klicken und
`Esc` sind der Ausweg.

**Zentriert wird über `margin: auto` an der Karte, nie über `align-items` am Schleier.**
Gemessen in Chromium (375×420): mit `align-items: center` wird eine Karte, die höher als
das Fenster ist, oben **abgeschnitten**, und in einem Scroll-Container ist alles vor der
Startkante unerreichbar – im Querformat wäre das E-Mail-Feld weg.

## Symbol-Knöpfe (`.erp-actbtn` / `.erp-actbtn-icon`)
Ein Knopf besitzt seine Form in der **Klasse**, nicht an der Aufrufstelle. `.erp-actbtn`
zentriert über `justify-content` – nicht über die Polsterung: die nimmt die
Symbol-Ausprägung ja gerade weg (`padding: 0`), und ohne die Zeile sass das Symbol 16 px
daneben (gemessen). Eine Inline-Breite am Knopf verschiebt es nur; ein Wächter verbietet
sie.

## Kamera-Scan (`lib/scan.ts` + `components/scan/`)
Der QR trägt **nur die 9-stellige Objektnummer**; den Typ löst der Server auf
(`GET /erp/objects/{id}`). Drei Schichten, strikt getrennt:

| Schicht | Datei | weiss nichts von |
|---|---|---|
| Logik + **Deutung** | `lib/scan.ts` (`ScanReading`, `objectCodes`) | React, API |
| **Kamera** | `components/scan/use-camera.ts` (`useCamera`, `pickCamera`) | Codes, Decodern, dem ERP |
| **Decoder** | `components/scan/use-barcode-scanner.ts` | Strom, Linse, Taschenlampe |
| Dialog | `components/scan/scan-dialog.tsx` | Decoder, Objektnummern |

**Kamera und Decoder sind getrennt** – die Naht ist ein Rückruf (`Attach`): die
Kamera-Schicht besitzt Strom, Linsenwahl, Taschenlampe und Aufräumen und reicht das
laufende `<video>` weiter; wer daraus etwas *lesen* will, hängt sich an. Darum benutzt die
**Bild-Erfassung** (`components/erp/photo-capture.tsx`) dieselbe Kamera ohne eine Zeile
Decoder – und ohne die Ultraweitwinkel-Falle und das Track-Leck neu lernen zu müssen.

Aufruf über `useScan()` (eine Instanz am ERP-Layout, lazy). Ein Vorgang ist eine
**Sequenz**: `steps: [{label, expected?, candidates?, restrict?, exists?, suggest?}]`.
`expected` = Verifikation · `restrict`+`candidates` = eingeschränkte Wahl · sonst freier
Lookup – dann **`exists` mitgeben**, sonst gilt jede 9-stellige Zahl.

- **`label` ist die SORTE, nie eine Nummer** («Instanz», «Material», «Zielort»). Sie
  steht als **Beschriftung über der Suchleiste** – dieselbe Anatomie wie das `Label` über
  dem Referenzfeld. Die Nummer baut der Scanner selbst (`objectCodes.prompt` aus
  `expected`); steht sie auch im Label, sagt der Dialog sie zweimal (#737). Ein Wächter
  prüft die Regel, nicht den Einzelfall.
- **`objectCodes.prompt` ist der PLATZHALTER, kein Handlungsauftrag.** «scannen» stand
  darin, solange der Satz nur im Kamerabild vorkam – in einem Textfeld wäre das Verb
  falsch, und es war das Einzige, was Feld und Dialog daran hinderte, denselben Satz zu
  tragen. Dass gescannt wird, sagen Zielrahmen und Suchstrahl.
- **`emptyOption` gibt es auch im Scanner**: wo «nichts» eine gültige Wahl ist, steht sie
  als erste Zeile – sonst müsste man den Dialog schliessen, um eine Entscheidung zu
  treffen, die er selbst anbietet. Was «nichts» bedeutet, sagt der Aufrufer (`pick()`);
  der Scanner erfindet dafür keine Nummer.

- **Vorschläge: der Scanner bietet an, was er ANNIMMT** (`offersFor`). Ein
  Verifikationsschritt braucht dafür keine Suche – seine Vorschlagsmenge *ist* `expected`,
  also genügt eine Teileingabe («00787»). Das war der strukturelle Bruch: die
  Vorschlagsquelle war eine Angabe **je Aufrufer**, der Feed brachte eine mit, ein
  Prozessschrittmodul nicht – dort blieb die Liste für immer leer, und nur die volle
  neunstellige Nummer ging durch. Wo die Menge das halbe ERP wäre (freier Lookup), gibt
  der Aufrufer weiterhin `suggest` mit – **seine eigene Suche**, nicht eine zweite (der
  Feed reicht `feedMatch` + `api.getInstances` herein).
  **Die Vorschlagsmenge ist die Gültigkeitsmenge**: ein `restrict`- oder `expected`-Schritt
  fragt `suggest` gar nicht erst.
- **Kein Zwischenschritt.** Enter bzw. ein Klick auf einen Vorschlag geht direkt durch;
  passt die Nummer nicht, steht der **Grund im Zielrahmen** (dort ist der Blick, und dort
  meldet die Farbe den Zustand). Der frühere «Übernehmen»-Knopf war ein zweiter Klick für
  eine getroffene Entscheidung – und ausgerechnet gesperrt, wenn die Eingabe nicht passte,
  also genau dann, wenn der Mensch den Grund gebraucht hätte.

- **Deutung tauschen** heisst `reading` mitgeben, nicht den Dialog anfassen.
- **ZXing nur als Rückfall** und nur `await import(…)` – der native `BarcodeDetector`
  kommt zuerst (5 kB statt 112 kB gzip beim Öffnen).
- **Der Stream gehört dem Hook.** Tracks im Cleanup explizit stoppen – ZXings `stop()`
  beendet nur die Decode-Schleife, sonst wächst der Video-Puffer über jeden Scan.
- Etikett drucken: `<LabelButton objectId title kind />` im `DetailHeader`.

## Wichtige Konventionen
- 'use client' nur wenn nötig (Interaktivität, Hooks)
- **`no-unused-vars` ist scharf** (`.eslintrc.json`, läuft in der CI): eine ungenutzte
  `useState`-Destrukturierung ist die Form, in der ein Knopf ohne Wirkung auftritt.
- Server Components für statische Seiten
- **Im ERP wird nicht abgeschickt, sondern gespeichert** (`use-autosave`, debounced, grüner
  Rahmen-Flash): ein Detailfenster hat keinen Speichern-Knopf. react-hook-form + zod gelten
  nur dort, wo es ein echtes **Absenden** gibt – heute allein das Kontaktformular.
- Lucide React für alle Icons
- TypeScript strict: kein 'any'
- **Eine Abhängigkeit ohne Import ist Altlast** (`npm ls <name>` sagt nichts darüber, ob sie
  jemand *benutzt*): mit dem entfernten Bereich geht sein Paket. Vorsicht bei zwei Formen,
  die ein naives `from '<name>'` übersieht – der **Unterpfad** (`@hookform/resolvers/zod`)
  und der **dynamische** Import (`await import('@zxing/browser')`); beide sind echte Nutzung.

## Rechtliche Seiten
- Impressum: Daten dynamisch von /api/v1/admin/settings/public
- AGB: Vollständiger Schweizer Rechtstext (B2B + B2C)
- Datenschutz: Vollständig DSGVO + CH DSG konform
