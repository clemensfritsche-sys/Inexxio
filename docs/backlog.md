# Backlog

Offene Themen, die bewusst **nicht** sofort umgesetzt werden. Jeder Eintrag nennt Ziel,
Vorschlag und – wichtig – was dagegen spricht bzw. noch zu entscheiden ist. Erledigtes
steht nicht hier, sondern in `docs/history/` (zuletzt `2026-10-backlog-erledigt.md`).

---

## Zwei-Deploy-Regel: vorgemerkte Drops

`user_profiles.department`, `user_profiles.job_title` – Mapping entfernt (28.10.2026), stehen in
`PENDING_DROP` (`backend/tests/test_schema_is_built_by_the_migrations.py`); der Folge-Deploy droppt
sie. Wer eine Spalte entmappt, trägt sie dort **und** hier ein; der Eintrag geht mit dem Drop.
Bewusst gemappt geblieben (Entscheid E7): `articles.safety_stock`, `min_order_qty`,
`supplier_article_number`, `user_profiles.language`, `notification_email`,
`notification_inapp`.

## Offene Befunde

Aus dem Audit vom August 2026 (`docs/history/2026-08-findings.md`, dort mit Ursache).

1. **S94 – «Noch nicht erfasst: OK.» nennt den Punkt, aber nicht das Stück.**
   `capture_types.check_values` kennt die Einzelinstanz nicht; bei 1500 gezogenen Stücken
   sucht der Mensch. In der Matrix als `open_finding` an S94 – wer es behebt, entfernt die Markierung.
2. **Zwei Fallback-Anzeigen im Auftrags-Detail** (`components/erp/order-detail.tsx`):
   `ln.article_name ?? 'Artikel'` (ein erfundenes Wort) und `…?.action ?? ''` (ein leerer
   Knopf). Heute unerreichbar; im Fehlerfall lügen sie statt zu melden (SYSTEM_LOGIC G3.6).
3. **`modules.sample_of` fällt auf «alle» zurück**, wenn die Stichprobe in einer
   gespeicherten Definition fehlt – ein dokumentierter Rückfall für Alt-Definitionen
   (SYSTEM_LOGIC §5 Punkt 2), heute unerreichbar. Stehen lassen, nicht zum Standard werden lassen.
4. **Der Verlierer einer echten Nebenläufigkeit sieht eine rohe Datenbankmeldung** (S63):
   die Exklusivität hält, aber statt des Satzes aus `_assert_as_picked` kommt ein
   `IntegrityError`. Erst angehen, wenn mehrere Personen gleichzeitig freigeben.

## Shop

**Offen.** Das Zahlungsmodul trägt einen Shop (ein Aufruf legt den Auftrag samt Beleg an,
`can` ist Auskunft und Tor auch für einen Shop-Server, Karte und QR-Rechnung sind da). Was
fehlt, liegt **vor** dem Beleg:

- ein **Verkaufspreis** am Artikel (Vorschlag: Tabelle Artikel · gültig ab · Preis ·
  Währung – ohne das Abo-Feld des Vorgängers),
- **Konditionen je Partner** als Kaskade Haus → Partner → Vorgang (leer = Stufe darüber),
- eine **Herkunft** am Auftrag (`source_reference`, eindeutig) gegen doppelte Bestellungen.

Nicht nötig: ein eigener Endpunkt, ein Warenkorb im ERP, eine Reservierung. Wortlaut und
Begründung: `docs/history/2026-09-13-konzept-beleg-shop-besitz.md` (Frage 1; Frage 2 und 3
sind umgesetzt).

## Die Zahlungsarten sind eine Konto-Entscheidung

Keine Code-Frage — unser Code fragt `automatic_payment_methods` und führt bewusst **keine
eigene Liste**. Gemessen im Sandbox-Konto (`payment_method_configurations`, 05.09.2026):

- **TWINT ist aus** (`available: false` — Stripe schaltet es frei, wenn das Konto
  aktiviert ist). Karte ist an, bezahlen funktioniert also.
- **An sind daneben** Klarna, Link, Amazon Pay, Bancontact, EPS, BLIK, MB Way, Pix,
  Satispay, Apple Pay — für ein Schweizer B2B-ERP kaum passend, und sie stehen dem
  Zahlenden alle im Formular.

Beides ist ein Schalter unter **Settings → Payments → Payment methods**.

## Die offene-Posten-Liste je Partner (und mit ihr die Sammelzahlung)

**Benannt, nicht versteckt** (PROCESS_CORE §9.15). Eine Rechnung ist *der Beleg*; zwei
Rechnungen desselben Kunden liegen damit zwingend in **verschiedenen Modulen** – meist in
verschiedenen Aufträgen. Zwei Fragen haben keinen Ort an *einem* Modul:

1. **«Was schuldet mir dieser Kunde insgesamt?»** Die Summe über alle Module ist
   **Debitorenbuchhaltung**. Die Zahlungen-Liste an Person und Gesellschaft
   (`services/payment_list`) zeigt die Zeilen, rechnet aber nicht gegeneinander auf.
2. **Eine Überweisung über mehrere Rechnungen.** Auf dem Kontoauszug steht eine Zeile; im
   ERP sind es zwei erfasste Zahlungen – eine Zeile mehr auf dem Bildschirm, **keine
   falsche Zahl**.

## Teilkorrektur ohne Ware und ein Beleg ganz ohne Ware

«Stornieren» nach der Rechnung erzeugt die Gutschrift über die **ganze** Rechnung von
selbst. Eine **Teil**korrektur (ein reiner Rechnungsfehler nach dem Versand) braucht einen
eigenen Korrekturbeleg in einem Auftrag über die betroffenen Stücke – das dokumentiert,
worauf sie sich bezieht, fühlt sich aber schief an. Es ist derselbe offene Punkt wie
**«ein Beleg ganz ohne Ware»** (Miete, Lohn, Gebühr): `assert_releasable` verlangt
mindestens eine Einzelinstanz. Fällt die Regel eines Tages, fällt sie für beide.

## Automatische Freigabe einzelner Papiere

`voucher.AUTO_RELEASE` ist leer: Auftragsbestätigung und Quittung gehen nur mit «Prüfen und
freigeben» hinaus. Wer ein Papier von selbst freigeben will, trägt es dort ein – zuerst
entscheiden, welches.
