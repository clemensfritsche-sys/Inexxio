'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Search, Building2, Loader2, AlertCircle, X, ChevronRight, CheckCircle2,
  Globe, Mail, Phone, MapPin
} from 'lucide-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Company, CompanyRole } from '@/types';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

const ROLE_CONFIG: Record<CompanyRole, { color: string; label: string }> = {
  Kunde: { color: 'bg-blue-50 text-blue-700', label: 'Kunde' },
  Lieferant: { color: 'bg-green-50 text-green-700', label: 'Lieferant' },
  Interessent: { color: 'bg-amber-50 text-amber-700', label: 'Interessent' },
  Partner: { color: 'bg-purple-50 text-purple-700', label: 'Partner' },
};

const MOCK_COMPANIES: Company[] = [
  {
    id: 1, number: '400000001', name: 'Hydraulik AG Zürich', legal_form: 'AG', role: 'Lieferant', is_active: true,
    address: { street: 'Industriestrasse', street_number: '45', zip: '8152', city: 'Glattbrugg', country: 'Schweiz', country_code: 'CH' },
    uid: 'CHE-123.456.789', vat_number: 'CHE-123.456.789 MWST', website: 'https://www.hydraulik-ag.ch',
    email: 'info@hydraulik-ag.ch', phone: '+41 44 800 10 20', notes: 'Hauptlieferant für Hydraulikkomponenten',
    payment_terms_days: 30, discount_percent: '2.00',
    created_at: '2026-01-12T14:00:00Z', updated_at: '2026-04-02T10:00:00Z',
  },
  {
    id: 2, number: '400000002', name: 'Maschinenbau Müller GmbH', legal_form: 'GmbH', role: 'Kunde', is_active: true,
    address: { street: 'Werkstrasse', street_number: '12', zip: '4500', city: 'Solothurn', country: 'Schweiz', country_code: 'CH' },
    uid: 'CHE-987.654.321', vat_number: 'CHE-987.654.321 MWST', website: null,
    email: 'einkauf@mueller-mb.ch', phone: '+41 32 622 10 30', notes: null,
    payment_terms_days: 30, discount_percent: null,
    created_at: '2026-01-20T09:00:00Z', updated_at: '2026-03-15T11:00:00Z',
  },
  {
    id: 3, number: '400000003', name: 'Dichtungstechnik Bern AG', legal_form: 'AG', role: 'Lieferant', is_active: true,
    address: { street: 'Belpstrasse', street_number: '28', zip: '3007', city: 'Bern', country: 'Schweiz', country_code: 'CH' },
    uid: null, vat_number: null, website: 'https://www.dichtungen-bern.ch',
    email: 'vertrieb@dichtungen-bern.ch', phone: '+41 31 388 77 00', notes: 'Lieferant für Dichtungssets',
    payment_terms_days: 14, discount_percent: '3.00',
    created_at: '2026-02-05T10:00:00Z', updated_at: '2026-04-18T15:30:00Z',
  },
  {
    id: 4, number: '400000004', name: 'AutoMotive Solutions SA', legal_form: 'SA', role: 'Interessent', is_active: true,
    address: { street: 'Route de la Industrie', street_number: '5', zip: '1030', city: 'Bussigny', country: 'Schweiz', country_code: 'CH' },
    uid: null, vat_number: null, website: null,
    email: 'contact@automotive-solutions.ch', phone: '+41 21 633 40 50', notes: 'Interesse an Hydraulikzylindern für Fahrzeuge',
    payment_terms_days: 30, discount_percent: null,
    created_at: '2026-03-01T13:00:00Z', updated_at: '2026-05-22T10:00:00Z',
  },
];

