# Frontend – Next.js 14 (TypeScript)

> **Ist-Stand.** Wie das Frontend so geworden ist (Testnotizen, Messungen in Chromium,
> verworfene Anläufe), steht in `docs/history/2026-10-frontend-claude-md-chronik.md`. Im
> Zweifel gilt der Code.

## Technologie
Next.js 14 (statischer Export), TypeScript strict, Tailwind CSS, App Router. Dazu
**punktuell**: React Query (`@tanstack/react-query`, **nur** im Konto: `konto/page.tsx`,
`profile-section.tsx`), ZXing (nur als dynamisch geladener Rückfall des Scanners),
`@stripe/stripe-js` (dynamisch, erst auf Klick in der Bezahlkarte). Das ERP lädt seine Daten
sonst direkt über `lib/api.ts`.

## Die Website ist NICHT hier – aber Kopf und Fuss kommen von ihr
- Startseite und alle öffentlichen Seiten liefert `website/` (Astro); die CI kopiert dessen
  Ausgabe in `frontend/out`. Hier bleiben `/login`, `/abmelden`, `/konto`, `/erp` und `/agb`.
  Links auf Website-Seiten sind schlichte `<a>`.
- **Kopf und Fuss SIND die der Website** (WEBSITE_PLAN Entscheid 60). Der Website-Build legt
  HTML, Skript und ein auf `.ix-shell` beschränktes Stylesheet nach `website/dist/_shell/`;
  `scripts/site-shell.mjs` (läuft vor `dev`, `build`, `lint`, `type-check`, `test`) übernimmt
  es nach `src/generated/site-shell.json` (nicht im Repo; ohne Website-Build ein leerer
  Platzhalter, im Deploy Pflicht über `SHELL_REQUIRED=1`). `components/layout/site-shell.tsx`
  setzt es ein. Wer Kopf oder Fuss ändern will, ändert `website/src/components/Header.astro`
  bzw. `Footer.astro`.
- Das Frontend schreibt nur den **Anzeige-Cache** (`components/layout/account-sync.tsx` →
  `lib/account-cache.ts`, vier Schlüssel) und ruft `window.inexxioShell.account()`. Die
  Kopfhöhe kommt als `--site-header-h` – nie als Zahl. `lib/site-meta.json` (Name,
  Metadaten) ist generiert von `website/scripts/export-erp.mjs`.

## Starten
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # build-islands + next build
npm test           # node --test scripts/*.test.mjs
```

## Struktur
```
src/app/
├── (public)/agb/        ← AGB (B2B + B2C) – der Anmeldedialog verweist darauf
├── (auth)/login/        ← Magic Link · Google · Passkey (Pop-up ODER Route); verify/ = Magic-Link-Rückkehr
├── (auth)/abmelden/     ← Abmelde-Weg für die Website (ruft logout(), räumt den Anzeige-Cache)
├── (account)/konto/     ← «Mein Konto»: EINE Seite (Person · Adressen · Firma · Newsletter · Sicherheit) – Spiegel des eigenen Benutzer-Datensatzes
└── (erp)/erp/           ← Universal Feed (Master-Detail) – die EINZIGE ERP-Oberfläche
src/components/
├── erp/       ← alle ERP-Bauteile (siehe unten)
├── account/   ← account-shell (Kopf mit dem Namen als grossem Wort, Sprungleiste), sections/ (profile, security, passkeys)
├── auth/      ← login-dialog, passkey-nudge
├── scan/      ← scan-provider (useScan), scan-dialog, use-camera, use-barcode-scanner, object-label,
│                doc-scanner (Dokumentscanner: Blatt finden, Ecken, Seiten – `lib/doc-scan.ts`)
├── form/      ← field, save-status, kt-section (Konto: Abschnitt, Feld, Datum «TT.MM.JJJJ»; Stile `.kt-*` – Adressbuch und Firmenfeld tragen sie über `cards`/`look`)
├── layout/    ← site-shell, account-sync
└── feedback/  ← feedback-pin (Testnotizen; als Insel auch auf der Website)
src/lib/       ← api.ts · modules.ts · scan.ts · when.ts · use-autosave.ts · use-search.ts ·
                 status-catalog.ts (generiert) · process-status.ts · status-tone.ts ·
                 record-status.ts (isStaff) · account-cache.ts · login-target.ts · legal-forms.ts …
