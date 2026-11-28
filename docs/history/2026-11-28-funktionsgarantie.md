# 28.11.2026 – Funktionsgarantie statt Zufriedenheitsgarantie

**Warum:** Heiri: «zufrieden» lässt sich nicht prüfen und würde ausgenutzt. Ob etwas
funktioniert, lässt sich dagegen bei der Abnahme gemeinsam feststellen.

**Was jetzt gilt (vom Inhaber freigegeben):**
- Abschnitt: «Funktioniert und einsatzbereit mit Garantie.»
- Karte: «INEXXIO Funktionsgarantie» – «Funktioniert garantiert. Sonst übernehmen wir die Hälfte.»
- Versprechen: «Was in der Offerte steht, funktioniert. Sonst bessern wir nach – auf unsere
  Kosten. Klappt es trotzdem nicht, übernehmen wir 50 % des vereinbarten Preises.»
- Keine Frist für die Nachbesserung genannt (gewollt). INEXXIO 365 und die Gratis-Inspektion
  bleiben unverändert, ebenso die Grafik «50 % übernehmen wir».

**Wo geändert:** `website/src/content/promises.ts` (Karte, Frage), Leitsatz in
`config/site.mjs`, Startseite, Fahrzeugtechnik, Krantechnik, Speziallösungen – in allen vier
Sprachen (Glossar `website/src/i18n/README.md`: FR «garantie de bon fonctionnement», EN
«performance guarantee», IT «garanzia di buon funzionamento»). `FaqStage` erkennt die Frage am
Wort «Funktionsgarantie».

**AGB:** neue Vorlage `backend/app/assets/legal/agb/2026-11-28.md`, nur Ziffer 11 neu
(Funktion wie in Offerte/AB vereinbart, Abnahme gemeinsam, Nachbesserung auf eigene Kosten,
sonst 50 %, angerechnet auf Rechte aus Ziffer 10; ausgenommen u. a. Fehlbedienung, Verschleiss,
nicht Vereinbartes). Die Fassung vom 21.11. bleibt unverändert. **Ein Papier trägt die AGB, die
die Gesellschaft übernommen hat** – die neue gilt erst nach «Aus Vorlage übernehmen».

**Test:** `test_sale_from_offer_to_done` erwartete das Datum der neuesten *Vorlage* auf der
Offerte; richtig ist das Datum der *übernommenen* AGB (`legal.text_of`). Die Erwartung folgt
jetzt der Regel, nicht dem Zufall, dass beide gleich alt waren.

**Offen beim Inhaber:** Ziffer 11 rechtlich prüfen lassen; beim Release je eigener
Gesellschaft «Aus Vorlage übernehmen». Laufende Offerten behalten die alte Garantie.
