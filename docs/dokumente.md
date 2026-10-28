# Dokumente – die eine Ablage

> **Ist-Stand.** Wie es so wurde: `docs/history/2026-10-28-dokumente.md`. Im Zweifel gilt der Code
> (`backend/app/domain/documents.py`, `services/documents.py`, `services/fields.py`,
> `services/signing.py`, `services/ai.py`).

Ein **Dokument** ist **Datei + Art + Name + Referenz(en)**, mit eigener Objektnummer. Jede Datei
im Haus, die etwas belegt, ist eines: Lieferantenrechnung, Ausfuhrnachweis, Nachweis einer
Absenz, Bild der Datenerfassung, Anhang einer Mail, Foto aus dem Kontaktformular, jeder Beleg
(Offerte, AB, Rechnung, Quittung, Storno, Gutschrift, Mahnung), AGB und Datenschutz, Verfasstes.

## Die neun Regeln

1. **Dieselbe Datei ist dasselbe Dokument** (SHA-256, partieller Unique-Index). Kommt sie ein
   zweites Mal, öffnet der Entwurf das vorhandene.
2. **Vorher gibt es nichts.** Der Entwurf lebt im Browser; «Freigeben» legt in EINEM `POST`
   Datei, Nummer, Art, Name und Referenzen an (`documents.file`, die einzige Stelle).
3. **Art und Name sind Pflicht**, beides freier Text. Ohne KI tippt sie der Mensch.
4. **Ein Dokument erscheint genau dort, wohin seine Referenz zeigt** – als Kachel unten am
   Datensatz (`DocumentTiles`), keine Vererbung (auch nicht Person → Firma).
5. **Zuordnung als Vorschlag** (`services/reading`): ein wartendes Modul geht vor
   (`services/requirements`), dann unsere Nummer auf dem Blatt, dann der Absender. Den Betrag
   vergleicht der Code (±5 %), nie die KI. Gesetzt wird erst mit der Freigabe.
6. **Ein Pflichtfeld ist änderbar, nie leer** (`documents.set_field`; Schloss statt × am Chip).
   Felder: `voucher.original` · `voucher.export` · `voucher.doc` · `time.proof` ·
   `capture.photo` · `company.agb` · `company.privacy` (`domain/documents.FIELDS`), je mit
   seinem Auslöser in `services/fields.HANDLERS` – in derselben Transaktion wie die Freigabe.
7. **Gültig ist erst, was alle unterschrieben haben.** Zustand (abgeleitet): Freigegeben ·
   Unterschrift angefragt · Abgelehnt (endgültig) · Gelöscht.
8. **Gelöscht wird nur, was nirgends hängt** – mit Grund; Datei und Gelesenes sind weg, der
   Datensatz bleibt im Feed mit Art, Name, wer, wann, warum. Ein Beleg hängt immer
   (`voucher.doc`) und ist damit nie löschbar (10 Jahre).
9. **Wer die Referenz sehen darf, sieht das Dokument** (`services/access`): nur Personal; ein
   Teil `time:` nur die Person selbst und der Admin. Kein «vertraulich»-Schalter.

## Wege hinein – alle in DENSELBEN Entwurf (`document-draft.tsx`)

- **«+» → Dokument**: Scannen · Datei · Verfassen.
- **Scannen** (`components/scan/doc-scanner.tsx`, `lib/doc-scan.ts`): OpenCV.js
  (`public/vendor/opencv-<Version>.js`, geladen erst beim Scannen) findet das Blatt, liegt es
  ruhig, wird von selbst aufgenommen; Ecken ziehen, «Nächste Seite», «Fertig». Mehrere Seiten
  werden beim Freigeben ein PDF. Ohne OpenCV bleibt es ein Fotoapparat.
- **Verfassen** (`compose-chat.tsx`, `services/composing.py`): im Gespräch mit der KI, gesetzt
  in der Vorlage (`document.written`), Linien für die Unterzeichner. Ohne KI kein Verfassen.
