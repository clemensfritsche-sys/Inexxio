---
name: feedback
description: >-
  Testnotizen aus der Inexxio-Oberfläche abarbeiten – die Pins, die beim Testen auf
  inexxio-dev.web.app gesetzt wurden. Nutze diese Skill, wenn der Nutzer Testnotizen
  einfügt (Markdown-Blöcke mit "## #<id> · /route" und "**Element:**"), wenn er sagt
  "arbeite die Notizen ab", "hier sind meine Befunde vom Testen", "Feedback umsetzen"
  oder /feedback aufruft. Erklärt, wie aus einer angehefteten Notiz die betroffene
  Code-Stelle wird und wie die Notiz danach geschlossen wird.
  Trigger: "Testnotizen", "Notizen", "Feedback", "Befunde", "Pins", "beim Testen aufgefallen".
---

# Testnotizen abarbeiten

Vollständige Beschreibung des Moduls: **`docs/feedback.md`** (bei Fragen zum Datenmodell
oder zur Bedienung dort nachlesen).

## Woher die Notizen kommen

Der Nutzer testet auf `https://inexxio-dev.web.app`, heftet Notizen an konkrete Elemente
und kopiert sie im Widget über **«Alle offenen Notizen als Markdown kopieren»**. Liegt kein
Markdown vor, danach fragen – es gibt (noch) keinen Weg, die Notizen aus einer Sitzung
heraus selbst abzurufen.

Format je Notiz:

```markdown
## #12 · /erp

> Der Freigeben-Knopf sollte hier ausgegraut sein

- **Ansicht:** Auftrag · Ablauf
- **Abschnitt:** Bewegung
- **Element:** «Freigeben» (`button`)
- **Selektor:** `div > div:nth-of-type(2) > button`
- **Datensatz:** 100000123
- **Umgebung:** Rolle employee · 1440x900 · Build a1b2c3d4
- **Fehler:** TypeError: x is undefined (page-3f2.js:1)
```

## Vorgehen je Notiz

1. **Code-Stelle finden – in dieser Reihenfolge.**
   - **Ansicht + Abschnitt zuerst:** «Auftrag · Prozess / Beschaffen» führt direkt zu
     `components/erp/purchase-work.tsx`. Der Abschnitt ist der Titel eines
     `PanelHeader`/`SectionTitle` – `rg -n 'PanelHeader|SectionTitle' frontend/src`.
     Bei Prozess-Notizen ist das der zuverlässigste Einstieg, weil die Modulliste
     sortierbar ist und der Selektor mitwandert.
     **Ein Modul ist keine eigene Datei.** Die Ausführung aller Module läuft über
     `capture-work.tsx` (Erfassung, Aussondern, Verbrauch, Bewegen) bzw.
     `purchase-work.tsx` (Beschaffen, und der Einkaufs-Beleg des Bewegens); was ein
     Modultyp mitbringt, steht als Zuordnung in `lib/modules.ts`, nicht als Datei.
   - **Dann der sichtbare Text:** die Oberfläche ist deutschsprachig, Beschriftungen
     stehen meist genau einmal im Repository: `rg -n "Freigeben" frontend/src`.
   - **Route als Eingrenzung:** `/erp` → `frontend/src/app/(erp)/` und
     `components/erp/`, `/konto` → `components/account/`. Andere Routen gibt es im
     angemeldeten Bereich nicht – der Feed ist EINE Route (`?open=` ist nur der
     Deep-Link von aussen), darum trägt die Notiz die Objektnummer statt eines Pfades.
   - Hilft nichts davon (Icon-Knopf), das `outerHTML` und den Selektor heranziehen.
2. **Rolle beachten.** `Rolle customer` heisst: der Befund gilt für die Kundensicht –
   und die reicht heute nur bis zur öffentlichen Website und zum eigenen Konto
   (`app/(public)/`, `components/account/`), nicht ins ERP. `Rolle supplier` sieht einen
   Auftrag **durch sein eigenes Beschaffungs-Modul** – dieselben Komponenten wie das
   Personal, nur ein anderer Ausschnitt. Die Verengung steht im **Backend**
   (`services/purchase.mine`, gelesen beim Aufbau der Antwort), nicht in der Oberfläche:
   ein Filter dort wäre eine Bitte, keine Grenze. Wer «sieht zu viel» meldet, sucht
   darum im Dienst, nicht in der Komponente.
3. **Fehlerzeile ernst nehmen.** Steht unter `**Fehler:**` etwas, ist das meist die
   eigentliche Ursache und nicht bloss Begleitrauschen.
4. **Datensatz nutzen.** `**Datensatz:** 100000123` nennt das Objekt, an dem es passiert
   ist – nützlich, um die Fachlogik im Backend zu prüfen.
5. **Umsetzen** wie jede andere Änderung: Regeln aus `CLAUDE.md`, bei UI-Arbeit vorher die
   Skill `inexxio-design-system`.

## Abschluss

- Im Commit die Notiz-Nummern nennen: `Testnotizen #12, #14: …`.
- Dem Nutzer am Ende die erledigten Nummern melden – er hakt sie im Widget ab (der Pin
  wird beim nächsten Testlauf grün, an genau derselben Stelle).
- Notizen, die **nicht** umgesetzt werden, ausdrücklich benennen und begründen, statt sie
  stillschweigend zu übergehen.

## Einordnung

Mehrere Notizen betreffen oft dieselbe Ursache – erst gruppieren, dann fixen. Umgekehrt
kann eine harmlos klingende Notiz eine Logiklücke sein: Bei allem, was Bestand, Geld oder
Status betrifft, die Fachregeln in `CLAUDE.md` prüfen, statt nur die Oberfläche zu
beruhigen.
