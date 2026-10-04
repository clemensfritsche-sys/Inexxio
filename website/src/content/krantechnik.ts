/**
 * Krantechnik – Bereichsseite und vier Unterseiten (Auftrag Kap. 3.3 A, 7.4, 7.5).
 * Heukrananlagen stehen an erster Stelle. «HS» ist kein Produktname mehr: es sind
 * Krananlagen von INEXXIO; Besitzer bestehender HS-Anlagen finden den Hinweis im Text,
 * in den FAQ und auf der Übergabe-Seite.
 */
import { site } from '../config/site.mjs';
import { inquiry } from '../config/inquiry.mjs';
import { sharedFaq } from './uebergabe';
import type { AreaPage, Faq, Step, SubPage } from './types';

const anfrage = (label: string) => ({ label, href: '#anfrage' });

/** Dieselbe Antwort wie auf Startseite und Übergabe (#1127). */
const faqHsCare = sharedFaq.whoCares;
const faqSpeed: Faq = {
  q: 'Wie schnell sind Sie bei einem Stillstand vor Ort?',
  a: 'Steht eine Anlage still, rufen Sie am besten direkt an: {{phone.link}}.',
};
/**
 * Krane anderer Hersteller – bewusst zurückhaltend (Rückmeldung 04.10.2026: «defensiver …
 * ich möchte nicht lügen»). Schwerpunkt sind die HS- und die eigenen Anlagen; alles andere
 * auf Anfrage, ohne Versprechen zu Teilen.
 */
