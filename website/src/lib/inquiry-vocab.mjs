// @ts-check
/**
 * Das Vokabular des Anfrage-Formulars als EIN Objekt – für den Browser (data-vocab am
 * Formular → scripts/form.ts) und für den Server (scripts/export-erp.mjs →
 * backend/app/assets/website_contact.json). Beide prüfen und schreiben mit denselben
 * Wörtern, denselben Mustern und derselben Betreff-Regel.
 */
import { inquiry } from '../config/inquiry.mjs';

export function formVocab() {
  const { labels, messages, patterns, subject } = inquiry;
  return { labels, messages, patterns, subject };
}
