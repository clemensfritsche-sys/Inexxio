'use client';

import { useEffect, useMemo, useState } from 'react';
import type { ReactNode, ElementType } from 'react';
import {
  Boxes, ArrowLeft, FileText, MapPin, Package, CalendarDays, History,
  ClipboardList, ChevronRight, ArrowUpRight, QrCode, TriangleAlert, ClipboardPlus,
  ArrowDownWideNarrow, ArrowUpWideNarrow, Loader2, Info, Hash, FolderOpen,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, InstanceOrderRef, LocationType, ObjectDocument, CompanySettings, DocumentContent } from '@/types';
import { instanceStatusConfig, LOCATION_META } from '@/lib/process';
import { orderStatusConfig } from '@/lib/order';
import { ObjectDocuments } from '@/components/erp/object-documents';
import { ObjectReferences } from '@/components/erp/object-references';
import { InstanceLocationsCard } from '@/components/erp/instance-locations';
import { DocumentView } from '@/components/erp/document-editor';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { fmtObjId } from '@/components/erp/user-detail';

type InstTab = 'spec' | 'orders' | 'verwendung' | 'docs';
import { useErpNav } from '@/components/erp/obj-id';
import { printObjectLabel } from '@/components/scan/object-label';
import { cn, localDate, timeAgo } from '@/lib/utils';

/**
 * Instanz-Detail – bewusst EINE Ansicht (keine Reiter): Eine Instanz ist die
 * **Summe aller Prozesse**, und Prozesse werden ausschliesslich durch **Aufträge**
 * angestossen. Kopf mit Status, «Auf einen Blick»-Kacheln (Spezifikation, Standort,
 * Bestand, Erstellt, letzte Bewegung) und die **vollständige Liste der Aufträge**,
 * die diese Instanz angefasst haben (sortierbar). Aktionen an einer Instanz
 * (verschrotten, verkaufen, …) laufen ausschliesslich über einen Auftrag – hier
 * gibt es daher nur die «Abweichung melden»-Abkürzung (ein Unter-Auftrag).
 * Design: Inexxio Design System (Instanz-Detail-Redesign).
 */
