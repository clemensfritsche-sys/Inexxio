# Beleg, Shop, Besitz — drei Fragen, einfach erklärt

> **Was ist das hier?** Ein Konzept, kein Bauprotokoll. **Nichts davon ist umgesetzt.**
> Stand: 13.09.2026, gemessen am Code auf `develop` (Commit `9598091`).
>
> **Für wen?** Für jeden, der mitreden will – ohne Vorwissen. Fachbegriffe stehen drin,
> aber immer mit Erklärung daneben.

Drei Fragen standen im Raum:

1. Ist das Zahlungsmodul bereit für einen Online-Shop?
2. Der Bereich «Rechnung & Zahlung» fühlt sich wirr an – wie baut man ihn besser?
3. Wie merkt sich das System, ob ein Stück bei uns ist oder beim Kunden?

Die dritte ist die wichtigste, und die Antwort darauf ist wahrscheinlich überraschend.

---

## Kurz vorab: drei Wörter, die immer wieder vorkommen

| Wort | Was es heisst, in einem Satz |
|---|---|
| **Einzelinstanz** | Ein einzelnes physisches Stück. Eine Schraube. Das kleinste Ding, mit dem das System arbeitet. |
| **Auftrag** | Ein Ablauf mit Stationen. Stücke wandern von Station zu Station durch. |
| **Modul** | Eine Station in diesem Ablauf. «Bewegen», «Zahlung», «Verbrauch» sind Module. |

Und eine Regel, die überall gilt:

> **Jede Angabe hat genau einen Ort.**
> Steht dieselbe Sache an zwei Stellen, geraten die beiden früher oder später
> in Widerspruch – und dann weiss niemand, welche gilt.

---

# Frage 1 · Ist das Modul bereit für den Shop?

## Die kurze Antwort

**Das Zahlungsmodul selbst ist bereit. Was fehlt, liegt eine Ebene davor.**

Stell dir das Zahlungsmodul wie einen Kellner vor. Er kann bestellen, kassieren und
Rechnungen schreiben – alles perfekt. Aber es gibt **keine Speisekarte**: nirgends steht,
was etwas kostet und welche Konditionen für welchen Kunden gelten.

Der Shop müsste sich diese Angaben also selbst ausdenken. Und dann hätten wir zwei
Wahrheiten: eine im Shop, eine im ERP. Genau das soll nicht passieren.

## Was heute schon funktioniert

* **Eine Shop-Bestellung ist ein einziger Aufruf.** Der Auftrag entsteht als Ganzes
  (Material, Ablauf, Stückauswahl in einem Zug), und der Zahlungs-Beleg entsteht
  automatisch mit.
* **Der Shop kann dieselben Befehle geben wie ein Mensch im ERP.** Der Ablauf
  «Preis setzen → anbieten → Zusage → Rechnung → bezahlen» ist eine Kette von Befehlen.
  Ein Shop-Server kann sie genauso schicken. **Kein neuer Programmierschnittstellen-Punkt
  nötig.**
* **Was erlaubt ist, sagt der Server – nicht der Shop.** Es gibt eine Liste namens `can`
  («was darf dieser Betrachter jetzt tun?»). Sie steuert die Knöpfe in der Oberfläche
  **und** weist unerlaubte Befehle ab. Der Shop bekommt genau dieselbe Antwort. Also kann
  er nichts tun, was ein Mensch nicht auch dürfte.
* **Verkaufen, was es noch nicht gibt, geht schon.** Bestellt jemand etwas, das erst
  gefertigt wird, entsteht ein Auftrag mit der Herkunft «Neu» – die Stücke werden bei der
  Freigabe angelegt. Kein neues Konzept nötig.
* **Bezahlen per Karte ist verdrahtet** (Stripe, Bezahlformular im ERP), ebenso
  Mehrwertsteuer, Währungen, Belegkopf und die Schweizer QR-Rechnung.

