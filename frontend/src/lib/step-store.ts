import { api } from '@/lib/api';
import { STEP_META } from '@/lib/process';
import type {
  ArticleProcessStep, ArticleProcessStepInput, ArticleProcessStepUpdateInput,
  StepType, UserProfile,
} from '@/types';

/**
 * **Woher die Prozessschritte kommen und wohin sie gehen – EINE Schnittstelle, zwei Speicher.**
 *
 * Der Schritt-Editor (`ProcessSteps`) ist derselbe, egal ob er den Prozess eines
 * gespeicherten Artikels/Auftrags bearbeitet oder den eines **Auftrags-Entwurfs**, den es
 * in der Datenbank noch gar nicht gibt (Testnotiz #386: ein Auftrag entsteht erst mit der
 * Freigabe). Statt einen zweiten Editor zu bauen, tauscht nur der **Speicher**:
 *
 *   `apiStepStore`   – schreibt sofort (Artikel, freigegebener Träger, bestehender Auftrag)
 *   `draftStepStore` – hält die Schritte im Browser, bis der Auftrag erteilt wird
 *
 * Der Entwurfs-Speicher vergibt **negative** Pseudo-ids: sie sind eindeutig, sortierbar und
 * können nie mit einer echten Datenbank-id verwechselt werden.
 */
export type StepStore = {
  list(): Promise<ArticleProcessStep[]>;
  create(data: ArticleProcessStepInput): Promise<void>;
  update(stepId: number, data: ArticleProcessStepUpdateInput): Promise<ArticleProcessStep>;
  remove(stepId: number): Promise<void>;
  reorder(orderedIds: number[]): Promise<ArticleProcessStep[]>;
};

export function apiStepStore(owner: 'articles' | 'orders', ownerObjectId: number): StepStore {
  return {
    list: () => api.getSteps(owner, ownerObjectId),
    create: async (data) => { await api.createStep(owner, ownerObjectId, data); },
    update: (stepId, data) => api.updateStep(owner, ownerObjectId, stepId, data),
    remove: async (stepId) => { await api.deleteStep(owner, ownerObjectId, stepId); },
    reorder: (ids) => api.reorderSteps(owner, ownerObjectId, ids),
  };
}

/**
 * Die Felder, die der Server sonst ableitet – hier aus dem, was das Formular ohnehin weiss.
 * `label` kommt aus derselben Registry-Spiegelung wie überall (`STEP_META`, mirror-getestet),
 * der Lieferantenname aus der Liste, die der Editor bereits geladen hat.
 */
function toStep(id: number, position: number, data: ArticleProcessStepInput,
                suppliers: UserProfile[]): ArticleProcessStep {
  const sup = data.supplier_id != null ? suppliers.find((s) => s.id === data.supplier_id) : undefined;
  return {
    ...(data as Record<string, unknown>),
    id,
    position,
    label: STEP_META[data.step_type as StepType]?.label ?? data.step_type,
    supplier_object_id: sup?.object_id ?? null,
    supplier_name: sup ? (sup.company_name || [sup.first_name, sup.last_name].filter(Boolean).join(' ') || sup.email) : null,
  } as unknown as ArticleProcessStep;
}

export function draftStepStore(
  get: () => ArticleProcessStep[],
  set: (steps: ArticleProcessStep[]) => void,
  suppliers: UserProfile[] = [],
): StepStore {
  const renumber = (list: ArticleProcessStep[]) => list.map((s, i) => ({ ...s, position: i + 1 }));
  return {
    list: async () => get(),
    create: async (data) => {
      const list = get();
      // Negative Pseudo-id: eindeutig und nie mit einer echten id zu verwechseln.
      const id = Math.min(0, ...list.map((s) => s.id)) - 1;
      set(renumber([...list, toStep(id, list.length + 1, data, suppliers)]));
    },
    update: async (stepId, data) => {
      const next = get().map((s) => (s.id === stepId ? { ...s, ...(data as object) } as ArticleProcessStep : s));
      set(next);
      return next.find((s) => s.id === stepId)!;
    },
    remove: async (stepId) => { set(renumber(get().filter((s) => s.id !== stepId))); },
    reorder: async (ids) => {
      const by = new Map(get().map((s) => [s.id, s]));
      const next = renumber(ids.map((id) => by.get(id)!).filter(Boolean));
      set(next);
      return next;
    },
  };
}

/** Was der Entwurf beim Erteilen mitschickt – die reinen Eingaben, ohne Anzeige-Zutaten. */
export function toStepInputs(steps: ArticleProcessStep[]): ArticleProcessStepInput[] {
  return steps.map((s) => {
    const { id, label, supplier_object_id, supplier_name, position, ...rest } =
      s as unknown as Record<string, unknown>;
    void id; void label; void supplier_object_id; void supplier_name;
    return { ...rest, position: position as number } as ArticleProcessStepInput;
  });
}
