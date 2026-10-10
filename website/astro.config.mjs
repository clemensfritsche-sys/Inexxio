// @ts-check
import { defineConfig } from 'astro/config';
import { satteri } from '@astrojs/markdown-satteri';

/**
 * SITE_MODE   preview (Standard) | live – siehe README.md
 * SITE_URL    wohin DIESER Build ausgeliefert wird (Canonical, Sitemap, Open Graph).
 *             Im Modus «live» muss er eine https-Adresse sein.
 */
const MODE = process.env.SITE_MODE ?? 'preview';
if (MODE !== 'preview' && MODE !== 'live') {
  throw new Error(`SITE_MODE muss «preview» oder «live» sein, nicht «${MODE}».`);
}
const SITE_URL = (process.env.SITE_URL ?? 'http://localhost:4321').replace(/\/+$/, '');
if (MODE === 'live' && !SITE_URL.startsWith('https://')) {
  throw new Error(`Modus «live»: SITE_URL (${SITE_URL}) muss eine https-Adresse sein.`);
}

export default defineConfig({
  site: SITE_URL,
  // Dieselbe URL-Form wie das ERP auf derselben Firebase-Site (cleanUrls, ohne Slash):
  // /krane/reparatur wird als krane/reparatur.html ausgeliefert.
  trailingSlash: 'never',
  build: {
    format: 'file',
    // Ein gemeinsames Stylesheet, vom Browser gecacht – und kein Inline-<style>, damit die
    // strenge Content-Security-Policy der Website keine Ausnahme braucht.
    inlineStylesheets: 'never',
  },
  compressHTML: true,
  // Bereichsstile per Klasse: ein `class` an einer Kind-Komponente (z. B. <Rich class="…">)
  // trägt den Bereich der Eltern mit – mit dem Standard «attribute» griffe das Stil der
  // Eltern-Komponente auf diesem Element nicht.
  scopedStyleStrategy: 'class',
  devToolbar: { enabled: false },
  prefetch: false,
  markdown: {
    // Keine «typografischen» Ersetzungen: «CHF 1'200.–» bleibt, wie es geschrieben ist.
    processor: satteri({ features: { smartPunctuation: false } }),
  },
  vite: {
    define: {
      __SITE_MODE__: JSON.stringify(MODE),
      __SITE_URL__: JSON.stringify(SITE_URL),
    },
    build: {
      // Skripte immer als eigene Datei – ein eingebettetes Skript bräuchte eine
      // CSP-Ausnahme ('unsafe-inline').
      assetsInlineLimit: 0,
      // EIN Stylesheet für die ganze Website (rund 13 KB gzip): vorher lud jede Seite ein
      // Dutzend Teil-Dateien, jede davon blockiert das erste Zeichnen. Gemessen mit
      // Lighthouse mobil: LCP 2.1–2.4 s → 1.5–1.8 s; ab der zweiten Seite aus dem Cache.
      cssCodeSplit: false,
    },
    server: {
      // Lokal: das Formular spricht mit dem lokal laufenden Backend (uvicorn :8000).
      proxy: { '/api': 'http://127.0.0.1:8000' },
    },
  },
});
