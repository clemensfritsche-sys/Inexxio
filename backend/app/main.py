import re
import traceback
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from .core.config import get_settings
from .core.database import Base, SessionLocal, engine
from .domain import statuses as st
from .models import UserProfile
from .routers import (
    admin, articles, attachments, auth, contact, erp, feedback, health,
    instances, orders, passkey, payments, places,
)

settings = get_settings()


def _bootstrap_admin() -> None:
    """Ensure initial_admin_email always has admin role; fall back to first user."""
    db = SessionLocal()
    try:
        if settings.initial_admin_email:
            candidate = db.query(UserProfile).filter(
                UserProfile.email == settings.initial_admin_email,
                UserProfile.is_active == True,
            ).first()
            if candidate:
                if candidate.role != "admin":
                    candidate.role = "admin"
                    db.commit()
                    print(f"INFO: Promoted {settings.initial_admin_email} to admin.", flush=True)
                return

        has_admin = db.query(UserProfile).filter(
            UserProfile.role == "admin", UserProfile.is_active == True
        ).first()
        if has_admin:
            return
        candidate = (
            db.query(UserProfile)
            .filter(UserProfile.is_active == True)
            .order_by(UserProfile.id)
            .first()
        )
        if candidate:
            candidate.role = "admin"
            db.commit()
    finally:
        db.close()


# Spalten, die nach dem Initial-Schema ergänzt wurden (Tabelle, Spalte, DDL-Typ).
# create_all() legt nur fehlende TABELLEN an – KEINE neuen Spalten auf bestehenden.
_COLUMN_SAFETY_NET = (
    # ``company_settings`` liest JEDE Halter-Anzeige (ein Unternehmen ist ein Standort)
    # und der öffentliche Impressum-Endpunkt. Fehlt hier eine Spalte, die das Modell kennt,
    # endet jede dieser Abfragen in einem 500 – das nimmt ERP **und** Website mit. Genau
    # das ist mit ``is_primary`` passiert (Migration 090), als sie hier fehlte.
    ("company_settings", "google_maps_api_key", "VARCHAR(255)"),
    ("company_settings", "is_operator", "BOOLEAN NOT NULL DEFAULT false"),
    ("company_settings", "currency", "VARCHAR(3) NOT NULL DEFAULT 'CHF'"),
    ("company_settings", "is_active", "BOOLEAN NOT NULL DEFAULT true"),
    ("company_settings", "object_id", "BIGINT"),
    # Artikel-Spezifikation (optionale Felder, nachträglich ergänzt).
    ("articles", "landed_unit_cost", "NUMERIC(12,4)"),
    ("articles", "material", "VARCHAR(255)"),
    ("articles", "cad_url", "VARCHAR(500)"),
    ("articles", "surface", "VARCHAR(255)"),
    ("articles", "supplier_article_number", "VARCHAR(255)"),
    ("articles", "min_order_qty", "NUMERIC(12,3)"),
    ("articles", "safety_stock", "NUMERIC(12,3)"),
    ("articles", "replaced_by_id", "BIGINT"),
    ("articles", "is_hazmat", "BOOLEAN DEFAULT FALSE NOT NULL"),
    # Prozesslogik (Migration 104/107) – NEUE Spalten auf der BESTEHENDEN Tabelle
    # ``orders``. ``end_status`` ist der eine Ort des Endzustands (PROCESS_CORE.md §4.2),
    # ``name`` entsteht mit der Objektnummer. Fehlt eine, scheitert jede Auftrags-Abfrage,
    # weil das Modell sie kennt.
    ("orders", "end_status", "VARCHAR(30) NOT NULL DEFAULT 'freigegeben'"),
    ("orders", "name", "VARCHAR(120) NOT NULL DEFAULT ''"),
    # Definitionsbereich + Erzeugungsprozess (Migration 105) – ebenfalls NEUE Spalten auf
    # BESTEHENDEN Tabellen. ``process_version`` liest jede Artikel-Abfrage (das Modell
    # kennt sie), ``source_*`` jede Auftrags-Abfrage.
    ("articles", "process_version", "INTEGER NOT NULL DEFAULT 0"),
    ("process_steps", "source_article_id", "BIGINT"),
    ("process_steps", "source_version", "INTEGER"),
    # Abweichungsauftrag (Migration 109): die Verbindung zwischen zwei Aufträgen. Das
    # Modell kennt sie, also scheitert ohne sie **jede** Auftrags- und Bestandsabfrage –
    # dieselbe Ausfallklasse wie Migration 090.
    ("order_units", "return_to_order_id", "BIGINT"),
    # Der Ort (Migration 111): eine NEUE Spalte auf der BESTEHENDEN Tabelle
    # ``instance_units``. Das Modell kennt sie, also scheitert ohne sie **jede** Abfrage
    # auf Einzelinstanzen – und die trägt der halbe ERP-Feed. Dieselbe Ausfallklasse wie
    # Migration 090, und der Grund, warum dieses Netz existiert.
    ("instance_units", "place_object_id", "BIGINT"),
    # Der Träger (Migration 112) – dieselbe Tabelle, dieselbe Ausfallklasse.
    ("instance_units", "place_unit_id", "BIGINT"),
    # ►►► **Die Netze für ``purchases`` sind mitgegangen** (September 2026). ◄◄◄
    #
    # Sie schützten Lesezugriffe auf den Beschaffungs-Beleg – und den gibt es nicht mehr:
    # Beschaffen und Verkauf sind ersatzlos entfernt, das Geld steht im «Zahlung»-Modul.
    # Ein Netz für eine Spalte, die kein Modell mehr liest, schützt nichts; die **Tabelle**
    # bleibt trotzdem stehen (Zwei-Deploy-Regel, ``docs/backlog.md``).
    # **Der Geldvorgang hat zwei Parteien** (Migration 125): der Angebotsspiegel steht an
    # der BESTEHENDEN Tabelle ``deals``. Ohne ihn scheitert jeder Lesezugriff auf einen
    # Vorgang – und damit jede Auftrags-Anzeige, in der ein «Zahlung»-Modul steht.
    # ``create_all`` legt eine fehlende Tabelle an, **nie** eine fehlende Spalte.
    ("deals", "quotes", "JSONB NOT NULL DEFAULT '[]'::jsonb"),
    # Was gehandelt wird, eingefroren mit der Zusage (Migration 125).
    ("deals", "agreed_lines", "JSONB"),
    # **Eine Stornierung ist eine Gegenbuchung** (Migration 126) – der Verweis auf die
    # stornierte Zeile. Der Fremdschlüssel ist hier bewusst nicht dabei: das Netz zieht
    # eine **Spalte** nach, damit der Dienst startet; die Integrität stellt die Migration
    # her, und sie ist die Wahrheit.
    ("deal_entries", "reverses_id", "BIGINT"),
    # **Die Steuer gehört zum Beleg** (Migration 127): ohne Satz und Steuerbetrag ist eine
    # Rechnung keine, und das Leistungsdatum entscheidet bei einem Satzwechsel über beides.
    ("deal_entries", "vat", "JSONB"),
    ("deal_entries", "service_date", "DATE"),
    # **Ein Betrag hat eine Währung** (Migration 128): ohne sie ist «1000» tausend Franken
    # oder tausend Yen. Vorgabe ``CHF``; wer in einer anderen fakturiert, sagt es am
    # Vorgang – bis zur Zusage.
    ("deals", "currency", "VARCHAR(3) NOT NULL DEFAULT 'CHF'"),
)

