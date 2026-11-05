# Projektakte «Die lernende Firma»

> **Kopfstatus:** Konzept, in Arbeit · Lead: Claude · Entscheid: Clemens Fritsche · seit 03.11.2026
> Mockup (1:1 im ERP): https://claude.ai/artifact/8jAy56JQ1jEESPwgRHPSSK
> Diese Akte ist die eine Quelle für Ziel, Regeln, Entscheide und offene Fragen. Was hier nicht
> steht, ist nicht entschieden.

## Problem

Wissen entsteht überall – im Gespräch, auf Montage, in Mails, in Aufträgen. Das meiste bleibt
im Kopf (implizites Wissen), verändert sich bei jeder Übergabe (stille Post), ist später nicht
auffindbar und geht mit den Leuten (Organisationsgedächtnis). Rückmeldungen erreichen nicht, wer
handeln kann, und ob eine Massnahme gewirkt hat, prüft niemand. Die Firma lernt darum nicht
verlässlich aus dem, was sie erlebt.

## Ziel

**Eine Firma, die nichts vergisst und sich von selbst verbessert – ohne dass jemand es managt
oder überwacht.**

Woran wir es messen (nach rund 3 Monaten im Alltag):

1. **Erfassen unter 30 Sekunden** – jede Montage, jedes Kundengespräch hinterlässt eine Notiz.
2. **In 30 Sekunden gefunden** – was über ein Ding bekannt ist, steht dort, mit Quelle.
3. **Wichtiges ist nicht zu übersehen** – es steht oben am Ding, bis es erledigt oder überholt ist.
4. **Keine neue Insel** – bestehende Funktionen werden zusammengeführt, keine kommt dazu.

## Grundsatz

**Die KI arbeitet nach dem Ziel, ein Mensch kontrolliert.** Sie bekommt keine Wenn-dann-Regeln,
sondern einen Auftrag (wer wir sind, was wir erreichen wollen) und darf, was die Person darf.
Gearbeitet wird **nur im ERP** – Mitarbeitende erfassen dort, die KI verarbeitet im Hintergrund.

## Aufbau in vier Schichten

| Schicht | Inhalt | Reihenfolge |
|---|---|---|
| 1 · **Das Log** | was geschehen ist – jede Handlung, eine Stelle | zuerst |
| 2 · **Wissen am Ding** | Verlauf, Kommunikation, Dokumente, Dateien, Bilder, Notizen an der Objektnummer | danach |
| 3 · **KI-Werkzeuge** | die KI darf, was die Person darf, in ihrem Namen | danach |
| 4 · **Oberflächen** | «Erfassen» im ERP; optional ein MCP-Zugang für Claude (nur Clemens) | zuletzt |

## 1 · Das Log

**Zweck:** die eine, vollständige, unveränderliche Wahrheit darüber, was im System geschehen
ist – Grundlage für den Verlauf am Ding, für das Lernen der KI aus Korrekturen, für «Relevant
hier», für Nachvollziehbarkeit (Buchungsbelege 10 Jahre) und für die Fehlersuche.

**Keine Rückwärtskompatibilität.** Die heutigen Logs (`audit_log`, `process_events`, das
Protokoll einzelner Stellen) werden ersetzt, nicht übernommen. Was heute aus `process_events`
abgeleitet wird (Prozessbild, Protokoll, Stückliste, Journey), liest danach aus dem neuen Log.

**Was ein Eintrag festhält** (eine Tabelle, append-only):

| Feld | Bedeutung |
|---|---|
| Zeitpunkt | von der Datenbank gesetzt, nicht vom Aufrufer |
| Wer | Person (Objektnummer) · Art: Mensch · KI im Namen von · System · von aussen (Webhook, Kunde über Link) |
| Woher | Oberfläche, Erfassen, Webhook, Job, Migration, MCP – und eine Vorgangs-Id, die alle Einträge einer Handlung verbindet |
| Woran | Objektnummer des Dings (und die Zeile, falls es keine Nummer hat) |
| Was | Handlung: angelegt · geändert · gelöscht (weich) · fachliches Ereignis (z. B. Status passiert, Mail gesendet, Vorschlag verworfen) |
| Vorher → nachher | nur die geänderten Felder |
| Prüfsumme | Kette über die Einträge: jede nachträgliche Änderung wird erkennbar |

