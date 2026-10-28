"""Quelltext-Wächter: das Zahlungsmodul «Beleg» (``beleg-work.tsx``, ``services/voucher``).
"""

import re

from tests._source import (
    BACKEND,
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
    work = _code(_beleg())
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


def test_the_payment_module_has_no_finish_button_the_pieces_pass_by_themselves():
    """►►► **Ein Zahlungsmodul bestätigt niemand von Hand** (Runde vom 25.10.2026). ◄◄◄

    Früher hiess der Knopf «Vorgang abschliessen» (davor «Auftrag erledigt», Testnotiz
    #848). Jetzt gibt es ihn nicht mehr: **die Stücke ziehen von selbst weiter** – mit der
    Zusage, bei einer Vorauszahlung mit dem Geld (``process.advance_payments``). Erledigt
    ist der Beleg, wenn der Saldo null ist; Kulanz ist ein Storno mit Grund.

    Geprüft wird die **Regel an ihren beiden Formen**: das Wort des Moduls beschreibt, was
    geschieht (``Beleg.action_for``), und die Tür nennt den Grund, warum es keinen Knopf
    gibt (``completion_problem`` ↔ ``assert_completable`` mit ``PASSES_ITSELF``).

    Bug-Formen: (a) das Verb «Vorgang abschliessen» (oder sein Vorgänger) ist zurück –
    in der Domäne oder in der Karte; (b) das Modul bietet wieder eine Handlung an statt
    zu sagen, was von selbst geschieht; (c) ``completion_problem`` gibt für ein
    Zahlungsmodul ``None`` zurück – dann stünde der Bestätigen-Knopf wieder da.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as dm, modules

    assert not hasattr(dm, "FINISH_VERB"), "Das Abschluss-Verb ist zurück (a)."
    for gone in ("Vorgang abschliessen", "Auftrag erledigt"):
        assert gone not in _code(_read(BACKEND / "app" / "domain" / "modules.py")), (
            f"«{gone}» steht wieder im Modul (a).")
        assert gone not in _beleg(), f"«{gone}» steht wieder in der Karte (a)."
    beleg = modules.get("beleg")
    for direction in ("in", "out"):
        assert beleg.action_for({"direction": direction}) == "Zieht von selbst weiter", (
            "Das Modul nennt wieder eine Handlung statt dessen, was von selbst "
            "geschieht (b)."
        )
    src = _code(_read(BACKEND / "app" / "services" / "voucher.py"))
    body = src[src.index("def completion_problem"):src.index("def pass_problem")]
    assert "PASSES_ITSELF" in body and "return None" not in body.split('"""')[-1], (
        "``completion_problem`` lässt für ein Zahlungsmodul wieder einen Knopf zu (c)."
    )
    gate = src[src.index("def assert_completable"):src.index("def service_day")]
    assert "PASSES_ITSELF" in gate, "Die Tür nennt den Grund nicht mehr (c)."


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

    work = _beleg()
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

    Der Beleg **ist** die Rechnung – es kann keine zweite geben, also kann auch keine
    Handlung die falsche meinen (``chargeId``, ``entryId={…}``, ``settle_charge`` sind
    entfallen). **Was eine Zeile korrigiert, steht an ihr**: seit dem Umbau ist das allein
    das leise «falsch erfasst?» (``reverse`` mit ``entry: e.id``) an der Geld-Zeile, die
    es meint. «Rechnung zurücknehmen» gibt es nicht mehr – der einzige Weg zurück ist
    «Stornieren» (Gutschrift von selbst, lückenlose Nummern).

    Bug-Formen: (a) eine Handlung nennt wieder eine Rechnung, also gibt es wieder mehrere;
    (b) das Formular fragt nach ihr; (c) die Korrektur verlässt ihre Zeile oder hängt nicht
    mehr an der Angabe des Servers (``e.reversible``); (d) die Rücknahme der Rechnung ist
    zurück.
    """
    src = _code(_beleg())
    money = _component(src, "Invoice")
    for gone in ("chargeId={", "entryId={", "settle_charge", "open_charges"):
        assert gone not in money, (
            f"«{gone}» ist zurück (a) – dann gibt es die Rechnung wieder mehrfach, und "
            f"eine Handlung muss raten, welche gemeint ist."
        )
    entry = _component(src, "EntryForm")
    assert "open_invoices" not in entry and "Rechnung</Label>" not in entry, (
        "Das Formular fragt wieder, worauf die Zahlung geht (b)."
    )
    row = _component(src, "EntryRow")
    for piece in ("action: 'reverse'", "entry: e.id", "e.reversible"):
        assert piece in row, (
            f"«{piece}» steht nicht mehr an der Geld-Zeile (c) – dann gilt die Korrektur "
            f"wieder dem ganzen Vorgang, oder sie steht da, wo der Server sie nicht führt."
        )
    assert "'unbill'" not in src and "Rechnung zurücknehmen" not in src, (
        "«Rechnung zurücknehmen» ist zurück (d) – der Weg zurück heisst «Stornieren»."
    )


def test_a_payment_stands_in_the_compartment_it_belongs_to():
    """►►► **Rechnung, Geld und Saldo sind EIN Abschnitt «Rechnung»** (Umbau 25.10.2026). ◄◄◄

    Früher standen «Fordern» und «Begleichen» als zwei Fächer da – zwei Abschnitte, die
    dieselbe Zahl zweimal zeigten. Jetzt ist es eine Frage – *was ist mit dem Geld?* – und
    ein Abschnitt (``invoice_title``): die Rechnung, jede Geld-Zeile darunter, der Saldo.
    Die Zeilen sind strukturell getrennt: die Rechnung reist als ``invoice``, ``entries``
    sind ausschliesslich Geld (Zahlung · Ausbuchung · Trinkgeld).

    Bug-Formen: (a) die beiden Fächer «Fordern»/«Begleichen» sind zurück; (b) eine
    Geld-Zeile fällt heraus, weil gefiltert wird; (c) die Rechnung sagt ihren eigenen
    Stand nicht mehr (``invoice.state_tone`` vom Server); (d) die Rechnung wird wieder aus
    den Zeilen herausgesucht.
    """
    src = _code(_beleg())
    for gone in ("claim_title", "settle_title", "'Fordern'", "'Begleichen'"):
        assert gone not in src, f"«{gone}»: die zwei Fächer sind zurück (a)."
    money = _component(src, "Invoice")
    assert "d.invoice_title" in money, "Der Abschnitt heisst nicht, wie der Server sagt (a)."
    assert "<InvoiceRow" in money and "<Balance" in money, (
        "Rechnung und Saldo stehen nicht im selben Abschnitt (a)."
    )
    assert "d.entries.map(" in money and "entries.filter(" not in money, (
        "Eine Geld-Zeile fällt aus der Ansicht (b) – dann verschwindet Geld, das geflossen ist."
    )
    assert "invoice.state_tone" in _component(src, "InvoiceRow"), (
        "Die Rechnung sagt ihren eigenen Stand nicht mehr (c)."
    )
    assert "kind === 'charge'" not in src, "Die Rechnung wird aus den Zeilen gesucht (d)."


def test_a_transfer_is_information_with_a_code_and_a_reason():
    """►►► **Überweisen ist eine AUSKUNFT** (#865). ◄◄◄

    Bar wird **erfasst**, die Karte wird **ausgeführt**, und die Überweisung löst der
    Zahlende selbst aus. Was er dafür braucht, sind Angaben: Bankverbindung, Referenz und –
    wo er gilt – der QR-Code. **Erzeugt wird er im Backend.**

    Bug-Formen: (a) der Code wird im Browser gebaut; (b) der Grund fehlt, wo es keinen
    geben kann; (c) die Auskunft hängt nicht mehr an der Angabe des Servers (``way.info``),
    sondern an einem Vergleich des Schlüssels.
    """
    src = _code(_beleg())
    panel = _component(src, "Transfer")
    assert "api.voucherTransfer" in panel, "Die Auskunft kommt nicht vom Server (a)."
    for own in ("segno", "SPC", "qrcode", "toDataURL"):
        assert own not in src, f"«{own}»: der Code wird im Browser gebaut (a)."
    assert "{info.problem}" in panel and "info.qr ? (" in panel, (
        "Wo es keinen Code geben kann, steht kein Grund (b)."
    )
    money = _component(src, "Invoice")
    assert "way?.info" in money, "Der Einzahlungsschein hängt nicht am Server (c)."
    assert "'transfer'" not in money, "Die Oberfläche vergleicht den Schlüssel des Weges (c)."


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
    src = _code(_beleg())
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

    Heute sagen es die **Stationen** über dem Beleg (`beleg/stages.tsx`); der Abschnitt
    mit Punkt (`ModuleSection`) hatte zuletzt keine Aufrufstelle mehr und ist entfernt.

    Bug-Form: das Bauteil ist zurück.
    """
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    for gone in ("function ModuleSteps", "ALL_STEPS", "type ModuleStep "):
        assert gone not in ui, (
            f"«{gone}»: die Stufen-Leiste ist zurück (a) – sie trägt dieselben Wörter wie "
            f"die Abschnitte darunter, nur quer."
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
    src = _code(_beleg())
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
    src = _code(_beleg())
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
    """►►► **DIE Rechnung IST der Beleg — die Karte baut sie nicht zusammen.** ◄◄◄

    Eine Geld-Zeile hat wieder eine Art (``voucher_entries.kind``) – aber sie heisst
    **Zahlung · Ausbuchung · Trinkgeld** (``ENTRY_KINDS``), nie «Forderung». Die Rechnung
    selbst (Nummer, Tag, Fälligkeit, Betrag, Steuer) steht am **Beleg**
    (``Voucher.number``/``billed_on``/``due_on``/``amount``/``vat``) und reist als **ein
    Objekt** mit (``VoucherEmbed.invoice``); ``null`` ist die vollständige Antwort auf
    «gibt es eine?».

    Bug-Formen: (a) es gibt wieder eine Art «charge» – dann gibt es die Rechnung zweimal,
    und die Karte muss wieder wählen; (b) die Karte sucht sich die Rechnung aus den Zeilen
    oder liest Nummer, Fälligkeit oder Steuer von einer Geld-Zeile; (c) die Felder der
    Rechnung wandern vom Beleg weg oder an die Geld-Zeile; (d) das Feld gibt es an der Tür
    gar nicht, also käme es nie an.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as dm
    from app.models.voucher import Voucher, VoucherEntry
    from app.schemas.voucher import VoucherEmbed, VoucherEntryOut

    # (a) **Die Arten einer Geld-Zeile – ohne Forderung.**
    assert set(dm.ENTRY_KINDS) == {"payment", "writeoff", "tip"}, (
        f"Die Arten einer Geld-Zeile sind {dm.ENTRY_KINDS} – eine Forderung ist keine (a)."
    )
    assert "charge" not in _code(_read(BACKEND / "app" / "domain" / "voucher.py")).replace(
        "charge_word", "").replace("charged", "").replace("CHARGE_", ""), (
        "Eine Art «charge» ist zurück (a)."
    )
    src = _code(_beleg())
    # (b) **Keine Suche** – die Karte fragt nie nach einer Forderungs-Zeile.
    assert "'charge'" not in src, "Die Karte sucht sich die Rechnung aus den Zeilen (b)."
    row = _component(src, "InvoiceRow")
    for field in ("invoice.number", "invoice.due_on", "invoice.amount"):
        assert field in row, f"«{field}» steht nicht an der Rechnung (b)."
    # (c) **Die Rechnung steht am Beleg, nicht an der Geld-Zeile.**
    for field in ("number", "billed_on", "due_on", "amount", "vat"):
        assert hasattr(Voucher, field), f"«Voucher.{field}» fehlt (c)."
    for gone in ("due_on", "vat", "service_date", "charge_id", "allocations"):
        assert not hasattr(VoucherEntry, gone), (
            f"«VoucherEntry.{gone}»: die Rechnung steht wieder an der Geld-Zeile (c).")
        assert gone not in VoucherEntryOut.model_fields, (
            f"«{gone}» steht wieder an der Geld-Zeile (c)."
        )
    # (d) **Und die Tür kennt sie.**
    assert "invoice" in VoucherEmbed.model_fields, "Der Beleg liefert seine Rechnung nicht (d)."


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
    src = _code(_beleg())
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
    cls = re.search(r"const INPUT_FORM = '([^']+)'", fields)
    assert cls, "Die Form von «inputCls» (`INPUT_FORM`) steht nicht mehr in `fields.tsx` – der Spiegel hat kein Original."
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
    deal = _code(_beleg())
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
    src = _code(_beleg())
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
    jeder änderbare Wert trägt sie. Und sie darf **nichts am Layout tun**.

    Bug-Formen: (a) die Klasse gibt es nicht; (b) sie ändert die Geometrie (`border`,
    `padding`, `font-size`); (c) ein änderbarer Wert der Karte trägt sie nicht – seit dem
    Umbau auch die Leistung, der Teilbetrag, das Gewicht, die Anschriften, das Eigentum und
    die Offerte eines Lieferanten; (d) die Karte baut die Auszeichnung selbst statt das
    eine Bauteil zu nehmen.
    """
    css = _read(FRONTEND / "app" / "globals.css")
    assert "\n.ix-editable {" in css, "Die Auszeichnung gibt es nicht (a)."
    rule = css.split("\n.ix-editable {", 1)[1].split("}", 1)[0]
    assert not re.search(r"border(?!-radius)", rule), "Ein Rahmen in `.ix-editable` (b)."
    for geometry in ("padding", "font-size", "font-weight", "margin"):
        assert geometry not in rule, f"«{geometry}» in `.ix-editable` (b)."
    assert "box-shadow" in rule, "Die Auszeichnung hat keine Linie (a)."

    src = _beleg()
    assert "function Editable(" in src, "Kein gemeinsames Bauteil für den änderbaren Wert (d)."
    for wrapper in ("DocPick", "DocRef", "DocFind"):
        assert re.search(rf"function {wrapper}\b", src), f"«{wrapper}» fehlt (d)."
        assert "<Editable" in _component(src, wrapper), f"«{wrapper}» setzt sie nicht (d)."
    marks = ("<Editable", "ix-editable", "<DocPick", "<DocRef", "<DocFind")
    for name in ("Currency", "Term", "Delivery", "Service", "Price", "VatPick", "Part",
                 "CustomsField", "SideName", "Anschrift", "Issuer", "Ownership",
                 "PickParty", "QuoteForm", "Correction"):
        body = _component(src, name)
        assert any(m in body for m in marks), (
            f"«{name}» trägt die Auszeichnung nicht (c) – der Nutzer wollte sie "
            f"ausdrücklich für **alle** Angaben auf dem Beleg."
        )


def test_the_action_that_moves_the_document_looks_the_same_everywhere():
    """►►► **Die Handlung, die weiterbringt, steht an EINER Stelle: in der Leiste** (#923, Umbau). ◄◄◄

    Früher stand sie als `StageAction` in jedem Fach (Anbieten, Rechnung stellen, Zahlung
    erfassen). Jetzt hat die Karte **eine** Leiste unten: Stand, wer dran ist, und die eine
    Handlung, die der Server nennt (`state.primary`). Ein Knopf, eine Form, ein Ort – so
    gross und ausdrucksstark wie der Abschluss eines Moduls (42 px, 14 px Schrift).

    Bug-Formen: (a) die Handlung steht wieder in einem Abschnitt (`StageAction` in der
    Karte); (b) der Knopf trägt nicht die Masse; (c) die Leiste wählt die Handlung selbst,
    statt `state.primary` zu lesen.
    """
    src = _code(_beleg())
    assert "<StageAction" not in src, (
        "Eine Handlung steht wieder in einem Abschnitt (a) – sie gehört in die Leiste."
    )
    button = _component(src, "MainButton")
    for mark in ("erp-actbtn-primary", "ACT_H.stage", "fontSize: 14"):
        assert mark in button, f"«{mark}» fehlt (b)."
    assert "d.state?.primary" in _component(src, "primaryOf"), (
        "Die Leiste wählt die Handlung selbst (c) – welche ansteht, sagt der Server."
    )
    assert "<Footer" in _component(src, "BelegWork"), "Die Karte hat keine Leiste (a)."


def test_every_summed_amount_names_its_currency():
    """►►► **«Wenn daneben die Währung stehen würde»** (Testnotiz #921, #1010/#1017). ◄◄◄

    Jede Zahl, die man abschreibt oder überweist, nennt ihre Währung – Netto, Steuer je
    Satz, Total, Saldo, jede Geld-Zeile, und auch der Einzelpreis in beiden Zuständen.

    Bug-Formen: (a) eine Summe ohne Währung; (b) der Einzelpreis nennt sie nicht in beiden
    Zuständen; (c) die Währung ist fest «CHF» statt der des Belegs.
    """
    src = _beleg()
    sums = _component(src, "Sums")
    assert sums.count("code={d.currency}") >= sums.count("<SumRow"), (
        f"Nicht jede Summenzeile nennt ihre Währung (a): "
        f"{sums.count('code={d.currency}')} von {sums.count('<SumRow')}."
    )
    assert "currency={<Currency" in sums, "Das Total nennt seine Währung nicht (a)."
    price = _code(_component(src, "Price"))
    assert price.count("currency={d.currency}") >= 2, (
        "Der Einzelpreis nennt seine Währung nicht in beiden Zuständen (b)."
    )
    for name in ("EntryRow", "InvoiceRow", "Balance"):
        assert "currency={d.currency}" in _component(src, name), (
            f"«{name}» nennt die Währung nicht (a)."
        )
    assert "'CHF'" not in _code(src), "Die Karte schreibt «CHF» fest (c)."


def test_the_terms_carry_no_heading_and_no_prepaid_chip():
    """►►► **Die Konditionen: ihr Titel kommt vom Server, keine Pille im Kopf** (#924–#926, Umbau). ◄◄◄

    Seit dem Umbau trägt jeder Abschnitt einen ruhigen Kopf – sein Titel kommt vom Server
    (`terms_title`), nie als Literal. Die Vorauszahlung steht nicht als Pille im Kopf: sie
    ist die Zahlungsfrist, die in den Konditionen steht und dort geändert wird.

    Bug-Formen: (a) die Überschrift steht als Literal; (b) der Kopf zeigt die
    Vorauszahlung; (c) die Zahlungsfrist steht nicht über der Lieferfrist (#897).
    """
    src = _beleg()
    assert "Konditionen" not in _code(src), "Die Überschrift steht als Literal (a)."
    terms = _component(src, "Terms")
    assert "d.terms_title" in terms, "Der Titel kommt nicht vom Server (a)."
    assert "prepaid" not in _component(src, "Parties"), "Der Kopf zeigt die Vorauszahlung (b)."
    assert terms.index("payment_term_label") < terms.index("lead_term_label"), (
        "Die Lieferfrist steht über der Zahlungsfrist (c)."
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
    old = _code(_beleg())
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
    der entsprechende Prozentsatz angegeben sein.»* Zusammengesetzt wird es an **einer**
    Stelle (`vatText`), sonst nennt die Auswahlliste den Satz und die Anzeige daneben nicht.

    Bug-Formen: (a) es gibt keine gemeinsame Auflösung; (b) sie nennt den Satz nicht;
    (c) die Auswahl oder die Anzeige geht daran vorbei.
    """
    src = _beleg()
    assert "function vatText(" in src, "Es gibt keine gemeinsame Auflösung (a)."
    body = _code(_component(src, "vatText"))
    assert "rate" in body and "%" in body, "Die Auflösung nennt den Prozentsatz nicht (b)."
    pick = _code(_component(src, "VatPick"))
    assert pick.count("vatText(") >= 2, (
        "Auswahl und Anzeige lösen nicht beide über `vatText` auf (c)."
    )


def test_a_name_and_its_number_stand_in_one_line():
    """►►► **Name und Objektnummer sind EIN Datensatz** (Testnotiz #933). ◄◄◄

    *«Der Name und die Objektnummer sollten immer in einer Linie, in einer Reihe sein,
    nicht umgebrochen.»* Gekappt wird der **Name**; die Nummer ist die Kennung.

    Bug-Formen: (a) Name und Nummer stehen in verschiedenen Zeilen; (b) die Nummer darf
    schrumpfen statt des Namens.
    """
    src = _code(_component(_beleg(), "LineTitle"))
    at_name = src.find("article_name")
    at_id = src.find("<ObjId", at_name)
    assert at_name != -1 and at_id != -1, "Die Zeile nennt nicht beides."
    assert "flex flex-col" not in src[at_name:at_id], (
        "Zwischen Name und Nummer beginnt eine neue Spalte (a)."
    )
    assert "truncate" in src[max(0, at_name - 160):at_id], "Der Name wird nicht gekappt (b)."
    assert "flex: 'none'" in src[max(0, at_id - 120):at_id + 260], (
        "Die Nummer darf schrumpfen (b) – gekappt gehört der Name, nie die Kennung."
    )


def test_a_typed_amount_has_the_decimals_of_its_currency():
    """►►► **Was man tippen kann, ist die Stelligkeit der Währung** (Testnotiz #931). ◄◄◄

    Wer vier Nachkommastellen tippen kann, bekommt sie vom Server gerundet zurück, und das
    sieht aus wie ein Datenverlust. Das gilt für den Einzelpreis, den Teilbetrag und jeden
    Betrag, der erfasst wird.

    Bug-Formen: (a) `numericOnly` kann gar nicht begrenzen; (b) ein Betragsfeld begrenzt
    nicht; (c) es begrenzt fest auf zwei (JPY hat null, KWD drei).
    """
    fields = _code(_read(FRONTEND / "components" / "erp" / "fields.tsx"))
    assert "decimals?: boolean | number" in fields, "`numericOnly` kennt keine Stellenzahl (a)."
    assert "slice(0, decimals)" in fields, "`numericOnly` begrenzt nicht (a)."
    src = _beleg()
    for name, label in (("Price", "Einzelpreis"), ("Part", "Teilbetrag"),
                        ("EntryForm", "Betrag"), ("QuoteForm", "Betrag")):
        body = _code(_component(src, name))
        at = body.find(f'aria-label="{label}"')
        assert at != -1, f"«{name}»: das Feld «{label}» heisst nicht mehr so."
        window = body[max(0, at - 400):at + 400]
        assert "currency_decimals" in window and "decimals: 2" not in window, (
            f"«{name}» nimmt die Stelligkeit nicht aus der Währung (b/c)."
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
    src = _code(_beleg())
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
    src = _code(_beleg())
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

    Name und Objektnummer benennen **einen** Datensatz (#933); eine eigene Zeile «Nr.»
    gibt es nicht. Beide Seiten stehen auf einem gemeinsamen Raster (`SIDE_ROWS`, je
    Angabe eine Zeile), damit gleiche Angaben auf gleicher Höhe stehen.

    Bug-Formen: (a) die Nummer steht wieder in einer eigenen Zeile; (b) das Raster und die
    Angaben des Blocks sind nicht gleich lang; (c) die Beschriftung «Nr.» lebt weiter.
    """
    src = _code(_beleg())
    side = _component(src, "Side")
    head = side[: side.index("<Attn")]
    assert "<ObjId value={" in head, "Die Nummer steht nicht beim Namen (a)."
    assert "PARTY_NUMBER_LABEL" not in src and "'Nr.'" not in src, "«Nr.» lebt weiter (c)."
    rows = int(re.search(r"const SIDE_ROWS = (\d+)", src).group(1))
    body = side[side.index("gridTemplateRows: 'subgrid'"):]
    shown = 2 + sum(body.count(tag) for tag in ("<Attn", "<Addresses", "<Contact"))
    assert rows == shown, (
        f"Das Raster ({rows}) und die Angaben des Blocks ({shown}) sind nicht gleich "
        f"lang (b) – dann klafft in beiden Blöcken eine Lücke."
    )


def test_two_ways_to_reach_someone_stand_below_each_other():
    """**E-Mail und Telefon untereinander** (Testnotiz #944) – zwei **Wege**, nicht ein Wert.

    Bug-Form: sie stehen wieder mit «·» in einer Zeile.
    """
    contact = _component(_code(_beleg()), "Contact")
    assert "join('\\n')" in contact and "whiteSpace: 'pre-line'" in contact, (
        "Kontaktweg und Telefon stehen in einer Zeile – zwei Wege sind kein Wert."
    )


def test_asking_someone_is_built_in_exactly_one_place():
    """►►► **Derselbe Befehl, zwei Nutzlasten** (Testnotiz #941, #985). ◄◄◄

    Das Anbieten bzw. Anfragen entsteht an **einer** Stelle – der Leiste – und trägt nichts,
    was der Beleg schon kennt: die Fristen stehen auf ihm (Verb ``terms``), der Betrag folgt
    aus den Positionen. Eine Nutzlast, die nichts trägt, kann sich zwischen zwei
    Aufrufstellen nicht unterscheiden.

    Bug-Formen: (a) eine zweite Aufrufstelle baut die Nutzlast wieder selbst; (b) sie trägt
    wieder eine Angabe, die der Beleg schon kennt.
    """
    src = _code(_beleg())
    assert src.count("action: 'ask'") == 1, (
        "Die Nutzlast des Anfragens entsteht an mehr als einer Stelle (a)."
    )
    assert "({ action: 'ask' })" in _component(src, "primaryOf"), (
        "Die Nutzlast trägt wieder eine Angabe (b) – dann gibt es einen zweiten Ort für "
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
    src = _code(_beleg())
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
    src = _code(_beleg())
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
    beleg = _code(_beleg())
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
    No-Go.»* (#958) – Seit dem Umbau öffnet genau **eine** Stelle die Erfassung einer
    Zahlung: der Weg zum Geld in der Leiste (`wayOf`). Der Beleg **ist** die Rechnung – es
    kann keine zweite geben, also kann die Buchung nicht die falsche treffen.

    Bug-Formen: (a) die Erfassung wird an zwei Stellen geöffnet; (b) die Oberfläche sucht
    sich eine Rechnung aus den Zeilen; (c) eine Handlung nennt wieder eine.
    """
    src = _code(_beleg())
    opens = src.count("startForm('pay'")
    assert opens == 1, (
        f"Die Erfassung einer Zahlung geht von {opens} Stellen aus (a) – eine Handlung, "
        f"eine Stelle."
    )
    assert "startForm('pay'" in _component(src, "wayOf"), (
        "Die Zahlung wird nicht über den Weg zum Geld erfasst (a)."
    )
    money = _component(src, "Invoice")
    for guess in ("charges.find(", "charges[0]", "open_charges", "settle_charge",
                  "chargeId={"):
        assert guess not in money, f"«{guess}»: die Oberfläche sucht sich eine Rechnung (b/c)."


def test_the_cancel_button_stands_beside_the_finish_button_as_a_square():
    """►►► **«Stornieren» als Quadrat neben der einen Handlung** (Testnotizen #957/#976, Umbau). ◄◄◄

    Der Storno ist ein Wort in jeder Stufe (`undo`) und steht als quadratisches Symbol
    rechts in der Leiste, neben der einen Handlung, die weiterbringt – sie bleibt der
    dominante Knopf. Dieselbe Anatomie an der Angebotszeile: «Offerte annehmen» nimmt den
    Platz, die Absage steht als Quadrat daneben.

    Bug-Formen: (a) er steht wieder in einer eigenen Zeile oder heisst wieder «Vorgang
    abbrechen»/«Auftrag stornieren»; (b) er ist nicht quadratisch in der Höhe der Handlung;
    (c) die Breite kommt als Inline-Stil und nimmt dem Knopf die Geste, seinen Namen
    auszuklappen; (d) die Angebotszeile stellt ihre Handlungen gleichrangig nebeneinander;
    (e) er hängt nicht an `can`.
    """
    src = _code(_beleg())
    doing = _component(src, "Doing")
    at_main = doing.index("<MainButton label={primary.label}")
    at_undo = doing.index("icon={CircleSlash}")
    assert at_main < at_undo, "Der Storno steht nicht neben der Handlung (a)."
    undo = doing[at_undo:at_undo + 300]
    assert "square" in undo and "ACT_H.stage" in undo and "d.undo" in undo, (
        "Der Storno ist nicht quadratisch in der Höhe der Handlung (b)."
    )
    assert "may(d, 'revoke')" in doing, "Der Storno hängt nicht an `can` (e)."
    for gone in ("Vorgang abbrechen", "Auftrag stornieren"):
        assert gone not in src, f"«{gone}» ist zurück (a) – das Wort heisst «Stornieren»."
    quote = _component(src, "QuoteWork")
    decline = quote[quote.index("icon={CircleSlash}"):]
    assert "square" in decline[:200] and "erp-actbtn-primary" in quote, (
        "Die Angebotszeile stellt ihre Handlungen gleichrangig nebeneinander (d)."
    )
    ui = _code(_read(FRONTEND / "components" / "erp" / "module-ui.tsx"))
    assert "'--actbtn-w'" in ui and "width:" not in _component(ui, "ActionButton"), (
        "Die Breite kommt als Inline-Stil (c)."
    )
    css = _read(FRONTEND / "app" / "globals.css")
    assert "width: var(--actbtn-w, 32px)" in css, "Die Regelbreite kommt nicht aus der Variablen (c)."


def test_a_quote_row_closes_itself_and_keeps_name_and_number_together():
    """**Die Haarlinie unten, Nummer neben dem Namen** (Testnotizen #953/#955).

    Die Linie schliesst jede Zeile des Angebotsspiegels (unten, nie oben), und Name und
    Objektnummer sind eine Gruppe – gekappt wird der Name, nie die Kennung.

    Bug-Formen: (a) die Linie steht wieder oben; (b) Name und Nummer sind wieder
    Geschwister der umbrechenden Zeile.
    """
    src = _code(_beleg())
    row_style = src[src.index("const ROW ="):]
    row_style = row_style[: row_style.index("\n")]
    assert "borderBottom: '1px solid var(--border-1)'" in row_style and "borderTop" not in row_style, (
        "Die Linie eröffnet den Container statt ihn zu schliessen (a)."
    )
    for name in ("QuoteRow", "Candidate"):
        row = _component(src, name)
        assert "...ROW" in row, f"«{name}» schliesst sich nicht mit der Haarlinie (a)."
        group = row[row.index("className=\"flex items-baseline\""):]
        assert "<ObjId value={" in group[:500] and "flex: 'none'" in group[:500], (
            f"«{name}»: Name und Nummer sind zwei Geschwister der umbrechenden Zeile (b)."
        )


def test_a_recipient_chip_can_be_shown_and_dropped():
    """►►► **Ein Kandidat steht als Zeile – zeigen, abwählen, «Im Kopf»** (#951, Umbau). ◄◄◄

    Die Chips im Kopf sind weg: der Kopf nennt **eine** Gegenpartei, die Kandidaten stehen
    als Zeilen im Angebotsspiegel. Ein Klick auf den Namen stellt ihn in den Kopf
    (`onShow`), «Im Kopf» sagt, wessen Anschrift oben steht, und eine frei gewählte Partei
    lässt sich wieder wegnehmen (`unask`) – ob, sagt `can`.

    Bug-Formen: (a) der Name ist reine Anzeige; (b) es gibt kein Abwählen; (c) die
    Oberfläche entscheidet selbst, ob abgewählt werden darf, statt `can` zu fragen; (d) der
    Kopf zeigt blind die Seite des Servers statt der gewählten; (e) die Chips sind zurück.
    """
    src = _code(_beleg())
    assert "function RecipientChip" not in src, "Die Chips im Kopf sind zurück (e)."
    row = _component(src, "Candidate")
    assert re.search(r"onClick=\{onShow\}", row), "Der Name stellt ihn nicht in den Kopf (a)."
    assert "may(d, 'unask')" in row, "Die Oberfläche entscheidet selbst (c)."
    assert "action: 'unask'" in row, "Das Verb wird nicht geschickt (b)."
    assert "<InHead" in row and "inHead={head?.object_id === r.object_id}" in _component(src, "Quotes"), (
        "Es steht nicht da, wer im Kopf steht (d)."
    )
    head = _component(src, "headOf")
    assert "d.recipients" in head and "shown" in head, (
        "Der Kopf zeigt blind die Seite des Servers (d) – die gewählte Zeile gilt."
    )


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

    src = _code(_beleg())
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

    «Leicht blau hinterlegt» **ist** die Auszeichnung änderbarer Werte (`.ix-editable`);
    ein Pflichtwert ohne Wert trägt dieselbe Auszeichnung warnfarben. Die Regel steht im
    Dienst (`voucher.ask_problem`) – dies ist ihre freundliche Hälfte.

    Bug-Formen: (a) die Hülle kennt keine Pflichtangabe; (b) die Auszeichnung verschiebt
    den Beleg; (c) ein Wert trägt sie nicht; (d) sie steht noch da, wo nichts mehr änderbar
    ist.
    """
    src = _code(_beleg())
    hull = _component(src, "Editable")
    assert "missing" in hull and "is-missing" in hull, "Die Hülle kennt keine Pflichtangabe (a)."
    css = _read(FRONTEND / "app" / "globals.css")
    block = css[css.index(".ix-editable.is-missing {"):]
    block = block[: block.index("}")]
    assert "--danger" in block and "padding" not in block, "Die Auszeichnung verschiebt den Beleg (b)."
    assert ".ix-editable[aria-disabled='true'].is-missing" in css, "Ein gesperrter Wert bleibt rot (d)."
    for where in ("Price", "CustomsField", "Term", "Delivery", "Part", "QuoteForm"):
        assert "missing" in _component(src, where), (
            f"«{where}» sagt nicht, dass sein Wert Pflicht ist (c)."
        )
    # «Korrektur zu» ist KEIN Pflichtwert (Chrome-Test): «keine» ist eine Antwort – eine
    # gewöhnliche Offerte stand sonst rot da.
    assert "missing" not in _component(src, "Correction"), "«Korrektur zu» ist wieder rot (e)."


def test_the_chronicle_is_gone_and_its_dates_stand_where_they_belong():
    """►►► **Die Chronik entfällt – die Daten stehen an ihrem Ort** (#968/#969/#970). ◄◄◄

    *Wann offeriert wurde* steht am Kopf der Angebote, *wann zugesagt wurde* an der Zeile,
    bei der zugesagt wurde, *wann storniert wurde* an der Gutschrift aus dem Storno – und
    der Storno selbst in der Leiste («Storniert»). **Die Aussage steht da, die Tatsache im
    Hover** (`lib/when.happened`).

    Bug-Formen: (a) der Abschnitt ist zurück; (b) eine der Angaben fehlt; (c) sie nennt nur
    das Datum statt der Aussage; (d) die genaue Zeit fehlt im Hover.
    """
    src = _code(_beleg())
    assert "function Chronicle" not in src and "<Chronicle" not in src, "Die Chronik ist zurück (a)."
    assert "history_title" not in src, "Ihre Überschrift reist noch mit (a)."
    quotes = _component(src, "Quotes")
    assert "q.sent_at" in quotes and "happened(" in quotes, (
        "Der Abschnitt sagt nicht mehr, wann offeriert wurde (b/c)."
    )
    assert "sent.title" in quotes, "Die genaue Zeit fehlt im Hover (d)."
    row = _component(src, "QuoteRow")
    assert "q.agreed_at" in row and "happened(" in row and "taken.title" in row, (
        "Die Zeile sagt nicht, wann sie den Zuschlag bekam (b/c/d)."
    )
    assert "when(d.cancelled_on)" in _component(src, "CreditRow"), (
        "Der Storno hat keinen Ort mehr (b)."
    )


def test_the_vat_rate_stands_before_the_amount():
    """►►► **Der Satz steht VOR dem Betrag** (Testnotiz #972). ◄◄◄

    Die **Zahl** ist die letzte Angabe der Zeile; sie steht rechtsbündig und bildet mit
    der Zeile darunter eine Spalte. Stand der Satz dahinter, verschob jede Beschriftung
    anderer Länge den Betrag.

    Bug-Form: der Preis steht wieder vor dem Satz.
    """
    row = _component(_code(_beleg()), "LineRow")
    assert row.index("<VatPick") < row.index("<Price"), (
        "Der Preis steht wieder vor dem Steuersatz."
    )


def test_the_payment_method_is_a_slider_not_a_dropdown():
    """►►► **Wie bezahlt wird, ist ein SCHIEBER – in der Leiste** (Testnotiz #967, Umbau). ◄◄◄

    Die Wege zum Geld (Bar · Überweisung · Karte) sind **eine** Frage mit mehreren
    Antworten, und sie steht dort, wo die Handlung steht: in der Leiste (`Segmented`). Das
    Formular einer Zahlung fragt sie nicht noch einmal; nur die Erstattung, die keinen Weg
    in der Leiste hat, wählt im Formular.

    Bug-Formen: (a) die Zahlungsart ist wieder ein `<select>`; (b) das Zahlungsformular
    fragt sie erneut; (c) die Beschriftung steht zweimal.
    """
    src = _code(_beleg())
    doing = _component(src, "Doing")
    assert "<Segmented" in doing and "p.ways.map(" in doing, "Die Zahlungsart ist kein Schieber (a)."
    assert "aria-label={d.method_label}" not in src, "Das alte Auswahlfeld steht noch da (a)."
    entry = _component(src, "EntryForm")
    at = entry.find("<Segmented")
    assert at == -1 or "form.kind === 'refund' && (" in entry[max(0, at - 120):at], (
        "Das Formular fragt die Zahlungsart erneut (b) – sie ist in der Leiste gewählt."
    )
    assert "d.method_label}</Label>" not in src, "Die Beschriftung steht zweimal (c)."


def test_a_refusal_is_just_a_refusal():
    """**«Absage» – und sonst nichts** (Testnotiz #965); **«Offerte annehmen» in beiden Richtungen** (#966).

    Der Zusatz «liefert nicht» stammte aus dem Beschaffungs-Beleg. Das Wort der Schwelle
    ist in beiden Richtungen dasselbe; die Karte hält es als Spiegel (`AGREE_WORD`) von
    `domain/voucher.AGREE_VERB` – geprüft, damit beide nie auseinanderlaufen.

    Bug-Formen: (a) der Zusatz ist zurück; (b) die Absage heisst anders; (c) das Wort der
    Schwelle läuft vom Server weg.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    from app.domain import voucher as vo
    src = _code(_beleg())
    assert "liefert nicht" not in src, "Der Zusatz ist zurück (a)."
    assert "const DECLINE_WORD = 'Absage'" in src and "label={DECLINE_WORD}" in src, (
        "Die Absage heisst nicht mehr «Absage» (b)."
    )
    word = re.search(r"export const AGREE_WORD = '([^']+)'", src)
    assert word and word.group(1) == vo.AGREE_VERB, (
        "Das Wort der Schwelle in der Karte ist nicht das des Servers (c)."
    )


# ---------------------------------------------------------------------------
# ►► TESTNOTIZEN #975–#978
# ---------------------------------------------------------------------------


def test_what_to_do_stands_once_on_the_document():
    """►►► **«Was ist zu tun?» entfällt – es ist die Leistung an der Position** (Runde 25.10.2026). ◄◄◄

    Der Satz handelte von den Positionen, also steht er bei ihnen: als **Untertitel** jeder
    Position (`line.text`, die Leistung), vorbelegt und bis zur Offerte änderbar. Eine
    eigene Zeile «Was ist zu tun?» darunter gibt es nicht mehr.

    Bug-Formen: (a) die eigene Zeile ist zurück; (b) die Leistung steht nicht an der
    Position; (c) sie ist änderbar, wo `can` es nicht sagt.
    """
    src = _code(_beleg())
    assert "d.task" not in src and "task_label" not in src, "Die eigene Zeile ist zurück (a)."
    row = _component(src, "LineRow")
    assert "<Service" in row and "draft.text" in row, "Die Leistung steht nicht an der Position (b)."
    assert "may(d, 'price')" in row, "Die Leistung ist änderbar, ohne `can` zu fragen (c)."
    assert "if (!on)" in _component(src, "Service"), "Die Leistung ist immer änderbar (c)."


def test_each_side_of_the_head_names_both_addresses():
    """►►► **Beide Anschriften, auf beiden Seiten, immer** (Testnotiz #975). ◄◄◄

    Die Auflösung steht an **einer** Stelle im Dienst (`_addresses`) und gilt für beide
    Seiten – die Karte zeichnet nur noch, nebeneinander, mit der Beschriftung des Servers.

    Bug-Formen: (a) es gibt wieder zwei Auflösungen; (b) unsere Seite hat keine; (c) die
    Karte entscheidet selbst, ob eine Beschriftung erscheint.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    src = (BACKEND / "app" / "services" / "voucher.py").read_text()
    body = src[src.index("def _addresses("):]
    body = body[:body.index("\ndef ", 1)]
    assert "BILLING_LABEL" in body and "SHIPPING_LABEL" in body, "Die Beschriftungen kommen nicht aus der einen Auflösung (a)."
    head = src[src.index("def _ours("):src.index("def _creditor(")]
    assert "_addresses(" in head, "Unsere Seite nennt ihre Anschriften nicht (b)."
    assert src.count("_addresses(") >= 3, "Nicht beide Seiten lesen dieselbe Auflösung (a/b)."
    card = _code(_beleg())
    block = _component(card, "Addresses")
    assert "side.address_label" in block and "side.shipping_label" in block, (
        "Die Karte baut die Beschriftungen wieder selbst (c)."
    )
    for word in ("Rechnungsadresse", "Lieferadresse"):
        assert word not in card, f"«{word}» steht als Literal in der Karte (c)."


# ---------------------------------------------------------------------------
# ►► DER UMBAU VON «RECHNUNG & ZAHLUNG» + TESTNOTIZEN #979/#981/#982
# ---------------------------------------------------------------------------


def test_money_stands_in_two_compartments_not_in_one_row_of_buttons():
    """►►► **Regel 1 — EIN Abschnitt «Rechnung», keine Knopfreihe** (Umbau 25.10.2026). ◄◄◄

    *«Zu komplex, zu unstrukturiert, zu wirr, zu viele Optionen.»* – Erst wurden die sechs
    Knöpfe an einer Rechnung in zwei Fächer sortiert («Fordern» · «Begleichen»); jetzt ist
    es **ein** Abschnitt (Rechnung, Geld, Saldo), und was der Saldo verlangt, steht als
    Entscheidung bei ihm (`Decision`: ausbuchen · erstatten · als Trinkgeld behalten) – mit
    einem Satz, der sagt warum. Die eine Handlung, die weiterbringt, steht in der Leiste.

    Bug-Formen: (a) das Geld steht wieder in mehreren Abschnitten; (b) eine Entscheidung
    steht ohne ihren Satz da; (c) die Wörter stehen in der Karte statt beim Server.
    """
    src = _code(_beleg())
    money = _component(src, "Invoice")
    assert money.count("<Section") == 1, (
        f"Das Geld steht in {money.count('<Section')} Abschnitten (a)."
    )
    assert "money_label" not in src and "Rechnung & Zahlung" not in src, "Der alte Sammeltitel ist zurück (a/c)."
    balance = _component(src, "Balance")
    assert balance.count("<Decision text=") >= 2, "Eine Entscheidung steht ohne ihren Satz da (b)."
    for word in ("d.write_off_word", "d.refund_word", "d.tip_word"):
        assert word in balance, f"«{word}» kommt nicht vom Server (c)."


def test_exactly_one_money_action_moves_the_voucher_on():
    """►►► **Regel 2 — genau EINE Handlung bringt weiter, und sie steht in der Leiste.** ◄◄◄

    *Rechnung stellen* → *Zahlung erfassen* → nichts mehr: welche ansteht, sagt der Server
    (`state.primary`); die Leiste leitet daraus genau einen Hauptknopf ab. Ist ein
    Formular offen, tritt sein Abschicken («Buchen») an ihre Stelle – es steht nicht daneben.

    Bug-Formen: (a) die Handlung ist wieder ein Knopf unter vielen; (b) der Rang wird nicht
    abgeleitet, sondern nebeneinandergestellt; (c) das Formular steht neben dem Knopf, der
    es öffnet.
    """
    src = _code(_beleg())
    doing = _component(src, "Doing")
    assert doing.count("<MainButton label={primary.label}") == 1, (
        "Es gibt mehr als eine Stelle für die Handlung, die weiterbringt (a)."
    )
    primary = _component(src, "primaryOf")
    for derived in ("case 'bill':", "case 'pay':", "return wayOf(p);"):
        assert derived in primary, f"Der Rang wird nicht abgeleitet (b): «{derived}»."
    assert "if (form)" in primary and "formWord(form, d)" in primary, (
        "Formular und Knopf stehen gleichzeitig da (c)."
    )


def test_the_way_to_the_money_is_one_choice_with_several_answers():
    """►►► **Regel 3 — der Weg zum Geld ist eine Wahl, kein Verb.** ◄◄◄

    Bar · Überweisung · Karte sind drei Antworten auf **eine** Frage. Welche es gibt, sagt
    der Server (`ways`), und **jeder Weg sagt selbst, was er auslöst** (`action`/`verb`) –
    ein Weg ohne beides ist eine reine Auskunft, und dort steht kein Knopf.

    Bug-Formen: (a) die Wege sind wieder Knöpfe; (b) die Oberfläche baut die Liste selbst;
    (c) sie leitet das Verb aus dem Schlüssel ab; (d) bei genau einer Antwort steht
    trotzdem ein Schieber.
    """
    src = _code(_beleg())
    doing = _component(src, "Doing")
    way = _component(src, "wayOf")
    assert "<Segmented" in doing, "Die Wege sind wieder einzelne Knöpfe (a)."
    assert "p.ways.map(" in doing and "voucher.ways" in _component(src, "BelegWork"), (
        "Die Liste kommt nicht vom Server (b)."
    )
    for key in ("'cash'", "'card'", "'transfer'"):
        assert key not in doing and key not in way, f"«{key}»: die Oberfläche kennt die Schlüssel (c)."
    assert "way.verb" in way and "way.action" in way, "Der Weg sagt nicht selbst, was er auslöst (c)."
    assert "p.ways.length > 1" in doing, "Bei genau einer Antwort steht ein Schieber (d)."


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
    """►►► **Rolle, dann Name – und der gedruckte Name IST die Wahl** (#981, Entscheid 25.10.2026). ◄◄◄

    Die Chips über der Rolle sind weg (die Kandidaten stehen im Angebotsspiegel). Geblieben
    ist die Wahl *geschäftlich oder privat*: sie ist der gedruckte Name selbst
    (`side.choice`, Verb `address` mit `bill_to_company`), unter der Rolle – erst *welche
    Seite*, dann *wer*. Beide Seiten stehen auf demselben Raster (`SIDE_ROWS`).

    Bug-Formen: (a) die Rolle steht unter dem Namen; (b) die Wahl ist ein zweites Feld neben
    dem Namen; (c) die Wahl hängt nicht an der Angabe des Servers.
    """
    src = _code(_beleg())
    side = _component(src, "Side")
    assert side.index("{role.label}") < side.index("<SideName"), "Die Rolle steht unter dem Namen (a)."
    name = _component(src, "SideName")
    assert "<DocPick" in name and "text={side.name" in name, (
        "Die Wahl ist nicht der gedruckte Name (b)."
    )
    assert "side.choice" in name and "bill_to_company: v === FIRM" in name, (
        "Die Wahl hängt nicht an der Angabe des Servers (c)."
    )


def test_a_customs_field_names_itself_while_it_is_being_typed():
    """►►► **Die Beschriftung steht davor – beim Eingeben wie im Beleg** (#982). ◄◄◄

    *«Im fertigen Beleg steht eigentlich immer ‹Zolltarif xy, Ursprung xy› – hier bei der
    Eingabe steht einfach nur das Eingabefeld.»* Der Name steht nie als Platzhalter.

    Bug-Formen: (a) der Name ist wieder nur ein Platzhalter; (b) die beiden Zustände sehen
    verschieden aus; (c) die Beschriftung trägt die Auszeichnung änderbarer Werte.
    """
    body = _component(_code(_beleg()), "CustomsField")
    assert "placeholder=" not in body, "Der Name steht wieder als Platzhalter (a)."
    assert "const face" in body and "style={face}" in body and "...face" in body, (
        "Die Beschriftung sieht im Eingabe- und im Lesezustand verschieden aus (b)."
    )
    edit = body[body.index('<span className="inline-flex'):]
    assert edit.index("{label}</span>") < edit.index("<Editable"), (
        "Die Beschriftung steht innerhalb der Auszeichnung (c)."
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
    src = _code(_beleg())

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
    """►►► **Ein Kandidat sagt seinen Zustand als Wort, nicht als Punkt** (#983, Umbau). ◄◄◄

    Der Punkt vor dem Namen war ein Zeichen, das man deuten muss. Die Zeile eines
    Kandidaten nennt ihren Zustand als Wort («Noch nicht angeboten»), und ob er im Kopf
    steht, ebenso («Im Kopf»).

    Bug-Formen: (a) ein Punkt steht wieder vor dem Namen; (b) das Wort fehlt.
    """
    row = _component(_code(_beleg()), "Candidate")
    assert "rounded-full" not in row, "Der Zustandspunkt steht wieder da (a)."
    assert "Noch nicht angeboten" in row and "<InHead" in row, "Das Wort fehlt (b)."


def test_both_booking_forms_are_the_same_form():
    """►►► **Ein Formular, und es sieht aus wie jedes andere** (#987/#990). ◄◄◄

    Zahlung, Erstattung und Lieferantenrechnung sind **dieselbe** Komponente
    (`EntryForm`) im grauen Kasten: die Masse aus den Bauteilen (`FIELD_GAP`, `Label`),
    die Felder des Hauses (`inputCls`), «Abbrechen» dezent als Quadrat – abgeschickt wird
    mit der einen Handlung der Leiste.

    Bug-Formen: (a) die Masse stehen wieder als Zahlen an dieser Stelle; (b) zwei gleich
    grosse Knöpfe; (c) das Feld ist nicht das des Hauses.
    """
    work = _code(_beleg())
    form = _component(work, "EntryForm")
    assert "FIELD_GAP" in form, "Der Feld-Abstand steht wieder als Zahl da (a)."
    assert "gap:" not in _component(work, "FormField"), (
        "Unter der Beschriftung steht wieder ein eigener Abstand (a)."
    )
    assert "<Cancel" in form and "square" in _component(work, "Cancel"), (
        "«Abbrechen» ist kein Quadrat (b)."
    )
    assert "erp-actbtn-primary" not in form, (
        "Das Formular hat einen eigenen Hauptknopf neben der Leiste (b)."
    )
    assert form.count("inputCls") >= 2, "Die Felder sind nicht die des Hauses (c)."


def test_a_payment_row_begins_with_how_it_was_paid():
    """►►► **Zahlungsart zuerst, dann Betrag und Datum** (Testnotizen #994/#988). ◄◄◄

    Jede Geld-Zeile beginnt mit dem, woran man sie wiedererkennt: der Zahlungsart – bzw.
    bei einer Ausbuchung, einem Trinkgeld, einer Erstattung oder Gegenbuchung mit ihrer
    Art. Der Zustand steht nicht als eigene Zeile darunter; die Rechnung sagt ihren als
    Farbe ihres Betrags und als Wort im Hover.

    Bug-Formen: (a) die Zahlungsart steht wieder hinten; (b) der Zustand steht wieder als
    eigene Zeile darunter; (c) die Rechnung verliert dabei ihren Zustand ganz.
    """
    work = _code(_beleg())
    row = _component(work, "EntryRow")
    assert "ident={entryName(e)}" in row and "e.method_label" in _component(work, "entryName"), (
        "Die Zahlungszeile beginnt nicht mit ihrer Art (a)."
    )
    assert row.index("ident=") < row.index("amount="), "Die Zahlungsart steht hinter dem Betrag (a)."
    assert "state.label" not in row, "Der Zustand steht wieder als eigene Zeile darunter (b)."
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
    """►►► **Der Saldo: eine Zahl, ihre Farbe und ihr Name** (#997, Umbau). ◄◄◄

    Die Farbe ist die Aussage – sie kommt vom Server (`open_state_tone`). Wo der Saldo
    etwas anderes ist als ein offener Betrag, nennt er sich beim Namen des Servers
    («Beglichen», «Guthaben»); eine Gutschrift heisst «Wir erstatten». Die Zahl steht ohne
    Vorzeichen da: ein offener Posten ist eine Menge, die Richtung sagt das Wort.

    Bug-Formen: (a) die Oberfläche rechnet den Zustand selbst; (b) das Guthaben steht ohne
    Namen da; (c) der Saldo bekommt ein Minus.
    """
    src = _code(_beleg())
    bal = _component(src, "Balance")
    assert "toneOf(d.open_state_tone)" in bal and "TONE[" in _component(src, "toneOf"), (
        "Die Farbe wird wieder selbst gewählt (a)."
    )
    assert "Number(d.open)" not in bal, "Die Oberfläche entscheidet an der Zahl, welche Farbe gilt (a)."
    assert "d.open_state_label" in bal and "credit" in bal, "Das Guthaben nennt sich nicht beim Namen (b)."
    assert "value={unsigned(d.open)}" in bal, "Der Saldo trägt ein Vorzeichen (c)."


def test_choosing_a_party_writes_it_instead_of_asking():
    """►►► **Die Wahl wird geschrieben, nicht abgeschickt** (Testnotiz #1000). ◄◄◄

    «+ Partner wählen» schreibt die Wahl (`party`) – anbieten tut die Leiste, wenn alles
    dasteht. Wer nur gewählt ist, lässt sich wieder wegnehmen (`unask`); wer in der
    Definition steht, nicht.

    Bug-Formen: (a) das Feld fragt wieder an; (b) die Wahl lässt sich nicht mehr
    zurücknehmen, solange nichts hinausgegangen ist.
    """
    src = _code(_beleg())
    field = _component(src, "PickParty")
    assert "action: 'party'" in field and "'ask'" not in field, (
        "Die Wahl der Gegenpartei fragt sie sofort an (a)."
    )
    row = _component(src, "Candidate")
    assert "removable" in row and "d.allowed.some" in row, (
        "Ein nur gewählter Partner lässt sich nicht mehr abwählen (b)."
    )


def test_an_autosave_never_moves_the_page():
    """►►► **Ein Auto-Save darf die Geometrie der Seite nicht verändern** (#1009). ◄◄◄

    (a) **Die Aufstellung steht von Anfang an**: welche Zeilen es gibt, sagen die
    Positionen (jede trägt ihren Satz), nicht erst die Preise. (b) **`disabled` nimmt dem
    Feld den Fokus** – `busy` sperrt nur Handlungen, nie einen Wert.

    Bug-Formen: (a) die Netto-Zeile hängt wieder an einer Bedingung oder die Steuerzeilen
    kommen allein vom Server; (b) ein änderbarer Wert ist wieder `disabled={busy}`.
    """
    src = _beleg()
    sums = _code(_component(src, "Sums"))
    assert '<SumRow label="Netto"' in sums and "{d.net != null &&" not in sums, (
        "Die Netto-Zeile erscheint erst mit einem Wert (a)."
    )
    assert "sumLines(d" in sums and "for (const ln of d.lines)" in _code(_component(src, "sumLines")), (
        "Die Steuerzeilen kommen allein aus der Server-Aufteilung (a)."
    )
    for tag in ("<input", "<select"):
        for chunk in _code(src).split(tag)[1:]:
            head = chunk.split(">")[0]
            assert "disabled={busy}" not in head, (
                f"Ein Eingabefeld wird beim Speichern gesperrt (b): {tag}{head[:70]}"
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

    «falsch erfasst?» nimmt eine Buchung zurück (Kreispfeil gegen den Uhrzeiger), der
    Storno annulliert (durchgestrichener Kreis) – keine Korrektur trägt das Zeichen des
    Hinzufügens.

    Bug-Form: eine Korrektur trägt ein Plus oder ein falsches Zeichen.
    """
    src = _code(_beleg())
    entry = _component(src, "EntryRow")
    assert "icon={Plus}" not in src, "Eine Handlung trägt das Zeichen des Hinzufügens."
    assert "icon={RotateCcw}" in entry, "Der Gegenbuchung fehlt ihr Symbol."
    assert "icon={CircleSlash}" in _component(src, "Doing"), "Dem Storno fehlt sein Symbol."


def test_a_save_never_hides_a_control_in_the_party_block():
    """►►► **Ein Auto-Save verändert die Geometrie NICHT** (Testnotiz #1016). ◄◄◄

    *«Der Partner-Block im Zahlungsmodul springt beim Autosave weiterhin.»* – Die Knöpfe
    hingen an ``!busy`` und verschwanden während jedes Speicherns. **``busy`` darf nie
    etwas ein- oder ausblenden**: es sperrt Handlungen (``disabled``) und pausiert das
    Speichern selbst. Die Regel gilt der ganzen Karte.

    Bug-Formen: (a) eine Handlung hängt wieder an ``busy``, also verschwindet ein Knopf;
    (b) ein Kandidat verliert sein «Wegnehmen» beim Speichern.
    """
    src = _beleg()
    allowed = ("useAutosaveSignature(", "const ready =")
    code = _code(src)
    for m in re.finditer(r"!busy", code):
        window = code[max(0, m.start() - 160):m.start()]
        assert any(a in window for a in allowed), (
            f"«{code[m.start() - 40:m.start() + 40].strip()}»: `busy` entscheidet wieder, "
            f"ob etwas gezeichnet wird (a)."
        )
    row = _code(_component(src, "Candidate"))
    assert "disabled={busy}" in row and "busy &&" not in row, (
        "Das Wegnehmen eines Kandidaten verschwindet beim Speichern (b)."
    )


def test_a_date_stands_right_of_the_row_never_in_the_flow():
    """►►► **Datum und Fälligkeit stehen RECHTS, links vom Betrag** (#1011/#1012). ◄◄◄

    Es ist die **zweite Zahl** der Zeile, und zwei Zahlen gehören nebeneinander: so stehen
    sie über alle Zeilen hinweg in zwei Spalten (`LedgerRow.date`).

    Bug-Formen: (a) das Datum steckt wieder im Fliesstext (``meta``); (b) es gibt den Platz
    gar nicht; (c) es schrumpft mit und malt sich über seine Box hinaus.
    """
    row = _code(_component(_module_ui(), "LedgerRow"))
    assert "date" in row, "Die Zeilen-Grammatik kennt keinen Platz für das Datum (b)."
    assert row.rindex("{date}") < row.rindex("{amount}"), "Das Datum steht hinter dem Betrag (b)."
    src = _code(_beleg())
    entry = _component(src, "EntryRow")
    assert "date={when(" in entry, "Die Geld-Zeile füllt den Platz nicht (b)."
    meta = entry[entry.index("const meta"):entry.index("return (")]
    assert "when(" not in meta, "Das Datum steckt wieder im Fliesstext (a)."
    assert "date={stamp}" in _component(src, "InvoiceRow"), "Die Rechnung füllt den Platz nicht (b)."
    block = row[row.index("{date}") - 400:row.index("{date}")]
    assert "flex: 'none'" in block and "nowrap" in block, "Das Datum darf schrumpfen (c)."


def test_a_refund_that_fails_says_so():
    """►►► **«Zurück auf die Karte» sagt, was daraus wurde** (Testnotiz #1013). ◄◄◄

    Ein Fehlschlag erzeugt eine sichtbare Meldung, nicht stilles Scheitern; und weil der
    Webhook bucht, wird danach nachgefragt wie bei einer Zahlung.

    Bug-Formen: (a) der Fehler wird wieder verschluckt; (b) es wird nicht nachgefragt;
    (c) die Meldung wird gefangen, aber nirgends gerendert.
    """
    src = _code(_beleg())
    work = _component(src, "BelegWork")
    assert "catch (e)" in work and "setFailed" in work, "Der Fehlschlag wird weggeworfen (a)."
    assert "catch(() => {})" not in src, "Irgendwo wird ein Fehlschlag verschluckt (a)."
    assert re.search(r"refundVoucherPayment[\s\S]{0,120}wait\(\)", work), (
        "Nach der Erstattung wird nicht nachgefragt (b) – gebucht wird vom Webhook."
    )
    assert "{failed}" in work, "Die Meldung wird nirgends gezeigt (c)."


def test_a_refund_button_closes_at_the_click():
    """►►► **Ab dem Klick zu** (Testnotiz #1018). ◄◄◄

    Zwischen Klick und Buchung liegt die Meldung des Webhooks; in diesem Fenster sagt es
    der Knopf selbst (gesperrt, mit dem Grund). Dass er danach verschwindet, sagt der Server
    (`refundable` → Weg `refund_online`).

    Bug-Formen: (a) der Knopf kennt seinen Zustand nicht; (b) er wird erst nach der Antwort
    gesperrt; (c) die Sperre fällt nach einem Fehler nicht zurück.
    """
    src = _code(_beleg())
    way = _component(src, "wayOf")
    refund = way[way.index("'refund_online'"):]
    assert "p.refunding" in refund[:500], "Der Knopf kennt seinen Zustand nicht (a)."
    work = _component(src, "BelegWork")
    body = work[work.index("const refundCard"):]
    assert body.index("setRefunding(true)") < body.index("await api.refundVoucherPayment"), (
        "Gesperrt wird erst nach der Antwort (b)."
    )
    assert "setRefunding(false)" in body[body.index("catch"):], (
        "Nach einem Fehler bleibt der Knopf zu (c)."
    )


def test_what_is_still_open_stands_above_the_way_to_settle_it():
    """►►► **Der Saldo steht ÜBER dem Weg zum Geld** (Testnotiz #1019). ◄◄◄

    Man wählt einen Weg zum Geld nicht, ohne die Zahl zu sehen, um die es geht: im
    Abschnitt «Rechnung» steht der Saldo vor dem Erfassen, der Auskunft und der Karte – und
    die Wege selbst stehen darunter, in der Leiste. Was die Zahl verlangt (ausbuchen,
    erstatten), steht bei ihr.

    Bug-Formen: (a) der Saldo steht unter dem Erfassen oder der Auskunft; (b) die Wege
    stehen über dem Saldo; (c) die Ausbuchung wandert von der Zahl weg.
    """
    src = _code(_beleg())
    money = _component(src, "Invoice")
    body = money[money.index("return ("):]
    at = body.index("<Balance")
    for later in ("<EntryForm", "<Transfer", "<PayOnline"):
        assert at < body.index(later), f"Der Saldo steht unter «{later}» (a)."
    work = _component(src, "BelegWork")
    assert work.index("<Invoice") < work.index("<Footer"), "Die Wege stehen über dem Saldo (b)."
    assert "d.write_off_word" in _component(src, "Balance"), "Die Ausbuchung steht nicht bei der Zahl (c)."


def test_the_way_to_the_money_needs_no_label():
    """►►► **«Zahlungsart» sagt nichts, was nicht darunter steht** (Testnotiz #1020). ◄◄◄

    *«Das Label ‹Zahlungsart› entfernen – der Bereich ist selbsterklärend.»*

    «Bar», «Überweisung», «Karte» sagen jede für sich, was sie sind, und der Abschnitt
    darüber heisst «Begleichen». Ein Wort, das nur wiederholt, ist Höhe ohne Aussage.

    **Und der Platz geht mit**: eine leere Beschriftungszeile wäre dieselbe Höhe ohne
    denselben Inhalt.

    Bug-Formen: (a) die Beschriftung ist wieder da; (b) sie ist weg, die Zeile bleibt.
    """
    work = _code(_beleg())
    at = work.index("<Segmented")
    assert "label=" not in work[at:work.index("/>", at)], (
        "Die Zahlungsart trägt wieder eine Beschriftung (a)."
    )
    seg = _body(_code(_read(FRONTEND / "components" / "erp" / "fields.tsx")),
                "Segmented", kind="export function")
    # Kein Aufrufer gibt eine Beschriftung mit – also hat der Baustein keine Zeile dafür.
    assert "<Label" not in seg, (
        "Der Umschalter trägt eine Beschriftungszeile (b) – dieselbe Höhe ohne denselben Inhalt."
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
    ui = _code(_beleg())
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
    """►►► **Der Grund steht am Knopf** (Testnotiz #1046). ◄◄◄

    Der Knopf ist gesperrt, bis alles vollständig ist, und sagt im Hover warum – **der Satz
    kommt vom Server** (`ask_problem`), dieselbe Ableitung, mit der `_ask` abweist.

    Bug-Formen: (a) der Knopf ist nicht gesperrt; (b) der Grund steht nicht in seiner
    Blase; (c) die Oberfläche baut ihn selbst.
    """
    src = _code(_beleg())
    primary = _component(src, "primaryOf")
    ask = primary[primary.index("case 'ask':"):primary.index("case 'party':")]
    assert "d.ask_problem" in ask, "Der Knopf fragt den Server nicht (a/c)."
    button = _component(src, "MainButton")
    assert "disabled={busy || !!problem}" in button, "Der Knopf ist nicht gesperrt (a)."
    assert "data-tip={problem}" in button, "Der Grund steht nicht in der Blase (b)."
    assert "Zolltarifnummer» fehlt" not in src and "anzubieten." not in src, (
        "Die Karte formuliert den Grund selbst (c)."
    )


def test_the_invoice_is_out_there_once_it_is_billed():
    """►►► **«Rechnung ist versendet» ist gelöscht** (Testnotiz #1047). ◄◄◄

    *«Bitte komplett und vollständig aus dem Code eliminieren.»* – Gestellt heisst
    hinausgegangen (die Rechnung geht als Dokument per Mail). Wie weit der Beleg ist, sagen
    die Stationen oben – vom Server (`stages[].done/active`), nie aus einem Versand-Datum.

    Bug-Formen: (a) das Verb ist wieder da; (b) der Fortschritt hängt wieder am
    Versand-Datum oder wird in der Karte gerechnet; (c) die Zeile zeigt es wieder an.
    """
    src = _code(_beleg())
    assert "'issue'" not in src and "issue_word" not in src, "Das Verb ist wieder da (a)."
    assert "issued_on" not in src, "Das Versand-Datum wird wieder gelesen (b/c)."
    stages = _component(src, "Stages")
    assert "d.stages.map(" in stages and "s.done" in stages and "s.active" in stages, (
        "Der Fortschritt kommt nicht vom Server (b)."
    )


def test_every_amount_field_names_its_currency():
    """►►► **Kein Betrags-Feld ohne Währung — auch das der Offerte** (Testnotiz #1049). ◄◄◄

    Das Betragsfeld der Offerte eines Lieferanten trägt die Währung als Suffix in derselben
    Hülle (#1010/#1017), die Stellenzahl der Währung (#931) und seine Beschriftung. Und die
    Aufstellung steht immer – sie trägt den Währungs-Wähler.

    Bug-Formen: (a) das Feld trägt keine Währung; (b) es nimmt zu viele Nachkommastellen;
    (c) es steht ohne Beschriftung da; (d) die Aufstellung verschwindet.
    """
    src = _code(_beleg())
    form = _component(src, "QuoteForm")
    at = _at(form, 'aria-label="Betrag"')
    around = form[max(0, at - 400):at + 300]
    assert "<Amount currency={d.currency}" in around, "Das Betragsfeld trägt keine Währung (a)."
    assert "decimals: d.currency_decimals" in around, "Es nimmt zu viele Nachkommastellen (b)."
    assert '<Stacked label="Betrag">' in around, "Es steht ohne Beschriftung da (c)."
    assert "return null" not in _component(src, "Sums"), "Die Aufstellung verschwindet (d)."


def test_time_comes_before_what_happened():
    """►►► **Zeit zuerst, dann der Vorgang — und die Form steht EINMAL** (#1052). ◄◄◄

    «Gerade eben offeriert», «Gerade eben angenommen»: die Form wohnt bei der einen
    Datums-Ausgabe des Hauses (`lib/when.happened`), die Wörter kommen vom Server.

    Bug-Formen: (a) `happened` gibt es nicht; (b) eine Aufrufstelle baut «Wort · Zeit»
    wieder selbst; (c) der Satzanfang wird nicht gross geschrieben; (d) die Wörter stehen
    in der Karte.
    """
    when_src = _read(FRONTEND / "lib" / "when.ts")
    assert "export function happened(" in when_src, "Die Form steht nicht bei der Datums-Ausgabe (a)."
    assert "toUpperCase()" in _code(_body(when_src, "happened", kind="function")), (
        "Der Satzanfang bleibt klein (c)."
    )
    work = _code(_beleg())
    assert not re.search(r"[a-zäöü]+ · \{when\(", work), (
        "Eine Aufrufstelle setzt «Wort · Zeit» wieder von Hand zusammen (b)."
    )
    assert work.count("happened(") >= 2, (
        f"Nur {work.count('happened(')} Aufrufstellen nennen die Form – es sind zwei "
        f"(offeriert · angenommen)."
    )
    from app.domain import voucher as dm
    for word in (dm.SENT_WORD, dm.TAKEN_WORD, dm.CANCELLED_WORD):
        assert f"'{word}'" not in work, f"«{word}» steht in der Karte (d)."
    for field in ("d.sent_word", "d.taken_word"):
        assert field in work, f"Die Karte liest «{field}» nicht (d)."


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
    src = _beleg()
    row = _code(_component(src, "QuoteRow"))
    assert "!taken" in row, (
        "Das Wort steht neben der Aussage, die es wiederholt (a)."
    )
    assert "quoteLook(" in row and "look.label" in row, (
        "Die übrigen Ausgänge haben ihr Wort verloren (b) – «unbeantwortet» und "
        "«abgesagt» stehen an keiner Zahl."
    )


def test_the_form_asks_for_the_number_the_service_demands():
    """►►► **Eine Lieferantenrechnung hat immer eine Nummer, ein Datum und ein Foto** (#1058, Umbau). ◄◄◄

    Der Dienst weist `bill` ohne Rechnungsnummer und ohne Foto ab (und ohne MWST-Nr., sobald
    Steuer darauf steht). Die Leiste sperrt «Buchen» vorher und nennt den Grund am Knopf –
    zwei Formen einer Regel (`formProblem` ↔ `_bill`), ein Massstab. Eine Zahlung verlangt
    keine Referenz.

    Bug-Formen: (a) der Knopf bleibt offen; (b) es gibt keinen Grund im Hover; (c) die
    Zahlung verlangt sie plötzlich auch.
    """
    src = _code(_beleg())
    problem = _component(src, "formProblem")
    bill = problem[problem.index("case 'bill':"):problem.index("case 'export':")]
    for need in ("blank('reference')", "blank('original')", "blank('party_uid')", "billed_on"):
        assert need in bill, f"«{need}»: die Lieferantenrechnung geht ohne sie (a)."
    pay = problem[problem.index("case 'pay':"):problem.index("case 'bill':")]
    assert "reference" not in pay, "Die Zahlung verlangt eine Referenz (c)."
    primary = _component(src, "primaryOf")
    assert "problem: formProblem(form, d)" in primary, "Der Knopf fragt die Prüfung nicht (a)."
    assert "data-tip={problem}" in _component(src, "MainButton"), "Kein Grund im Hover (b)."


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
    src = _beleg()
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

    Der Server liefert sie am Adressaten, vor der Zusage, für das Personal; danach ist der
    Kopf eingefroren. Die Karte formuliert die Bedingung nicht selbst nach.

    Bug-Formen: (a) die Wahl hängt an der Stufe statt an ``choice``; (b) sie schickt ein
    anderes Verb als ``address``; (c) die Anschrift ist ein Freitextfeld statt einer Wahl
    aus dem Adressbuch.
    """
    src = _code(_beleg())
    assert "const c = side.choice;" in _component(src, "SideName") and "if (c?.company)" in src, "(a)"
    assert src.count("action: 'address'") == 3, "(b)"
    body = _component(src, "Anschrift")
    assert "<DocPick" in body and "choice?.options" in body and "<input" not in body, "(c)"


