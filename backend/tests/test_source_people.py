"""Quelltext-Wächter: Person, Firma, Adressen, Rolle.
"""

import re

from tests._source import (
    BACKEND,
    FRONTEND,
    ROOT,
    _USER_SURFACES,
    _address_field,
    _at,
    _beleg,
    _body,
    _code,
    _component,
    _read,
)


# ---------------------------------------------------------------------------
# EIN Referenzfeld, überall (Testnotiz #738)
# ---------------------------------------------------------------------------


    #     Die Beschriftung, deren Typografie hier einmal geprüft wurde, gibt es nicht
    #     mehr – geblieben ist das Feld, und das war ohnehin die Anatomie, um die es ging.


def test_the_login_is_a_popup_over_the_page_behind_it():
    """**Ein Pop-up ist ein Pop-up** – und es gibt genau EINEN Anmelde-Dialog.

    Bug-Form (die gemeldete): das Anmelden war eine **Seite** mit eigener, deckender
    Fläche – die Seite dahinter verschwand, also brauchte es einen Knopf «Zurück zur
    Startseite», um wieder herauszukommen. Genau das ist der Umweg, den ein Pop-up nicht
    hat: daneben klicken beendet es, und was man vorher tat, steht noch da.

    Die zweite Bug-Form wäre die naheliegende Abkürzung: den Dialog in der Navbar
    **nachbauen** und die Route so lassen. Dann gäbe es zwei Anmeldungen, und die zweite
    veraltet beim ersten neuen Anmeldeweg – darum ist ``LoginDialog`` **ein** Bauteil,
    das beide benutzen.
    """
    dialog = _code(_read(FRONTEND / "components" / "auth" / "login-dialog.tsx"))
    page = _code(_read(FRONTEND / "app" / "(auth)" / "login" / "page.tsx"))
    css = _read(FRONTEND / "app" / "globals.css")

    # (1) Die Fläche dahinter bleibt sichtbar – ein Schleier, keine Wand.
    assert ".ix-login-scrim" in css, "Der Schleier über der Seite fehlt."
    # **Ohne die Erklärung gelesen** – der Kommentar in der Regel nennt die Bug-Form beim
    # Namen, und ein Wächter, der ihn mitliest, schlägt an, weil jemand den Fehler
    # *beschreibt*, den er verhindern soll. Genau das ist hier beim Schreiben passiert.
    rules = re.sub(r"/\*[\s\S]*?\*/", "", css)
    scrim = rules[rules.index(".ix-login-scrim"):]
    scrim = scrim[: scrim.index("}") + 1]
    assert "rgba(" in scrim, (
        "Der Hintergrund des Pop-ups ist wieder deckend – dann ist es keines, sondern "
        "eine Seite, und man braucht einen Weg zurück."
    )
    assert "position: fixed" in scrim and "inset: 0" in scrim, (
        "Der Schleier liegt nicht über der ganzen Seite."
    )
    # **Zentriert wird über `margin: auto`, nicht über `align-items`** – die klassische
    # Flexbox-Falle. Gemessen in Chromium (375x420): mit `align-items: center` steht der
    # Kopf einer zu hohen Karte bei −74 px, und in einem Scroll-Container ist alles vor
    # der Startkante unerreichbar; auf einem Telefon im Querformat wäre das E-Mail-Feld
    # schlicht weg. Mit `margin: auto` steht er bei +31 px.
    assert "align-items: center" not in scrim, (
        "Der Schleier zentriert wieder über `align-items` – eine Karte, die höher ist "
        "als das Fenster, wird dann oben abgeschnitten und lässt sich nicht hinscrollen."
    )
    card = rules[rules.index(".ix-login-card {"):]
    card = card[: card.index("}") + 1]
    assert "margin: auto" in card, (
        "Die Karte zentriert sich nicht mehr selbst – dann greift wieder die Falle."
    )
    assert ".ix-login-bg" not in css, (
        "Die alte, deckende Anmelde-Fläche ist zurück."
    )

    # (2) Daneben klicken beendet – und `Esc` ebenso; beides ist üblich, und wer nur
    #     eines baut, zwingt Tastatur- oder Mausnutzer in den jeweils anderen Weg.
    assert "e.target === e.currentTarget" in dialog, (
        "Ein Klick neben das Pop-up schliesst es nicht – dann ist der einzige Ausweg "
        "wieder ein Knopf."
    )
    assert "'Escape'" in dialog, "`Esc` schliesst das Pop-up nicht."
    assert 'aria-modal="true"' in dialog, (
        "Ohne `aria-modal` ist es für Hilfsmittel kein Dialog, sondern Seiteninhalt."
    )

    # (3) Der Weg zurück ist das Danebenklicken – der Knopf ist damit entfallen.
    # Gelesen wird der **Code**: die Erklärung darüber nennt den Knopf, den es nicht
    # mehr gibt – ein Wächter, der Kommentare liest, schlägt an, weil jemand den Fehler
    # *beschreibt*, den er verhindern soll.
    assert "Zurück zur Startseite" not in dialog, (
        "Der Knopf «Zurück zur Startseite» ist zurück – in einem Pop-up ist er der "
        "Umweg, den es gerade nicht braucht."
    )

    # (4) EIN Dialog, EIN Weg: seit Website und ERP denselben Kopf tragen (WEBSITE_PLAN
    #     Entscheid 60), führt «Anmelden» von überall auf die Route – und der Kopf hängt die
    #     Seite an, auf der man stand (`?from=`). Dorthin geht es danach, und ebenso beim
    #     Danebenklicken: «was man vorher tat, steht noch da» gilt damit weiter.
    assert "export function LoginDialog" in dialog, "Der Dialog ist kein eigenes Bauteil."
    assert "<LoginDialog" in page, (
        "Die Route baut die Anmeldung wieder selbst – dann gibt es sie zweimal."
    )
    assert "onClose={() => window.location.assign(cameFrom())}" in page, (
        "Daneben klicken führt nicht mehr dorthin zurück, wo man war."
    )
    shell = _code(_read(ROOT / "website" / "src" / "scripts" / "account.ts"))
    assert "/login?from=" in shell, (
        "Der gemeinsame Kopf nennt der Anmeldung nicht mehr, woher man kam."
    )


