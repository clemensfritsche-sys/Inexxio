# «ERP ist Master» – die Prüfung (11.11.2026)

**Anlass.** Im Konto unter «Sicherheit» sah und verwaltete Clemens Fritsche seine Passkeys und
seine «Verbindungen mit Claude» (mit «Trennen»); am ERP-Datensatz derselben Person stand davon nur
eine Zahl («Passkeys: 2 Geräte»). Dazu standen zwei Einträge «Verbunden – Claude», obwohl er einmal
verbunden und später in Claude selbst wieder getrennt hatte. Beides verstösst gegen das Leitbild:
*jeder Datensatz hat genau EINEN Ort, an dem er gepflegt wird – das ERP; das ERP muss alles können,
was aussen geht.*

## Was gebaut wurde

- **Karte «Zugang» am Personendatensatz** (`components/erp/person-access.tsx`, dasselbe Bauteil
  wie «Sicherheit» im Konto, `owner`: `null` = ich, sonst die Nummer): die Passkeys (Name,
  hinzugefügt, zuletzt benutzt, «Entfernen») und die Verbindungen mit Claude (Client, erlaubt,
  zuletzt benutzt, «Trennen»). Sehen und handeln: die Person selbst und der Admin
  (`policy` «person.access», SELF); andere Mitarbeitende sehen wie bisher nur die Zahl der Passkeys
  in «System». Die Antwort des Datensatzes trägt `may_access` – die Oberfläche fragt den Server.
- **Routen** `GET · DELETE /api/v1/erp/records/{nr}/passkeys[/{id}]`,
  `GET /api/v1/erp/records/{nr}/mcp`, `POST …/mcp/{grant}/revoke` (`routers/access.py`) – sie rufen
  **dieselben Dienste** wie das Konto (`passkey.list_passkeys` · `delete_passkey`, `mcp.grants` ·
  `revoke`). Kein Handgriff: Anmeldewege fasst die KI nicht an (`handgriff._routes`).
- **Eine Verbindung mit Claude ist offen**, solange sie nicht getrennt ist **und** ihre letzte
  Benutzung (das Erlauben oder die jüngste Erneuerung) höchstens `REFRESH_TTL` (30 Tage) zurückliegt
  – abgeleitet aus dem Log, keine Spalte (`mcp._OPEN`). Dieselbe Abfrage für die Liste und für jede
  Anfrage (`bearer`, Erneuerung): was nicht in der Liste steht, kommt auch nicht hinein. Die
  Erneuerung selbst läuft signiert nach 30 Tagen ab (`core/signed`, geprüft). Trennt jemand in Claude,
  erfährt das ERP es nie – «zuletzt benutzt» macht das sichtbar, nach 30 Tagen fällt der Eintrag weg.
  Nicht automatisch getrennt wird eine ältere Verbindung desselben Clients: zwei Geräte sind legitim.
- **Wächter** `tests/test_erp_master.py`: jede Route der Selbstbedienung (`/api/v1/auth/…`,
  angemeldet) steht in `policy.SELF_SERVICE` – mit ihrem Gegenstück im ERP (das es als Route geben
  muss) oder als `SelfOnly` mit Grund. Gegengeprüft: auf dem alten Stand fehlten vier Gegenstücke
  (Passkeys lesen/entfernen, Claude lesen/trennen); eine neue Konto-Route ohne Eintrag und ein
  `SelfOnly` ohne Grund schlagen an.

## Die Prüfung

| Bereich | aussen | im ERP sichtbar | im ERP machbar | Befund / Massnahme |
|---|---|---|---|---|
| Person (Name, Telefon, Geburtsdatum) | Konto | ja (Karte «Person») | ja (`PATCH /erp/records/{nr}`, derselbe Pfad) | in Ordnung |
| Anmelde-E-Mail ändern | Konto (Firebase-Link an die neue Adresse) | ja («System») | nein | **Selbst** (`SelfOnly`): nur die Person beweist, dass die neue Adresse ihr gehört. **Vorschlag** unten (1) |
| Adressbuch (privat, Geschäft) | Konto | ja | ja (dieselben Dienste) | in Ordnung |
| Firma | Konto (nennen → erkennen/anlegen) | ja | ja (zuordnen; anlegen über «+» Firma) | in Ordnung |
| Newsletter | Konto (direkt an/ab), Website (Double Opt-in) | ja (Zustand + Nachweis) | Bitte senden, abmelden | Anmelden ist eine **Einwilligung** – nur die Person; das ERP bittet darum. In Ordnung |
| `notification_email` · `notification_inapp` | Konto-API nahm sie an (keine Oberfläche) | nein | nein | **Behoben**: das Konto schrieb Werte, die das ERP nie zeigte und nichts liest – `UserProfileUpdate` nimmt sie nicht mehr an (Spalten bleiben, Backlog) |
| Passkeys | Konto (einrichten, entfernen) | **vorher nur die Zahl** | **vorher nein** | **Behoben**: Karte «Zugang» (sehen, entfernen; selbst und Admin). Einrichten bleibt `SelfOnly` (Gerät) |
| Verbindungen mit Claude | Konto (sehen, trennen) | **vorher nein** | **vorher nein** | **Behoben**: Karte «Zugang»; dazu «offen» = nicht getrennt und zuletzt benutzt ≤ 30 Tage |
| Claude verbinden (OAuth-Zustimmung) | `/erp/verbinden` | – | – | ist selbst im ERP; die Zustimmung gibt nur die Person (Selbst) |
| Vorschläge aus Claude (MCP) | Claude der Person | ja («Auf einen Blick», privat: selbst · Admin) | ja (übernommen nur im ERP) | in Ordnung |
| Dokument unterschreiben / ablehnen | `/dokument` (Link) | ja (Zustand am Dokument) | nein | **Selbst**: eine Unterschrift ist die der Person. In Ordnung |
| Offerte annehmen / ablehnen | `/dokument` | ja (Beleg) | ja (Verben `agree` · `decline` am Beleg) | in Ordnung |
| Mit Karte bezahlen | `/dokument`, Bezahlkarte | ja (Geld-Zeile vom Webhook) | bar · Überweisung erfassen | Kartendaten gibt nur die Partei ein. In Ordnung |
| Kontaktformular | Website | ja (offene Nachricht im Verlauf der Person) | ja (antworten) | in Ordnung |
| Newsletter-Anmeldung Website | Website | ja, sobald bestätigt (Person + Nachweis) | Bitte, abmelden | vor der Bestätigung gibt es nichts – gewollt |
| Kontaktdaten der Website | Website | ja (Gesellschaft) | ja (gepflegt nur im ERP) | Spiegel, in Ordnung |

## Vorschläge (nicht gebaut)

1. **Anmelde-E-Mail einer Person im ERP korrigieren** (z. B. beim Anlegen vertippt, die Person hat
   sich nie angemeldet). Heute geht das nur über das Konto der Person. Vorschlag: Admin-Handlung
   `POST /erp/records/{nr}/email` – nur solange die Person sich nie angemeldet hat
   (`last_login_at` leer) direkt über das Firebase Admin SDK, sonst schickt sie den
   Bestätigungslink an die neue Adresse (gleiche Regel `people.email_problem`). Gross, weil es die
   Identität in Firebase berührt; eingetragen in `docs/backlog.md`.
2. **Verbindungen mit Claude aufräumen**: ein Hinweis «älter als die neueste Verbindung desselben
   Clients, seit X nicht benutzt» wäre möglich; bewusst nicht gebaut – «zuletzt benutzt» genügt, und
   nach 30 Tagen fällt der Eintrag von selbst weg.
