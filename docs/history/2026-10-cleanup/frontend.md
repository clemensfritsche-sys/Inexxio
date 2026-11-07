# Cleanup-Analyse Frontend – INEXXIO (develop, fbd70fc)

Umfang: `frontend/src` (ohne generiertes `types/api.ts`), `frontend/scripts` (ohne Tests),
`globals.css`, `tailwind.config.js`. Nur gelesen, nichts geändert.

Werkzeuge: `python -m scripts.deadcode` (Frontend-Teil lief), jede Fundstelle per `grep -rnw`
gegengeprüft; eigene Wegwerf-Skripte im Scratchpad (TypeScript-AST für Funktionslängen und
ungenutzte destrukturierte Props, Abgleich `lib/api.ts` ↔ `app.routes` aus `app.main`,
Abgleich CSS-Klassen ↔ TSX, `var(--x)` ↔ Definitionen, Kommentaranteil je Datei).

Grundmasse: 27 337 Zeilen (ohne `types/api.ts`), davon **8 706 Kommentarzeilen (32 %)**,
311 «►►►»-Marker, ~596 Verweise auf Testnotiz-Nummern, 54 «Hier stand …/ist entfallen»-Grabsteine.
`any`: 0 · `@ts-ignore`: 0 · `fetch(` ausserhalb `lib/api.ts`: 0 · undefinierte CSS-Variablen: 1
(`--site-header-h`, kommt aus dem Website-Shell-Stylesheet – bleibt).

---

## Kurzfassung – die 10 wichtigsten Befunde

1. **Die Alt-Palette lebt als Hex weiter** (F-20): `#0F172A`, `#E2E8F0`, `#94a3b8`, `#64748b`,
   `#F1F5F9`, `#374151`, `#f59e0b`, `#16a34a`, `#dc2626` … (Tailwind slate/gray/amber/green)
   in Konto (`account-shell`, `account/field`, `security-section`, `save-status`) **und** in
   ERP-Formularen, weil `account/field.tsx` dort importiert wird. Die «0 Vorkommen»-Aussage
   gilt nur für Klassennamen. Grösster sichtbarer Gewinn, eine zweite Farbsprache.
2. **`lib/modules.ts` heisst das Zahlungsmodul noch «deal»** (F-30): `DEAL_DIRECTION`,
   `DEAL_PARTY`, `DEAL_STAGE`, `DEAL_TASK*`, `DEAL_ORDER_REF*`, `dealDirection`, dazu
   vier Kommentare «gespiegelt von `domain/deal`» – die Datei gibt es nicht mehr, Quelle ist
   `domain/voucher`. Wer den Spiegel sucht, sucht an der falschen Stelle.
3. **Toter Code mit eindeutigem Befund** (F-01…F-12): `lib/optimistic.ts` (ganze Datei),
   API-Methoden `deleteStep` (Endpunkt existiert **nicht** mehr), `updateArticle`,
   `getUsers`, `getPublicContact`, `clearToken`; `TILE`, `ChoiceButton`, `MODULE_GRID`,
   `PARTY_NUMBER_LABEL`, `StatusAction`, `ConsentCategory`, Ton `rose`; 13 Typ-Aliase in
   `types/index.ts` ohne Leser; prop `side` in `Recipients`.
4. **11 tote CSS-Klassen in `globals.css`** (F-13): `.btn-secondary`, `.form-input`,
   `.erp-tile`, `.erp-tile-link`, `.erp-orow`, `.erp-chip`, `.erp-palette`, `.ix-truck`,
   `.ix-road` (+ 2 Keyframes), `.ix-flow-aside` – rund 60 Zeilen inkl. Prosa.
5. **Zwei `useAutosave`-Hooks gleichen Namens, verschiedene Signatur und Vorgabe**
   (F-40): `components/account/use-autosave.ts` (Wert-basiert, 3000 ms, Status) und
   `lib/use-autosave.ts` (Signatur-basiert, 1500 ms, nur `flush`); dazu 2500 ms in
   `organization-detail`. Hausregel sagt «3 s».
6. **Doppelte Bausteine** (F-41…F-45): `Card` (profile-section ≈ `fields.Card`, obwohl der
   Kommentar in `fields.tsx` behauptet, beide nutzten ihn), `SubBlock` 2× wortgleich
   (profile-section, user-detail), 7 Varianten des Mikro-Labels statt `MICRO_LABEL`,
   `FieldLabel`/`EditField` in article-detail neben `fields.Label`, drei Chip-Bauteile,
   `isStaff` 2× inline nachgebaut, Markenrot in drei Schreibweisen (`#E51A14` 17×,
   `--ix-red`-Alias, `--inexxio-red`).
7. **Verschluckter Fehler beim Versand einer Nachricht** (F-60): verlässt man die Ansicht
   während «Rückgängig», geht die Nachricht in einem Unmount-Effekt mit
   `.catch(() => {})` hinaus – scheitert sie, ist sie weg, ohne Spur (communication.tsx:842).
   Dazu ~20 weitere `.catch(() => {})` im ERP-Feed (Feed bleibt still leer statt Meldung).
8. **Personenname: drei Regeln** (F-61): `userDisplayName` hat einen toten Firmen-Zweig
   (`company_name` gibt es am Benutzer nicht mehr), kürzt auf den E-Mail-Präfix (Backend:
   ganze E-Mail), und `userName` vergleicht deshalb `n !== u.email` ins Leere; Docblock und
   Inline-Kommentar widersprechen sich in der Reihenfolge.
9. **Irreführende Texte für den Nutzer** (F-62): Platzhalter «Sicherheitsbestand – darunter
   wird **automatisch nachbestellt**» – es gibt keinen Leser von `safety_stock` im Backend.
