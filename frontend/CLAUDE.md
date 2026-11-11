# Frontend – Next.js 16 (TypeScript)

> **Ist-Stand.** Wie das Frontend so geworden ist (Testnotizen, Messungen in Chromium,
> verworfene Anläufe), steht in `docs/history/2026-10-frontend-claude-md-chronik.md`. Im
> Zweifel gilt der Code.

## Technologie
Next.js 16 (statischer Export, Turbopack), React 19, TypeScript 5.9 strict, Tailwind CSS 3,
App Router, ESLint 9 (Flat Config `eslint.config.mjs`), Node 22. Dazu: React Query 5
(`@tanstack/react-query`) für **alles, was das ERP vom Server liest** – die Listen des Feeds
und die Detailansichten (siehe «Datenfluss») – und im Konto (`konto/page.tsx`,
`profile-section.tsx`, eigener Client); Firebase 12 (Auth); SimpleWebAuthn 14 (Passkeys,
`lib/passkey.ts`); ZXing (nur als dynamisch geladener Rückfall des Scanners);
`@stripe/stripe-js` 10 (dynamisch, erst auf Klick in der Bezahlkarte); `clsx` (`lib/utils.cn`,
setzt Klassen zusammen, mischt keine).
- **Firebase bleibt auf 12**: 13 verlangt Node ≥ 24.12, die Workflows bauen mit Node 22.
- **`@grpc/grpc-js` ist per `overrides` gehoben** (kommt nur über Firestore für Node herein,
  das das Frontend nie lädt) – `npm audit` meldet 0 Lücken.
- `next-env.d.ts` ist erzeugt (`next typegen` vor `type-check`, `next build`) und nicht im
  Repo; `npm run lint` ist `eslint .` (`next lint` gibt es nicht mehr).

## Die Website ist NICHT hier – aber Kopf und Fuss kommen von ihr
- Startseite und alle öffentlichen Seiten liefert `website/` (Astro); die CI kopiert dessen
  Ausgabe in `frontend/out`. Hier bleiben die ERP-Pfade – welche, steht EINMAL in
  `website/src/config/site.mjs` (`erpPaths`: `/erp`, `/konto`, `/login`, `/abmelden`,
  `/dokument`, `/agb`, `/datenschutz`, `/impressum`, `/vendor`). Links auf
  Website-Seiten sind schlichte `<a>`.
- **Kopf und Fuss SIND die der Website** (WEBSITE_PLAN Entscheid 60). Der Website-Build legt
  HTML, Skript und ein auf `.ix-shell` beschränktes Stylesheet nach `website/dist/_shell/`;
  `scripts/site-shell.mjs` (läuft vor `dev`, `build`, `lint`, `type-check`, `test`) übernimmt
  es nach `src/generated/site-shell.json` (nicht im Repo; ohne Website-Build ein leerer
  Platzhalter, im Deploy Pflicht über `SHELL_REQUIRED=1`). `components/layout/site-shell.tsx`
  setzt es ein. Wer Kopf oder Fuss ändern will, ändert `website/src/components/Header.astro`
  bzw. `Footer.astro`. **Gleich bis aufs Glas** (gemessen in Chromium, 1440/390 px): Tailwinds
  Preflight wird in `.ix-shell` zurückgenommen (`globals.css`: Laufweite der Knöpfe,
  `vertical-align` der Symbole), `<html lang="de-CH">` wie die Website. Gewollt verschieden:
  Glas und Schleier nur unter `html[data-site]`; im ERP ist die Kopf-Karte deckend weiss mit
  Haarlinie (`--line`).
- Das Frontend schreibt nur den **Anzeige-Cache** (`lib/account-cache.ts`: vier Schlüssel,
  gelesen und geschrieben nur über `cachedRole`/`rememberRole`/`rememberName`/
  `rememberContact`/`rememberPhoto`/`clearAccountCache`; Name, Kontakt und Bild schreibt
  `components/layout/account-sync.tsx`) und ruft `window.inexxioShell.account()`. Die
  Kopfhöhe kommt als `--site-header-h` – nie als Zahl. `lib/site-meta.json` (Name,
  Metadaten) ist generiert von `website/scripts/export-erp.mjs`.

## Starten
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # next build
npm test           # node --test scripts/*.test.mjs
npm run lint       # eslint .
```
Ausgeliefert wird der statische Export (`out/`) über Firebase Hosting – `next start` gibt es
nicht, ein Frontend-Bild auch nicht.

## Struktur
```
src/app/
├── (public)/agb/        ← AGB (B2B + B2C) – der Anmeldedialog verweist darauf
├── (auth)/login/        ← Magic Link · Google · Passkey (Pop-up ODER Route); verify/ = Magic-Link-Rückkehr
├── (auth)/abmelden/     ← Abmelde-Weg für die Website (ruft logout(), räumt den Anzeige-Cache)
├── (account)/konto/     ← «Mein Konto»: EINE Seite (Person · Adressen · Firma · Newsletter · Sicherheit) – Spiegel des eigenen Benutzer-Datensatzes
└── (erp)/erp/           ← Universal Feed (Master-Detail) – die EINZIGE ERP-Oberfläche;
                           erfassen/ = dasselbe «+» zum Einbetten (die Website zeigt es Personal
                           in einem Rahmen, `html[data-embed]`: ohne Kopf und Fuss);
                           verbinden/ = «Claude verbinden» (MCP: erlauben → zurück zum Client)