## Was fehlt — drei Lücken, alle *vor* dem Beleg

### Lücke 1: Es gibt keinen Verkaufspreis

Heute tippt ein Mensch den Preis in den Beleg. Am Artikel selbst steht nur der
**Einkaufspreis** («was hat es uns gekostet»), und der ist nicht änderbar.

*Warum das ein Problem ist:* Der Shop braucht einen Preis, bevor jemand bestellt.
Ohne Preis am Artikel müsste der Shop eine eigene Preisliste führen.

### Lücke 2: Es gibt keine Konditionen je Kunde

«Konditionen» heisst hier: Zahlungsfrist (in wie vielen Tagen ist zu zahlen),
Lieferfrist, Lieferbedingung. Heute wählt man sie **je Vorgang** neu aus. Nirgends steht:
*«Kunde Müller AG hat 30 Tage netto.»*

*Warum das ein Problem ist:* Der Shop müsste die Werte mitschicken – und würde damit
unsere Konditionen bestimmen. Falsch herum.

### Lücke 3: Der Auftrag weiss nicht, woher er kommt

Es gibt kein Feld für «das ist Shop-Bestellung Nr. 4711».

*Warum das ein Problem ist:* Bricht die Verbindung im falschen Moment ab, schickt der Shop
die Bestellung nochmal – und es entstehen **zwei** Aufträge für **eine** Bestellung.

## Der Vorschlag: eine Kaskade

«Kaskade» ist nur ein Wort für **Wasserfall**: Werte fliessen von oben nach unten, und
jede Stufe darf die darüber überschreiben.

```
   HAUS          Standard-Zahlungsfrist, Standard-Lieferbedingung, Währung
     │           (steht beim Betreiber-Unternehmen)
     │  wird überschrieben von
     ▼
   PARTNER       seine Frist, seine Bedingung, sein Preis
     │           (steht beim Kunden / Lieferanten)
     │  wird überschrieben von
     ▼
   VORGANG       was in diesem einen Fall gilt
                 (steht am Beleg, wie heute frei änderbar)
```

**Jede Stufe ist freiwillig. Leer heisst: es gilt die Stufe darüber.**

Damit ist der Shop nur noch ein **Leser**: er fragt ab, was gilt, und bekommt dieselbe
Antwort wie ein Mitarbeiter, der den Auftrag im ERP anlegt. Und der einzelne Vorgang
bleibt trotzdem frei änderbar – so wie überall im System gilt:
**vorgeschlagen, nicht erzwungen.**

### Was dafür konkret gebaut werden müsste

| Was | Wie |
|---|---|
| Verkaufspreis | Eine Tabelle `article_prices`: Artikel · gültig ab · Preis · Währung. Mehr nicht. |
| Konditionen | Je ein paar Felder am Unternehmen und am Benutzer. |
| Herkunft | Eine Spalte `source_reference` am Auftrag, die zweimal denselben Wert nicht zulässt. |

*Zur Preistabelle: die gab es im alten System schon einmal – dort mit einem Zusatzfeld für
Abo-Modelle, aus dem viel Komplexität entstand. Ohne dieses Feld ist sie eine Zahl mit
einem Datum, sonst nichts.*

## Was der Shop ausdrücklich **nicht** braucht

* **Keinen eigenen Schnittstellen-Punkt.** Er nutzt, was da ist.
* **Kein Warenkorb-Modell im ERP.** Ein Warenkorb lebt im Browser, bis jemand bestellt.
* **Keine Reservierung.** Das System reserviert grundsätzlich nichts: die Freigabe eines
  Auftrags **ist** die Prüfung, ob genug da ist. Sind die Stücke im selben Moment weg,
  sagt das System es – wie immer.

---

# Frage 2 · Rechnung & Zahlung neu bauen

