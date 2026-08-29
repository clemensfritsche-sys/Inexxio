# Altlasten-Bereinigung, August 2026

**Ziel:** altlastenlos werden. Was einmal gebaut und nicht mehr gebraucht wird, kommt
restlos weg – Code, Datenmodell, Typen, Abhängigkeiten, Namen, Kommentare und Verweise.

**Zahlen** (7 Commits, `e293691`…`028a090`): **159 Dateien**, davon **64 gelöscht**;
**−19'550 / +7'103 Zeilen**. Ohne Dokumentation und generierte Dateien:
**−11'268 / +745** – auf zehn entfernte Zeilen Code kommt weniger als eine neue.

**Rollback-Punkt:** Git-Tag `attic/pre-cleanup-2026-08` (Commit `676a68c`).

---

## 1. Die Arbeitsweise: erst messen, dann löschen

Der erste Commit ist **kein** Löschen, sondern ein Messwerkzeug
(`backend/scripts/deadcode.py`, aufrufbar als `python -m scripts.deadcode`). Es
beantwortet «wer liest das eigentlich noch?» und unterscheidet drei Antworten:
**gar niemand** · **nur das Modul selbst** (eine Namensfrage, kein toter Code) · **nur
Tests und Skripte** (eine legitime Nutzung – die Wächter *sind* das Netz).

Zwei Feinheiten, an denen eine naive Messung falsch liegt und die im Werkzeug stehen:
ein Import führt **jede** `__init__.py` auf dem Weg aus, und ein Paket, das seine
Geschwister über `pkgutil.iter_modules` selbst einsammelt, hat gar keinen geschriebenen
Import. Dazu werden FastAPI-Endpunkte übersprungen – sie sind über HTTP erreichbar, nicht
über einen Import.

**Jede Fundstelle ist ein Hinweis, kein Urteil.** Von 35 Backend-Hinweisen am Ende waren
31 schwache Signale; gelöscht wurde, was einzeln geprüft war. Nach jeder Etappe lief die
volle Suite.

---

## 2. Was weg ist – und warum es weg durfte

### 2.1 Die abgeschalteten Bereiche (E1, −9'940 Zeilen)

Verkauf/Shop, Zahlungen, Dokumente/Belege, KI, Versand und der Ereignis-Strom lagen seit
dem Basis-Neuaufbau **abgeschaltet, aber vorhanden** im Repo: nicht importierbar, von
einem Stub mit `503` beantwortet, und für jeden Suchlauf trotzdem da.

Sie sind gelöscht, nicht stillgelegt. **Was dabei zählt, ist nicht die Datei, sondern die
Entscheidung darin** – die steht je Bereich auf einer Seite in **`docs/attic.md`**: was
es tat, wo die letzte lauffähige Fassung liegt (Tag oben) und welche fachliche Frage
darin beantwortet ist. Ein Wiederaufbau beginnt bei dieser Frage, nicht bei der alten
Datei; sonst holt man sich mit dem Code auch die Annahmen zurück, die inzwischen falsch
sind.

**Der Feature-Schalter ist mitgegangen** (`core/features.py` + sein Frontend-Spiegel).
Nachdem die Bereiche weg sind, schaltet er nichts mehr: ein «abgeschaltet» zu melden, wo
schlicht nichts existiert, ist eine Auskunft, die nicht stimmt – `404` ist die richtige
Antwort. Der Spiegel im Frontend war ohnehin von keiner Seite erreichbar und seine
Beschriftungen waren bereits abgewichen.

### 2.2 Ein echter Fund im Nummernraum

`services/objects.py` sammelt die vergebenen Objektnummern, um die nächste zu bestimmen.
Es las die Spalten der bekannten Typen **plus** `DocumentFile.object_id` – eine Tabelle,
die mit dem Dokument-Modul verschwand. Statt den Namen zu streichen (dann fehlten die
Nummern jener Zeilen im Raum) liest es jetzt die **Registry** (`ObjectRef.object_id`):
dort steht **jede je vergebene Nummer**, auch die eines Typs, den es nicht mehr gibt.
Das ist strikt stärker als eine Aufzählung von Tabellen – und es kann beim nächsten
entfernten Typ nicht wieder auseinanderlaufen.

