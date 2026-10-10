"""►►► **Die QR-Rechnung — damit eine Überweisung nicht abgetippt wird.** ◄◄◄

*«Am besten einen international gültigen QR-Code, welcher vom Kunden gescannt werden
kann, damit man die Überweisung teilautomatisch machen kann – also ohne manuelle Eingabe
ins E-Banking.»* (Testnotiz #865)

**Die ehrliche Antwort auf «international gültig»: einen weltweiten Standard gibt es
nicht.** Es gibt zwei, und einer davon deckt unseren Fall vollständig ab:

* die **Swiss QR-Rechnung** (Pflicht seit 10/2022, jede Schweizer Banking-App liest sie) –
  Empfänger mit CH/LI-IBAN, Währung **CHF oder EUR**. Das sind wir.
* der **EPC-QR / GiroCode** für EUR an ausländische IBANs (verbreitet in DE/AT) –
  dieselbe Mechanik, eine andere Nutzlast. Später eine Datei mehr, kein Umbau.

Gebaut ist der erste. **Und wo er nicht gilt, gibt es ihn nicht** (fremde Währung, keine
CH-IBAN): dann steht die Bankverbindung im Klartext da, mit dem Grund daneben. Ein QR, der
in der App des Kunden einen Fehler wirft, wäre schlimmer als keiner.

**Die Referenz ist die Creditor Reference** (`RF…`, ISO 11649) aus unserer
Rechnungsnummer – strukturiert, international gültig und **ohne QR-IBAN**: die muss man
bei der Bank bestellen, und ohne sie ist die schweizerische QR-Referenz gar nicht erlaubt.
So kommt die Zahlung mit unserer Belegnummer zurück, und niemand tippt sie ab.

**Der Code wird hier erzeugt, nicht im Browser**: die Nutzlast ist eine Liste von
einunddreissig Zeilen in fester Reihenfolge – eine zweite Fassung im Frontend wäre die
Stelle, an der beim nächsten Feld eine Zeile verrutscht, und das sieht man einem QR nicht
an.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

import segno

#: Die Währungen, die die Swiss QR-Rechnung kennt. Mehr sind es nicht – und ein QR über
#: einen Yen-Betrag wäre keine Toleranzfrage, sondern ein Beleg, den keine Bank annimmt.
CURRENCIES: tuple[str, ...] = ("CHF", "EUR")

#: Wo die Anschrift des Empfängers stehen muss. Ohne IBAN gibt es keine Überweisung, und
#: ohne Ort keine gültige Nutzlast.
COUNTRIES: tuple[str, ...] = ("CH", "LI")

#: Der Kopf jeder Swiss-QR-Nutzlast (Version 2.0 der Implementation Guidelines).
_HEADER = ("SPC", "0200", "1")
_TRAILER = "EPD"

#: Höchstbetrag der Spezifikation – darüber ist es keine Zahlung, sondern ein Tippfehler.
MAX_AMOUNT = Decimal("999999999.99")


def reference(number: str) -> str:
    """**Creditor Reference** (`RF…`, ISO 11649) aus unserer Rechnungsnummer.

    Erlaubt sind nur Buchstaben und Ziffern, also fällt der Trennstrich weg
    (`100000886-1` → `RF…1000008861`). Eindeutig bleibt es trotzdem: eine Objektnummer hat
    immer neun Stellen, der Rest ist die laufende Nummer.

    Die zwei Prüfziffern rechnen sich wie bei einer IBAN – `RF00` ans Ende, Buchstaben zu
    Zahlen, Rest modulo 97. Ohne sie nimmt keine Bank die Referenz an.
    """
    body = "".join(c for c in number.upper() if c.isalnum())[:21]
    digits = "".join(str(int(c, 36)) if c.isalpha() else c for c in f"{body}RF00")
    return f"RF{98 - int(digits) % 97:02d}{body}"


def payload(*, iban: str, creditor: dict[str, Any], amount: Decimal, currency: str,
            debtor: Optional[dict[str, Any]], number: str) -> str:
    """Die Nutzlast – **einunddreissig Zeilen in fester Reihenfolge**.

    Die Reihenfolge ist der Standard; sie zu «verbessern» hiesse, einen Code zu drucken,
    den niemand liest. Leere Zeilen sind Teil davon (der *Endempfänger* ist bei uns immer
    leer) – wer sie weglässt, verschiebt alles danach.
    """
    lines = [
        *_HEADER,
        _plain(iban),
        # Empfänger – strukturierte Adresse (`S`): Strasse und Nummer getrennt.
        "S", creditor["name"], creditor.get("street") or "",
        creditor.get("street_nr") or "", creditor.get("zip") or "",
        creditor.get("city") or "", creditor.get("country") or "CH",
        # Endempfänger: sieben leere Zeilen. Er ist für Sammelaufträge gedacht und
        # bleibt hier leer – ein erfundener Wert wäre eine Behauptung über ein Konto.
        "", "", "", "", "", "", "",
        f"{amount:.2f}", currency,
    ]
    if debtor and debtor.get("name"):
        lines += ["S", debtor["name"], debtor.get("street") or "",
                  debtor.get("street_nr") or "", debtor.get("zip") or "",
                  debtor.get("city") or "", debtor.get("country") or ""]
    else:
        # **Ohne vollständige Adresse steht der Zahlende NICHT da.** Eine halbe Anschrift
        # macht die Nutzlast ungültig; leer heisst «der Zahlende trägt sich selbst ein»,
        # und genau das tut seine App ohnehin.
        lines += ["", "", "", "", "", "", ""]
    lines += ["SCOR", reference(number), "", _TRAILER]
    return "\n".join(lines)


def svg(text: str) -> str:
    """Der Code als **SVG** – mit dem Schweizerkreuz in der Mitte.

    Selbst gezeichnet statt aus der Bibliothek geholt: das Kreuz gehört zur Spezifikation
    (daran erkennt eine App, dass es eine QR-Rechnung ist), und die Fehlerkorrektur `M`
    ist genau dafür vorgeschrieben. Ein Bild ohne Kreuz wäre ein QR-Code, der zufällig
    dieselben Daten trägt.

    ►►► **Wie GROSS er ist, entscheidet die Stelle, an der er steht** (Testnotiz #872).
    ◄◄◄

    Er trug einmal eine feste Kantenlänge (``size = 240``) und stand damit in einem
    168 px breiten Kasten: 72 px zu breit, also ragte er heraus und sass sichtbar
    ausser der Mitte. Eine zweite Zahl im Backend, die zur Breite im Browser passen
    muss, geht beim ersten Umbau auseinander – und ein QR ohne Rand ist zudem einer,
    den manche App nicht mehr liest.

    Jetzt sagt das Bild nur noch sein **Seitenverhältnis** (``viewBox``, quadratisch)
    und füllt seinen Kasten. ``display:block`` gehört dazu: als Inline-Element bekäme es
    darunter die Grundlinien-Lücke, und schon stünde es wieder nicht mittig.
    """
    matrix = [list(row) for row in segno.make(text, error="m").matrix]
    n = len(matrix)
    dots = " ".join(f"M{x} {y}h1v1h-1z"
                    for y, row in enumerate(matrix)
                    for x, on in enumerate(row) if on)
    # Das Kreuz misst 7 × 7 Prozent der Kantenlänge – in Modulen gerechnet, damit es auf
    # jeder Grösse an derselben Stelle sitzt.
    box = max(3.0, n * 0.14)
    off = (n - box) / 2
    arm, thick = box * 0.6, box * 0.2
    # **Die Ruhezone gehört zum Code**, nicht zum Layout drumherum: vier Module ringsum
    # (ISO/IEC 18004), sonst liest ihn eine App auf einem farbigen Grund nicht mehr. Sie
    # steht in der ``viewBox``, damit sie mitskaliert – als Polsterung im Browser wäre sie
    # die zweite Stelle, an der jemand sie wegoptimiert.
    quiet, span = 4, n + 8
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{-quiet} {-quiet} {span} {span}" '
        f'style="display:block;width:100%;height:auto" '
        f'role="img" aria-label="QR-Rechnung">'
        f'<rect x="{-quiet}" y="{-quiet}" width="{span}" height="{span}" fill="#fff"/>'
        f'<path d="{dots}" fill="#000"/>'
        f'<rect x="{off:.2f}" y="{off:.2f}" width="{box:.2f}" height="{box:.2f}" '
        f'fill="#000" stroke="#fff" stroke-width="{box * 0.06:.2f}"/>'
        f'<rect x="{off + (box - thick) / 2:.2f}" y="{off + (box - arm) / 2:.2f}" '
        f'width="{thick:.2f}" height="{arm:.2f}" fill="#fff"/>'
        f'<rect x="{off + (box - arm) / 2:.2f}" y="{off + (box - thick) / 2:.2f}" '
        f'width="{arm:.2f}" height="{thick:.2f}" fill="#fff"/>'
        f'</svg>'
    )


def problem(*, iban: Optional[str], currency: str, amount: Decimal) -> Optional[str]:
    """**Warum es hier keinen QR gibt** – oder ``None``.

    Zwei Formen einer Regel, ein Namensstamm (wie ``pick_problem``/``unpickable`` im
    Prozess): dieselbe Prüfung nennt den Grund und verhindert den Code. Ohne den Grund
    stünde an einer EUR-Rechnung eine leere Fläche, und niemand wüsste, ob sie fehlt oder
    lädt.
    """
    if not iban or not _plain(iban):
        return ("Ohne IBAN gibt es keinen Einzahlungsschein – sie steht am Unternehmen, "
                "das die Website betreibt.")
    if _plain(iban)[:2] not in COUNTRIES:
        return ("Die QR-Rechnung gilt für Konten in der Schweiz und in Liechtenstein; "
                "für andere Länder steht die Bankverbindung im Klartext daneben.")
    if currency not in CURRENCIES:
        return (f"Die QR-Rechnung kennt nur {' und '.join(CURRENCIES)} – "
                f"dieser Beleg lautet auf {currency}.")
    if not Decimal("0") < amount <= MAX_AMOUNT:
        return "Ein Einzahlungsschein trägt einen positiven Betrag."
    return None


def _plain(iban: str) -> str:
    """Eine IBAN ohne Zwischenräume – so steht sie in der Nutzlast."""
    return "".join(iban.split()).upper()
