/**
 * Krantechnik – Bereichsseite und drei Unterseiten: Krane nach Mass (Sonderkrane,
 * Industriekrane, Boots- und Mastkrane, Bootslifte, Kran aus Markenkomponenten), Kranservice
 * (vier Stufen bis INEXXIO 365, mit Modernisierung) und Heukrananlagen.
 * Wir bewerben Lösungen nach Mass, keine Katalogkrane. Welche Versprechen wo gelten, steht je
 * Seite in `promises` (content/promises.ts).
 */
import { inquiry } from '../config/inquiry.mjs';
import { sharedFaq } from './uebergabe';
import { promiseFaq } from './promises';
import type { AreaPage, Step, SubPage } from './types';

const anfrage = (label: string) => ({ label, href: '#anfrage' });

const faqHsCare = sharedFaq.whoCares;
const faqSpeed = sharedFaq.speed;
const faqOtherMakes = sharedFaq.otherMakes;
const ratgeberPruefung = { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Wer muss wann was prüfen?', kind: 'ratgeber' as const };
const ratgeberHeukran = { href: '/ratgeber/heukrananlage-planen', label: 'Neue Heukrananlage planen', text: 'Bauformen, Platzbedarf, Ablauf.', kind: 'ratgeber' as const };

/* ------------------------------------------------------------------ Bereich */
export const krantechnik: AreaPage = {
  id: 'krantechnik',
  path: '/krantechnik',
  title: 'Krantechnik: Krane nach Mass',
  description:
    'Krane nach Mass, Kranservice und Heukrananlagen – mit Zufriedenheitsgarantie und INEXXIO 365. Die erste Inspektion ist gratis. Aus Tuttwil-Wängi TG.',
  hero: {
    eyebrow: 'Krantechnik',
    h1: 'Krane, die zu Ihrem Betrieb ==passen== – und laufen',
    lead:
      'Wir bauen Krane nach Mass, betreuen bestehende Krane und modernisieren, was sich lohnt. Lernen Sie uns kennen: Die erste Inspektion ist gratis. Mit INEXXIO 365 ist Ihr Kran einsatzbereit – Ausfälle übernehmen wir.',
    photo: 'heukran-einsatz',
    primary: anfrage('Anfrage stellen'),
  },
  summary:
    '{{brand.full}} plant, baut und betreut Krane: Sonderkrane und Industriekrane für besondere Hallen und Abläufe, Boots- und Mastkrane und Bootslifte für Häfen, Clubs und Werften, Heukrananlagen – dazu Kranservice und Modernisierung. Die erste Inspektion ist gratis. Mit INEXXIO 365 zahlen Sie eine fixe Monatsrate für die Einsatzbereitschaft – Ausfälle, Reparaturen und Ersatzteile übernehmen wir. Was Sie bei uns bekommen, deckt die Zufriedenheitsgarantie: Nicht zufrieden, übernehmen wir 50 %. Die Werkstatt steht in Tuttwil-Wängi TG; im Einsatz sind wir {{area.summary}}.',
  steps: [
    { title: 'Anfrage', text: 'Sie schildern Ihr Anliegen – per Formular oder am Telefon. Ein Foto vom Typenschild hilft.' },
    { title: 'Abklärung', text: 'Wir klären vor Ort oder am Telefon, was es braucht. Sie erhalten einen Fixpreis.' },
    { title: 'Umsetzung', text: 'Wir bauen, montieren, prüfen oder reparieren – die nötigen Teile sind dabei.' },
    { title: 'Protokoll', text: 'Sie erhalten zu jeder Arbeit ein Protokoll. Der Eintrag gehört ins Kranbuch.' },
  ],
  promises: ['garantie', 'inexxio365', 'erstservice'],
  faq: [
    promiseFaq.garantie,
    promiseFaq.inexxio365,
    promiseFaq.erstservice,
    sharedFaq.newCranes,
    faqHsCare,
    faqOtherMakes,
    promiseFaq.secondOpinion,
    faqSpeed,
  ],
  service: { name: 'Krantechnik', serviceType: 'Bau, Prüfung, Wartung, Modernisierung und Reparatur von Kranen' },
  keywords: ['Kran nach Mass', 'Kranservice Schweiz', 'Sonderkran', 'Kranbau Thurgau', 'Kranprüfung'],
};

/* ------------------------------------------------------------------ Krane nach Mass */
export const kraneNachMass: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/krane-nach-mass',
  crumb: 'Krane nach Mass',
  title: 'Krane nach Mass',
  description:
    'Sonderkrane, Industriekrane, Boots- und Mastkrane, Bootslifte: Krane, die zu Halle, Hafen und Ablauf passen. Kauf mit Garantie oder zur Monatsrate.',
  hero: {
    eyebrow: 'Krantechnik · Krane nach Mass',
    h1: 'Krane, die zu Ihrer Halle ==passen== – nicht umgekehrt',
    lead:
      'Wir planen den Kran nach Ihrem Gebäude, Ihrer Last und Ihrem Ablauf. Wir bauen, montieren und betreuen ihn – auch am Steg. Sie kaufen mit Garantie oder nutzen ihn ohne Kauf, zur Monatsrate.',
    photo: 'reparatur-vor-ort',
    primary: anfrage('Kran anfragen'),
  },
  summary:
    '{{brand.full}} baut Krane nach Mass: Sonderkrane, Industriekrane für besondere Hallen und Abläufe, Boots- und Mastkrane und Bootslifte für Häfen, Clubs und Werften. Als Standard dient ein Kran nach Mass aus Markenkomponenten: Hubwerk und Fahrwerke von Markenherstellern, Planung, Montage und Service von uns. Neue Krane gibt es zum Kauf – mit Zufriedenheitsgarantie: nicht zufrieden, übernehmen wir 50 % – oder ohne Kauf, zur Monatsrate mit INEXXIO 365.',
  glance: {
    forWhom: 'Recycling und Entsorgung, Sägewerke und Holzhandel, Stahlhandel und Metallbau, Betonwerke, Häfen und Clubs – überall, wo der Katalogkran nicht passt.',
    what: 'Planung, Konstruktion, Fertigung und Montage – danach Prüfung, Wartung und Reparatur aus derselben Hand.',
    deliverables: 'Einen Kran, der zu Ihrem Betrieb passt, mit Dokumentation und Kranbuch – und einen Ansprechpartner, der ihn kennt.',
  },
  promises: ['garantie', 'inexxio365', 'erstservice'],
  scope: {
    title: 'Was zu jedem Kran gehört',
    lead: 'Gleich, ob Sonderkran, Hallenkran oder Bootslift.',
    items: [
      { title: 'Planung vor Ort', text: 'Wir messen Gebäude, Steg und Last auf und hören zu, wie Sie arbeiten.' },
      { title: 'Konstruktion und Berechnung', text: 'Tragwerk, Kranbahn und Anbindung – nachvollziehbar dokumentiert.' },
      { title: 'Fertigung und Montage', text: 'Stahlbau in der eigenen Werkstatt, Montage und Inbetriebnahme bei Ihnen.' },
      { title: 'Abnahme und Kranbuch', text: 'Erste Prüfung, Einweisung in die Bedienung, Kranbuch angelegt.' },
      { title: 'Service aus einer Hand', text: 'Prüfung, Wartung und Reparatur von dem, der den Kran gebaut hat.' },
      { title: 'Ersatzteile', text: 'Markenkomponenten, die man beschaffen kann – und Stahlteile, die wir selbst fertigen.' },
    ],
  },
  faq: [
    {
      q: 'Bauen Sie auch Standardkrane?',
      a: 'Ja – als Kran nach Mass aus Markenkomponenten. Hubwerk und Fahrwerke kommen von Markenherstellern, Planung, Montage und Service von uns.',
    },
    {
      q: 'Muss ich den Kran kaufen?',
      a: 'Nein. Sie kaufen ihn mit Garantie – oder nutzen ihn ohne Kauf, zur Monatsrate mit INEXXIO 365.',
    },
    promiseFaq.garantie,
    promiseFaq.inexxio365,
    {
      q: 'Bauen Sie auch Bootslifte und betreuen bestehende?',
      a: 'Ja. Wir bauen neue Bootslifte nach Mass und prüfen, warten und reparieren bestehende – auch von anderen Herstellern.',
    },
    {
      q: 'Wann ist der beste Zeitpunkt für die Prüfung eines Bootskrans?',
      a: 'Vor dem Einwassern im Frühling. Dann bleibt Zeit für Reparaturen, bevor alle Boote auf einmal ins Wasser wollen.',
    },
    promiseFaq.price,
    promiseFaq.secondOpinion,
  ],
  related: [
    { href: '/krantechnik/kranservice', label: 'Kranservice', text: 'Vier Stufen bis INEXXIO 365.' },
    { href: '/krantechnik/heukrananlagen', label: 'Heukrananlagen', text: 'Betreuen, umbauen, neu planen.' },
    ratgeberPruefung,
  ],
  service: { name: 'Krane nach Mass', serviceType: 'Planung, Bau und Montage von Kranen und Bootsliften nach Mass' },
  keywords: ['Kran nach Mass', 'Sonderkran', 'Industriekran', 'Bootslift', 'Bootskran', 'Mastkran', 'Brückenkran'],
};