### 2.3 Datenmodell: erst das Mapping, im nächsten Deploy der Drop (E2)

Tote Spalten verlieren ihr ORM-Mapping sofort, gedroppt werden sie **im Folge-Deploy**.
Das ist die Lehre aus dem Vorfall zu Migration `090`: während eines Cloud-Run-Rollouts
läuft die Vorgänger-Revision weiter und mappt die Spalte noch – ein Drop im selben Deploy
trifft sie. Die genaue Liste steht in **`docs/backlog.md`**.

### 2.4 Frontend (E3) und tote Abhängigkeiten (E5)

Tote Typen, API-Methoden und Exporte sind weg; die **Alt-Palette** (`slate-*`, `blue-*`,
`gray-*`, `#2563eb`, `brand-*`) hat **0 Vorkommen**.

Dazu vier npm-Pakete ohne einen einzigen Import – Reste der entfernten Bereiche
(`@stripe/react-stripe-js`, `@stripe/stripe-js`, `react-markdown`, `remark-gfm`):
**−1'485 Zeilen `package-lock.json`**. Zwei Formen muss man dabei sehen, sonst löscht man
Lebendes: der **Unterpfad** (`@hookform/resolvers/zod` – deshalb bleibt das Paket) und
der **dynamische** Import (`await import('@zxing/browser')`).

### 2.5 Tote Funktionen (E6)

`services/address.py` war für Versand-Etikett, PDF-Briefkopf und den Zahlungsanbieter
gebaut; alle drei sind entfernt. Vier öffentliche Funktionen hatten danach **keinen**
Leser (`of_user`, `one_line`, `lines`, `same`), zwei Helfer nur diese vier
(`person_name`, `_norm`), dazu ein toter Import. Geblieben ist, was Impressum und
Gebietskarte lesen. **Die zwei Entscheidungen darin stehen im Attic**, damit sie niemand
neu herleiten muss: der Rückfall «Lieferadresse, sonst Wohnadresse», und dass zwei leere
Adressen bewusst **nicht** als derselbe Ort gelten (daran hing die Transportklasse).

Ebenso entfallen: `models/process_event.EVENT_KINDS` (eine Aufzählung, die nichts
abweist – die `KIND_*`-Konstanten bleiben, sie sind das Vokabular) und
`schemas/process.StepConfirmResult` (beschrieb eine Rückgabe, die der Endpunkt nicht
liefert – er antwortet mit `OrderResponse`).

---

## 3. Die Dokumentation hat gelogen – gemessen, nicht gelesen

Geprüft wurde jeder genannte Pfad, jedes Symbol, jeder Wächter und jeder Endpunkt gegen
die laufende Anwendung. **Der Endpunkt-Vergleich lief gegen `app.routes`**, nicht gegen
das Gedächtnis:

* **4 dokumentierte Endpunkte existierten nicht** (`articles/{}/process-steps` CRUD –
  der Prozess ist heute *read-only* und entsteht als Ganzes mit der Freigabe).
* **16 lebende Endpunkte fehlten** (Instanzen, Orte, Objektauflösung, Gebiete, Passkeys,
  `validate`, Anhänge, Genealogie).
* **«Ein Lieferant hat keine Sicht auf einen Auftrag» war falsch** – die Sicht ist gebaut
  und verengt in `_to_response`/`_visible` über `purchase.mine`.

Drei falsche Behauptungen in `CLAUDE.md`: ein «Systemprotokoll am Auftrag», dessen
Endpunkt es nicht gibt; der «zentrale Schalter», der mitgegangen ist; und zwei normative
Beispiele, die `services/locations.py` und `inventory.in_stock_clauses()` nannten – beide
existieren nicht mehr (ersetzt durch die lebenden Paare). In `frontend/CLAUDE.md` stand
«react-hook-form + zod für **alle** Formulare» – im ERP wird nicht abgeschickt, sondern
gespeichert (`use-autosave`); die Bibliothek trägt genau ein Formular.

