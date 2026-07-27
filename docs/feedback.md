# Testnotizen – Pin setzen statt Befund dokumentieren

> Werkzeug der **Testumgebung**. In der Produktion existiert das Modul nicht (Backend
> antwortet 404, das Widget rendert nichts).

## Warum

Beim Testen fallen laufend Dinge auf, die besser sein müssten. Der Aufwand steckt nicht
im Erkennen, sondern im **Rekonstruieren des Kontexts**: Wo war ich? Welcher Datensatz war
offen? In welcher Rolle? Was hat der Browser dabei gemeldet? Genau das kann die Oberfläche
selbst mitschneiden – dann darf der Kommentar ein halber Satz sein.

Der schwierige Teil ist nicht das Kommentarfeld, sondern die Brücke vom Pixel zum Code.
Die Antwort hier sind **nicht Koordinaten und kein Screenshot, sondern Text + DOM-Signatur**:
Die Oberfläche ist deutschsprachig, ihre Beschriftungen («Freigeben», «Nachschub anlegen»)
stehen im Repository meist genau einmal. Der sichtbare Text des angeklickten Elements ist
damit der beste greppbare Anker, den es gibt.

## Bedienung

1. Launcher unten **links** (die KI sitzt rechts) → Liste der Notizen dieser Seite.
2. **«Notiz anheften»** → Zeigemodus. Das Element unter dem Cursor wird rot umrandet,
   ein Klick heftet die Notiz daran. `Esc` bricht ab.
3. Kommentar tippen, **Enter** speichert.
4. Solange die Liste offen ist, sitzen die **Pins** an ihren Elementen: gelb = offen,
   grün = erledigt, grau = verworfen. Ein Klick auf den Haken schliesst eine Notiz,
   der Papierkorb löscht sie.
5. **«Alle offenen Notizen als Markdown kopieren»** → das Briefing für die Entwicklung.
6. Fusszeile: **«Erledigte aufräumen»** entfernt alles Abgehakte/Verworfene,
   **«Alles zurücksetzen»** leert die Liste (zweiter Klick bestätigt). Beides wirkt nur
   auf die Notizen, die man auch sehen darf – ein Kunde räumt nie fremde Notizen weg.
   Gelöscht wird **weich** (`is_active=false`, Hausregel «nie hart löschen»).

**Für jede angemeldete Rolle** – Mitarbeiter, Admin, Lieferant und Kunde. Aus Kundensicht
zu testen und dabei melden zu können, ist ausdrücklich Teil des Zwecks.

## Was automatisch mitkommt

| Feld | Inhalt | Wozu |
|---|---|---|
| `route` | Pfad + Query (`/erp?open=100000123`) | Seite wiederfinden |
| `target_object_id` | Objektnummer des offenen Datensatzes | Fall reproduzieren |
| `context.view` | Datensatzart + aktiver Reiter («Artikel · Prozess») | Ansicht eingrenzen |
| `anchor.section` | umgebender Abschnitt («Bewegung», «Bestand») | Panel/Sektion eingrenzen |
| `anchor.label` | sichtbarer Text des Elements | **greppbarer Anker im Code** |
| `anchor.selector` | Tag-/Positions-Kette (ohne Klassen) | Pin wiederfinden |
| `anchor.html` | `outerHTML`, auf 800 Zeichen gekappt | Komponente erkennen |
| `anchor.rx/ry` | relative Position im Element | Pin sitzt wieder gleich |
| `context.role` | Rolle des Melders | Rechte-abhängige Befunde |
| `context.viewport` | Fenstergrösse | «nur auf dem Handy kaputt» |
| `context.version` | Build-Commit (`NEXT_PUBLIC_COMMIT_SHA`) | «welchen Stand hast du gesehen?» |
| `context.errors` | letzte 5 Laufzeitfehler der Sitzung | der Teil, den niemand von Hand notiert |

Der Fehler-Ringpuffer hört nur auf `error` und `unhandledrejection` – **kein**
Monkey-Patching von `console.*`, damit das Werkzeug die Anwendung nicht beeinflussen kann.

### Warum «Ansicht» und «Abschnitt» nötig wurden

Der ERP-Feed ist ein **Master-Detail auf EINER Route**: `/erp` bleibt `/erp`, egal welcher
Datensatz offen ist (`?open=` ist nur der Deep-Link von aussen). Notizen aus dem
Detailfenster trugen deshalb anfangs **keine Objektnummer** – die Entwicklung musste den
Datensatz aus dem Notiztext erschliessen. Jetzt meldet die ERP-Seite ihre Auswahl an
`setOpenRecord` (eine Stelle: der `sel`-Effekt in `erp/page.tsx`), und `currentObjectId`
zieht sie der URL vor.

