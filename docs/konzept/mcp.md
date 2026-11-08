# MCP – das ERP im eigenen Claude (Projektakte)

Stand: 08.11.2026 · gebaut: Lesen und Vorbereiten · offen: Ausführen

## Ziel

Jede Mitarbeiterin, jeder Mitarbeiter arbeitet mit dem ERP auch aus dem **eigenen Claude** –
Claude.ai, Desktop, Code, Mobile. Dieselben Rechte, dieselben Regeln, dieselbe Spur im Log wie
ein Klick im ERP. MCP ist der offene Standard, über den Claude Werkzeuge anderer Systeme nutzt;
das ERP wird damit ein «Connector».

## Grundsatz: kein zweiter Weg

- **Die Handlungen** sind die Routen des ERP (`services/handgriff`): was ein Klick kann, kann
  Claude – geprüft durch denselben Code. Es gibt keine Liste, die gepflegt werden müsste.
- **Die Werkzeuge** sind die des «+» (`ai_tools.tools_for` · `ai_tools.erp_tools`): `find`,
  `record`, `history`, `wissen`, `handlungen`, `handlung`, `abrufen`, `vorbereiten`. Ein neues
  Werkzeug dort ist ein neues Werkzeug hier.
- **Wer handelt**: die Person. Claude liest mit **ihren** Rechten (das Ergebnis bleibt bei ihr) –
  anders als die KI im «+», die als gemeinsamer Betrachter liest, weil ihr Ergebnis alle sehen.
- **Ändern = vorbereiten.** Ein Handgriff aus Claude ist privat wie ein Gespräch (`payload.mcp`)
  und steht im Angehefteten am Datensatz; ausgeführt wird er dort von der Person (Quelle
  «Claude»). Claude bekommt den Link `…/erp?open=<Nummer>`.

## Anmelden (OAuth 2.1, ohne Tabelle)

1. Claude fragt `/api/v1/mcp` → 401 mit dem Hinweis, wo man sich anmeldet
   (`/.well-known/oauth-protected-resource`, `/.well-known/oauth-authorization-server`; das
   Hosting leitet `/.well-known/oauth-*` an den Dienst).
2. Claude meldet sich als Client an (`…/oauth/register`, RFC 7591). Seine Kennung IST seine
   signierte Beschreibung (Name, Rückkehr-Adressen: https oder http auf localhost).
3. Die Person landet auf `/erp/verbinden` – angemeldet wie immer (Magic Link, Google, Passkey),
   sieht den Client und erlaubt. Nur Personal.
4. Der Code (2 Min., PKCE S256) wird gegen Zugang (1 h) und Erneuerung (90 Tage, rollend)
   getauscht. Das Tauschen schreibt `mcp.grant` – ein eindeutiger Index (Migration 179) macht
   «genau einmal».
5. Jede Anfrage prüft: Zugang echt, Person noch Personal, Verbindung nicht getrennt
   (`mcp.revoked`). Trennen: Konto · Sicherheit · Claude.

## Protokoll

JSON-RPC über einen `POST` (Streamable HTTP, Antwort als JSON, ohne Sitzung): `initialize`,
`ping`, `tools/list`, `tools/call`. Ein Werkzeug, das scheitert, antwortet mit `isError`. `GET`
gibt 405 (kein Strom vom Server nötig). Kein SDK – die vier Methoden sind wenige Zeilen.

## Einrichten

In Claude: Einstellungen · Connectors · «Eigenen Connector hinzufügen» → Adresse
`https://<host>/api/v1/mcp` (steht im Konto unter Sicherheit). Für Claude Code:

```bash
claude mcp add --transport http inexxio https://inexxio-dev.web.app/api/v1/mcp
```

## Nächster Schritt: Ausführen

Ein Werkzeug `ausfuehren` (über `handgriff.run`, genau einmal, mit den Rechten der Person) – wie
im «+» nur für einen Handgriff, den die Person ausdrücklich bestätigt. Anmeldung, Rechte und Log
bleiben, wie sie sind.