const otherMakes = 'Auf Anfrage. Unser Schwerpunkt sind die HS- und unsere eigenen Krananlagen; bei Kranen anderer Hersteller klären wir im Einzelfall, ob und wie wir helfen können.';
const ratgeberPruefung = { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Wer muss wann was prüfen?', kind: 'ratgeber' as const };
const ratgeberHeukran = { href: '/ratgeber/heukrananlage-planen', label: 'Neue Heukrananlage planen', text: 'Bauformen, Platzbedarf, Ablauf.', kind: 'ratgeber' as const };

/* ------------------------------------------------------------------ Bereich */
export const krantechnik: AreaPage = {
  id: 'krantechnik',
  path: '/krantechnik',
  title: 'Krananlagen und Kranservice',
  description:
    'Heukrananlagen und Industriekrane nach Mass, dazu Prüfung, Wartung und Modernisierung bestehender Anlagen in der Schweiz. Jetzt unverbindlich anfragen.',
  hero: {
    eyebrow: 'Krantechnik',
    h1: 'Krantechnik: Heukrananlagen und ==Industriekrane==',
    lead:
      'Wir planen und bauen Krananlagen nach Mass – seit {{history.cranesSince}} in der eigenen Werkstatt. Und wir prüfen, warten, reparieren und modernisieren bestehende Anlagen, allen voran die HS-Krananlagen.',
    photo: 'heukran-einsatz',
    primary: anfrage('Anfrage stellen'),
  },
  summary:
    '{{brand.full}} plant, baut und montiert Heukrananlagen für die Landwirtschaft und Industriekrane für Gewerbe, Industrie und Gemeinden. Dazu kommen Prüfung, Wartung, Reparatur und Modernisierung bestehender Anlagen – vor allem der HS- und unserer eigenen, auf Anfrage auch anderer. Die Werkstatt steht in Tuttwil-Wängi TG; im Einsatz sind wir {{area.summary}}.',
  levels: [
    {
      title: 'Lösungen',
      text: 'Neue Krananlagen nach Mass: vom Heukran in der Scheune bis zum Brückenkran in der Halle – und Umbauten bestehender Anlagen.',
      links: [
        { href: '/krantechnik/heukrananlagen', label: 'Heukrananlagen' },
        { href: '/krantechnik/industriekrane', label: 'Industriekrane' },
        { href: '/krantechnik/modernisierung', label: 'Modernisierung' },
      ],
    },
    {
      title: 'Service & Reparatur',
      text: 'Jährliche Überprüfung, Wartung und Reparatur – für HS- und eigene Anlagen, auf Anfrage auch für andere. Mit Bericht zu jeder Arbeit.',
      links: [
        { href: '/krantechnik/pruefung-wartung', label: 'Prüfung & Wartung' },
        { href: '/krantechnik/industriekrane#service', label: 'Service und Reparatur' },
        { href: '/service/notfall', label: 'Notfall-Service' },
      ],
    },
    {
      title: 'Ersatzteile für HS-Anlagen',
      text: 'Für die bestehenden HS-Anlagen liegen die Teile entweder an Lager, oder wir fertigen sie neu an.',
      links: [
        { href: '/krantechnik/heukrananlagen#bestehende-anlagen', label: 'Bestehende HS-Anlagen' },
        { href: '/kontakt', label: 'Teil anfragen' },
      ],
    },
  ],
  steps: [
    { title: 'Anfrage', text: 'Sie schildern Ihr Anliegen – per Formular oder am Telefon. Ein Foto vom Typenschild hilft.' },
    { title: 'Abklärung', text: 'Wir klären vor Ort oder am Telefon, was es braucht, und machen eine Offerte.' },
    { title: 'Umsetzung', text: 'Wir bauen, montieren, prüfen oder reparieren – mit den nötigen Teilen im Fahrzeug.' },
    { title: 'Bericht', text: 'Sie erhalten einen Bericht zu jeder Arbeit; der Eintrag gehört ins Kranbuch.' },
  ],
  faq: [
    {
      q: 'Bauen Sie weiterhin neue Krananlagen?',
      a: 'Ja. Heukrananlagen und Industriekrane planen und bauen wir nach Mass – abgestimmt auf Ihr Gebäude und Ihre Arbeit.',
    },
    faqHsCare,
    { q: 'Betreuen Sie auch Krane anderer Hersteller?', a: otherMakes },
    {
      q: 'Wie oft muss ein Kran geprüft werden?',
      a: 'Alle Krane regelmässig, nach den Angaben des Herstellers, durch Kranfachleute. Für Fahrzeug- und Turmdrehkrane gelten zusätzlich feste Fristen. Die Übersicht steht auf der Seite [Prüfung und Wartung](/krantechnik/pruefung-wartung).',
    },
    faqSpeed,
  ],
  service: { name: 'Krantechnik', serviceType: 'Bau, Prüfung, Wartung, Reparatur und Modernisierung von Krananlagen' },
  keywords: ['Krananlagen', 'Kranbau Thurgau', 'Kranservice Schweiz'],
};

/* ------------------------------------------------------------------ Heukrananlagen */
export const heukrananlagen: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/heukrananlagen',
  crumb: 'Heukrananlagen',
  title: 'Heukrananlagen nach Mass',
  description:
    'Heukran kaufen oder umbauen: Heukrananlagen nach Mass für Heu, Silage, Hackschnitzel, Kompost und Biogas – dazu Service und Saison-Check. Anfragen.',
  hero: {
    eyebrow: 'Krantechnik · Heukrananlagen',
    h1: 'Heukrananlagen nach Mass – neu, umgebaut, betreut',
    lead:
      'Seit {{history.cranesSince}} bauen wir in Tuttwil Heukrane für Betriebe in der Schweiz und im Ausland. Wir planen Ihre Anlage passend zum Gebäude, bauen bestehende um und halten sie mit Service am Laufen.',
    photo: 'heukran-einsatz',
    primary: anfrage('Anlage anfragen'),
  },
  summary:
    '{{brand.full}} plant und baut Heukrananlagen nach Mass: Einschienenkrane, Brückenkrane, hydraulische Drehkrane und Anlagen, die an das Gebäude angepasst sind. Dazu kommen Umbau, Service und Saison-Check – auch für alle bestehenden HS-Krananlagen. Die Werkstatt steht in Tuttwil-Wängi TG.',
  glance: {
    forWhom: 'Landwirtschaftsbetriebe für Heu, Stroh, Silage und Mist – und alle, die lose Güter mit dem Greifer umschlagen: Hackschnitzel- und Holzheizungen, Sägewerke, Kompost- und Biogasanlagen, Werkhöfe von Gemeinden.',
    what: 'Besichtigung, Konzept und Offerte, Fertigung in der eigenen Werkstatt, Montage und Inbetriebnahme – danach Service und Saison-Check.',
    deliverables: 'Eine Anlage, die zu Ihrem Gebäude passt, mit Einweisung in Bedienung und Wartung – und einen Ansprechpartner, der sie kennt.',
  },
  scope: {
    title: 'Was wir für Ihre Heukrananlage tun',
    lead: 'Von der ersten Skizze bis zum Service.',
    items: [
      { title: 'Neuanlage nach Mass', text: 'Bauform, Spannweite und Hubhöhe passend zu Scheune, Heustock und Arbeitsweise.' },
      { title: 'Umbau und Erweiterung', text: 'Längere Fahrbahn, neuer Greifer, zusätzlicher Bereich – die bestehende Anlage wächst mit dem Betrieb.' },
      { title: 'Service und Saison-Check', text: 'Kranbahn, Fahrwerke, Seil, Greifer, Hydraulik und Elektrik prüfen, bevor die Ernte beginnt.' },
      { title: 'Reparatur', text: 'Fehlersuche und Reparatur vor Ort.' },
      { title: 'Ersatzteile für HS-Anlagen', text: 'An Lager oder für Sie neu gefertigt – auch für ältere Anlagen.' },
      { title: 'Modernisierung', text: 'Funkfernsteuerung, Frequenzumrichter und neue Steuerung für bestehende Anlagen.' },
    ],
  },
  faq: [
    {
      q: 'Was kostet eine neue Heukrananlage?',
      a: 'Das hängt von Bauform, Spannweite, Hubhöhe und Gebäude ab. Nach der Besichtigung erhalten Sie eine Offerte.',
    },
    {
      q: 'Wie lange dauert es von der Anfrage bis zur fertigen Anlage?',
      a: 'Das hängt von Bauform und Auslastung ab. Planen Sie früh – am besten im Winter, damit die Anlage vor dem ersten Schnitt läuft.',
    },
    faqHsCare,
    sharedFaq.parts,
    {
      q: 'Wann ist der beste Zeitpunkt für den Service?',
      a: 'Vor der Saison, zwischen März und Mai. Dann bleibt Zeit für Reparaturen, ohne dass das Wetter drängt.',
    },
    {
      q: 'Bauen Sie auch Anlagen im Ausland?',
      a: 'Ja. Krananlagen planen und bauen wir {{area.summary}} – fragen Sie an.',
    },
  ],
  related: [
    { href: '/krantechnik/modernisierung', label: 'Modernisierung', text: 'Funkfernsteuerung, Umrichter und neue Steuerung für ältere Anlagen.' },
    { href: '/krantechnik/pruefung-wartung', label: 'Prüfung und Wartung', text: 'Jährliche Überprüfung mit Bericht.' },
    ratgeberHeukran,
  ],
  service: { name: 'Heukrananlagen', serviceType: 'Bau, Umbau und Service von Heukrananlagen' },
  keywords: ['Heukran', 'Heukrananlage', 'Heukran kaufen', 'Heukran Service', 'Heudrehkran', 'Hackschnitzelkran'],
};

