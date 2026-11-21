# 2026-10-21 – Website v4: Feinschliff nach dem ersten Testen

## Was
- **Bühne** füllt das Fenster (`100svh`, Rückfall `100vh`) – vorher bei 960 px gedeckelt, auf
  hohen Bildschirmen blieb unten ein weisser Streifen.
- **Menü verschwand beim Weg ins Panel (Sprache, Konto)** – Grundursache: die Knöpfe waren
  40 px hoch, das Panel beginnt bei 64 px; im 12-px-Spalt verlor der Punkt den Zeiger und
  schloss (nur beim langsamen Fahren, darum «manchmal»). Lösung: `.is-open` ist der EINE
  Zustand (`:hover` nur noch ohne JS), ein Punkt schliesst erst, wenn der Zeiger die ganze
  Kopf-Karte verlässt (150 ms), und die Werkzeug-Punkte reichen über die volle Zeilenhöhe.
- **Warum**: «Gleicher Standort, gleiche Telefonnummer» entfällt; statt «100 % dokumentiert»
  steht «50 % – übernehmen wir, wenn Sie nicht zufrieden sind». Die Zahlen zählen beim
  Hineinscrollen hoch (`scripts/countup.ts`, Breite vorher reserviert).
- **Ratgeber-Karussell** mit der Maus ziehbar (`scripts/carousel.ts`, `data-rail`), rastet
  danach ein; ein Zug löst keinen Klick aus.
- **Fragen auf allen Seiten** im Layout der Startseite (`FaqStage`): das Bild wählt sich nach
  dem Thema der Frage (Garantie, 365, Telefon, Übergabe), sonst die Zeichnung der Seite.
  `Faq.astro` entfernt.
- **Scrollbar** der Website schmal und halbtransparent (nur `html[data-site]`).
- **Anfrage**: grosses weisses Feld mit deutlichem Schatten; «Foto anhängen» und ein runder
  Senden-Pfeil sitzen im Feld. Beide Schritte liegen in derselben Fläche und blenden über –
  nichts darunter springt (gemessen: 0 px).

## Gemessen
Website `npm test`, `astro check`, Build mit `check-site`, `export-erp --check`; Frontend
`type-check`, `lint`, `test`, `build`; Backend-Suite mit Datenbank (748 grün). In Chromium:
langsamer Weg vom Sprach- und Konto-Knopf ins Panel bleibt offen, Verlassen schliesst.

## Zweite Runde (gleicher Tag)
- **Video**: kein Zoom mehr auf Videos (das Skalieren liess sie ruckeln); Ton entfernt und neu
  kodiert (10,5 → 3 MB). Sichtbar wird es erst, wenn es läuft – verweigert ein Handy das
  automatische Abspielen (Stromsparmodus), bleibt das Foto statt eines durchgestrichenen
  Play-Knopfs. Videos nur in Bühne und Seitenkopf (`Media motion`).
- **Kopf**: harte Kanten links/rechts beim offenen Menü kamen vom Zuschnitt der Karte
  (`overflow-x: clip` schnitt den Schatten ab). Zuschnitt weg, die Panels gleiten nur noch
  24 px – so viel Rand hat die Karte, nichts ragt hinaus.
- **Handy-Kopf**: rechts Konto · Telefon · Menü-Symbol (vorher rückte das Konto-Symbol nach
  links, sobald man angemeldet war). Kein Warenkorb (kein Shop).
- **Untere Leiste** auf dem Handy: schwebende Glas-Leiste.
- **Bereiche**: Masse der Kran-Bühne werden nicht mehr in jedem Bild gelesen (ResizeObserver),
  die Karten sind `contain`-iert → das Wachsen läuft flüssig; die Trommel fährt nur noch knapp
  über das Fahrzeug, und kein Haken hängt je über der Katze.
- **Anfrage**: Platzhalter «Erzählen Sie uns kurz, worum es geht – wir freuen uns auf Ihre
  Nachricht.»
