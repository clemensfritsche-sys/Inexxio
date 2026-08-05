"""Mengengenaue Instanz-Reservierung **ohne Teilung** (REA-konform).

Die universelle Objektnummer einer Instanz ist physisch (Etikett/QR an den Teilen) –
sie darf sich **nie** ändern und eine Instanz darf **nie** in eine zweite Instanz mit
eigener Nummer aufgeteilt werden. Eine Charge wird daher nicht mehr „geteilt"; statt-
dessen merkt sich die Instanz **pro Auftrag eine Menge** (``instances.reservations`` =
``{auftrag_db_id: menge}``). Die denormalisierte Summe (``reserved_quantity``) macht die
Verfügbarkeit per SQL-Aggregat zählbar.

Frei verfügbar (für andere Aufträge) = ``quantity − reserved_quantity``. So bleibt eine
Charge von 1000 Schrauben mit 970 frei, auch wenn 30 für einen Auftrag reserviert sind.

**Bruchmengen:** alle Mengen sind ``Decimal`` (kg/m²/m³/l, nicht nur ganze Stück). Die
Reservierungs-Map speichert die Mengen als **String** (JSON-sicher, exakt), gelesen/
geschrieben ausschliesslich über ``services/quantity.py``.
"""

from decimal import Decimal

from ..models import Instance
from .quantity import ZERO, qty_key, qty_sum, to_qty


def _load(inst: Instance) -> dict[str, Decimal]:
    """Reservierungs-Map als ``{auftrag: Decimal}`` einlesen (Werte sind Strings in JSONB)."""
    return {k: to_qty(v) for k, v in (inst.reservations or {}).items()}


def reserved_for(inst: Instance, order_id: int) -> Decimal:
    """Wie viel dieser Instanz für den gegebenen Auftrag reserviert ist."""
    return to_qty((inst.reservations or {}).get(str(order_id), 0))


def free_qty(inst: Instance) -> Decimal:
    """**Wem gehört an dieser Instanz nichts?** – gesamt − beansprucht, nie negativ.

    Das ist eine Frage der **Eigentümerschaft**, nicht der Entnehmbarkeit: ob eine freie
    Menge auch schon ihr Prozessziel erreicht hat, beantwortet ``inventory.ready_qty``.
    Zwei Fragen, zwei Namen – die Auswahl einer noch laufenden Instanz (Abweichung) braucht
    diese hier, FIFO die andere.

    Überbucht ist möglich, solange ein **Entwurf** nur vormerkt (``claim``): dann wollen zwei
    Aufträge zusammen mehr, als die Instanz hergibt. Für FIFO heisst das schlicht «nichts
    frei» – nicht «minus eins». Aufgelöst wird die Überbuchung erst bei der Freigabe
    (``enforce``)."""
    rest = to_qty(inst.quantity) - to_qty(inst.reserved_quantity)
    return rest if rest > 0 else ZERO


def _write(inst: Instance, m: dict, *, taker: int | None = None,
           source: int | None = None) -> None:
    """Reservierungs-Map zurückschreiben + Denormalisierungen (Summe, Einzel-Zeiger)
    konsistent nachziehen – die EINE Stelle, an der die drei Felder gesetzt werden.
    Nicht-positive Einträge werden verworfen; Mengen JSON-sicher als String abgelegt.

    **Und hier hängen die Stücke dran.** Weil dies die einzige Stelle ist, an der sich
    «wer beansprucht wie viel» ändert, ist es auch die einzige, an der sich «welche Stücke»
    ändern muss (``units.sync``). So können Mengen und Nummern gar nicht auseinanderlaufen –
    es gibt keinen zweiten Weg, an dem man es vergessen könnte.

    ``taker``/``source`` reichen dabei die **eine** Angabe durch, die die Mengen-Seite
    ohnehin hat: wer nimmt sich etwas, und aus wessen Anteil. Die Stücke folgen ihr genauso
    (Testnotiz #553) – sonst nähme derselbe Klick auf der einen Seite dem genannten Halter
    etwas weg und auf der anderen einem Dritten."""
    from . import units
    clean = {k: qty_key(v) for k, v in m.items() if to_qty(v) > 0}
    inst.reservations = clean or None
    inst.reserved_quantity = qty_sum(clean.values())
    inst.reserved_for_order_id = int(next(iter(clean))) if len(clean) == 1 else None
    units.sync(inst, taker=taker, source=source)


def reserve(inst: Instance, order_id: int, qty) -> None:
    """``qty`` der Instanz für ``order_id`` reservieren (additiv). Aktualisiert die Summe
    und den Einzel-Zeiger; die Instanz wird NICHT geteilt (Objektnummer bleibt)."""
    q = to_qty(qty)
    if q <= 0:
        return
    m = _load(inst)
    m[str(order_id)] = m.get(str(order_id), ZERO) + q
    _write(inst, m)


