// ►►► Kopf und Fuss kommen von der Website – EINE Quelle (WEBSITE_PLAN Entscheid 60). ◄◄◄
//
// Der Website-Build legt sie in website/dist/_shell/shell.json ab (scripts/export-shell.mjs):
// HTML von Kopf und Fuss, das auf `.ix-shell` beschränkte Stylesheet und die Skripte. Dieses
// Skript übernimmt die Datei nach src/generated/site-shell.json (nicht im Repository), wo
// components/layout/site-shell.tsx sie liest.
//
// Fehlt der Website-Build (lokal, Typprüfung in der CI), entsteht eine leere Fassung: die
// Seiten bauen, nur ohne Kopf und Fuss. Mit SHELL_REQUIRED=1 (Deploy) ist das ein Fehler –
// ausgeliefert wird nie ein ERP ohne den Kopf der Website.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = resolve(ROOT, '../website/dist/_shell/shell.json');
const TARGET = resolve(ROOT, 'src/generated/site-shell.json');
const EMPTY = { _comment: 'Leer: website/dist fehlt (erst «npm run build» in website/).', header: '', footer: '', css: '', early: '', module: '', contact: '' };

mkdirSync(dirname(TARGET), { recursive: true });
if (existsSync(SOURCE)) {
  writeFileSync(TARGET, readFileSync(SOURCE, 'utf8'));
  console.log('site-shell: Kopf und Fuss aus website/dist übernommen.');
} else if (process.env.SHELL_REQUIRED === '1') {
  console.error('site-shell: website/dist/_shell/shell.json fehlt – zuerst die Website bauen (SHELL_REQUIRED=1).');
  process.exit(1);
} else {
  writeFileSync(TARGET, `${JSON.stringify(EMPTY, null, 2)}\n`);
  console.warn('site-shell: website/dist fehlt – leere Fassung (ohne Kopf und Fuss).');
}
