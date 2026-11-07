# 2026-10-22 – «Mein Konto»: Feinschliff, Anmelde-E-Mail ändern

## Was
- **Kopf**: der Name ist das grosse, leise Wort hinter der Person (statt «Mein Konto»); die
  Überschrift darunter entfällt. Grösse nach Länge (`--n`), schmal je Wort eine Zeile (`--w`).
- **Adresssuche** (Google Places) im Konto in der neuen Haut: `AddressField look="kt"`
  (graue Flächen, Suchfeld 52 px, Standort als Pille). Die Vorschlagsliste (`.pac-container`)
  ist global neu – rund, ein Ort-Symbol je Zeile, «powered by Google» bleibt (Bedingung).
- **Bearbeiten** (Stift an einer Anschrift, neue Anschrift, Firma angeben, zugeordnete Firma):
  dieselben Karten und Felder wie der Rest der Seite (`AddressBook cards`, `CompanyField look`).
  Die Bausteine `.kt-*` wohnen jetzt in `components/form/kt-section.tsx` (Wächter: ERP-Dateien
  importieren nicht aus `components/account/`).
- **Geburtsdatum**: Eingabe «TT.MM.JJJJ» (Punkte setzen sich selbst) statt des Browser-Kalenders;
  weitergegeben wird nur ein gültiger Tag.
- **Telefon**: der Server schreibt die Nummer lesbar zurück (`people.tidy_phone`, dieselbe
  Schreibweise wie Website und Mail-Unterschrift, `services/phone`); das Konto übernimmt sie,
  solange im Feld noch steht, was gesendet wurde. Gilt auch im ERP (ein Schreibpfad).
- **Anmelde-E-Mail ändern** – für jede Anmeldeart:
  1. `POST /auth/me/email-check` (`people.email_problem`): gültig, neu, nicht schon bei einem
     anderen aktiven Konto. Dieselbe Regel prüft `core/auth._sync_user_profile`, bevor er die
     Adresse aus dem Token übernimmt (jetzt mit Audit-Eintrag).
  2. Firebase `verifyBeforeUpdateEmail` schickt den Link an die NEUE Adresse (Deutsch); erst der
     Klick ändert sie. Die alte Adresse bekommt von Firebase eine Nachricht mit Rückgängig-Link.
  3. Verlangt Firebase eine frische Anmeldung: mit Google im Pop-up (`reauthenticateWithPopup`),
     sonst «Neu anmelden» – die neue Adresse ist gemerkt und steht danach wieder im Feld.
  4. Der Link führt nach `/konto?email=neu`: frischer Token (das Backend übernimmt die Adresse)
     oder – da Firebase bei einer neuen E-Mail die Sitzungen widerruft – zur Anmeldung.

## Was es sonst berührt
- Magic Link und Passkey hängen an der Firebase-UID bzw. an der Adresse im Firebase-Konto –
  beide gehen nach dem Wechsel mit der neuen Adresse. Newsletter-Einwilligung hängt an der Person.
- Postfach-Abgleich: Mails von der neuen Adresse landen bei der Person; Mails von der alten
  Adresse würden eine neue Person anlegen (wie bei jedem unbekannten Absender).
- Im ERP lässt sich die Anmelde-E-Mail einer Person weiterhin nicht ändern (sie gehört zum
  Firebase-Konto); das bleibt so.

## Geprüft
Backend `pytest tests/` gegen ein Schema aus den Migrationen: 750 passed. Frontend type-check,
lint, test, build. Sichtprüfung in Chromium (1440/390) mit einer Vorschau-Seite (wieder
entfernt), die Google-Vorschlagsliste mit einem Stub nachgestellt.
