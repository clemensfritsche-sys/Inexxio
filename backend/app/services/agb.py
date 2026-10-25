"""**Die AGB – eine Datei je Fassung, mit ihrem Datum** (``app/assets/agb/<JJJJ-MM-TT>.md``).

►►► **Eine Quelle für alles**: die Website zeigt sie unter ``/agb`` als A4-Dokument, jedes
Dokument eines Belegs hängt **die Fassung an, die an seinem Tag galt**, und nennt ihr
Datum («Es gelten unsere Allgemeinen Geschäftsbedingungen vom 01.01.2026.»). ◄◄◄

Eine neue Fassung ist eine **neue Datei** – die alte bleibt liegen, damit nachvollziehbar
bleibt, was damals galt. Ein Dokument friert seine AGB ohnehin mit ein (``voucher_documents``).

Die Datei ist schlichtes Markdown: ``#`` Titel, ``##`` je Teil (Geschäftskunden ·
Endkunden), ``###`` je Paragraf, Absätze und ``-`` Aufzählungen.
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

DIR = Path(__file__).resolve().parent.parent / "assets" / "agb"
#: Welcher Teil für wen gilt – am Anfang des Teil-Titels.
BUSINESS, PRIVATE = "Für Geschäftskunden", "Für Endkunden"


@dataclass
class Paragraph:
    title: str
    blocks: list[tuple[str, str]] = field(default_factory=list)   # ("p"|"li", Text)


@dataclass
class Part:
    title: str
    intro: str = ""
    paragraphs: list[Paragraph] = field(default_factory=list)


@dataclass
class Terms:
    """Eine Fassung der AGB – ihr Datum und ihre Teile."""
    valid_from: date
    title: str
    parts: list[Part]

    @property
    def key(self) -> str:
        return self.valid_from.isoformat()

    @property
    def day(self) -> str:
        """Das Datum, wie es auf dem Papier steht – «01.01.2026»."""
        return self.valid_from.strftime("%d.%m.%Y")

    def part_for(self, business: bool) -> Optional[Part]:
        """Der Teil, der für diesen Empfänger gilt – sonst der erste."""
        start = BUSINESS if business else PRIVATE
        return next((p for p in self.parts if p.title.startswith(start)),
                    self.parts[0] if self.parts else None)


def versions() -> list[date]:
    """Alle Fassungen, älteste zuerst – der Dateiname ist ihr Datum."""
    out = []
    for f in DIR.glob("*.md"):
        try:
            out.append(date.fromisoformat(f.stem))
        except ValueError:
            continue
    return sorted(out)


def current(on: Optional[date] = None) -> Optional[Terms]:
    """**Die Fassung, die an diesem Tag gilt** – die jüngste, die schon begonnen hat."""
    day = on or date.today()
    valid = [d for d in versions() if d <= day] or versions()[:1]
    if not valid:
        return None
    return parse(valid[-1], (DIR / f"{valid[-1].isoformat()}.md").read_text())


def parse(valid_from: date, text: str) -> Terms:
    """Markdown in Teile und Paragrafen – nur die vier Formen, die die Datei kennt."""
    title, parts = "Allgemeine Geschäftsbedingungen", []
    part: Optional[Part] = None
    para: Optional[Paragraph] = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("gültig ab"):
            continue
        if line.startswith("### "):
            para = Paragraph(line[4:].strip())
            if part is None:
                part = Part("")
                parts.append(part)
            part.paragraphs.append(para)
        elif line.startswith("## "):
            part, para = Part(line[3:].strip()), None
            parts.append(part)
        elif line.startswith("# "):
            title = line[2:].strip()
        elif para is not None:
            para.blocks.append(("li", line[2:].strip()) if line.startswith("- ")
                               else ("p", line))
        elif part is not None:
            part.intro = f"{part.intro} {line}".strip()
    return Terms(valid_from=valid_from, title=title, parts=parts)