Dasselbe Problem in klein hat der **Prozess-Editor**: seine Schritte sind eine dynamische,
sortierbare Liste – eine `nth-of-type`-Kette sagt dort nur «der dritte Block», was nach dem
nächsten Umsortieren nicht mehr stimmt. Darum markieren sich `PanelHeader` und
`SectionTitle` mit `data-fb-section` (wieder: je eine Stelle), und der Anker nimmt den
Abschnittstitel mit. Eine Notiz am Bewegungs-Panel liest sich dann als
«Ansicht: Auftrag · Ablauf / Abschnitt: Bewegung» – unabhängig von der Position.

## Datenmodell

`feedback_notes` (Migration `082`) – bewusst **ohne Objektnummer**. Eine Notiz ist ein
Meta-Artefakt *über* dem System, kein Geschäftsobjekt; sie gehört weder in den 9-stelligen
Nummernkreis noch in den ERP-Feed, den Event-Strom oder das Audit-Log. Gleiche Einordnung
wie `ai_actions`, `attachments`, `audit_log`. Deshalb heisst die Referenz auf den offenen
Datensatz `target_object_id` (wie bei `AiAction`) und nicht `object_id` – `object_id` ist
im System immer die *eigene* Nummer eines Datensatzes.

Status als Ampel, drei Werte: `open` (gelb) → `done` (grün) | `dismissed` (grau).

**Sichtbarkeit:** Personal (admin/employee) sieht alle Notizen, jede andere Rolle
ausschliesslich die eigenen. So kann aus Kundensicht gemeldet werden, ohne dass ein Kunde
die Testnotizen anderer liest.

## Code

| Datei | Rolle |
|---|---|
| `backend/app/models/feedback.py` | Tabelle |
| `backend/app/schemas/feedback.py` | Grenzen (Längen, Status-Whitelist, Fehler-Kappung) |
| `backend/app/services/feedback.py` | die EINE Stelle für Sichtbarkeit/Anlage/Abschluss |
| `backend/app/routers/feedback.py` | `GET/POST /api/v1/feedback`, `PATCH`/`DELETE …/{id}`, `DELETE …?scope=done\|all` |
| `frontend/src/lib/feedback.ts` | Anker, Kontext, Markdown-Export (React-frei) |
| `frontend/src/components/feedback/feedback-pin.tsx` | Widget (Launcher, Liste, Zeigemodus, Pins) |

Gemountet in den Layouts `(public)`, `(account)` und `(erp)` – wie das KI-Widget, mit
eigener Auth-Prüfung, damit es in jedem Layout ohne Zutun funktioniert.

## Arbeiten mit den Notizen (Entwicklung)

1. Im Widget **«Alle offenen Notizen als Markdown kopieren»**.
2. In einer Claude-Code-Sitzung einfügen (oder `/feedback` verwenden,
   `.claude/skills/feedback/`).
3. Pro Notiz: über `anchor.label` das Element im Repository suchen
   (`rg -n "Freigeben" frontend/src`), `route` grenzt auf die Seite ein.
4. Nach der Umsetzung: Notiz auf **erledigt** setzen (Haken im Widget) – der Pin wird beim
   nächsten Testlauf grün, an genau derselben Stelle. Damit wird direkt am Ort verifiziert
   statt aus einer Liste heraus.

Exportformat (stabil halten – die Skill liest es):

```markdown
## #12 · /erp

> Der Freigeben-Knopf sollte hier ausgegraut sein

- **Ansicht:** Auftrag · Ablauf
- **Abschnitt:** Bewegung
- **Element:** «Freigeben» (`button`)
- **Selektor:** `div > div:nth-of-type(2) > button`
- **Datensatz:** 100000123
- **Umgebung:** Rolle employee · 1440x900 · Build a1b2c3d4
- **Fehler:** …
- **Gemeldet:** Clemens Fritsche, 27.07.2026, 10:14
```

## Bewusst nicht gebaut

- **Kein automatisches GitHub-Issue.** Das hiesse ein Token im Backend und eine zweite
  Wahrheit neben der Datenbank. Der Markdown-Export deckt den Bedarf; ein Sync ist später
  ein Zehnzeiler.
- **Kein Screenshot per `html2canvas`.** CSP-Ärger und Bundle-Gewicht für etwas, das der
  Text-Anker besser leistet.
- **Keine `data-*`-Anker im ganzen UI.** Verlockend (exakter Anker), hiesse aber, hunderte
  Attribute zu verdrahten, bevor die erste Notiz existiert. Nachrüstbar genau dort, wo der
  automatische Anker danebenliegt.
- **Kein Voting, keine Kommentar-Threads, kein Kanban.** Das ist ein Zettel mit Kontext.

## Erweiterungspfad

- **Service-Token** in Secret Manager → die Entwicklungs-Sitzung holt die offenen Notizen
  selbst (`GET /api/v1/feedback?status=open`), das manuelle Kopieren entfällt.
- **Screenshot per Zwischenablage** (Strg+V in die Notiz) über das bestehende
  `attachments`-Modul – Auslieferung authentifiziert, nicht über den öffentlichen Token.
- **KI-Veredelung** nach ADR-004-Muster: Titel/Kategorie ableiten, Dubletten erkennen
  (lexikalisch gratis über `article_names._similarity`).
