// ►►► Überträgt das Vokabular der Anfrage an den Server. ◄◄◄
//
//   node scripts/export-contact.mjs           schreibt backend/app/assets/website_contact.json
//   node scripts/export-contact.mjs --check   bricht ab (Exit 1), wenn die Datei veraltet ist (CI)
//
// Der Endpunkt backend/app/routers/contact.py prüft gegen DIESELBEN Listen und schreibt die
// E-Mails mit DENSELBEN Wörtern wie das Formular im Browser. Die Quelle bleibt
// src/config (site.mjs, inquiry.mjs) – diese JSON-Datei ist nur ihr Abdruck.
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
  pikett: site.features.pikett ? { display: site.pikett.display, e164: site.pikett.e164 } : null,
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
    // Der Pikett steht in einer E-Mail erst, wenn er bestätigt ist: auf der Website trägt er
    // seine Prüf-Markierung sichtbar, eine E-Mail kann keine tragen – sie versprächen sonst
    // einen Dienst, dessen Weiterführung noch offen ist.
    urgentPikett:
      site.features.pikett && !isMissing(site.pikett.display) && !hasMarker(site.pikett.review)
        ? textOr(mail.urgentPikett)
        : null,
    closing: mail.closing,
  },
};

const json = `${JSON.stringify(data, null, 2)}\n`;

if (process.argv.includes('--check')) {
  const current = existsSync(TARGET) ? readFileSync(TARGET, 'utf8') : '';
  if (current !== json) {
    console.error(
      'export-contact: backend/app/assets/website_contact.json ist veraltet – «npm run export:contact» ausführen und committen.',
    );
    process.exit(1);
  }
  console.log('export-contact: aktuell');
} else {
  writeFileSync(TARGET, json);
  console.log(`export-contact: ${TARGET.replace(resolve(ROOT, '..') + '/', '')} geschrieben`);
}