**5'668 Zeilen Historie** sind nach `docs/history/2026-06-vorgaenger-system.md` gewandert;
sieben veraltete Berichte liegen ebenfalls dort, jeder mit dem Hinweis, dass er einen
Zustand beschreibt, den es nicht mehr gibt. Jede ADR trägt jetzt einen **Kopfstatus**
(gültig · teilweise gültig · historisch) – eine Entscheidung von damals ist kein Irrtum,
aber sie darf nicht wie eine heutige Regel aussehen.

---

## 4. Echte Fehler, die dabei aufgefallen sind – und behoben wurden

Alle vier sind dieselbe Klasse: **ein Verweis auf etwas, das es nicht mehr gibt.**

1. **`deploy-prod.yml` mountete zwei Secrets ins Nichts** (`SECRET_KEY`,
   `GCS_BUCKET_NAME`). Kein Code liest sie mehr; ein Secret-Verweis, der sich nicht
   auflösen lässt, lässt die Cloud-Run-Revision **gar nicht erst starten**.
2. **`FRONTEND_BASE_URL` fehlte in der Produktion** (dev setzt es). Der Default ist
   `http://localhost:3000`, und `sites.website_url` leitet daraus das **Impressum** ab –
   die Produktion hätte dort localhost genannt.
3. **`cors_origins` nannte zwei Hosts, die es nie gab** (`inexxio.web.app`,
   `inexxio.com`) und **nicht** `inexxio-prod.web.app`. Da keine der beiden
   Bereitstellungen `CORS_ORIGINS` setzt, **ist dieser Default der Betrieb** – und es
   sind zugleich die erlaubten **WebAuthn-Origins**: was hier fehlt, kann sich nicht per
   Passkey anmelden.
4. **Zwei tote Fallbacks:** `next.config` erlaubte Bilder vom GCS-Bucket des entfernten
   Dokument-Moduls (dazu nutzt keine Stelle `next/image`), und `firebase.ts` fiel für den
   Magic-Link auf `inexxio.web.app` zurück – kein Ziel. Die Adresse weiss jetzt das
   Deployment (`NEXT_PUBLIC_APP_URL`).

Dazu: `docker-compose` fuhr **PostgreSQL 15** gegen **16** in CI und Cloud SQL – ein
Versionsunterschied, der erst im Deploy auffällt.

---

## 5. Gefunden, bewusst NICHT behoben

> Diese Punkte sind gemessen und reproduzierbar. Sie zu ändern hiesse, Verhalten zu
> ändern – das ist eine Entscheidung, keine Aufräumarbeit.

**(a) Die «freundliche Hälfte» der Modul-Prüfung läuft gar nicht.**
`lib/modules.ts: moduleIncomplete` (und die fünf `incomplete`-Closures) hat **keinen
Aufrufer**. Der Wächter `test_the_order_reference_is_a_mandatory_field` verspricht in
seinem Docstring ausdrücklich *beides* – «der Server weist sie ab (die Regel) und die
Oberfläche meldet sie vor der Freigabe (die freundliche Hälfte)» –, prüft aber nur, ob
die **Zeichenkette** in der Datei steht. Er schlägt also nicht an, obwohl die Hälfte
fehlt; und er schlägt an, wenn man den toten Code entfernt.
*Der Code wurde testweise gelöscht, gemessen und wieder hergestellt.* Zu entscheiden:
entweder `moduleIncomplete` im Designer verdrahten (dann stimmt der Wächter), oder den
Wächter auf die Server-Regel zeigen lassen und den Browser-Zwilling löschen.