def test_a_person_is_never_deactivated_only_re_roled():
    """**Man deaktiviert keine Menschen** (Testnotiz #755).

    Wer das Unternehmen verlässt, hört nicht auf zu existieren – er wird vom Mitarbeiter
    zum gewöhnlichen Benutzer und darf weiterhin bei uns einkaufen. «Deaktivieren» war
    damit eine Aktion ohne fachliche Begründung, und sie hatte eine echte Folge: der
    Betroffene kam nicht mehr herein.

    Bug-Form: die Aktion bleibt (oder kommt als «löschen» zurück). Geprüft wird darum
    **die Tür, nicht das Wort** – die beiden Endpunkte dürfen es nicht mehr geben, und
    kein Knopf darf sie rufen.
    """
    admin = _code(_read(BACKEND / "app" / "routers" / "admin.py"))
    assert "def deactivate_user" not in admin, (
        "Der Deaktivieren-Endpunkt ist zurück – ein Benutzer wechselt die Rolle."
    )
    assert "def reactivate_user" not in admin, (
        "Ohne Deaktivieren braucht es auch keine Gegenaktion."
    )

    api = _code(_read(FRONTEND / "lib" / "api.ts"))
    assert "deactivateUser" not in api and "reactivateUser" not in api, (
        "Der Client ruft die Türen wieder, die es nicht mehr gibt."
    )
    user = _code(_read(FRONTEND / "components" / "erp" / "user-detail.tsx"))
    assert "Deaktivieren" not in user and "Reaktivieren" not in user, (
        "Der Knopf ist zurück – die Rolle ist der Weg, nicht der Aus-Schalter."
    )


def test_the_user_has_no_empty_document_tab():
    """**Kein Reiter über einer leeren Fläche** (Testnotiz #772).

    «Dokumente» rendete zwei Überschriften und sonst nichts – seine Karten hingen am
    Dokumentenmodul, und das gibt es nicht mehr. Übrig blieb ein Reiter, der das ganze
    Formular trägt: dann gibt es nichts zu wählen.
    """
    src = _read(FRONTEND / "components" / "erp" / "user-detail.tsx")
    assert "Freigaben & Anerkennungen" not in src and "Abgelegte Dokumente" not in src, (
        "Die leeren Überschriften stehen wieder da."
    )
    # Die Regel ist «keine Reiterleiste mit genau EINEM Reiter» – seit der Kommunikation
    # (CRM Schritt 2) trägt der Benutzer zwei: Person · Kommunikation.
    if "DetailTabs" in src:
        assert src.count("{ key: '") >= 2, (
            "Der Benutzer hat wieder eine Reiterleiste – mit genau einem Reiter darin."
        )


# ---------------------------------------------------------------------------
# ►► Testnotizen #897–#901 — der Geldvorgang ist EIN Beleg
# ---------------------------------------------------------------------------


