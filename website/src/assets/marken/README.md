# Marken-Logos (Fahrmischer)

Ein Logo je Marke aus `config/site.mjs` (`marks.mixers`) als PNG mit durchsichtigem Grund,
Dateiname = Marke klein, Leerzeichen → «-»: `putzmeister.png`, `liebherr.png`, `cifa.png`,
`schwing-stetter.png`, `belloli.png` (120 px hoch, Rand weggeschnitten).

Das Marken-Band (`components/fahrzeug/BrandBand.astro`) zeigt das Logo in schwachem Grau, beim
Zeigen in Farbe, und gleicht die Grösse über die Fläche an; fehlt die Datei, steht der Name.
