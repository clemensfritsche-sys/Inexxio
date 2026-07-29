'use client';

/**
 * **Verkauf** – die lebende Verkaufs-Ebene am Artikel (Profil · Preise · Zielgruppe).
 *
 * Gestaltungsregel dieses Reiters (Design-System «weniger ist mehr»): jede Wahl ist eine
 * Reihe **Symbol-Chips** statt Dropdown/Segment, und jede Erklärung sitzt im **Hover** des
 * Chips – nicht als Absatz in der Fläche. Vorher standen unter jedem Feld ein bis zwei
 * Sätze Fliesstext; auf einen Blick war dadurch nicht erkennbar, was überhaupt eingestellt
 * ist. Gespeichert wird ausschliesslich per **Auto-Save** (kein Speichern-Knopf).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Tag, Plus, Trash2, Globe, Lock, Image as ImageIcon, Coins, Eye, EyeOff,
  Hammer, Warehouse, RefreshCw, CalendarDays, CalendarRange, KeyRound, PackageCheck,
  Star, X,
} from 'lucide-react';
import { api } from '@/lib/api';
import type {
  ArticleSalesProfile, ArticlePrice, AudienceMember,
  SalesVisibility, SalesFulfillment, SalesContent, SalesContentBlock,
  PriceKind, PriceInterval, PriceSubType, UserProfile,
} from '@/types';
import { Label, TextField, SectionTitle, Placeholder, IconSwitch } from '@/components/erp/fields';
import { PhotoCapture } from '@/components/erp/photo-capture';
import { AiImageAssist } from '@/components/ai/image-assist';
import { useAutosave } from '@/lib/use-autosave';

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
  if (loading) return <div style={{ padding: 16, fontSize: 13, color: 'var(--fg-4)' }}>Lädt…</div>;
  if (!profile) return <div style={{ padding: 16, fontSize: 13, color: 'var(--danger)' }}>{error ?? 'Kein Profil'}</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, maxWidth: 980, marginInline: 'auto' }}>
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
  background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)',
  padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14,
};

// ─── Symbol-Wahl: EINE Zeile Chips, Erklärung im Hover ───────────────────────────

type Choice<T extends string> = { value: T; label: string; icon: React.ElementType; hint: string };

/**
 * **Schieberegler statt Chip-Reihe** (Notizen #159–#161): dass die Optionen einander
 * ausschliessen, zeigt die Bewegung des Reiters – nicht ein zweiter Rahmen. Es ist
 * derselbe `IconSwitch` wie am Bedarf und am Beschaffungs-Schritt: gleiche Bedeutung,
 * gleiche Form. Die Erklärung sitzt im Hover, nie in der Fläche.
 */
function IconChoice<T extends string>({ label, value, onChange, options }: {
  label: string; value: T; onChange: (v: T) => void; options: Choice<T>[];
}) {
  return (
    <div>
      <Label>{label}</Label>
      <IconSwitch value={value} onChange={onChange} options={options} />
    </div>
  );
}

// «Sichtbar / Nicht sichtbar» – dieselben Wörter wie überall sonst, wenn es um
// Sichtbarkeit geht. Der Ausgangszustand (nicht sichtbar) steht LINKS: Listen liest man
// von links, und ein Artikel ist erst einmal nicht im Shop.
const PUBLISHED: Choice<'true' | 'false'>[] = [
  { value: 'false', label: 'Nicht sichtbar', icon: EyeOff, hint: 'Nicht im Shop – nur intern sichtbar.' },
  { value: 'true', label: 'Sichtbar', icon: Eye, hint: 'Im Shop auffindbar und kaufbar.' },
];

const VISIBILITY: Choice<SalesVisibility>[] = [
  { value: 'public', label: 'Öffentlich', icon: Globe, hint: 'Für alle im Shop sichtbar.' },
  { value: 'private', label: 'Privat', icon: Lock, hint: 'Nur zugewiesene Kunden sehen es.' },
];

const FULFILLMENT: Choice<SalesFulfillment>[] = [
  { value: 'make', label: 'Auf Bestellung', icon: Hammer,
    hint: 'Made-to-Order: jeder Kauf erzeugt die Einheiten – kein Lager nötig.' },
  { value: 'stock', label: 'Ab Lager', icon: Warehouse,
    hint: 'Ab Lager (FIFO): der Verkauf bedient sich aus dem Bestand, bis dieser erschöpft ist.' },
];

const KIND: Choice<PriceKind>[] = [
  { value: 'one_time', label: 'Einmalkauf', icon: Coins, hint: 'Einmalige Zahlung.' },
  { value: 'subscription', label: 'Abo', icon: RefreshCw, hint: 'Wiederkehrende Zahlung.' },
];

