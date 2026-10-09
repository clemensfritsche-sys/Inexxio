/**
 * Speziallösungen – Spezialmaschinenbau quer durch alle Bereiche: für Krane, Fahrzeuge und
 * Baumaschinen. Maschinen, Anbauten und Vorrichtungen, die eine bestimmte Aufgabe erledigen,
 * oft automatisiert. Einzelstücke und Kleinserien, keine Serienmaschinen.
 *
 * Die Seite hat ein eigenes Layout (src/pages/spezialloesungen.astro); das `SubPage`-Objekt
 * liefert Titel, Beschreibung, Zusammenfassung, Leistungsumfang und FAQ für Sitemap,
 * llms.txt und JSON-LD. Bildsprache: Grau ist die Serie, Rot ist, was wir dazubauen.
 *
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
  title: 'Spezialmaschinen nach Mass',
  description:
    'Wenn kein Hersteller liefert, was Ihre Aufgabe braucht: Spezialmaschinen, Anbauten und Vorrichtungen für Krane, Fahrzeuge und Baumaschinen. Mit Garantie.',
  hero: {
    eyebrow: 'Speziallösungen',
    h1: 'Ihre Aufgabe. Unsere ==Maschine==.',
    lead:
      'Wenn kein Hersteller liefert, was Ihre Arbeit verlangt, bauen wir es: Spezialmaschinen, Anbauten und Vorrichtungen für Krane, Fahrzeuge und Baumaschinen – als Einzelstück oder Kleinserie.',
    photo: 'arbeit-werkstatt',
    primary: { label: 'Aufgabe schildern', href: '#anfrage' },
  },
  summary:
    '{{brand.full}} baut Spezialmaschinen nach Mass – für Krane, Fahrzeuge und Baumaschinen: Sonderkrane, Hilfskrane und Lastaufnahmen, Sonderaufbauten und Anbauten für Fahrzeuge, Anbaugeräte wie Rüttler, Klemmen und Greifer, Podeste und Begehungen, Vorrichtungen und die Automatisierung von Abläufen. Einzelstücke und Kleinserien, konstruiert von einem Maschinenbauingenieur und gebaut in der eigenen Werkstatt in Tuttwil-Wängi TG. Fixpreis vor Baubeginn; nicht zufrieden, übernehmen wir 50 %.',
  glance: {
    forWhom: 'Bauunternehmen und Spezialtiefbau mit eigener Geräteflotte, Vermieter und Händler von Baugeräten – und alle Betriebe mit Kranen oder Fahrzeugen, deren Aufgabe kein Hersteller löst.',
    what: 'Machbarkeit prüfen, konstruieren, in der eigenen Werkstatt bauen und bei Ihnen in Betrieb nehmen.',
    deliverables: 'Eine Maschine, die genau Ihre Aufgabe erledigt – mit Zeichnungen, Unterlagen und Service aus derselben Hand.',
  },
  promises: ['garantie', 'inexxio365', 'erstservice'],
  scope: {
    title: 'Was wir bauen',
    lead: 'Einzelstücke und Kleinserien – keine Serienmaschinen.',
    items: [
      { title: 'Für Krane', text: 'Sonderkrane, Hilfskrane, Ausleger, Lastaufnahmen und Greifer nach Mass.' },
      { title: 'Für Fahrzeuge', text: 'Sonderaufbauten und Anbauten, die kein Hersteller anbietet.' },
      { title: 'Für Baumaschinen', text: 'Anbaugeräte wie Rüttler, Klemmen und Greifer, Podeste und Begehungen.' },
      { title: 'Vorrichtungen', text: 'Damit ein Arbeitsschritt sicher, schnell und wiederholbar gelingt.' },
      { title: 'Automatisierung', text: 'Abläufe, die heute Hand und Zeit kosten, laufen danach von selbst.' },
      { title: 'Service danach', text: 'Wer es gebaut hat, kennt es – Wartung und Reparatur aus derselben Hand.' },
    ],
  },
  faq: [
    {
      q: 'Welche Aufträge passen zu Ihnen?',
      a: 'Einzelstücke und Kleinserien – vom Anbau für ein bestehendes Gerät bis zur Maschine für eine besondere Baustelle. Serienmaschinen bauen wir nicht.',
    },
    {
      q: 'Brauche ich eine fertige Zeichnung?',
      a: 'Nein. Schildern Sie die Aufgabe – eine Skizze, ein Foto oder ein Video vom Einsatz genügt. Die Konstruktion übernehmen wir.',
    },
    {
      q: 'Was kostet eine Speziallösung?',
      a: 'Nach der Machbarkeitsprüfung erhalten Sie einen Fixpreis – bevor wir bauen.',
    },
    promiseFaq.garantie,
    {
      q: 'Was heisst Co-Entwicklung?',
      a: 'Sie entwickeln mit und zahlen dafür weniger. Die Rechte an der Lösung bleiben bei {{brand.name}}; verkaufen wir sie weiter, erhalten Sie einen Anteil. Die Einzelheiten besprechen wir im Gespräch.',
    },
    {
      q: 'Bleibt die Lösung bei Ihnen in Betreuung?',
      a: 'Ja. Wartung, Reparatur und Ersatzteile kommen aus derselben Werkstatt, die sie gebaut hat.',
    },
  ],
  related: [
    { href: '/krantechnik/krane-nach-mass', label: 'Krane nach Mass', text: 'Sonderkrane und Industriekrane.' },
    { href: '/fahrzeugtechnik/trommeltausch', label: 'Trommeltausch', text: 'Neue Trommel statt neuer Fahrmischer.' },
  ],
  service: { name: 'Speziallösungen', serviceType: 'Spezialmaschinenbau für Krane, Fahrzeuge und Baumaschinen' },
  keywords: ['Spezialmaschinenbau', 'Sondermaschine Baustelle', 'Anbaugerät Baumaschine', 'Sonderkran', 'Sonderaufbau', 'Vorrichtungsbau'],
};

/** Kurz und belegt – unter dem Seitenkopf. */
export const specialFacts = [
  { value: 'Einzelstück', label: 'bis Kleinserie' },
  { value: 'Nach Mass', label: 'passend zu Ihrem Gerät' },
  { value: 'Fixpreis', label: 'bevor wir bauen' },
  { value: '50 %', label: 'übernehmen wir, wenn Sie nicht zufrieden sind' },
];

