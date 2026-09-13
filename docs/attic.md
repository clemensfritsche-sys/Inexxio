# Dachboden – was entfernt wurde und wo es liegt

Der Basis-Neuaufbau (August 2026) hat die Prozesslogik ersatzlos entfernt und auf dem
Einzelinstanz-Modell neu aufgebaut. Vier Bereiche standen auf der alten Logik auf und
blieben liegen: **Verkauf/Shop**, **Dokumente/Belege**, **KI** und die daran hängenden
Anbindungen (Zahlung, Versand, Datei-Ablage). Sie waren monatelang nicht einmal
importierbar – eine Aufstellung des Kaputten, an der jeder Wächter vorbeisah.

Mit dem Aufräumen sind sie **gelöscht**. Diese Seite ist ihr Ersatz: sie sagt, wo die
letzte lauffähige Fassung liegt, was sie konnte und welche fachliche Entscheidung darin
steckt – damit ein Wiederaufbau bei der Entscheidung anfängt und nicht bei der Archäologie.

> **Der Wiederaufbau ist kein Zurückholen.** Jede dieser Fassungen steht auf dem alten
> Datenmodell (Instanz mit Mengen-Skalar, `quality`/`disposition`, Reservierungs-Map,
> `article_process_steps` als Prozess). Das gibt es nicht mehr. Was hier steht, ist als
> **Entscheidungsprotokoll** wertvoll, nicht als Vorlage: die Fragen sind dieselben, die
> Antworten müssen neu gegeben werden.

## Die Handels-Module «Beschaffen» und «Verkauf» (September 2026)

`domain/{procurement,money}.py` · `services/{purchase,invoices,payments}.py` ·
`models/{purchase,invoice,payment}.py` · `frontend/components/erp/purchase-work.tsx`

**Der Stand:** der Commit vor dieser Löschung auf `develop` (`git log -- backend/app/services/purchase.py`).
Die Tabellen `purchases`, `invoices`, `payments` stehen unverändert in der Datenbank
(`docs/backlog.md`) – die Daten sind also da, nur ohne Code.

**Warum sie weg sind — es war eine Doppelung, kein Fehler.** Der Beleg war Angebot →
Zusage → Erfüllung, mit Angebotsspiegel, Rechnungen, Zahlungen und Storno. Genau das ist
der **Geldvorgang** (`domain/deal`, PROCESS_CORE §9.12), nur ohne die Bindung an Ware –
und damit auch für Miete, Lohn, Gebühr, Spesen und eine eingekaufte Spedition brauchbar.
Zwei Maschinen für dasselbe Geschäft laufen beim ersten neuen Verb auseinander.

**Was die Löschung leicht machte:** der Geldvorgang war von Anfang an bewusst *neben*
ihnen gebaut, ohne eine Zeile zu teilen («kein Import aus `procurement`/`purchase`», mit
einem Quelltext-Wächter). An ihm war für die Löschung nichts zu tun.

**Die Entscheidungen, die darin steckten und heute im Geldvorgang leben:**

* *Drei Stufen, weil drei Dinge unumkehrbar sind* – nichts zugesagt · zugesagt · erfüllt.
  Der Geldvorgang hat davon **zwei**: die Erfüllung ist ein **Zustand**, kein Schritt.
* *Mehrere Gegenparteien sind eine Liste, kein zweiter Mechanismus* – der Angebotsspiegel
  des Einkaufs und der Tarifvergleich des Transports sind dieselbe Zeile.
* *Ein Modul räumt selbst auf* – **eine** Gegenhandlung (`revoke`), und was sie bewirkt,
  sagt die Stufe.
* *Eine Sendung zu buchen IST ein Einkauf* – ein Frachtführer ist ein Lieferant, ein
  Tarifvergleich ein Angebotsspiegel. Darum gab es nie ein «Versand»-Modul.
* *Die Richtung steht am Beleg, nicht am Modultyp* – ein laufender Auftrag trägt seinen
  Prozess eingefroren.
* *Was beschafft wird, sagt der Prozess* – die Einzelinstanzen davor tragen ihren Artikel;
  ein Artikelfeld daneben wäre die zweite Aussage.

