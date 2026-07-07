'use client';

import { useCallback, useEffect, useState } from 'react';
import { Tag, Plus, Trash2, Globe, Lock, Image as ImageIcon, Coins } from 'lucide-react';
import { api } from '@/lib/api';
import type {
  ArticleSalesProfile, ArticlePrice, AudienceMember,
  SalesVisibility, SalesFulfillment, SalesContent, SalesContentBlock,
  PriceKind, PriceInterval, PriceSubType, UserProfile,
} from '@/types';
import {
  Label, TextField, SelectField, Segmented, SectionTitle, Placeholder,
} from '@/components/erp/fields';
import { PhotoCapture } from '@/components/erp/photo-capture';
import { AiImageAssist } from '@/components/ai/image-assist';
import { useAutosave } from '@/lib/use-autosave';

const VISIBILITY: { value: SalesVisibility; label: string; icon: React.ElementType; hint: string }[] = [
  { value: 'public', label: 'Öffentlich', icon: Globe, hint: 'Für alle im Shop sichtbar.' },
  { value: 'private', label: 'Privat', icon: Lock, hint: 'Nur zugewiesene Kunden sehen es.' },
];

const SUB_TYPE_LABEL: Record<PriceSubType, string> = {
  usage: 'Nutzungsabo (Zugang/Miete)', product: 'Produktabo (wiederkehrende Lieferung)',
};

function emptyBlock(): SalesContentBlock {
  return { title: '', subtitle: '', description: '', images: [] };
}