src/components/
├── erp/       ← alle ERP-Bauteile (siehe unten)
├── account/   ← account-shell (Kopf mit dem Namen als grossem Wort, Sprungleiste), sections/ (profile, security – Passkeys und Claude kommen aus `erp/person-access`)
├── auth/      ← login-dialog, passkey-nudge, auth-gate (Schutz von /erp und /konto, `staffOnly`)
├── scan/      ← scan-provider (useScan), scan-dialog, use-camera, use-barcode-scanner, object-label,
│                doc-scanner (Dokumentscanner: Blatt finden, Ecken, Seiten – `lib/doc-scan.ts`)
├── form/      ← field + use-field (**der Feld-Baustein**, siehe unten), save-status, kt-section (Konto: Abschnitt, Feld, Datum «TT.MM.JJJJ»; Stile `.kt-*` – Adressbuch und Firmenfeld tragen sie über `cards`/`look`)
└── layout/    ← site-shell, account-sync
src/lib/       ← api.ts · modules.ts · scan.ts · when.ts (auch `NOTHING`) · status-catalog.ts · vocab.ts (beide generiert) ·
                 process-status.ts · status-tone.ts · record-status.ts (isStaff) · account-cache.ts ·
                 login-target.ts · legal-forms.ts · feed.ts (was ein Pfad ändert, `TOUCHES`) ·
                 queries.ts (Schlüssel der Detailansichten, `useDebouncedQuery`) ·
                 saver.ts (Kern des Auto-Saves) · process-graph.ts (Prozessbild, reine
                 Funktionen) · web-link.ts · notice.ts · draft.ts (der Entwurf im «+», nur im Browser) · recorder.ts (Aufnehmen ohne
                 Browser: Abschnitte, Stücke, Warteschlange – Wächter `scripts/recorder.test.mjs`,
                 der Anschluss `scripts/use-recorder.test.mjs`) · transcribe.ts (eine Aufnahme
                 zu Ende abschreiben lassen, auch wenn das «+» zu ist) · assistant.ts (Gespräche,
                 Aufnahmen, «Auf einen Blick» – die Queries des Assistenten) · pin-point.ts (die
                 Stecknadel: auf eine Stelle zeigen, «Stelle: …», Artikel «ERP»/«Website») ·
                 proposal-draft.ts (ein Vorschlag ganz als Entwurf: Auftrag und Artikel mit allen
                 Zeilen, Schritten, Wiederholung; Rest in `left` – `scripts/proposal-draft.test.mjs`)
                 … und **alle Hooks** als `use-*.ts`
                 (use-action, use-dialog, use-outside, use-autosave, use-search, use-profile-completion, use-google-maps,
                 use-maps-key, use-feed, use-feed-lists, use-mail-sync, use-url-params,
                 use-recorder = Mikrofon, `MediaRecorder`, Pegel, Wake Lock);
                 nur Kamera und Decoder liegen beim Scanner (components/scan/)
