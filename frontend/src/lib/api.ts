import type {
  Article, ArticleInput, ArticleUpdateInput, ArticleNameSuggestion,
  ArticleProcessStep, ArticleProcessStepInput, ArticleProcessStepUpdateInput,
  Order, OrderSummary, OrderInput, OrderUpdateInput, OrderLineCreateInput, OrderLinePinsInput,
  PurchaseOrderUpdateInput, InspectionUpdateInput, DocumentUpdateInput,
  MovementUpdateInput, ResourceUpdateInput, ScrapUpdateInput, SaleUpdateInput, LegalDocument,
  PendingDocument, Acknowledgement,
  Instance, InstanceOrderRef, ObjectReference, StorageLocation, StorageLocationInput, StorageLocationUpdateInput,
  CompanySettings, UserProfile, DeactivationImpact, OrdersMode, OperatingCosts,
  ArticleSalesProfile, ArticleSalesUpdateInput, ArticlePrice, ArticlePriceInput, ArticlePriceUpdateInput,
  AudienceMember, ShopProduct, ShopConfig, ShopCheckoutResult, PaymentStatus, SaleStatus,
  CustomerOrder,
  AiConfig, AiChatMessage, AiChatResponse, AiProposal, AiDocContent, AiImageEditResponse,
  ObjectDocument, DocumentAnalyzeResponse, DocumentConfirmInput,
} from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
  }

  clearToken() {
    this.token = null;
  }

  // Transiente Transportfehler (Kaltstart / Skalierung / kurz nach einem Deploy)
  // äussern sich als 502/503 oder als abgewiesene Verbindung – die Anfrage
  // erreicht die App dann GAR NICHT und wird kurz erneut versucht (auch
  // schreibende, da der Server sie nie verarbeitet hat → keine Doppelanlage).
  // 500/504 hingegen nur bei LESENDEN (idempotenten) Anfragen wiederholen.
  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...((options.headers as Record<string, string>) || {}),
    };
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

    const method = (options.method ?? 'GET').toUpperCase();
    const idempotent = method === 'GET' || method === 'HEAD';
    const MAX_ATTEMPTS = 3;
    let lastError: Error = new Error('Keine Verbindung zum Server');

    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      let response: Response;
      try {
        response = await fetch(`${API_BASE}${path}`, { ...options, headers });
      } catch {
        // Keine Antwort erhalten → Anfrage kam nicht an, sicher wiederholbar.
        lastError = new Error('Keine Verbindung zum Server');
        if (attempt < MAX_ATTEMPTS) { await this.backoff(attempt); continue; }
        throw lastError;
      }

      if (response.ok) {
        if (response.status === 204) return {} as T;
        return response.json() as Promise<T>;
      }

      const retriable = response.status === 502 || response.status === 503
        || (idempotent && response.status >= 500);
      if (retriable && attempt < MAX_ATTEMPTS) {
        lastError = new Error(`Server nicht erreichbar (HTTP ${response.status})`);
        await this.backoff(attempt);
        continue;
      }
      throw new Error(await this.errorMessage(response));
    }
    throw lastError;
  }

  private backoff(attempt: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, attempt === 1 ? 500 : 1200));
  }

  // Fehlermeldung aufbereiten: bevorzugt das JSON-`detail` der API, sonst der
  // echte HTTP-Status (statt eines undurchsichtigen «Netzwerkfehler»).
  private async errorMessage(response: Response): Promise<string> {
    const body = (await response.json().catch(() => null)) as
      { detail?: unknown; error?: string } | null;
    const detail = body?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join('; ');
    }
    if (body?.error) return body.error;
    return response.status >= 500
      ? `Server nicht erreichbar (HTTP ${response.status})`
      : `HTTP ${response.status}`;
  }

  get<T>(path: string) {
    return this.request<T>(path);
  }

  post<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(body) });
  }

  patch<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
  }

  delete<T>(path: string) {
    return this.request<T>(path, { method: 'DELETE' });
  }

  // ─── Auth / Profile ────────────────────────────────────────────────────────

  getMe(): Promise<UserProfile> {
    return this.get('/api/v1/auth/me');
  }

  updateMe(data: Partial<UserProfile>): Promise<UserProfile> {
    return this.patch('/api/v1/auth/me', data);
  }

  // ─── Consent-Gate: zu bestätigende Pflichtdokumente ─────────────────────────
  getPendingDocuments(): Promise<PendingDocument[]> {
    return this.get('/api/v1/consent/pending');
  }

  // Ein Dokument bestätigen; liefert die verbleibenden offenen Bestätigungen zurück.
  acknowledgeDocument(kind: string): Promise<PendingDocument[]> {
    return this.post('/api/v1/consent/acknowledge', { kind });
  }

  // Bestätigungen eines Nutzers (für den Benutzer-ERP-Datensatz).
  getUserAcknowledgements(userObjectId: number): Promise<Acknowledgement[]> {
    return this.get(`/api/v1/consent/acknowledgements/${userObjectId}`);
  }

  // ─── Admin: Users ──────────────────────────────────────────────────────────

  getUsers(): Promise<UserProfile[]> {
    return this.get('/api/v1/admin/users');
  }

  updateUserRole(userId: number, role: string): Promise<UserProfile> {
    return this.patch(`/api/v1/admin/users/${userId}/role`, { role });
  }

  deactivateUser(userId: number): Promise<{ deactivated: boolean }> {
    return this.delete(`/api/v1/admin/users/${userId}`);
  }

  // ─── Admin: Settings ───────────────────────────────────────────────────────

  getSettings(): Promise<CompanySettings> {
    return this.get<Record<string, unknown>>('/api/v1/admin/settings').then(mapSettingsFromBackend);
  }

  getPublicSettings(): Promise<Partial<CompanySettings>> {
    return this.get<Record<string, unknown>>('/api/v1/admin/settings/public').then(mapSettingsFromBackend);
  }

  // Öffentliches Rechtsdokument (AGB/Datenschutz/…) – aufgelöster Zeiger (D). 404 → null.
  getLegalDocument(kind: string): Promise<LegalDocument | null> {
    return this.get<LegalDocument>(`/api/v1/legal/${kind}`).catch(() => null);
  }

  getOperatingCosts(): Promise<OperatingCosts> {
    return this.get<OperatingCosts>('/api/v1/admin/operating-costs');
  }

  // Lagerwartung (E): Meldebestand prüfen (Auto-Nachbestellung).
  runMaintenanceSweep(): Promise<{ reordered: number }> {
    return this.post('/api/v1/erp/maintenance/sweep', {});
  }

  updateSettings(data: Partial<CompanySettings>): Promise<CompanySettings> {
    return this.patch<Record<string, unknown>>('/api/v1/admin/settings', mapSettingsToBackend(data)).then(mapSettingsFromBackend);
  }

  // ─── ERP Records ──────────────────────────────────────────────────────────

  getErpRecords(): Promise<UserProfile[]> {
    return this.get('/api/v1/erp/records');
  }

  updateErpRecord(objectId: number, data: Partial<UserProfile>): Promise<UserProfile> {
    return this.patch(`/api/v1/erp/records/${objectId}`, data);
  }

  // ─── ERP Articles ──────────────────────────────────────────────────────────

  getArticles(): Promise<Article[]> {
    return this.get('/api/v1/erp/articles');
  }

  getArticle(objectId: number): Promise<Article> {
    return this.get(`/api/v1/erp/articles/${objectId}`);
  }

  createArticle(data: ArticleInput): Promise<Article> {
    return this.post('/api/v1/erp/articles', data);
  }

  // Intelligente Namensvorschläge beim Anlegen (bereits verwendete/ähnliche Namen –
  // Dubletten vermeiden). Leere Eingabe → die häufigsten bestehenden Namen.
  articleNameSuggestions(q: string, limit = 8): Promise<ArticleNameSuggestion[]> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return this.get(`/api/v1/erp/articles/name-suggestions?${params.toString()}`);
  }

  updateArticle(objectId: number, data: ArticleUpdateInput): Promise<Article> {
    return this.patch(`/api/v1/erp/articles/${objectId}`, data);
  }

  // Inaktiv/Ersetzen: Wirkungsanalyse, Inaktiv-Setzen (mit Auftrags-Wahl), Ersetzen
  getArticleDeactivationImpact(objectId: number): Promise<DeactivationImpact> {
    return this.get(`/api/v1/erp/articles/${objectId}/deactivation-impact`);
  }

  deactivateArticle(objectId: number, ordersMode: OrdersMode): Promise<Article> {
    return this.post(`/api/v1/erp/articles/${objectId}/deactivate`, { orders_mode: ordersMode });
  }

  replaceArticle(objectId: number, ordersMode: OrdersMode): Promise<Article> {
    return this.post(`/api/v1/erp/articles/${objectId}/replace`, { orders_mode: ordersMode });
  }

  // ─── Prozesse: eigenständige Objekte (Feed «Prozesse») + Stückliste je Artikel ─

  // ─── Prozessschritte – am Artikel (Entstehung) ODER am Auftrag (CUSTOM) ────────
  // ``owner`` = 'articles' | 'orders'; kein eigenständiges Prozess-Objekt mehr.

  getSteps(owner: 'articles' | 'orders', objectId: number): Promise<ArticleProcessStep[]> {
    return this.get(`/api/v1/erp/${owner}/${objectId}/steps`);
  }

  createStep(owner: 'articles' | 'orders', objectId: number, data: ArticleProcessStepInput): Promise<ArticleProcessStep> {
    return this.post(`/api/v1/erp/${owner}/${objectId}/steps`, data);
  }

  updateStep(owner: 'articles' | 'orders', objectId: number, stepId: number, data: ArticleProcessStepUpdateInput): Promise<ArticleProcessStep> {
    return this.patch(`/api/v1/erp/${owner}/${objectId}/steps/${stepId}`, data);
  }

  deleteStep(owner: 'articles' | 'orders', objectId: number, stepId: number): Promise<{ deleted: boolean }> {
    return this.delete(`/api/v1/erp/${owner}/${objectId}/steps/${stepId}`);
  }

  // Reihenfolge der frei sortierbaren Schritte; Pflicht-Bewegungen ordnet der Server.
  reorderSteps(owner: 'articles' | 'orders', objectId: number, orderedIds: number[]): Promise<ArticleProcessStep[]> {
    return this.patch(`/api/v1/erp/${owner}/${objectId}/steps/reorder`, { ordered_ids: orderedIds });
  }

  // ─── Dokumente (PDF-Rendering, Web-Ansicht) ─────────────────────────────────
  // Das PDF ist authentifiziert (Bearer) – ein blosser <a href> würde den Token nicht
  // mitsenden. Daher als Blob mit Auth-Header laden und über einen programmatischen
  // Download-Link ausliefern. Bewusst KEIN `window.open`: das läuft nach dem `await`
  // ausserhalb der Klick-Geste und würde von Safari/Firefox als Popup blockiert – der
  // Klick eines `<a download>` ist davon nicht betroffen und funktioniert überall.
  private async fetchPdf(path: string, filename: string): Promise<void> {
    const headers: Record<string, string> = {};
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    const res = await fetch(`${API_BASE}${path}`, { headers });
    if (!res.ok) throw new Error(await this.errorMessage(res));
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

  // Dokument (Fachzeile) als PDF laden – funktioniert für Entwurf & Ausgestelltes
  // (Layout-Vorschau während des Verfassens). ``docId`` = Embed-id, ``nr`` = Instanznummer.
  openDocumentPdf(docId: number, nr?: number | null): Promise<void> {
    const name = nr ? `Dokument-${String(nr).padStart(9, '0')}.pdf` : 'Dokument.pdf';
    return this.fetchPdf(`/api/v1/erp/documents/${docId}/pdf`, name);
  }

  // ─── Dokumente (hochgeladene Belege/Anleitungen – KI-Aufnahme + Reiter «Dokumente») ─

  // Reiter «Dokumente» eines beliebigen ERP-Objekts (hochgeladene Dateien + erzeugte Dokumente)
  getObjectDocuments(objectId: number): Promise<ObjectDocument[]> {
    return this.get(`/api/v1/erp/objects/${objectId}/documents`);
  }

  // Datei hochladen → KI analysiert & schlägt Name + Objektzuordnung vor (noch nicht gespeichert)
  async analyzeDocument(file: File, contextObjectId: number | null): Promise<DocumentAnalyzeResponse> {
    const headers: Record<string, string> = {};
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    const form = new FormData();
    form.append('file', file);
    if (contextObjectId != null) form.append('context_object_id', String(contextObjectId));
    const res = await fetch(`${API_BASE}/api/v1/ai/documents/analyze`, { method: 'POST', headers, body: form });
    if (!res.ok) throw new Error(await this.errorMessage(res));
    return res.json();
  }

  // Bestätigen: Name + Zuordnung festschreiben → Dokument anlegen (AiAction-Pfad)
  confirmDocument(actionId: number, data: DocumentConfirmInput): Promise<ObjectDocument> {
    return this.post(`/api/v1/ai/documents/${actionId}/confirm`, data);
  }

  // Vorschlag ablehnen (Datei wird aus der Ablage entfernt)
  rejectDocument(actionId: number): Promise<{ rejected: boolean }> {
    return this.post(`/api/v1/ai/documents/${actionId}/reject`, {});
  }

  // Eine hochgeladene Datei authentifiziert laden (inline-Vorschau/Download)
  openDocumentFile(docId: number, filename?: string | null): Promise<void> {
    return this.fetchPdf(`/api/v1/erp/document-files/${docId}/download`, filename || 'dokument');
  }

  // Datei-Bytes authentifiziert holen und als lokale Object-URL bereitstellen (Inline-Vorschau
  // von PDF/Bild – ein <iframe>/<img> kann den Bearer-Token nicht selbst mitsenden). Der Aufrufer
  // gibt die URL per URL.revokeObjectURL wieder frei.
  async documentPreviewUrl(downloadPath: string): Promise<{ url: string; mime: string }> {
    const headers: Record<string, string> = {};
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    const res = await fetch(`${API_BASE}${downloadPath}`, { headers });
    if (!res.ok) throw new Error(await this.errorMessage(res));
    const blob = await res.blob();
    return { url: URL.createObjectURL(blob), mime: blob.type || 'application/octet-stream' };
  }

  deleteDocumentFile(docId: number): Promise<{ deleted: boolean }> {
    return this.delete(`/api/v1/erp/document-files/${docId}`);
  }

  // ─── Foto-/Bild-Upload (multipart) ──────────────────────────────────────────
  // Gibt eine relative URL (Token) zurück; die speichern die Verbraucher als String.
  async uploadAttachment(file: File): Promise<{ url: string; width: number | null; height: number | null }> {
    const headers: Record<string, string> = {};
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/api/v1/erp/attachments`, { method: 'POST', headers, body: form });
    if (!res.ok) throw new Error(await this.errorMessage(res));
    return res.json();
  }

  // ─── ERP Orders (Aufträge) ──────────────────────────────────────────────────

  // Schlanker Feed (ohne Embeds); Detail via getOrder(id)
  getOrders(): Promise<OrderSummary[]> {
    return this.get('/api/v1/erp/orders');
  }

  getOrder(objectId: number): Promise<Order> {
    return this.get(`/api/v1/erp/orders/${objectId}`);
  }

  createOrder(data: OrderInput): Promise<Order> {
    return this.post('/api/v1/erp/orders', data);
  }

  updateOrder(objectId: number, data: OrderUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}`, data);
  }

  // Mehrpositionen: weitere Artikel zu einem bestehenden Entwurf hinzufügen/entfernen/
  // fixieren – jederzeit möglich, auch nach dem ersten Speichern.
  addOrderLine(objectId: number, data: OrderLineCreateInput): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${objectId}/lines`, data);
  }

  removeOrderLine(objectId: number, lineId: number): Promise<Order> {
    return this.delete(`/api/v1/erp/orders/${objectId}/lines/${lineId}`);
  }

  setOrderLinePins(objectId: number, lineId: number, data: OrderLinePinsInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/lines/${lineId}`, data);
  }

  // Abbrechen: erzwingt einen Folgeauftrag (Abweichung); liefert diesen zurück (bzw. bei
  // einem Entwurf den direkt inaktivierten Auftrag).
  abortOrder(objectId: number): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${objectId}/abort`, {});
  }

  // «Abweichung melden»: eröffnet einen Unterauftrag (Abweichung) auf den Instanzen
  // dieses Auftrags (optional eine Teilmenge); liefert den Entwurf der Abweichung zurück.
  createDeviation(objectId: number, instanceObjectIds?: number[]): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${objectId}/deviation`,
      instanceObjectIds && instanceObjectIds.length ? { instance_object_ids: instanceObjectIds } : {});
  }

  // «Nachschub anlegen»: eröffnet einen Nachschub-Unterauftrag (reason='supply'), der die
  // Fehlmenge eines blockierten Schritts beschafft/produziert; liefert den Auftrag zurück.
  createSupply(objectId: number): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${objectId}/supply`, {});
  }

  // «Aus Lager decken» / «Andere Instanz wählen»: deckt die Subjekt-Fehlmenge aus
  // vorhandenem Lagerbestand – FIFO (ohne ids) oder gezielt gewählte Instanzen.
  coverStock(objectId: number, instanceObjectIds?: number[]): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${objectId}/cover-stock`,
      instanceObjectIds && instanceObjectIds.length ? { instance_object_ids: instanceObjectIds } : {});
  }

  // «Abbruch zurücknehmen»: verwirft einen noch im Entwurf befindlichen Folgeauftrag
  // (objectId = Folgeauftrag); das Original läuft danach unverändert weiter. Liefert das
  // wieder laufende Original zurück.
  revokeAbort(followupObjectId: number): Promise<Order> {
    return this.post(`/api/v1/erp/orders/${followupObjectId}/revoke`, {});
  }

  // Beschaffungsschritt des Auftrags (läuft unter der Auftragsnummer)
  updateOrderPurchase(objectId: number, data: PurchaseOrderUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/purchase`, data);
  }

  // Schritt «Eingangskontrolle»: Stichprobenergebnis erfassen
  updateOrderInspection(objectId: number, data: InspectionUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/inspection`, data);
  }

  // Schritt «Dokument»: Inhalt verfassen (save) bzw. ausstellen (issue)
  updateOrderDocument(objectId: number, data: DocumentUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/document`, data);
  }

  // Schritt «Bewegung»: Instanzen einlagern/umlagern (Zielstandort je Instanz)
  updateOrderMovement(objectId: number, data: MovementUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/movement`, data);
  }

  // Schritt «Ressource»: Verbrauch (FIFO) + Betriebsmittel erfassen
  updateOrderResource(objectId: number, data: ResourceUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/resource`, data);
  }

  // Schritt «Verschrotten»: gewählte Instanzen ausschleusen (disposition='scrapped')
  updateOrderScrap(objectId: number, data: ScrapUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/scrap`, data);
  }

  // Schritt «Verkauf» (kaufmännisch): Bestätigung → Rechnung → Zahlung
  updateOrderSale(objectId: number, data: SaleUpdateInput): Promise<Order> {
    return this.patch(`/api/v1/erp/orders/${objectId}/sale`, data);
  }

  // Bestand (Instanzen) eines Artikels
  getArticleInstances(objectId: number): Promise<Instance[]> {
    return this.get(`/api/v1/erp/articles/${objectId}/instances`);
  }

  // Instanz-Feed (server-seitig paginierbar + durchsuchbar; limit=0 → alle, neueste zuerst)
  getInstances(limit = 0, offset = 0, search = ''): Promise<Instance[]> {
    const p = new URLSearchParams();
    if (limit) p.set('limit', String(limit));
    if (offset) p.set('offset', String(offset));
    if (search) p.set('search', search);
    const qs = p.toString();
    return this.get(`/api/v1/erp/instances${qs ? `?${qs}` : ''}`);
  }

  // Gesamtzahl (matchender) Instanzen für die Feed-Zähler/Pagination
  getInstanceCount(search = ''): Promise<{ count: number }> {
    return this.get(`/api/v1/erp/instances/count${search ? `?search=${encodeURIComponent(search)}` : ''}`);
  }

  // Universelle Objektnummer serverseitig auf ihren Typ auflösen (Scan/Navigation)
  resolveObject(objectId: number): Promise<{ object_id: number; object_type: string }> {
    return this.get(`/api/v1/erp/objects/${objectId}`);
  }

  getInstance(objectId: number): Promise<Instance> {
    return this.get(`/api/v1/erp/instances/${objectId}`);
  }

  // Aufträge, die diese Instanz angefasst haben (Herkunft zuerst)
  getInstanceOrders(objectId: number): Promise<InstanceOrderRef[]> {
    return this.get(`/api/v1/erp/instances/${objectId}/orders`);
  }

  // ─── ERP Storage Locations (Lagerplätze) ────────────────────────────────────

  getStorageLocations(): Promise<StorageLocation[]> {
    return this.get('/api/v1/erp/storage-locations');
  }

  getStorageLocation(objectId: number): Promise<StorageLocation> {
    return this.get(`/api/v1/erp/storage-locations/${objectId}`);
  }

  createStorageLocation(data: StorageLocationInput): Promise<StorageLocation> {
    return this.post('/api/v1/erp/storage-locations', data);
  }

  updateStorageLocation(objectId: number, data: StorageLocationUpdateInput): Promise<StorageLocation> {
    return this.patch(`/api/v1/erp/storage-locations/${objectId}`, data);
  }

  // Ersetzen: Duplikat (Entwurf) anlegen, verknüpfen, Original inaktiv (nur wenn leer)
  replaceStorageLocation(objectId: number): Promise<StorageLocation> {
    return this.post(`/api/v1/erp/storage-locations/${objectId}/replace`, {});
  }

  // Verwendung eines Lagerplatzes (lagernde Instanzen + referenzierende Artikel)
  getStorageLocationReferences(objectId: number): Promise<ObjectReference[]> {
    return this.get(`/api/v1/erp/storage-locations/${objectId}/references`);
  }

  // Generischer Rückverweis je Objektnummer («wer zeigt auf mich» – verortet/Ziel).
  getObjectReferences(objectId: number): Promise<ObjectReference[]> {
    return this.get(`/api/v1/erp/objects/${objectId}/references`);
  }

  // ─── Verkauf (ERP, Reiter «Verkauf» am Artikel) ─────────────────────────────
  // Verkaufs-Daten sind IMMER editierbar (auch bei freigegebenem Artikel).

  getArticleSales(objectId: number): Promise<ArticleSalesProfile> {
    return this.get(`/api/v1/erp/articles/${objectId}/sales`);
  }

  updateArticleSales(objectId: number, data: ArticleSalesUpdateInput): Promise<ArticleSalesProfile> {
    return this.patch(`/api/v1/erp/articles/${objectId}/sales`, data);
  }

  createArticlePrice(objectId: number, data: ArticlePriceInput): Promise<ArticlePrice> {
    return this.post(`/api/v1/erp/articles/${objectId}/sales/prices`, data);
  }

  updateArticlePrice(objectId: number, priceId: number, data: ArticlePriceUpdateInput): Promise<ArticlePrice> {
    return this.patch(`/api/v1/erp/articles/${objectId}/sales/prices/${priceId}`, data);
  }

  deleteArticlePrice(objectId: number, priceId: number): Promise<{ deleted: boolean }> {
    return this.delete(`/api/v1/erp/articles/${objectId}/sales/prices/${priceId}`);
  }

  addArticleAudience(objectId: number, userId: number): Promise<AudienceMember[]> {
    return this.post(`/api/v1/erp/articles/${objectId}/sales/audience`, { user_id: userId });
  }

  removeArticleAudience(objectId: number, rowId: number): Promise<{ removed: boolean }> {
    return this.delete(`/api/v1/erp/articles/${objectId}/sales/audience/${rowId}`);
  }

  // ─── Shop (öffentlich / Kunde) ──────────────────────────────────────────────

  getShopConfig(): Promise<ShopConfig> {
    return this.get('/api/v1/shop/config');
  }

  // Preise immer in CHF (Basis); Stripe Adaptive Pricing zeigt die Lokalwährung an der Kasse.
  getShopProducts(lang?: string): Promise<ShopProduct[]> {
    const qs = lang ? `?lang=${lang}` : '';
    return this.get(`/api/v1/shop/products${qs}`);
  }

  getShopProduct(objectId: number, lang?: string): Promise<ShopProduct> {
    const qs = lang ? `?lang=${lang}` : '';
    return this.get(`/api/v1/shop/products/${objectId}${qs}`);
  }

  // Warenkorb-Checkout: mehrere Positionen ⇒ eine Zahlungs-Session (Defer-Modell).
  shopCheckout(items: { article_object_id: number; price_id: number; quantity: number }[]): Promise<ShopCheckoutResult> {
    return this.post('/api/v1/shop/checkout', { items });
  }


  // Stripe Customer Portal (Abo/Zahlungsmittel selbst verwalten)
  openCustomerPortal(): Promise<{ url: string }> {
    return this.post('/api/v1/shop/portal', {});
  }

  // Eigene Bestellungen + Abos (Kunde)
  getMyOrders(): Promise<CustomerOrder[]> {
    return this.get('/api/v1/shop/orders');
  }

  // Abo on-site kündigen (kündigt zuerst bei Stripe, dann lokal)
  cancelSubscription(orderObjectId: number): Promise<{ cancelled: boolean; subscription_active: boolean }> {
    return this.post(`/api/v1/shop/orders/${orderObjectId}/cancel-subscription`, {});
  }

  // Retoure/Rückgabe einer abgeschlossenen Bestellung anfragen (Online-Shop-Logik) – legt einen
  // Retoure-Auftrag an (Personal verarbeitet ihn im ERP: Wareneingang + Gutschrift/Stripe-Refund).
  requestReturn(orderObjectId: number, reason: string | null): Promise<{ return_object_id: number; status: string }> {
    return this.post(`/api/v1/shop/orders/${orderObjectId}/return`, { reason });
  }

  // Bestellungen eines Benutzers (ERP-Reiter, staff)
  getRecordOrders(objectId: number): Promise<CustomerOrder[]> {
    return this.get(`/api/v1/erp/records/${objectId}/orders`);
  }

  // Manueller Provider (Fallback ohne Stripe-Keys)
  getPaymentStatus(token: string): Promise<PaymentStatus> {
    return this.get(`/api/v1/shop/payment/${token}`);
  }

  simulatePayment(token: string, result: 'paid' | 'cancelled'): Promise<{ status: SaleStatus }> {
    return this.post('/api/v1/shop/payments/simulate', { sale_token: token, result });
  }

  // ─── KI-Layer (ADR 004) ─────────────────────────────────────────────────────

  getAiConfig(): Promise<AiConfig> {
    return this.get('/api/v1/ai/config');
  }

  aiChat(messages: AiChatMessage[], context?: string): Promise<AiChatResponse> {
    return this.post('/api/v1/ai/chat', { messages, context: context ?? null });
  }

  aiWrite(instruction: string, content: AiDocContent | null): Promise<{ content: AiDocContent }> {
    return this.post('/api/v1/ai/write', { instruction, content });
  }

  aiImageEdit(imageUrl: string, instruction: string): Promise<AiImageEditResponse> {
    return this.post('/api/v1/ai/image-edit', { image_url: imageUrl, instruction });
  }

  aiConfirmAction(actionId: number): Promise<AiProposal> {
    return this.post(`/api/v1/ai/actions/${actionId}/confirm`, {});
  }

  aiRejectAction(actionId: number): Promise<AiProposal> {
    return this.post(`/api/v1/ai/actions/${actionId}/reject`, {});
  }

  // ─── Contact form ──────────────────────────────────────────────────────────

  sendContactForm(data: {
    name: string;
    email: string;
    phone?: string;
    subject: string;
    message: string;
  }): Promise<{ ok: boolean }> {
    return this.post('/api/v1/contact', data);
  }
}

