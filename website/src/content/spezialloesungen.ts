/**
 * Speziallösungen – Spezialmaschinenbau quer durch alle Bereiche: für Krane, Fahrzeuge und
 * Baumaschinen. Maschinen, Anbauten und Vorrichtungen, die eine bestimmte Aufgabe erledigen,
 * oft automatisiert. Einzelstücke und Kleinserien, keine Serienmaschinen.
 *
 * Die Seite hat ein eigenes Layout (src/pages/spezialloesungen.astro); das `SubPage`-Objekt
 * liefert Titel, Beschreibung, Zusammenfassung, Leistungsumfang und FAQ für Sitemap,
 * llms.txt und JSON-LD. Bildsprache: Grau ist die Serie, Rot ist, was wir dazubauen.
 *
 * Nicht auf die Seite: Mietpool, Hinweise zu CE oder Maschinenverordnung.
 */
import { site } from '../config/site.mjs';
import type { SubPage } from './types';
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
    h1: 'Speziallösungen',
    lead: 'Wenn kein Hersteller liefert, was Ihre Arbeit verlangt, bauen wir es für Sie.',
    photo: 'arbeit-werkstatt',
    primary: { label: 'Aufgabe schildern', href: '#anfrage' },
  },
  summary:
    '{{brand.full}} baut Spezialmaschinen nach Mass – für Krane, Fahrzeuge und Baumaschinen: Sonderkrane, Hilfskrane und Lastaufnahmen, Sonderaufbauten und Anbauten für Fahrzeuge, Anbaugeräte wie Rüttler, Klemmen und Greifer, Podeste und Begehungen, Vorrichtungen und die Automatisierung von Abläufen. Einzelstücke und Kleinserien, konstruiert von einem Maschinenbauingenieur und gebaut im eigenen Betrieb in {{address.home}}. Verbindliche Offerte vor Baubeginn; nicht zufrieden, übernehmen wir 50 %.',
  glance: {
    forWhom: 'Bauunternehmen und Spezialtiefbau mit eigener Geräteflotte, Vermieter und Händler von Baugeräten – und alle Betriebe mit Kranen oder Fahrzeugen, deren Aufgabe kein Hersteller löst.',
    what: 'Machbarkeit prüfen, konstruieren, im eigenen Betrieb bauen und bei Ihnen in Betrieb nehmen.',
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
      a: 'Nach der Machbarkeitsprüfung erhalten Sie eine verbindliche Offerte – bevor wir bauen.',
    },
    promiseFaq.garantie,
    {
      q: 'Bleibt die Lösung bei Ihnen in Betreuung?',
      a: 'Ja. Wartung, Reparatur und Ersatzteile kommen aus demselben Betrieb, der sie gebaut hat.',
    },
  ],
  related: [
    { href: '/krantechnik/krane-nach-mass', label: 'Krane nach Mass', text: 'Sonderkrane und Industriekrane.' },
    { href: '/fahrzeugtechnik/trommeltausch', label: 'Trommeltausch', text: 'Neue Trommel statt neuer Fahrmischer.' },
  ],
  service: { name: 'Speziallösungen', serviceType: 'Spezialmaschinenbau für Krane, Fahrzeuge und Baumaschinen' },
  keywords: ['Spezialmaschinenbau', 'Sondermaschine Baustelle', 'Anbaugerät Baumaschine', 'Sonderkran', 'Sonderaufbau', 'Vorrichtungsbau'],
};

/** Das Prinzip: warum es Speziallösungen braucht – und was Sie davon haben. */
export const specialPrinciple = {
  title: 'Serienmaschinen sind für den Durchschnitt gebaut. Ihre Aufgabe ist es nicht.',
  lead: 'Was dazwischen fehlt, erledigt heute meist ein Mensch – mit Zeit, Umwegen und Improvisation. Wir bauen die Maschine, die diese Lücke schliesst.',
  /** Bild: eine Reihe gleicher Serienmaschinen als Zeichnung, eine tritt heraus – mit rotem Anbau. */
  alt: 'Eine Reihe gleicher Minibagger als Zeichnung; einer tritt heraus, echt, mit rotem Sondergreifer',
  gains: [
    { icon: 'hand' as const, title: 'Weniger Handarbeit', text: 'Was heute von Hand geschieht, erledigt danach die Maschine – schneller und jedes Mal gleich.' },
    { icon: 'shield-check' as const, title: 'Mehr Sicherheit', text: 'Wer nicht mehr improvisieren muss, steht nicht mehr unter der Last.' },
    { icon: 'trending-up' as const, title: 'Ihr Vorsprung', text: 'Sie nehmen Aufträge an, die andere ablehnen müssen.' },
  ],
};

