'use client';

import { useMemo, useState } from 'react';
import { Trash2, Lock, CheckCircle2, Info, ScanLine } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, OrderInstance } from '@/types';
import { instanceStatusConfig, instanceLabel, heldOf } from '@/lib/process';
import { StatusBadge, PlannedNotice, PrimaryButton, Label } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';

import { useScan } from '@/components/scan/scan-provider';
import { formatObjectId } from '@/lib/utils';

/**
 * Prozessschritt «Verschrotten» **und** «Sperren» – dieselbe Auswahl, zwei Wirkungen:
 *
 * * **Verschrotten** (endgültig): das Teil verlässt den Bestand (disposition='scrapped').
 * * **Sperren** (vorübergehend): das Teil bleibt, wo es ist, darf aber nicht verwendet
 *   werden (quality='blocked') – z. B. eine defekte Maschine bis zur Wartung. Die Sperre
 *   wird an der Instanz wieder aufgehoben.
 *
 * **Quittierung per Scan ist verbindlich:** jede Instanz wird vorher physisch gescannt
 * (kein blosses Anklicken) – so trifft es nie das falsche Teil. Eine **Teilmenge** gibt es
 * nur beim Verschrotten: eine halbe Maschine kann man nicht sperren.
 */
const MODE_TEXT = {
  scrap: {
    verb: 'Verschrotten', running: 'Verschrottet…',
    doneText: 'Verschrottung abgeschlossen', tone: 'var(--danger)',
    info: 'Jede Instanz wird vorher gescannt (Verifikation). Gescannte Instanzen werden endgültig aus dem Bestand genommen.',
  },
  block: {
    verb: 'Sperren', running: 'Sperrt…',
    doneText: 'Gesperrt', tone: 'var(--warning)',
    info: 'Jede Instanz wird vorher gescannt (Verifikation). Gesperrte Instanzen bleiben an ihrem Standort, sind aber nicht mehr verwendbar – die Sperre wird an der Instanz wieder aufgehoben.',
  },
} as const;

