/**
 * ►►► **Was ein Benutzer-Datensatz ERBT, wenn ein Feld leer bleibt** (Testnotizen
 * #1042/#1043). ◄◄◄
 *
 * Zwei Angaben des Datensatzes sind freiwillig und fallen auf eine andere zurück: die
 * **Rechnungs-E-Mail** (leer → die Login-/Kontakt-Adresse) und die **Rechnungsadresse**
 * (leer → die Lieferadresse). Die Regel ist in beiden Fällen dieselbe und steht in den
 * **Daten**; verschieden ist nur, wie sichtbar sie ist: bei der E-Mail sagt es der
 * Platzhalter, bei der Anschrift ein **Schalter** (sie ist ein halbes Dutzend Felder, und
 * ein leerer Block sieht nicht nach einer Entscheidung aus).
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
 * ►►► **Der Schalter über der Rechnungsadresse — eine ABLEITUNG, keine Spalte.** ◄◄◄
 *
 * Er war einmal ein gespeicherter Wert (``invoice_same_as_shipping``) und schrieb bei
 * «gleich wie» eine **Kopie** der Lieferadresse in die Rechnungsfelder – die beim
 * nächsten Umzug veraltete. Darum ist er mit #1043 verschwunden; zurück ist er jetzt als
 * das, was er immer sein wollte: die **sichtbare Form** der einen Regel *leer heisst
 * erben*.
 *
 * * **An** heisst «es steht eine eigene da» – die Felder sind offen.
 * * **Aus** räumt sie und sagt damit in den Daten, was der Schalter anzeigt.
 *
 * Es gibt also weiterhin **eine** Wahrheit (die Felder) und **keine** Kopie. Und die
 * Frage «steht eine eigene da?» ist dieselbe, die der Dienst stellt
 * (``voucher.billing_of`` – zwei Formen einer Regel, ein Namensstamm).
 */
export const OWN_ADDRESS = 'Eigene Rechnungsadresse';
/**
 * Was «Aus» bedeutet – **als Satz, nicht als Rechnung**: er steht wortgleich als
 * Beschriftung des Schalters und als Wert dort, wo nur gelesen wird. Ihn an der zweiten
 * Stelle aus der ersten zusammenzuschneiden wäre dieselbe Falle wie «Kundeen» (#787).
 */
export const OWN_ADDRESS_HINT = 'Ohne eigene gilt die Lieferadresse';

/** Die **Felder**, aus denen «es steht eine eigene da» folgt – wie im Dienst gelesen. */
export type BillingFields = {
  invoice_first_name: string;
  invoice_last_name: string;
  invoice_address_line1: string;
};

export function hasOwnBilling(v: BillingFields): boolean {
  return !!(v.invoice_first_name.trim() || v.invoice_last_name.trim()
    || v.invoice_address_line1.trim());
}

/**
 * Was **«Aus»** in den Daten bedeutet: die Felder sind geräumt.
 *
 * Der Schalter ist damit die einzige Stelle, die etwas schreibt – und was er schreibt,
 * ist eine **Leere**, keine Kopie. Das Land bleibt auf dem Vorgabewert, damit die
 * Länderauswahl einen gültigen Wert zeigt; gelesen wird es ohne eigene Anschrift nie.
 */
export const NO_OWN_BILLING = {
  invoice_first_name: '',
  invoice_last_name: '',
  invoice_address_line1: '',
  invoice_address_line2: '',
  invoice_postal_code: '',
  invoice_city: '',
  invoice_country: 'CH',
} as const;
