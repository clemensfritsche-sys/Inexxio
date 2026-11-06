"""►►► **Das Log – wie es geschrieben wird, steht in der Datenbank.** ◄◄◄

Fachschicht ohne Datenbank-Zugriff: hier stehen die Regeln, aus denen der Start
(``main._sync_database_rules``) die Funktionen und Trigger **bei jedem Lauf** neu schreibt –
dieselbe Bauart wie ``statuses.terminal_guard_sql`` und ``timekeeping.append_only_sql``.

* ``log_actor()`` – **wer handelt**, aus der Transaktion (``SET LOCAL inexxio.actor``, gesetzt
  an EINER Stelle: ``services/log.act``). Fehlt er, scheitert das Schreiben – lieber laut als
  ohne Spur.
* ``log_row()`` – der Trigger an **jeder** Tabelle (``OBJECT`` sagt, an welchem Datensatz eine
  Zeile hängt). Nur Geändertes, ``updated_at`` zählt nicht; Geheimes und Binäres steht nie
  im Klartext da; ein langer Wert (``LONG_VALUE``) nur als Prüfsumme (``log_shorten``).
* ``log_event(…)`` – ein fachliches Ereignis, das keine Zeile ändert, in derselben
  Transaktion.
* ``log_immutable()`` – ``UPDATE``, ``DELETE`` und ``TRUNCATE`` auf ``log`` und ``log_seal``
  werden abgewiesen; einzige Ausnahme ist ``log_redact`` (Datenschutz), die sich selbst
  einträgt und die betroffenen Tage nennt. Sie schwärzt nie Prozess-Ereignisse (``process.*``
  tragen keine Personendaten, nur Nummern und Zustände – Bild, Protokoll und Journey lesen
  daraus). Die Sperre ist eine Regel gegen Versehen, keine gegen jemanden mit Zugang zur
  Datenbank (derselbe Benutzer): dagegen steht das Siegel.
* ``log_seal_due()`` / ``log_verify()`` – je abgeschlossenem Tag eine Prüfsumme, verkettet
  mit der des Vortags.
"""

#: Wer handelt.
KINDS = ("person", "ai", "system", "external")
#: Woher eine Handlung kommt.
SOURCES = ("ui", "capture", "web", "link", "webhook", "login", "probe", "job", "start",
           "migration", "mcp", "test")

#: Diese Spaltennamen stehen nie im Klartext im Log (Zugangs-Token, Schlüssel, Challenges).
#: Binäre Spalten (Dateien, Schlüssel) kommen von selbst dazu (``main``, aus den Modellen).
SECRET_COLUMNS = frozenset({"token", "challenge", "public_key", "credential_id"})

#: Tabellen ohne Zeilen-Trigger – mit Grund.
EXEMPT = {
    "log": "das Log selbst (unveränderlich, eigener Trigger)",
    "log_seal": "die Siegel des Logs (unveränderlich, eigener Trigger)",
    "process_log": "eine Sicht auf das Log, keine Tabelle",
}


def _own(column: str) -> str:
    """Die Zeile trägt die Objektnummer selbst."""
    return f"SELECT ($1->>'{column}')::bigint"


def _via(fk: str, table: str, key: str = "id", number: str = "object_id") -> str:
    """Die Objektnummer steht an der Zeile, auf die ``fk`` zeigt."""
    return f"SELECT {number} FROM {table} WHERE {key} = ($1->>'{fk}')::bigint"


#: Die Order-Nummer eines Belegs – für alle Zeilen, die an einem Beleg hängen.
_VOUCHER = ("SELECT o.object_id FROM vouchers v JOIN orders o ON o.id = v.order_id "
            "WHERE v.id = ($1->>'voucher_id')::bigint")

