/**
 * Krantechnik – Bereichsseite und drei Unterseiten: Krane nach Mass (die Seite für schwierige
 * Gebäude: um Ecken, über Steigungen und Versätze; dazu Häfen und der Standardkran), Kranservice
 * (vier Stufen bis INEXXIO 365, mit Modernisierung und Prüfpflicht) und Heukrananlagen (Funk statt
 * Kabine, Saison-Check, Bauformen).
 * Alle vier Seiten haben ein eigenes Layout nach dem Muster von Speziallösungen (Oktober 2026); die
 * `AreaPage`-/`SubPage`-Objekte liefern Titel, Beschreibung, Zusammenfassung, Leistungsumfang und FAQ
 * für Sitemap, llms.txt und JSON-LD. Was auf der Seite als Weg steht, ist dort die Quelle – Ablauf
 * (`steps`) wird daraus abgeleitet. Bildsprache: Gebäude grau, was die Lösung ausmacht rot.
 * Wir bewerben Lösungen nach Mass, keine Katalogkrane. Keine Preise, kein «Abo», keine erfundenen Werte.
 */
import type { IconName } from '../components/Icon.astro';
import { inquiry } from '../config/inquiry.mjs';
import { site } from '../config/site.mjs';
import { sharedFaq } from './uebergabe';
import { promiseFaq } from './promises';
import type { AreaPage, Faq, Step, SubPage } from './types';

const anfrage = (label: string) => ({ label, href: '#anfrage' });
const KNM = site.labels.kraneNachMass;

