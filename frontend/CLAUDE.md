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

**Die Leiste IST das Bedienelement – und sie nennt, was sie zeigt** (Testnotiz #789).
Die Farbe allein kann es nicht: der Katalog kennt **drei** Ampeltöne für **sechs**
Zustände eines Stücks (*Freigegeben*, *Verbaut*, *Verkauft* sind alle grün). Zwei
gleichfarbige Segmente nebeneinander sind darum strukturell nicht unterscheidbar – also
stehen Punkt, Wort und Menge **unter der Leiste, als Teil von ihr** (`StockBar`), eine
Haarlinie trennt die Segmente, und ein Klick öffnet **genau einen** Ausschnitt darunter.
Die frühere Liste aufklappbarer Sektionen ist damit entfallen: ihr Kopf sagte Zeile für
Zeile das, was die Leiste eine Zeile höher schon zeigte, nur zwanzigmal höher. *Kein
Rückschritt hinter #716 – dort wurde eine Legende **neben** den Gruppen entfernt, also
die Doppelung; hier bleibt nur noch eine Fassung übrig.*

**Und die Ansicht zählt keinen einzigen Status auf.** Welche Segmente es gibt, sagen die
gelieferten `states`; Reihenfolge = Position im `CATALOG` (= Lebenszyklus), Farbe =
Ampelton. Ein neuer Zustand erscheint ohne eine Zeile Änderung an seiner Stelle. Ein
Zustand ohne Zuordnung wird **gemeldet**, nicht geraten. **Keine Gesamtzahl im Kopf** –
sie summierte auch Verschrottetes.

Karte + Kopf + Werteraster kommen aus `fields.tsx` (`SPEC`, `SpecHead`, `SpecSection`,
`ReadField`) – die Anatomie **jeder** Detail-Ansicht.

**Und die Leiste selbst kommt aus `module-ui.ValueBar`**: `StockBar` ist ihre Ausprägung
für Zustände von Einzelinstanzen und trägt nur noch, was wirklich am Bestand hängt – die
Übersetzung eines Zustands in Farbe und Wort. Die Frage «wie teilt sich ein Ganzes auf,
und welchen Teil sehe ich mir an» ist nicht die des Bestands; die Stufen eines Moduls
stellen sie ebenso.

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

- **Der Einkaufs-Block hängt an `buys`, nicht am Modultyp** (#777). Zugelassene
  Lieferanten und Auftrag an den Lieferanten gehören dem **Beleg**; jedes Modul, das
  einkaufen kann, bekommt sie – und ob sie Pflicht sind, sagt derselbe Katalog-Eintrag
  (`suppliers_required` / `instruction_required`). `MODULE_FIELDS` trägt darum
  `beschaffen: null`: ausser seinem Beleg hat es nichts zu konfigurieren. Ein neuer
  einkaufender Typ bekommt den Block, ohne dass jemand diese Datei anfasst.
  **Was abgeleitet ist, steht als Auskunft da, nicht als Vorschlag im Feld**: beim
  Bewegen heisst das Feld «Ergänzung zum Auftrag», weil «Transport von A nach B» schon
  daneben steht – eintippbar wäre es die zweite Aussage über dieselbe Sache.
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

## Beschaffen und Verkauf — ENTFERNT
Beide Module und ihre Beleg-Karte (`purchase-work.tsx`) sind gelöscht, nicht abgeschaltet.
Was sie konnten, kann der **Beleg** (`beleg-work.tsx`) – nur ohne die Bindung an
Ware, und damit auch für Miete, Lohn, Gebühr und eine eingekaufte Spedition. Zwei Karten
für dasselbe Geschäft laufen beim ersten neuen Verb auseinander.

Mit ihnen entfallen aus `lib/modules.ts`: `FLOW`, `flowOf`, `STAGE`, `HAULAGE`,
`MANUAL_METHODS`, `SupplierRule` und die Entwurfsfelder `suppliers`/`instruction`; aus
`order-detail.tsx` die Bauteile `Wrapped` und `ProcurementBlock`. Die **Symbole** der
beiden Richtungen (Handschlag ↔ Einkaufswagen) leben in `DEAL_DIRECTION` weiter – eine
Zuordnung mit genau einem Leser ist keine.

*Eine Runde lang trat «Ausliefern» an ihre Stelle – ein Scan, ein Statuswechsel. Auch
das ist entfernt: was physisch geschieht, sagen die Module, die es tun. `MODULE_FIELDS`
und `MODULE_FORM` kennen den Schlüssel nicht mehr; `null` bleibt als Wert erlaubt (er
heisst «kennt ihn, hat aber nichts zu fragen»), nur trägt ihn heute niemand.*

## Datum und Uhrzeit (`lib/when.ts`)
►►► **EINE Datums-Ausgabe für das ganze System** (Testnotiz #992). ◄◄◄ Vorher sieben:
`localDate`, `localDateTime`, drei eigene Helfer im Beleg (`daysUntil`/`relative`/`since`)
und je ein `toLocaleDateString` an Benutzer, Profil und Passkeys – dieselbe Angabe las
sich an fünf Stellen anders.

- **`when()` sagt, WANN es war** – die Aussage: heute die Uhrzeit · «Gestern» · «vor 3
  Tagen» · «13. Sep.» · «13. Sep. 2025» · «Morgen» · «in 5 Tagen». Für alles, wo ein
  Zeitpunkt eine **Auskunft** ist (Log, Angebote, letzter Login, angelegt/geändert).
- **`day()` sagt, WELCHER TAG auf dem Papier steht** – die Tatsache: Rechnungs-,
  Leistungs- und Fälligkeitsdatum, ein Eintrittsdatum. Auf einem **Beleg** ist «vor 3
  Tagen» keine Angabe. *Zwei Formen einer Regel, ein Modul, ein Namensstamm.*
- **`formatWhen()` gibt beides** (Text + `title`), damit eine Aufrufstelle den Hover
  **nicht vergessen kann**: eine Aussage ohne ihre Tatsache ist eine Zahl, die niemand
  nachprüfen kann.
- **Die Wörter stehen im Modul, nicht im ICU.** `toLocaleDateString('de-CH', {month:
  'short'})` liefert je nach ICU-Fassung «Sep.» oder «Sept.» – dieselbe Falle wie beim
  Tausender-Trenner in `formatAmount`. Ein Wächter verbietet jede zweite Formatierung.

## Bezahlen (`components/erp/pay-online.tsx`)
**Die Bezahlkarte ist unsere** – kein Zahllink, keine fremde Seite. Vom Dienst kommen nur
die **Eingabefelder** (ein *Payment Element* in einem iframe), und das ist ihr Sinn: so
berührt keine Kartennummer unseren Server. Das **Aussehen kommt aus unseren Tokens**
(`getComputedStyle` liest die CSS-Variablen), nicht aus einer geratenen Farbliste.

- **Das SDK kommt erst auf Klick** (`await import('@stripe/stripe-js')`) – dieselbe Regel
  wie beim Decoder des Scanners: was niemand öffnet, kostet niemanden etwas. Kein
  React-Wrapper: das Element wird in ein `<div>` gemountet, das sind vier Zeilen.
- **Was das ERP weiss, fragt die Karte nicht** (`fields: 'never'`) – **und liefert es
  dann auch mit** (`payment_method_data.billing_details`). Die beiden Hälften gehören
  zusammen: wer nur die eine schreibt, bekommt eine Ablehnung, und zwar erst beim
  Bezahlen. Fehlt eine Angabe, fragt das Element sie.
- **Die Felder tragen UNSERE Anatomie** (#892): `labels: 'above'`, 13 px, unsere
  Polsterung – im Haus steht die Beschriftung über der Eingabe, nie schwebend darin.
- **Die Rechnungsnummer steht nicht zweimal** (#891): die Karte klappt **unter** der Zeile
  auf, an der die Nummer steht. Mitgeliefert wird sie weiterhin – sie geht beim
  Zahlungsdienst in Beschreibung und Metadaten.
- **Sie schliesst, wenn die Zahlung ankommt** (#893): sie blieb stehen, weil niemand sie
  zumachte – `onDone` startete das Nachfragen, die Karte blieb an ihrer Rechnung. Jetzt
  endet sie an derselben Bedingung wie das Nachfragen, und **nur** dann: läuft es aus, ohne
  dass etwas kommt, bleibt sie stehen – sie hat ja nichts Falsches gesagt.
- **Sie sagt «ausgeführt», nie «gebucht»**: die Zeile entsteht, wenn der Webhook sie
  meldet. Ein Satz, der eine Buchung behauptet, die noch nicht dasteht, ist beim nächsten
  Blick eine Lüge. Danach wird der Auftrag **nachgeladen** (`onPaid` → `reload`) – das ist
  der einzige Weg im Detail, der keine Antwort auf einen Befehl ist.
- **Ob es den Knopf gibt, sagt `can`** (`pay_online`), nie eine Rollenabfrage – und die
  **Gegenpartei hat ihn ebenso**: dass der Kunde bei uns bezahlt, ist der Sinn der Sache.
  Sein **Wort** kommt vom Server (`pay_online_word`).

## Die Bauteile eines Moduls (`components/erp/module-ui.tsx`)
> **Das Zahlungsmodul ist das erste in dieser Sprache – alle weiteren folgen.** Damit sie
> es nicht ein zweites Mal erfinden, steht hier, was ein Modul *als Modul* ausmacht, und
> nicht, was ein Geldvorgang ist.

Es ist **kein neues Design-System**: jede Zahl kommt aus
`styles/design-system/colors_and_type.css`, jede Regel steht in
`docs/design-system/README.md`. Neu ist nur, dass sie **einmal** angewendet sind statt an
jeder Aufrufstelle mit leicht anderen Werten – die Lehre aus `MICRO_LABEL`.

| Bauteil | Was es ist |
|---|---|
| `MODULE_CARD` · `MODULE_TITLE` | Die Fläche und der Name – dieselbe Karte wie `SPEC.card` am Datensatz, nur mit der Polsterung einer schmalen Prozessspalte. Gesetzt wird sie in `ModuleShell`, also erbt sie **jedes** Modul. |
| `ModuleSection` | Abschnitt: Versalien-Beschriftung über einer Haarlinie – mit **Punkt davor**, wenn er sagt, wie weit er ist (`state`: `past · active · ahead`). **Leerer Titel = kein Kopf.** ►►► **Die Status-Spalte steht immer, auch leer** (#899): ein Punkt rückt die Beschriftung um seine Breite ein, und nur *manche* Abschnitte sind ein Schritt – gemessen 18 px ↔ 33 px im selben Beleg. Ein Punkt für alle wäre die falsche Lösung: er behauptete einen Fortschritt, den ein Inhalts-Abschnitt nicht hat. |
| `ModuleMeta` | Die leise Zeile für das, was über den ganzen Vorgang gilt (Richtung, Währung, Termin, Sperre). |
| `ValueBar` | **Ein Anteil an einem Ganzen** – Leiste, Punkt, Wort, Zahl; die Beschriftung ist zugleich das Bedienelement. |
| `Row` · `RowActions` | ►►► **Eine Zeilenaktion ist eine GATTUNG** (#989/#993). ◄◄◄ Die Korrekturen stehen am **Zeilenende**, im Ruhezustand unsichtbar, bei Hover und Fokus da – und auf einem Gerät **ohne Zeiger dauerhaft** (`.ix-row`/`.ix-rowactions` in `globals.css`, die Regel aus #832, jetzt für jede Zeile statt für eine). Sie belegen ihren Platz immer (`opacity`, kein `display`): erschienen sie erst beim Zeigen, verschöbe die Zeile ihren Inhalt unter dem Zeiger. ►►► **Und ihre Knöpfe klappen ihren Namen NICHT aus – gemessen.** ◄◄◄ In der echten Geld-Zeile bei 375 px steht der Knopf beim Zeigen nicht still (`313/48 → 329/32 → 317/44 → …`); die Entscheidung trifft darum die **Zeile** (`InRow`-Kontext), nicht die Aufrufstelle – als Angabe je Knopf wäre sie eine Regel, die der erste Neue vergisst. Der Name steht dann in der Blase, die am Layout nichts ändert. |
| `ConfirmButton` | **Was nicht rückgängig zu machen ist, fragt einmal nach** – derselbe Knopf, ein zweiter Klick, das Wort daneben; die Frage schliesst sich von selbst (ein stehender Zustand müsste weggeklickt werden). Kein Dialog: die Rückfrage gehört an die Zeile, an der sie entsteht. |
| `FIELD_GAP` | Der Abstand zwischen zwei Feldern einer Formular-Zeile (#987/#990). **Unter** der Beschriftung gibt es keinen: `fields.Label` bringt seine 4 px mit, und ein `gap` daneben kommt obendrauf – genau das waren die 7 px, die gemeldet wurden. |
| `ACT_H` · `MODULE_GRID` | Knopfhöhen und Werteraster an einer Stelle statt als `style={{height: 30}}` an dreissig. |
| `ActionButton` · `Actions` | ►►► **Ein Knopf ist ein Symbol, und beim Zeigen klappt sein Name DANEBEN auf** (#877–#896, #900). ◄◄◄ Acht Notizen, ein Satz – also **ein** Bauteil und **eine** Geste: `.ix-tuck` in `globals.css`, von der die Modul-Palette (`.ix-palette`) die getönte Ausprägung ist. Ein Anlauf lang stand der Name in der Blase, weil ein wachsender Knopf in einer **umbrechenden** Zeile schwingt (gemessen 32 → 63 → 51 → 59 px in 800 ms, mit kippendem `:hover`) – #900 hat das zu Recht zurückgewiesen: die Antwort ist nicht, die Geste aufzugeben, sondern **Platz** zu geben. `Actions` ist eine Zeile mit `flex-wrap: nowrap`; wo sie in einer umbrechenden Zeile steht, bekommt sie zusätzlich `flex: 1 1 100%` (eine eigene Zeile, **linksbündig** – rechts angeschlagen wanderte die Gruppe beim Aufklappen unter dem Zeiger weg). Gemessen dann: **148 px, acht Messungen lang unverändert**, bei 1440 · 375 · 320 px. Der **Grund** hängt an einer Hülle, nicht am Knopf: `.ix-tuck` ist `overflow: hidden`, und das schneidet ein `::after` weg (#790). |

- ►►► **Die Karte ist weiss – wie jeder Datensatz im Haus.** ◄◄◄ Sie war getönt, Rahmen
  **und** Fläche in der Modulfarbe; bei fünf Modulen untereinander standen fünf farbige
  Blöcke in der Spalte, und die ERP-Regel lautet **Struktur vor Fläche**. Die Modulfarbe
  verschwindet nicht, sie bekommt einen **Ort**: die 34-px-Marke, wo sie das Modul
  *benennt* statt es zu übertönen – und den Rahmen, wenn das Modul **dran** ist. Das ist
  die einzige Stelle, an der die Karte Farbe trägt, und sie sagt damit genau eine Sache.
- ►►► **Die Leiste steht EINMAL** – `StockBar` ist ihre Ausprägung für Zustände von
  Einzelinstanzen. «Wie teilt sich ein Ganzes auf, und welchen Teil sehe ich mir an» ist
  nicht die Frage des Bestands: die **Stufen** eines Moduls und die Aufteilung *bezahlt ·
  offen · nicht berechnet* eines Geldvorgangs sind dieselbe Aussage mit anderen Segmenten.
  Alle Regeln von dort gelten unverändert (Beschriftung gehört zur Leiste #789, Haarlinie
  als `border` statt `gap`, kein Filter).
- **`dim` gilt dem Bestand**: dort treten die anderen Segmente zurück, sobald man eines
  ansieht – das ersetzt einen Filter.
- ►►► **Eine Stufen-LEISTE gibt es nicht** (Testnotiz #868). ◄◄◄ `ModuleSteps`/`ALL_STEPS`
  standen hier und waren ein **Bedienelement** – man wechselte damit zwischen den
  Schritten. Seit alles untereinander steht (#863) hatten sie keinen Handler mehr, und was
  blieb, war eine waagrechte Zeile mit denselben Wörtern wie die Abschnitte darunter:
  *«mir passt das da oben nicht»*. Der Verlauf steht jetzt **an** den Abschnitten
  (`ModuleSection state`) – von oben nach unten gelesen ist das die vertikale Fassung
  derselben Aussage. `ValueBar` bleibt beim **Anteil an einem Ganzen**; drei Schritte sind
  keiner, und dass sie als drei **gleich breite** Segmente dastanden, sagte es bereits.
- **Die Stand-Wörter heissen `past · active · ahead`, bewusst nicht `done`/`open`:** das
  sind die Wörter, mit denen ein *Modul* seine eigenen Stufen benennt (`DEAL_STAGE.done`)
  bzw. eine Leiste sagt, welcher Abschnitt **offen** ist. Ein Wort, das in derselben Datei
  zwei Dinge meint, ist die Form, in der ein Vergleich still falsch wird.

## Zahlung, der Vorgänger (`deal-work.tsx`) — ENTFERNT

►►► **Ersatzlos gelöscht** (Testnotiz #960). ◄◄◄ *«Dieses Prozessschrittmodul kann
vollständig und gänzlich aus dem Code eliminiert werden wie bereits geplant.»*

Es war ein **Löschen**, kein Umbau – und genau dafür wurde sein Nachfolger **neben** ihn
gebaut statt in ihn hinein: gefallen sind `deal-work.tsx`, fünf API-Methoden
(`updateDeal` · `searchDealParties` · `dealTransfer` · `preparePayment` ·
`refundPayment`), `runDeal` in `order-detail`, die `DealEmbed`-Typen, der
`zahlung`-Eintrag in `MODULE_FORM`/`MODULE_FIELDS`/`MODULE_ICON` und 54 Wächter, die
seine Form prüften. Am **Beleg** keine Zeile.

Mit ihm ging sein letzter Aufrufer von `fields.TermField` – eine Frist ist ein **Wert**
auf dem Beleg, keine Knopfreihe (#934). `Segmented` bleibt: es ist die Form für eine
Aufzählung mit wenigen Werten im **Formular** (die Zahlungsart beim Buchen, #967).

**Seine Prosa liegt in `docs/history/2026-09-zahlungsmodul-vorgaenger.md`** – darin
stecken fachliche Entscheidungen, die weiter gelten (warum eine Gutschrift eine negative
Rechnung ist, warum ein Storno seinen Weg behält, warum die Währung an den Betrag
gehört). Hier stand sie als Beschreibung eines Systems, das es nicht mehr gibt.

## Zahlung (`components/erp/beleg-work.tsx`)
►►► **Die Karte ist von der ersten Zeile an ein BELEG** (`docs/neuaufbau-zahlungsmodul.md`,
PROCESS_CORE §9.15). ◄◄◄ *Belegkopf → Positionen → Konditionen → Angebote → Rechnung &
Zahlung.* Der Vorgänger entstand als Modulkarte und wurde über #847 · #899 · #913 dorthin
umgeformt – drei Runden für eine Einsicht; **er ist gelöscht** (#960, siehe oben).

- ►►► **Ein änderbarer Wert trägt EINE Auszeichnung** (#922, `.ix-editable` in
  `globals.css`, Hülle `Editable`). ◄◄◄ *«Es soll so ausschauen wie der finale Beleg, nur
  eben gehighlighted … ACHTUNG: Ich will das auch für alle anderen Angaben auf dem
  Beleg.»* Eine Haarlinie in der leisen Stimme des Hauses, als `inset box-shadow` und
  damit **ohne Layoutwirkung** – Grösse, Form und Schrift bleiben, wie der Nutzer es
  verlangt hat (gemessen: Δb 0.00 · Δh 0.00 · Δx 0.00 px). Sie tragen: Währung ·
  Zahlungsfrist · Lieferfrist · Lieferbedingung · Preis · MWST · Zolltarifnummer ·
  Ursprungsland · Gegenpartei.
  **Und die Felder verloren ihren Rahmen** (`DOC_FIELD`): ein gerahmter Eingabekasten ist
  die Form eines *Formulars*, und ein Beleg ist keines. `inputCls` bleibt richtig, wo man
  wirklich ein Formular ausfüllt – im Editor und beim Buchen einer Geld-Zeile.
  **Nach der Zusage steht der Beleg fest**, und dann trägt **nichts** mehr die
  Auszeichnung: eine Linie, die Änderbarkeit verspricht, wäre dort eine Unwahrheit.
- ►►► **Die Handlung, die weiterbringt, sieht überall gleich aus** (#923, `StageAction`).
  ◄◄◄ *«Kann dieser Button so gross und ausdrucksstark werden wie ‹Vorgang abschliessen›
  am Schluss? Eine UI-Logik.»* – Volle Breite, Fläche, 42 px, 14 px Schrift: buchstäblich
  die Masse des Knopfes, der jedes Modul beendet (`order-detail`). Ein Sonderfall für
  einen Knopf wäre die Stelle, an der der nächste wieder anders aussieht.
- **Jede Zahl, die man abschreibt, nennt ihre Währung** (#921): Netto, Steuer je Satz,
  Total, offener Betrag, jede Geld-Zeile. **Nicht** an jedem Einzelpreis – dort stünde
  dasselbe Wort zwanzigmal. Die Währung selbst **ist** der Wähler (der Code am Total, ein
  unsichtbares `<select>` darüber).
- **Keine Überschrift «Konditionen»** (#926) – die drei Zeilen darunter sagen selbst, was
  sie sind. Und **keine Vorauszahlungs-Pille im Kopf** (#924/#925): ob vorausbezahlt wird,
  sagt die **Zahlungsfrist** eine Zeile tiefer, wo man sie ändert.
- **Kein einziges `if` auf die Richtung**: `label`, `ask_verb`, `we_quote`, `ref_label`,
  `stages[].label/verb` reisen fertig mit; die Karte kennt weder «Kunde» noch «Lieferant».
  Ein Wächter zählt es.
- **Die beiden Zahlungsmodule teilen keine Zeile** – eigene Komponente, eigene
  API-Methoden (`updateVoucher` · `prepareVoucherPayment` · `voucherTransfer` ·
  `refundVoucherPayment` · `searchVoucherParties`), eigener Endpunkt. Die **Definition**
  teilen sie dagegen sehr wohl: `MONEY_FORM` in `lib/modules.ts` steht einmal und wird
  zweimal referenziert – beim Löschen des alten Moduls fällt genau **eine Zeile**.
- **Symbol gleich, Farbe anders**: es ist dasselbe Modul in einer besseren Datenform, also
  dasselbe Zeichen (`HandCoins`) – was sie unterscheidet, ist der `tone` vom Backend
  (`plum` ↔ `rose`).

### Ein änderbarer Wert hat EINE Form (#929/#930/#934/#935)
`DocPick` (eine Aufzählung) und `DocRef` (ein Datensatz) sind die zwei Hüllen, beide auf
`Editable` gebaut. **Sichtbar ist ein `<span>` in der Schrift, die dort ohnehin steht;
bedienbar ein unsichtbares Bedienelement darüber** – die Lösung, die die Währung hatte,
jetzt als Regel für jeden Wert des Belegs.

Das ist zugleich der Fix von #935: ein natives Auswahlfeld nimmt die Breite seiner
**längsten Zeile** («DPU · Geliefert entladen»), und daneben sass der Pfeil scheinbar
eingerückt – gemessen **229 px → 13 px**. Damit ist auch der Stift-Knopf am Aussteller
entfallen (#929) und die Frist wieder ein Wert statt einer Knopfreihe (#934); `TermField`
kommt in dieser Datei nicht mehr vor. Die freie Eingabe steht an **derselben** Stelle.

- **`vatText` ist die eine Auflösung** (#932): Name **und** Prozentsatz. «Normalsatz»
  allein sagt nicht, ob 8.1 oder 7.7 – und getrennt gebaut nennt die Liste den Satz und
  die Zeile daneben nicht.
- **Name und Objektnummer stehen in EINER Zeile** (#933); gekappt wird der Name, nie die
  Kennung (#853).
- **`numericOnly` nimmt eine Stellenzahl** (#931, `decimals?: boolean | number`), und das
  Preisfeld die des Vorgangs. Die Anzeige behebt der Dienst (`_money`) – dieselbe
  Zeichenkette steht gleich im Eingabefeld.

### Eine API-Methode behält ihren Client (#927)
`ApiClient` bindet im Konstruktor **über den Prototyp**. Vorher verlor jede Methode, die
als **Wert** weitergereicht wurde (`search={api.searchVoucherParties}`), ihr `this` –
`this.get` warf, der Fehler landete in der Konsole, und das Suchfeld blieb **stumm**.
Das war die Ursache von «kommt kein Vorschlag, nichts» und stand als Konsolen-Fehler
unter *jeder* Notiz dieser Runde. Am Aufrufer wäre es eine Regel, die man bei jedem neuen
`search={…}` erneut einhalten muss.

### Die Auszeichnung ist so gross wie das Feld (#948/#949)
►►► **Eine Box, nicht zwei.** ◄◄◄ *«Das gehighlightete Feld ist deutlich grösser als das
selektierbare Feld – ein design- und UX-technisches No-Go.»* Gemessen an der echten
Komponente: die alte Bauart hat **62** Stellen, an denen beides auseinander liegt
(«Zahlungsfrist Fläche 229×24 ≠ Feld 46×24»). Ursache ist ein Grundzug von Flexbox: in
einer **Spalte** wird jedes Kind blockifiziert und auf die volle Breite gezogen.

`Editable` ist darum `inline-flex` **mit `align-self: start`** (keine Streckung in beiden
Achsen), und `DocPick` setzt das Bedienelement mit `inset: 0` auf **dieselbe** Hülle – der
frühere Zwischen-`<span>` war die zweite Box. Auch `as="div"` ist ein Flex-Kasten: sonst
ist die Hülle so hoch wie ihre **Zeile** (24 px) und das Feld darin 19,5 px. Gemessen
danach: **76 Felder, alle deckungsgleich**.

**Und es ist eine Fläche, kein Unterstrich** (#949, `.ix-editable`): ruhend getönt, beim
Zeigen kräftiger – über eine `background` und einen **äusseren** `box-shadow`, damit die
Bedingung aus #922 gilt (Δb 0.00 · Δh 0.00, auch beim Zeigen). Polsterung hätte den Beleg
verschoben. Die Farbe kommt aus `--accent-soft`, nie als Zahl im Blatt.

### Der Empfänger ist wählbar, abwählbar – und zeigt seine Anschrift (#951/#952)
Ein **Beleg** hat einen Adressaten: einer steht vollständig da, ein Klick auf einen Chip
schaltet um. Die Seiten aller Angefragten reisen mit (`recipients`) – ein Endpunkt
«Anschrift zu Nummer» wäre ein zweiter Weg zu einer Angabe, die der Beleg ohnehin
liefert. **Welcher Block die Gegenseite ist, sagt der Server** (`VoucherSide.ours`); ein
Vergleich auf «Leistungserbringer» wäre ein Spiegel über die API-Grenze.

Der Chip trägt **zwei** Knöpfe in einer Hülle – der Name zeigt die Anschrift, das ✕ zieht
die Anfrage zurück (`unask`); verschachtelte Knöpfe wären ungültiges HTML. **Ob abgewählt
werden darf, sagt `can`.** Und wo eine eigene Rechnungsadresse hinterlegt ist, stehen
**zwei** Anschriften mit Beschriftung – nur dann: bei einer einzigen wäre
«Rechnungsadresse» eine Unterscheidung ohne Gegenstück.

### Die Fusszeile: der Abschluss, und der Storno daneben (#950/#957)
*«Wenn es die Option zum jetzigen Zeitpunkt nicht gibt, dann entfernen.»* Der gesperrte
Abschluss-Knopf ist **weg**, nicht ausgegraut (`order-detail`: `blocked ? null : …`) – das
ist #945 einen Schritt weiter, und was im Weg steht, sagt die Modul-Karte selbst. Der
**Storno** steht als 42 × 42-px-Quadrat daneben (`Footer`), der dominante Knopf nimmt den
Rest. Seine Breite kommt aus der CSS-Variablen `--actbtn-w`, nie inline: ein Inline-Wert
gewinnt gegen `.ix-tuck:hover { width: auto }`, und der Name klappte nie aus.

### «Jetzt bezahlen» fragt den richtigen Vorgang (#959)
`PayOnline` kennt **keinen** Endpunkt mehr – `prepare` kommt vom Aufrufer
(`api.prepareVoucherPayment` ↔ `api.preparePayment`), als **prototypgebundene** Methode:
eine dort gebaute Pfeilfunktion wäre bei jedem Rendern eine neue Referenz und liesse die
Vorbereitung endlos laufen. Vorher rief die Karte fest die Tür des **alten** Moduls; am
Beleg gab es dort keinen Vorgang (404), und der Knopf tat nichts. Stripe war unberührt.

**Und «Zahlung erfassen» gibt es nur AN der Rechnung** (#958): der Knopf am Vorgang wusste
nicht, welche gemeint ist, und wählte still die älteste offene.

## Bewegen (`components/erp/capture-work.tsx` in der Modul-Karte)
Ein Transport, den eine Spedition fährt, ist eine **Leistung, die man einkauft** – das
Bewegen-Modul trug dafür einmal den Einkaufs-Beleg samt Schalter «Selbst ↔ Beschaffen»
(`order-detail.Wrapped`). Mit dem Beleg ist beides entfallen: wer eine Spedition
beauftragt, legt einen **Geldvorgang** daneben. Das Bewegen-Modul weiss davon nichts
mehr; es bewegt.

- **Die Oberfläche fragt eine Eigenschaft, nie den Modultyp**: `step.moves` (Ziel-Scan?).
  Sie reist mit dem Schritt, wie Farbe und Beschriftung – den Modul-Katalog lädt nur der
  Editor.
- **Kein «womit».** Die Liste `manuell · paket · fracht` ist entfallen: *Paket* und
  *Fracht* sind zwei **Angebote** desselben Einkaufs, und das entscheidet der Tarif.
  `confirmStep` schickt keine Transportart mehr mit.

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
- ►►► **Die Vorschlagsliste hängt an `document.body`, nicht im Feld** (#909). ◄◄◄
  *«Wenn ich hier etwas suche und auswählen möchte, dann geht das nicht wirklich gut, da
  es von der Ebene her zu tief ist.»* – Als `position: absolute` **im** Feld lag sie in
  jedem Rahmen darüber: ein Vorfahr mit `overflow: hidden` schnitt sie ab, ein Nachbar
  mit eigenem Stapelplatz legte sich darüber (gemessen: die unterste Zeile traf das
  Modul darunter, der Klick ging ins Leere). **`z-index` hilft dagegen nicht** – er gilt
  nur *innerhalb* des Stapelkontexts, in dem das Element steht, und einen solchen macht
  jede Karte mit `transform`, `filter` oder eigenem `z-index` auf.
  Also verlässt sie den Baum: `createPortal` an `document.body`, `position: fixed` an der
  gemessenen Stelle des Feldes (`LIST_*` in `fields.tsx`). Damit gibt es **keinen
  Vorfahren mehr**, der sie schneiden könnte – konstruktiv statt geprüft.
  Drei Dinge gehören dazu und sind je eine Zeile: der Klick-daneben-Schliesser fragt
  **auch** die Liste (sie ist kein Nachfahre mehr – sonst verschwindet die Zeile, bevor
  der Klick auf ihr ankommt), `scroll` mit `capture: true` führt sie nach (auch innere
  Container), und am unteren Fensterrand klappt sie nach **oben**. Gemessen in Chromium:
  Portal an `<body>`, unterste Zeile anklickbar, Klick kommt an, Esc schliesst, Abstand
  beim Scrollen unverändert 4,0 px, Flip nach oben – und jede Prüfung gegen ihre
  Bug-Form gegengeprüft.
- **Und wo «nichts» heisst «das entscheidet sich erst am Band», ist der Satz geteilt**:
  `scan.RUNTIME_CHOICE` = «Beim Ausführen definieren» (#785/#786). Nicht «scannen» – das
  ist einer von zwei Wegen zur selben Wahl, und bei den zugelassenen Gegenparteien wird
  gar nicht gescannt; ein Wort, das den Weg nennt statt den Zeitpunkt, ist an der Hälfte
  der Stellen falsch. Ein **Erklärsatz darunter** («Leer: freie Wahl beim Ausführen») ist
  ersatzlos entfallen: das ist die eine Form, in der man die Wahl nicht wählen kann.
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

## Die Objektnummer ist eine Kennung, kein Hyperlink (`.erp-objid`)
Sie stand als blauer, unterstrichener Text da – die drei Marker, an denen man im Web
einen Link erkennt. Im ERP steht sie in fast **jeder** Zeile: das Raster las sich als
Linkliste, und die Kennung war die lauteste Angabe darin (Testnotiz #784). Im
Ruhezustand trägt sie darum die Farbe ihres Textes; dass sie führt, sagt der Zeiger und –
sobald er darauf steht – Farbe **und** Unterstreichung (Farbe allein ist kein
zugängliches Signal). Der Tastaturweg bekommt dieselbe Auszeichnung über
`:focus-visible`. Die **Form** bleibt die einer Nummer ohne Ziel (#282): `baseStyle` ist
geteilt, die Auszeichnung kommt allein aus der Klasse – inline greift kein `:hover`.

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

### Testnotizen #961–#974 — eine Ursache, zwei Symptome; und der Beleg wird ruhiger

- ►►► **Ein änderbarer Wert stört seine Zeile nicht** (#961/#963 – **EINE** Ursache). ◄◄◄
  *«Hier ist so ein komischer Höhenversatz zwischen Objektname und Nummer»* · *«auch hier
  ist so ein leichter Höhenversatz zwischen den Werten»* – zwei Meldungen, ein Grund:
  `Editable` trug `align-self: start`. Das beantwortet die **Streckung** in einer Spalte
  richtig und beantwortet zugleich eine **zweite** Frage, die es nicht beantworten darf:
  in einer **Zeile** ist die Querachse die senkrechte, und `start` heisst dort «oben» –
  die Hülle fiel aus dem `items-baseline` ihres Elternteils heraus. `width: fit-content`
  löst genau das eine Problem: eine **definite** Quergrösse schliesst `stretch` aus (CSS
  Flexbox §8.3), und in der Zeile bleibt die Ausrichtung die des Elternteils.
  **Und die Positionszeile richtet sich an der Grundlinie aus** statt mittig: Satz (12 px)
  und Preis (13 px) sind zwei Texte einer Zeile. Gemessen in Chromium mit einer
  Grundlinien-**Sonde** (ein leeres 0×0-`inline-block`, dessen Unterkante die Grundlinie
  ist): **Δ 0.00 px**, die Bug-Form 2 px. *Ein `Range` über einen Textknoten taugt dafür
  nicht – er liefert die **Zeilenbox**, und zwei Zeilenhöhen haben verschiedene
  Unterkanten, auch wenn die Grundlinien stimmen (gemessen: 3 px, davon 0 echt).*
- ►►► **Ein Pflichtwert, der fehlt, sagt es an SEINER Stelle** (#964, `Editable missing`,
  `.ix-editable.is-missing`). ◄◄◄ *«Alle Eingabefelder – alles, was so leicht blau
  hinterlegt ist – sollen Muss-Felder sein.»* «Leicht blau hinterlegt» **ist** die
  Auszeichnung änderbarer Werte, also gehört die Regel ihr und nicht neun Aufrufstellen:
  dieselbe Auszeichnung in einer anderen Stimme (warnfarben statt akzentfarben), Grösse
  und Schrift unverändert (gemessen Δb 0 · Δh 0 · Δx 0). Kein Sternchen daneben – eine
  zweite Form wäre eine zweite Aussage und bräuchte Platz, den ein Beleg nicht hat.
  **Die Regel selbst steht im Dienst** (`voucher._assert_complete`); dies ist ihre
  freundliche Hälfte, nie ein zweiter Massstab.
- ►►► **Die Gegenpartei: EINE Liste, EINE Form** (#962). ◄◄◄ Dieselbe Sache stand in zwei
  Formensprachen da – Chip mit ✕ ↔ `+ Name`-Knopf –, und der zweite trug `.ix-editable`:
  **jede** Partei sah dauerhaft «aktiv» aus. Jetzt ein Chip je **möglicher** Gegenpartei
  (zugelassen ∪ angefragt, `recipients` vom Server): Punkt (gefüllt ↔ hohler Ring), Name
  **zeigt die Anschrift** – auch bei einer noch nicht angefragten –, `+` fragt an, `✕`
  zieht zurück. **Und die Liste hängt nicht mehr an `ask`**: was man *tun* darf, sagt
  `can` je Chip; was man *sehen* darf, ist eine andere Frage.
- **Die Chronik ist weg, ihre Daten stehen an ihrem Ort** (#968/#969/#970): «vor 3 Tagen
  offeriert» am Kopf der Angebote, «vor 3 Tagen angenommen» an der Zeile mit dem Zuschlag,
  der Storno im Belegkopf. Die **Aussage** steht da, die **Tatsache** (Datum und Uhrzeit)
  im Hover – dieselbe Regel wie bei der Fälligkeit (#890).
- **Der Belegkopf nennt die Belegart, nicht den Zustand** (#974): «Erledigt» ist kein
  Beleg. `Direction.document_label` löst es im Backend auf – hier wird gezeichnet.
- **Der Satz steht vor dem Betrag** (#972): die Zahl ist die letzte Angabe der Zeile und
  bildet mit der darunter eine Spalte; dahinter verschob jede Satz-Beschriftung anderer
  Länge den Betrag.
- **Mehr Luft über jedem Abschnitt** (#971, `ModuleSection` 18 → 26 px) – der Abstand
  gehört der **Gattung**, nicht der Aufrufstelle.
- **Die Zahlungsart ist ein Schieber** (#967, `Segmented`): zwei Werte hinter einem Klick
  zu verstecken ist ein Klick für eine Entscheidung, die man sehen könnte.
- **Kleineres:** «Absage» ohne Zusatz (#965 – «liefert nicht» sagt an einer *Einnahme*
  sogar das Falsche); «Offerte annehmen» statt «Angebot annehmen» (#966, vom Server);
  ein Modul mit eigener Karte zeigt daneben **keine** `PointList` mehr (#973).
- **Gemessen in Chromium an der echten Komponente** (Karte im `ModuleShell`): 1440 · 1280 ·
  1024 · 834 · 375 · 320 px, **0 px** waagrechter Überlauf über **sechs** Beleg-Zustände –
  und die Messung gegen ihre eigene Bug-Form gegengeprüft (+46.7 px bei 375, +101.7 px bei
  320 mit einem unteilbaren Wort). *Ein Name in der Positionszeile taugt als Bug-Form
  nicht: er trägt `truncate`, wird also wirklich abgeschnitten – und eine Textbreite
  hinter `overflow: hidden` ist kein Überlauf.*

### Testnotizen #975–#978 — zwei Fragen, zwei Angaben; und die Blase steht über ihrer Auskunft

- ►►► **«Was ist zu tun?» ≠ «Wie bestellen?»** ◄◄◄ Der Editor (`MoneyFields`) fragt jetzt
  **zwei** Dinge: den Satz am Modul (`instruction`, freiwillig, `DEAL_TASK`) und je Partner
  die Bestellangabe (`DEAL_ORDER_REF`) – **nur, wo wir bestellen**
  (`DEAL_DIRECTION[…].partyRef`, gespiegelt von `Direction.party_ref`; der Dienst verwirft
  einen trotzdem gesendeten Wert, dies ist die freundliche Hälfte derselben Regel). Auf dem
  Beleg steht der Satz bei den **Positionen** – als **Auskunft**, nicht als Feld: entschieden
  wird er beim Modellieren. **Leer schreibt der Beleg nicht hin.**
- ►►► **Die dominante Handlung, daneben die leise** (`StageRow`, #976). ◄◄◄ *«Kann man
  diesen Bereich ähnlich darstellen wie ‹Vorgang abschliessen› und daneben das
  unscheinbarere Abbrechen?»* – Eine Handlung nimmt den Platz (`StageAction`, volle Breite),
  alles andere steht als 42 × 42-Quadrat daneben (`ActionButton square`). Es ist **ein**
  Bauteil: die Fusszeile der Karte und der Zuschlag an einer Angebotszeile sind dieselbe
  Zeile. **Welche die dominante ist, sagen die Daten** – annehmen, sobald ein Preis dasteht,
  sonst ihn erfassen. Gemessen: Absage 42 × 42 px, Δy 0,00, und der Knopf steht beim Zeigen
  über vier Messungen still (die Zeile bricht nicht um).
- ►►► **Die Blase steht über dem, was sie erklärt** (`Note`, #978). ◄◄◄ Sie sitzt über der
  **Mitte ihres Elements** – und das Element war die ganze Zeile: ein Kind einer
  Flex-**Spalte** wird blockifiziert und auf die volle Breite gezogen. `width: fit-content`
  ist die Antwort und **nicht** `align-self` (dieselbe Lehre wie bei `Editable`, #961/#963:
  eine definite Quergrösse wirkt in der Spalte *und* in der Zeile). Drei Aufrufstellen, ein
  Bauteil – wann offeriert, wann angenommen, wie bestellt; die Angabe zum Zuschlag steht
  dabei **neben dem Betrag** in der Kopfzeile der Angebotszeile. Gemessen: Box == Text,
  Δ 0,0 px; die Bug-Form meldet 1146 px.
- **Der Belegkopf nennt keine Belegart mehr** (#977): `d.stage_label` gibt es nicht, und die
  Auflösung dahinter ebenso wenig. **Der Storno bleibt** – er ist eine Tatsache über dieses
  Papier, keine Belegart.
- **Beide Anschriften auf beiden Seiten** (#975): `Party` reicht `address_label` und
  `shipping_label` nur noch **durch**; ob es eine Beschriftung gibt, entscheidet der Server.
  Die Wörter stehen nirgends als Literal in der Karte.
