import { t } from '../i18n/t.mjs';
/** /ratgeber – Kopf der Übersicht. Die Artikel selbst liegen in src/content/ratgeber/. */
export const ratgeberUebersicht = t('ratgeber-uebersicht', {
  /** Kurz vor den Karten (components/spezial/FieldCards). */
  listTitle: 'Artikel',
  listLead: 'Geschrieben von {{people.owner.name}} – mit Quellen zum Nachlesen.',
  title: 'Ratgeber: Kranprüfung, Heukran, Fahrmischer',
  h1: 'Kurz erklärt – damit Sie ==sicher entscheiden==.',
  description:
    'Ratgeber zu Kranprüfung, Kranfachmann und Kranexperte, zur Planung einer neuen Heukrananlage und zu Verschleissteilen am Fahrmischer – kurz erklärt.',
  /** «Auf einen Blick» – steht als Einleitung auf der Seite und in llms-full.txt. */
  summary:
    'Kurz erklärt, mit Quellen: was die Prüfpflicht verlangt und wer Krane prüft, wie man eine neue Heukrananlage plant und wann Verschleissteile am Fahrmischer fällig sind. Geschrieben von {{people.owner.name}}, {{brand.name}}.',
});
