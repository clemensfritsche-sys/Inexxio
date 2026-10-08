/**
 * Krane – Bereichsseite und drei Unterseiten: Kranservice (drei Stufen bis INEXXIO 365),
 * Krananlagen (Industrie, Häfen und Werften – Testnotizen #1200/#1201) und Heukrananlagen.
 * Welche Versprechen wo gelten, steht je Seite in `promises` (content/promises.ts). «HS» ist
 * kein Produktname mehr; Besitzer bestehender HS-Anlagen finden den Hinweis im Text, in den
 * FAQ und auf der Übergabe-Seite.
 */
import { inquiry } from '../config/inquiry.mjs';
import { sharedFaq } from './uebergabe';
import { industries, promiseFaq } from './promises';
import type { AreaPage, Step, SubPage } from './types';

const anfrage = (label: string) => ({ label, href: '#anfrage' });

/** Dieselbe Antwort wie auf Startseite und Übergabe (#1127). */
const faqHsCare = sharedFaq.whoCares;
const faqSpeed = sharedFaq.speed;
const faqOtherMakes = sharedFaq.otherMakes;
const ratgeberPruefung = { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Wer muss wann was prüfen?', kind: 'ratgeber' as const };
const ratgeberHeukran = { href: '/ratgeber/heukrananlage-planen', label: 'Neue Heukrananlage planen', text: 'Bauformen, Platzbedarf, Ablauf.', kind: 'ratgeber' as const };

/* ------------------------------------------------------------------ Bereich */
export const krane: AreaPage = {
  id: 'krane',
  path: '/krane',
  title: 'Krane: Service und Anlagen',
  description:
    'Kranservice mit Gratis-Erstservice und INEXXIO 365, neue Krananlagen, Heukrananlagen und Bootslifte mit Zufriedenheitsgarantie. Aus Tuttwil-Wängi TG.',
  hero: {
    eyebrow: 'Krane',
    h1: 'Krane bauen, betreuen und am Laufen ==halten==',
    lead:
      'Wir prüfen, warten und reparieren Krane aller Marken – der erste Service ist gratis. Mit INEXXIO 365 läuft Ihr Kran, oder Sie zahlen nicht. Und wir bauen neue Anlagen: Krane entstehen bei uns seit {{history.cranesSince}}.',
    photo: 'heukran-einsatz',
    primary: anfrage('Anfrage stellen'),
  },
  summary:
    '{{brand.full}} prüft, wartet, repariert und modernisiert Krane aller Marken: Brücken-, Hänge- und Schwenkkrane in Industrie und Gewerbe, Boots- und Mastkrane und Bootslifte in Häfen und Werften sowie Heukrananlagen. Der erste Kranservice ist gratis; mit INEXXIO 365 sind Prüfung, Wartung, Ersatzteile und Reparaturen zur fixen Monatsrate inklusive. Neue Anlagen bauen wir nach Mass – sind Sie nicht zufrieden, zahlen Sie nur die Hälfte. Die Werkstatt steht in Tuttwil-Wängi TG; im Einsatz sind wir {{area.summary}}.',
  steps: [
    { title: 'Anfrage', text: 'Sie schildern Ihr Anliegen – per Formular oder am Telefon. Ein Foto vom Typenschild hilft.' },
    { title: 'Abklärung', text: 'Wir klären vor Ort oder am Telefon, was es braucht. Sie erhalten einen Fixpreis.' },
    { title: 'Umsetzung', text: 'Wir bauen, montieren, prüfen oder reparieren – mit den nötigen Teilen im Fahrzeug.' },
    { title: 'Bericht', text: 'Sie erhalten einen Bericht zu jeder Arbeit; der Eintrag gehört ins Kranbuch.' },
  ],
  promises: ['erstservice', 'garantie', 'inexxio365'],
  faq: [
    promiseFaq.inexxio365,
    promiseFaq.erstservice,
    promiseFaq.garantie,
    sharedFaq.newCranes,
    faqHsCare,
    faqOtherMakes,
    faqSpeed,
  ],
  service: { name: 'Krane', serviceType: 'Bau, Prüfung, Wartung und Reparatur von Krananlagen' },
  keywords: ['Kranservice Schweiz', 'Krananlagen', 'Kranbau Thurgau', 'Kranprüfung'],
};

/** Das Hafenjahr – wann wir was tun (Modul der Krananlagen-Seite). */
export const harbourYear = {
  title: 'Das Hafenjahr',
  lead: 'Ein Bootskran arbeitet in Wellen. Wir richten den Service danach aus.',
  seasons: [
    { title: 'Vor dem Einwassern', when: 'Winter und Frühling', text: 'Prüfung und Wartung, Kranbuch nachführen, Mängel beheben – damit Kran und Lift am ersten Tag der Saison laufen.' },
    { title: 'In der Saison', when: 'Frühling bis Herbst', text: 'Fällt etwas aus, rufen Sie direkt an. Mit INEXXIO 365 ist jeder Tag, an dem der Kran steht, gratis.' },
    { title: 'Nach dem Auswassern', when: 'Herbst', text: 'Zustand aufnehmen, Reparaturen und neue Anlagen über den Winter planen.' },
  ],
};

/* ------------------------------------------------------------------ Heukrananlagen */
export const heukrananlagen: SubPage = {
  area: 'krane',
  path: '/krane/heukrananlagen',
  crumb: 'Heukrananlagen',
  title: 'Heukrananlagen nach Mass',
  description:
    'Heukran kaufen oder umbauen: Heukrananlagen nach Mass für Heu, Silage, Hackschnitzel, Kompost und Biogas – dazu Service und Saison-Check. Anfragen.',
  hero: {
    eyebrow: 'Krane · Heukrananlagen',
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
  promises: ['erstservice', 'garantie'],
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
      a: 'Das hängt von Bauform, Spannweite, Hubhöhe und Gebäude ab. Nach der Besichtigung erhalten Sie einen Fixpreis.',
    },
    promiseFaq.garantie,
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
    { href: '/krane/kranservice', label: 'Kranservice', text: 'Der erste Service ist gratis.' },
    { href: '/krane/krananlagen', label: 'Krananlagen', text: 'Industrie-, Hafen- und Bootskrane nach Mass.' },
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
      { title: 'Konzept und Offerte', text: 'Sie erhalten einen Vorschlag zu Bauform, Spannweite und Hubhöhe – mit Fixpreis.' },
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

/* ------------------------------------------------------------------ Krananlagen */
/**
 * Krananlagen (Testnotizen #1200/#1201): Industrie- und Hafenkrane sind Typen DERSELBEN
 * Leistung – neue Anlagen nach Mass und Service für bestehende. Heukrananlagen haben ihre
 * eigene Seite, weil sie einen eigenen Markt haben.
 */
export const krananlagen: SubPage = {
  area: 'krane',
  path: '/krane/krananlagen',
  crumb: 'Krananlagen',
  title: 'Krananlagen nach Mass',
  description:
    'Brücken-, Hänge- und Schwenkkrane, Boots- und Mastkrane, Bootslifte: neu nach Mass und mit Service. Erster Service gratis, INEXXIO 365 zur Monatsrate.',
  hero: {
    eyebrow: 'Krane · Krananlagen',
    h1: 'Krananlagen, die Ihren Betrieb ==laufen== lassen',
    lead:
      'Brücken-, Hänge- und Schwenkkrane in Industrie und Gewerbe, Boots- und Mastkrane und Bootslifte am Hafen. Wir bauen neue Anlagen nach Mass und prüfen, warten und reparieren bestehende – der erste Service ist gratis.',
    photo: 'reparatur-vor-ort',
    primary: anfrage('Kran anfragen'),
  },
  summary:
    '{{brand.full}} baut Krananlagen nach Mass und prüft, wartet und repariert Krane aller Marken: Brücken-, Hänge-, Schwenk- und Drehkrane in Industrie und Gewerbe, Boots- und Mastkrane und Bootslifte für Häfen, Clubs und Werften. Der erste Service ist gratis, mit INEXXIO 365 läuft der Kran zur fixen Monatsrate, oder Sie zahlen nicht. Steht ein Kran still, rufen Sie direkt an.',
  glance: {
    forWhom: 'Industrie und Gewerbe – Recycling und Entsorgung, Sägewerke und Holzhandel, Stahlhandel und Metallbau, Betonwerke, Werkhöfe – sowie Häfen, Clubs und Werften.',
    what: 'Neue Krananlagen nach Mass. Prüfung, Wartung, Fehlersuche und Reparatur – auf Abruf, im Service-Vertrag oder mit INEXXIO 365.',
    deliverables: 'Einen Kran, der läuft, ein nachgeführtes Kranbuch und einen Rapport mit Ursache, Arbeiten und Teilen.',
  },
  promises: ['erstservice', 'garantie', 'inexxio365'],
  scope: {
    title: 'Welche Krane wir bauen und betreuen',
    lead: 'Neue Anlagen nach Mass – und Service für bestehende, auch von anderen Herstellern.',
    items: [
      { title: 'Brückenkrane', text: 'Ein- und Zweiträger-Brückenkrane in Produktions- und Lagerhallen.' },
      { title: 'Hängekrane', text: 'Unter der Hallendecke aufgehängt – für Hallen ohne Kranbahnstützen.' },
      { title: 'Schwenk- und Drehkrane', text: 'Säulen- und Wandschwenkkrane am Arbeitsplatz, Drehkrane im Werkhof.' },
      { title: 'Boots- und Mastkrane', text: 'Am Steg oder auf dem Hafenplatz – sicher auch für Mitglieder, die selten kranen.' },
      { title: 'Bootslifte', text: 'Nach Mass gebaut – passend zu Steg, Boot und Platz am Ufer.' },
      { title: 'Hubwerk, Elektrik, Tragwerk', text: 'Seil- und Kettenzüge, Bremsen, Antriebe, Steuerung, Stahlbau und Kranbahn.' },
    ],
  },
  faq: [
    promiseFaq.inexxio365,
    faqOtherMakes,
    {
      q: 'Was tue ich, wenn der Kran stehen bleibt?',
      a: 'Den Kran ausser Betrieb nehmen und sichern, die Last – wenn möglich – sicher absetzen und uns anrufen: {{phone.link}}. Nicht unter Last weiterarbeiten.',
    },
    {
      q: 'Bauen Sie neue Krane und Bootslifte?',
      a: 'Ja – abgestimmt auf Halle, Steg, Last und Arbeitsweise. Sind Sie nicht zufrieden, zahlen Sie nur die Hälfte. Mit INEXXIO 365 auch ohne Kauf, zur Monatsrate.',
    },
    {
      q: 'Wann ist der beste Zeitpunkt für die Prüfung eines Bootskrans?',
      a: 'Vor dem Einwassern im Frühling. Dann bleibt Zeit für Reparaturen, bevor alle Boote auf einmal ins Wasser wollen.',
    },
    promiseFaq.secondOpinion,
  ],
  related: [
    { href: '/krane/kranservice', label: 'Kranservice', text: 'Drei Stufen bis INEXXIO 365.' },
    { href: '/sonderloesungen#krane', label: 'Sonderlösungen', text: 'Krane, die es nicht zu kaufen gibt.' },
    ratgeberPruefung,
  ],
  service: { name: 'Krananlagen', serviceType: 'Bau, Prüfung, Wartung und Reparatur von Industrie- und Hafenkranen' },
  keywords: ['Brückenkran', 'Hallenkran Wartung', 'Schwenkkran', 'Bootslift', 'Bootskran', 'Mastkran', 'Kranreparatur'],
};

/** Module der Krananlagen-Seite: INEXXIO 365, Service (Anker #service), Foto-Hinweis. */
export const krananlagenModules = {
  inexxio365: {
    title: 'Ihr Kran muss laufen? INEXXIO 365.',
    text: `${industries} Prüfung, Wartung, Ersatzteile und Reparaturen sind inklusive, zur fixen Monatsrate – und jeder Tag, an dem der Kran steht, ist gratis.`,
    link: { href: '/krane/kranservice#inexxio-365', label: 'So funktioniert INEXXIO 365' },
  },
  service: {
    title: 'Service und Reparatur',
    text: 'Wir suchen die Ursache und reparieren vor Ort – unabhängig vom Hersteller. Steht ein Kran still, rufen Sie direkt an.',
  },
  photoHint: {
    title: 'Foto vom Typenschild oder vom Schaden mitschicken',
    text: `Mit einem Foto wissen wir vor dem Einsatz, welcher Kran es ist, und können den Einsatz besser vorbereiten. Im Formular können Sie bis zu ${inquiry.photos.max} Fotos anhängen.`,
  },
};

/* ------------------------------------------------------------------ Kranservice */
/**
 * EINE Seite für den Kranservice: die drei Stufen (Auf Abruf · Basis · INEXXIO 365),
 * die zwei Wege zu INEXXIO 365, was wir prüfen und die Prüfpflicht. Keine Preise, keine
 * Kranklassen – vor jeder Arbeit gibt es einen Fixpreis.
 */
export const kranservice: SubPage = {
  area: 'krane',
  path: '/krane/kranservice',
  crumb: 'Kranservice',
  title: 'Kranservice und Kranprüfung',
  description:
    'Kranservice in drei Stufen: erster Service gratis, Service-Vertrag Basis oder INEXXIO 365 – Ihr Kran läuft, oder Sie zahlen nicht. Fixpreis vorab.',
  hero: {
    eyebrow: 'Krane · Kranservice',
    h1: 'Ihr Kran läuft – oder Sie ==zahlen nicht==',
    lead:
      'Testen Sie uns: Der erste Kranservice ist gratis. Danach wählen Sie, wie viel wir Ihnen abnehmen – bis zu INEXXIO 365, mit Prüfung, Wartung, Ersatzteilen und Reparaturen zur fixen Monatsrate.',
    photo: 'pruefung-hallenkran',
    primary: anfrage('Kranservice anfragen'),
  },
  summary:
    '{{brand.full}} prüft, wartet und repariert Krane aller Marken: Brücken-, Hänge-, Schwenk- und Drehkrane, Boots- und Mastkrane und Heukrane. Drei Stufen: Auf Abruf (der erste Service ist gratis), Service-Vertrag Basis (Prüfung, Wartung und Kranbuch) und INEXXIO 365 (alles inklusive zur fixen Monatsrate, jeder Tag Stillstand ist gratis). Fixpreis vor jeder Arbeit, keine Mindestlaufzeit.',
  glance: {
    forWhom: 'Betriebe mit einem oder mehreren Kranen: Industrie und Gewerbe, Häfen, Clubs und Werften, Landwirtschaft.',
    what: 'Prüfung nach Herstellerangaben, Wartung und Reparatur durch Kranfachleute – vom einzelnen Einsatz bis INEXXIO 365.',
    deliverables: 'Einen Kran, der läuft, ein nachgeführtes Kranbuch und einen Fixpreis vor jeder Arbeit.',
  },
  promises: ['erstservice', 'inexxio365'],
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
    promiseFaq.erstservice,
    promiseFaq.inexxio365,
    {
      q: 'Welche Stufe passt zu mir?',
      a: 'Auf Abruf, wenn Sie selten etwas brauchen. Basis, wenn Prüfung, Wartung und Kranbuch sicher erledigt sein sollen. INEXXIO 365, wenn Ihr Betrieb vom Kran abhängt.',
    },
    promiseFaq.price,
    promiseFaq.binding,
    promiseFaq.secondOpinion,
    {
      q: 'Wie oft muss ich meinen Hallenkran prüfen lassen?',
      a: 'Regelmässig, nach den Angaben des Herstellers – in der Praxis meist einmal im Jahr. Massgebend sind die Betriebsanleitung und die Vorgaben der Suva.',
    },
    faqOtherMakes,
    {
      q: 'Machen Sie auch die Kontrolle durch den Kranexperten?',
      a: 'Nein. Die periodische Kontrolle von Fahrzeug- und Turmdrehkranen macht ein von der Suva anerkannter Kranexperte. Wir übernehmen die Überprüfung durch Kranfachleute und die Wartung. Den Unterschied erklärt unser Ratgeber [Kranprüfung in der Schweiz](/ratgeber/kranpruefung-schweiz#kranfachmann-oder-kranexperte).',
    },
  ],
  related: [
    { href: '/krane/krananlagen', label: 'Krananlagen', text: 'Wenn ein neuer Kran die bessere Lösung ist.' },
    { href: '/krane/heukrananlagen', label: 'Heukrananlagen', text: 'Saison-Check vor dem ersten Schnitt.' },
    ratgeberPruefung,
  ],
  service: { name: 'Kranservice', serviceType: 'Kranprüfung, Kranwartung und Kranreparatur' },
  keywords: ['Kranservice', 'Kranprüfung', 'Kranwartung', 'INEXXIO 365', 'Kranbuch'],
};

/**
 * Die drei Stufen des Kranservice. Jede enthält die vorherige – darum nennt jede nur, was
 * dazukommt. Kein Betrag, keine Kranklasse: den Fixpreis erhalten Sie mit der Offerte.
 */
export const serviceTiers = {
  title: 'Drei Stufen – Sie wählen, wie viel wir übernehmen',
  lead: 'Jede Stufe enthält die vorherige.',
  tiers: [
    { name: 'Auf Abruf', claim: 'Sie rufen an, wir kommen.', items: ['Service, Wartung, Prüfung oder Reparatur, wenn Sie sie brauchen', 'Der erste Service ist gratis'] },
    { name: 'Service-Vertrag Basis', claim: 'Prüfung und Wartung sind erledigt.', items: ['Prüfung nach Herstellerangaben, mit Bericht', 'Wartung nach Herstellervorgabe', 'Kranbuch nachgeführt, Fristen im Blick'] },
    { name: 'INEXXIO 365', claim: 'Ihr Kran läuft – oder Sie zahlen nicht.', items: ['Ersatzteile, Verschleissteile und Reparaturen inklusive', 'Fixe Monatsrate', 'Jeder Tag Stillstand ist gratis'], featured: true },
  ],
};

/** INEXXIO 365 im Detail – zwei Wege, für wen (Anker #inexxio-365 auf dem Kranservice). */
export const inexxio365 = {
  eyebrow: 'INEXXIO 365',
  title: 'Zwei Wege zu einem Kran, der läuft',
  lead: 'Prüfung, Wartung, Ersatzteile und Reparaturen inklusive, zur fixen Monatsrate. Jeder Tag, an dem der Kran steht, ist gratis. Keine Mindestlaufzeit.',
  ways: [
    { title: 'Ihr bestehender Kran', text: 'Auch von anderen Herstellern: Wir schauen ihn an und übernehmen ihn rundum.' },
    { title: 'Ein neuer Kran', text: 'Ohne Kauf, zur Monatsrate. Wir bauen ihn nach Mass und sorgen dafür, dass er läuft.' },
  ],
  industries,
  cta: 'INEXXIO 365 anfragen',
};

/** Alle Unterseiten des Bereichs, in der Reihenfolge der Navigation. */
export const kranePages = [kranservice, krananlagen, heukrananlagen];
