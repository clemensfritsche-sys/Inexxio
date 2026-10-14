/**
 * ►►► **Was ein Benutzer-Datensatz ERBT, wenn ein Feld leer bleibt** (Testnotizen
 * #1042/#1043). ◄◄◄
 *
 * Die **Rechnungs-E-Mail** einer Anschrift ist freiwillig und fällt leer auf die
 * Login-/Kontakt-Adresse zurück – das sagt der Platzhalter. *Der Schalter «Eigene
 * Rechnungsadresse» stand hier daneben; er ist mit dem Adressbuch entfallen: es gibt
 * beliebig viele Anschriften und je einen Standard für Lieferung und Rechnung.*
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
