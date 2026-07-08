'use client';

import { useState } from 'react';
import { MapPin, ArrowLeftRight, Loader2, Split } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, LocationType } from '@/types';
import { SearchSelect } from '@/components/erp/fields';
import { LOCATION_META } from '@/lib/process';
import { fmtObjId } from '@/components/erp/user-detail';
import { userDisplayName } from '@/lib/utils';

const TERMINAL = ['consumed', 'sold', 'scrapped'];

/**
 * Standort einer Instanz + **Teilmengen-Verlagerung** einer Charge («ein Bewegen = ein
 * Task», Variante b). Eine Charge (z. B. 1000 Schrauben) kann so über mehrere Standorte
 * verteilt werden (300 → Band A, 700 → Band B), OHNE Teilung der Instanz / ohne neue
 * Objektnummer. Der Rest bleibt, wo er war. Design: Inexxio Design System.
 */
export function InstanceMovePanel({ instance, onMoved }: {
  instance: Instance;
  onMoved: (updated: Instance) => void;
}) {
  const slices = instance.locations ?? [];
  const movable = !TERMINAL.includes(instance.disposition ?? '') && instance.object_id != null;
  const distributed = slices.length > 1;

  const [open, setOpen] = useState(false);
  const [qty, setQty] = useState('');
  const [target, setTarget] = useState('');   // "type:objectId"
  const [source, setSource] = useState('');    // Objektnummer (optional, nur bei Verteilung)
  const [opts, setOpts] = useState<{ value: string; label: string }[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function loadOptions() {
    if (opts) return;
    const [sl, us, ins] = await Promise.allSettled([
      api.getStorageLocations(), api.getUsers(), api.getInstances(),
    ]);
    const o: { value: string; label: string }[] = [];
    if (sl.status === 'fulfilled') {
      sl.value.filter((l) => l.status === 'released' && l.object_id != null).forEach((l) =>
        o.push({ value: `lagerplatz:${l.object_id}`, label: `Lagerplatz ${fmtObjId(l.object_id)}${l.note ? ` · ${l.note}` : ''}` }));
    }
    if (us.status === 'fulfilled') {
      us.value.filter((u) => u.object_id != null).forEach((u) =>
        o.push({ value: `user:${u.object_id}`, label: `Person · ${userDisplayName(u)}` }));
    }
    if (ins.status === 'fulfilled') {
      ins.value.filter((i) => i.object_id != null && i.object_id !== instance.object_id).forEach((i) =>
        o.push({ value: `instance:${i.object_id}`, label: `Instanz ${fmtObjId(i.object_id)}${i.article_name ? ` · ${i.article_name}` : ''}` }));
    }
    setOpts(o);
  }

  function toggle() {
    const next = !open;
    setOpen(next); setErr(null);
    if (next) loadOptions();
  }

  async function submit() {
    setErr(null);
    const q = Number(qty);
    if (!q || q <= 0) { setErr('Bitte eine Menge grösser als 0 eingeben.'); return; }
    if (!target) { setErr('Bitte einen Zielstandort wählen.'); return; }
    const sep = target.indexOf(':');
    const type = target.slice(0, sep) as LocationType;
    const id = Number(target.slice(sep + 1));
    setBusy(true);
    try {
      const updated = await api.moveInstancePart(instance.object_id as number, {
        quantity: q, location_type: type, location_id: id,
        from_location_id: source ? Number(source) : null,
      });
      onMoved(updated);
      setOpen(false); setQty(''); setTarget(''); setSource('');
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Verlagern fehlgeschlagen.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={ST.card}>
      <div style={ST.head}>
        <MapPin size={16} style={{ color: 'var(--fg-3)' }} />
        <h3 style={ST.title}>Standort{distributed ? ' · verteilt' : ''}</h3>
        {distributed && (
          <span style={ST.pill}>{slices.length} Standorte</span>
        )}
      </div>

      {/* Verteilung: je Standort eine Zeile mit Menge */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {slices.length === 0 ? (
          <span style={ST.empty}>Kein Standort festgelegt.</span>
        ) : (
          slices.map((s) => {
            const Icon = LOCATION_META[s.location_type as LocationType]?.icon ?? MapPin;
            return (
              <div key={`${s.location_type}:${s.location_id}`} style={ST.slice}>
                <Icon size={15} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                <span style={ST.sliceLabel}>{s.location_label ?? fmtObjId(s.location_id)}</span>
                <span style={ST.sliceNr}>{fmtObjId(s.location_id)}</span>
                <span style={ST.sliceQty}>{s.quantity}</span>
              </div>
            );
          })
        )}
      </div>

      {movable && (
        <>
          {!open ? (
            <button onClick={toggle} style={ST.moveBtn} type="button">
              <Split size={15} /> Teilmenge verlagern
            </button>
          ) : (
            <div style={ST.form}>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <div style={{ width: 120 }}>
                  <label style={ST.lbl}>Menge</label>
                  <input
                    type="number" min={0} step="any" value={qty}
                    onChange={(e) => setQty(e.target.value)}
                    placeholder="z. B. 300" autoFocus style={ST.input}
                  />
                </div>
                <div style={{ flex: 1, minWidth: 220 }}>
                  <SearchSelect
                    label="Zielstandort" value={target} onChange={setTarget}
                    options={opts ?? []} placeholder={opts ? '— wählen —' : 'Lädt…'}
                  />
                </div>
              </div>
              {distributed && (
                <SearchSelect
                  label="Quellstandort (optional)" value={source}
                  onChange={setSource}
                  options={slices.map((s) => ({
                    value: String(s.location_id),
                    label: `${s.location_label ?? fmtObjId(s.location_id)} · ${s.quantity}`,
                  }))}
                  placeholder="Automatisch (grösste Teilmenge)"
                />
              )}
              {err && <div style={ST.err}>{err}</div>}
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={submit} disabled={busy} style={ST.primary} type="button">
                  {busy ? <Loader2 size={15} className="animate-spin" /> : <ArrowLeftRight size={15} />}
                  Verlagern
                </button>
                <button onClick={() => { setOpen(false); setErr(null); }} style={ST.ghost} type="button">
                  Abbrechen
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

const ST: Record<string, React.CSSProperties> = {
  card: { border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', padding: 18, background: '#fff', display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 30 },
  head: { display: 'flex', alignItems: 'center', gap: 8 },
  title: { font: '700 15px var(--font-display)', color: 'var(--fg-1)', margin: 0 },
  pill: { marginLeft: 'auto', font: '600 11px var(--font-body)', color: 'var(--accent-ink)', background: 'var(--accent-soft)', padding: '2px 9px', borderRadius: 'var(--r-pill)' },
  empty: { font: '500 13px var(--font-body)', color: 'var(--fg-4)' },
  slice: { display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', border: '1px solid var(--border-1)', borderRadius: 'var(--r-sm)' },
  sliceLabel: { font: '600 13.5px var(--font-body)', color: 'var(--fg-1)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  sliceNr: { fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-4)', fontVariantNumeric: 'tabular-nums' },
  sliceQty: { font: '700 14px var(--font-body)', color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums', minWidth: 44, textAlign: 'right' },
  moveBtn: { alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 7, padding: '8px 14px', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-2)', background: 'var(--bg-1)', font: '600 13px var(--font-body)', color: 'var(--fg-1)', cursor: 'pointer' },
  form: { display: 'flex', flexDirection: 'column', gap: 12, padding: 14, background: 'var(--bg-2)', borderRadius: 'var(--r-sm)' },
  lbl: { display: 'block', font: '600 11.5px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--fg-3)', marginBottom: 5 },
  input: { width: '100%', padding: '9px 12px', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-2)', font: '500 14px var(--font-body)', color: 'var(--fg-1)', outline: 'none', fontVariantNumeric: 'tabular-nums' },
  err: { font: '500 12.5px var(--font-body)', color: 'var(--danger)', background: 'var(--danger-bg)', padding: '8px 12px', borderRadius: 'var(--r-sm)' },
  primary: { display: 'inline-flex', alignItems: 'center', gap: 7, padding: '9px 18px', borderRadius: 'var(--r-sm)', border: 'none', background: 'var(--inexxio-red)', color: '#fff', font: '600 13px var(--font-body)', cursor: 'pointer' },
  ghost: { padding: '9px 16px', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-2)', background: 'var(--bg-1)', font: '600 13px var(--font-body)', color: 'var(--fg-2)', cursor: 'pointer' },
};