src/types/api.ts ← generiert aus backend/openapi.json – NICHT editieren
```

### `components/erp/` – eine Zeile je Datei
| Datei | Rolle |
|---|---|
| `skeleton.tsx` | **Laden = die graue Form dessen, was kommt**: `Skeleton` (`lines` · `rows` · `block`) und `DetailSkeleton` (ganzes Fenster) – an jeder Stelle, die auf den Server wartet; kein «Lädt …», kein Kreisel. Der Schimmer ist `.erp-skel` (still bei «weniger Bewegung») |
| `fields.tsx` | Grundtöne: `MICRO_LABEL`, `StatusDot` (der eine Zustandspunkt, 6 px), `StatusBadge`, `Row` |
| `detail-frame.tsx` | Anatomie eines Datensatz-Fensters: `DetailHeader`, `RecordIcon` (+ `IconMark`, rotes Zeichen der Aufgaben aus `lib/todo`; «!» = niemand da, der es kann), `TodoChip` (das Zeichen an der Stelle; an meiner Aufgabe «Abgeben»), `TodoAt` (Stelle mit Sprungziel und Zeichen), `HeaderAction`, `DetailBody`/`DETAIL_MAXW`, `Card` (`info`, `extra`, `unclipped`, `anchor`), `SPEC`, `SpecHead`, `SpecSection`, `ReadField` (Link nur ins Web, `lib/web-link`), `SectionSep`, `TodoChip` |
| `controls.tsx` | Bedienelemente: **die eine Feldform** `inputClass` (normal · warn · read) / `inputCls`, **die eine Beschriftung** `Label` (13 px, `fg-2`, Satzschreibung; Pflicht = `RequiredMark`, ein `*` in `--warning`), `IconSwitch`, `Segmented`, `Dialog` (modal; das Verhalten aus `lib/use-dialog`), `Palette`, `numericOnly`, `FieldAction` |
| `search-select.tsx`, `hints.tsx` | `SearchSelect`/`OptionRow` (Liste per Portal am `body`) · **die eine Hover-Blase** `TipHost` (Wurzel-Layout) + `Tooltip`, `InfoHint`, `ErrorText` |
| `feed-panel.tsx`, `detail-pane.tsx` | Die zwei Hälften der Feed-Seite: Liste (Suche, Typ-Filter, Zeilen, «+») · Detail (was angelegt wird oder ausgewählt ist, im `ErrorBoundary`; **jede Ansicht und das «+» laden erst beim Öffnen**, `next/dynamic` mit `DetailSkeleton`) |
| `module-ui.tsx` | Bauteile eines Prozessschrittmoduls (Tabelle unten) |
| `object-select.tsx` | **Jedes Referenzfeld** («welchen Datensatz meinst du?»), Kamera im Feld |
| `address-field.tsx`, `address-book.tsx` | Jede Adress-Eingabe (Google Places) · das Adressbuch einer Person (zwei Konten) |
| `company-field.tsx` | Firmenzuordnung einer Person (Konto und ERP) |
| `person-access.tsx` | **Der Zugang einer Person** (Konto «Sicherheit» und ERP-Karte «Zugang», `owner` wie `AddressBook`): `PasskeyList` (entfernen; einrichten nur im Konto) · `ClaudeList` (erlaubt, zuletzt benutzt, trennen); Schlüssel `qk.access` |
| `history.tsx` | **Der Verlauf** – EINE Komponente an jeder Detailansicht (Person, Firma, Auftrag, Artikel, Instanz, Dokument): `useHistory` (`useInfiniteQuery`, Seiten vom Server, «ältere laden» beim Rollen), Nachrichten als Blasen, Dokumente als Zeile, Änderungen je Handlung technisch (`feld: alt → neu`, Festbreite) |
| `communication.tsx` + `communication/` | Kommunikation an Person (oben auf der einen Seite, kein Reiter) und Firma (Reiter «Verlauf»): die Ansicht (`communication.tsx`: Postfach, `History`, Eingabe) · `timeline` (die Blase einer Nachricht, Tagestrenner, die wartende Mail) · `composer` (einzeilige Eingabe, **ein** Zustand `Draft`, «Rückgängig») · `mailboxes` (Postfach) · `shared` (Person, Arten, Versand Mail · Rundschreiben · Newsletter – `DELIVERIES` aus `lib/vocab`) |
| `user-detail.tsx`, `organization-detail.tsx`, `article-detail.tsx`, `instance-detail.tsx`, `order-detail.tsx` | Die Detail-Ansichten der fünf Datensatztypen |
| `new-record.tsx` | Person und Firma anlegen (Entwurf; `initial` = vorausgefüllt aus einem Handgriff) |
| `capture/` | **«+» = der Assistent – EIN Gespräch wie bei Claude** (Phase 5): `capture-sheet` (die Eingabe: **das Feld bleibt immer stehen**, Enter = senden; 📷/📄 hängen die Datei an die Nachricht (Korb), auch mit Ctrl+V oder hineinziehen; 📌 Stecknadel als Chip «📍 …» (`lib/pin-point`); 🎤 Aufnahme dezent in der Leiste (`RecordingBar`), der abgeschriebene Text kommt ans Ende des Feldes (`useDictation`, «schreibt ab …» im Feld), gesendet von der Person (`api.say({recordings})`); was im Feld steht, ist der Entwurf `lib/draft` (nur im Browser, bleibt beim Schliessen) – **vor dem Senden entsteht nichts**; darüber das Gespräch – Blasen (die KI als Markdown, `markdown.tsx`) und Vorschlag-Karten; während die KI antwortet, live jeder ihrer Schritte, dann ihr Text Wort für Wort, und ➤ wird zum Stopp (`api.stopTalk`); «←» zurück zur Übersicht: «Offene Gespräche» (Aufnahmen nur, wenn sie nicht abgeschrieben werden konnten) und «Neu anlegen»; während einer Aufnahme nicht schliessbar; `host` = wo die Stecknadel zeigt) · `handgriff-card` (**ein Vorschlag** – Zeile, Datensatz, Quelle; im Gespräch nur **Öffnen** (Entwurf über `DRAFTS`, sonst der Datensatz über `useErpNav`) und ✕; am Datensatz (`at="record"`) was sich ändert, alt → neu, und **Übernehmen** bzw. «Entwurf öffnen») · `recorder` (`RecordingBar`: Punkt, Zeit, Pegel, ■; `recordingWord`) · `markdown` (Markdown als React-Elemente, nie HTML; Wächter `scripts/markdown.test.mjs`) · `capture-context` (`openDraft` – der Entwurf, gehalten von der Feed-Seite bzw. `/erp/erfassen`) · `proposal-left` (was aus einem Vorschlag nicht in den Entwurf passte, oben im Entwurf) |
| `pinned.tsx` | **Auf einen Blick** unten im Verlauf (`History`): offene Vorschläge (dieselbe Karte, hier mit alt → neu und «Übernehmen»), dann das Wissen, das jetzt zählt (Datum, Quelle); meist im Takt vorbereitet, sonst neu gewählt still im Hintergrund, wenn sich im Umfeld etwas änderte (`lib/assistant.usePinned`); Sprungziel `data-todo="handgriffe"` |
| `process-designer.tsx`, `definition-lines.tsx` | Prozess-Editor (Artikel-Vorlage, Auftragsentwurf) · Bedarf/Stückliste |
| `loop-card.tsx` | **Die Wiederholung** unter dem Ende: im Entwurf einschalten und einstellen (`LoopDraftCard`, Nutzlast `loopPayload`), am laufenden Auftrag Zustand + Satz + «Beenden» (`LoopRunCard`, `api.endLoop`); die Linie links zurück zum Start ist `process-columns.LoopLine` (Zeile `loop` in `columnRows`) |
| `flow-column.tsx`, `module-card.tsx`, `process-columns.tsx`, `process-flow.tsx` | Prozessbild: die Spalte (`FlowColumn`, Achse, Zustände, Herkunft) · die Modul-Karte (`ModuleShell`, `StepCard`, `ModuleMark`) · drei Spuren · **ein** Liniengenerator (`polyPath`); die reinen Funktionen in `lib/process-graph.ts` (Wächter `scripts/process-graph.test.mjs`) |
| `capture-work.tsx`, `capture-form.tsx`, `photo-capture.tsx`, `signature-pad.tsx` | Ausführung von Datenerfassung, Aussondern, Verbrauch, Bewegen |
| `beleg-work.tsx`, `beleg/`, `pay-online.tsx` | Modul «Zahlung»: der Einstieg (gemeinsamer Zustand, Vorschau → Freigeben) · die Abschnitte (`stages`, `parties`, `goods`, `terms`, `quotes`, `invoice`, `documents`, `footer`, `shared`, `forms`, `paper-sheet`) · die eigene Bezahlkarte |
| `documents.tsx`, `document-detail.tsx`, `document-draft.tsx`, `document-field.tsx`, `compose-chat.tsx`, `legal-texts.tsx` | **Dokumente** (`docs/dokumente.md`): Kacheln unten an jedem Datensatz · die Seite eines Dokuments (Senden, Löschen) · **der eine Entwurf** (Scannen · Datei · Verfassen, auch als `DraftSheet` über einem Modul) · ein Pflichtfeld mit Dokument · Verfassen im Chat · AGB/Datenschutz der Gesellschaft |
| `payment-list.tsx` | **Zahlungen** einer Person (Abschnitt) oder eigenen Gesellschaft (Reiter) – eine Liste, Zeile öffnet den Auftrag |
| `step-record.tsx` | Modul-Protokoll (eine Komponente für alle Modultypen) |
| `stock-view.tsx`, `stock-bar.tsx`, `unit-number(s).tsx` | Bestand (Artikel- und Instanz-Umfang) · Leiste · Stücknummern |
| `place-trail.tsx`, `obj-id.tsx` | Ortskette eines Stücks · Objektnummer als Kennung (`.erp-objid`) |
| `time/` | **Zeiterfassung**: `time-card` (die Karte im Personendatensatz), `time-swipe` (Kommen ↔ Gehen), `time-calendar` (Monat, abgeschlossene Tage blass), `time-day` (Tag + «Erfassen», Vorschau vom Server), `time-contracts` (Verträge, Buchungen), `company-time` (Feiertage, Absenzarten, Regeln an der Gesellschaft), `time-ui` (Formate in Minuten, Symbole – getippt gegen `TimeIconName`) |
| `territory-map.tsx`, `world-map.tsx` | Gebietskarte |
| `detail-tabs.tsx`, `error-boundary.tsx` | Hilfen |

## Design System (VERBINDLICH)
Alle UI baut auf dem Inexxio Design System – Regeln: **`../docs/design-system/README.md`**,
Skill `inexxio-design-system`.
- **Tokens** nur in `src/styles/design-system/colors_and_type.css` (erstes CSS-Modul in
  `app/layout.tsx`). Tailwind-Utilities daraus (`bg-bg-1/2/3`, `text-fg-1…4`, `text-accent`,
  `text-inexxio`, `border-border-1/2`, `rounded-ds-lg`, `shadow-ds-sm/md`, `font-display`),
  Zahlen `.ix-tnum`.
- **Farbe = Bedeutung**: kühle, neutrale Grautöne (v4) = Fläche · Rot (`inexxio`) = der eine laute Akzent
  · Slate (`accent`) = Info/aktiv/Links im ERP.
- **ERP**: Haarlinien + Weissraum statt Schatten; Status = Punkt + Wort (`fields.StatusDot`); ein Eingabefeld hat EINE Form (`controls.inputClass`); Lucide-Symbole;
  8-px-Raster. Eine Detail-Ansicht hat **eine** Breite (`detail-frame.DETAIL_MAXW` über
  `DetailBody`); eine Kürzungsgrenze an einer Zeile ist etwas anderes.
- **Alt-Palette: 0 Vorkommen** (`slate-*`, `blue-*`, `gray-*`, `brand-*`, `#2563eb`, auch
  als Hex – Ausnahme Gebietskarte).