/** Module der Heukran-Seite (Auftrag 7.5). */
export const heukranModules = {
  forms: {
    title: 'Bauformen',
    lead: 'Welche Bauform passt, hängt vom Gebäude und von der Arbeit ab. Bei der Besichtigung klären wir es gemeinsam.',
    items: [
      { title: 'Einschienenkran', illo: 'einschiene' as const, text: 'Der Kran fährt auf einer Laufschiene unter dem Dach.', use: 'Lange, schmale Scheunen; ein Heustock entlang der Fahrbahn.' },
      { title: 'Brückenkran', illo: 'bruecke' as const, text: 'Eine Kranbrücke fährt über die ganze Breite des Gebäudes, die Katze quer dazu.', use: 'Breite Scheunen; mehrere Stöcke oder Abladeplätze, die Fläche wird ganz erreicht.' },
      { title: 'Drehkran, hydraulisch', illo: 'drehkran' as const, text: 'Ein Drehturm mit Ausleger fährt in Längs- und Querrichtung und dreht zusätzlich um die eigene Achse; der Antrieb ist hydraulisch.', use: 'Der Greifer soll auch Ecken, Nischen und Abladeplätze neben der Fahrbahn erreichen.' },
      { title: 'An das Gebäude angepasst', illo: 'angepasst' as const, text: 'Fahrbahn, Stützen und Spannweite richten sich nach dem bestehenden Bau.', use: 'Umbauten, ungewöhnliche Grundrisse, Erweiterungen bestehender Anlagen.' },
    ],
  },
  steps: {
    title: 'Ablauf einer Neuanlage',
    items: [
      { title: 'Besichtigung', text: 'Wir schauen Scheune, Heustock und Abladeplatz an und hören zu, wie Sie arbeiten.' },
      { title: 'Konzept und Offerte', text: 'Sie erhalten einen Vorschlag zu Bauform, Spannweite und Hubhöhe – mit Offerte.' },
      { title: 'Fertigung', text: 'Wir fertigen die Anlage in unserer Werkstatt in Tuttwil.' },
      { title: 'Montage und Inbetriebnahme', text: 'Wir montieren vor Ort, nehmen in Betrieb und zeigen Ihnen die Bedienung.' },
      { title: 'Service', text: 'Saison-Check und Wartung – solange die Anlage läuft.' },
    ] satisfies Step[],
  },
  owners: {
    title: 'Sie haben eine HS-Krananlage? Ihre Anlage wird weiter betreut.',
    text: 'Die Anlagen, die seit {{history.cranesSince}} in Tuttwil entstanden sind, betreuen wir weiter. Die Übergabe an {{people.owner.name}} ändert daran nichts: Service, Reparatur und Ersatzteile führen wir weiter – mit demselben Wissen. Mehr dazu auf der Seite [Aus HS Steiner wird {{brand.name}}](/uebergabe).',
  },
  season: {
    title: 'Saison-Check vor dem ersten Schnitt',
    text: 'Ein Heukran steht über den Winter still und muss beim ersten Schnitt sofort laufen. Beim Saison-Check zwischen März und Mai prüfen wir Kranbahn, Fahrwerke, Seil oder Kette, Greifer, Hydraulik und Elektrik – und ersetzen, was bis zur Ernte nicht hält.',
    checks: ['Kranbahn und Endanschläge', 'Fahrwerke und Laufräder', 'Seil oder Kette, Haken', 'Greifer: Zinken, Bolzen, Lager', 'Hydraulik: Schläuche, Zylinder, Hydrauliköl', 'Elektrik: Endschalter, Not-Halt, Steuerung'],
  },
};