src/types/api.ts ← generiert aus backend/openapi.json – NICHT editieren
src/islands/   ← Testnotizen als Insel für die Website (scripts/build-islands.mjs)
```

### `components/erp/` – eine Zeile je Datei
| Datei | Rolle |
|---|---|
| `fields.tsx` | Grundbausteine: Detail-Anatomie (`SPEC`, `SpecHead`, `SpecSection`, `ReadField`, `DetailBody`/`DETAIL_MAXW`), `Card` (`info`, `extra`, `unclipped`, `anchor`), `SectionSep`, `TodoChip`, `Label`, `inputCls`, `SearchSelect`/`OptionRow`/`FieldAction`, `Segmented`, `StatusBadge`, `RecordIcon` (+ `IconMark`, Zahl «zu tun» aus `lib/todo`), `DetailHeader`, `Dialog`, `Tooltip`/`InfoHint` |
| `module-ui.tsx` | Bauteile eines Prozessschrittmoduls (Tabelle unten) |
| `object-select.tsx` | **Jedes Referenzfeld** («welchen Datensatz meinst du?»), Kamera im Feld |
| `address-field.tsx`, `address-book.tsx` | Jede Adress-Eingabe (Google Places) · das Adressbuch einer Person (zwei Konten) |
| `company-field.tsx` | Firmenzuordnung einer Person (Konto und ERP) |
| `communication.tsx` | Kommunikation an Person (oben auf der einen Seite, kein Reiter) und Firma (Reiter): Verlauf als Chat ab der jüngsten Nachricht, «ältere laden», einzeilige Eingabe, Postfach; Versand Mail · Rundschreiben · Newsletter (Spiegel `DELIVERIES`) |
| `user-detail.tsx`, `organization-detail.tsx`, `article-detail.tsx`, `instance-detail.tsx`, `order-detail.tsx` | Die Detail-Ansichten der fünf Datensatztypen |
| `new-record.tsx` | Anlegen aus dem Feed («+») |
| `process-designer.tsx`, `definition-lines.tsx` | Prozess-Editor (Artikel-Vorlage, Auftragsentwurf) · Bedarf/Stückliste |
| `process-diagram.tsx`, `process-columns.tsx`, `process-flow.tsx` | Prozessbild: `ModuleShell` (die Modul-Karte), drei Spuren, **ein** Liniengenerator (`polyPath`) |
| `capture-work.tsx`, `capture-form.tsx`, `photo-capture.tsx`, `signature-pad.tsx` | Ausführung von Datenerfassung, Aussondern, Verbrauch, Bewegen |
| `beleg-work.tsx`, `beleg/`, `pay-online.tsx` | Modul «Zahlung»: der Einstieg (gemeinsamer Zustand, Vorschau → Freigeben) · die Abschnitte (`stages`, `parties`, `goods`, `terms`, `quotes`, `invoice`, `documents`, `footer`, `shared`, `forms`, `paper-sheet`) · die eigene Bezahlkarte |
| `documents.tsx`, `document-detail.tsx`, `document-draft.tsx`, `document-field.tsx`, `compose-chat.tsx`, `legal-texts.tsx` | **Dokumente** (`docs/dokumente.md`): Kacheln unten an jedem Datensatz · die Seite eines Dokuments (Senden, Löschen) · **der eine Entwurf** (Scannen · Datei · Verfassen, auch als `DraftSheet` über einem Modul) · ein Pflichtfeld mit Dokument · Verfassen im Chat · AGB/Datenschutz der Gesellschaft |
| `payment-list.tsx` | **Zahlungen** einer Person (Abschnitt) oder eigenen Gesellschaft (Reiter) – eine Liste, Zeile öffnet den Auftrag |
| `step-record.tsx` | Modul-Protokoll (eine Komponente für alle Modultypen) |
| `stock-view.tsx`, `stock-bar.tsx`, `unit-number(s).tsx` | Bestand (Artikel- und Instanz-Umfang) · Leiste · Stücknummern |
| `place-trail.tsx`, `obj-id.tsx` | Ortskette eines Stücks · Objektnummer als Kennung (`.erp-objid`) |
| `time/` | **Zeiterfassung**: `time-card` (die Karte im Personendatensatz), `time-swipe` (Kommen ↔ Gehen), `time-calendar` (Monat, abgeschlossene Tage blass), `time-day` (Tag + «Erfassen», Vorschau vom Server), `time-contracts` (Verträge, Buchungen), `company-time` (Feiertage, Absenzarten, Regeln an der Gesellschaft), `time-ui` (Formate in Minuten, Symbole – Spiegel getestet) |
| `territory-map.tsx`, `world-map.tsx` | Gebietskarte |
| `detail-tabs.tsx`, `error-boundary.tsx`, `use-google-maps.ts`, `use-maps-key.ts` | Hilfen |

## Design System (VERBINDLICH)
Alle UI baut auf dem Inexxio Design System – Regeln: **`../docs/design-system/README.md`**,
Skill `inexxio-design-system`.
- **Tokens** nur in `src/styles/design-system/colors_and_type.css` (erstes CSS-Modul in
  `app/layout.tsx`). Tailwind-Utilities daraus (`bg-bg-1/2/3`, `text-fg-1…4`, `text-accent`,
  `text-inexxio`, `border-border-1/2`, `rounded-ds-lg`, `shadow-ds-sm/md`, `font-display`),
  Zahlen `.ix-tnum`.
- **Farbe = Bedeutung**: kühle, neutrale Grautöne (v4) = Fläche · Rot (`inexxio`) = der eine laute Akzent
  · Slate (`accent`) = Info/aktiv/Links im ERP.
- **ERP**: Haarlinien + Weissraum statt Schatten; Status = Punkt + Wort; Lucide-Symbole;
  8-px-Raster. Eine Detail-Ansicht hat **eine** Breite (`fields.DETAIL_MAXW` über
  `DetailBody`); eine Kürzungsgrenze an einer Zeile ist etwas anderes.
- **Alt-Palette: 0 Vorkommen** (`slate-*`, `blue-*`, `gray-*`, `brand-*`, `#2563eb`, auch
  als Hex – Ausnahme Gebietskarte).