10. **Kommentare, die Gelöschtes als aktuell beschreiben** (F-70…F-85): `recovery.auto_resolve`
    + `POST …/cover`, `services/metrics.py`, `voucher._assert_complete`,
    `people.assert_company`, `purchase.can`, `deal.can`, `deal.record_payment`,
    `Zahlung.clean_config`, KI-Live-Refresh/KI-Navigation, «zwei Stufen», «Forderung
    (`charge`)», «keine Reaktivierung», verwaiste JSDoc-Blöcke in `api.ts`, `modules.ts`,
    `beleg-work.tsx`, `article-detail.tsx`. Dazu der Gesamtbefund: 32 % Kommentar, in
    `modules.ts` 62 %, `module-ui.tsx` 59 % – grösstenteils Änderungshistorie.

---

## Befundtabelle

Spalten: Risiko = Risiko der Änderung (niedrig/mittel/hoch) · VÄ = Verhaltensänderung.

### Achse 1 – Tot

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | VÄ | wie geprüft |
|---|---|---|---|---|---|---|---|
| F-01 | tot | `lib/optimistic.ts:5` | Ganze Datei (`isVersionConflict`) ohne Importeur. | entfernen | niedrig | nein | deadcode «nicht erreichbar» + `grep -rn optimistic src` → nur die Datei selbst |
| F-02 | tot | `lib/api.ts:598` | `deleteStep` ohne Aufrufer **und** ohne Backend-Pfad (`DELETE /erp/{owner}/{id}/steps/{step}` existiert nicht). | entfernen | niedrig | nein | `grep -rnw deleteStep` → nur Definition; Routenliste aus `app.main` |
| F-03 | tot | `lib/api.ts:587` | `updateArticle` ohne Aufrufer (Artikel ist nach Freigabe read-only, Entwurf lebt im Browser); mit ihm wird `ArticleUpdateInput` (`types/index.ts:77`) tot. | entfernen (Backend-Agent: `PATCH /erp/articles/{id}` hat keinen Frontend-Leser) | niedrig | nein | `grep -rnw updateArticle\|ArticleUpdateInput` |
| F-04 | tot | `lib/api.ts:343` | `getUsers` (`/admin/users`) ohne Aufrufer; der Feed nutzt `getErpRecords`. | entfernen | niedrig | nein | `grep -rnw getUsers` |
| F-05 | tot | `lib/api.ts:267` | `getPublicContact` ohne Aufrufer (die Website holt den Kontakt selbst, `website/src/scripts/contact.ts`). | entfernen; Typ `PublicContact` prüfen | niedrig | nein | `grep -rnw getPublicContact src ../website/src` |
| F-06 | tot | `lib/api.ts:141` | `clearToken` ohne Aufrufer. | entfernen (oder in `logout()` nutzen – zu prüfen, ob dort der Token bleibt) | niedrig | nein | `grep -rnw clearToken` |
| F-07 | tot | `components/erp/fields.tsx:41`, `:711` | `TILE` und `ChoiceButton` (40 Zeilen) – nur Deklaration. | entfernen | niedrig | nein | deadcode + `grep -cw` = 1 in eigener Datei, 0 sonst, 0 in Tests |
| F-08 | tot | `components/erp/module-ui.tsx:521` | `MODULE_GRID` nur Deklaration. | entfernen | niedrig | nein | wie F-07 |
| F-09 | tot | `lib/modules.ts:131` | `PARTY_NUMBER_LABEL = 'Nr.'` ohne Leser (Kommentar verweist auf `domain/deal`); ein Wächter verlangt sogar, dass es in beleg-work fehlt. | entfernen | niedrig | nein | `grep -rnw PARTY_NUMBER_LABEL` + `test_frontend_mirrors.py:7430` |
| F-10 | tot | `lib/modules.ts:246` | Farbfamilie `rose` ohne Verwender (Zahlung trägt `plum`; Backend nennt slate/clay/moss/plum/sand). | entfernen (Wächter prüft nur `⊆`) | niedrig | nein | `grep -rn "rose"` + `domain/modules.py:742–783` |
| F-11 | tot | `lib/status-flow.ts:18`, `lib/consent.ts:13`, `types/index.ts:132` | `StatusAction`, `ConsentCategory`, `ArticleProcessStep` nur deklariert. | entfernen | niedrig | nein | deadcode + `grep -cw` = 1 |
| F-12 | tot | `types/index.ts` (div.) | 13 Typ-Aliase ohne Leser: `RetiredInput`, `TerritoryRegion/Company/Country`, `OrderUnitResponse`, `OrderLineResponse`, `PaymentBilling`, `ModuleTypeInfo`, `VoucherStage`, `VoucherEntryOut`, `VoucherLineOut`, `VoucherInvoice`, `VoucherCorrects` – samt teils veralteter Docblöcke (s. F-77). | entfernen (oder bewusst behalten, wenn als «Lesehilfe» gewollt) | niedrig | nein | Schleife über `export type` in index.ts, `grep -rlw` ausserhalb index/api = 0 (deadcode meldet sie nicht – falsch-negativ) |
| F-13 | tot | `app/globals.css:420–441, 563–573, 769–778, 826–856` | 11 Klassen ohne Verwender: `.btn-secondary`, `.form-input`, `.erp-tile`, `.erp-tile-link`, `.erp-orow`, `.erp-chip`, `.erp-palette` (abgelöst durch `.ix-palette`), `.ix-truck`, `.ix-road` + `@keyframes ix-truck-bob/ix-road-flow`, `.ix-flow-aside`. | entfernen | niedrig | nein | jede Klasse aus globals.css gegen `*.ts/*.tsx` gegrept; dynamisch gebaute Namen geprüft (`erp-actbtn-${tone}` hält `-danger` am Leben → bleibt) |
| F-14 | tot | `components/erp/beleg-work.tsx:945` | Prop `side` in `Recipients` destrukturiert und übergeben (`:804`), im Rumpf nie gelesen. | entfernen | niedrig | nein | AST-Skript «destrukturierte Props ohne Referenz» – einziger Treffer im ganzen Frontend |
| F-15 | tot | `hooks/useProfileCompletion.ts:8–12` | Option `condition` in `RequiredField` – kein Eintrag nutzt sie. | vereinfachen (Option + Filter weg) | niedrig | nein | Lesen der vier `REQUIRED`-Zeilen |
| F-16 | tot | `components/account/account-shell.tsx:51–58` | `sections` per `useMemo([])` mit totem Kommentar zur Systemkonfiguration – eine Konstante. | vereinfachen (Modulkonstante) | niedrig | nein | Lesen |
| F-17 | tot | `tailwind.config.js:105–115` | `animation`/`keyframes` (`fade-in`, `slide-in-right`) ohne Verwender; ebenso `shadow-ds-red`, `tracking-tightest`, `oak`, `info`, `border-strong`. | entfernen (Animationen); Tokens bleiben (erzeugen ohne Verwender kein CSS) | niedrig | nein | `grep -rn animate-fade-in` usw. = 0 |
| F-18 | tot? | `lib/api.ts` vs. Backend | Backend-Routen ohne Frontend-Aufrufer: `GET /admin/audit-log`, `POST /auth/terms-accept` (CLAUDE.md nennt die AGB-Akzeptanz mit Zeitstempel als gebaut). | Info an Backend-Agent; **zu prüfen**, ob die AGB-Akzeptanz eine Oberfläche braucht | – | – | Routenliste ↔ `grep -rn "terms-accept\|audit-log" frontend/src website/src` |
| F-19 | Werkzeug | `backend/scripts/deadcode.py` | Meldet `src/islands/*` als unerreichbar (falsch-positiv: eigener esbuild-Einstieg `scripts/build-islands.mjs`) und übersieht Typ-Aliase in `types/index.ts` (falsch-negativ, F-12). | Einstieg `islands/feedback.tsx` ergänzen; `components['schemas']`-Aliase mitzählen (Backend-Agent) | niedrig | nein | `scripts/build-islands.mjs:1–10` |

