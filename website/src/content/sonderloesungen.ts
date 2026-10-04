/**
 * Sonderlösungen – Bereichsseite und drei Unterseiten (Auftrag Kap. 3.3 C, 7.4, 7.5).
 * Maschinenbau im weiteren Sinn, Richtung Baumaschinen. Ton: «Sie haben ein Problem, für das
 * es kein Produkt von der Stange gibt? Wir konstruieren und bauen die Lösung.»
 * Grossprojekte nicht aktiv bewerben – die Werkstatt ist klein.
 */
import { site } from '../config/site.mjs';
import type { AreaPage, Step, SubPage } from './types';

const anfrage = (label: string) => ({ label, href: '#anfrage' });
const ratgeberModern = { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Was Prüfpflicht und Dokumentation verlangen.', kind: 'ratgeber' as const };

/* ------------------------------------------------------------------ Bereich */
export const sonderloesungen: AreaPage = {
  id: 'sonderloesungen',
  path: '/sonderloesungen',
  title: 'Sonderlösungen und Stahlbau',
  description:
    'Konstruktion, Schweiss- und Stahlbau, Umbau und Reparatur von Baumaschinen: Lösungen, die es nicht von der Stange gibt – aus Tuttwil-Wängi TG. Anfragen.',
  hero: {
    eyebrow: 'Sonderlösungen',
    h1: 'Sonderlösungen: konstruiert und gebaut, wo es nichts zu ==kaufen== gibt',
    lead:
      'Sie haben ein Problem, für das es kein Produkt von der Stange gibt? Wir konstruieren und bauen die Lösung – mit Ingenieurwissen aus dem Baumaschinenbau und einer eigenen Werkstatt.',
    photo: 'arbeit-werkstatt',
    primary: anfrage('Anliegen schildern'),
  },
  summary:
    '{{brand.full}} entwickelt und baut Sonderlösungen: Konstruktion und Berechnung, Schweiss- und Stahlbau, Umbauten und Reparaturen an Baumaschinen. Für Bau- und Industriebetriebe, die eine Einzelanfertigung oder einen Umbau brauchen. Geführt von {{people.owner.name}}, Maschinenbauingenieur mit Erfahrung in der Baumaschinen-Entwicklung.',
  levels: [
    {
      title: 'Lösungen',
      text: 'Von der Idee bis zum fertigen Teil: Konzept, Konstruktion, Berechnung, Fertigung und Dokumentation.',
      links: [
        { href: '/sonderloesungen/konstruktion-engineering', label: 'Konstruktion & Engineering' },
        { href: '/sonderloesungen/schweiss-stahlbau', label: 'Schweiss- & Stahlbau' },
      ],
    },
    {
      title: 'Service & Reparatur',
      text: 'Umbauten, Nachrüstungen und Reparaturen an Baumaschinen und Stahlkonstruktionen.',
      links: [
        { href: '/sonderloesungen/baumaschinen', label: 'Baumaschinen: Umbau & Reparatur' },
        { href: '/service/notfall', label: 'Notfall-Service' },
      ],
    },
    {
      title: 'Ersatz- und Verschleissteile',
      text: 'Gibt es ein Teil nicht mehr zu kaufen, fertigen wir es nach Muster oder Zeichnung. [[PRÜFEN: Nachfertigung von Teilen]]',
      links: [
        { href: '/sonderloesungen/schweiss-stahlbau#leistungen', label: 'Einzelstücke und Kleinserien' },
        { href: '/kontakt?thema=teil', label: 'Teil anfragen' },
      ],
    },
  ],
  steps: [
    { title: 'Anfrage', text: 'Sie schildern das Problem – eine Skizze, ein Foto oder ein Muster genügt.' },
    { title: 'Abklärung', text: 'Wir prüfen die Machbarkeit und nennen eine Richtofferte.' },
    { title: 'Umsetzung', text: 'Wir konstruieren, fertigen und bauen ein – in der eigenen Werkstatt oder mit Partnern aus der Region. [[PRÜFEN: Fertigung mit Partnern]]' },
    { title: 'Bericht', text: 'Sie erhalten die Lösung mit Zeichnung und Dokumentation.' },
  ],
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
      q: 'Rechnen Sie auch nach?',
      a: 'Ja. Zur Konstruktion gehören Berechnung und Dokumentation. [[PRÜFEN: Umfang der Berechnungen und Nachweise]]',
    },
    {
      q: 'Welche Materialien verarbeiten Sie?',
      a: '[[PRÜFEN: Materialien – Stahl, Inox, Alu?]]',
    },
  ],
  cta: {},
  service: { name: 'Sonderlösungen', serviceType: 'Konstruktion, Stahlbau und Umbau von Baumaschinen' },
  keywords: ['Sondermaschinenbau Thurgau', 'Stahlbau', 'Schweissarbeiten', 'Baumaschinen Umbau'],
};