#: ►►► **Spalten, die es GIBT, aber mit der falschen Genauigkeit.** ◄◄◄
#:
#: Die vierte Lücke zwischen den Netzen – und sie ist die unangenehmste, weil sie
#: **nichts** meldet: eine fehlende Tabelle legt ``create_all`` an, eine fehlende Spalte
#: das Netz darüber, eine gelöste ``NOT NULL`` das darunter. Eine Spalte mit zu kleiner
#: Skala nimmt den Wert **an** und rundet ihn weg. Bei ``NUMERIC(14, 2)`` und einem
#: dreistelligen Betrag (KWD) fehlt danach die letzte Stelle, und niemand sieht es.
#:
#: Dieselbe Lehre wie bei den Indizes (Testnotiz #778): **eine Typänderung, die nur in
#: einer Migration steht, erreicht die dev-Datenbank nie** – dort läuft kein
#: ``alembic upgrade``. Geprüft wird vorher, damit nicht bei jedem Start eine Tabelle
#: umgeschrieben wird.
_NUMERIC_SAFETY_NET: tuple[tuple[str, str, int, int], ...] = (
    ("deals", "amount", 18, 4),
    ("deal_entries", "amount", 18, 4),
)
# Für ``instances`` steht hier bewusst NICHTS mehr: die Tabelle wird von Migration 102
# neu aufgebaut. Ein Netz-Eintrag würde eine gerade entfernte Spalte wieder anlegen –
# das Netz darf reparieren, aber nicht auferstehen lassen. Die Einträge für orders /
# order_lines / purchase_orders / sales / shipments / movements / disposals /
# resource_usages / documents / inspections / article_process_steps / material_moves /
# instance_order_links sind mit ihren Tabellen entfallen.

#: **Spalten, die ihre ``NOT NULL``-Sperre verlieren.** Das Gegenstück zum Drop-Netz:
#: eine Spalte, die das Modell nicht mehr kennt, deren Sperre aber noch steht, lässt
#: **jedes** Insert auflaufen – und zwar sofort und für alle. Sie zu lösen ist der erste
#: von zwei Schritten (der Drop folgt im nächsten Deploy, wenn keine Vorgänger-Revision
#: sie mehr schreibt). Idempotent.
#:
#: Ein Eintrag hier lebt genau einen Deploy lang: er entsteht, wenn eine Spalte ihr
#: Mapping verliert, und geht mit ihrem Drop wieder (``purchases.quantity``/``article_id``
#: – Migrationen 115/116, gedroppt von 120). Das Netz bleibt trotzdem stehen: es ist der
#: erste von zwei Schritten der Zwei-Deploy-Regel, kein einmaliger Fix – wer es entfernt,
#: erfindet es beim nächsten unmapped gewordenen Pflichtfeld neu, und bis dahin laufen
#: alle Inserts auf.
_NULLABLE_SAFETY_NET: tuple[tuple[str, str], ...] = (
    # **«Ausser Betrieb» ist keine eigene Angabe mehr** (Testnotiz #773, Migration 121):
    # der Zustand eines Artikels ist die Projektion von ``replaced_by_id``. Die Spalte hat
    # ihr Mapping verloren; gedroppt wird sie im Folge-Deploy.
    ("articles", "status"),
    # ``payments``/``invoices``/``purchases`` haben mit dem Handel ihr Mapping verloren –
    # es schreibt niemand mehr hinein, also kann auch kein Insert an einer ``NOT NULL``
    # auflaufen. Die Tabellen bleiben stehen (Zwei-Deploy-Regel).
)

