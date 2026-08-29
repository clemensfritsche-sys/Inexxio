from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class CompanySettings(Base):
    """Ein **Unternehmen** (eine Gesellschaft) – ein gleichrangiger ERP-Datensatz.

    Bis Juli 2026 war das ein Singleton (``id == 1``); danach kurz ein «Hauptsitz +
    kastrierte Standorte»-Modell. Jetzt trägt die Tabelle n **gleichrangige** Zeilen –
    jede eine vollständige juristische Einheit vom Feed-Typ ``organization``: eigene
    Objektnummer, eigener Name, Anschrift, **eigene Rechtsidentität** (UID/EIN/VAT), Bank,
    MWST. Als **Halter** verwendbar (``instances.location_type='company'`` zeigt auf die
    Objektnummer). Keine Zeile ist einer anderen untergeordnet.

    **Zwei Reichweiten, und wo eine Angabe gilt, entscheidet die Schreibstelle** – nicht
    ein Rang (``services/sites.py`` ist die eine Auflösung):

      * **je Gesellschaft** (``sites.ENTITY_FIELDS``, editierbar an JEDEM Datensatz):
        Name, Rechtsform, Anschrift, Währung, Rechtsidentität (UID/MWST), Kontakt, IBAN.
        Die US-Gesellschaft hat ihre EIGENE EIN/Steuer/Bank – deshalb ist Rechtsidentität
        hier bewusst dabei. Der Satz ist bewusst **klein**: jedes Feld hier ist ein Feld,
        das jemand für JEDE Gesellschaft pflegen muss.
      * **die eine Website/Integration** (``sites.PLATFORM_FIELDS``): Stripe-Key,
        Shop-Währungen, ``pricing_zone_factors``, ``legal_documents``, Plausible, Maps.
        Diese gibt es genau EINMAL; sie liegen (vorerst) als Spalten auf dem **Betreiber**
        (dem ältesten Unternehmen) und werden nur über die Systemkonfiguration gepflegt.

    **Der «Betreiber» ist abgeleitet, kein Flag** (``sites.operator`` = ältestes
    Unternehmen). Das frühere ``is_primary`` ist entfallen: es stellte eine Zeile über die
    anderen und war die Ursache eines Deploy-Ausfalls. Die Rolle «wer vertritt die eine
    Website» braucht keine Markierung – die kleinste ``id`` (der Ursprung) ist die Antwort.
    """

    __tablename__ = "company_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Universelle Objektnummer: Jede Gesellschaft ist ein vollwertiger ERP-Datensatz
    # (im Feed als «Unternehmen» geführt, vom Admin pflegbar). Wird bei der ersten
    # Abfrage lazy vergeben (services/sites.operator) bzw. beim Anlegen (sites.create).
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, index=True)
    # **Betreiber der Website** – genau EINE Gesellschaft trägt den Titel (partieller
    # Unique-Index, Migration 091). Er vertritt die eine Website nach aussen (Impressum,
    # Fallback) und trägt die Plattform-/Systemkonfiguration. Anders als das frühere
    # ``is_primary`` bedeutet das Flag NUR «vertritt die Website» – keine Kaste; jede
    # Gesellschaft bleibt vollständig. **Wählbar** (``sites.set_operator``), Default =
    # das älteste Unternehmen. Gelesen wird tolerant: fehlt die Markierung, gilt das
    # älteste (``sites.find_operator``), damit eine ausstehende Migration nie zu «kein
    # Betreiber» führt.
    is_operator: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False)
    # **Aktiv?** – Soft-Delete wie überall. Ein geschlossener Standort/eine liquidierte
    # Gesellschaft wird deaktiviert, nicht gelöscht: ihre Objektnummer bleibt als Halter
    # historischer Instanzen und Belege auflösbar.
    #
    # **Endgültig, ohne Reaktivierung** – wie beim Artikel. Der reale Vorgang dahinter ist
    # eine Liquidation: eine wiedereröffnete Gesellschaft bekommt eine NEUE UID/EIN, ein
    # neues Handelsregister-Datum und neue Belegkreise. Sie ist damit nicht dieselbe
    # Rechtsperson, und sie so zu behandeln wäre eine Fälschung im Beleg. Wer wieder
    # eröffnet, legt ein neues Unternehmen an (Inhalte darf er abschreiben).
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False)
    # **Funktionswährung** der Gesellschaft (ISO-3, Default CHF). Wird aus dem Land
    # vorbelegt (``sites.currency_for_country``). Grundlage für «ein Preis, überall in
    # Landeswährung»: der Katalogpreis bleibt EIN kanonischer CHF-Betrag, Eingabe/Anzeige
    # laufen über den bestehenden FX-Anker in dieser Währung.
    currency: Mapped[str] = mapped_column(
        String(3), default="CHF", server_default="CHF", nullable=False)
    # Der Name der Gesellschaft. Das ist zugleich das Halter-Label:
    # ``locations.location_label`` gibt für einen ``company``-Halter genau dieses Feld zurück.
    company_name: Mapped[str] = mapped_column(String(255), default="Inexxio AG")
    legal_form: Mapped[str] = mapped_column(String(50), default="AG")
    street: Mapped[Optional[str]] = mapped_column(String(255))
    street_nr: Mapped[Optional[str]] = mapped_column(String(20))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="Schweiz")
    # **Rechtsidentität – auf das Minimum reduziert** (Testnotizen #307/#313/#314/#319/#321):
    # Was die Gesellschaft ausweist, sind UID/Steuernummer und MWST-Nummer – sie stehen auf
    # dem Beleg-Briefkopf (``document_render``) und im Impressum. Die Handelsregister-Nummer
    # ist in der Schweiz seit 2016 die UID selbst, der HR-Kanton steht im Register und das
    # Aktienkapital ist nirgends vorgeschrieben – drei Felder, die nur abschrieben, was die
    # UID ohnehin sagt.
    uid_number: Mapped[Optional[str]] = mapped_column(String(30))
    vat_number: Mapped[Optional[str]] = mapped_column(String(30))
    # Bank = **eine** Zahl: die IBAN trägt Land, Bank und Konto. QR-IBAN (die QR-Rechnung
    # ist nicht gebaut), Bankname und BIC waren Abschriften daraus.
    iban_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    email: Mapped[str] = mapped_column(String(255), default="info@inexxio.com")
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    # ── Plattform-Konfiguration (die EINE Website, nicht je Gesellschaft) ─────────
    # Sie steht als Spalten auf dem Betreiber-Datensatz und wird ausschliesslich über
    # die Systemkonfiguration gepflegt (``services/sites.PLATFORM_FIELDS``).
    plausible_domain: Mapped[Optional[str]] = mapped_column(String(255))
    google_maps_api_key: Mapped[Optional[str]] = mapped_column(String(255))