const faqHsCare = sharedFaq.whoCares;
const faqOtherMakes = sharedFaq.otherMakes;
const ratgeberPruefung = { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Wer muss wann was prüfen?', kind: 'ratgeber' as const };
const ratgeberHeukran = { href: '/ratgeber/heukrananlage-planen', label: 'Neue Heukrananlage planen', text: 'Bauformen, Platzbedarf, Ablauf.', kind: 'ratgeber' as const };
const relatedNachMass = { href: '/krantechnik/krane-nach-mass', label: KNM, text: 'Auch für schwierige Gebäude.' };

/** Eine Station auf dem Weg (components/spezial/SolutionPath.astro). */
interface Station { icon: IconName; who: string; title: string; text: string; tags?: string[]; check?: string }
const facts = (items: Station[]): Step[] => items.map(({ title, text }) => ({ title, text }));

/* ------------------------------------------------------------------ Bereich */
/** Der Weg auf der Bereichsseite – zugleich der Ablauf in vier Schritten (`steps`). */
export const cranePath = {
  title: 'So läuft es ab',
  start: 'Ihr Anliegen',
  end: 'Ihr Kran läuft',
  items: [
    { icon: 'phone', who: 'Sie', title: 'Anfrage', text: 'Sie schildern Ihr Anliegen – per Formular oder am Telefon. Ein Foto hilft.', tags: ['Foto', 'Typenschild'] },
    { icon: 'search', who: 'Gemeinsam', title: 'Abklärung', text: 'Wir klären vor Ort oder am Telefon, was es braucht.', check: 'Verbindliche Offerte' },
    { icon: 'wrench', who: 'Wir', title: 'Umsetzung', text: 'Wir bauen, montieren, prüfen oder reparieren – die nötigen Teile sind dabei.' },
    { icon: 'clipboard-check', who: 'Wir', title: 'Protokoll', text: 'Zu jeder Arbeit ein Protokoll – der Eintrag gehört ins Kranbuch.', check: 'Kranbuch nachgeführt' },
  ] satisfies Station[],
};

export const krantechnik: AreaPage = {
  id: 'krantechnik',
  path: '/krantechnik',
  title: 'Krantechnik: Krane nach Mass',
  description:
    'Krane nach Mass – auch um Ecken, über Steigungen und Versätze. Heukrane per Funk, Kranservice bis INEXXIO 365. Die erste Inspektion ist gratis.',
  hero: {
    eyebrow: 'Krantechnik',
    h1: 'Krane, die zu Ihrem Gebäude ==passen==',
    lead:
      'Wir bauen Krane nach Mass – auch um Ecken, über Steigungen und Versätze. Unsere Heukrane steuern Sie per Funk, ohne Kabine. Und jeden Kran halten wir einsatzbereit.',
    photo: 'heukran-einsatz',
    primary: anfrage('Anfrage stellen'),
  },
  summary:
    '{{brand.full}} plant, baut und betreut Krane: Krane nach Mass auch für schwierige Gebäude – um Ecken, über Steigungen und Deckenversätze, in Scheunen und Hallen –, Boots- und Mastkrane und Bootslifte für Häfen, Clubs und Werften, Heukrananlagen ohne Kabine, bedient per Funk – dazu Kranservice und Modernisierung. Die erste Inspektion ist gratis. Mit INEXXIO 365 zahlen Sie eine fixe Monatsrate für die Einsatzbereitschaft – Ausfälle, Reparaturen und Ersatzteile übernehmen wir. Was Sie bei uns bekommen, deckt die Zufriedenheitsgarantie: Nicht zufrieden, übernehmen wir 50 %. Der Standort ist in {{address.home}}; im Einsatz sind wir {{area.summary}}.',
  steps: facts(cranePath.items),
  promises: ['garantie', 'inexxio365', 'erstservice'],
  faq: [
    promiseFaq.garantie,
    promiseFaq.inexxio365,
    promiseFaq.erstservice,
    sharedFaq.newCranes,
    faqOtherMakes,
  ],
  service: { name: 'Krantechnik', serviceType: 'Bau, Prüfung, Wartung, Modernisierung und Reparatur von Kranen' },
  keywords: ['Kran nach Mass', 'Kranservice Schweiz', 'Sonderkran', 'Kranbau Thurgau', 'Kranprüfung', 'Kurvenkran', 'Heukran Funkfernsteuerung'],
};

/** Die drei Karten der Bereichsseite (components/spezial/FieldCards.astro), je mit der Zeichnung aus dem Menü. */
export const craneOffers = {
  title: 'Alles rund um Ihren Kran',
  lead: 'Bauen, betreuen, modernisieren – aus einer Hand.',
  items: [
    { id: 'nach-mass', illo: 'menu/krane-nach-mass', alt: 'Zeichnung: Kran mit roter Brücke', title: KNM, text: 'Auch um Ecken, über Steigungen und Versätze – für Scheune, Halle und Hafen.', href: '/krantechnik/krane-nach-mass' },
    { id: 'service', illo: 'menu/kranservice', alt: 'Zeichnung: roter Werkzeugkasten und Prüfprotokoll', title: 'Kranservice', text: 'Die erste Inspektion ist gratis – bis zu INEXXIO 365: Ausfälle übernehmen wir.', href: '/krantechnik/kranservice' },
    { id: 'heukran', illo: 'menu/heukrananlagen', alt: 'Zeichnung: Heukran mit Greifer über dem Heustock', title: 'Heukrananlagen', text: 'Nach Mass, ohne Kabine, bedient per Funk – und betreut, solange sie läuft.', href: '/krantechnik/heukrananlagen' },
  ],
};

/* ------------------------------------------------------------------ Krane nach Mass */
export const kraneNachMass: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/krane-nach-mass',
  crumb: KNM,
  title: 'Krane für schwierige Gebäude',
  description:
    'Kurve, Steigung, Deckenversatz oder enge Ecke: Krane nach Mass für Scheunen und Hallen. Dazu Bootskrane und Bootslifte. Kauf mit Garantie oder zur Monatsrate.',
  hero: {
    eyebrow: 'Krantechnik · Krane nach Mass',
    h1: 'Ihr Gebäude ist nicht gerade. ==Ihr Kran== muss es auch nicht sein.',
    lead:
      'Kurve, Steigung, Deckenversatz oder eine enge Ecke: Wir bauen den Kran um Ihr Gebäude herum, nicht das Gebäude um den Kran. Für Scheunen und Hallen, neu oder als Erweiterung.',
    photo: 'reparatur-vor-ort',
    primary: anfrage('Fotos schicken'),
  },
  summary:
    '{{brand.full}} baut Krane nach Mass für Gebäude, in die kein Katalogkran passt: Die Fahrbahn biegt um Ecken, steigt an, folgt Deckenversätzen und erreicht auch enge, verwinkelte Stellen – in Scheunen wie in Gewerbehallen, neu oder als Erweiterung. Heukrane bedienen Sie per Funk, ohne Kabine. Dazu Boots- und Mastkrane und Bootslifte für Häfen, Clubs und Werften, und der Standardkran aus Markenkomponenten. Neue Krane gibt es zum Kauf – mit Zufriedenheitsgarantie: nicht zufrieden, übernehmen wir 50 % – oder ohne Kauf, zur Monatsrate mit INEXXIO 365.',
  glance: {
    forWhom: 'Landwirtschaftsbetriebe mit alten oder umgebauten Scheunen, Gewerbe, Lager, Recycling, Holz und Metall in Hallen, die gewachsen sind statt geplant – dazu Häfen, Clubs und Werften.',
    what: 'Fotos einschätzen, aufmessen und die Tragfähigkeit klären, konstruieren, im eigenen Betrieb fertigen, montieren – danach Prüfung, Wartung und Reparatur aus derselben Hand.',
    deliverables: 'Einen Kran, der um Ihr Gebäude herum gebaut ist, mit Dokumentation und Kranbuch – und einen Ansprechpartner, der ihn kennt.',
  },
  promises: ['garantie', 'inexxio365', 'erstservice'],
  scope: {
    title: 'Was zu jedem Kran gehört',
    lead: 'Gleich, ob Kurvenkran, Hallenkran oder Bootslift.',
    items: [
      { title: 'Planung vor Ort', text: 'Wir messen Gebäude, Steg und Last auf und hören zu, wie Sie arbeiten.' },
      { title: 'Konstruktion und Berechnung', text: 'Tragwerk, Kranbahn und Anbindung – nachvollziehbar dokumentiert.' },
      { title: 'Fertigung und Montage', text: 'Stahlbau im eigenen Betrieb, Montage und Inbetriebnahme bei Ihnen.' },
      { title: 'Abnahme und Kranbuch', text: 'Erste Prüfung, Einweisung in die Bedienung, Kranbuch angelegt.' },
      { title: 'Service aus einer Hand', text: 'Prüfung, Wartung und Reparatur von dem, der den Kran gebaut hat.' },
      { title: 'Ersatzteile', text: 'Markenkomponenten, die man beschaffen kann – und Stahlteile, die wir selbst fertigen.' },
    ],
  },
  faq: [
    { q: 'Geht das auch in meinem Gebäude?', a: 'Schicken Sie uns Fotos. Wir sagen Ihnen ehrlich, ob es geht, und wenn nicht, warum.' },
    { q: 'Muss ich umbauen?', a: 'Meist nicht. Wir passen den Kran ans Gebäude an, nicht umgekehrt.' },
    { q: 'Betreuen Sie auch bestehende Anlagen dieser Art?', a: 'Ja, auch Anlagen anderer Hersteller.' },
    { q: 'Muss ich den Kran kaufen?', a: 'Nein. Sie kaufen ihn mit Garantie – oder nutzen ihn ohne Kauf, zur Monatsrate mit INEXXIO 365.' },
    { q: 'Bauen Sie auch Bootslifte und betreuen bestehende?', a: 'Ja. Wir bauen neue Bootslifte nach Mass und prüfen, warten und reparieren bestehende – auch von anderen Herstellern.' },
  ],
  related: [
    { href: '/krantechnik/kranservice', label: 'Kranservice', text: 'Vier Stufen bis INEXXIO 365.' },
    { href: '/krantechnik/heukrananlagen', label: 'Heukrananlagen', text: 'Ohne Kabine, bedient per Funk.' },
    ratgeberPruefung,
  ],
  service: { name: KNM, serviceType: 'Planung, Bau und Montage von Kranen und Bootsliften nach Mass, auch für schwierige Gebäude' },
  keywords: ['Kran nach Mass', 'Sonderkran', 'Kurvenkran', 'Kran Kurvenfahrt', 'Kran mit Steigung', 'Heukran Kurve', 'Kran für Altbau', 'Sonderkran Thurgau', 'Industriekran', 'Bootslift', 'Bootskran'],
};

