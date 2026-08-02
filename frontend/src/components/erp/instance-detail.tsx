'use client';

import { useEffect, useMemo, useState } from 'react';
import type { ReactNode, ElementType } from 'react';
import {
  Boxes, FileText, Package, CalendarDays,
  ClipboardList, ChevronRight, QrCode, TriangleAlert, ClipboardPlus,
  ArrowDownWideNarrow, ArrowUpWideNarrow, Loader2, Hash, FolderOpen, LockOpen,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, InstanceOrderRef, ObjectDocument, CompanySettings, DocumentContent } from '@/types';
import { instanceStatus } from '@/lib/record-status';
import { orderStatusConfig } from '@/lib/order';
import { ObjectDocuments } from '@/components/erp/object-documents';
import { ObjectReferences } from '@/components/erp/object-references';
import { LocationPathCard } from '@/components/erp/location-path';
import type { OrderSeed } from '@/components/erp/order-detail';
import { DocumentView } from '@/components/erp/document-editor';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { TileShell, TILE, DetailHeader, HeaderSep } from '@/components/erp/fields';
import { ObjId as ObjIdLink } from '@/components/erp/obj-id';

import { instanceName } from '@/lib/record-name';

type InstTab = 'spec' | 'orders' | 'verwendung' | 'docs';
import { useErpNav } from '@/components/erp/obj-id';
import { printObjectLabel } from '@/components/scan/object-label';
import { cn, formatObjectId, localDate, timeAgo } from '@/lib/utils';
import { isPending } from '@/lib/status-flow';

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
export function InstanceDetail({ record, onBack, onChanged, onCreateOrder }: {
  record: Instance;
  onBack: () => void;
  onChanged?: () => void;   // Feed/Listen aktualisieren (z. B. nach Aufheben einer Sperre)
  /** Anlage-Fenster mit dieser Instanz vorgewählt öffnen (der Auftrag entsteht erst mit
   *  der Freigabe, #386). */
  onCreateOrder?: (seed: OrderSeed) => void;
}) {
  const inst = record;
  const nav = useErpNav();
  const [orders, setOrders] = useState<InstanceOrderRef[] | null>(null);
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');   // Aufträge: neueste ↔ älteste zuerst
  const [devErr, setDevErr] = useState<string | null>(null);
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

  const status = instanceStatus(inst);

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
  // Bestand: zählbar nur, wenn freigegeben UND am Lager.
  const inStock = inst.quality === 'passed' && inst.disposition === 'in_stock';
  const bestand = inStock ? inst.quantity : 0;
  // **Die Kachel heisst, was sie misst** (Testnotiz #384): «Am Lager» – die Menge, die
  // freigegeben und entnehmbar ist. Damit erklärt sich die 0 von selbst (WARUM sagt die
  // Badge im Kopf: Im Prozess · Gesperrt · Verkauft …), das ⓘ entfällt, und die frühere
  // Unterzeile «Nicht am Lager» ist weg – sie war eine schiefe Zustandsaussage neben der
  // Badge: die Instanz IST im Betrieb, sie ist nur noch nicht verfügbar.
  // Die Unterzeile trägt nur noch, was sonst nirgends steht: die reservierte Menge.
  const reserved = inst.reserved_quantity ?? 0;
  const bestandSub = reserved > 0 ? `${reserved} reserviert` : undefined;

  // Jede Aktion an dieser Instanz läuft über einen **Auftrag** – auch die Abweichung. Den
  // legt der Shortcut unten an, mit dieser Instanz vorgewählt (Notiz #371).

  const [unblockBusy, setUnblockBusy] = useState(false);
  async function unblockInstance() {
    if (inst.object_id == null || unblockBusy) return;
    setUnblockBusy(true);
    setDevErr(null);
    try {
      await api.unblockInstance(inst.object_id);
      onChanged?.();
    } catch (e) {
      setDevErr(e instanceof Error ? e.message : 'Sperre konnte nicht aufgehoben werden');
    } finally { setUnblockBusy(false); }
  }

  // **EIN Shortcut, kein Sonderweg** (Testnotiz #371): der Knopf legt einen ganz
  // gewöhnlichen Auftrag an und trägt diese Instanz **vor** – als Eingabehilfe, nicht als
  // Fixierung. Alles Weitere (Artikel, Menge, weitere Instanzen, Ablauf) definiert man dort
  // wie bei jedem anderen Auftrag.
  //
  // Was daraus wird, sagt die Auswahl, nicht der Einstieg: eine **gebundene** Instanz (gelb –
  // in Arbeit, reserviert, gesperrt) macht den Auftrag zur **Abweichung**, eine **verkaufte**
  // zur **Retoure**, eine freie zu einem gewöhnlichen Bedarf. Darum gibt es hier auch keinen
  // zweiten Knopf «Abweichung melden» mehr und keine Bedingung ausser der einen, die
  // fachlich zählt: an verschrotteter Ware ist nichts mehr zu tun.
  const canOrderInstance = inst.disposition !== 'scrapped';
  // Reine **Vorschau** für den Knopf: gelbe Badge → daraus wird eine Abweichung. Gelesen
  // wird dieselbe Badge, die daneben steht – nicht die Regel nachgebaut (Notiz #380).
  const willDeviate = canOrderInstance && isPending(status);

  // **Der Knopf legt nichts an – er öffnet das Anlage-Fenster mit dieser Instanz vorgewählt**
  // (Testnotiz #386): einen Auftrag gibt es erst mit der Freigabe. Wer es sich anders
  // überlegt, klickt weg und es bleibt nichts zurück.
  //
  // **Immer EIN Stück vorwählen** (Testnotiz #385): der Shortcut ist eine Eingabehilfe,
  // kein Vorgriff auf die Menge. Von einer Charge à 500 will man fast nie alle 500
  // behandeln – und die Menge lässt sich im Entwurf ohnehin frei ändern (auch nach oben,
  // bis zur vollen Instanz-Menge).
  // **Die Vorauswahl nennt ihren Halter** (Testnotiz #390): ohne ihn zeigte sie auf eine
  // Zeile, die es in der Auswahl gar nicht gibt – sie zählte zur Menge, war aber nirgends
  // markiert, und bei Auftragsmenge 1 liess sich die Instanz dadurch nicht mehr anklicken.
  //
  // **Aber nur, wenn es nichts zu entscheiden gibt** (Testnotiz #394): trägt die Instanz
  // mehrere Anteile (etwa Erzeugungsauftrag *und* eine laufende Abweichung), sind das zwei
  // verschiedene Vorgänge – und seit der genannte Anteil bei der Freigabe wirklich verliert,
  // ist die Wahl der Zeile keine Formsache mehr. Raten (früher: der grösste) hiesse, dem
  // falschen Auftrag etwas wegzunehmen. Also wird dann gar nichts vorgewählt: die Auswahl
  // steht offen und der Mensch klickt die Zeile an, die er meint.
  function createOrderShortcut() {
    if (!canOrderInstance || inst.object_id == null || inst.article_id == null) return;
    const rows = inst.shares ?? [];
    const only = rows.length === 1 ? rows[0] : null;
    onCreateOrder?.({
      articleId: inst.article_id, quantity: 1,
      instance: rows.length > 1 ? undefined
        : { objectId: inst.object_id, quantity: 1, fromOrderObjectId: only?.order_object_id ?? null },
    });
  }

  return (
    <div className="flex flex-col h-full bg-bg-1" style={{ color: 'var(--fg-1)' }}>
      {/* Kopf – die EINE Anatomie aller Datensatz-Fenster (`DetailHeader`, Notiz #242). */}
      <DetailHeader
        icon={Boxes} iconBg="#E9EDEC" iconFg="#5E6B66"
        eyebrow="Instanz" title={instanceName(inst)} objectId={inst.object_id ?? null}
        onBack={onBack}
        status={status}
        actions={<>
          <HeaderSep />
          <button className="erp-idbtn" data-tip="Etikett drucken (QR)" data-tip-pos="bottom" aria-label="Etikett drucken"
            onClick={() => inst.object_id != null && printObjectLabel(inst.object_id, inst.article_name, 'Instanz')}>
            <QrCode size={15} />
          </button>
          {/* Shortcut «Auftrag»: direkt einen Auftrag auf diese Instanz auslösen.
              **Der Knopf trägt den Ton des Zustands** (Testnotiz #380): ist die Instanz
              gebunden (gelbe Badge), wird aus dem Auftrag eine Abweichung – also sieht der
              Knopf schon vorher so aus. Das ist keine zweite Regel, sondern ein Blick auf
              dieselbe Badge (`isPending`): die Entscheidung trifft weiterhin allein die
              Auswahl im Auftrag (`subject.classify_pick`), hier steht nur die Vorschau. */}
          <button className={cn('erp-idbtn', willDeviate ? 'erp-idbtn-flag' : 'erp-idbtn-act')} data-tip-pos="bottom"
            data-tip={!canOrderInstance
              ? 'An verschrotteter Ware ist nichts mehr zu tun'
              : willDeviate
                ? 'Abweichungsauftrag anlegen – diese Instanz ist gebunden und darin vorgewählt'
                : 'Auftrag anlegen – diese Instanz ist darin vorgewählt (bewegen, prüfen, aussondern, verkaufen …)'}
            aria-label="Auftrag anlegen"
            disabled={!canOrderInstance}
            onClick={createOrderShortcut}>
            <ClipboardPlus size={15} />
          </button>
          {/* Sperre aufheben – nur wenn gesperrt. Bewusst eine Aktion an der Instanz
              (kein Prozessschritt): eine Maschine kommt aus der Wartung zurück, ohne
              dass jemand dafür einen Auftrag anlegen will. */}
          {inst.quality === 'blocked' && (
            <button className="erp-idbtn erp-idbtn-act" data-tip-pos="bottom"
              data-tip="Sperre aufheben – die Instanz ist danach wieder verwendbar"
              aria-label="Sperre aufheben" disabled={unblockBusy}
              onClick={unblockInstance}>
              {unblockBusy ? <Loader2 size={15} className="animate-spin" /> : <LockOpen size={15} />}
            </button>
          )}
          {/* **Kein zweiter Knopf «Abweichung melden»** (Notiz #371): eine Abweichung ist ein
              ganz gewöhnlicher Auftrag auf eine gebundene Instanz – und genau den legt der
              Knopf darüber an. Was daraus wird, sagt der Zustand der Instanz, nicht der
              Einstieg. */}
        </>}
      >
        {devErr && <div style={S.devErr}>{devErr}</div>}
        <DetailTabs<InstTab> style={{ marginTop: 16 }} active={tab} onChange={setTab} tabs={[
          { key: 'spec', label: 'Spezifikation', icon: FileText },
          { key: 'orders', label: 'Aufträge', icon: ClipboardList },
          { key: 'verwendung', label: 'Verwendung', icon: Boxes },
          { key: 'docs', label: 'Dokumente', icon: FolderOpen },
        ]} />
      </DetailHeader>

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
                objectNr={formatObjectId(inst.object_id)} issuedAt={genDoc.created_at ?? null} signoffs={genDoc.signoffs} />
            </div>
          )}
          <div style={S.glance}>
            <Tile
              wide icon={FileText} label="Spezifikation"
              value={inst.article_name ?? 'Artikel'}
              sub={inst.article_object_id != null ? formatObjectId(inst.article_object_id) : undefined} subMono
              onClick={inst.article_object_id != null ? () => nav?.(inst.article_object_id as number) : undefined}
            />
            <Tile
              icon={Package} label="Am Lager"
              value={<>{bestand} <span style={S.unit}>Stk</span></>}
              sub={bestandSub}
            />
            <Tile icon={CalendarDays} label="Erstellt" value={localDate(inst.created_at)} sub={timeAgo(inst.created_at)} />
            {inst.serial_number && (
              <Tile icon={Hash} label="Seriennummer" value={inst.serial_number} subMono />
            )}

            {/* Standort gehört in dasselbe Raster – er ist eine Kennzahl der Instanz wie
                jede andere, keine Karte für sich (Notiz #5). */}
            {/* Verteilte Charge: die Aufteilung steht IM Standort-Container statt als
                zweite Karte darunter – eine Frage, eine Antwort (Notiz #147). */}
            <LocationPathCard
              style={TILE.wide}
              path={inst.location_path ?? []}
              slices={inst.locations ?? []}
            />

            {/* **Wem gehört diese Menge?** – die Aufteilung, dieselbe Aussage wie im
                Auftrag, nur aus der anderen Richtung. Sie steht nur da, wenn sie etwas
                sagt: eine unberührte Instanz hat genau EINEN freien Anteil. */}
            {(inst.shares ?? []).length > 1 && (
              <TileShell style={TILE.wide} icon={Boxes} label="Aufteilung">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 2 }}>
                  {(inst.shares ?? []).map((sh, i) => (
                    <div key={`${sh.order_object_id ?? 'free'}-${i}`} style={S.shareRow}>
                      <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>{sh.quantity}</span>
                      {sh.order_object_id != null ? (
                        <>
                          <span style={{ color: 'var(--fg-3)' }}>{sh.order_name || 'Auftrag'}</span>
                          <ObjIdLink value={sh.order_object_id} />
                        </>
                      ) : (
                        <span style={{ color: 'var(--fg-4)' }}>frei</span>
                      )}
                    </div>
                  ))}
                </div>
              </TileShell>
            )}
          </div>
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
                      {/* Name · Objektnummer · Status – wie im Feed; ein Abweichungs-
                          auftrag trägt dasselbe gelbe Warnzeichen am Symbol (Notiz #243). */}
                      <div style={{ ...S.oico, position: 'relative' }}>
                        <ClipboardList size={17} />
                        {o.reason === 'deviation' && (
                          <span title="Abweichungsauftrag" style={S.devTag}>
                            <TriangleAlert size={9} style={{ color: 'var(--warning)' }} />
                          </span>
                        )}
                      </div>
                      <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
                        <div style={S.oT}>{o.name && o.name !== 'Auftrag' ? o.name : 'Auftrag'}</div>
                        <div style={S.oN}>{formatObjectId(o.object_id)}</div>
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
function Tile({ icon, label, hint, value, sub, subMono, wide, onClick }: {
  icon: ElementType; label: string; hint?: string; value: ReactNode;
  sub?: string; subMono?: boolean; wide?: boolean; onClick?: () => void;
}) {
  return (
    <TileShell icon={icon} label={label} hint={hint} onClick={onClick} style={wide ? TILE.wide : undefined}>
      <div style={TILE.v}>{value}</div>
      {sub && <div style={{ ...TILE.sub, ...(subMono ? S.mono : null) }}>{sub}</div>}
    </TileShell>
  );
}