def test_a_company_record_is_named_with_its_legal_form():
    """►►► **Unternehmensname · Abstand · Rechtsform — an EINER Stelle** (Notiz #910). ◄◄◄

    *«Der Datensatzname bei Datensatztyp Unternehmen soll immer der Unternehmensname
    sein → Abstand → Rechtsform.»* – Die Regel gab es längst (``sites.legal_name``,
    inklusive der Ausnahme «Muster AG» + «AG» = «Muster AG», nicht «Muster AG AG»); sie
    wurde nur nicht überall gerufen. Genannt wird derselbe Datensatz in der
    **Halter-Kette**, in der **Halter-Suche**, auf der **Gebietskarte**, in der
    **Kopfzeile**, im **Feed** und im **Impressum** – und er muss überall gleich heissen.

    **Zusammengesetzt wird er nirgendwo sonst.** Das Impressum tat es und schrieb
    ``«Inexxio AG (AG)»``: eine zweite Fassung einer Regel, die eine Ausnahme kennt,
    sieht richtig aus und ist es nicht.

    Bug-Formen: (a) eine Station trägt den blossen Spaltenwert; (b) die Antwort führt den
    Datensatznamen gar nicht; (c) jemand baut ihn ein zweites Mal aus beiden Feldern
    zusammen; (d) das Frontend setzt ihn selbst statt ihn zu lesen.
    """
    places = _code(_read(BACKEND / "app" / "services" / "places.py"))
    for line in places.split("\n"):
        if 'Station(' in line and '"organization"' in line:
            assert "legal_name" in line, (
                "Eine Halter-Station trägt den blossen Spaltenwert (a) – dieselbe "
                f"Gesellschaft hiesse dort anders als auf dem Beleg: {line.strip()}"
            )

    admin = _code(_read(BACKEND / "app" / "routers" / "admin.py"))
    assert admin.count("legal_name") >= 3, (
        "Der Datensatzname fehlt in einer der Antworten (b) – Detail, Gebietskarte und "
        "die öffentliche Auskunft müssen ihn alle drei führen."
    )

    # (c) Keine zweite Zusammensetzung – weder im Backend noch im Browser. Gesucht ist
    # die **Verbindung** beider Angaben in einem Ausdruck, nicht ihr blosses Vorkommen
    # (sie stehen völlig zu Recht nebeneinander in Formular, Schema und Modell).
    joiner = re.compile(
        r"(company_name|companyName)[^\n]{0,40}[+`}][^\n]{0,40}(legal_form|legalForm)"
        r"|(legal_form|legalForm)[^\n]{0,40}[+`}][^\n]{0,40}(company_name|companyName)"
    )
    files = [p for p in (BACKEND / "app").rglob("*.py")]
    files += [p for p in (FRONTEND).rglob("*.ts")] + [p for p in FRONTEND.rglob("*.tsx")]
    for path in files:
        if path.name in ("sites.py", "api.ts"):
            continue
        hit = joiner.search(_code(_read(path)))
        assert hit is None, (
            f"«{path.name}» setzt den Namen ein zweites Mal aus Name und Rechtsform "
            f"zusammen (c): {hit.group(0)!r}. Die Regel steht in ``sites.legal_name``."
        )

    # (d) Der eine Namensgeber des Frontends liest ihn, statt ihn zu bauen.
    names = _code(_read(FRONTEND / "lib" / "record-name.ts"))
    block = _body(names, "organizationName", kind="function")
    assert "legal_name" in block, (
        "``organizationName`` liest den Datensatznamen nicht (d) – dann heisst dieselbe "
        "Gesellschaft im Feed anders als in der Halter-Kette."
    )


def test_a_private_customer_is_named_by_his_own_name():
    """►►► **Der Name auf dem Beleg entsteht an EINER Stelle** (#914, #1042). ◄◄◄

    Die Regel steht in `people.billing_name`: *Firma zuerst, Person als «z. H.»; ohne
    Firma bleibt die Person.* Ein Privatkunde trägt keine Firma – also steht dort sein
    Name.

    ►►► **Und ob eine Firma dasteht, sagt der KONTOTYP** – nicht die Rolle. ◄◄◄ Dieser
    Wächter verbot einmal jedes `is_business` mit der Begründung «die Daten sagen es
    bereits» (#914). Das war die **Form** der damaligen Lösung, nicht die Regel: gefragt
    wurde das blosse Vorhandensein von `company_name`, und *sichtbar* waren die
    Firmenfelder nur bei `role == 'supplier'` – ein Geschäftskunde hatte damit keinen
    Firmennamen, und ein Mitarbeiter sah die Firma seines Arbeitgebers. Genau daraus
    entstand #1042. Der **Kontotyp** ist jetzt die eine Angabe, und was unverändert gilt,
    ist die Zahl der Stellen: **eine**.

    Bug-Formen: (a) der Beleg fragt wieder die **Rolle**, statt den Kontotyp;
    (b) er fragt das blosse Feld (dann trägt ein Privatkonto seinen alten Firmennamen
    wieder auf dem Beleg); (c) die Oberfläche entscheidet selbst, was in den Namen gehört,
    statt zu lesen, was der Server schickt.
    """
    people = _code(_read(BACKEND / "app" / "services" / "people.py"))
    voucher = _code(_read(BACKEND / "app" / "services" / "voucher_head.py"))
    # **Die Rolle, nicht die Beleg-Rolle.** ``voucher`` kennt «supplier»/«customer» als die
    # MWSTG-Rollen des Papiers (Leistungserbringer ↔ -empfänger) – gemeint ist hier die
    # Rolle des *Benutzers*, und die steht als ``.role`` am Datensatz.
    for name, block in (("people.billing_name", _body(people, "billing_name")),
                        ("voucher.billing_of", _body(voucher, "billing_of"))):
        assert ".role" not in block, (
            f"«{name}» fragt die Rolle des Benutzers (a) – der Kontotyp ist die Angabe."
        )
    block = " ".join(_body(people, "billing_name").split())
    assert "is_business(u)" in block, (
        "``billing_name`` fragt nicht den Kontotyp (b) – ein Privatkonto behält seinen "
        "Firmennamen in der Zeile, und er darf nicht mehr auf den Beleg."
    )
    assert "u.company_name" not in block, (
        "``billing_name`` liest das Firmenfeld roh (b) – die Frage lautet, ob der "
        "**Kontotyp** «Geschäft» ist; ``sites.legal_name`` setzt den Namen zusammen."
    )
    block = _body(people, "billing_name")
    assert "z. H." in block, (
        "Die Regel «Firma zuerst, Person als z. H.» steht nicht mehr in "
        "``people.billing_name`` – dann baut sie jemand ein zweites Mal."
    )
    # Der Belegkopf **zeigt** die Zeile, die der Dienst gebaut hat (`view.attn`) – er
    # setzt sie nicht zusammen. Ein «z. H.» im Browser wäre die zweite Regel daneben.
    beleg = _code(_beleg())
    party = " ".join(_component(beleg, "Attn").split())
    assert "side?.attn" in party and "z. H." not in beleg, (
        "Die Oberfläche baut den Namen selbst (b) – sie zeigt, was der Server schickt."
    )


