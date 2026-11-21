# Cleanup-Analyse: Doku und Tests (INEXXIO, `develop` @ `fbd70fc`)

Ich habe nur gelesen. Im Repository ist keine Datei geändert, `git status` ist sauber. Die pytest-Läufe
liefen mit `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`, und die vorhandenen Cache-Verzeichnisse sind
älter als diese Sitzung.

Massstab ist der Code in `backend/app` und `frontend/src`. Jeder Befund nennt eine Fundstelle und
sagt, wie er geprüft wurde.

---

## Kurzfassung

1. **CLAUDE.md besteht zu 93 % aus der Chronik der Runden.** Die Zeilen 1–5225 sind ein einziger
   Blockquote mit Rundenberichten. Nur die Zeilen 5226–5618, also etwa 390, beschreiben den heutigen
   Stand. Etwa 2'200 Zeilen der Chronik handeln von gelöschten Modulen:
   - Beschaffen/Verkauf: ca. 1046–1862
   - `deal` («Zahlung (alt)»): ca. 1863–3340
2. **Auch der Teil zum heutigen Stand ist fehlerhaft.**
   - «Was heute steht» nennt das Verb `issue` (gelöscht mit #1047).
   - Dort steht auch «Rechnungen und Zahlungen als Zeilen daneben». Seit Migration 138 ist der Beleg selbst die Rechnung.
   - «ausser Betrieb nehmen ist ein Statuswechsel in beide Richtungen» widerspricht #773.
   - Der Leitbild-Abschnitt nennt TS-Unions `StepType`/`LocationType`, die es nicht gibt.
   - «Autosave 3 s» stimmt nur für einen von zwei Hooks.
   - CRM, Kommunikation und Gmail fehlen in «Was heute steht» ganz.
3. **Die API-Tabelle in backend/CLAUDE.md ist falsch.**
   - Sie führt 6 Endpunkte, die es nicht gibt: `/auth/me/company`, `/orders/deal-parties`, `…/deal`, `…/deal/payment`, `…/deal/refund`, `…/deal/transfer`.
   - 15 vorhandene Endpunkte fehlen, darunter das ganze `…/voucher*`, `/auth/me/addresses*`, `/erp/records/{id}/addresses*`, `/erp/messages/channels|open`, `/public/contact`.
   - 2 Zeilen stehen doppelt.
   - Mindestens 2 Auth-Angaben sind falsch.
   - Im Code gibt es **86 Endpunkte**.
4. **Die «verbindliche» PROCESS_CORE.md beschreibt Gelöschtes als gebaut.**
   - §9.12–§9.14c (Z. 1797–2774, ca. 980 Zeilen) beschreibt das gelöschte `deal`-Modul mit 35 Verweisen auf `deal.*`. Der Kopf behauptet dazu «Status: gebaut — die EINZIGE Maschine».
   - §9.15q führt `issue` als aktuelle Stufenhandlung (Z. 3276–3289); #1047 ist dort nie nachgezogen.
5. **Betriebsdokus sind veraltet, mit echter Wirkung.**
   - `docs/gmail-setup.md` nennt die Scopes `gmail.readonly`/`gmail.send`. Der Code verlangt `gmail.modify` + `gmail.send` + `userinfo.profile`.
   - Dieselbe Datei beschreibt persönliche Postfächer, die Migration 149 entfernt hat.
   - `docs/stripe-setup.md` nennt als Metadaten `deal_id`/`charge_id`. Der Code schreibt `voucher_id`.
6. **Die Rollback-Tags gibt es nicht.** `attic/pre-cleanup-2026-08` und `rollback/basis-20260806` werden in CLAUDE.md und
   docs/attic.md als Wiederherstellungspunkt genannt. `git ls-remote origin` liefert über den Proxy aber **0 Tags**.
7. **Mehrere Doku-Dateien sind erledigt und gehören nach `docs/history/`.**
   - `docs/arbeitsauftrag-beleg*.md`, `konzept-*.md`, `neuaufbau-zahlungsmodul.md`, `beleg-pflichtangaben.md`, `cleanup-2026-08.md`
   - `ANALYSE_RETOURE_20260917.md` (trägt selbst den Vermerk «ÜBERHOLT»)
   - `TEST_REPORT.md` (meldet 71 Fälle, die Matrix hat heute **77**)
   - Grösstenteils `FINDINGS.md`
   - Kein Test liest eine dieser Dateien. Nur Code-Kommentare verweisen auf sie (z. B. `neuaufbau-zahlungsmodul` in 8 Code-Dateien).
8. **`test_frontend_mirrors.py` ist im Kern ein Quelltext-Grep, kein Spiegeltest.**
   - Die Datei hat 10'499 Zeilen und 322 Tests.
   - 3'360 Zeilen sind Docstrings und 1'035 Kommentare, also nur ca. 4'550 Zeilen Code.
   - Sie enthält 681 `assert "…" in …` und 27 Zählprüfungen nach dem Muster `count("x") == n`.
   - Echte Spiegel über die API-Grenze sind es nur 5 Tests.
   - 55 Tests sind Wiederkehr-Wächter («ist zurück»), davon sind etwa 10 reine Grabsteine für gelöschte Module.
   - Die Datei läuft in 2,8 s.
9. **Es gibt tote und doppelte Tests.**
   - `test_the_two_vat_catalogues_do_not_drift` wird immer übersprungen.
   - `test_it_does_not_import_a_line_of_the_old_module` prüft Importe von Modulen, die es nicht gibt.
   - 4 Testnamen kommen in zwei Dateien vor. Bei `test_the_chain_is_resolved_per_holder_not_per_piece` (material_place ↔ move_module) ist es auch inhaltlich dieselbe Prüfung.
   - Es gibt keine `conftest.py`. Die DB-Fixture `_db()` ist 12-fach kopiert und verhält sich uneinheitlich: Ohne PostgreSQL überspringen sich 208 Tests, 80 werden dagegen rot (37 failed, 43 errors).
10. **In der CI fehlt einiges.**
    - Ein Python-Linter läuft nicht (`.ruff_cache` existiert lokal, ruff ist in der CI nicht konfiguriert).
    - Der Frontend-Build ist kein Quality-Gate. Er läuft erst im Deploy-Job, **nachdem** das Backend ausgerollt ist.
    - Der Dev-Deploy nutzt `npm install` statt `npm ci`.
    - Skips laufen ohne `-rs` und ohne Pflicht-DB, ein DB-Ausfall würde also unbemerkt grün.
    - `deploy-prod.yml` hat keine eigenen Prüfungen.
    - Es gibt keinen Wächter «jede Route in `api.ts` existiert im Backend». Messung: `api.deleteStep` ruft `DELETE /erp/{owner}/{id}/steps/{id}`, den es nicht gibt, und hat keinen Aufrufer.

---

## Befundtabelle

Risiko meint das Risiko der **vorgeschlagenen Änderung**: niedrig = reine Doku/Testpflege,
mittel = berührt Verweise oder CI-Verhalten, hoch = verändert Schutzwirkung.

### Doku

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | wie geprüft |
|---|---|---|---|---|---|---|
| D-01 | 4 Struktur | `CLAUDE.md:1–5225` | 93 % der Datei sind ein Rundenprotokoll (Blockquote ab Z. 3, Rundenköpfe Z. 728…5215); der Stand steht in Z. 5226–5618. Jede Sitzung liest 459 kB. | Chronik unverändert nach `docs/history/2026-08-10-claude-chronik.md`; CLAUDE.md neu nach Gliederung unten (~300–400 Z.). | niedrig | `awk` über Blockköpfe, `wc -c` |
| D-02 | 1 | `CLAUDE.md:1046–1862` | Beschaffen, Verkauf, «Einkauf im Bewegen», Geld als Zeile (`domain/procurement`, `domain/money`, `services/purchase`) werden ausführlich als Regelwerk beschrieben – alles gelöscht. | → Chronik (D-01). | niedrig | `ls backend/app/domain` (kein procurement/money), `ls services` (kein purchase/invoices/payments) |
| D-03 | 1 | `CLAUDE.md:1863–3340` | ~1'480 Zeilen über das gelöschte `deal`-Modul (62 Treffer `deal`/`Geldvorgang`). | → Chronik. | niedrig | `ls domain/deal.py services/deal.py` = fehlt |
| D-04 | 1 | `CLAUDE.md:4121–4207` | Sammelzahlung `voucher_allocations` als Regel; mit Z. 4419ff. zurückgenommen, Modell gelöscht (`models/voucher.py:422` «Hier stand VoucherAllocation»). | → Chronik. | niedrig | grep `VoucherAllocation` in app = nur Kommentare |
| D-05 | 1 | `CLAUDE.md:4540–4605` | «Kontotyp» (`domain/accounts.py`, `assert_account`) – gelöscht mit #1043. | → Chronik. | niedrig | grep app: 0 (`account_type` nur Kommentar `main.py:148`) |
| D-06 | 1 | `CLAUDE.md:4891–4940` | CRM 1b: `PATCH /auth/me/company`, `update_member_company`, `CompanyEditor` – gelöscht (selbst in Z. 4938 vermerkt). | → Chronik. | niedrig | Endpunkt fehlt in Router-Liste; grep FE `CompanyEditor` = 0 |
| D-07 | 1 | `CLAUDE.md:5572–5573` | **«Was heute steht»**: «drei Verben (`bill` · `issue` · `unbill`) … endet, wo … versendet». `issue` gelöscht (#1047). | Neu schreiben: «zwei Verben `bill`·`unbill`; Rücknahme bis Geld geflossen». | niedrig | `services/voucher.py:1434 VERBS` = …bill unbill pay… (kein issue) |
| D-08 | 2 | `CLAUDE.md:5532–5533` | «Rechnungen und Zahlungen als Zeilen daneben» – seit Migr. 138 ist der Beleg die Rechnung, Zeilen sind nur Zahlungen. | korrigieren. | niedrig | `domain/voucher.py:91 STAGES=(offer,agreed,billed)` |
| D-09 | 2 | `CLAUDE.md:5523–5524` | «ausser Betrieb nehmen ist ein Statuswechsel in beide Richtungen» widerspricht #773 (Status = Projektion von `replaced_by_id`, kein Schalter) und backend/CLAUDE.md:107. | korrigieren. | niedrig | Text-Vergleich; SYSTEM_LOGIC.md:54 «inaktiv … abgeleitet aus replaced_by_id» |
| D-10 | 2 | `CLAUDE.md:5508–5585` | «Was heute steht (Stand August 2026)» kennt CRM (Firma-Datensatz, Adressbuch, UID-Schlüssel), Kommunikation, Gmail und das Kontaktformular→ERP nicht – das steht nur in der Chronik (Z. 4891–5222). | Abschnitt «CRM & Kommunikation» in den Stand. | niedrig | grep in Z. 5505–5602: 0× «Kommunikation»/«Gmail»/«Adressbuch» |
| D-11 | 2 | `CLAUDE.md:5408` | Leitbild: Spiegeltest vergleicht `StepType`, `LocationType`, `ArticleUnit`. Die ersten beiden existieren nicht, keiner davon steht im Test. | Liste aus den echten Spiegeltests ableiten (T-09). | niedrig | grep FE `type StepType`/`LocationType` = 0; Test: 0 Treffer |
| D-12 | 2 | `CLAUDE.md:5440` | «Autosave debounced 3 s» – es gibt **zwei** Hooks: `components/account/use-autosave.ts` (3000 ms, 6 Nutzer) und `lib/use-autosave.ts` (1500 ms, 1 Nutzer). Auch ein Code-Befund («eine Sache, eine Stelle»). | Doku auf den Stand; Duplikat an Code-Analyse weitergeben. | niedrig | grep `delay =` in beiden Dateien |
| D-13 | 2 | `CLAUDE.md:5442` | «MWST … für den späteren Beleg vorgemerkt» – der Beleg existiert, Katalog inkl. `reverse` in `domain/voucher.py:874–881`. | «gebaut, Katalog in domain/voucher.VAT_RATES». | niedrig | Read |
| D-14 | 1 | `CLAUDE.md:628, 659`; `docs/attic.md` (Tag) | «abgeschaltete Bereiche (`ai`, `selling`)» (gelöscht); **Rollback-Tag `rollback/basis-20260806`** und `attic/pre-cleanup-2026-08` werden als Wiederherstellungsweg genannt – `git ls-remote origin` zeigt **0 Tags** (6 Fundstellen in Doku). | Tags prüfen/setzen oder Doku auf Commit-Hashes umstellen (attic nennt teils schon `git log -- …`). | mittel (Wiederherstellbarkeit) | `git ls-remote origin \| grep -c refs/tags` = 0 (über Session-Proxy, Heads sichtbar) |
| D-15 | 2 | `CLAUDE.md` (Zitate) | Zitierte Wächter, die es nicht gibt: `test_the_article_status_has_exactly_one_vocabulary` (heisst `test_the_article_status_has_exactly_one_source`, `test_invariants.py`), `test_account_type.py`, `test_deal_module.py`, `test_purchase_module.py`, `test_invoices.py`, `test_sales_module.py`, `test_a_shop_checkout_needs_no_new_endpoint`. | Bei Neuschnitt nur existierende nennen. | niedrig | 61 zitierte `test_*`-Namen gegen `backend/tests` gegrept |
| D-16 | 1/2 | `backend/CLAUDE.md:93–157` | API-Tabelle «tatsächlich vorhanden»: 6 nicht existente Endpunkte (`PATCH /auth/me/company`, `GET /orders/deal-parties`, `POST …/deal`, `…/deal/payment`, `…/deal/refund`, `GET …/deal/transfer`); 2 Doppelzeilen (`name-suggestions` Z.105/110, `stock` Z.109/111); fehlend: `POST/PATCH/DELETE /auth/me/addresses*`, `POST/PATCH/DELETE /erp/records/{id}/addresses*`, `GET /orders/voucher-parties`, `POST …/voucher`, `…/voucher/payment`, `…/voucher/refund`, `GET …/voucher/transfer`, `…/voucher/correctable`, `GET /erp/messages/channels`, `GET /erp/messages/open` (nur im Fliesstext), `GET /public/contact`. | Tabelle aus Routern generieren (Liste unten); idealerweise per Skript + CI-Diff (wie `dump_openapi`). | niedrig | Regex über `app/routers/*.py` + `main.py:1092–1107` |
| D-17 | 2 | `backend/CLAUDE.md:99, 117` | Auth falsch: `GET /erp/companies` «user» → Code `require_employee` (`erp.py:89–93`); `GET /erp/objects/{id}` «user» → `require_employee` (`erp.py:49–53`); `PATCH /erp/records/{id}` «staff/admin» → nur `require_admin` (`erp.py:121`). | Auth-Spalte aus Code. | niedrig | Read der Signaturen |
| D-18 | 1 | `backend/CLAUDE.md:165–168` | «Bewegt über zwei Befehle: `confirm` und `deal`» – `deal` gelöscht, heute `voucher`. | korrigieren. | niedrig | Router-Liste |
| D-19 | 1/4 | `backend/CLAUDE.md:209–932, 966–999, 1014–1495` | ~1'100 Zeilen Rundenprosa im Abschnitt «API-Endpunkte» und hinter «Konventionen»/«Tote Stellen» (48 `deal`-Treffer in 209–789; `deal_entries`, `DealUpdate`, `domain/deal.VAT_RATES`, `deals.issuer_company_id` …). | → `docs/history/`; Datei auf ~200 Z. | niedrig | `grep -n "^> ►►►"` |
| D-20 | 2 | `backend/CLAUDE.md:36–45` | Struktur-Baum `domain/` ohne `communication.py`, `incoterms.py`, `uid.py`; `scripts/` ohne `build_geoip.py`. | ergänzen. | niedrig | `ls` |
| D-21 | 1 | `frontend/CLAUDE.md:329, 333` | Bauteil-Tabelle `module-ui` führt `ModuleMeta` und `ConfirmButton` als vorhanden – beide entfernt (`module-ui.tsx:275, 502` «Hier stand …»). | Tabelle aus Exporten von `module-ui.tsx` ableiten. | niedrig | grep FE: nur Kommentar-Treffer |
| D-22 | 1 | `frontend/CLAUDE.md:233, 366, 905, 979–1015` | Abschnitte zu gelöschtem Beschaffen/Verkauf, `deal-work.tsx`, Grund/Sammelzahlung, **Kontotyp** (`UserProfileResponse.account_type` – existiert nicht; Z. 989). | → history. | niedrig | grep `account_type` in schemas = 0 |
| D-23 | 2 | `frontend/CLAUDE.md` gesamt | Kein Abschnitt zu `communication.tsx`, `address-book.tsx`, `company-field.tsx` (0 Treffer «Kommunikation»). | Abschnitt CRM ergänzen. | niedrig | grep |
| D-24 | 2 | `frontend/CLAUDE.md:43–60` | Routenbaum ohne `(auth)/abmelden`. | ergänzen. | niedrig | `ls src/app/(auth)` |
| D-25 | 1 | `PROCESS_CORE.md:1797–2774` | §9.12–§9.14c beschreiben das gelöschte `deal`-Modul (35 `deal`-Treffer: `deal.PARTY`, `deals.agreed_lines`, `domain/deal.balance` …); Kopf §9.12: «Status: gebaut — die EINZIGE Maschine». Kein Code verweist auf §9.12–§9.14 (0 Treffer). | → `docs/history/2026-09-zahlungsmodul-vorgaenger.md` anhängen; in PROCESS_CORE 5–10 Zeilen «Entscheidungen, die im Beleg weiter gelten». | niedrig | grep `§9.12`/`§9.13`/`§9.14` in Code = 0 |
| D-26 | 2 | `PROCESS_CORE.md:3276, 3285–3289` | §9.15q: Stufentabelle `billed → issue («Rechnung ist versendet»)`, `unbill` bis «versendet». #1047 nie nachgezogen (0× «1047»). | korrigieren. | niedrig | grep |
| D-27 | 2 | `SYSTEM_LOGIC.md:533, 537` | Verweis auf `invoices.is_overdue` (gelöscht) und `deals.agreed_lines` (gelöscht; heute `voucher_lines`), «es gibt keinen Versandweg (kein E-Mail)» – Gmail-Versand existiert. | korrigieren. | niedrig | `ls services/invoices.py` fehlt; `services/mailbox.py` |
| D-28 | 3 | `TEST_REPORT.md` | Momentaufnahme der Testkampagne («71 Fälle», «337 Aufträge …»); `matrix.CASES` hat heute **77**. | → `docs/history/`; die laufende Wahrheit ist `scripts/scenario_report.py`. | niedrig | `len(matrix.CASES)` = 77 |
| D-29 | 3 | `FINDINGS.md` | Audit-Bericht, 🟠 alle erledigt; Fund 4 nennt `services/ai`, `services/selling` (gelöscht). Offen: 🟡-1 (in `matrix.py:1032` als `open_finding` referenziert), 🟡-2…5. | Offene 🟡 nach `docs/backlog.md`, Rest → history; `matrix.py:1032`-Verweis anpassen. | mittel (Verweis im Test-String) | Read; grep |
| D-30 | 3 | `ANALYSE_RETOURE_20260917.md` | trägt selbst «ÜBERHOLT» (Z. 5ff.). | → history. | niedrig | Read |
| D-31 | 3 | `docs/arbeitsauftrag-beleg.md`, `-beleg-2.md`, `beleg-pflichtangaben.md`, `konzept-eine-rechnung-je-modul.md` («UMGESETZT»), `konzept-beleg-shop-besitz.md` («nichts davon umgesetzt», Stand 13.09.), `neuaufbau-zahlungsmodul.md`, `cleanup-2026-08.md` | erledigte Aufträge/Konzepte/Berichte. Verweise: `neuaufbau-zahlungsmodul` aus 8 Code-Dateien + 3 Tests (nur Strings/Kommentare), `cleanup-2026-08` aus 3 Code-Dateien. | → `docs/history/2026-09-*`; Verweise in Kommentaren mitziehen. `konzept-beleg-shop-besitz` nur, falls «Shop/Besitz» nicht mehr geplant – sonst als offenes Konzept stehen lassen. | niedrig–mittel | Kopfzeilen gelesen; Verweis-grep |
| D-32 | 2 | `docs/gmail-setup.md:10, 12, 37` | Scopes `gmail.readonly`, `gmail.send` – Code: `gmail.modify`, `gmail.send`, `userinfo.profile` (`services/mailbox.py:62–64`); «persönlich: jeder Mitarbeiter …» – seit Migr. 149 entfernt. **Betriebsrelevant** (OAuth-Zustimmungsbildschirm). | korrigieren (vorrangig). | niedrig | Read + grep |
| D-33 | 2 | `docs/stripe-setup.md:13, 70, 79, 210, 245` | `services/deal.record_payment`, `deal_entries.vat`, Metadaten `deal_id`·`charge_id`, `DealEmbed.can` – Code: `stripe_pay.MONEY = (("voucher_id", voucher_svc, Voucher),)` (Z. 95–96). | auf `voucher` ziehen. | niedrig | Read |
| D-34 | 2 | `docs/attic.md:30, 54` | Geldvorgang = `domain/deal`, `deal.record_payment` – beides gelöscht; kein Eintrag für «Zahlung (alt)», «Ausliefern», «Kontotyp», «Objekt scannen». | Einträge ergänzen bzw. auf `voucher` korrigieren. | niedrig | grep |
| D-35 | 2 | `docs/history/README.md` | Index ohne `2026-09-zahlungsmodul-vorgaenger.md`. | ergänzen (+ neue Dateien aus D-01/D-31). | niedrig | `ls docs/history` vs Tabelle |
| D-36 | 2 | `docs/adr/001-tech-stack.md:3–6` | Kopfstatus: «Nicht verdrahtet: Stripe, … Gmail API» – beide verdrahtet. | Kopfstatus aktualisieren. | niedrig | `services/stripe_pay.py`, `services/mailbox.py` |
| D-37 | 2 | `docs/adr/005-logistik.md:3–6`, `006-…:3–8` | 005 verweist auf `domain/procurement.py` (gelöscht); 006: «Konsequenz entsteht erst wieder, wenn es Belege gibt» – Belege gibt es (`vouchers.issuer_company_id`), Gebietskarte speist `/public/contact`. | Kopfstatus aktualisieren. | niedrig | `ls`, Read |
| D-38 | 2 | `docs/Lastenheft_v1.0.md:56, 76, 113` | «Final, verbindlich»: TOTP-MFA Admin «verpflichtend» (nicht gebaut, CLAUDE.md:5455 «vorgemerkt»); **Z. 113 «CLAUDE.md nach jeder Session aktualisieren»** – die Regel, aus der die Chronik entstand. | Kopfstatus mit Abweichungen; Regel ändern: «Stand aktualisieren, Rundenbericht in docs/history». | niedrig | Read |
| D-39 | 2 | `.claude/skills/feedback/SKILL.md:44–51, 61–66` | Einstieg «Beschaffen → `purchase-work.tsx`», «`services/purchase.mine`», `Rolle supplier`/`customer` – alles gelöscht; empfiehlt `PanelHeader`/`SectionTitle` (exportiert, aber **0 Nutzer**), heute markiert `ModuleSection` (`module-ui.tsx:430 data-fb-section`). | Skill auf `beleg-work.tsx`, `ModuleSection`, Rollen admin/employee/user ziehen. | niedrig | `ls components/erp`; grep Nutzer |
| D-40 | 2 | `.claude/skills/inexxio-design-system/SKILL.md:52–56, 58–60` | «Alt-Palette kompiliert noch» – laut CLAUDE.md und grep 0 Vorkommen; empfiehlt `PrimaryButton` (existiert nicht in `fields.tsx`), `PanelHeader`/`SectionTitle` (ungenutzt). | aktualisieren. | niedrig | grep (die 2 Treffer für `slate-` sind `-translate-`) |
| D-41 | 2 | Code-Docstrings (Grenzfall, eher für Code-Analyse) | Veraltete Verweise im Code: `domain/__init__.py:12` listet `procurement`; `domain/voucher.py:40` «Steuerkatalog steht auch in domain/deal.py»; `core/config.py:99` `services/deal.can`; dazu viele «Hier stand …»-Grabstein-Kommentare (z. B. `models/voucher.py:191, 422`, `domain/voucher.py:693, 724, 1103`). | an Code-Analyse übergeben. | niedrig | grep |
| D-42 | 3 | `SYSTEM_INTENT.md`, `README.md` (Root) | nicht im Umfang, aber Root-Doku: SYSTEM_INTENT ist ein Vor-Review-Dokument (Inhalt nicht gegen Code geprüft). | prüfen, ob nach history. | – | Kopf gelesen |

### Tests

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | wie geprüft |
|---|---|---|---|---|---|---|
| T-01 | 5 | `test_voucher_module.py:504–528` | `test_the_two_vat_catalogues_do_not_drift` überspringt sich **immer** (`domain/deal.py` existiert nicht). Docstring: «stirbt mit dem alten Modul». | löschen. | niedrig | Lauf: `SKIPPED … Das alte Zahlungsmodul ist gelöscht` |
| T-02 | 5 | `test_voucher_module.py:480–501` | `test_it_does_not_import_a_line_of_the_old_module` verbietet Importe von `deal`/`purchase`/`invoices`/`payments`/`money` – Module existieren nicht; ein Import würde ohnehin `test_no_undefined_names` (Importierbarkeit) brechen. | löschen. | niedrig | `ls`; `test_no_undefined_names.py:15` |
| T-03 | 5 | `test_frontend_mirrors.py:5896` (`…trade_modules_are_gone…`), `:7949` (`…previous_payment_module_is_gone…`), `:205` (`…old_process_concepts_stay_gone`), `:963` (`…object_scan…is_gone`), `:4877` (`…usage_tab_is_gone`); `test_article_lifecycle.py:580`; `test_communication.py:288`; `test_user_record.py:111, 454` | Grabsteine: prüfen, dass gelöschte Dateien/Namen nicht existieren (15 `not ….exists()` allein in mirrors). Schutzwert gering (Wiedereinführung unter neuem Namen fällt nicht auf), Pflegeaufwand real (Namenslisten). | Zu **einem** `test_removed_stays_removed` mit Datenliste zusammenfassen oder streichen; die Entscheidung steht in `docs/attic.md`. | niedrig | `grep -c "assert not .*exists()"`; Lesen |
| T-04 | 6 | `test_frontend_mirrors.py` gesamt | 681 `assert "literal" in …`, 27 `.count("x") == n`, 106 `.index(`, 223 `_body/_component`-Schnitte. Beispiele für Form statt Regel: `:277` `count("next_object_id") == 2  # Import + EIN Aufruf`; `:153` `count("insert(InstanceUnit)") == 1`; `:306–315` «`disabled` kommt in detail-tabs.tsx nicht vor» (jedes Vorkommen des Wortes bricht). CLAUDE.md protokolliert selbst ≥ 15 Fälle «Wächter prüfte die Form der alten Lösung» und ≥ 20 «stumpfe» Wächter. | Neue Wächter bevorzugt als Verhaltens-/Komponententest (Frontend: `node --test` gegen echte Quelle wie `when.test.mjs`, oder Playwright); bestehende Grep-Wächter beim Anfassen auf AST/Export-Ebene (`tsc`-API) heben. | mittel | Zählungen per Skript (AST + Regex) |
| T-05 | 6 | `test_frontend_mirrors.py` | 3'360 Docstring- + 1'035 Kommentarzeilen bei ~4'550 Code-Zeilen; 381 Testnotiz-Nummern, 181× «Bug-Form» – die Datei ist zugleich Rundenchronik. | Docstrings auf Regel + Bug-Form (≤ 5 Z.) kürzen; Historie gehört nach `docs/history`. | niedrig | AST-Zählung |
| T-06 | 6 | `test_material_place.py:348` ↔ `test_move_module.py:437` | Gleicher Name **und** gleicher Inhalt (Abfragen zählen für 60 Stücke in einem Regal). | einen streichen. | niedrig | Read beider |
| T-07 | 6 | `test_frontend_mirrors.py:10023` ↔ `test_user_record.py:566`; `:8450` ↔ `test_voucher_module.py:2052`; `:3578` ↔ `test_capture_module.py:843` | gleiche Namen in zwei Dateien; Bankdaten-Test überlappt (Schema-Felder doppelt geprüft, FE-Teil nur in mirrors). | umbenennen bzw. zusammenführen. | niedrig | `uniq -d` über `def test_` |
| T-08 | 7 | `backend/tests/` | **Keine `conftest.py`, kein pytest-Config.** `_db()` 12× kopiert (z. B. `test_capture_module.py:29`, `test_voucher_module.py:37`, `test_flow_graph.py:135` …), jede ruft `create_all` + `main._ensure_columns()`. Ohne DB: 208 skipped **und** 37 failed + 43 errors (`test_communication` 20E, `test_contact` 14E, `test_mailbox` 9E+1F, `test_article_lifecycle` 13F, `test_user_record` 11F, `test_material_place` 9F, `test_mail_layout` 3F) – alle `OperationalError: Connection refused`. | Eine `conftest.py` mit Session-Fixture; einheitlich «skip mit Grund» lokal, **Fehler** in CI (`INEXXIO_REQUIRE_DB=1`). | mittel | Lauf ohne PostgreSQL (lokal down) |
| T-09 | 7 | `test_frontend_mirrors.py` | Name passt nicht: echte Spiegel sind 5 Tests (`:187, 419, 1540, 5181, 5225`), der Rest sind Quelltext-Wächter über ~45 Dateien (Top: `beleg-work.tsx` 46, `order-detail.tsx` 36, `process-diagram.tsx` 34, `process.py` 27, `process-designer.tsx` 24). Abschnitte teils fachlich, teils chronologisch («Testrunde 7.8.2026 nachmittags», «Testnotizen #960–#974»). | Aufteilen (Vorschlag unten). | niedrig (reine Verschiebung, Hilfen in `tests/_source.py`) | AST-Auswertung je Test nach gelesenen Dateien |
| T-10 | 7 | Laufzeit | `test_frontend_mirrors.py`: 322 passed in **2,83 s** (langsamste 0,98 s). Gesamtsuite ohne DB: 28,6 s (427 passed). DB-Teil **nicht gemessen** – PostgreSQL ist in dieser Umgebung aus (`service postgresql status` = down), laut Auftrag nicht gestartet. | Laufzeit ist kein Grund zum Aufteilen; Grund ist Auffindbarkeit. | – | `pytest --durations` |
| T-11 | 5 | `test_scenarios.py` + `matrix.py:1032` | 77 Fälle; Skips «impossible»/«open_finding» sind beabsichtigt (Wächter meldet, wenn der Befund verschwindet). | behalten; nur `TEST_REPORT`-Zahl ist veraltet (D-28). | – | `len(CASES)` |
| T-12 | 8 | `frontend/scripts/*.test.mjs` | 2 Dateien, ~20 Tests (`when.test.mjs` 14, `login-target.test.mjs`), laufen in CI über `npm test`. CI-Kommentar `deploy-dev.yml:59–61` nennt nur die Datums-Ausgabe. | Kommentar korrigieren. Kandidat für die Verlagerung von FE-Grep-Wächtern (T-04). | niedrig | `package.json:16`, Read |

### CI (`.github/workflows/`)

| ID | Achse | Datei:Zeile | Befund | Vorschlag | Risiko | wie geprüft |
|---|---|---|---|---|---|---|
| T-13 | 8 | `deploy-dev.yml:22–117` | **Geprüft:** `npm ci`, `type-check`, `lint`, `npm test` (FE); `alembic upgrade head` von null; `pytest tests/ -v`; Typen/Status-Katalog aktuell (`git diff --exit-code`). Website-Job: `npm test`, `astro check`, `export-contact --check`, Build mit `check-site`. | – | – | Read |
| T-14 | 8 | `deploy-dev.yml:98–102` | pytest ohne `-rs`/Fehler bei Skip: fällt die DB-Verbindung aus, gehen ~210 Prüfungen still auf «skipped», der Job bleibt grün (Kommentar Z. 90–94 benennt genau dieses Risiko). | `-rs` + Pflicht-DB-Flag (T-08), oder `--strict` über Zählung der Skips. | mittel | Read; lokaler Lauf zeigt 208 Skips |
| T-15 | 8 | `deploy-dev.yml:291–308, 243` | **Frontend-Build kein Quality-Gate**: `next build` läuft erst in `deploy-frontend`, das `needs: deploy-backend` hat → ein Build-Fehler zeigt sich, nachdem das Backend schon ausgerollt ist (Teil-Deploy). | `npm run build` (bzw. `next build` mit Dummy-Env) in `quality`. | mittel | `needs:` Z. 158/243 |
| T-16 | 8 | `deploy-dev.yml:289` | Dev-Deploy `npm install` statt `npm ci` (Quality nutzt `npm ci`, Prod `npm ci`) – nicht reproduzierbar, Lockfile-Drift möglich. | `npm ci`. | niedrig | Read |
| T-17 | 8 | `deploy-prod.yml:1–31` | Prod (push `main`) hat **keine** Prüfung, nur `approve`. Sicher nur, solange `main` ausschliesslich aus grünem `develop` kommt. | Quality-Job wiederverwenden (`workflow_call`) oder Branch-Schutz dokumentieren. | mittel | Read |
| T-18 | 8 | CI gesamt | Fehlt: Python-Linter (`backend/.ruff_cache` existiert lokal, keine Config, nicht in CI; Ersatz nur `test_no_undefined_names`); `scripts/deadcode.py` nicht in CI; kein Abgleich Frontend-Routen ↔ Backend-Routen – Messung: `lib/api.ts:599 deleteStep` ruft `DELETE /api/v1/erp/{owner}/{id}/steps/{id}`, den es nicht gibt (0 Aufrufer). | ruff (nur F-Regeln) in CI; Routen-Abgleich als kleiner Test (Router-Regex ↔ `api.ts`), oder FE-Calls aus `api.ts` gegen `openapi.json` prüfen. | niedrig–mittel | Skript-Abgleich: 133 FE-Pfadreferenzen, 1 echter Fehltreffer |
| T-19 | 8 | Doppelungen | Website wird in dev zweimal gebaut (Quality-Job + Deploy-Job) – bewusst (anderes Env), kein Fehler. Typen werden nur in CI geprüft, gut. Keine echten Doppelprüfungen gefunden. | – | – | Read |

---

## Gliederungsvorschlag

### Neue `CLAUDE.md` (Ziel 300–400 Zeilen)

1. **Lesereihenfolge** (10 Z.): CLAUDE.md → PROCESS_CORE.md (Prozess) → SYSTEM_LOGIC.md (Regeln als
   Sätze) → docs/attic.md (was weg ist) → docs/history/ (warum es so wurde).
2. **Was ist Inexxio / Architektur / Monorepo** (bestehende Z. 5226–5291, gekürzt).
3. **Datenmodell** (60 Z.): Artikel → Instanz → Einzelinstanz (Einzelinstanz-Regel), Auftrag,
   Ereignis-Log append-only, Exklusivität (partieller Unique-Index), Ort (`place_object_id`/`place_unit_id`),
   Statuskatalog (`domain/statuses.py`, generiert nach FE), Nummernkreis, Artikel-Lebenszyklus
   (`replaced_by_id`), Firma/Person/Adressbuch (zwei Konten, UID-/Namensschlüssel), Nachricht.
4. **Module** (60 Z., je 6–10 Z.): Datenerfassung (Scan = Instanz, Stichprobe = eine Zahl, Halt =
   Auskunft) · Aussondern (Parameter, terminal = Ausgang) · Verbrauch (Eintritt am Modul, Stückliste =
   Ableitung) · Bewegen (Ort = Zeiger, Ziel optional) · Zahlung/`beleg` (Stufen offer→agreed→billed,
   `VERBS` als eine Deklaration, Beleg = Rechnung, Korrektur = eigener Beleg, Währung/Steuer).
   Je Modul: Datei, Wächter-Datei, PROCESS_CORE-§.
5. **Regeln/Prinzipien** (60 Z.): ERP ist Master · Eine Sache eine Stelle · Zwei Formen einer Regel
   (`*_problem` ↔ Tor) · `can` ist Auskunft und Tor · Ableitung statt Spalte · Nichtverfügbarkeit ist
   kein Zustand (`StepNeed`/`DataGap`) · Abweichung = gewöhnlicher Auftrag · Das Prozessbild ist ein
   Graph aus dem Log · Kein Löschen, Gegenbuchung · busy sperrt Handlungen, nie Geometrie.
6. **Konventionen** (bestehende Z. 5411–5424 + Design-System-Kurzfassung 5342–5367).
7. **Schema & Netze** (30 Z.): Migration ist die Wahrheit; dev fährt kein `alembic upgrade`; die
   sechs Netze in `main.py` (`_COLUMN_`, `_NUMERIC_`, `_NULLABLE_`, `_DROP_COLUMN_`, `_INDEX_`,
   `_RAW_INDEX_SAFETY_NET`) und die Daten-Reparaturen (`terminal_guard_sql`, `invoice_backfill_sql`,
   `magnitude_sql`, `people.repair_sql`, `address_book.*_sql`, `communication.*_repair_sql`,
   `sites.backfill_keys`) – jede Datenänderung braucht Migration **und** Netz; Zwei-Deploy-Regel für
   Drops (Liste in backlog.md); neue Tabelle mit vollem Spaltensatz.
8. **Tests & CI** (20 Z.): was die CI prüft (T-13), lokal wie CI testen (Schema aus Migrationen),
   Wächter-Regel «gegen Bug-Form gegenprüfen».
9. **Deployment / Lokale Entwicklung / Phasenplan** (bestehend).
10. **Pflichtregeln für Claude** (bestehend 5462–5489) + neu: «Rundenberichte nicht in CLAUDE.md,
    sondern als `docs/history/<datum>-<thema>.md`; CLAUDE.md beschreibt nur den Stand».
11. **Status** (40 Z.): Was heute steht (korrigiert: D-07…D-10), Nicht vorhanden, Offen.

**Nach `docs/history/` wandert:**
- `CLAUDE.md:1–5225` unverändert als `2026-08-bis-10-claude-chronik.md` (eine Datei, oder geteilt nach Thema:
  `…-prozess.md`, `…-handel-und-deal.md` (Z. 1046–3340), `…-beleg.md` (3341–4890), `…-crm.md` (4891–5222))
- `backend/CLAUDE.md:209–932, 966–999, 1014–1495` als `…-backend-chronik.md`
- `frontend/CLAUDE.md:110–1129` (Rundenteile), also alles ausser Technologie, Struktur, Design-System, Typen und Konventionen
- `PROCESS_CORE.md:1797–2774` (§9.12–§9.14c, an `2026-09-zahlungsmodul-vorgaenger.md` anhängen)
- `TEST_REPORT.md`, `FINDINGS.md` (offene 🟡 vorher nach backlog), `ANALYSE_RETOURE_20260917.md`
- `docs/arbeitsauftrag-beleg.md`, `docs/arbeitsauftrag-beleg-2.md`, `docs/beleg-pflichtangaben.md`,
  `docs/konzept-eine-rechnung-je-modul.md`, `docs/neuaufbau-zahlungsmodul.md`, `docs/cleanup-2026-08.md`;
  `docs/konzept-beleg-shop-besitz.md` je nach Entscheidung (offenes Konzept oder erledigt)

**Bleibt** (aktualisiert): `PROCESS_CORE.md`, `SYSTEM_LOGIC.md`, `docs/attic.md`, `docs/backlog.md`,
`docs/feedback.md`, `docs/gmail-setup.md`, `docs/stripe-setup.md`, `docs/passkeys.md`, `docs/adr/*`
(Kopfstatus), `docs/design-system/*`, `docs/Lastenheft_v1.0.md` (Kopfstatus).

### Neue `backend/CLAUDE.md` (Ziel ~200 Zeilen)

Technologie · Pflichtregeln · Starten · Alembic · Struktur (vollständiger `domain/`-Baum, D-20) ·
OpenAPI/Status-Generierung (bestehend 61–92, gut) · **API-Endpunkte** (Tabelle aus dem Code,
siehe unten; Spalten Methode/Pfad/Auth/Datei/1-Satz-Zweck; idealerweise generiert) · Befehle statt
Feld-Updates (`confirm`, `voucher`) · Unternehmen/`sites` (bestehend 170–186) · Schema-Netze
(bestehend 933–954) · Konventionen · Env · Tote Stellen.

### Neue `frontend/CLAUDE.md` (Ziel ~200 Zeilen)

Technologie · Website-/Shell-Beziehung (bestehend 8–34) · Starten · Struktur (inkl. `abmelden`,
`components/erp/*` mit 1-Zeilen-Rolle je Datei) · Design System · Typen/Generierung · API-Client
(Methoden prototypgebunden, #927) · **Bauteile** (`module-ui`, `fields`, `object-select`, Scan) als
Tabelle aus den **Exporten** abgeleitet · Datum (`lib/when.ts`) · Konventionen.

---

## Tatsächlich existierende API-Endpunkte (86)

Quelle: `@<router>.<methode>("…")` in `backend/app/routers/*.py` mit Präfix aus `APIRouter(prefix=…)`,
registriert in `backend/app/main.py:1092–1107`. Auth heuristisch aus der Signatur
(`require_admin` = admin, `require_employee` = staff, `get_current_user` = user, – = ohne);
einzelne Routen prüfen zusätzlich im Rumpf (z. B. «eigene Firma: nur Admin»).

| Methode | Pfad | Auth | Datei:Zeile |
|---|---|---|---|
| GET | `/health` | – | routers/health.py:10 |
| GET | `/api/v1/auth/me` | user | routers/auth.py:15 |
| PATCH | `/api/v1/auth/me` | user | routers/auth.py:20 |
| POST | `/api/v1/auth/me/addresses` | user | routers/auth.py:36 |
| PATCH | `/api/v1/auth/me/addresses/{address_id}` | user | routers/auth.py:48 |
| DELETE | `/api/v1/auth/me/addresses/{address_id}` | user | routers/auth.py:62 |
| POST | `/api/v1/auth/terms-accept` | user | routers/auth.py:74 |
| POST | `/api/v1/auth/passkeys/register/options` | user | routers/passkey.py:27 |
| POST | `/api/v1/auth/passkeys/register/verify` | user | routers/passkey.py:37 |
| GET | `/api/v1/auth/passkeys` | user | routers/passkey.py:50 |
| DELETE | `/api/v1/auth/passkeys/{passkey_id}` | user | routers/passkey.py:59 |
| POST | `/api/v1/auth/passkeys/login/options` | – | routers/passkey.py:72 |
| POST | `/api/v1/auth/passkeys/login/verify` | – | routers/passkey.py:78 |
| POST | `/api/v1/contact` | – | routers/contact.py:306 |
| GET | `/api/v1/public/contact` | – | routers/website.py:37 |
| GET | `/api/v1/admin/settings` | admin | routers/admin.py:64 |
| PATCH | `/api/v1/admin/settings` | admin | routers/admin.py:74 |
| GET | `/api/v1/admin/settings/public` | – | routers/admin.py:92 |
| GET | `/api/v1/admin/companies` | staff | routers/admin.py:128 |
| GET | `/api/v1/admin/companies/{object_id}` | staff | routers/admin.py:138 |
| POST | `/api/v1/admin/companies` | staff | routers/admin.py:148 |
| PATCH | `/api/v1/admin/companies/{object_id}` | staff | routers/admin.py:169 |
| POST | `/api/v1/admin/companies/{object_id}/operator` | admin | routers/admin.py:188 |
| DELETE | `/api/v1/admin/companies/{object_id}` | staff | routers/admin.py:203 |
| POST | `/api/v1/admin/companies/{object_id}/reopen` | staff | routers/admin.py:218 |
| GET | `/api/v1/admin/territories` | admin | routers/admin.py:263 |
| PUT | `/api/v1/admin/territories/{area}` | admin | routers/admin.py:274 |
| GET | `/api/v1/admin/users` | staff | routers/admin.py:288 |
| GET | `/api/v1/admin/audit-log` | admin | routers/admin.py:315 |
| GET | `/api/v1/erp/objects/{object_id}` | staff | routers/erp.py:49 |
| GET | `/api/v1/erp/records` | staff | routers/erp.py:62 |
| POST | `/api/v1/erp/records` | staff | routers/erp.py:77 |
| GET | `/api/v1/erp/companies` | staff | routers/erp.py:89 |
| GET | `/api/v1/erp/records/{object_id}` | staff | routers/erp.py:106 |
| PATCH | `/api/v1/erp/records/{object_id}` | admin | routers/erp.py:118 |
| POST | `/api/v1/erp/records/{object_id}/addresses` | admin | routers/erp.py:154 |
| PATCH | `/api/v1/erp/records/{object_id}/addresses/{address_id}` | admin | routers/erp.py:166 |
| DELETE | `/api/v1/erp/records/{object_id}/addresses/{address_id}` | admin | routers/erp.py:181 |
| GET | `/api/v1/erp/articles/name-suggestions` | staff | routers/articles.py:103 |
| GET | `/api/v1/erp/articles` | staff | routers/articles.py:113 |
| POST | `/api/v1/erp/articles/validate` | staff | routers/articles.py:128 |
| POST | `/api/v1/erp/articles` | staff | routers/articles.py:143 |
| GET | `/api/v1/erp/articles/{object_id}` | staff | routers/articles.py:169 |
| PATCH | `/api/v1/erp/articles/{object_id}` | staff | routers/articles.py:178 |
| GET | `/api/v1/erp/articles/{object_id}/stock` | staff | routers/articles.py:204 |
| GET | `/api/v1/erp/articles/{object_id}/process` | staff | routers/articles.py:268 |
| GET | `/api/v1/erp/instances` | staff | routers/instances.py:85 |
| GET | `/api/v1/erp/instances/{object_id}` | staff | routers/instances.py:130 |
| GET | `/api/v1/erp/instances/{object_id}/units` | staff | routers/instances.py:139 |
| GET | `/api/v1/erp/instances/{object_id}/units/{suffix}/genealogy` | staff | routers/instances.py:172 |
| GET | `/api/v1/erp/places` | staff | routers/places.py:25 |
| GET | `/api/v1/erp/places/{object_id}` | staff | routers/places.py:47 |
| GET | `/api/v1/erp/orders` | user | routers/orders.py:372 |
| GET | `/api/v1/erp/orders/article-options` | staff | routers/orders.py:406 |
| GET | `/api/v1/erp/orders/voucher-parties` | staff | routers/orders.py:450 |
| GET | `/api/v1/erp/orders/module-catalog` | staff | routers/orders.py:473 |
| GET | `/api/v1/erp/orders/unit-options` | staff | routers/orders.py:499 |
| POST | `/api/v1/erp/orders/validate` | staff | routers/orders.py:634 |
| POST | `/api/v1/erp/orders` | staff | routers/orders.py:716 |
| GET | `/api/v1/erp/orders/{object_id}` | user | routers/orders.py:731 |
| GET | `/api/v1/erp/orders/{object_id}/units` | staff | routers/orders.py:741 |
| POST | `/api/v1/erp/orders/{object_id}/steps/{step_id}/confirm` | staff | routers/orders.py:781 |
| GET | `/api/v1/erp/orders/{object_id}/steps/{step_id}/hold` | staff | routers/orders.py:809 |
| GET | `/api/v1/erp/orders/{object_id}/steps/{step_id}/record` | staff | routers/orders.py:842 |
| POST | `/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher` | user | routers/orders.py:916 |
| POST | `/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher/payment` | user | routers/orders.py:949 |
| POST | `/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher/refund` | staff | routers/orders.py:976 |
| GET | `/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher/transfer` | user | routers/orders.py:1001 |
| GET | `/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher/correctable` | staff | routers/orders.py:1028 |
| POST | `/api/v1/erp/attachments` | staff | routers/attachments.py:24 |
| GET | `/api/v1/attachments/{token}` | – | routers/attachments.py:36 |
| POST | `/api/v1/payments/webhook` | – (Signatur) | routers/payments.py:22 |
| GET | `/api/v1/erp/messages/channels` | staff | routers/communication.py:25 |
| GET | `/api/v1/erp/messages/mailboxes` | staff | routers/communication.py:31 |
| POST | `/api/v1/erp/messages/mailboxes/{channel}/connect` | staff | routers/communication.py:39 |
| DELETE | `/api/v1/erp/messages/mailboxes/{channel}` | staff | routers/communication.py:46 |
| POST | `/api/v1/erp/messages/sync` | staff | routers/communication.py:52 |
| GET | `/api/v1/mail/callback` | – (signierter state) | routers/communication.py:59 |
| GET | `/api/v1/erp/messages/open` | staff | routers/communication.py:69 |
| GET | `/api/v1/erp/messages` | staff | routers/communication.py:75 |
| POST | `/api/v1/erp/messages` | staff | routers/communication.py:88 |
| GET | `/api/v1/feedback` | user | routers/feedback.py:25 |
| POST | `/api/v1/feedback` | user | routers/feedback.py:37 |
| DELETE | `/api/v1/feedback` | user | routers/feedback.py:50 |
| DELETE | `/api/v1/feedback/{note_id}` | user | routers/feedback.py:66 |
| PATCH | `/api/v1/feedback/{note_id}` | user | routers/feedback.py:81 |

Abgleich mit dem Frontend: 133 Pfadreferenzen in `frontend/src`. Die Fehltreffer sind bis auf einen
Artefakte von Template-Strings mit Querystring. Der echte Fehltreffer ist `lib/api.ts:599 deleteStep`,
denn den Endpunkt dahinter gibt es nicht.

---

## Vorschlag Paketierung

Jedes Paket ist ein eigener Commit/PR und für sich rückrollbar.

| Paket | Inhalt | IDs | Aufwand | Risiko |
|---|---|---|---|---|
| **P1 – Betriebsdoku sofort richtig** | gmail-setup (Scopes, keine persönlichen Postfächer), stripe-setup (voucher-Metadaten), Rollback-Tags klären/setzen oder Doku auf Commit-Hashes, history/README-Index | D-32, D-33, D-14, D-35 | klein | niedrig |
| **P2 – Archivieren** | erledigte Dokus nach `docs/history/` (git mv), Verweise in Code-Kommentaren/Tests nachziehen (`neuaufbau-zahlungsmodul`: 8+3 Stellen, `cleanup-2026-08`: 3, `FINDINGS.md 🟡-1` in `matrix.py:1032`), offene 🟡 nach backlog | D-28…D-31, D-29 | klein | niedrig–mittel |
| **P3 – CLAUDE.md neu** | Chronik 1:1 nach history; neue CLAUDE.md nach Gliederung, «Was heute steht» korrigiert (issue, Rechnung am Beleg, ausser Betrieb, CRM, Autosave, MWST, Spiegel-Liste); Lastenheft-Regel Z. 113 umformulieren | D-01…D-15, D-38 | mittel | niedrig |
| **P4 – backend/frontend CLAUDE.md neu** | API-Tabelle aus Code (optional `scripts/dump_routes.py` + CI-Diff), Struktur vervollständigen, Rundenprosa nach history; FE-Bauteil-Tabelle aus Exporten | D-16…D-24 | mittel | niedrig |
| **P5 – PROCESS_CORE / SYSTEM_LOGIC / ADR / Skills** | §9.12–§9.14c nach history, §9.15q `issue` korrigieren, SYSTEM_LOGIC 533/537, ADR-Kopfstatus 001/005/006, beide Skills | D-25…D-27, D-36, D-37, D-39, D-40 | mittel | niedrig |
| **P6 – Test-Hygiene** | `conftest.py` mit einer DB-Fixture und Pflicht-DB-Flag; T-01/T-02 löschen; Grabsteine zu einem datengetriebenen Test; Duplikate T-06/T-07 bereinigen | T-01…T-03, T-06…T-08 | mittel | mittel (Schutz darf nicht verloren gehen: vor/nach Testzahl und Bug-Form-Gegenprobe vergleichen) |
| **P7 – `test_frontend_mirrors.py` aufteilen** | reine Verschiebung in `tests/source/`: `test_source_process.py` (Prozess, Bild, Designer, Abweichung, ~112 Tests), `test_source_beleg.py` (~44), `test_source_ui.py` (Design, fields, module-ui, Datum, ~32), `test_source_capture.py` (~21), `test_source_stock.py` (~20), `test_source_scan_reference.py` (~16), `test_source_people.py` (Person/Firma/Kommunikation), `test_api_mirrors.py` (die 5 echten Spiegel); Hilfen `_read/_code/_at/_body/_component` nach `tests/source/_source.py`; Docstrings kürzen | T-04, T-05, T-09 | mittel | niedrig (Testzahl 322 vorher = nachher prüfen; Zuordnung oben ist eine Näherung über die gelesenen Dateien) |
| **P8 – CI** | pytest `-rs` + Pflicht-DB; FE-`next build` ins Quality-Gate; `npm ci` im Dev-Deploy; ruff (nur F-Regeln); Routen-Abgleich FE↔BE; Prod-Gate per `workflow_call`; CI-Kommentar FE-Tests | T-12, T-14…T-18 | klein–mittel | mittel (ruff/Routen-Abgleich können initial rot sein: `deleteStep`) |

Reihenfolge: P1 → P2 → P3/P4 → P5 → P6 → P7 → P8. P1 hat Betriebswirkung und ist unabhängig.
P7 erst nach P6, damit die Fixture nur einmal umzieht.

### Nicht gemessen / Grenzen
- Die DB-gebundenen Tests liefen nicht, weil PostgreSQL hier aus ist. Ihre Laufzeit und ihr Ergebnis gegen ein frisches Schema sind darum offen.
- `git ls-remote` lief über den Session-Proxy. Heads sind sichtbar, Tags 0. Dass es auf GitHub wirklich keine Tags gibt, sollte jemand mit direktem Zugriff bestätigen.
- `website/*.md` (WEBSITE_PLAN, Reports) und `SYSTEM_INTENT.md` habe ich inhaltlich nicht geprüft.
- Die Zuordnung der 322 Mirror-Tests zu Bereichen ist eine Heuristik über die gelesenen Dateinamen. 70 Tests lassen sich so nicht eindeutig zuordnen.
