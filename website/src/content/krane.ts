/**
 * Krane – Übersicht und vier Leistungsseiten (Auftrag Kap. 7.3).
 * Struktur jeder Seite: siehe ServicePage und layouts/Service.astro.
 */
import { site } from '../config/site.mjs';
import type { Faq, ServicePage } from './types';

const parent = { name: 'Krane', path: '/krane' };
const anfrage = (label: string) => ({ label, href: '#anfrage' });

const steps = {
  anfrage: { title: 'Anfrage', text: 'Sie nennen Kranart, Hersteller und Standort – per Formular oder am Telefon.' },
  termin: { title: 'Termin', text: 'Wir schlagen einen Termin vor, der Ihren Betrieb möglichst wenig stört.' },
  bericht: { title: 'Bericht', text: 'Sie erhalten einen Bericht; der Eintrag steht im Kranbuch.' },
};

const faqHsCare: Faq = {
  q: 'Wer betreut meinen HS-Kran in Zukunft?',
  a: 'Wir. Service und Ersatzteile für HS-Krananlagen führen wir weiter, mit demselben Wissen und denselben Teilen ab Lager.',
};
const faqSpeed: Faq = {
  q: 'Wie schnell sind Sie vor Ort?',
  a: '{{promises.reactionTime}} Steht eine Anlage still, rufen Sie am besten direkt an: {{phone.link}}.',
};

