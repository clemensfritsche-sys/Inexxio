'use client';

import { Package } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Row } from '@/lib/use-feed-lists';
import { ErpNavContext } from '@/components/erp/obj-id';
import { ErrorBoundary } from '@/components/erp/error-boundary';
import { ArticleDetail } from '@/components/erp/article-detail';
import { OrderDetail, type OrderSeed } from '@/components/erp/order-detail';
import { InstanceDetail } from '@/components/erp/instance-detail';
import { OrganizationDetail } from '@/components/erp/organization-detail';
import { UserDetail } from '@/components/erp/user-detail';
import { NewCompany, NewPerson } from '@/components/erp/new-record';
import { DocumentDetail } from '@/components/erp/document-detail';
import { DocumentDraft } from '@/components/erp/document-draft';
import type { Creatable } from '@/components/erp/feed-panel';
import type { Article, CompanySettings, ErpRecordType, Order, Todo, UserProfile } from '@/types';

/** Was der Feed nach einer Anlage oder Änderung tut – an EINER Stelle (Feed-Seite). */
export interface DetailHandlers {
  onArticleSaved: (a: Article) => void;
  onOrderSaved: (o: Order) => void;
  onUserSaved: (u: UserProfile) => void;
  onCompanySaved: (c: CompanySettings) => void;
  onPersonCreated: (u: UserProfile) => void;
  onCompanyCreated: (c: CompanySettings) => void;
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
export function DetailPane({ show, creating, sel, activeRow, orderSeed, isAdmin, me, todos, h }: {
  show: boolean;
  creating: Creatable | null;
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
            <ArticleDetail key="new-article" record={null} onSaved={h.onArticleSaved}
              onRefresh={h.onRefreshArticles} onBack={h.onCancelCreate} />
          )}
          {creating === 'person' && (
            <NewPerson key="new-person" isAdmin={isAdmin} onSaved={h.onPersonCreated} onBack={h.onCancelCreate} />
          )}
          {creating === 'company' && (
            <NewCompany key="new-company" isAdmin={isAdmin} onSaved={h.onCompanyCreated} onBack={h.onCancelCreate} />
          )}
          {creating === 'order' && (
            <OrderDetail key="new-order" record={null} seed={orderSeed} onSaved={h.onOrderSaved} onBack={h.onCancelCreate} />
          )}
          {creating === 'document' && (
            <DocumentDraft key="new-document" onCancel={h.onCancelCreate}
              onFiled={(d) => h.onOpen({ type: 'document', objectId: d.object_id })}
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