**Was NICHT mitging:** `services/stripe_pay.py` und `docs/stripe-setup.md`. Die Anbindung
hängt jetzt am Geldvorgang (`deal.record_payment`), und die eine teuer bezahlte Lehre gilt
unverändert: **Adaptive Pricing bleibt aus**.

**Der Weg zurück beginnt bei der Frage, nicht bei der Datei:** *was kann der Geldvorgang
nicht, das ein eigenes Handels-Modul könnte?* Wenn die Antwort «nichts» ist, ist es kein
Wiederaufbau, sondern ein Feld am Geldvorgang.

## Der Stand

| | |
|---|---|
| Git-Tag | `attic/pre-cleanup-2026-08` |
| Commit | `676a68c` |
| Datum | 29. August 2026 |

```bash
git show attic/pre-cleanup-2026-08:backend/app/services/selling.py
git checkout attic/pre-cleanup-2026-08 -- backend/app/services/ai/   # nur zum Nachlesen
```

## Verkauf und Shop

`services/{selling,sale,pricing,tax,fx,refund,customer_returns,operating_costs}.py` ·
`routers/{sales,shop}.py` · `schemas/{sale,sales,shop}.py` ·
`models/{article_price,article_sales_audience,fx_rate}.py` · `services/payments/`

Der Verkauf lebte **am Artikel** (Profil + `article_prices` + Zielgruppe), nicht als
eigenes «Angebot»-Objekt. Die tragenden Entscheidungen:

- **Nur der Basispreis in CHF wird gepflegt**, alles andere ist abgeleitet – eine
  gestaffelte Pipeline (Kunden-/Zonenpreis → Rabatt → Währung → Steuer), und der
  Fremdwährungsbetrag ist **gepinnt** statt live umgerechnet.
- **EINE Kursquelle.** Der Shop zeigte unseren Tageskurs, Stripe belastete seinen –
  zwei Kurse für denselben Kauf. Gelöst, indem der Checkout Betrag **und** Währung
  vorgibt (Adaptive Pricing aus).
- **Zwei unabhängige Achsen**: Preismodell (Einmalkauf ↔ Abo) und Verfügbarkeit
  (ab Lager ↔ auf Bestellung). Ein Kauf war immer ein gewöhnlicher Auftrag; was an
  Bestand fehlte, deckte ein Nachschub-Unterauftrag.
- **Der Auftrag entstand erst bei bestätigter Zahlung** (`CheckoutIntent`), und die
  Retoure war kein eigener Typ, sondern derselbe Verkaufs-Beleg im **Kredit-Modus**.

## Dokumente und Belege

`services/{document,document_render,legal,consent,storage}.py` ·
`routers/{documents,document_files,legal,consent}.py` ·
`models/{document_file,document_link,document_blob,document_signoff,document_acknowledgement}.py`

Zwei Dinge, die man nicht verwechseln darf: ein **verfasstes** Dokument (Instanz mit
Objektnummer, aus einem Prozessschritt) und eine **hochgeladene** Fremddatei (Rechnung,
Lieferschein). Die Entscheidungen:

- **Freigabe als Sub-Prozess** (Entwurf → ausgestellt → Freigaben laufen → freigegeben),
  mit einer endlichen, geordneten Parteienliste; erst wenn alle signiert haben, ist es
  freigegeben. Daneben ein **offenes Publikum**, das anerkennen muss – das blockiert
  nie einen Auftrag, sondern erscheint als Gate beim nächsten Login.
- **Die Zuordnung ist n:m** und entsteht über einen Vorschlag, den ein Mensch bestätigt
  («Vorschlagen ≠ Ausführen»); ein Dokument entsteht nie objektlos.
- **Rechtstexte sind ein Zeiger auf einen Artikel** – neue Fassung = neuer Artikel +
  Ersetzen, die Auflösung folgt der Kette. Damit ist die AGB-Version geschenkt.

## KI

`services/ai/` · `routers/ai.py` · `schemas/ai.py` · `models/ai.py`

Vier dünne Schichten (ADR 004, weiterhin unter `docs/adr/`): Gateway (Anbieter
austauschbar), **KI-Identität** als System-Benutzer mit Objektnummer, **rechte-gescopte
Werkzeuge** (jedes Tool wrappt die bestehende Authz – Scoping ist Authz, nicht Prompt)
und die Autonomie-Regel: Entwürfe legt sie an, **Kritisches schlägt sie vor** und ein
Mensch bestätigt.

