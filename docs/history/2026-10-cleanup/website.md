# Cleanup-Analyse: öffentliche Website (`website/`) und ihre Nähte

Stand `develop` @ fbd70fc, 18.10.2026. Nur gelesen, nichts im Repo geändert. **Nicht
gebaut**: `npm run build` schreibt im `postbuild` die versionierte Datei
`website/OFFENE_PUNKTE.md` (check-content), das wäre eine Änderung im Repo gewesen.
Untersucht habe ich stattdessen das vorhandene `website/dist/` (heute 15:13 gebaut, ohne
`SITE_API`) und `frontend/out/` (12:45).

Methode: Leser über `grep -rn`/`grep -rlF` in `website/src`, `website/scripts`,
`frontend/src`, `frontend/scripts`, `backend/app` gesucht, Schlüssel aus `site.mjs` per
Node-Skript geflacht und je Schlüssel nach `{{pfad}}`-Token und `.schluessel`-Zugriff gesucht,
CSS-Klassen aus `global.css`/`form.css` gegen alle `.astro/.ts/.mjs/.md/.html` geprüft. Wo die
automatische Suche falsche Treffer lieferte, habe ich von Hand nachgeprüft. Steht unten
**„zu prüfen“**, ist es nicht gemessen.

## Kurzfassung (Top 10)

1. **Ein Schalter, der nichts schaltet, und ein Bericht, der deshalb falsch ist (W-01).**
   `site.features.team = false` liest kein Code. Die Team-Sektion auf `/ueber-uns` und das
   Team-Foto im Kopf-Dropdown „Karriere“ werden immer gezeigt. `OFFENE_PUNKTE.md` meldet
   trotzdem „`team` – ohne echte Fotos abgeschaltet“.
2. **Prod-Rewrite zeigt auf das Dev-Backend (W-30).** In `firebase.json` steht
   `/api/** → serviceId inexxio-backend-dev`, und derselbe Eintrag gilt beim Prod-Deploy
   (`deploy-prod.yml` deployt ohne `jq`-Anpassung, der Prod-Dienst heisst
   `inexxio-backend-prod`). Damit sind Formular (`/api/v1/contact`) und Kontaktdaten
   (`/api/v1/public/contact`) in Prod kaputt oder schreiben ins falsche System. Der Punkt ist
   bekannt (Start-Checkliste im Report 20261004), im Code aber offen. Infrastruktur: zu prüfen.
3. **Toter Header-Block in `firebase.json` (W-31).** `/(app|admin)/**` setzt `no-store` und
   `X-Robots-Tag`, aber diese Routen gibt es nicht (das Frontend hat `(account)`, `(auth)`,
   `(erp)` und `(public)`). `/erp` und `/konto` bekommen den Block **nicht**.
4. **Der mailto-Ausweg des Formulars nutzt die Adresse aus dem Build, nicht die aus dem ERP
   (W-33).** `form.ts` liest `data-mail`, und `contact.ts` tauscht nur Textknoten und
   `a[href]`. `fail()` überschreibt zudem den bereits getauschten `href`.
5. **Das Formular-Senden hat kein Timeout (W-34).** Hängt das Backend, bleibt der Knopf
   gesperrt, bis Cloud Run nach bis zu 300 s abbricht. `contact.ts` hat dagegen ein Timeout
   von 4 s.
6. **Tote Konfiguration in `site.mjs` (W-02…W-07):** `history.experience`,
   `history.markets`, `people.owner.career` (als Export), `area.home`, `seo.oldDomain`,
   `analytics.provider`, `service.photo`, dazu `__SITE_URL__` in `astro.config.mjs`.
7. **Tote Einträge im Formular-Vokabular und im Router (W-10/W-11).** In
   `website_contact.json` liest niemand `address`, `pages.contact` und `mail.closing`.
   `mail_layout.GREETING` ist eine zweite Kopie von `closing`. Im Router hat
   `contact._summary()` keinen Aufrufer.
8. **Tote Bild-Dateien werden mit ausgeliefert (W-14/W-15).** Das Beispielbild
   `samples/portraet-clemens.jpg` (499 KB) ist durch ein echtes Foto ersetzt, liegt aber noch
   im Repo und in `dist/`. `typenschild-hs`, `servicefahrzeug` und `aufbau-reparatur` stehen
   auf keiner Seite. Zwei davon nennt der Bildnachweis im Impressum trotzdem, und der
   `import.meta.glob(..., {eager})` kopiert alle Originale nach `dist/_astro`.