**Wie es nicht vergessen werden kann:**
- **Die Datenbank schreibt es selbst** – ein Trigger an jeder Tabelle hält jede Änderung fest.
  Wer handelt, gibt die Anwendung je Anfrage in der Transaktion mit; fehlt diese Angabe, **scheitert
  das Schreiben** (lieber laut als ohne Spur).
- **Fachliche Ereignisse** (die keine Zeile ändern) schreibt eine einzige Funktion in dieselbe
  Tabelle, in derselben Transaktion – entweder beides oder nichts.
- **Wächter-Tests:** jede Tabelle hat den Trigger (Ausnahmen namentlich begründet); das Log ist
  weder änder- noch löschbar (auch nicht für die Anwendung selbst).
- **Lesen sensibler Daten** (Download, Export, Zugriff der KI) wird ebenfalls festgehalten.

**Datenschutz:** Das Log nennt Personen über ihre Objektnummer. Muss eine Person gelöscht werden,
geschieht das über eine einzige, selbst protokollierte Schwärzungsfunktion – die einzige erlaubte
Änderung.

**Grösse und Ort:** Das Log bleibt in der Datenbank (Cloud SQL). Für das ERP reicht das auf
Jahre; es wird nach Monaten aufgeteilt, damit es schnell bleibt.

**Website-Messung ist ein eigener Strom, nicht das Log.** Klicks und Wege von anonymen Besuchern
sind Messdaten, keine Handlungen im System – viel mehr, kurzlebiger, anonym. Sie gehen in
**BigQuery** (gebaut für genau solche Mengen und Auswertungen, günstig bei unseren Zahlen); das ERP
liest daraus verdichtete Zahlen, nicht jede Zeile. Wird aus einem Besucher ein Kunde (Anfrage),
beginnt seine Spur im Log.

## 2 · Wissen am Ding

- **Jedes Ding hat eine Nummer, jede Nummer einen Verlauf.** Der Verlauf zeigt, was zum Ding
  gehört: Kommunikation, Dokumente, Dateien, Bilder, Notizen und Änderungen (aus dem Log).
- **Eine Heimat:** jeder Eintrag gehört genau einem Ding; nichts wird doppelt abgelegt. Eine
  Aufnahme mit mehreren Themen (z. B. ein Meeting) teilt die KI in Teile, jeder mit seiner Heimat.
- **Datensatz oder Eintrag:** Ein Datensatz (mit Nummer) hat einen eigenen Zustand oder wird von
  anderswo angesprochen. Notiz, Änderung → Eintrag. Foto, Scan, Datei, Video → Dokument. Etwas zu
  tun → Auftrag (immer mit Stücken; Immaterielles über einen Artikel, z. B. «Website»).
- **«Relevant hier»** holt Wichtiges aus verbundenen Dingen – jedes Mal neu berechnet, nie
  gespeichert, immer mit Quelle. So viele Punkte, wie wirklich helfen – auch keiner.
- **Wichtiges bleibt oben**, bis es erledigt oder überholt ist. Wichtigkeit beurteilt die KI aus
  dem Ziel und echten Daten (Neukunde? Warenwert? schon vorgekommen?), nicht durch Zählen.
- **Audio wird nicht gespeichert** (wörtliches Transkript und KI-Fassung bleiben), **Video
  bleibt im Original**.
- **Kommunikation bleibt, wie sie ist:** Mails an Personen und Firmen schreibt man dort wie
  heute. Andere Dinge (Artikel, Auftrag …) haben kein eigenes Eingabefeld – Wissen kommt über
  «Erfassen».

## 3 · KI-Werkzeuge

- **Die KI darf, was die Person darf, in ihrem Namen** – über dieselben Wege und Prüfungen wie die
  Oberfläche, kein zweiter Code. Ihre Handlungen sind die Handlungen des ERP selbst; mit jedem
  neuen Feature kann sie es von selbst auch. Keine eigene, feste Liste.
- **Lesen frei (im Rahmen der Rechte), Schreiben als Vorschlag.** Was die KI ändern oder anlegen
  will, wird ein Vorschlag; ein Mensch bestätigt oder verwirft. (Ob einzelne Handlungen später
  ohne Bestätigung laufen dürfen, entscheiden wir mit Erfahrung.)
- **Offene Vorschläge warten am Ding**, an dem erfasst wurde, und zählen in dessen «zu tun»-Zahl
  am Symbol (gibt es schon). Nichts muss sofort nach dem Erfassen erledigt werden.
