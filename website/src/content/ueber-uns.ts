/**
 * Über uns (Entwurf Oktober 2026): Kopf · ein Betrieb aus der Praxis (Zahlen) · drei Bereiche ·
 * Geschichte als Weg · die Übergabe (zwei Menschen, Texte teils in content/uebergabe.ts) · Werte ·
 * Garantien · mehr von uns · Fragen. Der Standort steht im Kontaktbereich (Karte).
 * Der Ort kommt aus dem ERP ({{erp.city}}, #1146/#1153).
 */
import type { Faq } from './types';

export const ueberUns = {
  title: 'Über uns',
  description:
    'INEXXIO (ehemals HS Steiner) in {{address.home}}: Betrieb mit Ingenieurwissen seit 1982 – Team, Werte, Geschichte und die Nachfolge von Heiri Steiner.',
  hero: {
    h1: 'Über uns',
    lead:
      'Seit {{history.founded}} bauen und betreuen wir in {{address.city}} Krane, Fahrzeuge und Maschinen – heute als {{brand.name}}, mit Ingenieurwissen aus dem Maschinenbau.',
  },
  /** Ein Betrieb aus der Praxis – das WIR, dazu vier belegte Zahlen (keine erfundenen). */
  team: {
    title: 'Ein Betrieb aus der Praxis',
    text: 'Hinter {{brand.name}} steht ein Team aus Mechanik, Schweiss- und Stahlbau und Konstruktion. Jede Anlage entsteht gemeinsam – von der ersten Skizze bis zum Service.',
    figures: [
      { figure: '{{history.founded}}', text: 'Gegründet von Heiri Steiner in {{address.town}}' },
      { figure: '{{history.cranesSince}}', text: 'Die erste eigene Krananlage' },
      { figure: '3', text: 'Bereiche: Krantechnik, Fahrzeugtechnik, Speziallösungen' },
      { figure: 'CH · DE · AT', text: 'Im Einsatz – und darüber hinaus, wo Sie uns brauchen' },
    ],
  },
  /** Die Geschichte als Weg (Baustein SolutionPath) – die Jahre stehen gross daneben. */
  history: {
    title: 'Über 40 Jahre, ein Betrieb',
    start: '{{address.town}}',
    end: 'Heute: {{brand.name}}',
    items: [
      { no: '{{history.founded}}', icon: 'wrench' as const, who: 'Gründung', title: 'Ein Reparaturbetrieb', text: '{{history.foundedText}}' },
      { no: '{{history.cranesSince}}', icon: 'hard-hat' as const, who: 'Krane', title: 'Die erste eigene Krananlage', text: '{{history.cranesText}}' },
      { no: '{{history.gmbhYear}}', icon: 'flag' as const, who: 'Firma', title: '{{brand.formerLegalName}}', text: 'Aus dem Einzelbetrieb wird eine GmbH – mit Kunden, die über Jahrzehnte bleiben.' },
      { no: 'Heute', icon: 'handshake' as const, who: 'Nachfolge', title: 'Aus HS Steiner wird {{brand.name}}', text: 'Heiri Steiner übergibt an Clemens Fritsche. Standort, Telefonnummer und der Service für alle HS-Krananlagen bleiben.' },
    ],
  },
  /** Die Übergabe – ein grosses Bild (der Handschlag), Heiris Zitat, Clemens' Botschaft, kurz was bleibt und was neu ist. */
  people: {
    title: 'Ein Handschlag zwischen zwei Generationen',
    /** Zitat von Heiri Steiner – in seinen Worten, freigegeben mit Testnotiz #1097. */
    quote:
      'Über 40 Jahre war dieser Betrieb mein Leben. Ich gebe ihn mit gutem Gefühl weiter: Clemens bringt neues Wissen mit und hat Respekt vor dem, was hier gewachsen ist. Meine Kunden sind bei ihm in guten Händen.',
    message: [
      'Ich bin Maschinenbauingenieur, habe bei Liebherr Bohrgeräte mitentwickelt und danach vernetzte Maschinen und Plattformen verantwortet. Als ich Heiri kennengelernt habe, war schnell klar: Hier stimmt die Basis – treue Kunden, solide Anlagen, ehrliches Handwerk.',
      'Was Heiri in {{history.experienceDative}} aufgebaut hat, führe ich mit derselben Sorgfalt weiter – und ergänze es dort, wo es Ihnen nützt.',
    ],
    stays: 'Standort · Telefonnummer · Service für HS-Anlagen',
    news: 'Der Name {{brand.name}} · Ingenieurwissen · Speziallösungen',
  },
  /** Mehr über uns – die Unterseiten von «Über uns», wie im Menü. */
  more: {
    title: 'Mehr von uns',
    items: [
      { href: '/ratgeber', illo: 'ratgeber' as const, title: 'Ratgeber', text: 'Kurz erklärt: Prüfpflicht, Heukran planen, Verschleiss.' },
      { href: '/karriere', illo: 'karriere' as const, title: 'Karriere', text: 'Arbeiten bei {{brand.name}} in {{address.city}}.' },
    ],
  },
  summary:
    '{{brand.full}} arbeitet in drei Bereichen: Krantechnik, Fahrzeugtechnik und Speziallösungen. Wir bauen und betreuen Krane, tauschen Trommeln von Fahrmischern und bauen Spezialmaschinen für den Bau. Der Standort ist in {{erp.city}}. Mit der Übergabe von Heiri Steiner an Clemens Fritsche wird aus der {{brand.formerLegalName}} die {{brand.legalName}} – derselbe Standort, dieselbe Telefonnummer, derselbe Service für alle bestehenden Anlagen.',
  /** Die Werte der Firma (#1182) – wofür wir stehen; die Zusagen darunter machen sie prüfbar. */
  values: {
    title: 'Wofür wir stehen',
    /** Locker gesetzt: das Wort gross, der halbe Satz dahinter leise – kein Raster, keine Symbole. */
    items: [
      { title: 'Verbindlichkeit.', text: 'Gesagt ist gemacht.' },
      { title: 'Qualität.', text: 'Lieber einmal richtig.' },
      { title: 'Zuverlässigkeit.', text: 'Steht etwas still, sind wir da.' },
      { title: 'Innovation.', text: 'Neues Leben für gute Maschinen.' },
      { title: 'Design.', text: 'Schön ist, was gut funktioniert.' },
    ],
  },
  /** Die Zusagen – Über uns und /service zeigen dieselbe Liste (vorher stand «So arbeiten wir» daneben). */
  promises: {
    title: 'Worauf Sie sich verlassen können',
    lead: 'Konkrete Zusagen statt schöner Worte – dazu die Zufriedenheitsgarantie: Nicht zufrieden? Die Hälfte übernehmen wir.',
    items: [
      { title: 'Verbindliche Offerte vor jeder Arbeit', text: 'Sie wissen vorher, was es kostet. Auf der Rechnung steht keine Überraschung.' },
      { title: 'Keine Mindestlaufzeit', text: 'Sie bleiben, weil es passt – nicht, weil ein Vertrag Sie hält.' },
      { title: 'Rückmeldung', text: 'Wir melden uns innert {{promises.responseTime}}.' },
      { title: 'Protokoll', text: 'Jeder Einsatz dokumentiert, mit Protokoll.' },
      { title: 'Ersatzteile', text: 'Die Ersatzteile für unsere Krananlagen liegen an Lager, oder wir fertigen sie neu an.' },
    ],
  },
  areaFaq: [
    {
      q: 'Kommen Sie auch ins Ausland?',
      a: 'Ja. Zuerst in Deutschland und Österreich, darüber hinaus dort, wo Sie uns brauchen – geplant und zuverlässig. Fragen Sie an.',
    },
    {
      q: 'Kostet die Anfahrt extra?',
      a: 'Die Anfahrt steht in der Offerte, den Sie vor der Arbeit erhalten – auf der Rechnung steht keine Überraschung.',
    },
  ] satisfies Faq[],
};
