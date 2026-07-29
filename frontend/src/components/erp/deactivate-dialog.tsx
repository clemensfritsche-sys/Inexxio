'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Package, ClipboardList, Boxes, PlayCircle, Ban } from 'lucide-react';
import { api } from '@/lib/api';
import type { DeactivationImpact, OrdersMode } from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { Dialog, ChoiceButton, PrimaryButton, IconSwitch } from '@/components/erp/fields';

// Banner «Ersetzt durch …» / «Ersetzt …» – Nachvollziehbarkeit der Ersetzen-Kette.
export function ReplacedBanner({ replacedBy, replaces }: { replacedBy: number | null; replaces: number | null }) {
  if (replacedBy == null && replaces == null) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 8, padding: '6px 10px', borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--border-1)', fontSize: 12, color: 'var(--fg-3)' }}>
      {replacedBy != null && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>Ersetzt durch <ObjId value={replacedBy} /></span>}
      {replaces != null && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>Ersetzt <ObjId value={replaces} /></span>}
    </div>
  );
}

/**
 * Dialog für «Deaktivieren» / «Ersetzen».
 *
 * **Der Klick auf den Weg IST die Ausführung** (Notiz #155): früher wählte man erst eine
 * Option und bestätigte sie darunter noch einmal – zwei Schritte für eine Entscheidung.
 * Jetzt führen die Wege selbst aus, es gibt kein ×, kein «Abbrechen» und keine
 * hervorgehobene Vorauswahl (#152–#154); geschlossen wird per Klick daneben oder `Esc`.
 *
 * Die **Wirkungsanalyse** bleibt – sie ist die Tatsachengrundlage der Entscheidung, nicht
 * ihre Erklärung. Die erläuternden Unterzeilen sind entfallen (#148–#150).
 *
 * Die einzige Angabe, die vorab gewählt werden MUSS, ist der Umgang mit laufenden
 * Aufträgen (Auslaufen ↔ Abbrechen) – sie ändert die Wirkung, nicht den Weg, und bleibt
 * darum eine Auswahl.
 */
