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

## 5. Der Nachtrag: die drei offenen Punkte sind erledigt

> Die erste Runde hat drei Dinge gemessen und liegen gelassen, weil sie **Verhalten**
> ändern statt aufzuräumen. Sie sind in einem Folge-Deploy nachgezogen – und bei zweien
> war die im ersten Bericht vermutete Lösung **falsch**. Das steht hier so, weil eine
> Vermutung, die man nicht nachprüft, beim nächsten Mal als Tatsache gelesen wird.

### 5.1 Die toten Spalten sind gedroppt (Migration `120`)

Die **Zwei-Deploy-Regel** ist damit einmal komplett durchlaufen: 22 Spalten verloren im
Aufräum-Deploy ihr Mapping und fallen jetzt. Vorbedingung geprüft statt angenommen –
keine stand mehr in `Base.metadata`. Verifiziert von null · idempotent · downgrade ·
**und über das Lifespan-Netz** (eine Datenbank, auf der Alembic nie lief: 10 tote
Spalten vor dem Start, 0 danach, alle Endpunkte 200).

Die **Tabellen** der entfernten Bereiche bleiben stehen, und das ist eine Entscheidung,
keine Vergesslichkeit: eine Spalte, die niemand liest, kostet nichts – ein Tabellen-Drop
kostet die Vergangenheit und ist unumkehrbar. `document_blobs` hält die Dateien selbst.
Der Drop verlangt vorher eine Sicherung der **produktiven** Datenbank, und die kann nur
jemand mit Zugriff darauf ziehen. Reihenfolge in `docs/backlog.md`.

### 5.2 Die Modul-Vollständigkeitsprüfung im Browser ist gelöscht

**Die Diagnose der ersten Runde war falsch.** Dort stand, die «freundliche Hälfte» laufe
gar nicht. Sie lief – nur über den **Server**: beide Entwürfe fragen `POST …/validate`,
dessen `missing` im Hinweis des Freigabe-Knopfes steht, und `validate_draft` schickt die
Modul-Konfiguration durch dieselbe `Module.clean_config`, an der auch die Freigabe
abweist. Gemessen an den echten Dienstpfaden:

| Fall | Antwort des Servers |
|---|---|
| Beschaffen ohne Bestellangabe | «Lieferant 100000001 braucht eine Bestellangabe – seine Artikelnummer oder den Link, unter dem man bei ihm bestellt.» |
| Datenerfassung ohne Punkt | «Eine Datenerfassung ohne Erfassungspunkt erfasst nichts. Mindestens ein Punkt ist Pflicht.» |
| Aussondern ohne Grund | «‹Aussondern› braucht einen Grund – ohne ihn steht später da, dass Stücke ausgesondert wurden, aber nicht warum.» |

Die Browser-Fassung sagte dazu «Bestellangabe fehlt». Sie war also nicht nur doppelt,
sondern **schlechter** – und beim nächsten Feld wäre sie die mildere von zweien gewesen.
`moduleIncomplete` und die fünf `incomplete`-Closures sind darum weg.

**Die Wächter zeigen jetzt auf die Regel statt auf eine Zeichenkette.** Vorher prüften
sie, ob «Bestellangabe fehlt» in `modules.ts` *vorkommt* – das ist die Anwesenheit einer
toten Kopie, nicht das Verhalten: der Wächter schlug nicht an, obwohl die Kopie keinen
Aufrufer hatte, und er hätte angeschlagen, wenn man sie entfernt. Beide sind gegen ihre
Bug-Form gegengeprüft, und **einer war dabei stumpf**: `assert problems` war schon von
der ohnehin gemeldeten fehlenden Einzelinstanz erfüllt und liess die Bug-Form durch. Er
prüft jetzt die **Differenz** (mit Auftrag ↔ ohne).

### 5.3 Der seitliche Überlauf der Startseite ist behoben