**(b) Die Startseite scrollt auf schmalen Telefonen seitwärts.**
Gemessen in Chromium: **62 px** Überlauf bei 320 px, **7 px** bei 375 px; ab 834 px
sauber, alle anderen Seiten bei jeder Breite 0. Ursache ist `.ix-section-head`
(`grid-template-columns: auto 1fr`): eine `1fr`-Spalte ist `minmax(auto, 1fr)` und
schrumpft **nicht** unter ihren Inhalt – 100 px Meta-Spalte + 28 px Lücke + das längste
Wort («Kernkompetenzen») passen nicht in 320 px. *Ein `min-width: 0` an den Kindern ist
**nicht** die Lösung (gemessen: verschlechterte es auf 68 px) – die Track-Definition muss
`minmax(0, 1fr)` heissen.* Vorbestehend: die Startseite wurde in dieser Runde nicht
angefasst, und die einzige Änderung an `globals.css` war ein Rahmen**farb**-Token.

**(c) Zwei Funktionen überschreiten die 80-Zeilen-Regel deutlich:**
`process.confirm_step` (259 Zeilen, davon **132 Code**) und `process.release` (166/109).
Sie sind nicht Teil dieser Runde – der einzige Eingriff in `process.py` war eine
Kommentarzeile –, und `confirm_step` ist die **eine** Ausführungsstelle, durch die jedes
Modul läuft. Sie hier zu zerlegen wäre ein Refactoring auf Verdacht am bestgeschützten
Stück des Systems. Die Nähte sind vorgezeichnet (die ►►◄◄-Überschriften im Code:
Vorbedingungen · Erfassung · Bewegung/Verbrauch · Übergang · Nachlauf) – eine eigene
Runde mit eigener Messung wert.

**(d) `main._ensure_columns` (104 Zeilen)** bleibt ebenfalls: das Lifespan-Netz für
Kosmetik anzufassen ist nach dem Vorfall zu Migration `090` das falsche Risiko. Es ist
ohnehin tabellengetrieben.

**(e) Die AGB beschreiben einen «Online-Shop www.inexxio.com».** Den gibt es nicht mehr.
Ein Rechtstext wird nicht nebenbei umgeschrieben – das ist eine geschäftliche
Entscheidung, zumal der Shop in Phase 2 zurückkommen soll.

---

## 6. Verifikation

| Prüfung | Ergebnis |
|---|---|
| `pytest` gegen die gewachsene Datenbank | **445 passed**, 1 skipped |
| `pytest` gegen ein Schema **nur aus den Migrationen** (`alembic upgrade head` von null) | **445 passed**, 1 skipped |
| Lifespan-Sicherheitsnetz gegen die gewachsene Datenbank | alle Netze gelaufen, `/health` · `/admin/settings/public` · `/` je **200** |
| `tsc --noEmit` | 0 Fehler |
| `next lint` | keine Warnungen |
| `next build` | 12 Routen, alle statisch |
| Generierte Dateien neu erzeugt (`openapi.json`, `status-catalog.ts`, `api.ts`) | nur Docstring-Text geändert, **kein Schema-Unterschied** |
| Chromium, 7 öffentliche Seiten | 0 unsichtbare Texte, 0 JS-Fehler |
| Chromium, Überlauf bei 1440/1280/1024/834/375/320 px | 0 – ausser der Startseite (siehe 5b) |

**Die Sichtprüfung war kein Ritual.** Sie hat in dieser Runde einen echten Fehler
gefunden, den der Build nicht meldet: eine unbekannte Tailwind-Klasse ist **kein**
Fehler, sie erzeugt schlicht kein CSS. Die Farbgruppe heisst `bg` und der Wert `dark` –
die Klasse ist also `bg-bg-dark`, nicht `bg-dark`. Fünf dunkle Abschnitte der
öffentlichen Seiten wären weiss auf weiss gewesen. Gefunden hat es eine Prüfung, die je
Element Text- und Hintergrundfarbe vergleicht.

---

## 7. Was als Nächstes ansteht

1. **Der Folge-Deploy mit den Spalten-Drops** – Liste in `docs/backlog.md`.
2. Eine Entscheidung zu **5a** (Modul-Prüfung verdrahten oder Zwilling löschen).
3. **5b** beheben (`minmax(0, 1fr)`), gemessen wie oben.