class CompanyTerritory(Base):
    """Ein **Gebietsanspruch**: dieses Gebiet fakturiert diese Gesellschaft (ADR 006).

    Die Welt ist in feste Regionen partitioniert (``services/geography.REGIONS``). Jedes Gebiet
    gehört **genau EINER** Gesellschaft; diese Tabelle hält NUR die **Abweichungen vom Default**.
    Steht ein Gebiet NICHT in der Tabelle, gilt der Standard – so gehört jeder Fleck der Erde
    jemandem (Totalität), ohne dass alle ~250 Länder gepflegt werden müssen.

    **Ein Gebiet ist eine Region ODER ein einzelnes Land** (Ausnahme: «Europa gehört der GmbH,
    Liechtenstein aber der Schweizer AG»). Beides steht in derselben Spalte, weil es fachlich
    EINE Sache ist – der Unterschied wird **abgeleitet, nicht gespeichert**: ISO-2 hat exakt
    2 Zeichen, jeder Regions-Code mindestens 3 (NAM/EUR/ASIA/…), eine Kollision ist unmöglich
    (``geography.is_country_code``). Der Spaltenname ``region`` ist historisch – gemeint ist
    der **Gebiets-Code**.

    ``region`` ist **unique** (ein Gebiet hat genau einen Besitzer). ``company_id`` zeigt auf
    ``company_settings.id`` (interner Schlüssel des Besitzers). Die Auflösung «welche Gesellschaft
    gehört zu diesem Land» ist ``services/sites.company_for_country`` (**Land ≻ Region ≻
    Betreiber**).

    **Neue Tabelle** → ``create_all()`` im Lifespan legt sie an, falls Migration 092 nicht lief
    (das Lifespan-Netz braucht nur für neue SPALTEN auf bestehenden Tabellen Einträge)."""

    __tablename__ = "company_territories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Gebiets-Code: Regions-Code («EUR») ODER ISO-2-Land als Ausnahme («LI»).
    region: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    company_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
