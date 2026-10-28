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
  Message, MessageIn, MessageChannel, Mailbox, Todo, NewsletterState, PaymentRow,
  TimeView, TimeEntryIn, EntryPreview, TimeContractIn, CompanyTimeView, HolidayOut, HolidayIn, TimeRulesIn,
  ArticleInput,
  ArticleNameSuggestion,
  Instance,
  ArticleStock,
  UnitPage,
  Genealogy,
  StepRecord,
  CompanySettings,
  CompanyPerson,
  CompanyRef,
  AddressInput,
  PersonCreate,
  UserProfile,
  TerritoryMap,
  Passkey,
  FeedbackNote,
  FeedbackCreateInput,
  FeedbackUpdateInput,
  PlaceRef,
  PaymentSetup,
  TransferInfo,
  DocumentSummary, DocumentDetail, DocumentProposal, DocumentTarget, DocumentRequirement, RecordRef,
} from '@/types';
import type {
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
  RegistrationResponseJSON,
  AuthenticationResponseJSON,
} from '@simplewebauthn/browser';

/**
 * Ein Fehler der API – mit **Status** und dem rohen `detail`. `message` bleibt der lesbare
 * Text (jede bestehende Aufrufstelle liest ihn unverändert weiter).
 */
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

/** **Eine Datei des Servers** (`/api/v1/…`, z. B. ein Dokument oder sein Vorschaubild) –
 *  im Betrieb dieselbe Herkunft, lokal das Backend. Die eine Stelle, die die Basis kennt. */
export function assetUrl(path: string): string {
  return path.startsWith('/api/') ? `${API_BASE}${path}` : path;
}

/** Der gezeigte Monat der Zeiterfassung als Query («month=2026-10»), leer = der aktuelle. */
const monthQuery = (month?: string) => (month ? `month=${month}` : '');

/**
 * **«Ich habe Daten geändert» – an EINER Stelle gesagt** (Testnotizen #685/#688).
 *
 * Der ERP-Feed hört auf `inexxio:data-changed` und lädt dann nach. Gefeuert wird nach
 * **jeder erfolgreichen Anfrage, die kein GET ist** – so kann ein Aufrufer es nicht
 * vergessen, und ein zweiter Melde-Weg kann nicht entstehen.
 *
 * Ausgenommen sind die **Testnotizen**: sie sind keine ERP-Daten, und beim Anheften
 * einer Notiz vier Feed-Abfragen auszulösen wäre Arbeit ohne Ertrag.
 */
function notifyDataChanged(path: string) {
  if (typeof window === 'undefined') return;
  if (path.startsWith('/api/v1/feedback')) return;
  window.dispatchEvent(new CustomEvent('inexxio:data-changed'));
}

class ApiClient {
  /**
   * **Jede Methode ist an ihren Client gebunden** (Testnotiz #927): eine Methode, die als
   * **Wert** weitergereicht wird (`search={api.searchPeople}`), behält ihr `this`.
   * Ohne das warf `this.get`, und das Suchfeld blieb stumm. Gebunden wird über den
   * **Prototyp**, nicht über eine Namensliste – die vergässe den nächsten Endpunkt.
   */
  constructor() {
    const proto = Object.getPrototypeOf(this) as object;
    for (const name of Object.getOwnPropertyNames(proto)) {
      if (name === 'constructor') continue;
      // Über den **Deskriptor**, nicht über den Zugriff: ein `get foo()` würde beim
      // blossen Lesen ausgeführt – hier gibt es keinen, und genau darum darf es auch
      // später keinen Unfall geben.
      const desc = Object.getOwnPropertyDescriptor(proto, name);
      if (typeof desc?.value === 'function') {
        (this as unknown as Record<string, unknown>)[name] = desc.value.bind(this);
      }
    }
  }

  private token: string | null = null;
  /**
   * Liefert einen **frischen** Token (Firebase erneuert bei Bedarf selbst). Wird von der
   * Auth-Schicht registriert, damit `api.ts` frei von Firebase-Abhängigkeiten bleibt.
   *
   * Hintergrund: `token` ist ein Schnappschuss vom letzten `onIdTokenChanged`. Firebase
   * erneuert proaktiv per Timer – der wird in einem **Hintergrund-Tab gedrosselt** und im
   * Ruhezustand des Geräts gar nicht ausgeführt. Kommt der Nutzer nach längerer Pause
   * zurück, ist der Schnappschuss abgelaufen → jede Anfrage 401. Genau dafür ist das hier.
   */
  private tokenProvider: (() => Promise<string | null>) | null = null;

  setToken(token: string) {
    this.token = token;
  }

  setTokenProvider(fn: () => Promise<string | null>) {
    this.tokenProvider = fn;
  }

