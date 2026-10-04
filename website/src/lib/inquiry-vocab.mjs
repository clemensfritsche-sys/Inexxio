// @ts-check
/**
 * Das Vokabular des Anfrage-Formulars als EIN Objekt – für den Browser (data-vocab am
 * Formular → scripts/form.ts) und für den Server (scripts/export-contact.mjs →
 * backend/app/assets/website_contact.json). Beide prüfen und schreiben mit denselben Wörtern.
 */
import { inquiry } from '../config/inquiry.mjs';

export function formVocab() {
  return { labels: inquiry.labels, messages: inquiry.messages };
}
