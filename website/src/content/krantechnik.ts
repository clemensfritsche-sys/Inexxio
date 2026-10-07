/**
 * Krantechnik – Bereichsseite und fünf Unterseiten (WEBSITE_PLAN §7.7a/§7.7b).
 * Zuerst der Kranservice (einzeln oder als Jahrespaket – EINE Seite für Prüfung, Wartung und
 * Pakete), dann die Fokusmärkte (Industrie-KMU, Häfen & Werften, Landwirtschaft), dann die
 * Modernisierung. «HS» ist kein Produktname mehr; Besitzer bestehender HS-Anlagen finden den
 * Hinweis im Text, in den FAQ und auf der Übergabe-Seite.
 */
import { site } from '../config/site.mjs';
import { inquiry } from '../config/inquiry.mjs';
import { sharedFaq } from './uebergabe';
import type { AreaPage, Faq, Step, SubPage } from './types';

const anfrage = (label: string) => ({ label, href: '#anfrage' });

/** Dieselbe Antwort wie auf Startseite und Übergabe (#1127). */
const faqHsCare = sharedFaq.whoCares;
const faqSpeed = sharedFaq.speed;
const faqOtherMakes = sharedFaq.otherMakes;
/** Der Jahrespreis – Bereichsseite und Unterseiten verweisen gleich auf den Kranservice. */
const faqYear: Faq = {
  q: 'Gibt es einen festen Preis pro Jahr?',
  a: 'Ja. Neben einzelnen Einsätzen bieten wir drei Pakete zum festen Preis pro Kran und Jahr – von der Prüfung bis zum Rundum-Service. Mehr dazu unter [Kranservice](/krantechnik/kranservice#pakete).',
};
const ratgeberPruefung = { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Wer muss wann was prüfen?', kind: 'ratgeber' as const };
const ratgeberHeukran = { href: '/ratgeber/heukrananlage-planen', label: 'Neue Heukrananlage planen', text: 'Bauformen, Platzbedarf, Ablauf.', kind: 'ratgeber' as const };

/* ------------------------------------------------------------------ Bereich */
export const krantechnik: AreaPage = {
  id: 'krantechnik',
  path: '/krantechnik',
  title: 'Krananlagen und Kranservice',
  description:
    'Kranservice einzeln oder zum Jahrespreis, neue Heukrananlagen und Industriekrane, Boots- und Mastkrane, Modernisierung – aus Tuttwil-Wängi TG.',
  hero: {
    eyebrow: 'Krantechnik',
    h1: 'Krantechnik: Service, neue Anlagen und ==Modernisierung==',
    lead:
      'Wir prüfen, warten und reparieren Krane – einzeln oder zum festen Preis pro Jahr. Für Industrie und Gewerbe, Häfen und Werften und die Landwirtschaft. Und wir bauen neue Anlagen: Krane entstehen bei uns seit {{history.cranesSince}}.',
    photo: 'heukran-einsatz',
    primary: anfrage('Anfrage stellen'),
  },
  summary:
    '{{brand.full}} prüft, wartet, repariert und modernisiert Krane – einzeln oder als Jahrespaket zum festen Preis pro Kran: Brücken-, Hänge- und Schwenkkrane in Industrie- und Gewerbebetrieben, Boots- und Mastkrane und Bootslifte in Häfen, Segelclubs und Werften sowie Heukrananlagen. Neue Heukrananlagen und Industriekrane bauen wir nach Mass. Die Werkstatt steht in Tuttwil-Wängi TG; im Einsatz sind wir {{area.summary}}.',
  steps: [
    { title: 'Anfrage', text: 'Sie schildern Ihr Anliegen – per Formular oder am Telefon. Ein Foto vom Typenschild hilft.' },
    { title: 'Abklärung', text: 'Wir klären vor Ort oder am Telefon, was es braucht, und machen eine Offerte.' },
    { title: 'Umsetzung', text: 'Wir bauen, montieren, prüfen oder reparieren – mit den nötigen Teilen im Fahrzeug.' },
    { title: 'Bericht', text: 'Sie erhalten einen Bericht zu jeder Arbeit; der Eintrag gehört ins Kranbuch.' },
  ],
  faq: [
    faqYear,
    sharedFaq.newCranes,
    faqHsCare,
    faqOtherMakes,
    faqSpeed,
  ],
  service: { name: 'Krantechnik', serviceType: 'Bau, Prüfung, Wartung, Reparatur und Modernisierung von Krananlagen' },
  keywords: ['Kranservice Schweiz', 'Krananlagen', 'Kranbau Thurgau', 'Kranprüfung'],
};

/* ------------------------------------------------------------------ Häfen & Werften */
export const haefen: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/haefen-werften',
  crumb: 'Häfen & Werften',
  title: 'Boots- und Mastkrane',
  description:
    'Prüfung, Wartung und Reparatur von Bootskranen, Mastkranen und Bootsliften für Häfen, Segelclubs, Gemeinden und Werften – einzeln oder zum Jahrespreis.',
  hero: {
    eyebrow: 'Krantechnik · Häfen & Werften',
    h1: 'Boots- und Mastkrane, die zur ==Saison== laufen',
    lead:
      'Im Frühling kommen die Boote ins Wasser, im Herbst wieder heraus. Dann muss der Kran laufen. Wir prüfen, warten und reparieren Boots- und Mastkrane und Bootslifte – für Häfen, Segelclubs, Gemeinden und Werften.',
    photo: 'hafen-bootskran',
    primary: anfrage('Anlage anfragen'),
  },
  summary:
    '{{brand.full}} prüft, wartet und repariert Bootskrane, Mastkrane und Bootslifte für Häfen, Segelclubs, Gemeindehäfen und Werften – einzeln oder als Jahrespaket zum festen Preis pro Kran. Krane bauen und betreuen wir seit {{history.cranesSince}}; im Einsatz sind wir {{area.summary}}.',
  glance: {
    forWhom: 'Hafenmeister, Segel- und Bootsclubs, Gemeinden mit eigenem Hafen, Werften und Bootsbauer.',
    what: 'Prüfung, Wartung und Reparatur von Boots- und Mastkranen und Bootsliften – einzeln oder als Jahrespaket.',
    deliverables: 'Eine geprüfte Anlage vor dem Einwassern, ein nachgeführtes Kranbuch und einen Ansprechpartner, der sie kennt.',
  },
  scope: {
    title: 'Was wir am Hafen betreuen',
    lead: 'Wasser, Wetter und lange Pausen setzen Seil, Stahlbau und Elektrik zu.',
    items: [
      { title: 'Bootskrane', text: 'Säulen- und Schwenkkrane am Steg oder auf dem Hafenplatz, die Boote ein- und auswassern.' },
      { title: 'Mastkrane', text: 'Kleine Krane zum Stellen und Legen der Masten – oft von vielen Mitgliedern bedient.' },
      { title: 'Bootslifte', text: 'Lifte, die das Boot aus dem Wasser heben und dort halten.' },
      { title: 'Prüfung vor der Saison', text: 'Tragwerk, Seil oder Kette, Haken, Bremse, Endschalter und Not-Halt – bevor der Ansturm kommt.' },
      { title: 'Schutz vor Korrosion', text: 'Rost und Feuchtigkeit an Stahlbau, Seil und Elektrik finden und beheben.' },
      { title: 'Modernisierung', text: 'Funkfernsteuerung, Überlastsicherung und eine Bedienung, die auch Gelegenheitsnutzer sicher führt.' },
    ],
  },
  faq: [
    {
      q: 'Wann ist der beste Zeitpunkt für die Prüfung?',
      a: 'Vor dem Einwassern im Frühling. Dann bleibt Zeit für Reparaturen, bevor alle Boote auf einmal ins Wasser wollen. Nach dem Auswassern im Herbst lohnt sich ein Blick auf das, was über den Winter repariert werden kann.',
    },
    faqOtherMakes,
    {
      q: 'Gibt es einen festen Jahrespreis auch für Clubs und Gemeinden?',
      a: 'Ja. Ein fester Betrag pro Kran und Jahr lässt sich im Budget des Clubs oder der Gemeinde planen. Die drei Pakete stehen unter [Kranservice](/krantechnik/kranservice#pakete).',
    },
    {
      q: 'Unser Kran wird von vielen Mitgliedern bedient. Worauf achten Sie?',
      a: 'Auf eine klare Bedienung, sichere Endschalter und eine Überlastsicherung – und auf eine Einweisung, die der Club an seine Mitglieder weitergeben kann.',
    },
    {
      q: 'Arbeiten Sie auch an Seen ausserhalb der Ostschweiz?',
      a: 'Ja. Im Einsatz sind wir {{area.summary}}.',
    },
  ],
  related: [
    { href: '/krantechnik/kranservice', label: 'Kranservice', text: 'Einzeln oder zum festen Preis pro Jahr.' },
    { href: '/krantechnik/modernisierung', label: 'Modernisierung', text: 'Funk, Überlastsicherung, neue Steuerung.' },
    ratgeberPruefung,
  ],
  service: { name: 'Service für Boots- und Mastkrane', serviceType: 'Prüfung, Wartung und Reparatur von Bootskranen, Mastkranen und Bootsliften' },
  keywords: ['Bootskran', 'Mastkran', 'Bootslift', 'Hafenkran Service', 'Bootskran Prüfung'],
};

