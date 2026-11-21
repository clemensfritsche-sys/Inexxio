# Arbeitsauftrag — Der Beleg wird vollständig

> **Grundlage für die Umsetzung.** Zusammengeführt aus der Soll/Ist-Analyse
> (`beleg-pflichtangaben.md`) und den Testnotizen #902–#908.
>
> **Das eine Ziel, an dem alles gemessen wird:** *Keine Rückfragen.* Ein Beleg, der beim
> Empfänger eine Frage auslöst, kostet mehr Zeit als jedes Feld, das sie verhindert
> hätte. Umgekehrt gilt genauso: ein Feld, das nie eine Frage verhindert, ist Ballast.
>
> **Die Hausregeln gelten unverändert** — eine Sache, eine Stelle · Ableitung vor Spalte ·
> `can` ist Auskunft **und** Tor · kein `if direction ==` · Struktur vor Fläche · jede
> Regel gegen ihre Bug-Form gegengeprüft.
>
> Stand: 12.09.2026, gegen `7a3ff19`.

---

## Teil 0 · Drei Entscheidungen, die vorab getroffen sind

Der Auftrag delegiert drei Urteile. Hier stehen sie, mit Begründung — sie sind die
Grundlage für Teil 1–4 und nicht mehr offen.

### 0.1 · Auftragsbestätigung (#908) — **kein neuer Schritt, nur der richtige Name**

**Entscheidung: Es gibt keine dritte Stufe.** Die Auftragsbestätigung *ist* die Schwelle
`agreed` — derselbe Moment, aus der Sicht dessen, der bestätigt. Sie hat bereits alles,
was eine AB ausmacht: ein Datum (`agreed_on`), eine Nummer (die Auftragsnummer), die
bestätigten Positionen mit Preis und Satz (`agreed_lines`), Liefer- und Zahlungsfrist.