/* ------------------------------------------------------------------ Konstruktion & Engineering */
export const konstruktion: SubPage = {
  area: 'sonderloesungen',
  path: '/sonderloesungen/konstruktion-engineering',
  crumb: 'Konstruktion & Engineering',
  title: 'Konstruktion und Engineering',
  description:
    'Konstruktion und Engineering für Sonderlösungen: Konzept, Konstruktion, Berechnung und Dokumentation – gefertigt in der eigenen Werkstatt in Tuttwil TG.',
  hero: {
    eyebrow: 'Sonderlösungen · Konstruktion & Engineering',
    h1: 'Konstruktion und Engineering: von der Idee bis zur Zeichnung',
    lead:
      'Konzept, Konstruktion, Berechnung und Dokumentation für Lösungen, die es nicht zu kaufen gibt – und auf Wunsch gleich gefertigt, in der eigenen Werkstatt.',
    photo: 'konstruktion',
    primary: anfrage('Anliegen schildern'),
  },
  summary:
    '{{brand.full}} entwickelt und konstruiert Sonderlösungen: Konzept, Konstruktion, Berechnung und Dokumentation, gefertigt in der eigenen Werkstatt in Tuttwil-Wängi TG oder mit Partnern aus der Region. {{people.owner.name}} ist Maschinenbauingenieur und hat bei Liebherr Baumaschinen entwickelt. [[PRÜFEN: Fertigung mit Partnern aus der Region]]',
  glance: {
    forWhom: 'Bau- und Industriebetriebe mit einem Problem, für das es kein fertiges Produkt gibt.',
    what: 'Konzept, Konstruktion, Berechnung, Dokumentation – und auf Wunsch die Fertigung.',
    deliverables: 'Zeichnungen und Dokumentation zur Lösung – und das fertige Teil, wenn wir es bauen.',
  },
  scope: {
    title: 'Was dazugehört',
    lead: '[[PRÜFEN: Leistungsumfang Konstruktion und Engineering]]',
    items: [
      { title: 'Konzept', text: 'Wir verstehen das Problem, bevor wir zeichnen – vor Ort, am Teil, im Gespräch.' },
      { title: 'Konstruktion', text: 'Zeichnungen und 3D-Modelle für Einzelteile, Baugruppen und Umbauten. [[PRÜFEN: eingesetzte Werkzeuge]]' },
      { title: 'Berechnung', text: 'Festigkeit, Tragfähigkeit und Auslegung – nachvollziehbar dokumentiert.' },
      { title: 'Dokumentation', text: 'Unterlagen, die auch in zehn Jahren noch sagen, was gebaut wurde und warum.' },
      { title: 'Fertigung', text: 'In unserer Werkstatt oder mit Partnern aus der Region.' },
    ],
  },
  faq: [
    {
      q: 'Brauche ich eine fertige Zeichnung?',
      a: 'Nein. Eine Skizze, ein Foto oder ein altes Teil als Muster genügt.',
    },
    {
      q: 'Konstruieren Sie auch, ohne dass Sie fertigen?',
      a: 'Ja. Sie können die Zeichnungen auch selbst oder anderswo fertigen lassen. [[PRÜFEN: Konstruktion als eigene Leistung]]',
    },
    {
      q: 'Was kostet eine Konstruktion?',
      a: 'Nach der Abklärung erhalten Sie eine Richtofferte – vor jeder weiteren Arbeit.',
    },
    {
      q: 'Wem gehören die Zeichnungen?',
      a: '[[PRÜFEN: rechtlich – Rechte an Zeichnungen und Konstruktionen]]',
    },
  ],
  cta: { need: 'konstruktion' },
  related: [
    { href: '/sonderloesungen/schweiss-stahlbau', label: 'Schweiss- und Stahlbau', text: 'Die Fertigung in der eigenen Werkstatt.' },
    { href: '/krantechnik/modernisierung', label: 'Kran modernisieren', text: 'Umbauten an bestehenden Kranen – mit Dokumentation.' },
    ratgeberModern,
  ],
  service: { name: 'Konstruktion und Engineering', serviceType: 'Konstruktion und Berechnung von Sonderlösungen' },
  keywords: ['Sondermaschinenbau Thurgau', 'Konstruktion', 'Engineering'],
};