/** Die vier Arten Kran nach Mass – je ein Abschnitt mit eigenem Anker (Seite Krane nach Mass). */
export const craneKinds = [
  {
    id: 'sonderkrane',
    eyebrow: 'Sonderkrane',
    title: 'Wo kein Katalogkran passt',
    text: 'Ungewöhnliche Last, enge Halle, besondere Bewegung: Wir konstruieren den Kran für genau diese Aufgabe.',
    photo: 'arbeit-werkstatt',
    items: ['An das Gebäude angepasst: Fahrbahn, Stützen, Spannweite', 'Ausleger, Hebezeuge und Lastaufnahmen nach Mass', 'Umbau und Erweiterung bestehender Anlagen'],
  },
  {
    id: 'industriekrane',
    eyebrow: 'Industriekrane',
    title: 'Für besondere Hallen und Abläufe',
    text: 'Brücken-, Hänge- und Schwenkkrane, abgestimmt auf Halle, Last und Takt – damit der Kran den Ablauf trägt, nicht bremst.',
    photo: 'pruefung-hallenkran',
    items: ['Ein- und Zweiträger-Brückenkrane', 'Hängekrane für Hallen ohne Kranbahnstützen', 'Säulen- und Wandschwenkkrane am Arbeitsplatz'],
  },
  {
    id: 'hafen',
    eyebrow: 'Häfen, Clubs und Werften',
    title: 'Boots- und Mastkrane, Bootslifte',
    text: 'Für Hafenmeister, Clubs und Werften am Bodensee und an Schweizer Seen: neue Bootslifte und Krane nach Mass, Service für bestehende. Die erste Inspektion ist gratis; für Clubs mit eigenem Kran gibt es INEXXIO 365.',
    photo: 'hafen-bootskran',
    items: ['Bootslifte nach Mass – passend zu Steg, Boot und Ufer', 'Boots- und Mastkrane, sicher auch für Mitglieder, die selten kranen', 'Prüfung und Wartung vor dem Einwassern'],
  },
  {
    id: 'standard',
    eyebrow: 'Standardkran',
    title: 'Kran nach Mass aus Markenkomponenten',
    text: 'Hubwerk und Fahrwerke kommen von Markenherstellern. Wir planen, montieren und betreuen den Kran – Planung, Montage und Service aus einer Hand.',
    photo: 'reparatur-vor-ort',
    items: ['Bewährte Komponenten, Ersatzteile verfügbar', 'Planung und Montage passend zu Ihrer Halle', 'Service von dem, der ihn montiert hat'],
  },
];

