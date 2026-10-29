# 24.10.2026 – Titel ohne «ehemals HS Steiner», Beschreibungen neu

**Auftrag:** Nach der Durchsicht der Website: «(ehemals HS Steiner)» darf in Titeln und an
SEO-wichtigen Stellen nicht mehr stehen, im Fliesstext schon. Die sieben Meta-Descriptions
ausserhalb 140–155 Zeichen neu schreiben. Die E-Mail im Fuss muss aus dem ERP kommen.

**Gemacht**
- `Base.astro`: Titel-Zusatz `| INEXXIO`, `og:site_name` und `og:image:alt` mit dem Namen allein.
- `seo.mjs`: `WebSite.name` = INEXXIO; `Organization.alternateName` behält «INEXXIO (ehemals HS
  Steiner)», «HS Steiner» usw. – dort gehört der alte Name für Suchmaschinen hin.
- `llms.ts`: Kopf `# INEXXIO`; «früher HS Steiner» steht weiter in der Zeile «Rechtlicher Name».
- Zusammenfassungen (JSON-LD-Beschreibungen, llms-full) beginnen mit `{{brand.name}}`.
- Neun Beschreibungen neu (Datenschutz, Impressum, Fahrzeugtechnik, Karriere, Kontakt, Über uns,
  Krane nach Mass, Verschleissteile, Service) – alle 140–155 Zeichen, keine mit «ehemals».
- Wächter in `check-site`: Titel, Meta-Description oder `og:title` mit «ehemals HS Steiner» → Abbruch.
  Gegengeprüft: ein von Hand eingesetzter Titel auf /service bricht ab.

**Nicht geändert**
- Logo und seine `aria-label` (das Logo trägt «ehemals HS Steiner» sichtbar).
- E-Mail: Der Code liest sie schon aus dem ERP (`GET /api/v1/public/contact` beim Build und im
  Browser). Die Website zeigt die alte Adresse nur, weil die Betreiber-Gesellschaft im ERP noch
  keine E-Mail hat (sie entsteht durch Verbinden des Postfachs). Die alte Adresse bleibt als
  Ersatz, weil Impressum, Datenschutz und Bewerbung eine Adresse brauchen.
