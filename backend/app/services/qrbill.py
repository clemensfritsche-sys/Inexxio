"""►►► **Die QR-Rechnung — damit eine Überweisung nicht abgetippt wird.** ◄◄◄

Gebaut ist die **Swiss QR-Rechnung** (Empfänger mit CH/LI-IBAN, Währung CHF oder EUR); der
EPC-QR für EUR an ausländische IBANs wäre später eine Datei mehr. **Wo sie nicht gilt, gibt
es keinen QR** – dann steht die Bankverbindung im Klartext mit dem Grund daneben.

**Die Referenz ist die Creditor Reference** (`RF…`, ISO 11649) aus unserer Rechnungsnummer –
ohne QR-IBAN gültig; die Zahlung kommt mit unserer Belegnummer zurück. Die Nutzlast entsteht
nur hier, nicht im Browser.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

import segno

#: Die Währungen, die die Swiss QR-Rechnung kennt.
CURRENCIES: tuple[str, ...] = ("CHF", "EUR")

#: Wo die Anschrift des Empfängers stehen muss (ohne IBAN und Ort keine gültige Nutzlast).
COUNTRIES: tuple[str, ...] = ("CH", "LI")

#: Der Kopf jeder Swiss-QR-Nutzlast (Version 2.0 der Implementation Guidelines).
_HEADER = ("SPC", "0200", "1")
_TRAILER = "EPD"

#: Höchstbetrag der Spezifikation.
MAX_AMOUNT = Decimal("999999999.99")


def reference(number: str) -> str:
    """**Creditor Reference** (`RF…`, ISO 11649) aus unserer Rechnungsnummer.

    Nur Buchstaben und Ziffern (`100000886-1` → `RF…1000008861`; die Objektnummer hat immer
    neun Stellen). Die Prüfziffern wie bei einer IBAN: `RF00` ans Ende, modulo 97.
    """
    body = "".join(c for c in number.upper() if c.isalnum())[:21]
    digits = "".join(str(int(c, 36)) if c.isalpha() else c for c in f"{body}RF00")
    return f"RF{98 - int(digits) % 97:02d}{body}"


def payload(*, iban: str, creditor: dict[str, Any], amount: Decimal, currency: str,
            debtor: Optional[dict[str, Any]], number: str) -> str:
    """Die Nutzlast – **einunddreissig Zeilen in fester Reihenfolge**, leere Zeilen
    eingeschlossen (der Endempfänger ist bei uns immer leer)."""
    lines = [
        *_HEADER,
        _plain(iban),
        # Empfänger – strukturierte Adresse (`S`): Strasse und Nummer getrennt.
        "S", creditor["name"], creditor.get("street") or "",
        creditor.get("street_nr") or "", creditor.get("zip") or "",
        creditor.get("city") or "", creditor.get("country") or "",
        # Endempfänger: sieben leere Zeilen.
        "", "", "", "", "", "", "",
        f"{amount:.2f}", currency,
    ]
    if complete(debtor):
        lines += ["S", debtor["name"], debtor.get("street") or "",
                  debtor.get("street_nr") or "", debtor.get("zip") or "",
                  debtor.get("city") or "", debtor.get("country") or ""]
    else:
        # Ohne **vollständige** Anschrift steht der Zahlende nicht da – leer heisst «trägt
        # sich selbst ein».
        lines += ["", "", "", "", "", "", ""]
    lines += ["SCOR", reference(number), "", _TRAILER]
    return "\n".join(lines)


def svg(text: str) -> str:
    """Der Code als **SVG** – mit dem Schweizerkreuz in der Mitte (Fehlerkorrektur `M`,
    beides von der Spezifikation verlangt). Die Grösse bestimmt der Kasten (``viewBox``,
    ``display:block``)."""
    matrix = [list(row) for row in segno.make(text, error="m").matrix]
    n = len(matrix)
    dots = " ".join(f"M{x} {y}h1v1h-1z"
                    for y, row in enumerate(matrix)
                    for x, on in enumerate(row) if on)
    # Das Kreuz misst 7 × 7 Prozent der Kantenlänge, in Modulen gerechnet.
    box = max(3.0, n * 0.14)
    off = (n - box) / 2
    arm, thick = box * 0.6, box * 0.2
    # **Die Ruhezone gehört zum Code** (vier Module, ISO/IEC 18004) – in der ``viewBox``,
    # damit sie mitskaliert.
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


def complete(party: Optional[dict[str, Any]]) -> bool:
    """**Ist diese Anschrift vollständig genug für die Nutzlast?** – Name, PLZ, Ort, Land."""
    return bool(party) and all(party.get(k) for k in ("name", "zip", "city", "country"))


def problem(*, iban: Optional[str], currency: str, amount: Decimal,
            creditor: dict[str, Any]) -> Optional[str]:
    """**Warum es hier keinen QR gibt** – oder ``None``.

    Zwei Formen einer Regel: dieselbe Prüfung nennt den Grund und verhindert den Code. Der
    Satz nennt den **Aussteller** (``creditor``) – an ihm fehlt, was fehlt.
    """
    issuer = f"«{creditor['name']}»" if creditor.get("name") else "der ausstellenden Gesellschaft"
    if not iban or not _plain(iban):
        return f"Ohne IBAN gibt es keinen Einzahlungsschein – sie fehlt bei {issuer}."
    if not complete(creditor):
        return (f"Ohne vollständige Anschrift (PLZ, Ort, Land) von {issuer} gibt es keinen "
                f"Einzahlungsschein.")
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