/** Neue Krane: zwei Wege (Seite Krane nach Mass, Anker #wege). */
export const newCraneWays = {
  title: 'Kaufen – oder ohne Kauf nutzen',
  lead: 'Für jeden neuen Kran gilt: Fixpreis vor jeder Arbeit, keine Mindestlaufzeit.',
  ways: [
    { label: 'Kaufen mit Garantie', title: 'Sie kaufen den Kran.', text: 'Nicht zufrieden? Die Hälfte übernehmen wir.' },
    { label: 'INEXXIO 365', title: 'Ohne Kauf, zur Monatsrate.', text: 'Sie zahlen für die Einsatzbereitschaft – Ausfälle, Reparaturen und Ersatzteile übernehmen wir. Jeder Tag Stillstand ist gratis.' },
  ],
};

/** Das Hafenjahr – wann wir am Hafen was tun (Seite Krane nach Mass). */
export const harbourYear = {
  title: 'Das Hafenjahr',
  lead: 'Ein Bootskran arbeitet in Wellen. Wir richten den Service danach aus.',
  seasons: [
    { title: 'Vor dem Einwassern', when: 'Winter und Frühling', text: 'Prüfung und Wartung, Kranbuch nachführen, Mängel beheben – damit Kran und Lift am ersten Tag der Saison laufen.' },
    { title: 'In der Saison', when: 'Frühling bis Herbst', text: 'Fällt etwas aus, rufen Sie direkt an. Mit INEXXIO 365 übernehmen wir Ausfälle – jeder Tag Stillstand ist gratis.' },
    { title: 'Nach dem Auswassern', when: 'Herbst', text: 'Zustand aufnehmen, Reparaturen und neue Anlagen über den Winter planen.' },
  ],
};

