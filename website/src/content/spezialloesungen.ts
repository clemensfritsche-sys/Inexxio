/**
 * Speziallösungen – Spezialmaschinenbau für den Bau: Maschinen, die eine bestimmte Aufgabe
 * auf einer besonderen Baustelle erledigen, oft automatisiert. Einzelstücke und Kleinserien,
 * keine Serienmaschinen. Eigene Bereichsseite ohne Unterseiten.
 * Nicht auf die Seite: Mietpool, Hinweise zu CE oder Maschinenverordnung, Konditionen der
 * Co-Entwicklung (Prozentsätze) – die gibt es im Gespräch.
 */
import { site } from '../config/site.mjs';
import type { Step, SubPage } from './types';
import { promiseFaq } from './promises';

export const spezialloesungen: SubPage = {
  area: 'spezialloesungen',
  path: '/spezialloesungen',
  crumb: 'Speziallösungen',
  title: 'Spezialmaschinen für den Bau',
  description:
    'Sondermaschinen, Vorrichtungen und Anbauten für Baugeräte – für besondere Baustellen, als Einzelstück oder Kleinserie. Mit Garantie. Aus Tuttwil-Wängi TG.',
  hero: {
    eyebrow: 'Speziallösungen',
    h1: 'Spezialmaschinen nach Mass für die ==Baustelle==',
    lead:
      'Für Aufgaben, die kein Hersteller löst: Wir konstruieren und bauen Sondermaschinen, Vorrichtungen und Anbauten für Ihre Geräte – als Einzelstück oder Kleinserie, unabhängig von der Marke.',
    photo: 'arbeit-werkstatt',
    primary: { label: 'Aufgabe schildern', href: '#anfrage' },
  },
  summary:
    '{{brand.full}} baut Spezialmaschinen für den Bau: Sondermaschinen und Vorrichtungen für besondere Baustellen, die Automatisierung von Abläufen und Anbauten für bestehende Geräte – etwa Rüttler, Podeste und Begehungen, Klemmen, Hilfskrane und Greifer. Einzelstücke und Kleinserien, unabhängig von der Marke des Geräts, konstruiert und gebaut in der eigenen Werkstatt in Tuttwil-Wängi TG. Nicht zufrieden, zahlen Sie nur die Hälfte.',
  glance: {
    forWhom: 'Bau- und Spezialtiefbauunternehmen mit eigener Geräteflotte, Vermieter und Händler von Baugeräten.',
    what: 'Machbarkeit prüfen, konstruieren, in der eigenen Werkstatt bauen und bei Ihnen in Betrieb nehmen.',
    deliverables: 'Eine Maschine oder einen Anbau, der genau Ihre Aufgabe erledigt – mit Zeichnungen und Unterlagen.',
  },
  promises: ['garantie'],
  scope: {
    title: 'Was wir bauen',
    lead: 'Einzelstücke und Kleinserien – keine Serienmaschinen.',
    items: [
      { title: 'Sondermaschinen', text: 'Für eine bestimmte Aufgabe auf einer besonderen Baustelle – wo es nichts zu kaufen gibt.' },
      { title: 'Vorrichtungen', text: 'Damit ein Arbeitsschritt sicher, schnell und wiederholbar gelingt.' },
      { title: 'Automatisierung', text: 'Abläufe, die heute Hand und Zeit kosten, laufen danach von selbst.' },
      { title: 'Anbauten für bestehende Geräte', text: 'Rüttler, Podeste und Begehungen, Klemmen, Hilfskrane, Greifer.' },
      { title: 'Markenunabhängig', text: 'Für Geräte aller Hersteller – wir passen den Anbau an Ihr Gerät an.' },
      { title: 'Service danach', text: 'Wer es gebaut hat, kennt es – Wartung und Reparatur aus derselben Hand.' },
    ],
  },
  faq: [
    {
      q: 'Welche Aufträge passen zu Ihnen?',
      a: 'Einzelstücke und Kleinserien – vom Anbau für ein bestehendes Gerät bis zur Sondermaschine für eine besondere Baustelle. Serienmaschinen bauen wir nicht.',
    },
    {
      q: 'Brauche ich eine fertige Zeichnung?',
      a: 'Nein. Schildern Sie die Aufgabe – eine Skizze, ein Foto oder ein Video vom Einsatz genügt. Die Konstruktion übernehmen wir.',
    },
    {
      q: 'Was heisst Co-Entwicklung?',
      a: 'Sie entwickeln mit und zahlen dafür weniger. Die Rechte an der Lösung bleiben bei {{brand.name}}; verkaufen wir sie weiter, erhalten Sie einen Anteil. Die Einzelheiten besprechen wir im Gespräch.',
    },
    {
      q: 'Was kostet eine Speziallösung?',
      a: 'Nach der Machbarkeitsprüfung erhalten Sie einen Fixpreis – vor jeder Arbeit.',
    },
    promiseFaq.garantie,
    {
      q: 'Bauen Sie für Geräte jeder Marke?',
      a: 'Ja. Wir sind unabhängig und passen den Anbau an Ihr Gerät an.',
    },
  ],
  related: [
    { href: '/krantechnik/krane-nach-mass', label: 'Krane nach Mass', text: 'Sonderkrane und Industriekrane.' },
    { href: '/fahrzeugtechnik/trommeltausch', label: 'Trommeltausch', text: 'Neue Trommel statt neuer Fahrmischer.' },
    { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Was Prüfpflicht und Dokumentation verlangen.', kind: 'ratgeber' },
  ],
  service: { name: 'Speziallösungen', serviceType: 'Spezialmaschinenbau für den Bau: Sondermaschinen, Vorrichtungen und Anbauten für Baugeräte' },
  keywords: ['Spezialmaschinenbau Bau', 'Sondermaschine Baustelle', 'Anbaugerät Baumaschine', 'Spezialtiefbau Gerät', 'Vorrichtungsbau'],
};

/** Modul: Ablauf – kurz. */
export const specialSteps = {
  title: 'So läuft es',
  items: [
    { title: 'Aufgabe', text: 'Sie schildern, was die Maschine leisten soll – mit Skizze, Foto oder Video vom Einsatz.' },
    { title: 'Machbarkeit', text: 'Wir prüfen, ob und wie es geht, und nennen den Rahmen.' },
    { title: 'Konstruktion', text: 'Wir konstruieren und rechnen; Sie geben die Lösung frei.' },
    { title: 'Bau', text: 'In unserer eigenen Werkstatt in Tuttwil.' },
    { title: 'Inbetriebnahme', text: 'Bei Ihnen, mit Einweisung, Zeichnungen und Unterlagen.' },
  ] satisfies Step[],
};

/** Modul: Co-Entwicklung (Anker #co-entwicklung) – ohne Prozentsätze, ohne Konditionen. */
export const coDevelopment = {
  title: 'Mitentwickeln und weniger zahlen',
  text: 'Bringen Sie Ihre Erfahrung von der Baustelle ein – dafür zahlen Sie weniger. Die Rechte an der Lösung bleiben bei {{brand.name}}, und verkaufen wir sie weiter, erhalten Sie einen Anteil daran. Die Einzelheiten besprechen wir im Gespräch.',
  points: ['Ihr Wissen aus dem Einsatz', 'Unser Ingenieurwissen und unsere Werkstatt', 'Ein Anteil an weiteren Verkäufen'],
};

/** Modul: Wer dahintersteht – sachlich, kurz, ohne fremde Logos. */
export const specialBackground = {
  title: 'Wir kennen die Wünsche, die Hersteller nicht erfüllen',
  text: `${site.people.owner.name} ist Maschinenbauingenieur und hat bei Liebherr Bohrgeräte mitentwickelt. Er weiss, wo Serienmaschinen an ihre Grenzen kommen – und wie man eine Lösung baut, die auf der Baustelle hält.`,
};