- **Ein Feld eines Moduls** (`document-field.tsx`): vorhandenes Dokument wählen oder «Neu».
- **Anhang einer Mail / Foto der Anfrage**: Klick öffnet den Entwurf
  (`GET /erp/messages/{id}/attachments/{i}`, aus Gmail geholt, wenn ein Mensch öffnet).
- **Bild der Datenerfassung**: nur Kamera, dann der Entwurf (Feld `capture.photo`).
- **Beleg**: `voucher_docs.issue` legt das Papier als Dokument ab. Davor zeigt die Karte es
  (Vorschau → Freigeben, `voucher_docs.preview`, ein zurückgerollter Lauf derselben Handlung).
  AB und Quittung gehen nie von selbst: sie stehen an (`voucher.papers_due`, «zu tun») und
  gehen mit «Prüfen und freigeben» (Verb `release`); `voucher.AUTO_RELEASE` ist leer.

## Wege hinaus

- **Senden** (`services/signing.send`): je Empfänger ein Link `/dokument?t=…` **ohne Ablauf**
  und eine Mail im Verlauf (Postfach des Betreibers). Optional «sollen unterschreiben».
- **Unterschreiben** auf `/dokument`: ein Zug (PNG) oder Ablehnen mit Grund. Die Unterschrift
  steht auf dem Papier (`signing.signed_html` ersetzt die Marke `<!--sig:…-->`; das Papier
  selbst ändert sich nie). Gelöscht → 410 mit einem Satz.

## KI (optional)

Eine Tür (`services/ai.ask`), Aufgaben und Modelle in `TASKS` (Lesen: Haiku 5.5, Verfassen:
Sonnet 5.5), feste Antwortform (structured outputs), Tagesdeckel `AI_DAILY_CAP` (300), jeder
Aufruf eine Zeile im `audit_log` (`on_behalf = ai`). Ohne `ANTHROPIC_API_KEY` geht alles
ausser Verfassen; ein ohne KI freigegebenes Dokument wird beim Öffnen nachgelesen, sobald es
sie gibt. **Suchen** ist reine Datenbank (Nummer, Art, Name, Volltext über Gelesenes).

## Speicher

Die Bytes liegen in **Cloud Storage**, je Umgebung ein eigener Bucket (`inexxio-dev-files` ·
`inexxio-prod-files`, Region europe-west6, privat, Objektname = Token). Der Deploy legt ihn an
und gibt dem Dienstkonto `cloudrun-backend@…` die Rolle «Storage-Objekt-Administrator»; dann
setzt er `FILES_BUCKET`. Ohne Bucket (lokal, Tests) oder wenn er gerade nicht schreibbar ist,
bleiben die Bytes in der Zeile (`attachments.data`) – eine Datei geht nie verloren. Gelöscht
wird das Objekt erst nach dem Commit. Alles steht in `services/attachments` (`keep` ·
`bytes_of` · `discard`). Grenze 25 MB je Datei (Cloud Run nimmt 32 MB je Anfrage).

Klappt das Anlegen im Deploy nicht (fehlende Rechte), einmal von Hand – je Umgebung:

```bash
P=inexxio-dev   # bzw. inexxio-prod
gcloud storage buckets create gs://$P-files --project $P --location europe-west6 \
  --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets add-iam-policy-binding gs://$P-files \
  --member serviceAccount:cloudrun-backend@$P.iam.gserviceaccount.com --role roles/storage.objectAdmin
```

## Rechtstexte

AGB und Datenschutz sind Pflichtfelder jeder eigenen Gesellschaft. Jedes Papier hängt die AGB
seiner Gesellschaft an (Markdown aus der Vorlage wird gesetzt; ein PDF wird genannt); die
Website zeigt die AGB der Gesellschaft zum Land des Besuchers, Datenschutz und Impressum des
Betreibers. `app/assets/legal/` ist die Vorlage («Aus Vorlage übernehmen», nur Admin).