function FirmenPageInner() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<CompanyRole | 'all'>('all');
  const [showCreate, setShowCreate] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [error, setError] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['companies'],
    queryFn: () => api.getCompanies(1, 100),
  });

  const companies: Company[] = isError || !data ? MOCK_COMPANIES : data.items;

  const filtered = companies.filter((c) => {
    const q = search.toLowerCase();
    const matchesSearch =
      !q ||
      c.name.toLowerCase().includes(q) ||
      c.number.includes(q) ||
      (c.email || '').toLowerCase().includes(q) ||
      (c.address?.city || '').toLowerCase().includes(q);
    const matchesRole = roleFilter === 'all' || c.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  const createMutation = useMutation({
    mutationFn: (data: Partial<Company>) => api.createCompany(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['companies'] });
      setShowCreate(false);
    },
    onError: () => setError('Fehler beim Erstellen der Firma.'),
  });

  const roleCounts = (['Kunde', 'Lieferant', 'Interessent', 'Partner'] as CompanyRole[]).map((role) => ({
    role,
    count: companies.filter((c) => c.role === role).length,
  }));

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
            <Building2 className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Firmen</h1>
            <p className="text-sm text-slate-500">{companies.length} Firmen</p>
          </div>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary">
          <Plus className="h-4 w-4" />
          Firma erstellen
        </button>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
          <p className="text-sm text-red-700">{error}</p>
          <button onClick={() => setError('')} className="ml-auto"><X className="h-4 w-4 text-red-400" /></button>
        </div>
      )}

      {isError && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <AlertCircle className="h-4 w-4 text-amber-500 shrink-0" />
          <p className="text-sm text-amber-700">Demo-Modus: API nicht erreichbar.</p>
        </div>
      )}

      {/* Role Stats */}
      <div className="mb-4 flex flex-wrap gap-2">
        {roleCounts.map(({ role, count }) => (
          <button
            key={role}
            onClick={() => setRoleFilter(roleFilter === role ? 'all' : role)}
            className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              roleFilter === role
                ? ROLE_CONFIG[role].color + ' border-current'
                : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
            }`}
          >
            {ROLE_CONFIG[role].label}
            <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${
              roleFilter === role ? 'bg-white/40' : 'bg-slate-100'
            }`}>{count}</span>
          </button>
        ))}
      </div>

      <div className="mb-4 relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <input
          type="text"
          placeholder="Firma suchen…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="form-input pl-10"
        />
      </div>

      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-4 py-3 text-left font-medium text-slate-600 w-32">Nr.</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Firma</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 w-28">Rolle</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 hidden md:table-cell">Kontakt</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 hidden lg:table-cell">Standort</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 hidden md:table-cell w-20">Zahlungsfrist</th>
                <th className="px-4 py-3 w-8"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-500">
                    <Building2 className="mx-auto mb-3 h-8 w-8 text-slate-300" />
                    <p className="font-medium">Keine Firmen gefunden</p>
                    <p className="text-xs mt-1">Erstellen Sie Ihren ersten Firmeneintrag.</p>
                  </td>
                </tr>
              ) : (
                filtered.map((company) => {
                  const rc = ROLE_CONFIG[company.role] || ROLE_CONFIG.Interessent;
                  return (
                    <tr
                      key={company.id}
                      onClick={() => setSelectedCompany(company)}
                      className="border-b border-slate-100 last:border-0 hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{company.number}</td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-900">{company.name}</p>
                        {company.legal_form && (
                          <p className="text-xs text-slate-500">{company.legal_form}</p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${rc.color}`}>
                          {rc.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        {company.email && (
                          <a
                            href={`mailto:${company.email}`}
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center gap-1 text-xs text-blue-600 hover:underline"
                          >
                            <Mail className="h-3 w-3" />
                            {company.email}
                          </a>
                        )}
                        {company.phone && (
                          <p className="flex items-center gap-1 text-xs text-slate-500 mt-0.5">
                            <Phone className="h-3 w-3" />
                            {company.phone}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell">
                        {company.address && (
                          <p className="flex items-center gap-1 text-xs text-slate-600">
                            <MapPin className="h-3 w-3 shrink-0" />
                            {company.address.zip} {company.address.city}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-slate-600 text-center">
                        {company.payment_terms_days ? `${company.payment_terms_days}T` : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <ChevronRight className="h-4 w-4 text-slate-300" />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}
      </div>

      {selectedCompany && (
        <CompanyDetailModal company={selectedCompany} onClose={() => setSelectedCompany(null)} />
      )}

      {showCreate && (
        <CreateCompanyModal
          onClose={() => setShowCreate(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          saving={createMutation.isPending}
        />
      )}
    </div>
  );
}

function CompanyDetailModal({ company, onClose }: { company: Company; onClose: () => void }) {
  const rc = ROLE_CONFIG[company.role] || ROLE_CONFIG.Interessent;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="relative w-full max-w-2xl rounded-xl bg-white shadow-xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 p-6">
          <div>
            <p className="text-xs font-mono text-slate-500 mb-0.5">{company.number}</p>
            <h2 className="text-xl font-bold text-slate-900">{company.name}</h2>
            {company.legal_form && <p className="text-sm text-slate-500">{company.legal_form}</p>}
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-6 space-y-6">
          <div className="flex flex-wrap gap-2">
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${rc.color}`}>
              {rc.label}
            </span>
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
              company.is_active ? 'bg-green-50 text-green-700' : 'bg-slate-100 text-slate-500'
            }`}>
              {company.is_active ? 'Aktiv' : 'Inaktiv'}
            </span>
          </div>

          <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            {company.address && (
              <div>
                <p className="text-xs text-slate-500 mb-1">Adresse</p>
                <div className="flex items-start gap-1.5 text-sm text-slate-800">
                  <MapPin className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
                  <div>
                    <p>{company.address.street} {company.address.street_number}</p>
                    <p>{company.address.zip} {company.address.city}</p>
                    <p>{company.address.country}</p>
                  </div>
                </div>
              </div>
            )}
            <div className="space-y-2">
              {company.email && (
                <div className="flex items-center gap-1.5 text-sm">
                  <Mail className="h-4 w-4 text-slate-400" />
                  <a href={`mailto:${company.email}`} className="text-blue-600 hover:underline">{company.email}</a>
                </div>
              )}
              {company.phone && (
                <div className="flex items-center gap-1.5 text-sm text-slate-700">
                  <Phone className="h-4 w-4 text-slate-400" />
                  {company.phone}
                </div>
              )}
              {company.website && (
                <div className="flex items-center gap-1.5 text-sm">
                  <Globe className="h-4 w-4 text-slate-400" />
                  <a href={company.website} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                    {company.website.replace(/^https?:\/\//, '')}
                  </a>
                </div>
              )}
            </div>
          </div>

          {(company.uid || company.vat_number) && (
            <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2 rounded-lg border border-slate-200 p-4">
              {company.uid && (
                <div>
                  <p className="text-xs text-slate-500">UID-Nummer</p>
                  <p className="text-sm font-mono text-slate-800 mt-0.5">{company.uid}</p>
                </div>
              )}
              {company.vat_number && (
                <div>
                  <p className="text-xs text-slate-500">MWST-Nummer</p>
                  <p className="text-sm font-mono text-slate-800 mt-0.5">{company.vat_number}</p>
                </div>
              )}
            </div>
          )}

          {(company.payment_terms_days || company.discount_percent) && (
            <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2 rounded-lg border border-slate-200 p-4">
              {company.payment_terms_days && (
                <div>
                  <p className="text-xs text-slate-500">Zahlungsfrist</p>
                  <p className="text-sm font-medium text-slate-800 mt-0.5">{company.payment_terms_days} Tage</p>
                </div>
              )}
              {company.discount_percent && (
                <div>
                  <p className="text-xs text-slate-500">Rabatt</p>
                  <p className="text-sm font-medium text-slate-800 mt-0.5">{company.discount_percent}%</p>
                </div>
              )}
            </div>
          )}

          {company.notes && (
            <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-700">
              {company.notes}
            </div>
          )}

          <p className="text-xs text-slate-400">
            Erstellt: {new Date(company.created_at).toLocaleDateString('de-CH')} ·
            Zuletzt geändert: {new Date(company.updated_at).toLocaleDateString('de-CH')}
          </p>
        </div>
      </div>
    </div>
  );
}

function CreateCompanyModal({
  onClose,
  onSubmit,
  saving,
}: {
  onClose: () => void;
  onSubmit: (data: Partial<Company>) => void;
  saving: boolean;
}) {
  const [form, setForm] = useState({
    name: '',
    legal_form: '',
    role: 'Kunde' as CompanyRole,
    email: '',
    phone: '',
    website: '',
    street: '',
    street_number: '',
    zip: '',
    city: '',
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      name: form.name,
      legal_form: form.legal_form || null,
      role: form.role,
      email: form.email || null,
      phone: form.phone || null,
      website: form.website || null,
      is_active: true,
      address: (form.street || form.zip || form.city)
        ? {
            street: form.street,
            street_number: form.street_number || null,
            zip: form.zip,
            city: form.city,
            country: 'Schweiz',
            country_code: 'CH',
          }
        : null,
    });
  }

  const f = (k: keyof typeof form) => ({
    value: form[k],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm({ ...form, [k]: e.target.value }),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="relative w-full max-w-lg rounded-xl bg-white shadow-xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <form onSubmit={handleSubmit}>
          <div className="flex items-center justify-between border-b border-slate-200 p-6">
            <h2 className="text-lg font-bold text-slate-900">Neue Firma</h2>
            <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="p-6 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Firmenname *</label>
                <input required className="form-input" placeholder="z.B. Hydraulik AG" {...f('name')} />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Rechtsform</label>
                <input className="form-input" placeholder="AG, GmbH, ..." {...f('legal_form')} />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Rolle *</label>
                <select className="form-input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as CompanyRole })}>
                  <option value="Kunde">Kunde</option>
                  <option value="Lieferant">Lieferant</option>
                  <option value="Interessent">Interessent</option>
                  <option value="Partner">Partner</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">E-Mail</label>
                <input type="email" className="form-input" placeholder="info@firma.ch" {...f('email')} />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Telefon</label>
                <input type="tel" className="form-input" placeholder="+41 44 000 00 00" {...f('phone')} />
              </div>
            </div>
            <div className="border-t border-slate-100 pt-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Adresse (optional)</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="sm:col-span-2 grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <label className="block text-xs text-slate-600 mb-1">Strasse</label>
                    <input className="form-input" placeholder="Musterstrasse" {...f('street')} />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-600 mb-1">Nr.</label>
                    <input className="form-input" placeholder="1a" {...f('street_number')} />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">PLZ</label>
                  <input className="form-input" placeholder="8000" {...f('zip')} />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">Ort</label>
                  <input className="form-input" placeholder="Zürich" {...f('city')} />
                </div>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-3 border-t border-slate-100 px-6 py-4">
            <button type="button" onClick={onClose} className="btn-secondary">Abbrechen</button>
            <button type="submit" disabled={saving || !form.name} className="btn-primary disabled:opacity-50">
              {saving ? <><Loader2 className="h-4 w-4 animate-spin" /> Speichert…</> : <><CheckCircle2 className="h-4 w-4" /> Erstellen</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function FirmenPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <FirmenPageInner />
    </QueryClientProvider>
  );
}