_DROP_COLUMN_SAFETY_NET = (
    # Gesellschaften (Migration 091): der «Betreiber» ist WÄHLBAR (``is_operator`` mit eigenem
    # Unique-Index) statt das starre «Hauptsitz»-Flag. ``is_primary`` ist tot – auch im Netz
    # gedroppt, falls Alembic 091 nicht durchlief (belt-and-suspenders).
    ("company_settings", "is_primary"),
    # Reste des per Notfall-Revert (#85) zurückgenommenen Konzepts «Standort als Instanz».
    ("articles", "is_location"),
    ("articles", "max_load_kg"),
    # Dokument-Redesign: das Dokument wurde im Auftrag verfasst (Nummer = Instanz).
    ("articles", "physical"),
    # Der Auftragsstatus ist ABGELEITET (Migration 107, ``process.order_status``) – eine
    # Spalte daneben wäre der zweite Ort, an dem er gesetzt wird.
    ("orders", "status"),
    # Dasselbe eine Ebene tiefer (Migration 107): eine Instanz ist eine Gruppe – ihren
    # Zustand leiten ihre Einzelinstanzen ab (``instances.status_of``). Die Spalte stand
    # auf ``new`` und wurde nie geschrieben.
    ("instances", "status"),
    # Der Modulname (Migration 108): ein Modul heisst nach seinem TYP, und als Identität
    # taugte ein Name nie – die ``id`` ist es. Das Pflichtfeld war zugleich die Quelle
    # der Meldung «String should have at least 1 character».
    ("process_steps", "name"),
    ("article_process_steps", "name"),
    # Die Erfassungsmaske am Artikel (Migration 106): was erfasst wird, sagt das **Modul**.
    # Am Artikel war es eine zweite Stelle für dieselbe Frage – und sie hing an keinem
    # Prozess. Auch im Netz gedroppt, falls Alembic 106 nicht durchlief.
    ("articles", "capture_fields"),
    # ►► **Der Folge-Deploy der Aufräumrunde (Migration 120).** ◄◄
    #
    # Zweiter Schritt der Zwei-Deploy-Regel: im Aufräum-Deploy verloren diese Spalten ihr
    # Mapping, jetzt fallen sie. Jede gehört zu einem Bereich, den es nicht mehr gibt
    # (``docs/attic.md``) – Verkauf/Shop, Zahlungen, Dokumente – bzw. zu einem Umbau am
    # Beschaffungs-Beleg (die Menge ist abgeleitet, 115; die Zeilen sagen was, 116).
    ("articles", "procurement_mode"),
    ("articles", "default_supplier_id"),
    ("articles", "default_webshop_url"),
    ("articles", "sales_published"),
    ("articles", "sales_visibility"),
    ("articles", "sales_fulfillment"),
    ("articles", "sales_content"),
    ("company_settings", "logo_path"),
    ("company_settings", "stripe_publishable_key"),
    ("company_settings", "hcaptcha_site_key"),
    ("company_settings", "shop_currencies"),
    ("company_settings", "shop_country_currency"),
    ("company_settings", "shop_default_currency"),
    ("company_settings", "payments_provider"),
    ("company_settings", "pricing_zone_factors"),
    ("company_settings", "infra_monthly_chf"),
    ("company_settings", "legal_documents"),
    ("company_settings", "default_receiving_location_id"),
    ("user_profiles", "stripe_customer_id"),
)
# Die Einträge für orders / order_lines / purchase_orders / sales / shipments / documents /
# inspections / article_process_steps sind mit ihren Tabellen entfallen (Migration 102).

# Indizes, die nach dem Initial-Schema ergänzt wurden. create_all() legt Indizes
# nur für NEUE Tabellen an – auf bestehenden Tabellen müssen sie idempotent
# nachgezogen werden (sonst Seq-Scans, z. B. auf dem wachsenden Audit-Log).
_INDEX_SAFETY_NET = (
    ("ix_audit_log_object_id", "audit_log", "object_id"),
    ("ix_audit_log_table_name", "audit_log", "table_name"),
    ("ix_company_settings_object_id", "company_settings", "object_id"),
    # Neues Datenmodell: der Feed filtert Instanzen je Artikel, das Detail zählt die
    # Einzelinstanzen einer Instanz. Beides ohne Index ein Seq-Scan über den Bestand.
    ("ix_instances_article_id", "instances", "article_id"),
    ("ix_instance_units_instance_id", "instance_units", "instance_id"),
    ("ix_captures_instance_unit_id", "captures", "instance_unit_id"),
    ("ix_captures_order_id", "captures", "order_id"),
    ("ix_captures_step_id", "captures", "step_id"),
)

# Roh-Indizes mit speziellem Typ: GIN auf der Reservierungs-Map – die Hot-Path-Abfragen
# ``Instance.reservations.has_key(...)`` (Unterdeckung, Verkaufs-Abgang, Abschluss)
# wären sonst Full-Table-Scans über den gesamten Bestand.
_RAW_INDEX_SAFETY_NET: tuple[str, ...] = (
    # ►► Die Exklusivitätsregel (PROCESS_CORE.md §3). Sie ist kein Beiwerk: ohne diesen
    #    Index kann dieselbe Einzelinstanz in zwei Aufträgen aktiv sein, und zwar genau
    #    dann, wenn zwei Freigaben gleichzeitig laufen – der Fall, den eine Prüfung in
    #    der Anwendungslogik nicht abdeckt. ``create_all`` legt ihn mit der Tabelle an;
    #    hier steht er für den Fall, dass die Tabelle schon ohne ihn existiert.
    "DO $$ BEGIN IF to_regclass('public.order_units') IS NOT NULL THEN "
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_order_units_active "
    "ON order_units (instance_unit_id) WHERE released_at IS NULL; END IF; END $$;",
    # ►► Die **Journey** (services/journey): «welcher Auftrag war vor bzw. nach diesem?»
    #    ist ein Sprung an die Nachbar-Zeile derselben Einzelinstanz. Ohne diesen Index
    #    wird daraus ein Sortieren über alle Ereignisse des Stücks.
    "DO $$ BEGIN IF to_regclass('public.process_events') IS NOT NULL THEN "
    "CREATE INDEX IF NOT EXISTS ix_process_events_unit_timeline "
    "ON process_events (instance_unit_id, id); END IF; END $$;",
    # ►► Die **Verbindung** (Migration 109): «wer wartet auf Rückführung» ist eine Frage
    #    an diese Spalte, und sie wird bei jedem Auftrags-Feed gestellt.
    "DO $$ BEGIN IF to_regclass('public.order_units') IS NOT NULL "
    "AND EXISTS (SELECT 1 FROM information_schema.columns "
    "WHERE table_name='order_units' AND column_name='return_to_order_id') THEN "
    "CREATE INDEX IF NOT EXISTS ix_order_units_return_to_order_id "
    "ON order_units (return_to_order_id); END IF; END $$;",
    # ►► **Die Vorauswahl der Stück-Auswahl** (Migration 113): «die ältesten Stücke
    #    dieser Instanz, die im Regal liegen» – genau die Form, für die ein
    #    zusammengesetzter Index gebaut ist. Gemessen bei 50 000 Stücken: 15,3 → 1,2 ms.
    "DO $$ BEGIN IF to_regclass('public.instance_units') IS NOT NULL THEN "
    "CREATE INDEX IF NOT EXISTS ix_instance_units_instance_status "
    "ON instance_units (instance_id, status, id); END IF; END $$;",
    # ►► **Der Ort ist EINE Aussage** (Migration 112). Ohne diesen Riegel könnte ein
    #    Stück gleichzeitig im Regal und in einem Getriebe liegen – und welche der beiden
    #    Angaben gilt, entschiede die Lesestelle. Er steht hier und nicht nur in der
    #    Migration, weil ``create_all`` ihn nicht kennt: dasselbe Netz, dieselbe Lehre
    #    aus Migration 090, nur für einen ``CHECK`` statt eine Spalte.
    "DO $$ BEGIN IF to_regclass('public.instance_units') IS NOT NULL "
    "AND EXISTS (SELECT 1 FROM information_schema.columns "
    "WHERE table_name='instance_units' AND column_name='place_unit_id') "
    "AND NOT EXISTS (SELECT 1 FROM pg_constraint "
    "WHERE conname='ck_instance_units_one_place') THEN "
    "ALTER TABLE instance_units ADD CONSTRAINT ck_instance_units_one_place "
    "CHECK (place_object_id IS NULL OR place_unit_id IS NULL); END IF; END $$;",
    # ►►► **EIN AKTIVER Beleg je Modul** (Migration 119) – und die Lehre daraus. ◄◄◄
    #
    # Migration 114 legte ``uq_purchases_step`` als **vollen** Unique-Index an, 119 machte
    # ihn **partiell** (``WHERE is_active``), weil ein zurückgenommener Beleg als Zeile
    # stehenbleibt. Genau dieser Wechsel erreichte eine gewachsene Datenbank **nie**:
    # ``create_all`` legt Indizes nur mit einer *neuen* Tabelle an, und der Deploy fährt
    # kein ``alembic upgrade`` – dort stand also weiter der volle Index. Wer zwischen
    # «Beschaffen» und «Selbst» hin- und herschaltete, bekam beim zweiten Mal «Dieser Wert
    # ist bereits vergeben» (Testnotiz #778); gegen ein migrationsgebautes Schema war es
    # nicht nachstellbar.
    #
    # **Die Regel, die daraus folgt:** jeder Index und jeder CHECK, den eine Migration
    # *nach* dem Entstehen der Tabelle geändert hat, gehört in dieses Netz – sonst gilt er
    # ausschliesslich dort, wo Alembic läuft.
    #
    # Ersetzt wird **nur, wenn er noch nicht partiell ist**: ein bedingungsloser DROP
    # nähme den Exklusivitäts-Riegel für die Dauer der Anweisung weg.
    "DO $$ BEGIN IF to_regclass('public.purchases') IS NOT NULL "
    "AND EXISTS (SELECT 1 FROM pg_indexes WHERE indexname='uq_purchases_step' "
    "AND indexdef NOT ILIKE '%%WHERE%%is_active%%') THEN "
    "DROP INDEX uq_purchases_step; "
    "CREATE UNIQUE INDEX uq_purchases_step ON purchases (step_id) WHERE is_active; "
    "END IF; END $$;",
)

