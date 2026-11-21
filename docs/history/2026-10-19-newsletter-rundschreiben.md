# 2026-10-19 – Newsletter, Rundschreiben, Einwilligung als Nachweis

## Auftrag
Konzept (freigegeben): drei Versandarten statt Bcc-Umdeutung – **Mail · Rundschreiben ·
Newsletter**; Anmeldung zum Newsletter nach Stand der Technik und so, dass jede Person im
Lead-Prozess dezent dazu eingeladen wird, im rechtlichen Rahmen. Empfängerauswahl per KI
später, nur vorbereitet. Google Workspace, zentrale Gmail-Signatur und persönliche
Postfächer verschoben.

## Entscheide
- **Zwei Zustände** (angemeldet · nicht angemeldet) statt drei. «Ausstehend» braucht es
  nicht: die Bitte um Bestätigung ist eine Mail im Verlauf, der Link trägt seine Aussage
  signiert selbst (Person, Zweck, Quelle, Ablauf 30 Tage). Keine Tabelle offener Bitten.
- **Einwilligung als Nachweis**, append-only (`newsletter_consents`: Quelle, Wortlaut,
  Zeitpunkt). Das frühere Häkchen `newsletter_opt_in` ist eine Zeile «legacy» geworden;
  die Spalte fällt im Folge-Deploy (Zwei-Deploy-Regel, `PENDING_DROP`).
- **Je Empfänger eine Nachricht** für Rundschreiben und Newsletter (`group_id` → die
  erste). So bleibt «was im Verlauf steht, ist, was hinausging» wahr (eigene Anrede, eigener
  Abmeldelink), und die Antwort einer Person ist ein gewöhnliches Anliegen bei ihr. Der
  Verlauf zeigt die Gruppe einmal («an 23»).
- **Versand über den Abgleich** (20 je Lauf), nicht im Klick; nach dem Senden stösst die
  Oberfläche einen Lauf sofort an. Ein Dienst (SES, Postmark, Infomaniak) ersetzt später
  nur `mailbox.send` – Gruppe, Einwilligung und Verlauf bleiben.
- **Das ERP meldet niemanden an** – es schickt die Bitte oder meldet ab. Das Konto meldet
  direkt an (die Adresse ist dort bestätigt).
- **Abmeldeseite mit Knopf** statt Abmelden beim Aufruf: Link-Scanner der Mailprogramme
  rufen Links auf. Das «Abbestellen» im Mailprogramm (RFC 8058) geht direkt.
- **Schlüssel der Links** aus `database_url` abgeleitet – keine zweite Einstellung, die
  jemand setzen muss. Wechselt das DB-Passwort, gelten alte Links nicht mehr (die Seite
  sagt es; das Konto bleibt der Weg).
- **Name «Post aus der Werkstatt»**, Wortlaut in `website/src/config/newsletter.mjs` –
  eine Quelle für Häkchen, Konto, Mails und Nachweis.

## Die Anmeldestellen
Häkchen im Anfrage-Formular (nie vorausgewählt) · Knopf in der Eingangsbestätigung
(mit Häkchen die Bitte, ohne eine leise Einladung – nie an An- oder Abgemeldete) ·
Seite `/newsletter` (Link im Fuss jeder Seite, auch Konto/ERP) · Schalter im Konto ·
«Einladung senden» im ERP (z. B. nach einem Telefonat). Datenschutzerklärung um
Abschnitt 6 ergänzt.

## Geprüft
- 747 Backend-Tests grün (10 neue in `test_newsletter.py`, 1 Spiegel-Wächter).
- Gegenproben: ohne die Einwilligungsprüfung beim Senden wird
  `test_a_newsletter_goes_only_to_subscribers_and_checks_again_when_sending` rot; mit
  falschem Wort im Frontend-Spiegel `test_the_deliveries_mirror_the_backend_word_for_word`.
- Bestätigungsmail und Newsletter gerendert angesehen (Knopf, sichtbare Adresse,
  Abmeldezeile im Fuss).

## Offen
- Rechtliche Prüfung der leisen Einladung in der Eingangsbestätigung (UWG Art. 3 lit. o).
- Ohne verbundenes Postfach geht keine Bitte um Bestätigung hinaus; das Häkchen im
  Formular bleibt dann ohne Wirkung (die Anfrage selbst ist gespeichert).
- Versanddienst, Rückläufer (unzustellbar → abmelden), Unterdomain für Massenversand.
