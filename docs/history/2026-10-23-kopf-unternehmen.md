# 2026-10-23 – Kopf mit Platz: «Unternehmen» statt «Über uns» und «Kontakt»

**Was** (WEBSITE_PLAN Entscheid 127): Die Hauptzeile hat fünf statt sechs Punkte. «Über uns» heisst
«Unternehmen» und trägt Über uns · Ratgeber · Karriere · Kontakt; «Kontakt» als eigener Punkt ist weg
(Telefon und «Anfrage stellen» rechts im Kopf sind der Weg zu uns). Platz für einen späteren Shop.
- `config/site.mjs`: `about.label` = «Unternehmen», `selfLabel` «Über uns» für die Übersichtskachel,
  Kontakt als Unterpunkt; `site.menu` (nur noch Kontakt) entfernt. Kopf, Mobil-Menü und Fuss lesen
  dieselbe Liste – der Fuss nennt in der Spalte «Unternehmen» jetzt auch «Über uns».
- `Header.astro`: die eigene Kontakt-Kachel ist weg; «Über uns» zeigt ihr eigenes Bild statt eines
  Stapels; ein Punkt gilt als aktuell, wenn man auf ihm **oder einer seiner Unterseiten** steht
  (vorher blieb «Über uns» auf /ratgeber, /karriere ohne Strich).
- Unverändert: Sprachwahl im Kopf (kommt bald), Brotkrumen der Seiten («Über uns»), Fuss-Spalte mit
  Anschrift (Kontakt), Prüfungen «jede Seite über das Menü erreichbar» und «Fuss = Kopf» (grün).

**Nicht gebaut:** Shop-Symbol und «Meine Produkte» im Konto – es gibt noch keinen Shop, und ein Knopf,
der nichts tun kann, steht nicht da.
