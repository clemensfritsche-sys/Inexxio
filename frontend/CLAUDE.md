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

## Verkauf und Geld (`purchase-work.tsx`)
**Dieselbe Karte, andere Richtung.** Ein Verkaufs-Beleg rendert buchstäblich dieselbe
Komponente wie ein Einkauf: dieselben drei Zeilen, dieselben Knöpfe. Was sie
unterscheidet, **reist fertig mit** – Wörter und Verben in `stages[]`, Name und Farbe in
`label`/`tone`, das Wort für «zurück» in `undo`. Die Oberfläche braucht dafür **kein
einziges `if`**; das Symbol kommt aus `FLOW` (`lib/modules`), weil eine Antwort es nicht
transportieren kann.

- **Die Stufen-Schlüssel stehen an EINER Stelle** (`lib/modules.STAGE`) und decken das
  Backend genau ab. Vorher standen die deutschen Einkaufs-Wörter im Rumpf
  (`stage.key === 'wareneingang'`) – ein Verkaufs-Beleg hätte an **keiner** Stufe etwas
  gezeigt: alle Vergleiche falsch, still und ohne Fehlermeldung.
- **Die Gegenpartei-Rolle kommt vom Server** (`party_role` am Beleg, `ModuleTypeInfo` im
  Editor) und wird **durchgereicht, nicht ausgewertet**. `moduleType === 'verkauf' ?
  'customer' : 'supplier'` wäre die zweite Stelle für dieselbe Regel – und der Dienst
  wiese danach ab, was die Liste angeboten hat. Dasselbe gilt für das **Wort**
  (`party_word`): «Auftrag an den Lieferanten» ist an einem Verkaufs-Modul falsch.
- **Das Geld steht NEBEN den Stufen** (`Money`), nicht als vierte in der Kette: eine
  Zahlung macht aus einem Angebot keine Zusage, und nach einem Storno ist eine Erstattung
  der Normalfall. Ob es überhaupt etwas zu zeigen gibt, sagt der Beleg (`open` ist `null`,
  solange nichts zugesagt ist) – «offen: 0.00» wäre eine erfundene Aussage.
- **Gerechnet wird nichts im Browser.** *Offen*, *fällig* und *überfällig* sind
  Ableitungen des Servers (`services/payments`); eine zweite Formel hier wiche ab, und
  ihre Zahl sähe trotzdem richtig aus. **Punkt + Wort** wie jeder Zustand im Haus, Beträge
  über `formatAmount` und `.ix-tnum`.
- **Die Knöpfe hängen an `can`** – auch `pay` und `link`, obwohl sie keine Stufe haben.
  Der Zahllink erscheint nur, wo es einen Dienst **und** einen offenen Betrag gibt: ein
  Knopf, der nie etwas tun kann, ist kein Angebot, und ein ausgegrauter wäre eine Bitte.
- **Die Route kennt der Aufrufer, nicht die Karte** (`onLink`): dieselbe Bauart wie
  `onAction`. Fehlt der Rückruf, gibt es den Knopf nicht.

## Zahlung (`components/erp/deal-work.tsx`)
Der Geldvorgang an der Ausführungsstelle: **drei Zeilen** – `Angebot → Auftrag →
Rechnung & Zahlung`, in **beide** Richtungen dieselben. Was Einnahme von Ausgabe
unterscheidet, **reist fertig mit** (`DealEmbed.label`, `stages[].label/verb`, `party_word`,
`ask_verb`, `charge_word`, `money_label`, `stage_label`, `undo`) – die Karte braucht dafür
**kein einziges `if` auf die Richtung**; ein Wächter zählt sie.

- **Zwei Stufen, und die dritte Zeile ist KEINE.** Unumkehrbar sind zwei Dinge: nichts
  zugesagt · zugesagt. «Abgeschlossen» stand einmal als dritte Stufe da und war genau das
  Missverständnis – ein **Zustand** in einer Reihe von **Schritten**. Die dritte Zeile ist
  das **Geld**: eine Zahlung macht aus einem Angebot keine Zusage, sie ist reversibel, und
  sie darf **vor** der Erfüllung stehen (Vorauszahlung) wie danach. Sie steht dort, wo man
  sie erwartet, und ist ab der Zusage bedienbar.
