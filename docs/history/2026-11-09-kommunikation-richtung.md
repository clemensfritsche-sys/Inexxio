# 2026-11-09 · Kommunikation: die Richtung einer Nachricht, Absender, Kennung

## Anlass
Der Inhaber schrieb von seiner privaten Adresse an das Firmenpostfach. Die Mail stand im
Verlauf als «von uns», war nie offen, und «Antworten» hatte niemanden im «An». Eine Prüfung
des ganzen Mail-Wegs fand dazu weitere Fehler.

## Ursache
«Von uns» hiess überall: **der Absender ist Mitarbeiter**. Das verwechselt die Person mit dem
Weg der Mail. Ein Mitarbeiter mit privater Adresse schreibt von aussen; eine Mail der
Gesellschaft selbst hat gar keinen Menschen als Absender – darum wurde ihr der Admin
untergeschoben, der das Postfach verbunden hatte.

## Was jetzt gilt
- **`messages.inbound`** (Migration 183): kam die Nachricht von aussen? Gesetzt, wenn sie
  entsteht (Abgleich: Absenderadresse ist keine eigene; im ERP: der Handelnde ist kein
  Personal oder es ist ein eingehender Anruf). «Offen», «beantwortet», die Seite im Verlauf und
  die Vorschläge aus Mails lesen nur sie. Bestand: von aussen = nicht von Personal und nicht
  von einer eigenen Gesellschaft (die bisherige Lesart, festgeschrieben).
- **Die Gesellschaft schreibt**, was sie schreibt: Eingangsbestätigung, Newsletter-Bitte, Beleg
  ohne Mensch, was direkt in Gmail hinausging.
- **Kennung vor dem Senden** (`Message._message_id`): zufällig, gespeichert mit der Nachricht.
  Bisher war sie die Zeilennummer – nach einem Neuaufbau der Datenbank fand Gmail eine alte
  Mail mit derselben Nummer, und die neue galt als gesendet. Der Abgleich erkennt eigene
  Kennungen und holt sie nie herein (auch keine Person aus der Bitte an eine blosse Adresse,
  und keine Dublette, wenn Abgleich und Versand zugleich laufen).
- **Eine Antwort zählt erst, wenn sie draussen ist** (nicht `outgoing`, nicht `mail.gave_up`).
  Beleg- und Dokument-Mails warten mit Anbindung auf ihr Postfach, statt als gesendet dazustehen.
- **Mail ohne Betreff**: abgeholt als «(ohne Betreff)»; die Antwort erledigt sie. Hat eine ältere
  keinen, zeigt die Eingabe das Feld.
- **Eingabe**: Antwort auf eine eigene Mail von aussen geht an mich; ohne Postfach wird die
  Antwort intern (Kunde im «Betrifft»); ist das Postfach einer Mail getrennt, wird von Hand
  gewählt.

## Bewusst nicht
- Ein Kollege bleibt fest im «An», wenn man auf seine Mail antwortet (Entscheid des Inhabers).
- Alte Nachrichten werden nicht umgeschrieben (ihr Absender bleibt).

## Geprüft
`tests/test_mail_direction.py` (7 Fälle, je mit Bug-Form; 4 davon rot gegen den alten Stand),
Backend 798 grün, Frontend Typen · Lint · 161 Tests grün.
