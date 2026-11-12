"""Artikel – Anlage (= Freigabe) und Freigabebedingungen.

**Ein Artikel entsteht erst bei der Freigabe.** Bis dahin lebt der Entwurf im Browser:
keine Zeile, keine Objektnummer, kein Autosave – wie beim Auftrag (``services/orders.py``).
Die Freigabebedingungen stehen **an dieser einen Stelle**; die Oberfläche fragt sie ab
(``POST /erp/articles/validate``).
"""

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import Article
from . import article_process
from .objects import next_object_id
from ..domain.errors import Invalid, Rejected

# **Angelegt heisst freigegeben** – abgeleitet: ein frischer Artikel hat keinen Nachfolger
# (``Article.status``).

#: Pflichtfelder der Spezifikation (Feldname → Beschriftung) – geprüft hier, nicht im Formular.
_REQUIRED = (
    ("name", "Artikelname"),
    ("size", "Abmessungen"),
    ("weight_kg", "Gewicht"),
)

#: Wie weit einer Ersetzungskette gefolgt wird – ein Netz gegen Kreise.
MAX_CHAIN = 100


def may_create(article: Article) -> Optional[str]:
    """►►► **Darf dieser Artikel NEUE Einzelinstanzen erzeugen?** ◄◄◄ ``None`` = ja.

    *Ein abgelöster Artikel erzeugt nichts Neues mehr* – gesperrt wird nur die Herkunft
    **Neu**, «Lager» bleibt erlaubt. Gelesen wird die Tatsache ``replaced_by_id``.

    Zwei Formen derselben Regel (wie ``release.pick_problem``/``unpickable``): Freigabe
    und Auswahl-Liste nennen denselben Satz. Geprüft bei der Freigabe; ein laufender
    Auftrag läuft zu Ende (eingefrorene Kopie, §6.5).
    """
    if article.replaced_by_id:
        return (
            f"Artikel {article.object_id} ist durch {article.replaced_by_id} ersetzt – "
            f"ein abgelöster Artikel erzeugt keine neuen Einzelinstanzen. Bestehende "
            f"Stücke lassen sich weiterhin über «Lager» abwickeln, und Neues entsteht "
            f"beim Nachfolger."
        )
    return None


def missing_for_release(draft: dict[str, Any]) -> list[str]:
    """Was fehlt diesem Artikel-Entwurf noch zur Freigabe? Leere Liste = freigebbar.

    1. alle Pflichtfelder der Spezifikation,
    2. mindestens ein Prozessschrittmodul im Erzeugungsprozess.
    """
    # Geprüft auf «nicht gesetzt», nicht auf «unwahr» – ein Gewicht von 0 ist ein Wert.
    missing = [
        label for key, label in _REQUIRED
        if draft.get(key) is None or str(draft.get(key)).strip() == ""
    ]
    if not list(draft.get("steps") or []):
        missing.append("mindestens ein Prozessschrittmodul")
    return missing


def validate_draft(db: Session, draft: dict[str, Any]) -> list[str]:
    """Wäre dieser Entwurf freigebbar? Prüft **dieselben** Bedingungen wie die Anlage, dazu
    die Modul-Definitionen durch ihre echte Prüfung – Fehler fallen vor «Freigeben» auf."""
    from .voucher_input import step_party_problems
    missing = missing_for_release(draft)
    if missing:
        return missing
    try:
        steps = _clean_steps(list(draft.get("steps") or []))
    except Rejected as e:
        return [str(e.detail)]
    return step_party_problems(db, steps)