# ---------------------------------------------------------------------------
# ►► DER UMBAU VON «RECHNUNG & ZAHLUNG» + TESTNOTIZEN #979/#981/#982
# ---------------------------------------------------------------------------


def test_a_company_is_named_the_same_in_the_feed_and_in_its_window():
    """►►► **Unternehmensname + Rechtsform – überall dasselbe** (Testnotiz #984). ◄◄◄

    *«ERP-Feed und Header des Detailfensters, zwingend identisch, eine gemeinsame
    Anzeigefunktion.»*

    Die gemeinsame Funktion gab es (`organizationName`) – **die Angabe kam nur nie an**:
    ein handgeschriebener Mapper (`mapSettingsFromBackend`) baute das Objekt Feld für Feld,
    und `legal_name` stand nicht darin. Was ein solcher Mapper nicht nennt, verschwindet
    **still**. Heute gibt es keinen Mapper mehr: das Unternehmen IST der generierte Typ
    (`CompanySettingsResponse`), geändert wird mit `CompanySettingsUpdate` – das die
    abgeleiteten Felder gar nicht kennt.

    Bug-Formen: (a) ein Mapper/eine Abschrift des Typs kehrt zurück und verliert das Feld;
    (b) eine Aufrufstelle baut sich einen eigenen Namen daneben; (c) der abgeleitete Name
    kann zurückgeschickt werden (Änderung typisiert als das ganze Unternehmen).
    """
    api = _code(_read(FRONTEND / "lib" / "api.ts"))
    types = _code(_read(FRONTEND / "types" / "index.ts"))
    assert "mapSettings" not in api and "interface CompanySettings" not in types, (
        "Ein handgeschriebener Mapper bzw. Typ für das Unternehmen ist zurück (a) – was er "
        "nicht nennt, erreicht den Browser nicht, und niemand sieht es."
    )
    assert "CompanySettings = components['schemas']['CompanySettingsResponse']" in types, "(a)"
    # (c) **Abgeleitet heisst: nicht zurückschreiben** – die Änderung hat ihren eigenen Typ.
    assert re.search(r"updateCompany\(objectId: number, data: CompanySettingsUpdate\)", api), (
        "Die Änderung eines Unternehmens ist nicht mehr `CompanySettingsUpdate` (c) – der "
        "abgeleitete Name könnte als zweite Wahrheit zurück an den Server gehen."
    )
    # (b) **Eine Anzeige, ein Aufruf** – im Feed wie in der Kopfzeile, ohne Rückfall.
    detail = _code(_read(FRONTEND / "components" / "erp" / "organization-detail.tsx"))
    head = detail[_at(detail, "<DetailHeader"):]
    head = head[: head.index("/>")]
    assert "organizationName(base)" in head and "form.company_name" not in head, (
        "Die Kopfzeile hat einen eigenen Rückfall (b) – und ausgerechnet einen ohne "
        "Rechtsform."
    )


# ---------------------------------------------------------------------------
# ►► Der Kontotyp und die EINE Rechnungs-E-Mail (Testnotiz #1042)
# ---------------------------------------------------------------------------