export function SalesPanel({ articleObjectId }: { articleObjectId: number | null }) {
  const [profile, setProfile] = useState<ArticleSalesProfile | null>(null);
  const [customers, setCustomers] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Live-Sichtbarkeit (sofort beim Umschalten) – damit die Zielgruppe-Karte ohne Autosave-Wartezeit erscheint.
  const [liveVis, setLiveVis] = useState<SalesVisibility>('public');

  const reload = useCallback(async () => {
    if (articleObjectId == null) return;
    try {
      const p = await api.getArticleSales(articleObjectId);
      setProfile(p);
      setLiveVis(p.sales_visibility);
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
      <ProfileCard profile={profile} onSaved={setProfile} onVisibilityChange={setLiveVis} articleObjectId={articleObjectId} />
      <PricesCard articleObjectId={articleObjectId} prices={profile.prices} onChanged={reload} />
      {liveVis === 'private' && (
        <AudienceCard articleObjectId={articleObjectId} audience={profile.audience}
          customers={customers} onChanged={reload} />
      )}
    </div>
  );
}

const card: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px',
  display: 'flex', flexDirection: 'column', gap: 12,
};

// ─── Profil: Publiziert + Sichtbarkeit + Verfügbarkeit + Inhalt (einsprachig) ────

function ProfileCard({ profile, onSaved, onVisibilityChange, articleObjectId }: {
  profile: ArticleSalesProfile; onSaved: (p: ArticleSalesProfile) => void;
  onVisibilityChange: (v: SalesVisibility) => void; articleObjectId: number;
}) {
  const [published, setPublished] = useState(profile.sales_published);
  const [visibility, setVisibility] = useState<SalesVisibility>(profile.sales_visibility);
  const [content, setContent] = useState<SalesContent>(profile.sales_content ?? { de: emptyBlock() });
  const [flash, setFlash] = useState(false);

  // Einsprachig (KI-Übersetzung folgt später): Inhalt wird im Block 'de' gepflegt.
  const block = content.de ?? emptyBlock();
  function setBlock(patch: Partial<SalesContentBlock>) {
    setContent((c) => ({ ...c, de: { ...(c.de ?? emptyBlock()), ...patch } }));
  }

  const [fulfillment, setFulfillment] = useState<SalesFulfillment>(profile.sales_fulfillment);

  const sig = JSON.stringify({ published, visibility, fulfillment, content });
  const [savedSig, setSavedSig] = useState(sig);

  const save = useCallback(async () => {
    try {
      const saved = await api.updateArticleSales(articleObjectId, {
        sales_published: published, sales_visibility: visibility,
        sales_fulfillment: fulfillment, sales_content: content,
      });
      onSaved(saved);
      setSavedSig(JSON.stringify({ published: saved.sales_published, visibility: saved.sales_visibility, fulfillment: saved.sales_fulfillment, content: saved.sales_content ?? { de: emptyBlock() } }));
      setFlash(true); setTimeout(() => setFlash(false), 700);
    } catch { /* belassen */ }
  }, [articleObjectId, published, visibility, fulfillment, content, onSaved]);

  const flush = useAutosave(sig, sig !== savedSig, save);


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
              <button key={v.value} type="button" title={v.hint}
                onClick={() => { setVisibility(v.value); onVisibilityChange(v.value); }}
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

      <div>
        <Label>Verfügbarkeit</Label>
        <Segmented label="" value={fulfillment} onChange={(v) => setFulfillment(v as SalesFulfillment)}
          options={[{ value: 'make', label: 'Auf Bestellung' }, { value: 'stock', label: 'Ab Lager' }]} />
        <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8' }}>
          {fulfillment === 'make'
            ? 'Made-to-Order: jeder Kauf erzeugt die Einheiten (kein Lager nötig).'
            : 'Ab Lager (FIFO): Verkauf bedient sich aus dem Bestand, bis dieser erschöpft ist.'}
        </div>
      </div>

      <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: 12 }}>
        <SectionTitle icon={Tag} info="Sprache folgt später (KI-Übersetzung). Aktuell einsprachig gepflegt.">Inhalt</SectionTitle>
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
            <Label>Produktbilder</Label>
            <PhotoCapture
              value={block.images ?? []}
              max={10}
              onChange={(urls) => setBlock({ images: urls })}
            />
            <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 4 }}>
              <ImageIcon size={11} /> Fotografieren oder hochladen – das erste Bild ist das Titelbild.
            </div>
            {/* KI-Bildbearbeitung (Gemini): erzeugt eine bearbeitete Kopie als neues Bild. */}
            <AiImageAssist
              images={block.images ?? []}
              onAdd={(url) => setBlock({ images: [...(block.images ?? []), url] })}
            />
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
  const [form, setForm] = useState<{ kind: PriceKind; interval: PriceInterval; subType: PriceSubType; amount: string; compare: string }>(
    { kind: 'one_time', interval: 'month', subType: 'usage', amount: '', compare: '' });

  const [err, setErr] = useState<string | null>(null);

  async function add() {
    if (!form.amount.trim()) return;
    setBusy(true); setErr(null);
    try {
      await api.createArticlePrice(articleObjectId, {
        kind: form.kind,
        interval: form.kind === 'subscription' ? form.interval : null,
        sub_type: form.kind === 'subscription' ? form.subType : null,
        amount_chf: form.amount, compare_at_chf: form.compare.trim() || null,
        is_primary: prices.length === 0,
      });
      setForm({ kind: 'one_time', interval: 'month', subType: 'usage', amount: '', compare: '' });
      setAdding(false);
      onChanged();
    // FIX: try/finally OHNE catch – ein 4xx (z. B. ungültiger Betrag «19,x») verschwand als
    // unhandled rejection, das Formular blieb kommentarlos offen. Fehler jetzt anzeigen.
    } catch (e) { setErr(e instanceof Error ? e.message : 'Preis konnte nicht angelegt werden'); }
    finally { setBusy(false); }
  }

  return (
    <div style={card}>
      <SectionTitle icon={Coins} info="Beträge sind die Netto-Basis in CHF. Stripe zeigt an der Kasse die Lokalwährung und berechnet die finale Steuer. Mehrere Optionen je Produkt sind möglich (Einmalkauf, Nutzungs-/Produktabo).">Preise</SectionTitle>
      {err && <div style={{ fontSize: 12, color: '#dc2626' }}>{err}</div>}
      {prices.length === 0 && !adding && (
        <div style={{ fontSize: 12, color: '#94a3b8' }}>Noch kein Preis – ohne Preis erscheint das Produkt nicht im Shop.</div>
      )}
      {prices.map((p) => (
        <PriceRow key={p.id} articleObjectId={articleObjectId} price={p} onChanged={onChanged} />
      ))}

      {adding ? (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))', gap: 10 }}>
            <SelectField label="Art" value={form.kind} onChange={(v) => setForm((f) => ({ ...f, kind: v as PriceKind }))}
              options={[{ value: 'one_time', label: 'Einmalkauf' }, { value: 'subscription', label: 'Abo' }]} />
            {form.kind === 'subscription' && (
              <SelectField label="Intervall" value={form.interval} onChange={(v) => setForm((f) => ({ ...f, interval: v as PriceInterval }))}
                options={[{ value: 'month', label: 'monatlich' }, { value: 'year', label: 'jährlich' }]} />
            )}
          </div>
          {form.kind === 'subscription' && (
            <SelectField label="Abo-Typ" value={form.subType} onChange={(v) => setForm((f) => ({ ...f, subType: v as PriceSubType }))}
              options={(Object.keys(SUB_TYPE_LABEL) as PriceSubType[]).map((k) => ({ value: k, label: SUB_TYPE_LABEL[k] }))} />
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))', gap: 10 }}>
            <TextField label="Preis (CHF, brutto)" value={form.amount} onChange={(v) => setForm((f) => ({ ...f, amount: v }))} placeholder="z. B. 199.00" />
            <TextField label="Vergleichspreis (optional)" value={form.compare} onChange={(v) => setForm((f) => ({ ...f, compare: v }))} placeholder="durchgestrichen" />
          </div>
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
  const isSub = price.kind === 'subscription';
  const [amount, setAmount] = useState(String(price.amount_chf));
  const [compare, setCompare] = useState(price.compare_at_chf != null ? String(price.compare_at_chf) : '');
  const [subType, setSubType] = useState<PriceSubType>((price.sub_type as PriceSubType) ?? 'usage');
  const [interval, setInterval] = useState<PriceInterval>((price.interval as PriceInterval) ?? 'month');
  const [flash, setFlash] = useState(false);

  const sig = JSON.stringify({ amount, compare, subType, interval });
  const [savedSig, setSavedSig] = useState(sig);
  const save = useCallback(async () => {
    try {
      await api.updateArticlePrice(articleObjectId, price.id, {
        amount_chf: amount, compare_at_chf: compare.trim() || null,
        ...(isSub ? { sub_type: subType, interval } : {}),
      });
      setSavedSig(JSON.stringify({ amount, compare, subType, interval }));
      setFlash(true); setTimeout(() => setFlash(false), 700);
      onChanged();
    } catch { /* belassen */ }
  }, [articleObjectId, price.id, amount, compare, subType, interval, isSub, onChanged]);
  const flush = useAutosave(sig, sig !== savedSig && !!amount.trim(), save);

  const [rowErr, setRowErr] = useState<string | null>(null);
  // FIX: schwebende Promises ohne catch – ein Backend-Fehler (z. B. Preis nicht löschbar)
  // verpuffte still als unhandled rejection. Fehler jetzt am Preis anzeigen.
  async function makePrimary() {
    try { await api.updateArticlePrice(articleObjectId, price.id, { is_primary: true }); setRowErr(null); onChanged(); }
    catch (e) { setRowErr(e instanceof Error ? e.message : 'Fehler beim Speichern'); }
  }
  async function remove() {
    try { await api.deleteArticlePrice(articleObjectId, price.id); setRowErr(null); onChanged(); }
    catch (e) { setRowErr(e instanceof Error ? e.message : 'Fehler beim Entfernen'); }
  }

  return (
    <div style={{ border: `1px solid ${price.is_primary ? '#bfdbfe' : '#e2e8f0'}`, borderRadius: 8, padding: 12,
      background: price.is_primary ? '#f8fbff' : '#fff', boxShadow: flash ? 'inset 0 0 0 2px #16a34a' : 'none', transition: 'box-shadow .2s', display: 'flex', flexDirection: 'column', gap: 10 }}
      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); flush(); } }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#0f172a' }}>
          {isSub ? (subType === 'product' ? 'Produktabo' : 'Nutzungsabo') : 'Einmalkauf'}
        </span>
        {price.is_primary
          ? <span style={{ fontSize: 10, fontWeight: 700, color: '#2563eb', background: '#eff6ff', padding: '2px 7px', borderRadius: 999 }}>Hauptpreis</span>
          : <button onClick={makePrimary} style={{ fontSize: 11, color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer' }}>Als Hauptpreis</button>}
        {rowErr && <span style={{ fontSize: 11, color: '#dc2626' }}>{rowErr}</span>}
        <button onClick={remove} title="Preis entfernen" style={{ marginLeft: 'auto', border: '1px solid #e2e8f0', background: '#fff', borderRadius: 7, padding: '5px 7px', color: '#94a3b8', cursor: 'pointer' }}>
          <Trash2 size={14} />
        </button>
      </div>
      {isSub && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))', gap: 10 }}>
          <SelectField label="Abo-Typ" value={subType} onChange={(v) => setSubType(v as PriceSubType)}
            options={(Object.keys(SUB_TYPE_LABEL) as PriceSubType[]).map((k) => ({ value: k, label: SUB_TYPE_LABEL[k] }))} />
          <SelectField label="Intervall" value={interval} onChange={(v) => setInterval(v as PriceInterval)}
            options={[{ value: 'month', label: 'monatlich' }, { value: 'year', label: 'jährlich' }]} />
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))', gap: 10 }}>
        <TextField label="Preis (CHF, brutto)" value={amount} onChange={setAmount} placeholder="199.00" />
        <TextField label="Vergleichspreis" value={compare} onChange={setCompare} placeholder="optional" />
      </div>
    </div>
  );
}