def claim(inst: Instance, order_id: int, qty, from_order_id: int | None = None) -> Decimal:
    """**Vormerken**: den Anspruch eines Auftrags auf genau ``qty`` setzen – ohne fremde
    Ansprüche anzutasten. Liefert die gesetzte Menge.

    Drei Formen derselben Sache, klar getrennt nach dem Moment, in dem sie gelten:

        reserve  – **addiert**   → FIFO füllt auf, was es findet (Freigabe)
        claim    – **setzt**     → der Mensch wählt Instanz + Menge (Entwurf)
        enforce  – **setzt sich durch** → der Anspruch wird scharf (Freigabe)

    Ein Entwurf nimmt **niemandem etwas weg**: er merkt nur vor. Darum darf die Summe hier
    die Instanz-Menge übersteigen – für FIFO ist das Stück damit gesprochen (``free_qty``
    fällt auf 0), aber der laufende Auftrag, der es gedeckt hat, behält seine Reservierung
    und merkt nichts. Das ist der ganze Punkt: solange man noch am Auswählen ist, soll beim
    anderen Auftrag nichts passieren (Testnotiz #370).

    **Der genannte Anteil bestimmt aber schon jetzt, WELCHE Stücke gemeint sind** – auch
    wenn mengenmässig noch nichts geschieht. Sonst greift die Vormerkung in den freien Topf
    (der dem Erzeuger gehört), und wenn die Freigabe die Mengen anschliessend richtig stellt,
    haben zwei Aufträge die Stücke getauscht (Testnotiz #553)."""
    want = min(to_qty(qty), to_qty(inst.quantity))
    if want <= 0:
        release(inst, order_id)
        return ZERO
    m = _load(inst)
    m[str(order_id)] = want
    _write(inst, m, taker=order_id, source=from_order_id)
    return want


def enforce(inst: Instance, order_id: int, from_order_id: int | None = None) -> Decimal:
    """**Scharf werden**: den vorgemerkten Anspruch durchsetzen – und zwar zulasten des
    **genannten** Anteils. Liefert die entzogene Menge.

    Das ist der Moment der **Freigabe**, und genau hier entsteht die Unterdeckung: nimmt
    eine Abweichung ein Stück aus einer Charge, die ein laufender Auftrag gedeckt hatte,
    schrumpft **dessen** Reservierung – und damit meldet er die Fehlmenge von selbst. Es
    braucht dafür keine zweite Buchführung, nur diesen einen Schnitt zum richtigen
    Zeitpunkt.

    **Wer verliert, wird nicht mehr geraten.** Früher lief eine Schleife über alle übrigen
    Ansprüche und kürzte den erstbesten. Bei EINEM anderen Halter war das zufällig richtig;
    ab zwei war es Willkür – eine Charge à 4, an der Hauptauftrag (2) und Abweichung (2)
    hängen, konnte bei einem Zugriff auf 1 Stück beliebig den einen oder anderen treffen.
    Jetzt sagt die **Auswahl**, wessen Anteil gemeint ist (``orders.pick_sources``), und hier
    wird genau der gekürzt.

    **Der genannte Anteil verliert IMMER – auch wenn woanders noch etwas frei wäre**
    (Testnotiz #394). Ein Klick auf die Zeile «1 Stk · Auftrag …557» ist eine Aussage über
    die **Herkunft**, nicht bloss über die Menge: gemeint ist *dieses* Stück. Vorher war der
    Name nur eine Rangfolge für den Fehlbetrag – gab es irgendwo sonst noch Luft, blieb der
    genannte Anteil unangetastet und die Menge kam still von jemand anderem. Damit war der
    Klick folgenlos: die Abweichung trug zwar den richtigen Eltern-Namen, das Material nahm
    sie aber einem Dritten weg, und dessen Unterdeckung tauchte nirgends auf.

    Danach gilt weiter, was immer galt: was **darüber hinaus** zu viel ist, geht zulasten
    der übrigen Ansprüche (wer 2 aus einer 2er-Charge nimmt, an der zwei Aufträge hängen,
    trifft zwangsläufig beide); bleibt dann immer noch etwas offen, schrumpft der **eigene**
    Anspruch – wer nimmt, was nicht mehr da ist, bekommt eben weniger, statt es jemandem
    stillschweigend wegzunehmen. Dieselbe Rangfolge beantwortet auch, **wer gefragt wird**
    (``shares.losses`` – zwei Formen, eine Regel)."""
    m = _load(inst)
    mine_key = str(order_id)
    src_key = str(from_order_id) if from_order_id is not None and str(from_order_id) != mine_key else None
    taken = ZERO
    # 1. Der genannte Anteil gibt her, was dieser Auftrag beansprucht – unbedingt.
    if src_key is not None:
        cut = min(m.get(mine_key, ZERO), m.get(src_key, ZERO))
        if cut > 0:
            m[src_key] -= cut
            taken += cut
    # 2. Was jetzt noch über die Instanz-Menge hinausgeht, tragen die übrigen Ansprüche
    #    (der genannte zuerst, falls er noch etwas hat).
    over = qty_sum(m.values()) - to_qty(inst.quantity)
    ranked = ([src_key] if src_key else []) + [k for k in m if k not in (mine_key, src_key)]
    for key in ranked:
        if over <= 0:
            break
        cut = min(over, m.get(key, ZERO))
        if cut <= 0:
            continue
        m[key] -= cut
        over -= cut
        taken += cut
    if over > 0:                       # so viel war schlicht nicht mehr da
        mine = m.get(mine_key, ZERO) - over
        m[mine_key] = mine if mine > 0 else ZERO
    _write(inst, m, taker=order_id, source=from_order_id)
    return taken