/** Das Prinzip: warum es Speziallösungen braucht – und was Sie davon haben. */
export const specialPrinciple = {
  eyebrow: 'Das Prinzip',
  title: 'Serienmaschinen sind für den Durchschnitt gebaut. Ihre Aufgabe ist es nicht.',
  lead: 'Was dazwischen fehlt, erledigt heute meist ein Mensch – mit Zeit, Umwegen und Improvisation. Wir bauen die Maschine, die diese Lücke schliesst.',
  gains: [
    { title: 'Weniger Handarbeit', text: 'Was heute von Hand geschieht, erledigt danach die Maschine – schneller und jedes Mal gleich.' },
    { title: 'Mehr Sicherheit', text: 'Wer nicht mehr improvisieren muss, steht nicht mehr unter der Last.' },
    { title: 'Ihr Vorsprung', text: 'Sie nehmen Aufträge an, die andere mit Seriengeräten ablehnen müssen.' },
  ],
};

/** Drei Felder, ein Prinzip – je mit Bild (src/assets/illustrations/spezial-*.svg). */
export const specialFields = [
  {
    id: 'krane',
    illo: 'krane' as const,
    title: 'Für Krane',
    text: 'Wo der Katalogkran aufhört: Ausleger, Hilfskrane und Lastaufnahmen für die Last, die nur Sie heben.',
    examples: ['Sonderkrane und Hilfskrane', 'Ausleger und Hebezeuge nach Mass', 'Lastaufnahmen und Greifer'],
    link: { href: '/krantechnik/krane-nach-mass#sonderkrane', label: 'Krane nach Mass' },
  },
  {
    id: 'fahrzeuge',
    illo: 'fahrzeuge' as const,
    title: 'Für Fahrzeuge',
    text: 'Das Fahrgestell ist Serie, die Aufgabe nicht: Aufbauten und Anbauten, die kein Hersteller anbietet.',
    examples: ['Sonderaufbauten', 'Ladekrane und Arbeitsbühnen am Fahrzeug', 'Anbauten am Fahrmischer'],
    link: { href: '/fahrzeugtechnik', label: 'Fahrzeugtechnik' },
  },
  {
    id: 'baumaschinen',
    illo: 'baumaschinen' as const,
    title: 'Für Baumaschinen',
    text: 'Ihr Gerät kann mehr, als der Hersteller vorsieht: Anbaugeräte, Vorrichtungen und Automatisierung für die besondere Baustelle.',
    examples: ['Rüttler, Klemmen und Greifer', 'Podeste und Begehungen', 'Vorrichtungen und Automatisierung'],
  },
];

