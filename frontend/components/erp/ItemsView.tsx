"use client";

import { useState } from "react";
import useSWR from "swr";
import { Plus, Search, CheckCircle, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { formatObjectId } from "@/lib/format";
import { cn } from "@/lib/cn";
import type { Item, PaginatedResponse } from "@/types";
import ItemDetail from "./ItemDetail";

const fetcher = (url: string) => api.get<PaginatedResponse<Item>>(url);

export default function ItemsView() {
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [page, setPage] = useState(1);

  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (search) params.set("search", search);

  const { data, isLoading, mutate } = useSWR(
    `/api/v1/items?${params}`,
    fetcher
  );

  return (
    <div className="flex h-full gap-4">
      {/* List panel */}
      <div className={cn("flex flex-col", selectedId ? "hidden md:flex w-80 shrink-0" : "flex-1")}>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold text-gray-900">Artikel</h1>
          <button className="btn-primary flex items-center gap-1.5 text-sm py-1.5">
            <Plus size={15} />
            Neu
          </button>
        </div>

        {/* Search */}
        <div className="relative mb-3">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="search"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Suchen..."
            className="input pl-9 text-sm"
          />
        </div>

        {/* Item list */}
        <div className="flex-1 overflow-y-auto space-y-1">
          {isLoading && (
            <div className="text-center py-8 text-gray-400 text-sm">Laden...</div>
          )}
          {data?.items.map((item) => (
            <button
              key={item.id}
              onClick={() => setSelectedId(item.id)}
              className={cn(
                "w-full text-left px-3 py-3 rounded-lg border transition-colors",
                selectedId === item.id
                  ? "bg-brand-50 border-brand-300"
                  : "bg-white border-gray-200 hover:border-gray-300"
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-gray-400">
                  {formatObjectId(item.id)}
                </span>
                {item.is_approved ? (
                  <CheckCircle size={14} className="text-green-500 shrink-0" />
                ) : (
                  <XCircle size={14} className="text-yellow-500 shrink-0" />
                )}
              </div>
              <p className="font-medium text-sm text-gray-900 mt-0.5 truncate">{item.name}</p>
              <div className="flex items-center gap-2 mt-1">
                {item.category && (
                  <span className="badge-gray text-xs">{item.category}</span>
                )}
                {item.replaced_by_id && (
                  <span className="badge-red text-xs">Ersetzt</span>
                )}
              </div>
            </button>
          ))}

          {data && data.items.length === 0 && (
            <div className="text-center py-8 text-gray-400 text-sm">
              Keine Artikel gefunden
            </div>
          )}
        </div>

        {/* Pagination */}
        {data && data.total > 20 && (
          <div className="flex justify-between items-center pt-3 border-t border-gray-100">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
              className="btn-ghost text-sm disabled:opacity-40"
            >
              Zurück
            </button>
            <span className="text-xs text-gray-500">
              {(page - 1) * 20 + 1}–{Math.min(page * 20, data.total)} / {data.total}
            </span>
            <button
              disabled={!data.has_more}
              onClick={() => setPage((p) => p + 1)}
              className="btn-ghost text-sm disabled:opacity-40"
            >
              Weiter
            </button>
          </div>
        )}
      </div>

      {/* Detail panel */}
      {selectedId && (
        <div className="flex-1 animate-slide-in">
          <ItemDetail
            itemId={selectedId}
            onClose={() => setSelectedId(null)}
            onUpdate={() => mutate()}
          />
        </div>
      )}
    </div>
  );
}
