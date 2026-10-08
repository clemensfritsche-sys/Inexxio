/**
 * Sonderlösungen – EINE Seite, eigener Hauptmenüpunkt, und zugleich der zweite Punkt in den
 * Untermenüs von Krane und Fahrzeugbau (Testnotizen #1204/#1205/#1206). Darum ist sie nach
 * DEREN Fragen gegliedert: drei Felder mit eigenem Anker – #krane, #fahrzeugbau, #stahlbau –,
 * und jeder Verweis landet bei dem Feld, das ihn betrifft.
 * Ton: «Es gibt kein Produkt von der Stange für Ihr Problem? Wir konstruieren und bauen die
 * Lösung.» Grossprojekte nicht aktiv bewerben – die Werkstatt ist klein.
 */
import { site } from '../config/site.mjs';
import type { Step, SubPage } from './types';
import { promiseFaq } from './promises';

export const sonderloesungen: SubPage = {
  area: 'sonderloesungen',
  path: '/sonderloesungen',
  crumb: 'Sonderlösungen',
  title: 'Sonderlösungen nach Mass',
  description:
    'Sonderkrane, Sonderaufbauten, Konstruktion und Stahlbau: Lösungen, die es nicht von der Stange gibt – geplant und gebaut in Tuttwil-Wängi TG. Anfragen.',
  hero: {
    eyebrow: 'Sonderlösungen',
    h1: 'Konstruiert und gebaut, wo es nichts zu ==kaufen== gibt',
    lead:
      'Ein Kran, der in kein Gebäude passt? Ein Aufbau, den kein Hersteller anbietet? Ein Teil, das es nicht mehr gibt? Wir konstruieren und bauen die Lösung – mit Ingenieurwissen aus dem Baumaschinenbau, eigener Werkstatt und Fixpreis.',
    photo: 'arbeit-werkstatt',
    primary: { label: 'Anliegen schildern', href: '#anfrage' },
  },
  summary:
    '{{brand.full}} konstruiert und baut Sonderlösungen in drei Feldern: Krane, die es nicht zu kaufen gibt (an das Gebäude angepasst, Ausleger und Hebezeuge nach Mass, Umbau bestehender Anlagen), Sonderaufbauten und die Reparatur von Aufbauten, Mulden, Kippern und Hydraulik, sowie Konstruktion, Stahlbau und Schweissarbeiten – vom Einzelstück bis zur Kleinserie. Gefertigt in der Werkstatt in Tuttwil-Wängi TG.',
  glance: {
    forWhom: 'Betriebe in Industrie, Bau, Transport und Landwirtschaft mit einer Aufgabe, für die es kein fertiges Produkt gibt.',
    what: 'Konzept, Konstruktion und Berechnung, Fertigung in Stahl, Montage – und auf Wunsch der Service danach.',
    deliverables: 'Die fertige Lösung mit Zeichnungen und Unterlagen – oder nur die Konstruktion, wenn Sie selbst fertigen.',
  },
  promises: ['garantie'],
  scope: {
    title: 'Was jede Sonderlösung mitbringt',
    lead: 'Gleich, ob Kran, Aufbau oder Stahlkonstruktion.',
    items: [
      { title: 'Konstruktion und Berechnung', text: 'Zeichnungen und 3D-Modelle, Festigkeit und Tragfähigkeit – nachvollziehbar dokumentiert.' },
      { title: 'Fertigung in der eigenen Werkstatt', text: 'In Tuttwil – oder mit Partnern aus der Region, wo es die Aufgabe verlangt.' },
      { title: 'Nach Muster', text: 'Ein altes Teil, eine Skizze oder ein Foto genügt – wir messen auf und fertigen nach.' },
      { title: 'Montage vor Ort', text: 'Wir bauen ein, nehmen in Betrieb und zeigen Ihnen die Bedienung.' },
      { title: 'Dokumentation', text: 'Zeichnungen und Unterlagen zu jeder Lösung – wichtig bei jedem Umbau.' },
      { title: 'Service danach', text: 'Wer es gebaut hat, kennt es – Wartung und Reparatur aus derselben Hand.' },
    ],
  },
  faq: [
    {
      q: 'Welche Aufträge passen zu Ihnen?',
      a: 'Einzelanfertigungen, Umbauten und Kleinserien – vom Anbauteil über den Sonderaufbau bis zum Kran nach Mass. Für grosse Serien und Grossprojekte ist unsere Werkstatt zu klein; das sagen wir offen.',
    },
    {
      q: 'Brauche ich eine fertige Zeichnung?',
      a: 'Nein. Eine Skizze, ein Foto oder ein altes Teil als Muster genügt. Die Zeichnung erstellen wir.',
    },
    {
      q: 'Konstruieren Sie auch, ohne dass Sie fertigen?',
      a: 'Ja. Sie können die Zeichnungen auch selbst oder anderswo fertigen lassen.',
    },
    {
      q: 'Reparieren Sie auch bestehende Aufbauten?',
      a: 'Ja – Mulden, Kipper, Hydraulik und Aufbauten von Baustellenfahrzeugen. Was sich nicht mehr reparieren lässt, fertigen wir neu.',
    },
    {
      q: 'Was kostet eine Sonderlösung?',
      a: 'Nach der Abklärung erhalten Sie einen Fixpreis – vor jeder Arbeit.',
    },
    promiseFaq.garantie,
    {
      q: 'Was ist bei einem Umbau einer Maschine zu beachten?',
      a: 'Wer eine Maschine wesentlich verändert, braucht saubere Unterlagen – ab 2027 gilt in der EU dazu die neue Maschinenverordnung. Wir dokumentieren jeden Umbau.',
    },
    {
      q: 'Sind Sie Vertragswerkstatt einer Marke?',
      a: 'Nein. Wir sind unabhängig.',
    },
  ],
  related: [
    { href: '/krane/krananlagen', label: 'Krananlagen', text: 'Wenn ein Kran nach Mass genügt.' },
    { href: '/fahrzeugbau/fahrmischer', label: 'Fahrmischer', text: 'Trommeltausch, Revision und Verschleissteile.' },
    { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Was Prüfpflicht und Dokumentation verlangen.', kind: 'ratgeber' },
  ],
  service: { name: 'Sonderlösungen', serviceType: 'Sonderkrane, Sonderaufbauten, Konstruktion und Stahlbau' },
  keywords: ['Sonderkran', 'Sonderaufbau', 'Sondermaschinenbau Thurgau', 'Stahlbau', 'Schweissarbeiten', 'Aufbau Reparatur'],
};

/**
 * Die drei Felder – die Anker sind die Adressen, auf die die Untermenüs von Krane und
 * Fahrzeugbau zeigen (site.mjs, `special`). Ein Feld umbenennen heisst, seinen Anker dort mitzuziehen;
 * die Prüfung der Links (check-site) meldet einen verwaisten.
 */
export const sonderFields = [
  {
    id: 'krane',
    eyebrow: 'Krane',
    title: 'Krane, die es nicht zu kaufen gibt',
    text: 'Kein Katalogkran passt in Ihre Halle, an Ihren Steg oder zu Ihrer Last? Wir konstruieren und bauen ihn – und wissen seit {{history.cranesSince}}, worauf es ankommt.',
    photo: 'reparatur-vor-ort',
    items: ['An das Gebäude angepasst: Fahrbahn, Stützen, Spannweite', 'Ausleger und Hebezeuge nach Mass', 'Umbau und Erweiterung bestehender Anlagen', 'Kranbahnen und Tragwerke'],
    link: { href: '/krane/krananlagen', label: 'Zu den Krananlagen' },
  },
  {
    id: 'fahrzeugbau',
    eyebrow: 'Fahrzeugbau',
    title: 'Sonderaufbauten – und Reparatur dessen, was auf Ihrem Fahrzeug ist',
    text: 'Aufbauten, die kein Hersteller anbietet, bauen wir nach Mass. Und wir setzen instand, was der Alltag auf der Baustelle zerlegt.',
    photo: 'aufbau-reparatur',
    items: ['Sonderaufbauten nach Mass', 'Mulden, Kipper, Bordwände und Verschlüsse', 'Hydraulik: Zylinder, Pumpen, Ventile, Leitungen', 'Baumaschinen umbauen und nachrüsten'],
    link: { href: '/fahrzeugbau/fahrmischer', label: 'Zu den Fahrmischern' },
  },
  {
    id: 'stahlbau',
    eyebrow: 'Stahlbau',
    title: 'Konstruktion und Stahlbau',
    text: 'Vom einzelnen Teil bis zur Stahlkonstruktion für die Halle – nach Zeichnung oder nach Muster.',
    photo: 'arbeit-werkstatt',
    items: ['Stahlkonstruktionen: Gestelle, Bühnen, Halterungen', 'Schweissarbeiten an Maschinen und Konstruktionen', 'Einzelstücke und Kleinserien', 'Nur die Konstruktion, wenn Sie selbst fertigen'],
  },
];

/** Modul: Ablauf. */
export const sonderSteps = {
  title: 'Von der Skizze zur Lösung',
  lead: 'Eine Skizze, ein Foto oder ein Muster genügt für den Anfang – auch als PDF.',
  items: [
    { title: 'Anliegen', text: 'Sie schildern das Problem – mit Skizze, Foto oder Muster.' },
    { title: 'Machbarkeit und Richtofferte', text: 'Wir prüfen, ob und wie es geht, und nennen den Rahmen.' },
    { title: 'Konstruktion', text: 'Wir konstruieren und rechnen; Sie geben die Lösung frei.' },
    { title: 'Fertigung', text: 'In unserer Werkstatt oder mit Partnern aus der Region.' },
    { title: 'Übergabe mit Dokumentation', text: 'Sie erhalten die Lösung mit Zeichnungen und Unterlagen.' },
  ] satisfies Step[],
};

/** Modul: Hintergrund (Baumaschinen-Entwicklung). */
export const sonderBackground = {
  title: 'Wir wissen, wie eine Maschine gebaut ist',
  text: `${site.people.owner.name} hat als Maschinenbauingenieur bei Liebherr Baumaschinen entwickelt. Wer eine Maschine von innen kennt, baut sie so um, dass sie danach weiter zuverlässig arbeitet – und dokumentiert, was er verändert hat.`,
};
