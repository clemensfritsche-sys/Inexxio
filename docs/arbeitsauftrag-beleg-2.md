# Arbeitsauftrag — Der Beleg wird ruhig (Testnotizen #909–#920)

> **Grundlage für die Umsetzung.** Zwölf Notizen, und der rote Faden ist **einer**:
> *dieselbe Angabe steht zweimal da, und geändert wird sie nicht dort, wo man sie liest.*
>
> Die letzte Runde hat den Beleg **vollständig** gemacht. Diese hier macht ihn **ruhig**:
> jede Angabe genau einmal, und änderbar an der Stelle, an der sie steht.
>
> **Hausregeln gelten unverändert** — eine Sache, eine Stelle · Ableitung vor Spalte ·
> `can` ist Auskunft **und** Tor · kein `if direction ==` · Struktur vor Fläche · jede
> Regel gegen ihre Bug-Form gegengeprüft · gemessen statt behauptet.
>
> Stand: 12.09.2026, gegen `e400c76`.

---

## Teil 0 · Zwei Befunde vorab — beide im Code nachgelesen, nicht vermutet

### 0.1 · #911 ist ein echter Bug, und die Ursache ist eine Reihenfolge

Das Auswahlfeld der Lieferbedingung ist an den **Serverwert** gebunden
(`value={d.incoterm ?? ''}`) und schickt beim Wählen sofort
`{incoterm: 'FCA', incoterm_place: place}` — und `place` ist in diesem Moment **leer**.
Der Dienst weist eine Klausel ohne benannten Ort mit **400** ab (`deal._incoterm`,
richtig so: «FCA» allein ist keine Vereinbarung). Der Server ändert also nichts, das
Feld liest den unveränderten Wert zurück, und der Nutzer sieht: *nichts wird übernommen.*