- **Eine unbekannte Tailwind-Klasse oder CSS-Variable erzeugt still nichts** (`bg-dark` gibt
  es nicht, `bg-bg-dark` schon; `var(--x)` ohne Rückfall muss definiert sein – ein Wächter
  prüft es). Nach einer Farbänderung hinsehen, nicht nur bauen.
- **Scrollbalken sind unsichtbar** (`*`-Regel in `globals.css`); seitwärts scrollen ist
  verboten.

## Typen und generierte Quellen
- `src/types/api.ts` – aus `backend/openapi.json` (`npm run generate:types`). Gelesen wird er
  über die Aliase in `src/types/index.ts` (z. B. `CompanySettings` =
  `CompanySettingsResponse`, `CompanySettingsUpdate`, `PublicDocument`, `Deal`) – kein
  `components['schemas'][…]` an der Aufrufstelle, kein handgeschriebener Typ oder Mapper
  daneben: das Frontend spricht die Feldnamen des Backends (`street_nr`, `zip_code`,
  `uid_number`). `lib/api.ts` liest `paths` direkt (siehe «API-Client»); ein Alias, den niemand
  mehr liest, fällt weg.
- `src/lib/status-catalog.ts` – aus `backend/app/domain/statuses.py`
  (`python -m scripts.dump_statuses`). Eine **Quelle, kein Spiegel**: Beschriftung,
  Ampelton, Achsen, Bestand/Historie, Endgültigkeit kommen von dort. `lib/process-status.ts`
  trägt nur das **Symbol** und `isPickable`.
- `src/lib/vocab.ts` – Schlüssel und Wörter aus `backend/app/domain/…`
  (`python -m scripts.dump_vocab`): Instanz-Arten, Modulschlüssel und Farbfamilien,
  Erfassungstypen, `CapturePoint`, Aussondern-Modi, Geld-Richtungen/-Stufen/-Vorgaben,
  Eigentum, Incoterms, Angebotszustände, Versandarten, Kanal-Arten, Symbole der Zeiterfassung,
  Takte der Wiederholung, `DRAFT_OBJECT_ID`, Rollen (`ROLES`, `STAFF_ROLES` – gelesen von `isStaff`). **Keine Spiegel von Hand**: was die Oberfläche
  selbst hält (Symbol, Farbwert, Hover-Satz), ist gegen die Schlüssel getippt
  (`MODULE_ICON: Record<ModuleKey, LucideIcon>`, `MODULE_FORM`, `MODULE_FIELDS`,
  `MODULE_TONE`, `CAPTURE_ICON`, `KIND_LABEL`, `TIME_ICONS`, …) – ein neuer oder entfernter
  Schlüssel ist ein Typfehler. Gelesen wird mit einem Schlüssel von aussen über
  `vocab.lookup(table, key)` (unbekannt → `undefined`, nie ein Prototyp-Eintrag).
