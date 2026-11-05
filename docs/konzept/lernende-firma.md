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

## Aufbau in vier Schichten (Gesamtbild, 05.11.2026)

1. **Das Log** – was geschehen ist. Eine Stelle, jede Handlung, von Mensch, KI oder System.
   Fundament für alles Weitere (Verlauf, Lernen aus Korrekturen, «Relevant hier»).
2. **Das Wissen am Ding** – Verlauf, Dokumente, Notizen, an der Objektnummer.
3. **Die KI-Werkzeuge** – die KI darf, was die Person darf, in ihrem Namen (Grundsatz aus den
   Dokumenten). Ihre Handlungen sind die Handlungen des ERP selbst – keine eigene, feste Liste;
   sie wachsen mit jedem neuen Feature von selbst mit.
4. **Die Oberflächen** – «Erfassen» im ERP (schnell, unterwegs); Claude (App) über einen
   MCP-Connector für Gespräche, Meetings, Fragen; später weitere.

## Das Log (Leitlinie, Umsetzung eigenes Teilprojekt)

- **Ein Log für alles**, append-only: wer (Person, KI in ihrem Namen, System), was (Handlung),
  woran (Objektnummer), vorher → nachher, wann, aus welcher Quelle (Anfrage, Erfassen, Webhook …).
- **Nicht vergessbar:** geschrieben von der Datenbank selbst (Trigger an jeder Tabelle, der
  Handelnde wird je Anfrage mitgegeben), nicht von jedem Programmierer einzeln. Ein Wächter-Test
  verlangt den Trigger an jeder neuen Tabelle – so ist es bei jedem neuen Feature erzwungen.
- Die heutigen Teil-Logs (Prozess-Log, Audit-Log, Zeiterfassung) werden schrittweise Teile davon.
- Auswertung grosser Mengen (z. B. BigQuery) erst, wenn die Datenbank nicht mehr reicht.

## Regeln (entschieden)

- **Jedes Ding hat eine Nummer, jede Nummer einen Verlauf.** Der Verlauf ist die heutige
  Kommunikation, verallgemeinert von der Person auf jede Objektnummer.
- **Eine Heimat:** jeder Eintrag (Notiz, Dokument, Änderung) gehört genau einem Ding. Der Verlauf
  zeigt nur Eigenes; nichts wird doppelt abgelegt oder verknüpft.
- **«Relevant hier»** holt Wichtiges aus verbundenen Dingen – jedes Mal neu berechnet, nie
  gespeichert, immer mit Quelle, höchstens 3 bis 5 Punkte. Keine Bewertungsknöpfe.
- **Datensatz oder Eintrag:** Ein Datensatz (mit Nummer) hat einen eigenen Zustand oder wird von
  anderswo angesprochen. Notiz und Änderung → Eintrag. Foto, Scan, Datei, Video → Dokument. Etwas
  zu tun → Auftrag.
- **Aufträge immer mit Stücken.** Kein Auftrag ohne Stück; Arbeit an etwas Immateriellem läuft
  über einen Artikel (z. B. «Website»).
- **Die KI fasst zusammen und füllt vor, ein Mensch legt an.** «Auftrag daraus» und «Angabe
  ändern» sind Knöpfe, keine automatischen Aktionen. Zu Beginn wird jedes einzeln bestätigt.
- **Höchstens eine Rückfrage** beim Erfassen, nur wenn Wichtiges fehlt (meist das «Warum»),
  jederzeit überspringbar.
- **Audio wird nicht gespeichert**, das wörtliche Transkript und die KI-Fassung bleiben. **Video
  bleibt im Original** (als Dokument).
- **Spracherfassung** von Anfang an, mit einem professionellen, robusten Dienst.
- **Ein zentrales Log** für jede Änderung an jedem Ding, sichtbar im Verlauf (vorher → nachher,
  wer, woher). Heute lückenlos nur Prozess, Zeiterfassung und Geld; sonst nur «wer rief welche
  Adresse auf». Vorgesehen, noch nicht gebaut.
- **Ein Wissenswerkzeug, kein Management-Werkzeug.** Kein Rückblick, kein Dashboard, keine
  Termine, kein «zu tun». Wer was tut, regeln Aufträge.