- **Eine unbekannte Tailwind-Klasse oder CSS-Variable erzeugt still nichts** (`bg-dark` gibt
  es nicht, `bg-bg-dark` schon; `var(--x)` ohne Rückfall muss definiert sein – ein Wächter
  prüft es). Nach einer Farbänderung hinsehen, nicht nur bauen.
- **Scrollbalken sind unsichtbar** (`*`-Regel in `globals.css`); seitwärts scrollen ist
  verboten.

## Typen und generierte Quellen
- `src/types/api.ts` – aus `backend/openapi.json` (`npm run generate:types`).
- `src/lib/status-catalog.ts` – aus `backend/app/domain/statuses.py`
  (`python -m scripts.dump_statuses`). Eine **Quelle, kein Spiegel**: Beschriftung,
  Ampelton, Achsen, Bestand/Historie, Endgültigkeit kommen von dort. `lib/process-status.ts`
  trägt nur das **Symbol** und `isPickable`.
- Handgepflegte Spiegel über die API-Grenze sind getestet
  (`backend/tests/test_frontend_mirrors.py`): Instanz-Arten (`lib/record-status`),
  Modul-/Erfassungssymbole und `MODULE_FORM`-Schlüssel (`lib/modules.ts`), `CapturePoint`,
  Aussondern-Modi, Geld-Richtungen. Quelltext-Wächter liegen nach Bereich in
  `backend/tests/test_source_*.py`; jeder Aufruf in `lib/api.ts` muss eine Backend-Route
  treffen (`test_api_routes.py`).

## API-Client (`lib/api.ts`)
Fetch-Wrapper mit Bearer-Token (Firebase). **`ApiClient` bindet alle Methoden im
Konstruktor über den Prototyp** – eine als Wert weitergereichte Methode
(`search={api.searchPeople}`) behält ihr `this`. Die Personensuche heisst `searchPeople`
(`GET /erp/people`), die Firmensuche `searchCompanies`. Auth-Schutz: `/erp` und `/konto`
prüfen die Anmeldung in ihren Layouts (Redirect auf `/login?from=…`), das Backend prüft
jede Anfrage. Personal ist **nur** `isStaff(role)` (`lib/record-status.ts`, Spiegel von
`people.STAFF_ROLES`) – erlaubend gefragt.

## Regeln, die jede Oberfläche erbt
- **Im ERP wird gespeichert, nicht abgeschickt**: `lib/use-autosave.ts`
  (`useAutosaveValue` für einen Wert, `useAutosaveSignature` für einen Satz Werte; debounced
  `AUTOSAVE_DELAY` = 3 s, Enter sofort, Rückmeldung im Karten-Kopf). Kein Speichern-Knopf.
