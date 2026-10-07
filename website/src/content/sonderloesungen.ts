/**
 * Sonderlösungen – EINE Seite (Rückmeldung 07.10.2026: zu viele Seiten). Konstruktion,
 * Schweiss- und Stahlbau und Baumaschinen waren drei dünne Unterseiten mit denselben Fragen;
 * jetzt sind sie der Leistungsumfang dieser einen Seite.
 * Ton: «Sie haben ein Problem, für das es kein Produkt von der Stange gibt? Wir konstruieren
 * und bauen die Lösung.» Grossprojekte nicht aktiv bewerben – die Werkstatt ist klein.
 */
import { site } from '../config/site.mjs';
import type { Step, SubPage } from './types';
import { promiseFaq } from './promises';

export const sonderloesungen: SubPage = {
  area: 'sonderloesungen',
  path: '/sonderloesungen',
  crumb: 'Sonderlösungen',
  title: 'Sonderlösungen und Stahlbau',
  description:
    'Konstruktion, Schweiss- und Stahlbau, Umbau und Reparatur von Baumaschinen: Lösungen, die es nicht von der Stange gibt – aus Tuttwil-Wängi TG. Anfragen.',
  hero: {
    eyebrow: 'Sonderlösungen',
    h1: 'Sonderlösungen: konstruiert und gebaut, wo es nichts zu ==kaufen== gibt',
    lead:
      'Es gibt kein Produkt von der Stange für Ihr Problem? Wir konstruieren und bauen die Lösung – mit Ingenieurwissen aus dem Baumaschinenbau, eigener Werkstatt und Fixpreis.',
    photo: 'arbeit-werkstatt',
    primary: { label: 'Anliegen schildern', href: '#anfrage' },
  },
  summary:
    '{{brand.full}} entwickelt und baut Sonderlösungen: Konstruktion und Berechnung, Stahlkonstruktionen und Schweissarbeiten, Einzelstücke und Kleinserien, Umbauten, Nachrüstungen und Reparaturen an Baumaschinen. Für Bau-, Industrie- und Landwirtschaftsbetriebe, die eine Einzelanfertigung oder einen Umbau brauchen. Gefertigt in der Werkstatt in Tuttwil-Wängi TG oder mit Partnern aus der Region.',
  glance: {
    forWhom: 'Bau-, Industrie- und Landwirtschaftsbetriebe mit einem Problem, für das es kein fertiges Produkt gibt.',
    what: 'Konzept, Konstruktion und Berechnung, Fertigung in Stahl, Umbau und Reparatur von Baumaschinen – mit Dokumentation.',
    deliverables: 'Die fertige Lösung mit Zeichnungen und Unterlagen – oder nur die Konstruktion, wenn Sie selbst fertigen.',
  },
  promises: ['garantie'],
  scope: {
    title: 'Was wir konstruieren und bauen',
    lead: 'Vom einzelnen Teil bis zur Stahlkonstruktion für die Halle.',
    items: [
      { title: 'Konstruktion und Berechnung', text: 'Zeichnungen und 3D-Modelle, Festigkeit und Tragfähigkeit – nachvollziehbar dokumentiert.' },
      { title: 'Stahlkonstruktionen', text: 'Gestelle, Bühnen, Halterungen und Tragwerke – passend zum Einsatzort.' },
      { title: 'Schweissarbeiten', text: 'Neuteile und Reparaturschweissen an Maschinen, Aufbauten und Konstruktionen.' },
      { title: 'Einzelstücke und Kleinserien', text: 'Nach Zeichnung oder nach Muster: Ein altes Teil genügt – wir messen auf und fertigen nach.' },
      { title: 'Baumaschinen umbauen', text: 'Umbauten, Nachrüstungen und Anbauteile, die es so nicht zu kaufen gibt.' },
      { title: 'Baumaschinen reparieren', text: 'Stahlbau, Hydraulik und Mechanik instand stellen.' },
    ],
  },
  faq: [
    {
      q: 'Welche Aufträge passen zu Ihnen?',
      a: 'Einzelanfertigungen, Umbauten und Kleinserien – vom Anbauteil bis zur Stahlkonstruktion für die Halle. Für grosse Serien und Grossprojekte ist unsere Werkstatt zu klein; das sagen wir offen.',
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
      q: 'Was kostet eine Sonderlösung?',
      a: 'Nach der Abklärung erhalten Sie einen Fixpreis – vor jeder Arbeit.',
    },
    promiseFaq.garantie,
    promiseFaq.secondOpinion,
    {
      q: 'Was ist bei einem Umbau einer Baumaschine zu beachten?',
      a: 'Wer eine Maschine wesentlich verändert, braucht saubere Unterlagen – ab 2027 gilt in der EU dazu die neue Maschinenverordnung. Wir dokumentieren jeden Umbau.',
    },
    {
      q: 'Sind Sie Vertragswerkstatt einer Marke?',
      a: 'Nein. Wir sind unabhängig.',
    },
  ],
  related: [
    { href: '/krantechnik/modernisierung', label: 'Kran modernisieren', text: 'Umbauten an bestehenden Kranen – mit Dokumentation.' },
    { href: '/fahrzeugtechnik/aufbauten-reparatur', label: 'Aufbauten reparieren', text: 'Mulden, Kipper und Hydraulik.' },
    { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Was Prüfpflicht und Dokumentation verlangen.', kind: 'ratgeber' },
  ],
  service: { name: 'Sonderlösungen', serviceType: 'Konstruktion, Stahlbau und Umbau von Baumaschinen' },
  keywords: ['Sondermaschinenbau Thurgau', 'Stahlbau', 'Schweissarbeiten', 'Baumaschinen Umbau', 'Konstruktion'],
};

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

// Sonderlösungen hat keine Unterseiten: die Navigation nennt keine.
if (site.areas.find((a) => a.id === 'sonderloesungen')!.children.length) throw new Error('Sonderlösungen: die Navigation nennt Unterseiten, die es nicht gibt.');