9. **Dieselbe Liste an vier Stellen (W-20).** Die ERP-/Privat-Pfade stehen in
   `site.privatePaths`, `check-site.ERP_PATHS`, einer Regex in `check-site.checkErpPaths`
   (dort fehlt `abmelden`) und `merge-hosting.ERP`. Der Literal „Tuttwil-Wängi“ steht 20-mal
   im Inhalt, während `area.home` ungenutzt ist (W-21).
10. **Die Doku in `website/` ist zu grossen Teilen Historie (W-40…W-43).** Beide
    Abschlussberichte beschreiben einen Stand, den es nicht mehr gibt (Sonderlösungen,
    Notfallnummer, Servicezeile, SMTP-Versand, „125 offene Punkte“). Die Start-Checkliste, auf
    die `CLAUDE.md` verweist, verlangt noch `INQUIRY_SMTP_*`. Der Plan ist eine Folge von
    124 Entscheiden mit vielen „löst X ab“.

## Befunde

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | Verhaltens­änderung | wie geprüft |
|---|---|---|---|---|---|---|---|
| W-01 | 1 Tot / 6 Robustheit | `website/src/config/site.mjs:203`, `photos.mjs` (`team.feature`), `pages/ueber-uns.astro:36-42`, `site.mjs:276` (Karriere-Foto `team`) | `features.team: false` hat keinen Leser. Die Team-Sektion und das Foto stehen immer da. Ausgewertet wird `features` nur von `check-content.mjs:57/76`, das daraus in `OFFENE_PUNKTE.md` „abgeschaltet“ schreibt. | Entweder Schalter + `feature`-Feld entfernen (dann sind Bericht und Wirklichkeit gleich) oder die Sektion wirklich daran hängen. Fachlich entscheiden: soll das Team bis zum Fototag sichtbar sein? | niedrig | nein (beim Entfernen; nur der generierte Bericht ändert sich) / ja (wenn die Sektion daran gehängt wird) | `grep -rn "features\." src scripts` → nur `heiriAdvisory` (3×) und check-content; `grep -n team src/pages/ueber-uns.astro` ohne Bedingung |
| W-02 | 1 Tot | `site.mjs:135`, `:138` | `history.experience` und `history.markets` haben weder Token noch Zugriff; genutzt wird nur `experienceDative`. | löschen | keins | nein | Schlüssel-Skript + `grep -rlF "{{history.experience}}"` und `grep -rnE "\.markets\b"` → 0 |
| W-03 | 1 Tot / 7 Kommentar | `site.mjs:145`, Kommentar `:39` | `people.owner.career` hat keinen Leser. Der Kommentar „als Liste (Über uns)“ stimmt nicht mehr, nur `short` (seo.mjs:188) wird gelesen. | `career` aus dem Export nehmen (die Konstante `ownerCareer` bleibt für `short`) und den Kommentar korrigieren | keins | nein | `grep -rn career src` → nur site.mjs |
| W-04 | 1 Tot / 3 Doppelung | `site.mjs:183` | `area.home` („Tuttwil-Wängi TG“) hat keinen Leser. Derselbe Text steht 20-mal als Literal im Inhalt (siehe W-21). | entweder als `{{area.home}}` einsetzen oder löschen | keins | nein | `grep -rlF "{{area.home}}"` → 0, `grep -rn "area\.home"` → 0 |
| W-05 | 1 Tot | `site.mjs:302` | `seo.oldDomain` hat keinen Leser. | löschen (die Weiterleitungen leben in firebase.json, check-site kennt die alten Pfade) | keins | nein | grep `oldDomain` → 0 ausserhalb site.mjs |
| W-06 | 1 Tot | `site.mjs:318-321`, `src/scripts/track.ts:16-20` | `analytics.provider: null` hat keinen Leser. `track.ts` fragt `html[data-analytics]`, das nirgends gesetzt wird. Auf das Ereignis `ix:track` hört niemand. Das ganze Tracking (13× `tel_click`, 5× `mailto_click`, `part_inquiry`, `form_start/submit`) wirkt also derzeit nicht. Der Kommentar nennt noch `pikett_click` und `abo_interest`. | Den Haken bewusst stehen lassen (Plausible ist geplant), aber `analytics.provider` löschen oder wirklich als `data-analytics` setzen. Die Ereignisliste im Kommentar nachziehen. | keins | nein | `grep -rn "data-analytics\|analytics" src` → nur track.ts:16 und site.mjs; `grep -rn "ix:track"` → nur Dispatcher |
| W-07 | 1 Tot | `site.mjs:236` (`service.photo`), `:233-238` (`service.overview`, `children: []`) | Gruppen ohne Kinder rendert der Kopf als einfachen Link (`Header.astro:60`), der Fuss nimmt `text`. `photo` und `overview` von Service und Speziallösungen werden nie gezeigt. Laut OFFENE_PUNKTE ist `servicefahrzeug` „noch nicht verwendet“, die einzige Referenz ist `service.photo`. | `photo`/`overview` für Gruppen ohne Kinder optional machen und bei Service weglassen. Wird es weiter gebraucht (Typ `NavGroup`), mindestens das Foto entfernen. | niedrig (Typ `NavGroup` anpassen) | nein | Header.astro:60-107 gelesen; `grep -rln servicefahrzeug src` → nur config |
| W-08 | 1 Tot | `website/astro.config.mjs:44`, `src/env.d.ts:5` | `__SITE_URL__` wird definiert und deklariert, aber nie gelesen (überall wird `Astro.site` genutzt). | löschen | keins | nein | `grep -rn __SITE_URL__` → nur Definition und Deklaration |
| W-09 | 1 Tot (Platzhalter-Rest) | `src/components/Footer.astro:55`, `src/lib/seo.mjs:73` | `isMissing(site.email.primary) && <span set:html={rich(site.email.primary)}>` rendert bei leerem `primary` einen leeren Span. Das ist ein Rest der früheren `[[…]]`-Vermerke. In seo.mjs:73 ist `legalName` immer gesetzt, also ist der Zweig `isMissing(...) ? undefined` tot. | Beide Zweige streichen. `isMissing` bleibt für `contactEmail()` und `Quote`. | keins | nein (leerer Span fällt weg) | Footer/seo gelesen; `rich('')` gibt `''` zurück (text.mjs) |
| W-10 | 1 Tot (Naht) | `website/scripts/export-contact.mjs:40-42,72`, `backend/app/assets/website_contact.json` | Für `address`, `pages.contact` und `mail.closing` gibt es im Backend keinen Leser. `closing` ist zudem doppelt (`mail_layout.GREETING = "Freundliche Grüsse"`). | Die drei Schlüssel aus dem Export und aus `inquiry.mail.closing` nehmen und die JSON neu erzeugen. Oder umgekehrt: `mail_layout` liest `closing`, dann gäbe es nur eine Quelle. | niedrig (CI `--check` zieht mit) | nein | `grep -rn` auf alle 15 `mail.*`-Schlüssel in `backend/app` → `closing` 0×; `VOCAB["address"]`/`["pages"]["contact"]` 0× |
| W-11 | 1 Tot (Naht) | `backend/app/routers/contact.py:206` | `_summary()` hat keinen Aufrufer (Rest aus der Zeit des SMTP-Versands). | löschen | keins | nein | `grep -rn "_summary" backend/app backend/tests` → nur die Definition |
| W-12 | 1 Tot | `src/styles/global.css:136-137` (`.swoosh`), `:256` (`.btn--sm`), `:331` (`.field__hint`), `src/styles/form.css:8-12` (`.input--file`) | Klassen ohne Verwender, weder in der Website noch im Frontend (die Shell-CSS ist auf `.ix-shell` beschränkt). `.btn-link`/`.ix-grid-bg--fade` sind nur Kommentar-Verweise aufs DS, das ist in Ordnung. | Regeln streichen (bei `.swoosh` nur den Selektor-Teil) | keins | nein | Klassen-Extraktion + `grep -rlF` über `website/src` und `frontend/src`, auch Template-Strings (`btn--${…}`) gesucht → 0 |
| W-13 | 1 Tot | `website/scripts/merge-hosting.mjs:18` | Die Ausnahme `robots.txt` in `OVERRIDES` greift nie, weil `frontend/out` keine robots.txt hat (der Kommentar sagt das selbst). | auf `404.html` reduzieren. Liefert das ERP wieder eine, bricht der Merge laut ab, und das ist gewollt. | keins | nein | `ls frontend/out \| grep robots` → nichts; kein `app/robots.ts`, kein `public/robots.txt` |
| W-14 | 1 Tot (Asset) | `src/assets/photos/samples/portraet-clemens.jpg`, `photo-samples.mjs:37`, `photo-credits.json` (Eintrag `portraet-clemens`) | `portraet-clemens` hat ein echtes Foto (`file: 'portraet-clemens.png'`), das Beispielbild wird nie gezeigt. Durch den eager-Glob in `Photo.astro:26` liegt es trotzdem in `dist/_astro` (499 KB). | Beispieldatei, ALT-Eintrag und Credit-Eintrag löschen | keins | nein | `photos.mjs:92-93` (`file` gesetzt), `ls dist/_astro \| grep portraet` → `.jpg` vorhanden |
| W-15 | 1 Tot (Asset) / 6 | `photos.mjs` (`typenschild-hs`, `servicefahrzeug`, `aufbau-reparatur`), zugehörige `samples/*.jpg` und Credits | Diese drei Bildstellen kommen auf keiner Seite vor. Der **Bildnachweis im Impressum** nennt trotzdem zwei Beispielbilder („Typenschild an einer Maschine“, „Kleinbus … Basel“), die nirgends zu sehen sind (`PhotoCredits` filtert nach Config, nicht nach Verwendung). Beide Originale liegen in `dist/_astro`. | Einträge löschen, sobald klar ist, dass sie nicht gebraucht werden. Sonst `PhotoCredits` auf tatsächlich gerenderte IDs beschränken. Grundsätzlich: der eager-Glob über `assets/photos/**` liefert jedes Original aus. Zu prüfen ist, ob eine nicht-eager Zuordnung nur die genutzten emittiert. | niedrig | ja (Bildnachweis kürzer) | `grep -rln <id> src` ohne config → 0; `grep -o "Kleinbus…\|Typenschild an…" dist/impressum.html` → beide vorhanden |
| W-16 | 1 Tot / 5 | `src/scripts/form.ts:152`, `:162` | `for (const n of [name])` ist eine Schleife über ein einzelnes Element. `:not([type="radio"])` ist ein Rest der entfallenen Auswahlfelder (Bereich/Dringlichkeit); im Formular gibt es keine Radios mehr. | vereinfachen | keins | nein | InquiryForm.astro gelesen: keine `type="radio"` |
| W-17 | 1 Tot (Prüfregel) | `scripts/check-site.mjs:322`, `:409` | Gesucht wird nach `[[`. Die Syntax der gelben Vermerke gibt es in `text.mjs` nicht mehr, der Teil der Prüfung kann also nie mehr anschlagen. `{{` bleibt sinnvoll. | `\[\[` aus beiden Regexen nehmen, die Meldung auf „offener Wert“ kürzen | keins | nein | text.mjs: nur `{{…}}`, `**`, `==`, `[]()`; `grep -rn "\[\["` in src → 0 |
| W-20 | 3 Doppelung | `site.mjs:292` (`privatePaths`), `scripts/check-site.mjs:24` (`ERP_PATHS`), `:445-449` (Regex), `scripts/merge-hosting.mjs:19` (`ERP`) | Dieselbe Frage („welche Pfade gehören dem ERP?“) steht in vier Fassungen. Die Regex in `checkErpPaths` kennt `abmelden` nicht, `ERP_PATHS` kennt `api`/`_next` nicht. | Eine Liste in `site.mjs` (z. B. `erpPaths` + `privatePaths = [...erpPaths, '/shop', '/api/']`), die alle drei Skripte importieren | niedrig | nein | die vier Stellen gelesen und verglichen |
| W-21 | 3 Doppelung | `src/content/*.ts` (20 Fundstellen), `src/content/legal/impressum.md:3` | „Tuttwil-Wängi (TG)“ steht als Literal im Fliesstext, während `area.home`, `{{address.place}}` und `{{erp.city}}` (aus dem ERP getauscht) existieren. Die Impressum-Beschreibung schreibt Strasse und PLZ aus. | Fliesstext auf `{{area.home}}` bzw. `{{erp.city}}` umstellen (gewollt ist das laut Entscheid 64). Das Impressum ist bewusst „Betreiber“ und darf bleiben, sollte aber `{{address.line}}` nutzen. | niedrig | nein (gleicher Text) / ja, wenn `{{erp.city}}` genommen wird (dann tauscht es zur Laufzeit) | `grep -rn "Tuttwil-Wängi\|Tuttwil (Wängi\|9546\|Waldweg" src … \| grep -v site.mjs \| wc -l` → 20 |
| W-22 | 3 Doppelung (Naht) | `website/src/scripts/form.ts:24-25`, `backend/app/routers/contact.py:61-62` | Die Regexe für E-Mail und Telefon stehen in Browser und Server getrennt. Meldungen und Grenzen kommen schon aus einer Quelle (Vokabular), die Muster nicht. | Muster in `inquiry.mjs` aufnehmen (als String) und auf beiden Seiten lesen | niedrig | nein | beide Dateien gelesen, Muster heute identisch |
| W-23 | 3 Doppelung (Naht) | `backend/app/services/inquiry.py:80` (`_body`: „Firma“, „Telefon“, „Seite“), `contact.py:263` („ehemals HS Steiner“ hart), `contact.py:_subject` vs `services/inquiry.subject_of` | Die Beschriftungen der ERP-Nachricht sind im Backend fest eingetippt, statt aus `VOCAB.labels` zu kommen. Der Name auf der Fallback-Seite ist teils hart kodiert (`VOCAB.brand.full` gibt es). Der mailto-Betreff lautet „[Anfrage] Firma“, die ERP-Nachricht „Anfrage: erster Satz“. Der Kommentar in `form.ts:237` („derselbe Betreff … wie die E-Mail des Servers“) stimmt damit nicht mehr. | Labels aus `VOCAB`, `brand.full` statt Literal. Den mailto-Betreff entweder an `subject_of` angleichen (dann in beiden Sprachen derselbe Algorithmus) oder den Kommentar korrigieren. | niedrig | ja (Betreff im mailto, falls angeglichen) | `grep -n` in beiden Dateien, `subject_of` gelesen |
| W-24 | 3 Doppelung | `src/components/Header.astro:187` | Der mobile CTA ist hart „Anfrage“, `site.cta.label` ist „Anfrage stellen“. Vermutlich gewollt kürzer, steht aber als Literal. | `site.cta.short` o. ä. oder bewusst so lassen | keins | nein | gelesen |
| W-25 | 2 Rest / 4 Benennung | `src/pages/ueber-uns.astro:130`, `:4`, `content/ueber-uns.ts:3,53` | Die Überschrift „Werkstatt und **Einsatzgebiet**“ steht noch da, obwohl laut WEBSITE_PLAN 52 und CLAUDE.md kein Einsatzgebiet mehr genannt wird. Der Text darunter sagt „überall“. | Overline z. B. „Werkstatt und Einsatz“ / „Wo wir arbeiten“ | keins | ja (sichtbares Wort) | `grep -rn Einsatzgebiet src` |
| W-26 | 2 Rest | `site.mjs:289-292`, `scripts/seo.test.mjs:21` | `/shop` ist in robots.txt „reserviert“, obwohl der Shop entfernt ist. Harmlos. | Entscheiden: bleibt er als Vorhaltung, ist es in Ordnung. Sonst mit dem Test zusammen entfernen. | keins | ja (robots.txt eine Zeile weniger) | gelesen |
| W-27 | 4 Benennung | `scripts/export-contact.mjs` (3 Ausgaben) | Das Skript heisst `export-contact`, schreibt aber Formular-Vokabular, `frontend/src/lib/site-meta.json` **und** eine Logo-Kopie nach `frontend/public/brand/`. | Umbenennen in z. B. `export-erp.mjs` (+ `npm run export:erp`, CI-Schritt, Verweise) | niedrig (CI-Name, Doku) | nein | gelesen |
| W-28 | 4 Benennung | `inquiry.mjs` → `messages.contact` | Der Schlüssel `contact` meint heute „E-Mail fehlt“ (Rest aus der Zeit, als Telefon *oder* E-Mail genügte). | in `emailMissing` o. ä. umbenennen (beide Seiten, generiert) | niedrig | nein | `contact.py:146`, `form.ts:101` |
| W-29 | 5 Vereinfachung | `src/lib/inquiry-vocab.mjs` | Ein Modul mit 3 Zeilen, das `{labels, messages}` aus `inquiry` zurückgibt. | in `inquiry.mjs` als `export const vocab` aufnehmen, eine Datei weniger. Geschmackssache mit kleinem Gewinn, optional. | keins | nein | gelesen; 2 Importeure |
| W-30 | 6 Robustheit | `firebase.json` `rewrites[0]`, `.github/workflows/deploy-prod.yml` | `/api/**` → `inexxio-backend-dev`. Der Prod-Deploy übernimmt das unverändert, obwohl dort `CLOUD_RUN_SERVICE: inexxio-backend-prod` gilt. Formular und `public/contact` hängen an diesem Rewrite, das ERP-Frontend nicht (`NEXT_PUBLIC_API_URL`). | wie beim `X-Robots-Tag` per `jq` im Prod-Workflow ersetzen und mit `jq -e` absichern | **hoch** (falls Prod genutzt wird) | ja | gelesen; die Start-Checkliste (Report 20261004 §6) nennt es als offen. **Zu prüfen**: gibt es den Dienst `inexxio-backend-dev` im Projekt `inexxio-prod`? |
| W-31 | 1 Tot / 6 | `firebase.json` `headers[3]` `/(app|admin)/**` | Die Routen `/app` und `/admin` gibt es nicht. `no-store` und `noindex` greifen damit nirgends. `/erp` und `/konto` haben `Cache-Control: no-cache` (global) und bekommen den `noindex`-Header nur auf Dev. | Block auf `/(erp|konto|login|abmelden)/**` umstellen oder löschen (robots.txt sperrt die Pfade ohnehin) | niedrig | ja (beim Umstellen) | `ls frontend/src/app` → `(account) (auth) (erp) (public)` |
| W-32 | 6 Robustheit / 3 | `scripts/erp-contact.mjs:28` | Beim Build holt das Skript nur `phone`, `phone_e164` und `email` aus dem ERP, die **Anschrift** nicht. Die Vorgabe für HTML, JSON-LD, Impressum, llms.txt und den Fuss ohne JS ist immer die feste aus `site.mjs` (Waldweg 1), auch wenn das ERP etwas anderes führt. CLAUDE.md sagt „Telefon, E-Mail und Anschrift kommen aus dem ERP“. | `address_lines`/`name` mit ablegen und in `site.mjs` als Vorgabe nutzen (Strasse/PLZ/Ort parsen). Alternativ ehrlich dokumentieren, dass die Anschrift nur zur Laufzeit getauscht wird. | mittel (Parsing, JSON-LD-Felder) | ja | gelesen |
| W-33 | 6 Robustheit | `src/components/InquiryForm.astro:46` (`data-mail`), `src/scripts/form.ts:224,247`, `src/scripts/contact.ts:73-85` | Der mailto-Fallback (503/Netz weg) geht an `contactEmail()` **aus dem Build**. `contact.ts` tauscht `data-mail` nicht, und `fail()` setzt `href` neu, womit auch ein bereits getauschter Link überschrieben wird. Ohne ERP-E-Mail im Build ist das die Altadresse `fahrzeug-kranbau@hs-steiner.ch`. | In `contact.apply` auch `[data-mail]` tauschen, oder `mailto()` die Adresse aus dem bereits getauschten Footer/`a[href^=mailto]` lesen lassen | niedrig | ja | gelesen; `dist/_shell/shell.json` → `contact.email = fahrzeug-kranbau@hs-steiner.ch`. **Zu prüfen**: ist die Altadresse noch zustellbar? |
| W-34 | 6 Robustheit | `src/scripts/form.ts:68` | `fetch(form.action, …)` ohne `AbortController`. Ein hängendes Backend lässt das Formular „busy“ (Knopf gesperrt), bis die Plattform abbricht. | Timeout (z. B. 30 s) → `fail(…, 0)` mit Telefon/mailto | niedrig | ja (nur im Fehlerfall) | gelesen; zum Vergleich `contact.ts:46-49` mit 4 s |
| W-35 | 6 Robustheit | `website/scripts/export-shell.mjs:23` | Importiert `postcss`, das nicht in `website/package.json` steht. Es kommt nur transitiv über Astro/Vite (`package-lock.json:3790`). Ein Astro-Update ohne PostCSS bräche den Shell-Export und damit jeden Deploy (`SHELL_REQUIRED=1`). | `postcss` als devDependency mit fester Version eintragen | niedrig | nein | `grep postcss package.json` → nichts |
| W-36 | 6 Robustheit | `scripts/check-content.mjs:84-87`, CI `deploy-dev.yml` Job `website` | Der Build schreibt `OFFENE_PUNKTE.md` (versioniert), die CI prüft aber nicht, ob die Datei im Repo aktuell ist. Wer `photos.mjs` ändert, ohne lokal zu bauen, hinterlässt einen veralteten Bericht. Ausserdem verändert jeder lokale Build das Repo. | Wie bei `export-contact --check` einen `--check`-Modus bzw. `git diff --exit-code website/OFFENE_PUNKTE.md` in der CI. Alternativ die Datei nicht versionieren (gitignore). | keins | nein | Skript gelesen, CI gelesen |
| W-37 | 6 Robustheit (Naht) | `export-contact.mjs` ← `site.mjs:24-32` | Die exportierte `website_contact.json` hängt davon ab, ob lokal gerade `src/config/erp-contact.json` liegt (nach einem Build mit `SITE_API`). Dann landen ERP-Nummer/-Adresse im Export, und `export-contact --check` in der CI (ohne die Datei) schlägt fehl. Inhaltlich ist der Fallback des Backends (503/429-Seite, mailto) die **Vorgabe aus site.mjs**. Das ist richtig, denn er muss ohne DB funktionieren, ist aber nirgends so benannt. | Export aus den reinen Vorgaben bauen (erp-contact.json ignorieren) und den Zweck „DB-freier Fallback“ in contact.py nennen | niedrig | nein | Code gelesen, Ablauf nachvollzogen; **nicht** ausgeführt |
| W-38 | 6 Robustheit | `export-shell.mjs:33-38` | Kopf und Fuss werden per nicht-gierigem Regex `<header class="site-header…</header>` aus `404.html` geschnitten, und `contact` wird nur von `&quot;` dekodiert. Heute in Ordnung (genau ein `<header>`/`<footer>`), aber ein verschachteltes `<header>` (z. B. in einem künftigen Seitenkopf-Bauteil) schnitte still falsch. | Zählprüfung ergänzen: genau ein `<header`/`</header>` in 404.html, sonst Abbruch | keins | nein | `grep -o "<header\b\|</header>" dist/404.html` → je 1 |
| W-39 | 5 Vereinfachung | `dist/_shell/shell.*.css` (109 KB roh / 18 KB gzip) | Das ERP lädt das **komplette** Website-Stylesheet (alle Seiten-Stile, `cssCodeSplit:false`), nur für Kopf und Fuss. | optional nur die Regeln exportieren, deren Klassen in Kopf/Fuss-HTML vorkommen (PurgeCSS-artig, im selben PostCSS-Lauf). Gewinn klein, Risiko: dynamisch gesetzte Klassen (`is-open`, `menu-open`). | mittel | nein | `wc -c`, `gzip -c \| wc -c` |
| W-40 | 7 Doku | `website/WEBSITE_REPORT_20261003.md` (255 Z.), `WEBSITE_REPORT_20261004.md` (226 Z.) | Beide Berichte beschreiben überholte Stände (Sonderlösungen, Notfallnummer 076…, Servicezeile, SMTP, „125 offene Punkte / 157 Markierungen“). CLAUDE.md verweist auf 20261004 für die **Start-Checkliste**, die u. a. `INQUIRY_SMTP_*` verlangt; das liest kein Code mehr (Versand jetzt über das ERP-Postfach). | Beide nach `docs/history/` verschieben. Die Start-Checkliste als kurze, gültige Liste herausziehen (z. B. `website/START.md` oder in den Plan) und den CLAUDE.md-Verweis anpassen. | keins | nein | `grep -c` auf Altbegriffe (Tabelle oben: SMTP 3×, Servicezeile 9×, Notfallnummer 5× in R04); `grep -rn INQUIRY_SMTP backend .env.example` → 0 |
| W-41 | 7 Doku | `website/WEBSITE_PLAN.md` (872 Z.) | Eine Chronik von 124 Entscheiden, viele durch spätere abgelöst (8→22/36 Logo, 9→32 Platzhalter, 16→48 Testnotizen, 39→60 Kopf/Fuss, 73→83→97→105→120 Kranservice, 75→84, 77→85, 79→86, 110–115→119). §3/§7.8 nennen veraltete Dateien (`frontend/src/lib/site-shell.json`, „drei Schlüssel“ statt vier). | Eindampfen auf **geltende** Entscheide (ein Satz + Datei), die Chronik nach `docs/history/` | keins | nein | Gliederung per `grep -n "^[0-9]\+\. "` gelesen |
| W-42 | 7 Doku | `website/AUFTRAG.md` (843 Z.) | Der Auftrag im Wortlaut (Fassung 2), in zentralen Punkten durch den Strategie-Auftrag Oktober (Entscheid 119) und spätere Rückmeldungen überholt (Sonderlösungen 17×, Notfallnummer 10×, Einsatzgebiet 9×, Öffnungszeiten 3×). CLAUDE.md empfiehlt, ihn als Zweites zu lesen. | Als Wortlaut behalten, aber nach `docs/history/` verschieben bzw. oben deutlich „überholt durch WEBSITE_PLAN §…“ vermerken. Die CLAUDE.md-Leseanweisung kürzen. | keins | nein | `grep -c` |
| W-43 | 7 Kommentar | `site.mjs:5-9`, `:115`; `layouts/Base.astro:3-7`; `astro.config.mjs:6`; `photo-samples.mjs:10`; `track.ts:6-7`; `form.ts:237`; `deploy-prod.yml:137`; `deploy-dev.yml:143` | Veraltete Kommentare: „Öffnungszeiten“; „Kopf/Fuss … über export-contact“ (heute export-shell); Logo-Kommentar über `legalName`; Base: „Markierungen sichtbar, Hinweisbalken oben“, „Kopfzeile mit Servicezeile“; „siehe README.md“ (Datei fehlt); „trägt sichtbar das Wort Beispielbild“ (#1194 entfernt); Ereignisse `pikett_click`/`abo_interest`; „jede Markierung erledigt“; „Die E-Mails des Formulars schreibt das Backend mit den Wörtern der Website“ (nur noch die Bestätigung). | nachziehen | keins | nein | gelesen; `ls website/README.md` → fehlt |
| W-44 | 6 Robustheit | `OFFENE_PUNKTE.md` (Spalte „Verwendet auf“) | Fotos aus dem Kopf-Dropdown (z. B. `pruefung-hallenkran`, `team`, `werkstatt-aussen`) werden mit **allen 21 Seiten** gelistet, weil der Kopf auf jeder Seite steht. Damit taugt die Spalte für den Fototag nichts. | In `check-content.scanDist` Treffer innerhalb `<header class="site-header` ausnehmen oder als „Menü“ zusammenfassen | keins | nein (nur Bericht) | OFFENE_PUNKTE.md gelesen |
| W-45 | 3 Doppelung | `text.mjs:21`, `astro.config.mjs:10`, `check-site.mjs:21`, `check-content.mjs:18` | Der Modus (`SITE_MODE`) wird an vier Stellen gelesen und zweimal validiert. | Skripte `siteMode()`/`isLive()` aus `text.mjs` importieren lassen (check-content importiert `site.mjs` ohnehin) | keins | nein | gelesen |

Bewusst **nicht** als Befund aufgenommen (geprüft, ist in Ordnung):

- `style-src 'unsafe-inline'` in der Website-CSP: wird gebraucht, die eingebetteten SVG-Szenen
  tragen `style=""` (`grep -c 'style="' dist/index.html` → 5).
- Die `.ph`-Platzhalter-Fläche in `Photo.astro` lebt noch, für `hafen-bootskran` auf
  `/krantechnik/krane-nach-mass`. Sie ist kein Rest der gelben Vermerke, sondern der
  dokumentierte Weg für ein fehlendes Foto.
- Alle Komponenten, Layouts, Skripte und `public/`-Dateien haben mindestens einen Leser
  (Import-Zählung je Datei; `public/logo/*`, `public/og/*`, Favicons geprüft).
- Die spiegelnden Account-Schlüssel (`account.ts` ↔ `frontend/src/lib/account-cache.ts`)
  sind getestet (`scripts/account.test.mjs`), also beabsichtigt.
- `frontend/src/app/not-found.tsx`: das exportierte `404.html` wird von der Website ersetzt,
  die Komponente dient aber auch dem clientseitigen `notFound()`. Gehört zum Frontend-Agenten.

## Vorschlag Paketierung

1. **Paket A: „Tote Teile“ (ein Commit, keine Verhaltensänderung).** W-02, W-03, W-05, W-07
   (nur `service.photo`/`overview`), W-08, W-09, W-11, W-12, W-13, W-14, W-16, W-17, dazu W-10
   inklusive neu erzeugtem `website_contact.json` (CI `--check` grün). Prüfen: `npm test`,
   `npm run check`, `npm run build` (vergleichen, ob `dist/` ausser Hashes gleich bleibt),
   Backend `test_contact.py`.
2. **Paket B: „Kommentare und Doku“.** W-43 (Kommentare), W-40 bis W-42 (Berichte und Auftrag
   nach `docs/history/`, Plan eindampfen, Start-Checkliste neu und gültig, CLAUDE.md-Verweise
   anpassen). Das berührt keinen Code.
3. **Paket C: „Eine Liste“.** W-20 (ERP-Pfade), W-22 (Regexe ins Vokabular), W-23 (Labels und
   Name im Backend aus VOCAB), W-45 (Modus), W-28 (Schlüsselname), W-27 (Skriptname).
   Kleine Diffs auf beiden Seiten der Naht, die CI prüft den Export.
4. **Paket D: „Fachliche Entscheide, dann aufräumen“** (vorher den Nutzer fragen). W-01
   (Team-Schalter: entfernen oder wirksam machen), W-06 (Tracking-Haken lassen oder raus),
   W-15 (unbenutzte Bildstellen), W-21 (Ortsangaben auf Tokens), W-25 (Wort
   „Einsatzgebiet“), W-26 (`/shop`), W-24.
5. **Paket E: „Robustheit“** (Verhaltensänderung, einzeln testen). Zuerst **W-30** (Prod-Rewrite, hoch,
   vorher Infrastruktur prüfen), dann W-31 (Header-Block), W-33 (mailto-Adresse), W-34
   (Timeout), W-35 (`postcss` deklarieren), W-36 (OFFENE_PUNKTE in der CI), W-37, W-38. Später
   und optional: W-32 (Anschrift aus dem ERP auch beim Build), W-39 (Shell-CSS verschlanken),
   W-44 (Bericht).
