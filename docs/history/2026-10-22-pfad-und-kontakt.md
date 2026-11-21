# 2026-10-22 – Pfadangabe weg, Kontakt bildschirmhoch

**Was:** Die sichtbare Pfadangabe («Startseite / Service») entfällt jetzt auch am Desktop
(`Breadcrumbs.astro` gelöscht). Die strukturierte Fassung (BreadcrumbList im JSON-LD) bleibt.
Auf `/kontakt` füllt der Kontaktbereich den Bildschirm unter dem Kopf
(`.contact--main`, `min-height: calc(100svh - var(--header-h))`), der Fuss erscheint erst beim Scrollen.

**Warum:** Die Website ist flach (höchstens zwei Ebenen), der Kopf führt überall zurück.
Marken-Websites wie Porsche oder Apple zeigen auf Marketingseiten keine Pfadangabe. Für
Google zählt die strukturierte Fassung.