def test_the_role_is_the_access_in_every_surface():
    """►►► **Die Rolle beantwortet GENAU EINE Frage: darf sie ins ERP?** (#1043) ◄◄◄

    *«Lieferant ↔ Kunde ist eine Eigenschaft des VORGANGS, nicht der Person.»* Die
    Oberfläche fragte sie an **vier** Stellen – Navbar zweimal, ERP-Layout, ERP-Feed –, und
    eine davon war **verneinend** formuliert («ausser Kunden dürfen alle»): sie liess damit
    jeden Wert durch, den sie nicht kannte, und ein «Lieferant» landete auf einer
    Oberfläche, die ihm der Server danach leer beantwortet.

    Bug-Formen: (a) die Union kennt wieder einen Vorgangs-Wert; (b) sie weicht von der Tür
    ab; (c) eine Stelle fragt die Rolle selbst, statt ``isStaff`` zu rufen; (d) das
    Rollen-Dropdown bietet einen Wert an, den die Tür abweist.
    """
    from app.services import people as pp

    union = re.search(r"export type UserRole = ([^;]+);", _read(FRONTEND / "types" / "index.ts"))
    assert union and sorted(re.findall(r"'(\w+)'", union.group(1))) == sorted(pp.ROLES), (
        f"Die Rollen-Union weicht vom Dienst ab (a/b): {union and union.group(1)}"
    )
    # (c) – **eine** Auflösung, und die anderen rufen sie.
    gate = _code(_read(FRONTEND / "lib" / "record-status.ts"))
    assert "export function isStaff(" in gate, "``isStaff`` fehlt (c)."
    for where in ("components/auth/auth-gate.tsx", "lib/use-feed-lists.ts"):
        src = _code(_read(FRONTEND / where))
        assert "isStaff(" in src, f"«{where}» fragt die Rolle selbst (c)."
        # ►►► **Gefragt ist die ZWEIER-Aufzählung, nicht «admin».** ◄◄◄ Der erste Anlauf
        # verbot auch ``=== 'admin'`` und schlug am ERP-Feed an – der fragt dort eine
        # **andere** Frage («darf ich die Gesellschaften laden?»), und die ist wirklich
        # admin-only. «employee» allein hat dagegen keine eigene Bedeutung: wo es steht,
        # wird das Personal-Paar nachgebaut.
        assert "'employee'" not in src, (
            f"«{where}» zählt die Personal-Rollen daneben auf (c)."
        )
    assert "<AuthGate staffOnly" in _code(_read(FRONTEND / "app" / "(erp)" / "layout.tsx")), (
        "Das ERP-Layout lässt nicht mehr nur Personal hinein (c)."
    )
    # (c′) Der gemeinsame Kopf (Website **und** ERP, WEBSITE_PLAN Entscheid 60) zeigt den
    # ERP-Link nach derselben Frage – er läuft vor jedem Framework und kann `isStaff` nicht
    # importieren, also zählt er das Paar auf; gefragt ist, dass es **dasselbe** ist.
    for where in ("early.js", "account.ts"):
        src = _code(_read(ROOT / "website" / "src" / "scripts" / where))
        pair = re.findall(r"role === '(\w+)'", src)
        assert sorted(pair) == sorted(pp.STAFF_ROLES), (
            f"Der Kopf («{where}») fragt ein anderes Personal-Paar als der Dienst (c′): {pair}"
        )
    # (d) – das Dropdown bietet genau die Werte der Tür an.
    detail = _code(_read(FRONTEND / "components" / "erp" / "user-detail.tsx"))
    block = detail[_at(detail, 'label="Rolle"'):_at(detail, 'label="Rolle"') + 400]
    assert sorted(re.findall(r"value: '(\w+)'", block)) == sorted(pp.ROLES), (
        f"Das Rollen-Dropdown weicht von der Tür ab (d): {block[:200]}"
    )


def test_the_company_is_a_record_in_every_surface():
    """►►► **Die Firma ist ein Datensatz – gewählt, nicht abgetippt** (CRM Schritt 1). ◄◄◄

    Firmenname, Rechtsform und UID standen als Text an jeder Person; zwei Mitarbeiter
    derselben Kundenfirma trugen zwei Fassungen derselben Firma. Jetzt wählen Konto und
    ERP sie über **dasselbe** Bauteil (`CompanyField`), und ihre Angaben pflegt man an
    ihrem eigenen Datensatz.

    Bug-Formen: (a) eine Oberfläche tippt den Firmennamen wieder als Feld an der Person;
    (b) es gibt wieder einen Kontotyp; (c) eine Oberfläche baut ihr eigenes Firmenfeld.
    """
    for where in _USER_SURFACES:
        src = _code(_read(FRONTEND / where))
        assert "account_type" not in src and "isBusiness" not in src, (
            f"«{where}» führt wieder einen Kontotyp (b)."
        )
        assert 'label="Firmenname"' not in src and "company_name" not in src, (
            f"«{where}» tippt die Firma wieder als Text an der Person (a)."
        )
        assert re.search(r"<CompanyField[\s/>]", src), (
            f"«{where}» wählt die Firma nicht über das gemeinsame Bauteil (c)."
        )


def test_the_billing_email_is_one_field_in_every_surface():
    """►►► **Eine Information existiert genau einmal** (Testnotiz #1042). ◄◄◄

    Seit dem Adressbuch (Migration 143) steht die Rechnungs-E-Mail **an der Anschrift**:
    wohin die Rechnung per Post und wohin per E-Mail geht, ist dieselbe Entscheidung. Es
    gibt sie darum genau einmal – im Bauteil ``AddressBook`` –, und keine Oberfläche führt
    daneben ein eigenes Feld.

    Bug-Formen: (a) ``company_billing_email`` ist wieder da; (b) eine Oberfläche führt
    ein eigenes Feld ``invoice_email`` neben dem Adressbuch; (c) ein zweites
    Firmennamen-Feld an der Rechnungsadresse (``invoice_company``); (d) das Adressbuch hat
    das Feld nicht oder zweimal.
    """
    for where in _USER_SURFACES:
        src = _code(_read(FRONTEND / where))
        assert "company_billing_email" not in src, f"«{where}» (a)"
        assert "invoice_company" not in src, f"«{where}» (c)"
        assert "invoice_email" not in src and "Rechnungs-E-Mail" not in src, (
            f"«{where}» führt die Rechnungs-E-Mail neben dem Adressbuch (b).")
        assert "(Firma)" not in src, f"«{where}» beschriftet noch ein Feld mit «(Firma)» (a)."
    book = _code(_read(FRONTEND / "components/erp/address-book.tsx"))
    fields = re.findall(r"label=\"Rechnungs-E-Mail[^\"]*\"", book)
    assert len(fields) == 1, f"Das Adressbuch hat {len(fields)} Felder «Rechnungs-E-Mail» (d)."