> **Stand: gebaut** (September 2026). Die drei Regeln unten sind umgesetzt – zwei Fächer,
> genau eine Handlung, ein Schieber für den Weg zum Geld –, dazu die beiden
> Wortkorrekturen. **Nicht gebaut und ausdrücklich offen**: die *Automatisierung* und die
> *Zustellung* (die beiden letzten Abschnitte dieser Frage). Details in `PROCESS_CORE.md`
> §9.15i.

## Warum es sich wirr anfühlt — vier Gründe, am Code nachgezählt

### 1. Sechs Knöpfe, die gleich aussehen, aber drei verschiedene Dinge tun

An einer Rechnung stehen heute bis zu sechs Knöpfe nebeneinander, alle in derselben Form:

* **«Rechnung erfassen»** → es entsteht ein Beleg. Eine echte Buchung.
* **«Stornieren»** → eine Korrektur.
* **«Überweisen»** → **überhaupt keine Buchung.** Es zeigt nur IBAN und QR-Code an.

Drei völlig verschiedene Bedeutungen, ein Aussehen.

### 2. Zwei Rollen in einer Zeile

«Rechnung erfassen» ist **unsere** Handlung. «Jetzt bezahlen» ist die Handlung des
**Kunden**. Beide stehen nebeneinander – jeder sieht also Knöpfe, die ihm gar nicht
gehören.

### 3. Ein Wort für zwei verschiedene Vorgänge

* Bei einer **Einnahme** *stellen* wir eine Rechnung. Sie geht hinaus.
* Bei einer **Ausgabe** *schreiben wir ab*, was der Lieferant uns geschickt hat.

Beides heisst heute «Rechnung erfassen».

### 4. Kein Fortschritt sichtbar

Beim Angebot und bei der Zusage sieht man, wo man steht (Punkt + Wort). Bei
«Rechnung & Zahlung» nicht – obwohl es dort drei klare Zustände gibt:
*nichts gefordert → gefordert → bezahlt.*

## Der Umbau: drei Regeln

### Regel 1 — Zwei Fächer statt sechs Knöpfe

Es sind eigentlich nur **zwei Fragen**:

| Fach | Frage | Wem gehört es |
|---|---|---|
| **FORDERN** | Was schuldet uns jemand? | uns (Rechnung stellen, stornieren, gutschreiben) |
| **BEGLEICHEN** | Wie kommt das Geld hierher? | dem Zahlenden (Karte, Überweisung, bar) |

Dazwischen steht die Zeile **«Offen»** – sie verbindet die beiden.

Wer welches Fach bedienen darf, weiss das System schon (die `can`-Liste). Es wird heute
bloss nicht dargestellt.

### Regel 2 — Genau eine Handlung bringt weiter

Ganz unten, breit, farbig – **ein** Knopf. Was auf ihm steht, sagt der Server:

```
Rechnung stellen   →   Zahlung erfassen   →   (nichts mehr)
```

Alles andere sind **Korrekturen** und stehen klein bei der Zeile, die sie korrigieren.
Nie im gleichen Rang wie der Hauptknopf.

### Regel 3 — Der Weg zum Geld ist eine Wahl, kein Verb

Bar · Überweisung · Karte sind **drei Antworten auf eine Frage**. Also ein Schieber mit
drei Feldern, nicht drei Knöpfe.

Was dahinter passiert, ist verschieden (buchen ↔ Angaben zeigen ↔ Zahlformular öffnen) –
die **Frage** ist dieselbe.

## Wie es aussieht

### Heute

```
┌─ RECHNUNG & ZAHLUNG ─────────────────────────────┐
│ ● 100000801-1     fällig in 30 T.   1'284.50 CHF │
│ Offen                                            │
│ [Stornieren] [Zahlung erfassen] [Überweisen]     │
│ [Jetzt bezahlen]                                 │
│     Zahlung                          −500.00 CHF │
│     [Korrigieren]                                │
│ [Rechnung erfassen]                              │
│ ──────────────────────────────────────────────── │
│ OFFEN                                784.50 CHF  │
└──────────────────────────────────────────────────┘
```

