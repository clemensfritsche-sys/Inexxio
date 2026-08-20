import type {
  Order,
  OrderSummary,
  OrderDraft,
  OrderValidation,
  UnitOption,
  ArticleOption,
  OrderUnitPage,
  ArticleProcess,
  InstanceSummary,
  ArticleValidation,
  ModuleCatalog,
  Article,
  ArticleInput,
  ArticleUpdateInput,
  ArticleNameSuggestion,
  Instance,
  ArticleStock,
  UnitPage,
  Genealogy,
  StepRecord,
  ObjectReference,
  CompanySettings,
  UserProfile,
  TerritoryMap,
  ShopConfig,
  Passkey,
  FeedbackNote,
  FeedbackCreateInput,
  FeedbackUpdateInput,
  PlaceRef,
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

/**
 * **«Ich habe Daten geändert» – an EINER Stelle gesagt** (Testnotizen #685/#688).
 *
 * Den Mechanismus gab es längst: der ERP-Feed hört auf `inexxio:data-changed` und lädt
 * dann sofort nach. Gefeuert hat ihn nur das KI-Widget – jedes Detailfenster schrieb
 * still an ihm vorbei. Darum stand im Feed «Im Prozess», während das Detail daneben
 * längst «Abgeschlossen» zeigte (#688), und eine frisch erzeugte Instanz erschien erst
 * nach einem Reload (#685). Es waren nie **zwei Quellen** – Feed und Detail leiten den
 * Status aus derselben Ableitung ab; der Feed hatte nur einen alten Stand.
 *
 * Die Stelle, an der «geändert» mit Sicherheit zutrifft, ist hier: **jede Anfrage, die
 * kein GET ist.** Ein Aufrufer kann es damit nicht mehr vergessen – und ein zweiter
 * Melde-Weg kann nicht entstehen.
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

  clearToken() {
    this.token = null;
  }

  // Transiente Transportfehler (Kaltstart / Skalierung / kurz nach einem Deploy)
  // äussern sich als 502/503 oder als abgewiesene Verbindung – die Anfrage
  // erreicht die App dann GAR NICHT und wird kurz erneut versucht (auch
  // schreibende, da der Server sie nie verarbeitet hat → keine Doppelanlage).
  // 500/504 hingegen nur bei LESENDEN (idempotenten) Anfragen wiederholen.
  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    // (Der Erfolgspfad unten meldet die Änderung – siehe ``notifyDataChanged``.)
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
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
        return response.json() as Promise<T>;
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







  // ─── Admin: Users ──────────────────────────────────────────────────────────

  getUsers(): Promise<UserProfile[]> {
    return this.get('/api/v1/admin/users');
  }

  deactivateUser(userId: number): Promise<{ deactivated: boolean }> {
    return this.delete(`/api/v1/admin/users/${userId}`);
  }

  /** Deaktivierten Benutzer reaktivieren – die bewusste Admin-Umkehr des Soft-Delete
   *  (die Identität/Objektnummer bleibt; beim Login wird ein Deaktivierter abgewiesen). */
  reactivateUser(userId: number): Promise<{ reactivated: boolean }> {
    return this.post(`/api/v1/admin/users/${userId}/reactivate`, {});
  }

  // ─── Admin: Settings ───────────────────────────────────────────────────────

  getSettings(): Promise<CompanySettings> {
    return this.get<Record<string, unknown>>('/api/v1/admin/settings').then(mapSettingsFromBackend);
  }

  getPublicSettings(): Promise<Partial<CompanySettings>> {
    return this.get<Record<string, unknown>>('/api/v1/admin/settings/public').then(mapSettingsFromBackend);
  }



  // Lagerwartung (E): Meldebestand prüfen (Auto-Nachbestellung).
  runMaintenanceSweep(): Promise<{ reordered: number }> {
    return this.post('/api/v1/erp/maintenance/sweep', {});
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

  createCompany(companyName: string): Promise<CompanySettings> {
    return this.post<Record<string, unknown>>('/api/v1/admin/companies', { company_name: companyName }).then(mapSettingsFromBackend);
  }

  updateCompany(objectId: number, data: Partial<CompanySettings>): Promise<CompanySettings> {
    return this.patch<Record<string, unknown>>(`/api/v1/admin/companies/${objectId}`, mapSettingsToBackend(data)).then(mapSettingsFromBackend);
  }

  /** Diese Gesellschaft zum **Betreiber der Website** machen – genau EINE trägt den Titel. */
  setCompanyOperator(objectId: number): Promise<CompanySettings> {
    return this.post<Record<string, unknown>>(`/api/v1/admin/companies/${objectId}/operator`, {}).then(mapSettingsFromBackend);
  }

  /** Ein Unternehmen **schliessen** (Soft-Delete, endgültig – keine Reaktivierung). */
  deactivateCompany(objectId: number): Promise<CompanySettings> {
    return this.delete<Record<string, unknown>>(`/api/v1/admin/companies/${objectId}`).then(mapSettingsFromBackend);
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

  updateErpRecord(objectId: number, data: Partial<UserProfile>): Promise<UserProfile> {
    return this.patch(`/api/v1/erp/records/${objectId}`, data);
  }

  // ─── ERP Articles ──────────────────────────────────────────────────────────

  getArticles(): Promise<Article[]> {
    return this.get('/api/v1/erp/articles');
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

  updateArticle(objectId: number, data: ArticleUpdateInput): Promise<Article> {
    return this.patch(`/api/v1/erp/articles/${objectId}`, data);
  }








  deleteStep(owner: 'articles' | 'orders', objectId: number, stepId: number): Promise<{ deleted: boolean }> {
    return this.delete(`/api/v1/erp/${owner}/${objectId}/steps/${stepId}`);
  }



  // ─── Dokumente (hochgeladene Belege/Anleitungen – KI-Aufnahme + Reiter «Dokumente») ─




  // Vorschlag ablehnen (Datei wird aus der Ablage entfernt)
  rejectDocument(actionId: number): Promise<{ rejected: boolean }> {
    return this.post(`/api/v1/ai/documents/${actionId}/reject`, {});
  }


  // Datei-Bytes authentifiziert holen und als lokale Object-URL bereitstellen (Inline-Vorschau
  // von PDF/Bild – ein <iframe>/<img> kann den Bearer-Token nicht selbst mitsenden). Der Aufrufer
  // gibt die URL per URL.revokeObjectURL wieder frei.
  async documentPreviewUrl(downloadPath: string): Promise<{ url: string; mime: string }> {
    const headers: Record<string, string> = {};
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    const res = await fetch(`${API_BASE}${downloadPath}`, { headers });
    if (!res.ok) throw await this.apiError(res);
    const blob = await res.blob();
    return { url: URL.createObjectURL(blob), mime: blob.type || 'application/octet-stream' };
  }

  deleteDocumentFile(docId: number): Promise<{ deleted: boolean }> {
    return this.delete(`/api/v1/erp/document-files/${docId}`);
  }

  // ─── Foto-/Bild-Upload (multipart) ──────────────────────────────────────────
  // Gibt eine relative URL (Token) zurück; die speichern die Verbraucher als String.
  async uploadAttachment(file: File): Promise<{ url: string; width: number | null; height: number | null }> {
    const headers: Record<string, string> = {};
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/api/v1/erp/attachments`, { method: 'POST', headers, body: form });
    if (!res.ok) throw await this.apiError(res);
    return res.json();
  }

  // ─── ERP Orders (Aufträge) ──────────────────────────────────────────────────










  // (Über eine Fehlmenge entscheidet seit Testnotiz #556 das System selbst
  //  (``recovery.auto_resolve``): hält sie noch jemand, wird gewartet; hält sie niemand
  //  mehr, sinkt das Soll darauf. «Ersetzen» ist bewusst zurückgestellt – der Weg existiert
  //  im Backend weiter (`POST …/cover`), es fragt nur niemand mehr danach.)
















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

  /** Welche Einzelinstanzen kann die Definition aufnehmen? Gesperrte kommen MIT –
   *  die Oberfläche soll den Grund zeigen, statt eine Zeile stumm verschwinden zu lassen. */
  getUnitOptions(articleObjectId?: number): Promise<UnitOption[]> {
    const qs = articleObjectId ? `?article=${articleObjectId}` : '';
    return this.get(`/api/v1/erp/orders/unit-options${qs}`);
  }

  /** Welche Artikel kann eine Definitionszeile aufnehmen? `template_steps` fährt mit,
   *  damit «Neu» gesperrt UND begründet werden kann, ohne einen zweiten Aufruf. */
  getArticleOptions(): Promise<ArticleOption[]> {
    return this.get('/api/v1/erp/orders/article-options');
  }

  /** Die einzelnen Stücke einer Gruppe – erst wenn jemand aufklappt. Das Diagramm
   *  selbst rechnet mit Zahlen (`unit_groups`), nicht mit 5000 Zeilen. */
  /** Die Stücke **einer Kante** des Prozessbildes – dieselbe Position, die die Pille
   *  zählt (Befund 2.1). Die frühere Frage «Schritt X, aktiv» war gröber als das Bild:
   *  an einem Punkt mit Teilung zählte die Pille die Gruppe, die Liste kannte die
   *  Teilung nicht und zeigte beide. */
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

  /** «Bestätigen» – der eine Ausführungs-Endpunkt, für jedes Modul derselbe. Was im
   *  Rumpf steht, entscheidet der Modultyp (Datenerfassung: die erfassten Werte). */
  /**
   * «Bestätigen» an einem Modul – **für genau eine Instanz** (Scan-Regel §3). Wie sie
   * verifiziert wurde (`scan` | `manual`), reist mit: beides ist eine Bestätigung, und
   * ohne den Vermerk wäre die Tastatur hinterher nicht von der Kamera zu unterscheiden.
   */
  /**
   * «Bestätigen» – **ein Wertesatz je Einzelinstanz**.
   *
   * `values` ist zweistufig: Nummer der Einzelinstanz → (Punkt-`key` → Wert). Der
   * Scan verifiziert die **Instanz**, erfasst wird je **Stück**; ein flacher Satz
   * wäre eine Messung, aus der n gleiche würden.
   */
  confirmStep(objectId: number, stepId: number, values: Record<string, Record<string, unknown>> = {},
              instanceObjectId?: number, verification?: string,
              sources: number[] = [], place: number | null = null,
              transport = ''): Promise<Order> {
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
      // **Womit.** Leer heisst «manuell» – die einzige Art, die es heute wirklich gibt.
      transport: transport || null,
    });
  }

  /**
   * Die Nummern einer Entscheidungs-Gruppe – **erst auf Klick** (§4.1). Der «Rest» einer
   * 6000er-Charge wären sechstausend Nummern; sie in jeder Auftrags-Antwort mitzuführen
   * wäre der Preis dafür, dass man sie einmal braucht.
   */
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


  // Generischer Rückverweis je Objektnummer («wer zeigt auf mich» – verortet/Ziel).
  getObjectReferences(objectId: number): Promise<ObjectReference[]> {
    return this.get(`/api/v1/erp/objects/${objectId}/references`);
  }

  // ─── Verkauf (ERP, Reiter «Verkauf» am Artikel) ─────────────────────────────
  // Verkaufs-Daten sind IMMER editierbar (auch bei freigegebenem Artikel).





  deleteArticlePrice(objectId: number, priceId: number): Promise<{ deleted: boolean }> {
    return this.delete(`/api/v1/erp/articles/${objectId}/sales/prices/${priceId}`);
  }


  removeArticleAudience(objectId: number, rowId: number): Promise<{ removed: boolean }> {
    return this.delete(`/api/v1/erp/articles/${objectId}/sales/audience/${rowId}`);
  }

  // ─── Shop (öffentlich / Kunde) ──────────────────────────────────────────────

  getShopConfig(): Promise<ShopConfig> {
    return this.get('/api/v1/shop/config');
  }





  // Stripe Customer Portal (Abo/Zahlungsmittel selbst verwalten)
  openCustomerPortal(): Promise<{ url: string }> {
    return this.post('/api/v1/shop/portal', {});
  }


  // Abo on-site kündigen (kündigt zuerst bei Stripe, dann lokal)
  cancelSubscription(orderObjectId: number): Promise<{ cancelled: boolean; subscription_active: boolean }> {
    return this.post(`/api/v1/shop/orders/${orderObjectId}/cancel-subscription`, {});
  }

  // Retoure/Rückgabe einer abgeschlossenen Bestellung anfragen (Online-Shop-Logik) – legt einen
  // Retoure-Auftrag an (Personal verarbeitet ihn im ERP: Wareneingang + Gutschrift/Stripe-Refund).
  requestReturn(orderObjectId: number, reason: string | null): Promise<{ return_object_id: number; status: string }> {
    return this.post(`/api/v1/shop/orders/${orderObjectId}/return`, { reason });
  }




  // ─── KI-Layer (ADR 004) ─────────────────────────────────────────────────────







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

  // ─── Contact form ──────────────────────────────────────────────────────────

  sendContactForm(data: {
    name: string;
    email: string;
    phone?: string;
    subject: string;
    message: string;
  }): Promise<{ ok: boolean }> {
    return this.post('/api/v1/contact', data);
  }
}


// ─── CompanySettings field mapping (frontend ↔ backend) ──────────────────────

function mapSettingsFromBackend(s: Record<string, unknown>): CompanySettings {
  return {
    object_id: (s.object_id as number | null) ?? null,
    // Abgeleitete Rollen (kein Rang): ältestes Unternehmen = Betreiber der Website;
    // has_address = trägt echte Ortsangaben (sonst logistisch stumm, ADR 005).
    is_operator: (s.is_operator as boolean) ?? false,
    is_active: (s.is_active as boolean) ?? true,
    has_address: (s.has_address as boolean) ?? false,
    company_name: (s.company_name as string) ?? '',
    legal_form: (s.legal_form as string | null) ?? null,
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
    logo_url: (s.logo_path as string | null) ?? null,
    iban: null,
    iban_masked: (s.iban_masked as string | null) ?? null,
    stripe_publishable_key: (s.stripe_publishable_key as string | null) ?? null,
    plausible_domain: (s.plausible_domain as string | null) ?? null,
    hcaptcha_site_key: (s.hcaptcha_site_key as string | null) ?? null,
    google_maps_api_key: (s.google_maps_api_key as string | null) ?? null,
    default_receiving_location_id: (s.default_receiving_location_id as number | null) ?? null,
    shop_currencies: (s.shop_currencies as string[] | null) ?? ['CHF', 'EUR', 'USD'],
    shop_country_currency: (s.shop_country_currency as Record<string, string> | null) ?? null,
    shop_default_currency: (s.shop_default_currency as string | null) ?? 'CHF',
    payments_provider: (s.payments_provider as string | null) ?? null,
    pricing_zone_factors: (s.pricing_zone_factors as Record<string, number> | null) ?? null,
    infra_monthly_chf: (s.infra_monthly_chf as number | null) ?? null,
    legal_documents: (s.legal_documents as Record<string, number> | null) ?? null,
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
  const skip = new Set(['iban_masked', 'logo_url', 'website', 'is_operator', 'has_address', 'is_active']);
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
