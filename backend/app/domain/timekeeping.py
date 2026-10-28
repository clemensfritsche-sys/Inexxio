"""Zeiterfassung – der fachliche Kern: KEINE DB, KEINE Services (docs/zeiterfassung-spezifikation.md).

Hier steht, was die Zeiterfassung **weiss**: die Absenzarten mit ihrer einen Wirkung, die
Regeln des Landes (ArG, ArGV 1, OR), die Hinweise mit Ton und Wort und die Sätze des
Reglements, die die Oberfläche als ⓘ an der Stelle zeigt, an der sie gelten. Gerechnet wird
in ``services/timekeeping``; gespeichert wird dort nur, was ein Mensch eingibt.

►►► **Alles in Minuten.** ◄◄◄ Ein Stundenkonto, ein Ferienguthaben, ein Tagessoll – jede
Zahl ist eine Menge Minuten. Ein «Tag» ist nur eine Anzeige: das Tagessoll aus dem Vertrag.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

#: Was ein Eintrag ist. Eine Tabelle für alles, was einen Tag füllt oder ein Konto bewegt:
#: ``in``/``out`` (Stempel) · ``absence`` · ``booking`` (nur Admin) · ``void`` (nimmt einen
#: Eintrag zurück, gelöscht wird nichts). Eine Änderung ist ein neuer Eintrag mit
#: ``replaces_id`` – er ersetzt den alten.
KINDS = ("in", "out", "absence", "booking", "void")
STAMPS = ("in", "out")

#: Woher ein Stempel kommt: gewischt (Serverzeit) oder von Hand nachgetragen.
SOURCES = ("swipe", "manual")

# ─── Wirkungen und Absenzarten ─────────────────────────────────────────────────────

#: Jede Absenzart hat **genau eine** Wirkung (Schlüssel → Wort, Satz).
EFFECTS: dict[str, tuple[str, str]] = {
    "fulfilled": ("Erfüllt", "Zählt als Arbeitszeit."),
    "vacation": ("Ferien", "Zählt als Arbeitszeit, wird vom Ferienguthaben abgezogen."),
    "unpaid": ("Entfällt", "Die Sollzeit fällt weg, in dieser Zeit wachsen keine Ferien an."),
}


@dataclass(frozen=True)
class Art:
    key: str
    label: str
    #: Symbol (Lucide), Spiegel in ``frontend/src/components/erp/time/vocab.ts`` – getestet.
    icon: str
    effect: str
    #: Welcher Nachweis – ``None`` = keiner.
    proof: Optional[str] = None
    #: Ab dem wievielten Arbeitstag der Nachweis nötig ist (1 = immer). Das Gesetz kennt
    #: keine feste Frist, der Betrieb legt sie fest (je Gesellschaft änderbar).
    proof_from: Optional[int] = None


#: ►►► **Die Absenzarten – nicht zusammengelegt.** ◄◄◄ Krankheit und Unfall zahlen
#: verschiedene Versicherungen (KTG/OR 324a ↔ UVG), Militär und Elternschaft die EO.
ARTS: tuple[Art, ...] = (
    Art("ferien", "Ferien", "sun", "vacation"),
    Art("krank", "Krankheit", "thermometer", "fulfilled", "Arztzeugnis", 3),
    Art("unfall", "Unfall", "activity", "fulfilled", "Arztzeugnis", 3),
    Art("militaer", "Militär/Zivildienst", "shield", "fulfilled", "Dienstbescheinigung", 1),
    Art("eltern", "Mutter-/Vaterschaft", "baby", "fulfilled", "Bescheinigung", 1),
    Art("bezahlt", "Bezahlte Absenz", "calendar-check", "fulfilled"),
    Art("unbezahlt", "Unbezahlter Urlaub", "calendar-x", "unpaid"),
)
ART_BY_KEY = {a.key: a for a in ARTS}

# ─── Regeln des Landes (Schweiz) ───────────────────────────────────────────────────

WEEK_MAX = 45 * 60            # ArG Art. 9: Höchstarbeitszeit (Industrie, Büro)
REST = 11 * 60                # ArG Art. 15a: tägliche Ruhezeit
REST_U18 = 12 * 60            # ArGV 5 Art. 16
DAY_MAX_U18 = 9 * 60          # ArG Art. 31
NIGHT_FROM, NIGHT_TO = 23 * 60, 6 * 60   # ArG Art. 10/16: Nacht 23–06 Uhr
#: Mindestpausen (ArG Art. 15): ab so viel Arbeit → so viel Pause.
PAUSES: tuple[tuple[int, int], ...] = ((9 * 60, 60), (7 * 60, 30), (330, 15))
#: Ein «Kommen» läuft am selben Tag, bis «Gehen» kommt; über Mitternacht höchstens so lange
#: (ArG Art. 10 Abs. 3: die Tagesarbeit liegt in 14 Stunden – Nachtschicht). Danach fehlt
#: «Gehen», und der nächste Wisch ist wieder «Kommen» (``services/timekeeping.reaches``).
RUNNING_MAX = 14 * 60
#: …und nur ein **spätes** Kommen läuft über Mitternacht (Abendarbeit ab 20 Uhr, ArG Art. 10):
#: wer um 18 Uhr kommt und das Gehen vergisst, hat am Morgen einen offenen Tag – keine
#: 13-Stunden-Nachtschicht.
SHIFT_FROM = 20 * 60
#: Eigene Einträge lassen sich so viele Tage zurück ändern; ältere ändert der Admin.
CORRECTION_DAYS = 7
#: Ein zweiter Wisch innerhalb dieser Sekunden gilt als derselbe.
DOUBLE_SWIPE_S = 60
#: Eine Aufgabe ist ab so vielen Tagen dringend (rot).
URGENT_DAYS = 5
#: Feiertage fürs nächste Jahr: ab diesem Monat fällig, ab jenem dringend.
HOLIDAYS_DUE_MONTH, HOLIDAYS_URGENT_MONTH = 10, 12

#: Die Regeln als Sätze – die Karte «Regeln · Schweiz» an der Gesellschaft.
RULE_FACTS: tuple[tuple[str, str], ...] = (
    ("Arbeitstage", "Mo–Fr (Vorschlag)"),
    ("Wochenstunden", "42 h (Vorschlag)"),
    ("Höchstens", "45 h pro Woche"),
    ("Ruhezeit", "11 h · unter 18: 12 h"),
    ("Pausen", "15 · 30 · 60 min ab 5½ · 7 · 9 h"),
    ("Nacht", "23–06 Uhr, gesperrt"),
    ("Sonntag", "gesperrt"),
    ("Mindestferien", "4 Wochen · bis 20: 5"),
    ("Korrektur", f"{CORRECTION_DAYS} Tage selbst"),
)

#: Die Kantone – der Kanton einer Gesellschaft bestimmt den Vorschlag der Feiertage.
CANTONS: tuple[tuple[str, str], ...] = (
    ("AG", "Aargau"), ("AI", "Appenzell Innerrhoden"), ("AR", "Appenzell Ausserrhoden"),
    ("BE", "Bern"), ("BL", "Basel-Landschaft"), ("BS", "Basel-Stadt"), ("FR", "Freiburg"),
    ("GE", "Genf"), ("GL", "Glarus"), ("GR", "Graubünden"), ("JU", "Jura"),
    ("LU", "Luzern"), ("NE", "Neuenburg"), ("NW", "Nidwalden"), ("OW", "Obwalden"),
    ("SG", "St. Gallen"), ("SH", "Schaffhausen"), ("SO", "Solothurn"), ("SZ", "Schwyz"),
    ("TG", "Thurgau"), ("TI", "Tessin"), ("UR", "Uri"), ("VD", "Waadt"), ("VS", "Wallis"),
    ("ZG", "Zug"), ("ZH", "Zürich"),
)
CANTON_CODES = tuple(c for c, _ in CANTONS)

# ─── Hinweise: Schlüssel → (Wort, Ton, Symbol) ─────────────────────────────────────

#: Die Ampel warnt nur – es gibt nie einen automatischen Abzug. ``danger`` = eine
#: gesetzliche Grenze, ``warning`` = ein Hinweis oder etwas fehlt.
HINTS: dict[str, tuple[str, str, str]] = {
    "pause": ("Pause fehlt", "warning", "alert-triangle"),
    "night": ("Nachtarbeit", "danger", "octagon-alert"),
    "u18": ("Unter 18: über 9 h", "danger", "octagon-alert"),
    "rest": ("Ruhezeit zu kurz", "danger", "octagon-alert"),
    "week": ("Über 45 h/Woche", "danger", "octagon-alert"),
    "sunday": ("Sonntagsarbeit", "danger", "octagon-alert"),
    "open": ("Stempel fehlt", "warning", "alert-triangle"),
    "proof": ("Nachweis fehlt", "warning", "file-warning"),
}

# ─── Das Reglement – an der Stelle, an der es gilt ─────────────────────────────────

TEXTS: dict[str, str] = {
    "card": ("Kleinen Knopf wischen: «Kommen» nach rechts, «Gehen» nach links – im Betrieb, "
             "beim Kunden, unterwegs und zu Hause. Mittagspause: «Gehen», danach «Kommen»; "
             "Pausen unter 30 Minuten nicht stempeln. Sie sehen nur Ihre eigenen Daten, die "
             "Administration alle. Gelöscht wird nichts – jede Änderung bleibt sichtbar."),
    "account": ("Stand gestern – heute zählt ab morgen. Mehr- und Minderzeit landen hier; "
                "Ausgleich durch Freizeit, abgesprochen mit dem Team. Ein Tag mit fehlendem "
                "«Gehen» zählt erst, wenn er vollständig ist."),
    "vacation": ("Guthaben heute, in Stunden – die Bemessungsgrundlage; in Klammern in Tagen "
                 "(Tagessoll des Vertrags). Die Ferien wachsen jeden Tag an. Anspruch gemäss "
                 "Vertrag, mindestens 4 Wochen, bis zum 20. Geburtstag 5. Ins Minus gehen ist "
                 "erlaubt (Ferien im Voraus). Eintragen: Tag wählen → «Erfassen»."),
    "contract": ("Soll pro Arbeitstag = Wochenstunden ÷ Anzahl Arbeitstage (z. B. 25 h an "
                 "Mo–Mi = 8:20 h); an Feiertagen 0. Eintritt = erster Vertrag, jede Änderung "
                 "= neuer Vertrag ab Stichtag, Austritt = 0 h. Die Gesellschaft im Vertrag "
                 "bestimmt Feiertage und Gesetz. Die Verträge pflegt die Administration."),
    "calendar": ("Punkt orange: Hinweis oder es fehlt etwas. Punkt rot: gesetzliche Grenze. "
                 "Grau hinterlegt: ganztägige Absenz. Blass: abgeschlossen (älter als "
                 f"{CORRECTION_DAYS} Tage) – ändern kann nur die Administration. Tag "
                 "antippen: Stempel, Nachtrag, Absenz."),
    "locked": (f"Eigene Einträge lassen sich {CORRECTION_DAYS} Tage lang ändern. Danach ist "
               "der Tag abgeschlossen; korrigieren kann nur noch die Administration – "
               "sichtbar an der Zeile. Einen Nachweis kann man jederzeit nachreichen."),
    "pause": "Mindestpausen: ab 5½ h Arbeit 15 Minuten, ab 7 h 30 Minuten, ab 9 h 1 Stunde.",
    "limits": ("Höchstens 45 h pro Woche, mindestens 11 h Ruhe zwischen zwei Arbeitstagen "
               "(unter 18: 12 h), keine Arbeit am Sonntag und zwischen 23 und 6 Uhr, unter 18 "
               "höchstens 9 h pro Tag. Das System warnt nur."),
    "capture": ("Ein Tag besteht aus Einträgen: Stempel (Kommen/Gehen) oder Absenz – ganzer "
                "Tag oder Stunden. Gerechnet wird immer in Stunden; ein ganzer Tag ist das "
                "Tagessoll aus dem Vertrag. Eine neue Absenz ersetzt an ihren Tagen eine "
                "ältere (krank in den Ferien: die Ferien kommen zurück). Krankheit und Unfall "
                "am selben Tag eintragen."),
    "scope": "Ganzer Tag = Tagessoll aus dem Vertrag. Gerechnet wird immer in Stunden.",
    "until": "Gleiches Datum = nur dieser Tag. Oder den letzten Tag im Kalender anklicken.",
    "bookings": ("Wirken direkt auf Stundenkonto und Ferien: Übertrag bei Einführung, "
                 "ausbezahlte Stunden, Korrektur. Nie geändert, nie gelöscht – ein Fehler "
                 "wird mit einer Gegenbuchung behoben."),
    "proof": ("Das Gesetz kennt keine feste Frist – der Arbeitgeber legt sie fest. Üblich ist "
              "ab dem 3. Tag; 1 = immer, leer = nie."),
    "holidays": ("Feiertage gelten für alle, deren Vertrag auf diese Gesellschaft lautet; an "
                 "einem Feiertag ist das Soll 0. Der Vorschlag kommt aus OpenHolidays "
                 "(openholidaysapi.org, CC BY 4.0) für den gewählten Kanton – es zählt nur, "
                 "was Sie übernehmen. Fällig: ab 1. Oktober fürs nächste Jahr, ab 1. Dezember "
                 "dringend."),
    "rules": ("Aus ArG, ArGV 1 und OR – ein Satz je Land. Bei Widerspruch gilt das Gesetz."),
}


# ─── Kleine Rechnungen ohne Datenbank ──────────────────────────────────────────────

def age(born: date, on: date) -> int:
    """Alter in ganzen Jahren am Tag ``on``."""
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def legal_weeks(born: date, on: date) -> int:
    """Gesetzliche Ferienwochen (OR 329a): bis zum vollendeten 20. Altersjahr 5, sonst 4."""
    return 5 if age(born, on) < 20 else 4


def needed_pause(work: float) -> int:
    """Mindestpause in Minuten für so viel Arbeit (ArG Art. 15)."""
    for threshold, pause in PAUSES:
        if work > threshold:
            return pause
    return 0


def days_of(mask: int) -> list[int]:
    """Arbeitstage als Liste (0 = Mo … 6 = So) aus der Bitmaske des Vertrags."""
    return [i for i in range(7) if mask & (1 << i)]


def mask_of(days: list[int]) -> int:
    return sum(1 << d for d in set(days) if 0 <= d <= 6)


def hm(minutes: float) -> str:
    """Minuten als «8:24» (ohne Vorzeichen-Logik: ein Minus ist ein echtes Minus)."""
    m = round(minutes)
    sign = "−" if m < 0 else ""
    m = abs(m)
    return f"{sign}{m // 60}:{m % 60:02d}"


def dmy(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def proof_from(art: Art, overrides: dict) -> Optional[int]:
    """Ab welchem Arbeitstag diese Art einen Nachweis braucht – die Gesellschaft kann es
    festlegen (``company_settings.time_rules['proof']``), sonst gilt die Vorgabe."""
    if art.proof is None:
        return None
    if art.key in overrides:
        v = overrides[art.key]
        return int(v) if v else None
    return art.proof_from


def append_only_sql() -> str:
    """►►► **Ein Eintrag wird nie geändert und nie gelöscht – das steht in der Datenbank.** ◄◄◄

    Dieselbe Bauart wie ``statuses.terminal_guard_sql``: der Schutz sitzt **unter** jeder
    Anwendung (Reparaturskript, Migration, ein ``UPDATE`` von Hand). Eine Korrektur ist ein
    neuer Eintrag, der den alten ersetzt; ein Vertrag ändert sich mit einem neuen Vertrag.
    Idempotent: ``CREATE OR REPLACE`` plus ``DROP TRIGGER IF EXISTS``; ohne Tabelle nichts."""
    parts = [
        "CREATE OR REPLACE FUNCTION time_append_only() RETURNS trigger AS $fn$ "
        "BEGIN RAISE EXCEPTION 'Zeiterfassung: «%» wird nie geändert oder gelöscht – "
        "eine Korrektur ist ein neuer Eintrag.', TG_TABLE_NAME USING ERRCODE = 'check_violation'; "
        "END; $fn$ LANGUAGE plpgsql;",
    ]
    for table in ("time_entries", "time_contracts"):
        parts.append(
            f"IF to_regclass('public.{table}') IS NOT NULL THEN "
            f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}; "
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION time_append_only(); END IF;")
    return "DO $guard$ BEGIN EXECUTE $q$" + parts[0] + "$q$; " + " ".join(parts[1:]) + \
        " END $guard$;"
