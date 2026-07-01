'use client';

import { useEffect, useState } from 'react';
import { Plus, X, Loader2, Factory, ShoppingBag, CheckCircle2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, Instance, Order, OrderLineGoal, OrderLineIn } from '@/types';
import { unitLabel } from '@/lib/article';
import { fmtObjId } from '@/components/erp/user-detail';
import { Label, SearchSelect, ErrorText, Segmented } from '@/components/erp/fields';
import { TextFieldUnit, cardStyle, linkBtn } from '@/components/erp/order-detail';

let seq = 0;
function newRowId(): string {
  seq += 1;
  return `row-${seq}`;
}

type Row = { id: string; articleId: string; quantity: string; goal: OrderLineGoal; pins: number[] };

function emptyRow(): Row {
  return { id: newRowId(), articleId: '', quantity: '', goal: 'stock', pins: [] };
}

/** Mehrpositionen-Anlage: mehrere Artikel/Mengen auf einmal, je Zeile «Herstellen»
 *  (wird ein eigener Auftrag – eigene Fertigungs-Timeline) oder «Verkaufen» (Position
 *  eines gemeinsamen Sammel-Auftrags/einer Sendung, optional mit fixierten Instanzen
 *  statt FIFO). Genau die gleiche Logik wie der Einzel-Artikel-Auftrag – nur je Zeile
 *  wiederholt statt einmal. */
export function MultiLineOrderForm({ articles, onCreated, onCancel }: {
  articles: Article[];      // bereits auf freigegebene Artikel gefiltert
  onCreated: (o: Order) => void;
  onCancel: () => void;
}) {
  const [rows, setRows] = useState<Row[]>(() => [emptyRow(), emptyRow()]);
  const [stock, setStock] = useState<Instance[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Für die optionale Instanz-Fixierung je «Verkaufen»-Zeile (statt FIFO).
    api.getInstances(500).then(setStock).catch(() => {});
  }, []);

  const articleOptions = [
    { value: '', label: '— Artikel wählen —' },
    ...articles.map((a) => ({ value: String(a.id), label: `${fmtObjId(a.object_id)} · ${a.name}` })),
  ];

  function updateRow(id: string, patch: Partial<Row>) {
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }
  function addRow() {
    setRows((rs) => [...rs, emptyRow()]);
  }
  function removeRow(id: string) {
    setRows((rs) => (rs.length > 1 ? rs.filter((r) => r.id !== id) : rs));
  }

  const validRows = rows.filter((r) => r.articleId && Number(r.quantity) > 0);
  const canSave = validRows.length === rows.length && rows.length > 0 && !saving;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const lines: OrderLineIn[] = rows.map((r) => ({
        article_id: Number(r.articleId),
        quantity: Number(r.quantity),
        goal: r.goal,
        ...(r.goal === 'stock' && r.pins.length ? { instance_object_ids: r.pins } : {}),
      }));
      const created = await api.createOrder({ lines });
      onCreated(created);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Anlegen');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {rows.map((row, idx) => (
        <RowEditor key={row.id} row={row} index={idx} articleOptions={articleOptions} articles={articles}
          stock={stock} onChange={(patch) => updateRow(row.id, patch)}
          onRemove={rows.length > 1 ? () => removeRow(row.id) : undefined} />
      ))}
      <button type="button" onClick={addRow} style={{ ...linkBtn, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
        <Plus size={13} /> Weitere Position hinzufügen
      </button>
      {error && <ErrorText msg={error} />}
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <button type="button" onClick={save} disabled={!canSave}
          style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            padding: '9px 18px', borderRadius: 8, border: 'none',
            background: canSave ? '#2563eb' : '#cbd5e1', color: '#fff',
            fontSize: 13, fontWeight: 700, cursor: canSave ? 'pointer' : 'not-allowed',
          }}>
          {saving ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
          {rows.length > 1 ? `${rows.length} Aufträge/Positionen anlegen` : 'Auftrag anlegen'}
        </button>
        <button type="button" onClick={onCancel} style={linkBtn}>Abbrechen</button>
      </div>
    </div>
  );
}

