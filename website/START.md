# Website – Start-Checkliste (gültig)

> Die eine gültige Liste für den Wechsel von `SITE_MODE=preview` auf `live`. Sie ersetzt die
> Checkliste aus `docs/history/2026-10-04-website-report.md` §6 (Cleanup Oktober 2026, W-40):
> dort standen noch SMTP-Versand, Servicezeile und der Prod-Rewrite als offen – alle drei
> sind erledigt bzw. entfallen. Offene **Inhalte** (Fotos) stehen in `OFFENE_PUNKTE.md`
> (generiert, nie von Hand ändern).

## Vor dem Umschalten

- [x] Freigabe von Heiri Steiner: Texte, Zitat, Fotos, Namenswechsel (23.11.2026)
- [x] Kein Foto fehlt auf einer Seite (`OFFENE_PUNKTE.md`: 0 blockieren); weitere Fotos vom Fototag
      kommen nach und nach – im Modus `live` bricht der Build bei jedem fehlenden Foto ab
- [x] `SITE_MODE=live` und `SITE_URL=https://inexxio.com` im Produktions-Workflow (23.11.2026)
- [x] **Anfragen landen im ERP**: das Postfach der eigenen Gesellschaft ist verbunden
      (`docs/gmail-setup.md`) – sonst wird die Anfrage gespeichert, die Bestätigung an den
      Kunden geht aber nicht hinaus. Lässt sich eine Anfrage gar nicht speichern, zeigt das
      Formular Telefon und `mailto:` (503).
- [x] Kontaktdaten (Telefon, E-Mail, Anschrift) stehen am Datensatz der Gesellschaft im ERP –
      Website und Formular lesen sie von dort (`GET /api/v1/public/contact`)
- [ ] AGB und Datenschutz rechtlich prüfen und anpassen: sie sind **Dokumente je eigener
      Gesellschaft** (ERP → Gesellschaft → Karte «Rechtstexte», «Aus Vorlage übernehmen» nur
      Admin); die Vorlagen liegen in `backend/app/assets/legal/agb/<gültig ab>.md` bzw. `…/datenschutz/…`
- [x] Login, Profil und ERP einmal mit einem echten Konto durchklicken (Mitarbeiter und
      Kunde): Profilmenü, «ERP» im Menü, Abmelden – auf Website **und** im ERP
- [x] Test auf iPhone (Safari) und Android (Chrome); externe Links einmal öffnen

## Beim Umschalten

- [x] Domain mit Firebase Hosting verbinden (22.11.2026) (keine eigene Weiterleitungs-Site für hs-steiner.ch –
      Entscheid 21.11.2026)
- [x] Formular und Login in Produktion einmal testen (Anfrage steht im ERP, Bestätigung kommt an)
- [ ] Google Search Console und Bing Webmaster Tools: Domain bestätigen, Sitemap einreichen,
      Adressänderung melden

## Ausserhalb der Website

- [ ] Google-Unternehmensprofil umbenennen («INEXXIO – ehemals HS Steiner»), Bing Places,
      Apple Business Connect, local.ch/search.ch – überall derselbe Name
- [ ] E-Mail-Weiterleitungen der bisherigen Adressen und neue Signaturen

## Bereits erledigt (nicht mehr prüfen)

- Der `/api/**`-Rewrite zeigt in Prod auf den Prod-Dienst (`deploy-prod.yml` setzt ihn per
  `jq` und bricht ab, wenn danach ein anderer Dienst steht).
- Kein SMTP mehr: Anfrage und Bestätigung laufen über das ERP (`services/inquiry`).
- Kein Einwilligungs-Dialog: die eigene Statistik setzt keine Cookies und speichert keine IP
  (`services/site_stats`, November 2026).
