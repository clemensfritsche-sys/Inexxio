/**
 * Service – EINE Seite für den Einstieg nach Anliegen und den Notfall (Rückmeldung
 * 07.10.2026: vorher /service und /service/notfall). Der Service selbst ist in jedem Bereich
 * beschrieben; hier stehen nur die Nummer, der Weg zur richtigen Stelle und was man im
 * Notfall bereithält.
 */
import { sharedFaq } from './uebergabe';
import type { Entry, Faq } from './types';

export const service = {
  path: '/service',
  title: 'Service und Notfall',
  description:
    'Kran steht still, Prüfung fällig, Trommel am Ende oder Teil gesucht? Die Nummer für den Notfall und der direkte Weg zum richtigen Service.',
  hero: {
    eyebrow: 'Service und Notfall',
    h1: 'Service: Was steht bei Ihnen ==an==?',
    lead:
      'Steht etwas still, rufen Sie direkt an. Sonst wählen Sie Ihr Anliegen – wir führen Sie zur richtigen Stelle.',
  },
  summary:
    '{{brand.full}} prüft, wartet und repariert Krane aller Marken: Der erste Service ist gratis, und mit INEXXIO 365 läuft der Kran – oder Sie zahlen nicht. Für Fahrmischer tauschen wir die Trommel und beschaffen Verschleissteile für alle Marken – aus der Werkstatt in Tuttwil-Wängi TG. Steht etwas still, rufen Sie direkt an: {{phone.display}}.',
  entries: [
    { title: 'Etwas steht still', text: 'Rufen Sie direkt an – und halten Sie das Nötigste bereit', href: '#notfall', icon: 'siren' },
    { title: 'Kran prüfen, warten, reparieren', text: 'Der erste Service ist gratis. Mit INEXXIO 365 läuft Ihr Kran – oder Sie zahlen nicht', href: '/krantechnik/kranservice', icon: 'shield-check' },
    { title: 'Trommel am Ende', text: 'Neue Trommel statt neuer Fahrmischer – für alle Marken', href: '/fahrzeugtechnik/trommeltausch', icon: 'truck' },
    { title: 'Verschleissteil gesucht', text: 'Für alle Marken, schnell beschafft', href: '/fahrzeugtechnik/verschleissteile', icon: 'package' },
  ] satisfies Entry[],
  /** Zweite Ziele zu den Kacheln, die zwei Wege haben (Auftrag 7.6). */
  alsoLinks: [
    { href: '/fahrzeugtechnik#reparatur', label: 'Aufbau reparieren lassen' },
  ],
  /** Notfall (Anker #notfall). */
  prepare: {
    title: 'Was Sie bereithalten sollten',
    items: [
      { title: 'Standort', text: 'Wo steht die Anlage oder Maschine? PLZ, Ort, Zufahrt.' },
      { title: 'Maschine', text: 'Was ist es – Kran, Fahrmischer, Aufbau, Baumaschine? Hersteller und Typ.' },
      { title: 'Typenschild', text: 'Typ, Baujahr und Nummer – am einfachsten als Foto.' },
      { title: 'Foto vom Schaden', text: 'Was ist passiert, was ist zu sehen? Ein Foto sagt oft mehr als die Beschreibung.' },
    ],
  },
  safety: {
    title: 'Bis wir da sind',
    text: 'Anlage ausser Betrieb nehmen und sichern, Last – wenn möglich – sicher absetzen, Bereich absperren. Nicht unter Last weiterarbeiten.',
  },
  faq: [
    sharedFaq.speed,
    sharedFaq.otherMakes,
  ] satisfies Faq[],
};
