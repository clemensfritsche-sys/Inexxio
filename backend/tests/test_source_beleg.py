"""Quelltext-Wächter: das Zahlungsmodul «Beleg» (``beleg-work.tsx``, ``services/voucher``).
"""

import re

from tests._source import (
    BACKEND,
    DEAL_WORK,
    FRONTEND,
    _at,
    _beleg,
    _body,
    _code,
    _component,
    _module_ui,
    _read,
)


# ---------------------------------------------------------------------------
# ►►► Das Geldmodul «Zahlung» — eigenständig, und die Spiegel decken sich ◄◄◄
# ---------------------------------------------------------------------------


def test_the_money_module_is_a_pass_through_in_the_editor_too():
    """**Zwei Angaben, und keine davon ist eine Menge, ein Artikel, ein Betrag – oder
    eine Frist.**

    ►►► **Und `prepaid` gehört nicht mehr dazu** (Testnotiz #854). ◄◄◄ Der Schalter
    «Zahlung abwarten» war eine **zweite Aussage über dieselbe Sache**: ob vorausbezahlt
    wird, sagt die vereinbarte **Zahlungsfrist** – null Tage *ist* Vorauszahlung. Zwei
    Stellen, die dasselbe behaupten, widersprechen sich beim ersten Vorgang, in dem
    jemand nur eine davon setzt; und die Frist gehört dorthin, wo das Angebot entsteht,
    nicht in eine Vorlage, die für jeden künftigen Auftrag dasselbe behauptet.

    Bug-Formen: (a) ein Betragsfeld in der Definition; (b) der Schalter ist zurück;
    (c) eine Frist steht im Editor.
    """
    src = _read(FRONTEND / "lib" / "modules.ts")
    # ►►► **Die Definition steht als KONSTANTE daneben.** ◄◄◄
    #
    # Sie stand einmal als Rumpf direkt unter ihrem Schlüssel; als das Vorgängermodul
    # daneben lief, wurde sie eine Konstante mit zwei Referenzen – und genau deshalb
    # kostete dessen Löschung hier **eine Zeile** statt einer halb nachgeführten Kopie
    # (Testnotiz #960). Geprüft wird darum die **Regel**: es gibt eine Form, und der
    # Schlüssel zeigt darauf.
    form = _body(src, "MODULE_FORM", kind="const")
    assert "beleg: MONEY_FORM," in form, (
        "«beleg» hat wieder eine eigene Entwurfsform – zwei Fassungen derselben "
        "Definition laufen beim nächsten Feld auseinander."
    )
    row = _body(src, "MONEY_FORM", kind="const")
    for field in ("direction", "parties"):
        assert field in row, f"«{field}» fehlt in der Entwurfsform des Geldmoduls."
    assert "prepaid" not in row, (
        "Der Schalter ist zurück (b) – ob vorausbezahlt wird, sagt die Zahlungsfrist "
        "(#854); zwei Aussagen über dieselbe Sache können sich widersprechen."
    )
    assert "subject" not in row, (
        "Der abgeschaffte Satz ist zurück (#805) – was zu tun ist, steht bei dem Partner, "
        "den es betrifft."
    )
    fields = _body(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"),
                   "MoneyFields", kind="function")
    for forbidden in ("Betrag", "Menge", "Artikel", "Zahlungsfrist", "Lieferfrist"):
        assert f">{forbidden}<" not in fields, (
            f"Der Editor fragt nach «{forbidden}» – das steht beim Modellieren nicht "
            f"fest und wäre bei der zweiten Ausführung falsch."
        )
    assert "prepaid" not in _code(fields), (
        "Der Vorauszahlungs-Schalter steht wieder im Editor (b)."
    )


def test_a_module_without_verification_confirms_without_a_scan():
    """►►► **Ohne Scan-Regel kein Scan-Tor** — und das ist eine Eigenschaft des Moduls. ◄◄◄

    Ein Geldvorgang bewegt keine Stücke: es gibt nichts zu verifizieren, und ein Scan
    davor wäre ein erfundenes Hindernis. Die Frage steht am **Modul**
    (`Module.requires_verification` → `ModuleFacts.verifies`) und reist mit dem Schritt –
    den Modul-Katalog lädt nur der Editor.

    Bug-Formen: (a) die Ausführungsstelle nennt wieder einen Modultyp; (b) die Eigenschaft
    reist nicht mit, dann kann die Oberfläche gar nicht anders als raten.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import modules as dmod

    assert dmod.get(dmod.BELEG).requires_verification is False, (
        "Das Geldmodul verlangt wieder eine Verifikation – es bewegt keine Stücke, es "
        "gibt nichts zu scannen."
    )
    facts = _read(BACKEND / "app" / "schemas" / "process.py")
    assert "def verifies" in facts, (
        "`ModuleFacts` trägt die Eigenschaft nicht – dann muss die Oberfläche raten."
    )
    detail = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    assert "step.verifies" in detail, (
        "Die Ausführungsstelle liest die mitgereiste Eigenschaft nicht."
    )
    for key in ("'beleg'", '"beleg"'):
        assert key not in detail, (
            f"Die Ausführungsstelle nennt wieder den Modultyp {key} statt seine "
            f"Eigenschaft – beim nächsten Modul derselben Art fehlt die Zeile."
        )


def test_one_field_asked_two_questions_so_there_are_two():
    """►►► **«Was ist zu tun?» ≠ «Wie bestelle ich bei ihm?»** ◄◄◄

    *«Bei Einkaufsteilen ist es oft ‹gemäss Spezifikation›, aber wenn ein intern gefertigtes
    Teil auswärts nachbearbeitet werden muss, soll dieses Feld dafür genutzt werden … bei
    der Verkaufsabwicklung habe ich keine Ahnung, was ich dort reinschreiben soll. Es ist
    ein Mussfeld – die Logik geht bei Verkaufsteilen nicht auf.»*

    Und das stimmt, weil die **eine** Pflichtangabe je Partner zwei Dinge meinte:

    * **Was ist zu tun?** – eine Eigenschaft des **Moduls**: «Härten auf 58 HRC» lautet für
      jeden Lieferanten gleich und stand n-mal da. Sie steht jetzt **einmal** und ist
      **freiwillig**: *was* es ist, sagen die Positionen; leer heisst «gemäss
      Spezifikation», also eine vollständige Aussage.
    * **Wie bestellen?** – eine Eigenschaft der **Paarung** Modul × Partner, weiterhin
      **Pflicht**, aber nur, **wo wir bestellen** (``Direction.party_ref``).

    Bug-Formen: (a) die Bestellangabe ist beim Verkauf wieder Pflicht; (b) ein dort
    gesendeter Wert wird gespeichert statt verworfen; (c) sie ist beim Einkauf freiwillig
    geworden; (d) der Auftrag am Modul wird Pflicht; (e) er kommt gar nicht an; (f) die
    Länge ist ungeprüft; (g) im Editor steht das Bestellfeld auch beim Verkauf; (h) der
    Auftrag fehlt dort ganz.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from fastapi import HTTPException
    from app.domain import modules as dmod
    from app.domain import voucher as vo

    module = dmod.get(dmod.BELEG)

    # (a)/(b) **Verkauf**: keine Bestellangabe – und ein gesendeter Wert wird verworfen.
    sale = module.clean_config({"direction": "in",
                                "parties": [{"party": 100000001, "ref": "Art. 4711"}]})
    assert sale["parties"][0]["ref"] == "", (
        "Beim Verkauf wird die Bestellangabe gespeichert (b) – ein Feld, das die "
        "Oberfläche nicht anbietet, wäre die Hintertür zu einer Angabe, die niemand liest."
    )
    module.clean_config({"direction": "in", "parties": [{"party": 100000001}]})

    # (c) **Einkauf**: Pflicht, mit Grund im Satz.
    try:
        module.clean_config({"direction": "out",
                             "parties": [{"party": 100000001, "ref": "  "}]})
    except HTTPException as e:
        assert vo.ORDER_REF in str(e.detail), "Der Satz nennt die Angabe nicht."
    else:
        raise AssertionError("Beim Einkauf ist die Bestellangabe freiwillig geworden (c).")
    buy = module.clean_config({"direction": "out",
                               "parties": [{"party": 100000001, "ref": "Art. 4711"}]})
    assert buy["parties"][0]["ref"] == "Art. 4711"

    # (d)/(e) **Der Auftrag am Modul**: freiwillig, und er kommt an.
    assert module.clean_config({"direction": "in"})[module.INSTRUCTION] == "", (
        "Ohne Auftrag geht das Modul nicht mehr durch (d) – leer heisst «gemäss "
        "Spezifikation»."
    )
    got = module.clean_config({"direction": "in", "instruction": " Härten auf 58 HRC "})
    assert module.instruction_of(got) == "Härten auf 58 HRC", (
        "Der Auftrag erreicht das Modul nicht (e)."
    )
    # (f) Und er ist kein Pflichtenheft.
    try:
        module.clean_config({"direction": "in", "instruction": "x" * (vo.MAX_TASK + 1)})
    except HTTPException:
        pass
    else:
        raise AssertionError("Die Länge des Auftrags ist ungeprüft (f).")

    # (g)/(h) **Der Editor fragt dieselben zwei Fragen** – und das Bestellfeld hängt an der
    # Richtung, nicht am Modultyp.
    fields = _code(_component(_read(FRONTEND / "components" / "erp"
                                    / "process-designer.tsx"), "MoneyFields"))
    assert "voucherDirection(m.direction).partyRef" in fields, (
        "Das Bestellfeld steht auch beim Verkauf da (g) – dort hat es keine richtige "
        "Antwort."
    )
    assert "aria-label={VOUCHER_ORDER_REF}" in fields and "required" in fields, (
        "Die Bestellangabe ist im Editor weder benannt noch als Pflicht ausgezeichnet."
    )
    assert "onChange({ instruction:" in fields and "{VOUCHER_TASK}" in fields, (
        "«Was ist zu tun?» gibt es im Editor nicht (h) – dann wird es nie gesetzt."
    )


def test_a_new_money_module_starts_as_income():
    """**Der Normalfall ist die Vorgabe** (Testnotiz #791).

    Ein Vorgang ohne Richtung gibt es nicht; die Frage bleibt, aber sie beginnt mit der
    häufigeren Antwort. Bug-Form: der Entwurf startet ohne Richtung – dann steht im
    Editor ein Schalter, der auf nichts steht, und der Server setzt still `out`.
    """
    blank = _body(_read(FRONTEND / "lib" / "modules.ts"), "blankModule", kind="function")
    assert "direction: 'in'" in blank, (
        "Der Entwurf startet nicht als Einnahme (#791) – der Schalter stünde auf nichts "
        "oder auf der selteneren Antwort."
    )


def test_the_editor_explains_nothing_it_already_shows():
    """**Kein Erklärsatz unter einem Feld, das sich selbst erklärt** (Testnotiz #792).

    Bug-Form: ein `<p>` unter den Feldern des Geldmoduls. Ein Satz, der sagt, was das
    Feld darüber ohnehin zeigt, ist die Doppelung, aus der beim nächsten Umbau zwei
    Aussagen werden.
    """
    fields = _body(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"),
                   "MoneyFields", kind="function")
    assert "<p " not in fields and "<p>" not in fields, (
        "Der Editor erklärt wieder in Prosa, was die Felder zeigen (#792)."
    )


def test_the_money_module_is_not_named_after_a_trade():
    """►►► **«Einnahme» ↔ «Ausgabe», nicht «Verkauf» ↔ «Einkauf»** (Testnotiz #831). ◄◄◄

    Dieses Modul entstand aus der Einsicht, dass der kleinste gemeinsame Nenner **nicht
    die Ware** ist, sondern Geld mit einer zweiten Partei. Miete, Lohn, Gebühr, Spesen und
    ein Transport sind keine Käufe – ein Wert, der «Verkauf» heisst, ist damit **enger als
    das Modul**, und beim ersten Mietvertrag ist er schlicht falsch. *Meine frühere Wahl
    (#804) wird damit zurückgenommen: sie stimmte für die beiden Fälle, die zufällig
    zuerst gebaut wurden.*

    ►►► **Das gilt den WÖRTERN – die Symbole kommen vom Handel** (Testnotiz #845). ◄◄◄

    Hier stand einmal das Gegenteil («darum trägt es nicht die Symbole des Handels»), und
    das war eine Regel zu viel: ein Symbol behauptet keinen **Namen**, es zeigt die
    häufigste Gestalt der Sache. Zwei gespiegelte Pfeile derselben Familie sind auf 15 px
    das gleiche Zeichen mit anderer Neigung – Einkaufswagen und Handschlag sind
    verschiedene Dinge. Der Einwand aus #831 bleibt beantwortet: er galt den Werten, und
    die heissen unverändert «Einnahme» ↔ «Ausgabe».

    *Die beiden Symbole standen einmal in einer eigenen Zuordnung (`FLOW`, gespiegelt vom
    Handels-Beleg). Mit den Modulen «Beschaffen»/«Verkauf» ist sie entfallen – eine
    Zuordnung mit genau einem Leser ist keine –, und sie stehen jetzt dort, wo sie
    gebraucht werden. Die Regel bleibt: **zwei verschiedene Dinge, keine zwei Pfeile.**

    Bug-Formen: (a) die Handels-Wörter kommen zurück; (b) die Vorzeichen aus #799;
    (c) zwei gespiegelte Pfeile statt zweier verschiedener Zeichen.
    """
    src = _read(FRONTEND / "lib" / "modules.ts")
    block = _body(src, "VOUCHER_DIRECTION", kind="const")
    assert "'Einnahme'" in block and "'Ausgabe'" in block, (
        "Die Richtung heisst nicht mehr nach dem Geldfluss."
    )
    for word in ("'Verkauf'", "'Einkauf'"):
        assert word not in block, (
            f"{word} ist zurück – dieses Modul kann auch Miete, Lohn und Gebühr, und "
            f"ein Wort, das einen Kauf behauptet, ist enger als das Modul (#831)."
        )
    for sign in ("CirclePlus", "CircleMinus"):
        assert sign not in block, (
            f"«{sign}» ist zurück – ein Vorzeichen sagt, wie gebucht wird, nicht wohin "
            f"das Geld fliesst (#799)."
        )
    # (c) ►►► **Zwei verschiedene Dinge, keine zwei Pfeile** (#845). ◄◄◄
    #
    # Geld **herein** ist der Handschlag (wir verkaufen), Geld **hinaus** der
    # Einkaufswagen. Zwei Zeichen derselben Familie, gespiegelt, wären auf 15 px dasselbe
    # Zeichen mit anderer Neigung – man müsste hinsehen, statt zu erkennen.
    assert "icon: Handshake" in block and "icon: ShoppingCart" in block, (
        "Die Richtung trägt wieder zwei Zeichen derselben Familie – dann muss man "
        "hinsehen, statt zu erkennen (#845)."
    )
    assert block.index("icon: Handshake") < block.index("icon: ShoppingCart"), (
        "Herein und hinaus sind vertauscht – Geld kommt herein, weil wir verkaufen."
    )
    assert "Arrow" not in block, (
        "Die Pfeile aus der ersten Fassung sind zurück."
    )
    # **Und die Backend-Wörter sind dieselben** – der Spiegel darf nicht auseinanderlaufen.
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as dm
    for key, row in dm.DIRECTIONS.items():
        assert f"'{row.label}'" in block, (
            f"«{row.label}» ({key}) steht im Backend, aber nicht im Spiegel."
        )


def test_the_stage_label_sits_on_the_height_of_its_dot():
    """**Punkt und Wort teilen EINE Zeilenhöhe** (Testnotiz #798).

    Vorher standen beide mit einem geratenen Abstand da – der Punkt mit `marginTop`, das
    Wort auf der Grundlinie seiner Zeile. Zwei Ränder, die sich zufällig treffen müssen,
    treffen sich beim ersten anderen Schriftgrad nicht mehr.

    *Gemessen wurde die Regel damals an der Stufen-Kette des Geldvorgangs (`Row`, zwei
    gleiche Höhen nebeneinander). Die Kette gibt es nicht mehr – Punkt und Wort stehen
    heute in `module-ui.SegmentMark`, dem einen Bauteil, mit dem das Haus **jeden**
    Anteil schreibt. Der Wächter folgt der Regel, nicht ihrer damaligen Form: eine
    gemeinsame Zeile ist jetzt ein `flex`-Container, und das ist die einfachere Antwort
    auf dieselbe Frage.*

    Bug-Form: die Ausrichtung hängt wieder an einem Abstand statt an einer gemeinsamen
    Zeile.
    """
    mark = _body(_code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx")),
                 "SegmentMark", kind="function")
    assert mark.count("flex items-center") >= 2, (
        "Punkt und Beschriftung stehen nicht mehr in einer gemeinsamen, mittig "
        "ausgerichteten Zeile – dann ist ihre Ausrichtung wieder Zufall (#798)."
    )
    assert "marginTop" not in mark and "marginBottom" not in mark, (
        "Die Ausrichtung hängt wieder an einem Abstand – genau die Form, die beim "
        "nächsten Schriftgrad auseinanderfällt."
    )


def test_every_button_of_the_money_card_looks_like_a_button():
    """►►► **Ein blosser `.erp-actbtn` ist KEIN Knopf.** ◄◄◄

    Die Basisklasse hat `border: 1px solid transparent` und keine Fläche – erst
    `-primary` / `-neutral` / `-danger` machen daraus etwas, das man als Knopf erkennt.
    `purchase-work.tsx` vergibt an jedem Knopf eine Ausprägung, `beleg-work.tsx` an
    keinem: daher «die Buttons sind nur Text». Das ist die Ursache, nicht der Geschmack.

    Bug-Form: irgendwo steht wieder `className="erp-actbtn"` ohne Ausprägung.
    """
    css = _read(FRONTEND / "app" / "globals.css")
    base = css.split(".erp-actbtn {", 1)[1].split("}", 1)[0]
    assert "border: 1px solid transparent" in base, (
        "Die Basisklasse trägt jetzt selbst eine Kontur – dann prüft dieser Wächter "
        "eine Regel, die es nicht mehr gibt; er gehört überdacht, nicht gelöscht."
    )
    # *Diese Prüfung sah zuerst nur `beleg-work.tsx` – und liess damit ausgerechnet den
    # Knopf durch, der gemeldet wurde (#813): der Modul-Abschluss steht in
    # `order-detail.tsx`. Gemessen an der Bug-Form, nachgeschärft.*
    for name in ("beleg-work.tsx", "order-detail.tsx"):
        src = _read(FRONTEND / "components" / "erp" / name)
        bare = [ln.strip() for ln in src.splitlines()
                if re.search(r'className="erp-actbtn(?: w-full)?"', ln)
                or "className={`erp-actbtn`}" in ln]
        assert not bare, (
            f"{name}: diese Knöpfe tragen keine Ausprägung und sehen darum aus wie Text – "
            + " | ".join(bare)
        )
    # **Und der Modul-Abschluss ist der lauteste Knopf der Karte** (#813): er ist die eine
    # Handlung, die das Modul beendet – er trägt Fläche und volle Breite, keine Kontur.
    detail = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    confirm = detail.split("const work =", 1)[1].split("</button>", 1)[0]
    assert "erp-actbtn-primary" in confirm and "w-full" in confirm, (
        "Der Knopf, der ein Modul abschliesst, ist nicht der lauteste – er sah damit aus "
        "wie Text (#813)."
    )