// ─── CompanySettings field mapping (frontend ↔ backend) ──────────────────────

function mapSettingsFromBackend(s: Record<string, unknown>): CompanySettings {
  return {
    object_id: (s.object_id as number | null) ?? null,
    company_name: (s.company_name as string) ?? '',
    legal_form: (s.legal_form as string | null) ?? null,
    street: (s.street as string) ?? '',
    street_number: (s.street_nr as string | null) ?? null,
    zip: (s.zip_code as string) ?? '',
    city: (s.city as string) ?? '',
    country: (s.country as string) ?? '',
    uid: (s.uid_number as string | null) ?? null,
    vat_number: (s.vat_number as string | null) ?? null,
    trade_register_number: (s.trade_register_nr as string | null) ?? null,
    trade_register_canton: (s.trade_register_canton as string | null) ?? null,
    share_capital: (s.share_capital as string | null) ?? null,
    email: (s.email as string) ?? '',
    phone: (s.phone as string | null) ?? null,
    website: (s.website as string) ?? '',
    logo_url: (s.logo_path as string | null) ?? null,
    iban: null,
    iban_masked: (s.iban_masked as string | null) ?? null,
    qr_iban: null,
    qr_iban_masked: (s.qr_iban_masked as string | null) ?? null,
    bank_name: (s.bank as string | null) ?? null,
    bic: (s.bic_swift as string | null) ?? null,
    vat_method: (s.vat_method as 'effektiv' | 'saldosteuersatz' | null) ?? 'effektiv',
    vat_period: (s.vat_period as 'quartal' | 'semester' | 'jahr' | null) ?? 'quartal',
    default_payment_days: (s.default_payment_days as number) ?? 30,
    default_discount_percent: s.default_skonto_pct != null ? String(s.default_skonto_pct) : null,
    default_discount_days: (s.default_skonto_days as number | null) ?? null,
    oss_active: (s.oss_active as boolean) ?? false,
    oss_number: (s.oss_reg_number as string | null) ?? null,
    vies_validation: (s.vies_active as boolean) ?? false,
    stripe_publishable_key: (s.stripe_publishable_key as string | null) ?? null,
    plausible_domain: (s.plausible_domain as string | null) ?? null,
    hcaptcha_site_key: (s.hcaptcha_site_key as string | null) ?? null,
    google_maps_api_key: (s.google_maps_api_key as string | null) ?? null,
    default_receiving_location_id: (s.default_receiving_location_id as number | null) ?? null,
    shop_currencies: (s.shop_currencies as string[] | null) ?? ['CHF', 'EUR', 'USD'],
    shop_country_currency: (s.shop_country_currency as Record<string, string> | null) ?? null,
    shop_default_currency: (s.shop_default_currency as string | null) ?? 'CHF',
    payments_provider: (s.payments_provider as string | null) ?? null,
    pricing_zone_factors: (s.pricing_zone_factors as Record<string, number> | null) ?? null,
    legal_documents: (s.legal_documents as Record<string, number> | null) ?? null,
    legal_ack_config: (s.legal_ack_config as Record<string, string[]> | null) ?? null,
  };
}

function mapSettingsToBackend(s: Partial<CompanySettings>): Record<string, unknown> {
  const fieldMap: Record<string, string> = {
    street_number: 'street_nr',
    zip: 'zip_code',
    uid: 'uid_number',
    trade_register_number: 'trade_register_nr',
    bank_name: 'bank',
    bic: 'bic_swift',
    oss_number: 'oss_reg_number',
    vies_validation: 'vies_active',
    default_discount_percent: 'default_skonto_pct',
    default_discount_days: 'default_skonto_days',
  };
  const skip = new Set(['iban_masked', 'qr_iban_masked', 'logo_url']);
  const result: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(s)) {
    if (skip.has(k)) continue;
    result[fieldMap[k] ?? k] = v;
  }
  return result;
}

export const api = new ApiClient();

// Absolute Anzeige-URL für ein Attachment (die DB speichert nur den relativen Token-Pfad).
export function attachmentUrl(path: string): string {
  if (!path) return path;
  if (/^https?:\/\//.test(path) || path.startsWith('data:')) return path;
  return `${API_BASE}${path}`;
}
