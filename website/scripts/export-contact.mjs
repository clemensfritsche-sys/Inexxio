// ►►► Überträgt, was ausserhalb der Website dieselben Wörter braucht. ◄◄◄
//
//   node scripts/export-contact.mjs           schreibt alle Abdrucke
//   node scripts/export-contact.mjs --check   bricht ab (Exit 1), wenn eine veraltet ist (CI)
//
// 1. backend/app/assets/website_contact.json – das Vokabular der Anfrage: der Endpunkt
//    backend/app/routers/contact.py prüft gegen DIESELBEN Listen und schreibt die E-Mails mit
//    DENSELBEN Wörtern wie das Formular im Browser.
// 2. frontend/src/lib/site-shell.json – Inhalt von Kopf und Fuss im Konto- und ERP-Bereich
//    (Bereiche, Telefon, Notfallnummer, Adresse, Pfade): dort wird derselbe Kopf in React
//    nachgebaut (WEBSITE_PLAN Entscheid 39), die Inhalte kommen von hier.
//
// 3. frontend/public/brand/inexxio-ehemals-hs-steiner(-weiss).svg – das Logo für Kopf, Fuss
//    und Anmeldedialog des ERP. Ein Abdruck von public/logo/, damit Konto und ERP dasselbe
//    Zeichen tragen und es auch ohne die Website (npm run dev im Frontend) da ist.
//
// Die Quelle bleibt src/config (site.mjs, inquiry.mjs) und public/logo – die Dateien
// drüben sind ihr Abdruck.
//
// Eine E-Mail enthält nie eine Markierung: ist ein Wert noch offen ([[…]]), gilt die
// hinterlegte Ausweichformulierung bzw. die Angabe fällt weg.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { site, contactEmail, isMissing } from '../src/config/site.mjs';
import { inquiry } from '../src/config/inquiry.mjs';
import { formVocab } from '../src/lib/inquiry-vocab.mjs';
import { hasMarker, plain } from '../src/lib/text.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const TARGET = resolve(ROOT, '../backend/app/assets/website_contact.json');
const SHELL = resolve(ROOT, '../frontend/src/lib/site-shell.json');
const LOGOS = ['inexxio-ehemals-hs-steiner.svg', 'inexxio-ehemals-hs-steiner-weiss.svg'];
const BRAND = resolve(ROOT, '../frontend/public/brand');

/** Text mit Werten; enthält er eine offene Markierung, gilt `fallback` (oder nichts). */
const textOr = (/** @type {string} */ text, /** @type {string | null} */ fallback = null) =>
  hasMarker(text) ? fallback : plain(text);

const a = site.address;
const v = formVocab();
const mail = inquiry.mail;

const data = {
  _comment:
    'Generiert aus website/src/config (site.mjs, inquiry.mjs) mit «npm run export:contact» – nicht von Hand ändern.',
  brand: { name: site.brand.name, full: plain(site.brand.full) },
  phone: { display: site.phone.display, e164: site.phone.e164 },
  notfall: site.features.notfall ? { display: site.notfall.display, e164: site.notfall.e164 } : null,
  email: contactEmail(),
  address: [a.street, `${a.zip} ${a.city} (${a.municipality} ${a.canton})`],
  pages: { thanks: '/kontakt/danke', contact: '/kontakt' },
  kinds: inquiry.kinds.map((k) => ({ value: k.value, label: k.label, subject: k.subject })),
  needs: inquiry.needs,
  urgencies: inquiry.urgencies.map((u) => ({ value: u.value, label: u.label, subject: u.subject })),
  contactPrefs: inquiry.contactPrefs,
  photos: inquiry.photos,
  minSeconds: inquiry.minSeconds,
  limits: inquiry.limits,
  labels: v.labels,
  messages: v.messages,
  mail: {
    confirmSubject: textOr(mail.confirmSubject, `Ihre Anfrage bei ${site.brand.name}`),
    confirmIntro: textOr(mail.confirmIntro),
    confirmNext: textOr(mail.confirmNext.text, mail.confirmNext.fallback),
    urgent: textOr(mail.urgent),
    // Die Notfallnummer steht in einer E-Mail erst, wenn sie bestätigt ist: auf der Website
    // trägt sie ihre Prüf-Markierung sichtbar, eine E-Mail kann keine tragen – sie verspräche
    // sonst einen Dienst, dessen Weiterführung noch offen ist.
    urgentNotfall:
      site.features.notfall && !isMissing(site.notfall.display) && !hasMarker(site.notfall.review)
        ? textOr(mail.urgentNotfall)
        : null,
    closing: mail.closing,
  },
};

/** Kopf und Fuss des Konto-/ERP-Bereichs – nur Anzeige, ohne Markierungen. */
const link = (/** @type {{ label: string, href: string, text?: string }} */ l) => ({
  label: plain(l.label), href: l.href, ...(l.text ? { text: plain(l.text) } : {}),
});
const shell = {
  _comment:
    'Generiert aus website/src/config/site.mjs mit «npm run export:contact» – nicht von Hand ändern. Kopf und Fuss des Konto-/ERP-Bereichs spiegeln die Website (WEBSITE_PLAN Entscheid 39).',
  brand: { name: site.brand.name, full: plain(site.brand.full), legalName: plain(site.brand.legalName) },
  logo: { dark: `/brand/${LOGOS[0]}`, light: `/brand/${LOGOS[1]}` },
  claim: plain(site.footer.claim),
  announcement: site.features.announcement
    ? { text: plain(site.announcement.text), link: link(site.announcement.link) }
    : null,
  phone: { display: site.phone.display, e164: site.phone.e164 },
  notfall: site.features.notfall ? { display: site.notfall.display, e164: site.notfall.e164 } : null,
  email: contactEmail(),
  hours: plain(site.hours.text),
  address: [plain(site.brand.legalName), a.street, `${a.zip} ${a.city} (${a.municipality} ${a.canton})`],
  uid: isMissing(site.brand.uid) ? null : site.brand.uid,
  areas: site.areas.map((ar) => ({ ...link(ar), overview: ar.overview, children: ar.children.map(link) })),
  service: { ...link(site.service), overview: site.service.overview, children: site.service.children.map(link) },
  menu: site.menu.map(link),
  company: site.company.map(link),
  cta: link(site.cta),
  account: site.account,
  legal: [{ label: 'Impressum', href: '/impressum' }, { label: 'Datenschutz', href: '/datenschutz' }],
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