/* ------------------------------------------------------------------ Übersicht */
export const krane: ServicePage & { services: { href: string; label: string; text: string }[] } = {
  path: '/krane',
  crumb: 'Krane',
  title: 'Kranservice für alle Marken',
  description:
    'Prüfung, Wartung, Reparatur und Modernisierung für Brücken-, Hänge-, Dreh- und Heukrane aller Marken in der Ostschweiz. Teile ab Lager. Jetzt anfragen.',
  og: 'krane',
  hero: {
    eyebrow: 'Krane',
    h1: 'Kranservice in der Ostschweiz – für alle Marken',
    lead:
      'Ob Brückenkran in der Produktionshalle oder Heukran in der Scheune: Wir prüfen, warten, reparieren und modernisieren Krane – und betreuen weiterhin alle HS-Krananlagen.',
    photo: 'arbeit-werkstatt',
    primary: anfrage('Kranservice anfragen'),
  },
  summary:
    '{{brand.full}} prüft, wartet, repariert und modernisiert Krane aller Marken – Brücken-, Hänge-, Schwenk- und Drehkrane in Industrie und Gewerbe sowie Heukrane in der Landwirtschaft. Seit {{history.cranesSince}} bauen wir in Tuttwil auch eigene Krananlagen.',
  glance: {
    forWhom: 'Industrie- und Gewerbebetriebe mit Hallenkranen, Landwirtschaftsbetriebe mit Heukranen, Gemeinden.',
    what: 'Prüfung, Wartung, Reparatur, Modernisierung, Ersatzteile – und neue Krananlagen auf Anfrage.',
    speed: '{{promises.reactionTime}}',
    deliverables: 'Einen Bericht zu jeder Arbeit und den Eintrag ins Kranbuch.',
  },
  services: site.nav[0].children!.map((c) => ({ href: c.href, label: c.label, text: c.text })),
  scope: {
    title: 'Welche Krane wir betreuen',
    lead: 'Krane aller Hersteller – nicht nur die Anlagen aus unserer eigenen Werkstatt.',
    items: [
      { title: 'Brückenkrane', text: 'Ein- und Zweiträger-Brückenkrane in Produktions- und Lagerhallen.' },
      { title: 'Hängekrane', text: 'Unter der Hallendecke aufgehängt – für Hallen ohne Kranbahnstützen.' },
      { title: 'Schwenkkrane', text: 'Säulen- und Wandschwenkkrane direkt am Arbeitsplatz.' },
      { title: 'Drehkrane', text: 'Elektrisch oder hydraulisch, im Werkhof und in der Landwirtschaft.' },
      { title: 'Heukrane und HS-Krananlagen', text: 'Alle Anlagen aus Tuttwil – Service, Ersatzteile und Saison-Check.' },
    ],
  },
  steps: [
    steps.anfrage,
    steps.termin,
    { title: 'Arbeit vor Ort', text: 'Kranfachleute prüfen, warten oder reparieren – mit den nötigen Teilen im Fahrzeug.' },
    steps.bericht,
  ],
  faq: [
    {
      q: 'Betreuen Sie Krane aller Hersteller?',
      a: 'Ja. Wir arbeiten an Kranen aller Marken – nicht nur an den HS-Krananlagen aus unserer eigenen Werkstatt.',
    },
    faqHsCare,
    {
      q: 'Wie oft muss ein Kran geprüft werden?',
      a: 'Alle Krane regelmässig, nach den Angaben des Herstellers, durch Kranfachleute. Für Fahrzeug- und Turmdrehkrane gelten zusätzlich feste Fristen. Die Übersicht steht auf der Seite [Kranprüfung und Wartung](/krane/pruefung-wartung). [[PRÜFEN: fachlich]]',
    },
    faqSpeed,
    {
      q: 'Bauen Sie auch neue Krananlagen?',
      a: 'Ja, auf Anfrage – vom Heukran bis zur Anlage, die auf ein bestehendes Gebäude abgestimmt ist. [[PRÜFEN: Umfang Neuanlagen]]',
    },
  ],
  cta: {
    title: 'Kranservice anfragen',
    lead: 'Nennen Sie Kranart, Hersteller und Standort. Wir melden uns innert {{promises.responseTime}}.',
    kind: 'kran',
  },
  related: [
    { href: '/service-abo', label: 'Service-Abo und digitales Kranbuch', text: 'Prüfung und Wartung zum Fixpreis pro Kran und Jahr.' },
    { href: '/fahrmischer', label: 'Fahrmischer', text: 'Service, Reparatur und Verschleissteile für alle gängigen Marken.' },
    { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Wer muss wann was prüfen?', kind: 'ratgeber' },
  ],
  service: { name: 'Kranservice', serviceType: 'Prüfung, Wartung, Reparatur und Modernisierung von Kranen' },
};

/* ------------------------------------------------------------------ Prüfung & Wartung */
export const pruefung: ServicePage = {
  path: '/krane/pruefung-wartung',
  crumb: 'Prüfung & Wartung',
  title: 'Kranprüfung und Kranwartung',
  description:
    'Kranprüfung und Wartung für Brücken-, Hänge-, Dreh- und Heukrane aller Marken in der Ostschweiz – mit Prüfbericht und Kranbuch. Jetzt Termin anfragen.',
  og: 'krane',
  parent,
  hero: {
    eyebrow: 'Krane · Prüfung & Wartung',
    h1: 'Kranprüfung und Wartung für Hallen- und Heukrane',
    lead:
      'Wir prüfen und warten Krane aller Marken nach den Angaben des Herstellers – mit Prüfbericht und Eintrag ins Kranbuch. So ist die Prüfpflicht erfüllt, und der Kran läuft, wenn Sie ihn brauchen.',
    photo: 'pruefung-hallenkran',
    primary: anfrage('Prüfung anfragen'),
  },
  summary:
    '{{brand.full}} prüft und wartet Krane aller Marken in der Ostschweiz: Brücken-, Hänge-, Schwenk- und Drehkrane in Industrie und Gewerbe sowie Heukrane in der Landwirtschaft. Jede Prüfung endet mit einem Bericht und einem Eintrag ins Kranbuch.',
  glance: {
    forWhom: 'Betriebe mit Hallen-, Werkhof- oder Heukranen – vom Gewerbebetrieb bis zum Bauernhof.',
    what:
      'Überprüfung nach Herstellerangaben, Wartung, Schmierung und Verschleiss-Check durch Kranfachleute. [[PRÜFEN: Qualifikation der Kranfachleute im Team bestätigen]]',
    speed:
      'Termin nach Absprache; mit dem Service-Abo erinnern wir Sie jedes Jahr von selbst. [[PLATZHALTER: übliche Vorlaufzeit für Prüftermine]]',
    deliverables: 'Prüfbericht und Eintrag ins Kranbuch – auf Papier oder digital.',
  },
  scope: {
    title: 'Was wir prüfen und warten',
    lead: 'Je nach Kranart und Angaben des Herstellers. [[PRÜFEN: fachlich – Leistungsumfang]]',
    items: [
      { title: 'Tragwerk und Kranbahn', text: 'Risse, Verformungen und lose Verbindungen; Zustand von Schienen, Puffern und Endanschlägen.' },
      { title: 'Hubwerk, Seil und Kette', text: 'Seil oder Kette, Haken und Hakensicherung, Bremse und Getriebe.' },
      { title: 'Fahrwerke', text: 'Laufräder, Antriebe und Bremsen von Katze und Kranbrücke.' },
      { title: 'Elektrik und Steuerung', text: 'Endschalter, Not-Halt, Hängetaster oder Funkfernsteuerung, Kabel und Stromzuführung.' },
      { title: 'Sicherheitseinrichtungen', text: 'Überlastsicherung, Schutzeinrichtungen, Beschilderung und Tragfähigkeitsangaben.' },
      { title: 'Wartung', text: 'Schmieren, nachstellen, Verschleissteile ersetzen – nach Vorgabe des Herstellers.' },
    ],
  },
  steps: [
    steps.anfrage,
    steps.termin,
    { title: 'Prüfung vor Ort', text: 'Kranfachleute prüfen und warten den Kran nach den Angaben des Herstellers.' },
    { title: 'Bericht', text: 'Sie erhalten den Prüfbericht; der Eintrag steht im Kranbuch.' },
  ],
  faq: [
    {
      q: 'Wie oft muss ich meinen Hallenkran prüfen lassen?',
      a: 'Regelmässig, nach den Angaben des Herstellers – in der Praxis meist einmal im Jahr. Massgebend sind die Betriebsanleitung und die Vorgaben der Suva. [[PRÜFEN: fachlich]]',
    },
    {
      q: 'Prüfen Sie auch Krane anderer Hersteller?',
      a: 'Ja. Wir prüfen und warten Krane aller Marken – nicht nur HS-Krananlagen.',
    },
    {
      q: 'Was steht im Prüfbericht?',
      a: 'Was geprüft wurde, in welchem Zustand der Kran ist und was zu beheben ist. Der Bericht gehört ins Kranbuch. [[PRÜFEN: Inhalt des Prüfberichts]]',
    },
    {
      q: 'Darf das Kranbuch digital sein?',
      a: 'Ja. Die Form des Kranbuchs ist frei – Papier oder digital. Mit dem [Service-Abo](/service-abo) führen wir es digital, abrufbar per QR-Code am Kran. [[PRÜFEN: fachlich und Verfügbarkeit des digitalen Kranbuchs]]',
    },
    {
      q: 'Machen Sie auch die Kontrolle durch den Kranexperten?',
      a: 'Die periodische Kontrolle von Fahrzeug- und Turmdrehkranen macht ein von der Suva anerkannter Kranexperte. Wir übernehmen die Überprüfung durch Kranfachleute und die Wartung. Den Unterschied erklärt unser Ratgeber [Kranfachmann oder Kranexperte?](/ratgeber/kranfachmann-kranexperte) [[PRÜFEN: fachlich – Abgrenzung zum Kranexperten]]',
    },
    {
      q: 'Was kostet eine Kranprüfung?',
      a: 'Das hängt von Kranart, Grösse und Anfahrt ab. Fragen Sie uns an – oder wählen Sie das [Service-Abo](/service-abo) zum Fixpreis pro Kran und Jahr. [[PLATZHALTER: Preisrahmen für eine Kranprüfung]]',
    },
  ],
  cta: {
    title: 'Prüfung anfragen',
    lead: 'Nennen Sie Kranart, Hersteller und Standort. Wir melden uns innert {{promises.responseTime}}.',
    kind: 'kran',
    need: 'pruefung',
  },
  related: [
    { href: '/service-abo', label: 'Service-Abo und digitales Kranbuch', text: 'Prüfung und Wartung zum Fixpreis pro Kran und Jahr.' },
    { href: '/krane/reparatur', label: 'Reparatur und Pikett', text: 'Wenn bei der Prüfung ein Mangel auftaucht oder der Kran steht.' },
    { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Wer muss wann was prüfen?', kind: 'ratgeber' },
  ],
  service: { name: 'Kranprüfung und Kranwartung', serviceType: 'Kranprüfung' },
};

/* ------------------------------------------------------------------ Reparatur & Pikett */
export const reparatur: ServicePage = {
  path: '/krane/reparatur',
  crumb: 'Reparatur & Pikett',
  title: 'Kranreparatur und Pikett',
  description:
    'Kran steht still? Reparatur von Hallen- und Heukranen aller Marken in der Ostschweiz, Ersatzteile ab Lager in Tuttwil, Pikett für Notfälle. Rufen Sie an.',
  og: 'krane',
  parent,
  hero: {
    eyebrow: 'Krane · Reparatur & Pikett',
    h1: 'Kranreparatur: wenn der Kran stillsteht',
    lead:
      'Wir finden die Ursache, reparieren vor Ort und haben viele Teile an Lager. Ein Foto vom Typenschild oder vom Schaden hilft, schneller zu helfen.',
    photo: 'reparatur-vor-ort',
    primary: anfrage('Störung melden'),
  },
  summary:
    '{{brand.full}} repariert Krane aller Marken in der Ostschweiz – Hallen-, Werkhof- und Heukrane, auch HS-Krananlagen. Viele Ersatzteile liegen in Tuttwil an Lager; für Notfälle gibt es ein Pikett.',
  glance: {
    forWhom: 'Betriebe, deren Kran ausgefallen ist oder nicht mehr sicher läuft.',
    what: 'Fehlersuche, Reparatur vor Ort, Ersatzteile ab Lager oder auf Bestellung, Funktionsprüfung nach der Reparatur.',
    speed: '{{promises.reactionTime}}',
    deliverables: 'Rapport mit Ursache, ausgeführten Arbeiten und verbauten Teilen; Eintrag ins Kranbuch.',
  },
  scope: {
    title: 'Was wir reparieren',
    lead: 'An Kranen aller Hersteller. [[PRÜFEN: fachlich – Leistungsumfang]]',
    items: [
      { title: 'Hubwerk', text: 'Seil- und Kettenzüge, Bremsen, Getriebe und Motoren.' },
      { title: 'Fahrwerke', text: 'Laufräder, Antriebe und Bremsen von Katze und Kranbrücke.' },
      { title: 'Elektrik und Steuerung', text: 'Schaltschrank, Schütze, Endschalter, Hängetaster und Funkfernsteuerung.' },
      { title: 'Hydraulik', text: 'Bei hydraulischen Drehkranen: Zylinder, Schläuche, Ventile und Pumpen.' },
      { title: 'Greifer', text: 'Zinken, Bolzen, Lager und Hydraulik – bei Heukranen das Teil, das am meisten arbeitet.' },
      { title: 'Tragwerk und Kranbahn', text: 'Schäden am Stahlbau und an der Kranbahn begutachten und instand stellen.' },
    ],
  },
  steps: [
    { title: 'Anruf oder Anfrage', text: 'Sie beschreiben den Fehler – am besten mit einem Foto vom Typenschild oder vom Schaden.' },
    { title: 'Einsatz planen', text: 'Wir klären, welche Teile es braucht, und bringen sie mit.' },
    { title: 'Reparatur vor Ort', text: 'Wir beheben den Fehler und prüfen danach die Sicherheitsfunktionen.' },
    { title: 'Rapport', text: 'Sie erhalten einen Rapport; der Eintrag steht im Kranbuch.' },
  ],
  faq: [
    {
      q: 'Was tue ich, wenn der Kran stehen bleibt?',
      a: 'Den Kran ausser Betrieb nehmen und sichern, die Last – wenn möglich – sicher absetzen und uns anrufen: {{phone.link}}. Nicht unter Last weiterarbeiten. [[PRÜFEN: fachlich – Verhalten bei einer Störung]]',
    },
    {
      q: 'Haben Sie Ersatzteile an Lager?',
      a: 'Für HS-Krananlagen viele: Greifer, Ausleger, Fahrwerke, Drehtürme und Verschleissteile. Für andere Hersteller bestellen wir, was fehlt. [[PRÜFEN: Lager für andere Hersteller]]',
    },
    {
      q: 'Reparieren Sie auch Krane anderer Hersteller?',
      a: 'Ja, Krane aller Marken.',
    },
    faqSpeed,
    ...(site.features.pikett
      ? [{
          q: 'Gibt es einen Notdienst ausserhalb der Bürozeiten?',
          a: 'Für Notfälle gibt es ein Pikett: {{pikett.link}}. {{pikett.hours}} {{pikett.review}}',
        }]
      : []),
  ],
  cta: {
    title: 'Störung melden',
    lead: 'Beschreiben Sie kurz, was passiert ist. Eilt es, rufen Sie besser an.',
    kind: 'kran',
    need: 'stoerung',
    messageLabel: 'Was ist passiert?',
    pikettFirst: true,
  },
  related: [
    { href: '/krane/hs-krananlagen', label: 'HS-Krananlagen', text: 'Ersatzteile und Service für Krane aus Tuttwil.' },
    { href: '/krane/modernisierung', label: 'Modernisierung', text: 'Wenn Steuerung oder Antrieb in die Jahre gekommen sind.' },
    { href: '/ratgeber/heukran-saison-check', label: 'Heukran-Saison-Check', text: 'Ausfälle vermeiden, bevor die Ernte beginnt.', kind: 'ratgeber' },
  ],
  service: { name: 'Kranreparatur und Pikett', serviceType: 'Kranreparatur' },
};

/* ------------------------------------------------------------------ Modernisierung */
export const modernisierung: ServicePage = {
  path: '/krane/modernisierung',
  crumb: 'Modernisierung',
  title: 'Kran modernisieren',
  description:
    'Älteren Kran modernisieren: Funkfernsteuerung, Frequenzumrichter, Überlastsicherung und neue Steuerung für Hallen- und Heukrane aller Marken. Jetzt anfragen.',
  og: 'krane',
  parent,
  hero: {
    eyebrow: 'Krane · Modernisierung',
    h1: 'Kran modernisieren statt ersetzen',
    lead:
      'Ein guter Stahlbau hält Jahrzehnte – Steuerung und Antrieb oft nicht. Wir rüsten ältere Krane nach: sicherer, ruhiger und einfacher zu bedienen.',
    photo: 'steuerung-funk',
    primary: anfrage('Modernisierung anfragen'),
  },
  summary:
    '{{brand.full}} modernisiert ältere Krane aller Marken: Funkfernsteuerung, Frequenzumrichter, Überlastsicherung, Steuerung, Endschalter und Greifer. Vorher klären wir vor Ort, was sich lohnt.',
  glance: {
    forWhom: 'Betriebe mit älteren Hallen- oder Heukranen, deren Steuerung oder Antrieb an Grenzen stösst.',
    what: 'Bestandsaufnahme, Offerte, Umbau, Inbetriebnahme und Dokumentation.',
    speed: 'Nach Bestandsaufnahme und Offerte; Teile mit Lieferfrist planen wir ein. [[PLATZHALTER: typische Dauer eines Umbaus]]',
    deliverables: 'Umbau mit Unterlagen und Eintrag ins Kranbuch. [[PRÜFEN: Umfang der Dokumentation]]',
  },
  scope: {
    title: 'Was wir nachrüsten',
    lead: 'Je Punkt der Nutzen in einem Satz. [[PRÜFEN: fachlich – Leistungsumfang]]',
    items: [
      { title: 'Funkfernsteuerung', text: 'Wer bedient, steht dort, wo er die Last sieht – nicht dort, wo das Kabel endet.' },
      { title: 'Frequenzumrichter', text: 'Sanftes Anfahren und Bremsen: Die Last pendelt weniger, Getriebe und Bremsen verschleissen langsamer.' },
      { title: 'Überlastsicherung', text: 'Verhindert, dass mehr gehoben wird, als der Kran tragen darf.' },
      { title: 'Steuerung', text: 'Neue Schaltschränke und Komponenten, für die es wieder Ersatzteile gibt.' },
      { title: 'Endschalter', text: 'Begrenzen Hub- und Fahrwege zuverlässig und schützen Kran und Gebäude.' },
      { title: 'Greifer', text: 'Ein neuer oder überholter Greifer – bei Heukranen das Teil, das am meisten arbeitet.' },
    ],
  },
  steps: [
    { title: 'Anfrage', text: 'Sie schildern, was stört, und schicken ein Foto vom Typenschild.' },
    { title: 'Bestandsaufnahme', text: 'Wir schauen den Kran vor Ort an und offerieren, was sich lohnt.' },
    { title: 'Umbau', text: 'Wir bauen um, nehmen in Betrieb und prüfen die Sicherheitsfunktionen.' },
    { title: 'Dokumentation', text: 'Sie erhalten die Unterlagen; der Umbau steht im Kranbuch.' },
  ],
  faq: [
    {
      q: 'Lohnt sich eine Modernisierung bei einem alten Kran?',
      a: 'Oft ja: Der Stahlbau hält meist viel länger als Steuerung und Antrieb. Ob es sich lohnt, zeigt die Bestandsaufnahme – ist ein neuer Kran die bessere Lösung, sagen wir das. [[PRÜFEN: fachlich]]',
    },
    {
      q: 'Kann man jeden Kran mit Funk nachrüsten?',
      a: 'Die meisten Brücken-, Hänge- und Drehkrane ja. Vor Ort klären wir, welche Steuerung vorhanden ist und was es dafür braucht. [[PRÜFEN: fachlich]]',
    },
    {
      q: 'Was bringt ein Frequenzumrichter?',
      a: 'Er lässt die Motoren sanft anfahren und abbremsen. Die Last pendelt weniger, Getriebe, Bremsen und Kranbahn werden geschont.',
    },
    {
      q: 'Rüsten Sie auch Krane anderer Hersteller um?',
      a: 'Ja, Krane aller Marken.',
    },
    {
      q: 'Was ändert sich mit der neuen EU-Maschinenverordnung?',
      a: 'Sie gilt in der EU ab dem 20. Januar 2027; die Schweiz passt ihre Maschinenverordnung an. Wer eine Maschine wesentlich verändert, braucht saubere Unterlagen. [[PRÜFEN: fachlich – Übernahme durch die Schweiz und Folgen für Umbauten]]',
    },
  ],
  cta: {
    title: 'Modernisierung anfragen',
    lead: 'Schreiben Sie, was stört – ein Foto vom Typenschild hilft bei der ersten Einschätzung.',
    kind: 'kran',
    need: 'modernisierung',
  },
  related: [
    { href: '/krane/reparatur', label: 'Reparatur und Pikett', text: 'Wenn der Kran heute schon stillsteht.' },
    { href: '/service-abo', label: 'Service-Abo', text: 'Mit jährlichem Modernisierungs-Check in der Stufe «Komplett».' },
    { href: '/ratgeber/kranpruefung-schweiz', label: 'Kranprüfung in der Schweiz', text: 'Was die Prüfpflicht nach einem Umbau verlangt.', kind: 'ratgeber' },
  ],
  service: { name: 'Kranmodernisierung', serviceType: 'Modernisierung von Krananlagen' },
};

/** Hinweis EU-Maschinenverordnung (Modul der Modernisierungsseite). */
export const machineryNote = {
  title: 'Umbauten sauber dokumentieren',
  text: [
    'Ab dem 20. Januar 2027 gilt in der EU die neue Maschinenverordnung (EU) 2023/1230. Die Schweiz revidiert ihre Maschinenverordnung, damit die Regeln gleichwertig und gleichzeitig gelten.',
    'Wer eine Maschine wesentlich verändert, übernimmt dafür Verantwortung – und braucht saubere Unterlagen: was umgebaut wurde, mit welchen Teilen, mit welchen Einstellungen. Diese Unterlagen liefern wir mit jedem Umbau. [[PRÜFEN: fachlich – wesentliche Veränderung, Übernahme durch die Schweiz, Folgen für Umbauten]]',
  ],
  sources: [
    { label: 'SECO: Maschinen', href: 'https://www.seco.admin.ch/de/maschinen' },
    { label: 'Verordnung (EU) 2023/1230 über Maschinen, EUR-Lex', href: 'https://eur-lex.europa.eu/eli/reg/2023/1230/oj' },
  ],
};

/* ------------------------------------------------------------------ HS-Krananlagen */
export const hsKrananlagen: ServicePage = {
  path: '/krane/hs-krananlagen',
  crumb: 'HS-Krananlagen',
  title: 'HS-Krananlagen und Heukrane',
  description:
    'Service, Ersatzteile und Saison-Check für HS-Krananlagen und Heukrane – aus der Werkstatt, in der sie entstanden sind. Teile ab Lager, Neuanlagen auf Anfrage.',
  og: 'krane',
  parent,
  hero: {
    eyebrow: 'Krane · HS-Krananlagen',
    h1: 'HS-Krananlagen: Service und Ersatzteile für Ihren Heukran',
    lead:
      'Seit {{history.cranesSince}} entstehen in Tuttwil die HS-Krananlagen. Wir betreuen sie weiter – mit dem Wissen von damals und den Teilen ab Lager.',
    photo: 'heukran-einsatz',
    primary: anfrage('Service anfragen'),
  },
  summary:
    'Seit {{history.cranesSince}} baut die Werkstatt in Tuttwil die HS-Krananlagen – Einschienenkrane, hydraulische Drehkrane, Brückenkrane, gebäudeangepasste Anlagen und Heukrane. {{brand.full}} betreut diesen Bestand weiter, mit Ersatzteilen ab Lager – auch in Jahrzehnten noch.',
  glance: {
    forWhom: 'Besitzerinnen und Besitzer von HS-Krananlagen in Landwirtschaft, Industrie und Gemeinden.',
    what: 'Service, Reparatur, Saison-Check, Ersatzteile, Modernisierung – und Neuanlagen auf Anfrage.',
    speed: '{{promises.reactionTime}}',
    deliverables: 'Bericht bzw. Rapport und Eintrag ins Kranbuch.',
  },
  scope: {
    title: 'Welche HS-Anlagen wir betreuen',
    lead: 'Die meisten HS-Krananlagen sind Sonderanfertigungen – darum zählt, wer sie kennt.',
    items: [
      { title: 'Einschienenkrane', text: 'Kran auf einer Laufschiene, oft in Scheunen und Werkstätten.' },
      { title: 'Drehkrane, hydraulisch', text: 'Hydraulischer Drehkran mit Ausleger für grosse Arbeitsbereiche.' },
      { title: 'Brückenkrane', text: 'Kranbrücke über die ganze Hallenbreite, für Industrie und Gewerbe.' },
      { title: 'Gebäudeangepasste Anlagen', text: 'Auf das Gebäude abgestimmte Anlagen für Industrie und Gemeinden.' },
      { title: 'Heukrane', text: 'Krananlagen mit Greifer für Heu und Stroh in der Landwirtschaft.' },
    ],
  },
  steps: [
    { title: 'Anfrage', text: 'Sie nennen Typ, Baujahr und Standort – ein Foto vom Typenschild genügt.' },
    steps.termin,
    { title: 'Arbeit vor Ort', text: 'Wir prüfen, warten oder reparieren – mit den Ersatzteilen aus unserem Lager.' },
    steps.bericht,
  ],
  faq: [
    {
      q: 'Gibt es für meinen alten HS-Kran noch Ersatzteile?',
      a: 'In vielen Fällen ja: Greifer, Ausleger, Fahrwerke und Drehtürme liegen an Lager. Schicken Sie uns ein Foto vom Typenschild, dann klären wir es. [[PRÜFEN: Lagerbestand für ältere Typen]]',
    },
    faqHsCare,
    {
      q: 'Wann ist der beste Zeitpunkt für den Service am Heukran?',
      a: 'Vor der Saison, zwischen März und Mai. Dann bleibt Zeit für Ersatzteile, ohne dass das Wetter drängt.',
    },
    {
      q: 'Bauen Sie noch neue HS-Krananlagen?',
      a: 'Ja, auf Anfrage – vom Heukran bis zur Anlage, die auf ein bestehendes Gebäude abgestimmt ist. [[PRÜFEN: Neuanlagen – Umfang und Bezeichnung]]',
    },
    {
      q: 'Betreuen Sie auch Anlagen im Ausland?',
      a: '{{area.abroad}} {{area.abroadReview}}',
    },
  ],
  cta: {
    title: 'Service für Ihre HS-Krananlage anfragen',
    lead: 'Typ und Baujahr helfen – ein Foto vom Typenschild genügt. Wir melden uns innert {{promises.responseTime}}.',
    kind: 'kran',
  },
  related: [
    { href: '/krane/reparatur', label: 'Reparatur und Pikett', text: 'Wenn der Heukran mitten in der Saison stehen bleibt.' },
    { href: '/krane/modernisierung', label: 'Modernisierung', text: 'Funkfernsteuerung, Umrichter und neue Steuerung für ältere Anlagen.' },
    { href: '/ratgeber/heukran-saison-check', label: 'Heukran-Saison-Check', text: 'Worauf es vor dem ersten Schnitt ankommt.', kind: 'ratgeber' },
  ],
  service: { name: 'Service und Ersatzteile für HS-Krananlagen', serviceType: 'Heukran-Service und Ersatzteile' },
  keywords: ['HS Krananlagen', 'Heukran Service', 'Heukran Ersatzteile', 'Drehkran hydraulisch'],
};

/** Module der HS-Seite. */
export const hsModules = {
  parts: {
    title: 'Ersatzteile ab Lager',
    text: 'Greifer, Ausleger, Fahrwerke und Drehtürme für HS-Krananlagen liegen in Tuttwil an Lager, dazu gängige Verschleissteile. Was nicht an Lager ist, klären wir mit Ihnen. [[PRÜFEN: Nachfertigung von Teilen möglich?]]',
  },
  season: {
    title: 'Saison-Check vor dem ersten Schnitt',
    text: 'Ein Heukran steht über den Winter still und muss beim ersten Schnitt sofort laufen. Beim Saison-Check zwischen März und Mai prüfen wir Kranbahn, Fahrwerke, Seil, Greifer, Hydraulik und Elektrik – und ersetzen, was bis zur Ernte nicht hält.',
    link: { href: '/ratgeber/heukran-saison-check', label: 'Was wir beim Saison-Check anschauen' },
  },
  plate: {
    title: 'So finden Sie Typ und Baujahr',
    steps: [
      'Suchen Sie das Typenschild: [[PLATZHALTER: wo das Typenschild an HS-Krananlagen sitzt]]',
      'Darauf stehen Typ, Baujahr und Nummer – etwa Typenbezeichnungen wie AGRO Sprint, AGRO Top, RANCH-PROFI oder KING. [[PRÜFEN: Typenbezeichnungen]]',
      'Machen Sie ein Foto und schicken Sie es mit der Anfrage oder per E-Mail an {{email.link}}.',
    ],
  },
  newPlants: {
    title: 'Neue Krananlagen auf Anfrage',
    text: 'Sie planen einen neuen Heukran oder eine Krananlage für Ihre Halle? Wir planen und bauen sie, abgestimmt auf Ihr Gebäude und Ihre Arbeit. [[PRÜFEN: Umfang Neuanlagen]]',
  },
};