/** Wo ein Katalogkran nicht passt – vier Situationen, je mit Strichzeichnung (src/assets/illustrations/kran-*.svg). */
export const craneSituations = {
  title: 'Wo ein Katalogkran nicht passt',
  lead: 'Vier Situationen, die wir oft sehen – und wie der Kran trotzdem passt.',
  items: [
    { id: 'kurve', illo: 'kran-kurve', title: 'Um die Ecke', problem: 'Die Fahrbahn muss abbiegen.', solution: 'Kurvenfahrbahn mit passendem Fahrwerk.' },
    { id: 'steigung', illo: 'kran-steigung', title: 'Bergauf und bergab', problem: 'Boden oder Dach steigen an.', solution: 'Fahrbahn und Antrieb für die Steigung ausgelegt, mit sicherer Bremse.' },
    { id: 'versatz', illo: 'kran-versatz', title: 'Decke mit Versatz', problem: 'Die Höhe springt, Balken oder Unterzüge stören.', solution: 'Fahrbahn an jede Höhe angepasst, die Hubhöhe bleibt nutzbar.' },
    { id: 'eng', illo: 'kran-eng', title: 'Eng und verwinkelt', problem: 'Stützen, Nischen, wenig Platz.', solution: 'Kompakter Kran und Greifer, die auch die letzte Ecke erreichen.' },
  ],
  more: 'Ihre Situation ist nicht dabei? Fragen Sie trotzdem.',
};

