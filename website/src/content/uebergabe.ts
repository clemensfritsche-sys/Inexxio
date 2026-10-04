/**
 * Übergabe: Aus HS Steiner wird INEXXIO (Auftrag Kap. 7.4 und 7.5).
 * «Was bleibt / was neu ist» und die Botschaft von Clemens stehen NUR hier – die
 * Startseite und «Über uns» lesen sie von dieser Stelle.
 */
import { site } from '../config/site.mjs';
import type { Faq } from './types';

/** Zitat von Heiri Steiner – erst mit seiner Freigabe ein Text, bis dahin nur der Platzhalter. */
export const heiriQuote =
  '[[PLATZHALTER: Zitat mit Heiri Steiner formulieren und von ihm freigeben lassen. Kein erfundenes Zitat veröffentlichen.]]';

/** Was bleibt – dieselbe Liste auf Startseite und Übergabe-Seite (Auftrag 7.3). */
export const stays = [
  'Standort Tuttwil-Wängi',
  'Telefonnummer {{phone.display}}',
  'Bekannte Ansprechpartner [[PLATZHALTER: Namen nur mit Einverständnis]]',
  'Service und Ersatzteile für alle bestehenden HS-Krananlagen',
  'Laufende Verträge [[PRÜFEN: rechtlich]]',
];

/** Was neu ist. */
export const news = [
  'Der Name {{brand.name}}',
  'Ingenieurwissen für Konstruktion und Modernisierung',
  'Sonderlösungen: Konstruktion, Stahlbau, Baumaschinen',
  'Ein Konto für Kunden – später mit Aufträgen und Bestellungen',
];

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
    lead:
      'Nach {{history.experienceDative}} übergibt Heiri Steiner sein Unternehmen an Clemens Fritsche. Werkstatt, Telefonnummer und der Service für alle bestehenden HS-Krananlagen bleiben – dazu kommen Ingenieurwissen und Sonderlösungen. [[PRÜFEN: Wortlaut freigeben]]',
  },
  summary:
    '{{brand.full}} ist das Unternehmen, das Heiri Steiner {{history.founded}} in Tuttwil-Wängi TG gegründet hat – bisher als {{brand.formerLegalName}}, früher auch bekannt für die HS-Krananlagen. Mit der Übergabe an Clemens Fritsche tritt es als {{brand.legalName}} auf: dieselbe Werkstatt, dieselbe Telefonnummer, derselbe Service für alle bestehenden Anlagen. {{brand.legalNameReview}}',
  timeline: [
    { year: String(site.history.founded), text: site.history.foundedText },
    { year: String(site.history.cranesSince), text: site.history.cranesText },
    { year: `${site.history.gmbhYear} ${site.history.gmbhReview}`, text: 'Das Unternehmen wird zur {{brand.formerLegalName}}.' },
    { year: site.history.handoverDate, text: 'Heiri Steiner übergibt an Clemens Fritsche – aus HS Steiner wird die {{brand.legalName}}.' },
  ],
  discontinued: {
    title: 'Nicht mehr in unserem Angebot',
    lead: 'Wir konzentrieren uns auf Krantechnik, Fahrzeugtechnik und Sonderlösungen. Einige Leistungen von HS Steiner bieten wir darum nicht mehr an:',
    items: [
      'Haus und Garten, Motorgeräte, Pflanzenschutz, Pflanzenbehälter, Transportwagen',
      'Reifenservice, Reparaturen von Personenwagen und Transportern',
      'Vermietung von Hebebühnen',
      'Trailer, Neuaufbauten und Fahrzeughandel',
      'Events und Oldtimer',
      'Geländer und Verglasungen',
    ],
    review: '[[PRÜFEN: Liste von Clemens bestätigen lassen]]',
    after: 'Unsicher, ob wir Ihnen helfen können? Rufen Sie an: {{phone.link}}. Wir sagen es Ihnen offen.',
  },
  faq: [
    {
      q: 'Bleibt die Telefonnummer gleich?',
      a: 'Ja, {{phone.display}}. Auch die bisherigen E-Mail-Adressen erreichen uns weiterhin. [[PRÜFEN: Weiterleitung der E-Mail-Adressen bestätigen]]',
    },
    {
      q: 'Gelten bestehende Verträge weiter?',
      a: 'Ja. Das Unternehmen bleibt dasselbe, nur der Name ändert sich. [[PRÜFEN: rechtlich – Aussage zu laufenden Verträgen]]',
    },
    {
      q: 'Wer betreut meine HS-Krananlage in Zukunft?',
      a: 'Wir. Service und Ersatzteile für HS-Krananlagen führen wir weiter, mit demselben Wissen und denselben Teilen ab Lager.',
    },
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
    {
      q: 'Bauen Sie weiterhin neue Krananlagen?',
      a: 'Ja. Heukrananlagen und Industriekrane planen und bauen wir nach Mass – mehr dazu unter [Heukrananlagen](/krantechnik/heukrananlagen).',
    },
  ] satisfies Faq[],
  cta: {
    title: 'Fragen zur Übergabe?',
    lead: 'Rufen Sie an oder schreiben Sie uns – wir melden uns innert {{promises.responseTime}}.',
  },
};