/* ------------------------------------------------------------------ Kranservice */
/**
 * EINE Seite für den Kranservice: die vier Stufen (Auf Abruf · Basis · Plus · INEXXIO 365),
 * INEXXIO 365 mit seinen zwei Wegen, Modernisierung, was wir prüfen und die Prüfpflicht.
 * Keine Preise, keine Kranklassen – vor jeder Arbeit gibt es einen Fixpreis.
 */
export const kranservice: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/kranservice',
  crumb: 'Kranservice',
  title: 'Kranservice und INEXXIO 365',
  description:
    'Kranservice in vier Stufen: erste Inspektion gratis, Service-Vertrag Basis oder Plus, INEXXIO 365. Dazu Modernisierung. Fixpreis vorab.',
  hero: {
    eyebrow: 'Krantechnik · Kranservice',
    h1: 'Ihr Kran ist einsatzbereit. Ausfälle ==übernehmen wir==.',
    lead:
      'Lernen Sie uns kennen: Die erste Inspektion ist gratis. Danach wählen Sie, wie viel wir übernehmen – bis zu INEXXIO 365: eine fixe Monatsrate für die Einsatzbereitschaft, Ausfälle übernehmen wir.',
    photo: 'pruefung-hallenkran',
    primary: anfrage('Kranservice anfragen'),
  },
  summary:
    '{{brand.full}} prüft, wartet, repariert und modernisiert Krane: Brücken-, Hänge-, Schwenk- und Drehkrane, Boots- und Mastkrane und Heukrane. Vier Stufen: Auf Abruf (die erste Inspektion ist gratis), Service-Vertrag Basis (gesetzliche Prüfung, digitales Kranbuch, Erinnerung an Fristen), Service-Vertrag Plus (dazu Wartung, feste Reaktionszeit, fester Ansprechpartner) und INEXXIO 365 (dazu Teile und Reparaturen, Ersatz-Hebezeug und das Verfügbarkeitsversprechen). Fixpreis vor jeder Arbeit, keine Mindestlaufzeit.',
  glance: {
    forWhom: 'Recycling und Entsorgung, Sägewerke und Holzhandel, Stahlhandel und Metallbau, Betonwerke, Häfen und Clubs – und alle, deren Kran laufen muss.',
    what: 'Prüfung, Wartung, Reparatur und Modernisierung durch Kranfachleute – vom einzelnen Einsatz bis INEXXIO 365.',
    deliverables: 'Einen Kran, der einsatzbereit ist, ein nachgeführtes Kranbuch und einen Fixpreis vor jeder Arbeit.',
  },
  promises: ['garantie', 'inexxio365', 'erstservice'],
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
      a: 'Auf Abruf, wenn Sie selten etwas brauchen. Basis, wenn Prüfung und Kranbuch sicher erledigt sein sollen. Plus, wenn auch die Wartung geregelt sein soll. INEXXIO 365, wenn Ihr Betrieb vom Kran abhängt.',
    },
    promiseFaq.price,
    promiseFaq.binding,
    promiseFaq.secondOpinion,
    {
      q: 'Lohnt sich eine Modernisierung?',
      a: 'Oft ja: Ist der Stahlbau gut, bringen Funkfernsteuerung, Frequenzumrichter oder eine neue Überlastsicherung den Kran auf den Stand der Technik – ohne neuen Kran. Wir sagen Ihnen offen, wann ein neuer die bessere Lösung ist.',
    },
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
    { href: '/krantechnik/krane-nach-mass', label: 'Krane nach Mass', text: 'Wenn ein neuer Kran die bessere Lösung ist.' },
    { href: '/krantechnik/heukrananlagen', label: 'Heukrananlagen', text: 'Saison-Check vor dem ersten Schnitt.' },
    ratgeberPruefung,
  ],
  service: { name: 'Kranservice', serviceType: 'Kranprüfung, Kranwartung, Kranmodernisierung und Kranreparatur' },
  keywords: ['Kranservice', 'Kranprüfung', 'Kranwartung', 'Kranmodernisierung', 'INEXXIO 365', 'Kranbuch'],
};