- **Quelltext-Wächter** in Node lesen den Syntaxbaum über `scripts/lib/source.mjs` (`files`,
  `parse`, `walk`/`find`, `calls`, `jsx`, `imports`, `exports`, `strings`, `stripComments`);
  was kein Typ prüfen kann, steht so (`scripts/vocab-use.test.mjs`: Modulfarben nur in
  `lib/modules`, Beleg-Stufen nur über `VOUCHER_STAGE`). **Kein Backend-Test liest den Quelltext
  der Oberfläche** (Wächter `backend/tests/test_tests_read_behaviour.py`; Urteile je alter Test:
  `docs/history/2026-11-09-tests-neu.md`); jeder Aufruf in `lib/api.ts` muss eine Backend-Route
  treffen (Compiler über `paths`, dazu `test_api_routes.py`).

## Datenfluss (`lib/feed.ts`, `lib/use-feed.ts`, `lib/queries.ts`, `lib/use-feed-lists.ts`)
- **Ein `QueryClient` im ERP-Layout** (`app/(erp)/layout.tsx` → `useFeedClient`), dieselbe Bauart
  im Konto (`lib/use-feed.newQueryClient`: Fehler über `tell`, kein zweiter Wiederholungsweg). Was
  das ERP vom Server liest, ist eine Query – **die einzige Datenquelle**; ein `api.…` in einem
  `useEffect` gibt es nur für Handlungen, öffentliche Seiten und die Anmeldung, je mit Grund
  (Wächter `scripts/queries.test.mjs`, für das ganze Frontend).
- **Feed** (`app/(erp)/erp/page.tsx` → `lib/use-feed-lists.ts`): `['feed', 'people' |
  'articles' | 'orders' | 'companies' | 'todo']`, mit der Suche `['feed', 'instances', q]`
  (seitenweise, `useInfiniteQuery`, 100 je Seite) und `['feed', 'documents', q]`; dazu
  `['me']`. Firmen, Dokumente und Aufgaben (`GET /erp/tasks`, Schlüssel `todo`; `mine` = meine eine Aufgabe, zuoberst im Feed) fragen erst, wenn die Rolle feststeht. Die Suche ist
  entprellt (300 ms) und Teil des Schlüssels.
- **Detailansichten**: Schlüssel aus `lib/queries.qk` (`[<Bereich>, …]`, Bereiche in
  `feed.DETAILS`): Auftrag, Instanz, Dokument, Artikel (Umfeld), Erzeugungsprozess, Bestand
  und Nummern (`useInfiniteQuery`), Dokumente an einem Datensatz (`useDocumentsOf`),
  Zahlungen, Verlauf (`qk.history`, `useInfiniteQuery` – jeder Schreibvorgang lädt ihn nach), Absender, Postfach, Newsletter, Gesellschaft,
  Zeiterfassung (`qk.time` · `qk.companyTime`), Protokoll · Überweisung · korrigierbare Rechnungen
  (unter dem Auftrag: `qk.stepRecord` · `transfer` · `correctable`), Seltenes (`qk.catalog`: Modul-Katalog, Ort, Artikel);
  **Phase 4/5** `qk.openRecordings` · `qk.openTalks` · `qk.talk` · `qk.pins` (`lib/assistant.ts`; `feed.LOGGED` =
  Verlauf + «Auf einen Blick» lädt jede Änderung am Datensatz nach – offen ist abgeleitet; ein
  übernommener Vorschlag lädt **alles** nach, er kann alles, was das ERP kann). Die Antwort einer Handlung
  geht per `setQueryData` in den Cache. **Prüfen und Vorschau** (Auftrag, Artikel,
  Zeiterfassung) über `useDebouncedQuery`: Eingabe 250 ms entprellt und Teil des Schlüssels,
  `keepPreviousData`, überholte Anfragen brechen ab (die Methoden von `api` nehmen `{ signal }`).
- **Invalidiert wird an EINER Stelle**: `lib/api.ts` meldet jede erfolgreiche Anfrage, die
  kein GET ist, mit ihrem Pfad (`DATA_CHANGED`); `useFeedClient` invalidiert die Bereiche aus
  `touchedBy(path)` – Listen des Feeds **und** Detailansichten (Tabelle `TOUCHES` in
  `lib/feed.ts`, erster Treffer gilt, `*` = ein Pfadteil; **unbekannt → alle**,
  Prüfen/Lesen/leerer Abgleich/ein Stück einer Aufnahme → keine). Neue Nachrichten (`MESSAGES_CHANGED`) laden «zu tun», Personen und den Verlauf,
  `TODO_CHANGED` «zu tun». Wächter: `scripts/feed.test.mjs`.
- **Query-Daten treiben nie ein Formular**: ein Formular mit Auto-Save (Person,
  Gesellschaft, Konto) wird einmal befüllt; ein anderer Datensatz ist ein neues Bauteil
  (`key`). Was am Server gleich bleibt, behält seine Identität (`structuralSharing`) – darum
  setzt ein Nachladen keinen Entwurf zurück (Beleg: Positionen, Angebote).
