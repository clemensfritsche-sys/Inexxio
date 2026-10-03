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

/** Was bleibt – dieselbe Liste auf Startseite und Übergabe-Seite. */
export const stays = [
  'Standort Tuttwil-Wängi',
  'Telefonnummer {{phone.display}}',
  'Bekannte Ansprechpartner [[PLATZHALTER: Namen nur mit Einverständnis]]',
  'Service und Ersatzteile für alle HS-Krananlagen',
  'Laufende Verträge [[PRÜFEN: rechtlich]]',
];

/** Was neu ist. */
export const news = [
  'Service-Abos zum Fixpreis',
  'Digitales Kranbuch',
  'Modernisierung älterer Krane',
  'Verschleissteile für Fahrmischer',
  'Der Name {{brand.name}}',
];

/** Persönliche Botschaft von Clemens Fritsche (Entwurf, Auftrag Kap. 7.5). */
export const message = {
  review: '[[PRÜFEN: von Clemens anpassen und freigeben]]',
  paragraphs: [
    'Ich bin Maschinenbauingenieur und habe bei Liebherr Baumaschinen entwickelt. Krane und schwere Maschinen begleiten mich mein ganzes Berufsleben. Als ich Heiri Steiner kennengelernt habe, war schnell klar: Hier stimmt die Basis – treue Kunden, solide Anlagen, ehrliches Handwerk.',
    'Was Heiri in {{history.experienceDative}} aufgebaut hat, führe ich mit derselben Sorgfalt weiter. Und ich ergänze es dort, wo es Ihnen nützt.',
  ],
  signature: '{{people.owner.name}}, {{people.owner.role}}',
};

export const uebergabe = {
  title: 'Aus HS Steiner wird INEXXIO',
  description:
    'HS Steiner Fahrzeug- und Kranbau GmbH in Tuttwil heisst jetzt INEXXIO: gleiche Nummer, gleicher Standort, Service für alle HS-Krananlagen. Antworten zur Nachfolge.',
  hero: {
    eyebrow: 'Nachfolge geregelt',
    h1: 'Aus HS Steiner wird {{brand.name}}',
    lead:
      'Nach {{history.experienceDative}} übergibt Heiri Steiner sein Unternehmen an Clemens Fritsche. Werkstatt, Telefonnummer und der Service für alle HS-Krananlagen bleiben – dazu kommt mehr Service. [[PRÜFEN: Wortlaut freigeben]]',
  },
  summary:
    '{{brand.full}} ist das Unternehmen, das Heiri Steiner {{history.founded}} in Tuttwil-Wängi TG gegründet hat – bisher als {{brand.formerLegalName}}. Mit der Übergabe an Clemens Fritsche tritt es als {{brand.name}} auf: dieselbe Werkstatt, dieselbe Telefonnummer, derselbe Service für alle HS-Krananlagen.',
  timeline: [
    { year: String(site.history.founded), text: site.history.foundedText },
    { year: String(site.history.cranesSince), text: site.history.cranesText },
    { year: `${site.history.gmbhYear} ${site.history.gmbhReview}`, text: 'Das Unternehmen wird zur {{brand.formerLegalName}}.' },
    { year: site.history.handoverDate, text: 'Heiri Steiner übergibt an Clemens Fritsche – aus HS Steiner wird {{brand.name}}.' },
  ],
  discontinued: {
    title: 'Nicht mehr in unserem Angebot',
    lead: 'Wir konzentrieren uns auf Krane und Fahrmischer. Einige Leistungen von HS Steiner bieten wir darum nicht mehr an:',
    items: [
      'Haus und Garten, Motorgeräte, Pflanzenschutz, Pflanzenbehälter, Transportwagen',
      'Reifenservice, Reparaturen von Personenwagen und Transportern',
      'Vermietung von Hebebühnen',
      'Fahrzeughandel',
      'Events und Oldtimer',
      'Geländer und Verglasungen',
    ],
    review:
      '[[PRÜFEN: Liste von Clemens bestätigen lassen. Offen sind Hydraulikschlauch-Service, Reparaturen an Baumaschinen und LKW-Aufbauten sowie allgemeine Schlosserarbeiten.]]',
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
      q: 'Wer betreut meinen HS-Kran in Zukunft?',
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
      a: 'Ja. Das Lager in Tuttwil bleibt – mit Greifern, Auslegern, Fahrwerken und Drehtürmen für HS-Krananlagen. [[PRÜFEN: Lagerbestand für ältere Typen]]',
    },
  ] satisfies Faq[],
  cta: {
    title: 'Fragen zur Übergabe?',
    lead: 'Rufen Sie an oder schreiben Sie uns – wir melden uns innert {{promises.responseTime}}.',
  },
};
