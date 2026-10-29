# Tiefenanalyse umgesetzt (28./29.10.2026)

Auftrag: eine zweite, tiefe Analyse des ganzen Systems – aufräumen, konsolidieren,
korrigieren, Altlasten weg, robuster, schlanker – und dann **alles** umsetzen, testen,
deployen. Sechs Prüfer lasen je einen Bereich (Beleg, Prozess, übriges Backend, Frontend,
Tests/CI/Infra, Doku/Website), rund 190 Befunde, jeder im Code belegt; die schwersten wurden
nachgeprüft. Umgesetzt in fünf parallelen Arbeitskopien (Phase 1) und einer für Tests/CI
(Phase 2), zusammengeführt auf `claude/integration`.

**Rollback-Punkte:** vor der Runde `57aec14` · Phase 1 auf dev `b58fd98` (Deploy grün,
Migrationen 163/164 auf den dev-Daten durchgelaufen).

## Entscheide des Auftraggebers
- **Fehler 1 – Nummer der Stornierung.** Geprüft: Art. 26 MWSTG verlangt die eindeutige
  Identifikation einer Rechnung, keine fortlaufende Nummer; die Praxis (und das
  ESTV-Formular für Entgeltsminderungen) verlangt, dass die Korrektur die Originalrechnung
  nennt. Umgesetzt: die Gutschrift ist ein **eigenes Papier mit eigener Nummer** und nennt
  die Rechnung mit Nummer und Datum; die Rechnung bleibt unverändert.
- **Fehler 3 – gesperrte Stücke in der Vorauswahl: kein Fehler.** Gesperrtes wird über eine
  Abweichung zurückgeholt; der Code nennt den Grund jetzt im Docstring.
- **Login-Lightbox** ist gewollt; korrigiert wurde nur die Rückkehrseite vom Magic Link
  (zwei Stilklassen, die es nicht gab).
- **E7 bleibt:** `language`, `notification_*` am Benutzer waren von einem Prüfer entfernt
  worden – zurückgenommen, weil am 18.10. «belassen» entschieden war. Entfernt sind nur
  `department`, `job_title` (und `orders.end_status`), Drop im Folge-Deploy.

## Was umgesetzt ist
- **Fehler:** doppelte Rechnungsnummer (eine Zählung für Rechnung und Gutschrift unter
  Sperre + Unique-Index, Migration 164); keine Sperren an Freigabe/Bestätigen/Beleg →
  `FOR UPDATE` an je einer Stelle (Tests mit zwei Sitzungen); Protokoll verlor den
  Vorher-Status; Entwurfsprüfung ≠ Freigabeprüfung → eine Funktion `release._checked`;
  Lieferantenrechnung über 0; Stornierung an mehrere Parteien; QR ohne volle Anschrift;
  Kunde umging Datenlücken; Stripe-Teilerstattungen (`Refund.list` je Erstattung); ein
  zurückgekehrtes Stück blieb stehen (Matrix S100); Ausbau gibt den Ort des Trägers;
  Autosave verlor die letzten Sekunden (`lib/saver.ts`, flush beim Verlassen, Speichern
  hintereinander); Mail-Abgleich blockierte an einer Mail bzw. an einem getrennten Postfach;
  51 `async`-Handler blockierten die Event-Loop (jetzt `def`, Webhook im Threadpool, Wächter
  `test_source_async`); Zeitzone (`core/clock`); «Letzter Login» nur bei Passkeys.
- **Sicherheit:** offene Weiterleitung nach dem Login (`/\t/evil.com`); `javascript:` im
  CAD-Link; Kontaktformular als Spam-Relais; Newsletter-Bestätigung per GET und Person vor
  der Bestätigung; unbestätigte E-Mail beim Anlegen; Dateien mit `Cache-Control: public`;
  zweiter Weg für den Absenz-Nachweis; signierte Links an einer Stelle (`core/signed`,
  `LINK_SECRET`, der alte Schlüssel prüft mit); Personendaten im 422-Log; Passkey-Challenges
  begrenzt (`services/visitor`).
