// ►►► Überträgt ins ERP (Backend und Frontend), was dort dieselben Wörter braucht. ◄◄◄
//
//   node scripts/export-erp.mjs           schreibt alle Abdrucke  (npm run export:erp)
//   node scripts/export-erp.mjs --check   bricht ab (Exit 1), wenn eine veraltet ist (CI)
//
// 1. backend/app/assets/website_contact.json – das Vokabular der Anfrage: der Endpunkt
//    backend/app/routers/contact.py prüft gegen DIESELBEN Listen und Muster wie das Formular
//    im Browser, die Nachricht im ERP trägt dieselben Beschriftungen und denselben Betreff
//    (services/inquiry), und die Eingangsbestätigung spricht mit den Wörtern der Website.
// 2. frontend/src/lib/site-meta.json – Name und Satz für die Metadaten des Konto-/ERP-
//    Bereichs. Kopf und Fuss sind die der Website selbst (scripts/export-shell.mjs, Entscheid 60).
//
// 3. frontend/public/brand/inexxio-ehemals-hs-steiner.svg – das Logo für den
//    Anmeldedialog des ERP. Ein Abdruck von public/logo/, damit Konto und ERP dasselbe
//    Zeichen tragen und es auch ohne die Website (npm run dev im Frontend) da ist.
//
// Die Quelle bleibt src/config (site.mjs, inquiry.mjs, newsletter.mjs) und public/logo – die Dateien
// drüben sind ihr Abdruck.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// ►►► Der Abdruck baut auf den VORGABEN, nie auf den Angaben eines früheren Builds. ◄◄◄
// Er ist der DB-freie Ausweg des Backends (503-/429-Seite, mailto): lag lokal noch
// src/config/erp-contact.json, landeten dessen Nummern im Abdruck, und `--check` schlug in
// der CI (ohne die Datei) fehl. Darum wird site.mjs erst NACH dem Schalter geladen.
process.env.SITE_ERP = '0';
const { site, contactEmail } = await import('../src/config/site.mjs');
const { inquiry } = await import('../src/config/inquiry.mjs');
const { newsletter } = await import('../src/config/newsletter.mjs');
const { formVocab } = await import('../src/lib/inquiry-vocab.mjs');
const { plain } = await import('../src/lib/text.mjs');

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const TARGET = resolve(ROOT, '../backend/app/assets/website_contact.json');
const SHELL = resolve(ROOT, '../frontend/src/lib/site-meta.json');
const LOGOS = ['inexxio-ehemals-hs-steiner.svg'];
const BRAND = resolve(ROOT, '../frontend/public/brand');

const v = formVocab();
const mail = inquiry.mail;

const data = {
  _comment:
    'Generiert aus website/src/config (site.mjs, inquiry.mjs, newsletter.mjs) mit «npm run export:erp» – nicht von Hand ändern.',
  brand: { name: site.brand.name, formerly: plain(site.brand.formerly), full: plain(site.brand.full) },
  phone: { display: site.phone.display, e164: site.phone.e164 },
  email: contactEmail(),
  pages: { thanks: '/kontakt/danke' },
  photos: inquiry.photos,
  minSeconds: inquiry.minSeconds,
  limits: inquiry.limits,
  labels: v.labels,
  sourceLabel: inquiry.sourceLabel,
  messages: v.messages,
  patterns: v.patterns,
  subject: v.subject,
  mail: {
    confirmSubject: plain(mail.confirmSubject),
    confirmIntro: plain(mail.confirmIntro),
    confirmNext: plain(mail.confirmNext),
    confirmMore: plain(mail.confirmMore),
    kicker: mail.kicker,
    copyTitle: mail.copyTitle,
    factCompany: mail.factCompany,
    factPhone: mail.factPhone,
    factPhotos: mail.factPhotos,
    photoOne: mail.photoOne,
    photoMany: mail.photoMany,
    nextTitle: mail.nextTitle,
    received: mail.received,
    urgent: plain(mail.urgent),
  },
  newsletter: Object.fromEntries(Object.entries(newsletter).map(([k, t]) => [k, plain(t)])),
};

/**
 * Name und Satz für die Metadaten des Konto-/ERP-Bereichs (Titel, Beschreibung). Kopf und
 * Fuss selbst kommen NICHT von hier – sie sind die der Website (scripts/export-shell.mjs).
 */
const shell = {
  _comment:
    'Generiert aus website/src/config/site.mjs mit «npm run export:erp» – nicht von Hand ändern. Nur Name und Satz für die Metadaten; Kopf und Fuss liefert scripts/export-shell.mjs.',
  brand: { name: site.brand.name, full: plain(site.brand.full), legalName: plain(site.brand.legalName) },
  claim: plain(site.footer.claim),
};

const outputs = [
  [TARGET, `${JSON.stringify(data, null, 2)}\n`],
  [SHELL, `${JSON.stringify(shell, null, 2)}\n`],
  ...LOGOS.map((f) => [resolve(BRAND, f), readFileSync(resolve(ROOT, 'public/logo', f), 'utf8')]),
];
const rel = (/** @type {string} */ p) => p.replace(resolve(ROOT, '..') + '/', '');

if (process.argv.includes('--check')) {
  const stale = outputs.filter(([file, json]) => (existsSync(file) ? readFileSync(file, 'utf8') : '') !== json);
  if (stale.length) {
    for (const [file] of stale) {
      console.error(`export-erp: ${rel(file)} ist veraltet – «npm run export:erp» ausführen und committen.`);
    }
    process.exit(1);
  }
  console.log('export-erp: aktuell');
} else {
  for (const [file, json] of outputs) {
    writeFileSync(file, json);
    console.log(`export-erp: ${rel(file)} geschrieben`);
  }
}