- **Veraltet nach 60 s**: kehrt man nach einer Pause zurück, lädt eine Query einmal nach –
  kein Polling. Kein eigener Wiederholungsweg (`retry: false`, `lib/api.ts` wiederholt
  selbst; ein Abbruch wird nicht wiederholt).
- **Nichts scheitert still**: jede Query trägt `meta.what`, der `QueryCache` meldet ihren
  Fehler über `tell()` («Nicht geladen: Aufträge – …»); der alte Stand bleibt stehen.

## API-Client (`lib/api.ts`)
**Getippt aus dem Backend**: jede Methode (`api.getCompany(id)`) ist eine Zeile über **eine**
Anfrage `call(method, '/api/v1/admin/companies/{object_id}', { path, query, body }, { signal })`;
Pfad (mit den Namen des Backends), Methode, Pfad-Parameter, Query, JSON-Rumpf und Antwort kommen
aus `paths` in `src/types/api.ts` – ein Pfad oder eine Methode, die es nicht gibt, ein falsches
Feld im Rumpf, ein fehlender Pflicht-Parameter ist ein **Typfehler**. Rückgabetypen werden nicht
von Hand geschrieben; Parameter, die den Rumpf durchreichen, heissen `In<'post', '<pfad>'>`.
`fill` setzt die Parameter ein (kodiert) und baut die Query (leere Werte fallen weg, eine Liste
wiederholt den Schlüssel). Verengt wird an EINER Stelle (`Narrowed`): Rolle der Person, Status/
Einheit/Serialisierung des Artikels (`UserProfile`, `Article` aus `types/index.ts`). **Von Hand**
bleibt nur, was kein JSON ist, je mit Pfad als `Route<…>` und Antwort als `Res<…>`: Dateien
(`upload` – multipart; `uploadAttachment` einmal versucht, ohne Wiederholung), Blobs
(`messageAttachment`, `attachmentBlob`), der NDJSON-Stream `say` (Rumpf getippt), die Optionen der
Passkeys (Backend sagt nur «Objekt») und `getMapsKey` (Route ohne Antwortform). Der Wächter
`backend/tests/test_api_routes.py` prüft jedes Paar Methode + Pfad zusätzlich gegen die
registrierten Routen und weist einen `/api/v1/`-Pfad ab, der an den Typen vorbei gebaut wird.
Fetch-Wrapper mit Bearer-Token (Firebase). **Den Token setzt niemand**: `request()` fragt
ihn je Anfrage beim Provider, den `lib/firebase.ts` registriert (Firebase hält ihn vor und
erneuert ihn selbst; nach einem 401 einmal erzwungen frisch); ohne Anmeldung geht die
Anfrage ohne Token. **`getMe()` teilt eine Antwort** (laufend oder höchstens 10 s alt) – jede
schreibende Anfrage, `logout()` und ein Wechsel der Person verwerfen sie (`forgetMe`).
**`ApiClient` bindet alle Methoden im
Konstruktor über den Prototyp** – eine als Wert weitergereichte Methode
(`search={api.searchPeople}`) behält ihr `this`. Die Personensuche heisst `searchPeople`
(`GET /erp/people`), die Firmensuche `searchCompanies`. Auth-Schutz: `/erp` und `/konto`
prüfen die Anmeldung in ihren Layouts über **ein** Bauteil, `components/auth/auth-gate.tsx`
(Redirect auf `/login?from=…`; `staffOnly` am ERP schickt Nicht-Personal ins Konto), das
Backend prüft jede Anfrage. Personal ist **nur** `isStaff(role)`, Admin nur `isAdmin(role)`
(`lib/record-status.ts`, liest `STAFF_ROLES` aus `lib/vocab`, generiert aus `domain/policy`; ESLint verbietet Rollenvergleiche daneben) –
ob man etwas **darf**, sagt der Server (`can`, `may_edit`). Ein Fehler ist ein `ApiError`
(`message` = Satz des Servers, `code` = Art oder eigener Code wie `pick_stale`, `field`).

## Regeln, die jede Oberfläche erbt
- **Ein Dialog verhält sich überall gleich** (`lib/use-dialog.ts`, `useDialog(onClose, {focus})`):
  Fokus hinein und zurück, Escape schliesst **den obersten** (liegt der Scanner über dem Entwurf,
  nur den Scanner), Tab bleibt im Dialog; das Aussehen bleibt beim Dialog (Anmelden, Scannen,
  Dokumentscanner, «+», Passkey-Hinweis, `controls.Dialog`, das Blatt `document-draft.Sheet` für
  Entwurf und Papier-Vorschau). Eine Liste in einem Dialog (`SearchSelect`) fängt ihr Escape selbst.
  Wächter `scripts/dialog.test.mjs`.
- **Ein Klick daneben schliesst – über `lib/use-outside.ts`** (`useOutside(open, close, [refs],
  ignore?)`, `pointerdown`): jedes Aufklapp-Menü und jede Liste; kein eigener Lauscher am
  Dokument (Wächter `scripts/hints.test.mjs`, Ausnahme die Stecknadel).
- **Eine Hover-Blase** (`components/erp/hints.tsx`): wer etwas erklärt, setzt `data-tip="…"`
  (oder `Tooltip`/`InfoHint`); gezeigt wird sie von `TipHost` im Wurzel-Layout – **am `body`**,
  aus dem Rechteck des Auslösers, kippt am Fensterrand, erbt nichts (keine Grossschreibung einer
  Überschrift), Satzschreibung wie geschrieben; die innere gewinnt; `data-tip-pos`
  (`bottom|left|right`), `data-tip-list` (Zeilen), `data-tip-hidden`. **Kein natives `title=`**
  (ausser `iframe`: dort ist es der Name), kein `role="tooltip"`, kein `content: attr(…)` daneben
  – Wächter `scripts/hints.test.mjs`. `.ix-tuck` (Name klappt am Symbol aus) und `.ix-seg-label`
  sind kein Hinweis, sondern der Name des Knopfs – auch sie in Satzschreibung.