// ── Styles (Inexxio Design System Tokens via CSS-Vars) ─────────────────────────
const S: Record<string, React.CSSProperties> = {
  shareRow: { display: 'flex', alignItems: 'center', gap: 6, font: '500 12.5px var(--font-body)', flexWrap: 'wrap' },
  devErr: { marginTop: 12, padding: '8px 12px', borderRadius: 'var(--r-sm)', background: 'var(--danger-bg)', color: 'var(--danger)', font: '500 12.5px var(--font-body)' },
  // Zentriert (nicht linksbündig): auf einem breiten Schirm klebte der Inhalt sonst am
  // linken Rand. Gilt für ALLE Reiter – der Rumpf ist EIN Container.
  body: { padding: '24px clamp(14px, 4vw, 28px) 40px', maxWidth: 1040, marginInline: 'auto' },
  // Kacheln tragen ihre eigene Haarlinie und stehen in Weissraum (Design-System:
  // «Struktur vor Fläche»). Das frühere Raster war durchgehend in der Linienfarbe
  // eingefärbt und liess Lücken bei 1 : Eine unvollständige letzte Reihe erschien als
  // grauer Block. Breitere Mindestspalte, damit bei viel Platz nicht sieben schmale
  // Streifen entstehen (Notiz #3).
  glance: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 260px), 1fr))', gap: 12, marginBottom: 30 },
  unit: { font: '600 13px var(--font-body)', color: 'var(--fg-3)' },
  mono: { fontFamily: 'var(--font-mono)' },
  osecHead: { display: 'flex', alignItems: 'center', gap: 11, marginBottom: 4 },
  osecIc: { width: 36, height: 36, borderRadius: 'var(--r-sm)', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' },
  osecH3: { font: '800 19px var(--font-display)', letterSpacing: '-.02em', margin: 0, color: 'var(--fg-1)' },
  ocount: { font: '700 14px var(--font-body)', color: 'var(--fg-2)', background: 'var(--bg-3)', borderRadius: 'var(--r-pill)', padding: '3px 13px', fontVariantNumeric: 'tabular-nums' },
  sortchip: { marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6, font: '600 12.5px var(--font-body)', color: 'var(--fg-3)', background: 'var(--bg-2)', border: '1px solid var(--border-1)', borderRadius: 'var(--r-pill)', padding: '5px 12px', cursor: 'pointer' },
  osecSub: { font: '500 13px var(--font-body)', color: 'var(--fg-4)', margin: '6px 0 16px 47px' },
  olist: { border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', overflow: 'hidden' },
  orow: { display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px', borderBottom: '1px solid var(--border-1)', cursor: 'pointer', background: '#fff', width: '100%', border: 'none', borderBottomWidth: 1, borderBottomStyle: 'solid', borderBottomColor: 'var(--border-1)', font: 'inherit' },
  devTag: { position: 'absolute', bottom: -3, right: -3, width: 14, height: 14, borderRadius: 999, background: 'var(--warning-bg)', border: '1px solid var(--warning)', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  oico: { width: 36, height: 36, borderRadius: 'var(--r-sm)', background: 'var(--accent-soft)', color: 'var(--accent-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' },
  oT: { font: '700 14px var(--font-body)', color: 'var(--fg-1)' },
  oN: { font: 'var(--mono-sm)', color: 'var(--fg-3)', fontVariantNumeric: 'tabular-nums', marginTop: 2 },
  badge: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 10px 4px 8px', borderRadius: 'var(--r-pill)', font: '600 12px var(--font-body)', lineHeight: 1, whiteSpace: 'nowrap' },
  oArrow: { color: 'var(--fg-4)', display: 'flex', flex: 'none' },
  emptyLine: { font: '500 13px var(--font-body)', color: 'var(--fg-4)', padding: '14px 2px' },
  labelCard: { marginTop: 24, border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', padding: 18, background: '#fff' },
};
