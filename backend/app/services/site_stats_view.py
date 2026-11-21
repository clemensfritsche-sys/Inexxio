"""**Die Auswertung der Website-Statistik** (``site_stats``) – eine Ableitung über ``site_hits``.

Ein **Besuch** ist ein Besucher an einem Tag (die Kennung wechselt jede Nacht). Gezählt wird
je Zeitraum (``days`` bis heute) und je Vorzeitraum gleicher Länge. Die Quelle benennt
``domain/site_sources`` beim Lesen – auch für alte Zeilen.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core import clock
from ..domain import site_sources as src
from ..domain.errors import Invalid
from ..models import Message
from . import record_labels

_VISIT = "day::text || visitor"


def _rows(db: Session, sql: str, s: date, e: date) -> list[Any]:
    return list(db.execute(text(sql), {"s": s, "e": e}))


def _totals(db: Session, s: date, e: date) -> dict[str, int]:
    r = _rows(db, f"""
        SELECT count(DISTINCT {_VISIT}) FILTER (WHERE kind = 'view') AS visits,
               count(*) FILTER (WHERE kind = 'view') AS views,
               count(*) FILTER (WHERE kind = 'inquiry') AS inquiries,
               count(*) FILTER (WHERE kind = 'call') AS calls,
               count(*) FILTER (WHERE kind = 'mail') AS mails,
               count(*) FILTER (WHERE kind = 'newsletter') AS newsletter
        FROM site_hits WHERE day BETWEEN :s AND :e""", s, e)[0]
    return {k: int(getattr(r, k) or 0) for k in ("visits", "views", "inquiries", "calls", "mails", "newsletter")}


def _series(db: Session, s: date, e: date) -> list[dict]:
    got = {r.day: r for r in _rows(db, f"""
        SELECT day, count(DISTINCT {_VISIT}) FILTER (WHERE kind = 'view') AS visits,
               count(*) FILTER (WHERE kind = 'inquiry') AS inquiries,
               count(*) FILTER (WHERE kind = 'call') AS calls
        FROM site_hits WHERE day BETWEEN :s AND :e GROUP BY day""", s, e)}
    out, d = [], s
    while d <= e:
        r = got.get(d)
        out.append({"day": d.isoformat(), "visits": int(r.visits) if r else 0,
                    "inquiries": int(r.inquiries) if r else 0, "calls": int(r.calls) if r else 0})
        d += timedelta(days=1)
    return out


def _sources(db: Session, s: date, e: date) -> list[dict]:
    """Je Quelle: Besuche (Einstiege) und was daraus wurde (Anfragen, Anrufe)."""
    acc: dict[str, dict] = {}

    def slot(so: src.Source) -> dict:
        return acc.setdefault(so.key, {"key": so.key, "label": so.label, "channel": so.channel,
                                       "visits": 0, "inquiries": 0, "calls": 0})
    for r in _rows(db, f"""SELECT ref_host, utm_source, count(DISTINCT {_VISIT}) AS n FROM site_hits
                           WHERE kind = 'view' AND entry AND day BETWEEN :s AND :e
                           GROUP BY 1, 2""", s, e):
        slot(src.source_of(r.ref_host, r.utm_source))["visits"] += int(r.n)
    for r in _rows(db, """SELECT ref_host, utm_source, entry_path IS NULL AS lost, kind, count(*) AS n
                          FROM site_hits WHERE kind IN ('inquiry', 'call') AND day BETWEEN :s AND :e
                          GROUP BY 1, 2, 3, 4""", s, e):
        so = src.UNKNOWN if r.lost else src.source_of(r.ref_host, r.utm_source)
        slot(so)["inquiries" if r.kind == "inquiry" else "calls"] += int(r.n)
    return sorted(acc.values(), key=lambda x: (-x["visits"], -x["inquiries"], x["label"]))


def _pages(db: Session, s: date, e: date) -> list[dict]:
    """Je Seite: Besuche, Einstiege, Lesezeit, Anrufe – und Anfragen, deren Besuch hier begann."""
    led = {r.entry_path: int(r.n) for r in _rows(db, """
        SELECT entry_path, count(*) AS n FROM site_hits
        WHERE kind = 'inquiry' AND entry_path IS NOT NULL AND day BETWEEN :s AND :e GROUP BY 1""", s, e)}
    rows = _rows(db, f"""
        SELECT path, count(DISTINCT {_VISIT}) FILTER (WHERE kind = 'view') AS visits,
               count(*) FILTER (WHERE kind = 'view') AS views,
               count(*) FILTER (WHERE kind = 'view' AND entry) AS entries,
               coalesce(sum(value) FILTER (WHERE kind = 'leave'), 0) AS seconds,
               count(*) FILTER (WHERE kind = 'call') AS calls,
               count(*) FILTER (WHERE kind = 'inquiry') AS sent
        FROM site_hits WHERE day BETWEEN :s AND :e AND kind IN ('view', 'leave', 'call', 'inquiry')
        GROUP BY path""", s, e)
    out = [{"path": r.path, "visits": int(r.visits), "entries": int(r.entries),
            "read_seconds": round(int(r.seconds) / int(r.views)) if r.views else 0,
            "calls": int(r.calls), "inquiries": led.get(r.path, 0), "sent": int(r.sent)}
           for r in rows]
    out = [p for p in out if p["visits"] or p["inquiries"] or p["sent"]]
    return sorted(out, key=lambda p: (-p["inquiries"], -p["sent"], -p["visits"], p["path"]))[:40]


def _split(db: Session, column: str, s: date, e: date) -> list[dict]:
    """Besuche (und Anfragen) je Land, Gerät oder Sprache."""
    rows = _rows(db, f"""
        SELECT {column} AS k, count(DISTINCT {_VISIT}) FILTER (WHERE kind = 'view') AS visits,
               count(*) FILTER (WHERE kind = 'inquiry') AS inquiries
        FROM site_hits WHERE day BETWEEN :s AND :e AND kind IN ('view', 'inquiry')
        GROUP BY 1""", s, e)
    return sorted(({"key": r.k or "", "visits": int(r.visits), "inquiries": int(r.inquiries)} for r in rows),
                  key=lambda x: (-x["visits"], -x["inquiries"], x["key"]))


def _funnel(db: Session, s: date, e: date, inquiries: int) -> dict[str, int]:
    r = _rows(db, f"""
        SELECT count(DISTINCT {_VISIT}) FILTER (WHERE kind = 'form_view') AS seen,
               count(DISTINCT {_VISIT}) FILTER (WHERE kind = 'form_start') AS started,
               count(DISTINCT {_VISIT}) FILTER (WHERE kind = 'form_step') AS step2
        FROM site_hits WHERE day BETWEEN :s AND :e
          AND kind IN ('form_view', 'form_start', 'form_step')""", s, e)[0]
    return {"seen": int(r.seen), "started": int(r.started), "step2": int(r.step2), "sent": inquiries}


def _speed(db: Session, s: date, e: date) -> dict[str, Any]:
    """Ladezeit wie Google sie misst: das 75. Perzentil (LCP in ms, CLS × 1000)."""
    by_device = {r.device: {"lcp": round(r.p75), "samples": int(r.n)} for r in _rows(db, """
        SELECT device, percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75, count(*) AS n
        FROM site_hits WHERE kind = 'lcp' AND day BETWEEN :s AND :e GROUP BY device""", s, e)}
    cls = _rows(db, """SELECT percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75 FROM site_hits
                       WHERE kind = 'cls' AND day BETWEEN :s AND :e""", s, e)[0].p75
    slow = [{"path": r.path, "lcp": round(r.p75), "samples": int(r.n)} for r in _rows(db, """
        SELECT path, percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75, count(*) AS n
        FROM site_hits WHERE kind = 'lcp' AND day BETWEEN :s AND :e
        GROUP BY path HAVING count(*) >= 5 ORDER BY 2 DESC LIMIT 5""", s, e)]
    return {"by_device": by_device, "cls": None if cls is None else round(cls), "slowest": slow}


def _inquiries(db: Session, s: date, e: date) -> list[dict]:
    rows = _rows(db, """SELECT created_at, message_id, ref_host, utm_source, entry_path, path, country
                        FROM site_hits WHERE kind = 'inquiry' AND day BETWEEN :s AND :e
                        ORDER BY id DESC LIMIT 50""", s, e)
    senders = {m.id: m.sender_object_id for m in db.query(Message).filter(
        Message.id.in_([r.message_id for r in rows if r.message_id])).all()}
    names = record_labels.labels(db, set(senders.values()))
    out = []
    for r in rows:
        oid = senders.get(r.message_id)
        so = src.UNKNOWN if r.entry_path is None else src.source_of(r.ref_host, r.utm_source)
        out.append({"at": r.created_at.isoformat(), "person_object_id": oid,
                    "person": names[oid].name if oid in names else None,
                    "source": so.label, "channel": so.channel, "entry_path": r.entry_path,
                    "path": r.path, "country": r.country})
    return out


def view(db: Session, days: int) -> dict[str, Any]:
    """►► Die ganze Auswertung eines Zeitraums – für den Reiter «Website» am Betreiber."""
    from .site_stats import PERIODS
    if days not in PERIODS:
        raise Invalid(f"Zeitraum «{days}» gibt es nicht – möglich sind {', '.join(map(str, PERIODS))} Tage.",
                      field="days")
    e = clock.today()
    s = e - timedelta(days=days - 1)
    now, before = _totals(db, s, e), _totals(db, s - timedelta(days=days), s - timedelta(days=1))
    return {
        "days": days, "start": s.isoformat(), "end": e.isoformat(),
        "totals": now, "previous": before,
        "series": _series(db, s, e),
        "sources": _sources(db, s, e),
        "channels": [{"key": k, "label": v} for k, v in src.CHANNELS.items()],
        "pages": _pages(db, s, e),
        "countries": _split(db, "country", s, e),
        "devices": _split(db, "device", s, e),
        "languages": _split(db, "lang", s, e),
        "funnel": _funnel(db, s, e, now["inquiries"]),
        "speed": _speed(db, s, e),
        "inquiries": _inquiries(db, s, e),
    }
