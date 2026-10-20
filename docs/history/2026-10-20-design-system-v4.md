# 2026-10-20 – Design System v4: kühles Grau, Glas, Website-Sprache

## Was
- **Grau:** die warme Skala (`--gray-*`, «one temperature for everything») ist durch ein
  kühles, neutrales Grau ersetzt – gleiche Token-Namen, neue Werte. Mit dabei: Elevation
  (Schattenfarbe), Dark-Theme-Werte, `--fg-on-dark`, `sand-*` (zeigt jetzt auf die
  Grauskala, war ungenutzt). Website, Konto und ERP übernehmen es über die Tokens.
- **Mitgezogen, wo Werte hart standen:** E-Mail-Vorlage (`mail_layout.py`, Test erweitert),
  Website-Zeichnungen (`assets/illustrations/*.svg`), `form.css`, Laufkatze in
  `HomeHero.astro`, die Schrift auf dunklen Flächen (`rgba(243,244,246,…)`), die
  Open-Graph-Bilder (`make-assets.mjs` neu laufen gelassen). **Nicht umgefärbt:** die Logos
  (Regel «nie umfärben»).
- **Glas:** Tokens `--glass-*` und die Helfer `.ix-glass` / `.ix-glass-dark` – nur Website,
  nie ERP.
- **Regeln:** README §3a «Website-Sprache v4» (eine Überschrift-Form, Rot nur für die
  Anfrage, Karten 16 px mit Text auf dem Bild, kein Kasten im Kasten, Glas, Muster,
  Bewegung), Wortregeln (kein «Fixpreis», keine «Werkstatt»). Skill und beide CLAUDE.md
  nachgezogen. `brand-foundations.md` neu geschrieben (die alte Fassung beschrieb ein
  Microliving-Konzept).
- **Vorlage:** die abgenommene Startseite aus dem Design-Artefakt «Website Startseite» liegt
  als `reference/mockups/Startseite v4.dc.html` (+ mobil).

## Warum
Entwurfsrunde am Design-Artefakt: Beige wirkt ruhig, aber «KI-mässig»; das kühle Grau mit
Glas (nach Porsche) wurde als Probe neben die alte Fassung gestellt und gewählt. Das Grau
gilt bewusst auch fürs ERP (ein System); Glas im ERP wurde ausdrücklich zurückgestellt.

## Gemessen
Website: `npm test`, `astro check`, `export-erp --check`, Build mit `check-site` grün,
`OFFENE_PUNKTE.md` unverändert; Startseite in Chromium angesehen (`--paper` = `#f5f6f7`).
Frontend: `type-check`, `lint`, `npm test`, `build` grün. Backend: `ruff`, die Suite ohne DB
(442 bestanden; die DB-Tests laufen in der CI).

## Offen
- Die Website trägt das neue Grau, aber noch **nicht** die neue Gestaltung der Startseite –
  das ist der nächste Schritt (Vorlage: `Startseite v4.dc.html`).
- «Fixpreis» und «Werkstatt» stehen noch in Website-Texten (Garantien, Übergabe,
  Speziallösungen); sie gehen mit dem Umbau raus.
