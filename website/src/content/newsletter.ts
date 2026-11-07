/**
 * Die Seiten des Newsletters «Post von INEXXIO» (/newsletter …). Der Wortlaut der
 * Einwilligung und die Mail-Texte stehen in `config/newsletter.mjs` – sie reisen ins ERP.
 */
export const newsletterPages = {
  description: 'Post von INEXXIO – der Newsletter von INEXXIO: Neues aus Krantechnik, Fahrzeugtechnik und Speziallösungen, nur wenn es etwas zu erzählen gibt.',
  signup: {
    eyebrow: 'Newsletter',
    title: 'Post von ==INEXXIO==',
    lead: 'Ab und zu erzählen wir, was bei uns entsteht – neue Lösungen, Einblicke, Termine. Kein Rauschen, nur wenn es etwas zu erzählen gibt.',
    label: 'Ihre E-Mail-Adresse',
    button: 'Anmelden',
    small: 'Sie erhalten zuerst eine Mail mit einem Knopf – erst Ihr Klick meldet Sie an. Abmelden geht jederzeit mit einem Klick.',
  },
  pending: {
    title: 'Fast geschafft',
    lead: 'Wir haben Ihnen eine Mail geschickt. Ein Klick auf den Knopf darin, und Sie sind dabei.',
  },
  confirmed: {
    title: 'Schön, dass Sie dabei sind',
    lead: 'Sie erhalten ab jetzt «Post von INEXXIO». Abmelden geht jederzeit mit einem Klick – der Link steht in jeder Ausgabe.',
  },
  unsubscribed: {
    title: 'Sie sind abgemeldet',
    lead: 'Sie erhalten keine «Post von INEXXIO» mehr. War das ein Versehen? Dann melden Sie sich einfach wieder an.',
    again: 'Wieder anmelden',
  },
};