def test_the_inheritance_of_the_billing_email_is_visible():
    """**Ist sie leer, wird die Login-/Kontakt-E-Mail verwendet – und das steht da.**

    Der Satz steht an **einer** Stelle (``address-book.inheritedEmail``, sein einziger
    Leser) – zwei Formulierungen wären zwei Aussagen über dieselbe Vererbung.

    Bug-Formen: (a) der Platzhalter nennt nur die Adresse; (b) daneben steht eine
    Checkbox; (c) der Satz steht ausserhalb der einen Funktion ein zweites Mal.
    """
    book = _code(_read(FRONTEND / "components/erp/address-book.tsx"))
    rule = _body(book, "inheritedEmail", kind="function")
    assert "übernimmt" in rule, "Der Satz nennt die Vererbung nicht (a)."
    assert book.count("übernimmt") == 1, "Die Vererbung steht zweimal (c)."
    assert "placeholder={inheritedEmail(" in book, "Das Feld nennt die Vererbung nicht (a)."
    assert not re.search(r"(ToggleField|Segmented)[^>]*Rechnungs-E-Mail", book), "(b)"


def test_addresses_live_in_one_address_book():
    """►►► **Zwei Konten, EINE Maske** – privat und Geschäftskonto, in Konto und ERP. ◄◄◄

    Je Konto eine Adresse, optional eine abweichende Rechnungsadresse (Schalter) und
    weitere Lieferadressen. Konto und ERP zeigen **dasselbe** Bauteil, je einmal für jedes
    Konto. Der Schalter ist eine **Ableitung** aus den Standards des Servers, keine
    gespeicherte Angabe; die Rechnungs-E-Mail gibt es nur im Geschäftskonto.

    Bug-Formen: (a) eine Oberfläche baut ihre eigene Anschrift wieder als Formularfeld;
    (b) ein Konto fehlt an einer Oberfläche; (c) der Schalter wird zu einer gespeicherten
    Angabe; (d) die Oberfläche formuliert die Standards selbst, statt sie vom Server zu
    lesen; (e) die Rechnungs-E-Mail steht auch privat.
    """
    for where in _USER_SURFACES:
        src = _code(_read(FRONTEND / where))
        assert re.search(r"<AddressBook[^>]*account=\"private\"", src), (
            f"«{where}» zeigt das Privatkonto nicht (b).")
        assert re.search(r"<AddressBook[^>]*account=\"business\"", src), (
            f"«{where}» zeigt das Geschäftskonto nicht (b).")
        assert "<AddressField" not in src, f"«{where}» baut eine eigene Anschrift (a)."
        assert "OWN_ADDRESS" not in src and "ownBilling" not in src, f"«{where}» (c)"
        assert not re.search(r"invoice_\w+|address_line1|postal_code", src), (
            f"«{where}» schreibt noch die alten Felder am Benutzer (a).")
    book = _code(_read(FRONTEND / "components/erp/address-book.tsx"))
    assert "a.is_default_delivery" in book and "a.is_default_billing" in book, (
        "Die Standards kommen nicht vom Server (d).")
    assert "Abweichende" not in book and "ToggleField" not in book, (
        "Die Lieferadressen sind eine Liste, kein Schalter (c).")
    assert "Lieferadresse hinzufügen" in book, "Keine Lieferadresse hinzufügbar (c)."
    detail = _code(_read(FRONTEND / "components/erp/user-detail.tsx"))
    assert "onCreate" not in detail and "neu erfassen" not in _read(
        FRONTEND / "components/erp/company-field.tsx"), (
        "Im ERP entsteht eine Firma über «+» im Feed, nicht im Benutzer-Datensatz (#1214).")
    assert "account === 'business'" in book and "email={business" in book, (
        "Die Rechnungs-E-Mail hängt nicht am Geschäftskonto (e).")


def test_a_field_explains_itself_without_a_paragraph():
    """►►► **Zusatzinfo entfallen lassen** (Testnotizen #1043/#1045). ◄◄◄

    Zwei Erklärtexte standen im Benutzer-Formular und beschrieben das **Datenmodell**: was
    die Rolle bedeutet und was ein leerer Firmenname heisst. Beide sagten nichts, was das
    Feld darunter nicht selbst sagt – und ein Formular, das sich erklärt, ist eines, das
    man nicht versteht.

    Bug-Formen: (a) der Satz zur Rolle ist zurück; (b) der zu den Firmendaten.
    """
    for where in _USER_SURFACES:
        src = _read(FRONTEND / where)
        assert "entscheidet der Vorgang" not in src, (
            f"«{where}» erklärt die Rolle wieder in Prosa (a)."
        )
        assert "Leer: eine Privatperson" not in src, (
            f"«{where}» erklärt die Firmendaten wieder in Prosa (b)."
        )


