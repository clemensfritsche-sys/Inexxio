"""**Die geschlossene Liste der Prozessschrittmodule — die eine Stelle.**

Schlüssel, Übergang und erlaubte ``config`` jedes Moduls stehen hier; ein Modultyp, den es
hier nicht gibt, ist nicht anlegbar. **Der Übergang gehört zum Modul, nicht zum Anwender**:
Wer ein Modul passiert und weiterläuft, bleibt «Im Prozess»; einen Übergang je Schritt
gibt es nicht (``Module.exit_status_for`` sagt, was beim Hinausgehen geschieht).
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from . import capture_types, competences, sampling, statuses as st
from . import voucher as vo
from .errors import Invalid

#: Der eine Ortsbedarf, den es heute gibt: **beim Produkt**. Eine geschlossene Liste wie
#: ``Aussondern.MODES``.
AT_PRODUCT = "product"

DATENERFASSUNG = "datenerfassung"
AUSSONDERN = "aussondern"
VERBRAUCH = "verbrauch"
BEWEGEN = "bewegen"
#: ►►► **Das Zahlungsmodul – Schlüssel ``beleg``.** ◄◄◄ Der Schlüssel ist eine Adresse in
#: eingefrorenen Prozessen (die Sache), die Beschriftung die Handlung («Zahlung»).
BELEG = "beleg"


class Module:
    """Ein Modultyp. Was ihn ausmacht: sein Übergang und die Form seiner Konfiguration."""

    #: **Darf ein Stück diesen Modultyp verlassen, während davor gearbeitet wird?**
    #: Bewusster Haken (SYSTEM_LOGIC R7), gelesen nur in ``release._assert_may_leave``; wer
    #: ``False`` setzt, beantwortet den Abbruch-Ausgang (§4.4) mit.
    units_may_leave: bool = True

    #: **Muss die Instanz vor der Eingabe verifiziert werden?** (Scan-Pflicht) Global;
    #: abschaltbar nur für einen Modultyp ohne physischen Bezug.
    requires_verification: bool = True

    #: **Wo muss das Material dieses Moduls liegen?** Vorgabe: nirgends.
    #:
    #: Abgeleitet, nicht konfiguriert: ``AT_PRODUCT`` heisst «dort, wo mein Produkt liegt» –
    #: kein zweites Ortsfeld neben dem Ziel des Bewegen-Moduls. «Am falschen Ort» ist eine
    #: Spalte in ``StepNeed``, kein Zustand (§9.6).
    material_place: Optional[str] = None

    #: **Verlassen ALLE ankommenden Stücke den Auftrag hier?** Dann ist das Modul ein
    #: **Ausgang**: dahinter steht nichts (``chain.assert_closes``), es passiert nicht das
    #: Ende-Objekt (``_finish``) und schneidet damit eine Rückführung ab. Der Verbrauch ist
    #: nicht terminal – Komponenten treten dort ein und gehen im selben Zug
    #: (``process._enter_at_step``), das Produkt läuft weiter.
    terminal: bool = False

    #: **Bewegt dieses Modul die Stücke?** Vorgabe: nein. Die Oberfläche fragt danach,
    #: nie nach dem Modultyp.
    moves: bool = False

    #: **Lässt dieses Modul die Stücke von selbst durch?** ``None`` (Vorgabe): nein, ein
    #: Mensch bestätigt. Sonst der Satz, warum es keinen «Bestätigen»-Knopf gibt – dann zieht
    #: der Prozess die Stücke weiter, sobald das Modul es erlaubt (``process.carry_on``).
    #: Eine Eigenschaft wie ``terminal``: der Kern fragt sie, nie den Modultyp.
    passes_itself: Optional[str] = None

    def __init__(self, key: str, label: str, tone: str, competence: Optional[str] = None):
        self.key = key
        self.label = label
        #: **Welche Kompetenz ein Schritt dieses Moduls braucht** – die Vorgabe; am Schritt
        #: lässt sie sich gegen eine aus ``domain/competences`` tauschen (``clean_step``).
        #: Jedes Modul in ``MODULES`` nennt eine (Wächter ``test_tasks``).
        self.competence = competences.clean(competence)
        #: **Die Farbfamilie dieses Modultyps** – ein Wort, das das Frontend auf Tokens
        #: abbildet (``lib/modules.MODULE_TONE``). Getrennt von der Ampel: ein Modul ist
        #: kein Zustand (PROCESS_CORE.md §5.3).
        self.tone = tone

    def clean_config(self, raw: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Die Konfiguration prüfen und normalisieren. Ohne Konfiguration: ``None``."""
        return None

    def clean_step(self, raw: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """►► **Die Konfiguration eines Schritts** – die des Moduls (``clean_config``) und, für
        jedes Modul gleich, die am Schritt gewählte Kompetenz (``competence``; leer oder gleich
        der Vorgabe = nicht gespeichert). Die eine Stelle, durch die jeder Schritt geht. ◄◄"""
        rest = dict(raw or {})
        chosen = competences.clean(rest.pop("competence", None))
        config = self.clean_config(rest or None)
        if chosen and chosen != self.competence:
            config = {**(config or {}), "competence": chosen}
        return config

    def competence_of(self, config: Optional[dict[str, Any]]) -> Optional[str]:
        """Welche Kompetenz ein Schritt mit dieser Konfiguration braucht."""
        return (config or {}).get("competence") or self.competence

    def config_schema(self) -> dict[str, Any]:
        """►►► **Die Form der Konfiguration als JSON-Schema** – die andere Form von
        ``clean_config``, direkt daneben: dieselben Felder, je mit einem kurzen Satz, dazu
        gültige Beispiele (``examples``). ◄◄◄

        Daraus beschreibt sich jede Route, die Schritte nimmt (``schemas/process.ModuleInput``),
        und daraus kennt die KI die Einstellungen eines Moduls – ohne einen Satz über Prozesse
        im Auftrag. Geprüft wird weiter allein in ``clean_config``; dass beide dieselben
        Felder kennen, hält ``tests/test_module_config_schema.py``. Vorgabe: keine Einstellung."""
        return _schema({}, examples=[{}])

    #: Was der Knopf sagt, der dieses Modul ausführt – ein Verb, kein Modulname.
    action: str = "Erfassen & bestätigen"

    def action_for(self, config: Optional[dict[str, Any]]) -> str:
        """Wie heisst die Ausführung dieses Moduls? Vorgabe: sein ``action``; ein Typ darf
        dafür seine Konfiguration lesen (Aussondern: «Verschrotten» · «Sperren»)."""
        return self.action

    def movement_for(self, config: Optional[dict[str, Any]], *,
                     target: Optional[int]) -> Optional[int]:
        """**Wohin bringt dieses Modul die Stücke?** – die Objektnummer des Halters, oder
        ``None`` (Vorgabe: es bewegt nichts). Wie ``consumption.plan``: die
        Ausführungsstelle muss den Modultyp nicht kennen.
        """
        return None

    @staticmethod
    def _object_id(value: Any) -> Optional[int]:
        """**Eine Objektnummer lesen** – oder ``None``, wenn dort keine steht. Was ein
        fehlender Wert bedeutet, sagt der Aufrufer; hier wird nur gelesen.
        """
        if value in (None, "", 0):
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    def exit_status_for(self, config: Optional[dict[str, Any]]) -> Optional[str]:
        """Auf welchen Zustand setzt dieses Modul ein Stück, das **hier hinausgeht**?
        ``None`` (Vorgabe): hier geht niemand hinaus.

        **Wer weiterläuft, bleibt «Im Prozess»** – an jedem Modul. Ein Zustand ändert sich nur
        beim Hinausgehen: an einem Ausgang (Aussondern) oder für die Komponenten des
        Verbrauchs. Darum speichert ein Schritt keinen Übergang (PROCESS_CORE §4)."""
        return None


class Datenerfassung(Module):
    """Im Prozess laufend Daten erfassen und kontrollieren (Richtung Qualitätssicherung).

    **Durchläufer** (``Im Prozess`` → ``Im Prozess``). Ein «nicht bestanden» ist eine
    Aussage über die Messung, kein Ereignis im Prozess (PROCESS_CORE.md §12.5).
    """

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        return {
            "points": capture_types.clean_points((raw or {}).get("points")),
            # Wie viele der wartenden Stücke erfasst werden (``domain/sampling``); ohne
            # Angabe alle. Gezogen wird zur Laufzeit.
            "sample": sampling.clean((raw or {}).get("sample")),
        }

    def config_schema(self) -> dict[str, Any]:
        return _schema({
            "points": {"type": "array", "minItems": 1, "items": capture_types.point_schema(),
                       "description": "Die Erfassungspunkte, mindestens einer; jeder ist Pflicht"},
            "sample": sampling.SCHEMA,
        }, required=["points"],
            examples=[{"points": capture_types.example_points(), "sample": {"percent": 25}}])


class Aussondern(Module):
    """Einzelinstanzen **aus dem Verkehr ziehen** – verschrotten oder sperren.

    Zwei Fälle, ein Modul: der Zielzustand ist ein **Parameter**. Was ankommt, wird
    ausgesondert – ohne Auswahl, ohne Stichprobe. **Der Grund ist Pflicht und wird beim
    Modellieren gegeben** (eine Eigenschaft des Ablaufs, nicht eine Frage am Band); ohne
    Grund ist das Modul nicht anlegbar – für beide Ausprägungen.
    """

    #: Die beiden Ausprägungen und der Zustand, auf den jede setzt – nur hier.
    MODES: dict[str, str] = {"scrap": st.VERSCHROTTET, "block": st.GESPERRT}
    DEFAULT_MODE = "scrap"

    terminal = True

    #: Wie lang der Grund höchstens sein darf.
    REASON_MAX = 200

    #: Das Verb je Ausprägung – dieselbe Zuordnung wie ``MODES``, andere Spalte.
    ACTIONS: dict[str, str] = {"scrap": "Verschrotten", "block": "Sperren"}

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        mode = ((raw or {}).get("mode") or self.DEFAULT_MODE)
        if mode not in self.MODES:
            raise Invalid(f"«{mode}» ist keine Aussonderungs-Art. Erlaubt: "
                    + ", ".join(self.MODES) + ".")
        reason = str((raw or {}).get("reason") or "").strip()
        if not reason:
            raise Invalid("«Aussondern» braucht einen Grund – ohne ihn steht später da, dass "
                    "Stücke ausgesondert wurden, aber nicht warum.")
        if len(reason) > self.REASON_MAX:
            raise Invalid(f"Der Grund ist zu lang (max. {self.REASON_MAX} Zeichen).")
        # Keine Erfassungspunkte: der Scan ist die Bestätigung, der Grund steht in der
        # Definition.
        return {"mode": mode, "reason": reason, "points": [],
                "sample": dict(sampling.DEFAULT)}

    def config_schema(self) -> dict[str, Any]:
        return _schema({
            "mode": {"type": "string", "enum": list(self.MODES), "default": self.DEFAULT_MODE,
                     "description": "Was mit den Stücken geschieht: " + ", ".join(
                         f"{k} = {self.ACTIONS[k]} ({v})" for k, v in self.MODES.items())},
            "reason": {"type": "string", "maxLength": self.REASON_MAX,
                       "description": "Warum ausgesondert wird – Pflicht, beim Modellieren"},
        }, required=["reason"], examples=[{"mode": "scrap", "reason": "Riss im Gehäuse"}])

    def _mode(self, config: Optional[dict[str, Any]]) -> str:
        return (config or {}).get("mode") or self.DEFAULT_MODE

    def exit_status_for(self, config: Optional[dict[str, Any]]) -> Optional[str]:
        return self.MODES[self._mode(config)]

    def action_for(self, config: Optional[dict[str, Any]]) -> str:
        return self.ACTIONS[self._mode(config)]


class Verbrauch(Module):
    """Einzelinstanzen **in ein anderes Stück einbauen** – der Zwilling des Aussonderns.

    Die Komponenten **treten hier ein** (``process._enter_at_step``) und verlassen den
    Auftrag im selben Zug; das Produkt läuft weiter, darum **nicht** ``terminal``.
    **Gebunden wird beim Erreichen, nicht bei der Freigabe**: ``Freigegeben`` → (Scan) →
    ``Im Prozess`` → (Bestätigen) → ``Verbaut``, beides im Log. Keine Reservierung; die
    Stückliste ist eine Ableitung aus dem Log (``services/genealogy``) und überlebt eine
    Demontage.
    """

    #: Je Zeile **Artikel (Objektnummer) + Menge pro Einzelinstanz**. Die Menge gilt je
    #: Produkt-Stück und wird beim **Erreichen** des Moduls gerechnet.
    LINES = "lines"

    #: Höchstmenge je Zeile – mehr ist ein Tippfehler oder das falsche Modul.
    MAX_PER_UNIT = 1000

    #: Das Verb auf dem Knopf – erfasst wird nichts, der Scan ist die Bestätigung.
    action = "Verbauen"

    #: **Die Komponenten müssen dort liegen, wo das Produkt liegt.**
    material_place = AT_PRODUCT

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        found = (raw or {}).get(self.LINES) or []
        if not isinstance(found, (list, tuple)):
            raise Invalid("«Verbrauch» erwartet eine Liste aus Artikel und Menge.")
        lines: list[dict[str, int]] = []
        seen: set[int] = set()
        for row in found:
            article, quantity = self._one(row)
            if article in seen:
                raise Invalid(f"Artikel {article} steht zweimal in der Stückliste. Zwei Zeilen "
                        f"für denselben Artikel sind eine Menge, die man addieren muss – "
                        f"und zwei Stellen, an denen sie auseinanderlaufen kann.")
            seen.add(article)
            lines.append({"article": article, "quantity": quantity})
        if not lines:
            raise Invalid("«Verbrauch» braucht mindestens eine Zeile – sonst gibt es nichts zu "
                    "verbauen, und das Modul wäre ein Durchgang, der so aussieht wie "
                    "eine Montage.")
        # Keine Erfassungspunkte, keine Stichprobe: was gebraucht wird, wird verbaut.
        return {self.LINES: lines, "points": [], "sample": dict(sampling.DEFAULT)}

    def config_schema(self) -> dict[str, Any]:
        return _schema({
            self.LINES: {"type": "array", "minItems": 1, "description":
                         "Die Stückliste: je Zeile ein Artikel, jeder Artikel höchstens einmal",
                         "items": {"type": "object", "required": ["article", "quantity"],
                                   "properties": {
                                       "article": _object_id("Der Artikel, der verbaut wird"),
                                       "quantity": {"type": "integer", "minimum": 1,
                                                    "maximum": self.MAX_PER_UNIT,
                                                    "description": "Menge je Produkt-Stück"}}}},
        }, required=[self.LINES],
            examples=[{self.LINES: [{"article": 100000101, "quantity": 4}]}])

    @staticmethod
    def _one(row: Any) -> tuple[int, int]:
        """Eine Zeile prüfen: **Artikel + Menge pro Stück**, beide Pflicht."""
        if not isinstance(row, dict):
            raise Invalid(f"«{row}» ist keine Stücklisten-Zeile (Artikel und Menge).")
        try:
            article = int(row.get("article"))
        except (TypeError, ValueError):
            raise Invalid(f"«{row.get('article')}» ist keine Artikel-Objektnummer.")
        try:
            quantity = int(row.get("quantity"))
        except (TypeError, ValueError):
            raise Invalid(f"Artikel {article}: die Menge fehlt. Sie gilt **pro Einzelinstanz** – "
                    f"«4» heisst vier Stück je Produkt, nicht vier im ganzen Auftrag.")
        if not 1 <= quantity <= Verbrauch.MAX_PER_UNIT:
            raise Invalid(f"Artikel {article}: die Menge muss zwischen 1 und "
                    f"{Verbrauch.MAX_PER_UNIT} liegen.")
        return article, quantity

    def exit_status_for(self, config: Optional[dict[str, Any]]) -> Optional[str]:
        """Der Zustand der **Komponenten**, die dieses Modul zieht.

        Nicht der der ankommenden Stücke: die laufen weiter («Im Prozess»). Das ist
        der ganze Unterschied zum Aussondern – dort ist beides dasselbe, weil dort nichts
        weiterläuft.
        """
        return st.VERBAUT


class Bewegen(Module):
    """Einzelinstanzen an einen **Halter** bringen (``services/places``).

    **Ein Durchläufer**: ein Ort ändert nie Status oder Zugehörigkeit. **Das Ziel ist
    optional**: steht es in der Definition, verifiziert der Ziel-Scan dagegen; fehlt es,
    wählt der Ausführende – sichtbar verschieden (``ModuleFacts.target``). Hier wird nur
    die Form geprüft; Existenz und Kreisfreiheit prüft ``places.assert_placeable``.
    """

    #: Der Schlüssel der einen Einstellung. ``None`` heisst «wird beim Ausführen gewählt».
    TARGET = "target"

    #: Es bewegt – daraus folgt in der Oberfläche der Ziel-Scan.
    moves = True

    #: Was der Knopf sagt: **«Bestätigen»** – gescannt sind Ware und Ziel schon, der Knopf
    #: bucht die Ablage.
    action: str = "Bewegung bestätigen"

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        data = raw or {}
        target = self._as_object_id(data.get(self.TARGET))
        # Eine optionale Angabe; Erfassungspunkte und Stichprobe stehen leer da, damit jede
        # Lesestelle dieselbe Form vorfindet.
        return {self.TARGET: target,
                "points": [], "sample": dict(sampling.DEFAULT)}

    def config_schema(self) -> dict[str, Any]:
        return _schema({
            self.TARGET: {"type": ["integer", "null"], "description":
                          "Wohin die Stücke gebracht werden (Objektnummer eines Halters: "
                          "Instanz, Person, Unternehmen); leer = wird beim Ausführen gewählt"},
        }, examples=[{self.TARGET: 100000123}, {self.TARGET: None}])

    def _as_object_id(self, value: Any) -> Optional[int]:
        """**Das Ziel** – gelesen mit ``Module._object_id``; leer heisst «wird beim
        Ausführen gewählt», alles andere Unlesbare ist ein Fehler."""
        if value in (None, "", 0):
            return None
        number = self._object_id(value)
        if number is None:
            raise Invalid(f"«{value}» ist keine Objektnummer. Das Ziel von «Bewegen» ist "
                        f"ein Regal, eine Person oder ein Unternehmen – oder es bleibt "
                        f"leer und wird beim Ausführen gewählt.")
        return number

    def movement_for(self, config: Optional[dict[str, Any]], *,
                     target: Optional[int]) -> int:
        """Wohin geht es – und ist das mit der Definition vereinbar?"""
        planned = (config or {}).get(self.TARGET)
        scanned = self._as_object_id(target)
        if planned and scanned and int(scanned) != int(planned):
            raise Invalid(f"Dieses Modul bringt die Stücke zu {planned}, gescannt wurde "
                        f"{scanned}. Wer woanders hinlegt, ändert den Ablauf – dafür gibt "
                        f"es den Abweichungsauftrag, nicht den Scanner.")
        goal = planned or scanned
        if not goal:
            raise Invalid("Dieses Modul hat kein festes Ziel – ohne gescannten Zielort "
                        "steht nicht fest, wohin die Stücke gebracht wurden.")
        return int(goal)


class Beleg(Module):
    """►►► **Geld mit einer zweiten Partei — als Beleg gedacht.** ◄◄◄

    Fachkern in ``domain/voucher``. Angebotsspiegel als Tabelle, die Position in einer
    Form, jedes Verb an einer Stelle.

    ## Die Angaben

    ``direction``    **Kommt Geld herein oder geht es hinaus?** Daraus folgt jedes Wort.
    ``parties``      Die **zugelassenen** Gegenparteien; **leer heisst frei**. Je Zeile
                     «Wie bestellen?» (``vo.ORDER_REF``), nur wo wir bestellen
                     (``Direction.party_ref``).
    ``instruction``  **Was ist zu tun?** (``vo.TASK``) – freiwillig, leer heisst «gemäss
                     Spezifikation».

    Was gehandelt wird, sagen die Einzelinstanzen vor dem Modul. **Vorgeben** darf das
    Modul, was für jeden Auftrag gleich ist: Fristen, Lieferbedingung, Eigentum
    (``PRESETS``) und bei einer Einnahme den Einzelpreis je Artikel (``PRICES``).

    ## Es bewegt keine Stücke

    Ein **Durchläufer**, ``terminal = False``, ``moves = False`` – darum muss keine andere
    Regel von ihm wissen.
    """

    passes_itself = ("Die Stücke ziehen von selbst weiter – mit der Zusage, bei einer "
                     "Vorauszahlung mit dem Geld.")

    #: Die **drei** Schlüssel der Konfiguration – hier und nirgends sonst als Zeichenkette.
    DIRECTION = "direction"
    PARTIES = "parties"
    INSTRUCTION = "instruction"
    #: Die beiden Schlüssel **einer Zeile** der Freigabe-Liste.
    PARTY = "party"
    REF = "ref"

    #: Mehr ist keine Auswahl mehr, sondern eine Adressliste.
    MAX_PARTIES = 10
    #: Eine Artikelnummer oder ein Link – kein Bestelltext.
    MAX_REF = 200

    #: ►►► **Kein Scan.** ◄◄◄ Dieses Modul tut mit dem Stück nichts physisch.
    requires_verification = False

    #: ►►► **Was das Modul dem Beleg vorgeben DARF** – fest im Beleg, punktiert, Grund im
    #: Hover («Im Modul vorgegeben»). ◄◄◄ Was leer bleibt, wählt der Mensch am Beleg.
    PRESETS: tuple[str, ...] = ("payment_days", "lead_days", "valid_days", "incoterm",
                                "ownership")
    PRESET_LABELS: dict[str, str] = {
        "payment_days": vo.PAYMENT_TERM_LABEL, "lead_days": vo.LEAD_TERM_LABEL,
        "valid_days": vo.VALID_LABEL, "incoterm": "Lieferbedingung",
        "ownership": vo.OWNERSHIP_LABEL,
    }

    def action_for(self, config: Optional[dict[str, Any]]) -> str:
        """**Es gibt keinen Knopf**: die Stücke ziehen von selbst weiter, mit der Zusage
        (bei einer Vorauszahlung mit dem Geld). Das Wort beschreibt, was geschieht."""
        return "Zieht von selbst weiter"

    @classmethod
    def presets_of(cls, config: Optional[dict[str, Any]]) -> dict[str, Any]:
        """**Die Vorgaben des Moduls** – nur, was wirklich gesetzt ist."""
        data = config or {}
        return {k: data[k] for k in cls.PRESETS if data.get(k) not in (None, "")}

    #: ►►► **Preise als Vorgabe** – je Artikel ein Einzelpreis, netto, in der Hauswährung. ◄◄◄
    #: Nur bei einer Einnahme; ohne Preis setzt ihn der Mensch in der Offerte. Den
    #: Steuersatz entscheidet die Anschrift (``voucher_head.fit_to_address``).
    PRICES = "prices"
    #: Mehr ist keine Vorgabe mehr, sondern eine Preisliste.
    MAX_PRICES = 50

    @classmethod
    def prices_of(cls, config: Optional[dict[str, Any]]) -> dict[int, Decimal]:
        """**Die vorgegebenen Preise** – Objektnummer des Artikels → Einzelpreis (netto).

        Gelesen tolerant (geschrieben wurde streng, ``_clean_prices``): eine Zeile, die sich
        nicht lesen lässt, gibt keinen Preis vor – sie macht ihn nicht zu null.
        """
        out: dict[int, Decimal] = {}
        for row in (config or {}).get(cls.PRICES) or []:
            try:
                out[int(row["article"])] = Decimal(str(row["price"]))
            except (KeyError, TypeError, ValueError, InvalidOperation):
                continue
        return out

    def _clean_prices(self, value: Any, flow: "vo.Direction") -> list[dict[str, Any]]:
        """Die Preis-Vorgaben **streng** prüfen. Leer ist die Regel: der Preis kommt in der
        Offerte."""
        from . import currency as cur
        if value in (None, ""):
            return []
        if not isinstance(value, (list, tuple)):
            raise Invalid("Vorgegebene Preise sind eine Liste je Artikel.")
        if value and flow.quoted_by != vo.BY_US:
            raise Invalid(f"Bei einer «{flow.label}» nennt die Partei den Preis – vorgeben lässt er "
                f"sich nur, wo wir ihn nennen.")
        if len(value) > self.MAX_PRICES:
            raise Invalid(f"Höchstens {self.MAX_PRICES} vorgegebene Preise je Modul.")
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for entry in value:
            raw = entry if isinstance(entry, dict) else {}
            number = self._object_id(raw.get("article"))
            if number is None:
                raise Invalid("Zu einem vorgegebenen Preis gehört ein Artikel.")
            if number in seen:
                raise Invalid(f"Artikel {number} hat schon einen vorgegebenen Preis.")
            try:
                price = vo.amount(raw.get("price"), cur.DEFAULT)
            except ValueError as e:
                raise Invalid(str(e))
            if price is None:
                raise Invalid(f"Zu Artikel {number} fehlt der Preis.")
            seen.add(number)
            rows.append({"article": number, "price": str(price)})
        return rows

    def _clean_presets(self, data: dict[str, Any]) -> dict[str, Any]:
        """Die Vorgaben streng prüfen – leer heisst «wählt der Mensch am Beleg»."""
        from . import incoterms as inc
        out: dict[str, Any] = {}
        try:
            for key in ("payment_days", "lead_days", "valid_days"):
                days = vo.assert_days(key, data.get(key))
                if days is not None:
                    out[key] = days
            if data.get("incoterm"):
                out["incoterm"] = inc.assert_incoterm(data.get("incoterm"))
            if data.get("ownership"):
                out["ownership"] = vo.assert_ownership(data.get("ownership"))
        except ValueError as e:
            raise Invalid(str(e))
        return out

    def direction_of(self, config: Optional[dict[str, Any]]) -> str:
        """**Die Richtung dieses Schritts** – die eine Lesestelle (eine Einstellung in der
        ``config``); ohne Angabe Ausgabe."""
        return str((config or {}).get(self.DIRECTION) or vo.OUT)

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        data = raw or {}
        try:
            direction = vo.assert_direction(data.get(self.DIRECTION))
        except ValueError as e:
            raise Invalid(str(e))
        flow = vo.of(direction)
        # Keine Erfassungspunkte, keine Stichprobe. Alles andere (Steuersatz, Sperre,
        # Betrag) wird verworfen – ein Feld, das die Oberfläche nicht anbietet, nimmt
        # der Dienst nicht an.
        return {
            self.DIRECTION: direction,
            self.PARTIES: self._clean_parties(data.get(self.PARTIES), flow),
            self.INSTRUCTION: self._clean_instruction(data.get(self.INSTRUCTION)),
            **self._clean_presets(data),
            self.PRICES: self._clean_prices(data.get(self.PRICES), flow),
            "points": [], "sample": dict(sampling.DEFAULT),
        }

    def config_schema(self) -> dict[str, Any]:
        from . import incoterms as inc
        days = {"type": "integer", "minimum": 0, "maximum": 365}
        return _schema({
            self.DIRECTION: {"type": "string", "enum": list(vo.DIRECTIONS), "description":
                             "; ".join(d.hint for d in vo.DIRECTIONS.values())},
            self.PARTIES: {"type": "array", "maxItems": self.MAX_PARTIES, "description":
                           "Die zugelassenen Gegenparteien; leer = frei",
                           "items": {"type": "object", "required": [self.PARTY], "properties": {
                               self.PARTY: _object_id("Gegenpartei (Person)"),
                               self.REF: {"type": "string", "maxLength": self.MAX_REF,
                                          "description": f"{vo.ORDER_REF} ({vo.ORDER_REF_HINT}) "
                                          f"– Pflicht und nur bei {vo.OUT}"}}}},
            self.INSTRUCTION: {"type": "string", "maxLength": vo.MAX_TASK,
                               "description": f"{vo.TASK} – freiwillig; leer = gemäss Spezifikation"},
            "payment_days": {**days, "description": f"Vorgabe {vo.PAYMENT_TERM_LABEL} in Tagen "
                             "(0 = Vorauszahlung); leer = am Beleg gewählt"},
            "lead_days": {**days, "description": f"Vorgabe {vo.LEAD_TERM_LABEL} in Tagen ab Zusage"},
            "valid_days": {**days, "minimum": 1,
                           "description": "Vorgabe: wie viele Tage die Offerte gilt"},
            "incoterm": {"type": "string", "enum": [t.key for t in inc.INCOTERMS],
                         "description": "Vorgabe Lieferbedingung (Incoterms 2020)"},
            "ownership": {"type": "string", "enum": [k for k, _ in vo.OWNERSHIP],
                          "description": f"Vorgabe {vo.OWNERSHIP_LABEL}: " + ", ".join(
                              f"{k} = {w}" for k, w in vo.OWNERSHIP)},
            self.PRICES: {"type": "array", "maxItems": self.MAX_PRICES, "description":
                          f"Vorgegebene Einzelpreise je Artikel, netto – nur bei {vo.IN}",
                          "items": {"type": "object", "required": ["article", "price"],
                                    "properties": {
                                        "article": _object_id("Der Artikel"),
                                        "price": {"type": ["string", "number"],
                                                  "description": "Einzelpreis netto, Hauswährung"}}}},
        }, required=[self.DIRECTION], examples=[
            {self.DIRECTION: vo.IN, self.PARTIES: [{self.PARTY: 100000201}],
             self.INSTRUCTION: "Härten auf 58 HRC", "payment_days": 30, "lead_days": 10,
             "valid_days": 30, "incoterm": "EXW", "ownership": vo.TO_PARTY,
             self.PRICES: [{"article": 100000101, "price": "120.00"}]},
            {self.DIRECTION: vo.OUT,
             self.PARTIES: [{self.PARTY: 100000202, self.REF: "Art.-Nr. 4711"}]},
        ])

    def _clean_instruction(self, value: Any) -> str:
        """**Was ist zu tun?** – freiwillig, in beiden Richtungen, am Modul; leer heisst
        «gemäss Spezifikation»."""
        text = str(value or "").strip()
        if len(text) > vo.MAX_TASK:
            raise Invalid(f"«{vo.TASK}» ist zu lang (max. {vo.MAX_TASK} Zeichen). Was mehr "
                        f"braucht, gehört in die Spezifikation des Artikels.")
        return text

    def _clean_parties(self, value: Any,
                       flow: "vo.Direction") -> list[dict[str, Any]]:
        """Die Freigabe-Liste **streng** prüfen. Leer ist erlaubt und heisst **frei**."""
        if value in (None, ""):
            value = []
        if not isinstance(value, (list, tuple)):
            raise Invalid(f"«{flow.label}» erwartet eine Liste zugelassener {vo.PARTY}.")
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for entry in value:
            raw = entry.get(self.PARTY) if isinstance(entry, dict) else entry
            number = self._object_id(raw)
            if number is None:
                raise Invalid(f"«{entry}» ist keine Objektnummer ({vo.PARTY}).")
            if number in seen:
                raise Invalid(f"{vo.PARTY} {number} steht zweimal – zweimal derselbe ist "
                            f"keine zweite Wahl.")
            seen.add(number)
            # ►►► **Die Bestellangabe gibt es nur, wo WIR bestellen** (``party_ref``). ◄◄◄
            # Ein trotzdem gesendeter Wert wird verworfen.
            if not flow.party_ref:
                rows.append({self.PARTY: number, self.REF: ""})
                continue
            ref = str((entry.get(self.REF) if isinstance(entry, dict) else "")
                      or "").strip()
            if not ref:
                raise Invalid(f"{vo.PARTY} {number}: «{vo.ORDER_REF}» fehlt – ohne die "
                            f"Angabe weiss er nicht, was er liefern soll "
                            f"({vo.ORDER_REF_HINT}).")
            if len(ref) > self.MAX_REF:
                raise Invalid(f"{vo.PARTY} {number}: «{vo.ORDER_REF}» ist zu lang "
                            f"(max. {self.MAX_REF} Zeichen).")
            rows.append({self.PARTY: number, self.REF: ref})
        if len(rows) > self.MAX_PARTIES:
            raise Invalid(f"Höchstens {self.MAX_PARTIES} {vo.PARTY} je Modul.")
        return rows

    @classmethod
    def parties_of(cls, config: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
        """Die zugelassenen Gegenparteien **mit ihrer Bestellangabe** – eine Lesestelle.
        **Leer heisst frei, nicht «niemand».**"""
        rows: list[dict[str, Any]] = []
        for entry in (config or {}).get(cls.PARTIES) or []:
            raw = entry.get(cls.PARTY) if isinstance(entry, dict) else entry
            try:
                number = int(raw)
            except (TypeError, ValueError):
                continue
            ref = str((entry.get(cls.REF) if isinstance(entry, dict) else "") or "")
            rows.append({cls.PARTY: number, cls.REF: ref})
        return rows

    @classmethod
    def parties_allowed(cls, config: Optional[dict[str, Any]]) -> list[int]:
        """Nur die Nummern – die Form, in der die **Freigabe-Prüfung** sie braucht
        (Namensstamm mit ``parties_of``)."""
        return [int(r[cls.PARTY]) for r in cls.parties_of(config)]

    @classmethod
    def ref_for(cls, config: Optional[dict[str, Any]], party: Optional[int]) -> str:
        """**Wie man bei DIESEM Partner bestellt** – leer, wo er nicht gelistet ist."""
        if party is None:
            return ""
        return next((str(r[cls.REF]) for r in cls.parties_of(config)
                     if int(r[cls.PARTY]) == int(party)), "")

    @classmethod
    def instruction_of(cls, config: Optional[dict[str, Any]]) -> str:
        """**Was an diesem Schritt zu tun ist** – die eine Lesestelle. Leer ist gültig."""
        return str((config or {}).get(cls.INSTRUCTION) or "").strip()


MODULES: dict[str, Module] = {
    m.key: m for m in (
        Datenerfassung(
            key=DATENERFASSUNG,
            label="Datenerfassung",
            tone="slate",
            competence=competences.PRUEFEN,
        ),
        Aussondern(
            key=AUSSONDERN,
            label="Aussondern",
            tone="clay",
            competence=competences.BEWEGEN,
        ),
        Bewegen(
            key=BEWEGEN,
            label="Bewegen",
            tone="moss",
            competence=competences.BEWEGEN,
        ),
        Beleg(
            key=BELEG,
            label="Zahlung",
            # Gedämpftes Violett – die anderen Familien sind vergeben (Slate · Sand · Moss ·
            # Clay).
            tone="plum",
            competence=competences.VERRECHNEN,
        ),
        Verbrauch(
            key=VERBRAUCH,
            label="Verbrauch",
            tone="sand",
            competence=competences.BAUEN,
        ),
    )
}

KEYS: tuple[str, ...] = tuple(MODULES)


def config_schemas() -> dict[str, dict[str, Any]]:
    """►►► **Die Einstellungen jedes Modultyps als JSON-Schema** – je Schlüssel aus
    ``Module.config_schema``. Ein neues Modul erscheint hier (und damit in jeder Route, die
    Schritte nimmt) von selbst. ◄◄◄"""
    return {k: _with_competence(m) for k, m in MODULES.items()}


def _with_competence(m: Module) -> dict[str, Any]:
    """Die Beschreibung eines Moduls, dazu für jedes gleich ``competence`` (``clean_step``)."""
    schema = m.config_schema()
    props = {**(schema.get("properties") or {}), "competence": {
        "type": "string", "enum": list(competences.COMPETENCES),
        "description": f"Wer kann das? Leer = Vorgabe des Moduls ({m.competence})."}}
    return {"description": m.label, **schema, "properties": props}

LABELS: dict[str, str] = {k: m.label for k, m in MODULES.items()}
TONES: dict[str, str] = {k: m.tone for k, m in MODULES.items()}


def _schema(properties: dict[str, Any], *, required: Optional[list[str]] = None,
            examples: list[dict[str, Any]]) -> dict[str, Any]:
    """Ein Objekt-Schema einer Konfiguration – die eine Form für jedes Modul."""
    return {"type": "object", "properties": properties,
            **({"required": required} if required else {}), "examples": examples}


def _object_id(what: str) -> dict[str, Any]:
    return {"type": "integer", "description": f"{what} (Objektnummer)"}


def get(module_type: Any) -> Module:
    """Modul zu einem Schlüssel. Unbekannt = harter Fehler, kein Rückfall."""
    found = MODULES.get(module_type)
    if found is None:
        raise Invalid(f"«{module_type}» ist kein Prozessschrittmodul. Erlaubt: "
                + ", ".join(f"{m.label} ({m.key})" for m in MODULES.values()) + ".")
    return found


def points_of(config: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Erfassungspunkte einer gespeicherten Definition — die eine Lesestelle."""
    return list((config or {}).get("points") or [])


def reason_of(config: Optional[dict[str, Any]]) -> str:
    """Der in der Definition gegebene Grund — die eine Lesestelle (nur Aussondern; sonst
    leer)."""
    return str((config or {}).get("reason") or "")


def lines_of(config: Optional[dict[str, Any]]) -> list[dict[str, int]]:
    """Die **Stückliste** eines Moduls — je Zeile Artikel und Menge pro Stück (nur
    Verbrauch; sonst leer)."""
    return [
        {"article": int(row["article"]), "quantity": int(row["quantity"])}
        for row in (config or {}).get(Verbrauch.LINES) or []
    ]


def sample_of(config: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Die Stichprobenregel einer gespeicherten Definition — die eine Lesestelle.

    Fehlt sie, gilt **alle** (``domain/sampling.DEFAULT``).
    """
    return (config or {}).get("sample") or dict(sampling.DEFAULT)


def label(module_type: str) -> str:
    """Wie ein Modul heisst. **Abgeleitet aus dem Typ, nie gespeichert.** Unbekanntes
    erscheint roh, nicht schöngefärbt."""
    return LABELS.get(module_type, module_type)