export function ScrapPanel({ order, stepState, stepId, mode = 'scrap', onOrderUpdated }: {
  order: Order;
  stepState: string;
  stepId?: number | null;
  /** «Verschrotten» (endgültig) oder «Sperren» (aufhebbar) – gleiche Auswahl, andere Wirkung. */
  mode?: 'scrap' | 'block';
  onOrderUpdated: (o: Order) => void;
}) {
  const T = MODE_TEXT[mode];
  const disp = order.disposal;
  const done = !!disp?.done;
  const instances = useMemo(() => order.instances ?? [], [order.instances]);
  const scan = useScan();

  // Noch verschrottbar = nicht bereits verschrottet/verbaut. Normalerweise sind auch VERKAUFTE
  // Teile «raus»; bei einer Retoure/Erstattung (reason='return') sind die verkauften Instanzen
  // aber das Subjekt – ein defekt zurückgekommenes Teil kann direkt verschrottet werden.
  const scrappable = useMemo(
    () => instances.filter((i) => i.object_id != null && (order.reason === 'return'
      ? !['scrapped', 'consumed'].includes(i.disposition ?? '')
      : !['scrapped', 'sold', 'consumed'].includes(i.disposition ?? ''))),
    [instances, order.reason],
  );

  const [scanned, setScanned] = useState<Set<number>>(new Set());
  // Je gescannter Instanz die zu verschrottende Menge (Default = ganze Instanz). Für Chargen
  // (Menge > 1) editierbar – analog Ressourcen-Teilentnahme: nur die Menge sinkt.
  const [qtys, setQtys] = useState<Record<number, number>>({});
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Eine Instanz nach der anderen scannen (Verifikation gegen die Objektnummer). Jede
  // bestätigte Instanz wandert in die «gescannt»-Menge; danach folgt die nächste.
  function runSequence(queue: OrderInstance[], acc: Set<number>) {
    if (queue.length === 0) return;
    const inst = queue[0];
    const oid = inst.object_id as number;
    scan({
      steps: [{
        label: 'Instanz', expected: oid, kind: 'instance',
        candidates: [{ objectId: oid, label: instanceLabel() }],
      }],
      onComplete: () => {
        const next = new Set(acc); next.add(oid); setScanned(next);
        // Default = der **Anteil dieses Auftrags**, nicht die ganze Instanz (#412/#414):
        // von einer 4er-Charge, an der eine Abweichung 2 hält, sind «alle» eben 2.
        setQtys((q) => (q[oid] != null ? q : { ...q, [oid]: heldOf(inst) }));
        runSequence(queue.slice(1), next);
      },
    });
  }

  function startScan(only?: OrderInstance) {
    setError(null);
    const queue = only ? [only] : scrappable.filter((i) => !scanned.has(i.object_id as number));
    if (queue.length) runSequence(queue, scanned);
  }

  async function submit() {
    const ids = [...scanned];
    if (ids.length === 0) { setError(`Bitte zuerst die Instanzen zum ${T.verb} scannen`); return; }
    if (!note.trim()) { setError('Bitte den Grund angeben'); return; }
    // Teilmenge NUR beim Verschrotten – eine halbe Maschine lässt sich nicht sperren.
    const items = ids.map((oid) => ({ instance_id: oid, quantity: mode === 'scrap' ? (qtys[oid] ?? null) : null }));
    const payload = { items, note: note.trim() || null, step_id: stepId ?? null };
    setSaving(true); setError(null);
    try {
      const oid = order.object_id as number;
      onOrderUpdated(mode === 'scrap'
        ? await api.updateOrderScrap(oid, payload)
        : await api.updateOrderBlock(oid, payload));
    } catch (e) {
      setError(e instanceof Error ? e.message : `Fehler beim ${T.verb}`);
    } finally { setSaving(false); }
  }

  if (instances.length === 0) {
    return (
      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#94a3b8' }}>
          <Info size={14} /> Noch keine Instanzen vorhanden.
        </div>
      </div>
    );
  }

  if (done) {
    const scrapped = instances.filter((i) => i.disposition === 'scrapped');
    return (
      <div style={cardStyle}>
        {/* Keine Erfolgsmeldung (Notiz #266): dass der Schritt erledigt ist, sagt der Haken
            im Modul-Kopf; WER und WANN steht dort im Hover. Hier zählt das Ergebnis –
            und der Grund, der die eigentliche Information dieses Schritts ist. */}
        {disp?.note && (
          <div style={{ font: '500 12.5px var(--font-body)', color: 'var(--fg-2)' }}>
            <span style={{ color: 'var(--fg-4)' }}>Grund: </span>{disp.note}
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 320, overflowY: 'auto' }}>
          {(scrapped.length ? scrapped : instances).map((i) => <InstanceRow key={i.id} instance={i} />)}
        </div>
      </div>
    );
  }

  const allScanned = scrappable.length > 0 && scrappable.every((i) => scanned.has(i.object_id as number));

  // **Ein künftiger Schritt zeigt seine Planung** (Testnotiz #487) – was hier geschehen
  // soll, steht längst im Panel; nur ausführen lässt er sich noch nicht.
  // **Nur der Schritt, der DRAN ist, lässt sich bedienen** (Testnotiz #542). Ansehen darf
  // man jeden (#471) – aber ein Schritt, der noch nicht an der Reihe ist oder gerade ruht,
  // bietet keine Eingabe an: das Backend lehnt sie ohnehin mit 409 ab, und ein Knopf, der
  // nicht tut, was er verspricht, ist schlimmer als keiner.
  const planned = stepState !== 'active';
  return (
    <div style={cardStyle}>
      {planned && <PlannedNotice />}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto' }}>
        {scrappable.map((i) => {
          const oid = i.object_id as number;
          const sel = scanned.has(oid);
          return (
            <div key={i.id} style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
              border: `1px solid ${sel ? '#fecaca' : '#f1f5f9'}`, borderRadius: 8,
              background: sel ? '#fef2f2' : '#fff',
            }}>
              <span style={{ fontSize: 12 }}><ObjId value={i.object_id} /></span>
              <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>{instanceLabel(heldOf(i), order.article_unit ?? undefined)}</span>
              {mode === 'scrap' && sel && heldOf(i) > 1 && (
                // Charge: Teilmenge zum Verschrotten wählen (Bruchmenge möglich, z. B. 0.75 … volle Menge).
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#64748b' }}>
                  <input type="number" min={0} step="any" max={heldOf(i)}
                    value={qtys[oid] ?? heldOf(i)}
                    onChange={(e) => {
                      const raw = Math.round((Number(e.target.value) || 0) * 1000) / 1000;
                      const v = Math.min(heldOf(i), Math.max(0, raw)) || 0;
                      setQtys((q) => ({ ...q, [oid]: v }));
                    }}
                    style={{ width: 60, padding: '3px 6px', fontSize: 12, border: '1px solid #e2e8f0', borderRadius: 6, textAlign: 'right' }} />
                  <span>/ {heldOf(i)}</span>
                </span>
              )}
              {sel ? (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 700, color: '#dc2626' }}>
                  <CheckCircle2 size={13} /> gescannt
                </span>
              ) : (
                <StatusBadge cfg={instanceStatusConfig(i.quality, i.disposition, (i.reserved_quantity ?? 0) > 0)} />
              )}
              <button onClick={() => startScan(i)} title="Diese Instanz scannen"
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 30, height: 30, borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', color: '#dc2626', cursor: 'pointer', flexShrink: 0 }}>
                <ScanLine size={15} />
              </button>
            </div>
          );
        })}
      </div>

      {/* Der Grund ist **Pflicht** (Notiz #255): warum etwas ausgeschleust wurde, ist die
          eigentliche Information dieses Schritts – ohne sie bleibt im Nachhinein nur «weg».
          Dass er verlangt wird, steht bereits in der Schritt-Definition. */}
      <div>
        <Label required>Grund</Label>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2}
          placeholder="z. B. Defekt, Bruch, Falschteil"
          className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
          style={{ borderColor: 'var(--border-1)', resize: 'vertical' }} />
      </div>

      {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}

      {scanned.size > 0 && (
        <button onClick={submit} disabled={saving}
          style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%',
            minHeight: 44, padding: '0 16px', borderRadius: 10, border: 'none', background: '#dc2626', color: '#fff',
            fontSize: 14, fontWeight: 700, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.55 : 1,
          }}>
          <Trash2 size={18} /> {saving ? T.running : `${T.verb} (${scanned.size})`}
        </button>
      )}
      {/* Das **Scannen** ist Routine – also die ruhige, schwarze Hauptaktion wie überall
          (Notiz #256). Rot bleibt dem Vollzug oben vorbehalten: das ist die Entscheidung,
          die etwas endgültig aus dem Bestand nimmt. */}
      {!allScanned && (
        <PrimaryButton icon={ScanLine} onClick={() => startScan()} disabled={planned || saving}>
          {scanned.size > 0 ? 'Weitere scannen' : `Scannen & ${T.verb.toLowerCase()}`}
        </PrimaryButton>
      )}
    </div>
  );
}

function InstanceRow({ instance }: { instance: OrderInstance }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', border: '1px solid #f1f5f9', borderRadius: 8 }}>
      <span style={{ fontSize: 12 }}><ObjId value={instance.object_id} /></span>
      <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>{instanceLabel()}</span>
      <StatusBadge cfg={instanceStatusConfig(instance.quality, instance.disposition, (instance.reserved_quantity ?? 0) > 0)} />
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  // Das Panel sitzt IN der Modul-Karte des Ablaufs – kein eigener Rahmen, kein eigener
  // Hintergrund, keine eigene Polsterung. Container-in-Container war genau die Schwere,
  // die Notiz #100 meint; die Karte drumherum ist bereits der Container.
  display: 'flex', flexDirection: 'column', gap: 12,
};
