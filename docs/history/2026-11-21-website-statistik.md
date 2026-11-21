# Website-Statistik (21.11.2026)

**Auftrag:** vor dem Go-live eine eigene Statistik statt Google Analytics; Vorschlag im Artefakt
«Website-Statistik INEXXIO», Etappe 1 und 2 freigegeben; sichtbar für alles Personal; statt
Länderliste eine Karte; jede Quelle muss erscheinen, auch eine unbekannte. Search Console
(Etappe 3) später, Monatsbericht per Mail nicht gewünscht.

**Gebaut:** `site_hits` + `site_salts` (Migration 191, nicht im Log), `services/site_stats`
(Meldung, Anfrage/Newsletter, Tagesschlüssel, Aufräumen im Takt), `site_stats_view` (Ableitung),
`domain/site_sources` (Quelle beim Lesen benannt; Unbekanntes = Rechnername), Route
`POST /api/v1/public/page` (Text-JSON über `sendBeacon`, immer 204) und `GET /erp/site-stats`,
Skript `website/src/scripts/stats.ts`, Reiter «Website» am Betreiber mit Europakarte
(`lib/europe-map.ts` aus Natural Earth 10m, vereinfacht, an der Karte abgeschnitten, 33 KB).
Datenschutzerklärung (Fassung 21.11.2026, Ziff. 2 und 3) nachgezogen.

**Entscheide unterwegs**
- **Rohdaten statt Summen**: die Kennung eines Besuchs gilt einen Tag und ist danach keiner
  Adresse mehr zuzuordnen (Schlüssel gelöscht) – die Zeilen sind damit ohne Personenbezug und
  dürfen bleiben (800 Tage). Keine Verdichtung, kein zweiter Weg durch die Daten.
- **Eine Anfrage trägt keine Kennung**, nur Einstieg und Quelle – sonst wäre der Rest des Besuchs
  mit einer Person verbunden.
- **Endpunkt `/public/page`** statt `/hit`/`/collect` (Werbeblocker sperren solche Pfade).
- **Text statt `application/json`** im Beacon: Chrome weist `sendBeacon` mit Typen ausserhalb
  der CORS-Ausnahmen ab.
- `visitor.allow_send` nimmt eine eigene Gesamtgrenze (`total`); Vorgabe bleibt `GLOBAL_LIMIT`
  (zur Laufzeit gelesen – ein Test setzt sie herab).
- Personal zählt nicht (Anzeige-Cache `data-account="staff"`); wer testen will: privates Fenster.