/** Modul: Ablauf (Auftrag 7.5). */
export const konstruktionSteps = {
  title: 'Ablauf',
  items: [
    { title: 'Anliegen', text: 'Sie schildern das Problem – mit Skizze, Foto oder Muster.' },
    { title: 'Machbarkeit und Richtofferte', text: 'Wir prüfen, ob und wie es geht, und nennen den Rahmen.' },
    { title: 'Konstruktion', text: 'Wir konstruieren und rechnen; Sie geben die Lösung frei.' },
    { title: 'Fertigung', text: 'In unserer Werkstatt oder mit Partnern aus der Region.' },
    { title: 'Übergabe mit Dokumentation', text: 'Sie erhalten die Lösung mit Zeichnungen und Unterlagen.' },
  ] satisfies Step[],
};

/* ------------------------------------------------------------------ Schweiss- & Stahlbau */
export const stahlbau: SubPage = {
  area: 'sonderloesungen',
  path: '/sonderloesungen/schweiss-stahlbau',
  crumb: 'Schweiss- & Stahlbau',
  title: 'Schweiss- und Stahlbau',
  description:
    'Schweissarbeiten und Stahlbau in Tuttwil-Wängi TG: Stahlkonstruktionen, Einzelstücke und Kleinserien, Reparaturschweissen – nach Zeichnung oder Muster.',
  hero: {
    eyebrow: 'Sonderlösungen · Schweiss- & Stahlbau',
    h1: 'Schweiss- und Stahlbau: Einzelstücke und Kleinserien',
    lead:
      'Stahlkonstruktionen, Schweissarbeiten und Einzelanfertigungen aus der eigenen Werkstatt – nach Ihrer Zeichnung, nach Muster oder von uns konstruiert.',
    photo: 'arbeit-werkstatt',
    primary: anfrage('Anfrage stellen'),
  },
  summary:
    '{{brand.full}} fertigt Stahlkonstruktionen, Schweissarbeiten, Einzelstücke und Kleinserien in der Werkstatt in Tuttwil-Wängi TG – nach Zeichnung, nach Muster oder mit eigener Konstruktion. [[PRÜFEN: Materialien – Stahl, Inox, Alu?]]',
  glance: {
    forWhom: 'Gewerbe-, Bau- und Landwirtschaftsbetriebe, die ein Stahlteil oder eine Konstruktion brauchen.',
    what: 'Stahlkonstruktionen, Schweissarbeiten, Einzelstücke, Kleinserien, Reparaturschweissen.',
    deliverables: 'Das fertige Teil – auf Wunsch montiert und mit Unterlagen.',
  },
  scope: {
    title: 'Was wir fertigen',
    lead: '[[PRÜFEN: Leistungsumfang, Materialien und Verfahren]]',
    items: [
      { title: 'Stahlkonstruktionen', text: 'Gestelle, Bühnen, Halterungen und Tragwerke – passend zum Einsatzort.' },
      { title: 'Schweissarbeiten', text: 'Neuteile und Reparaturschweissen an Maschinen, Aufbauten und Konstruktionen.' },
      { title: 'Einzelstücke und Kleinserien', text: 'Vom einzelnen Ersatzteil bis zur kleinen Serie.' },
      { title: 'Nach Muster', text: 'Ein altes Teil genügt als Vorlage – wir messen auf und fertigen nach.' },
    ],
  },
  faq: [
    {
      q: 'Welche Materialien verarbeiten Sie?',
      a: '[[PRÜFEN: Materialien – Stahl, Inox, Alu?]]',
    },
    {
      q: 'Machen Sie auch grössere Stahlbauprojekte?',
      a: 'Unsere Werkstatt ist auf Einzelstücke, Umbauten und Kleinserien eingerichtet. Für grosse Projekte sagen wir offen, wenn ein anderer Betrieb besser passt.',
    },
    {
      q: 'Montieren Sie auch vor Ort?',
      a: '[[PRÜFEN: Montage vor Ort – ja oder nein, in welchem Umfang]]',
    },
    {
      q: 'Wie schnell geht eine Reparatur?',
      a: 'Das hängt von Teil und Auslastung ab. Steht eine Maschine still, rufen Sie an: {{phone.link}}.',
    },
  ],
  cta: { need: 'stahlbau' },
  related: [
    { href: '/sonderloesungen/konstruktion-engineering', label: 'Konstruktion und Engineering', text: 'Wenn es noch keine Zeichnung gibt.' },
    { href: '/fahrzeugtechnik/aufbauten-reparatur', label: 'Aufbauten reparieren', text: 'Mulden, Kipper und Hydraulik.' },
    { href: '/ratgeber/verschleissteile-fahrmischer', label: 'Verschleissteile am Fahrmischer', text: 'Wann ein Teil ersetzt werden muss.', kind: 'ratgeber' },
  ],
  service: { name: 'Schweiss- und Stahlbau', serviceType: 'Stahlbau und Schweissarbeiten' },
  keywords: ['Stahlbau', 'Schweissarbeiten'],
};