**Auch hier war die vermutete Lösung falsch.** Der erste Bericht nannte `minmax(0, 1fr)`
für die Track-Definition. Das lässt die Spalte schrumpfen – aber «Kernkompetenzen» ist
bei `--h2` (`clamp(28px, 3.2vw, 44px)`, dort also 28 px) ein **unteilbares Wort von
~234 px**; der Überlauf wäre nur vom Raster in den Text gewandert. Zweispaltig blieben
dem Titel bei 320 px genau `280 − 100 (Meta) − 28 (Lücke) = 152 px`.

Der Kopf steht darum unter 640 px **einspaltig** – dieselbe Grenze, die `.ix-wrap`
ohnehin benutzt; ein zweiter Wert wäre ein zweiter Umbruchpunkt, den man beim nächsten
Abschnitt vergisst. Gemessen in Chromium: **0 px** Überlauf bei 1440 · 1280 · 1024 ·
834 · 375 · 320 px, und ab 640 px ist das Bild unverändert zweispaltig (geprüft: die
Meta-Spalte sitzt bei 1440 px und 700 px an derselben Stelle wie zuvor).

### 5.4 Was weiterhin bewusst steht

**`process.confirm_step` (259 Zeilen, davon 132 Code)** und `process.release` (166/109)
überschreiten die 80-Zeilen-Regel. Sie sind nicht Teil dieser Runde – der einzige
Eingriff in `process.py` war eine Kommentarzeile –, und `confirm_step` ist die **eine**
Ausführungsstelle, durch die jedes Modul läuft. Die Nähte sind vorgezeichnet (die
►►◄◄-Überschriften: Vorbedingungen · Erfassung · Bewegung/Verbrauch · Übergang ·
Nachlauf); eine eigene Runde mit eigener Messung wert.

**`main._ensure_columns` (104 Zeilen)** bleibt: das Lifespan-Netz für Kosmetik
anzufassen ist nach dem Vorfall zu Migration `090` das falsche Risiko.

**Die AGB beschreiben einen «Online-Shop www.inexxio.com».** Ein Rechtstext wird nicht
nebenbei umgeschrieben – das ist eine geschäftliche Entscheidung, zumal der Shop in
Phase 2 zurückkommen soll.

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
| Chromium, Überlauf bei 1440/1280/1024/834/375/320 px | **0 px, alle Seiten, alle Breiten** |
| Migration `120` | von null · idempotent · downgrade · **über das Lifespan-Netz** (10 tote Spalten vor dem Start, 0 danach) |

**Die Sichtprüfung war kein Ritual.** Sie hat in dieser Runde einen echten Fehler
gefunden, den der Build nicht meldet: eine unbekannte Tailwind-Klasse ist **kein**
Fehler, sie erzeugt schlicht kein CSS. Die Farbgruppe heisst `bg` und der Wert `dark` –
die Klasse ist also `bg-bg-dark`, nicht `bg-dark`. Fünf dunkle Abschnitte der
öffentlichen Seiten wären weiss auf weiss gewesen. Gefunden hat es eine Prüfung, die je
Element Text- und Hintergrundfarbe vergleicht.

---

## 7. Was als Nächstes ansteht

Die drei Punkte, mit denen dieser Bericht ursprünglich endete, sind erledigt (§5).
Offen bleibt genau einer, und er braucht einen Menschen mit Produktionszugriff:

**Die Tabellen der entfernten Bereiche droppen** – `events`, `document_*`,
`article_prices`, `ai_actions`, `fx_rates`, `article_sales_audience`. Kein Modell
verweist mehr auf sie, sie kosten nichts, und der Nummernraum hängt seit dem Aufräumen
an der Registry statt an einer Modellspalte. Der Drop ist aber unumkehrbar und verlangt
vorher eine Sicherung der produktiven Datenbank (`scripts/dump-db.sh`): **sichern →
Sicherung lesen → droppen**. Reihenfolge und Begründung in `docs/backlog.md`.