Eine eigene Stufe dafür wäre **genau der Fehler, der bei «Abgeschlossen» schon einmal
korrigiert wurde** (#791–#797): ein **Zustand** in einer Reihe von **Schritten** — man
tut nichts, um ihn zu erreichen.

**Was stattdessen zu tun ist:** die Stufen heissen je Richtung richtig. `stage_labels`
trägt das längst, es ist nur falsch gefüllt — beide Richtungen sagen heute «Auftrag».

| Richtung | `offer` | `agreed` |
|---|---|---|
| **Einnahme** (wir verkaufen) | **Offerte** | **Auftragsbestätigung** |
| **Ausgabe** (wir kaufen) | **Anfrage** | **Bestellung** |

Damit heisst der Beleg in jedem Zustand, was er ist — und der spätere PDF-Export ist
weiterhin *dieselbe Komponente ohne Knöpfe* (#899).

### 0.2 · Die beiden Rollen (#903) — **Leistungserbringer / Leistungsempfänger**

«Lieferant / Kunde» ist zu eng: Miete, Lohn, Gebühr, Spesen und eine Spedition haben
keinen Lieferanten. «Rechnungssteller / Rechnungsempfänger» (der Vorschlag aus der Notiz)
ist präzise für eine **Rechnung** und falsch auf einer **Offerte** — dort hat noch
niemand eine Rechnung gestellt, und derselbe Beleg trägt beide Zustände.

**Entscheidung: Leistungserbringer ↔ Leistungsempfänger.** Drei Gründe:

1. Es sind die **Begriffe des MWSTG selbst** — also die, die auf einem Schweizer Beleg
   ohnehin gelten.
2. Sie gelten für **jede** Leistung: Ware, Dienstleistung, Miete, Lohn, Transport.
3. Sie passen **wörtlich** zum Reverse-Charge-Pflichtsatz, den wir in 1.3 ergänzen:
   «Steuerschuldnerschaft des **Leistungsempfängers**». Zwei verschiedene Wörter für
   dieselbe Person auf demselben Papier wären die Rückfrage, die wir vermeiden wollen.

*Sie sind etwas sperrig — darum erklärt der Hover sie in einem Satz («wer die Leistung
erbringt und den Beleg stellt» ↔ «wer sie bezieht und bezahlt»).*

`deal.SUPPLIER` / `deal.CUSTOMER` werden entsprechend umbenannt; sie sind bereits
Konstanten an **einer** Stelle.

### 0.3 · Die Nummer im Belegkopf (#904) — **eigene Zeile, Mikro-Label «Nr.»**

«Objektnummer» ist ein Systembegriff und auf einem Beleg fehl am Platz; «Usernummer» ist
falsch, sobald die Partei ein Unternehmen ist.

**Entscheidung:** die Nummer steht als **eigene Zeile** unter dem Namen, mit dem
Mikro-Label **«Nr.»** — kurz, neutral, und im Kontext eindeutig, weil der Block darüber
bereits sagt, **wessen** Nummer es ist (Leistungserbringer ↔ -empfänger). Sie bleibt
klickbar (`ObjId`).

Kein neues Vokabular, keine Rolle im Wort verdoppelt.

---

## Teil 1 · Der Beleg wird rechtssicher

### 1.1 · UID / MWST-Nummer des Empfängers

**Heute:** `document_head` setzt sie hart auf `None`, mit der Begründung «eine UID der
Gegenpartei führt das System nicht». **Das ist falsch** — `UserProfile.uid_number`,
`vat_number` und `vat_registered` stehen seit dem Fundament da. *(Fehler aus der letzten
Runde; die Begründung im Docstring geht mit.)*

**Zu tun:** dieselbe Regel wie bei uns — MWST-Nummer vor blosser UID. Eine Zeile.
**Wächter:** ein Empfänger mit hinterlegter UID zeigt sie; die Bug-Form (hart `None`)
meldet.

### 1.2 · Der Empfänger ist eine Rechtsperson, nicht ihr Vertreter

**Heute:** `billing_of` fällt auf `people.display_name` zurück, und das ist bewusst
**person-first** («Vorname Nachname → Firma → E-Mail», #291). Im ERP richtig — man
arbeitet mit Menschen. Auf einer Rechnung falsch: Schuldner ist die *Muster AG*.

**Zu tun:** eine eigene Regel **für den Beleg**, in `services/people` **neben**
`display_name` (zwei Formen einer Regel sind in Ordnung; zwei Regeln nicht):

```
Firma
z. H. Vorname Nachname      ← nur wenn beide vorhanden
```

Ohne Firma bleibt die Person — das ist der B2C-Fall und korrekt. `display_name` bleibt
unangetastet.

### 1.3 · Der Nullsatz trägt zwei Tatbestände

**Heute:** `("0.00", "Ohne (Export · Reverse Charge)")` — ein Schrägstrich zwischen zwei
**verschiedenen** Rechtsgründen mit **verschiedenen** Pflichtsätzen. Ein Beleg, der nur
«0 %» sagt, nennt den Grund nicht, und genau den braucht der Empfänger für seine eigene
Abrechnung.

**Zu tun:** aus einer Katalogzeile mit zwei Bedeutungen werden zwei mit je einer — und
der Pflichtsatz hängt am **Satz**, nicht am Beleg:

```python
VAT_RATES = (
    ("normal",  "8.10", "Normalsatz",    None),
    ("reduced", "2.60", "Reduziert",     None),
    ("lodging", "3.80", "Beherbergung",  None),
    ("export",  "0.00", "Export",          "Steuerfreie Ausfuhrlieferung"),
    ("reverse", "0.00", "Reverse Charge",  "Steuerschuldnerschaft des Leistungsempfängers"),
)
```

Der Hinweis erscheint damit **automatisch**, sobald ein solcher Satz auf dem Beleg
vorkommt — kein `if`, kein Feld, keine zweite Stelle, die jemand vergisst.

**Die zwei Stellen, die mitziehen müssen** (benannt, damit sie nicht still brechen):
* Der **Schlüssel** ist ab jetzt die Katalogzeile, nicht die Zahl — `assert_vat`
  vergleicht heute auf den Zahlenwert, und «0.00» ist danach mehrdeutig.
* `vat_split` gruppiert nach **Katalogzeile**, nicht nach Satz — sonst fallen Export und
  Reverse Charge zu einer Zeile zusammen und der Beleg nennt nur einen der beiden Gründe.
* Eingefrorene Belege (`DealEntry.vat`) behalten ihren Wert; altes `"0.00"` wird tolerant
  als «Export» gelesen (der häufigere Fall) — und das steht als Annahme im Code.

### 1.4 · Rechtsform und Kontaktweg des Ausstellers

**Heute:** `legal_form`, `email`, `phone` stehen am Unternehmen und **nicht** im Kopf.
«Inexxio» ist nicht die Bezeichnung der Rechtsperson; und ein Beleg ohne Kontaktweg ist
genau das Dokument, das eine Rückfrage per Telefonbuch auslöst.

**Zu tun:** `legal_form` an den Namen, `email`/`phone` unter die Anschrift des
Ausstellers. Daten sind da.

---

## Teil 2 · Vollständigkeit als Modul-Eigenschaft — **der Kern dieser Runde**

> *«Wenn das Modul zu wenig Angaben hat, um seinen Prozess abzuwickeln, dann muss es
> Alarm schlagen.»*

### 2.1 · Die Regel

**Ein Modul weiss selbst, was es braucht, und sagt, was fehlt.** Kein neuer Zustand,
keine Sperre mit Schlüssel, kein `if` an einer Aufrufstelle.

**Das Vorbild steht im Haus und ist erprobt: `StepNeed`.** Der Verbrauch meldet fehlendes
Material als Zeile («Artikel · gebraucht · verfügbar · davon hier») — *«Nichtverfügbarkeit
ist KEIN Zustand: die Freigabe geht, das Modul bewegt nichts, und die Zeile sagt, woran es
liegt.»* Eine fehlende **Stammdatenangabe** ist dieselbe Aussage, nur über einen anderen
Gegenstand.

### 2.2 · Die Form

```python
class DataGap(BaseModel):
    """Eine Angabe, die dieses Modul braucht und nicht findet."""
    record_object_id: int    # wo sie hingehört – klickbar
    record_label: str        # «Inexxio AG» · «Monika Fritsche»
    field_label: str         # «MWST-Nummer» · «Anschrift» · «IBAN»
    why: str                 # ein Satz: warum dieser Beleg sie braucht
```

* **Erhoben** an **einer** Stelle: `deal.gaps(db, row, *, action)`.
* **Gerendert** von **einer** Komponente — dieselbe Anatomie wie `StepNeed`
  (Zeile · Nummer · Klartext · Klick führt zum Datensatz).
* **Durchgesetzt ohne eine neue Regel:** die Lücken speisen **`can`**. Fehlt etwas, führt
  `can` das Verb nicht → der Knopf ist **nicht da** (ein Knopf, der nie etwas tun kann,
  ist kein Angebot), und `apply` weist mit einem Satz ab, der die Sache **nennt**.
  *`can` ist Auskunft und Tor — es braucht keine zweite Prüfung daneben.*

### 2.3 · Was wann gebraucht wird — eine Tabelle, kein Code

Gestaffelt, weil eine Anfrage weniger braucht als eine Rechnung. Fehlendes blockiert
**nur die Handlung, die es wirklich braucht** — sonst stünde das Modul still, weil eine
Angabe fehlt, die erst in drei Schritten zählt.

| Handlung | Verlangt |
|---|---|
| `ask` (anfragen/anbieten) | **Wir:** Name · Rechtsform · Anschrift · Kontaktweg. **Partner:** Name · Anschrift |
| `agree` (zusagen) | alles von `ask` · **unsere MWST-Nr.**, wenn wir steuerpflichtig sind · Liefer- und Zahlungsfrist |
| `charge` (Rechnung) | alles von `agree` · **UID des Empfängers**, wenn eine Position `Reverse Charge` trägt · **IBAN**, wenn wir einziehen (`collects`) |
| Export-Positionen (`export`/`reverse`) | je Artikel: **HS-Code** · **Ursprungsland** |

*Die Tabelle ist **Daten** (`REQUIRED_FOR`), keine Bedingungskette — ein neues Feld ist
eine Zeile, und ein neues Modul deklariert seine eigene.*

### 2.4 · Wo es hingehört: am Modul, nicht am Geldvorgang

`Module.data_gaps(db, step, order)` als Rahmen-Frage mit leerer Vorgabe. Das Zahlungsmodul
beantwortet sie; jedes andere erbt das Schweigen. **Damit erbt jedes künftige Modul den
Mechanismus, ohne eine Zeile zu schreiben** — dieselbe Bauart wie `needs`, `target`,
`verifies`.

---

## Teil 3 · Aussenhandel

### 3.1 · HS-Code — die Sachfrage zuerst beantwortet

**Der HS-Code ist weltweit einheitlich — in seinen ersten sechs Stellen.**

* Das **Harmonisierte System** (HS) ist ein Abkommen der **Weltzollorganisation (WCO)**;
  rund **200 Länder** wenden es an, es deckt über 98 % des Welthandels ab.
* **Die ersten 6 Stellen sind identisch** — in der Schweiz, in Deutschland, in den USA,
  in China. Sie sind *die* gemeinsame Sprache und genau das, was auf eine Handelsrechnung
  gehört.
* **Darüber hinaus ist es national**: die EU hängt zwei Stellen an (Kombinierte
  Nomenklatur, 8-stellig) und für Zollsätze nochmals zwei (TARIC, 10-stellig); die
  Schweiz führt einen **8-stelligen** Zolltarif (Tares); die USA 10 Stellen (HTSUS).
* Alle fünf Jahre revidiert die WCO das HS (zuletzt 2022, nächste Fassung 2028) — eine
  Nummer ist also **datierbar**, aber nicht länderabhängig.

**Folgerung — und sie bestätigt den Vorschlag aus der Notiz:** wir speichern **die
6-stellige HS-Nummer** und erlauben bis zu 8 Stellen (wer den Schweizer Tarif kennt,
trägt ihn ein; das Importland hängt seine eigene Verlängerung ohnehin selbst an). Sie
steht **standardmässig auf jedem Beleg**, nicht nur im Export: sie kostet eine Zeile und
verhindert genau die Rückfrage, um die es geht. Wo sie fehlt, ist das im Inland kein
Fehler — sie fehlt eben.

**Umsetzung ohne neue Mechanik:** `articles.hs_code` + `articles.origin_country`, dazu
**zwei Zeilen in `SPEC_FIELDS`**. Die Spezifikation **reist bereits mit dem Beleg** —
damit stehen beide auf Offerte *und* Rechnung, ohne dass der Geldvorgang davon weiss.

*Ursprungsland ist **nicht** aus dem HS-Code ableitbar und auch nicht das Versandland —
es ist eine eigene Angabe (Länderliste, kein Freitext).*

### 3.2 · Incoterms 2020 — vollständig, mit Erklärung im Hover

**Wo sie hingehören:** ein Incoterm ist eine **Vereinbarung** über Kosten und Risiko
zwischen zwei Parteien, kein physischer Vorgang. Also an den **Vorgang**
(`deals.incoterm` + `deals.incoterm_place`), eingefroren mit der Zusage wie die Währung —
nicht an das Bewegen-Modul, das nur *ausführt*, was hier vereinbart wurde.

**Ein Katalog, kein Freitext** — dieselbe Begründung wie bei Währung und Steuersatz.
**Der benannte Ort ist Pflicht**, sobald eine Klausel gewählt ist: «FCA» allein ist keine
Vereinbarung, «FCA Rorschach» ist eine.

**Alle elf Klauseln, mit einer DAU-sicheren Erklärung im Hover** (der Grund für die
Notiz: genau hier entstehen die Fragen):

| Klausel | Name | Erklärung im Hover |
|---|---|---|
| **EXW** | Ab Werk | Der Käufer holt ab. Ab unserer Rampe trägt er Kosten **und** Risiko. |
| **FCA** | Frei Frachtführer | Wir übergeben dem Transporteur des Käufers. Ab der Übergabe trägt er Kosten und Risiko. |
| **CPT** | Frachtfrei | **Wir** zahlen den Transport bis zum Zielort — das **Risiko** geht aber schon bei der Übergabe an den ersten Frachtführer über. |
| **CIP** | Frachtfrei versichert | Wie CPT, und wir zahlen zusätzlich die Transportversicherung. |
| **DAP** | Geliefert benannter Ort | Wir liefern bis zum Ort. Abgeladen wird vom Käufer, den Einfuhrzoll zahlt er. |
| **DPU** | Geliefert entladen | Wie DAP, und wir laden zusätzlich ab. |
| **DDP** | Geliefert verzollt | Wir tragen alles bis zur Tür — inklusive Einfuhrzoll und Einfuhrsteuer. |
| **FAS** | Frei Längsseite Schiff | *Nur See-/Binnenschiff.* Wir stellen die Ware am Kai neben das Schiff. |
| **FOB** | Frei an Bord | *Nur See-/Binnenschiff.* Wir bringen die Ware an Bord; ab da trägt der Käufer. |
| **CFR** | Kosten und Fracht | *Nur See-/Binnenschiff.* Wir zahlen die Seefracht bis zum Zielhafen — das Risiko geht an Bord über. |
| **CIF** | Kosten, Versicherung, Fracht | Wie CFR, zusätzlich mit Versicherung. |

*Die vier See-Klauseln tragen ihren Hinweis im Text — sie für Luftfracht oder Camion zu
wählen ist der häufigste Fehler überhaupt.*

---

## Teil 4 · Testnotizen #902–#907

### #902 · Die Kopfzeile «Angebot · Offen 0.00 CHF» entfällt

**Zu tun:** die Zeile wird **vollständig entfernt**. Zwei Gründe, beide tragen:
* Die **Belegart** steht ab jetzt in den Rollen darunter (Teil 0.2) und im Titel des
  Vorgangs — dreimal dasselbe Wort ist Fläche.
* Der **offene Betrag** sagt auf einer Offerte nichts: es ist nichts gefordert, also ist
  er null, und «Offen 0.00» liest sich wie «bezahlt».

**Aber die Information geht nicht verloren** — *sie war die Antwort auf «was muss man in
unter einer Sekunde finden?»*. Sie steht weiterhin **genau einmal**, dort, wo sie etwas
sagt: an der **Rechnung** (Punkt + Wort, #875). Ohne Rechnung gibt es nichts Offenes.

### #903 · Rollennamen → siehe **Teil 0.2**
### #904 · Die Nummer im Kopf → siehe **Teil 0.3**

### #905 · Die eigene Organisation — automatisch vorgewählt, manuell änderbar

**Zwei Funktionen, und die erste ist eine Datenlücke:** `UserProfile` hat **keine**
Verbindung zu einer Gesellschaft. Ohne sie kann nichts vorgewählt werden.

**Automatisch:**
* Neue Spalte `UserProfile.company_object_id` → Gesellschaft (`company_settings`).
* **Wer Mitarbeiter wird, braucht eine Organisation**: die Rollenänderung auf
  `employee`/`admin` verlangt sie — durchgesetzt im Dienst (`people.apply_*`), nicht nur
  im Formular. *Das ist zugleich eine `DataGap` aus Teil 2: ohne Zuordnung kann der
  Auftraggeber nicht anbieten.*
* Der Geldvorgang friert bei der Anlage die Gesellschaft **des handelnden Mitarbeiters**
  ein: `deals.issuer_company_id`. Fällt sie weg, gilt weiterhin der Betreiber —
  `sites.find_operator` bleibt der Rückfall, nicht die Regel.

**Manuell:** solange `currency` änderbar ist (Stufe `offer`, dieselbe Tabelle `ACTIONS`),
ist auch die Gesellschaft änderbar. **Visuell minimal-invasiv:** ein kleines
Stift-Symbol am Block des Leistungserbringers, das ein `ObjectSelect` über die angelegten
Gesellschaften öffnet — dasselbe Bauteil wie jede Referenz im Haus. Ab der Zusage fehlt
das Symbol (kein ausgegrauter Knopf).

### #906 · Die Währung steht bei den Preisen

> *«Informationen dort anpassbar machen, wo man sie sucht.»*

**Zu tun:** das Währungs-Auswahlfeld wandert aus dem Abschnitt «Bedingungen» **in den
Kopf der Positionsspalte «Preis netto»**. Der eigene Abschnitt entfällt.

* **Geschlossen minimal:** nur der Code («CHF»), als leises Bedienelement am Spaltenkopf —
  der Platz ist knapp, und die Karte ist auch auf einem breiten Schirm ~460 px.
* **Offen vollständig:** «CHF · Schweizer Franken» (die Liste trägt den Namen bereits).
* **Eine Währung je Vorgang** — das ist gesetzt (§9.12) und muss **sichtbar** sein: der
  Hover sagt in einem Satz, dass die Wahl für **alle** Positionen gilt. Sie am Spaltenkopf
  statt an jeder Zeile zu zeigen, sagt genau das schon durch ihre Position.

### #907 · Fristen stehen **einmal** — und «Bedingungen» sieht aus wie der Beleg

**Teil 1 — die Doppelung:** Zahlungs- und Lieferfrist stehen heute in «Bedingungen`
**und** an der Angebotszeile. Zwei unabhängige Eingaben für dieselbe Vereinbarung.

**Die Auflösung ist die bestehende Regel, nicht eine neue:** `Direction.quoted_by` sagt,
**wer den Preis nennt** — und wer den Preis nennt, nennt auch die Fristen.

| | Bedingungen | Angebotszeile des Partners |
|---|---|---|
| **Einnahme** (wir nennen den Preis) | **Eingabe** — hier wird es festgelegt | **nur Annehmen / Ablehnen** |
| **Ausgabe** (er nennt den Preis) | **Auskunft**, gelesen aus der gewählten Zeile | **Eingabe** — das ist sein Angebot |

Damit gibt es je Richtung **genau eine** Schreibstelle. Kein `if` in der Oberfläche: sie
fragt `quoted_by`, wie sie es beim Betrag schon tut.

**Teil 2 — die Gestalt:** «Bedingungen» soll aussehen **wie der fertige Beleg**, damit
man intuitiv erkennt, was man ändert. Also kein Formular-Raster, sondern die
**Beleg-Fusszeile**, in der die Werte selbst die Bedienelemente sind:

```
Zahlungsbedingungen   30 Tage netto, zahlbar bis 12.10.2026
Lieferung             10 Arbeitstage · FCA Rorschach (Incoterms 2020)
Währung               CHF
```

Ein Wert, den man anklickt, öffnet seine Wahl an Ort und Stelle. **Was man sieht, ist,
was gedruckt wird.**

---

## Teil 5 · Reihenfolge und Abnahme

**Reihenfolge** (jede Stufe für sich lauffähig und deploybar):

1. **Rollen und Wörter** — 0.2 · 0.3 · 0.1 · #902. Kein Datenmodell, sofort sichtbar.
2. **Der Kopf wird vollständig** — 1.1 · 1.2 · 1.4.
3. **Die Steuer wird eindeutig** — 1.3 (berührt Katalog, `assert_vat`, `vat_split`).
4. **Vollständigkeit als Modul-Eigenschaft** — Teil 2. *Der Kern; baut auf 1–3 auf, weil
   erst dann feststeht, welche Felder es überhaupt gibt.*
5. **Die Oberfläche folgt dem Beleg** — #906 · #907.
6. **Die eigene Organisation** — #905 (Migration).
7. **Aussenhandel** — 3.1 · 3.2 (Migrationen).

**Abnahme — dieselben Massstäbe wie in jeder Runde:**

* Jeder neue Wächter **gegen seine Bug-Form gegengeprüft**; ein Wächter, der nie
  anschlägt, ist von einem kaputten nicht zu unterscheiden.
* Suite grün gegen die **gewachsene Datenbank** *und* gegen ein Schema, das **nur aus den
  Migrationen** kommt.
* Jede Migration: von null · idempotent · downgrade · über das Lifespan-Netz — und
  **Index- bzw. Typänderungen gehören ins Netz** (die Lehre aus #778 und aus Migration
  128: was nur in einer Migration steht, erreicht dev nie).
* Gemessen in Chromium an den **echten** Komponenten (Karte im `ModuleShell`):
  1440 · 1280 · 1024 · 834 · 375 · 320 px, **0 px** waagrechter Überlauf — über alle
  Beleg-Zustände, inkl. beider Richtungen und der Sicht der Gegenpartei. Die Messung
  selbst gegen ihre eigene Bug-Form gegenprüfen.
* Die Gegenpartei sieht **0** fremde Preise und **0** Angaben, die ihr nicht gehören.

**Ausdrücklich nicht in dieser Runde** (Begründung in `beleg-pflichtangaben.md` §3):
eigene Offertnummern-Serie · Skonto · Proforma · VIES-Validierung · Packliste und
Gewichte · englische Belege.