/** Das Hafenjahr – wann wir was tun (Modul der Häfen-Seite). */
export const harbourYear = {
  title: 'Das Hafenjahr',
  lead: 'Ein Bootskran arbeitet in Wellen. Wir richten den Service danach aus.',
  seasons: [
    { title: 'Vor dem Einwassern', when: 'Winter und Frühling', text: 'Prüfung und Wartung, Kranbuch nachführen, Mängel beheben – damit der Kran am ersten Krantag der Saison läuft.' },
    { title: 'In der Saison', when: 'Frühling bis Herbst', text: 'Fällt der Kran aus, rufen Sie direkt an. In den Paketen Pflege und Rundum gilt eine feste Reaktionszeit.' },
    { title: 'Nach dem Auswassern', when: 'Herbst', text: 'Zustand aufnehmen, Reparaturen und Modernisierungen über den Winter planen.' },
  ],
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
    { href: '/krantechnik/kranservice', label: 'Kranservice', text: 'Prüfung, Wartung und Saison-Check.' },
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
    text: 'Die Anlagen, die seit {{history.cranesSince}} in Tuttwil entstanden sind, betreuen wir weiter. Die Übergabe an {{people.owner.name}} ändert daran nichts: Service, Reparatur und Ersatzteile führen wir weiter – mit demselben Wissen. Mehr dazu unter [Aus HS Steiner wird {{brand.name}}](/ueber-uns#uebergabe).',
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
    'Brücken-, Hänge- und Schwenkkrane in KMU der Ostschweiz: Prüfung, Wartung und Reparatur, einzeln oder zum Jahrespreis – und neue Krane nach Mass.',
  hero: {
    eyebrow: 'Krantechnik · Industriekrane',
    h1: 'Industriekrane: Service, der den Betrieb ==laufen== lässt',
    lead:
      'Brücken-, Hänge- und Schwenkkrane in Industrie- und Gewerbebetrieben der Ostschweiz. Wir prüfen, warten und reparieren – zum festen Preis pro Kran und Jahr. Und wo ein neuer Kran die bessere Lösung ist, bauen wir ihn nach Mass.',
    photo: 'reparatur-vor-ort',
    primary: anfrage('Kran anfragen'),
  },
  summary:
    '{{brand.full}} prüft, wartet und repariert Brücken-, Hänge- und Schwenkkrane in Industrie- und Gewerbebetrieben der Ostschweiz – einzeln oder als Jahrespaket zum festen Preis pro Kran. Neue Industriekrane bauen wir nach Mass. Steht ein Kran still, rufen Sie direkt an.',
  glance: {
    forWhom: 'Instandhaltungs- und Betriebsleiter in Industrie- und Gewerbebetrieben (KMU) der Ostschweiz, Werkhöfe von Gemeinden.',
    what: 'Prüfung, Wartung, Fehlersuche und Reparatur – einzeln oder als Jahrespaket. Neuanlagen nach Mass.',
    deliverables: 'Einen Kran, der läuft, ein nachgeführtes Kranbuch und einen Rapport mit Ursache, Arbeiten und Teilen.',
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
    faqOtherMakes,
    faqYear,
    {
      q: 'Was tue ich, wenn der Kran stehen bleibt?',
      a: 'Den Kran ausser Betrieb nehmen und sichern, die Last – wenn möglich – sicher absetzen und uns anrufen: {{phone.link}}. Nicht unter Last weiterarbeiten.',
    },
    {
      q: 'Bauen Sie neue Industriekrane?',
      a: 'Ja – abgestimmt auf Halle, Last und Arbeitsplatz.',
    },
  ],
  related: [
    { href: '/krantechnik/kranservice', label: 'Kranservice', text: 'Einzeln oder zum festen Preis pro Jahr.' },
    { href: '/service#notfall', label: 'Notfall-Service', text: 'Wenn der Kran heute stillsteht.' },
    ratgeberPruefung,
  ],
  service: { name: 'Industriekrane', serviceType: 'Service, Reparatur und Bau von Industriekranen' },
  keywords: ['Brückenkran Service', 'Hallenkran Wartung', 'Schwenkkran', 'Kranreparatur Ostschweiz'],
};

