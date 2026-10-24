/**
 * Service – EINE Seite für den Notfall und den Einstieg nach Anliegen (Rückmeldung 07.10.2026: vorher
 * /service und /service/notfall). Der Service selbst ist in jedem Bereich beschrieben; hier stehen die
 * Nummer, was man im Notfall bereithält, und der Weg zur richtigen Seite. Layout v4 (Oktober 2026):
 * Kopf wie Porsche → Notfall (dunkle Karte, #notfall) → Ihr Anliegen (drei Karten) → Garantien → Fragen.
 */
import type { IconName } from '../components/Icon.astro';
import { sharedFaq } from './uebergabe';
import { promiseFaq } from './promises';
import type { Faq } from './types';

export const service = {
  path: '/service',
  title: 'Service und Notfall',
  description:
    'Kran steht still, Prüfung fällig, Trommel am Ende oder Teil gesucht? Die Nummer für den Notfall und der direkte Weg zum richtigen Service.',
  hero: {
    h1: 'Steht etwas still? Wir sind ==für Sie da==.',
    lead: 'Im Notfall rufen Sie direkt an. Für alles andere wählen Sie Ihr Anliegen – wir führen Sie zur richtigen Stelle.',
  },
  summary:
    '{{brand.full}} prüft, wartet und repariert Krane, Fahrmischer und Spezialmaschinen: Die erste Inspektion ist gratis, und mit INEXXIO 365 ist Ihre Maschine einsatzbereit – Ausfälle übernehmen wir. Für Fahrmischer tauschen wir die Trommel und beschaffen Verschleissteile – von unserem Standort in {{address.home}} aus. Steht etwas still, rufen Sie direkt an: {{phone.display}}.',
  /** Notfall (Anker #notfall) – components/CallPanel. */
  emergency: {
    label: 'Notfall',
    title: 'Steht etwas still? Rufen Sie an.',
    text: 'Halten Sie bereit, was wir zuerst fragen – dann geht es schneller.',
    items: [
      { icon: 'map-pin' as IconName, title: 'Standort', text: 'Wo steht die Maschine? PLZ, Ort, Zufahrt.' },
      { icon: 'truck' as IconName, title: 'Maschine', text: 'Kran, Fahrmischer, Aufbau oder Baumaschine – Hersteller und Typ.' },
      { icon: 'file-text' as IconName, title: 'Typenschild', text: 'Typ, Baujahr und Nummer – am einfachsten als Foto.' },
      { icon: 'camera' as IconName, title: 'Foto vom Schaden', text: 'Was ist passiert, was ist zu sehen?' },
    ],
    note: {
      title: 'Bis wir da sind:',
      text: 'Maschine ausser Betrieb nehmen und sichern, Last – wenn möglich – sicher absetzen, Bereich absperren. Nicht unter Last weiterarbeiten.',
    },
  },
  /** Ihr Anliegen – drei Karten (components/spezial/FieldCards), je zur Seite, auf der alles steht. */
  offers: {
    title: 'Wobei dürfen wir helfen?',
    lead: 'Wählen Sie Ihr Anliegen – dort steht alles Weitere.',
    items: [
      { id: 'kran', illo: 'menu/kranservice', alt: 'Zeichnung: roter Werkzeugkasten und Prüfprotokoll', title: 'Kranservice', text: 'Prüfen, warten, reparieren. Die erste Inspektion ist gratis.', href: '/krantechnik/kranservice' },
      { id: 'fahrmischer', illo: 'menu/trommeltausch', alt: 'Zeichnung: Fahrmischer mit roter Trommel', title: 'Fahrmischer', text: 'Neue Trommel statt neuer Fahrmischer – und Reparaturen am Aufbau.', href: '/fahrzeugtechnik' },
      { id: 'teile', illo: 'menu/verschleissteile', alt: 'Zeichnung: rote Rinne und Trichter', title: 'Verschleissteile', text: 'Rinne, Schurre, Trichter und Mischspiralen – auf Bestellung, schnell beschafft.', href: '/fahrzeugtechnik/verschleissteile' },
    ],
  },
  faq: [
    sharedFaq.speed,
    sharedFaq.otherMakes,
    promiseFaq.erstservice,
    promiseFaq.inexxio365,
  ] satisfies Faq[],
};
