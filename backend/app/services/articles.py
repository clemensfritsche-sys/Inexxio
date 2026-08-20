"""Artikel – Anlage (= Freigabe) und Freigabebedingungen.

**Ein Artikel entsteht erst bei der Freigabe.** Bis dahin lebt der Entwurf im Browser:
keine Zeile, keine Objektnummer, kein Autosave, kein Datensatz «draft». Das ist dieselbe
Regel wie beim Auftrag (``services/orders.py``) und aus demselben Grund – wer ein Fenster
verlässt, lässt keine Spur.

*Vorher war es anders, und das war ein Fehler:* das Formular speicherte per Autosave,
sobald die Pflichtfelder der Spezifikation standen. Damit existierte ein Artikel mit
Objektnummer, der nichts erzeugen konnte, weil sein Prozess leer war – ein Datensatz, der
eine Zusage macht, die er nicht halten kann.

Die Freigabebedingungen stehen **an dieser einen Stelle**. Die Oberfläche fragt sie ab
(``POST /erp/articles/validate``), statt sie nachzuformulieren; sonst gäbe es zwei
Massstäbe für dieselbe Frage, und der schwächere entscheidet, ob der Knopf leuchtet.
"""

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import statuses as st
from ..models import Article
from . import article_process
from .objects import next_object_id

#: Status eines angelegten Artikels – aus der EINEN Statusliste (``domain/statuses``).
#: Es gibt nur diesen einen Einstieg: **angelegt heisst freigegeben**.
RELEASED = st.FREIGEGEBEN

#: Pflichtfelder der Spezifikation (Feldname → Beschriftung). Sie stehen hier und nicht
#: im Formular: eine deaktivierte Schaltfläche ist keine Absicherung, sondern eine Bitte.
_REQUIRED = (
    ("name", "Artikelname"),
    ("size", "Abmessungen"),
    ("weight_kg", "Gewicht"),
)

#: Wie weit einer Ersetzungskette gefolgt wird. Ein Artikel, der zwanzigmal ersetzt
#: wurde, ist real; wer hundert erreicht, hat einen Kreis – und dann ist eine gekappte
#: Antwort besser als eine Ansicht, die hängt.
MAX_CHAIN = 100


def may_create(article: Article) -> Optional[str]:
    """►►► **Darf dieser Artikel NEUE Einzelinstanzen erzeugen?** ◄◄◄ ``None`` = ja.

    Die Regel in einem Satz: *nur ein Artikel im Zustand «Freigegeben» erzeugt Neues.*
    Sie sperrt damit ausschliesslich die Herkunft **Neu** — **Lager bleibt erlaubt**, und
    zwar mit Absicht: sonst würde jedes Stück eines ausgelaufenen Artikels zur Leiche, die
    sich nicht einmal mehr aussondern liesse.

    **Warum die Funktion nach der Regel heisst und nicht nach dem Zustand.** Der Fehler,
    aus dem sie entstanden ist, war eine Verwechslung zweier Achsen, die beide «aktiv»
    heissen: ``is_active`` ist der **Soft-Delete** (Datensatz ausgeblendet),
    ``status`` ist der **fachliche** Zustand (Freigegeben ↔ Inaktiv). Geprüft wurde die
    erste, gemeint war die zweite — und weil die erste im ganzen Prozessbereich **nie**
    gesetzt wird, konnte die Prüfung gar nichts abweisen. Ein Name wie ``is_article_active``
    hätte dieselbe Falle nur eine Ebene weiter aufgestellt; ``may_create`` benennt die
    Frage, und die kann man nicht verwechseln.

    **Zwei Formen derselben Regel** (wie ``process.pick_problem``/``unpickable``): sie gibt
    den Grund zurück, statt zu werfen. Die Freigabe bricht damit ab, die Auswahl-Liste
    sperrt damit «Neu» und nennt denselben Satz. Zwei Formulierungen wären zwei Massstäbe.

    **Geprüft wird bei der Freigabe, nicht laufend.** Ein bereits laufender Auftrag läuft
    zu Ende, auch wenn der Artikel zwischenzeitlich inaktiv gesetzt wird — sein Prozess ist
    eine eingefrorene Kopie (§6.5), und ihn von aussen anzuhalten hiesse, die Vergangenheit
    umzuschreiben.
    """
    if article.status != st.FREIGEGEBEN:
        return (
            f"Artikel {article.object_id} ist «{st.label(article.status)}» – ein Artikel "
            f"ausser Betrieb erzeugt keine neuen Einzelinstanzen. Bestehende Stücke "
            f"lassen sich weiterhin über «Lager» abwickeln."
        )
    return None


