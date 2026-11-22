// @ts-check
/**
 * ►►► **«Meinten Sie …@gmail.com?» – ein Tippfehler in der Adresse, bevor die Antwort ins Leere geht.** ◄◄◄
 *
 * Eine Bestätigung an «…@gmai.com» kommt nie an, und oft kommt nicht einmal ein Rückläufer
 * zurück (manche vertippten Domains nehmen Mails stillschweigend an). Darum fragt das Formular,
 * wenn die Domain einem grossen Anbieter um einen Buchstaben gleicht. Es ist nur ein Hinweis:
 * gesendet wird, was dasteht.
 */

/** Die Anbieter, bei denen sich Tippfehler lohnen (Schweiz, Nachbarländer, die grossen). */
export const KNOWN = [
  'gmail.com', 'googlemail.com', 'bluewin.ch', 'gmx.ch', 'gmx.net', 'gmx.de', 'gmx.at',
  'hotmail.com', 'hotmail.ch', 'outlook.com', 'live.com', 'icloud.com', 'me.com', 'yahoo.com',
  'sunrise.ch', 'hispeed.ch', 'swissonline.ch', 'bluemail.ch', 'protonmail.com', 'proton.me',
  'web.de', 't-online.de', 'aon.at', 'libero.it', 'orange.fr', 'free.fr', 'wanadoo.fr',
];

/** Wie viele Zeichen trennen zwei Wörter (ein Tausch zweier Nachbarn zählt eins). */
export function distance(/** @type {string} */ a, /** @type {string} */ b) {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
    }
  }
  return d[a.length][b.length];
}

/**
 * Die vermutlich gemeinte Adresse – oder `null`. Gefragt wird nur bei einer Domain, die
 * einem bekannten Anbieter um höchstens ein Zeichen (lange Domains: zwei) gleicht und
 * selbst keiner ist.
 * @param {string} email
 * @returns {string | null}
 */
export function suggest(email) {
  const at = email.trim().lastIndexOf('@');
  if (at < 1) return null;
  const local = email.trim().slice(0, at);
  const domain = email.trim().slice(at + 1).toLowerCase();
  if (!domain || KNOWN.includes(domain)) return null;
  let best = null;
  let bestD = Infinity;
  for (const k of KNOWN) {
    const dd = distance(domain, k);
    if (dd < bestD) { best = k; bestD = dd; }
  }
  const limit = (best ?? '').length >= 10 ? 2 : 1;
  return best && bestD <= limit ? `${local}@${best}` : null;
}