- **Leistung/Robustheit:** Beleg-Karte 133–141 → 21–41 Abfragen; «zu tun» filtert in SQL;
  N+1 in Personen, Firmen, Dokumenten, `find_units` (40 → 1); Gegenpartei bekommt keine
  volle Auftragsrechnung; Migration 163: 19 Fremdschlüssel, `process_events` append-only per
  Trigger; Detailansichten auf React Query (Invalidierung an einer Stelle, `lib/feed`);
  Geld rechnet nur der Server (`VoucherEmbed.total`, `VoucherInvoice.net`).
- **Aufräumen:** `services/voucher.py` → Kern/Kopf/Geld/Handlungen/Ansicht;
  `services/process.py` → `release`/`process`/`order_state`; Frontend `fields`,
  `communication`, `process-diagram`, Feed-Seite geschnitten; Objektnummer Pflicht
  (Migration 164); `adopt.py` → `legal.adopt_templates`; eine Stelle für Personen
  (`people.ensure`); toter Code, Tokens, `tailwind-merge`, `pytest-asyncio`, Kommentare auf den
  Ist-Stand.
- **Doku/Website:** PROCESS_CORE 3'152 → 2'027 Zeilen (alte §9.15-Fassungen und die
  Zeichenregeln ausgelagert), falsche Aussagen korrigiert, FINDINGS/Cleanup/Konzept/Auftrag
  nach history, Design-Referenz entrümpelt; Website-Build 65 → 43 MB (WebP-Rückfall), Video
  nur ab 768 px, Pause-Knopf, Logo als Symbol, Budget zählt das Video.

- **Tests/CI (Phase 2):** 178 Quelltext-Tests, die nur die Form prüften, entfernt oder durch
  Verhalten ersetzt (`test_pieces_and_log`), Hausregeln nach ESLint; eine Fabrik für Personen
  und Firmen, eine Beleg-Szene; Gate in drei parallelen Jobs mit Cache, auch auf
  Feature-Branches; ein Deploy-Ablauf `deploy.yml` für dev und prod (einmal bauen, dann
  ausrollen); dev und prod min 0 / max 2 Instanzen (max 2 passt auf jede Cloud-SQL-Stufe);
  GeoIP-Schicht im Docker-Cache; Frontend-Dockerfile weg, docker-compose nur noch die DB.
- **Stripe:** eine Erstattung, die nach «ausstehend» scheitert, wird gegengebucht
  (`refund.updated`).

## Gemessen
- Backend-Tests 856 → 920 nach Phase 1 (neue Fehler-, Sicherheits- und
  Nebenläufigkeitstests, jeder gegen seine Bug-Form geprüft), 744 nach Phase 2 (Testcode
  29'099 → 23'304 Zeilen, Laufzeit 88 → 48 s); Frontend-Tests 45 → 63; Gate 3:05 → 2:13 min.
- Der Kanton-Wähler der Zeiterfassung (`company-time.tsx`) steht als einzige Ausnahme der
  ESLint-Regel `disabled={busy}` – er gehört an den Speicherweg der Zeiterfassung.
- Abfragen je Beleg-Karte, `find_units`, Gegenpartei-Antwort: siehe oben.

## Bewusst nicht
`VERBS`/`can`, Saldo als Ableitung, `vat_entry`-Toleranz, doppelter Endzustand-Schutz,
Ratelimit im Speicher, Gmail als Anhang-Speicher, Passkey-PIN-Pflicht (Entscheid offen),
eine Uhr für den Mail-Abgleich (Option), Firebase 13 (Node 24), Tailwind 4, TS 7.

## Danach erledigt (29.10.)
- `LINK_SECRET` auf dev angelegt, DB-Passwort dev neu, Uptime-Check auf `/health`,
  Stripe-Webhook hört `refund.updated`, alter JSON-Schlüssel gelöscht.
- **Befund beim Nachprüfen:** das WIF-Deploy-Konto durfte die Secrets nicht lesen; die
  Prüfung «gibt es das Secret?» hielt darum alle für fehlend, und der Deploy band nur
  `DATABASE_URL` (und das eben freigegebene `LINK_SECRET`) ein – grün, aber ohne
  Firebase, Stripe, Gmail, KI und Karten. Jetzt: eine Liste (`gcloud secrets list`, Rolle
  `secretmanager.viewer`), Pflicht-Secrets fehlen → rot, Liste unlesbar → rot.

## Offen danach
- `LINK_SECRET` auf prod anlegen (vor dem Go-live).
- Folge-Deploy: Drops `orders.end_status`, `user_profiles.department`, `job_title`.
