/**
 * Übergabe: Aus HS Steiner wird INEXXIO (Auftrag Kap. 7.4 und 7.5).
 * «Was bleibt / was neu ist» und die Botschaft von Clemens stehen NUR hier – die
 * Startseite und «Über uns» lesen sie von dieser Stelle.
 */
import { site } from '../config/site.mjs';
import type { Faq } from './types';

/**
 * Zitat von Heiri Steiner – Entwurf in seinen Worten (Rückmeldung 04.10.2026: «versetze dich
 * in die Lage von Heiri»). Ein Zitat legt einer echten Person Worte in den Mund: es bleibt
 * markiert, bis Heiri es freigegeben hat.
 */
export const heiriQuote =
  'Über 40 Jahre war diese Werkstatt mein Leben. Ich gebe sie mit gutem Gefühl weiter: Clemens bringt neues Wissen mit und hat Respekt vor dem, was hier gewachsen ist. Meine Kunden sind bei ihm in guten Händen. [[PRÜFEN: Zitat von Heiri Steiner freigeben lassen]]';

/** Der eine Satz zur Übergabe – Startseite und Übergabe-Seite sagen ihn gleich. */
export const handoverLead =
  'Nach {{history.experienceDative}} übergibt Heiri Steiner sein Unternehmen an Clemens Fritsche. Werkstatt, Telefonnummer und der Service für alle bestehenden HS-Krananlagen bleiben – dazu kommen Ingenieurwissen und Sonderlösungen.';

/** Was bleibt – dieselbe Liste auf Startseite und Übergabe-Seite (Auftrag 7.3). */
export const stays = [
  'Standort Tuttwil-Wängi',
  'Telefonnummer {{phone.display}}',
  'Service und Ersatzteile für alle bestehenden HS-Krananlagen',
  'Ihre Kundenbeziehung – wir kennen Ihre Anlagen und ihre Geschichte',
];

/** Was neu ist. */
export const news = [
  'Der Name {{brand.name}}',
  'Ihr Ansprechpartner: {{people.owner.name}}',
  'Ingenieurwissen für Konstruktion und Modernisierung',
  'Sonderlösungen: Konstruktion, Stahlbau, Baumaschinen',
];

/**
 * Fragen, die Startseite und Übergabe-Seite beide stellen – EINE Antwort, an einer Stelle.
 * (Rückmeldung 04.10.2026: «die Startseite spiegelt die Unterseiten – das muss matchen».)
 */
export const sharedFaq = {
  whoCares: {
    q: 'Wer betreut meine HS-Krananlage in Zukunft?',
    a: 'Wir – ohne Unterbruch. Wir kennen die HS-Krananlagen von der Konstruktion bis zum Ersatzteil und betreuen sie weiter.',
  },
  newCranes: {
    q: 'Bauen Sie weiterhin neue Krananlagen?',
    a: 'Ja. Heukrananlagen und Industriekrane planen, bauen und montieren wir weiterhin selbst.',
  },
  phone: {
    q: 'Bleibt die Telefonnummer gleich?',
    a: 'Ja, {{phone.display}}. Die aktuellen Kontaktangaben finden Sie jederzeit hier auf unserer Website.',
  },
  contracts: {
    q: 'Gelten bestehende Verträge weiter?',
    a: 'Ja. Das Unternehmen bleibt dasselbe, nur der Name ändert sich.',
  },
} satisfies Record<string, Faq>;

/** Persönliche Botschaft von Clemens Fritsche (Entwurf, Auftrag Kap. 7.8). */
export const message = {
  review: '[[PRÜFEN: von Clemens anpassen und freigeben]]',
  paragraphs: [
    'Ich bin Maschinenbauingenieur und habe bei Liebherr Baumaschinen entwickelt. Krane und schwere Maschinen begleiten mich mein ganzes Berufsleben. Als ich Heiri Steiner kennengelernt habe, war schnell klar: Hier stimmt die Basis – treue Kunden, solide Anlagen, ehrliches Handwerk.',
    'Was Heiri in {{history.experienceDative}} aufgebaut hat, führe ich mit derselben Sorgfalt weiter. Und ich ergänze es dort, wo es Ihnen nützt: mit Ingenieurwissen, sauberer Dokumentation und Lösungen, die es nicht von der Stange gibt.',
  ],
  signature: '{{people.owner.name}}, {{people.owner.role}}',
};

export const uebergabe = {
  title: 'Aus HS Steiner wird INEXXIO',
  description:
    'HS Steiner Fahrzeug- und Kranbau GmbH heisst jetzt INEXXIO AG: gleiche Nummer, gleicher Standort, Service für alle HS-Krananlagen. Fragen zur Nachfolge.',
  hero: {
    eyebrow: 'Nachfolge geregelt',
    h1: 'Aus HS Steiner wird {{brand.name}}',
    lead: handoverLead,
  },
  summary:
    '{{brand.full}} ist das Unternehmen, das Heiri Steiner {{history.founded}} in Tuttwil-Wängi TG gegründet hat – bisher als {{brand.formerLegalName}}, früher auch bekannt für die HS-Krananlagen. Mit der Übergabe an Clemens Fritsche tritt es als {{brand.legalName}} auf: dieselbe Werkstatt, dieselbe Telefonnummer, derselbe Service für alle bestehenden Anlagen. {{brand.legalNameReview}}',
  timeline: [
    { year: String(site.history.founded), text: site.history.foundedText },
    { year: String(site.history.cranesSince), text: site.history.cranesText },
    { year: `${site.history.gmbhYear} ${site.history.gmbhReview}`, text: 'Das Unternehmen wird zur {{brand.formerLegalName}}.' },
    { year: site.history.handoverDate, text: 'Heiri Steiner übergibt an Clemens Fritsche – aus HS Steiner wird die {{brand.legalName}}.' },
  ],
  faq: [
    sharedFaq.phone,
    sharedFaq.contracts,
    sharedFaq.whoCares,
    ...(site.features.heiriAdvisory
      ? [{ q: 'Bleibt Heiri Steiner dabei?', a: '{{people.founder.advisory}}' }]
      : []),
    {
      q: 'Ändern sich Rechnungsadresse oder Bankverbindung?',
      a: '[[PLATZHALTER: Rechnungsstellung und Bankverbindung nach der Übergabe]]',
    },
    {
      q: 'Bekomme ich weiterhin Ersatzteile für ältere Anlagen?',
      a: 'Ja. Das Lager in Tuttwil bleibt – mit Greifern, Auslegern, Fahrwerken und Drehtürmen für die bestehenden Anlagen. [[PRÜFEN: Lagerbestand für ältere Typen]]',
    },
    { q: sharedFaq.newCranes.q, a: `${sharedFaq.newCranes.a} Mehr dazu unter [Heukrananlagen](/krantechnik/heukrananlagen).` },
  ] satisfies Faq[],
  cta: {
    title: 'Fragen zur Übergabe?',
    lead: 'Rufen Sie an oder schreiben Sie uns – wir melden uns innert {{promises.responseTime}}.',
  },
};