/**
 * Die vier Stufen des Kranservice. Jede enthält die vorherige – darum nennt jede nur, was
 * dazukommt. Kein Betrag, keine Kranklasse: den Fixpreis erhalten Sie mit der Offerte.
 */
export const serviceTiers = {
  title: 'Vier Stufen – Sie wählen, wie viel wir übernehmen',
  lead: 'Jede Stufe enthält die vorherige.',
  tiers: [
    { name: 'Auf Abruf', claim: 'Einzeln bestellt, wenn Sie es brauchen.', items: ['Service, Wartung, Prüfung oder Reparatur', 'Die erste Inspektion ist gratis'] },
    { name: 'Service-Vertrag Basis', claim: 'Die Pflicht ist erledigt.', items: ['Gesetzliche Prüfung, mit Protokoll', 'Digitales Kranbuch', 'Erinnerung an Fristen'] },
    { name: 'Service-Vertrag Plus', claim: 'Der Kran ist gepflegt.', items: ['Wartung nach Herstellervorgabe', 'Feste Reaktionszeit', 'Fester Ansprechpartner'] },
    { name: 'INEXXIO 365', claim: 'Einsatzbereit. Ausfälle übernehmen wir.', items: ['Teile und Reparaturen inklusive', 'Ersatz-Hebezeug', 'Verfügbarkeitsversprechen: jeder Tag Stillstand ist gratis'], featured: true },
  ],
};