const INTERVAL: Choice<PriceInterval>[] = [
  { value: 'month', label: 'Monatlich', icon: CalendarDays, hint: 'Abrechnung jeden Monat.' },
  { value: 'year', label: 'Jährlich', icon: CalendarRange, hint: 'Abrechnung einmal im Jahr.' },
];

const SUB_TYPE: Choice<PriceSubType>[] = [
  { value: 'usage', label: 'Nutzung', icon: KeyRound, hint: 'Nutzungsabo: Zugang oder Miete, einmalige Erfüllung.' },
  { value: 'product', label: 'Lieferung', icon: PackageCheck, hint: 'Produktabo: je Zyklus wird erneut geliefert.' },
];

/** Grüner Rahmen-Flash nach dem Auto-Save – die einzige Speicher-Rückmeldung. */
function flashStyle(on: boolean): React.CSSProperties {
  return { boxShadow: on ? 'inset 0 0 0 2px var(--success)' : 'none', transition: 'box-shadow .2s' };
}

// ─── Profil: Status + Sichtbarkeit + Verfügbarkeit + Inhalt (einsprachig) ────────

function ProfileCard({ profile, onSaved, onVisibilityChange, articleObjectId }: {
  profile: ArticleSalesProfile; onSaved: (p: ArticleSalesProfile) => void;
  onVisibilityChange: (v: SalesVisibility) => void; articleObjectId: number;
}) {
  const [published, setPublished] = useState(profile.sales_published);
  const [visibility, setVisibility] = useState<SalesVisibility>(profile.sales_visibility);
  const [content, setContent] = useState<SalesContent>(profile.sales_content ?? { de: emptyBlock() });
  const [fulfillment, setFulfillment] = useState<SalesFulfillment>(profile.sales_fulfillment);
  const [flash, setFlash] = useState(false);

  // Einsprachig (KI-Übersetzung folgt später): Inhalt wird im Block 'de' gepflegt.
  const block = content.de ?? emptyBlock();
  function setBlock(patch: Partial<SalesContentBlock>) {
    setContent((c) => ({ ...c, de: { ...(c.de ?? emptyBlock()), ...patch } }));
  }

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
    <div style={{ ...card, ...flashStyle(flash) }}
      onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); flush(); } }}>
      <SectionTitle icon={Tag} info="Der Verkauf bleibt auch nach der Freigabe editierbar – nur Spezifikation und Prozess sind eingefroren. Erklärungen zu den Optionen stehen im Hover.">Verkauf</SectionTitle>

      {/* Drei binäre Achsen nebeneinander – auf einen Blick erfassbar. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 230px), 1fr))', gap: 14 }}>
        <IconChoice label="Status" value={published ? 'true' : 'false'} options={PUBLISHED}
          onChange={(v) => setPublished(v === 'true')} />
        <IconChoice label="Sichtbarkeit" value={visibility} options={VISIBILITY}
          onChange={(v) => { setVisibility(v); onVisibilityChange(v); }} />
        <IconChoice label="Verfügbarkeit" value={fulfillment} options={FULFILLMENT}
          onChange={setFulfillment} />
      </div>

      <div style={{ borderTop: '1px solid var(--border-1)', paddingTop: 14 }}>
        <SectionTitle icon={ImageIcon}>Inhalt</SectionTitle>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))', gap: 10 }}>
            <TextField label="Titel" value={block.title ?? ''} onChange={(v) => setBlock({ title: v })} placeholder="Produkttitel" />
            <TextField label="Untertitel" value={block.subtitle ?? ''} onChange={(v) => setBlock({ subtitle: v })} placeholder="kurzer Zusatz" />
          </div>
          <div>
            <Label>Beschreibung</Label>
            <textarea value={block.description ?? ''} onChange={(e) => setBlock({ description: e.target.value })}
              onBlur={flush} rows={3} placeholder="Produktbeschreibung"
              className="w-full rounded-ds-md border border-border-1 bg-white px-2.5 py-1.5 text-sm text-fg-1 outline-none placeholder:text-fg-4 focus:ring-2 focus:ring-accent"
              style={{ resize: 'vertical' }} />
          </div>
          <div>
            <Label>Produktbilder</Label>
            <PhotoCapture value={block.images ?? []} max={10} onChange={(urls) => setBlock({ images: urls })} />
            {/* KI-Bildbearbeitung (Gemini): erzeugt eine bearbeitete Kopie als neues Bild. */}
            <AiImageAssist images={block.images ?? []}
              onAdd={(url) => setBlock({ images: [...(block.images ?? []), url] })} />
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

  return (
    <div style={card}>
      <SectionTitle icon={Coins}>Preise</SectionTitle>
      {prices.map((p) => (
        <PriceRow key={p.id} articleObjectId={articleObjectId} price={p} onChanged={onChanged} />
      ))}

      {adding ? (
        <NewPriceRow articleObjectId={articleObjectId} isFirst={prices.length === 0}
          onDone={() => { setAdding(false); onChanged(); }} onCancel={() => setAdding(false)} />
      ) : (
        <button onClick={() => setAdding(true)}
          style={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 6, padding: '7px 13px',
            borderRadius: 'var(--r-md)', border: '1px solid var(--border-1)', background: '#fff',
            color: 'var(--accent-ink)', font: '600 12.5px var(--font-body)', cursor: 'pointer' }}>
          <Plus size={14} /> Preis hinzufügen
        </button>
      )}
    </div>
  );
}