/** Drei Felder, ein Prinzip – je mit Zeichnung (src/assets/illustrations/spezial-*.svg). */
export const specialFields = {
  title: 'Drei Felder, ein Prinzip',
  lead: 'Wir nehmen, was die Serie kann, und bauen dazu, was Ihre Aufgabe braucht.',
  items: [
    {
      id: 'baumaschinen',
      illo: 'spezial-baumaschinen',
      alt: 'Zeichnung: Speziallösung für Baumaschinen',
      title: 'Für Baumaschinen',
      text: 'Rüttler, Klemmen, Greifer: Ihr Gerät kann mehr, als der Hersteller vorsieht.',
    },
    {
      id: 'fahrzeuge',
      illo: 'spezial-fahrzeuge',
      alt: 'Zeichnung: Speziallösung für Fahrzeuge',
      title: 'Für Fahrzeuge',
      text: 'Sonderaufbauten und Anbauten: Das Fahrgestell ist Serie, die Aufgabe nicht.',
      href: '/fahrzeugtechnik',
    },
    {
      id: 'krane',
      illo: 'spezial-krane',
      alt: 'Zeichnung: Speziallösung für Krane',
      title: 'Für Krane',
      text: 'Sonderkrane und Lastaufnahmen: Wo der Katalogkran aufhört, fangen wir an.',
      href: '/krantechnik/krane-nach-mass#situationen',
    },
  ],
};

/** Der Weg vom Problem zur Lösung – wer was tut, ohne Offerte und ohne Zahlen. */
export const specialSteps = {
  title: 'Vom Problem zur Lösung',
  start: 'Ihr Problem',
  end: 'Ihre Lösung',
  items: [
    { icon: 'pen-line' as const, who: 'Sie', title: 'Aufgabe', text: 'Sie zeigen uns, wo es klemmt.', tags: ['Skizze', 'Foto', 'Video'] },
    { icon: 'search' as const, who: 'Gemeinsam', title: 'Lösungsweg', text: 'Wir schauen uns den Einsatz an und zeigen Ihnen, wie die Lösung aussieht.', check: 'Klar, bevor gebaut wird' },
    { icon: 'drafting-compass' as const, who: 'Wir', title: 'Konstruktion', text: 'Wir konstruieren und rechnen die Lösung durch – bis sie hält, was sie soll.', check: 'Abgestimmt mit Ihnen' },
    { icon: 'wrench' as const, who: 'Wir', title: 'Bau', text: 'Wir bauen Ihre Lösung – Stahlbau, Hydraulik und Steuerung aus einer Hand.', tags: ['Stahlbau', 'Hydraulik', 'Steuerung'] },
    { icon: 'flag' as const, who: 'Bei Ihnen', title: 'Inbetriebnahme', text: 'Wir nehmen die Lösung bei Ihnen in Betrieb und weisen Ihr Team ein.', tags: ['Einweisung', 'Unterlagen'] },
  ],
};

/** Modul: Wer dahintersteht – sachlich, kurz, ohne fremde Logos. */
export const specialBackground = {
  eyebrow: 'Wer dahintersteht',
  title: 'Entwicklung, Fertigung & Montage unter einem Dach',
  text: `${site.people.owner.name} ist Maschinenbauingenieur und hat jahrelang Baumaschinen entwickelt – von der Hydraulik bis zu vernetzten Steuerungen und IoT-Anwendungen. Er kennt die Wünsche, die Hersteller nicht erfüllen – und weiss, wie man eine Lösung baut, die auf der Baustelle hält.`,
  facts: [
    'Langjährige Entwicklung von Baumaschinen',
    'Krane bauen wir seit {{history.cranesSince}} selbst',
    'Konstruktion, Stahlbau und Montage aus einer Hand',
  ],
};
