// @ts-check
/**
 * ►►► Der Newsletter «Post von INEXXIO» – seine Wörter an EINER Stelle. ◄◄◄
 *
 * Die Website (Häkchen im Anfrage-Formular, Seite /newsletter) und das ERP (Bestätigungs-
 * mail, Einladung in der Eingangsbestätigung, Abmeldelink, Konto) sprechen mit denselben
 * Sätzen – `scripts/export-erp.mjs` überträgt sie nach backend/app/assets/website_contact.json.
 *
 * ►►► `consent` ist der Wortlaut der Einwilligung. ◄◄◄ Er steht neben dem Häkchen und im
 * Konto, und er wird mit jeder Anmeldung als Nachweis gespeichert (newsletter_consents).
 * Wer ihn ändert, ändert, wozu künftige Personen Ja sagen – frühere behalten ihren.
 *
 * Die Regeln dahinter (UWG Art. 3 lit. o, DSG): nie vorausgewählt, nie an eine Leistung
 * gekoppelt, Bestätigung per Mail (Double Opt-in), Abmelden mit einem Klick.
 */
export const newsletter = {
  name: 'Post von INEXXIO',
  consent:
    'Ja, schicken Sie mir ab und zu «Post von INEXXIO» – unseren Newsletter, nur wenn es etwas zu erzählen gibt. Abmelden geht jederzeit mit einem Klick.',
  /** Die Bitte um Bestätigung (Double Opt-in). */
  confirmSubject: 'Ein Klick noch: Post von INEXXIO',
  confirmLead:
    'Sie möchten «Post von INEXXIO» erhalten, unseren Newsletter. Damit niemand Sie ohne Ihr Wissen anmeldet, bestätigen Sie es bitte mit einem Klick.',
  confirmIgnore: 'Waren Sie das nicht? Dann ignorieren Sie diese Mail einfach – ohne Bestätigung schicken wir nichts.',
  confirmButton: 'Ja, ich bin dabei',
  kicker: 'Newsletter',
  /** In der Eingangsbestätigung einer Anfrage: Häkchen gesetzt → bestätigen, sonst einladen. */
  inviteTitle: 'Post von INEXXIO',
  inviteAsked: 'Sie möchten unseren Newsletter – bitte bestätigen Sie es noch mit einem Klick.',
  inviteOffer:
    'Ab und zu erzählen wir, was bei uns entsteht. Wenn Sie mögen, genügt ein Klick – abmelden geht genauso schnell.',
  inviteButton: 'Ja, gerne',
  /** Im Fuss jedes Newsletters. */
  footer: 'Sie erhalten «Post von INEXXIO», weil Sie sich dafür angemeldet haben.',
  unsubscribe: 'Abmelden',
  /** Die Seite hinter dem Abmeldelink (ein Knopf, damit kein Link-Scanner abmeldet). */
  unsubscribeTitle: 'Vom Newsletter abmelden?',
  unsubscribeLead: 'Ein Klick, und Sie erhalten keine «Post von INEXXIO» mehr.',
  unsubscribeButton: 'Abmelden',
  invalid: 'Dieser Link ist abgelaufen oder unvollständig.',
};