- **`busy` sperrt Handlungen, nie Geometrie und nie Werte**: kein `disabled={busy}` an einem
  Eingabefeld, nichts verschwindet während eines Auto-Saves; was erst mit der Serverantwort
  entsteht, hat seinen Platz von Anfang an.
- **Ein gescheiterter Abruf ist nie stumm** (`lib/notice.ts`): wer bei einem Fehler nichts
  anderes zu tun hat, schreibt `.catch(tell('Aufträge'))` – unten rechts steht dann «Nicht
  geladen: Aufträge – <Grund>» (`components/layout/notice-host.tsx`, im Wurzel-Layout),
  dieselbe Meldung einmal je fünf Minuten. Ein `.catch(() => {})` verbietet
  `scripts/notice.test.mjs`.
- **Datum nur über `lib/when.ts`**: `when()` = Auskunft («vor 3 Tagen», «gerade eben»),
  `day()` = Tag auf dem Papier (Beleg), `formatWhen()` gibt beides (Hover), `happened()`
  setzt Zeit + Zustandswort. Die Wörter stehen im Modul, nicht im ICU. Wächter:
  `scripts/when.test.mjs`.
- **Beträge** über `module-ui.Amount` (Währung als Kind der Zahl, gleiche Farbe, Stellenzahl
  der Währung).
- **Ein Knopf, der nie etwas tun kann, steht nicht da**; ein Knopf, der *noch nicht* kann,
  ist gesperrt und nennt den **Grund vom Server** im Hover. Ob man kann, sagt `can`.
- **Kein natives `<select>` über Datensätze** – dafür `ObjectSelect`; Aufzählungen (Währung,
  Land) dürfen eins sein.
- **Objektnummer = Kennung** (`.erp-objid`, ruhend ohne Link-Auszeichnung). Ein Name steht
  nie ohne seine Nummer.
- **Ein Symbol-Knopf besitzt seine Form in der Klasse** (`.erp-actbtn` / `.erp-actbtn-icon`,
  `.ix-tuck`), keine Inline-Breiten.

## Die Bauteile eines Moduls (`components/erp/module-ui.tsx`)
| Bauteil | Was es ist |
|---|---|
| `MODULE_CARD` · `MODULE_TITLE` | Fläche und Name der Modul-Karte (weiss wie jeder Datensatz; die Modulfarbe sitzt in der Marke und im Rahmen, wenn das Modul dran ist). Gesetzt in `ModuleShell`. |
| `ModuleSection` | Abschnitt: Leiste als Kopf, Punkt davor, wenn er ein Schritt ist (`state`: `past · active · ahead`), die Status-Spalte steht immer. `data-fb-section` benennt ihn für Testnotizen. |
| `ActionButton` · `Actions` | Ein Knopf ist ein Symbol, beim Zeigen klappt der Name daneben auf (`.ix-tuck`); `Actions` gibt ihm eine eigene, nicht umbrechende Zeile. |
| `StageAction` | Die Handlung, die eine Sache weiterbringt (volle Breite, 42 px) – Beleg und Zeiterfassung. |
| `LedgerRow` · `RowActions` | Zeilen-Grammatik `[Identifikator] [Meta] … [Aktion] [Datum] [Betrag]`, strikt einreihig; Zeilenaktionen am Ende, im Ruhezustand unsichtbar, auf Touch dauerhaft – und **in einer Zeile klappt kein Name aus** (Blase statt `.ix-tuck`). |
| `Amount` | EIN Betrag – Zahl, Währung, Zustandsfarbe. |
| `ValueBar` | Ein Anteil an einem Ganzen (Leiste + Punkt + Wort + Zahl); die Beschriftung ist das Bedienelement. `StockBar` ist ihre Ausprägung für den Bestand. |
| `ACT_H` · `FIELD_GAP` | Knopfhöhen und Feldabstand an einer Stelle. |

## Prozessschrittmodule (`lib/modules.ts`, `process-designer.tsx`)
- Was ein Modultyp im Editor mitbringt, steht als **Zuordnung**, nicht als `if`:
  `MODULE_FORM` (Nutzlast **und** Umkehrform `draft`) und `MODULE_FIELDS` (Feldsatz).
  Ein Modul-Entwurf entsteht an einer Stelle (`blankModule`).