**Die Regel ist richtig, die Bauart falsch.** Klausel und Ort sind **eine** Vereinbarung
— also gehören sie in **einen** lokalen Entwurf und gehen **zusammen** hinaus, sobald er
vollständig ist. Das ist exakt die Bauart der Angebotszeile (`useAutosave`, #879), und
sie ist im Haus schon zweimal die Antwort auf dieselbe Frage gewesen.

*Verworfen: die Server-Regel lockern. Dann stünde eine halbe Klausel im Datensatz, und
die Prüfung wanderte an die Zusage — eine Regel weiter weg von der Eingabe.*

### 0.2 · #910 braucht kein `if`, es braucht den vorhandenen Aufruf

`sites.legal_name(company)` gibt es seit der letzten Runde und tut **genau** das, was
die Notiz verlangt: Firmenname, und die Rechtsform nur dort angehängt, wo sie fehlt
(«Muster AG» wird nicht zu «Muster AG AG»). Sie steht heute nur an **einer** Stelle im
Einsatz — dem Belegkopf. Feed, Halter-Suche und Ortskette lesen weiterhin roh
`company_name`.

**Zu tun ist darum nicht ein neues `if`, sondern die eine Funktion überall zu rufen.**
Ein zweites Namensrezept wäre die Stelle, an der die beiden beim nächsten Feld
auseinanderlaufen.

---

## Teil 1 · Der Belegkopf wird symmetrisch und trägt die Gegenpartei

### 1.1 · #913 — beide Parteien auf einer Linie

Heute fliessen die Angaben je Seite untereinander: hat die eine Partei kein «z. H.»,
rutscht bei ihr alles eine Zeile hoch, und Anschrift steht neben Nummer.

**Zu tun:** die beiden Blöcke teilen **ein** Raster mit einer festen Zeile je Angabe
(Name · z. H. · Anschrift · Nr. · Kontakt · UID). Fehlt eine Angabe, bleibt die Zeile
**leer** — die Symmetrie ist die Aussage, nicht die Dichte.

*Technisch: ein gemeinsames `grid` mit `grid-template-rows`, die Blöcke als `subgrid`
(oder, wo das nicht trägt, dieselbe Zeilenzahl je Seite). **Gemessen**, nicht geschätzt:
gleiche Angabe = gleiche `y`-Koordinate, Δ 0,0 px, über alle sechs Breiten.*

### 1.2 · #912 — die Gegenpartei wählt man dort, wo sie steht

> *«…dass diese Auswahl-Eingabe hier unten vollumfänglich entfällt (bis auf „Bei 1
> anbieten") und die jeweilige Gegenpartei oben rechts direkt als Leistungsempfänger
> aufführst.»*

**Die Idee dahinter ist die Hausregel selbst:** ändern, wo man liest. Der Belegkopf sagt
«Leistungsempfänger: Monika Fritsche» — dann gehört die Wahl genau dorthin, nicht in
einen Abschnitt zwei Bildschirme tiefer.

**Zu tun:**
* Der **Leistungsempfänger** im Kopf wird zum Bedienelement — dieselbe Geste wie der
  Aussteller-Stift (#905, `ActionButton` + `ObjectSelect`): hinzufügen und abwählen.
* Sind **mehrere** angefragt, steht dort der, um den es geht, und man wechselt.
  **Nicht mit Pfeilen** — ein Karussell sagt weder, wie viele es gibt, noch welcher
  gewählt ist. Stattdessen dieselbe Form, die das Haus für «einer aus wenigen» schon
  hat: eine Zeile aus Chips (`Segmented`-Bauart), jeder mit **Punkt + Wort** für seinen
  Zustand (angefragt · offeriert · abgesagt · **Zuschlag**). Bei genau einem gibt es
  nichts zu wechseln, und die Zeile ist schlicht der Name.
* **Nach dem Zuschlag** steht nur noch der Gewinner — die Unterlegenen sind Nachweis,
  kein Bedienelement (#899).
* Der Knopf **«Bei N anbieten»** bleibt, wo die Handlung hingehört: am Angebot.

### 1.3 · #914 — B2B und B2C, und warum es dafür keinen Schalter gibt

**Die Regel steht schon da** (`people.billing_name`): *Firma zuerst, Person als «z. H.»;
ohne Firma bleibt die Person.* Ein Privatkunde trägt keinen Firmennamen — also steht
dort sein Name, und zwar ohne dass jemand ein Häkchen setzt.

**Zu tun ist darum: messen und festhalten**, nicht bauen. Ein `is_business`-Feld wäre
eine **zweite Aussage** über etwas, das die Daten schon sagen — und es wäre die Stelle,
an der jemand es falsch setzt.

*Wächter: ein Empfänger ohne Firmenname erscheint mit seinem Personennamen und **ohne**
eine «z. H.»-Zeile; einer mit Firma mit beiden. Gegen die Bug-Form gegenprüfen.*

---

## Teil 2 · Die Positionszeile trägt, was auf den Beleg gehört

### 2.1 · #916 — die aufklappbare Spezifikation entfällt vollständig

Sie war der Kompromiss «Datenblatt auf Klick». Auf einem **Beleg** ist sie das nicht:
was der Empfänger braucht, steht in der Zeile; was er nicht braucht, gehört nicht auf
das Papier. **Ersatzlos gelöscht** — Chevron, Zustand, Raster.

### 2.2 · #915 — der HS-Code ist am Beleg überschreibbar

> *«…jedoch wenn nichts eingetragen ist, oder auch wenn etwas eingetragen ist, dann soll
> es trotzdem möglich sein, hier eine Eingabe bzw. Änderung einzutragen.»*

**Die Idee dahinter ist richtig und wichtiger, als sie aussieht:** die Zolltarifnummer
ist eine Eigenschaft der **Sache** — aber welche Nummer auf *diesem* Beleg steht, ist
eine Aussage **dieses Geschäfts**. Der Artikel liefert die **Vorbelegung**, der Beleg
trägt den **Wert**. Dieselbe Beziehung wie beim Preis.

**Zu tun:**
* Je Position ein kleines Feld für den HS-Code, **vorbelegt aus dem Artikel**, frei
  überschreibbar — und **mit der Zusage eingefroren** (`agreed_lines`), wie Preis und
  Satz. Ab dort ist eine zweite Partei gebunden.
* **Das Ursprungsland gehört dazu** und ist hiermit benannt: mit #916 verschwände es
  sonst spurlos vom Beleg, obwohl es für die Ausfuhr dieselbe Pflichtangabe ist. Es
  bekommt dieselbe Behandlung.
* Der Artikel bleibt die Quelle der Vorbelegung; **zurückgeschrieben wird nichts** — ein
  Beleg korrigiert keine Stammdaten.

### 2.3 · #917 — die Währung steht am Betrag, und zwar leise

Die letzte Runde hat sie an den Kopf der Preisspalte gesetzt (#906). Richtig war die
Richtung, zu laut die Form: ein 190-px-Auswahlfeld über einer Tabelle.

**Zu tun:** sie sitzt **am Nettobetrag** (Summenblock) als minimaler Wähler — der Code
selbst ist das Bedienelement, nicht ein Feld daneben. Aufgeklappt steht der volle Name.
**Eine Währung je Vorgang bleibt** (§9.12); änderbar bis zur Zusage, und das sagt
weiterhin `can`, kein zweites Feld.

---

## Teil 3 · Was unten steht, ist eine Chronik — nicht ein zweiter Beleg

### 3.1 · #918 — der Abschnitt sagt nur noch, WANN

> *«Eigentlich muss ich ja nur wissen: wann wurde offeriert, wann wurde die Offerte
> angenommen… Alle anderen Details — von wem, welcher Betrag etc. — sind nur Duplikate,
> es steht ja oben sowieso.»*

**Stimmt, und es ist genau die Regel aus #899**, nur eine Stufe weiter gedacht: jede
Beleg-Angabe steht an **genau einem** Ort. Partner, Betrag und Fristen stehen im Kopf,
in den Positionen und in den Konditionen — unten sind sie das dritte Mal.

**Zu tun:** aus dem Abschnitt wird eine **Chronik**: je Ereignis eine Zeile mit Datum.
*Offeriert · angenommen · (storniert)*. Minimal, tabellarisch, ohne Kasten.

**Was bleibt und warum:** die **Handlungen** (anfragen, offerieren, absagen, Zuschlag)
gehören zu den Zeilen, auf die sie wirken — solange verhandelt wird, ist das die
Arbeitsfläche. Sie wandern mit der Gegenpartei-Wahl in den Kopf (1.2), was dort steht,
ist danach wirklich nur noch Geschichte.

### 3.2 · #920 — «Bedingungen» heisst im Handel **«Konditionen»**

Geprüft statt geraten: im deutschen Geschäftsverkehr ist der **Sammelbegriff für
Zahlungs-, Liefer- und Preisvereinbarungen** *Konditionen*; «Bedingungen» ist im
Deutschen juristisch belegt (**A**llgemeine **G**eschäfts**b**edingungen) und liest sich
auf einem Beleg als Verweis auf ein Regelwerk statt auf das, was hier vereinbart wurde.
International steht dort *Terms*, und dessen kaufmännische Entsprechung ist
*Konditionen*.

**Zu tun:** die Überschrift heisst **«Konditionen»**. Ein Wort, eine Konstante, eine
Stelle.

### 3.3 · #919 — das Leistungsdatum ist kein Eingabefeld

> *«…es soll nicht möglich sein, hier ein veränderbares Leistungsdatum anzugeben, bzw.
> ich will hier gar keine Information zum Lieferdatum, denn das ist oben schon in den
> Bedingungen.»*

**Die erste Hälfte wird umgesetzt, die zweite braucht einen Satz.** Das Feld entfällt:
der Server leitet das Datum aus dem Prozess ab (`deal.service_day` — der Tag, an dem die
Stücke das Modul erreicht haben), und eine Eingabe daneben war die zweite Aussage.

**Aber es verschwindet nicht vom Beleg.** Das Leistungsdatum ist auf einer Schweizer
Rechnung eine **Pflichtangabe** (MWSTG Art. 26 Abs. 2 Bst. c) und — das ist der Punkt —
**nicht dasselbe wie der Liefertermin** in den Konditionen: der Termin ist die *Zusage*,
das Leistungsdatum die *Tatsache*, und bei einem Satzwechsel oder über den Jahreswechsel
entscheidet es, welche Steuerperiode gilt.

**Zu tun:** kein Feld im Formular. Es steht als **Auskunft an der gebuchten Rechnung**,
wo es hingehört — dort, wo es rechtlich zählt, und nicht dort, wo man arbeitet.

*Falls du auch die Auskunft nicht willst: dann bleibt sie in den Daten und fehlt auf dem
Papier — das ist eine bewusste Abweichung von Art. 26, und sie müsste so benannt werden.
Sag Bescheid.*

---

## Teil 4 · #909 — ein Auswahlfeld darf nicht abgeschnitten werden

> *«…dieser Container, dieser Bereich ist eine Ebene höher als das Dropdown-Suchfeld, und
> deswegen kann ich es dann nicht anwählen. Finden wir hier eine elegante und vor allem
> robuste Lösung.»*

**Die Diagnose ist richtig und das Problem ist strukturell.** Die Vorschlagsliste ist
`position: absolute` im Feld (`SearchSelect`, `zIndex: 40`). Damit hängt sie an **jedem**
Vorfahren: einer mit `overflow: hidden` schneidet sie ab, einer mit `transform`,
`filter` oder eigenem `z-index` legt den nächsten Block darüber. Ein höherer `z-index`
verschiebt das Problem nur zur nächsten Aufrufstelle.

**Die robuste Lösung ist die etablierte:** die Liste wird **in `document.body` portiert**
(React-Portal) und **fix positioniert**, ausgerichtet an der gemessenen Position des
Feldes. Damit kennt sie keinen Vorfahren mehr — kein Stacking-Context, kein `overflow`.

**An EINER Stelle** (`SearchSelect`), also erbt es **jedes** Referenzfeld im Haus:
Modul-Ziel, Bedarfszeile, «Ersetzt Artikel», Partner, Gesellschaft.

**Was dazugehört, damit es wirklich robust ist:**
* Neuausrichtung bei Scroll und Resize (die Liste hängt nicht mehr am Feld).
* Nach **oben** klappen, wenn unten kein Platz ist.
* Schliessen bei Klick daneben und `Esc`, Tastaturweg unverändert.
* **Gemessen in Chromium**, im echten Rahmen: Liste vollständig sichtbar und klickbar,
  auch wenn ein weiteres Modul darunter steht — und die Bug-Form (ohne Portal) meldet.

---

## Teil 5 · #910 — der Datensatzname eines Unternehmens

`sites.legal_name` wird zur **einen** Stelle, an der ein Unternehmen benannt wird:
Feed, Halter-Suche (`places`), Ortskette, Adressen, Belegkopf.

**Kein zweites Rezept, kein `if` an der Aufrufstelle.** Wächter: keine Datei ausser
`sites.py` baut einen Unternehmens-Anzeigenamen aus `company_name` + `legal_form`.

---

## Teil 6 · Reihenfolge und Abnahme

**Reihenfolge** (jede Stufe für sich lauffähig):

1. **#911** — der Bug. Klausel und Ort als ein Entwurf, Autosave bei Vollständigkeit.
2. **#910** — `legal_name` überall.
3. **#909** — Portal für `SearchSelect`. *Zuerst, weil 1.2 darauf aufbaut.*
4. **#920 · #919 · #917 · #916** — Wörter und Wegnehmen. Kein Datenmodell.
5. **#915** — HS-Code und Ursprungsland an der Position (Migration: `agreed_lines`
   trägt sie mit; die Spalten am Artikel bleiben Vorbelegung).
6. **#913** — Symmetrie im Belegkopf.
7. **#912 · #918** — die Gegenpartei in den Kopf, der Abschnitt wird Chronik.
   *Zuletzt, weil es die grösste Änderung an der Karte ist.*
8. **#914** — messen und mit Wächtern festhalten.

**Abnahme — dieselben Massstäbe wie in jeder Runde:**

* Jeder neue Wächter **gegen seine Bug-Form gegengeprüft**.
* Suite grün gegen die **gewachsene Datenbank** *und* gegen ein Schema **nur aus den
  Migrationen**.
* Jede Migration: von null · idempotent · downgrade · über das Lifespan-Netz.
* Gemessen in Chromium an den **echten** Komponenten (Karte im `ModuleShell`):
  1440 · 1280 · 1024 · 834 · 375 · 320 px, **0 px** waagrechter Überlauf über alle
  Beleg-Zustände, beide Richtungen und die Sicht der Gegenpartei. Die Messung selbst
  gegen ihre eigene Bug-Form gegenprüfen.
* **Zusätzlich in dieser Runde gemessen:** Symmetrie der Parteiblöcke (Δ y = 0,0 px je
  Angabe) und die Vorschlagsliste über einem nachfolgenden Modul (vollständig klickbar).
