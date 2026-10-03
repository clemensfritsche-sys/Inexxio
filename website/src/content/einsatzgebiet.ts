/** Einsatzgebiet (Auftrag Kap. 6.2, 12.6): EINE starke Seite statt vieler dünner Ortsseiten. */
import type { Faq } from './types';

export const einsatzgebiet = {
  title: 'Einsatzgebiet Ostschweiz',
  description:
    'Kranservice und Fahrmischer-Service rund eine Stunde ab Tuttwil-Wängi: Thurgau, St. Gallen, Winterthur, Frauenfeld, Wil, Raum Zürich und Schaffhausen.',
  hero: {
    eyebrow: 'Einsatzgebiet',
    h1: 'Kranservice in Thurgau, St. Gallen, Winterthur und Zürich',
    lead:
      'Wir sind rund eine Stunde im Umkreis von Tuttwil-Wängi unterwegs. Werkstatt und Ersatzteillager liegen mittendrin – das hält die Wege kurz.',
  },
  summary:
    '{{brand.full}} arbeitet an Kranen und Fahrmischern rund eine Stunde im Umkreis von Tuttwil-Wängi TG: im Thurgau, im Kanton St. Gallen, im Raum Winterthur und Zürich und in Schaffhausen. {{area.review}}',
  regions: [
    { name: 'Thurgau', places: 'Frauenfeld, Weinfelden, Wängi, Aadorf, Sirnach, Münchwilen, Kreuzlingen, Romanshorn, Amriswil' },
    { name: 'St. Gallen', places: 'Wil, Uzwil, Gossau, St. Gallen, Wattwil, Rapperswil-Jona' },
    { name: 'Raum Winterthur', places: 'Winterthur, Elgg, Turbenthal, Seuzach, Andelfingen' },
    { name: 'Raum Zürich', places: 'Uster, Effretikon, Kloten, Zürich' },
    { name: 'Schaffhausen', places: 'Schaffhausen, Stein am Rhein, Diessenhofen' },
    { name: 'Appenzell Ausserrhoden', places: 'Herisau' },
  ],
  regionsReview: '[[PRÜFEN: Orte im Einsatzgebiet]]',
  faq: [
    {
      q: 'Kommen Sie auch ausserhalb dieses Gebiets?',
      a: 'Fragen Sie an – bei grösseren Aufträgen und für HS-Krananlagen sind wir auch weiter unterwegs. {{area.abroad}} {{area.abroadReview}}',
    },
    {
      q: 'Kostet die Anfahrt extra?',
      a: '[[PLATZHALTER: Berechnung der Anfahrt]] Im [Service-Abo](/service-abo) ab der Stufe «Service» ist die Anfahrt zum Fixpreis enthalten.',
    },
    {
      q: 'Arbeiten Sie vor Ort oder in der Werkstatt?',
      a: 'Krane prüfen, warten und reparieren wir dort, wo sie stehen. Fahrmischer kommen für Service und Reparatur in unsere Werkstatt in Tuttwil. [[PRÜFEN: Einsätze vor Ort bei Fahrmischern]]',
    },
  ] satisfies Faq[],
};
