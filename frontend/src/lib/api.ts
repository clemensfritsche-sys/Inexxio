import type {
  CompanySettings,
  Item,
  BOM,
  WorkPlan,
  Company,
  Contact,
  UserProfile,
  UniversalObject,
  PaginatedResponse,
  ObjectFilter,
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

  getItems(page = 1, pageSize = 50): Promise<PaginatedResponse<Item>> {
    return this.get(`/api/v1/items?page=${page}&page_size=${pageSize}`);
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

  approveItem(id: number): Promise<Item> {
    return this.post(`/api/v1/items/${id}/approve`, {});
  }

  // ─── BOMs ──────────────────────────────────────────────────────────────────

  getBOMs(page = 1, pageSize = 50): Promise<PaginatedResponse<BOM>> {
    return this.get(`/api/v1/boms?page=${page}&page_size=${pageSize}`);
  }

  getBOM(id: number): Promise<BOM> {
    return this.get(`/api/v1/boms/${id}`);
  }

  createBOM(data: Partial<BOM>): Promise<BOM> {
    return this.post('/api/v1/boms', data);
  }

  updateBOM(id: number, data: Partial<BOM>): Promise<BOM> {
    return this.patch(`/api/v1/boms/${id}`, data);
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
