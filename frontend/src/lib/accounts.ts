/**
 * ►►► **Was ein Benutzer-Datensatz ERBT, wenn ein Feld leer bleibt** (Testnotizen
 * #1042/#1043). ◄◄◄
 *
 * Zwei Angaben des Datensatzes sind freiwillig und fallen auf eine andere zurück: die
 * **Rechnungs-E-Mail** (leer → die Login-/Kontakt-Adresse) und die **Rechnungsadresse**
 * (leer → die Lieferadresse). In beiden Fällen gilt die Hausregel aus #1042: *das sagt
 * das Feld selbst – kein zweites Feld, keine Checkbox.*
 *
 * Die Sätze stehen darum hier, an **einer** Stelle, und werden von beiden Oberflächen
 * gelesen (ERP-Datensatz und Konto). Zwei Formulierungen wären zwei Aussagen über
 * dieselbe Vererbung.
 *
 * *Hier lag einmal der Spiegel eines **Kontotyps** (Privat ↔ Geschäft). Er ist entfallen
 * (#1043): der **Firmenname** ist die Erklärung – steht er da, tritt der Datensatz als
 * Firma auf. Ein Schalter daneben sagte dasselbe und konnte ihm widersprechen.*
 */

/**
 * Der Platzhalter der Rechnungs-E-Mail – er nennt die **Regel**, nicht nur die Adresse.
 *
 * Vorher stand dort allein die Login-Adresse: ein Platzhalter, der wie eine Vorbelegung
 * aussieht und nicht wie eine Vererbung.
 */
export function inheritedEmail(login: string | null | undefined): string {
  return login ? `übernimmt ${login}` : 'rechnung@firma.ch';
}

/**
 * Der Hinweis unter der Rechnungsadresse.
 *
 * Sie war einmal hinter einem Schalter «Rechnungsadresse = Lieferadresse» versteckt, und
 * der schrieb bei «gleich wie» eine **Kopie** der Lieferadresse in die Rechnungsfelder –
 * die beim nächsten Umzug veraltete. Jetzt steht der Block immer da, und was «leer»
 * bedeutet, steht als Satz darüber.
 */
export const INHERITED_ADDRESS = 'Leer: es gilt die Lieferadresse';