- **Leer ist `NOTHING`** (`lib/when.ts`, «—») – kein Strich als Literal (Wächter
  `scripts/hints.test.mjs`); `formatAmount` und `day`/`when` geben ihn selbst.
- **Im ERP wird gespeichert, nicht abgeschickt**: `lib/use-autosave.ts`
  (`useAutosaveValue` für einen Wert, `useAutosaveSignature` für einen Satz Werte; debounced
  `AUTOSAVE_DELAY` = 3 s, Enter sofort, Rückmeldung im Karten-Kopf). Kein Speichern-Knopf.
  **Eine Logik für beide** (`lib/saver.ts`): beim Verlassen und beim Wechsel des Datensatzes
  geht der offene Stand sofort an den Datensatz, für den er getippt wurde; gespeichert wird
  hintereinander, nie überholt ein älterer PATCH einen neueren; ein Fehler meldet sich über
  `tell()`. Wächter: `scripts/autosave.test.mjs` (in echtem React).
- **`busy` sperrt Handlungen, nie Geometrie und nie Werte**: kein `disabled={busy}` an einem
  Eingabefeld, nichts verschwindet während eines Auto-Saves; was erst mit der Serverantwort
  entsteht, hat seinen Platz von Anfang an.
- **Ein Feld = der Feld-Baustein** (`components/form/use-field.ts` + `field.tsx`): die Logik
  steht EINMAL in `useField` (Wert, Pflicht, weiche Format-Prüfung, Meldung, Enter = fertig;
  was die KI an einem Feld ändern will, ist ein Vorschlag «Auf einen Blick» – das Feld trägt kein
  Zeichen); `Field` · `SelectField`
  sind die Standardform, `Input` · `Select` · `TextArea` dieselbe Logik in freiem Aussehen (Beleg,
  Konto, Prozess-Editor). Ein loses `<input>`/`<select>`/`<textarea>` unter
  `components/{erp,account,beleg}` weist ESLint ab (`RAW_FIELD`); die Ausnahmen (Suchfelder,
  Nachrichten-Eingabe, Kästchen, Dateiwahl) stehen dort mit Grund.
- **Eine Handlung am Server = `useAction`** (`lib/use-action.ts`): `useAction(fallback?)`,
  `run(fn, onError?)` setzt `busy`, leert den Fehler, gibt das Ergebnis zurück oder den Satz des
  Servers in `error` (`onError` darf ihn ersetzen, z. B. «ohne Netz»); der Fehlertext steht EINMAL
  in `errorText(e, fallback?)`. Ein eigenes `[busy, setBusy]` um einen `api.…`-Aufruf weist
  `scripts/action.test.mjs` ab (Ausnahmen mit Grund dort). (Ausnahme: Module, die ein Test einzeln
  übersetzt – `use-autosave`, `use-recorder` – können keine Nachbarn importieren.)
- **Kein Netz ist eine eigene Art Fehler**: `lib/api.ts` wirft dann `ApiError` mit `code:
  'offline'` (Status 0) – gefragt wird `e.code === 'offline'`, nie der Wortlaut.
- **Ein gescheiterter Abruf ist nie stumm** (`lib/notice.ts`): wer bei einem Fehler nichts
  anderes zu tun hat, schreibt `.catch(tell('Aufträge'))` – unten rechts steht dann «Nicht
  geladen: Aufträge – <Grund>» (`components/layout/notice-host.tsx`, im Wurzel-Layout),
  dieselbe Meldung einmal je fünf Minuten; was stehen bleiben muss, trägt `sticky` (eine
  Nachricht, die nicht gespeichert wurde), eine Auskunft `tone: 'info'` – es gibt EINE
  Meldezeile. Verboten sind alle Formen des Schweigens (`.catch(() => {} | [] | null |
  false | undefined)`, `set…([] | null)` im catch, leeres `catch {}`) – `scripts/notice.test.mjs`
  mit einer Liste begründeter Ausnahmen. Eine Frage nach einer Nummer trennt 404 vom Ausfall
  (`api.absentOn404`).
- **Datum nur über `lib/when.ts`**: `when()` = Auskunft («vor 3 Tagen», «gerade eben»),
  `day()` = Tag auf dem Papier (Beleg), `formatWhen()` gibt beides (Hover), `happened()`
  setzt Zeit + Zustandswort. Die Wörter stehen im Modul, nicht im ICU. Wächter:
  `scripts/when.test.mjs`.
- **Beträge** über `module-ui.Amount` (Währung als Kind der Zahl, gleiche Farbe, Stellenzahl
  der Währung, Vorzeichen über `sign`).
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
| `ActionButton` | Ein Knopf ist ein Symbol, beim Zeigen klappt der Name daneben auf (`.ix-tuck`) – in einer eigenen, nicht umbrechenden Zeile (`.ix-actions`). |
| `StageAction` | Die Handlung, die eine Sache weiterbringt (volle Breite, 42 px) – Beleg und Zeiterfassung. |
| `LedgerRow` · `RowActions` | Zeilen-Grammatik `[Identifikator] [Meta] … [Aktion] [Datum] [Betrag]`, strikt einreihig; Zeilenaktionen am Ende, im Ruhezustand unsichtbar, auf Touch dauerhaft – und **in einer Zeile klappt kein Name aus** (Blase statt `.ix-tuck`). |
| `Amount` | EIN Betrag – Zahl, Vorzeichen, Währung, Zustandsfarbe; leer `NOTHING`. |
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
(eingefroren, Link auf `/dokument?t=…`) – und unten **eine graue Leiste** (`footer.tsx`).
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
- `/agb` zeigt das A4-Dokument vom Server (`api.publicLegal('agb')`; ebenso `/datenschutz`, `/impressum`).
- API: `updateVoucher` · `previewVoucher` · `prepareVoucherPayment` · `voucherTransfer` ·
  `refundVoucherPayment` · `paymentsOf`. Vorgaben des Moduls im Editor:
  `MONEY_FORM` in `lib/modules.ts` (Schlüssel und Wörter aus `lib/vocab`).