/** INEXXIO 365 im Detail – zwei Wege (Anker #inexxio-365 auf dem Kranservice). */
export const inexxio365 = {
  eyebrow: 'INEXXIO 365',
  title: 'Zwei Wege zu einem einsatzbereiten Kran',
  lead: 'Sie zahlen eine fixe Monatsrate für die Einsatzbereitschaft – nicht für Ausfallzeiten und Reparaturen. Prüfung, Wartung und Ersatzteile sind inklusive, jeder Tag Stillstand ist gratis. Keine Mindestlaufzeit.',
  ways: [
    { title: 'Ihr bestehender Kran', text: 'Nach einer Eintrittsprüfung übernehmen wir ihn rundum.' },
    { title: 'Ein neuer Kran', text: 'Ohne Kauf, zur Monatsrate. Wir bauen ihn nach Mass und halten ihn einsatzbereit.' },
  ],
  cta: 'INEXXIO 365 anfragen',
};

/** Modernisierung (Anker #modernisierung auf dem Kranservice) – gehört zum Service, mit Garantie. */
export const modernisation = {
  title: 'Modernisieren statt ersetzen',
  lead: 'Ist der Stahlbau gut, bringen wir die Technik auf den neuen Stand. Nicht zufrieden? Die Hälfte übernehmen wir.',
  items: [
    { title: 'Funkfernsteuerung', text: 'Bedienen mit Abstand zur Last – sicherer und mit Blick auf den ganzen Weg.' },
    { title: 'Frequenzumrichter', text: 'Sanft anfahren und bremsen: weniger Pendeln, weniger Verschleiss.' },
    { title: 'Überlastsicherung', text: 'Nachgerüstet oder erneuert – damit der Kran nicht mehr hebt, als er darf.' },
    { title: 'Steuerung und Elektrik', text: 'Neue Steuerung, Endschalter und Not-Halt nach heutigem Stand.' },
  ],
};

/** Foto-Hinweis (Kranservice): mit Typenschild bereitet sich der Einsatz besser vor. */
export const photoHint = {
  title: 'Foto vom Typenschild oder vom Schaden mitschicken',
  text: `Mit einem Foto wissen wir vor dem Einsatz, welcher Kran es ist. Im Formular können Sie bis zu ${inquiry.photos.max} Fotos anhängen.`,
};

