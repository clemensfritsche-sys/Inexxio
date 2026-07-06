'use client';

/**
 * Reiter «Dokumente» – für JEDEN ERP-Objekttyp einsetzbar (Artikel, Auftrag, Instanz,
 * Benutzer, Lagerplatz, Unternehmen). Vereint zwei Quellen:
 *   • hochgeladene Fremd-Dokumente (Belege/Anleitungen/Rechnungen) – die KI vergibt
 *     Name + Typ und schlägt die Objektzuordnung vor; der Mensch bestätigt (AiAction).
 *   • im Prozessschritt «Dokument» erzeugte Inexxio-Dokumente (als PDF).
 *
 * Ein Dokument muss IMMER mindestens einem Objekt zugeordnet sein (Backend-Gate). Beim
 * Hochladen aus einem Objekt heraus ist dieses Objekt vorbelegt; weitere/andere Objekte
 * lassen sich per KI-Vorschlag anhaken oder per Objektnummer manuell hinzufügen.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  FileText, Upload, Camera, Loader2, Sparkles, Trash2, Download, X, Plus, Check,
  ReceiptText, Truck, BookOpen, ShieldCheck, FileSignature, Receipt, File as FileIcon,
  FolderOpen, AlertTriangle, Info,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { ObjectDocument, DocumentAnalyzeResponse, DocumentFileType, SuggestedLink } from '@/types';
import { fmtObjId } from '@/components/erp/user-detail';
import { localDate } from '@/lib/utils';

// ─── Dokumenttyp: Symbol + Label (Farbe = Bedeutung, Symbol statt Text) ───────────
const DOC_TYPE: Record<string, { label: string; icon: React.ElementType; tone: string }> = {
  invoice:       { label: 'Rechnung',    icon: ReceiptText,   tone: '#b91c1c' },
  delivery_note: { label: 'Lieferschein', icon: Truck,        tone: '#1d4ed8' },
  manual:        { label: 'Anleitung',   icon: BookOpen,      tone: '#7c3aed' },
  datasheet:     { label: 'Datenblatt',  icon: FileText,      tone: '#0f766e' },
  certificate:   { label: 'Zertifikat',  icon: ShieldCheck,   tone: '#166534' },
  contract:      { label: 'Vertrag',     icon: FileSignature, tone: '#9a3412' },
  receipt:       { label: 'Beleg',       icon: Receipt,       tone: '#a16207' },
  generated:     { label: 'Erzeugt',     icon: FileText,      tone: '#0d9488' },
  other:         { label: 'Dokument',    icon: FileIcon,      tone: '#475569' },
};
const docCfg = (t?: string | null) => DOC_TYPE[t ?? 'other'] ?? DOC_TYPE.other;

const TYPE_OPTIONS: { value: DocumentFileType; label: string }[] = [
  { value: 'invoice', label: 'Rechnung' }, { value: 'delivery_note', label: 'Lieferschein' },
  { value: 'manual', label: 'Anleitung' }, { value: 'datasheet', label: 'Datenblatt' },
  { value: 'certificate', label: 'Zertifikat' }, { value: 'contract', label: 'Vertrag' },
  { value: 'receipt', label: 'Beleg' }, { value: 'other', label: 'Sonstiges' },
];

function fmtSize(bytes?: number | null): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function ObjectDocuments({ objectId, contextLabel }: {
  objectId: number | null | undefined;
  contextLabel?: string;   // z. B. «diesem Artikel» (nur für den Info-Text)
}) {
  const [docs, setDocs] = useState<ObjectDocument[] | null>(null);
  const [dialog, setDialog] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(() => {
    if (objectId == null) { setDocs([]); return; }
    api.getObjectDocuments(objectId).then(setDocs).catch(() => setDocs([]));
  }, [objectId]);

  useEffect(() => { load(); }, [load]);

  async function download(d: ObjectDocument) {
    try {
      if (d.kind === 'file') await api.openDocumentFile(d.id, d.filename ?? d.title);
      else await api.openDocumentPdf(d.id, d.object_number ?? undefined);
    } catch { /* ignore */ }
  }

  async function remove(d: ObjectDocument) {
    if (d.kind !== 'file' || busyId) return;
    if (!window.confirm(`Dokument «${d.title}» entfernen?`)) return;
    setBusyId(d.id);
    try { await api.deleteDocumentFile(d.id); load(); }
    catch { /* ignore */ } finally { setBusyId(null); }
  }

  if (objectId == null) {
    return (
      <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--fg-4)' }}>
        <FolderOpen size={40} strokeWidth={1} style={{ margin: '0 auto 10px' }} />
        <div style={{ fontSize: 13.5, fontWeight: 600 }}>Dokumente sind nach dem Anlegen verfügbar</div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 860 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <span style={{ width: 34, height: 34, borderRadius: 'var(--r-sm)', background: '#F4EBDD', color: '#9A7238', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
          <FolderOpen size={18} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '800 15px var(--font-display)', color: 'var(--fg-1)' }}>Dokumente</div>
          <div style={{ font: '500 11.5px var(--font-body)', color: 'var(--fg-4)', marginTop: 1 }}>
            Belege, Anleitungen & Rechnungen – hochladen, die KI benennt und ordnet sie zu.
          </div>
        </div>
        <button onClick={() => setDialog(true)}
          className="erp-actbtn erp-actbtn-primary"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 7, flex: 'none' }}>
          <Plus size={15} /> Dokument
        </button>
      </div>

      {docs === null ? (
        <div style={{ padding: '20px 2px', color: 'var(--fg-4)', fontSize: 13 }}>Laden…</div>
      ) : docs.length === 0 ? (
        <div style={{ border: '1px dashed var(--border-2)', borderRadius: 'var(--r-lg)', padding: '32px 20px', textAlign: 'center', color: 'var(--fg-4)' }}>
          <FileText size={34} strokeWidth={1} style={{ margin: '0 auto 8px' }} />
          <div style={{ fontSize: 13, fontWeight: 600 }}>Noch keine Dokumente</div>
          <div style={{ fontSize: 12, marginTop: 3 }}>Laden Sie eine Rechnung, einen Lieferschein oder eine Anleitung hoch.</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {docs.map((d) => {
            const cfg = docCfg(d.doc_type);
            const Icon = cfg.icon;
            return (
              <div key={`${d.kind}-${d.id}`}
                style={{ display: 'flex', alignItems: 'flex-start', gap: 13, padding: '14px 16px', background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)' }}>
                <span style={{ width: 40, height: 40, borderRadius: 'var(--r-sm)', background: `${cfg.tone}14`, color: cfg.tone, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
                  <Icon size={19} />
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ font: '700 14px var(--font-body)', color: 'var(--fg-1)' }}>{d.title}</span>
                    <span style={{ font: '600 10px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.04em', padding: '2px 7px', borderRadius: 999, color: cfg.tone, background: `${cfg.tone}14` }}>
                      {cfg.label}
                    </span>
                  </div>
                  {d.summary && <div style={{ font: '500 12.5px var(--font-body)', color: 'var(--fg-3)', marginTop: 4, lineHeight: 1.45 }}>{d.summary}</div>}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6, font: '500 11px var(--font-body)', color: 'var(--fg-4)', flexWrap: 'wrap' }}>
                    {d.object_number != null && <span style={{ fontFamily: 'var(--font-mono)' }}>{fmtObjId(d.object_number)}</span>}
                    {d.created_at && <span>{localDate(d.created_at)}</span>}
                    {d.created_by_name && <span>· {d.created_by_name}</span>}
                    {d.page_count ? <span>· {d.page_count} S.</span> : null}
                    {d.byte_size ? <span>· {fmtSize(d.byte_size)}</span> : null}
                    {d.kind === 'generated' && <span style={{ color: 'var(--accent)' }}>· im Prozess erzeugt</span>}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 4, flex: 'none' }}>
                  <button onClick={() => download(d)} data-tip="Öffnen / herunterladen" data-tip-pos="left" aria-label="Herunterladen"
                    className="erp-idbtn"><Download size={16} /></button>
                  {d.kind === 'file' && (
                    <button onClick={() => remove(d)} disabled={busyId === d.id} data-tip="Entfernen" data-tip-pos="left" aria-label="Entfernen"
                      className="erp-idbtn" style={{ color: 'var(--danger)' }}>
                      {busyId === d.id ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {dialog && (
        <DocumentUploadDialog objectId={objectId} contextLabel={contextLabel}
          onClose={() => setDialog(false)} onDone={() => { setDialog(false); load(); }} />
      )}
    </div>
  );
}

// ─── Upload-/Analyse-/Bestätigungs-Dialog ─────────────────────────────────────────

type Phase = 'pick' | 'analyzing' | 'review';
type SelLink = { object_id: number; label: string; relation: string; primary: boolean };

function DocumentUploadDialog({ objectId, contextLabel, onClose, onDone }: {
  objectId: number; contextLabel?: string; onClose: () => void; onDone: () => void;
}) {
  const [phase, setPhase] = useState<Phase>('pick');
  const [error, setError] = useState<string | null>(null);
  const [proposal, setProposal] = useState<DocumentAnalyzeResponse | null>(null);
  const [title, setTitle] = useState('');
  const [docType, setDocType] = useState<DocumentFileType>('other');
  const [links, setLinks] = useState<SelLink[]>([]);
  const [manualId, setManualId] = useState('');
  const [saving, setSaving] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const camRef = useRef<HTMLInputElement>(null);

  async function onFile(file: File | null | undefined) {
    if (!file) return;
    setPhase('analyzing'); setError(null);
    try {
      const res = await api.analyzeDocument(file, objectId);
      if (res.duplicate) {
        setError(`Dieses Dokument ist bereits abgelegt${res.duplicate_object_id ? ` (${fmtObjId(res.duplicate_object_id)})` : ''}.`);
        setPhase('pick');
        return;
      }
      setProposal(res);
      setTitle(res.title ?? '');
      setDocType((res.doc_type as DocumentFileType) ?? 'other');
      // Vorschläge als Auswahl übernehmen; das Kontext-Objekt ist «primär».
      const sel: SelLink[] = (res.suggested_links ?? []).map((s: SuggestedLink) => ({
        object_id: s.object_id, label: s.label, relation: s.relation || 'about',
        primary: s.object_id === objectId,
      }));
      if (!sel.some((l) => l.object_id === objectId)) {
        sel.unshift({ object_id: objectId, label: contextLabel ?? 'Dieses Objekt', relation: 'about', primary: true });
      }
      if (!sel.some((l) => l.primary) && sel.length) sel[0].primary = true;
      setLinks(sel);
      setPhase('review');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analyse fehlgeschlagen');
      setPhase('pick');
    }
  }

  function addManual() {
    const oid = Number(manualId.trim());
    if (!Number.isFinite(oid) || oid < 100000000) { setError('Bitte eine gültige 9-stellige Objektnummer eingeben.'); return; }
    if (links.some((l) => l.object_id === oid)) { setManualId(''); return; }
    setLinks((ls) => [...ls, { object_id: oid, label: fmtObjId(oid), relation: 'about', primary: ls.length === 0 }]);
    setManualId(''); setError(null);
  }

  async function reject() {
    if (proposal?.action_id) { try { await api.rejectDocument(proposal.action_id); } catch { /* ignore */ } }
    onClose();
  }

  async function confirm() {
    if (!proposal?.action_id || !title.trim() || links.length === 0 || saving) return;
    setSaving(true); setError(null);
    try {
      await api.confirmDocument(proposal.action_id, {
        title: title.trim(), doc_type: docType,
        links: links.map((l) => ({ object_id: l.object_id, relation: l.relation, primary: l.primary })),
      });
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Speichern fehlgeschlagen');
      setSaving(false);
    }
  }

  return (
    <div onClick={phase === 'analyzing' ? undefined : reject}
      style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(15,23,42,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div onClick={(e) => e.stopPropagation()}
        style={{ width: 'min(560px, 100%)', maxHeight: '88vh', overflowY: 'auto', background: '#fff', borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-lg)' }}>
        {/* Kopf */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 20px', borderBottom: '1px solid var(--border-1)' }}>
          <span style={{ width: 32, height: 32, borderRadius: 'var(--r-sm)', background: '#F4EBDD', color: '#9A7238', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Upload size={17} />
          </span>
          <div style={{ flex: 1 }}>
            <div style={{ font: '800 15px var(--font-display)', color: 'var(--fg-1)' }}>Dokument hinzufügen</div>
          </div>
          <button onClick={reject} aria-label="Schliessen" className="erp-idbtn"><X size={18} /></button>
        </div>

        <div style={{ padding: '18px 20px' }}>
          {phase === 'pick' && (
            <>
              <button type="button" onClick={() => fileRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => { e.preventDefault(); onFile(e.dataTransfer.files?.[0]); }}
                style={{ width: '100%', border: '2px dashed var(--border-2)', borderRadius: 'var(--r-lg)', padding: '34px 20px', background: 'var(--bg-2)', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <Upload size={30} style={{ color: 'var(--accent)' }} />
                <div style={{ font: '700 14px var(--font-body)', color: 'var(--fg-1)' }}>Datei wählen oder hierher ziehen</div>
                <div style={{ font: '500 12px var(--font-body)', color: 'var(--fg-4)' }}>PDF oder Bild (max. 30 MB)</div>
              </button>
              <button type="button" onClick={() => camRef.current?.click()}
                style={{ marginTop: 10, width: '100%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, minHeight: 42, borderRadius: 'var(--r-md)', border: '1px solid var(--border-2)', background: '#fff', color: 'var(--fg-2)', font: '600 13px var(--font-body)', cursor: 'pointer' }}>
                <Camera size={16} /> Mit Kamera aufnehmen
              </button>
              <input ref={fileRef} type="file" accept="application/pdf,image/*" hidden
                onChange={(e) => onFile(e.target.files?.[0])} />
              <input ref={camRef} type="file" accept="image/*" capture="environment" hidden
                onChange={(e) => onFile(e.target.files?.[0])} />
              <div style={{ marginTop: 12, display: 'flex', gap: 7, font: '500 11.5px var(--font-body)', color: 'var(--fg-4)', lineHeight: 1.5 }}>
                <Sparkles size={13} style={{ flex: 'none', marginTop: 1, color: 'var(--accent)' }} />
                <span>Die KI liest das Dokument, vergibt einen Namen und schlägt vor, zu welchen Objekten es gehört. Sie bestätigen anschliessend.</span>
              </div>
              {error && <div style={{ marginTop: 12, ...errBox }}>{error}</div>}
            </>
          )}

          {phase === 'analyzing' && (
            <div style={{ padding: '40px 10px', textAlign: 'center' }}>
              <Loader2 size={30} className="animate-spin" style={{ color: 'var(--accent)', margin: '0 auto 12px' }} />
              <div style={{ font: '700 14px var(--font-body)', color: 'var(--fg-1)' }}>Dokument wird analysiert…</div>
              <div style={{ font: '500 12px var(--font-body)', color: 'var(--fg-4)', marginTop: 4 }}>Name & Zuordnung werden vorgeschlagen.</div>
            </div>
          )}

          {phase === 'review' && proposal && (
            <>
              {!proposal.ai_analyzed && (
                <div style={{ marginBottom: 14, display: 'flex', gap: 8, padding: '9px 12px', borderRadius: 'var(--r-sm)', background: '#FFFBEB', color: '#92400e', font: '500 12px var(--font-body)' }}>
                  <Info size={14} style={{ flex: 'none', marginTop: 1 }} />
                  KI-Analyse nicht verfügbar – bitte Name und Zuordnung selbst prüfen.
                </div>
              )}

              <Label>Dokumentname</Label>
              <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200}
                placeholder="z. B. Rechnung Meier AG 2026-0421" className={FIN} style={{ marginBottom: 14 }} />

              <Label>Dokumenttyp</Label>
              <select value={docType} onChange={(e) => setDocType(e.target.value as DocumentFileType)}
                className={FIN} style={{ marginBottom: 14 }}>
                {TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>

              {proposal.summary && (
                <div style={{ marginBottom: 14, padding: '10px 12px', borderRadius: 'var(--r-sm)', background: 'var(--bg-2)', font: '500 12.5px var(--font-body)', color: 'var(--fg-3)', lineHeight: 1.5 }}>
                  {proposal.summary}
                </div>
              )}

              <Label>Zugeordnete Objekte <span style={{ color: 'var(--danger)' }}>*</span></Label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}>
                {links.length === 0 && (
                  <div style={{ font: '500 12px var(--font-body)', color: 'var(--warning)', display: 'flex', gap: 6, alignItems: 'center' }}>
                    <AlertTriangle size={13} /> Mindestens ein Objekt zuordnen.
                  </div>
                )}
                {links.map((l) => (
                  <div key={l.object_id}
                    style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 11px', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-1)', background: '#fff' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12.5, color: 'var(--fg-2)' }}>{fmtObjId(l.object_id)}</span>
                    <span style={{ flex: 1, minWidth: 0, font: '600 13px var(--font-body)', color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.label}</span>
                    <button type="button" onClick={() => setLinks((ls) => ls.map((x) => ({ ...x, primary: x.object_id === l.object_id })))}
                      data-tip="Als Hauptobjekt" data-tip-pos="left"
                      style={{ border: 'none', background: 'none', cursor: 'pointer', color: l.primary ? 'var(--accent)' : 'var(--fg-4)', display: 'flex' }}>
                      <Check size={16} strokeWidth={l.primary ? 3 : 2} />
                    </button>
                    <button type="button" onClick={() => setLinks((ls) => ls.filter((x) => x.object_id !== l.object_id))}
                      aria-label="Zuordnung entfernen" style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--fg-4)', display: 'flex' }}>
                      <X size={15} />
                    </button>
                  </div>
                ))}
              </div>

              {/* Vorschläge, die noch nicht ausgewählt sind, zum Hinzufügen */}
              {(proposal.suggested_links ?? []).filter((s) => !links.some((l) => l.object_id === s.object_id)).length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <div style={{ font: '600 10.5px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--fg-4)', marginBottom: 5 }}>KI-Vorschläge</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {(proposal.suggested_links ?? []).filter((s) => !links.some((l) => l.object_id === s.object_id)).map((s) => (
                      <button key={s.object_id} type="button"
                        onClick={() => setLinks((ls) => [...ls, { object_id: s.object_id, label: s.label, relation: s.relation || 'about', primary: ls.length === 0 }])}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px', borderRadius: 'var(--r-pill)', border: '1px dashed var(--border-2)', background: 'var(--bg-2)', cursor: 'pointer', font: '600 12px var(--font-body)', color: 'var(--fg-2)' }}>
                        <Plus size={13} /> {s.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Manuell per Objektnummer */}
              <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
                <input value={manualId} onChange={(e) => setManualId(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addManual(); } }}
                  placeholder="Objektnummer manuell hinzufügen…" className={FIN} inputMode="numeric" />
                <button type="button" onClick={addManual}
                  style={{ flex: 'none', padding: '0 14px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-2)', background: '#fff', color: 'var(--fg-2)', font: '600 13px var(--font-body)', cursor: 'pointer' }}>
                  Hinzufügen
                </button>
              </div>

              {error && <div style={{ marginBottom: 12, ...errBox }}>{error}</div>}

              <div style={{ display: 'flex', gap: 8 }}>
                <button type="button" onClick={reject}
                  style={{ flex: 'none', padding: '0 16px', minHeight: 44, borderRadius: 'var(--r-md)', border: '1px solid var(--border-2)', background: '#fff', color: 'var(--fg-2)', font: '600 13.5px var(--font-body)', cursor: 'pointer' }}>
                  Abbrechen
                </button>
                <button type="button" onClick={confirm} disabled={!title.trim() || links.length === 0 || saving}
                  style={{ flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, minHeight: 44, borderRadius: 'var(--r-md)', border: 'none', background: '#2563eb', color: '#fff', font: '700 14px var(--font-body)', cursor: 'pointer', opacity: (!title.trim() || links.length === 0 || saving) ? 0.5 : 1 }}>
                  {saving ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
                  {saving ? 'Wird abgelegt…' : 'Ablegen & zuordnen'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const FIN = 'w-full rounded-ds-md border border-border-2 bg-white px-3 py-2.5 text-[14px] font-medium text-fg-1 outline-none placeholder:text-fg-4 focus:border-accent focus:ring-2 focus:ring-accent-soft';
const errBox: React.CSSProperties = { padding: '9px 12px', borderRadius: 8, background: 'var(--danger-bg)', color: 'var(--danger)', font: '500 12.5px var(--font-body)' };

function Label({ children }: { children: React.ReactNode }) {
  return <div style={{ font: '600 11px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--fg-4)', marginBottom: 5 }}>{children}</div>;
}