/** Für Scheune und Halle – zwei gleich starke Bildkarten (components/PhotoCard.astro). */
export const craneWorlds = {
  title: 'Für Scheune und Halle',
  items: [
    {
      photo: 'heukran-einsatz', label: 'Landwirtschaft', title: 'Für die Scheune',
      text: 'Heu, Stroh, Silage, Mist – auch in alten und umgebauten Scheunen. Bedienung per Funk, ohne Kabine.',
      cta: { label: 'Zu den Heukrananlagen', href: '/krantechnik/heukrananlagen' },
    },
    {
      photo: 'pruefung-hallenkran', label: 'Gewerbe und Industrie', title: 'Für die Halle',
      text: 'Gewerbe, Lager, Recycling, Holz und Metall – Hallen, die gewachsen sind statt geplant. Ein- und Zweiträger-Brückenkrane, Hängekrane und Schwenkkrane, angepasst an das Gebäude.',
      cta: { label: 'Kran anfragen', href: '#anfrage' },
    },
  ],
};

/** Was Sie vorher wissen wollen – drei Sorgen vor der Anfrage, aus Kundensicht. Keine Dauer, keine weiteren Zusagen. */
export const craneConcerns = {
  title: 'Was Sie vorher wissen wollen',
  items: [
    { icon: 'shield-check' as IconName, q: 'Trägt mein Gebäude den Kran?', a: 'Wir klären, ob Dachstuhl, Wände oder Stützen die Last tragen, wenn nötig zusammen mit einem Statiker. Erst dann bauen wir.' },
    { icon: 'clock' as IconName, q: 'Steht mein Betrieb still?', a: 'Wir fertigen im eigenen Betrieb vor und montieren in kurzer Zeit. Den Termin legen wir mit Ihnen fest, in der Landwirtschaft ausserhalb der Erntezeit.' },
    { icon: 'trending-up' as IconName, q: 'Wächst die Anlage mit?', a: 'Längere Fahrbahn, zusätzlicher Bereich oder anderer Greifer: Wir bauen später aus.' },
  ],
};

/** Ablauf (Anker #ablauf) – vier Stationen. */
export const nachMassPath = {
  title: "So geht's",
  start: 'Ihr Gebäude',
  end: 'Ihr Kran läuft',
  items: [
    { icon: 'camera', who: 'Sie', title: 'Fotos schicken', text: 'Ein paar Handyfotos genügen für eine erste Einschätzung.', tags: ['Raum', 'Schwierige Stelle', 'Decke'] },
    { icon: 'search', who: 'Gemeinsam', title: 'Aufmass vor Ort', text: 'Wir messen alles auf, was den Kran betrifft, und klären die Tragfähigkeit.' },
    { icon: 'drafting-compass', who: 'Wir', title: 'Konstruktion und Offerte', text: 'Sie erhalten die Lösung mit verbindlicher Offerte.', check: 'Verbindliche Offerte' },
    { icon: 'wrench', who: 'Wir', title: 'Bau, Montage, Service', text: 'Alles aus einer Hand, vom Hersteller des Krans.', tags: ['Bau', 'Montage', 'Service'] },
  ] satisfies Station[],
};

/** Foto-Hilfe direkt beim Formular (Krane nach Mass). */
export const nachMassPhotoHint = {
  title: 'Diese Fotos helfen uns am meisten:',
  items: ['Gesamtansicht des Raums', 'Die schwierige Stelle', 'Decke bzw. Dachstuhl', 'Ablade- oder Arbeitsplatz'],
  note: `Dazu, wenn vorhanden, grobe Masse: Länge, Breite, Höhe. Bis zu ${inquiry.photos.max} Fotos.`,
};

/**
 * Belege (Referenzen): Projekte mit Foto, Situation, Lösung und Ort grob – ohne Kundennamen ohne
 * Freigabe. Sichtbar erst, wenn `site.features.craneReferences` an ist UND Einträge da sind; die Fotos
 * (`kran-kurve`, `kran-steigung`, `kran-versatz`, `kran-eng` in config/photos.mjs) kommen nach.
 * Eintrag: { photo: 'kran-kurve', situation: '…', solution: '…', place: 'Thurgau' }.
 */
export const craneReferences = {
  title: 'So sieht das aus',
  items: [] as { photo: string; situation: string; solution: string; place: string }[],
};

/** Der Standardkran – kurz: wenn es einfach geht, ist es auch einfach. */
export const standardCrane = {
  title: 'Wenn es einfach geht, ist es auch einfach.',
  text: 'Passt ein Standardkran, bauen wir ihn aus Markenkomponenten: Hubwerk und Fahrwerke von Markenherstellern, Planung, Montage und Service von uns.',
  items: ['Bewährte Komponenten, Ersatzteile verfügbar', 'Planung und Montage passend zu Ihrer Halle', 'Service von dem, der ihn montiert hat'],
};

