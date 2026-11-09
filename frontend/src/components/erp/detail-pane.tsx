'use client';

import { Package } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Row } from '@/lib/use-feed-lists';
import { ErpNavContext } from '@/components/erp/obj-id';
import { ErrorBoundary } from '@/components/erp/error-boundary';
import dynamic from 'next/dynamic';
import type { OrderSeed } from '@/components/erp/order-detail';
import type { DraftSeed } from '@/components/erp/document-draft';
import { DetailSkeleton } from '@/components/erp/skeleton';
import type { Creatable } from '@/components/erp/feed-panel';
import type { Article, CompanySettings, ErpRecordType, Order, Todo, UserProfile } from '@/types';

// ►►► **Jede Ansicht wird erst geladen, wenn man sie öffnet** (Änderungsakte U18) – das ERP
// startet schlank, der Prozess-Editor, die Zahlung oder die Gebietskarte kommen beim ersten
// Öffnen nach; bis dahin steht die graue Form des Fensters. ◄◄◄
const ArticleDetail = dynamic(() => import('@/components/erp/article-detail').then((m) => m.ArticleDetail), { loading: () => <DetailSkeleton />, ssr: false });
const OrderDetail = dynamic(() => import('@/components/erp/order-detail').then((m) => m.OrderDetail), { loading: () => <DetailSkeleton />, ssr: false });
const InstanceDetail = dynamic(() => import('@/components/erp/instance-detail').then((m) => m.InstanceDetail), { loading: () => <DetailSkeleton />, ssr: false });
const OrganizationDetail = dynamic(() => import('@/components/erp/organization-detail').then((m) => m.OrganizationDetail), { loading: () => <DetailSkeleton />, ssr: false });
const UserDetail = dynamic(() => import('@/components/erp/user-detail').then((m) => m.UserDetail), { loading: () => <DetailSkeleton />, ssr: false });
const NewCompany = dynamic(() => import('@/components/erp/new-record').then((m) => m.NewCompany), { loading: () => <DetailSkeleton />, ssr: false });
const NewPerson = dynamic(() => import('@/components/erp/new-record').then((m) => m.NewPerson), { loading: () => <DetailSkeleton />, ssr: false });
const DocumentDetail = dynamic(() => import('@/components/erp/document-detail').then((m) => m.DocumentDetail), { loading: () => <DetailSkeleton />, ssr: false });
const DocumentDraft = dynamic(() => import('@/components/erp/document-draft').then((m) => m.DocumentDraft), { loading: () => <DetailSkeleton />, ssr: false });

/** Was der Feed nach einer Anlage oder Änderung tut – an EINER Stelle (Feed-Seite). */
export interface DetailHandlers {
  onArticleSaved: (a: Article) => void;
  onOrderSaved: (o: Order) => void;
  onUserSaved: (u: UserProfile) => void;
  onCompanySaved: (c: CompanySettings) => void;
  onPersonCreated: (u: UserProfile) => void;
  onCompanyCreated: (c: CompanySettings) => void;
  /** Ein Dokument ist freigegeben (aus dem Entwurf). */
  onDocumentFiled: (objectId: number) => void;
  onRefreshArticles: () => void;
  onCreate: (type: Creatable, seed?: OrderSeed) => void;
  onOpen: (sel: { type: ErpRecordType; objectId: number }) => void;
  onCancelCreate: () => void;
  onBack: () => void;
  onReset: () => void;
}

/**
 * ►►► **Das Detail des Feeds** – was gerade angelegt wird (`creating`) oder ausgewählt ist
 * (`sel` → `activeRow`). ◄◄◄ Ein Render-Fehler in EINEM Datensatz sperrt nie die ganze
 * Oberfläche: der Boundary zeigt eine erholbare Meldung und setzt sich beim Wechsel der
 * Auswahl zurück. Im Entwurf führt keine Nummer weg – er lebt nur im Browser.
 */
