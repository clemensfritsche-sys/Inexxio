/**
 * ►►► Die drei Versprechen – an EINER Stelle (WEBSITE_PLAN §7.7d). ◄◄◄
 *
 * ① Gratis-Erstservice · ② INEXXIO Zufriedenheitsgarantie · ③ INEXXIO 365. Die Startseite zeigt alle drei,
 * jede Unterseite nur die, die für sie gelten (`SubPage.promises` → Promises.astro). Wer
 * einen Satz ändert, ändert ihn überall.
 *
 * Regeln (Rückmeldung 07.10.2026): keine Preise, keine Kranklassen, keine Bedingungen,
 * Fristen oder Kleingedrucktes, die nicht genannt sind. Verbotene Wörter prüft
 * scripts/check-site.mjs (FORBIDDEN_WORDS).
 */
import type { Faq } from './types';

export type PromiseKey = 'erstservice' | 'garantie' | 'inexxio365';

export interface PromiseItem {
  /** Die grosse Zahl – der Blickfang. */
  figure: string;
  label: string;
  title: string;
  text: string;
  link?: { href: string; label: string };
}

export const promises = {
  eyebrow: 'Unsere Versprechen',
  eyebrowOne: 'Unser Versprechen',
  title: 'Sie tragen kein Risiko. Das tragen wir.',
  items: {
    erstservice: {
      figure: '0.–',
      label: 'Gratis-Erstservice',
      title: 'Der erste Kranservice ist gratis.',
      text: 'Einmal pro Kunde: Service und Wartung für Industrie-, Heu-, Boots- und Mastkrane aller Marken. Sie zahlen nur das Material.',
      link: { href: '/krantechnik/kranservice#stufen', label: 'Zum Kranservice' },
    },
    garantie: {
      figure: '50 %',
      label: 'INEXXIO Zufriedenheitsgarantie',
      title: 'Nicht zufrieden? Sie zahlen nur die Hälfte.',
      text: 'Auf den ganzen Preis, ohne Einschränkung – für neue Krane und Bootslifte, Heukrananlagen, Trommeltausch und Sonderlösungen.',
    },
    inexxio365: {
      figure: '365',
      label: 'INEXXIO 365',
      title: 'Ihr Kran läuft – oder Sie zahlen nicht.',
      text: 'Prüfung, Wartung, Ersatzteile und Reparaturen inklusive, zur fixen Monatsrate. Jeder Tag, an dem der Kran steht, ist gratis.',
      link: { href: '/krantechnik/kranservice#inexxio-365', label: 'So funktioniert INEXXIO 365' },
    },
  } satisfies Record<PromiseKey, PromiseItem>,
  /** Gilt für alles – steht unter jedem Versprechens-Block. */
  always: ['Fixpreis vor jeder Arbeit', 'Keine Mindestlaufzeit', 'Zweitmeinung gratis'],
};

/** Für wen INEXXIO 365 gemacht ist – Startseite, Kranservice und Industriekrane sagen es gleich. */
export const industries =
  'Für Recycling und Entsorgung, Sägewerke und Holzhandel, Stahlhandel und Metallbau, Betonwerke – und alle, deren Kran laufen muss.';

/** Wie die Versprechen funktionieren – kurz, ohne neue Regeln. Jede Seite wählt, was passt. */
export const promiseFaq = {
  erstservice: {
    q: 'Was ist im Gratis-Erstservice enthalten?',
    a: 'Service und Wartung Ihres Krans – einmal pro Kunde, für Industrie-, Heu-, Boots- und Mastkrane aller Marken. Das Material verrechnen wir. Eine Prüfung gehört nicht dazu.',
  },
  garantie: {
    q: 'Wie funktioniert die INEXXIO Zufriedenheitsgarantie?',
    a: 'Sind Sie mit dem Ergebnis nicht zufrieden, sagen Sie es uns – dann zahlen Sie nur die Hälfte. Auf den ganzen Preis, ohne Einschränkung.',
  },
  inexxio365: {
    q: 'Was heisst «Ihr Kran läuft – oder Sie zahlen nicht»?',
    a: 'Mit INEXXIO 365 zahlen Sie eine fixe Monatsrate. Prüfung, Wartung, Ersatzteile und Reparaturen sind inklusive. Steht der Kran still, ist jeder Tag gratis.',
  },
  binding: {
    q: 'Wie lange binde ich mich?',
    a: 'Gar nicht. Es gibt keine Mindestlaufzeit.',
  },
  price: {
    q: 'Was kostet es?',
    a: 'Das hängt von Ihrem Kran und Ihrem Bedarf ab. Vor jeder Arbeit erhalten Sie einen Fixpreis – auf der Rechnung steht keine Überraschung.',
  },
  secondOpinion: {
    q: 'Ich habe eine Offerte von einem anderen Anbieter. Prüfen Sie sie?',
    a: 'Ja, gratis. Schicken Sie uns die Offerte – wir sagen Ihnen offen, was wir davon halten.',
  },
} satisfies Record<string, Faq>;
