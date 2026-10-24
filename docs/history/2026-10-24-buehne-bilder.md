# 24.10.2026 – Bühne der Startseite mit KI-Bildern

**Auftrag:** Die drei Symbolbilder der Bühne «Ihre Aufgabe. Unsere Lösung.» durch KI-Bilder
ersetzen; Prompts im Stil der Titelbilder (graue Konstruktionszeichnung, nur das, was wir
dazubauen, echt und rot).

**Gemacht**
- Prompts: Säulenschwenkkran mit Rohrgreifer · Lastwagen mit Kippbrücke · Minibagger mit
  Anbau-Rüttelplatte. Verworfen für Fahrzeuge: Aufbau-Modul mit Werkzeugträger (wirkte seltsam),
  Schneepflug vorne (gewünscht war ein Aufbau hinten).
- `home/SpecialStage`: ein Feld trägt `illo` (Zeichnung) oder `image` (Bild, `<Picture>` avif/webp);
  die Startseite nimmt die drei Bilder als Vorgabe. Trommeltausch und Heukrananlagen unverändert.

**Gemessen**
- Freigestellt (WebP/AVIF mit Transparenz) wog die Startseite 1050–1183 KB (Budget 1024 KB) – die
  feinen grauen Linien machen den Alphakanal teuer. Auf Weiss (JPG-Quelle, Rand auf reines Weiss
  gesetzt): 874 KB.