export function DetailPane({ show, creating, sel, activeRow, orderSeed, seeds, isAdmin, me, todos, h }: {
  show: boolean;
  creating: Creatable | null;
  /** Was ein Entwurf schon mitbringt – aus «+» (Foto, Datei) oder einem Handgriff
   *  («Entwurf öffnen»); `no` zählt je Anlage hoch, damit ein neuer Entwurf neu beginnt. */
  seeds: { no: number; draft: DraftSeed | null; record: Record<string, string> | null };
  sel: { type: ErpRecordType; objectId: number } | null;
  activeRow: Row | null;
  orderSeed: OrderSeed | null;
  isAdmin: boolean;
  me: { object_id: number; name: string } | null;
  todos: Map<number, Todo>;
  h: DetailHandlers;
}) {
  const todoOf = (id: number | null | undefined) => (id != null ? todos.get(id) : null);
  const row = creating ? null : activeRow;
  const hasDetail = creating !== null || activeRow !== null || sel?.type === 'instance' || sel?.type === 'document';
  return (
    <div className={cn('flex-1 overflow-hidden flex-col', show ? 'flex' : 'hidden md:flex')}>
      <ErrorBoundary resetKey={creating ?? (sel ? `${sel.type}-${sel.objectId}` : 'none')} onReset={h.onReset}>
        <ErpNavContext.Provider value={null}>
          {creating === 'article' && (
            <ArticleDetail key={`new-article-${seeds.no}`} record={null} initial={seeds.record} onSaved={h.onArticleSaved}
              onRefresh={h.onRefreshArticles} onBack={h.onCancelCreate} />
          )}
          {creating === 'person' && (
            <NewPerson key={`new-person-${seeds.no}`} isAdmin={isAdmin} initial={seeds.record} onSaved={h.onPersonCreated} onBack={h.onCancelCreate} />
          )}
          {creating === 'company' && (
            <NewCompany key={`new-company-${seeds.no}`} isAdmin={isAdmin} initial={seeds.record} onSaved={h.onCompanyCreated} onBack={h.onCancelCreate} />
          )}
          {creating === 'order' && (
            <OrderDetail key={`new-order-${seeds.no}`} record={null} seed={orderSeed} onSaved={h.onOrderSaved} onBack={h.onCancelCreate} />
          )}
          {creating === 'document' && (
            <DocumentDraft key={`new-document-${seeds.no}`} seed={seeds.draft ?? undefined} onCancel={h.onCancelCreate}
              onFiled={(d) => h.onDocumentFiled(d.object_id)}
              onOpen={(oid) => h.onOpen({ type: 'document', objectId: oid })} />
          )}
        </ErpNavContext.Provider>
        {row?.type === 'order' && (
          <OrderDetail key={row.key} record={row.data} onSaved={h.onOrderSaved}
            onDeviate={(seed) => h.onCreate('order', seed)} onBack={h.onBack} />
        )}
        {row?.type === 'user' && (
          <UserDetail key={row.key} record={row.data} onSave={h.onUserSaved} isAdmin={isAdmin}
            onBack={h.onBack} me={me} todo={todoOf(row.data.object_id)} />
        )}
        {row?.type === 'article' && (
          <ArticleDetail key={row.key} record={row.data} onSaved={h.onArticleSaved}
            onRefresh={h.onRefreshArticles}
            // **Ein reiner Shortcut, kein zweiter Anlagepfad**: derselbe Entwurf wie über «+»,
            // nur mit vorbelegtem Artikel. Einen Auftrag gibt es erst mit der Freigabe.
            onCreateOrder={(articleObjectId) => h.onCreate('order', { articleObjectId })}
            onBack={h.onBack} />
        )}
        {!creating && sel?.type === 'document' && (
          <DocumentDetail key={`d-${sel.objectId}`} objectId={sel.objectId} onBack={h.onBack} />
        )}
        {!creating && sel?.type === 'instance' && (
          <InstanceDetail key={`i-${sel.objectId}`} objectId={sel.objectId} onBack={h.onBack} />
        )}
        {row?.type === 'organization' && (
          <OrganizationDetail key={row.key} record={row.data} isAdmin={isAdmin}
            todo={todoOf(row.data.object_id)} onSaved={h.onCompanySaved} onBack={h.onBack} />
        )}
        {!hasDetail && (
          <div className="flex-1 flex flex-col items-center justify-center bg-bg-2">
            <Package size={48} strokeWidth={1} className="text-fg-4" />
            <p className="mt-3 text-sm text-fg-3">Datensatz auswählen oder neu anlegen</p>
          </div>
        )}
      </ErrorBoundary>
    </div>
  );
}
