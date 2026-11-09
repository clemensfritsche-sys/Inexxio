# Gesamtprüfung des ERP (09.11.2026)

Auftrag des Inhabers: das ganze System kritisch prüfen – Architektur, Logik, Vereinheitlichung,
und je Bereich: macht es Sinn, würde man es heute anders bauen, was fehlt. Sechs unabhängige
Prüfer (Gesamtarchitektur · Prozess · Geld/Dokumente/Mail · Zeiterfassung/CRM · KI/MCP/Sicherheit ·
Frontend), rund 66'000 Zeilen gelesen; die schweren Befunde danach selbst im Code bestätigt.
Nichts wurde geändert – das hier ist die Grundlage für die nächsten Runden.

## Urteil

Das Fundament ist gut und für ein 10-Personen-System ungewöhnlich sauber: eine Speicherstelle je
Anfrage, das Log schreibt die Datenbank selbst, Zustände sind abgeleitet statt kopiert, eine
Schreibstelle je Sache (`_pass`, `timekeeping.record`, `VERBS`), Handgriffe gehen durch die echte
Route. **Kein Neubau.** Die Schulden liegen an drei Stellen: (1) Regeln, die über viele Dateien
verstreut sind (Rechte, Fehler, Ereignisse), (2) einige echte Fehler in Recht und Sicherheit,
(3) Lücken, die im echten Betrieb bald fehlen (Mengen in m/kg, Buchhaltungs-Export, Lohn-Export).

## Echte Fehler (klein, zuerst)

| # | Befund | Stelle | Aufwand |
|---|---|---|---|
| F1 | Eine gebuchte Lieferantenrechnung lässt sich nach dem Buchen ersetzen; die alte hängt dann nirgends mehr und ist löschbar (Aufbewahrung 10 Jahre). | `services/fields._original`, `documents.set_field`/`delete_problem` | S |
| F2 | Dienstleistung an Privatkunden im Ausland: fest «Reverse Charge», die Rechnung verlangt eine MWST-Nr., die eine Privatperson nicht hat → nicht fakturierbar. Richtig: «nicht im Inland steuerbar». | `domain/voucher.vat_choices`, `voucher_actions.REQUIRED_FOR` | S |
| F3 | Arztzeugnisse (Nachweis Absenz) gehen beim Nachreichen automatisch zur KI (Gesundheitsdaten, ohne Einwilligung). | `document-draft.tsx` liest jede Datei, auch für `time.proof` | S |
| F4 | Ferien laufen während unbezahltem Urlaub an Wochenenden weiter auf. | `timekeeping.ledger`/`absence_on` | S |
| F5 | Eine Mail kann doppelt hinausgehen (erst senden, dann speichern; keine eigene Message-ID). | `mailbox.send` | S |
| F6 | Beim Neu-Verbinden eines Postfachs gehen Mails aus der Lücke verloren. | `mailbox._store`, Rückfall 2 Tage/200 | S |
| F7 | MCP: Erneuerung (90 Tage) ist nicht einmalig und nicht an den Client gebunden; jede https-Rückkehr-Adresse wird angenommen (Zustimmungs-Phishing); Zugang ohne Umgebung/Empfänger (dev ↔ prod). | `services/mcp.py` | S |
| F8 | Das Gespräch live: die KI hält eine Transaktion bis 240 s in einem Faden; Cloud Run drosselt nach der Antwort – bricht es ab, rollen auch die `ai.call`-Kosten zurück (Deckel zählt sie nicht), der Takt zahlt ein zweites Mal. | `talk.stream`, `ai.py`, Deploy ohne `--no-cpu-throttling` | M |
| F9 | Unser eigenes Rechnungsdatum ist frei wählbar (rückdatieren in eine abgerechnete MWST-Periode). | `voucher_actions._bill` | S |
| F10 | Beträge mit «’» (Schweizer Apostroph) werden abgewiesen; zwei Betrags-Leser, die sich widersprechen. | `domain/voucher.amount` ↔ `reading._amount` | S |

## Vereinheitlichen (Architektur)

1. **Rechte an EINER Stelle.** Routen sind einheitlich (`require_employee/admin`), aber in ~20
   Diensten stehen rund 60 eigene Rollenprüfungen; «Admin oder selbst» steht fünfmal
   (`access`, `talk`, `handgriff`, `recordings`, `timekeeping`), die Sichtbarkeit eines Auftrags
   im Router (`routers/orders._visible`). → `core/policy.py` mit `may(wer, was, woran) → Grund`
   (wie `can` beim Beleg), ein Wächter verbietet `.role ==` ausserhalb. Im Frontend `isAdmin`
   34-mal durchgereicht → vom Server (`can`) statt Rolle. (M)
2. **Ein Fehlermodell.** `HTTPException` steht 52-mal in `domain/`, 288-mal in Diensten; der
   Handgriff liest Fehlertexte zurück und erkennt «gesperrt» am Wortlaut. → eine Ausnahme
   `Rejected(art, satz)` in der Fachschicht, EIN Übersetzer nach HTTP in `main.py`. (M)