- **Farbe und Symbol** haben je eine Auflösung (`moduleTone`, `moduleIcon`) und fallen auf
  **sichtbar unbekannt** zurück, nie auf ein anderes Modul. Sie reisen mit dem Schritt
  (`ModuleFacts`) – den Modul-Katalog lädt nur der Editor.
- **Ein Modul zeigt seine Sache in jedem Zustand**; eingefroren ist es derselbe Feldsatz,
  gesperrt über `fieldset[disabled]`. Hinter einem terminalen Modul bietet der Editor nichts
  an. Das **Verb** auf dem Knopf kommt vom Server.
- **Datenerfassung** (`capture-work.tsx`): Zeile je Instanz; ohne Scan-Bestätigung kein
  Formular (die Tastatur ist die Alternative **im** Scan-Dialog, `onComplete(ids, via)`);
  je gezogener Einzelinstanz ein Wertesatz (Nummern erst auf Klick, `api.stepHold`); der
  **Halt steht NEBEN dem Weg nach vorn** (`{work.held && …}`), nie an seiner Stelle; die
  Vorschau (was, an wie vielen) steht vor dem Scan.
- **Bewegen** fragt eine Eigenschaft (`step.moves`), nie den Modultyp; «Beim Ausführen
  definieren» ist `scan.RUNTIME_CHOICE`.

## Zahlung (`components/erp/beleg-work.tsx` + `components/erp/beleg/`)
Die Karte ist von der ersten Zeile an ein **Beleg**: oben die vier **Stationen** (`stages`),
dann ruhige Abschnitte mit Titeln vom Server – **Parteien** (Von · An, je Rechnung und
Versand/Lieferung) → **Positionen** mit Summe → **Konditionen** (+ «Es gelten unsere AGB vom
…») → **Angebote** → **Rechnung** (Geld-Zeilen, Saldo mit den Entscheiden) → **Dokumente**
(eingefroren, Link auf `/beleg?t=…`) – und unten **eine graue Leiste** (`footer.tsx`).
- **Kein `if` auf die Richtung**: Wörter, Verben und Titel reisen fertig mit; die Karte kennt
  weder «Kunde» noch «Lieferant». Wer handeln darf, sagt `can`.
- **Die Leiste ist `state`** (`voucher.situation`): Punkt + Wort, Satz und Datum
  (`date_word` + `lib/when.day`), rechts die Wege zum Geld (`Segmented`), die **eine**
  Handlung `state.primary` und das Storno-Symbol, wenn `can` `revoke` enthält. Ist ein
  Formular offen, ist die Hauptschaltfläche sein Absenden; ihr Hover nennt den Grund, aus dem
  der Dienst abweisen würde.
- **Stornieren ist ein Wort** (`undo`), in jeder Stufe; «Rechnung zurücknehmen» gibt es
  nicht, eine Geld-Zeile korrigiert «falsch erfasst?» (`reverse`, nur wo `reversible`).
- **`locked`**: die Abschnitte werden grau, nur «Stornieren» geht.
- **Ein änderbarer Wert hat EINE Form** (`Editable`, `DocPick`, `DocRef`, `.ix-editable`);
  jeder wird sofort geschrieben (eigenes Verb). Feste Vorgaben des Moduls (`fixed`) sind
  punktiert unterstrichen, `fixed_hint` im Hover. Der Steuersatz bietet nur `vat_choices`.
- **Was man bearbeitet, bleibt stehen**: jede Handlung am Beleg hält den zuletzt bearbeiteten
  Abschnitt an seiner Stelle (`lib/hold-place.ts`). **Lieferantenrechnung und Ausfuhrnachweis
  sind Dokumente** (`document-field.tsx`: vorhandenes wählen oder «Neu» über den Entwurf; die
  abgelesenen Werte füllen die leeren Felder vor). **Vorschau → Freigeben**: was ein Papier
  hinausgibt (`paper_verbs` vom Server), zeigt `beleg/paper-sheet.tsx` vorher; AB und Quittung
  stehen an (`paper_due`) und gehen mit «Prüfen und freigeben» (Verb `release`).
- **Bezahlen** (`pay-online.tsx`): unsere Karte, vom Dienst nur die Eingabefelder; die Karte
  sagt «ausgeführt», gebucht wird vom Webhook.