/* ------------------------------------------------------------------ Industriekrane */
export const industriekrane: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/industriekrane',
  crumb: 'Industriekrane',
  title: 'Industriekrane nach Mass',
  description:
    'Brückenkran, Hallenkran, Schwenkkran: neue Industriekrane nach Mass, dazu Service und Reparatur bestehender Anlagen in der Schweiz. Jetzt anfragen.',
  hero: {
    eyebrow: 'Krantechnik · Industriekrane',
    h1: 'Industriekrane: neue Anlagen und Service',
    lead:
      'Brücken-, Hänge-, Schwenk- und Drehkrane für Gewerbe, Industrie und Gemeinden. Wir planen neue Anlagen nach Mass und betreuen bestehende – aus der Region, mit kurzen Wegen.',
    photo: 'reparatur-vor-ort',
    primary: anfrage('Kran anfragen'),
  },
  summary:
    '{{brand.full}} plant und baut Industriekrane – Brücken-, Hänge-, Schwenk- und Drehkrane – und prüft, wartet und repariert bestehende Krane in Gewerbe, Industrie und Gemeinden. Steht ein Kran still, rufen Sie direkt an.',
  glance: {
    forWhom: 'Instandhaltungs- und Betriebsleiter in Produktions- und Gewerbebetrieben, Werkhöfe von Gemeinden.',
    what: 'Neuanlagen nach Mass, Prüfung, Wartung, Fehlersuche und Reparatur.',
    deliverables: 'Einen Rapport mit Ursache, Arbeiten und verbauten Teilen – bei Neuanlagen die Unterlagen zur Anlage.',
  },
  scope: {
    title: 'Welche Krane wir bauen und betreuen',
    lead: 'Neue Anlagen nach Mass – und Service für bestehende.',
    items: [
      { title: 'Brückenkrane', text: 'Ein- und Zweiträger-Brückenkrane in Produktions- und Lagerhallen.' },
      { title: 'Hängekrane', text: 'Unter der Hallendecke aufgehängt – für Hallen ohne Kranbahnstützen.' },
      { title: 'Schwenkkrane', text: 'Säulen- und Wandschwenkkrane direkt am Arbeitsplatz.' },
      { title: 'Drehkrane', text: 'Elektrisch oder hydraulisch, im Werkhof und auf dem Betriebsgelände.' },
      { title: 'Hubwerk, Fahrwerke, Elektrik', text: 'Seil- und Kettenzüge, Bremsen, Getriebe, Antriebe, Schaltschrank und Steuerung.' },
      { title: 'Tragwerk und Kranbahn', text: 'Schäden am Stahlbau und an der Kranbahn begutachten und instand stellen.' },
    ],
  },
  faq: [
    { q: 'Reparieren Sie auch Krane anderer Hersteller?', a: otherMakes },
    {
      q: 'Was tue ich, wenn der Kran stehen bleibt?',
      a: 'Den Kran ausser Betrieb nehmen und sichern, die Last – wenn möglich – sicher absetzen und uns anrufen: {{phone.link}}. Nicht unter Last weiterarbeiten.',
    },
    faqSpeed,
    {
      q: 'Bauen Sie neue Industriekrane?',
      a: 'Ja – abgestimmt auf Halle, Last und Arbeitsplatz.',
    },
  ],
  related: [
    { href: '/service/notfall', label: 'Notfall-Service', text: 'Wenn der Kran heute stillsteht.' },
    { href: '/krantechnik/pruefung-wartung', label: 'Prüfung und Wartung', text: 'Prüfpflicht erfüllen, Ausfälle vermeiden.' },
    ratgeberPruefung,
  ],
  service: { name: 'Industriekrane', serviceType: 'Bau, Service und Reparatur von Industriekranen' },
  keywords: ['Brückenkran', 'Hallenkran', 'Schwenkkran', 'Kranreparatur'],
};

