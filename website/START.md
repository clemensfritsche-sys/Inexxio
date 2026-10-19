# Website – Start-Checkliste (gültig)

> Die eine gültige Liste für den Wechsel von `SITE_MODE=preview` auf `live`. Sie ersetzt die
> Checkliste aus `docs/history/2026-10-04-website-report.md` §6 (Cleanup Oktober 2026, W-40):
> dort standen noch SMTP-Versand, Servicezeile und der Prod-Rewrite als offen – alle drei
> sind erledigt bzw. entfallen. Offene **Inhalte** (Fotos) stehen in `OFFENE_PUNKTE.md`
> (generiert, nie von Hand ändern).

## Vor dem Umschalten

- [ ] Freigabe von Heiri Steiner: Texte, Zitat, Fotos, Namenswechsel
- [ ] Fototag; Fotos in `src/config/photos.mjs` eintragen (jedes ersetzt ein Beispielbild) –
      im Modus `live` bricht der Build bei jedem verbliebenen Beispielbild ab
- [ ] `OFFENE_PUNKTE.md` leer, dann `SITE_MODE=live` und `SITE_URL=https://<Domain>` im
      Produktions-Workflow
- [ ] **Anfragen landen im ERP**: das Postfach der eigenen Gesellschaft ist verbunden
      (`docs/gmail-setup.md`) – sonst wird die Anfrage gespeichert, die Bestätigung an den
      Kunden geht aber nicht hinaus. Lässt sich eine Anfrage gar nicht speichern, zeigt das
      Formular Telefon und `mailto:` (503).
- [ ] Kontaktdaten (Telefon, E-Mail, Anschrift) stehen am Datensatz der Gesellschaft im ERP –
      Website und Formular lesen sie von dort (`GET /api/v1/public/contact`)
- [ ] AGB rechtlich prüfen und anpassen (`frontend/src/app/(public)/agb/`)
- [ ] Login, Profil und ERP einmal mit einem echten Konto durchklicken (Mitarbeiter und
      Kunde): Profilmenü, «ERP» im Menü, Abmelden – auf Website **und** im ERP
- [ ] Test auf iPhone (Safari) und Android (Chrome); externe Links einmal öffnen

## Beim Umschalten

- [ ] Domain mit Firebase Hosting verbinden; hs-steiner.ch per 301 weiterleiten – dafür eine
      eigene Hosting-Site mit derselben Tabelle plus Fangregel «alles andere → Startseite»
      (auf der neuen Site wäre diese Regel ein Fehler, WEBSITE_PLAN Entscheid 40)
- [ ] Formular und Login in Produktion einmal testen (Anfrage steht im ERP, Bestätigung kommt an)
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
- Keine Statistik, kein Einwilligungs-Dialog (Plausible entfernt, Oktober 2026).
