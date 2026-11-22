---
name: inexxio-design-system
description: >-
  VERBINDLICH bei JEDER UI-/Design-Arbeit an Inexxio (Website, Konto, ERP, E-Mail, Papiere) — vor
  dem Schreiben von JSX/TSX/Astro/CSS lesen. Nutze diese Skill immer, wenn du Oberflächen,
  Komponenten, Seiten, Styles, Farben, Layout, Knöpfe, Karten, Icons, Tailwind-Klassen, die
  Mail-Vorlage oder die Papier-Vorlage erstellst oder änderst. Liefert die Tokens (eine Quelle),
  die Regeln und die Bausteine, die es schon gibt. Trigger: "design", "UI", "Komponente", "Seite",
  "styling", "Farbe", "Layout", "Tailwind", "Button", "Karte", "Redesign", "Mail-Vorlage".
---

# INEXXIO Design System – Pflicht vor UI-Arbeit

1. **Lies `docs/design-system/README.md`** – die Regeln, wie sie gebaut sind (der Code ist die
   Wahrheit). Für die Website dort §6, fürs ERP §7 und `frontend/CLAUDE.md`, für Mails §8, für
   Papiere §9.
2. **Werte nur aus `frontend/src/styles/design-system/colors_and_type.css`.** Nie einen Hexwert,
   Radius oder Schatten in einer Komponente, in `globals.css` oder `tailwind.config.js` abschreiben.
   Die Website liest dieselben Werte unter eigenen Namen (`--ink`, `--line`, `--red`, generiert von
   `website/scripts/tokens.mjs`).
3. **Erst die Bausteine, dann Eigenbau**: Website `website/src/components/` (Liste README §6), ERP
   `detail-frame` · `controls` · `fields` · `hints` · `module-ui` · `object-select` · `form/field`.

## Das Wichtigste in Kürze
- **Farbe = Bedeutung.** Kühles Grau trägt die Fläche. **Rot** ist der eine laute Akzent – auf der
  Website **nur die Anfrage**, im ERP aktiv und echte Fehler; **nie in einer Überschrift**. **Slate**
  (`accent`) ist die leise Stimme im ERP.
- **Radien:** Bedienelemente 6 px (`rounded-ds-md`), Karten, Flächen, Bilder, Dialoge 8 px
  (`rounded-ds-lg`). Keine Pillen-Knöpfe.
- **Flach:** Haarlinien statt Schatten; Schatten nur, was schwebt.
- **Status trägt sein Wort** – im ERP als Etikett (`fields.StatusBadge`), in Zeilen Punkt + Wort
  (`fields.StatusDot`). **Icons nur Lucide**, kein Emoji.
- **ERP-Datensatz = Abschnitte wie im Konto** (`detail-frame.Card` = `.kt-sec`, weiss, keine Karte
  in der Karte); Felder grau ohne Rahmen (`inputClass`); **Art-Farben** `--type-*` nur in Symbol,
  Überschrift des Kopfs und gewählter Feed-Zeile.
- **Zahlen tabellarisch** (`.ix-tnum`), Schweizer Formate, Datum nur über `lib/when.ts`.
- **Website:** eine Überschrift-Form (`.v4-h2` + höchstens ein grauer Satz, linksbündig); Glas nur
  in der Kopfleiste, der Handy-Leiste und auf kleinen Knöpfen über Fotos; Text auf Fotos auf `.plate--dark`; kein Kasten im Kasten; Fotos zoomen beim
  Überfahren mit `.zoom-on-hover`; Karussells über `scripts/carousel.ts` (endlos). Jeder Text durch
  `t()` und in jeder Sprache.
- **Wörter:** nie «Fixpreis», nie «Werkstatt» («Standort», «Betrieb», «bei INEXXIO»).

## Wächter
`frontend/scripts/design.test.mjs`: jede `var(--x)` definiert · jede `ix-`-Klasse mit Stil · keine
Alt-Palette (`slate-*`, `blue-*`, `gray-*`, `#2563eb`) · **jedes Token wird gelesen** – ein neues
Token nur, wenn es jemand liest. Eine unbekannte Tailwind-Klasse erzeugt still nichts: hinsehen.

## Danach
Wer eine Regel oder einen Baustein ändert, zieht README §6–§10 nach – und das Artefakt
«INEXXIO Design System» (https://claude.ai/artifact/6CQGEWynpkcEskuDzVkKbn) zeigt es danach.