/** Modul: Hinweis «Foto mitschicken» und Abschnitt Service (Anker #service). */
export const industrieModules = {
  service: {
    title: 'Service und Reparatur',
    text: 'Wir suchen die Ursache und reparieren vor Ort – für die HS- und unsere eigenen Anlagen, auf Anfrage auch für andere. Steht ein Kran still, rufen Sie direkt an.',
  },
  photoHint: {
    title: 'Foto vom Typenschild oder vom Schaden mitschicken',
    text: `Mit einem Foto wissen wir vor dem Einsatz, welcher Kran es ist, und können den Einsatz besser vorbereiten. Im Formular können Sie bis zu ${inquiry.photos.max} Fotos anhängen.`,
  },
};

/* ------------------------------------------------------------------ Prüfung & Wartung */
export const pruefung: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/pruefung-wartung',
  crumb: 'Prüfung & Wartung',
  title: 'Kranprüfung und Kranwartung',
  description:
    'Kranprüfung und Wartung für Brücken-, Hänge-, Dreh- und Heukrane in der Schweiz – die Prüfpflicht einfach erklärt, mit Bericht. Jetzt anfragen.',
  hero: {
    eyebrow: 'Krantechnik · Prüfung & Wartung',
    h1: 'Kranprüfung und Wartung – Prüfpflicht erfüllt',
    lead:
      'Wir prüfen und warten Ihre Krane nach den Angaben des Herstellers und dokumentieren jede Arbeit. So ist die Prüfpflicht erfüllt – und der Kran läuft, wenn Sie ihn brauchen.',
    photo: 'pruefung-hallenkran',
    primary: anfrage('Prüfung anfragen'),
  },
  summary:
    '{{brand.full}} prüft und wartet Krane: Brücken-, Hänge-, Schwenk- und Drehkrane in Industrie und Gewerbe sowie Heukrane in der Landwirtschaft. Jede Prüfung endet mit einem Bericht für das Kranbuch.',
  glance: {
    forWhom: 'Betriebe mit Hallen-, Werkhof- oder Heukranen – vom Gewerbebetrieb bis zum Bauernhof.',
    what:
      'Überprüfung nach Herstellerangaben, Wartung, Schmierung und Verschleiss-Check durch Kranfachleute.',
    deliverables: 'Einen einwandfreien, sicheren Kran – gewartet, geprüft und mit Prüfbericht für das Kranbuch.',
  },
  scope: {
    title: 'Was wir prüfen und warten',
    items: [
      { title: 'Tragwerk und Kranbahn', text: 'Risse, Verformungen und lose Verbindungen; Zustand von Schienen, Puffern und Endanschlägen.' },
      { title: 'Hubwerk, Seil und Kette', text: 'Seil oder Kette, Haken und Hakensicherung, Bremse und Getriebe.' },
      { title: 'Fahrwerke', text: 'Laufräder, Antriebe und Bremsen von Katze und Kranbrücke.' },
      { title: 'Elektrik und Steuerung', text: 'Endschalter, Not-Halt, Hängetaster oder Funkfernsteuerung, Kabel und Stromzuführung.' },
      { title: 'Sicherheitseinrichtungen', text: 'Überlastsicherung, Schutzeinrichtungen, Beschilderung und Tragfähigkeitsangaben.' },
      { title: 'Wartung', text: 'Schmieren, nachstellen, Verschleissteile ersetzen – nach Vorgabe des Herstellers.' },
    ],
  },
  faq: [
    {
      q: 'Wie oft muss ich meinen Hallenkran prüfen lassen?',
      a: 'Regelmässig, nach den Angaben des Herstellers – in der Praxis meist einmal im Jahr. Massgebend sind die Betriebsanleitung und die Vorgaben der Suva.',
    },
    { q: 'Prüfen Sie auch Krane anderer Hersteller?', a: otherMakes },
    {
      q: 'Was steht im Prüfbericht?',
      a: 'Was geprüft wurde, in welchem Zustand der Kran ist und was zu beheben ist. Der Bericht gehört ins Kranbuch.',
    },
    {
      q: 'Darf das Kranbuch digital sein?',
      a: 'Ja. Die Form des Kranbuchs ist frei – Papier oder digital.',
    },
    {
      q: 'Machen Sie auch die Kontrolle durch den Kranexperten?',
      a: 'Nein. Die periodische Kontrolle von Fahrzeug- und Turmdrehkranen macht ein von der Suva anerkannter Kranexperte. Wir übernehmen die Überprüfung durch Kranfachleute und die Wartung. Den Unterschied erklärt unser Ratgeber [Kranprüfung in der Schweiz](/ratgeber/kranpruefung-schweiz#kranfachmann-oder-kranexperte).',
    },
    {
      q: 'Was kostet eine Kranprüfung?',
      a: 'Das hängt von Kranart und Grösse ab. Fragen Sie uns an.',
    },
  ],
  related: [
    { href: '/krantechnik/modernisierung', label: 'Modernisierung', text: 'Wenn bei der Prüfung Steuerung oder Antrieb auffallen.' },
    { href: '/service/notfall', label: 'Notfall-Service', text: 'Wenn der Kran stillsteht.' },
    ratgeberPruefung,
  ],
  service: { name: 'Kranprüfung und Kranwartung', serviceType: 'Kranprüfung' },
  keywords: ['Kranprüfung', 'Krankontrolle', 'Kranwartung'],
};

