# Favicon der Testumgebung

Orange wie das «DEV»-Band im Kopf (`--amber-500`), das Logo weiss. Der Deploy kopiert diese
Dateien (`favicon.svg`, `favicon-32.png`, `favicon-192.png`, `favicon.ico`, `apple-touch-icon.png`;
neu erzeugt mit `node scripts/make-assets.mjs --icons`) nur bei `site_env=dev` über die normalen (`.github/workflows/deploy.yml`, Schritt
«Favicon der Testumgebung») – Produktion zeigt immer das rote Favicon.
