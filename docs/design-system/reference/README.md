# Referenz (read-only) — nicht direkt importieren

Diese Dateien sind der Roh-Export aus **Claude Design** und dienen als **Vorlage**,
nicht als produktiver Code:

- **`mockups/Instanz Detail.dc.html`** + **`Instanz Detail Mobile.dc.html`** —
  die HTML/CSS-Mockups der neu gestalteten Instanz-Detailseite. Vorlage für das
  Redesign von `frontend/src/components/erp/instance-detail.tsx` (pixelgenau
  nachbauen, aber mit den Design-System-Tokens/Utilities statt Inline-HTML).
- **`components/*.tsx`** — von Claude Design generierte Referenz-React-Komponenten
  (Button, Badge, Tabs, Input, Select, Process-Tracker, Item-Detail-Form). Zeigen die
  gewünschte Optik/API. **Nicht 1:1 in die App kopieren** — die App hat eigenes,
  etabliertes Vokabular in `frontend/src/components/erp/fields.tsx` (StatusBadge,
  PanelHeader, PrimaryButton …). Ideen übernehmen, bestehende Bausteine bevorzugen,
  und Farben auf die Tokens ziehen (die Referenz nutzt teils noch generische
  slate/blue-Klassen).

Produktive Quelle der Wahrheit ist ausschliesslich
`frontend/src/styles/design-system/colors_and_type.css`; Regeln in
`docs/design-system/README.md`.
