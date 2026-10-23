# 2026-10-23 – Menü-Kacheln mit Titelbild

**Was:** Im Kopf- und Mobil-Menü zeigt jede Kachel das Titelbild ihrer Seite statt der Zeichnung; ohne
Titelbild bleibt die Zeichnung (WEBSITE_PLAN Entscheid 126). Probe vorher als Artefakt
«Kopf-Menü – Probe Titelbilder» (heute ↔ Probe, Desktop und Handy), vom Auftraggeber freigegeben.
- Neu `src/lib/titles.ts`: Pfad → Titelbild, EINE Liste. Die neun Seiten mit `StageHero` holen ihr Bild
  von dort (`pageTitle`) statt es selbst zu importieren; `Header.astro` nimmt `titleImage` und rechnet es
  klein (480 px WebP, Qualität 70).
- **Gemessen:** mit den Bildern im Menü wog die Startseite 1406 KB (Budget 1024 KB) – die Kachelreihe war
  nur unsichtbar und lud mit jeder Seite. Jetzt ist sie bis zum ersten Berühren des Kopfs nicht im
  Layout (`display: none`, reines CSS): beim Laden 0 Menübilder, nach dem Berühren laden sie.
  `check-site` zählt Menübilder darum nicht mehr zum Startseitengewicht (Startseite 848 KB).

**Verworfen:** Bilder per Skript erst beim Öffnen setzen – das Menü ginge ohne JS ohne Bilder auf, und
die CSS-Lösung lädt früh genug (beim Weg der Maus zum Menüpunkt).
