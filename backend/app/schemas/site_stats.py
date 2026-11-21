"""Die Antwort der Website-Statistik (``services/site_stats_view.view``)."""

from typing import Optional

from pydantic import BaseModel


class SiteTotals(BaseModel):
    visits: int
    views: int
    inquiries: int
    calls: int
    mails: int
    newsletter: int


class SiteDay(BaseModel):
    day: str
    visits: int
    inquiries: int
    calls: int


class SiteSource(BaseModel):
    key: str
    label: str
    channel: str
    visits: int
    inquiries: int
    calls: int


class SiteChannel(BaseModel):
    key: str
    label: str


class SitePage(BaseModel):
    path: str
    visits: int
    entries: int
    read_seconds: int
    calls: int
    #: Anfragen, deren Besuch auf dieser Seite begann.
    inquiries: int
    #: Anfragen, die auf dieser Seite gesendet wurden.
    sent: int


class SiteSplit(BaseModel):
    key: str
    visits: int
    inquiries: int


class SiteFunnel(BaseModel):
    seen: int
    started: int
    step2: int
    sent: int


class SiteLcp(BaseModel):
    lcp: int
    samples: int


class SiteSlowPage(BaseModel):
    path: str
    lcp: int
    samples: int


class SiteSpeed(BaseModel):
    by_device: dict[str, SiteLcp]
    cls: Optional[int]
    slowest: list[SiteSlowPage]


class SiteInquiry(BaseModel):
    at: str
    person_object_id: Optional[int]
    person: Optional[str]
    source: str
    channel: str
    entry_path: Optional[str]
    path: str
    country: Optional[str]


class SiteStatsOut(BaseModel):
    days: int
    start: str
    end: str
    totals: SiteTotals
    previous: SiteTotals
    series: list[SiteDay]
    sources: list[SiteSource]
    channels: list[SiteChannel]
    pages: list[SitePage]
    countries: list[SiteSplit]
    devices: list[SiteSplit]
    languages: list[SiteSplit]
    funnel: SiteFunnel
    speed: SiteSpeed
    inquiries: list[SiteInquiry]
