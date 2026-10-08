/**
 * ►►► Die drei Versprechen – an EINER Stelle. ◄◄◄
 *
 * Drei verschiedene Dinge, die nicht vermischt werden: ① Service testen (nur Krane) ·
 * ② Kaufen mit Garantie (alles, was man kauft) · ③ INEXXIO 365 (bestehende und neue Krane).
 * Die Startseite zeigt alle drei, jede Unterseite nur die, die für sie gelten
 * (`promises` der Seite → Promises.astro). Wer einen Satz ändert, ändert ihn überall.
 *
 * Regeln: keine Preise, keine Kranklassen, keine Tagesabrechnung, keine Laufzeit-Rabatte,
 * kein «Abo» – und keine Bedingungen, Fristen oder Kleingedrucktes, die nicht feststehen.
 * Verbotene Wörter prüft scripts/check-site.mjs (FORBIDDEN_WORDS).
 */
import type { Faq } from './types';

export type PromiseKey = 'erstservice' | 'garantie' | 'inexxio365';

export interface PromiseItem {
  /** Die grosse Zahl – der Blickfang. */
  figure: string;
  /** Kleine Einheit neben der Zahl («Tage») – sonst ist offen, was die Zahl zählt. */
  unit?: string;
  label: string;
  title: string;
  text: string;
  link?: { href: string; label: string };
}

export const promises = {
  eyebrow: 'Unsere Versprechen',
  eyebrowOne: 'Unser Versprechen',
  title: 'Wir stehen für unsere Arbeit ein.',
  lead: 'Wir sind von unserer Arbeit überzeugt. Darum tragen wir das Risiko: Unser Geld hängt an Ihrer Zufriedenheit – und an jedem Tag, an dem Ihr Kran läuft.',
  items: {
    erstservice: {
      figure: '0.–',
      label: 'Service testen',
      title: 'Der erste Kranservice ist gratis.',
      text: 'Service und Wartung für Industrie-, Heu-, Boots- und Mastkrane aller Marken. Einmal pro Kunde, das Material verrechnen wir.',
      link: { href: '/krantechnik/kranservice#stufen', label: 'Zum Kranservice' },
    },
    garantie: {
      figure: '50 %',
      label: 'Kaufen mit Garantie',
      title: 'Nicht zufrieden? Sie zahlen nur die Hälfte.',
      text: 'Auf den ganzen Preis – für alles, was Sie bei uns kaufen: Krane, Bootslifte, Heukrananlagen, Modernisierung, Trommeltausch und Speziallösungen.',
    },
    inexxio365: {
      figure: '365',
      unit: 'Tage',
      label: 'INEXXIO 365',
      title: 'Ihr Kran läuft – oder Sie zahlen nicht.',
      text: 'Prüfung, Wartung, Ersatzteile und Reparaturen inklusive, zur fixen Monatsrate. Für Ihren bestehenden Kran, auch fremder Marken – oder einen neuen, ohne Kauf.',
      link: { href: '/krantechnik/kranservice#inexxio-365', label: 'So funktioniert INEXXIO 365' },
    },
  } satisfies Record<PromiseKey, PromiseItem>,
  /** Gilt für alles – steht unter jedem Versprechens-Block. */
  always: ['Fixpreis vor jeder Arbeit', 'Keine Mindestlaufzeit', 'Zweitmeinung gratis'],
};

/** Wie die Versprechen funktionieren – kurz, ohne neue Regeln. Jede Seite wählt, was passt. */
export const promiseFaq = {
  erstservice: {
    q: 'Was ist im Gratis-Erstservice enthalten?',
    a: 'Service und Wartung Ihres Krans – einmal pro Kunde, für Industrie-, Heu-, Boots- und Mastkrane aller Marken. Das Material verrechnen wir. Eine Prüfung gehört nicht dazu. Rufen Sie an oder schreiben Sie uns – wir vereinbaren den Termin.',
  },
  garantie: {
    q: 'Wie funktioniert die Garantie «Nicht zufrieden? Sie zahlen nur die Hälfte»?',
    a: 'Sind Sie mit dem Ergebnis nicht zufrieden, sagen Sie es uns – dann zahlen Sie nur die Hälfte. Auf den ganzen Preis, ohne Einschränkung.',
  },
  inexxio365: {
    q: 'Was heisst «Ihr Kran läuft – oder Sie zahlen nicht»?',
    a: 'Mit INEXXIO 365 zahlen Sie eine fixe Monatsrate. Prüfung, Wartung, Ersatzteile und Reparaturen sind inklusive. Steht der Kran still, ist jeder Tag gratis. Einen bestehenden Kran – auch fremder Marke – übernehmen wir nach einer Eintrittsprüfung; einen neuen erhalten Sie ohne Kauf, zur Monatsrate.',
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
    q: 'Fremd-Offerte erhalten – prüfen Sie sie?',
    a: 'Ja, gratis. Schicken Sie uns die Offerte. Wir sagen Ihnen offen, was wir davon halten.',
  },
} satisfies Record<string, Faq>;
