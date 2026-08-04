"""**Die Regel-Tabelle, ausgeführt** – jede Zeile über die echten Dienste.

Gebaut wird jede Lage so, wie sie im Betrieb entsteht (Freigabe über ``release_order``,
Abweichung über den Router-Pfad, Verschrottung über ``scrap.record_scrap``) – kein
Nachstellen von Zuständen per Hand. Geprüft wird, was die Oberfläche daraus liest:
``subject_shortfalls`` (fehlt etwas?) und ``is_paused`` (ruht der Prozess?).

Bricht eine Zeile, steht ihre **Begründung** im Fehlertext. Wer die Regel ändern will,
ändert damit zwangsläufig auch den Satz, der sie erklärt.
"""

import pytest

from .table import RULES, Rule


from .conftest import _situation  # noqa: F401


# ─── Die Prüfung ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("r", RULES, ids=lambda r: r.id)
def test_rule(db, world, r: Rule):
    """Eine Zeile der Tabelle: Lage bauen, Antwort des Systems prüfen."""
    from app.services import process

    order, opening = _situation(db, world, r)
    short = process.subject_shortfalls(db, order)
    paused = process.is_paused(db, order)
    assert bool(short) is r.fehlmenge, (
        f"{r.id}: {r.lage}\n  erwartet Fehlmenge={r.fehlmenge}, tatsächlich {dict(short)}\n"
        f"  Regel: {r.warum}")
    assert paused is r.pause, (
        f"{r.id}: {r.lage}\n  erwartet Pause={r.pause}, tatsächlich {paused}\n"
        f"  Regel: {r.warum}")
    # **Und was mit seiner Menge geschah** – die eigentliche Konsequenz, seit die
    # Entscheidung automatisch fällt (#556).
    soll = ("abgebrochen" if order.status == "inactive"
            else "gekürzt" if _declared(db, order) != opening
            else "unverändert")
    assert soll == r.soll, (
        f"{r.id}: {r.lage}\n  erwartet Soll={r.soll}, tatsächlich {soll}\n"
        f"  Regel: {r.warum}")


def _declared(db, order) -> object:
    """Das Soll eines Auftrags, wie es die Anlage gesetzt hat (Einzel-Artikel oder Summe)."""
    from app.services.order_lines import declared_quantity
    return declared_quantity(db, order)


def test_the_table_is_the_written_rule():
    """**Die Tabelle ist die Regel, nicht ihre Illustration.**

    Jede Zeile muss eine Begründung tragen und beide Auftragsarten müssen vorkommen –
    sonst beschreibt die Tabelle nur den Fall, der gerade zufällig gemeldet wurde."""
    assert len(RULES) >= 6
    assert {r.art for r in RULES} == {"regular", "fixed"}
    assert {"alles", "teil", "nichts"} <= {r.rest for r in RULES}
    for r in RULES:
        assert r.warum.strip() and r.lage.strip(), r.id
    # Der Kern, um den es in #522/#523 ging – beide Zeilen müssen es ausdrücklich sagen.
    from .table import rule
    assert rule("fixed-teil-verloren").fehlmenge is False
    assert rule("fixed-alles-verloren").fehlmenge is True
    # **Selbst ausgesteuert ist nicht fehlend** (#555) – der Steckenbleiber.
    assert rule("fixed-selbst-ausgesteuert").fehlmenge is False
    # **Entschieden wird automatisch** (#556): was nicht zurückkommt, senkt das Soll;
    # was zurückkommen kann, lässt es unangetastet und wartet.
    assert rule("regular-teil-verloren").soll == "gekürzt"
    assert rule("regular-alles-verliehen").soll == "unverändert"
    assert {r.soll for r in RULES} <= {"unverändert", "gekürzt", "abgebrochen"}
