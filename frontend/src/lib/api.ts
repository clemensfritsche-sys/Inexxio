import type {
  Order,
  OrderSummary,
  OrderDraft,
  OrderValidation,
  VoucherCorrectable,
  VoucherParty,
  UnitChoices,
  ArticleOption,
  OrderUnitPage,
  ArticleProcess,
  InstanceSummary,
  ArticleValidation,
  ModuleCatalog,
  Article,
  Message, MessageIn, MessageChannel, HistoryPage, Mailbox, Todo, NewsletterState, PaymentRow,
  TimeView, TimeEntryIn, EntryPreview, TimeContractIn, CompanyTimeView, HolidayOut, HolidayIn, TimeRulesIn,
  ArticleInput,
  ArticleNameSuggestion,
  Instance,
  ArticleStock,
  UnitPage,
  Genealogy,
  StepRecord,
  CompanySettings,
  CompanyRef,
  AddressInput,
  PersonCreate,
  UserProfile,
  UserProfileUpdate,
  ErpAdminUpdate,
  TerritoryMap,
  Passkey,
  PlaceRef,
  PaymentSetup,
  TransferInfo,
  DocumentSummary, DocumentDetail, DocumentProposal, DocumentTarget, RecordRef,
  CompanySettingsUpdate, PublicDocument, LegalText, VoucherPapers, ComposeResult, UploadResult,
  Talk, TalkFile, Handgriff, HandgriffOperation, HandgriffRun, HandgriffProbe, Pinned, Recording,
} from '@/types';
import type {
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
  RegistrationResponseJSON,
  AuthenticationResponseJSON,
} from '@simplewebauthn/browser';
import { DATA_CHANGED } from '@/lib/feed';

