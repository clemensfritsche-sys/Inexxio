'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Plus, Package, ClipboardList, ScanLine, X, Loader2, Building2 } from 'lucide-react';
import { cn, formatObjectId } from '@/lib/utils';
import { TYPE_META, FILTER_TYPES } from '@/lib/erp-record';
import {userName, articleName, organizationName, orderName } from '@/lib/record-name';
import { articleStatus, organizationStatus, userStatus, orderStatus } from '@/lib/record-status';
import { RecordIcon, StatusBadge } from '@/components/erp/fields';
import { api } from '@/lib/api';
import type {Article, CompanySettings, UserProfile, ErpRecordType, InstanceSummary, OrderSummary, Order } from '@/types';
import type { StatusCfg } from '@/lib/status-flow';
import { userInitials, UserDetail } from '@/components/erp/user-detail';
import { ErpNavContext } from '@/components/erp/obj-id';
import { useScan } from '@/components/scan/scan-provider';
import type { ScanCandidate } from '@/lib/scan';
import { ErrorBoundary } from '@/components/erp/error-boundary';
import { setOpenRecord } from '@/lib/feedback';
import { ArticleDetail } from '@/components/erp/article-detail';
import { OrderDetail, type OrderSeed } from '@/components/erp/order-detail';
import { InstanceDetail } from '@/components/erp/instance-detail';
import { OrganizationDetail } from '@/components/erp/organization-detail';

// Typ-Metadaten (Label, Symbol, Symbolfarbe) + Filter-Reihenfolge sind mit dem Detail
// geteilt – EINE Quelle der Wahrheit für die Typ-Identität: lib/erp-record.ts.
const INSTANCE_PAGE = 100;   // Seitengrösse des server-paginierten Instanz-Feeds
// Ab wann gilt der Feed nach einer Pause als veraltet und wird bei der Rückkehr (Tab wieder
// sichtbar / Fenster fokussiert) EINMAL nachgeladen. Bewusst kein Polling – das kostet
// Cloud-Run-Zeit, ohne dass jemand hinschaut.
const STALE_AFTER_MS = 60_000;

type Row =
  | { type: 'user'; key: string; objectId: number | null; data: UserProfile }
  | { type: 'article'; key: string; objectId: number | null; data: Article }
  | { type: 'order'; key: string; objectId: number | null; data: OrderSummary }
  | { type: 'instance'; key: string; objectId: number | null; data: InstanceSummary }
  | { type: 'organization'; key: string; objectId: number | null; data: CompanySettings };

// Der Name eines Datensatzes kommt aus der EINEN Ableitung (`lib/record-name`) – nie steht
// hier der Typ (den sagt das Symbol). `null` = noch ohne Namen (Notiz #177).
function rowTitle(row: Row): string | null {
  if (row.type === 'user') return userName(row.data);
  if (row.type === 'order') return orderName(row.data);
  if (row.type === 'instance') return row.data.article_name?.trim() || null;
  if (row.type === 'organization') return organizationName(row.data);
  return articleName(row.data);
}

// Der Zustand kommt aus der EINEN Ableitung (`lib/record-status`) – genau wie der Name.
// Hier wird nur verteilt, nie gebaut: sonst läuft der Feed vom Detail weg (Notiz #379).
function rowStatus(row: Row): StatusCfg | null {
  if (row.type === 'user') return userStatus(row.data);
  if (row.type === 'order') return orderStatus(row.data);
  // Die Instanz ist eine Gruppe und trägt keinen Zustand (Testnotiz #675) – ein Wort
  // hier wäre bei einer Charge mit gemischten Stücken eine Behauptung.
  if (row.type === 'instance') return null;
  if (row.type === 'organization') return organizationStatus(row.data);
  return articleStatus(row.data);
}

// Gesucht wird über Name + Typ-Wort + Objektnummer: «auftrag» bleibt als Suchwort nützlich,
// obwohl es nicht mehr als Bezeichnung angezeigt wird.
function rowSearchText(row: Row): string {
  const parts = [rowTitle(row) ?? '', TYPE_META[row.type].label, String(row.objectId ?? '')];
  if (row.type === 'user') parts.push(row.data.email);
  if (row.type === 'article') parts.push(row.data.size ?? '');
  return parts.join(' ').toLowerCase();
}