def missing_for_release(draft: dict[str, Any]) -> list[str]:
    """Was fehlt diesem Artikel-Entwurf noch zur Freigabe? Leere Liste = freigebbar.

    Beide harten Bedingungen, in **einer** Funktion:

    1. alle Pflichtfelder der Spezifikation,
    2. mindestens ein Prozessschrittmodul im Erzeugungsprozess.

    Namen statt True/False, damit die Oberfläche sagen kann *was* fehlt, statt den Nutzer
    suchen zu lassen.
    """
    # Ausdrücklich auf «nicht gesetzt» geprüft, nicht auf «unwahr»: ein Gewicht von 0 ist
    # ein Wert, den jemand eingetragen hat. Ob er fachlich taugt, entscheidet der
    # Feld-Validator – nicht eine Wahrheitsprüfung, die 0 wie «leer» behandelt.
    missing = [
        label for key, label in _REQUIRED
        if draft.get(key) is None or str(draft.get(key)).strip() == ""
    ]
    if not list(draft.get("steps") or []):
        missing.append("mindestens ein Prozessschrittmodul")
    return missing


def validate_draft(draft: dict[str, Any]) -> list[str]:
    """Wäre dieser Entwurf freigebbar? Prüft **dieselben** Bedingungen wie die Anlage.

    Zusätzlich läuft die Modul-Definition durch ihre echte Prüfung: ein Modul ohne
    Erfassungspunkt oder ein Soll-Ist-Vergleich ohne Sollwert soll auffallen, **bevor**
    jemand auf «Freigeben» drückt – nicht als Fehlermeldung danach.
    """
    missing = missing_for_release(draft)
    if missing:
        return missing
    try:
        _clean_steps(list(draft.get("steps") or []))
    except HTTPException as e:
        return [str(e.detail)]
    return []