/**
 * Neuer Preis – **ohne Speichern-Knopf**, wie überall sonst im ERP. Angelegt wird, sobald
 * ein gültiger Betrag steht: sofort bei Enter oder beim Verlassen des Feldes, sonst nach
 * einer bewusst längeren Denkpause (2,5 s statt 1,5 s), damit eine halb getippte Zahl
 * nicht als Preis committet wird. Das «X» schliesst die Zeile nur – es verwirft nichts,
 * was schon existierte.
 */
function NewPriceRow({ articleObjectId, isFirst, onDone, onCancel }: {
  articleObjectId: number; isFirst: boolean; onDone: () => void; onCancel: () => void;
}) {
  const [kind, setKind] = useState<PriceKind>('one_time');
  const [interval, setInterval] = useState<PriceInterval>('month');
  const [subType, setSubType] = useState<PriceSubType>('usage');
  const [amount, setAmount] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const created = useRef(false);

  const valid = Number(amount.replace(',', '.')) > 0;
  const sig = JSON.stringify({ kind, interval, subType, amount });

  const create = useCallback(async () => {
    if (created.current) return;
    created.current = true;
    try {
      await api.createArticlePrice(articleObjectId, {
        kind,
        interval: kind === 'subscription' ? interval : null,
        sub_type: kind === 'subscription' ? subType : null,
        amount_chf: amount, compare_at_chf: null,
        is_primary: isFirst,
      });
      onDone();
    } catch (e) {
      created.current = false;      // erneut versuchbar (z. B. «19,x»)
      setErr(e instanceof Error ? e.message : 'Preis konnte nicht angelegt werden');
    }
  }, [articleObjectId, kind, interval, subType, amount, isFirst, onDone]);

  const flush = useAutosave(sig, valid, create, 2500);

  return (
    <div style={{ border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', padding: 12, display: 'flex', flexDirection: 'column', gap: 12 }}
      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); flush(); } }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <IconChoice label="Art" value={kind} onChange={setKind} options={KIND} />
        </div>
        <button onClick={onCancel} title="Zeile schliessen" aria-label="Zeile schliessen"
          style={{ border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer', padding: 4 }}>
          <X size={15} />
        </button>
      </div>
      {kind === 'subscription' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 230px), 1fr))', gap: 12 }}>
          <IconChoice label="Intervall" value={interval} onChange={setInterval} options={INTERVAL} />
          <IconChoice label="Abo-Typ" value={subType} onChange={setSubType} options={SUB_TYPE} />
        </div>
      )}
      <div style={{ maxWidth: 240 }}>
        <TextField label="Preis (CHF)" value={amount} onChange={setAmount} placeholder="z. B. 199.00" />
      </div>
      {err && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{err}</div>}
    </div>
  );
}