/* ------------------------------------------------------------------ Baumaschinen */
export const baumaschinen: SubPage = {
  area: 'sonderloesungen',
  path: '/sonderloesungen/baumaschinen',
  crumb: 'Baumaschinen',
  title: 'Baumaschinen-Umbau, Reparatur',
  description:
    'Umbauten, Nachrüstungen, Anbauteile und Reparaturen an Baumaschinen – mit Ingenieurwissen aus der Baumaschinen-Entwicklung. Aus Tuttwil-Wängi TG. Anfragen.',
  hero: {
    eyebrow: 'Sonderlösungen · Baumaschinen',
    h1: 'Baumaschinen: Umbau, Nachrüstung und Reparatur',
    lead:
      'Umbauten, Nachrüstungen, Anbauteile und Reparaturen an Baumaschinen. Wir verstehen, wie eine Maschine gebaut ist – {{people.owner.name}} hat bei Liebherr Baumaschinen entwickelt.',
    photo: 'baumaschine',
    primary: anfrage('Anfrage stellen'),
  },
  summary:
    '{{brand.full}} baut Baumaschinen um, rüstet sie nach, fertigt Anbauteile und repariert sie – in Tuttwil-Wängi TG. {{people.owner.name}} hat als Maschinenbauingenieur bei Liebherr Baumaschinen entwickelt. [[PRÜFEN: Umfang Baumaschinen – welche Maschinen, welche Arbeiten]]',
  glance: {
    forWhom: 'Bauunternehmen und Betriebe mit eigenen Baumaschinen.',
    what: 'Umbauten, Nachrüstungen, Anbauteile und Reparaturen. [[PRÜFEN: Umfang]]',
    deliverables: 'Die umgebaute oder reparierte Maschine mit Unterlagen zum Umbau.',
  },
  scope: {
    title: 'Was wir an Baumaschinen machen',
    lead: '[[PRÜFEN: Umfang – welche Maschinen, welche Arbeiten]]',
    items: [
      { title: 'Umbauten', text: 'Maschinen an eine neue Aufgabe anpassen – geplant, gerechnet und dokumentiert.' },
      { title: 'Nachrüstungen', text: 'Zusätzliche Funktionen, Schutzeinrichtungen oder Hydraulikkreise nachrüsten.' },
      { title: 'Anbauteile', text: 'Halterungen, Adapter und Werkzeuge, die es so nicht zu kaufen gibt.' },
      { title: 'Reparaturen', text: 'Stahlbau, Hydraulik und Mechanik instand stellen.' },
    ],
  },
  faq: [
    {
      q: 'An welchen Baumaschinen arbeiten Sie?',
      a: '[[PRÜFEN: Maschinenarten und Marken – nur nennen, was wir wirklich machen]]',
    },
    {
      q: 'Was ist bei einem Umbau zu beachten?',
      a: 'Wer eine Maschine wesentlich verändert, braucht saubere Unterlagen – ab 2027 gilt in der EU dazu die neue Maschinenverordnung. Wir dokumentieren jeden Umbau. [[PRÜFEN: fachlich – Übernahme durch die Schweiz und Folgen für Umbauten]]',
    },
    {
      q: 'Sind Sie Vertragswerkstatt einer Marke?',
      a: 'Nein. Wir sind unabhängig. [[PRÜFEN: bestehende Partnerschaften]]',
    },
    {
      q: 'Kommen Sie auf die Baustelle?',
      a: '[[PLATZHALTER: Einsätze vor Ort bei Baumaschinen – ja oder nein, in welchem Umfang]]',
    },
  ],
  cta: { need: 'baumaschine' },
  related: [
    { href: '/sonderloesungen/konstruktion-engineering', label: 'Konstruktion und Engineering', text: 'Berechnung und Dokumentation für den Umbau.' },
    { href: '/fahrzeugtechnik/aufbauten-reparatur', label: 'Aufbauten reparieren', text: 'Mulden, Kipper und Hydraulik.' },
    ratgeberModern,
  ],
  service: { name: 'Umbau und Reparatur von Baumaschinen', serviceType: 'Umbau und Reparatur von Baumaschinen' },
  keywords: ['Baumaschinen Umbau'],
};

/** Alle Unterseiten des Bereichs, in der Reihenfolge der Navigation. */
export const sonderloesungenPages = [konstruktion, stahlbau, baumaschinen];

const nav = site.areas.find((a) => a.id === 'sonderloesungen')!.children.map((c) => c.href).join();
if (nav !== sonderloesungenPages.map((p) => p.path).join()) throw new Error('Sonderlösungen: Navigation und Seiten nennen andere Pfade.');
