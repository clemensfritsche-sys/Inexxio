// ►►► Überträgt, was ausserhalb der Website dieselben Wörter braucht. ◄◄◄
//
//   node scripts/export-contact.mjs           schreibt alle Abdrucke
//   node scripts/export-contact.mjs --check   bricht ab (Exit 1), wenn eine veraltet ist (CI)
//
// 1. backend/app/assets/website_contact.json – das Vokabular der Anfrage: der Endpunkt
//    backend/app/routers/contact.py prüft gegen DIESELBEN Listen und schreibt die E-Mails mit
//    DENSELBEN Wörtern wie das Formular im Browser.
// 2. frontend/src/lib/site-meta.json – Name und Satz für die Metadaten des Konto-/ERP-
//    Bereichs. Kopf und Fuss sind die der Website selbst (scripts/export-shell.mjs, Entscheid 60).
//
// 3. frontend/public/brand/inexxio-ehemals-hs-steiner.svg – das Logo für den
//    Anmeldedialog des ERP. Ein Abdruck von public/logo/, damit Konto und ERP dasselbe
//    Zeichen tragen und es auch ohne die Website (npm run dev im Frontend) da ist.
//
// Die Quelle bleibt src/config (site.mjs, inquiry.mjs) und public/logo – die Dateien
// drüben sind ihr Abdruck.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { site, contactEmail } from '../src/config/site.mjs';
import { inquiry } from '../src/config/inquiry.mjs';
import { formVocab } from '../src/lib/inquiry-vocab.mjs';
import { plain } from '../src/lib/text.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const TARGET = resolve(ROOT, '../backend/app/assets/website_contact.json');
const SHELL = resolve(ROOT, '../frontend/src/lib/site-meta.json');
const LOGOS = ['inexxio-ehemals-hs-steiner.svg'];
const BRAND = resolve(ROOT, '../frontend/public/brand');


const a = site.address;
const v = formVocab();
const mail = inquiry.mail;

const data = {
  _comment:
    'Generiert aus website/src/config (site.mjs, inquiry.mjs) mit «npm run export:contact» – nicht von Hand ändern.',
  brand: { name: site.brand.name, full: plain(site.brand.full) },
  phone: { display: site.phone.display, e164: site.phone.e164 },
  email: contactEmail(),
  address: [a.street, `${a.zip} ${a.city} (${a.municipality} ${a.canton})`],
  pages: { thanks: '/kontakt/danke', contact: '/kontakt' },
  photos: inquiry.photos,
  minSeconds: inquiry.minSeconds,
  limits: inquiry.limits,
  labels: v.labels,
  messages: v.messages,
  mail: {
    confirmSubject: plain(mail.confirmSubject),
    confirmIntro: plain(mail.confirmIntro),
    confirmNext: plain(mail.confirmNext),
    urgent: plain(mail.urgent),
    closing: mail.closing,
  },
};

/**
 * Name und Satz für die Metadaten des Konto-/ERP-Bereichs (Titel, Beschreibung). Kopf und
 * Fuss selbst kommen NICHT von hier – sie sind die der Website (scripts/export-shell.mjs).
 */
const shell = {
  _comment:
    'Generiert aus website/src/config/site.mjs mit «npm run export:contact» – nicht von Hand ändern. Nur Name und Satz für die Metadaten; Kopf und Fuss liefert scripts/export-shell.mjs.',
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
      console.error(`export-contact: ${rel(file)} ist veraltet – «npm run export:contact» ausführen und committen.`);
    }
    process.exit(1);
  }
  console.log('export-contact: aktuell');
} else {
  for (const [file, json] of outputs) {
    writeFileSync(file, json);
    console.log(`export-contact: ${rel(file)} geschrieben`);
  }
}