#: ►► **An welchem Ding hängt eine Zeile** – eine Abfrage je Tabelle, ``$1`` ist die Zeile
#:    als ``jsonb``. ``None``: die Zeile hängt an keinem Ding (der Datei-Korb).
#:    Jede Tabelle steht hier oder in ``EXEMPT`` – sonst startet der Dienst nicht
#:    (``triggers_sql``), und ein Wächter sagt es vorher (``tests/test_log.py``).
OBJECT: dict[str, str | None] = {
    "addresses": _via("owner_id", "user_profiles"),
    "article_process_steps": _via("article_id", "articles"),
    "articles": _own("object_id"),
    "attachments": None,
    "captures": _via("order_id", "orders"),
    "company_settings": _own("object_id"),
    "company_territories": _via("company_id", "company_settings"),
    "document_links": _via("document_id", "documents"),
    "document_refs": _via("document_id", "documents"),
    "document_signatures": _via("document_id", "documents"),
    "documents": _own("object_id"),
    "feedback_notes": _own("target_object_id"),
    "holidays": _own("company_object_id"),
    "instance_units": _via("instance_id", "instances"),
    "instances": _own("object_id"),
    "mailboxes": _own("owner_object_id"),
    "message_parties": _own("person_object_id"),
    "messages": _own("sender_object_id"),
    "newsletter_consents": _own("person_object_id"),
    "objects": _own("object_id"),
    "order_lines": _via("order_id", "orders"),
    "order_units": _via("order_id", "orders"),
    "orders": _own("object_id"),
    "process_steps": _via("order_id", "orders"),
    "time_contracts": _own("person_object_id"),
    "time_entries": _own("person_object_id"),
    "user_profiles": _own("object_id"),
    "voucher_documents": _VOUCHER,
    "voucher_entries": _VOUCHER,
    "voucher_lines": _VOUCHER,
    "voucher_quotes": _VOUCHER,
    "vouchers": _via("order_id", "orders"),
    "webauthn_challenges": _via("user_id", "user_profiles"),
    "webauthn_credentials": _via("user_id", "user_profiles"),
}

ROW_TRIGGER = "trg_log_row"
IMMUTABLE_TRIGGER = "trg_log_immutable"
IMMUTABLE_TRUNCATE = "trg_log_no_truncate"
#: Ab dieser Länge (Zeichen) steht ein Wert im Log als Prüfsumme ``{"sha256", "len"}`` statt als
#: Inhalt – er liegt unveränderlich in seiner Zeile; doppelt wüchse das Log mit jeder Mail.
LONG_VALUE = 2000
#: Der Siegel-Lauf: einer zur Zeit, die anderen gehen weiter, statt zu warten.
SEAL_LOCK = 778_899_003


def missing(tables: list[str]) -> list[str]:
    """Tabellen, die weder ``OBJECT`` noch ``EXEMPT`` kennt."""
    return sorted(t for t in tables if t not in OBJECT and t not in EXEMPT)


def _literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