Sechs Knöpfe, gleiche Form, verschiedene Bedeutung. Fortschritt: nirgends.

### Vorschlag

```
┌──────────────────────────────────────────────────┐
│ ● FORDERN                                        │
│   Rechnung 100000801-1              1'284.50 CHF │
│   6.9.2026 · Leistung 3.9. · fällig in 30 Tagen  │
│   [Stornieren]                                   │
│                                                  │
│ ● BEGLEICHEN                                     │
│   ( Bar │ ▸Überweisung◂ │ Karte )                │
│   RF18 5390 0754 7034                            │
│   Zahlung 6.9.                       −500.00 CHF │
│ ──────────────────────────────────────────────── │
│ ● Offen                              784.50 CHF  │
│                                                  │
│ ┃          Zahlung erfassen                    ┃ │
└──────────────────────────────────────────────────┘
```

Zwei Fächer. Ein Punkt je Fach zeigt, wo man steht. Eine grosse Handlung. Korrekturen
klein und bei ihrer Zeile.

## Zwei Wortkorrekturen, die sich aus der Sache ergeben

* **«Rechnung stellen»** (bei einer Einnahme) ↔ **«Rechnung erfassen»** (bei einer
  Ausgabe). Kein Geschmack: im einen Fall entsteht der Beleg hier, im anderen schreiben
  wir einen fremden ab.
* Die beiden Fächer bekommen denselben Fortschritts-Punkt wie alle anderen Abschnitte.

## User Stories — wer macht was, Schritt für Schritt

> «User Story» heisst nur: *wer will was, und warum.* Danach die Klickfolge.

**① Mitarbeiter, Normalfall**
*Ich habe geliefert und will Geld sehen, ohne über Reihenfolgen nachzudenken.*
→ `Rechnung stellen` → Betrag, Fälligkeit, Leistungsdatum und Nummer stehen schon da
→ `Buchen`.
Zwei Klicks. Der Rest ist vorausgefüllt.

**② Kunde bezahlt selbst mit Karte**
*Ich sehe, was ich schulde, und bezahle sofort.*
→ Fach «Begleichen» → `Karte` → Zahlformular im ERP → die Zeile erscheint, sobald der
Zahlungsdienst meldet.
Den Storno-Knopf sieht er gar nicht – der gehört uns.

**③ Kunde überweist**
*Ich will die Angaben für mein E-Banking, nicht ein Formular.*
→ `Überweisung` → IBAN, Referenznummer, QR-Rechnung.
Kein Knopf, der nach Buchung aussieht: das ist eine **Auskunft**.

**④ Mitarbeiter, Bargeld**
*Der Kunde hat bar bezahlt, ich schreibe es auf.*
→ `Bar` → `Zahlung erfassen` → Betrag ist mit dem offenen Rest vorbelegt.

**⑤ Die Rechnung war falsch, noch nichts bezahlt**
→ `Stornieren` → es entsteht eine Gegenbuchung mit eigener Nummer → `Rechnung stellen`.
*Es gibt keinen Löschweg. Eine Rechnungsnummer ist vergeben, ein Beleg ist draussen – wer
die Zeile verschwinden lässt, behauptet, sie sei nie passiert.*

**⑥ Die Rechnung war richtig, aber der Kunde bekommt etwas zurück**
→ `Gutschrift` → der offene Betrag wird negativ → `Erstattung`.
Derselbe Knopf wie beim Storno; wie er heisst, entscheidet die Zahl (bezahlt ↔ unbezahlt).

**⑦ Lieferantenrechnung (Ausgabe)**
→ `Rechnung erfassen` (seine Nummer, sein Betrag, sein Steuersatz) → `Überweisung`
→ `Zahlung erfassen`.

## Automatisierung — ohne Flexibilität zu verlieren

> **Nicht gebaut.** Bewusst zurückgestellt – hier steht, was möglich wäre.