- **Kundenseite** (`app/(public)/beleg`, `components/beleg/`): das eingefrorene Dokument in
  einem `iframe srcdoc`, darüber die Stationen und die Handlungen der Partei
  (`api.publicBeleg` · `acceptBeleg` · `declineBeleg` · `prepareBelegPayment`); `/agb` zeigt
  das A4-Dokument vom Server (`api.publicAgb`).
- API: `updateVoucher` · `previewVoucher` · `prepareVoucherPayment` · `voucherTransfer` ·
  `refundVoucherPayment` · `paymentsOf`. Vorgaben des Moduls im Editor:
  `MONEY_FORM` in `lib/modules.ts` (Spiegel getestet).
- **Seite eines Dokuments** (`app/(public)/dokument`, `components/beleg/document-page.tsx`): das
  Papier mit Unterschriften, Unterschreiben (dieselbe Fläche wie `signature-pad.tsx`,
  `onSigned`) oder Ablehnen; gelöscht → ein Satz (410).
- **Scanner** (`components/scan/doc-scanner.tsx`): OpenCV.js unter `/vendor/opencv-<Version>.js`
  (`scripts/vendor-opencv.mjs` legt es vor `dev`/`build` ab, nicht im Repo), erst beim Scannen
  geladen; ohne OpenCV ein Fotoapparat. Die Blatterkennung (`lib/doc-scan.detect`): drei Karten
  (hell · Kanten · Kanten fein), konvexe Hülle, ein Viereck zählt nur, wenn sein Rand trägt
  (innen heller als aussen, an allen vier Seiten). Wächter `scripts/doc-scan.test.mjs`
  (nachgebildete Kamerabilder, echtes OpenCV.js).

## Referenz-Eingabe und Kamera-Scan
- **`ObjectSelect`** ist auf `SearchSelect` gebaut: tippen sucht auf dem Server (Nummer ODER
  Name), die **Kamera sitzt im Feld** (`SearchSelect.action`), beides führt zur selben Wahl.
  «Nichts» ist eine Zeile der Liste (`emptyOption`). Die Vorschlagsliste hängt per Portal an
  `document.body` (kein Vorfahr kann sie abschneiden).
- **Scanner** (`lib/scan.ts` + `components/scan/`): Logik/Deutung (`ScanReading`,
  `objectCodes`) · Kamera (`use-camera.ts`, `pickCamera`) · Decoder
  (`use-barcode-scanner.ts`, nativer `BarcodeDetector` zuerst, ZXing dynamisch) · Dialog –
  strikt getrennt. Aufruf über `useScan()` (Provider im Wurzel-Layout). Ein Vorgang ist eine
  Sequenz von Schritten (`expected` = Verifikation · `restrict`+`candidates` · sonst freier
  Lookup mit `exists`/`suggest`). Der Scanner bietet an, was er annimmt (`offersFor`);
  `label` ist die **Sorte**, nie eine Nummer. Gescannt wird die Instanz, nie das Stück.
- Etikett drucken: `<LabelButton>` im `DetailHeader` (Artikel · Instanz · Auftrag).

## Anmelden (`components/auth/login-dialog.tsx`, `lib/login-target.ts`)
EIN Bauteil: als Pop-up über der Seite oder als Route `/login?from=…`. Danach **nie auf «/»**
(das ist die Website): Ziel ist `?from=` · das gemerkte Ziel · sonst der Startplatz der
Rolle (Personal → `/erp`, alle anderen → `/konto`); navigiert wird hart (`window.location`).
Zentriert über `margin: auto` an der Karte. Wächter: `scripts/login-target.test.mjs`.

## Konventionen
- `'use client'` nur, wo nötig. Lucide React für alle Icons. TypeScript strict, kein `any`.
- **`no-unused-vars` ist scharf** (`.eslintrc.json`, CI) – ein ungenutzter Zustand ist die
  Form, in der ein Knopf ohne Wirkung auftritt.
- Einsprachig Deutsch (kein i18n verdrahtet).
- **Eine Abhängigkeit ohne Import ist Altlast** – auf Unterpfade und dynamische Importe
  achten (`await import('@zxing/browser')` ist echte Nutzung).
- Rechtliches: AGB, Datenschutz und Impressum hier (`/agb`, `/datenschutz`, `/impressum`, eine
  Komponente `components/beleg/legal-page.tsx`, Text vom Server `api.publicLegal`). Keine
  Statistik, kein Cookie-Dialog.
