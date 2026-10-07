/**
 * Über uns: Wer wir sind (das WIR, nicht eine Person – Testnotiz #1147) · Werte · Zusagen ·
 * die Übergabe (Texte in content/uebergabe.ts) · Werkstatt und Einsatzgebiet · Fragen.
 * Der Ort kommt aus dem ERP ({{erp.city}}, #1146/#1153).
 */
import type { Faq } from './types';

export const ueberUns = {
  title: 'Über uns',
  description:
    'INEXXIO (ehemals HS Steiner) in Tuttwil-Wängi TG: Werkstatt mit Ingenieurwissen seit 1982 – Team, Werte, Geschichte und die Nachfolge von Heiri Steiner.',
  hero: {
    eyebrow: 'Über uns',
    h1: 'Werkstatt mit Ingenieurwissen – in Tuttwil seit {{history.founded}}',
    lead:
      '{{brand.full}} ist das Unternehmen, das Heiri Steiner {{history.founded}} gegründet hat – heute mit demselben Handwerk und mit Ingenieurwissen aus dem Maschinenbau.',
  },
  summary:
    '{{brand.full}} ist ein Servicebetrieb mit eigenen Produkten: Wir betreuen und bauen Krane, überholen und tauschen Trommeln von Fahrmischern und konstruieren Sonderlösungen. Die Werkstatt steht in {{erp.city}}. Mit der Übergabe von Heiri Steiner an Clemens Fritsche wird aus der {{brand.formerLegalName}} die {{brand.legalName}} – dieselbe Werkstatt, dieselbe Telefonnummer, derselbe Service für alle bestehenden Anlagen.',
  /** Wer wir sind – das Team, nicht eine Person (#1147: «es braucht immer alle»). */
  team: {
    title: 'Wer wir sind',
    text: 'Hinter {{brand.name}} steht ein Team aus der Werkstatt: Mechanik, Schweiss- und Stahlbau, Konstruktion. Jede Anlage und jede Reparatur entsteht gemeinsam – von der ersten Skizze bis zum Service.',
    points: [
      'Krane bauen, prüfen, warten und modernisieren',
      'Fahrmischer warten, reparieren und mit neuer Trommel ausrüsten',
      'Konstruieren, schweissen, umbauen – auch, was es nicht zu kaufen gibt',
    ],
  },
  /** Die Werte der Firma (#1182) – wofür wir stehen; die Zusagen darunter machen sie prüfbar. */
  values: {
    title: 'Die Werte der {{brand.legalName}}',
    items: [
      { title: 'Handschlagqualität', text: 'Ein Wort gilt. Was wir zusagen – Termin, Preis, Absprache –, halten wir.' },
      { title: 'Qualität', text: 'Saubere Arbeit in allem, was wir tun – vom ersten Gespräch bis zum Bericht.' },
      { title: 'Zuverlässigkeit', text: 'Ihr Kran, Ihr Fahrzeug muss laufen. Dafür planen wir voraus und sind erreichbar, wenn etwas stillsteht.' },
      { title: 'Innovation', text: 'Modernisieren statt ersetzen: neue Technik auf bewährtem Stahlbau, neue Trommel auf bewährtem Fahrgestell.' },
      { title: 'Design', text: 'Eine Anlage soll gut funktionieren, sicher zu bedienen sein und gut aussehen – bis ins Detail.' },
    ],
  },
  /** Die Zusagen – Über uns und /service zeigen dieselbe Liste (vorher stand «So arbeiten wir» daneben). */
  promises: {
    title: 'Worauf Sie sich verlassen können',
    lead: 'Konkrete Zusagen statt schöner Worte – dazu die INEXXIO Zufriedenheitsgarantie: Nicht zufrieden? Sie zahlen nur die Hälfte.',
    items: [
      { title: 'Fixpreis vor jeder Arbeit', text: 'Sie wissen vorher, was es kostet. Auf der Rechnung steht keine Überraschung.' },
      { title: 'Keine Mindestlaufzeit', text: 'Sie bleiben, weil es passt – nicht, weil ein Vertrag Sie hält.' },
      { title: 'Rückmeldung', text: 'Wir melden uns innert {{promises.responseTime}}.' },
      { title: 'Bericht', text: 'Jede Arbeit mit Bericht.' },
      { title: 'Ersatzteile', text: 'Die Ersatzteile für unsere Krananlagen liegen an Lager, oder wir fertigen sie neu an.' },
    ],
  },
  /** Werkstatt, Standort und Einsatzgebiet – EIN Abschnitt (vorher zwei, die beide «Werkstatt steht in …» sagten). */
  workshop: {
    title: 'Zuhause in der Werkstatt – im Einsatz, wo Sie uns brauchen',
    text: 'In {{erp.city}} steht unsere Werkstatt. Hier bauen wir Krananlagen, reparieren Fahrmischer und Aufbauten und fertigen Sonderlösungen. Im Einsatz sind wir {{area.summary}}: Krane prüfen, warten und reparieren wir dort, wo sie stehen; Fahrmischer, Aufbauten und Baumaschinen kommen meist in unsere Werkstatt. In der Nähe sind wir schnell bei Ihnen, für weiter entfernte Einsätze planen wir gemeinsam.',
  },
  areaFaq: [
    {
      q: 'Kommen Sie auch ins Ausland?',
      a: 'Ja. Zuerst in Deutschland und Österreich, darüber hinaus dort, wo Sie uns brauchen – geplant und zuverlässig. Fragen Sie an.',
    },
    {
      q: 'Kostet die Anfahrt extra?',
      a: 'Die Anfahrt steht im Fixpreis, den Sie vor der Arbeit erhalten – auf der Rechnung steht keine Überraschung.',
    },
  ] satisfies Faq[],
};
