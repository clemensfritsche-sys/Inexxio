"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { X, CheckCircle, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { formatObjectId, formatDateTime } from "@/lib/format";
import type { Item } from "@/types";

interface Props {
  itemId: number;
  onClose: () => void;
  onUpdate: () => void;
}

type SaveStatus = "idle" | "saving" | "saved" | "error";

export default function ItemDetail({ itemId, onClose, onUpdate }: Props) {
  const { data: item, mutate } = useSWR<Item>(
    `/api/v1/items/${itemId}`,
    (url: string) => api.get<Item>(url)
  );

  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [dirtyFields, setDirtyFields] = useState<Partial<Item>>({});

  // Debounced autosave (3s)
  useEffect(() => {
    if (Object.keys(dirtyFields).length === 0) return;
    const timer = setTimeout(async () => {
      setSaveStatus("saving");
      try {
        await api.patch(`/api/v1/items/${itemId}`, dirtyFields);
        setSaveStatus("saved");
        setDirtyFields({});
        mutate();
        onUpdate();
        setTimeout(() => setSaveStatus("idle"), 2000);
      } catch {
        setSaveStatus("error");
      }
    }, 3000);
    return () => clearTimeout(timer);
  }, [dirtyFields, itemId, mutate, onUpdate]);

  function handleChange<K extends keyof Item>(field: K, value: Item[K]) {
    setDirtyFields((prev) => ({ ...prev, [field]: value }));
  }

  if (!item) {
    return (
      <div className="card p-6 flex items-center justify-center h-64">
        <p className="text-gray-400 text-sm">Laden...</p>
      </div>
    );
  }

  const displayItem = { ...item, ...dirtyFields };

  return (
    <div className="card flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div
        className={`flex items-start justify-between p-4 border-b transition-all duration-300 ${
          saveStatus === "saved" ? "border-green-400 shadow-[0_0_0_2px_#16a34a40]" : "border-gray-200"
        }`}
      >
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-gray-400">{formatObjectId(item.id)}</span>
            {item.is_approved ? (
              <span className="badge-green">Freigegeben</span>
            ) : (
              <span className="badge-yellow">Nicht freigegeben</span>
            )}
            {item.replaced_by_id && (
              <span className="badge-red">Ersetzt durch #{formatObjectId(item.replaced_by_id)}</span>
            )}
          </div>
          <h2 className="text-lg font-bold text-gray-900 mt-1">{displayItem.name}</h2>
        </div>

        <div className="flex items-center gap-2">
          {saveStatus === "saving" && (
            <span className="text-xs text-gray-400">Speichert...</span>
          )}
          {saveStatus === "saved" && (
            <span className="text-xs text-green-600 flex items-center gap-1">
              <CheckCircle size={12} /> Gespeichert
            </span>
          )}
          {saveStatus === "error" && (
            <span className="text-xs text-red-600 flex items-center gap-1">
              <AlertCircle size={12} /> Fehler
            </span>
          )}
          <button
            onClick={onClose}
            className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-100"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Basic fields */}
        <section>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Allgemein</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Name *</label>
              <input
                className="input"
                value={displayItem.name}
                onChange={(e) => handleChange("name", e.target.value)}
              />
            </div>
            <div>
              <label className="label">Einheit</label>
              <input
                className="input"
                value={displayItem.unit}
                onChange={(e) => handleChange("unit", e.target.value)}
              />
            </div>
            <div>
              <label className="label">Kategorie</label>
              <input
                className="input"
                value={displayItem.category ?? ""}
                onChange={(e) => handleChange("category", e.target.value || null)}
                placeholder="z.B. Rohmaterial"
              />
            </div>
            <div>
              <label className="label">Grösse / Spez.</label>
              <input
                className="input"
                value={displayItem.size ?? ""}
                onChange={(e) => handleChange("size", e.target.value || null)}
                placeholder="z.B. M6×20"
              />
            </div>
            <div className="md:col-span-2">
              <label className="label">Beschreibung</label>
              <textarea
                className="input resize-none"
                rows={3}
                value={displayItem.description ?? ""}
                onChange={(e) => handleChange("description", e.target.value || null)}
              />
            </div>
          </div>
        </section>

        {/* Flags */}
        <section>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Eigenschaften</h3>
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={displayItem.is_equipment}
                onChange={(e) => handleChange("is_equipment", e.target.checked)}
                className="rounded border-gray-300 text-brand-600"
              />
              Equipment / Anlage
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={displayItem.is_sales_product}
                onChange={(e) => handleChange("is_sales_product", e.target.checked)}
                className="rounded border-gray-300 text-brand-600"
              />
              Im Shop anzeigen
            </label>
          </div>
        </section>

        {/* Stock */}
        <section>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Lagerbestand</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="label">Mindestbestand</label>
              <input
                type="number"
                className="input"
                value={displayItem.min_stock ?? ""}
                onChange={(e) => handleChange("min_stock", e.target.value ? Number(e.target.value) : null)}
              />
            </div>
            <div>
              <label className="label">Meldebestand</label>
              <input
                type="number"
                className="input"
                value={displayItem.reorder_point ?? ""}
                onChange={(e) => handleChange("reorder_point", e.target.value ? Number(e.target.value) : null)}
              />
            </div>
            <div>
              <label className="label">Maximalbestand</label>
              <input
                type="number"
                className="input"
                value={displayItem.max_stock ?? ""}
                onChange={(e) => handleChange("max_stock", e.target.value ? Number(e.target.value) : null)}
              />
            </div>
          </div>
        </section>

        {/* Pricing (shop items) */}
        {displayItem.is_sales_product && (
          <section>
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Preisgestaltung (Shop)</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Listenpreis CHF</label>
                <input
                  type="number"
                  step="0.01"
                  className="input"
                  value={displayItem.list_price_chf ?? ""}
                  onChange={(e) => handleChange("list_price_chf", e.target.value ? Number(e.target.value) : null)}
                />
              </div>
              <div>
                <label className="label">HS-Code (Zoll)</label>
                <input
                  className="input"
                  value={displayItem.hs_code ?? ""}
                  onChange={(e) => handleChange("hs_code", e.target.value || null)}
                  placeholder="z.B. 8483.10"
                />
              </div>
            </div>
          </section>
        )}

        {/* Metadata */}
        <section className="text-xs text-gray-400 border-t border-gray-100 pt-4">
          <p>Erstellt: {formatDateTime(item.created_at)}</p>
          <p>Geändert: {formatDateTime(item.updated_at)}</p>
          {item.approved_at && <p>Freigegeben: {formatDateTime(item.approved_at)}</p>}
        </section>
      </div>
    </div>
  );
}
