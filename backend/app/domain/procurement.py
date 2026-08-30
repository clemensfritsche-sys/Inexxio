"""**Der Beleg — die Vokabel eines Einkaufs, und sie gehört keinem Modul.**

Ein Einkaufs-Beleg hat drei Stufen und einen Ausgang. Das ist eine Aussage über den
**Vorgang**, nicht über den Modultyp, der ihn ausgelöst hat — und genau darum steht sie
hier statt an einer Modul-Klasse.

**Warum das mehr ist als eine Verschiebung.** Im Datenmodell hing der Beleg nie am Modul:
``purchases`` trägt eine ``step_id`` und keinen Modultyp, ``_can`` liest Stufe × Rolle,
``assert_receivable``/``note_receipt`` fragen nur, ob es zu diesem Schritt einen Beleg
gibt. Es waren genau **zwei Fäden**, die ihn an «Beschaffen» banden: er las dessen
``suppliers`` und dessen ``instruction``. Sind die gekappt (``Module.suppliers_of`` /
``Module.instruction_for``), trägt **jedes** Modul denselben Beleg — dieselben Stufen,
dieselben Verben, dieselbe Oberfläche.

Das ist die Grundlage dafür, dass eine **Sendung** kein zweites Konzept braucht: eine
Spedition zu beauftragen IST ein Einkauf, ein Tarifvergleich IST der Angebotsspiegel, und
die Sendungsnummer ist das ``tracking``-Feld, das es längst gibt (§9.8/§9.9).

**Drei Stufen, weil drei Dinge unumkehrbar sind** — nichts zugesagt · zugesagt · erfüllt.
«Preis steht» ist keine vierte: das ist der *Inhalt* der Anfrage.
"""

#: ►►► **Wie der Vorgang heisst und wie er aussieht.** ◄◄◄
#:
#: Sie stehen hier und nicht an einer Modul-Klasse, weil sie den **Vorgang** beschreiben:
#: ein Einkauf sieht überall gleich aus, ob ihn ein Beschaffen-Modul auslöst (dort ist er
#: der Zweck) oder ein Bewegen-Modul (dort war er eine Wahl). Das Modul ``Beschaffen``
#: liest sie ebenso – damit können die beiden gar nicht auseinanderlaufen, und ein
#: Bewegen-Modul mit Beleg trägt buchstäblich dieselbe Identität statt einer nachgebauten.
#:
#: Die Farbfamilie ist ein **Name**, kein Wert: welcher Ton dahintersteht, entscheidet die
#: Oberfläche (``lib/modules.MODULE_TONE``) – hier steht nur, welcher gemeint ist.
LABEL = "Beschaffen"
TONE = "plum"

#: Die Stufen in ihrer Reihenfolge. Die Oberfläche fragt danach, statt sie nachzubauen.
STAGES: tuple[str, ...] = ("anfrage", "bestellung", "wareneingang")

#: Der Ausgang. **Keine Stufe** – man kommt dort an, statt hindurchzugehen; die gegangene
#: Kette bleibt dabei stehen, wo sie stand (ein Storno macht die Bestellung nicht
#: ungeschehen, er sagt nur, dass nichts mehr ankommt).
CANCELLED = "storniert"

#: **Ab hier ist eine zweite Partei gebunden.** Vor dieser Stufe darf das System die
#: Grundlage still nachziehen; ab ihr liegt eine Bestellung beim Lieferanten, und eine
#: stille Änderung wäre ein Beleg, der nicht mehr stimmt.
BINDING = "bestellung"

STAGE_LABELS: dict[str, str] = {
    "anfrage": "Anfrage",
    "bestellung": "Bestellung",
    "wareneingang": "Wareneingang",
    CANCELLED: "Storniert",
}

#: **Was man an der AKTIVEN Stufe tut, um sie zu verlassen** – das Wort auf dem Knopf.
#: Getrennt von der Beschriftung, weil der Zustand daneben steht: «Bestellen» ↔
#: «Bestellt» (Testnotiz #596). Die letzte Stufe trägt keines: dort ist man angekommen.
STAGE_VERBS: dict[str, str] = {
    "anfrage": "Bestellen",
    "bestellung": "Wareneingang buchen",
}