def release(inst: Instance, order_id: int) -> Decimal:
    """Die Reservierung eines Auftrags vollständig lösen. Liefert die gelöste Menge."""
    m = _load(inst)
    qty = m.pop(str(order_id), ZERO)
    _write(inst, m)
    return qty


def release_all(inst: Instance) -> None:
    """**Alle** Reservierungen einer Instanz lösen. Für terminale Verbleibe (verschrottet):
    ein Teil, das den Bestand verlässt, kann keinen Auftrag mehr beliefern – auch nicht einen
    Eltern-/Fremd-Auftrag, der es reserviert hatte. So wird dessen Fehlmenge **ehrlich** wieder
    sichtbar (statt still von einer toten Reservierung „gedeckt" zu bleiben)."""
    _write(inst, {})


def take(inst: Instance, qty, *, state: str, by_order_id: int | None = None,
         gone: list | None = None) -> Decimal:
    """``qty`` aus der Instanz **herausnehmen** – die EINE Regel für jeden Mengen-Abgang
    (verbaut, verkauft, teilverschrottet). Die Objektnummer bleibt, es entsteht KEINE neue
    Instanz. Liefert die tatsächlich entnommene Menge.

    Zwei Dinge passieren, und beide gehören zusammen:

    1. **Der Anspruch des Entnehmers ist erfüllt** (``by_order_id``): wer die Menge für
       seinen Auftrag reserviert hatte, gibt sie mit der Entnahme frei. Sonst hielte er
       einen Anspruch auf Ware, die er gerade selbst weggenommen hat.
    2. **Fremde Ansprüche werden auf die Restmenge gedeckelt**: was jetzt nicht mehr da ist,
       kann niemanden mehr beliefern – die betroffenen Aufträge sehen dadurch **ehrlich**
       eine Fehlmenge (Recovery), statt still von einer toten Reservierung «gedeckt» zu sein.

    Vorher waren das zwei fast gleiche Funktionen, die je EINEN der beiden Schritte machten
    (``consume`` nur (1), ``reduce_quantity`` nur (2)) – und die Teil-Verschrottung griff zur
    falschen: eine Charge à 10 mit 5 reservierten Stück behielt nach dem Verschrotten dieser
    5 ihre Reservierung über 5 auf einer nur noch 5 Stück grossen Instanz. Der Rest galt als
    **vollständig belegt** (frei = 0): FIFO übersah ihn, andere Aufträge meldeten eine
    Fehlmenge, die es nicht gab, und die Auto-Nachbestellung bestellte den Sicherheitsbestand
    ein zweites Mal."""
    want = to_qty(qty)
    if want <= 0:
        return ZERO
    # Entnommen wird höchstens, was da ist – der **Anspruch** des Entnehmers ist danach
    # trotzdem erledigt (was fehlt, kann ihn nicht mehr beliefern; seine Fehlmenge wird
    # über die Unterdeckung sichtbar, nicht über eine stehengebliebene Reservierung).
    cut = min(want, to_qty(inst.quantity))
    # **Welche Stücke gehen weg**, nicht nur wie viel: die Nummern werden endgültig
    # entwertet (sie kommen nie wieder), bevorzugt beim Entnehmer selbst. Sie bleiben dabei
    # in der Karte stehen und tragen ``state`` als Endzustand – ein Stück verschwindet
    # nicht, es ändert seinen Zustand (Testnotiz #549).
    from . import units
    # ``gone`` sammelt die Nummern der ausgeschiedenen Stücke – der Aufrufer gibt sie an die
    # Buchung weiter (``ledger.post(units=…)``), damit die Vergangenheit sie behält.
    if gone is not None:
        gone.extend(units.drop(inst, cut, state=state, by_order_id=by_order_id))
    else:
        units.drop(inst, cut, state=state, by_order_id=by_order_id)
    inst.quantity = to_qty(inst.quantity) - cut
    m = _load(inst)
    if by_order_id is not None:
        key = str(by_order_id)
        left = m.get(key, ZERO) - want
        if left > 0:
            m[key] = left
        else:
            m.pop(key, None)
    while m and qty_sum(m.values()) > to_qty(inst.quantity):
        k = max(m, key=lambda x: m[x])
        over = qty_sum(m.values()) - to_qty(inst.quantity)
        m[k] = m[k] - over
        if m[k] <= 0:
            del m[k]
    _write(inst, m)
    return cut
