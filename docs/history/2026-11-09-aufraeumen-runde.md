# Aufräumen – Runde vom 09.11.2026 (B1–B7, C1–C5)

Grundlage: Gesamtdurchsicht (`docs/aenderungsakte.md` §6), Entscheid des Inhabers vom selben Tag.

## Was, warum

| Punkt | Was | Warum |
|---|---|---|
| B1 | `objects.TYPES` (Typ → Tabelle, Wort); `record_labels.labels` fragt zuerst die Registry | Dieselbe Tabelle stand dreimal; ein Name kostete sechs Abfragen, jetzt zwei (gemessen, `test_record_labels`) |
| B2 | `ai_tools.record` liest über `ai_tools.ROUTES` → `handgriff.look` (in der Sitzung der KI, hinter einem Sicherungspunkt) | Vorher rohe Spalten mit einer Ausschlussliste – jede neue Spalte ging ungefragt an die KI |
| B3 | Soll-Ist liest Zahlen über `domain/number` | «1'250» war «fehlt» |
| B4 | `require_employee`/`require_admin` lesen `policy.RULES` (`erp` · `admin`); Rollen-Literale nur in `policy` | Eine Tür prüfte an der Regeltabelle vorbei |
| B5 | `core/locks`: Räume, Schlüssel, `xact` · `hold` | Sechs magische Zahlen in fünf Dateien, zwei Arten SQL |
| B6 | `core/clock.utcnow` · `day` · `stamp` | 4× `_now`, 22× `datetime.now`, 9× eigenes Tagesformat |
| B7 | Website-Anfrage: eine Datenform, Prüfung im Dienst; `document.py` → `a4.py`, `records.py` → `record_labels.py`; toter Parameter, falsche Docstrings, `signed.BadLink` | Zwei `Inquiry`/`Photo` mit Umwandlung; verwechselbare Namen |
| C1 | `module-ui.Actions`, `.btn-primary`, `.erp-partyrow` weg | tot |
| C2 | jede Handlung über `useAction`; kein Netz = `ApiError` `offline` | ~20× eigenes `busy`; Netzfehler per Textvergleich |
| C3 | `useOutside`, ein `Label`, Entwurf/Scanner als Dialog, `NOTHING`, `Amount` | je Muster mehrere Bauarten |
| Hover | eine Blase (`hints.TipHost`, Portal am `body`) | uneinheitlich, abgeschnitten, Versalien geerbt |
| Kopf | Preflight in `.ix-shell` zurückgenommen, `lang="de-CH"` | 1 px Laufweite, Symbol-Höhe; Glas bleibt bewusst verschieden |
| C4 | `lib/api.ts` aus `paths` getippt (`call`, `In`, `Res`) | Pfad, Methode, Werte, Antwort ungeprüft |
| C5 | Spiegel erzeugt (`dump_vocab.py` → `vocab.ts`); ~150 Textsuch-Tests aufgelöst | «Tests prüfen Verhalten, nicht Quelltext» |

## Gemessen
- Backend 787 Tests, Frontend 157, Website 17 – grün; jeder neue Wächter einmal am echten Code
  gebrochen (Liste in `2026-11-09-tests-neu.md`).
- `api.ts`: 1'133 → 1'159 Zeilen. Die angekündigte Einsparung (~70 %) trat **nicht** ein – die
  benannten Methoden bleiben die eine Stelle der Pfade; der Gewinn ist die Prüfung durch den Compiler.

## Funde unterwegs
- Ursprungsland nur im Editor grossgeschrieben → `ArticleCreate` normt es.
- `articleNameSuggestions` schickte `limit`, das das Backend nie annahm.
- `HoldNumbers.numbers` ist optional – die Oberfläche nahm es als immer da an.
- Doppelklick bei Senden/Löschen eines Dokuments löste doppelt aus; Bezahlknopf blieb nach Fehler gesperrt.

## Verworfen
- KI-Kosten als `Decimal`, Abschaffen des alten Link-Schlüssels (Akte §6, Entscheid).
- `openapi-fetch`: bringt eigene Fetch-Schicht; Wiederholung, 401 und Ereignisse hätten neu gebaut werden müssen.
- Name `paper.py`: kollidiert mit lokalen Variablen `paper` → `a4.py`.
