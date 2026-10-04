/**
 * Über uns (Auftrag Kap. 7.7): Clemens (Porträt, Werdegang, Botschaft) · Team (abgeschaltet)
 * · Geschichte · «Worauf Sie sich verlassen können» · Werkstatt und Standort ·
 * Wo wir arbeiten (zuhause in Tuttwil, im Einsatz überall – keine Grenzen) · Ausbildung.
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
      '{{brand.full}} ist das Unternehmen, das Heiri Steiner {{history.founded}} gegründet hat. Heute führt es Clemens Fritsche – mit demselben Handwerk und mit Ingenieurwissen aus dem Maschinenbau.',
  },
  summary:
    '{{brand.full}} plant, baut und betreut Krananlagen, wartet und repariert Fahrmischer und Aufbauten aller Marken und konstruiert Sonderlösungen. Die Werkstatt steht in Tuttwil-Wängi TG. Das Unternehmen führt Clemens Fritsche.',
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
      { title: 'Ersatzteile', text: 'Die Ersatzteile für die Anlagen aus Tuttwil liegen an Lager, oder wir fertigen sie neu an.' },
    ],
  },
  workshop: {
    title: 'Werkstatt und Standort',
    text: 'In Tuttwil-Wängi TG steht unsere Werkstatt. Hier bauen wir Krananlagen, reparieren Fahrmischer und Aufbauten und fertigen Sonderlösungen.',
  },
  area: {
    title: 'Zuhause in Tuttwil – im Einsatz, wo Sie uns brauchen',
    text: 'Werkstatt und Ersatzteillager stehen in {{area.home}}. Im Einsatz sind wir {{area.summary}}: Krane prüfen, warten und reparieren wir dort, wo sie stehen; Fahrmischer, Aufbauten und Baumaschinen kommen meist in unsere Werkstatt. In der Nähe sind wir schnell bei Ihnen, für weiter entfernte Einsätze planen wir gemeinsam.',
  },
  areaFaq: [
    {
      q: 'Kommen Sie auch ins Ausland?',
      a: 'Ja. Krananlagen, Service und Sonderlösungen bieten wir weltweit an – nicht immer innert Stunden, aber geplant und zuverlässig. Fragen Sie an.',
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