FUNCTIONS_SQL = r"""
CREATE OR REPLACE FUNCTION log_actor() RETURNS jsonb LANGUAGE plpgsql STABLE AS $fn$
DECLARE a text := current_setting('inexxio.actor', true);
BEGIN
  IF a IS NULL OR a = '' THEN
    RAISE EXCEPTION 'Log: niemand handelt – jede Änderung braucht einen Handelnden '
      '(services/log.act).' USING ERRCODE = 'insufficient_privilege';
  END IF;
  RETURN a::jsonb;
END;
$fn$;

CREATE OR REPLACE FUNCTION log_shorten(v jsonb) RETURNS jsonb LANGUAGE sql IMMUTABLE AS $fn$
  SELECT CASE
    WHEN v IS NULL OR jsonb_typeof(v) = 'null' THEN v
    WHEN jsonb_typeof(v) = 'string' AND length(v #>> '{}') > __LONG__ THEN
      jsonb_build_object('sha256', encode(sha256(convert_to(v #>> '{}', 'UTF8')), 'hex'),
                         'len', length(v #>> '{}'))
    WHEN jsonb_typeof(v) IN ('object', 'array') AND length(v::text) > __LONG__ THEN
      jsonb_build_object('sha256', encode(sha256(convert_to(v::text, 'UTF8')), 'hex'),
                         'len', length(v::text))
    ELSE v
  END;
$fn$;

CREATE OR REPLACE FUNCTION log_row() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
  a jsonb := log_actor();
  r jsonb;
  o jsonb;
  ch jsonb;
  act text;
  oid bigint;
  k text;
  secrets text[] := TG_ARGV[1]::text[];
BEGIN
  IF TG_OP = 'DELETE' THEN
    r := to_jsonb(OLD); act := 'delete'; ch := r - 'updated_at';
  ELSIF TG_OP = 'INSERT' THEN
    r := to_jsonb(NEW); act := 'insert'; ch := r - 'updated_at';
  ELSE
    r := to_jsonb(NEW); o := to_jsonb(OLD);
    SELECT jsonb_object_agg(e.key, jsonb_build_array(o -> e.key, e.value)) INTO ch
      FROM jsonb_each(r) e
     WHERE e.key <> 'updated_at' AND (o -> e.key) IS DISTINCT FROM e.value;
    IF ch IS NULL THEN
      RETURN NULL;                                  -- nur der Zeitstempel: keine Handlung
    END IF;
    act := CASE WHEN (o ->> 'is_active') = 'true' AND (r ->> 'is_active') = 'false'
                THEN 'delete' ELSE 'update' END;
  END IF;
  IF secrets IS NOT NULL THEN
    FOREACH k IN ARRAY secrets LOOP
      IF ch ? k THEN
        ch := jsonb_set(ch, ARRAY[k], CASE WHEN TG_OP = 'UPDATE'
                                           THEN '["[geheim]", "[geheim]"]'::jsonb
                                           ELSE '"[geheim]"'::jsonb END);
      END IF;
    END LOOP;
  END IF;
  -- Ein langer Wert (Mail-HTML, Dokumenttext …) steht nur als Prüfsumme da: er liegt schon
  -- unveränderlich in seiner Zeile, und doppelt gespeichert wüchse das Log mit jeder Mail.
  SELECT jsonb_object_agg(e.key, CASE WHEN TG_OP = 'UPDATE'
                                      THEN jsonb_build_array(log_shorten(e.value -> 0),
                                                             log_shorten(e.value -> 1))
                                      ELSE log_shorten(e.value) END)
    INTO ch FROM jsonb_each(ch) e;
  IF TG_ARGV[0] <> '' THEN
    EXECUTE TG_ARGV[0] INTO oid USING r;
  END IF;
  INSERT INTO log (actor_kind, actor_id, source, request_id, object_id, table_name, row_key,
                   action, changes)
  VALUES (a ->> 'kind', (a ->> 'id')::bigint, a ->> 'source', (a ->> 'request')::uuid, oid,
          TG_TABLE_NAME, coalesce(r ->> 'id', r ->> 'object_id'), act, ch);
  RETURN NULL;
END;
$fn$;

CREATE OR REPLACE FUNCTION log_event(p_event text, p_object bigint, p_payload jsonb,
                                     p_table text DEFAULT NULL, p_row text DEFAULT NULL,
                                     p_kind text DEFAULT NULL, p_actor bigint DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $fn$
DECLARE
  a jsonb := log_actor();
  new_id bigint;
BEGIN
  INSERT INTO log (actor_kind, actor_id, source, request_id, object_id, table_name, row_key,
                   action, event, payload)
  VALUES (coalesce(p_kind, a ->> 'kind'),
          CASE WHEN p_kind IS NULL THEN (a ->> 'id')::bigint ELSE p_actor END,
          a ->> 'source', (a ->> 'request')::uuid, p_object, p_table, p_row, 'event', p_event,
          p_payload)
  RETURNING id INTO new_id;
  RETURN new_id;
END;
$fn$;

CREATE OR REPLACE FUNCTION log_process(p_rows jsonb) RETURNS void
LANGUAGE plpgsql AS $fn$
DECLARE
  r record;
  body jsonb;
BEGIN
  FOR r IN SELECT e.v, o.object_id AS order_no, u.object_id AS actor_no
             FROM jsonb_array_elements(p_rows) WITH ORDINALITY AS e(v, n)
             LEFT JOIN orders o ON o.id = (e.v ->> 'order_id')::bigint
             LEFT JOIN user_profiles u ON u.id = (e.v ->> 'actor_id')::bigint
            ORDER BY e.n LOOP
    IF r.order_no IS NULL THEN
      RAISE EXCEPTION 'Log: Prozess-Ereignis ohne Auftrag (%) – es gäbe keine Spur.',
        r.v ->> 'order_id' USING ERRCODE = 'foreign_key_violation';
    END IF;
    body := jsonb_build_object('order', (r.v ->> 'order_id')::bigint,
                               'unit', (r.v ->> 'instance_unit_id')::bigint,
                               'before', r.v ->> 'status_before',
                               'after', r.v ->> 'status_after');
    IF (r.v ->> 'step_id') IS NOT NULL THEN
      body := body || jsonb_build_object('step', (r.v ->> 'step_id')::bigint);
    END IF;
    IF jsonb_typeof(r.v -> 'payload') = 'object' THEN
      body := body || jsonb_build_object('data', r.v -> 'payload');
    END IF;
    PERFORM log_event('process.' || (r.v ->> 'kind'), r.order_no, body, 'instance_units',
                      r.v ->> 'instance_unit_id',
                      CASE WHEN r.actor_no IS NULL THEN 'system' ELSE 'person' END,
                      r.actor_no);
  END LOOP;
END;
$fn$;

CREATE OR REPLACE FUNCTION log_immutable() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
  IF TG_TABLE_NAME = 'log' AND TG_OP = 'UPDATE'
     AND current_setting('inexxio.redacting', true) = 'on' THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Log: % wird nie geändert oder gelöscht – eine Korrektur ist ein neuer '
    'Eintrag.', TG_TABLE_NAME USING ERRCODE = 'check_violation';
END;
$fn$;

CREATE OR REPLACE FUNCTION log_redact(p_object bigint, p_reason text) RETURNS bigint
LANGUAGE plpgsql AS $fn$
DECLARE
  n bigint;
  days jsonb;
BEGIN
  PERFORM log_actor();
  SELECT coalesce(jsonb_agg(DISTINCT (at AT TIME ZONE 'UTC')::date), '[]'::jsonb) INTO days
    FROM log WHERE object_id = p_object AND coalesce(event, '') NOT LIKE 'process.%'
     AND event IS DISTINCT FROM 'log.redacted';
  PERFORM set_config('inexxio.redacting', 'on', true);
  UPDATE log
     SET changes = CASE WHEN changes IS NULL THEN NULL ELSE '{"geschwärzt": true}'::jsonb END,
         payload = CASE WHEN payload IS NULL THEN NULL ELSE '{"geschwärzt": true}'::jsonb END
   WHERE object_id = p_object AND coalesce(event, '') NOT LIKE 'process.%'
     AND event IS DISTINCT FROM 'log.redacted';
  GET DIAGNOSTICS n = ROW_COUNT;
  PERFORM set_config('inexxio.redacting', 'off', true);
  PERFORM log_event('log.redacted', p_object,
                    jsonb_build_object('entries', n, 'days', days, 'reason', p_reason));
  RETURN n;
END;
$fn$;

CREATE OR REPLACE FUNCTION log_digest(p_day date) RETURNS TABLE(n bigint, first_id bigint,
                                                               last_id bigint, digest text)
LANGUAGE sql STABLE AS $fn$
  SELECT count(*), min(id), max(id),
         encode(sha256(convert_to(coalesce(string_agg(jsonb_build_array(id,
           (extract(epoch FROM at) * 1000000)::bigint, actor_kind, actor_id, source,
           request_id, object_id, table_name, row_key, action, event, changes,
           payload)::text, E'\n' ORDER BY id), ''), 'UTF8')), 'hex')
    FROM log
   WHERE at >= p_day::timestamp AT TIME ZONE 'UTC'
     AND at < (p_day + 1)::timestamp AT TIME ZONE 'UTC';
$fn$;

CREATE OR REPLACE FUNCTION log_seal_due() RETURNS integer LANGUAGE plpgsql AS $fn$
DECLARE
  last_day date;
  upto date := ((now() AT TIME ZONE 'UTC') - interval '6 hours')::date - 1;
  d date;
  prev text;
  rec record;
  done integer := 0;
BEGIN
  IF NOT pg_try_advisory_xact_lock(__SEAL_LOCK__) THEN
    RETURN 0;
  END IF;
  SELECT day, hash INTO last_day, prev FROM log_seal ORDER BY day DESC LIMIT 1;
  IF last_day IS NULL THEN
    SELECT (min(at) AT TIME ZONE 'UTC')::date - 1 INTO last_day FROM log;
    IF last_day IS NULL THEN
      RETURN 0;
    END IF;
    prev := '';
  END IF;
  d := last_day + 1;
  WHILE d <= upto LOOP
    SELECT * INTO rec FROM log_digest(d);
    prev := encode(sha256(convert_to(prev || rec.digest, 'UTF8')), 'hex');
    INSERT INTO log_seal (day, first_id, last_id, entries, hash)
    VALUES (d, rec.first_id, rec.last_id, rec.n, prev);
    done := done + 1;
    d := d + 1;
  END LOOP;
  RETURN done;
END;
$fn$;

CREATE OR REPLACE FUNCTION log_verify() RETURNS TABLE(day date, ok boolean, redacted boolean)
LANGUAGE plpgsql STABLE AS $fn$
DECLARE
  s record;
  prev text := '';
  rec record;
BEGIN
  FOR s IN SELECT * FROM log_seal ORDER BY log_seal.day LOOP
    SELECT * INTO rec FROM log_digest(s.day);
    day := s.day;
    ok := encode(sha256(convert_to(prev || rec.digest, 'UTF8')), 'hex') = s.hash;
    redacted := EXISTS (SELECT 1 FROM log l WHERE l.event = 'log.redacted'
                         AND l.payload -> 'days' ? s.day::text);
    prev := s.hash;
    RETURN NEXT;
  END LOOP;
END;
$fn$;
""".replace("__SEAL_LOCK__", str(SEAL_LOCK)).replace("__LONG__", str(LONG_VALUE))