/** Häfen, Clubs und Werften – unverändert, unterhalb der neuen Abschnitte (Anker #hafen). */
export const harbour = {
  title: 'Boots- und Mastkrane, Bootslifte',
  text: 'Für Hafenmeister, Clubs und Werften am Bodensee und an Schweizer Seen: neue Bootslifte und Krane nach Mass, Service für bestehende. Die erste Inspektion ist gratis; für Clubs mit eigenem Kran gibt es INEXXIO 365.',
  items: ['Bootslifte nach Mass – passend zu Steg, Boot und Ufer', 'Boots- und Mastkrane, sicher auch für Mitglieder, die selten kranen', 'Prüfung und Wartung vor dem Einwassern'],
};

/** Das Hafenjahr – wann wir am Hafen was tun. */
export const harbourYear = {
  title: 'Das Hafenjahr',
  lead: 'Ein Bootskran arbeitet in Wellen. Wir richten den Service danach aus.',
  seasons: [
    { title: 'Vor dem Einwassern', when: 'Winter und Frühling', text: 'Prüfung und Wartung, Kranbuch nachführen, Mängel beheben – damit Kran und Lift am ersten Tag der Saison laufen.' },
    { title: 'In der Saison', when: 'Frühling bis Herbst', text: 'Fällt etwas aus, rufen Sie direkt an. Mit INEXXIO 365 übernehmen wir Ausfälle – jeder Tag Stillstand ist gratis.' },
    { title: 'Nach dem Auswassern', when: 'Herbst', text: 'Zustand aufnehmen, Reparaturen und neue Anlagen über den Winter planen.' },
  ],
};

/** Neue Krane: zwei Wege (Anker #wege). */
export const newCraneWays = {
  title: 'Kaufen – oder ohne Kauf nutzen',
  lead: 'Für jeden neuen Kran gilt: Verbindliche Offerte vor jeder Arbeit, keine Mindestlaufzeit.',
  ways: [
    { label: 'Kaufen mit Garantie', title: 'Sie kaufen den Kran.', text: 'Nicht zufrieden? Die Hälfte übernehmen wir.' },
    { label: 'INEXXIO 365', title: 'Ohne Kauf, zur Monatsrate.', text: 'Sie zahlen für die Einsatzbereitschaft – Ausfälle, Reparaturen und Ersatzteile übernehmen wir. Jeder Tag Stillstand ist gratis.', dark: true },
  ],
};

/* ------------------------------------------------------------------ Kranservice */
/**
 * EINE Seite für den Kranservice: die vier Stufen (Auf Abruf · Basis · Plus · INEXXIO 365),
 * INEXXIO 365 mit seinen zwei Wegen, was wir prüfen, Modernisierung und die Prüfpflicht.
 * Keine Preise, keine Kranklassen – vor jeder Arbeit gibt es eine verbindliche Offerte.
 */
export const kranservice: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/kranservice',
  crumb: 'Kranservice',
  title: 'Kranservice und INEXXIO 365',
  description:
    'Kranservice in vier Stufen: erste Inspektion gratis, Service-Vertrag Basis oder Plus, INEXXIO 365. Dazu Modernisierung. Verbindliche Offerte vorab.',
  hero: {
    eyebrow: 'Krantechnik · Kranservice',
    h1: 'Ihr Kran ist einsatzbereit. Ausfälle ==übernehmen wir==.',
    lead:
      'Lernen Sie uns kennen: Die erste Inspektion ist gratis. Danach wählen Sie, wie viel wir übernehmen – bis zu INEXXIO 365: eine fixe Monatsrate für die Einsatzbereitschaft.',
    photo: 'pruefung-hallenkran',
    primary: anfrage('Kranservice anfragen'),
  },
  summary:
    '{{brand.full}} prüft, wartet, repariert und modernisiert Krane: Brücken-, Hänge-, Schwenk- und Drehkrane, Boots- und Mastkrane und Heukrane. Vier Stufen: Auf Abruf (die erste Inspektion ist gratis), Service-Vertrag Basis (gesetzliche Prüfung, digitales Kranbuch, Erinnerung an Fristen), Service-Vertrag Plus (dazu Wartung, feste Reaktionszeit, fester Ansprechpartner) und INEXXIO 365 (dazu Teile und Reparaturen, Ersatz-Hebezeug und das Verfügbarkeitsversprechen). Verbindliche Offerte vor jeder Arbeit, keine Mindestlaufzeit.',
  glance: {
    forWhom: 'Recycling und Entsorgung, Sägewerke und Holzhandel, Stahlhandel und Metallbau, Betonwerke, Häfen und Clubs – und alle, deren Kran laufen muss.',
    what: 'Prüfung, Wartung, Reparatur und Modernisierung durch Kranfachleute – vom einzelnen Einsatz bis INEXXIO 365.',
    deliverables: 'Einen Kran, der einsatzbereit ist, ein nachgeführtes Kranbuch und eine verbindliche Offerte vor jeder Arbeit.',
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
    {
      q: 'Lohnt sich eine Modernisierung?',
      a: 'Oft ja: Ist der Stahlbau gut, bringen Funkfernsteuerung, Frequenzumrichter oder eine neue Überlastsicherung den Kran auf den Stand der Technik – ohne neuen Kran. Wir sagen Ihnen offen, wann ein neuer die bessere Lösung ist.',
    },
    {
      q: 'Machen Sie auch die Kontrolle durch den Kranexperten?',
      a: 'Nein. Die periodische Kontrolle von Fahrzeug- und Turmdrehkranen macht ein von der Suva anerkannter Kranexperte. Wir übernehmen die Überprüfung durch Kranfachleute und die Wartung. Den Unterschied erklärt unser Ratgeber [Kranprüfung in der Schweiz](/ratgeber/kranpruefung-schweiz#kranfachmann-oder-kranexperte).',
    },
  ],
  related: [
    relatedNachMass,
    { href: '/krantechnik/heukrananlagen', label: 'Heukrananlagen', text: 'Saison-Check vor dem ersten Schnitt.' },
    ratgeberPruefung,
  ],
  service: { name: 'Kranservice', serviceType: 'Kranprüfung, Kranwartung, Kranmodernisierung und Kranreparatur' },
  keywords: ['Kranservice', 'Kranprüfung', 'Kranwartung', 'Kranmodernisierung', 'INEXXIO 365', 'Kranbuch'],
};

