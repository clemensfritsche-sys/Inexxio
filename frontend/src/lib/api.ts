import type { components, paths } from '@/types/api';
import type { Article, UserProfile } from '@/types';
import type {
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
  RegistrationResponseJSON,
  AuthenticationResponseJSON,
} from '@simplewebauthn/browser';
import { DATA_CHANGED } from '@/lib/feed';

/** Ein Fehler der API – mit **Status** und dem rohen `detail`; `message` ist der lesbare Text. */
/** **Eine Abweisung des Servers** – überall dieselbe Form (`domain/errors`): der Satz
 *  (`message`), die Art oder ein eigener Code (`code`: `invalid` · `forbidden` · `not_found` ·
 *  `conflict` · … · `pick_stale`) und, wo es eines betrifft, das Feld. */
export class ApiError extends Error {
  status: number;
  code: string;
  field?: string;
  constructor(message: string, status: number, code = '', field?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** **«Gibt es das?» – 404 ist Nein, alles andere ein Fehler**, der weitergereicht wird
 *  (ein Ausfall ist nicht «nicht im ERP»). */
export function absentOn404(e: unknown): false {
  if (e instanceof ApiError && e.status === 404) return false;
  throw e;
}

/** Wie lange ein abgerufenes eigenes Profil für weitere Fragen gilt (`ApiClient.getMe`). */
const ME_TTL = 10_000;

/** **Eine Datei des Servers** (`/api/v1/…`, z. B. ein Dokument oder sein Vorschaubild) –
 *  im Betrieb dieselbe Herkunft, lokal das Backend. Die eine Stelle, die die Basis kennt. */
export function assetUrl(path: string): string {
  return path.startsWith('/api/') ? `${API_BASE}${path}` : path;
}

/** Das Signal, mit dem React Query eine überholte Anfrage abbricht. */
export interface Req { signal?: AbortSignal }

function aborted(options: RequestInit): boolean {
  return !!options.signal?.aborted;
}

/** **Kein Netz ist eine eigene Art Fehler** (`code: 'offline'`, Status 0) – die Oberfläche fragt
 *  `e.code === 'offline'`, nie den Wortlaut. */
function offline(): ApiError {
  return new ApiError('Keine Verbindung zum Server', 0, 'offline');
}

/** `fetch`, dessen Netzfehler `offline()` ist; ein Abbruch bleibt ein Abbruch. */
async function reach(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (e) {
    if (aborted(init)) throw e;
    throw offline();
  }
}

/**
 * **«Ich habe Daten geändert» – an EINER Stelle gesagt**: nach jeder erfolgreichen Anfrage,
 * die kein GET ist. Der Feed (`lib/feed.ts`) invalidiert, was der **Pfad** betrifft.
 */
function notifyDataChanged(path: string) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(DATA_CHANGED, { detail: { path } }));
}

// ─── Die Routen des Backends als Typen (`types/api.ts`, generiert aus `openapi.json`) ──────
// Pfad, Methode, Pfad-Parameter, Query, Rumpf und Antwort jeder Anfrage prüft der Compiler
// gegen das Backend: ein Pfad, den es nicht gibt, ist ein Typfehler.

type Method = 'get' | 'post' | 'put' | 'patch' | 'delete';
/** Die Handlung `M` an Pfad `P`, wie das Backend sie beschreibt (`never`, wenn es sie nicht gibt). */
type Op<M extends Method, P extends keyof paths> = Exclude<paths[P][M], undefined>;
/** Jeder Pfad, den es mit Methode `M` gibt. */
type Route<M extends Method> = { [P in keyof paths]: [Op<M, P>] extends [never] ? never : P }[keyof paths];

type Params<O> = O extends { parameters: infer X } ? X : never;
type PathArg<O> = Params<O> extends { path: infer X } ? { path: X } : { path?: never };
type QueryArg<O> = Params<O> extends { query: infer Q } ? { query: Q }
  : Params<O> extends { query?: infer Q } ? ([NonNullable<Q>] extends [never] ? { query?: never } : { query?: Q })
  : { query?: never };
type Json<X> = X extends { content: { 'application/json': infer T } } ? T : never;
type BodyOf<O> = O extends { requestBody?: infer R } ? Json<NonNullable<R>> : never;
type BodyArg<O> = [BodyOf<O>] extends [never] ? { body?: never } : { body: BodyOf<O> };
type Args<O> = PathArg<O> & QueryArg<O> & BodyArg<O>;
/** Die Antwort im Erfolg (200 · 201; 204 = nichts). */
type Ok<O> = O extends { responses: infer R }
  ? R extends { 200: infer X } ? Json<X> : R extends { 201: infer X } ? Json<X> : R extends { 204: unknown } ? void : never
  : never;

/** Was `M` an `P` als JSON-Rumpf nimmt bzw. im Erfolg antwortet – für Parameter und Felder. */
type In<M extends Method, P extends Route<M>> = BodyOf<Op<M, P>>;
type Res<M extends Method, P extends Route<M>> = Narrowed<Ok<Op<M, P>>>;

/** **Was `types/index.ts` enger fasst als das Backend** (die Rolle einer Person; Status,
 *  Einheit und Serialisierung eines Artikels – dort `string`) – verengt an dieser einen Stelle. */
type Narrowed<T> = T extends components['schemas']['UserProfileResponse'] ? UserProfile
  : T extends components['schemas']['ArticleResponse'] ? Article
  : T extends (infer E)[] ? Narrowed<E>[] : T;

type Loose = { path?: Record<string, unknown>; query?: Record<string, unknown>; body?: unknown };

/** **Die Adresse einer Anfrage**: `{name}` aus `path` (kodiert), dazu die Query – leere Werte
 *  (`undefined`, `null`) fallen weg, eine Liste wird je Wert wiederholt (`status=a&status=b`). */
function fill(route: string, args: Loose = {}): string {
  const url = route.replace(/\{(\w+)\}/g, (_, name: string) => {
    const v = args.path?.[name];
    if (v == null) throw new Error(`Pfad-Parameter «${name}» fehlt: ${route}`);
    return encodeURIComponent(String(v));
  });
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(args.query ?? {})) {
    for (const x of Array.isArray(v) ? v : [v]) if (x != null) q.append(k, String(x));
  }
  const qs = q.toString();
  return qs ? `${url}?${qs}` : url;
}

class ApiClient {
  /**
   * **Jede Methode ist an ihren Client gebunden**: als Wert weitergereicht
   * (`search={api.searchPeople}`) behält sie ihr `this`. Über den Prototyp, nicht über
   * eine Namensliste – die vergässe den nächsten Endpunkt.
   */
  constructor() {
    const proto = Object.getPrototypeOf(this) as object;
    for (const name of Object.getOwnPropertyNames(proto)) {
      if (name === 'constructor') continue;
      // Über den Deskriptor: ein Getter würde beim blossen Lesen ausgeführt.
      const desc = Object.getOwnPropertyDescriptor(proto, name);
      if (typeof desc?.value === 'function') {
        (this as unknown as Record<string, unknown>)[name] = desc.value.bind(this);
      }
    }
  }

  /**
   * **Woher der Token kommt** – je Anfrage gefragt, registriert von `lib/firebase.ts` (so
   * bleibt `api.ts` frei von Firebase). `force` erzwingt einen frischen (nach einem 401);
   * ohne Anmeldung `null`, die Anfrage geht ohne Token.
   */
  private tokenProvider: ((force: boolean) => Promise<string | null>) | null = null;

