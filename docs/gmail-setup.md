# Gmail anbinden (CRM Schritt 3)

Gmail ist das Postfach, das ERP der Verlauf. Ohne die beiden Schlüssel unten gibt es
keine Anbindung – eine E-Mail wird dann wie bisher nur **erfasst**, nicht gesendet.

## Einmalig in der Google Cloud Console (Projekt `inexxio-dev`)

1. **Gmail API aktivieren** – *APIs & Dienste → Bibliothek → Gmail API → Aktivieren*.
2. **OAuth-Zustimmungsbildschirm** – Typ **Extern**, Status **Testen**. App-Name
   «Inexxio», Support-Mail eintragen. Bereiche (müssen genau zu `services/mailbox.SCOPES`
   passen): `gmail.modify` (lesen **und** «gelesen» setzen), `gmail.send` und
   `userinfo.profile` (das Bild des Kontos neben der Unterschrift).
   Unter **Testnutzer** jedes Konto eintragen, das verbunden wird – je **eigene
   Gesellschaft** eines (z. B. `info.inexxio@gmail.com`), höchstens 100.
3. **OAuth-Client anlegen** – *Anmeldedaten → Anmeldedaten erstellen → OAuth-Client-ID →
   Webanwendung*. Autorisierte Weiterleitungs-URI:
   `https://inexxio-dev.web.app/api/v1/mail/callback`
4. **Die zwei Werte in den Secret Manager** und dem Backend lesen lassen:
   ```bash
   printf '%s' 'CLIENT-ID'     | gcloud secrets create GOOGLE_CLIENT_ID --data-file=- --project inexxio-dev
   printf '%s' 'CLIENT-SECRET' | gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=- --project inexxio-dev
   for s in GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET; do
     gcloud secrets add-iam-policy-binding $s --project inexxio-dev \
       --member serviceAccount:cloudrun-backend@inexxio-dev.iam.gserviceaccount.com \
       --role roles/secretmanager.secretAccessor
   done
   ```
5. **Einmal neu deployen** (Push auf `develop`). Die CI bindet die zwei Secrets nur ein,
   wenn es sie gibt – vorher läuft der Deploy unverändert durch.

## Im ERP

Ein Postfach wird dort verbunden, wem es gehört (Reiter **Kommunikation**, Zeile
«Postfach» → **Verbinden**):
* **Je eigene Gesellschaft eines** – an ihrem **Unternehmens-Datensatz**, nur ein
  **Admin**. Das verbundene Konto **wird** die **Kontakt-E-Mail** der Gesellschaft
  (dieselbe, die die Website im Land dieser Gesellschaft zeigt); **Trennen** leert sie.
  Ein Eingabefeld dafür gibt es nicht – die Adresse ist immer die des Postfachs.
* **Persönliche Postfächer gibt es nicht** (Migration `149`): im Kommunikationstool ist
  jeder Benutzer gleich. Ein früher verbundenes persönliches Postfach ist getrennt, seine
  Mails stehen beim Betreiber.

Anfragen aus dem **Kontaktformular der Website** landen im Postfach der Gesellschaft, die
die Website dem Besucher zeigt (sonst des Betreibers); die Bestätigung an den Kunden geht
über dasselbe Postfach hinaus.

## Was dann automatisch passiert

* Solange das ERP offen ist, wird jede Minute abgeglichen (der Server höchstens alle 30 s
  je Postfach). Gezählt wird ab dem Verbinden – alte Mails werden nicht importiert.
* Ein **unbekannter Absender wird als Person angelegt** (ohne Anmeldekonto; meldet er
  sich später mit dieser Adresse an, ist er genau dieser Datensatz). **Massenpost**
  (Werbung, Newsletter, «noreply», Gmail-Kategorien Werbung/Soziale Netzwerke/Benachrichtigungen/Foren)
  legt **keine** Kontakte an und erscheint nicht.
* **Das Anliegen ist der Betreff** (Migration `148`): was denselben Betreff trägt (ohne
  «Re:», «AW:», «Fwd:», ohne Gross/Klein), gehört zusammen. Eine spätere Nachricht **von
  uns** mit demselben Betreff erledigt die offenen – auch eine, die direkt in Gmail
  geschrieben und beim Abgleich übernommen wurde.
* **Erledigt im ERP = gelesen in Gmail** (nur in diese Richtung, nur die letzten 30 Tage):
  was beantwortet ist, verliert «Ungelesen». Dafür braucht es `gmail.modify` – **ein vor
  Migration `150` verbundenes Postfach muss einmal neu verbunden werden**, bis dahin bleibt
  in Gmail alles, wie es ist.
* Senden im ERP geht über Gmail hinaus, im selben Faden (gefunden über den Betreff);
  «Später senden» wartet bis zum Zeitpunkt. **Jede Mail geht genau einmal hinaus**: sie
  wird einzeln gesperrt, gesendet und sofort festgeschrieben. Scheitert der Versand, steht
  sie als «wartet auf Versand» da und wird beim nächsten Abgleich erneut versucht.
* Jede Mail trägt die **eine Vorlage** des Hauses (`services/mail_layout.py`): Kopf mit
  Logo, der Betreff als Überschrift, Unterschrift mit dem Menschen im Namen der
  Gesellschaft, Fuss mit Anschrift.
* Anhänge bleiben in Gmail; im ERP stehen ihre Namen und der Link «In Gmail öffnen».

## Grenzen im Testmodus

* Google lässt eine Verbindung im Status **Testen** nach **7 Tagen** ablaufen. Das ERP
  merkt es (roter Punkt, «Neu verbinden»). Dauerhaft wird es mit **Google Workspace** und
  einer **internen** App – dann ohne Prüfung und ohne Ablauf.
* Höchstens 100 Testnutzer.