/**
 * Die vier Stufen des Kranservice. Jede enthält die vorherige – darum nennt jede nur, was
 * dazukommt. Kein Betrag, keine Kranklasse: die verbindliche Offerte erhalten Sie vorab.
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
  title: 'Zwei Wege zu INEXXIO 365',
  lead: 'Sie zahlen eine fixe Monatsrate für die Einsatzbereitschaft – nicht für Ausfallzeiten und Reparaturen. Prüfung, Wartung und Ersatzteile sind inklusive, jeder Tag Stillstand ist gratis. Keine Mindestlaufzeit.',
  ways: [
    { label: 'Ihr bestehender Kran', title: 'Wir übernehmen ihn.', text: 'Nach einer Eintrittsprüfung betreuen wir ihn rundum.' },
    { label: 'Ein neuer Kran', title: 'Ohne Kauf, zur Monatsrate.', text: 'Wir bauen ihn nach Mass und halten ihn einsatzbereit.', dark: true },
  ],
  cta: 'INEXXIO 365 anfragen',
};

/** Modernisierung (Anker #modernisierung auf dem Kranservice) – gehört zum Service, mit Garantie. */
export const modernisation = {
  title: 'Modernisieren statt ersetzen',
  lead: 'Ist der Stahlbau gut, bringen wir die Technik auf den neuen Stand. Nicht zufrieden? Die Hälfte übernehmen wir.',
  items: [
    { icon: 'smartphone' as IconName, title: 'Funkfernsteuerung', text: 'Bedienen mit Abstand zur Last – sicherer und mit Blick auf den ganzen Weg.' },
    { icon: 'trending-up' as IconName, title: 'Frequenzumrichter', text: 'Sanft anfahren und bremsen: weniger Pendeln, weniger Verschleiss.' },
    { icon: 'shield-check' as IconName, title: 'Überlastsicherung', text: 'Nachgerüstet oder erneuert – damit der Kran nicht mehr hebt, als er darf.' },
    { icon: 'wrench' as IconName, title: 'Steuerung und Elektrik', text: 'Neue Steuerung, Endschalter und Not-Halt nach heutigem Stand.' },
  ],
};

/** Foto-Hilfe (Kranservice): mit Typenschild bereitet sich der Einsatz besser vor. */
export const photoHint = {
  title: 'Foto vom Typenschild oder vom Schaden mitschicken',
  items: ['Typenschild', 'Der Schaden', 'Der ganze Kran'],
  note: `Mit einem Foto wissen wir vor dem Einsatz, welcher Kran es ist. Bis zu ${inquiry.photos.max} Fotos.`,
};

/* ------------------------------------------------------------------ Heukrananlagen */
const faqNoCabin: Faq = {
  q: 'Warum hat Ihr Heukran keine Kabine?',
  a: 'Weil Sie vom Boden aus besser sehen, nicht klettern müssen und jeder im Betrieb den Kran bedienen kann.',
};