// ─── Zielgruppe (private) – Mehrfachauswahl per Checkbox ─────────────────────────

function AudienceCard({ articleObjectId, audience, customers, onChanged }: {
  articleObjectId: number; audience: AudienceMember[]; customers: UserProfile[]; onChanged: () => void;
}) {
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  // user_id → Zeilen-id der Zuweisung (für gezieltes Entfernen).
  const rowByUser = new Map(audience.map((a) => [a.user_id, a.id]));

  function nameOf(c: UserProfile): string {
    return [c.first_name, c.last_name].filter(Boolean).join(' ') || c.company_name || c.email;
  }

  const needle = q.trim().toLowerCase();
  const list = customers
    .filter((c) => !needle || nameOf(c).toLowerCase().includes(needle) || (c.email ?? '').toLowerCase().includes(needle))
    .sort((a, b) => Number(rowByUser.has(b.id)) - Number(rowByUser.has(a.id)) || nameOf(a).localeCompare(nameOf(b)));

  const [err, setErr] = useState<string | null>(null);
  async function toggle(c: UserProfile) {
    if (busy) return;
    setBusy(true); setErr(null);
    try {
      const rowId = rowByUser.get(c.id);
      if (rowId) await api.removeArticleAudience(articleObjectId, rowId);
      else await api.addArticleAudience(articleObjectId, c.id);
      onChanged();
    // FIX: try/finally ohne catch – Zuweisungs-Fehler verschwanden still.
    } catch (e) { setErr(e instanceof Error ? e.message : 'Zuweisung fehlgeschlagen'); }
    finally { setBusy(false); }
  }

  return (
    <div style={card}>
      <SectionTitle icon={Lock} info="Nur ausgewählte Kunden sehen das Produkt (bei privater Sichtbarkeit). Mehrfachauswahl per Klick.">
        Zielgruppe{audience.length > 0 ? ` (${audience.length})` : ''}
      </SectionTitle>
      {err && <div style={{ fontSize: 12, color: '#dc2626' }}>{err}</div>}
      <TextField label="" value={q} onChange={setQ} placeholder="Kunde suchen (Name oder E-Mail)…" />
      {customers.length === 0 && <div style={{ fontSize: 12, color: '#94a3b8' }}>Keine Kunden vorhanden.</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, maxHeight: 260, overflowY: 'auto' }}>
        {list.map((c) => {
          const checked = rowByUser.has(c.id);
          return (
            <label key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 8px', borderRadius: 8,
              cursor: busy ? 'default' : 'pointer', background: checked ? '#eff6ff' : 'transparent' }}
              className={busy ? '' : 'hover:bg-slate-50'}>
              <input type="checkbox" checked={checked} disabled={busy} onChange={() => toggle(c)}
                style={{ width: 16, height: 16, accentColor: '#2563eb', cursor: busy ? 'default' : 'pointer' }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>{nameOf(c)}</span>
              {c.email && <span style={{ fontSize: 12, color: '#94a3b8' }}>{c.email}</span>}
            </label>
          );
        })}
        {list.length === 0 && customers.length > 0 && (
          <div style={{ fontSize: 12, color: '#94a3b8', padding: '4px 8px' }}>Kein Treffer.</div>
        )}
      </div>
    </div>
  );
}
