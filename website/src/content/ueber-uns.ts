/**
 * Über uns (Auftrag Kap. 7.7): Clemens (Porträt, Werdegang, Botschaft) · Team (abgeschaltet)
 * · Geschichte · «Worauf Sie sich verlassen können» · Werkstatt und Standort ·
 * Einsatzgebiet (Karte + Regionen als Fliesstext – keine Ortsseiten) · Ausbildung.
 */
import type { Faq } from './types';

export const ueberUns = {
  title: 'Über uns und Einsatzgebiet',
  description:
    'INEXXIO (ehemals HS Steiner), Tuttwil-Wängi TG: Krantechnik, Fahrzeugtechnik und Sonderlösungen seit 1982 – im Einsatz in Thurgau, St. Gallen, Winterthur.',
  hero: {
    eyebrow: 'Über uns',
    h1: 'Werkstatt mit Ingenieurwissen – in Tuttwil seit {{history.founded}}',
    lead:
      '{{brand.full}} ist das Unternehmen, das Heiri Steiner {{history.founded}} gegründet hat. Heute führt es Clemens Fritsche – mit demselben Handwerk und mit Ingenieurwissen aus dem Maschinenbau.',
  },
  summary:
    '{{brand.full}} plant und baut Krananlagen, wartet und repariert Krane, Fahrmischer und Aufbauten aller Marken und konstruiert Sonderlösungen. Werkstatt und Ersatzteillager stehen in Tuttwil-Wängi TG; im Einsatz sind wir in der {{area.summary}}. Geschäftsführer ist Clemens Fritsche.',
  owner: {
    title: 'Clemens Fritsche',
    career: 'Werdegang',
  },
  history: {
    title: 'Geschichte',
    text: 'Heiri Steiner hat die Reparaturwerkstätte {{history.founded}} in Tuttwil-Wängi gebaut. Seit {{history.cranesSince}} entstehen hier eigene Krananlagen für Landwirtschaft und Industrie – vermarktet {{history.markets}}. Mit der Übergabe an Clemens Fritsche wird aus HS Steiner die {{brand.legalName}}.',
    link: 'Die ganze Geschichte der Übergabe',
  },
  promises: {
    title: 'Worauf Sie sich verlassen können',
    lead: 'Konkrete Zusagen statt schöner Worte. [[PLATZHALTER: Zusagen definieren und freigeben]]',
    items: [
      { title: 'Rückmeldung', text: 'Wir melden uns innert {{promises.responseTime}}.' },
      { title: 'Bericht', text: 'Jede Arbeit mit Bericht – bei Kranen für das Kranbuch.' },
      { title: 'Offerte', text: 'Vor grösseren Arbeiten erhalten Sie eine Offerte. [[PRÜFEN: Zusage freigeben]]' },
      { title: 'Ersatzteile', text: 'Für die Anlagen aus Tuttwil halten wir Ersatzteile an Lager. [[PRÜFEN: Zusage freigeben]]' },
    ],
  },
  workshop: {
    title: 'Werkstatt und Standort',
    text: 'In Tuttwil-Wängi TG stehen Werkstatt und Ersatzteillager – Waldweg 1, mitten im Einsatzgebiet. Hier bauen wir Krananlagen, reparieren Fahrmischer und Aufbauten und fertigen Sonderlösungen.',
  },
  area: {
    title: 'Einsatzgebiet',
    lead: 'Werkstatt und Ersatzteillager liegen mittendrin – das hält die Wege kurz.',
    text: 'Im Einsatz sind wir im Thurgau, im Kanton St. Gallen, im Raum Winterthur und Zürich und in Schaffhausen – rund um Frauenfeld, Wil, Winterthur und Weinfelden. Krane prüfen, warten und reparieren wir dort, wo sie stehen; Fahrmischer, Aufbauten und Baumaschinen kommen meist in unsere Werkstatt in Tuttwil. {{area.review}}',
    regions: [
      { name: 'Thurgau', places: 'Frauenfeld, Weinfelden, Wängi, Aadorf, Sirnach, Münchwilen, Kreuzlingen, Romanshorn, Amriswil' },
      { name: 'St. Gallen', places: 'Wil, Uzwil, Gossau, St. Gallen, Wattwil, Rapperswil-Jona' },
      { name: 'Raum Winterthur', places: 'Winterthur, Elgg, Turbenthal, Seuzach, Andelfingen' },
      { name: 'Raum Zürich', places: 'Uster, Effretikon, Kloten, Zürich' },
      { name: 'Schaffhausen', places: 'Schaffhausen, Stein am Rhein, Diessenhofen' },
      { name: 'Appenzell Ausserrhoden', places: 'Herisau' },
    ],
    regionsReview: '[[PRÜFEN: Orte im Einsatzgebiet]]',
    abroad: '{{area.abroad}} {{area.abroadReview}}',
  },
  areaFaq: [
    {
      q: 'Kommen Sie auch ausserhalb dieses Gebiets?',
      a: 'Fragen Sie an – bei grösseren Aufträgen und für Krananlagen sind wir auch weiter unterwegs. {{area.abroad}} {{area.abroadReview}}',
    },
    {
      q: 'Kostet die Anfahrt extra?',
      a: '[[PLATZHALTER: Berechnung der Anfahrt]]',
    },
    {
      q: 'Arbeiten Sie vor Ort oder in der Werkstatt?',
      a: 'Krane prüfen, warten und reparieren wir dort, wo sie stehen. Fahrmischer kommen für Service und Reparatur in unsere Werkstatt in Tuttwil. [[PRÜFEN: Einsätze vor Ort bei Fahrmischern]]',
    },
  ] satisfies Faq[],
  training: {
    title: 'Ausbildung',
    text: '[[PRÜFEN: Ausbildungsbetrieb – ob und in welchen Berufen wir ausbilden]]',
  },
};