def _clean_steps(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Modul-Definitionen durch die echte Prüfung schicken, ohne etwas anzulegen.

    Sie ist dieselbe, die ``article_process.create_steps`` benutzt – die Prüfung sitzt im
    Modul (``domain/modules.Module.clean_config``), nicht in einer Kopie davon.
    """
    from ..domain import modules

    for data in raw:
        module = modules.get(data.get("module_type"))
        module.clean_config(data.get("config"))
    return raw


def create_article(db: Session, draft: dict[str, Any], *, actor_id: int | None) -> Article:
    """Aus einem Entwurf einen freigegebenen Artikel machen. **Eine Transaktion.**

    Reihenfolge wie beim Auftrag: erst prüfen, **dann** die Objektnummer ziehen. Eine
    Sequence ist absichtlich nicht transaktional – ein Rollback danach liesse eine Lücke
    im Nummernkreis. Ein abgebrochener Versuch verbraucht darum keine Nummer.

    **Ersetzen ist Teil der Anlage** (``replaces_object_id``), nicht ein zweiter Aufruf
    danach: sonst gäbe es den Zwischenzustand «Nachfolger existiert, Vorgänger läuft
    weiter», und wer das Fenster in diesem Moment schliesst, hinterlässt genau ihn.
    """
    steps = list(draft.pop("steps", None) or [])
    replaces = draft.pop("replaces_object_id", None)
    draft = {k: v for k, v in draft.items() if v is not None}

    missing = missing_for_release({**draft, "steps": steps})
    if missing:
        raise HTTPException(
            status_code=400,
            detail="Der Artikel ist noch nicht freigebbar – es fehlt: " + ", ".join(missing) + ".",
        )
    _clean_steps(steps)
    predecessor = _predecessor_for(db, replaces)

    # ── Ab hier wird eine Nummer vergeben ────────────────────────────────────
    article = Article(object_id=next_object_id(db, "article"), status=RELEASED, **draft)
    db.add(article)
    db.flush()
    article_process.create_steps(db, article, steps)
    if predecessor is not None:
        apply_replacement(db, predecessor=predecessor, successor=article)
    return article


def _predecessor_for(db: Session, object_id: Any) -> Optional[Article]:
    """Den zu ersetzenden Artikel laden und **vor** der Nummernvergabe prüfen.

    Geprüft wird alles, was ohne den Nachfolger prüfbar ist (gibt es ihn? ist er schon
    ersetzt?). Der Rest – Selbstbezug und Kreis – kann erst danach, und beides ist beim
    frisch angelegten Nachfolger ohnehin unmöglich; die Prüfung steht trotzdem, weil sie
    zur Regel gehört und nicht zum Zeitpunkt.
    """
    if object_id is None:
        return None
    found = db.query(Article).filter(Article.object_id == int(object_id)).first()
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=f"Artikel {object_id} gibt es nicht – er kann nicht ersetzt werden.",
        )
    problem = replaceable_problem(found)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    return found


# ---------------------------------------------------------------------------
# Ausser Betrieb nehmen und ersetzen
# ---------------------------------------------------------------------------
#
# **Ein Artikel wird nicht versioniert, er wird ersetzt.** Eine Änderung an
# Spezifikation oder Prozess ist ein *anderer* Artikel – der alte bleibt stehen, weil
# seine Stücke, seine Aufträge und seine Nachweise auf ihn zeigen. Was die beiden
# verbindet, ist genau eine Angabe: ``replaced_by_id`` (alt → neu).
#
# **Die Angabe steht am NACHFOLGER, nicht am Vorgänger.** Wer ersetzt, legt den neuen
# Artikel an und sagt dabei, welchen er ablöst – das ist die Reihenfolge, in der es
# gedacht wird, und sie hat nur einen Moment: die Anlage. Ein Feld am Vorgänger («wer
# löst mich ab?») wäre dagegen jederzeit änderbar und damit eine zweite Wahrheit über
# dieselbe Kette.
#
# **Ersetzen nimmt ausser Betrieb.** Das ist keine zusätzliche Wirkung, sondern die
# Bedeutung: wer abgelöst ist, erzeugt nichts Neues mehr. Zwei Klicks für einen Vorgang
# wären zwei Gelegenheiten, den zweiten zu vergessen.


def replaceable_problem(predecessor: Article) -> Optional[str]:
    """►►► **Lässt sich dieser Artikel ersetzen?** ◄◄◄ ``None`` = ja.

    Ein Vorgänger hat genau **einen** Nachfolger – sonst gäbe es zwei «neueste
    Fassungen», und keine Auflösung könnte sagen, welche gilt. Die bestehende wird
    **genannt**, damit man weiterklicken kann statt zu suchen.

    **Zwei Formen derselben Regel** (wie ``may_create``): sie gibt den Grund zurück,
    statt zu werfen. Die Anlage wirft damit, und die Auswahl-Liste sperrt damit denselben
    Artikel mit demselben Satz – ein zweiter Massstab wäre ein Knopf, der leuchtet und
    dann scheitert.
    """
    if predecessor.replaced_by_id:
        return (
            f"Artikel {predecessor.object_id} ist bereits ersetzt – Nachfolger ist "
            f"{predecessor.replaced_by_id}. Ersetzt wird immer die neueste Fassung."
        )
    return None


def assert_replaceable(db: Session, predecessor: Article, successor: Article) -> None:
    """Wie ``replaceable_problem`` – nur wirft sie (400), und sie kennt den Nachfolger.

    Zwei Ablehnungen kommen erst mit ihm dazu: **sich selbst** (eine Kette, die im Kreis
    zeigt, hat keinen neuesten Stand) und der **Kreis** über mehrere Stufen. Der frisch
    angelegte Nachfolger kann beides nicht auslösen; die Prüfung steht trotzdem, weil sie
    zur Regel gehört und nicht zum Zeitpunkt – und weil sie beim ersten Aufrufer, der
    einen *bestehenden* Artikel zum Nachfolger macht, sonst fehlte.
    """
    problem = replaceable_problem(predecessor)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    if predecessor.object_id == successor.object_id:
        raise HTTPException(
            status_code=400, detail="Ein Artikel kann sich nicht selbst ersetzen.")
    # **Gefragt wird vorwärts, ab dem NACHFOLGER.** Der Vorgänger hat definitionsgemäss
    # noch keinen (die Prüfung darüber), seine Kette ist also immer leer – dort zu suchen
    # wäre eine Bedingung, die nie zutrifft. Ein Kreis entsteht, wenn der Nachfolger über
    # seine eigene Kette bereits beim Vorgänger ankommt.
    if predecessor.object_id in {a.object_id for a in chain_of(db, successor)}:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Artikel {predecessor.object_id} steht bereits in der Ersetzungskette von "
                f"{successor.object_id} – daraus entstünde ein Kreis."
            ),
        )


def apply_replacement(db: Session, *, predecessor: Article, successor: Article) -> None:
    """Den Vorgänger ablösen: Nachfolger eintragen **und** ausser Betrieb nehmen.

    Beides in einem Zug, weil es ein Vorgang ist. Der Aufrufer schreibt das Audit – er
    weiss, wer geklickt hat; dieser Dienst kennt nur die Regel.
    """
    assert_replaceable(db, predecessor, successor)
    predecessor.replaced_by_id = successor.object_id
    predecessor.status = st.INAKTIV


def chain_of(db: Session, article: Article) -> list[Article]:
    """Die Ersetzungskette **ab** diesem Artikel: ``[Nachfolger … neuester]``.

    Zyklensicher (``seen``) und gekappt (``MAX_CHAIN``) – dasselbe zweite Netz wie beim
    Lesen einer Stückliste: was in den Daten nicht vorkommen darf, fängt man beim Lesen ab,
    nicht erst, wenn eine Ansicht hängt.
    """
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
    """Wen löst dieser Artikel ab? — die Gegenrichtung von ``replaced_by_id``.

    Eine Abfrage statt einer zweiten Spalte: der Rückweg ist die Umkehrung derselben
    Kante, und eine gespiegelte Spalte wäre die zweite Stelle, an der die Kette
    auseinanderlaufen kann.
    """
    if article.object_id is None:
        return None
    return db.query(Article).filter(Article.replaced_by_id == article.object_id).first()