Die Regel des Hauses lautet: **das System schlägt vor, der Mensch entscheidet.**
Automatik heisst hier *vorausfüllen*, nie *selbst ausführen*.

| Was | Stand | Kostet an Flexibilität |
|---|---|---|
| Betrag, Fälligkeit, Leistungsdatum, Nummer, Steueraufteilung | **schon gebaut** | nichts – alles überschreibbar |
| Konditionen aus der Kaskade (Frage 1) | Vorschlag | nichts – leer heisst «Stufe darüber» |
| **Zahlungseingang aus der Bankdatei** (camt.053) | Vorschlag | **nichts** – siehe unten |
| Mahnliste | Vorschlag | nichts, *solange es eine Liste bleibt* |
| Rechnung automatisch stellen | **bewusst nicht** | viel – siehe unten |

**Der grösste Hebel ist die Bankdatei.** Jede Bank liefert die Kontobewegungen als Datei
(Format `camt.053`, ein Schweizer/EU-Standard). Auf unserer QR-Rechnung steht bereits eine
eindeutige Referenznummer, und die kommt mit der Zahlung zurück. Das System kann also
zuordnen, ohne zu raten – und es bucht dieselbe Zeile nie zweimal, weil es die Referenz
kennt. **Kein Abtippen mehr, und keine einzige Entscheidung wird jemandem abgenommen.**

**Warum die Rechnung nicht automatisch entsteht:** *Wann* gefordert wird, ist eine
Entscheidung – Anzahlung, Teillieferung, Kulanz. Eine Automatik müsste eine davon
festlegen und wäre bei allen anderen falsch.

## Eine Lücke, die benannt gehört: die Zustellung

> **Nicht gebaut.** Bewusst zurückgestellt – hier steht, was fehlt.

Eine Rechnung, die wir stellen, muss beim Empfänger **ankommen**. Heute sieht er sie in
seinem Zugang zum ERP. Ein PDF oder eine E-Mail gibt es nicht (E-Mail ist im System
nirgends angeschlossen).

Das ist keine Modellfrage, sondern ein fehlender Kanal – ändert am Vorschlag oben nichts,
darf aber nicht unerwähnt bleiben.

---

# Frage 3 · Der Status «Verkauft»

## Die kurze Antwort

**Es fühlt sich falsch an, weil es falsch ist.**

«Verkauft» ist keine Antwort auf die Frage *«in welchem Zustand ist das Stück?»*, sondern
auf *«wem gehört es?»*. Das sind **zwei verschiedene Fragen**. Ein einziges Feld, das
beide beantworten soll, wird bei der ersten Kombination falsch – und diese Kombination
ist genau der Konzern-Fall, den du beschrieben hast.

## Der Beweis in einer Tabelle

Neun ganz normale Situationen, und drei Spalten:

| Situation | Zustand | Wo liegt es? | Wem gehört es? |
|---|---|---|---|
| Im Regal | Freigegeben | Regal B | uns |
| In Arbeit | Im Prozess | Werkbank 5 | uns |
| **Verkauft, noch nicht abgeholt** | Freigegeben | **Regal B** | **Kunde** |
| Verkauft und geliefert | Freigegeben | – | Kunde |
| **Konsignation beim Kunden** | Freigegeben | **Kunde** | **uns** |
| Muster / Leihgerät | Freigegeben | Kunde | uns |
| An Tochtergesellschaft verkauft | Freigegeben | Werk Süd | Tochter |
| Gesperrt | Gesperrt | Regal B | uns |
| Verschrottet | Verschrottet | – | – |

> **Konsignation** heisst: unsere Ware steht beim Kunden im Lager, gehört aber noch uns.
> Bezahlt wird erst, wenn er sie verbraucht. Ganz normal im Maschinenbau.

**Schau dir die beiden fett markierten Zeilen an.** Sie sind exakt vertauscht:

* einmal **bei uns**, aber **dem Kunden gehörend**
* einmal **beim Kunden**, aber **uns gehörend**

Ein einziger Status kann die beiden nicht unterscheiden. Egal, wie er heisst. Egal, wie
viele man hinzufügt.

## Die Lösung: eine dritte Achse

Das System hat diese Entscheidung schon einmal getroffen – **beim Ort**.

Der Ort eines Stücks ist kein Status, sondern ein **Zeiger**: eine Spalte, in der die
Nummer des Halters steht (Regal, Behälter, LKW, Person, Unternehmen). Er ändert nie den
Status. Und genau deshalb muss **keine andere Regel im System vom Bewegen-Modul wissen**.

*Der erste Versuch damals hatte den Ort als Zustand mit Mengen gebaut und musste
zurückgerollt werden.*

Also machen wir es mit dem Besitz genauso:

```
┌──────────────────────────────────────────────────────────┐
│  Eine Einzelinstanz hat DREI unabhängige Angaben:        │
│                                                          │
│    Zustand   →  Freigegeben · Im Prozess · Gesperrt …    │
│    Ort       →  place_object_id   (wo liegt es)          │
│    Besitz    →  owner_object_id   (wem gehört es)  ← NEU │
│                                                          │
│  Leer beim Besitz heisst: es gehört uns.                 │
└──────────────────────────────────────────────────────────┘
```

**Eine Spalte. Kein Typfeld daneben** – Objektnummern sind im ganzen System eindeutig, der
Typ ergibt sich daraus.

## Was diese eine Spalte alles löst

**Der Konzern-Fall braucht keine Sonderregel.**
Die Tochtergesellschaft ist ein Unternehmen im ERP, also eine gültige Objektnummer.
«Verkauft **und** trotzdem verfügbar» ist kein Widerspruch mehr, sondern zwei Werte in
zwei Spalten. Und «gehört zum Konzern» braucht keine neue Liste – **alle Unternehmen in
der Tabelle `company_settings` sind wir.**

**Die Kettenregel bleibt heil.**
Die Kettenregel prüft: passt der Zustand, den ein Modul erwartet, zu dem, was davor
herauskommt? Ein Besitzwechsel ist **kein** Zustandswechsel. Also bleibt jedes Modul ein
Durchläufer, es braucht kein Modul, das den Ablauf beendet, und hinter dem Verkauf darf
noch etwas kommen: Versand, Endprüfung, Zahlung.

**Kein neues Modul, kein neuer Status.**
Der Status `Verkauft` bleibt, was er seit der Löschung des «Ausliefern»-Moduls ist: ein
Wort in der Geschichte alter Stücke, das niemand mehr neu schreibt.

**Der Bestand wird richtiger, nicht komplizierter.**
Heute heisst «zählt zum Bestand»: *liegt im Regal und ist nicht endgültig weg.*
Neu: *… und gehört uns.* Eine Zeile in derselben Rechnung.

**Und du siehst trotzdem «Verkauft».**
Die Bestandsleiste bekommt ein Segment «Bei Kunden», abgeleitet aus dem Besitz. Du siehst
also genau das, was du sehen wolltest – es steht nur nicht im Statusfeld.

## Wer setzt den Besitz? Nicht das Zahlungsmodul.

Das ist der zweite wichtige Punkt.

Rechtlich (Schweiz, ZGB Art. 714) geht das Eigentum an einer beweglichen Sache mit der
**Übergabe** über – **nicht** mit dem Vertrag und **nicht** mit der Zahlung.

Und die Übergabe ist im System bereits ein Modul: **Bewegen**, mit einem Ziel.

Also bekommt «Bewegen» **eine** neue Angabe:

> **Eigentum geht über: ja / nein**
> Vorausgewählt aus dem Ziel: fremde Partei → ja. Eigenes Regal, eigene Gesellschaft,
> eigener Mitarbeiter → nein. **Überschreibbar.**