- **Dieselbe Bildsprache wie der Beschaffungs-Beleg**, aber **kein geteilter Code**: das
  Modul soll bestehen, wenn «Beschaffen»/«Verkauf» gelöscht werden. Zeilen statt
  Modul-Karten, kräftige Linie bis zur offenen Stelle, Haarlinie danach.
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
- **Im Editor** (`MoneyFields`) drei Angaben – und **kein einziges Label darüber**
  (#816/#817/#819): der Schieber **Einnahme ↔ Ausgabe** (Vorgabe Einnahme, #791/#831), die
  **Partner** (`ObjectSelect`, leer = `RUNTIME_CHOICE`, Beschriftung schlicht «Partner»,
  #830) und der Schieber **«Zahlung nicht abwarten» ↔ «Zahlung abwarten»** (#834). Was ein
  Bedienelement selbst sagt, sagt man nicht daneben – **aber es muss es dann auch sagen**:
  «Nach Zusage» nannte den Bezugspunkt, nicht die Entscheidung. **Kein Betragsfeld** und
  kein Satz am Vorgang: beides stünde beim Modellieren nicht fest bzw. doppelt.
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
- **Wen man anfragt, wählt man aus** (#809): die **Zeile ist der Schalter**, wie im
  Beschaffen-Modul – «Anfragen (2)» war eine Ansage, keine Wahl.
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
- **Was WIR anbieten, füllen wir vor dem Hinausgehen** (#837, `OurOffer` + `we_quote`):
  bei einer Einnahme nennen wir den Preis, und ein Angebot ohne Betrag ist keines. Es sind
  **dieselben drei Felder** wie an einer Angebotszeile, nur eine Ebene früher. Und die
  **Abwahl gilt für die Anfrage, die man gerade stellt** (#835) – sie fällt mit dem
  Absenden; sonst blieb der zweite Partner abgewählt, nachdem man den ersten gefragt hatte.
- **Ohne Rechnung kein Zahlungs-Knopf** (#822) – nicht ausgegraut, sondern gar nicht da:
  `can` führt `pay` erst, wenn etwas gefordert ist.
- **Der Modul-Abschluss steht am ENDE der Karte** (#829), hinter der Geld-Zeile. Er stand
  in der Stufe «Auftrag», also mitten in der Kette, und darunter kam noch etwas – ein
  Knopf, der ein Modul abschliesst, sagt so «hier ist Schluss», während sichtbar noch
  etwas folgt. Die Sperre (`prepaid`) ersetzt an genau dieser Stelle den Knopf.
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
- **Der Steuersatz ist eine VORGABE, kein fester Wert** (`ModuleDraft.vatRate`): das Modul
  muss die Rechnung selbst können, aber der Satz hängt an der Sache – hier steht die
  Vorbelegung jeder neuen Position, an der Position ist sie überschreibbar. Der Katalog
  kommt vom Server (`ModuleCatalog.vat_rates`) und reist über die **gemeinsame** Prop-Form
  aller Feldsätze (`vatRates`), wie `types`.
- **Ohne Verifikation kein Scan-Tor** (`step.verifies`, aus `Module.requires_verification`):
  ein Modul, das keine Stücke bewegt, wird mit **einem** Knopf bestätigt. Die
  Ausführungsstelle fragt die **Eigenschaft**, nie den Modultyp – sonst fehlt beim nächsten
  Modul derselben Art die Zeile.
- ►►► **Der Preis steht an SEINER Position, und der Steuersatz daneben** (MWSTG Art. 26).
  ◄◄◄ Sie hängen an der **Sache**: sechs Wellen zu 8.1 % und eine Ausfuhr zu 0 % stehen
  auf demselben Papier. Wo **wir** den Preis nennen (`we_quote`), fragt `OurOffer` je Zeile
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

## Bewegen: selbst gebracht oder eingekauft (`order-detail.Wrapped`)
Ein Transport, den eine Spedition fährt, ist eine **Leistung, die man einkauft** – also
trägt das Bewegen-Modul denselben Einkaufs-Beleg wie das Beschaffen-Modul: dieselben drei
Stufen, dieselben Verben, **dieselbe Komponente** (`PurchaseWork` wird an genau einer
Stelle gerendert). Ein zweites «Versand»-Bauteil daneben wäre der Einkauf ein zweites Mal,
und das zweite veraltet beim ersten neuen Verb.

- **Die Oberfläche fragt zwei Eigenschaften, nie den Modultyp**: `step.moves` (Ziel-Scan?)
  und `step.buys` (`'if_chosen'` → die Wahl anbieten). Beide reisen mit dem Schritt, wie
  Farbe und Beschriftung – den Modul-Katalog lädt nur der Editor.
- **Die Wahl steht dort, wo ihre Folge steht** (`Wrapped`) – und **derselbe Schalter
  nimmt sie zurück** (#775). Der Wert ist **abgeleitet** (`purchase ? 'bought' : 'self'`),
  beide Richtungen sind verdrahtet (`buy` ↔ `revoke`), und **ob es zurückgeht, sagt der
  Server** (`revoke ∈ purchase.can`). Vorher stand er fest auf `self` und verschwand,
  sobald ein Beleg entstand: das Bedienelement, mit dem man gewählt hat, war weg, und der
  Weg zurück lag im Beleg – zwei Gesten für eine Sache. Ist die Wahl nicht mehr umkehrbar,
  bleibt der Schalter **stehen** (gesperrt, Grund im Hover): sonst beantwortet nichts mehr,
  was gewählt war.
- **Der ganze Einkaufs-Bereich trägt seinen Ton** (`ProcurementBlock`, #776) – als
  Haarlinie an der Kante, nicht als Fläche: eine getönte Karte wäre die dritte
  (Modul-Karte → Beleg-Karte → Stufen-Zeile). Sie heisst **«Selbst ↔ Beschaffen»** –
  dasselbe Wort wie das Modul, das es sonst tut, aus **einer** Quelle (`FLOW.buy`,
  gespiegelt von `domain/procurement`). Eine Spedition wird **gekauft**, nie verkauft –
  darum steht dort die Richtung fest und nicht `flowOf(…)`.
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