3. **Ereignis-Register.** Viele Funktionen leben nur als Ereignisse im Log (Gespräch,
   Handgriff, Wiederholung, Aufnahme, MCP); `log.event` nimmt jeden Namen und jede Nutzlast. →
   `domain/events.py`: jedes Ereignis mit seiner Form, geprüft beim Schreiben. (S–M)
4. **Frontend liest überall über React Query.** ~26 Stellen laden noch von Hand in `useState`
   (Zeiterfassung, Feiertage, Prozess-Editor, Passkeys …) und werden nach einer Änderung nicht
   neu geladen. → `useQuery` + ESLint-Wächter «kein `api.` in `useEffect`». (M)
5. **Aufräumen der grossen Dateien:** `voucher_actions.py` (1'339), `routers/orders.py` (962,
   ein Dienst im Router), `mailbox.py` (938). (M)
6. **Protokollieren mit Schweregrad** statt 28× `print("WARNING")` – sonst kein Alarm. (S)
7. **Inline-Styles** (1'036 im Frontend) schrittweise auf Token-Klassen. (M, laufend)
8. **Ein Dialog-Baustein** statt sechs eigener `role="dialog"`. (S)

## Je Bereich – würde man es anders bauen?

- **Prozess:** Modell richtig (Stück = Zeile, eine Schreibstelle, Abweichung = Auftrag).
  Anders von Anfang an: **Menge als Dezimalzahl für Material** (m, kg, l – heute nur ganze
  Stück, `OrderLine.quantity` ist Integer, `Article.unit` wird nirgends gelesen) und **ein
  Ereignis je Sammel-Durchlauf** (10'000 Schrauben ≈ 40'000 Log-Zeilen in einer Anfrage).
  Dazu: Umlagern und Inventur ohne Auftrag; der Beleg hängt an 6 Stellen fest in der Engine
  (Haken je Modul statt Aufruf).
- **Geld:** Modell richtig (ein Beleg je Modul, Nummern unter Sperre, eingefroren, Gutschrift
  über alles, MWSTG Art. 26). Zu eng: Lieferantenrechnung nur ein Steuersatz und nur mit Ware
  (Miete, Versicherung gehen nicht). «Erledigt» abgeleitet → Listen werden jedes Jahr langsamer.
- **Dokumente:** eine Ablage ist richtig; Lohn-Dokumente wären heute für alle sichtbar.
- **Zeiterfassung:** append-only + Ableitung ist richtig. Es fehlt der **Monatsabschluss** –
  heute rechnet alles ab dem ersten Vertrag neu, und Rückwirkendes (Vertrag, Feiertag,
  Geburtsdatum) ändert bezahlte Monate still. Überzeit (ArG 170 h/Jahr) und Zuschläge fehlen.
- **CRM:** eine E-Mail je Person passt nicht zu info@kunde.ch; der Verlauf einer Firma wandert
  mit der Person, wenn sie die Stelle wechselt; nur der Admin darf Kundendaten ändern; «zu tun»
  wird von Mail-Kontakten mit fehlender Adresse geflutet.
- **KI/MCP:** Handgriff über die echte Route ist die richtige Entscheidung. Risiko:
  Handgriffe aus fremden Mails (Prompt-Injection) laufen im Probelauf mit den Rechten des
  Admins und sind für alle sichtbar; `ausfuehren` entscheidet die KI selbst, ob «ja» gesagt
  wurde; frühere Entscheide gehen als «richte dich danach» in die Anleitung.
- **Sicherheit/Betrieb:** CSP mit `unsafe-eval`, `*.googleapis.com`, `*.a.run.app` schützt kaum;
  kein zweiter Faktor für den Admin; Prod-Backup (PITR) und Rückspiel-Probe noch offen.
- **Frontend:** solide Kernschicht (Anfrage, Fehler nie still, strikte Typen). Ein Bündel von
  2,2 MB für alles; keine Tests, die eine Oberfläche wirklich darstellen (nur Logik-Tests).

## Was fehlt (Rang)

1. Mengen in m/kg/l für Material.
2. Buchhaltungs-Export (Journal, bexio/Abacus) – sonst tippt der Treuhänder ab.
3. Lohn-Export + Monatsabschluss der Zeiterfassung.
4. Lieferantenrechnung ohne Ware, mit mehreren Sätzen.
5. Datenschutz: Löschen/Anonymisieren und Aufbewahrungsfristen (`log.redact` hat keinen Aufrufer).
6. Bankdatei-Import (camt.054; die RF-Referenz ist schon da).
7. Reservierung/Verfügbarkeit, Termine am Auftrag, Bestellvorschlag.
8. Rauchtests der Oberfläche (Playwright, 5–8 Abläufe).
9. Offene-Posten-Liste über alle, PDF als Anhang der Rechnung.

## Bewusst gut – bleibt

Speichern am Ende der Anfrage · `core/outside` · Log mit Handelndem, unveränderlich, versiegelt ·
Migration als einziger Weg mit Wächter in beide Richtungen · Zustände abgeleitet · eine
Schreibstelle je Sache · `can` als Auskunft und Tor · Abweichungen als gewöhnliche Aufträge ·
Stückliste/Genealogie aus dem Log · Firmen-Dubletten unmöglich per Schlüssel · Stripe idempotent ·
Handgriff durch die echte Route · PKCE und einmaliger Code bei MCP.