## Versand

`services/shipping/` (Shippo · Sendcloud · manual)

ADR 005 bleibt gültig in seiner Kernaussage: **Versand wird abgeleitet, nicht bestellt** –
aus Quelle und Ziel einer Bewegung folgt die Transportklasse, adressbasiert und ohne
Geofence. Der Beleg selbst ist inzwischen anders gelöst: eine Sendung **ist ein Einkauf**
(`domain/procurement.py`), ein Frachtführer ist ein Lieferant und der Tarifvergleich der
Angebotsspiegel. Ein eigenes Versandmodul kommt darum nicht zurück; was fehlt, ist eine
Angebotszeile, die eine Anbindung füllt statt ein Mensch.

## Der Ereignis-Strom

`services/events.py` · `routers/events.py` · `schemas/event.py` · `models/event.py`

Eine append-only Outbox (`events`) als «ökonomische Wahrheit» für KI und Automatisierung.
Sie ist mitgegangen, weil sie nach dem Neuaufbau **kein einziger Schreiber mehr füllte** –
der Endpunkt lieferte einen Strom aus, in den nichts mehr floss. Die Wahrheit über das
Material steht seither im **Material-Journal** (`process_events`, ADR 007); ein zweiter
Strom daneben wäre genau die zweite Wahrheit, die dieses Projekt nicht will. Die Tabelle
bleibt vorerst in der Datenbank stehen (Historie), sie wird nur nicht mehr gelesen.

## Der Feature-Schalter

`core/features.py` · `frontend/src/lib/features.ts`

Er hielt die Entscheidung «was ist an, was ist aus» an einer Stelle und mountete für jedes
abgeschaltete Modul einen Stub, der mit `503` und einem Grund antwortete statt mit
Schweigen. Das war richtig, solange der Code **da** war und nur nicht laufen sollte.

Nachdem er gelöscht ist, schaltet der Schalter nichts mehr: es gibt nichts einzuschalten.
Ein «abgeschaltet» zu melden, wo schlicht nichts existiert, wäre eine Auskunft, die nicht
stimmt – `404` ist die richtige Antwort. Der frontend-seitige Spiegel las ohnehin niemand
(die Datei war von keiner Seite aus erreichbar), und seine Beschriftungen waren bereits
von den Backend-Beschriftungen abgewichen: ein Spiegel, den nur ein Test vergleicht.

Wer einen dieser Bereiche neu baut, schreibt seinen Router – er legt keinen Schalter um.

## Die Adress-Helfer für Etikett, Briefkopf und Bezahlung

`services/address.py`: `of_user` · `one_line` · `lines` · `same` (+ `person_name`, `_norm`)

`address.py` war die eine Übersetzung zwischen den historisch verschiedenen Spaltennamen
(`address_line1`/`postal_code` an der Person ↔ `street`+`street_nr`/`zip_code` am
Unternehmen) – gebaut für Versand-Etiketten, den PDF-Briefkopf und den Zahlungsanbieter.
Diese drei Leser sind mit ihren Bereichen gegangen; die Funktionen blieben stehen und
hatten danach **null** Aufrufer, auch keinen modulinternen.

Zwei Entscheidungen stecken darin und sind es wert, nicht neu hergeleitet zu werden:

* **`of_user` kapselt den Rückfall** «Lieferadresse, sonst Wohnadresse» (`ship_*` ≻ `*`).
  Er stand vorher an jeder Aufrufstelle einzeln ausgeschrieben – genau die Form, in der
  eine Adresse je nach Herkunft anders aussieht. Wer den Versand zurückbaut, holt die
  Funktion aus dem Tag, statt den Rückfall wieder zu verteilen.
* **`same` wertet zwei Adressen als denselben Ort** (normalisiert, ohne Sonderzeichen) –
  und **ohne echte Ortsangabe bewusst NICHT als gleich**, sonst gingen zwei leere
  Adressen als derselbe Ort durch. Daran hing die Transportklasse (ADR 005): «zwei
  interne Orte mit unterschiedlicher Adresse → Versand».

Geblieben ist, was heute wirklich jemand liest: `iso2` (Gebietskarte, Währung je
Gesellschaft), `of_company` + `has_content` (Impressum, Halter-Anschrift) und `make`.