### Achse 2 – Reste entfernter Bereiche

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | VÄ | wie geprüft |
|---|---|---|---|---|---|---|---|
| F-20 | Rest Alt-Palette | `account/account-shell.tsx` (21×), `account/field.tsx` (15×), `account/sections/security-section.tsx` (11×), `account/save-status.tsx`, `erp/fields.tsx` (5), `erp/organization-detail.tsx` (4), `erp/territory-map.tsx` (4), `erp/error-boundary.tsx`, `erp/article-detail.tsx`, `scan/object-label.tsx`, `(erp)/layout.tsx` | Tailwind-slate/gray/amber/green als Hex-Literale (`#0F172A`, `#E2E8F0`, `#94a3b8`, `#64748b`, `#F1F5F9`, `#374151`, `#f59e0b`, `#16a34a`, `#dc2626`, `#cbd5e1`, `#F8FAFC` …). Über `account/field.tsx` auch in ERP-Formularen (new-record, company-field, user-detail, organization-detail, address-book). | auf Tokens ziehen (`--fg-1…4`, `--border-1/2`, `--bg-2`, `--warning`, `--success`, `--danger`); Konto zuerst | mittel (sichtbar) | ja (Farbtöne) | `grep -rnoE "#[0-9A-Fa-f]{6}"` + Zuordnung zur Tailwind-Palette |
| F-21 | Rest deal | `lib/modules.ts:42,51–52,118,129,139,164,169,203,451,473`, `components/erp/module-ui.tsx:303`, `process-diagram.tsx:110`, `pay-online.tsx:38`, `types/index.ts:217` | Verweise auf `domain/deal.py`, `deal.can`, `deal.record_payment`, `deal.of`, `DealEmbed.*`, `deal-work.OurOffer`, `DEAL_STAGE.done` – alles gelöscht. | Verweise auf `domain/voucher` / `services/voucher` / `stripe_pay` korrigieren oder streichen | niedrig | nein | `grep -rniE "deal" src` + `ls backend/app/domain` (kein `deal.py`) |
| F-22 | Rest Beschaffen/Verkauf | `lib/modules.ts:226–246`, `components/erp/article-detail.tsx:643–647`, `order-detail.tsx:486`, `beleg-work.tsx:964`, `lib/status-flow.ts:27`, `fields.tsx:1211` | Kommentare beschreiben `plum` als «Beschaffen», `teal` als «Verkauf», `rose` als «Zahlung»; «das Beschaffen-Modul im Reiter Prozess trägt seine Lieferanten»; `purchase.can`; Ampel «Beschaffung/Verkauf/Dokument». | Kommentare auf heutigen Stand (plum = Zahlung, teal = nur Betreff-Farbe in Kommunikation) | niedrig | nein | `grep -rnE "Beschaff|purchase|Verkauf"` |
| F-23 | Rest Kontotyp | `lib/accounts.ts:1–24` | Datei heisst «accounts», trägt eine Funktion (`inheritedEmail`, ein Leser: address-book) und 20 Zeilen über den entfallenen Kontotyp/Schalter. | in `address-book.tsx` ziehen, Datei entfernen | niedrig | nein | `grep -rn "lib/accounts"` → 1 Importeur |
| F-24 | Rest Rollen/Firma | `hooks/useProfileCompletion.ts:14–23` | Kommentar sagt, Rechtsform sei Pflicht «wenn ein Name dasteht» (`people.assert_company`) – Regel und Funktion existieren nicht mehr (Firma ist Datensatz). | Kommentar kürzen | niedrig | nein | `grep -n assert_company backend/app/services/people.py` = 0 |
| F-25 | Rest iban_masked | `lib/api.ts:942,960` | `skip`-Set nennt `iban_masked` (Feld gibt es nicht mehr) – `is_own` fehlt darin dagegen. | `iban_masked` streichen; s. F-64 | niedrig | nein | `CompanySettingsResponse` in `backend/app/schemas/admin.py:123` |
| F-26 | Rest Grabsteine | 54 Stellen, u. a. `module-ui.tsx:275,398,667`, `fields.tsx:1168`, `beleg-work.tsx:1687,2416`, `lib/utils.ts:39–45`, `lib/modules.ts:136–146,459–474` | «Hier stand `ConfirmButton` / `ModuleSteps` / `TermField` / `issued_on` / `prepaid` / `localDate` …» – Erklärungen zu Code, den es nicht gibt. Freistehende Blöcke ohne Code (`module-ui.tsx:664–681`, `fields.tsx:1167–1177`, `modules.ts:136–146`). | entfernen; Historie steht in `docs/history`/Git | niedrig | nein | `grep -rnE "Hier stand|ist entfallen|stand einmal|lag einmal"` = 54 |
| F-27 | Rest Shop/Cart | – | Keine Reste (`ShoppingCart` ist das Ausgabe-Symbol). | bleibt | – | – | `grep -rnE "/shop|Cart"` |
| F-28 | Rest Antwort auf | `communication.tsx` | Kein `reply_to`/`Quote`/Zitat mehr; `reply` ist der Antwort-Zustand (legitim). | bleibt | – | – | `grep -nE "reply|Quote|answer_to"` |
| F-29 | Rest KI | `app/(erp)/erp/page.tsx:264,299–303` | «Tiefer Link … von der KI-Navigation», «KI-Live-Refresh … das Widget feuert». Heute feuert `lib/api.ts:85` das Ereignis nach jedem Nicht-GET. | Kommentare korrigieren | niedrig | nein | `grep -rn "data-changed"` |