export function DeactivateDialog({ mode, articleObjectId, title, message, confirmLabel, offerSuccessor, onConfirm, onClose }: {
  mode: 'deactivate' | 'replace';
  articleObjectId?: number | null;   // gesetzt ⇒ Wirkungsanalyse (Artikel) laden
  title: string;
  message?: string;
  confirmLabel: string;
  offerSuccessor?: boolean;          // gesetzt ⇒ optional einen Nachfolger anlegen («Ersetzen»)
  onConfirm: (ordersMode: OrdersMode, createSuccessor: boolean) => Promise<void>;
  onClose: () => void;
}) {
  const [impact, setImpact] = useState<DeactivationImpact | null>(null);
  const [loading, setLoading] = useState(articleObjectId != null);
  const [ordersMode, setOrdersMode] = useState<OrdersMode>('phase_out');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (articleObjectId == null) return;
    api.getArticleDeactivationImpact(articleObjectId)
      .then(setImpact).catch(() => {}).finally(() => setLoading(false));
  }, [articleObjectId]);

  const orders = impact?.orders ?? [];
  const articles = impact?.articles ?? [];
  const stock = impact?.stock ?? 0;
  const hasOrders = orders.length > 0;

  async function run(createSuccessor: boolean) {
    setBusy(true); setError(null);
    try {
      await onConfirm(ordersMode, createSuccessor);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler');
      setBusy(false);
    }
  }

  return (
    <Dialog icon={AlertTriangle} title={title} width={460} onClose={onClose}>
      {message && <p style={{ fontSize: 13, color: 'var(--fg-2)', margin: 0 }}>{message}</p>}

      {/* ── Folgen ────────────────────────────────────────────────────────────
          Was diese Entscheidung auslöst – als Liste im selben Raster wie überall
          (Symbol · Sache · Zahl/Werte), Objektnummern klickbar. Was NICHT betroffen
          ist, steht leise da: dass nichts passiert, ist auch eine Antwort. Und die
          eine Angabe, die man dazu wirklich entscheiden muss (was mit laufenden
          Aufträgen geschieht), sitzt DIREKT an ihrer Zeile – nicht in einer zweiten
          Gruppe mit demselben Titel darunter (Notiz #180). */}
      {loading ? (
        <div style={{ fontSize: 13, color: 'var(--fg-4)' }}>Folgen werden geprüft…</div>
      ) : impact && (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <ImpactRow icon={ClipboardList} label="Laufende Aufträge"
            ids={orders.map((o) => o.object_id ?? null)} empty="keine">
            {hasOrders && (
              <div style={{ marginTop: 8 }}>
                <IconSwitch<OrdersMode> value={ordersMode} onChange={setOrdersMode}
                  options={[
                    { value: 'phase_out', icon: PlayCircle, label: 'Auslaufen lassen',
                      hint: 'Laufende Aufträge dürfen normal fertig werden.' },
                    { value: 'cancel', icon: Ban, label: 'Abbrechen',
                      hint: 'Freigegebene Aufträge werden abgebrochen – ihre Instanzen gehen in einen Abweichungsauftrag.' },
                  ]} />
              </div>
            )}
          </ImpactRow>
          <ImpactRow icon={Package} label="Mitbetroffene Artikel"
            ids={articles.map((a) => a.object_id ?? null)} empty="keine" />
          <ImpactRow icon={Boxes} label="Lagerbestand"
            value={stock === 0 ? null : `${stock} Stück`} empty="keiner" />
        </div>
      )}

      {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}

      {/* Zwei gleichwertige Wege statt Auswahl + Bestätigung – der Klick führt aus.
          «Ersetzen» ist der prägnante Name für «Nachfolger anlegen (Ersatz)» (#151):
          derselbe Vorgang, den der Artikel-Kopf ohnehin so nennt. */}
      {offerSuccessor ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <ChoiceButton disabled={busy || loading} onClick={() => run(false)} title="Deaktivieren" />
          <ChoiceButton disabled={busy || loading} onClick={() => run(true)} title="Ersetzen" />
        </div>
      ) : (
        <PrimaryButton onClick={() => run(false)} disabled={busy || loading}>
          {busy ? '…' : confirmLabel}
        </PrimaryButton>
      )}
    </Dialog>
  );
}

/**
 * Eine Folge: Symbol · Sache · betroffene Datensätze (klickbar) bzw. Wert. Ist nichts
 * betroffen, steht das leise da – die Zeile verschwindet nicht, denn «keine» ist die
 * Antwort auf eine Frage, die man sich sonst selbst stellen müsste.
 */
function ImpactRow({ icon: Icon, label, ids, value, empty, children }: {
  icon: React.ElementType; label: string;
  ids?: (number | null)[]; value?: string | null; empty: string;
  children?: React.ReactNode;
}) {
  const has = ids ? ids.length > 0 : !!value;
  return (
    <div style={{ display: 'flex', gap: 10, padding: '9px 0', borderTop: '1px solid var(--border-1)' }}>
      <Icon size={15} style={{ color: has ? 'var(--fg-2)' : 'var(--fg-4)', flexShrink: 0, marginTop: 2 }} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ font: '500 13px var(--font-body)', color: 'var(--fg-3)', flex: 1, minWidth: 0 }}>{label}</span>
          {!has ? (
            <span style={{ font: '500 13px var(--font-body)', color: 'var(--fg-4)' }}>{empty}</span>
          ) : ids ? (
            <span style={{ display: 'inline-flex', flexWrap: 'wrap', gap: 8, justifyContent: 'flex-end' }}>
              {ids.map((id) => <ObjId key={id} value={id} />)}
            </span>
          ) : (
            <span style={{ font: '700 13px var(--font-body)', color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
          )}
        </div>
        {children}
      </div>
    </div>
  );
}

