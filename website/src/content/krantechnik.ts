/**
 * Krantechnik – Bereichsseite und drei Unterseiten: Krane nach Mass (die Seite für schwierige
 * Gebäude: um Ecken, über Steigungen und Versätze; dazu Häfen und der Standardkran), Kranservice
 * (drei Stufen bis INEXXIO 365, mit Modernisierung und Prüfpflicht) und Heukrananlagen (Funk statt
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
  title: 'So läuft es ab.',
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
    h1: 'Krane, die zu Ihrem Gebäude ==passen==.',
    lead:
      'Wir bauen Krane nach Mass – auch um Ecken, über Steigungen und Versätze. Unsere Heukrane steuern Sie per Funk, ohne Kabine. Und jeden Kran halten wir einsatzbereit.',
    photo: 'heukran-einsatz',
    primary: anfrage('Anfrage stellen'),
  },
  summary:
    '{{brand.name}} plant, baut und betreut Krane: Krane nach Mass auch für schwierige Gebäude – um Ecken, über Steigungen und Deckenversätze, in Scheunen und Hallen –, Boots- und Mastkrane und Bootslifte für Häfen, Clubs und Werften, Heukrananlagen ohne Kabine, bedient per Funk – dazu Kranservice und Modernisierung. Die erste Inspektion ist gratis. Mit INEXXIO 365 zahlen Sie eine fixe Monatsrate für die Einsatzbereitschaft – Ausfälle, Reparaturen und Ersatzteile übernehmen wir. Was Sie bei uns bekommen, deckt die Zufriedenheitsgarantie: Nicht zufrieden, übernehmen wir 50 %. Der Standort ist in {{address.home}}; im Einsatz sind wir {{area.summary}}.',
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
  title: 'Alles rund um Ihren Kran.',
  lead: 'Bauen, betreuen, modernisieren – aus einer Hand.',
  items: [
    { id: 'nach-mass', illo: 'menu/krane-nach-mass', alt: 'Zeichnung: Kran mit roter Brücke', title: KNM, text: 'Kurve, Steigung, Versatz? Wir bauen den Kran um Ihr Gebäude herum.', href: '/krantechnik/krane-nach-mass' },
    { id: 'service', illo: 'menu/kranservice', alt: 'Zeichnung: roter Werkzeugkasten und Prüfprotokoll', title: 'Kranservice', text: 'Die erste Inspektion ist gratis. Mit INEXXIO 365 übernehmen wir die Ausfälle.', href: '/krantechnik/kranservice' },
    { id: 'heukran', illo: 'menu/heukrananlagen', alt: 'Zeichnung: Heukran mit Greifer über dem Heustock', title: 'Heukrananlagen', text: 'Ohne Kabine, per Funk: Sie bleiben unten, der Greifer arbeitet.', href: '/krantechnik/heukrananlagen' },
  ],
};

/* ------------------------------------------------------------------ Krane nach Mass */
export const kraneNachMass: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/krane-nach-mass',
  crumb: KNM,
  title: 'Krane für schwierige Gebäude',
  description:
    'Kurve, Steigung, Deckenversatz oder Ecke: Krane nach Mass für Scheunen und Hallen, dazu Bootskrane und Bootslifte. Kauf mit Garantie oder zur Monatsrate.',
  hero: {
    eyebrow: 'Krantechnik · Krane nach Mass',
    h1: 'Ihr Gebäude ist nicht gerade. ==Ihr Kran== muss es auch nicht sein.',
    lead:
      'Kurve, Steigung, Deckenversatz oder eine enge Ecke: Wir bauen den Kran um Ihr Gebäude herum, nicht das Gebäude um den Kran. Für Scheunen und Hallen, neu oder als Erweiterung.',
    photo: 'reparatur-vor-ort',
    primary: anfrage('Fotos schicken'),
  },
  summary:
    '{{brand.name}} baut Krane nach Mass für Gebäude, in die kein Katalogkran passt: Die Fahrbahn biegt um Ecken, steigt an, folgt Deckenversätzen und erreicht auch enge, verwinkelte Stellen – in Scheunen wie in Gewerbehallen, neu oder als Erweiterung. Heukrane bedienen Sie per Funk, ohne Kabine. Dazu Boots- und Mastkrane und Bootslifte für Häfen, Clubs und Werften, und der Standardkran aus Markenkomponenten. Neue Krane gibt es zum Kauf – mit Zufriedenheitsgarantie: nicht zufrieden, übernehmen wir 50 % – oder ohne Kauf, zur Monatsrate mit INEXXIO 365.',
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
    { q: 'Geht das auch in meinem Gebäude?', a: 'Schicken Sie uns Fotos. Wir sagen Ihnen ehrlich, ob es geht, und wenn nicht, warum. Umbauen müssen Sie meist nicht: Wir passen den Kran ans Gebäude an.' },
    { q: 'Trägt mein Gebäude den Kran?', a: 'Das klären wir vor dem Bau: ob Dachstuhl, Wände oder Stützen die Last tragen, wenn nötig zusammen mit einem Statiker. Erst dann bauen wir.' },
    { q: 'Steht mein Betrieb während der Montage still?', a: 'Wir fertigen im eigenen Betrieb vor und montieren in kurzer Zeit. Den Termin legen wir mit Ihnen fest, in der Landwirtschaft ausserhalb der Erntezeit.' },
    promiseFaq.garantie,
    { q: 'Betreuen Sie auch bestehende Krane und Bootslifte?', a: 'Ja. Wir prüfen, warten und reparieren bestehende Anlagen – auch von anderen Herstellern.' },
  ],
  related: [
    { href: '/krantechnik/kranservice', label: 'Kranservice', text: 'Drei Stufen bis INEXXIO 365.' },
    { href: '/krantechnik/heukrananlagen', label: 'Heukrananlagen', text: 'Ohne Kabine, bedient per Funk.' },
    ratgeberPruefung,
  ],
  service: { name: KNM, serviceType: 'Planung, Bau und Montage von Kranen und Bootsliften nach Mass, auch für schwierige Gebäude' },
  keywords: ['Kran nach Mass', 'Sonderkran', 'Kurvenkran', 'Kran Kurvenfahrt', 'Kran mit Steigung', 'Heukran Kurve', 'Kran für Altbau', 'Sonderkran Thurgau', 'Industriekran', 'Bootslift', 'Bootskran'],
};

