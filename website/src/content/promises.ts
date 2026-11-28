/**
 * ►►► Die Garantien – an EINER Stelle. ◄◄◄
 *
 * Zwei Garantien tragen das Angebot und gelten für alle drei Bereiche (Krane, Fahrmischer,
 * Spezialmaschinen): ① INEXXIO Funktionsgarantie · ② INEXXIO 365. Die Gratis-Inspektion
 * ist der leise Einstieg (Priorität 3) und steht als schmale Zeile darunter.
 * Gezeigt werden sie als die Garantie-Karten (components/home/Guarantees.astro) und in den Fragen;
 * `promises` einer Seite nennt für llms.txt, welche dort gelten. Wer einen Satz ändert, ändert ihn überall.
 *
 * Regeln: keine Preise, kein «Abo», keine Markenaufzählung («aller Marken» ist gestrichen) –
 * und keine Bedingungen, Fristen oder Kleingedrucktes, die nicht feststehen.
 * Verbotene Wörter prüft scripts/check-site.mjs (FORBIDDEN, FORBIDDEN_WORDS).
 */
import type { Faq } from './types';
import { t } from '../i18n/t.mjs';

export type PromiseKey = 'garantie' | 'inexxio365' | 'erstservice';

export interface PromiseItem {
  /** Die grosse Zahl – der Blickfang. */
  figure: string;
  /** Kleine Einheit neben der Zahl («Tage», «%»). */
  unit?: string;
  label: string;
  title: string;
  text: string;
  /** Kurze Punkte unter dem Text – nur bei den beiden Garantien. */
  checks?: string[];
  link?: { href: string; label: string };
}

export const promises = t('promises', {
  title: 'Funktioniert und einsatzbereit mit Garantie.',
  lead: 'Zwei Garantien für alles, was wir bauen, warten und reparieren – Fahrmischer, Krane und Spezialmaschinen.',
  items: {
    garantie: {
      figure: '50',
      unit: '%',
      label: 'INEXXIO Funktionsgarantie',
      title: 'Funktioniert garantiert. Sonst übernehmen wir die Hälfte.',
      text: 'Was in der Offerte steht, funktioniert. Sonst bessern wir nach – auf unsere Kosten. Klappt es trotzdem nicht, übernehmen wir 50 % des vereinbarten Preises. Das gilt für alles, was wir für Sie bauen, warten und reparieren: Krane, Bootslifte, Heukrananlagen, Modernisierung, Trommeltausch und Speziallösungen.',
      checks: ['Für alles, was wir bauen, warten und reparieren', 'Nachbessern auf unsere Kosten', 'Bedingungen: AGB, Ziffer 11'],
    },
    inexxio365: {
      figure: '365',
      unit: 'Tage',
      label: 'INEXXIO 365',
      title: 'Ihre Maschine ist einsatzbereit. Ausfälle übernehmen wir.',
      text: 'Sie zahlen eine fixe Monatsrate für die Einsatzbereitschaft – nicht für Ausfallzeiten und Reparaturen. Prüfung, Wartung und Ersatzteile sind inklusive, und steht die Maschine still, ist jeder Tag gratis.',
      checks: ['Fixe Monatsrate für Einsatzbereitschaft', 'Reparaturen und Ersatzteile übernehmen wir', 'Keine Mindestlaufzeit'],
      link: { href: '/krantechnik/kranservice#inexxio-365', label: 'So funktioniert INEXXIO 365' },
    },
    erstservice: {
      figure: '0.–',
      label: 'Lernen Sie uns kennen',
      title: 'Die erste Inspektion ist gratis.',
      text: 'Wir prüfen Ihre Maschine einmal kostenlos – Fahrmischer, Krane und Spezialmaschinen.',
      link: { href: '#anfrage', label: 'Termin vereinbaren' },
    },
  } satisfies Record<PromiseKey, PromiseItem>,
});

/** Wie die Garantien funktionieren – kurz, ohne neue Regeln. Jede Seite wählt, was passt. */
export const promiseFaq = t('promises', {
  erstservice: {
    q: 'Was ist in der Gratis-Inspektion enthalten?',
    a: 'Wir prüfen Ihre Maschine einmal kostenlos – Fahrmischer, Krane und Spezialmaschinen, einmal pro Kunde. Rufen Sie an oder schreiben Sie uns – wir vereinbaren den Termin.',
  },
  garantie: {
    q: 'Wie funktioniert die Funktionsgarantie?',
    a: 'Was in der Offerte steht, funktioniert – das prüfen wir bei der Abnahme gemeinsam mit Ihnen. Sonst bessern wir nach, auf unsere Kosten. Klappt es trotzdem nicht, übernehmen wir 50 % des vereinbarten Preises – für alles, was wir für Sie bauen, warten und reparieren. Melden Sie sich innert 30 Tagen nach der Abnahme; die Bedingungen stehen in unseren AGB (Ziffer 11). Für reine Teilelieferungen gilt die Garantie nicht.',
  },
  inexxio365: {
    q: 'Was ist INEXXIO 365?',
    a: 'Sie zahlen eine fixe Monatsrate für die Einsatzbereitschaft Ihrer Maschine. Prüfung, Wartung, Ersatzteile und Reparaturen übernehmen wir, und steht die Maschine still, ist jeder Tag gratis. Eine Mindestlaufzeit gibt es nicht.',
  },
  binding: {
    q: 'Wie lange binde ich mich?',
    a: 'Gar nicht. Es gibt keine Mindestlaufzeit.',
  },
  price: {
    q: 'Wie erfahre ich den Preis?',
    a: 'Vor jeder Arbeit erhalten Sie eine verbindliche Offerte – ob Inspektion, Reparatur, neue Anlage oder Speziallösung. Auf der Rechnung steht keine Überraschung.',
  },
  secondOpinion: {
    q: 'Fremd-Offerte erhalten – prüfen Sie sie?',
    a: 'Ja, gratis. Schicken Sie uns die Offerte. Wir sagen Ihnen offen, was wir davon halten.',
  },
} satisfies Record<string, Faq>);
