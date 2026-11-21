// @ts-check
/**
 * ►►► Der Betreff einer Anfrage – «Anfrage: Kran läuft beim Anfahren ruckartig». ◄◄◄
 *
 * Der erste Satz der Nachricht, gekappt am Wort. Dieselbe Regel wie im ERP
 * (`backend/app/services/inquiry.subject_of`): der mailto-Ausweg (Server nicht erreichbar)
 * landet im Postfach der Gesellschaft und damit im Verlauf – unter demselben Anliegen, als
 * wäre das Formular durchgegangen. «[Anfrage] Firma» machte zwei Anfragen derselben Firma
 * zu EINEM Anliegen, und eine Antwort erledigte beide.
 * Wächter: `backend/tests/test_contact.py` vergleicht beide Fassungen an denselben Fällen.
 *
 * @param {string} message
 * @param {{ word: string, max: number }} rule  `inquiry.subject` (src/config/inquiry.mjs)
 */
export function subjectOf(message, { word, max }) {
  const line = (message ?? '').split(/\r\n|\r|\n/).map((l) => l.trim()).find(Boolean) ?? '';
  let first = line.split(/\s+/).filter(Boolean).join(' ').split(/(?<=[.!?])\s/, 1)[0].replace(/\.+$/, '');
  if (first.length > max) {
    const head = first.slice(0, max + 1);
    const space = head.lastIndexOf(' ');
    const cut = (space === -1 ? head : head.slice(0, space)) || first.slice(0, max);
    first = `${cut.replace(/[,;:–\- ]+$/, '')} …`;
  }
  return first ? `${word}: ${first}` : word;
}
