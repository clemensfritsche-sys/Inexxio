# Handy-Menü mit einer Ebene (21.10.2026)

Entwurf im Design-Canvas «Speziallösungen – Ist und Vorschlag» (Boards «Handy-Menü – Ist» und
«Handy-Menü – Vorschlag»), umgesetzt in `components/Header.astro` und `scripts/header.ts`.

## Was
- Statt zwei Ebenen (Liste → hereingleitende Unterseite mit Zurück-Pfeil) EINE Ebene: jeder
  Punkt klappt eine Reihe Karten zum Wischen auf, die nächste Karte schaut herein. Beim Öffnen
  ist der erste Punkt offen; höchstens einer ist offen.
- Punkte mit Unterseiten beginnen mit «Alles zu …» – dunkle Karte, Stapel der Zeichnungen der
  Unterseiten, roter Pfeil. Ersetzt den unauffälligen Titel-Link der alten zweiten Ebene.
- Alle Karten gleich gross, auch bei Punkten mit nur einer Seite.
- Sprache: Knopf «Deutsch» unten, klappt Karten mit grossen Sprechblasen auf (wie die Kacheln im
  breiten Kopf). Telefon als Glas-Knopf.
- Ohne JavaScript bleiben die Punkte Links auf ihre Seite; der erste ist offen gerendert.