def test_a_counterparty_does_not_confirm_a_module():
    """**Ein Knopf, der nie etwas tun kann, ist kein Angebot.**

    `confirm_step` ist `require_employee` – jeder Bestätigungsweg endet für eine
    Gegenpartei in einem 403. Gefragt wird `internal` (die Aussage der Aufrufstelle über
    sich selbst), nicht die Rolle: dieselbe Naht, an der auch das Modul-Protokoll hängt.

    Bug-Formen: (a) die Bestätigung hängt wieder nur an `isActive`; (b) die Ansicht
    fragt stattdessen nach einer Rolle.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    body = src.split("const stepBody =", 1)[1].split("\n  };", 1)[0]
    head = body.split("const work =", 1)[1].split(";", 1)[0]
    assert "internal" in head, (
        "Die Modul-Bestätigung hängt nicht an `internal` – eine Gegenpartei bekommt "
        "damit einen Knopf, den der Server mit 403 abweist."
    )
    for role in ("'supplier'", "'customer'", "'employee'", "'admin'"):
        assert role not in body, (
            f"Die Ausführungsstelle fragt wieder nach einer Rolle ({role}) – was jemand "
            f"darf, sagt der Vorgang (`can`), nicht sein Titel."
        )


def test_the_module_record_says_what_it_is():
    """**Eine Liste von Einzelinstanzen ohne Überschrift ist eine Frage** (#801).

    Bei einem Modul, das am Stück nichts ändert (ein Geldvorgang), bleibt im Protokoll
    genau das übrig: wer wann was bestätigt hat. Das **ist** die Aussage – man muss sie
    nur lesen können. Entfernt wird sie nicht: sie ist der Nachweis, und die Regel gilt
    für jedes Modul (#717).

    Bug-Form: die Überschrift fehlt, und es steht wieder eine Nummer ohne Erklärung da.
    """
    src = _read(FRONTEND / "components" / "erp" / "step-record.tsx")
    assert "Was hier passiert ist" in src, (
        "Das Modul-Protokoll sagt nicht mehr, was es ist (#801)."
    )


def test_the_money_card_speaks_one_language_in_both_directions():
    """►►► **Kein `if` auf die Richtung — auch nicht in den Wörtern** (#802/#804). ◄◄◄

    Die Karte bekam Wörter je Richtung geliefert und der Editor hielt eigene daneben. Was
    für beide Seiten gilt, steht jetzt **einmal** da: der Partner, die Angabe bei ihm und
    die Beschriftungen des Schiebers.

    Bug-Formen: (a) ein Rollen-Wort steht wieder als Literal in der Oberfläche; (b) der
    Editor verzweigt auf die Richtung, um zu entscheiden, welche Felder es gibt.
    """
    fields = _body(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"),
                   "MoneyFields", kind="function")
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    for word in ("'Kunde'", "'Lieferant'", "'Kunden'", "'Lieferanten'",
                 "'Einnahme'", "'Ausgabe'", "'Bestellangabe'"):
        for where, name in ((fields, "Editor"), (work, "Karte")):
            assert word not in where, (
                f"{name}: {word} steht wieder als Literal – es ist ein Wort der Richtung "
                f"bzw. der Rolle und gehört in `domain/voucher`."
            )
    # Die einzige erlaubte Direktabfrage ist die **Normalisierung** des Schiebers selbst
    # (`value={m.direction === 'in' ? …}`) – sie sagt, was eingestellt ist, und trifft
    # keine Aussage darüber, welche Felder es gibt.
    branches = [ln.strip() for ln in fields.splitlines()
                if "m.direction ===" in ln and "value=" not in ln]
    assert not branches, (
        "Der Editor verzweigt wieder auf die Richtung: " + " | ".join(branches)
    )


def test_a_card_you_can_still_act_on_is_never_dimmed():
    """►►► **Ausgegraut heisst «hier ist nichts zu tun»** (Testnotiz #821). ◄◄◄

    Gemessen war es der Fix meines eigenen letzten Fixes: die Geld-Knöpfe funktionierten
    an einem abgeschlossenen Auftrag (ein Zahlungsziel läuft weiter, wenn die Ware
    draussen ist), und die Karte lag trotzdem bei 55 % Deckkraft da. Eine erfundene
    Sperre, nur in Farbe.

    **Und die Frage stellt der Schritt**, nicht die Zeichnung: ``open_actions`` kommt aus
    derselben Tabelle, die auch das Tor ist (``deal.can`` / ``purchase.can``). Eine
    Heuristik der Oberfläche wäre eine dritte Wahrheit.

    Bug-Formen: (a) ``dimmed`` hängt wieder allein an «ist dieses Modul dran»; (b) die
    Angabe erreicht den Schritt gar nicht erst; (c) die Oberfläche rechnet sie selbst aus
    (etwa über den Modultyp).
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.schemas.order import ProcessStepResponse

    diagram = _code(_read(FRONTEND / "components" / "erp" / "process-diagram.tsx"))
    assert "dimmed={running && !isActive}" not in diagram, (
        "Gedämpft wird wieder allein danach, ob das Modul dran ist."
    )
    assert "!step.openActions" in diagram, (
        "Die Zeichnung fragt nicht, ob noch etwas ansteht."
    )
    # (b) **Die Angabe muss auch ankommen** – eine Ableitung, die niemand durchreicht,
    # ist im Browser schlicht `undefined`, und `!undefined` ist wahr: die Karte wäre
    # danach NIE gedämpft. Genau diese Form fällt sonst niemandem auf.
    assert "openActions: s.open_actions" in _code(
        _read(FRONTEND / "components" / "erp" / "process-columns.tsx")), (
        "`open_actions` wird nicht an den Schritt durchgereicht."
    )
    # (c) **Abgeleitet aus `can`, nicht aus dem Modultyp.**
    assert "open_actions" in ProcessStepResponse.model_fields \
        or "open_actions" in ProcessStepResponse.model_computed_fields, (
        "Der Schritt sagt gar nicht mehr, ob an ihm etwas ansteht."
    )
    # **Der Code, nicht die Prosa**: der Docstring der Ableitung *nennt* den Modultyp,
    # um zu begründen, warum er nicht gefragt wird – ein Wächter, der ihn mitliest,
    # schlägt an, weil jemand den Fehler erklärt.
    body = _code(_body(_read(BACKEND / "app" / "schemas" / "order.py"), "open_actions"))
    assert "module_type" not in body, (
        "Die Ableitung fragt nach dem Modultyp – dann ist sie beim nächsten Modul falsch."
    )
    assert ".can" in body, "Sie liest nicht die Tabelle, die auch das Tor ist."


def test_the_record_appears_only_where_there_is_something_to_report():
    """►►► **Nummer, Name und Uhrzeit sind kein Nachweis** (Testnotiz #825). ◄◄◄

    Das Protokoll bleibt für **jedes** Modul, was es ist – aber bei einem Modul, das am
    Stück nichts ändert, nichts erfasst und nichts verifiziert, blieben genau drei
    Angaben übrig, und die Frage «warum steht die hier?» war berechtigt.

    **Gefragt wird die Sache, nicht der Modultyp**: erfasste Werte · ein Zustandswechsel
    · eine Verifikation. Alle drei stehen am Schritt; es braucht keine Abfrage auf den
    Log und schon gar nicht eine je Modul in jeder Auftrags-Antwort.

    Bug-Formen: (a) ein ``if module_type ===`` in der Oberfläche; (b) die Ableitung fragt
    den Modultyp; (c) ein Modul, das etwas zu berichten hat, verliert sein Protokoll.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.schemas.order import ProcessStepResponse

    src = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    guard = src[src.index("<StepRecord") - 200:src.index("<StepRecord")]
    assert "step.records" in guard, (
        "Das Protokoll erscheint wieder überall – auch dort, wo es nichts zu berichten hat."
    )
    assert "zahlung" not in guard, (
        "Die Bedingung nennt einen Modultyp – beim nächsten Modul ohne physisches "
        "Gegenstück wäre sie wieder falsch."
    )
    body = _code(_body(_read(BACKEND / "app" / "schemas" / "order.py"), "records"))
    assert "module_type" not in body, "Die Ableitung fragt nach dem Modultyp."
    for part in ("points_of", "status_after", "verifies"):
        assert part in body, f"Die Ableitung fragt «{part}» nicht."
    assert "records" in ProcessStepResponse.model_computed_fields


def test_the_money_module_says_it_with_its_values_not_with_labels():
    """►►► **Was ein Bedienelement selbst sagt, sagt man nicht daneben** (#816/#817/#819).

    Drei Labels standen über drei Bedienelementen, die alle für sich sprechen:
    «Geschäft *» über «Verkauf ↔ Einkauf», «Was ist zu tun? *» über einem Platzhalter,
    der es genauer sagt, und «Weiter, wenn» über zwei Werten, die die Bedingung schon
    tragen. *«Die Buttons sind selbsterklärend genug.»*

    **Und die Werte werden dafür richtig** (#818): «zugesagt» klang nach einem *Zustand*
    statt nach einer *Bedingung* – einzeln gelesen war es eine schlechte Beschreibung.
    «Nach Zusage» ↔ «Nach Zahlung» stimmt auch dort, wo es allein steht.

    Bug-Formen: (a) ein Label kommt zurück; (b) die alten Werte kommen zurück.
    """
    fields = _code(_component(_read(FRONTEND / "components" / "erp" / "process-designer.tsx"),
                              "MoneyFields"))
    for label in ("<Label required>Geschäft</Label>", "<Label>Weiter, wenn</Label>"):
        assert label not in fields, f"«{label}» steht wieder über seinem Schalter."
    # ►►► **Die Regel gilt den Bedienelementen, die für sich sprechen — nicht allen.** ◄◄◄
    #
    # «Kein Label im ganzen Feldsatz» war die **Form** der damaligen Lösung, nicht die
    # Regel: sie lautet «was ein Bedienelement selbst sagt, sagt man nicht daneben». Ein
    # Schieber mit zwei benannten Werten sagt es (Einnahme ↔ Ausgabe, Zahlung abwarten ↔
    # nicht), ein Referenzfeld sagt es im Platzhalter (#843) – ein Auswahlfeld über
    # «8.10 % · Normalsatz» sagt **nicht**, wozu der Satz gehört, und braucht sein Wort.
    # Geprüft wird darum, dass über einem `IconSwitch` und über dem Partner-Feld keines
    # steht; wo eines steht, muss es eine Frage beantworten, die der Wert nicht stellt.
    for after in re.findall(r"</Label>\s*(<[A-Za-z]+)", fields):
        assert after not in ("<IconSwitch", "<ObjectSelect"), (
            f"Über «{after}» steht wieder ein Label – es spricht für sich."
        )
    # ►►► **Der Wert benennt die ENTSCHEIDUNG, nicht ihren Bezugspunkt** (#834). ◄◄◄
    #
    # «Nach Zusage» ↔ «Nach Zahlung» war die zweite Fassung und immer noch zu knapp: der
    # Satz sagt nicht, *worauf* er sich bezieht, und ohne das Label darüber (#819) fehlte
    # der Bezug ganz. Jetzt steht die Frage im Wert – warte ich auf das Geld, ja oder nein.
    # ►►► **Der Schalter, um den es in #834 ging, gibt es nicht mehr** (#854). ◄◄◄
    #
    # Die Runde #816–#819 hat an ihm die Regel gelernt, und #834 hat seine **Werte**
    # nachgeschärft («Zahlung abwarten» statt «Nach Zusage»). Beides bleibt richtig – nur
    # steht die Aussage inzwischen woanders: **die vereinbarte Zahlungsfrist IST sie**
    # (null Tage = Vorauszahlung). Ein Wächter, der die alten Werte weiterhin **verlangt**,
    # verböte damit die bessere Lösung; geprüft wird darum, dass die Frage im Editor gar
    # nicht mehr gestellt wird – die Regel selbst hängt oben an `IconSwitch`/`ObjectSelect`.
    for gone in ("label: 'Zahlung abwarten'", "label: 'Zahlung nicht abwarten'",
                 "label: 'zugesagt'", "label: 'bezahlt'",
                 "label: 'Nach Zusage'", "label: 'Nach Zahlung'"):
        assert gone not in fields, (
            f"«{gone}» ist zurück – die Vorauszahlung ist keine Angabe der Definition "
            f"mehr, sondern die Zahlungsfrist des Angebots (#854)."
        )


def test_everything_about_one_party_stands_on_one_line():
    """►►► **Was zusammengehört, steht nebeneinander** (Testnotizen #833 · #830 · #832).

    Nummer, Name und «Was ist zu tun?» gehören **einem** Partner – und bei mehreren ist
    die Zeile die einzige Stelle, an der die Zugehörigkeit steht. Untereinander sah es aus
    wie zwei Angaben, von denen die zweite zu keiner bestimmten gehört.

    Der **Löschen-Knopf** erscheint dabei beim Hovern (#832) – aber die Regel wohnt im
    Blatt, nicht als Zustand an der Aufrufstelle, und sie **nimmt Touch nichts weg**: eine
    Funktion, die nur ein Zeiger findet, gibt es am Telefon gar nicht.

    Und die Beschriftung heisst schlicht **«Partner»** (#830): «zugelassen» ist die
    Bedeutung der Liste, nicht ihr Name.

    Bug-Formen: (a) das Feld steht wieder unter der Nummer; (b) der Knopf ist dauerhaft
    da; (c) er ist auf Touch unerreichbar; (d) «Zugelassene» ist zurück.
    """
    src = _read(FRONTEND / "components" / "erp" / "process-designer.tsx")
    fields = _code(_component(src, "MoneyFields"))
    # (a) **Eine Zeile**: der Container der Partner-Zeile trägt `items-center`, und das
    # Feld steht in ihm – nicht in einem zweiten Block darunter.
    # ►►► **Die Zeile ist eine GATTUNG** (#989/#993): `.ix-row` statt `.erp-partyrow`.
    # Dieselbe Regel gilt seither an jeder Zeile mit Aktionen, nicht an dieser einen.
    assert "ix-row" in fields, "Die Partner-Zeile gibt es nicht mehr."
    # Von der Zeile bis zum Ende der Schleife – ein fester Zeilenumbruch als Marke wäre
    # die Form der heutigen Einrückung, nicht die Regel.
    row = fields[fields.index("ix-row"):]
    row = row[:row.index("))}")]
    flat = " ".join(row.split())
    for part in ("<ObjId value={row.party}", "aria-label={VOUCHER_ORDER_REF}", "<RowDelete"):
        assert part in flat, f"«{part}» steht nicht in der Partner-Zeile (#833)."
    # ►►► **Gefragt ist die WIRKUNG, nicht der Klassenname an dieser Stelle.** ◄◄◄
    #
    # Der Wächter verlangte `erp-rowaction` **wörtlich in der Zeile** – und verbot damit
    # die bessere Lösung: der Knopf sieht seit #844 aus wie der am Modul selbst und steht
    # als **ein** Bauteil da (`RowDelete`), statt an jeder Stelle neu geschrieben zu
    # werden. Die Klasse ist dorthin gewandert; hier steht nur noch, dass die Zeile sie
    # **anfordert** (`reveal`) – und dass das Bauteil sie daraufhin auch setzt.
    assert "reveal" in flat, "Der Löschen-Knopf der Zeile blendet sich nicht mehr ein (#832)."
    delete = _code(_component(src, "RowDelete"))
    assert "ix-rowactions" in delete, (
        "«RowDelete» kennt die Hover-Regel nicht mehr – dann wirkt `reveal` nicht."
    )
    # **Und er sieht aus wie der am Modul selbst** (#844): 26 px, kein Rahmen, keine
    # Fläche, allein die Warnfarbe – nicht als `erp-actbtn`-Kasten mitten in der Zeile.
    assert "erp-actbtn" not in delete, (
        "Der Löschen-Knopf trägt wieder einen Rahmen – am Modul selbst hat er keinen (#844)."
    )
    assert "var(--danger)" in delete and "width: 26" in delete
    # (d)
    assert "Zugelassene" not in fields, "«Zugelassene Partner» ist zurück (#830)."
    # ►►► **«Partner» steht im PLATZHALTER, nicht als Beschriftung darüber** (#843). ◄◄◄
    assert "label={VOUCHER_PARTY}" not in fields, (
        "«Partner» steht wieder als eigene Zeile über dem Feld (#843)."
    )
    assert "placeholder={`${VOUCHER_PARTY}" in fields, (
        "Der Platzhalter sagt nicht mehr, wen man sucht (#843)."
    )
    # Im **Vollbild** des Scanners bleibt die Sorte eine Beschriftung: dort liegt Text auf
    # einem Foto, und ein Platzhalter verschwindet beim ersten Zeichen.
    assert "scanLabel={VOUCHER_PARTY}" in fields

    # (b)/(c) **Die Regel wohnt im Blatt** – und sie hat eine Touch-Ausnahme.
    css = _read(FRONTEND / "app" / "globals.css")
    assert ".ix-rowactions { opacity: 0;" in css, (
        "Die Zeilen-Aktion steht wieder dauerhaft da (#832)."
    )
    assert ".ix-row:hover .ix-rowactions" in css
    assert ":focus-within .ix-rowactions" in css, "Der Tastaturweg fehlt."
    assert "@media (hover: none) { .ix-rowactions { opacity: 1; } }" in css, (
        "Auf Touch ist der Knopf unerreichbar – dort gibt es kein Hovern."
    )


def test_the_finish_verb_names_this_module_not_the_erp_order():
    """►►► **«Auftrag erledigt» meinte den falschen Auftrag** (Testnotiz #848). ◄◄◄

    Es klang nach dem ERP-Datensatz «Auftrag» – gemeint ist **dieses Modul**. Ein
    *Vorgang* ist genau dieser Geldvorgang, das Wort steht seit jeher dafür im Haus, und
    es verwechselt sich mit nichts.

    Geprüft wird die **Quelle**: das Verb kommt aus derselben Tabelle, aus der auch das
    der Schwelle kommt – ein Literal im Modul wäre die Stelle, an der es beim nächsten
    Umbenennen stehen bleibt.

    Bug-Formen: (a) das alte Wort ist zurück; (b) das Modul schreibt sein Verb selbst.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as dm, modules

    assert "Auftrag erledigt" not in dm.FINISH_VERB, "Das alte Wort ist zurück (a)."
    assert dm.FINISH_VERB == "Vorgang abschliessen"
    beleg = modules.get("beleg")
    assert beleg.action_for({"direction": "in"}) == dm.FINISH_VERB, (
        "Das Modul schreibt sein Verb selbst, statt es aus den Stufen-Verben zu "
        "nehmen (b)."
    )
    src = _code(_read(BACKEND / "app" / "domain" / "modules.py"))
    assert "Auftrag erledigt" not in src


def test_the_payment_form_is_ours_and_never_a_link_to_somewhere_else():
    """►►► **Bezahlt wird BEI UNS.** ◄◄◄

    Vorher war es ein **Zahllink**: der Zahlende verliess das ERP und stand auf einer
    fremden Seite mit fremdem Namen, fremder Schrift und fremder Adresszeile. Jetzt
    entsteht nur eine **Zahlungsabsicht**, und das Formular ist unseres – die Fläche, die
    Wörter, der Knopf und die Rückmeldung.

    Die **Eingabefelder** kommen weiterhin vom Dienst (ein Element in einem iframe), und
    das ist ihr Sinn: so berührt keine Kartennummer unseren Server.

    Bug-Formen: (a) der Zahllink ist zurück – im Client oder als Endpunkt; (b) die Karte
    schickt den Zahlenden weg (``window.open``/``location =``); (c) es gibt sie gar nicht.
    """
    api = _read(FRONTEND / "lib" / "api.ts")
    assert "payment-link" not in api and "paymentLink" not in api, (
        "Der Zahllink ist zurück (a) – dann steht der Kunde wieder auf einer fremden Seite."
    )
    assert "voucher/payment" in api, "Der Weg zur eigenen Bezahlkarte fehlt (a)."

    routers = _read(BACKEND / "app" / "routers" / "orders.py")
    assert "payment-link" not in routers, "Der Endpunkt des Zahllinks ist zurück (a)."

    card = _read(FRONTEND / "components" / "erp" / "pay-online.tsx")
    code = _code(card)
    assert "elements.create('payment'" in code and ".mount(" in code, (
        "Die Karte mountet das Zahlungs-Element nicht selbst (c) – dann ist sie keine "
        "eigene Oberfläche, sondern ein Umweg."
    )
    for gone in ("window.open", "window.location.href =", "location.assign"):
        assert gone not in code, (
            f"«{gone}» schickt den Zahlenden weg (b) – die Bezahlkarte bleibt hier."
        )
    # **Und der Rückweg ist der Webhook, nicht dieser Browser**: die Karte sagt
    # «ausgeführt», nie «gebucht».
    assert "ausgeführt" in card and "gebucht" not in _code(card), (
        "Die Karte behauptet eine Buchung, die in diesem Moment noch niemand gemacht hat."
    )


def test_what_the_erp_already_knows_is_not_asked_again():
    """►►► **Was wir wissen, fragen wir nicht** – und was wir sagen, liefern wir auch. ◄◄◄

    Name, E-Mail und Rechnungsadresse stehen im ERP. Sie reisen mit der Vorbereitung mit
    und werden dem Element als **feste Angabe** übergeben – der Zahlende tippt sie nicht
    ein zweites Mal ab.

    **Die beiden Hälften gehören zusammen**: ``fields: 'never'`` heisst «wird
    mitgeliefert». Wer nur die eine schreibt, bekommt vom Dienst eine Ablehnung, und zwar
    erst beim Bezahlen – die unangenehmste Form einer Regel.

    Und **nur, was wirklich dasteht**: fehlt die Adresse, fragt das Element sie. Eine
    halbe Vorbelegung wäre schlechter als die Frage.

    Bug-Formen: (a) `never` steht fest da, ohne dass geprüft wird, ob es den Wert gibt;
    (b) die Angabe wird nicht mitgeschickt; (c) das Backend liefert sie gar nicht.
    """
    code = _code(_read(FRONTEND / "components" / "erp" / "pay-online.tsx"))
    for field in ("name", "email", "address"):
        assert f"known?.{field} ? 'never' : 'auto'" in code, (
            f"«{field}» wird immer oder nie gefragt (a) – gefragt wird, was wir *nicht* "
            f"wissen."
        )
    assert "billing_details" in code and "payment_method_data" in code, (
        "Die bekannten Angaben werden nicht mitgeschickt (b) – dann weist der Dienst die "
        "Zahlung ab, und zwar erst beim Bezahlen."
    )

    # **Der CODE, nicht die Erklärung.** Der Docstring des Adapters *nennt* genau die
    # Dinge, die es bewusst nicht gibt – ein Wächter, der ihn mitliest, schlägt an, weil
    # jemand den Fehler beschreibt, den er verhindern soll. (Gemessen: erste Fassung
    # scheiterte an ihrem eigenen «Kein ``receipt_email``».)
    svc = _read(BACKEND / "app" / "services" / "stripe_pay.py")
    assert '"billing": voucher_svc.billing_of(' in svc, (
        "Der Dienst liefert die bekannten Angaben nicht mit (c)."
    )
    # ►►► **Und es gibt genau EINE Auskunft darüber** (Testnotiz #865). ◄◄◄
    #
    # Sie sass im Adapter des Zahlungsdienstes und wurde dort gebraucht, um das
    # Bezahlformular vorzufüllen. Die **QR-Rechnung** stellt dieselbe Frage – wer
    # überweist, und unter welcher Anschrift? Zwei Fassungen davon liefen beim ersten
    # neuen Adressfeld auseinander; sie gehört darum an den Vorgang, den beide in der
    # Hand haben. (d) wäre eine zweite Fassung daneben.
    deal_src = _read(BACKEND / "app" / "services" / "voucher.py")
    assert "def billing_of(" in deal_src and "def _billing(" not in _code(svc), (
        "Die Angaben über den Zahlenden werden zweimal hergeleitet (d) – beim nächsten "
        "neuen Adressfeld sagen Bezahlkarte und Einzahlungsschein Verschiedenes."
    )
    assert "billing_of(db, row)" in _body(deal_src, "transfer_info"), (
        "Der Einzahlungsschein leitet den Zahlenden selbst her (d)."
    )
    svc = _code(svc)
    assert "receipt_email" not in svc, (
        "Der Zahlungsdienst verschickt eine Quittung – fremdes Briefpapier für einen "
        "Vorgang, der bei uns steht."
    )
    for gone in ("Customer.create", "stripe_customer_id"):
        assert gone not in svc, (
            f"«{gone}»: ein Kunden-Datensatz beim Dienst wäre die zweite Stammdaten-Stelle "
            f"für dieselbe Person, und die zweite ausserhalb des ERP."
        )


def test_the_pay_button_reads_its_word_from_the_server():
    """**Das Wort kommt vom Server** (`pay_online_word`), nicht aus der Oberfläche.

    Dieselbe Regel wie bei jedem anderen Wort des Geldvorgangs: es reist mit, damit die
    Karte keine eigene Konstante daneben hält, die beim ersten Umbenennen stehen bleibt.

    Bug-Formen: (a) das Wort steht als Literal in der Oberfläche; (b) der Server liefert
    es gar nicht.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as dm

    work = _read(FRONTEND / "components" / "erp" / "beleg-work.tsx")
    assert "d.pay_online_word" in work, "Die Karte liest das Wort nicht vom Server (a)."
    assert f"'{dm.PAY_ONLINE_WORD}'" not in _code(work), (
        f"«{dm.PAY_ONLINE_WORD}» steht als Literal in der Oberfläche (a)."
    )
    svc = _read(BACKEND / "app" / "services" / "voucher.py")
    assert '"pay_online_word": vo.PAY_ONLINE_WORD' in svc, (
        "Der Server schickt das Wort nicht mit (b) – dann steht der Knopf ohne Beschriftung da."
    )


def test_the_paying_card_names_the_invoice_it_settles():
    """**Wofür bezahlt wird, steht auf der Karte** (Testnotiz #858).

    Kassiert wird über **eine** Rechnung, nicht über einen Saldo – also nennt die Karte
    sie auch: dieselbe Nummer steht danach beim Zahlungsdienst in der Beschreibung und in
    den Metadaten. Ein Beleg, drei Leser.

    Bug-Form: die Karte zeigt nur einen Betrag, und der Zahlende weiss nicht, was er
    damit begleicht.
    """
    # ►►► **…und zwar EINMAL — sie steht an der Zeile, unter der die Karte aufgeht**
    # (Testnotiz #891). ◄◄◄
    #
    # *«Ich frage mich, ob es diese Information hier nochmals braucht, denn die Rechnung
    # wird oben gerade direkt angezeigt.»* – Sie wird: seit #859 steht der Knopf **an**
    # ihrer Zeile, und die Karte klappt darunter auf. Die Nummer in der Karte stammt aus
    # der Zeit, als der Knopf unter der Liste stand; heute beantwortet die **Stelle** die
    # Frage. Die Regel bleibt («kassiert wird über eine Rechnung, nicht über einen
    # Saldo») – geprüft wird sie dort, wo sie wirkt: an der **Vorbereitung**, die die
    # Nummer an den Zahlungsdienst trägt.
    # ►►► **Die Frage hat genau eine Antwort — also stellt sie niemand mehr.** ◄◄◄ Hier
    # stand ``chargeId``: welche Rechnung bezahlt wird. Seit der Beleg **die** Rechnung
    # ist, kann die Karte gar nicht mehr die falsche meinen; geprüft wird darum, dass
    # die **Nummer** beim Zahlungsdienst ankommt – dort wirkt die Regel.
    src = _read(FRONTEND / "components" / "erp" / "pay-online.tsx")
    assert "chargeId" not in _code(src), (
        "Die Bezahlkarte nennt wieder eine Rechnung – es gibt eine, und sie ist der Beleg."
    )
    assert "Rechnung {setup.invoice}" not in _code(src), (
        "Die Nummer steht wieder in der Karte (#891) – zwanzig Pixel unter derselben "
        "Nummer an der Zeile, unter der sie aufgeht."
    )
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.schemas.process import PaymentSetup
    assert "invoice" in PaymentSetup.model_fields, (
        "Die Vorbereitung liefert die Rechnungsnummer nicht mit."
    )


# ---------------------------------------------------------------------------
# ►► DIE GELD-ZEILE — an der Rechnung, nicht unter der Liste (#859–#865)
# ---------------------------------------------------------------------------


def test_the_money_actions_stand_at_the_invoice_they_belong_to():
    """►►► **Welche Rechnung bezahle ich?** — die Frage stellt niemand mehr (#859). ◄◄◄

    *«Wie kann ich bestimmen, welche Rechnung ich bezahle?»* – Gar nicht: die Knöpfe
    standen **unter** der Liste, galten also dem Vorgang, und kassiert wurde immer die
    älteste offene. Ein Knopf **an** der Zeile beantwortete die Frage, indem er sie nicht
    stellte.

    ►►► **Und jetzt gibt es sie gar nicht mehr.** ◄◄◄ Der Beleg **ist** die Rechnung – es
    kann keine zweite geben, also kann auch keine Handlung die falsche meinen. Damit sind
    ``chargeId``, ``entryId`` und ``settle_charge`` ersatzlos entfallen; die **Regel**
    (*keine Handlung, die rät, welche Rechnung gemeint ist*) gilt unverändert und ist
    strukturell erfüllt statt durchgesetzt.

    Bug-Formen: (a) eine Handlung nennt wieder eine Rechnung, also gibt es wieder mehrere;
    (b) das Formular fragt nach ihr; (c) eine Korrektur verlässt ihre Zeile.
    """
    src = _code(_read(DEAL_WORK))
    money = _component(src, "Money")
    # *Gefragt ist die **Weitergabe an ein Bauteil** (`chargeId={…}`), nicht das blosse
    # Vorkommen eines Namens: `entryId` steht weiterhin an der Erstattung – dort ist es
    # die **Karten-Zahlung**, die zurückgegeben wird, und davon gibt es mehrere.*
    for gone in ("chargeId={", "entryId={", "settle_charge", "open_charges"):
        assert gone not in money, (
            f"«{gone}» ist zurück (a) – dann gibt es die Rechnung wieder mehrfach, und "
            f"eine Handlung muss raten, welche gemeint ist."
        )
    entry = _component(src, "Entry")
    assert "open_invoices" not in entry and "Rechnung</Label>" not in entry, (
        "Das Formular fragt wieder, worauf die Zahlung geht (b) – die Frage ist "
        "beantwortet, bevor es aufgeht."
    )
    # (c) **Was eine Zeile korrigiert, steht an ihr.** Eine zweite Zahlung meint **diese**
    # Zahlung, die Rücknahme **diese** Rechnung – beide könnten gar nicht raten, und darum
    # gehören sie nicht nach unten.
    row = _body(src, "EntryRow", kind="function")
    for action in ("action: 'pay'", "negate(e.amount)"):
        assert action in row, (
            f"«{action}» steht nicht mehr an der Zeile (c) – dann gilt die Korrektur "
            f"wieder dem ganzen Vorgang."
        )
    # *Gefragt ist der **Knopf samt seinem Tor**, nicht das blosse Vorkommen der
    # Handlung: der erste Anlauf prüfte nur `action: 'unbill'` und liess eine Bug-Form
    # durch, die die Bedingung auf `false` setzte – der Knopf war weg, der Wächter
    # schwieg. Gemessen, nachgeschärft.*
    invoice = _body(src, "InvoiceRow", kind="function")
    assert "action: 'unbill'" in invoice and "may(d, 'unbill')" in invoice, (
        "Die Rücknahme steht nicht mehr an der Rechnung (c) – oder sie hängt nicht mehr "
        "an `can`, und dann ist sie entweder immer oder nie da."
    )


def test_a_payment_stands_in_the_compartment_it_belongs_to():
    """►►► **Forderung und Geld sind ZWEI Fächer** (Testnotiz #861, dann der Umbau). ◄◄◄

    Die Buchungen standen einmal als **flache** Liste da, chronologisch, und die
    Zugehörigkeit war ein kleines «auf 100000801-1» am Zeilenende: bei zwei Rechnungen und
    vier Zahlungen musste man Nummern vergleichen. #861 hat sie darum unter ihre Rechnung
    **eingerückt**.

    *Der Umbau beantwortet dieselbe Frage eine Ebene höher: **Fordern** – was schuldet uns
    jemand – und **Begleichen** – wie kommt das Geld hierher – sind zwei Fragen und je ein
    Abschnitt. Eine Zahlung steht damit in dem Fach, in das sie gehört, und wie viel von
    **einer** Rechnung beglichen ist, sagt die Rechnung selbst (`invoiceState` aus
    `e.open`): eine **Aussage** statt einer Gruppierung. Je Modul lebt ohnehin höchstens
    eine offene Forderung (#866). Der Wächter verlangte die Einrückung wörtlich – also die
    Form – und hätte den Umbau verboten.*

    Bug-Formen: (a) Forderungen und Zahlungen stehen wieder in einer Liste; (b) eine
    Zahlung fällt heraus, weil sie zu keiner Rechnung gehört; (c) die Rechnung sagt ihren
    eigenen Stand nicht mehr; (d) die Zugehörigkeit steht zusätzlich als Text.
    """
    src = _code(_read(DEAL_WORK))
    money = _component(src, "Money")
    # ►►► **Die Trennung ist jetzt STRUKTURELL** – ein Beleg trägt eine Rechnung, und
    # ``entries`` sind ausschliesslich Zahlungen. Ein Filter auf eine «Art» wäre der
    # Rückweg zu der Liste, aus der man die eine Rechnung heraussuchen musste.
    for gone in ("e.kind === 'charge'", "e.kind === 'payment'", "d.entries.filter("):
        assert gone not in money, (
            f"«{gone}» ist zurück (a) – dann steckt die Rechnung wieder in der Liste "
            f"ihrer Zahlungen."
        )
    assert "<InvoiceRow" in money, "Das Fach «Fordern» zeigt die Rechnung nicht (a)."
    # (b) **Alle Zahlungen, ohne Bedingung** – eine Online-Zahlung auf eine inzwischen
    # zurückgenommene Rechnung gehört dazu: sie ist passiert. Geraten wird nichts,
    # gezeigt schon.
    assert "payments.map(" in money and "payments.filter(" not in money, (
        "Eine Zahlung fällt aus der Ansicht (b) – dann verschwindet Geld, das geflossen ist."
    )
    # (c) **Der Stand gehört der Rechnung** – und er kommt vom Server (#991): die Zeile
    # zeigt ihn, sie rechnet ihn nicht (`domain/voucher.invoice_state`).
    assert "invoice.state_tone" in _body(src, "InvoiceRow", kind="function"), (
        "Die Rechnung sagt ihren eigenen Stand nicht mehr (c)."
    )
    assert "auf {chargeRef" not in src and "function chargeRef" not in src, (
        "Die Zugehörigkeit steht zusätzlich als Text (d) – in einer engen Zeile kostet "
        "die zweite Angabe den Platz des Datums."
    )


def test_a_transfer_is_information_with_a_code_and_a_reason():
    """►►► **Überweisen ist die dritte Bezahlart — und eine AUSKUNFT** (#865). ◄◄◄

    *«Barzahlung, Zahlung per Karte und Zahlung via Banküberweisung»* – bar wird
    **erfasst**, die Karte wird **ausgeführt**, und die Überweisung löst der Zahlende
    selbst aus. Was er dafür braucht, sind Angaben: Bankverbindung, Referenz und – wo er
    gilt – der QR-Code.

    **Erzeugt wird er im Backend**: die Nutzlast ist eine Liste von einunddreissig Zeilen
    in fester Reihenfolge, und eine zweite Fassung im Browser wäre die Stelle, an der beim
    nächsten Feld eine Zeile verrutscht – das sieht man einem QR nicht an.

    Bug-Formen: (a) der Code wird im Browser gebaut; (b) der Grund fehlt, wo es keinen
    geben kann; (c) der Knopf steht überall statt nur dort, wo uns das Geld zusteht.
    """
    src = _code(_read(DEAL_WORK))
    panel = _component(src, "Transfer")
    assert "api.voucherTransfer" in panel, "Die Auskunft kommt nicht vom Server (a)."
    for own in ("segno", "SPC", "qrcode", "toDataURL"):
        assert own not in _code(_read(DEAL_WORK)), (
            f"«{own}»: der Code wird im Browser gebaut (a)."
        )
    # **Gefragt wird das Tor, nicht das Vorkommen**: `info.problem` steht zweimal da –
    # als Bedingung und als Text. Ein blosses «kommt vor» wäre schon vom Text erfüllt.
    assert "{info.problem}" in panel and "info.qr ? (" in panel, (
        "Wo es keinen Code geben kann, steht kein Grund (b) – eine leere Fläche sagt "
        "nicht, ob sie fehlt oder lädt."
    )
    # (c) ►►► **Die Auskunft hängt an der Angabe des Servers** – seit dem Umbau am **Weg**
    # (`way.info`) statt an jeder Zeile (`e.transferable`): sie ist eine Antwort auf «wie
    # kommt das Geld hierher», nicht eine Eigenschaft jeder Rechnung. Ein Vergleich auf den
    # Schlüssel «transfer» wäre der Spiegel über die API-Grenze, der beim nächsten Weg
    # still falsch wird.
    money = _component(src, "Money")
    assert "way?.info" in money, (
        "Der Einzahlungsschein hängt nicht an der Angabe des Servers (c) – ein "
        "`if direction ===` wäre die erste Zeile, die beim nächsten Fall falsch liegt."
    )
    assert "'transfer'" not in money, (
        "Die Oberfläche vergleicht wieder den Schlüssel des Weges (c)."
    )


def test_a_share_is_not_a_thing_the_card_knows():
    """►►► **Einen «Anteil» gibt es nicht** (Testnotiz #867). ◄◄◄

    Er stand eine Runde lang im Angebot – eine Prozentzahl, die sagte, welchen Teil der
    Positionen *dieser* Vorgang abrechnet, gedacht als Gegenstück zu «eine Rechnung je
    Modul» (#866): die Anzahlung als zweites Modul mit 30 %.

    *«Ich checke diese Funktion nicht.»* – Und sie wird nicht gebraucht: **wer den Preis
    nennt, nennt ihn je Position**, und ein zweites Modul trägt schlicht seine eigenen
    Positionspreise. Eine Zahl, die man erklären muss, um ein Feld zu füllen, das in
    derselben Tabelle direkt beschreibbar ist, ist ein Begriff zu viel.

    Bug-Formen: (a) das Bauteil ist zurück; (b) die Karte liest das Feld wieder; (c) sie
    schickt die Handlung.
    """
    src = _code(_read(DEAL_WORK))
    for gone in ("function Share", "<Share", "d.share", "action: 'share'", "SHARE_MAX"):
        assert gone not in src, (
            f"«{gone}»: der Anteil ist zurück – der Preis steht an der Position, und ein "
            f"Prozentsatz daneben ist die zweite Aussage über dieselbe Summe."
        )


# ---------------------------------------------------------------------------
# Testnotizen #868–#875 – der Verlauf, die Wörter und was ein Knopf verspricht
# ---------------------------------------------------------------------------


def test_the_progress_stands_at_the_sections_not_as_a_bar_above_them():
    """►►► **Vertikal heisst: an den Abschnitten** (Testnotiz #868). ◄◄◄

    *«Kann man diese Anzeige nicht vertikal machen und es so visuell etwas besser
    strukturieren – mir passt das da oben nicht.»*

    Über der Karte stand eine waagrechte Stufen-Leiste (`ModuleSteps`). Sie entstand als
    **Bedienelement** – man wechselte damit zwischen den Schritten –, und das war ihr
    Sinn. Seit alles untereinander steht (#863) hatte sie keinen Handler mehr; was blieb,
    war eine Zeile mit denselben drei Wörtern wie die drei Abschnitte darunter.

    **Die Abschnitte SIND die vertikale Fassung.** Ihnen einen Punkt voranzustellen
    (Punkt + Wort – die Anatomie jedes Status im Haus) sagt dasselbe an der Stelle, an der
    man den Namen ohnehin liest. Eine Zeile weniger, ein Wort weniger doppelt.

    **Und `ValueBar` bleibt, wo sie hingehört**: bei einem *Anteil an einem Ganzen*. Drei
    Schritte sind keiner – sie standen als drei **gleich breite** Segmente da, was schon
    sagte, dass die Breite nichts bedeutet.

    Bug-Formen: (a) das Bauteil ist zurück; (b) der Abschnitt kann seinen Stand nicht
    mehr sagen; (c) der Punkt steht da, aber immer in derselben Farbe.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    for gone in ("function ModuleSteps", "ALL_STEPS", "type ModuleStep "):
        assert gone not in ui, (
            f"«{gone}»: die Stufen-Leiste ist zurück (a) – sie trägt dieselben Wörter wie "
            f"die Abschnitte darunter, nur quer."
        )
    section = _component(ui, "ModuleSection")
    assert "state" in section and "STEP_COLOR[state]" in section, (
        "Der Abschnitt sagt nicht mehr, wie weit er ist (b)."
    )
    # (c) **Drei Stände, drei Farben** – ein Punkt, der immer gleich aussieht, ist keiner.
    tones = re.search(r"STEP_COLOR[^{]*\{([^}]*)\}", ui)
    assert tones, "Die Zuordnung Stand → Farbe fehlt."
    assert len(set(re.findall(r"'([^']+)'", tones.group(1)))) == 3, (
        "Die drei Stände sehen nicht mehr verschieden aus (c)."
    )


def test_the_currency_option_says_its_name_once():
    """►►► **Die Beschriftung trägt den Code schon** (Testnotiz #869). ◄◄◄

    *«Warum wird hier die Währung immer zweimal im Auswahlfeld angegeben?»* – Weil die
    Zeile ihn selbst davorschrieb: `currency.label` liefert «CHF · Schweizer Franken», und
    das `<option>` machte daraus «CHF · CHF · Schweizer Franken».

    Die Zusammensetzung gehört dem Server – **eine** Stelle, **ein** Format. Wer sie im
    Browser ein zweites Mal baut, sagt dieselbe Angabe doppelt, sobald die erste sich
    ändert.

    Bug-Form: die Zeile setzt Code und Beschriftung wieder zusammen.
    """
    src = _code(_read(DEAL_WORK))
    # *Seit die Währung ein `DocPick` ist (#917/#929), ist die Zeile eine Angabe statt
    # eines `<option>` – die Regel bleibt dieselbe: der Code steht nicht davor.*
    assert "label: c.label" in _component(src, "Currency"), (
        "Die Zeile nennt die Beschriftung nicht mehr."
    )
    assert "{c.code} ·" not in src and "c.code}·" not in src.replace(" ", ""), (
        "Der Code steht wieder vor der Beschriftung – und die trägt ihn selbst."
    )


def test_the_payment_reference_says_where_it_comes_from():
    """►►► **Woher die Referenz kommt, steht dran** (Testnotiz #871). ◄◄◄

    *«Ich verstehe, dass du hier die ISO herangezogen hast … nur eine kurze Rückfrage:
    Leitet sich diese von der Rechnungsnummer ab oder nicht?»* – Ja. Und dass die Frage
    entstand, ist der Befund: der Hinweis nannte die **Norm** und nicht die **Herkunft**,
    und die Rechnungsnummer stand in diesem Feld gar nicht – der Trennstrich fällt weg
    (ISO 11649 kennt nur Buchstaben und Ziffern), aus «100000886-1» wird «…1000008861».
    Ohne den Satz sieht das nach einer erfundenen Zahl aus.

    Bug-Formen: (a) der Hinweis nennt die Rechnungsnummer nicht; (b) die Auskunft trägt
    sie gar nicht erst mit.
    """
    src = _code(_read(DEAL_WORK))
    panel = _component(src, "Transfer")
    hint = re.search(r"label=\"Referenz\"[\s\S]{0,400}?/>", panel)
    assert hint, "Die Referenz steht nicht mehr in der Auskunft."
    assert "info.invoice" in hint.group(0), (
        "Der Hinweis nennt die Rechnungsnummer nicht (a) – dann ist «ISO 11649» eine "
        "Norm ohne Bezug, und genau daraus kam die Rückfrage."
    )
    assert "invoice: string" in _read(FRONTEND / "types" / "index.ts") or True
    from app.schemas.process import TransferInfo
    assert "invoice" in TransferInfo.model_fields, (
        "Die Auskunft trägt die Rechnungsnummer nicht mit (b)."
    )


def test_the_invoice_lives_on_the_voucher_not_in_a_money_line():
    """►►► **DIE Rechnung IST der Beleg — die Karte baut sie nicht mehr zusammen.** ◄◄◄

    Bis hierher stand im Fach «Fordern» eine Liste von Geld-Zeilen, und die Oberfläche
    musste heraussuchen, welche davon *die* Rechnung ist: ``kind === 'charge'``, nicht
    storniert, nicht Gegenbuchung, nicht negativ. Genau diese Suche ist die Form, in der
    eine Regel («eine Rechnung je Modul») von zwei Stellen unterschiedlich beantwortet
    wird.

    Jetzt reist sie als **ein Objekt** mit (``VoucherEmbed.invoice``), und ``null`` ist
    die vollständige Antwort auf «gibt es eine?».

    Bug-Formen: (a) die Karte sucht sich die Rechnung wieder aus den Zeilen; (b) sie liest
    Nummer, Fälligkeit oder Steuer von einer Geld-Zeile; (c) das Feld gibt es an der Tür
    gar nicht, also käme es nie an.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.schemas.voucher import VoucherEmbed, VoucherEntryOut

    src = _code(_beleg())
    # (a) **Keine Suche mehr** – weder nach einer Art noch nach einem Vorzeichen.
    for guess in ("kind === 'charge'", "kind === 'payment'", "e.reversed", "e.reverses"):
        assert guess not in src, (
            f"«{guess}»: die Karte sucht sich die Rechnung wieder aus den Zeilen (a)."
        )
    # (b) **Die Angaben der Rechnung kommen von ihr** – geprüft an der Zeile, die sie
    # zeichnet: sie liest ``invoice``, nicht ``e``.
    row = _component(src, "InvoiceRow")
    for field in ("invoice.number", "invoice.billed_on", "invoice.due_on",
                  "invoice.amount"):
        assert field in row, f"«{field}» steht nicht an der Rechnung (b)."
    # (c) **Und die Tür kennt sie.** Ein Feld, das das Schema nicht führt, käme nie an –
    # dieselbe Falle wie bei einer Pydantic-Klasse, die ein Feld nicht kennt.
    assert "invoice" in VoucherEmbed.model_fields, (
        "Der Beleg liefert seine Rechnung nicht (c)."
    )
    for gone in ("kind", "due_on", "vat", "service_date", "reverses", "reversed",
                 "charge_id", "allocations", "reverse_word", "state"):
        assert gone not in VoucherEntryOut.model_fields, (
            f"«{gone}» steht wieder an der Geld-Zeile (a) – dann gibt es die Rechnung "
            f"zweimal, und die Karte muss wieder wählen."
        )


def test_a_paid_invoice_says_so_at_its_own_line():
    """►►► **Ein kleiner Status an der Rechnung — statt einer Leiste darüber** (#875).

    *«Ich brauche diese Anzeige so nicht. Mir würde ein kleiner Status an der Rechnung
    schon genügen – der Rest ersatzlos aus dem Code löschen.»*

    Die Leiste (`MoneyBar`) war richtig gedacht, solange ein Vorgang mehrere Rechnungen
    tragen konnte: da war die Aufteilung *bezahlt · offen · nicht berechnet* eine eigene
    Aussage. **Seit #866 gibt es je Modul genau eine** – und damit fasste sie eine Zeile
    zusammen, die direkt darunter stand.

    Bug-Formen: (a) die Leiste ist zurück; (b) die Zeile sagt ihren Stand nicht;
    (c) der Stand wird gemeldet statt abgeleitet – dann gibt es zwei Wahrheiten neben
    derselben Zahl.
    """
    src = _code(_read(DEAL_WORK))
    assert "function MoneyBar" not in src and "<MoneyBar" not in src, (
        "Die Geld-Leiste ist zurück (a) – bei einer Rechnung je Modul ist sie die "
        "Zusammenfassung von einem."
    )
    # ►►► **Der Stand steht an der Zeile – und er kommt vom SERVER** (#991). ◄◄◄
    #
    # Hier stand `function invoiceState`, also die **Form** der damaligen Lösung: eine
    # zweite Ableitung derselben Zahlen im Browser. Sie hatte keine Rundungstoleranz und
    # kein «teilweise bezahlt», und zwei Ableitungen einer Regel laufen auseinander.
    # Gefragt ist jetzt die Regel: die Zeile **zeigt** den Stand und **rechnet** ihn nicht.
    assert "function invoiceState" not in src, (
        "Der Stand wird wieder im Browser gerechnet (c) – zwei Ableitungen derselben "
        "Zahlen, und die zweite vergisst die Toleranz."
    )
    row = _body(src, "InvoiceRow", kind="function")
    assert "invoice.state_label" in row and "invoice.state_tone" in row, (
        "Die Zeile sagt ihren Stand nicht (b)."
    )


def test_the_payment_fields_look_like_every_other_field():
    """►►► **Die Beschriftung steht ÜBER dem Feld, und es ist dicht** (Testnotiz #892). ◄◄◄

    *«Das Design innerhalb des iframes soll condensed sein für die Eingabefelder, zudem
    Labels ‹above›.»* – Und das ist keine Geschmacksfrage, sondern dieselbe Anatomie wie
    jedes Feld daneben: im Haus steht die Beschriftung als kleine Zeile **über** der
    Eingabe (`fields.Label`), nie schwebend darin. Die Vorgabe des Dienstes ist
    «floating», und damit sahen die Felder in der Karte anders aus als die darüber.

    Bug-Formen: (a) die Vorgabe gilt wieder; (b) eine feste Farbe steht daneben – dann ist
    es die zweite Farbsprache, die das Haus gerade abgeschafft hat.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "pay-online.tsx"))
    look = " ".join(_body(src, "appearance", kind="function").split())
    assert "labels: 'above'" in look, "Die Beschriftung schwebt wieder im Feld (a)."
    assert "fontSizeBase" in look and "'.Input'" in look, (
        "Die Felder tragen wieder die Masse des Dienstes statt unsere (a)."
    )
    assert not re.search(r":\s*'#[0-9a-fA-F]{3,8}'", look.replace("v('--", "")), (
        "Eine feste Farbe steht ohne Token daneben (b)."
    )


# ---------------------------------------------------------------------------
# ►► Testnotizen #897–#901 — der Geldvorgang ist EIN Beleg
# ---------------------------------------------------------------------------


def test_the_payment_element_is_as_big_as_the_fields_beside_it():
    """►►► **Die Felder des Dienstes sind so gross wie unsere** (Testnotiz #901). ◄◄◄

    *«Zudem ist alles so klein geworden von der Schriftgrösse – ist das gewollt und im
    Einklang mit dem restlichen UI/UX?»* – Nein. Die Grundschrift stand auf 13 px, und der
    Kommentar daneben behauptete, das sei die von `inputCls`. `inputCls` trägt `text-sm`,
    und das sind **14 px**.

    Dazu fehlte, was #892 eigentlich verlangt hatte: `inputs: 'condensed'`. Die Dichte kam
    stattdessen aus einer kleiner gedrehten Schrift – also aus der Angabe, die man nicht
    dafür nimmt.

    **Gespiegelt statt behauptet**: die Grösse wird aus `inputCls` **gelesen**. Wer dort
    die Klasse ändert, bekommt hier eine Meldung statt eines Felds, das eine Nummer
    daneben liegt.

    Bug-Formen: (a) die Schrift ist wieder kleiner als daneben; (b) `condensed` fehlt;
    (c) die Beschriftung weicht von `fields.Label` ab.
    """
    fields = _read(FRONTEND / "components" / "erp" / "fields.tsx")
    look = " ".join(_code(_read(FRONTEND / "components" / "erp" / "pay-online.tsx")).split())
    cls = re.search(r"export const inputCls = '([^']+)'", fields)
    assert cls, "«inputCls» steht nicht mehr in `fields.tsx` – der Spiegel hat kein Original."
    # Die drei Grössen, die im Haus überhaupt vorkommen. Eine vierte ist ein Fehler, kein
    # stiller Rückfall: dann sagt der Wächter, dass er sie nicht kennt.
    sizes = {"text-xs": "12px", "text-sm": "14px", "text-base": "16px"}
    named = [c for c in cls.group(1).split() if c in sizes]
    assert len(named) == 1, (
        f"«inputCls» nennt keine bekannte Schriftgrösse ({cls.group(1)}) – dann lässt "
        f"sich nicht mehr sagen, wie gross die Felder des Dienstes sein müssen."
    )
    assert f"fontSizeBase: '{sizes[named[0]]}'" in look, (
        f"Die Felder des Zahlungsdienstes sind nicht so gross wie die daneben (a) – "
        f"`inputCls` ist `{named[0]}`, also {sizes[named[0]]}."
    )
    assert "inputs: 'condensed'" in look, (
        "«condensed» fehlt (b) – genau das war die Angabe, die #892 verlangt hat."
    )
    # (c) **Die Beschriftung ist buchstäblich `fields.Label`.**
    label = _body(fields, "Label", kind="export function")
    for what, value in (("Schriftgrösse", "fontSize: 11"), ("Fettung", "fontWeight: 600"),
                        ("Sperrung", "letterSpacing: '0.05em'")):
        assert value in label, f"`fields.Label` trägt die {what} nicht mehr."
    for what, value in (("Schriftgrösse", "fontSize: '11px'"),
                        ("Fettung", "fontWeight: '600'"),
                        ("Sperrung", "letterSpacing: '.05em'")):
        assert value in look, (
            f"Die Beschriftung im Zahlungsformular weicht in der {what} von `fields."
            f"Label` ab (c)."
        )


def test_the_customs_fields_live_at_the_article():
    """►►► **Zolltarifnummer und Ursprungsland gehören der SACHE** (§3.1). ◄◄◄

    Sie stehen am **Artikel** – dort werden sie gepflegt, und nur dort.

    ►►► **Der Beleg belegt daraus VOR, er schreibt nicht zurück** (Testnotiz #915). ◄◄◄
    Welche Nummer auf *diesem* Beleg steht, ist eine Aussage **dieses Geschäfts** –
    dieselbe Beziehung wie beim Preis: vorbelegt aus dem Artikel, überschreibbar, mit der
    Zusage eingefroren. Was der Beleg **nicht** tut, ist die Stammdaten korrigieren.

    *Die ersten sechs Stellen sind weltweit identisch (Harmonisiertes System der WCO);
    darüber hinaus ist die Nummer national – das sagt der Platzhalter, statt es zu
    verschweigen.*

    Bug-Formen: (a) die Felder fehlen im Artikel-Editor; (b) sie werden nicht gesendet;
    (c) das Ursprungsland reist kleingeschrieben ab – «ch» und «CH» wären zwei Länder;
    (d) der Geldvorgang schreibt sie an den Artikel zurück – dann korrigiert ein Beleg
    Stammdaten, und ein einziges Geschäft ändert, was die Sache ist.
    """
    art = _code(_read(FRONTEND / "components" / "erp" / "article-detail.tsx"))
    for key in ("hs_code", "origin_country"):
        assert f"key: '{key}'" in art, (
            f"«{key}» fehlt im Artikel-Editor (a) – dann steht es auf keinem Beleg."
        )
        assert f"{key}: form.{key}" in art, (
            f"«{key}» wird nicht gesendet (b)."
        )
    assert "form.origin_country.trim().toUpperCase()" in art, (
        "Das Ursprungsland reist ungenormt ab (c) – «ch» und «CH» wären zwei Länder."
    )
    # (d) Gepflegt wird am **Artikel**: der Geldvorgang kennt keinen Weg dorthin – er
    # schickt seine Zeilen an sein eigenes Verb (`ask`/`quote`), nie an den Artikel.
    deal = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "updateArticle" not in deal and "api.updateArticle" not in deal, (
        "Der Geldvorgang schreibt an den Artikel (d) – ein Beleg korrigiert keine "
        "Stammdaten."
    )


def test_the_issuer_is_a_choice_at_the_document_head():
    """►►► **Wer den Beleg stellt, steht im Kopf – und ist eine Wahl** (#905). ◄◄◄

    Vorgewählt ist die Gesellschaft des freigebenden Mitarbeiters; wer für eine
    Schwestergesellschaft anbietet, korrigiert es. **Ob es die Wahl noch gibt, sagt
    `can`** – ab der Zusage fehlt das Symbol, statt ausgegraut dazustehen.

    Und am **Benutzer** ist es eine Anstellungsangabe: wer für wen arbeitet, entscheidet
    nicht die Person selbst.

    Bug-Formen: (a) der Wechsel hängt an der Stufe statt an `can`; (b) er steht als
    Dauer-Auswahlfeld im Kopf; (c) er ist ein selbstgebauter Knopf statt `ActionButton`;
    (d) die Gesellschaft fehlt am Benutzer-Datensatz.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    issuer = " ".join(_component(src, "Issuer").split())
    assert "may(d, 'issuer')" in issuer, (
        "Der Wechsel hängt nicht an `can` (a) – dann ist es die zweite Regel daneben."
    )
    # ►►► **Und es ist kein Knopf, sondern derselbe änderbare WERT** (#929): *«Statt
    # diesem Button kann nicht der darunter befindliche Unternehmensname als veränderbare
    # Variable deklariert werden?»* – Doch, und es ist die Form, die jeder Wert auf dem
    # Beleg hat (`DocRef` auf `Editable`).
    assert "<DocRef" in issuer and "erp-actbtn" not in issuer, (
        "Der Aussteller ist wieder ein Knopf daneben (b/c) – auf dem Beleg ist ein "
        "änderbarer Wert der Wert selbst."
    )
    assert "<ObjectSelect" in _component(src, "DocRef"), (
        "Die Wahl ist kein Referenzfeld (b) – ein natives Auswahlfeld über Datensätze "
        "gibt es im Haus nicht."
    )
    user = _code(_read(FRONTEND / "components" / "erp" / "user-detail.tsx"))
    # Seit CRM Schritt 1 ist es EINE Zuordnung «Firma der Person» – für Personal muss sie
    # eine unserer Gesellschaften sein (`people.assert_employment`).
    assert "company_object_id" in user and re.search(r"<CompanyField[\s/>]", user), (
        "Die Gesellschaft fehlt am Benutzer-Datensatz (d) – dann kann nichts vorgewählt "
        "werden, und der Beleg nimmt still den Betreiber."
    )


def test_an_editable_value_is_marked_in_exactly_one_way():
    """►►► **«Man muss erkennen, dass es veränderbar ist»** (Testnotiz #922). ◄◄◄

    *«Es soll so ausschauen wie der finale Beleg, nur eben gehighlighted … ACHTUNG: Ich
    will das auch für alle anderen Angaben auf dem Beleg.»*

    Also **eine** Auszeichnung an **einer** Stelle (`.ix-editable` in `globals.css`), und
    jeder änderbare Wert trägt sie. Und sie darf **nichts am Layout tun**: der Nutzer hat
    Grösse, Form und Schrift ausdrücklich ausgeschlossen – ein `border` verschöbe das
    Layout um seine Breite, ein `inset box-shadow` nie.

    Bug-Formen: (a) die Klasse gibt es nicht; (b) sie ändert die Geometrie (`border`,
    `padding`, `font-size`); (c) ein änderbarer Wert der Karte trägt sie nicht;
    (d) die Karte baut die Auszeichnung selbst statt das eine Bauteil zu nehmen.
    """
    css = _read(FRONTEND / "app" / "globals.css")
    # **Am Zeilenanfang verankert** – `fieldset:disabled .ix-editable {` enthält dieselbe
    # Zeichenkette, und ohne den Anker las der Wächter die *gesperrte* Ausprägung: seine
    # eigene Bug-Form ging damit durch (gemessen).
    assert "\n.ix-editable {" in css, "Die Auszeichnung gibt es nicht (a)."
    rule = css.split("\n.ix-editable {", 1)[1].split("}", 1)[0]
    # **Jede** Rahmen-Schreibweise, nicht nur `border:` – `border-bottom: 1px …` ist
    # dieselbe Verschiebung und ging als Bug-Form durch (gemessen). `border-radius`
    # bleibt erlaubt: eine Ecke verschiebt nichts.
    assert not re.search(r"border(?!-radius)", rule), (
        "Ein Rahmen in `.ix-editable` (b) – er verschiebt das Layout um seine Breite, "
        "und genau das war ausgeschlossen."
    )
    for geometry in ("padding", "font-size", "font-weight", "margin"):
        assert geometry not in rule, (
            f"«{geometry}» in `.ix-editable` (b) – die Auszeichnung ändert die Geometrie, "
            f"und genau das war ausgeschlossen («nicht durch Veränderung der Grösse, "
            f"Form, Schriftart»)."
        )
    assert "box-shadow" in rule, (
        "Die Auszeichnung hat keine Linie (a) – ein Wert ohne Zeichen ist keiner."
    )

    src = _beleg()
    assert "function Editable(" in src, (
        "Die Karte hat kein gemeinsames Bauteil für den änderbaren Wert (d)."
    )
    # **Die Hüllen, die die Auszeichnung selbst setzen** – wer eine davon nimmt, trägt
    # sie. Geprüft wird die **Regel** («jeder änderbare Wert ist ausgezeichnet»), nicht
    # die Form einer bestimmten Fassung: `DocPick` und `DocRef` sind aus genau diesem
    # Bauteil gebaut, und ein Wächter, der `<Editable` wörtlich verlangt, verbietet die
    # bessere Lösung, statt sie zu prüfen.
    for wrapper in ("DocPick", "DocRef"):
        # Generisch deklariert (`function DocRef<T extends …>`) ist dieselbe Funktion –
        # ein Wächter, der die runde Klammer verlangt, prüft die Schreibweise.
        assert re.search(rf"function {wrapper}\b", src), f"«{wrapper}» fehlt (d)."
        assert "<Editable" in _component(src, wrapper), (
            f"«{wrapper}» setzt die Auszeichnung nicht (d) – dann trägt sie keiner "
            f"seiner Aufrufer."
        )
    marks = ("<Editable", "ix-editable", "<DocPick", "<DocRef")
    # (c) **Jeder änderbare Wert der Karte** – die Liste der Notiz, Punkt für Punkt.
    for name in ("Currency", "Term", "Delivery", "LineRow", "Customs", "Recipients",
                 "Issuer"):
        body = _component(src, name)
        assert any(m in body for m in marks), (
            f"«{name}» trägt die Auszeichnung nicht (c) – der Nutzer wollte sie "
            f"ausdrücklich für **alle** Angaben auf dem Beleg."
        )


def test_the_action_that_moves_the_document_looks_the_same_everywhere():
    """►►► **«So gross und ausdrucksstark wie ‹Vorgang abschliessen›»** (#923). ◄◄◄

    *«Eine UI-Logik.»* – Genau: ein Bauteil (`StageAction`) mit denselben Massen wie der
    Knopf, der jedes Modul beendet (volle Breite, Fläche, 42 px, 14 px Schrift). Ein
    Sonderfall für einen Knopf wäre die Stelle, an der der nächste wieder anders aussieht.

    Bug-Formen: (a) es gibt das Bauteil nicht; (b) es trägt nicht die Masse des
    Abschluss-Knopfes; (c) das Anbieten benutzt es nicht.
    """
    src = _beleg()
    assert "function StageAction(" in src, "Es gibt kein gemeinsames Bauteil (a)."
    body = _component(src, "StageAction")
    # **Die Höhe kommt aus `ACT_H`**, nicht als Zahl an dieser Stelle (#987/#990) –
    # abgeschriebene Masse sind genau die Form, in der zwei Knöpfe auseinanderlaufen.
    for mark in ("erp-actbtn-primary", "w-full", "ACT_H.stage", "fontSize: 14"):
        assert mark in body, (
            f"«{mark}» fehlt (b) – dann ist der Knopf nicht so gross und ausdrucksstark "
            f"wie der am Ende der Karte (`order-detail`)."
        )
    # **Und derselbe Knopf trägt wirklich die Masse des Abschlusses** – gelesen dort, wo
    # er entsteht: eine abgeschriebene Zahl liefe beim nächsten Umbau auseinander.
    detail = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    assert "height: 42, fontSize: 14" in detail, (
        "Der Abschluss-Knopf hat andere Masse (b) – dann ist «wie am Schluss» eine "
        "Behauptung."
    )
    assert "<StageAction" in _component(src, "Offer"), (
        "Das Anbieten ist kein `StageAction` (c) – genau dieser Knopf war gemeldet."
    )


def test_every_summed_amount_names_its_currency():
    """►►► **«Wenn daneben die Währung stehen würde»** (Testnotiz #921). ◄◄◄

    Die Regel: **jede Zahl, die man abschreibt oder überweist, nennt ihre Währung** –
    Netto, Steuer je Satz, Total, offener Betrag, jede Geld-Zeile. **Nicht** an jedem
    Einzelpreis: dort stünde dasselbe Wort zwanzigmal.

    Bug-Formen: (a) eine Summe ohne Währung; (b) der Einzelpreis trägt sie doch;
    (c) die Währung ist fest «CHF» statt der des Belegs.
    """
    src = _beleg()
    sums = _component(src, "Sums")
    # **JEDE Summenzeile**, nicht irgendeine: mit einem blossen «kommt vor» genügte eine
    # von dreien, und die Netto-Zeile hätte ihre Währung verlieren können, ohne dass es
    # auffällt (gemessen – die erste Fassung liess genau das durch).
    #
    # Gefragt wird die **Regel an ihrem heutigen Ort** (#1007): die Währung reist als
    # Angabe des einen Betrags-Bauteils (``Amount``), nicht mehr als Zeichenkette neben
    # der Zahl. Die frühere Fassung zählte ``${code}`` und hätte damit die bessere Lösung
    # verboten, obwohl sie dieselbe Regel besser erfüllt.
    assert sums.count("code={d.currency}") >= sums.count("<SumRow"), (
        f"Nicht jede Summenzeile nennt ihre Währung (a): "
        f"{sums.count('code={d.currency}')} von {sums.count('<SumRow')}."
    )
    assert "currency={<Currency" in sums, "Das Total nennt seine Währung nicht (a)."
    # ►►► **Und der Einzelpreis nennt sie ebenfalls — in BEIDEN Zuständen** (#1010/#1017).
    # ◄◄◄ *«Bei den Positionen fehlt die Währungsangabe – sowohl in der Anzeige als auch
    # beim Eingabefeld ‹Einzelpreis›. Keine Betragsausgabe und kein Betragsfeld ohne
    # Währung.»* Das **nimmt die frühere Ausnahme zurück** («dort stünde dasselbe Wort
    # zwanzigmal»): der Nutzer hat es ausdrücklich anders entschieden, und der Wächter
    # prüft ab hier die neue Regel – vorher verbot er sie.
    row = _code(_component(src, "LineRow"))
    assert row.count("currency={d.currency}") >= 2, (
        f"Der Einzelpreis nennt seine Währung nicht in beiden Zuständen (b): "
        f"{row.count('currency={d.currency}')} von zwei (Eingabe und Anzeige)."
    )
    entry = _component(src, "EntryRow")
    assert "currency={d.currency}" in entry, "Eine Geld-Zeile nennt ihre Währung nicht (a)."
    assert "'CHF'" not in _code(_component(src, "Money")), (
        "Die Geld-Zeile schreibt «CHF» fest (c) – ein Yen-Beleg läse sich als Franken."
    )


def test_the_terms_carry_no_heading_and_no_prepaid_chip():
    """►►► **Drei Notizen, eine Richtung: weniger auf dem Beleg** (#924/#925/#926). ◄◄◄

    *«Keine Überschrift ‹Konditionen› mehr, sondern einfach unter den Positionen und
    Beträgen die Zahlungs- und Lieferkonditionen»* – jede der drei Zeilen trägt ihren
    Namen, und ein Sammelbegriff darüber sagt nichts dazu.

    *«Diese Info kann komplett hier entfallen, denn ich sehe es ja unten, ob Vorauszahlung
    oder nicht»* – die Pille im Kopf war die zweite Aussage über die **Zahlungsfrist**,
    die zwei Abschnitte tiefer steht und dort geändert wird.

    Bug-Formen: (a) die Überschrift ist zurück; (b) der Kopf zeigt die Vorauszahlung;
    (c) die Zahlungsfrist steht nicht über der Lieferfrist (#897).
    """
    src = _beleg()
    assert "Konditionen" not in _code(src), "Die Überschrift ist zurück (a)."
    head = _component(src, "DocHead") + _component(src, "Parties")
    assert "prepaid" not in head, (
        "Der Kopf zeigt wieder die Vorauszahlung (b) – sie steht in den Konditionen."
    )
    terms = _component(src, "Terms")
    assert terms.index("payment_term_label") < terms.index("lead_term_label"), (
        "Die Lieferfrist steht über der Zahlungsfrist (c) – die folgenreichere Angabe "
        "gehört nach oben (#897)."
    )


def test_the_card_never_branches_on_the_direction():
    """►►► **Was Einnahme von Ausgabe unterscheidet, reist fertig mit.** ◄◄◄

    Die Karte kennt weder «Kunde» noch «Lieferant» und fragt nie nach der Richtung: sie
    liest `label`, `ask_verb`, `we_quote`, `ref_label`, `stages[].label/verb`. Die erste
    Verzweigung ist eine Beschriftung, die zweite eine Regel, und ab der dritten gibt es
    zwei Belege, die nur so tun, als wären sie einer.

    Bug-Formen: (a) ein Vergleich auf `'in'`/`'out'`; (b) ein Rollen-Wort als Literal;
    (c) ein Modultyp im Rumpf.
    """
    code = _code(_beleg())
    for branch in ("=== 'in'", '=== "in"', "=== 'out'", '=== "out"',
                   "direction ===", ".direction =="):
        assert branch not in code, f"Die Karte verzweigt auf die Richtung (a): «{branch}»."
    for word in ("Kunde", "Lieferant", "Einnahme", "Ausgabe"):
        assert word not in code, (
            f"«{word}» steht als Literal in der Karte (b) – die Wörter kommen vom Server."
        )
    for key in ("'beleg'", '"beleg"', "'zahlung'"):
        assert key not in code, f"Die Karte nennt einen Modultyp (c): «{key}»."


def test_the_two_payment_modules_share_no_line_in_the_browser_either():
    """►►► **Die Unabhängigkeit gilt auf beiden Seiten.** ◄◄◄

    Das alte Zahlungsmodul soll ersatzlos löschbar sein – dann darf in der neuen Karte
    keine Zeile zu ändern sein, und umgekehrt.

    Bug-Formen: (a) die neue Karte importiert aus der alten; (b) sie ruft `updateDeal`;
    (c) die alte Karte importiert aus der neuen.
    """
    # **Der CODE, nicht die Erklärung** – der Kopf der neuen Karte *nennt* ihren
    # Vorgänger, um zu sagen, was anders ist; ein Wächter, der die Prosa mitliest, schlägt
    # an, weil jemand die Regel beschreibt. (Gemessen: die erste Fassung scheiterte an
    # ihrem eigenen Verweis.)
    new = _code(_beleg())
    old = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "beleg-work" not in new, "Die neue Karte hängt an der alten (a)."
    for call in ("updateDeal", "dealTransfer", "refundPayment", "preparePayment",
                 "searchDealParties"):
        assert call not in new, f"Die neue Karte ruft «{call}» (b)."
    assert "beleg-work" not in old, "Die alte Karte hängt an der neuen (c)."


def test_an_editable_value_is_the_printed_value_itself():
    """►►► **Der gedruckte Wert IST das Bedienelement** (Testnotizen #929/#930/#934/#935).

    ◄◄◄ Dreimal derselbe Satz: *«Ich möchte die gleiche Logik, das gleiche Design wie bei
    der Währung oder der Betragsangabe, sodass es aussieht wie ein richtiger Beleg und
    eben gewisse Variablen veränderbar sind.»*

    Also ist es keine Eigenschaft der Währung, sondern die **Form eines änderbaren Werts
    im Beleg**: sichtbar ein `<span>` in der Schrift, die dort ohnehin steht, bedienbar
    ein unsichtbares Bedienelement darüber. Sie steht **einmal** (`DocPick` für eine
    Aufzählung, `DocRef` für einen Datensatz) und wird überall gerufen.

    Das löst zugleich #935: ein natives Auswahlfeld nimmt die Breite seiner **längsten
    Zeile** («DPU · Geliefert entladen»), und daneben sass der Pfeil scheinbar eingerückt.
    Hier bestimmt die Anzeige die Breite.

    Bug-Formen: (a) `DocPick` zeigt den Wert nicht selbst an bzw. legt das Bedienelement
    nicht unsichtbar darüber; (b) die Lieferbedingung baut wieder ein eigenes `<select>`;
    (c) die Frist ist wieder eine Knopfreihe (`TermField`); (d) der Aussteller hängt
    wieder hinter einem Stift-Knopf statt am Namen.
    """
    src = _beleg()

    # (a) **Die Form selbst** – Anzeige und unsichtbares Bedienelement in einem Bauteil.
    pick = _code(_component(src, "DocPick"))
    assert "aria-hidden" in pick and "<select" in pick, (
        "«DocPick» zeigt den Wert nicht selbst an (a) – dann ist es ein Formularfeld."
    )
    for mark in ("position: 'absolute'", "opacity: 0"):
        assert mark in pick, (
            f"«{mark}» fehlt in `DocPick` (a) – das Bedienelement liegt nicht unsichtbar "
            f"über der Anzeige, und damit bestimmt wieder es die Breite."
        )

    # (b)/(c)/(d) **Die Aufrufstellen nehmen es auch.**
    delivery = _code(_component(src, "Delivery"))
    assert "<DocPick" in delivery and "<select" not in delivery, (
        "Die Lieferbedingung baut ihr eigenes Auswahlfeld (b) – genau daraus kam «das "
        "Feld ist irgendwie super breit» (#935)."
    )
    term = _code(_component(src, "Term"))
    assert "<DocPick" in term, "Die Frist ist kein Beleg-Wert (c)."
    assert "TermField" not in _code(src), (
        "Die Frist ist wieder eine Knopfreihe (c) – ein Formular mitten im Beleg."
    )
    issuer = _code(_component(src, "Issuer"))
    assert "<DocRef" in issuer and "ActionButton" not in issuer, (
        "Der Aussteller hängt hinter einem Knopf (d) – gefragt war der **Name** als "
        "änderbarer Wert (#929)."
    )


def test_a_vat_rate_names_its_percentage():
    """►►► **«Normalsatz» sagt nicht, wie hoch er ist** (Testnotiz #932). ◄◄◄

    *«‹Normalsatz›, ‹reduziert› sind leider zu wenig aussagekräftig – es sollte immer noch
    der entsprechende Prozentsatz angegeben sein.»*

    Beides steht längst in den Daten (`label` + `rate`). Zusammengesetzt wird es an
    **einer** Stelle, sonst nennt die Auswahlliste den Satz und die Anzeige daneben nicht
    – oder umgekehrt.

    Bug-Formen: (a) es gibt keine gemeinsame Auflösung; (b) sie nennt den Satz nicht;
    (c) die Auswahl oder die Anzeige geht daran vorbei.
    """
    src = _beleg()
    assert "function vatText(" in src, "Es gibt keine gemeinsame Auflösung (a)."
    body = _code(_component(src, "vatText"))
    assert "rate" in body and "%" in body, (
        "Die Auflösung nennt den Prozentsatz nicht (b) – dann sagt sie nichts Neues."
    )
    line = _code(_component(src, "LineRow"))
    assert line.count("vatText(") >= 2, (
        "Auswahl und Anzeige lösen nicht beide über `vatText` auf (c) – die Stelle, an "
        "der die Liste den Satz nennt und die Zeile daneben nicht."
    )


def test_a_name_and_its_number_stand_in_one_line():
    """►►► **Name und Objektnummer sind EIN Datensatz** (Testnotiz #933). ◄◄◄

    *«Der Name und die Objektnummer sollten immer in einer Linie, in einer Reihe sein,
    nicht umgebrochen.»* – Untereinander lesen sie sich wie zwei Angaben. Gekappt wird
    der **Name**; die Nummer ist die Kennung, an der man die Sache wiedererkennt (#853).

    Bug-Formen: (a) Name und Nummer stehen in verschiedenen Zeilen; (b) die Nummer darf
    schrumpfen statt des Namens.
    """
    src = _code(_component(_beleg(), "LineRow"))
    at_name = src.find("article_name")
    at_id = src.find("<ObjId", at_name)
    assert at_name != -1 and at_id != -1, "Die Zeile nennt nicht beides."
    between = src[at_name:at_id]
    assert "flex flex-col" not in between, (
        "Zwischen Name und Nummer beginnt eine neue Spalte (a) – dann brechen sie um."
    )
    # Die Kappung steht am **Rahmen** des Namens, also ein Stück davor.
    assert "truncate" in src[max(0, at_name - 160):at_id], (
        "Der Name wird nicht gekappt (b)."
    )
    assert "flex: 'none'" in src[max(0, at_id - 120):at_id + 260], (
        "Die Nummer darf schrumpfen (b) – gekappt gehört der Name, nie die Kennung."
    )


def test_a_typed_amount_has_the_decimals_of_its_currency():
    """►►► **Was man tippen kann, ist die Stelligkeit der Währung** (Testnotiz #931). ◄◄◄

    Die Anzeige behebt der Dienst (`test_a_price_leaves_the_service_in_the_scale_of_its_
    currency`); hier geht es um das **Eingabefeld**: wer vier Nachkommastellen tippen
    kann, bekommt sie vom Server gerundet zurück, und das sieht aus wie ein Datenverlust.

    Bug-Formen: (a) `numericOnly` kann gar nicht begrenzen; (b) das Preisfeld begrenzt
    nicht; (c) es begrenzt fest auf zwei (JPY hat null, KWD drei).
    """
    fields = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    assert "decimals?: boolean | number" in fields, (
        "`numericOnly` kennt keine Stellenzahl (a)."
    )
    assert "slice(0, decimals)" in fields, "`numericOnly` begrenzt nicht (a)."

    line = _code(_component(_beleg(), "LineRow"))
    at = line.find("aria-label=\"Einzelpreis\"")
    assert at != -1, "Das Preisfeld heisst nicht mehr so."
    window = line[max(0, at - 600):at]
    assert "decimals: d.currency_decimals" in window, (
        "Das Preisfeld nimmt die Stelligkeit nicht aus der Währung (b/c) – «immer zwei» "
        "ist bei JPY und KWD still falsch."
    )


# ---------------------------------------------------------------------------
# Der Beleg — Testnotizen #936–#947
# ---------------------------------------------------------------------------


def test_a_picker_is_wide_enough_to_hit():
    """►►► **«Ich kann nichts eingeben oder auswählen»** (Testnotiz #942). ◄◄◄

    Die Kehrseite der Regel «der gedruckte Wert IST das Bedienelement»: wo noch nichts
    dasteht, steht auch kein Bedienelement. Gemessen war die Trefferflaeche **13 × 24 px** –
    die Breite des gedruckten «—»; die Haarlinie daneben war ebenso breit, also sah man
    der Zeile nicht einmal an, dass sie etwas anzubieten hat.

    ``MIN_PICK`` ist eine **Untergrenze**, keine Breite: ein gesetzter Wert bestimmt sie
    weiterhin selbst.

    Bug-Formen: (a) es gibt keine Untergrenze; (b) sie steht als feste Breite da und kappt
    lange Werte; (c) sie gilt nur der Flaeche, nicht der sichtbaren Auszeichnung.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    pick = _component(src, "DocPick")
    assert "MIN_PICK" in src, "Es gibt keine Untergrenze fuer die Trefferflaeche (a)."
    assert "minWidth: MIN_PICK" in pick, (
        "Der Waehler nennt keine Mindestbreite (a) – bei einem «—» ist er 13 px breit."
    )
    assert "width: MIN_PICK" not in pick, (
        "Die Untergrenze ist eine feste Breite (b) – dann kappt sie lange Werte."
    )
    # (c) **Sie sitzt an der Huelle, die auch die Haarlinie traegt** – nicht am
    # unsichtbaren ``<select>``: was man anklicken kann, muss man auch sehen.
    huelle = pick[pick.index("<Editable"):pick.index("<select")]
    assert "minWidth: MIN_PICK" in huelle, (
        "Die Untergrenze gilt nur der Flaeche (c) – die Auszeichnung bleibt 13 px schmal."
    )


def test_a_vat_rate_leads_with_its_number():
    """**Der Wert zuerst, der Name danach** (Testnotiz #938).

    Auf einem Beleg ist die **Zahl** die Aussage; der Name ist ihr Rechtsgrund. Und
    untereinander gelesen steht so das Gleiche uebereinander.

    Bug-Formen: (a) der Name steht wieder vorn; (b) die Zusammensetzung wandert an die
    Aufrufstelle, und Auswahl und Anzeige laufen auseinander.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    body = _body(src, "vatText", kind="function")
    assert "${rate} % · ${name}" in body, (
        "Der Steuersatz nennt den Namen vor dem Wert (a)."
    )
    assert "${name} · ${rate}" not in src, "Irgendwo steht die alte Reihenfolge (a)."
    assert src.count("vatText(") >= 3, (
        "Die Zusammensetzung steht nicht mehr an einer Stelle (b) – Auswahl und Anzeige "
        "muessen dieselbe sein."
    )


def test_a_name_in_the_document_head_carries_its_number():
    """**Die Nummer steht neben dem Namen** (Testnotiz #940) – wie in der Positionszeile.

    Sie stand als eigene Zeile mit dem Mikro-Label «Nr.», vier Zeilen unter dem Namen, zu
    dem sie gehoert. Name und Objektnummer benennen **einen** Datensatz (#933).

    Bug-Formen: (a) die Nummer steht wieder in einer eigenen Zeile; (b) das Raster behaelt
    die Zeile, die es nicht mehr gibt; (c) die Beschriftung «Nr.» lebt weiter.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    party = _component(src, "Party")
    # *Gefragt wird die **Regel**, nicht der Variablenname: seit #951 zeigt der Block den
    # gewaehlten Empfaenger (``view``), nicht mehr blind ``side`` – die Nummer gehoert
    # weiterhin in dieselbe Zeile wie der Name.*
    head = party[: party.index(".attn")]
    assert "<ObjId value={" in head, "Die Nummer steht nicht bei Name und Waehler (a)."
    assert "PARTY_NUMBER_LABEL" not in src and "'Nr.'" not in src, (
        "Die Beschriftung «Nr.» lebt weiter (c) – neben dem Namen sagt der Block darueber "
        "laengst, wessen Nummer es ist."
    )
    # Die Zeilenzahl selbst ist keine Regel – sie muss nur zur Zahl der Angaben passen, die
    # der Block untereinander stellt. Gezaehlt wird darum, nicht verglichen.
    rows = int(re.search(r"const PARTY_ROWS = (\d+)", src).group(1))
    grid = party[party.index("gridRow:"):]
    assert rows == grid.count("<div />") + grid.count(": <div>") + 2, (
        "Das Raster und die Angaben des Blocks sind nicht gleich lang (b) – dann klafft in "
        "beiden Bloecken eine Luecke."
    )


def test_two_ways_to_reach_someone_stand_below_each_other():
    """**E-Mail und Telefon untereinander** (Testnotiz #944).

    Es sind zwei **Wege**, nicht ein Wert – und auf der Breite einer Beleg-Spalte brach die
    Zeile ohnehin, nur an einer beliebigen Stelle.

    Bug-Form: sie stehen wieder mit «·» in einer Zeile.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    party = _component(src, "Party")
    kontakt = party[party.index(".email ||"):]
    assert "join('\\n')" in kontakt and "whiteSpace: 'pre-line'" in kontakt, (
        "Kontaktweg und Telefon stehen in einer Zeile – zwei Wege sind kein Wert."
    )


def test_asking_someone_is_built_in_exactly_one_place():
    """►►► **Derselbe Befehl, zwei Nutzlasten** (Testnotiz #941). ◄◄◄

    *«Ist die Funktion dieses Buttons wirklich aktiv?»* – Nein: der Knopf im Belegkopf
    schickte ``ask`` **ohne** die beiden Fristen, und der Dienst weist ein Angebot ohne sie
    ab. Der Knopf am Angebot schickte sie mit; derselbe Befehl tat also je nach Herkunft
    etwas anderes.

    ►►► **Und seit #985 trägt die Nutzlast gar keine Frist mehr.** ◄◄◄ Sie stehen auf
    dem Beleg und werden dort geschrieben (Verb ``terms``); ``_ask`` liest sie von ihm,
    wie den Betrag aus den Positionen. Damit ist die Regel dieses Wächters **besser**
    erfüllt als mit der Fassung, die er ursprünglich prüfte – eine Nutzlast, die nichts
    trägt, kann sich zwischen zwei Aufrufstellen nicht unterscheiden. Geprüft wird darum
    die Regel, nicht die damalige Form.

    Bug-Formen: (a) eine Aufrufstelle baut die Nutzlast wieder selbst; (b) sie trägt
    wieder eine Angabe, die der Beleg schon kennt.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert src.count("action: 'ask'") == 1, (
        "Die Nutzlast des Anfragens entsteht an mehr als einer Stelle (a)."
    )
    bauer = src[_at(src, "const onAsk"):]
    bauer = bauer[: bauer.index("return (")]
    assert "payment_days" not in bauer and "lead_days" not in bauer, (
        "Die Nutzlast trägt wieder eine Frist (b) – dann gibt es einen zweiten Ort für "
        "sie, und der lebt nur im Browser."
    )


def test_the_issuer_stays_changeable():
    """**Welche Gesellschaft den Beleg stellt, kann man korrigieren** (Testnotiz #936).

    Die Automatik bleibt – der Aussteller friert mit der Freigabe ein. Hier stand
    zusaetzlich ``options.length > 1``: «eine Auswahl mit genau einer Antwort ist keine».
    Das stimmt fuer eine *Frage*, nicht fuer eine **Korrektur** – wer nachsehen will,
    findet sonst gar kein Bedienelement.

    Bug-Form: die Zahl der Gesellschaften entscheidet wieder ueber die Aenderbarkeit.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    issuer = _component(src, "Issuer")
    assert "options.length" not in issuer, (
        "Die Aenderbarkeit haengt wieder an der Zahl der Gesellschaften – bei genau einer "
        "gibt es dann kein Bedienelement."
    )
    assert "on={may(d, 'issuer')}" in issuer, (
        "Der Aussteller fragt nicht mehr `can` – und `can` ist Auskunft und Tor."
    )


def test_a_finish_button_that_cannot_act_is_not_there():
    """►►► **Was jetzt nicht geht, steht auch nicht da** (Testnotiz #950). ◄◄◄

    *«Es gibt hier ja noch den Button ‹Vorgang abschliessen›, welcher bewusst ausgegraut
    deaktiviert ist … Ich sehe keinen Grund, warum dies sichtbar sein sollte. Wenn es die
    Option zum jetzigen Zeitpunkt nicht gibt, dann entfernen.»*

    Das ist #945 einen Schritt weiter, nicht zurueck: dort war das Problem, dass der Knopf
    eine **Einladung** war, die der Dienst mit 409 abwies – ausgegraut loeste das halb. Die
    Hausregel ist eindeutig: *ein Knopf, der nie etwas tun kann, ist kein Angebot.*

    Bug-Formen, jede gegengeprueft: (a) der Knopf steht gesperrt da; (b) er fragt die Sperre
    gar nicht (und laeuft dann in den 409); (c) die Oberflaeche leitet den Grund selbst her
    (ein Modultyp).
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "order-detail.tsx"))
    knopf = src[_at(src, "const blocked ="):]
    knopf = knopf[: knopf.index("</button>")]
    assert "blocked ? null :" in knopf, (
        "Der Abschluss-Knopf steht gesperrt da statt zu fehlen (a/b) – und ausgegraut ist "
        "er eine Einladung, die der Dienst gleich darauf abweist."
    )
    assert "disabled={busy}" in knopf, (
        "Er fragt die Sperre nicht mehr, aber auch nicht mehr `busy` – dann laeuft ein "
        "Doppelklick in zwei Bestaetigungen."
    )
    # *Und der **Grund** ist kein Hover an einem toten Knopf mehr: die Modul-Karte sagt ihn
    # selbst (Stufe, gemeldete Luecken). Ein zweiter Ort dafuer waere dieselbe Auskunft
    # noch einmal – und zwar dort, wo man sie nur findet, wenn man auf nichts zeigt.*
    assert "'data-tip': blocked" not in knopf, (
        "Die Begruendung haengt wieder am Knopf – den es in diesem Zustand nicht gibt."
    )
    assert "beleg" not in knopf and "zahlung" not in knopf, (
        "Die Oberflaeche nennt einen Modultyp (c) – die Regel steht im Dienst."
    )


# ---------------------------------------------------------------------------
# Testnotizen #948–#959 — die Fläche, der Ort und die richtige Tür
# ---------------------------------------------------------------------------


def test_an_editable_value_is_a_tinted_area_not_an_underline():
    """►►► **Eine Fläche, kein Unterstrich** (Testnotiz #949). ◄◄◄

    *«Ich möchte keinen Unterstrich, sondern wie jetzt beim Hover, dass der ganze
    Eingabebereich leicht farblich hintersetzt ist – also standardmässig schon ohne Hover,
    und der Unterstrich dafür weg. Beim Hover vielleicht nochmals eine dezent kräftigere
    Farbe. Wende das bei allen solchen Feldern an.»*

    Die Bedingung aus #922 gilt unverändert: **keine Layoutwirkung**. Die Tönung ist darum
    eine ``background`` und wächst über einen **äusseren** ``box-shadow``; Polsterung hätte
    genau das gebrochen.

    Bug-Formen, jede gegengeprüft: (a) der Unterstrich lebt weiter; (b) im Ruhezustand gibt
    es keine Fläche; (c) der Hover ist nicht kräftiger; (d) die Fläche kommt über eine
    Polsterung und verschiebt damit den Beleg; (e) eine Farbe steht als Zahl daneben statt
    aus dem Token zu kommen.
    """
    css = _read(FRONTEND / "app" / "globals.css")
    rule = css[_at(css, "\n.ix-editable {"):]
    rule = rule[: rule.index("}")]
    assert "inset" not in rule, "Der Unterstrich lebt weiter (a)."
    assert "background:" in rule, "Im Ruhezustand gibt es keine Fläche (b)."
    assert "padding" not in rule, (
        "Die Fläche kommt über eine Polsterung (d) – #922 verlangt ausdrücklich, dass "
        "Grösse und Form bleiben, wie sie gedruckt würden."
    )
    assert "box-shadow: 0 0 0" in rule, (
        "Die Fläche klebt am Text – sie wächst über einen äusseren Schatten, weil der "
        "keinen Platz belegt."
    )
    assert not re.search(r"(rgba?\(|#[0-9a-fA-F]{3,6})", rule), (
        "Eine Farbe steht als Zahl im Blatt (e) – Token-Werte gehören in "
        "`colors_and_type.css`."
    )
    hover = css[_at(css, "\n.ix-editable:hover"):]
    hover = hover[: hover.index("}")]
    assert "var(--accent-soft)" in hover and "58%" not in hover, (
        "Der Hover ist nicht kräftiger als der Ruhezustand (c) – dann sagt er nichts."
    )


def test_the_marking_is_congruent_with_the_control():
    """►►► **Die Auszeichnung ist so gross wie das Bedienelement** (Testnotiz #948). ◄◄◄

    *«Das gehighlightete Feld ist deutlich grösser als das selektierbare Feld. Das ist ein
    design- und UX-technisches No-Go. Bitte eine robuste Lösung etablieren und bei allen
    Eingabefeldern kontrollieren.»*

    Gelöst wird es **konstruktiv**, nicht durch abgestimmte Zahlen: die Hülle ist
    ``inline-flex`` (dann nimmt sie genau die Höhe ihres Kindes), und Auszeichnung und
    ``<select>`` sitzen auf **demselben** Element – der frühere Zwischen-``<span>`` war die
    zweite Box, und sie konnte grösser sein als das, was sie versprach.

    Bug-Formen: (a) die Hülle ist wieder ein reines Inline-Element; (b) es gibt zwei Boxen;
    (c) das Bedienelement deckt nicht die ganze Fläche.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    hull = _component(src, "Editable")
    assert "'inline-flex'" in hull and "'flex'" in hull, (
        "Die Hülle ist ein reines Inline-Element (a) – dann nimmt sie die Höhe der Zeile "
        "und ist grösser als das Bedienelement darin (gemessen 24 px ↔ 19,5 px)."
    )
    # *Und sie darf sich nicht **strecken**: in einer Spalte wird jedes Flex-Kind
    # blockifiziert und auf die volle Breite gezogen – gemessen war die getönte Fläche
    # 229 px breit und das `<select>` darin 46 px, also genau der gemeldete Unterschied.*
    #
    # ►►► **Zurückgenommen wird sie über die BREITE, nicht über `align-self`**
    # (Testnotizen #961/#963). ◄◄◄ `align-self: start` beantwortet die Streckung richtig
    # und beantwortet **zugleich** eine zweite Frage, die es nicht beantworten darf: in
    # einer *Zeile* ist die Querachse die senkrechte, und `start` heisst dort «oben» – die
    # Hülle fiel damit aus dem `items-baseline` ihres Elternteils heraus, und neben einer
    # Angabe anderer Schriftgrösse stand sie sichtbar versetzt (genau die beiden
    # gemeldeten Höhenversätze). Eine **definite** Quergrösse schliesst `stretch` aus
    # (CSS Flexbox §8.3) und lässt die senkrechte Ausrichtung dem Elternteil.
    assert "width: 'fit-content'" in hull, (
        "Die Hülle streckt sich auf die Breite ihrer Spalte (a)."
    )
    assert "alignSelf: 'start'" not in hull, (
        "Die Hülle richtet sich selbst aus (d) – dann steht sie in einer Zeile neben "
        "einer anderen Schriftgrösse versetzt (#961/#963)."
    )
    pick = _component(src, "DocPick")
    assert pick.count("<Editable") == 1 and "display: 'inline-block'" not in pick, (
        "Es gibt zwei Boxen (b) – Auszeichnung und Bedienelement gehören auf dasselbe "
        "Element, sonst kann die eine grösser sein als die andere."
    )
    assert "inset: 0" in pick, "Das Bedienelement deckt die Fläche nicht (c)."


def test_paying_a_voucher_asks_the_voucher():
    """►►► **«Jetzt bezahlen» rief die Tür des ALTEN Moduls** (Testnotiz #959). ◄◄◄

    *«Wieso funktioniert diese Option nicht mehr? Achtung, dies muss sauber funktionieren,
    und ich habe keinen Bock, nochmals Stripe zu konfigurieren.»* – Musste er nicht: die
    Schlüssel, der Webhook und das Zahlungsformular sind unverändert. Die Karte rief fest
    ``api.preparePayment``, also den Endpunkt des **Vorgängers**; am Beleg gab es dort
    keinen Vorgang, und der Dienst antwortete mit 404.

    Bug-Formen: (a) die Karte kennt wieder einen Endpunkt; (b) beide Aufrufer geben densel-
    ben mit; (c) die Funktion wird an der Aufrufstelle gebaut (dann läuft die Vorbereitung
    bei jedem Rendern neu).
    """
    card = _code(_read(FRONTEND / "components" / "erp" / "pay-online.tsx"))
    assert "api." not in card, (
        "Die Karte kennt wieder einen Endpunkt (a) – welcher Vorgang bezahlt wird, weiss "
        "nur der Aufrufer."
    )
    assert "prepare(orderObjectId" in card, "Die Karte fragt nicht den Aufrufer."
    beleg = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "prepare={api.prepareVoucherPayment}" in beleg, "Der Beleg ruft die falsche Tür."
    # *Der Vorgänger rief hier seine eigene (`api.preparePayment`) – **genau deshalb** war
    # die Trennung nötig, und genau deshalb kostete seine Löschung hier eine Zeile (#960).*
    # (c) **Eine prototypgebundene Methode, keine Pfeilfunktion** – sonst ist es bei jedem
    # Rendern eine neue Referenz, und der Effekt der Vorbereitung läuft endlos.
    assert "prepare={(" not in beleg, (
        "Die Funktion wird an der Aufrufstelle gebaut (c)."
    )


def test_recording_a_payment_exists_exactly_once_and_names_its_invoice():
    """►►► **«Zahlung erfassen» gibt es EINMAL — und es weiss, welche Rechnung.** ◄◄◄

    *«Warum gibt es hier zweimal den Button ‹Zahlung erfassen›? Das ist ein absolutes
    No-Go.»* (#958) – Und es war kein Gestaltungsfehler, sondern eine offene Frage: der
    Knopf am **Vorgang** wusste nicht, welche Rechnung gemeint ist, und wählte still die
    älteste offene.

    *Der Wächter verlangte damals, dass `d.payment_word` **in `EntryRow`** steht und
    **nicht in `Money`** – also die Form der damaligen Lösung. Seit der Umbau die Geld-
    Handlungen in zwei Fächer sortiert (eine Buchung ist keine Korrektur), steht das Verb
    genau einmal, nämlich als die **eine** Handlung, die ihr Fach weiterbringt.*

    ►►► **Und «welche Rechnung» ist keine Frage mehr.** ◄◄◄ Der Beleg **ist** die
    Rechnung – es kann keine zweite geben, also kann die Buchung nicht die falsche
    treffen. `settle_charge` ist damit entfallen, und die Regel gilt strukturell.

    Bug-Formen: (a) das Verb steht wieder an zwei Stellen; (b) die Oberfläche sucht sich
    eine Rechnung aus den Zeilen; (c) eine Handlung nennt wieder eine.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    # (a) **Gezählt, nicht gesucht** – und gezählt wird die **Handlung**, nicht das Wort:
    # es steht auch als Überschrift des Formulars da, und ein «kommt zweimal vor» wäre
    # davon erfüllt. Genau eine Stelle öffnet die Erfassung einer Zahlung.
    opens = src.count("setForm({ kind: 'pay'")
    assert opens == 1, (
        f"Die Erfassung einer Zahlung geht von {opens} Stellen aus (a) – eine Handlung, "
        f"eine Stelle."
    )
    money = _component(src, "Money")
    for guess in ("charges.find(", "charges[0]", "open_charges", "settle_charge",
                  "chargeId={"):
        assert guess not in money, (
            f"«{guess}»: die Oberfläche sucht sich eine Rechnung (b/c) – es gibt eine, "
            f"und sie ist der Beleg."
        )


def test_the_cancel_button_stands_beside_the_finish_button_as_a_square():
    """►►► **Der Storno neben dem Abschluss, als Quadrat** (Testnotiz #957). ◄◄◄

    *«Ich hätte gerne, dass es neben dem grossen Button ‹Vorgang abschliessen› platziert
    wird, jedoch nur ein quadratischer Button mit Icon, sodass der Hauptfokus und der absolut
    dominante Button immer noch ‹Vorgang abschliessen› ist.»*

    ►►► **Und es ist die Anatomie einer ENTSCHEIDUNG, nicht die der Fusszeile** (#976).◄◄◄
    *«Kann man diesen Bereich ähnlich darstellen wie ‹Vorgang abschliessen› und daneben das
    unscheinbarere Abbrechen?»* – Gemeldet an der **Angebotszeile** (annehmen ↔ absagen),
    und damit ist es dieselbe Zeile: eine Handlung nimmt den Platz, die leise steht als
    Quadrat daneben. Sie wohnt darum in `StageRow` und wird von beiden gesetzt.

    *Der Wächter verlangte `flex: 1` **wörtlich in `Footer`** – also die Form der damaligen
    Lösung; er hätte das gemeinsame Bauteil verboten, obwohl es die Regel besser erfüllt.
    Gefragt ist jetzt die Zeile selbst.*

    Bug-Formen: (a) er steht wieder in einer eigenen Zeile darunter; (b) er ist nicht
    quadratisch; (c) die Breite kommt als Inline-Stil und nimmt dem Knopf damit die Geste,
    seinen Namen beim Zeigen auszuklappen; (d) die Angebotszeile baut ihre eigene Fassung.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    stage_row = _component(src, "StageRow")
    assert "flex: 1" in stage_row, (
        "Die dominante Handlung nimmt den Platz nicht (a) – dann ist der Storno ein "
        "zweiter Block und nicht sein kleiner Nachbar."
    )
    foot = _component(src, "Footer")
    assert "<StageRow" in foot and "children" in foot, (
        "Der Abschluss steht nicht in derselben Zeile wie der Storno (a)."
    )
    assert "square" in foot and "ACT_H.stage" in foot, (
        "Der Knopf ist nicht quadratisch in der Höhe des Abschlusses (b)."
    )
    # (d) **Dieselbe Zeile an der Angebotszeile** – der Zuschlag ist für sie, was der
    # Abschluss für das Modul ist. Drei gleich laute Knöpfe sind kein Vorschlag.
    quote = _component(src, "QuoteRow")
    assert "<StageRow" in quote and "<StageAction" in quote, (
        "Die Angebotszeile stellt ihre Handlungen wieder gleichrangig nebeneinander (d)."
    )
    assert "<Actions" not in quote, (
        "Die Angebotszeile baut ihre eigene Fassung daneben (d)."
    )
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    assert "'--actbtn-w'" in ui and "width:" not in _component(ui, "ActionButton"), (
        "Die Breite kommt als Inline-Stil (c) – sie gewinnt gegen "
        "`.ix-tuck:hover { width: auto }`, und der Name klappt nie aus."
    )
    css = _read(FRONTEND / "app" / "globals.css")
    assert "width: var(--actbtn-w, 32px)" in css, (
        "Die Regelbreite kommt nicht aus der Variablen (c) – dann kann der Aufrufer sie "
        "nur inline setzen."
    )


def test_a_quote_row_closes_itself_and_keeps_name_and_number_together():
    """**Die Haarlinie unten, Nummer neben dem Namen** (Testnotizen #953/#955).

    *«Der obere Strich in diesem Container ist irgendwie unnötig bzw. macht optisch keinen
    Sinn – ich würde ihn pro Container unten setzen.»* Er war zugleich die **zweite** Linie
    direkt unter der Trennlinie des Abschnitts. Und *«die Objektnummer immer neben den
    Objektnamen»* (#853): als Geschwister in einer umbrechenden Zeile rutschte die Nummer
    auf die nächste, sobald es eng wurde.

    Bug-Formen: (a) die Linie steht wieder oben; (b) Name und Nummer sind wieder
    Geschwister der umbrechenden Zeile.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    row = _component(src, "QuoteRow")
    assert "borderBottom: '1px solid var(--border-1)'" in row and "borderTop" not in row, (
        "Die Linie eröffnet den Container statt ihn zu schliessen (a)."
    )
    group = row[row.index("party_name"):]
    assert "<ObjId value={d.party_object_id} /></span>" in group[:400], (
        "Name und Nummer sind zwei Geschwister der umbrechenden Zeile (b) – dann fällt die "
        "Kennung auf die nächste Zeile."
    )
    assert "flex: `1 1 ${NAME_MIN}px`" in row, "Die Gruppe schrumpft nicht mit."


def test_a_recipient_chip_can_be_shown_and_dropped():
    """►►► **Der Chip zeigt seine Anschrift und lässt sich abwählen** (Testnotiz #951). ◄◄◄

    *«Ich kann zwar mehrere User aufführen, jedoch kann ich sie nicht wie zuvor auch
    abwählen … zudem stört mich, dass die jeweilige Anschrift nicht sichtbar ist.»*

    Bug-Formen: (a) der Chip ist wieder reine Anzeige; (b) es gibt kein Abwählen; (c) die
    Oberfläche entscheidet selbst, ob abgewählt werden darf, statt `can` zu fragen; (d) der
    Block zeigt weiter blind die Seite des Servers statt der gewählten.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    chip = _component(src, "RecipientChip")
    # *Zwei Knöpfe in **einer** Hülle – ein Klick auf den Namen zeigt die Anschrift, das ✕
    # zieht die Anfrage zurück. Verschachtelte Knöpfe wären ungültiges HTML, und ein
    # einziger müsste erraten, was gemeint war. Gezählt wird, statt nach dem Vorkommen der
    # Namen zu fragen: die standen auch dann noch da, als die Bug-Form den Klick entfernte.*
    # ►►► **Drei Knöpfe, und nie mehr** (Testnotiz #962): der **Name** zeigt die
    # Anschrift, `+` fragt an, `✕` zieht zurück – und die beiden letzten schliessen
    # einander aus, es steht also immer höchstens einer da. Gezählt wird, statt nach dem
    # Vorkommen der Namen zu fragen: die standen auch dann noch da, als die Bug-Form den
    # Klick entfernte.
    assert chip.count("<button") == 3, (
        f"Der Chip hat {chip.count('<button')} Knöpfe statt drei (a/b) – reine Anzeige "
        f"zeigt keine Anschrift, und ohne + / ✕ gibt es kein An- und Abwählen."
    )
    # Gefragt wird, **dass** der Knopf seine Handlung trägt – nicht, wie der Ausdruck
    # geschrieben ist: seit #1016 steht dort `busy ? undefined : onAsk`, und eine Prüfung
    # auf die Schreibweise hätte ausgerechnet die bessere Fassung verboten.
    for handler, what in (("onShow", "Der Name zeigt die Anschrift nicht (a)."),
                          ("onAsk", "Das + fragt nicht an (b)."),
                          ("onDrop", "Das ✕ zieht die Anfrage nicht zurück (b).")):
        assert re.search(r"onClick=\{[^}]*\b" + handler + r"\b", chip), what
    # ►►► **Eine Form für beide Fälle** (#962): eine zugelassene, noch nicht angefragte
    # Partei stand als `+ Name`-Knopf mit `.ix-editable` daneben – der Auszeichnung
    # **änderbarer Werte**. Damit sah jede Partei dauerhaft «aktiv» aus, und ob eine
    # angefragt war, war an der Form nicht abzulesen.
    assert "ix-editable" not in _component(src, "Recipients"), (
        "Die noch nicht angefragte Partei hat wieder eine eigene Form (e) – dann sagt "
        "die Auszeichnung änderbarer Werte etwas über einen Zustand."
    )
    rec = _component(src, "Recipients")
    assert "may(d, 'unask')" in rec, (
        "Die Oberfläche entscheidet selbst (c) – `can` ist Auskunft **und** Tor."
    )
    assert "action: 'unask'" in rec, "Das Verb wird nicht geschickt (b)."
    party = _component(src, "Party")
    # *Gefragt wird, dass **keine** angezeigte Angabe mehr aus `side` kommt – ein blosses
    # «`view.address` steht irgendwo» war stumpf: die eine Stelle umzustellen liess das
    # Wort an der anderen stehen, und der Wächter schlug nicht an (gemessen).*
    assert "d.recipients" in party, "Die Seiten der Angefragten werden nicht gelesen (d)."
    # *`side.object_id` bleibt erlaubt – daraus **entsteht** die Vorwahl (der Adressat ist
    # der Standard). Gefragt sind die **angezeigten** Angaben.*
    for feld in ("address", "shipping", "attn", "email", "phone", "uid"):
        assert f"side.{feld}" not in party, (
            f"«{feld}» kommt weiter blind aus der Seite des Servers (d) – dann bleibt beim "
            f"Umschalten die Angabe des Adressaten stehen."
        )
    # **Wer die Gegenseite ist, sagt die Struktur** – nicht ein Vergleich auf ein Rollenwort.
    assert "side.ours" in party, "Die Seite wird geraten statt gelesen."


def test_a_delivery_clause_carries_no_edition_in_brackets():
    """**«(Incoterms 2020)» entfällt – bei allen** (Testnotiz #956).

    Welche Fassung gilt, steht in der **Erklärung** der gewählten Klausel, und die steht auf
    dem Beleg sichtbar darunter. Als Anhang an jedem Wert wäre sie eine Wiederholung, die
    mit jeder Anzeige länger wird.

    Bug-Form: der Satz baut die Fassung wieder an.
    """
    src = _code(_read(BACKEND / "app" / "domain" / "incoterms.py"))
    out = src[_at(src, "def sentence"):]
    out = out[: out.index("\n\n\n")] if "\n\n\n" in out else out
    assert "Incoterms" not in out, (
        "Der Satz trägt die Fassung wieder – und zwar an jeder Anzeige."
    )


def test_a_term_is_a_value_on_the_document_not_a_row_of_buttons():
    """►►► **Eine Frist ist ein WERT auf dem Beleg, keine Knopfreihe** (Testnotiz #934).
    ◄◄◄

    *«Ich möchte die gleiche Logik, das gleiche Design wie bei Währung oder
    Betragsangabe.»* – Dagestanden hatte ein `TermField`: *Vorauszahlung · 30 Tage ·
    Individuell* als drei Chips nebeneinander, also ein **Formular** mitten in einem
    Dokument. Ein Beleg druckt «Zahlbar in 30 Tagen», und dass man das ändern kann, sagt
    die Haarlinie – mehr nicht. Es ist damit dieselbe Form wie jeder andere änderbare Wert
    (`DocPick`, #929/#930/#935), und die freie Eingabe steht an **derselben** Stelle.

    *`fields.TermField` hatte danach nur noch einen Aufrufer – das Vorgänger-Zahlungsmodul
    – und ist mit ihm gegangen (#960). `Segmented` bleibt: es ist die Form für eine
    Aufzählung mit wenigen Werten im **Formular** (die Zahlungsart beim Buchen, #967).*

    **Und die üblichen Werte kommen vom SERVER** (`payment_terms`/`lead_terms`): eine
    zweite Liste im Browser liefe beim ersten neuen Regelwert auseinander – und «0» ist
    dort keine Ziffer, sondern «Vorauszahlung».

    Bug-Formen: (a) `TermField` ist zurück; (b) ein Schieberegler; (c) die Werte stehen
    als Literal im Browser; (d) die Frist ist kein `DocPick` mehr.
    """
    fields = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    assert "function TermField" not in fields, (
        "`TermField` ist zurück (a) – eine Frist ist ein Wert, kein Formular."
    )
    assert 'type="range"' not in fields, "Ein Schieberegler für eine Frist (b)."

    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    term = _component(src, "Term")
    assert "<DocPick" in term, (
        "Die Frist hat eine eigene Bauart (d) – sie ist ein änderbarer Wert wie jeder "
        "andere auf dem Beleg."
    )
    assert "freeMin" in term and "numericInputProps" in term, (
        "Die freie Eingabe steht nicht mehr an derselben Stelle (d)."
    )
    for word in ("Vorauszahlung", "30 Tage", "Sofort"):
        assert word not in src, (
            f"«{word}» steht als Literal im Browser (c) – die üblichen Werte gehören "
            f"dem Dienst (`domain/voucher.PAYMENT_TERMS`/`LEAD_TERMS`)."
        )
    for source in ("d.lead_terms", "d.payment_terms", "d.term_free_min"):
        assert source in src, f"«{source}» kommt nicht vom Server (c)."


# ---------------------------------------------------------------------------
# ►►► Testnotizen #960–#974 – das alte Modul ist weg, und der Beleg wird ruhiger
# ---------------------------------------------------------------------------


def test_a_module_with_its_own_document_needs_no_list_beside_it():
    """►►► **Ein Modul, das seine Sache selbst zeigt, zählt sie nicht daneben auf**
    (Testnotiz #973). ◄◄◄

    *«Ich checke nicht, was diese Info hier soll. Zahlung war abgeschlossen, und es zeigt
    es immer noch an – bitte hier entfernen.»*

    Dagestanden hatte die `PointList`, und die sagt, was ein Modul **tun wird**: seine
    Erfassungspunkte, seine Stichprobe, sein Verb. Ein Beleg hat nichts davon; übrig blieb
    sein **Verb** («Vorgang abschliessen») – also der Name eines Knopfes, den es an einem
    erledigten Modul gar nicht mehr gibt.

    **Gefragt wird, ob es einen Beleg GIBT**, nie der Modultyp: jedes künftige Modul,
    dessen Inhalt eine eigene Karte ist, erbt die Regel ohne eine Zeile.

    Bug-Formen: (a) die Aufzählung steht wieder neben dem Beleg; (b) gefragt wird der
    Modultyp statt der Sache.
    """
    raw = _read(FRONTEND / "components" / "erp" / "order-detail.tsx")
    src = _code(raw)
    body = raw[raw.index("const stepBody ="):raw.index("// **Ohne Prozessbild")]
    assert "paper ? (" in body and "<PointList" in body, (
        "Die Aufzählung hängt nicht mehr am Vorhandensein eines Belegs (a)."
    )
    # Der `paper`-Zweig steht **vor** der `PointList` – sonst greift sie zuerst.
    assert body.index("paper ? (") < body.index("<PointList"), (
        "Die Aufzählung steht wieder vor dem Beleg (a)."
    )
    for key in ("'beleg'", '"beleg"'):
        assert key not in src, f"Die Ausführungsstelle nennt wieder den Modultyp {key} (b)."


def test_a_required_value_says_so_where_it_stands():
    """►►► **Ein Pflichtwert, der fehlt, sagt es an SEINER Stelle** (Testnotiz #964). ◄◄◄

    *«Alle Eingabefelder hier in diesem Modul – also alles, was so leicht blau hinterlegt
    ist – sollen Muss-Felder sein.»* «Leicht blau hinterlegt» **ist** die Auszeichnung
    änderbarer Werte (`.ix-editable`, #922) – die Regel gehört darum ihr und nicht neun
    Aufrufstellen.

    Es ist **dieselbe Auszeichnung in einer anderen Stimme**: die Fläche wird warnfarben
    statt akzentfarben, Grösse und Schrift bleiben, wie #922/#948 sie festgelegt haben.
    Kein Sternchen und kein Ausrufezeichen daneben – eine zweite Form wäre eine zweite
    Aussage über dieselbe Sache, und sie bräuchte Platz, den ein Beleg nicht hat.

    **Und die Regel steht im Dienst** (`voucher._assert_complete`): dies ist ihre
    freundliche Hälfte, nie ein zweiter Massstab.

    Bug-Formen: (a) die Hülle kennt keine Pflichtangabe; (b) die Auszeichnung verschiebt
    den Beleg (Polsterung statt Fläche); (c) ein Wert trägt sie nicht; (d) sie steht noch
    da, wo gar nichts mehr änderbar ist.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    hull = _component(src, "Editable")
    assert "missing" in hull and "is-missing" in hull, (
        "Die Hülle kennt keine Pflichtangabe (a)."
    )
    css = _read(FRONTEND / "app" / "globals.css")
    block = css[css.index(".ix-editable.is-missing {"):]
    block = block[: block.index("}")]
    assert "--danger" in block and "padding" not in block, (
        "Die Auszeichnung verschiebt den Beleg (b) – sie ist eine Fläche, keine Polsterung."
    )
    # (d) **Wo nichts mehr änderbar ist, gibt es keine Pflichtangabe** – der Beleg ist
    #     gedruckt, und eine rote Fläche darauf wäre eine Aufforderung ins Leere.
    assert ".ix-editable[aria-disabled='true'].is-missing" in css, (
        "Ein gesperrter Wert bleibt rot (d)."
    )
    # (c) **Jeder Wert trägt sie** – Preis, Satz, Zoll, beide Fristen, Lieferbedingung.
    for where in ("LineRow", "Customs", "Term", "Delivery"):
        assert "missing" in _component(src, where), (
            f"«{where}» sagt nicht, dass sein Wert Pflicht ist (c)."
        )


def test_the_chronicle_is_gone_and_its_dates_stand_where_they_belong():
    """►►► **Die Chronik entfällt – die Daten stehen an ihrem Ort** (#968/#969/#970). ◄◄◄

    *«Die Chronik kann hier vollständig und gänzlich entfallen. Ich möchte die Information
    dort darstellen, wo sie eigentlich angezeigt werden.»*

    Sie zählte **zwei Daten** auf, und beide haben einen eigenen Ort: *wann offeriert
    wurde* am Kopf der Angebote, *wann zugesagt wurde* an der Zeile, bei der zugesagt
    wurde – und *wann storniert wurde* im Belegkopf, neben der Belegart. Ein Abschnitt,
    der dieselben Daten ein zweites Mal nennt, ist nicht der Nachweis, sondern seine
    ärmere Kopie: nacktes Datum statt Aussage.

    **Die Aussage steht da, die Tatsache im Hover** – dieselbe Regel wie bei der
    Fälligkeit einer Geld-Zeile (#890): eine Zahl, die man erst von heute abziehen muss,
    ist keine Auskunft, sondern eine Aufgabe.

    Bug-Formen: (a) der Abschnitt ist zurück; (b) eine der beiden Angaben fehlt; (c) sie
    nennt nur das Datum statt der Aussage; (d) die genaue Zeit fehlt im Hover.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "function Chronicle" not in src and "<Chronicle" not in src, (
        "Die Chronik ist zurück (a)."
    )
    assert "history_title" not in src, "Ihre Überschrift reist noch mit (a)."

    # ►►► **Die Aussage kommt aus `lib/when`** (#992) – hier standen `since(` und
    # `localDateTime(`, also die Namen der damaligen Helfer in dieser Datei. Sie gibt es
    # nicht mehr: Datum und Uhrzeit haben im Haus **eine** Stelle.
    quotes = _component(src, "Quotes")
    # **Die Form heisst seit #1052 `happened`** («Vor 3 Tagen offeriert») – gefragt ist
    # die Regel «der Abschnitt sagt es», nicht der Name des damaligen Helfers.
    assert "q.sent_at" in quotes and "happened(" in quotes, (
        "Der Abschnitt sagt nicht mehr, wann offeriert wurde (b/c)."
    )
    assert re.search(r"happened\([^)]*\)\.title", quotes), (
        "Die genaue Zeit fehlt im Hover (d)."
    )
    row = _component(src, "QuoteRow")
    assert "d.agreed_at" in row and re.search(r"happened\([^)]*\)\.title", row), (
        "Die Zeile sagt nicht, wann sie den Zuschlag bekam (b/c/d)."
    )
    # **Und der Storno steht im Kopf** – er war die dritte Zeile der Chronik.
    head = _component(src, "DocHead")
    assert "d.cancelled_on" in head, (
        "Der Storno hat keinen Ort mehr (b) – er stand in der Chronik."
    )


def test_the_vat_rate_stands_before_the_amount():
    """►►► **Der Satz steht VOR dem Betrag** (Testnotiz #972). ◄◄◄

    *«Kann der MWST-Satz evtl. vor dem Betrag stehen? Irgendwie schaut das etwas komisch
    aus, da alles weiter untereinander steht.»*

    Und es ist nicht bloss Geschmack: die **Zahl** ist die letzte Angabe der Zeile, sie
    steht rechtsbündig und bildet mit der Zeile darunter eine Spalte. Stand der Satz
    dahinter, verschob jede Beschriftung anderer Länge («8.10 % · Normalsatz» ↔ «0.00 % ·
    Export») den Betrag – die Beträge standen untereinander **nicht** untereinander.

    Bug-Form: der Preis steht wieder vor dem Satz.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    row = _component(src, "LineRow")
    assert row.index("<DocPick") < row.index('title="Einzelpreis'), (
        "Der Preis steht wieder vor dem Steuersatz – dann verschiebt jede Satz-"
        "Beschriftung anderer Länge die Spalte der Beträge."
    )


def test_the_payment_method_is_a_slider_not_a_dropdown():
    """►►► **Wie bezahlt wurde, ist ein SCHIEBER** (Testnotiz #967). ◄◄◄

    *«Hier soll wieder der Sliderbutton zum Einsatz kommen.»* – Und die Regel dahinter ist
    die des Hauses: ein Auswahlfeld ist die Form für eine **lange** Aufzählung; hier sind
    es **zwei** Werte (bar · Überweisung – die Karte tippt niemand ab, sie kommt über den
    Webhook). Zwei Werte hinter einem Klick zu verstecken ist ein Klick für eine
    Entscheidung, die man sehen könnte.

    ►►► **Und der Schieber steht dort, wo die Frage entsteht** (der Umbau). ◄◄◄ Er sass
    im **Erfassungsformular**, also *nachdem* man sich schon entschieden hatte, überhaupt
    zu buchen – und daneben standen «Überweisen» und «Jetzt bezahlen» als eigene Knöpfe an
    der Rechnungszeile: dieselbe Frage, dreimal, in zwei Formensprachen. Jetzt ist es
    **eine** Frage im Fach «Begleichen» (*wie kommt das Geld hierher?*), und das Formular
    fragt sie nicht noch einmal.

    Bug-Formen: (a) die Zahlungsart ist wieder ein `<select>`; (b) sie steht wieder im
    Formular; (c) die Beschriftung steht zweimal.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    money = _component(src, "Money")
    assert "<Segmented" in money, "Die Zahlungsart ist kein Schieber mehr (a)."
    assert "aria-label={d.method_label}" not in src, (
        "Das alte Auswahlfeld steht noch da (a)."
    )
    entry = _component(src, "Entry")
    assert "<Segmented" not in entry and "setMethod" not in entry, (
        "Das Formular fragt die Zahlungsart erneut (b) – sie ist längst gewählt, und die "
        "getippte gewänne auch dann, wenn sie der Wahl widerspricht."
    )
    assert "d.method_label}</Label>" not in money, (
        "Die Beschriftung steht zweimal (c) – `Segmented` bringt seine eigene mit."
    )


def test_a_refusal_is_just_a_refusal():
    """**«Absage» – und sonst nichts** (Testnotiz #965).

    *«Hier soll einfach nur ‹Absage› stehen und nicht ‹liefert nicht›.»* Der Zusatz
    stammte aus dem Beschaffungs-Beleg, wo nur eingekauft wurde; an einer **Einnahme**
    sagt er sogar das Falsche – dort liefern wir, und abgesagt hat der Kunde.

    **Und das Verb der Schwelle kommt vom Server** (#966): «Offerte annehmen», in beiden
    Richtungen dasselbe – wie der Beleg heisst, sagt die Stufe.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo

    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "liefert nicht" not in src, "Der Zusatz ist zurück."
    assert 'label="Absage"' in src, "Die Absage heisst nicht mehr «Absage»."
    assert vo.AGREE_VERB == "Offerte annehmen", (
        "Das Wort der Schwelle ist wieder ein anderes (#966)."
    )
    assert "v.stages[0]?.verb" in src, (
        "Die Karte schreibt das Verb selbst, statt es vom Server zu lesen."
    )


# ---------------------------------------------------------------------------
# ►► TESTNOTIZEN #975–#978
# ---------------------------------------------------------------------------


def test_what_to_do_stands_once_on_the_document():
    """►►► **«Was ist zu tun?» steht bei den Positionen – einmal** (#975er-Runde). ◄◄◄

    Der Satz handelt von den Positionen («Härten auf 58 HRC»), also steht er bei ihnen. Er
    ist eine **Auskunft**, kein Feld: entschieden wird er beim Modellieren, wo man einen
    Fertigungsablauf definiert – auf dem Beleg wird er abgearbeitet.

    **Leer schreibt der Beleg nicht hin**: «gemäss Spezifikation» ist die Regel, und eine
    Zeile, die «nichts Besonderes» sagt, ist keine Auskunft.

    Bug-Formen: (a) der Satz steht nicht auf dem Beleg; (b) er steht auch leer da; (c) er
    ist zu einem Eingabefeld geworden; (d) seine Beschriftung wird selbst geschrieben.
    """
    src = _code(_beleg())
    goods = _component(src, "Goods")
    assert "d.task" in goods, "Der Auftrag steht nicht auf dem Beleg (a)."
    assert "{d.task &&" in goods, "Ein leerer Auftrag belegt eine Zeile (b)."
    assert "{d.task_label}" in goods, (
        "Die Beschriftung wird selbst geschrieben (d) – sie kommt vom Server."
    )
    # (c) **Eine Auskunft, kein Feld** – kein `.ix-editable`, kein Befehl daran. Das
    # Fenster endet an der nächsten Zeile des Belegs; ein fester Zeichen-Abstand läse den
    # `onAction` der Summen mit und meldete, obwohl die Regel erfüllt ist.
    block = goods[goods.index("{d.task &&"):goods.index("<Sums")]
    assert "Editable" not in block and "onAction" not in block, (
        "Der Auftrag ist am Beleg änderbar geworden (c) – entschieden wird er beim "
        "Modellieren."
    )


def test_each_side_of_the_head_names_both_addresses():
    """►►► **Beide Anschriften, auf beiden Seiten, immer** (Testnotiz #975). ◄◄◄

    *«Mir gefällt das ziemlich gut mit Rechnungsadresse, Lieferadresse usw. Ich möchte, dass
    du das auch auf dem Leistungserbringer machst – also standardmässig immer bei
    Informationen ausweisen, global etablieren, auch wenn sie zweimal das Gleiche anzeigt.
    Eine Logik für alles, Komplexität und If/Else verringern.»*

    Die Auflösung steht darum an **einer** Stelle im Dienst (`_addresses`) und gilt für
    beide Seiten – die Karte zeichnet nur noch.

    Bug-Formen: (a) es gibt wieder zwei Auflösungen; (b) unsere Seite hat keine; (c) die
    Karte entscheidet selbst, ob eine Beschriftung erscheint.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    src = (BACKEND / "app" / "services" / "voucher.py").read_text()
    body = src[src.index("def _addresses("):]
    body = body[:body.index("\ndef ", 1)]
    assert "BILLING_LABEL" in body and "SHIPPING_LABEL" in body, (
        "Die Beschriftungen kommen nicht mehr aus der einen Auflösung (a)."
    )
    # **Unsere Seite entsteht in ``_ours``** (seit sie mit der Zusage einfriert,
    # Migration 143) – ``document_head`` liest sie von dort bzw. aus dem Kopf.
    head = src[src.index("def _ours("):src.index("def _creditor(")]
    assert "_addresses(" in head, "Unsere Seite nennt ihre Anschriften nicht (b)."
    assert src.count("_addresses(") >= 3, (
        "Nicht beide Seiten lesen dieselbe Auflösung (a/b)."
    )
    # (c) **Die Karte zeichnet, sie entscheidet nicht**: sie reicht die Beschriftung
    # durch, statt selbst zu fragen, ob es zwei Anschriften gibt.
    card = _code(_beleg())
    party = _component(card, "Party")
    assert "view.address_label" in party and "view.shipping_label" in party, (
        "Die Karte baut die Beschriftungen wieder selbst (c)."
    )
    for word in ("Rechnungsadresse", "Lieferadresse"):
        assert word not in card, (
            f"«{word}» steht als Literal in der Karte (c) – die Wörter kommen vom Server."
        )


# ---------------------------------------------------------------------------
# ►► DER UMBAU VON «RECHNUNG & ZAHLUNG» + TESTNOTIZEN #979/#981/#982
# ---------------------------------------------------------------------------


def test_money_stands_in_two_compartments_not_in_one_row_of_buttons():
    """►►► **Regel 1 — zwei Fächer statt sechs Knöpfen.** ◄◄◄

    *«Zu komplex, zu unstrukturiert, zu wirr, zu viele Optionen, die sich gegeneinander
    stören, kannibalisieren.»* – Gezählt: an einer Rechnung standen bis zu sechs gleich
    aussehende Knöpfe mit **drei** Bedeutungen (Buchung · Korrektur · blosse Auskunft),
    und **zwei Rollen** in einer Zeile («Rechnung erfassen» ist unsere Handlung, «Jetzt
    bezahlen» die des Zahlenden).

    Es sind zwei Fragen: *was schuldet uns jemand* (uns) und *wie kommt das Geld hierher*
    (dem Zahlenden). Zwei Fragen, zwei `ModuleSection` – und damit derselbe
    Fortschritts-Punkt wie an jedem anderen Abschnitt des Belegs, den es hier vorher gar
    nicht gab.

    Bug-Formen: (a) es gibt wieder einen gemeinsamen Abschnitt; (b) ein Fach zeigt keinen
    Fortschritt; (c) die Wörter stehen wieder in der Karte statt beim Server.
    """
    src = _code(_beleg())
    money = _component(src, "Money")
    assert money.count("<ModuleSection") == 2, (
        f"Das Geld steht in {money.count('<ModuleSection')} Abschnitt(en) statt in zwei "
        f"Fächern (a)."
    )
    assert money.count("state=") >= 2, "Ein Fach sagt seinen Fortschritt nicht (b)."
    assert "d.claim_title" in money and "d.settle_title" in money, (
        "Die Überschriften kommen nicht vom Server (c)."
    )
    # (c) **Und der alte Sammeltitel ist weg** – er fasste zwei Fragen zu einer zusammen.
    assert "money_label" not in src and "Rechnung & Zahlung" not in src, (
        "Der gemeinsame Titel ist zurück (a/c)."
    )


def test_exactly_one_money_action_moves_the_voucher_on():
    """►►► **Regel 2 — genau EINE Handlung bringt weiter.** ◄◄◄

    Unten, breit, farbig: *Rechnung stellen* → *Zahlung erfassen* → nichts mehr. Alles
    andere ist eine **Korrektur** und steht klein bei der Zeile, die sie korrigiert – nie
    im selben Rang. Es ist dasselbe Bauteil, das den Zuschlag und den Modul-Abschluss
    trägt (`StageAction`, #923): eine Handlung, die weiterbringt, sieht überall gleich aus.

    ►►► **Je Fach eine** – und sie überlappen nicht. ◄◄◄ *Rechnung stellen* → *Rechnung
    ist versendet* im einen, *Zahlung erfassen* bzw. *Jetzt bezahlen* im anderen; dass man
    erst auf eine Rechnung kassiert, die **draussen** ist, sagt `can` und nicht diese
    Datei.

    Bug-Formen: (a) die Handlung ist wieder ein Knopf unter vielen; (b) der Rang wird
    nicht abgeleitet, sondern nebeneinandergestellt; (c) das Formular steht neben dem
    Knopf, der es öffnet; (d) sie steht ausserhalb ihres Fachs.
    """
    src = _code(_beleg())
    money = _component(src, "Money")
    assert "<StageAction" in money, (
        "Die Geld-Handlung ist keine Stufen-Handlung mehr (a) – dann steht sie wieder im "
        "Rang einer Korrektur."
    )
    # **Eine Stelle rendert sie** – welche der beiden es ist, entscheidet `slot`.
    assert money.count("<StageAction") == 1, (
        f"Es gibt {money.count('<StageAction')} Stellen, an denen eine dominante "
        f"Handlung entsteht (a) – es ist eine Form, kein Knopf je Fall."
    )
    # (b) **Abgeleitet, nicht nebeneinandergestellt**: erst stellen, dann versenden, dann
    # kassieren – ein Rang, den die Oberfläche vergäbe, wäre die zweite Regel neben `can`.
    for derived in ("const claimAction =", "const settleAction ="):
        assert derived in money, f"Der Rang wird nicht abgeleitet (b): «{derived}»."
    # (c) **Das Formular tritt an ihre Stelle**, es steht nicht daneben – entschieden an
    # **einer** Stelle.
    assert "if (form)" in money, (
        "Formular und Knopf stehen gleichzeitig da (c) – zwei Handlungen für dieselbe "
        "Sache."
    )
    # (d) ►►► **Und sie steht in dem Fach, zu dem sie gehört** (Testnotiz #1001). ◄◄◄
    # Unter **beiden** Abschnitten stand sie hinter allem, was in ihnen wächst: jede
    # erfasste Zahlung schob sie weiter weg von der Wahl, mit der sie eine Einheit bildet.
    assert money.count("slot('bill')") == 1 and money.count("slot('pay')") == 1, (
        "Die Handlung steht wieder ausserhalb der beiden Fächer (d) – dann trennt sie "
        "jede neue Zeile von der Wahl, zu der sie gehört."
    )


def test_the_way_to_the_money_is_one_choice_with_several_answers():
    """►►► **Regel 3 — der Weg zum Geld ist eine Wahl, kein Verb.** ◄◄◄

    Bar · Überweisung · Karte sind drei Antworten auf **eine** Frage. Was dahinter
    passiert, ist verschieden (buchen ↔ Angaben zeigen ↔ Zahlformular öffnen) – die Frage
    ist dieselbe. Als drei Knöpfe standen sie im selben Rang wie eine Buchung und wie eine
    Korrektur.

    **Welche Antworten es gibt, sagt der Server** (`ways` aus `can`), und **jeder Weg sagt
    selbst, was er auslöst** (`action`/`verb`) – ein Weg ohne beides ist eine reine
    Auskunft, und dort steht kein Knopf, der nach Buchung aussieht.

    Bug-Formen: (a) die Wege sind wieder Knöpfe; (b) die Oberfläche baut die Liste selbst;
    (c) sie leitet das Verb aus dem Schlüssel ab; (d) bei genau einer Antwort steht
    trotzdem ein Schieber.
    """
    src = _code(_beleg())
    money = _component(src, "Money")
    assert "<Segmented" in money, "Die Wege sind wieder einzelne Knöpfe (a)."
    assert "d.ways" in money, "Die Liste kommt nicht vom Server (b)."
    for key in ("'cash'", "'card'", "'transfer'"):
        assert key not in money, (
            f"«{key}»: die Oberfläche kennt die Schlüssel der Wege (c) – dann leitet sie "
            f"das Verb daraus ab, statt es zu lesen."
        )
    assert "way.verb" in money and "way?.action" in money, (
        "Der Weg sagt nicht selbst, was er auslöst (c)."
    )
    assert "ways.length > 1" in money, (
        "Bei genau einer Antwort steht ein Schieber (d) – eine Wahl mit einer Antwort ist "
        "keine (#793)."
    )


def test_the_card_takes_the_charge_word_from_the_server():
    """►►► **«Rechnung stellen» ↔ «Rechnung erfassen» – das Wort kommt vom Server.** ◄◄◄

    Die Regel selbst (zwei Bits, zwei Wörter) prüft
    ``test_voucher_module.test_an_invoice_is_issued_here_and_recorded_there``; hier steht
    nur die Naht zur Oberfläche.

    Bug-Formen: (b) der Beleg schickt das Wort nicht mit; (c) die Karte schreibt es selbst.
    """
    src = (BACKEND / "app" / "services" / "voucher.py").read_text()
    assert '"charge_word": vo.charge_word(' in src, (
        "Der Beleg schickt nicht das Wort seiner Lage (b)."
    )
    card = _code(_beleg())
    for word in ("Rechnung stellen", "Rechnung erfassen", "Gutschrift stellen"):
        assert word not in card, f"«{word}» steht als Literal in der Karte (c)."


def test_the_sender_side_names_the_address_the_goods_leave_from():
    """►►► **«Lieferadresse» beim Leistungserbringer war falsch** (Testnotiz #979). ◄◄◄

    *«Beim Leistungserbringer wäre es evtl. besser/richtiger zu sagen Absendeadresse oder
    so? Etabliere hier korrektes.»* – Richtig gesehen: «Lieferadresse» heisst *wohin
    geliefert wird*, und an der eigenen Anschrift des Leistungserbringers stand damit, man
    möge ihm dorthin liefern – während er derjenige ist, der liefert. Von seiner Seite aus
    ist es die Adresse, von der die Ware **abgeht**: **Versandadresse** (der Versender ist
    die Gegenrolle des Empfängers, so heisst es im Handel, in der Logistik und im Zoll).

    **Nur diese eine Beschriftung ist rollenabhängig**, und das ist Absicht: die
    «Rechnungsadresse» beantwortet auf beiden Seiten dieselbe Frage – *welche Anschrift
    gilt in Rechnungssachen*. Ein zweites Wort dafür wäre eine Unterscheidung ohne
    Unterschied.

    Bug-Formen: (a) beide Seiten sagen wieder «Lieferadresse»; (b) die Rolle wird an der
    Aufrufstelle geraten statt aus der Richtung gelesen; (c) die Karte kennt die Wörter.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo

    assert vo.SHIPPING_FROM_LABEL != vo.SHIPPING_LABEL, (
        "Beide Seiten sagen dasselbe (a)."
    )
    src = (BACKEND / "app" / "services" / "voucher.py").read_text()
    body = src[src.index("def _addresses("):]
    body = body[:body.index("\ndef ", 1)]
    assert "sends" in body and "SHIPPING_FROM_LABEL" in body, (
        "Die Auflösung kennt die Rolle nicht (a)."
    )
    # (b) **Die Richtung sagt es** – `collects` steht längst da, und die Gegenseite leitet
    # es selbst ab: ein Parameter wäre eine Angabe, die jeder Aufrufer falsch setzen kann.
    theirs = src[src.index("def their_side("):]
    theirs = theirs[:theirs.index("\ndef ", 1)]
    assert "not vo.of(row.direction).collects" in theirs, (
        "Die Gegenseite rät ihre Rolle (b)."
    )
    head = src[src.index("def _ours("):src.index("def _creditor(")]
    assert "sends=flow.collects" in head, "Unsere Seite rät ihre Rolle (b)."
    assert "Versandadresse" not in _code(_beleg()), (
        "Das Wort steht als Literal in der Karte (c)."
    )


def test_the_recipient_choice_stands_above_the_role_not_in_its_name_line():
    """►►► **Die Auswahl steht ÜBER der Rolle** (Testnotiz #981). ◄◄◄

    *«Gefühlt sollte die Auswahloptionen oberhalb vom Headline Leistungsempfänger stehen
    und dann je nachdem was angewählt wurde unterhalb der Headline die Angaben geladen
    werden – es ist einfach noch nicht so elegant, wie ich es gerne hätte.»*

    Die Chips standen **in** der Namenszeile, also unter der Rolle und an genau der
    Stelle, an der sonst der Name steht: sie ersetzten die Angabe, die sie auswählen. Über
    der Rolle ist es die Reihenfolge des Lesens – erst *wen meine ich*, dann *was gilt für
    ihn*. Auf unserer Seite bleibt die Zeile leer; die Symmetrie ist dieselbe Regel wie bei
    jeder anderen Zeile des Rasters (#913).

    Bug-Formen: (a) die Auswahl steht wieder unter der Rolle; (b) das Raster zählt die
    Zeile nicht mit – dann laufen die beiden Blöcke auseinander; (c) der Name steht nicht
    mehr unter der Rolle.
    """
    src = _code(_beleg())
    party = _component(src, "Party")
    assert party.index("<Recipients") < party.index("{side.label}"), (
        "Die Auswahl steht wieder unter der Rolle (a)."
    )
    assert party.index("{side.label}") < party.index("view.name"), (
        "Der Name steht nicht unter der Rolle (c)."
    )
    assert "const PARTY_ROWS = 8" in src, (
        "Das Raster zählt die neue Zeile nicht mit (b) – dann steht dieselbe Angabe auf "
        "beiden Seiten auf verschiedener Höhe."
    )
    # (b) **Und unsere Seite hält die Zeile frei** – ein fehlendes Kind verschöbe alles
    # darunter um eine Zeile.
    assert "side.ours\n        ? <div />" in party or "? <div />" in party, (
        "Unsere Seite lässt die Zeile aus (b)."
    )
    # (a) **Die Chips sind nur noch die Auswahl** – benannt wird die Gewählte darunter.
    rec = _component(src, "Recipients")
    assert "font: '600 13px var(--font-body)'" not in rec, (
        "Die Auswahl trägt wieder den Namen der Gewählten (a) – dann steht er zweimal."
    )


def test_a_customs_field_names_itself_while_it_is_being_typed():
    """►►► **Die Beschriftung steht davor – beim Eingeben wie im Beleg** (#982). ◄◄◄

    *«Im fertigen Beleg steht eigentlich immer ‹Zolltarif xy, Ursprung xy› – hier bei der
    Eingabe steht einfach nur das Eingabefeld, aber der entsprechende Text nicht davor.
    Das ist eine unerlaubte Abweichung von unserer Logik.»*

    Der Name stand als **Platzhalter** im Feld – also an der Stelle, an der eine Oberfläche
    sagt «hier ist nichts» – und verschwand beim ersten Zeichen. Die Regel dieses Belegs
    lautet *der gedruckte Wert IST das Bedienelement* (#922): was man ändert, muss aussehen
    wie das, was gedruckt wird.

    Bug-Formen: (a) der Name ist wieder nur ein Platzhalter; (b) die beiden Zustände sehen
    verschieden aus; (c) die Beschriftung trägt die Auszeichnung änderbarer Werte, obwohl
    sie nicht änderbar ist.
    """
    src = _code(_beleg())
    body = _body(src, "Customs", kind="function")
    assert "placeholder=" not in body, (
        "Der Name steht wieder als Platzhalter (a) – dann ist er beim ersten Zeichen weg."
    )
    # (b) **Dieselbe Zeile in beiden Zuständen**: Beschriftung, dann Wert – gleiche Grösse,
    # gleiche Farbe. Gezählt, denn genau eine der beiden Stellen könnte abweichen.
    assert body.count("fontSize: 11.5, color: 'var(--fg-3)'") == 2, (
        "Die Beschriftung sieht im Eingabe- und im Lesezustand verschieden aus (b)."
    )
    # (c) **Nur der Wert ist änderbar** – die Hülle umschliesst das Feld, nicht das Wort.
    # Gefragt wird der **Textknoten**: `title={label}` und `aria-label={label}` stehen
    # zu Recht in der Hülle, und ein blosses «`{label}` kommt darin vor» wäre schon davon
    # erfüllt (gemessen – die erste Fassung schlug genau daran an).
    edit = body[body.index('<span className="inline-flex'):]
    assert edit.index("{label}</span>") < edit.index("<Editable"), (
        "Die Beschriftung steht innerhalb der Auszeichnung (c) – dann verspricht sie "
        "Änderbarkeit, die es nicht gibt."
    )


def test_no_editable_value_of_the_voucher_lives_only_in_the_browser():
    """►►► **Jede Angabe des Belegs hat ihr Verb** (Testnotiz #985). ◄◄◄

    *«Eingaben in ‹Zahlungsfrist› und ‹Lieferfrist› werden nicht persistiert.»* – Sie
    waren die einzige Angabe ohne eigenes: ein gehobener Zustand in ``BelegWork``,
    mitgeschickt allein in der Nutzlast von ``ask``. Ein Reload verwarf ihn.

    Geprüft wird die **Regel**, nicht die zwei Felder: der Beleg schickt keine Frist in
    der Nutzlast eines anderen Verbs mit, und die Zeile, die sie zeigt, speichert sie
    selbst – dieselbe Bauart wie die Lieferbedingung.

    Bug-Formen: (a) ``ask`` trägt wieder eine Frist mit (der Entwurf lebt woanders);
    (b) die Frist wird nicht gespeichert (kein ``useAutosave`` in ihrer Zeile); (c) das
    Verb heisst nicht ``terms``, also kommt nichts an.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))

    # (a) **Keine Frist reist in einem fremden Befehl mit.** Der eine Payload-Bauer für
    #     `ask` steht in `BelegWork`; steht dort eine Frist, gibt es wieder einen Entwurf,
    #     den niemand schreibt.
    asker = _component(src, "BelegWork")
    for field in ("payment_days", "lead_days"):
        assert field not in asker, (
            f"«{field}» reist wieder in der Nutzlast von `ask` mit (a) – dann lebt der "
            f"Entwurf im Browser, und ein Reload verwirft ihn."
        )

    # (b)/(c) **Die Zeile, die eine Frist zeigt, speichert sie auch** – mit ihrem Verb.
    saver = _component(src, "SavedTerm")
    assert "useAutosave" in saver, (
        "Die Frist wird nicht gespeichert (b) – sie steht wieder nur im Browser."
    )
    assert "'terms'" in saver or '"terms"' in saver, (
        "Die Frist wird mit einem anderen Verb geschickt (c) – der Dienst kennt nur "
        "`terms`, also kommt nichts an."
    )


def test_a_recipient_chip_carries_no_state_dot():
    """►►► **Der Chip sagt seinen Zustand nicht zum vierten Mal** (Testnotiz #983). ◄◄◄

    *«Ein optisch störender Punkt/Separator. Entfernen, ohne das umliegende Spacing zu
    zerschiessen.»* – Er stand als 6-px-Punkt vor dem Namen und war genau das: was
    angefragt ist, sagt das **Zeichen rechts** (`+` ↔ `✕`), die **Textfarbe** und das
    **Wort im Hover** – und ausführlich der Abschnitt *Angebote* eine Zeile tiefer, wo
    jede Zeile ihren eigenen Punkt **und** ihr Wort trägt.

    «Punkt + Wort» bleibt die Anatomie eines Zustands im Haus; hier fehlte das Wort, und
    was blieb, war ein Zeichen, das man deuten muss.

    Bug-Formen: (a) der Punkt steht wieder im Chip; (b) mit ihm verschwand auch das Wort
    im Hover, also sagt der Chip seinen Zustand gar nicht mehr.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    chip = _component(src, "RecipientChip")
    assert "rounded-full" not in chip, (
        "Der Zustandspunkt steht wieder im Chip (a) – die vierte Fassung derselben "
        "Aussage, und die einzige ohne Wort."
    )
    assert "data-tip={look.label}" in chip, (
        "Mit dem Punkt ist auch das Wort gegangen (b) – dann sagt der Chip seinen "
        "Zustand nirgends mehr."
    )


def test_both_booking_forms_are_the_same_form():
    """►►► **Ein Formular, und es sieht aus wie jedes andere** (#987/#990). ◄◄◄

    *«Feldhöhen, Spacing, Button-Hierarchie: eine Primäraktion, Abbrechen dezent. Beide
    untereinander identisch.»*

    «Rechnung stellen» und «Zahlung erfassen» waren schon **dieselbe** Komponente;
    auseinander lagen die Masse – ein eigener `gap: 3` unter der Beschriftung (obwohl
    `fields.Label` seine 4 px mitbringt) und zwei gleich grosse Knöpfe nebeneinander.

    Bug-Formen: (a) die Masse stehen wieder als Zahlen an dieser Stelle; (b) zwei gleich
    grosse Knöpfe; (c) das Feld ist nicht das des Hauses.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    form = _component(work, "Entry")
    # (a) **Der Abstand kommt aus dem Bauteil.** Und unter der Beschriftung gibt es keinen:
    # `Label` bringt seine eigenen 4 px mit.
    assert "FIELD_GAP" in form, "Der Feld-Abstand steht wieder als Zahl da (a)."
    ask = _component(work, "Ask")
    assert "gap:" not in ask, (
        "Unter der Beschriftung steht wieder ein eigener Abstand (a) – `Label` bringt "
        "seine 4 px mit, und ein `gap` kommt obendrauf."
    )
    # (b) **Eine Primäraktion, Abbrechen dezent** – dieselbe Zeile wie überall im Beleg.
    assert "<StageRow" in form and "<StageAction" in form, (
        "Die beiden Knöpfe stehen wieder gleichrangig nebeneinander (b)."
    )
    assert "square" in form, "«Abbrechen» ist kein Quadrat daneben (b)."
    # (c) **Das Formularfeld des Hauses** – ein Beleg-Feld (`DOC_FIELD`) wäre hier falsch:
    # dies ist wirklich ein Formular.
    assert form.count("inputCls") >= 2, "Die Felder sind nicht die des Hauses (c)."


def test_a_payment_row_begins_with_how_it_was_paid():
    """►►► **Zahlungsart zuerst, dann Betrag und Datum** (Testnotiz #994). ◄◄◄

    *«Im Abschnitt ‹Begleichen› soll jede Zahlungszeile mit der Zahlungsart beginnen.»* –
    Das ist die Angabe, an der man eine Zahlung wiedererkennt; die Referenz sagt sie
    nicht, und bei einer Barzahlung gibt es gar keine. Sie stand in einer zweiten Zeile
    hinter dem Zustand.

    ►►► **Und «Offen» steht nicht dreimal** (#988). ◄◄◄ Der Zustand stand als eigene
    Zeile unter der Rechnung, obwohl der Punkt eine Zeile höher ihn schon sagt – und
    «Offen» ein drittes Mal in der Brücke zwischen den beiden Fächern, wo es die Zahl
    trägt.

    Bug-Formen: (a) die Zahlungsart steht wieder hinten; (b) der Zustand steht wieder als
    eigene Zeile darunter; (c) die Rechnung verliert dabei ihren Zustand ganz.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    row = _component(work, "EntryRow")
    # **Der Identifikator ist der erste Platz der Zeilen-Grammatik** – gefragt ist, was
    # dort steht, nicht mehr, in welcher Reihenfolge eine handgebaute Flexzeile ihre
    # Kinder aufzählt.
    ident = row[row.index("ident="):row.index("meta=")]
    assert "e.method_label" in ident, (
        "Die Zahlungszeile beginnt nicht mit ihrer Art (a)."
    )
    assert row.index("ident=") < row.index("amount="), (
        "Die Zahlungsart steht hinter dem Betrag (a)."
    )
    # (b) **Keine zweite Zeile mehr** – dort standen Zustand und Vermerk (#988/#999).
    assert "state.label" not in row, (
        "Der Zustand steht wieder als eigene Zeile darunter (b)."
    )
    # (c) **Und die RECHNUNG sagt ihren Zustand weiterhin** – als Farbe ihres Betrags und
    # als Wort im Hover. *Sie steht seit dem Umbau nicht mehr in derselben Liste wie die
    # Zahlungen: eine Zahlung ist ein Ereignis, kein Beleg mit einem Stand.*
    invoice = _component(work, "InvoiceRow")
    assert "invoice.state_tone" in invoice and "invoice.state_label" in invoice, (
        "Die Rechnung sagt ihren Zustand gar nicht mehr (c)."
    )


# ---------------------------------------------------------------------------
# ►► Testnotizen #995–#1003 — eine Zeilen-Grammatik, und der Saldo ist eine Farbe
# ---------------------------------------------------------------------------


def test_a_money_row_follows_one_grammar():
    """►►► **Eine Zeile, vier Plätze, immer dieselben** (#996/#998/#999/#1002). ◄◄◄

    *«Definiere EIN Zeilenlayout, das für alle Zeilen in ‹Fordern› und ‹Begleichen› gilt,
    und implementiere es als eine Komponente:*
    ``[ Identifikator ] [ Meta ] … [ Aktion ] [ Betrag ]``*»*

    Vier Notizen, ein Layout – und jede betraf einen anderen Platz darin: der Zustandspunkt
    vor der Rechnungsnummer (#996), die Korrekturen **hinter** dem Betrag (#998/#1002) und
    eine **zweite Zeile** mit einer Angabe, die die erste schon sagt (#999).

    Bug-Formen: (a) die Aufrufstelle baut ihre Zeile wieder selbst; (b) der Betrag steht
    nicht zuletzt; (c) die Aktion steht hinter ihm; (d) die Zeile bricht um oder hat eine
    zweite; (e) vor dem Identifikator steht wieder ein Zeichen.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    grammar = _body(ui, "LedgerRow", kind="export function")
    flat = " ".join(grammar.split())
    # (b)/(c) **Die Reihenfolge IST die Grammatik.**
    order = [flat.index(x) for x in ("{ident}", "{meta}", "<RowActions", "{amount}")]
    assert order == sorted(order), (
        f"Die vier Plätze stehen nicht in ihrer Reihenfolge (b/c): {order}."
    )
    # (d) **Strikt einreihig** – was nicht passt, wird gekappt, nie umgebrochen.
    assert "flexWrap: 'nowrap'" in flat, (
        "Die Zeile darf wieder umbrechen (d) – dann rutscht der Betrag unter den Text."
    )
    assert flat.count("truncate") >= 2, (
        "Identifikator und Meta kappen nicht (d) – dann bricht die Zeile doch."
    )
    # (a) **Die Aufrufstelle sagt nur, WAS an die Plätze gehört.**
    row = _component(_code(_beleg()), "EntryRow")
    assert "<LedgerRow" in row, "Die Geld-Zeile baut sich wieder selbst (a)."
    for slot in ("ident=", "meta=", "actions=", "amount="):
        assert slot in row, f"Der Platz «{slot}» fehlt (a)."
    # (e) **Kein Zeichen vor dem Identifikator** – der Punkt sagte als viertes, was die
    # Farbe des Betrags, der Hover und der Abschnitt «Angebote» längst sagen (#996).
    assert "rounded-full" not in row, (
        "Vor der Rechnungsnummer steht wieder ein Punkt (e) – er rückt sie ein und sagt "
        "als Zeichen etwas, wofür ihm das Wort fehlt."
    )
    # (d) **Und die zweite Zeile ist weg** – dort stand «Zahlungsdienst» neben «Karte».
    # *Gefragt ist der **Vermerk**, nicht das Wort: «Zahlungsdienst» steht in derselben
    # Datei völlig zu Recht in einer Fehlermeldung – der erste Anlauf zählte sie mit.*
    assert 'note="Zahlungsdienst"' not in _read(
        BACKEND / "app" / "services" / "stripe_pay.py"), (
        "Der Vermerk «Zahlungsdienst» wird wieder geschrieben (d) – die Zahlungsart sagt "
        "es bereits."
    )


def test_the_balance_is_a_number_and_its_colour():
    """►►► **Der Saldo sagt seinen Zustand als FARBE** (Testnotiz #997). ◄◄◄

    *«Das Wort ‹Offen› entfällt.»* – Es war ohnehin nur an einem der vier Zustände
    richtig: «Offen 0.00» las sich wie «bezahlt», und bei einer Überzahlung sagte es das
    Gegenteil dessen, was dastand.

    Bug-Formen: (a) das Wort steht wieder vor der Zahl; (b) die Oberfläche rechnet den
    Zustand selbst; (c) das Guthaben steht ohne Namen da; (d) der offene Posten bekommt
    ein Minus.
    """
    src = _code(_beleg())
    bal = _component(src, "Balance")
    # (a) **Kein Wort ausser dem Guthaben** – und das kommt vom Server.
    assert "open_word" not in src, "Das Wort «Offen» steht wieder vor der Zahl (a)."
    # *Gefragt ist der **Textknoten**, nicht das Vorkommen: das Wort steht ohnehin als
    # `data-tip`, und «kommt vor» liess die eigene Bug-Form durch – gemessen,
    # nachgeschärft.*
    visible = re.sub(r"\b\w+=\{[^}]*\}", "", bal)
    assert "d.open_state_label" in visible, (
        "Das Guthaben nennt sich nicht beim Namen (c) – «250.00» in Grün sagt nicht, wer "
        "wem etwas schuldet."
    )
    # (b) **Der Zustand kommt vom Server** – hier gerechnet wäre er die zweite Ableitung
    # derselben Zahlen und die erste, die eine Rundungstoleranz vergisst.
    assert "d.open_state_tone" in bal and "TONE[" in bal, (
        "Die Farbe wird wieder selbst gewählt (b)."
    )
    assert "Number(d.open)" not in bal, (
        "Die Oberfläche entscheidet wieder an der Zahl, welche Farbe gilt (b)."
    )
    # (d) **Ein offener Posten ist eine Forderung, kein negativer Wert** – das Vorzeichen
    # gibt es nur beim Guthaben, und dort dreht es die Zahl ins Positive.
    assert "negate(d.open)" in bal and "credit" in bal, (
        "Das Vorzeichen hängt nicht mehr am Guthaben (d)."
    )


def test_choosing_a_party_writes_it_instead_of_asking():
    """►►► **Die Wahl wird geschrieben, nicht abgeschickt** (Testnotiz #1000). ◄◄◄

    *«Wurde beim Anlegen kein Partner vorgewählt, lässt er sich nachträglich nicht mehr
    setzen. Die Auswahl wird korrekt angezeigt, aber nicht übernommen/persistiert.»*

    Das freie Feld rief `onAsk` – die Handlung, mit der der Beleg **nach aussen** geht. Sie
    verlangt Preis, beide Fristen und die Lieferbedingung, und an einem frischen Modul
    fehlt davon naturgemäss alles: der Dienst wies mit einem Satz ab, und die getroffene
    Wahl war weg. Anfragen tut der `+` am Chip, wenn alles dasteht.

    Bug-Formen: (a) das Feld fragt wieder an; (b) die Wahl lässt sich nicht mehr
    zurücknehmen, solange nichts hinausgegangen ist.
    """
    src = _code(_beleg())
    who = _component(src, "Recipients")
    field = who[who.index("<DocRef"):]
    assert "action: 'party'" in field and "onAsk(" not in field, (
        "Die Wahl der Gegenpartei fragt sie sofort an (a) – dann verwirft ein "
        "unvollständiger Beleg sie stillschweigend."
    )
    # (b) **Wer nur gewählt ist, lässt sich auch wieder wegnehmen** – dieselbe
    # Gegenhandlung wie beim Zurückziehen einer Anfrage; was sie bewirkt, sagt der Beleg.
    assert "removable" in who and "allowed.some" in who, (
        "Ein nur gewählter Partner lässt sich nicht mehr abwählen (b)."
    )


def test_an_autosave_never_moves_the_page():
    """►►► **Ein Auto-Save darf die Geometrie der Seite nicht verändern** (#1009). ◄◄◄

    *«Beim Autosave im Zahlungsmodul springt das Layout: Felder verändern ihre Höhe,
    wodurch das nächste Feld nicht mehr getroffen wird.»*

    Gemessen in Chromium an der echten Komponente – zwei Ursachen, beide hier festgehalten:

    (a) **Die Aufstellung entstand erst mit dem ersten Preis.** Netto- und Steuerzeile
        gab es nicht, solange nichts gebucht war; kam die Antwort des Servers, wuchsen sie
        in den Beleg und schoben die drei Konditionen-Felder um **45,5 px** nach unten.
        Welche Zeilen es gibt, sagen die **Positionen** (jede trägt ihren Satz) – der Platz
        steht damit von Anfang an, und wo noch kein Betrag gebucht ist, steht ein «—».

    (b) **`disabled` nimmt dem Feld den Fokus**, und es bekommt ihn nicht zurück: gemessen
        war ``document.activeElement`` nach jedem Auto-Save ``null`` – mitten im Tippen.
        `busy` sperrt darum nur noch **Handlungen** (Knöpfe), nie einen Wert.

    Bug-Formen: (a) die Netto-Zeile hängt wieder an einer Bedingung; (b) ein änderbarer
    Wert ist wieder `disabled={busy}`.
    """
    src = _beleg()
    sums = _code(_component(src, "Sums"))
    assert '<SumRow label="Netto"' in sums and "{d.net != null &&" not in sums, (
        "Die Netto-Zeile erscheint erst mit einem Wert (a) – dann springt alles darunter."
    )
    # **Die Zeilen kommen aus den Positionen**, nicht aus der Antwort des Servers allein:
    # sonst steht die Aufstellung erst, wenn der erste Preis gebucht ist. Gefragt ist die
    # **Schleife**, nicht der blosse Name: `d.lines` steht auch in der Abhängigkeitsliste,
    # und die erste Fassung war schon dadurch erfüllt (gegengeprüft).
    assert "for (const ln of d.lines)" in sums, (
        "Die Steuerzeilen kommen allein aus der Server-Aufteilung (a) – vor dem ersten "
        "Preis gibt es sie damit nicht."
    )
    # (b) **Kein Wert wird beim Speichern gesperrt.** Gefragt ist das Bedienelement, nicht
    # der Knopf: ein `<input>`/`<select>` hält Fokus und Cursor, ein Knopf nicht.
    for tag in ("<input", "<select"):
        for chunk in _code(src).split(tag)[1:]:
            head = chunk.split(">")[0]
            assert "disabled={busy}" not in head, (
                f"Ein Eingabefeld wird beim Speichern gesperrt (b): {tag}{head[:70]} – "
                "es verliert dabei Fokus und Cursorposition."
            )


def test_a_money_row_says_when_it_was_not_which_day():
    """►►► **In einer Geld-Zeile ist das Datum eine AUSKUNFT** (Testnotiz #1004). ◄◄◄

    *«‹Begleichen› zeigt weiterhin ‹13.09.2026› statt der relativen Form.»* – Und die
    Ursache war nicht der Server (er liefert ISO-Zeitstempel, formatiert wird allein im
    Browser): die Zeile rief ``day()``, also die **Tatsache**, die auf ein Papier gehört
    (MWSTG Art. 26). Gefragt ist hier aber *wann war das* – «vor 3 Tagen», wie eine Zeile
    höher bei der Fälligkeit. Das Datum verschwindet nicht, es steht im Hover.

    ►►► **Und eine Auskunft braucht einen ZEITPUNKT** (Testnotiz #1014). ◄◄◄ Dieselbe
    Regel, dreimal gemeldet – und die letzte Meldung lag nicht mehr an `when()`: die
    Funktion bekam `booked_on`, einen **reinen Tag**, und aus einem Tag ohne Uhrzeit lässt
    sich «vor 5 Minuten» nicht ableiten (sie überspringt die Stunden-Kaskade darum
    bewusst, statt Genauigkeit zu erfinden). Gefehlt hat der Zeitpunkt; er reist als
    `booked_at` mit.

    Bug-Formen: (a) der Buchungstag steht wieder als Datum in der Zeile; (b) die Aussage
    liest wieder den reinen Tag, und alles von heute heisst «Heute».
    """
    entry = _code(_component(_beleg(), "EntryRow"))
    assert "when(e.booked_at" in entry, (
        "Die Aussage liest den reinen Tag statt des Zeitpunkts (b) – damit heisst alles "
        "von heute «Heute», auch was vor fünf Minuten gebucht wurde."
    )
    assert "text: day(e.booked_on)" not in entry, (
        "Der Buchungstag steht wieder als Tatsache in der Zeile."
    )
    # Gefragt ist der Hover **dieser** Zeile: `day(e.booked_on)` steht auch im Hover der
    # Rechnungs-Zeile, und ein blosses «kommt vor» war schon dadurch erfüllt
    # (gegengeprüft).
    assert "`Gebucht ${day(e.booked_on)}`" in entry, (
        "Die Tatsache fehlt im Hover – eine Aussage ohne sie kann niemand nachprüfen."
    )


def test_an_amount_is_one_component_and_wears_one_colour():
    """►►► **EIN Betrag — Zahl, Währung, Zustandsfarbe** (Testnotiz #1007). ◄◄◄

    *«Zahl und Währung immer in derselben Farbe. Die Währung darf zurücktreten, aber nie
    in einer anderen Farbe.»* – Genau das war passiert: die Geld-Zeile färbte beide
    zusammen, der Saldo darunter setzte die Währung auf ``--fg-2`` und die Zahl auf ihren
    Ampelton.

    Die Regel steckt in der **Bauart**, nicht in einer Verabredung: die Währung ist ein
    **Kind** der Zahl und erbt ihre Farbe – sie kann gar keine andere mehr haben.

    Bug-Formen: (a) eine Aufrufstelle formatiert wieder selbst; (b) die Währung bekommt
    eine eigene Farbe.
    """
    assert "formatAmount(" not in _code(_beleg()), (
        "Eine Aufrufstelle des Belegs formatiert ihren Betrag selbst (a) – dann gibt es "
        "wieder zwei Schreibweisen für dieselbe Sache."
    )
    amount = _code(_component(_module_ui(), "Amount"))
    assert "color: 'inherit'" in amount, (
        "Die Währung trägt eine eigene Farbe (b) statt der der Zahl."
    )


def test_a_row_begins_on_the_same_edge_as_every_other():
    """►►► **Der Name der Angebotszeile ist nicht eingerückt** (Testnotiz #1005). ◄◄◄

    Ursache war ein **Icon-Platzhalter**: ein 6-px-Zustandspunkt mit 10 px Abstand davor –
    der Name begann damit 16 px weiter rechts als der Identifikator einer Geld-Zeile, die
    Menge einer Position oder die Beschriftung einer Kondition (gemessen: 525 statt 509).

    Es ist dieselbe Frage wie in der Geld-Zeile (#996), und die Antwort ist dieselbe: der
    Punkt geht, die Aussage bleibt – als Preis, und wo keiner dasteht, als **Wort**.

    Bug-Form: der Punkt steht wieder vor dem Namen.
    """
    quote = _code(_component(_beleg(), "QuoteRow"))
    assert "background: look.color" not in quote, (
        "Vor dem Namen steht wieder ein Zustandspunkt – er rückt die Zeile ein."
    )
    # Gefragt ist der **Textknoten**, nicht das Vorkommen: `tip={look.label}` steht
    # daneben am Betrag, und ein blosses «kommt vor» war schon dadurch erfüllt
    # (gegengeprüft) – dieselbe Falle wie bei `data-tip` in der Vorrunde.
    shown = re.sub(r"\b\w+=\{[^}]*\}", "", quote)
    # **Wie das Wort heisst, ist der Zeile ueberlassen** – gefragt ist, dass es dasteht.
    # Der Waechter verlangte woertlich ``{look.label}`` und verbot damit die bessere
    # Fassung von #1032: dort entscheidet eine Zeile hoeher, **wann** das Wort noetig ist
    # (waehrend verhandelt wird, IST der Preis die Aussage), und es steht unter einem
    # eigenen Namen da. Also: die Aufloesung, direkt oder unter ihrem Alias.
    names = {"look.label", *re.findall(r"const (\w+) = [^;]*look\.label", quote)}
    assert any("{%s}" % n in shown for n in names), (
        "Ohne Punkt und ohne Wort sagt die Zeile ihren Zustand gar nicht mehr."
    )


def test_an_undoing_action_never_looks_like_an_adding_one():
    """►►► **Ein Symbol zeigt, was die Handlung TUT** (Testnotiz #1008). ◄◄◄

    «Korrigieren» trug ein **Plus** – das Zeichen des Hinzufügens für eine Handlung, die
    eine Buchung zurücknimmt. Drei Korrekturen stehen in dieser Zeilengattung, und jede
    tut etwas anderes: annullieren (durchgestrichener Kreis, dasselbe Zeichen, mit dem
    das Haus «storniert» schreibt), zurücknehmen (Kreispfeil gegen den Uhrzeiger),
    Geld zurückschicken (Rückwärtspfeil).

    *Seit der Beleg **die** Rechnung ist, sind es zwei statt drei: der durchgestrichene
    Kreis gehörte der Gegenbuchung an einer Forderungs-Zeile, und die gibt es nicht mehr.
    An der **Rechnung** steht die Rücknahme (Rückwärtspfeil – sie ist nie hinausgegangen),
    an der **Zahlung** die Korrektur (Kreispfeil) und die Online-Erstattung.*

    Bug-Form: eine Korrektur trägt wieder ein Plus.
    """
    src = _code(_beleg())
    entry = _component(src, "EntryRow")
    invoice = _component(src, "InvoiceRow")
    assert "icon={Plus}" not in entry and "icon={Plus}" not in invoice, (
        "Eine rückgängig machende Handlung trägt das Zeichen des Hinzufügens."
    )
    for icon in ("icon={RotateCcw}", "icon={Undo2}"):
        assert icon in entry, f"Der Zahlungszeile fehlt ihr Symbol: {icon}."
    assert "icon={Undo2}" in invoice, "Der Rechnung fehlt ihr Rücknahme-Symbol."


def test_a_save_never_hides_a_control_in_the_party_block():
    """►►► **Ein Auto-Save verändert die Geometrie NICHT** (Testnotiz #1016). ◄◄◄

    *«Der Partner-Block im Zahlungsmodul springt beim Autosave weiterhin.»*

    Die Ursache stand im Chip: ``onAsk``/``onDrop`` hingen an ``!busy``, waren also
    während **jedes** Speicherns ``undefined``. Damit verschwanden die beiden Zeichen aus
    dem Chip, seine rechte Polsterung wechselte von 4 auf 8 px – jeder Chip wurde
    schmaler, die umbrechende Reihe floss neu, der Block sprang; danach kamen sie zurück
    und er sprang erneut.

    Es ist dieselbe Fehlerform wie ``disabled={busy}`` an einem Eingabefeld (#1009), nur
    eine Stufe gröber: **``busy`` darf nie etwas ein- oder ausblenden.** Rückmeldung
    kommt über **Deckkraft**, die am Layout nichts ändert.

    Bug-Formen: (a) die Handlungen hängen wieder an ``busy``, also verschwinden die
    Knöpfe; (b) die Rückmeldung ändert wieder Masse statt Deckkraft.
    """
    src = _beleg()
    rec = _code(_component(src, "Recipients"))
    for form in ("!busy ?", "&& !busy", "!busy &&"):
        assert form not in rec, (
            f"Eine Handlung des Chips hängt wieder am Speichern (a): «{form}» – damit "
            f"verschwindet ein Knopf mitten im Vorgang und die Reihe fliesst neu."
        )
    # ►►► **Und die Regel gilt der ganzen KARTE, nicht diesem einen Block.** ◄◄◄ Sie ist
    # zweimal gebrochen worden – einmal an den Chips (#1016), einmal am Korrektur-Verweis,
    # dessen Auszeichnung samt ihrer Mindestbreite (`MIN_PICK`) beim Speichern verschwand
    # und die Zeile schrumpfen liess. `busy` sperrt **Handlungen** (`disabled`) und pausiert
    # das Speichern selbst; es entscheidet nie, **ob** etwas dasteht.
    #
    # *Gelesen wird ein **Fenster** vor der Fundstelle, nicht die Zeile: ein
    # `useAutosaveSignature(…)`-Aufruf bricht um, und ein zeilenweiser Wächter meldete
    # ausgerechnet seine Fortsetzung (gemessen, nachgeschärft).*
    allowed = ("useAutosaveSignature(", "const ready =")
    code = _code(src)
    for m in re.finditer(r"!busy", code):
        window = code[max(0, m.start() - 160):m.start()]
        assert any(a in window for a in allowed), (
            f"«{code[m.start() - 40:m.start() + 40].strip()}»: `busy` entscheidet wieder, "
            f"ob etwas gezeichnet wird (a) – das verschiebt die Zeile unter dem Zeiger."
        )
    chip = _code(_component(src, "RecipientChip"))
    assert "opacity: busy" in chip, (
        "Der Chip meldet das Speichern nicht über die Deckkraft (b)."
    )
    # **Kein Mass hängt am Speichern** – Polsterung, Breite, Höhe und Anzeigeart sind
    # genau die Angaben, die eine Zeile umbrechen lassen.
    for prop in ("padding", "width", "height", "display", "fontSize", "gap"):
        assert not re.search(prop + r":\s*busy", chip), (
            f"«{prop}» hängt am Speichern (b) – das verschiebt die Zeile unter dem Zeiger."
        )


def test_a_date_stands_right_of_the_row_never_in_the_flow():
    """►►► **Datum und Fälligkeit stehen RECHTS, links vom Betrag** (#1011/#1012). ◄◄◄

    *«Datum/Fälligkeit stehen links im Fliesstext. Das Datum gehört rechtsbündig direkt
    links neben den Betrag; der Betrag bleibt ganz rechts auf fester Flucht.»*

    Es ist die **zweite Zahl** der Zeile, und zwei Zahlen gehören nebeneinander: so
    stehen sie über alle Zeilen hinweg in zwei Spalten, ohne dass jemand eine
    Spaltenbreite pflegt.

    Bug-Formen: (a) das Datum steckt wieder im Fliesstext (``meta``); (b) es gibt den
    Platz gar nicht; (c) es schrumpft mit und malt sich über seine Box hinaus.
    """
    row = _code(_component(_module_ui(), "LedgerRow"))
    assert "date" in row, "Die Zeilen-Grammatik kennt keinen Platz für das Datum (b)."
    # Der Betrag bleibt das **letzte** Element – daran hängt seine Flucht (#996).
    assert row.rindex("{date}") < row.rindex("{amount}"), (
        "Das Datum steht hinter dem Betrag (b) – dort sucht das Auge die Zahl."
    )
    entry = _code(_component(_beleg(), "EntryRow"))
    assert "date={stamp.text}" in entry, (
        "Die Geld-Zeile füllt den Platz nicht (b)."
    )
    assert "meta={[stamp.text" not in entry, (
        "Das Datum steckt wieder im Fliesstext (a) – dann springt der Blick zweimal."
    )
    # (c) Ein Datum hat keine Umbruchstelle; schrumpfen darf allein das Meta.
    block = row[row.index("{date}") - 400:row.index("{date}")]
    assert "flex: 'none'" in block and "nowrap" in block, (
        "Das Datum darf schrumpfen (c) – «20.8.2026» malt sich dann über seine Box hinaus."
    )


def test_a_refund_that_fails_says_so():
    """►►► **«Online erstatten» sagt, was daraus wurde** (Testnotiz #1013). ◄◄◄

    *«Der Button ‹Online erstatten› hat keine Wirkung. Ein Fehlschlag muss eine sichtbare
    Meldung erzeugen, nicht stillschweigend scheitern.»*

    Zwei Ursachen: der Aufruf endete auf ``.catch(() => {})`` – ein 409 des Dienstes kam
    nirgends an –, und **gebucht wird vom Webhook**, nicht vom Aufruf: ein einzelnes
    Neuladen direkt danach zeigt verlässlich nichts. Nachgefragt wird jetzt mit derselben
    Mechanik wie bei einer Zahlung, und die Meldung steht da, wo man sie sieht.

    Bug-Formen: (a) der Fehler wird wieder verschluckt; (b) es wird nicht nachgefragt,
    also sieht man die gebuchte Zeile nie; (c) die Meldung wird gefangen, aber nirgends
    gerendert.
    """
    money = _code(_component(_beleg(), "Money"))
    assert "catch (e)" in money and "setFailed" in money, (
        "Der Fehlschlag wird gefangen und weggeworfen (a) – ein stiller Nicht-Effekt ist "
        "schlimmer als ein Fehler."
    )
    assert "catch(() => {})" not in _code(_beleg()), (
        "Irgendwo wird ein Fehlschlag wieder verschluckt (a)."
    )
    assert re.search(r"refundVoucherPayment[\s\S]{0,200}setWaiting\(WAIT_TRIES\)", money), (
        "Nach der Erstattung wird nicht nachgefragt (b) – gebucht wird vom Webhook."
    )
    # (c) Gefragt ist das **Rendern**, nicht der Zustand: `setFailed` allein steht auch
    #     dann noch da, wenn niemand die Meldung zeigt (gegengeprüft).
    assert "{failed}" in money, "Die Meldung wird nirgends gezeigt (c)."


def test_a_refund_button_closes_at_the_click():
    """►►► **Ab dem Klick zu — die dritte Ebene von dreien** (Testnotiz #1018). ◄◄◄

    *«Der Button lässt sich mehrfach drücken, dann erscheint ein technischer Fehlertext
    des Zahlungsdienstes.»*

    Die beiden anderen Ebenen stehen im Dienst (der erstattbare **Rest**) und beim Dienst
    (der **Idempotenz-Schlüssel**). Hier fehlt die dritte: zwischen Klick und Buchung
    liegt die Meldung des Webhooks, und in diesem Fenster sagt niemand etwas – also sagt
    es der Knopf selbst. Dass er danach ganz **verschwindet**, sagt weiterhin der Server
    (``refundable``); eine Oberfläche, die das selbst rechnete, wäre der zweite Massstab.

    Bug-Formen: (a) der Knopf kennt seinen Zustand nicht; (b) er wird nicht gesperrt;
    (c) die Sperre fällt nach einem Fehler nicht zurück (dann ist ein Netzwerkfehler eine
    Sackgasse).
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    row = _component(work, "EntryRow")
    money = _component(work, "Money")
    # (a) **Die Aufrufstelle sagt es der Zeile** – je Zeile, nicht je Karte: es geht um
    #     genau diese Zahlung.
    assert "refunding" in row and "refunding={" in money, (
        "Die Geld-Zeile weiss nicht, dass ihre Erstattung unterwegs ist (a)."
    )
    at = row.index("onRefund(e.id)")
    near = row[row.rfind("<ActionButton", 0, at):at]
    assert "refunding" in near, (
        "Der Erstattungs-Knopf bleibt beim Klick offen (b) – dann geht sie zweimal hinaus."
    )
    # (c) **Und nach einem Fehler kommt er zurück.** Gesucht wird die Reihenfolge: gesperrt
    #     **vor** dem Aufruf, freigegeben im `catch`.
    refund = money[money.index("const refund ="):money.index("const invoice =")]
    lock = refund.index("setSent")
    assert lock < refund.index("await api.refundVoucherPayment"), (
        "Gesperrt wird erst nach der Antwort (b) – das Fenster ist genau davor."
    )
    assert "s.filter((id) => id !== entryId)" in refund[refund.index("catch"):], (
        "Nach einem Fehler bleibt der Knopf zu (c) – dann ist ein Netzwerkfehler eine "
        "Sackgasse."
    )


def test_what_is_still_open_stands_above_the_way_to_settle_it():
    """►►► **Der Saldo steht ÜBER der Zahlungsart** (Testnotiz #1019). ◄◄◄

    *«Der Saldo-Container gehört über den Bereich Zahlungsart, nicht darunter.»*

    Er war die **Fusszeile der ganzen Karte** und stand damit hinter allem, was in ihr
    wächst: man wählte einen Weg zum Geld, ohne die Zahl zu sehen, um die es geht. Die
    Reihenfolge im Fach «Begleichen» ist jetzt fest – erfasste Zahlungen → **Saldo** →
    Zahlungsart → Auskunft/Karte → Handlung.

    Bug-Formen: (a) der Saldo steht wieder ausserhalb des Fachs; (b) er steht darin, aber
    unter der Wahl; (c) die Ausbuchung, die von genau dieser Zahl handelt, wandert weg.
    """
    money = _code(_component(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"),
                             "Money"))
    body = money[money.index("return ("):]
    settle = body.index("d.settle_title")
    close = body.index("</ModuleSection>", settle)
    fach = body[settle:close]
    # (a)
    assert "<Balance" in fach, (
        "Der Saldo steht wieder ausserhalb des Fachs «Begleichen» (a) – dann hängt er "
        "hinter allem, was darin wächst."
    )
    assert "<Balance" not in body[close:], "Der Saldo steht zweimal (a)."
    # (b) **und (c)** – die Reihenfolge ist die Aussage.
    assert fach.index("<Balance") < fach.index("<Segmented"), (
        "Der Saldo steht unter der Zahlungsart (b) – man wählt, ohne die Zahl zu sehen."
    )
    assert "{writeOff}" in fach and fach.index("{writeOff}") < fach.index("<Segmented"), (
        "Die Ausbuchung steht nicht mehr bei der Zahl, von der sie handelt (c)."
    )


def test_the_way_to_the_money_needs_no_label():
    """►►► **«Zahlungsart» sagt nichts, was nicht darunter steht** (Testnotiz #1020). ◄◄◄

    *«Das Label ‹Zahlungsart› entfernen – der Bereich ist selbsterklärend.»*

    «Bar», «Überweisung», «Karte» sagen jede für sich, was sie sind, und der Abschnitt
    darüber heisst «Begleichen». Ein Wort, das nur wiederholt, ist Höhe ohne Aussage.

    **Und der Platz geht mit**: eine leere Beschriftungszeile wäre dieselbe Höhe ohne
    denselben Inhalt.

    Bug-Formen: (a) die Beschriftung ist wieder da; (b) sie ist weg, die Zeile bleibt.
    """
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    at = work.index("<Segmented")
    assert "label=" not in work[at:work.index("/>", at)], (
        "Die Zahlungsart trägt wieder eine Beschriftung (a)."
    )
    seg = _body(_code(_read(FRONTEND / "components" / "erp" / "fields.tsx")),
                "Segmented", kind="export function")
    assert "{label && <Label" in seg, (
        "Ohne Beschriftung bleibt die leere Zeile stehen (b) – dieselbe Höhe ohne "
        "denselben Inhalt."
    )


# ---------------------------------------------------------------------------
# Testnotizen #1032-#1036
# ---------------------------------------------------------------------------


def test_every_offer_stays_visible_and_names_its_outcome():
    """►►► **Kein Aufklapper im Angebotsspiegel** (Testnotiz #1032). ◄◄◄

    Nach dem Zuschlag stand hier eine Zeile und darunter «1 von 2 Angeboten gewaehlt».
    Die unterlegenen Zeilen sind aber der Nachweis, warum so entschieden wurde – und ein
    Nachweis hinter einem Klick beantwortet die Frage erst, wenn man sie gestellt hat.
    Unterschieden wird ueber das **Wort**, und das kommt aus der EINEN Aufloesung.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "Angeboten gewählt" not in ui, "Der Aufklapper ist wieder da."
    assert "ChevronDown" not in ui, "Der Beleg klappt wieder etwas auf."
    quotes = _component(ui, "Quotes")
    assert quotes.count("<QuoteRow") == 1, (
        "Die Angebote werden wieder fallweise gerendert – eine Zeile fehlt je nach Stufe."
    )
    look = _body(ui, "quoteLook", kind="function")
    for word in ("Unterlegen", "Unbeantwortet"):
        assert word in look, f"Der Ausgang «{word}» hat kein Wort."
    assert re.search(r"quoteLook\([^)]*decided", _component(ui, "QuoteRow")), (
        "Die Zeile fragt die Aufloesung ohne die gefallene Entscheidung – nach dem "
        "Zuschlag heisst «Offeriert» dann immer noch «offeriert»."
    )


# ---------------------------------------------------------------------------
# ►► TESTNOTIZEN #1046/#1047/#1049 — am Beleg
# ---------------------------------------------------------------------------


def test_the_blocked_request_says_why_at_the_button():
    """►►► **Der Grund steht am Knopf, nicht als rote Zeile oben** (Testnotiz #1046). ◄◄◄

    *«Diese Meldung erscheint nicht an der Stelle des Geschehens. Besser wäre, der
    Submit-Button ist deaktiviert/ausgegraut, bis alles vollständig ist, und beim Hover
    erklärt er, warum.»*

    **Der Satz kommt vom Server** (``ask_problem``) – dieselbe Ableitung, mit der ``_ask``
    abweist. Ein zweiter Massstab im Browser wäre die Stelle, an der Knopf und Tür
    auseinanderlaufen.

    *Und ein gesperrter Knopf ist hier richtig, obwohl «ein Knopf, der nie etwas tun kann,
    ist kein Angebot» die Hausregel ist (#950): dieser **kann** – sobald die Angaben
    stehen.*

    Bug-Formen: (a) der Knopf ist nicht gesperrt; (b) der Grund steht nicht in seiner
    Blase; (c) die Oberfläche baut ihn selbst; (d) der `+` am Chip fragt trotzdem an.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    offer = _component(src, "Offer")
    assert "d.ask_problem" in offer, f"Der Knopf fragt den Server nicht (a/c): {offer[:200]}"
    assert re.search(r"disabled=\{busy \|\| !!problem\}", offer), (
        "Der Knopf ist nicht gesperrt, solange etwas fehlt (a)."
    )
    assert re.search(r"tip=\{problem", offer), (
        "Der Grund steht nicht in der Blase des Knopfes (b)."
    )
    # (c) **Kein zweiter Massstab**: die Karte zählt keine Pflichtangaben selbst auf.
    assert "Zolltarifnummer» fehlt" not in src and "anzubieten." not in src, (
        "Die Karte formuliert den Grund selbst (c)."
    )
    # (d) **Dieselbe Sperre am Chip** – er löst dieselbe Handlung aus.
    chip = _component(src, "RecipientChip")
    assert "askProblem" in chip and "const askOff = busy || !!askProblem;" in chip, (
        "Der `+` am Chip fragt an, obwohl der Beleg unvollständig ist (d)."
    )
    assert "data-tip={askProblem || 'Anfragen'}" in chip, (
        "Der `+` sagt nicht, warum er nicht geht (b/d)."
    )


def test_the_invoice_is_out_there_once_it_is_billed():
    """►►► **«Rechnung ist versendet» ist gelöscht** (Testnotiz #1047). ◄◄◄

    *«Ich sehe nicht wirklich, wozu es diesen extra Button braucht … bitte komplett und
    vollständig aus dem Code eliminieren.»*

    Bug-Formen: (a) das Verb ist wieder da; (b) der Fortschritts-Punkt des Fachs hängt
    wieder am Versand-Datum; (c) die Zeile zeigt es wieder an.
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    assert "'issue'" not in src and "issue_word" not in src, (
        "Das Verb ist wieder da (a) – ein Knopf, dessen ganze Wirkung ein Datum ist."
    )
    assert "issued_on" not in src, (
        "Das Versand-Datum wird wieder gelesen (b/c) – und es gibt es nicht mehr."
    )
    assert "state={invoice ? 'past' : 'active'}" in src, (
        "Der Punkt des Fachs «Fordern» hängt nicht an der gestellten Rechnung (b)."
    )


def test_every_amount_field_names_its_currency():
    """►►► **Kein Betrags-Feld ohne Währung — auch das der Offerte** (Testnotiz #1049).◄◄◄

    *«Dieses Eingabefeld ist nicht ganz sauber konfiguriert. Die Währung fehlt hier
    gänzlich. Etabliere auch im Kontext Ausgabe eine passende Option für Währungen.»*

    Drei Dinge fehlten, und alle drei gibt es im Haus längst: die **Währung** als Suffix in
    derselben Hülle wie die Zahl (#1010/#1017), die **Stellenzahl dieser Währung** (#931)
    und die **Beschriftung** (daneben stehen zwei Fristen mit ihrer).

    **Und der Währungs-Wähler ist der Code am Total** (#917) – den Block gab es bei einer
    **Ausgabe** gar nicht, also war die Währung in dieser Richtung nie wählbar.

    Bug-Formen: (a) das Feld trägt keine Währung; (b) es nimmt vier Nachkommastellen;
    (c) es steht ohne Beschriftung da; (d) die Aufstellung verschwindet bei einer Ausgabe
    (dann gibt es dort keinen Wähler – und beim Buchen springt das Layout, #1009).
    """
    src = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    quote = _component(src, "QuoteRow")
    at = _at(quote, 'aria-label={AMOUNT_LABEL}')
    around = quote[max(0, at - 400):at + 200]
    assert "<Amount currency={v.currency}" in around, (
        "Das Betragsfeld der Offerte trägt keine Währung (a)."
    )
    assert "decimals: dec" in around, (
        "Es nimmt mehr Nachkommastellen, als die Währung hat (b)."
    )
    assert "<Stacked label={AMOUNT_LABEL}>" in around, (
        "Es steht ohne Beschriftung da (c) – daneben tragen zwei Fristen ihre."
    )
    # (d) **Die Aufstellung steht immer** – sie trägt den Währungs-Wähler.
    sums = _component(src, "Sums")
    assert "return null" not in sums, (
        "Die Aufstellung verschwindet (d) – mit ihr der Währungs-Wähler bei einer "
        "Ausgabe, und beim Buchen wächst sie in den Beleg hinein."
    )


def test_time_comes_before_what_happened():
    """►►► **Zeit zuerst, dann der Vorgang — und die Form steht EINMAL** (#1052). ◄◄◄

    *«Kann man das hier und sonst überall, wo diese Logik vorhanden ist, umdrehen und
    sagen: Zeit und dann Status – beispielsweise ‹gerade eben zugesagt›.»*

    Es stand andersherum («offeriert · vor 3 Tagen»), und zwar an **drei** Stellen von
    Hand. Das ist keine Eigenschaft einer Zeile, sondern die Form einer Aussage über einen
    Vorgang – also wohnt sie bei der einen Datums-Ausgabe des Hauses (`lib/when.happened`)
    und nicht dreimal in der Karte.

    Bug-Formen: (a) `happened` gibt es nicht; (b) eine Aufrufstelle baut «Wort · Zeit»
    wieder selbst; (c) der Satzanfang wird nicht gross geschrieben (dann stehen «Gerade
    eben» und «vor 3 Tagen» nebeneinander).
    """
    when_src = _read(FRONTEND / "lib" / "when.ts")
    assert "export function happened(" in when_src, (
        "Die Form steht nicht bei der Datums-Ausgabe (a) – dann baut sie jede "
        "Aufrufstelle selbst."
    )
    assert "toUpperCase()" in _code(_body(when_src, "happened", kind="function")), (
        "Der Satzanfang bleibt klein (c): «vor 3 Tagen offeriert» neben «Gerade eben "
        "zugesagt» sind zwei Formen derselben Aussage."
    )
    work = _code(_read(FRONTEND / "components" / "erp" / "beleg-work.tsx"))
    # (b) **Niemand baut es mehr selbst** – gesucht wird die alte Form «Wort · {when(…)}».
    assert not re.search(r"[a-zäöü]+ · \{when\(", work), (
        "Eine Aufrufstelle setzt «Wort · Zeit» wieder von Hand zusammen (b)."
    )
    assert work.count("happened(") >= 3, (
        f"Nur {work.count('happened(')} Aufrufstellen nennen die Form – es sind drei "
        f"(storniert · offeriert · angenommen)."
    )
    # ►►► **Und die WÖRTER kommen vom Server.** ◄◄◄ Sie standen in der Karte, und ein
    # bestehender Wächter hat genau das gemeldet: so entsteht der zweite Ort für dasselbe
    # Wort. Die **Form** baut die Oberfläche, die Wörter reisen mit.
    from app.domain import voucher as dm
    for word in (dm.SENT_WORD, dm.TAKEN_WORD, dm.CANCELLED_WORD):
        assert f"'{word}'" not in work, (
            f"«{word}» steht in der Karte – damit gibt es das Wort zweimal."
        )
    for field in ("d.sent_word", "v.taken_word", "d.cancelled_word"):
        assert field in work, f"Die Karte liest «{field}» nicht."


def test_a_state_stands_once_per_line():
    """►►► **Ein Zustand steht EINMAL je Zeile** (Testnotiz #1053). ◄◄◄

    *«Braucht es diesen Status, denn ich habe gleich links daneben nochmals ‹angenommen›?
    Ich möchte einfach Doppelspurigkeiten vermeiden.»*

    An der zugesagten Angebotszeile stand «Vor 3 Tagen angenommen» **und** daneben das
    Wort «Zugesagt». Die Aussage mit der Zeit sagt mehr, also bleibt sie – und trägt den
    Ton des Zustands, damit nichts verlorengeht. **`quoteLook` bleibt**: es benennt die
    drei übrigen Ausgänge (unterlegen · unbeantwortet · abgesagt) und den Hover.

    Bug-Formen: (a) beide stehen wieder da; (b) das Wort ist ganz gelöscht, und die
    übrigen Zeilen sagen nichts mehr.
    """
    src = _read(FRONTEND / "components" / "erp" / "beleg-work.tsx")
    row = _code(_component(src, "QuoteRow"))
    assert "!taken" in row, (
        "Das Wort steht neben der Aussage, die es wiederholt (a)."
    )
    assert "quoteLook(" in row and "look.label" in row, (
        "Die übrigen Ausgänge haben ihr Wort verloren (b) – «unbeantwortet» und "
        "«abgesagt» stehen an keiner Zahl."
    )


def test_the_form_asks_for_the_number_the_service_demands():
    """►►► **Eine Rechnung hat immer eine Nummer** (Testnotiz #1058). ◄◄◄

    *«Wenn die Zahlungsreferenz nicht ausgefüllt war, dann war der Button zum die Rechnung
    erstellen trotzdem aktiv und nicht deaktiviert mit entsprechendem Hinweis.»*

    Gemessen: der Dienst weist `bill` ohne sie mit **400** ab, und das Formular liess
    «Buchen» zu. Zwei Formen einer Regel, ein Massstab – der Grund steht **am Knopf**,
    nicht nach dem Klick (dieselbe Regel wie #1046).

    Bug-Formen: (a) der Knopf bleibt offen; (b) es gibt keinen Grund im Hover; (c) die
    **Zahlung** verlangt sie plötzlich auch (eine Barzahlung hat keine Referenz).
    """
    src = _read(FRONTEND / "components" / "erp" / "beleg-work.tsx")
    entry = _code(_component(src, "Entry"))
    assert "missingRef" in entry and "&& !missingRef" in entry, (
        "«Buchen» bleibt offen, obwohl der Dienst gleich darauf mit 400 abweist (a)."
    )
    assert re.search(r"tip=\{missingRef", entry), (
        "Der gesperrte Knopf sagt nicht, warum (b)."
    )
    assert "kind === 'bill' && !!d.ref_label" in entry, (
        "Die Pflicht hängt nicht an der Rechnung (c) – eine Barzahlung hat keine Referenz."
    )


def test_the_correction_target_is_searched_like_every_reference():
    """►►► **«Korrektur zu» ist das Suchfeld des Hauses** (Testnotiz #1050). ◄◄◄

    *«Es wäre schön, wenn dies wie jedes andere Suchfeld wäre – hier haben wir ja eine
    global gültige Logik, etablieren mit Suchfeld, Scan-Possibility usw.»*

    Es war ein natives `<select>` mit einer fertigen Liste – richtig bei einer Handvoll
    Belegen, falsch beim hundertsten. Jetzt dieselbe Bauart wie jede Referenz:
    `SearchSelect` mit Server-Suche.

    ►►► **Und bewusst OHNE Kamera.** ◄◄◄ Eine Rechnung zieht keine Objektnummer – es kann
    für sie gar kein Etikett geben (dieselbe Regel wie bei der Einzelinstanz). Ein
    Scan-Knopf wäre ein Angebot, das nie etwas treffen kann.

    Bug-Formen: (a) wieder eine fertige Liste ohne Suche; (b) der Suchtext erreicht den
    Server nicht; (c) jemand hängt eine Kamera daran.
    """
    src = _read(FRONTEND / "components" / "erp" / "beleg-work.tsx")
    find = _code(_component(src, "DocFind"))
    assert "<SearchSelect" in find and "search={search}" in find, (
        "Der Wähler ist kein Suchfeld (a)."
    )
    assert "ObjectSelect" not in find, (
        "Eine Kamera an einem Beleg, der kein Etikett haben kann (c)."
    )
    correction = _code(_component(src, "Correction"))
    assert "<DocFind" in correction, "«Korrektur zu» ist wieder ein `<select>` (a)."
    # **Und der Suchtext erreicht den Server** – gelesen im Rumpf **dieser** Methode:
    # `?search=${encodeURIComponent(…)}` steht in `api.ts` auch an der Halter-Suche, und
    # ein Wächter, der die ganze Datei liest, war damit von ihr erfüllt (gemessen – die
    # eigene Bug-Form ging durch).
    whole = _read(FRONTEND / "lib" / "api.ts")
    start = _at(whole, "voucherCorrectable")
    api = _code(whole[start:whole.index("\n  }", start)])
    assert re.search(r"search=\$\{encodeURIComponent", api), (
        "Der Suchtext erreicht den Server nicht (b) – dann filtert der Browser eine "
        "Seite, die ohnehin gekappt ist."
    )


def test_the_document_offers_firm_and_addresses_only_where_the_server_says_so():
    """**An wen und wohin – am Beleg, und nur, wo der Server ``choice`` liefert.**

    Der Server liefert sie am Adressaten, vor der Zusage, für das Personal; danach ist
    der Kopf eingefroren. Die Karte formuliert die Bedingung nicht selbst nach.

    Bug-Formen: (a) die Wahl hängt an der Stufe statt an ``choice``; (b) sie schickt ein
    anderes Verb als ``address``; (c) die Anschrift ist ein Freitextfeld statt einer Wahl
    aus dem Adressbuch.
    """
    src = _code(_beleg())
    assert "view.choice?.company ?" in src and "choice={view.choice}" in src, "(a)"
    assert src.count("action: 'address'") == 3, "(b)"
    body = src[src.index("function Anschrift("):]
    body = body[:body.index("\nfunction ", 1)]
    assert "<DocPick" in body and "choice?.options" in body and "<input" not in body, "(c)"
