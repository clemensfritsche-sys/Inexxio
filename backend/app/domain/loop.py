"""►►► **Die Schlaufe** – ein Auftrag, der sich im Takt wiederholt (Projektakte
``docs/konzept/wiederkehr.md``). Hier steht der fachliche Kern: Takte, Kalender, Wahl je Zeile
und die Prüfung der Einstellung – **ohne Datenbank**. ◄◄◄

Die Regeln in einem Satz je (SYSTEM_LOGIC §5.10):

* eingeschaltet wird **nur im Entwurf**, mit der Freigabe ist die Schlaufe eingefroren;
* jeder Auftrag hat **höchstens einen Nachfolger**, eine **1:1-Kopie** mit derselben Schlaufe;
* ein Termin ist ein **Kalendertag** in Europe/Zurich; die erste Ausführung legt den Tag im
  Monat fest, ein kürzerer Monat nimmt seinen letzten Tag (wie ein Dauerauftrag);
* das Ende ist «unbefristet», ein Datum oder eine Anzahl Wiederholungen;
* je Lager-Zeile sagt der Mensch ausdrücklich, was die Wiederholung nimmt: **gleiche
  Einzelinstanzen** oder **FIFO** (ableiten lässt es sich nicht); eine Zeile «Neu» erzeugt jedes
  Mal neu.

Gespeichert ist eine Schlaufe als Ereignis ``loop.set`` am Auftrag (``services/loop``); die
Nutzlast ist genau die Form, die ``clean`` hier liefert.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any, Optional

from ..core import clock

#: ►► **Die Takte** – Schlüssel, Wort und Abstand in Monaten (Woche: 0 = sieben Tage). ◄◄
EVERY: dict[str, tuple[str, int]] = {
    "week": ("wöchentlich", 0),
    "month": ("monatlich", 1),
    "quarter": ("vierteljährlich", 3),
    "half": ("halbjährlich", 6),
    "year": ("jährlich", 12),
}

#: ►► **Was eine Wiederholung je Zeile nimmt.** ``new`` gibt es nur bei einer Zeile «Neu» und
#: wird nicht gewählt, sondern folgt aus ihr. ◄◄
SAME = "same"
FIFO = "fifo"
NEW = "new"
TAKES: dict[str, str] = {SAME: "gleiche Einzelinstanzen", FIFO: "FIFO", NEW: "neu erzeugt"}

#: ►► **Die Zustände einer Schlaufe** – Wort und Ampelton (``lib/status-tone.TONE``). Abgeleitet,
#: nie gespeichert (``services/loop.view``). ◄◄
STATES: dict[str, tuple[str, str]] = {
    "run": ("läuft", "done"),
    "wait": ("wartet", "pending"),
    "stuck": ("geht nicht mehr", "danger"),
    "ended": ("beendet", "danger"),
    "done": ("abgeschlossen", "done"),
    "continued": ("weiter im Nachfolger", "done"),
}

#: Mehr Wiederholungen nach Anzahl sind kein Dauerauftrag mehr, sondern ein Tippfehler.
MAX_COUNT = 1000


def label(every: Optional[str]) -> str:
    return EVERY.get(every or "", ("", 0))[0]


def _months_later(day: date, months: int, anchor: int) -> date:
    """``months`` Kalendermonate später, am Tag ``anchor`` – oder am letzten Tag des Monats."""
    total = day.month - 1 + months
    year, month = day.year + total // 12, total % 12 + 1
    return date(year, month, min(anchor, calendar.monthrange(year, month)[1]))


def after(day: date, every: str, anchor: int) -> date:
    """►► **Der nächste Termin nach ``day``.** Monatlich und länger am Tag ``anchor`` (der Tag
    der ersten Ausführung) – fehlt er im Monat, der letzte Tag; wöchentlich sieben Tage. ◄◄"""
    months = EVERY[every][1]
    if months == 0:
        return day + timedelta(days=7)
    return _months_later(day, months, anchor)


def sentence(loop: dict[str, Any]) -> str:
    """**Die Schlaufe in einem Satz** – derselbe in der Karte und auf dem Papier."""
    parts = [f"{label(loop.get('every'))}, nächste am {_day(loop.get('next'))}"]
    if loop.get("until"):
        parts.append(f"bis {_day(loop['until'])}")
    elif loop.get("left") is not None:
        n = int(loop["left"])
        parts.append(f"noch {n} {'Mal' if n == 1 else 'Male'}")
    else:
        parts.append("bis auf Widerruf")
    return ", ".join(parts)


def _day(value: Any) -> str:
    d = value if isinstance(value, date) else date.fromisoformat(str(value))
    return clock.day(d)


def go_on(loop: dict[str, Any]) -> bool:
    """**Gibt es noch einen Nachfolger?** Nein, wenn die Anzahl erreicht oder das Enddatum
    vorbei ist – dann endet die Kette von selbst."""
    if loop.get("left") is not None and int(loop["left"]) <= 0:
        return False
    if loop.get("until") and date.fromisoformat(str(loop["next"])) > \
            date.fromisoformat(str(loop["until"])):
        return False
    return True


def follow(loop: dict[str, Any]) -> dict[str, Any]:
    """►► **Die Schlaufe des Nachfolgers**: dieselbe Einstellung, der nächste Termin, bei «nach
    Anzahl» eins weniger. ◄◄"""
    nxt = date.fromisoformat(str(loop["next"]))
    out = dict(loop)
    out["next"] = after(nxt, loop["every"], int(loop["anchor"])).isoformat()
    if loop.get("left") is not None:
        out["left"] = int(loop["left"]) - 1
    return out


def problems(raw: Any, origins: list[str], today: date) -> list[str]:
    """►►► **Was an einer Schlaufe im Entwurf fehlt** – als Sätze, wie ``validate_draft``. ◄◄◄
    Die zweite Form derselben Regel ist ``clean`` (wirft beim ersten Satz)."""
    if raw in (None, {}, ""):
        return []
    if not isinstance(raw, dict):
        return ["Die Wiederholung ist unlesbar."]
    out: list[str] = []
    if raw.get("every") not in EVERY:
        out.append("Wie oft wiederholt sich der Auftrag?")
    first = _date(raw.get("first"))
    if first is None:
        out.append("Wann ist die erste Wiederholung?")
    elif first < today:
        out.append("Die erste Wiederholung liegt in der Vergangenheit – sie ist heute oder später.")
    until = _date(raw.get("until")) if raw.get("until") else None
    if raw.get("until") and until is None:
        out.append(f"«{raw.get('until')}» ist kein Datum.")
    if until is not None and first is not None and until < first:
        out.append("Das Ende liegt vor der ersten Wiederholung.")
    count = raw.get("count")
    if count not in (None, ""):
        try:
            n = int(count)
        except (TypeError, ValueError):
            n = 0
        if not 1 <= n <= MAX_COUNT:
            out.append(f"Die Anzahl Wiederholungen liegt zwischen 1 und {MAX_COUNT}.")
    if until is not None and count not in (None, ""):
        out.append("Das Ende ist ein Datum oder eine Anzahl, nicht beides.")
    takes = raw.get("takes") or []
    for i, origin in enumerate(origins):
        if origin != "lager":
            continue
        take = takes[i] if i < len(takes) else None
        if take not in (SAME, FIFO):
            out.append(f"Zeile {i + 1}: Was nimmt die Wiederholung – gleiche Einzelinstanzen "
                       f"oder FIFO?")
    return out


def clean(raw: Any, lines: list[dict[str, Any]], today: date) -> Optional[dict[str, Any]]:
    """►► **Die Schlaufe, wie sie mit der Freigabe eingefroren wird** – oder ``None``. ◄◄

    ``lines`` sind die Zeilen des Entwurfs (``origin``, ``units`` mit ``number``). «Gleiche
    Einzelinstanzen» friert die gewählten Nummern ein: Stücke hängen nicht an Zeilen, darum
    sagt die Schlaufe selbst, welche es sind.
    """
    found = problems(raw, [str(ln.get("origin")) for ln in lines], today)
    if found:
        raise ValueError(found[0])
    if raw in (None, {}, ""):
        return None
    first = _date(raw["first"])
    takes = raw.get("takes") or []
    rows: list[dict[str, Any]] = []
    for i, ln in enumerate(lines):
        if ln.get("origin") != "lager":
            rows.append({"take": NEW})
        elif takes[i] == SAME:
            rows.append({"take": SAME,
                         "units": [str(u.get("number")) for u in ln.get("units") or []]})
        else:
            rows.append({"take": FIFO})
    count = raw.get("count")
    return {
        "every": raw["every"],
        "next": first.isoformat(),
        "anchor": first.day,
        "until": _date(raw["until"]).isoformat() if raw.get("until") else None,
        "left": int(count) if count not in (None, "") else None,
        "lines": rows,
    }


def _date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None
