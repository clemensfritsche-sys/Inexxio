"""Intelligente Artikelnamen-Vorschläge – bewusst OHNE KI (kostenlos, keine Latenz).

Artikelnamen sind frei wählbar (keine Katalog-Pflicht mehr). Damit trotzdem keine
Dubletten/Beinahe-Dubletten entstehen («Schraubendreher» vs. «Akkuschrauber»), schlägt
das System beim Tippen **bereits verwendete oder ähnliche** Namen vor. Die Ähnlichkeit
wird rein lexikalisch bestimmt (Trigramm-Jaccard + Substring-/Wortstamm-Bonus) – das
erkennt gemeinsame Wortstämme (z. B. «schraub») ohne teuren Modell-Aufruf. Für ~1'000
Artikel ist die Bewertung in Python vernachlässigbar (eine Aggregat-Query + O(n) Scoring)."""

import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Article
from ..schemas.article import ArticleNameSuggestion

_WORD_RE = re.compile(r"[a-z0-9äöü]+")
_MIN_SCORE = 0.12          # Ähnlichkeits-Schwelle, ab der ein Name vorgeschlagen wird
_STEM_LEN = 4             # gemeinsamer Wortstamm-Präfix (z. B. «schr…» / «bolz…»)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().strip())


def _trigrams(s: str) -> set[str]:
    s = _norm(s)
    if not s:
        return set()
    padded = f"  {s} "          # Randmarkierung: Präfixe/Suffixe zählen stärker
    return {padded[i:i + 3] for i in range(len(padded) - 2)}


def _similarity(query: str, candidate: str) -> float:
    """0..1 – wie ähnlich ist ``candidate`` der Eingabe ``query`` (lexikalisch)."""
    q, c = _norm(query), _norm(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    tq, tc = _trigrams(q), _trigrams(c)
    union = tq | tc
    jacc = len(tq & tc) / len(union) if union else 0.0
    # Zusatz-Signal: direkte Enthaltensein-/Wortstamm-Treffer (fängt «schraub» in
    # «Schraubendreher», auch wenn die Trigramm-Überlappung allein grenzwertig ist).
    if c.startswith(q) or q.startswith(c):
        bonus = 0.35
    elif q in c or c in q:
        bonus = 0.25
    else:
        bonus = 0.0
        for qt in _WORD_RE.findall(q):
            for ct in _WORD_RE.findall(c):
                if len(qt) >= _STEM_LEN and len(ct) >= _STEM_LEN and qt[:_STEM_LEN] == ct[:_STEM_LEN]:
                    bonus = max(bonus, 0.2)
    return min(1.0, jacc + bonus)


def _pool(db: Session) -> dict[str, int]:
    """Kandidaten-Namen mit Häufigkeit: bereits verwendete Artikelnamen (mit Anzahl) plus
    die optionale Admin-Vorschlagsliste (`company_settings.article_names`, Anzahl 0) als Seed."""
    rows = (
        db.query(Article.name, func.count(Article.id))
        .filter(Article.is_active == True, Article.name.isnot(None))
        .group_by(Article.name)
        .all()
    )
    counts: dict[str, int] = {name: int(cnt) for name, cnt in rows if name and name.strip()}
    from .admin import get_or_create_settings
    for n in (get_or_create_settings(db).article_names or []):
        if n and n.strip():
            counts.setdefault(n.strip(), 0)
    return counts


def suggest(db: Session, query: str, limit: int = 8) -> list[ArticleNameSuggestion]:
    """Namensvorschläge für die (Teil-)Eingabe ``query`` (leer → häufigste bestehende Namen)."""
    limit = max(1, min(limit, 20))
    counts = _pool(db)
    query = (query or "").strip()

    if not query:
        # Ohne Eingabe die am häufigsten verwendeten Namen anbieten (Wiederverwendung fördern).
        ranked = sorted(counts.keys(), key=lambda n: (-counts[n], n.lower()))
        return [ArticleNameSuggestion(name=n, count=counts[n]) for n in ranked[:limit]]

    scored: list[tuple[float, str]] = []
    for name in counts:
        s = _similarity(query, name)
        if s >= _MIN_SCORE:
            scored.append((s, name))
    # Sortierung: Ähnlichkeit ↓, dann Häufigkeit ↓ (etablierte Namen zuerst), dann alphabetisch.
    scored.sort(key=lambda t: (-t[0], -counts[t[1]], t[1].lower()))
    return [
        ArticleNameSuggestion(name=n, count=counts[n], score=round(s, 3))
        for s, n in scored[:limit]
    ]
