# 2026-10-25 · Rechtstexte als A4-Dokumente, eine AGB, kein Bildnachweis

> Rundenbericht. Was gilt, steht in `CLAUDE.md` (Website · Rechtstexte).

## Weisung
- Eine AGB für Geschäfts- und Endkunden – nicht zwei Dokumente pflegen.
- Der Download der AGB ergab einen «elendslangen» Text auf einer Seite statt A4-Seiten.
- Datenschutz wie die AGB-Seite, Inhalt komplett neu; Impressum ebenso im neuen Layout.
- Bildnachweis ganz entfernen, stattdessen «Foto fehlt».

## Umgesetzt
- `services/legal.py` ersetzt `services/agb.py`: eine Datei je Art und Fassung
  (`assets/legal/<art>/<datum>.md`), ein Text ohne Teile, Werte aus dem ERP (`{{firma}}` …,
  eine Zeile ohne Wert fällt weg).
- `document.py`: Rechtstexte werden auf dem Server in A4-Seiten geteilt (vorsichtige Schätzung:
  96 Zeichen je Zeile, 18.6 px je Zeile; ein Absatz nie geteilt, ein Titel nie allein). Gemessen
  im Browser: jedes Blatt genau 1123 px (A4), mindestens 50 px Luft bis zum Fuss; PDF-Seiten =
  Blätter (AGB 4, Datenschutz 3, Impressum 1; Rechnung mit AGB 5 – «Seite 1/5 … 5/5»).
- Die Schrift steckt im Dokument (woff2 als data-URL) – vorher lud jedes Dokument Google Fonts,
  was der Datenschutzerklärung widersprach.
- `GET /public/legal/{kind}` ersetzt `/public/agb`; Seiten `/agb`, `/datenschutz`, `/impressum`
  aus einer Komponente (`legal-page.tsx`). Die Website hat ihre Seiten Impressum/Datenschutz,
  `Legal.astro`, `lib/legal.ts` und `content/legal/` abgegeben (`site.erpPaths`).
- Beispielbilder (Wikimedia, 7 in Gebrauch, davon mehrere CC BY-SA) samt Nachweis, Holer-Skript
  und Actions-Job entfernt; ohne Foto steht der graue Rahmen «Foto fehlt».
- AGB neu als ein Text; Datenschutzerklärung neu (Website, Anfragen und E-Mail-Verlauf,
  Offerten/Rechnungen mit Link, Zahlungen, Konto mit Google-Adresssuche, Newsletter,
  Bewerbungen, Dienstleister, Rechte, Aufbewahrung 10 Jahre).

## Offen
- Rechtliche Durchsicht von AGB und Datenschutzerklärung durch eine Fachperson empfohlen.