export const heukrananlagen: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/heukrananlagen',
  crumb: 'Heukrananlagen',
  title: 'Heukrananlagen: Service',
  description:
    'Heukrananlagen ohne Kabine, bedient per Funk: betreuen, umbauen, neu planen. Saison-Check, Reparatur, Ersatzteile – die erste Inspektion ist gratis.',
  hero: {
    eyebrow: 'Krantechnik · Heukrananlagen',
    h1: 'Ihre Heukrananlage läuft, wenn die ==Ernte== beginnt',
    lead:
      'Seit {{history.cranesSince}} bauen wir in {{address.city}} Heukrane – nach Mass, bedient per Funk. Wir betreuen bestehende Anlagen, die erste Inspektion ist gratis, und planen neue, wenn Sie eine brauchen.',
    photo: 'heukran-einsatz',
    primary: anfrage('Service anfragen'),
  },
  summary:
    '{{brand.full}} betreut Heukrananlagen: Saison-Check, Wartung, Reparatur, Ersatzteile und Modernisierung – auch für alle bestehenden HS-Krananlagen. Die erste Inspektion ist gratis. Unsere Heukrane haben keine Kabine: Sie steuern per Funk, vom Boden, vom Wagen oder vom Heustock aus. Neue Anlagen planen und bauen wir auf Anfrage nach Mass: Einschienenkrane, Brückenkrane, hydraulische Drehkrane und Anlagen, die an das Gebäude angepasst sind – auch um Ecken, über Steigungen und Versätze. Nicht zufrieden, übernehmen wir 50 %. Der Standort ist in {{address.home}}.',
  glance: {
    forWhom: 'Landwirtschaftsbetriebe für Heu, Stroh, Silage und Mist – und alle, die lose Güter mit dem Greifer umschlagen: Hackschnitzelheizungen, Sägewerke, Kompost- und Biogasanlagen, Werkhöfe.',
    what: 'Saison-Check, Wartung, Reparatur und Modernisierung bestehender Anlagen. Neue Anlagen ohne Kabine, bedient per Funk: Besichtigung, Konzept, Fertigung, Montage.',
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
      { title: 'Neuanlage nach Mass', text: 'Bauform, Spannweite und Hubhöhe passend zu Scheune, Heustock und Arbeitsweise – bedient per Funk.' },
    ],
  },
  faq: [
    faqNoCabin,
    promiseFaq.erstservice,
    {
      q: 'Wann ist der beste Zeitpunkt für den Service?',
      a: 'Vor der Saison, zwischen März und Mai. Dann bleibt Zeit für Reparaturen, ohne dass das Wetter drängt.',
    },
    faqHsCare,
    {
      q: 'Was kostet eine neue Heukrananlage?',
      a: 'Das hängt von Bauform, Spannweite, Hubhöhe und Gebäude ab. Nach der Besichtigung erhalten Sie eine verbindliche Offerte.',
    },
  ],
  related: [
    { href: '/krantechnik/kranservice', label: 'Kranservice', text: 'Die erste Inspektion ist gratis.' },
    relatedNachMass,
    ratgeberHeukran,
  ],
  service: { name: 'Heukrananlagen', serviceType: 'Service, Umbau und Bau von Heukrananlagen ohne Kabine, bedient per Funk' },
  keywords: ['Heukran', 'Heukrananlage', 'Heukran Service', 'Heukran kaufen', 'Heudrehkran', 'Hackschnitzelkran', 'Heukran Funkfernsteuerung', 'Heukran ohne Kabine'],
};

/** Funk statt Kabine – direkt nach dem Kopf der Heukrananlagen (Zeichnung heukran-funk, bis das Foto da ist). */
export const radioControl = {
  eyebrow: 'Funk statt Kabine',
  title: 'Steuern, wo Sie ==stehen==.',
  lead: 'Unsere Heukrane haben keine Kabine. Sie steuern per Funk, vom Boden, vom Wagen oder vom Heustock aus. Dort, wo Sie am besten sehen.',
  /** Foto (config/photos.mjs `heukran-funk`), sobald es da ist; bis dahin die Zeichnung. */
  photo: 'heukran-funk',
  illo: 'heukran-funk',
  alt: 'Zeichnung: Mensch am Boden mit Funksender, der Heukran mit Greifer über dem Heustock',
  items: [
    { icon: 'smartphone' as IconName, title: 'Kein Aufsteigen', text: 'Keine Leiter, keine Kabine, kein Klettern. Sender in die Hand, und der Kran läuft.' },
    { icon: 'shield-check' as IconName, title: 'Beste Sicht, sicherer Abstand', text: 'Sie stehen dort, wo Sie den Greifer genau sehen, und mit Abstand zur Last.' },
    { icon: 'user' as IconName, title: 'Allein abladen', text: 'Wagen hineinfahren, absteigen, abladen. Es braucht niemanden in der Kabine.' },
    { icon: 'users' as IconName, title: 'Jeder kann bedienen', text: 'Auch wer nicht schwindelfrei oder nicht mehr so beweglich ist, und die ganze Familie.' },
  ],
};

