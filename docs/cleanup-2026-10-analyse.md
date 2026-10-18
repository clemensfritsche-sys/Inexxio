# Cleanup Oktober 2026 – Gesamtbericht

Stand `develop` @ `fbd70fc`, 18.10.2026. Nur gelesen, nichts geändert.
Detailberichte mit jeder Fundstelle: `docs/cleanup-2026-10/` (backend · frontend · website ·
docs-tests). IDs hier verweisen dorthin (B = Backend, F = Frontend, W = Website, D = Doku,
T = Tests/CI).

Die schwersten Befunde habe ich selbst am Code nachgeprüft (markiert mit ✔).

**Entscheide:** E1–E10 wie empfohlen, E7 belassen (18.10.2026).
**Rollback-Punkt:** Commit `eefb0dc` – ein Tag liess sich aus der Cloud-Umgebung nicht
pushen (Proxy). Wer ihn will: `git tag rollback/pre-cleanup-2026-10 eefb0dc && git push origin rollback/pre-cleanup-2026-10`.

**Stand:** Paket 1 ✔

---

## 1. Die 10 wichtigsten Befunde

| # | Befund | Wirkung heute | IDs |
|---|---|---|---|
| 1 ✔ | **Mails können doppelt hinausgehen.** Fällige Mails werden ohne Zeilensperre geholt (zwei offene ERP-Tabs = zwei Versender). Und ein Netzfehler *nach* dem Versand rollt den ganzen Abgleich zurück → alle schon versendeten Mails gelten als «noch nicht versendet» und gehen beim nächsten Lauf erneut hinaus. | Kunde bekommt dieselbe Mail 2×. Nicht zurückholbar. | B-30, B-31, B-32 |
| 2 ✔ | **Der Start kann Kerndaten löschen.** Ein Formwächter aus dem Basis-Neuaufbau macht bei einer «unerwarteten Pflichtspalte» `DROP TABLE … CASCADE` auf `orders`, `process_events` (der append-only Log!), `instance_units` – bei jedem Start. | Eine unvorsichtige Migration = Prozessdaten weg. | B-33, B-34 |
| 3 ✔ | **Prod-Rewrite zeigt aufs Dev-Backend.** `firebase.json` leitet `/api/**` an `inexxio-backend-dev`, der Prod-Deploy übernimmt das unverändert. | Kontaktformular und Kontaktdaten in Prod kaputt oder im falschen System. | W-30, T-17 |
| 4 ✔ | **Eine Nachricht kann still verloren gehen.** Wer die Ansicht während «Rückgängig» verlässt, schickt sie im Hintergrund; scheitert das, wird der Fehler verschluckt. | Nachricht weg, ohne Spur. | F-60 |
| 5 ✔ | **Plausible lädt nie.** Der öffentliche Einstellungs-Endpunkt liefert `plausible_domain` nicht, das Frontend liest genau das. Dazu erfundene Vorgaben («Inexxio AG», info@inexxio.com). | Keine Statistik, ohne dass es jemand merkt. | B-35, B-44, W-06 |
| 6 | **Optimistic Locking ist tot.** Gerufen nur am Artikel-PATCH, und den ruft das Frontend gar nicht mehr. CLAUDE.md führt es unter «Sicherheit – gebaut». | Falsche Sicherheit in der Doku. | B-36, F-01, F-03 |
| 7 | **Viel toter Code.** 3 Endpunkte ohne Aufrufer, 5 API-Methoden (eine ruft einen Endpunkt, den es nicht gibt), 1 ganze Datei, 11 CSS-Klassen, 13 Typen, tote Konstanten, Website-Schalter ohne Wirkung (`features.team`), Bilder, die mit ausgeliefert werden. | Rauschen, falsche Fährten. | B-01…15, F-01…19, W-01…17 |
| 8 | **Die Doku beschreibt ein anderes System.** CLAUDE.md ist zu 93 % Chronik; selbst der Ist-Teil ist falsch (`issue`, «Rechnungen als Zeilen», CRM fehlt). Die API-Tabelle in `backend/CLAUDE.md` führt 6 gelöschte und vermisst 15 echte Endpunkte. `gmail-setup.md` nennt falsche OAuth-Scopes, `stripe-setup.md` falsche Metadaten. Die genannten **Rollback-Tags gibt es nicht**. | Jede Sitzung liest 459 kB, teils falsch. | D-01…D-42, W-40…43 |
| 9 | **Doppelungen gegen «eine Sache, eine Stelle».** Staff-Rollen 5×, zwei `useAutosave` (3000 ↔ 1500 ms), zwei Personensuchen mit verschiedenen Ergebnissen, UID auf demselben Beleg einmal formatiert, einmal roh, ERP-Pfadliste 4×, Card/SubBlock/Label/Chip mehrfach. | Gleiche Frage, verschiedene Antworten. | B-40…46, F-40…53, W-20…23 |
| 10 | **Tests/CI schützen weniger, als es scheint.** Ohne DB werden 80 Tests rot statt übersprungen – und in der CI würde ein DB-Ausfall still «grün» (Skips). Frontend-Build läuft erst *nach* dem Backend-Deploy. `test_frontend_mirrors.py` = 10'499 Zeilen Quelltext-Grep. Kein Linter, kein Routenabgleich. | Fehler fallen spät oder gar nicht auf. | T-01…T-18 |

