/**
 * Service-Abo und digitales Kranbuch (Auftrag Kap. 7.3). Stufen, Inhalte und Preis stehen
 * in config/abo.mjs – hier nur die Texte der Seite.
 */
import type { ServicePage } from './types';

export const serviceAbo: ServicePage = {
  path: '/service-abo',
  crumb: 'Service-Abo',
  title: 'Service-Abo und Kranbuch',
  description:
    'Service-Abo für Krane: Prüfung und Wartung zum Fixpreis pro Kran und Jahr, mit digitalem Kranbuch per QR-Code und Terminerinnerung. Jetzt Offerte anfragen.',
  og: 'krane',
  hero: {
    eyebrow: 'Service-Abo und digitales Kranbuch',
    h1: 'Service-Abo für Krane: Prüfung und Wartung zum Fixpreis',
    lead:
      'Ein Abo, ein Preis pro Kran und Jahr. Wir denken an den Termin, prüfen, warten und tragen alles ins digitale Kranbuch ein. [[PRÜFEN: Abo und Kranbuch ab Start verfügbar oder «in Vorbereitung»?]]',
    photo: 'servicefahrzeug',
    primary: { label: 'Abo-Offerte anfragen', href: '#anfrage', track: 'abo_interest' },
  },
  summary:
    '{{brand.full}} bietet Service-Abos für Krane in drei Stufen: Prüfung, Service und Komplett. Der Preis gilt pro Kran und Jahr; jede Kontrolle landet im digitalen Kranbuch, abrufbar per QR-Code direkt am Kran.',
  glance: {
    forWhom: 'Betriebe mit einem oder mehreren Kranen – Hallenkrane, Heukrane, HS-Krananlagen, alle Marken.',
    what: 'Jährliche Prüfung, je nach Stufe Wartung und bevorzugte Reaktion bei Störungen.',
    speed: 'Wir planen die Termine und melden uns rechtzeitig vor jeder Prüfung.',
    deliverables: 'Prüfbericht, Einträge im digitalen Kranbuch, Terminerinnerung.',
  },
  scope: {
    title: 'Was im Abo steckt',
    lead: 'Der Umfang hängt von der Stufe ab.',
    items: [
      { title: 'Termine', text: 'Wir planen die jährliche Prüfung und erinnern Sie rechtzeitig daran.' },
      { title: 'Prüfung', text: 'Überprüfung durch Kranfachleute nach den Angaben des Herstellers – mit Prüfbericht.' },
      { title: 'Wartung', text: 'Ab der Stufe «Service»: Wartung, Verschleiss-Check und Schmierung im selben Termin.' },
      { title: 'Digitales Kranbuch', text: 'Jeder Eintrag abrufbar per QR-Code am Kran – Prüfberichte, Wartungen, Reparaturen.' },
      { title: 'Fixpreis', text: 'Ein Preis pro Kran und Jahr; die Stufe bestimmt, was enthalten ist.' },
    ],
  },
  steps: [
    { title: 'Offerte', text: 'Sie nennen Anzahl, Art und Standort Ihrer Krane; wir offerieren pro Kran und Jahr.' },
    { title: 'Erster Termin', text: 'Wir prüfen die Krane und legen das Kranbuch an – mit QR-Code am Kran.' },
    { title: 'Jedes Jahr', text: 'Wir melden uns vor dem Termin, prüfen und warten nach Stufe.' },
    { title: 'Kranbuch', text: 'Alle Berichte stehen im Kranbuch, abrufbar per QR-Code.' },
  ],
  faq: [
    {
      q: 'Was kostet das Service-Abo?',
      a: 'Der Preis gilt pro Kran und Jahr und hängt von Stufe und Kranart ab. [[PLATZHALTER: Preis bzw. Preisrahmen der Abo-Stufen]]',
    },
    {
      q: 'Gilt das Abo auch für Krane anderer Hersteller?',
      a: 'Ja. Das Abo gilt für Krane aller Marken – nicht nur für HS-Krananlagen.',
    },
    {
      q: 'Brauche ich ein Login für das Kranbuch?',
      a: 'Nein. Der QR-Code am Kran führt direkt zu den Einträgen dieses Krans. [[PRÜFEN: Zugang zum digitalen Kranbuch]]',
    },
    {
      q: 'Was passiert, wenn bei der Prüfung ein Mangel auftaucht?',
      a: 'Er steht im Prüfbericht, mit dem, was zu tun ist. Reparaturen offerieren wir separat; in der Stufe «Komplett» gibt es Rabatt auf Ersatzteile. [[PRÜFEN: Abo-Bedingungen]]',
    },
    {
      q: 'Wie lange läuft das Abo?',
      a: '[[PLATZHALTER: Laufzeit und Kündigung des Abos]]',
    },
  ],
  cta: {
    title: 'Abo-Offerte anfragen',
    lead: 'Wie viele Krane, welche Art, wo? Wir offerieren pro Kran und Jahr und melden uns innert {{promises.responseTime}}.',
    kind: 'abo',
    messageLabel: 'Welche Krane (Art, Hersteller) und welche Stufe interessiert Sie?',
  },
  related: [
    { href: '/krane/pruefung-wartung', label: 'Kranprüfung und Wartung', text: 'Was die Prüfpflicht verlangt – mit Prüfpflicht-Check.' },
    { href: '/krane/hs-krananlagen', label: 'HS-Krananlagen', text: 'Service und Ersatzteile für Krane aus Tuttwil.' },
    { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Wer muss wann was prüfen?', kind: 'ratgeber' },
  ],
  service: { name: 'Service-Abo für Krane mit digitalem Kranbuch', serviceType: 'Wartungsvertrag für Krananlagen' },
};

/** Modul: so funktioniert das digitale Kranbuch. */
export const kranbuch = {
  title: 'So funktioniert das digitale Kranbuch',
  lead: 'Das Kranbuch ist Pflicht – seine Form ist frei. Digital ist es dort, wo man es braucht: am Kran.',
  items: [
    { title: 'QR-Code am Kran', text: 'Ein Etikett mit QR-Code direkt am Kran oder an der Steuerung.' },
    { title: 'Alles an einem Ort', text: 'Prüfberichte, Wartungen und Reparaturen – mit Datum und Befund.' },
    { title: 'Termin im Blick', text: 'Die nächste Prüfung steht im Kranbuch; wir erinnern Sie vorher.' },
  ],
  review: '[[PRÜFEN: digitales Kranbuch – ab Start verfügbar oder «in Vorbereitung»?]]',
};