def test_no_person_surface_shows_bank_details():
    """►►► **Eine Bankverbindung gibt es nur bei UNSEREN Gesellschaften.** ◄◄◄

    Sie stand an jeder Person (#1043: «hängt an nichts») – sensible Daten, die niemand
    liest: überwiesen wird an den **Aussteller** eines Belegs, und bezahlt wird über die
    Bankverbindung der eigenen Gesellschaft (QR-Rechnung). Eine IBAN am Kunden ist keine
    Vorsorge, sondern eine Haftung.

    Bug-Form: ein Bankfeld wieder im Formular einer Person. Schema und Modell prüft
    ``test_user_record.test_a_person_carries_no_bank_details``.
    """
    for where in _USER_SURFACES:
        src = _code(_read(FRONTEND / where))
        for field in ("bank_iban", "bank_bic", "bank_name", "bank_account_holder"):
            assert field not in src, f"«{where}» trägt wieder «{field}»."


def test_the_legal_form_suggestions_exist_exactly_once():
    """**EINE Liste Rechtsformen, zwei Aufrufstellen** (Testnotiz #1042, #303).

    Sie lag in ``organization-detail.tsx`` – dort wird die Rechtsform **unserer**
    Gesellschaften gepflegt. Seit ein Geschäftskonto am Benutzer dieselbe Angabe trägt,
    fragt eine zweite Stelle sie; kopiert wäre sie die Liste, die beim nächsten Land
    auseinanderläuft.

    Bug-Form: eine zweite Definition (dann kennt der Benutzer andere Rechtsformen als das
    Unternehmen).
    """
    # ►►► **Gefragt sind NAME und INHALT.** ◄◄◄ Beide Anläufe davor waren stumpf, und
    # zwar gegen je eine der zwei Formen, in denen eine Kopie entsteht: nach Dateien
    # gezählt blieb eine zweite Definition in derselben Datei grün, und nach dem **Namen**
    # gezählt blieb jede Kopie grün, die anders heisst. Also beides – der Name findet die
    # abgeschriebene Funktion, eine Rechtsform, die es nur hier gibt, die abgeschriebenen
    # Werte.
    def _spots(needle: str) -> list[tuple[str, int]]:
        return [(p.relative_to(FRONTEND).as_posix(), n)
                for p in sorted(FRONTEND.rglob("*.ts*")) if p.is_file()
                for n in [len(re.findall(needle, _code(_read(p))))] if n]

    for needle in (r"LEGAL_FORMS_BY_ISO2\s*(?::|=)", r"Kollektivgesellschaft"):
        assert _spots(needle) == [("lib/legal-forms.ts", 1)], (
            f"Die Rechtsform-Liste steht nicht genau einmal: {_spots(needle)}"
        )
    for where in ("components/erp/organization-detail.tsx",
                  "components/erp/company-field.tsx",
                  "components/erp/new-record.tsx"):
        src = _code(_read(FRONTEND / where))
        assert "legalForms(" in src, f"«{where}» fragt die gemeinsame Liste nicht."


# ---------------------------------------------------------------------------
# ►► TESTNOTIZ #1044 — das Adressfeld hat EIN Gesicht, und die Region kommt an
# ---------------------------------------------------------------------------


def test_the_address_mode_is_a_derivation_not_a_latch():
    """►►► **Manchmal Suche, manchmal Formular — das war ein WETTLAUF.** ◄◄◄

    *«Die Adresse wird manchmal mit dem Google-Maps-Suchdesign gerendert und manchmal
    wechselt sie zu einem einfachen Eingabeformular.»* (Testnotiz #1044)

    Der Schlüssel kommt aus den Einstellungen und ist beim **ersten** Rendern noch nicht
    da; ``useGoogleMaps`` meldete dafür ``no-key``, und ein Effekt setzte daraufhin
    ``manual = true`` – **für immer**. Wer den Datensatz als Erstes in der Sitzung
    öffnete, bekam das Formular, beim zweiten Mal (Schlüssel gecacht) die Suche: dieselbe
    Oberfläche, zwei Gesichter.

    Jetzt trägt der Zustand nur die **Wahl des Menschen**, der Modus folgt daraus – und
    solange die Antwort fehlt, wird **nicht entschieden** (``pending``).

    Bug-Formen: (a) der Latch ist zurück (ein Effekt setzt den Modus aus ``error``);
    (b) der Modus ist wieder ein Zustand statt einer Ableitung; (c) «noch nicht bekannt»
    und «es gibt keinen» sind wieder derselbe Wert; (d) ``useGoogleMaps`` antwortet auf
    ein unbekanntes ``undefined`` mit ``no-key``.
    """
    src = _address_field()
    assert "setManual(" not in src, (
        "Der Modus wird wieder gesetzt (a/b) – ein Einbahn-Schalter aus einem "
        "vorübergehenden Zustand ist genau der gemeldete Fehler."
    )
    assert re.search(r"const manual = wantsManual \|\|", src), (
        "Der Modus ist keine Ableitung mehr (b)."
    )
    assert "pending" in src, "Ohne «noch nicht bekannt» entscheidet er zu früh (c)."
    key = _code(_read(FRONTEND / "lib" / "use-maps-key.ts"))
    assert re.search(r"useMapsApiKey\(\): string \| null \| undefined", key), (
        "Der Schlüssel unterscheidet «noch nicht bekannt» nicht von «es gibt keinen» (c) "
        "– gefragt ist seine ANTWORT, nicht der Typ seines inneren Zustands."
    )
    maps = _code(_read(FRONTEND / "lib" / "use-google-maps.ts"))
    assert "if (apiKey === undefined) return;" in maps, (
        "Ein unbekannter Schlüssel wird wie ein fehlender behandelt (d)."
    )


