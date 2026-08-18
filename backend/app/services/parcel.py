"""**Was eine Fuhre wiegt und misst — abgeleitet, nie eingegeben** (PROCESS_CORE §15.5a).

Gewicht und Grösse stehen am **Artikel**; was eine Fuhre wiegt, ist die Summe über ihre
Stücke. Eine Eingabe daneben wäre die zweite Wahrheit über dasselbe Paket – und die, die
niemand nachpflegt.

**Es wird nicht geraten.** Fehlt am Artikel das Gewicht, sagt die Anfrage, welcher Artikel
es schuldig bleibt. Ein geschätztes Paket ergäbe einen Preis, der beim Wiegen nicht
stimmt – und der Fehler fiele erst auf der Rechnung des Frachtführers auf.

Die Grösse steht am Artikel als Zeichenkette in **Millimetern** (»3x40x600«, aufsteigend).
Was sie **bedeutet**, entscheidet der Artikel selbst (``schemas.article.parse_size``) –
hier wird sie nur in Zentimeter umgerechnet. Zwei Ausleger an zwei Orten hiessen, dass
ein Preis davon abhängt, wer gerade rechnet.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ..models import Article, Instance, InstanceUnit
from ..schemas.article import parse_size
from .carriers import Parcel

#: Was ein Paket misst, wenn **kein einziger** Artikel eine Grösse trägt. Bewusst **kein**
#: Rückfall für das **Gewicht**: die Grösse beeinflusst den Preis bei den meisten
#: Frachtführern erst ab dem Volumengewicht, das Gewicht immer.
#:
#: Es ist eine **Ersatzangabe für nichts**, keine Untergrenze: ein echtes Mass von 0,3 cm
#: bleibt 0,3 cm. Als Untergrenze verstanden machte sie aus jedem kleinen Teil ein
#: zentimetergrosses – und der Preis stimmte dann bei genau den Teilen nicht, bei denen
#: das Volumen zählt.
MIN_CM = Decimal("1")


@dataclass(frozen=True)
class ParcelProblem:
    """Warum sich kein Paket bilden lässt. Nennt den Artikel, nicht nur die Tatsache."""

    article_object_id: int
    article_name: str
    missing: str

    @property
    def message(self) -> str:
        return (f"Artikel {self.article_object_id} «{self.article_name}» hat kein "
                f"{self.missing} – ohne das lässt sich kein Tarif holen. Ein geschätztes "
                f"Paket ergäbe einen Preis, der beim Wiegen nicht stimmt.")


def of_units(db: Session, unit_ids: Iterable[int]) -> tuple[Optional[Parcel], list[ParcelProblem]]:
    """Das Paket dieser Stücke – oder die Artikel, die etwas schuldig bleiben.

    Gerechnet wird **je Stück**: eine Einzelinstanz ist immer genau ein Stück (§0), also
    ist das Gewicht die Zahl der Stücke mal dem Artikel-Gewicht. Die Masse werden
    **gestapelt** (Länge und Breite bleiben, die Höhe summiert) – die einfachste Annahme,
    die nie kleiner ist als die Wirklichkeit; ein Packalgorithmus wäre eine Behauptung
    über eine Kiste, die niemand gesehen hat.
    """
    ids = [int(u) for u in unit_ids]
    if not ids:
        return None, []

    rows = (db.query(InstanceUnit.id, Article.id, Article.object_id, Article.name,
                     Article.weight_kg, Article.size, Article.is_hazmat)
            .join(Instance, Instance.id == InstanceUnit.instance_id)
            .join(Article, Article.id == Instance.article_id)
            .filter(InstanceUnit.id.in_(ids)).all())

    problems: list[ParcelProblem] = []
    weight = Decimal("0")
    length = width = height = Decimal("0")
    hazmat = False
    seen: set[int] = set()

    for _unit, _aid, a_obj, a_name, a_weight, a_size, a_haz in rows:
        if a_weight is None or Decimal(a_weight) <= 0:
            if a_obj not in seen:
                problems.append(ParcelProblem(a_obj, a_name or "", "Gewicht"))
                seen.add(a_obj)
            continue
        weight += Decimal(a_weight)
        hazmat = hazmat or bool(a_haz)
        dims = _cm(a_size)
        if dims:
            l, w, h = dims
            length, width = max(length, l), max(width, w)
            height += h

    if problems:
        return None, problems
    return Parcel(
        weight_kg=weight.quantize(Decimal("0.001")),
        length_cm=length or MIN_CM, width_cm=width or MIN_CM,
        height_cm=height or MIN_CM, hazmat=hazmat,
    ), []


def _cm(size: Optional[str]) -> Optional[tuple[Decimal, Decimal, Decimal]]:
    """Die Masse des Artikels in **Zentimetern** – gelesen wird sie am Artikel.

    Der Artikel führt sie in Millimetern (Spezifikations-Feld); die Umrechnung ist das
    Einzige, was hier passiert. Was »3x40x600« *bedeutet*, steht in
    ``schemas.article.parse_size`` und nirgends sonst.
    """
    mm = parse_size(size)
    if not mm:
        return None
    return tuple((v / Decimal(10)).quantize(Decimal("0.1")) for v in mm)  # type: ignore[return-value]
