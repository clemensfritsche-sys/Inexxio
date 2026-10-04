/**
 * Übergabe: Aus HS Steiner wird INEXXIO (Auftrag Kap. 7.4 und 7.5).
 * «Was bleibt / was neu ist» und die Botschaft von Clemens stehen NUR hier – die
 * Startseite und «Über uns» lesen sie von dieser Stelle.
 */
import { site } from '../config/site.mjs';
import type { Faq } from './types';

/**
 * Zitat von Heiri Steiner – Entwurf in seinen Worten (Rückmeldung 04.10.2026: «versetze dich
 * in die Lage von Heiri»), freigegeben mit Testnotiz #1097.
 */
export const heiriQuote =
  'Über 40 Jahre war diese Werkstatt mein Leben. Ich gebe sie mit gutem Gefühl weiter: Clemens bringt neues Wissen mit und hat Respekt vor dem, was hier gewachsen ist. Meine Kunden sind bei ihm in guten Händen.';

/** Der eine Satz zur Übergabe – Startseite und Übergabe-Seite sagen ihn gleich. */
export const handoverLead =
  'Nach {{history.experienceDative}} übergibt Heiri Steiner sein Unternehmen an Clemens Fritsche. Werkstatt, Telefonnummer und der Service für alle bestehenden HS-Krananlagen bleiben – ergänzt um Ingenieurwissen, wo es Ihnen nützt.';

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
  /** Ersatzteile für HS-Anlagen (#1128) – Übergabe- und Heukran-Seite sagen es gleich. */
  parts: {
    q: 'Bekomme ich weiterhin Ersatzteile für ältere Anlagen?',
    a: 'Ja. Die Ersatzteile für die bestehenden HS-Anlagen liegen entweder an Lager, oder wir fertigen sie für Sie neu an.',
  },
} satisfies Record<string, Faq>;

/** Persönliche Botschaft von Clemens Fritsche (Auftrag Kap. 7.8). */
export const message = {
  paragraphs: [
    'Ich bin Maschinenbauingenieur und habe bei Liebherr Baumaschinen entwickelt. Krane und schwere Maschinen begleiten mich mein ganzes Berufsleben. Als ich Heiri Steiner kennengelernt habe, war schnell klar: Hier stimmt die Basis – treue Kunden, solide Anlagen, ehrliches Handwerk.',
    'Danach habe ich im IoT-Umfeld Produkte und Plattformen verantwortet – also Maschinen, die vernetzt sind und ihren Zustand melden. Dieses Wissen bringe ich mit: bei der Modernisierung von Steuerung und Funk ebenso wie dort, wo eine Anlage künftig mehr über sich verraten soll als heute.',
    'Was Heiri in {{history.experienceDative}} aufgebaut hat, führe ich mit derselben Sorgfalt weiter. Und ich ergänze es dort, wo es Ihnen nützt: mit Ingenieurwissen, sauberer Dokumentation und Lösungen, die es nicht von der Stange gibt.',
  ],
  signature: '{{people.owner.name}}',
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
    '{{brand.full}} ist das Unternehmen, das Heiri Steiner {{history.founded}} in Tuttwil-Wängi TG gegründet hat – bisher als {{brand.formerLegalName}}, früher auch bekannt für die HS-Krananlagen. Mit der Übergabe an Clemens Fritsche tritt es als {{brand.legalName}} auf: dieselbe Werkstatt, dieselbe Telefonnummer, derselbe Service für alle bestehenden Anlagen.',
  timeline: [
    { year: String(site.history.founded), text: site.history.foundedText },
    { year: String(site.history.cranesSince), text: site.history.cranesText },
    { year: `${site.history.gmbhYear}`, text: 'Das Unternehmen wird zur {{brand.formerLegalName}}.' },
    { year: 'Heute', text: 'Heiri Steiner übergibt an Clemens Fritsche – aus HS Steiner wird die {{brand.legalName}}.' },
  ],
  faq: [
    sharedFaq.phone,
    sharedFaq.contracts,
    sharedFaq.whoCares,
    ...(site.features.heiriAdvisory
      ? [{ q: 'Bleibt Heiri Steiner dabei?', a: '{{people.founder.advisory}}' }]
      : []),
    sharedFaq.parts,
    { q: sharedFaq.newCranes.q, a: `${sharedFaq.newCranes.a} Mehr dazu unter [Heukrananlagen](/krantechnik/heukrananlagen).` },
  ] satisfies Faq[],
};
