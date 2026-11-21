"""►►► **Woher kommt ein Besuch?** – die eine Regel für die Website-Statistik. ◄◄◄

Gespeichert wird nur, was der Browser sagt: der Rechnername der Seite, von der jemand kam
(``ref_host``), und die Kampagnen-Angaben der Adresse (``utm_source``). Benannt wird **beim
Lesen** (``source_of``) – eine neue Suchmaschine oder ein neuer KI-Assistent hier eingetragen
gilt damit auch rückwirkend.

**Nichts geht verloren**: was keine Regel kennt, ist ein Verweis und heisst wie sein
Rechnername («verband.ch»). So steht jede Quelle in der Statistik, auch eine, die es heute noch
nicht gibt.
"""

from __future__ import annotations

import re
from typing import NamedTuple

#: Die Arten von Quellen, in dieser Reihenfolge gezeigt.
CHANNELS: dict[str, str] = {
    "search": "Suchmaschine",
    "ai": "KI-Assistent",
    "direct": "Direkt",
    "social": "Soziale Medien",
    "mail": "E-Mail",
    "campaign": "Kampagne",
    "referral": "Verweis",
    "unknown": "Unbekannt",
}


class Source(NamedTuple):
    key: str        # stabil, z. B. «google» oder der Rechnername
    label: str      # wie gezeigt
    channel: str    # Schlüssel aus CHANNELS


#: (Muster auf den Rechnernamen ohne «www.», Schlüssel, Name, Art) – der erste Treffer gilt.
#: Reihenfolge zählt: «gemini.google.com» vor «google.».
RULES: tuple[tuple[str, str, str, str], ...] = (
    # KI-Assistenten
    (r"^(chatgpt\.com|chat\.openai\.com|openai\.com)$", "chatgpt", "ChatGPT", "ai"),
    (r"(^|\.)perplexity\.ai$", "perplexity", "Perplexity", "ai"),
    (r"^claude\.ai$", "claude", "Claude", "ai"),
    (r"^(gemini\.google\.com|bard\.google\.com)$", "gemini", "Gemini", "ai"),
    (r"^copilot\.(microsoft\.com|cloud\.microsoft)$", "copilot", "Copilot", "ai"),
    (r"^(grok\.com|x\.ai)$", "grok", "Grok", "ai"),
    (r"^chat\.mistral\.ai$", "mistral", "Le Chat", "ai"),
    (r"^(chat\.)?deepseek\.com$", "deepseek", "DeepSeek", "ai"),
    (r"^meta\.ai$", "meta-ai", "Meta AI", "ai"),
    (r"^(you\.com|phind\.com|poe\.com)$", "ai-other", "Andere KI", "ai"),
    # Suchmaschinen
    (r"(^|\.)google\.[a-z.]+$", "google", "Google", "search"),
    (r"(^|\.)bing\.com$", "bing", "Bing", "search"),
    (r"(^|\.)duckduckgo\.com$", "duckduckgo", "DuckDuckGo", "search"),
    (r"(^|\.)ecosia\.org$", "ecosia", "Ecosia", "search"),
    (r"(^|\.)search\.brave\.com$", "brave", "Brave Search", "search"),
    (r"(^|\.)(search\.yahoo\.com|yahoo\.com)$", "yahoo", "Yahoo", "search"),
    (r"(^|\.)(startpage\.com|qwant\.com|yandex\.[a-z]+|baidu\.com|swisscows\.com|search\.ch|local\.ch)$",
     "search-other", "Andere Suche", "search"),
    # Soziale Medien
    (r"(^|\.)(facebook\.com|fb\.com|m\.facebook\.com|l\.facebook\.com)$", "facebook", "Facebook", "social"),
    (r"(^|\.)instagram\.com$", "instagram", "Instagram", "social"),
    (r"(^|\.)(linkedin\.com|lnkd\.in)$", "linkedin", "LinkedIn", "social"),
    (r"(^|\.)(youtube\.com|youtu\.be)$", "youtube", "YouTube", "social"),
    (r"(^|\.)(x\.com|twitter\.com|t\.co)$", "x", "X", "social"),
    (r"(^|\.)tiktok\.com$", "tiktok", "TikTok", "social"),
    (r"(^|\.)(whatsapp\.com|wa\.me)$", "whatsapp", "WhatsApp", "social"),
    # E-Mail (Webmail)
    (r"^(mail\.google\.com|outlook\.live\.com|outlook\.office\.com|outlook\.office365\.com|mail\.yahoo\.com|"
     r"webmail\.[a-z0-9.-]+|mail\.[a-z0-9-]+\.ch)$", "mail", "E-Mail", "mail"),
)
_COMPILED = tuple((re.compile(p), k, n, c) for p, k, n, c in RULES)

#: Kampagnen-Werte, die einen Dienst meinen (``utm_source=chatgpt.com``, ``…=newsletter``).
_UTM_ALIASES = {"newsletter": ("newsletter", "Newsletter", "mail"),
                "email": ("mail", "E-Mail", "mail"), "mail": ("mail", "E-Mail", "mail")}

DIRECT = Source("direct", "Direkt / Lesezeichen", "direct")
#: Eine Anfrage ohne gezählten Besuch (Skript blockiert, Formular ohne JavaScript).
UNKNOWN = Source("unknown", "Ohne gezählten Besuch", "unknown")


def host_of(value: str | None) -> str:
    """Rechnername in Kleinbuchstaben, ohne «www.» und Port – leer, wenn keiner."""
    h = (value or "").strip().lower()
    h = re.sub(r"^[a-z][a-z0-9+.-]*://", "", h).split("/")[0].split("?")[0].split(":")[0]
    h = h[4:] if h.startswith("www.") else h
    return h if re.fullmatch(r"[a-z0-9.-]{1,120}", h) and "." in h else ""


def _by_host(host: str) -> Source | None:
    for rx, key, label, channel in _COMPILED:
        if rx.search(host):
            return Source(key, label, channel)
    return None


def source_of(ref_host: str | None, utm_source: str | None = None) -> Source:
    """►► Die Quelle eines Besuchs. Kampagne vor Verweis (wer einen Link mit ``utm_source``
    baut, sagt selbst, woher er stammt); ein bekannter Dienst bleibt dabei der Dienst."""
    utm = (utm_source or "").strip().lower()
    if utm:
        known = _by_host(host_of(utm)) if host_of(utm) else None
        if known:
            return known
        alias = _UTM_ALIASES.get(utm)
        if alias:
            return Source(*alias)
        return Source(f"utm:{utm[:60]}", utm[:60], "campaign")
    host = host_of(ref_host)
    if not host:
        return DIRECT
    return _by_host(host) or Source(host, host, "referral")
