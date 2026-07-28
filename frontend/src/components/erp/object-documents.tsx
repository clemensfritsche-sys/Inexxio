'use client';

/**
 * Reiter «Dokumente» – für JEDEN ERP-Objekttyp (Artikel, Auftrag, Instanz, Benutzer,
 * Lagerplatz, Unternehmen), überall gleiche Optik. Vereint:
 *   • hochgeladene Fremd-Dokumente (Belege/Anleitungen/Rechnungen) – KI benennt + ordnet zu,
 *   • im Prozessschritt «Dokument» erzeugte Inexxio-Dokumente.
 *
 * Klick auf ein Dokument öffnet eine **Inline-Vorschau** (Bild/PDF, auch die selbst erstellten
 * Dokumente) – kein Download nötig. Herunterladen bleibt als Aktion beim Hover erhalten.
 * Hinzufügen ist **kamera-first** (`DocumentCamera`): Kamera startet sofort, Auslöser fotografiert,
 * «Datei hochladen» als Rückfall. Der Ingest-Dialog wird auch im Feed genutzt (kombinierte Kamera).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  FileText, Loader2, Trash2, Download, X, Plus, Check, ReceiptText, Truck, BookOpen,
  ShieldCheck, FileSignature, Receipt, File as FileIcon, FolderOpen, Info, AlertTriangle, Eye,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { ObjectDocument, DocumentAnalyzeResponse, DocumentFileType, SuggestedLink, CompanySettings, DocumentContent } from '@/types';
import { fmtObjId } from '@/components/erp/user-detail';
import { DocumentCamera } from '@/components/erp/document-camera';
import { DocumentView } from '@/components/erp/document-editor';
import { StatusBadge } from '@/components/erp/fields';
import { instanceStatusConfig } from '@/lib/process';
import { localDate } from '@/lib/utils';

// ─── Dokumenttyp: Symbol + Label (Farbe = Bedeutung) ──────────────────────────────
const DOC_TYPE: Record<string, { label: string; icon: React.ElementType; tone: string }> = {
  invoice:       { label: 'Rechnung',    icon: ReceiptText,   tone: '#b91c1c' },
  delivery_note: { label: 'Lieferschein', icon: Truck,        tone: '#1d4ed8' },
  manual:        { label: 'Anleitung',   icon: BookOpen,      tone: '#7c3aed' },
  datasheet:     { label: 'Datenblatt',  icon: FileText,      tone: '#0f766e' },
  certificate:   { label: 'Zertifikat',  icon: ShieldCheck,   tone: '#166534' },
  contract:      { label: 'Vertrag',     icon: FileSignature, tone: '#9a3412' },
  receipt:       { label: 'Beleg',       icon: Receipt,       tone: '#a16207' },
  generated:     { label: 'Erstellt',    icon: FileText,      tone: '#0d9488' },
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
  contextLabel?: string;
}) {
  const [docs, setDocs] = useState<ObjectDocument[] | null>(null);
  const [dialog, setDialog] = useState(false);
  const [preview, setPreview] = useState<ObjectDocument | null>(null);
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
    <div style={{ maxWidth: 880, marginInline: 'auto', width: '100%' }}>
      {/* Kompakte Kopfzeile (der Reiter heisst bereits «Dokumente») */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
        <span style={{ font: '500 12px var(--font-body)', color: 'var(--fg-4)', flex: 1 }}>
          {docs && docs.length > 0 ? `${docs.length} Dokument${docs.length === 1 ? '' : 'e'}` : 'Belege, Anleitungen & Rechnungen'}
        </span>
        <button onClick={() => setDialog(true)} className="erp-actbtn erp-actbtn-primary"
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
          <div style={{ fontSize: 12, marginTop: 3 }}>Rechnung, Lieferschein oder Anleitung fotografieren oder hochladen.</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {docs.map((d) => {
            const cfg = docCfg(d.doc_type);
            const Icon = cfg.icon;
            return (
              <div key={`${d.kind}-${d.id}`} className="erp-docrow"
                onClick={() => setPreview(d)}
                style={{ display: 'flex', alignItems: 'flex-start', gap: 13, padding: '14px 16px', background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', cursor: 'pointer' }}>
                <span style={{ width: 40, height: 40, borderRadius: 'var(--r-sm)', background: `${cfg.tone}14`, color: cfg.tone, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
                  <Icon size={19} />
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ font: '700 14px var(--font-body)', color: 'var(--fg-1)' }}>{d.title}</span>
                    {/* Ein erstelltes Dokument IST die Instanz → es zeigt DEREN Status (nicht «Erstellt»). */}
                    {d.kind === 'generated' && d.quality ? (
                      <StatusBadge cfg={instanceStatusConfig(d.quality, d.disposition ?? 'in_process', !!d.reserved)} size={10} />
                    ) : (
                      <span style={{ font: '600 10px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.04em', padding: '2px 7px', borderRadius: 999, color: cfg.tone, background: `${cfg.tone}14` }}>
                        {cfg.label}
                      </span>
                    )}
                  </div>
                  {d.summary && <div style={{ font: '500 12.5px var(--font-body)', color: 'var(--fg-3)', marginTop: 4, lineHeight: 1.45 }}>{d.summary}</div>}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6, font: '500 11px var(--font-body)', color: 'var(--fg-4)', flexWrap: 'wrap' }}>
                    {d.object_number != null && <span style={{ fontFamily: 'var(--font-mono)' }}>{fmtObjId(d.object_number)}</span>}
                    {d.created_at && <span>{localDate(d.created_at)}</span>}
                    {d.created_by_name && <span>· {d.created_by_name}</span>}
                    {d.page_count ? <span>· {d.page_count} S.</span> : null}
                    {d.byte_size ? <span>· {fmtSize(d.byte_size)}</span> : null}
                    {d.kind === 'generated' && <span style={{ color: 'var(--accent)' }}>· im Prozess erstellt</span>}
                  </div>
                </div>
                {/* Aktionen erscheinen beim Hover (Vorschau ist der Klick auf die Zeile). */}
                <div className="erp-docrow-actions" style={{ display: 'flex', gap: 4, flex: 'none' }} onClick={(e) => e.stopPropagation()}>
                  <button onClick={() => setPreview(d)} data-tip="Vorschau" data-tip-pos="left" aria-label="Vorschau" className="erp-idbtn"><Eye size={16} /></button>
                  <button onClick={() => download(d)} data-tip="Herunterladen" data-tip-pos="left" aria-label="Herunterladen" className="erp-idbtn"><Download size={16} /></button>
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

      {preview && <DocumentPreview entry={preview} onClose={() => setPreview(null)} onDownload={() => download(preview)} />}
      {dialog && (
        <DocumentIngestDialog contextObjectId={objectId} contextLabel={contextLabel}
          onClose={() => setDialog(false)} onDone={() => { setDialog(false); load(); }} />
      )}
    </div>
  );
}

// ─── Inline-Vorschau ──────────────────────────────────────────────────────────────
// Erstellte Dokumente (kind='generated') werden direkt als Inexxio-Dokument gerendert
// (DocumentView – kein PDF-Iframe, keine CSP-Blockade). Hochgeladene Dateien: Bild als
// <img>, PDF als <iframe> (authentifiziert geladen → Object-URL; frame-src blob: erlaubt).
function DocumentPreview({ entry, onClose, onDownload }: {
  entry: ObjectDocument; onClose: () => void; onDownload: () => void;
}) {
  const isGenerated = entry.kind === 'generated' && !!entry.content;
  const [src, setSrc] = useState<string | null>(null);
  const [mime, setMime] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [company, setCompany] = useState<Partial<CompanySettings> | null>(null);

  useEffect(() => {
    if (!isGenerated) return;
    let alive = true;
    api.getPublicSettings().then((s) => { if (alive) setCompany(s); }).catch(() => {});
    return () => { alive = false; };
  }, [isGenerated]);

  useEffect(() => {
    if (isGenerated) return;
    let url: string | null = null;
    let alive = true;
    api.documentPreviewUrl(entry.download_url)
      .then((r) => { if (alive) { url = r.url; setSrc(r.url); setMime(r.mime); } })
      .catch(() => { if (alive) setError('Vorschau konnte nicht geladen werden.'); });
    return () => { alive = false; if (url) URL.revokeObjectURL(url); };
  }, [entry.download_url, isGenerated]);

  const isImage = mime.startsWith('image/') || (entry.mime ?? '').startsWith('image/');

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 70, background: 'rgba(15,23,42,.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 'min(920px, 96vw)', height: '90vh', background: '#fff', borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-lg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', borderBottom: '1px solid var(--border-1)', flex: 'none' }}>
          <span style={{ font: '700 14px var(--font-body)', color: 'var(--fg-1)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{entry.title}</span>
          <button onClick={onDownload} data-tip="Herunterladen" data-tip-pos="bottom" aria-label="Herunterladen" className="erp-idbtn"><Download size={17} /></button>
          <button onClick={onClose} aria-label="Schliessen" className="erp-idbtn"><X size={18} /></button>
        </div>
        <div style={{ flex: 1, minHeight: 0, overflowY: isGenerated ? 'auto' : 'hidden', background: '#f1f5f9', display: 'flex', alignItems: isGenerated ? 'flex-start' : 'center', justifyContent: 'center' }}>
          {isGenerated ? (
            <div style={{ padding: 24, width: '100%', maxWidth: 820 }}>
              <DocumentView content={entry.content as unknown as DocumentContent} company={company}
                objectNr={entry.object_number ? fmtObjId(entry.object_number) : null}
                issuedAt={entry.created_at ?? null} signoffs={entry.signoffs} />
            </div>
          ) : error ? (
            <div style={{ color: 'var(--fg-4)', fontSize: 13, textAlign: 'center', padding: 24 }}>{error}<br />Bitte stattdessen herunterladen.</div>
          ) : !src ? (
            <Loader2 size={28} className="animate-spin" style={{ color: 'var(--accent)' }} />
          ) : isImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={src} alt={entry.title} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
          ) : (
            <iframe src={src} title={entry.title} style={{ width: '100%', height: '100%', border: 'none' }} />
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Kamera-first Ingest-Dialog (auch im Feed genutzt: onCode = Datensatz öffnen) ──
type Phase = 'camera' | 'analyzing' | 'review';
type SelLink = { object_id: number; label: string; relation: string; primary: boolean };

export function DocumentIngestDialog({ contextObjectId, contextLabel, onCode, onClose, onDone, title = 'Dokument hinzufügen', captureEnabled = true }: {
  contextObjectId: number | null;
  contextLabel?: string;
  onCode?: (objectId: number) => void;   // Feed: erkannter/eingegebener Code → Datensatz öffnen
  onClose: () => void;
  onDone: () => void;
  title?: string;
  captureEnabled?: boolean;              // false = reiner Scanner (Lieferant): kein Dokument-Upload
}) {
  const [phase, setPhase] = useState<Phase>('camera');
  const [error, setError] = useState<string | null>(null);
  const [proposal, setProposal] = useState<DocumentAnalyzeResponse | null>(null);
  const [docTitle, setDocTitle] = useState('');
  const [docType, setDocType] = useState<DocumentFileType>('other');
  const [links, setLinks] = useState<SelLink[]>([]);
  const [manualId, setManualId] = useState('');
  const [saving, setSaving] = useState(false);

  async function onFile(file: File) {
    setPhase('analyzing'); setError(null);
    try {
      const res = await api.analyzeDocument(file, contextObjectId);
      if (res.duplicate) {
        setError(`Dieses Dokument ist bereits abgelegt${res.duplicate_object_id ? ` (${fmtObjId(res.duplicate_object_id)})` : ''}.`);
        setPhase('camera');
        return;
      }
      setProposal(res);
      setDocTitle(res.title ?? '');
      setDocType((res.doc_type as DocumentFileType) ?? 'other');
      const sel: SelLink[] = (res.suggested_links ?? []).map((s: SuggestedLink) => ({
        object_id: s.object_id, label: s.label, relation: s.relation || 'about',
        primary: s.object_id === contextObjectId,
      }));
      if (contextObjectId != null && !sel.some((l) => l.object_id === contextObjectId)) {
        sel.unshift({ object_id: contextObjectId, label: contextLabel ?? 'Dieses Objekt', relation: 'about', primary: true });
      }
      if (sel.length && !sel.some((l) => l.primary)) sel[0].primary = true;
      setLinks(sel);
      setPhase('review');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analyse fehlgeschlagen');
      setPhase('camera');
    }
  }

  function addManualLink() {
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
    if (!proposal?.action_id || !docTitle.trim() || links.length === 0 || saving) return;
    setSaving(true); setError(null);
    try {
      await api.confirmDocument(proposal.action_id, {
        title: docTitle.trim(), doc_type: docType,
        links: links.map((l) => ({ object_id: l.object_id, relation: l.relation, primary: l.primary })),
      });
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Speichern fehlgeschlagen');
      setSaving(false);
    }
  }

  function manualOpen() {
    const oid = Number(manualId.trim());
    if (Number.isFinite(oid) && oid >= 100000000 && onCode) { onCode(oid); onClose(); }
    else setError('Bitte eine gültige 9-stellige Objektnummer eingeben.');
  }

  // **Kamera-Phase = Scanner-Design** (Notiz #119): die ganze Fläche ist die Kamera, alle
  // Bedienelemente liegen als milchige Chips darin – dieselbe Bildsprache wie der
  // Objekt-Scanner, nur mit den Zusatzfunktionen Auslöser/Upload/Nummer. Erst ab «Analyse»
  // wird es ein normales Formular-Fenster (dort geht es um Text, nicht um Bild).
  if (phase === 'camera') {
    return (
      <div onClick={reject} style={darkBackdrop}>
        <div onClick={(e) => e.stopPropagation()} style={darkSheet}>
          <DocumentCamera
            onCapture={onFile} onCode={onCode} captureEnabled={captureEnabled}
            extra={onCode ? (
              <div style={{ display: 'flex', gap: 6 }}>
                <input value={manualId} onChange={(e) => setManualId(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); manualOpen(); } }}
                  placeholder="Objektnummer öffnen, z. B. 100000123" inputMode="numeric"
                  style={glassInput} />
                <button type="button" onClick={manualOpen} style={glassBtn}>Öffnen</button>
              </div>
            ) : undefined}
          />
          {error && <div style={{ position: 'absolute', top: 14, left: 14, right: 14, ...errBox }}>{error}</div>}
        </div>
      </div>
    );
  }

  return (
    <div onClick={phase === 'analyzing' ? undefined : reject}
      style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(15,23,42,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div onClick={(e) => e.stopPropagation()}
        style={{ width: 'min(500px, 100%)', maxHeight: '92vh', overflowY: 'auto', background: '#fff', borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-lg)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 18px', borderBottom: '1px solid var(--border-1)' }}>
          <span style={{ width: 30, height: 30, borderRadius: 'var(--r-sm)', background: '#F4EBDD', color: '#9A7238', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <FolderOpen size={16} />
          </span>
          <div style={{ font: '800 15px var(--font-display)', color: 'var(--fg-1)', flex: 1 }}>{title}</div>
          <button onClick={reject} aria-label="Schliessen" className="erp-idbtn"><X size={18} /></button>
        </div>

        <div style={{ padding: '16px 18px' }}>
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
                  <Info size={14} style={{ flex: 'none', marginTop: 1 }} /> KI-Analyse nicht verfügbar – bitte Name und Zuordnung selbst prüfen.
                </div>
              )}
              <Label>Dokumentname</Label>
              <input value={docTitle} onChange={(e) => setDocTitle(e.target.value)} maxLength={200}
                placeholder="z. B. Rechnung Meier AG 2026-0421" className={FIN} style={{ marginBottom: 14 }} />
              <Label>Dokumenttyp</Label>
              <select value={docType} onChange={(e) => setDocType(e.target.value as DocumentFileType)} className={FIN} style={{ marginBottom: 14 }}>
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
                  <div key={l.object_id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 11px', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-1)', background: '#fff' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12.5, color: 'var(--fg-2)' }}>{fmtObjId(l.object_id)}</span>
                    <span style={{ flex: 1, minWidth: 0, font: '600 13px var(--font-body)', color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.label}</span>
                    <button type="button" onClick={() => setLinks((ls) => ls.map((x) => ({ ...x, primary: x.object_id === l.object_id })))}
                      data-tip="Als Hauptobjekt" data-tip-pos="left" style={{ border: 'none', background: 'none', cursor: 'pointer', color: l.primary ? 'var(--accent)' : 'var(--fg-4)', display: 'flex' }}>
                      <Check size={16} strokeWidth={l.primary ? 3 : 2} />
                    </button>
                    <button type="button" onClick={() => setLinks((ls) => ls.filter((x) => x.object_id !== l.object_id))}
                      aria-label="Zuordnung entfernen" style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--fg-4)', display: 'flex' }}>
                      <X size={15} />
                    </button>
                  </div>
                ))}
              </div>
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
              <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
                <input value={manualId} onChange={(e) => setManualId(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addManualLink(); } }}
                  placeholder="Objektnummer manuell hinzufügen…" className={FIN} inputMode="numeric" />
                <button type="button" onClick={addManualLink} style={neutralBtn}>Hinzufügen</button>
              </div>
              {error && <div style={{ marginBottom: 12, ...errBox }}>{error}</div>}
              <div style={{ display: 'flex', gap: 8 }}>
                <button type="button" onClick={reject} style={{ ...neutralBtn, minHeight: 44 }}>Abbrechen</button>
                <button type="button" onClick={confirm} disabled={!docTitle.trim() || links.length === 0 || saving}
                  style={{ flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, minHeight: 44, borderRadius: 'var(--r-md)', border: 'none', background: '#2563eb', color: '#fff', font: '700 14px var(--font-body)', cursor: 'pointer', opacity: (!docTitle.trim() || links.length === 0 || saving) ? 0.5 : 1 }}>
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
const darkBackdrop: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(15,23,42,.62)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
};
const darkSheet: React.CSSProperties = {
  position: 'relative', width: '100%', maxWidth: 420, aspectRatio: '3 / 4', maxHeight: '86vh',
  background: '#0B1220', borderRadius: 18, overflow: 'hidden', boxShadow: '0 24px 60px rgba(15,23,42,.4)',
};
const glassInput: React.CSSProperties = {
  flex: 1, minWidth: 0, padding: '11px 12px', fontSize: 13.5, borderRadius: 12, outline: 'none',
  border: '1px solid rgba(255,255,255,.22)', background: 'rgba(15,23,42,.5)',
  backdropFilter: 'blur(10px)', color: '#fff', boxSizing: 'border-box',
};
const glassBtn: React.CSSProperties = {
  padding: '0 16px', borderRadius: 12, border: '1px solid rgba(255,255,255,.22)',
  background: 'rgba(15,23,42,.5)', backdropFilter: 'blur(10px)', color: '#fff',
  fontSize: 13, fontWeight: 700, cursor: 'pointer', flex: 'none',
};
const neutralBtn: React.CSSProperties = { flex: 'none', padding: '0 14px', minHeight: 42, borderRadius: 'var(--r-md)', border: '1px solid var(--border-2)', background: '#fff', color: 'var(--fg-2)', font: '600 13px var(--font-body)', cursor: 'pointer' };

function Label({ children }: { children: React.ReactNode }) {
  return <div style={{ font: '600 11px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--fg-4)', marginBottom: 5 }}>{children}</div>;
}
