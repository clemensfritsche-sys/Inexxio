# INEXXIO Design System

> **Stand v4, November 2026 – verbindlich für jede Oberfläche:** Website, Konto, ERP, E-Mail,
> Papiere (Offerte bis Mahnung). **Der Code ist die Wahrheit.** Diese Datei beschreibt, was gebaut
> ist; das Artefakt [«INEXXIO Design System»](https://claude.ai/artifact/6CQGEWynpkcEskuDzVkKbn)
> zeigt dasselbe zum Anschauen und wird nach dieser Datei nachgezogen, nie umgekehrt.
> Was entfernt wurde (Mockups v4, Dunkelmodus, v2/v3-Aliase, ungenutzte Tokens und Klassen),
> steht in `docs/history/2026-11-22-design-system-aufgeraeumt.md`.

## 1. Wo was steht

| Pfad | Rolle |
|---|---|
| **`frontend/src/styles/design-system/colors_and_type.css`** | **Die eine Quelle aller Werte**: Skalen → Rollen, Schrift, Form, Schatten, Bewegung, Glas, `@font-face`, `.ix-tnum`. Erstes CSS-Modul in `frontend/src/app/layout.tsx`. |
| `frontend/tailwind.config.js` | Die Rollen als Utilities (`bg-bg-2`, `text-fg-3`, `text-accent`, `border-border-1`, `rounded-ds-lg`, `shadow-ds-md`, `font-display` …) – nur `var(--…)`, keine Werte. |
| `website/scripts/tokens.mjs` → `website/src/styles/tokens.css` | Die Website liest dieselben Werte unter eigenen Namen (`--ink`, `--line`, `--red` …), generiert bei jedem Build. Fehlt ein Token, bricht der Build. |
| `website/src/styles/global.css` | Masse der Website (`--maxw`, `--gutter`, `--header-h`, `--section-y`) und die Klassen, die mehrere Bausteine teilen: `.btn*`, `.v4-h2`/`.v4-sub`, `.v4-section`, `.plate`/`.plate--dark`, `.garrow`, `.cdot`, `.zoom-on-hover`. |
| `website/src/components/` | **Die Bausteine der Website** (§6). Je Baustein eine Datei, der Kopfkommentar sagt, was er ist. |
| `frontend/src/app/globals.css` · `frontend/src/components/erp/` | ERP und Konto: Klassen `.erp-*`, `.kt-*`, `.ix-login-*`; Bausteine §7. |
| `backend/app/services/mail_layout.py` | **Die eine Mail-Vorlage** (§8). |
| `backend/app/services/a4.py` | **Die eine Papier-Vorlage** (§9). |
| `docs/design-system/reference/assets/logo/` | Das Logo als Vektor, erzeugt von `generator/make_logos.py` (§10). |
| `frontend/public/fonts/` · `website/src/assets/fonts/` · `backend/app/assets/fonts/` | Inter (variabel) und Inter Tight 600–700, selbst gehostet – kein Abruf bei Google. |
| `.claude/skills/inexxio-design-system/SKILL.md` | Legt jeder Claude-Sitzung bei UI-Arbeit diese Datei vor. |

**Wächter** (`frontend/scripts/design.test.mjs`): jede `var(--x)` ist definiert · jede `ix-`-Klasse
hat einen Stil · keine Alt-Palette (auch als Hex) · Status über `StatusDot` · **jedes Token wird
gelesen** – ein Token, das niemand liest, wird gelöscht, nicht gepflegt.

## 2. Grundsätze

1. **Farbe = Bedeutung.** Kühles, neutrales Grau trägt die Fläche – überall gleich. **Rot ist der
   eine laute Akzent**: auf der Website nur die Anfrage, im ERP der aktive Zustand und echte Fehler.
   Nie dekorativ, **nie in einer Überschrift**. **Slate** ist die leise Stimme im ERP (Info, Links,
   aktive Zeile) und konkurriert nie mit Rot.
2. **Struktur vor Fläche.** Haarlinien und Weissraum trennen, nicht Rahmen und Schatten. Schatten
   nur, was schwebt (Menü, Dialog, Toast).
3. **Nie nur Farbe.** Ein Zustand trägt immer sein Wort – im ERP als Etikett mit Symbol
   (`fields.StatusBadge`, Feed und Kopf), in einer Zeile als Punkt + Wort (`fields.StatusDot`); ein
   Fehler ist ein Satz an der Stelle.
4. **Symbol vor Text** im ERP: Lucide-Symbole, der Name im Hover (`data-tip`). Keine Emoji, kein
   zweites Icon-Set.
5. **Ruhig.** Flach, kurze Bewegungen, bei «weniger Bewegung» steht alles.
6. **Was nicht feststeht, steht nicht da** – keine Platzhalter, keine erfundenen Zahlen.

## 3. Farbe

Verwendet werden die **Rollen**, nie Hexwerte. Die Skalen speisen die Rollen; direkt gelesen wird
eine Skala nur in Zeichnungen (Kran-Szenen) und für einzelne Grautöne.

| Rolle | Token (Website-Name) | Wert | Einsatz |
|---|---|---|---|
| Text | `fg-1` (`--ink`) · `fg-2` · `fg-3` · `fg-4` | `#0A0A0B` · `#44464A` · `#5E6064` · `#A3A5AA` | Titel · Text · der graue Satz, Metadaten · Deaktiviertes |
| Fläche | `bg-1` (`--white`) · `bg-2` (`--paper`) · `bg-3` · `bg-4` | `#FFF` · `#F5F6F7` · `#EEEFF1` · `#E3E4E7` | Grund · Gruppen · Hover · tiefer |
| Dunkel | `bg-dark` · `bg-dark-2` | `#0A0A0B` · `#191A1C` | Fusszeile, dunkle Karten |
| Linie | `border-1` (`--line`) · `border-2` · `border-strong` · `border-on-dark` | `#E3E4E7` · `#D0D2D6` · Ink · Weiss 12 % | Trenner · Feldrahmen · Fokus · auf Dunkel |
| Rot | `inexxio-red` (`--red`) · `-hover` · `-deep` | `#E51A14` · `#C8140F` · `#A5110D` | Anfrage, aktiv, Fehler |
| Slate | `accent` · `accent-soft` · `accent-ink` | `#2C6E8F` · `#EEF4F7` · `#1C4D66` | Info, Links, aktive Zeile (ERP) |
| Bedeutung | `success` · `warning` · `danger`, je `-bg` | `#1E7F46` · `#94570A` · `#C8140F` | Freigegeben/fertig · im Prozess · Problem |

- **Status im Prozess:** Grün = Freigegeben, Anfang und Ende · Amber = im Prozess · Rot = Problem.
  Die Farbe hängt am Status (`domain/statuses.CATALOG`), nie an der Position.
- **Die Alt-Palette ist weg** (`slate-*`, `blue-*`, `gray-*`, `brand-*`, `#2563eb`: 0 Vorkommen;
  eigene Palette nur die Gebietskarte). **Kein Dunkelmodus** – es gibt ihn nirgends.

## 4. Schrift

- **Inter Tight 600–700** für Titel, **Inter** für alles andere (400 Text, 500 Bedienelemente,
  600 kleine Titel). Kein Gewicht über 700, keine weitere Schrift.
- Laufweite Titel −0.03 em (`--tracking-tight`), Zwischentitel −0.015 em (`--tracking-snug`),
  Versalien +0.08 em nur im Mikro-Label des ERP (`fields.MICRO_LABEL`).
- **Zahlen, die untereinander stehen, sind tabellarisch** (`.ix-tnum`, `tabular-nums`).
- **Schweiz:** `1'240.50`, `CHF 1'240.50` (in Tabellen die Währung im Kopf), `14.10.2026`, `14:30`,
  Leerschlag vor der Einheit (`75 %`, `24.5 kg`), **ss** statt ß, Anführungszeichen «so».
  Datum im Frontend nur über `lib/when.ts`, Telefonnummern international («+41 52 378 22 47»).

## 5. Form, Schatten, Bewegung

- **Radien:** Bedienelemente (Knopf, Feld, Etikett, Menüpunkt) **6 px** (`--r-sm`/`--r-md`,
  `rounded-ds-md`) · Karten, Flächen, Bilder, Dialoge, Kopfleiste **8 px** (`--r-lg`/`--r-xl`,
  `rounded-ds-lg`). Kreise bleiben rund. **Keine Pillen-Knöpfe**, keine festen Radien in Bausteinen.
- **Schatten** `--shadow-sm` … `-xl` nur für Schwebendes; `--shadow-red` nur beim Zeigen auf den
  roten Knopf, nie im Ruhezustand.
- **Bewegung:** `--dur-fast` 120 ms (Farbe, Hover) · `--dur-base` 180 ms (Anhebung), Kurve
  `--ease-out`. Auf der Website dürfen Überblendungen 350–600 ms dauern. Bei
  `prefers-reduced-motion` steht alles still.

## 6. Website (v4)

Haltung wie porsche.com in Struktur und Ruhe: grosse Bilder und Videos, wenige Worte, präzise
Raster, weiche Übergänge. Gefühl: leicht, vertrauenswürdig, kompetent, nahbar. Jede Seite will eine
**Anfrage** oder einen **Anruf**.

**Masse:** Inhalt bis 1264 px (`--maxw`) mittig, Seitenrand 16 / 24 px (`--gutter`, ab 768 px),
12 Spalten ab 960 px, Kopf 64 / 76 px (`--header-h`). Abschnitte `.v4-section` 72 px oben (ab
960 px 120 px); nach den drei Bereichen der Startseite etwas mehr (96 / 152 px).

**Regeln**
- **Überschrift – eine Form:** `.v4-h2` (Inter Tight 600, 48 px, mobil 32 px, −0.03 em), darunter
  höchstens ein grauer Satz `.v4-sub` (17 / 16 px, `--ink-3`). **Immer linksbündig.** Keine Kicker,
  keine roten Wörter, kein Mono, keine gesperrte Schrift (`SectionHead.astro`).
- **Knöpfe** (`.btn`, 40 px, gross 48 px, 6 px Radius): **Rot nur für die Anfrage** («Anfrage
  stellen», «Weiter», «Anfrage senden», «Aufgabe schildern»). Abschnitts-Links hellgrau
  (`.btn--grey`). Auf Bildkarten der runde Pfeil `.garrow` (44 px, hell auf Foto, `--ink` auf Grau).
- **Karten:** 8 px, Foto randlos, Text direkt auf dem Bild über einem dunklen Verlauf oder auf der
  dunklen Fläche `.plate--dark`. **Kein Kasten im Kasten** – Text und Knopf nie gemeinsam in einem
  Rahmen. Flächen im Inhalt sind weiss mit feiner Linie (`.plate`), ohne Schatten.
- **Glas nur, wo etwas über der Seite schwebt:** die Kopfleiste (`Header.astro`, Tokens `--glass-*`,
  nur unter `html[data-site]` – im ERP und Konto ist derselbe Kopf deckend weiss), die Leiste unten am
  Handy (`MobileBar`) und kleine Knöpfe auf Fotos (Telefon und Pause auf der Bühne, der runde Pfeil
  `.garrow`). Kein Glas im Inhalt: keine Glaskarten, keine Glasfelder, kein Glas-Akkordeon.
- **Beim Überfahren:** ein Foto in einem Rahmen zoomt langsam um 5 % (1.4 s, `.zoom-on-hover` am
  Rahmen) – überall gleich, ob Link oder nicht. Freigestellte Bilder und Zeichnungen heben sich nur,
  wenn die ganze Fläche ein Link ist (Kachel im Kopf, Feldkarte); sonst stehen sie still.
- **Karussell** (`scripts/carousel.ts`, `[data-carousel]`): eingerastet, beginnt in der Mitte,
  Nachbarn angeschnitten, Punkte darunter (`.cdot`), mit der Maus ziehbar – und **endlos**: nach dem
  letzten kommt der erste. Breit, wo alles nebeneinander passt, ist es eine Reihe.
- **Zeichnungen:** isometrisch, Grau-Rampe – «**Grau ist die Serie, Rot ist, was wir dazubauen.**»
  Garantien zeigen Schemata, keine Stockfotos. Zeichnungen per Schlüssel über `lib/illustrations.ts`.
- **Bilder:** echte Arbeit (Anlagen, Montage, Menschen), natürliches Licht, keine Filter. Ein
  fehlendes Foto ist der graue Rahmen «Foto fehlt» – keine Beispielbilder. Video als `<video>` mit
  Standbild, schmal die Hochkant-Fassung, bei «weniger Bewegung» das Standbild.
- **Wörter:** kein «Fixpreis» (in keiner Form), keine «Werkstatt» – «Standort», «Betrieb», «bei
  INEXXIO» (`check-site` bricht ab). Jeder Text in jeder gebauten Sprache (`t()`).

**Bausteine** (`website/src/components/`)

| Baustein | Was er ist |
|---|---|
| `Header` | Logo · fünf Menüpunkte · Telefon · «Anfrage stellen». Öffnet zu Glas mit Kacheln (Titelbild der Seite, sonst Zeichnung); mobil dasselbe Menü. |
| `Stage` | Bühne der Startseite: Video oder Foto über die ganze Breite, Titel unten links, Rot + runder Knopf. |
| `StageHero` | Seitenkopf der Unterseiten: grosses graues Wort hinten, freigestelltes Bild davor, weich auslaufend. |
| `SectionHead` | Die eine Überschrift-Form. |
| `home/AreaTrio` | Drei Bereiche: hohe Bildkarten, beim Darüberfahren breiter mit Kran-Szene; schmal ein Karussell. |
| `home/Handover` | Nachfolge: Collage aus drei Bildern, Text darunter. |
| `home/WhyNumbers` | Grosse Zahlen an Haarlinien (2 × 2) neben einem freigestellten Porträt. |
| `home/Stagger` · `home/Guarantees` | Drei versetzte Karten, Überschrift dazwischen (Garantien, Funk). |
| `home/SpecialStage` | Bühne mit drei Plätzen und Umschalter (bis vier Felder). |
| `home/ArticleCarousel` | Ratgeber als Karussell, Text auf `.plate--dark`. |
| `spezial/FieldCards` | Graue Karten, das Bild steht auf ihrer Oberkante; schmal ein Karussell. |
| `spezial/SolutionPath` | Jeder Ablauf als senkrechter Weg: «Ihr Problem» → Stationen → roter Punkt «Ihre Lösung». |
| `spezial/PracticeCase` · `spezial/SeriesGap` | Ein Fall aus der Praxis · Serie gegen Einzelstück. |
| `PhotoCard` · `Magazine` · `PhotoRows` | Bildkarte · zwei Spalten versetzt (schmal zum Wischen) · Zeilen im Wechsel. |
| `FactGrid` · `ServiceTiers` · `SeasonCalendar` | Sätze an Haarlinien · drei Stufen als Treppe · Wandkalender (Jan–Dez). |
| `FaqStage` | Höchstens fünf Fragen: links ein Bild zur offenen Frage, rechts eine Liste mit feinen Linien. |
| `ContactSection` · `InquiryForm` · `ContactPanel` | Die Anfrage auf der Standortkarte, in zwei Schritten (erst ein Feld, dann Kontakt); darunter der direkte Kontakt. |
| `CallPanel` | Dunkle Karte für den direkten Weg (Notfall, Bewerbung). |
| `Footer` | Dunkel: Logo oben links, je Menüpunkt eine Spalte, unten der grosse Schriftzug. |
| `MobileBar` | Schmal unten: «Anrufen» · «Anfrage», sobald der Kopf aus dem Bild ist. |
| `Media` · `Photo` · `Icon` · `Lockup` | Bild oder Video · ein Foto aus der Fotoliste · Lucide inline (Strich 1.75) · das Logo als `<symbol>`. |

## 7. Konto und ERP

- **Konto** sieht aus wie die Website (Kopf, Fuss, Schrift, Radien), ohne Glas; der Name als
  grosses Wort im Kopf, Karten `.kt-*`.
- **ERP – dicht, 14 px:** Struktur vor Fläche, Haarlinien statt Kartenrahmen mit Schatten, 8-px-Raster,
  Infotexte im Hover, Objektnummer als Kennung (`.erp-objid`), Zahlen tabellarisch. Rot nur aktiv
  und «zu tun», Slate für Info und Links. Der Kopf ist der der Website.
- **Ein Datensatz ist eine weisse Seite aus Abschnitten – dieselben wie im Konto** (November 2026):
  links der Titel (28 px, ohne Untertitel, daneben ⓘ und «zu tun»), rechts die Sache, eine Haarlinie
  dazwischen (`Card` = `.kt-sec`); keine Karte in der Karte. Breiter Inhalt (Diagramme, Listen):
  Titel darüber (`Card wide`, `SectionSep`). Gestapelt wird nach der Breite des Fensters, nicht des
  Bildschirms (Container-Abfrage `.erp-secs`). Keine Sprungleiste – man scrollt.
- **Felder wie im Konto:** die eine Feldform (`inputClass`) ist eine graue Fläche ohne Rahmen, beim
  Tippen weiss mit dunkler Linie; am Personendatensatz die Konto-Felder selbst (`KtField`,
  `KtDate`, `KtSelect`).
- **Art-Farben** (`--type-*`, je Datensatz-Art eine leise Farbe mit hellem Ton, kühl gestimmt, keine
  erinnert an Rot): im Symbol, in der Überschrift des Kopfs und als Ton der gewählten Zeile im Feed.
  Der Kopf selbst bleibt weiss.
- **Feed ohne Kästen:** Suche als graue Fläche (Scan als Symbol darin), Filter nur als Symbole,
  Zeilen über die ganze Breite; «+» links unten. Der Kopf des Feeds ist so hoch wie der Kopf eines
  Datensatzes (`ERP_HEAD_H`) – die Linien treffen sich.
- **Verlauf:** Nachrichten, Notizen, Dokumente; die Änderungen aus dem Log nur mit «Änderungen
  zeigen» (standardmässig aus).
- **Die Bausteine** (nicht neu erfinden): `detail-frame.tsx` (Anatomie eines Datensatzes:
  `DetailHeader`, `RecordIcon`, `Card`, `SectionSep`, `DETAIL_PANE`, `DetailBody`, `ERP_HEAD_H`,
  `SpecSection`, `ReadField`, `DETAIL_MAXW`) · `form/kt-section.tsx` (`KtField`, `KtDate`,
  `KtSelect`) · `history.tsx` (`HistoryCard`, `ChangesSwitch`) · `controls.tsx`
  (`inputClass` – die eine Feldform –, `Label`, `Segmented`, `Dialog`) · `fields.tsx` (`StatusDot`,
  `MICRO_LABEL`) · `hints.tsx` (die eine Hover-Blase) · `module-ui.tsx` (`ActionButton`, `LedgerRow`,
  `Amount`, `ValueBar`) · `object-select.tsx` (jedes Referenzfeld) · `form/field.tsx` (jedes
  Eingabefeld) · `skeleton.tsx` (Laden = die graue Form dessen, was kommt). Regeln und die ganze
  Liste: `frontend/CLAUDE.md`.

## 8. E-Mail

**Eine Vorlage für jede Mail des Hauses – wie ein Brief** (`mail_layout.compose`, Inhaber 28.11.2026):
**Briefkopf** – links INEXXIO mit Unterzeile «Kranbau · Fahrzeugbau · Service»
(`inexxio-horizontal-tagline-*`, 176 × 64 px, `frontend/public/mail/kopf.png` · `kopf-dark.png`),
rechts «ehemals HS Steiner» mittig dazu (unterste Zeile von `inexxio-stacked-tagline-*`, 157 × 12 px,
`ehemals.png` · `ehemals-dark.png`; am Handy darunter), eine Haarlinie · Betreff als Überschrift
(Inter Tight 700, 28 px) · Inhalt und «Beste Grüsse aus ‹Ort›» in der Schrift des Textes (Inter 17 px,
Ink) · eine Haarlinie · **Unterschrift**: Bild rund (56 px, Foto oder Initialen, `services/portrait.py`),
daneben Name, E-Mail des Postfachs, Telefon · ein Streifen als kleine Werbefläche (Bild, Stichwort in
Grau-600, Titel, Satz, Link) · unter der Karte die **Fusszeile** (Gesellschaft, Anschrift, E-Mail,
Website; 12 px, Grau-600). Farben nur aus den Tokens (Ink Grau-950, Text Grau-700, leise Grau-600,
Haarlinie Grau-200); kein Rot ausser im Logo. Kästen 8 px, Knöpfe 6 px in Ink; Links öffnen ein neues
Fenster; hell und dunkel. Gruss und Streifen stehen in `website/src/config/inquiry.mjs` (`letter`, je
Sprache). **Mindestbreite** des Logos mit Unterzeile in der Mail: 176 px (sonst 240 px, §10).

## 9. Papier (A4)

**Eine Vorlage für jedes Papier** (`a4.py`: Offerte, Auftragsbestätigung, Rechnung, Quittung,
Stornierung, Gutschrift, Mahnung, AGB, Datenschutz, Impressum): A4, Ränder 20 mm, der Dokumenttyp
gross und blass oben links, das Logo (32 mm) oben rechts, links die Anschrift (Fensterkuvert), rechts
die Fakten; Positionen mit Seriennummer, Beträge rechtsbündig und tabellarisch; **der Absender steht
einmal – in der Fusszeile** (Name, Sitz, MWST-Nummer, Seite x/n). Rot nur im Logo. Die Schrift steckt
im Dokument, die Seiten sind echte A4-Seiten (der Download hat so viele Seiten, wie «Seite x/n» sagt).

## 10. Logo

**Logo v5 «F1»** (Oktober 2026): Pfeil-E, das verschachtelte XX, der rote Schwung; O als gerundetes
Rechteck. **Nie umfärben, verzerren, nachbauen** – eine Änderung geht über den Generator
(`reference/assets/logo/generator/`, Kopien und Masse: dessen README).

| Datei | Wo |
|---|---|
| `inexxio-stacked-light` · `-dark` | **Im Einsatz auf Website, Konto und ERP:** Kopf, Mobil-Menü, Fuss (`Lockup.astro`, Kopie `website/public/logo/inexxio-ehemals-hs-steiner*.svg`), Anmeldung, Vorschaubild. 60 % INEXXIO : 40 % «ehemals HS Steiner». |
| `inexxio-horizontal-light` · `-dark` | Wortmarke allein: Papiere (`backend/app/assets/logo.png`), Laufkatze der Kran-Szenen, der Schriftzug im Fuss (`schriftzug-fuss.svg`). |
| `inexxio-symbol-red` | **Favicon** (Website `favicon.svg`, ERP `app/icon.svg`, PNG-Abzüge `make-assets.mjs`). |
| `inexxio-*-mono` | Einfarbig Ink: Gravur, Typenschild, Stempel. |
| `inexxio-symbol*`, `inexxio-app-icon`, `inexxio-*-red` | Symbol auf bekanntem Grund, App-Icon, auf Logo-Rot. |
| mit Unterzeile «Kranbau · Fahrzeugbau · Service» | Nur im Artefakt (Gruppe «Logos»); daraus das Logo der Mail. |

Schutzraum rundum ≈ ¼ der Versalhöhe; Mindestbreite Wortmarke 96 px, gestapelt 120 px, mit Unterzeile 240 px (in der Mail 176 px, §8), Symbol
16 px; nur auf Weiss, hellem Grau, Ink oder Logo-Rot. Kein zweiter Schwung neben dem Logo.

## 11. Schreiben

- **Sie**, kurze Sätze, eine Sache je Satz, Nutzen vor Aufzählung. Kein Werbe-Superlativ, kein
  Ausrufezeichen, kein Emoji. Versprechen so, dass man sie prüfen kann.
- Die Marke heisst **INEXXIO** (Versalien, auch im Fliesstext).
- **Oberfläche:** Knopf = Verb («Speichern», «Auftrag freigeben») · Bestätigung = Partizip
  («Gespeichert») · Fehler = ein Satz an der Stelle, der sagt, was zu tun ist, mit der Sache in «»
  · leer = «—» (`NOTHING`).

## 12. Das System ändern

1. Einen Wert ändern: nur in `colors_and_type.css`. Website und Frontend bauen ihn mit.
2. Ein neues Token nur, wenn es jemand liest – der Wächter verlangt es.
3. Einen neuen Website-Baustein: aus den Bausteinen §6 zusammensetzen; erst wenn keiner passt, ein
   neuer – mit Kopfkommentar und einer Zeile in §6.
4. Danach das Artefakt nachziehen (README, Tokens, Komponente).
5. Hinsehen, nicht nur bauen: eine unbekannte Tailwind-Klasse oder CSS-Variable erzeugt still
   nichts (`bg-dark` gibt es nicht, `bg-bg-dark` schon).