Konsignation ist damit: Ziel = Kunde, Eigentum geht über = **nein**. Ein Feld, ein
Vorschlagswert, kein Regelwerk.

**Und Ware und Geld bleiben getrennt** – wie überall in diesem System. «Verkauft, aber nie
geliefert» und «geliefert, aber nie bezahlt» sind beide abbildbar, ohne einen einzigen
Sonderfall.

## Was ist mit Rückgaben?

Ein ganz gewöhnlicher Auftrag greift das Stück. **Das Greifen IST die Rücknahme** –
dieselbe Regel, die schon beim Entsperren und beim Ausbauen gilt.

Zwei kleine Folgen:

* Die automatische Vorauswahl schlägt fremdes Material nicht vor (dieselbe Frage
  *«liegt es im Regal?»* fragt zusätzlich den Besitz).
* Greifbar bleibt es trotzdem. Weil der Zustand `Freigegeben` ist, gilt eine Retoure heute
  nicht als dokumentierte Abweichung – dafür sollte die Regel um «gehörte jemand anderem»
  erweitert werden. Eine Zeile, und der Nachweis stimmt wieder.

## Der Preis, ehrlich

**Was es kostet:** eine Spalte, eine Migration, ein Feld am Bewegen-Modul, eine Zeile in
der Bestandsrechnung, eine Zeile bei der Abweichungs-Erkennung. Das ist alles.

**Was es nicht kann:**

* Teileigentum und Miteigentums-Anteile (halb uns, halb dem Kunden).
* Eigentumsvorbehalt mit Registereintrag (ZGB Art. 715) – in der Schweiz sehr selten.

Beides wäre ein eigenes Modell, keine Erweiterung dieser Spalte. Lieber benannt als
verschwiegen.

**Was NICHT dazukommen darf:** ein zweites Feld «Besitzer-Typ» daneben. Die Nummer ist
eindeutig, der Typ ist ableitbar – das ist die Lehre aus einem früheren Fehler beim Ort.

---

# Was zuerst?

| Schritt | Warum jetzt | Datenbank-Änderung |
|---|---|---|
| **1 · Rechnung & Zahlung umbauen** | Nur Oberfläche plus zwei Wörter im Fachkern. Sofort spürbar, kein Risiko an den Daten. | nein |
| **2 · Besitz-Achse** | Voraussetzung für einen ehrlichen Bestand – ohne sie kann ein Shop nicht sagen, was verfügbar ist. | ja, eine |
| **3 · Kaskade + Verkaufspreis** | Das Fundament, aus dem der Shop liest. | ja |
| **4 · Shop** | Braucht danach keinen einzigen neuen Schnittstellen-Punkt. | nein |

Jeder Schritt ist einzeln machbar und einzeln rückholbar.

---

## Der rote Faden

Alle drei Antworten folgen derselben Regel, die dieses System stark macht:

> **Eine Frage, ein Feld.
> Und was eine Folge ist, wird ausgerechnet – nicht gespeichert.**

* Frage 1: Preise und Konditionen bekommen **einen** Ort (statt keinen, und statt einem
  zweiten im Shop).
* Frage 2: «fordern» und «begleichen» sind **zwei** Fragen und bekommen zwei Fächer
  (statt sechs Knöpfe für dreierlei).
* Frage 3: Zustand, Ort und Besitz sind **drei** Fragen und bekommen drei Spalten (statt
  eines Status, der alle drei beantworten soll).

---

*Grundlage: `develop` @ `9598091` · Zahlungsmodul = `domain/voucher.py`,
`services/voucher.py`, `beleg-work.tsx` · Statusliste = `domain/statuses.py` ·
Einzelinstanz = `models/instance_unit.py`. Die visuelle Fassung dieses Dokuments:
https://claude.ai/code/artifact/9e4e248b-5eb6-4a6b-84ff-0a7f7e80e603*
