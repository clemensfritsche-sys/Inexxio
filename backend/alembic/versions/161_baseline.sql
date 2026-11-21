-- Das Schema auf dem Stand von Migration 161, eingefroren (pg_dump --schema-only).
-- Bis dahin standen hier 161 einzelne Migrationen; ihre Geschichte steht in git
-- (Rollback-Punkt vor dem Zusammenfassen: siehe docs/history/2026-10-28-dokumente.md).
-- Nie von Hand ändern – eine Änderung ist eine neue Migration.

CREATE FUNCTION public.instance_units_terminal_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
  BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status
       AND OLD.status = ANY (ARRAY['verschrottet']::text[]) THEN
      RAISE EXCEPTION
        'Einzelinstanz % steht auf «%» – das ist ein Endzustand. '
        'Ein Endzustand wird nicht überschrieben (Versuch: «%»).',
        OLD.id, OLD.status, NEW.status
        USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
  END;
  $$;

CREATE FUNCTION public.time_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN RAISE EXCEPTION 'Zeiterfassung: «%» wird nie geändert oder gelöscht – eine Korrektur ist ein neuer Eintrag.', TG_TABLE_NAME USING ERRCODE = 'check_violation'; END; $$;

CREATE TABLE public.addresses (
    id bigint NOT NULL,
    owner_id bigint NOT NULL,
    account character varying(10) DEFAULT 'private'::character varying NOT NULL,
    street1 character varying(255) DEFAULT ''::character varying NOT NULL,
    street2 character varying(255),
    zip character varying(20) DEFAULT ''::character varying NOT NULL,
    city character varying(100) DEFAULT ''::character varying NOT NULL,
    region character varying(100),
    country character varying(2) DEFAULT 'CH'::character varying NOT NULL,
    email character varying(255),
    is_default_delivery boolean DEFAULT false NOT NULL,
    is_default_billing boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE public.addresses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.addresses_id_seq OWNED BY public.addresses.id;

CREATE TABLE public.article_process_steps (
    id bigint NOT NULL,
    article_id bigint NOT NULL,
    "position" integer NOT NULL,
    module_type character varying(30) NOT NULL,
    status_before character varying(30) NOT NULL,
    status_after character varying(30) NOT NULL,
    config jsonb,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE public.article_process_steps_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.article_process_steps_id_seq OWNED BY public.article_process_steps.id;

CREATE TABLE public.articles (
    id bigint NOT NULL,
    object_id bigint,
    name character varying(255) NOT NULL,
    unit character varying(10) DEFAULT 'Stk'::character varying NOT NULL,
    serialization character varying(20) DEFAULT 'unit'::character varying NOT NULL,
    size character varying(100),
    weight_kg numeric(12,3),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    material character varying(255),
    cad_url character varying(500),
    surface character varying(255),
    min_order_qty numeric(12,3),
    safety_stock numeric(12,3),
    supplier_article_number character varying(255),
    is_hazmat boolean DEFAULT false NOT NULL,
    process_version integer DEFAULT 0 NOT NULL,
    replaced_by_id bigint,
    hs_code character varying(12),
    origin_country character varying(2),
    is_service boolean DEFAULT false NOT NULL
);

CREATE SEQUENCE public.articles_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.articles_id_seq OWNED BY public.articles.id;

CREATE TABLE public.attachments (
    id bigint NOT NULL,
    token character varying(64) NOT NULL,
    mime character varying(100) DEFAULT 'image/jpeg'::character varying NOT NULL,
    data bytea,
    filename character varying(255),
    width integer,
    height integer,
    byte_size integer,
    created_by bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE public.attachments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.attachments_id_seq OWNED BY public.attachments.id;

CREATE TABLE public.audit_log (
    id bigint NOT NULL,
    object_id bigint,
    table_name character varying(100) NOT NULL,
    field_name character varying(100),
    old_value text,
    new_value text,
    user_id bigint,
    changed_at_utc timestamp with time zone DEFAULT now() NOT NULL,
    on_behalf character varying(12)
);

CREATE SEQUENCE public.audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;

CREATE TABLE public.captures (
    id bigint NOT NULL,
    instance_unit_id bigint NOT NULL,
    order_id bigint NOT NULL,
    step_id bigint NOT NULL,
    "values" jsonb NOT NULL,
    result character varying(10),
    captured_by bigint,
    note character varying(500),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE public.captures_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.captures_id_seq OWNED BY public.captures.id;

CREATE TABLE public.company_settings (
    id integer NOT NULL,
    company_name character varying(255) DEFAULT 'Inexxio AG'::character varying NOT NULL,
    legal_form character varying(50) DEFAULT 'AG'::character varying NOT NULL,
    street character varying(255),
    street_nr character varying(20),
    zip_code character varying(20),
    city character varying(100),
    country character varying(100) DEFAULT 'Schweiz'::character varying NOT NULL,
    uid_number character varying(30),
    vat_number character varying(30),
    iban_encrypted text,
    email character varying(255) DEFAULT 'info@inexxio.com'::character varying NOT NULL,
    phone character varying(50),
    object_id bigint,
    is_operator boolean DEFAULT false NOT NULL,
    currency character varying(3) DEFAULT 'CHF'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_own boolean DEFAULT false NOT NULL,
    uid_key character varying(20),
    name_key character varying(320),
    time_rules json
);

CREATE SEQUENCE public.company_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.company_settings_id_seq OWNED BY public.company_settings.id;

CREATE TABLE public.company_territories (
    id bigint NOT NULL,
    region character varying(10) NOT NULL,
    company_id integer NOT NULL
);

CREATE SEQUENCE public.company_territories_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.company_territories_id_seq OWNED BY public.company_territories.id;

CREATE TABLE public.document_links (
    id bigint NOT NULL,
    token character varying(64) NOT NULL,
    document_id bigint NOT NULL,
    person_object_id bigint,
    message_id bigint,
    created_by bigint,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean NOT NULL
);

CREATE SEQUENCE public.document_links_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.document_links_id_seq OWNED BY public.document_links.id;

CREATE TABLE public.document_refs (
    id bigint NOT NULL,
    document_id bigint NOT NULL,
    object_id bigint NOT NULL,
    part character varying(60),
    field character varying(40),
    created_by bigint,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean NOT NULL
);

CREATE SEQUENCE public.document_refs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.document_refs_id_seq OWNED BY public.document_refs.id;

CREATE TABLE public.document_signatures (
    id bigint NOT NULL,
    document_id bigint NOT NULL,
    person_object_id bigint NOT NULL,
    name character varying(200) NOT NULL,
    signed_at timestamp with time zone,
    declined_at timestamp with time zone,
    reason character varying(300),
    image bytea,
    sha256 character varying(64),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean NOT NULL
);

CREATE SEQUENCE public.document_signatures_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.document_signatures_id_seq OWNED BY public.document_signatures.id;

CREATE TABLE public.documents (
    id bigint NOT NULL,
    object_id bigint NOT NULL,
    art character varying(80) NOT NULL,
    name character varying(200) NOT NULL,
    source character varying(12) NOT NULL,
    file_id bigint,
    mime character varying(100) NOT NULL,
    filename character varying(255),
    byte_size integer NOT NULL,
    sha256 character varying(64),
    text text,
    keywords text,
    facts jsonb,
    created_by bigint,
    deleted_at timestamp with time zone,
    deleted_by bigint,
    delete_reason character varying(300),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean NOT NULL
);

CREATE SEQUENCE public.documents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.documents_id_seq OWNED BY public.documents.id;

CREATE TABLE public.feedback_notes (
    id bigint NOT NULL,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    body text NOT NULL,
    route character varying(500) DEFAULT ''::character varying NOT NULL,
    target_object_id bigint,
    anchor jsonb,
    context jsonb,
    resolution text,
    resolved_at timestamp with time zone,
    resolved_by bigint,
    created_by bigint,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE public.feedback_notes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.feedback_notes_id_seq OWNED BY public.feedback_notes.id;

CREATE TABLE public.holidays (
    id bigint NOT NULL,
    company_object_id bigint NOT NULL,
    day date NOT NULL,
    name character varying(120) NOT NULL,
    created_by bigint,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean NOT NULL
);

CREATE SEQUENCE public.holidays_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.holidays_id_seq OWNED BY public.holidays.id;

CREATE TABLE public.instance_units (
    id bigint NOT NULL,
    instance_id bigint NOT NULL,
    suffix integer NOT NULL,
    status character varying(30) DEFAULT 'freigegeben'::character varying NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    place_object_id bigint,
    place_unit_id bigint,
    CONSTRAINT ck_instance_units_one_place CHECK (((place_object_id IS NULL) OR (place_unit_id IS NULL)))
);

CREATE SEQUENCE public.instance_units_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.instance_units_id_seq OWNED BY public.instance_units.id;

CREATE TABLE public.instances (
    id bigint NOT NULL,
    object_id bigint NOT NULL,
    article_id bigint NOT NULL,
    kind character varying(10) NOT NULL,
    label character varying(120),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE public.instances_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.instances_id_seq OWNED BY public.instances.id;

CREATE TABLE public.mailboxes (
    id bigint NOT NULL,
    channel character varying(20) NOT NULL,
    address character varying(255) NOT NULL,
    owner_object_id bigint NOT NULL,
    token text NOT NULL,
    history_id character varying(32),
    problem text,
    synced_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    picture text
);

CREATE SEQUENCE public.mailboxes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.mailboxes_id_seq OWNED BY public.mailboxes.id;

CREATE TABLE public.message_parties (
    id bigint NOT NULL,
    message_id bigint NOT NULL,
    person_object_id bigint NOT NULL,
    role character varying(5) NOT NULL
);

CREATE SEQUENCE public.message_parties_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.message_parties_id_seq OWNED BY public.message_parties.id;

CREATE TABLE public.messages (
    id bigint NOT NULL,
    sender_object_id bigint NOT NULL,
    channel character varying(20) NOT NULL,
    subject character varying(255),
    body text DEFAULT ''::text NOT NULL,
    at timestamp with time zone NOT NULL,
    created_by bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    gmail_id character varying(64),
    thread_id character varying(64),
    rfc_id character varying(255),
    outgoing boolean DEFAULT false NOT NULL,
    attachments jsonb,
    html text,
    read_marked boolean DEFAULT false NOT NULL,
    group_id bigint,
    newsletter boolean DEFAULT false NOT NULL
);

CREATE SEQUENCE public.messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.messages_id_seq OWNED BY public.messages.id;

CREATE TABLE public.newsletter_consents (
    id bigint NOT NULL,
    person_object_id bigint NOT NULL,
    subscribed boolean NOT NULL,
    source character varying(20) NOT NULL,
    wording text,
    at timestamp with time zone NOT NULL,
    created_by bigint,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean NOT NULL
);

CREATE SEQUENCE public.newsletter_consents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.newsletter_consents_id_seq OWNED BY public.newsletter_consents.id;

CREATE SEQUENCE public.object_id_seq
    START WITH 100000001
    INCREMENT BY 1
    MINVALUE 100000001
    NO MAXVALUE
    CACHE 1;

CREATE TABLE public.objects (
    object_id bigint NOT NULL,
    object_type character varying(30) NOT NULL,
    created_at timestamp with time zone NOT NULL
);

CREATE TABLE public.order_lines (
    id bigint NOT NULL,
    order_id bigint NOT NULL,
    "position" integer NOT NULL,
    article_id bigint NOT NULL,
    quantity integer NOT NULL,
    origin character varying(10) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE public.order_lines_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.order_lines_id_seq OWNED BY public.order_lines.id;

CREATE TABLE public.order_units (
    id bigint NOT NULL,
    order_id bigint NOT NULL,
    instance_unit_id bigint NOT NULL,
    current_step_id bigint,
    released_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    return_to_order_id bigint
);

CREATE SEQUENCE public.order_units_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.order_units_id_seq OWNED BY public.order_units.id;

CREATE TABLE public.orders (
    id bigint NOT NULL,
    object_id bigint NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    end_status character varying(30) DEFAULT 'freigegeben'::character varying NOT NULL,
    name character varying(120) NOT NULL
);

CREATE SEQUENCE public.orders_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.orders_id_seq OWNED BY public.orders.id;

CREATE TABLE public.process_events (
    id bigint NOT NULL,
    order_id bigint NOT NULL,
    step_id bigint,
    instance_unit_id bigint NOT NULL,
    kind character varying(10) NOT NULL,
    status_before character varying(30) NOT NULL,
    status_after character varying(30) NOT NULL,
    payload jsonb,
    actor_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.process_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.process_events_id_seq OWNED BY public.process_events.id;

CREATE TABLE public.process_steps (
    id bigint NOT NULL,
    order_id bigint NOT NULL,
    "position" integer NOT NULL,
    module_type character varying(30) NOT NULL,
    status_before character varying(30) NOT NULL,
    status_after character varying(30) NOT NULL,
    config jsonb,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    source_article_id bigint,
    source_version integer
);

CREATE SEQUENCE public.process_steps_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.process_steps_id_seq OWNED BY public.process_steps.id;

CREATE TABLE public.time_contracts (
    id bigint NOT NULL,
    person_object_id bigint NOT NULL,
    valid_from date NOT NULL,
    weekly_minutes integer NOT NULL,
    workdays smallint NOT NULL,
    vacation_weeks numeric(4,1) NOT NULL,
    company_object_id bigint,
    created_by bigint,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean NOT NULL
);

CREATE SEQUENCE public.time_contracts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.time_contracts_id_seq OWNED BY public.time_contracts.id;

CREATE TABLE public.time_entries (
    id bigint NOT NULL,
    person_object_id bigint NOT NULL,
    kind character varying(10) NOT NULL,
    day date NOT NULL,
    at timestamp with time zone,
    until date,
    art character varying(20),
    minutes integer,
    vacation_minutes integer,
    note text,
    proof_url character varying(200),
    source character varying(10),
    replaces_id bigint,
    idem_key character varying(64),
    created_by bigint,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean NOT NULL
);

CREATE SEQUENCE public.time_entries_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.time_entries_id_seq OWNED BY public.time_entries.id;

CREATE TABLE public.user_profiles (
    id bigint NOT NULL,
    object_id bigint,
    firebase_uid character varying(128) NOT NULL,
    email character varying(255) NOT NULL,
    photo_url text,
    role character varying(20) DEFAULT 'customer'::character varying NOT NULL,
    first_name character varying(100),
    last_name character varying(100),
    phone character varying(50),
    date_of_birth date,
    department character varying(100),
    job_title character varying(100),
    language character varying(10) DEFAULT 'de'::character varying NOT NULL,
    notification_email boolean DEFAULT true NOT NULL,
    notification_inapp boolean DEFAULT true NOT NULL,
    last_login_at timestamp with time zone,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_sign_in_provider character varying(40),
    company_object_id bigint
);

CREATE SEQUENCE public.user_profiles_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.user_profiles_id_seq OWNED BY public.user_profiles.id;

CREATE TABLE public.voucher_documents (
    id bigint NOT NULL,
    voucher_id bigint NOT NULL,
    kind character varying(16) NOT NULL,
    level integer,
    number character varying(120),
    party_id bigint,
    token character varying(64) NOT NULL,
    agb character varying(10),
    message_id bigint,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_active boolean NOT NULL,
    document_id bigint
);

CREATE SEQUENCE public.voucher_documents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.voucher_documents_id_seq OWNED BY public.voucher_documents.id;

CREATE TABLE public.voucher_entries (
    id bigint NOT NULL,
    voucher_id bigint NOT NULL,
    amount numeric(18,4) NOT NULL,
    booked_on date,
    reference character varying(120),
    note character varying(200),
    method character varying(10),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    kind character varying(10) DEFAULT 'payment'::character varying NOT NULL,
    reason character varying(20),
    reverses_id bigint,
    iban character varying(34)
);

CREATE SEQUENCE public.voucher_entries_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.voucher_entries_id_seq OWNED BY public.voucher_entries.id;

CREATE TABLE public.voucher_lines (
    id bigint NOT NULL,
    voucher_id bigint NOT NULL,
    article_id bigint,
    quantity integer DEFAULT 1 NOT NULL,
    price numeric(18,4),
    vat character varying(16) DEFAULT 'normal'::character varying NOT NULL,
    hs_code character varying(12),
    origin_country character varying(60),
    "position" integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    text character varying(300),
    part numeric(18,4),
    weight_kg numeric(12,3)
);

CREATE SEQUENCE public.voucher_lines_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.voucher_lines_id_seq OWNED BY public.voucher_lines.id;

CREATE TABLE public.voucher_quotes (
    id bigint NOT NULL,
    voucher_id bigint NOT NULL,
    party_id bigint NOT NULL,
    state character varying(16) DEFAULT 'angefragt'::character varying NOT NULL,
    amount numeric(18,4),
    lead_days integer,
    payment_days integer,
    sent_on date,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    reference character varying(120),
    link character varying(500)
);

CREATE SEQUENCE public.voucher_quotes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.voucher_quotes_id_seq OWNED BY public.voucher_quotes.id;

CREATE TABLE public.vouchers (
    id bigint NOT NULL,
    order_id bigint NOT NULL,
    step_id bigint NOT NULL,
    direction character varying(8) DEFAULT 'out'::character varying NOT NULL,
    currency character varying(3) DEFAULT 'CHF'::character varying NOT NULL,
    issuer_company_id bigint,
    stage character varying(16) DEFAULT 'offer'::character varying NOT NULL,
    agreed_on date,
    cancelled_on date,
    incoterm character varying(3),
    incoterm_place character varying(120),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    lead_days integer,
    payment_days integer,
    parties jsonb DEFAULT '[]'::jsonb NOT NULL,
    billed_on date,
    due_on date,
    number character varying(120),
    amount numeric(18,4),
    vat jsonb,
    service_date date,
    corrects_id bigint,
    bill_to_company boolean,
    billing_address_id bigint,
    delivery_address_id bigint,
    head jsonb,
    valid_days integer,
    ownership character varying(8),
    unit_ids jsonb,
    offered_hash character varying(64),
    cancel_note character varying(200),
    credit_number character varying(120),
    party_uid character varying(40),
    original_id bigint,
    deviation_note character varying(200),
    export_number character varying(60),
    export_photo_id bigint
);

CREATE SEQUENCE public.vouchers_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.vouchers_id_seq OWNED BY public.vouchers.id;

CREATE TABLE public.webauthn_challenges (
    id bigint NOT NULL,
    challenge character varying(255) NOT NULL,
    purpose character varying(16) NOT NULL,
    user_id bigint,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE public.webauthn_challenges_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.webauthn_challenges_id_seq OWNED BY public.webauthn_challenges.id;

CREATE TABLE public.webauthn_credentials (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    credential_id character varying(512) NOT NULL,
    public_key bytea NOT NULL,
    sign_count bigint DEFAULT 0 NOT NULL,
    rp_id character varying(255) NOT NULL,
    transports jsonb,
    device_name character varying(80),
    device_type character varying(20),
    backed_up boolean DEFAULT false NOT NULL,
    last_used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

CREATE SEQUENCE public.webauthn_credentials_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.webauthn_credentials_id_seq OWNED BY public.webauthn_credentials.id;

ALTER TABLE ONLY public.addresses ALTER COLUMN id SET DEFAULT nextval('public.addresses_id_seq'::regclass);

ALTER TABLE ONLY public.article_process_steps ALTER COLUMN id SET DEFAULT nextval('public.article_process_steps_id_seq'::regclass);

ALTER TABLE ONLY public.articles ALTER COLUMN id SET DEFAULT nextval('public.articles_id_seq'::regclass);

ALTER TABLE ONLY public.attachments ALTER COLUMN id SET DEFAULT nextval('public.attachments_id_seq'::regclass);

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);

ALTER TABLE ONLY public.captures ALTER COLUMN id SET DEFAULT nextval('public.captures_id_seq'::regclass);

ALTER TABLE ONLY public.company_settings ALTER COLUMN id SET DEFAULT nextval('public.company_settings_id_seq'::regclass);

ALTER TABLE ONLY public.company_territories ALTER COLUMN id SET DEFAULT nextval('public.company_territories_id_seq'::regclass);

ALTER TABLE ONLY public.document_links ALTER COLUMN id SET DEFAULT nextval('public.document_links_id_seq'::regclass);

ALTER TABLE ONLY public.document_refs ALTER COLUMN id SET DEFAULT nextval('public.document_refs_id_seq'::regclass);

ALTER TABLE ONLY public.document_signatures ALTER COLUMN id SET DEFAULT nextval('public.document_signatures_id_seq'::regclass);

ALTER TABLE ONLY public.documents ALTER COLUMN id SET DEFAULT nextval('public.documents_id_seq'::regclass);

ALTER TABLE ONLY public.feedback_notes ALTER COLUMN id SET DEFAULT nextval('public.feedback_notes_id_seq'::regclass);

ALTER TABLE ONLY public.holidays ALTER COLUMN id SET DEFAULT nextval('public.holidays_id_seq'::regclass);

ALTER TABLE ONLY public.instance_units ALTER COLUMN id SET DEFAULT nextval('public.instance_units_id_seq'::regclass);

ALTER TABLE ONLY public.instances ALTER COLUMN id SET DEFAULT nextval('public.instances_id_seq'::regclass);

ALTER TABLE ONLY public.mailboxes ALTER COLUMN id SET DEFAULT nextval('public.mailboxes_id_seq'::regclass);

ALTER TABLE ONLY public.message_parties ALTER COLUMN id SET DEFAULT nextval('public.message_parties_id_seq'::regclass);

ALTER TABLE ONLY public.messages ALTER COLUMN id SET DEFAULT nextval('public.messages_id_seq'::regclass);

ALTER TABLE ONLY public.newsletter_consents ALTER COLUMN id SET DEFAULT nextval('public.newsletter_consents_id_seq'::regclass);

ALTER TABLE ONLY public.order_lines ALTER COLUMN id SET DEFAULT nextval('public.order_lines_id_seq'::regclass);

ALTER TABLE ONLY public.order_units ALTER COLUMN id SET DEFAULT nextval('public.order_units_id_seq'::regclass);

ALTER TABLE ONLY public.orders ALTER COLUMN id SET DEFAULT nextval('public.orders_id_seq'::regclass);

ALTER TABLE ONLY public.process_events ALTER COLUMN id SET DEFAULT nextval('public.process_events_id_seq'::regclass);

ALTER TABLE ONLY public.process_steps ALTER COLUMN id SET DEFAULT nextval('public.process_steps_id_seq'::regclass);

ALTER TABLE ONLY public.time_contracts ALTER COLUMN id SET DEFAULT nextval('public.time_contracts_id_seq'::regclass);

ALTER TABLE ONLY public.time_entries ALTER COLUMN id SET DEFAULT nextval('public.time_entries_id_seq'::regclass);

ALTER TABLE ONLY public.user_profiles ALTER COLUMN id SET DEFAULT nextval('public.user_profiles_id_seq'::regclass);

ALTER TABLE ONLY public.voucher_documents ALTER COLUMN id SET DEFAULT nextval('public.voucher_documents_id_seq'::regclass);

ALTER TABLE ONLY public.voucher_entries ALTER COLUMN id SET DEFAULT nextval('public.voucher_entries_id_seq'::regclass);

ALTER TABLE ONLY public.voucher_lines ALTER COLUMN id SET DEFAULT nextval('public.voucher_lines_id_seq'::regclass);

ALTER TABLE ONLY public.voucher_quotes ALTER COLUMN id SET DEFAULT nextval('public.voucher_quotes_id_seq'::regclass);

ALTER TABLE ONLY public.vouchers ALTER COLUMN id SET DEFAULT nextval('public.vouchers_id_seq'::regclass);

ALTER TABLE ONLY public.webauthn_challenges ALTER COLUMN id SET DEFAULT nextval('public.webauthn_challenges_id_seq'::regclass);

ALTER TABLE ONLY public.webauthn_credentials ALTER COLUMN id SET DEFAULT nextval('public.webauthn_credentials_id_seq'::regclass);

ALTER TABLE ONLY public.addresses
    ADD CONSTRAINT addresses_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.article_process_steps
    ADD CONSTRAINT article_process_steps_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT articles_object_id_key UNIQUE (object_id);

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT articles_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT attachments_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.captures
    ADD CONSTRAINT captures_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.company_settings
    ADD CONSTRAINT company_settings_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.company_territories
    ADD CONSTRAINT company_territories_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.document_links
    ADD CONSTRAINT document_links_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.document_links
    ADD CONSTRAINT document_links_token_key UNIQUE (token);

ALTER TABLE ONLY public.document_refs
    ADD CONSTRAINT document_refs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.document_signatures
    ADD CONSTRAINT document_signatures_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.feedback_notes
    ADD CONSTRAINT feedback_notes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.holidays
    ADD CONSTRAINT holidays_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.instance_units
    ADD CONSTRAINT instance_units_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.instances
    ADD CONSTRAINT instances_object_id_key UNIQUE (object_id);

ALTER TABLE ONLY public.instances
    ADD CONSTRAINT instances_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.mailboxes
    ADD CONSTRAINT mailboxes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.message_parties
    ADD CONSTRAINT message_parties_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.newsletter_consents
    ADD CONSTRAINT newsletter_consents_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.objects
    ADD CONSTRAINT objects_pkey PRIMARY KEY (object_id);

ALTER TABLE ONLY public.order_lines
    ADD CONSTRAINT order_lines_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.order_units
    ADD CONSTRAINT order_units_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_object_id_key UNIQUE (object_id);

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.process_events
    ADD CONSTRAINT process_events_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.process_steps
    ADD CONSTRAINT process_steps_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.time_contracts
    ADD CONSTRAINT time_contracts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.time_entries
    ADD CONSTRAINT time_entries_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.instance_units
    ADD CONSTRAINT uq_instance_units_instance_suffix UNIQUE (instance_id, suffix);

ALTER TABLE ONLY public.webauthn_challenges
    ADD CONSTRAINT uq_webauthn_challenges_challenge UNIQUE (challenge);

ALTER TABLE ONLY public.webauthn_credentials
    ADD CONSTRAINT uq_webauthn_credentials_credential_id UNIQUE (credential_id);

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_email_key UNIQUE (email);

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_firebase_uid_key UNIQUE (firebase_uid);

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_object_id_key UNIQUE (object_id);

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.voucher_documents
    ADD CONSTRAINT voucher_documents_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.voucher_documents
    ADD CONSTRAINT voucher_documents_token_key UNIQUE (token);

ALTER TABLE ONLY public.voucher_entries
    ADD CONSTRAINT voucher_entries_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.voucher_lines
    ADD CONSTRAINT voucher_lines_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.voucher_quotes
    ADD CONSTRAINT voucher_quotes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.vouchers
    ADD CONSTRAINT vouchers_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.webauthn_challenges
    ADD CONSTRAINT webauthn_challenges_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.webauthn_credentials
    ADD CONSTRAINT webauthn_credentials_pkey PRIMARY KEY (id);

CREATE INDEX ix_addresses_owner_id ON public.addresses USING btree (owner_id);

CREATE INDEX ix_article_process_steps_article_id ON public.article_process_steps USING btree (article_id);

CREATE INDEX ix_articles_object_id ON public.articles USING btree (object_id);

CREATE INDEX ix_articles_replaced_by_id ON public.articles USING btree (replaced_by_id);

CREATE UNIQUE INDEX ix_attachments_token ON public.attachments USING btree (token);

CREATE INDEX ix_audit_log_object_id ON public.audit_log USING btree (object_id);

CREATE INDEX ix_audit_log_table_name ON public.audit_log USING btree (table_name);

CREATE INDEX ix_captures_instance_unit_id ON public.captures USING btree (instance_unit_id);

CREATE INDEX ix_captures_order_id ON public.captures USING btree (order_id);

CREATE INDEX ix_captures_step_id ON public.captures USING btree (step_id);

CREATE UNIQUE INDEX ix_company_settings_object_id ON public.company_settings USING btree (object_id);

CREATE INDEX ix_company_territories_company_id ON public.company_territories USING btree (company_id);

CREATE INDEX ix_document_links_document_id ON public.document_links USING btree (document_id);

CREATE INDEX ix_document_refs_document_id ON public.document_refs USING btree (document_id);

CREATE INDEX ix_document_refs_object_id ON public.document_refs USING btree (object_id);

CREATE INDEX ix_document_signatures_document_id ON public.document_signatures USING btree (document_id);

CREATE UNIQUE INDEX ix_documents_object_id ON public.documents USING btree (object_id);

CREATE INDEX ix_feedback_notes_created_by ON public.feedback_notes USING btree (created_by);

CREATE INDEX ix_feedback_notes_route ON public.feedback_notes USING btree (route);

CREATE INDEX ix_feedback_notes_status ON public.feedback_notes USING btree (status);

CREATE INDEX ix_feedback_notes_target_object_id ON public.feedback_notes USING btree (target_object_id);

CREATE INDEX ix_instance_units_instance_id ON public.instance_units USING btree (instance_id);

CREATE INDEX ix_instance_units_instance_status ON public.instance_units USING btree (instance_id, status, id);

CREATE INDEX ix_instance_units_place ON public.instance_units USING btree (place_object_id);

CREATE INDEX ix_instance_units_place_unit ON public.instance_units USING btree (place_unit_id);

CREATE INDEX ix_instances_article_id ON public.instances USING btree (article_id);

CREATE INDEX ix_instances_object_id ON public.instances USING btree (object_id);

CREATE INDEX ix_message_parties_message_id ON public.message_parties USING btree (message_id);

CREATE INDEX ix_message_parties_person_object_id ON public.message_parties USING btree (person_object_id);

CREATE INDEX ix_messages_at ON public.messages USING btree (at);

CREATE INDEX ix_messages_group_id ON public.messages USING btree (group_id);

CREATE INDEX ix_messages_sender_object_id ON public.messages USING btree (sender_object_id);

CREATE INDEX ix_newsletter_consents_person_object_id ON public.newsletter_consents USING btree (person_object_id);

CREATE INDEX ix_objects_object_type ON public.objects USING btree (object_type);

CREATE INDEX ix_order_lines_article_id ON public.order_lines USING btree (article_id);

CREATE INDEX ix_order_lines_order_id ON public.order_lines USING btree (order_id);

CREATE INDEX ix_order_units_instance_unit_id ON public.order_units USING btree (instance_unit_id);

CREATE INDEX ix_order_units_order_id ON public.order_units USING btree (order_id);

CREATE INDEX ix_order_units_return_to_order_id ON public.order_units USING btree (return_to_order_id);

CREATE INDEX ix_orders_object_id ON public.orders USING btree (object_id);

CREATE INDEX ix_process_events_order_id ON public.process_events USING btree (order_id);

CREATE INDEX ix_process_events_unit ON public.process_events USING btree (instance_unit_id);

CREATE INDEX ix_process_events_unit_timeline ON public.process_events USING btree (instance_unit_id, id);

CREATE INDEX ix_process_steps_order_id ON public.process_steps USING btree (order_id);

CREATE INDEX ix_time_contracts_person_object_id ON public.time_contracts USING btree (person_object_id);

CREATE INDEX ix_time_entries_person_day ON public.time_entries USING btree (person_object_id, day);

CREATE INDEX ix_user_profiles_email ON public.user_profiles USING btree (email);

CREATE INDEX ix_user_profiles_firebase_uid ON public.user_profiles USING btree (firebase_uid);

CREATE INDEX ix_user_profiles_object_id ON public.user_profiles USING btree (object_id);

CREATE INDEX ix_voucher_documents_document_id ON public.voucher_documents USING btree (document_id);

CREATE INDEX ix_voucher_documents_party_id ON public.voucher_documents USING btree (party_id);

CREATE INDEX ix_voucher_documents_voucher_id ON public.voucher_documents USING btree (voucher_id);

CREATE INDEX ix_voucher_entries_voucher_id ON public.voucher_entries USING btree (voucher_id);

CREATE INDEX ix_voucher_lines_article_id ON public.voucher_lines USING btree (article_id);

CREATE INDEX ix_voucher_lines_voucher_id ON public.voucher_lines USING btree (voucher_id);

CREATE INDEX ix_voucher_quotes_party_id ON public.voucher_quotes USING btree (party_id);

CREATE INDEX ix_voucher_quotes_voucher_id ON public.voucher_quotes USING btree (voucher_id);

CREATE INDEX ix_vouchers_corrects_id ON public.vouchers USING btree (corrects_id);

CREATE INDEX ix_vouchers_order_id ON public.vouchers USING btree (order_id);

CREATE INDEX ix_vouchers_step_id ON public.vouchers USING btree (step_id);

CREATE INDEX ix_webauthn_challenges_challenge ON public.webauthn_challenges USING btree (challenge);

CREATE INDEX ix_webauthn_credentials_credential_id ON public.webauthn_credentials USING btree (credential_id);

CREATE INDEX ix_webauthn_credentials_user_id ON public.webauthn_credentials USING btree (user_id);

CREATE UNIQUE INDEX uq_addresses_default_billing_account ON public.addresses USING btree (owner_id, account) WHERE (is_active AND is_default_billing);

CREATE UNIQUE INDEX uq_addresses_default_delivery_account ON public.addresses USING btree (owner_id, account) WHERE (is_active AND is_default_delivery);

CREATE UNIQUE INDEX uq_company_settings_name_key ON public.company_settings USING btree (name_key) WHERE (is_active AND (uid_key IS NULL) AND (name_key IS NOT NULL));

CREATE UNIQUE INDEX uq_company_settings_operator ON public.company_settings USING btree (is_operator) WHERE is_operator;

CREATE UNIQUE INDEX uq_company_settings_uid_key ON public.company_settings USING btree (uid_key) WHERE (is_active AND (uid_key IS NOT NULL));

CREATE UNIQUE INDEX uq_company_territories_region ON public.company_territories USING btree (region);

CREATE UNIQUE INDEX uq_documents_sha256 ON public.documents USING btree (sha256) WHERE ((deleted_at IS NULL) AND (sha256 IS NOT NULL));

CREATE UNIQUE INDEX uq_holidays_company_day ON public.holidays USING btree (company_object_id, day) WHERE is_active;

CREATE UNIQUE INDEX uq_mailboxes_channel ON public.mailboxes USING btree (channel) WHERE is_active;

CREATE UNIQUE INDEX uq_messages_gmail ON public.messages USING btree (channel, gmail_id) WHERE (gmail_id IS NOT NULL);

CREATE UNIQUE INDEX uq_messages_rfc_id ON public.messages USING btree (rfc_id) WHERE (rfc_id IS NOT NULL);

CREATE UNIQUE INDEX uq_order_units_active ON public.order_units USING btree (instance_unit_id) WHERE (released_at IS NULL);

CREATE UNIQUE INDEX uq_time_contracts_person_from ON public.time_contracts USING btree (person_object_id, valid_from);

CREATE UNIQUE INDEX uq_time_entries_key ON public.time_entries USING btree (idem_key) WHERE (idem_key IS NOT NULL);

CREATE UNIQUE INDEX uq_time_entries_replaces ON public.time_entries USING btree (replaces_id) WHERE (replaces_id IS NOT NULL);

CREATE UNIQUE INDEX uq_voucher_entries_reference ON public.voucher_entries USING btree (reference) WHERE (is_active AND (reference IS NOT NULL));

CREATE UNIQUE INDEX uq_voucher_lines_article ON public.voucher_lines USING btree (voucher_id, article_id) WHERE is_active;

CREATE UNIQUE INDEX uq_voucher_quotes_party ON public.voucher_quotes USING btree (voucher_id, party_id) WHERE is_active;

CREATE UNIQUE INDEX uq_vouchers_step ON public.vouchers USING btree (step_id) WHERE is_active;

CREATE TRIGGER trg_instance_units_terminal BEFORE UPDATE ON public.instance_units FOR EACH ROW EXECUTE FUNCTION public.instance_units_terminal_guard();

CREATE TRIGGER trg_time_contracts_append_only BEFORE DELETE OR UPDATE ON public.time_contracts FOR EACH ROW EXECUTE FUNCTION public.time_append_only();

CREATE TRIGGER trg_time_entries_append_only BEFORE DELETE OR UPDATE ON public.time_entries FOR EACH ROW EXECUTE FUNCTION public.time_append_only();

ALTER TABLE ONLY public.addresses
    ADD CONSTRAINT addresses_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.user_profiles(id);

ALTER TABLE ONLY public.document_links
    ADD CONSTRAINT document_links_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.document_refs
    ADD CONSTRAINT document_refs_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.document_signatures
    ADD CONSTRAINT document_signatures_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT fk_articles_replaced_by FOREIGN KEY (replaced_by_id) REFERENCES public.objects(object_id) ON DELETE SET NULL;

ALTER TABLE ONLY public.vouchers
    ADD CONSTRAINT fk_vouchers_corrects FOREIGN KEY (corrects_id) REFERENCES public.vouchers(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.message_parties
    ADD CONSTRAINT message_parties_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.messages(id);

ALTER TABLE ONLY public.time_entries
    ADD CONSTRAINT time_entries_replaces_id_fkey FOREIGN KEY (replaces_id) REFERENCES public.time_entries(id) ON DELETE RESTRICT;

ALTER TABLE ONLY public.voucher_documents
    ADD CONSTRAINT voucher_documents_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);

ALTER TABLE ONLY public.voucher_documents
    ADD CONSTRAINT voucher_documents_voucher_id_fkey FOREIGN KEY (voucher_id) REFERENCES public.vouchers(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.voucher_entries
    ADD CONSTRAINT voucher_entries_reverses_id_fkey FOREIGN KEY (reverses_id) REFERENCES public.voucher_entries(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.voucher_entries
    ADD CONSTRAINT voucher_entries_voucher_id_fkey FOREIGN KEY (voucher_id) REFERENCES public.vouchers(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.voucher_lines
    ADD CONSTRAINT voucher_lines_voucher_id_fkey FOREIGN KEY (voucher_id) REFERENCES public.vouchers(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.voucher_quotes
    ADD CONSTRAINT voucher_quotes_voucher_id_fkey FOREIGN KEY (voucher_id) REFERENCES public.vouchers(id) ON DELETE CASCADE;