/** Module der Heukran-Seite. */
export const heukranModules = {
  forms: {
    title: 'Bauformen',
    lead: 'Welche Bauform passt, hängt vom Gebäude und von der Arbeit ab. Bei der Besichtigung klären wir es gemeinsam.',
    legend: { grey: 'Grau: das Gebäude', red: 'Rot: die Bauform' },
    items: [
      { title: 'Einschienenkran', tab: 'Einschiene', illo: 'heukran-einschiene', text: 'Der Kran fährt auf einer Laufschiene unter dem Dach. Passt für lange, schmale Scheunen mit einem Heustock entlang der Fahrbahn. Bedienung per Funk.' },
      { title: 'Brückenkran', tab: 'Brücke', illo: 'heukran-bruecke', text: 'Eine Kranbrücke fährt über die ganze Breite, die Katze quer dazu. Passt für breite Scheunen mit mehreren Stöcken oder Abladeplätzen. Bedienung per Funk.' },
      { title: 'Drehkran, hydraulisch', tab: 'Drehkran', illo: 'heukran-drehkran', text: 'Ein Drehturm mit Ausleger fährt längs und quer und dreht sich – der Greifer erreicht auch Ecken und Nischen neben der Fahrbahn. Bedienung per Funk.' },
      { title: 'An das Gebäude angepasst', tab: 'Angepasst', illo: 'heukran-angepasst', text: 'Fahrbahn, Stützen und Spannweite folgen dem Bau – auch um Ecken, über Steigungen und Versätze. Mehr unter [Krane nach Mass](/krantechnik/krane-nach-mass). Bedienung per Funk.' },
    ],
    cta: { label: 'Neuanlage anfragen', href: '#anfrage' },
  },
  steps: {
    title: 'Ablauf einer Neuanlage',
    start: 'Ihre Scheune',
    end: 'Die Anlage läuft',
    items: [
      { icon: 'search', who: 'Gemeinsam', title: 'Besichtigung', text: 'Wir schauen Scheune, Heustock und Abladeplatz an und hören zu, wie Sie arbeiten.' },
      { icon: 'drafting-compass', who: 'Wir', title: 'Konzept und Offerte', text: 'Ein Vorschlag zu Bauform, Spannweite und Hubhöhe.', check: 'Verbindliche Offerte' },
      { icon: 'wrench', who: 'Wir', title: 'Fertigung', text: 'Wir fertigen die Anlage bei uns in {{address.city}}.' },
      { icon: 'flag', who: 'Bei Ihnen', title: 'Montage und Inbetriebnahme', text: 'Wir montieren vor Ort, nehmen in Betrieb und zeigen Ihnen die Bedienung per Funk.' },
      { icon: 'calendar-check', who: 'Wir', title: 'Service', text: 'Saison-Check und Wartung – solange die Anlage läuft.' },
    ] satisfies Station[],
  },
  owners: {
    title: 'Sie haben eine HS-Krananlage? Sie wird weiter betreut.',
    text: 'Die Anlagen, die seit {{history.cranesSince}} in {{address.city}} entstanden sind, betreuen wir weiter. Service, Reparatur und Ersatzteile – mit demselben Wissen. Mehr dazu unter [Aus HS Steiner wird {{brand.name}}](/ueber-uns#uebergabe).',
  },
  /** Saison-Check (Anker #saison-check, Ziel der Saison-Aktion) – der Wandkalender (components/SeasonCalendar.astro). */
  season: {
    id: 'saison-check',
    title: 'Saison-Check vor dem ersten Schnitt',
    text: 'Ein Heukran steht über den Winter still und muss beim ersten Schnitt sofort laufen. Zwischen März und Mai prüfen wir die ganze Anlage – und ersetzen, was bis zur Ernte nicht hält.',
    kinds: [
      { icon: 'wrench' as IconName, word: 'Check', legend: 'März bis Mai: Saison-Check', dark: true },
      { icon: 'sun' as IconName, word: 'Saison', legend: 'Die Anlage läuft' },
      { icon: 'snowflake' as IconName, word: 'Ruhe', legend: 'Die Anlage steht' },
    ],
    plan: [2, 2, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2],
    items: ['Kranbahn und Endanschläge', 'Fahrwerke und Laufräder', 'Seil oder Kette, Haken', 'Greifer: Zinken, Bolzen, Lager', 'Hydraulik: Schläuche, Zylinder, Hydrauliköl', 'Elektrik: Endschalter, Not-Halt, Steuerung'],
    cta: 'Saison-Check planen',
  },
};

/** Alle Unterseiten des Bereichs, in der Reihenfolge der Navigation. */
export const krantechnikPages = [kraneNachMass, kranservice, heukrananlagen];
