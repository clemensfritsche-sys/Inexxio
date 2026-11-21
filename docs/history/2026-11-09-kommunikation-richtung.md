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

## Nachtrag 2026-11-10 · Gesamtschau, umgesetzt A und B
- **Ein Fehler danach**: die Antwort an die private Adresse eines Mitarbeiters galt selbst als
  offen («Mitarbeiter im An» – gedacht für die interne Erinnerung). `domain.to_us` zählt das nur
  noch bei internen Kanälen.
- **A – kleiner**: `communication.history` (nur noch im Test) und die alte Kennung
  «Nummer der Zeile» weg (Migration 184 schreibt wartenden Altmails ihre Kennung fest); eine
  Grussformel-Erkennung statt zwei; `References` mit dem ganzen Faden; Outlook-Zitatkopf
  («Von: … Gesendet: …») wird abgeschnitten.
- **B – eine Stelle**: `services/outbox.py` – jede Mail des Hauses entsteht über `deliver`
  (vorher baute jeder der vier Absender Postfach, Firmenangaben, Absender und Versand selbst –
  genau dort lagen die Fehler); gebaut beim Anlegen, auch die Antwort aus dem Verlauf; «nicht
  gesendet» ist EINE Regel (`_FAILED`), an der Mail sichtbar, mit «Neu senden».
- **Verworfen für jetzt** (C): Eingabe teilen in «Antworten» und «Neu», nur noch ein Modus
  (immer Gmail), Gmail-Push statt Abfragen.
- Geprüft: Backend 803 grün (neu u. a. Wächter «keine zweite Stelle legt eine Mail an», je
  gegen die Bug-Form gegengeprüft), Frontend Typen · Lint · 161 Tests grün.

## Nachtrag 2026-11-10 · C umgesetzt (7, 8, 9)
- **8 – ein Modus**: «ohne Gmail nur erfassen» ist weg. Eine Mail geht hinaus oder wartet
  sichtbar auf ihr Postfach; die Eingabe bietet nur verbundene Postfächer an. Tests: ein
  Test-Postfach (`factories.post_office`) statt einer eigenen Welt.
- **7 – Eingabe**: drei Arten (Mail · Anruf · Intern); «an mehrere» ist keine Maske, sondern
  die Zeile «Versand», die erst ab zwei Empfängern erscheint (einzeln = Rundschreiben,
  Häkchen = Newsletter). Vorher im Artefakt «Kommunikation – neue Eingabe» gezeigt und
  freigegeben. Die Antwortzeile nennt das Postfach.
- **9 – Push**: Gmail meldet über Pub/Sub (`POST /api/v1/mail/push`, dieselbe Anmeldung wie der
  Takt); die Anmeldung bei Gmail erneuert der Takt (`watch_until`, Migration 185); der Browser
  holt gemeldete Postfächer nicht mehr bei Gmail ab, er fragt nur nach `latest`. Wirksam erst
  nach `infra/setup-gmail-push.sh` je Projekt – bis dahin holt der Takt ab (Warnung im Log).
- Unterwegs: zwei Log-Tests waren lokal rot, weil die Test-Datenbank aus Vortagen schon
  versiegelte Tage hatte – mit frischer Datenbank grün (kein Befund im Code).
- Geprüft: Backend 808 grün, Frontend Typen · Lint · 161 Tests grün; Gegenproben der neuen
  Wächter rot gegen den alten Stand.
