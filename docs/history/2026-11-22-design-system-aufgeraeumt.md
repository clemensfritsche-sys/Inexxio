# Design System aufgeräumt (22.11.2026)

**Auftrag des Inhabers:** Das Design System ist veraltet – Website, Mail- und Papiervorlagen sind neu,
die Regeln nicht. Das heutige Website-Design fest verankern, alles Veraltete und Ungenutzte löschen.

## Gemessen
- `colors_and_type.css`: **230 Tokens, 127 davon las niemand** (Frontend `var()`, Tailwind, Website
  über `tokens.mjs`, transitiv). Dazu 22 `.ix-*`-Klassen, von denen nur `.ix-tnum` benutzt war, und
  ein Dunkelmodus `[data-theme="dark"]`, den keine Seite setzt.
- Tailwind: `inexxio-bright`, `rounded-ds-xs`, `shadow-ds-xs/-sm/-lg` – 0 Verwendungen.
- Website: 10 übernommene Tokens ungelesen, 6 eigene Variablen ungelesen, tote Klassen
  `.section--dark`, `.section--paper`, `.dots` (Punktraster).
- Ein echter Fehler: `var(--gray-400)` auf der Website war nie definiert (Symbol in den Kacheln
  des Kopfs, «Aus der Praxis») – jetzt `--ink-4` (derselbe Wert).
- Doku: zwei Dateien mit Widersprüchen (Karten 16 px ↔ 8 px, Glas «nur Kopf» ↔ «Text auf Fotos,
  Felder»), Verweise auf `README §3a`, Mockups `Startseite v4(.mobil).dc.html` (350 KB), die den
  Stand vom Oktober zeigten (16-px-Karten, Glas-Akkordeon, Glas-Felder).

## Getan
- **Token-Datei neu**: zwei Schichten (Skalen → Rollen), nur, was gelesen wird (77 statt 230). Werte
  unverändert; umbenannt nur Namen, die der Code direkt las (`--color-primary-hover` →
  `--inexxio-red-hover`, `--color-border-focus` → `--border-focus`, `--elev-3/4` →
  `--shadow-lg/-xl`, `--color-ink-hover` → `--gray-800`).
- **Neuer Wächter** in `frontend/scripts/design.test.mjs`: jedes Token wird gelesen.
- **Eine Doku** `docs/design-system/README.md` statt README + `brand-foundations.md`: Regeln wie
  gebaut, Liste der Website-Bausteine, ERP, Mail-Vorlage, Papier-Vorlage, Logo, Schreiben.
- **Mockups gelöscht** (in der Git-Historie bis `4fbdb01`). Die Vorlage ist der Code.
- Skill, CLAUDE.md, frontend/CLAUDE.md, Kommentare in Website-Bausteinen nachgezogen.
- Das Artefakt «INEXXIO Design System» danach auf denselben Stand gebracht.

## Offen
- Das Logo mit Unterzeile «Kranbau · Fahrzeugbau · Service» gibt es nur im Artefakt (daraus das Logo
  der Mail); der Generator kennt es nicht. Die Website trägt das gestapelte Logo ohne Unterzeile.