- **Ziel statt Regeln.** Die KI bekommt keine Wenn-dann-Regeln (kein «frag immer nach dem
  Warum», kein «ab dem dritten Mal», kein Pflicht-Grund), sondern **einen Auftrag**: unser Ziel,
  unsere Firma und was sie tun *kann*. Daraus leitet sie selbst ab, was sie mit einem Input macht –
  zusammenfassen, aufteilen, ablegen, wichtig finden, nachfragen oder nichts. Fest ist nur die Liste
  der möglichen Handlungen; was sie wann tut, entscheidet sie aus dem Ziel. Für Wichtigkeit liest sie
  echte Daten nach (Neukunde? Warenwert? schon öfter?), statt zu zählen.
- **Die KI zuerst:** sie legt ab, auch aufgeteilt auf mehrere Dinge (je Teil eine Heimat – wichtig
  für Meetings mit vielen Themen). Der Mensch kontrolliert («Stimmt so» oder «ändern») – auch im
  Datensatz entscheidet nicht er, wohin es gehört.
- **Sie lernt aus Korrekturen:** jedes «ändern» und «verwerfen» wird als Beispiel aufbewahrt und
  geht in künftige Entscheide ein. Kein Training, kein Regelwerk – eigene Beispiele.
- **Wichtiges bleibt oben** in «Relevant hier», bis es erledigt oder überholt ist. Kein Zählen
  («ab dem dritten Mal» ist verworfen: eine einzelne Meldung kann hochrelevant sein).
- **Ein Einstieg «Erfassen»:** der rote «+» öffnet das Menü (Aufnehmen, Kamera, Galerie, Scannen,
  Schreiben, Neuer Datensatz). Kein Halten – Aufnehmen läuft mit Start und Stopp, auch für ein
  ganzes Meeting. **Der Verlauf hat kein eigenes Eingabefeld**; alles läuft über diesen
  Einstieg.
- **Eine Regel für alles, keine Ausnahmen** (auch nicht für Sicherheit). Dass etwas getan werden
  muss, gehört ins Aufgabenmanagement («wer macht was»), nicht ins Wissen.
- **Mail:** keine eigene Notiz-Adresse; was an die Postfächer der Gesellschaften kommt, ordnet das
  System zu.
- Kultur (Fehler melden ist sicher, wer meldet, hört, was daraus wurde) ist Teil des Ziels, kann
  aber nicht gebaut werden – sie wird vorgelebt.

## Plan

| Phase | Inhalt | Stand |
|---|---|---|
| 0 | Projektakte, Mockup | in Arbeit |
| 0b | **Das Log** (Fundament) | offen |
| 0c | KI-Werkzeuge («darf, was die Person darf») + MCP-Connector | offen |
| 1 | Verlauf an jeder Nummer · «Erfassen» (Sprechen, Kamera, Galerie, Scannen, Schreiben) · KI-Fassung · eine Rückfrage | offen |
| 2 | Zentrales Log im Verlauf | offen |
| 3 | «Relevant hier» | offen |


Nach jeder Phase zwei Wochen im Alltag, dann Entscheid über die nächste.

## Entscheide (mit Datum)

- 03.11.2026 – Arbeitsweise: Claude führt, stellt Fragen mit Empfehlung; Clemens entscheidet.
- 03.11.2026 – Spracherfassung kommt in Phase 1, nicht später.
- 03.11.2026 – Kein Zählen, keine Termine, kein «zu tun»: Wichtigkeit beurteilt die KI je Notiz mit
  Grund; Wichtiges bleibt oben am Ding. Das Werkzeug bewahrt Wissen, es führt keine Aufgaben.
- 03.11.2026 – Die KI legt ab (auch aufgeteilt), der Mensch kontrolliert; «+» halten = sprechen.
- 04.11.2026 – Ziel statt Regeln für die KI; Name bleibt «Erfassen»; kein Halten, Aufnehmen mit
  Start/Stopp. Zuständigkeit künftig je Prozessschritt (Kompetenz statt Abteilung) – Folgeprojekt.
- 03.11.2026 – Keine Ausnahme für Sicherheit; kein Eingabefeld im Verlauf; Wichtigkeit ohne feste
  Gründe (freier Satz).

## Offene Fragen

- Der Auftrag an die KI (der eine Prompt): Entwurf, Prüfung an echten Beispielen.
- Offene Vorschläge warten am Ding, wo sie erfasst wurden («zu tun»-Zahl am Symbol, gibt es schon)?
- Eigenen Assistenten bauen oder Claude (App) über MCP anschliessen?
- Antworten auf eine Mail ohne Eingabefeld im Verlauf: über den Einstieg, mit Empfänger vorbelegt?
- Aufgabenmanagement («wer macht was»): eigenes Folgeprojekt; Mindestlösung bis dahin?
- Welcher Sprachdienst (Mundart)?