/** Modul: Ablauf – und was Sie dafür tun. */
export const specialSteps = {
  title: 'Vom Problem zur Maschine',
  lead: 'Ihr Aufwand zu Beginn: eine Skizze, ein Foto oder ein Video vom Einsatz.',
  items: [
    { title: 'Aufgabe', text: 'Sie schildern, was die Maschine leisten soll.' },
    { title: 'Machbarkeit', text: 'Wir prüfen, ob und wie es geht, und nennen den Fixpreis.' },
    { title: 'Konstruktion', text: 'Wir konstruieren und rechnen; Sie geben frei.' },
    { title: 'Bau', text: 'In unserer eigenen Werkstatt in Tuttwil.' },
    { title: 'Inbetriebnahme', text: 'Bei Ihnen, mit Einweisung und Unterlagen.' },
  ] satisfies Step[],
};

/** Modul: Co-Entwicklung (Anker #co-entwicklung) – ohne Prozentsätze, ohne Konditionen. */
export const coDevelopment = {
  eyebrow: 'Co-Entwicklung',
  title: 'Entwickeln Sie mit – und verdienen Sie mit.',
  text: 'Sie kennen die Baustelle, wir die Maschine. Bringen Sie Ihre Erfahrung ein und zahlen Sie dafür weniger. Die Rechte an der Lösung bleiben bei {{brand.name}} – und verkaufen wir sie weiter, erhalten Sie einen Anteil. Die Einzelheiten besprechen wir im Gespräch.',
  points: [
    { title: 'Sie zahlen weniger', text: 'Ihr Wissen aus dem Einsatz ist Teil der Entwicklung.' },
    { title: 'Sie verdienen mit', text: 'An jedem weiteren Verkauf der Lösung erhalten Sie einen Anteil.' },
    { title: 'Sie sind zuerst dran', text: 'Die Maschine entsteht an Ihrer Aufgabe – und läuft zuerst bei Ihnen.' },
  ],
};

/** Modul: Wer dahintersteht – sachlich, kurz, ohne fremde Logos. */
export const specialBackground = {
  eyebrow: 'Wer dahintersteht',
  title: 'Ingenieur und Werkstatt unter einem Dach',
  text: `${site.people.owner.name} ist Maschinenbauingenieur und hat bei Liebherr Bohrgeräte mitentwickelt. Er kennt die Wünsche, die Hersteller nicht erfüllen – und weiss, wie man eine Lösung baut, die auf der Baustelle hält.`,
  facts: [
    'Entwicklung von Bohrgeräten bei Liebherr',
    'Krane bauen wir seit {{history.cranesSince}} selbst',
    'Konstruktion, Stahlbau und Montage aus einer Hand',
  ],
};