# Gesellschaften (Migration 091): genau EIN Betreiber. Wurde die Spalte gerade erst vom
# Sicherheitsnetz ergänzt (Default ``false``), trüge sonst KEINE Zeile die Markierung –
# lesend fiele ``sites.find_operator`` zwar auf die kleinste ``id`` zurück, aber der
# gewählte Betreiber wäre nicht persistent. Wiederholbar; ein bereits gewählter Betreiber
# bleibt unberührt. Der partielle Unique-Index erzwingt «höchstens einer».
#: Statuswerte auf die EINE Liste ziehen (Migration 107), falls Alembic nicht durchlief.
#: Ein Artikel mit ``released`` wäre sonst ein Wert, den die Anzeige nicht kennt – und
#: der Feed zeigte den rohen Schlüssel statt eines Wortes.
#: **Der Artikel-Status ist abgeleitet** (Testnotiz #773) – die Spalte trägt nur noch
#: Altbestand. Geheilt wird darum genau das, was ohne den entfernten Schalter für immer
#: stillgelegt bliebe: ein «inaktiv», das **kein** Nachfolger erklärt. Wo einer steht,
#: bleibt der Wert stehen; er stimmt dann mit der Ableitung überein.
_ARTICLE_STATUS_FIXES = (
    "UPDATE articles SET status = 'freigegeben' "
    "WHERE status <> 'freigegeben' AND replaced_by_id IS NULL",
    "UPDATE articles SET status = 'inaktiv' "
    "WHERE status <> 'inaktiv' AND replaced_by_id IS NOT NULL",
    "UPDATE orders SET name = 'Auftrag ' || object_id WHERE name IS NULL OR name = ''",
)

_COMPANY_DATA_FIXES = (
    "UPDATE company_settings SET is_operator = true "
    "WHERE id = (SELECT min(id) FROM company_settings) "
    "AND NOT EXISTS (SELECT 1 FROM company_settings WHERE is_operator)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_company_settings_operator "
    "ON company_settings (is_operator) WHERE is_operator",
)