Dazu: **Alt-Palette lebt als Hex** im Konto und über `account/field.tsx` auch im ERP (F-20) –
«0 Vorkommen» gilt nur für Klassennamen.

---

## 2. Was ich von dir entscheiden lassen muss

Je Frage meine Empfehlung zuerst.

| # | Frage | Empfehlung |
|---|---|---|
| E1 | **Wird Prod heute genutzt?** (bestimmt die Dringlichkeit von #3) | Rewrite trotzdem jetzt korrigieren – kostet eine Zeile im Prod-Workflow. |
| E2 | **AGB-Akzeptanz** (`POST /auth/terms-accept`, nie verdrahtet) | Löschen. Kommt mit dem Shop zurück, wenn es wieder etwas zu akzeptieren gibt. |
| E3 | **Audit-Log-Endpunkt** (`GET /admin/audit-log`, kein Aufrufer) | Löschen. Das Log selbst bleibt in der DB. |
| E4 | **Optimistic Locking** | Löschen (samt Artikel-PATCH ohne Aufrufer) und Doku korrigieren. Ein Artikel ist nach der Freigabe ohnehin fest. |
| E5 | **Plausible** – soll Statistik laufen? | Wenn du sie nicht anschaust: ERP-Teil und Website-Tracking-Haken entfernen. Sonst: Endpunkt reparieren (1 Feld). |
| E6 | **«Erster Benutzer wird Admin»** auf leerer DB (B-39) | Streichen; nur `initial_admin_email` wird Admin. |
| E7 | **Artikel-Felder ohne Leser**: `safety_stock`, `min_order_qty`, `supplier_article_number` (Platzhalter verspricht «automatisch nachbestellt») und am Benutzer `language`, `notification_*` | Platzhalter-Satz sofort streichen. Felder: behalten, wenn Disposition kommt – sonst raus. |
| E8 | **Website**: Team-Sektion bis zum Fototag zeigen? `/shop` in robots.txt? Wort «Einsatzgebiet»? unbenutzte Beispielbilder? | Team bleibt sichtbar (Schalter löschen) · `/shop` raus · «Werkstatt und Einsatz» · Bilder löschen. |
| E9 | **Rollback-Tags** | Vor dem ersten Paket einen Tag `rollback/pre-cleanup-2026-10` setzen und Doku auf echte Tags/Hashes stellen. |
| E10 | **DB-Drops** (rund 40 Spalten und ~14 Tabellen entfernter Bereiche) | Erst nach einer Sicherung der **produktiven** DB, die du anstösst. Bis dahin kosten sie nichts. |

---

## 3. Pakete – Reihenfolge nach Nutzen/Risiko

Jedes Paket: eigener Commit, Tests grün, einzeln deployt. «Verh.» = Verhaltensänderung,
«DB» = Migration/Datenänderung.

| Paket | Inhalt | IDs | Verh. | DB | Aufwand |
|---|---|---|---|---|---|
| **1 Mail härten** | Zeilensperre beim Versand, Ergebnis je Mail sofort festschreiben, Metadaten-Abruf geschützt, Fehlversand loggen; Nachricht beim Verlassen nicht verlieren | B-30–32, F-60 | ja (nur Fehlerfall) | nein | klein |
| **2 Start entschärfen** | DROP-Zweig → nur Warnung; jede Daten-Reparatur eigener `try` mit Log; Admin-Bootstrap (E6) | B-33, B-34, B-39 | ja (Fehlerfall) | nein | klein |
| **3 Hosting & Formular** | Prod-Rewrite, Header-Block auf echte Pfade, mailto-Ausweg mit ERP-Adresse, Formular-Timeout, `postcss` deklarieren, `OFFENE_PUNKTE.md` in CI prüfen | W-30–38 | ja | nein | klein |
| **4 Öffentliche Einstellungen** | je nach E5 reparieren oder entfernen; keine erfundenen Vorgaben | B-35, B-44, W-06 | ja | nein | klein |
| **5 Toter Code** | alles aus §1 #7, Entscheide E2–E4/E7–E8 eingerechnet; `deadcode.py` nachschärfen | B-01–15, B-21, F-01–19, W-02–17, T-01, T-02 | nein | nein | mittel |
| **6 Doku neu** | CLAUDE.md auf ~350 Zeilen Ist-Stand (Gliederung in docs-tests.md), Chronik 1:1 nach `docs/history/`; backend/frontend-CLAUDE.md, API-Tabelle aus dem Code; gmail/stripe-Setup; PROCESS_CORE §9.12–14 nach history; erledigte Konzepte archivieren; Website-Berichte archivieren; Regel «Rundenbericht nach history, nicht in CLAUDE.md» | D-01–42, W-40–42 | nein | nein | mittel |
| **7 Kommentare** | 167 Grabsteine («Hier stand …») und falsche Verweise (`deal`, `purchase`, `Module.buys` …) raus; Prosa auf «was + warum heute» | B-29, B-49, B-54, B-60–66, F-21–26, F-29, F-35–37, F-70–79, W-43 | nein | nein | mittel |
| **8 Namen** | `DEAL_*` → `VOUCHER_*`, `voucher-parties` → `GET /erp/people` (Personensuche, alter Pfad 1 Deploy als Alias), `iban_encrypted` → Attribut `iban` (ohne Migration), `status-flow` → `status-tone`, gemeinsame Bausteine aus `components/account/` heraus | B-47, B-48, F-30–34, W-27, W-28 | nein | nein | klein |
| **9 Eine Regel, eine Stelle** | `STAFF_ROLES` 1×, eine Personensuche, UID 1× formatiert, ein Autosave-Hook (3 s), Card/SubBlock/Label/Chip aus `fields`, Markenrot 1 Schreibweise, Personenname = Backend-Regel, ERP-Pfadliste 1×, Formular-Regex aus dem Vokabular | B-40–46, F-40–53, F-61, W-20–23, W-45 | leicht | nein | mittel |
| **10 Alt-Palette** | Hex-Farben im Konto/ERP auf Tokens, AccountShell ein Kopf statt zwei, Admin sieht Anstellung | F-20, F-50, F-51, F-57, F-65 | sichtbar | nein | mittel |
| **11 Tests & CI** | `conftest.py` mit einer DB-Fixture (CI: Pflicht-DB, `-rs`), Grabstein-Tests zusammenfassen, Duplikate weg, Frontend-Build ins Quality-Gate, `npm ci`, ruff (nur F-Regeln), Routenabgleich FE↔BE, Prod-Gate; `test_frontend_mirrors.py` nach Bereich aufteilen | T-03–18 | nein | nein | mittel |
| **12 Netze aufräumen (ohne Drop)** | tote Netz-Einträge (`purchases`-Index, 28 längst gedroppte Spalten, selbstbegrenzte Reparaturen); Index/FK `corrects_id` nachziehen. **Vorher prüfe ich**, ob `alembic upgrade head` auf dev wirklich läuft (`start.sh` tut es – die CLAUDE.md-Aussage «dev fährt kein alembic» ist dann falsch, und viele Netze sind doppelt) | B-20–24, B-52, B-70 | nein | ja (nur DDL-Netz) | klein |
| **13 Messen** | Feed-Zähler lädt den ganzen Nachrichtenbestand; Auftragsantwort N+1; `sync_lines` auf GET konfliktfest | B-37, B-38, B-50 | nein | nein | mittel |
| **14 Grosse Dateien** | `beleg-work.tsx` (2805 Z.), `ErpPage` (616 Z.), `embed_data` (297 Z.), `confirm_step` (254 Z.) … aufteilen – nur im Zuge fachlicher Arbeit | B-53, F-54–56 | nein | nein | fortlaufend |
| **F / G Drops** | Spalten (F) und Tabellen (G) entfernter Bereiche, mit den zugehörigen Backfills | B-08, B-09, B-25–28 | – | **ja, unumkehrbar** | nach E10 |

**Vorschlag für den Anfang:** E9 (Tag) → Paket 1 → 2 → 3 → 4. Das sind die vier mit echter
Wirkung, alle klein. Danach 5 → 6 → 7 (aufräumen ohne Verhaltensänderung), dann 8–13.

---

## 4. Grenzen

- DB-gebundene Tests liefen in der Analyse nicht (PostgreSQL war aus). Vor jedem Paket laufen sie.
- Nicht gemessen: Abfragezahl einer Auftragsantwort, Laufzeit des Feed-Zählers, ob Index/FK zu
  `vouchers.corrects_id` auf dev existieren, ob `alembic upgrade head` auf dev durchläuft.
- Tags: über den Session-Proxy 0 sichtbar – mit direktem GitHub-Zugriff bestätigen.
