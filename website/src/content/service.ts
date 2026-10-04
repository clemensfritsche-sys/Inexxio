/**
 * Service – Einstieg nach Anliegen und Notfall-Service (Auftrag Kap. 7.6).
 * Der Service ist inhaltlich in jedem Bereich beschrieben; /service ist nur der schnelle
 * Einstieg für Kunden mit einem akuten Anliegen.
 */
import type { Entry, Faq } from './types';

export const service = {
  path: '/service',
  title: 'Service und Reparatur',
  description:
    'Kran steht still, Prüfung fällig, Fahrmischer defekt oder Teil gesucht? Der schnelle Einstieg zum Service von INEXXIO (ehemals HS Steiner) in Tuttwil.',
  hero: {
    eyebrow: 'Service',
    h1: 'Service: Was steht bei Ihnen ==an==?',
    lead:
      'Wählen Sie Ihr Anliegen – wir führen Sie direkt zur richtigen Stelle. Steht etwas still, rufen Sie am besten gleich an.',
    photo: 'servicefahrzeug',
  },
  summary:
    '{{brand.full}} betreut Krananlagen – vor allem die HS- und die eigenen Anlagen –, wartet und repariert Fahrmischer, Aufbauten und Baumaschinen und liefert Verschleissteile für Fahrmischer ab Lager in Tuttwil-Wängi TG. Steht etwas still, rufen Sie direkt an.',
  entries: [
    { title: 'Etwas steht still', text: 'Notfall-Service – rufen Sie direkt an', href: '/service/notfall', icon: 'siren' },
    { title: 'Kran prüfen oder warten lassen', text: 'Jährliche Überprüfung mit Bericht', href: '/krantechnik/pruefung-wartung', icon: 'shield-check' },
    { title: 'Fahrmischer oder Aufbau reparieren', text: 'Alle gängigen Marken, Teile ab Lager', href: '/fahrzeugtechnik/fahrmischer', icon: 'truck' },
    { title: 'Ersatz- oder Verschleissteil gesucht', text: 'Katalog oder Teil direkt anfragen', href: '/fahrzeugtechnik/verschleiss-ersatzteile', icon: 'package' },
  ] satisfies Entry[],
  /** Zweite Ziele zu den Kacheln, die zwei Wege haben (Auftrag 7.6). */
  alsoLinks: [
    { href: '/fahrzeugtechnik/aufbauten-reparatur', label: 'Aufbau reparieren lassen' },
    { href: '/kontakt', label: 'Teil direkt anfragen' },
  ],
  how: {
    title: 'So arbeiten wir',
    items: [
      { title: 'Offerte vor Arbeitsbeginn', text: 'Vor grösseren Arbeiten erhalten Sie eine Offerte – Sie entscheiden, bevor wir anfangen. [[PRÜFEN: Zusage freigeben]]' },
      { title: 'Bericht nach jeder Arbeit', text: 'Sie erhalten einen Bericht mit Arbeiten und Teilen; bei Kranen gehört er ins Kranbuch. [[PRÜFEN: Zusage freigeben]]' },
      { title: 'Teile ab Lager', text: 'Verschleissteile für Fahrmischer und Teile für HS-Krananlagen liegen in Tuttwil – das verkürzt Stillstände.' },
      { title: 'Ein Ansprechpartner', text: 'Fahrmischer der gängigen Marken, HS- und eigene Krananlagen – auf Anfrage auch Krane anderer Hersteller.' },
    ],
  },
  area: {
    title: 'Wo wir arbeiten',
    text: 'Zuhause sind wir in {{erp.city}}, im Einsatz {{area.summary}}. Krane prüfen und reparieren wir dort, wo sie stehen; Fahrmischer, Aufbauten und Baumaschinen kommen meist in unsere Werkstatt.',
    link: 'Mehr über uns',
  },
};

export const notfall = {
  path: '/service/notfall',
  title: 'Notfall-Service',
  description:
    'Kran, Fahrmischer oder Maschine steht still? Die Telefonnummer, was Sie bereithalten sollten, und das Formular für dringende Fälle. INEXXIO, Tuttwil TG.',
  hero: {
    eyebrow: 'Service · Notfall',
    h1: 'Notfall-Service: wenn etwas stillsteht',
    lead:
      'Rufen Sie uns an: {{phone.link}}. Je genauer Sie beschreiben, was passiert ist, desto schneller können wir helfen.',
  },
  summary:
    '{{brand.full}} hilft bei Stillständen von Kranen, Fahrmischern, Aufbauten und Baumaschinen. Telefon: {{phone.display}}.',
  prepare: {
    title: 'Was Sie bereithalten sollten',
    items: [
      { title: 'Standort', text: 'Wo steht die Anlage oder Maschine? PLZ, Ort, Zufahrt.' },
      { title: 'Maschine', text: 'Was ist es – Kran, Fahrmischer, Aufbau, Baumaschine? Hersteller und Typ.' },
      { title: 'Typenschild', text: 'Typ, Baujahr und Nummer – am einfachsten als Foto.' },
      { title: 'Foto vom Schaden', text: 'Was ist passiert, was ist zu sehen? Ein Foto sagt oft mehr als die Beschreibung.' },
    ],
  },
  safety: {
    title: 'Bis wir da sind',
    text: 'Anlage ausser Betrieb nehmen und sichern, Last – wenn möglich – sicher absetzen, Bereich absperren. Nicht unter Last weiterarbeiten. [[PRÜFEN: fachlich – Verhalten bei einer Störung]]',
  },
  faq: [
    {
      q: 'Wie schnell sind Sie bei einem Stillstand vor Ort?',
      a: 'Steht eine Anlage still, rufen Sie am besten direkt an: {{phone.link}}.',
    },
    {
      q: 'Helfen Sie auch bei Kranen anderer Hersteller?',
      a: 'Auf Anfrage. Unser Schwerpunkt sind die HS- und unsere eigenen Krananlagen; bei Kranen anderer Hersteller klären wir im Einzelfall, ob und wie wir helfen können. Bei Fahrmischern arbeiten wir an allen gängigen Marken.',
    },
    {
      q: 'Was kostet ein Notfalleinsatz?',
      a: '[[PLATZHALTER: Berechnung von Notfalleinsätzen ausserhalb der Bürozeiten]]',
    },
  ] satisfies Faq[],
};
