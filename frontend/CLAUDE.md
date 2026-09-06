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
Was sie konnten, kann der **Geldvorgang** (`deal-work.tsx`) – nur ohne die Bindung an
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

## Zahlung (`components/erp/deal-work.tsx`)
►►► **Die Karte IST der Beleg — und sie WÄCHST** (Testnotiz #899). ◄◄◄ *Belegkopf ·
Positionen · Bedingungen · Rückläufe · Rechnung & Zahlungen · Handlungen*, in **beide**
Richtungen dasselbe. Was Einnahme von Ausgabe unterscheidet, **reist fertig mit**
(`DealEmbed.label`, `stages[].label/verb`, `party_word`, `ask_verb`, `charge_word`,
`money_label`, `stage_label`, `undo`) – die Karte braucht dafür **kein einziges `if` auf
die Richtung**; ein Wächter zählt sie.

- ►►► **Ein Dokument, kein Stapel von Blöcken.** ◄◄◄ Vorher war die Karte eine **Kette**:
  Positionen, Abschnitt «Angebot», Abschnitt «Auftrag», Geld – und mit der Zusage kam ein
  Block dazu (`Agreed`), der Partner, Summe und Fristen **noch einmal** zeigte, in anderer
  Reihenfolge als oben. Jetzt ist es **ein** Beleg in der Ordnung, die ein Beleg hat:
  **Kopf** (`DocHead` – Belegart · An <Partner> · Datum) → **Positionen** mit Summe
  (`Goods` → `Totals`) → **Bedingungen** (`Terms` – Währung und die beiden Fristen) →
  **Rückläufe** (`Offer` – der Angebotsspiegel) → **Rechnung & Zahlungen** (`Money`) →
  **Handlungen** unter einer Haarlinie, wie die Unterschrift.
- **Er wächst, statt umzuschalten**: der Kopf heisst nach der Zusage «Auftrag» statt
  «Angebot» und nennt den Empfänger, die Preisspalte trägt die gebuchten Zahlen statt des
  Entwurfs, die Bedingungen stehen als Auskunft statt als Feld, die Rückläufe klappen auf
  **eine** Zeile zusammen, und darunter kommt das Geld dazu. *Ein späterer PDF-Export ist
  damit dieselbe Komponente ohne Knöpfe.*
- **Jede Beleg-Angabe steht an GENAU einem Ort** (Empfänger · Zusagedatum · Zahlungsfrist ·
  Liefertermin · Steueraufteilung · Nettosumme) – gezählt, nicht behauptet. Und die
  **Summe** gibt es einmal (`Totals`): Vorschau aus getippten Preisen und gebuchte Zahlen
  des Servers sind dieselbe Aufstellung; zwei Bauteile wären zwei Schreibweisen für Netto,
  Steuer und Total.
- **Zusammengeklappt wird erst NACH dem Zuschlag** («1 von 2 Angeboten gewählt»): solange
  verhandelt wird, versteckt der Beleg nichts. Danach sind die unterlegenen Zeilen der
  **Nachweis**, warum so entschieden wurde – und der gehört auf Klick.
- **Die Zahlungsfrist steht über der Lieferfrist** (#897) – im Beleg wie an der
  Angebotszeile, und auch in deren **Anzeige**: sie ist die folgenreichere Angabe (aus ihr
  kommt die Fälligkeit, und null heisst Vorauszahlung), und zwei Formulare für dieselben
  zwei Fragen dürfen nicht anders herum fragen.

- **Zwei Stufen, und der dritte Schritt ist KEINE.** Unumkehrbar sind zwei Dinge: nichts
  zugesagt · zugesagt. «Abgeschlossen» stand einmal als dritte Stufe da und war genau das
  Missverständnis – ein **Zustand** in einer Reihe von **Schritten**. Der dritte Schritt ist
  das **Geld**: eine Zahlung macht aus einem Angebot keine Zusage, sie ist reversibel, und
  sie darf **vor** der Erfüllung stehen (Vorauszahlung) wie danach. Er steht dort, wo man
  ihn erwartet, und ist ab der Zusage bedienbar. Das Geld trägt darum auch **keinen
  eigenen Schlüssel** mehr: der Abschnitt nennt sich über `d.money_label` vom Server.
- ►►► **Der Verlauf steht AN den Abschnitten** (Testnotiz #868). ◄◄◄ *«Kann man diese
  Anzeige nicht vertikal machen und es so visuell etwas besser strukturieren – mir passt
  das da oben nicht.»* Über der Karte stand eine waagrechte Stufen-Leiste. Sie entstand als
  **Bedienelement** (#863 nahm ihr den Handler), und was blieb, war eine Zeile mit
  denselben drei Wörtern wie die Abschnitte darunter. **Die Abschnitte SIND die vertikale
  Fassung**: ein Punkt vor der Überschrift (`ModuleSection state`) sagt dasselbe an der
  Stelle, an der man den Namen ohnehin liest – vorbei (dunkel) · dran (Akzent) · steht noch
  aus (Haarlinie). Damit sind `ModuleSteps`, `ALL_STEPS`, die drei Schlüssel (`OFFER`,
  `AGREED`, `MONEY`) und `moneyValue` entfallen.
- **Der Angebotsspiegel ist der Kern der ersten Zeile** (`quotes`): je angefragter
  Gegenpartei eine Zeile mit Preis, Lieferfrist und Zahlungsfrist. **Wo niemand zugelassen
  ist, wird gesucht** (`ObjectSelect` + `api.searchDealParties`); wo genau einer steht, gibt
  es nichts zu wählen und der Knopf heisst schlicht `ask_verb` (#793).
- **Worum es geht, steht oben und ist abgeleitet** (`lines`) – Menge, Name, Objektnummer je
  Artikel; die **Spezifikation erst auf Klick**. Sie wird nicht getippt und nicht ausgewählt.
- **Die Knöpfe hängen an `can`** (`services/deal.ACTIONS`) – nie an der Rolle und nie an
  der Stufe: dieselbe Tabelle ist Auskunft **und** Tor. Eine **Gegenpartei** bekommt
  dieselbe Komponente; dass sie weniger sieht, entscheidet die **Antwort**, nicht die
  Oberfläche (`open == null` → die Geld-Zeile rendert nichts; wer nicht den Zuschlag hat,
  bekommt Name, Preis und Frist des Gewählten gar nicht erst geliefert).
- ►►► **Die Geld-Zeile hängt an `can`, nicht an «ist dieses Modul dran».** ◄◄◄ Bei einem
  **Zahlungsziel** ist es das längst nicht mehr, wenn das Geld kommt: gemessen erlaubte der
  Dienst Rechnung und Zahlung an einem abgeschlossenen Auftrag, die Karte bot **null**
  Knöpfe an – eine erfundene Sperre ohne Schlüssel. Die beiden **Stufen** behalten `active`:
  dort ist es richtig, man verhandelt nicht an einem Modul, das nicht dran ist.
- ►►► **Jeder Knopf trägt eine Ausprägung.** ◄◄◄ Ein blosser `.erp-actbtn` hat
  `border: 1px solid transparent` und keine Fläche – er **sieht aus wie Text**. Erst
  `-primary` (der Vorschlag) / `-neutral` (die übrigen) / `-danger` (Storno) machen daraus
  einen Knopf, `-icon` daraus ein Quadrat. Das war die Ursache von «die Buttons gefallen
  mir nicht», nicht der Geschmack.
- **Und «Weitere» gibt es nicht.** Ein Auswahlmenü ist die richtige Form für viele
  gleichrangige Dinge; hier waren es drei, und eines davon (der Storno) ist die
  Gegenhandlung des ganzen Vorgangs. **Was man jetzt tun kann, muss man sehen** – welches
  das naheliegende ist, sagt die Fläche des Knopfes, kein Klick, der es erst hervorholt.
- **Wo man steht, sagt die Zeile** – gefüllter Punkt in der Akzentfarbe, Beschriftung in
  Versalien. Punkt und Wort teilen dafür **eine** Zeilenhöhe (`HEAD_H`) statt zweier
  geratener Abstände (#798, gemessen: Δy 0,0 px).
- **Offerte und Absage sind Symbol-Knöpfe** wie im Beschaffungs-Beleg (#800): «Offerte»
  beschreibt einen *Zustand*, der Knopf löst eine *Handlung* aus.
- **Die Angabe «Was ist zu tun?» steht an SEINER Zeile** (`quote.ref`) – seine
  Artikelnummer, sein Shop-Link oder ein Satz; sieht sie aus wie eine Adresse, ist sie ein
  Link. Sie gilt in **beiden** Richtungen (#803): beim Einkauf sagt sie, wie man bei ihm
  bestellt, beim Verkauf, was er bekommt.
- **Gerechnet wird nichts im Browser** – *berechnet · bezahlt · offen · noch nicht
  berechnet* kommen vom Server. «Bezahlt» heisst «gefordert UND beglichen»; ohne die
  Unterscheidung stünde direkt nach der Zusage «Bezahlt» da, weil *offen* null ist.
- **EINE naheliegende Handlung, und der Server sagt welche** (`next_charge` ↔
  `next_payment`): erst fordern, dann kassieren. Die Rangfolge sagt die **Fläche** des
  Knopfes (`-primary` ↔ `-neutral`), nicht ein Umweg – alle stehen da.
- **Die Richtung ist ein SYMBOL mit Hover, kein Dauertext** (#797): Plus und Minus sind die
  Buchhaltungssprache selbst – ein Wort daneben sagt dieselbe Sache ein zweites Mal.
- **Die Referenz nimmt den Rest und wird gekappt, das Datum nicht.** Umgekehrt war es
  falsch: das Datum bekam `flex-1` und behielt bei einer 227 px breiten QR-Referenz 39 px –
  «20.8.2026» hat keine Umbruchstelle und malte sich über seine Box hinaus (gemessen
  380,1 px bei 375 px; **kein Element-Rahmen zeigte es, nur der Text selbst**). Wer auf
  Überlauf misst, muss darum auch **Textknoten** messen – **und sie an jedem `overflow:
  hidden`-Vorfahren kappen**: ein `truncate`-Text ist wirklich abgeschnitten, und eine
  Messung, die die Lösung als Fehler meldet, ist so falsch wie eine, die ihn übersieht.
- **Im Editor** (`MoneyFields`) **zwei** Angaben – und **kein einziges Label darüber**
  (#816/#817/#819): der Schieber **Einnahme ↔ Ausgabe** (Vorgabe Einnahme, #791/#831) und
  die **Partner** (`ObjectSelect`, leer = `RUNTIME_CHOICE`, Beschriftung schlicht
  «Partner», #830). Was ein Bedienelement selbst sagt, sagt man nicht daneben. **Kein
  Betragsfeld** und kein Satz am Vorgang: beides stünde beim Modellieren nicht fest bzw.
  doppelt.
  ►►► **Der dritte Schalter ist weg** (#854): «Zahlung abwarten ↔ nicht abwarten» sagte,
  was die vereinbarte **Zahlungsfrist** ohnehin sagt (null Tage = Vorauszahlung) – zwei
  Aussagen über dieselbe Sache, und die zweite steht in einer **Vorlage**, während die
  Entscheidung dort fällt, wo man das Angebot schreibt. `ModuleDraft.prepaid` ist damit
  ebenfalls entfallen. *Die Regel aus #834 gilt weiter – nur gibt es den Wert nicht mehr,
  an dem sie gelernt wurde.*
- ►►► **Eine Frist ist ein `TermField`** (#854–#856, `fields.tsx`) – die üblichen Werte mit
  **Namen**, der Rest getippt. «Vorauszahlung» ist ein Geschäftsbegriff, «0» eine Ziffer,
  die man erklären muss; *«soll ich bei einer Software einfach 0 eintragen?»* beantwortet
  darum **«Sofort»**. **Kein Schieberegler**: zwischen «Vorauszahlung» und «30 Tage» liegt
  nichts, was man durch Ziehen findet – es ist eine Aufzählung mit freiem Rest, und dafür
  gibt es `Segmented`. Die freie Eingabe beginnt bei `freeMin` (geklemmt beim **Verlassen**,
  nicht beim Tippen – wer eine 3 vor die 0 setzen will, muss die 0 schreiben dürfen), und
  **die Werte kommen vom Server** (`d.payment_terms`/`d.lead_terms`): eine zweite Liste im
  Browser liefe beim ersten neuen Regelwert auseinander. Dasselbe Bauteil im Angebot
  (`Terms`) wie an der Angebotszeile (`QuoteRow`) – zwei Bauarten für dieselbe Frage
  liefen beim nächsten üblichen Wert auseinander. Gemessen in Chromium: 1440 · 1280 · 1024 ·
  834 · 375 · 320 px, **0 px** waagrechter Überlauf (Bug-Form mit einem unteilbaren Wort:
  +140 px bei 375, +195 px bei 320 – die Messung ist nicht blind).
- ►►► **Alles zu EINEM Partner steht auf EINER Zeile** (#833, `.erp-partyrow`). ◄◄◄
  Nummer, Name und die Pflichtangabe «Was ist zu tun?» (#805/#808, benannt über
  `aria-label`, gesagt vom Platzhalter) gehören zusammen – bei mehreren Partnern ist die
  Zeile die **einzige** Stelle, an der die Zugehörigkeit steht. Gemessen: ab 834 px eine
  Zeile, darunter bricht das Feld um (auf einem Telefon geht es nicht anders).
- **Der Löschen-Knopf erscheint beim Hovern** (#832, `.erp-rowaction` in `globals.css`) –
  **und bleibt auf Touch sichtbar** (`@media (hover: none)`): eine Funktion, die nur ein
  Zeiger findet, gibt es am Telefon gar nicht. `:focus-within` deckt die Tastatur ab. Als
  **eine** Regel im Blatt, nicht als `onMouseEnter`-Zustand je Zeile.
- **Und «Was ist zu tun?» ist an der Angebotszeile eine AUSKUNFT** (#836): dort steht das
  Ergebnis, also Symbol + Wert mit Erklärung im Hover – ein Fragezeichen über einer Antwort
  liest sich schräg. Im Editor bleibt die Frage richtig, dort füllt man sie aus.
- ►►► **Ein Wort für beide Richtungen** (`DEAL_PARTY`, `DEAL_TASK`, #802). ◄◄◄ «Kunde» ↔
  «Lieferant» ist dieselbe Rolle; Singular = Plural, damit es keine Beugung gibt, die
  jemand rechnet. Ein Rollen-Wort als Literal in der Oberfläche ist ein Wächter-Fehler.
- **Nummer und Name brechen nicht um** (#838) – der Name wird gekappt; umgebrochen las er
  sich wie eine zweite Angabe. Und **was eine Zahl ist, steht tabellarisch** (#839, `mono`):
  Betrag, Zahlungsfrist und Datum. Die **Objektnummer** bleibt bewusst anders – sie ist eine
  **Kennung**, kein Messwert (#282/#784).
- **Der Kopf trägt Symbol UND Wort** (#815) – als kompakte Marke, nicht als Symbol allein
  auf einer eigenen Reihe. Daneben der **Liefertermin** und, wenn er vorbei ist, «überfällig
  seit …» (#814) – eine Ableitung des Servers, kein Zustand.
- **Abgesagt ist abgesagt** (#811): an einer abgelehnten Zeile stehen weder Preis noch
  Frist. Die Zahlen bleiben in den Daten – der Log ist die Historie.
- **Alle Knöpfe einer Angebotszeile sind gleich hoch** (`ACT_H`, #810): zwei Knöpfe, die
  sich um einen Pixel unterscheiden, lesen sich als Rangfolge.
- **Wen man anfragt, wählt man aus** (#809): die **Zeile ist der Schalter** –
  «Anfragen (2)» war eine Ansage, keine Wahl.
- **Kein Referenz-Feld** (#812): niemand wusste, was hineingehört, und die Rechnungsnummer
  erzeugt der Server selbst. Damit hatte `note` keinen Aufrufer mehr. **Kein Betragsfeld** – beim
  Modellieren steht er nicht fest. **Kein Erklärsatz darunter** (#792): er sagte, was das
  Feld darüber zeigt.
- ►►► **Storniert wird, nicht gelöscht** (#823/#824). Der Papierkorb verspricht, dass die
  Zeile verschwindet – eine Rechnungsnummer ist aber vergeben. Das Zeichen ist darum
  `CircleSlash` (dasselbe, mit dem das Haus überall «storniert» schreibt), und was
  passiert, ist eine **Gegenbuchung**: die Zeile bleibt und heisst «storniert», die neue
  heisst «Storno». Beide Richtungen der Angabe kommen vom Server (`reverses` ·
  `reversed`) – im Browser müsste die zweite über die ganze Liste gesucht werden.
- ►►► **…aber nur eine RECHNUNG** (#842). Eine **Zahlung** ist ein Ereignis der
  Aussenwelt; an ihr steht «Korrigieren», und das ist **kein neues Verb**: es öffnet die
  gewöhnliche Erfassung mit dem **negativen Betrag vorbelegt** (`negate`, als Zeichenkette
  gerechnet – Beträge reisen als String). Ob es ein Erfassungsfehler war oder ob das Geld
  zurückkam, weiss nur ein Mensch: angeboten wird es, angelegt nicht. Die Sperre steht im
  **Dienst**; dies ist die freundliche Hälfte.
- **Ein Nummernfeld gibt es nur, wo die Nummer von aussen kommt** (#840,
  `charge_ref_label` ↔ `payment_ref_label`). `null` heisst «wir nummerieren» – dann gibt es
  **kein Feld**; ein Platzhalter «automatisch» war ein Feld, das nichts aufnimmt. Wie es
  heisst, sagt der Server, nie ein `if` auf die Richtung.
- **Was WIR anbieten, füllen wir vor dem Hinausgehen** (#837, `Terms` + `we_quote`):
  bei einer Einnahme nennen wir den Preis, und ein Angebot ohne Betrag ist keines. Es sind
  **dieselben drei Felder** wie an einer Angebotszeile, nur eine Ebene früher. Und die
  **Abwahl gilt für die Anfrage, die man gerade stellt** (#835) – sie fällt mit dem
  Absenden; sonst blieb der zweite Partner abgewählt, nachdem man den ersten gefragt hatte.
- **Ohne Rechnung kein Zahlungs-Knopf** (#822) – nicht ausgegraut, sondern gar nicht da:
  `can` führt `pay` erst, wenn etwas gefordert ist.
- **Der Modul-Abschluss steht am ENDE der Karte** (#829), hinter der Geld-Zeile. Er stand
  in der Stufe «Auftrag», also mitten in der Kette, und darunter kam noch etwas – ein
  Knopf, der ein Modul abschliesst, sagt so «hier ist Schluss», während sichtbar noch
  etwas folgt. Die Sperre (`d.prepaid`, jetzt aus der vereinbarten Zahlungsfrist) ersetzt
  an genau dieser Stelle den Knopf.
- ►►► **Ein Name steht nie ohne seine Nummer** (#853). ◄◄◄ *«Der Objektname allein darf nie
  ohne die Objektnummer stehen – immer beides in Kombination.»* Gemeldet an der Preiszeile
  des Angebots («1×Blech»), während dieselbe Sache eine Zeile höher **mit** ihrer Nummer
  stand: derselbe Datensatz in zwei Schreibweisen, und die schlechtere ist die, an der man
  ihn nicht wiedererkennt – ein Name ist nicht eindeutig, die Nummer ist die Kennung. Der
  Wächter prüft die **Regel** (jede `*_name`-Anzeige hat ihren `<ObjId>` in Sichtweite),
  nicht die gemeldete Zeile.
- ►►► **Nach dem Bezahlen wird kurz nachgefragt** (#857, `Money`). ◄◄◄ Gebucht wird vom
  **Webhook** – das bleibt so (der Browser des Zahlenden ist keine Quelle). Zwischen dem
  «bezahlt» der Karte und der Meldung liegen ein bis drei Sekunden, und in denen lädt ein
  einzelnes Nachladen zu früh. Nachgefragt wird alle 1.5 s, bis sich `d.paid` ändert,
  höchstens zehnmal: **kein zweiter Kanal** (WebSocket/SSE) für ein Ereignis, das einmal je
  Zahlung eintrifft. Bleibt die Meldung aus, steht die Karte still da, statt sie zu
  behaupten.
- **Und die Bezahlkarte nennt die Rechnung** (#858, `pay-online.tsx`): kassiert wird über
  **eine** Rechnung, nicht über einen Saldo – dieselbe Nummer steht danach beim
  Zahlungsdienst in Beschreibung und Metadaten.
- **Das Partner-Feld hält die frische Wahl nur, bis sie als Zeile dasteht** (#794 → #820).
  Gehalten wird sie, weil sie im Moment des Klicks noch nicht gespeichert ist; sobald der
  Server sie als Angebotszeile zurückgibt, stünde derselbe Partner zweimal da. Eine
  **Ableitung**, kein zweiter Zustand – ein Zurücksetzen an der Antwort wäre die Stelle,
  die der nächste Pfad vergisst.
- **Eine Karte, an der man noch handeln kann, wird nicht gedämpft** (#821,
  `DiagramStep.openActions` ← `ProcessStepResponse.open_actions`). Gemessen war es der Fix
  des letzten Fixes: die Geld-Knöpfe funktionierten an einem abgeschlossenen Auftrag, die
  Karte lag trotzdem bei 55 % Deckkraft da – eine erfundene Sperre, nur in Farbe. **Und
  die Angabe muss durchgereicht werden**: fehlt sie, ist sie `undefined`, `!undefined` ist
  wahr, und die Karte wäre danach **nie** gedämpft.
- **Das Modul-Protokoll erscheint nur, wo es etwas zu berichten hat** (#825,
  `DiagramStep.records`): erfasste Werte · ein Zustandswechsel · eine Verifikation. Kein
  `if module_type` – bei einem Modul ohne physisches Gegenstück blieben sonst Nummer, Name
  und Uhrzeit übrig. Entfernt wird es nirgends; es ist der Nachweis.
- **Die Wörter der Richtung stehen in `lib/modules.DEAL_DIRECTION`** (Symbol, Label,
  Hinweis) – der Editor braucht sie, bevor es einen Vorgang gibt. Mehr trägt sie nicht:
  «Partner» ist ein Wort für beide Richtungen und Singular = Plural (#787/#802).
  `test_frontend_mirrors` hält sie mit `domain/deal.DIRECTIONS` deckungsgleich.
  ►►► **Die Symbole kommen aus `FLOW`** (#845) – Handschlag ↔ Einkaufswagen, eine
  Bildsprache im Haus. Zwei gespiegelte Pfeile waren auf 15 px dasselbe Zeichen mit
  anderer Neigung: man musste hinsehen, statt zu erkennen. Die **Wörter** bleiben
  «Einnahme» ↔ «Ausgabe» – der Einwand aus #831 galt ihnen, und ein Symbol behauptet
  keinen Namen; es zeigt die häufigste Gestalt der Sache.
- **«Partner» steht im PLATZHALTER, nicht darüber** (#843): die Beschriftung kostete eine
  Zeile für ein Wort, und darunter erklärte «Nummer oder Name» dasselbe Feld ein zweites
  Mal. Zusammengelegt sagt der Platzhalter beides. Im **Scan-Vollbild** bleibt die Sorte
  eine Beschriftung (`scanLabel`) – dort liegt Text auf einem Foto.
- **Der Löschen-Knopf einer Zeile sieht aus wie der am Modul** (#844, `RowDelete`): ein
  26-px-Quadrat, kein Rahmen, keine Fläche, allein die Warnfarbe – nicht ein
  `erp-actbtn`-Kasten mitten in einer Zeile aus Nummer, Name und Eingabefeld. **Ob er sich
  einblendet, sagt der Aufrufer** (`reveal`), nicht das Bauteil: der Erfassungspunkt hatte
  ihn immer sichtbar, und das bleibt so.
- ►►► **Der Steuersatz steht NICHT im Editor** (Testnotiz #851). ◄◄◄ Er stand dort als
  «Vorbelegung jeder neuen Position» (`ModuleDraft.vatRate`) und war damit eine
  Eigenschaft des **Moduls** – eine Vorlage, die für jeden künftigen Auftrag denselben
  Satz behauptet, obwohl er an der **Sache** hängt. Gefragt wird er je Position an der
  Ausführungsstelle (`Goods`), und der Katalog reist mit dem **Vorgang**
  (`DealEmbed.vat_rates`). Mit ihm sind `DEFAULT_VAT`, `VAT_LABEL`, der
  `ModuleCatalog.vat_rates`-Weg und die ganze `vatRates`-Prop-Kette entfallen: ein
  Spiegel ohne Leser ist kein Spiegel, sondern eine zweite Wahrheit, die niemand
  vergleicht.
- ►►► **Die Währung steht im KOPF, nicht an jeder Zahl** (`Currency`). ◄◄◄ Ein Beleg hat
  *eine* (zwei wären zwei Belege) – fünfzehnmal «CHF» neben fünfzehn Beträgen wäre Fläche
  statt Struktur. **Ob man sie noch wählen darf, sagt `can`**, nie die Stufe; ist sie
  gebunden, **verschwindet sie nicht**, sondern wird zur Auskunft mit dem Grund im Hover.
  Genannt wird sie beim **Total** und beim **offenen Betrag** – den Zahlen, die
  abgeschrieben und überwiesen werden. Ein `<select>` ist hier richtig: Währungen sind
  eine endliche Aufzählung, keine Referenz auf einen Datensatz.
- ►►► **Die Nachkommastellen kommen von der Währung**, nie aus einer festen 2. ◄◄◄
  `formatAmount(v, decimals)` mit `d.currency_decimals`; **JPY** hat null, **KWD** drei.
  Auch die **Vorschau** (`Sums`) rechnet damit – sonst zeigte sie eine andere Zahl als
  die, die der Dienst danach bucht, und hätte genau ihren einen Zweck verfehlt.
- **Das Leistungsdatum ist vorbelegt** (#852, `d.service_date`) – aus dem Prozess, nicht
  aus dem Rechnungsdatum. Überschreibbar: ein Mensch weiss von Teilleistungen.
- **Ohne Verifikation kein Scan-Tor** (`step.verifies`, aus `Module.requires_verification`):
  ein Modul, das keine Stücke bewegt, wird mit **einem** Knopf bestätigt. Die
  Ausführungsstelle fragt die **Eigenschaft**, nie den Modultyp – sonst fehlt beim nächsten
  Modul derselben Art die Zeile.
- ►►► **Der Preis steht an SEINER Position, und der Steuersatz daneben** (MWSTG Art. 26).
  ◄◄◄ Sie hängen an der **Sache**: sechs Wellen zu 8.1 % und eine Ausfuhr zu 0 % stehen
  auf demselben Papier. Wo **wir** den Preis nennen (`we_quote`), fragt `Goods` je Zeile
  *Preis netto* und *Satz*, und der Angebotsbetrag ist ihre **Brutto-Summe** – ein
  Betragsfeld daneben ist entfallen, es wäre nicht nur die zweite Aussage über dieselbe
  Sache, sondern eine, die der Dienst abweist. Der **Katalog kommt vom Server**
  (`d.vat_rates`); eine zweite Liste im Browser liefe beim ersten Satzwechsel auseinander.
  Ein `<select>` ist hier richtig – die Sätze sind eine endliche **Aufzählung**, keine
  Referenz auf einen Datensatz.
- **Gerechnet wird nichts, ausser als Vorschau** (`Sums`): dieselbe Regel wie im Dienst –
  **je Satz auf der Summe**, nie je Position aufsummiert. Gebucht wird dort.
- **Der bestätigte Auftrag ist ein BELEG, kein Feldraster** (#847). Vier gleich laute
  Lesefelder in einem `auto-fit`-Raster zerfielen je nach Breite in eine, zwei oder vier
  Spalten, und der **Betrag** stand als drittes Kästchen von links. Jetzt: **wer** (eine
  Zeile) · **was es kostet** (rechtsbündig Netto · Steuer je Satz · Total unter **einer**
  Haarlinie über beide Spalten – an die zwei Zellen geschrieben hätte sie ein Loch in der
  Mitte) · **zu welchen Bedingungen** (klein daneben). Die **Positionen stehen nicht noch
  einmal darin**: sie stehen oben in `Goods`, seit die Zeile ihren Preis trägt.
- **Die Steuer einer gebuchten Zeile steht im HOVER** (`taxTip`): bei zwei Sätzen wären es
  fünf zusätzliche Zahlen neben Betrag, Referenz und Datum, und bei 320 px ist dort kein
  Platz. Eine **Zahlung** trägt keinen Hinweis – Geld trägt keine Steuer, es begleicht sie.
- **Was der Partner ändert, kommt an** (#846). Die drei Felder einer Angebotszeile sind
  lokal, damit man tippen kann – aber ein `useState`-Startwert wird genau **einmal**
  gelesen: ändert die Gegenpartei danach ihre Zahlungsfrist, zeigte das Feld weiter den
  alten Wert, und wer etwas anderes korrigierte, **schrieb die alte Frist zurück**.
  Nachgezogen wird beim **Wechsel des Server-Werts** (`[remote]`), nicht bei jedem
  Rendern – dieselbe Bauart wie `defaultOpen` (#727). Und **beide** Fristen stehen in der
  Zeile, jede mit ihrem Wort im Hover; zwei nackte Tageszahlen wären nicht unterscheidbar.
- **Kein Erklärsatz über den fehlenden Abschluss-Knopf** (#849): die Sperre steht als
  Auskunft im **Kopf**, die Zahlen in der **Geld-Zeile**, und dass der Knopf fehlt, sieht
  man. Ein Hinweis, der nichts Neues sagt, liest sich wie eine Fehlermeldung.
- **Das Mikro-Label ist ein Bauteil** (`fields.MICRO_LABEL`) – es stand als Inline-Stil an
  jeder Stelle, mit leicht verschiedenen Werten (11 ↔ 11.5 px, 600 ↔ 700, .05 ↔ .07 em).
  Genau die Form, in der eine Gestaltungsregel auseinanderläuft, ohne dass es auffällt.
- ►►► **Keine Reiter — alles untereinander** (Testnotiz #863). ◄◄◄ *«Ich mag diese
  Reiter-Ansicht nicht, ich möchte alles auf einmal sehen untereinander.»* Und die Meldung
  hat recht, weil der Vorgang **einer** ist: das Angebot erklärt die Zusage, die Zusage
  erklärt die Rechnung. `open`/`setOpen`/`shows` sind entfallen; die Leiste blieb eine
  Runde lang als **Übersicht** ohne Handler und ist mit #868 ebenfalls gegangen – der
  Verlauf steht jetzt an den Abschnitten. *Die Sorge aus der Vorrunde («bei vier Buchungen
  zwei Bildschirme hoch») bleibt richtig – sie ist eine Frage der **Dichte**, nicht des
  Versteckens, und die drei Antworten darauf stehen unten.*
- ►►► **EINE Positionstabelle** (#862). ◄◄◄ *«Der Positions-Abschnitt ist doppelt.»* – Er
  war es: `Goods` sagte, worum es geht, und der Angebotsblock zeigte dieselben Zeilen noch einmal
  mit Eingabefeldern (und **weniger**: kein Chevron, keine Spezifikation). Jetzt ist es
  eine Tabelle, die tippen lässt, solange man anbieten darf. **Der Entwurf wohnt darum in
  `DealWork`** – beide sehen ihn – und wird **je Artikel** gehalten (`Record<string,
  PriceRow>`), nicht als Liste: eine Liste müsste nachgezogen werden, sobald der Prozess
  eine Position dazustellt, und ein Nachziehen löscht getippte Preise.
- ►►► **Die Zahlungen stehen eingerückt unter ihrer Rechnung** (#861). ◄◄◄ Sie standen
  flach und chronologisch da, die Zugehörigkeit war ein «auf 100000801-1» am Zeilenende.
  Eingerückt sagt es die **Form** (dieselbe Geste wie die Stückliste unter ihrer
  Einzelinstanz, #724) – der Text daneben ist damit entfallen, und in einer engen Zeile
  ist es genau der Platz, den das Datum braucht. **Was zu keiner Rechnung gehört,
  verschwindet nicht**: eine Gruppe «Nicht zugeordnet» am Ende.
- ►►► **Die Geld-Handlungen stehen AN der Rechnung** (#859, `EntryRow`). ◄◄◄ *«Wie kann
  ich bestimmen, welche Rechnung ich bezahle?»* – Ein Knopf **an** der Zeile beantwortet
  die Frage, indem er sie nicht stellt: Zahlung erfassen · Jetzt bezahlen · Überweisen ·
  Stornieren/Gutschrift. Unten bleibt, was dem **Vorgang** gilt (die nächste Forderung,
  die Gegenhandlung). Das Auswahlfeld «welche Rechnung?» im Formular ist damit weg.
- **Storno oder Gutschrift sagt der Server** (`e.reverse_word`, #860): was bezahlt ist,
  nimmt man nicht zurück, man schreibt es gut. Und **erstattet wird auf dem Weg, auf dem
  gezahlt wurde** – `e.refundable` (nur eine Karte) gegen «Korrigieren» daneben, das die
  gewöhnliche Erfassung mit dem negativen Betrag öffnet.
- **Überweisen ist eine AUSKUNFT** (#865, `Transfer`): Bankverbindung, RF-Referenz und die
  **QR-Rechnung** als fertiges SVG vom Server – erst auf Klick. Im Browser gebaut wären es
  einunddreissig Zeilen ein zweites Mal, und eine verrutschte sieht man einem QR nicht an.
  Wo es keinen Code geben kann, steht der **Grund** statt einer leeren Fläche.
- **Wie bezahlt wurde, ist ein `Segmented`** (`d.methods`) – zwei Werte sind ein Schieber,
  keine Auswahlliste; die **Karte** steht nicht darin (sie kommt über den Webhook).
- ►►► **Die Währung steht im ANGEBOT** (#864). ◄◄◄ Sie ist eine **Entscheidung** über das,
  was gleich hinausgeht – ein Auswahlfeld zwischen lauter Auskünften (der Meta-Zeile) liest
  sich wie eine. Sie hängt an **`can`**, nicht an einem zweiten Feld (`currency_locked` ist
  entfallen); was feststeht, steht als Wert da (`Fixed`), nicht als gesperrtes Feld (#749).
  **Und ihre Beschriftung trägt den Code schon** (#869): `currency.label` liefert «CHF ·
  Schweizer Franken» – der Code davor ergab «CHF · CHF · Schweizer Franken». Das Feld ist
  so breit, dass der Name lesbar bleibt; ein natives Auswahlfeld zeigt geschlossen genau
  den Text der gewählten Zeile.
- ►►► **Einen «Anteil» gibt es nicht** (#867). ◄◄◄ Er stand daneben – eine Prozentzahl, die
  sagte, welchen Teil der Positionen dieser Vorgang abrechnet. *«Ich checke diese Funktion
  nicht»*, und gebraucht wird sie nicht: **wer den Preis nennt, nennt ihn je Position**,
  also trägt ein zweites Modul schlicht seine eigenen Positionspreise.
- ►►► **Jeder Knopf der Karte ist ein `ActionButton`** (#877–#896). ◄◄◄ *«Ein Icon und
  beim Hover der Text dazu»* – siebenmal gemeldet, also die Form eines Knopfes im Haus und
  nicht eine Eigenschaft dieser Zeile. Der **Name** steht zuerst in der Blase, ein Grund
  dahinter; was dort stand, waren ganze Sätze statt des Wortes, nach dem gefragt war.
- **Eine WAHL behält ihr Wort** (#877/#878): mit Symbol stehen die Fristen auf ihrer
  **Inhaltsbreite** statt jede auf einem Drittel der Spalte – eingeklappt wären es drei
  anonyme Quadrate, und man müsste auf jedes zeigen, um zu lesen, worunter man wählt. Ein
  **Knopf** ist eine Handlung und hat keine Antwort, die dastehen müsste; eine Frist hat
  eine. Das Symbol folgt aus der **Zahl** (0 = ohne Frist · n = Termin · frei = Eingabe).
- **Die Währung steht bei den BETRÄGEN** (#876/#881): an jeder Zahl, die man abschreibt
  (Angebotszeile · Vorschau · Total). Die Beschriftung über dem Auswahlfeld ist entfallen –
  es zeigt geschlossen «CHF · Schweizer Franken» –, und ab der Zusage steht dort **gar
  nichts** mehr. *Löst #864 ab: die Auskunft gibt es weiterhin, sie steht nur dort, wo die
  Frage entsteht.*
- **«0 Tage» heisst «Vorauszahlung»** (#885, `termText`) – gelesen aus **derselben Liste**,
  aus der man sie wählt; was keine Liste kennt, ist die freie Eingabe («x Tage»).
- **Aus einer Frist folgt ein Datum** (#884, `TermField preview`): die Eingabe bleibt «in x
  Tagen», das Datum rechnet das System. Vorbelegt ist der Wert aus dem Angebot, änderbar
  bleibt er – nachverhandelt wird auch am Telefon.
- **EIN Datum je Geld-Zeile** (#890, `dateText`): «fällig in 30 Tagen» bzw. «überfällig
  seit 17 Tagen», beide Daten im Hover. Ohne Fälligkeit bleibt das Buchungsdatum.
- **Die Offerte wird gespeichert, nicht abgeschickt** (#879, `useAutosave`) – und erst,
  wenn die Zeile **vollständig** ist: der Dienst weist eine halbe Offerte ab, und ein
  Auto-Save beim ersten Tastendruck liefe gegen eine Meldung, die nur sagt, dass man noch
  nicht fertig ist.
- **«Zahlung erfassen» verschwindet an einer bezahlten Rechnung** (#894) – überzahlt bleibt
  er, dann steht die Rückgabe an. Eine Ableitung aus derselben Zahl, die den Punkt daneben
  färbt.
- **Der Hover erklärt, statt zu wiederholen** (#882): «Was ist zu tun? 123456» sagte die
  Frage plus den Wert, der daneben steht. Eine Blase, die den sichtbaren Text wiederholt,
  ist die Stelle, an der man aufhört, Blasen zu lesen.
- **Kleineres:** «Buchen» heisst, was es bucht (#887, vom Server); die Beschriftung
  «Partner» am bestätigten Auftrag ist entfallen (#883); der **«Schliessen»-Knopf** im
  Überweisen-Panel ist gelöscht (#889 – der Knopf, der es geöffnet hat, schliesst es);
  das **Leistungsdatum** ist längst automatisch, und was fehlte, war der Satz, der das
  sagt (#886 – Pflichtangabe nach MWSTG Art. 26 Bst. c, aus dem Prozess vorbelegt).
- ►►► **Der Status steht an der RECHNUNG, nicht als Leiste darüber** (#875). ◄◄◄ `MoneyBar`
  war richtig, solange ein Vorgang mehrere Rechnungen tragen konnte; seit #866 gibt es je
  Modul **eine** – die Leiste fasste damit eine Zeile zusammen, die direkt darunter stand.
  Übrig bleibt **Punkt + Wort** an der Zeile (*Bezahlt · Offen · Überfällig · Überzahlt*),
  **abgeleitet** aus `e.open`/`e.overdue`. Und die **Beleg-Nummer wird dabei nicht bis zur
  Unkenntlichkeit gekappt** («100…»): sie schrumpft nur bis `REF_MIN`, darunter bricht die
  Zeile um – dieselbe Lehre wie bei der Positionszeile (#847).
- ►►► **Zwei Knöpfe sind gefallen** (#874). ◄◄◄ «Gutschrift erfassen» am Vorgang trug
  dasselbe Wort wie die Gutschrift **an der Rechnung** und tat etwas anderes (eine
  freistehende negative Forderung ohne Bezug, die in der Liste als zweite Rechnung
  erschien); «Zahlung erfassen» am Vorgang war **unerreichbar** (`can` führt `pay` erst mit
  einer gebuchten Forderung). **Und «Auftrag stornieren» ist keine Buchung**: es stand
  zwischen den beiden und steht jetzt am **Ende der Karte**, neben dem Abschluss – die eine
  bringt den Vorgang ans Ziel, die andere nimmt ihn zurück.

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