- **Der Auftrag an die KI** ist ein einziger, versionierter Text im Repository: wer wir sind,
  unser Ziel, worauf es ankommt. Er gilt für Erfassen und «Relevant hier». Keine Regeln wie «frag
  immer nach dem Warum» – Rückfragen stellt sie, wenn das Ziel es verlangt.
- **Sie lernt aus Korrekturen:** jedes Bestätigen, Ändern und Verwerfen steht im Log und geht als
  Beispiel in künftige Entscheide ein. Weniger Korrekturen = bessere KI; das ist zugleich der
  Massstab für ihre Qualität.
- **Eine Tür:** jeder KI-Aufruf läuft über `services/ai.py` (Tageslimit, jeder Aufruf im Log).
- **MCP-Zugang (optional, später):** dieselben Werkzeuge, angeboten an Claude (App) – nur für
  Clemens, aus Interesse. Richtung: Claude ruft das ERP auf, nicht umgekehrt. Das ERP selbst
  braucht dafür nichts: «Erfassen» spricht die KI direkt über `services/ai.py` an.

## 4 · Oberflächen

- **Ein Einstieg «Erfassen»:** der rote «+» öffnet das Menü – Aufnehmen (Start/Stopp, auch für
  ein ganzes Meeting), Kamera, Galerie, Scannen, Schreiben, Neuer Datensatz.
- **Die KI legt ab, der Mensch kontrolliert** («Stimmt so» oder «ändern»), auch im Datensatz.
- **Spracherfassung** von Anfang an, mit einem professionellen, robusten Dienst (Mundart).

## Weitere Regeln

- **Eine Regel für alles, keine Ausnahmen** (auch nicht für Sicherheit).
- **Ein Wissenswerkzeug, kein Management-Werkzeug:** kein Rückblick, kein Dashboard, keine
  Termine. Wer was tut, regeln Aufträge; Zuständigkeit künftig je Prozessschritt (Kompetenz
  statt Abteilung) – Folgeprojekt «Aufgaben».
- **Mail:** keine eigene Notiz-Adresse; was an die Postfächer der Gesellschaften kommt, ordnet das
  System zu.
- Kultur (Fehler melden ist sicher, wer meldet, hört, was daraus wurde) ist Teil des Ziels, kann
  aber nicht gebaut werden – sie wird vorgelebt.

## Plan

| Phase | Inhalt | Stand |
|---|---|---|
| 0 | Projektakte, Mockup | in Arbeit |
| 1 | **Das Log** – neu, ersetzt alle heutigen Logs | offen |
| 2 | Verlauf an jeder Nummer (Wissen am Ding) | offen |
| 3 | KI-Werkzeuge: Vorschläge, Auftrag an die KI, Lernen aus Korrekturen | offen |
| 4 | «Erfassen» mit Spracherfassung | offen |
| 5 | «Relevant hier» | offen |
| später | Website-Messung (BigQuery) · MCP-Zugang · Folgeprojekt «Aufgaben» | offen |

Nach jeder Phase zwei Wochen im Alltag, dann Entscheid über die nächste.

## Entscheide (mit Datum)

- 03.11.2026 – Arbeitsweise: Claude führt, stellt Fragen mit Empfehlung; Clemens entscheidet.
- 03.11.2026 – Kein Zählen, keine Termine; Wichtiges bleibt oben am Ding. Das Werkzeug bewahrt
  Wissen, es führt keine Aufgaben. Keine Ausnahme für Sicherheit.
- 03.11.2026 – Die KI legt ab (auch aufgeteilt), der Mensch kontrolliert.
- 04.11.2026 – Ziel statt Regeln; Name «Erfassen»; Aufnehmen mit Start/Stopp; Wichtigkeit ohne
  feste Gründe.
- 05.11.2026 – Vier Schichten, das Log zuerst; **keine Rückwärtskompatibilität** für die heutigen
  Logs; Website-Messung als eigener Strom (BigQuery).
- 05.11.2026 – Gearbeitet wird nur im ERP; MCP höchstens als persönlicher Zugang für Clemens.
- 05.11.2026 – Kommunikation (Mails an Personen und Firmen) bleibt, wie sie ist.

## Offene Fragen

- Der Auftrag an die KI: Entwurf und Prüfung an drei echten Beispielen (Montage-Notiz,
  Meeting-Notiz, Kunden-Mail).
- Welcher Sprachdienst versteht Mundart zuverlässig?
- Folgeprojekt «Aufgaben» (wer macht was, Zuständigkeit je Prozessschritt).
