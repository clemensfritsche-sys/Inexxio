"""►►► **Verfassen – ein Papier im Gespräch mit der KI.** ◄◄◄

Der Mensch sagt, was er braucht; die KI schreibt das Papier (Art, Name, Titel, Einleitung,
Abschnitte) und schlägt vor, wer unterschreibt. Gesetzt wird es in der EINEN Vorlage
(``document.written``), auf A4-Seiten wie jeder Beleg. Das Gespräch lebt im Browser: jede
Runde schickt den Verlauf und den letzten Stand mit, gespeichert wird nichts – ein Dokument
entsteht erst mit der Freigabe (Regel 2).

Ohne KI gibt es kein Verfassen (die Kachel steht gesperrt da); sonst geht alles ohne sie.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models import UserProfile
from . import ai, document, legal, people, sites


class Section(BaseModel):
    title: str = Field(description="Überschrift des Abschnitts, z. B. «1. Gegenstand»")
    paragraphs: list[str] = Field(default_factory=list, description="Absätze, je ein Eintrag")
    bullets: list[str] = Field(default_factory=list, description="Aufzählungspunkte nach den Absätzen")


class Paper(BaseModel):
    """Das Papier, wie die KI es schreibt – und was sie dem Menschen dazu sagt."""
    reply: str = Field(description="Ein bis drei Sätze an den Menschen: was du geschrieben oder "
                                   "geändert hast, oder eine Rückfrage, wenn etwas Wesentliches fehlt.")
    art: str = Field(description="Die Art des Dokuments in einem Wort, z. B. «Vertrag», «Bestätigung»")
    name: str = Field(description="Was es von anderen derselben Art unterscheidet, z. B. «Wartung Heukran Muster AG 2027»")
    title: str = Field(description="Der Titel auf dem Papier")
    intro: list[str] = Field(default_factory=list, description="Einleitende Absätze vor den Abschnitten")
    sections: list[Section] = Field(default_factory=list)
    signers: list[str] = Field(default_factory=list,
                               description="Vor- und Nachname jeder Person, die unterschreiben soll – "
                                           "leer, wenn niemand unterschreibt")


class Turn(BaseModel):
    """Eine Runde im Gespräch – wer (``user`` · ``ai``) und was."""
    who: str
    text: str = Field(max_length=4000)


SYSTEM = (
    "Du schreibst Geschäftsdokumente für {firma}, ein Schweizer Maschinenbau-KMU. Schreibe "
    "auf Deutsch (Schweiz: «ss» statt «ß», Anrede «Sie»), klar, kurz und vollständig – wie ein "
    "erfahrener Sachbearbeiter. Erfinde keine Beträge, Daten oder Namen, die der Mensch nicht "
    "genannt hat; fehlt etwas Wesentliches, frage im Feld reply nach und lasse eine Lücke "
    "«[…]». Kein Briefkopf, keine Unterschriftszeilen, kein Datum – das setzt die Vorlage. "
    "Ändere bei einer Rückmeldung nur, was verlangt ist, und gib immer das ganze Papier zurück."
)


def compose(db: Session, *, actor: UserProfile, turns: list[Turn],
            current: Optional[Paper]) -> Optional[Paper]:
    """Eine Runde: Verlauf + letzter Stand rein, das neue Papier raus – oder ``None`` (keine
    KI, Deckel, Ausfall)."""
    firm = legal.values_of(sites.find_operator(db)).get("firma") or "INEXXIO"
    talk = "\n".join(f"{'Mensch' if t.who == 'user' else 'Du'}: {t.text}" for t in turns[-20:])
    content = [{"type": "text", "text": f"Das Gespräch bisher:\n{talk}"}]
    if current is not None:
        content.append({"type": "text", "text": "Der letzte Stand des Papiers (JSON):\n"
                                                 + current.model_dump_json()})
    return ai.ask(db, task="compose", actor=actor, system=SYSTEM.format(firma=firm),
                  content=content, schema=Paper)


def signers_of(db: Session, names: list[str]) -> list[dict]:
    """**Wer unterschreiben soll** – ein Name wird zur Person nur, wenn er genau eine trifft."""
    out = []
    for name in names[:10]:
        words = name.split()
        if not words:
            continue
        # Gesucht wird nach einem Wort (die Suche kennt Vor- ODER Nachname), passen muss der
        # ganze Name – sonst würde «Beat Muster» zu jedem Muster.
        found = [u for u in people.search(db, words[-1], limit=50)
                 if " ".join((u.display_name or "").lower().split()) == " ".join(w.lower() for w in words)]
        if len(found) == 1 and all(x["object_id"] != found[0].object_id for x in out):
            out.append({"object_id": found[0].object_id, "name": found[0].display_name or name})
    return out


def render(db: Session, paper: Paper, signers: list[tuple[int, str]]) -> str:
    """Das Papier als A4-HTML in der Vorlage – mit den Linien der Unterzeichner."""
    values = legal.values_of(sites.find_operator(db))
    w = document.Writing(
        word=paper.art.strip() or "Dokument", title=paper.title.strip() or paper.name,
        day=date.today().strftime("%d.%m.%Y"), intro=[p for p in paper.intro if p.strip()],
        sections=[legal.Section(title=s.title, blocks=[("p", p) for p in s.paragraphs if p.strip()]
                                + [("li", b) for b in s.bullets if b.strip()])
                  for s in paper.sections])
    return document.written(w, sender=legal.sender_line(values), signers=signers)
