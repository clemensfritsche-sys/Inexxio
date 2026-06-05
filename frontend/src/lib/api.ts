import type {
  CompanySettings,
  Item,
  ItemCategory,
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

  invalidateItem(id: number): Promise<Item> {
    return this.post(`/api/v1/items/${id}/invalidate`, {});
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
    return this.get('/api/v1/admin/settings');
  }

  getPublicSettings(): Promise<Partial<CompanySettings>> {
    return this.get('/api/v1/admin/settings/public');
  }

  updateSettings(data: Partial<CompanySettings>): Promise<CompanySettings> {
    return this.patch('/api/v1/admin/settings', data);
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

export const api = new ApiClient();
