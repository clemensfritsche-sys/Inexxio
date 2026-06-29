'use client';

import { useCallback, useEffect, useState } from 'react';
import { Tag, Plus, Trash2, Globe, Lock, EyeOff, Image as ImageIcon, Languages, Coins } from 'lucide-react';
import { api } from '@/lib/api';
import type {
  ArticleSalesProfile, ArticlePrice, AudienceMember, PriceView,
  SalesVisibility, SalesContent, SalesContentBlock, PriceKind, PriceInterval, TaxClass, UserProfile,
} from '@/types';
import {
  Label, TextField, SelectField, Segmented, SearchSelect, SectionTitle, InfoHint, Placeholder,
} from '@/components/erp/fields';
import { useAutosave } from '@/lib/use-autosave';

const VISIBILITY: { value: SalesVisibility; label: string; icon: React.ElementType; hint: string }[] = [
  { value: 'public', label: 'Öffentlich', icon: Globe, hint: 'Für alle im Shop sichtbar.' },
  { value: 'private', label: 'Privat', icon: Lock, hint: 'Nur zugewiesene Kunden sehen es.' },
  { value: 'unlisted', label: 'Verborgen', icon: EyeOff, hint: 'Nur per direktem Link erreichbar (nicht gelistet).' },
];

const TAX_LABEL: Record<TaxClass, string> = {
  standard: 'Standard 8.1 %', reduced: 'Reduziert 2.6 %', lodging: 'Beherbergung 3.8 %', zero: 'Steuerfrei 0 %',
};

