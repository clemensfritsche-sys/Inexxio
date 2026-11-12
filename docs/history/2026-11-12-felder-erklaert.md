# Rundenbericht: Das Feld erklärt sich (12.11.2026)

Anlass: ein Gespräch, in dem die KI einen Kaufartikel (PB Swiss Tools, Galaxus) vorbereitete. Sie
erfand nichts, kannte aber die Regeln des ERP nicht: Name über 32 Zeichen (still gekürzt),
Abmessungen erst richtig (`36x70`), dann «korrigiert» auf `70x36` (abgewiesen), der Shop-Link im
falschen Feld, eine Firma als Partner der Zahlung, kein Verketten der Vorschläge, und das Web nur,
wenn ein Link im Gespräch stand.

## Ursache, gemessen

Von den Feldern, die die KI ausfüllen kann (51 Handlungen, 280 Angaben), hatten **269 keine
Beschreibung** – die KI sah «size: string». Die Regeln standen nur im Prüfcode. Dazu: der Name wurde
still gekürzt (der Probelauf merkte nichts), eine 422 nannte ihr Feld nicht, und die Regel der
Abmessungen stand zweimal (Backend und `lib/article.ts`) – beide erlaubten zwei Masse.

## Entscheid (Inhaber)

Keine Regeln für die KI («wenn das, dann das»), sondern: das System erklärt sich selbst. Die KI liest
nicht den Code (zu gross, zu teuer, nicht der Vertrag).

## Was gebaut ist

- **Jedes Feld einer Handlung beschreibt sich** (`Field(description=…)`; Listen aus der Fachschicht
  erzeugt: Kanäle, Takte, Absenzarten, Zahlungswege, Eigentum). Wächter: jedes Feld beschrieben.
- **Nie still kürzen**: ein zu langer Name wird abgewiesen («höchstens 32 Zeichen (jetzt 49)»).
  Wächter: jedes Textfeld jeder Handlung mit 5000 Zeichen – abgewiesen oder unverändert.
- **Jede Abweisung nennt ihr Feld**: 422 trägt `field` und `fields`; das Artikel-Formular zeigt die
  Sätze des Servers am Feld, `lib/article.ts` prüft nichts mehr selbst (eine Regel statt zwei).
- **Abmessungen**: genau drei Masse in mm, aufsteigend (`SIZE_PATTERN`, auch im Schema). Gewicht
  liest `domain/number` («0,327»).
- **Partner ist immer eine Person** (`voucher_input.party_problem` ↔ `assert_party`), geprüft schon
  beim Modellieren (Artikel-Vorlage, Auftrag) und mit einem Satz, der die Firma nennt.
- **Lieferantenartikel-Nr. entmappt** (`PENDING_DROP`): «Wie bestellen?» je Partner am Zahlungsmodul
  ersetzt sie. Spalte fällt im nächsten Deploy.
- **Websuche im Gespräch** (`web_search_20260209`, höchstens drei je Antwort, 1 Rappen je Suche unter
  dem Deckel; nie bei Mails). Schritt «sucht im Web …».
- **Vorschlag-Karte hinter der Antwort** desselben Zugs (`capture-sheet.TalkView`).

## Geprüft

Backend 873 grün (neu `tests/test_felder_erklaert.py`, je Wächter gegen die Bug-Form geprüft:
Beschreibungen fehlten, Name gekürzt, 422 ohne Feld), ruff sauber; Frontend type-check, lint, 166
Tests grün; generierte Dateien neu. Nicht im laufenden ERP angesehen.

## Offen

- Zwei Links im Zahlungsmodul: «Wie bestellen?» je Partner (dauerhaft, am Modul) und «Link» an der
  Offerte (je Vorgang, z. B. Warenkorb). Entscheid, ob beide bleiben.
- Bestehende Artikel mit zwei Massen bleiben, wie sie sind (ein Artikel ändert sich nicht).