def _ensure_columns() -> None:
    """Fehlende Spalten idempotent ergänzen, obsolete entfernen und Altdaten
    normalisieren, falls eine Migration nicht lief. create_all() ändert
    bestehende Tabellen NICHT."""
    try:
        with engine.connect() as conn:
            # **Der Inspektor sitzt auf DERSELBEN Verbindung wie die DDL.**
            #
            # ``inspect(engine)`` zieht eine ZWEITE Verbindung aus dem Pool – und die
            # blockiert, sobald diese hier eine Tabelle geändert hat: das ``ALTER TABLE``
            # hält bis zum ``commit`` am Ende der Funktion einen ACCESS-EXCLUSIVE-Lock,
            # und die nächste Reflexion derselben Tabelle wartet darauf. Sie wartet auf
            # eine Transaktion, die erst nach ihr fertig wird – der Start bliebe für
            # immer stehen.
            #
            # Der Fehler war latent, solange keine Aufräum-Anweisung eine Tabelle traf,
            # die danach noch gelesen wird; der erste ``DROP COLUMN`` auf ``instances``
            # hat ihn ausgelöst. Auf einer Verbindung kann er nicht wieder entstehen –
            # und nebenbei sieht die Reflexion jetzt, was diese Funktion eben geändert
            # hat, statt einen Stand von vorher.
            insp = inspect(conn)
            tables = set(insp.get_table_names())
            for table, col, ddl in _COLUMN_SAFETY_NET:
                if table not in tables:
                    continue
                if col not in {c["name"] for c in insp.get_columns(table)}:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {ddl}"
                    ))
            for table, col, precision, scale in _NUMERIC_SAFETY_NET:
                if table not in tables:
                    continue
                found = {c["name"]: c for c in insp.get_columns(table)}.get(col)
                if found is None or getattr(found["type"], "scale", None) == scale:
                    continue
                conn.execute(text(
                    f"ALTER TABLE {table} ALTER COLUMN {col} "
                    f"TYPE NUMERIC({precision}, {scale})"
                ))
            for table, col in _NULLABLE_SAFETY_NET:
                if table in tables and col in {c["name"] for c in insp.get_columns(table)}:
                    conn.execute(text(
                        f"ALTER TABLE {table} ALTER COLUMN {col} DROP NOT NULL"
                    ))
            for table, col in _DROP_COLUMN_SAFETY_NET:
                if table in tables:
                    conn.execute(text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {col}"))
            for index_name, table, col in _INDEX_SAFETY_NET:
                if table in tables and col in {c["name"] for c in insp.get_columns(table)}:
                    conn.execute(text(
                        f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({col})"
                    ))
            for stmt in _RAW_INDEX_SAFETY_NET:
                conn.execute(text(stmt))
            # ►► **Endzustände sind terminal – und das steht in der Datenbank.**
            #
            # Der Trigger wird bei **jedem Start** aus der Statusliste neu erzeugt, nicht
            # nur von der Migration. Das ist der Unterschied zwischen einer Zusage und
            # einer Momentaufnahme: kommt ein zweiter Endzustand in den Katalog, gilt er
            # ab dem nächsten Start auch unten – niemand muss daran denken, und die
            # Datenbank kann von der einen Liste nicht abweichen.
            conn.execute(text(st.terminal_guard_sql()))
            # ►► **Das Schema wird hier festgeschrieben, bevor Daten angefasst werden.**
            #
            # DDL ist in PostgreSQL transaktional: bis hierher hängt jede ergänzte Spalte
            # an derselben Transaktion wie die Daten-Reparaturen darunter. Scheitert EINE
            # davon, rollt sie **alles** zurück – auch die Spalten. Genau das ist die
            # Ausfallklasse von Migration 090, nur eine Ebene tiefer: das Netz ist der
            # zweite Weg, und beim Ausfall zählt nur der zweite Weg. Eine Daten-Reparatur
            # darf ihn nicht mitreissen.
            conn.commit()
            # **Auch die Spalte wird geprüft, nicht nur die Tabelle.** ``articles.status``
            # hat ihr Mapping verloren (Testnotiz #773) und fällt im Folge-Deploy – eine
            # Reparatur, die nur nach der Tabelle fragt, wäre danach die Anweisung, die
            # das ganze Netz reisst.
            for stmt in _ARTICLE_STATUS_FIXES:
                table = stmt.split()[1]
                if table not in tables:
                    continue
                columns = {c["name"] for c in insp.get_columns(table)}
                if all(word in columns for word in ("status", "replaced_by_id")) \
                        or table != "articles":
                    conn.execute(text(stmt))
            if "instance_units" in tables:
                # Der Platzhalter-Status ``new`` aus dem Basis-Neuaufbau gibt es mit der
                # geschlossenen Liste nicht mehr (Migration 104). Ein Stück, das in keinem
                # Auftrag steckt, ist einsatzbereit – genau das heisst ``freigegeben``.
                # Bleibt der Altwert stehen, lässt sich das Stück nie starten: das
                # Start-Objekt erwartet ``freigegeben`` und lehnt sauber ab.
                #
                # ►► **Die Liste kommt aus dem Katalog – und das ist hier der ganze Punkt.**
                #
                # Diese Reparatur stand einmal als ``NOT IN ('freigegeben','im_prozess')``
                # da, weil es damals nur diese beiden Zustände gab. Sie ist damit still
                # veraltet, als ``Gesperrt`` und ``Verschrottet`` dazukamen: seither hat
                # **jeder Start** – also jeder Deploy – jedes ausgesonderte Stück wieder auf
                # ``freigegeben`` gesetzt. Ein verschrottetes Stück wurde grün, und zwar
                # nicht beim Abschluss eines Auftrags, sondern beim nächsten Neustart. In
                # keiner einzelnen Anfrage war das nachstellbar.
                #
                # Repariert wird darum nur noch, was der Katalog **nicht kennt** (der alte
                # Platzhalter, Fremdwerte). Ein Zustand, der in ``CATALOG`` steht, ist per
                # Konstruktion nicht mehr betroffen – die Liste kann nicht wieder veralten.
                conn.execute(
                    text(
                        "UPDATE instance_units SET status = :fallback "
                        "WHERE status IS NULL OR status <> ALL(:known)"
                    ),
                    {"fallback": st.INITIAL_UNIT_STATUS, "known": list(st.UNIT_STATUSES)},
                )
            if "company_settings" in tables:
                # Über information_schema auf DERSELBEN Verbindung prüfen – ``insp`` stammt
                # von VOR dem ADD-COLUMN-Lauf und sähe die eben ergänzte Spalte nicht
                # (gleiche Begründung wie beim ``documents``-Block oben).
                cs_cols = {r[0] for r in conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='company_settings'"))}
                if "is_operator" in cs_cols:
                    for stmt in _COMPANY_DATA_FIXES:
                        conn.execute(text(stmt))
            conn.commit()
    except Exception as e:
        print(f"WARNING: _ensure_columns() failed: {e}", flush=True)


def _ensure_object_id_sequence() -> None:
    """Objektnummern-Sequence anlegen und (einmalig) an Altdaten ausrichten.

    Idempotent und rewind-sicher: hebt die Sequence höchstens auf den höchsten
    bereits vergebenen Stand – nie darunter. Auf einer leeren DB bleibt der Start
    bei OBJ_ID_START. Migration ``021`` macht dasselbe; diese Funktion ist das
    Fallback, falls die Migration übersprungen wurde/fehlschlug."""
    from .services.objects import OBJ_ID_START, OBJECT_ID_SEQUENCE, current_max_object_id
    db = SessionLocal()
    try:
        db.execute(text(
            f"CREATE SEQUENCE IF NOT EXISTS {OBJECT_ID_SEQUENCE} AS BIGINT "
            f"START WITH {OBJ_ID_START} MINVALUE {OBJ_ID_START}"
        ))
        db.commit()
        max_id = current_max_object_id(db)
        if max_id >= OBJ_ID_START:
            db.execute(text(
                f"SELECT setval('{OBJECT_ID_SEQUENCE}', "
                f"GREATEST((SELECT last_value FROM {OBJECT_ID_SEQUENCE}), :m), true)"
            ), {"m": max_id})
            db.commit()
    except Exception as e:
        print(f"WARNING: _ensure_object_id_sequence() failed: {e}", flush=True)
    finally:
        db.close()


# Eigener Advisory-Lock für die (potenziell destruktive) Registry-Reparatur,
# damit parallele Worker/Instanzen sie serialisieren (kein Drop-Recreate-Race).
_REGISTRY_LOCK_KEY = 778_899_002


def _ensure_object_registry_shape() -> None:
    """Die Objekt-Registry ``objects`` muss dem aktuellen ``ObjectRef``-Modell
    entsprechen (``object_id`` als Schlüssel, ``object_type``, ``created_at``).

    Auf gewachsenen Datenbanken existiert evtl. noch eine **veraltete** ``objects``-
    Tabelle aus einem früheren Modell (Spalte ``id`` statt ``object_id``).
    ``create_all()`` ändert bestehende Tabellen nicht, daher schlägt JEDE
    Objektanlage mit «column object_id … does not exist» fehl. Hier wird die
    veraltete Tabelle verworfen und korrekt neu angelegt – die Registry ist eine
    reine Ableitung der Fachtabellen (``_backfill_object_registry`` füllt sie neu).
    Idempotent und über einen Advisory-Lock gegen Nebenläufigkeit abgesichert."""
    db = SessionLocal()
    try:
        # Serialisiert diese Reparatur über alle Worker/Instanzen (eine Transaktion).
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _REGISTRY_LOCK_KEY})
        exists = db.execute(text("SELECT to_regclass('public.objects')")).scalar() is not None
        if exists:
            has_object_id = db.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'objects' AND column_name = 'object_id'"
            )).first() is not None
            if not has_object_id:
                db.execute(text("DROP TABLE objects CASCADE"))
        db.execute(text(
            "CREATE TABLE IF NOT EXISTS objects ("
            "object_id BIGINT PRIMARY KEY, "
            "object_type VARCHAR(30) NOT NULL, "
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now())"
        ))
        db.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_objects_object_type ON objects (object_type)"
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"WARNING: _ensure_object_registry_shape() failed: {e}", flush=True)
    finally:
        db.close()


