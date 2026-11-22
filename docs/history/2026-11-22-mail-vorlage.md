# Die Mail-Vorlage, neu (22.11.2026)

**Auftrag:** Die Bestätigungsmail wirkte «too much KI». Nach vier Runden im Artefakt
«Bestätigungsmail Anfrage» (heute · drei Richtungen · Mischung) entschieden – und **global** für
jede Mail des ERP umgesetzt (`services/mail_layout`).

**Entschieden**
- Kopf: Überschrift links, Logo rechts auf gleicher Höhe; kein rotes Stichwort mehr.
- Bestätigung: «Angekommen – Danke für Ihre Anfrage», «Guten Tag <Name>» (neutral, Vor- und
  Nachname), Text: «Schön, dass Sie sich bei uns melden …», Foto/Mass per Antwort, «Eilt es?»
  als Satz statt Kasten; kein Ablauf mit Punkten, keine Angaben-Tabelle.
- «Beste Grüsse aus <Ort>», die Unterschrift direkt darunter; sie ist zugleich der Fuss
  (Anschrift, Telefon, E-Mail, Website). Unterschreibt das Unternehmen, mit dem Bild des Postfachs
  (Gmail) – keine Rolle, kein Geschäftsführer.
- Unten ein Streifen als Werbefläche: «Nachfolge geregelt – Aus HS Steiner wird INEXXIO», Bild der
  Übergabe (Funksender wechselt die Hand), Link auf «Über uns» #uebergabe; Bild als Datei auf der
  Website (`/mail/nachfolge.jpg`), kein Anhang.
- Links öffnen ein neues Fenster; Radien 8 px (Karte) / 6 px (Knopf).

**Abgewogen:** Der Name in der Anrede öffnet ein kleines Relais (wer eine fremde Adresse eintippt,
schreibt in den Gruss). Begrenzt auf Namen, die wie Namen aussehen (`salutation_name`); ein Wort aus
Buchstaben geht trotzdem durch – vom Inhaber so entschieden.

**Verworfen:** Unterschrift durch eine Person mit Rolle (Vorschlag «persönlich»); Werkstattbild oben;
Quittung mit Eckdaten.