def _clean_steps(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Modul-Definitionen durch die echte Prüfung schicken, ohne etwas anzulegen
    (``Module.clean_config``, wie in ``article_process.create_steps``)."""
    from ..domain import modules

    for data in raw:
        module = modules.get(data.get("module_type"))
        module.clean_step(data.get("config"))
    return raw


def create_article(db: Session, draft: dict[str, Any], *, actor_id: int | None) -> Article:
    """Aus einem Entwurf einen freigegebenen Artikel machen. **Eine Transaktion.**

    Erst prüfen, **dann** die Objektnummer ziehen (kein Loch im Nummernkreis). **Ersetzen
    ist Teil der Anlage** (``replaces_object_id``) – kein Zwischenzustand.
    """
    steps = list(draft.pop("steps", None) or [])
    replaces = draft.pop("replaces_object_id", None)
    draft = {k: v for k, v in draft.items() if v is not None}

    missing = missing_for_release({**draft, "steps": steps})
    if missing:
        raise Invalid("Der Artikel ist noch nicht freigebbar – es fehlt: " + ", ".join(missing) + ".")
    _clean_steps(steps)
    predecessor = _predecessor_for(db, replaces)

    # ── Ab hier wird eine Nummer vergeben ────────────────────────────────────
    article = Article(object_id=next_object_id(db, "article"), **draft)
    db.add(article)
    db.flush()
    article_process.create_steps(db, article, steps)
    if predecessor is not None:
        apply_replacement(db, predecessor=predecessor, successor=article)
    return article


def _predecessor_for(db: Session, object_id: Any) -> Optional[Article]:
    """Den zu ersetzenden Artikel laden und **vor** der Nummernvergabe prüfen; Selbstbezug
    und Kreis prüft ``assert_replaceable`` danach."""
    if object_id is None:
        return None
    found = db.query(Article).filter(Article.object_id == int(object_id)).first()
    if found is None:
        raise Invalid(f"Artikel {object_id} gibt es nicht – er kann nicht ersetzt werden.")
    problem = replaceable_problem(found)
    if problem:
        raise Invalid(problem)
    return found


# ---------------------------------------------------------------------------
# Ausser Betrieb nehmen und ersetzen
# ---------------------------------------------------------------------------
#
# **Ein Artikel wird nicht versioniert, er wird ersetzt.** Eine Änderung ist ein anderer
# Artikel; der alte bleibt, weil Stücke, Aufträge und Nachweise auf ihn zeigen. Die eine
# Angabe ``replaced_by_id`` (alt → neu) entsteht **bei der Anlage des Nachfolgers**, und
# **Ersetzen nimmt ausser Betrieb** – das ist ihre Bedeutung.


def replaceable_problem(predecessor: Article) -> Optional[str]:
    """►►► **Lässt sich dieser Artikel ersetzen?** ◄◄◄ ``None`` = ja.

    Ein Vorgänger hat genau **einen** Nachfolger; der bestehende wird genannt. Zwei Formen
    derselben Regel (wie ``may_create``).
    """
    if predecessor.replaced_by_id:
        return (
            f"Artikel {predecessor.object_id} ist bereits ersetzt – Nachfolger ist "
            f"{predecessor.replaced_by_id}. Ersetzt wird immer die neueste Fassung."
        )
    return None


def assert_replaceable(db: Session, predecessor: Article, successor: Article) -> None:
    """Wie ``replaceable_problem`` – nur wirft sie (400), und sie kennt den Nachfolger: dazu
    kommen **Selbstbezug** und **Kreis** über mehrere Stufen."""
    problem = replaceable_problem(predecessor)
    if problem:
        raise Invalid(problem)
    if predecessor.object_id == successor.object_id:
        raise Invalid("Ein Artikel kann sich nicht selbst ersetzen.")
    # Gefragt wird vorwärts ab dem Nachfolger: ein Kreis entsteht, wenn seine Kette beim
    # Vorgänger ankommt.
    if predecessor.object_id in {a.object_id for a in chain_of(db, successor)}:
        raise Invalid(f"Artikel {predecessor.object_id} steht bereits in der Ersetzungskette von "
                f"{successor.object_id} – daraus entstünde ein Kreis.")


def apply_replacement(db: Session, *, predecessor: Article, successor: Article) -> None:
    """Den Vorgänger ablösen — **eine** Angabe, ausser Betrieb ist ihre Bedeutung
    (``Article.status``). Das Audit schreibt der Aufrufer."""
    assert_replaceable(db, predecessor, successor)
    predecessor.replaced_by_id = successor.object_id


def chain_of(db: Session, article: Article) -> list[Article]:
    """Die Ersetzungskette **ab** diesem Artikel: ``[Nachfolger … neuester]`` – zyklensicher
    (``seen``) und gekappt (``MAX_CHAIN``)."""
    out: list[Article] = []
    seen = {article.object_id}
    cur = article
    while cur.replaced_by_id and cur.replaced_by_id not in seen and len(out) < MAX_CHAIN:
        seen.add(cur.replaced_by_id)
        nxt = db.query(Article).filter(Article.object_id == cur.replaced_by_id).first()
        if nxt is None:
            break
        out.append(nxt)
        cur = nxt
    return out


def predecessor_of(db: Session, article: Article) -> Optional[Article]:
    """Wen löst dieser Artikel ab? — die Gegenrichtung von ``replaced_by_id``, als Abfrage
    statt zweiter Spalte."""
    if article.object_id is None:
        return None
    return db.query(Article).filter(Article.replaced_by_id == article.object_id).first()