def _immutable_sql(table: str) -> str:
    return f"""
DROP TRIGGER IF EXISTS {IMMUTABLE_TRIGGER} ON {table};
CREATE TRIGGER {IMMUTABLE_TRIGGER} BEFORE UPDATE OR DELETE ON {table}
  FOR EACH ROW EXECUTE FUNCTION log_immutable();
DROP TRIGGER IF EXISTS {IMMUTABLE_TRUNCATE} ON {table};
CREATE TRIGGER {IMMUTABLE_TRUNCATE} BEFORE TRUNCATE ON {table}
  FOR EACH STATEMENT EXECUTE FUNCTION log_immutable();
"""


def triggers_sql(secrets: dict[str, list[str]]) -> str:
    """Funktionen + je Tabelle ihr Zeilen-Trigger. ``secrets``: jede Tabelle des Modells →
    die Spalten, die nie im Klartext ins Log gehen. Idempotent; eine Tabelle ohne Eintrag in
    ``OBJECT``/``EXEMPT`` hält den Start an (lieber kein Dienst als einer ohne Spur)."""
    gap = missing(list(secrets))
    if gap:
        raise RuntimeError(f"Log: an welchem Ding hängen {', '.join(gap)}? "
                           f"(domain/log.OBJECT)")
    parts = [FUNCTIONS_SQL, _immutable_sql("log"), _immutable_sql("log_seal")]
    for table in sorted(secrets):
        if table in EXEMPT:
            continue
        query = OBJECT[table] or ""
        hidden = "{" + ",".join(sorted(secrets[table])) + "}"
        parts.append(
            f"DROP TRIGGER IF EXISTS {ROW_TRIGGER} ON {table};\n"
            f"CREATE TRIGGER {ROW_TRIGGER} AFTER INSERT OR UPDATE OR DELETE ON {table}\n"
            f"  FOR EACH ROW EXECUTE FUNCTION log_row({_literal(query)}, {_literal(hidden)});")
    return "\n".join(parts)
