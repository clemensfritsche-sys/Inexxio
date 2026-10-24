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
    "legacy": "Früheres Häkchen",    # aus ``user_profiles.newsletter_opt_in`` (Migration 153)
}

#: Wie lange eine Bitte um Bestätigung gilt.
CONFIRM_DAYS = 30


def legacy_repair_sql() -> list[str]:
    """Das frühere Häkchen ``newsletter_opt_in`` wird ein Nachweis mit Quelle «legacy» –
    gelesen von Migration 153 **und** vom Lifespan-Netz. Selbstbegrenzend: wer schon eine
    Zeile hat, bekommt keine zweite."""
    return ["INSERT INTO newsletter_consents (person_object_id, subscribed, source, wording, "
            "at, created_at, updated_at, is_active) "
            "SELECT u.object_id, true, 'legacy', NULL, now(), now(), now(), true "
            "FROM user_profiles u WHERE u.newsletter_opt_in AND u.object_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM newsletter_consents c "
            "WHERE c.person_object_id = u.object_id)"]
