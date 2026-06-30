import type {
  Article, ArticleInput, ArticleUpdateInput,
  ArticleProcessStep, ArticleProcessStepInput, ArticleProcessStepUpdateInput,
  Order, OrderSummary, OrderInput, OrderUpdateInput, PurchaseOrderUpdateInput, InspectionUpdateInput,
  MovementUpdateInput, ResourceUpdateInput, ScrapUpdateInput, SaleUpdateInput,
  Instance, InstanceOrderRef, ObjectReference, StorageLocation, StorageLocationInput, StorageLocationUpdateInput,
  CompanySettings, UserProfile, DeactivationImpact, OrdersMode,
  ArticleSalesProfile, ArticleSalesUpdateInput, ArticlePrice, ArticlePriceInput, ArticlePriceUpdateInput,
  AudienceMember, ShopProduct, ShopConfig, ShopCheckoutResult, PaymentStatus, SaleStatus,
  CustomerOrder,
} from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
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
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...((options.headers as Record<string, string>) || {}),
    };
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

    const method = (options.method ?? 'GET').toUpperCase();
    const idempotent = method === 'GET' || method === 'HEAD';
    const MAX_ATTEMPTS = 3;
    let lastError: Error = new Error('Keine Verbindung zum Server');

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
        if (response.status === 204) return {} as T;
        return response.json() as Promise<T>;
      }

      const retriable = response.status === 502 || response.status === 503
        || (idempotent && response.status >= 500);
      if (retriable && attempt < MAX_ATTEMPTS) {
        lastError = new Error(`Server nicht erreichbar (HTTP ${response.status})`);
        await this.backoff(attempt);
        continue;
      }
      throw new Error(await this.errorMessage(response));
    }
    throw lastError;
  }

  private backoff(attempt: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, attempt === 1 ? 500 : 1200));
  }

  // Fehlermeldung aufbereiten: bevorzugt das JSON-`detail` der API, sonst der
  // echte HTTP-Status (statt eines undurchsichtigen «Netzwerkfehler»).
  private async errorMessage(response: Response): Promise<string> {
    const body = (await response.json().catch(() => null)) as
      { detail?: unknown; error?: string } | null;
    const detail = body?.detail;
    if (typeof detail === 'string') return detail;
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

  acceptTerms(): Promise<UserProfile> {
    return this.post('/api/v1/auth/terms-accept', {});
  }

  // ─── Admin: Users ──────────────────────────────────────────────────────────

  getUsers(): Promise<UserProfile[]> {
    return this.get('/api/v1/admin/users');
  }

  updateUserRole(userId: number, role: string): Promise<UserProfile> {
    return this.patch(`/api/v1/admin/users/${userId}/role`, { role });
  }

  deactivateUser(userId: number): Promise<{ deactivated: boolean }> {
    return this.delete(`/api/v1/admin/users/${userId}`);
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

  // ─── ERP Records ──────────────────────────────────────────────────────────

  getErpRecords(): Promise<UserProfile[]> {
    return this.get('/api/v1/erp/records');
  }

  getErpRecord(objectId: number): Promise<UserProfile> {
    return this.get(`/api/v1/erp/records/${objectId}`);
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

  createArticle(data: ArticleInput): Promise<Article> {
    return this.post('/api/v1/erp/articles', data);
  }

  updateArticle(objectId: number, data: ArticleUpdateInput): Promise<Article> {
    return this.patch(`/api/v1/erp/articles/${objectId}`, data);
  }

  // Inaktiv/Ersetzen: Wirkungsanalyse, Inaktiv-Setzen (mit Auftrags-Wahl), Ersetzen
  getArticleDeactivationImpact(objectId: number): Promise<DeactivationImpact> {
    return this.get(`/api/v1/erp/articles/${objectId}/deactivation-impact`);
  }

  deactivateArticle(objectId: number, ordersMode: OrdersMode): Promise<Article> {
    return this.post(`/api/v1/erp/articles/${objectId}/deactivate`, { orders_mode: ordersMode });
  }

  replaceArticle(objectId: number, ordersMode: OrdersMode): Promise<Article> {
    return this.post(`/api/v1/erp/articles/${objectId}/replace`, { orders_mode: ordersMode });
  }

  // ─── Prozesse: eigenständige Objekte (Feed «Prozesse») + Stückliste je Artikel ─

  // ─── Prozessschritte – am Artikel (Entstehung) ODER am Auftrag (CUSTOM) ────────
  // ``owner`` = 'articles' | 'orders'; kein eigenständiges Prozess-Objekt mehr.

  getSteps(owner: 'articles' | 'orders', objectId: number): Promise<ArticleProcessStep[]> {
    return this.get(`/api/v1/erp/${owner}/${objectId}/steps`);
  }

  createStep(owner: 'articles' | 'orders', objectId: number, data: ArticleProcessStepInput): Promise<ArticleProcessStep> {
    return this.post(`/api/v1/erp/${owner}/${objectId}/steps`, data);
  }

  updateStep(owner: 'articles' | 'orders', objectId: number, stepId: number, data: ArticleProcessStepUpdateInput): Promise<ArticleProcessStep> {
    return this.patch(`/api/v1/erp/${owner}/${objectId}/steps/${stepId}`, data);
  }

  deleteStep(owner: 'articles' | 'orders', objectId: number, stepId: number): Promise<{ deleted: boolean }> {
    return this.delete(`/api/v1/erp/${owner}/${objectId}/steps/${stepId}`);
  }

  // Reihenfolge der frei sortierbaren Schritte; Pflicht-Bewegungen ordnet der Server.
  reorderSteps(owner: 'articles' | 'orders', objectId: number, orderedIds: number[]): Promise<ArticleProcessStep[]> {
    return this.patch(`/api/v1/erp/${owner}/${objectId}/steps/reorder`, { ordered_ids: orderedIds });
  }

  // ─── ERP Orders (Aufträge) ──────────────────────────────────────────────────

  // Schlanker Feed (ohne Embeds); Detail via getOrder(id)
  getOrders(): Promise<OrderSummary[]> {
    return this.get('/api/v1/erp/orders');
  }

  getOrder(objectId: number): Promise<Order> {
    return this.get(`/api/v1/erp/orders/${objectId}`);
  }

  createOrder(data: OrderInput): Promise<Order> {
    return this.post('/api/v1/erp/orders', data);
  }

  updateOrder(objectId: number, data: OrderUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}`, data);
  }

  // Ersetzen: neuen Auftrag (Entwurf) anlegen, verknüpfen, Original abbrechen
  replaceOrder(objectId: number): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${objectId}/replace`, {});
  }

  // Abbrechen: erzwingt einen Folgeauftrag (Abweichung); liefert diesen zurück (bzw. bei
  // einem Entwurf den direkt inaktivierten Auftrag).
  abortOrder(objectId: number): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${objectId}/abort`, {});
  }

  // «Abweichung melden»: eröffnet einen Unterauftrag (Abweichung) auf den Instanzen
  // dieses Auftrags (optional eine Teilmenge); liefert den Entwurf der Abweichung zurück.
  createDeviation(objectId: number, instanceObjectIds?: number[]): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${objectId}/deviation`,
      instanceObjectIds && instanceObjectIds.length ? { instance_object_ids: instanceObjectIds } : {});
  }

  // Beschaffungsschritt des Auftrags (läuft unter der Auftragsnummer)
  updateOrderPurchase(objectId: number, data: PurchaseOrderUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/purchase`, data);
  }

  // Schritt «Eingangskontrolle»: Stichprobenergebnis erfassen
  updateOrderInspection(objectId: number, data: InspectionUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/inspection`, data);
  }

  // Schritt «Bewegung»: Instanzen einlagern/umlagern (Zielstandort je Instanz)
  updateOrderMovement(objectId: number, data: MovementUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/movement`, data);
  }

  // Schritt «Ressource»: Verbrauch (FIFO) + Betriebsmittel erfassen
  updateOrderResource(objectId: number, data: ResourceUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/resource`, data);
  }

  // Schritt «Verschrotten»: gewählte Instanzen ausschleusen (disposition='scrapped')
  updateOrderScrap(objectId: number, data: ScrapUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/scrap`, data);
  }

  // Schritt «Verkauf» (kaufmännisch): Bestätigung → Rechnung → Zahlung
  updateOrderSale(objectId: number, data: SaleUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/sale`, data);
  }

  // Bestand (Instanzen) eines Artikels
  getArticleInstances(objectId: number): Promise<Instance[]> {
    return this.get(`/api/v1/erp/articles/${objectId}/instances`);
  }

  // Instanz-Feed (server-seitig paginierbar + durchsuchbar; limit=0 → alle, neueste zuerst)
  getInstances(limit = 0, offset = 0, search = ''): Promise<Instance[]> {
    const p = new URLSearchParams();
    if (limit) p.set('limit', String(limit));
    if (offset) p.set('offset', String(offset));
    if (search) p.set('search', search);
    const qs = p.toString();
    return this.get(`/api/v1/erp/instances${qs ? `?${qs}` : ''}`);
  }

  // Gesamtzahl (matchender) Instanzen für die Feed-Zähler/Pagination
  getInstanceCount(search = ''): Promise<{ count: number }> {
    return this.get(`/api/v1/erp/instances/count${search ? `?search=${encodeURIComponent(search)}` : ''}`);
  }

  // Universelle Objektnummer serverseitig auf ihren Typ auflösen (Scan/Navigation)
  resolveObject(objectId: number): Promise<{ object_id: number; object_type: string }> {
    return this.get(`/api/v1/erp/objects/${objectId}`);
  }

  getInstance(objectId: number): Promise<Instance> {
    return this.get(`/api/v1/erp/instances/${objectId}`);
  }

  // Aufträge, die diese Instanz angefasst haben (Herkunft zuerst)
  getInstanceOrders(objectId: number): Promise<InstanceOrderRef[]> {
    return this.get(`/api/v1/erp/instances/${objectId}/orders`);
  }

  // ─── ERP Storage Locations (Lagerplätze) ────────────────────────────────────

  getStorageLocations(): Promise<StorageLocation[]> {
    return this.get('/api/v1/erp/storage-locations');
  }

  getStorageLocation(objectId: number): Promise<StorageLocation> {
    return this.get(`/api/v1/erp/storage-locations/${objectId}`);
  }

  createStorageLocation(data: StorageLocationInput): Promise<StorageLocation> {
    return this.post('/api/v1/erp/storage-locations', data);
  }

  updateStorageLocation(objectId: number, data: StorageLocationUpdateInput): Promise<StorageLocation> {
    return this.patch(`/api/v1/erp/storage-locations/${objectId}`, data);
  }

  // Ersetzen: Duplikat (Entwurf) anlegen, verknüpfen, Original inaktiv (nur wenn leer)
  replaceStorageLocation(objectId: number): Promise<StorageLocation> {
    return this.post(`/api/v1/erp/storage-locations/${objectId}/replace`, {});
  }

  // Verwendung eines Lagerplatzes (lagernde Instanzen + referenzierende Artikel)
  getStorageLocationReferences(objectId: number): Promise<ObjectReference[]> {
    return this.get(`/api/v1/erp/storage-locations/${objectId}/references`);
  }

  // ─── Verkauf (ERP, Reiter «Verkauf» am Artikel) ─────────────────────────────
  // Verkaufs-Daten sind IMMER editierbar (auch bei freigegebenem Artikel).

  getArticleSales(objectId: number): Promise<ArticleSalesProfile> {
    return this.get(`/api/v1/erp/articles/${objectId}/sales`);
  }

  updateArticleSales(objectId: number, data: ArticleSalesUpdateInput): Promise<ArticleSalesProfile> {
    return this.patch(`/api/v1/erp/articles/${objectId}/sales`, data);
  }

  createArticlePrice(objectId: number, data: ArticlePriceInput): Promise<ArticlePrice> {
    return this.post(`/api/v1/erp/articles/${objectId}/sales/prices`, data);
  }

  updateArticlePrice(objectId: number, priceId: number, data: ArticlePriceUpdateInput): Promise<ArticlePrice> {
    return this.patch(`/api/v1/erp/articles/${objectId}/sales/prices/${priceId}`, data);
  }

  deleteArticlePrice(objectId: number, priceId: number): Promise<{ deleted: boolean }> {
    return this.delete(`/api/v1/erp/articles/${objectId}/sales/prices/${priceId}`);
  }

  addArticleAudience(objectId: number, userId: number): Promise<AudienceMember[]> {
    return this.post(`/api/v1/erp/articles/${objectId}/sales/audience`, { user_id: userId });
  }

  removeArticleAudience(objectId: number, rowId: number): Promise<{ removed: boolean }> {
    return this.delete(`/api/v1/erp/articles/${objectId}/sales/audience/${rowId}`);
  }

  // ─── Shop (öffentlich / Kunde) ──────────────────────────────────────────────

  getShopConfig(): Promise<ShopConfig> {
    return this.get('/api/v1/shop/config');
  }

  // Preise immer in CHF (Basis); Stripe Adaptive Pricing zeigt die Lokalwährung an der Kasse.
  getShopProducts(lang?: string): Promise<ShopProduct[]> {
    const qs = lang ? `?lang=${lang}` : '';
    return this.get(`/api/v1/shop/products${qs}`);
  }

  getShopProduct(objectId: number, lang?: string): Promise<ShopProduct> {
    const qs = lang ? `?lang=${lang}` : '';
    return this.get(`/api/v1/shop/products/${objectId}${qs}`);
  }

  // Warenkorb-Checkout: mehrere Positionen ⇒ eine Zahlungs-Session (Defer-Modell).
  shopCheckout(items: { article_object_id: number; price_id: number; quantity: number }[]): Promise<ShopCheckoutResult> {
    return this.post('/api/v1/shop/checkout', { items });
  }

  // Stripe-Checkout-Session-Status (Erfolgsseite nach eingebetteter Kasse)
  getCheckoutSession(sessionId: string): Promise<{ order_object_id: number | null; order_object_ids: number[]; status: SaleStatus; paid: boolean }> {
    return this.get(`/api/v1/shop/session/${sessionId}`);
  }

  // Stripe Customer Portal (Abo/Zahlungsmittel selbst verwalten)
  openCustomerPortal(): Promise<{ url: string }> {
    return this.post('/api/v1/shop/portal', {});
  }

  // Eigene Bestellungen + Abos (Kunde)
  getMyOrders(): Promise<CustomerOrder[]> {
    return this.get('/api/v1/shop/orders');
  }

  // Bestellungen eines Benutzers (ERP-Reiter, staff)
  getRecordOrders(objectId: number): Promise<CustomerOrder[]> {
    return this.get(`/api/v1/erp/records/${objectId}/orders`);
  }

  // Manueller Provider (Fallback ohne Stripe-Keys)
  getPaymentStatus(token: string): Promise<PaymentStatus> {
    return this.get(`/api/v1/shop/payment/${token}`);
  }

  simulatePayment(token: string, result: 'paid' | 'cancelled'): Promise<{ status: SaleStatus }> {
    return this.post('/api/v1/shop/payments/simulate', { sale_token: token, result });
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
    company_name: (s.company_name as string) ?? '',
    legal_form: (s.legal_form as string | null) ?? null,
    street: (s.street as string) ?? '',
    street_number: (s.street_nr as string | null) ?? null,
    zip: (s.zip_code as string) ?? '',
    city: (s.city as string) ?? '',
    country: (s.country as string) ?? '',
    uid: (s.uid_number as string | null) ?? null,
    vat_number: (s.vat_number as string | null) ?? null,
    trade_register_number: (s.trade_register_nr as string | null) ?? null,
    trade_register_canton: (s.trade_register_canton as string | null) ?? null,
    share_capital: (s.share_capital as string | null) ?? null,
    email: (s.email as string) ?? '',
    phone: (s.phone as string | null) ?? null,
    website: (s.website as string) ?? '',
    logo_url: (s.logo_path as string | null) ?? null,
    iban: null,
    iban_masked: (s.iban_masked as string | null) ?? null,
    qr_iban: null,
    qr_iban_masked: (s.qr_iban_masked as string | null) ?? null,
    bank_name: (s.bank as string | null) ?? null,
    bic: (s.bic_swift as string | null) ?? null,
    vat_method: (s.vat_method as 'effektiv' | 'saldosteuersatz' | null) ?? 'effektiv',
    vat_period: (s.vat_period as 'quartal' | 'semester' | 'jahr' | null) ?? 'quartal',
    default_payment_days: (s.default_payment_days as number) ?? 30,
    default_discount_percent: s.default_skonto_pct != null ? String(s.default_skonto_pct) : null,
    default_discount_days: (s.default_skonto_days as number | null) ?? null,
    oss_active: (s.oss_active as boolean) ?? false,
    oss_number: (s.oss_reg_number as string | null) ?? null,
    vies_validation: (s.vies_active as boolean) ?? false,
    stripe_publishable_key: (s.stripe_publishable_key as string | null) ?? null,
    plausible_domain: (s.plausible_domain as string | null) ?? null,
    hcaptcha_site_key: (s.hcaptcha_site_key as string | null) ?? null,
    google_maps_api_key: (s.google_maps_api_key as string | null) ?? null,
    default_receiving_location_id: (s.default_receiving_location_id as number | null) ?? null,
    article_names: (s.article_names as string[] | null) ?? [],
    shop_currencies: (s.shop_currencies as string[] | null) ?? ['CHF', 'EUR', 'USD'],
    shop_country_currency: (s.shop_country_currency as Record<string, string> | null) ?? null,
    shop_default_currency: (s.shop_default_currency as string | null) ?? 'CHF',
    payments_provider: (s.payments_provider as string | null) ?? null,
    pricing_zone_factors: (s.pricing_zone_factors as Record<string, number> | null) ?? null,
  };
}

function mapSettingsToBackend(s: Partial<CompanySettings>): Record<string, unknown> {
  const fieldMap: Record<string, string> = {
    street_number: 'street_nr',
    zip: 'zip_code',
    uid: 'uid_number',
    trade_register_number: 'trade_register_nr',
    bank_name: 'bank',
    bic: 'bic_swift',
    oss_number: 'oss_reg_number',
    vies_validation: 'vies_active',
    default_discount_percent: 'default_skonto_pct',
    default_discount_days: 'default_skonto_days',
  };
  const skip = new Set(['iban_masked', 'qr_iban_masked', 'logo_url']);
  const result: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(s)) {
    if (skip.has(k)) continue;
    result[fieldMap[k] ?? k] = v;
  }
  return result;
}

export const api = new ApiClient();