function PriceRow({ articleObjectId, price, onChanged }: {
  articleObjectId: number; price: ArticlePrice; onChanged: () => void;
}) {
  const isSub = price.kind === 'subscription';
  const [amount, setAmount] = useState(String(price.amount_chf));
  const [subType, setSubType] = useState<PriceSubType>((price.sub_type as PriceSubType) ?? 'usage');
  const [interval, setInterval] = useState<PriceInterval>((price.interval as PriceInterval) ?? 'month');
  const [flash, setFlash] = useState(false);
  const [rowErr, setRowErr] = useState<string | null>(null);

  const sig = JSON.stringify({ amount, subType, interval });
  const [savedSig, setSavedSig] = useState(sig);
  const save = useCallback(async () => {
    try {
      await api.updateArticlePrice(articleObjectId, price.id, {
        amount_chf: amount,
        ...(isSub ? { sub_type: subType, interval } : {}),
      });
      setSavedSig(JSON.stringify({ amount, subType, interval }));
      setFlash(true); setTimeout(() => setFlash(false), 700);
      onChanged();
    } catch (e) { setRowErr(e instanceof Error ? e.message : 'Fehler beim Speichern'); }
  }, [articleObjectId, price.id, amount, subType, interval, isSub, onChanged]);
  const flush = useAutosave(sig, sig !== savedSig && !!amount.trim(), save);

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

  const KindIcon = isSub ? RefreshCw : Coins;
  return (
    <div style={{
      border: `1px solid ${price.is_primary ? 'var(--accent)' : 'var(--border-1)'}`, borderRadius: 'var(--r-md)',
      padding: 12, background: price.is_primary ? 'var(--accent-soft)' : '#fff',
      display: 'flex', flexDirection: 'column', gap: 12, ...flashStyle(flash),
    }}
      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); flush(); } }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <KindIcon size={15} style={{ color: 'var(--fg-3)' }} />
        <span style={{ font: '700 12.5px var(--font-body)', color: 'var(--fg-1)' }}>
          {isSub ? (subType === 'product' ? 'Produktabo' : 'Nutzungsabo') : 'Einmalkauf'}
        </span>
        {/* Hauptpreis: Symbol statt Wortmarke – gefüllt = ist es, leer = zum Setzen. */}
        <button onClick={price.is_primary ? undefined : makePrimary}
          title={price.is_primary ? 'Hauptpreis – wird im Shop zuerst gezeigt' : 'Als Hauptpreis setzen'}
          aria-label={price.is_primary ? 'Hauptpreis' : 'Als Hauptpreis setzen'}
          style={{ border: 'none', background: 'none', padding: 2, display: 'inline-flex',
            cursor: price.is_primary ? 'default' : 'pointer',
            color: price.is_primary ? 'var(--warning)' : 'var(--fg-4)' }}>
          <Star size={14} fill={price.is_primary ? 'currentColor' : 'none'} />
        </button>
        {rowErr && <span style={{ fontSize: 11, color: 'var(--danger)' }}>{rowErr}</span>}
        <button onClick={remove} title="Preis entfernen" aria-label="Preis entfernen"
          style={{ marginLeft: 'auto', border: '1px solid var(--border-1)', background: '#fff',
            borderRadius: 'var(--r-sm)', padding: '5px 7px', color: 'var(--fg-4)', cursor: 'pointer' }}>
          <Trash2 size={14} />
        </button>
      </div>
      {isSub && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 230px), 1fr))', gap: 12 }}>
          <IconChoice label="Intervall" value={interval} onChange={setInterval} options={INTERVAL} />
          <IconChoice label="Abo-Typ" value={subType} onChange={setSubType} options={SUB_TYPE} />
        </div>
      )}
      <div style={{ maxWidth: 240 }}>
        <TextField label="Preis (CHF)" value={amount} onChange={setAmount} placeholder="199.00" />
      </div>
    </div>
  );
}

// ─── Zielgruppe (private) – Mehrfachauswahl per Klick ────────────────────────────

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
      {err && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{err}</div>}
      <TextField label="" value={q} onChange={setQ} placeholder="Kunde suchen (Name oder E-Mail)…" />
      {customers.length === 0 && <div style={{ fontSize: 12, color: 'var(--fg-4)' }}>Keine Kunden vorhanden.</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, maxHeight: 260, overflowY: 'auto' }}>
        {list.map((c) => {
          const checked = rowByUser.has(c.id);
          return (
            <label key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 8px', borderRadius: 'var(--r-sm)',
              cursor: busy ? 'default' : 'pointer', background: checked ? 'var(--accent-soft)' : 'transparent' }}>
              <input type="checkbox" checked={checked} disabled={busy} onChange={() => toggle(c)}
                style={{ width: 16, height: 16, accentColor: 'var(--accent)', cursor: busy ? 'default' : 'pointer' }} />
              <span style={{ font: '600 13px var(--font-body)', color: 'var(--fg-1)' }}>{nameOf(c)}</span>
              {c.email && <span style={{ fontSize: 12, color: 'var(--fg-4)' }}>{c.email}</span>}
            </label>
          );
        })}
        {list.length === 0 && customers.length > 0 && (
          <div style={{ fontSize: 12, color: 'var(--fg-4)', padding: '4px 8px' }}>Kein Treffer.</div>
        )}
      </div>
    </div>
  );
}