  setTokenProvider(fn: (force: boolean) => Promise<string | null>) {
    this.tokenProvider = fn;
  }

  /**
   * **Das eigene Profil – EIN Abruf für alle, die es gleichzeitig fragen**, gehalten für
   * `ME_TTL`; jede schreibende Anfrage und `forgetMe` verwerfen es, ein Fehler wird nicht gehalten.
   */
  private me: { at: number; promise: Promise<Res<'get', '/api/v1/auth/me'>> } | null = null;

  /** Das gehaltene Profil verwerfen – beim Abmelden und bei jedem Wechsel der Person. */
  forgetMe() {
    this.me = null;
  }

  // 502/503 und abgewiesene Verbindungen erreichen die App nie → auch schreibende Anfragen
  // werden wiederholt; 500/504 nur lesende (idempotente).
  private async request<T>(path: string, options: RequestInit = {}, as: 'json' | 'blob' = 'json'): Promise<T> {
    // Eine Datei geht als `FormData` – den Typ samt Grenze setzt dann der Browser selbst.
    const headers: Record<string, string> = {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...((options.headers as Record<string, string>) || {}),
    };
    const token = this.tokenProvider ? await this.tokenProvider(false).catch(() => null) : null;
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const method = (options.method ?? 'GET').toUpperCase();
    const idempotent = method === 'GET' || method === 'HEAD';
    const MAX_ATTEMPTS = 3;
    let lastError: Error = offline();
    let refreshed = false;   // Token-Erneuerung: höchstens EINMAL je Anfrage

    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      let response: Response;
      try {
        response = await fetch(`${API_BASE}${path}`, { ...options, headers });
      } catch (e) {
        if (aborted(options)) throw e;
        lastError = offline();
        if (attempt < MAX_ATTEMPTS) { await this.backoff(attempt); continue; }
        throw lastError;
      }

      if (response.ok) {
        if (!idempotent) { this.forgetMe(); notifyDataChanged(path); }
        if (response.status === 204) return {} as T;
        return (as === 'blob' ? response.blob() : response.json()) as Promise<T>;
      }

      // 401 = Token abgelaufen: EINMAL einen frischen holen und dieselbe Anfrage wiederholen.
      if (response.status === 401 && !refreshed && this.tokenProvider) {
        refreshed = true;
        const fresh = await this.tokenProvider(true).catch(() => null);
        if (fresh) {
          headers['Authorization'] = `Bearer ${fresh}`;
          continue;   // zählt als Versuch – kein Backoff nötig, der Server war erreichbar
        }
      }

      const retriable = response.status === 502 || response.status === 503
        || (idempotent && response.status >= 500);
      if (retriable && attempt < MAX_ATTEMPTS && !aborted(options)) {
        lastError = new Error(`Server nicht erreichbar (HTTP ${response.status})`);
        await this.backoff(attempt);
        continue;
      }
      throw await this.apiError(response);
    }
    throw lastError;
  }

  /** Die Abweisung des Servers: `{detail, code, field?}` – sonst der HTTP-Status als Satz. */
  private async apiError(response: Response): Promise<ApiError> {
    const body = (await response.clone().json().catch(() => null)) as
      { detail?: unknown; code?: unknown; field?: unknown } | null;
    return new ApiError(await this.errorMessage(response), response.status,
      typeof body?.code === 'string' ? body.code : '',
      typeof body?.field === 'string' ? body.field : undefined);
  }

  private backoff(attempt: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, attempt === 1 ? 500 : 1200));
  }

  // Bevorzugt das JSON-`detail` der API, sonst der HTTP-Status.
  private async errorMessage(response: Response): Promise<string> {
    const body = (await response.clone().json().catch(() => null)) as
      { detail?: unknown; error?: string } | null;
    const detail = body?.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (body?.error) return body.error;
    return response.status >= 500
      ? `Server nicht erreichbar (HTTP ${response.status})`
      : `HTTP ${response.status}`;
  }

  /**
   * ►►► **Die eine getippte Anfrage** ◄◄◄ – Methode und Pfad wie im Backend (`'/api/v1/x/{id}'`),
   * dazu Pfad-Parameter, Query und JSON-Rumpf; die Antwort ist der Typ, den das Backend nennt.
   * Ohne Rumpf geht ein schreibender Aufruf mit `{}` hinaus.
   */
  private call<M extends Method, P extends Route<M>>(
    method: M, route: P,
    ...[args, req]: {} extends Args<Op<M, P>>
      ? [args?: Args<Op<M, P>>, req?: Req] : [args: Args<Op<M, P>>, req?: Req]
  ): Promise<Res<M, P>> {
    const a = (args ?? {}) as Loose;
    const body = a.body !== undefined ? JSON.stringify(a.body)
      : method === 'get' || method === 'delete' ? undefined : '{}';
    return this.request(fill(route, a), { method: method.toUpperCase(), body, signal: req?.signal });
  }

  /** **Eine Datei hochladen** (multipart) – dieselbe Anfrage, der Rumpf ist ein `FormData`. */
  private upload<P extends Route<'post'>>(route: P, form: FormData, path?: Record<string, unknown>,
                                          req: Req = {}): Promise<Res<'post', P>> {
    return this.request(fill(route, { path }), { method: 'POST', body: form, signal: req.signal });
  }

  // ─── Auth / Profile ────────────────────────────────────────────────────────

  getMe() {
    if (this.me && Date.now() - this.me.at < ME_TTL) return this.me.promise;
    const entry = { at: Date.now(), promise: this.call('get', '/api/v1/auth/me') };
    this.me = entry;
    entry.promise.catch(() => { if (this.me === entry) this.me = null; });
    return entry.promise;
  }

  updateMe(body: In<'patch', '/api/v1/auth/me'>) {
    return this.call('patch', '/api/v1/auth/me', { body });
  }

  /** Darf die Anmelde-E-Mail auf diese Adresse wechseln? Wirft den Grund (409), sonst nichts. */
  async checkMyEmail(email: string): Promise<void> {
    await this.call('post', '/api/v1/auth/me/email-check', { body: { email } });
  }

  // ─── Das Adressbuch – im Konto die eigene Person, im ERP ein Datensatz ──────
  // `services/address_book`; die Antwort ist jedes Mal der ganze Benutzer.
  // `owner`: `null` = die eigene Person (Konto), sonst die Objektnummer (ERP).

  addAddress(owner: number | null, body: In<'post', '/api/v1/auth/me/addresses'>) {
    return owner == null
      ? this.call('post', '/api/v1/auth/me/addresses', { body })
      : this.call('post', '/api/v1/erp/records/{object_id}/addresses', { path: { object_id: owner }, body });
  }

  changeAddress(owner: number | null, id: number, body: In<'patch', '/api/v1/auth/me/addresses/{address_id}'>) {
    return owner == null
      ? this.call('patch', '/api/v1/auth/me/addresses/{address_id}', { path: { address_id: id }, body })
      : this.call('patch', '/api/v1/erp/records/{object_id}/addresses/{address_id}',
        { path: { object_id: owner, address_id: id }, body });
  }

  removeAddress(owner: number | null, id: number) {
    return owner == null
      ? this.call('delete', '/api/v1/auth/me/addresses/{address_id}', { path: { address_id: id } })
      : this.call('delete', '/api/v1/erp/records/{object_id}/addresses/{address_id}',
        { path: { object_id: owner, address_id: id } });
  }

  // ─── Passkeys (WebAuthn/FIDO2) ──────────────────────────────────────────────
  // Registrierung/Verwaltung setzen eine Anmeldung voraus; die Anmeldung per
  // Passkey selbst ist unauthentifiziert und liefert einen Firebase Custom Token.
  // Die Optionen beschreibt das Backend nur als Objekt – ihre Form ist die von WebAuthn.
  passkeyRegisterOptions(): Promise<PublicKeyCredentialCreationOptionsJSON> {
    return this.call('post', '/api/v1/auth/passkeys/register/options') as Promise<never>;
  }

  passkeyRegisterVerify(credential: RegistrationResponseJSON, deviceName?: string) {
    return this.call('post', '/api/v1/auth/passkeys/register/verify',
      { body: { credential: { ...credential }, device_name: deviceName ?? null } });
  }

  // ─── Der Zugang einer Person – im Konto die eigene, im ERP ein Datensatz ─────
  // Dieselben Dienste (`passkey`, `mcp`); im ERP nur die Person selbst und der Admin
  // (`policy` «person.access», `routers/access.py`). `owner`: `null` = die eigene Person.

  listPasskeys(owner: number | null = null) {
    return owner == null
      ? this.call('get', '/api/v1/auth/passkeys')
      : this.call('get', '/api/v1/erp/records/{object_id}/passkeys', { path: { object_id: owner } });
  }

  deletePasskey(owner: number | null, id: number) {
    return owner == null
      ? this.call('delete', '/api/v1/auth/passkeys/{passkey_id}', { path: { passkey_id: id } })
      : this.call('delete', '/api/v1/erp/records/{object_id}/passkeys/{passkey_id}',
        { path: { object_id: owner, passkey_id: id } });
  }

  /** Die offenen Verbindungen mit Claude (zuletzt benutzt vor höchstens 30 Tagen). */
  mcpGrants(owner: number | null) {
    return owner == null
      ? this.call('get', '/api/v1/auth/me/mcp')
      : this.call('get', '/api/v1/erp/records/{object_id}/mcp', { path: { object_id: owner } });
  }

  /** Eine Verbindung trennen – die Antwort sind die übrigen. */
  revokeMcpGrant(owner: number | null, id: number) {
    return owner == null
      ? this.call('post', '/api/v1/auth/me/mcp/{grant_id}/revoke', { path: { grant_id: id } })
      : this.call('post', '/api/v1/erp/records/{object_id}/mcp/{grant_id}/revoke',
        { path: { object_id: owner, grant_id: id } });
  }

  passkeyLoginOptions(): Promise<PublicKeyCredentialRequestOptionsJSON> {
    return this.call('post', '/api/v1/auth/passkeys/login/options') as Promise<never>;
  }

  passkeyLoginVerify(credential: AuthenticationResponseJSON) {
    return this.call('post', '/api/v1/auth/passkeys/login/verify', { body: { credential: { ...credential } } });
  }

  // ─── Öffentlich: die Seite eines Dokuments (`/dokument?t=…`) und die AGB (`/agb`) ──
  // Ohne Anmeldung: der unerratbare Link IST die Berechtigung (`routers/public_documents.py`). Ist
  // jemand angemeldet, reist sein Token mit – die Routen fragen nicht danach.

  /** **Ein Dokument über seinen Link** – das eingefrorene Papier, der Weg, die Handlungen. */
  publicDocument(token: string) {
    return this.call('get', '/api/v1/public/document/{token}', { path: { token } });
  }

  signDocument(token: string, image: string) {
    return this.call('post', '/api/v1/public/document/{token}/sign', { path: { token }, body: { image } });
  }

  declineDocument(token: string, reason: string) {
    return this.call('post', '/api/v1/public/document/{token}/decline', { path: { token }, body: { reason } });
  }

  /** **Die Offerte annehmen** – als die Partei eines Belegs; die Antwort ist die neue Ansicht. */
  agreeDocument(token: string) {
    return this.call('post', '/api/v1/public/document/{token}/agree', { path: { token } });
  }

  /** **Die Offerte ablehnen** – als die Partei; die Antwort ist die neue Ansicht. */
  rejectDocument(token: string) {
    return this.call('post', '/api/v1/public/document/{token}/reject', { path: { token } });
  }

  /** **Mit Karte bezahlen** – die Zahlungsabsicht über den offenen Betrag (wie
   *  `prepareVoucherPayment`); gebucht wird vom Webhook. */
  prepareDocumentPayment(token: string) {
    return this.call('post', '/api/v1/public/document/{token}/payment', { path: { token } });
  }

  // ─── Claude (MCP): verbinden und trennen (`routers/mcp.py`) ─────────────────

  /** Welcher Claude-Client verbunden werden will (Seite `/erp/verbinden`). */
  mcpRequest(r: string) {
    return this.call('get', '/api/v1/mcp/oauth/request', { query: { r } });
  }

  /** Erlauben oder ablehnen – die Antwort ist die Adresse zurück zum Client. */
  mcpApprove(r: string, allow: boolean) {
    return this.call('post', '/api/v1/mcp/oauth/approve', { body: { r, allow } });
  }

  /** **Ein Rechtstext, wie er heute gilt** (AGB · Datenschutz · Impressum) – als A4-Dokument. */
  publicLegal(kind: 'agb' | 'datenschutz' | 'impressum') {
    return this.call('get', '/api/v1/public/legal/{kind}', { path: { kind } });
  }

  // ─── Öffentliche Einstellungen ─────────────────────────────────────────────

  /** Der Google-Maps-Schlüssel der Adress-Suche – aus der Deploy-Konfiguration, `null` ohne.
   *  (Die Route nennt keine Antwortform – darum hier die eine Angabe von Hand.) */
  getMapsKey(): Promise<string | null> {
    return this.call('get', '/api/v1/admin/settings/public')
      .then((s) => (s as { google_maps_api_key?: string | null }).google_maps_api_key || null);
  }

  // ─── Admin: Unternehmen (Gesellschaften) ───────────────────────────────────
  // Eigene anlegen/ändern nur Admin, fremde jedes Personal; Feldnamen wie im Backend.

  getCompanies() {
    return this.call('get', '/api/v1/admin/companies');
  }

  getCompany(objectId: number, req?: Req) {
    return this.call('get', '/api/v1/admin/companies/{object_id}', { path: { object_id: objectId } }, req);
  }

  /** Eine Firma anlegen – Name und Rechtsform sind Pflicht; ``is_own`` setzt nur ein Admin. */
  createCompany(body: In<'post', '/api/v1/admin/companies'>) {
    return this.call('post', '/api/v1/admin/companies', { body });
  }

  /** **Welche Firma ist gemeint?** – Vorschläge für das **Personal** (die Tür lässt nur
   *  Personal durch: Kunden nennen ihre Firma über die UID, sie suchen sie nicht). */
  searchCompanies(search: string) {
    return this.call('get', '/api/v1/erp/companies', { query: { search } });
  }

  updateCompany(objectId: number, body: In<'patch', '/api/v1/admin/companies/{object_id}'>) {
    return this.call('patch', '/api/v1/admin/companies/{object_id}', { path: { object_id: objectId }, body });
  }

  /** Diese Gesellschaft zum **Betreiber der Website** machen – genau EINE trägt den Titel. */
  setCompanyOperator(objectId: number) {
    return this.call('post', '/api/v1/admin/companies/{object_id}/operator', { path: { object_id: objectId } });
  }

  /** Ein Unternehmen **schliessen** (Soft-Delete; `reopenCompany` macht es rückgängig). */
  deactivateCompany(objectId: number) {
    return this.call('delete', '/api/v1/admin/companies/{object_id}', { path: { object_id: objectId } });
  }

  reopenCompany(objectId: number) {
    return this.call('post', '/api/v1/admin/companies/{object_id}/reopen', { path: { object_id: objectId } });
  }

  // ─── Gebiete (Weltkarte: welche Gesellschaft fakturiert welche Region) ─────────
  getTerritories() {
    return this.call('get', '/api/v1/admin/territories');
  }

  /** `area` = Regions-Code («EUR») ODER ISO-2-Land als Ausnahme («LI»); `null` bzw. die
   *  ohnehin zuständige Gesellschaft = Standard wiederherstellen. */
  assignTerritory(area: string, companyObjectId: number | null) {
    return this.call('put', '/api/v1/admin/territories/{area}',
      { path: { area }, body: { company_object_id: companyObjectId } });
  }

  // ─── ERP Records ──────────────────────────────────────────────────────────

  getErpRecords() {
    return this.call('get', '/api/v1/erp/records');
  }

  /** Eine Person anlegen – Vorname, Nachname, E-Mail, Rolle; Nummer und Anmeldekonto sofort. */
  createErpRecord(body: In<'post', '/api/v1/erp/records'>) {
    return this.call('post', '/api/v1/erp/records', { body });
  }

  updateErpRecord(objectId: number, body: In<'patch', '/api/v1/erp/records/{object_id}'>) {
    return this.call('patch', '/api/v1/erp/records/{object_id}', { path: { object_id: objectId }, body });
  }

  // ─── Der Beleg (Modul «Zahlung») ────────────────────────────────────────────

  /** **Eine Handlung am Beleg** – ein Endpunkt, eine Tabelle (`voucher.VERBS`). */
  updateVoucher(orderObjectId: number, stepId: number,
                body: In<'post', '/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher'>) {
    return this.call('post', '/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher',
      { path: { object_id: orderObjectId, step_id: stepId }, body });
  }

  /** **Vorschau → Freigeben**: das Papier, das diese Handlung hinausgäbe – es geschieht nichts. */
  previewVoucher(orderObjectId: number, stepId: number,
                 body: In<'post', '/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher/preview'>) {
    return this.call('post', '/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher/preview',
      { path: { object_id: orderObjectId, step_id: stepId }, body });
  }

  /** **Ein Anhang einer Nachricht als Datei** – für den Entwurf eines Dokuments. */
  async messageAttachment(messageId: number, index: number, name: string): Promise<File> {
    const route: Route<'get'> = '/api/v1/erp/messages/{message_id}/attachments/{index}';
    const blob = await this.request<Blob>(fill(route, { path: { message_id: messageId, index } }), {}, 'blob');
    return new File([blob], name, { type: blob.type });
  }

  /** **Eine Runde Verfassen** – gespeichert wird nichts. */
  composeDocument(turns: In<'post', '/api/v1/erp/documents/compose'>['turns'],
                  current: In<'post', '/api/v1/erp/documents/compose'>['current']) {
    return this.call('post', '/api/v1/erp/documents/compose', { body: { turns, current } });
  }

  /** **Senden** – je Empfänger ein Link und eine Mail; `sign`: sie sollen unterschreiben. */
  sendDocument(objectId: number, to: number[], sign: boolean, note: string) {
    return this.call('post', '/api/v1/erp/documents/{object_id}/send',
      { path: { object_id: objectId }, body: { to, sign, note } });
  }

  /** «Aus Vorlage»: AGB oder Datenschutz einer eigenen Gesellschaft (nur Admin). */
  legalFromTemplate(company: number, kind: 'agb' | 'datenschutz') {
    return this.call('post', '/api/v1/erp/documents/template', { body: { company, kind } });
  }

  /** **Eine Zahlung über den offenen Betrag vorbereiten** (Karte) – ändert am Beleg nichts;
   *  gebucht wird vom Webhook. */
  prepareVoucherPayment(objectId: number, stepId: number) {
    return this.call('post', '/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher/payment',
      { path: { object_id: objectId, step_id: stepId } });
  }

  /** **Wie man diese Rechnung überweist** – Bankverbindung, Referenz, QR-Rechnung als Bild. */
  voucherTransfer(objectId: number, stepId: number, req: Req = {}) {
    return this.call('get', '/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher/transfer',
      { path: { object_id: objectId, step_id: stepId } }, req);
  }

  /**
   * ►►► **Welche Rechnung mindert dieser Beleg?** ◄◄◄ Gesucht über **alle Aufträge** (auf dem
   * Server): eine Gutschrift gehört in den Auftrag, in dem die Ware zurückkommt.
   */
  voucherCorrectable(objectId: number, stepId: number, search = '', req: Req = {}) {
    return this.call('get', '/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher/correctable',
      { path: { object_id: objectId, step_id: stepId }, query: { search: search.trim() || undefined } }, req);
  }

  /**
   * **Geld zurück – über den Dienst, der es eingezogen hat.** Nur für eine **Karten**-
   * Zahlung: bar und per Überweisung ist die Erstattung eine gewöhnliche negative Zahlung.
   */
  refundVoucherPayment(objectId: number, stepId: number, entryId: number, amount?: string) {
    return this.call('post', '/api/v1/erp/orders/{object_id}/steps/{step_id}/voucher/refund', {
      path: { object_id: objectId, step_id: stepId },
      body: { action: 'refund_online', entry: entryId, ...(amount ? { amount } : {}) },
    });
  }

  /**
   * **Personen suchen** – Nummer, Firma, Name oder E-Mail, ohne Rollenfilter
   * (`people.search`, die eine Personensuche). Gegenpartei eines Belegs, Partner im
   * Editor, Empfänger einer Nachricht.
   */
  searchPeople(search?: string, limit = 20, staff = false) {
    return this.call('get', '/api/v1/erp/people',
      { query: { limit, search: search?.trim() || undefined, staff: staff || undefined } });
  }

  /** **Der Verlauf eines Datensatzes** – eine Seite, die neuesten zuerst; `before` ist der
   *  Cursor der vorigen Seite (`services/history`). */
  history(objectId: number, before?: string, req?: Req) {
    return this.call('get', '/api/v1/erp/history/{object_id}',
      { path: { object_id: objectId }, query: { before: before || undefined } }, req);
  }

  createMessage(body: In<'post', '/api/v1/erp/messages'>) {
    return this.call('post', '/api/v1/erp/messages', { body });
  }

  /** Je Datensatz, was zu tun ist – die Zahl am Symbol in Feed und Kopf. */
  todo() {
    return this.call('get', '/api/v1/erp/todo');
  }

  // ─── Phase 5 · Der Assistent: Gespräch, Handgriff, Angeheftet (docs/konzept/phase5-bauplan.md) ──
  /** Wo das Gespräch live läuft – die direkte Adresse des Dienstes (einmal gefragt; leer = hier). */
  private door: Promise<string> | null = null;

  private talkDoor(): Promise<string> {
    this.door ??= this.call('get', '/api/v1/erp/assistant/door').then(
      (d) => d.url || API_BASE,
      (e: unknown) => { this.door = null; throw e; });
    return this.door;
  }

  /**
   * ►►► **Dem Assistenten etwas sagen – die Antwort kommt live** (wie bei Claude). ◄◄◄ Ohne `talk`
   * beginnt ein Gespräch (am offenen Datensatz `hint`); ohne Text, aber mit `talk`, antwortet die KI
   * auf das, was dasteht. `recordings` = die Aufnahmen, deren Text darin steht. Je Zeile des Streams:
   * `onTalk` (das Gespräch – sofort mit der Nachricht, am Ende mit der Antwort), `onStep` (was die KI
   * gerade tut), `onText` (ein Stück ihrer Antwort, Wort für Wort). Läuft direkt am
   * Dienst – ohne die 60 s des Hostings; begrenzt durch Schritte, Deckel und «Stopp».
   * Von Hand, weil die Antwort ein NDJSON-Stream ist; der Rumpf ist trotzdem getippt.
   */
  async say(text: string, opts: {
    talk?: number | null; hint?: number | null; files?: In<'post', '/api/v1/erp/assistant/talks'>['files'];
    recordings?: number[];
    onTalk?: (t: Talk) => void; onStep?: (step: string) => void; onText?: (piece: string) => void;
    signal?: AbortSignal;
  } = {}): Promise<Talk> {
    const path: Route<'post'> = '/api/v1/erp/assistant/talks';
    const payload: In<'post', '/api/v1/erp/assistant/talks'> = {
      text, ...(opts.talk ? { talk: opts.talk } : {}), ...(opts.hint ? { hint_object_id: opts.hint } : {}),
      ...(opts.files?.length ? { files: opts.files } : {}),
      ...(opts.recordings?.length ? { recordings: opts.recordings } : {}),
    };
    const body = JSON.stringify(payload);
    const base = await this.talkDoor();
    let res: Response | null = null;
    for (const force of [false, true]) {
      const token = this.tokenProvider ? await this.tokenProvider(force).catch(() => null) : null;
      res = await reach(`${base}${path}`, {
        method: 'POST', body, signal: opts.signal,
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (res.status !== 401 || !this.tokenProvider) break;
    }
    if (!res || !res.ok || !res.body) throw res ? await this.apiError(res) : offline();
    notifyDataChanged(path);
    let last: Talk | null = null;
    for await (const line of ndjson(res.body)) {
      const item = line as { talk?: Talk; step?: string; text?: string; error?: string };
      if (item.talk) { last = item.talk; opts.onTalk?.(item.talk); }
      if (item.step) opts.onStep?.(item.step);
      if (item.text) opts.onText?.(item.text);
      if (item.error) throw new Error(item.error);
    }
    notifyDataChanged(path);
    if (!last) throw new Error('Die Verbindung riss ab – deine Nachricht ist gespeichert.');
    return last;
  }

  /** **Stopp** – die KI hält vor ihrem nächsten Schritt an; was sie vorbereitete, bleibt. */
  stopTalk(id: number) {
    return this.call('post', '/api/v1/erp/assistant/talks/{talk_id}/stop', { path: { talk_id: id } });
  }

  /** Meine offenen Gespräche – die Zahl am «+». */
  openTalks(req?: Req) {
    return this.call('get', '/api/v1/erp/assistant/talks/open', {}, req);
  }

  /** Ein Gespräch (nur, wer es führt, und der Admin). */
  talk(id: number, req?: Req) {
    return this.call('get', '/api/v1/erp/assistant/talks/{talk_id}', { path: { talk_id: id } }, req);
  }

  /** Eine Datei (Foto, PDF) ins Gespräch – sie liegt im Korb, bis sie ein Dokument wird. */
  addTalkFile(file: Blob, name: string) {
    const form = new FormData();
    form.append('file', file, name);
    return this.upload('/api/v1/erp/assistant/files', form);
  }

  /** Eine Datei aus dem Gespräch (im Korb) – für den Dokument-Entwurf. */
  attachmentBlob(token: string): Promise<Blob> {
    const route: Route<'get'> = '/api/v1/attachments/{token}';
    return this.request<Blob>(fill(route, { path: { token } }), {}, 'blob');
  }

  /** Ein Vorschlag – für «Entwurf öffnen» über die Adresse (`?neu=…&handgriff=…`). */
  getHandgriff(id: number) {
    return this.call('get', '/api/v1/erp/assistant/handgriffe/{handgriff_id}', { path: { handgriff_id: id } });
  }

  /** **Übernehmen** – genau einmal, mit meinen Rechten, durch die echte Route (am Datensatz). */
  runHandgriff(id: number) {
    return this.call('post', '/api/v1/erp/assistant/handgriffe/{handgriff_id}/run', { path: { handgriff_id: id } });
  }

  /** **Weg** – der Handgriff geschieht nicht. */
  dropHandgriff(id: number) {
    return this.call('post', '/api/v1/erp/assistant/handgriffe/{handgriff_id}/drop', { path: { handgriff_id: id } });
  }

  /** **Von Hand erledigt** (Entwurf freigegeben, Datei abgelegt) – `result` = was entstand. */
  handgriffDone(id: number, result: number | null) {
    return this.call('post', '/api/v1/erp/assistant/handgriffe/{handgriff_id}/done',
      { path: { handgriff_id: id }, body: { result } });
  }

  /** **Das Angeheftete**: offene Handgriffe, dann das Wissen (`stale` = neu wählen lohnt sich). */
  pins(objectId: number, req?: Req) {
    return this.call('get', '/api/v1/erp/assistant/pins/{object_id}', { path: { object_id: objectId } }, req);
  }

  /** Das Wissen neu wählen – nur, wenn sich im Umfeld etwas geändert hat. */
  refreshPins(objectId: number) {
    return this.call('post', '/api/v1/erp/assistant/pins/{object_id}/refresh', { path: { object_id: objectId } });
  }

  // ─── Phase 4 · Sprache: Aufnehmen (docs/konzept/phase4-bauplan.md) ─────────
  /** Eine Aufnahme beginnen – `hint` = der Datensatz, der dabei offen war; `context` = die
   *  Stecknadel («Stelle: …»), sie kommt mit dem abgeschriebenen Text zurück. */
  startRecording(mime: string, hint?: number | null, context?: string | null) {
    return this.call('post', '/api/v1/erp/recordings', {
      body: { mime, ...(hint ? { hint_object_id: hint } : {}), ...(context ? { context } : {}) },
    });
  }

  /** **Ein Stück** (alle 30 s) – Abschnitt und Stück ab 0; dasselbe Stück noch einmal ersetzt es. */
  recordingChunk(id: number, segment: number, seq: number, file: Blob, req?: Req) {
    const form = new FormData();
    form.append('segment', String(segment));
    form.append('seq', String(seq));
    form.append('file', file, `${segment}-${seq}`);
    return this.upload('/api/v1/erp/recordings/{recording_id}/chunks', form, { recording_id: id }, req);
  }

  /** **Stopp** – `segments` = wie viele Abschnitte es gibt. */
  stopRecording(id: number, segments: number) {
    return this.call('post', '/api/v1/erp/recordings/{recording_id}/stop',
      { path: { recording_id: id }, body: { segments } });
  }

  /** **Weiter abschreiben** – so weit es in einer Anfrage geht (≤ 60 s); dann wieder fragen. */
  advanceRecording(id: number, req?: Req) {
    return this.call('post', '/api/v1/erp/recordings/{recording_id}/advance', { path: { recording_id: id } }, req);
  }

  /** Meine Aufnahmen, die noch nicht fertig sind. */
  openRecordings(req?: Req) {
    return this.call('get', '/api/v1/erp/recordings/open', {}, req);
  }

  /** **Verwerfen** – eine gescheiterte Aufnahme verschwindet aus dem «+». */
  dismissRecording(id: number) {
    return this.call('post', '/api/v1/erp/recordings/{recording_id}/dismiss', { path: { recording_id: id } });
  }

  // ─── Zahlungen (eine Ableitung aus den Zahlungsmodulen) ────────────────────
  /** **Die Zahlungen einer Person** (`person`) **oder einer eigenen Gesellschaft**
   *  (`company`) – neueste Nummer zuoberst. */
  paymentsOf(scope: { person: number } | { company: number }, req?: Req) {
    return this.call('get', '/api/v1/erp/payments', { query: scope }, req);
  }

  // ─── Zeiterfassung ─────────────────────────────────────────────────────────
  // Jede Schreib-Route antwortet mit der neuen Ansicht des gezeigten Monats (`month`,
  // «2026-10»; leer = der aktuelle).

  timeView(person: number, month?: string, req: Req = {}) {
    return this.call('get', '/api/v1/erp/time/{object_id}',
      { path: { object_id: person }, query: { month: month || undefined } }, req);
  }

  timeSwipe(person: number, direction: 'in' | 'out', key: string, month?: string) {
    return this.call('post', '/api/v1/erp/time/{object_id}/swipe',
      { path: { object_id: person }, query: { month: month || undefined }, body: { direction, key } });
  }

  timeEntry(person: number, body: In<'post', '/api/v1/erp/time/{object_id}/entries'>, month?: string) {
    return this.call('post', '/api/v1/erp/time/{object_id}/entries',
      { path: { object_id: person }, query: { month: month || undefined }, body });
  }

  /** Was ein Eintrag bewirken würde – dieselbe Regel wie beim Speichern, ohne zu schreiben. */
  timePreview(person: number, body: In<'post', '/api/v1/erp/time/{object_id}/entries/preview'>, req?: Req) {
    return this.call('post', '/api/v1/erp/time/{object_id}/entries/preview',
      { path: { object_id: person }, body }, req);
  }

  timeContract(person: number, body: In<'post', '/api/v1/erp/time/{object_id}/contracts'>, month?: string) {
    return this.call('post', '/api/v1/erp/time/{object_id}/contracts',
      { path: { object_id: person }, query: { month: month || undefined }, body });
  }

  companyTime(company: number, year?: number, req: Req = {}) {
    return this.call('get', '/api/v1/erp/time/companies/{object_id}',
      { path: { object_id: company }, query: { year: year || undefined } }, req);
  }

  holidayProposal(company: number, year: number) {
    return this.call('get', '/api/v1/erp/time/companies/{object_id}/proposal',
      { path: { object_id: company }, query: { year } });
  }

  addHolidays(company: number, holidays: In<'post', '/api/v1/erp/time/companies/{object_id}/holidays'>['holidays'],
              year: number) {
    return this.call('post', '/api/v1/erp/time/companies/{object_id}/holidays',
      { path: { object_id: company }, query: { year }, body: { holidays } });
  }

  removeHoliday(company: number, id: number, year: number) {
    return this.call('delete', '/api/v1/erp/time/companies/{object_id}/holidays/{holiday_id}',
      { path: { object_id: company, holiday_id: id }, query: { year } });
  }

  setTimeRules(company: number, body: In<'put', '/api/v1/erp/time/companies/{object_id}/rules'>, year: number) {
    return this.call('put', '/api/v1/erp/time/companies/{object_id}/rules',
      { path: { object_id: company }, query: { year }, body });
  }

  messageChannels(req?: Req) {
    return this.call('get', '/api/v1/erp/messages/channels', {}, req);
  }

  /** Das Postfach einer eigenen Gesellschaft – Adresse, Zustand, darf ich verbinden?
   *  Persönliche Postfächer gibt es nicht. */
  mailboxes(company: number, req?: Req) {
    return this.call('get', '/api/v1/erp/messages/mailboxes', { query: { company } }, req);
  }

  /** Die Adresse bei Google, an der die Zustimmung erteilt wird. */
  connectMailbox(channel: string) {
    return this.call('post', '/api/v1/erp/messages/mailboxes/{channel}/connect', { path: { channel } });
  }

  disconnectMailbox(channel: string) {
    return this.call('delete', '/api/v1/erp/messages/mailboxes/{channel}', { path: { channel } });
  }

  /** Postfächer abgleichen und Fälliges senden – der Server drosselt selbst. */
  syncMail() {
    return this.call('post', '/api/v1/erp/messages/sync');
  }
  resendMessage(id: number) {
    return this.call('post', '/api/v1/erp/messages/{message_id}/resend', { path: { message_id: id } });
  }

  // ─── Newsletter ────────────────────────────────────────────────────────────

  /** Mein Newsletter – angemeldet oder nicht, und der Satz, dem ich zustimme. */
  myNewsletter() {
    return this.call('get', '/api/v1/auth/me/newsletter');
  }

  setMyNewsletter(subscribed: boolean) {
    return this.call('put', '/api/v1/auth/me/newsletter', { body: { subscribed } });
  }

  /** Zustand und Nachweis einer Person (ERP). */
  personNewsletter(objectId: number, req?: Req) {
    return this.call('get', '/api/v1/erp/newsletter/{object_id}', { path: { object_id: objectId } }, req);
  }

  /** Die Bitte um Bestätigung schicken – anmelden kann das ERP niemanden. */
  inviteNewsletter(objectId: number) {
    return this.call('post', '/api/v1/erp/newsletter/{object_id}/invite', { path: { object_id: objectId } });
  }

  unsubscribeNewsletter(objectId: number) {
    return this.call('post', '/api/v1/erp/newsletter/{object_id}/unsubscribe', { path: { object_id: objectId } });
  }

  // ─── ERP Articles ──────────────────────────────────────────────────────────

  /** Der Artikel-Feed; `search` sucht im Namen. */
  getArticles(search?: string, limit?: number) {
    return this.call('get', '/api/v1/erp/articles', { query: { search: search?.trim() || undefined, limit: limit || undefined } });
  }

  getArticle(objectId: number, req?: Req) {
    return this.call('get', '/api/v1/erp/articles/{object_id}', { path: { object_id: objectId } }, req);
  }

  /** Wäre dieser Artikel-Entwurf freigebbar? Legt nichts an und zieht keine Nummer –
   *  dieselbe Regel, die auch die Anlage prüft (services/articles.validate_draft). */
  validateArticle(body: In<'post', '/api/v1/erp/articles/validate'>, req?: Req) {
    return this.call('post', '/api/v1/erp/articles/validate', { body }, req);
  }

  /** Anlegen **ist** Freigeben: Spezifikation UND Erzeugungsprozess in einem Aufruf –
   *  erst dabei entsteht der Datensatz und seine Objektnummer. */
  createArticle(body: In<'post', '/api/v1/erp/articles'>) {
    return this.call('post', '/api/v1/erp/articles', { body });
  }

  /** Namensvorschläge gegen Dubletten; leer → die häufigsten bestehenden Namen. */
  articleNameSuggestions(q: string) {
    return this.call('get', '/api/v1/erp/articles/name-suggestions', { query: { q } });
  }

  // ─── Dokumente (`services/documents`) ───────────────────────────────────────
  /** Der Feed «Dokument» – seitenweise, durchsucht auf dem Server (wie die Instanzen). */
  getDocuments(q = '', limit = 100, offset = 0) {
    return this.call('get', '/api/v1/erp/documents', { query: { q, limit, offset } });
  }

  getDocument(objectId: number, req?: Req) {
    return this.call('get', '/api/v1/erp/documents/{object_id}', { path: { object_id: objectId } }, req);
  }

  /** Die Kacheln unten an einem Datensatz. */
  documentsOf(objectId: number, req?: Req) {
    return this.call('get', '/api/v1/erp/documents/of/{object_id}', { path: { object_id: objectId } }, req);
  }

  /** Ein Datensatz für eine Referenz – Nummer ODER Name. */
  documentTargets(q: string) {
    return this.call('get', '/api/v1/erp/documents/targets', { query: { q } });
  }

  /** **Einen Entwurf lesen** – nichts wird gespeichert. */
  readDraft(files: Blob[], opts: { sender?: number | null; hint?: string } = {}) {
    const form = new FormData();
    files.forEach((f, i) => form.append('files', f, f instanceof File ? f.name : `seite-${i + 1}`));
    if (opts.sender) form.append('sender', String(opts.sender));
    if (opts.hint) form.append('hint', opts.hint);
    return this.upload('/api/v1/erp/documents/read', form);
  }

  /** **Freigeben** – das Dokument entsteht erst hier (eine Datei oder mehrere Seiten). */
  fileDocument(files: Blob[], data: {
    art: string; name: string; source: string; refs: number[];
    target?: In<'post', '/api/v1/erp/documents/{object_id}/field'> | null;
    text?: string; keywords?: string; facts?: Record<string, unknown>;
    /** Wer unterschreiben soll (Personen). */
    signers?: number[];
  }) {
    const form = new FormData();
    files.forEach((f, i) => form.append('files', f, f instanceof File ? f.name : `seite-${i + 1}`));
    form.append('art', data.art);
    form.append('name', data.name);
    form.append('source', data.source);
    form.append('refs', JSON.stringify(data.refs.map((object_id) => ({ object_id }))));
    if (data.target) form.append('target', JSON.stringify(data.target));
    if (data.signers?.length) form.append('signers', JSON.stringify(data.signers));
    if (data.text) form.append('text', data.text);
    if (data.keywords) form.append('keywords', data.keywords);
    if (data.facts && Object.keys(data.facts).length) form.append('facts', JSON.stringify(data.facts));
    return this.upload('/api/v1/erp/documents', form);
  }

  addDocumentRef(objectId: number, target: number) {
    return this.call('post', '/api/v1/erp/documents/{object_id}/refs',
      { path: { object_id: objectId }, body: { object_id: target } });
  }

  removeDocumentRef(objectId: number, refId: number) {
    return this.call('delete', '/api/v1/erp/documents/{object_id}/refs/{ref_id}',
      { path: { object_id: objectId, ref_id: refId } });
  }

  /** Ein schon freigegebenes Dokument in ein Pflichtfeld – ändern, nie leeren. */
  setDocumentField(objectId: number, body: In<'post', '/api/v1/erp/documents/{object_id}/field'>) {
    return this.call('post', '/api/v1/erp/documents/{object_id}/field', { path: { object_id: objectId }, body });
  }

  deleteDocument(objectId: number, reason: string) {
    return this.call('post', '/api/v1/erp/documents/{object_id}/delete',
      { path: { object_id: objectId }, body: { reason } });
  }

  /** Das Lesen nachholen (ohne KI freigegeben). */
  readDocumentLater(objectId: number) {
    return this.call('post', '/api/v1/erp/documents/{object_id}/read', { path: { object_id: objectId } });
  }

  // ─── Foto-/Bild-Upload (multipart) ──────────────────────────────────────────
  // Gibt eine relative URL (Token) zurück; die speichern die Verbraucher als String.
  // Von Hand: einmal versucht, ohne Wiederholung und ohne «Daten geändert».
  async uploadAttachment(file: File): Promise<Res<'post', '/api/v1/erp/attachments'>> {
    const token = this.tokenProvider ? await this.tokenProvider(false).catch(() => null) : null;
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    const form = new FormData();
    form.append('file', file);
    const route: Route<'post'> = '/api/v1/erp/attachments';
    const res = await reach(`${API_BASE}${route}`, { method: 'POST', headers, body: form });
    if (!res.ok) throw await this.apiError(res);
    return res.json();
  }

  // Bestand eines Artikels: Aufstellung über ALLE Stücke + eine Seite Instanzen.
  getArticleStock(objectId: number, limit = 50, offset = 0, req?: Req) {
    return this.call('get', '/api/v1/erp/articles/{object_id}/stock',
      { path: { object_id: objectId }, query: { limit, offset } }, req);
  }

  // Ebene 3: die Nummern der Einzelinstanzen – seitenweise, auf Klick; `statuses` ist eine Menge.
  getInstanceUnits(objectId: number, opts: {
    statuses?: readonly string[]; limit?: number; offset?: number;
  } = {}, req?: Req) {
    return this.call('get', '/api/v1/erp/instances/{object_id}/units', {
      path: { object_id: objectId },
      query: { status: [...(opts.statuses ?? [])], limit: opts.limit ?? 60, offset: opts.offset ?? 0 },
    }, req);
  }

  /** **Woraus besteht ein Stück – und worin steckt es?** Abgeleitet aus dem Log
   *  (`services/genealogy`); erst auf Klick. */
  getUnitGenealogy(objectId: number, suffix: number, req?: Req) {
    return this.call('get', '/api/v1/erp/instances/{object_id}/units/{suffix}/genealogy',
      { path: { object_id: objectId, suffix } }, req);
  }

  // ─── Auftrag ───────────────────────────────────────────────────────────────
  // Kein Entwurfs-Endpunkt: der Entwurf lebt im Browser, erst `createOrder` legt ihn an.

  getOrders(limit = 0, offset = 0) {
    return this.call('get', '/api/v1/erp/orders', { query: { limit: limit || undefined, offset: offset || undefined } });
  }

  getOrder(objectId: number, req?: Req) {
    return this.call('get', '/api/v1/erp/orders/{object_id}', { path: { object_id: objectId } }, req);
  }

  /** Wäre dieser Entwurf speicherbar? Dieselbe Regel wie beim Anlegen, legt nichts an. */
  validateOrder(body: In<'post', '/api/v1/erp/orders/validate'>, req?: Req) {
    return this.call('post', '/api/v1/erp/orders/validate', { body }, req);
  }

  /** Anlegen **ist** Freigeben: ein Aufruf, eine Transaktion – der Auftrag entsteht,
   *  bekommt seine Nummer, die Stücke passieren das Start-Objekt (PROCESS_CORE.md §6.3). */
  createOrder(body: In<'post', '/api/v1/erp/orders'>) {
    return this.call('post', '/api/v1/erp/orders', { body });
  }

  /** **Die Wiederholung beenden** – nur am neuesten Auftrag der Kette (`services/loop.end`). */
  endLoop(objectId: number) {
    return this.call('post', '/api/v1/erp/orders/{object_id}/loop/end', { path: { object_id: objectId } });
  }

  /** **Eine Seite wählbarer Einzelinstanzen** – Gesperrte kommen mit (die Oberfläche nennt
   *  den Grund). `preselect`: die FIFO-Vorauswahl rechnet der Server, nie eine gekappte Seite. */
  getUnitOptions(opts: {
    articleObjectId?: number; search?: string; status?: string[];
    preselect?: number; limit?: number; offset?: number;
  } = {}, req?: Req) {
    return this.call('get', '/api/v1/erp/orders/unit-options', {
      query: {
        article: opts.articleObjectId || undefined, search: opts.search?.trim() || undefined,
        status: opts.status, preselect: opts.preselect || undefined,
        limit: opts.limit || undefined, offset: opts.offset || undefined,
      },
    }, req);
  }

  /** Welche Artikel kann eine Definitionszeile aufnehmen? **Gesucht, nicht geladen** –
   *  passend zur Eingabe oder genau der gewählte (`objectId`). */
  getArticleOptions(opts: { search?: string; objectId?: number; limit?: number } = {}, req: Req = {}) {
    return this.call('get', '/api/v1/erp/orders/article-options', {
      query: {
        object_id: opts.objectId,
        search: opts.objectId == null ? opts.search?.trim() || undefined : undefined,
        limit: opts.limit || undefined,
      },
    }, req);
  }

  /** Die Stücke **einer Kante** des Prozessbildes – erst beim Aufklappen. */
  getOrderUnits(objectId: number, edge: string, limit = 100, offset = 0) {
    return this.call('get', '/api/v1/erp/orders/{object_id}/units',
      { path: { object_id: objectId }, query: { edge, limit, offset } });
  }

  // ─── Erzeugungsprozess des Artikels (Vorlage) ──────────────────────────────
  // Die Vorlage führt nichts aus und hat keinen Schreib-Endpunkt (entsteht mit dem Artikel).

  getArticleProcess(objectId: number, req?: Req) {
    return this.call('get', '/api/v1/erp/articles/{object_id}/process', { path: { object_id: objectId } }, req);
  }

  /** Was sich modellieren lässt – Modultypen und Erfassungspunkt-Typen, vom Backend. */
  getModuleCatalog(req: Req = {}) {
    return this.call('get', '/api/v1/erp/orders/module-catalog', {}, req);
  }

  /**
   * «Bestätigen» – der eine Ausführungs-Endpunkt, **für genau eine Instanz**. `values`:
   * Nummer der Einzelinstanz → (Punkt-`key` → Wert); `verification` = `scan` | `manual`.
   */
  confirmStep(objectId: number, stepId: number, values: Record<string, Record<string, unknown>> = {},
              instanceObjectId?: number | null, verification?: string,
              sources: number[] = [], place: number | null = null) {
    return this.call('post', '/api/v1/erp/orders/{object_id}/steps/{step_id}/confirm', {
      path: { object_id: objectId, step_id: stepId },
      body: {
        values,
        instance_object_id: instanceObjectId ?? null,
        verification: verification ?? null,
        // Woraus verbaut wird; leer = der freie Bestand, älteste zuerst.
        sources,
        // Wohin bewegt wurde: Verifikation eines festen Ziels, sonst die Wahl.
        place,
      },
    });
  }

  /**
   * Die Nummern **einer Gruppe dieser Instanz an diesem Modul** – erst auf Klick.
   * `sample` = die gezogenen (je ein Wertesatz). Die durchgefallenen stehen in `StepWork.failed_numbers`.
   */
  stepHold(objectId: number, stepId: number, instance: number, group: 'sample') {
    return this.call('get', '/api/v1/erp/orders/{object_id}/steps/{step_id}/hold',
      { path: { object_id: objectId, step_id: stepId }, query: { instance, group } });
  }

  /** **Was an diesem Modul passiert ist** – je Einzelinstanz, aus dem Log (`services/record`),
   *  erst auf Klick. */
  stepRecord(objectId: number, stepId: number, limit = 200, offset = 0, req: Req = {}) {
    return this.call('get', '/api/v1/erp/orders/{object_id}/steps/{step_id}/record',
      { path: { object_id: objectId, step_id: stepId }, query: { limit, offset } }, req);
  }

  // Instanz-Feed: Zusammenfassungen, durchsucht und seitenweise auf dem Server.
  getInstances(limit = 0, offset = 0, search = '') {
    return this.call('get', '/api/v1/erp/instances',
      { query: { limit: limit || undefined, offset: offset || undefined, search: search || undefined } });
  }

  // Universelle Objektnummer serverseitig auf ihren Typ auflösen (Scan/Navigation)
  resolveObject(objectId: number) {
    return this.call('get', '/api/v1/erp/objects/{object_id}', { path: { object_id: objectId } });
  }

  /** **Kann diese Objektnummer etwas halten?** 404 ist die Antwort «kein Ort», kein Ausfall. */
  getPlace(objectId: number, req: Req = {}) {
    return this.call('get', '/api/v1/erp/places/{object_id}', { path: { object_id: objectId } }, req);
  }

  /** **Halter suchen** – Nummer oder Name; die eine Quelle jeder Zielort-Eingabe, angeboten
   *  wird nur, was Halter sein kann. */
  searchPlaces(search: string) {
    return this.call('get', '/api/v1/erp/places', { query: { search } });
  }

  getInstance(objectId: number, req?: Req) {
    return this.call('get', '/api/v1/erp/instances/{object_id}', { path: { object_id: objectId } }, req);
  }
}

/** Ein Gespräch des Assistenten, wie das Backend es zurückgibt (auch im Stream von `say`). */
type Talk = Res<'get', '/api/v1/erp/assistant/talks/{talk_id}'>;

export const api = new ApiClient();

// Absolute Anzeige-URL für ein Attachment (die DB speichert nur den relativen Token-Pfad).
export function attachmentUrl(path: string): string {
  if (!path) return path;
  if (/^https?:\/\//.test(path) || path.startsWith('data:')) return path;
  return `${API_BASE}${path}`;
}

/** Die Zeilen eines NDJSON-Streams, je eine als JSON (Leerzeilen = Lebenszeichen). */
async function* ndjson(body: ReadableStream<Uint8Array>): AsyncGenerator<unknown> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let rest = '';
  for (;;) {
    const { value, done } = await reader.read();
    rest += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const lines = rest.split('\n');
    rest = lines.pop() ?? '';
    for (const l of lines) if (l.trim()) yield JSON.parse(l);
    if (done) break;
  }
  if (rest.trim()) yield JSON.parse(rest);
}
