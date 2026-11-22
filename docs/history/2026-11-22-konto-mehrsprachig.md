# Konto und Anmeldung mehrsprachig (22.11.2026)

**Auftrag:** «Die Profileinstellungen sind nicht in allen Sprachen verfügbar … das ERP ist bewusst
nicht übersetzt, aber es ist der Teil vom ERP, auf den Kunden Zugriff haben.»

**Gebaut**
- Sprache = die der Website-Seite, von der man kommt: die Website verlinkt Konto, Anmelden und
  Abmelden je Sprache mit `?lang=` (`Header.astro`); die Anmeldung erkennt sie auch am Ziel
  `?from=/fr/…`. EINE Regel im ausgelieferten HTML (`site-shell.ShellLanguage`) setzt
  `html[data-lang]` und tauscht Kopf und Fuss – vor dem Zeichnen, ohne Flackern.
- Kopf und Fuss je Sprache: `languages.mjs` legt die Fehlerseite jeder Sprache (mit übersetzten
  Links) nach `.build/shell-<sprache>.html`, `export-shell.mjs` schreibt sie als `langs` in `shell.json`.
- 149 Texte (Konto, Adressbuch, Adress- und Firmenfeld, Passkeys, Anmeldung, Magic-Link-Rückkehr,
  Abmelden, Passkey-Hinweis) über `t()`; Wörterbücher fr/en/it; Wächter `scripts/i18n.test.mjs`.
- Die Anmeldemail (`services/login_link`) in vier Sprachen; der Link führt mit `?lang=` zurück
  (immer gesetzt – vor dem `lang`, das Firebase selbst anhängt).

**Bewusst nicht:** das ERP; Meldungen des Servers (Abweisungen, Newsletter-Wortlaut); Datum bleibt
`TT.MM.JJJJ` (im Konto zeigen Passkeys den Tag statt «vor 3 Tagen»); `/dokument` und die Papiere.

**Geprüft:** Chromium gegen den Export: `/login?lang=fr|en`, `?from=/it/…` in der Sprache (Kopf,
Fuss, Dialog, `html lang`), ohne Zeichen deutsch; `/konto?lang=fr` bleibt beim Weg zur Anmeldung
französisch.