- **Die eine Seite nach aussen** (`app/(public)/dokument`, `components/beleg/document-page.tsx`):
  jedes Dokument über seinen Link – das Papier (A4-HTML in einem `iframe srcdoc`, PDF, Bild),
  Unterschreiben (dieselbe Fläche wie `signature-pad.tsx`, `onSigned`) oder Ablehnen; ist es ein
  Papier eines Belegs (`view.deal`), darüber die Stationen und die Handlungen der Partei
  (`components/beleg/deal.tsx`; `api.agreeDocument` · `rejectDocument` ·
  `prepareDocumentPayment`); gelöscht → ein Satz (410).
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
Ein Ziel gilt nur, wenn es – so aufgelöst, wie der Browser es auflöst (`new URL`) – auf
derselben Herkunft bleibt (`isSafeTarget`, auch für «daneben klicken»). Die Rückkehr vom
Magic Link (`/login/verify`) ist dieselbe Lightbox (`.ix-login-scrim` + `.ix-login-card`).
Zentriert über `margin: auto` an der Karte. Wächter: `scripts/login-target.test.mjs`; jede
`ix-`-Klasse im Markup hat einen Stil (`scripts/design.test.mjs`).

## Konventionen
- `'use client'` nur, wo nötig. Lucide React für alle Icons. TypeScript strict, kein `any`.
- **`@typescript-eslint/no-unused-vars` ist scharf** (`eslint.config.mjs`, CI; kennt auch
  ungenutzte Typen; `scripts/house.test.mjs` prüft an Beispielen, dass ESLint abweist) – ein ungenutzter Zustand
  ist die Form, in der ein Knopf ohne Wirkung auftritt. Von den Hook-Regeln gelten die beiden
  von vorher (`rules-of-hooks`, `exhaustive-deps`); die Compiler-Regeln von
  `eslint-plugin-react-hooks` 7 sind aus, weil das Projekt den React Compiler nicht einsetzt. Ein `export`, den keine andere Datei liest, gibt es nicht
  (`backend/scripts/deadcode.py --frontend`; was bleibt, liest ein Wächter oder Test).
- Einsprachig Deutsch (kein i18n verdrahtet).
- **Eine Abhängigkeit ohne Import ist Altlast** – auf Unterpfade und dynamische Importe
  achten (`await import('@zxing/browser')` ist echte Nutzung).
- Rechtliches: AGB, Datenschutz und Impressum hier (`/agb`, `/datenschutz`, `/impressum`, eine
  Komponente `components/beleg/legal-page.tsx`, Text vom Server `api.publicLegal`). Keine
  Statistik, kein Cookie-Dialog.

## Aufnehmen (Phase 4, `docs/konzept/phase4-bauplan.md`)
- **Logik ohne Browser** in `lib/recorder.ts`: Stück alle 30 s (`MediaRecorder.start(30000)`),
  Abschnitt = 5 min (neuer Recorder am selben Mikrofon, Stück-Zählung ab 0), höchstens 3 h;
  Warteschlange der Reihe nach – **ein Stück wird nie aufgegeben, solange die Seite lebt**:
  Pausen 1 · 2 · 4 · 8 · 16 s, dann 30 s ohne Ende, jeder Versuch mit Zeitgrenze 30 s
  (`AbortController`); aufgegeben nur bei 4xx ausser 408/429 (→ `tell`; 409 = die Aufnahme ist
  schon abgeschlossen → sofort beenden, klarer Satz). Solange ein Stück wartet, steht ruhig
  «wartet auf Netz» (eine Meldung beim ersten Hängen). Stopp = auf das `stop`-Ereignis jedes
  Recorders warten (Sicherheitsgrenze 60 s), Mikrofon zu, Warteschlange leeren,
  `POST …/stop {segments}`; **30 s Stille** (`silence`: Pegel unter `VOICE_LEVEL`) halten von selbst an
  wie «Stopp». Die Laufzeit «mm:ss» / «h:mm:ss» steht EINMAL dort (`runtime` –
  eine Dauer, kein Datum).
- **Anschluss** `lib/use-recorder.ts`: Mono, Opus/WebM → MP4 → Vorgabe, 24 kbit/s; Pegel
  (`AnalyserNode`, 10 × je s); Wake Lock (beim Zurückkehren neu, verweigert = fehlt);
  `beforeunload`, solange Mikrofon offen oder Stücke unterwegs; `pagehide`/unsichtbar →
  `requestData` (das Letzte geht sofort hoch). **Fällt das Mikrofon aus** (`MediaRecorder.onerror`,
  Spur `ended`, länger als 5 s `mute`): einmal «Mikrofon getrennt – Aufnahme beendet», dann
  sauber beenden. Wird das Bauteil entfernt, hält die Aufnahme an wie mit «Stopp» (abgeschrieben
  im Takt). Spuren, `AudioContext` und Wake Lock werden in jedem Fall freigegeben.
- `Recording` kommt generiert aus `src/types/api.ts` (Alias in `src/types/index.ts`).
