"""Quelltext-Wächter: das Zahlungsmodul «Beleg» (``beleg-work.tsx``, ``services/voucher``).
"""

import re

from tests._source import (
    _kit,
    BACKEND,
    FRONTEND,
    _at,
    _beleg,
    _body,
    _code,
    _component,
    _read,
)


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
    assert '"billing": voucher_head.billing_of(' in svc, (
        "Der Dienst liefert die bekannten Angaben nicht mit (c)."
    )
    # ►►► **Und es gibt genau EINE Auskunft darüber** (Testnotiz #865). ◄◄◄
    #
    # Sie sass im Adapter des Zahlungsdienstes und wurde dort gebraucht, um das
    # Bezahlformular vorzufüllen. Die **QR-Rechnung** stellt dieselbe Frage – wer
    # überweist, und unter welcher Anschrift? Zwei Fassungen davon liefen beim ersten
    # neuen Adressfeld auseinander; sie gehört darum an den Vorgang, den beide in der
    # Hand haben. (d) wäre eine zweite Fassung daneben.
    deal_src = _read(BACKEND / "app" / "services" / "voucher_head.py")
    money_src = _read(BACKEND / "app" / "services" / "voucher_money.py")
    assert "def billing_of(" in deal_src and "def _billing(" not in _code(svc), (
        "Die Angaben über den Zahlenden werden zweimal hergeleitet (d) – beim nächsten "
        "neuen Adressfeld sagen Bezahlkarte und Einzahlungsschein Verschiedenes."
    )
    assert "billing_of(db, row)" in _body(money_src, "transfer_of"), (
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
    svc = _read(BACKEND / "app" / "services" / "voucher_view.py")
    assert '"pay_online_word": vo.PAY_ONLINE_WORD' in svc, (
        "Der Server schickt das Wort nicht mit (b) – dann steht der Knopf ohne Beschriftung da."
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


def test_a_typed_amount_has_the_decimals_of_its_currency():
    """►►► **Was man tippen kann, ist die Stelligkeit der Währung** (Testnotiz #931). ◄◄◄

    Wer vier Nachkommastellen tippen kann, bekommt sie vom Server gerundet zurück, und das
    sieht aus wie ein Datenverlust. Das gilt für den Einzelpreis, den Teilbetrag und jeden
    Betrag, der erfasst wird.

    Bug-Formen: (a) `numericOnly` kann gar nicht begrenzen; (b) ein Betragsfeld begrenzt
    nicht; (c) es begrenzt fest auf zwei (JPY hat null, KWD drei).
    """
    fields = _code(_kit())
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


def test_the_card_takes_the_charge_word_from_the_server():
    """►►► **«Rechnung stellen» ↔ «Rechnung erfassen» – das Wort kommt vom Server.** ◄◄◄

    Die Regel selbst (zwei Bits, zwei Wörter) prüft
    ``test_voucher_module.test_an_invoice_is_issued_here_and_recorded_there``; hier steht
    nur die Naht zur Oberfläche.

    Bug-Formen: (b) der Beleg schickt das Wort nicht mit; (c) die Karte schreibt es selbst.
    """
    src = (BACKEND / "app" / "services" / "voucher_view.py").read_text()
    assert '"charge_word": vo.charge_word(' in src, (
        "Der Beleg schickt nicht das Wort seiner Lage (b)."
    )
    card = _code(_beleg())
    for word in ("Rechnung stellen", "Rechnung erfassen", "Gutschrift stellen"):
        assert word not in card, f"«{word}» steht als Literal in der Karte (c)."


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


def test_the_agreed_amount_comes_from_the_server():
    """Was zugesagt ist, rechnet der Dienst (`voucher.agreed_amount` → `amount`). Die Karte
    rechnete es aus «Rechnung minus Abweichung» zurück – Geld im Browser, mit Fliesskomma.
    Bug-Form: eine Rechnung mit Betrag und `.toFixed` in der Abweichung."""
    invoice = _code(_read(FRONTEND / "components" / "erp" / "beleg" / "invoice.tsx"))
    body = invoice[invoice.index("function Deviation("):]
    body = body[: body.index("\n}\n")]
    assert "toFixed" not in body and "Number(d.invoice.amount)" not in body, (
        "Die Abweichung rechnet den zugesagten Betrag im Browser."
    )
    assert "d.amount" in body, "Der zugesagte Betrag kommt nicht vom Server."