  // Transiente Transportfehler (Kaltstart / Skalierung / kurz nach einem Deploy)
  // äussern sich als 502/503 oder als abgewiesene Verbindung – die Anfrage
  // erreicht die App dann GAR NICHT und wird kurz erneut versucht (auch
  // schreibende, da der Server sie nie verarbeitet hat → keine Doppelanlage).
  // 500/504 hingegen nur bei LESENDEN (idempotenten) Anfragen wiederholen.
  private async request<T>(path: string, options: RequestInit = {}, as: 'json' | 'blob' = 'json'): Promise<T> {
    // (Der Erfolgspfad unten meldet die Änderung – siehe ``notifyDataChanged``.)
    // Eine Datei geht als `FormData` – den Typ samt Grenze setzt dann der Browser selbst.
    const headers: Record<string, string> = {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...((options.headers as Record<string, string>) || {}),
    };
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

    const method = (options.method ?? 'GET').toUpperCase();
    const idempotent = method === 'GET' || method === 'HEAD';
    const MAX_ATTEMPTS = 3;
    let lastError: Error = new Error('Keine Verbindung zum Server');
    let refreshed = false;   // Token-Erneuerung: höchstens EINMAL je Anfrage

    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      let response: Response;
      try {
        response = await fetch(`${API_BASE}${path}`, { ...options, headers });
      } catch {
        // Keine Antwort erhalten → Anfrage kam nicht an, sicher wiederholbar.
        lastError = new Error('Keine Verbindung zum Server');
        if (attempt < MAX_ATTEMPTS) { await this.backoff(attempt); continue; }
        throw lastError;
      }

      if (response.ok) {
        if (!idempotent) notifyDataChanged(path);
        if (response.status === 204) return {} as T;
        return (as === 'blob' ? response.blob() : response.json()) as Promise<T>;
      }

      // 401 = Token abgelaufen (typisch nach längerer Pause / Ruhezustand). EINMAL einen
      // frischen Token holen und dieselbe Anfrage wiederholen, statt den Fehler nach oben
      // zu geben (wo er bisher als «keine Daten» endete). Kostet im Normalfall NICHTS –
      // der Pfad läuft nur, wenn tatsächlich ein 401 kam.
      if (response.status === 401 && !refreshed && this.tokenProvider) {
        refreshed = true;
        const fresh = await this.tokenProvider().catch(() => null);
        if (fresh) {
          this.token = fresh;
          headers['Authorization'] = `Bearer ${fresh}`;
          continue;   // zählt als Versuch – kein Backoff nötig, der Server war erreichbar
        }
      }

      const retriable = response.status === 502 || response.status === 503
        || (idempotent && response.status >= 500);
      if (retriable && attempt < MAX_ATTEMPTS) {
        lastError = new Error(`Server nicht erreichbar (HTTP ${response.status})`);
        await this.backoff(attempt);
        continue;
      }
      throw await this.apiError(response);
    }
    throw lastError;
  }

  /**
   * Fehler mit **Struktur**: die Meldung bleibt der `Error.message` (jede Aufrufstelle liest
   * ihn unverändert), das JSON-`detail` hängt zusätzlich daran. Gebraucht dort, wo die
   * Oberfläche mit dem Fehler weiterarbeitet statt ihn nur anzuzeigen – etwa bei der
   * Unterdeckungs-Frage, die die betroffenen Aufträge benennt (Notizen #386/#387).
   */
  private async apiError(response: Response): Promise<ApiError> {
    const body = (await response.clone().json().catch(() => null)) as { detail?: unknown } | null;
    const err = new ApiError(await this.errorMessage(response), response.status) ;
    err.detail = body?.detail;
    return err;
  }

  private backoff(attempt: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, attempt === 1 ? 500 : 1200));
  }

  // Fehlermeldung aufbereiten: bevorzugt das JSON-`detail` der API, sonst der
  // echte HTTP-Status (statt eines undurchsichtigen «Netzwerkfehler»).
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

  get<T>(path: string) {
    return this.request<T>(path);
  }

  post<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(body) });
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
    return this.get('/api/v1/auth/me');
  }

  updateMe(data: Partial<UserProfile>): Promise<UserProfile> {
    return this.patch('/api/v1/auth/me', data);
  }

  /** Darf die Anmelde-E-Mail auf diese Adresse wechseln? Wirft den Grund (409), sonst nichts. */
  async checkMyEmail(email: string): Promise<void> {
    await this.post('/api/v1/auth/me/email-check', { email });
  }

  // ─── Das Adressbuch – im Konto die eigene Person, im ERP ein Datensatz ──────
  // Dieselben Funktionen im Dienst (`services/address_book`); die Antwort ist jedes Mal
  // der ganze Benutzer, damit kein Aufrufer eine Liste nachführen muss.

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

  // ─── Öffentlich: die Seite eines Belegs (`/beleg?t=…`) und die AGB (`/agb`) ──
  // Ohne Anmeldung: der unerratbare Link IST die Berechtigung (`routers/beleg.py`). Ist
  // jemand angemeldet, reist sein Token mit – die Routen fragen nicht danach.

  /** **Ein Dokument über seinen Link** – das eingefrorene Papier, der Weg, die Handlungen. */
  publicBeleg(token: string): Promise<import('@/types/api').components['schemas']['BelegView']> {
    return this.get(`/api/v1/public/beleg/${encodeURIComponent(token)}`);
  }

  /** **Die Offerte annehmen** – als die Partei; die Antwort ist die neue Ansicht. */
  acceptBeleg(token: string): Promise<import('@/types/api').components['schemas']['BelegView']> {
    return this.post(`/api/v1/public/beleg/${encodeURIComponent(token)}/accept`, {});
  }

  /** **Die Offerte ablehnen** – als die Partei; die Antwort ist die neue Ansicht. */
  declineBeleg(token: string): Promise<import('@/types/api').components['schemas']['BelegView']> {
    return this.post(`/api/v1/public/beleg/${encodeURIComponent(token)}/decline`, {});
  }

  /** **Mit Karte bezahlen** – die Zahlungsabsicht über den offenen Betrag (wie
   *  `prepareVoucherPayment`); gebucht wird vom Webhook. */
  prepareBelegPayment(token: string): Promise<PaymentSetup> {
    return this.post(`/api/v1/public/beleg/${encodeURIComponent(token)}/payment`, {});
  }

  /** **Ein Rechtstext, wie er heute gilt** (AGB · Datenschutz · Impressum) – als A4-Dokument. */
  publicLegal(kind: 'agb' | 'datenschutz' | 'impressum'): Promise<import('@/types/api').components['schemas']['LegalOut']> {
    return this.get(`/api/v1/public/legal/${kind}`);
  }

  // ─── Admin: Settings ───────────────────────────────────────────────────────

  getSettings(): Promise<CompanySettings> {
    return this.get<Record<string, unknown>>('/api/v1/admin/settings').then(mapSettingsFromBackend);
  }

  getPublicSettings(): Promise<Partial<CompanySettings>> {
    return this.get<Record<string, unknown>>('/api/v1/admin/settings/public').then(mapSettingsFromBackend);
  }

  updateSettings(data: Partial<CompanySettings>): Promise<CompanySettings> {
    return this.patch<Record<string, unknown>>('/api/v1/admin/settings', mapSettingsToBackend(data)).then(mapSettingsFromBackend);
  }

  // ─── Admin: Unternehmen (Gesellschaften) ───────────────────────────────────
  // EIN gleichrangiger Datensatztyp (`organization`), jede Zeile eine vollständige
  // juristische Einheit (eigene Rechtsidentität). Anlegen/Ändern nur Admin. Die
  // Plattform-/Systemkonfiguration bleibt getrennt (getSettings/updateSettings).

  getCompanies(): Promise<CompanySettings[]> {
    return this.get<Record<string, unknown>[]>('/api/v1/admin/companies').then((rows) => rows.map(mapSettingsFromBackend));
  }

  getCompany(objectId: number): Promise<CompanySettings> {
    return this.get<Record<string, unknown>>(`/api/v1/admin/companies/${objectId}`).then(mapSettingsFromBackend);
  }

  /** Eine Firma anlegen – Name und Rechtsform sind Pflicht; ``is_own`` setzt nur ein Admin. */
  createCompany(data: { company_name: string; legal_form: string; uid_number?: string | null;
                        is_own?: boolean }): Promise<CompanySettings> {
    return this.post<Record<string, unknown>>('/api/v1/admin/companies', data).then(mapSettingsFromBackend);
  }

  /** **Welche Firma ist gemeint?** – Vorschläge für das **Personal** (die Tür lässt nur
   *  Personal durch: Kunden nennen ihre Firma über die UID, sie suchen sie nicht). */
  searchCompanies(search: string): Promise<CompanyRef[]> {
    return this.get(`/api/v1/erp/companies?search=${encodeURIComponent(search)}`);
  }

  updateCompany(objectId: number, data: Partial<CompanySettings>): Promise<CompanySettings> {
    return this.patch<Record<string, unknown>>(`/api/v1/admin/companies/${objectId}`, mapSettingsToBackend(data)).then(mapSettingsFromBackend);
  }

  /** Diese Gesellschaft zum **Betreiber der Website** machen – genau EINE trägt den Titel. */
  setCompanyOperator(objectId: number): Promise<CompanySettings> {
    return this.post<Record<string, unknown>>(`/api/v1/admin/companies/${objectId}/operator`, {}).then(mapSettingsFromBackend);
  }

  /** Ein Unternehmen **schliessen** (Soft-Delete; `reopenCompany` macht es rückgängig). */
  deactivateCompany(objectId: number): Promise<CompanySettings> {
    return this.delete<Record<string, unknown>>(`/api/v1/admin/companies/${objectId}`).then(mapSettingsFromBackend);
  }

  reopenCompany(objectId: number): Promise<CompanySettings> {
    return this.post<Record<string, unknown>>(`/api/v1/admin/companies/${objectId}/reopen`, {}).then(mapSettingsFromBackend);
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

  updateErpRecord(objectId: number, data: Partial<UserProfile>): Promise<UserProfile> {
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
                 body: { action: string } & Record<string, unknown>): Promise<import('@/types/api').components['schemas']['PapersOut']> {
    return this.post(`/api/v1/erp/orders/${orderObjectId}/steps/${stepId}/voucher/preview`, body);
  }

  /** **Ein Anhang einer Nachricht als Datei** – für den Entwurf eines Dokuments. */
  async messageAttachment(messageId: number, index: number, name: string): Promise<File> {
    const blob = await this.request<Blob>(`/api/v1/erp/messages/${messageId}/attachments/${index}`, {}, 'blob');
    return new File([blob], name, { type: blob.type });
  }

  /** «Aus Vorlage»: AGB oder Datenschutz einer eigenen Gesellschaft (nur Admin). */
  legalFromTemplate(company: number, kind: 'agb' | 'datenschutz'): Promise<DocumentDetail> {
    return this.post('/api/v1/erp/documents/template', { company, kind });
  }

  /**
   * **Eine Zahlung über den offenen Betrag vorbereiten** – für unsere eigene Karte.
   *
   * Sie ändert am Beleg **nichts**; gebucht wird erst, wenn das Geld da ist – und das
   * meldet der Webhook, nicht dieser Browser. Je Modul gibt es eine Rechnung, und sie
   * **ist** der Beleg – darum braucht es keine Rechnungsnummer.
   */
  prepareVoucherPayment(objectId: number, stepId: number): Promise<PaymentSetup> {
    return this.post(
      `/api/v1/erp/orders/${objectId}/steps/${stepId}/voucher/payment`, {});
  }

  /**
   * **Wie man diese Rechnung überweist** – Bankverbindung, Referenz und, wo er gilt, die
   * **QR-Rechnung** als fertiges Bild. Erzeugt wird sie im Backend: die Nutzlast ist eine
   * Liste von einunddreissig Zeilen in fester Reihenfolge.
   */
  voucherTransfer(objectId: number, stepId: number): Promise<TransferInfo> {
    return this.get(
      `/api/v1/erp/orders/${objectId}/steps/${stepId}/voucher/transfer`);
  }

  /**
   * ►►► **Welche Rechnung mindert dieser Beleg?** ◄◄◄
   *
   * Gesucht wird über **alle Aufträge** – das ist der Kern: eine Gutschrift gehört in den
   * Auftrag, in dem die Ware **zurückkommt**, nicht in den, der sie geliefert hat.
   */
  voucherCorrectable(objectId: number, stepId: number,
                     search = ''): Promise<VoucherCorrectable[]> {
    // **Gesucht wird auf dem Server** (#1050): dieselbe Bauart wie jede Referenz-Suche im
    // Haus – eine fertige Liste war bei einer Handvoll Belegen richtig und ist es beim
    // hundertsten nicht mehr.
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
    // Nur Mitarbeiter – die Empfänger einer internen Nachricht.
    if (staff) params.set('staff', 'true');
    return this.get(`/api/v1/erp/people?${params}`);
  }

  /** **Der Verlauf** einer Person bzw. aller Personen einer Firma – chronologisch. */
  getMessages(scope: { person?: number; company?: number }): Promise<Message[]> {
    const params = new URLSearchParams();
    if (scope.person) params.set('person', String(scope.person));
    if (scope.company) params.set('company', String(scope.company));
    return this.get(`/api/v1/erp/messages?${params}`);
  }

  createMessage(data: MessageIn): Promise<Message> {
    return this.post('/api/v1/erp/messages', data);
  }

  /** Je Datensatz, was zu tun ist – die Zahl am Symbol in Feed und Kopf. */
  todo(): Promise<Todo[]> {
    return this.get('/api/v1/erp/todo');
  }

  // ─── Zahlungen (eine Ableitung aus den Zahlungsmodulen) ────────────────────
  /** **Die Zahlungen einer Person** (`person`) **oder einer eigenen Gesellschaft**
   *  (`company`) – neueste Nummer zuoberst. */
  paymentsOf(scope: { person: number } | { company: number }): Promise<PaymentRow[]> {
    const params = new URLSearchParams();
    if ('person' in scope) params.set('person', String(scope.person));
    else params.set('company', String(scope.company));
    return this.get(`/api/v1/erp/payments?${params}`);
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
  timePreview(person: number, data: TimeEntryIn): Promise<EntryPreview> {
    return this.post(`/api/v1/erp/time/${person}/entries/preview`, data);
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

  messageChannels(): Promise<MessageChannel[]> {
    return this.get('/api/v1/erp/messages/channels');
  }

  /** Das Postfach einer eigenen Gesellschaft – Adresse, Zustand, darf ich verbinden?
   *  Persönliche Postfächer gibt es nicht. */
  mailboxes(company: number): Promise<Mailbox[]> {
    return this.get(`/api/v1/erp/messages/mailboxes?company=${company}`);
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
  personNewsletter(objectId: number): Promise<NewsletterState> {
    return this.get(`/api/v1/erp/newsletter/${objectId}`);
  }

  /** Die Bitte um Bestätigung schicken – anmelden kann das ERP niemanden. */
  inviteNewsletter(objectId: number): Promise<NewsletterState> {
    return this.post(`/api/v1/erp/newsletter/${objectId}/invite`, {});
  }

  unsubscribeNewsletter(objectId: number): Promise<NewsletterState> {
    return this.post(`/api/v1/erp/newsletter/${objectId}/unsubscribe`, {});
  }

  // ─── ERP Articles ──────────────────────────────────────────────────────────

  /** Der Artikel-Feed. `search` sucht im Namen – dieselbe Regel wie im Feed selbst,
   *  damit ein Auswahlfeld nicht zweihundert Artikel laden muss, um acht zu zeigen. */
  getArticles(search?: string, limit?: number): Promise<Article[]> {
    const params = new URLSearchParams();
    if (search?.trim()) params.set('search', search.trim());
    if (limit) params.set('limit', String(limit));
    const q = params.toString();
    return this.get(`/api/v1/erp/articles${q ? `?${q}` : ''}`);
  }

  getArticle(objectId: number): Promise<Article> {
    return this.get(`/api/v1/erp/articles/${objectId}`);
  }

  /** Wäre dieser Artikel-Entwurf freigebbar? Legt nichts an und zieht keine Nummer –
   *  dieselbe Regel, die auch die Anlage prüft (services/articles.validate_draft). */
  validateArticle(draft: unknown): Promise<ArticleValidation> {
    return this.post('/api/v1/erp/articles/validate', draft);
  }

  /** Anlegen **ist** Freigeben: Spezifikation UND Erzeugungsprozess in einem Aufruf –
   *  erst dabei entsteht der Datensatz und seine Objektnummer. */
  createArticle(data: ArticleInput): Promise<Article> {
    return this.post('/api/v1/erp/articles', data);
  }

  // Intelligente Namensvorschläge beim Anlegen (bereits verwendete/ähnliche Namen –
  // Dubletten vermeiden). Leere Eingabe → die häufigsten bestehenden Namen.
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

  getDocument(objectId: number): Promise<DocumentDetail> {
    return this.get(`/api/v1/erp/documents/${objectId}`);
  }

  /** Die Kacheln unten an einem Datensatz. */
  documentsOf(objectId: number): Promise<DocumentSummary[]> {
    return this.get(`/api/v1/erp/documents/of/${objectId}`);
  }

  /** Ein Datensatz für eine Referenz – Nummer ODER Name. */
  documentTargets(q: string): Promise<RecordRef[]> {
    return this.get(`/api/v1/erp/documents/targets?${new URLSearchParams({ q })}`);
  }

  /** Worauf Module warten – je Anforderung ein Satz. */
  documentRequirements(): Promise<DocumentRequirement[]> {
    return this.get('/api/v1/erp/documents/requirements');
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
  }): Promise<{ document: DocumentDetail; existed: boolean }> {
    const form = new FormData();
    files.forEach((f, i) => form.append('files', f, f instanceof File ? f.name : `seite-${i + 1}`));
    form.append('art', data.art);
    form.append('name', data.name);
    form.append('source', data.source);
    form.append('refs', JSON.stringify(data.refs.map((object_id) => ({ object_id }))));
    if (data.target) form.append('target', JSON.stringify(data.target));
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
  async uploadAttachment(file: File): Promise<import('@/types/api').components['schemas']['UploadResult']> {
    const headers: Record<string, string> = {};
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/api/v1/erp/attachments`, { method: 'POST', headers, body: form });
    if (!res.ok) throw await this.apiError(res);
    return res.json();
  }

  // Bestand eines Artikels: Aufstellung über ALLE Stücke + eine Seite Instanzen.
  getArticleStock(objectId: number, limit = 50, offset = 0): Promise<ArticleStock> {
    const p = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return this.get(`/api/v1/erp/articles/${objectId}/stock?${p}`);
  }

  // Ebene 3: die Nummern der Einzelinstanzen – seitenweise, auf Klick.
  // `statuses` ist eine Menge, keine Einzelwahl: ein Block der Bestandsansicht kann
  // mehrere Zustände umfassen, ein angeklicktes Segment genau einen.
  getInstanceUnits(objectId: number, opts: {
    statuses?: readonly string[]; limit?: number; offset?: number;
  } = {}): Promise<UnitPage> {
    const p = new URLSearchParams();
    (opts.statuses ?? []).forEach((s) => p.append('status', s));
    p.set('limit', String(opts.limit ?? 60));
    p.set('offset', String(opts.offset ?? 0));
    return this.get(`/api/v1/erp/instances/${objectId}/units?${p}`);
  }

  /**
   * **Woraus besteht ein Stück – und worin steckt es?** Beides abgeleitet aus dem
   * Ereignis-Log (`services/genealogy`), kein gespeichertes Feld.
   *
   * Erst auf Klick, wie die Nummern selbst: eine Baugruppe kann hunderte Teile haben.
   */
  getUnitGenealogy(objectId: number, suffix: number): Promise<Genealogy> {
    return this.get(`/api/v1/erp/instances/${objectId}/units/${suffix}/genealogy`);
  }

  // ─── Auftrag ───────────────────────────────────────────────────────────────
  // Es gibt KEINEN Entwurfs-Endpunkt: der Entwurf lebt im Browser, bis er speicherbar
  // ist. Erst `createOrder` legt ihn an – und erst dabei entsteht die Objektnummer.

  getOrders(limit = 0, offset = 0): Promise<OrderSummary[]> {
    const p = new URLSearchParams();
    if (limit) p.set('limit', String(limit));
    if (offset) p.set('offset', String(offset));
    const qs = p.toString();
    return this.get(`/api/v1/erp/orders${qs ? `?${qs}` : ''}`);
  }

  getOrder(objectId: number): Promise<Order> {
    return this.get(`/api/v1/erp/orders/${objectId}`);
  }

  /** Wäre dieser Entwurf speicherbar? Legt nichts an und zieht keine Nummer – die
   *  Oberfläche fragt damit dieselbe Regel ab, die auch das Speichern anlegt. */
  validateOrder(draft: OrderDraft): Promise<OrderValidation> {
    return this.post('/api/v1/erp/orders/validate', draft);
  }

  /** Anlegen **ist** Freigeben: ein Aufruf, eine Transaktion – der Auftrag entsteht,
   *  bekommt seine Nummer, die Stücke passieren das Start-Objekt (PROCESS_CORE.md §6.3). */
  createOrder(draft: OrderDraft): Promise<Order> {
    return this.post('/api/v1/erp/orders', draft);
  }

  /** **Eine Seite wählbarer Einzelinstanzen** (#740) – nicht die Liste. Gesperrte kommen
   *  mit: die Oberfläche zeigt den Grund, statt eine Zeile stumm verschwinden zu lassen.
   *
   *  `preselect` bittet den Server um die FIFO-Vorauswahl: sie aus einer gekappten Seite
   *  zu ziehen war der Fehler – sind die ersten Stücke verbaut, fände die Oberfläche
   *  nichts, obwohl freie da sind. */
  getUnitOptions(opts: {
    articleObjectId?: number; search?: string; status?: string[];
    preselect?: number; limit?: number; offset?: number;
  } = {}): Promise<UnitChoices> {
    const p = new URLSearchParams();
    if (opts.articleObjectId) p.set('article', String(opts.articleObjectId));
    if (opts.search?.trim()) p.set('search', opts.search.trim());
    (opts.status ?? []).forEach((s) => p.append('status', s));
    if (opts.preselect) p.set('preselect', String(opts.preselect));
    if (opts.limit) p.set('limit', String(opts.limit));
    if (opts.offset) p.set('offset', String(opts.offset));
    const q = p.toString();
    return this.get(`/api/v1/erp/orders/unit-options${q ? `?${q}` : ''}`);
  }

  /** Welche Artikel kann eine Definitionszeile aufnehmen? **Gesucht, nicht geladen**
   *  (#738): passend zur Eingabe, oder genau der eine gewählte (`objectId`) – damit im
   *  Feld sein Name steht. `template_steps` fährt mit, damit «Neu» begründet gesperrt wird. */
  getArticleOptions(opts: { search?: string; objectId?: number; limit?: number } = {}):
    Promise<ArticleOption[]> {
    const p = new URLSearchParams();
    if (opts.objectId != null) p.set('object_id', String(opts.objectId));
    else if (opts.search?.trim()) p.set('search', opts.search.trim());
    if (opts.limit) p.set('limit', String(opts.limit));
    const q = p.toString();
    return this.get(`/api/v1/erp/orders/article-options${q ? `?${q}` : ''}`);
  }

  /** Die Stücke **einer Kante** des Prozessbildes – dieselbe Position, die die Pille
   *  zählt; erst wenn jemand aufklappt (das Bild rechnet mit Zahlen, nicht Zeilen). */
  getOrderUnits(objectId: number, edge: string,
                limit = 100, offset = 0): Promise<OrderUnitPage> {
    const p = new URLSearchParams({ edge, limit: String(limit), offset: String(offset) });
    return this.get(`/api/v1/erp/orders/${objectId}/units?${p.toString()}`);
  }

  // ─── Erzeugungsprozess des Artikels (Vorlage) ──────────────────────────────
  // Sie kann nichts ausführen: es gibt hier keinen Aufruf, der ein Stück bewegt.

  getArticleProcess(objectId: number): Promise<ArticleProcess> {
    return this.get(`/api/v1/erp/articles/${objectId}/process`);
  }

  // Es gibt KEINEN Schreib-Endpunkt auf die Vorlage: sie entsteht mit dem Artikel
  // (`createArticle`) und ist ab da eingefroren.

  /** Was sich modellieren lässt – Modultypen und Erfassungspunkt-Typen. Beides sind
   *  geschlossene Listen im Backend; die Oberfläche holt sie, statt sie nachzubauen. */
  getModuleCatalog(): Promise<ModuleCatalog> {
    return this.get('/api/v1/erp/orders/module-catalog');
  }

  /**
   * «Bestätigen» – der eine Ausführungs-Endpunkt, für jedes Modul derselbe, **für genau
   * eine Instanz**. `values` ist zweistufig: Nummer der Einzelinstanz → (Punkt-`key` →
   * Wert) – der Scan verifiziert die Instanz, erfasst wird je Stück. Wie verifiziert
   * wurde (`scan` | `manual`), reist mit.
   */
  confirmStep(objectId: number, stepId: number, values: Record<string, Record<string, unknown>> = {},
              instanceObjectId?: number | null, verification?: string,
              sources: number[] = [], place: number | null = null): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${objectId}/steps/${stepId}/confirm`, {
      values,
      instance_object_id: instanceObjectId ?? null,
      verification: verification ?? null,
      // **Woraus verbaut wird** – die Instanzen, die der Lagerist gescannt hat. Leer
      // heisst «der ganze freie Bestand, älteste zuerst»; der Server rät nie mehr als das.
      sources,
      // **Wohin bewegt wurde** – die gescannte Ziel-Objektnummer. Bei einem Modul mit
      // festgelegtem Ziel ist sie die Verifikation, sonst die Wahl; bei jedem anderen
      // Modultyp bleibt sie `null` und wird verworfen.
      place,
    });
  }

  /**
   * Die Nummern **einer Gruppe dieser Instanz an diesem Modul** – erst auf Klick.
   *
   * `sample` sind die **gezogenen**: für jede ist ein eigener Wertesatz zu erfassen.
   * `failed`/`rest` sind die Vorauswahl der Entscheidung nach einem «nicht bestanden».
   *
   * Keine davon steht in der Auftrags-Antwort: bei einer 6000er-Charge wären es
   * tausende Nummern bei jedem Öffnen. Die Zahlen der Vorschau kommen aus `step_work`.
   */
  stepHold(objectId: number, stepId: number, instance: number,
           group: 'sample' | 'failed' | 'rest'): Promise<{ numbers: string[] }> {
    return this.get(
      `/api/v1/erp/orders/${objectId}/steps/${stepId}/hold`
      + `?instance=${instance}&group=${group}`);
  }

  /**
   * **Was an diesem Modul passiert ist** – lückenlos, je Einzelinstanz (#717).
   *
   * Erst auf Klick: bei einer 6000er-Charge wären es tausende Vorgänge. Die Regel gilt
   * für **alle** Module und wird serverseitig aus dem Ereignis-Log abgeleitet
   * (`services/record`) – hier steht keine zweite.
   */
  stepRecord(objectId: number, stepId: number, limit = 200, offset = 0): Promise<StepRecord> {
    return this.get(
      `/api/v1/erp/orders/${objectId}/steps/${stepId}/record`
      + `?limit=${limit}&offset=${offset}`);
  }

  // Instanz-Feed (server-seitig durchsuchbar/paginierbar, neueste Objektnummer zuerst).
  // Liefert Zusammenfassungen: die Einzelinstanzen stehen im Detail, nicht in der Liste.
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

  /**
   * **Kann diese Objektnummer etwas halten?** Dann: was sie ist und wie sie heisst.
   *
   * Ein 404 ist hier eine **Antwort** («das ist kein Ort»), kein Ausfall – Artikel und
   * Aufträge tragen ebenfalls Objektnummern, sind aber keine Halter. Genau daran
   * erkennt der Scanner einen Fehlgriff, bevor er ihn quittiert.
   */
  getPlace(objectId: number): Promise<PlaceRef> {
    return this.get(`/api/v1/erp/places/${objectId}`);
  }

  /**
   * **Halter suchen** – nach Objektnummer-Teil oder Namen («001», «Clemens», «Regal»).
   *
   * Die eine Vorschlagsquelle für jede Zielort-Eingabe: das Feld im Editor und der
   * Zielort-Scan zur Laufzeit fragen dieselbe Stelle. Angeboten wird nur, was auch
   * Halter sein **kann** – eine Liste, die etwas vorschlägt, das die Prüfung danach
   * abweist, wäre schlimmer als keine.
   */
  searchPlaces(query: string): Promise<PlaceRef[]> {
    return this.get(`/api/v1/erp/places?search=${encodeURIComponent(query)}`);
  }

  getInstance(objectId: number): Promise<Instance> {
    return this.get(`/api/v1/erp/instances/${objectId}`);
  }

  // ─── Testnotizen (in-app Feedback, nur Testumgebung) ────────────────────────

  listFeedback(route?: string): Promise<FeedbackNote[]> {
    const q = route ? `?route=${encodeURIComponent(route)}` : '';
    return this.get(`/api/v1/feedback${q}`);
  }

  createFeedback(data: FeedbackCreateInput): Promise<FeedbackNote> {
    return this.post('/api/v1/feedback', data);
  }

  updateFeedback(id: number, data: FeedbackUpdateInput): Promise<FeedbackNote> {
    return this.patch(`/api/v1/feedback/${id}`, data);
  }

  deleteFeedback(id: number): Promise<void> {
    return this.delete(`/api/v1/feedback/${id}`);
  }

  /** Aufräumen: 'done' entfernt Erledigte/Verworfene, 'all' setzt zurück. */
  clearFeedback(scope: 'done' | 'all'): Promise<{ deleted: number }> {
    return this.delete(`/api/v1/feedback?scope=${scope}`);
  }
}

// ─── CompanySettings field mapping (frontend ↔ backend) ──────────────────────

function mapSettingsFromBackend(s: Record<string, unknown>): CompanySettings {
  return {
    object_id: (s.object_id as number | null) ?? null,
    // Abgeleitet: Betreiber der Website (ein gewählter); has_address = trägt echte
    // Ortsangaben (ADR 005).
    is_operator: (s.is_operator as boolean) ?? false,
    is_active: (s.is_active as boolean) ?? true,
    // «Eigenes Unternehmen» – eine unserer Gesellschaften (CRM Schritt 1).
    is_own: (s.is_own as boolean) ?? false,
    people: (s.people as CompanyPerson[] | undefined) ?? [],
    has_address: (s.has_address as boolean) ?? false,
    company_name: (s.company_name as string) ?? '',
    legal_form: (s.legal_form as string | null) ?? null,
    // Der Datensatzname – Name UND Rechtsform (#984). Dieser Mapper baut Feld für Feld:
    // was er nicht nennt, verschwindet still.
    legal_name: (s.legal_name as string | undefined) ?? undefined,
    street: (s.street as string) ?? '',
    street_number: (s.street_nr as string | null) ?? null,
    zip: (s.zip_code as string) ?? '',
    city: (s.city as string) ?? '',
    country: (s.country as string) ?? '',
    currency: (s.currency as string) ?? 'CHF',
    uid: (s.uid_number as string | null) ?? null,
    vat_number: (s.vat_number as string | null) ?? null,
    email: (s.email as string) ?? '',
    phone: (s.phone as string | null) ?? null,
    // Abgeleitet aus dem Deployment (read-only, #309) – keine Eingabe, kein Rückweg.
    website: (s.website as string) ?? '',
    // Ausgeschrieben, nicht maskiert (#870): die IBAN steht auf jeder Rechnung.
    iban: (s.iban as string | null) ?? null,
    google_maps_api_key: (s.google_maps_api_key as string | null) ?? null,
  };
}

function mapSettingsToBackend(s: Partial<CompanySettings>): Record<string, unknown> {
  const fieldMap: Record<string, string> = {
    street_number: 'street_nr',
    zip: 'zip_code',
    uid: 'uid_number',
  };
  // `website` ist abgeleitet (Deployment-Adresse, #309) – es zurückzuschicken hiesse,
  // eine zweite Wahrheit anzulegen; das Backend nähme es ohnehin nicht an.
  // `legal_name` ist ebenso abgeleitet (Name + Rechtsform, `sites.legal_name`) – es
  // zurückzuschicken wäre die zweite Wahrheit neben den beiden Feldern, aus denen es kommt.
  const skip = new Set(['website', 'is_operator', 'has_address', 'is_active',
                        'legal_name', 'people']);
  const result: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(s)) {
    if (skip.has(k)) continue;
    result[fieldMap[k] ?? k] = v;
  }
  return result;
}

export const api = new ApiClient();

// Absolute Anzeige-URL für ein Attachment (die DB speichert nur den relativen Token-Pfad).
export function attachmentUrl(path: string): string {
  if (!path) return path;
  if (/^https?:\/\//.test(path) || path.startsWith('data:')) return path;
  return `${API_BASE}${path}`;
}