def _backfill_object_registry() -> None:
    """Zentrale Objekt-Registry mit allen vorhandenen Objektnummern auffüllen
    (Altdaten + ohne Typ vergebene). Idempotent."""
    from .services.objects import backfill_registry, ensure_foreign_keys
    db = SessionLocal()
    try:
        backfill_registry(db)
        db.commit()
        ensure_foreign_keys(db)   # FK-Integrität der Quer-Referenzen (best-effort)
    except Exception as e:
        db.rollback()
        print(f"WARNING: _backfill_object_registry() failed: {e}", flush=True)
    finally:
        db.close()


def _ensure_company_object_id() -> None:
    """Das Unternehmen (Singleton) als nummerierten ERP-Datensatz sicherstellen:
    fehlt die Objektnummer, wird sie hier EINMALIG beim Start vergeben – deploy-
    deterministisch und unabhängig davon, ob jemand die Admin-Einstellungen öffnet
    (der öffentliche Settings-Endpoint vergibt bewusst keine Nummern)."""
    from .services.sites import operator
    db = SessionLocal()
    try:
        operator(db)   # legt die erste Gesellschaft an + vergibt die Objektnummer
    except Exception as e:
        db.rollback()
        print(f"WARNING: _ensure_company_object_id() failed: {e}", flush=True)
    finally:
        db.close()


def _shape_problem(insp, table: str, model) -> Optional[str]:
    """Kann diese Tabelle das Modell bedienen? Nennt den **Grund**, wenn nicht.

    Zwei Befunde, und beide sind fatal – der zweite ist der, den man vergisst:

    * eine **erwartete Spalte fehlt** → jede Abfrage endet in «column … does not exist»;
    * eine **fremde Pflichtspalte** (NOT NULL ohne Vorgabe) steht da → jedes ``INSERT``
      scheitert, obwohl alle erwarteten Spalten vorhanden sind.

    Eine fremde *nullable* Spalte bleibt unangetastet: sie stört nichts, und Reparieren,
    was nicht kaputt ist, wäre hier besonders teuer (der Fix ist ein ``DROP TABLE``).
    """
    cols = {c["name"]: c for c in insp.get_columns(table)}
    expected = set(model.__table__.columns.keys())
    missing = sorted(expected - set(cols))
    if missing:
        return f"es fehlen {', '.join(missing)}"
    blocking = sorted(
        name for name, c in cols.items()
        if name not in expected and not c["nullable"] and c.get("default") is None
    )
    if blocking:
        return f"fremde Pflichtspalten: {', '.join(blocking)}"
    return None


def _ensure_rebuilt_tables_shape() -> None:
    """Tabellen, die **neu aufgebaut** statt migriert wurden, ans Modell angleichen.

    ``create_all()`` legt nur **fehlende** Tabellen an. Eine vorgefundene Tabelle mit
    fremder Form fasst es nicht an – und genau das ist der Ausfall, den man erst im
    Betrieb sieht: nicht ein 500 beim Deploy, sondern ein 500 beim ersten Klick.

    Für diese Tabellen ist eine fremde Form **keine Altdaten-Frage**: der Basis-Neuaufbau
    (Migration 102 ff.) hat sie ausdrücklich verworfen und neu angelegt, ihr Inhalt aus
    der Vorgängerwelt ist irrelevant. Was hier steht und nicht passt, ist darum kein
    Bestand, den man retten müsste, sondern eine Tabelle, die nichts bedienen kann.

    **Der Fall ist real:** in der Testumgebung stand noch das ``article_process_steps``
    aus dem Vorgängersystem (``step_type``, ``order_id NOT NULL``, kein ``module_type``).
    Migration 102 hätte sie gedroppt und 105 neu angelegt – lief Alembic aber nicht durch,
    blieb die alte stehen, ``create_all`` übersprang sie, und **jeder** Aufruf des Reiters
    «Erzeugungsprozess» endete in «column article_process_steps.module_type does not
    exist». Ein Netz-Eintrag je fehlender Spalte hätte hier nicht gereicht: es fehlten
    fünf, und ``order_id NOT NULL`` hätte danach jedes ``INSERT`` gekippt.
    """
    from sqlalchemy import inspect
    from .models import (
        ArticleProcessStep, Attachment, Capture, Instance, InstanceUnit, Order,
        OrderLine, OrderUnit, ProcessEvent, ProcessStep,
    )
    models = (
        # Der Prozess-Kern (PROCESS_CORE.md §11) – von 102/103/104/105 neu aufgebaut.
        Instance, InstanceUnit, Capture,
        Order, OrderLine, OrderUnit, ProcessStep, ArticleProcessStep, ProcessEvent,
        # Bild-Uploads: derselbe Fall, nur älter (fehlendes ``token`` → jeder Upload 500).
        Attachment,
    )
    try:
        insp = inspect(engine)
        present = set(insp.get_table_names())
        for model in models:
            table = model.__tablename__
            if table not in present:
                model.__table__.create(bind=engine, checkfirst=True)
                continue
            problem = _shape_problem(insp, table, model)
            if problem is None:
                continue
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            model.__table__.create(bind=engine, checkfirst=True)
            # Laut, nicht still: eine stumme Reparatur sähe aus wie «war schon immer so».
            print(f"INFO: Tabelle {table} neu aufgebaut – {problem}.", flush=True)
    except Exception as e:
        print(f"WARNING: _ensure_rebuilt_tables_shape() failed: {e}", flush=True)