function fmtMoney(amount: number | string | null | undefined, currency: string): string {
  if (amount == null) return '—';
  return `${currency} ${Number(amount).toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function emptyBlock(): SalesContentBlock {
  return { title: '', subtitle: '', description: '', images: [] };
}

export function SalesPanel({ articleObjectId }: { articleObjectId: number | null }) {
  const [profile, setProfile] = useState<ArticleSalesProfile | null>(null);
  const [customers, setCustomers] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (articleObjectId == null) return;
    try {
      const p = await api.getArticleSales(articleObjectId);
      setProfile(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Laden');
    } finally {
      setLoading(false);
    }
  }, [articleObjectId]);

  useEffect(() => { reload(); }, [reload]);
  useEffect(() => {
    api.getUsers().then((u) => setCustomers(u.filter((x) => x.role === 'customer'))).catch(() => {});
  }, []);

  if (articleObjectId == null) {
    return <Placeholder icon={Tag} title="Noch nicht verfügbar" text="Der Artikel muss zuerst angelegt werden." />;
  }
  if (loading) return <div style={{ padding: 16, fontSize: 13, color: '#94a3b8' }}>Lädt…</div>;
  if (!profile) return <div style={{ padding: 16, fontSize: 13, color: '#dc2626' }}>{error ?? 'Kein Profil'}</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <ProfileCard profile={profile} onSaved={setProfile} articleObjectId={articleObjectId} />
      <PricesCard articleObjectId={articleObjectId} prices={profile.prices} onChanged={reload} />
      {profile.sales_visibility !== 'public' && (
        <AudienceCard articleObjectId={articleObjectId} audience={profile.audience}
          customers={customers} onChanged={reload} />
      )}
      <PreviewCard previews={profile.previews} />
    </div>
  );
}

const card: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px',
  display: 'flex', flexDirection: 'column', gap: 12,
};

// ─── Profil: Publiziert + Sichtbarkeit + Inhalt (de/en) ──────────────────────────

function ProfileCard({ profile, onSaved, articleObjectId }: {
  profile: ArticleSalesProfile; onSaved: (p: ArticleSalesProfile) => void; articleObjectId: number;
}) {
  const [published, setPublished] = useState(profile.sales_published);
  const [visibility, setVisibility] = useState<SalesVisibility>(profile.sales_visibility);
  const [content, setContent] = useState<SalesContent>(profile.sales_content ?? { de: emptyBlock(), en: emptyBlock() });
  const [lang, setLang] = useState<'de' | 'en'>('de');
  const [flash, setFlash] = useState(false);

  const block = content[lang] ?? emptyBlock();
  function setBlock(patch: Partial<SalesContentBlock>) {
    setContent((c) => ({ ...c, [lang]: { ...(c[lang] ?? emptyBlock()), ...patch } }));
  }

  const sig = JSON.stringify({ published, visibility, content });
  const [savedSig, setSavedSig] = useState(sig);

  const save = useCallback(async () => {
    try {
      const saved = await api.updateArticleSales(articleObjectId, {
        sales_published: published, sales_visibility: visibility, sales_content: content,
      });
      onSaved(saved);
      setSavedSig(JSON.stringify({ published: saved.sales_published, visibility: saved.sales_visibility, content: saved.sales_content ?? { de: emptyBlock(), en: emptyBlock() } }));
      setFlash(true); setTimeout(() => setFlash(false), 700);
    } catch { /* belassen */ }
  }, [articleObjectId, published, visibility, content, onSaved]);

  const flush = useAutosave(sig, sig !== savedSig, save);

  const imagesText = (block.images ?? []).join('\n');

  return (
    <div style={{ ...card, boxShadow: flash ? 'inset 0 0 0 2px #16a34a' : 'none', transition: 'box-shadow .2s' }}
      onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); flush(); } }}>
      <SectionTitle icon={Tag} info="Der Verkauf bleibt auch nach der Freigabe editierbar – nur Spezifikation und Prozess sind eingefroren.">Verkauf</SectionTitle>

      <Segmented label="Status" value={published ? 'true' : 'false'} onChange={(v) => setPublished(v === 'true')}
        options={[{ value: 'true', label: 'Publiziert' }, { value: 'false', label: 'Nicht publiziert' }]} />

      <div>
        <Label>Sichtbarkeit</Label>
        <div style={{ display: 'flex', gap: 6 }}>
          {VISIBILITY.map((v) => {
            const active = visibility === v.value;
            const Icon = v.icon;
            return (
              <button key={v.value} type="button" title={v.hint} onClick={() => setVisibility(v.value)}
                style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                  padding: '7px 8px', fontSize: 12, fontWeight: 600, borderRadius: 8, cursor: 'pointer',
                  border: `1px solid ${active ? '#2563eb' : '#e2e8f0'}`, background: active ? '#eff6ff' : '#fff',
                  color: active ? '#2563eb' : '#64748b' }}>
                <Icon size={13} /> {v.label}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: 12 }}>
        <SectionTitle icon={Languages} right={
          <Segmented label="" value={lang} onChange={(v) => setLang(v as 'de' | 'en')}
            options={[{ value: 'de', label: 'DE' }, { value: 'en', label: 'EN' }]} />
        }>Inhalt</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <TextField label="Titel" value={block.title ?? ''} onChange={(v) => setBlock({ title: v })} placeholder="Produkttitel" />
          <TextField label="Untertitel" value={block.subtitle ?? ''} onChange={(v) => setBlock({ subtitle: v })} placeholder="kurzer Zusatz" />
          <div>
            <Label>Beschreibung</Label>
            <textarea value={block.description ?? ''} onChange={(e) => setBlock({ description: e.target.value })}
              onBlur={flush} rows={3} placeholder="Produktbeschreibung"
              className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500"
              style={{ borderColor: '#e2e8f0', resize: 'vertical' }} />
          </div>
          <div>
            <Label>Bild-URLs</Label>
            <textarea value={imagesText} onChange={(e) => setBlock({ images: e.target.value.split('\n').map((s) => s.trim()).filter(Boolean) })}
              onBlur={flush} rows={2} placeholder="https://… (eine URL pro Zeile, z. B. GCS-Links)"
              className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500"
              style={{ borderColor: '#e2e8f0', resize: 'vertical' }} />
            <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 4 }}>
              <ImageIcon size={11} /> Eine Bild-URL pro Zeile.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Preise ──────────────────────────────────────────────────────────────────────

function PricesCard({ articleObjectId, prices, onChanged }: {
  articleObjectId: number; prices: ArticlePrice[]; onChanged: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<{ kind: PriceKind; interval: PriceInterval; amount: string; compare: string; tax: TaxClass }>(
    { kind: 'one_time', interval: 'month', amount: '', compare: '', tax: 'standard' });

  async function add() {
    if (!form.amount.trim()) return;
    setBusy(true);
    try {
      await api.createArticlePrice(articleObjectId, {
        kind: form.kind, interval: form.kind === 'subscription' ? form.interval : null,
        amount_chf: form.amount, compare_at_chf: form.compare.trim() || null,
        tax_class: form.tax, is_primary: prices.length === 0,
      });
      setForm({ kind: 'one_time', interval: 'month', amount: '', compare: '', tax: 'standard' });
      setAdding(false);
      onChanged();
    } finally { setBusy(false); }
  }

  return (
    <div style={card}>
      <SectionTitle icon={Coins} info="Beträge sind die Netto-Basis in CHF. Der Shop rechnet pro Anzeige in die Zielwährung um (Tageskurs, schön gerundet) und schlägt die MWST auf.">Preise</SectionTitle>
      {prices.length === 0 && !adding && (
        <div style={{ fontSize: 12, color: '#94a3b8' }}>Noch kein Preis – ohne Preis erscheint das Produkt nicht im Shop.</div>
      )}
      {prices.map((p) => (
        <PriceRow key={p.id} articleObjectId={articleObjectId} price={p} onChanged={onChanged} />
      ))}

      {adding ? (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <SelectField label="Art" value={form.kind} onChange={(v) => setForm((f) => ({ ...f, kind: v as PriceKind }))}
              options={[{ value: 'one_time', label: 'Einmalkauf' }, { value: 'subscription', label: 'Abo' }]} />
            {form.kind === 'subscription' && (
              <SelectField label="Intervall" value={form.interval} onChange={(v) => setForm((f) => ({ ...f, interval: v as PriceInterval }))}
                options={[{ value: 'month', label: 'monatlich' }, { value: 'year', label: 'jährlich' }]} />
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <TextField label="Preis (CHF, netto)" value={form.amount} onChange={(v) => setForm((f) => ({ ...f, amount: v }))} placeholder="z. B. 199.00" />
            <TextField label="Vergleichspreis (optional)" value={form.compare} onChange={(v) => setForm((f) => ({ ...f, compare: v }))} placeholder="durchgestrichen" />
          </div>
          <SelectField label="Steuerklasse" value={form.tax} onChange={(v) => setForm((f) => ({ ...f, tax: v as TaxClass }))}
            options={(Object.keys(TAX_LABEL) as TaxClass[]).map((k) => ({ value: k, label: TAX_LABEL[k] }))} />
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={add} disabled={busy || !form.amount.trim()}
              style={{ padding: '7px 14px', borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', opacity: busy ? 0.6 : 1 }}>Speichern</button>
            <button onClick={() => setAdding(false)}
              style={{ padding: '7px 14px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', fontSize: 13, color: '#475569', cursor: 'pointer' }}>Abbrechen</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setAdding(true)}
          style={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', color: '#2563eb', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
          <Plus size={14} /> Preis hinzufügen
        </button>
      )}
    </div>
  );
}

function PriceRow({ articleObjectId, price, onChanged }: {
  articleObjectId: number; price: ArticlePrice; onChanged: () => void;
}) {
  const [amount, setAmount] = useState(String(price.amount_chf));
  const [compare, setCompare] = useState(price.compare_at_chf != null ? String(price.compare_at_chf) : '');
  const [tax, setTax] = useState<TaxClass>(price.tax_class as TaxClass);
  const [flash, setFlash] = useState(false);

  const sig = JSON.stringify({ amount, compare, tax });
  const [savedSig, setSavedSig] = useState(sig);
  const save = useCallback(async () => {
    try {
      await api.updateArticlePrice(articleObjectId, price.id, {
        amount_chf: amount, compare_at_chf: compare.trim() || null, tax_class: tax,
      });
      setSavedSig(JSON.stringify({ amount, compare, tax }));
      setFlash(true); setTimeout(() => setFlash(false), 700);
      onChanged();
    } catch { /* belassen */ }
  }, [articleObjectId, price.id, amount, compare, tax, onChanged]);
  const flush = useAutosave(sig, sig !== savedSig && !!amount.trim(), save);

  async function makePrimary() {
    await api.updateArticlePrice(articleObjectId, price.id, { is_primary: true });
    onChanged();
  }
  async function remove() {
    await api.deleteArticlePrice(articleObjectId, price.id);
    onChanged();
  }

  return (
    <div style={{ border: `1px solid ${price.is_primary ? '#bfdbfe' : '#e2e8f0'}`, borderRadius: 8, padding: 12,
      background: price.is_primary ? '#f8fbff' : '#fff', boxShadow: flash ? 'inset 0 0 0 2px #16a34a' : 'none', transition: 'box-shadow .2s', display: 'flex', flexDirection: 'column', gap: 10 }}
      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); flush(); } }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#0f172a' }}>
          {price.kind === 'subscription' ? `Abo (${price.interval === 'year' ? 'jährlich' : 'monatlich'})` : 'Einmalkauf'}
        </span>
        {price.is_primary
          ? <span style={{ fontSize: 10, fontWeight: 700, color: '#2563eb', background: '#eff6ff', padding: '2px 7px', borderRadius: 999 }}>Hauptpreis</span>
          : <button onClick={makePrimary} style={{ fontSize: 11, color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer' }}>Als Hauptpreis</button>}
        <button onClick={remove} title="Preis entfernen" style={{ marginLeft: 'auto', border: '1px solid #e2e8f0', background: '#fff', borderRadius: 7, padding: '5px 7px', color: '#94a3b8', cursor: 'pointer' }}>
          <Trash2 size={14} />
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <TextField label="Preis (CHF, netto)" value={amount} onChange={setAmount} placeholder="199.00" />
        <TextField label="Vergleichspreis" value={compare} onChange={setCompare} placeholder="optional" />
      </div>
      <SelectField label="Steuerklasse" value={tax} onChange={(v) => setTax(v as TaxClass)}
        options={(Object.keys(TAX_LABEL) as TaxClass[]).map((k) => ({ value: k, label: TAX_LABEL[k] }))} />
    </div>
  );
}

// ─── Zielgruppe (private/unlisted) ───────────────────────────────────────────────

function AudienceCard({ articleObjectId, audience, customers, onChanged }: {
  articleObjectId: number; audience: AudienceMember[]; customers: UserProfile[]; onChanged: () => void;
}) {
  const [pick, setPick] = useState('');
  const assignedIds = new Set(audience.map((a) => a.user_id));
  const options = customers.filter((c) => !assignedIds.has(c.id)).map((c) => ({
    value: String(c.id),
    label: [c.first_name, c.last_name].filter(Boolean).join(' ') || c.company_name || c.email,
  }));

  async function add(userId: string) {
    setPick('');
    await api.addArticleAudience(articleObjectId, Number(userId));
    onChanged();
  }
  async function remove(rowId: number) {
    await api.removeArticleAudience(articleObjectId, rowId);
    onChanged();
  }

  return (
    <div style={card}>
      <SectionTitle icon={Lock} info="Nur diese Kunden sehen das Produkt (bei privater/verborgener Sichtbarkeit).">Zielgruppe</SectionTitle>
      {audience.length === 0 && <div style={{ fontSize: 12, color: '#94a3b8' }}>Noch keine Kunden zugewiesen.</div>}
      {audience.map((a) => (
        <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
          <span style={{ color: '#0f172a', fontWeight: 600 }}>{a.name ?? a.email ?? `#${a.user_id}`}</span>
          {a.email && a.name && <span style={{ color: '#94a3b8', fontSize: 12 }}>{a.email}</span>}
          <button onClick={() => remove(a.id)} title="Entfernen" style={{ marginLeft: 'auto', border: '1px solid #e2e8f0', background: '#fff', borderRadius: 7, padding: '4px 7px', color: '#94a3b8', cursor: 'pointer' }}>
            <Trash2 size={13} />
          </button>
        </div>
      ))}
      <SearchSelect label="Kunde hinzufügen" value={pick} onChange={add} options={options} placeholder="Kunde suchen…" />
    </div>
  );
}

// ─── Preis-Vorschau (CHF/EUR/USD …) ──────────────────────────────────────────────

function PreviewCard({ previews }: { previews: PriceView[] }) {
  if (!previews || previews.length === 0) return null;
  return (
    <div style={card}>
      <SectionTitle icon={Coins} info="Berechneter Anzeige-Preis je Shop-Währung (Tageskurs, schön gerundet, inkl. CH-MWST).">Vorschau</SectionTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {previews.map((v) => (
          <div key={v.currency} style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 13 }}>
            <span style={{ width: 44, fontWeight: 700, color: '#475569' }}>{v.currency}</span>
            <span style={{ fontSize: 15, fontWeight: 700, color: '#0f766e' }}>{fmtMoney(v.gross, v.currency)}</span>
            {v.compare_at != null && (
              <span style={{ color: '#94a3b8', textDecoration: 'line-through' }}>{fmtMoney(v.compare_at, v.currency)}</span>
            )}
            <span style={{ marginLeft: 'auto', fontSize: 11, color: '#94a3b8' }}>
              netto {fmtMoney(v.net, v.currency)} · MWST {Number(v.tax_rate)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