def test_a_google_hit_fills_the_region():
    """►►► **Die Region kam von Google nie an** (Testnotiz #1044). ◄◄◄

    *«Zudem wird in dieser Variante die Region nicht korrekt befüllt.»* – Sie stand als
    Feld im manuellen Modus, wurde aber beim Einlesen eines Treffers **nicht gelesen**:
    ein Treffer liess sie unberührt, also blieb die des *vorherigen* Ortes stehen. Und in
    der Zusammenfassung des gefüllten Feldes fehlte sie ganz – was von einer nicht
    gespeicherten Angabe nicht zu unterscheiden ist.

    Bug-Formen: (a) der Treffer wird nicht nach der Region gefragt; (b) sie wird nicht
    übernommen; (c) die Zusammenfassung verschweigt sie.
    """
    src = _address_field()
    assert "administrative_area_level_1" in src, (
        "Der Treffer wird nicht nach der Region gefragt (a)."
    )
    apply = _body(src, "applyPlace", kind="function")
    assert re.search(r"region: p\.region", apply), (
        "Die Region eines Treffers wird nicht übernommen (b)."
    )
    assert "showRegion && value.region" in src, (
        "Die Zusammenfassung zeigt die Region nicht (c) – wer sie erfasst, sieht sie "
        "beim nächsten Blick nicht mehr."
    )


# ---------------------------------------------------------------------------
# ►► TESTNOTIZEN #1046/#1047/#1049 — am Beleg
# ---------------------------------------------------------------------------


def test_a_late_profile_cannot_undo_a_logout():
    """►►► **Erst abmelden, dann räumen – und wer NACH einem ``await`` schreibt, fragt
    nach, ob die Sitzung noch besteht.** ◄◄◄

    Auf ``/abmelden`` läuft auch ``AccountSync``: sein Profil-Abruf kam nach dem Räumen des
    Anzeige-Caches an und schrieb Name und Rolle zurück – die Website zeigte weiter einen
    Angemeldeten, man musste zweimal abmelden.

    Bug-Formen: (a) der Schreiber prüft die Sitzung nicht nach dem ``await``; (b) ``logout``
    räumt vor ``signOut`` bzw. nicht im ``finally``.
    """
    sync = _code(_read(FRONTEND / "components" / "layout" / "account-sync.tsx"))
    check, write = sync.find("currentUid() !== user.uid"), sync.find("rememberRole(")
    assert -1 < sync.find("await api.getMe()") < check < write, "(a)"
    fb = _code(_read(FRONTEND / "lib" / "firebase.ts"))
    body = fb[fb.index("export async function logout"):fb.index("export function currentUid")]
    assert body.index("signOut(auth)") < body.index("finally") < body.index("clearAccountCache()"), "(b)"


def test_a_customer_names_its_firm_and_only_staff_picks_from_a_list():
    """►►► **Kunden sehen keine fremden Firmen** (CRM, Migration 143). ◄◄◄

    Im **Konto** wird die Firma *genannt* (UID, sonst Name und Rechtsform) – ohne Liste
    bestehender Firmen; im **ERP** wählt das Personal aus ihr. Und es gibt keinen Weg
    mehr, als Kunde die Angaben einer Firma zu ändern.

    Bug-Formen: (a) das Konto bekommt die Firmensuche; (b) das ERP verliert sie; (c) die
    Suche steht ohne Bedingung im Bauteil; (d) der Pflegeweg ``updateMyCompany`` ist
    zurück.
    """
    prof = _code(_read(FRONTEND / "components/account/sections/profile-section.tsx"))
    erp = _code(_read(FRONTEND / "components/erp/user-detail.tsx"))
    mine = re.search(r"<CompanyField(.*?)/>", prof, re.S)
    theirs = re.search(r"<CompanyField(.*?)/>", erp, re.S)
    assert mine and not re.search(r"\bsearch\b", mine.group(1)), "(a)"
    assert theirs and re.search(r"\bsearch\b", theirs.group(1)), "(b)"
    field = _code(_read(FRONTEND / "components/erp/company-field.tsx"))
    at = field.index("<ObjectSelect")
    assert "{search ? (" in field[max(0, at - 120):at], "(c)"
    for where in ("components/erp/company-field.tsx", "lib/api.ts",
                  "components/account/sections/profile-section.tsx"):
        src = _code(_read(FRONTEND / where))
        assert "updateMyCompany" not in src and "CompanyEditor" not in src, f"«{where}» (d)"