/* ------------------------------------------------------------------ Modernisierung */
export const modernisierung: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/modernisierung',
  crumb: 'Modernisierung',
  title: 'Kran modernisieren',
  description:
    'Kran modernisieren statt ersetzen: Funkfernsteuerung nachrüsten, Frequenzumrichter, Überlastsicherung und neue Steuerung für bestehende Krane. Anfragen.',
  hero: {
    eyebrow: 'Krantechnik · Modernisierung',
    h1: 'Kran modernisieren statt ersetzen',
    lead:
      'Ein guter Stahlbau hält Jahrzehnte – Steuerung und Antrieb oft nicht. Wir rüsten ältere Krane nach: sicherer, ruhiger und einfacher zu bedienen.',
    photo: 'steuerung-funk',
    primary: anfrage('Modernisierung anfragen'),
  },
  summary:
    '{{brand.full}} modernisiert ältere Krane: Funkfernsteuerung, Frequenzumrichter, Überlastsicherung, Steuerung, Endschalter und Greifer. Vorher klären wir vor Ort, was sich lohnt, und dokumentieren jeden Umbau.',
  glance: {
    forWhom: 'Betriebe mit älteren Hallen- oder Heukranen, deren Steuerung oder Antrieb an Grenzen stösst.',
    what: 'Bestandsaufnahme, Offerte, Umbau, Inbetriebnahme und Dokumentation.',
    deliverables: 'Einen modernisierten Kran mit allen Unterlagen zum Umbau.',
  },
  scope: {
    title: 'Was wir nachrüsten',
    items: [
      { title: 'Funkfernsteuerung', text: 'Wer bedient, steht dort, wo er die Last sieht – nicht dort, wo das Kabel endet.' },
      { title: 'Frequenzumrichter', text: 'Sanftes Anfahren und Bremsen: Die Last pendelt weniger, Getriebe und Bremsen verschleissen langsamer.' },
      { title: 'Überlastsicherung', text: 'Verhindert, dass mehr gehoben wird, als der Kran tragen darf.' },
      { title: 'Steuerung', text: 'Neue Schaltschränke und Komponenten, für die es wieder Ersatzteile gibt.' },
      { title: 'Endschalter', text: 'Begrenzen Hub- und Fahrwege zuverlässig und schützen Kran und Gebäude.' },
      { title: 'Greifer', text: 'Ein neuer oder überholter Greifer – bei Heukranen das Teil, das am meisten arbeitet.' },
    ],
  },
  faq: [
    {
      q: 'Lohnt sich eine Modernisierung bei einem alten Kran?',
      a: 'Oft ja: Der Stahlbau hält meist viel länger als Steuerung und Antrieb. Ob es sich lohnt, zeigt die Bestandsaufnahme – ist ein neuer Kran die bessere Lösung, sagen wir das.',
    },
    {
      q: 'Kann man jeden Kran mit Funk nachrüsten?',
      a: 'Die meisten Brücken-, Hänge- und Drehkrane ja. Vor Ort klären wir, welche Steuerung vorhanden ist und was es dafür braucht.',
    },
    {
      q: 'Was bringt ein Frequenzumrichter?',
      a: 'Er lässt die Motoren sanft anfahren und abbremsen. Die Last pendelt weniger, Getriebe, Bremsen und Kranbahn werden geschont.',
    },
    { q: 'Rüsten Sie auch Krane anderer Hersteller um?', a: otherMakes },
    {
      q: 'Was ändert sich mit der neuen EU-Maschinenverordnung?',
      a: 'Sie gilt in der EU ab dem 20. Januar 2027; die Schweiz passt ihre Maschinenverordnung an. Wer eine Maschine wesentlich verändert, braucht saubere Unterlagen.',
    },
  ],
  related: [
    { href: '/krantechnik/industriekrane', label: 'Industriekrane', text: 'Wenn ein neuer Kran die bessere Lösung ist.' },
    { href: '/sonderloesungen/konstruktion-engineering', label: 'Konstruktion und Engineering', text: 'Berechnung und Dokumentation für Umbauten.' },
    ratgeberPruefung,
  ],
  service: { name: 'Kranmodernisierung', serviceType: 'Modernisierung von Krananlagen' },
  keywords: ['Kran modernisieren', 'Funkfernsteuerung Kran nachrüsten', 'Frequenzumrichter Kran'],
};

