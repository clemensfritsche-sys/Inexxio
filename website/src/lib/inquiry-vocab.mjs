// @ts-check
/**
 * Das Vokabular der Anfrage-Formulare als EIN Objekt – für den Browser (data-vocab am
 * Formular → scripts/form.ts) und für den Server (scripts/export-contact.mjs →
 * backend/app/assets/website_contact.json). Beide prüfen und schreiben mit denselben Wörtern.
 */
import { inquiry } from '../config/inquiry.mjs';
import { abo } from '../config/abo.mjs';

export function formVocab() {
  return {
    kind: Object.fromEntries(inquiry.kinds.map((k) => [k.value, k.label])),
    kindSubject: Object.fromEntries(inquiry.kinds.map((k) => [k.value, k.subject])),
    need: Object.fromEntries(Object.values(inquiry.needs).flat().map((n) => [n.value, n.label])),
    urgency: Object.fromEntries(inquiry.urgencies.map((u) => [u.value, u.label])),
    urgencySubject: Object.fromEntries(inquiry.urgencies.map((u) => [u.value, u.subject])),
    pref: Object.fromEntries(inquiry.contactPrefs.map((p) => [p.value, p.label])),
    /** Abo-Stufen (Vorbelegung ?stufe=…). */
    tiers: Object.fromEntries(abo.tiers.map((t) => [t.id, t.name])),
    labels: inquiry.labels,
    messages: inquiry.messages,
  };
}
