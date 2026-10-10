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