# Advisory-Lock-Schlüssel: Schema-/Daten-Fixups laufen genau EINMAL – auch bei
# mehreren uvicorn-Workern oder mehreren Cloud-Run-Instanzen (Lock liegt in der DB).
_STARTUP_LOCK_KEY = 778_899_001


def _run_startup_fixups_once() -> None:
    """Alle Startup-Mutationen (Schema-Nachzug, Registry, Prozess-Backfill, Pflicht-
    Bewegungen, Wiederkehr) unter einem DB-Advisory-Lock ausführen, damit sie sich
    bei parallelem Start nicht in die Quere kommen (verhindert doppelte Prozesse/
    Bewegungen und Lock-Konflikte → keine sporadischen 5xx kurz nach dem Deploy)."""
    db = SessionLocal()
    acquired = False
    try:
        acquired = bool(db.execute(text("SELECT pg_try_advisory_lock(:k)"),
                                   {"k": _STARTUP_LOCK_KEY}).scalar())
        if not acquired:
            print("INFO: Startup-Fixups laufen bereits (anderer Worker/Instanz) – übersprungen.", flush=True)
            return
        # **Erst die Spalten, dann als LETZTES Mittel die Form.**
        #
        # Umgekehrt war es datenvernichtend: eine bloss fehlende Spalte ist genau der
        # Fall, den das Spaltennetz behebt – der Formwächter dagegen kann nur eines,
        # nämlich DROP TABLE. Lief Alembic 107 nicht durch, warf er die ganze
        # ``orders``-Tabelle weg («es fehlen name»), obwohl der Eintrag daneben die
        # Spalte in einer Zeile ergänzt hätte. Gemessen, nicht vermutet: auf einer
        # 106er-Datenbank war der Alt-Auftrag danach spurlos verschwunden.
        #
        # In dieser Reihenfolge ist der Neuaufbau das, was er sein soll: die Antwort auf
        # eine Form, die auch nach dem Netz noch unbenutzbar ist (fremde Pflichtspalten
        # aus einer alten Welt) – und nicht die erste Reaktion auf eine fehlende Spalte.
        _ensure_columns()
        _ensure_rebuilt_tables_shape()
        _ensure_object_id_sequence()
        _backfill_object_registry()
        _ensure_company_object_id()   # Firma = nummerierter ERP-Datensatz
    except Exception as e:
        print(f"WARNING: _run_startup_fixups_once() failed: {e}", flush=True)
    finally:
        if acquired:
            try:
                db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _STARTUP_LOCK_KEY})
                db.commit()
            except Exception:
                pass
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Safety-Net: fehlende Tabellen idempotent anlegen, falls eine Migration
        # übersprungen wurde oder fehlschlug. create_all() ändert bestehende
        # Tabellen NICHT – Schema-Änderungen bleiben Sache von Alembic.
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"WARNING: create_all() failed: {e}", flush=True)
    # Den universellen Nummernkreis-Generator IMMER sicherstellen – NICHT hinter
    # dem Advisory-Lock. Sonst startet ein Worker, der den Lock nicht erhält, ohne
    # ``object_id_seq`` und JEDE Objektanlage (Artikel/Auftrag/…) endet in einem
    # 500 (``nextval`` auf fehlende Sequence). Idempotent & nebenläufigkeitssicher.
    _ensure_object_id_sequence()
    # Objekt-Registry auf die aktuelle Form bringen (veraltete `objects`-Tabelle
    # ohne `object_id` → Neuanlage). Ebenfalls IMMER, race-sicher per Advisory-Lock.
    _ensure_object_registry_shape()
    # Übrige Schema-/Daten-Fixups genau einmal (Advisory-Lock, cross-worker/-instanz).
    _run_startup_fixups_once()
    try:
        _bootstrap_admin()
    except Exception as e:
        print(f"WARNING: _bootstrap_admin() failed: {e}", flush=True)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Ein verletzter DB-Constraint ist ein **Eingabe**-Fehler, kein Serverabsturz.

    Vorher fiel er in die letzte Auffanglinie unten und erschien im Formular als roher
    psycopg2-Dump («NotNullViolation … Failing row contains (2, Inexxio LLC, null, Dah…»,
    Testnotiz #338): unlesbar, und er verriet nebenbei den Zeileninhalt. Hier wird daraus
    ein 400 mit einem Satz, der die betroffene **Spalte** nennt – die eigentliche Ursache
    gehört ins Log, nicht in die Oberfläche."""
    tb = traceback.format_exc()
    print(f"ERROR: IntegrityError on {request.method} {request.url.path}\n{tb}", flush=True)
    raw = str(getattr(exc, "orig", exc))
    column = None
    match = re.search(r'column "([^"]+)"', raw)
    if match:
        column = match.group(1)
    if "not-null" in raw or "NotNullViolation" in raw:
        detail = (f"Pflichtangabe «{column}» fehlt." if column
                  else "Eine Pflichtangabe fehlt.")
    elif "unique" in raw.lower():
        detail = (f"«{column}» ist bereits vergeben." if column
                  else "Dieser Wert ist bereits vergeben.")
    else:
        detail = "Die Angaben verletzen eine Datenbank-Regel und wurden nicht gespeichert."
    return JSONResponse(status_code=400, content={"detail": detail, "code": "INTEGRITY_ERROR"})


#: Rohe Pydantic-Meldungen → Klartext. Sie sagen, was die **Regel** war, nie was der
#: Mensch tun soll: «String should have at least 1 character» ist wahr und trotzdem
#: unbrauchbar (Testnotiz #686). Was hier nicht steht, wird als Regel-Satz durchgereicht –
#: sichtbar bleibt er, nur mit Feldnamen davor.
_VALIDATION_TEXTS: tuple[tuple[str, str], ...] = (
    ("Field required", "fehlt"),
    ("at least 1 character", "darf nicht leer sein"),
    ("at least", "ist zu kurz"),
    ("at most", "ist zu lang"),
    ("valid integer", "muss eine ganze Zahl sein"),
    ("valid number", "muss eine Zahl sein"),
    ("valid boolean", "muss ja oder nein sein"),
    ("greater than or equal", "ist zu klein"),
    ("less than or equal", "ist zu gross"),
    ("valid list", "muss eine Liste sein"),
    ("valid dictionary", "hat die falsche Form"),
)

#: Feldnamen → das Wort, das der Mensch auf dem Bildschirm sieht. Ein Feld, das hier
#: fehlt, erscheint mit seinem technischen Namen – unschön, aber ehrlich, und es fällt
#: auf. Eine erfundene Übersetzung wäre schlimmer.
_FIELD_LABELS: dict[str, str] = {
    "name": "Name",
    "quantity": "Menge",
    "size": "Abmessungen",
    "weight_kg": "Gewicht",
    "unit": "Mengeneinheit",
    "serialization": "Serialisierung",
    "module_type": "Modultyp",
    "label": "Bezeichnung",
    "type": "Typ",
    "target": "Sollwert",
    "tolerance": "Toleranz",
    "points": "Erfassungspunkte",
    "steps": "Prozessschrittmodule",
    "lines": "Definitionszeilen",
    "article_object_id": "Artikel",
    "origin": "Herkunft",
    "values": "Erfassung",
    "config": "Konfiguration",
}


def _field_path(loc: tuple) -> str:
    """``('body', 'steps', 0, 'name')`` → «Prozessschrittmodule → 1 → Name».

    **Wo** der Fehler steckt, ist die halbe Meldung. Ohne den Pfad steht bei einem
    Auftrag mit acht Modulen nur da, dass irgendwo etwas zu kurz ist. Listen-Indizes
    werden dabei ab 1 gezählt – für einen Menschen ist das erste Modul das erste.
    """
    parts: list[str] = []
    for item in loc:
        if item in ("body", "query", "path"):
            continue
        if isinstance(item, int):
            parts.append(str(item + 1))
        else:
            parts.append(_FIELD_LABELS.get(str(item), str(item)))
    return " → ".join(parts)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Eingabefehler in **Klartext**: was fehlt, und wo.

    Vorher reichte FastAPI seine Liste roher Validator-Texte durch, und die Oberfläche
    zeigte sie unverändert an – «String should have at least 1 character», ohne Feld,
    ohne Ort (Testnotiz #686). Der Nutzer sah kein Feld, in dem etwas fehlte, weil das
    betroffene gar nicht auf seinem Bildschirm stand.

    Die Regel für **jede** Fehlermeldung: sie sagt, **was** fehlt und **wo**. Rohe
    Validator-Texte gehören ins Log, nicht ins Formular. Darum steht dieser Handler an
    genau einer Stelle statt als Übersetzung an jedem Endpunkt.
    """
    seen: list[str] = []
    for err in exc.errors():
        where = _field_path(tuple(err.get("loc") or ()))
        # ``Value error, …`` ist Pydantic-Rahmen um eine **selbst geschriebene** Meldung
        # aus einem Feld-Validator. Die ist bereits Klartext – sie braucht die Übersetzung
        # nicht, nur den Rahmen weg.
        raw = str(err.get("msg") or "").removeprefix("Value error, ")
        what = next((text for needle, text in _VALIDATION_TEXTS if needle in raw), raw)
        # Nennt die Meldung ihr Feld schon selbst, wäre der Pfad davor ein Stottern
        # («Name: Name ist ein Pflichtfeld»).
        head = where.split(" → ")[-1] if where else ""
        line = what if (head and head.lower() in what.lower()) else (
            f"{where}: {what}" if where else what)
        if line not in seen:
            seen.append(line)
    print(f"WARNING: 422 on {request.method} {request.url.path} – {exc.errors()}", flush=True)
    return JSONResponse(
        status_code=422,
        content={"detail": " · ".join(seen) or "Die Eingaben sind unvollständig.",
                 "code": "VALIDATION_ERROR"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Letzte Auffanglinie für unbehandelte Fehler.

    Ohne diesen Handler liefert Starlette einen **text/plain** «Internal Server
    Error» ohne jede Diagnose – der Client kann ihn nicht als JSON lesen und zeigt
    nur «Server nicht erreichbar». Hier wird der vollständige Traceback in die
    Logs geschrieben (Cloud Run) und eine **strukturierte JSON-Antwort** geliefert.
    Ausserhalb der Produktion enthält ``detail`` die echte Ursache (Diagnose);
    HTTPException wird davon nicht erfasst (eigener Handler)."""
    tb = traceback.format_exc()
    print(f"ERROR: Unhandled exception on {request.method} {request.url.path}\n{tb}", flush=True)
    expose = settings.debug or settings.app_env.lower() != "production"
    detail = f"{type(exc).__name__}: {exc}" if expose else "Interner Serverfehler"
    return JSONResponse(status_code=500, content={"detail": detail, "code": "INTERNAL_ERROR"})

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(passkey.router)
app.include_router(contact.router)
app.include_router(admin.router)
app.include_router(erp.router)
app.include_router(articles.router)
app.include_router(orders.router)
app.include_router(instances.router)
app.include_router(places.router)
app.include_router(attachments.router)
app.include_router(payments.router)
app.include_router(feedback.router)


@app.get("/")
async def root():
    return {
        "name": "Inexxio ECS API",
        "version": settings.app_version,
        "docs": "/api/docs",
    }
