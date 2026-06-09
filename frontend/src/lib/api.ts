import type {
  CompanySettings,
  Item,
  ItemCategory,
  ItemHistoryEntry,
  ItemName,
  ItemSurface,
  BOM,
  WorkPlan,
  Company,
  Contact,
  UserProfile,
  UniversalObject,
  PaginatedResponse,
  ObjectFilter,
  WhereUsedEntry,
  UniObjekt,
  UniObjektSummary,
  ProzessSchrittDef,
  ObjektTyp,
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

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...((options.headers as Record<string, string>) || {}),
    };
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ error: 'Netzwerkfehler', code: 'NETWORK_ERROR' }));
      const detail = error.detail;
      const msg = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join('; ')
          : error.error || `HTTP ${response.status}`;
      throw new Error(msg);
    }

    if (response.status === 204) return {} as T;
    return response.json();
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

  // ─── Objects (universal feed) ──────────────────────────────────────────────

  getObjects(filter?: ObjectFilter): Promise<PaginatedResponse<UniversalObject>> {
    const params = new URLSearchParams();
    if (filter?.q) params.set('q', filter.q);
    if (filter?.object_type) params.set('object_type', filter.object_type);
    if (filter?.status) params.set('status', filter.status);
    if (filter?.page) params.set('page', String(filter.page));
    if (filter?.page_size) params.set('page_size', String(filter.page_size));
    const qs = params.toString();
    return this.get(`/api/v1/objects${qs ? `?${qs}` : ''}`);
  }

  getObject(id: number): Promise<UniversalObject> {
    return this.get(`/api/v1/objects/${id}`);
  }

  // ─── Items ─────────────────────────────────────────────────────────────────

  getItems(params?: { page?: number; pageSize?: number; q?: string; status?: string }): Promise<PaginatedResponse<Item>> {
    const p = new URLSearchParams();
    p.set('page', String(params?.page ?? 1));
    p.set('page_size', String(params?.pageSize ?? 50));
    if (params?.q) p.set('q', params.q);
    if (params?.status) p.set('status', params.status);
    return this.get(`/api/v1/items?${p.toString()}`);
  }

  getItem(id: number): Promise<Item> {
    return this.get(`/api/v1/items/${id}`);
  }

  createItem(data: Partial<Item>): Promise<Item> {
    return this.post('/api/v1/items', data);
  }

  updateItem(id: number, data: Partial<Item>): Promise<Item> {
    return this.patch(`/api/v1/items/${id}`, data);
  }

  submitItem(id: number): Promise<Item> {
    return this.post(`/api/v1/items/${id}/submit`, {});
  }

  approveItem(id: number): Promise<Item> {
    return this.post(`/api/v1/items/${id}/approve`, {});
  }

  replaceItem(id: number): Promise<Item> {
    return this.post(`/api/v1/items/${id}/replace`, {});
  }

  invalidateItem(id: number, replacedById?: number): Promise<Item> {
    return this.post(`/api/v1/items/${id}/invalidate`, { replaced_by_id: replacedById ?? null });
  }

  setItemReplacement(id: number, replacedById: number): Promise<Item> {
    return this.post(`/api/v1/items/${id}/set-replacement`, { replaced_by_id: replacedById });
  }

  deleteItem(id: number): Promise<void> {
    return this.delete(`/api/v1/items/${id}`);
  }

  getItemNames(): Promise<ItemName[]> {
    return this.get('/api/v1/admin/item-names');
  }

  createItemName(label: string): Promise<ItemName> {
    return this.post('/api/v1/admin/item-names', { label });
  }

  getItemSurfaces(): Promise<ItemSurface[]> {
    return this.get('/api/v1/admin/item-surfaces');
  }

  createItemSurface(label: string): Promise<ItemSurface> {
    return this.post('/api/v1/admin/item-surfaces', { label });
  }

  getItemCategories(): Promise<ItemCategory[]> {
    return this.get('/api/v1/admin/item-categories');
  }

  createItemCategory(label: string): Promise<ItemCategory> {
    return this.post('/api/v1/admin/item-categories', { label });
  }

  deleteItemName(id: number): Promise<void> {
    return this.delete(`/api/v1/admin/item-names/${id}`);
  }

  deleteItemSurface(id: number): Promise<void> {
    return this.delete(`/api/v1/admin/item-surfaces/${id}`);
  }

  deleteItemCategory(id: number): Promise<void> {
    return this.delete(`/api/v1/admin/item-categories/${id}`);
  }

  recallItem(id: number): Promise<Item> {
    return this.post(`/api/v1/items/${id}/recall`, {});
  }

  // ─── BOMs ──────────────────────────────────────────────────────────────────

  getBOMs(page = 1, pageSize = 50): Promise<BOM[]> {
    return this.get(`/api/v1/boms?page=${page}&page_size=${pageSize}`);
  }

  getBOM(id: number): Promise<BOM> {
    return this.get(`/api/v1/boms/${id}`);
  }

  getBOMsForItem(itemId: number): Promise<BOM[]> {
    return this.get(`/api/v1/boms/by-item/${itemId}`);
  }

  createBOM(data: { parent_item_id: number; note?: string | null; lines: { component_item_id: number; quantity: number; unit: string; position: number; note?: string | null }[] }): Promise<BOM> {
    return this.post('/api/v1/boms', data);
  }

  updateBOM(id: number, data: { note?: string | null; lines?: { component_item_id: number; quantity: number; unit: string; position: number; note?: string | null }[] }): Promise<BOM> {
    return this.patch(`/api/v1/boms/${id}`, data);
  }

  getItemWhereUsed(itemId: number): Promise<WhereUsedEntry[]> {
    return this.get(`/api/v1/items/${itemId}/where-used`);
  }

  getItemHistory(itemId: number): Promise<ItemHistoryEntry[]> {
    return this.get(`/api/v1/items/${itemId}/history`);
  }

  // ─── Work Plans ────────────────────────────────────────────────────────────

  getWorkPlans(page = 1, pageSize = 50): Promise<PaginatedResponse<WorkPlan>> {
    return this.get(`/api/v1/work-plans?page=${page}&page_size=${pageSize}`);
  }

  getWorkPlan(id: number): Promise<WorkPlan> {
    return this.get(`/api/v1/work-plans/${id}`);
  }

  createWorkPlan(data: Partial<WorkPlan>): Promise<WorkPlan> {
    return this.post('/api/v1/work-plans', data);
  }

  // ─── Companies ─────────────────────────────────────────────────────────────

  getCompanies(page = 1, pageSize = 50): Promise<PaginatedResponse<Company>> {
    return this.get(`/api/v1/companies?page=${page}&page_size=${pageSize}`);
  }

  getCompany(id: number): Promise<Company> {
    return this.get(`/api/v1/companies/${id}`);
  }

  createCompany(data: Partial<Company>): Promise<Company> {
    return this.post('/api/v1/companies', data);
  }

  updateCompany(id: number, data: Partial<Company>): Promise<Company> {
    return this.patch(`/api/v1/companies/${id}`, data);
  }

  // ─── Contacts ──────────────────────────────────────────────────────────────

  getContacts(companyId?: number): Promise<PaginatedResponse<Contact>> {
    const qs = companyId ? `?company_id=${companyId}` : '';
    return this.get(`/api/v1/contacts${qs}`);
  }

  // ─── Users ─────────────────────────────────────────────────────────────────

  getMe(): Promise<UserProfile> {
    return this.get('/api/v1/auth/me');
  }

  updateMe(data: Partial<UserProfile>): Promise<UserProfile> {
    return this.patch('/api/v1/auth/me', data);
  }

  getUsers(): Promise<UserProfile[]> {
    return this.get('/api/v1/admin/users');
  }

  updateUserRole(userId: number, role: string): Promise<UserProfile> {
    return this.patch(`/api/v1/admin/users/${userId}/role`, { role });
  }

  deactivateUser(userId: number): Promise<{ deactivated: boolean }> {
    return this.delete(`/api/v1/admin/users/${userId}`);
  }

  // ─── Settings ──────────────────────────────────────────────────────────────

  getSettings(): Promise<CompanySettings> {
    return this.get<Record<string, unknown>>('/api/v1/admin/settings').then(mapSettingsFromBackend);
  }

  getPublicSettings(): Promise<Partial<CompanySettings>> {
    return this.get<Record<string, unknown>>('/api/v1/admin/settings/public').then(mapSettingsFromBackend);
  }

  updateSettings(data: Partial<CompanySettings>): Promise<CompanySettings> {
    return this.patch<Record<string, unknown>>('/api/v1/admin/settings', mapSettingsToBackend(data)).then(mapSettingsFromBackend);
  }

  // ─── Unified Objekte ───────────────────────────────────────────────────────

  listUniObjekte(params?: { q?: string; stamm?: boolean; page?: number; page_size?: number }): Promise<PaginatedResponse<UniObjektSummary>> {
    const p = new URLSearchParams();
    if (params?.q) p.set('q', params.q);
    if (params?.stamm !== undefined) p.set('stamm', String(params.stamm));
    if (params?.page) p.set('page', String(params.page));
    if (params?.page_size) p.set('page_size', String(params.page_size));
    const qs = p.toString();
    return this.get(`/api/v1/uni-objekte${qs ? `?${qs}` : ''}`);
  }

  createUniObjekt(data: { name: string; notiz?: string; einheit?: string }): Promise<UniObjekt> {
    return this.post('/api/v1/uni-objekte', data);
  }

  getUniObjekt(id: number): Promise<UniObjekt> {
    return this.get(`/api/v1/uni-objekte/${id}`);
  }

  updateUniObjekt(id: number, data: { name?: string; notiz?: string; einheit?: string; lagerort?: string }): Promise<UniObjekt> {
    return this.patch(`/api/v1/uni-objekte/${id}`, data);
  }

  deleteUniObjekt(id: number): Promise<void> {
    return this.delete(`/api/v1/uni-objekte/${id}`);
  }

  freigeben(id: number): Promise<UniObjekt> {
    return this.post(`/api/v1/uni-objekte/${id}/freigeben`, {});
  }

  addSchritt(id: number, data: { position: number; beschreibung: string; ressourcen?: object[]; daten_felder?: object[]; ergebnis_optionen?: object[]; referenz_objekt_id?: number; referenz_menge?: number }): Promise<ProzessSchrittDef> {
    return this.post(`/api/v1/uni-objekte/${id}/schritte`, data);
  }

  updateSchritt(id: number, schrittId: number, data: Partial<{ position: number; beschreibung: string; ressourcen: object[]; daten_felder: object[]; ergebnis_optionen: object[]; referenz_objekt_id: number | null; referenz_menge: number }>): Promise<ProzessSchrittDef> {
    return this.patch(`/api/v1/uni-objekte/${id}/schritte/${schrittId}`, data);
  }

  deleteSchritt(id: number, schrittId: number): Promise<void> {
    return this.delete(`/api/v1/uni-objekte/${id}/schritte/${schrittId}`);
  }

  ausfuehren(id: number, data: { menge: number; lagerort?: string }): Promise<UniObjektSummary[]> {
    return this.post(`/api/v1/uni-objekte/${id}/ausfuehren`, data);
  }

  listInstanzen(id: number, page = 1, page_size = 20): Promise<PaginatedResponse<UniObjektSummary>> {
    return this.get(`/api/v1/uni-objekte/${id}/instanzen?page=${page}&page_size=${page_size}`);
  }

  schrittErledigen(instanceId: number, position: number, data: { ergebnis: string; erfasste_daten?: Record<string, string>; ausgefuehrt_von?: string }): Promise<UniObjekt> {
    return this.post(`/api/v1/uni-objekte/${instanceId}/protokoll/${position}/erledigen`, data);
  }

  // ─── Objekttypen (admin) ──────────────────────────────────────────────────

  listObjektTypen(): Promise<ObjektTyp[]> {
    return this.get('/api/v1/admin/objekttypen');
  }

  createObjektTyp(data: { name: string; farbe?: string }): Promise<ObjektTyp> {
    return this.post('/api/v1/admin/objekttypen', data);
  }

  deleteObjektTyp(id: number): Promise<void> {
    return this.delete(`/api/v1/admin/objekttypen/${id}`);
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