function RowEditor({ row, index, articleOptions, articles, stock, onChange, onRemove }: {
  row: Row; index: number;
  articleOptions: { value: string; label: string }[];
  articles: Article[];
  stock: Instance[];
  onChange: (patch: Partial<Row>) => void;
  onRemove?: () => void;
}) {
  const [pinOpen, setPinOpen] = useState(false);
  const article = articles.find((a) => String(a.id) === row.articleId) ?? null;
  const unit = article ? unitLabel(article.unit) : '';
  const qty = Number(row.quantity) || 0;
  const availableForArticle = stock.filter((i) =>
    i.object_id != null && i.article_id === article?.id && i.quality === 'passed' && i.disposition === 'in_stock');
  const pinnedQty = row.pins.reduce((s, oid) => s + (availableForArticle.find((i) => i.object_id === oid)?.quantity ?? 1), 0);

  function togglePin(oid: number) {
    onChange({ pins: row.pins.includes(oid) ? row.pins.filter((x) => x !== oid) : [...row.pins, oid] });
  }

  return (
    <div style={{ ...cardStyle, marginBottom: 0, position: 'relative' }}>
      {onRemove && (
        <button type="button" onClick={onRemove} title="Position entfernen"
          style={{ position: 'absolute', top: 10, right: 10, border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer' }}>
          <X size={15} />
        </button>
      )}
      <Label>Position {index + 1}</Label>
      <SearchSelect value={row.articleId} onChange={(v) => onChange({ articleId: v, pins: [] })} options={articleOptions} required />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <TextFieldUnit label="Menge" value={row.quantity} onChange={(v) => onChange({ quantity: v, pins: [] })} unit={unit} required placeholder="z. B. 2" />
        <Segmented label="Ziel" value={row.goal} onChange={(v) => onChange({ goal: v as OrderLineGoal, pins: [] })}
          options={[
            { value: 'produce', label: 'Herstellen' },
            { value: 'stock', label: 'Verkaufen' },
          ]} />
      </div>
      {row.goal === 'produce' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#64748b' }}>
          <Factory size={13} style={{ color: '#0f766e', flexShrink: 0 }} />
          Wird ein eigener Auftrag – der Artikel-Prozess erzeugt {qty || ''} {unit} neu.
        </div>
      )}
      {row.goal === 'stock' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#64748b' }}>
            <ShoppingBag size={13} style={{ color: '#2563eb', flexShrink: 0 }} />
            Position eines Verkaufsauftrags – FIFO ab Lager, Kunde/Preis später im Verkaufs-Panel.
          </div>
          {!pinOpen ? (
            <button type="button" onClick={() => setPinOpen(true)} style={{ ...linkBtn, alignSelf: 'flex-start' }}>
              Bestimmte Instanz(en) statt FIFO wählen
            </button>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ fontSize: 12, color: '#64748b' }}>Fixierte Instanzen (≤ {qty || '?'} {unit}):</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: pinnedQty <= qty ? '#16a34a' : '#dc2626' }}>{pinnedQty} gewählt</span>
              </div>
              {availableForArticle.length === 0 ? (
                <div style={{ fontSize: 12, color: '#94a3b8' }}>Keine verfügbaren Instanzen – ohne Auswahl FIFO.</div>
              ) : (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {availableForArticle.map((i) => {
                    const sel = row.pins.includes(i.object_id!);
                    return (
                      <button key={i.object_id} type="button" onClick={() => togglePin(i.object_id!)}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontFamily: 'monospace',
                          padding: '4px 10px', borderRadius: 999, cursor: 'pointer',
                          border: `1px solid ${sel ? '#7c3aed' : '#e2e8f0'}`,
                          background: sel ? '#f5f3ff' : '#fff', color: sel ? '#6d28d9' : '#475569',
                        }}>
                        {sel && <CheckCircle2 size={12} />}
                        {fmtObjId(i.object_id)}{(i.quantity ?? 1) > 1 ? ` ·${i.quantity}` : ''}
                      </button>
                    );
                  })}
                </div>
              )}
              <button type="button" onClick={() => { setPinOpen(false); onChange({ pins: [] }); }} style={{ ...linkBtn, alignSelf: 'flex-start' }}>
                Zurück zu FIFO
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