### Achse 3 – Doppelungen

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | VÄ | wie geprüft |
|---|---|---|---|---|---|---|---|
| F-40 | Doppelung | `components/account/use-autosave.ts`, `lib/use-autosave.ts`, `organization-detail.tsx:239` | Zwei Hooks namens `useAutosave` mit verschiedener Signatur, Vorgabe 3000 ms vs. 1500 ms; Aufrufer setzt 2500 ms. 5 Importe vs. 1 (beleg-work, 3×). | einen Hook (z. B. `lib/use-autosave.ts`) mit beiden Formen oder klar getrennten Namen (`useAutosaveValue` / `useAutosaveSignature`); eine Vorgabe | mittel | ja (Timing) | `grep -rn "use-autosave'"` |
| F-41 | Doppelung | `account/sections/profile-section.tsx:171` vs. `erp/fields.tsx:23` | `Card` fast zeichengleich nachgebaut; `user-detail.tsx:48–52` behauptet, sie wohne gemeinsam in fields. | `fields.Card` importieren | niedrig | nein | Vergleich beider Rümpfe |
| F-42 | Doppelung | `profile-section.tsx:188` vs. `user-detail.tsx:55` | `SubBlock` wortgleich zweimal. | nach `fields.tsx` | niedrig | nein | Vergleich |
| F-43 | Doppelung | `user-detail.tsx:62`, `profile-section.tsx:98,195`, `territory-map.tsx:127`, `step-record.tsx:69`, `process-designer.tsx:663`, `address-book.tsx:86`, `article-detail.tsx:583,698` | 9 Varianten des Mikro-Labels (11/12 px, 600/700, Laufweite .05/.06/.07em) statt `fields.MICRO_LABEL`/`Label`; `article-detail.FieldLabel` ist ausdrücklich «lokal» neben dem geteilten `Label`. | `MICRO_LABEL`/`Label` nutzen | niedrig | ja (minimal) | `grep -rn "textTransform: 'uppercase'"` (pay-online:286 ist Stripe-Appearance → bleibt) |
| F-44 | Doppelung | `article-detail.tsx:600` (`EditField`) vs. `account/field.Field` vs. `fields.inputCls` | Drittes Eingabefeld-Bauteil. | zu prüfen, ob `Field` + `Label` genügen | mittel | ja | Lesen |
| F-45 | Doppelung | `communication.tsx:401`, `beleg-work.tsx:1040`, `photo-capture.tsx:155` | Drei `Chip`-Bauteile; communication-Chip wechselt die Polsterung je nach `onRemove` (dieselbe Geometrie-Falle wie #1016). | gemeinsamen Chip in `fields`/`module-ui` erwägen; mindestens Name eindeutig | mittel | nein | `grep -rn "function Chip"` |
| F-46 | Doppelung | `user-detail.tsx:114,175` | `role === 'employee' \|\| role === 'admin'` inline statt `record-status.isStaff` (CLAUDE: «gefragt wird an einer Stelle»). | `isStaff()` | niedrig | nein | `grep -rn "role === 'employee'"` |
| F-47 | Doppelung | `communication.tsx:421–445` (`People`) vs. `fields.SearchSelect`/`ObjectSelect` | Eigene entprellte Personensuche mit Stale-Schutz; das Haus hat `ObjectSelect` als «ein Referenzfeld». 9× das Muster `setTimeout + stale = true` in 7 Dateien. | Hook `useSearch(q, fn, delay)`; `People` auf ihn ziehen | mittel | nein | `grep -rn "stale = true"` = 9 |
| F-48 | Doppelung | `components/erp/article-detail.tsx:399` | `fmtWeight` nutzt `toLocaleString('de-CH')` – genau die ICU-Falle (`’` vs `'`), gegen die `formatAmount` den Trenner festschreibt. | `formatAmount(v, …)` bzw. eine `formatNumber` in utils | niedrig | ja (ab 1000 kg) | `grep -rn toLocaleString` |
| F-49 | Doppelung | `communication.tsx:78` (`dayLabel`) | Baut aus `day(iso)` per `split('.')` wieder ein ISO-Datum, um `when()` zu füttern – hängt an der Ausgabeform von `day()`. | `when.ts` um «Kalendertag als Aussage» ergänzen (`whenDay(iso)`) | niedrig | nein | Lesen `lib/when.ts` |
| F-50 | Doppelung | `#E51A14` (17×: account-shell 9, login-dialog 3, field 2, layouts 2, security 1), `--ix-red*`-Aliase (`globals.css:15–18`, 12 Verwendungen), `--inexxio-red` (25) | Markenrot in drei Schreibweisen. | `var(--inexxio-red)` überall; `--ix-*`-Alias auflösen | niedrig | nein | `grep -rn "#E51A14"`, `grep -c "var(--ix-red"` |
| F-51 | Doppelung | `communication.tsx:237`, `fields.tsx:495` | `var(--color-warning)` / `--color-warning-icon` (Rohtoken) neben `var(--warning)` (semantischer Alias) im selben Bauteil. | `--warning` | niedrig | nein | `grep -rn "var(--color-"` |
| F-52 | Doppelung | `types/index.ts:46–80, 277–325, 333–390` | Handgeschriebene `ArticleInput`, `CompanySettings`, `FeedbackAnchor/Context/Note/Create/Update` – das generierte Schema hat `ArticleCreate`, `CompanySettingsResponse`, `Feedback*`. | auf `components['schemas'][…]` umstellen (wie die übrigen Typen) | mittel | nein | `grep -nE "^ +(Feedback|ArticleCreate|CompanySettingsResponse)" types/api.ts` |
| F-53 | Doppelung | `profile-section.tsx` vs. `user-detail.ProfileForm` | Dasselbe Personenformular (Name, Telefon, Geburtstag, Adressbuch, Firma) zweimal gebaut; die Hausregel verlangt «derselbe Pfad» – im Backend erfüllt, im Frontend nicht. | **zu prüfen**: gemeinsamer Personen-Block, ERP ergänzt Anstellung | mittel | nein | Lesen beider Komponenten |

### Achse 4 – Benennung

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | VÄ | wie geprüft |
|---|---|---|---|---|---|---|---|
| F-30 | Benennung | `lib/modules.ts:84–203`, Leser `process-designer.tsx`, `beleg-work.tsx` | `DEAL_*`/`dealDirection` für das Modul `beleg` (Backend: `domain/voucher`). | `VOUCHER_*`/`voucherDirection` (oder `MONEY_*`); Wächter in `test_frontend_mirrors.py` mitziehen (Testagent) | mittel (Wächter) | nein | `grep -rn "DEAL_"` |
| F-31 | Benennung | `lib/api.ts:507`, Leser `communication.tsx:443`, `beleg-work.tsx:955`, `process-designer.tsx:421` | `searchVoucherParties` (Endpunkt `/orders/voucher-parties`) ist auch die Personensuche der Kommunikation (`staff=true`). | `searchPeople` – Backend-Pfad z. B. `/erp/people` (mit Backend-Agent abstimmen) | mittel | nein | `grep -rn searchVoucherParties` |
| F-32 | Benennung | `lib/status-flow.ts:1–3` | Datei heisst «status-flow», Kopf beschreibt einen Lebenszyklus «Entwurf → Freigeben → … → Reaktivieren», den es nicht gibt; Inhalt sind Ampeltöne + `StatusCfg`. | `lib/status-tone.ts`, Kopf neu | niedrig | nein | Lesen |
| F-33 | Benennung | `components/account/{field,save-status,use-autosave}.tsx`, `account/sections/system-config-section.tsx` | Unter «account» liegen gemeinsame Bausteine, die das ERP importiert (field: 9 Importeure, davon 6 ERP); `system-config-section` hat nur einen Leser: `erp/organization-detail`. | nach `components/form/` bzw. `components/erp/` verschieben | niedrig | nein | Importeure per grep |
| F-34 | Benennung | `fields.tsx:1215` (`Row`), `module-ui.tsx:294` (`Actions`) vs. `communication.tsx:171,479` | Exportiertes `Row`/`Actions` und gleichnamige lokale Funktionen mit anderer Bedeutung. | lokale umbenennen (`MessageActions`, `PersonRow`) | niedrig | nein | Deklarationsliste |
| F-35 | Benennung | `lib/modules.ts:395` | `ModuleDraft.sample` «je Instanz» – die Stichprobe ist seit dem Umbau der Anteil an der **Gesamtmenge**. | Kommentar korrigieren | niedrig | nein | CLAUDE.md «Die Stichprobe ist EINE Zahl» |
| F-36 | Benennung | `lib/erp-record.ts:48` | «'organization' erscheint nur für Admins» – Firmen sieht jedes Personal (CRM Schritt 1; `erp/page.tsx:212`). | korrigieren | niedrig | nein | Lesen |
| F-37 | Benennung | `order-detail.tsx:478–486,605` | «Lieferanten-Sicht» – gemeint ist die Sicht jeder Gegenpartei (`viewerRole === 'party'`). | «Partner-Sicht» | niedrig | nein | Lesen |

### Achse 5 – Vereinfachung

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | VÄ | wie geprüft |
|---|---|---|---|---|---|---|---|
| F-54 | Vereinfachung | `app/(erp)/erp/page.tsx:147–762` | `ErpPage` ist **616 Zeilen**, 24 `useState`, 13 `useEffect`; `isAdmin`, `staff`, `viewerRole` sind drei Zustände aus derselben `me.role`. | einen `role`-Zustand, Rest ableiten; Feed-Laden (Promise.allSettled, data-changed, visibility, Instanz-Paging) in `useErpFeed()`; Mail-Sync + offene Zähler in `useMessagesBadge()` | mittel | nein | AST-Funktionslängen; Lesen 147–330 |
| F-55 | Vereinfachung | `components/erp/beleg-work.tsx` | 2 805 Zeilen, 43 % Kommentar, ~45 Bauteile; `d`, `busy`, `onAction` (+ `orderObjectId`, `stepId`) laufen durch jede Ebene. | Kontext `BelegCtx {d,busy,onAction,orderObjectId,stepId}`; Datei in Ordner aufteilen (s. Grössen-Tabelle) | mittel | nein | Deklarationsliste; Props-Signaturen |
| F-56 | Vereinfachung | Funktionen > 80 Zeilen (54 Stück) | Grösste: `ErpPage` 616, `AGBPage` 417 (statischer Text – ok), `OrganizationDetail` 389, `ScanDialog` 331, `LoginDialog` 317, `ArticleDetail` 284, `StockPicker` 267, `Composer` 263, `AddressField` 253, `RunView` 243, `ProcessColumns` 232, `AccountShell` 230, `CaptureWork` 226, `OrderDetail` 226, `TerritoryMap` 214, `Money` 204, `SearchSelect` 191, `PayOnline` 187, `QuoteRow` 186, `MoneyFields` 186. | schrittweise beim nächsten Anfassen; Reihenfolge s. Paketierung | – | nein | AST-Skript (Längen inkl. Kommentare) |
| F-57 | Vereinfachung | `account/account-shell.tsx:43–272` | Mobil- und Desktop-Zweig rendern Kopf, Fortschritt und Navigation je für sich (zweimal dieselbe Initialen-/Prozent-Logik und Farben). | einen Kopf/Navi-Baustein, Layout per CSS | mittel | nein | Lesen |
| F-58 | Vereinfachung | `lib/api.ts:341,349,598,626,646` | Blöcke von 3–16 Leerzeilen (Löschreste), Abschnitt «ERP Articles» enthält Mail-Methoden. | Leerzeilen weg, Abschnitte sortieren | niedrig | nein | awk über Leerzeilen-Läufe |
| F-59 | Vereinfachung | `lib/api.ts:906–967` | `mapSettingsFromBackend/ToBackend` führt Aliasnamen nur im Frontend (`street_number`↔`street_nr`, `zip`↔`zip_code`, `uid`↔`uid_number`) – genau die Mapper-Bauart, an der #984 still `legal_name` verlor. | Backend-Namen direkt übernehmen (Typ aus `CompanySettingsResponse`), Mapper streichen | mittel | nein (wenn vollständig umgestellt) | Feldvergleich mit `schemas/admin.py:123–178` |

### Achse 6 – Robustheit

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | VÄ | wie geprüft |
|---|---|---|---|---|---|---|---|
| F-60 | Robustheit | `communication.tsx:838–843` | Unmount während «Rückgängig»: `createMessage(...).catch(() => {})` – scheitert der Versand, ist die Nachricht verloren, ohne Meldung. | Fehler mindestens loggen und global melden (z. B. Ereignis an `ErpPage`), oder Entwurf in `sessionStorage` halten bis Erfolg | mittel | ja | `grep -rn ".catch(() => {})"` |
| F-61 | Robustheit/Bug | `lib/utils.ts:46–59`, `lib/record-name.ts:26–29` | `userDisplayName`: toter `company_name`-Zweig (Feld fehlt in `UserProfileResponse`), E-Mail-Präfix statt ganzer E-Mail (Backend `models/user.py:105`), Docblock und Kommentar widersprechen sich; `userName` prüft `n !== u.email` und gibt darum für Personen ohne Namen den Präfix statt `null` zurück. | Regel = Backend: «Vorname Nachname» → E-Mail; `userName` → `full || null` | niedrig | ja (Feed zeigt «Kein Name» statt Präfix) | Feldliste `UserProfileResponse` aus api.ts |
| F-62 | Robustheit/Text | `article-detail.tsx:72` | Platzhalter «darunter wird automatisch nachbestellt» – kein Leser von `safety_stock`/`min_order_qty` im Backend (nur Modell, Schema, main). | Satz streichen; fachlich **zu prüfen**, ob die Felder (samt `supplier_article_number`) bleiben | niedrig | ja (Text) | `grep -rln safety_stock backend/app` |
| F-63 | Robustheit | `app/(erp)/erp/page.tsx:212,223,237,274,286,307–310,509,708,736` | ~12 Lade-Aufrufe mit `.catch(() => {})`: scheitert ein Feed, bleibt die Liste stumm leer (Startladen nutzt `allSettled` ebenfalls ohne Meldung). | eine Fehlerzeile im Feed-Kopf (wie `mailNote`) | niedrig | ja | grep |
| F-64 | Robustheit | `lib/api.ts:958–966` | `mapSettingsToBackend` schickt alles ausser einer Skip-Liste; `is_own` und `email` würden bei einem Gesamt-Update mitgehen (heute baut `organization-detail` die Nutzlast selbst → latent). | Erlaubtliste statt Sperrliste, oder F-59 | niedrig | nein | Lesen + `sites.ENTITY_FIELDS` |
| F-65 | Robustheit | `account/account-shell.tsx:49` | `isEmployee = role === 'employee'` – ein **Admin** sieht im Konto seine Anstellung nicht und kann seine Firmenzuordnung ändern, die für Personal eine eigene sein muss. | **zu prüfen**: `isStaff(role)` | niedrig | ja | Vergleich mit `record-status.isStaff` |
| F-66 | Robustheit | eslint-disable (18) | 6× `react-hooks/exhaustive-deps` (login-dialog:108, account/use-autosave:44, communication:774, process-columns:227, definition-lines:450,472) – alle begründet; Rest `no-img-element`/a11y. | bleibt; bei F-40 `use-autosave:44` mit auflösen | – | – | `grep -rn eslint-disable` |
| F-67 | Robustheit | `communication.tsx:443`, `process-designer.tsx:450`, `definition-lines.tsx:251` | Suchfehler werden verschluckt → Liste bleibt leer, ohne «Suche fehlgeschlagen». | im gemeinsamen Such-Hook (F-47) einmal behandeln | niedrig | ja | grep |

### Achse 7 – Kommentare

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | VÄ | wie geprüft |
|---|---|---|---|---|---|---|---|
| F-70 | Kommentar veraltet | `lib/api.ts:626–629` | Verweist auf `recovery.auto_resolve` und `POST …/cover` – beides existiert nicht. | entfernen | niedrig | nein | `ls backend/app/services` (kein recovery), Routenliste |
| F-71 | Kommentar verwaist | `lib/api.ts:435–436` | JSDoc «Der Artikel-Feed …» steht vor dem Beleg-Abschnitt, nicht vor `getArticles` (`:556`). | verschieben | niedrig | nein | Lesen |
| F-72 | Kommentar verwaist | `components/erp/article-detail.tsx:589–593` | Abschnitt «Abgeleitete Kennzahlen … `services/metrics.py`» ohne Code darunter; Datei gibt es nicht. | entfernen | niedrig | nein | `ls backend/app/services` |
| F-73 | Kommentar verwaist | `beleg-work.tsx:138` | «Wie viele Tage von heute bis zu diesem Datum?» – JSDoc ohne Funktion (Rest von `daysUntil`), hängt jetzt an `BelegWork`. | entfernen | niedrig | nein | Lesen |
| F-74 | Kommentar veraltet | `beleg-work.tsx:234` | Regel stehe in `voucher._assert_complete` – heute `ask_problem`/`_assert_ask`. | korrigieren | niedrig | nein | `grep -n "def ask_problem" services/voucher.py` |
| F-75 | Kommentar verwaist | `lib/modules.ts:250–262, 284, 489–506` | Docblock «unbekannte Farbfamilie» steht vor `moduleIcon` statt vor `moduleTone`; «Typen, die einen Sollwert brauchen» hängt an `MOVE_MODULE` statt an `NEEDS_TARGET`; zwei JSDoc-Blöcke übereinander vor `MONEY_FORM` (der erste gehört zu `MODULE_FORM`). | Blöcke an ihre Deklaration | niedrig | nein | Lesen |
| F-76 | Kommentar veraltet | `lib/modules.ts:657` | `Zahlung.clean_config` – Klasse heisst `Beleg`. | korrigieren | niedrig | nein | `grep "^class " domain/modules.py` |
| F-77 | Kommentar veraltet | `types/index.ts:140,217–225,284` | «Reiter Bestand am Artikel» (Artikel hat keine Reiter), «zwei Stufen» (drei), «Forderung (`charge`) oder Zahlung» (nur noch Zahlungen), «Gesellschaft … endgültig (keine Reaktivierung)» (`reopenCompany` existiert). | korrigieren | niedrig | nein | Lesen + CLAUDE.md §9.15q / CRM-Nachtrag |
| F-78 | Kommentar veraltet | `components/account/account-shell.tsx:56–57`, `hooks/useProfileCompletion.ts:14–23` | Siehe F-16/F-24. | mit F-16/F-24 | niedrig | nein | – |
| F-79 | Kommentar-Menge | `lib/modules.ts` 62 %, `module-ui.tsx` 59 %, `process-flow.tsx` 46 %, `beleg-work.tsx` 43 %, `process-columns.tsx` 43 %, `process-diagram.tsx` 42 %, `process-designer.tsx` 41 % | Lange Prosa mit Testnotiz-Historie («►►►», Zitate des Nutzers, «erster Anlauf war falsch»). Die Regel gehört in 1–3 Sätze an den Code, die Geschichte in Git/`docs/history`. | pro Datei kürzen auf «was + warum heute»; Testnotiz-Nummer als Referenz genügt | mittel (Wächter lesen teils Rümpfe, nicht Prosa – vorher `test_frontend_mirrors.py` laufen lassen) | nein | Zählskript |
| F-80 | Kommentar/Doku | `frontend/CLAUDE.md` (1 129 Zeilen) | Beschreibt u. a. den Kontotyp (`:979–1010`, `account_type`, `lib/accounts.ts`) als aktuell; enthält Abschnitte «— ENTFERNT» mit Methodenlisten. | wie die Wurzel-CLAUDE.md: Historie nach `docs/history/`, Rest auf Ist-Stand | niedrig | nein | `grep -n Kontotyp frontend/CLAUDE.md` |

---

## Dateien nach Grösse (Top 15, ohne `types/api.ts`)

| # | Datei | Zeilen | Kommentar | Einschätzung |
|---|---|---|---|---|
| 1 | `components/erp/beleg-work.tsx` | 2 805 | 43 % | **Aufteilen** in `components/erp/beleg/`: `fields.tsx` (Editable, DocPick, DocRef, DocFind, Missing, Note – eigentlich Haus-Bauteile, Kandidat für `module-ui`), `head.tsx` (DocHead, Correction, Parties, Party, Anschrift, Recipients, Chip, Issuer, Gaps), `goods.tsx` (Goods, LineRow, Customs, Sums, SumRow, Currency), `terms.tsx` (Terms, SavedTerm, Term, Stacked, Fixed, Delivery), `quotes.tsx` (Quotes, QuoteRow, Offer, quoteLook), `money.tsx` (Money, InvoiceRow, Balance, EntryRow, Transfer, Entry, Ask), `index.tsx` (BelegWork, Footer, StageAction, StageRow, Kontext). Mit Kontext statt Prop-Drilling. Nach Kürzen der Prosa ~1 500 Zeilen. |
| 2 | `components/erp/process-diagram.tsx` | 1 329 | 42 % | Aufteilen: Graph-Helfer (`definitionGraph`, `columnRows`, `axisEdges`, Journey-Funktionen) nach `lib/process-graph.ts`; `ModuleShell`/`ModuleMark`/`StepCard` nach `module-shell.tsx`; Rest (FlowColumn, Axis, StateRow …) bleibt. |
| 3 | `components/erp/fields.tsx` | 1 233 | 33 % | Sammeldatei für drei Gattungen: Detail-Anatomie (Card, SPEC, DetailHeader, RecordIcon), Formularfelder (Label, inputCls, SearchSelect, Segmented, IconSwitch) und Anzeige (StatusBadge, Row, Tooltip). Aufteilen in `detail.tsx` / `form.tsx` / `display.tsx` mit `fields.tsx` als Re-Export (keine Aufrufer anfassen). `SearchSelect` (191 Z.) eigene Datei. |
| 4 | `components/erp/communication.tsx` | 1 081 | 15 % | Code-dicht. `Composer` (263 Z., 29 `useState` in der Datei) in eigene Datei; Zustand des Composers in `useReducer` (Draft-Objekt existiert schon – `restore`/`clear` setzen 12 Felder einzeln). Verlauf (`Timeline`, `Bubble`, `Time`, `linkify`) separat. |
| 5 | `app/globals.css` | 981 | 32 % | Tote Klassen raus (F-13), `@layer components`-Altbestand (`.container`/`.section` nur AGB, `.btn-primary` 3 Leser) prüfen; Prosa kürzen. Kein Aufteilen nötig. |
| 6 | `lib/api.ts` | 978 | 29 % | Tote Methoden/Leerzeilen raus (F-02…F-06, F-58), Mapper vereinfachen (F-59). Danach ~800 Zeilen; Aufteilen nach Ressource optional. |
| 7 | `components/erp/article-detail.tsx` | 955 | 27 % | `ArticleDetail` 284 Z.; Namensfeld mit Vorschlägen und `SpecRead`/`SpecEdit` in eigene Dateien; lokale `FieldLabel`/`EditField` durch Haus-Bauteile (F-43/F-44). |
| 8 | `components/erp/order-detail.tsx` | 839 | 38 % | `RunView` (243 Z.) enthält den verschachtelten `stepBody` (116 Z.) – als eigene Komponente `StepBody` herausziehen; `DraftView` separat. |
| 9 | `components/erp/process-designer.tsx` | 781 | 41 % | `MoneyFields` (186 Z.) in eigene Datei (beleg-Definition); Prosa kürzen. |
| 10 | `app/(erp)/erp/page.tsx` | 769 | 18 % | `ErpPage` 616 Z. – Hooks `useErpFeed`, `useMessagesBadge`, `useDeepLink` herausziehen; Rollenzustand vereinheitlichen (F-54). Höchster Wartungsgewinn je Zeile. |
| 11 | `components/erp/definition-lines.tsx` | 684 | 33 % | `StockPicker` (267 Z.) in eigene Datei; `LineRow` 165 Z. ok nach Kürzen. |
| 12 | `components/erp/module-ui.tsx` | 682 | 59 % | Nicht aufteilen – Grabsteine (F-26) und Prosa kürzen, `MODULE_GRID` weg; danach ~350 Zeilen. |
| 13 | `lib/modules.ts` | 666 | 62 % | Nicht aufteilen – Kommentare halbieren, DEAL→VOUCHER (F-30), verwaiste Docblöcke (F-75), tote Konstanten (F-09/F-10). Danach ~300 Zeilen. |
| 14 | `components/erp/process-columns.tsx` | 655 | 43 % | `ProcessColumns` 232 Z.; Layout-Rechnung (`channels`, Zeilenraster) als reine Funktionen auslagern (testbar); Prosa kürzen. |
| 15 | `components/erp/capture-work.tsx` | 643 | 36 % | `CaptureWork` 226 Z., `NeedRow` 159 Z., `InstanceRow` 95 Z. – `NeedRow` (Ressourcenmodul) in eigene Datei. |

(Ausserhalb Top 15 auffällig: `organization-detail.tsx` 551 mit einer 389-Zeilen-Komponente,
`scan-dialog.tsx` 425 mit 331, `login-dialog.tsx` 376 mit 317, `account-shell.tsx` 272 mit 230.)

---

## Vorschlag Paketierung

Reihenfolge nach Risiko; jedes Paket einzeln mergebar, `npm run lint`, `npm run type-check`,
`npm test` und `backend/tests/test_frontend_mirrors.py` je Paket.

**P1 – Toter Code, null Verhaltensänderung** (½ Tag)
F-01…F-17 ohne F-12-Einwände, F-58. Reine Löschungen: `optimistic.ts`, 5 API-Methoden,
`TILE`, `ChoiceButton`, `MODULE_GRID`, `PARTY_NUMBER_LABEL`, `rose`, `StatusAction`,
`ConsentCategory`, Typ-Aliase, prop `side`, Option `condition`, 11 CSS-Klassen + Keyframes,
Tailwind-Animationen, Leerzeilen. Vorher `grep` in `backend/tests` auf jeden Namen
(`PARTY_NUMBER_LABEL` wird dort als «darf nicht vorkommen» geprüft – unkritisch).

**P2 – Veraltete und verwaiste Kommentare** (½–1 Tag)
F-21, F-22, F-24, F-26, F-29, F-35…F-37, F-70…F-78. Nur Kommentare; schliesst die falschen
Verweise auf `deal`/`purchase`/`recovery`/`metrics`. F-79 (Prosa kürzen) als Fortsetzung
datei­weise, beginnend mit `lib/modules.ts` und `module-ui.tsx`. Vorher prüfen, dass kein
Wächter Kommentartext liest (die meisten nutzen `_code()`).

**P3 – Benennung** (½ Tag, mit Test-Agent abstimmen)
F-30 (`DEAL_*` → `VOUCHER_*`), F-32 (`status-flow` → `status-tone`), F-33 (Bausteine aus
`components/account/` heraus), F-34, F-23. F-31 nur zusammen mit dem Backend-Agenten
(Endpunkt `voucher-parties` → Personensuche).

**P4 – Doppelungen zusammenführen** (1–2 Tage)
F-40 (ein Autosave-Hook, eine Vorgabe), F-41/F-42 (Card/SubBlock), F-43/F-44 (Labels/Felder),
F-46, F-48, F-49, F-50, F-51, F-47 + F-67 (`useSearch`-Hook mit Fehlerbehandlung),
F-52 (generierte Typen), F-59/F-64 (Settings-Mapper). Kleine sichtbare Abweichungen möglich.

**P5 – Alt-Palette im Konto** (1 Tag, sichtbar)
F-20, zusammen mit F-57 (AccountShell vereinheitlichen) und F-65 (Admin = Personal). Am
Bildschirm gegen das Design-System prüfen.

**P6 – Robustheit** (½ Tag)
F-60 (Nachricht beim Unmount nicht verlieren), F-61 (Personenname = Backend-Regel), F-62
(irreführender Platzhalter; Fachfrage zu `safety_stock` & Co.), F-63 (Feed-Ladefehler sichtbar).

**P7 – Grosse Dateien aufteilen** (fortlaufend, beim nächsten Anfassen)
`beleg-work.tsx` (mit Kontext), `ErpPage`, `order-detail.stepBody`, `fields.tsx` (mit
Re-Export), `process-diagram.tsx`. Kein eigener Release – immer im Zuge fachlicher Arbeit,
damit die Wächter mitwandern.

**Für andere Agenten notiert:** Backend – `PATCH /erp/articles/{id}`, `GET /admin/users`,
`GET /admin/audit-log`, `POST /auth/terms-accept` haben keinen Frontend-Aufrufer;
`safety_stock`/`min_order_qty`/`supplier_article_number` haben keinen Leser;
`deadcode.py` falsch-positiv bei `src/islands`, falsch-negativ bei Typ-Aliasen.
Tests – Wächter zu `DEAL_*`-Namen und `MODULE_TONE` bei F-30/F-10 mitziehen.
