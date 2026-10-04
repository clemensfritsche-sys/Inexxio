/**
 * Über uns (Auftrag Kap. 7.7): Wer wir sind (das WIR, nicht eine Person – Testnotiz #1147) ·
 * Zusagen · Geschichte · Werkstatt und Standort · Wo wir arbeiten (zuhause in der Werkstatt,
 * im Einsatz überall). Der Ort kommt aus dem ERP ({{erp.city}}, #1146/#1153).
 */
import type { Faq } from './types';

export const ueberUns = {
  title: 'Über uns',
  description:
    'INEXXIO (ehemals HS Steiner), Tuttwil-Wängi TG: Krantechnik, Fahrzeugtechnik und Sonderlösungen seit 1982 – im Einsatz in der ganzen Schweiz und weltweit.',
  hero: {
    eyebrow: 'Über uns',
    h1: 'Werkstatt mit Ingenieurwissen – in Tuttwil seit {{history.founded}}',
    lead:
      '{{brand.full}} ist das Unternehmen, das Heiri Steiner {{history.founded}} gegründet hat – heute mit demselben Handwerk und mit Ingenieurwissen aus dem Maschinenbau.',
  },
  summary:
    '{{brand.full}} plant, baut und betreut Krananlagen, wartet und repariert Fahrmischer und Aufbauten aller Marken und konstruiert Sonderlösungen. Die Werkstatt steht in {{erp.city}}.',
  /** Wer wir sind – das Team, nicht eine Person (#1147: «es braucht immer alle»). */
  team: {
    title: 'Wer wir sind',
    text: 'Hinter {{brand.name}} steht ein Team aus der Werkstatt: Mechanik, Schweiss- und Stahlbau, Konstruktion. Jede Anlage und jede Reparatur entsteht gemeinsam – von der ersten Skizze bis zum Service.',
    points: [
      'Krananlagen planen, bauen und betreuen',
      'Fahrmischer und Aufbauten warten und reparieren',
      'Konstruieren, schweissen, umbauen – auch, was es nicht zu kaufen gibt',
    ],
  },
  history: {
    title: 'Geschichte',
    text: 'Heiri Steiner hat die Reparaturwerkstätte {{history.founded}} gebaut. Seit {{history.cranesSince}} entstehen hier eigene Krananlagen für Landwirtschaft und Industrie – vermarktet {{history.markets}}. Mit der Übergabe wird aus HS Steiner die {{brand.legalName}}.',
    link: 'Die ganze Geschichte der Übergabe',
  },
  /** Die Werte der Firma (#1182) – wofür wir stehen; die Zusagen darunter machen sie prüfbar. */
  values: {
    title: 'Die Werte der {{brand.legalName}}',
    items: [
      { title: 'Qualität', text: 'Qualität in allem, was wir tun – vom ersten Gespräch bis zum Bericht.' },
      { title: 'Verlässlichkeit', text: 'Was wir zusagen, halten wir. Termine, Preise und Absprachen gelten.' },
      { title: 'Ehrlichkeit', text: 'Wir sagen offen, was es braucht – auch wenn das heisst: ersetzen statt reparieren.' },
      { title: 'Verantwortung', text: 'Krane und Fahrzeuge müssen sicher laufen. Dafür stehen wir mit unserer Arbeit ein.' },
    ],
  },
  promises: {
    title: 'Worauf Sie sich verlassen können',
    lead: 'Konkrete Zusagen statt schöner Worte.',
    items: [
      { title: 'Rückmeldung', text: 'Wir melden uns innert {{promises.responseTime}}.' },
      { title: 'Bericht', text: 'Jede Arbeit mit Bericht.' },
      { title: 'Offerte', text: 'Vor grösseren Arbeiten erhalten Sie eine Offerte.' },
      { title: 'Ersatzteile', text: 'Die Ersatzteile für unsere Anlagen liegen an Lager, oder wir fertigen sie neu an.' },
    ],
  },
  workshop: {
    title: 'Werkstatt und Standort',
    text: 'In {{erp.city}} steht unsere Werkstatt. Hier bauen wir Krananlagen, reparieren Fahrmischer und Aufbauten und fertigen Sonderlösungen.',
  },
  area: {
    title: 'Zuhause in der Werkstatt – im Einsatz, wo Sie uns brauchen',
    text: 'Unsere Werkstatt steht in {{erp.city}}. Im Einsatz sind wir {{area.summary}}: Krane prüfen, warten und reparieren wir dort, wo sie stehen; Fahrmischer, Aufbauten und Baumaschinen kommen meist in unsere Werkstatt. In der Nähe sind wir schnell bei Ihnen, für weiter entfernte Einsätze planen wir gemeinsam.',
  },
  areaFaq: [
    {
      q: 'Kommen Sie auch ins Ausland?',
      a: 'Ja. Krananlagen, Service und Sonderlösungen bieten wir weltweit an – geplant und zuverlässig. Fragen Sie an.',
    },
    {
      q: 'Kostet die Anfahrt extra?',
      a: 'Ja, nach Aufwand. Sie sehen die Anfahrt vorher in der Offerte – auf der Rechnung steht keine Überraschung.',
    },
    {
      q: 'Arbeiten Sie vor Ort oder in der Werkstatt?',
      a: 'Krane prüfen, warten und reparieren wir dort, wo sie stehen. Fahrmischer kommen für Service und Reparatur in unsere Werkstatt in {{erp.city}}.',
    },
  ] satisfies Faq[],
};
