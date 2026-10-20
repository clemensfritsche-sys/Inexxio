# Fotos

Echte Fotos hierher legen (JPG, lange Seite ≥ 2400 px, sprechender Dateiname wie
`kranpruefung-brueckenkran-tuttwil.jpg`) und in `src/config/photos.mjs` beim passenden
Eintrag unter `file` eintragen. Der Build erzeugt daraus AVIF/WebP in mehreren Breiten.

Keine Stockfotos mit Menschen, keine KI-generierten Bilder.

Bis dahin stehen in `samples/` gekennzeichnete **Beispielbilder** aus Wikimedia Commons
(freie Lizenzen; Urheber und Lizenz in `src/config/photo-credits.json`, Alt-Texte in
`src/config/photo-samples.mjs`). Ein echtes Foto ersetzt sein Beispiel automatisch; ist keines
mehr in Gebrauch, verschwindet auch der Bildnachweis. Neue Beispiele holt
`scripts/sample-photos.mjs` über den Actions-Job `sample-photos.yml`.

## Videos

Ein Video (MP4, H.264, ohne Ton, kurz, höchstens etwa 8 MB) nach `public/video/` legen und in
`src/config/photos.mjs` beim Foto der Stelle `video: 'name.mp4'` eintragen. Es läuft stumm in
Schleife über dem Foto; das Foto bleibt Standbild (vor dem Laden, bei «reduzierter Bewegung»).
Die Bühne der Startseite ist das Foto `heukran-einsatz` (`src/content/start.ts`, `hero.photo`).
