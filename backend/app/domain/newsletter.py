"""►►► **Der Newsletter – Einwilligung als Nachweis** (``services/newsletter``). ◄◄◄

Zwei Zustände, kein dritter: **angemeldet** oder **nicht angemeldet** (nie oder
abgemeldet). Ein «ausstehend» gibt es nicht: die Bitte um Bestätigung ist eine Mail im
Verlauf, und angemeldet ist erst, wer darin klickt (Double Opt-in). Wer schon bestätigt
ist – im Konto angemeldet, die Adresse ist dort geprüft –, braucht keinen zweiten Klick.

Eine Zeile je Wechsel (``models/newsletter``), mit Quelle und Wortlaut: das ist der
Nachweis, den das Gesetz verlangt, und die Geschichte dazu.
"""

#: Woher eine Zeile kommt – Anmeldung wie Abmeldung.
SOURCES: dict[str, str] = {
    "website": "Website",            # Anmeldeseite /newsletter, bestätigt per Mail
    "inquiry": "Kontaktformular",    # Häkchen oder Einladung in der Eingangsbestätigung
    "account": "Konto",              # die Person selbst, angemeldet
    "invitation": "Einladung",       # aus dem ERP verschickt, bestätigt per Mail
    "link": "Abmeldelink",
    "one_click": "Mailprogramm",     # List-Unsubscribe-Post (RFC 8058)
    "erp": "ERP",                    # Abmeldung durch Mitarbeitende (z. B. am Telefon)
}

#: Wie lange eine Bitte um Bestätigung gilt.
CONFIRM_DAYS = 30


