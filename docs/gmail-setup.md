# Gmail anbinden (CRM Schritt 3)

Gmail ist das Postfach, das ERP der Verlauf. Ohne die beiden Schlüssel unten gibt es
keine Anbindung – eine E-Mail wird dann wie bisher nur **erfasst**, nicht gesendet.

## Einmalig in der Google Cloud Console (Projekt `inexxio-dev`)

1. **Gmail API aktivieren** – *APIs & Dienste → Bibliothek → Gmail API → Aktivieren*.
2. **OAuth-Zustimmungsbildschirm** – Typ **Extern**, Status **Testen**. App-Name
   «Inexxio», Support-Mail eintragen. Bereiche: `gmail.readonly`, `gmail.send`.
   Unter **Testnutzer** jedes Konto eintragen, das verbunden wird (z. B.
   `info.inexxio@gmail.com` und die persönlichen Adressen der Mitarbeiter, höchstens 100).
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
  **Admin**. Es muss das Konto sein, das dort als **Kontakt-E-Mail** steht (dieselbe, die
  die Website im Land dieser Gesellschaft zeigt) – sonst lehnt das ERP ab und sagt,
  welches.
* **Persönlich**: jeder Mitarbeiter an seinem **eigenen** Benutzer-Datensatz.

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
* Eine Antwort in Gmail beantwortet die Nachricht im ERP (über `In-Reply-To`/`References`).
* Senden im ERP geht über Gmail hinaus, im selben Faden; «Später senden» wartet bis zum
  Zeitpunkt. Scheitert der Versand, steht die Mail als «wartet auf Versand» da und wird beim
  nächsten Abgleich erneut versucht.
* Anhänge bleiben in Gmail; im ERP stehen ihre Namen und der Link «In Gmail öffnen».

## Grenzen im Testmodus

* Google lässt eine Verbindung im Status **Testen** nach **7 Tagen** ablaufen. Das ERP
  merkt es (roter Punkt, «Neu verbinden»). Dauerhaft wird es mit **Google Workspace** und
  einer **internen** App – dann ohne Prüfung und ohne Ablauf.
* Höchstens 100 Testnutzer.