export function InstanceDetail({ record, onBack, onChanged }: {
  record: Instance;
  onBack: () => void;
  onChanged?: () => void;   // Feed/Listen aktualisieren (z. B. nach Anlage einer Abweichung)
}) {
  const inst = record;
  const nav = useErpNav();
  const [orders, setOrders] = useState<InstanceOrderRef[] | null>(null);
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');   // Aufträge: neueste ↔ älteste zuerst
  const [devBusy, setDevBusy] = useState(false);
  const [devErr, setDevErr] = useState<string | null>(null);
  const [orderBusy, setOrderBusy] = useState(false);
  const [tab, setTab] = useState<InstTab>('spec');
  // Ist diese Instanz ein erstelltes Dokument, IST sie dieses Dokument – wir zeigen den
  // Inhalt direkt in der Spezifikation (die «Essenz» dieser digitalen Instanz).
  const [genDoc, setGenDoc] = useState<ObjectDocument | null>(null);
  const [company, setCompany] = useState<Partial<CompanySettings> | null>(null);

  useEffect(() => {
    if (inst.object_id == null) return;
    let cancelled = false;
    api.getInstanceOrders(inst.object_id)
      .then((o) => { if (!cancelled) setOrders(o); })
      .catch(() => { if (!cancelled) setOrders([]); });
    api.getObjectDocuments(inst.object_id)
      .then((docs) => { if (!cancelled) setGenDoc(docs.find((d) => d.kind === 'generated' && d.content) ?? null); })
      .catch(() => { if (!cancelled) setGenDoc(null); });
    return () => { cancelled = true; };
  }, [inst.object_id]);

  useEffect(() => {
    if (!genDoc) return;
    let alive = true;
    api.getPublicSettings().then((s) => { if (alive) setCompany(s); }).catch(() => {});
    return () => { alive = false; };
  }, [genDoc]);

  const status = instanceStatusConfig(inst.quality, inst.disposition, (inst.reserved_quantity ?? 0) > 0);
  const LocIcon = LOCATION_META[(inst.location_type as LocationType)]?.icon ?? MapPin;
  const distributed = (inst.locations?.length ?? 0) > 1;

  // Aufträge sortiert nach Zeitpunkt (an), Richtung umschaltbar.
  const sortedOrders = useMemo(() => {
    const list = [...(orders ?? [])];
    list.sort((a, b) => {
      const ta = a.at ? new Date(a.at).getTime() : 0;
      const tb = b.at ? new Date(b.at).getTime() : 0;
      return sortDir === 'desc' ? tb - ta : ta - tb;
    });
    return list;
  }, [orders, sortDir]);
  const latestOrder = useMemo(() => {
    return [...(orders ?? [])].sort((a, b) => (b.at ? new Date(b.at).getTime() : 0) - (a.at ? new Date(a.at).getTime() : 0))[0] ?? null;
  }, [orders]);

  // Bestand: zählbar nur, wenn freigegeben UND am Lager.
  const inStock = inst.quality === 'passed' && inst.disposition === 'in_stock';
  const bestand = inStock ? inst.quantity : 0;
  const bestandSub =
    inst.disposition === 'sold' ? 'Verkauft – nicht mehr am Lager'
    : inst.disposition === 'scrapped' ? 'Verschrottet'
    : inst.disposition === 'consumed' ? 'Verbaut'
    : inst.quality === 'failed' ? 'Qualität: durchgefallen'
    : inStock ? ((inst.reserved_quantity ?? 0) > 0 ? `${inst.reserved_quantity} reserviert` : 'Am Lager')
    : 'In Arbeit';

  // Eine Abweichung an genau dieser Instanz läuft – wie jede Aktion – über einen Auftrag:
  // einen Unter-Auftrag am (Herkunfts-)Auftrag, der freigegeben/abgeschlossen ist.
  const deviationParent = (orders ?? []).find((o) => o.status === 'released' || o.status === 'completed') ?? null;

  async function reportDeviation() {
    if (!deviationParent || inst.object_id == null) return;
    setDevBusy(true);
    setDevErr(null);
    try {
      const devi = await api.createDeviation(deviationParent.object_id, [inst.object_id]);
      onChanged?.();
      if (devi.object_id != null) nav?.(devi.object_id);
    } catch (e) {
      setDevErr(e instanceof Error ? e.message : 'Abweichung konnte nicht eröffnet werden');
    } finally {
      setDevBusy(false);
    }
  }

  // Shortcut «Auftrag»: aus dieser Instanz direkt einen Auftrag auslösen, der auf **genau
  // sie** wirkt (bewegen, prüfen, verschrotten, verkaufen …). Sinnvoll, sobald sie am Lager
  // freigegeben ist (in_stock) oder verkauft ist (→ Retoure). Der Auftrag entsteht als
  // Entwurf mit der Instanz als fixiertem Subjekt; den Ablauf wählt der Nutzer dort.
  const canOrderInstance = (inst.quality === 'passed' && inst.disposition === 'in_stock')
    || inst.disposition === 'sold';

  async function createOrderShortcut() {
    if (!canOrderInstance || inst.object_id == null || inst.article_id == null || orderBusy) return;
    setOrderBusy(true);
    setDevErr(null);
    try {
      const qty = inst.quantity && inst.quantity > 0 ? inst.quantity : 1;
      const order = await api.createOrder({ article_id: inst.article_id, quantity: qty });
      if (order.object_id != null) {
        await api.updateOrder(order.object_id,
          { instance_object_ids: [inst.object_id], expected_updated_at: order.updated_at });
        onChanged?.();
        nav?.(order.object_id);
      }
    } catch (e) {
      setDevErr(e instanceof Error ? e.message : 'Auftrag konnte nicht angelegt werden');
    } finally {
      setOrderBusy(false);
    }
  }

  const StatusIcon = status.icon;

  return (
    <div className="flex flex-col h-full bg-bg-1" style={{ color: 'var(--fg-1)' }}>
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div style={S.dhead}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm mb-3 md:hidden" style={{ color: 'var(--accent)' }}>
          <ArrowLeft size={15} /> Zurück
        </button>
        <div style={S.dheadTop}>
          <div style={S.dico}><Boxes size={26} /></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={S.eyebrow}>Instanz</div>
            <h1 style={S.dtitle}>{inst.article_name ?? 'Instanz'}</h1>
            <div style={S.dsub}>
              <span style={S.dsubN}>{fmtObjId(inst.object_id ?? null)}</span>
              <span style={S.idsep} />
              <button className="erp-idbtn" data-tip="Etikett drucken (QR)" data-tip-pos="bottom" aria-label="Etikett drucken"
                onClick={() => inst.object_id != null && printObjectLabel(inst.object_id, inst.article_name, 'Instanz')}>
                <QrCode size={15} />
              </button>
              {/* Shortcut «Auftrag»: direkt einen Auftrag auf diese Instanz auslösen. */}
              <button className="erp-idbtn" data-tip-pos="bottom"
                data-tip={canOrderInstance ? 'Auftrag auf diese Instanz anlegen' : 'Auftrag möglich, sobald die Instanz am Lager (freigegeben) oder verkauft ist'}
                aria-label="Auftrag auf diese Instanz anlegen"
                disabled={!canOrderInstance || orderBusy}
                style={canOrderInstance ? { color: 'var(--accent)' } : undefined}
                onClick={createOrderShortcut}>
                {orderBusy ? <Loader2 size={15} className="animate-spin" /> : <ClipboardPlus size={15} />}
              </button>
              <button
                className="erp-idbtn erp-idbtn-flag"
                data-tip={deviationParent ? 'Abweichung melden (Defekt / Nacharbeit / Reklamation)' : 'Abweichung erst nach Freigabe eines Auftrags möglich'}
                data-tip-pos="bottom"
                aria-label="Abweichung melden"
                disabled={!deviationParent || devBusy}
                onClick={reportDeviation}
              >
                {devBusy ? <Loader2 size={15} className="animate-spin" /> : <TriangleAlert size={15} />}
              </button>
            </div>
          </div>
          <div style={{ flex: 'none' }}>
            <span style={{ ...S.statusbig, background: status.bg, color: status.color }}>
              {StatusIcon && <StatusIcon size={15} strokeWidth={2.5} />}{status.label}
            </span>
          </div>
        </div>
        {devErr && <div style={S.devErr}>{devErr}</div>}
        <DetailTabs<InstTab> style={{ marginTop: 16 }} active={tab} onChange={setTab} tabs={[
          { key: 'spec', label: 'Spezifikation', icon: FileText },
          { key: 'orders', label: 'Aufträge', icon: ClipboardList },
          { key: 'verwendung', label: 'Verwendung', icon: Boxes },
          { key: 'docs', label: 'Dokumente', icon: FolderOpen },
        ]} />
      </div>

      {/* ── Body ───────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto pb-20" style={{ background: 'var(--bg-1)' }}>
        <div style={S.body}>
          {tab === 'verwendung' && (
            <ObjectReferences objectId={inst.object_id ?? null} emptyHint="Nichts an dieser Instanz verortet (kein Inhalt / leerer Behälter)." />
          )}
          {tab === 'docs' && (
            <ObjectDocuments objectId={inst.object_id ?? null} contextLabel="dieser Instanz" />
          )}
          {/* Auf einen Blick */}
          {tab === 'spec' && (
          <>
          {genDoc && (
            <div style={{ marginBottom: 24 }}>
              <DocumentView content={genDoc.content as unknown as DocumentContent} company={company}
                objectNr={fmtObjId(inst.object_id)} issuedAt={genDoc.created_at ?? null} signoffs={genDoc.signoffs} />
            </div>
          )}
          <div style={S.glance}>
            <Tile
              wide icon={FileText} label="Spezifikation"
              value={inst.article_name ?? 'Artikel'}
              sub={inst.article_object_id != null ? fmtObjId(inst.article_object_id) : undefined} subMono
              onClick={inst.article_object_id != null ? () => nav?.(inst.article_object_id as number) : undefined}
            />
            <Tile
              icon={LocIcon} label="Standort"
              hint={distributed ? 'Diese Charge liegt auf mehreren Standorten (siehe Karte «Standort»).' : undefined}
              value={distributed ? 'Verteilt' : (inst.location_label ?? (inst.location_type === 'place' ? 'Ort' : inst.location_id != null ? 'Objekt' : 'Nicht festgelegt'))}
              sub={distributed ? `${inst.locations?.length} Standorte`
                : inst.location_id != null ? fmtObjId(inst.location_id)
                : inst.location_type === 'place' ? 'Adresse (keine Objektnummer)' : undefined}
              subMono={!distributed && inst.location_id != null}
              onClick={!distributed && inst.location_id != null ? () => nav?.(inst.location_id as number) : undefined}
            />
            <Tile
              icon={Package} label="Bestand" hint="Zählbar nur, wenn freigegeben und am Lager."
              value={<>{bestand} <span style={S.unit}>Stk</span></>}
              sub={bestandSub}
            />
            <Tile icon={CalendarDays} label="Erstellt" value={localDate(inst.created_at)} sub={timeAgo(inst.created_at)} />
            <Tile
              icon={History} label="Letzte Bewegung" value={status.label}
              sub={[timeAgo(inst.updated_at), latestOrder ? `Auftrag ${fmtObjId(latestOrder.object_id)}` : null].filter(Boolean).join(' · ')}
            />
            {inst.serial_number && (
              <Tile icon={Hash} label="Seriennummer" value={inst.serial_number} subMono />
            )}
          </div>

          {/* Standort-Verteilung einer Charge (read-only; verteilt wird über Auftrag + Bewegung) */}
          <InstanceLocationsCard instance={inst} />
          </>
          )}

          {/* Aufträge – ohne Überschrift (der aktive Reiter benennt es bereits) */}
          {tab === 'orders' && (
          <div>
            {orders && orders.length > 1 && (
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
                <button
                  className="erp-chip"
                  style={S.sortchip}
                  onClick={() => setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))}
                  data-tip="Sortierreihenfolge umschalten"
                >
                  {sortDir === 'desc' ? <ArrowDownWideNarrow size={14} /> : <ArrowUpWideNarrow size={14} />}
                  {sortDir === 'desc' ? 'Neueste zuerst' : 'Älteste zuerst'}
                </button>
              </div>
            )}

            {orders === null ? (
              <div style={S.emptyLine}>Laden…</div>
            ) : orders.length === 0 ? (
              <div style={S.emptyLine}>Noch kein Auftrag hat diese Instanz verarbeitet.</div>
            ) : (
              <div style={S.olist}>
                {sortedOrders.map((o, i) => {
                  const cfg = orderStatusConfig(o.status);
                  const OIcon = cfg.icon;
                  const isLast = i === sortedOrders.length - 1;
                  return (
                    <button key={o.object_id} className="erp-orow" style={{ ...S.orow, ...(isLast ? { borderBottom: 'none' } : null) }} onClick={() => nav?.(o.object_id)}>
                      <div style={S.oico}><ClipboardList size={17} /></div>
                      <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
                        <div style={S.oT}>Auftrag</div>
                        <div style={S.oN}>{fmtObjId(o.object_id)}</div>
                      </div>
                      <span style={{ ...S.badge, background: cfg.bg, color: cfg.color }}>
                        {OIcon && <OIcon size={13} strokeWidth={2.5} />}{cfg.label}
                      </span>
                      <span style={S.oArrow}><ChevronRight size={18} /></span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          )}

        </div>
      </div>
    </div>
  );
}

// ── Kachel («Auf einen Blick») ─────────────────────────────────────────────────
function Tile({ icon: Icon, label, hint, value, sub, subMono, wide, onClick }: {
  icon: ElementType; label: string; hint?: string; value: ReactNode;
  sub?: string; subMono?: boolean; wide?: boolean; onClick?: () => void;
}) {
  const clickable = !!onClick;
  const Comp: ElementType = clickable ? 'button' : 'div';
  return (
    <Comp
      onClick={onClick}
      className={cn('erp-tile', clickable && 'erp-tile-link')}
      style={{ ...S.tile, ...(wide ? S.tileWide : null), ...(clickable ? S.tileLink : null) }}
    >
      <div style={S.tileIco}><Icon size={19} /></div>
      <div style={{ minWidth: 0, flex: 1, textAlign: 'left' }}>
        <div style={S.tileK}>
          {label}
          {hint && (
            <span style={S.hint} data-tip={hint}><Info size={13} /></span>
          )}
        </div>
        <div style={S.tileV}>{value}</div>
        {sub && <div style={{ ...S.tileSub, ...(subMono ? S.mono : null) }}>{sub}</div>}
      </div>
      {clickable && <span style={S.goto}><ArrowUpRight size={18} /></span>}
    </Comp>
  );
}

// ── Styles (Inexxio Design System Tokens via CSS-Vars) ─────────────────────────
const S: Record<string, React.CSSProperties> = {
  dhead: { position: 'sticky', top: 0, zIndex: 5, background: 'rgba(255,255,255,.93)', backdropFilter: 'blur(8px)', borderBottom: '1px solid var(--border-1)', padding: '20px clamp(14px, 4vw, 28px)', flexShrink: 0 },
  dheadTop: { display: 'flex', alignItems: 'flex-start', gap: 'clamp(10px, 3vw, 16px)', flexWrap: 'wrap' },
  dico: { width: 56, height: 56, borderRadius: 'var(--r-md)', background: '#E9EDEC', color: '#5E6B66', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' },
  eyebrow: { font: 'var(--overline)', letterSpacing: 'var(--tracking-overline)', textTransform: 'uppercase', color: 'var(--inexxio-red)', marginBottom: 6 },
  dtitle: { font: '800 28px var(--font-display)', letterSpacing: '-.03em', margin: 0, lineHeight: 1.05, color: 'var(--fg-1)' },
  dsub: { display: 'flex', alignItems: 'center', gap: 9, marginTop: 10 },
  dsubN: { fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--fg-3)', fontSize: 13 },
  idsep: { width: 1, height: 16, background: 'var(--border-2)', margin: '0 2px' },
  idbtn: { width: 28, height: 28, borderRadius: 'var(--r-sm)', border: 'none', background: 'transparent', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: 'var(--fg-4)', cursor: 'pointer', padding: 0 },
  idbtnFlag: {},
  idbtnDisabled: { opacity: 0.4, cursor: 'not-allowed' },
  statusbig: { display: 'inline-flex', alignItems: 'center', gap: 7, padding: '6px 13px', borderRadius: 'var(--r-pill)', font: '600 13.5px var(--font-body)', whiteSpace: 'nowrap' },
  devErr: { marginTop: 12, padding: '8px 12px', borderRadius: 'var(--r-sm)', background: 'var(--danger-bg)', color: 'var(--danger)', font: '500 12.5px var(--font-body)' },
  body: { padding: '24px clamp(14px, 4vw, 28px) 40px', maxWidth: 980 },
  glance: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 160px), 1fr))', gap: 1, background: 'var(--border-1)', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', overflow: 'hidden', marginBottom: 30 },
  tile: { background: '#fff', padding: '18px 20px', display: 'flex', gap: 14, alignItems: 'flex-start', border: 'none', width: '100%', font: 'inherit' },
  tileWide: { gridColumn: '1 / -1' },
  tileLink: { cursor: 'pointer' },
  tileIco: { width: 40, height: 40, borderRadius: 'var(--r-sm)', background: 'var(--bg-2)', color: 'var(--fg-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' },
  tileK: { font: '600 11.5px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--fg-3)', display: 'flex', alignItems: 'center', gap: 6 },
  hint: { width: 13, height: 13, color: 'var(--fg-4)', cursor: 'help', display: 'inline-flex' },
  tileV: { font: '700 18px var(--font-body)', color: 'var(--fg-1)', marginTop: 6, fontVariantNumeric: 'tabular-nums', display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  unit: { font: '600 13px var(--font-body)', color: 'var(--fg-3)' },
  tileSub: { font: '500 13px var(--font-body)', color: 'var(--fg-3)', marginTop: 3, fontVariantNumeric: 'tabular-nums' },
  mono: { fontFamily: 'var(--font-mono)' },
  goto: { marginLeft: 'auto', color: 'var(--accent)', display: 'flex', alignSelf: 'center' },
  osecHead: { display: 'flex', alignItems: 'center', gap: 11, marginBottom: 4 },
  osecIc: { width: 36, height: 36, borderRadius: 'var(--r-sm)', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' },
  osecH3: { font: '800 19px var(--font-display)', letterSpacing: '-.02em', margin: 0, color: 'var(--fg-1)' },
  ocount: { font: '700 14px var(--font-body)', color: 'var(--fg-2)', background: 'var(--bg-3)', borderRadius: 'var(--r-pill)', padding: '3px 13px', fontVariantNumeric: 'tabular-nums' },
  sortchip: { marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6, font: '600 12.5px var(--font-body)', color: 'var(--fg-3)', background: 'var(--bg-2)', border: '1px solid var(--border-1)', borderRadius: 'var(--r-pill)', padding: '5px 12px', cursor: 'pointer' },
  osecSub: { font: '500 13px var(--font-body)', color: 'var(--fg-4)', margin: '6px 0 16px 47px' },
  olist: { border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', overflow: 'hidden' },
  orow: { display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px', borderBottom: '1px solid var(--border-1)', cursor: 'pointer', background: '#fff', width: '100%', border: 'none', borderBottomWidth: 1, borderBottomStyle: 'solid', borderBottomColor: 'var(--border-1)', font: 'inherit' },
  oico: { width: 36, height: 36, borderRadius: 'var(--r-sm)', background: 'var(--accent-soft)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' },
  oT: { font: '700 14px var(--font-body)', color: 'var(--fg-1)' },
  oN: { font: 'var(--mono-sm)', color: 'var(--fg-3)', fontVariantNumeric: 'tabular-nums', marginTop: 2 },
  badge: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 10px 4px 8px', borderRadius: 'var(--r-pill)', font: '600 12px var(--font-body)', lineHeight: 1, whiteSpace: 'nowrap' },
  oArrow: { color: 'var(--fg-4)', display: 'flex', flex: 'none' },
  emptyLine: { font: '500 13px var(--font-body)', color: 'var(--fg-4)', padding: '14px 2px' },
  labelCard: { marginTop: 24, border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', padding: 18, background: '#fff' },
};
