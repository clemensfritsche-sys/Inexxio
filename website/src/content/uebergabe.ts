/**
 * Übergabe: Aus HS Steiner wird INEXXIO – steht auf «Über uns» (#uebergabe).
 * Der Satz zur Übergabe und die geteilten Antworten stehen NUR hier – Startseite, «Über uns»
 * und die Bereiche lesen sie von dieser Stelle.
 */
import { site } from '../config/site.mjs';
import type { Faq } from './types';

/** Der eine Satz zur Übergabe – Startseite und «Über uns» sagen ihn gleich. */
export const handoverLead =
  'Nach {{history.experienceDative}} übergibt Heiri Steiner sein Unternehmen an Clemens Fritsche. Standort, Telefonnummer und der Service für alle bestehenden HS-Krananlagen bleiben – ergänzt um Ingenieurwissen, wo es Ihnen nützt.';

/**
 * Fragen, die Startseite und Übergabe-Seite beide stellen – EINE Antwort, an einer Stelle.
 * (Rückmeldung 04.10.2026: «die Startseite spiegelt die Unterseiten – das muss matchen».)
 */
export const sharedFaq = {
  whoCares: {
    q: 'Wer betreut meine HS-Krananlage in Zukunft?',
    a: 'Wir – ohne Unterbruch. Wir kennen die HS-Krananlagen von der Konstruktion bis zum Ersatzteil und betreuen sie weiter.',
  },
  newCranes: {
    q: 'Bauen Sie weiterhin neue Krananlagen?',
    a: 'Ja. Krane nach Mass und Heukrananlagen planen, bauen und montieren wir weiterhin selbst.',
  },
  phone: {
    q: 'Bleibt die Telefonnummer gleich?',
    a: 'Ja, {{phone.display}}. Die aktuellen Kontaktangaben finden Sie jederzeit hier auf unserer Website.',
  },
  contracts: {
    q: 'Gelten bestehende Verträge weiter?',
    a: 'Ja. Das Unternehmen bleibt dasselbe, nur der Name ändert sich.',
  },
  /**
   * Krane anderer Hersteller – EINE Antwort für Krane, Service und Notfall (vorher sagte
   * der Notfall «nur auf Anfrage», der Kranservice «unabhängig vom Hersteller»). Kein «alle
   * Hersteller»: jeder Kran wird zuerst angeschaut, Teile werden im Einzelfall geklärt.
   */
  /** Stillstand – Startseite, Krane und Notfall sagen es gleich. */
  speed: {
    q: 'Wie schnell sind Sie bei einem Stillstand vor Ort?',
    a: 'Steht eine Anlage still, rufen Sie direkt an: {{phone.link}}. Wir kümmern uns darum.',
  },
  otherMakes: {
    q: 'Betreuen Sie auch Krane anderer Hersteller?',
    a: 'Ja. Wir prüfen, warten und reparieren Krane unabhängig vom Hersteller. Vorher schauen wir uns jeden Kran an. Ob wir Teile für ein bestimmtes Modell beschaffen können, klären wir im Einzelfall.',
  },
  /** Ersatzteile für HS-Anlagen (#1128) – Übergabe- und Heukran-Seite sagen es gleich. */
  parts: {
    q: 'Bekomme ich weiterhin Ersatzteile für ältere Anlagen?',
    a: 'Ja. Die Ersatzteile für die bestehenden HS-Anlagen liegen entweder an Lager, oder wir fertigen sie für Sie neu an.',
  },
} satisfies Record<string, Faq>;

/**
 * Die Übergabe auf «Über uns» (#uebergabe) – vorher eine eigene Seite /uebergabe, die dieselbe
 * Geschichte erzählte wie der Abschnitt «Geschichte» daneben (Rückmeldung 07.10.2026).
 */
export const handover = {
  eyebrow: 'Nachfolge geregelt',
  title: 'Aus HS Steiner wird {{brand.name}}',
  lead: handoverLead,
  timeline: [
    { year: String(site.history.founded), text: site.history.foundedText },
    { year: String(site.history.cranesSince), text: site.history.cranesText },
    { year: `${site.history.gmbhYear}`, text: 'Das Unternehmen wird zur {{brand.formerLegalName}}.' },
    { year: 'Heute', text: 'Heiri Steiner übergibt an Clemens Fritsche – aus HS Steiner wird die {{brand.legalName}}.' },
  ],
  /** Nur, was «Was bleibt / was neu ist» nicht schon beantwortet (Telefon, Verträge, neue Krane). */
  faq: [
    sharedFaq.whoCares,
    ...(site.features.heiriAdvisory
      ? [{ q: 'Bleibt Heiri Steiner dabei?', a: '{{people.founder.advisory}}' }]
      : []),
    sharedFaq.parts,
  ] satisfies Faq[],
};