/** Modul: Hinweis «Foto mitschicken» und Abschnitt Service (Anker #service). */
export const industrieModules = {
  service: {
    title: 'Service und Reparatur',
    text: 'Wir suchen die Ursache und reparieren vor Ort – unabhängig vom Hersteller. In den Paketen Pflege und Rundum gilt eine feste Reaktionszeit. Steht ein Kran still, rufen Sie direkt an.',
  },
  photoHint: {
    title: 'Foto vom Typenschild oder vom Schaden mitschicken',
    text: `Mit einem Foto wissen wir vor dem Einsatz, welcher Kran es ist, und können den Einsatz besser vorbereiten. Im Formular können Sie bis zu ${inquiry.photos.max} Fotos anhängen.`,
  },
};

/* ------------------------------------------------------------------ Kranservice */
/**
 * EINE Seite für Prüfung, Wartung und die Jahrespakete (Rückmeldung 07.10.2026: «Prüfung
 * und Wartung und Service-Vertrag zusammenführen»). Der Pfad bleibt `/pruefung-wartung` –
 * er ist verlinkt und wird gesucht.
 */
export const kranservice: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/kranservice',
  crumb: 'Kranservice',
  title: 'Kranservice und Kranprüfung',
  description:
    'Kranprüfung, Wartung und Reparatur – einzeln oder als Paket zum festen Preis pro Kran und Jahr. Die Prüfpflicht einfach erklärt, jede Arbeit mit Bericht.',
  hero: {
    eyebrow: 'Krantechnik · Kranservice',
    h1: 'Kranservice, wie Sie ihn ==brauchen==',
    lead:
      'Einmal prüfen lassen oder das ganze Jahr betreut: Sie wählen, wie viel wir Ihnen abnehmen. Jede Prüfung und jede Arbeit steht danach im Kranbuch.',
    photo: 'pruefung-hallenkran',
    primary: anfrage('Kranservice anfragen'),
  },
  summary:
    '{{brand.full}} prüft, wartet und repariert Krane: Brücken-, Hänge-, Schwenk- und Drehkrane, Boots- und Mastkrane und Heukrane. Jede Leistung gibt es einzeln nach Aufwand oder als Jahrespaket zum festen Preis pro Kran – Pflicht (Prüfung, Kranbuch, Fristen), Pflege (dazu Wartung und feste Reaktionszeit) oder Rundum (dazu Teile, Reparaturen und Ersatz-Hebezeug). Jede Prüfung endet mit einem Bericht für das Kranbuch.',
  glance: {
    forWhom: 'Betriebe mit einem oder mehreren Kranen: Industrie und Gewerbe, Häfen, Segelclubs und Werften, Landwirtschaft.',
    what: 'Prüfung nach Herstellerangaben, Wartung und Reparatur durch Kranfachleute – einzeln oder als Jahrespaket.',
    deliverables: 'Einen sicheren Kran, ein nachgeführtes Kranbuch und – wenn Sie wollen – einen festen Preis pro Jahr.',
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
      q: 'Was kostet der Kranservice?',
      a: 'Einzelne Arbeiten verrechnen wir nach Aufwand. Für ein Paket erhalten Sie je Kran einen festen Jahrespreis – er richtet sich nach Tragkraft, Alter und Nutzung. Nachdem wir Ihre Krane angeschaut haben, erhalten Sie eine Offerte.',
    },
    {
      q: 'Welches Paket passt zu mir?',
      a: 'Pflicht, wenn Sie vor allem die Prüfpflicht sicher erfüllen wollen. Pflege, wenn der Kran gewartet und im Störfall schnell betreut sein soll. Rundum, wenn Ihr Betrieb vom Kran abhängt und Sie Teile und Reparaturen nicht einzeln einplanen wollen.',
    },
    {
      q: 'Wie oft muss ich meinen Hallenkran prüfen lassen?',
      a: 'Regelmässig, nach den Angaben des Herstellers – in der Praxis meist einmal im Jahr. Massgebend sind die Betriebsanleitung und die Vorgaben der Suva.',
    },
    faqOtherMakes,
    {
      q: 'Was steht im Prüfbericht?',
      a: 'Was geprüft wurde, in welchem Zustand der Kran ist und was zu beheben ist. Der Bericht gehört ins Kranbuch – auf Papier oder digital, die Form ist frei.',
    },
    {
      q: 'Machen Sie auch die Kontrolle durch den Kranexperten?',
      a: 'Nein. Die periodische Kontrolle von Fahrzeug- und Turmdrehkranen macht ein von der Suva anerkannter Kranexperte. Wir übernehmen die Überprüfung durch Kranfachleute und die Wartung. Den Unterschied erklärt unser Ratgeber [Kranprüfung in der Schweiz](/ratgeber/kranpruefung-schweiz#kranfachmann-oder-kranexperte).',
    },
  ],
  related: [
    { href: '/krantechnik/modernisierung', label: 'Modernisierung', text: 'Wenn bei der Prüfung Steuerung oder Antrieb auffallen.' },
    { href: '/service#notfall', label: 'Notfall-Service', text: 'Wenn der Kran stillsteht.' },
    ratgeberPruefung,
  ],
  service: { name: 'Kranservice', serviceType: 'Kranprüfung, Kranwartung und Kranreparatur' },
  keywords: ['Kranservice', 'Kranprüfung', 'Kranwartung', 'Wartungsvertrag Kran', 'Kranbuch'],
};