/**
 * **Die EINE Suchregel des Feeds.** Sie gilt für die Liste **und** für die Vorschläge im
 * Scanner – nicht als zweite Implementierung «für die Kamera», sondern als derselbe
 * Aufruf: sonst fände die eine Suche etwas, das die andere nicht kennt.
 *
 * `needle` kommt bereits in Kleinschreibung.
 */
function feedMatch(row: Row, needle: string): boolean {
  return rowSearchText(row).includes(needle);
}

/** Ein Datensatz als Scanner-Vorschlag: Nummer + «Typ · Name». */
function toCandidate(row: Row): ScanCandidate {
  const label = TYPE_META[row.type].label;
  const title = rowTitle(row);
  return { objectId: row.objectId as number, label: title ? `${label} · ${title}` : label };
}

// Wie viele Vorschläge der Scanner höchstens anbietet (er zeigt ohnehin nur die ersten).
const SUGGEST_LIMIT = 8;

// ─── Feed item ───────────────────────────────────────────────────────────────

function FeedItem({ row, sel, onClick }: { row: Row; sel: boolean; onClick: () => void }) {
  const title = rowTitle(row);

  const badge = rowStatus(row);

  return (
    <button
      onClick={onClick}
      className={cn(
        // Leichter (Notizen #206/#300): kleineres Symbol, halbfetter Titel, **mehr Luft**
        // (12 px statt 10 px innen, 4 px zwischen den Zeilen). Der Feed ist eine Liste zum
        // Überfliegen – die Trennung machen Weissraum und Ausrichtung, nicht Fläche.
        'w-full flex items-center gap-3 px-3 py-3 mb-1 rounded-ds-md text-left transition-colors',
        sel ? 'bg-accent-soft' : 'hover:bg-bg-2',
      )}
    >
      {/* **Dieselbe Komponente wie im Detail-Kopf** (#697/#699) – Symbol, Farbfamilie,
          Form und das Abweichungs-Zeichen kommen aus EINER Stelle; nur die Grösse
          unterscheidet die beiden Orte. Zwei Implementierungen driften garantiert
          auseinander (#688). */}
      <RecordIcon
        type={row.type}
        size={28}
        photoUrl={row.type === 'user' ? row.data.photo_url : undefined}
        initials={row.type === 'user' ? userInitials(title ?? '', row.data.email) : undefined}
        deviation={row.type === 'order' && row.data.is_deviation}
      />
      <div className="min-w-0 flex-1">
        <div className={cn('text-sm font-semibold truncate', sel ? 'text-accent-ink' : title ? 'text-fg-1' : 'text-fg-4 italic')}>
          {title ?? (row.type === 'user' ? 'Kein Name' : 'Ohne Bezeichnung')}
        </div>
        {/* Zweite Zeile: Kennung + Zustand. Der Zustand ist die **gefüllte Pille mit Symbol**
            – dieselbe Form wie im Detail-Kopf (Notiz #334): derselbe Zustand soll überall
            gleich aussehen. Die Luft, die den Feed leichter macht (Notiz #300), kommt aus
            Polsterung und Zeilenabstand, nicht aus einer zweiten Status-Form. */}
        <div className="flex items-center gap-2.5 mt-1">
          <span className="text-fg-4 tabular-nums" style={{ font: 'var(--mono-sm)' }}>{formatObjectId(row.objectId)}</span>
          {badge && <StatusBadge cfg={badge} size={11} />}
        </div>
      </div>
    </button>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ErpPage() {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  // Instanzen (höchste Kardinalität): server-paginiert + server-durchsucht.
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [instances, setInstances] = useState<InstanceSummary[]>([]);
  const [instanceLoadingMore, setInstanceLoadingMore] = useState(false);
  // Unternehmen (Gesellschaften): ein gleichrangiger ERP-Datensatztyp `organization` –
  // der Betreiber (ältestes) + jede weitere Gesellschaft. Admin-only.
  const [companies, setCompanies] = useState<CompanySettings[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<ErpRecordType | null>(null);
  const [sel, setSel] = useState<{ type: ErpRecordType; objectId: number } | null>(null);
  const [creating, setCreating] = useState<'article' | 'order' | null>(null);
  /**
   * **Der Entwurf mit einer bereits gewählten Einzelinstanz** (Abweichungsauftrag §3.1).
   *
   * Der Klick an einem Stück im Prozess öffnet einen **ganz gewöhnlichen** Auftragsentwurf –
   * er steht nur schon in der Definition drin. Angelegt wird dabei nichts: ein Entwurf lebt
   * im Browser, bis er freigegeben wird (§6.1). Eine eigene «Abweichung anlegen»-Aktion
   * gäbe es nicht zu bauen, sie wäre ein zweiter Anlage-Weg.
   */
  const [orderSeed, setOrderSeed] = useState<OrderSeed | null>(null);
  const [mobileView, setMobileView] = useState<'list' | 'detail'>('list');
  const [isAdmin, setIsAdmin] = useState(false);
  const [viewerRole, setViewerRole] = useState<'staff' | 'supplier'>('staff');
  const [plusOpen, setPlusOpen] = useState(false);
  const [visibleCount, setVisibleCount] = useState(50);
  const plusRef = useRef<HTMLDivElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  // Aktueller «mehr laden»-Handler (immer frisch, vom Sentinel-Observer aufgerufen).
  const loadMoreRef = useRef<() => void>(() => {});
  const lastLoadRef = useRef<number>(0);   // Zeitpunkt des letzten Feed-Ladens (Rückkehr-Refresh)

  const suppliers = users.filter((u) => u.role === 'supplier');
  const scan = useScan();

  useEffect(() => {
    // Kern-Feeds (geringe Kardinalität) blockierend laden – die Shell erscheint
    // sofort. Instanzen (höchste Kardinalität) danach nachladen.
    lastLoadRef.current = Date.now();
    Promise.allSettled([
      api.getErpRecords(), api.getArticles(), api.getOrders(), api.getMe(),
    ]).then(([u, a, o, me]) => {
      if (u.status === 'fulfilled') setUsers(u.value);
      if (a.status === 'fulfilled') setArticles(a.value);
      if (o.status === 'fulfilled') setOrders(o.value);
      if (me.status === 'fulfilled') {
        setIsAdmin(me.value.role === 'admin');
        setViewerRole(me.value.role === 'admin' || me.value.role === 'employee' ? 'staff' : 'supplier');
        // Unternehmen erst laden, wenn die Rolle feststeht – der Endpunkt ist admin-only.
        if (me.value.role === 'admin') api.getCompanies().then(setCompanies).catch(() => {});
      }
      setLoading(false);
    });
  }, []);

  // Tiefer Link «?open=<Objektnummer>» (z. B. von der KI-Navigation): den Datensatz direkt
  // öffnen. Typ serverseitig auflösen (funktioniert auch, bevor der Feed geladen ist).
  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get('open');
    const oid = raw ? Number(raw) : NaN;
    if (!Number.isFinite(oid)) return;
    api.resolveObject(oid).then((r) => {
      setCreating(null);
      setSel({ type: r.object_type as ErpRecordType, objectId: oid });
      setMobileView('detail');
    }).catch(() => {});
  }, []);

  // Instanz-Feed: server-paginiert + server-durchsucht. Lädt Seite 0 beim Start und
  // bei jeder (entprellten) Suchänderung neu; weitere Seiten via Infinite-Scroll.
  useEffect(() => {
    const q = search.trim();
    // FIX: Antworten einer ÄLTEREN Suche konnten eine neuere überholen (Suche tippen und
    // sofort löschen → 0ms- vor 300ms-Antwort) und Liste/Zähler inkonsistent überschreiben.
    // Der Cleanup markiert den vorherigen Effekt als veraltet – späte Antworten verfallen.
    let stale = false;
    const t = setTimeout(() => {
      api.getInstances(INSTANCE_PAGE, 0, q).then((rows) => { if (!stale) setInstances(rows); }).catch(() => {});
    }, q ? 300 : 0);
    return () => { stale = true; clearTimeout(t); };
  }, [search]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (plusRef.current && !plusRef.current.contains(e.target as Node)) setPlusOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  // KI-Live-Refresh: legt/ändert die KI im Chat einen Artikel/Auftrag/Prozessschritt,
  // feuert das Widget 'inexxio:data-changed' – der Feed lädt sofort nach, ohne dass der
  // Nutzer manuell aktualisieren muss (Optimierung #2). Re-Abo bei Suchänderung, damit
  // die Instanzen mit der aktuellen Suche neu geladen werden.
  useEffect(() => {
    const q = search.trim();
    function onDataChanged() {
      lastLoadRef.current = Date.now();
      api.getErpRecords().then(setUsers).catch(() => {});
      api.getArticles().then(setArticles).catch(() => {});
      api.getOrders().then(setOrders).catch(() => {});
      api.getInstances(INSTANCE_PAGE, 0, q).then(setInstances).catch(() => {});
    }
    // **Rückkehr nach Pause**: Der Feed war ein Schnappschuss vom Seitenaufbau – wer das ERP
    // ein paar Minuten liegen liess, sah alte Daten (und musste F5 drücken). Jetzt lädt er
    // beim Zurückkommen nach, aber NUR wenn er wirklich veraltet ist (Schwelle unten) –
    // kein Polling, kein Traffic beim kurzen Tab-Wechsel: ein Nachladen je Rückkehr.
    function onBack() {
      if (document.visibilityState !== 'visible') return;
      if (Date.now() - lastLoadRef.current < STALE_AFTER_MS) return;
      onDataChanged();
    }
    window.addEventListener('inexxio:data-changed', onDataChanged);
    document.addEventListener('visibilitychange', onBack);
    window.addEventListener('focus', onBack);
    return () => {
      window.removeEventListener('inexxio:data-changed', onDataChanged);
      document.removeEventListener('visibilitychange', onBack);
      window.removeEventListener('focus', onBack);
    };
  }, [search]);

  // Infinite scroll: Observer per Callback-Ref an den Sentinel hängen (robust, auch
  // wenn der Sentinel erst nach dem Nachladen der Daten erscheint). Ruft den stets
  // frischen loadMoreRef-Handler.
  const sentinelCb = useCallback((node: HTMLDivElement | null) => {
    observerRef.current?.disconnect();
    if (!node) return;
    observerRef.current = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) loadMoreRef.current(); },
      { threshold: 0.1 },
    );
    observerRef.current.observe(node);
  }, []);

  // Sichtbarkeits-Zähler zurücksetzen, wenn Suche oder Filter wechselt
  useEffect(() => { setVisibleCount(50); }, [typeFilter, search]);

  const rows: Row[] = [
    // Jedes **Unternehmen** ist ein nummerierter ERP-Datensatz – nur für Admins sichtbar
    // (Firmen-/Bank-/API-Konfiguration ist sensibel, und wer Gesellschaften anlegen darf,
    // ist ohnehin auf Admin beschränkt).
    ...companies.map((s): Row => ({
      type: 'organization', key: `org${s.object_id}`, objectId: s.object_id ?? null, data: s,
    })),
    ...users.map((u): Row => ({ type: 'user', key: `u${u.id}`, objectId: u.object_id, data: u })),
    ...articles.map((a): Row => ({ type: 'article', key: `a${a.id}`, objectId: a.object_id, data: a })),
    ...orders.map((o): Row => ({ type: 'order', key: `o${o.id}`, objectId: o.object_id, data: o })),
    ...instances.map((i): Row => ({ type: 'instance', key: `i${i.id}`, objectId: i.object_id, data: i })),
    // FIX: Fallback -Infinity ergab NaN, sobald ZWEI Zeilen ohne Objektnummer verglichen
    // wurden (-Infinity − -Infinity = NaN) – ein NaN-Komparator verletzt die Sortier-Ordnung
    // und macht die Reihenfolge undefiniert. 0 sortiert Zeilen ohne Nummer stabil ans Ende
    // (alle echten Nummern sind 9-stellig > 0).
  ].sort((x, y) => (y.objectId ?? 0) - (x.objectId ?? 0));   // höchste Nummer zuerst

  const counts = rows.reduce<Record<string, number>>((acc, r) => {
    acc[r.type] = (acc[r.type] ?? 0) + 1;
    return acc;
  }, {});

  const filtered = rows.filter((r) => {
    if (typeFilter && r.type !== typeFilter) return false;
    // Instanzen sind bereits server-seitig durchsucht (kein erneuter Client-Filter).
    if (search && r.type !== 'instance' && !feedMatch(r, search.toLowerCase())) return false;
    return true;
  });

  const selectedRow = sel ? rows.find((r) => r.type === sel.type && r.objectId === sel.objectId) ?? null : null;

  // Cross-Feed-Navigation (z. B. Klick auf den Artikel im Instanz-Detail): zeigt der ausgewählte
  // Datensatz auf einen Typ, dessen Detail sonst AUS DER LISTE rendert (Artikel), er aber
  // (noch) nicht geladen ist, wird er on-demand nachgeladen – sonst bliebe die Detailseite leer.
  // Auftrag/Instanz haben bereits ihren eigenen Fetch-Pfad (orderDetail/instanceDetail).
  const [navRecord, setNavRecord] = useState<Row | null>(null);
  useEffect(() => {
    if (!sel || selectedRow || sel.type === 'instance') { setNavRecord(null); return; }
    let cancelled = false;
    const load: Promise<Row | null> =
      sel.type === 'article'
        ? api.getArticle(sel.objectId).then((d): Row => ({ type: 'article', key: `a${d.id}`, objectId: sel.objectId, data: d }))
        : Promise.resolve(null);
    load.then((row) => { if (!cancelled) setNavRecord(row); }).catch(() => { if (!cancelled) setNavRecord(null); });
    return () => { cancelled = true; };
  }, [sel, selectedRow]);
  // Für aus-der-Liste rendernde Typen: der geladene Feed-Datensatz ODER der on-demand nachgeladene.
  const activeRow = selectedRow ?? navRecord;

  // Testnotizen: dem Notiz-Widget melden, WAS gerade offen ist. Der Feed ist ein
  // Master-Detail auf EINER Route – ohne diese Meldung trüge eine Notiz aus dem
  // Detailfenster keine Objektnummer (die Route bleibt schlicht `/erp`).
  useEffect(() => {
    setOpenRecord(sel ? { kind: TYPE_META[sel.type]?.label ?? sel.type, objectId: sel.objectId } : null);
  }, [sel]);

  // Instanz-Pagination: nur laden, wenn Instanzen sichtbar sind (Feed «alle» oder «Instanzen»).
  const instancesRelevant = typeFilter === null || typeFilter === 'instance';
  const hasMoreInstances = instancesRelevant && instances.length < instances.length;
  const displayCount = (t: ErpRecordType): number => (t === 'instance' ? instances.length : (counts[t] ?? 0));

  async function loadMoreInstances() {
    if (instanceLoadingMore) return;
    setInstanceLoadingMore(true);
    try {
      const next = await api.getInstances(INSTANCE_PAGE, instances.length, search.trim());
      setInstances((prev) => {
        const seen = new Set(prev.map((i) => i.id));
        return [...prev, ...next.filter((i) => !seen.has(i.id))];
      });
    } catch { /* ignore */ } finally {
      setInstanceLoadingMore(false);
    }
  }

  // Beim Sichtbarwerden des Sentinels: mehr Zeilen rendern + ggf. nächste Instanz-Seite laden.
  loadMoreRef.current = () => {
    setVisibleCount((c) => c + 50);
    if (hasMoreInstances) loadMoreInstances();
  };

  function handleSelect(type: ErpRecordType, objectId: number | null) {
    if (objectId == null) return;
    setCreating(null);
    setSel({ type, objectId });
    setMobileView('detail');
  }

  // Klick/Scan auf eine Objektnummer → Datensatz öffnen. Ist er nicht im geladenen
  // Feed (z. B. eine nicht geladene Instanz), wird der Typ serverseitig aufgelöst.
  async function openByObjectId(objectId: number) {
    const row = rows.find((r) => r.objectId === objectId);
    if (row) { handleSelect(row.type, objectId); return; }
    try {
      const r = await api.resolveObject(objectId);
      handleSelect(r.object_type as ErpRecordType, objectId);
    } catch { /* Objekt nicht gefunden – ignorieren */ }
  }

  /**
   * **Die Suche des Feeds – für den Scanner.** Nicht nachgebaut, sondern derselbe Aufruf:
   * die geladenen Zeilen durch `feedMatch`, die Instanzen durch dieselbe Server-Suche
   * (`api.getInstances(…, search)`), die auch der Instanz-Feed benutzt. Eine zweite
   * Fassung «für die Kamera» hätte anders getroffen als die Liste daneben.
   */
  async function suggestFromFeed(q: string): Promise<ScanCandidate[]> {
    const needle = q.trim().toLowerCase();
    if (!needle) return [];
    const local = rows
      .filter((r) => r.objectId != null && r.type !== 'instance' && feedMatch(r, needle))
      .slice(0, SUGGEST_LIMIT)
      .map(toCandidate);
    // Instanzen haben die höchste Kardinalität und werden darum serverseitig gesucht –
    // genau wie im Feed. Fällt die Abfrage aus, bleiben die lokalen Treffer.
    const found = await api.getInstances(SUGGEST_LIMIT, 0, needle).catch(() => []);
    return [
      ...local,
      ...found.map((i): ScanCandidate => ({
        objectId: i.object_id,
        label: `${TYPE_META.instance.label} · ${i.article_name ?? 'Ohne Bezeichnung'}`,
      })),
    ];
  }

  /**
   * **Suchen mit der Kamera.** Ein freier Lookup: kein `expected`, kein `restrict` –
   * jede Objektnummer des Hauses darf es sein, und was sie ist, löst der Server auf.
   *
   * `exists` ist dabei der Unterschied zwischen «funktioniert» und «tut so»: ohne die
   * Frage gilt jede formal gültige 9-stellige Zahl, der Dialog meldet Erfolg, schliesst –
   * und hier passiert nichts, weil die Nummer keinen Datensatz hat. Mit ihr sagt es der
   * Rahmen im Bild, wo der Mensch gerade hinschaut.
   *
   * `suggest` ist die **Vorschlagsquelle**: ohne sie gab es hier nichts zu filtern (der
   * freie Lookup hat naturgemäss keine Kandidatenliste), und wer eine Teilnummer tippte,
   * sah nichts. Die Gültigkeitsregel bleibt davon unberührt.
   */
  function openScanner() {
    scan({
      steps: [{
        label: 'Datensatz',
        exists: (id) => api.resolveObject(id).then(() => true).catch(() => false),
        suggest: suggestFromFeed,
      }],
      onComplete: ([objectId]) => { void openByObjectId(objectId); },
    });
  }

  function startCreate(type: 'article' | 'order', seed?: OrderSeed) {
    setPlusOpen(false);
    setSel(null);
    setOrderSeed(seed ?? null);
    setCreating(type);
    setMobileView('detail');
  }

  function handleCompanySaved(s: CompanySettings) {
    setCompanies((prev) => prev.map((x) => (x.object_id === s.object_id ? s : x)));
    if (s.is_operator) {
      // Betreiber gewechselt: die ganze Liste neu laden, damit der frühere Betreiber
      // seinen Titel verliert (genau EINE Gesellschaft trägt is_operator). Und die im
      // Fenster mitgeführte Firmenangabe (Impressum) nachziehen.
      api.getCompanies().then(setCompanies).catch(() => {});
    }
  }

  /** Neue Gesellschaft (nur Admin). Entsteht sofort als Datensatz mit Objektnummer –
   *  ein leeres Anlage-Formular gäbe es sonst nur hier, überall sonst legt das ERP
   *  direkt an und man füllt danach aus. */
  async function createCompany() {
    setPlusOpen(false);
    try {
      const s = await api.createCompany('Neues Unternehmen');
      setCompanies((prev) => [...prev, s]);
      setCreating(null);
      if (s.object_id != null) setSel({ type: 'organization', objectId: s.object_id });
      setMobileView('detail');
    } catch { /* Fehler zeigt das Detailfenster beim Speichern – hier kein Blocker */ }
  }

  function handleArticleSaved(a: Article) {
    setArticles((prev) => (prev.some((x) => x.id === a.id) ? prev.map((x) => (x.id === a.id ? a : x)) : [...prev, a]));
    setCreating(null);
    if (a.object_id != null) setSel({ type: 'article', objectId: a.object_id });
  }


  function handleUserSaved(u: UserProfile) {
    setUsers((prev) => prev.map((x) => (x.id === u.id ? u : x)));
  }

  // Erst hier existiert der Auftrag: die Anlage liefert ihn samt frisch vergebener
  // Objektnummer zurück, und der Feed übernimmt ihn ohne Nachladen.
  function handleOrderSaved(o: Order) {
    setCreating(null);
    setOrders((prev) => (prev.some((x) => x.id === o.id) ? prev.map((x) => (x.id === o.id ? o : x)) : [...prev, o]));
    setSel({ type: 'order', objectId: o.object_id });
  }

  function cancelCreate() {
    setCreating(null);
    setMobileView('list');
  }

  const showList = mobileView === 'list';
  const hasDetail = creating !== null || activeRow !== null || sel?.type === 'instance';

  return (
    <ErpNavContext.Provider value={openByObjectId}>
    {/* 100dvh statt 100vh: auf Mobile berücksichtigt die dynamische Viewport-Höhe die
        Browser-Leiste – sonst rutscht der «+»-FAB (bottom) unter die Adressleiste (unsichtbar). */}
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100dvh - 72px)' }}>
      <div className="flex overflow-hidden" style={{ flex: 1, minHeight: 0 }}>

        {/* ── List panel ───────────────────────────────────────────────────── */}
        <div className={cn(
          'flex-shrink-0 border-r border-border-1 flex flex-col bg-bg-1 relative',
          'w-full md:w-[300px] lg:w-[336px]',
          showList ? 'flex' : 'hidden md:flex',
        )}>
          {/* Suche + Scan */}
          <div className="flex items-center gap-2.5 px-5 pt-4 pb-3.5">
            <div className="flex-1 min-w-0 flex items-center gap-2.5 rounded-ds-md border border-border-2 px-2.5 py-2">
              <Search size={17} className="flex-none text-fg-4" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Suchen…"
                className="flex-1 min-w-0 border-none outline-none bg-transparent text-sm text-fg-1 placeholder:text-fg-4"
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  title="Eingabe löschen"
                  aria-label="Eingabe löschen"
                  className="flex-none w-8 h-8 rounded-ds-sm flex items-center justify-center bg-bg-3 text-fg-3 hover:text-fg-1 transition-colors"
                >
                  <X size={13} />
                </button>
              )}
              <button
                onClick={openScanner}
                data-tip="Datensatz scannen"
                data-tip-pos="bottom"
                aria-label="Datensatz scannen"
                className="flex-none w-10 h-10 rounded-ds-sm flex items-center justify-center bg-bg-2 border border-border-1 text-fg-3 hover:text-fg-1 hover:bg-bg-3 transition-colors"
              >
                <ScanLine size={18} />
              </button>
            </div>
          </div>
          {/* Typ-Filter — Symbol-first, aktiv expandiert zu Label + Anzahl (Farbe = Typ) */}
          <div className="flex flex-wrap gap-1.5 px-5 pb-4 border-b border-border-1">
            {FILTER_TYPES.filter((t) => displayCount(t)).map((t) => {
              const active = typeFilter === t;
              const meta = TYPE_META[t];
              const Icon = meta.icon;
              return (
                <button
                  key={t}
                  onClick={() => setTypeFilter(active ? null : t)}
                  data-tip={`${meta.label} · ${displayCount(t)}`}
                  data-tip-pos="bottom"
                  {...(active ? { 'data-tip-hidden': '' } : {})}
                  className={cn(
                    'h-[42px] rounded-ds-md flex items-center justify-center gap-1.5 border transition-colors',
                    active ? 'border-transparent px-3.5' : 'min-w-[42px] border-border-1 bg-bg-1 hover:bg-bg-2',
                  )}
                  style={active ? { background: meta.bg, color: meta.fg } : { color: meta.fg }}
                >
                  <Icon size={18} />
                  {active && (
                    <>
                      <span className="text-[13px] font-bold">{meta.label}</span>
                      <span className="text-[12.5px] font-bold tabular-nums opacity-60">{displayCount(t)}</span>
                    </>
                  )}
                </button>
              );
            })}
          </div>

          <div className="flex-1 overflow-y-auto min-h-0 p-2 pb-24">
            {loading && <div className="p-6 text-center text-sm text-fg-4">Laden…</div>}
            {!loading && filtered.length === 0 && (
              <div className="p-6 text-center text-sm text-fg-4">
                {search || typeFilter ? 'Keine Treffer' : 'Keine Datensätze'}
              </div>
            )}
            {filtered.slice(0, visibleCount).map((r) => (
              <FeedItem
                key={r.key}
                row={r}
                sel={!creating && !!sel && sel.type === r.type && sel.objectId === r.objectId}
                onClick={() => handleSelect(r.type, r.objectId)}
              />
            ))}
            {(visibleCount < filtered.length || hasMoreInstances) && (
              <div ref={sentinelCb} className="flex items-center justify-center gap-2 p-3.5 text-fg-4 text-xs">
                <Loader2 size={15} className="animate-spin" />
                <span>Weitere werden geladen…</span>
              </div>
            )}
          </div>

          {/* FAB — neuen Datensatz anlegen (Menü öffnet nach oben) */}
          {viewerRole === 'staff' && (
            <div ref={plusRef} className="absolute left-5 bottom-5 z-20">
              {plusOpen && (
                <div className="absolute left-0 bottom-[calc(100%+10px)] bg-bg-1 border border-border-1 rounded-ds-md shadow-ds-lg p-1 min-w-[170px]">
                  <button onClick={() => startCreate('article')} style={menuItemStyle}>
                    <Package size={15} style={{ color: 'var(--fg-3)' }} /> Artikel
                  </button>
                  <button onClick={() => startCreate('order')} style={menuItemStyle}>
                    <ClipboardList size={15} style={{ color: 'var(--fg-3)' }} /> Auftrag
                  </button>
                  {/* Gesellschaften anlegen ist bewusst Admin-Sache (fix vorgegeben). */}
                  {isAdmin && (
                    <button onClick={createCompany} style={menuItemStyle}>
                      <Building2 size={15} style={{ color: 'var(--fg-3)' }} /> Unternehmen
                    </button>
                  )}
                </div>
              )}
              <button
                onClick={() => setPlusOpen((o) => !o)}
                data-tip={plusOpen ? undefined : 'Neuen Datensatz anlegen'}
                aria-label="Neuen Datensatz anlegen"
                className="w-[54px] h-[54px] rounded-full bg-inexxio hover:bg-inexxio-deep text-white flex items-center justify-center transition-all hover:-translate-y-0.5"
                style={{ boxShadow: '0 10px 22px rgba(179,18,15,.28)' }}
              >
                <Plus size={24} className={cn('transition-transform', plusOpen && 'rotate-45')} />
              </button>
            </div>
          )}
        </div>

        {/* ── Detail panel ─────────────────────────────────────────────────── */}
        <div className={cn(
          'flex-1 overflow-hidden flex flex-col',
          !showList ? 'flex' : 'hidden md:flex',
        )}>
          {/* Ein Render-Fehler in EINEM Datensatz darf nie die ganze ERP-Oberfläche
              sperren – der Boundary zeigt eine erholbare Meldung; `resetKey` setzt ihn
              beim Wechsel der Auswahl zurück, «Zurück» führt in die Liste. */}
          <ErrorBoundary
            resetKey={creating ?? (sel ? `${sel.type}-${sel.objectId}` : 'none')}
            onReset={() => { setSel(null); setCreating(null); setMobileView('list'); }}
          >
          {creating === 'article' && (
            <ArticleDetail key="new-article" record={null} suppliers={suppliers} onSaved={handleArticleSaved} onCancel={cancelCreate} onBack={cancelCreate} />
          )}
          {creating === 'order' && (
            <OrderDetail key="new-order" record={null} seed={orderSeed} onSaved={handleOrderSaved} onBack={cancelCreate} />
          )}
          {!creating && activeRow?.type === 'order' && (
            <OrderDetail
              key={activeRow.key}
              record={activeRow.data as Order}
              onSaved={handleOrderSaved}
              onDeviate={(seed) => startCreate('order', seed)}
              onBack={() => setMobileView('list')}
            />
          )}
          {!creating && activeRow?.type === 'user' && (
            <UserDetail key={activeRow.key} record={activeRow.data} onSave={handleUserSaved} isAdmin={isAdmin} onBack={() => setMobileView('list')} />
          )}
          {!creating && activeRow?.type === 'article' && (
            <ArticleDetail key={activeRow.key} record={activeRow.data} suppliers={suppliers}
              onSaved={handleArticleSaved}
              onRefresh={() => api.getArticles().then(setArticles).catch(() => {})}
              // **Ein reiner Shortcut, kein zweiter Anlagepfad** (#690): derselbe Entwurf
              // wie über «+», nur mit vorbelegtem Artikel. Angelegt wird nichts – einen
              // Auftrag gibt es erst mit der Freigabe (#386).
              onCreateOrder={(articleObjectId) => startCreate('order', { articleObjectId })}
              onCancel={() => setMobileView('list')} onBack={() => setMobileView('list')} />
          )}
          {!creating && sel?.type === 'instance' && (
            <InstanceDetail key={`i-${sel.objectId}`} objectId={sel.objectId} onBack={() => setMobileView('list')} />
          )}
          {!creating && activeRow?.type === 'organization' && (
            <OrganizationDetail key={activeRow.key} record={activeRow.data}
              onSaved={handleCompanySaved} onBack={() => setMobileView('list')} />
          )}
          {!hasDetail && (
            <div className="flex-1 flex flex-col items-center justify-center bg-bg-2">
              <Package size={48} strokeWidth={1} className="text-fg-4" />
              <p className="mt-3 text-sm text-fg-3">Datensatz auswählen oder neu anlegen</p>
            </div>
          )}
          </ErrorBoundary>
        </div>
      </div>
    </div>
    </ErpNavContext.Provider>
  );
}

const menuItemStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8, width: '100%',
  padding: '9px 11px', borderRadius: 8, border: 'none', background: 'none',
  fontSize: 13, fontWeight: 600, color: 'var(--fg-2)', cursor: 'pointer', textAlign: 'left',
};