/** Ein Fehler der API – mit **Status** und dem rohen `detail`; `message` ist der lesbare Text. */
export class ApiError extends Error {
  status: number;
  detail?: unknown;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
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

/** Der gezeigte Monat der Zeiterfassung als Query («month=2026-10»), leer = der aktuelle. */
const monthQuery = (month?: string) => (month ? `month=${month}` : '');

/** Das Signal, mit dem React Query eine überholte Anfrage abbricht. */
export interface Req { signal?: AbortSignal }

function aborted(options: RequestInit): boolean {
  return !!options.signal?.aborted;
}

/**
 * **«Ich habe Daten geändert» – an EINER Stelle gesagt**: nach jeder erfolgreichen Anfrage,
 * die kein GET ist. Der Feed (`lib/feed.ts`) invalidiert, was der **Pfad** betrifft.
 */
function notifyDataChanged(path: string) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(DATA_CHANGED, { detail: { path } }));
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
  private me: { at: number; promise: Promise<UserProfile> } | null = null;

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
    let lastError: Error = new Error('Keine Verbindung zum Server');
    let refreshed = false;   // Token-Erneuerung: höchstens EINMAL je Anfrage

    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      let response: Response;
      try {
        response = await fetch(`${API_BASE}${path}`, { ...options, headers });
      } catch (e) {
        if (aborted(options)) throw e;
        lastError = new Error('Keine Verbindung zum Server');
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

  /** Fehler mit **Struktur**: `message` lesbar, dazu das JSON-`detail` für Oberflächen, die
   *  mit dem Fehler weiterarbeiten. */
  private async apiError(response: Response): Promise<ApiError> {
    const body = (await response.clone().json().catch(() => null)) as { detail?: unknown } | null;
    const err = new ApiError(await this.errorMessage(response), response.status) ;
    err.detail = body?.detail;
    return err;
  }

  private backoff(attempt: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, attempt === 1 ? 500 : 1200));
  }

  // Bevorzugt das JSON-`detail` der API, sonst der HTTP-Status.
  private async errorMessage(response: Response): Promise<string> {
    const body = (await response.clone().json().catch(() => null)) as
      { detail?: unknown; error?: string } | null;
    const detail = body?.detail;
    if (typeof detail === 'string') return detail;
    // Strukturiertes Detail: die lesbare Meldung steckt unter `message`.
    if (detail && typeof detail === 'object' && typeof (detail as { message?: unknown }).message === 'string') {
      return (detail as { message: string }).message;
    }
    if (Array.isArray(detail)) {
      return detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join('; ');
    }
    if (body?.error) return body.error;
    return response.status >= 500
      ? `Server nicht erreichbar (HTTP ${response.status})`
      : `HTTP ${response.status}`;
  }

  get<T>(path: string, req: Req = {}) {
    return this.request<T>(path, { signal: req.signal });
  }

  post<T>(path: string, body: unknown, req: Req = {}) {
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(body), signal: req.signal });
  }

  patch<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
  }

  put<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'PUT', body: JSON.stringify(body) });
  }

  delete<T>(path: string) {
    return this.request<T>(path, { method: 'DELETE' });
  }

  // ─── Auth / Profile ────────────────────────────────────────────────────────

  getMe(): Promise<UserProfile> {
    if (this.me && Date.now() - this.me.at < ME_TTL) return this.me.promise;
    const entry = { at: Date.now(), promise: this.get<UserProfile>('/api/v1/auth/me') };
    this.me = entry;
    entry.promise.catch(() => { if (this.me === entry) this.me = null; });
    return entry.promise;
  }

  updateMe(data: UserProfileUpdate): Promise<UserProfile> {
    return this.patch('/api/v1/auth/me', data);
  }

  /** Darf die Anmelde-E-Mail auf diese Adresse wechseln? Wirft den Grund (409), sonst nichts. */
  async checkMyEmail(email: string): Promise<void> {
    await this.post('/api/v1/auth/me/email-check', { email });
  }

  // ─── Das Adressbuch – im Konto die eigene Person, im ERP ein Datensatz ──────
  // `services/address_book`; die Antwort ist jedes Mal der ganze Benutzer.

  /** `null` = die eigene Person (Konto), sonst die Objektnummer (ERP). */
  addAddress(owner: number | null, data: AddressInput): Promise<UserProfile> {
    return this.post(this.addressBase(owner), data);
  }

  changeAddress(owner: number | null, id: number, data: AddressInput): Promise<UserProfile> {
    return this.patch(`${this.addressBase(owner)}/${id}`, data);
  }

  removeAddress(owner: number | null, id: number): Promise<UserProfile> {
    return this.delete(`${this.addressBase(owner)}/${id}`);
  }

  private addressBase(owner: number | null): string {
    return owner == null ? '/api/v1/auth/me/addresses' : `/api/v1/erp/records/${owner}/addresses`;
  }

  // ─── Passkeys (WebAuthn/FIDO2) ──────────────────────────────────────────────
  // Registrierung/Verwaltung setzen eine Anmeldung voraus; die Anmeldung per
  // Passkey selbst ist unauthentifiziert und liefert einen Firebase Custom Token.
  passkeyRegisterOptions(): Promise<PublicKeyCredentialCreationOptionsJSON> {
    return this.post('/api/v1/auth/passkeys/register/options', {});
  }

  passkeyRegisterVerify(
    credential: RegistrationResponseJSON,
    deviceName?: string,
  ): Promise<Passkey> {
    return this.post('/api/v1/auth/passkeys/register/verify', {
      credential,
      device_name: deviceName ?? null,
    });
  }

  listPasskeys(): Promise<Passkey[]> {
    return this.get('/api/v1/auth/passkeys');
  }

  deletePasskey(id: number): Promise<void> {
    return this.delete(`/api/v1/auth/passkeys/${id}`);
  }

  passkeyLoginOptions(): Promise<PublicKeyCredentialRequestOptionsJSON> {
    return this.post('/api/v1/auth/passkeys/login/options', {});
  }

  passkeyLoginVerify(credential: AuthenticationResponseJSON): Promise<{ firebase_token: string }> {
    return this.post('/api/v1/auth/passkeys/login/verify', { credential });
  }

  // ─── Öffentlich: die Seite eines Dokuments (`/dokument?t=…`) und die AGB (`/agb`) ──
  // Ohne Anmeldung: der unerratbare Link IST die Berechtigung (`routers/public_documents.py`). Ist
  // jemand angemeldet, reist sein Token mit – die Routen fragen nicht danach.

  /** **Ein Dokument über seinen Link** – das eingefrorene Papier, der Weg, die Handlungen. */
  publicDocument(token: string): Promise<PublicDocument> {
    return this.get(`/api/v1/public/document/${encodeURIComponent(token)}`);
  }

  signDocument(token: string, image: string): Promise<PublicDocument> {
    return this.post(`/api/v1/public/document/${encodeURIComponent(token)}/sign`, { image });
  }

  declineDocument(token: string, reason: string): Promise<PublicDocument> {
    return this.post(`/api/v1/public/document/${encodeURIComponent(token)}/decline`, { reason });
  }

  /** **Die Offerte annehmen** – als die Partei eines Belegs; die Antwort ist die neue Ansicht. */
  agreeDocument(token: string): Promise<PublicDocument> {
    return this.post(`/api/v1/public/document/${encodeURIComponent(token)}/agree`, {});
  }

  /** **Die Offerte ablehnen** – als die Partei; die Antwort ist die neue Ansicht. */
  rejectDocument(token: string): Promise<PublicDocument> {
    return this.post(`/api/v1/public/document/${encodeURIComponent(token)}/reject`, {});
  }

  /** **Mit Karte bezahlen** – die Zahlungsabsicht über den offenen Betrag (wie
   *  `prepareVoucherPayment`); gebucht wird vom Webhook. */
  prepareDocumentPayment(token: string): Promise<PaymentSetup> {
    return this.post(`/api/v1/public/document/${encodeURIComponent(token)}/payment`, {});
  }

  /** **Ein Rechtstext, wie er heute gilt** (AGB · Datenschutz · Impressum) – als A4-Dokument. */
  publicLegal(kind: 'agb' | 'datenschutz' | 'impressum'): Promise<LegalText> {
    return this.get(`/api/v1/public/legal/${kind}`);
  }

  // ─── Öffentliche Einstellungen ─────────────────────────────────────────────

  /** Der Google-Maps-Schlüssel der Adress-Suche – aus der Deploy-Konfiguration, `null` ohne. */
  getMapsKey(): Promise<string | null> {
    return this.get<{ google_maps_api_key: string | null }>('/api/v1/admin/settings/public')
      .then((s) => s.google_maps_api_key || null);
  }

  // ─── Admin: Unternehmen (Gesellschaften) ───────────────────────────────────
  // Eigene anlegen/ändern nur Admin, fremde jedes Personal; Feldnamen wie im Backend.

  getCompanies(): Promise<CompanySettings[]> {
    return this.get('/api/v1/admin/companies');
  }

  getCompany(objectId: number, req?: Req): Promise<CompanySettings> {
    return this.get(`/api/v1/admin/companies/${objectId}`, req);
  }

  /** Eine Firma anlegen – Name und Rechtsform sind Pflicht; ``is_own`` setzt nur ein Admin. */
  createCompany(data: { company_name: string; legal_form: string; uid_number?: string | null;
                        is_own?: boolean }): Promise<CompanySettings> {
    return this.post('/api/v1/admin/companies', data);
  }

  /** **Welche Firma ist gemeint?** – Vorschläge für das **Personal** (die Tür lässt nur
   *  Personal durch: Kunden nennen ihre Firma über die UID, sie suchen sie nicht). */
  searchCompanies(search: string): Promise<CompanyRef[]> {
    return this.get(`/api/v1/erp/companies?search=${encodeURIComponent(search)}`);
  }

  updateCompany(objectId: number, data: CompanySettingsUpdate): Promise<CompanySettings> {
    return this.patch(`/api/v1/admin/companies/${objectId}`, data);
  }

  /** Diese Gesellschaft zum **Betreiber der Website** machen – genau EINE trägt den Titel. */
  setCompanyOperator(objectId: number): Promise<CompanySettings> {
    return this.post(`/api/v1/admin/companies/${objectId}/operator`, {});
  }

  /** Ein Unternehmen **schliessen** (Soft-Delete; `reopenCompany` macht es rückgängig). */
  deactivateCompany(objectId: number): Promise<CompanySettings> {
    return this.delete(`/api/v1/admin/companies/${objectId}`);
  }

  reopenCompany(objectId: number): Promise<CompanySettings> {
    return this.post(`/api/v1/admin/companies/${objectId}/reopen`, {});
  }

  // ─── Gebiete (Weltkarte: welche Gesellschaft fakturiert welche Region) ─────────
  getTerritories(): Promise<TerritoryMap> {
    return this.get('/api/v1/admin/territories');
  }

  assignTerritory(area: string, companyObjectId: number | null): Promise<TerritoryMap> {
    // `area` = Regions-Code («EUR») ODER ISO-2-Land als Ausnahme («LI»).
    // null bzw. die ohnehin zuständige Gesellschaft = Standard wiederherstellen.
    return this.put(`/api/v1/admin/territories/${area}`, { company_object_id: companyObjectId });
  }

  // ─── ERP Records ──────────────────────────────────────────────────────────

  getErpRecords(): Promise<UserProfile[]> {
    return this.get('/api/v1/erp/records');
  }

  /** Eine Person anlegen – Vorname, Nachname, E-Mail, Rolle; Nummer und Anmeldekonto sofort. */
  createErpRecord(data: PersonCreate): Promise<UserProfile> {
    return this.post('/api/v1/erp/records', data);
  }

  updateErpRecord(objectId: number, data: ErpAdminUpdate): Promise<UserProfile> {
    return this.patch(`/api/v1/erp/records/${objectId}`, data);
  }

  // ─── Der Beleg (Modul «Zahlung») ────────────────────────────────────────────

  /** **Eine Handlung am Beleg** – ein Endpunkt, eine Tabelle (`voucher.VERBS`). */
  updateVoucher(orderObjectId: number, stepId: number,
                body: { action: string } & Record<string, unknown>): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${orderObjectId}/steps/${stepId}/voucher`, body);
  }

  /** **Vorschau → Freigeben**: das Papier, das diese Handlung hinausgäbe – es geschieht nichts. */
  previewVoucher(orderObjectId: number, stepId: number,
                 body: { action: string } & Record<string, unknown>): Promise<VoucherPapers> {
    return this.post(`/api/v1/erp/orders/${orderObjectId}/steps/${stepId}/voucher/preview`, body);
  }

  /** **Ein Anhang einer Nachricht als Datei** – für den Entwurf eines Dokuments. */
  async messageAttachment(messageId: number, index: number, name: string): Promise<File> {
    const blob = await this.request<Blob>(`/api/v1/erp/messages/${messageId}/attachments/${index}`, {}, 'blob');
    return new File([blob], name, { type: blob.type });
  }

  /** **Eine Runde Verfassen** – gespeichert wird nichts. */
  composeDocument(turns: { who: 'user' | 'ai'; text: string }[], current: Record<string, unknown> | null):
    Promise<ComposeResult> {
    return this.post('/api/v1/erp/documents/compose', { turns, current });
  }

  /** **Senden** – je Empfänger ein Link und eine Mail; `sign`: sie sollen unterschreiben. */
  sendDocument(objectId: number, to: number[], sign: boolean, note: string): Promise<DocumentDetail> {
    return this.post(`/api/v1/erp/documents/${objectId}/send`, { to, sign, note });
  }

  /** «Aus Vorlage»: AGB oder Datenschutz einer eigenen Gesellschaft (nur Admin). */
  legalFromTemplate(company: number, kind: 'agb' | 'datenschutz'): Promise<DocumentDetail> {
    return this.post('/api/v1/erp/documents/template', { company, kind });
  }

  /** **Eine Zahlung über den offenen Betrag vorbereiten** (Karte) – ändert am Beleg nichts;
   *  gebucht wird vom Webhook. */
  prepareVoucherPayment(objectId: number, stepId: number): Promise<PaymentSetup> {
    return this.post(
      `/api/v1/erp/orders/${objectId}/steps/${stepId}/voucher/payment`, {});
  }

  /** **Wie man diese Rechnung überweist** – Bankverbindung, Referenz, QR-Rechnung als Bild. */
  voucherTransfer(objectId: number, stepId: number): Promise<TransferInfo> {
    return this.get(
      `/api/v1/erp/orders/${objectId}/steps/${stepId}/voucher/transfer`);
  }

  /**
   * ►►► **Welche Rechnung mindert dieser Beleg?** ◄◄◄ Gesucht über **alle Aufträge** (auf dem
   * Server): eine Gutschrift gehört in den Auftrag, in dem die Ware zurückkommt.
   */
  voucherCorrectable(objectId: number, stepId: number,
                     search = ''): Promise<VoucherCorrectable[]> {
    const q = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : '';
    return this.get(
      `/api/v1/erp/orders/${objectId}/steps/${stepId}/voucher/correctable${q}`);
  }

  /**
   * **Geld zurück – über den Dienst, der es eingezogen hat.** Nur für eine **Karten**-
   * Zahlung: bar und per Überweisung ist die Erstattung eine gewöhnliche negative Zahlung.
   */
  refundVoucherPayment(objectId: number, stepId: number,
                       entryId: number, amount?: string): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${objectId}/steps/${stepId}/voucher/refund`,
      { action: 'refund_online', entry: entryId, ...(amount ? { amount } : {}) });
  }

  /**
   * **Personen suchen** – Nummer, Firma, Name oder E-Mail, ohne Rollenfilter
   * (`people.search`, die eine Personensuche). Gegenpartei eines Belegs, Partner im
   * Editor, Empfänger einer Nachricht.
   */
  searchPeople(search?: string, limit = 20, staff = false): Promise<VoucherParty[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (search?.trim()) params.set('search', search.trim());
    if (staff) params.set('staff', 'true');
    return this.get(`/api/v1/erp/people?${params}`);
  }

  /** **Der Verlauf eines Datensatzes** – eine Seite, die neuesten zuerst; `before` ist der
   *  Cursor der vorigen Seite (`services/history`). */
  history(objectId: number, before?: string, req?: Req): Promise<HistoryPage> {
    const params = new URLSearchParams();
    if (before) params.set('before', before);
    return this.get(`/api/v1/erp/history/${objectId}?${params}`, req);
  }

  createMessage(data: MessageIn): Promise<Message> {
    return this.post('/api/v1/erp/messages', data);
  }

  /** Je Datensatz, was zu tun ist – die Zahl am Symbol in Feed und Kopf. */
  todo(): Promise<Todo[]> {
    return this.get('/api/v1/erp/todo');
  }

  // ─── Phase 5 · Der Assistent: Gespräch, Handgriff, Angeheftet (docs/konzept/phase5-bauplan.md) ──
  /** Wo das Gespräch live läuft – die direkte Adresse des Dienstes (einmal gefragt; leer = hier). */
  private door: Promise<string> | null = null;

  private talkDoor(): Promise<string> {
    this.door ??= this.get<{ url: string }>('/api/v1/erp/assistant/door').then(
      (d) => d.url || API_BASE,
      (e: unknown) => { this.door = null; throw e; });
    return this.door;
  }

  /**
   * ►►► **Dem Assistenten etwas sagen – die Antwort kommt live** (wie bei Claude). ◄◄◄ Ohne `talk`
   * beginnt ein Gespräch (am offenen Datensatz `hint`); ohne Text, aber mit `talk`, antwortet die KI
   * auf das, was dasteht (nach einer Aufnahme). Je Zeile des Streams: `onTalk` (das Gespräch – sofort
   * mit der Nachricht, am Ende mit der Antwort), `onStep` (was die KI gerade tut). Läuft direkt am
   * Dienst – ohne die 60 s des Hostings; begrenzt durch Schritte, Deckel und «Stopp».
   */
  async say(text: string, opts: {
    talk?: number | null; hint?: number | null; files?: TalkFile[];
    onTalk?: (t: Talk) => void; onStep?: (step: string) => void; signal?: AbortSignal;
  } = {}): Promise<Talk> {
    const path = '/api/v1/erp/assistant/talks';
    const body = JSON.stringify({
      text, ...(opts.talk ? { talk: opts.talk } : {}), ...(opts.hint ? { hint_object_id: opts.hint } : {}),
      ...(opts.files?.length ? { files: opts.files } : {}),
    });
    const base = await this.talkDoor();
    let res: Response | null = null;
    for (const force of [false, true]) {
      const token = this.tokenProvider ? await this.tokenProvider(force).catch(() => null) : null;
      res = await fetch(`${base}${path}`, {
        method: 'POST', body, signal: opts.signal,
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (res.status !== 401 || !this.tokenProvider) break;
    }
    if (!res || !res.ok || !res.body) throw res ? await this.apiError(res) : new Error('Keine Verbindung zum Server');
    notifyDataChanged(path);
    let last: Talk | null = null;
    for await (const line of ndjson(res.body)) {
      const item = line as { talk?: Talk; step?: string; error?: string };
      if (item.talk) { last = item.talk; opts.onTalk?.(item.talk); }
      if (item.step) opts.onStep?.(item.step);
      if (item.error) throw new Error(item.error);
    }
    notifyDataChanged(path);
    if (!last) throw new Error('Die Verbindung riss ab – deine Nachricht ist gespeichert.');
    return last;
  }

  /** **Stopp** – die KI hält vor ihrem nächsten Schritt an; was sie vorbereitete, bleibt. */
  stopTalk(id: number): Promise<void> {
    return this.post(`/api/v1/erp/assistant/talks/${id}/stop`, {});
  }

  /** Meine offenen Gespräche – die Zahl am «+». */
  openTalks(req?: Req): Promise<Talk[]> {
    return this.get('/api/v1/erp/assistant/talks/open', req);
  }

  /** Ein Gespräch (nur, wer es führt, und der Admin). */
  talk(id: number, req?: Req): Promise<Talk> {
    return this.get(`/api/v1/erp/assistant/talks/${id}`, req);
  }

  /** Eine Datei (Foto, PDF) ins Gespräch – sie liegt im Korb, bis sie ein Dokument wird. */
  addTalkFile(file: Blob, name: string): Promise<TalkFile> {
    const form = new FormData();
    form.append('file', file, name);
    return this.request('/api/v1/erp/assistant/files', { method: 'POST', body: form });
  }

  /** Eine Datei aus dem Gespräch (im Korb) – für den Dokument-Entwurf. */
  attachmentBlob(token: string): Promise<Blob> {
    return this.request<Blob>(`/api/v1/attachments/${encodeURIComponent(token)}`, {}, 'blob');
  }

  /** Die Handlung hinter einem Handgriff – ihre Felder für «Ändern». */
  handgriffOperation(id: number, req?: Req): Promise<HandgriffOperation> {
    return this.get(`/api/v1/erp/assistant/handgriffe/${id}/operation`, req);
  }

  /** **Ausführen** – genau einmal, mit meinen Rechten; `body` nur mit geänderten Werten. */
  runHandgriff(id: number, body?: unknown): Promise<HandgriffRun> {
    return this.post(`/api/v1/erp/assistant/handgriffe/${id}/run`, body === undefined ? {} : { body });
  }

  /** Eine geänderte Fassung prüfen – der Probelauf derselben Route, nichts bleibt. */
  probeHandgriff(id: number, body: unknown, req?: Req): Promise<HandgriffProbe> {
    return this.post(`/api/v1/erp/assistant/handgriffe/${id}/probe`, { body }, req);
  }

  /** **Weg** – der Handgriff geschieht nicht. */
  dropHandgriff(id: number): Promise<Handgriff> {
    return this.post(`/api/v1/erp/assistant/handgriffe/${id}/drop`, {});
  }

  /** **Von Hand erledigt** (Entwurf freigegeben, Datei abgelegt) – `result` = was entstand. */
  handgriffDone(id: number, result: number | null): Promise<Handgriff> {
    return this.post(`/api/v1/erp/assistant/handgriffe/${id}/done`, { result });
  }

  /** **Das Angeheftete**: offene Handgriffe, dann das Wissen (`stale` = neu wählen lohnt sich). */
  pins(objectId: number, req?: Req): Promise<Pinned> {
    return this.get(`/api/v1/erp/assistant/pins/${objectId}`, req);
  }

  /** Das Wissen neu wählen – nur, wenn sich im Umfeld etwas geändert hat. */
  refreshPins(objectId: number): Promise<Pinned> {
    return this.post(`/api/v1/erp/assistant/pins/${objectId}/refresh`, {});
  }

  // ─── Phase 4 · Sprache: Aufnehmen (docs/konzept/phase4-bauplan.md) ─────────
  /** Eine Aufnahme beginnen – `hint` = der Datensatz, der dabei offen war; `context` = die
   *  Stecknadel («Stelle: …»), sie steht später vor dem abgeschriebenen Text; `talk` = das offene
   *  Gespräch, in das der Text geht (wie getippt). */
  startRecording(mime: string, hint?: number | null, context?: string | null, talk?: number | null): Promise<Recording> {
    return this.post('/api/v1/erp/recordings', {
      mime, ...(hint ? { hint_object_id: hint } : {}), ...(context ? { context } : {}),
      ...(talk ? { talk } : {}),
    });
  }

  /** **Ein Stück** (alle 30 s) – Abschnitt und Stück ab 0; dasselbe Stück noch einmal ersetzt es. */
  recordingChunk(id: number, segment: number, seq: number, file: Blob, req?: Req): Promise<Recording> {
    const form = new FormData();
    form.append('segment', String(segment));
    form.append('seq', String(seq));
    form.append('file', file, `${segment}-${seq}`);
    return this.request(`/api/v1/erp/recordings/${id}/chunks`, { method: 'POST', body: form, signal: req?.signal });
  }

  /** **Stopp** – `segments` = wie viele Abschnitte es gibt. */
  stopRecording(id: number, segments: number): Promise<Recording> {
    return this.post(`/api/v1/erp/recordings/${id}/stop`, { segments });
  }

  /** **Weiter abschreiben** – so weit es in einer Anfrage geht (≤ 60 s); dann wieder fragen. */
  advanceRecording(id: number, req?: Req): Promise<Recording> {
    return this.post(`/api/v1/erp/recordings/${id}/advance`, {}, req);
  }

  /** Meine Aufnahmen, die noch nicht fertig sind. */
  openRecordings(req?: Req): Promise<Recording[]> {
    return this.get('/api/v1/erp/recordings/open', req);
  }

  /** **Verwerfen** – eine gescheiterte Aufnahme verschwindet aus dem «+». */
  dismissRecording(id: number): Promise<Recording> {
    return this.post(`/api/v1/erp/recordings/${id}/dismiss`, {});
  }

  // ─── Zahlungen (eine Ableitung aus den Zahlungsmodulen) ────────────────────
  /** **Die Zahlungen einer Person** (`person`) **oder einer eigenen Gesellschaft**
   *  (`company`) – neueste Nummer zuoberst. */
  paymentsOf(scope: { person: number } | { company: number }, req?: Req): Promise<PaymentRow[]> {
    const params = new URLSearchParams();
    if ('person' in scope) params.set('person', String(scope.person));
    else params.set('company', String(scope.company));
    return this.get(`/api/v1/erp/payments?${params}`, req);
  }

  // ─── Zeiterfassung ─────────────────────────────────────────────────────────
  // Jede Schreib-Route antwortet mit der neuen Ansicht des gezeigten Monats.

  timeView(person: number, month?: string): Promise<TimeView> {
    return this.get(`/api/v1/erp/time/${person}?${monthQuery(month)}`);
  }

  timeSwipe(person: number, direction: 'in' | 'out', key: string, month?: string): Promise<TimeView> {
    return this.post(`/api/v1/erp/time/${person}/swipe?${monthQuery(month)}`, { direction, key });
  }

  timeEntry(person: number, data: TimeEntryIn, month?: string): Promise<TimeView> {
    return this.post(`/api/v1/erp/time/${person}/entries?${monthQuery(month)}`, data);
  }

  /** Was ein Eintrag bewirken würde – dieselbe Regel wie beim Speichern, ohne zu schreiben. */
  timePreview(person: number, data: TimeEntryIn, req?: Req): Promise<EntryPreview> {
    return this.post(`/api/v1/erp/time/${person}/entries/preview`, data, req);
  }

  timeContract(person: number, data: TimeContractIn, month?: string): Promise<TimeView> {
    return this.post(`/api/v1/erp/time/${person}/contracts?${monthQuery(month)}`, data);
  }

  companyTime(company: number, year?: number): Promise<CompanyTimeView> {
    return this.get(`/api/v1/erp/time/companies/${company}?${year ? `year=${year}` : ''}`);
  }

  holidayProposal(company: number, year: number): Promise<HolidayOut[]> {
    return this.get(`/api/v1/erp/time/companies/${company}/proposal?year=${year}`);
  }

  addHolidays(company: number, holidays: HolidayIn[], year: number): Promise<CompanyTimeView> {
    return this.post(`/api/v1/erp/time/companies/${company}/holidays?year=${year}`, { holidays });
  }

  removeHoliday(company: number, id: number, year: number): Promise<CompanyTimeView> {
    return this.delete(`/api/v1/erp/time/companies/${company}/holidays/${id}?year=${year}`);
  }

  setTimeRules(company: number, data: TimeRulesIn, year: number): Promise<CompanyTimeView> {
    return this.put(`/api/v1/erp/time/companies/${company}/rules?year=${year}`, data);
  }

  messageChannels(req?: Req): Promise<MessageChannel[]> {
    return this.get('/api/v1/erp/messages/channels', req);
  }

  /** Das Postfach einer eigenen Gesellschaft – Adresse, Zustand, darf ich verbinden?
   *  Persönliche Postfächer gibt es nicht. */
  mailboxes(company: number, req?: Req): Promise<Mailbox[]> {
    return this.get(`/api/v1/erp/messages/mailboxes?company=${company}`, req);
  }

  /** Die Adresse bei Google, an der die Zustimmung erteilt wird. */
  connectMailbox(channel: string): Promise<{ url: string }> {
    return this.post(`/api/v1/erp/messages/mailboxes/${channel}/connect`, {});
  }

  disconnectMailbox(channel: string): Promise<void> {
    return this.delete(`/api/v1/erp/messages/mailboxes/${channel}`);
  }

  /** Postfächer abgleichen und Fälliges senden – der Server drosselt selbst. */
  syncMail(): Promise<{ new: number; sent: number }> {
    return this.post('/api/v1/erp/messages/sync', {});
  }

  // ─── Newsletter ────────────────────────────────────────────────────────────

  /** Mein Newsletter – angemeldet oder nicht, und der Satz, dem ich zustimme. */
  myNewsletter(): Promise<NewsletterState> {
    return this.get('/api/v1/auth/me/newsletter');
  }

  setMyNewsletter(subscribed: boolean): Promise<NewsletterState> {
    return this.put('/api/v1/auth/me/newsletter', { subscribed });
  }

  /** Zustand und Nachweis einer Person (ERP). */
  personNewsletter(objectId: number, req?: Req): Promise<NewsletterState> {
    return this.get(`/api/v1/erp/newsletter/${objectId}`, req);
  }

  /** Die Bitte um Bestätigung schicken – anmelden kann das ERP niemanden. */
  inviteNewsletter(objectId: number): Promise<NewsletterState> {
    return this.post(`/api/v1/erp/newsletter/${objectId}/invite`, {});
  }

  unsubscribeNewsletter(objectId: number): Promise<NewsletterState> {
    return this.post(`/api/v1/erp/newsletter/${objectId}/unsubscribe`, {});
  }

  // ─── ERP Articles ──────────────────────────────────────────────────────────

  /** Der Artikel-Feed; `search` sucht im Namen. */
  getArticles(search?: string, limit?: number): Promise<Article[]> {
    const params = new URLSearchParams();
    if (search?.trim()) params.set('search', search.trim());
    if (limit) params.set('limit', String(limit));
    const q = params.toString();
    return this.get(`/api/v1/erp/articles${q ? `?${q}` : ''}`);
  }

  getArticle(objectId: number, req?: Req): Promise<Article> {
    return this.get(`/api/v1/erp/articles/${objectId}`, req);
  }

  /** Wäre dieser Artikel-Entwurf freigebbar? Legt nichts an und zieht keine Nummer –
   *  dieselbe Regel, die auch die Anlage prüft (services/articles.validate_draft). */
  validateArticle(draft: unknown, req?: Req): Promise<ArticleValidation> {
    return this.post('/api/v1/erp/articles/validate', draft, req);
  }

  /** Anlegen **ist** Freigeben: Spezifikation UND Erzeugungsprozess in einem Aufruf –
   *  erst dabei entsteht der Datensatz und seine Objektnummer. */
  createArticle(data: ArticleInput): Promise<Article> {
    return this.post('/api/v1/erp/articles', data);
  }

  // Namensvorschläge gegen Dubletten; leer → die häufigsten bestehenden Namen.
  articleNameSuggestions(q: string, limit = 8): Promise<ArticleNameSuggestion[]> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return this.get(`/api/v1/erp/articles/name-suggestions?${params.toString()}`);
  }

  // ─── Dokumente (`services/documents`) ───────────────────────────────────────
  /** Der Feed «Dokument» – seitenweise, durchsucht auf dem Server (wie die Instanzen). */
  getDocuments(q = '', limit = 100, offset = 0): Promise<DocumentSummary[]> {
    const p = new URLSearchParams({ q, limit: String(limit), offset: String(offset) });
    return this.get(`/api/v1/erp/documents?${p}`);
  }

  getDocument(objectId: number, req?: Req): Promise<DocumentDetail> {
    return this.get(`/api/v1/erp/documents/${objectId}`, req);
  }

  /** Die Kacheln unten an einem Datensatz. */
  documentsOf(objectId: number, req?: Req): Promise<DocumentSummary[]> {
    return this.get(`/api/v1/erp/documents/of/${objectId}`, req);
  }

  /** Ein Datensatz für eine Referenz – Nummer ODER Name. */
  documentTargets(q: string): Promise<RecordRef[]> {
    return this.get(`/api/v1/erp/documents/targets?${new URLSearchParams({ q })}`);
  }

  /** **Einen Entwurf lesen** – nichts wird gespeichert. */
  readDraft(files: Blob[], opts: { sender?: number | null; hint?: string } = {}): Promise<DocumentProposal> {
    const form = new FormData();
    files.forEach((f, i) => form.append('files', f, f instanceof File ? f.name : `seite-${i + 1}`));
    if (opts.sender) form.append('sender', String(opts.sender));
    if (opts.hint) form.append('hint', opts.hint);
    return this.request('/api/v1/erp/documents/read', { method: 'POST', body: form });
  }

  /** **Freigeben** – das Dokument entsteht erst hier (eine Datei oder mehrere Seiten). */
  fileDocument(files: Blob[], data: {
    art: string; name: string; source: string; refs: number[];
    target?: DocumentTarget | null; text?: string; keywords?: string; facts?: Record<string, unknown>;
    /** Wer unterschreiben soll (Personen). */
    signers?: number[];
  }): Promise<{ document: DocumentDetail; existed: boolean }> {
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
    return this.request('/api/v1/erp/documents', { method: 'POST', body: form });
  }

  addDocumentRef(objectId: number, target: number): Promise<DocumentDetail> {
    return this.post(`/api/v1/erp/documents/${objectId}/refs`, { object_id: target });
  }

  removeDocumentRef(objectId: number, refId: number): Promise<DocumentDetail> {
    return this.delete(`/api/v1/erp/documents/${objectId}/refs/${refId}`);
  }

  /** Ein schon freigegebenes Dokument in ein Pflichtfeld – ändern, nie leeren. */
  setDocumentField(objectId: number, target: DocumentTarget): Promise<DocumentDetail> {
    return this.post(`/api/v1/erp/documents/${objectId}/field`, target);
  }

  deleteDocument(objectId: number, reason: string): Promise<DocumentDetail> {
    return this.post(`/api/v1/erp/documents/${objectId}/delete`, { reason });
  }

  /** Das Lesen nachholen (ohne KI freigegeben). */
  readDocumentLater(objectId: number): Promise<DocumentDetail> {
    return this.post(`/api/v1/erp/documents/${objectId}/read`, {});
  }

  // ─── Foto-/Bild-Upload (multipart) ──────────────────────────────────────────
  // Gibt eine relative URL (Token) zurück; die speichern die Verbraucher als String.
  async uploadAttachment(file: File): Promise<UploadResult> {
    const token = this.tokenProvider ? await this.tokenProvider(false).catch(() => null) : null;
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/api/v1/erp/attachments`, { method: 'POST', headers, body: form });
    if (!res.ok) throw await this.apiError(res);
    return res.json();
  }

  // Bestand eines Artikels: Aufstellung über ALLE Stücke + eine Seite Instanzen.
  getArticleStock(objectId: number, limit = 50, offset = 0, req?: Req): Promise<ArticleStock> {
    const p = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return this.get(`/api/v1/erp/articles/${objectId}/stock?${p}`, req);
  }

  // Ebene 3: die Nummern der Einzelinstanzen – seitenweise, auf Klick; `statuses` ist eine Menge.
  getInstanceUnits(objectId: number, opts: {
    statuses?: readonly string[]; limit?: number; offset?: number;
  } = {}, req?: Req): Promise<UnitPage> {
    const p = new URLSearchParams();
    (opts.statuses ?? []).forEach((s) => p.append('status', s));
    p.set('limit', String(opts.limit ?? 60));
    p.set('offset', String(opts.offset ?? 0));
    return this.get(`/api/v1/erp/instances/${objectId}/units?${p}`, req);
  }

  /** **Woraus besteht ein Stück – und worin steckt es?** Abgeleitet aus dem Log
   *  (`services/genealogy`); erst auf Klick. */
  getUnitGenealogy(objectId: number, suffix: number, req?: Req): Promise<Genealogy> {
    return this.get(`/api/v1/erp/instances/${objectId}/units/${suffix}/genealogy`, req);
  }

  // ─── Auftrag ───────────────────────────────────────────────────────────────
  // Kein Entwurfs-Endpunkt: der Entwurf lebt im Browser, erst `createOrder` legt ihn an.

  getOrders(limit = 0, offset = 0): Promise<OrderSummary[]> {
    const p = new URLSearchParams();
    if (limit) p.set('limit', String(limit));
    if (offset) p.set('offset', String(offset));
    const qs = p.toString();
    return this.get(`/api/v1/erp/orders${qs ? `?${qs}` : ''}`);
  }

  getOrder(objectId: number, req?: Req): Promise<Order> {
    return this.get(`/api/v1/erp/orders/${objectId}`, req);
  }

  /** Wäre dieser Entwurf speicherbar? Dieselbe Regel wie beim Anlegen, legt nichts an. */
  validateOrder(draft: OrderDraft, req?: Req): Promise<OrderValidation> {
    return this.post('/api/v1/erp/orders/validate', draft, req);
  }

  /** Anlegen **ist** Freigeben: ein Aufruf, eine Transaktion – der Auftrag entsteht,
   *  bekommt seine Nummer, die Stücke passieren das Start-Objekt (PROCESS_CORE.md §6.3). */
  createOrder(draft: OrderDraft): Promise<Order> {
    return this.post('/api/v1/erp/orders', draft);
  }

  /** **Die Wiederholung beenden** – nur am neuesten Auftrag der Kette (`services/loop.end`). */
  endLoop(objectId: number): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${objectId}/loop/end`, {});
  }

  /** **Eine Seite wählbarer Einzelinstanzen** – Gesperrte kommen mit (die Oberfläche nennt
   *  den Grund). `preselect`: die FIFO-Vorauswahl rechnet der Server, nie eine gekappte Seite. */
  getUnitOptions(opts: {
    articleObjectId?: number; search?: string; status?: string[];
    preselect?: number; limit?: number; offset?: number;
  } = {}, req?: Req): Promise<UnitChoices> {
    const p = new URLSearchParams();
    if (opts.articleObjectId) p.set('article', String(opts.articleObjectId));
    if (opts.search?.trim()) p.set('search', opts.search.trim());
    (opts.status ?? []).forEach((s) => p.append('status', s));
    if (opts.preselect) p.set('preselect', String(opts.preselect));
    if (opts.limit) p.set('limit', String(opts.limit));
    if (opts.offset) p.set('offset', String(opts.offset));
    const q = p.toString();
    return this.get(`/api/v1/erp/orders/unit-options${q ? `?${q}` : ''}`, req);
  }

  /** Welche Artikel kann eine Definitionszeile aufnehmen? **Gesucht, nicht geladen** –
   *  passend zur Eingabe oder genau der gewählte (`objectId`). */
  getArticleOptions(opts: { search?: string; objectId?: number; limit?: number } = {}):
    Promise<ArticleOption[]> {
    const p = new URLSearchParams();
    if (opts.objectId != null) p.set('object_id', String(opts.objectId));
    else if (opts.search?.trim()) p.set('search', opts.search.trim());
    if (opts.limit) p.set('limit', String(opts.limit));
    const q = p.toString();
    return this.get(`/api/v1/erp/orders/article-options${q ? `?${q}` : ''}`);
  }

  /** Die Stücke **einer Kante** des Prozessbildes – erst beim Aufklappen. */
  getOrderUnits(objectId: number, edge: string,
                limit = 100, offset = 0): Promise<OrderUnitPage> {
    const p = new URLSearchParams({ edge, limit: String(limit), offset: String(offset) });
    return this.get(`/api/v1/erp/orders/${objectId}/units?${p.toString()}`);
  }

  // ─── Erzeugungsprozess des Artikels (Vorlage) ──────────────────────────────
  // Die Vorlage führt nichts aus und hat keinen Schreib-Endpunkt (entsteht mit dem Artikel).

  getArticleProcess(objectId: number, req?: Req): Promise<ArticleProcess> {
    return this.get(`/api/v1/erp/articles/${objectId}/process`, req);
  }

  /** Was sich modellieren lässt – Modultypen und Erfassungspunkt-Typen, vom Backend. */
  getModuleCatalog(): Promise<ModuleCatalog> {
    return this.get('/api/v1/erp/orders/module-catalog');
  }

  /**
   * «Bestätigen» – der eine Ausführungs-Endpunkt, **für genau eine Instanz**. `values`:
   * Nummer der Einzelinstanz → (Punkt-`key` → Wert); `verification` = `scan` | `manual`.
   */
  confirmStep(objectId: number, stepId: number, values: Record<string, Record<string, unknown>> = {},
              instanceObjectId?: number | null, verification?: string,
              sources: number[] = [], place: number | null = null): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${objectId}/steps/${stepId}/confirm`, {
      values,
      instance_object_id: instanceObjectId ?? null,
      verification: verification ?? null,
      // Woraus verbaut wird; leer = der freie Bestand, älteste zuerst.
      sources,
      // Wohin bewegt wurde: Verifikation eines festen Ziels, sonst die Wahl.
      place,
    });
  }

  /**
   * Die Nummern **einer Gruppe dieser Instanz an diesem Modul** – erst auf Klick.
   * `sample` = die gezogenen (je ein Wertesatz); `failed`/`rest` = Vorauswahl nach «nicht bestanden».
   */
  stepHold(objectId: number, stepId: number, instance: number,
           group: 'sample' | 'failed' | 'rest'): Promise<{ numbers: string[] }> {
    return this.get(
      `/api/v1/erp/orders/${objectId}/steps/${stepId}/hold`
      + `?instance=${instance}&group=${group}`);
  }

  /** **Was an diesem Modul passiert ist** – je Einzelinstanz, aus dem Log (`services/record`),
   *  erst auf Klick. */
  stepRecord(objectId: number, stepId: number, limit = 200, offset = 0): Promise<StepRecord> {
    return this.get(
      `/api/v1/erp/orders/${objectId}/steps/${stepId}/record`
      + `?limit=${limit}&offset=${offset}`);
  }

  // Instanz-Feed: Zusammenfassungen, durchsucht und seitenweise auf dem Server.
  getInstances(limit = 0, offset = 0, search = ''): Promise<InstanceSummary[]> {
    const p = new URLSearchParams();
    if (limit) p.set('limit', String(limit));
    if (offset) p.set('offset', String(offset));
    if (search) p.set('search', search);
    const qs = p.toString();
    return this.get(`/api/v1/erp/instances${qs ? `?${qs}` : ''}`);
  }

  // Universelle Objektnummer serverseitig auf ihren Typ auflösen (Scan/Navigation)
  resolveObject(objectId: number): Promise<{ object_id: number; object_type: string }> {
    return this.get(`/api/v1/erp/objects/${objectId}`);
  }

  /** **Kann diese Objektnummer etwas halten?** 404 ist die Antwort «kein Ort», kein Ausfall. */
  getPlace(objectId: number): Promise<PlaceRef> {
    return this.get(`/api/v1/erp/places/${objectId}`);
  }

  /** **Halter suchen** – Nummer oder Name; die eine Quelle jeder Zielort-Eingabe, angeboten
   *  wird nur, was Halter sein kann. */
  searchPlaces(query: string): Promise<PlaceRef[]> {
    return this.get(`/api/v1/erp/places?search=${encodeURIComponent(query)}`);
  }

  getInstance(objectId: number, req?: Req): Promise<Instance> {
    return this.get(`/api/v1/erp/instances/${objectId}`, req);
  }
}

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