/**
 * Wo ein Katalogkran nicht passt (Anker #situationen) – alle vier Situationen auf einen Blick, gesetzt wie
 * der Verschleissteile-Katalog (components/Magazine + PhotoCard). Solange die Fotos (config/photos.mjs
 * `kran-*`) fehlen, steht die Zeichnung (src/assets/illustrations/kran-*.svg). Die letzte Karte fragt.
 */
export const craneSituations = {
  title: 'Wo ein Katalogkran nicht passt.',
  lead: 'Vier Situationen, die wir oft sehen – und wie der Kran trotzdem passt.',
  items: [
    { photo: 'kran-kurve', illo: 'kran-kurve', label: 'Kurve', title: 'Um die Ecke', alt: 'Zeichnung von oben: Halle in L-Form, die rote Fahrbahn biegt um die Ecke', text: 'Die Fahrbahn muss abbiegen. Wir bauen sie als Kurve, mit einem Fahrwerk, das ihr folgt.' },
    { photo: 'kran-steigung', illo: 'kran-steigung', label: 'Steigung', title: 'Über eine Steigung', alt: 'Zeichnung im Schnitt: Decke mit Absatz, die rote Fahrbahn steigt weich mit an', text: 'Die Decke hat einen Absatz. Die Fahrbahn steigt weich mit an – Antrieb und Bremse sind dafür ausgelegt.' },
    { photo: 'kran-versatz', illo: 'kran-versatz', label: 'Versatz', title: 'Decke mit Versatz', alt: 'Zeichnung im Schnitt: Decke springt in der Höhe, die rote Fahrbahn hängt gerade darunter', text: 'Die Höhe springt, Balken oder Unterzüge stören. Wir hängen die Fahrbahn so ab, dass die Hubhöhe nutzbar bleibt.' },
    { photo: 'kran-eng', illo: 'kran-eng', label: 'Wenig Platz', title: 'Eng und verwinkelt', alt: 'Zeichnung von oben: Raum mit Stützen und Nische, der rote Kran erreicht die Ecke', text: 'Stützen, Nischen, wenig Platz: Ein kompakter Kran mit passendem Greifer erreicht auch die letzte Ecke.' },
  ],
  missing: { title: 'Ihre Situation ist nicht dabei?', text: 'Fragen Sie trotzdem. Schicken Sie uns ein paar Fotos, wir sagen Ihnen ehrlich, ob es geht.', cta: anfrage('Fotos schicken') },
};