/** Hinweis EU-Maschinenverordnung (Modul der Modernisierungsseite). */
export const machineryNote = {
  title: 'Umbauten sauber dokumentieren',
  text: [
    'Ab dem 20. Januar 2027 gilt in der EU die neue Maschinenverordnung (EU) 2023/1230. Die Schweiz revidiert ihre Maschinenverordnung, damit die Regeln gleichwertig und gleichzeitig gelten.',
    'Wer eine Maschine wesentlich verändert, übernimmt dafür Verantwortung – und braucht saubere Unterlagen: was umgebaut wurde, mit welchen Teilen, mit welchen Einstellungen. Diese Unterlagen liefern wir mit jedem Umbau.',
  ],
  sources: [
    { label: 'SECO: Maschinen', href: 'https://www.seco.admin.ch/de/maschinen' },
    { label: 'Verordnung (EU) 2023/1230 über Maschinen, EUR-Lex', href: 'https://eur-lex.europa.eu/eli/reg/2023/1230/oj' },
  ],
};

/** Alle Unterseiten des Bereichs, in der Reihenfolge der Navigation. */
export const krantechnikPages = [heukrananlagen, industriekrane, pruefung, modernisierung];

// Die Navigation (site.areas) und diese Seiten müssen dieselben Pfade nennen.
const nav = site.areas.find((a) => a.id === 'krantechnik')!.children.map((c) => c.href).join();
if (nav !== krantechnikPages.map((p) => p.path).join()) throw new Error('Krantechnik: Navigation und Seiten nennen andere Pfade.');