/* ------------------------------------------------------------------ Heukrananlagen */
export const heukrananlagen: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/heukrananlagen',
  crumb: 'Heukrananlagen',
  title: 'Heukrananlagen: Service',
  description:
    'Heukrananlagen betreuen, umbauen und neu planen: Saison-Check, Reparatur und Ersatzteile – die erste Inspektion ist gratis. Neuanlagen auf Anfrage.',
  hero: {
    eyebrow: 'Krantechnik · Heukrananlagen',
    h1: 'Ihre Heukrananlage läuft, wenn die ==Ernte== beginnt',
    lead:
      'Seit {{history.cranesSince}} bauen wir in Tuttwil Heukrane. Wir betreuen bestehende Anlagen – die erste Inspektion ist gratis – und planen neue nach Mass, wenn Sie eine brauchen.',
    photo: 'heukran-einsatz',
    primary: anfrage('Service anfragen'),
  },
  summary:
    '{{brand.full}} betreut Heukrananlagen: Saison-Check, Wartung, Reparatur, Ersatzteile und Modernisierung – auch für alle bestehenden HS-Krananlagen. Die erste Inspektion ist gratis. Neue Anlagen planen und bauen wir auf Anfrage nach Mass: Einschienenkrane, Brückenkrane, hydraulische Drehkrane und Anlagen, die an das Gebäude angepasst sind. Nicht zufrieden, übernehmen wir 50 %. Die Werkstatt steht in Tuttwil-Wängi TG.',
  glance: {
    forWhom: 'Landwirtschaftsbetriebe für Heu, Stroh, Silage und Mist – und alle, die lose Güter mit dem Greifer umschlagen: Hackschnitzelheizungen, Sägewerke, Kompost- und Biogasanlagen, Werkhöfe.',
    what: 'Saison-Check, Wartung, Reparatur und Modernisierung bestehender Anlagen. Neue Anlagen: Besichtigung, Konzept, Fertigung, Montage.',
    deliverables: 'Eine Anlage, die zur Ernte läuft – und einen Ansprechpartner, der sie kennt.',
  },
  promises: ['garantie', 'inexxio365', 'erstservice'],
  scope: {
    title: 'Was wir für Ihre Heukrananlage tun',
    lead: 'Zuerst für die Anlage, die Sie haben.',
    items: [
      { title: 'Saison-Check', text: 'Kranbahn, Fahrwerke, Seil, Greifer, Hydraulik und Elektrik prüfen, bevor die Ernte beginnt.' },
      { title: 'Reparatur', text: 'Fehlersuche und Reparatur vor Ort.' },
      { title: 'Ersatzteile für HS-Anlagen', text: 'An Lager oder für Sie neu gefertigt – auch für ältere Anlagen.' },
      { title: 'Modernisierung', text: 'Funkfernsteuerung, Frequenzumrichter und neue Steuerung für bestehende Anlagen.' },
      { title: 'Umbau und Erweiterung', text: 'Längere Fahrbahn, neuer Greifer, zusätzlicher Bereich – die Anlage wächst mit dem Betrieb.' },
      { title: 'Neuanlage nach Mass', text: 'Bauform, Spannweite und Hubhöhe passend zu Scheune, Heustock und Arbeitsweise – auf Anfrage.' },
    ],
  },
  faq: [
    promiseFaq.erstservice,
    {
      q: 'Wann ist der beste Zeitpunkt für den Service?',
      a: 'Vor der Saison, zwischen März und Mai. Dann bleibt Zeit für Reparaturen, ohne dass das Wetter drängt.',
    },
    faqHsCare,
    sharedFaq.parts,
    {
      q: 'Was kostet eine neue Heukrananlage?',
      a: 'Das hängt von Bauform, Spannweite, Hubhöhe und Gebäude ab. Nach der Besichtigung erhalten Sie einen Fixpreis.',
    },
    promiseFaq.garantie,
    {
      q: 'Bauen Sie auch Anlagen im Ausland?',
      a: 'Ja. Krananlagen planen und bauen wir {{area.summary}} – fragen Sie an.',
    },
  ],
  related: [
    { href: '/krantechnik/kranservice', label: 'Kranservice', text: 'Die erste Inspektion ist gratis.' },
    { href: '/krantechnik/krane-nach-mass', label: 'Krane nach Mass', text: 'Sonderkrane, Industriekrane, Bootslifte.' },
    ratgeberHeukran,
  ],
  service: { name: 'Heukrananlagen', serviceType: 'Service, Umbau und Bau von Heukrananlagen' },
  keywords: ['Heukran', 'Heukrananlage', 'Heukran Service', 'Heukran kaufen', 'Heudrehkran', 'Hackschnitzelkran'],
};

/** Module der Heukran-Seite. */
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
    title: 'Sie haben eine HS-Krananlage? Sie wird weiter betreut.',
    text: 'Die Anlagen, die seit {{history.cranesSince}} in Tuttwil entstanden sind, betreuen wir weiter. Service, Reparatur und Ersatzteile – mit demselben Wissen. Mehr dazu unter [Aus HS Steiner wird {{brand.name}}](/ueber-uns#uebergabe).',
  },
  season: {
    title: 'Saison-Check vor dem ersten Schnitt',
    text: 'Ein Heukran steht über den Winter still und muss beim ersten Schnitt sofort laufen. Beim Saison-Check zwischen März und Mai prüfen wir die ganze Anlage – und ersetzen, was bis zur Ernte nicht hält.',
    checks: ['Kranbahn und Endanschläge', 'Fahrwerke und Laufräder', 'Seil oder Kette, Haken', 'Greifer: Zinken, Bolzen, Lager', 'Hydraulik: Schläuche, Zylinder, Hydrauliköl', 'Elektrik: Endschalter, Not-Halt, Steuerung'],
  },
};

/** Alle Unterseiten des Bereichs, in der Reihenfolge der Navigation. */
export const krantechnikPages = [kraneNachMass, kranservice, heukrananlagen];