/** Für Scheune und Halle – zwei gleich starke Bildkarten (components/PhotoCard.astro). */
export const craneWorlds = {
  title: 'Für Scheune und Halle.',
  items: [
    {
      photo: 'heukran-einsatz', label: 'Landwirtschaft', title: 'Für die Scheune',
      text: 'Heu, Stroh, Silage, Mist – auch in alten und umgebauten Scheunen. Bedienung per Funk, ohne Kabine.',
      cta: { label: 'Zu den Heukrananlagen', href: '/krantechnik/heukrananlagen' },
    },
    {
      photo: 'pruefung-hallenkran', label: 'Gewerbe und Industrie', title: 'Für die Halle',
      text: 'Gewerbe, Lager, Recycling, Holz und Metall – auch Hallen, die gewachsen sind statt geplant. Passt ein Standardkran, bauen wir ihn aus Markenkomponenten.',
      cta: { label: 'Kran anfragen', href: '#anfrage' },
    },
  ],
};

/** Ablauf (Anker #ablauf) – fünf Stationen; sie sagen zugleich, was zu jedem Kran gehört. */
export const nachMassPath = {
  title: 'So läuft es ab.',
  start: 'Ihr Gebäude',
  end: 'Ihr Kran läuft',
  items: [
    { icon: 'camera', who: 'Sie', title: 'Fotos schicken', text: 'Ein paar Handyfotos genügen für eine erste Einschätzung.' },
    { icon: 'search', who: 'Gemeinsam', title: 'Aufmass vor Ort', text: 'Wir messen Gebäude und Last auf, klären die Tragfähigkeit und hören zu, wie Sie arbeiten.' },
    { icon: 'drafting-compass', who: 'Wir', title: 'Konstruktion und Offerte', text: 'Tragwerk, Kranbahn und Anbindung – berechnet und dokumentiert.', check: 'Verbindliche Offerte' },
    { icon: 'wrench', who: 'Wir', title: 'Fertigung und Montage', text: 'Stahlbau im eigenen Betrieb, Montage und Abnahme bei Ihnen, mit Einweisung.', check: 'Kranbuch angelegt' },
    { icon: 'calendar-check', who: 'Wir', title: 'Service', text: 'Prüfung, Wartung und Ersatzteile. Wächst Ihr Betrieb, bauen wir den Kran aus.' },
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

/** Häfen, Clubs und Werften (Anker #hafen) – Text und das freigestellte Hafen-Bild. */
export const harbour = {
  label: 'Häfen, Clubs und Werften',
  title: 'Boots- und Mastkrane, Bootslifte.',
  text: 'Wir bauen sie nach Mass für Ihren Hafen – und halten bestehende Anlagen in Schuss, auch von anderen Herstellern.',
  alt: 'Roter Bootslift hält ein Motorboot über dem Wasser, daneben ein roter Mastkran auf dem Steg; Ufer und Steg als Zeichnung',
  items: [
    { icon: 'drafting-compass' as IconName, title: 'Bootslifte', text: 'Nach Mass für Steg, Boot und Ufer.' },
    { icon: 'users' as IconName, title: 'Boots- und Mastkrane', text: 'Einfach zu bedienen – auch für Mitglieder, die selten kranen.' },
    { icon: 'calendar-check' as IconName, title: 'Service', text: 'Prüfung und Wartung rechtzeitig vor dem Einwassern.' },
  ],
  cta: anfrage('Hafen-Anlage anfragen'),
};

/* ------------------------------------------------------------------ Kranservice */
/**
 * EINE Seite für den Kranservice: die drei Stufen (Auf Abruf · Service-Vertrag · INEXXIO 365),
 * INEXXIO 365 mit seinen zwei Wegen, was wir prüfen, Modernisierung und die Prüfpflicht.
 * Keine Preise, keine Kranklassen – vor jeder Arbeit gibt es eine verbindliche Offerte.
 */
export const kranservice: SubPage = {
  area: 'krantechnik',
  path: '/krantechnik/kranservice',
  crumb: 'Kranservice',
  title: 'Kranservice und INEXXIO 365',
  description:
    'Kranservice in drei Stufen: erste Inspektion gratis, Service-Vertrag mit Prüfung und Wartung, INEXXIO 365. Dazu Modernisierung. Verbindliche Offerte vorab.',
  hero: {
    eyebrow: 'Krantechnik · Kranservice',
    h1: 'Ihr Kran ist einsatzbereit. Ausfälle ==übernehmen wir==.',
    lead:
      'Lernen Sie uns kennen: Die erste Inspektion ist gratis. Danach wählen Sie, wie viel wir übernehmen – bis zu INEXXIO 365: eine fixe Monatsrate für die Einsatzbereitschaft.',
    photo: 'pruefung-hallenkran',
    primary: anfrage('Kranservice anfragen'),
  },
  summary:
    '{{brand.name}} prüft, wartet, repariert und modernisiert Krane: Brücken-, Hänge-, Schwenk- und Drehkrane, Boots- und Mastkrane und Heukrane. Drei Stufen: Auf Abruf (die erste Inspektion ist gratis), Service-Vertrag (gesetzliche Prüfung, Wartung, digitales Kranbuch mit Erinnerung an Fristen, feste Reaktionszeit, fester Ansprechpartner) und INEXXIO 365 (dazu Teile und Reparaturen, Ersatz-Hebezeug und das Verfügbarkeitsversprechen). Verbindliche Offerte vor jeder Arbeit, keine Mindestlaufzeit.',
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
      a: 'Auf Abruf, wenn Sie selten etwas brauchen. Der Service-Vertrag, wenn Prüfung, Wartung und Kranbuch sicher erledigt sein sollen. INEXXIO 365, wenn Ihr Betrieb vom Kran abhängt.',
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
    { href: '/krantechnik/heukrananlagen', label: 'Heukrananlagen', text: 'Saison-Check im Frühling oder im Spätherbst.' },
    ratgeberPruefung,
  ],
  service: { name: 'Kranservice', serviceType: 'Kranprüfung, Kranwartung, Kranmodernisierung und Kranreparatur' },
  keywords: ['Kranservice', 'Kranprüfung', 'Kranwartung', 'Kranmodernisierung', 'INEXXIO 365', 'Kranbuch'],
};

/**
 * Die drei Stufen des Kranservice. Jede enthält die vorherige – darum nennt jede nur, was
 * dazukommt. Kein Betrag, keine Kranklasse: die verbindliche Offerte erhalten Sie vorab.
 */
export const serviceTiers = {
  title: 'Drei Stufen – Sie wählen, wie viel wir übernehmen.',
  lead: 'Jede Stufe enthält die vorherige.',
  tiers: [
    { name: 'Auf Abruf', claim: 'Einzeln bestellt, wenn Sie es brauchen.', items: ['Service, Wartung, Prüfung oder Reparatur', 'Die erste Inspektion ist gratis'] },
    { name: 'Service-Vertrag', claim: 'Pflicht erledigt, Kran gepflegt.', items: ['Gesetzliche Prüfung, mit Protokoll', 'Wartung nach Herstellervorgabe', 'Digitales Kranbuch, Erinnerung an Fristen', 'Feste Reaktionszeit, fester Ansprechpartner'] },
    { name: 'INEXXIO 365', claim: 'Einsatzbereit. Ausfälle übernehmen wir.', items: ['Teile und Reparaturen inklusive', 'Ersatz-Hebezeug', 'Verfügbarkeitsversprechen: jeder Tag Stillstand ist gratis'], featured: true },
  ],
};

/** Prüfen, warten, modernisieren (Kranservice) – zwei Bildkarten (PhotoCard), Anker #pruefen und #modernisierung. */
export const serviceWork = {
  title: 'Prüfen, warten, modernisieren.',
  items: [
    {
      id: 'pruefen', photo: 'pruefung-hallenkran', label: 'Prüfen und warten', title: 'Der ganze Kran, einmal durch',
      text: 'Tragwerk und Kranbahn, Hubwerk, Seil oder Kette, Fahrwerke, Elektrik und Sicherheit – nach Herstellervorgabe, mit Protokoll fürs Kranbuch.',
      cta: anfrage('Prüfung anfragen'),
    },
    {
      id: 'modernisierung', photo: 'reparatur-vor-ort', label: 'Modernisieren', title: 'Neue Technik, bewährter Stahl',
      text: 'Ist der Stahlbau gut, bringen Funkfernsteuerung, Frequenzumrichter, Überlastsicherung und neue Steuerung den Kran auf den Stand der Technik.',
      cta: anfrage('Modernisierung anfragen'),
    },
  ],
};

/** Die Prüfpflicht – drei Sätze an einer Haarlinie (FactGrid), Einzelheiten im Ratgeber. */
export const inspectionDuty = {
  title: 'Was die Prüfpflicht verlangt.',
  lead: 'Nach Kranverordnung und EKAS-Richtlinie 6511. Mehr im Ratgeber [Kranprüfung in der Schweiz](/ratgeber/kranpruefung-schweiz).',
  items: [
    { icon: 'clipboard-check' as IconName, title: 'Jeder Kran', text: 'Regelmässige Überprüfung nach Herstellervorgabe durch Kranfachleute. Das übernehmen wir.' },
    { icon: 'file-text' as IconName, title: 'Kranbuch', text: 'Zu jedem Kran gehört ein Kranbuch. Wir führen es nach, digital.' },
    { icon: 'shield-check' as IconName, title: 'Fahrzeug- und Turmdrehkrane', text: 'Zusätzlich die periodische Kontrolle durch einen von der Suva anerkannten Kranexperten – sie gehört nicht zu unserem Angebot.' },
  ],
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
  title: 'Heukrananlagen planen, bauen, betreuen',
  description:
    'Heukrananlagen ohne Kabine, bedient per Funk: betreuen, umbauen, neu planen. Saison-Check, Reparatur, Ersatzteile – die erste Inspektion ist gratis.',
  hero: {
    eyebrow: 'Krantechnik · Heukrananlagen',
    h1: 'Heukrane, gebaut für ==Ihre Scheune==.',
    lead:
      'Seit {{history.cranesSince}} bauen wir Heukrane nach Mass für Ihre Scheune – ohne Kabine, bedient per Funk. Bestehende Anlagen betreuen wir weiter; die erste Inspektion ist gratis.',
    photo: 'heukran-einsatz',
    primary: anfrage('Anfrage stellen'),
  },
  summary:
    '{{brand.name}} betreut Heukrananlagen: Saison-Check, Wartung, Reparatur, Ersatzteile und Modernisierung – auch für alle bestehenden HS-Krananlagen. Die erste Inspektion ist gratis. Unsere Heukrane haben keine Kabine: Sie steuern per Funk, vom Boden, vom Wagen oder vom Heustock aus. Neue Anlagen planen und bauen wir auf Anfrage nach Mass: Einschienenkrane, Brückenkrane, hydraulische Drehkrane und Anlagen, die an das Gebäude angepasst sind – auch um Ecken, über Steigungen und Versätze. Nicht zufrieden, übernehmen wir 50 %. Der Standort ist in {{address.home}}.',
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
      { title: 'Saison-Check', text: 'Kranbahn, Fahrwerke, Seil, Greifer, Hydraulik und Elektrik prüfen – im Frühling vor der Ernte oder im Spätherbst danach.' },
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
      a: 'Im Frühling vor dem ersten Schnitt, wenn der Heustock fast leer ist – oder im Spätherbst, wenn das Heu drin ist und das Vieh noch auf der Weide. Dann bleibt Zeit für Reparaturen.',
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

/**
 * Funk statt Kabine (Anker #funk) – direkt nach dem Kopf der Heukrananlagen, gesetzt wie die Garantien
 * (components/kran/RadioControl.astro → home/Stagger), dazu das Foto `heukran-funk`.
 */
export const radioControl = {
  title: 'Ohne Kabine. Mit dem ==besten Blick==.',
  lead: 'Unsere Heukrane bedienen Sie per Funk – vom Boden, vom Wagen oder vom Heustock aus. Das kann jeder im Betrieb, auch wer nicht schwindelfrei ist.',
  photo: 'heukran-funk',
  sight: 'funk-sicht',
  a: { label: 'Funk statt Kabine', title: 'Sender in die Hand – und der Kran läuft.' },
  b: { label: 'Beste Sicht', title: 'Sie sehen genau, was der Greifer packt.' },
  c: { label: 'Allein abladen', title: 'Wagen hinein, absteigen, abladen.' },
};

/** Module der Heukran-Seite. */
export const heukranModules = {
  /** Bauformen (Anker #neuanlage) – alle vier auf einen Blick wie die Situationen (Magazine + PhotoCard). */
  forms: {
    title: 'Bauformen',
    lead: 'Vier Bauformen, alle ohne Kabine und per Funk bedient.',
    items: [
      { label: 'Einschiene', title: 'Einschienenkran', illo: 'heukran-einschiene', text: 'Der Kran fährt auf einer Laufschiene unter dem Dach. Für lange, schmale Scheunen mit einem Heustock entlang der Fahrbahn.' },
      { label: 'Brücke', title: 'Brückenkran', illo: 'heukran-bruecke', text: 'Eine Kranbrücke fährt über die ganze Breite, die Katze quer dazu. Für breite Scheunen mit mehreren Stöcken oder Abladeplätzen.' },
      { label: 'Drehkran', title: 'Drehkran, hydraulisch', illo: 'heukran-drehkran', text: 'Ein Drehturm mit Ausleger fährt längs und quer und dreht sich – der Greifer erreicht auch Ecken und Nischen.' },
      { label: 'Angepasst', title: 'An das Gebäude angepasst', illo: 'heukran-angepasst', text: 'Fahrbahn, Stützen und Spannweite folgen dem Bau – auch um Ecken, über Steigungen und Versätze. Mehr unter [Krane nach Mass](/krantechnik/krane-nach-mass).' },
    ],
    missing: { title: 'Welche passt zu Ihrer Scheune?', text: 'Das klären wir bei der Besichtigung gemeinsam – mit Blick auf Gebäude, Heustock und Ihre Arbeit.', cta: { label: 'Neuanlage anfragen', href: '#anfrage' } },
  },
  steps: {
    title: 'So läuft es ab.',
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
    title: 'Saison-Check in den ruhigen Wochen.',
    text: 'Ihr Heukran arbeitet das ganze Jahr: Im Sommer lagern Sie ein, im Winter holen Sie heraus. Ruhig wird es zweimal – im Frühling vor dem ersten Schnitt und im Spätherbst, wenn das Heu drin ist und das Vieh noch auf der Weide. Dann prüfen wir Kranbahn, Fahrwerke, Seil, Greifer, Hydraulik und Elektrik – und ersetzen, was nicht mehr hält.',
    kinds: [
      { icon: 'wrench' as IconName, word: 'Check', legend: 'Frühling und Spätherbst: Saison-Check', dark: true },
      { icon: 'sun' as IconName, word: 'Einlagern', legend: 'Sommer: Sie lagern ein' },
      { icon: 'snowflake' as IconName, word: 'Füttern', legend: 'Winter: Sie holen heraus' },
    ],
    plan: [2, 2, 0, 0, 1, 1, 1, 1, 1, 0, 0, 2],
    cta: 'Saison-Check planen',
  },
};

/** Alle Unterseiten des Bereichs, in der Reihenfolge der Navigation. */
export const krantechnikPages = [kraneNachMass, kranservice, heukrananlagen];