/**
 * Die Pakete als Tabelle «was kann was» (Rückmeldung 07.10.2026: intuitiv zeigen, was welches
 * Paket kann). `from` = ab welchem Paket eine Zeile gilt – jedes Paket enthält das vorherige,
 * also gibt es keine Kreuzchen-Liste, die auseinanderlaufen kann. Kein Betrag: die Preise je
 * Kranklasse entstehen mit der Offerte – auf der Website steht kein Betrag.
 */
export const servicePlans = {
  title: 'Drei Pakete – oder einzeln',
  lead: 'Jedes Paket enthält das vorherige. Der Preis gilt pro Kran und Jahr.',
  plans: [
    { name: 'Pflicht', claim: 'Die Prüfpflicht ist erfüllt.', short: 'Prüfung, Kranbuch und Fristen.' },
    { name: 'Pflege', claim: 'Der Kran wird gepflegt.', short: 'Dazu Wartung und feste Reaktionszeit.' },
    { name: 'Rundum', claim: 'Wir sorgen dafür, dass er läuft.', short: 'Dazu Teile, Reparaturen und Ersatz-Hebezeug.' },
  ],
  rows: [
    { label: 'Prüfung nach Herstellerangaben, mit Bericht', from: 0 },
    { label: 'Kranbuch nachgeführt', from: 0 },
    { label: 'Wir melden uns, wenn eine Frist kommt', from: 0 },
    { label: 'Wartung nach Herstellervorgabe', from: 1 },
    { label: 'Feste Reaktionszeit bei Ausfall', from: 1 },
    { label: 'Teile und Reparaturen inbegriffen', from: 2 },
    { label: 'Ersatz-Hebezeug, wenn der Kran ausfällt', from: 2 },
  ],
  single: {
    name: 'Auf Abruf',
    claim: 'Sie rufen an, wir kommen.',
    short: 'Jede Leistung einzeln, nach Aufwand.',
    title: 'Lieber einzeln?',
    text: 'Jede Leistung gibt es auch auf Abruf: Sie rufen an, wir kommen und verrechnen nach Aufwand.',
  },
  price: 'Den Jahrespreis rechnen wir je Kran – nach Tragkraft, Alter und Nutzung. Sie erhalten eine Offerte.',
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
    {
      q: 'Was ändert sich mit der neuen EU-Maschinenverordnung?',
      a: 'Sie gilt in der EU ab dem 20. Januar 2027; die Schweiz passt ihre Maschinenverordnung an. Wer eine Maschine wesentlich verändert, braucht saubere Unterlagen.',
    },
  ],
  related: [
    { href: '/krantechnik/industriekrane', label: 'Industriekrane', text: 'Wenn ein neuer Kran die bessere Lösung ist.' },
    { href: '/sonderloesungen', label: 'Sonderlösungen', text: 'Konstruktion, Berechnung und Dokumentation für Umbauten.' },
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
export const krantechnikPages = [kranservice, industriekrane, haefen, heukrananlagen, modernisierung];

// Die Navigation (site.areas) und diese Seiten müssen dieselben Pfade nennen.
const nav = site.areas.find((a) => a.id === 'krantechnik')!.children.map((c) => c.href).join();
if (nav !== krantechnikPages.map((p) => p.path).join()) throw new Error('Krantechnik: Navigation und Seiten nennen andere Pfade.');
