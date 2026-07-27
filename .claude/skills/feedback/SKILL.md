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
## #12 · /erp?open=100000123

> Der Freigeben-Knopf sollte hier ausgegraut sein

- **Element:** «Freigeben» (`button`)
- **Selektor:** `div > div:nth-of-type(2) > button`
- **Datensatz:** 100000123
- **Umgebung:** Rolle employee · 1440x900 · Build a1b2c3d4
- **Fehler:** TypeError: x is undefined (page-3f2.js:1)
```

## Vorgehen je Notiz

1. **Code-Stelle finden.** Der sichtbare Text ist der stärkste Anker – die Oberfläche ist
   deutschsprachig, Beschriftungen stehen meist genau einmal im Repository:
   `rg -n "Freigeben" frontend/src`. Grenzt die Route ein: `/erp` →
   `frontend/src/app/(erp)/`, `/konto` → `components/account/`, `/shop` → `(public)/shop/`.
   Hilft der Text nicht (Icon-Knopf), das `outerHTML` und den Selektor heranziehen.
2. **Rolle beachten.** `Rolle customer` heisst: der Befund gilt für die Kundensicht –
   nicht in ERP-Komponenten suchen, sondern in Shop/Konto.
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
